import unittest
from unittest.mock import patch, MagicMock
from kubernetes.client.exceptions import ApiException

from holmes.core.tools import ToolResultStatus
from holmes.plugins.toolsets.kubernetes_logs import KubernetesLogsToolset
from holmes.plugins.toolsets.logging_api import FetchLogsParams
from holmes.plugins.toolsets.utils import to_unix


class TestKubernetesLogsToolset(unittest.TestCase):

    def setUp(self):
        self.toolset = KubernetesLogsToolset()

        # Patch the _initialize_client method to prevent actual k8s client initialization
        patcher = patch.object(self.toolset, "_initialize_client")
        self.mock_initialize = patcher.start()
        self.addCleanup(patcher.stop)

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
        
        mock_api_instance = mock_api.return_value
        mock_api_instance.read_namespaced_pod.return_value = self.mock_pod
        mock_api_instance.read_namespaced_pod_log.return_value = self.sample_logs

        # Set the internal API reference (normally done in _initialize_client)
        self.toolset._core_v1_api = mock_api_instance

        params = FetchLogsParams(
            namespace="default",
            pod_name="test-pod",
            limit=2000,
            start_time=None,
            end_time=None,
            filter_pattern=None
        )
        
        result = self.toolset.fetch_logs(params=params)

        self.assertEqual(result.status, ToolResultStatus.SUCCESS)

        # Verify that the logs are formatted correctly (no line numbers)
        expected_logs = (
            "2023-05-01T12:00:00Z Log line 1\n"
            "2023-05-01T12:00:01Z Log line 2\n"
            "2023-05-01T12:00:02Z Log line 3"
        )
        self.assertEqual(result.data, expected_logs)

        self.assertIn("2023-05-01T12:00:00Z", result.data)

        mock_api_instance.read_namespaced_pod.assert_called_once_with(
            name="test-pod", namespace="default"
        )

        mock_api_instance.read_namespaced_pod_log.assert_called_once()
        kwargs = mock_api_instance.read_namespaced_pod_log.call_args[1]
        self.assertEqual(kwargs["name"], "test-pod")
        self.assertEqual(kwargs["namespace"], "default")
        self.assertEqual(kwargs["container"], "test-container")

    @patch("kubernetes.client.CoreV1Api")
    @patch("kubernetes.config")
    def test_fallback_to_previous_logs(self, mock_config, mock_api):
        """Test fallback to previous logs when current logs are empty"""
        # Configure mocks
        mock_api_instance = mock_api.return_value
        mock_api_instance.read_namespaced_pod.return_value = self.mock_pod

        # Set the internal API reference (normally done in _initialize_client)
        self.toolset._core_v1_api = mock_api_instance

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

        params = FetchLogsParams(
            namespace="default",
            pod_name="test-pod",
            limit=2000,
            start_time=None,
            end_time=None,
            filter_pattern=None
        )
        
        result = self.toolset.fetch_logs(params=params)

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

        # Set the internal API reference (normally done in _initialize_client)
        self.toolset._core_v1_api = mock_api_instance

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
        params = FetchLogsParams(
            namespace="default",
            pod_name="test-pod",
            limit=2000,
            start_time=None,
            end_time=None,
            filter_pattern=None
        )
        
        result = self.toolset.fetch_logs(params=params)

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

        # Set the internal API reference (normally done in _initialize_client)
        self.toolset._core_v1_api = mock_api_instance

        # Call the fetch_logs method with limit
        params = FetchLogsParams(
            namespace="default",
            pod_name="test-pod",
            limit=100,
            start_time=None,
            end_time=None,
            filter_pattern=None
        )
        
        self.toolset.fetch_logs(params=params)

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
        # Also make logs method raise error to simulate both pod and logs failing
        mock_api_instance.read_namespaced_pod_log.side_effect = ApiException(
            status=404, reason="Not Found"
        )

        # Set the internal API reference (normally done in _initialize_client)
        self.toolset._core_v1_api = mock_api_instance

        # Call the fetch_logs method
        params = FetchLogsParams(
            namespace="default",
            pod_name="nonexistent-pod",
            limit=2000,
            start_time=None,
            end_time=None,
            filter_pattern=None
        )

        result = self.toolset.fetch_logs(params=params)

        # In the updated API, if the pod is not found it tries previous logs which returns empty
        # rather than an error, which is considered a success with "No logs found"
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertEqual(result.data, "No logs found")

    @patch("kubernetes.client.CoreV1Api")
    @patch("kubernetes.config")
    def test_filter_logs(self, mock_config, mock_api):
        """Test log filtering"""
        # Configure mocks
        mock_api_instance = mock_api.return_value
        mock_api_instance.read_namespaced_pod.return_value = self.mock_pod
        
        logs_with_errors = (
            "2023-05-01T12:00:00Z INFO: Starting service\n"
            "2023-05-01T12:00:01Z ERROR: Connection failed\n"
            "2023-05-01T12:00:02Z INFO: Retrying connection\n"
            "2023-05-01T12:00:03Z ERROR: Connection timeout\n"
        )
        
        mock_api_instance.read_namespaced_pod_log.return_value = logs_with_errors

        # Set the internal API reference (normally done in _initialize_client)
        self.toolset._core_v1_api = mock_api_instance

        # Call the fetch_logs method with filter
        params = FetchLogsParams(
            namespace="default",
            pod_name="test-pod",
            limit=2000,
            start_time=None,
            end_time=None,
            filter_pattern="ERROR"
        )
        
        result = self.toolset.fetch_logs(params=params)

        # Verify only filtered logs are returned
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        assert result.data
        self.assertIn("ERROR: Connection failed", result.data)
        self.assertIn("ERROR: Connection timeout", result.data)
        self.assertNotIn("INFO: Starting service", result.data)
        self.assertNotIn("INFO: Retrying connection", result.data)

    @patch("kubernetes.client.CoreV1Api")
    @patch("kubernetes.config")
    @patch("holmes.plugins.toolsets.kubernetes_logs.filter_log_lines_by_timestamp_and_strip_prefix")
    def test_logs_filtered_by_timestamps(self, mock_filter_func, mock_config, mock_api):
        """Test that logs are filtered by start/end timestamp when those are provided"""
        # Configure mocks
        mock_api_instance = mock_api.return_value
        mock_api_instance.read_namespaced_pod.return_value = self.mock_pod
        
        # Sample logs with timestamps
        logs_with_timestamps = (
            "2023-05-01T12:00:00Z Log line 1\n"
            "2023-05-01T12:00:01Z Log line 2\n"
            "2023-05-01T12:00:02Z Log line 3\n"
        )
        
        mock_api_instance.read_namespaced_pod_log.return_value = logs_with_timestamps
        
        # Set up the filter function to return filtered logs
        filtered_logs = ["Log line 2"]
        mock_filter_func.return_value = filtered_logs
        
        # Set the internal API reference (normally done in _initialize_client)
        self.toolset._core_v1_api = mock_api_instance
        
        # Define start and end times for filtering
        start_time = "2023-05-01T12:00:01Z"
        end_time = "2023-05-01T12:00:01Z"
        
        # Call the fetch_logs method with start/end time
        params = FetchLogsParams(
            namespace="default",
            pod_name="test-pod",
            limit=2000,
            start_time=start_time,
            end_time=end_time,
            filter_pattern=None
        )
        
        result = self.toolset.fetch_logs(params=params)
        
        # Verify API was called with timestamps=True
        mock_api_instance.read_namespaced_pod_log.assert_called_once()
        kwargs = mock_api_instance.read_namespaced_pod_log.call_args[1]
        self.assertTrue(kwargs["timestamps"])
        
        # Verify filter function was called with correct parameters
        mock_filter_func.assert_called_once()
        # Convert timestamps to Unix for verification
        unix_start = to_unix(start_time)
        unix_end = to_unix(end_time)
        
        # Check that filter_by_timestamp_and_strip_prefix was called with correct params
        filter_args, filter_kwargs = mock_filter_func.call_args
        self.assertEqual(filter_args[0], logs_with_timestamps.strip().split("\n"))
        self.assertEqual(filter_args[1], unix_start)
        self.assertEqual(filter_args[2], unix_end)
        
        # Verify result only contains filtered logs
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertEqual(result.data, "Log line 2")


if __name__ == "__main__":
    unittest.main()