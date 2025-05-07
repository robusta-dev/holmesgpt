import json
from typing import Dict, Optional
from pydantic import BaseModel
import datetime


class GrafanaConfig(BaseModel):
    api_key: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    url: str
    grafana_datasource_uid: str
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
