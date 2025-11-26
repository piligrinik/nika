import ast
import re
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
        # Ищем энтити и тип сообщения
        rrel_1 = ScKeynodes.resolve(
                "rrel_1", sc_type.CONST_NODE_ROLE)
        rrel_2 = ScKeynodes.resolve(
                "rrel_2", sc_type.CONST_NODE_ROLE)
        rrel_entity = ScKeynodes.resolve(
                "rrel_entity", sc_type.CONST_NODE_ROLE)
        nrel_sc_text_translation = ScKeynodes.resolve(
                "nrel_sc_text_translation", sc_type.CONST_NODE_ROLE)
        concept_intent_possible_class = ScKeynodes.resolve(
                "concept_intent_possible_class", sc_type.CONST_NODE_CLASS)
        action_finished = ScKeynodes.resolve(
                "action_finished", sc_type.CONST_NODE_CLASS)
        _message_node= "_message_node"
        _entity_node= "_entity_node"
        _message_type_node= "_message_type_node"
        _question="_question"
        _some_node="_some_node"
        get_message_temp = ScTemplate()
        get_message_temp.quintuple(
            action_node,
            sc_type.VAR_PERM_POS_ARC,
            sc_type.VAR_NODE>>_message_node,
            sc_type.VAR_PERM_POS_ARC,
            rrel_1,
        )
        get_message_temp.quintuple(
            _message_node,
            sc_type.VAR_PERM_POS_ARC,
            _entity_node,
            sc_type.VAR_PERM_POS_ARC,
            rrel_entity,
        )
        get_message_temp.quintuple(
            _some_node,
            sc_type.VAR_COMMON_ARC,
            _message_node,
            sc_type.VAR_PERM_POS_ARC,
            nrel_sc_text_translation,
        )
        get_message_temp.triple(
            _some_node,
            sc_type.VAR_PERM_POS_ARC,
            _question,
        )        
        get_message_temp.triple(
            _message_type_node,
            sc_type.VAR_PERM_POS_ARC,
            _message_node,
        )
        get_message_temp.triple(
            concept_intent_possible_class,
            sc_type.VAR_PERM_POS_ARC,
            _message_type_node,
        )
        search_result_get_message = search_by_template(get_message_temp)[0]
        entity_node=search_result_get_message.get(_entity_node)
        message_type_node=search_result_get_message.get(_message_type_node)
        question=search_result_get_message.get(_question)
        #---------------CHECK-----------------------------------------------
        self.logger.info('CHECK POINT №1')
        self.logger.info(get_element_system_identifier(entity_node))
        self.logger.info(get_element_system_identifier(message_type_node))
        #-------------------------------------------------------------------
        # Ищем джейсончики и всякие темплейтики омлетики
        rrel_entity_template = ScKeynodes.resolve(
                "rrel_entity_template", sc_type.CONST_NODE_ROLE)
        rrel_input_json = ScKeynodes.resolve(
                "rrel_input_json", sc_type.CONST_NODE_ROLE)
        rrel_prompt_json = ScKeynodes.resolve(
                "rrel_prompt_json", sc_type.CONST_NODE_ROLE)
        nrel_llm_template = ScKeynodes.resolve(
                "nrel_llm_template", sc_type.CONST_NODE_NON_ROLE)

        _templates_tuple_node="_templates_tuple_node"
        _entity_template="_entity_template"
        _input_json="_input_json"
        _prompt_json="_prompt_json"
        _tuple_node="_tuple_node"
        get_llm_templates_temp=ScTemplate()
        get_llm_templates_temp.quintuple(
            message_type_node,
            sc_type.VAR_COMMON_ARC,
            sc_type.VAR_NODE_TUPLE>>_tuple_node,
            sc_type.VAR_PERM_POS_ARC,
            nrel_llm_template,
        )

        get_llm_templates_temp.quintuple(
            _tuple_node,
            sc_type.VAR_PERM_POS_ARC,
            _entity_template,
            sc_type.VAR_PERM_POS_ARC,
            rrel_entity_template,
        )

        get_llm_templates_temp.quintuple(
            _tuple_node,
            sc_type.VAR_PERM_POS_ARC,
            _prompt_json,
            sc_type.VAR_PERM_POS_ARC,
            rrel_prompt_json,
        )

        get_llm_templates_temp.quintuple(
            _tuple_node,
            sc_type.VAR_PERM_POS_ARC,
            _input_json,
            sc_type.VAR_PERM_POS_ARC,
            rrel_input_json,
        )
        search_result_get_llm_templates=search_by_template(get_llm_templates_temp)[0]


        input_json_node=search_result_get_llm_templates.get(_input_json)
        entity_template=search_result_get_llm_templates.get(_entity_template)
        prompt_json_node=search_result_get_llm_templates.get(_prompt_json)


        input_json=get_link_content_data(input_json_node)# получаем из узла джейсончик номер раз в виде строки
        input_json_dict=self.str_to_dict(input_json) # преобразуем его в словарь
        prompt_json=get_link_content_data(prompt_json_node) #!!!!!!!!!!!!!!!!!!!!!! ПРОМТОВЫЙ  ДЖЕЙСОН В СТРОКОВОМ ВИДЕ
        #---------------CHECK----------------------------------------------------------
        self.logger.info('CHECK POINT №2')
        self.logger.info(input_json)
        self.logger.info(input_json_dict)
        self.logger.info(type(input_json_dict))
        self.logger.info(prompt_json)
        #-------------------------------------------------------------------------------
        # Ищем все параметры для энтити из темплейта для энтити
        entity=ScKeynodes.resolve(
                "entity", sc_type.CONST_NODE)
        _param="_param"
        _nrel_param="_nrel_param"

        get_params_names_temp=ScTemplate()
        get_params_names_temp.triple(
            entity_template,
            sc_type.VAR_PERM_POS_ARC,
            _param
        )
        get_params_names_temp.triple(
            entity_template,
            sc_type.VAR_PERM_POS_ARC,
            _nrel_param
        )
        get_params_names_temp.quintuple(
            entity,
            sc_type.VAR_COMMON_ARC,
            _param,
            sc_type.VAR_PERM_POS_ARC,
            _nrel_param
        )
        search_result_get_entity_params=search_by_template(get_params_names_temp)
        self.logger.info('EMERGENCY CHECK POINT')
        self.logger.info(len(search_result_get_entity_params))
        params=[]
        nrel_params=[]
        self.logger.info('MORE CHECK POINTS(№3)')
        for result in search_result_get_entity_params:
            params.append(result.get(_param))
            nrel_params.append(result.get(_nrel_param))
            #---------------CHECK----------------------------------------------------------
            self.logger.info('PARAMS')
            self.logger.info(get_element_system_identifier(result.get(_nrel_param)))
            self.logger.info(get_element_system_identifier(result.get(_param)))
            #-------------------------------------------------------------------------------

        input_json_dict['question']=get_link_content_data(question)
        input_json_dict['entity']=get_element_system_identifier(entity_node)

        # Ищем значения в БЗ и подставляем что есть
        for nrel_param in nrel_params:
            get_entity_params_template=ScTemplate()
            _answer="_answer"
            get_entity_params_template.quintuple(
                entity_node,
                sc_type.VAR_COMMON_ARC,
                _answer,
                sc_type.VAR_PERM_POS_ARC,
                nrel_param
            )
            result=search_by_template(get_entity_params_template)
            if result:
                answer=result[0].get(_answer)
                input_json_dict[get_element_system_identifier(nrel_param)]=get_link_content_data(answer)
        self.logger.info('CHECK POINT №4')
        self.logger.info(input_json_dict)
        input_json_str=self.dict_to_str(input_json_dict) # !!!!!!!!!!!!!!!!!!!!ИНПУТОВЫЙ ДЖЕЙСОН УЖЕ В СТРОКОВОМ ВИДЕ
        return 1
    
    def str_to_dict(self,input_str):
        s_quoted_keys = re.sub(r'(\w+):', r'"\1":', input_str)
        d=ast.literal_eval(s_quoted_keys)
        return d

    def dict_to_str(self,input_dict):
        return str(input_dict)

        



        

        
        


    
        


        
       