#!/usr/bin/env bash
# Restore and save the prediction log (data/predictions.json) in the backup bucket.
#
#   prediction_log.sh restore   copy $PREDICTIONS_BACKUP to data/predictions.json
#   prediction_log.sh save      copy it back; with --if-unchanged, only when nobody
#                               else wrote the backup since this run restored it
#
# Restore fails on any error except a missing file, so an S3 hiccup can't start a
# new log that the save would then write over the real one. Save refuses a log with
# fewer matches than the backup (the log only grows). Every write is conditional
# on the observed ETag (or nonexistence), so a race never replaces newer history.
# The hourly prices job saves
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

saved() {
    if [ -n "${GITHUB_OUTPUT:-}" ]; then
        echo "saved=$1" >> "$GITHUB_OUTPUT"
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
    [ -f "$LOG" ] || { echo "No prediction log to save."; saved false; exit 0; }
    restored=$(cat "$STATE" 2>/dev/null || true)
    current=$(etag)
    if [ "$current" != "$restored" ]; then
        if [ "${2:-}" = "--if-unchanged" ]; then
            echo "::warning::The prediction log changed since it was restored; not saving (next run retries)."
            saved false
            exit 0
        fi
        echo "::error::The prediction log changed since restore; refusing to overwrite newer saved calls or alerts. Rerun this build."
        exit 1
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
    # S3 checks this condition atomically, including a writer racing after head.
    condition=(--if-none-match '*')
    [ -z "$current" ] || condition=(--if-match "$current")
    aws s3api put-object --bucket "$bucket" --key "$key" --body "$LOG" \
        --content-type application/json "${condition[@]}" >/dev/null
    saved true
    echo "Saved the prediction log: $(count "$LOG") matches."
    ;;
*)
    echo "usage: $0 restore|save [--if-unchanged]" >&2
    exit 2
    ;;
esac
