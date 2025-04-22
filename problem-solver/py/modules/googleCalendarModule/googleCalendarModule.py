from sc_kpm import ScModule
from .AddEventAgent import AddEventAgent
from .googleAuthAgent import GoogleAuthAgent
from .DeleteEventAgent import DeleteEventAgent
from .UpdateEventAgent import UpdateEventAgent

class GoogleCalendarModule(ScModule):
    def __init__(self):
        super().__init__(
            AddEventAgent(),
            GoogleAuthAgent(),
            DeleteEventAgent(),
            UpdateEventAgent()
            )
