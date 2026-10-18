#!/usr/bin/env bash
# Run feed_timelines.py collect in N shards that survive this machine sleeping or
# going offline (exit 4: rerun a minute later). A refusal or server error from
# Riot (exit 3) pauses the shard 5 minutes, once: Riot answers an isolated 403
# now and then and the same request succeeds soon after. A shard refused again
# before it saves another map stops for good. Logs: <out>/collect_<i>.log.
#   bash scripts/research/feed_timelines_collect.sh [out] [shards] [shard index ...]
# EXTRA: more collect arguments, e.g. EXTRA="--split 1/4" to share a slow
# shard's missing maps among runs.
set -u
cd "$(dirname "$0")/../.."
out=${1:-data/feed_timelines}
shards=${2:-4}
shift $(($# < 2 ? $# : 2))
which=${*:-$(seq 0 $((shards - 1)))}
saved() { grep -c " samples" "$1" 2>/dev/null || true; }
for i in $which; do
  (
    log="$out/collect_$i.log"
    refused_at=-1
    while true; do
      # PYTHON: an interpreter command (default: uv run python).
      caffeinate -i ${PYTHON:-uv run --quiet python} scripts/research/feed_timelines.py collect \
        --shard "$i/$shards" --out "$out" ${EXTRA:-} >>"$log" 2>&1
      code=$?
      if [ "$code" -eq 4 ]; then
        sleep 60
      elif [ "$code" -eq 3 ]; then
        now=$(saved "$log")
        if [ "$now" -eq "$refused_at" ]; then
          echo "Refused twice with no map saved between: shard stopped." >>"$log"
          exit 3
        fi
        refused_at=$now
        sleep 300
      else
        exit "$code"
      fi
    done
  ) &
done
wait
