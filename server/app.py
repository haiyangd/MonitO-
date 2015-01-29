#!/usr/bin/env python

############ ###########################
###  Flask REST Api Implementation   ###
############ ###########################

_author_ = 'Nitheesh CS'
_email_  = 'nitheesh007@gmail.com'

import sys
import json
from flask import Flask, render_template, request, jsonify

# Initialize the Flask application
app = Flask(__name__)
app.debug = True

global clients

json_config=open('clients.json')
clients = json.load(json_config)

@app.route('/')
def index():
  print "Welcome"
  return render_template('index.html')
  #return None

@app.route('/post', methods = ['POST'])
def post():
  # Get the parsed contents of the form data
  data = request.json
  # Match the key with client ip
  try:
    key = data["key"]
    if key == clients[data["ServerIP"]]:
      print "key matched"
      filename = data["ServerIP"] + str(".json")
      # Output the data to file
      with open(filename, 'w') as outfile:
        json.dump(data, outfile, sort_keys = True, indent = 4)      
      # Return output
      return jsonify(data), 200
    else:
      _error = "Key is not valid!"
      return _error, 403
  except KeyError as e:
    _error = "Invalid key!"
    return _error, 403  

# Run
if __name__ == '__main__':
  app.run(
      host = "127.0.0.1",
      port = 8888
  )