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
from datetime import datetime, timedelta, timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_FILE = 'modules/googleCalendarModule/token.json'
CREDENTIALS_FILE = 'modules/googleCalendarModule/credentials.json'
calendar_id = "primary"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s", datefmt="[%d-%b-%y %H:%M:%S]"
)


class DeleteEventAgent(ScAgentClassic):
    def __init__(self):
        super().__init__("action_delete_event")
        
    def on_event(self, event_element: ScAddr, event_edge: ScAddr, action_element: ScAddr) -> ScResult:
        result = self.run(action_element)
        is_successful = result == ScResult.OK
        finish_action_with_status(action_element, is_successful)
        self.logger.info("DeleteEventAgentAgent finished %s",
                         "successfully" if is_successful else "unsuccessfully")
        return result

    def run(self, action_node: ScAddr) -> ScResult:
        self.logger.info("DeleteEventAgent started")

        try:
            creds = self.get_authenticated_creds()
            access_token = creds.token
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
            message_addr = get_action_arguments(action_node, 1)[0]
            message_type = ScKeynodes.resolve(
                "concept_delete_calendar_event_message", sc_type.CONST_NODE_CLASS)

            if not check_connector(sc_type.VAR_PERM_POS_ARC, message_type, message_addr):
                self.logger.info(
                    f"DeleteEventAgent: the message isn’t about adding calendar event")
                return ScResult.OK

            rrel_event_summary = ScKeynodes.resolve("rrel_event_summary", sc_type.CONST_NODE_ROLE)
            self.logger.info('Found dummary rrel')
            if not rrel_event_summary.is_valid():
                self.logger.info("Calendar event necessary parameters weren't found")
                return ScResult.ERROR
            summary_content = self.get_event_summary_content(message_addr, rrel_event_summary)

            event = self.search_event(headers, summary_content)
            if event == ScResult.ERROR:
                self.logger.info("DeleteEventAgent: event hasn't been found in Google Calendar")
                return ScResult.ERROR
            self.logger.info(f"found event: {event['summary']}")
            deletion_response = self.delete_event(headers, event['id'])
            if not deletion_response:
                self.logger.info("DeleteEventAgent: event hasn't been deleted in Google Calendar")
                return ScResult.ERROR
            self.logger.info("Event was deleted")
        except Exception as e:
            self.logger.info(f"DeleteEventAgent: finished with an error {e}")
            return ScResult.ERROR
        summary_addr = search_element_by_role_relation(message_addr, rrel_event_summary)
        generate_action_result(action_node, summary_addr)
        return ScResult.OK

    def get_event_summary_content(self, message_addr: ScAddr, rrel_summary: ScAddr):
        # search link addresses
        summary_addr = search_element_by_role_relation(message_addr, rrel_summary)
        self.logger.info("Found summary link address")

        # search links content
        summary_content = get_link_content_data(summary_addr)
        self.logger.info("All base content was found")
        return str(summary_content)

    def search_event(self, headers, summary):
        params = {
            'q': summary,
            'maxResults': 1,
            'timeMin': datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + 'Z',
            'singleEvents': 'true',
            'orderBy': 'startTime'
        }
        try:
            response = requests.get(
                f'https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events',
                headers=headers,
                params=params
            )
            if response.status_code == 200:
                return response.json().get('items', [])
            else:
                self.logger.info(f"DeleteEventAgent: Search error: {response.status_code} - {response.text}")
                return ScResult.ERROR
        except requests.exceptions.ConnectionError:
            self.logger.info(f"DeleteEventAgent: finished with connection error")
            return ScResult.ERROR

    def delete_event(self, headers, event_id):
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}"

        try:
            response = requests.delete(
                url,
                headers=headers
            )

            if response.status_code == 204:
                return True
            else:
                raise Exception(f"DeleteEventAgent: Delete error: {response.status_code} - {response.text}")
        except requests.exceptions.ConnectionError:
            self.logger.info(f"DeleteEventAgent: finished with connection error")
            return ScResult.ERROR

    def get_authenticated_creds(self):
        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE,
                    scopes=["https://www.googleapis.com/auth/calendar"]
                )
                creds = flow.run_local_server(port=0)

            with open(TOKEN_FILE, "w") as token_file:
                token_file.write(creds.to_json())
        return creds