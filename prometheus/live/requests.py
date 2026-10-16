"""Bounded, opt-in public Riot probes with raw response provenance; no retries."""

import hashlib
import json
import re
import time
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# The public key lolesports.com's own frontend sends to its esports API. Used only
# to discover in-progress games (getLive); the live-stats feed needs no key.
SITE_API_KEY = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
SITE_API_HOST = "esports-api.lolesports.com"
# Kalshi's public market data (no key); used by the live service for quotes.
KALSHI_HOST = "api.elections.kalshi.com"


def utc_now():
    return datetime.now(UTC).isoformat()


def discover_events(html):
    """Inspect only embedded official EventMatch objects, without executing JS."""
    events = {}
    for match in re.finditer(r'\{"__typename":"EventMatch"', html):
        event, _ = json.JSONDecoder().raw_decode(html[match.start() :])
        events[event["id"]] = event
    return list(events.values())


def probe(url, out, count=1, interval=10, opener=None, json_body=None):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc
        not in {"lolesports.com", "feed.lolesports.com", SITE_API_HOST, KALSHI_HOST}
        or parsed.username
        or parsed.fragment
    ):
        raise ValueError("Only explicit public HTTPS Riot page/feed URLs are allowed")
    if not 1 <= count <= 12 or not 5 <= interval <= 30:
        raise ValueError("count must be 1..12; interval must be 5..30 seconds")
    if (count - 1) * interval > 120:
        raise ValueError("observation schedule exceeds 120 seconds")
    out.mkdir(parents=True, exist_ok=False)
    opener = opener or build_opener(NoRedirect())
    records = []
    for index in range(count):
        if index:
            time.sleep(interval)
        record = {"url": url, "requested_at_utc": utc_now(), "sequence": index}
        if json_body is not None:
            record["method"] = "POST"
            record["request_json"] = json_body
        started = time.monotonic()
        body = b""
        try:
            with opener.open(
                Request(
                    url,
                    data=(
                        json.dumps(json_body).encode()
                        if json_body is not None
                        else None
                    ),
                    headers={
                        "User-Agent": "lol-live-feasibility/1",
                        **(
                            {"Content-Type": "application/json"}
                            if json_body is not None or parsed.path == "/api/gql"
                            else {}
                        ),
                        **(
                            {"x-api-key": SITE_API_KEY}
                            if parsed.netloc == SITE_API_HOST
                            else {}
                        ),
                        **(
                            {
                                "apollographql-client-name": "Esports Web",
                                "apollographql-client-version": "740a2d5",
                            }
                            if parsed.path == "/api/gql"
                            else {}
                        ),
                    },
                ),
                timeout=20,
            ) as response:
                record["http_status"] = response.status
                record["headers"] = {
                    key: response.headers.get(key)
                    for key in ["Date", "Age", "Cache-Control", "Content-Type"]
                }
                body = response.read(8_000_001)
                if len(body) > 8_000_000:
                    raise ValueError("response exceeds 8 MB; saved bounded prefix")
        except HTTPError as error:
            record["http_status"] = error.code
            body = error.read(8_000_000)
            record["error"] = f"HTTP {error.code}; stopped without retry"
        except Exception as error:
            record["error"] = f"{type(error).__name__}: {error}"
        record["received_at_utc"] = utc_now()
        record["request_seconds"] = time.monotonic() - started
        raw = out / f"response_{index:03d}.bin"
        raw.write_bytes(body)
        record["raw_file"] = raw.name
        record["sha256"] = hashlib.sha256(body).hexdigest()
        try:
            payload = json.loads(body)
            if payload.get("errors"):
                record["parse_error"] = (
                    "GraphQL returned errors; inspect saved response"
                )
            frames = payload.get("frames", [])
            record["frame_count"] = len(frames)
            record["first_source_timestamp"] = (
                frames[0].get("rfc460Timestamp") if frames else None
            )
            record["last_source_timestamp"] = (
                frames[-1].get("rfc460Timestamp") if frames else None
            )
        except (ValueError, AttributeError, TypeError):
            if "lolesports.com" == parsed.netloc and not record.get("error"):
                try:
                    events = discover_events(body.decode())
                    (out / f"events_{index:03d}.json").write_text(
                        json.dumps(events, indent=2) + "\n"
                    )
                    record["event_count"] = len(events)
                    record["states"] = sorted({e.get("state", "") for e in events})
                except (ValueError, UnicodeError, KeyError) as error:
                    record["parse_error"] = str(error)
            else:
                record["parse_error"] = "not a JSON object"
        records.append(record)
        (out / "manifest.json").write_text(
            json.dumps({"no_retries": True, "records": records}, indent=2) + "\n"
        )
        if record.get("error") or record.get("parse_error"):
            break
    return records
