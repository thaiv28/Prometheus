"""Multi-game private execution contracts; synthetic artifacts, no network."""

import copy
import datetime as dt
import io
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_execution import NOW, candidate_api, candidate_proposal, harness, settings
from test_execution_api import PublicClient, config
from test_execution_runner import Parameter, clients, control, handler

from prometheus import alert_contract as ac
from prometheus import market_blend as mb
from prometheus.execution import core
from prometheus.execution.kalshi import Kalshi

FIXTURES = Path(__file__).with_name("fixtures")


@pytest.fixture
def game_artifacts(monkeypatch):
    monkeypatch.setattr(mb, "GAME_PATH", FIXTURES / "game_blends")
    mb.load.cache_clear()
    yield
    mb.load.cache_clear()


def game_document(game="cs2", now=NOW, **changes):
    return {
        "version": 1,
        "game": game,
        "generated": now.isoformat(),
        "matches": [
            {
                ac.CANDIDATE_KEY: {
                    "kind": "candidate-v1",
                    "schema_version": 1,
                    "game": game,
                    "series_ticker": ac.GAMES[game]["series"],
                    "at": now.isoformat(),
                    "fixture_id": "f",
                    "event_ticker": ac.GAMES[game]["series"] + "-F",
                    "teams": ["GamerLegion", "HOTU"],
                    "team_homes": {},
                    "international": game == "cs2",
                    "group": next(g for g, v in ac.GAME_GROUPS.items() if v == game),
                    "start": (now + dt.timedelta(days=1)).isoformat(),
                    "raw": {"GamerLegion": 0.999, "HOTU": 0.001},
                    "provenance": {},
                    **changes,
                }
            }
        ],
    }


@pytest.mark.parametrize("game", ["cs2", "valorant"])
def test_game_candidates_and_frozen_clipping(game_artifacts, game):
    proposals = ac.saved_candidates(game_document(game), NOW)
    assert len(proposals) == 2
    artifact = mb.load(game)
    model = artifact["snapshots"][0]
    for p in proposals:
        assert p["game"] == game and p["series_ticker"] == ac.GAMES[game]["series"]
        raw = float(p["probability"])
        assert p["trading"] == {
            "version": "game-blend-v1",
            "policy": mb.POLICY,
            "game": game,
            "model": model["available_from"],
            "trained_through": model["trained_through"],
            "market_slope": model["market_slope"],
            "gap_slope": model["gap_slope"],
            "raw_probability": raw,
        }
        for market in (0.0001, 0.4, 0.9999):

            def logit(p):
                p = min(0.99, max(0.01, p))
                return math.log(p / (1 - p))

            z = model["market_slope"] * logit(market) + model["gap_slope"] * (
                logit(raw) - logit(market)
            )
            expected = 1 / (1 + math.exp(-z))
            assert mb.combine(raw, market, model, clip=0.01) == pytest.approx(expected)
            assert mb.refresh(p["trading"], market) == pytest.approx(expected)
            estimate = mb.estimate(raw, market, NOW, game=game)
            assert estimate["probability"] == pytest.approx(expected)
            assert estimate["game"] == game
        core.validate_alert(p, core.Config.parse(settings(games={game: True})), NOW)
        with pytest.raises(ValueError, match=r"^game_disabled$"):
            core.validate_alert(p, core.Config.parse(settings()), NOW)
        with pytest.raises(ValueError, match="unknown trading snapshot"):
            mb.refresh({**p["trading"], "gap_slope": 99}, 0.4)


def test_league_contract_and_refresh_exactly_match_before_change():
    baseline = json.loads((FIXTURES / "execution_lol_baseline.json").read_text())
    now = dt.datetime.fromisoformat(baseline["now"])
    proposals = ac.saved_candidates(baseline["document"], now)
    assert json.dumps(proposals) == json.dumps(baseline["proposals"])
    assert [mb.refresh(p["trading"], 0.4) for p in proposals] == baseline["refresh"]
    assert mb.estimate(0.7, 0.4, now) == baseline["estimate"]


