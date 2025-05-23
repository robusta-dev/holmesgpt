import pytest
from holmes.plugins.toolsets.bash.common.parse_command import (
    parse_command, 
    KubectlGetCommand, 
    KubectlDescribeCommand,
    KubectlTopCommand,
    KubectlEventsCommand,
    BaseKubectlCommand,
    Command,
    GrepCommand,
    validate_kubectl_command,
    validate_kubectl_get_command,
    validate_kubectl_describe_command,
    validate_kubectl_top_command,
    validate_kubectl_events_command,
    validate_grep_command
)


class TestParseCommand:
    
    def test_basic_kubectl_get_pods(self):
        result = parse_command("kubectl get pods")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pods"
        assert result[0].resource_name is None
        assert result[0].namespace is None
        assert result[0].all_namespaces is False
        
    def test_kubectl_get_with_resource_name(self):
        result = parse_command("kubectl get pod my-pod")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pod"
        assert result[0].resource_name == "my-pod"
        
    def test_kubectl_get_with_namespace_short_flag(self):
        result = parse_command("kubectl get pods -n kube-system")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pods"
        assert result[0].namespace == "kube-system"
        
    def test_kubectl_get_with_namespace_long_flag(self):
        result = parse_command("kubectl get pods --namespace default")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pods"
        assert result[0].namespace == "default"
        
    def test_kubectl_get_all_namespaces_short(self):
        result = parse_command("kubectl get pods -A")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pods"
        assert result[0].all_namespaces is True
        
    def test_kubectl_get_all_namespaces_long(self):
        result = parse_command("kubectl get pods --all-namespaces")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pods"
        assert result[0].all_namespaces is True
        
    def test_kubectl_get_with_output_format_short(self):
        result = parse_command("kubectl get pods -o yaml")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pods"
        assert result[0].output_format == "yaml"
        
    def test_kubectl_get_with_output_format_long(self):
        result = parse_command("kubectl get pods --output json")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pods"
        assert result[0].output_format == "json"
        
    def test_kubectl_get_with_label_selector_short(self):
        result = parse_command("kubectl get pods -l app=nginx")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pods"
        assert result[0].selector == "app=nginx"
        
    def test_kubectl_get_with_label_selector_long(self):
        result = parse_command("kubectl get pods --selector env=prod")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pods"
        assert result[0].selector == "env=prod"
        
    def test_kubectl_get_with_field_selector_equals(self):
        result = parse_command("kubectl get pods --field-selector=status.phase=Running")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pods"
        assert result[0].field_selector == "status.phase=Running"
        
    def test_kubectl_get_with_field_selector_space(self):
        result = parse_command("kubectl get pods --field-selector status.phase=Failed")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pods"
        assert result[0].field_selector == "status.phase=Failed"
        
    def test_kubectl_get_show_labels(self):
        result = parse_command("kubectl get pods --show-labels")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pods"
        assert result[0].show_labels is True
        
    def test_kubectl_get_complex_command(self):
        result = parse_command("kubectl get pods my-pod -n production -o yaml --show-labels")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pods"
        assert result[0].resource_name == "my-pod"
        assert result[0].namespace == "production"
        assert result[0].output_format == "yaml"
        assert result[0].show_labels is True
        
    def test_kubectl_get_with_unknown_flags_blocked(self):
        with pytest.raises(ValueError, match="Unsafe additional flag"):
            parse_command("kubectl get pods --unknown-flag --another-flag")
        
    def test_kubectl_get_multiple_resources(self):
        result = parse_command("kubectl get pods services deployments")
        assert len(result) == 1
        assert isinstance(result[0], KubectlGetCommand)
        assert result[0].resource_type == "pods"
        assert result[0].resource_name == "services"
        assert "deployments" in result[0].additional_flags
        
    def test_non_kubectl_command_raises_error(self):
        with pytest.raises(ValueError, match="Unsupported command"):
            parse_command("docker ps")
            
    def test_kubectl_non_supported_command_raises_error(self):
        with pytest.raises(ValueError, match="Unsupported command"):
            parse_command("kubectl apply -f file.yaml")
            
    def test_kubectl_get_without_resource_raises_error(self):
        with pytest.raises(ValueError, match="Resource type is required for kubectl get command"):
            parse_command("kubectl get")
            
    def test_kubectl_get_with_only_flags_raises_error(self):
        with pytest.raises(ValueError, match="Resource type is required for kubectl get command"):
            parse_command("kubectl get -n default")
            
    def test_empty_command_raises_error(self):
        with pytest.raises(ValueError, match="Unsupported command"):
            parse_command("")
            
    def test_single_word_command_raises_error(self):
        with pytest.raises(ValueError, match="Unsupported command"):
            parse_command("kubectl")


