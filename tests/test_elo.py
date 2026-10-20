import numpy as np
import pandas as pd
import pytest

from prometheus import elo
from prometheus.elo import (
    calculate_game_length_elo_change,
    expected_score,
)

# Disable RD, slope overrides, discounts and league-move bonuses to isolate mechanisms.
OFF = {
    "player_rd": None,
    "other_league_slope": None,
    "rookie_penalty": 0,
    "rookie_games": 0,
    "move_down_bonus": 0.0,
}


def compute_elo_records(games, *args, **kwargs):
    return elo.compute_elo_records(games, *args, **{**OFF, **kwargs})


def test_duration_curve_has_frozen_midpoint_and_transition():
    # Guard the approved evidence curve, including vector/scalar parity.
    lengths = np.array([1200, 1500, 1800, 2100, 2400])
    expected = [0.9937048265, 0.9582789773, 0.825, 0.6917210227, 0.6562951735]
    np.testing.assert_allclose(elo.winner_score(lengths), expected, atol=1e-9)
    assert elo.winner_score(1800) == pytest.approx(0.825)
    assert elo.winner_score(1500) + elo.winner_score(2100) == pytest.approx(1.65)
    with pytest.raises(ValueError, match="positive"):
        elo.winner_score(1800, transition=0)


def test_original_curve_remains_explicit_for_season_stats_and_research():
    assert elo.power_winner_score(1200) == pytest.approx(0.92)
    assert elo.winner_score(1200, steepness=3) == pytest.approx(0.92)
    assert elo.winner_score(1200) > elo.power_winner_score(1200)


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
    rosters = {
        (g, t): _five(t)
        for g, t, o in zip(games.gameid, games.teamid, games.opponent_teamid)
    }
    rosters.update(
        {(g, o): _five(o) for g, o in zip(games.gameid, games.opponent_teamid)}
    )
    team, _ = compute_elo_records(games, calculate_game_length_elo_change)
    player, _ = compute_elo_records(
        games, calculate_game_length_elo_change, rosters=rosters
    )
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
        ("g1", "A"): _five("a"),
        ("g1", "B"): _five("b"),
        ("g2", "A"): _five("a"),
        ("g2", "B"): _five("b"),
        ("g3", "A"): ("x0",) + _five("a")[1:],
        ("g3", "B"): b_after,
    }
    df, _ = compute_elo_records(
        games, calculate_game_length_elo_change, rosters=rosters
    )
    gain = _row(df, "g2", "A").post_match_elo - 1500
    # B swaps one 1500 - gain player for a 1500 + gain one: up by 2 * gain / 5.
    b_before = _row(df, "g2", "B").post_match_elo
    assert _row(df, "g3", "B").pre_match_elo == pytest.approx(b_before + 2 * gain / 5)
    # A loses a0; the newcomer x0 starts at the average of the 10 active players (1500).
    assert _row(df, "g3", "A").pre_match_elo == pytest.approx(
        (4 * (1500 + gain) + 1500) / 5
    )


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
        ("g1", "A"): _five("a"),
        ("g1", "B"): _five("b"),
        ("g2", "E"): ("a0", *_five("e")[1:]),
        ("g2", "F"): _five("f"),
        ("g3", "C"): _five("c"),
        ("g3", "D"): _five("d"),
    }
    df, _ = compute_elo_records(
        games, calculate_game_length_elo_change, rosters=rosters
    )
    # Only E's and F's ten players played within a year of the debut.
    active = (
        _row(df, "g2", "E").post_match_elo + _row(df, "g2", "F").post_match_elo
    ) / 2
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
        ("g1", "A"): _five("a"),
        ("g1", "B"): _five("b"),
        ("g2", "A"): ("b0",) + _five("a")[1:],
        ("g2", "C"): _five("c"),
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
    assert b0.loc["g2", "pre_match_elo"] == pytest.approx(
        b0.loc["g1", "post_match_elo"]
    )


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
            "date": [
                "2024-06-01",
                "2024-06-02",
                "2024-12-01",
                "2024-12-02",
                "2025-01-10",
            ],
        }
    )
    rosters = {(g, t): _five(t) for g, t in zip(games.gameid, games.teamid)}
    rosters.update({(g, "B"): _five("B") for g in games.gameid})
    rosters.update({(g, "C"): _five("C") for g in games.gameid})
    rosters[("g3", "A")] = _five("a")  # academy lineup under A's name
    # Isolate roster selection from cross-league link and transfer evidence.
    df, _ = compute_elo_records(
        games,
        calculate_game_length_elo_change,
        rosters=rosters,
        link_share=0,
        transfer_share=0,
    )

    # Two LCK games outweigh the cup, so A's home stays LCK through it and into 2025.
    assert [_row(df, g, "A").home_league for g in games.gameid] == ["LCK"] * 5
    # The academy game rates the academy lineup but leaves A's main rating alone.
    assert _row(df, "g3", "A").pre_match_elo != pytest.approx(
        _row(df, "g2", "A").post_match_elo
    )
    assert _row(df, "g3", "A").main_elo == pytest.approx(_row(df, "g2", "A").main_elo)
    # The main roster's cup game counts.
    assert _row(df, "g4", "A").main_elo == pytest.approx(
        _row(df, "g4", "A").post_match_elo
    )


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
    assert [_row(df, g, "A").home_league for g in games.gameid] == [
        "LCKC",
        "LCKC",
        "LCK",
        "LCK",
    ]


