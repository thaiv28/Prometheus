"""Multi-game private execution contracts; synthetic artifacts, no network."""

import copy
import datetime as dt
import io
import json
import math
import re
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_execution import (
    NOW,
    candidate_api,
    candidate_proposal,
    fill,
    harness,
    saved,
    settings,
)
from test_execution_api import PublicClient, config
from test_execution_runner import Parameter, clients, control, handler

from prometheus import alert_contract as ac
from prometheus import market_blend as mb
from prometheus.execution import core, dashboard
from prometheus.execution.kalshi import Kalshi
from prometheus.execution.ledger import _item
from prometheus.other_games import ACCOUNT_KEYS, GAMES, account_key

FIXTURES = Path(__file__).with_name("fixtures")


@pytest.fixture
def game_artifacts(monkeypatch):
    monkeypatch.setattr(mb, "GAME_PATH", FIXTURES / "game_blends")
    monkeypatch.setattr(mb, "_INSTALLED", {})
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


@pytest.mark.parametrize("game", ["cs2", "valorant", "dota2"])
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
        core.validate_alert(
            p,
            core.Config.parse(
                settings(games={game: {"enabled": True, "starting_bankroll_usd": "50"}})
            ),
            NOW,
        )
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
    control.configure(
        parameter,
        "/config",
        {
            "games": {
                "cs2": {"enabled": True, "starting_bankroll_usd": "50"},
                "valorant": {"enabled": False},
            }
        },
    )
    assert parameter.value == settings(
        mode="off",
        games={
            "cs2": {"enabled": True, "starting_bankroll_usd": "50"},
            "valorant": {"enabled": False},
        },
    )
    parameter.value["mode"] = "live"
    with pytest.raises(ValueError, match="off"):
        control.configure(
            parameter,
            "/config",
            {"games": {"valorant": {"enabled": True, "starting_bankroll_usd": "50"}}},
        )


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
    _, api, ledger, execute = harness(
        settings(games={"cs2": {"enabled": enabled, "starting_bankroll_usd": "50"}})
    )
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


@pytest.mark.parametrize(
    "game,word",
    [
        ("cs2", "CS2"),
        ("cs2", "League of Legends"),
        ("dota2", "Dota 2"),
        ("dota2", "CS2"),
    ],
)
def test_cs2_rule_resolution(game, word):
    series = GAMES[game].series_ticker
    api = PublicClient()
    api.event.update(event_ticker=f"{series}-F", series_ticker=series)
    books = {}
    for market, team in zip(api.event["markets"], ["GamerLegion", "HOTU"], strict=True):
        book = api.books[market["ticker"]]
        book["no_dollars"] = [[".4", "2"]]
        books[f"{series}-F-{team}"] = book
        market.update(
            ticker=f"{series}-F-{team}",
            event_ticker=f"{series}-F",
            yes_sub_title=team,
            rules_primary=f"If {team} wins the Tesla Cup 2026: GamerLegion vs. HOTU {word} match originally scheduled for Oct 29, 2026 at 2:00 PM EDT",
        )
    api.books = books
    original = api.request

    def request(method, path, body=None, **query):
        if path == f"/series/{series}":
            return {"series": api.series}
        return original(method, path, body, **query)

    api.request = request
    proposal = {
        "game": game,
        "event_ticker": f"{series}-F",
        "start": "2026-10-29T18:00Z",
        "teams": ["GamerLegion", "HOTU"],
        "backed_team": "HOTU",
    }
    if word == GAMES[game].rules_word:
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
    assert len(quotes["E"]) == 4


