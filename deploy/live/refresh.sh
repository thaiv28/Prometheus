#!/usr/bin/env bash
# The live worker's refresh (prometheus-live-refresh.timer, every 6 hours), run as
# the service user: the newest main, its dependencies, the ratings file the
# publish build leaves in the artifacts bucket and the site's team catalog. Backs
# up the live evidence first (backup.sh). Touches $APP_ROOT/restart when the code or the data
# changed, so the unit restarts the service only then.
set -euo pipefail
# shellcheck source=/dev/null
source /etc/prometheus-live.env
cd "$APP_ROOT/app"
uv="$HOME/.local/bin/uv"
before=$(git rev-parse HEAD)

bash deploy/live/backup.sh

git fetch --quiet --depth 50 origin main
git reset --quiet --hard origin/main
"$uv" sync --quiet --frozen --no-dev

mkdir -p data output
changed=$([ "$(git rev-parse HEAD)" != "$before" ] && echo 1 || echo 0)

# Ratings for FORGE and the in-game model (scripts/export_live_inputs.py, uploaded
# by the publish build): a small file, so the worker never loads the database.
aws s3 cp "s3://$ARTIFACTS_BUCKET/prometheus/live-inputs/live_inputs.json" \
  data/live_inputs.json.new --only-show-errors
if ! cmp -s data/live_inputs.json.new data/live_inputs.json; then
  mv data/live_inputs.json.new data/live_inputs.json
  changed=1
else
  rm data/live_inputs.json.new
fi

aws s3 cp "s3://$SITE_BUCKET/current/teams.json" output/teams.json.new --only-show-errors
if ! cmp -s output/teams.json.new output/teams.json; then
  mv output/teams.json.new output/teams.json
  changed=1
else
  rm output/teams.json.new
fi

if [ "$changed" = 1 ]; then touch "$APP_ROOT/restart"; fi
