from sc_kpm import ScAgentClassic, ScResult
from sc_client.models import ScAddr

class DeleteEventAgent(ScAgentClassic):
    def __init__(self):
        super().__init__("action_delete_event")
        
    def on_event(
        self, 
        event_element: ScAddr, 
        event_edge: ScAddr, 
        action_element: ScAddr
        ) -> ScResult:
        ...