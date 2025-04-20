import json
import logging
from sc_client.models import ScAddr, ScLinkContent, ScLinkContentType
from sc_client.constants import sc_type
from sc_client.client import set_link_contents
from sc_kpm import ScAgentClassic, ScResult
from sc_kpm.utils import (
    get_link_content_data,
    check_connector,
    search_element_by_role_relation,
    search_element_by_non_role_relation
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

SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = 'modules/googleCalendarModule/credentials.json'
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
        self.logger.info("Finished %s",
                         "successfully" if is_successful else "unsuccessfully")
        return result

    def run(self, action_node: ScAddr) -> ScResult:
        self.logger.info("Started")

    # try:
        access_token = self.get_authenticated_token()
        if not access_token:
            return ScResult.ERROR
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        message_addr = get_action_arguments(action_node, 1)[0]
        message_type = ScKeynodes.get("concept_add_calendar_event_message")
        
        if not check_connector(
            sc_type.VAR_PERM_POS_ARC, 
            message_type, 
            message_addr
            ):
            self.logger.info(
                f"The message isn’t about adding calendar event")
            return ScResult.OK

        rrel_event_summary = ScKeynodes.resolve("rrel_event_summary", sc_type.CONST_NODE_ROLE)
        rrel_start_time = ScKeynodes.resolve("rrel_start_time", sc_type.CONST_NODE_ROLE)
        
        self.logger.info('Found all necessary rrels')
        
        if (
            not rrel_event_summary.is_valid() 
            or not rrel_start_time.is_valid()
            ):
            self.logger.info("Calendar event necessary parameters weren't found")
            return ScResult.ERROR
        
        rrel_end_time = ScKeynodes.get("rrel_end_time")
        params = self.get_event_params(
            message_addr, 
            rrel_event_summary,
            rrel_start_time, 
            rrel_end_time
            )

        # check if start_date > end_date
        if params['start_time'] > params['end_time']:
            self.logger.info("Invalid end date detected")
            return ScResult.ERROR

        response = self.add_event_in_calendar(
            headers, params['summary'], 
            params['start_time'], 
            params['end_time']
            )
        if not response:
            self.logger.info("Event wasn't generated in Google Calendar")
            return ScResult.ERROR
    # except Exception as e:
    #     self.logger.info(f"AddEventAgent: finished with an error {e}")
    #     return ScResult.ERROR
        summary_addr = search_element_by_role_relation(message_addr, rrel_event_summary)
        generate_action_result(action_node, summary_addr)
        return ScResult.OK

    def get_event_params(
        self, 
        message_addr: ScAddr, 
        rrel_summary: ScAddr,
        rrel_start_time: ScAddr, 
        rrel_end_time: ScAddr | None
        ) -> dict:
        
        # search link addresses
        summary_link = search_element_by_role_relation(message_addr, rrel_summary)
        start_time_link = search_element_by_role_relation(message_addr, rrel_start_time)
        end_time_link = search_element_by_role_relation(message_addr, rrel_end_time)
        self.logger.info("Found rrel nodes")

        # search links content
        summary = get_link_content_data(summary_link)
        start_time = datetime.datetime.fromisoformat(
            get_link_content_data(start_time_link)
            )
        params = {
            'summary': summary,
            'start_time': start_time
        }
        self.logger.info("All base content was found")

        if end_time_link:
            end_time = datetime.datetime.fromisoformat(
            get_link_content_data(end_time_link)
            )
            params['end_time'] = end_time    
            self.logger.info("Unnecessary content was found")
        else: 
            end_time = start_time + datetime.timedelta(hours=1)
            params['end_time'] = end_time
        
        return params

    def add_event_in_calendar(
        self, 
        headers, 
        summary: str, 
        start_time: datetime.datetime, 
        end_time: datetime.datetime
        ) -> ScResult:
        
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
            self.logger.info(f"Finished with connection error")
            return ScResult.ERROR

    def get_authenticated_token(self) -> str | None:
        creds = None
        nrel_google_access_token = ScKeynodes.get('nrel_google_access_token')
        current_user_node = ScKeynodes.get('current_user')
        access_token_link = search_element_by_non_role_relation(
            current_user_node, 
            nrel_google_access_token
            )
        self.logger.warning(f'{get_link_content_data(access_token_link)=}')
        if nrel_google_access_token and current_user_node:
            self.logger.info("Found necessary auth nodes")
            creds_dict = json.loads(get_link_content_data(access_token_link))
            creds = Credentials.from_authorized_user_info(creds_dict)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())  # Автоматическое обновление
            else:
                self.logger.warning('Cant work because user is not authorized')
                # flow = InstalledAppFlow.from_client_secrets_file(
                #     CREDENTIALS_FILE,
                #     scopes=["https://www.googleapis.com/auth/calendar"]
                # )
                # creds = flow.run_local_server(port=0)
            new_link_content = ScLinkContent(
                creds.to_json(),
                ScLinkContentType.STRING, 
                access_token_link
                )
            set_link_contents(new_link_content)
        return (creds.token if creds else None)
