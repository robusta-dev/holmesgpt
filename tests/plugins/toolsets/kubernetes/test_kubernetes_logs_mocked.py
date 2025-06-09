from typing import Optional
import unittest
from unittest.mock import patch, MagicMock
from kubernetes.client.exceptions import ApiException

from holmes.core.tools import ToolResultStatus
from holmes.plugins.toolsets.kubernetes_logs import KubernetesLogsToolset
from holmes.plugins.toolsets.logging_api import FetchPodLogsParams


def mock_k8s_read_log(
    name: str,
    namespace: str,
    container: Optional[str] = None,
    previous: bool = False,
    timestamps: bool = True,
):
    print(
        f"Mock k8s_read_log called with: name='{name}', namespace='{namespace}', container='{container}', previous={previous}"
    )

    container_suffix = ""
    if container:
        container_suffix = f" - container={container}"

    if namespace == "default" and name == "test-pod":
        if previous:
            return (
                f"2023-05-01T12:00:01Z Log line 1 - prev{container_suffix}\n"
                f"2023-05-01T12:00:02Z Log line 2 - prev{container_suffix}\n"
                f"2023-05-01T12:00:03Z Log line 3 - prev{container_suffix}\n"
            )
        else:
            return (
                f"2023-05-01T12:00:04Z Log line 1 - current{container_suffix}\n"
                f"2023-05-01T12:00:05Z Log line 2 - current{container_suffix}\n"
                f"2023-05-01T12:00:06Z Log line 3 - current{container_suffix}\n"
            )

    # Fallback for unhandled cases, or you could raise an error
    raise Exception(
        f"UNEXPECTED_MOCK_CALL: name={name}, ns={namespace}, container={container}, previous={previous}"
    )


