"""
Integration tests for kubectl command parsing and stringifying.

These tests verify the complete round-trip functionality by:
1. Taking a string command as input
2. Parsing it into structured Command objects
3. Stringifying it back to a command string
4. Verifying the output matches expected behavior
"""

import pytest
from holmes.plugins.toolsets.bash.common.config import (
    BashExecutorConfig,
    KubectlConfig,
    KubectlImageConfig,
)
from holmes.plugins.toolsets.bash.parse_command import make_command_safe


TEST_CONFIG = BashExecutorConfig(
    kubectl=KubectlConfig(
        allowed_images=[
            KubectlImageConfig(
                image="busybox",
                allowed_commands=["cat /etc/resolv.conf", "nslookup .*"],
            ),
            KubectlImageConfig(
                image="registry.k8s.io/e2e-test-images/jessie-dnsutils:1.3",
                allowed_commands=["cat /etc/resolv.conf"],
            ),
        ]
    )
)


class TestKubectlIntegration:
    """Integration tests for kubectl commands through parse -> stringify pipeline."""

    @pytest.mark.parametrize(
        "input_command,expected_output",
        [
            # Basic kubectl get commands
            ("kubectl get pods", "kubectl get pods"),
            ("kubectl get pod my-pod", "kubectl get pod my-pod"),
            ("kubectl get pods -n default", "kubectl get pods --namespace default"),
            (
                "kubectl get pods --namespace=kube-system",
                "kubectl get pods --namespace kube-system",
            ),
            ("kubectl get pods --all-namespaces", "kubectl get pods --all-namespaces"),
            ("kubectl get pods -A", "kubectl get pods --all-namespaces"),
            ("kubectl get pods -o yaml", "kubectl get pods --output yaml"),
            ("kubectl get pods --output=json", "kubectl get pods --output json"),
            ("kubectl get pods -l app=nginx", "kubectl get pods --selector app=nginx"),
            (
                "kubectl get pods --selector=environment=production",
                "kubectl get pods --selector environment=production",
            ),
            (
                "kubectl get pods --field-selector=status.phase=Running",
                "kubectl get pods --field-selector status.phase=Running",
            ),
            ("kubectl get pods --show-labels", "kubectl get pods --show-labels"),
            # Basic kubectl describe commands
            ("kubectl describe pods", "kubectl describe pods"),
            ("kubectl describe pod my-pod", "kubectl describe pod my-pod"),
            (
                "kubectl describe pods -n default",
                "kubectl describe pods --namespace default",
            ),
            (
                "kubectl describe pods --namespace=kube-system",
                "kubectl describe pods --namespace kube-system",
            ),
            (
                "kubectl describe pods --all-namespaces",
                "kubectl describe pods --all-namespaces",
            ),
            ("kubectl describe pods -A", "kubectl describe pods --all-namespaces"),
            (
                "kubectl describe pods -l app=nginx",
                "kubectl describe pods --selector app=nginx",
            ),
            (
                "kubectl describe pods --selector=environment=production",
                "kubectl describe pods --selector environment=production",
            ),
            # Basic kubectl top commands
            ("kubectl top nodes", "kubectl top nodes"),
            ("kubectl top pods", "kubectl top pods"),
            ("kubectl top pods -n default", "kubectl top pods --namespace default"),
            (
                "kubectl top pods --namespace=kube-system",
                "kubectl top pods --namespace kube-system",
            ),
            ("kubectl top pods --containers", "kubectl top pods --containers"),
            (
                "kubectl top pods --use-protocol-buffers",
                "kubectl top pods --use-protocol-buffers",
            ),
            ("kubectl top pods -l app=nginx", "kubectl top pods --selector app=nginx"),
            ("kubectl top pod my-pod", "kubectl top pod my-pod"),
            # Basic kubectl events commands
            ("kubectl events", "kubectl events"),
            ("kubectl events -n default", "kubectl events --namespace default"),
            (
                "kubectl events --namespace=kube-system",
                "kubectl events --namespace kube-system",
            ),
            ("kubectl events --for=pod/my-pod", "kubectl events --for pod/my-pod"),
            ("kubectl events --types=Normal", "kubectl events --types Normal"),
            (
                "kubectl events --types=Normal,Warning",
                "kubectl events --types Normal,Warning",
            ),
            ("kubectl events --watch", "kubectl events --watch"),
            # kubectl get with grep
            ("kubectl get pods | grep nginx", "kubectl get pods | grep nginx"),
            (
                "kubectl get pods -n default | grep 'my-app'",
                "kubectl get pods --namespace default | grep my-app",
            ),
            (
                "kubectl get deployments -o wide | grep running",
                "kubectl get deployments --output wide | grep running",
            ),
            (
                "kubectl get pods --all-namespaces | grep kube-system",
                "kubectl get pods --all-namespaces | grep kube-system",
            ),
            (
                "kubectl get pods -l app=nginx | grep 'Running'",
                "kubectl get pods --selector app=nginx | grep Running",
            ),
            # kubectl describe with grep
            (
                "kubectl describe pods | grep Error",
                "kubectl describe pods | grep Error",
            ),
            (
                "kubectl describe pod my-pod | grep 'Status:'",
                "kubectl describe pod my-pod | grep Status:",
            ),
            (
                "kubectl describe pods -n kube-system | grep Warning",
                "kubectl describe pods --namespace kube-system | grep Warning",
            ),
            # kubectl top with grep
            ("kubectl top pods | grep high-cpu", "kubectl top pods | grep high-cpu"),
            ("kubectl top nodes | grep 'Ready'", "kubectl top nodes | grep Ready"),
            (
                "kubectl top pods --containers | grep memory",
                "kubectl top pods --containers | grep memory",
            ),
            # kubectl events with grep
            ("kubectl events | grep Failed", "kubectl events | grep Failed"),
            (
                "kubectl events -n default | grep 'Warning'",
                "kubectl events --namespace default | grep Warning",
            ),
            (
                "kubectl events --for=pod/my-pod | grep Error",
                "kubectl events --for pod/my-pod | grep Error",
            ),
            # Complex kubectl get commands
            (
                "kubectl get deployments -n kube-system -o wide --show-labels",
                "kubectl get deployments --namespace kube-system --output wide --show-labels",
            ),
            (
                "kubectl get pods -n kube-system -l app=nginx -o yaml --show-labels",
                "kubectl get pods --namespace kube-system --selector app=nginx --output yaml --show-labels",
            ),
            (
                "kubectl get deployments --all-namespaces --field-selector=metadata.namespace!=kube-system -o wide",
                "kubectl get deployments --all-namespaces --field-selector 'metadata.namespace!=kube-system' --output wide",
            ),
            (
                "kubectl get services -n production --selector=tier=frontend --output=json",
                "kubectl get services --namespace production --selector tier=frontend --output json",
            ),
            # Complex kubectl describe commands
            (
                "kubectl describe pods -n monitoring --selector=app=prometheus",
                "kubectl describe pods --namespace monitoring --selector app=prometheus",
            ),
            (
                "kubectl describe deployments --all-namespaces -l environment=staging",
                "kubectl describe deployments --all-namespaces --selector environment=staging",
            ),
            # Complex kubectl top commands
            (
                "kubectl top pods -n kube-system --containers --selector=k8s-app=kube-dns",
                "kubectl top pods --namespace kube-system --selector k8s-app=kube-dns --containers",
            ),
            (
                "kubectl top nodes --use-protocol-buffers",
                "kubectl top nodes --use-protocol-buffers",
            ),
            # Complex kubectl events commands
            (
                "kubectl events -n default --for=deployment/my-app --types=Warning,Normal",
                "kubectl events --namespace default --for deployment/my-app --types Warning,Normal",
            ),
            (
                "kubectl events --namespace=kube-system --types=Warning --watch",
                "kubectl events --namespace kube-system --types Warning --watch",
            ),
            # Complex commands with grep
            (
                "kubectl get pods -n production -l tier=web -o wide | grep 'Running'",
                "kubectl get pods --namespace production --selector tier=web --output wide | grep Running",
            ),
            (
                "kubectl describe pods --all-namespaces --selector=app=nginx | grep 'Status:'",
                "kubectl describe pods --all-namespaces --selector app=nginx | grep Status:",
            ),
            (
                "kubectl top pods -n monitoring --containers | grep 'prometheus'",
                "kubectl top pods --namespace monitoring --containers | grep prometheus",
            ),
            (
                "kubectl events -n kube-system --types=Warning | grep 'Failed'",
                "kubectl events --namespace kube-system --types Warning | grep Failed",
            ),
            # Resource names with special characters
            ("kubectl get pod my-pod-123", "kubectl get pod my-pod-123"),
            (
                "kubectl describe deployment nginx-deployment-v2",
                "kubectl describe deployment nginx-deployment-v2",
            ),
            (
                "kubectl get service my-service.example.com",
                "kubectl get service my-service.example.com",
            ),
            # Selectors with various formats
            (
                "kubectl get pods -l app=nginx,version=v1",
                "kubectl get pods --selector app=nginx,version=v1",
            ),
            (
                "kubectl get pods --selector=app!=nginx",
                "kubectl get pods --selector 'app!=nginx'",
            ),
            (
                "kubectl get pods --field-selector=spec.nodeName=worker-1",
                "kubectl get pods --field-selector spec.nodeName=worker-1",
            ),
            (
                "kubectl get pods -n kube-system -l k8s-app=kube-dns",
                "kubectl get pods --namespace kube-system --selector k8s-app=kube-dns",
            ),
            # Grep with quoted strings containing special characters
            (
                "kubectl get pods | grep 'my-app-.*'",
                "kubectl get pods | grep 'my-app-.*'",
            ),
            (
                'kubectl describe pods | grep "Status: Running"',
                "kubectl describe pods | grep 'Status: Running'",
            ),
            (
                "kubectl events | grep 'Failed to pull image'",
                "kubectl events | grep 'Failed to pull image'",
            ),
            # Namespaces with special characters
            (
                "kubectl get pods -n my-namespace-123",
                "kubectl get pods --namespace my-namespace-123",
            ),
            (
                "kubectl describe pods --namespace=test-env",
                "kubectl describe pods --namespace test-env",
            ),
            # Mixed flag formats (short/long)
            (
                "kubectl get pods -n default --output=yaml",
                "kubectl get pods --namespace default --output yaml",
            ),
            (
                "kubectl describe pods --namespace=kube-system -l app=nginx",
                "kubectl describe pods --namespace kube-system --selector app=nginx",
            ),
            (
                "kubectl top pods -A --containers",
                "kubectl top pods --all-namespaces --containers",
            ),
            # Flag format normalization
            ("kubectl get pods -n=default", "kubectl get pods --namespace default"),
            (
                "kubectl get pods --namespace default",
                "kubectl get pods --namespace default",
            ),
            # Quote normalization in grep
            ('kubectl get pods | grep "nginx"', "kubectl get pods | grep nginx"),
            ("kubectl get pods | grep 'nginx'", "kubectl get pods | grep nginx"),
        ],
    )
    def test_kubectl_round_trip(self, input_command: str, expected_output: str):
        output_command = make_command_safe(input_command, config=TEST_CONFIG)
        print(f"* EXPECTED:\n{expected_output}")
        print(f"* ACTUAL:\n{output_command}")
        assert output_command == expected_output
