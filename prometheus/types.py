from enum import Enum


class Metric(str, Enum):
    glory = "glory"


class League(str, Enum):
    MAJOR = "MAJOR"
    LCK = "LCK"
    LPL = "LPL"
    EU_LCS = "EU LCS"
    LEC = "LEC"
    NA_LCS = "NA LCS"
    LCS = "LCS"
    LTA_N = "LTA N"
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
    WORLDS = "WORLDS"


PRE_2019_MAJOR_LEAGUES = [
    League.LCK,
    League.LPL,
    League.EU_LCS,
    League.NA_LCS,
]

PRE_2025_MAJOR_LEAGUES = [
    League.LCK,
    League.LPL,
    League.LEC,
    League.LCS,
]

CURRENT_MAJOR_LEAGUES = [
    League.LCK,
    League.LPL,
    League.LEC,
    League.LTA_N,
]

ALL_MAJOR_LEAGUES = list(
    set(PRE_2019_MAJOR_LEAGUES + PRE_2025_MAJOR_LEAGUES + CURRENT_MAJOR_LEAGUES)
)
