# type: ignore
import os
import subprocess
from typing import Any, Dict, List
from unittest.mock import Mock, call, patch

from holmes.core.tools import (
    CallablePrerequisite,
    StaticPrerequisite,
    Tool,
    Toolset,
    ToolsetCommandPrerequisite,
    ToolsetEnvironmentPrerequisite,
    ToolsetStatusEnum,
)
from tests.utils.toolsets import (
    callable_failure_no_message,
    callable_failure_with_message,
    callable_success,
    failing_callable_for_test,
)


class DummyTool(Tool):
    name: str = "dummy_tool"
    description: str = "A dummy tool"

    def _invoke(self, params: Dict) -> Any:
        pass

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return ""


class SampleToolset(Toolset):
    name: str = "sample_toolset"
    description: str = "A sample toolset for testing"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tools: List[Tool] = [DummyTool()]

    def get_example_config(self) -> Dict[str, Any]:
        return {}


def test_check_prerequisites_none():
    toolset = SampleToolset(prerequisites=[])
    toolset.check_prerequisites()
    assert toolset.status == ToolsetStatusEnum.ENABLED
    assert toolset.error is None


def test_check_prerequisites_static_enabled():
    prereq = StaticPrerequisite(enabled=True, disabled_reason="Should not be used")
    toolset = SampleToolset(prerequisites=[prereq])
    toolset.check_prerequisites()
    assert toolset.status == ToolsetStatusEnum.ENABLED
    assert toolset.error is None


def test_check_prerequisites_static_disabled():
    reason = "Feature is turned off"
    prereq = StaticPrerequisite(enabled=False, disabled_reason=reason)
    toolset = SampleToolset(prerequisites=[prereq])
    toolset.check_prerequisites()
    assert toolset.status == ToolsetStatusEnum.FAILED
    assert toolset.error == reason


@patch("subprocess.run")
def test_check_prerequisites_command_success(mock_subprocess_run):
    mock_subprocess_run.return_value = Mock(stdout="expected output", returncode=0)
    prereq = ToolsetCommandPrerequisite(
        command="my_command", expected_output="expected output"
    )
    toolset = SampleToolset(prerequisites=[prereq])
    toolset.check_prerequisites()
    assert toolset.status == ToolsetStatusEnum.ENABLED
    assert toolset.error is None
    mock_subprocess_run.assert_called_once_with(
        "my_command",
        shell=True,
        check=True,
        text=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )


@patch("subprocess.run")
def test_check_prerequisites_command_output_mismatch(mock_subprocess_run):
    mock_subprocess_run.return_value = Mock(stdout="actual output", returncode=0)
    prereq = ToolsetCommandPrerequisite(
        command="my_command", expected_output="expected output"
    )
    toolset = SampleToolset(prerequisites=[prereq])
    toolset.check_prerequisites()
    assert toolset.status == ToolsetStatusEnum.FAILED
    assert "did not include `expected output`" in toolset.error


@patch("subprocess.run")
def test_check_prerequisites_command_failure(mock_subprocess_run):
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        1, "my_command", "error output"
    )
    prereq = ToolsetCommandPrerequisite(command="my_command")
    toolset = SampleToolset(prerequisites=[prereq])
    toolset.check_prerequisites()
    assert toolset.status == ToolsetStatusEnum.FAILED


@patch.dict(os.environ, {"EXISTING_VAR": "value"}, clear=True)
def test_check_prerequisites_env_var_exists():
    prereq = ToolsetEnvironmentPrerequisite(env=["EXISTING_VAR"])
    toolset = SampleToolset(prerequisites=[prereq])
    toolset.check_prerequisites()
    assert toolset.status == ToolsetStatusEnum.ENABLED
    assert toolset.error is None


@patch.dict(os.environ, {}, clear=True)
def test_check_prerequisites_env_var_missing():
    prereq = ToolsetEnvironmentPrerequisite(env=["MISSING_VAR"])
    toolset = SampleToolset(prerequisites=[prereq])
    toolset.check_prerequisites()
    assert toolset.status == ToolsetStatusEnum.FAILED
    assert toolset.error == "Environment variable MISSING_VAR was not set"


def test_check_prerequisites_callable_success():
    prereq = CallablePrerequisite(callable=callable_success)
    toolset = SampleToolset(prerequisites=[prereq], config={"key": "value"})
    toolset.check_prerequisites()
    assert toolset.status == ToolsetStatusEnum.ENABLED
    assert toolset.error is None


def test_check_prerequisites_callable_failure_with_message():
    prereq = CallablePrerequisite(callable=callable_failure_with_message)
    toolset = SampleToolset(prerequisites=[prereq], config={})
    toolset.check_prerequisites()
    assert toolset.status == ToolsetStatusEnum.FAILED
    assert toolset.error == "Callable check failed"


def test_check_prerequisites_callable_failure_no_message():
    prereq = CallablePrerequisite(callable=callable_failure_no_message)
    toolset = SampleToolset(prerequisites=[prereq])
    toolset.check_prerequisites()
    assert toolset.status == ToolsetStatusEnum.FAILED
    assert toolset.error is None


