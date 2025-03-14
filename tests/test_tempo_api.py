

import json
import os

from holmes.plugins.toolsets.grafana.trace_parser import process_trace

input_trace_data_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'fixtures', 'test_tempo_api', 'trace_data.input.json'))
expected_trace_data_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'fixtures', 'test_tempo_api', 'trace_data.expected.txt'))

def test_process_trace_json():
    labels = ['service.name', 'service.version', 'k8s.deployment.name',
'k8s.node.name', 'k8s.pod.name', 'k8s.namespace.name']
    trace_data = json.loads(open(input_trace_data_file_path).read())
    expected_result = open(expected_trace_data_file_path).read()
    result = process_trace(trace_data, labels)
    print(result)
    assert result is not None
    assert result.strip() == expected_result.strip()
