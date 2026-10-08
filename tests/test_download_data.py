import datetime
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "download_data", Path(__file__).parent.parent / "scripts" / "download_data.py"
)
dd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dd)

NAMES = [
    f"{y}_LoL_esports_match_data_from_OraclesElixir.csv" for y in (2024, 2025, 2026)
]


def _csv(path, *dates):
    path.write_text(
        "gameid,date\n" + "".join(f"g{i},{d}\n" for i, d in enumerate(dates))
    )
    return path


def test_wanted_takes_the_current_year_unless_files_are_missing(tmp_path):
    for n in NAMES:
        (tmp_path / n).touch()
    oct_ = datetime.date(2026, 10, 7)
    assert dd.wanted(NAMES, tmp_path, oct_) == NAMES[2:]
    assert dd.wanted(NAMES, tmp_path, datetime.date(2026, 1, 5)) == NAMES[1:]
    assert dd.wanted(NAMES, tmp_path, oct_, full=True) == NAMES
    (tmp_path / NAMES[0]).unlink()
    assert dd.wanted(NAMES, tmp_path, oct_) == NAMES


def test_install_replaces_only_with_newer_games(tmp_path):
    dest = _csv(tmp_path / "old.csv", "2026-10-01 10:00:00")
    assert not dd.install(_csv(tmp_path / "same.csv", "2026-10-01 10:00:00"), dest)
    assert not dd.install(_csv(tmp_path / "older.csv", "2026-09-30 10:00:00"), dest)
    (tmp_path / "html.csv").write_text("<html>Too many users</html>")
    assert not dd.install(tmp_path / "html.csv", dest)
    assert dd.newest_date(dest) == "2026-10-01 10:00:00"
    assert dd.install(
        _csv(tmp_path / "new.csv", "2026-10-01 10:00:00", "2026-10-07 11:00:00"), dest
    )
    assert dd.newest_date(dest) == "2026-10-07 11:00:00"
    assert dd.install(
        _csv(tmp_path / "first.csv", "2026-10-07"), tmp_path / "absent.csv"
    )
