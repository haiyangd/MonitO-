#!/usr/bin/env python

################# #####################
#### Linux Server Monitoring Script ###
################# #####################

_author_ = 'Nitheesh CS'
_email_  = 'nitheesh.cs007@gmail.com'

_sent_mail = False

import re
import time
import json
import urllib2
import smtplib
import logging
import requests
import email.utils
import multiprocessing
import subprocess, sys, os
from termcolor import cprint
from operator import itemgetter
from collections import OrderedDict
from email.mime.text import MIMEText

global sender
global receivers

sender = 'Monito Admin <admin@linuxpanda.com>'
receivers = ['nitheesh.cs@powercms.in']

try:
    unicode = unicode
except:
    def unicode(object, *args, **kwargs):
        return str(object)
    
_log = logging.getLogger(__name__)  #module level logging

def get_data():
    """
    Function to get the data this module provides.
    
    Returns:
        dict containing data.
    """
    
    data = {
        'loadAvg1Min': 0,  #load average 1 min
        'loadAvg5Min': 0,  #load average 5 min
        'loadAvg15Min': 0,  #load average 15 min
        'cpuUsage': [],  #usage distribution for each cpu
        'memUsage': {},  #memory usage 
        'diskUsage': "",
        'networkReads': [],  #network reads per second for each interface
        'networkWrites': [],  #network writes per second for each interface
        'diskReads': [],  #disk reads per second for each disk
        'diskWrites': [],  #disk writes per second for each disk
        'ServiceStatus': ""
    }

    #metrics that doesnt need sampling
    data['loadAvg1Min'], data['loadAvg5Min'], data['loadAvg15Min'] = get_load_avg()  #get load avg
    #data['memUsage'].update(get_mem_usage())  #memory usage
    data['memUsage'].update(get_memory_usage())

    data['diskUsage'] = get_disk_usage()
    
    #metrics that needs sampling
    #they are written as a generator so that we can sleep before collection again
    #we sample twice
    sampling_duration, sampling_count = 1, 2
    cpu_usage_gen = get_cpu_usage(sampling_duration)  #generator for cpu usage
    net_rw_gen = get_net_rw(sampling_duration)  #generator for network read write
    disk_rw_gen = get_disk_rw(sampling_duration)  #generator for disk read write
    
    while sampling_count > 0:
        try:
            cpu_usage = next(cpu_usage_gen)
        except (StopIteration, GeneratorExit):
            cpu_usage = {}
        except Exception as e:
            cpu_usage = {}
            _log.error('Failed to sample CPU usage; %s' % unicode(e))
            
        try:
            net_rw = next(net_rw_gen)
        except (StopIteration, GeneratorExit):
            net_rw = {}
        except Exception as e:
            net_rw = {}
            _log.error('Failed to sample network R/W; %s' % unicode(e))
            
        try:
            disk_rw = next(disk_rw_gen)
        except (StopIteration, GeneratorExit):
            disk_rw = {}
        except Exception as e:
            disk_rw = {}
            _log.error('Failed to sample disk R/W; %s' % unicode(e))
            
        sampling_count -= 1
        sampling_count and time.sleep(sampling_duration)  #sleep before sampling again
    
    #append cpu usage for each cpu core
    for cpu, usage in cpu_usage.items():
        data['cpuUsage'].append({'name': cpu, 'value': usage})
        
    #append network read and write for each interface
    for interface, rw in net_rw.items():
        data['networkReads'].append({'name': interface, 'value': rw['reads']})
        data['networkWrites'].append({'name': interface, 'value': rw['writes']})        
        
    #append disk read and write for each logical disk
    for device, rw in disk_rw.items():
        data['diskReads'].append({'name': device, 'value': rw['reads']})
        data['diskWrites'].append({'name': device, 'value': rw['writes']})
    
    return data

def get_load_avg():
    """
    Function to get load avg.
    
    Returns:
        [loadAvg1Min, loadAvg5Min, loadAvg15Min]
    """
    
    with open('/proc/loadavg') as f:
        line = f.readline()
    
    return [float(x) for x in line.split()[:3]]

def get_mem_usage():
    """
    Function to get memory usage.
    
    Returns:
        dict containing memory usage stats
    """
    
    mem_total, mem_free, vm_total, mem_cached = 0, 0, 0, 0
    
    with open('/proc/meminfo') as f:
        for line in f:
            if line.startswith('MemTotal:'):
                mem_total = int(line.split()[1])
            elif line.startswith('MemFree:'):
                mem_free = int(line.split()[1])
            elif line.startswith('VmallocTotal:'):
                vm_total = int(line.split()[1])
            elif line.startswith('Cached:'):
                mem_cached = int(line.split()[1])
                
    return {
        'total': mem_total,
        'res': mem_total - mem_free,
        'virt': vm_total,
        'cached': mem_cached
    }

