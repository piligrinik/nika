import logging
from sc_client.models import ScAddr, ScLinkContentType, ScTemplate
from sc_client.constants import sc_type
from sc_client.client import search_by_template

from sc_kpm import ScAgentClassic, ScResult
from sc_kpm.sc_sets import ScSet
from sc_kpm.utils import (
    generate_link,
    get_link_content_data,
    check_connector, generate_connector,
    erase_connectors,
    search_element_by_non_role_relation,
    search_element_by_role_relation,
    get_element_system_identifier,
    search_connector
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
from googleapiclient.discovery import build
from threading import Thread

SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'
calendar_id = "primary"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s", datefmt="[%d-%b-%y %H:%M:%S]"
)


class AddEventAgent(ScAgentClassic):
    def __init__(self):
        super().__init__("action_add_calendar_event")

    def on_event(self, event_element: ScAddr, event_edge: ScAddr, action_element: ScAddr) -> ScResult:
        result = self.run(action_element)
        is_successful = result == ScResult.OK
        finish_action_with_status(action_element, is_successful)
        self.logger.info("WeatherAgent finished %s",
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
                    f"WeatherAgent: the message isn’t about adding calendar event")
                return ScResult.OK

            rrel_event_summary = ScKeynodes.resolve("rrel_event_summary", sc_type.CONST_NODE_ROLE)
            rrel_start_time = ScKeynodes.resolve("rrel_start_time", sc_type.CONST_NODE_ROLE)
            rrel_start_date = ScKeynodes.resolve("rrel_start_date", sc_type.CONST_NODE_ROLE)
            if (not rrel_event_summary.is_valid() or
                    not rrel_start_date.is_valid() or not rrel_start_time.is_valid()):
                self.logger.info("Calendar event necessary parameters weren't found")
                return ScResult.ERROR
            rrel_end_time = ScKeynodes.resolve("rrel_end_time", sc_type.CONST_NODE_ROLE)
            rrel_end_date = ScKeynodes.resolve("rrel_end_date", sc_type.CONST_NODE_ROLE)
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
        params = {}
        # search link addresses
        summary_addr = search_element_by_role_relation(message_addr, rrel_summary)
        start_date = search_element_by_role_relation(message_addr, rrel_start_date)
        start_time_addr = search_element_by_role_relation(message_addr, rrel_start_time)

        # search links content
        summary_content = get_link_content_data(summary_addr)
        start_date_content = get_link_content_data(start_date)
        start_time_content = get_link_content_data(start_time_addr)
        params = {
            'summary': summary_content,
            'start_date': start_date_content,
            'start_time': start_time_content
        }

        if rrel_end_date:
            end_date_addr = search_element_by_role_relation(message_addr, rrel_end_date)
            end_date_content = get_link_content_data(end_date_addr)
            params['end_date'] = end_date_content
        if rrel_end_time:
            end_time_addr = search_element_by_role_relation(message_addr, rrel_end_time)
            end_time_content = get_link_content_data(end_time_addr)
            params['end_time'] = end_time_content
        return params

    def convert_time(self, params):
        start_time = datetime.datetime.strptime(f"{params['start_date']}T{params['start_time']}:00",
                                                "%Y-%m-%dT%H:%M:%S")
        if 'end_date' in params.keys():
            if 'end_time' in params.keys():
                end_time = datetime.datetime.strptime(f"{params['end_date']}T{params['end_time']}:00",
                                                      "%Y-%m-%dT%H:%M:%S")
            else:
                end_time = datetime.datetime.strptime(f"{params['end_date']}T{params['start_time']}:00",
                                                      "%Y-%m-%dT%H:%M:%S")
        else:
            if 'end_time' in params.keys():
                end_time = datetime.datetime.strptime(f"{params['start_date']}T{params['end_time']}:00",
                                                      "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(days=1)
            else:
                end_time = start_time + datetime.timedelta(days=1)
        return start_time, end_time

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
            self.logger.info(f"WeatherAgent: finished with connection error")
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
                    "client_secret.json",
                    scopes=["https://www.googleapis.com/auth/calendar"]
                )
                creds = flow.run_local_server(port=0)

            with open(TOKEN_FILE, "w") as token_file:
                token_file.write(creds.to_json())
        return creds
