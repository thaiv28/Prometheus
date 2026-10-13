"""Exercise the real backup script with a local stand-in for S3."""

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prop_data.sh"


@pytest.mark.parametrize("suffix", ["jsonl", "json"])
@pytest.mark.parametrize("entries", [1, 2, 3])
def test_save_checks_backup_count_using_original_format(tmp_path, suffix, entries):
    aws = tmp_path / "aws"
    aws.write_text('#!/bin/sh\ncp "$3" "$4"\n')
    aws.chmod(0o755)
    backup = tmp_path / "backup"
    local = tmp_path / f"prop_data.{suffix}"

    def content(n):
        rows = {str(i): {"line": i} for i in range(n)}
        if suffix == "jsonl":
            return "\n".join(json.dumps(row) for row in rows.values()) + "\n"
        return json.dumps(rows)

    original = content(2)
    backup.write_text(original)
    local.write_text(content(entries))
    result = subprocess.run(
        ["bash", str(SCRIPT), "save", str(local), str(backup)],
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
    )
    if entries < 2:
        assert result.returncode == 1
        assert "the backup has 2" in result.stderr
        assert backup.read_text() == original
    else:
        assert result.returncode == 0, result.stderr
        assert backup.read_text() == local.read_text()
        assert f"{entries} entries" in result.stdout
