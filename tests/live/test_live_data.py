import importlib.util
import io
import json
import tarfile
from pathlib import Path

from prometheus.live.data import load_maps

spec = importlib.util.spec_from_file_location(
    "live_data", Path(__file__).resolve().parents[2] / "scripts" / "live_data.py"
)
live_data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live_data)


def frame(at, gold0, gold1, clock):
    teams = [
        {"gold": g, "kills": 0, "towers": 0, "dragons": 0, "barons": 0, "inhibitors": 0}
        for g in (gold0, gold1)
    ]
    return {
        "at": at,
        "source_at": at,
        "clock": None,
        "clock_estimate": clock,
        "teams": teams,
    }


def write_page(path):
    path.parent.mkdir(parents=True)
    page = {
        "match": {"id": "m1", "teams": [{"name": "Karmine Corp"}, {"name": "Cloud9"}]},
        "game": {
            "id": "g4",
            "number": 4,
            "blue": 1,
            "winner": 0,
            "pregame": {"p": 0.62, "by": "FORGE"},
            "frames": [
                frame("2026-10-15T21:14:11Z", 2500, 2500, 0.0),
                frame("2026-10-15T21:20:00Z", 9000, 8000, 349.0),
            ],
            "calls": [
                {"minute": 5.8, "p": 0.7, "by": "x", "at": "2026-10-15T21:20:00Z"}
            ],
            "market": [{"at": "2026-10-15T21:20:01Z", "bid": 0.6, "ask": 0.64}],
        },
    }
    path.write_text(json.dumps(page))


def test_loads_a_saved_map_in_match_team_order(tmp_path):
    write_page(tmp_path / "m1" / "pages" / "map4.json")
    (m,) = load_maps(tmp_path)
    assert (m.match_id, m.number, m.teams, m.blue, m.winner) == (
        "m1",
        4,
        ["Karmine Corp", "Cloud9"],
        1,
        0,
    )
    assert m.frames["gold_lead"].tolist() == [0, 1000]
    assert m.frames["clock_estimate"].tolist() == [0.0, 349.0]
    assert abs(m.market["mid"].iloc[0] - 0.62) < 1e-9
    assert m.calls["p"].tolist() == [0.7]


def test_unpack_extracts_each_archive_once(tmp_path):
    game = tmp_path / "m1" / "g4"
    game.mkdir(parents=True)
    with tarfile.open(game / "archive.tar.gz", "w:gz") as tar:
        data = b'{"at": "t", "bid": 0.5, "ask": 0.6}\n'
        info = tarfile.TarInfo("quotes.jsonl")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    assert live_data.unpack(tmp_path) == 1
    assert (game / "quotes.jsonl").exists()
    assert live_data.unpack(tmp_path) == 0
