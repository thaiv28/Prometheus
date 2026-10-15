"""Restore the original BNK alert from the versioned backup, once.

Issue #45 documents BNK before the match. Recover exact original terms from S3,
never the rounded notification or a later model. Only the identified alert and
its recovery audit change. Default is a dry run; --apply writes the restored log.
No-op after recovery, or when the legacy entry is absent (e.g. a fresh PR log).
"""

import argparse
import copy
import json
import subprocess
import tempfile
from pathlib import Path

MATCH = "2026 Demacia Cup Global Invitational_Semifinals_1"
TEAM = "BNK FEARX"
ISSUE = "https://github.com/thaiv28/Prometheus/issues/45"
# First notification: October 12, 21:17 UTC. Inspect backups from that hour up to
# the currently corrupt record, in chronological order. Never inspect the result.
SINCE = "2026-10-12T21:00:00"


def needs_recovery(log):
    entry = log.get(MATCH, {})
    return bool(entry.get("alert") and not entry.get("alert_history_recovery"))


def restore(log, snapshots):
    if not needs_recovery(log):
        return None
    entry = log[MATCH]
    pair = [entry.get(f"ours{i}") or entry.get(f"team{i}") for i in (1, 2)]
    if TEAM not in pair:
        raise ValueError("Recovery fixture's teams do not match the original alert")
    for version, saved in snapshots:
        candidates = [
            e
            for e in saved.values()
            if e.get("alert")
            and e.get("start") == entry["start"]
            and {e.get("ours1") or e.get("team1"), e.get("ours2") or e.get("team2")}
            == set(pair)
        ]
        if not candidates:
            continue
        old = min(candidates, key=lambda e: e["alert"]["at"])
        alert = old["alert"]
        backed = (
            alert.get("team")
            or old.get(f"ours{alert['side']}")
            or old.get(f"team{alert['side']}")
        )
        if backed != TEAM or alert["at"] >= entry["start"]:
            raise ValueError(
                "Earliest preserved alert disagrees with the pre-match notification"
            )
        restored = {**alert, "team": TEAM, "side": pair.index(TEAM) + 1}
        audit = {
            "source_issue": ISSUE,
            "source_match_id": old["match_id"],
            "source_version": version,
            "previous_alert": copy.deepcopy(entry["alert"]),
        }
        entry["alert"], entry["alert_history_recovery"] = restored, audit
        return {
            "match_id": MATCH,
            "before": audit["previous_alert"],
            "after": restored,
            "source_version": version,
        }
    raise ValueError("No original BNK alert found in preserved backup versions")


def read_log(path):
    return {e["match_id"]: e for e in json.loads(Path(path).read_text())["matches"]}


def aws(*args):
    return subprocess.check_output(["aws", "--no-cli-pager", *args], text=True)


def snapshots(uri, until):
    bucket, key = uri.removeprefix("s3://").split("/", 1)
    listing = json.loads(
        aws(
            "s3api",
            "list-object-versions",
            "--bucket",
            bucket,
            "--prefix",
            key,
            "--output",
            "json",
        )
    )
    versions = [
        v
        for v in listing.get("Versions", [])
        if v["Key"] == key and SINCE <= v["LastModified"][:19] <= until[:19]
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for v in sorted(versions, key=lambda v: v["LastModified"]):
            target = str(Path(tmp) / "log.json")
            aws(
                "s3api",
                "get-object",
                "--bucket",
                bucket,
                "--key",
                key,
                "--version-id",
                v["VersionId"],
                target,
            )
            yield v["VersionId"], read_log(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", default="data/predictions.json", type=Path)
    parser.add_argument("--backup", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    log = read_log(args.log)
    if not needs_recovery(log):
        print("Legacy alert recovery: nothing to do")
        return
    result = restore(log, snapshots(args.backup, log[MATCH]["alert"]["at"]))
    print(json.dumps(result, sort_keys=True))
    if args.apply:
        original = json.loads(args.log.read_text())
        original["matches"] = [log[e["match_id"]] for e in original["matches"]]
        args.log.write_text(json.dumps(original, ensure_ascii=False, indent=1))
        print("Restored original alert; saved forecasts untouched")


if __name__ == "__main__":
    main()
