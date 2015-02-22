#!/usr/bin/env python

############ ###########################
###  Flask REST Api Implementation   ###
############ ###########################

_author_ = 'Nitheesh CS'
_email_  = 'nitheesh007@gmail.com'

import sys
import smtplib
import json, re
import glob, pygal
import email.utils, time
from pygal import Config
from termcolor import cprint
from pygal.style import Style
from multiprocessing import Process
from email.mime.text import MIMEText
from pygal.style import DarkColorizedStyle
from flask import Flask, render_template, request, jsonify, abort

# Initialize the Flask application
app = Flask(__name__)
app.debug = True

global clients
global activeClients
global loadAvg15Min
global loadAvg5Min
global loadAvg1Min
global MemUsage
global diskUsage

global sender
global receivers

sender = 'Monito admin <admin@linuxpanda.com>'
receivers = ['nitheesh.cs@powercms.in']

config = Config()
config.range=(.0001, 5)
config.legend_font_size=30
config.tooltip_font_size=30
config.legend_box_size=18
config.title_font_size=30
config.label_font_size=20
config.legend_at_bottom=True
config.major_label_font_size=20
config.no_data_text='Fetching data..'

config1 = Config()
config1.fill=True
config1.spacing=50
config1.range=(1, 100)
config1.legend_font_size=30
config1.tooltip_font_size=30
config1.legend_box_size=18
config1.title_font_size=30
config1.label_font_size=20
config1.legend_at_bottom=True
config1.major_label_font_size=20
config1.no_data_text='Fetching data..'

style1 = Style(
  #background='transparent',
  #plot_background='transparent',
  foreground='#53E89B',
  foreground_light='#53A0E8',
  foreground_dark='#630C0D',
  opacity='.6',
  opacity_hover='.9',  
  colors = ['#FF5050','#3366FF'])

activeClients = []

loadAvg15Min = {}
loadAvg5Min  = {}
loadAvg1Min  = {}

MemUsage = {}
diskUsage = {}

analysis = False

json_config=open('clients.json')
clients = json.load(json_config)

@app.route('/')
def index():
  # pat = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
  # match = pat.match('192.168.1.1')
  files = glob.glob('data/*.json')
  cprint (files, 'cyan')

  clients = {}

  for file in files:
    ip = file.split('/')[1][:-5]
    file = file[:-5]
    clients[file] = ip
    cprint (clients, 'green')

  return render_template('clients.html', clients=clients)
  # return render_template('index.html', data=data)
  #return None

@app.route('/chart')
def test():
    bar_chart = pygal.HorizontalStackedBar()
    bar_chart.title = "Remarquable sequences"
    bar_chart.x_labels = map(str, range(11))
    bar_chart.add('Fibonacci', [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55])
    bar_chart.add('Padovan', [1, 1, 1, 2, 2, 3, 4, 5, 7, 9, 12]) 
    chart = bar_chart.render(is_unicode=True)
    return render_template('chart.html', chart=chart )

@app.route('/post', methods = ['POST'])
def post():
  # Get the parsed contents of the form data
  data = request.json
  global analysis
  # Match the key with client ip
  try:
    key = data["key"]
    if key == clients[data["ServerIP"]]:
      client_ip = data["ServerIP"]
      cprint (client_ip + " key matched", 'blue')
      activeClients.append(client_ip)
      filename = data["ServerIP"] + str(".json")
      # Output the data to file

      if not client_ip in diskUsage:
        diskUsage[client_ip] = ""

      diskUsage[client_ip] = data['diskUsage']

      if not client_ip in loadAvg15Min:
        loadAvg15Min[client_ip] = []
        loadAvg5Min[client_ip]  = []
        loadAvg1Min[client_ip]  = []

      loadAvg15Min[client_ip].append(data['loadAvg15Min'])
      loadAvg5Min[client_ip].append(data['loadAvg5Min'])
      loadAvg1Min[client_ip].append(data['loadAvg1Min'])

      if not client_ip in MemUsage:  
        MemUsage[client_ip] = {}
        MemUsage[client_ip]['used'] = []

      used = float(data['memUsage']['used'])

      MemUsage[client_ip]['used'].append(used)

      if len(loadAvg15Min[client_ip]) == 25:
        loadAvg15Min[client_ip].pop(0)
        loadAvg5Min[client_ip].pop(0)
        loadAvg1Min[client_ip].pop(0)
        MemUsage[client_ip]['used'].pop(0)

      cprint (loadAvg15Min, 'yellow')
      cprint (MemUsage, 'white')

      AnalysisClientData(loadAvg5Min[client_ip], loadAvg1Min[client_ip], MemUsage[client_ip], diskUsage[client_ip])

      with open('data/' + str(filename), 'w') as outfile:
        json.dump(data, outfile, sort_keys = True, indent = 4)      
      # Return output
      return jsonify(data), 200
    else:
      _error = "Key is not valid!"
      return _error, 403
  except KeyError as e:
    print e
    _error = "Invalid key!"
    return _error, 403  

