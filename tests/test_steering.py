"""Steering guard: code changes must come with a work-log entry (see AGENTS.md).

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
