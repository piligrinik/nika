from sc_kpm import ScModule
from .AddEventAgent import AddEventAgent
from .googleAuthAgent import GoogleAuthAgent
from .DeleteEventAgent import DeleteEventAgent

class GoogleCalendarModule(ScModule):
    def __init__(self):
        super().__init__(
            AddEventAgent(),
            GoogleAuthAgent(),
            DeleteEventAgent()
            )
