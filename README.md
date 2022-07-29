# qrzlogger

This script is a QRZ.com command line QSO logger.
It does the following:
  1) asks the user for a call sign
  2) displays available call sign info pulled from QRZ.com
  3) displays all previous QSOs with this call (pulled from QRZ.com logbook)
  4) asks the user to enter QSO specific data (date, time, report, band etc.)
  5) uploads the QSO to QRZ.com's logbook
  5) fetches the just uploaded QSO from QRZ.com for review
  7) starts again from 1)

# Screnshot

![screenshot](/screenshot.jpg?raw=true "screenshot")

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

 * execute the application with "python3 qrzlogger.py"
 * qrzlogger creates a default config file and states its location (e.g. _~/.qrzlogger.ini_)
 * adapt _~/.qrzlogger.ini_ to your needs. Important setting are:
    * station_call: This is your station call (must match with the QRZ.com logbook)
    * api_key: Your QRZ.com API key. You find it under "settings" in the QRZ.com logbook'
    * qrz_user: Your QRZ.com user name, typically your call sign'
    * qrz_pass: Your QRZ.com password (not the API key)'
 * execute the application again with "python3 qrzlogger.py"

# License

see ![LICENSE](LICENSE)