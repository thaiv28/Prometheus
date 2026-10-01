import pandas as pd
import pytest

from prometheus.elo import (
    _elo_table,
    calculate_game_length_elo_change,
    compute_elo_records,
    expected_score,
)


def test_equal_ratings_win_and_loss_are_symmetric():
    win = calculate_game_length_elo_change(1500, 1500, 30 * 60, 1)
    loss = calculate_game_length_elo_change(1500, 1500, 30 * 60, 0)
    assert win > 0
    assert loss == pytest.approx(-win)


def test_shorter_wins_gain_more():
    short = calculate_game_length_elo_change(1500, 1500, 20 * 60, 1)
    long = calculate_game_length_elo_change(1500, 1500, 45 * 60, 1)
    assert short > long > 0


def test_favorite_losing_drops_more_than_underdog_losing():
    favorite_loss = calculate_game_length_elo_change(1700, 1500, 30 * 60, 0)
    underdog_loss = calculate_game_length_elo_change(1500, 1700, 30 * 60, 0)
    assert favorite_loss < 0
    # A heavy underdog losing a long game can still gain a little (the loser earns
    # 1 - winner_score); either way it must lose less than the favorite does.
    assert favorite_loss < underdog_loss


def test_loss_uses_complement_of_winner_score():
    # A loss must equal the negation of the opponent's win, not the negation of
    # this team's hypothetical win.
    loss = calculate_game_length_elo_change(1600, 1500, 25 * 60, 0)
    opponent_win = calculate_game_length_elo_change(1500, 1600, 25 * 60, 1)
    assert loss == pytest.approx(-opponent_win)


def test_long_game_win_by_heavy_favorite_can_lose_elo():
    # Winner score floors at lower_bound, so a big favorite barely winning a long
    # game performs below expectation.
    assert expected_score(2000, 1500) > 0.5
    assert calculate_game_length_elo_change(2000, 1500, 60 * 60, 1) < 0


def test_long_win_beats_a_draw():
    # Even the longest win must score above 0.5 for the winner.
    assert calculate_game_length_elo_change(1500, 1500, 90 * 60, 1) > 0


def test_compute_elo_records_tracks_ratings_per_team():
    games = pd.DataFrame(
        {
            "gameid": ["g1", "g2", "g3"],
            "teamid": ["A", "A", "B"],
            "opponent_teamid": ["B", "C", "C"],
            "gamelength": [1800, 1800, 1800],
            "result": [1, 1, 0],
        }
    )
    df = compute_elo_records(
        games, calculate_game_length_elo_change, starting_elo=1500
    )

    assert len(df) == 6
    # zero-sum per game
    assert df.groupby("gameid")["elo_change"].sum().abs().max() == pytest.approx(0)

    g1_a = df[(df.gameid == "g1") & (df.teamid == "A")].iloc[0]
    g2_a = df[(df.gameid == "g2") & (df.teamid == "A")].iloc[0]
    g3_b = df[(df.gameid == "g3") & (df.teamid == "B")].iloc[0]
    g3_c = df[(df.gameid == "g3") & (df.teamid == "C")].iloc[0]
    g1_b = df[(df.gameid == "g1") & (df.teamid == "B")].iloc[0]
    g2_c = df[(df.gameid == "g2") & (df.teamid == "C")].iloc[0]

    # each team's pre-match rating carries over from its previous game
    assert g1_a.pre_match_elo == 1500
    assert g2_a.pre_match_elo == pytest.approx(g1_a.post_match_elo)
    assert g3_b.pre_match_elo == pytest.approx(g1_b.post_match_elo)
    assert g3_c.pre_match_elo == pytest.approx(g2_c.post_match_elo)
    # A beat B, so A's second game starts above B's
    assert g2_a.pre_match_elo > g3_b.pre_match_elo


def test_unknown_method_rejected():
    with pytest.raises(ValueError):
        _elo_table("game_length_elo; DROP TABLE matches")