@pytest.mark.parametrize(
    "changes",
    [
        {"game": "lol"},
        {"game": "valorant"},
        {"game": "unknown"},
        {"series_ticker": "KXLOLGAME"},
        {"group": "major-domestic"},
        {"kind": "bad"},
        {"schema_version": 2},
        {"at": "2026-10-15T12:01Z"},
        {"at": "2026-10-15T08:59Z"},
        {"start": NOW.isoformat()},
        {"raw": {"GamerLegion": 0, "HOTU": 1}},
    ],
)
def test_game_candidate_rejects_wrong_identity_or_existing_guards(
    game_artifacts, changes
):
    document = game_document()
    document["matches"][0][ac.CANDIDATE_KEY].update(changes)
    assert ac.saved_candidates(document, NOW) == []


def test_valorant_international_never_trades(game_artifacts):
    assert (
        ac.saved_candidates(
            game_document(
                "valorant", group="valorant-international", international=True
            ),
            NOW,
        )
        == []
    )


def test_missing_game_artifact_and_not_yet_available(
    game_artifacts, monkeypatch, tmp_path
):
    assert mb.snapshot("2026-01-31T00:00Z", "cs2") is None
    assert (
        ac.saved_candidates(
            game_document(now=dt.datetime(2026, 1, 31, tzinfo=dt.UTC)),
            dt.datetime(2026, 1, 31, tzinfo=dt.UTC),
        )
        == []
    )
    monkeypatch.setattr(mb, "GAME_PATH", tmp_path)
    mb.load.cache_clear()
    for game in ac.GAME_GROUPS.values():
        assert mb.snapshot(NOW, game) is None
        assert ac.saved_candidates(game_document(game), NOW) == []
        assert mb.estimate(0.8, 0.5, NOW, game=game) is None
    assert mb.snapshot(NOW) is not None


@pytest.mark.parametrize(
    "changes",
    [
        {"version": "market-blend-v1"},
        {"game": "valorant"},
        {"series_ticker": "KXLOLGAME"},
        {"clip": 0},
        {"clip": 0.5},
        {"clip": float("nan")},
        {"clip": "0.01"},
        {"training_series": 299},
        {"market_slope": float("inf")},
        {"gap_slope": float("nan")},
        {"trained_through": "2026-02-01T00:00:00+00:00"},
        {"duplicate": True},
    ],
)
def test_invalid_artifacts_fail_closed(game_artifacts, monkeypatch, tmp_path, changes):
    data = copy.deepcopy(mb.load("cs2"))
    for k, v in changes.items():
        if k in {"training_series", "market_slope", "gap_slope", "trained_through"}:
            data["snapshots"][0][k] = v
        elif k == "duplicate":
            data["snapshots"] *= 2
        else:
            data[k] = v
    (tmp_path / "cs2.json").write_text(json.dumps(data))
    monkeypatch.setattr(mb, "GAME_PATH", tmp_path)
    mb.load.cache_clear()
    with pytest.raises(ValueError):
        mb.load("cs2")
    assert ac.saved_candidates(game_document(), NOW) == []


@pytest.mark.parametrize(
    "games",
    [
        None,
        [],
        True,
        {"lol": True},
        {"unknown": False},
        {"cs2": 1},
        {"valorant": "true"},
    ],
)
@pytest.mark.parametrize("mode", ["off", "demo"])
def test_invalid_game_config(games, mode):
    with pytest.raises(ValueError, match="games"):
        core.Config.parse(settings(mode=mode, games=games))


def test_game_configure_requires_off_and_preserves_other_settings():
    parameter = Parameter(settings(mode="off"))
    control.configure(parameter, "/config", {"games": {"cs2": True, "valorant": False}})
    assert parameter.value == settings(
        mode="off", games={"cs2": True, "valorant": False}
    )
    parameter.value["mode"] = "live"
    with pytest.raises(ValueError, match="off"):
        control.configure(parameter, "/config", {"games": {"valorant": True}})


