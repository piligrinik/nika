from sc_kpm import ScModule
from .DeleteEventAgent import DeleteEventAgent


class GoogleCalendarModule(ScModule):
    def __init__(self):
        super().__init__(DeleteEventAgent())
