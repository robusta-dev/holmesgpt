from unittest.mock import Mock, patch
import pytest
import subprocess
import os

from holmes.utils.holmes_sync_toolsets import holmes_sync_toolsets_status
from holmes.core.tools import Toolset, ToolsetStatusEnum, ToolsetTag, YAMLTool
from holmes.config import Config


@pytest.fixture
def mock_dal():
    dal = Mock()
    dal.account_id = "test-account"
    dal.sync_toolsets = Mock()
    return dal


@pytest.fixture
def mock_config():
    config = Mock(spec=Config)
    config.cluster_name = "test-cluster"
    return config


@pytest.fixture
def sample_toolset():
    return Toolset(
        name="test-toolset",
        description="Test toolset",
        enabled=True,
        tools=[
            YAMLTool(name="test-tool", description="Test tool", command="echo test")
        ],
        tags=[ToolsetTag.CORE],
    )


def test_sync_toolsets_basic(mock_dal, mock_config, sample_toolset):
    mock_config.create_tool_executor.return_value = Mock(toolsets=[sample_toolset])

    holmes_sync_toolsets_status(mock_dal, mock_config)

    mock_dal.sync_toolsets.assert_called_once()
    call_args = mock_dal.sync_toolsets.call_args[0]

    assert len(call_args[0]) == 1
    toolset_data = call_args[0][0]

    assert toolset_data["toolset_name"] == "test-toolset"
    assert toolset_data["cluster_id"] == "test-cluster"
    assert toolset_data["account_id"] == "test-account"
    assert toolset_data["description"] == "Test toolset"
    assert toolset_data["status"] == ToolsetStatusEnum.DISABLED
    assert isinstance(toolset_data["updated_at"], str)


def test_sync_toolsets_no_cluster_name(mock_dal):
    config = Mock(spec=Config)
    config.cluster_name = None

    with pytest.raises(Exception) as exc_info:
        holmes_sync_toolsets_status(mock_dal, config)

    assert "Cluster name is missing" in str(exc_info.value)
    mock_dal.sync_toolsets.assert_not_called()


@patch(
    "holmes.utils.holmes_sync_toolsets.render_default_installation_instructions_for_toolset"
)
def test_sync_toolsets_with_installation_instructions(
    mock_render, mock_dal, mock_config, sample_toolset
):
    mock_render.return_value = "Test installation instructions"
    mock_config.create_tool_executor.return_value = Mock(toolsets=[sample_toolset])

    holmes_sync_toolsets_status(mock_dal, mock_config)

    mock_dal.sync_toolsets.assert_called_once()
    toolset_data = mock_dal.sync_toolsets.call_args[0][0][0]

    assert toolset_data["installation_instructions"] == "Test installation instructions"
    mock_render.assert_called_once_with(sample_toolset)


@patch("subprocess.run")
def test_sync_toolsets_multiple(mock_subprocess_run, mock_dal, mock_config):
    mock_subprocess_run.return_value = Mock(stdout="success", returncode=0)

    toolset1 = Toolset(
        name="toolset1",
        description="First toolset",
        enabled=True,
        tools=[YAMLTool(name="tool1", description="Tool 1", command="echo 1")],
        tags=[ToolsetTag.CORE],
    )
    toolset1.check_prerequisites()

    toolset2 = Toolset(
        name="toolset2",
        description="Second toolset",
        enabled=False,
        tools=[YAMLTool(name="tool2", description="Tool 2", command="echo 2")],
        tags=[ToolsetTag.CLI],
        prerequisites=[{"enabled": False, "disabled_reason": "Feature flag disabled"}],
    )
    toolset2.check_prerequisites()

    mock_config.create_tool_executor.return_value = Mock(toolsets=[toolset1, toolset2])

    holmes_sync_toolsets_status(mock_dal, mock_config)

    mock_dal.sync_toolsets.assert_called_once()
    toolsets_data = mock_dal.sync_toolsets.call_args[0][0]

    assert len(toolsets_data) == 2

    assert toolsets_data[0]["toolset_name"] == "toolset1"
    assert toolsets_data[0]["status"] == ToolsetStatusEnum.ENABLED

    assert toolsets_data[1]["toolset_name"] == "toolset2"
    assert toolsets_data[1]["status"] == ToolsetStatusEnum.DISABLED


