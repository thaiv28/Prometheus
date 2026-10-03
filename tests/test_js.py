"""Runs the JavaScript unit tests (tests/js, Node's built-in runner) under pytest."""

import shutil
import subprocess
from pathlib import Path

import pytest

JS_TESTS = Path(__file__).parent / "js"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_javascript_units():
    result = subprocess.run(
        ["node", "--test", *sorted(str(p) for p in JS_TESTS.glob("*.test.mjs"))],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
