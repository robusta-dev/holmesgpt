"""Renders the Kubernetes MCP addon with `helm template` and checks:

- a CA certificate set in mcpAddons.kubernetes.config.certificateAuthority
  reaches the MCP server pod, so `certificate_authority` in serverConfig can
  point at it (for example, Dex served from a private CA);
- with a mounted kubeconfig, the server runs as a stdio subprocess of Holmes,
  so nothing but Holmes can reach the kubeconfig's cluster credentials."""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

HELM_DIR = Path(__file__).resolve().parents[1] / "helm" / "holmes"
TEMPLATE = "templates/mcp-servers/kubernetes/deployment.yaml"
CA_PATH = "/etc/kubernetes-mcp-ca"

CA_PEM = """-----BEGIN CERTIFICATE-----
MIIBszCCAVmgAwIBAgIUTESTONLYTESTONLYTESTONLYTESTONLYwCgYIKoZIzj0E
-----END CERTIFICATE-----
"""

pytestmark = pytest.mark.skipif(shutil.which("helm") is None, reason="helm binary not installed")


def _render(tmp_path, ca_pem=None, server_config=None):
    args = [
        "helm", "template", "t", str(HELM_DIR), "--namespace", "holmes",
        "--show-only", TEMPLATE,
        "--set", "mcpAddons.kubernetes.enabled=true",
    ]
    if server_config is not None:
        config_file = tmp_path / "server-config.toml"
        config_file.write_text(server_config)
        args += ["--set-file", f"mcpAddons.kubernetes.config.serverConfig={config_file}"]
    if ca_pem is not None:
        ca_file = tmp_path / "ca.pem"
        ca_file.write_text(ca_pem)
        args += ["--set-file", f"mcpAddons.kubernetes.config.certificateAuthority={ca_file}"]
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    return {doc["kind"]: doc for doc in yaml.safe_load_all(result.stdout) if doc}


def _pod(docs):
    return docs["Deployment"]["spec"]["template"]["spec"]


def test_no_ca_renders_nothing_extra(tmp_path):
    docs = _render(tmp_path)
    assert docs["ConfigMap"]["data"] == {}
    pod = _pod(docs)
    assert "volumes" not in pod
    assert "volumeMounts" not in pod["containers"][0]


def test_ca_is_mounted_for_certificate_authority(tmp_path):
    docs = _render(
        tmp_path,
        ca_pem=CA_PEM,
        server_config=f'require_oauth = true\ncertificate_authority = "{CA_PATH}/ca.crt"\n',
    )
    config_map = docs["ConfigMap"]
    assert config_map["data"]["ca.crt"].strip() == CA_PEM.strip()

    pod = _pod(docs)
    ca_volume = next(v for v in pod["volumes"] if v["name"] == "mcp-ca")
    assert ca_volume["configMap"]["name"] == config_map["metadata"]["name"]
    assert ca_volume["configMap"]["items"] == [{"key": "ca.crt", "path": "ca.crt"}]
    mount = next(m for m in pod["containers"][0]["volumeMounts"] if m["name"] == "mcp-ca")
    assert mount["mountPath"] == CA_PATH
    # The config.toml mount is untouched alongside it.
    assert any(m["mountPath"] == "/etc/kubernetes-mcp" for m in pod["containers"][0]["volumeMounts"])


def test_ca_without_server_config_still_mounts(tmp_path):
    """The CA can come with an external configSecret, so it must not depend on serverConfig."""
    pod = _pod(_render(tmp_path, ca_pem=CA_PEM))
    assert [v["name"] for v in pod["volumes"]] == ["mcp-ca"]
    assert [m["mountPath"] for m in pod["containers"][0]["volumeMounts"]] == [CA_PATH]


KUBECONFIG_SET = ["--set", "mcpAddons.kubernetes.config.kubeconfig.secretName=kc"]


def _render_chart(*extra_args):
    args = [
        "helm", "template", "t", str(HELM_DIR), "--namespace", "holmes",
        "--set", "mcpAddons.kubernetes.enabled=true", *extra_args,
    ]
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def _named(docs, kind, name):
    return next((d for d in docs if d["kind"] == kind and d["metadata"]["name"] == name), None)


