import pytest
from holmes.plugins.toolsets.bash.common.stringify_command import (
    stringify_command,
    _escape_shell_args,
)
from holmes.plugins.toolsets.bash.common.parse_command import (
    KubectlGetCommand,
    KubectlDescribeCommand,
    KubectlTopCommand,
    KubectlEventsCommand,
    GrepCommand,
    Command,
)


class TestStringifyCommand:
    def test_single_kubectl_get_command(self):
        cmd = KubectlGetCommand(resource_type="pods")
        result = stringify_command([cmd])
        assert result == "kubectl get pods"

    def test_kubectl_get_with_resource_name(self):
        cmd = KubectlGetCommand(resource_type="pod", resource_name="my-pod")
        result = stringify_command([cmd])
        assert result == "kubectl get pod my-pod"

    def test_kubectl_get_with_namespace(self):
        cmd = KubectlGetCommand(resource_type="pods", namespace="kube-system")
        result = stringify_command([cmd])
        assert result == "kubectl get pods --namespace kube-system"

    def test_kubectl_get_all_namespaces(self):
        cmd = KubectlGetCommand(resource_type="pods", all_namespaces=True)
        result = stringify_command([cmd])
        assert result == "kubectl get pods --all-namespaces"

    def test_kubectl_get_with_output_format(self):
        cmd = KubectlGetCommand(resource_type="pods", output_format="yaml")
        result = stringify_command([cmd])
        assert result == "kubectl get pods --output yaml"

    def test_kubectl_get_with_selectors(self):
        cmd = KubectlGetCommand(
            resource_type="pods",
            selector="app=nginx",
            field_selector="status.phase=Running",
        )
        result = stringify_command([cmd])
        assert (
            result
            == "kubectl get pods --selector app=nginx --field-selector status.phase=Running"
        )

    def test_kubectl_get_with_show_labels(self):
        cmd = KubectlGetCommand(resource_type="pods", show_labels=True)
        result = stringify_command([cmd])
        assert result == "kubectl get pods --show-labels"

    def test_kubectl_get_complex_command(self):
        cmd = KubectlGetCommand(
            resource_type="pods",
            resource_name="my-pod",
            namespace="production",
            output_format="json",
            selector="app=nginx",
            show_labels=True,
            additional_flags=["--no-headers"],
        )
        result = stringify_command([cmd])
        expected = "kubectl get pods my-pod --namespace production --output json --selector app=nginx --show-labels --no-headers"
        assert result == expected


class TestStringifyKubectlDescribe:
    def test_basic_kubectl_describe(self):
        cmd = KubectlDescribeCommand(resource_type="pods")
        result = stringify_command([cmd])
        assert result == "kubectl describe pods"

    def test_kubectl_describe_with_resource_name(self):
        cmd = KubectlDescribeCommand(resource_type="pod", resource_name="my-pod")
        result = stringify_command([cmd])
        assert result == "kubectl describe pod my-pod"

    def test_kubectl_describe_with_namespace(self):
        cmd = KubectlDescribeCommand(resource_type="pods", namespace="kube-system")
        result = stringify_command([cmd])
        assert result == "kubectl describe pods --namespace kube-system"

    def test_kubectl_describe_show_events_false(self):
        cmd = KubectlDescribeCommand(resource_type="pods", show_events=False)
        result = stringify_command([cmd])
        assert result == "kubectl describe pods --show-events=false"

    def test_kubectl_describe_with_selector(self):
        cmd = KubectlDescribeCommand(resource_type="pods", selector="app=nginx")
        result = stringify_command([cmd])
        assert result == "kubectl describe pods --selector app=nginx"


class TestStringifyKubectlTop:
    def test_basic_kubectl_top(self):
        cmd = KubectlTopCommand(resource_type="nodes")
        result = stringify_command([cmd])
        assert result == "kubectl top nodes"

    def test_kubectl_top_with_containers(self):
        cmd = KubectlTopCommand(resource_type="pods", containers=True)
        result = stringify_command([cmd])
        assert result == "kubectl top pods --containers"

    def test_kubectl_top_with_protocol_buffers(self):
        cmd = KubectlTopCommand(resource_type="pods", use_protocol_buffers=True)
        result = stringify_command([cmd])
        assert result == "kubectl top pods --use-protocol-buffers"

    def test_kubectl_top_complex(self):
        cmd = KubectlTopCommand(
            resource_type="pods",
            namespace="kube-system",
            selector="app=nginx",
            containers=True,
            additional_flags=["--sort-by", "cpu"],
        )
        result = stringify_command([cmd])
        expected = "kubectl top pods --namespace kube-system --selector app=nginx --containers --sort-by cpu"
        assert result == expected


class TestStringifyKubectlEvents:
    def test_basic_kubectl_events(self):
        cmd = KubectlEventsCommand(resource_type="events")
        result = stringify_command([cmd])
        assert result == "kubectl events"

    def test_kubectl_events_with_for_object(self):
        cmd = KubectlEventsCommand(resource_type="events", for_object="pod/my-pod")
        result = stringify_command([cmd])
        assert result == "kubectl events --for pod/my-pod"

    def test_kubectl_events_with_types(self):
        cmd = KubectlEventsCommand(resource_type="events", types="Warning")
        result = stringify_command([cmd])
        assert result == "kubectl events --types Warning"

    def test_kubectl_events_with_watch(self):
        cmd = KubectlEventsCommand(resource_type="events", watch=True)
        result = stringify_command([cmd])
        assert result == "kubectl events --watch"

    def test_kubectl_events_complex(self):
        cmd = KubectlEventsCommand(
            resource_type="events",
            namespace="production",
            for_object="deployment/my-app",
            types="Normal,Warning",
            selector="app=nginx",
        )
        result = stringify_command([cmd])
        expected = "kubectl events --namespace production --selector app=nginx --for deployment/my-app --types Normal,Warning"
        assert result == expected


