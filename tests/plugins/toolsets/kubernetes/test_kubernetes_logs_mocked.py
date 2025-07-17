import unittest
from unittest.mock import patch, MagicMock

from holmes.core.tools import ToolResultStatus
from holmes.plugins.toolsets.kubernetes_logs import KubernetesLogsToolset
from holmes.plugins.toolsets.logging_utils.logging_api import FetchPodLogsParams


def mock_subprocess_run(cmd, **kwargs):
    """Mock subprocess.run for kubectl commands"""
    print(f"Mock subprocess.run called with: {' '.join(cmd)}")

    if cmd[0] == "kubectl" and cmd[1] == "version":
        # Health check
        result = MagicMock()
        result.returncode = 0
        result.stdout = "Client Version: v1.27.0"
        result.stderr = ""
        return result

    if cmd[0] == "kubectl" and cmd[1] == "logs":
        pod_name = cmd[2]
        namespace = cmd[4]  # After -n flag
        previous = "--previous" in cmd

        result = MagicMock()

        if namespace == "default" and pod_name == "test-pod":
            result.returncode = 0
            result.stderr = None

            # kubectl with --prefix=true and --all-containers=true formats output as:
            # [pod/container] timestamp content
            if previous:
                result.stdout = (
                    "[test-pod/my-container] 2023-05-01T12:00:01Z Log line 1 - prev - container=my-container\n"
                    "[test-pod/my-container] 2023-05-01T12:00:02Z Log line 2 - prev - container=my-container\n"
                    "[test-pod/my-container] 2023-05-01T12:00:03Z Log line 3 - prev - container=my-container\n"
                )
            else:
                result.stdout = (
                    "[test-pod/my-container] 2023-05-01T12:00:04Z Log line 1 - current - container=my-container\n"
                    "[test-pod/my-container] 2023-05-01T12:00:05Z Log line 2 - current - container=my-container\n"
                    "[test-pod/my-container] 2023-05-01T12:00:06Z Log line 3 - current - container=my-container\n"
                )
        elif namespace == "default" and pod_name == "multi-container-pod":
            result.returncode = 0
            result.stderr = None

            # Multi-container output with interleaved logs
            if previous:
                result.stdout = (
                    "[multi-container-pod/container1] 2023-05-01T12:00:01Z Log line 1 - prev - container=container1\n"
                    "[multi-container-pod/container2] 2023-05-01T12:00:01Z Log line 1 - prev - container=container2\n"
                    "[multi-container-pod/container1] 2023-05-01T12:00:02Z Log line 2 - prev - container=container1\n"
                    "[multi-container-pod/container2] 2023-05-01T12:00:02Z Log line 2 - prev - container=container2\n"
                    "[multi-container-pod/container1] 2023-05-01T12:00:03Z Log line 3 - prev - container=container1\n"
                    "[multi-container-pod/container2] 2023-05-01T12:00:03Z Log line 3 - prev - container=container2\n"
                )
            else:
                result.stdout = (
                    "[multi-container-pod/container1] 2023-05-01T12:00:04Z Log line 1 - current - container=container1\n"
                    "[multi-container-pod/container2] 2023-05-01T12:00:04Z Log line 1 - current - container=container2\n"
                    "[multi-container-pod/container1] 2023-05-01T12:00:05Z Log line 2 - current - container=container1\n"
                    "[multi-container-pod/container2] 2023-05-01T12:00:05Z Log line 2 - current - container=container2\n"
                    "[multi-container-pod/container1] 2023-05-01T12:00:06Z Log line 3 - current - container=container1\n"
                    "[multi-container-pod/container2] 2023-05-01T12:00:06Z Log line 3 - current - container=container2\n"
                )
        elif namespace == "default" and pod_name == "nonexistent-pod":
            result.returncode = 1
            result.stdout = (
                'Error from server (NotFound): pods "nonexistent-pod" not found'
            )
            result.stderr = None
        else:
            raise Exception(
                f"Unexpected mock call: pod={pod_name}, namespace={namespace}"
            )

        return result

    raise Exception(f"Unexpected command: {' '.join(cmd)}")


class TestKubernetesLogsToolset(unittest.TestCase):
    def setUp(self):
        # Patch subprocess.run for all tests
        self.subprocess_patcher = patch(
            "subprocess.run", side_effect=mock_subprocess_run
        )
        self.mock_subprocess = self.subprocess_patcher.start()
        self.addCleanup(self.subprocess_patcher.stop)

        # Create toolset after patching
        self.toolset = KubernetesLogsToolset()

    def test_single_container(self):
        params = FetchPodLogsParams(
            namespace="default",
            pod_name="test-pod",
            limit=2000,
            start_time=None,
            end_time=None,
            filter=None,
        )

        result = self.toolset.fetch_pod_logs(params=params)

        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertEqual(result.return_code, 0)
        self.assertIsNone(result.error)
        assert result.data

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

    def test_multi_containers(self):
        """Test multi-container pod logs with container prefixes"""

        params = FetchPodLogsParams(
            namespace="default",
            pod_name="multi-container-pod",
            limit=2000,
            start_time=None,
            end_time=None,
            filter=None,
        )

        result = self.toolset.fetch_pod_logs(params=params)

        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertEqual(result.return_code, 0)
        self.assertIsNone(result.error)

        print(result.data)

        # Verify that the logs are formatted with container prefixes for multi-container pods
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

    def test_pod_not_found(self):
        """Test error handling when pod is not found"""
        params = FetchPodLogsParams(
            namespace="default",
            pod_name="nonexistent-pod",
            limit=2000,
            start_time=None,
            end_time=None,
            filter=None,
        )

        result = self.toolset.fetch_pod_logs(params=params)

        # With kubectl, we get an ERROR status when pod is not found
        self.assertEqual(result.return_code, 1)
        self.assertEqual(result.status, ToolResultStatus.ERROR)
        self.assertIn("not found", result.error)

    def test_filter_logs(self):
        params = FetchPodLogsParams(
            namespace="default",
            pod_name="test-pod",  # This will use our standard test logs
            limit=2000,
            start_time=None,
            end_time=None,
            filter="line 2",  # Filter for logs containing "line 2"
        )

        result = self.toolset.fetch_pod_logs(params=params)

        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertEqual(result.return_code, 0)
        self.assertIsNone(result.error)

        assert result.data
        print(f"ACTUAL:\n{result.data}")

        # Should only contain logs with "line 2"
        self.assertIn("Log line 2", result.data)
        self.assertNotIn("Log line 1", result.data)
        self.assertNotIn("Log line 3", result.data)


if __name__ == "__main__":
    unittest.main()
