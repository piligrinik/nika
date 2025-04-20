import logging
from sc_client.models import ScAddr
from sc_client.constants import sc_type

from sc_kpm import ScAgentClassic, ScResult
from sc_kpm.utils import (
    get_link_content_data,
    check_connector,
    search_element_by_role_relation,
)
from sc_kpm.utils.action_utils import (
    generate_action_result,
    finish_action_with_status,
    get_action_arguments,
)
from sc_kpm import ScKeynodes

import requests
import os
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import re
import locale

SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_FILE = 'modules/googleCalendarModule/token.json'
CREDENTIALS_FILE = 'modules/googleCalendarModule/credentials.json'
calendar_id = "primary"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s", datefmt="[%d-%b-%y %H:%M:%S]"
)
locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')

class AddEventAgent(ScAgentClassic):
    def __init__(self):
        super().__init__("action_add_calendar_event")

    def on_event(self, event_element: ScAddr, event_edge: ScAddr, action_element: ScAddr) -> ScResult:
        result = self.run(action_element)
        is_successful = result == ScResult.OK
        finish_action_with_status(action_element, is_successful)
        self.logger.info("AddEventAgentAgent finished %s",
                         "successfully" if is_successful else "unsuccessfully")
        return result

    def run(self, action_node: ScAddr) -> ScResult:
        self.logger.info("AddEventAgent started")

        try:
            creds = self.get_authenticated_creds()
            access_token = creds.token
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
            message_addr = get_action_arguments(action_node, 1)[0]
            message_type = ScKeynodes.resolve(
                "concept_add_calendar_event_message", sc_type.CONST_NODE_CLASS)

            if not check_connector(sc_type.VAR_PERM_POS_ARC, message_type, message_addr):
                self.logger.info(
                    f"AddEventAgent: the message isn’t about adding calendar event")
                return ScResult.OK

            rrel_event_summary = ScKeynodes.resolve("rrel_event_summary", sc_type.CONST_NODE_ROLE)
            rrel_start_time = ScKeynodes.resolve("rrel_start_time", sc_type.CONST_NODE_ROLE)
            rrel_start_date = ScKeynodes.resolve("rrel_start_date", sc_type.CONST_NODE_ROLE)
            self.logger.info('FOUND ALL RRELS')
            if (not rrel_event_summary.is_valid() or
                    not rrel_start_date.is_valid() or not rrel_start_time.is_valid()):
                self.logger.info("Calendar event necessary parameters weren't found")
                return ScResult.ERROR
            rrel_end_time = ScKeynodes.get("rrel_end_time")
            rrel_end_date = ScKeynodes.get("rrel_end_date")
            params = self.get_event_params(message_addr, rrel_event_summary, rrel_start_date, rrel_start_time,
                                           rrel_end_date, rrel_end_time)
            # time convertion
            start_time, end_time = self.convert_time(params)

            # check if start_date > end_date
            if start_time > end_time:
                self.logger.info("Invalid end date detected")
                return ScResult.ERROR

            response = self.add_event_in_calendar(headers, params['summary'], start_time, end_time)
            if not response:
                self.logger.info("AddEventAgent: event wasn't generated in Google Calendar")
                return ScResult.ERROR
        except Exception as e:
            self.logger.info(f"AddEventAgent: finished with an error {e}")
            return ScResult.ERROR
        summary_addr = search_element_by_role_relation(message_addr, rrel_event_summary)
        generate_action_result(action_node, summary_addr)
        return ScResult.OK

    def get_event_params(self, message_addr: ScAddr, rrel_summary: ScAddr, rrel_start_date: ScAddr,
                         rrel_start_time: ScAddr, rrel_end_date: ScAddr | None, rrel_end_time: ScAddr | None):
        # search link addresses
        summary_addr = search_element_by_role_relation(message_addr, rrel_summary)
        start_date = search_element_by_role_relation(message_addr, rrel_start_date)
        start_time_addr = search_element_by_role_relation(message_addr, rrel_start_time)
        self.logger.info("Found args addresses")

        # search links content
        summary_content = get_link_content_data(summary_addr)
        start_date_content = get_link_content_data(start_date)
        start_time_content = get_link_content_data(start_time_addr)
        params = {
            'summary': summary_content,
            'start_date': start_date_content,
            'start_time': start_time_content
        }
        self.logger.info("All base content was found")

        if rrel_end_date:
            end_date_addr = search_element_by_role_relation(message_addr, rrel_end_date)
            if end_date_addr:
                end_date_content = get_link_content_data(end_date_addr)
                params['end_date'] = end_date_content
        if rrel_end_time:
            end_time_addr = search_element_by_role_relation(message_addr, rrel_end_time)
            if end_time_addr:
                end_time_content = get_link_content_data(end_time_addr)
                params['end_time'] = end_time_content
        self.logger.info("All content was found")
        return params

    def is_valid_russian_date(self, date_str):
        pattern = (r'^\d{1,2}\s(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s'
                   r'\d{4}$')
        return bool(re.fullmatch(pattern, date_str.lower()))

    def is_valid_ymd_date(self, date_str):
        pattern = r'^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
        return bool(re.fullmatch(pattern, date_str))

    def convert_time(self, params):
        # check date format
        if self.is_valid_russian_date(params['start_date']):
            start_date = datetime.datetime.strptime(params['start_date'], "%d %B %Y").strftime("%Y-%m-%d")
        elif not self.is_valid_ymd_date(params['start_date']):
            self.logger.info(f"AddEventAgent: invalid date format")
            return ScResult.ERROR
        else:
            start_date = params['start_date']

        start_date_time = datetime.datetime.strptime(f"{start_date}T{params['start_time']}:00",
                                                "%Y-%m-%dT%H:%M:%S")
        if 'end_date' in params.keys():
            if self.is_valid_russian_date(params['end_date']):
                end_date = datetime.datetime.strptime(params['end_date'], "%d %B %Y").strftime("%Y-%m-%d")
            elif not self.is_valid_ymd_date(params['end_date']):
                self.logger.info(f"AddEventAgent: invalid date format")
                return ScResult.ERROR
            else:
                end_date = params['end_date']
            if 'end_time' in params.keys():
                end_date_time = datetime.datetime.strptime(f"{end_date}T{params['end_time']}:00",
                                                      "%Y-%m-%dT%H:%M:%S")
            else:
                end_date_time = datetime.datetime.strptime(f"{end_date}T{params['start_time']}:00",
                                                      "%Y-%m-%dT%H:%M:%S")
        else:
            if 'end_time' in params.keys():
                end_date_time = datetime.datetime.strptime(f"{start_date}T{params['end_time']}:00",
                                                      "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(days=1)
            else:
                end_date_time = start_date_time + datetime.timedelta(days=1)
        return start_date_time, end_date_time

    def add_event_in_calendar(self, headers, summary, start_time, end_time):
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Europe/Moscow',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Europe/Moscow',
            },
        }
        try:
            # start request
            response = requests.post(
                f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
                headers=headers,
                json=event
            )
            if response.status_code == 200:
                return True
            else:
                return False
        except requests.exceptions.ConnectionError:
            self.logger.info(f"AddEventAgent: finished with connection error")
            return ScResult.ERROR

    def get_authenticated_creds(self):
        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())  # Автоматическое обновление
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE,
                    scopes=["https://www.googleapis.com/auth/calendar"]
                )
                creds = flow.run_local_server(port=0)

            with open(TOKEN_FILE, "w") as token_file:
                token_file.write(creds.to_json())
        return creds
