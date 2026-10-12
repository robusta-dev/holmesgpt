"""Behaviour tests for the kubernetes/core query tools (kubernetes_jq_query,
kubernetes_count, kubernetes_tabular_query).

The real tool scripts run through the production path (sanitize -> jinja ->
bash) against a stub ``kubectl`` that serves canned API responses and records
every call, so we can assert both the result and the exact API requests made.
"""

import json
import os
import shutil
import stat

import pytest

from holmes.plugins.toolsets import load_toolsets_from_file

KUBERNETES_YAML = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "holmes",
    "plugins",
    "toolsets",
    "kubernetes.yaml",
)

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required to execute the kubernetes tool scripts",
)


def _load_core_tools():
    toolsets = load_toolsets_from_file(KUBERNETES_YAML, strict_check=False)
    core = next(t for t in toolsets if t.name == "kubernetes/core")
    return {t.name: t for t in core.tools}


TOOLS = _load_core_tools()
PAGINATED_TOOLS = ["kubernetes_jq_query", "kubernetes_count"]

# `kubectl api-resources` sorts by group name, so Calico's CRD is listed before
# networking.k8s.io - exactly the ordering that used to shadow the built-in.
API_RESOURCES = """\
bindings                                       v1                                true         Binding
nodes                             no           v1                                false        Node
pods                              po           v1                                true         Pod
networkpolicies                                crd.projectcalico.org/v1          true         NetworkPolicy
pods                                           metrics.k8s.io/v1beta1            true         PodMetrics
networkpolicies                   netpol       networking.k8s.io/v1              true         NetworkPolicy
"""

# Server discovery order (what `kubectl get` uses): built-ins before CRD groups.
APIS = {
    "groups": [
        {"name": "networking.k8s.io"},
        {"name": "metrics.k8s.io"},
        {"name": "crd.projectcalico.org"},
    ]
}

STUB_KUBECTL = r"""#!/bin/bash
printf '%s\n' "$*" >> "$KUBE_STUB_DIR/calls.log"
if [ "$1" = "api-resources" ]; then
  cat "$KUBE_STUB_DIR/api-resources.txt"
  exit 0
fi
if [ "$1" = "get" ] && [ "$2" = "--raw" ]; then
  if [ "$3" = "/apis" ]; then
    cat "$KUBE_STUB_DIR/apis.json"
    exit 0
  fi
  path="${3%%\?*}"
  page=""
  case "$3" in *continue=*) page=".page2" ;; esac
  f="$KUBE_STUB_DIR/raw$(printf '%s' "$path" | tr '/' '_')$page.json"
  if [ -f "$f" ]; then
    cat "$f"
    exit 0
  fi
  echo "Error from server (NotFound): the server could not find the requested resource" >&2
  exit 1
fi
if [ "$1" = "get" ]; then
  cat "$KUBE_STUB_DIR/tabular.txt"
  exit 0
fi
exit 1
"""


def _items(*names, namespace="team-a"):
    return [{"metadata": {"name": n, "namespace": namespace}} for n in names]


def _list(items, cont=None):
    meta = {"continue": cont} if cont else {}
    return {"kind": "List", "metadata": meta, "items": items}


