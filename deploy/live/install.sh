#!/usr/bin/env bash
# Rerunnable root setup: live worker and CloudWatch agent; reads /etc/prometheus-live.env.
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

rpm -q amazon-cloudwatch-agent >/dev/null 2>&1 || dnf install -y amazon-cloudwatch-agent
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -s -c "file:$app/cloudwatch-agent.json"

# The first refresh syncs dependencies and fetches the database and team catalog;
# the service needs both before it can start.
systemctl start prometheus-live-refresh.service
systemctl enable --now prometheus-live-refresh.timer prometheus-live.service