def test_game_veto_keeps_cloud9_but_ignores_home_leagues():
    for team in ("Cloud9", "Cloud9 Esports", "C9"):
        assert (
            ac.trade_veto({"game": "cs2", "teams": [team, "HOTU"]}) == "cloud9_fixture"
        )
    proposal = {
        "game": "cs2",
        "teams": ["HOTU", "GamerLegion"],
        "international": True,
        "team_homes": {},
    }
    assert ac.trade_veto(proposal) is None
    assert (
        ac.trade_veto({**proposal, "game": "lol"})
        == "missing_international_home_leagues"
    )


@pytest.mark.parametrize("enabled", [False, True])
def test_game_bulk_selection_and_shared_execution(game_artifacts, enabled):
    _, api, ledger, execute = harness(settings(games={"cs2": enabled}))
    candidate_api(api)
    quotes = api.open_markets()
    calls = []

    def bulk(series_tickers):
        calls.append(series_tickers)
        return {**quotes, "KXCS2GAME-F": quotes["KXLOLGAME-F"]}

    api.open_markets = bulk
    proposal = candidate_proposal(
        game="cs2",
        series_ticker="KXCS2GAME",
        event_ticker="KXCS2GAME-F",
        group="cs2-series",
        trading=mb.estimate(0.999, 0.59, NOW, game="cs2"),
    )
    # Include a League proposal that fails the quote screen; only CS2 can submit.
    league = candidate_proposal(trading=mb.estimate(0.001, 0.59, NOW))
    if not enabled:
        api.open_markets = lambda: quotes
    result = execute([proposal, league])
    assert result["submitted"] == int(enabled)
    assert result["errors"] == 0
    assert bool(ledger.pending()) == enabled
    if enabled:
        assert calls == [("KXCS2GAME", "KXLOLGAME")]
        assert api.calls[0]["count"]


@pytest.mark.parametrize("word", ["CS2", "League of Legends"])
def test_cs2_rule_resolution(word):
    api = PublicClient()
    api.event.update(event_ticker="KXCS2GAME-F", series_ticker="KXCS2GAME")
    books = {}
    for market, team in zip(api.event["markets"], ["GamerLegion", "HOTU"], strict=True):
        book = api.books[market["ticker"]]
        book["no_dollars"] = [[".4", "2"]]
        books[f"KXCS2GAME-F-{team}"] = book
        market.update(
            ticker=f"KXCS2GAME-F-{team}",
            event_ticker="KXCS2GAME-F",
            yes_sub_title=team,
            rules_primary=f"If {team} wins the Tesla Cup 2026: GamerLegion vs. HOTU {word} match originally scheduled for Oct 29, 2026 at 2:00 PM EDT",
        )
    api.books = books
    original = api.request

    def request(method, path, body=None, **query):
        if path == "/series/KXCS2GAME":
            return {"series": api.series}
        return original(method, path, body, **query)

    api.request = request
    proposal = {
        "game": "cs2",
        "event_ticker": "KXCS2GAME-F",
        "start": "2026-10-29T18:00Z",
        "teams": ["GamerLegion", "HOTU"],
        "backed_team": "HOTU",
    }
    if word == "CS2":
        assert len(api.resolve(proposal, NOW, config())) == 2
    else:
        with pytest.raises(ValueError, match="unsupported_or_ambiguous_market"):
            api.resolve(proposal, NOW, config())
    with pytest.raises(ValueError, match="unsupported_game_live_map"):
        api.resolve({**proposal, "kind": "live-map-30s-v1"}, NOW, config())


