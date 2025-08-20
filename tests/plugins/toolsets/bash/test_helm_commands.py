"""
Tests for Helm CLI command parsing, validation, and stringification.

This module tests the Helm CLI integration in the bash toolset, ensuring:
1. Safe Helm commands are allowed and properly parsed
2. Unsafe Helm commands are blocked with appropriate error messages
3. Helm command options are validated correctly
4. Commands are properly stringified back to safe command strings
"""

import argparse
import pytest
from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.parse_command import make_command_safe


class TestHelmCliSafeCommands:
    """Test Helm CLI safe commands that should be allowed."""

    @pytest.mark.parametrize(
        "input_command,expected_output",
        [
            # Release management (read-only)
            ("helm list", "helm list"),
            ("helm ls", "helm ls"),
            ("helm list --all-namespaces", "helm list --all-namespaces"),
            ("helm list -A", "helm list -A"),
            ("helm list --namespace production", "helm list --namespace production"),
            ("helm list -n production", "helm list -n production"),
            ("helm list --output json", "helm list --output json"),
            ("helm list -o json", "helm list -o json"),
            ("helm list --output table", "helm list --output table"),
            ("helm list --output yaml", "helm list --output yaml"),
            ("helm list --short", "helm list --short"),
            ("helm list -q", "helm list -q"),
            ("helm list --date", "helm list --date"),
            ("helm list --deployed", "helm list --deployed"),
            ("helm list --failed", "helm list --failed"),
            ("helm list --pending", "helm list --pending"),
            ("helm list --superseded", "helm list --superseded"),
            ("helm list --uninstalled", "helm list --uninstalled"),
            ("helm list --filter nginx", "helm list --filter nginx"),
            ("helm list --selector app=web", "helm list --selector app=web"),
            ("helm list -l app=web", "helm list -l app=web"),
            ("helm list --max 10", "helm list --max 10"),
            ("helm list --offset 5", "helm list --offset 5"),
            ("helm list --reverse", "helm list --reverse"),
            ("helm list -r", "helm list -r"),
            # Get commands
            ("helm get all myrelease", "helm get all myrelease"),
            ("helm get hooks myrelease", "helm get hooks myrelease"),
            ("helm get manifest myrelease", "helm get manifest myrelease"),
            ("helm get notes myrelease", "helm get notes myrelease"),
            ("helm get values myrelease", "helm get values myrelease"),
            ("helm get metadata myrelease", "helm get metadata myrelease"),
            (
                "helm get values myrelease --output json",
                "helm get values myrelease --output json",
            ),
            ("helm get values myrelease -o yaml", "helm get values myrelease -o yaml"),
            (
                "helm get values myrelease --revision 2",
                "helm get values myrelease --revision 2",
            ),
            (
                "helm get manifest myrelease --revision 1",
                "helm get manifest myrelease --revision 1",
            ),
            (
                "helm get all myrelease --namespace production",
                "helm get all myrelease --namespace production",
            ),
            (
                "helm get all myrelease -n production",
                "helm get all myrelease -n production",
            ),
            # Status commands
            ("helm status myrelease", "helm status myrelease"),
            (
                "helm status myrelease --output json",
                "helm status myrelease --output json",
            ),
            ("helm status myrelease -o yaml", "helm status myrelease -o yaml"),
            (
                "helm status myrelease --namespace production",
                "helm status myrelease --namespace production",
            ),
            (
                "helm status myrelease -n production",
                "helm status myrelease -n production",
            ),
            (
                "helm status myrelease --revision 2",
                "helm status myrelease --revision 2",
            ),
            # History commands
            ("helm history myrelease", "helm history myrelease"),
            (
                "helm history myrelease --output json",
                "helm history myrelease --output json",
            ),
            ("helm history myrelease -o table", "helm history myrelease -o table"),
            (
                "helm history myrelease --namespace production",
                "helm history myrelease --namespace production",
            ),
            (
                "helm history myrelease -n production",
                "helm history myrelease -n production",
            ),
            ("helm history myrelease --max 5", "helm history myrelease --max 5"),
            # Show commands
            ("helm show chart nginx", "helm show chart nginx"),
            ("helm show values nginx", "helm show values nginx"),
            ("helm show readme nginx", "helm show readme nginx"),
            ("helm show all nginx", "helm show all nginx"),
            ("helm show crds nginx", "helm show crds nginx"),
            ("helm show chart stable/nginx", "helm show chart stable/nginx"),
            (
                "helm show values bitnami/nginx --version 1.0.0",
                "helm show values bitnami/nginx --version 1.0.0",
            ),
            ("helm show chart ./mychart", "helm show chart ./mychart"),
            (
                "helm show values https://example.com/charts/nginx-1.0.0.tgz",
                "helm show values https://example.com/charts/nginx-1.0.0.tgz",
            ),
            # Search commands
            ("helm search repo nginx", "helm search repo nginx"),
            (
                "helm search repo nginx --max-col-width 50",
                "helm search repo nginx --max-col-width 50",
            ),
            ("helm search repo nginx --devel", "helm search repo nginx --devel"),
            (
                "helm search repo nginx --version 1.0.0",
                "helm search repo nginx --version 1.0.0",
            ),
            ("helm search repo nginx --versions", "helm search repo nginx --versions"),
            ("helm search repo nginx --regexp", "helm search repo nginx --regexp"),
            ("helm search repo nginx -r", "helm search repo nginx -r"),
            (
                "helm search repo nginx --output json",
                "helm search repo nginx --output json",
            ),
            ("helm search repo nginx -o table", "helm search repo nginx -o table"),
            # Template commands (dry-run rendering)
            ("helm template myrelease nginx", "helm template myrelease nginx"),
            (
                "helm template myrelease nginx --dry-run",
                "helm template myrelease nginx --dry-run",
            ),
            (
                "helm template myrelease nginx --namespace production",
                "helm template myrelease nginx --namespace production",
            ),
            (
                "helm template myrelease nginx -n production",
                "helm template myrelease nginx -n production",
            ),
            (
                "helm template myrelease nginx --values values.yaml",
                "helm template myrelease nginx --values values.yaml",
            ),
            (
                "helm template myrelease nginx -f values.yaml",
                "helm template myrelease nginx -f values.yaml",
            ),
            (
                "helm template myrelease nginx --set image.tag=v2.0",
                "helm template myrelease nginx --set image.tag=v2.0",
            ),
            (
                "helm template myrelease nginx --set-string nodeSelector.zone=us-east-1",
                "helm template myrelease nginx --set-string nodeSelector.zone=us-east-1",
            ),
            (
                "helm template myrelease nginx --set-file config=config.yaml",
                "helm template myrelease nginx --set-file config=config.yaml",
            ),
            (
                "helm template myrelease nginx --show-only templates/deployment.yaml",
                "helm template myrelease nginx --show-only templates/deployment.yaml",
            ),
            (
                "helm template myrelease nginx --include-crds",
                "helm template myrelease nginx --include-crds",
            ),
            (
                "helm template myrelease nginx --skip-crds",
                "helm template myrelease nginx --skip-crds",
            ),
            (
                "helm template myrelease nginx --skip-tests",
                "helm template myrelease nginx --skip-tests",
            ),
            (
                "helm template myrelease nginx --no-hooks",
                "helm template myrelease nginx --no-hooks",
            ),
            (
                "helm template myrelease nginx --is-upgrade",
                "helm template myrelease nginx --is-upgrade",
            ),
            (
                "helm template myrelease nginx --kube-version v1.25.0",
                "helm template myrelease nginx --kube-version v1.25.0",
            ),
            (
                "helm template myrelease nginx --api-versions apps/v1",
                "helm template myrelease nginx --api-versions apps/v1",
            ),
            (
                "helm template myrelease nginx --output-dir ./output",
                "helm template myrelease nginx --output-dir ./output",
            ),
            (
                "helm template myrelease nginx --validate",
                "helm template myrelease nginx --validate",
            ),
            # Lint commands
            ("helm lint ./mychart", "helm lint ./mychart"),
            ("helm lint ./mychart --strict", "helm lint ./mychart --strict"),
            (
                "helm lint ./mychart --values values.yaml",
                "helm lint ./mychart --values values.yaml",
            ),
            (
                "helm lint ./mychart -f values.yaml",
                "helm lint ./mychart -f values.yaml",
            ),
            (
                "helm lint ./mychart --set image.tag=v2.0",
                "helm lint ./mychart --set image.tag=v2.0",
            ),
            (
                "helm lint ./mychart --with-subcharts",
                "helm lint ./mychart --with-subcharts",
            ),
            ("helm lint ./mychart --quiet", "helm lint ./mychart --quiet"),
            # Verify commands
            ("helm verify mychart-1.0.0.tgz", "helm verify mychart-1.0.0.tgz"),
            (
                "helm verify mychart-1.0.0.tgz --keyring ~/.gnupg/pubring.gpg",
                "helm verify mychart-1.0.0.tgz --keyring ~/.gnupg/pubring.gpg",
            ),
            # Dependency commands (read-only)
            ("helm dependency list ./mychart", "helm dependency list ./mychart"),
            (
                "helm dependency build ./mychart --dry-run",
                "helm dependency build ./mychart --dry-run",
            ),
            # Repository commands (read-only)
            ("helm repo list", "helm repo list"),
            ("helm repo index . --dry-run", "helm repo index . --dry-run"),
            ("helm repo index charts --dry-run", "helm repo index charts --dry-run"),
            (
                "helm repo index charts --url https://example.com/charts --dry-run",
                "helm repo index charts --url https://example.com/charts --dry-run",
            ),
            # Plugin commands (read-only)
            ("helm plugin list", "helm plugin list"),
            # Help and information
            ("helm help", "helm help"),
            ("helm version", "helm version"),
            ("helm version --short", "helm version --short"),
            ("helm version --client", "helm version --client"),
            (
                "helm version --template '{{.Version}}'",
                "helm version --template '{{.Version}}'",
            ),
            ("helm env", "helm env"),
            # Completion
            ("helm completion bash", "helm completion bash"),
            ("helm completion zsh", "helm completion zsh"),
            ("helm completion fish", "helm completion fish"),
            ("helm completion powershell", "helm completion powershell"),
            # Commands with Kubernetes context options
            (
                "helm list --kube-context production",
                "helm list --kube-context production",
            ),
            (
                "helm list --kubeconfig ~/.kube/config",
                "helm list --kubeconfig ~/.kube/config",
            ),
            (
                "helm list --kube-apiserver https://k8s.example.com",
                "helm list --kube-apiserver https://k8s.example.com",
            ),
            ("helm list --kube-token mytoken", "helm list --kube-token mytoken"),
            ("helm list --kube-as-user admin", "helm list --kube-as-user admin"),
            (
                "helm list --kube-as-group system:masters",
                "helm list --kube-as-group system:masters",
            ),
            # Commands with debug and logging options
            ("helm list --debug", "helm list --debug"),
            (
                "helm template myrelease nginx --debug",
                "helm template myrelease nginx --debug",
            ),
            ("helm lint ./mychart --debug", "helm lint ./mychart --debug"),
            # Commands with repository configuration
            (
                "helm list --repository-config ~/.config/helm/repositories.yaml",
                "helm list --repository-config ~/.config/helm/repositories.yaml",
            ),
            (
                "helm list --repository-cache ~/.cache/helm/repository",
                "helm list --repository-cache ~/.cache/helm/repository",
            ),
            (
                "helm search repo nginx --repository-config ~/.config/helm/repositories.yaml",
                "helm search repo nginx --repository-config ~/.config/helm/repositories.yaml",
            ),
            # Complex template commands with multiple options
            (
                "helm template myrelease bitnami/nginx --namespace production --values prod-values.yaml --set replicas=3 --set-string image.tag=1.21-alpine --include-crds --validate",
                "helm template myrelease bitnami/nginx --namespace production --values prod-values.yaml --set replicas=3 --set-string image.tag=1.21-alpine --include-crds --validate",
            ),
            # Commands with time formatting
            (
                "helm list --time-format '2006-01-02 15:04:05'",
                "helm list --time-format '2006-01-02 15:04:05'",
            ),
            (
                "helm history myrelease --time-format RFC3339",
                "helm history myrelease --time-format RFC3339",
            ),
            # Diff commands (if diff plugin available)
            ("helm diff revision myrelease 1 2", "helm diff revision myrelease 1 2"),
            ("helm diff upgrade myrelease nginx", "helm diff upgrade myrelease nginx"),
            # Help for subcommands
            ("helm list --help", "helm list --help"),
            ("helm get --help", "helm get --help"),
            ("helm show --help", "helm show --help"),
            ("helm template --help", "helm template --help"),
        ],
    )
    def test_helm_safe_commands(self, input_command: str, expected_output: str):
        """Test that safe Helm commands are parsed and stringified correctly."""
        config = BashExecutorConfig()
        output_command = make_command_safe(input_command, config=config)
        assert output_command == expected_output


