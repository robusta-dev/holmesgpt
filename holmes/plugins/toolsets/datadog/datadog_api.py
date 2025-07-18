import logging
from typing import Optional
import requests  # type: ignore
from requests.structures import CaseInsensitiveDict  # type: ignore
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_incrementing
from tenacity.wait import wait_base


START_RETRY_DELAY = (
    5.0  # Initial fallback delay if datadog does not return a reset_time
)
INCREMENT_RETRY_DELAY = 5.0  # Delay increment after each rate limit, if datadog does not return a reset_time
MAX_RETRY_COUNT_ON_RATE_LIMIT = 5

RATE_LIMIT_REMAINING_SECONDS_HEADER = "X-RateLimit-Reset"


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


def extract_logs_cursor(data: dict) -> Optional[str]:
    """Extract cursor for paginating through Datadog logs API responses."""
    return data.get("meta", {}).get("page", {}).get("after", None)


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
)
def execute_datadog_http_request(
    url: str, headers: dict, payload: dict, timeout: int
) -> tuple[list[dict], Optional[str]]:
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)

    if response.status_code == 200:
        data = response.json()
        cursor = extract_logs_cursor(data)

        logs = data.get("data", [])
        return logs, cursor

    else:
        raise DataDogRequestError(
            payload=payload,
            status_code=response.status_code,
            response_text=response.text,
            response_headers=response.headers,
        )