def get_cpu_usage(*args):
    """
    Generator to get the cpu usage in percentage.
        
    Yields:
        dict containing cpu usage percents for each cpu
    """
    
    keys = ['us', 'ni', 'sy', 'id', 'wa', 'hi', 'si', 'st']  #usage % to be returned
    
    with open('/proc/stat') as f1:
        with open('/proc/stat') as f2:
            content1 = f1.read()  #first collection
            yield {}  #yield so that caller can put delay before sampling again
            content2 = f2.read()  #second collection
            
    cpu_count = multiprocessing.cpu_count()  #total number of cpu cores available

    lines1, lines2 = content1.splitlines(), content2.splitlines()

    # print lines1
    # print lines2

    data, deltas = {}, {}
    
    #if only one cpu available, read only the first line, else read total cpu count lines starting from the second line
    i, cpu_count = (1, cpu_count + 1) if cpu_count > 1 else (0, 1)
    
    #extract deltas
    while i < cpu_count:
        line_split1 = lines1[i].split()
        line_split2 = lines2[i].split()
        deltas[line_split1[0]] = [int(b) - int(a) for a, b in zip(line_split1[1:], line_split2[1:])]
        i += 1
    
    for key in deltas:
        #calculate the percentage
        total = sum(deltas[key])
        data[key] = dict(zip(keys, [100 - (100 * (float(total - x) / total)) for x in deltas[key]]))
    
    yield data

def get_net_rw(sampling_duration):
    """
    Generator to get network reads and writes for the duration given.
    
    Args:
        sampling_duration: time in seconds between the two collection.
    
    Yields:
        dict containing network read and writes for each interface.
    """
        
    with open('/proc/net/dev') as f1:
        with open('/proc/net/dev') as f2:
            content1 = f1.read()  #first collection
            yield {}  #yield so that caller can put delay before sampling again
            content2 = f2.read()  #second collection
            
    #network interfaces
    interfaces = [interface[:-1].strip() for interface in re.findall('^\s*.+:', content1, flags = re.MULTILINE)]
            
    #initialize the dict with interfaces and values
    data = dict(zip(interfaces, [dict(zip(['reads', 'writes'], [0, 0])) for interface in interfaces]))
            
    for line in content1.splitlines():  #read through first collection
        for interface in [interface_x for interface_x in interfaces if '%s:' % interface_x in line]:
            fields = line.split('%s:' % interface)[1].split()
            data[interface]['reads'] = int(fields[0])
            data[interface]['writes'] = int(fields[8])
            break
    
    for line in content2.splitlines():  #read through second collection
        for interface in [interface_x for interface_x in interfaces if '%s:' % interface_x in line]:
            fields = line.split('%s:' % interface)[1].split()
            data[interface]['reads'] = (int(fields[0]) - data[interface]['reads']) / float(sampling_duration)
            data[interface]['writes'] = (int(fields[8]) - data[interface]['writes']) / float(sampling_duration)
            break
    
    yield data

def get_disk_rw(sampling_duration):
    """
    Generator to get disk reads and writes for the duration given.
    
    Args:
        sampling_duration: time in seconds between the two collection.
    
    Yields:
        dict containing disk reads and writes for each device.
    """
    
    #get te list of devices
    with open('/proc/partitions') as f:
        devices = [re.search('\s([^\s]+)$', line).group(1).strip() for line in re.findall('^\s*[0-9]+\s+[0-9]+\s+[0-9]+\s+.+$', f.read(), flags = re.MULTILINE)]
    
    with open('/proc/diskstats') as f1:
        with open('/proc/diskstats') as f2:
            content1 = f1.read()  #first collection
            yield {}  #yield so that caller can put delay before sampling again
            content2 = f2.read()  #second collection
            
    #initialize the dict with interfaces and values
    data = dict(zip(devices, [dict(zip(['reads', 'writes'], [0, 0])) for device in devices]))

    for line in content1.splitlines():  #read through first collection
        for device in [device_x for device_x in devices if '%s ' % device_x in line]:
            fields = line.strip().split('%s ' % device)[1].split()
            data[device]['reads'] = int(fields[0])
            data[device]['writes'] = int(fields[4])
            break
    
    for line in content2.splitlines():  #read through second collection
        for device in [device_x for device_x in devices if '%s ' % device_x in line]:
            fields = line.strip().split('%s ' % device)[1].split()
            data[device]['reads'] = (int(fields[0]) - data[device]['reads']) / float(sampling_duration)
            data[device]['writes'] = (int(fields[4]) - data[device]['writes']) / float(sampling_duration)
            break            
            
    yield data

