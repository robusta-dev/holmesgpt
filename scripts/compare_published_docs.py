"""Compare the published docs tree with a rebuilt one and exit 1 on any content difference, printing each.

Usage: python scripts/compare_published_docs.py PUBLISHED_REF REBUILT_REF   (run inside the repo, e.g. origin/gh-pages gh-pages)

A rebuild with a newer docs toolchain may change the theme but not the content, so:
  - a page is compared by its article body and primary nav (a page with no article, such as a redirect, in full), with the random tab group ids docs/custom_fences.py generates replaced
  - search/search_index.json is compared by its config and its entry for each location
  - sitemap.xml is compared without its <lastmod> build dates
  - the theme's own files, under each version's assets/javascripts and assets/stylesheets, are skipped
  - every other file is compared byte for byte
A page that matches once its generator meta and hashed theme asset names are also replaced is not parsed, which skips the parse for nearly every page.
"""

import difflib
import gzip
import json
import re
import subprocess
import sys
from typing import Callable, Dict, Iterator, Tuple

from bs4 import BeautifulSoup

THEME_ASSET_FILE = re.compile(r"^[^/]+/assets/(javascripts|stylesheets)/")
HASHED_ASSET = re.compile(
    r"(assets/(?:javascripts/bundle|javascripts/workers/search|stylesheets/main|stylesheets/palette))\.[0-9a-f]{8,}(\.min\.(?:js|css))"
)
GENERATOR = re.compile(r'<meta name="generator" content="[^"]*"\s*/?>')
TAB_GROUP_ID = re.compile(
    r"__tabbed_[0-9a-f]{8}_[0-9a-f]{4}_[0-9a-f]{4}_[0-9a-f]{4}_[0-9a-f]{12}"
)
LASTMOD = re.compile(rb"<lastmod>[^<]*</lastmod>")

Tree = Dict[str, Tuple[str, str]]


def norm(text: str) -> str:
    text = GENERATOR.sub("<meta generator>", text)
    text = HASHED_ASSET.sub(r"\1.HASH\2", text)
    return TAB_GROUP_ID.sub("__tabbed_ID", text)


def tree(ref: str) -> Tree:
    """Map each file path in ref to its (mode, blob id)."""
    listing = subprocess.run(
        ["git", "ls-tree", "-r", "-z", ref], capture_output=True, text=True, check=True
    ).stdout
    entries = {}
    for entry in filter(None, listing.split("\0")):
        meta, path = entry.split("\t", 1)
        mode, _, oid = meta.split()
        entries[path] = (mode, oid)
    return entries


def blob_reader() -> Callable[[str], bytes]:
    batch = subprocess.Popen(
        ["git", "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )
    requests, replies = batch.stdin, batch.stdout
    assert requests and replies

    def read(oid: str) -> bytes:
        requests.write(oid.encode() + b"\n")
        requests.flush()
        size = int(replies.readline().split()[2])
        data = replies.read(size)
        replies.read(1)
        return data

    return read


def excerpt(old: str, new: str, lines: int = 6) -> str:
    diff = [
        line[:200]
        for line in difflib.unified_diff(
            old.splitlines(), new.splitlines(), n=0, lineterm=""
        )
        if not line.startswith(("---", "+++", "@@"))
    ]
    more = [f"... ({len(diff) - lines} more lines)"] if len(diff) > lines else []
    return "\n    ".join(diff[:lines] + more)


def page_parts(html: str) -> Dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article.md-content__inner")
    if article is None:
        return {"page": html}
    return {"article": str(article), "nav": str(soup.select_one("nav.md-nav--primary"))}


def search_entries(data: bytes) -> Dict[str, object]:
    index = json.loads(data)
    entries: Dict[str, object] = {
        f"location {doc['location']!r}": doc for doc in index["docs"]
    }
    entries["config"] = index["config"]
    return entries


def content_differences(path: str, old: bytes, new: bytes) -> Iterator[str]:
    if path.endswith(".html"):
        old_text, new_text = norm(old.decode()), norm(new.decode())
        if old_text == new_text:
            return
        old_parts, new_parts = page_parts(old_text), page_parts(new_text)
        for part in sorted(old_parts.keys() | new_parts.keys()):
            if old_parts.get(part) != new_parts.get(part):
                yield f"{path} [{part}]\n    {excerpt(old_parts.get(part, ''), new_parts.get(part, ''))}"
    elif path.endswith("search/search_index.json"):
        old_entries, new_entries = search_entries(old), search_entries(new)
        for key in sorted(old_entries.keys() | new_entries.keys()):
            if old_entries.get(key) != new_entries.get(key):
                yield f"{path} [{key}]\n    {excerpt(repr(old_entries.get(key)), repr(new_entries.get(key)))}"
    elif path.endswith(("sitemap.xml", "sitemap.xml.gz")):
        if path.endswith(".gz"):
            old, new = gzip.decompress(old), gzip.decompress(new)
        if LASTMOD.sub(b"", old) != LASTMOD.sub(b"", new):
            yield f"{path}: differs"
    else:
        yield f"{path}: differs"


def differences(
    published: Tree, rebuilt: Tree, read: Callable[[str], bytes]
) -> Iterator[str]:
    for path in sorted(published.keys() | rebuilt.keys()):
        old, new = published.get(path), rebuilt.get(path)
        if old == new or THEME_ASSET_FILE.match(path):
            continue
        if new is None:
            yield f"{path}: missing from the rebuild"
        elif old is None:
            yield f"{path}: new in the rebuild"
        elif old[0] != new[0]:
            yield f"{path}: mode {old[0]} -> {new[0]}"
        else:
            yield from content_differences(path, read(old[1]), read(new[1]))


def main(argv: list) -> int:
    published_ref, rebuilt_ref = argv
    published, rebuilt = tree(published_ref), tree(rebuilt_ref)
    found = 0
    for difference in differences(published, rebuilt, blob_reader()):
        print(difference)
        found += 1
    changed = sum(published.get(path) != entry for path, entry in rebuilt.items())
    if found:
        print(f"Content differences between {published_ref} and {rebuilt_ref}: {found}")
        return 1
    print(
        f"No content differences between {published_ref} and {rebuilt_ref} ({len(rebuilt)} files, {changed} changed)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
