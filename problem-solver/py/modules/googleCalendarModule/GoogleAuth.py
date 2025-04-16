import os.path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

class GoogleClient:
    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    FILE_PATH = 'credentials.json'

    def __init__(self):
        self._credentials = None
        if os.path.exists("token.json"):
            self._credentials = Credentials.from_authorized_user_file("token.json", self.SCOPES)
        if not self._credentials or not self._credentials.valid:
            if self._credentials and self._credentials.expired and self._credentials.refresh_token:
                self._credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", self.SCOPES
                )
                self._credentials = flow.run_local_server(port=0)
            with open("token.json", "w") as token:
                token.write(self._credentials.to_json())

    @property
    def credentials(self):
        return self._credentials

