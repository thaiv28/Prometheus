#!/usr/bin/env bash
# Rebuild db/prometheus.db from Oracle's Elixir CSVs.
#
# Data: CSVs live in data/raw. If it's empty they are downloaded from Google Drive.
# Set REFRESH_DATA=1 (CI does) to re-download even when CSVs exist; if that download
# fails (Drive rate-limits shared files), the existing CSVs are used instead.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
RAW_DIR="$ROOT_DIR/data/raw"
DB_PATH="$ROOT_DIR/db/prometheus.db"
FRESH_MARKER="$ROOT_DIR/data/.fresh-download" # tells CI to back up the new CSVs
GDRIVE_ID="1gLSw0RLjBbtaNy0dgnGQDAZOHIgCe-HH" # Oracle's Elixir game data folder

mkdir -p "$RAW_DIR"
rm -f "$FRESH_MARKER"
have_csvs() { compgen -G "$RAW_DIR/*.csv" > /dev/null; }

# Download into a temp dir and only replace data/raw on full success,
# so a failed or partial download never mixes with good data.
download() {
    local tmp
    tmp="$(mktemp -d)"
    for attempt in 1 2 3; do
        echo "Downloading data/raw from Google Drive (attempt $attempt)..."
        if gdown --folder "https://drive.google.com/drive/folders/$GDRIVE_ID" -O "$tmp" \
            && compgen -G "$tmp/*.csv" > /dev/null; then
            for zipfile in "$tmp"/*.zip; do
                [ -f "$zipfile" ] && unzip -o "$zipfile" -d "$tmp" && rm "$zipfile"
            done
            rm -f "$RAW_DIR"/*.csv
            mv "$tmp"/*.csv "$RAW_DIR"/
            rm -rf "$tmp"
            touch "$FRESH_MARKER"
            return 0
        fi
        [ "$attempt" -lt 3 ] && sleep $((attempt * 30))
    done
    rm -rf "$tmp"
    return 1
}

if ! have_csvs || [ "${REFRESH_DATA:-0}" = "1" ]; then
    if ! download; then
        if have_csvs; then
            echo "::warning::Google Drive download failed; building from cached CSVs."
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
