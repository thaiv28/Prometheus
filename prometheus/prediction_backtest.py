"""Current-model copies of reconstructed calls; never edits the saved log."""

import copy
import os

from prometheus import markets, regional_calibration, schedule


def rebuild(log, states, before=None):
    before = before if before is not None else schedule.RatingsBefore(states)
    out = {}
    for mid, saved in log.items():
        if not saved.get("reconstructed") or not saved.get("matched"):
            out[mid] = saved
            continue
        entry = copy.deepcopy(saved)
        start = markets._parse_start(entry["start"])

        def call(at, entry=entry, start=start):
            ratings = before(at.date())
            names = [entry.get(f"ours{i}") for i in (1, 2)]
            if not all(name in ratings.index for name in names):
                return None
            a, b = (ratings.loc[name] for name in names)
            p, method = schedule.game_probability(
                a,
                b,
                at=at,
                event=entry.get("league"),
                title=entry.get("event", ""),
                event_day=start,
            )
            return (
                p,
                schedule.series_probability(
                    p, entry["best_of"], schedule.series_rho(a.league, b.league)
                ),
                method,
                a.league,
                b.league,
            )

        forecast = call(start.replace(hour=0, minute=0))
        if forecast is None:
            entry["matched"] = False
        else:
            p, ps, method, home1, home2 = forecast
            entry.update(
                p_game=round(p, 4),
                p_series=round(ps, 4),
                method=method,
                home1=home1,
                home2=home2,
            )
            entry.pop("calibration", None)
            if (
                os.environ.get("REGIONAL_CALIBRATION", "1") != "0"
                and home1 != home2
                and regional_calibration.eligible(
                    entry.get("league"), entry.get("event", ""), start
                )
            ):
                model = regional_calibration.snapshot(
                    start.date(),
                    regional_calibration.event_code(
                        entry.get("league"), entry.get("event", "")
                    ),
                    start,
                )
                if model is not None:
                    entry["calibration"] = {
                        "version": regional_calibration.VERSION,
                        "model": model["available_from"],
                        "trained_through": model["trained_through"],
                    }
            if entry.get("market_12h"):
                early = call(start - markets.BET_LEAD)
                entry["market_12h"]["ours"] = round(early[1], 4) if early else None
        out[mid] = entry
    return out
