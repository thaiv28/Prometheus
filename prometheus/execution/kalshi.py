"""Small V2 REST client. Official docs checked 2026-10-15.

https://docs.kalshi.com/api-reference/orders/create-order-v2
https://docs.kalshi.com/api-reference/market/get-market-orderbook
https://docs.kalshi.com/getting_started/api_keys

Only fixed allowlisted hosts are used. No automatic POST retry or redirects.
Credentials, HTTP bodies and account data are never logged.
"""

import base64
import datetime as dt
import email.utils
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from zoneinfo import ZoneInfo

from prometheus.alert_contract import fold

from .core import decimal, fee_bound, timestamp

ROOTS = {
    "demo": "https://external-api.demo.kalshi.co",
    "live": "https://external-api.kalshi.com",
}
PATH = "/trade-api/v2"
MAP_RULES = re.compile(
    r"^If (?P<side>.+?) wins game (?P<map>\d+) in the (?P<event>.+): (?P<team1>.+?) vs\.? (?P<team2>.+?) "
    r"League of Legends match originally scheduled for (?P<day>\w{3} \d{1,2}, \d{4})"
    r" at (?P<time>\d{1,2}:\d{2} [AP]M) E[DS]T"
)
RULES = re.compile(
    r"^If (?P<side>.+?) wins the (?P<event>.+): (?P<team1>.+?) vs\.? (?P<team2>.+?) "
    r"League of Legends match originally scheduled for (?P<day>\w{3} \d{1,2}, \d{4})"
    r" at (?P<time>\d{1,2}:\d{2} [AP]M) E[DS]T"
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("exchange_redirect_refused")


class Kalshi:
    def __init__(self, environment, key_id, private_key_pem, canonical_aliases=None):
        if environment not in ROOTS:
            raise ValueError("invalid_environment")
        # Lazy optional dependency: the normal site never imports cryptography.
        from cryptography.hazmat.primitives import serialization

        self.environment = environment
        self.key_id = key_id
        self.key = serialization.load_pem_private_key(
            private_key_pem.encode(), password=None
        )
        self.aliases = canonical_aliases or {}
        self.opener = urllib.request.build_opener(NoRedirect())

    @staticmethod
    def now():
        return dt.datetime.now(dt.UTC)

    def headers(self, method, path):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa

        stamp = str(int(time.time() * 1000))
        message = (stamp + method + PATH + path.split("?")[0]).encode()
        if isinstance(self.key, ed25519.Ed25519PrivateKey):
            signature = self.key.sign(message)
        elif isinstance(self.key, rsa.RSAPrivateKey):
            signature = self.key.sign(
                message,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
                hashes.SHA256(),
            )
        else:
            raise ValueError("unsupported_key_type")
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-TIMESTAMP": stamp,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
            "Content-Type": "application/json",
            "Cache-Control": "no-cache, no-store",
        }

    def request(self, method, path, body=None, **query):
        url = ROOTS[self.environment] + PATH + path
        if query:
            url += "?" + urllib.parse.urlencode(
                {k: v for k, v in query.items() if v is not None}
            )
        request = urllib.request.Request(
            url,
            method=method,
            headers=self.headers(method, path),
            data=None if body is None else json.dumps(body).encode(),
        )
        try:
            with self.opener.open(request, timeout=10) as response:
                # Books cannot come from a stale intermediary cache. Server Date
                # is second-granularity; tolerate 5 s skew, require fresh receipt.
                date = response.headers.get("Date")
                server_time = email.utils.parsedate_to_datetime(date) if date else None
                age = decimal(response.headers.get("Age", "0"))
                result = json.load(response)
                result["_received_at"] = self.now().isoformat()
                result["_server_time"] = (
                    server_time.isoformat() if server_time else None
                )
                result["_cache_age"] = str(age)
                return result
        except urllib.error.HTTPError as error:
            # Never expose returned HTTP bodies, account identifiers or headers.
            if error.code == 404:
                raise LookupError("exchange_not_found") from None
            raise RuntimeError(f"exchange_http_{error.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise RuntimeError("exchange_transport_uncertain") from None

    def pages(self, path, field, **query):
        rows, cursor, seen = [], None, set()
        for _ in range(100):
            page = self.request("GET", path, limit=100, cursor=cursor, **query)
            rows.extend(page[field])
            cursor = page.get("cursor")
            if not cursor:
                return rows
            if cursor in seen:
                raise ValueError("repeated_pagination_cursor")
            seen.add(cursor)
        raise ValueError("pagination_limit_exceeded")

    def canonical(self, name, teams):
        # An explicit alias, else the one fixture team whose folded name (case,
        # accents, punctuation) is identical: "Dplus KIA" -> "Dplus Kia", "LOS"
        # -> "LØS". No substring or similarity matching.
        name = self.aliases.get(name.strip(), name.strip())
        matches = [team for team in teams if fold(team) == fold(name)]
        return matches[0] if len(matches) == 1 else name

    def resolve(self, alert, now, config):
        from prometheus import live_map

        is_map = alert.get("kind") == live_map.VERSION
        series_ticker = "KXLOLMAP" if is_map else "KXLOLGAME"
        ticker = urllib.parse.quote(alert["event_ticker"], safe="")
        response = self.request("GET", f"/events/{ticker}", with_nested_markets="true")
        event = response["event"]
        if (
            event["event_ticker"] != alert["event_ticker"]
            or event["series_ticker"] != series_ticker
            or event.get("mutually_exclusive") is not True
        ):
            raise ValueError("wrong_or_nonexclusive_event")
        series = self.request("GET", f"/series/{series_ticker}")["series"]
        # Ordinary event responses need not expose current fee overrides. Read
        # their authoritative history, including explicit null/null clears.
        changes = self.pages(
            "/events/fee_changes",
            "event_fee_changes",
            event_ticker=alert["event_ticker"],
        )
        if any(c.get("event_ticker") != alert["event_ticker"] for c in changes):
            raise ValueError("fee_event_mismatch")
        applicable = [c for c in changes if timestamp(c["scheduled_ts"]) <= now]
        effective = (
            max(applicable, key=lambda c: timestamp(c["scheduled_ts"]))
            if applicable
            else event
        )
        future_overrides = [
            c
            for c in changes
            if now < timestamp(c["scheduled_ts"]) <= timestamp(alert["start"])
        ]
        series_changes = self.request(
            "GET", "/series/fee_changes", series_ticker=series_ticker
        )["series_fee_change_arr"]
        if any(c.get("series_ticker") != series_ticker for c in series_changes):
            raise ValueError("fee_series_mismatch")
        future_series = [
            c
            for c in series_changes
            if now < timestamp(c["scheduled_ts"]) <= timestamp(alert["start"])
        ]
        # Conservatively cover every announced combination through fixture start.
        # IOC execution occurs now; bounding future changes avoids a clock/race at
        # a scheduled fee boundary without a second authenticated quote phase.
        for profile in [series, *future_series]:
            for override in [effective, *future_overrides]:
                fee_type = override.get("fee_type_override") or profile["fee_type"]
                multiplier = override.get("fee_multiplier_override")
                multiplier = decimal(
                    profile["fee_multiplier"] if multiplier is None else multiplier
                )
                if (
                    fee_type not in {"quadratic", "quadratic_with_maker_fees"}
                    or multiplier < 0
                ):
                    raise ValueError("unsupported_fee_schedule")
                if Decimal(".07") * multiplier > config.number("fee_rate_upper_bound"):
                    raise ValueError("fee_bound_exceeded")
        markets = event.get("markets") or response.get("markets") or []
        if len(markets) != 2:
            raise ValueError("ambiguous_outcomes")
        parsed = []
        for market in markets:
            rules = (MAP_RULES if is_map else RULES).match(
                market.get("rules_primary", "")
            )
            if (
                not rules
                or (is_map and int(rules["map"]) != alert["map_number"])
                or market.get("market_type") != "binary"
                or market.get("event_ticker") != alert["event_ticker"]
                or decimal(market.get("notional_value_dollars", "0")) != 1
            ):
                raise ValueError("unsupported_or_ambiguous_market")
            teams = {
                self.canonical(rules[name], alert["teams"])
                for name in ("team1", "team2")
            }
            side = self.canonical(rules["side"], alert["teams"])
            when = dt.datetime.strptime(
                f"{rules['day']} {rules['time']}", "%b %d, %Y %I:%M %p"
            ).replace(tzinfo=ZoneInfo("America/New_York"))
            if teams != set(alert["teams"]) or side not in teams:
                raise ValueError("fixture_team_mismatch")
            # Exact timed fixture match; reschedules with changed rules fail safe.
            if when.astimezone(dt.UTC) != timestamp(alert["start"]):
                raise ValueError("fixture_start_mismatch")
            if self.canonical(market.get("yes_sub_title", ""), alert["teams"]) != side:
                raise ValueError("outcome_label_mismatch")
            parsed.append((market, side))
        if {side for _, side in parsed} != set(alert["teams"]):
            raise ValueError("duplicate_or_missing_outcome")
        if is_map:
            parent = self.request(
                "GET",
                f"/events/{urllib.parse.quote(alert['series_id'], safe='')}",
                with_nested_markets="true",
            )["event"]
            parents = parent.get("markets") or []
            if (
                parent.get("event_ticker") != alert["series_id"]
                or parent.get("series_ticker") != "KXLOLGAME"
                or len(parents) != 2
            ):
                raise ValueError("live_series_identity_mismatch")
            parent_sides = set()
            for item in parents:
                rule = RULES.match(item.get("rules_primary", ""))
                if not rule or {
                    self.canonical(rule[n], alert["teams"]) for n in ("team1", "team2")
                } != set(alert["teams"]):
                    raise ValueError("live_series_identity_mismatch")
                when = dt.datetime.strptime(
                    f"{rule['day']} {rule['time']}", "%b %d, %Y %I:%M %p"
                ).replace(tzinfo=ZoneInfo("America/New_York"))
                if when.astimezone(dt.UTC) != timestamp(alert["start"]):
                    raise ValueError("live_series_identity_mismatch")
                parent_sides.add(self.canonical(rule["side"], alert["teams"]))
            if parent_sides != set(alert["teams"]):
                raise ValueError("live_series_identity_mismatch")
        self._fixture_tickers = {market["ticker"] for market, _ in parsed}
        routes = []
        mids, quote_times = [], []
        live_book = None
        for market, team in parsed:
            if (
                market.get("status") != "active"
                or timestamp(market["close_time"]) <= now
            ):
                continue
            name = urllib.parse.quote(market["ticker"], safe="")
            book = self.request("GET", f"/markets/{name}/orderbook", depth=0)
            received = timestamp(book["_received_at"])
            server = book.get("_server_time")
            age_limit = config.number("max_quote_age_seconds")
            if (
                server is None
                or not -5 <= (received - timestamp(server)).total_seconds() <= age_limit
                or decimal(book["_cache_age"]) > 0
            ):
                raise ValueError("stale_or_undated_orderbook")
            own = team == alert["backed_team"]
            if is_map and team == alert["teams"][0]:
                levels = book.get("orderbook_fp") or {}
                bids = [
                    decimal(p)
                    for p, q in levels.get("yes_dollars", [])
                    if decimal(q) > 0
                ]
                offers = [
                    decimal(p)
                    for p, q in levels.get("no_dollars", [])
                    if decimal(q) > 0
                ]
                if bids and offers:
                    live_book = {
                        "at": received.isoformat(),
                        "bid": str(max(bids)),
                        "ask": str(1 - max(offers)),
                    }
            if alert.get("trading"):
                bids = []
                for field in ("yes_dollars", "no_dollars"):
                    valid_bids = [
                        decimal(p)
                        for p, q in book["orderbook_fp"].get(field, [])
                        if 0 < decimal(p) < 1 and decimal(q) > 0
                    ]
                    bids.append(max(valid_bids) if valid_bids else None)
                yes, no = bids
                if (
                    yes is not None
                    and no is not None
                    and 0 <= 1 - no - yes <= Decimal(".10")
                ):
                    mid = (yes + 1 - no) / 2
                    mids.append(mid if own else 1 - mid)
                    quote_times.append(received)
            levels = book["orderbook_fp"]["no_dollars" if own else "yes_dollars"]
            valid = [
                (decimal(p), decimal(q))
                for p, q in levels
                if 0 < decimal(p) < 1 and decimal(q) > 0
            ]
            if not valid:
                continue
            best = max(p for p, _ in valid)
            quantity = sum(q for p, q in valid if p == best)
            price = 1 - best
            limit = price if own else best
            ranges = market.get("price_ranges") or []
            if not any(
                decimal(b["step"]) > 0
                and decimal(b["start"]) <= limit <= decimal(b["end"])
                and (limit - decimal(b["start"])) % decimal(b["step"]) == 0
                for b in ranges
            ):
                raise ValueError("invalid_or_missing_price_grid")
            if limit != limit.quantize(Decimal(".0001")):
                raise ValueError("unsupported_price_precision")
            routes.append(
                {
                    "ticker": market["ticker"],
                    "outcome_team": team,
                    "side": "bid" if own else "ask",
                    "price": str(price),
                    "limit": f"{price if own else best:.4f}",
                    "quantity": str(quantity),
                    "at": received.isoformat(),
                }
            )
        if alert.get("trading"):
            if not mids:
                raise ValueError("no_two_sided_blend_quote")
            for route in routes:
                route["market_mid"] = str(sum(mids) / len(mids))
                route["at"] = min(timestamp(route["at"]), *quote_times).isoformat()
        if is_map:
            if live_book is None:
                raise ValueError("missing_live_two_sided_book")
            trades = []
            tickers = {m["ticker"]: alert["teams"].index(team) for m, team in parsed}
            for name in tickers:
                page = self.request(
                    "GET",
                    "/markets/trades",
                    ticker=name,
                    min_ts=int(now.timestamp()) - 31,
                    limit=1000,
                )
                if (
                    page.get("cursor")
                    or page.get("_cache_age") is None
                    or decimal(page["_cache_age"]) != 0
                    or page.get("_server_time") is None
                    or not 0
                    <= (self.now() - timestamp(page["_server_time"])).total_seconds()
                    <= 3
                ):
                    raise ValueError("incomplete_live_trade_window")
                trades.extend(page["trades"])
            checked = self.now()
            decision = live_map.evaluate(
                alert["live"]["observation"],
                live_map.normalize_trades(trades, tickers),
                live_book,
                checked.isoformat(),
                lambda price: fee_bound(
                    decimal(price),
                    1,
                    config.number("fee_rate_upper_bound"),
                    config.number("balance_precision_usd"),
                ),
            )
            if alert["teams"][decision["side"]] != alert["backed_team"]:
                raise ValueError("live_signal_side_changed")
            for route in routes:
                route.update(
                    live_probability=str(decision["probability"]),
                    live_checked_at=checked.isoformat(),
                )
        return routes

    def balance(self):
        result = self.request("GET", "/portfolio/balance", subaccount=0)
        value = decimal(result["balance_dollars"])
        if value < 0:
            raise ValueError("invalid_balance")
        return value

    def exposure(self):
        """Whole primary-account exposure, including unrelated positions/orders.

        Our own filled exposure is counted again by the ledger until settlement;
        this intentionally errs toward smaller spending. No accountwide cancel.
        """
        positions = self.pages("/portfolio/positions", "market_positions", subaccount=0)
        fixture_tickers = getattr(self, "_fixture_tickers", set())
        if any(
            p["ticker"] in fixture_tickers
            and decimal(p["market_exposure_dollars"]) != 0
            for p in positions
        ):
            raise ValueError("existing_fixture_exposure")
        exposure = sum(
            (abs(decimal(p["market_exposure_dollars"])) for p in positions), Decimal(0)
        )
        resting = self.pages(
            "/portfolio/orders", "orders", status="resting", subaccount=0
        )
        for order in resting:
            if (
                order["ticker"] in fixture_tickers
                and decimal(order["remaining_count_fp"]) > 0
            ):
                raise ValueError("existing_fixture_order")
            side = order.get("book_side")
            if side not in {"bid", "ask"}:
                raise ValueError("unknown_resting_order_direction")
            price = decimal(
                order["yes_price_dollars"]
                if side == "bid"
                else order["no_price_dollars"]
            )
            count = decimal(order["remaining_count_fp"])
            if count < 0 or not 0 <= price <= 1:
                raise ValueError("invalid_resting_order")
            # Reserve full $1 payoff for each outstanding contract, bounding its
            # collateral and fees independent of an external order's fee scheme.
            exposure += count
        return exposure

    def place(self, request):
        return self.request("POST", "/portfolio/events/orders", request)

    def lookup(self, client_id, order_id=None):
        if order_id:
            try:
                return self.request(
                    "GET", f"/portfolio/orders/{urllib.parse.quote(order_id, safe='')}"
                )["order"]
            except LookupError:
                pass
        matches = []
        for path in ("/portfolio/orders", "/historical/orders"):
            for order in self.pages(path, "orders", subaccount=0):
                if order.get("client_order_id") == client_id:
                    matches.append(order)
            if matches:
                break
        if len(matches) > 1:
            raise ValueError("duplicate_exchange_client_ids")
        return matches[0] if matches else None

    def fills(self, order_id, expected=None):
        rows = self.pages("/portfolio/fills", "fills", order_id=order_id, subaccount=0)
        if (
            expected is None
            or sum((decimal(f["count_fp"]) for f in rows), Decimal(0)) != expected
        ):
            rows += self.pages(
                "/historical/fills", "fills", order_id=order_id, subaccount=0
            )
        by_id = {}
        for row in rows:
            old = by_id.setdefault(row["fill_id"], row)
            if old != row:
                raise ValueError("conflicting_fill_records")
        return list(by_id.values())

    def settlements(self, ticker):
        rows = self.pages(
            "/portfolio/settlements", "settlements", ticker=ticker, subaccount=0
        )
        valid = []
        for row in rows:
            if row["ticker"] != ticker or row.get("market_result") not in {
                "yes",
                "no",
                "scalar",
            }:
                continue
            if (
                not row.get("settled_time")
                or decimal(row["revenue"]) < 0
                or decimal(row["fee_cost"]) < 0
            ):
                raise ValueError("invalid_settlement")
            timestamp(row["settled_time"])
            if row["market_result"] == "scalar":
                name = urllib.parse.quote(ticker, safe="")
                try:
                    market = self.request("GET", f"/markets/{name}")["market"]
                except LookupError:
                    market = self.request("GET", f"/historical/markets/{name}")[
                        "market"
                    ]
                if (
                    market.get("ticker") != ticker
                    or market.get("status") != "finalized"
                    or market.get("result") != "scalar"
                    or not market.get("settlement_ts")
                ):
                    continue
                value = decimal(market["settlement_value_dollars"])
                if (
                    not 0 <= value <= 1
                    or timestamp(market["settlement_ts"]) > self.now()
                ):
                    raise ValueError("invalid_scalar_settlement")
                row = {**row, "finalized_market": market}
            valid.append(row)
        return valid

    def cancel(self, order_id, market_ticker=None):
        return self.request(
            "DELETE",
            f"/portfolio/events/orders/{urllib.parse.quote(order_id, safe='')}",
            market_ticker=market_ticker,
        )


class PublicKalshi(Kalshi):
    def __init__(self, canonical_aliases=None):
        self.environment, self.aliases = "live", canonical_aliases or {}
        self.opener = urllib.request.build_opener(NoRedirect())

    def headers(self, method, path):
        if method != "GET" or not path.startswith(
            ("/markets/", "/events/", "/series/")
        ):
            raise ValueError("shadow_private_request_refused")
        return {
            "Cache-Control": "no-cache, no-store",
            "User-Agent": "prometheus-live-shadow/1",
        }
