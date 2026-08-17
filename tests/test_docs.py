"""Documentation links: every relative link and anchor resolves.

Vendored and generated task directories are skipped: their markdown comes
from upstream and is not ours to fix.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SKIP = (
    "tasks/autoresearch/edgebench/",
    "tasks/autoresearch/frontier-cs/frontier-cs-",
    "tasks/continual-learning/cl-bench/",
    "tasks/continual-learning/terminal-bench/",
    "tasks/continual-learning/swebench-verified/",
    ".venv/",
    "runs/",
    "site/",
)


def _ours(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return not any(skip in rel for skip in SKIP)


DOCS = sorted(p for p in ROOT.rglob("*.md") if _ours(p))


def _anchors(text: str) -> set[str]:
    """GitHub-style slugs for every heading in a page."""
    found = set()
    for line in text.splitlines():
        heading = re.match(r"^#{1,6}\s+(.*)$", line)
        if not heading:
            continue
        slug = heading.group(1).strip().lower()
        slug = re.sub(r"[`*.,:;()\[\]/?!'\"]", "", slug)
        found.add(re.sub(r"\s+", "-", slug))
    return found


def test_docs_were_found():
    assert len(DOCS) > 10, f"expected the doc set, found {DOCS}"


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_relative_links_and_anchors_resolve(doc):
    text = doc.read_text()
    for match in re.finditer(r"\]\(([^)]+)\)", text):
        link = match.group(1)
        if link.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target, _, fragment = link.partition("#")
        path = (doc.parent / target).resolve()
        assert path.exists(), f"{doc.name} links to a missing path: {link}"
        if fragment and path.suffix == ".md":
            assert fragment.lower() in _anchors(path.read_text()), (
                f"{doc.name} links to a missing anchor: {link}"
            )
