import json
import os
from holmes.plugins.toolsets.prometheus.data_compression import (
    CompressedMetric,
    Group,
    RawMetric,
    find_most_common_label,
    format_compressed_metrics,
    format_data,
    group_metrics,
    raw_metric_to_compressed_metric,
    summarize_metrics,
)


class TestPrometheusDataCompression:
    """Test cases for Prometheus range query data compression."""

    def test_find_most_common_labels(self):
        metrics = [
            {
                "labels": set(
                    {
                        "exported_endpoint": "api_v1",
                        "service_version": "v2.0.9",
                        "source_ip": "192.168.1.10",
                    }.items()
                ),
                "values": [],
            },
            {
                "labels": set(
                    {
                        "exported_endpoint": "api_v1",
                        "service_version": "v2.0.9",
                        "source_ip": "192.168.1.11",
                    }.items()
                ),
                "values": [],
            },
            {
                "labels": set(
                    {
                        "exported_endpoint": "api_v1",
                        "service_version": "v2.0.9",
                        "source_ip": "192.168.1.12",
                    }.items()
                ),
                "values": [],
            },
            {
                "labels": set(
                    {
                        "exported_endpoint": "api_v1",
                        "service_version": "v2.0.10",
                        "source_ip": "192.168.1.30",
                    }.items()
                ),
                "values": [],
            },
        ]
        assert find_most_common_label(
            metrics=[CompressedMetric(**metric) for metric in metrics],
            ignore_label_set=set(),
        ) == (("exported_endpoint", "api_v1"), 4)

    def test_find_most_common_labels_none(self):
        metrics = [
            {
                "labels": set(
                    {
                        "exported_endpoint": "api_v1",
                        "service_version": "v2.0.1",
                        "source_ip": "192.168.1.10",
                    }.items()
                ),
                "values": [],
            },
            {
                "labels": set(
                    {
                        "exported_endpoint": "api_v2",
                        "service_version": "v2.0.2",
                        "source_ip": "192.168.1.11",
                    }.items()
                ),
                "values": [],
            },
            {
                "labels": set(
                    {
                        "exported_endpoint": "api_v3",
                        "service_version": "v2.0.3",
                        "source_ip": "192.168.1.12",
                    }.items()
                ),
                "values": [],
            },
            {
                "labels": set(
                    {
                        "exported_endpoint": "api_v4",
                        "service_version": "v2.0.4",
                        "source_ip": "192.168.1.30",
                    }.items()
                ),
                "values": [],
            },
        ]
        assert find_most_common_label(
            metrics=[CompressedMetric(**metric) for metric in metrics],
            ignore_label_set=set(),
        ) == (None, 0)

    def test_group_metrics(self):
        input_metrics = [
            {
                "labels": set(
                    {
                        "exported_endpoint": "api_v1",
                        "service_version": "v2.0.9",
                        "source_ip": "192.168.1.10",
                        "http_code": 404,
                    }.items()
                ),
                "values": [
                    [1758179790, "10.1"],
                    [1758180000, "10.2"],
                ],
            },
            {
                "labels": set(
                    {
                        "exported_endpoint": "api_v1",
                        "service_version": "v2.0.9",
                        "source_ip": "192.168.1.11",
                        "http_code": 404,
                    }.items()
                ),
                "values": [
                    [1758180210, "11.1"],
                    [1758180420, "11.2"],
                ],
            },
            {
                "labels": set(
                    {
                        "exported_endpoint": "api_v1",
                        "service_version": "v2.0.9",
                        "source_ip": "192.168.1.12",
                        "http_code": 404,
                    }.items()
                ),
                "values": [
                    [1758180630, "12.1"],
                    [1758183360, "12.2"],
                ],
            },
            {
                "labels": set(
                    {
                        "exported_endpoint": "api_v1",
                        "service_version": "v2.0.9",
                        "source_ip": "192.168.1.12",
                        "http_code": 404,
                    }.items()
                ),
                "values": [
                    [1758183570, "12.3"],
                    [1758183780, "12.4"],
                ],
            },
            {
                "labels": set(
                    {
                        "exported_endpoint": "api_v1",
                        "service_version": "v2.0.9",
                        "source_ip": "192.168.1.30",
                        "http_code": 404,
                    }.items()
                ),
                "values": [
                    [1758183990, "30.1"],
                    [1758184200, "30.2"],
                ],
            },
            {
                "labels": set(
                    {
                        "exported_endpoint": "api_v1",
                        "service_version": "v2.0.9",
                        "source_ip": "192.168.1.12",
                        "http_code": 400,
                    }.items()
                ),
                "values": [
                    [1758184410, "12.5"],
                    [1758184620, "12.6"],
                ],
            },
        ]

        expected_metrics_raw = [
            {
                "common_labels": set(
                    {
                        "exported_endpoint": "api_v1",
                        "service_version": "v2.0.9",
                    }.items()
                ),
                "metrics": [
                    {
                        "labels": set(
                            {
                                "source_ip": "192.168.1.12",
                                "http_code": 400,
                            }.items()
                        ),
                        "values": [
                            [1758184410, "12.5"],
                            [1758184620, "12.6"],
                        ],
                    },
                    {
                        "common_labels": set(
                            {
                                "http_code": 404,
                            }.items()
                        ),
                        "metrics": [
                            {
                                "labels": set(
                                    {
                                        "source_ip": "192.168.1.10",
                                    }.items()
                                ),
                                "values": [
                                    [1758179790, "10.1"],
                                    [1758180000, "10.2"],
                                ],
                            },
                            {
                                "labels": set(
                                    {
                                        "source_ip": "192.168.1.11",
                                    }.items()
                                ),
                                "values": [
                                    [1758180210, "11.1"],
                                    [1758180420, "11.2"],
                                ],
                            },
                            {
                                "labels": set(
                                    {
                                        "source_ip": "192.168.1.12",
                                    }.items()
                                ),
                                "values": [
                                    [1758180630, "12.1"],
                                    [1758183360, "12.2"],
                                ],
                            },
                            {
                                "labels": set(
                                    {
                                        "source_ip": "192.168.1.12",
                                    }.items()
                                ),
                                "values": [
                                    [1758183570, "12.3"],
                                    [1758183780, "12.4"],
                                ],
                            },
                            {
                                "labels": set(
                                    {
                                        "source_ip": "192.168.1.30",
                                    }.items()
                                ),
                                "values": [
                                    [1758183990, "30.1"],
                                    [1758184200, "30.2"],
                                ],
                            },
                        ],
                    },
                ],
            }
        ]

        expected_metrics = [
            Group(**metric)
            if metric.get("common_labels")
            else CompressedMetric(**metric)
            for metric in expected_metrics_raw
        ]

        compressed_metrics = group_metrics(
            metrics_to_process=[CompressedMetric(**metric) for metric in input_metrics]
        )

        print("**** EXPECTED:")
        print(format_compressed_metrics(expected_metrics))
        print("**** ACTUAL:")
        print(format_compressed_metrics(compressed_metrics))
        assert expected_metrics == compressed_metrics

    def test_format_data_compressed_metric(self):
        metric = CompressedMetric(
            labels=set([("exported_endpoint", "api_v1"), ("http_code", 400)]),
            values=[
                [1758184410, "12.5"],
                [1758184620, "12.6"],
            ],
        )
        actual_str = format_data(metric)

        expected_str = 'labels: {"exported_endpoint": "api_v1", "http_code": 400}\n'
        expected_str += "values:\n"
        expected_str += "  - 1758184410: 12.5\n"
        expected_str += "  - 1758184620: 12.6"

        assert expected_str == actual_str

    def test_format_data_group(self):
        group = Group(
            common_labels=set([("exported_endpoint", "api_v1"), ("http_code", 400)]),
            metrics=[
                Group(
                    common_labels=set(
                        [
                            ("service_version", "v2.0.9"),
                        ]
                    ),
                    metrics=[
                        CompressedMetric(
                            labels=set(
                                [
                                    ("source_ip", "192.168.1.13"),
                                ]
                            ),
                            values=[
                                [1758184410, "13.1"],
                                [1758184620, "13.2"],
                            ],
                        ),
                        CompressedMetric(
                            labels=set(
                                [
                                    ("source_ip", "192.168.1.14"),
                                ]
                            ),
                            values=[
                                [1758184410, "14.1"],
                                [1758184620, "14.2"],
                            ],
                        ),
                    ],
                ),
                CompressedMetric(
                    labels=set(
                        [
                            ("source_ip", "192.168.1.12"),
                        ]
                    ),
                    values=[
                        [1758184410, "12.1"],
                        [1758184620, "12.2"],
                    ],
                ),
            ],
        )

        expected_str = (
            '  common_labels: {"exported_endpoint": "api_v1", "http_code": 400}\n'
        )
        expected_str += "  metrics:\n"
        expected_str += '    - common_labels: {"service_version": "v2.0.9"}\n'
        expected_str += "      metrics:\n"
        expected_str += '        - labels: {"source_ip": "192.168.1.13"}\n'
        expected_str += "          values:\n"
        expected_str += "            - 1758184410: 13.1\n"
        expected_str += "            - 1758184620: 13.2\n"
        expected_str += '        - labels: {"source_ip": "192.168.1.14"}\n'
        expected_str += "          values:\n"
        expected_str += "            - 1758184410: 14.1\n"
        expected_str += "            - 1758184620: 14.2\n"
        expected_str += '    - labels: {"source_ip": "192.168.1.12"}\n'
        expected_str += "      values:\n"
        expected_str += "        - 1758184410: 12.1\n"
        expected_str += "        - 1758184620: 12.2"

        actual_str = format_compressed_metrics([group])

        print("**** EXPECTED:")
        print(expected_str)
        print("**** ACTUAL:")
        print(actual_str)

        assert expected_str.strip() in actual_str.strip()

    def test_format_data_realistic(self):
        # This test is mostly used to manually analyze the output and make sure there is no error thrown
        # The data is from a
        example_json_file_path = os.path.join(
            os.path.dirname(__file__), "raw_prometheus_data.json"
        )

        with open(example_json_file_path) as file:
            data = json.load(file)
            metrics_list_dict = data.get("result")

            raw_metrics = [RawMetric(**metric) for metric in metrics_list_dict]
            metrics = [
                raw_metric_to_compressed_metric(metric, remove_labels=set())
                for metric in raw_metrics
            ]

            formatted_data = summarize_metrics(metrics)

            ratio = len(formatted_data) / len(json.dumps(data, indent=2))
            # print(formatted_data)

            assert ratio < 0.31
            # assert False # Uncomment to see the formatted output
