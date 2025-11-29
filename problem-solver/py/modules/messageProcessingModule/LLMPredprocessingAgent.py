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
    generate_non_role_relation,
    generate_node,
    generate_links
)
from sc_kpm.utils.action_utils import (
     generate_action_result,
    finish_action_with_status,
    get_action_arguments,
)

from sc_kpm import ScKeynodes

from dotenv import load_dotenv
import os
import json

from langchain.chat_models import init_chat_model


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
        return ScResult.OK


    def run(self, action_node: ScAddr) -> ScResult:
        try:
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
            message_node = search_result_get_message.get(_message_node)
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
                sc_type.VAR_NODE_STRUCTURE >> _entity_template,
                sc_type.VAR_PERM_POS_ARC,
                rrel_entity_template,
            )

            get_llm_templates_temp.quintuple(
                _tuple_node,
                sc_type.VAR_PERM_POS_ARC,
                sc_type.VAR_NODE_LINK >> _prompt_json,
                sc_type.VAR_PERM_POS_ARC,
                rrel_prompt_json,
            )

            get_llm_templates_temp.quintuple(
                _tuple_node,
                sc_type.VAR_PERM_POS_ARC,
                sc_type.VAR_NODE_LINK >>  _input_json,
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
            prompt_json = prompt_json.replace("(", "[")
            prompt_json = prompt_json.replace(")", "]")
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
            #---------------CHECK----------------------------------------------------------
            # отдаем джейсончики в модель
            self.logger.info('CHECK POINT №5')
            output_json_dict = self.get_llm_answer(json_template=prompt_json, json_input=input_json_str)
            self.logger(f"Output from LLM: {output_json_dict}")
            # находим новые значения параметров
            diff_params = self.find_new_params(input_json_dict, output_json_dict)
            
            #---------------CHECK----------------------------------------------------------
            # добавляем новые значения параметров в БЗ
            self.logger.info('CHECK POINT №6')
            self.add_new_params_to_kb(diff_params, entity_node)
            
            #---------------CHECK----------------------------------------------------------
            # достаем ответ
            self.logger.info('CHECK POINT №6')
            answer_txt = output_json_dict["answer"]
            # формируем reply_message и присоединяем все к исходной структуре 
            reply_node = self.add_answer_to_result(message_node, answer_txt)
            generate_action_result(action_node, reply_node)
            return ScResult.OK
        except Exception as e:
            self.logger.exception(f"LLMPredprocessingAgent: finished with an error: {e}")
            return ScResult.ERROR
    
    def str_to_dict(self,input_str):
        s_quoted_keys = re.sub(r'(\w+):', r'"\1":', input_str)
        d=ast.literal_eval(s_quoted_keys)
        return d

    def dict_to_str(self,input_dict):
        return str(input_dict)
    
    def get_llm_answer(self, json_template: dict, json_input: dict) -> dict: 
        ''' Получение ответа от LLM с типом dict
            - json_template: prompt_json для объевления модели, какой формат json нужно отдать
            - json_input: входной json, который нужно дозаполнить модели'''

        llm = init_chat_model("google_genai:gemini-2.5-flash-lite")
        # объявление модели, что нужно вернуть json в prompt_json формате
        model_with_structure = llm.with_structured_output(
            json_template,
            method="json_schema",
        )
        # ответ json -> dict
        response = json.loads(model_with_structure.invoke(f"""Please complite provided JSON, don't change the fields that are not None: \n 
                 {json_input}"""))
        return response
    
    def find_new_params(self, json_input: dict, json_output: dict) -> dict:
        '''Получение новых параметров путем сравнение input и output json'''
        diff = {}
        if json_output.keys() == json_input.keys():
            for v1, v2 in zip(sorted(json_input.items()), sorted(json_output.items())):
                if v1 != v2:
                    self.logger.debug(f"Different field: {v1} and {v2}")
                    diff[v1[0]] = v2[1]
        return diff
    
    def add_new_params_to_kb(self, new_params: dict, entity_node: ScAddr):
        new_links = generate_links(new_params.values(), ScLinkContentType.STRING, sc_type.CONST_NODE_LINK)
        for link, key in zip(new_links, new_params.keys()):
            nrel = generate_non_role_relation(entity_node, link, generate_node(sc_type.CONST_NODE_NON_ROLE, key))
        self.logger.info(f"New params are linked to an entity")

    def add_answer_to_result(self, message_addr: ScAddr, answer_text: str):
        # generate answer text link
        answer_link = generate_link(answer_text, ScLinkContentType.STRING, sc_type.CONST_NODE_LINK)
        answer_link_node = generate_node(sc_type.NODE)
        # resolve or create all necessary nodes 
        nrel_reply_node = ScKeynodes.resolve("nrel_reply", sc_type.CONST_NODE_NON_ROLE)
        text_translation_node = ScKeynodes.resolve("nrel_sc_text_translation", sc_type.CONST_NODE_NON_ROLE)
        reply_message_node = ScKeynodes.resolve("reply_message", sc_type.NODE)
        
        answer_template = ScTemplate()
        answer_template.triple(
            sc_type.VAR_NODE >> "_link_node",
            sc_type.VAR_TEMP_POS_ARC,
            sc_type.VAR_NODE_LINK >> "_link"

        )
        answer_template.quintuple(
            "_link_node",
            sc_type.VAR_COMMON_ARC,
            sc_type.VAR_NODE >> "_reply_node",
            sc_type.VAR_PERM_POS_ARC,
            sc_type.VAR_NODE_NON_ROLE >> "_nrel_sc_text_translation"
        )
        answer_template.quintuple(
            message_addr,
            sc_type.VAR_COMMON_ARC,
            "_reply_node",
            sc_type.VAR_TEMP_POS_ARC,
            sc_type.VAR_NODE_NON_ROLE >> "_nrel_reply"
        )
        
        params = {"_link": answer_link,
                  "_link_node": answer_link_node,
                  "_reply_node": reply_message_node,
                  "_nrel_reply": nrel_reply_node,
                  "_nrel_sc_text_translation": text_translation_node}
        results = generate_by_template(answer_template, params)
        self.logger.info(f"Result message is formed: {results}")
        return reply_message_node
    
    
    


        



        

        
        


    
        


        
       