class TestHelmCliUnsafeCommands:
    """Test Helm CLI unsafe commands that should be rejected."""

    @pytest.mark.parametrize(
        "command,expected_exception,partial_error_message_content",
        [
            # Release lifecycle operations
            ("helm install myrelease nginx", ValueError, "blocked operation 'install'"),
            ("helm upgrade myrelease nginx", ValueError, "blocked operation 'upgrade'"),
            ("helm uninstall myrelease", ValueError, "blocked operation 'uninstall'"),
            ("helm delete myrelease", ValueError, "blocked operation 'delete'"),
            ("helm rollback myrelease 1", ValueError, "blocked operation 'rollback'"),
            ("helm test myrelease", ValueError, "blocked operation 'test'"),
            # Repository management
            (
                "helm repo add stable https://charts.helm.sh/stable",
                ValueError,
                "blocked operation 'repo add'",
            ),
            ("helm repo remove stable", ValueError, "blocked operation 'repo remove'"),
            ("helm repo rm stable", ValueError, "blocked operation 'repo rm'"),
            ("helm repo update", ValueError, "blocked operation 'repo update'"),
            ("helm repo index charts", ValueError, "blocked operation 'repo index'"),
            # Chart packaging and publishing
            ("helm create mychart", ValueError, "blocked operation 'create'"),
            ("helm package mychart", ValueError, "blocked operation 'package'"),
            (
                "helm push mychart.tgz oci://registry.example.com",
                ValueError,
                "blocked operation 'push'",
            ),
            ("helm pull bitnami/nginx", ValueError, "blocked operation 'pull'"),
            ("helm fetch bitnami/nginx", ValueError, "blocked operation 'fetch'"),
            (
                "helm dependency update ./mychart",
                ValueError,
                "blocked operation 'dependency update'",
            ),
            (
                "helm dependency build ./mychart",
                ValueError,
                "blocked operation 'dependency build'",
            ),
            # Plugin management
            (
                "helm plugin install https://github.com/example/helm-plugin",
                ValueError,
                "blocked operation 'plugin install'",
            ),
            (
                "helm plugin uninstall myplugin",
                ValueError,
                "blocked operation 'plugin uninstall'",
            ),
            (
                "helm plugin update myplugin",
                ValueError,
                "blocked operation 'plugin update'",
            ),
            # Registry operations
            (
                "helm registry login registry.example.com",
                ValueError,
                "blocked operation 'registry login'",
            ),
            (
                "helm registry logout registry.example.com",
                ValueError,
                "blocked operation 'registry logout'",
            ),
            # Environment modification
            ("helm env set HELM_DRIVER sql", ValueError, "blocked operation 'env set'"),
            ("helm env unset HELM_DRIVER", ValueError, "blocked operation 'env unset'"),
            # Configuration modification
            ("helm config list", ValueError, "blocked operation 'config'"),
            ("helm config set driver sql", ValueError, "blocked operation 'config'"),
            # Mapkubeapis operations
            (
                "helm mapkubeapis myrelease",
                ValueError,
                "blocked operation 'mapkubeapis'",
            ),
            # Invalid command
            ("helm nonexistent", ValueError, "not in the allowlist"),
            # Invalid subcommand for valid command
            ("helm get invalid myrelease", ValueError, "not allowed"),
            ("helm show invalid nginx", ValueError, "not allowed"),
            ("helm repo invalid", ValueError, "not in the allowlist"),
            # Invalid output format
            ("helm list --output invalid", ValueError, "not allowed"),
            ("helm get values myrelease --output xml", ValueError, "not allowed"),
            # Invalid namespace format
            (
                "helm list --namespace 'Invalid-Namespace!'",
                ValueError,
                "Invalid Helm namespace format",
            ),
            (
                "helm get all myrelease --namespace 'bad@namespace'",
                ValueError,
                "Invalid Helm namespace format",
            ),
            # Invalid release name format
            (
                "helm template 'Invalid-Release-Name!' nginx",
                ValueError,
                "Invalid Helm release name format",
            ),
            (
                "helm template MyRelease nginx",
                ValueError,
                "Invalid Helm release name format",
            ),
            # Invalid repository URL format
            (
                "helm repo index charts --url ftp://invalid.com",
                ValueError,
                "Invalid Helm repository URL format",
            ),
            (
                "helm repo index charts --url javascript:alert(1)",
                ValueError,
                "Invalid Helm repository URL format",
            ),
            # Unknown flags
            ("helm list --malicious-flag value", ValueError, "Unknown or unsafe"),
            (
                "helm template myrelease nginx --evil-option",
                ValueError,
                "Unknown or unsafe",
            ),
            # Operations that could modify cluster state
            ("helm template myrelease nginx --atomic", ValueError, "Unknown or unsafe"),
            ("helm template myrelease nginx --wait", ValueError, "Unknown or unsafe"),
            ("helm template myrelease nginx --force", ValueError, "Unknown or unsafe"),
            # Invalid command structure
            ("helm", argparse.ArgumentError, None),  # Missing command
        ],
    )
    def test_helm_unsafe_commands(
        self, command: str, expected_exception: type, partial_error_message_content: str
    ):
        """Test that unsafe Helm commands are properly rejected."""
        config = BashExecutorConfig()
        with pytest.raises(expected_exception) as exc_info:
            make_command_safe(command, config=config)

        if partial_error_message_content:
            assert partial_error_message_content in str(exc_info.value)