@pytest.mark.parametrize(
    "mode,games,keys",
    [
        ("off", {"cs2": {"enabled": True, "starting_bankroll_usd": "50"}}, "cs2.json"),
        ("demo", {}, "cs2.json"),
        (
            "demo",
            {"dota2": {"enabled": True, "starting_bankroll_usd": "50"}},
            "dota2-model/feed/candidates.json",
        ),
        ("demo", {"dota2": {"enabled": False}}, "dota2-model/feed/candidates.json"),
        ("demo", {"cs2": {"enabled": False}}, "cs2.json"),
        ("demo", {"cs2": {"enabled": True, "starting_bankroll_usd": "50"}}, ""),
        (
            "demo",
            {"cs2": {"enabled": True, "starting_bankroll_usd": "50"}},
            " cs2.json, valorant.json, ",
        ),
        (
            "demo",
            {"valorant": {"enabled": True, "starting_bankroll_usd": "50"}},
            "cs2.json,valorant.json",
        ),
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
    if mode != "off" and any(g["enabled"] for g in games.values()):
        expected += [k.strip() for k in keys.split(",") if k.strip()]
    assert adapted == expected
    assert reads == [{"Bucket": "private-backup", "Key": k} for k in expected]
    assert reconciled == [{"source": k} for k in expected]


@pytest.mark.parametrize(
    "error", ["NoSuchKey", "404", "AccessDenied", "bad-json", "transport"]
)
def test_handler_game_source_errors_still_reconcile(monkeypatch, error):
    aws, _ = clients(
        monkeypatch,
        settings(games={"cs2": {"enabled": True, "starting_bankroll_usd": "50"}}),
    )
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


@pytest.mark.parametrize("bankroll", [None, "0", "-1", "NaN", "Infinity", "bad", True])
def test_enabled_game_requires_positive_bankroll(bankroll):
    game = {"enabled": True}
    if bankroll is not None:
        game["starting_bankroll_usd"] = bankroll
    with pytest.raises(ValueError, match="games"):
        core.Config.parse(settings(games={"cs2": game}))
    assert core.Config.parse(settings(mode="off", games={"cs2": game})).mode == "off"
    assert core.Config.parse(settings(games={"cs2": {"enabled": False}}))


@pytest.mark.parametrize("game", [{}, {"enabled": 1}, {"enabled": False, "typo": 1}])
def test_game_config_rejects_missing_enabled_and_unknown_fields(game):
    with pytest.raises(ValueError, match="games"):
        core.Config.parse(settings(games={"cs2": game}))


def game_settings(game="cs2", **changes):
    return settings(
        games={game: {"enabled": True, "starting_bankroll_usd": "50"}},
        order_budget_usd="1000",
        fixture_budget_usd="1000",
        daily_budget_usd="1000",
        max_exposure_usd="1000",
        max_contracts=1000,
        **changes,
    )


@pytest.mark.parametrize("game", ["cs2", "dota2"])
def test_game_losses_stop_at_own_bankroll_and_leave_league_untouched(game):
    client, api, ledger, execute = harness(
        game_settings(game, starting_bankroll_usd="10000")
    )
    league = {
        "pk": "ENV#demo",
        "sk": "ACCOUNT",
        "held": Decimal(7),
        "realized": Decimal(12),
    }
    client.put_item(Item=_item(league))
    untouched = {"ACCOUNT": league}
    for key in ACCOUNT_KEYS[1:]:
        if key != account_key(game):
            untouched[key] = {**league, "sk": key}
            client.put_item(Item=_item(untouched[key]))
    api.cash = "1000"
    api.routes[0]["quantity"] = "1000"
    losses = Decimal(0)
    for index in range(100):
        proposal = saved(
            game=game,
            group=f"{game}-series",
            probability=".99",
            fixture_id=f"{game}-{index}",
            event_ticker=f"{GAMES[game].series_ticker}-{index}",
        )
        result = execute([proposal])
        assert result["errors"] == 0
        if not result["submitted"]:
            break
        row = ledger.pending()[0]
        assert row["account"] == account_key(game)
        account = ledger.get("demo", account_key(game))
        assert account["held"] <= 50 + account.get("realized", 0)
        count = row["request"]["count"]
        fees = Decimal(row["held"]) - Decimal(".60") * Decimal(count)
        api.orders = [api.orders[-1]]
        fill(api, count=count, price=".60", fee=str(fees))
        # First reconcile actual fills, then verify a losing settlement.
        api.settlement_rows = []
        assert execute([])["reconciled"] == 1
        assert ledger.get("demo", account_key(game))["held"] <= 50 - losses
        api.settlement_rows = [
            {
                "ticker": row["request"]["ticker"],
                "yes_count_fp": count,
                "market_result": "no",
                "revenue": 0,
            }
        ]
        assert execute([])["reconciled"] == 1
        losses += Decimal(row["held"])
        account = ledger.get("demo", account_key(game))
        assert account["held"] == 0
        assert account["realized"] == -losses >= -50
        assert {key: ledger.get("demo", key) for key in untouched} == untouched
    else:
        pytest.fail("Losing game must stop placing orders")
    assert index > 1 and losses > 49
    assert {key: ledger.get("demo", key) for key in untouched} == untouched
    cfg = core.Config.parse(game_settings(game))
    with pytest.raises(ValueError, match="exhausted"):
        core.plan_order(
            proposal, api.routes, cfg, Decimal(1000), NOW, {"realized": -50}
        )


def test_game_reserve_checks_cap_and_both_account_snapshots():
    client, api, ledger, _ = harness(game_settings())
    cfg = core.Config.parse(game_settings())
    proposal = saved(game="cs2", group="cs2-series")
    plan = core.plan_order(proposal, api.routes, cfg, Decimal(100), NOW)
    assert ledger.reserve(plan, cfg, Decimal(100))
    other = copy.deepcopy(plan)
    other["alert"].update(fixture_id="other", event_ticker="other")
    assert ledger.reserve(other, cfg, Decimal(100)) is None
    account = ledger.get("demo", "ACCOUNT#cs2")
    other["sizing"].update(held_before=str(account["held"]), realized_before="1")
    assert ledger.reserve(other, cfg, Decimal(100)) is None
    # A matching held snapshot still cannot reserve more than seed plus realized.
    account = ledger.get("demo", "ACCOUNT#cs2")
    account["realized"] = Decimal(-49)
    client.put_item(Item=_item(account))
    other["sizing"].update(held_before=str(account["held"]), realized_before="-49")
    assert ledger.reserve(other, cfg, Decimal(100)) is None
    assert ledger.get("demo", "ACCOUNT") is None


@pytest.mark.parametrize("game", ["lol", "cs2"])
def test_total_held_balance_and_exposure_guard(game):
    _, api, _, _ = harness()
    cfg = core.Config.parse(game_settings())
    proposal = saved(
        game=game, group="cs2-series" if game == "cs2" else "minor-domestic"
    )
    for account, balance, exposure in [
        ({"held": 0, "total_held": 95}, 100, 0),
        ({"held": 0, "total_held": 990}, 2000, 10),
    ]:
        with pytest.raises(ValueError, match="exhausted"):
            core.plan_order(
                proposal,
                api.routes,
                cfg,
                Decimal(balance),
                NOW,
                account,
                exposure=exposure,
            )


def refit():
    data = copy.deepcopy(mb.load("cs2"))
    data["snapshots"].append(
        {
            **data["snapshots"][-1],
            "available_from": "2026-11-01T00:00:00+00:00",
            "trained_through": "2026-10-31T00:00:00+00:00",
            "market_slope": 1.2,
            "gap_slope": 0.4,
            "training_series": 400,
        }
    )
    return data


def test_append_only_blend_install_updates_all_readers(game_artifacts):
    league = copy.deepcopy(mb.load())
    old = copy.deepcopy(mb.load("cs2"))
    data = refit()
    assert mb.install("cs2", json.dumps(data).encode())
    assert mb.load("cs2") == data
    assert mb.snapshot(NOW, "cs2") == old["snapshots"][-1]
    estimate = mb.estimate(0.8, 0.6, "2026-11-02", "cs2")
    assert estimate["model"] == data["snapshots"][-1]["available_from"]
    assert mb.refresh(estimate, 0.6) == estimate["probability"]
    data["snapshots"][-1]["market_slope"] = 99
    assert mb.load("cs2")["snapshots"][-1]["market_slope"] == 1.2
    assert not mb.install("lol", league)
    assert mb.load() == league


@pytest.mark.parametrize(
    "mutation",
    [
        "old",
        "removed",
        "earlier",
        "clip",
        "game",
        "version",
        "series_ticker",
        "invalid",
        "market_low",
        "market_high",
        "gap_low",
        "gap_high",
        "too_few",
        "noncausal",
        "nan",
    ],
)
def test_blend_install_rejection_retains_last_good(game_artifacts, mutation):
    base = refit()
    added = base["snapshots"].pop()
    assert mb.install("cs2", base)
    good = copy.deepcopy(mb.load("cs2"))
    data = refit()
    if mutation == "old":
        data["snapshots"][0]["gap_slope"] += 0.01
    elif mutation == "removed":
        data["snapshots"].pop(0)
    elif mutation == "earlier":
        data["snapshots"].reverse()
    elif mutation in {"clip", "game", "version", "series_ticker"}:
        data[mutation] = 0.02 if mutation == "clip" else "wrong"
    elif mutation == "invalid":
        data = b"invalid json"
    else:
        key, value = {
            "market_low": ("market_slope", 0.199),
            "market_high": ("market_slope", 3.01),
            "gap_low": ("gap_slope", -1.01),
            "gap_high": ("gap_slope", 2.01),
            "too_few": ("training_series", 299),
            "nan": ("market_slope", float("nan")),
            "noncausal": ("trained_through", "2026-12-01T00:00:00+00:00"),
        }[mutation]
        data["snapshots"][-1][key] = value
    if mutation in {"old", "removed"}:
        # Months already in force are kept as loaded; only the new month is added.
        assert mb.install("cs2", data)
        assert mb.load("cs2")["snapshots"] == [*good["snapshots"], added]
        return
    assert not mb.install("cs2", data)
    assert mb.load("cs2") == good


@pytest.mark.parametrize("response", ["valid", "invalid", "NoSuchKey", "404"])
def test_handler_hourly_game_refits_and_missing_objects(
    game_artifacts, monkeypatch, response
):
    aws, _ = clients(monkeypatch, game_settings())
    monkeypatch.setenv(
        "GAME_BLEND_KEYS",
        "cs2:cs2-model/feed/blend_artifact.json,valorant:valorant-model/feed/blend_artifact.json",
    )
    monkeypatch.setattr(handler, "_BLEND_CHECKED", {})
    clock = [100.0]
    monkeypatch.setattr(handler.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(core, "run", lambda *a, **kw: {"errors": 0})
    reads = []
    data = refit()

    class Missing(Exception):
        def __init__(self):
            self.response = {"Error": {"Code": response}}

    def read(**kw):
        if kw["Key"] == "private-log.json":
            return {"Body": io.BytesIO(b'{"matches": []}')}
        reads.append(kw["Key"])
        if response in {"NoSuchKey", "404"}:
            raise Missing()
        return {
            "Body": io.BytesIO(
                json.dumps(data).encode() if response == "valid" else b"invalid"
            )
        }

    aws["s3"] = SimpleNamespace(get_object=read)
    for offset, expected in [(0, 1), (3599, 1), (3600, 2)]:
        clock[0] = 100 + offset
        result = handler.handler({}, None, clients=aws)
        assert len(reads) == expected
        assert result.get("blend_rejected", 0) == int(
            response == "invalid" and offset != 3599
        )
    if response == "valid":
        assert mb.load("cs2") == data


@pytest.mark.parametrize("game", ["lol", "cs2"])
@pytest.mark.parametrize("held_game", ["valorant", "dota2"])
def test_runner_counts_other_games_held_even_when_disabled(game, held_game):
    client, api, ledger, execute = harness(game_settings())
    client.put_item(
        Item=_item(
            {
                "pk": "ENV#demo",
                "sk": account_key(held_game),
                "held": Decimal(95),
            }
        )
    )
    result = execute(
        [saved(game=game, group="cs2-series" if game == "cs2" else "minor-domestic")]
    )
    assert result["submitted"] == 0 and result["skipped"] == 1
    assert result["errors"] == 0
    assert api.calls == [] and ledger.pending() == []


def test_other_game_registry():
    assert {slug: game.series_ticker for slug, game in GAMES.items()} == {
        "cs2": "KXCS2GAME",
        "valorant": "KXVALORANTGAME",
        "dota2": "KXDOTA2GAME",
    }
    assert ACCOUNT_KEYS == (
        "ACCOUNT",
        "ACCOUNT#cs2",
        "ACCOUNT#valorant",
        "ACCOUNT#dota2",
    )
    root = Path(__file__).resolve().parents[1]
    shell = (root / "scripts/game_feeds.sh").read_text()
    entries = re.search(r"^GAMES=\(([^)]+)\)", shell, re.M)[1].split()
    assert dict(entry.split(":") for entry in entries) == {
        slug: game.repo for slug, game in GAMES.items()
    }
    assert {slug: dashboard.MARKETS[slug] for slug in GAMES} == {
        "cs2": ("CS2", "🟥", "#dc2626"),
        "valorant": ("Valorant", "🟩", "#16a34a"),
        "dota2": ("Dota 2", "🟧", "#ea580c"),
    }
    for slug, game in GAMES.items():
        assert game.slug == slug and game.trade_groups <= game.groups
        assert game.groups <= ac.GROUPS and game.trade_groups <= ac.TRADE_GROUPS
    assert "valorant-international" not in ac.TRADE_GROUPS
    assert core.Config.parse(settings()).raw.get("games", {}) == {}


def test_dota_packaged_blend_and_missing_file(monkeypatch, tmp_path):
    assert mb.load("dota2")["series_ticker"] == "KXDOTA2GAME"
    monkeypatch.setattr(mb, "GAME_PATH", tmp_path)
    mb.load.cache_clear()
    try:
        assert mb.snapshot(NOW, "dota2") is None
    finally:
        mb.load.cache_clear()


def test_dota_blend_env_refit(game_artifacts, monkeypatch):
    aws, _ = clients(monkeypatch, game_settings("dota2"))
    monkeypatch.setenv("GAME_BLEND_KEYS", "dota2:dota2-model/feed/blend_artifact.json")
    monkeypatch.setattr(handler, "_BLEND_CHECKED", {})
    data = copy.deepcopy(mb.load("dota2"))
    reads = []

    def read(**kw):
        reads.append(kw["Key"])
        return {"Body": io.BytesIO(json.dumps(data).encode())}

    aws["s3"] = SimpleNamespace(get_object=read)
    assert handler.refresh_blends(aws, {"dota2": {"enabled": False}}) == 0
    assert reads == []
    assert handler.refresh_blends(aws, {"dota2": {"enabled": True}}) == 0
    assert reads == ["dota2-model/feed/blend_artifact.json"]
    assert mb.load("dota2") == data
