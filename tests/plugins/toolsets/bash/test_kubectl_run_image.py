"""
Tests for the kubectl_run_image toolset functionality.

These tests verify that the KubectlRunImageCommand properly validates
images and commands according to the configured whitelist.
"""

import pytest
from unittest.mock import patch, MagicMock

from holmes.core.tools import ToolResultStatus
from holmes.plugins.toolsets.bash.kubectl_run_image import (
    KubectlRunImageToolset,
    KubectlRunImageCommand,
    KubectlRunImageConfig,
    KubectlImageConfig,
    validate_image_and_commands,
)


class TestValidateImageAndCommands:
    """Tests for the validate_image_and_commands function."""

    def test_no_config_raises_error(self):
        """Test that validation fails when no config is provided."""
        with pytest.raises(
            ValueError, match="kubectl run.*is not allowed.*none have been configured"
        ):
            validate_image_and_commands("busybox", "echo test", None)

    def test_image_not_in_whitelist(self):
        """Test that validation fails for non-whitelisted images."""
        config = KubectlRunImageConfig(
            allowed_images=[
                KubectlImageConfig(image="busybox", allowed_commands=["echo .*"])
            ]
        )

        with pytest.raises(ValueError, match="Image 'malicious-image' not allowed"):
            validate_image_and_commands("malicious-image", "echo test", config)

    def test_command_not_matching_patterns(self):
        """Test that validation fails for commands not matching allowed patterns."""
        config = KubectlRunImageConfig(
            allowed_images=[
                KubectlImageConfig(
                    image="busybox",
                    allowed_commands=["echo .*", "cat /etc/resolv.conf"],
                )
            ]
        )

        with pytest.raises(ValueError, match="Command 'rm -rf /' not allowed"):
            validate_image_and_commands("busybox", "rm -rf /", config)

    def test_valid_image_and_command(self):
        """Test that validation passes for whitelisted image and matching command."""
        config = KubectlRunImageConfig(
            allowed_images=[
                KubectlImageConfig(
                    image="busybox",
                    allowed_commands=["echo .*", "cat /etc/resolv.conf"],
                )
            ]
        )

        # Should not raise any exception
        validate_image_and_commands("busybox", "echo hello world", config)
        validate_image_and_commands("busybox", "cat /etc/resolv.conf", config)

    def test_regex_pattern_matching(self):
        """Test that regex patterns work correctly for command matching."""
        config = KubectlRunImageConfig(
            allowed_images=[
                KubectlImageConfig(
                    image="curlimages/curl", allowed_commands=[r"curl -s http://.*"]
                )
            ]
        )

        # Should pass
        validate_image_and_commands(
            "curlimages/curl", "curl -s http://example.com", config
        )

        # Should fail - doesn't match the pattern
        with pytest.raises(
            ValueError, match="Command 'curl http://example.com' not allowed"
        ):
            validate_image_and_commands(
                "curlimages/curl", "curl http://example.com", config
            )


