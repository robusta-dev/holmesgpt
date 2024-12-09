
import os
import requests
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

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

def execute_loki_query(
    loki_datasource_uid:str,
    query: str,
    time_range_minutes: int,
    limit: int) -> List[Dict]:
    """
    Execute a Loki query through Grafana

    Args:
        query: Loki query string
        time_range_minutes: Time range to query in minutes
        limit: Maximum number of log lines to return

    Returns:
        List of log entries
    """

    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=time_range_minutes)

    params = {
        'query': query,
        'limit': limit,
        'start': int(start_time.timestamp() * 1000),
        'end': int(end_time.timestamp() * 1000)
    }


    try:
        (grafana_url, api_key) = get_connection_info()
        response = requests.get(
            f'{grafana_url}/api/datasources/proxy/{loki_datasource_uid}/loki/api/v1/query_range',
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

def list_loki_datasources() -> List[Dict]:
    """
    List all configured Loki datasources from a Grafana instance

    Returns:
        List of Loki datasource configurations
    """
    try:
        (grafana_url, api_key) = get_connection_info()
        response = requests.get(
            f'{grafana_url}/api/datasources',
            headers=headers(api_key=api_key)
        )
        response.raise_for_status()
        datasources = response.json()

        # Print datasources for debugging
        loki_datasources = []
        for ds in datasources:
            print(f"Found datasource: {ds['name']} (type: {ds['type']}, uid: {ds['uid']})")
            if ds['type'].lower() == 'loki':
                loki_datasources.append(ds)

        return loki_datasources
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to list datasources: {str(e)}")

def query_loki_logs_by_node(
    loki_datasource_uid:str,
    node_name: str,
    time_range_minutes: int = 60,
    limit: int = 1000) -> List[Dict]:
    """
    Query Loki logs filtered by node name

    Args:
        node_name: Kubernetes node name
        time_range_minutes: Time range to query in minutes
        limit: Maximum number of log lines to return

    Returns:
        List of log entries
    """

    query = f'{{node="{node_name}"}}'
    return execute_loki_query(
        loki_datasource_uid=loki_datasource_uid,
        query=query,
        time_range_minutes=time_range_minutes,
        limit=limit)

def query_loki_logs_by_pod(
    loki_datasource_uid:str,
    namespace: str,
    pod_regex: str,
    time_range_minutes: int = 60,
    limit: int = 1000) -> List[Dict]:
    """
    Query Loki logs filtered by namespace and pod name regex

    Args:
        namespace: Kubernetes namespace
        pod_regex: Regular expression to match pod names
        time_range_minutes: Time range to query in minutes
        limit: Maximum number of log lines to return

    Returns:
        List of log entries
    """

    query = f'{{namespace="{namespace}", pod=~"{pod_regex}"}}'

    return execute_loki_query(
        loki_datasource_uid=loki_datasource_uid,
        query=query,
        time_range_minutes=time_range_minutes,
        limit=limit)
