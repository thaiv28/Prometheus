"""Bring the live worker's saved matches to this machine, and list them.

    uv run python scripts/live_data.py pull     # s3://$DATA_BACKUP_BUCKET/prometheus/live/ -> data/live/
    uv run python scripts/live_data.py list     # every saved map: teams, winner, frames, calls, quotes

`pull` needs AWS credentials that can read the artifacts bucket (`--bucket` or
DATA_BACKUP_BUCKET). It unpacks each finished map's archive.tar.gz (raw Riot
responses, the collector's SQLite, Kalshi quotes) next to it. Load the maps in
Python with `prometheus.live.data.load_maps()`.
"""

import argparse
import os
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prometheus.live.data import load_maps


def unpack(root):
    """Extract every archive whose contents aren't there yet; returns the count."""
    count = 0
    for archive in sorted(Path(root).glob("*/*/archive.tar.gz")):
        done = archive.parent / ".unpacked"
        if done.exists():
            continue
        with tarfile.open(archive) as tar:
            tar.extractall(archive.parent, filter="data")
        done.touch()
        count += 1
    return count


def pull(bucket, root):
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["aws", "s3", "sync", f"s3://{bucket}/prometheus/live/", str(root)],
        check=True,
    )
    print(f"Unpacked {unpack(root)} map archives into {root}")


def show(root):
    maps = load_maps(root)
    for m in maps:
        winner = m.teams[m.winner] if m.winner in (0, 1) else "?"
        print(
            f"{m.match_id} map {m.number}: {m.teams[0]} v {m.teams[1]}, won by "
            f"{winner}; {len(m.frames):,} frames, {len(m.calls)} calls, "
            f"{len(m.market)} quotes"
        )
    print(f"{len(maps)} maps under {root}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("pull", "list"))
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "live")
    parser.add_argument("--bucket", default=os.environ.get("DATA_BACKUP_BUCKET"))
    args = parser.parse_args(argv)
    if args.command == "pull":
        if not args.bucket:
            parser.error("--bucket or DATA_BACKUP_BUCKET is required to pull")
        pull(args.bucket, args.root)
    show(args.root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
