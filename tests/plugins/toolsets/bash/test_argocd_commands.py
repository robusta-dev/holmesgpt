"""
Tests for Argo CD CLI command parsing, validation, and safety.

These tests verify:
1. Safe Argo CD commands are properly parsed and stringified
2. Unsafe Argo CD commands are rejected
3. Command validation works correctly
"""

import pytest
import argparse
from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.parse_command import make_command_safe


class TestArgoCDCliSafeCommands:
    """Test Argo CD CLI safe commands that should be allowed."""

    @pytest.mark.parametrize(
        "input_command,expected_output",
        [
            # Version command (no subcommands)
            ("argocd version", "argocd version"),
            ("argocd version --help", "argocd version --help"),
            # Context command (listing contexts)
            ("argocd context", "argocd context"),
            # Application management (read-only)
            ("argocd app list", "argocd app list"),
            ("argocd app get myapp", "argocd app get myapp"),
            (
                "argocd app get myapp --output json",
                "argocd app get myapp --output json",
            ),
            (
                "argocd app get myapp --output yaml",
                "argocd app get myapp --output yaml",
            ),
            (
                "argocd app get myapp --output wide",
                "argocd app get myapp --output wide",
            ),
            (
                "argocd app get myapp --show-params",
                "argocd app get myapp --show-params",
            ),
            (
                "argocd app get myapp --show-operation",
                "argocd app get myapp --show-operation",
            ),
            ("argocd app resources myapp", "argocd app resources myapp"),
            ("argocd app diff myapp", "argocd app diff myapp"),
            (
                "argocd app diff myapp --revision HEAD",
                "argocd app diff myapp --revision HEAD",
            ),
            ("argocd app history myapp", "argocd app history myapp"),
            (
                "argocd app history myapp --revision 5",
                "argocd app history myapp --revision 5",
            ),
            ("argocd app manifests myapp", "argocd app manifests myapp"),
            (
                "argocd app manifests myapp --source live",
                "argocd app manifests myapp --source live",
            ),
            ("argocd app logs myapp", "argocd app logs myapp"),
            ("argocd app logs myapp --tail 100", "argocd app logs myapp --tail 100"),
            (
                "argocd app logs myapp --filter error",
                "argocd app logs myapp --filter error",
            ),
            (
                "argocd app logs myapp --container web",
                "argocd app logs myapp --container web",
            ),
            (
                "argocd app logs myapp --group apps --kind Deployment --name myapp",
                "argocd app logs myapp --group apps --kind Deployment --name myapp",
            ),
            ("argocd app logs myapp --previous", "argocd app logs myapp --previous"),
            ("argocd app logs myapp --since 1h", "argocd app logs myapp --since 1h"),
            (
                "argocd app logs myapp --timestamps",
                "argocd app logs myapp --timestamps",
            ),
            ("argocd app wait myapp", "argocd app wait myapp"),
            (
                "argocd app wait myapp --timeout 300s",
                "argocd app wait myapp --timeout 300s",
            ),
            ("argocd app wait myapp --health", "argocd app wait myapp --health"),
            ("argocd app wait myapp --sync", "argocd app wait myapp --sync"),
            # Application listing with filters
            ("argocd app list --output table", "argocd app list --output table"),
            (
                "argocd app list --project myproject",
                "argocd app list --project myproject",
            ),
            (
                "argocd app list --cluster mycluster",
                "argocd app list --cluster mycluster",
            ),
            (
                "argocd app list --repo https://github.com/myorg/myrepo",
                "argocd app list --repo https://github.com/myorg/myrepo",
            ),
            (
                "argocd app list --selector app=web",
                "argocd app list --selector app=web",
            ),
            (
                "argocd app list --app-namespace mynamespace",
                "argocd app list --app-namespace mynamespace",
            ),
            # Cluster management (read-only)
            ("argocd cluster list", "argocd cluster list"),
            ("argocd cluster list --output wide", "argocd cluster list --output wide"),
            ("argocd cluster get mycluster", "argocd cluster get mycluster"),
            (
                "argocd cluster get https://kubernetes.default.svc",
                "argocd cluster get https://kubernetes.default.svc",
            ),
            # Project management (read-only)
            ("argocd proj list", "argocd proj list"),
            ("argocd proj get myproject", "argocd proj get myproject"),
            ("argocd proj get default", "argocd proj get default"),
            # Repository management (read-only)
            ("argocd repo list", "argocd repo list"),
            (
                "argocd repo get https://github.com/myorg/myrepo",
                "argocd repo get https://github.com/myorg/myrepo",
            ),
            (
                "argocd repo get git@github.com:myorg/myrepo.git",
                "argocd repo get git@github.com:myorg/myrepo.git",
            ),
            # Account management (read-only)
            ("argocd account list", "argocd account list"),
            ("argocd account get", "argocd account get"),
            ("argocd account get-user-info", "argocd account get-user-info"),
            (
                "argocd account can-i create applications",
                "argocd account can-i create applications",
            ),
            (
                "argocd account can-i get applications myapp",
                "argocd account can-i get applications myapp",
            ),
            # Administrative commands (read-only)
            ("argocd admin dashboard", "argocd admin dashboard"),
            (
                "argocd admin dashboard --port 8080",
                "argocd admin dashboard --port 8080",
            ),
            ("argocd admin settings", "argocd admin settings"),
            # Commands with server connection options
            (
                "argocd app list --server argocd.example.com",
                "argocd app list --server argocd.example.com",
            ),
            (
                "argocd app list --server argocd.example.com --insecure",
                "argocd app list --server argocd.example.com --insecure",
            ),
            ("argocd app list --grpc-web", "argocd app list --grpc-web"),
            ("argocd app list --plaintext", "argocd app list --plaintext"),
            # Commands with namespaces
            (
                "argocd app list --app-namespace default",
                "argocd app list --app-namespace default",
            ),
            (
                "argocd app get myapp --app-namespace production",
                "argocd app get myapp --app-namespace production",
            ),
            # Commands with selectors and filters
            (
                "argocd app list --selector environment=production",
                "argocd app list --selector environment=production",
            ),
            (
                "argocd app list --selector app.kubernetes.io/name=myapp",
                "argocd app list --selector app.kubernetes.io/name=myapp",
            ),
            # Commands with refresh options
            ("argocd app get myapp --refresh", "argocd app get myapp --refresh"),
            ("argocd app diff myapp --refresh", "argocd app diff myapp --refresh"),
            (
                "argocd app get myapp --hard-refresh",
                "argocd app get myapp --hard-refresh",
            ),
            # Log commands with various options
            (
                "argocd app logs myapp --since-time 2023-01-01T00:00:00Z",
                "argocd app logs myapp --since-time 2023-01-01T00:00:00Z",
            ),
            (
                "argocd app logs myapp --namespace default",
                "argocd app logs myapp --namespace default",
            ),
            (
                "argocd app logs myapp --match-case",
                "argocd app logs myapp --match-case",
            ),
            # Commands with log levels and formats (for admin)
            (
                "argocd admin dashboard --loglevel info",
                "argocd admin dashboard --loglevel info",
            ),
            (
                "argocd admin dashboard --logformat json",
                "argocd admin dashboard --logformat json",
            ),
            # Help commands
            ("argocd app --help", "argocd app --help"),
            ("argocd cluster --help", "argocd cluster --help"),
            ("argocd proj --help", "argocd proj --help"),
            ("argocd repo --help", "argocd repo --help"),
            # Commands with complex resource specifications
            (
                "argocd app logs myapp --group extensions --kind Deployment --name myapp",
                "argocd app logs myapp --group extensions --kind Deployment --name myapp",
            ),
            (
                "argocd app logs myapp --kind Pod --name myapp-pod-123",
                "argocd app logs myapp --kind Pod --name myapp-pod-123",
            ),
            # Wait commands with different conditions
            ("argocd app wait myapp --suspended", "argocd app wait myapp --suspended"),
            ("argocd app wait myapp --degraded", "argocd app wait myapp --degraded"),
            # Output formats for different commands
            ("argocd cluster list --output json", "argocd cluster list --output json"),
            ("argocd proj list --output yaml", "argocd proj list --output yaml"),
            ("argocd repo list --output wide", "argocd repo list --output wide"),
            (
                "argocd app get myapp --output tree",
                "argocd app get myapp --output tree",
            ),
            # Commands with config and client cert options (for connection)
            (
                "argocd app list --config /path/to/config",
                "argocd app list --config /path/to/config",
            ),
        ],
    )
    def test_argocd_safe_commands(self, input_command: str, expected_output: str):
        """Test that safe Argo CD commands are parsed and stringified correctly."""
        config = BashExecutorConfig()
        output_command = make_command_safe(input_command, config=config)
        assert output_command == expected_output


