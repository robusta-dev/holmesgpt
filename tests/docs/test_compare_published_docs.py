"""The gate the docs rebuild job runs before pushing gh-pages: scripts/compare_published_docs.py."""

import gzip
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Dict

import pytest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("compare_published_docs", REPO / "scripts" / "compare_published_docs.py")
assert spec and spec.loader
compare_published_docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare_published_docs)


def page(build: str, tab_id: str, body: str) -> str:
    asset_hash = build.replace(".", "") + "0abcdef"
    return f"""<html><head>
<meta name="generator" content="mkdocs-1.6.1, mkdocs-material-{build}">
<link rel="stylesheet" href="../assets/stylesheets/main.{asset_hash}.min.css">
</head><body>
<nav class="md-nav md-nav--primary"><a href="../">Home</a><a href="./">Guide</a></nav>
<article class="md-content__inner md-typeset">
<input checked="checked" id="__tabbed_{tab_id}_1" name="__tabbed_{tab_id}" type="radio">
<p>{body}</p>
</article>
<script src="../assets/javascripts/bundle.{asset_hash}.min.js"></script>
</body></html>"""


def sitemap(lastmod: str) -> bytes:
    return f"<urlset><url><loc>https://example.com/1.0/guide/</loc><lastmod>{lastmod}</lastmod></url></urlset>".encode()


def site(build: str, tab_id: str, lastmod: str, guide_body: str = "Install the agent.", guide_search_text: str = "Install the agent.") -> Dict[str, bytes]:
    asset_hash = build.replace(".", "") + "0abcdef"
    return {
        "versions.json": json.dumps([{"version": "1.0", "title": "1.0", "aliases": ["latest"]}]).encode(),
        "index.html": b'<meta http-equiv="refresh" content="0; url=latest/">',
        "1.0/index.html": page(build, tab_id, "Welcome.").encode(),
        "1.0/guide/index.html": page(build, tab_id, guide_body).encode(),
        f"1.0/assets/javascripts/bundle.{asset_hash}.min.js": f"/* material {build} */".encode(),
        "1.0/search/search_index.json": json.dumps(
            {
                "config": {"lang": ["en"]},
                "docs": [{"location": "", "title": "Home", "text": "Welcome."}, {"location": "guide/", "title": "Guide", "text": guide_search_text}],
            }
        ).encode(),
        "1.0/sitemap.xml": sitemap(lastmod),
        "1.0/sitemap.xml.gz": gzip.compress(sitemap(lastmod), mtime=int(lastmod.replace("-", ""))),
    }


PUBLISHED = site("9.7.6", "0f3c9a2e_1b2c_4d5e_8f90_a1b2c3d4e5f6", "2026-09-01")
REBUILT_SAME_CONTENT = site("9.7.7", "7d1e2f3a_4b5c_4d6e_9f01_b2c3d4e5f6a7", "2026-10-16")


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    """A git repo with a tag per tree below, each tag a root commit holding exactly that tree."""
    trees = {
        "published": PUBLISHED,
        "rebuilt-same-content": REBUILT_SAME_CONTENT,
        "rebuilt-deleted-page": {p: c for p, c in REBUILT_SAME_CONTENT.items() if p != "1.0/guide/index.html"},
        "rebuilt-changed-word": site("9.7.7", "7d1e2f3a_4b5c_4d6e_9f01_b2c3d4e5f6a7", "2026-10-16", guide_body="Install the operator."),
        "rebuilt-edited-search-entry": site("9.7.7", "7d1e2f3a_4b5c_4d6e_9f01_b2c3d4e5f6a7", "2026-10-16", guide_search_text="Install the operator."),
    }
    stream = b""
    for name, files in trees.items():
        stream += f"commit refs/tags/{name}\ncommitter test <test@example.com> 0 +0000\ndata 0\n".encode()
        for rel, content in files.items():
            stream += f"M 100644 inline {rel}\ndata {len(content)}\n".encode() + content + b"\n"
    path = tmp_path_factory.mktemp("gh-pages")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "fast-import", "--quiet"], cwd=path, input=stream, check=True)
    return path


def compare(repo: Path, rebuilt: str, monkeypatch) -> int:
    monkeypatch.chdir(repo)
    return compare_published_docs.main(["published", rebuilt])


def test_passes_a_rebuild_that_changes_only_the_theme(repo, monkeypatch, capsys):
    assert compare(repo, "rebuilt-same-content", monkeypatch) == 0
    assert "No content differences between published and rebuilt-same-content (8 files, 5 changed)" in capsys.readouterr().out


@pytest.mark.parametrize(
    "rebuilt, reported",
    [
        ("rebuilt-deleted-page", "1.0/guide/index.html: missing from the rebuild"),
        ("rebuilt-changed-word", "1.0/guide/index.html [article]\n    -<p>Install the agent.</p>\n    +<p>Install the operator.</p>"),
        ("rebuilt-edited-search-entry", "1.0/search/search_index.json [location 'guide/']"),
    ],
)
def test_refuses_a_content_difference(repo, monkeypatch, capsys, rebuilt, reported):
    assert compare(repo, rebuilt, monkeypatch) == 1
    out = capsys.readouterr().out
    assert reported in out
    assert out.endswith(f"Content differences between published and {rebuilt}: 1\n")
