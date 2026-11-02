#!/usr/bin/env bash
set -euo pipefail

GAMES=(cs2:cs2-model valorant:valorant-model dota2:dota2-model)

[[ "${1:-}" == restore ]] || { echo "Usage: $0 restore" >&2; exit 2; }
restored=()
if staging=$(mktemp -d); then
  trap 'rm -rf "$staging"' EXIT
  if mkdir -p data/games; then
    for entry in "${GAMES[@]}"; do
      slug=${entry%%:*}
      prefix=${entry#*:}
      if aws s3 cp "s3://${DATA_BACKUP_BUCKET:-}/$prefix/feed/$slug.json.gz" "$staging/feed.gz" --only-show-errors 2>"$staging/error"; then
        if gunzip -c "$staging/feed.gz" > "$staging/feed.json" && mv "$staging/feed.json" "data/games/$slug.json"; then
          restored+=("$slug")
        else
          echo "::warning::Game feeds: could not unpack $slug; skipping."
        fi
      elif grep -qE '404|NoSuchKey|Not Found' "$staging/error"; then
        echo "Game feeds: $slug has no export yet; skipping."
      else
        echo "::warning::Game feeds: could not restore $slug; skipping."
        cat "$staging/error" >&2
      fi
    done
  else
    echo "::warning::Game feeds: could not create data/games; skipping."
  fi
else
  echo "::warning::Game feeds: could not create temporary directory; skipping."
fi
summary="Game feeds restored: ${restored[*]:-none}"
echo "$summary"
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then echo "$summary" >> "$GITHUB_STEP_SUMMARY" || true; fi
