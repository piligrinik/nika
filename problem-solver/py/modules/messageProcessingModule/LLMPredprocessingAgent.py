
import logging
from sc_client.models import ScAddr, ScLinkContentType, ScTemplate
from sc_client.constants import sc_type
from sc_client.client import search_by_template,generate_by_template

from sc_kpm import ScAgentClassic, ScResult
from sc_kpm.sc_sets import ScSet
from sc_kpm.utils import (
    generate_link,
    get_link_content_data,
    check_connector, generate_connector,
    erase_connectors,
    search_element_by_role_relation,
    search_element_by_non_role_relation,
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


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s", datefmt="[%d-%b-%y %H:%M:%S]"
)

class LLMPredprocessingAgent(ScAgentClassic):
    def __init__(self):
        super().__init__("action_llm_predprocessing")

    
    def on_event(self, event_element: ScAddr, event_edge: ScAddr, action_element: ScAddr) -> ScResult:
        result = self.run(action_element)
        is_successful = result == ScResult.OK
        finish_action_with_status(action_element, is_successful)
        self.logger.info("LLMPredprocessingAgent finished %s",
                         "successfully" if is_successful else "unsuccessfully")
        return result


    def run(self, action_node: ScAddr) -> ScResult:
        self.logger.info("LLMPredprocessingAgent started")
        rrel_1 = ScKeynodes.resolve(
                "rrel_1", sc_type.CONST_NODE_ROLE)
        rrel_2 = ScKeynodes.resolve(
                "rrel_2", sc_type.CONST_NODE_ROLE)
        rrel_entity = ScKeynodes.resolve(
                "rrel_entity", sc_type.CONST_NODE_ROLE)
        concept_intent_possible_class = ScKeynodes.resolve(
                "concept_intent_possible_class", sc_type.CONST_NODE)
        self.logger.info("Nodes resolved")
        message_template = ScTemplate()
        _message_node= "_message_node"
        _entity_node= "_entity_node"
        _message_type_node= "_message_type_node"
        message_template.quintuple(
            action_node,
            sc_type.VAR_PERM_POS_ARC,
            sc_type.VAR_NODE>>_message_node,
            sc_type.VAR_PERM_POS_ARC,
            rrel_1,
        )
        message_template.quintuple(
            _message_node,
            sc_type.VAR_PERM_POS_ARC,
            sc_type.VAR_NODE>>_entity_node,
            sc_type.VAR_PERM_POS_ARC,
            rrel_entity,
        )
        message_template.triple(
            _message_type_node,
            sc_type.VAR_PERM_POS_ARC,
            _message_node,
        )
        message_template.triple(
            concept_intent_possible_class,
            sc_type.VAR_PERM_POS_ARC,
            _message_type_node,
        )
        search_result_message_templ = search_by_template(message_template)[0]
        entity_node=search_result_message_templ.get(_entity_node)
        message_type_node=search_result_message_templ.get(_message_type_node)
        self.logger.info("First search done")
        self.logger.info(f"ENTITY {get_element_system_identifier(entity_node)}")
        self.logger.info(f"MESSAGE TYPE {get_element_system_identifier(message_type_node)}")

        _llm_template= "_llm_template"
        nrel_llm_template = ScKeynodes.resolve(
                "nrel_llm_template", sc_type.CONST_NODE_NON_ROLE)
        llm_temp_template=ScTemplate()
        llm_temp_template.quintuple(
            message_type_node,
            sc_type.VAR_COMMON_ARC,
            _llm_template,
            sc_type.VAR_PERM_POS_ARC,
            nrel_llm_template,
        )
        search_result_llm_temp=search_by_template(llm_temp_template)[0]
        self.logger.info("Second search done")

        llm_template=search_result_llm_temp.get(_llm_template)
        resultTemplate=ScTemplate()
        resultTemplate.quintuple(
            action_node,
            sc_type.VAR_PERM_POS_ARC,
            llm_template,
            sc_type.VAR_PERM_POS_ARC,
            rrel_2,
        )
        gen_result = generate_by_template(resultTemplate)
        self.logger.info("Generation done")


        
       