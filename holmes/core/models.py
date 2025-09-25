import json
from holmes.core.investigation_structured_output import InputSectionsDataType
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, model_validator, Field
from enum import Enum

from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus


class TruncationMetadata(BaseModel):
    tool_call_id: str
    start_index: int
    end_index: int
    tool_name: str
    original_token_count: int


class TruncationResult(BaseModel):
    truncated_messages: list[dict]
    truncations: list[TruncationMetadata]


class ToolCallResult(BaseModel):
    tool_call_id: str
    tool_name: str
    description: str
    result: StructuredToolResult
    size: Optional[int] = None

    def as_tool_call_message(self):
        content = format_tool_result_data(self.result)
        if self.result.params:
            content = (
                f"Params used for the tool call: {json.dumps(self.result.params)}. The tool call output follows on the next line.\n"
                + content
            )
        return {
            "tool_call_id": self.tool_call_id,
            "role": "tool",
            "name": self.tool_name,
            "content": content,
        }

    def as_tool_result_response(self):
        result_dump = self.result.model_dump()
        result_dump["data"] = self.result.get_stringified_data()

        return {
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "description": self.description,
            "role": "tool",
            "result": result_dump,
        }

    def as_streaming_tool_result_response(self):
        result_dump = self.result.model_dump()
        result_dump["data"] = self.result.get_stringified_data()

        return {
            "tool_call_id": self.tool_call_id,
            "role": "tool",
            "description": self.description,
            "name": self.tool_name,
            "result": result_dump,
        }


def format_tool_result_data(tool_result: StructuredToolResult) -> str:
    tool_response = tool_result.data
    if isinstance(tool_result.data, str):
        tool_response = tool_result.data
    else:
        try:
            if isinstance(tool_result.data, BaseModel):
                tool_response = tool_result.data.model_dump_json(indent=2)
            else:
                tool_response = json.dumps(tool_result.data, indent=2)
        except Exception:
            tool_response = str(tool_result.data)
    if tool_result.status == StructuredToolResultStatus.ERROR:
        tool_response = f"{tool_result.error or 'Tool execution failed'}:\n\n{tool_result.data or ''}".strip()
    return tool_response


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


class PendingToolApproval(BaseModel):
    """Represents a tool call that requires user approval."""

    tool_call_id: str
    tool_name: str
    description: str
    params: Dict[str, Any]


class ToolApprovalDecision(BaseModel):
    """Represents a user's decision on a tool approval."""

    tool_call_id: str
    approved: bool


class ChatRequestBaseModel(BaseModel):
    conversation_history: Optional[list[dict]] = None
    model: Optional[str] = None
    stream: bool = Field(default=False)
    enable_tool_approval: Optional[bool] = (
        False  # Optional boolean for backwards compatibility
    )
    tool_decisions: Optional[List[ToolApprovalDecision]] = None

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
    pending_approvals: Optional[List[PendingToolApproval]] = None
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
