"""
The checks of Helm values against a chart and the Kubernetes API: every key path of the values
must be one the chart's `values.yaml` declares, and every object of the values' one render must
match its Kubernetes schema. `check_chart` takes any chart directory, values and release name, so
a caller with another chart runs it too; `docs/fence_checks.py` runs it on each Holmes Helm Chart
tab and adds Holmes's own checks. This module imports nothing from `holmes`: it needs Helm on
PATH, kubernetes-validate, PyYAML and `docs/custom_fences.py`.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Collection, Iterator, List, NamedTuple, Optional

import yaml  # type: ignore

from docs.custom_fences import key_path

try:
    import kubernetes_validate.utils
except ImportError as e:
    raise ImportError(
        "the chart checks need kubernetes-validate, a dev dependency: run `poetry install --with dev`"
    ) from e

# The Kubernetes version whose API schemas, as kubernetes-validate bundles them, the rendered
# objects are checked against.
KUBERNETES_VERSION = "1.36"


def _helm() -> str:
    helm = shutil.which("helm")
    if helm is None:
        raise RuntimeError(
            "the chart checks need Helm on PATH: install Helm 3 or later, https://helm.sh/docs/intro/install/"
        )
    return helm


def _render(chart_dir: Path, values: dict, release: str) -> subprocess.CompletedProcess:
    """`helm template` of the chart with `values`, as the release `release`."""
    return subprocess.run(
        [_helm(), "template", release, str(chart_dir), "-f", "-"],
        input=yaml.safe_dump(values),
        capture_output=True,
        text=True,
    )


def chart_defaults(chart_dir: Path, passed_on: Collection[str] = ()) -> dict:
    """The chart's `values.yaml`, with each top-level value in `passed_on`, which the chart
    passes on to another program that reads the keys under it, free-form."""
    defaults = yaml.safe_load((chart_dir / "values.yaml").read_text()) or {}
    return {**defaults, **dict.fromkeys(passed_on, {})}


def unresolved_key_paths(values, defaults, path: tuple = ()) -> Iterator[tuple]:
    """Each key path of `values` that `defaults`, a chart's values, does not declare, at any
    depth. Under a key whose default is an empty mapping or list, or null, any key resolves;
    a list entry resolves against the first entry of its default."""
    if defaults is None or defaults == {} or defaults == []:
        return
    if isinstance(values, dict):
        for key, value in values.items():
            if isinstance(defaults, dict) and key in defaults:
                yield from unresolved_key_paths(value, defaults[key], path + (key,))
            else:
                yield path + (key,)
    elif isinstance(values, list):
        entry = defaults[0] if isinstance(defaults, list) else defaults
        for index, value in enumerate(values):
            yield from unresolved_key_paths(value, entry, path + (index,))


def _schema_errors(render: str) -> List[str]:
    """Why the Kubernetes API schemas refuse each object of the render, in strict mode, which
    refuses a field the schema does not declare."""
    errors = []
    for document in yaml.safe_load_all(render):
        if not document:
            continue
        name = f"{document['kind']} {document['metadata']['name']}"
        try:
            kubernetes_validate.utils.validate(document, KUBERNETES_VERSION, strict=True)
        except kubernetes_validate.utils.ValidationError as e:
            where = ".".join(map(str, e.path))
            errors.append(
                f"the rendered {name} does not match its Kubernetes {KUBERNETES_VERSION} schema at `{where}`: {e.message}"
            )
        except kubernetes_validate.utils.SchemaNotFoundError:
            errors.append(
                f"the rendered {name} has no Kubernetes {KUBERNETES_VERSION} schema in kubernetes-validate: "
                f"kind {document['kind']}, apiVersion {document['apiVersion']}"
            )
    return errors


class ChartCheck(NamedTuple):
    # `helm template`'s output, or None when Helm refuses the values.
    render: Optional[str]
    errors: List[str]


def check_chart(chart_dir: Path, values: dict, release: str, passed_on: Collection[str] = ()) -> ChartCheck:
    """The render of the chart in `chart_dir` with `values` as the release `release`, and what
    the chart and the Kubernetes API refuse in the values. Every key path must be one the
    chart's `values.yaml` declares (`unresolved_key_paths`; under a top-level key in
    `passed_on`, any key resolves), the values must render once with `helm template`, and
    every rendered object must match its Kubernetes schema."""
    errors = [
        f"`{key_path(path)}` is not a key path of the chart's values.yaml"
        for path in unresolved_key_paths(values, chart_defaults(chart_dir, passed_on))
    ]
    result = _render(chart_dir, values, release)
    if result.returncode != 0:
        return ChartCheck(None, errors + [f"helm template fails: {result.stderr.strip()}"])
    return ChartCheck(result.stdout, errors + _schema_errors(result.stdout))
