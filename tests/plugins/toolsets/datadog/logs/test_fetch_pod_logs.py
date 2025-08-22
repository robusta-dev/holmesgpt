from unittest.mock import Mock, patch
from holmes.core.tools import ToolResultStatus
from holmes.plugins.toolsets.datadog.toolset_datadog_logs import (
    DatadogLogsToolset,
    DatadogLogsConfig,
    DataDogStorageTier,
)
from holmes.plugins.toolsets.logging_utils.logging_api import (
    FetchPodLogsParams,
    PodLoggingTool,
)


class TestDatadogToolsetFetchPodLogs:
    """Test cases for DatadogToolset.fetch_pod_logs() method"""

    def setup_method(self):
        """Setup common test data"""
        self.config = DatadogLogsConfig(
            dd_api_key="test-api-key",
            dd_app_key="test-app-key",
            site_api_url="https://api.datadoghq.com",
            indexes=["main"],
            storage_tiers=[DataDogStorageTier.INDEXES],
            page_size=100,
            default_limit=1000,
            request_timeout=60,
        )

        self.toolset = DatadogLogsToolset()
        self.toolset.dd_config = self.config

        self.fetch_params = FetchPodLogsParams(
            namespace="test-namespace",
            pod_name="test-pod",
            limit=300,
        )

    @patch("holmes.plugins.toolsets.datadog.datadog_api.requests.post")
    def test_fetch_pod_logs_with_pagination(self, mock_post):
        """Test fetch_pod_logs with pagination when more logs are available"""
        # Mock responses for pagination
        # First response with 100 logs and a cursor
        first_response = Mock()
        first_response.status_code = 200
        first_response.json.return_value = {
            "data": [
                {"attributes": {"message": f"Log message {i}"}} for i in range(100)
            ],
            "meta": {"page": {"after": "cursor_for_page_2"}},
        }

        # Second response with 100 logs and a cursor
        second_response = Mock()
        second_response.status_code = 200
        second_response.json.return_value = {
            "data": [
                {"attributes": {"message": f"Log message {i}"}} for i in range(100, 200)
            ],
            "meta": {"page": {"after": "cursor_for_page_3"}},
        }

        # Third response with 100 logs and no cursor (last page)
        third_response = Mock()
        third_response.status_code = 200
        third_response.json.return_value = {
            "data": [
                {"attributes": {"message": f"Log message {i}"}} for i in range(200, 300)
            ],
            "meta": {
                "page": {}  # No "after" cursor means no more pages
            },
        }

        mock_post.side_effect = [first_response, second_response, third_response]

        # Execute
        result = self.toolset.fetch_pod_logs(self.fetch_params)

        # Verify
        assert result.status == ToolResultStatus.SUCCESS
        assert result.error is None

        # Check that all 300 logs are present in reverse order (oldest first)
        logs_lines = result.data.strip().split("\n")
        assert len(logs_lines) == 300

        # Verify logs are in correct order (reversed from API response)
        for i in range(300):
            assert f"Log message {299-i}" in logs_lines[i]

        # Verify API calls
        assert mock_post.call_count == 3

        # Verify the query structure for each call
        for i, api_call in enumerate(mock_post.call_args_list):
            payload = api_call[1]["json"]
            # All calls should have the same base structure
            assert "kube_namespace:test-namespace" in payload["filter"]["query"]
            assert "pod_name:test-pod" in payload["filter"]["query"]
            assert payload["filter"]["storage_tier"] == "indexes"
            assert payload["sort"] == "-timestamp"

    @patch("holmes.plugins.toolsets.datadog.datadog_api.requests.post")
    def test_fetch_pod_logs_less_data_than_requested(self, mock_post):
        """Test fetch_pod_logs when API returns less data than requested"""
        # Mock response with only 80 logs when limit is 1000
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": [
                {"attributes": {"message": f"Log message {i}"}} for i in range(80)
            ],
            "meta": {
                "page": {}  # No cursor, indicating no more data
            },
        }

        mock_post.return_value = response

        # Set up params with higher limit
        params = FetchPodLogsParams(
            namespace="test-namespace",
            pod_name="test-pod",
            limit=1000,
        )

        # Execute
        result = self.toolset.fetch_pod_logs(params)

        # Verify
        assert result.status == ToolResultStatus.SUCCESS
        assert result.error is None

        # Check that only 80 logs are returned
        logs_lines = result.data.strip().split("\n")
        assert len(logs_lines) == 80

        # Verify logs are in correct order (reversed)
        for i in range(80):
            assert f"Log message {79-i}" in logs_lines[i]

        # Verify only one API call was made
        assert mock_post.call_count == 1

        # Check the API call
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert payload["page"]["limit"] == 100  # page_size from config

    @patch("holmes.plugins.toolsets.datadog.datadog_api.requests.post")
    def test_fetch_pod_logs_storage_tier_fallback(self, mock_post):
        """Test fetch_pod_logs falling back to secondary storage tier when first returns no data"""
        # Configure toolset with multiple storage tiers
        self.toolset.dd_config.storage_tiers = [
            DataDogStorageTier.INDEXES,
            DataDogStorageTier.ONLINE_ARCHIVES,
            DataDogStorageTier.FLEX,
        ]

        # Mock responses
        # First call to INDEXES returns no data
        empty_response = Mock()
        empty_response.status_code = 200
        empty_response.json.return_value = {"data": [], "meta": {"page": {}}}

        # Second call to ONLINE_ARCHIVES returns data
        data_response = Mock()
        data_response.status_code = 200
        data_response.json.return_value = {
            "data": [
                {"attributes": {"message": f"Archived log {i}"}} for i in range(50)
            ],
            "meta": {"page": {}},
        }

        mock_post.side_effect = [empty_response, data_response]

        # Execute
        result = self.toolset.fetch_pod_logs(self.fetch_params)

        # Verify
        assert result.status == ToolResultStatus.SUCCESS
        assert result.error is None

        # Check that logs from online archives are returned
        logs_lines = result.data.strip().split("\n")
        assert len(logs_lines) == 50

        # Verify logs content
        for i in range(50):
            assert f"Archived log {49-i}" in logs_lines[i]

        # Verify two API calls were made
        assert mock_post.call_count == 2

        # Check first call used INDEXES
        first_call = mock_post.call_args_list[0]
        payload = first_call[1]["json"]
        assert payload["filter"]["storage_tier"] == "indexes"

        # Check second call used ONLINE_ARCHIVES
        second_call = mock_post.call_args_list[1]
        payload = second_call[1]["json"]
        assert payload["filter"]["storage_tier"] == "online-archives"

    @patch("holmes.plugins.toolsets.datadog.datadog_api.requests.post")
    @patch("time.sleep", return_value=None)  # Mock time.sleep to avoid delays
    def test_fetch_pod_logs_rate_limiting(self, mock_sleep, mock_post):
        """Test fetch_pod_logs handling rate limiting with X-RateLimit-Reset header"""
        # Mock responses
        # First attempt: rate limited
        rate_limited_response = Mock()
        rate_limited_response.status_code = 429
        rate_limited_response.headers = {
            "X-RateLimit-Reset": "5"  # 5 seconds until reset
        }
        rate_limited_response.text = "Rate limit exceeded"

        # Second attempt: successful
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "data": [
                {"attributes": {"message": f"Log after retry {i}"}} for i in range(20)
            ],
            "meta": {"page": {}},
        }

        mock_post.side_effect = [rate_limited_response, success_response]

        # Execute
        result = self.toolset.fetch_pod_logs(self.fetch_params)

        # Verify
        assert result.status == ToolResultStatus.SUCCESS
        assert result.error is None

        # Check that logs are returned
        logs_lines = result.data.strip().split("\n")
        assert len(logs_lines) == 20

        # Verify two API calls were made (one failed with 429, one succeeded)
        assert mock_post.call_count == 2

    @patch("holmes.plugins.toolsets.datadog.datadog_api.requests.post")
    @patch("time.sleep", return_value=None)  # Mock time.sleep to avoid delays
    def test_fetch_pod_logs_rate_limiting_without_reset_header(
        self, mock_sleep, mock_post
    ):
        """Test fetch_pod_logs handling rate limiting without X-RateLimit-Reset header"""
        # Mock responses
        # First attempt: rate limited without reset header
        rate_limited_response = Mock()
        rate_limited_response.status_code = 429
        rate_limited_response.headers = {}  # No X-RateLimit-Reset
        rate_limited_response.text = "Rate limit exceeded"

        # Second attempt: also rate limited
        second_rate_limited = Mock()
        second_rate_limited.status_code = 429
        second_rate_limited.headers = {}
        second_rate_limited.text = "Rate limit exceeded"

        # Third attempt: successful
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "data": [{"attributes": {"message": "Finally got through!"}}],
            "meta": {"page": {}},
        }

        mock_post.side_effect = [
            rate_limited_response,
            second_rate_limited,
            success_response,
        ]

        # Execute
        result = self.toolset.fetch_pod_logs(self.fetch_params)

        # Verify
        assert result.status == ToolResultStatus.SUCCESS
        assert result.error is None

        # Verify three API calls were made (two failed with 429, one succeeded)
        assert mock_post.call_count == 3

    @patch("holmes.plugins.toolsets.datadog.datadog_api.requests.post")
    def test_fetch_pod_logs_no_config(self, mock_post):
        """Test fetch_pod_logs when dd_config is not set"""
        # Clear the config
        self.toolset.dd_config = None

        # Execute
        result = self.toolset.fetch_pod_logs(self.fetch_params)

        # Verify
        assert result.status == ToolResultStatus.ERROR
        assert result.data == "The toolset is missing its configuration"

        # Verify no API calls were made
        assert mock_post.call_count == 0

    @patch("holmes.plugins.toolsets.datadog.datadog_api.requests.post")
    @patch("time.sleep", return_value=None)  # Mock time.sleep to avoid delays
    def test_fetch_pod_logs_rate_limit_exhausted(self, mock_sleep, mock_post):
        """Test fetch_pod_logs when all rate limit retries are exhausted"""
        # Mock all responses as rate limited
        rate_limited_response = Mock()
        rate_limited_response.status_code = 429
        rate_limited_response.headers = {}
        rate_limited_response.text = "Rate limit exceeded"

        # Make all attempts return rate limited response
        mock_post.return_value = rate_limited_response

        # Execute
        result = self.toolset.fetch_pod_logs(self.fetch_params)

        # Verify
        assert result.status == ToolResultStatus.ERROR
        assert (
            "Datadog API rate limit exceeded. Failed after 5 retry attempts."
            in result.error
        )

        # Verify 5 API calls were made (MAX_RETRY_COUNT_ON_RATE_LIMIT)
        assert mock_post.call_count == 5

    @patch("holmes.plugins.toolsets.datadog.datadog_api.requests.post")
    def test_fetch_pod_logs_with_filter(self, mock_post):
        """Test fetch_pod_logs with search filter"""
        # Mock response
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": [
                {"attributes": {"message": "ERROR: Something went wrong"}},
                {"attributes": {"message": "ERROR: Another error occurred"}},
            ],
            "meta": {"page": {}},
        }

        mock_post.return_value = response

        # Set up params with filter
        params = FetchPodLogsParams(
            namespace="test-namespace",
            pod_name="test-pod",
            filter="ERROR",
            limit=100,
        )

        # Execute
        result = self.toolset.fetch_pod_logs(params)

        # Verify
        assert result.status == ToolResultStatus.SUCCESS

        # Check the API call included the filter
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        query = payload["filter"]["query"]
        assert "(ERROR)" in query  # Now wrapped in parentheses
        assert "kube_namespace:test-namespace" in query
        assert "pod_name:test-pod" in query

        # Verify response includes Datadog URL
        assert "View in Datadog:" in result.data

    @patch("holmes.plugins.toolsets.datadog.datadog_api.requests.post")
    def test_fetch_pod_logs_with_complex_filter(self, mock_post):
        """Test fetch_pod_logs with complex Datadog query syntax"""
        # Mock response
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": [
                {"attributes": {"message": "ERROR: Database error", "@level": "error"}},
            ],
            "meta": {"page": {}},
        }

        mock_post.return_value = response

        # Set up params with complex Datadog filter
        params = FetchPodLogsParams(
            namespace="test-namespace",
            pod_name="test-pod",
            filter="(error OR warn OR fatal) AND @level:error",
            limit=100,
        )

        # Execute
        result = self.toolset.fetch_pod_logs(params)

        # Verify
        assert result.status == ToolResultStatus.SUCCESS

        # Check the API call included the complex filter
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        query = payload["filter"]["query"]
        # The filter should be added as-is in parentheses
        assert "((error OR warn OR fatal) AND @level:error)" in query

    @patch("holmes.plugins.toolsets.datadog.datadog_api.requests.post")
    def test_fetch_pod_logs_with_exclude_filter(self, mock_post):
        """Test fetch_pod_logs with exclude filter using NOT syntax"""
        # Mock response
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": [
                {"attributes": {"message": "ERROR: Real error"}},
            ],
            "meta": {"page": {}},
        }

        mock_post.return_value = response

        # Test 1: exclude_filter without NOT prefix
        params = FetchPodLogsParams(
            namespace="test-namespace",
            pod_name="test-pod",
            exclude_filter="health",
            limit=100,
        )

        # Execute
        self.toolset.fetch_pod_logs(params)

        # Verify NOT was added automatically
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        query = payload["filter"]["query"]
        assert "NOT (health)" in query

        # Test 2: exclude_filter with NOT prefix already
        params2 = FetchPodLogsParams(
            namespace="test-namespace",
            pod_name="test-pod",
            exclude_filter="NOT (info OR debug)",
            limit=100,
        )

        # Execute
        self.toolset.fetch_pod_logs(params2)

        # Verify NOT wasn't duplicated
        call_args2 = mock_post.call_args
        payload2 = call_args2[1]["json"]
        query2 = payload2["filter"]["query"]
        assert "NOT (info OR debug)" in query2
        assert "NOT NOT" not in query2  # Ensure NOT wasn't duplicated

    @patch("holmes.plugins.toolsets.datadog.datadog_api.requests.post")
    def test_fetch_pod_logs_with_both_filters(self, mock_post):
        """Test fetch_pod_logs with both include and exclude filters"""
        # Mock response
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": [
                {"attributes": {"message": "ERROR: Database connection failed"}},
            ],
            "meta": {"page": {}},
        }

        mock_post.return_value = response

        params = FetchPodLogsParams(
            namespace="test-namespace",
            pod_name="test-pod",
            filter="@level:error OR @level:warn",
            exclude_filter="@http.status_code:200",
            limit=100,
        )

        # Execute
        self.toolset.fetch_pod_logs(params)

        # Verify both filters are in the query
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        query = payload["filter"]["query"]
        assert "(@level:error OR @level:warn)" in query
        assert "NOT (@http.status_code:200)" in query

    @patch("holmes.plugins.toolsets.datadog.datadog_api.requests.post")
    def test_fetch_pod_logs_datadog_url_generation(self, mock_post):
        """Test that Datadog Explorer URL is correctly generated"""
        # Mock response
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": [],
            "meta": {"page": {}},
        }

        mock_post.return_value = response

        params = FetchPodLogsParams(
            namespace="test-namespace",
            pod_name="test-pod",
            start_time="2024-01-01T00:00:00Z",
            end_time="2024-01-01T12:00:00Z",
        )

        # Execute
        result = self.toolset.fetch_pod_logs(params)

        # Verify URL is in the response
        assert result.status == ToolResultStatus.NO_DATA
        assert "View in Datadog: https://api.datadoghq.com/logs?" in result.data
        assert "query=kube_namespace%3Atest-namespace" in result.data
        assert "from_ts=2024-01-01T00%3A00%3A00Z" in result.data
        assert "to_ts=2024-01-01T12%3A00%3A00Z" in result.data


