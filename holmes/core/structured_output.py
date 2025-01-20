
from typing import List
from pydantic import BaseModel

from holmes.core.tool_calling_llm import LLMResult

class StructuredSection(BaseModel):
    text: str
    contains_meaningful_information: bool
    contains_hallucination: bool

class StructuredResponse(LLMResult):
    sections: List[StructuredSection]

PROMPT = "Your job as a LLM is to take the unstructured output from another LLM and structure it in the following sections. Return a JSON where the key is the section title."

EXPECTED_SECTIONS = [
    {
        "title": "Investigation",
        "prompt": "Extract the investigation"
    }
]

def generate_structured_output(llm_result:LLMResult) -> StructuredResponse:

    return StructuredResponse(
        **llm_result.model_dump(),
        sections=[],
    )
