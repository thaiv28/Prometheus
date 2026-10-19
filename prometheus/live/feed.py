"""Experimental offline normalization of explicitly selected Riot window snapshots."""

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp needs timezone")
    return parsed.astimezone(UTC)


def object_or_empty(value):
    return value if isinstance(value, dict) else {}


def integer(value):
    return value if type(value) is int and value >= 0 else None


class WindowSession:
    """Past-only review; selecting another map requires a new explicit session."""

    def __init__(self, session, match_id, game_id, blue_id, red_id, max_age=None):
        if not all(
            isinstance(v, str) and v
            for v in [session, match_id, game_id, blue_id, red_id]
        ):
            raise ValueError("explicit nonempty session/match/game/team IDs required")
        if blue_id == red_id:
            raise ValueError("team sides must differ")
        if max_age is not None and (
            isinstance(max_age, bool) or not math.isfinite(max_age) or max_age <= 0
        ):
            raise ValueError("research max_age must be finite and positive")
        self.session = session
        self.match_id = match_id
        self.game_id = game_id
        self.team_ids = {"blue": blue_id, "red": red_id}
        self.max_age = max_age
        self.seen = {}
        self.anchor = None
        self.finished = False
        self.sequence = 0

    def review(self, payload, received_at, evidence):
        receipt = timestamp(received_at)
        if not isinstance(payload, dict) or not isinstance(payload.get("frames"), list):
            raise ValueError("window must contain a frames list")
        metadata = object_or_empty(payload.get("gameMetadata"))
        identity_reasons = []
        if (
            payload.get("esportsGameId") != self.game_id
            or payload.get("esportsMatchId") != self.match_id
        ):
            identity_reasons.append("selected_game_or_match_mismatch")
        for side in self.team_ids:
            team = object_or_empty(metadata.get(f"{side}TeamMetadata"))
            if team.get("esportsTeamId") != self.team_ids[side]:
                identity_reasons.append(f"{side}_team_identity_mismatch")
        rows = []
        for raw in payload["frames"]:
            frame = object_or_empty(raw)
            reasons = list(identity_reasons)
            field_reasons = []
            age = None
            source_time = None
            try:
                source_time = timestamp(frame.get("rfc460Timestamp"))
                age = (receipt - source_time).total_seconds()
                if age < 0:
                    reasons.append("future_source_timestamp")
                elif self.max_age is None:
                    reasons.append("freshness_policy_unassessed")
                elif age > self.max_age:
                    reasons.append("stale_source_timestamp")
            except (ValueError, TypeError, OverflowError):
                reasons.append("invalid_source_timestamp")
            digest = hashlib.sha256(
                json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            # Invalid identity/future data cannot poison the selected session anchor.
            if source_time is not None and not identity_reasons and age >= 0:
                if source_time in self.seen:
                    reasons.append(
                        "duplicate"
                        if self.seen[source_time] == digest
                        else "timestamp_collision"
                    )
                elif self.anchor is not None and source_time < self.anchor:
                    reasons.append("out_of_order")
                else:
                    self.seen[source_time] = digest
                    self.anchor = source_time
            state = frame.get("gameState")
            if state != "in_game":
                reasons.append("source_not_in_game")
            if self.finished:
                reasons.append("selected_map_already_finished")
            if (
                state == "finished"
                and not identity_reasons
                and source_time is not None
                and age >= 0
                and (self.anchor is None or source_time >= self.anchor)
            ):
                # Riot can emit a terminal state at the same timestamp as gameplay.
                # Preserve the collision rejection and conservatively close the map.
                self.finished = True
            teams = {}
            for side in self.team_ids:
                team = object_or_empty(frame.get(f"{side}Team"))
                meta = object_or_empty(metadata.get(f"{side}TeamMetadata"))
                normalized = {"team_id": meta.get("esportsTeamId"), "side": side}
                for key in [
                    "totalGold",
                    "totalKills",
                    "towers",
                    "inhibitors",
                    "barons",
                ]:
                    normalized[key] = integer(team.get(key))
                    if normalized[key] is None:
                        field_reasons.append(f"{side}.{key}:missing_or_invalid")
                dragons = team.get("dragons")
                normalized["dragons"] = (
                    dragons
                    if isinstance(dragons, list)
                    and all(isinstance(v, str) and v for v in dragons)
                    else None
                )
                if normalized["dragons"] is None:
                    field_reasons.append(f"{side}.dragons:missing_or_invalid")
                participants = meta.get("participantMetadata")
                normalized["participant_metadata"] = (
                    participants if isinstance(participants, list) else None
                )
                if normalized["participant_metadata"] is None:
                    field_reasons.append(
                        f"{side}.participant_metadata:missing_or_invalid"
                    )
                live_participants = team.get("participants")
                if (
                    isinstance(live_participants, list)
                    and len(live_participants) == 5
                    and all(
                        isinstance(p, dict) and integer(p.get("kills")) is not None
                        for p in live_participants
                    )
                    and normalized["totalKills"] is not None
                    and normalized["totalKills"]
                    != sum(p["kills"] for p in live_participants)
                ):
                    normalized["totalKills"] = None
                    field_reasons.append(
                        f"{side}.totalKills:participant_sum_disagreement"
                    )
                if (
                    team.get("totalGold") == 0
                    and isinstance(live_participants, list)
                    and live_participants
                    and all(
                        isinstance(p, dict) and p.get("maxHealth") == 0
                        for p in live_participants
                    )
                ):
                    reasons.append(f"{side}_startup_placeholder_pattern")
                teams[side] = normalized
            # A conflicting aggregate kill counter must not erase the gold,
            # clock and other objectives. Keep kills unknown; inference falls
            # back to v1 rather than using an untrusted objective count.
            if any(
                not reason.endswith(":participant_sum_disagreement")
                for reason in field_reasons
            ):
                reasons.append("incomplete_or_invalid_fields")
            rows.append(
                {
                    "schema_version": "riot_window_research_v1",
                    "source": "riot_lolesports_window",
                    "session": self.session,
                    "match_id": payload.get("esportsMatchId"),
                    "game_id": payload.get("esportsGameId"),
                    "sequence": self.sequence,
                    "source_timestamp": frame.get("rfc460Timestamp"),
                    "received_at_utc": received_at,
                    "processed_at_utc": datetime.now(UTC).isoformat(),
                    "published_at_utc": None,
                    "source_age_seconds": age,
                    "research_max_age_seconds": self.max_age,
                    "elapsed_game_seconds": None,
                    "elapsed_clock_reason": "authoritative_elapsed_clock_not_verified",
                    "source_reported_state": state,
                    "status": "rejected" if reasons else "research_candidate",
                    "rejection_reasons": reasons,
                    "field_reasons": field_reasons,
                    "teams": teams,
                    "objective_semantics": "source_fields_preserved_not_model_approved",
                    "live_state_verified": False,
                    "evidence": evidence,
                    "raw_frame_sha256": digest,
                }
            )
            self.sequence += 1
        return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe_dir", type=Path)
    for field in ["session", "match-id", "game-id", "blue-id", "red-id"]:
        parser.add_argument(f"--{field}", required=True)
    parser.add_argument("--research-max-age", type=float)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.probe_dir / "manifest.json").read_text())
    session = WindowSession(
        args.session,
        args.match_id,
        args.game_id,
        args.blue_id,
        args.red_id,
        args.research_max_age,
    )
    rows = []
    for record in manifest["records"]:
        if (
            record.get("http_status") != 200
            or record.get("error")
            or record.get("parse_error")
        ):
            raise ValueError("failed response cannot supply an observation")
        filename = record["raw_file"]
        if Path(filename).name != filename:
            raise ValueError("raw response must be in probe directory")
        raw_path = args.probe_dir / filename
        raw = raw_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("raw response hash mismatch")
        rows.extend(
            session.review(
                json.loads(raw),
                record["received_at_utc"],
                {
                    "raw_path": str(raw_path.resolve()),
                    "response_sha256": record["sha256"],
                    "url": record["url"],
                },
            )
        )
    with args.out.open("x") as output:
        json.dump(rows, output, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