class TestHelmCliEdgeCases:
    """Test edge cases and error conditions for Helm CLI parsing."""

    def test_helm_with_grep_combination(self):
        """Test Helm commands combined with grep."""
        config = BashExecutorConfig()

        # Valid combination
        result = make_command_safe("helm list | grep nginx", config=config)
        assert result == "helm list | grep nginx"

        # Invalid - unsafe Helm command with grep
        with pytest.raises(ValueError):
            make_command_safe(
                "helm install myrelease nginx | grep success", config=config
            )

    def test_helm_commands_without_subcommands(self):
        """Test Helm commands that can work without subcommands."""
        config = BashExecutorConfig()

        # Commands that work without subcommands
        result = make_command_safe("helm version", config=config)
        assert result == "helm version"

        result = make_command_safe("helm help", config=config)
        assert result == "helm help"

        result = make_command_safe("helm env", config=config)
        assert result == "helm env"

    def test_helm_help_commands(self):
        """Test Helm help commands are allowed."""
        config = BashExecutorConfig()

        # Global help
        result = make_command_safe("helm --help", config=config)
        assert result == "helm --help"

        # Command help
        result = make_command_safe("helm list --help", config=config)
        assert result == "helm list --help"

        # Subcommand help
        result = make_command_safe("helm get --help", config=config)
        assert result == "helm get --help"

    def test_helm_complex_valid_parameters(self):
        """Test Helm commands with complex but valid parameters."""
        config = BashExecutorConfig()

        # Complex template command
        complex_cmd = "helm template myrelease bitnami/nginx --namespace production --values values.yaml --set replicas=3 --set-string image.tag=1.21 --include-crds --validate --debug"
        result = make_command_safe(complex_cmd, config=config)
        assert "helm template myrelease bitnami/nginx" in result
        assert "--namespace production" in result
        assert "--values values.yaml" in result
        assert "--set replicas=3" in result
        assert "--set-string image.tag=1.21" in result
        assert "--include-crds" in result
        assert "--validate" in result
        assert "--debug" in result

    def test_helm_chart_reference_validation(self):
        """Test Helm chart reference validation."""
        config = BashExecutorConfig()

        # Valid chart references
        valid_charts = [
            "nginx",
            "stable/nginx",
            "bitnami/nginx",
            "./mychart",
            "../charts/mychart",
            "/absolute/path/to/chart",
            "https://example.com/charts/nginx-1.0.0.tgz",
        ]

        for chart in valid_charts:
            result = make_command_safe(f"helm show chart {chart}", config=config)
            assert f"helm show chart {chart}" == result

    def test_helm_release_name_validation(self):
        """Test Helm release name validation patterns."""
        config = BashExecutorConfig()

        # Valid release names (DNS-1123 subdomain)
        valid_names = [
            "myrelease",
            "my-release",
            "release123",
            "web-server",
            "a",  # Single character
            "a" * 63,  # Maximum length
        ]

        for name in valid_names:
            result = make_command_safe(f"helm status {name}", config=config)
            assert f"helm status {name}" == result

        # Invalid release names
        invalid_names = [
            "MyRelease",  # Uppercase
            "my_release",  # Underscore
            "-myrelease",  # Starts with dash
            "myrelease-",  # Ends with dash
            "my.release",  # Contains dot
            "a" * 64,  # Too long
        ]

        for name in invalid_names:
            with pytest.raises(ValueError):
                make_command_safe(f"helm template {name} nginx", config=config)

    def test_helm_namespace_validation(self):
        """Test Helm namespace validation."""
        config = BashExecutorConfig()

        # Valid namespaces
        valid_namespaces = [
            "default",
            "kube-system",
            "production",
            "staging-env",
            "ns123",
        ]

        for namespace in valid_namespaces:
            result = make_command_safe(
                f"helm list --namespace {namespace}", config=config
            )
            assert f"helm list --namespace {namespace}" == result

        # Invalid namespaces
        invalid_namespaces = [
            "Invalid-Namespace!",
            "namespace_with_underscores",
            "UPPERCASE",
            "-invalid",
            "invalid-",
        ]

        for namespace in invalid_namespaces:
            with pytest.raises(ValueError):
                make_command_safe(f"helm list --namespace {namespace}", config=config)

    def test_helm_get_subcommand_validation(self):
        """Test Helm get subcommand validation."""
        config = BashExecutorConfig()

        # Valid get subcommands
        valid_subcommands = ["all", "hooks", "manifest", "notes", "values", "metadata"]

        for subcmd in valid_subcommands:
            result = make_command_safe(f"helm get {subcmd} myrelease", config=config)
            assert f"helm get {subcmd} myrelease" == result

        # Invalid get subcommand
        with pytest.raises(ValueError):
            make_command_safe("helm get invalid myrelease", config=config)

    def test_helm_show_subcommand_validation(self):
        """Test Helm show subcommand validation."""
        config = BashExecutorConfig()

        # Valid show subcommands
        valid_subcommands = ["all", "chart", "readme", "values", "crds"]

        for subcmd in valid_subcommands:
            result = make_command_safe(f"helm show {subcmd} nginx", config=config)
            assert f"helm show {subcmd} nginx" == result

        # Invalid show subcommand
        with pytest.raises(ValueError):
            make_command_safe("helm show invalid nginx", config=config)

    def test_helm_case_sensitivity(self):
        """Test that Helm commands are case-sensitive where appropriate."""
        config = BashExecutorConfig()

        # Commands should be lowercase
        with pytest.raises(ValueError):
            make_command_safe("helm LIST", config=config)

        # Release names should be lowercase (DNS-1123)
        with pytest.raises(ValueError):
            make_command_safe("helm status MyRelease", config=config)

    def test_helm_repository_url_validation(self):
        """Test Helm repository URL validation."""
        config = BashExecutorConfig()

        # Valid URLs (for repo index command with --url flag)
        valid_urls = [
            "https://charts.helm.sh/stable",
            "https://kubernetes-charts.storage.googleapis.com",
            "http://internal.registry.com/charts",
            "https://example.com:8080/charts",
        ]

        for url in valid_urls:
            result = make_command_safe(
                f"helm repo index charts --url {url} --dry-run", config=config
            )
            assert f"--url {url}" in result

        # Invalid URLs
        invalid_urls = [
            "ftp://charts.example.com",
            "javascript:alert(1)",
            "file:///etc/passwd",
            "not-a-url",
        ]

        for url in invalid_urls:
            with pytest.raises(ValueError):
                make_command_safe(
                    f"helm repo index charts --url {url} --dry-run", config=config
                )
