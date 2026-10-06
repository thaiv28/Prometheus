from enum import Enum


class Metric(str, Enum):
    # Season stats
    glory = "glory"
    record = "record"
    luck = "luck"
    # Forecasts
    forge = "forge"
    form = "form"
    # Sunset
    glorb = "glorb"


class League(str, Enum):
    MAJOR = "MAJOR"
    LCK = "LCK"
    LPL = "LPL"
    LEC = "LEC"
    LCS = "LCS"
    LTA_S = "LTA S"
    PCS = "PCS"
    VCS = "VCS"
    LJL = "LJL"
    TCL = "TCL"
    CBLOL = "CBLOL"
    LLA = "LLA"
    OPL = "OPL"
    LCL = "LCL"
    LCO = "LCO"
    WCS = "WCS"
    MSI = "MSI"
    WORLDS = "Worlds"


class ScoreCols(str, Enum):
    score = "score"
    era_score = "era_score"
    league_score = "league_score"


ALL_MAJOR_LEAGUES = [
    League.LCK,
    League.LPL,
    League.LEC,
    League.LCS,
]

# Events where teams from different regions meet. They are the only games that tie
# regional Elo pools together, and they are not a team's home league.
INTERNATIONAL_LEAGUES = [
    "Worlds",
    "MSI",
    "EWC",
    "FST",
    "IEM",
    "MSC",
    "Riot",
    "ASI",
    "IWCI",
    "DCGI",  # Demacia Cup Global Invitational (LPL, LCK, LCS, VCS, ... teams)
    "WSCI",  # World Star Challengers Invitational (academy teams from several regions)
]

GLORY_FEATURES = [
    "gpm",
    "kills_per_10",
    "turrets_per_10",
    "baron_per_10",
    "dragon_per_10",
    "atakhans",
    "heralds_per_10",
    "firstherald",
    "firstdragon",
    "firstbaron",
    "firsttower",
    "visionscore_per_10",
]

MATCHES_FEATURES = [
    "gameid",
    "date",
    "year",
    "split",
    "league",
    "teamid",
    "teamname",
    "side",
    "gamelength",
    "result",
]

MATCH_RAW_FEATURES = [
    "totalgold",
    "towers",
    "barons",
    "dragons",
    "kills",
    "atakhans",
    "heralds",
    "firstherald",
    "firstdragon",
    "firstbaron",
    "firsttower",
    "visionscore",
]

PLAYER_RAW_FEATURES = [
    "goldat10",
    "xpat10",
    "csat10",
    "opp_goldat10",
    "opp_xpat10",
    "opp_csat10",
    "killsat10",
    "assistsat10",
    "deathsat10",
    "opp_killsat10",
    "opp_assistsat10",
    "opp_deathsat10",
    "goldat15",
    "xpat15",
    "csat15",
    "opp_goldat15",
    "opp_xpat15",
    "opp_csat15",
    "killsat15",
    "assistsat15",
    "deathsat15",
    "opp_killsat15",
    "opp_assistsat15",
    "opp_deathsat15",
    "goldat20",
    "xpat20",
    "csat20",
    "opp_goldat20",
    "opp_xpat20",
    "opp_csat20",
    "killsat20",
    "assistsat20",
    "deathsat20",
    "opp_killsat20",
    "opp_assistsat20",
    "opp_deathsat20",
    "goldat25",
    "xpat25",
    "csat25",
    "opp_goldat25",
    "opp_xpat25",
    "opp_csat25",
    "killsat25",
    "assistsat25",
    "deathsat25",
    "opp_killsat25",
    "opp_assistsat25",
    "opp_deathsat25",
]

# Full-game player stats (end of game; NULL where Oracle's Elixir lacks them).
# "earned gpm" is renamed earned_gpm at ingest.
PLAYER_GAME_FEATURES = [
    "kills",
    "deaths",
    "assists",
    "teamkills",
    "teamdeaths",
    "damageshare",
    "earnedgoldshare",
    "damagetotowers",
    "dpm",
    "damagetakenperminute",
    "damagemitigatedperminute",
    "vspm",
    "wpm",
    "wcpm",
    "controlwardsbought",
    "cspm",
    "earned_gpm",
]