class TestKubernetesLogsToolset(unittest.TestCase):
    def setUp(self):
        self.toolset = KubernetesLogsToolset()

        # Patch the _initialize_client method to prevent actual k8s client initialization
        patcher = patch.object(self.toolset, "_initialize_client")
        self.mock_initialize = patcher.start()
        self.addCleanup(patcher.stop)

        # Create mock for read_namespaced_pod

    @patch("kubernetes.client.CoreV1Api")
    def test_single_container(self, mock_api):
        mock_pod = MagicMock()
        mock_container = MagicMock()
        mock_container.name = "my-container"
        mock_pod.spec.containers = [mock_container]

        mock_api_instance = mock_api.return_value
        mock_api_instance.read_namespaced_pod.return_value = mock_pod
        mock_api_instance.read_namespaced_pod_log.side_effect = mock_k8s_read_log

        self.toolset._core_v1_api = mock_api_instance

        params = FetchPodLogsParams(
            namespace="default",
            pod_name="test-pod",
            limit=2000,
            start_time=None,
            end_time=None,
            match=None,
        )

        result = self.toolset.fetch_pod_logs(params=params)

        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        assert result.data
        # Verify that the logs are formatted correctly (no line numbers)

        expected_logs = (
            "Log line 1 - prev - container=my-container\n"
            "Log line 2 - prev - container=my-container\n"
            "Log line 3 - prev - container=my-container\n"
            "Log line 1 - current - container=my-container\n"
            "Log line 2 - current - container=my-container\n"
            "Log line 3 - current - container=my-container"
        )
        print(f"EXPECTED:\n{expected_logs}")
        print(f"ACTUAL:\n{result.data}")

        assert expected_logs == result.data

    @patch("kubernetes.client.CoreV1Api")
    def test_multi_containers(self, mock_api):
        """Test fallback to previous logs when current logs are empty"""

        mock_pod = MagicMock()
        mock_container1 = MagicMock()
        mock_container1.name = "container1"
        mock_container2 = MagicMock()
        mock_container2.name = "container2"
        mock_pod.spec.containers = [mock_container1, mock_container2]
        mock_api_instance = mock_api.return_value
        mock_api_instance.read_namespaced_pod.return_value = mock_pod
        mock_api_instance.read_namespaced_pod_log.side_effect = mock_k8s_read_log

        self.toolset._core_v1_api = mock_api_instance

        params = FetchPodLogsParams(
            namespace="default",
            pod_name="test-pod",
            limit=2000,
            start_time=None,
            end_time=None,
            match=None,
        )

        result = self.toolset.fetch_pod_logs(params=params)

        self.assertEqual(result.status, ToolResultStatus.SUCCESS)

        print(result.data)

        # Verify that the logs are from the previous container instance
        expected_logs = (
            "container1: Log line 1 - prev - container=container1\n"
            "container2: Log line 1 - prev - container=container2\n"
            "container1: Log line 2 - prev - container=container1\n"
            "container2: Log line 2 - prev - container=container2\n"
            "container1: Log line 3 - prev - container=container1\n"
            "container2: Log line 3 - prev - container=container2\n"
            "container1: Log line 1 - current - container=container1\n"
            "container2: Log line 1 - current - container=container2\n"
            "container1: Log line 2 - current - container=container1\n"
            "container2: Log line 2 - current - container=container2\n"
            "container1: Log line 3 - current - container=container1\n"
            "container2: Log line 3 - current - container=container2"
        )
        print(f"EXPECTED:\n{expected_logs}")
        print(f"ACTUAL:\n{result.data}")
        self.assertEqual(result.data, expected_logs)

    @patch("kubernetes.client.CoreV1Api")
    def test_pod_not_found(self, mock_api):
        """Test error handling when pod is not found"""
        # Configure mock to raise 404 error
        mock_api_instance = mock_api.return_value
        mock_api_instance.read_namespaced_pod.side_effect = ApiException(
            status=404, reason="Not Found"
        )
        # Also make logs method raise error to simulate both pod and logs failing
        mock_api_instance.read_namespaced_pod_log.side_effect = ApiException(
            status=404, reason="Not Found"
        )

        # Set the internal API reference (normally done in _initialize_client)
        self.toolset._core_v1_api = mock_api_instance

        params = FetchPodLogsParams(
            namespace="default",
            pod_name="nonexistent-pod",
            limit=2000,
            start_time=None,
            end_time=None,
            match=None,
        )

        result = self.toolset.fetch_pod_logs(params=params)

        self.assertEqual(result.status, ToolResultStatus.NO_DATA)

    @patch("kubernetes.client.CoreV1Api")
    def test_filter_logs(self, mock_api):
        mock_pod = MagicMock()
        mock_container = MagicMock()
        mock_container.name = "my-container"
        mock_pod.spec.containers = [mock_container]
        mock_api_instance = mock_api.return_value
        mock_api_instance.read_namespaced_pod.return_value = mock_pod

        logs_with_errors = (
            "2023-05-01T12:00:00Z INFO: Starting service\n"
            "2023-05-01T12:00:01Z ERROR: Connection failed\n"
            "2023-05-01T12:00:02Z INFO: Retrying connection\n"
            "2023-05-01T12:00:03Z ERROR: Connection timeout\n"
        )

        mock_api_instance.read_namespaced_pod_log.return_value = logs_with_errors

        # Set the internal API reference (normally done in _initialize_client)
        self.toolset._core_v1_api = mock_api_instance

        params = FetchPodLogsParams(
            namespace="default",
            pod_name="test-pod",
            limit=2000,
            start_time=None,
            end_time=None,
            match="ERROR",
        )

        result = self.toolset.fetch_pod_logs(params=params)

        # Verify only filtered logs are returned
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        assert result.data
        print(f"ACTUAL:\n{result.data}")
        self.assertIn("ERROR: Connection failed", result.data)
        self.assertIn("ERROR: Connection timeout", result.data)
        self.assertNotIn("INFO: Starting service", result.data)
        self.assertNotIn("INFO: Retrying connection", result.data)


if __name__ == "__main__":
    unittest.main()