class TestKubectlRunImageCommand:
    """Tests for the KubectlRunImageCommand class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.toolset = KubectlRunImageToolset()
        self.toolset.config = KubectlRunImageConfig(
            allowed_images=[
                KubectlImageConfig(
                    image="busybox",
                    allowed_commands=["echo .*", "cat /etc/resolv.conf"],
                ),
                KubectlImageConfig(
                    image="curlimages/curl", allowed_commands=[r"curl -s http://.*"]
                ),
            ]
        )
        self.tool = KubectlRunImageCommand(self.toolset)

    def test_invalid_namespace_pattern(self):
        """Test that invalid namespace patterns are rejected."""
        params = {
            "image": "busybox",
            "command": "echo test",
            "namespace": "../../../etc/passwd",
        }

        result = self.tool._invoke(params)
        assert result.status == ToolResultStatus.ERROR
        assert "namespace is invalid" in result.error

    def test_valid_namespace_pattern(self):
        """Test that valid namespace patterns are accepted."""
        params = {
            "image": "busybox",
            "command": "echo test",
            "namespace": "my-namespace",
        }

        with patch(
            "holmes.plugins.toolsets.bash.kubectl_run_image.execute_bash_command"
        ) as mock_exec:
            mock_exec.return_value = MagicMock()
            self.tool._invoke(params)
            mock_exec.assert_called_once()

    def test_image_validation_error(self):
        """Test that image validation errors are properly handled."""
        params = {"image": "malicious-image", "command": "echo test"}

        result = self.tool._invoke(params)
        assert result.status == ToolResultStatus.ERROR
        assert "not allowed" in result.error

    def test_command_validation_error(self):
        """Test that command validation errors are properly handled."""
        params = {"image": "busybox", "command": "rm -rf /"}

        result = self.tool._invoke(params)
        assert result.status == ToolResultStatus.ERROR
        assert "not allowed" in result.error

    @patch("holmes.plugins.toolsets.bash.kubectl_run_image.execute_bash_command")
    def test_successful_execution(self, mock_exec):
        """Test successful command execution with valid parameters."""
        mock_exec.return_value = MagicMock()

        params = {
            "image": "busybox",
            "command": "echo hello",
            "namespace": "test-ns",
            "timeout": 30,
        }

        self.tool._invoke(params)

        # Verify execute_bash_command was called
        mock_exec.assert_called_once()
        args, kwargs = mock_exec.call_args

        # Check that the command was built correctly
        cmd = kwargs["cmd"]
        assert "kubectl run" in cmd
        assert "--image=busybox" in cmd
        assert "--namespace=test-ns" in cmd
        assert "--rm --attach --restart=Never -i" in cmd
        assert "-- echo hello" in cmd
        assert kwargs["timeout"] == 30

    def test_build_kubectl_command(self):
        """Test the kubectl command building logic."""
        params = {"image": "busybox", "command": "echo test", "namespace": "my-ns"}

        cmd = self.tool._build_kubectl_command(params, "test-pod")
        expected = "kubectl run test-pod --image=busybox --namespace=my-ns --rm --attach --restart=Never -i -- echo test"
        assert cmd == expected

    def test_build_kubectl_command_default_namespace(self):
        """Test kubectl command building with default namespace."""
        params = {"image": "busybox", "command": "echo test"}

        cmd = self.tool._build_kubectl_command(params, "test-pod")
        expected = "kubectl run test-pod --image=busybox --namespace=default --rm --attach --restart=Never -i -- echo test"
        assert cmd == expected

    def test_get_parameterized_one_liner(self):
        """Test the one-liner representation of the command."""
        params = {"image": "busybox", "command": "echo test", "namespace": "my-ns"}

        one_liner = self.tool.get_parameterized_one_liner(params)
        assert "kubectl run <pod_name>" in one_liner
        assert "--image=busybox" in one_liner
        assert "--namespace=my-ns" in one_liner


class TestKubectlRunImageToolset:
    """Tests for the KubectlRunImageToolset class."""

    def test_toolset_initialization(self):
        """Test that the toolset initializes correctly."""
        toolset = KubectlRunImageToolset()

        assert toolset.name == "kubectl_run_image"
        assert not toolset.enabled
        assert len(toolset.tools) == 1
        assert isinstance(toolset.tools[0], KubectlRunImageCommand)

    def test_prerequisites_callable_with_config(self):
        """Test prerequisites callable with valid config."""
        toolset = KubectlRunImageToolset()

        config = {
            "allowed_images": [{"image": "busybox", "allowed_commands": ["echo .*"]}]
        }

        success, message = toolset.prerequisites_callable(config)
        assert success
        assert message == ""
        assert toolset.config is not None
        assert len(toolset.config.allowed_images) == 1

    def test_prerequisites_callable_without_config(self):
        """Test prerequisites callable with no config."""
        toolset = KubectlRunImageToolset()

        success, message = toolset.prerequisites_callable(None)
        assert success
        assert message == ""
        assert toolset.config is not None
        assert len(toolset.config.allowed_images) == 0
