from enum import Enum
import logging
from typing import Any, Tuple
from urllib.parse import urljoin

import requests  # type: ignore

from holmes.plugins.toolsets.coralogix.utils import (
    CoralogixConfig,
    CoralogixQueryResult,
    merge_log_results,
    parse_logs,
    CoralogixLogsMethodology,
)
from holmes.plugins.toolsets.logging_utils.logging_api import FetchPodLogsParams
from holmes.plugins.toolsets.utils import (
    process_timestamps_to_rfc3339,
)


DEFAULT_TIME_SPAN_SECONDS = 86400
DEFAULT_LOG_COUNT = 2000  # Coralogix's default is 2000


class CoralogixTier(str, Enum):
    FREQUENT_SEARCH = "TIER_FREQUENT_SEARCH"
    ARCHIVE = "TIER_ARCHIVE"


def get_dataprime_base_url(domain: str) -> str:
    return f"https://ng-api-http.{domain}"


def execute_http_query(domain: str, api_key: str, query: dict[str, Any]):
    base_url = get_dataprime_base_url(domain)
    url = urljoin(base_url, "api/v1/dataprime/query")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    return requests.post(url, headers=headers, json=query)


def health_check(domain: str, api_key: str) -> Tuple[bool, str]:
    query = {"query": "source logs | limit 1"}

    response = execute_http_query(domain=domain, api_key=api_key, query=query)

    if response.status_code == 200:
        return True, ""
    else:
        return False, f"Failed with status_code={response.status_code}. {response.text}"


def build_query_string(config: CoralogixConfig, params: FetchPodLogsParams) -> str:
    query_filters = []
    query_filters.append(f'{config.labels.namespace}:"{params.namespace}"')
    query_filters.append(f'{config.labels.pod}:"{params.pod_name}"')

    if params.filter:
        query_filters.append(f'{config.labels.log_message}:"{params.filter}"')

    query_string = " AND ".join(query_filters)
    query_string = f"source logs | lucene '{query_string}' | limit {params.limit or DEFAULT_LOG_COUNT}"
    return query_string


def get_start_end(params: FetchPodLogsParams):
    (start, end) = process_timestamps_to_rfc3339(
        start_timestamp=params.start_time,
        end_timestamp=params.end_time,
        default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
    )
    return (start, end)


def build_query(
    config: CoralogixConfig, params: FetchPodLogsParams, tier: CoralogixTier
):
    (start, end) = get_start_end(params)

    query_string = build_query_string(config, params)
    return {
        "query": query_string,
        "metadata": {
            "tier": tier.value,
            "syntax": "QUERY_SYNTAX_DATAPRIME",
            "startDate": start,
            "endDate": end,
        },
    }


def query_logs_for_tier(
    config: CoralogixConfig, params: FetchPodLogsParams, tier: CoralogixTier
) -> CoralogixQueryResult:
    http_status = None
    try:
        query = build_query(config, params, tier)

        response = execute_http_query(
            domain=config.domain,
            api_key=config.api_key,
            query=query,
        )
        http_status = response.status_code
        if http_status == 200:
            logs = parse_logs(raw_logs=response.text.strip())
            return CoralogixQueryResult(logs=logs, http_status=http_status, error=None)
        else:
            return CoralogixQueryResult(
                logs=[], http_status=http_status, error=response.text
            )
    except Exception as e:
        logging.error("Failed to fetch coralogix logs", exc_info=True)
        return CoralogixQueryResult(logs=[], http_status=http_status, error=str(e))


def query_logs_for_all_tiers(
    config: CoralogixConfig, params: FetchPodLogsParams
) -> CoralogixQueryResult:
    methodology = config.logs_retrieval_methodology
    result: CoralogixQueryResult

    if methodology in [
        CoralogixLogsMethodology.FREQUENT_SEARCH_ONLY,
        CoralogixLogsMethodology.BOTH_FREQUENT_SEARCH_AND_ARCHIVE,
        CoralogixLogsMethodology.ARCHIVE_FALLBACK,
    ]:
        result = query_logs_for_tier(
            config=config, params=params, tier=CoralogixTier.FREQUENT_SEARCH
        )

        if (
            methodology == CoralogixLogsMethodology.ARCHIVE_FALLBACK and not result.logs
        ) or methodology == CoralogixLogsMethodology.BOTH_FREQUENT_SEARCH_AND_ARCHIVE:
            archive_search_results = query_logs_for_tier(
                config=config, params=params, tier=CoralogixTier.ARCHIVE
            )
            result = merge_log_results(result, archive_search_results)

    else:
        # methodology in [CoralogixLogsMethodology.ARCHIVE_ONLY, CoralogixLogsMethodology.FREQUENT_SEARCH_FALLBACK]:
        result = query_logs_for_tier(
            config=config, params=params, tier=CoralogixTier.ARCHIVE
        )

        if (
            methodology == CoralogixLogsMethodology.FREQUENT_SEARCH_FALLBACK
            and not result.logs
        ):
            frequent_search_results = query_logs_for_tier(
                config=config, params=params, tier=CoralogixTier.FREQUENT_SEARCH
            )
            result = merge_log_results(result, frequent_search_results)

    return result
