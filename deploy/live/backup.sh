#!/usr/bin/env bash
# Back up the live worker's evidence to s3://$ARTIFACTS_BUCKET/prometheus/live/,
# run by refresh.sh and when the service stops. Per match: settled results, the
# call journal, FORGE's call, series quotes, Kalshi's book before each map
# (pre_quotes.jsonl: the draft and loading screen), each finished map's page file
# (pages/map<n>.json: frames, calls, Kalshi, winner) and each finished map's
# packed evidence (archive.tar.gz: raw responses, collector, quotes).
# `scripts/live_data.py pull` brings it all back locally.
set -euo pipefail
# shellcheck source=/dev/null
source /etc/prometheus-live.env
cd "$APP_ROOT/app"
dest="s3://$ARTIFACTS_BUCKET/prometheus/live"

if [ -d data/live ]; then
  aws s3 sync data/live "$dest/" --only-show-errors \
    --exclude '*' --include '*/archive.tar.gz' --include '*/results.json' \
    --include '*/calls.jsonl' --include '*/forge.json' --include '*/series_quotes.jsonl' \
    --include '*/pre_quotes.jsonl' --include '*/draft_context.json' --include '*/trading/*'
fi
for match in output/live/*/; do
  [ -d "$match" ] || continue
  id=$(basename "$match")
  aws s3 sync "$match" "$dest/$id/pages/" --only-show-errors --exclude '*' --include 'map*.json'
done
