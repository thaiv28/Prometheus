"""Steering guard: code changes must come with a work-log entry, and the docs
agents read stay within their word budgets (see AGENTS.md).

Looks at uncommitted changes, including untracked files, so it only bites while
work is in progress. A clean checkout (CI) always passes.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STEERING_DOCS = [
    "AGENTS.md",
    "docs/steering/product.md",
    "docs/steering/current_state.md",
    "docs/steering/tech.md",
    "docs/steering/deployment.md",
    "docs/steering/ui.md",
    "docs/steering/work_log.md",
]
WORK_LOG = "docs/steering/work_log.md"
# Words (as `wc -w` counts them). A doc over budget is condensed, not given a bigger one.
WORD_BUDGETS = {
    "AGENTS.md": 2500,
    "README.md": 4500,
    "PRODUCT.md": 1500,
    "DESIGN.md": 8500,
    "docs/steering/product.md": 2000,
    "docs/steering/current_state.md": 10000,
    "docs/steering/tech.md": 9500,
    "docs/steering/deployment.md": 7000,
    "docs/steering/ui.md": 2500,
}
ENTRY_WORDS = 150
CODE = re.compile(
    r"^(prometheus/|scripts/|templates/|site_static/|tests/|\.github/|pyproject\.toml$|uv\.lock$)"
)


def test_steering_docs_exist():
    missing = [p for p in STEERING_DOCS if not (ROOT / p).is_file()]
    assert not missing, f"Missing steering docs: {missing}"


def _changed_paths():
    out = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    # Entries are "XY path"; renames add the old path as a separate entry.
    return [entry[3:] for entry in out.split("\0") if len(entry) > 3]


@pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="not a git checkout",
)
def test_code_changes_have_a_work_log_entry():
    changed = _changed_paths()
    code = [p for p in changed if CODE.match(p)]
    assert not code or WORK_LOG in changed, (
        f"Code changed without a {WORK_LOG} update: {code[:5]}. "
        "Add a dated entry with what changed and the checks you ran."
    )


def _entries(text):
    """Work-log entries by heading: {'## 2026-…': word count of the body}."""
    parts = re.split(r"^(## .*)$", text, flags=re.M)
    return {h: len(body.split()) for h, body in zip(parts[1::2], parts[2::2])}


@pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="not a git checkout",
)
def test_changed_docs_stay_within_word_budgets():
    changed = set(_changed_paths())
    over = {
        p: (len((ROOT / p).read_text().split()), budget)
        for p, budget in WORD_BUDGETS.items()
        if p in changed
        and (ROOT / p).is_file()
        and len((ROOT / p).read_text().split()) > budget
    }
    assert not over, (
        f"Over word budget (words, budget): {over}. Condense the doc: cut history "
        "(the work log has it), repetition and examples; don't raise the budget."
    )


@pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="not a git checkout",
)
def test_new_work_log_entries_are_short():
    if WORK_LOG not in _changed_paths():
        return
    committed = subprocess.run(
        ["git", "show", f"HEAD:{WORK_LOG}"], cwd=ROOT, capture_output=True, text=True
    ).stdout
    old = _entries(committed)
    long = {
        h: n
        for h, n in _entries((ROOT / WORK_LOG).read_text()).items()
        if n > ENTRY_WORDS and old.get(h) != n
    }
    assert not long, (
        f"Work-log entries over {ENTRY_WORDS} words: {long}. Keep what changed, "
        "the checks run and the limits; put detail in the docs or reports it names."
    )
