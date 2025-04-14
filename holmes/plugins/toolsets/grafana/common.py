import json
from typing import Dict, Optional
from pydantic import BaseModel
import datetime


class GrafanaConfig(BaseModel):
    api_key: str
    url: str
    grafana_datasource_uid: str
    external_url: Optional[str] = None


def headers(api_key: str):
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


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
