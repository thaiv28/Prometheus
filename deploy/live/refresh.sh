#!/usr/bin/env bash
# The live worker's refresh (prometheus-live-refresh.timer, every 6 hours), run as
# the service user: the newest main, its dependencies, the database snapshot the
# publish build leaves in the artifacts bucket and the site's team catalog. Backs
# up the live evidence first. Touches $APP_ROOT/restart when the code or the data
# changed, so the unit restarts the service only then.
set -euo pipefail
# shellcheck source=/dev/null
source /etc/prometheus-live.env
cd "$APP_ROOT/app"
uv="$HOME/.local/bin/uv"
before=$(git rev-parse HEAD)

# Finished games' archives, results and call journals, for later backtests.
if [ -d data/live ]; then
  aws s3 sync data/live "s3://$ARTIFACTS_BUCKET/prometheus/live/" --only-show-errors \
    --exclude '*' --include '*/archive.tar.gz' --include '*/results.json' \
    --include '*/calls.jsonl' --include '*/forge.json' --include '*/series_quotes.jsonl'
fi

git fetch --quiet --depth 50 origin main
git reset --quiet --hard origin/main
"$uv" sync --quiet --frozen --no-dev

mkdir -p db output
changed=$([ "$(git rev-parse HEAD)" != "$before" ] && echo 1 || echo 0)

# The database: replaced only when the snapshot's ETag moved.
snapshot="s3://$ARTIFACTS_BUCKET/prometheus/db/prometheus.db.gz"
etag=$(aws s3api head-object --bucket "$ARTIFACTS_BUCKET" --key prometheus/db/prometheus.db.gz \
  --query ETag --output text)
if [ "$etag" != "$(cat db/.snapshot-etag 2>/dev/null || true)" ]; then
  aws s3 cp "$snapshot" db/prometheus.db.gz.new --only-show-errors
  gunzip -c db/prometheus.db.gz.new > db/prometheus.db.new
  rm db/prometheus.db.gz.new
  mv db/prometheus.db.new db/prometheus.db
  echo "$etag" > db/.snapshot-etag
  changed=1
fi

aws s3 cp "s3://$SITE_BUCKET/current/teams.json" output/teams.json.new --only-show-errors
if ! cmp -s output/teams.json.new output/teams.json; then
  mv output/teams.json.new output/teams.json
  changed=1
else
  rm output/teams.json.new
fi

if [ "$changed" = 1 ]; then touch "$APP_ROOT/restart"; fi