@pytest.fixture
def kube_stub(tmp_path, monkeypatch):
    """A PATH dir with a recording ``kubectl`` stub. Returns a helper object."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    kubectl = bin_dir / "kubectl"
    kubectl.write_text(STUB_KUBECTL)
    kubectl.chmod(kubectl.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "api-resources.txt").write_text(API_RESOURCES)
    (tmp_path / "apis.json").write_text(json.dumps(APIS))
    (tmp_path / "tabular.txt").write_text("NAME\n")
    monkeypatch.setenv("KUBE_STUB_DIR", str(tmp_path))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    class Stub:
        def serve(self, path, body, page2=False):
            name = "raw" + path.replace("/", "_") + (".page2" if page2 else "")
            (tmp_path / f"{name}.json").write_text(json.dumps(body))

        def tabular(self, text):
            (tmp_path / "tabular.txt").write_text(text)

        def calls(self):
            log = tmp_path / "calls.log"
            return log.read_text().splitlines() if log.exists() else []

        def raw_calls(self):
            # resource list requests only (not the /apis discovery lookup)
            return [
                c[len("get --raw ") :]
                for c in self.calls()
                if c.startswith("get --raw /api") and c != "get --raw /apis"
            ]

    return Stub()


def _run(tool_name, params):
    output, _code, _rendered = TOOLS[tool_name]._YAMLTool__invoke_script(params, None)
    return json.loads(output)


def _params(tool_name, kind, **extra):
    if tool_name == "kubernetes_tabular_query":
        params = {"kind": kind, "columns": "NAME:.metadata.name"}
    else:
        params = {"kind": kind, "jq_expr": ".items[] | .metadata.name"}
    params.update(extra)
    return params


def _match_count(tool_name, result):
    return len(result["results"] if tool_name == "kubernetes_jq_query" else result["preview"])


# --- kind resolution (ROB-1564: networkpolicies silently returned 0) ----------


@pytest.mark.parametrize("tool_name", PAGINATED_TOOLS)
@pytest.mark.parametrize("kind", ["networkpolicies", "netpol", "networkpolicy", "NetworkPolicy"])
def test_builtin_group_wins_over_colliding_crd(kube_stub, tool_name, kind):
    kube_stub.serve("/apis/networking.k8s.io/v1/networkpolicies", _list(_items("deny-all", "allow-web")))
    kube_stub.serve("/apis/crd.projectcalico.org/v1/networkpolicies", _list([]))

    result = _run(tool_name, _params(tool_name, kind))

    assert result["stderr"] is None
    assert result["total_items_processed"] == 2
    assert _match_count(tool_name, result) == 2
    assert kube_stub.raw_calls() == ["/apis/networking.k8s.io/v1/networkpolicies?limit=500"]
    assert result["notes"] == [
        "'networkpolicies' also exists in crd.projectcalico.org/v1; queried networking.k8s.io/v1. "
        "Use kind=networkpolicies.crd.projectcalico.org to query the other one."
    ]


@pytest.mark.parametrize("tool_name", PAGINATED_TOOLS)
def test_group_qualified_kind_selects_that_group(kube_stub, tool_name):
    kube_stub.serve("/apis/crd.projectcalico.org/v1/networkpolicies", _list(_items("calico-np")))

    result = _run(tool_name, _params(tool_name, "networkpolicies.crd.projectcalico.org"))

    assert result["total_items_processed"] == 1
    assert kube_stub.raw_calls() == ["/apis/crd.projectcalico.org/v1/networkpolicies?limit=500"]
    assert "Use kind=networkpolicies.networking.k8s.io" in result["notes"][0]


@pytest.mark.parametrize("tool_name", PAGINATED_TOOLS)
def test_core_kind_has_no_note_for_metrics_mirror(kube_stub, tool_name):
    kube_stub.serve("/api/v1/pods", _list(_items("web-1")))

    result = _run(tool_name, _params(tool_name, "pods"))

    assert result["total_items_processed"] == 1
    assert kube_stub.raw_calls() == ["/api/v1/pods?limit=500"]
    assert result["notes"] == []


@pytest.mark.parametrize("tool_name", PAGINATED_TOOLS)
def test_unknown_kind_reports_error(kube_stub, tool_name):
    result = _run(tool_name, _params(tool_name, "widgets"))

    assert result["stderr"].startswith("Unable to find resource kind 'widgets'.")
    assert kube_stub.raw_calls() == []


@pytest.mark.parametrize("tool_name", PAGINATED_TOOLS)
def test_continue_token_is_url_encoded(kube_stub, tool_name):
    kube_stub.serve("/api/v1/pods", _list(_items("web-1"), cont="a+b/c="))
    kube_stub.serve("/api/v1/pods", _list(_items("web-2")), page2=True)

    result = _run(tool_name, _params(tool_name, "pods"))

    assert result["total_items_processed"] == 2
    assert kube_stub.raw_calls() == [
        "/api/v1/pods?limit=500",
        "/api/v1/pods?limit=500&continue=a%2Bb%2Fc%3D",
    ]
