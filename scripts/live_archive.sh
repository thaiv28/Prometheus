#!/usr/bin/env bash
# Restore the finished live maps for the live results pages into data/live/.
#
#   LIVE_BACKUP=s3://<bucket>/prometheus/live bash scripts/live_archive.sh
#
# The live worker backs up each finished map's page file (pages/map<n>.json,
# about 3 MB) to $LIVE_BACKUP/<match>/ (deploy/live/backup.sh). The compact
# copies (map<n>.min.json) and each match's results.json (settled map winners)
# are synced down; each page file without a current compact copy is downloaded,
# cut down by prometheus.live.archive (a few KB, with Kalshi's minute prices
# where the service recorded none) and its copy uploaded beside it. A failure leaves the
# pages without the newest maps, never fails the build.
set -uo pipefail

uri="${LIVE_BACKUP:?set LIVE_BACKUP}"
uri="${uri%/}"
dest=data/live
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

if ! aws s3 ls "$uri/" --recursive >"$tmp/list"; then
    echo "::warning::Can't list $uri; live results keep only what is restored."
    exit 0
fi
keys=$(awk '{print $4}' "$tmp/list")
prefix="${uri#s3://}"
prefix="${prefix#*/}/"
mkdir -p "$dest"
aws s3 sync "$uri/" "$dest/" --only-show-errors --exclude '*' \
    --include '*/pages/map*.min.json' --include '*/results.json' ||
    echo "::warning::Couldn't restore the live results."
# A compact copy from an older prometheus.live.archive (SCHEMA) is made again.
schema=$(uv run --no-sync python -c 'from prometheus.live.archive import SCHEMA; print(SCHEMA)')
made=0
for key in $(grep -E '/pages/map[0-9]+\.json$' <<<"$keys"); do
    rel="${key#"$prefix"}"
    min="$dest/${rel%.json}.min.json"
    grep -qF "\"schema\":$schema," "$min" 2>/dev/null && continue
    mkdir -p "$(dirname "$min")"
    if aws s3 cp "$uri/$rel" "$tmp/map.json" --only-show-errors &&
        uv run --no-sync python -m prometheus.live.archive "$tmp/map.json" "$min" &&
        aws s3 cp "$min" "$uri/${rel%.json}.min.json" --only-show-errors \
            --content-type application/json; then
        made=$((made + 1))
    else
        echo "::warning::Couldn't compact $rel"
        rm -f "$min"
    fi
done
echo "Live results: $made maps compacted, $(find "$dest" -name 'map*.min.json' | wc -l | tr -d ' ') restored."
