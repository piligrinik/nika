import logging
from sc_client.models import ScAddr, ScLinkContentType, ScTemplate
from sc_client.constants import sc_types
from sc_client.client import template_search

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
    create_role_relation
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
        "definition": {
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

llm = init_chat_model("google_genai:gemini-2.5-flash-lite")

model_with_structure = llm.with_structured_output(
    json_about_entity,
    method="json_schema",
)
json_input = {
        "question": "Что такое апельсин?",
        "entity": "апельсин",
        "question_type": "about_entity",
        "nrel_main_idtf": "Апельсин",
        "definition": None,
        "answer": None
        }
# response = model_with_structure.invoke(f"""Please complite provided JSON, don't change the fields that are not None: \n 
        # {json_input}""")

# json_output = json.dumps(response, ensure_ascii=False, indent=2)
# json_output = response
json_output = {
  "question": "Что такое апельсин?",
  "entity": "aпельсин",
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




if __name__ == "__main__":
    print(diff)

