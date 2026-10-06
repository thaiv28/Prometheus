import datetime

import pytest

from prometheus import markets

UTC = datetime.timezone.utc


def _open(
    side,
    team1,
    team2,
    bid,
    ask,
    when="Oct 6, 2026 at 4:00 PM EDT",
    event="KXLOLGAME-E1",
    map_no=None,
):
    where = f"map {map_no} in the" if map_no else "the"
    return {
        "ticker": f"{event}-{side}",
        "event_ticker": event,
        "rules_primary": f"If {side} wins {where} LCK 2026: {team1} vs. {team2} League of Legends match originally scheduled for {when}, then the market resolves to Yes.",
        "result": "",
        "open_time": "2026-10-05T18:00:00Z",
        "close_time": "2026-10-06T23:00:00Z",
        "volume_fp": "10.00",
        "yes_bid_dollars": str(bid),
        "yes_ask_dollars": str(ask),
    }


def _entry(start="2026-10-06T20:00Z", ours1="Cupid", ours2="Fuego"):
    return {
        "match_id": "m",
        "start": start,
        "matched": True,
        "ours1": ours1,
        "ours2": ours2,
    }


NOW = datetime.datetime(2026, 10, 6, 3, 0, tzinfo=UTC)


def test_attach_prices_orients_to_the_logged_team_order():
    # Kalshi lists Fuego first; the log lists Cupid first.
    book = [
        _open("Fuego", "Fuego", "Cupid", 0.16, 0.17),
        _open("Cupid", "Fuego", "Cupid", 0.83, 0.84),
    ]
    log = {"m": _entry()}
    assert markets.attach_prices(log, book, lambda name: name, NOW) == 1
    m = log["m"]["market"]
    assert m["p"] == pytest.approx(0.835) and m["spread"] == pytest.approx(0.01)
    assert (m["ask1"], m["ask2"]) == pytest.approx((0.84, 0.17))
    assert (m["at"], m["ticker"]) == ("2026-10-06T03:00Z", "KXLOLGAME-E1")


def test_attach_prices_skips_thin_quotes_far_starts_maps_and_started_matches():
    thin = [_open("Cupid", "Cupid", "Fuego", 0.05, 0.95)]
    log = {"m": _entry()}
    assert (
        markets.attach_prices(log, thin, lambda n: n, NOW) == 0
        and "market" not in log["m"]
    )

    far = [
        _open("Cupid", "Cupid", "Fuego", 0.6, 0.62, when="Oct 9, 2026 at 4:00 PM EDT")
    ]
    assert markets.attach_prices(log, far, lambda n: n, NOW) == 0

    map_one = [
        _open("Cupid", "Cupid", "Fuego", 0.6, 0.62, map_no=1, event="KXLOLMAP-E1-1")
    ]
    assert markets.attach_prices(log, map_one, lambda n: n, NOW) == 0

    started = {"m": {**_entry(start="2026-10-06T02:00Z"), "market": {"p": 0.5}}}
    good = [_open("Cupid", "Cupid", "Fuego", 0.6, 0.62)]
    assert markets.attach_prices(started, good, lambda n: n, NOW) == 0
    assert started["m"]["market"] == {"p": 0.5}


def test_attach_prices_needs_both_teams_matched():
    book = [_open("Cupid", "Cupid", "Somebody", 0.6, 0.62)]
    log = {"m": _entry()}
    assert markets.attach_prices(log, book, {"Cupid": "Cupid"}.get, NOW) == 0


def test_open_markets_parse_without_a_result():
    m = markets.parse_market(_open("Cupid", "Cupid", "Fuego", 0.6, 0.62), settled=False)
    assert (m["bid"], m["ask"], m["timed"]) == (0.6, 0.62, True)
    assert (
        markets.parse_market(_open("Cupid", "Cupid", "Fuego", 0.6, 0.62)) is None
    )  # not settled


def test_backfill_prices_prices_started_unpriced_matches_once():
    book = markets.events(
        [
            _open("Fuego", "Fuego", "Cupid", 0.3, 0.32),
            _open("Cupid", "Fuego", "Cupid", 0.68, 0.7),
        ],
        settled=False,
    )
    calls = []

    def price_at(row, team1, start):
        calls.append((row["event_ticker"], team1, start))
        return 0.31 if team1 == "Fuego" else 0.69, 0.02, start - datetime.timedelta(hours=1)

    later = datetime.datetime(2026, 10, 7, 3, 0, tzinfo=UTC)
    log = {
        "m": _entry(),  # Cupid first: oriented to the log's team1
        "priced": {**_entry(), "match_id": "priced", "market": {"p": 0.5}},
        "future": {**_entry(start="2026-10-08T20:00Z"), "match_id": "future"},
    }
    assert markets.backfill_prices(log, book, lambda n: n, price_at, later) == 1
    assert calls == [("KXLOLGAME-E1", "Cupid", datetime.datetime(2026, 10, 6, 20, tzinfo=UTC))]
    assert log["m"]["market"] == {
        "p": 0.69,
        "spread": 0.02,
        "at": "2026-10-06T19:00Z",
        "ticker": "KXLOLGAME-E1",
        "backfilled": True,
    }
    assert log["priced"]["market"] == {"p": 0.5} and "market" not in log["future"]
    # A match with no quote before its start stays unpriced.
    log = {"m": _entry()}
    assert markets.backfill_prices(log, book, lambda n: n, lambda *a: None, later) == 0


def test_attach_prices_keeps_the_last_read_twelve_hours_out_for_paper_bets():
    book = [_open("Cupid", "Cupid", "Fuego", 0.6, 0.62)]
    log = {"m": {**_entry(), "p_series": 0.7}}  # starts 20:00
    markets.attach_prices(log, book, lambda n: n, NOW)  # 03:00, 17 hours out
    assert log["m"]["market_12h"] == {
        "p": pytest.approx(0.61), "ask1": 0.62, "ask2": pytest.approx(0.4),
        "at": "2026-10-06T03:00Z", "ours": 0.7,
    }
    late = [_open("Cupid", "Cupid", "Fuego", 0.7, 0.72)]
    markets.attach_prices(log, late, lambda n: n, NOW + datetime.timedelta(hours=10))  # 7 hours out
    assert log["m"]["market"]["p"] == pytest.approx(0.71)
    assert log["m"]["market_12h"]["at"] == "2026-10-06T03:00Z"  # kept


def test_backfill_prices_adds_the_twelve_hour_price_to_priced_matches():
    book = markets.events([_open("Cupid", "Cupid", "Fuego", 0.6, 0.62)], settled=False)
    later = datetime.datetime(2026, 10, 7, 3, 0, tzinfo=UTC)
    log = {"m": {**_entry(), "p_series": 0.7, "market": {"p": 0.6}}}

    def bet_at(row, team1, start):
        return 0.58, 0.6, 0.44, start - markets.BET_LEAD

    assert markets.backfill_prices(log, book, lambda n: n, lambda *a: pytest.fail("priced"), later, bet_at) == 1
    assert log["m"]["market"] == {"p": 0.6}
    assert log["m"]["market_12h"] == {
        "p": 0.58, "ask1": 0.6, "ask2": 0.44, "at": "2026-10-06T08:00Z", "ours": 0.7, "backfilled": True,
    }