class TestKubectlDescribeCommand:
    
    def test_basic_kubectl_describe_pods(self):
        result = parse_command("kubectl describe pods")
        assert len(result) == 1
        assert isinstance(result[0], KubectlDescribeCommand)
        assert result[0].resource_type == "pods"
        assert result[0].resource_name is None
        assert result[0].namespace is None
        assert result[0].show_events is True
        
    def test_kubectl_describe_with_resource_name(self):
        result = parse_command("kubectl describe pod my-pod")
        assert len(result) == 1
        assert isinstance(result[0], KubectlDescribeCommand)
        assert result[0].resource_type == "pod"
        assert result[0].resource_name == "my-pod"
        
    def test_kubectl_describe_with_namespace(self):
        result = parse_command("kubectl describe pods -n kube-system")
        assert len(result) == 1
        assert isinstance(result[0], KubectlDescribeCommand)
        assert result[0].resource_type == "pods"
        assert result[0].namespace == "kube-system"
        
    def test_kubectl_describe_all_namespaces(self):
        result = parse_command("kubectl describe pods -A")
        assert len(result) == 1
        assert isinstance(result[0], KubectlDescribeCommand)
        assert result[0].resource_type == "pods"
        assert result[0].all_namespaces is True
        
    def test_kubectl_describe_with_selector(self):
        result = parse_command("kubectl describe pods -l app=nginx")
        assert len(result) == 1
        assert isinstance(result[0], KubectlDescribeCommand)
        assert result[0].resource_type == "pods"
        assert result[0].selector == "app=nginx"
        
    def test_kubectl_describe_show_events_false(self):
        result = parse_command("kubectl describe pods --show-events=false")
        assert len(result) == 1
        assert isinstance(result[0], KubectlDescribeCommand)
        assert result[0].resource_type == "pods"
        assert result[0].show_events is False
        
    def test_kubectl_describe_complex_command(self):
        result = parse_command("kubectl describe deployment my-app -n production -l version=v1")
        assert len(result) == 1
        assert isinstance(result[0], KubectlDescribeCommand)
        assert result[0].resource_type == "deployment"
        assert result[0].resource_name == "my-app"
        assert result[0].namespace == "production"
        assert result[0].selector == "version=v1"


class TestKubectlTopCommand:
    
    def test_basic_kubectl_top_nodes(self):
        result = parse_command("kubectl top nodes")
        assert len(result) == 1
        assert isinstance(result[0], KubectlTopCommand)
        assert result[0].resource_type == "nodes"
        assert result[0].resource_name is None
        assert result[0].containers is False
        
    def test_kubectl_top_pods_with_containers(self):
        result = parse_command("kubectl top pods --containers")
        assert len(result) == 1
        assert isinstance(result[0], KubectlTopCommand)
        assert result[0].resource_type == "pods"
        assert result[0].containers is True
        
    def test_kubectl_top_with_namespace(self):
        result = parse_command("kubectl top pods -n kube-system")
        assert len(result) == 1
        assert isinstance(result[0], KubectlTopCommand)
        assert result[0].resource_type == "pods"
        assert result[0].namespace == "kube-system"
        
    def test_kubectl_top_with_selector(self):
        result = parse_command("kubectl top pods -l app=nginx")
        assert len(result) == 1
        assert isinstance(result[0], KubectlTopCommand)
        assert result[0].resource_type == "pods"
        assert result[0].selector == "app=nginx"
        
    def test_kubectl_top_specific_pod(self):
        result = parse_command("kubectl top pod my-pod")
        assert len(result) == 1
        assert isinstance(result[0], KubectlTopCommand)
        assert result[0].resource_type == "pod"
        assert result[0].resource_name == "my-pod"


