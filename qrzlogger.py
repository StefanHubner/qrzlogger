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
from colored import fore, back, style

# read the config file
config = configparser.ConfigParser()
config.read('config.ini')

# headers for all POST requests
headers = CaseInsensitiveDict()
headers["Content-Type"] = "application/x-www-form-urlencoded"

session = None
session_key = None

if config['qrzlogger']['log_file']:
    log_file = config['qrzlogger']['log_file']
else:
    log_file = "qrzlogger.log"

# Read user definable colors from config
if config['qrzlogger']['use_colors'] == "yes":
    inputcol = eval(config['qrzlogger']['inputcol'])
    hlcol = eval(config['qrzlogger']['hlcol'])
    defvalcol = eval(config['qrzlogger']['defvalcol'])
    errorcol = eval(config['qrzlogger']['errorcol'])
    successcol = eval(config['qrzlogger']['successcol'])
    tablecol = eval(config['qrzlogger']['tablecol'])
    logocol = eval(config['qrzlogger']['logocol'])
else:
    inputcol = style.RESET
    hlcol = style.RESET
    defvalcol = style.RESET
    errorcol = style.RESET
    successcol = style.RESET
    tablecol = style.RESET
    logocol = style.RESET

bandfreqs = {
    '160m' : '1.850',
    '80m' : '3.700',
    '60m' : '5.355',
    '40m' : '7.100',
    '30m' : '10.130',
    '20m' : '14.200',
    '17m' : '18.130',
    '15m' : '21.200',
    '12m' : '24.950',
    '10m' : '28.500',
    '6m' : '50.150',
    '2m' : '145.500',
    '70cm' : '432.300'
    }


# Generate a session for QRZ.com's xml service with
# the help of the QRZ.com username and password
def get_session():
    global session
    global session_key
    xml_auth_url = '''https://xmldata.QRZ.com/xml/current/?username={0}&password={1}'''.format(
        config['qrzlogger']['qrz_user'],config['qrzlogger']['qrz_pass'])
    try:
        session = requests.Session()
        session.verify = bool(os.getenv('SSL_VERIFY', True))
        r = session.get(xml_auth_url)
        if r.status_code == 200:
            raw_session = xmltodict.parse(r.content)
            session_key = raw_session.get('QRZDatabase').get('Session').get('Key')
            if session_key:
                return True
    except requests.exceptions.ConnectionError as e_conn:
        print(errorcol + "\nUnable to connect to xmldata.qrz.com:")
        print(e_conn)
        print("\nPlease check if\n * username and password are correct (see config.ini)\n * you are connected to the internet")
        print(style.RESET)
    except:
        print(errorcol + "\nsomething unexpected has happened:\n")
        print(e_conn)
        print(style.RESET)
    return False


# Sends a POST request to QRZ.com, checks for errors
# and returns the response
def sendRequest(post_data):
    try:
        resp = requests.post(config['qrzlogger']['api_url'], headers=headers, data=post_data)
        if resp.status_code == 200:
            str_resp = resp.content.decode("utf-8")
            response = urllib.parse.unquote(str_resp)
            resp_list = response.splitlines()
            if resp_list[0]:
                if "invalid api key" in resp_list[0]:
                    print(errorcol + "\nThe API key configured in config.ini is not correct.\n" + style.RESET)
                else:
                    return response
        elif resp.status_code == 404:
            print(errorcol + "\nThe API URL could not be found. Please check the URL in config.ini\n" + style.RESET)
    except requests.exceptions.ConnectionError as e_conn:
        print(errorcol + "\nUnable to connect to xmldata.qrz.com:")
        print(e_conn)
        print("\nPlease check if you are connected to the internet")
        print(style.RESET)
    except:
        print(errorcol + "\nsomething unexpected has happened:\n")
        print(e_conn)
        print(style.RESET)
    return None


# Query QRZ.com's xml api to gather information
# about a specific call sign
def getCallData(call):
    global session
    global session_key

    try:
        xml_url = """https://xmldata.QRZ.com/xml/current/?s={0}&callsign={1}""" .format(session_key, call)
        r = session.get(xml_url)
        raw = xmltodict.parse(r.content).get('QRZDatabase')
        calldata = raw.get('Callsign')
        if calldata:
            return calldata
    except requests.exceptions.ConnectionError as e_conn:
        print(errorcol + "\nUnable to connect to xmldata.qrz.com:")
        print(e_conn)
        print("\nPlease check if you are connected to the internet")
        print(style.RESET)
    except:
        print(errorcol + "\nsomething unexpected has happened:\n")
        print(e_conn)
        print(style.RESET)
    return None


