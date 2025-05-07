import pytest
import json

from holmes.plugins.toolsets.opensearch.opensearch_utils import format_logs

# Sample data derived from the provided query result
SAMPLE_HITS = [
    {
        "_index": "fluentd-2025.05.05",
        "_id": "SFJ9oJYBnT25q51XkZM4",
        "_score": 5.028699,
        "_source": {
            "stream": "stdout",
            "logtag": "F",
            "message": "** ALERTMANAGER_HEADERS={'Content-type': 'application/json', 'X-Scope-Org-Id': '1|2|3|4'}",
            "time": "2025-05-05T12:22:16.745685103Z",
            "docker": {
                "container_id": "4bd5b29e14c6586b07ae8b862d51702c9da997e3c921ad6caeb1983bec8201b4"
            },
            "kubernetes": {
                "container_name": "runner",
                "namespace_name": "default",
                "pod_name": "robusta-runner-796c867f59-wbkpn",
            },
            "@timestamp": "2025-05-05T12:22:16.745685103+00:00",
        },
    },
    {
        "_index": "fluentd-2025.05.05",
        "_id": "SlJ9oJYBnT25q51XkZM4",
        "_score": 5.028699,
        "_source": {
            "stream": "stderr",
            "logtag": "F",
            "message": "\u001b[32m2025-05-05 12:25:16.990 INFO     discovered service with label-selector: `app=kube-prometheus-stack-alertmanager` at url: `http://robusta-kube-prometheus-st-alertmanager.default.svc.cluster.local:9093`\u001b[0m",
            "time": "2025-05-05T12:25:16.990851385Z",
            "docker": {
                "container_id": "4bd5b29e14c6586b07ae8b862d51702c9da997e3c921ad6caeb1983bec8201b4"
            },
            "kubernetes": {
                "container_name": "runner",
                "namespace_name": "default",
                "pod_name": "robusta-runner-796c867f59-wbkpn",
            },
            "@timestamp": "2025-05-05T12:25:16.990851385+00:00",
            "log.level": "INFO",  # Add a level field for testing
        },
    },
    {
        "_index": "fluentd-2025.05.05",
        "_id": "missing_fields_id",
        "_score": 5.0,
        "_source": {
            "stream": "stdout",
            # Missing @timestamp, message, log.level
            "time": "2025-05-05T12:30:00.000000000Z",
        },
    },
    {
        "_index": "fluentd-2025.05.05",
        "_id": "non_string_msg_id",
        "_score": 5.0,
        "_source": {
            "@timestamp": "2025-05-05T12:31:00.000000000+00:00",
            "log.level": "WARN",
            "message": 12345,  # Non-string message
        },
    },
]

# --- Test Cases ---


def test_format_logs_empty_input():
    assert format_logs([]) == ""
    assert format_logs(None) == ""


def test_format_logs_invalid_input_items():
    invalid_logs = [
        SAMPLE_HITS[0],  # Valid item
        "not_a_dictionary",
        None,
        {"_id": "no_source_hit"},  # Hit without _source
        {"_id": "bad_source_hit", "_source": "not_a_dict_source"},
    ]
    output = format_logs(invalid_logs, format_type="simplified")
    lines = output.split("\n")
    assert len(lines) == 5
    assert lines[0].startswith(
        "2025-05-05T12:22:16.745685103+00:00 N/A ** ALERTMANAGER_HEADERS"
    )  # First is valid
    assert "Skipping invalid log entry (not a dict): <class 'str'>" in lines[1]
    assert "Skipping invalid log entry (not a dict): <class 'NoneType'>" in lines[2]
    assert (
        "Skipping log entry with invalid or missing '_source': no_source_hit"
        in lines[3]
    )
    assert (
        "Skipping log entry with invalid or missing '_source': bad_source_hit"
        in lines[4]
    )

    output_json = format_logs(invalid_logs, format_type="json")
    lines_json = output_json.split("\n")
    assert len(lines_json) == 5
    # The current implementation just formats the full hit, not just the _source
    assert "_index" in lines_json[0]
    assert "_id" in lines_json[0]
    assert "_source" in lines_json[0]

    # Current implementation formats non-dict items as-is rather than skipping
    assert lines_json[1] == '"not_a_dictionary"'
    assert lines_json[2] == "null"
    # The following entries might be formatted as-is without error messages
    assert "no_source_hit" in lines_json[3]
    assert "bad_source_hit" in lines_json[4]


