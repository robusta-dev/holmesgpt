import unittest
from unittest.mock import patch, MagicMock
from kubernetes.client.exceptions import ApiException

from holmes.core.tools import ToolResultStatus
from holmes.plugins.toolsets.kubernetes_logs import KubernetesLogsToolset


class TestKubernetesLogsToolset(unittest.TestCase):
    """Test KubernetesLogsToolset functionality"""

    def setUp(self):
        """Set up common mocks and test fixtures"""
        self.toolset = KubernetesLogsToolset()

        # Create mock for read_namespaced_pod
        self.mock_pod = MagicMock()
        self.mock_container = MagicMock()
        self.mock_container.name = "test-container"
        self.mock_pod.spec.containers = [self.mock_container]

        # Create mock for read_namespaced_pod_log
        self.sample_logs = (
            "2023-05-01T12:00:00Z Log line 1\n"
            "2023-05-01T12:00:01Z Log line 2\n"
            "2023-05-01T12:00:02Z Log line 3\n"
        )

    @patch("kubernetes.client.CoreV1Api")
    @patch("kubernetes.config")
    def test_default_log_formatting(self, mock_config, mock_api):
        """Test that logs are formatted correctly with default settings"""
        # Configure mocks
        mock_api_instance = mock_api.return_value
        mock_api_instance.read_namespaced_pod.return_value = self.mock_pod
        mock_api_instance.read_namespaced_pod_log.return_value = self.sample_logs

        # Call the fetch_logs method
        result = self.toolset.fetch_logs(namespace="default", pod_name="test-pod")

        # Verify results
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)

        # Verify that the logs are formatted correctly (no line numbers)
        expected_logs = (
            "2023-05-01T12:00:00Z Log line 1\n"
            "2023-05-01T12:00:01Z Log line 2\n"
            "2023-05-01T12:00:02Z Log line 3"
        )
        self.assertEqual(result.data, expected_logs)

        # Verify that timestamps were included
        self.assertIn("2023-05-01T12:00:00Z", result.data)

        # Verify the correct API calls were made
        mock_api_instance.read_namespaced_pod.assert_called_once_with(
            name="test-pod", namespace="default"
        )

        mock_api_instance.read_namespaced_pod_log.assert_called_once()
        kwargs = mock_api_instance.read_namespaced_pod_log.call_args[1]
        self.assertEqual(kwargs["name"], "test-pod")
        self.assertEqual(kwargs["namespace"], "default")
        self.assertEqual(kwargs["container"], "test-container")
        self.assertEqual(kwargs["previous"], False)  # Default should be False
        self.assertEqual(kwargs["timestamps"], False)  # Default should be False

    @patch("kubernetes.client.CoreV1Api")
    @patch("kubernetes.config")
    def test_fallback_to_previous_logs(self, mock_config, mock_api):
        """Test fallback to previous logs when current logs are empty"""
        # Configure mocks
        mock_api_instance = mock_api.return_value
        mock_api_instance.read_namespaced_pod.return_value = self.mock_pod

        # Configure read_namespaced_pod_log to return empty for current logs
        # and non-empty for previous logs
        previous_logs = (
            "2023-05-01T11:00:00Z Previous log 1\n"
            "2023-05-01T11:00:01Z Previous log 2\n"
        )

        def mock_get_logs(**kwargs):
            if kwargs.get("previous", False):
                return previous_logs
            else:
                return ""  # Empty current logs

        mock_api_instance.read_namespaced_pod_log.side_effect = mock_get_logs

        # Call the fetch_logs method
        result = self.toolset.fetch_logs(namespace="default", pod_name="test-pod")

        # Verify results
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)

        # Verify that the logs are from the previous container instance
        expected_logs = (
            "2023-05-01T11:00:00Z Previous log 1\n"
            "2023-05-01T11:00:01Z Previous log 2"
        )
        self.assertEqual(result.data, expected_logs)

        # Verify the API was called twice - once for current logs and once for previous
        self.assertEqual(mock_api_instance.read_namespaced_pod_log.call_count, 2)

    @patch("kubernetes.client.CoreV1Api")
    @patch("kubernetes.config")
    def test_multi_container_pod(self, mock_config, mock_api):
        """Test logs from multi-container pod"""
        # Configure mocks with multiple containers
        mock_api_instance = mock_api.return_value

        # Create a pod with multiple containers
        mock_pod = MagicMock()
        mock_container1 = MagicMock()
        mock_container1.name = "container1"
        mock_container2 = MagicMock()
        mock_container2.name = "container2"
        mock_pod.spec.containers = [mock_container1, mock_container2]

        mock_api_instance.read_namespaced_pod.return_value = mock_pod

        # Configure different logs for each container
        container1_logs = "Log from container1"
        container2_logs = "Log from container2"

        def mock_get_logs(**kwargs):
            if kwargs.get("container") == "container1":
                return container1_logs
            elif kwargs.get("container") == "container2":
                return container2_logs
            return ""

        mock_api_instance.read_namespaced_pod_log.side_effect = mock_get_logs

        # Call the fetch_logs method
        result = self.toolset.fetch_logs(namespace="default", pod_name="test-pod")

        # Verify results
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)

        # Verify logs have container prefix
        self.assertIn("container1: Log from container1", result.data)
        self.assertIn("container2: Log from container2", result.data)

        # Verify the API call was made twice (once for each container)
        self.assertEqual(mock_api_instance.read_namespaced_pod_log.call_count, 2)

    @patch("kubernetes.client.CoreV1Api")
    @patch("kubernetes.config")
    def test_tail_lines_limit(self, mock_config, mock_api):
        """Test limit parameter becomes tail_lines"""
        # Configure mocks
        mock_api_instance = mock_api.return_value
        mock_api_instance.read_namespaced_pod.return_value = self.mock_pod
        mock_api_instance.read_namespaced_pod_log.return_value = self.sample_logs

        # Call the fetch_logs method with limit
        self.toolset.fetch_logs(namespace="default", pod_name="test-pod", limit=100)

        # Verify the API call was made with tail_lines
        mock_api_instance.read_namespaced_pod_log.assert_called_once()
        kwargs = mock_api_instance.read_namespaced_pod_log.call_args[1]
        self.assertEqual(kwargs["tail_lines"], 100)

    @patch("kubernetes.client.CoreV1Api")
    @patch("kubernetes.config")
    def test_pod_not_found(self, mock_config, mock_api):
        """Test error handling when pod is not found"""
        # Configure mock to raise 404 error
        mock_api_instance = mock_api.return_value
        mock_api_instance.read_namespaced_pod.side_effect = ApiException(
            status=404, reason="Not Found"
        )

        # Call the fetch_logs method
        result = self.toolset.fetch_logs(
            namespace="default", pod_name="nonexistent-pod"
        )

        # Verify error response
        self.assertEqual(result.status, ToolResultStatus.ERROR)
        self.assertIn("Pod nonexistent-pod not found", result.error)


if __name__ == "__main__":
    unittest.main()
