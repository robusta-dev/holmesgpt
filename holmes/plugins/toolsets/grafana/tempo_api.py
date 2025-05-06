import requests
from typing import Dict, List, Optional
import backoff

from holmes.plugins.toolsets.grafana.common import build_headers
from holmes.plugins.toolsets.grafana.trace_parser import process_trace


def execute_tempo_query_with_retry(
    grafana_url: str,
    api_key: Optional[str],
    headers: Optional[Dict[str, str]],
    tempo_datasource_uid: str,
    query_params: dict,
    retries: int = 3,
    timeout: int = 5,
):
    """
    Execute a Tempo API query through Grafana with retries and timeout.

    Args:
        tempo_datasource_uid: The UID of the Tempo datasource.
        query_params: Query parameters for the API.
        retries: Number of retries for the request.
        timeout: Timeout for each request in seconds.

    Returns:
        List of trace results.
    """
    url = f"{grafana_url}/api/datasources/proxy/uid/{tempo_datasource_uid}/api/search"

    @backoff.on_exception(
        backoff.expo,  # Exponential backoff
        requests.exceptions.RequestException,  # Retry on request exceptions
        max_tries=retries,  # Maximum retries
        giveup=lambda e: isinstance(e, requests.exceptions.HTTPError)
        and e.response.status_code < 500,
    )
    def make_request():
        response = requests.post(
            url,
            headers=build_headers(api_key=api_key, additional_headers=headers),
            json=query_params,
            timeout=timeout,  # Set timeout for the request
        )
        response.raise_for_status()  # Raise an error for non-2xx responses
        return response.json()

    try:
        return make_request()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request to Tempo API failed after retries: {e}")


def query_tempo_traces(
    grafana_url: str,
    api_key: Optional[str],
    headers: Optional[Dict[str, str]],
    tempo_datasource_uid: str,
    query: Optional[str],
    start: int,
    end: int,
    limit: int,
) -> Dict:
    """
    Query Tempo for traces exceeding a minimum duration.

    Args:
        tempo_datasource_uid: The UID of the Tempo datasource.
        min_duration: Minimum duration for traces (e.g., "5s").
        start: Start of the time range (epoch in seconds).
        end: End of the time range (epoch in seconds).
        limit: Maximum number of traces to return.

    Returns:
        List of trace results.
    """
    query_params = {
        "start": str(start),
        "end": str(end),
        "limit": str(limit),
    }

    if query:
        query_params["q"] = query
    data = execute_tempo_query_with_retry(
        grafana_url=grafana_url,
        api_key=api_key,
        headers=headers,
        tempo_datasource_uid=tempo_datasource_uid,
        query_params=query_params,
    )
    return data


def query_tempo_trace_by_id(
    grafana_url: str,
    api_key: Optional[str],
    headers: Optional[Dict[str, str]],
    tempo_datasource_uid: str,
    trace_id: str,
    key_labels: List[str],
    retries: int = 3,
    timeout: int = 5,
) -> str:
    """
    Query Tempo for a specific trace by its ID with retries and backoff.

    Args:
        tempo_datasource_id: The ID of the Tempo datasource.
        trace_id: The trace ID to retrieve.
        retries: Number of retries for the request.
        timeout: Timeout for each request in seconds.

    Returns:
        A formatted trace details string
    """
    url = f"{grafana_url}/api/datasources/proxy/uid/{tempo_datasource_uid}/api/traces/{trace_id}"

    @backoff.on_exception(
        backoff.expo,
        requests.exceptions.RequestException,
        max_tries=retries,
        giveup=lambda e: isinstance(e, requests.exceptions.HTTPError)
        and e.response.status_code < 500,
    )
    def make_request():
        response = requests.get(
            url,
            headers=build_headers(api_key=api_key, additional_headers=headers),
            timeout=timeout,
        )
        response.raise_for_status()
        return process_trace(response.json(), key_labels)

    try:
        return make_request()
    except requests.exceptions.RequestException as e:
        raise Exception(
            f"Failed to retrieve trace by ID after retries: {e} \n for URL: {url}"
        )
