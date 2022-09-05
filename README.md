# qrzlogger

This script is a QRZ.com command line QSO logger.
It does the following:
  1) asks the user for a call sign
  2) displays available call sign info pulled from QRZ.com
  3) displays additional info on country, continent and LotW upload date of the call
  4) checks if the country has not been confirmed via LotW yet and alerts the user
  5) displays all previous QSOs with this call (pulled from QRZ.com logbook)
  6) asks the user to enter QSO specific data (date, time, report, band etc.)
  7) uploads the QSO to QRZ.com's logbook
  8) fetches the just uploaded QSO from QRZ.com for review
  9) starts again from 1)

# Screnshot

![screenshot](/screenshot_0.8.1.jpg?raw=true "screenshot")

# Installation

qrzlogger needs Python 3 and the following libraries:

 * xmltodict
 * prettytable
 * colored
 * requests

Furthermore, you need at least the XML subscription from QRZ.com.

Before installing qrzlogger, please make sure that the above mentioned libraries have been installed:

```
# python3 -m pip install xmltodict
# python3 -m pip install prettytable
# python3 -m pip install colored
# python3 -m pip install requests
```

To download or update qrzlogger, clone the repo:

```
# git clone https://codeberg.org/mclemens/qrzlogger.git
```

# Usage

 * execute the application with "python3 qrzlogger.py" for normal mode or with "python3 qrzlogger.py -c" for contest mode
 * qrzlogger creates a default config file and states its location (e.g. _~/.config/qrzlogger/qrzlogger.ini_)
 * adapt _~/.config/qrzlogger/qrzlogger.ini_ to your needs. Important setting are:
    * station_call: This is your station call (must match with the QRZ.com logbook)
    * api_key: Your QRZ.com API key. You find it under "settings" in the QRZ.com logbook'
    * qrz_user: Your QRZ.com user name, typically your call sign'
    * qrz_pass: Your QRZ.com password (not the API key)'
    * lotw/user: Enter here your lotw user name (your call sign). Leave at "N0CALL" to disable this feature.
    * lotw/password: Enter here your lotw password
    * lotw/mode: Enter here the mode you would like to filter the QSL download from LotW
 * execute the application again with "python3 qrzlogger.py"
 * the software now tries to download the following files and stores them into the configuration directory:
    * https://www.country-files.com/bigcty/download/bigcty.zip (will be extracted)
    * https://lotw.arrl.org/lotw-user-activity.csv
    * https://lotw.arrl.org/lotwuser/lotwreport.adi?login={}&password={}&qso_query=1&qso_qsl=yes&qso_mode={}&qso_qsldetail=yes&qso_qslsince=1970-01-01


# License

see ![LICENSE](LICENSE)