@patch("subprocess.run")
@patch.dict(os.environ, {"EXISTING_VAR": "value"}, clear=True)
def test_check_prerequisites_multiple_success(mock_subprocess_run):
    mock_subprocess_run.return_value = Mock(stdout="output", returncode=0)
    prerequisites = [
        StaticPrerequisite(enabled=True, disabled_reason=""),
        ToolsetCommandPrerequisite(command="cmd1"),
        ToolsetEnvironmentPrerequisite(env=["EXISTING_VAR"]),
        CallablePrerequisite(callable=callable_success),
    ]
    toolset = SampleToolset(prerequisites=prerequisites, config={})
    toolset.check_prerequisites()
    assert toolset.status == ToolsetStatusEnum.ENABLED
    assert toolset.error is None
    assert mock_subprocess_run.call_count == 1  # Ensure command was run


@patch("subprocess.run")
def test_check_prerequisites_command_uses_interpolate_command(mock_subprocess_run):
    mock_subprocess_run.return_value = Mock(stdout="output", returncode=0)
    with patch.dict(os.environ, {"MY_VAR": "interpolated_value"}, clear=True):
        prereq = ToolsetCommandPrerequisite(command="echo $MY_VAR")
        toolset = SampleToolset(prerequisites=[prereq])
        toolset.check_prerequisites()
        mock_subprocess_run.assert_called_once_with(
            "echo interpolated_value",
            shell=True,
            check=True,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    assert toolset.status == ToolsetStatusEnum.ENABLED


@patch("subprocess.run")
@patch.dict(os.environ, {"EXISTING_VAR": "value"}, clear=True)
def test_check_prerequisites_multiple_all_types_success(mock_subprocess_run):
    mock_subprocess_run.return_value = Mock(stdout="output", returncode=0)
    mock_callable_success = Mock(return_value=(True, ""))
    second_mock_callable_success = Mock(return_value=(True, ""))

    prerequisites = [
        StaticPrerequisite(enabled=True, disabled_reason="Should not be used"),
        ToolsetEnvironmentPrerequisite(env=["EXISTING_VAR"]),
        ToolsetCommandPrerequisite(command="cmd1", expected_output="output"),
        ToolsetCommandPrerequisite(command="cmd2", expected_output="output"),
        CallablePrerequisite(callable=mock_callable_success),
        CallablePrerequisite(callable=second_mock_callable_success),
        ToolsetCommandPrerequisite(command="cmd3", expected_output="output"),
    ]
    toolset = SampleToolset(
        prerequisites=prerequisites, config={"some_config": "value"}
    )
    toolset.check_prerequisites()

    assert toolset.status == ToolsetStatusEnum.ENABLED
    assert toolset.error is None
    assert mock_subprocess_run.call_count == 3
    expected_subprocess_calls = [
        call(
            "cmd1",
            shell=True,
            check=True,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        ),
        call(
            "cmd2",
            shell=True,
            check=True,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        ),
        call(
            "cmd3",
            shell=True,
            check=True,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        ),
    ]
    mock_subprocess_run.assert_has_calls(expected_subprocess_calls, any_order=False)
    mock_callable_success.assert_called_once_with({"some_config": "value"})
    second_mock_callable_success.assert_called_once_with({"some_config": "value"})


@patch("subprocess.run")
@patch.dict(os.environ, {"EXISTING_VAR": "value"}, clear=True)
def test_check_prerequisites_stops_at_first_failure_command(mock_subprocess_run):
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        1, "failing_cmd", "error output"
    )
    mock_callable_should_not_be_called = Mock(return_value=(True, ""))

    prerequisites = [
        StaticPrerequisite(enabled=True, disabled_reason=""),
        ToolsetEnvironmentPrerequisite(env=["EXISTING_VAR"]),
        ToolsetCommandPrerequisite(command="failing_cmd"),  # This one should fail
        CallablePrerequisite(
            callable=mock_callable_should_not_be_called
        ),  # Should not be called
    ]
    toolset = SampleToolset(prerequisites=prerequisites, config={})
    toolset.check_prerequisites()

    assert toolset.status == ToolsetStatusEnum.FAILED
    assert toolset.error == "`failing_cmd` returned 1"
    mock_subprocess_run.assert_called_once_with(
        "failing_cmd",
        shell=True,
        check=True,
        text=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    mock_callable_should_not_be_called.assert_not_called()


def test_check_prerequisites_with_failing_callable():
    failing_prereq = CallablePrerequisite(callable=failing_callable_for_test)

    toolset = SampleToolset(
        name="failing-callable-toolset", prerequisites=[failing_prereq], config={}
    )

    toolset.check_prerequisites()

    assert toolset.status == ToolsetStatusEnum.FAILED
    assert toolset.error is not None
    expected_error_message = (
        "Prerequisite call failed unexpectedly: Failure in callable prerequisite"
    )
    assert toolset.error == expected_error_message


@patch("subprocess.run")
def test_check_prerequisites_command_timeout(mock_subprocess_run):
    mock_subprocess_run.side_effect = subprocess.TimeoutExpired("slow_command", 10)
    prereq = ToolsetCommandPrerequisite(command="slow_command")
    toolset = SampleToolset(prerequisites=[prereq])
    toolset.check_prerequisites()
    assert toolset.status == ToolsetStatusEnum.FAILED
    assert "`slow_command` timed out after 10 seconds" in toolset.error
    mock_subprocess_run.assert_called_once_with(
        "slow_command",
        shell=True,
        check=True,
        text=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