def _two_games():
    # A beats B, then A (with newcomer x0 for a0) plays B again.
    games = pd.DataFrame(
        {
            "gameid": ["g1", "g2"],
            "teamid": ["A", "A"],
            "opponent_teamid": ["B", "B"],
            "gamelength": [1800] * 2,
            "result": [1, 1],
            "league": ["LCK"] * 2,
            "date": ["2026-01-01", "2026-01-02"],
        }
    )
    rosters = {
        ("g1", "A"): _five("a"),
        ("g1", "B"): _five("b"),
        ("g2", "A"): ("x0",) + _five("a")[1:],
        ("g2", "B"): _five("b"),
    }
    return games, rosters


def test_rookie_discount_fades_and_is_not_stored():
    games, rosters = _two_games()
    base, _ = compute_elo_records(
        games, calculate_game_length_elo_change, rosters=rosters
    )
    disc, _ = compute_elo_records(
        games,
        calculate_game_length_elo_change,
        rosters=rosters,
        rookie_penalty=100,
        rookie_games=3,
    )
    # First game: every player counts 100 lower, so the game itself is unchanged
    # (the team's rating change also shows the discount halving, 100 to 50).
    assert _row(disc, "g1", "A").pre_match_elo == pytest.approx(1400)
    assert _row(disc, "g1", "A").elo_change - 50 == pytest.approx(
        _row(base, "g1", "A").elo_change
    )
    # g2: A's veterans are half way (50 off), x0 is new (100 off), B's all 50 off.
    # x0 is seated at the active average, which the discount doesn't lower.
    a2 = _row(disc, "g2", "A").pre_match_elo
    b2 = _row(disc, "g2", "B").pre_match_elo
    assert a2 == pytest.approx(_row(base, "g2", "A").pre_match_elo - (4 * 50 + 100) / 5)
    assert b2 == pytest.approx(_row(base, "g2", "B").pre_match_elo - 50)


def test_published_defaults_discount_rookies():
    games, rosters = _two_games()
    df, _ = elo.compute_elo_records(
        games, calculate_game_length_elo_change, rosters=rosters
    )
    # Everyone is new in g1: counted ROOKIE_PENALTY below the 1500 start.
    assert _row(df, "g1", "A").pre_match_elo == pytest.approx(1500 - elo.ROOKIE_PENALTY)


