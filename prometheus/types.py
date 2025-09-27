from enum import Enum


class Metric(str, Enum):
    glory = "glory"
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

RAW_FEATURES = [
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
