"""Mocked GitHub transport; no tokens or network required."""

import io
import json
from types import SimpleNamespace

import pytest

from prometheus.execution.notify import NoRedirect, close_issue, github_issue


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
            return SimpleNamespace(status=status, read=lambda: b'{"number": 42}')

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
    ) == (42 if status == 201 else False)


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


class Response(io.BytesIO):
    def __init__(self, status, payload=None):
        super().__init__(json.dumps(payload).encode())
        self.status = status


@pytest.mark.parametrize(
    "game,series",
    [
        ("cs2", "kxcs2game/counter-strike-2-game"),
        ("valorant", "kxvalorantgame/valorant-game-winner"),
    ],
)
def test_game_issue_link(game, series):
    saved = row()
    saved["alert"].update(game=game, event_ticker="EVENT-ABC")

    def open(request, timeout):
        assert (
            f"https://kalshi.com/markets/{series}/event-abc"
            in json.loads(request.data)["body"]
        )
        return Response(201, {"number": 42})

    assert (
        github_issue("token", "owner/private", saved, SimpleNamespace(open=open)) == 42
    )


@pytest.mark.parametrize(
    "profit,result", [("1.234", "won"), ("-1.234", "lost"), ("0", "even")]
)
@pytest.mark.parametrize("patch_status", [200, 500])
def test_close_result_comment_and_patch(profit, result, patch_status):
    calls = []

    def open(request, timeout):
        calls.append(request.method)
        assert timeout == 10
        assert request.full_url.startswith(
            "https://api.github.com/repos/owner/private/issues/42"
        )
        assert request.get_header("Authorization") == "Bearer token"
        if request.method == "POST":
            assert json.loads(request.data) == {
                "body": f"Settled: {result}, P&L ${float(profit):.2f}"
            }
            return Response(201)
        assert json.loads(request.data) == {
            "state": "closed",
            "state_reason": "completed",
        }
        return Response(patch_status)

    assert close_issue(
        "token",
        "owner/private",
        {**row(), "issue": 42, "realized_profit": profit},
        SimpleNamespace(open=open),
    ) is (patch_status == 200)
    assert calls == ["POST", "PATCH"]


@pytest.mark.parametrize("matches", [0, 1, 2])
def test_legacy_exact_lines_ignore_pull_requests_and_ambiguous_matches(matches):
    body = "Ticker: EVENT-A\nEnvironment: demo"
    issues = [
        {"number": 1, "body": body, "pull_request": {}},
        {"number": 2, "body": body + "-other"},
        {"number": 3, "body": "Ticker: EVENT-AB\nEnvironment: demo"},
        *[{"number": 42 + i, "body": body} for i in range(matches)],
    ]
    calls = []

    def open(request, timeout):
        calls.append(request.method)
        if request.method == "GET":
            assert request.full_url.endswith("?state=open&per_page=100&page=1")
            return Response(200, issues)
        return Response(201 if request.method == "POST" else 200)

    assert close_issue(
        "token",
        "owner/private",
        {**row(), "realized_profit": "0"},
        SimpleNamespace(open=open),
    ) is (matches == 1)
    assert calls == (["GET", "POST", "PATCH"] if matches == 1 else ["GET"])


def test_legacy_pagination_bounded_to_three_pages():
    calls = []

    def open(request, timeout):
        calls.append(request.full_url)
        assert request.method == "GET"
        return Response(200, [{"number": i, "body": "unrelated"} for i in range(100)])

    assert not close_issue("token", "owner/private", row(), SimpleNamespace(open=open))
    assert len(calls) == 3 and calls[-1].endswith("page=3")


def test_close_transport_failure_and_invalid_repo_are_safe():
    def failed(*args, **kwargs):
        raise TimeoutError

    assert not close_issue(
        "token", "owner/private", row(), SimpleNamespace(open=failed)
    )
    assert not close_issue("token", "https://evil.invalid/repo", row())
