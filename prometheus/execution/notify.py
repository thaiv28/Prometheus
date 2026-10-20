"""Best-effort private fill issues; credentials and response bodies stay private."""

import datetime as dt
import json
import re
import urllib.request
from decimal import Decimal


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("github_redirect_refused")


def github_issue(token, repo, row, opener=None):
    """Post only to api.github.com; callers persist successful notification state."""
    try:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            return False
        count = sum((Decimal(str(f["count_fp"])) for f in row["fills"]), Decimal(0))
        if count <= 0:
            return False
        average = Decimal(row["actual_cost"]) / count
        alert = row["alert"]
        start = dt.datetime.fromisoformat(
            alert["start"].replace("Z", "+00:00")
        ).astimezone(dt.UTC)
        payload = {
            "title": f"Bought {count} {alert['backed_team']} at {average:.2f}",
            "body": "\n".join(
                [
                    f"{' vs '.join(alert['teams'])} — {start:%Y-%m-%d %H:%M} UTC",
                    "https://kalshi.com/markets/kxlolgame/league-of-legends-game/"
                    + alert["event_ticker"].lower(),
                    f"Contracts: {count}",
                    f"Average price: {average:.2f}",
                    f"Fees: ${Decimal(row['actual_fees']):.4f}",
                    f"Execution probability: {Decimal(row['execution_probability']):.4f}",
                    f"Net edge: {Decimal(row['execution_net_edge']):.4f}",
                    f"Environment: {row['environment']}",
                    f"Ticker: {row['request']['ticker']}",
                ]
            ),
        }
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/issues",
            data=json.dumps(payload).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "prometheus-executor",
                "Content-Type": "application/json",
            },
        )
        transport = opener or urllib.request.build_opener(NoRedirect())
        with transport.open(request, timeout=10) as response:
            return response.status == 201
    except Exception:
        return False