@patch("subprocess.run")
def test_sync_toolsets_with_prerequisites_check(
    mock_subprocess_run, mock_dal, mock_config
):
    mock_subprocess_run.return_value = Mock(stdout="success", returncode=0)

    toolset = Toolset(
        name="test-toolset",
        description="Test toolset",
        enabled=True,
        tools=[
            YAMLTool(name="test-tool", description="Test tool", command="echo test")
        ],
        tags=[ToolsetTag.CORE],
        prerequisites=[],
    )
    toolset.check_prerequisites()

    mock_config.create_tool_executor.return_value = Mock(toolsets=[toolset])

    holmes_sync_toolsets_status(mock_dal, mock_config)

    mock_dal.sync_toolsets.assert_called_once()
    toolset_data = mock_dal.sync_toolsets.call_args[0][0][0]

    assert toolset_data["status"] == ToolsetStatusEnum.ENABLED
    assert toolset_data["error"] is None


@patch("subprocess.run")
def test_sync_toolsets_with_failed_prerequisites(
    mock_subprocess_run, mock_dal, mock_config
):
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        1, "some-failing-command", "error output"
    )

    toolset = Toolset(
        name="test-toolset",
        description="Test toolset",
        enabled=True,
        tools=[
            YAMLTool(name="test-tool", description="Test tool", command="echo test")
        ],
        tags=[ToolsetTag.CORE],
        prerequisites=[
            {
                "command": "some-failing-command",
            }
        ],
    )
    toolset.check_prerequisites()

    mock_config.create_tool_executor.return_value = Mock(toolsets=[toolset])

    holmes_sync_toolsets_status(mock_dal, mock_config)

    mock_dal.sync_toolsets.assert_called_once()
    toolset_data = mock_dal.sync_toolsets.call_args[0][0][0]

    assert toolset_data["status"] == ToolsetStatusEnum.FAILED
    assert toolset_data["error"] is not None
    assert "Prerequisites check failed" in toolset_data["error"]


@patch("subprocess.run")
def test_sync_toolsets_with_successful_prerequisites(
    mock_subprocess_run, mock_dal, mock_config
):
    mock_subprocess_run.return_value = Mock(stdout="success\n", returncode=0)

    toolset = Toolset(
        name="test-toolset",
        description="Test toolset",
        enabled=True,
        tools=[
            YAMLTool(name="test-tool", description="Test tool", command="echo test")
        ],
        tags=[ToolsetTag.CORE],
        prerequisites=[{"command": "echo success", "expected_output": "success"}],
    )
    toolset.check_prerequisites()

    mock_config.create_tool_executor.return_value = Mock(toolsets=[toolset])

    holmes_sync_toolsets_status(mock_dal, mock_config)

    mock_dal.sync_toolsets.assert_called_once()
    toolset_data = mock_dal.sync_toolsets.call_args[0][0][0]

    assert toolset_data["status"] == ToolsetStatusEnum.ENABLED
    assert toolset_data["error"] is None


@patch.dict(os.environ, {}, clear=True)
def test_sync_toolsets_with_missing_env_var_prerequisites(mock_dal, mock_config):
    toolset = Toolset(
        name="test-toolset",
        description="Test toolset",
        enabled=True,
        tools=[
            YAMLTool(name="test-tool", description="Test tool", command="echo test")
        ],
        tags=[ToolsetTag.CORE],
        prerequisites=[{"env": ["NONEXISTENT_ENV_VAR"]}],
    )
    toolset.check_prerequisites()

    mock_config.create_tool_executor.return_value = Mock(toolsets=[toolset])

    holmes_sync_toolsets_status(mock_dal, mock_config)

    mock_dal.sync_toolsets.assert_called_once()
    toolset_data = mock_dal.sync_toolsets.call_args[0][0][0]

    assert toolset_data["status"] == ToolsetStatusEnum.FAILED
    assert toolset_data["error"] is not None
    assert "NONEXISTENT_ENV_VAR" in toolset_data["error"]


@patch("subprocess.run")
def test_sync_toolsets_with_command_output_mismatch(
    mock_subprocess_run, mock_dal, mock_config
):
    mock_subprocess_run.return_value = Mock(
        stdout="wrong output\n", returncode=0, stderr=""
    )

    toolset = Toolset(
        name="test-toolset",
        description="Test toolset",
        enabled=True,
        tools=[
            YAMLTool(name="test-tool", description="Test tool", command="echo test")
        ],
        tags=[ToolsetTag.CORE],
        prerequisites=[
            {"command": "some-command", "expected_output": "expected output"}
        ],
    )
    toolset.check_prerequisites()

    mock_config.create_tool_executor.return_value = Mock(toolsets=[toolset])

    holmes_sync_toolsets_status(mock_dal, mock_config)

    mock_dal.sync_toolsets.assert_called_once()
    toolset_data = mock_dal.sync_toolsets.call_args[0][0][0]

    assert toolset_data["status"] == ToolsetStatusEnum.FAILED
    assert toolset_data["error"] is not None
    assert "Prerequisites check gave wrong output" in toolset_data["error"]
