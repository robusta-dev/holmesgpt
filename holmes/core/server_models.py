from typing import Union, List

from pydantic import BaseModel


class InvestigateContext(BaseModel):
    type: str
    value: Union[str, dict]


class InvestigateRequest(BaseModel):
    source: str  # "prometheus" etc
    title: str
    description: str
    subject: dict
    context: List[InvestigateContext]
    source_instance_id: str
    model: str = "gpt-4o"
    system_prompt: str = "builtin://generic_investigation.jinja2"
    # TODO in the future
    # response_handler: ...
