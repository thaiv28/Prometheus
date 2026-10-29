"""Persisted local Riot collector with explicit recorded/simulated offline replay."""

import copy
import fcntl
import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import timedelta
from pathlib import Path

from .feed import WindowSession, timestamp

# Rejections a paused frame may carry and still mean "paused".
PAUSE_REASONS = {
    "source_not_in_game",
    "duplicate",
    "out_of_order",
    "stale_source_timestamp",
}
from .requests import utc_now

MODES = {"simulated_replay", "recorded_replay", "network_probe"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def window_dump(window):
    return {
        "seen": [[at.isoformat(), digest] for at, digest in window.seen.items()],
        "anchor": window.anchor.isoformat() if window.anchor else None,
        "finished": window.finished,
        "sequence": window.sequence,
    }


def window_load(selection, saved):
    window = WindowSession(
        selection["session"],
        selection["match_id"],
        selection["game_id"],
        selection["blue_id"],
        selection["red_id"],
        selection["max_age_seconds"],
    )
    if saved:
        window.seen = {timestamp(at): digest for at, digest in saved["seen"]}
        window.anchor = timestamp(saved["anchor"]) if saved["anchor"] else None
        window.finished = saved["finished"]
        window.sequence = saved["sequence"]
    return window


def read_probe(directory, record_index=0):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    if type(record_index) is not int or not 0 <= record_index < len(
        manifest["records"]
    ):
        raise ValueError("invalid probe record index")
    record = manifest["records"][record_index]
    if (
        record.get("http_status") != 200
        or record.get("error")
        or record.get("parse_error")
    ):
        raise ValueError(
            f"source_failure: HTTP {record.get('http_status')}; {record.get('error') or record.get('parse_error')}"
        )
    name = record["raw_file"]
    if Path(name).name != name:
        raise ValueError("raw response must be in the probe directory")
    path = directory / name
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError("raw_response_hash_mismatch")
    return (
        json.loads(raw),
        record["received_at_utc"],
        {
            "raw_path": str(path.resolve()),
            "response_sha256": record["sha256"],
            "url": record["url"],
        },
    )


class Collector:
    """Single writer, atomic journal/state commits and recoverable latest.json."""

    def __init__(self, out, mode):
        if mode not in MODES:
            raise ValueError("explicit collector mode required")
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.lock = (self.out / "writer.lock").open("a+")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.lock.close()
            raise ValueError(
                "collector directory already has an active writer"
            ) from error
        self.db = sqlite3.connect(self.out / "collector.sqlite3")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS journal (sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL, digest TEXT NOT NULL, event TEXT NOT NULL, result TEXT NOT NULL, snapshot TEXT NOT NULL)"
        )
        stored = self.db.execute("SELECT body FROM state WHERE id=1").fetchone()
        self.state = (
            json.loads(stored[0])
            if stored
            else {
                "version": 1,
                "mode": mode,
                "selection": None,
                "used_sessions": {},
                "window": None,
                "last_good": None,
                "unavailable_reason": None,
                "as_of": None,
                "last_result": None,
            }
        )
        if self.state["mode"] != mode or self.state["version"] != 1:
            self.close()
            raise ValueError(
                "existing collector mode/version differs; use its original mode or fresh directory"
            )
        self._publish_local()
        if mode == "network_probe" and self.state["as_of"] is not None:
            self.process({"action": "tick", "at": utc_now()})

    def close(self):
        if getattr(self, "db", None):
            self.db.close()
            self.db = None
        if getattr(self, "lock", None):
            self.lock.close()
            self.lock = None

    def snapshot(self):
        state = self.state
        selection = state["selection"]
        last = state["last_good"]
        age = None
        if last and state["as_of"]:
            age = (
                timestamp(state["as_of"]) - timestamp(last["source_timestamp"])
            ).total_seconds()
        elif state["window"] and state["window"]["anchor"] and state["as_of"]:
            age = (
                timestamp(state["as_of"]) - timestamp(state["window"]["anchor"])
            ).total_seconds()
        if not selection:
            status = "no_selected_game"
        elif state["window"] and state["window"]["finished"]:
            status = "finished"
        elif state["unavailable_reason"]:
            status = "unavailable"
        elif state.get("paused"):
            status = "paused"
        elif age is not None and age > selection["max_age_seconds"]:
            status = "stale"
        elif last is None:
            status = "awaiting_data"
        else:
            status = (
                "simulated_current"
                if state["mode"] == "simulated_replay"
                else "research_current"
            )
        return {
            "schema_version": "riot_collector_v1",
            "mode": state["mode"],
            "as_of": state["as_of"],
            "status": status,
            "selection": selection,
            "observation": last,
            "effective_age_seconds": age,
            "expires_at_utc": (
                (
                    timestamp(last["source_timestamp"])
                    + timedelta(seconds=selection["max_age_seconds"])
                ).isoformat()
                if last and selection
                else None
            ),
            "age_basis": (
                "simulated_receipt"
                if state["mode"] == "simulated_replay"
                else (
                    "recorded_receipt"
                    if state["mode"] == "recorded_replay"
                    else "local_receipt"
                )
            ),
            "unavailable_reason": state["unavailable_reason"],
            "last_result": state["last_result"],
            "elapsed_game_seconds": None,
            "live_state_verified": False,
        }

    def _publish_local(self):
        # The SQLite state is authoritative if interrupted between commit and replace.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", dir=self.out, prefix="latest-", suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(
                    json.dumps(self.snapshot(), indent=2, allow_nan=False) + "\n"
                )
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.out / "latest.json")
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    def _select(self, event):
        selection = {
            key: event[key]
            for key in [
                "session",
                "competition",
                "match_id",
                "game_id",
                "blue_id",
                "red_id",
                "max_age_seconds",
            ]
        }
        if (
            not isinstance(selection["competition"], str)
            or not selection["competition"]
        ):
            raise ValueError("competition identity required")
        # Construction validates all selected identities and positive finite age cap.
        window = window_load(selection, None)
        if selection["max_age_seconds"] is None:
            raise ValueError("explicit research freshness cap required")
        used = self.state["used_sessions"].get(selection["session"])
        if used is not None:
            if used != selection or self.state["selection"] != selection:
                raise ValueError(
                    "session ID already used; a new selection requires a new session"
                )
            return {"selection_resumed": True}
        self.state.update(
            selection=selection,
            window=window_dump(window),
            last_good=None,
            unavailable_reason=None,
            paused=False,
        )
        self.state["used_sessions"][selection["session"]] = selection
        return {"selection_changed": True}

    def _response(self, event):
        if self.state["selection"] is None:
            raise ValueError("select a game before ingesting responses")
        try:
            if "probe_dir" in event:
                payload, actual_receipt, evidence = read_probe(
                    event["probe_dir"], event.get("record_index", 0)
                )
            elif event.get("fixture") is True and self.state["mode"] != "network_probe":
                payload, actual_receipt, evidence = (
                    event["payload"],
                    event.get("actual_received_at_utc"),
                    {"synthetic_fixture": True},
                )
            else:
                raise ValueError(
                    "responses require a hash-verified probe; inline fixtures are replay-only"
                )
            if (
                self.state["mode"] != "simulated_replay"
                and actual_receipt != event["at"]
            ):
                raise ValueError(
                    "recorded/network replay time must equal actual receipt time"
                )
            window = window_load(self.state["selection"], self.state["window"])
            rows = window.review(payload, event["at"], evidence)
        except (ValueError, KeyError, TypeError, OSError) as error:
            self.state["unavailable_reason"] = str(error)
            return {"error": str(error), "rows": []}
        candidates = []
        for row in rows:
            if self.state["mode"] == "simulated_replay":
                row["simulated_received_at_utc"] = row["received_at_utc"]
                row["received_at_utc"] = actual_receipt
                row["simulated_source_age_seconds"] = row["source_age_seconds"]
                try:
                    row["source_age_seconds"] = (
                        (
                            timestamp(actual_receipt)
                            - timestamp(row["source_timestamp"])
                        ).total_seconds()
                        if actual_receipt and row["source_timestamp"]
                        else None
                    )
                except (ValueError, TypeError, OverflowError):
                    row["source_age_seconds"] = None
            row["collector_mode"] = self.state["mode"]
            if row["status"] == "research_candidate":
                candidates.append(row)
        self.state["window"] = window_dump(window)
        # A paused game sends frozen frames marked `paused`: not usable, but the
        # match is still on, so the page says paused rather than unavailable.
        self.state["paused"] = bool(
            rows
            and not candidates
            and rows[-1]["source_reported_state"] == "paused"
            and set(rows[-1]["rejection_reasons"]) <= PAUSE_REASONS
        )
        if candidates:
            self.state["last_good"] = candidates[-1]
            self.state["unavailable_reason"] = None
        elif not rows:
            self.state["unavailable_reason"] = "empty_source_window"
        elif self.state["paused"]:
            self.state["unavailable_reason"] = None
        else:
            last_reasons = rows[-1]["rejection_reasons"]
            if any(
                reason not in {"duplicate", "out_of_order", "stale_source_timestamp"}
                for reason in last_reasons
            ):
                self.state["unavailable_reason"] = (
                    "no_usable_current_observation: " + ",".join(last_reasons)
                )
        return {
            "row_count": len(rows),
            "candidate_count": len(candidates),
            "rows": rows,
        }

    def process(self, event):
        if not isinstance(event, dict):
            raise ValueError("event must be an object")
        at = timestamp(event["at"])
        digest = hashlib.sha256(canonical(event).encode()).hexdigest()
        event_id = event.get("event_id", digest)
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("event ID must be a nonempty string")
        prior = self.db.execute(
            "SELECT digest FROM journal WHERE event_id=?", (event_id,)
        ).fetchone()
        if prior:
            if prior[0] != digest:
                raise ValueError("event ID reused with different content")
            self._publish_local()
            return self.snapshot()
        if self.state["as_of"] and at < timestamp(self.state["as_of"]):
            raise ValueError("receipt/replay event times must not regress")
        previous = copy.deepcopy(self.state)
        try:
            action = event["action"]
            if action == "select":
                result = self._select(event)
            elif action == "response":
                result = self._response(event)
            elif action == "tick":
                result = {"clock_advanced": True}
            elif action == "error":
                self.state["unavailable_reason"] = str(
                    event.get("reason", "source_unavailable")
                )
                result = {"error": self.state["unavailable_reason"]}
            elif action == "deselect":
                self.state.update(
                    selection=None,
                    window=None,
                    last_good=None,
                    unavailable_reason=None,
                    paused=False,
                )
                result = {"selection_cleared": True}
            else:
                raise ValueError("unknown collector action")
            self.state["as_of"] = event["at"]
            self.state["last_result"] = {
                key: value for key, value in result.items() if key != "rows"
            }
            snapshot = self.snapshot()
            with self.db:
                self.db.execute(
                    "INSERT INTO journal(event_id,digest,event,result,snapshot) VALUES(?,?,?,?,?)",
                    (
                        event_id,
                        digest,
                        canonical(event),
                        canonical(result),
                        canonical(snapshot),
                    ),
                )
                self.db.execute(
                    "INSERT INTO state(id,body) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                    (canonical(self.state),),
                )
        except Exception:
            self.state = previous
            raise
        self._publish_local()
        return snapshot


def replay(path, out, simulated=False):
    mode = "simulated_replay" if simulated else "recorded_replay"
    collector = Collector(out, mode)
    try:
        with Path(path).open() as stream:
            for line in stream:
                if line.strip():
                    collector.process(json.loads(line))
        return collector.snapshot()
    finally:
        collector.close()
