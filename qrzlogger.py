#!/usr/bin/env python3

# qrzlogger
# =========
#
# This script is a QRZ.com command line QSO logger.
# It does the following:
#   1) asks the user for a call sign
#   2) displays available call sign info pulled from QRZ.com
#   3) displays all previous QSOs with this call (pulled from QRZ.com logbook)
#   4) alles the user to enter QSO specific data (date, time, report, band etc.)
#   5) uploads the QSO to QRZ.com's logbook
#   6) lists the last 5 logged QSOs ((pulled from QRZ.com logbook)
#   7) starts again from 1)
#
#
# MIT License
#
# Copyright (c) 2021 Michael Clemens, DL6MHC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


# WARNING: This software is beta and is really not working properly yet!
# I'll remove this warning when it's done


import requests
import urllib
import re
import datetime
import os
import xmltodict
from prettytable import PrettyTable
from requests.structures import CaseInsensitiveDict
from datetime import date
from datetime import timezone
import configparser

# read in the config
config = configparser.ConfigParser()
config.read('config.ini')

headers = CaseInsensitiveDict()
headers["Content-Type"] = "application/x-www-form-urlencoded"

session = None
session_key = None


# Generate a session for QRZ.com's xml service with
# the help of the QRZ.com username and password
def get_session():
    global session
    global session_key
    xml_auth_url = '''https://xmldata.QRZ.com/xml/current/?username={0}&password={1}'''.format(
        config['qrzlogger']['qrz_user'],config['qrzlogger']['qrz_pass'])
    session = requests.Session()
    session.verify = bool(os.getenv('SSL_VERIFY', True))
    r = session.get(xml_auth_url)
    if r.status_code == 200:
        raw_session = xmltodict.parse(r.content)
        session_key = raw_session.get('QRZDatabase').get('Session').get('Key')
        if session_key:
            return True
    return False


# Query QRZ.com's xml api to gather information
# about a specific call sign
def getCallData(call):
    global session
    global session_key

    xml_url = """https://xmldata.QRZ.com/xml/current/?s={0}&callsign={1}""" .format(session_key, call)
    r = session.get(xml_url)
    if r.status_code != 200:
        print("nope")
    raw = xmltodict.parse(r.content).get('QRZDatabase')
    if not raw:
        print("nope")
    if raw['Session'].get('Error'):
        errormsg = raw['Session'].get('Error')
    else:
        calldata = raw.get('Callsign')
        if calldata:
            return calldata
    return "nope"


# Query QRZ.com's logbook for all previous QSOs
# with a specific call sign
def getQSOsForCallsign(callsign):
    option = "TYPE:ADIF,CALL:"+callsign
    fetch = { 'KEY' : config['qrzlogger']['api_key'], 'ACTION' : 'FETCH', 'OPTION' : option}
    data = urllib.parse.urlencode(fetch)

    resp = requests.post(config['qrzlogger']['api_url'], headers=headers, data=data)
    #resp = requests.post(config['qrzlogger']['api_url'], data=fetch)

    str_resp = resp.content.decode("utf-8") 
    response = urllib.parse.unquote(str_resp)

    resp_list = response.splitlines()
    result = [{}]
    for i in resp_list:
        if not i:
            result.append({})
        else:
            if any(s+":" in i for s in config['qrzlogger']['xml_fields']):
                i = re.sub('&lt;','',i, flags=re.DOTALL)
                i = re.sub(':.*&gt;',":",i, flags=re.DOTALL)
                v = re.sub('^.*:',"",i, flags=re.DOTALL)
                k = re.sub(':.*$',"",i, flags=re.DOTALL)
                result[-1][k] = v

    return result


# Generate a pretty ascii table containing all
# previous QSOs with a specific call sign
def getQSOTable(result):
    t = PrettyTable(['Date', 'Time', 'Band', 'Mode', 'RST-S', 'RST-R', 'Comment'])
    for d in result:
        if "qso_date" in d:
            date = datetime.datetime.strptime(d["qso_date"], '%Y%m%d').strftime('%Y/%m/%d')
            time = datetime.datetime.strptime(d["time_on"], '%H%M').strftime('%H:%M')
            comment = ""
            try:
                comment = d["comment"]
            except:
                comment = ""
            t.add_row([date, time, d["band"], d["mode"], d["rst_sent"], d["rst_rcvd"], comment])
    t.align = "r"
    return t

