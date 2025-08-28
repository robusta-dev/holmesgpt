import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from server import app
from holmes.core.models import PendingToolApproval, ToolApprovalDecision
from holmes.core.tools import StructuredToolResult, ToolResultStatus
from holmes.utils.stream import StreamEvents, StreamMessage


@pytest.fixture
def client():
    return TestClient(app)


class MockToolCallResult:
    """Mock for ToolCallResult used in streaming tests"""
    def __init__(self, tool_call_id, tool_name, description, result_status=ToolResultStatus.APPROVAL_REQUIRED, params=None):
        self.tool_call_id = tool_call_id
        self.tool_name = tool_name
        self.description = description
        self.result = StructuredToolResult(
            status=result_status,
            data="Command requires approval",
            params=params or {"command": "kubectl delete pod dangerous-pod"}
        )
    
    def as_streaming_tool_result_response(self):
        return {
            "tool_call_id": self.tool_call_id,
            "role": "tool",
            "description": self.description,
            "name": self.tool_name,
            "result": {
                "status": self.result.status.value,
                "data": self.result.data,
                "params": self.result.params
            }
        }


def create_mock_stream_generator(require_approval=True, approved_execution_result="Command executed successfully"):
    """Create a mock stream generator that simulates the approval workflow"""
    
    def mock_generator():
        # First, yield AI message
        yield StreamMessage(
            event=StreamEvents.AI_MESSAGE,
            data={"content": "I need to run a dangerous command. Let me check if this is allowed.", "reasoning": None}
        )
        
        # Then yield start tool message
        yield StreamMessage(
            event=StreamEvents.START_TOOL,
            data={"tool_name": "kubectl_delete", "id": "tool_call_123"}
        )
        
        if require_approval:
            # Yield approval required
            mock_tool_result = MockToolCallResult(
                tool_call_id="tool_call_123",
                tool_name="kubectl_delete",
                description="Delete Kubernetes pod: dangerous-pod"
            )
            
            yield StreamMessage(
                event=StreamEvents.TOOL_RESULT,
                data=mock_tool_result.as_streaming_tool_result_response()
            )
            
            # End stream with approval required
            yield StreamMessage(
                event=StreamEvents.APPROVAL_REQUIRED,
                data={
                    "content": None,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Delete the dangerous pod"},
                        {
                            "role": "assistant",
                            "content": "I need to run a dangerous command. Let me check if this is allowed.",
                            "tool_calls": [
                                {
                                    "id": "tool_call_123",
                                    "type": "function",
                                    "function": {
                                        "name": "kubectl_delete",
                                        "arguments": json.dumps({"command": "kubectl delete pod dangerous-pod"}),
                                    }
                                }
                            ],
                            "pending_approval": True,
                        }
                    ],
                    "pending_approvals": [
                        {
                            "tool_call_id": "tool_call_123",
                            "tool_name": "kubectl_delete",
                            "description": "Delete Kubernetes pod: dangerous-pod",
                            "params": {"command": "kubectl delete pod dangerous-pod"}
                        }
                    ],
                    "requires_approval": True,
                }
            )
        else:
            # Normal execution without approval
            mock_tool_result = MockToolCallResult(
                tool_call_id="tool_call_123",
                tool_name="kubectl_delete", 
                description="Delete Kubernetes pod: dangerous-pod",
                result_status=ToolResultStatus.SUCCESS
            )
            mock_tool_result.result.data = approved_execution_result
            
            yield StreamMessage(
                event=StreamEvents.TOOL_RESULT,
                data=mock_tool_result.as_streaming_tool_result_response()
            )
            
            # End with answer
            yield StreamMessage(
                event=StreamEvents.ANSWER_END,
                data={
                    "content": "Command executed successfully. The dangerous pod has been deleted.",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Delete the dangerous pod"},
                        {"role": "assistant", "content": "I need to run a dangerous command. Let me check if this is allowed."},
                        {"role": "tool", "content": approved_execution_result, "name": "kubectl_delete", "tool_call_id": "tool_call_123"}
                    ]
                }
            )
    
    return mock_generator


