"""Unit tests for Azure Monitor Metrics toolset individual tools."""

import json
import pytest
from unittest.mock import MagicMock, patch, Mock
from requests import RequestException

from holmes.core.tools import ToolResultStatus, StructuredToolResult
from holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset import (
    AzureMonitorMetricsToolset,
    AzureMonitorMetricsConfig,
    CheckAKSClusterContext,
    GetAKSClusterResourceID,
    CheckAzureMonitorPrometheusEnabled,
    GetActivePrometheusAlerts,
    ExecuteAzureMonitorPrometheusQuery,
    ExecuteAlertPromQLQuery,
    ExecuteAzureMonitorPrometheusRangeQuery,
)


class TestCheckAKSClusterContext:
    """Tests for CheckAKSClusterContext tool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.toolset = AzureMonitorMetricsToolset()
        self.toolset.config = AzureMonitorMetricsConfig()
        self.tool = CheckAKSClusterContext(self.toolset)
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.check_if_running_in_aks')
    def test_success_running_in_aks(self, mock_check_aks):
        """Test successful detection of AKS environment."""
        # Mock AKS detection to return True
        mock_check_aks.return_value = True
        
        # Execute tool
        result = self.tool._invoke({})
        
        # Verify result
        assert result.status == ToolResultStatus.SUCCESS
        assert isinstance(result.data, dict)
        assert result.data["running_in_aks"] is True
        assert "Running in AKS cluster" in result.data["message"]
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.check_if_running_in_aks')
    def test_success_not_running_in_aks(self, mock_check_aks):
        """Test successful detection of non-AKS environment."""
        # Mock AKS detection to return False
        mock_check_aks.return_value = False
        
        # Execute tool
        result = self.tool._invoke({})
        
        # Verify result
        assert result.status == ToolResultStatus.SUCCESS
        assert isinstance(result.data, dict)
        assert result.data["running_in_aks"] is False
        assert "Not running in AKS cluster" in result.data["message"]
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.check_if_running_in_aks')
    def test_failure_detection_error(self, mock_check_aks):
        """Test error handling during AKS detection."""
        # Mock AKS detection to raise exception
        mock_check_aks.side_effect = Exception("Environment detection failed")
        
        # Execute tool
        result = self.tool._invoke({})
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        assert "Failed to check AKS cluster context" in result.error
        assert "Environment detection failed" in result.error


class TestGetAKSClusterResourceID:
    """Tests for GetAKSClusterResourceID tool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.toolset = AzureMonitorMetricsToolset()
        self.toolset.config = AzureMonitorMetricsConfig()
        self.tool = GetAKSClusterResourceID(self.toolset)
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.get_aks_cluster_resource_id')
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.extract_cluster_name_from_resource_id')
    def test_success_cluster_found(self, mock_extract_name, mock_get_resource_id):
        """Test successful cluster resource ID retrieval."""
        # Mock cluster resource ID and name extraction
        test_resource_id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ContainerService/managedClusters/test-cluster"
        test_cluster_name = "test-cluster"
        
        mock_get_resource_id.return_value = test_resource_id
        mock_extract_name.return_value = test_cluster_name
        
        # Execute tool
        result = self.tool._invoke({})
        
        # Verify result
        assert result.status == ToolResultStatus.SUCCESS
        assert isinstance(result.data, dict)
        assert result.data["cluster_resource_id"] == test_resource_id
        assert result.data["cluster_name"] == test_cluster_name
        assert "Found AKS cluster: test-cluster" in result.data["message"]
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.get_aks_cluster_resource_id')
    def test_failure_cluster_not_found(self, mock_get_resource_id):
        """Test failure when cluster resource ID cannot be determined."""
        # Mock cluster resource ID to return None
        mock_get_resource_id.return_value = None
        
        # Execute tool
        result = self.tool._invoke({})
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        assert "Could not determine AKS cluster resource ID" in result.error
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.get_aks_cluster_resource_id')
    def test_failure_exception_during_detection(self, mock_get_resource_id):
        """Test error handling during cluster detection."""
        # Mock cluster detection to raise exception
        mock_get_resource_id.side_effect = Exception("Azure CLI not available")
        
        # Execute tool
        result = self.tool._invoke({})
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        assert "Failed to get AKS cluster resource ID" in result.error
        assert "Azure CLI not available" in result.error


