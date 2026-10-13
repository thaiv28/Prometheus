"""scripts/prop_data.sh against a fake `aws` that maps s3:// paths to a folder."""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "prop_data.sh"
FAKE_AWS = """#!/usr/bin/env bash
map() { case "$1" in s3://*) echo "$FAKE_S3/${1#s3://}";; *) echo "$1";; esac; }
s=$(map "$3"); d=$(map "$4")
[ -f "$s" ] || { echo "An error occurred (404) when calling the HeadObject operation: Not Found" >&2; exit 1; }
mkdir -p "$(dirname "$d")"; cp "$s" "$d"
"""


def _run(tmp_path, *args):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "aws").write_text(FAKE_AWS)
    (bin_dir / "aws").chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "FAKE_S3": str(tmp_path / "s3"),
    }
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )


def test_lines_log_saves_over_a_backup_and_refuses_to_shrink(tmp_path):
    log, uri = "data/prop_lines.jsonl", "s3://bucket/props/prop_lines.jsonl"
    (tmp_path / "data").mkdir()
    (tmp_path / log).write_text('{"a": 1}\n{"a": 2}\n')
    assert _run(tmp_path, "save", log, uri).returncode == 0
    # A second save compares with the backup (downloaded without the extension).
    (tmp_path / log).write_text('{"a": 1}\n{"a": 2}\n{"a": 3}\n')
    second = _run(tmp_path, "save", log, uri)
    assert second.returncode == 0, second.stderr
    assert "3 entries" in second.stdout
    (tmp_path / log).write_text('{"a": 1}\n')
    shrunk = _run(tmp_path, "save", log, uri)
    assert shrunk.returncode == 1 and "the backup has 3" in shrunk.stderr
    (tmp_path / log).unlink()
    assert "3 entries" in _run(tmp_path, "restore", log, uri).stdout


def test_calls_count_keys_and_missing_backup_starts_new(tmp_path):
    calls, uri = "data/prop_calls.json", "s3://bucket/props/prop_calls.json"
    restored = _run(tmp_path, "restore", calls, uri)
    assert restored.returncode == 0 and "starting a new one" in restored.stdout
    (tmp_path / calls).write_text('{"x": 1, "y": 2}')
    assert _run(tmp_path, "save", calls, uri).returncode == 0
    again = _run(tmp_path, "save", calls, uri)
    assert again.returncode == 0 and "2 entries" in again.stdout
