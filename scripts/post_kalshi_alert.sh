#!/usr/bin/env bash
# Post the alert written by build_site.py or update_prices.py (data/kalshi_alert.json)
# as the day's `kalshi-alert` GitHub issue. Needs `gh` with GH_TOKEN and GH_REPO.
#
# - No issue for the day yet: close earlier alert issues, then create today's
#   (creating it sends GitHub's notification email with every match in the body).
# - Today's issue exists: update its title and body in place (no email), and add
#   a comment listing matches new since the last run (comments are emailed).
set -euo pipefail

file="${1:-data/kalshi_alert.json}"
if [ ! -f "$file" ]; then
    echo "No alert to post."
    exit 0
fi
tmp="$(mktemp -d)"
title="$(jq -r .title "$file")"
day="$(jq -r .day "$file")"
jq -r .body "$file" > "$tmp/body.md"
jq -r '.comment // empty' "$file" > "$tmp/comment.md"

gh label create kalshi-alert --color 2342a0 --description "FORGE vs Kalshi daily edges" 2>/dev/null || true
open="$(gh issue list --label kalshi-alert --state open --limit 50 --json number,title)"
today="$(jq -r --arg d "$day" '.[] | select(.title | startswith($d)) | .number' <<<"$open" | head -1)"

if [ -n "$today" ]; then
    gh issue edit "$today" --title "$title" --body-file "$tmp/body.md"
    if [ -s "$tmp/comment.md" ]; then
        gh issue comment "$today" --body-file "$tmp/comment.md"
    fi
    echo "Updated issue #$today."
    exit 0
fi
for n in $(jq -r '.[].number' <<<"$open"); do
    gh issue close "$n" --comment "Superseded by today's alert."
done
gh issue create --title "$title" --body-file "$tmp/body.md" --label kalshi-alert
