import json
import logging
from sc_client.models import ScAddr
from sc_client.constants import sc_type
from sc_kpm.identifiers import CommonIdentifiers
from sc_kpm.sc_sets import ScStructure

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
    execute_agent,
    get_action_result,
)
from sc_kpm import ScKeynodes

import requests
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials

calendar_id = "primary"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s", datefmt="[%d-%b-%y %H:%M:%S]"
)


class DeleteEventAgent(ScAgentClassic):
    def __init__(self):
        super().__init__("action_delete_calendar_event")
        
    def on_event(self, event_element: ScAddr, event_edge: ScAddr, action_element: ScAddr) -> ScResult:
        result = self.run(action_element)
        is_successful = result == ScResult.OK
        finish_action_with_status(action_element, is_successful)
        self.logger.info("Finished %s",
                         "successfully" if is_successful else "unsuccessfully")
        return result

    def run(self, action_node: ScAddr) -> ScResult:
        self.logger.info("Started")

        try:
            access_token = self.get_authenticated_token()
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
            message_addr = get_action_arguments(action_node, 1)[0]
            message_type = ScKeynodes.resolve(
                "concept_delete_calendar_event_message", sc_type.CONST_NODE_CLASS)

            if not check_connector(sc_type.VAR_PERM_POS_ARC, message_type, message_addr):
                self.logger.info(
                    f"The message isn’t about deleting calendar event")
                return ScResult.OK

            rrel_event_summary = ScKeynodes.resolve("rrel_event_summary", sc_type.CONST_NODE_ROLE)
            self.logger.info('Found summary rrel')
            if not rrel_event_summary.is_valid():
                self.logger.info("Calendar event necessary parameters weren't found")
                return ScResult.ERROR
            summary_content = self.get_event_summary_content(message_addr, rrel_event_summary)

            event = self.search_event(headers, summary_content)
            if event == ScResult.ERROR:
                self.logger.info("Event hasn't been found in Google Calendar")
                return ScResult.ERROR
            self.logger.info(f"Found event: {event['summary']}")
            deletion_response = self.delete_event(headers, event['id'])
            if not deletion_response:
                self.logger.info("Event hasn't been deleted in Google Calendar")
                return ScResult.ERROR
            self.logger.info("Event was deleted")
        except Exception as e:
            self.logger.info(f"Finished with an error {e}")
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
                return response.json()['items'][0]
            else:
                self.logger.info(f"Search error: {response.status_code} - {response.text}")
                return ScResult.ERROR
        except requests.exceptions.ConnectionError:
            self.logger.info(f"Finished with connection error")
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
                raise Exception(f"Deletion error: {response.status_code} - {response.text}")
        except requests.exceptions.ConnectionError:
            self.logger.info(f"Finished with connection error")
            return ScResult.ERROR

    def get_authenticated_token(self) -> str | None:
            action_class_name = "action_google_auth"
            current_user_node = ScKeynodes.resolve("current_user", sc_type.CONST_NODE)
            action, is_successful = execute_agent(
                arguments={
                    current_user_node: False
                },
                concepts=[CommonIdentifiers.ACTION, action_class_name],
            )
            if is_successful:
                result_struct = get_action_result(action)
                token_link = ScStructure(set_node=result_struct).elements_set.pop()
                token = get_link_content_data(token_link)
                creds_dict = json.loads(token)
                creds = Credentials.from_authorized_user_info(creds_dict)
                return creds.token
            else:
                return None