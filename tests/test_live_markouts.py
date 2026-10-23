import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "live_markouts", Path(__file__).resolve().parents[1] / "scripts/live_markouts.py"
)
markouts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(markouts)


@pytest.fixture
def candidates(tmp_path):
    for match, event, backed in (
        ("bo1", "KXLOLGAME-X", "B"),
        ("missing", "KXLOLMAP-X-1", "A"),
    ):
        trading = tmp_path / match / "game" / "trading"
        trading.mkdir(parents=True)
        (trading / "candidate.json").write_text(
            json.dumps(
                {
                    "alert_at": "2026-10-23T00:00:00Z",
                    "backed_team": backed,
                    "teams": ["A", "B"],
                    "original_ask": "0.4",
                    "event_ticker": event,
                    "map_number": 1,
                    "live": {"book": {"bid": 0.5, "ask": 0.6}},
                }
            )
        )
    (tmp_path / "bo1/game/trading/delivered").touch()
    quotes = [
        {
            "at": f"2026-10-23T00:{minute:02d}:{second:02d}Z",
            "bid": bid,
            "ask": bid + 0.02,
        }
        for minute, second, bid in (
            (0, 29, 0.1),
            (0, 31, 0.5),
            (1, 0, 0.6),
            (2, 0, 0.7),
        )
    ]
    (tmp_path / "bo1/series_quotes.jsonl").write_text(
        "\n".join(map(json.dumps, quotes))
    )
    return tmp_path


def test_bo1_flip_horizons_missing_and_delivery(candidates, capsys):
    rows = markouts.markouts(candidates)
    assert rows[0]["delivered"] is True
    assert rows[1]["delivered"] is False
    assert [rows[0][f"markout_{h}"] for h in markouts.HORIZONS] == pytest.approx(
        [0.09, -0.01, -0.11]
    )
    assert rows[0]["quote_delay_30"] == 1
    assert all(rows[1][f"markout_{h}"] is None for h in markouts.HORIZONS)
    markouts.main(["--root", str(candidates)])
    output = capsys.readouterr().out
    assert "Candidates: 2" in output
    assert "30s: n=1, mean markout=+0.090000" in output


def test_map_uses_own_quotes_and_team_zero(candidates):
    (candidates / "missing/game/quotes.jsonl").write_text(
        json.dumps(
            {
                "at": "2026-10-23T00:00:30Z",
                "bid": 0.5,
                "ask": 0.6,
            }
        )
        + "\n"
    )
    row = markouts.markouts(candidates)[1]
    assert row["markout_30"] == pytest.approx(0.15)
    assert row["markout_60"] is None
