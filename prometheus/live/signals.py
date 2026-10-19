"""Opt-in live-map observer and private durable outbox, outside public pages.

AWS CLI uses the worker's role; no account reads or signing keys. One first
qualifying candidate per map, persisted before delivery; retries reuse its bytes.
"""

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlencode

from .. import live_map
from ..execution.core import fee_bound
from ..types import INTERNATIONAL_LEAGUES
from .kalshi import KALSHI, RULES, known, names
from .timeline import MODEL_PATH, timeline_calls


def rating_time(value):
    # OE/SQLite dates in live_inputs are timezone-free UTC by contract.
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def observation(game, page, at):
    if (
        not game.timeline
        or not game.start
        or not game.forge
        or page.get("status") != "live"
    ):
        raise ValueError("live_model_or_identity_unavailable")
    from .draft import available

    model, ratings = game.timeline
    if model != json.loads(live_map.MODEL.read_text()):
        raise ValueError("live_model_version_mismatch")
    packet = getattr(game, "draft_context", None)
    candidate = getattr(game, "draft_model", None)
    receipt = (
        page["game"]["frames"][-1]["actual_received_at"]
        if page["game"]["frames"]
        else at
    )
    use_draft = bool(
        candidate
        and available(packet, receipt, candidate)
        and available(packet, at, candidate)
    )
    if use_draft and candidate != json.loads(live_map.DRAFT_MODEL.read_text()):
        raise ValueError("live_draft_version_mismatch")
    _, calls = timeline_calls(
        page,
        candidate if use_draft else model,
        ratings,
        start=game.start["source_at"],
        draft=packet if use_draft else None,
        include_inputs=True,
    )
    frames = page["game"]["frames"]
    if (
        not calls
        or len(frames) < 2
        or calls[-1]["source_at"] != frames[-1]["source_at"]
    ):
        raise ValueError("live_latest_frame_not_modeled")
    frame = frames[-1]
    homes = game.forge["homes"]
    teams = [t["name"] for t in game.mapping["teams"]]
    draft_input = {}
    if use_draft:
        blue = page["game"]["blue"]
        packet = json.loads(json.dumps(packet))
        if packet.get("history_through"):
            packet["history_through"] = rating_time(packet["history_through"])
        draft_input = {
            "game_id": game.id,
            "draft": {
                "context": packet,
                "p_blue": game.forge["p_game"]
                if blue == 0
                else 1 - game.forge["p_game"],
                "model_sha256": hashlib.sha256(
                    live_map.DRAFT_MODEL.read_bytes()
                ).hexdigest(),
            },
        }
    return {
        **draft_input,
        "version": live_map.VERSION,
        "state": "live",
        "teams": teams,
        "blue": page["game"]["blue"],
        "inputs": calls[-1]["inputs"],
        "model_sha256": hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest(),
        # OE/SQLite dates in live_inputs are timezone-free UTC by contract.
        "rating_as_of": [rating_time(r["as_of"]) for r in ratings],
        "source_at": frame["source_at"],
        "received_at": frame["actual_received_at"],
        "calculated_at": at,
        "start": game.start_time,
        "flat": sum(t["gold"] for t in frame["teams"])
        == sum(t["gold"] for t in frames[-2]["teams"]),
        "team_homes": dict(zip(teams, homes)),
        "international": game.mapping["league"] in {*INTERNATIONAL_LEAGUES, "WLDs"}
        or homes[0] != homes[1],
        "map_number": game.number,
        "event_ticker": game.signal_event,
        "series_event_ticker": game.signal_series,
    }


class Outbox:
    def __init__(self, s3, sqs, bucket, queue):
        self.s3, self.sqs, self.bucket, self.queue = s3, sqs, bucket, queue

    def deliver(self, path, candidate):
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        key = live_map.PREFIX + digest + ".json"
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType="application/json",
                IfNoneMatch="*",
            )
        except Exception as error:
            if getattr(error, "response", {}).get("Error", {}).get("Code") not in {
                "PreconditionFailed",
                "412",
            }:
                raise
        self.sqs.send_message(
            QueueUrl=self.queue, MessageBody=json.dumps({"key": key, "sha256": digest})
        )


