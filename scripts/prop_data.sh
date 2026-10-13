#!/usr/bin/env bash
# Restore and save the props data in the backup bucket: the pick'em lines log
# (data/prop_lines.jsonl, appended by the hourly job) and our saved calls on them
# (data/prop_calls.json, written by the publish build).
#
#   prop_data.sh restore FILE URI   copy URI to FILE (a missing backup is fine)
#   prop_data.sh save FILE URI      copy FILE to URI, unless it holds fewer
#                                   entries than the backup (both only grow)
#
# Restore fails on any error except a missing file, so an S3 hiccup can't start a
# new file that the save would then write over the real one.
set -euo pipefail

cmd="${1:-}"
file="${2:?file}"
uri="${3:?s3 uri}"

# Entries: lines of a JSON-lines file, keys of a JSON object.
count() {
    # A downloaded backup has a temporary name; use the original file's format.
    case "${2:-$1}" in
    *.jsonl) grep -c . "$1" || true ;;
    *) python3 -c 'import json, sys; print(len(json.load(open(sys.argv[1]))))' "$1" ;;
    esac
}

case "$cmd" in
restore)
    mkdir -p "$(dirname "$file")"
    if out=$(aws s3 cp "$uri" "$file" --only-show-errors 2>&1); then
        echo "Restored $file: $(count "$file") entries."
    elif grep -qE "\(404\)|does not exist|Not Found" <<<"$out"; then
        echo "No saved $file yet; starting a new one."
    else
        echo "::error::Can't read $uri: $out" >&2
        exit 1
    fi
    ;;
save)
    [ -f "$file" ] || { echo "No $file to save."; exit 0; }
    tmp=$(mktemp)
    if aws s3 cp "$uri" "$tmp" --only-show-errors 2>/dev/null; then
        before=$(count "$tmp" "$file")
        after=$(count "$file")
        if [ "$after" -lt "$before" ]; then
            echo "::error::Not saving $file: $after entries, the backup has $before." >&2
            rm -f "$tmp"
            exit 1
        fi
    fi
    rm -f "$tmp"
    aws s3 cp "$file" "$uri" --only-show-errors
    echo "Saved $file: $(count "$file") entries."
    ;;
*)
    echo "usage: $0 restore|save FILE URI" >&2
    exit 2
    ;;
esac
