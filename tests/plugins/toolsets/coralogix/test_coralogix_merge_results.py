from holmes.plugins.toolsets.coralogix.api import (
    CoralogixQueryResult,
    merge_log_results,
)
from holmes.plugins.toolsets.coralogix.utils import FlattenedLog


log1 = FlattenedLog(timestamp="2023-10-26T10:00:00Z", log_message="Log A1")
log2 = FlattenedLog(timestamp="2023-10-26T10:01:00Z", log_message="Log A2")
log3 = FlattenedLog(timestamp="2023-10-26T09:59:00Z", log_message="Log B1")
log4 = FlattenedLog(
    timestamp="2023-10-26T10:00:00Z", log_message="Log A1"
)  # Duplicate of log1
log5 = FlattenedLog(timestamp="2023-10-26T10:00:30Z", log_message="Log C1")

# Results without errors
res_a_ok = CoralogixQueryResult(logs=[log1, log2], http_status=200, error=None)
res_b_ok = CoralogixQueryResult(logs=[log3, log4], http_status=201, error=None)
res_c_ok = CoralogixQueryResult(logs=[log5], http_status=202, error=None)
res_empty_ok_1 = CoralogixQueryResult(logs=[], http_status=204, error=None)
res_empty_ok_2 = CoralogixQueryResult(logs=[], http_status=None, error=None)
res_a_ok_none_status = CoralogixQueryResult(logs=[log1], http_status=None, error=None)


# Results with errors
res_a_err = CoralogixQueryResult(logs=[log1], http_status=500, error="Error in A")
res_b_err = CoralogixQueryResult(logs=[log3], http_status=503, error="Error in B")
res_empty_err = CoralogixQueryResult(logs=[], http_status=404, error="Not Found")


def test_a_ok_b_error_returns_a():
    """If 'a' has no error and 'b' does, return 'a'."""
    result = merge_log_results(res_a_ok, res_b_err)
    assert result is res_a_ok
    assert result == res_a_ok  # Also check content for completeness


def test_a_error_b_ok_returns_b():
    """If 'a' has an error and 'b' does not, return 'b'."""
    result = merge_log_results(res_a_err, res_b_ok)
    assert result is res_b_ok
    assert result == res_b_ok


def test_both_error_returns_a():
    """If both 'a' and 'b' have errors, return 'a'."""
    result = merge_log_results(res_a_err, res_b_err)
    assert result is res_a_err
    assert result == res_a_err


def test_both_error_empty_logs_returns_a():
    """If both 'a' and 'b' have errors (even if logs empty), return 'a'."""
    result = merge_log_results(res_empty_err, res_b_err)
    assert result is res_empty_err
    assert result == res_empty_err


# --- Merge Cases (Neither has error) ---


def test_merge_basic_deduplication_and_sort():
    """Test merging two successful results with overlap and different order."""
    result = merge_log_results(res_a_ok, res_b_ok)
    expected_logs = sorted(
        [log3, log1, log2], key=lambda log: log.timestamp
    )  # log4 is duplicate of log1
    assert isinstance(result, CoralogixQueryResult)  # Should be a new object
    assert result is not res_a_ok
    assert result is not res_b_ok
    assert result.logs == expected_logs
    assert result.error is None  # Explicitly check error is None in merge case
    assert result.http_status == res_a_ok.http_status  # 'a' status takes precedence


def test_merge_with_one_empty():
    """Test merging when one result has no logs."""
    result = merge_log_results(res_a_ok, res_empty_ok_1)
    expected_logs = sorted(res_a_ok.logs, key=lambda log: log.timestamp)
    assert result.logs == expected_logs
    assert result.error is None
    assert result.http_status == res_a_ok.http_status  # a's status

    result_rev = merge_log_results(res_empty_ok_1, res_a_ok)
    expected_logs_rev = sorted(res_a_ok.logs, key=lambda log: log.timestamp)
    assert result_rev.logs == expected_logs_rev
    assert result_rev.error is None
    assert result_rev.http_status == res_empty_ok_1.http_status  # empty_ok_1 is 'a' now


def test_merge_both_empty():
    """Test merging when both results have no logs."""
    result = merge_log_results(res_empty_ok_1, res_empty_ok_2)
    assert result.logs == []
    assert result.error is None
    assert result.http_status == res_empty_ok_1.http_status  # a's status (204)


def test_merge_status_precedence_a_has_status():
    """Check 'a's status is used when merging if not None."""
    result = merge_log_results(res_a_ok, res_b_ok)  # a=200, b=201
    assert result.http_status == 200


def test_merge_status_precedence_a_is_none():
    """Check 'b's status is used when merging if 'a's status is None."""
    result = merge_log_results(res_a_ok_none_status, res_b_ok)  # a=None, b=201
    assert result.http_status == 201


def test_merge_status_precedence_both_none():
    """Check status is None if both 'a' and 'b' statuses are None when merging."""
    result = merge_log_results(res_a_ok_none_status, res_empty_ok_2)  # a=None, b=None
    assert result.http_status is None


def test_merge_no_shared_logs():
    """Test merging results with completely distinct logs."""
    result = merge_log_results(res_a_ok, res_c_ok)  # Contains log1, log2 + log5
    expected_logs = sorted([log1, log2, log5], key=lambda log: log.timestamp)
    assert result.logs == expected_logs
    assert result.error is None
    assert result.http_status == res_a_ok.http_status  # a's status
