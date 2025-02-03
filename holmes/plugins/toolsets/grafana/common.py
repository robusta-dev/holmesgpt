from typing import Dict, Optional, Union
import uuid
import time
from pydantic import BaseModel

ONE_HOUR_IN_SECONDS = 3600


class GrafanaConfig(BaseModel):
    api_key: str
    url: str


def headers(api_key: str):
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def process_timestamps(
    start_timestamp: Optional[Union[int, str]], end_timestamp: Optional[Union[int, str]]
):
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


def get_param_or_raise(dict: Dict, param: str) -> str:
    value = dict.get(param)
    if not value:
        raise Exception(f'Missing param "{param}"')
    return value


def get_datasource_id(dict: Dict, param: str) -> str:
    datasource_id = get_param_or_raise(dict, param)
    try:
        if uuid.UUID(datasource_id, version=4):
            return f"uid/{datasource_id}"
    except:
        pass

    return datasource_id
