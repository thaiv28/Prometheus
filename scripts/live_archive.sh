#!/usr/bin/env bash
# Restore the finished live maps for the live results pages into data/live/.
#
#   LIVE_BACKUP=s3://<bucket>/prometheus/live bash scripts/live_archive.sh
#
# The live worker backs up each finished map's page file (pages/map<n>.json,
# about 3 MB) to $LIVE_BACKUP/<match>/ (deploy/live/backup.sh). Each one without
# a compact copy beside it is downloaded once, cut down by prometheus.live.archive
# (a few KB) and its map<n>.min.json uploaded; then every compact copy and each
# match's results.json (settled map winners) is synced down. A failure leaves the
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
made=0
for key in $(grep -E '/pages/map[0-9]+\.json$' <<<"$keys"); do
    min="${key%.json}.min.json"
    grep -qxF "$min" <<<"$keys" && continue
    rel="${key#"$prefix"}"
    if aws s3 cp "$uri/$rel" "$tmp/map.json" --only-show-errors &&
        uv run --no-sync python -m prometheus.live.archive "$tmp/map.json" "$tmp/map.min.json" &&
        aws s3 cp "$tmp/map.min.json" "$uri/${rel%.json}.min.json" --only-show-errors \
            --content-type application/json; then
        made=$((made + 1))
    else
        echo "::warning::Couldn't compact $rel"
    fi
done
mkdir -p "$dest"
aws s3 sync "$uri/" "$dest/" --only-show-errors --exclude '*' \
    --include '*/pages/map*.min.json' --include '*/results.json' ||
    echo "::warning::Couldn't restore the live results."
echo "Live results: $made new maps compacted, $(find "$dest" -name 'map*.min.json' | wc -l | tr -d ' ') restored."
