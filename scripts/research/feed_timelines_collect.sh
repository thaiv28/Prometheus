#!/usr/bin/env bash
# Run feed_timelines.py collect in N shards that survive this machine sleeping or
# going offline (exit 4: rerun a minute later). A refusal or server error from
# Riot (exit 3) stops that shard for good. Logs: <out>/collect_<i>.log.
#   bash scripts/research/feed_timelines_collect.sh [out] [shards]
set -u
cd "$(dirname "$0")/../.."
out=${1:-data/feed_timelines}
shards=${2:-4}
for ((i = 0; i < shards; i++)); do
  (
    while true; do
      # PYTHON: an interpreter command (default: uv run python).
      caffeinate -i ${PYTHON:-uv run --quiet python} scripts/research/feed_timelines.py collect \
        --shard "$i/$shards" --out "$out" >>"$out/collect_$i.log" 2>&1
      code=$?
      [ "$code" -eq 4 ] || exit "$code"
      sleep 60
    done
  ) &
done
wait
