import requests
from typing import Dict, List, Optional, Union
import backoff

from holmes.plugins.toolsets.grafana.common import build_headers


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
        stream = result.get("stream", {})
        for value in result.get("values", []):
            timestamp, log_line = value
            parsed_logs.append(
                {"timestamp": timestamp, "log": log_line, "labels": stream}
            )
    return parsed_logs


@backoff.on_exception(
    backoff.expo,  # Exponential backoff
    requests.exceptions.RequestException,  # Retry on request exceptions
    max_tries=5,  # Maximum retries
    giveup=lambda e: isinstance(e, requests.exceptions.HTTPError)
    and e.response.status_code < 500,
)
def execute_loki_query(
    grafana_url: str,
    api_key: Optional[str],
    headers: Optional[Dict[str, str]],
    loki_datasource_uid: str,
    query: str,
    start: Union[int, str],
    end: Union[int, str],
    limit: int,
) -> List[Dict]:
    params = {"query": query, "limit": limit, "start": start, "end": end}
    try:
        url = f"{grafana_url}/api/datasources/proxy/uid/{loki_datasource_uid}/loki/api/v1/query_range"
        response = requests.get(
            url,
            headers=build_headers(api_key=api_key, additional_headers=headers),
            params=params,
        )
        response.raise_for_status()

        result = response.json()
        if "data" in result and "result" in result["data"]:
            return parse_loki_response(result["data"]["result"])
        return []

    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to query Loki logs: {str(e)}")


def query_loki_logs_by_label(
    grafana_url: str,
    api_key: Optional[str],
    headers: Optional[Dict[str, str]],
    loki_datasource_uid: str,
    namespace: str,
    label_value: str,
    filter_regexp: Optional[str],
    start: Union[int, str],
    end: Union[int, str],
    label: str,
    namespace_search_key: str = "namespace",
    limit: int = 200,
) -> List[Dict]:
    query = f'{{{namespace_search_key}="{namespace}", {label}=~"{label_value}"}}'
    if filter_regexp:
        query += f' |~ "{filter_regexp}"'
    return execute_loki_query(
        grafana_url=grafana_url,
        api_key=api_key,
        headers=headers,
        loki_datasource_uid=loki_datasource_uid,
        query=query,
        start=start,
        end=end,
        limit=limit,
    )
