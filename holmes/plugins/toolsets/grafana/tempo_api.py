
import requests
from typing import Dict, List
import backoff

def execute_tempo_query_with_retry(
    grafana_url:str,
    api_key: str,
    tempo_datasource_id: str,
    query_params: dict,
    retries: int = 3,
    timeout: int = 5):
    """
    Execute a Tempo API query through Grafana with retries and timeout.

    Args:
        tempo_datasource_id: The ID of the Tempo datasource.
        query_params: Query parameters for the API.
        retries: Number of retries for the request.
        timeout: Timeout for each request in seconds.

    Returns:
        List of trace results.
    """
    url = f'{grafana_url}/api/datasources/proxy/{tempo_datasource_id}/api/search'

    @backoff.on_exception(
        backoff.expo,  # Exponential backoff
        requests.exceptions.RequestException,  # Retry on request exceptions
        max_tries=retries,  # Maximum retries
        giveup=lambda e: isinstance(e, requests.exceptions.HTTPError) and e.response.status_code < 500,
    )
    def make_request():
        response = requests.post(
            url,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            json=query_params,
            timeout=timeout,  # Set timeout for the request
        )
        response.raise_for_status()  # Raise an error for non-2xx responses
        return response.json()

    try:
        return make_request()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request to Tempo API failed after retries: {e}")


def query_tempo_traces_by_duration(
    grafana_url:str,
    api_key: str,
    tempo_datasource_id: str,
    min_duration: str,
    start: int,
    end: int,
    limit: int = 50,
) -> List[Dict]:
    """
    Query Tempo for traces exceeding a minimum duration.

    Args:
        tempo_datasource_id: The ID of the Tempo datasource.
        min_duration: Minimum duration for traces (e.g., "5s").
        start: Start of the time range (epoch in seconds).
        end: End of the time range (epoch in seconds).
        limit: Maximum number of traces to return.

    Returns:
        List of trace results.
    """
    query_params = {
        "minDuration": min_duration,
        "start": str(start),
        "end": str(end),
        "limit": str(limit),
    }
    return execute_tempo_query_with_retry(grafana_url, api_key, tempo_datasource_id, query_params)


def query_tempo_trace_by_id(
    grafana_url:str,
    api_key: str,
    tempo_datasource_id: str,
    trace_id: str,
    retries: int = 3,
    timeout: int = 5,
) -> Dict:
    """
    Query Tempo for a specific trace by its ID with retries and backoff.

    Args:
        tempo_datasource_id: The ID of the Tempo datasource.
        trace_id: The trace ID to retrieve.
        retries: Number of retries for the request.
        timeout: Timeout for each request in seconds.

    Returns:
        Trace details.
    """
    url = f'{grafana_url}/api/datasources/proxy/{tempo_datasource_id}/api/traces/{trace_id}'

    @backoff.on_exception(
        backoff.expo,  # Exponential backoff
        requests.exceptions.RequestException,  # Retry on request exceptions
        max_tries=retries,  # Maximum retries
        giveup=lambda e: isinstance(e, requests.exceptions.HTTPError) and e.response.status_code < 500,
    )
    def make_request():
        response = requests.get(
            url,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Accept': 'application/json',
            },
            timeout=timeout,  # Set timeout for the request
        )
        response.raise_for_status()  # Raise an error for non-2xx responses
        return process_trace_json(response.json())

    try:
        return make_request()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to retrieve trace by ID after retries: {e} \n for URL: {url}")

def process_trace_json(trace_json):
    result = {
        "total_elapsed_time_ms": 0,
        "applications": []
    }

    # First pass: Collect basic details about spans
    spans_info = {}
    for batch in trace_json.get("batches", []):
        attributes = batch.get("resource", {}).get("attributes", [])
        app_name = None
        service_name = None
        for attr in attributes:
            key = attr.get("key")
            value = attr.get("value", {}).get("stringValue")
            if key == "app":
                app_name = value

        scope_spans = batch.get("scopeSpans", [])
        for scope_span in scope_spans:
            spans = scope_span.get("spans", [])
            for span in spans:
                span_id = span.get("spanId")
                parent_span_id = span.get("parentSpanId")
                start_time = int(span.get("startTimeUnixNano", 0))
                end_time = int(span.get("endTimeUnixNano", 0))
                elapsed_time_ns = end_time - start_time

                spans_info[span_id] = {
                    "app_name": app_name,
                    "service_name": service_name,
                    "parent_span_id": parent_span_id,
                    "elapsed_time_ms": elapsed_time_ns / 1_000_000,
                    "exclusive_time_ms": elapsed_time_ns / 1_000_000,
                    "start_time": start_time,
                    "end_time": end_time,
                    "loki_labels": {"app": app_name}
                }

    # Second pass: Subtract child span times from parent spans
    for span_id, span_data in spans_info.items():
        parent_span_id = span_data["parent_span_id"]
        if parent_span_id in spans_info:
            parent_data = spans_info[parent_span_id]
            parent_data["exclusive_time_ms"] -= span_data["elapsed_time_ms"]

    # Build the result
    for span_id, span_data in spans_info.items():
        app_info = {
            "app_name": span_data["app_name"],
            "service_name": span_data["service_name"],
            #"elapsed_time_ms": span_data["elapsed_time_ms"], # this confuses the llm
            "elapsed_service_time_ms": span_data["exclusive_time_ms"],
            "start_time": span_data["start_time"],
            "end_time": span_data["end_time"],
            "loki_labels": span_data["loki_labels"]
        }

        if app_info["app_name"]:
            result["applications"].append(app_info)

    # Set the total elapsed time to the root span's time (if available)
    root_span = max(spans_info.values(), key=lambda x: x["elapsed_time_ms"], default=None)
    if root_span:
        result["total_elapsed_time_ms"] = root_span["elapsed_time_ms"]

    return result