def _move_games(first_league, second_league):
    # C plays D in `first_league`; then c0 starts for A against B in `second_league`
    # twice.
    games = pd.DataFrame(
        {
            "gameid": ["g1", "g2", "g3"],
            "teamid": ["C", "A", "A"],
            "opponent_teamid": ["D", "B", "B"],
            "gamelength": [1800] * 3,
            "result": [1, 1, 1],
            "league": [first_league, second_league, second_league],
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
        }
    )
    rosters = {
        ("g1", "C"): _five("c"),
        ("g1", "D"): _five("d"),
        ("g2", "A"): ("c0",) + _five("a")[1:],
        ("g2", "B"): _five("b"),
        ("g3", "A"): ("c0",) + _five("a")[1:],
        ("g3", "B"): _five("b"),
    }
    return games, rosters


@pytest.mark.parametrize(
    "first, second, expected",
    [("LCKC", "LCK", 0), ("LCK", "LCKC", 30), ("LCKC", "LFL", 0), ("LEC", "LCK", 0)],
)
def test_league_move_adjustment_by_direction(first, second, expected):
    games, rosters = _move_games(first, second)
    base, _ = compute_elo_records(
        games, calculate_game_length_elo_change, rosters=rosters
    )
    moved, _ = compute_elo_records(
        games,
        calculate_game_length_elo_change,
        rosters=rosters,
        move_down_bonus=30,
    )
    diff = _row(moved, "g2", "A").pre_match_elo - _row(base, "g2", "A").pre_match_elo
    assert diff == pytest.approx(expected / 5)
    # Stored in c0's rating: still there a game later (less the game's own change).
    diff3 = _row(moved, "g3", "A").pre_match_elo - _row(base, "g3", "A").pre_match_elo
    assert diff3 == pytest.approx(expected / 5, abs=1)


def test_log_rookie_curve_falls_with_log_games():
    games, rosters = _two_games()
    base, _ = compute_elo_records(
        games, calculate_game_length_elo_change, rosters=rosters
    )
    disc, _ = compute_elo_records(
        games,
        calculate_game_length_elo_change,
        rosters=rosters,
        rookie_penalty=100,
        rookie_games=3,
    )
    # First game: the full 100. g2: veterans have 1 game, 100 × (1 − log 2 / log 4)
    # = 50 off; x0 is new (100 off).
    assert _row(disc, "g1", "A").pre_match_elo == pytest.approx(1400)
    a2 = _row(disc, "g2", "A").pre_match_elo
    assert a2 == pytest.approx(_row(base, "g2", "A").pre_match_elo - (4 * 50 + 100) / 5)


def test_published_defaults_use_rd_and_the_move_down_bonus():
    games, rosters = _two_games()
    published, _ = elo.compute_elo_records(
        games, calculate_game_length_elo_change, rosters=rosters
    )
    explicit, _ = elo.compute_elo_records(
        games,
        calculate_game_length_elo_change,
        rosters=rosters,
        player_rd=elo.PLAYER_RD,
        player_rd_information=elo.PLAYER_RD_INFORMATION,
        other_league_slope=elo.OTHER_LEAGUE_SLOPE,
        move_down_bonus=elo.MOVE_DOWN_BONUS,
    )
    pd.testing.assert_frame_equal(published, explicit)
    assert elo.MOVE_DOWN_BONUS == 25.0


@pytest.mark.parametrize("gap", [-400, -100, 0, 100, 400])
def test_expected_slope_default_preserves_original_arithmetic(gap):
    original = 1 / (1 + 10 ** (-gap / 400))
    assert expected_score(1500 + gap, 1500) == original
    assert expected_score(1500 + gap, 1500, slope=elo.EXPECTED_SLOPE) == original
    actual = elo.winner_score(1800)
    assert calculate_game_length_elo_change(1500 + gap, 1500, 1800, 1) == 20 * (
        actual - original
    )


