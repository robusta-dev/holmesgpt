import logging
import requests
from typing import Tuple
import backoff

from holmes.plugins.toolsets.grafana.common import (
    GrafanaConfig,
    build_headers,
    get_base_url,
)


@backoff.on_exception(
    backoff.expo,  # Exponential backoff
    requests.exceptions.RequestException,  # Retry on request exceptions
    max_tries=5,  # Maximum retries
    giveup=lambda e: isinstance(e, requests.exceptions.HTTPError)
    and e.response.status_code < 500,
)
def get_health(config: GrafanaConfig) -> Tuple[bool, str]:
    base_url = get_base_url(config)

    # Both loki and tempo provide the same /ready api
    url = f"{base_url}/ready"
    try:
        headers_ = build_headers(api_key=config.api_key, additional_headers=None)

        response = requests.get(url, headers=headers_, timeout=10)  # Added timeout
        response.raise_for_status()
        return True, ""
    except Exception as e:
        logging.error(f"Failed to fetch grafana health status at {url}", exc_info=True)
        return False, f"Failed to fetch grafana health status at {url}. {str(e)}"