class TestStringifyGrep:
    def test_basic_grep(self):
        cmd = GrepCommand(keyword="nginx")
        result = stringify_command([cmd])
        assert result == "grep nginx"

    def test_grep_with_spaces(self):
        cmd = GrepCommand(keyword="error message")
        result = stringify_command([cmd])
        assert result == "grep 'error message'"

    def test_grep_with_special_chars(self):
        cmd = GrepCommand(keyword="error-404_test.log")
        result = stringify_command([cmd])
        assert result == "grep error-404_test.log"


class TestStringifyWithPipes:
    def test_kubectl_get_with_grep(self):
        kubectl_cmd = KubectlGetCommand(resource_type="pods")
        grep_cmd = GrepCommand(keyword="nginx")
        result = stringify_command([kubectl_cmd, grep_cmd])
        assert result == "kubectl get pods | grep nginx"

    def test_kubectl_describe_with_grep(self):
        kubectl_cmd = KubectlDescribeCommand(
            resource_type="pod", resource_name="my-pod"
        )
        grep_cmd = GrepCommand(keyword="Error")
        result = stringify_command([kubectl_cmd, grep_cmd])
        assert result == "kubectl describe pod my-pod | grep Error"

    def test_kubectl_top_with_grep(self):
        kubectl_cmd = KubectlTopCommand(resource_type="pods", containers=True)
        grep_cmd = GrepCommand(keyword="nginx")
        result = stringify_command([kubectl_cmd, grep_cmd])
        assert result == "kubectl top pods --containers | grep nginx"

    def test_kubectl_events_with_grep(self):
        kubectl_cmd = KubectlEventsCommand(
            resource_type="events", for_object="pod/my-pod"
        )
        grep_cmd = GrepCommand(keyword="Warning")
        result = stringify_command([kubectl_cmd, grep_cmd])
        assert result == "kubectl events --for pod/my-pod | grep Warning"

    def test_complex_command_with_grep(self):
        kubectl_cmd = KubectlGetCommand(
            resource_type="pods",
            namespace="kube-system",
            selector="app=nginx",
            output_format="wide",
        )
        grep_cmd = GrepCommand(keyword="Running")
        result = stringify_command([kubectl_cmd, grep_cmd])
        expected = "kubectl get pods --namespace kube-system --output wide --selector app=nginx | grep Running"
        assert result == expected


class TestEscapeShellArgs:
    def test_safe_args_no_escaping(self):
        args = ["kubectl", "get", "pods", "--namespace", "default"]
        result = _escape_shell_args(args)
        assert result == ["kubectl", "get", "pods", "--namespace", "default"]

    def test_args_with_spaces_escaped(self):
        args = ["grep", "error message"]
        result = _escape_shell_args(args)
        assert result == ["grep", "'error message'"]

    def test_args_with_single_quotes_escaped(self):
        args = ["grep", "can't connect"]
        result = _escape_shell_args(args)
        assert result == ["grep", "'can'\"'\"'t connect'"]

    def test_flags_not_escaped(self):
        args = ["--namespace", "--all-namespaces", "-n", "-A"]
        result = _escape_shell_args(args)
        assert result == ["--namespace", "--all-namespaces", "-n", "-A"]

    def test_safe_characters_not_escaped(self):
        args = ["error-404_test.log", "nginx-1.2.3"]
        result = _escape_shell_args(args)
        assert result == ["error-404_test.log", "nginx-1.2.3"]

    def test_special_characters_escaped(self):
        args = ["echo", "hello;rm -rf /"]
        result = _escape_shell_args(args)
        assert result == ["echo", "'hello;rm -rf /'"]


class TestStringifyErrorCases:
    def test_empty_commands_raises_error(self):
        with pytest.raises(ValueError, match="No commands provided"):
            stringify_command([])

    def test_unsupported_command_type_raises_error(self):
        class UnsupportedCommand(Command):
            prefix: str = "unsupported"

        cmd = UnsupportedCommand(prefix="unsupported")
        with pytest.raises(
            ValueError, match="Unsupported command type: UnsupportedCommand"
        ):
            stringify_command([cmd])


class TestRoundTripCompatibility:
    """Test that parse -> stringify produces equivalent commands."""

    def test_kubectl_get_round_trip(self):
        from holmes.plugins.toolsets.bash.common.parse_command import parse_command

        original = "kubectl get pods --namespace kube-system --output yaml"
        parsed = parse_command(original)
        reconstructed = stringify_command(parsed)

        # Should produce functionally equivalent command
        assert "kubectl get pods" in reconstructed
        assert "--namespace kube-system" in reconstructed
        assert "--output yaml" in reconstructed

    def test_kubectl_with_grep_round_trip(self):
        from holmes.plugins.toolsets.bash.common.parse_command import parse_command

        original = "kubectl describe pod my-pod | grep Error"
        parsed = parse_command(original)
        reconstructed = stringify_command(parsed)

        assert "kubectl describe pod my-pod" in reconstructed
        assert "grep Error" in reconstructed
        assert "|" in reconstructed