def test_explicit_expected_slope_changes_updates_on_hand_made_game():
    # A 100-point favourite, log-odds slope ln(3)/100: expected score is .75.
    slope = np.log(3) / 100
    assert expected_score(1600, 1500, slope=slope) == pytest.approx(0.75)
    assert expected_score(1500, 1600, slope=slope) == pytest.approx(0.25)
    assert expected_score(1500, 1500, slope=slope) == 0.5
    change = calculate_game_length_elo_change(
        1600, 1500, 1800, 1, K=16, expected_slope=slope
    )
    assert change == pytest.approx(16 * (0.825 - 0.75))
    assert calculate_game_length_elo_change(
        1500, 1600, 1800, 0, K=16, expected_slope=slope
    ) == pytest.approx(-change)
    assert change < calculate_game_length_elo_change(1600, 1500, 1800, 1, K=16)


def _rd_games(dates=None):
    games = pd.DataFrame(
        {
            "gameid": ["r1", "r2", "r3"],
            "teamid": ["A"] * 3,
            "opponent_teamid": ["B"] * 3,
            "gamelength": [1800] * 3,
            "result": [1] * 3,
        }
    )
    if dates is not None:
        games["date"] = dates
    return games


@pytest.mark.parametrize("information", [0.25, 0.5, 1.0])
def test_rd_harmonic_shrink_matches_hand_calculation_without_dates(information):
    records, _ = compute_elo_records(
        _rd_games().iloc[:2],
        lambda **kw: 10,
        player_rd=(250, 100, 0),
        player_rd_information=information,
    )
    a = records[records.teamid == "A"]
    b = records[records.teamid == "B"]
    assert a.iloc[0].elo_change == pytest.approx(10 * (250 / 100) ** 2)
    # First game's E=.5, so the first posterior variance gives the next K scale.
    variance = 1 / (1 / 250**2 + information * (np.log(10) / 400) ** 2 * 0.25)
    assert a.iloc[1].elo_change == pytest.approx(10 * variance / 100**2)
    np.testing.assert_allclose(a.elo_change, -b.elo_change)


def test_rd_floor_reference_reaches_published_k_after_hand_counted_games():
    games = pd.concat([_rd_games().iloc[:1]] * 43, ignore_index=True)
    games["gameid"] = range(len(games))

    # Zero movement keeps E=.5, isolating shrinkage; only the final game moves.
    def replay(multiplier, count):
        calls = iter([0] * (count - 1) + [10])
        records, _ = compute_elo_records(
            games.iloc[:count],
            lambda **kw: next(calls),
            player_rd=(250, 100, 0),
            player_rd_information=multiplier,
        )
        return records.iloc[-2].elo_change

    # ceil((1/100² - 1/250²)/(q²*.25*m)): 11 or 41 shrink updates.
    assert replay(1, 11) > 10
    assert replay(1, 12) == pytest.approx(10)
    assert replay(0.25, 41) > 10
    assert replay(0.25, 42) == pytest.approx(10)


@pytest.mark.parametrize("information", [0, -0.25, np.inf, np.nan])
def test_rd_rejects_invalid_information(information):
    with pytest.raises(ValueError, match="player_rd_information"):
        compute_elo_records(
            _rd_games(),
            lambda **kw: 10,
            player_rd=(250, 100, 0),
            player_rd_information=information,
        )


def test_rd_inactivity_inflates_variance_and_caps_at_new():
    games = _rd_games(["2020-01-01", "2020-01-01", "2021-01-01"])
    records, _ = compute_elo_records(
        games,
        lambda **kw: 10,
        player_rd=(250, 100, 100),
        player_rd_information=1.0,
    )
    a = records[records.teamid == "A"]
    assert a.iloc[1].elo_change < 62.5
    assert a.iloc[2].elo_change == pytest.approx(62.5)  # long break resets to cap
    floor, _ = compute_elo_records(games, lambda **kw: 10, player_rd=(100, 100, 0))
    np.testing.assert_allclose(floor[floor.teamid == "A"].elo_change, 10)


