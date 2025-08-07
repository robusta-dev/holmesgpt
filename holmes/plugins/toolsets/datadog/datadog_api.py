import logging
from typing import Any, Optional, Dict
import requests  # type: ignore
from pydantic import AnyUrl, BaseModel
from requests.structures import CaseInsensitiveDict  # type: ignore
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_incrementing
from tenacity.wait import wait_base


START_RETRY_DELAY = (
    5.0  # Initial fallback delay if datadog does not return a reset_time
)
INCREMENT_RETRY_DELAY = 5.0  # Delay increment after each rate limit, if datadog does not return a reset_time
MAX_RETRY_COUNT_ON_RATE_LIMIT = 5

RATE_LIMIT_REMAINING_SECONDS_HEADER = "X-RateLimit-Reset"


class DatadogBaseConfig(BaseModel):
    """Base configuration for all Datadog toolsets"""

    dd_api_key: str
    dd_app_key: str
    site_api_url: AnyUrl
    request_timeout: int = 60


class DataDogRequestError(Exception):
    payload: dict
    status_code: int
    response_text: str
    response_headers: CaseInsensitiveDict[str]

    def __init__(
        self,
        payload: dict,
        status_code: int,
        response_text: str,
        response_headers: CaseInsensitiveDict[str],
    ):
        super().__init__(f"HTTP error: {status_code} - {response_text}")
        self.payload = payload
        self.status_code = status_code
        self.response_text = response_text
        self.response_headers = response_headers


def get_headers(dd_config: DatadogBaseConfig) -> Dict[str, str]:
    """Get standard headers for Datadog API requests.

    Args:
        dd_config: Datadog configuration object

    Returns:
        Dictionary of headers for Datadog API requests
    """
    return {
        "Content-Type": "application/json",
        "DD-API-KEY": dd_config.dd_api_key,
        "DD-APPLICATION-KEY": dd_config.dd_app_key,
    }


def extract_cursor(data: dict) -> Optional[str]:
    """Extract cursor for paginating through Datadog logs API responses."""
    if data is None:
        return None
    meta = data.get("meta", {})
    if meta is None:
        return None
    page = meta.get("page", {})
    if page is None:
        return None
    return page.get("after", None)


class retry_if_http_429_error(retry_if_exception):
    def __init__(self):
        def is_http_429_error(exception):
            return (
                isinstance(exception, DataDogRequestError)
                and exception.status_code == 429
            )

        super().__init__(predicate=is_http_429_error)


class wait_for_retry_after_header(wait_base):
    def __init__(self, fallback):
        self.fallback = fallback

    def __call__(self, retry_state):
        if retry_state.outcome:
            exc = retry_state.outcome.exception()

            if isinstance(exc, DataDogRequestError) and exc.response_headers.get(
                RATE_LIMIT_REMAINING_SECONDS_HEADER
            ):
                reset_time_header = exc.response_headers.get(
                    RATE_LIMIT_REMAINING_SECONDS_HEADER
                )
                if reset_time_header:
                    try:
                        reset_time = int(reset_time_header)
                        wait_time = max(0, reset_time) + 0.1
                        return wait_time
                    except ValueError:
                        logging.warning(
                            f"Received invalid {RATE_LIMIT_REMAINING_SECONDS_HEADER} header value from datadog: {reset_time_header}"
                        )

        return self.fallback(retry_state)


@retry(
    retry=retry_if_http_429_error(),
    wait=wait_for_retry_after_header(
        fallback=wait_incrementing(
            start=START_RETRY_DELAY, increment=INCREMENT_RETRY_DELAY
        )
    ),
    stop=stop_after_attempt(MAX_RETRY_COUNT_ON_RATE_LIMIT),
    before_sleep=lambda retry_state: logging.warning(
        f"DataDog API rate limited. Retrying... "
        f"(attempt {retry_state.attempt_number}/{MAX_RETRY_COUNT_ON_RATE_LIMIT})"
    ),
    reraise=True,
)
def execute_paginated_datadog_http_request(
    url: str,
    headers: dict,
    payload_or_params: dict,
    timeout: int,
    method: str = "POST",
) -> tuple[Any, Optional[str]]:
    response_data = execute_datadog_http_request(
        url=url,
        headers=headers,
        payload_or_params=payload_or_params,
        timeout=timeout,
        method=method,
    )
    cursor = extract_cursor(response_data)
    data = response_data.get("data", [])
    return data, cursor


def execute_datadog_http_request(
    url: str,
    headers: dict,
    payload_or_params: dict,
    timeout: int,
    method: str = "POST",
) -> Any:
    if method == "GET":
        response = requests.get(
            url, headers=headers, params=payload_or_params, timeout=timeout
        )
    else:
        response = requests.post(
            url, headers=headers, json=payload_or_params, timeout=timeout
        )

    if response.status_code == 200:
        return response.json()

    else:
        raise DataDogRequestError(
            payload=payload_or_params,
            status_code=response.status_code,
            response_text=response.text,
            response_headers=response.headers,
        )