# Analaysis the current data and alert the admin.
def AnalysisClientData(loadAvg5, loadAvg1, MemUsg, diskUsg):
  try:
    cprint (sum(loadAvg1[-3:]), 'red')
    cprint (sum(MemUsg['used'][-3:]), 'red')
  except:
    pass  
  print diskUsg

def listToStr(lst):
    """This method makes comma separated list item string"""
    return ','.join(lst)

def sent_email_alert(message):
  print message
  msg = message
  msg_header = "From: " + sender + "\n" + \
               "To: " + listToStr(receivers) + "\n" + \
               "Subject: " + message + "\n"
  msg_body =  msg_header + msg
  try:
     smtpObj = smtplib.SMTP('localhost')
     smtpObj.sendmail(sender, receivers, msg_body)
     print "Successfully sent email"
  except:
     print "Error: unable to send email"
  return True


@app.route('/api/update', methods = ['GET', 'POST'])
def update():
  data_file_data = {}
  files = glob.glob('data/*.json')
  cprint (files, 'cyan')
  for file in files:
    data_file = file.split('/')[1]
    data_file = open(file)
    data_file_data[data_file] = json.load(data_file)
    data_file.close()
  print data_file_data
  return jsonify(data_file_data)

@app.route('/data/<ip>', methods = ['GET'])
def ClientData(ip):
  # if ip not in activeClients:
  #   return render_template('404.html'), 404
  try:
    json_data=open('data/' + str(ip) + str('.json'))
  except:  
    return render_template('404.html'), 404

  data = json.load(json_data)  
  json_data.close()

  bar_chart = pygal.Bar(config, style=DarkColorizedStyle)
  bar_chart.title = "Remarquable sequences"
  bar_chart.x_labels = map(str, range(11))
  bar_chart.add('Fibonacci', [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55])
  bar_chart.add('Padovan', [1, 1, 1, 2, 2, 3, 4, 5, 7, 9, 12]) 
  chart = bar_chart.render(is_unicode=True)
  #return render_template('chart.html', chart=chart )

  if not ip in diskUsage:
    diskUsage[ip] = None

  disk_used = float(data['diskUsage'])

  disk_chrt = pygal.Pie(config)
  disk_chrt.title = 'Disk Usage'
  disk_chrt.add('Used', disk_used)
  disk_chrt.add('free', float(100 - disk_used))
  disk_chart = disk_chrt.render(is_unicode=True)

  if not ip in MemUsage:
    MemUsage[ip] = {}
    MemUsage[ip]['used'] = []
  mem_used = MemUsage[ip]['used']
  mem_chart = pygal.Line(config1, style=style1)
  mem_chart.title = 'Memory Usage'
  mem_chart.add('Memory Used', mem_used)
  mem_crt = mem_chart.render(is_unicode=True)

  if not ip in loadAvg15Min:
    loadAvg15Min[ip] = []
    loadAvg5Min[ip]  = []
    loadAvg1Min[ip]  = []
  load_chart = pygal.Line(config)
  load_chart.title = 'Load Average'
  load_chart.add('loadAvg15Min', loadAvg15Min[ip])
  load_chart.add('loadAvg5Min', loadAvg5Min[ip])
  load_chart.add('loadAvg1Min', loadAvg1Min[ip])
  load_crt = load_chart.render(is_unicode=True)

  load_chart1 = pygal.Bar(config)
  load_chart1.title = 'Load Average'
  load_chart1.add('loadAvg15Min', loadAvg15Min[ip])
  load_chart1.add('loadAvg5Min', loadAvg5Min[ip])
  load_chart1.add('loadAvg1Min', loadAvg1Min[ip])
  load_crt1 = load_chart1.render(is_unicode=True)

  if not request.args:
    return render_template('index.html', 
      data=data, chart=chart, mem_crt=mem_crt, 
      load_chart=load_crt, disk_chart=disk_chart)

  if request.args['graph'] == 'mem':
    return render_template('graph.html', chart=mem_crt)
  elif request.args['graph'] == 'load':
    return render_template('graph.html', chart=load_crt)

# Run
if __name__ == '__main__':
  app.run(
      host = "127.0.0.1",
      port = 8888
  )