@patch("holmes.config.Config.load_robusta_api_key")
@patch("holmes.config.Config.create_toolcalling_llm")
@patch("holmes.core.supabase_dal.SupabaseDal.get_global_instructions_for_account")
def test_streaming_chat_approval_workflow_requires_approval(
    mock_get_global_instructions,
    mock_create_toolcalling_llm,
    mock_load_robusta_api_key,
    client,
):
    """Test that streaming chat requests approval for dangerous commands"""
    
    # Setup mocks
    mock_load_robusta_api_key.return_value = None
    mock_get_global_instructions.return_value = []
    
    mock_ai = MagicMock()
    mock_ai.call_stream.return_value = create_mock_stream_generator(require_approval=True)()
    mock_create_toolcalling_llm.return_value = mock_ai
    
    # Make streaming request
    payload = {
        "ask": "Delete the dangerous pod",
        "conversation_history": [
            {"role": "system", "content": "You are a helpful assistant."}
        ],
        "stream": True,
        "enable_tool_approval": True
    }
    
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    
    # Parse streaming response
    events = []
    for line in response.text.split('\n'):
        if line.startswith('event: '):
            event_type = line[7:]
        elif line.startswith('data: '):
            try:
                data = json.loads(line[6:])
                events.append((event_type, data))
            except json.JSONDecodeError:
                pass
    
    # Verify we got the expected events
    event_types = [event[0] for event in events]
    assert StreamEvents.AI_MESSAGE.value in event_types
    assert StreamEvents.START_TOOL.value in event_types
    assert StreamEvents.TOOL_RESULT.value in event_types
    assert StreamEvents.APPROVAL_REQUIRED.value in event_types
    
    # Find the approval required event
    approval_event = next((event[1] for event in events if event[0] == StreamEvents.APPROVAL_REQUIRED.value), None)
    assert approval_event is not None
    assert approval_event["requires_approval"] is True
    assert "pending_approvals" in approval_event
    assert len(approval_event["pending_approvals"]) == 1
    
    pending_approval = approval_event["pending_approvals"][0]
    assert pending_approval["tool_call_id"] == "tool_call_123"
    assert pending_approval["tool_name"] == "kubectl_delete"
    assert pending_approval["description"] == "Delete Kubernetes pod: dangerous-pod"


@patch("holmes.config.Config.load_robusta_api_key")
@patch("holmes.config.Config.create_toolcalling_llm")
@patch("holmes.core.supabase_dal.SupabaseDal.get_global_instructions_for_account")
def test_streaming_chat_approval_workflow_approve_and_execute(
    mock_get_global_instructions,
    mock_create_toolcalling_llm,
    mock_load_robusta_api_key,
    client,
):
    """Test that streaming chat executes approved commands"""
    
    # Setup mocks
    mock_load_robusta_api_key.return_value = None
    mock_get_global_instructions.return_value = []
    
    mock_ai = MagicMock()
    
    # Mock process_tool_decisions to simulate approval and execution
    mock_ai.process_tool_decisions = MagicMock(side_effect=lambda messages, tool_decisions: messages + [{
        "tool_call_id": "tool_call_123",
        "role": "tool", 
        "name": "kubectl_delete",
        "content": "pod 'dangerous-pod' deleted"
    }])
    
    # For the streaming call after approval, return a simple answer
    def simple_answer_stream():
        yield StreamMessage(
            event=StreamEvents.ANSWER_END,
            data={
                "content": "Command executed successfully. The dangerous pod has been deleted.",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Delete the dangerous pod"},
                    {"role": "assistant", "content": "I need to run a dangerous command. Let me check if this is allowed."},
                    {"role": "tool", "content": "pod 'dangerous-pod' deleted", "name": "kubectl_delete", "tool_call_id": "tool_call_123"},
                    {"role": "assistant", "content": "Command executed successfully. The dangerous pod has been deleted."}
                ]
            }
        )
    
    mock_ai.call_stream.return_value = simple_answer_stream()
    mock_create_toolcalling_llm.return_value = mock_ai
    
    # Request with approval decision
    approval_payload = {
        "ask": "Delete the dangerous pod",
        "conversation_history": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Delete the dangerous pod"},
            {
                "role": "assistant",
                "content": "I need to run a dangerous command. Let me check if this is allowed.",
                "tool_calls": [
                    {
                        "id": "tool_call_123",
                        "type": "function",
                        "function": {
                            "name": "kubectl_delete",
                            "arguments": json.dumps({"command": "kubectl delete pod dangerous-pod"}),
                        }
                    }
                ],
                "pending_approval": True,
            }
        ],
        "stream": True,
        "enable_tool_approval": True,
        "tool_decisions": [
            {
                "tool_call_id": "tool_call_123",
                "approved": True
            }
        ]
    }
    
    response = client.post("/api/chat", json=approval_payload)
    assert response.status_code == 200
    
    # Parse streaming response
    events = []
    for line in response.text.split('\n'):
        if line.startswith('event: '):
            event_type = line[7:]
        elif line.startswith('data: '):
            try:
                data = json.loads(line[6:])
                events.append((event_type, data))
            except json.JSONDecodeError:
                pass
    
    # Verify execution completed
    event_types = [event[0] for event in events]
    assert StreamEvents.ANSWER_END.value in event_types
    
    # Find the answer end event
    answer_event = next((event[1] for event in events if event[0] == StreamEvents.ANSWER_END.value), None)
    assert answer_event is not None
    assert "Command executed successfully" in answer_event["analysis"]
    
    # Verify tool execution was called
    mock_ai.process_tool_decisions.assert_called_once()
    args, kwargs = mock_ai.process_tool_decisions.call_args
    tool_decisions = args[1]  # Second argument is tool_decisions
    assert len(tool_decisions) == 1
    assert tool_decisions[0].tool_call_id == "tool_call_123" 
    assert tool_decisions[0].approved is True


