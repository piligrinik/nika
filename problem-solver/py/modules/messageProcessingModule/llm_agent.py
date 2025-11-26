import logging
from sc_client.models import ScAddr, ScLinkContentType, ScTemplate
from sc_client.constants import sc_type
from sc_client.client import search_by_template, generate_by_template

from sc_kpm.identifiers import CommonIdentifiers

from sc_kpm import ScAgentClassic, ScModule, ScResult, ScServer
from sc_kpm.sc_sets import ScSet
from sc_kpm.utils import (
    generate_link,
    generate_links,
    generate_non_role_relation,
    generate_node
)
from sc_kpm.utils.action_utils import (
    generate_action_result,
    finish_action_with_status,
    get_action_arguments
    
)
from sc_kpm import ScKeynodes

from dotenv import load_dotenv
import os
import json

from pydantic import BaseModel, Field
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model


load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")
os.environ["GOOGLE_API_KEY"] = gemini_api_key

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s", datefmt="[%d-%b-%y %H:%M:%S]"
)


# TODO: add_to_kb method


class LLMAgent(ScAgentClassic):
    def __init__(self):
        super().__init__("action_get_llm_answer")

    def on_event(self, event_element: ScAddr, event_edge: ScAddr, action_element: ScAddr) -> ScResult:
        result = self.run(action_element)
        is_successful = result == ScResult.OK
        finish_action_with_status(action_element, is_successful)
        self.logger.info("LLMAgent finished %s",
                         "successfully" if is_successful else "unsuccessfully")
        return result
    
    def run(self, action_node: ScAddr) -> ScResult:
        self.logger.info("LLMAgent started")
        try:
            message_addr = get_action_arguments(action_node, 1)[0]
            
            # message_type = ScKeynodes.resolve(
            #     "concept_message_about_weather", sc_types.NODE_CONST_CLASS)

            # if not check_edge(sc_types.EDGE_ACCESS_VAR_POS_PERM, message_type, message_addr):
            #     self.logger.info(
            #         f"WeatherAgent: the message isn’t about weather")
            #     return ScResult.OK

            entity_node = ScAddr(0) # TODO: take Alice's code here (search for entity address)
            # at this point i will have addresses: entity

            json_input = {
                "question": "Что такое апельсин?",
                "entity": "orange",
                "question_type": "about_entity",
                "nrel_main_idtf": "Апельсин",
                "definition": None,
                "answer": None
                }
            llm_template = ScAddr(0)
            
            rrel_prompt_json = ScKeynodes.resolve("rrel_prompt_json", None)
            self.logger.debug(f"rrel_prompt_json valid: {rrel_prompt_json.is_valid()}")
            llm_template_args = ScTemplate()
            llm_template_args.triple(
                llm_template,
                sc_type.VAR_TEMP_POS_ARC,
                sc_type.VAR_NODE_TUPLE >> "_param_tuple"
            )
            llm_template_args.quintuple(
                "_param_tuple",
                sc_type.VAR_TEMP_POS_ARC,
                sc_type.VAR_NODE_LINK >> "_json_template",
                sc_type.VAR_TEMP_POS_ARC,
                rrel_prompt_json
            )
            llm_templ_result = search_by_template(llm_template_args)
            json_template = llm_templ_result.get("_json_template")
            self.logger.debug(f"Json template found: {json_template.is_valid()}")        

            json_output = self.get_llm_answer(json_template=json_template, json_input=json_input)
            diff_params = self.find_new_params(json_input, json_output)
            self.add_new_params_to_kb(diff_params, entity_node)
            answer_txt = json_output["answer"]
            reply_node = self.add_answer_to_result(message_addr, answer_txt)
            generate_action_result(action_node, reply_node)
            ScResult.OK
        except Exception as e:
            self.logger.info(f"LLMAgent: finished with an error: {e}")
            return ScResult.ERROR
        
    def get_llm_answer(self, json_template: dict, json_input: dict): 

# TODO: работа с json!!!

        llm = init_chat_model("google_genai:gemini-2.5-flash-lite")

        model_with_structure = llm.with_structured_output(
            json_template,
            method="json_schema",
        )
        
        response = json.loads(model_with_structure.invoke(f"""Please complite provided JSON, don't change the fields that are not None: \n 
                 {json_input}"""))
        return response
    
    def find_new_params(self, json_input: dict, json_output: dict):
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
        # generate answer link
        answer_link = generate_link(answer_text, ScLinkContentType.STRING, sc_type.CONST_NODE_LINK)
        answer_link_node = generate_node(sc_type.NODE)
        # resolve or create all necessary nodes 
        nrel_reply_node = ScKeynodes.resolve("nrel_reply", None)
        text_translation_node = ScKeynodes.resolve("nrel_sc_text_translation", None)
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

        

if __name__ == "__main__":
    ...

