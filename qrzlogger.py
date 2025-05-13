#!/usr/bin/env python3

"""
QRZLogger - A Python application to log QSOs directly to QRZ.com from the CLI

Author: Michael Clemens, DK1MI (qrzlogger@qrz.is)
Documentation: Please see the README.md file
License: Please see the LICENSE file
Repository: https://github.com/exitnode/qrzlogger
"""

import atexit
import csv
import configparser
import datetime
import os
import re
import signal
import sys
import urllib.parse
import zipfile
import readline
from datetime import timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any, Generator

import requests
import xmltodict
from colored import attr, fg
from prettytable import PrettyTable


# Global variables for interrupt handling
in_qso_entry = False


class Config:
    """Configuration manager for QRZLogger"""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration"""
        # Disable interpolation to handle % characters in values
        self.config = configparser.ConfigParser(interpolation=None)
        self.home_dir = str(Path.home())
        self.config_dir = Path(self.home_dir) / ".config" / "qrzlogger"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = config_path or (self.config_dir / 'qrzlogger.ini')
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration or create default if none exists"""
        if self.config_file.exists():
            self.config.read(self.config_file)
        else:
            self._create_default_config()
            print(f"\nNo configuration file found. A new configuration file has been created.")
            print(f"\nPlease edit the file {self.config_file} and restart the application.\n")
            sys.exit(0)

    def _create_default_config(self) -> None:
        """Create default configuration"""
        self.config['qrz.com'] = {
            'station_call': 'MYCALL',
            'api_key': '1234-ABCD-1234-A1B2',
            'qrz_user': 'MYCALL',
            'qrz_pass': 'my_secret_password',
            'xml_fields': '("call", "band", "mode", "qso_date", "time_on", "rst_sent", "rst_rcvd", "tx_pwr")'
        }
        self.config['files'] = {
            'cty': 'cty.csv',
            'cty_url': 'https://www.country-files.com/bigcty/download/bigcty.zip',
        }
        self.config['log'] = {
            'log_file': '/tmp/qrzlogger.log'
        }
        self.config['qso_defaults'] = {
            'band': '20m',
            'mode': 'SSB',
            'rst_rcvd': '59',
            'rst_sent': '59',
            'tx_pwr': '100'
        }
        self.config['colors'] = {
            'use_colors': 'yes',
            'inputcol': 'yellow',
            'hlcol': 'yellow',
            'defvalcol': 'light_blue',
            'errorcol': 'red',
            'successcol': 'green',
            'tablecol': 'light_blue',
            'logocol': 'yellow'
        }
        self.config['bandfreqs'] = {
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

        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(section, key, fallback=fallback)

    def get_section(self, section: str) -> Dict[str, str]:
        """Get entire configuration section"""
        return dict(self.config[section]) if section in self.config else {}


class ColorManager:
    """Manages color styling for the application"""

    def __init__(self, config: Config):
        """Initialize color settings"""
        self.config = config
        self.use_colors = config.get('colors', 'use_colors') == 'yes'

        # Default colors
        self.inputcol = attr('reset')
        self.hlcol = attr('reset')
        self.defvalcol = attr('reset')
        self.errorcol = attr('reset')
        self.successcol = attr('reset')
        self.tablecol = attr('reset')
        self.logocol = attr('reset')

        # Set colors from config if enabled
        if self.use_colors:
            self._configure_colors()

    def _configure_colors(self) -> None:
        """Set colors from configuration"""
        self.inputcol = fg(self.config.get('colors', 'inputcol'))
        self.hlcol = fg(self.config.get('colors', 'hlcol'))
        self.defvalcol = fg(self.config.get('colors', 'defvalcol'))
        self.errorcol = fg(self.config.get('colors', 'errorcol'))
        self.successcol = fg(self.config.get('colors', 'successcol'))
        self.tablecol = fg(self.config.get('colors', 'tablecol'))
        self.logocol = fg(self.config.get('colors', 'logocol'))

    def print_table(self, table: PrettyTable) -> None:
        """Print a table with table styling"""
        print(self.tablecol)
        print(table)
        print(attr('reset'))

    def format_input_prompt(self, prompt: str, default: str = "") -> str:
        """Format an input prompt with appropriate colors"""
        if default:
            return f"{self.inputcol}{prompt} [{self.defvalcol}{default}{self.inputcol}]: {attr('reset')}"
        return f"{self.inputcol}{prompt}: {attr('reset')}"

    def error(self, message: str) -> None:
        """Print an error message"""
        print(f"{self.errorcol}{message}{attr('reset')}")

    def success(self, message: str) -> None:
        """Print a success message"""
        print(f"{self.successcol}{message}{attr('reset')}")

    def highlight(self, message: str) -> None:
        """Print a highlighted message"""
        print(f"{self.hlcol}{message}{attr('reset')}")


class FileManager:
    """Handles file operations for QRZLogger"""

    def __init__(self, config: Config, colors: ColorManager):
        """Initialize the file manager"""
        self.config = config
        self.colors = colors
        self.config_dir = config.config_dir

        # Initialize file status
        self.check_cty = False

        # Data containers
        self.cty = []

        # Check and download necessary files
        self._check_files()

    def _check_files(self) -> None:
        """Check if necessary files exist and download them if needed"""
        self._check_cty_file()

        # Load data if files exist
        if self.check_cty:
            with open(self.config_dir / self.config.get('files', 'cty'), encoding='us-ascii') as csvfile:
                self.cty = list(csv.reader(csvfile, delimiter=','))

    def _check_cty_file(self) -> None:
        """Check if CTY file exists and download if needed"""
        cty_file = self.config_dir / self.config.get('files', 'cty')
        self.check_cty = cty_file.exists()

        if not self.check_cty:
            url = self.config.get('files', 'cty_url')
            self.colors.highlight(f"The file {cty_file} is missing.")
            self.colors.highlight(f"Trying to download {url}")

            try:
                zip_path = self.config_dir / "bigcty.zip"
                self._download_file(url, zip_path)

                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extract("cty.csv", path=self.config_dir)

                zip_path.unlink()  # Remove the zip file
                self.check_cty = cty_file.exists()

                if self.check_cty:
                    self.colors.success("File successfully downloaded and extracted.")
                else:
                    self.colors.error(f"Something went wrong while downloading {url}")
            except Exception as e:
                self.colors.error(f"Error downloading CTY file: {e}")

    @staticmethod
    def _download_file(url: str, destination: Path) -> Path:
        """Download a file from URL to local destination"""
        with requests.get(url, stream=True) as req:
            req.raise_for_status()
            with open(destination, 'wb') as f:
                for chunk in req.iter_content(chunk_size=8192):
                    f.write(chunk)
        return destination

    def get_cty_row(self, call: str) -> List[str]:
        """Find country data for a call sign in the CTY database"""
        if not self.check_cty:
            return ["-", "-", "-", "-", "-", "-", "-"]

        original_call = call

        while call:
            for row in self.cty:
                entities = row[9].replace(";", "").replace("=", "").split(" ")
                for prefix in entities:
                    if call == prefix:
                        return row

            # Progressively remove characters from the end of the call
            call = call[:-1]

        # If no match found
        return ["-", "-", "-", "-", "-", "-", "-"]


class CallSignUtils:
    """Utilities for processing call signs"""

    @staticmethod
    def remove_indicators(call: str) -> str:
        """Strip indicators like /P, /MM, etc. from a call sign"""
        # Set the return value to the original call
        cleaned_call = call

        # Check for suffix (e.g., /P)
        if call.endswith(("/P", "/MM", "/M", "/QRP")):
            cleaned_call = call.rsplit('/', 1)[0]

        # Check for prefix (e.g., DL/)
        if "/" in cleaned_call:
            cleaned_call = re.sub(r'^\w+/', "", cleaned_call)

        return cleaned_call


class QRZAPI:
    """Handles all QRZ.com API interactions"""

    def __init__(self, config: Config, colors: ColorManager):
        """Initialize QRZ API handler"""
        self.config = config
        self.colors = colors

        # QRZ.com URLs
        self.xml_url = "https://xmldata.QRZ.com/xml/current/"
        self.api_url = "https://logbook.qrz.com/api"

        # Headers for all POST requests
        self.headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        # Parse XML fields from config
        self.xml_fields = eval(config.get('qrz.com', 'xml_fields'))

    def get_session(self) -> Optional[str]:
        """Get a QRZ.com XML service session key"""
        data = {
            'username': self.config.get('qrz.com', 'qrz_user'),
            'password': self.config.get('qrz.com', 'qrz_pass')
        }

        try:
            with requests.Session() as session:
                session.verify = True
                result = session.post(self.xml_url, data=data)

                if result.status_code == 200:
                    raw_session = xmltodict.parse(result.content)

                    if raw_session.get('QRZDatabase', {}).get('Session', {}).get('Error'):
                        self.colors.error("\nError while logging into the QRZ.com XML Service:")
                        self.colors.error(raw_session.get('QRZDatabase', {}).get('Session', {}).get('Error'))
                        return None

                    return raw_session.get('QRZDatabase', {}).get('Session', {}).get('Key')

                self.colors.error(f"\nError connecting to QRZ.com: HTTP status {result.status_code}")
                return None

        except requests.exceptions.ConnectionError as e:
            self.colors.error("\nUnable to connect to xmldata.qrz.com:")
            self.colors.error(str(e))
            self.colors.error("\nPlease check if:\n * username and password are correct (see config.ini)\n * you are connected to the internet")
            return None
        except Exception as e:
            self.colors.error("\nUnexpected error occurred while connecting to QRZ.com:")
            self.colors.error(str(e))
            return None

    def get_call_data(self, call: str, session_key: str) -> Optional[Dict[str, str]]:
        """Query QRZ.com XML API for call sign information"""
        if not session_key:
            return None

        data = {
            's': session_key,
            'callsign': call
        }

        try:
            with requests.Session() as session:
                session.verify = True
                result = session.post(self.xml_url, data=data)

                if result.status_code == 200:
                    raw = xmltodict.parse(result.content).get('QRZDatabase', {})
                    calldata = raw.get('Callsign')
                    return calldata

                self.colors.error(f"\nError querying call data: HTTP status {result.status_code}")
                return None

        except requests.exceptions.ConnectionError as e:
            self.colors.error("\nUnable to connect to xmldata.qrz.com:")
            self.colors.error(str(e))
            self.colors.error("\nPlease check if you are connected to the internet")
            return None
        except Exception as e:
            self.colors.error("\nUnexpected error occurred while querying call data:")
            self.colors.error(str(e))
            return None

    def send_request(self, post_data: Dict[str, str]) -> Optional[str]:
        """Send a POST request to QRZ.com API"""
        try:
            encoded_data = urllib.parse.urlencode(post_data)
            resp = requests.post(self.api_url, headers=self.headers, data=encoded_data)

            if resp.status_code == 200:
                str_resp = resp.content.decode("latin-1")
                response = urllib.parse.unquote(str_resp)
                resp_list = response.splitlines()

                if resp_list and resp_list[0]:
                    if "invalid api key" in resp_list[0].lower():
                        self.colors.error("\nThe API key configured in config.ini is not correct.")
                        return None
                    return response
            elif resp.status_code == 404:
                self.colors.error("\nThe API URL could not be found. Please check the URL in config.ini")
                return None
            else:
                self.colors.error(f"\nAPI request failed with status code: {resp.status_code}")
                return None

        except requests.exceptions.ConnectionError as e:
            self.colors.error("\nUnable to connect to QRZ.com API:")
            self.colors.error(str(e))
            self.colors.error("\nPlease check if you are connected to the internet")
            return None
        except Exception as e:
            self.colors.error("\nUnexpected error occurred during API request:")
            self.colors.error(str(e))
            return None

    def get_qsos(self, option: str) -> List[Dict[str, str]]:
        """Query QRZ.com logbook for previous QSOs"""
        result = [{}]

        post_data = {
            'KEY': self.config.get('qrz.com', 'api_key'),
            'ACTION': 'FETCH',
            'OPTION': f"TYPE:ADIF,{option}"
        }

        response = self.send_request(post_data)

        if response:
            resp_list = response.splitlines()
            for resp in resp_list:
                if not resp:
                    result.append({})
                else:
                    # Check if this line contains a field we're interested in
                    matches = [s for s in self.xml_fields if f"{s}:" in resp]
                    if matches:
                        # Parse the field
                        resp = re.sub('&lt;', '', resp, flags=re.DOTALL)
                        resp = re.sub(':.*&gt;', ":", resp, flags=re.DOTALL)
                        value = re.sub('^.*:', "", resp, flags=re.DOTALL)
                        key = re.sub(':.*$', "", resp, flags=re.DOTALL)
                        result[-1][key] = value

        return result

    def send_qso(self, qso: Dict[str, List[str]], call: str, log_file: Path) -> Optional[str]:
        """Send QSO data to QRZ.com logbook"""
        logid = None
        log_status = "FAILED:  "

        # Construct ADIF QSO entry
        station_call = self.config.get('qrz.com', 'station_call')
        adif = f'<station_callsign:{len(station_call)}>{station_call}'
        adif += f'<call:{len(call)}>{call}'

        for field, (field_name, field_value) in qso.items():
            adif += f'<{field}:{len(field_value)}>{field_value}'

        adif += '<eor>'

        # Construct POST data
        post_data = {
            'KEY': self.config.get('qrz.com', 'api_key'),
            'ACTION': 'INSERT',
            'ADIF': adif
        }

        # Send the POST request to QRZ.com
        response = self.send_request(post_data)

        if response:
            if "STATUS=FAIL" in response:
                self.colors.error("\nQSO upload failed. QRZ.com has sent the following reason:\n")
                resp_list = response.split("&")
                for item in resp_list:
                    self.colors.error(item)

                self.colors.error("\nPlease review the following request that led to this error:\n")
                print(post_data)
            else:
                try:
                    logid = re.search('LOGID=(\d+)', response).group(1)
                    self.colors.success(f"\nQSO successfully uploaded to QRZ.com (LOGID {logid})")
                    log_status = "SUCCESS: "
                except Exception:
                    logid = None
                    self.colors.error("\nQSO upload to QRZ.com failed!")

            # Log the result
            try:
                with open(log_file, "a") as log:
                    log.write(f"{log_status}{adif}\n")
            except Exception as e:
                self.colors.error(f"Error writing to log file: {e}")

        return logid


class UIManager:
    """Manages user interface and interaction"""

    def __init__(self, config: Config, colors: ColorManager, file_manager: FileManager, qrz_api: QRZAPI):
        self.config = config
        self.colors = colors
        self.file_manager = file_manager
        self.qrz_api = qrz_api
        self.qso = None
        self.log_file = Path(config.get('log', 'log_file', '/tmp/qrzlogger.log'))
        self.recent_qso_limit = 5
        self.session_defaults = {
            'freq': config.get_section('bandfreqs')[config.get('qso_defaults', 'band')],
            'mode': config.get('qso_defaults', 'mode'),
            'tx_pwr': config.get('qso_defaults', 'tx_pwr')
        }

    def show_call_info(self, call: str, session_key: str) -> None:
        """Display information about a call sign"""
        cleaned_call = CallSignUtils.remove_indicators(call)
        result = self.qrz_api.get_call_data(call, session_key)

        if result:
            self.colors.print_table(self._get_xml_query_table(result))
        else:
            self.colors.error(f"\n{call.upper()} has no record on QRZ.com")
            if call != cleaned_call:
                result = self.qrz_api.get_call_data(cleaned_call, session_key)
                if result:
                    self.colors.highlight(f"\nShowing results for {cleaned_call} instead")
                    self.colors.print_table(self._get_xml_query_table(result))

        self._show_previous_qsos(call)

    def _show_previous_qsos(self, call: str) -> None:
        """Show previous QSOs with a call sign"""
        result = self.qrz_api.get_qsos(f"CALL:{call}")

        if result and result[0]:
            self.colors.highlight(f"Previous QSOs with {call.upper()}")
            table = self._get_qso_table(result)
            self.colors.print_table(table)

    def _get_qso_table(self, result: List[Dict[str, str]]) -> PrettyTable:
        """Generate a table of QSO information"""
        table = PrettyTable(['Date', 'Time', 'Band', 'Mode', 'RST-S', 'RST-R', 'Power', 'Distance'])

        for qso in result:
            if "qso_date" in qso:
                # Format date and time
                try:
                    date = datetime.datetime.strptime(qso["qso_date"], '%Y%m%d').strftime('%Y/%m/%d')
                    time = datetime.datetime.strptime(qso["time_on"], '%H%M').strftime('%H:%M')
                except ValueError:
                    date = qso["qso_date"]
                    time = qso["time_on"]

                # Ensure all fields exist
                fields = ["band", "mode", "rst_sent", "rst_rcvd", "tx_pwr", "distance"]
                for field in fields:
                    if field not in qso:
                        qso[field] = ""

                # Add row to table
                table.add_row([
                    date, time, qso["band"], qso["mode"],
                    qso["rst_sent"], qso["rst_rcvd"], qso["tx_pwr"],
                    qso["distance"]
                ])

        table.align = "r"
        return table

    def query_qso_data(self) -> Optional[Dict[str, List[str]]]:
        """Query QSO details from the user"""

        # Get current UTC time
        date_time = datetime.datetime.now(timezone.utc)
        dt_now = date_time.replace(tzinfo=timezone.utc)

        # Define questions based on mode and existing QSO data
        if self.qso is None:
            # Initial QSO entry - use defaults from config
                questions = {
                    "freq": ["Frequency", self.session_defaults['freq']],
                    "rst_rcvd": ["RST Received", self.config.get('qso_defaults', 'rst_rcvd')],
                    "rst_sent": ["RST Sent", self.config.get('qso_defaults', 'rst_sent')],
                    "mode": ["Mode", self.session_defaults['mode']],
                    "tx_pwr": ["Power (in W)", self.session_defaults['tx_pwr']],
                    "qso_date": ["QSO Date", dt_now.strftime("%Y%m%d")],
                    "time_on": ["QSO Time", dt_now.strftime("%H%M")]
                }
        else:
            # Use existing QSO data
            questions = self.qso

        # Process each field
        for field, (prompt, default) in questions.items():
            formatted_prompt = self.colors.format_input_prompt(prompt, default)
            user_input = input(formatted_prompt)

            # Handle special commands
            if user_input.lower() in ["quit", "exit"]:
                in_qso_entry = False
                sys.exit(0)

            # Use input or default
            if user_input:
                questions[field][1] = user_input

        return questions

    def _get_qso_detail_table(self, qso: Dict[str, List[str]]) -> PrettyTable:
        """Generate a table of QSO details for review"""
        table = PrettyTable(['key', 'value'])
        table.header = False
        table.align = "l"

        for field, (label, value) in qso.items():
            table.add_row([label, value])

        return table

    def show_qso_form(self, call: str) -> bool:
        """Display QSO entry form and handle submission, returns True if logged"""
        self.colors.highlight(f"\nCall: {call.upper()}{attr('reset')}")
        self.qso = self.query_qso_data()

        if not self.qso:
            return False

        # self.colors.highlight("\nPlease review your choices")
        # self.colors.print_table(self._get_qso_detail_table(self.qso))

        if self.confirm_and_submit_qso(call):
            return True
        return False

    def confirm_and_submit_qso(self, call: str) -> bool:
        """Ask user to confirm QSO details and submit if confirmed"""
        global in_qso_entry
        in_qso_entry = True

        prompt = self.colors.format_input_prompt("Upload?", "y/n")
        answer = input(f"\n{prompt} ").upper()

        if answer == "Y":
            # Attempt to send QSO
                logid = self.qrz_api.send_qso(self.qso, call, self.log_file)

                if logid:
                    # Success - get the uploaded QSO details
                    result = self.qrz_api.get_qsos(f"LOGIDS:{logid}")
                    self.session_defaults['freq'] = self.qso['freq'][1]
                    self.session_defaults['mode'] = self.qso['mode'][1]
                    self.session_defaults['tx_pwr'] = self.qso['tx_pwr'][1]

                    if result and result[0]:
                        table = self._get_qso_table(result)
                        self.colors.print_table(table)

                    return True  # QSO confirmed and submitted

        elif answer == "N":
            return False  # No, revise the QSO details


    def parse_qsos_from_log(self, file_handle) -> Generator[dict, None, None]:
        """Parse QSO entries from log file"""
        current_qso = {}
        for line in file_handle:
            line = line.strip()
            if line.startswith('<') and '>' in line:
                tag_start = line.find('<') + 1
                tag_end = line.find('>')
                tag = line[tag_start:tag_end].lower()
                value_start = tag_end + 1
                value_end = line.find('<', value_start)
                value = line[value_start:value_end].strip()
                current_qso[tag] = value
            elif not line and current_qso:
                yield current_qso
                current_qso = {}
        if current_qso:
            yield current_qso

    def _get_xml_query_table(self, result: Dict[str, str]) -> PrettyTable:
        """Generate a table of call sign information from QRZ.com"""
        table = PrettyTable(['key', 'value'])
        table.header = False
        table.align = "l"

        fields = [
            ("fname", "First Name"),
            ("name", "Last Name"),
            ("addr1", "Street"),
            ("addr2", "City"),
            ("state", "State"),
            ("country", "Country"),
            ("grid", "Locator"),
            ("email", "Email"),
            ("qslmgr", "QSL via:")
        ]

        for field, label in fields:
            if field in result:
                table.add_row([label, result[field]])

        return table


class QRZLogger:
    def __init__(self):
        self.config = Config()
        self.colors = ColorManager(self.config)
        self.file_manager = FileManager(self.config, self.colors)
        self.qrz_api = QRZAPI(self.config, self.colors)
        self.ui = UIManager(self.config, self.colors, self.file_manager, self.qrz_api)
        self.history_file =  Path.home() / ".config" / "qrzlogger" /  ".history"
        self._init_readline()

    def _init_readline(self):
        """Initialize command history support"""
        # Load existing history
        if self.history_file.exists():
            readline.read_history_file(self.history_file)

        # Set history length
        readline.set_history_length(100)

        # Tab completion (basic implementation)
        readline.parse_and_bind("tab: complete")
        readline.set_completer(self._completer)

    def _completer(self, text: str, state: int) -> Optional[str]:
        """Basic tab completion for commands"""
        options = [cmd for cmd in ['query', 'log', 'help', 'exit'] if cmd.startswith(text.lower())]
        return options[state] if state < len(options) else None

    def _save_history(self):
        """Save command history to file"""
        readline.write_history_file(self.history_file)

    def run(self):
        """Run the command prompt interface"""

        while True:
            try:
                cmd = input("\nQRZ> ").strip()
                if not cmd:
                    continue

                if cmd.lower() in ('exit', 'quit', ':q'):
                    print("73!\n")
                    self._save_history()
                    break

                if cmd.lower() == 'help':
                    self._print_help()
                    continue

                # Split command and arguments properly
                parts = cmd.split(maxsplit=1)
                command = parts[0].lower()
                call = parts[1] if len(parts) > 1 else None
                if len(cmd) > 1: # no y/n 
                    readline.add_history(cmd)

                if command == 'query':
                    if not call:
                        self.colors.error("Missing callsign. Usage: query <callsign>")
                        continue
                    self._handle_query(call)

                elif command == 'log':
                    if not call:
                        self.colors.error("Missing callsign. Usage: log <callsign>")
                        continue
                    self._handle_log(call)

                else:
                    self.colors.error(f"Unknown command: {command}")

            except KeyboardInterrupt:
                continue
            except Exception as e:
                self.colors.error(f"Error: {str(e)}")

    def _handle_query(self, call: str) -> None:
        """Handle query command"""
        session_key = self.qrz_api.get_session()
        self.ui.show_call_info(call, session_key)

        if call.upper() != self.config.get('qrz.com', 'station_call'):
            response = input("Log QSO? [y/n] ").strip().lower()
            if response in ('', 'y', 'yes'):
                self._handle_log(call)

    def _handle_log(self, call: str) -> None:
        """Handle log command"""
        session_key = self.qrz_api.get_session()
        if self.ui.show_qso_form(call):
            self.colors.success(f"QSO with {call.upper()} logged successfully!")

    def _print_help(self) -> None:
        """Show help information"""
        help_text = """
Available commands:
  query <callsign>  - Show information about a callsign
  log <callsign>    - Start logging a QSO with the specified callsign
  help              - Show this help message
  exit/quit         - Exit the program
"""
        print(help_text)


def main():
    try:
        logger = QRZLogger()
        logger.run()
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
