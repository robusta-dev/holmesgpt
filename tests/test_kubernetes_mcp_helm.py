"""Renders the Kubernetes MCP addon with `helm template` and checks:

- a CA certificate set in mcpAddons.kubernetes.config.certificateAuthority
  reaches the MCP server pod, so `certificate_authority` in serverConfig can
  point at it (for example, Dex served from a private CA);
- the MCP ServiceAccount's role bindings: by default the built-in "view" role
  plus a chart role with Holmes's read rules (node, RBAC and CRD reads "view"
  lacks), never the customClusterRoleRules that widen Holmes itself."""

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


def _helm_template(*extra_args):
    args = [
        "helm", "template", "t", str(HELM_DIR), "--namespace", "holmes",
        "--set", "mcpAddons.kubernetes.enabled=true", *extra_args,
    ]
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def _render(tmp_path, ca_pem=None, server_config=None):
    args = ["--show-only", TEMPLATE]
    if server_config is not None:
        config_file = tmp_path / "server-config.toml"
        config_file.write_text(server_config)
        args += ["--set-file", f"mcpAddons.kubernetes.config.serverConfig={config_file}"]
    if ca_pem is not None:
        ca_file = tmp_path / "ca.pem"
        ca_file.write_text(ca_pem)
        args += ["--set-file", f"mcpAddons.kubernetes.config.certificateAuthority={ca_file}"]
    return {doc["kind"]: doc for doc in _helm_template(*args)}


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


MCP_SA = "k8s-mcp-sa"
CUSTOM_SECRET_RULE = (
    "--set-json",
    'customClusterRoleRules[0]={"apiGroups":[""],"resources":["secrets"],"verbs":["get"]}',
)


def _mcp_rbac(*helm_args):
    """Returns {(kind, name): role} for every role the chart renders, and the MCP
    ServiceAccount's bindings as (binding kind, binding name, role kind, role name)."""
    docs = _helm_template(*helm_args)
    roles = {(d["kind"], d["metadata"]["name"]): d for d in docs if d["kind"] in ("Role", "ClusterRole")}
    bindings = sorted(
        (d["kind"], d["metadata"]["name"], d["roleRef"]["kind"], d["roleRef"]["name"])
        for d in docs
        if d["kind"] in ("RoleBinding", "ClusterRoleBinding") and any(s["name"] == MCP_SA for s in d["subjects"])
    )
    return roles, bindings


def _reads(role, api_group, resource):
    return any(
        api_group in rule["apiGroups"] and resource in rule["resources"] and {"get", "list"} <= set(rule["verbs"])
        for rule in role["rules"]
    )


def test_default_binds_view_and_a_read_only_chart_role():
    roles, bindings = _mcp_rbac()
    # roleRef is immutable, so the view binding keeps the name and roleRef earlier
    # releases created, or `helm upgrade` fails.
    assert bindings == [
        ("ClusterRoleBinding", "t-k8s-mcp", "ClusterRole", "view"),
        ("ClusterRoleBinding", "t-k8s-mcp-role-binding", "ClusterRole", "t-k8s-mcp-role"),
    ]
    role = roles[("ClusterRole", "t-k8s-mcp-role")]
    assert _reads(role, "", "nodes")
    assert _reads(role, "rbac.authorization.k8s.io", "rolebindings")
    assert _reads(role, "apiextensions.k8s.io", "customresourcedefinitions")
    assert {verb for rule in role["rules"] for verb in rule["verbs"]} <= {"get", "list", "watch"}


def test_chart_role_has_holmes_read_rules_without_custom_rules():
    roles, _ = _mcp_rbac(*CUSTOM_SECRET_RULE)
    holmes_rules = roles[("ClusterRole", "t-holmes-cluster-role")]["rules"]
    assert holmes_rules[0]["resources"] == ["secrets"]
    assert roles[("ClusterRole", "t-k8s-mcp-role")]["rules"] == holmes_rules[1:]


def test_namespace_scoped_uses_a_role_in_release_namespace():
    roles, bindings = _mcp_rbac("--set", "namespaceScopedRBAC=true")
    assert bindings == [
        ("ClusterRoleBinding", "t-k8s-mcp", "ClusterRole", "view"),
        ("RoleBinding", "t-k8s-mcp-role-binding", "Role", "t-k8s-mcp-role"),
    ]
    assert roles[("Role", "t-k8s-mcp-role")]["metadata"]["namespace"] == "holmes"


def test_chart_role_does_not_depend_on_holmes_service_account():
    roles, bindings = _mcp_rbac("--set", "createServiceAccount=false")
    assert ("ClusterRole", "t-holmes-cluster-role") not in roles
    assert ("ClusterRoleBinding", "t-k8s-mcp-role-binding", "ClusterRole", "t-k8s-mcp-role") in bindings


def test_explicit_cluster_role_is_bound_alone():
    roles, bindings = _mcp_rbac("--set", "mcpAddons.kubernetes.serviceAccount.clusterRole=cluster-admin")
    assert bindings == [("ClusterRoleBinding", "t-k8s-mcp", "ClusterRole", "cluster-admin")]
    assert ("ClusterRole", "t-k8s-mcp-role") not in roles


def test_oauth_mode_binds_nothing():
    roles, bindings = _mcp_rbac("--set", "mcpAddons.kubernetes.serviceAccount.createClusterRoleBinding=false")
    assert bindings == []
    assert ("ClusterRole", "t-k8s-mcp-role") not in roles
