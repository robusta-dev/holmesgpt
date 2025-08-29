import logging
import requests  # type: ignore
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
def grafana_health_check(config: GrafanaConfig) -> Tuple[bool, str]:
    base_url = get_base_url(config)
    url = f"{base_url}/{config.healthcheck}"
    try:
        headers_ = build_headers(api_key=config.api_key, additional_headers=None)

        response = requests.get(url, headers=headers_, timeout=10)  # Added timeout
        response.raise_for_status()
        return True, ""
    except Exception as e:
        logging.error(f"Failed to fetch grafana health status at {url}", exc_info=True)
        error_msg = f"Failed to fetch grafana health status at {url}. {str(e)}"

        # Add helpful hint if this looks like a common misconfiguration
        if config.grafana_datasource_uid and ":3100" in config.url:
            error_msg += (
                "\n\nPossible configuration issue: grafana_datasource_uid is set but URL contains port 3100 "
                "(typically used for direct Loki connections). Please verify:\n"
                "- If connecting directly to Loki: remove grafana_datasource_uid from config\n"
                "- If connecting via Grafana proxy: ensure URL points to Grafana (usually port 3000)"
            )

        return False, error_msg