# Query QRZ.com's logbook for all previous QSOs
# with a specific call sign or for a specific
# logid
def getQSOs(option):
    post_data = { 
        'KEY' : config['qrzlogger']['api_key'],
        'ACTION' : 'FETCH',
        'OPTION' : "TYPE:ADIF," + option
        }
    post_data = urllib.parse.urlencode(post_data)

    response = sendRequest(post_data)

    if response:
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
    else:
        return None


# Generate a pretty ascii table containing all
# previous QSOs with a specific call sign
def getQSOTable(result):
    t = PrettyTable(['Date', 'Time', 'Band', 'Mode', 'RST-S', 'RST-R', 'Power', 'Comment'])
    for qso in result:
        if "qso_date" in qso:
            date = datetime.datetime.strptime(qso["qso_date"], '%Y%m%d').strftime('%Y/%m/%d')
            time = datetime.datetime.strptime(qso["time_on"], '%H%M').strftime('%H:%M')
            # add missing fields to dict
            for field in ["band", "mode", "rst_sent", "rst_rcvd", "tx_pwr", "comment"]:
                if field not in qso:
                    qso[field] = ""
            t.add_row([date, time, qso["band"], qso["mode"], qso["rst_sent"], qso["rst_rcvd"], qso["tx_pwr"], qso["comment"]])
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
    freq = ""
    mode = config['qrzlogger']['mode']
    rst_rcvd = config['qrzlogger']['rst_rcvd']
    rst_sent = config['qrzlogger']['rst_sent']
    tx_pwr = config['qrzlogger']['tx_pwr']
    comment = ""

    # If this is the first try filling out the QSO fields
    # then we use defaults
    if qso is None:
        questions = {
            "qso_date" : ["QSO Date",qso_date],
            "time_on": ["QSO Time", time_on],
            "band": ["Band", band],
            "freq": ["Frequency", freq],
            "mode": ["Mode", mode],
            "rst_rcvd": ["RST Received", rst_rcvd],
            "rst_sent": ["RST Sent", rst_sent],
            "tx_pwr": ["Power (in W)", tx_pwr],
            "comment": ["Comment", comment]
            }
    # if this is not the first try, we pre-fill the
    # vaulues we got from the last try
    else:
        questions = qso

    # We now loop through all defined fields and ask
    # the user for input
    for q in questions:
        txt = inputcol + questions[q][0] + " [" + defvalcol + questions[q][1] + inputcol + "]:" + style.RESET
        inp = input(txt)
        # If the user just hits enter, we keep the default value.
        # If not, we keep the data provided by the user
        if inp == "c":
            return None
        if inp != "":
            questions[q][1] = inp
        # check if we are asking for the band
        if q == "band":
            # check if the band is in the bandfreqs dictionary
            if questions[q][1] in bandfreqs:
                # populate the frequency with a common freq of this band
                questions['freq'][1] = bandfreqs[questions[q][1]]
    return questions


# Sends the previously collected QSO information as a new
# QRZ.com logbook entry via the API
def sendQSO(qso):
    logid = "null"
    log_status = "FAILED:  "

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
    response = sendRequest(data)
    # Check if the upload failed and print out
    # the reason plus some additional info
    if response:
        if "STATUS=FAIL" in response:
            print(errorcol)
            print("QSO upload failed. QRZ.com has send the following reason:\n")
            resp_list = response.split("&")
            for item in resp_list:
                print(item)
            print("\nPlease review the following request that led to this error:\n")
            print(style.RESET)
            print(post_data)
        else:
            try:
                logid = re.search('LOGID=(\d+)', response).group(1)
            except:
                logid = "null"
            print(successcol)
            print("QSO successfully uploaded to QRZ.com (LOGID "+ logid + ")")
            log_status = "SUCCESS: "
            print(style.RESET)
        with open(log_file, "a") as log:
            log.write(log_status + adif + "\n")
        return logid
    else:
        print(errorcol + "\nA critical error occured. Please review all previous output." + style.RESET)



