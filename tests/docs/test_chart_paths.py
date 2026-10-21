import re
from pathlib import Path
from typing import List

from docs.chart_checks import chart_defaults, unresolved_key_paths
from docs.custom_fences import FENCE_LINE_RE
from docs.fence_checks import PASSED_TO_HOLMES

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"
DEFAULTS = chart_defaults(REPO / "helm" / "holmes", PASSED_TO_HOLMES)

INLINE_CODE_RE = re.compile(r"`([^`]+)`")
# The forms of a span that names a chart path: mapping keys joined by dots, optionally
# followed by `: <value>`.
CHART_PATH_RE = re.compile(r"(?P<path>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)(?:: .+)?")

# Spans that start with a top-level key of the values but name something else.
NOT_CHART_PATHS = {
    "tls.crt": "a key of a Kubernetes TLS secret",
    "tls.key": "a key of a Kubernetes TLS secret",
    "mcpAddons.mariadb": "an add-on the chart no longer has, which a page tells readers to delete from their values",
}


def _values_at(keys: List[str]) -> dict:
    """The values that set the key path `keys`."""
    values: dict = {}
    node = values
    for key in keys:
        node[key] = {}
        node = node[key]
    return values


def unknown_chart_paths(text: str, page: str) -> List[str]:
    """An error for each inline code span outside a fence that starts with a top-level key of
    the Holmes chart's values and names a path the values do not have, resolved as the chart
    check of a fence resolves its key paths."""
    errors = []
    in_fence = False
    for number, line in enumerate(text.split("\n"), 1):
        if FENCE_LINE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for span in INLINE_CODE_RE.findall(line):
            if re.split(r"[.:\[ =]", span, maxsplit=1)[0] not in DEFAULTS or span in NOT_CHART_PATHS:
                continue
            match = CHART_PATH_RE.fullmatch(span)
            if match is None:
                errors.append(f"{page}:{number}: `{span}` starts with a chart key but is not a chart path in a form this check reads")
            elif any(unresolved_key_paths(_values_at(match["path"].split(".")), DEFAULTS)):
                errors.append(f"{page}:{number}: `{span}`: `{match['path']}` is not a key path of the chart's values.yaml")
    return errors


def test_every_chart_path_a_page_names_in_inline_code_is_in_the_chart_values():
    errors = []
    for path in sorted(DOCS.rglob("*.md")):
        errors += unknown_chart_paths(path.read_text(), path.relative_to(DOCS).as_posix())
    assert errors == []


def test_every_span_listed_as_not_a_chart_path_would_otherwise_fail():
    """An entry the chart check would take is a chart path, and leaves the list."""
    assert [span for span in NOT_CHART_PATHS if not any(unresolved_key_paths(_values_at(span.split(".")), DEFAULTS))] == []


def test_a_chart_path_the_values_lack_is_an_error_naming_the_page_and_line():
    text = (
        "Set `mcpAddons.aws.serviceAccount.name`, `serviceAccount.annotations.team` and `logLevel: DEBUG`.\n"
        "```yaml\n`mcpAddons.aws.missing`\n```\n"
        "Then `mcpAddons.aws.serviceAccount.missing`, `toolsets.yaml` and `resources.limits[0]`.\n"
    )
    assert unknown_chart_paths(text, "page.md") == [
        "page.md:5: `mcpAddons.aws.serviceAccount.missing`: `mcpAddons.aws.serviceAccount.missing` is not a key path of the chart's values.yaml",
        "page.md:5: `resources.limits[0]` starts with a chart key but is not a chart path in a form this check reads",
    ]
