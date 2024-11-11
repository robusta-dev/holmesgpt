import pytest

from holmes.utils.tags import format_tags_in_string, parse_messages_tags

@pytest.mark.parametrize("input, expected_output", [
    (
        'What is the status of << { "type": "service", "namespace": "default", "kind": "Deployment", "name": "nginx" } >>?',
        'What is the status of service nginx (namespace=default, kind=Deployment)?'
    ),
    (
        'why did << { "type": "job", "namespace": "my-namespace", "name": "my-job" } >> fail?',
        'why did job my-job (namespace=my-namespace) fail?'
    ),
    (
        'why did << { "type": "pod", "namespace": "my-namespace", "name": "runner-2323" } >> fail?',
        'why did pod runner-2323 (namespace=my-namespace) fail?'
    ),
    (
        'how many pods are running on << { "type": "node", "name": "my-node" } >>?',
        'how many pods are running on node my-node?'
    ),
    (
        'What caused << { "type": "issue", "id": "issue-id", "name": "KubeJobFailed", "subject_namespace": "my-namespace", "subject_name": "my-pod" } >>?',
        'What caused issue issue-id (name=KubeJobFailed, subject_namespace=my-namespace, subject_name=my-pod)?'
    )
])
def test_format_tags_in_string(input, expected_output):
    assert format_tags_in_string(input) == expected_output

def test_parse_message_tags():
    assert parse_messages_tags([{
        "role": "user",
        "content": 'how many pods are running on << { "type": "node", "name": "my-node" } >>?'
    }])[0] == {
        "role": "user",
        "content": 'how many pods are running on node my-node?'
    }
