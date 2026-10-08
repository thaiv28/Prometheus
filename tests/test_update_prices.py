import datetime
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "update_prices", ROOT / "scripts" / "update_prices.py"
)
update_prices = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(update_prices)

NOW = datetime.datetime(2026, 10, 6, 10, 0, tzinfo=datetime.UTC)


def _market(side, bid, ask):
    return {
        "ticker": f"KXLOLGAME-E-{side}",
        "event_ticker": "KXLOLGAME-26OCT070700SRFLY",
        "rules_primary": f"If {side} wins the Demacia Cup 2026: Shopify Rebellion vs. FlyQuest League of Legends match "
        "originally scheduled for Oct 7, 2026 at 7:00 AM EDT, then the market resolves to Yes.",
        "result": "",
        "open_time": "2026-10-05T10:00:00Z",
        "close_time": "2026-10-07T14:00:00Z",
        "volume_fp": "100",
        "yes_bid_dollars": str(bid),
        "yes_ask_dollars": str(ask),
    }


def test_run_prices_the_log_writes_site_files_and_the_alert(tmp_path):
    log_path, out, alert_path = (
        tmp_path / "predictions.json",
        tmp_path / "site",
        tmp_path / "alert.json",
    )
    entry = {
        "match_id": "m",
        "start": "2026-10-07T11:00Z",
        "matched": True,
        "method": "forge",
        "p_series": 0.566,
        "ours1": "FlyQuest",
        "ours2": "Shopify Rebellion",
        "home1": "LCS",
        "home2": "LCS",
        "event": "Demacia Cup",
        "league": "DCup",
        "data_through": "2026-10-05",
    }
    log_path.write_text(json.dumps({"matches": [entry]}))
    alert_path.write_text("stale")
    book = [_market("Shopify Rebellion", 0.35, 0.36), _market("FlyQuest", 0.64, 0.65)]
    summary = update_prices.run(
        str(log_path),
        str(out),
        str(alert_path),
        now=NOW,
        fetch=lambda: book,
        pages={"FlyQuest": "flyquest", "Shopify Rebellion": "shopify-rebellion"},
    )
    assert summary["priced"] == 1 and summary["alert"]["new"] == 1
    saved = json.loads(log_path.read_text())["matches"][0]
    assert (
        saved["market"]["ask2"] == 0.36 and saved["alert"]["side"] == 2
    )  # backs Shopify Rebellion: 43% vs 36¢
    prices = json.loads((out / "kalshi.json").read_text())
    assert prices["matches"]["m"]["p1"] == 64 and prices["at"] == "2026-10-06T10:00Z"
    assert (
        json.loads((out / "predictions.json").read_text())["matches"][0]["match_id"]
        == "m"
    )
    alert = json.loads(alert_path.read_text())
    assert (
        "**Shopify Rebellion** v FlyQuest" in alert["body"]
        and "teams/flyquest.html" in alert["body"]
    )


def test_run_without_markets_writes_no_alert(tmp_path):
    log_path, alert_path = tmp_path / "predictions.json", tmp_path / "alert.json"
    log_path.write_text(json.dumps({"matches": []}))
    assert (
        update_prices.run(
            str(log_path), str(tmp_path / "site"), str(alert_path), now=NOW, fetch=list
        )["priced"]
        == 0
    )
    assert not alert_path.exists()
