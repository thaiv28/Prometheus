import json
import sys

import pandas as pd

sys.path.insert(0, "scripts")
import update_props
from test_props_live import _table


def test_hourly_refresh_prices_saves_calls_and_writes_the_page_file(
    tmp_path, monkeypatch
):
    start = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)).floor("h")
    table = _table()
    table["matches"][0]["start"] = start.strftime("%Y-%m-%dT%H:%MZ")
    (tmp_path / "dist.json").write_text(json.dumps(table))
    line = {
        "read_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "source": "underdog",
        "line_id": "1",
        "player": "Yike",
        "team": "KC",
        "stat": "kills",
        "maps": "1-3",
        "line": 12.5,
        "over_mult": 1.0,
        "under_mult": 1.0,
        "over_prob": 0.5,
        "start": start.isoformat(),
    }
    (tmp_path / "lines.jsonl").write_text(json.dumps(line) + "\n")
    argv = [
        "update_props.py",
        "--lines",
        str(tmp_path / "lines.jsonl"),
        "--calls",
        str(tmp_path / "calls.json"),
        "--dist",
        str(tmp_path / "dist.json"),
        "--out",
        str(tmp_path / "out"),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    update_props.main()
    calls = json.loads((tmp_path / "calls.json").read_text())
    assert list(calls) == ["underdog|1"] and calls["underdog|1"]["side"] == "under"
    page = json.loads((tmp_path / "out" / "props-lines.json").read_text())
    assert [(c["match"], c["player"], c["app"]) for c in page["lines"]] == [
        ("m1", "p1", "underdog")
    ]


def test_hourly_refresh_without_projections_does_nothing(tmp_path, monkeypatch, capsys):
    argv = [
        "update_props.py",
        "--dist",
        str(tmp_path / "missing.json"),
        "--out",
        str(tmp_path / "out"),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    update_props.main()
    assert "No projections" in capsys.readouterr().out
    assert not (tmp_path / "out").exists()