# Print a pretty ascii table containing all interesting
# data found for a specific call sign
def getXMLQueryTable(result):
    t = PrettyTable(['key', 'value'])
    if "fname" in result:
        t.add_row(["First Name", result["fname"]])
    if "name" in result:
        t.add_row(["Last Name", result["name"]])
    if "addr1" in result:
        t.add_row(["Street", result["addr1"]])
    if "addr2" in result:
        t.add_row(["City", result["addr2"]])
    if "state" in result:
        t.add_row(["State", result["state"]])
    if "country" in result:
        t.add_row(["Country", result["country"]])
    if "grid" in result:
        t.add_row(["Locator", result["grid"]])
    if "email" in result:
        t.add_row(["Email", result["email"]])
    if "qslmgr" in result:
        t.add_row(["QSL via:", result["qslmgr"]])
    t.align = "l"
    t.header = False    
    return t


# Print a pretty ascii table containing all
# previously entered user data
def getQSODetailTable(qso):
    t = PrettyTable(['key', 'value'])
    for q in qso:
        t.add_row([qso[q][0], qso[q][1]])
    t.align = "l"
    t.header = False    
    return t


# Queries QSO specific data from the user via
# the command line
def queryQSOData(qso):
    dt = datetime.datetime.now(timezone.utc)
    dt_now = dt.replace(tzinfo=timezone.utc)

    qso_date = dt_now.strftime("%Y%m%d")
    qso_time = dt_now.strftime("%H%M")
    band = "40m"
    mode = "SSB"
    rst_rcvd = "59"
    rst_sent = "59"
    power = "100"
    comment = ""

    if qso is None:
        questions = {
            "qso_date" : ["QSO Date: ",qso_date],
            "qso_time": ["QSO Time: ", qso_time],
            "band": ["Band: ", band],
            "mode": ["Mode: ", mode],
            "rst_rcvd": ["RST Received: ", rst_rcvd],
            "rst_sent": ["RST Sent: ", rst_sent],
            "power": ["Power (in W): ", power],
            "comment": ["Comment: ", comment]
            }
    else:
        questions = qso

    for q in questions:
        inp = input(questions[q][0]+" ["+questions[q][1]+"]: " )
        if inp != "":
            questions[q][1] = inp

    return questions


# Sends the previously collected QSO information as a new
# QRZ.com logbook entry via the API
def sendQSO(qso):

    mycall = "DL6MHC"
    '''
    band = qso['band'][1]
    mode = qso['mode'][1]
    qso_date = qso['qso_date'][1]
    qso_time = qso['qso_time'][1]
    r_rcvd = qso['r_rcvd'][1]
    r_sent = qso['r_sent'][1]
    power=qso['power'][1]
    comment=qso['comment'][1]
    '''

    insert = { 'KEY' : config['qrzlogger']['api_key'], 'ACTION' : 'INSERT', 'ADIF' :
        '<band:' + str(len(qso['band'][1])) + '>' + qso['band'][1] +
        '<mode:' + str(len(qso['mode'][1])) + '>' + qso['mode'][1] +
        '<call:' + str(len(call)) + '>' + call +
        '<qso_date:' + str(len(qso['qso_date'][1])) + '>' + qso['qso_date'][1] +
        '<station_callsign:' + str(len(mycall)) + '>' + mycall +
        '<time_on:' + str(len(qso['qso_time'][1])) + '>' + qso['qso_time'][1] +
        '<rst_rcvd:' + str(len(qso['rst_rcvd'][1])) + '>' + qso['rst_rcvd'][1] +
        '<rst_sent:' + str(len(qso['rst_sent'][1])) + '>' + qso['rst_sent'][1] +
        '<power:' + str(len(qso['power'][1])) + '>' + qso['power'][1] +
        '<comment:' + str(len(qso['comment'][1])) + '>' + qso['comment'][1] +
        '<eor>'}
    print(insert)

    data = urllib.parse.urlencode(insert)
    #print(data)
    #resp = requests.post(config['qrzlogger']['api_url'], data=insert)
    resp = requests.post(config['qrzlogger']['api_url'], headers=headers, data=data)

    #str_resp = resp.content.decode("utf-8")
    #response = urllib.parse.unquote(str_resp)
    #print(res)

    return result 


# Main routine
if __name__ == '__main__':

    get_session()
    call = input("Enter Callsign: ")

    print('\nQRZ.com results for {0}:\n'.format(call))

    result = getCallData(call)
    tab = getXMLQueryTable(result)
    print(tab)

    print('\n\nPrevious QSOs with {0}:\n'.format(call))

    result = getQSOsForCallsign(call)
    tab = getQSOTable(result)
    print(tab)

    print('\nEnter new QSO details below ("c" to cancel, "b" to go one entry back):\n')

    qso_ok = False
    qso = None
   
    while not qso_ok:
        # query QSO details from thbe user
        qso = queryQSOData(qso)
        # generate a pretty table
        tab = getQSODetailTable(qso)
        print(tab)
        # ask user if everything is ok. If not, start over.
        inp = input("Is this correct? [y/n]: " )
        if inp == "y":
            res = sendQSO(qso)
            print(res)

            qso_ok = True

