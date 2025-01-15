
import logging
import os
import requests
from typing import Dict, List, Tuple, Optional
import backoff

def headers(api_key:str):
    return {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

GRAFANA_URL_ENV_NAME = "GRAFANA_URL"
GRAFANA_API_KEY_ENV_NAME = "GRAFANA_API_KEY"

def get_connection_info() -> Tuple[str, str]:

    grafana_url = os.environ.get(GRAFANA_URL_ENV_NAME)
    if not grafana_url:
        raise Exception(f'Missing env var {GRAFANA_URL_ENV_NAME}')
    api_key = os.environ.get(GRAFANA_API_KEY_ENV_NAME)
    if not api_key:
        raise Exception(f'Missing env var {GRAFANA_API_KEY_ENV_NAME}')
    return (grafana_url, api_key)

def parse_loki_response(results: List[Dict]) -> List[Dict]:
    """
    Parse Loki response into a more usable format

    Args:
        results: Raw results from Loki query

    Returns:
        List of formatted log entries
    """
    parsed_logs = []
    for result in results:
        stream = result.get('stream', {})
        for value in result.get('values', []):
            timestamp, log_line = value
            parsed_logs.append({
                'timestamp': timestamp,
                'log': log_line,
                'labels': stream
            })
    return parsed_logs

@backoff.on_exception(
    backoff.expo,  # Exponential backoff
    requests.exceptions.RequestException,  # Retry on request exceptions
    max_tries=5,  # Maximum retries
    giveup=lambda e: isinstance(e, requests.exceptions.HTTPError) and e.response.status_code < 500,
)
def execute_loki_query(
    loki_datasource_id: str,
    query: str,
    start: int,
    end: int,
    limit: int
) -> List[Dict]:
    """
    Execute a Loki query through Grafana with retry and backoff.

    Args:
        loki_datasource_id: The ID of the Loki datasource.
        query: Loki query string.
        start: Start of the time window to fetch the logs for (Epoch timestamp in seconds).
        end: End of the time window to fetch the logs for (Epoch timestamp in seconds).
        limit: Maximum number of log lines to return.

    Returns:
        List of log entries.
    """

    params = {
        'query': query,
        'limit': limit,
        'start': start,
        'end': end
    }

    try:
        (grafana_url, api_key) = get_connection_info()
        url = f'{grafana_url}/api/datasources/proxy/{loki_datasource_id}/loki/api/v1/query_range'
        response = requests.get(
            url,
            headers=headers(api_key=api_key),
            params=params
        )
        response.raise_for_status()

        result = response.json()
        if 'data' in result and 'result' in result['data']:
            return parse_loki_response(result['data']['result'])
        return []

    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to query Loki logs: {str(e)}")


@backoff.on_exception(
    backoff.expo,  # Exponential backoff
    requests.exceptions.RequestException,  # Retry on request exceptions
    max_tries=5,  # Maximum retries
    giveup=lambda e: isinstance(e, requests.exceptions.HTTPError) and e.response.status_code < 500,
)
def list_grafana_datasources(source_name: Optional[str] = None) -> List[Dict]:
    """
    List all configured datasources from a Grafana instance with retry and backoff.

    Args:
        source_name: Optional. Filter for datasources matching this type.

    Returns:
        List of datasource configurations.
    """
    try:
        grafana_url, api_key = get_connection_info()
        url = f'{grafana_url}/api/datasources'
        headers_ = headers(api_key=api_key)
        
        logging.info(f"Fetching datasources from: {url}")
        response = requests.get(url, headers=headers_, timeout=10)  # Added timeout
        response.raise_for_status()

        datasources = response.json()
        if not source_name:
            return datasources

        relevant_datasources = [
            ds for ds in datasources
            if ds['type'].lower() == source_name.lower()
        ]

        for ds in relevant_datasources:
            logging.info(f"Found datasource: {ds['name']} (type: {ds['type']}, id: {ds['id']})")

        return relevant_datasources
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to list datasources: {str(e)}")

def query_loki_logs_by_node(
    loki_datasource_id:str,
    node_name: str,
    start: int,
    end: int,
    node_name_search_key: str = "node",
    limit: int = 1000) -> List[Dict]:
    """
    Query Loki logs filtered by node name

    Args:
        node_name: Kubernetes node name
        start: Start of the time window to fetch the logs for. Epoch timestamp in seconds
        end: End of the time window to fetch the logs for. Epoch timestamp in seconds
        limit: Maximum number of log lines to return

    Returns:
        List of log entries
    """

    query = f'{{{node_name_search_key}="{node_name}"}}'

    return execute_loki_query(
        loki_datasource_id=loki_datasource_id,
        query=query,
        start=start,
        end=end,
        limit=limit)

def query_loki_logs_by_pod(
    loki_datasource_id:str,
    namespace: str,
    pod_regex: str,
    start: int,
    end: int,
    pod_name_search_key: str = "pod",
    namespace_search_key: str = "namespace",
    limit: int = 1000) -> List[Dict]:
    """
    Query Loki logs filtered by namespace and pod name regex

    Args:
        namespace: Kubernetes namespace
        pod_regex: Regular expression to match pod names
        start: Start of the time window to fetch the logs for. Epoch timestamp in seconds
        end: End of the time window to fetch the logs for. Epoch timestamp in seconds
        limit: Maximum number of log lines to return

    Returns:
        List of log entries
    """

    query = f'{{{namespace_search_key}="{namespace}", {pod_name_search_key}=~"{pod_regex}"}}'
    return execute_loki_query(
        loki_datasource_id=loki_datasource_id,
        query=query,
        start=start,
        end=end,
        limit=limit)