class TestKubectlEventsCommand:
    
    def test_basic_kubectl_events(self):
        result = parse_command("kubectl events")
        assert len(result) == 1
        assert isinstance(result[0], KubectlEventsCommand)
        assert result[0].resource_type == "events"
        assert result[0].for_object is None
        assert result[0].watch is False
        
    def test_kubectl_events_with_namespace(self):
        result = parse_command("kubectl events -n kube-system")
        assert len(result) == 1
        assert isinstance(result[0], KubectlEventsCommand)
        assert result[0].resource_type == "events"
        assert result[0].namespace == "kube-system"
        
    def test_kubectl_events_for_object(self):
        result = parse_command("kubectl events --for pod/my-pod")
        assert len(result) == 1
        assert isinstance(result[0], KubectlEventsCommand)
        assert result[0].resource_type == "events"
        assert result[0].for_object == "pod/my-pod"
        
    def test_kubectl_events_with_types(self):
        result = parse_command("kubectl events --types Warning")
        assert len(result) == 1
        assert isinstance(result[0], KubectlEventsCommand)
        assert result[0].resource_type == "events"
        assert result[0].types == "Warning"
        
    def test_kubectl_events_complex_command(self):
        result = parse_command("kubectl events -n production --for deployment/my-app --types Normal,Warning")
        assert len(result) == 1
        assert isinstance(result[0], KubectlEventsCommand)
        assert result[0].resource_type == "events"
        assert result[0].namespace == "production"
        assert result[0].for_object == "deployment/my-app"
        assert result[0].types == "Normal,Warning"


class TestGrepCommand:
    
    def test_kubectl_get_with_grep(self):
        result = parse_command("kubectl get pods | grep nginx")
        assert len(result) == 2
        assert isinstance(result[0], KubectlGetCommand)
        assert isinstance(result[1], GrepCommand)
        assert result[0].resource_type == "pods"
        assert result[1].keyword == "nginx"
        
    def test_kubectl_describe_with_grep(self):
        result = parse_command("kubectl describe pod my-pod | grep Error")
        assert len(result) == 2
        assert isinstance(result[0], KubectlDescribeCommand)
        assert isinstance(result[1], GrepCommand)
        assert result[0].resource_type == "pod"
        assert result[0].resource_name == "my-pod"
        assert result[1].keyword == "Error"
        
    def test_grep_with_quoted_keyword(self):
        result = parse_command('kubectl get pods | grep "error message"')
        assert len(result) == 2
        assert isinstance(result[1], GrepCommand)
        assert result[1].keyword == "error message"
        
    def test_grep_with_single_quoted_keyword(self):
        result = parse_command("kubectl get pods | grep 'failed pod'")
        assert len(result) == 2
        assert isinstance(result[1], GrepCommand)
        assert result[1].keyword == "failed pod"
        
    def test_complex_kubectl_with_grep(self):
        result = parse_command("kubectl get pods -n kube-system -l app=nginx | grep Running")
        assert len(result) == 2
        assert isinstance(result[0], KubectlGetCommand)
        assert isinstance(result[1], GrepCommand)
        assert result[0].resource_type == "pods"
        assert result[0].namespace == "kube-system"
        assert result[0].selector == "app=nginx"
        assert result[1].keyword == "Running"
        
    def test_multiple_pipes_raises_error(self):
        with pytest.raises(ValueError, match="Only single pipe is supported"):
            parse_command("kubectl get pods | grep nginx | head")
            
    def test_non_grep_after_pipe_raises_error(self):
        with pytest.raises(ValueError, match="Unsupported command"):
            parse_command("kubectl get pods | head")
            
    def test_grep_without_keyword_raises_error(self):
        with pytest.raises(ValueError, match="Grep command requires a keyword"):
            parse_command("kubectl get pods | grep")


