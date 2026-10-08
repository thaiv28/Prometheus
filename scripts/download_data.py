"""Download Oracle's Elixir CSVs from Google Drive into data/raw.

Drive refuses a file that has been downloaded too often ("Too many users have
viewed or downloaded this file recently"), and `gdown --folder` fails the whole
folder when any one file is refused. So this lists the folder, then downloads
each file on its own: only the current year's (and, in January, last year's)
when data/raw already has the others, every file with `--full` or when some are
missing. A file replaces the one in data/raw only if it parses and has games
after the old file's newest, so a refused or stale download never replaces good
data, and a day whose file hasn't been updated yet doesn't count as downloaded.

Exit status: 0 when every wanted file was downloaded, 1 when any failed (the
files that did download are kept). data/.fresh-download is touched when any file
was replaced, which is when CI backs the CSVs up and caches them for the day.
"""

import argparse
import csv
import datetime
import shutil
import sys
import tempfile
import time
from pathlib import Path

import gdown

FOLDER_ID = "1gLSw0RLjBbtaNy0dgnGQDAZOHIgCe-HH"  # Oracle's Elixir game data
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
FRESH_MARKER = ROOT / "data" / ".fresh-download"  # tells CI to back up the new CSVs
ATTEMPTS = 3


def newest_date(path):
    """The newest `date` in an Oracle's Elixir CSV, or None if it doesn't parse."""
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            col = next(reader).index("date")
            return max((row[col] for row in reader if len(row) > col), default=None)
    except (OSError, StopIteration, ValueError, UnicodeDecodeError, csv.Error):
        return None


def wanted(names, raw_dir, today, full=False):
    """Which of the folder's CSV names to download."""
    if full or any(not (raw_dir / n).exists() for n in names):
        return list(names)
    years = {str(today.year)} | ({str(today.year - 1)} if today.month == 1 else set())
    return [n for n in names if n[:4] in years]


def fetch(file_id, name, tmp, attempts=ATTEMPTS):
    """Download one file into `tmp`; its path, or None after `attempts` refusals."""
    out = tmp / name
    for attempt in range(1, attempts + 1):
        try:
            if gdown.download(id=file_id, output=str(out), quiet=True) and out.exists():
                return out
        except Exception as e:  # gdown raises on Drive's refusal
            print(f"  {name}: attempt {attempt} failed ({str(e).splitlines()[0]})")
        if attempt < attempts:
            time.sleep(10)  # the refusal lasts hours; a long wait doesn't help
    return None


def install(new, dest):
    """Move `new` over `dest` if it parses and has newer games. Returns whether it did."""
    new_date = newest_date(new)
    if new_date is None:
        print(
            f"  {dest.name}: download doesn't parse as an Oracle's Elixir CSV; kept the old file"
        )
        return False
    old_date = newest_date(dest) if dest.exists() else None
    if old_date is not None and new_date <= old_date:
        print(f"  {dest.name}: no games after {old_date[:10]}; kept the old file")
        return False
    shutil.move(str(new), dest)
    print(f"  {dest.name}: games through {new_date[:10]}")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Download every file")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    FRESH_MARKER.unlink(missing_ok=True)
    files = gdown.download_folder(id=FOLDER_ID, skip_download=True, quiet=True)
    ids = {Path(f.path).name: f.id for f in files if f.path.endswith(".csv")}
    if not ids:
        print("Google Drive folder listing has no CSVs.", file=sys.stderr)
        return 1
    today = datetime.datetime.now(datetime.timezone.utc).date()
    names = wanted(sorted(ids), RAW_DIR, today, args.full)
    print(
        f"Downloading {len(names)} of {len(ids)} Oracle's Elixir files: {', '.join(n[:4] for n in names)}"
    )
    failed, changed = [], False
    with tempfile.TemporaryDirectory() as tmp:
        for name in names:
            path = fetch(ids[name], name, Path(tmp))
            if path is None:
                failed.append(name)
            else:
                changed |= install(path, RAW_DIR / name)
    if changed:
        FRESH_MARKER.touch()
    if failed:
        print(f"Not downloaded: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
