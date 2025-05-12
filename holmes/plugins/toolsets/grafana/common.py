import json
from typing import Dict, Optional
from pydantic import BaseModel
import datetime

from holmes.core.tools import StructuredToolResult, ToolResultStatus


class GrafanaConfig(BaseModel):
    """A config that represents one of the Grafana related tools like Loki or Tempo
    If `grafana_datasource_uid` is set, then it is assume that Holmes will proxy all
    requests through grafana. In this case `url` should be the grafana URL.
    If `grafana_datasource_uid` is not set, it is assumed that the `url` is the
    systems' URL
    """

    api_key: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    url: str
    grafana_datasource_uid: Optional[str] = None
    external_url: Optional[str] = None


def build_headers(api_key: Optional[str], additional_headers: Optional[Dict[str, str]]):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if additional_headers:
        headers.update(additional_headers)

    return headers


def format_log(log: Dict) -> str:
    log_str = log.get("log")
    timestamp_nanoseconds = log.get("timestamp")
    if not log_str:
        log_str = json.dumps(log)
    elif timestamp_nanoseconds:
        timestamp_seconds = int(timestamp_nanoseconds) // 1_000_000_000
        dt = datetime.datetime.fromtimestamp(timestamp_seconds)
        log_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ") + " " + log_str

    return log_str


def get_base_url(config: GrafanaConfig) -> str:
    if config.grafana_datasource_uid:
        return f"{config.url}/api/datasources/proxy/uid/{config.grafana_datasource_uid}"
    else:
        return config.url


def ensure_grafana_uid_or_return_error_result(
    config: GrafanaConfig,
) -> Optional[StructuredToolResult]:
    if not config.grafana_datasource_uid:
        return StructuredToolResult(
            status=ToolResultStatus.ERROR,
            error="This tool only works when the toolset is configued ",
        )
    else:
        return None
