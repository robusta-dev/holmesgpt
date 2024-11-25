import logging
from pathlib import Path
import subprocess
from typing import List, Optional
from langfuse import Langfuse
from pydantic import TypeAdapter
import os
import sys
import pytest

from holmes.core.conversations import build_chat_messages
from holmes.core.llm import DefaultLLM
from holmes.core.models import ChatRequest
from holmes.core.tool_calling_llm import LLMResult, ToolCallingLLM
from holmes.core.tools import ToolExecutor
from tests.llm.utils.braintrust import upload_dataset
from tests.llm.utils.classifiers import get_context_classifier, get_logs_explanation_classifier
from tests.llm.utils.commands import invoke_command
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.langfuse import resolve_dataset_item, upload_test_cases
from tests.llm.utils.system import readable_timestamp
from tests.llm.utils.mock_toolset import MockToolsets
from braintrust import Experiment, ReadonlyExperiment
import concurrent.futures

from autoevals.llm import Factuality
import braintrust
from tests.llm.utils.mock_utils import AskHolmesTestCase, MockHelper
from tests.llm.utils.system import get_machine_state_tags
from os import path
import unittest

TEST_CASES_FOLDER = Path(path.abspath(path.join(
    path.dirname(__file__),
    "fixtures", "test_ask_holmes", "7_high_latency", "helm"

)))

logger = logging.getLogger()
logger.level = logging.INFO
stream_handler = logging.StreamHandler(sys.stdout)
logger.addHandler(stream_handler)


class TestHighLatency(unittest.TestCase):

    def setUp(self):
        invoke_command(
            command="kubectl apply -f ./manifest.yaml",
            cwd=TEST_CASES_FOLDER.absolute().as_posix()
        )

    @pytest.mark.llm
    def test_high_latency(self):

        tc = AskHolmesTestCase(
            id="7_high_latency",
            folder=TEST_CASES_FOLDER.absolute().as_posix(),
            mocks_passthrough=True,
            expected_output="The result mentions a timeout, connection, or dns resolution failure for promotions-db.cp8rwothwarq.us-east-2.rds.amazonaws.com",
            user_prompt="Why is there high latency with the customer-orders deployment?"
        )
        result = ask_holmes(tc)
        print(result.result)
        assert False

    def tearDown(self) -> None:
        invoke_command(
            command="kubectl delete -f ./manifest.yaml",
            cwd=TEST_CASES_FOLDER.absolute().as_posix()
        )

def ask_holmes(test_case:AskHolmesTestCase) -> LLMResult:

    mock = MockToolsets(tools_passthrough=test_case.mocks_passthrough, test_case_folder=test_case.folder)

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

    chat_request = ChatRequest(ask=test_case.user_prompt)

    messages = build_chat_messages(
        chat_request.ask, [], ai=ai
    )
    return ai.messages_call(messages=messages)
