from unittest.mock import MagicMock, patch

from holmes.core.tools import ToolsetStatusEnum
from holmes.plugins.toolsets.opensearch.opensearch import (
    OpenSearchToolset,
)


class TestOpenSearchToolset:
    """Tests for OpenSearch toolset initialization and health checks."""

    def test_nominal_config_successful_initialization(self):
        """Test that toolset initializes correctly with valid configuration."""
        # Prepare valid configuration
        config = {
            "opensearch_clusters": [
                {
                    "hosts": [{"host": "test-opensearch-host", "port": 9200}],
                    "headers": {"Authorization": "Bearer test-token"},
                    "use_ssl": True,
                    "ssl_assert_hostname": False,
                    "verify_certs": False,
                    "ssl_show_warn": False,
                }
            ]
        }

        # Create toolset instance
        toolset = OpenSearchToolset()

        # Mock OpenSearch client and health check
        with patch(
            "holmes.plugins.toolsets.opensearch.opensearch.OpenSearch"
        ) as mock_opensearch_class:
            # Create mock client instance
            mock_client = MagicMock()
            mock_health_response = {
                "cluster_name": "test-cluster",
                "status": "green",
                "timed_out": False,
                "number_of_nodes": 3,
                "number_of_data_nodes": 3,
                "active_primary_shards": 10,
                "active_shards": 20,
                "relocating_shards": 0,
                "initializing_shards": 0,
                "unassigned_shards": 0,
                "delayed_unassigned_shards": 0,
                "number_of_pending_tasks": 0,
                "number_of_in_flight_fetch": 0,
                "task_max_waiting_in_queue_millis": 0,
                "active_shards_percent_as_number": 100.0,
            }
            mock_client.cluster.health.return_value = mock_health_response
            mock_opensearch_class.return_value = mock_client

            # Set config and call check_prerequisites
            toolset.config = config
            toolset.check_prerequisites()

            # Verify OpenSearch client was created with correct parameters
            mock_opensearch_class.assert_called_once()
            call_args = mock_opensearch_class.call_args[1]

            # Verify hosts
            assert "hosts" in call_args
            assert len(call_args["hosts"]) == 1
            assert call_args["hosts"][0]["host"] == "test-opensearch-host"
            assert call_args["hosts"][0]["port"] == 9200

            # Verify SSL settings
            assert call_args["use_ssl"] is True
            assert call_args["ssl_assert_hostname"] is False
            assert call_args["verify_certs"] is False
            assert call_args["ssl_show_warn"] is False

            # Verify headers
            assert call_args["headers"]["Authorization"] == "Bearer test-token"

            # Verify health check was called
            mock_client.cluster.health.assert_called_once_with(params={"timeout": 5})

            # Verify toolset status
            assert toolset.status == ToolsetStatusEnum.ENABLED
            assert toolset.error is None

            # Verify client was stored
            assert len(toolset.clients) == 1
            assert toolset.clients[0].hosts == ["test-opensearch-host"]

    def test_incorrect_config_failed_health_check(self):
        """Test that toolset fails initialization when health check fails."""
        # Prepare configuration
        config = {
            "opensearch_clusters": [
                {
                    "hosts": [{"host": "test-opensearch-host", "port": 9200}],
                    "use_ssl": True,
                    "ssl_assert_hostname": False,
                    "verify_certs": False,
                }
            ]
        }

        # Create toolset instance
        toolset = OpenSearchToolset()

        # Mock OpenSearch client to fail health check
        with patch(
            "holmes.plugins.toolsets.opensearch.opensearch.OpenSearch"
        ) as mock_opensearch_class:
            # Create mock client instance that fails health check
            mock_client = MagicMock()
            mock_client.cluster.health.side_effect = Exception(
                "Connection refused: Unable to connect to OpenSearch cluster"
            )
            mock_opensearch_class.return_value = mock_client

            # Set config and call check_prerequisites
            toolset.config = config
            toolset.check_prerequisites()

            # Verify OpenSearch client was created
            mock_opensearch_class.assert_called_once()

            # Verify health check was attempted
            mock_client.cluster.health.assert_called_once_with(params={"timeout": 5})

            # Verify toolset status indicates failure
            assert toolset.status == ToolsetStatusEnum.FAILED
            assert toolset.error is not None
            assert "Failed to set up opensearch client" in toolset.error
            assert "Connection refused" in toolset.error

            # Verify no clients were stored
            assert len(toolset.clients) == 0

    def test_missing_config_fails(self):
        """Test that toolset fails when no configuration is provided."""
        # Create toolset instance
        toolset = OpenSearchToolset()

        # Set empty config and call check_prerequisites
        toolset.config = {}
        toolset.check_prerequisites()

        # Verify toolset status indicates failure
        assert toolset.status == ToolsetStatusEnum.FAILED
        assert toolset.error is not None
        assert "missing" in toolset.error.lower()

    def test_http_auth_configuration(self):
        """Test that toolset correctly handles HTTP authentication configuration."""
        # Prepare configuration with HTTP auth
        config = {
            "opensearch_clusters": [
                {
                    "hosts": [{"host": "test-opensearch-host", "port": 9200}],
                    "http_auth": {
                        "username": "test-user",
                        "password": "test-password",
                    },
                    "use_ssl": True,
                    "verify_certs": True,
                }
            ]
        }

        # Create toolset instance
        toolset = OpenSearchToolset()

        # Mock OpenSearch client
        with patch(
            "holmes.plugins.toolsets.opensearch.opensearch.OpenSearch"
        ) as mock_opensearch_class:
            # Create mock client instance
            mock_client = MagicMock()
            mock_client.cluster.health.return_value = {"status": "green"}
            mock_opensearch_class.return_value = mock_client

            # Set config and call check_prerequisites
            toolset.config = config
            toolset.check_prerequisites()

            # Verify OpenSearch client was created with correct parameters
            mock_opensearch_class.assert_called_once()
            call_args = mock_opensearch_class.call_args[1]

            # Verify http_auth was converted to tuple format
            assert "http_auth" in call_args
            assert call_args["http_auth"] == ("test-user", "test-password")

            # Verify toolset status
            assert toolset.status == ToolsetStatusEnum.ENABLED
            assert toolset.error is None

    def test_multiple_clusters_partial_failure(self):
        """Test that toolset succeeds when at least one cluster is healthy."""
        # Prepare configuration with multiple clusters
        config = {
            "opensearch_clusters": [
                {
                    "hosts": [{"host": "test-host-1", "port": 9200}],
                    "use_ssl": False,
                },
                {
                    "hosts": [{"host": "test-host-2", "port": 9200}],
                    "use_ssl": False,
                },
                {
                    "hosts": [{"host": "test-host-3", "port": 9200}],
                    "use_ssl": False,
                },
            ]
        }

        # Create toolset instance
        toolset = OpenSearchToolset()

        # Mock OpenSearch client with different behaviors
        with patch(
            "holmes.plugins.toolsets.opensearch.opensearch.OpenSearch"
        ) as mock_opensearch_class:
            # Create different mock behaviors for each cluster
            def side_effect(*args, **kwargs):
                mock_client = MagicMock()
                hosts = kwargs.get("hosts", [])
                if hosts and hosts[0]["host"] == "test-host-1":
                    # First cluster fails
                    mock_client.cluster.health.side_effect = Exception(
                        "Connection timeout"
                    )
                elif hosts and hosts[0]["host"] == "test-host-2":
                    # Second cluster succeeds
                    mock_client.cluster.health.return_value = {"status": "green"}
                elif hosts and hosts[0]["host"] == "test-host-3":
                    # Third cluster fails
                    mock_client.cluster.health.side_effect = Exception(
                        "Authentication failed"
                    )
                return mock_client

            mock_opensearch_class.side_effect = side_effect

            # Set config and call check_prerequisites
            toolset.config = config
            toolset.check_prerequisites()

            # Verify all three clients were attempted
            assert mock_opensearch_class.call_count == 3

            # Verify toolset status is enabled (at least one cluster succeeded)
            assert toolset.status == ToolsetStatusEnum.ENABLED
            assert toolset.error is not None  # Errors from failed clusters are recorded
            assert "Connection timeout" in toolset.error
            assert "Authentication failed" in toolset.error

            # Verify only successful client was stored
            assert len(toolset.clients) == 1
            assert toolset.clients[0].hosts == ["test-host-2"]

    def test_all_clusters_fail(self):
        """Test that toolset fails when all clusters fail health check."""
        # Prepare configuration with multiple clusters
        config = {
            "opensearch_clusters": [
                {
                    "hosts": [{"host": "test-host-1", "port": 9200}],
                    "use_ssl": False,
                },
                {
                    "hosts": [{"host": "test-host-2", "port": 9200}],
                    "use_ssl": False,
                },
            ]
        }

        # Create toolset instance
        toolset = OpenSearchToolset()

        # Mock OpenSearch client to always fail
        with patch(
            "holmes.plugins.toolsets.opensearch.opensearch.OpenSearch"
        ) as mock_opensearch_class:
            # Create mock client that always fails
            mock_client = MagicMock()
            mock_client.cluster.health.side_effect = Exception("Cluster unavailable")
            mock_opensearch_class.return_value = mock_client

            # Set config and call check_prerequisites
            toolset.config = config
            toolset.check_prerequisites()

            # Verify both clients were attempted
            assert mock_opensearch_class.call_count == 2

            # Verify toolset status indicates failure
            assert toolset.status == ToolsetStatusEnum.FAILED
            assert toolset.error is not None
            assert "Cluster unavailable" in toolset.error

            # Verify no clients were stored
            assert len(toolset.clients) == 0
