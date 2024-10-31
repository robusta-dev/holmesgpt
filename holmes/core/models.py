from holmes.core.tool_calling_llm import ToolCallResult
from typing import Optional, List, Dict, Any, Union, Literal
from pydantic import BaseModel, ValidationError, field_validator, ValidationInfo, Json
from enum import Enum


class InvestigationResult(BaseModel):
    analysis: Optional[str] = None
    tool_calls: List[ToolCallResult] = []
    instructions: List[str] = []


class InvestigateRequest(BaseModel):
    source: str  # "prometheus" etc
    title: str
    description: str
    subject: dict
    context: Dict[str, Any]
    source_instance_id: str = "ApiRequest"
    include_tool_calls: bool = False
    include_tool_call_results: bool = False
    prompt_template: str = "builtin://generic_investigation.jinja2"
    # TODO in the future
    # response_handler: ...


class ToolCallConversationResult(BaseModel):
    name: str
    description: str
    output: str


class ConversationInvestigationResponse(BaseModel):
    analysis: Optional[str] = None
    tool_calls: List[ToolCallResult] = []


class ConversationInvestigationResult(BaseModel):
    analysis: Optional[str] = None
    tools: Optional[List[ToolCallConversationResult]] = []


class IssueInvestigationResult(BaseModel):
    """
    :var result: A dictionary containing the summary of the issue investigation.
    :var tools: A list of dictionaries where each dictionary contains information
                about the tool, its name, description and output.

    It is based on the holmes investigation saved to Evidence table.
    """

    result: str
    tools: Optional[List[ToolCallConversationResult]] = []


class HolmesConversationHistory(BaseModel):
    ask: str
    answer: ConversationInvestigationResult


class HolmesConversationIssueContext(BaseModel):
    investigation_result: IssueInvestigationResult
    conversation_history: Optional[List[HolmesConversationHistory]] = []
    issue_type: str
    robusta_issue_id: Optional[str] = None
    source: Optional[str] = None


class ConversationType(str, Enum):
    ISSUE = "issue"
    CHAT = "chat"


class ConversationRequest(BaseModel):
    user_prompt: str
    source: Optional[str] = None
    resource: Optional[dict] = None
    conversation_type: ConversationType
    context: HolmesConversationIssueContext
    include_tool_calls: bool = False
    include_tool_call_results: bool = False


class HolmesConversationIssueContext(BaseModel):
    investigation_result: IssueInvestigationResult
    issue_type: str


class IssueChatRequest(BaseModel):
    ask: str
    investigation_result: IssueInvestigationResult
    issue_type: str
    conversation_history: Optional[list[dict]] = None


class WorkloadHealthRequest(BaseModel):
    ask: str
    resource: dict
    alert_history_since_hours: float = 24
    alert_history: bool = True
    stored_instrucitons: bool = True
    instructions: Optional[List[str]] = []
    include_tool_calls: bool = False
    include_tool_call_results: bool = False
    prompt_template: str = "builtin://kubernetes_workload_ask.jinja2"


class ChatRequest(BaseModel):
    ask: str
    conversation_history: Optional[list[dict]] = None


class ChatResponse(BaseModel):
    analysis: str
    conversation_history: list[dict]
    tool_calls: Optional[List[ToolCallResult]] = []