class TestCheckAzureMonitorPrometheusEnabled:
    """Tests for CheckAzureMonitorPrometheusEnabled tool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.toolset = AzureMonitorMetricsToolset()
        self.toolset.config = AzureMonitorMetricsConfig()
        self.tool = CheckAzureMonitorPrometheusEnabled(self.toolset)
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.get_azure_monitor_workspace_for_cluster')
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.extract_cluster_name_from_resource_id')
    def test_success_prometheus_enabled(self, mock_extract_name, mock_get_workspace):
        """Test successful detection of enabled Azure Monitor Prometheus."""
        # Mock workspace info and cluster name
        test_resource_id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ContainerService/managedClusters/test-cluster"
        test_cluster_name = "test-cluster"
        workspace_info = {
            "prometheus_query_endpoint": "https://test-workspace.prometheus.monitor.azure.com",
            "azure_monitor_workspace_resource_id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/microsoft.monitor/accounts/test-workspace",
            "location": "eastus",
            "associated_grafanas": []
        }
        
        mock_get_workspace.return_value = workspace_info
        mock_extract_name.return_value = test_cluster_name
        
        # Execute tool with cluster resource ID
        params = {"cluster_resource_id": test_resource_id}
        result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.SUCCESS
        assert isinstance(result.data, dict)
        assert result.data["azure_monitor_prometheus_enabled"] is True
        assert result.data["cluster_name"] == test_cluster_name
        assert result.data["prometheus_query_endpoint"] == workspace_info["prometheus_query_endpoint"]
        assert "Azure Monitor managed Prometheus is enabled" in result.data["message"]
        
        # Verify toolset config was updated
        assert self.toolset.config.azure_monitor_workspace_endpoint == workspace_info["prometheus_query_endpoint"]
        assert self.toolset.config.cluster_name == test_cluster_name
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.get_azure_monitor_workspace_for_cluster')
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.extract_cluster_name_from_resource_id')
    def test_failure_prometheus_not_enabled(self, mock_extract_name, mock_get_workspace):
        """Test failure when Azure Monitor Prometheus is not enabled."""
        # Mock workspace not found
        test_resource_id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ContainerService/managedClusters/test-cluster"
        test_cluster_name = "test-cluster"
        
        mock_get_workspace.return_value = None
        mock_extract_name.return_value = test_cluster_name
        
        # Execute tool
        params = {"cluster_resource_id": test_resource_id}
        result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        assert "Azure Monitor managed Prometheus is not enabled" in result.error
        assert test_cluster_name in result.error
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.get_aks_cluster_resource_id')
    def test_failure_no_cluster_specified(self, mock_get_resource_id):
        """Test failure when no cluster is specified or auto-detected."""
        # Mock auto-detection to return None
        mock_get_resource_id.return_value = None
        
        # Execute tool without cluster resource ID
        result = self.tool._invoke({})
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        assert "No AKS cluster specified" in result.error
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.get_azure_monitor_workspace_for_cluster')
    def test_failure_workspace_query_exception(self, mock_get_workspace):
        """Test error handling during workspace query."""
        # Mock workspace query to raise exception
        test_resource_id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ContainerService/managedClusters/test-cluster"
        mock_get_workspace.side_effect = Exception("Azure Resource Graph query failed")
        
        # Execute tool
        params = {"cluster_resource_id": test_resource_id}
        result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        assert "Failed to check Azure Monitor Prometheus status" in result.error
        assert "Azure Resource Graph query failed" in result.error


class TestExecuteAzureMonitorPrometheusQuery:
    """Tests for ExecuteAzureMonitorPrometheusQuery tool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.toolset = AzureMonitorMetricsToolset()
        self.toolset.config = AzureMonitorMetricsConfig(
            azure_monitor_workspace_endpoint="https://test-workspace.prometheus.monitor.azure.com/",
            cluster_name="test-cluster",
            tool_calls_return_data=True
        )
        self.tool = ExecuteAzureMonitorPrometheusQuery(self.toolset)
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.enhance_promql_with_cluster_filter')
    @patch('requests.post')
    def test_success_query_with_data(self, mock_post, mock_enhance_query):
        """Test successful PromQL query execution with data."""
        # Mock query enhancement and HTTP response
        original_query = "up"
        enhanced_query = 'up{cluster="test-cluster"}'
        mock_enhance_query.return_value = enhanced_query
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"__name__": "up", "cluster": "test-cluster"},
                        "value": [1234567890, "1"]
                    }
                ]
            }
        }
        mock_post.return_value = mock_response
        
        # Mock authenticated headers
        with patch.object(self.toolset, '_get_authenticated_headers') as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer test-token"}
            
            # Execute tool
            params = {
                "query": original_query,
                "description": "Check if services are up",
                "auto_cluster_filter": True
            }
            result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.SUCCESS
        result_data = json.loads(result.data)
        assert result_data["status"] == "success"
        assert result_data["query"] == enhanced_query
        assert result_data["cluster_name"] == "test-cluster"
        assert result_data["auto_cluster_filter_applied"] is True
        assert "data" in result_data
        
        # Verify HTTP call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "api/v1/query" in call_args[1]["url"]
        assert call_args[1]["data"]["query"] == enhanced_query
    
    @patch('requests.post')
    def test_success_query_no_data(self, mock_post):
        """Test successful query execution but no data returned."""
        # Mock HTTP response with no data
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": []
            }
        }
        mock_post.return_value = mock_response
        
        # Mock authenticated headers
        with patch.object(self.toolset, '_get_authenticated_headers') as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer test-token"}
            
            # Execute tool
            params = {
                "query": "nonexistent_metric",
                "description": "Query for nonexistent metric",
                "auto_cluster_filter": False
            }
            result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.NO_DATA
        result_data = json.loads(result.data)
        assert result_data["status"] == "no_data"
        assert "no results" in result_data["error_message"]
    
    @patch('requests.post')
    def test_failure_http_error(self, mock_post):
        """Test failure due to HTTP error."""
        # Mock HTTP error response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response
        
        # Mock authenticated headers
        with patch.object(self.toolset, '_get_authenticated_headers') as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer invalid-token"}
            
            # Execute tool
            params = {
                "query": "up",
                "description": "Test query"
            }
            result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        assert "HTTP 401: Unauthorized" in result.error
    
    @patch('requests.post')
    def test_failure_prometheus_error(self, mock_post):
        """Test failure due to Prometheus query error."""
        # Mock Prometheus error response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "error",
            "error": "invalid PromQL syntax"
        }
        mock_post.return_value = mock_response
        
        # Mock authenticated headers
        with patch.object(self.toolset, '_get_authenticated_headers') as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer test-token"}
            
            # Execute tool
            params = {
                "query": "invalid{query",
                "description": "Invalid PromQL query"
            }
            result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        result_data = json.loads(result.data)
        assert result_data["status"] == "error"
        assert "invalid PromQL syntax" in result_data["error_message"]
    
    def test_failure_workspace_not_configured(self):
        """Test failure when Azure Monitor workspace is not configured."""
        # Create toolset without workspace configuration
        toolset = AzureMonitorMetricsToolset()
        toolset.config = AzureMonitorMetricsConfig()  # No workspace endpoint
        tool = ExecuteAzureMonitorPrometheusQuery(toolset)
        
        # Execute tool
        params = {
            "query": "up",
            "description": "Test query"
        }
        result = tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        assert "Azure Monitor workspace is not configured" in result.error
    
    @patch('requests.post')
    def test_failure_connection_error(self, mock_post):
        """Test failure due to connection error."""
        # Mock connection error
        mock_post.side_effect = RequestException("Connection timeout")
        
        # Mock authenticated headers
        with patch.object(self.toolset, '_get_authenticated_headers') as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer test-token"}
            
            # Execute tool
            params = {
                "query": "up",
                "description": "Test query"
            }
            result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        assert "Connection error to Azure Monitor workspace" in result.error
        assert "Connection timeout" in result.error


