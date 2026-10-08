"""Tests of the finished research in scripts/research/ (docs/research/README.md).

Every test here is marked `research`: they run with the rest by default, and
`pytest -m "not research"` skips them.
"""

import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if "/tests/research/" in str(item.path):
            item.add_marker(pytest.mark.research)