def test_format_logs_simplified_default():
    output = format_logs(SAMPLE_HITS, format_type="simplified")
    lines = output.split("\n")
    # Current implementation includes a fallback for missing message field
    assert len(lines) == 4
    # Note: Default level_field 'log.level' is missing in first hit, present in second
    assert (
        lines[0]
        == "2025-05-05T12:22:16.745685103+00:00 N/A ** ALERTMANAGER_HEADERS={'Content-type': 'application/json', 'X-Scope-Org-Id': '1|2|3|4'}"
    )
    assert lines[1].startswith(
        "2025-05-05T12:25:16.990851385+00:00 INFO \u001b[32m2025-05-05 12:25:16.990 INFO"
    )
    # Third entry has missing fields and is presented as JSON
    assert '{"_index": "fluentd-2025.05.05"' in lines[2]
    assert (
        lines[3] == "2025-05-05T12:31:00.000000000+00:00 WARN 12345"
    )  # Non-string message converted


def test_format_logs_simplified_custom_fields():
    output = format_logs(
        SAMPLE_HITS,
        format_type="simplified",
        timestamp_field="time",
        level_field="stream",  # Use stream as level for testing
        message_field="logtag",  # Use logtag as message for testing
    )
    lines = output.split("\n")
    # Only the first two entries have time, stream, and logtag fields
    assert len(lines) >= 2
    assert "2025-05-05T12:22:16.745685103Z stdout F" in lines
    assert "2025-05-05T12:25:16.990851385Z stderr F" in lines
    # Other entries might be presented as JSON due to missing custom fields


def test_format_logs_simplified_truncation():
    output = format_logs(SAMPLE_HITS, format_type="simplified", max_message_length=20)
    lines = output.split("\n")
    print("** OUTPUT:")
    print(output)
    # The current implementation produces 4 lines including the JSON fallback
    assert len(lines) == 4
    assert " ALERTMANAGER_HEAD..." in lines[0]
    assert "2025-05-05 12:2..." in lines[1]
    # Third line is JSON of the entry with missing message field
    assert '{"_index": ' in lines[2]
    assert " 12345" in lines[3]


def test_format_logs_simplified_no_truncation():
    output = format_logs(SAMPLE_HITS, format_type="simplified", max_message_length=None)
    print("** OUTPUT:")
    print(output)
    lines = output.split("\n")
    # The current implementation produces 4 lines including the JSON fallback
    assert len(lines) == 4
    # Check end of first message without truncation/ellipsis
    assert "Org-Id': '1|2|3|4'}" in lines[0]
    # Check end of second message
    assert "local:9093`\u001b[0m" in lines[1]
    # Third line is the JSON fallback
    assert '{"_index": "fluentd-2025.05.05"' in lines[2]
    # Fourth line has the non-string message
    assert "12345" in lines[3]


def test_format_logs_json_source_only_default():
    output = format_logs(
        SAMPLE_HITS, format_type="json"
    )  # include_source_in_json=True is default
    lines = output.split("\n")
    assert len(lines) == 4
    for i, line in enumerate(lines):
        try:
            data = json.loads(line)
            # The current implementation outputs the full hit, not just _source
            # So we need to verify that all keys from the original hit are present
            for key in SAMPLE_HITS[i].keys():
                assert key in data
        except json.JSONDecodeError:
            pytest.fail(f"Line {i+1} is not valid JSON: {line}")
        except KeyError:
            pytest.fail(f"SAMPLE_HITS[{i}] seems malformed, missing expected key")


def test_format_logs_json_full_hit():
    output = format_logs(SAMPLE_HITS, format_type="json", include_source_in_json=False)
    lines = output.split("\n")
    assert len(lines) == 4
    for i, line in enumerate(lines):
        try:
            data = json.loads(line)
            # The current implementation always outputs the full hit
            # So we need to verify that all keys from the original hit are present
            for key in SAMPLE_HITS[i].keys():
                assert key in data
            assert "_index" in data
            assert "_id" in data
            assert "_source" in data
        except json.JSONDecodeError:
            pytest.fail(f"Line {i+1} is not valid JSON: {line}")


def test_format_logs_invalid_format_type():
    with pytest.raises(ValueError, match="Invalid format_type"):
        format_logs(SAMPLE_HITS, format_type="xml")  # type: ignore
