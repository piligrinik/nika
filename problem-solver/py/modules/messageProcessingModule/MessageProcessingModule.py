from sc_kpm import ScModule
from .WeatherAgent import WeatherAgent
from .LLMPredprocessingAgent import LLMPredprocessingAgent

class MessageProcessingModule(ScModule):
    def __init__(self):
        super().__init__(WeatherAgent(), LLMPredprocessingAgent())