class TestValidateGrepCommand:
    
    def test_valid_grep_command_passes(self):
        cmd = GrepCommand(keyword="nginx")
        validate_grep_command(cmd)
        
    def test_grep_with_spaces_passes(self):
        cmd = GrepCommand(keyword="error message")
        validate_grep_command(cmd)
        
    def test_empty_keyword_raises_error(self):
        cmd = GrepCommand(keyword="")
        with pytest.raises(ValueError, match="Grep keyword cannot be empty"):
            validate_grep_command(cmd)
            
    def test_unsafe_keyword_with_semicolon_raises_error(self):
        cmd = GrepCommand(keyword="nginx; rm -rf /")
        with pytest.raises(ValueError, match="Unsafe grep keyword"):
            validate_grep_command(cmd)
            
    def test_unsafe_keyword_with_backticks_raises_error(self):
        cmd = GrepCommand(keyword="nginx`rm -rf /`")
        with pytest.raises(ValueError, match="Unsafe grep keyword"):
            validate_grep_command(cmd)
            
    def test_keyword_too_long_raises_error(self):
        cmd = GrepCommand(keyword="a" * 101)
        with pytest.raises(ValueError, match="Grep keyword too long"):
            validate_grep_command(cmd)


class TestValidateKubectlCommand:
    
    def test_valid_base_command_passes(self):
        cmd = BaseKubectlCommand(resource_type="pods")
        validate_kubectl_command(cmd)
        
    def test_invalid_resource_type_raises_error(self):
        cmd = BaseKubectlCommand(resource_type="invalid-resource")
        with pytest.raises(ValueError, match="Invalid resource type"):
            validate_kubectl_command(cmd)


class TestValidateKubectlGetCommand:
    
    def test_valid_command_passes(self):
        cmd = KubectlGetCommand(resource_type="pods")
        validate_kubectl_get_command(cmd)
        
    def test_invalid_resource_type_raises_error(self):
        cmd = KubectlGetCommand(resource_type="invalid-resource")
        with pytest.raises(ValueError, match="Invalid resource type"):
            validate_kubectl_get_command(cmd)
            
    def test_invalid_resource_name_with_special_chars_raises_error(self):
        cmd = KubectlGetCommand(resource_type="pods", resource_name="pod-name;rm -rf /")
        with pytest.raises(ValueError, match="Invalid resource name"):
            validate_kubectl_get_command(cmd)
            
    def test_invalid_namespace_with_uppercase_raises_error(self):
        cmd = KubectlGetCommand(resource_type="pods", namespace="MyNamespace")
        with pytest.raises(ValueError, match="Invalid namespace"):
            validate_kubectl_get_command(cmd)
            
    def test_invalid_output_format_raises_error(self):
        cmd = KubectlGetCommand(resource_type="pods", output_format="malicious-format")
        with pytest.raises(ValueError, match="Invalid output format"):
            validate_kubectl_get_command(cmd)
            
    def test_unsafe_additional_flag_raises_error(self):
        cmd = KubectlGetCommand(resource_type="pods", additional_flags=["--exec", "rm -rf /"])
        with pytest.raises(ValueError, match="Unsafe additional flag"):
            validate_kubectl_get_command(cmd)
            
    def test_resource_name_too_long_raises_error(self):
        cmd = KubectlGetCommand(resource_type="pods", resource_name="a" * 254)
        with pytest.raises(ValueError, match="Resource name too long"):
            validate_kubectl_get_command(cmd)
            
    def test_namespace_too_long_raises_error(self):
        cmd = KubectlGetCommand(resource_type="pods", namespace="a" * 64)
        with pytest.raises(ValueError, match="Namespace name too long"):
            validate_kubectl_get_command(cmd)
            
    def test_valid_label_selector_passes(self):
        cmd = KubectlGetCommand(resource_type="pods", selector="app=nginx,version!=1.0")
        validate_kubectl_get_command(cmd)
        
    def test_invalid_label_selector_with_semicolon_raises_error(self):
        cmd = KubectlGetCommand(resource_type="pods", selector="app=nginx; rm -rf /")
        with pytest.raises(ValueError, match="Invalid label selector"):
            validate_kubectl_get_command(cmd)
            
    def test_valid_field_selector_passes(self):
        cmd = KubectlGetCommand(resource_type="pods", field_selector="status.phase=Running")
        validate_kubectl_get_command(cmd)
        
    def test_selector_too_long_raises_error(self):
        cmd = KubectlGetCommand(resource_type="pods", selector="a" * 1001)
        with pytest.raises(ValueError, match="Label selector too long"):
            validate_kubectl_get_command(cmd)


