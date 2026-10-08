#!/usr/bin/env bash
# Rebuild db/prometheus.db from Oracle's Elixir CSVs.
#
# Data: CSVs live in data/raw. If it's empty they are downloaded from Google Drive.
# Set REFRESH_DATA=1 (CI does on main, once a day) to download the current year's
# file even when CSVs exist, or REFRESH_DATA=full for every year's; if a download
# fails (Drive rate-limits shared files), the existing CSVs are used instead.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
RAW_DIR="$ROOT_DIR/data/raw"
DB_PATH="$ROOT_DIR/db/prometheus.db"
FRESH_MARKER="$ROOT_DIR/data/.fresh-download" # tells CI to back up the new CSVs

mkdir -p "$RAW_DIR"
rm -f "$FRESH_MARKER"
have_csvs() { compgen -G "$RAW_DIR/*.csv" > /dev/null; }

# scripts/download_data.py downloads each file on its own and replaces one in
# data/raw only when it parses and isn't older, so a refused or partial download
# never mixes with good data. REFRESH_DATA=full downloads every year's file;
# otherwise only the current year's when the rest are present.
download() {
    if [ "${REFRESH_DATA:-0}" = "full" ]; then
        python3 "$SCRIPT_DIR/download_data.py" --full
    else
        python3 "$SCRIPT_DIR/download_data.py"
    fi
}

if ! have_csvs || [ "${REFRESH_DATA:-0}" != "0" ]; then
    if ! download; then
        if have_csvs; then
            echo "::warning::Google Drive download failed for some files; building from the CSVs at hand."
        else
            echo "::error::Google Drive download failed and no cached CSVs exist." >&2
            exit 1
        fi
    fi
else
    echo "$RAW_DIR has CSVs. Skipping download (set REFRESH_DATA=1 to refresh)."
fi

# Rebuild the database from scratch
rm -f "$DB_PATH"
mkdir -p "$(dirname "$DB_PATH")"

# Run every numbered script in order
for script in "$SCRIPT_DIR"/[0-9]*; do
    if [[ "$script" == *.sql ]]; then
        echo "Running SQL script: $script"
        sqlite3 "$DB_PATH" < "$script"
    elif [[ "$script" == *.py ]]; then
        echo "Running Python script: $script"
        python3 "$script"
    fi
done

rows=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM matches")
if [ "$rows" -eq 0 ]; then
    echo "::error::matches table is empty after setup." >&2
    exit 1
fi
echo "Database ready: $rows team-game rows."
