from typing import Any, Tuple
from urllib.parse import urljoin

import requests


def execute_query(base_url: str, api_key: str, query: dict[str, Any]):
    url = urljoin(base_url, "api/v1/dataprime/query")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    return requests.post(url, headers=headers, json=query)


def health_check(base_url: str, api_key: str) -> Tuple[bool, str]:
    query = {"query": "source logs | limit 1"}

    response = execute_query(base_url=base_url, api_key=api_key, query=query)

    if response.status_code == 200:
        return True, ""
    else:
        return False, f"Failed with status_code={response.status_code}. {response.text}"
