import importlib.util
import pathlib


def load_prompt_parser():
    spec = importlib.util.spec_from_file_location(
        "tempo_toolset",
        pathlib.Path("holmes/plugins/toolsets/infrainsights/kfuse_tempo_toolset.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PromptParser


def test_extract_kube_deployment_after_keyword():
    PromptParser = load_prompt_parser()
    prompt = (
        'Get traces for deployment "arkham" in namespace "mt-prod" '
        "from the last 1 hour to analyze slow API responses."
    )
    assert PromptParser.extract_kube_deployment(prompt) == "arkham"


def test_extract_service_name():
    PromptParser = load_prompt_parser()
    prompt = "Fetch traces for service checkout in namespace payments"
    assert PromptParser.extract_service_name(prompt) == "checkout"


def test_extract_service_namespace_cluster_from_complex_prompt():
    PromptParser = load_prompt_parser()
    prompt = (
        'Get traces for servicename "connecticutchildrens-prod-patient360-arkham" '
        'in namespace "connecticutchildrens-prod" and cluster name is '
        '"connecticutchildrens-prod" from the last 1 hour to analyze slow API responses.'
    )
    info = PromptParser.extract_all_kubernetes_info(prompt)
    assert info["service_name"] == "connecticutchildrens-prod-patient360-arkham"
    assert info["namespace"] == "connecticutchildrens-prod"
    assert info["cluster_name"] == "connecticutchildrens-prod"


def test_extract_namespace_with_quotes():
    PromptParser = load_prompt_parser()
    prompt = 'Show logs for service foo in namespace "bar-baz"'
    assert PromptParser.extract_namespace(prompt) == "bar-baz"


def test_extract_cluster_name_phrase():
    PromptParser = load_prompt_parser()
    prompt = 'Get traces from service foo where cluster name is "qux-prod"'
    assert PromptParser.extract_kube_cluster_name(prompt) == "qux-prod"
