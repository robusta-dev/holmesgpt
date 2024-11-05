
from pathlib import Path
import pytest
from unittest.mock import Mock, patch
from holmes.common.env_vars import HOLMES_POST_PROCESSING_PROMPT
from holmes.config import Config
from holmes.core.issue import Issue
from holmes.core.models import InvestigateRequest
from holmes.core.runbooks import RunbookManager
from holmes.core.tool_calling_llm import IssueInvestigator, ResourceInstructions, ToolCallingLLM
from holmes.core.tools import ToolExecutor
from holmes.plugins.toolsets import load_builtin_toolsets
from holmes.main import alertmanager
from holmes.plugins.destinations import DestinationType
from rich.console import Console
from tests.mock_toolset import MockToolsets

@pytest.fixture
def mock_config():
    with patch('holmes.config') as MockConfig:
        config = MockConfig.return_value
        config.create_issue_investigator.return_value = Mock()
        config.create_alertmanager_source.return_value = Mock()
        yield config

@pytest.fixture
def mock_source(mock_config):
    source = mock_config.create_alertmanager_source.return_value
    source.fetch_issues.return_value = [
        Mock(name="Alert1"),
        Mock(name="Alert2")
    ]
    return source

def test_alertmanager():#mock_config, mock_source):

    # resource_instructions = ResourceInstructions(instructions=[], documents=[])
    # runbook_manager = RunbookManager([])

    # ai = IssueInvestigator(
    #     "gpt-4o",
    #     api_key=None,
    #     runbook_manager=runbook_manager,
    #     tool_executor=ToolExecutor(load_builtin_toolsets()),
    #     max_steps=10,
    # )
    # issue = Issue(
    #     id=context["id"] if context else "",
    #     name=investigate_request.title,
    #     source_type=investigate_request.source,
    #     source_instance_id=investigate_request.source_instance_id,
    #     raw=raw_data,
    # )
    #
    #
    investigate_request = InvestigateRequest(
        source="prometheus",
        title="starting container process caused",
        description="starting container process caused \"exec: \"mycommand\": executable file not found in $PATH\"",
        subject=dict(),
        context=dict(),
        source_instance_id="ApiRequest",
        include_tool_calls=True,
        include_tool_call_results=True,
        prompt_template="builtin://generic_investigation.jinja2",
    )
    raw_data = investigate_request.model_dump()
    console = Console()

    resource_instructions = ResourceInstructions(instructions=[], documents=[])
    runbook_manager = RunbookManager([])

    mock = MockToolsets(default_response="")
    mock.mock_tool(
        toolset_name="kubernetes/core",
        tool_name="kubectl_describe",
        match_params={},
        return_value="Warning  Failed  8s (x3 over 22s)  kubelet, nginx-7ef9efa7cd-qasd2  Error: container create failed: container_linux.go:296: starting container process caused \"exec: \"mycommand\": executable file not found in $PATH\""
    )
    mock.mock_tool(
        toolset_name="kubernetes/core",
        tool_name="kubectl_get",
        match_params={},
        return_value="Warning  Failed  8s (x3 over 22s)  kubelet, nginx-7ef9efa7cd-qasd2  Error: container create failed: container_linux.go:296: starting container process caused \"exec: \"mycommand\": executable file not found in $PATH\""
    )
    mock.mock_tool(
        toolset_name="kubernetes/core",
        tool_name="kubectl_get_all",
        match_params={},
        return_value="Warning  Failed  8s (x3 over 22s)  kubelet, nginx-7ef9efa7cd-qasd2  Error: container create failed: container_linux.go:296: starting container process caused \"exec: \"mycommand\": executable file not found in $PATH\""
    )
    mock.mock_tool(
        toolset_name="kubernetes/core",
        tool_name="kubectl_find_resource",
        match_params={},
        return_value="Warning  Failed  8s (x3 over 22s)  kubelet, nginx-7ef9efa7cd-qasd2  Error: container create failed: container_linux.go:296: starting container process caused \"exec: \"mycommand\": executable file not found in $PATH\""
    )
    mock.mock_tool(
        toolset_name="kubernetes/core",
        tool_name="kubectl_get_yaml",
        match_params={},
        return_value="Warning  Failed  8s (x3 over 22s)  kubelet, nginx-7ef9efa7cd-qasd2  Error: container create failed: container_linux.go:296: starting container process caused \"exec: \"mycommand\": executable file not found in $PATH\""
    )
    mock.mock_tool(
        toolset_name="kubernetes/core",
        tool_name="kubectl_previous_logs",
        match_params={},
        return_value="Warning  Failed  8s (x3 over 22s)  kubelet, nginx-7ef9efa7cd-qasd2  Error: container create failed: container_linux.go:296: starting container process caused \"exec: \"mycommand\": executable file not found in $PATH\""
    )
    mock.mock_tool(
        toolset_name="kubernetes/core",
        tool_name="kubectl_logs",
        match_params={},
        return_value="Warning  Failed  8s (x3 over 22s)  kubelet, nginx-7ef9efa7cd-qasd2  Error: container create failed: container_linux.go:296: starting container process caused \"exec: \"mycommand\": executable file not found in $PATH\""
    )

    ai = IssueInvestigator(
        "gpt-4o",
        api_key=None,
        runbook_manager=runbook_manager,
        tool_executor=ToolExecutor(mock.mocked_toolsets),
        max_steps=10,
    )

    issue = Issue(
        id="",
        name=investigate_request.title,
        source_type=investigate_request.source,
        source_instance_id=investigate_request.source_instance_id,
        raw=raw_data,
    )

    investigation = ai.investigate(
        issue=issue,
        prompt=investigate_request.prompt_template,
        console=console,
        post_processing_prompt=HOLMES_POST_PROCESSING_PROMPT,
        instructions=resource_instructions,
    )

    print(investigation.tool_calls)
    assert investigation.tool_calls
    print([t.tool_name for t in investigation.tool_calls])
    assert len(investigation.tool_calls) == 10
