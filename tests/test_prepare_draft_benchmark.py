"""A bounded API request is cached with provenance and stays a two-value API."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "prepare_draft_benchmark", ROOT / "scripts/prepare_draft_benchmark.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_api_observation_uses_actual_metadata_and_cached_provenance(
    monkeypatch, tmp_path
):
    record = {"received_at_utc": "2026-10-18T00:01:00Z", "sha256": "evidence"}
    payload = {
        "frames": [{"rfc460Timestamp": "2026-01-01T00:00:10Z"}],
        "gameMetadata": {
            "blueTeamMetadata": {
                "esportsTeamId": "blue",
                "participantMetadata": [{"championId": "Ahri"}],
            },
            "redTeamMetadata": {
                "esportsTeamId": "red",
                "participantMetadata": [{"championId": "Annie"}],
            },
        },
    }
    calls = []

    def fetch(url, out):
        calls.append(url)
        return record, payload

    monkeypatch.setattr(module, "fetch_json", fetch)
    m = {"game": "123", "start": "2026-01-01T00:00:01Z"}
    obs = module.fetch_observation(m, tmp_path, True)
    assert obs["riot_team_ids"] == ["blue", "red"]
    assert obs["teams"][0][0]["championId"] == "Ahri"
    assert obs["at"] == "2026-01-01T00:00:10Z"
    assert obs["provenance"]["fetched_at"] == record["received_at_utc"]
    assert obs["provenance"]["availability"] == "historical-window-proxy"
    assert module.fetch_observation(m, tmp_path, False) == obs
    assert len(calls) == 1
    assert module.fetch_observation({**m, "game": "missing"}, tmp_path, False) is None
