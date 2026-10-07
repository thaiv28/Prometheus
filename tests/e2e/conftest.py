"""e2e tests run on a small DB built at test time from a committed CSV sample.

The fixture runs the real build steps (scripts/001-004, as setup_db.sh does) on
tests/fixtures/oe_sample/*.csv, a slice of Oracle's Elixir carved by
tests/fixtures/make_oe_sample.py, and points `prometheus.utils.get_engine` at it.

Set PROMETHEUS_E2E_DB=real to run them against the full db/prometheus.db instead
(skipped when it isn't built), or to a path to use another built DB.
"""

import importlib.util
import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from prometheus import DB_PATH, utils

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
SAMPLE = ROOT / "tests" / "fixtures" / "oe_sample"


def _load_script(path, file_override=None):
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if file_override is not None:
        # 002_add_matches.py finds data/raw and db/ from its own __file__.
        module.__file__ = str(file_override)
    return module


def build_fixture_db(root):
    """Build root/db/prometheus.db from the CSV sample with scripts/[0-9]* in order."""
    raw = root / "data" / "raw"
    raw.mkdir(parents=True)
    for csv in SAMPLE.glob("*.csv"):
        shutil.copy(csv, raw / csv.name)
    db_path = root / "db" / "prometheus.db"
    db_path.parent.mkdir()

    for script in sorted(SCRIPTS.glob("[0-9]*")):
        if script.suffix == ".sql":
            with sqlite3.connect(db_path) as conn:
                conn.executescript(script.read_text())
        elif script.suffix == ".py":
            _load_script(script, root / "scripts" / script.name).main()
    return db_path


@pytest.fixture(scope="session")
def e2e_db_path(tmp_path_factory):
    """Path of the DB the e2e tests read, built once per session."""
    choice = os.environ.get("PROMETHEUS_E2E_DB", "")
    if choice:
        db_path = Path(DB_PATH if choice == "real" else choice)
        if not db_path.exists():
            pytest.skip(f"{db_path} is not built")
        return db_path
    root = tmp_path_factory.mktemp("e2e_root")
    db_path = root / "db" / "prometheus.db"
    # 004_bootstrap_elo.py writes through the engine, so point it here for the build.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(utils, "DB_PATH", str(db_path))
        build_fixture_db(root)
    return db_path


@pytest.fixture(scope="module", autouse=True)
def e2e_db(e2e_db_path):
    """Point `utils.get_engine` at the e2e DB for each e2e module, and back after it."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(utils, "DB_PATH", str(e2e_db_path))
        yield e2e_db_path


@pytest.fixture(scope="session")
def using_fixture_db():
    return not os.environ.get("PROMETHEUS_E2E_DB")