class Cli:
    """Role-authenticated CLI bridge; no signing keys or account data."""

    def __init__(self, root):
        self.root = root

    def put_object(self, **kw):
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "upload.json"
        path.write_bytes(kw["Body"])
        result = subprocess.run(
            [
                "aws",
                "s3api",
                "put-object",
                "--bucket",
                kw["Bucket"],
                "--key",
                kw["Key"],
                "--body",
                str(path),
                "--content-type",
                "application/json",
                "--if-none-match",
                "*",
            ],
            capture_output=True,
            timeout=4,
        )
        if result.returncode:
            if b"PreconditionFailed" in result.stderr or b"(412)" in result.stderr:
                return
            raise ValueError("live_signal_persistence_failed")

    def send_message(self, **kw):
        result = subprocess.run(
            [
                "aws",
                "sqs",
                "send-message",
                "--queue-url",
                kw["QueueUrl"],
                "--message-body",
                kw["MessageBody"],
            ],
            capture_output=True,
            timeout=4,
        )
        if result.returncode:
            raise ValueError("live_signal_delivery_failed")


class Signals:
    def __init__(self, fetch, outbox=None):
        self.fetch, self.outbox = fetch, outbox
        self.observations = {}

    @staticmethod
    def discover(game, markets):
        game.signal_event = game.signal_series = None
        game.signal_tickers = {}
        by_ticker = {m["ticker"]: m for m in markets}
        own, series = by_ticker.get(game.ticker), by_ticker.get(game.series_ticker)
        if not own or not series:
            return
        hits = [m for m in markets if m.get("event_ticker") == own["event_ticker"]]
        if len(hits) != 2:
            return
        teams = game.mapping["teams"]
        for m in hits:
            rule = RULES.match(m.get("rules_primary", ""))
            if not rule or int(rule["map"] or 0) != game.number:
                return
            sides = [
                i for i, team in enumerate(teams) if known(rule["side"], names(team))
            ]
            if len(sides) != 1:
                return
            game.signal_tickers[m["ticker"]] = sides[0]
        if sorted(game.signal_tickers.values()) != [0, 1]:
            return
        game.signal_event, game.signal_series = (
            own["event_ticker"],
            series["event_ticker"],
        )

    def poll(self, game, page, fresh_model=False):
        directory = game.dir / "trading"
        directory.mkdir(exist_ok=True)
        path, delivered = directory / "candidate.json", directory / "delivered"
        now = datetime.now(UTC).isoformat()
        if path.exists():
            candidate = json.loads(path.read_text())
            if (
                self.outbox
                and not delivered.exists()
                and live_map.timestamp(now)
                <= live_map.timestamp(candidate["expires_at"])
            ):
                self.outbox.deliver(path, candidate)
                delivered.write_text(now)
            return
        if not getattr(game, "signal_event", None):
            return
        try:
            if fresh_model:
                self.observations[game.id] = observation(game, page, now)
            current = self.observations.get(game.id)
            if not current:
                return
            if game.latest_signal_book is None:
                raise ValueError("live_book_unavailable")
            live_map.validate_observation(current, now)
            trades = []
            for ticker in game.signal_tickers:
                query = urlencode(
                    {
                        "ticker": ticker,
                        "min_ts": int(live_map.timestamp(now).timestamp()) - 31,
                        "limit": 1000,
                    }
                )
                _, payload = self.fetch(
                    f"{KALSHI}/markets/trades?{query}", game.request_dir("trades")
                )
                if payload is None or payload.get("cursor"):
                    raise ValueError("incomplete_live_trade_window")
                trades.extend(payload.get("trades", []))
            tape = live_map.normalize_trades(trades, game.signal_tickers)
            checked = datetime.now(UTC).isoformat()
            candidate = live_map.proposal(
                current,
                tape,
                game.latest_signal_book,
                checked,
                lambda price: fee_bound(
                    Decimal(str(price)), 1, Decimal(".07"), Decimal(".0001")
                ),
            )
            if len(live_map.canonical(candidate)) > 128 * 1024:
                raise ValueError("oversize_live_signal")
            # x-mode is a local first-candidate fence; consumer has an atomic map fence.
            with path.open("xb") as file:
                file.write(live_map.canonical(candidate))
            reason = "candidate"
        except (ValueError, KeyError, TypeError, ArithmeticError) as error:
            reason = str(error)
        journal_key = (
            getattr(game, "id", None),
            reason,
            (self.observations.get(game.id) or {}).get("source_at"),
        )
        if getattr(game, "last_signal_note", None) != journal_key:
            with (directory / "decisions.jsonl").open("a") as file:
                file.write(
                    json.dumps(
                        {"at": now, "reason": reason, "source_at": journal_key[-1]}
                    )
                    + "\n"
                )
            game.last_signal_note = journal_key
        if path.exists() and self.outbox:
            # Deliver only after the durable local write; failures retry these bytes.
            candidate = json.loads(path.read_text())
            if live_map.timestamp(datetime.now(UTC).isoformat()) <= live_map.timestamp(
                candidate["expires_at"]
            ):
                self.outbox.deliver(path, candidate)
                delivered.write_text(now)
