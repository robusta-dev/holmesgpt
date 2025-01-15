
from typing import Dict, List, Optional, Union, Tuple
import uuid
import time
import os
from pydantic import BaseModel

from holmes.core.tools import StaticPrerequisite

GRAFANA_URL_ENV_NAME = "GRAFANA_URL"
GRAFANA_API_KEY_ENV_NAME = "GRAFANA_API_KEY"
ONE_HOUR_IN_SECONDS = 3600

class GrafanaLokiConfig(BaseModel):
    enabled: bool = True # ability to disable Loki toolset even if Tempo toolset is enabled
    pod_name_search_key: str = "pod"
    namespace_search_key: str = "namespace"
    node_name_search_key: str = "node"

class GrafanaTempoConfig(BaseModel):
    enabled: bool = True # ability to disable Tempo toolset even if Loki toolset is enabled

class GrafanaConfig(BaseModel):
    loki: GrafanaLokiConfig = GrafanaLokiConfig()
    tempo: GrafanaTempoConfig = GrafanaTempoConfig()
    api_key: str = os.environ.get(GRAFANA_API_KEY_ENV_NAME, "")
    url: str = os.environ.get(GRAFANA_URL_ENV_NAME, "")

def is_grafana_configured(config:GrafanaConfig) -> Tuple[bool, List[str]]:
    errors = []
    if not config.api_key:
        errors.append(f"api_key is missing from the grafana configuration. Either set the api_key for grafana or set the environment variable {GRAFANA_API_KEY_ENV_NAME}")
    if not config.url:
        errors.append(f"url is missing from the grafana configuration. Either set the api_key for grafana or set the environment variable {GRAFANA_URL_ENV_NAME}")

    return (len(errors) == 0, errors)

def headers(api_key:str):
    return {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

def process_timestamps(start_timestamp: Optional[Union[int, str]], end_timestamp: Optional[Union[int, str]]):
    if start_timestamp and isinstance(start_timestamp, str):
        start_timestamp = int(start_timestamp)
    if end_timestamp and isinstance(end_timestamp, str):
        end_timestamp = int(end_timestamp)

    if not end_timestamp:
        end_timestamp = int(time.time())
    if not start_timestamp:
        start_timestamp = end_timestamp - ONE_HOUR_IN_SECONDS
    if start_timestamp < 0:
        start_timestamp = end_timestamp + start_timestamp
    return (start_timestamp, end_timestamp)

def get_param_or_raise(dict:Dict, param:str) -> str:
    value = dict.get(param)
    if not value:
        raise Exception(f'Missing param "{param}"')
    return value

def get_datasource_id(dict:Dict, param:str) -> str:
    datasource_id=get_param_or_raise(dict, param)
    try:
        if uuid.UUID(datasource_id, version=4):
            return f"uid/{datasource_id}"
    except ValueError:
        pass
    return datasource_id

def get_grafana_toolset_prerequisite(config:GrafanaConfig) -> StaticPrerequisite:
    enabled, errors = is_grafana_configured(config)
    return StaticPrerequisite(enabled=enabled, disabled_reason=", ".join(errors))
