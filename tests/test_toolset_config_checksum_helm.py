"""Renders the Holmes chart with `helm template` and checks that every value
feeding the custom-toolsets-configmap rolls the Holmes pod through its
checksum/toolset-config annotation."""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

HELM_DIR = Path(__file__).resolve().parents[1] / "helm" / "holmes"

pytestmark = pytest.mark.skipif(
    shutil.which("helm") is None, reason="helm binary not installed"
)


def _checksum(*set_args):
    args = [
        "helm",
        "template",
        "t",
        str(HELM_DIR),
        "--show-only",
        "templates/holmes.yaml",
    ]
    for arg in set_args:
        args += ["--set", arg]
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    deployment = next(
        doc
        for doc in yaml.safe_load_all(result.stdout)
        if doc and doc["kind"] == "Deployment"
    )
    return deployment["spec"]["template"]["metadata"]["annotations"][
        "checksum/toolset-config"
    ]


@pytest.mark.parametrize(
    "set_args",
    [
        ["toolsets.prometheus/metrics.enabled=false"],
        ["mcp_servers.example.config.url=http://example:8000/mcp"],
        ["modelList.example.model=gpt-4.1"],
        ["k8sRBAC=true"],
        ["mcpAddons.aws.enabled=true"],
        ["mcpAddons.gcp.enabled=true"],
        ["mcpAddons.azure.enabled=true"],
    ],
    ids=lambda set_args: set_args[0].split("=")[0],
)
def test_toolset_configmap_inputs_roll_the_pod(set_args):
    assert _checksum(*set_args) != _checksum()


def test_checksum_is_stable_across_renders():
    assert _checksum("k8sRBAC=true") == _checksum("k8sRBAC=true")
