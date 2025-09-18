from enum import Enum


class Metric(str, Enum):
    glory = "glory"


class League(str, Enum):
    LCK = "LCK"
    LPL = "LPL"
    EU_LCS = "EU LCS"
    NA_LCS = "NA LCS"
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
