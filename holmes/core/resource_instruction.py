from typing import List

from pydantic import BaseModel


class ResourceInstructionDocument(BaseModel):
    """Represents context necessary for an investigation in the form of a URL
    It is expected that Holmes will use that URL to fetch additional context about an error.
    This URL can for example be the location of a runbook
    """

    url: str


class ResourceInstructions(BaseModel):
    instructions: List[str] = []
    documents: List[ResourceInstructionDocument] = []
