from sc_kpm import ScModule
from .AddEventAgent import AddEventAgent


class GoogleCalendarModule(ScModule):
    def __init__(self):
        super().__init__(AddEventAgent())