def _holmes_pod(docs):
    return _named(docs, "Deployment", "t-holmes")["spec"]["template"]["spec"]


def _k8s_mcp_server_config(docs):
    toolsets = yaml.safe_load(_named(docs, "ConfigMap", "custom-toolsets-configmap")["data"]["custom_toolset.yaml"])
    return toolsets["mcp_servers"]["kubernetes"]["config"]


def test_without_kubeconfig_the_server_is_its_own_deployment():
    docs = _render_chart()
    assert _named(docs, "Deployment", "t-k8s-mcp-server") is not None
    assert _named(docs, "Service", "t-k8s-mcp-server") is not None
    assert "initContainers" not in _holmes_pod(docs)
    assert _k8s_mcp_server_config(docs)["url"] == "http://t-k8s-mcp-server.holmes.svc.cluster.local:8000/mcp"


def test_kubeconfig_runs_the_server_inside_the_holmes_pod(tmp_path):
    config_file = tmp_path / "server-config.toml"
    config_file.write_text('disabled_tools = ["configuration_view"]\n')
    docs = _render_chart(
        *KUBECONFIG_SET,
        "--set", "mcpAddons.kubernetes.networkPolicy.enabled=true",
        "--set-file", f"mcpAddons.kubernetes.config.serverConfig={config_file}",
    )

    # Nothing listens on the network or carries an identity of its own.
    for kind, name in [
        ("Deployment", "t-k8s-mcp-server"),
        ("Service", "t-k8s-mcp-server"),
        ("ServiceAccount", "k8s-mcp-sa"),
        ("ClusterRoleBinding", "t-k8s-mcp"),
        ("NetworkPolicy", "t-k8s-mcp-network-policy"),
    ]:
        assert _named(docs, kind, name) is None, (kind, name)

    pod = _holmes_pod(docs)
    [init] = pod["initContainers"]
    assert init["image"] == "us-central1-docker.pkg.dev/genuine-flight-317411/mcp/kubernetes-mcp-server:v0.0.61-oauth"
    assert init["command"] == ["cp", "/app/kubernetes-mcp-server", "/opt/k8s-mcp/kubernetes-mcp-server"]
    assert init["securityContext"] == {"readOnlyRootFilesystem": True}
    mounts = {m["mountPath"]: m["name"] for m in pod["containers"][0]["volumeMounts"]}
    volumes = {v["name"]: v for v in pod["volumes"]}
    assert volumes[mounts["/opt/k8s-mcp"]]["emptyDir"] == {}
    assert volumes[mounts["/etc/kubernetes"]]["secret"]["secretName"] == "kc"
    assert volumes[mounts["/etc/kubernetes-mcp"]]["secret"]["secretName"] == "t-k8s-mcp-server-config"

    assert _k8s_mcp_server_config(docs) == {
        "mode": "stdio",
        "command": "/opt/k8s-mcp/kubernetes-mcp-server",
        "args": [
            "--read-only",
            "--config", "/etc/kubernetes-mcp/config.toml",
            "--kubeconfig", "/etc/kubernetes/kubeconfig",
            "--cluster-provider", "kubeconfig",
        ],
        "icon_url": "https://cdn.simpleicons.org/kubernetes/326CE5",
    }


def test_kubeconfig_keeps_user_init_containers():
    docs = _render_chart(*KUBECONFIG_SET, "--set-json", 'initContainers=[{"name":"mine","image":"busybox"}]')
    assert [c["name"] for c in _holmes_pod(docs)["initContainers"]] == ["mine", "k8s-mcp-binary"]


def test_kubeconfig_with_oauth_is_refused():
    with pytest.raises(subprocess.CalledProcessError) as error:
        _render_chart(*KUBECONFIG_SET, "--set", "mcpAddons.kubernetes.config.oauth.enabled=true")
    assert "config.oauth needs the server as its own Deployment" in error.value.stderr