@patch("holmes.config.Config.load_robusta_api_key")
@patch("holmes.config.Config.create_toolcalling_llm")
@patch("holmes.core.supabase_dal.SupabaseDal.get_global_instructions_for_account")
def test_streaming_chat_approval_workflow_reject_command(
    mock_get_global_instructions,
    mock_create_toolcalling_llm,
    mock_load_robusta_api_key,
    client,
):
    """Test that streaming chat handles rejected commands"""
    
    # Setup mocks
    mock_load_robusta_api_key.return_value = None
    mock_get_global_instructions.return_value = []
    
    mock_ai = MagicMock()
    
    # Mock process_tool_decisions to simulate rejection
    mock_ai.process_tool_decisions = MagicMock(side_effect=lambda messages, tool_decisions: messages + [{
        "tool_call_id": "tool_call_123",
        "role": "tool",
        "name": "kubectl_delete", 
        "content": "Tool execution was denied by the user."
    }])
    
    # For the streaming call after rejection, return a simple answer
    def simple_rejection_stream():
        yield StreamMessage(
            event=StreamEvents.ANSWER_END,
            data={
                "content": "I understand. I won't execute the dangerous command as you denied the request.",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Delete the dangerous pod"},
                    {"role": "assistant", "content": "I need to run a dangerous command. Let me check if this is allowed."},
                    {"role": "tool", "content": "Tool execution was denied by the user.", "name": "kubectl_delete", "tool_call_id": "tool_call_123"},
                    {"role": "assistant", "content": "I understand. I won't execute the dangerous command as you denied the request."}
                ]
            }
        )
    
    mock_ai.call_stream.return_value = simple_rejection_stream()
    mock_create_toolcalling_llm.return_value = mock_ai
    
    # Request with rejection
    payload = {
        "ask": "Delete the dangerous pod",
        "conversation_history": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Delete the dangerous pod"},
            {
                "role": "assistant",
                "content": "I need to run a dangerous command. Let me check if this is allowed.",
                "tool_calls": [
                    {
                        "id": "tool_call_123",
                        "type": "function",
                        "function": {
                            "name": "kubectl_delete",
                            "arguments": json.dumps({"command": "kubectl delete pod dangerous-pod"}),
                        }
                    }
                ],
                "pending_approval": True,
            }
        ],
        "stream": True,
        "enable_tool_approval": True,
        "tool_decisions": [
            {
                "tool_call_id": "tool_call_123",
                "approved": False
            }
        ]
    }
    
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    
    # Parse streaming response to verify rejection was handled
    events = []
    for line in response.text.split('\n'):
        if line.startswith('event: '):
            event_type = line[7:]
        elif line.startswith('data: '):
            try:
                data = json.loads(line[6:])
                events.append((event_type, data))
            except json.JSONDecodeError:
                pass
    
    # Verify execution completed
    event_types = [event[0] for event in events]
    assert StreamEvents.ANSWER_END.value in event_types
    
    # Find the answer end event
    answer_event = next((event[1] for event in events if event[0] == StreamEvents.ANSWER_END.value), None)
    assert answer_event is not None
    assert "won't execute" in answer_event["analysis"]
    
    # Verify tool processing was called
    mock_ai.process_tool_decisions.assert_called_once()
    args, kwargs = mock_ai.process_tool_decisions.call_args
    tool_decisions = args[1]  # Second argument is tool_decisions
    assert len(tool_decisions) == 1
    assert tool_decisions[0].tool_call_id == "tool_call_123"
    assert tool_decisions[0].approved is False