# ask a user a simple y/n question
# returns True if "y"
# returns False in "n"
def askUser(question):
    while True:
        inp = input("\n" + inputcol + question + " [" + defvalcol +  "y/n" + inputcol + "]: " + style.RESET)
        if inp == "y":
            return True
        elif inp == "n":
            return False


# Main routine
if __name__ == '__main__':

    keeponlogging = True

    # print an awesome banner
    print(logocol + "              _                        ")
    print("  __ _ _ _ __| |___  __ _ __ _ ___ _ _ ")
    print(" / _` | '_|_ / / _ \/ _` / _` / -_) '_|")
    print(" \__, |_| /__|_\___/\__, \__, \___|_|  ")
    print("    |_|             |___/|___/         " + style.RESET)

    # get a session after logging into QRZ with user/pass
    get_session()

    # Begin the main loop
    while keeponlogging:
        # query a call sign from the user
        resume = True
        call = input("\n\n%sEnter Callsign:%s " % (inputcol, style.RESET))
        # check if it has the format of a valid call sign
        # (at least 3 characters, only alphanumeric and slashes)
        if not (len(call) > 2 and call.replace("/", "").isalnum()):
            print(errorcol + "\nPlease enter a callsign with\n * at least 3 characters\n * only letters, numbers and slashes" + style.RESET)
            resume = False
        if resume:
            # make the call sign all upper case
            call = call.upper()
            # query call sign data from QRZ
            result = getCallData(call)
            # the query was successful
            if result:
                print ('\n%s%sQRZ.com results for %s%s' % (style.UNDERLINED, hlcol, call, style.RESET))
                # generate a nice ascii table with the result
                tab = getXMLQueryTable(result)
                # print the table
                print(tablecol)
                print(tab)
                print(style.RESET)
            # the query was unsuccessful
            else:
                print ('\n%s%s has no record on QRZ.com ¯\_(ツ)_/¯%s' % (errorcol, call, style.RESET))
                # ask the user if he/she likes to continue anyway
                if not askUser("Continue logging this call sign?"):
                    # restart from the beginning
                    resume = False
                print("")
            if resume:
                # pull all previous QSOs from tzhe QRZ logbook
                result = getQSOs("CALL:"+ call)
                # ignore this part if there were no previous QSOs
                if result and result[0]:
                    print ('%s%sPrevious QSOs with %s%s' % (style.UNDERLINED, hlcol, call, style.RESET))
                    # generate a nice ascii table with the result
                    tab = getQSOTable(result)
                    # print the table
                    print(tablecol)
                    print(tab)
                    print(style.RESET)

                print ('%s%sEnter new QSO details below%s%s (enter \'c\' to cancel)%s\n' % (style.UNDERLINED, hlcol, style.RESET, hlcol, style.RESET,))

                qso_ok = False
                qso = None

                # we now ask the user for QSO details until he/she is happy with the result
                while not qso_ok and resume:
                    # query QSO details from the user
                    qso = queryQSOData(qso)
                    # the user has answered all questions
                    if qso:
                        print ('\n%s%sPlease review your choices%s' % (style.UNDERLINED, hlcol, style.RESET))
                        # generate a pretty table
                        tab = getQSODetailTable(qso)
                        # print the table
                        print(tablecol)
                        print(tab)
                        print(style.RESET)
                        # ask user if everything is ok. If not, start over.
                        if askUser("Is this correct?"):
                            logid = sendQSO(qso)
                            if logid and logid != "null":
                                # pull the uploaded QSO from QRZ
                                result = getQSOs("LOGIDS:"+ logid)
                                if result and result[0]:
                                    #print ('%sQSO uploaded to QRZ.com:%s' % (hlcol, style.RESET))
                                    # generate a nice ascii table with the result
                                    tab = getQSOTable(result)
                                    # print the table
                                    print(tablecol)
                                    print(tab)
                                    print(style.RESET)
                                qso_ok = True
                    # the user has entered 'c' during the QSO detail entering process
                    else:
                        resume = False
                        

    print(inputcol)
    print("73!")
    print(style.RESET)
