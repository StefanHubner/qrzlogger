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

# read the config file
config = configparser.ConfigParser()
config.read('config.ini')

# headers for all POST requests
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
    post_data = { 
            'KEY' : config['qrzlogger']['api_key'], 
            'ACTION' : 'FETCH', 
            'OPTION' : "TYPE:ADIF,CALL:" + callsign 
            }
    post_data_enc = urllib.parse.urlencode(post_data)

    resp = requests.post(config['qrzlogger']['api_url'], headers=headers, data=post_data_enc)

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

    # pre-fill the fields with date, time and
    # default values from the config file
    qso_date = dt_now.strftime("%Y%m%d")
    time_on = dt_now.strftime("%H%M")
    band = config['qrzlogger']['band']
    mode = config['qrzlogger']['mode']
    rst_rcvd = config['qrzlogger']['rst_rcvd']
    rst_sent = config['qrzlogger']['rst_sent']
    tx_pwr = config['qrzlogger']['tx_pwr']
    comment = ""

    # If this is the first try filling out the QSO fields
    # then we use defaults
    if qso is None:
        questions = {
            "qso_date" : ["QSO Date: ",qso_date],
            "time_on": ["QSO Time: ", time_on],
            "band": ["Band: ", band],
            "mode": ["Mode: ", mode],
            "rst_rcvd": ["RST Received: ", rst_rcvd],
            "rst_sent": ["RST Sent: ", rst_sent],
            "tx_pwr": ["Power (in W): ", tx_pwr],
            "comment": ["Comment: ", comment]
            }
    # if this is not the first try, we pre-fill the
    # vaulues we got from the last try
    else:
        questions = qso

    # We now loop through all defined fields and ask
    # the user for input
    for q in questions:
        inp = input(questions[q][0]+" ["+questions[q][1]+"]: " )
        # If the user just hits enter, we keep the default value.
        # If not, we keep the data provided by the user
        if inp != "":
            questions[q][1] = inp

    return questions


# Sends the previously collected QSO information as a new
# QRZ.com logbook entry via the API
def sendQSO(qso):
    is_ok = False

    # construct ADIF QSO entry
    adif = '<station_callsign:' + str(len(config['qrzlogger']['station_call'])) + '>' + config['qrzlogger']['station_call']
    adif += '<call:' + str(len(call)) + '>' + call
    for field in qso:
        adif += '<' + field + ':' + str(len(qso[field][1])) + '>' + qso[field][1]
    adif += '<eor>'

    # construct POST data
    post_data = { 'KEY' : config['qrzlogger']['api_key'], 'ACTION' : 'INSERT', 'ADIF' : adif }

    # URL encode the payload
    data = urllib.parse.urlencode(post_data)
    # send the POST request to QRZ.com
    resp = requests.post(config['qrzlogger']['api_url'], headers=headers, data=data)
    str_resp = resp.content.decode("utf-8")
    response = urllib.parse.unquote(str_resp)
    # Check if the upload failed and print out
    # the reason plus some additional info
    if "STATUS=FAIL" in response:
        print("\nQSO upload failed. QRZ.com has send the following reason:\n")
        resp_list = response.split("&")
        for item in resp_list:
            print(item)
        print("\nPlease review the following request that led to this error:\n")
        print(post_data)
    else:
        print("QSO successfully uploaded to QRZ.com")
        is_ok = True
    return is_ok


# ask a user a simple y/n question
# returns True if "y"
# returns False in "n"
def askUser(question):
    while True:
        inp = input("\n" + question + " [y/n]: ")
        if inp == "y":
            return True
        elif inp == "n":
            return False


# Main routine
if __name__ == '__main__':

    keeponlogging = True
    get_session()

    print("              _                        ")
    print("  __ _ _ _ __| |___  __ _ __ _ ___ _ _ ")
    print(" / _` | '_|_ / / _ \/ _` / _` / -_) '_|")
    print(" \__, |_| /__|_\___/\__, \__, \___|_|  ")
    print("    |_|             |___/|___/         ")

    while keeponlogging:
        call = input("\n\nEnter Callsign: ")

        print('\nQRZ.com results for {0}:\n'.format(call))

        result = getCallData(call)
        tab = getXMLQueryTable(result)
        print(tab)

        print('\n\nPrevious QSOs with {0}:\n'.format(call))

        result = getQSOsForCallsign(call)
        tab = getQSOTable(result)
        print(tab)

        print('\nEnter new QSO details below:\n')

        qso_ok = False
        qso = None
        ask_try_again = False
       
        while not qso_ok:
            # query QSO details from thbe user
            qso = queryQSOData(qso)
            # generate a pretty table
            tab = getQSODetailTable(qso)
            print(tab)
            # ask user if everything is ok. If not, start over.
            if askUser("Is this correct?"):
                qso_ok = sendQSO(qso)
                # QSO successfully sent.
                if qso_ok:
                    qso = None
                    keeponlogging = askUser("Log another QSO?")
                # QSO upload failed
                else:
                    ask_try_again = True
            else:
                ask_try_again = True
            # We ask the user if he/she wants to try again
            # and - if not - another QSO should be logged
            if ask_try_again:
                if not askUser("Try again?"):
                    # user answered with "n"
                    # we quit the loop and reset the QSO fields
                    qso_ok = True
                    qso = None
                    if not askUser("Log another QSO?"):
                        # quit the application
                        keeponlogging = False

    print("\nBye, bye!")
