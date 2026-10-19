"""Best-effort finished-map uploads and debounced call refresh dispatches."""

import json
import os
import subprocess
from urllib.request import Request, urlopen

_token = None
_disabled = False
_last_dispatch = None


def log(event, **fields):
    print(json.dumps(dict(event=event, **fields)), flush=True)


def upload_maps(match_dir, match_id):
    bucket = os.environ.get("ARTIFACTS_BUCKET")
    if not bucket:
        return
    try:
        subprocess.run(
            [
                "aws",
                "s3",
                "cp",
                str(match_dir / "maps.json"),
                f"s3://{bucket}/prometheus/live/{match_id}/maps.json",
                "--only-show-errors",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except Exception as exc:
        log("maps_upload_failed", reason=str(exc))


def dispatch_prices(now):
    global _token, _disabled, _last_dispatch
    try:
        if _disabled or (
            _last_dispatch is not None and (now - _last_dispatch).total_seconds() < 300
        ):
            return
        if _token is None:
            try:
                _token = (
                    os.environ.get("PRICES_DISPATCH_TOKEN")
                    or subprocess.run(
                        [
                            "aws",
                            "ssm",
                            "get-parameter",
                            "--name",
                            os.environ.get(
                                "PRICES_DISPATCH_PARAMETER",
                                "/thaiv/prometheus/live/prices-dispatch-token",
                            ),
                            "--with-decryption",
                            "--query",
                            "Parameter.Value",
                            "--output",
                            "text",
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=15,
                    ).stdout.strip()
                )
                if not _token:
                    raise ValueError("empty dispatch token")
            except Exception as exc:
                _disabled = True
                log("dispatch_disabled", reason=str(exc))
                return
        repo = os.environ.get("REPOSITORY", "thaiv28/Prometheus").rstrip("/")
        repo = repo.removeprefix("https://github.com/").removeprefix(
            "http://github.com/"
        )
        repo = repo.removeprefix("git@github.com:").removesuffix(".git")
        request = Request(
            f"https://api.github.com/repos/{repo}/actions/workflows/prices.yml/dispatches",
            data=json.dumps({"ref": "main"}).encode(),
            headers={
                "Authorization": f"Bearer {_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "prometheus-live",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        _last_dispatch = now
        with urlopen(request, timeout=15) as response:
            if response.status != 204:
                raise ValueError(f"HTTP {response.status}")
        log("dispatched")
    except Exception as exc:
        log("dispatch_failed", reason=str(exc))
