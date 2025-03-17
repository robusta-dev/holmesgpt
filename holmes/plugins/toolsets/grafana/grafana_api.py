import logging
import requests
from typing import Any, Dict, List, Optional
import backoff

from holmes.plugins.toolsets.grafana.common import headers


@backoff.on_exception(
    backoff.expo,  # Exponential backoff
    requests.exceptions.RequestException,  # Retry on request exceptions
    max_tries=5,  # Maximum retries
    giveup=lambda e: isinstance(e, requests.exceptions.HTTPError)
    and e.response.status_code < 500,
)
def list_grafana_datasources(
    grafana_url: str, api_key: str, datasource_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all configured datasources from a Grafana instance with retry and backoff.

    Args:
        source_name: Optional. Filter for datasources matching this type.

    Returns:
        List of datasource configurations.
    """
    try:
        url = f"{grafana_url}/api/datasources"
        headers_ = headers(api_key=api_key)

        logging.info(f"Fetching datasources from: {url}")
        response = requests.get(url, headers=headers_, timeout=10)  # Added timeout
        response.raise_for_status()

        datasources = response.json()
        if not datasource_type:
            return datasources

        relevant_datasources = [
            ds for ds in datasources if ds["type"].lower() == datasource_type.lower()
        ]

        for ds in relevant_datasources:
            logging.info(
                f"Found datasource: {ds['name']} (type: {ds['type']}, id: {ds['id']})"
            )

        return relevant_datasources
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to list datasources: {str(e)}")


@backoff.on_exception(
    backoff.expo,  # Exponential backoff
    requests.exceptions.RequestException,  # Retry on request exceptions
    max_tries=5,  # Maximum retries
    giveup=lambda e: isinstance(e, requests.exceptions.HTTPError)
    and e.response.status_code < 500,
)
def get_health(grafana_url: str, api_key: str) -> bool:
    url = f"{grafana_url}/api/health"
    try:
        headers_ = headers(api_key=api_key)

        response = requests.get(url, headers=headers_, timeout=10)  # Added timeout
        response.raise_for_status()
        return True
    except Exception:
        logging.error(f"Failed to fetch grafana health status at {url}", exc_info=True)
        return False
