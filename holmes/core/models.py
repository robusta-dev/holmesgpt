from holmes.core.investigation_structured_output import InputSectionsDataType
from holmes.core.tool_calling_llm import ToolCallResult
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, model_validator, Field
from enum import Enum


class InvestigationResult(BaseModel):
    analysis: Optional[str] = None
    sections: Optional[Dict[str, Union[str, None]]] = None
    tool_calls: List[ToolCallResult] = []
    instructions: List[str] = []
    metadata: Optional[Dict[Any, Any]] = None


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
    sections: Optional[InputSectionsDataType] = None
    model: Optional[str] = None
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


# HolmesConversationIssueContext, ConversationType and ConversationRequest classes will be deprecated later
class HolmesConversationIssueContext(BaseModel):
    investigation_result: IssueInvestigationResult
    conversation_history: Optional[List[HolmesConversationHistory]] = []
    issue_type: str
    robusta_issue_id: Optional[str] = None
    source: Optional[str] = None


class ConversationType(str, Enum):
    ISSUE = "issue"


class ConversationRequest(BaseModel):
    user_prompt: str
    source: Optional[str] = None
    resource: Optional[dict] = None
    # ConversationType.ISSUE is default as we gonna deprecate this class and won't add new conversation types
    conversation_type: Optional[ConversationType] = ConversationType.ISSUE
    context: HolmesConversationIssueContext
    include_tool_calls: bool = False
    include_tool_call_results: bool = False


class ChatRequestBaseModel(BaseModel):
    conversation_history: Optional[list[dict]] = None
    model: Optional[str] = None
    stream: bool = Field(default=False)

    # In our setup with litellm, the first message in conversation_history
    # should follow the structure [{"role": "system", "content": ...}],
    # where the "role" field is expected to be "system".
    @model_validator(mode="before")
    def check_first_item_role(cls, values):
        conversation_history = values.get("conversation_history")
        if (
            conversation_history
            and isinstance(conversation_history, list)
            and len(conversation_history) > 0
        ):
            first_item = conversation_history[0]
            if not first_item.get("role") == "system":
                raise ValueError(
                    "The first item in conversation_history must contain 'role': 'system'"
                )
        return values


class IssueChatRequest(ChatRequestBaseModel):
    ask: str
    investigation_result: IssueInvestigationResult
    issue_type: str


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
    model: Optional[str] = None


class ChatRequest(ChatRequestBaseModel):
    ask: str


class FollowUpAction(BaseModel):
    id: str
    action_label: str
    pre_action_notification_text: str
    prompt: str


class ChatResponse(BaseModel):
    analysis: str
    conversation_history: list[dict]
    tool_calls: Optional[List[ToolCallResult]] = []
    follow_up_actions: Optional[List[FollowUpAction]] = []
    metadata: Optional[Dict[Any, Any]] = None


class WorkloadHealthInvestigationResult(BaseModel):
    analysis: Optional[str] = None
    tools: Optional[List[ToolCallConversationResult]] = []

    @model_validator(mode="before")
    def check_analysis_and_result(cls, values):
        if "result" in values and "analysis" not in values:
            values["analysis"] = values["result"]
            del values["result"]
        return values


class WorkloadHealthChatRequest(ChatRequestBaseModel):
    ask: str
    workload_health_result: WorkloadHealthInvestigationResult
    resource: dict


workload_health_structured_output = {
    "type": "json_schema",
    "json_schema": {
        "name": "WorkloadHealthResult",
        "strict": False,
        "schema": {
            "type": "object",
            "properties": {
                "workload_healthy": {
                    "type": "boolean",
                    "description": "is the workload in healthy state or in error state",
                },
                "root_cause_summary": {
                    "type": "string",
                    "description": "concise short explaination leading to the workload_healthy result, pinpoint reason and root cause for the workload issues if any.",
                },
            },
            "required": ["root_cause_summary", "workload_healthy"],
            "additionalProperties": False,
        },
    },
}
