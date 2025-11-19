import logging
from sc_client.models import ScAddr, ScLinkContentType, ScTemplate
from sc_client.constants import sc_type
from sc_client.client import search_by_template, generate_by_template

from sc_kpm.identifiers import CommonIdentifiers

from sc_kpm import ScAgentClassic, ScModule, ScResult, ScServer
from sc_kpm.sc_sets import ScSet
from sc_kpm.utils import (
    create_link,
    get_link_content_data,
    check_edge, create_edge,
    delete_edges,
    get_element_by_role_relation,
    get_element_by_norole_relation,
    get_system_idtf,
    get_edge,
    generate_link,
    generate_links,
    generate_non_role_relation,
    generate_node
)
from sc_kpm.utils.action_utils import (
    generate_action_result,
    finish_action_with_status,
    get_action_arguments,
    search_element_by_role_relation,
    
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
        self.logger.info("WeatherAgent finished %s",
                         "successfully" if is_successful else "unsuccessfully")
        return result
    
    def run(self, action_node: ScAddr) -> ScResult:
        self.logger.info("WeatherAgent started")
        try:
            message_addr = get_action_arguments(action_node, 1)[0]
            
            # message_type = ScKeynodes.resolve(
            #     "concept_message_about_weather", sc_types.NODE_CONST_CLASS)

            # if not check_edge(sc_types.EDGE_ACCESS_VAR_POS_PERM, message_type, message_addr):
            #     self.logger.info(
            #         f"WeatherAgent: the message isn’t about weather")
            #     return ScResult.OK

            rrel_entity = ScKeynodes.resolve("rrel_entity", sc_type.NODE_ROLE)
            entity_addr = ScAddr(0) # TODO: take Alice's code here (search for entity address)
            # at this point i will have addresses: entity

            json_input = {
                "question": "Что такое апельсин?",
                "entity": "orange",
                "question_type": "about_entity",
                "nrel_main_idtf": "Апельсин",
                "definition": None,
                "answer": None
                }
            json_about_entity = {
                "title": "Question about an entity",
                "description": "A question about an entity, its name, definition and the answer in human format.",
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question about the definition of the entity, will always be mentioned in human question."
                    },
                    "entity": {
                        "type": "string",
                        "description": "Entity that the question is about."
                    },
                    "question_type": {
                        "type": "string",
                        "description": "Type of the question. Ex: about_entity, about_weather."
                    },
                    "nrel_main_idtf": {
                        "type": "string",
                        "description": "Identifier of the entity in the initial form (with a capital letter)."
                    },
                    "nrel_def": {
                        "type": "string",
                        "description": "A definition of the entity without mentioning the entity itself."
                    },
                    "answer": {
                        "type": "string",
                        "description": "An answer to human question in a natural language."
                    }
                },
                "required": ["question", "entity", "nrel_main_idtf", "definition", "answer"]
            }
            json_output = self.get_llm_answer(json_template=json_about_entity, json_input=json_input)
            diff_params = self.find_new_params(json_input, json_output)
        except:
            self.logger.info(f"LLMAgent: finished with an error")
            return ScResult.ERROR
        
    def get_llm_answer(self, json_template: dict, json_input: dict):
# TODO: add parameters 
# TODO: adopt dynamic json
# TODO: llm_json_template_to_kb

        llm = init_chat_model("google_genai:gemini-2.5-flash-lite")

        model_with_structure = llm.with_structured_output(
            json_template,
            method="json_schema",
        )
        
        response = model_with_structure.invoke(f"""Please complite provided JSON, don't change the fields that are not None: \n 
                # {json_input}""")
        return response
    
    def find_new_params(self, json_input: dict, json_output: dict):
        # json_output = json.dumps(response, ensure_ascii=False, indent=2)
        # json_output = response
        json_output = {
        "question": "Что такое апельсин?",
        "entity": "orange",
        "nrel_main_idtf": "Апельсин",
        "definition": "Плод апельсинового дерева.",
        "answer": "Апельсин — это плод апельсинового дерева.",
        "question_type": "about_entity"
        }
        diff = {}
        if json_output.keys() == json_input.keys():
            for v1, v2 in zip(sorted(json_input.items()), sorted(json_output.items())):
                if v1 != v2:
                    print(f"Different field: {v1} and {v2}")
                    diff[v1[0]] = v2[1]
        return diff
    
    def add_new_params_to_kb(self, new_params: dict, entity_addr: ScAddr):

        new_links = generate_links(new_params.values())
        for link, key in zip(new_links, new_params.keys()):
            nrel = generate_non_role_relation(entity_addr, link, generate_node(sc_type.CONST_NODE_NON_ROLE, key))

    def add_answer_to_result(self, message_addr: ScAddr, answer_text: str):
        # generate answer link
        answer_link = generate_link(answer_text, ScLinkContentType.STRING, sc_type.CONST_NODE_LINK)
        answer_link_node = generate_node(sc_type.NODE)
        # resolve or create all necessary nodes 
        nrel_reply_node = ScKeynodes.resolve("nrel_reply", None)
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
        search_results = generate_by_template(answer_template, params)
        



        

if __name__ == "__main__":
    ...

