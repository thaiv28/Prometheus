import pandas as pd
import pytest

from prometheus.elo import (
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
    df, offsets = compute_elo_records(
        games, calculate_game_length_elo_change, starting_elo=1500
    )
    # Without a league column there are no league offsets.
    assert offsets.empty

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


def _league_games():
    # A (LCK) and B (LCK) play at home; C (LCS) plays at home; then A beats C at
    # Worlds; then a new LCK team D debuts against B.
    return pd.DataFrame(
        {
            "gameid": ["g1", "g2", "g3", "g4"],
            "teamid": ["A", "C", "A", "B"],
            "opponent_teamid": ["B", "E", "C", "D"],
            "gamelength": [1800] * 4,
            "result": [1, 1, 1, 1],
            "league": ["LCK", "LCS", "Worlds", "LCK"],
            "date": ["2024-06-01", "2024-06-01", "2024-10-01", "2024-12-01"],
        }
    )


def _row(df, gameid, teamid):
    return df[(df.gameid == gameid) & (df.teamid == teamid)].iloc[0]


def test_international_win_lifts_the_whole_league():
    df, offsets = compute_elo_records(
        _league_games(), calculate_game_length_elo_change, league_share=0.5
    )
    worlds_a = _row(df, "g3", "A")
    worlds_c = _row(df, "g3", "C")
    a_own_change = worlds_a.elo_change / 1.5

    # A's league offset moved by half of A's own change, and C's the other way.
    assert worlds_a.league_offset == pytest.approx(0.5 * a_own_change)
    assert worlds_c.league_offset == pytest.approx(-0.5 * a_own_change)
    assert worlds_a.elo_change == pytest.approx(-worlds_c.elo_change)
    assert set(offsets["league"]) == {"LCK", "LCS"}
    assert offsets["date"].tolist() == ["2024-10-01", "2024-10-01"]

    # B stayed home but enters its next game with LCK's new offset.
    b_after_g1 = _row(df, "g1", "B").post_match_elo
    assert _row(df, "g4", "B").pre_match_elo == pytest.approx(
        b_after_g1 + worlds_a.league_offset
    )


def test_new_team_starts_at_its_league_average():
    df, _ = compute_elo_records(
        _league_games(), calculate_game_length_elo_change, league_share=0.5
    )
    lck_offset = _row(df, "g3", "A").league_offset
    assert lck_offset > 0
    # Without rosters a team plays as one "player": D starts at the average current
    # rating of LCK's active teams, A (after Worlds) and B (plus LCK's new offset).
    a_now = _row(df, "g3", "A").post_match_elo
    b_now = _row(df, "g1", "B").post_match_elo + lck_offset
    assert _row(df, "g4", "D").pre_match_elo == pytest.approx((a_now + b_now) / 2)
    assert _row(df, "g4", "D").home_league == "LCK"


def _five(prefix):
    return tuple(f"{prefix}{i}" for i in range(5))


def test_stable_rosters_match_team_elo():
    games = pd.DataFrame(
        {
            "gameid": ["g1", "g2", "g3"],
            "teamid": ["A", "A", "B"],
            "opponent_teamid": ["B", "C", "C"],
            "gamelength": [1500, 2400, 1800],
            "result": [1, 0, 1],
        }
    )
    rosters = {(g, t): _five(t) for g, t, o in zip(games.gameid, games.teamid, games.opponent_teamid)}
    rosters.update({(g, o): _five(o) for g, o in zip(games.gameid, games.opponent_teamid)})
    team, _ = compute_elo_records(games, calculate_game_length_elo_change)
    player, _ = compute_elo_records(games, calculate_game_length_elo_change, rosters=rosters)
    pd.testing.assert_frame_equal(team, player)


def test_transfer_carries_the_players_rating():
    # A beats B twice, then A's star a0 joins B in place of b0.
    games = pd.DataFrame(
        {
            "gameid": ["g1", "g2", "g3"],
            "teamid": ["A", "A", "A"],
            "opponent_teamid": ["B", "B", "B"],
            "gamelength": [1800] * 3,
            "result": [1, 1, 1],
        }
    )
    b_after = ("a0",) + _five("b")[1:]
    rosters = {
        ("g1", "A"): _five("a"), ("g1", "B"): _five("b"),
        ("g2", "A"): _five("a"), ("g2", "B"): _five("b"),
        ("g3", "A"): ("x0",) + _five("a")[1:], ("g3", "B"): b_after,
    }
    df, _ = compute_elo_records(games, calculate_game_length_elo_change, rosters=rosters)
    gain = _row(df, "g2", "A").post_match_elo - 1500
    # B swaps one 1500 - gain player for a 1500 + gain one: up by 2 * gain / 5.
    b_before = _row(df, "g2", "B").post_match_elo
    assert _row(df, "g3", "B").pre_match_elo == pytest.approx(b_before + 2 * gain / 5)
    # A loses a0; the newcomer x0 starts at the average of the 10 active players (1500).
    assert _row(df, "g3", "A").pre_match_elo == pytest.approx((4 * (1500 + gain) + 1500) / 5)


def test_new_player_ignores_long_inactive_players():
    # 2020: A beats B. 2023: E (with A's a0) beats F. 2024: new teams C and D debut.
    games = pd.DataFrame(
        {
            "gameid": ["g1", "g2", "g3"],
            "teamid": ["A", "E", "C"],
            "opponent_teamid": ["B", "F", "D"],
            "gamelength": [1800] * 3,
            "result": [1, 1, 1],
            "league": ["LCK"] * 3,
            "date": ["2020-01-01", "2023-06-01", "2024-01-01"],
        }
    )
    rosters = {
        ("g1", "A"): _five("a"), ("g1", "B"): _five("b"),
        ("g2", "E"): ("a0", *_five("e")[1:]), ("g2", "F"): _five("f"),
        ("g3", "C"): _five("c"), ("g3", "D"): _five("d"),
    }
    df, _ = compute_elo_records(games, calculate_game_length_elo_change, rosters=rosters)
    # Only E's and F's ten players played within a year of the debut.
    active = (_row(df, "g2", "E").post_match_elo + _row(df, "g2", "F").post_match_elo) / 2
    assert active != pytest.approx(1500)
    assert _row(df, "g3", "C").pre_match_elo == pytest.approx(active)
    assert _row(df, "g3", "D").pre_match_elo == pytest.approx(active)


def test_player_records_average_to_the_team_rating():
    games = pd.DataFrame(
        {
            "gameid": ["g1", "g2"],
            "teamid": ["A", "A"],
            "opponent_teamid": ["B", "C"],
            "gamelength": [1800, 2000],
            "result": [1, 0],
            "league": ["LCK", "LCK"],
            "date": ["2024-01-01", "2024-01-08"],
        }
    )
    rosters = {
        ("g1", "A"): _five("a"), ("g1", "B"): _five("b"),
        ("g2", "A"): ("b0",) + _five("a")[1:], ("g2", "C"): _five("c"),
    }
    teams, _, players = compute_elo_records(
        games, calculate_game_length_elo_change, rosters=rosters, player_records=True
    )
    assert len(players) == 20
    for (gameid, teamid), group in players.groupby(["gameid", "teamid"]):
        team = _row(teams, gameid, teamid)
        assert group["pre_match_elo"].mean() == pytest.approx(team.pre_match_elo)
        assert group["post_match_elo"].mean() == pytest.approx(team.post_match_elo)
    # b0 lost g1 with B, then carried that rating into A's lineup.
    b0 = players[players["playerid"] == "b0"].set_index("gameid")
    assert b0.loc["g2", "pre_match_elo"] == pytest.approx(b0.loc["g1", "post_match_elo"])


def test_a_cup_keeps_the_home_league_and_main_roster():
    # A plays the LCK, then two KeSPA Cup games: one with an academy lineup, one
    # with its main roster. A then plays the LCK again.
    games = pd.DataFrame(
        {
            "gameid": ["g1", "g2", "g3", "g4", "g5"],
            "teamid": ["A", "A", "A", "A", "A"],
            "opponent_teamid": ["B", "B", "C", "C", "B"],
            "gamelength": [1800] * 5,
            "result": [1, 1, 0, 1, 1],
            "league": ["LCK", "LCK", "KeSPA Cup", "KeSPA Cup", "LCK"],
            "date": ["2024-06-01", "2024-06-02", "2024-12-01", "2024-12-02", "2025-01-10"],
        }
    )
    rosters = {(g, t): _five(t) for g, t in zip(games.gameid, games.teamid)}
    rosters.update({(g, "B"): _five("B") for g in games.gameid})
    rosters.update({(g, "C"): _five("C") for g in games.gameid})
    rosters[("g3", "A")] = _five("a")  # academy lineup under A's name
    df, _ = compute_elo_records(games, calculate_game_length_elo_change, rosters=rosters)

    # Two LCK games outweigh the cup, so A's home stays LCK through it and into 2025.
    assert [_row(df, g, "A").home_league for g in games.gameid] == ["LCK"] * 5
    # The academy game rates the academy lineup but leaves A's main rating alone.
    assert _row(df, "g3", "A").pre_match_elo != pytest.approx(_row(df, "g2", "A").post_match_elo)
    assert _row(df, "g3", "A").main_elo == pytest.approx(_row(df, "g2", "A").main_elo)
    # The main roster's cup game counts.
    assert _row(df, "g4", "A").main_elo == pytest.approx(_row(df, "g4", "A").post_match_elo)


def test_home_league_moves_to_the_most_played_league():
    games = pd.DataFrame(
        {
            "gameid": ["g1", "g2", "g3", "g4"],
            "teamid": ["A"] * 4,
            "opponent_teamid": ["B", "C", "C", "C"],
            "gamelength": [1800] * 4,
            "result": [1] * 4,
            "league": ["LCKC", "LCK", "LCK", "LCK"],
            "date": ["2024-01-01", "2024-02-01", "2024-02-02", "2024-02-03"],
        }
    )
    df, _ = compute_elo_records(games, calculate_game_length_elo_change)
    # A tie (one game each) keeps LCKC; the second LCK game moves A to the LCK.
    assert [_row(df, g, "A").home_league for g in games.gameid] == ["LCKC", "LCKC", "LCK", "LCK"]