class TestGetActivePrometheusAlerts:
    """Tests for GetActivePrometheusAlerts tool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.toolset = AzureMonitorMetricsToolset()
        self.toolset.config = AzureMonitorMetricsConfig(
            cluster_resource_id="/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ContainerService/managedClusters/test-cluster"
        )
        self.tool = GetActivePrometheusAlerts(self.toolset)
    
    @patch('holmes.plugins.sources.azuremonitoralerts.AzureMonitorAlertsSource')
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.extract_cluster_name_from_resource_id')
    def test_success_multiple_alerts(self, mock_extract_name, mock_source_class):
        """Test successful retrieval of multiple Prometheus alerts."""
        # Mock cluster name extraction
        mock_extract_name.return_value = "test-cluster"
        
        # Mock alert source and issues
        mock_source = Mock()
        mock_source_class.return_value = mock_source
        
        # Create mock issues
        mock_issue1 = Mock()
        mock_issue1.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.AlertsManagement/alerts/alert-1"
        mock_issue1.name = "High CPU Usage"
        mock_issue1.raw = {
            "alert": {
                "properties": {
                    "essentials": {
                        "alertRule": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Insights/prometheusRuleGroups/test-rules/rules/cpu-high",
                        "description": "CPU usage is above 80%",
                        "severity": "Sev1",
                        "alertState": "New",
                        "monitorCondition": "Fired",
                        "firedDateTime": "2023-01-01T12:00:00Z",
                        "targetResource": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ContainerService/managedClusters/test-cluster"
                    }
                }
            },
            "rule_details": {},
            "extracted_query": "cpu_usage > 0.8",
            "extracted_description": "Alert when CPU usage exceeds 80%"
        }
        
        mock_issue2 = Mock()
        mock_issue2.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.AlertsManagement/alerts/alert-2"
        mock_issue2.name = "Memory Pressure"
        mock_issue2.raw = {
            "alert": {
                "properties": {
                    "essentials": {
                        "alertRule": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Insights/prometheusRuleGroups/test-rules/rules/memory-high",
                        "description": "Memory usage is above 90%",
                        "severity": "Sev0",
                        "alertState": "New",
                        "monitorCondition": "Fired",
                        "firedDateTime": "2023-01-01T12:05:00Z",
                        "targetResource": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ContainerService/managedClusters/test-cluster"
                    }
                }
            },
            "rule_details": {},
            "extracted_query": "memory_usage > 0.9",
            "extracted_description": "Alert when memory usage exceeds 90%"
        }
        
        mock_source.fetch_issues.return_value = [mock_issue1, mock_issue2]
        
        # Execute tool
        params = {}
        result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.SUCCESS
        assert "Successfully found 2 active Prometheus alerts" in result.data
        assert "IMPORTANT: The complete alert details" in result.data
        
        # Verify source was called correctly
        mock_source_class.assert_called_once_with(
            cluster_resource_id="/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ContainerService/managedClusters/test-cluster"
        )
        mock_source.fetch_issues.assert_called_once()
    
    @patch('holmes.plugins.sources.azuremonitoralerts.AzureMonitorAlertsSource')
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.extract_cluster_name_from_resource_id')
    def test_success_specific_alert(self, mock_extract_name, mock_source_class):
        """Test successful retrieval of specific alert by ID."""
        # Mock cluster name extraction
        mock_extract_name.return_value = "test-cluster"
        
        # Mock alert source
        mock_source = Mock()
        mock_source_class.return_value = mock_source
        
        # Create mock issue
        mock_issue = Mock()
        mock_issue.id = "alert-1"
        mock_issue.name = "High CPU Usage"
        mock_issue.raw = {
            "alert": {
                "properties": {
                    "essentials": {
                        "alertRule": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Insights/prometheusRuleGroups/test-rules/rules/cpu-high",
                        "description": "CPU usage is above 80%",
                        "severity": "Sev1",
                        "alertState": "New",
                        "monitorCondition": "Fired",
                        "firedDateTime": "2023-01-01T12:00:00Z",
                        "targetResource": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ContainerService/managedClusters/test-cluster"
                    }
                }
            },
            "rule_details": {},
            "extracted_query": "cpu_usage > 0.8",
            "extracted_description": "Alert when CPU usage exceeds 80%"
        }
        
        mock_source.fetch_issue.return_value = mock_issue
        
        # Execute tool with specific alert ID
        params = {"alert_id": "alert-1"}
        result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.SUCCESS
        assert "Successfully found 1 active Prometheus alerts" in result.data
        
        # Verify source was called correctly
        mock_source.fetch_issue.assert_called_once_with("alert-1")
    
    @patch('holmes.plugins.sources.azuremonitoralerts.AzureMonitorAlertsSource')
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.extract_cluster_name_from_resource_id')
    def test_success_no_alerts_found(self, mock_extract_name, mock_source_class):
        """Test successful execution but no alerts found."""
        # Mock cluster name extraction
        mock_extract_name.return_value = "test-cluster"
        
        # Mock alert source with no alerts
        mock_source = Mock()
        mock_source_class.return_value = mock_source
        mock_source.fetch_issues.return_value = []
        
        # Execute tool
        params = {}
        result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.NO_DATA
        assert "No active Prometheus metric alerts found" in result.data
        assert "test-cluster" in result.data
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.get_aks_cluster_resource_id')
    def test_failure_no_cluster_specified(self, mock_get_resource_id):
        """Test failure when no cluster is specified or auto-detected."""
        # Mock auto-detection to return None
        mock_get_resource_id.return_value = None
        
        # Create toolset without cluster configuration
        toolset = AzureMonitorMetricsToolset()
        toolset.config = AzureMonitorMetricsConfig()
        tool = GetActivePrometheusAlerts(toolset)
        
        # Execute tool
        result = tool._invoke({})
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        assert "No AKS cluster specified" in result.error
    
    @patch('holmes.plugins.sources.azuremonitoralerts.AzureMonitorAlertsSource')
    def test_failure_source_plugin_error(self, mock_source_class):
        """Test failure due to source plugin error."""
        # Mock source to raise exception
        mock_source_class.side_effect = Exception("Azure authentication failed")
        
        # Execute tool
        params = {}
        result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        assert "Failed to fetch alerts using source plugin" in result.error
        assert "Azure authentication failed" in result.error


class TestExecuteAzureMonitorPrometheusRangeQuery:
    """Tests for ExecuteAzureMonitorPrometheusRangeQuery tool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.toolset = AzureMonitorMetricsToolset()
        self.toolset.config = AzureMonitorMetricsConfig(
            azure_monitor_workspace_endpoint="https://test-workspace.prometheus.monitor.azure.com/",
            cluster_name="test-cluster",
            tool_calls_return_data=True,
            default_step_seconds=3600,
            min_step_seconds=60,
            max_data_points=1000
        )
        self.tool = ExecuteAzureMonitorPrometheusRangeQuery(self.toolset)
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.enhance_promql_with_cluster_filter')
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.process_timestamps_to_rfc3339')
    @patch('requests.post')
    def test_success_range_query(self, mock_post, mock_process_timestamps, mock_enhance_query):
        """Test successful PromQL range query execution."""
        # Mock query enhancement and timestamp processing
        original_query = "rate(cpu_usage[5m])"
        enhanced_query = 'rate(cpu_usage{cluster="test-cluster"}[5m])'
        mock_enhance_query.return_value = enhanced_query
        mock_process_timestamps.return_value = ("2023-01-01T11:00:00Z", "2023-01-01T12:00:00Z")
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"__name__": "cpu_usage", "cluster": "test-cluster"},
                        "values": [
                            [1672574400, "0.5"],
                            [1672578000, "0.6"]
                        ]
                    }
                ]
            }
        }
        mock_post.return_value = mock_response
        
        # Mock authenticated headers
        with patch.object(self.toolset, '_get_authenticated_headers') as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer test-token"}
            
            # Execute tool
            params = {
                "query": original_query,
                "description": "CPU usage rate over time",
                "start": "2023-01-01T11:00:00Z",
                "end": "2023-01-01T12:00:00Z",
                "step": 3600,
                "output_type": "Percentage",
                "auto_cluster_filter": True
            }
            result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.SUCCESS
        result_data = json.loads(result.data)
        assert result_data["status"] == "success"
        assert result_data["query"] == enhanced_query
        assert result_data["step"] == 3600
        assert result_data["output_type"] == "Percentage"
        assert result_data["auto_cluster_filter_applied"] is True
        
        # Verify HTTP call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "api/v1/query_range" in call_args[1]["url"]
        assert call_args[1]["data"]["query"] == enhanced_query
        assert call_args[1]["data"]["step"] == 3600
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.process_timestamps_to_rfc3339')
    def test_step_size_calculation(self, mock_process_timestamps):
        """Test optimal step size calculation."""
        # Mock timestamp processing for 24-hour range
        mock_process_timestamps.return_value = ("2023-01-01T00:00:00Z", "2023-01-02T00:00:00Z")
        
        # Test step size calculation
        params = {
            "query": "up",
            "description": "Test query",
            "output_type": "Plain"
        }
        step = self.tool._calculate_optimal_step_size(params, "2023-01-01T00:00:00Z", "2023-01-02T00:00:00Z")
        
        # For 24-hour range, should use default step (3600s)
        assert step == 3600
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.process_timestamps_to_rfc3339')
    def test_step_size_with_user_override(self, mock_process_timestamps):
        """Test step size calculation with user-provided step."""
        # Mock timestamp processing
        mock_process_timestamps.return_value = ("2023-01-01T00:00:00Z", "2023-01-01T01:00:00Z")
        
        # Test with user-provided step
        params = {
            "query": "up",
            "description": "Test query",
            "step": 300,  # 5 minutes
            "output_type": "Plain"
        }
        step = self.tool._calculate_optimal_step_size(params, "2023-01-01T00:00:00Z", "2023-01-01T01:00:00Z")
        
        # Should use user-provided step
        assert step == 300
    
    @patch('holmes.plugins.toolsets.azuremonitor_metrics.azuremonitor_metrics_toolset.process_timestamps_to_rfc3339')
    def test_step_size_minimum_enforcement(self, mock_process_timestamps):
        """Test that minimum step size is enforced."""
        # Mock timestamp processing
        mock_process_timestamps.return_value = ("2023-01-01T00:00:00Z", "2023-01-01T00:05:00Z")
        
        # Test with step below minimum
        params = {
            "query": "up",
            "description": "Test query",
            "step": 30,  # 30 seconds, below min of 60
            "output_type": "Plain"
        }
        step = self.tool._calculate_optimal_step_size(params, "2023-01-01T00:00:00Z", "2023-01-01T00:05:00Z")
        
        # Should enforce minimum step size
        assert step == 60
    
    def test_failure_workspace_not_configured(self):
        """Test failure when Azure Monitor workspace is not configured."""
        # Create toolset without workspace configuration
        toolset = AzureMonitorMetricsToolset()
        toolset.config = AzureMonitorMetricsConfig()  # No workspace endpoint
        tool = ExecuteAzureMonitorPrometheusRangeQuery(toolset)
        
        # Execute tool
        params = {
            "query": "up",
            "description": "Test query",
            "output_type": "Plain"
        }
        result = tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        assert "Azure Monitor workspace is not configured" in result.error


