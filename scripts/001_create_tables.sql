CREATE TABLE match_raw_stats (
    gameid             TEXT NOT NULL,       -- unique match ID taken from OE
    year               INT NOT NULL,
    split              TEXT,                -- Spring, Summer, etc
    league             TEXT NOT NULL,       -- LCK, LEC, VCS, etc.
    teamid             TEXT,                -- unique team identifier taken from OE
    teamname           TEXT NOT NULL,       -- ex: "T1", "G2 Esports", etc.
    side               TEXT CHECK (side IN ('Red','Blue')) NOT NULL, 
    gamelength         REAL NOT NULL,
    result             TEXT CHECK (result IN ('Win','Loss')) NOT NULL,

    -- raw totals
    totalgold           INT NOT NULL,
    golddiffat15        INT NOT NULL,
    towers              INT NOT NULL,
    barons              INT NOT NULL,
    dragons             INT NOT NULL,

    PRIMARY KEY(gameid, teamid)
);

CREATE TABLE match_lore_stats (
    gameid           TEXT NOT NULL,
    teamid           TEXT NOT NULL,
    -- derived stats
    gpm                 REAL NOT NULL,
    golddiffat15        REAL NOT NULL,
    turrets_per_10      REAL NOT NULL,
    baron_per_10        REAL NOT NULL,
    dragon_per_10       REAL NOT NULL,

    PRIMARY KEY(gameid, teamid),
    FOREIGN KEY(gameid, teamid) REFERENCES match_raw_stats(gameid, teamid)
);

