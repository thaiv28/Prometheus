#!/usr/bin/env bash
# Restore and save the prediction log (data/predictions.json) in the backup bucket.
#
#   prediction_log.sh restore   copy $PREDICTIONS_BACKUP to data/predictions.json
#   prediction_log.sh save      copy it back; with --if-unchanged, only when nobody
#                               else wrote the backup since this run restored it
#
# Restore fails on any error except a missing file, so an S3 hiccup can't start a
# new log that the save would then write over the real one. Save refuses a log with
# fewer matches than the backup (the log only grows). The hourly prices job saves
# with --if-unchanged: a publish run that wrote in between keeps its new calls, and
# the prices job tries again next hour.
set -euo pipefail

LOG=data/predictions.json
STATE=data/.predictions-etag # the restored backup's ETag
uri="${PREDICTIONS_BACKUP:?set PREDICTIONS_BACKUP}"
path="${uri#s3://}"
bucket="${path%%/*}"
key="${path#*/}"

count() { python3 -c 'import json, sys; print(len(json.load(open(sys.argv[1]))["matches"]))' "$1"; }

# The backup's ETag, empty when it doesn't exist; exits on any other error.
etag() {
    local out
    if out=$(aws s3api head-object --bucket "$bucket" --key "$key" \
        --query ETag --output text 2>&1); then
        echo "$out"
    elif grep -q "(404)" <<<"$out"; then
        echo ""
    else
        echo "::error::Can't read $uri: $out" >&2
        exit 1
    fi
}

case "${1:-}" in
restore)
    mkdir -p data
    tag=$(etag)
    if [ -z "$tag" ]; then
        echo "No saved prediction log yet; the build starts a new one."
        : >"$STATE"
        exit 0
    fi
    aws s3api get-object --bucket "$bucket" --key "$key" --if-match "$tag" "$LOG" >/dev/null
    echo "$tag" >"$STATE"
    echo "Restored the prediction log: $(count "$LOG") matches."
    ;;
save)
    [ -f "$LOG" ] || { echo "No prediction log to save."; exit 0; }
    restored=$(cat "$STATE" 2>/dev/null || true)
    current=$(etag)
    if [ "$current" != "$restored" ]; then
        if [ "${2:-}" = "--if-unchanged" ]; then
            echo "::warning::The prediction log changed since it was restored; not saving (next run retries)."
            exit 0
        fi
        echo "::warning::The prediction log changed since it was restored; this run's log replaces it."
    fi
    if [ -n "$current" ]; then
        tmp=$(mktemp)
        aws s3 cp "$uri" "$tmp" --only-show-errors
        before=$(count "$tmp")
        rm -f "$tmp"
        after=$(count "$LOG")
        if [ "$after" -lt "$before" ]; then
            echo "::error::Not saving: the log has $after matches, the backup $before." >&2
            exit 1
        fi
    fi
    aws s3 cp "$LOG" "$uri" --only-show-errors --content-type application/json
    echo "Saved the prediction log: $(count "$LOG") matches."
    ;;
*)
    echo "usage: $0 restore|save [--if-unchanged]" >&2
    exit 2
    ;;
esac