class TestExecuteAlertPromQLQuery:
    """Tests for ExecuteAlertPromQLQuery tool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.toolset = AzureMonitorMetricsToolset()
        self.toolset.config = AzureMonitorMetricsConfig(
            azure_monitor_workspace_endpoint="https://test-workspace.prometheus.monitor.azure.com/",
            cluster_name="test-cluster",
            tool_calls_return_data=True
        )
        self.tool = ExecuteAlertPromQLQuery(self.toolset)
    
    @patch('holmes.plugins.sources.azuremonitoralerts.AzureMonitorAlertsSource')
    @patch('requests.post')
    def test_success_execute_alert_query(self, mock_post, mock_source_class):
        """Test successful execution of alert's PromQL query."""
        # Mock alert source and issue
        mock_source = Mock()
        mock_source_class.return_value = mock_source
        
        mock_issue = Mock()
        mock_issue.id = "alert-1"
        mock_issue.name = "High CPU Usage"
        mock_issue.raw = {
            "extracted_query": "cpu_usage > 0.8"
        }
        mock_source.fetch_issue.return_value = mock_issue
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"__name__": "cpu_usage"},
                        "values": [[1672574400, "0.9"]]
                    }
                ]
            }
        }
        mock_post.return_value = mock_response
        
        # Mock authenticated headers
        with patch.object(self.toolset, '_get_authenticated_headers') as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer test-token"}
            
            # Execute tool
            params = {
                "alert_id": "alert-1",
                "time_range": "1h"
            }
            result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.SUCCESS
        result_data = json.loads(result.data)
        assert result_data["status"] == "success"
        assert result_data["alert_id"] == "alert-1"
        assert result_data["alert_name"] == "High CPU Usage"
        assert result_data["extracted_query"] == "cpu_usage > 0.8"
        assert result_data["time_range"] == "1h"
        
        # Verify HTTP call was made to query_range endpoint
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "api/v1/query_range" in call_args[1]["url"]
        assert call_args[1]["data"]["query"] == "cpu_usage > 0.8"
    
    @patch('holmes.plugins.sources.azuremonitoralerts.AzureMonitorAlertsSource')
    def test_failure_alert_not_found(self, mock_source_class):
        """Test failure when alert is not found."""
        # Mock alert source to return None
        mock_source = Mock()
        mock_source_class.return_value = mock_source
        mock_source.fetch_issue.return_value = None
        
        # Execute tool
        params = {
            "alert_id": "nonexistent-alert",
            "time_range": "1h"
        }
        result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        assert "Alert nonexistent-alert not found" in result.error
    
    @patch('holmes.plugins.sources.azuremonitoralerts.AzureMonitorAlertsSource')
    def test_failure_no_query_extracted(self, mock_source_class):
        """Test failure when no PromQL query can be extracted from alert."""
        # Mock alert source and issue without query
        mock_source = Mock()
        mock_source_class.return_value = mock_source
        
        mock_issue = Mock()
        mock_issue.id = "alert-1"
        mock_issue.name = "Test Alert"
        mock_issue.raw = {
            "extracted_query": "Query not available"
        }
        mock_source.fetch_issue.return_value = mock_issue
        
        # Execute tool
        params = {
            "alert_id": "alert-1",
            "time_range": "1h"
        }
        result = self.tool._invoke(params)
        
        # Verify result
        assert result.status == ToolResultStatus.ERROR
        assert "Could not extract PromQL query from alert" in result.error
    
    def test_parse_time_range_valid_formats(self):
        """Test time range parsing with valid formats."""
        assert self.tool._parse_time_range("1h") == 3600
        assert self.tool._parse_time_range("30m") == 1800
        assert self.tool._parse_time_range("24h") == 86400
        assert self.tool._parse_time_range("1d") == 86400
        assert self.tool._parse_time_range("120s") == 120
    
    def test_parse_time_range_invalid_formats(self):
        """Test time range parsing with invalid formats."""
        assert self.tool._parse_time_range("invalid") is None
        assert self.tool._parse_time_range("1x") is None
        assert self.tool._parse_time_range("") is None
        assert self.tool._parse_time_range("1.5h") is None
