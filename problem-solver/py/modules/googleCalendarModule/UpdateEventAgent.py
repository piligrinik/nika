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


class UpdateEventAgent(ScAgentClassic):
    def __init__(self):
        super().__init__("action_update_calendar_event")

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
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            message_addr = get_action_arguments(action_node, 1)[0]
            message_type = ScKeynodes.resolve(
                "concept_update_calendar_event_message", sc_type.CONST_NODE_CLASS)

            if not check_connector(sc_type.VAR_PERM_POS_ARC, message_type, message_addr):
                self.logger.info(
                    f"The message isn’t about updating calendar event")
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

            # check other parameters
            rrel_new_event_summary = ScKeynodes.resolve("rrel_new_event_summary", sc_type.CONST_NODE_ROLE)
            new_summary_link = search_element_by_role_relation(message_addr, rrel_new_event_summary)
            if new_summary_link:
                new_summary_content = get_link_content_data(new_summary_link)
                update_response = self.update_event(headers, event['id'], new_summary=new_summary_content)
            rrel_start_time = ScKeynodes.resolve("rrel_start_time", sc_type.CONST_NODE_ROLE)
            start_time_link = search_element_by_role_relation(message_addr, rrel_start_time)
            rrel_end_time = ScKeynodes.resolve("rrel_end_time", sc_type.CONST_NODE_ROLE)
            end_time_link = search_element_by_role_relation(message_addr, rrel_end_time)
            if start_time_link and end_time_link:
                start_time_content = get_link_content_data(start_time_link)
                end_time_content = get_link_content_data(end_time_link)
                update_response = self.update_event(headers, event['id'],
                                                    new_start_time=start_time_content,
                                                    new_end_time=end_time_content)
            elif start_time_link:
                start_time_content = get_link_content_data(start_time_link)
                update_response = self.update_event(headers, event['id'],
                                                    new_start_time=start_time_content)
            elif end_time_link:
                end_time_content = get_link_content_data(end_time_link)
                update_response = self.update_event(headers, event['id'],
                                                    new_end_time=end_time_content)
            else:
                self.logger.info("Necessary parameters weren't found for an update")
                update_response = False
            if not update_response:
                self.logger.info("Event wasn't updated in Google Calendar")
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
            self.logger.info(f"finished with connection error")
            return ScResult.ERROR

    def update_event(self, headers, event_id,
                     new_summary=None,
                     new_start_time=None,
                     new_end_time=None):
        try:
            url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}"
            if new_summary:
                update_data = {
                    "summary": new_summary
                }
            elif new_start_time:
                if new_end_time:
                    update_data = {
                        "start": {
                            "dateTime": new_start_time,
                            "timeZone": "Europe/Moscow"
                        },
                        "end": {
                            "dateTime": new_end_time,
                            "timeZone": "Europe/Moscow"
                        }
                    }
                else:
                    update_data = {
                        "start": {
                            "dateTime": new_start_time,
                            "timeZone": "Europe/Moscow"
                        }
                    }
            elif new_end_time and not new_start_time:
                update_data = {
                    "end": {
                            "dateTime": new_end_time,
                            "timeZone": "Europe/Moscow"
                        }
                }
            else:
                return False

            response = requests.patch(
                url,
                headers=headers,
                json=update_data
            )

            if response.status_code == 200:
                updated_event = response.json()
                self.logger.info(f"Event was successfully updated: {updated_event=}")
                return True
            else:
                self.logger.info(f"Search error: {response.status_code} - {response.text}")
                return False
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