def test_rd_rookie_weight_uses_floor_reference():
    games = _rd_games().iloc[:2]
    rosters = {
        ("r1", "A"): ("a", "b"),
        ("r2", "A"): ("a", "rookie"),
        ("r1", "B"): ("c", "d"),
        ("r2", "B"): ("c", "d"),
    }
    _, _, players = compute_elo_records(
        games,
        lambda **kw: 10,
        rosters=rosters,
        player_records=True,
        player_rd=(250, 100, 0),
        player_rd_information=1.0,
    )
    current = players[players.gameid == "r2"].set_index("playerid")
    moves = current.post_match_elo - current.pre_match_elo
    v = 1 / (1 / 250**2 + (np.log(10) / 400) ** 2 * 0.25)
    assert moves["a"] == pytest.approx(10 * v / 100**2)
    assert moves["rookie"] == pytest.approx(62.5)
    assert moves["c"] == pytest.approx(-10 * v / 100**2)


def test_rd_settled_player_keeps_baseline_move_beside_uncertain_teammate():
    games = pd.concat([_rd_games().iloc[:1]] * 14, ignore_index=True)
    games["gameid"] = range(len(games))
    rosters = {
        (i, side): (side + "1", side + "2") for i in range(14) for side in ("A", "B")
    }
    rosters[(13, "A")] = ("A1", "rookie")
    calls = iter([0] * 13 + [10])
    _, _, players = compute_elo_records(
        games,
        lambda **kw: next(calls),
        rosters=rosters,
        player_records=True,
        player_rd=(250, 100, 0),
        player_rd_information=1.0,
    )
    final = players[players.gameid == 13].set_index("playerid")
    moves = final.post_match_elo - final.pre_match_elo
    assert moves["A1"] == pytest.approx(10)
    assert moves["B1"] == pytest.approx(-10)
    assert moves["rookie"] == pytest.approx(62.5)


@pytest.mark.parametrize(
    "rd",
    [
        (100, 200, 1),
        (100, 0, 1),
        (100, 50, -1),
        (np.inf, 50, 1),
    ],
)
def test_rd_rejects_invalid_configuration(rd):
    with pytest.raises(ValueError, match="player_rd"):
        compute_elo_records(_rd_games(), lambda **kw: 10, player_rd=rd)


@pytest.mark.parametrize("league", ["LCKC", "LCK", "Worlds", None])
def test_published_update_slope_follows_event_league(league):
    games, _ = _two_games()
    games = (
        games.drop(columns="league") if league is None else games.assign(league=league)
    )
    calls = []

    def change(**kwargs):
        calls.append(kwargs.copy())
        return calculate_game_length_elo_change(**kwargs)

    records, _ = elo.compute_elo_records(games, change)
    for call in calls:
        if league == "LCKC":
            assert call["expected_slope"] == 0.0065
        else:
            assert "expected_slope" not in call
    # First game: equal ratings, RD 280 / floor 140 scales the 6.5 move by four.
    discount_after = 250 * (1 - np.log(2) / np.log(201))
    assert records.iloc[0].post_match_elo == pytest.approx(
        1500 + 4 * 6.5 - discount_after
    )
    assert calls[1]["elo"] != calls[1]["opponent_elo"]


@pytest.mark.parametrize("league", ["NACL", "LCS", "MSI", None])
def test_rd_information_uses_the_game_update_slope(league):
    games = _rd_games()
    if league is not None:
        games["league"] = league
    records, _ = elo.compute_elo_records(
        games, lambda **kw: 10, rookie_penalty=0, player_rd=(250, 100, 0)
    )
    # A constant update isolates RD shrinkage; later games have unequal ratings,
    # so E as well as the slope enters the information.
    slope = 0.0065 if league == "NACL" else np.log(10) / 400
    variance, difference = 250**2, 0.0
    for row in records[records.teamid == "A"].itertuples():
        step = 10 * variance / 100**2
        assert row.elo_change == pytest.approx(step)
        expectation = 1 / (1 + np.exp(-slope * difference))
        variance = max(
            100**2,
            1 / (1 / variance + 0.125 * slope**2 * expectation * (1 - expectation)),
        )
        difference += 2 * step
