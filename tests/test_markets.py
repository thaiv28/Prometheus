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
