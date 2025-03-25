import json
import logging
from typing import Optional, Dict, Any, Union
from urllib.parse import urljoin

import requests
from pydantic import BaseModel


class OpenSearchIndexConfig(BaseModel):
    opensearch_url: Union[str, None]
    index_name: Union[str, None]
    opensearch_auth_header: Union[str, None]
    # Setting to None will disable the cache
    fields_ttl_seconds: Union[int, None] = 14400  # 4 hours


def add_auth_header(auth_header: Optional[str]) -> Dict[str, Any]:
    results = {}
    if auth_header:
        results["Authorization"] = auth_header
    return results


def get_search_url(config: OpenSearchIndexConfig) -> str:
    return urljoin(config.opensearch_url, f"/{config.index_name}/_search")


def opensearch_health_check(config: OpenSearchIndexConfig) -> bool:
    try:
        headers = {"Content-Type": "application/json"}
        headers.update(add_auth_header(config.opensearch_auth_header))
        health_response = requests.get(
            url=get_search_url(config),
            verify=True,
            data=json.dumps({"size": 1}),
            headers=headers,
        )
        health_response.raise_for_status()
        return True
    except Exception:
        logging.info("Failed to initialize opensearch toolset", exc_info=True)
        return False
