"""Best-effort private fill issues; credentials and response bodies stay private."""

import datetime as dt
import json
import re
import urllib.request
from decimal import Decimal

from prometheus.alert_contract import GAMES


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
        market_path = "kxlolgame/league-of-legends-game"
        if alert.get("game") in {"cs2", "valorant"}:
            market_path = GAMES[alert["game"]]["series"].lower()
        payload = {
            "title": f"Bought {count} {alert['backed_team']} at {average:.2f}",
            "body": "\n".join(
                [
                    f"{' vs '.join(alert['teams'])} — {start:%Y-%m-%d %H:%M} UTC",
                    f"https://kalshi.com/markets/{market_path}/"
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
            if response.status == 201:
                number = json.load(response)["number"]
                return number if type(number) is int and number > 0 else False
            return False
    except Exception:
        return False


def close_issue(token, repo, row, opener=None) -> bool:
    """Comment and close a settled fill issue; failures never affect trading."""
    try:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            return False
        transport = opener or urllib.request.build_opener(NoRedirect())
        base = f"https://api.github.com/repos/{repo}/issues"

        def request(url, method="GET", payload=None):
            return urllib.request.Request(
                url,
                data=json.dumps(payload).encode() if payload is not None else None,
                method=method,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "prometheus-executor",
                    "Content-Type": "application/json",
                },
            )

        number = row.get("issue")
        if not number:
            matches = []
            required = {
                f"Ticker: {row['request']['ticker']}",
                f"Environment: {row['environment']}",
            }
            for page in range(1, 4):
                with transport.open(
                    request(f"{base}?state=open&per_page=100&page={page}"), timeout=10
                ) as response:
                    if response.status != 200:
                        return False
                    issues = json.load(response)
                for issue in issues:
                    if "pull_request" not in issue and required.issubset(
                        (issue.get("body") or "").splitlines()
                    ):
                        matches.append(issue["number"])
                if len(matches) > 1:
                    return False
                if len(issues) < 100:
                    break
            if len(matches) != 1:
                return False
            number = matches[0]
        if type(number) is not int or number <= 0:
            return False
        profit = Decimal(str(row["realized_profit"]))
        result = "won" if profit > 0 else "lost" if profit < 0 else "even"
        with transport.open(
            request(
                f"{base}/{number}/comments",
                "POST",
                {"body": f"Settled: {result}, P&L ${profit:.2f}"},
            ),
            timeout=10,
        ) as response:
            if response.status != 201:
                return False
        with transport.open(
            request(
                f"{base}/{number}",
                "PATCH",
                {"state": "closed", "state_reason": "completed"},
            ),
            timeout=10,
        ) as response:
            return response.status == 200
    except Exception:
        return False
