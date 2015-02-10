#!/usr/bin/env python

############ ###########################
###  Flask REST Api Implementation   ###
############ ###########################

_author_ = 'Nitheesh CS'
_email_  = 'nitheesh007@gmail.com'

import sys
import json, re
import glob, pygal
from termcolor import cprint
from pygal import Config
from pygal.style import DarkColorizedStyle
from flask import Flask, render_template, request, jsonify

# Initialize the Flask application
app = Flask(__name__)
app.debug = True

global clients

global loadAvg15Min
global loadAvg5Min
global loadAvg1Min

config = Config()
config.legend_font_size=30
config.tooltip_font_size=30
config.legend_box_size=18
config.title_font_size=30
config.label_font_size=20
config.major_label_font_size=20
config.legend_at_bottom=True

loadAvg15Min = {}
loadAvg5Min  = {}
loadAvg1Min  = {}

json_config=open('clients.json')
clients = json.load(json_config)

@app.route('/')
def index():
  # pat = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
  # match = pat.match('192.168.1.1')
  files = glob.glob('data/*.json')
  cprint (files, 'cyan')
  return "Welcome"
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
  # Match the key with client ip
  try:
    key = data["key"]
    if key == clients[data["ServerIP"]]:
      print "key matched"
      client_ip = data["ServerIP"]
      filename = data["ServerIP"] + str(".json")
      # Output the data to file

      loadAvg15Min[client_ip].append(data['loadAvg15Min'])
      loadAvg5Min.append(data['loadAvg5Min'])
      loadAvg1Min.append(data['loadAvg1Min'])

      print loadAvg15Min

      if len(loadAvg15Min) == '50':
        loadAvg15Min.pop(0)
        loadAvg5Min.pop(0)
        loadAvg1Min.pop(0)

      with open('data/' + str(filename), 'w') as outfile:
        json.dump(data, outfile, sort_keys = True, indent = 4)      
      # Return output
      return jsonify(data), 200
    else:
      _error = "Key is not valid!"
      return _error, 403
  except KeyError as e:
    _error = "Invalid key!"
    return _error, 403  

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
  cprint (ip, 'red')
  json_data=open('data/' + str(ip) + str('.json'))
  data = json.load(json_data)  
  json_data.close()

  bar_chart = pygal.Bar(config, style=DarkColorizedStyle)
  bar_chart.title = "Remarquable sequences"
  bar_chart.x_labels = map(str, range(11))
  bar_chart.add('Fibonacci', [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55])
  bar_chart.add('Padovan', [1, 1, 1, 2, 2, 3, 4, 5, 7, 9, 12]) 
  chart = bar_chart.render(is_unicode=True)
  #return render_template('chart.html', chart=chart )

  pie_chart = pygal.Pie(config)
  cached = data['memUsage']['cached']
  res = data['memUsage']['res']
  pie_chart.title = 'Memory Usage'
  pie_chart.add('cached', cached)
  pie_chart.add('res', res)
  pie_crt = pie_chart.render(is_unicode=True)

  # temp = [1,2,3,4]
  # loadAvg15Min.append(data['loadAvg15Min'])
  # loadAvg5Min.append(data['loadAvg5Min'])
  # loadAvg1Min.append(data['loadAvg1Min'])

  line_chart = pygal.Line(config)
  line_chart.title = 'Load Average'
  line_chart.add('loadAvg15Min', loadAvg15Min)
  line_chart.add('loadAvg5Min', loadAvg5Min)
  line_chart.add('loadAvg1Min', loadAvg1Min)
  line_chart1 = line_chart.render(is_unicode=True)

  return render_template('index.html', data=data, chart=chart, pie_crt=pie_crt, mem_chart=line_chart1)

# Run
if __name__ == '__main__':
  app.run(
      host = "127.0.0.1",
      port = 8888
  )