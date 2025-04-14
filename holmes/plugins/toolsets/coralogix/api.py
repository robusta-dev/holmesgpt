from typing import Any, Tuple
from urllib.parse import urljoin

import requests


def get_dataprime_base_url(domain: str) -> str:
    return f"https://ng-api-http.{domain}"


def execute_query(domain: str, api_key: str, query: dict[str, Any]):
    base_url = get_dataprime_base_url(domain)
    url = urljoin(base_url, "api/v1/dataprime/query")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    return requests.post(url, headers=headers, json=query)


def health_check(domain: str, api_key: str) -> Tuple[bool, str]:
    query = {"query": "source logs | limit 1"}

    response = execute_query(domain=domain, api_key=api_key, query=query)

    if response.status_code == 200:
        return True, ""
    else:
        return False, f"Failed with status_code={response.status_code}. {response.text}"