def get_service_status(status, service):
    command = "sudo service " + str(service) + str(" status")
    p = subprocess.Popen(command, shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
    status[service] = p.communicate()[0].strip('\n')


def get_apache_status(status):
    command = "sudo service apache2 status"
    p = subprocess.Popen(command, shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
    status['apache'] = p.communicate()[0].strip('\n')

def get_mysql_status(status):
    command = "sudo service mysql status"
    p = subprocess.Popen(command, shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
    status['mysql'] = p.communicate()[0].strip('\n')

def get_memory_usage():
    command1 = "free | grep Mem | awk '{print $3/$2 * 100.0}'"
    command2 = "free | grep Mem | awk '{print $4/$2 * 100.0}'"
    p = subprocess.Popen(command1, shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
    used = p.communicate()[0].strip('\n')    
    p = subprocess.Popen(command2, shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
    free = p.communicate()[0].strip('\n')

    return {
        'free': free,
        'used': used
    }

def get_disk_usage():
    command = "df -hl | awk '/^\/dev\/sd[ab]/ { sum+=$5 } END { print sum }'"
    p = subprocess.Popen(command, shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
    disk_used = p.communicate()[0].strip('\n')    
    return disk_used

def get_apache_connections():
    command = "sudo netstat -anp |grep 'tcp\|udp' | awk '{print $5}' | \
               cut -d: -f1 | sort | uniq -c | sort -r -n | awk '{$3=$4=\"\"; print $0}'"
    p = subprocess.Popen(command, shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
    out = p.communicate()[0].split('  \n')
    dic = {}
    for conn in out:
      try:
        _con,_ip = conn.split()
        dic[_ip] = _con
      except ValueError:
        pass
    dic = dict((k, v) for k, v in dic.iteritems() if v) 
    # print sorted(dic.iteritems(), key=itemgetter(1), reverse=True) 
    # print sorted(dic.values(), key=int, reverse=True)
    return dic

def post_data_to_server(_data, server_uri):
  cprint ("Connecting to server..", "yellow", attrs=['bold'])
  headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
  try:
    req = requests.post(server_uri, data=json.dumps(_data), headers=headers)
    if req.status_code == 200:
      cprint ("Data sent successfully!", "white")
      return True
    else:
      print req.text
  except:
    cprint ("Waiting for the server to respond!", 'red')
    return False  

def main():
  status = {}   
  json_config=open('config.json')
  config = json.load(json_config)
  server_uri = config['server']
  count = 0
  email_sent = False
  server_check_interval = 5

  server_reachable = check_server_conn(server_check_interval, config['server_ip'])

  while True:
    if server_reachable:
      data = get_data()
      for service in config['services']:
        get_service_status(status, service)
      data['apache_conns'] = get_apache_connections()
      data['key'] = config['key']
      data['ServerIP'] = config['ip']
      data['ServiceStatus'] = status

      sent_success = post_data_to_server(data, server_uri)

      if not sent_success:
        server_reachable = False
        message = "Server not reachable..."
        # Don't spam
        if not email_sent:
          if _sent_mail:
            email_sent = sent_email_alert(message)
        else:
          count = count + 1
          # Sent reminder
          if count == 3:
            email_sent = False
            count = 0
    else:
      server_reachable = check_server_conn(server_check_interval, config['server_ip'])

    time.sleep(10)

def check_server_conn(interval, server):
    try:
        response = urllib2.urlopen(server,timeout=1)
        return True
    except urllib2.URLError as err: 
      cprint ("No connection to the server!", 'red')
      pass
    return False

def listToStr(lst):
    """This method makes comma separated list item string"""
    return ','.join(lst)

def sent_email_alert(message):
  msg = "This is body"
  msg_header = "From: " + sender + "\n" + \
               "To: " + listToStr(receivers) + "\n" + \
               "Subject: " + message + "\n"
  msg_body =  msg_header + msg
  try:
     smtpObj = smtplib.SMTP('localhost')
     smtpObj.sendmail(sender, receivers, msg_body)
     cprint ("Successfully sent email", "white")
  except:
     cprint ("Error: unable to send email","red")
  return True

if __name__ == '__main__':
  main()