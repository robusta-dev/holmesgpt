import re
import logging

from typing import Any, Union

import requests
from pydantic import BaseModel
from holmes.core.tools import StaticPrerequisite, Tool, ToolParameter, Toolset, ToolsetTag
import json
from pip._vendor.requests import RequestException

from urllib.parse import urljoin
# https://prometheus.io/docs/prometheus/latest/querying/api/#http-api
# http://localhost:9090/api/v1/series?match[]=container_network_receive_bytes_total{namespace="default"}

# Imagine you're a PromQL expert. If it's relevant to the investigation, attempt to build
# a PromQL query to visualize the issue using ONLY available PromQL metrics and not the
# others. When constructing the query, ensure it's functional by verifying its correctness.
# Respond strictly in the following format and nothing else:: << { type: "graph",
# promQL: "PROMQL_HERE", description: "DESCRIPTION_HERE" } >>(Note: do NOT include any
# explanations, comments, titles, headers or additional text, related to this query,
# outside this format)

class PrometheusConfig(BaseModel):
    url: Union[str, None]

class ListAvailableMetrics(Tool):
    def __init__(self, config:PrometheusConfig):
        super().__init__(
            name="list_available_metrics",
            description="List all the available metrics to query from prometheus. This is necessary information prior to querying data.",
            parameters={},
        )
        self._config = config

    def invoke(self, params: Any) -> str:
        if not self._config.url:
            return "Prometheus is not configured. Prometheus URL is missing"
        try:
            api_endpoint = urljoin(self._config.url, '/api/v1/label/__name__/values')

            response = requests.get(
                api_endpoint,
                timeout=10,  # Add timeout to prevent hanging
                verify=True  # SSL verification
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success' and 'data' in data:
                    metrics_list = data['data']
                    if not metrics_list:
                        return "No metrics found in Prometheus."
                    formatted_response = "Available metrics:\n" + "\n".join(metrics_list)
                    return formatted_response
                else:
                    return f"Invalid response format from Prometheus. Response: {data}"
            else:
                return f"Unexpected HTTP status code: {response.status_code}. {response.text}"

        except Exception as e:
            return f"Unexpected error: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        return "listed available prometheus metrics"




class ListPrometheusSeries(Tool):
    def __init__(self, config: PrometheusConfig):
        super().__init__(
            name="list_prometheus_series",
            description="List all available time series in Prometheus.",
            parameters={
                "match": ToolParameter(
                    description="Repeated series selector argument that selects the series to return. At least one value must be provided",
                    type="array[string]",
                    required=True,
                ),
                "start": ToolParameter(
                    description="Start timestamp. <rfc3339 | unix_timestamp>",
                    type="string",
                    required=False,
                ),
                "end": ToolParameter(
                    description="End timestamp. <rfc3339 | unix_timestamp>",
                    type="string",
                    required=False,
                ),
                "limit": ToolParameter(
                    description="Maximum number of returned series. Optional. 0 means disabled",
                    type="number",
                    required=False,
                )
            },
        )
        self._config = config

    def invoke(self, params: Any) -> str:
        if not self._config.url:
            return "Prometheus is not configured. Prometheus URL is missing"

        try:
            api_endpoint = urljoin(self._config.url, '/api/v1/series')

            query_params = {}

            if not params.get('match'):
                return "match parameter is required"
            query_params['match[]'] = params['match']

            # Handle optional parameters
            if params.get('start'):
                query_params['start'] = params['start']
            if params.get('end'):
                query_params['end'] = params['end']
            if params.get('limit'):
                query_params['limit'] = params['limit']

            response = requests.get(
                api_endpoint,
                params=query_params,
                timeout=10,
                verify=True
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success' and 'data' in data:
                    series_list = data['data']
                    if not series_list:
                        return "No series found in Prometheus."
                    formatted_response = "Available series:\n" + "\n".join(
                        [str(series) for series in series_list]
                    )
                    return formatted_response
                else:
                    return f"Invalid response format from Prometheus. Response: {data}"
            else:
                return f"Unexpected HTTP status code: {response.status_code}. {response.text}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        match_str = ', '.join(params.get('match', []))
        return f"listed prometheus series matching: {match_str}"

class ListPrometheusLabels(Tool):
    def __init__(self, config: PrometheusConfig):
        super().__init__(
            name="list_prometheus_labels",
            description="List all available label names in Prometheus.",
            parameters={},
        )
        self._config = config

    def invoke(self, params: Any) -> str:
        if not self._config.url:
            return "Prometheus is not configured. Prometheus URL is missing"
        try:
            api_endpoint = urljoin(self._config.url, '/api/v1/labels')

            response = requests.get(
                api_endpoint,
                timeout=10,
                verify=True
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success' and 'data' in data:
                    labels_list = data['data']
                    if not labels_list:
                        return "No labels found in Prometheus."
                    formatted_response = "Available labels:\n" + "\n".join(labels_list)
                    return formatted_response
                else:
                    return f"Invalid response format from Prometheus. Response: {data}"
            else:
                return f"Unexpected HTTP status code: {response.status_code}. {response.text}"

        except Exception as e:
            return f"Unexpected error: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        return "listed prometheus labels"

class ListLabelValues(Tool):
    def __init__(self, config: PrometheusConfig):
        super().__init__(
            name="list_prometheus_label_values",
            description="List all possible values for a specific label in Prometheus.",
            parameters={
                "label_name": ToolParameter(
                    description="The name of the label to get values for",
                    type="string",
                    required=True,
                )
            }
        )
        self._config = config

    def invoke(self, params: Any) -> str:
        if not self._config.url:
            return "Prometheus is not configured. Prometheus URL is missing"
        try:
            label_name = params.get('label_name')
            api_endpoint = urljoin(self._config.url, f'/api/v1/label/{label_name}/values')

            response = requests.get(
                api_endpoint,
                timeout=10,
                verify=True
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success' and 'data' in data:
                    values_list = data['data']
                    if not values_list:
                        return f"No values found for label '{label_name}'."
                    formatted_response = f"Values for label '{label_name}':\n" + "\n".join(values_list)
                    return formatted_response
                else:
                    return f"Invalid response format from Prometheus. Response: {data}"
            else:
                return f"Unexpected HTTP status code: {response.status_code}. {response.text}"

        except Exception as e:
            return f"Unexpected error: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        return f"listed values for label '{params.get('label_name')}'"

class ExecutePromQLQuery(Tool):
    def __init__(self, config:PrometheusConfig):
        super().__init__(
            name="execute_prometheus_query",
            description="Execute a PromQL query",
            parameters={
                "type": ToolParameter(
                    description="The type of query. One of query, query_range",
                    type="string",
                    required=True,
                ),
                "query": ToolParameter(
                    description="The PromQL query",
                    type="string",
                    required=True,
                ),
                "description": ToolParameter(
                    description="Describes the query",
                    type="string",
                    required=True,
                )
            },
        )
        self._config = config

    def invoke(self, params: Any) -> str:
        if not self._config.url:
            return "Prometheus is not configured. Prometheus URL is missing"

        try:
            # Extract parameters
            query_type = params.get("type", "").strip().lower()
            query = params.get("query", "")

            # Determine the endpoint based on query type
            if query_type == "query":
                endpoint = "/api/v1/query"
            elif query_type == "query_range":
                endpoint = "/api/v1/query_range"
            else:
                return f"Error: Invalid query type '{query_type}'. Expected 'query' or 'query_range'."

            url = urljoin(self._config.url, endpoint)

            payload = {
                "query": query
            }

            response = requests.post(
                url=url,
                data=payload,
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                return json.dumps(data)

            # Handle known Prometheus error status codes
            error_msg = "Unknown error occurred"
            if response.status_code in [400, 429]:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", error_data.get("message", str(response.content)))
                except json.JSONDecodeError:
                    pass
                return f"Query execution failed. HTTP {response.status_code}: {error_msg}"

            # For other status codes, just return the status code and content
            return f"Query execution failed with unexpected status code: {response.status_code}. Response: {response.content}"

        except RequestException as e:
            logging.info("Failed to connect to Prometheus", exc_info=True)
            return f"Connection error to Prometheus: {str(e)}"
        except Exception as e:
            logging.info("Failed to connect to Prometheus", exc_info=True)
            return f"Unexpected error executing query: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        return f'<< { type: "{params.get("type")}", promQL: "{params.get("query")}", description: "{params.get("description")}" } >>'

class PrometheusToolset(Toolset):
    def __init__(self, config:PrometheusConfig):
        super().__init__(
            name="prometheus",
            description="Prometheus integration to fetch metadata and execute PromQL queries",
            icon_url="https://platform.robusta.dev/demos/internet-access.svg",
            prerequisites=[
                StaticPrerequisite(enabled=config.url is not None, disabled_reason="Prometheus URL is not set")
            ],
            tools=[
                ListAvailableMetrics(config),
                ListPrometheusSeries(config),
                ListPrometheusLabels(config),
                ListLabelValues(config),
                ExecutePromQLQuery(config)
            ],
            tags=[ToolsetTag.CORE,]
        )