class TestArgoCDCliUnsafeCommands:
    """Test Argo CD CLI unsafe commands that should be rejected."""

    @pytest.mark.parametrize(
        "command,expected_exception,partial_error_message_content",
        [
            # Authentication operations (sensitive)
            (
                "argocd login argocd.example.com",
                ValueError,
                "blocked operation 'login'",
            ),
            ("argocd logout", ValueError, "blocked operation 'logout'"),
            ("argocd relogin", ValueError, "blocked operation 'relogin'"),
            # State-modifying application operations
            ("argocd app create myapp", ValueError, "blocked operation 'create'"),
            ("argocd app delete myapp", ValueError, "blocked operation 'delete'"),
            ("argocd app sync myapp", ValueError, "blocked operation 'sync'"),
            ("argocd app rollback myapp", ValueError, "blocked operation 'rollback'"),
            ("argocd app edit myapp", ValueError, "blocked operation 'edit'"),
            ("argocd app set myapp", ValueError, "blocked operation 'set'"),
            ("argocd app unset myapp", ValueError, "blocked operation 'unset'"),
            ("argocd app patch myapp", ValueError, "blocked operation 'patch'"),
            (
                "argocd app delete-resource myapp",
                ValueError,
                "blocked operation 'delete-resource'",
            ),
            (
                "argocd app terminate-op myapp",
                ValueError,
                "blocked operation 'terminate-op'",
            ),
            ("argocd app actions myapp", ValueError, "blocked operation 'actions'"),
            # Account management (sensitive)
            (
                "argocd account generate-token",
                ValueError,
                "blocked operation 'generate-token'",
            ),
            (
                "argocd account delete-token mytoken",
                ValueError,
                "blocked operation 'delete-token'",
            ),
            (
                "argocd account update-password",
                ValueError,
                "blocked operation 'update-password'",
            ),
            (
                "argocd account bcrypt mypassword",
                ValueError,
                "blocked operation 'bcrypt'",
            ),
            # Cluster management (state-modifying)
            ("argocd cluster add mycluster", ValueError, "blocked operation 'add'"),
            ("argocd cluster rm mycluster", ValueError, "blocked operation 'rm'"),
            ("argocd cluster set mycluster", ValueError, "blocked operation 'set'"),
            (
                "argocd cluster rotate-auth mycluster",
                ValueError,
                "blocked operation 'rotate-auth'",
            ),
            # Project management (state-modifying)
            ("argocd proj create myproject", ValueError, "blocked operation 'create'"),
            ("argocd proj delete myproject", ValueError, "blocked operation 'delete'"),
            ("argocd proj edit myproject", ValueError, "blocked operation 'edit'"),
            (
                "argocd proj add-source myproject",
                ValueError,
                "blocked operation 'add-source'",
            ),
            (
                "argocd proj remove-source myproject",
                ValueError,
                "blocked operation 'remove-source'",
            ),
            (
                "argocd proj add-destination myproject",
                ValueError,
                "blocked operation 'add-destination'",
            ),
            (
                "argocd proj remove-destination myproject",
                ValueError,
                "blocked operation 'remove-destination'",
            ),
            (
                "argocd proj add-role myproject",
                ValueError,
                "blocked operation 'add-role'",
            ),
            (
                "argocd proj remove-role myproject",
                ValueError,
                "blocked operation 'remove-role'",
            ),
            # Repository management (state-modifying)
            (
                "argocd repo add https://github.com/myorg/myrepo",
                ValueError,
                "blocked operation 'add'",
            ),
            (
                "argocd repo rm https://github.com/myorg/myrepo",
                ValueError,
                "blocked operation 'rm'",
            ),
            # Context management (state-modifying when used with arguments)
            ("argocd context mycontext", ValueError, "blocked operation 'context'"),
            # Certificate and GPG management
            ("argocd cert add-tls myserver", ValueError, "blocked operation 'cert'"),
            ("argocd gpg add /path/to/key", ValueError, "blocked operation 'gpg'"),
            # Application set operations
            ("argocd appset create myappset", ValueError, "blocked operation 'appset'"),
            ("argocd appset list", ValueError, "blocked operation 'appset'"),
            # Notification operations
            (
                "argocd notifications template list",
                ValueError,
                "blocked operation 'notifications'",
            ),
            # Invalid command
            ("argocd nonexistent", ValueError, "not in the allowlist"),
            # Invalid operation for valid command
            ("argocd app invalid-operation", ValueError, "not allowed for command"),
            (
                "argocd cluster invalid-subcommand",
                ValueError,
                "not allowed for command",
            ),
            # Invalid output format
            ("argocd app list --output invalid", ValueError, "not allowed"),
            # Invalid namespace format
            (
                "argocd app list --app-namespace 'Invalid-Namespace!'",
                ValueError,
                "Invalid namespace format",
            ),
            (
                "argocd app get myapp --namespace 'bad@namespace'",
                ValueError,
                "Invalid namespace format",
            ),
            # Invalid project name format
            (
                "argocd app list --project 'Invalid@Project!'",
                ValueError,
                "Invalid project name format",
            ),
            # Invalid cluster name format
            (
                "argocd app list --cluster 'invalid cluster name'",
                ValueError,
                "Invalid cluster name format",
            ),
            # Invalid repository URL format
            (
                "argocd app list --repo 'not-a-valid-url'",
                ValueError,
                "Invalid repository URL format",
            ),
            (
                "argocd repo get 'javascript:alert(1)'",
                ValueError,
                "Invalid repository URL format",
            ),
            # Invalid log level
            (
                "argocd admin dashboard --loglevel invalid",
                ValueError,
                "Invalid log level",
            ),
            # Invalid log format
            (
                "argocd admin dashboard --logformat invalid",
                ValueError,
                "Invalid log format",
            ),
            # Unknown flags
            ("argocd app list --malicious-flag value", ValueError, "Unknown or unsafe"),
            ("argocd cluster list --evil-option", ValueError, "Unknown or unsafe"),
            # Operations that modify application state indirectly
            (
                "argocd app patch-resource myapp",
                ValueError,
                "blocked operation 'patch-resource'",
            ),
            # Admin operations that could modify state
            (
                "argocd admin app generate-spec myapp",
                ValueError,
                "operations that could modify state",
            ),
            # Invalid command structure
            ("argocd", argparse.ArgumentError, None),  # Missing command
        ],
    )
    def test_argocd_unsafe_commands(
        self, command: str, expected_exception: type, partial_error_message_content: str
    ):
        """Test that unsafe Argo CD commands are properly rejected."""
        config = BashExecutorConfig()
        with pytest.raises(expected_exception) as exc_info:
            make_command_safe(command, config=config)

        if partial_error_message_content:
            assert partial_error_message_content in str(exc_info.value)


