"""Read and rotate the work log (stdlib only, so the pre-commit hook needs no venv).

    python3 scripts/work_log.py recent [N]   # print the newest N entries (default 5)
    python3 scripts/work_log.py rotate       # move all but the newest KEEP entries to the archive

Rotation runs once the log holds more than MAX entries and keeps KEEP, so it
happens every few entries rather than on every commit. Entries start at a
`## ` heading; moved entries go to the top of the archive, newest first.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "docs/steering/work_log.md"
ARCHIVE = ROOT / "docs/steering/work_log_archive.md"
KEEP = 10
MAX = 15


def split(text):
    """Return (header, entries), each entry a string starting with '## '."""
    parts = text.split("\n## ")
    header, entries = parts[0], ["## " + p for p in parts[1:]]
    if header.startswith("## "):  # no header at all
        header, entries = "", [header] + entries
    return header.rstrip("\n") + "\n\n", [e.rstrip("\n") + "\n\n" for e in entries]


def recent(n=5):
    _, entries = split(LOG.read_text())
    sys.stdout.write("".join(entries[:n]))


def rotate():
    header, entries = split(LOG.read_text())
    if len(entries) <= MAX:
        return False
    keep, moved = entries[:KEEP], entries[KEEP:]
    a_header, a_entries = split(ARCHIVE.read_text())
    LOG.write_text((header + "".join(keep)).rstrip("\n") + "\n")
    ARCHIVE.write_text((a_header + "".join(moved + a_entries)).rstrip("\n") + "\n")
    print(f"work_log: moved {len(moved)} entries to {ARCHIVE.name}, kept {KEEP}")
    return True


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "recent"
    if cmd == "recent":
        recent(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
    elif cmd == "rotate":
        rotate()
    else:
        sys.exit(__doc__)
