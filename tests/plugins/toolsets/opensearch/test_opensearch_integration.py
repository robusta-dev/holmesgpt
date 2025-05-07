import pytest
import json
import os

from holmes.core.tools import ToolResultStatus
from holmes.plugins.toolsets.opensearch.opensearch_logs import (
    GetLogFields,
    OpenSearchLogsToolset,
)
from holmes.plugins.toolsets.opensearch.opensearch_utils import OpenSearchIndexConfig

REQUIRED_ENV_VARS = [
    "TEST_OPENSEARCH_URL",
    "TEST_OPENSEARCH_INDEX",
    "TEST_OPENSEARCH_AUTH_HEADER",
]

# Check if any required environment variables are missing
missing_vars = [var for var in REQUIRED_ENV_VARS if os.environ.get(var) is None]

pytestmark = pytest.mark.skipif(
    len(missing_vars) > 0,
    reason=f"Missing required environment variables: {', '.join(missing_vars)}",
)


class TestGetLogFieldsIntegration:
    """
    Integration tests that connect to a real OpenSearch instance.
    These tests help verify both the script-based and mappings-based field discovery methods.
    """

    @pytest.fixture
    def opensearch_config(self) -> OpenSearchIndexConfig:
        # All required env vars should be present due to the pytestmark skipif
        # This is defensive programming in case the test is run directly
        for var in REQUIRED_ENV_VARS:
            if os.environ.get(var) is None:
                pytest.skip(f"Missing required environment variable: {var}")

        return OpenSearchIndexConfig(
            opensearch_url=os.environ["TEST_OPENSEARCH_URL"],
            index_pattern=os.environ["TEST_OPENSEARCH_INDEX"],
            opensearch_auth_header=os.environ["TEST_OPENSEARCH_AUTH_HEADER"],
            fields_ttl_seconds=60,  # Short TTL for testing
        )

    @pytest.fixture
    def opensearch_logs_toolset(self, opensearch_config) -> OpenSearchLogsToolset:
        """Create an OpenSearchLogsToolset with the test configuration"""
        toolset = OpenSearchLogsToolset()
        toolset.config = opensearch_config
        return toolset

    def test_get_fields_using_mappings(self, opensearch_logs_toolset):
        toolset = opensearch_logs_toolset

        toolset.config.use_script_for_fields_discovery = False

        get_fields_tool = GetLogFields(toolset=toolset)
        result = get_fields_tool._invoke({})

        assert result.status == ToolResultStatus.SUCCESS
        assert result.data

        data = json.loads(result.data)
        assert "fields" in data
        fields = data["fields"]

        assert len(fields) > 0
        assert isinstance(fields, list)
        assert all(isinstance(field, dict) for field in fields)

        field_names = [field["name"] for field in fields]

        common_fields = [
            "@timestamp",
            "message",
            "kubernetes.namespace_name",
            "kubernetes.pod_name",
        ]

        found_common = any(field_name in field_names for field_name in common_fields)
        assert found_common, f"None of the expected common fields {common_fields} were found in the results: {field_names[:10]}..."

        for field in fields:
            assert "name" in field, f"Field missing 'name' property: {field}"
            assert "type" in field, f"Field missing 'type' property: {field}"
            assert "indexes" in field, f"Field missing 'indexes' property: {field}"
            assert isinstance(
                field["indexes"], list
            ), f"Field 'indexes' is not a list: {field}"
            assert len(field["indexes"]) > 0, f"Field 'indexes' is empty: {field}"

        assert field_names == sorted(field_names)

    def test_get_fields_using_script(self, opensearch_logs_toolset):
        toolset = opensearch_logs_toolset

        toolset.config.use_script_for_fields_discovery = True

        get_fields_tool = GetLogFields(toolset=toolset)
        result = get_fields_tool._invoke({})

        assert result.status == ToolResultStatus.SUCCESS

        assert result.data is not None
        assert len(result.data) > 0

        assert '"hits"' in result.data
        assert '"all_fields"' in result.data

        for field_name in ["@timestamp", "kubernetes.namespace_name"]:
            assert field_name in result.data