class TestArgoCDCliEdgeCases:
    """Test edge cases and error conditions for Argo CD CLI parsing."""

    def test_argocd_with_grep_combination(self):
        """Test Argo CD commands combined with grep."""
        config = BashExecutorConfig()

        # Valid combination
        result = make_command_safe("argocd app list | grep myapp", config=config)
        assert result == "argocd app list | grep myapp"

        # Invalid - unsafe Argo CD command with grep
        with pytest.raises(ValueError):
            make_command_safe("argocd app create myapp | grep success", config=config)

    def test_argocd_commands_without_subcommands(self):
        """Test Argo CD commands that don't require subcommands."""
        config = BashExecutorConfig()

        # Version command without subcommands
        result = make_command_safe("argocd version", config=config)
        assert result == "argocd version"

        # Context command without subcommands
        result = make_command_safe("argocd context", config=config)
        assert result == "argocd context"

    def test_argocd_help_commands(self):
        """Test Argo CD help commands are allowed."""
        config = BashExecutorConfig()

        # Command-level help
        result = make_command_safe("argocd app", config=config)
        assert result == "argocd app"

        # Help flag
        result = make_command_safe("argocd app --help", config=config)
        assert result == "argocd app --help"

    def test_argocd_complex_valid_parameters(self):
        """Test Argo CD commands with complex but valid parameters."""
        config = BashExecutorConfig()

        # Complex app logs command
        complex_cmd = "argocd app logs myapp --tail 100 --filter error --container web --namespace production --timestamps"
        result = make_command_safe(complex_cmd, config=config)
        assert "argocd app logs myapp" in result
        assert "--tail 100" in result
        assert "--filter error" in result
        assert "--container web" in result
        assert "--namespace production" in result
        assert "--timestamps" in result

    def test_argocd_repository_url_validation(self):
        """Test repository URL validation."""
        config = BashExecutorConfig()

        # Valid HTTPS URL
        result = make_command_safe(
            "argocd repo get https://github.com/myorg/myrepo", config=config
        )
        assert result == "argocd repo get https://github.com/myorg/myrepo"

        # Valid HTTP URL
        result = make_command_safe(
            "argocd repo get http://git.internal.com/myrepo", config=config
        )
        assert result == "argocd repo get http://git.internal.com/myrepo"

        # SSH URL (should be allowed as it doesn't match HTTP pattern)
        result = make_command_safe(
            "argocd repo get git@github.com:myorg/myrepo.git", config=config
        )
        assert result == "argocd repo get git@github.com:myorg/myrepo.git"

    def test_argocd_resource_name_validation(self):
        """Test Argo CD resource name validation patterns."""
        config = BashExecutorConfig()

        # Valid app name (DNS-1123)
        result = make_command_safe("argocd app get my-app-123", config=config)
        assert result == "argocd app get my-app-123"

        # Valid project name
        result = make_command_safe("argocd proj get default", config=config)
        assert result == "argocd proj get default"

        # Invalid app name (uppercase)
        with pytest.raises(ValueError):
            make_command_safe("argocd app get MyApp", config=config)

        # Invalid app name (special characters)
        with pytest.raises(ValueError):
            make_command_safe("argocd app get my_app@domain", config=config)

    def test_argocd_case_sensitivity(self):
        """Test that Argo CD commands are case-sensitive where appropriate."""
        config = BashExecutorConfig()

        # Command should be lowercase
        with pytest.raises(ValueError):
            make_command_safe("argocd APP list", config=config)

        # Operations should match exactly
        with pytest.raises(ValueError):
            make_command_safe("argocd app LIST", config=config)

    def test_argocd_wait_command_conditions(self):
        """Test Argo CD wait command with different conditions."""
        config = BashExecutorConfig()

        # Valid wait conditions
        conditions = ["--health", "--sync", "--suspended", "--degraded"]
        for condition in conditions:
            result = make_command_safe(
                f"argocd app wait myapp {condition}", config=config
            )
            assert f"argocd app wait myapp {condition}" == result

    def test_argocd_server_connection_options(self):
        """Test server connection options are handled correctly."""
        config = BashExecutorConfig()

        # Valid server options
        server_opts = ["--insecure", "--grpc-web", "--plaintext"]
        for opt in server_opts:
            result = make_command_safe(
                f"argocd app list --server argocd.example.com {opt}", config=config
            )
            assert opt in result
            assert "--server argocd.example.com" in result
