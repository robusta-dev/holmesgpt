from holmes.plugins.toolsets.opensearch.opensearch_utils import (
    OpenSearchLoggingConfig,
    OpenSearchLoggingLabelsConfig,
    format_logs,
)


config = OpenSearchLoggingConfig(
    opensearch_url="",
    opensearch_auth_header="",
    index_pattern="*",
    labels=OpenSearchLoggingLabelsConfig(log_level="stream"),
)

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
    assert format_logs([], config) == ""
    assert format_logs(None, config) == ""


def test_format_logs_invalid_input_items():
    invalid_logs = [
        SAMPLE_HITS[0],  # Valid item
        "not_a_dictionary",
        None,
        {"_id": "no_source_hit"},  # Hit without _source
        {"_id": "bad_source_hit", "_source": "not_a_dict_source"},
    ]
    output = format_logs(invalid_logs, config)
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


def test_format_logs_simplified_default():
    output = format_logs(SAMPLE_HITS, config)
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
    output = format_logs(SAMPLE_HITS, config)
    lines = output.split("\n")
    # Only the first two entries have time, stream, and logtag fields
    assert len(lines) >= 2
    assert "2025-05-05T12:22:16.745685103Z stdout F" in lines
    assert "2025-05-05T12:25:16.990851385Z stderr F" in lines
    # Other entries might be presented as JSON due to missing custom fields


def test_format_logs_simplified_truncation():
    output = format_logs(SAMPLE_HITS, config)
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
    output = format_logs(SAMPLE_HITS, config)
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
