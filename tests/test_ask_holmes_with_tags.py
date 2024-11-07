import json
from pathlib import Path
from typing import List, Optional
import pytest
from unittest.mock import Mock, patch
from holmes.common.env_vars import HOLMES_POST_PROCESSING_PROMPT
from holmes.config import Config
from holmes.core.issue import Issue
from holmes.core.llm import DefaultLLM
from holmes.core.models import ConversationType, InvestigateRequest
from holmes.core.runbooks import RunbookManager
from holmes.core.tool_calling_llm import IssueInvestigator, ResourceInstructions, ToolCallingLLM
from holmes.core.tools import ToolExecutor
from holmes.plugins.prompts import load_and_render_prompt
from holmes.plugins.toolsets import load_builtin_toolsets
from holmes.main import alertmanager, init_logging
from holmes.plugins.destinations import DestinationType
from rich.console import Console
from tests.mock_toolset import MockMetadata, MockToolsets, ToolMock

from deepeval import assert_test
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, ContextualPrecisionMetric, ContextualRecallMetric, ContextualRelevancyMetric


from tests.utils import AskHolmesTestCase, load_ask_holmes_test_cases

TEST_CASES_FOLDER = Path("tests/fixtures/test_ask_holmes_with_tags")

test_cases = load_ask_holmes_test_cases(TEST_CASES_FOLDER, expected_number_of_test_cases=6)

@pytest.mark.parametrize("test_case", test_cases, ids=[test_case.id for test_case in test_cases])
def test_ask_holmes_with_tags(test_case:AskHolmesTestCase):
    console = init_logging  ()
    mock = MockToolsets(tools_passthrough=test_case.tools_passthrough, test_case_folder=test_case.folder)

    expected_tools = []
    for tool_mock in test_case.tool_mocks:
        mock.mock_tool(tool_mock)
        expected_tools.append(tool_mock.tool_name)

    tool_executor = ToolExecutor(mock.mocked_toolsets)
    ai = ToolCallingLLM(
        tool_executor=tool_executor,
        max_steps=10,
        llm=DefaultLLM("gpt-4o")
    )

    template_context = {
        "investigation": "",
        "tools_called_for_investigation": None,
        "conversation_history": [],
    }

    system_prompt = load_and_render_prompt("builtin://generic_ask_for_issue_conversation.jinja2", template_context)

    result = ai.call(system_prompt, test_case.user_prompt)

    test_case = LLMTestCase(
        name=f"ask_holmes:{test_case.id}",
        input=test_case.user_prompt,
        actual_output=result.result,
        expected_output=test_case.expected_output,
        retrieval_context=test_case.retrieval_context,
        tools_called=[tool_call.tool_name for tool_call in (result.tool_calls or [])],
        expected_tools=expected_tools
    )
    assert_test(test_case, [
        AnswerRelevancyMetric(0.5),
        FaithfulnessMetric(0.5),
        ContextualPrecisionMetric(
            threshold=0.5,
            model="gpt-4o",
            include_reason=True
        ),
        ContextualRecallMetric(
            threshold=0.5,
            model="gpt-4o",
            include_reason=True
        ),
        ContextualRelevancyMetric(
            threshold=0.5,
            model="gpt-4o",
            include_reason=True
        )
    ])



# def _test_ask_holmes_with_tags():#mock_config, mock_source):

#     console = Console()

#     mock = MockToolsets(require_mock=True)
#     mock.mock_tool(ToolMock(
#         toolset_name="kubernetes/core",
#         tool_name="kubectl_describe",
#         match_params={},
#         return_value="Warning  Failed  8s (x3 over 22s)  kubelet, nginx-7ef9efa7cd-qasd2  Error: container create failed: container_linux.go:296: starting container process caused \"exec: \"mycommand\": executable file not found in $PATH\""
#     ))
#     mock.mock_tool(ToolMock(
#         toolset_name="kubernetes/core",
#         tool_name="kubectl_logs",
#         match_params={},
#         return_value=""
#     ))
#     mock.mock_tool(ToolMock(
#         toolset_name="kubernetes/core",
#         tool_name="kubectl_previous_logs",
#         match_params={},
#         return_value=""
#     ))

#     tool_executor = ToolExecutor(mock.mocked_toolsets)
#     ai = ToolCallingLLM(
#         "gpt-4o",
#         api_key=None,
#         tool_executor=tool_executor,
#         max_steps=10,
#     )

#     template_context = {
#         "investigation": "",
#         "tools_called_for_investigation": None,
#         "conversation_history": [],
#     }

#     system_prompt = load_and_render_prompt("builtin://generic_ask_for_issue_conversation.jinja2", template_context)

#     user_prompt = "Tell me why pod nginx-7ef9efa7cd-qasd2 is failing and how to fix it"
#     result = ai.call(system_prompt, user_prompt)


#     print(result.result)
#     print(result.tool_calls)
#     assert result.tool_calls
#     print([t.tool_name for t in result.tool_calls])
#     assert len(result.tool_calls) == 10
