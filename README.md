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

# Dependencies

qrzlogger needs the following libraries:

 * xmltodict
 * prettytable
 * colored

These libraries can be installed with the following commands:

```
# sudo pip install xmltodict prettytable colored
```

Furthermore, you need at least the XML subscription from QRZ.com.

# Installation

 * copy _qrzlogger.py_ into a directory
 * execute with "python3 qrzlogger.py"
 * the application creates a default config file and states its location (_~/.qrzlogger.ini_)
 * adapt _~/.qrzlogger.ini_ to your needs
 * execute the application again with "python3 qrzlogger.py"

# License

see ![LICENSE](LICENSE)
