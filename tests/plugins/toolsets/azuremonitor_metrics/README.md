# Azure Monitor Metrics Toolset Tests

This directory contains comprehensive unit tests for the Azure Monitor Metrics toolset individual tools.

## Test Coverage

The test suite covers all 7 tools in the Azure Monitor Metrics toolset:

### 1. CheckAKSClusterContext
- ✅ Successful AKS environment detection (running in AKS)
- ✅ Successful detection of non-AKS environment 
- ✅ Error handling during environment detection

### 2. GetAKSClusterResourceID
- ✅ Successful cluster resource ID retrieval
- ✅ Failure when cluster cannot be found
- ✅ Exception handling during cluster detection

### 3. CheckAzureMonitorPrometheusEnabled
- ✅ Successful detection of enabled Azure Monitor Prometheus
- ✅ Failure when Prometheus is not enabled
- ✅ Failure when no cluster is specified
- ✅ Exception handling during workspace queries

### 4. ExecuteAzureMonitorPrometheusQuery
- ✅ Successful PromQL query execution with data
- ✅ Query execution with no data returned
- ✅ HTTP error handling (401, etc.)
- ✅ Prometheus query error handling
- ✅ Workspace not configured scenarios
- ✅ Connection error handling

### 5. GetActivePrometheusAlerts
- ✅ Successful retrieval of multiple alerts
- ✅ Specific alert retrieval by ID
- ✅ No alerts found scenarios
- ✅ Missing cluster handling
- ✅ Source plugin error handling

### 6. ExecuteAzureMonitorPrometheusRangeQuery
- ✅ Successful range query execution
- ✅ Step size calculation logic
- ✅ User-provided step size handling
- ✅ Minimum step size enforcement
- ✅ Workspace configuration validation

### 7. ExecuteAlertPromQLQuery
- ✅ Successful alert query execution
- ✅ Alert not found scenarios
- ✅ Query extraction failures
- ✅ Time range parsing (valid and invalid formats)

## Test Structure

Each tool class has its own test class following the pattern:
```python
class TestToolName:
    def setup_method(self):
        # Set up test fixtures
    
    def test_success_scenario(self):
        # Test successful operations
    
    def test_failure_scenario(self):
        # Test error conditions
```

## Mocking Strategy

The tests use comprehensive mocking for:

- **Azure Authentication**: Mock `_get_authenticated_headers()` and token acquisition
- **HTTP Requests**: Mock `requests.get/post` calls to Azure Monitor endpoints
- **Azure Resource Graph**: Mock ARG queries for workspace discovery
- **Utility Functions**: Mock cluster detection and resource ID parsing
- **Source Plugins**: Mock `AzureMonitorAlertsSource` for alert fetching
- **External Commands**: Mock kubectl and Azure CLI interactions

## Running the Tests

```bash
# Run all tests
poetry run pytest tests/plugins/toolsets/azuremonitor_metrics/test_azuremonitor_metrics_tools.py -v

# Run specific tool tests
poetry run pytest tests/plugins/toolsets/azuremonitor_metrics/test_azuremonitor_metrics_tools.py::TestCheckAKSClusterContext -v

# Run specific test
poetry run pytest tests/plugins/toolsets/azuremonitor_metrics/test_azuremonitor_metrics_tools.py::TestCheckAKSClusterContext::test_success_running_in_aks -v
```

## Test Benefits

1. **Comprehensive Coverage**: Tests all major functionality and edge cases
2. **Isolated Testing**: Each tool tested independently with proper mocking
3. **Real-world Scenarios**: Covers actual usage patterns and failure modes
4. **Maintainable**: Clear organization and reusable patterns
5. **Integration Ready**: Follows existing project test patterns and conventions

## Key Features Tested

- **Azure Integration**: Authentication, token handling, workspace discovery
- **AKS Detection**: Environment detection, cluster resource ID retrieval
- **PromQL Processing**: Query enhancement, cluster filtering, response parsing
- **Error Handling**: Network errors, authentication failures, invalid parameters
- **Alert Management**: Alert fetching, formatting, investigation workflows
- **Configuration Validation**: Workspace setup, parameter validation, defaults

The test suite ensures the Azure Monitor Metrics toolset is robust, reliable, and handles all expected scenarios gracefully.
