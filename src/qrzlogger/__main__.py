#!/usr/bin/env python3

#######################################################################
#                            _                                        # 
#                __ _ _ _ __| |___  __ _ __ _ ___ _ _                 #
#               / _` | '_|_ / / _ \/ _` / _` / -_) '_|                #
#               \__, |_| /__|_\___/\__, \__, \___|_|                  #
#                  |_|             |___/|___/                         #
#                                                                     #
#                                                                     #
# A python application to log QSOs directly to QRZ.com from the CLI   #
#                                                                     #
# Author:           Michael Clemens, DL6MHC (qrzlogger@qrz.is)        #
#                                                                     # 
# Documentation:    Please see the README.md file                     #
# License:          Please see the LICENSE file                       #
# Repository:       https://github.com/exitnode/qrzlogger             #
#                                                                     #
#######################################################################


import requests
import urllib
import re
import datetime
import os
import sys
import xmltodict
from prettytable import PrettyTable
from requests.structures import CaseInsensitiveDict
from datetime import date
from datetime import timezone
import configparser
from colored import fore, back, style


class QRZLogger():

    # initialize things
    def __init__(self):

        self.version = "0.6.2"

        # Define the configuration object
        self.config = configparser.ConfigParser()
        self.config_file = os.path.expanduser('~/.qrzlogger.ini')

        self.writeDefaultConfig(self.config, self.config_file)

        if self.config and self.config['log']['log_file']:
            self.log_file = self.config['log']['log_file']
        else:
            self.log_file = os.path.expanduser('~/.qrzlogger.log')


        # QRZ.com URLs
        self.xml_url = "https://xmldata.QRZ.com/xml/current/"
        self.api_url = "https://logbook.qrz.com/api"

        # headers for all POST requests
        self.headers = CaseInsensitiveDict()
        self.headers["Content-Type"] = "application/x-www-form-urlencoded"

        # Default colors
        self.inputcol = style.RESET
        self.hlcol = style.RESET
        self.defvalcol = style.RESET
        self.errorcol = style.RESET
        self.successcol = style.RESET
        self.tablecol = style.RESET
        self.logocol = style.RESET

        # read colors from config and overwrite default vaulues
        self.configColors()


    # print an awesome banner
    def printBanner(self):
        v = self.version
        print(self.logocol)
        print("              _                        ")
        print("  __ _ _ _ __| |___  __ _ __ _ ___ _ _ ")
        print(" / _` | '_|_ / / _ \/ _` / _` / -_) '_|")
        print(" \__, |_| /__|_\___/\__, \__, \___|_|  ")
        print("    |_| -=DL6MHC=-  |___/|___/ v"+v+"  ")
        print(style.RESET)


    # Read color settings from config file
    def configColors(self):
        if self.config and self.config['colors']['use_colors'] == "yes":
            self.inputcol = eval(self.config['colors']['inputcol'])
            self.hlcol = eval(self.config['colors']['hlcol'])
            self.defvalcol = eval(self.config['colors']['defvalcol'])
            self.errorcol = eval(self.config['colors']['errorcol'])
            self.successcol = eval(self.config['colors']['successcol'])
            self.tablecol = eval(self.config['colors']['tablecol'])
            self.logocol = eval(self.config['colors']['logocol'])


    def writeDefaultConfig(self, config, file_name):
        if os.path.isfile(file_name):
            config.read(file_name)
        else:
            config = configparser.ConfigParser()
            config['qrz.com'] = {
                'station_call': 'MYCALL',
                'api_key': '1234-ABCD-1234-A1B2',
                'qrz_user': 'MYCALL',
                'qrz_pass': 'my_secret_password',
                'xml_fields': '("call", "band", "mode", "qso_date", "time_on", "rst_sent", "rst_rcvd", "comment")'}
            config['log'] = {
                'log_file': '/tmp/qrzlogger.log'}
            config['qso_defaults'] = {
                'band': '40m',
                'mode': 'SSB',
                'rst_rcvd': '59',
                'rst_sent': '59',
                'tx_pwr': '5'}
            config['colors'] = {
                'use_colors': 'yes',
                'inputcol': 'fore.YELLOW',
                'hlcol': 'fore.YELLOW',
                'defvalcol': 'fore.LIGHT_BLUE',
                'errorcol': 'fore.RED',
                'successcol': 'fore.GREEN',
                'tablecol': 'fore.LIGHT_BLUE',
                'logocol': 'fore.YELLOW'}
            config['bandfreqs'] = {
                '160m': '1.850',
                '80m': '3.700',
                '60m': '5.355',
                '40m': '7.100',
                '30m': '10.130',
                '20m': '14.200',
                '17m': '18.130',
                '15m': '21.200',
                '12m': '24.950',
                '10m': '28.500',
                '6m': '50.150',
                '2m': '145.500',
                '70cm': '432.300'
                }
                
            with open(file_name, 'w') as configfile:
              config.write(configfile) 
            print("\nNo configuration file found. A new configuration file has been created.")
            print("\nPlease edit the file " + file_name + " and restart the application.\n" )
            quit()
        return config


    #####################################################
    #             QRZ.com API Functions                 #
    #####################################################

    # Generate a session for QRZ.com's xml service with
    # the help of the QRZ.com username and password
    def get_session(self):
        session_key = None
        data = { 
            'username' : self.config['qrz.com']['qrz_user'],
            'password' : self.config['qrz.com']['qrz_pass']
            }

        try:
            session = requests.Session()
            session.verify = bool(os.getenv('SSL_VERIFY', True))
            r = session.post(self.xml_url, data=data)
            if r.status_code == 200:
                raw_session = xmltodict.parse(r.content)
                if raw_session.get('QRZDatabase').get('Session').get('Error'):
                    print(self.errorcol + "\nError while logging into the QRZ.com XML Service:\n")
                    print(raw_session.get('QRZDatabase').get('Session').get('Error'))
                    print(style.RESET)
                session_key = raw_session.get('QRZDatabase').get('Session').get('Key')
                if session_key:
                    return session_key
        except requests.exceptions.ConnectionError as e_conn:
            print(self.errorcol + "\nUnable to connect to xmldata.qrz.com:")
            print(e_conn)
            print("\nPlease check if\n * username and password are correct (see config.ini)\n * you are connected to the internet")
            print(style.RESET)
        except:
            print(self.errorcol + "\nsomething unexpected has happened:\n")
            print(style.RESET)
        return session_key


    # Sends a POST request to QRZ.com, checks for errors
    # and returns the response
    def sendRequest(self, post_data):
        try:
            resp = requests.post(self.api_url, headers=self.headers, data=post_data)
            if resp.status_code == 200:
                str_resp = resp.content.decode("utf-8")
                response = urllib.parse.unquote(str_resp)
                resp_list = response.splitlines()
                if resp_list[0]:
                    if "invalid api key" in resp_list[0]:
                        print(self.errorcol + "\nThe API key configured in config.ini is not correct.\n" + style.RESET)
                    else:
                        return response
            elif resp.status_code == 404:
                print(self.errorcol + "\nThe API URL could not be found. Please check the URL in config.ini\n" + style.RESET)
        except requests.exceptions.ConnectionError as e_conn:
            print(self.errorcol + "\nUnable to connect to xmldata.qrz.com:")
            print(e_conn)
            print("\nPlease check if you are connected to the internet")
            print(style.RESET)
        except:
            print(self.errorcol + "\nsomething unexpected has happened:\n")
            print(e_conn)
            print(style.RESET)
        return None


    # Query QRZ.com's xml api to gather information
    # about a specific call sign
    def getCallData(self, call, session_key):

        data = { 
            's' : session_key,
            'callsign' : call
            }

        try:
            session = requests.Session()
            session.verify = bool(os.getenv('SSL_VERIFY', True))
            r = session.post(self.xml_url, data=data)
            raw = xmltodict.parse(r.content).get('QRZDatabase')
            calldata = raw.get('Callsign')
            if calldata:
                return calldata
        except requests.exceptions.ConnectionError as e_conn:
            print(self.errorcol + "\nUnable to connect to xmldata.qrz.com:")
            print(e_conn)
            print("\nPlease check if you are connected to the internet")
            print(style.RESET)
        except:
            print(self.errorcol + "\nsomething unexpected has happened:\n")
            print(style.RESET)
        return None


    # Query QRZ.com's logbook for all previous QSOs
    # with a specific call sign or for a specific
    # logid
    def getQSOs(self, option):
        post_data = { 
            'KEY' : self.config['qrz.com']['api_key'],
            'ACTION' : 'FETCH',
            'OPTION' : "TYPE:ADIF," + option
            }
        post_data = urllib.parse.urlencode(post_data)

        response = self.sendRequest(post_data)

        if response:
            resp_list = response.splitlines()
            result = [{}]
            for i in resp_list:
                if not i:
                    result.append({})
                else:
                    if any(s+":" in i for s in self.config['qrz.com']['xml_fields']):
                        i = re.sub('&lt;','',i, flags=re.DOTALL)
                        i = re.sub(':.*&gt;',":",i, flags=re.DOTALL)
                        v = re.sub('^.*:',"",i, flags=re.DOTALL)
                        k = re.sub(':.*$',"",i, flags=re.DOTALL)
                        result[-1][k] = v
            return result
        else:
            return None


    # Sends the previously collected QSO information as a new
    # QRZ.com logbook entry via the API
    def sendQSO(self, qso, call):
        logid = "null"
        log_status = "FAILED:  "

        # construct ADIF QSO entry
        adif = '<station_callsign:' + str(len(self.config['qrz.com']['station_call'])) + '>' + self.config['qrz.com']['station_call']
        adif += '<call:' + str(len(call)) + '>' + call
        for field in qso:
            adif += '<' + field + ':' + str(len(qso[field][1])) + '>' + qso[field][1]
        adif += '<eor>'

        # construct POST data
        post_data = { 'KEY' : self.config['qrz.com']['api_key'], 'ACTION' : 'INSERT', 'ADIF' : adif }

        # URL encode the payload
        data = urllib.parse.urlencode(post_data)
        # send the POST request to QRZ.com
        response = self.sendRequest(data)
        # Check if the upload failed and print out
        # the reason plus some additional info
        if response:
            if "STATUS=FAIL" in response:
                print(self.errorcol)
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
                print(self.successcol)
                print("QSO successfully uploaded to QRZ.com (LOGID "+ logid + ")")
                log_status = "SUCCESS: "
                print(style.RESET)
            with open(self.log_file, "a") as log:
                log.write(log_status + adif + "\n")
            return logid
        else:
            print(self.errorcol + "\nA critical error occured. Please review all previous output." + style.RESET)



    #####################################################
    #     Functions for generating  ASCII Tables        #
    #####################################################

    # Generate a pretty ascii table containing all
    # previous QSOs with a specific call sign
    def getQSOTable(self, result):
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
    def getXMLQueryTable(self, result):
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
    def getQSODetailTable(self, qso):
        t = PrettyTable(['key', 'value'])
        for q in qso:
            t.add_row([qso[q][0], qso[q][1]])
        t.align = "l"
        t.header = False    
        return t



    #####################################################
    #          User Interaction Functions               #
    #####################################################

    # Queries QSO specific data from the user via
    # the command line
    def queryQSOData(self, qso):
        dt = datetime.datetime.now(timezone.utc)
        dt_now = dt.replace(tzinfo=timezone.utc)

        # pre-fill the fields with date, time and
        # default values from the config file
        qso_date = dt_now.strftime("%Y%m%d")
        time_on = dt_now.strftime("%H%M")
        band = self.config['qso_defaults']['band']
        freq = ""
        mode = self.config['qso_defaults']['mode']
        rst_rcvd = self.config['qso_defaults']['rst_rcvd']
        rst_sent = self.config['qso_defaults']['rst_sent']
        tx_pwr = self.config['qso_defaults']['tx_pwr']
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
            txt = self.inputcol + questions[q][0] + " [" + self.defvalcol + questions[q][1] + self.inputcol + "]:" + style.RESET
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
                try:
                    # populate the frequency with a common freq of this band
                    bandfreqs = dict(self.config.items('bandfreqs'))
                    questions['freq'][1] = bandfreqs[questions[q][1]]
                except:
                    print(self.errorcol + "\nUnable to read default frequency values from config file." + style.RESET)

        return questions


    # ask a user a simple y/n question
    # returns True if "y"
    # returns False in "n"
    def askUser(self, question):
        while True:
            inp = input("\n" + self.inputcol + question + " [" + self.defvalcol +  "y/n" + self.inputcol + "]: " + style.RESET)
            if inp == "y":
                return True
            elif inp == "n":
                return False



