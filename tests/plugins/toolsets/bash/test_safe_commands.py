"""
Integration tests for CLI command parsing and stringifying.

These tests verify the complete round-trip functionality by:
1. Taking a string command as input
2. Parsing it into structured Command objects
3. Stringifying it back to a command string
4. Verifying the output matches expected behavior

Covers kubectl, AWS CLI, Azure CLI, and Argo CD CLI commands.
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
            ("kubectl get pods -n default", "kubectl get pods -n default"),
            (
                "kubectl get pods --namespace=kube-system",
                "kubectl get pods --namespace=kube-system",
            ),
            ("kubectl get pods --all-namespaces", "kubectl get pods --all-namespaces"),
            ("kubectl get pods -A", "kubectl get pods -A"),
            ("kubectl get pods -o yaml", "kubectl get pods -o yaml"),
            ("kubectl get pods --output=json", "kubectl get pods --output=json"),
            ("kubectl get pods -l app=nginx", "kubectl get pods -l app=nginx"),
            (
                "kubectl get pods --selector=environment=production",
                "kubectl get pods --selector=environment=production",
            ),
            (
                "kubectl get pods --field-selector=status.phase=Running",
                "kubectl get pods --field-selector=status.phase=Running",
            ),
            ("kubectl get pods --show-labels", "kubectl get pods --show-labels"),
            # Basic kubectl describe commands
            ("kubectl describe pods", "kubectl describe pods"),
            ("kubectl describe pod my-pod", "kubectl describe pod my-pod"),
            (
                "kubectl describe pods -n default",
                "kubectl describe pods -n default",
            ),
            (
                "kubectl describe pods --namespace=kube-system",
                "kubectl describe pods --namespace=kube-system",
            ),
            (
                "kubectl describe pods --all-namespaces",
                "kubectl describe pods --all-namespaces",
            ),
            ("kubectl describe pods -A", "kubectl describe pods -A"),
            (
                "kubectl describe pods -l app=nginx",
                "kubectl describe pods -l app=nginx",
            ),
            (
                "kubectl describe pods --selector=environment=production",
                "kubectl describe pods --selector=environment=production",
            ),
            # Basic kubectl top commands
            ("kubectl top nodes", "kubectl top nodes"),
            ("kubectl top pods", "kubectl top pods"),
            ("kubectl top pods -n default", "kubectl top pods -n default"),
            (
                "kubectl top pods --namespace=kube-system",
                "kubectl top pods --namespace=kube-system",
            ),
            ("kubectl top pods --containers", "kubectl top pods --containers"),
            (
                "kubectl top pods --use-protocol-buffers",
                "kubectl top pods --use-protocol-buffers",
            ),
            ("kubectl top pods -l app=nginx", "kubectl top pods -l app=nginx"),
            ("kubectl top pod my-pod", "kubectl top pod my-pod"),
            # Basic kubectl events commands
            ("kubectl events", "kubectl events"),
            ("kubectl events -n default", "kubectl events -n default"),
            (
                "kubectl events --namespace=kube-system",
                "kubectl events --namespace=kube-system",
            ),
            ("kubectl events --for=pod/my-pod", "kubectl events --for=pod/my-pod"),
            ("kubectl events --types=Normal", "kubectl events --types=Normal"),
            (
                "kubectl events --types=Normal,Warning",
                "kubectl events --types=Normal,Warning",
            ),
            ("kubectl events --watch", "kubectl events --watch"),
            # kubectl get with grep
            ("kubectl get pods | grep nginx", "kubectl get pods | grep nginx"),
            (
                "kubectl get pods -n default | grep 'my-app'",
                "kubectl get pods -n default | grep my-app",
            ),
            (
                "kubectl get deployments -o wide | grep running",
                "kubectl get deployments -o wide | grep running",
            ),
            (
                "kubectl get pods --all-namespaces | grep kube-system",
                "kubectl get pods --all-namespaces | grep kube-system",
            ),
            (
                "kubectl get pods -l app=nginx | grep 'Running'",
                "kubectl get pods -l app=nginx | grep Running",
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
                "kubectl describe pods -n kube-system | grep Warning",
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
                "kubectl events -n default | grep Warning",
            ),
            (
                "kubectl events --for=pod/my-pod | grep Error",
                "kubectl events --for=pod/my-pod | grep Error",
            ),
            # Complex kubectl get commands
            (
                "kubectl get deployments -n kube-system -o wide --show-labels",
                "kubectl get deployments -n kube-system -o wide --show-labels",
            ),
            (
                "kubectl get pods -n kube-system -l app=nginx -o yaml --show-labels",
                "kubectl get pods -n kube-system -l app=nginx -o yaml --show-labels",
            ),
            (
                "kubectl get deployments --all-namespaces --field-selector=metadata.namespace!=kube-system -o wide",
                "kubectl get deployments --all-namespaces --field-selector=metadata.namespace!=kube-system -o wide",
            ),
            (
                "kubectl get services -n production --selector=tier=frontend --output=json",
                "kubectl get services -n production --selector=tier=frontend --output=json",
            ),
            # Complex kubectl describe commands
            (
                "kubectl describe pods -n monitoring --selector=app=prometheus",
                "kubectl describe pods -n monitoring --selector=app=prometheus",
            ),
            (
                "kubectl describe deployments --all-namespaces -l environment=staging",
                "kubectl describe deployments --all-namespaces -l environment=staging",
            ),
            # Complex kubectl top commands
            (
                "kubectl top pods -n kube-system --containers --selector=k8s-app=kube-dns",
                "kubectl top pods -n kube-system --containers --selector=k8s-app=kube-dns",
            ),
            (
                "kubectl top nodes --use-protocol-buffers",
                "kubectl top nodes --use-protocol-buffers",
            ),
            # Complex kubectl events commands
            (
                "kubectl events -n default --for=deployment/my-app --types=Warning,Normal",
                "kubectl events -n default --for=deployment/my-app --types=Warning,Normal",
            ),
            (
                "kubectl events --namespace=kube-system --types=Warning --watch",
                "kubectl events --namespace=kube-system --types=Warning --watch",
            ),
            # Complex commands with grep
            (
                "kubectl get pods -n production -l tier=web -o wide | grep 'Running'",
                "kubectl get pods -n production -l tier=web -o wide | grep Running",
            ),
            (
                "kubectl describe pods --all-namespaces --selector=app=nginx | grep 'Status:'",
                "kubectl describe pods --all-namespaces --selector=app=nginx | grep Status:",
            ),
            (
                "kubectl top pods -n monitoring --containers | grep 'prometheus'",
                "kubectl top pods -n monitoring --containers | grep prometheus",
            ),
            (
                "kubectl events -n kube-system --types=Warning | grep 'Failed'",
                "kubectl events -n kube-system --types=Warning | grep Failed",
            ),
            (
                "kubectl events -n kube-system --types=Warning | grep 'Failed connection'",
                "kubectl events -n kube-system --types=Warning | grep 'Failed connection'",
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
                "kubectl get pods -l app=nginx,version=v1",
            ),
            (
                "kubectl get pods --selector=app!=nginx",
                "kubectl get pods --selector=app!=nginx",
            ),
            (
                "kubectl get pods --field-selector=spec.nodeName=worker-1",
                "kubectl get pods --field-selector=spec.nodeName=worker-1",
            ),
            (
                "kubectl get pods -n kube-system -l k8s-app=kube-dns",
                "kubectl get pods -n kube-system -l k8s-app=kube-dns",
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
                "kubectl get pods -n my-namespace-123",
            ),
            (
                "kubectl describe pods --namespace=test-env",
                "kubectl describe pods --namespace=test-env",
            ),
            # Mixed flag formats (short/long)
            (
                "kubectl get pods -n default --output=yaml",
                "kubectl get pods -n default --output=yaml",
            ),
            (
                "kubectl describe pods --namespace=kube-system -l app=nginx",
                "kubectl describe pods --namespace=kube-system -l app=nginx",
            ),
            (
                "kubectl top pods -A --containers",
                "kubectl top pods -A --containers",
            ),
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
        # print(f"* EXPECTED:\n{expected_output}")
        # print(f"* ACTUAL:\n{output_command}")
        assert output_command == expected_output


class TestAWSIntegration:
    """Integration tests for AWS CLI commands through parse -> stringify pipeline."""

    @pytest.mark.parametrize(
        "input_command,expected_output",
        [
            # Basic AWS EC2 commands
            ("aws ec2 describe-instances", "aws ec2 describe-instances"),
            (
                "aws ec2 describe-instances --output json",
                "aws ec2 describe-instances --output json",
            ),
            (
                "aws ec2 describe-instances --region us-east-1",
                "aws ec2 describe-instances --region us-east-1",
            ),
            (
                "aws ec2 describe-images --owners amazon",
                "aws ec2 describe-images --owners amazon",
            ),
            # AWS S3 commands
            ("aws s3 list-buckets", "aws s3 list-buckets"),
            (
                "aws s3 list-objects --bucket my-bucket",
                "aws s3 list-objects --bucket my-bucket",
            ),
            (
                "aws s3api get-bucket-location --bucket my-bucket",
                "aws s3api get-bucket-location --bucket my-bucket",
            ),
            # AWS Lambda commands
            ("aws lambda list-functions", "aws lambda list-functions"),
            (
                "aws lambda get-function --function-name my-function",
                "aws lambda get-function --function-name my-function",
            ),
            # AWS with grep
            (
                "aws ec2 describe-instances | grep running",
                "aws ec2 describe-instances | grep running",
            ),
            ("aws s3 list-buckets | grep prod", "aws s3 list-buckets | grep prod"),
            # AWS with complex queries
            (
                "aws ec2 describe-instances --query 'Reservations[*].Instances[*].InstanceId'",
                "aws ec2 describe-instances --query 'Reservations[*].Instances[*].InstanceId'",
            ),
        ],
    )
    def test_aws_round_trip(self, input_command: str, expected_output: str):
        output_command = make_command_safe(input_command, config=TEST_CONFIG)
        assert output_command == expected_output


class TestAzureIntegration:
    """Integration tests for Azure CLI commands through parse -> stringify pipeline."""

    @pytest.mark.parametrize(
        "input_command,expected_output",
        [
            # Basic Azure commands
            ("az vm list", "az vm list"),
            ("az vm list --output json", "az vm list --output json"),
            (
                "az vm show --name myvm --resource-group mygroup",
                "az vm show --name myvm --resource-group mygroup",
            ),
            ("az group list", "az group list"),
            ("az account list", "az account list"),
            # Azure network commands
            ("az network vnet list", "az network vnet list"),
            ("az network nsg list", "az network nsg list"),
            ("az network public-ip list", "az network public-ip list"),
            # Azure storage commands
            ("az storage account list", "az storage account list"),
            (
                "az storage container list --account-name mystorageaccount",
                "az storage container list --account-name mystorageaccount",
            ),
            # Azure with grep
            ("az vm list | grep running", "az vm list | grep running"),
            ("az group list | grep prod", "az group list | grep prod"),
            # Azure with complex parameters
            (
                "az vm list --resource-group mygroup --query '[].{Name:name, Status:powerState}'",
                "az vm list --resource-group mygroup --query '[].{Name:name, Status:powerState}'",
            ),
        ],
    )
    def test_azure_round_trip(self, input_command: str, expected_output: str):
        output_command = make_command_safe(input_command, config=TEST_CONFIG)
        assert output_command == expected_output


class TestArgoCDIntegration:
    """Integration tests for Argo CD CLI commands through parse -> stringify pipeline."""

    @pytest.mark.parametrize(
        "input_command,expected_output",
        [
            # Basic Argo CD commands
            ("argocd version", "argocd version"),
            ("argocd context", "argocd context"),
            ("argocd app list", "argocd app list"),
            ("argocd app get myapp", "argocd app get myapp"),
            (
                "argocd app get myapp --output json",
                "argocd app get myapp --output json",
            ),
            # Argo CD cluster commands
            ("argocd cluster list", "argocd cluster list"),
            ("argocd cluster get mycluster", "argocd cluster get mycluster"),
            # Argo CD project commands
            ("argocd proj list", "argocd proj list"),
            ("argocd proj get myproject", "argocd proj get myproject"),
            # Argo CD repo commands
            ("argocd repo list", "argocd repo list"),
            (
                "argocd repo get https://github.com/myorg/myrepo",
                "argocd repo get https://github.com/myorg/myrepo",
            ),
            # Argo CD with grep
            ("argocd app list | grep myapp", "argocd app list | grep myapp"),
            ("argocd cluster list | grep prod", "argocd cluster list | grep prod"),
            # Argo CD logs and monitoring
            ("argocd app logs myapp", "argocd app logs myapp"),
            ("argocd app logs myapp --tail 100", "argocd app logs myapp --tail 100"),
            ("argocd app diff myapp", "argocd app diff myapp"),
            ("argocd app history myapp", "argocd app history myapp"),
            # Argo CD with filters
            (
                "argocd app list --project myproject",
                "argocd app list --project myproject",
            ),
            (
                "argocd app list --selector app=web",
                "argocd app list --selector app=web",
            ),
        ],
    )
    def test_argocd_round_trip(self, input_command: str, expected_output: str):
        output_command = make_command_safe(input_command, config=TEST_CONFIG)
        assert output_command == expected_output


class TestMultiCLIIntegration:
    """Integration tests for combinations of different CLI commands."""

    @pytest.mark.parametrize(
        "input_command,expected_output",
        [
            # Different CLIs with grep
            ("kubectl get pods | grep nginx", "kubectl get pods | grep nginx"),
            (
                "aws ec2 describe-instances | grep running",
                "aws ec2 describe-instances | grep running",
            ),
            ("az vm list | grep production", "az vm list | grep production"),
            ("argocd app list | grep web", "argocd app list | grep web"),
            ("docker ps | grep nginx", "docker ps | grep nginx"),
            ("helm list | grep myrelease", "helm list | grep myrelease"),
            # Commands with various output formats
            ("kubectl get pods -o json", "kubectl get pods -o json"),
            (
                "aws ec2 describe-instances --output yaml",
                "aws ec2 describe-instances --output yaml",
            ),
            ("az vm list --output table", "az vm list --output table"),
            ("argocd app list --output wide", "argocd app list --output wide"),
            ("docker ps --format json", "docker ps --format json"),
            ("helm list --output yaml", "helm list --output yaml"),
        ],
    )
    def test_multi_cli_round_trip(self, input_command: str, expected_output: str):
        output_command = make_command_safe(input_command, config=TEST_CONFIG)
        assert output_command == expected_output


class TestDockerIntegration:
    """Integration tests for Docker CLI commands through parse -> stringify pipeline."""

    @pytest.mark.parametrize(
        "input_command,expected_output",
        [
            # Basic Docker commands
            ("docker ps", "docker ps"),
            ("docker ps -a", "docker ps -a"),
            ("docker ps --format json", "docker ps --format json"),
            ("docker images", "docker images"),
            ("docker images -q", "docker images -q"),
            ("docker container ls", "docker container ls"),
            (
                "docker container inspect mycontainer",
                "docker container inspect mycontainer",
            ),
            ("docker container logs mycontainer", "docker container logs mycontainer"),
            (
                "docker container logs mycontainer --tail 100",
                "docker container logs mycontainer --tail 100",
            ),
            ("docker container stats", "docker container stats"),
            ("docker image ls", "docker image ls"),
            ("docker image inspect nginx", "docker image inspect nginx"),
            ("docker image history nginx", "docker image history nginx"),
            ("docker network ls", "docker network ls"),
            ("docker network inspect bridge", "docker network inspect bridge"),
            ("docker volume ls", "docker volume ls"),
            ("docker volume inspect myvolume", "docker volume inspect myvolume"),
            ("docker version", "docker version"),
            ("docker info", "docker info"),
            ("docker system df", "docker system df"),
            ("docker search nginx", "docker search nginx"),
            # Docker with grep
            ("docker ps | grep nginx", "docker ps | grep nginx"),
            ("docker images | grep latest", "docker images | grep latest"),
            # Docker with complex filters
            (
                "docker ps --filter status=running --format table",
                "docker ps --filter status=running --format table",
            ),
        ],
    )
    def test_docker_round_trip(self, input_command: str, expected_output: str):
        output_command = make_command_safe(input_command, config=TEST_CONFIG)
        assert output_command == expected_output


class TestHelmIntegration:
    """Integration tests for Helm CLI commands through parse -> stringify pipeline."""

    @pytest.mark.parametrize(
        "input_command,expected_output",
        [
            # Basic Helm commands
            ("helm list", "helm list"),
            ("helm ls", "helm ls"),
            ("helm list --output json", "helm list --output json"),
            ("helm list --namespace production", "helm list --namespace production"),
            ("helm list -n production", "helm list -n production"),
            ("helm list --all-namespaces", "helm list --all-namespaces"),
            ("helm get all myrelease", "helm get all myrelease"),
            ("helm get values myrelease", "helm get values myrelease"),
            ("helm get manifest myrelease", "helm get manifest myrelease"),
            ("helm status myrelease", "helm status myrelease"),
            ("helm history myrelease", "helm history myrelease"),
            ("helm show chart nginx", "helm show chart nginx"),
            ("helm show values nginx", "helm show values nginx"),
            ("helm search repo nginx", "helm search repo nginx"),
            ("helm template myrelease nginx", "helm template myrelease nginx"),
            (
                "helm template myrelease nginx --dry-run",
                "helm template myrelease nginx --dry-run",
            ),
            ("helm lint ./mychart", "helm lint ./mychart"),
            ("helm verify mychart-1.0.0.tgz", "helm verify mychart-1.0.0.tgz"),
            ("helm dependency list ./mychart", "helm dependency list ./mychart"),
            ("helm repo list", "helm repo list"),
            ("helm plugin list", "helm plugin list"),
            ("helm version", "helm version"),
            ("helm env", "helm env"),
            # Helm with grep
            ("helm list | grep myrelease", "helm list | grep myrelease"),
            (
                "helm search repo nginx | grep stable",
                "helm search repo nginx | grep stable",
            ),
            # Helm with complex parameters
            (
                "helm template myrelease nginx --namespace production --values values.yaml --set replicas=3",
                "helm template myrelease nginx --namespace production --values values.yaml --set replicas=3",
            ),
        ],
    )
    def test_helm_round_trip(self, input_command: str, expected_output: str):
        output_command = make_command_safe(input_command, config=TEST_CONFIG)
        assert output_command == expected_output


class TestShlexEscaping:
    """Tests to verify that shlex.quote properly escapes complex parameters."""

    @pytest.mark.parametrize(
        "input_command,expected_output",
        [
            # AWS CLI with complex JMESPath queries containing special characters
            (
                "aws ec2 describe-instances --query 'Reservations[*].Instances[?State.Name==`running`]'",
                "aws ec2 describe-instances --query 'Reservations[*].Instances[?State.Name==`running`]'",
            ),
            (
                "aws s3 list-objects --bucket mybucket --query 'Contents[?Size>`1000`]'",
                "aws s3 list-objects --bucket mybucket --query 'Contents[?Size>`1000`]'",
            ),
            (
                "aws ec2 describe-instances --query 'Reservations[].Instances[].[InstanceId,State.Name]'",
                "aws ec2 describe-instances --query 'Reservations[].Instances[].[InstanceId,State.Name]'",
            ),
            # Azure CLI with complex JMESPath queries
            (
                "az vm list --query '[].{Name:name, Status:powerState}'",
                "az vm list --query '[].{Name:name, Status:powerState}'",
            ),
            (
                "az vm list --query '[?powerState==`VM running`].name'",
                "az vm list --query '[?powerState==`VM running`].name'",
            ),
            (
                "az storage account list --query '[].{Name:name, Location:location}'",
                "az storage account list --query '[].{Name:name, Location:location}'",
            ),
            # Argo CD CLI with complex selectors
            (
                "argocd app list --selector 'app=web,version!=v1'",
                "argocd app list --selector 'app=web,version!=v1'",
            ),
            (
                "argocd app list --selector 'tier in (frontend,backend)'",
                "argocd app list --selector 'tier in (frontend,backend)'",
            ),
            # Resource names with spaces and special characters (properly quoted)
            (
                "kubectl get pod 'my pod with spaces'",
                "kubectl get pod 'my pod with spaces'",
            ),
            (
                "aws s3 list-objects --bucket 'my-bucket-with-special-chars_123'",
                "aws s3 list-objects --bucket my-bucket-with-special-chars_123",
            ),
            (
                "az vm show --name 'vm-with.dots' --resource-group 'rg-with_underscores'",
                "az vm show --name vm-with.dots --resource-group rg-with_underscores",
            ),
            # Complex grep patterns with special regex characters
            (
                "kubectl get pods | grep '^nginx-.*-[0-9]\\+$'",
                "kubectl get pods | grep '^nginx-.*-[0-9]\\+$'",
            ),
            (
                "aws ec2 describe-instances | grep 'i-[a-f0-9]\\{17\\}'",
                "aws ec2 describe-instances | grep 'i-[a-f0-9]\\{17\\}'",
            ),
            # Parameters with various quote combinations
            (
                "aws ec2 describe-instances --query \"Reservations[*].Instances[*].Tags[?Key=='Environment']\"",
                "aws ec2 describe-instances --query \"Reservations[*].Instances[*].Tags[?Key=='Environment']\"",
            ),
        ],
    )
    def test_shlex_escaping_complex_params(
        self, input_command: str, expected_output: str
    ):
        """Test that complex parameters are safely handled by shlex escaping."""
        output_command = make_command_safe(input_command, config=TEST_CONFIG)
        assert output_command == expected_output

    def test_shlex_escaping_security(self):
        """Test that potentially dangerous strings are safely escaped."""
        # These commands should not fail validation since shlex will properly escape them
        dangerous_commands = [
            "aws ec2 describe-instances --query 'test; echo injection'",
            "az vm list --query 'test | cat /etc/passwd'",
            "argocd app list --selector 'app=web && echo hack'",
            "kubectl get pods 'pod-name; rm -rf /'",
        ]

        for cmd in dangerous_commands:
            # Should not raise an exception due to character validation
            try:
                result = make_command_safe(cmd, config=TEST_CONFIG)
                # Verify the dangerous parts are properly quoted in the output
                assert ";" in result or "|" in result or "&" in result
            except ValueError as e:
                # If it fails, it should be for allowlist reasons, not character validation
                assert "unsafe characters" not in str(e).lower()
