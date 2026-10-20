"""Mocked GitHub transport; no tokens or network required."""

import json
from types import SimpleNamespace

import pytest

from prometheus.execution.notify import NoRedirect, github_issue


def row():
    return {
        "fills": [{"count_fp": "2"}, {"count_fp": "1"}],
        "actual_cost": "1.77",
        "actual_fees": ".04",
        "execution_probability": ".750012",
        "execution_net_edge": ".120001",
        "environment": "demo",
        "request": {"ticker": "EVENT-A"},
        "sizing": {"bankroll_usd": "SECRET-BALANCE"},
        "alert": {
            "teams": ["A", "B"],
            "backed_team": "A",
            "event_ticker": "KXLOLGAME-EVENT",
            "start": "2026-10-16T12:00Z",
        },
    }


@pytest.mark.parametrize("status", [201, 200, 401])
def test_issue_request_contents_and_status(status):
    class Response:
        def __enter__(self):
            return SimpleNamespace(status=status)

        def __exit__(self, *args):
            pass

    def open(request, timeout):
        assert request.full_url == "https://api.github.com/repos/owner/private/issues"
        assert timeout == 10 and request.method == "POST"
        headers = {k.lower(): v for k, v in request.header_items()}
        assert headers["authorization"] == "Bearer test-token"
        assert headers["accept"] == "application/vnd.github+json"
        assert headers["x-github-api-version"] == "2022-11-28"
        assert headers["user-agent"] == "prometheus-executor"
        data = json.loads(request.data)
        assert data["title"] == "Bought 3 A at 0.59"
        assert "2026-10-16 12:00 UTC" in data["body"]
        assert (
            "https://kalshi.com/markets/kxlolgame/league-of-legends-game/kxlolgame-event"
            in data["body"]
        )
        assert "0.7500" in data["body"] and "0.1200" in data["body"]
        assert "SECRET-BALANCE" not in data["body"]
        return Response()

    assert github_issue(
        "test-token", "owner/private", row(), SimpleNamespace(open=open)
    ) is (status == 201)


def test_failure_zero_fills_and_redirects_are_safe():
    def failed(*args, **kwargs):
        raise TimeoutError

    assert not github_issue(
        "token", "owner/private", row(), SimpleNamespace(open=failed)
    )
    assert not github_issue("token", "https://evil.invalid/repo", row())
    assert not github_issue("token", "owner/private", {**row(), "fills": []})
    with pytest.raises(ValueError, match="redirect"):
        NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid")