def test_open_markets_reads_each_series_and_merges_events():
    api = object.__new__(Kalshi)
    calls = []

    def request(method, path, body=None, **query):
        calls.append((method, path, query))
        return {
            "markets": [
                {
                    "event_ticker": "E",
                    "ticker": query["series_ticker"],
                    "yes_sub_title": "HOTU",
                    "yes_bid_dollars": ".4",
                    "yes_ask_dollars": ".5",
                }
            ]
        }

    api.request = request
    tickers = tuple(g["series"] for g in ac.GAMES.values())
    quotes = api.open_markets(tickers)
    assert [c[2]["series_ticker"] for c in calls] == list(tickers)
    assert all(c[:2] == ("GET", "/markets") and c[2]["status"] == "open" for c in calls)
    assert len(quotes["E"]) == 3


@pytest.mark.parametrize(
    "mode,games,keys",
    [
        ("off", {"cs2": True}, "cs2.json"),
        ("demo", {}, "cs2.json"),
        ("demo", {"cs2": False}, "cs2.json"),
        ("demo", {"cs2": True}, ""),
        ("demo", {"cs2": True}, " cs2.json, valorant.json, "),
        ("demo", {"valorant": True}, "cs2.json,valorant.json"),
    ],
)
def test_handler_game_sources_are_opt_in(monkeypatch, mode, games, keys):
    aws, _ = clients(monkeypatch, settings(mode=mode, games=games))
    monkeypatch.setenv("GAME_CANDIDATE_KEYS", keys)
    reads, adapted, reconciled = [], [], []

    def read(**kw):
        reads.append(kw)
        return {"Body": io.BytesIO(json.dumps({"source": kw["Key"]}).encode())}

    aws["s3"] = SimpleNamespace(get_object=read)
    monkeypatch.setattr(
        handler,
        "saved_candidates",
        lambda doc, now: adapted.append(doc["source"]) or [doc],
    )

    def run(proposals, *args, **kwargs):
        reconciled.extend(proposals)
        return {"errors": 0}

    monkeypatch.setattr(core, "run", run)
    handler.handler({}, None, clients=aws)
    expected = [] if mode == "off" else ["private-log.json"]
    if mode != "off" and any(games.values()):
        expected += [k.strip() for k in keys.split(",") if k.strip()]
    assert adapted == expected
    assert reads == [{"Bucket": "private-backup", "Key": k} for k in expected]
    assert reconciled == [{"source": k} for k in expected]


@pytest.mark.parametrize(
    "error", ["NoSuchKey", "404", "AccessDenied", "bad-json", "transport"]
)
def test_handler_game_source_errors_still_reconcile(monkeypatch, error):
    aws, _ = clients(monkeypatch, settings(games={"cs2": True}))
    monkeypatch.setenv("GAME_CANDIDATE_KEYS", "missing.json,next.json")
    reads, ran = [], []

    class S3Error(Exception):
        def __init__(self):
            self.response = {"Error": {"Code": error}}

    def read(**kw):
        reads.append(kw["Key"])
        if kw["Key"] == "missing.json":
            if error == "bad-json":
                return {"Body": io.BytesIO(b"invalid")}
            if error == "transport":
                raise OSError("transport unavailable")
            raise S3Error()
        return {"Body": io.BytesIO(b'{"matches": []}')}

    aws["s3"] = SimpleNamespace(get_object=read)
    monkeypatch.setattr(
        core,
        "run",
        lambda *args, **kwargs: ran.append(True) or {"errors": 0, "reconciled": 1},
    )
    if error in {"NoSuchKey", "404"}:
        assert handler.handler({}, None, clients=aws)["reconciled"] == 1
    else:
        with pytest.raises(RuntimeError, match="existing intents reconciled"):
            handler.handler({}, None, clients=aws)
    assert ran == [True]
    assert reads == ["private-log.json", "missing.json", "next.json"]


def test_league_aliases_never_rename_other_games_teams():
    api = Kalshi.__new__(Kalshi)
    api.aliases = {"DRX": "Kiwoom DRX"}
    teams = ["DRX", "Paper Rex"]
    assert api.canonical("DRX", teams, "valorant") == "DRX"
    assert api.canonical("DRX", ["Kiwoom DRX", "T1"]) == "Kiwoom DRX"
