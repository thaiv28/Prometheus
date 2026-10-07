import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

from prometheus import aura

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location(
    "evaluate_aura", ROOT / "scripts" / "evaluate_aura.py"
)
evaluate_aura = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evaluate_aura)
SCORE = evaluate_aura.CHOSEN
K = evaluate_aura.SHRINK_GAMES


def _lineup(team, game, date, players, score, result, league="LCK"):
    return [
        {
            "gameid": game,
            "teamid": team,
            "position": role,
            "playerid": pid,
            "date": date,
            "league": league,
            "result": result,
            SCORE: score.get(pid, 0.0),
            "gold15": 0.0,
        }
        for role, pid in zip(aura.ROLES, players)
    ]


def test_substitution_compares_incoming_so_far_with_outgoing():
    a = [f"a_{r}" for r in aura.ROLES]
    b = [f"b_{r}" for r in aura.ROLES]
    c = [f"c_{r}" for r in aura.ROLES]
    with_sub = a[:2] + ["sub"] + a[3:]
    rows = _lineup(
        "C", "g0", "2024-01-01", ["sub"] + c[1:], {"sub": 2.0}, 1
    )  # the sub's earlier game elsewhere
    rows += _lineup("D", "g0", "2024-01-01", b, {}, 0)
    for i, date in ((1, "2024-01-02"), (2, "2024-01-03")):
        rows += _lineup("A", f"g{i}", date, a, {"a_mid": 1.0}, 1) + _lineup(
            "B", f"g{i}", date, b, {}, 0
        )
    rows += _lineup("A", "g3", "2024-01-04", with_sub, {}, 0) + _lineup(
        "B", "g3", "2024-01-04", b, {}, 1
    )
    elos = pd.DataFrame(
        {"gameid": ["g3"], "teamid": ["A"], "elo": [1500.0], "opp_elo": [1500.0]}
    )

    subs = evaluate_aura.substitutions(pd.DataFrame(rows), elos)

    assert subs["gameid"].tolist() == [
        "g3"
    ]  # first games and unchanged lineups don't count
    # The sub's one earlier game (2.0) against the outgoing mid's two games (1.0 each), both shrunk.
    assert subs["aura_diff"].iat[0] == pytest.approx(2.0 / (1 + K) - 2.0 / (2 + K))
    assert subs["in_games"].iat[0] == 1 and subs["out_games"].iat[0] == 2
    assert subs["surprise"].iat[0] == pytest.approx(-0.5)


def test_roster_uses_each_players_other_half():
    rows = []
    t_first = [f"t{i}" for i in range(1, 6)]
    t_second = [
        "t1",
        "t2",
        "t3",
        "t4",
        "t6",
    ]  # t5 replaced by t6, who has no first-half games
    u = [f"u{i}" for i in range(1, 6)]
    for half, t_players, t_score in ((0, t_first, 1.0), (1, t_second, 0.0)):
        for g in range(evaluate_aura.MIN_HALF_GAMES):
            game = f"h{half}g{g}"
            for team, players, score, win in (
                ("T", t_players, t_score, 1.0),
                ("U", u, 0.0, 0.0),
            ):
                for role, pid in zip(aura.ROLES, players):
                    rows.append(
                        {
                            "playerid": pid,
                            "year": 2024,
                            "position": role,
                            "gameid": game,
                            "teamid": team,
                            "teamname": team,
                            "half": half,
                            SCORE: score,
                            "win": win,
                        }
                    )
    table = evaluate_aura.roster_table(pd.DataFrame(rows)).set_index(
        ["teamname", "half"]
    )

    # Second half: t1-t4's first-half AURA (10 games of 1.0, shrunk), t6 counts as average.
    roster = 4 * 10 / (10 + K)
    assert table.loc[("T", 1), "roster"] == pytest.approx(
        roster / 2
    )  # centred against U's 0
    assert table.loc[("T", 1), "team"] == pytest.approx(5 / 2)
    # First half: the second half's players all scored 0, and t5 never played there.
    assert table.loc[("T", 0), "roster"] == pytest.approx(0)
