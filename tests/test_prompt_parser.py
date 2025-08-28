import importlib.util
import pathlib


def load_prompt_parser():
    spec = importlib.util.spec_from_file_location(
        "tempo_toolset", pathlib.Path("holmes/plugins/toolsets/infrainsights/kfuse_tempo_toolset.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PromptParser


def test_extract_kube_deployment_after_keyword():
    PromptParser = load_prompt_parser()
    prompt = (
        'Get traces for deployment "arkham" in namespace "mt-prod" '
        'from the last 1 hour to analyze slow API responses.'
    )
    assert PromptParser.extract_kube_deployment(prompt) == "arkham"