#####################################################
#                  Main Routine                     #
#####################################################


def main():

    q = QRZLogger()
    q.printBanner()

    keeponlogging = True
    session_key = None

    # Begin the main loop
    while keeponlogging:
        # get a session after logging into QRZ with user/pass
        session_key = q.get_session()
        # query a call sign from the user
        resume = True
        call = input("\n\n%sEnter Callsign:%s " % (q.inputcol, style.RESET))
        # check if it has the format of a valid call sign
        # (at least 3 characters, only alphanumeric and slashes)
        if not (len(call) > 2 and call.replace("/", "").isalnum()):
            print(q.errorcol + "\nPlease enter a callsign with\n * at least 3 characters\n * only letters, numbers and slashes" + style.RESET)
            resume = False
        if resume:
            # make the call sign all upper case
            call = call.upper()
            # query call sign data from QRZ
            result = q.getCallData(call, session_key)
            # the query was successful
            if result:
                print ('\n%s%sQRZ.com results for %s%s' % (style.UNDERLINED, q.hlcol, call, style.RESET))
                # generate a nice ascii table with the result
                tab = q.getXMLQueryTable(result)
                # print the table
                print(q.tablecol)
                print(tab)
                print(style.RESET)
            # the query was unsuccessful
            else:
                print ('\n%s%s has no record on QRZ.com ¯\_(ツ)_/¯%s' % (q.errorcol, call, style.RESET))
                # ask the user if he/she likes to continue anyway
                if not q.askUser("Continue logging this call sign?"):
                    # restart from the beginning
                    resume = False
                print("")
            if resume:
                # pull all previous QSOs from tzhe QRZ logbook
                result = q.getQSOs("CALL:"+ call)
                # ignore this part if there were no previous QSOs
                if result and result[0]:
                    print ('%s%sPrevious QSOs with %s%s' % (style.UNDERLINED, q.hlcol, call, style.RESET))
                    # generate a nice ascii table with the result
                    tab = q.getQSOTable(result)
                    # print the table
                    print(q.tablecol)
                    print(tab)
                    print(style.RESET)

                print ('%s%sEnter new QSO details below%s%s (enter \'c\' to cancel)%s\n' % (style.UNDERLINED, q.hlcol, style.RESET, q.hlcol, style.RESET,))

                qso_ok = False
                qso = None

                # we now ask the user for QSO details until he/she is happy with the result
                while not qso_ok and resume:
                    # query QSO details from the user
                    qso = q.queryQSOData(qso)
                    # the user has answered all questions
                    if qso:
                        print ('\n%s%sPlease review your choices%s' % (style.UNDERLINED, q.hlcol, style.RESET))
                        # generate a pretty table
                        tab = q.getQSODetailTable(qso)
                        # print the table
                        print(q.tablecol)
                        print(tab)
                        print(style.RESET)
                        # ask user if everything is ok. If not, start over.
                        if q.askUser("Is this correct?"):
                            logid = q.sendQSO(qso, call)
                            if logid and logid != "null":
                                # pull the uploaded QSO from QRZ
                                result = q.getQSOs("LOGIDS:"+ logid)
                                if result and result[0]:
                                    #print ('%sQSO uploaded to QRZ.com:%s' % (hlcol, style.RESET))
                                    # generate a nice ascii table with the result
                                    tab = q.getQSOTable(result)
                                    # print the table
                                    print(q.tablecol)
                                    print(tab)
                                    print(style.RESET)
                                qso_ok = True
                    # the user has entered 'c' during the QSO detail entering process
                    else:
                        resume = False
                        
    print(q.inputcol)
    print("73!")
    print(style.RESET)


if __name__ == "__main__":
    sys.exit(main())
