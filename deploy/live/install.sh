#!/usr/bin/env bash
# One-time setup of the live worker, run as root by the instance's user data
# (project-platform-infrastructure, ThaivPrometheusLive) after it cloned this repo
# into $APP_ROOT/app. Safe to rerun. Reads /etc/prometheus-live.env.
set -euo pipefail
# shellcheck source=/dev/null
source /etc/prometheus-live.env
app="$APP_ROOT/app/deploy/live"

# uv for the service user (it installs the pinned Python itself).
sudo -u prometheus -H bash -c 'command -v ~/.local/bin/uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh'

install -m 644 "$app/prometheus-live.service" /etc/systemd/system/
install -m 644 "$app/prometheus-live-refresh.service" /etc/systemd/system/
install -m 644 "$app/prometheus-live-refresh.timer" /etc/systemd/system/
systemctl daemon-reload

# The first refresh syncs dependencies and fetches the database and team catalog;
# the service needs both before it can start.
systemctl start prometheus-live-refresh.service
systemctl enable --now prometheus-live-refresh.timer prometheus-live.service