class TestValidateKubectlDescribeCommand:
    
    def test_valid_describe_command_passes(self):
        cmd = KubectlDescribeCommand(resource_type="pods")
        validate_kubectl_describe_command(cmd)
        
    def test_unsafe_describe_flag_raises_error(self):
        cmd = KubectlDescribeCommand(resource_type="pods", additional_flags=["--exec"])
        with pytest.raises(ValueError, match="Unsafe additional flag"):
            validate_kubectl_describe_command(cmd)


class TestValidateKubectlTopCommand:
    
    def test_valid_top_command_passes(self):
        cmd = KubectlTopCommand(resource_type="pods")
        validate_kubectl_top_command(cmd)
        
    def test_unsafe_top_flag_raises_error(self):
        cmd = KubectlTopCommand(resource_type="pods", additional_flags=["--exec"])
        with pytest.raises(ValueError, match="Unsafe additional flag"):
            validate_kubectl_top_command(cmd)


class TestValidateKubectlEventsCommand:
    
    def test_valid_events_command_passes(self):
        cmd = KubectlEventsCommand(resource_type="events")
        validate_kubectl_events_command(cmd)
        
    def test_valid_events_with_for_object_passes(self):
        cmd = KubectlEventsCommand(resource_type="events", for_object="pod/my-pod")
        validate_kubectl_events_command(cmd)
        
    def test_valid_events_with_types_passes(self):
        cmd = KubectlEventsCommand(resource_type="events", types="Normal,Warning")
        validate_kubectl_events_command(cmd)
        
    def test_invalid_event_type_raises_error(self):
        cmd = KubectlEventsCommand(resource_type="events", types="Invalid")
        with pytest.raises(ValueError, match="Invalid event type"):
            validate_kubectl_events_command(cmd)
            
    def test_unsafe_for_object_raises_error(self):
        cmd = KubectlEventsCommand(resource_type="events", for_object="pod/test; rm -rf /")
        with pytest.raises(ValueError, match="Invalid for_object"):
            validate_kubectl_events_command(cmd)
            
    def test_unsafe_events_flag_raises_error(self):
        cmd = KubectlEventsCommand(resource_type="events", additional_flags=["--exec"])
        with pytest.raises(ValueError, match="Unsafe additional flag"):
            validate_kubectl_events_command(cmd)


class TestParseCommandWithValidation:
    
    def test_malicious_resource_type_blocked(self):
        with pytest.raises(ValueError, match="Invalid resource type"):
            parse_command("kubectl get malicious-resource")
            
    def test_command_injection_in_resource_name_blocked(self):
        with pytest.raises(ValueError, match="Invalid resource name"):
            parse_command("kubectl get pods 'pod-name; rm -rf /'")
            
    def test_unsafe_flag_blocked(self):
        with pytest.raises(ValueError, match="Unsafe additional flag"):
            parse_command("kubectl get pods --exec rm")