class TestDatadogPodLoggingTool:
    """Test the PodLoggingTool when used with Datadog"""

    def test_datadog_specific_tool_parameters(self):
        """Test that PodLoggingTool provides Datadog-specific parameter descriptions"""
        # Create toolset
        toolset = DatadogLogsToolset()
        toolset.dd_config = DatadogLogsConfig(
            dd_api_key="test-api-key",
            dd_app_key="test-app-key",
            site_api_url="https://api.datadoghq.com",
        )

        # Get the tool (it's created in __init__)
        tool = toolset.tools[0]
        assert isinstance(tool, PodLoggingTool)

        # Check tool description mentions Datadog
        assert "Datadog" in tool.description
        assert "Datadog's query syntax" in tool.description

        # Check filter parameter has Datadog-specific description
        filter_param = tool.parameters.get("filter")
        assert filter_param is not None
        assert "DATADOG QUERY SYNTAX" in filter_param.description
        assert "@level:error" in filter_param.description
        assert "OR queries" in filter_param.description

        # Check exclude_filter parameter has Datadog-specific description
        exclude_param = tool.parameters.get("exclude_filter")
        assert exclude_param is not None
        assert "DATADOG EXCLUSION SYNTAX" in exclude_param.description
        assert "NOT operator" in exclude_param.description
        assert "NOT @level:info" in exclude_param.description
