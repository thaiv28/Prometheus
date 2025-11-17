CREATE TABLE matches(
    gameid             TEXT NOT NULL,       -- unique match ID taken from OE
    year               INT NOT NULL,
    split              TEXT,                -- Spring, Summer, etc
    league             TEXT NOT NULL,       -- LCK, LEC, VCS, etc.
    teamid             TEXT NOT NULL,       -- unique team identifier taken from OE
    teamname           TEXT NOT NULL,       -- ex: "T1", "G2 Esports", etc.
    side               TEXT CHECK (side IN ('Red','Blue')) NOT NULL, 
    gamelength         INT NOT NULL,
    result             BOOLEAN NOT NULL,

    PRIMARY KEY(gameid, teamid)
);

CREATE TABLE match_stats(
    gameid              TEXT NOT NULL,
    teamid              TEXT NOT NULL,

    totalgold           INT NOT NULL,
    kills               INT NOT NULL,
    towers              INT NOT NULL,
    barons              INT NOT NULL,
    dragons             INT NOT NULL,
    atakhans            INT NOT NULL,
    heralds             INT NOT NULL,
    firstherald         BOOLEAN NOT NULL,
    firstdragon         BOOLEAN NOT NULL,
    firstbaron          BOOLEAN NOT NULL,
    firsttower          BOOLEAN NOT NULL,
    visionscore         INT NOT NULL,

    PRIMARY KEY (gameid, teamid),
    FOREIGN KEY(gameid, teamid) REFERENCES matches(gameid, teamid)
);

CREATE TABLE player_stats (
    gameid             TEXT NOT NULL,
    playerid           TEXT NOT NULL,       -- unique player identifier taken from OE
    playername         TEXT NOT NULL,       -- ex: "Faker", "Caps", etc.
    teamid             TEXT NOT NULL,       -- unique team identifier taken from OE
    position           TEXT CHECK (position IN ('top','jng','mid','bot','sup')) NOT NULL,
    champion           TEXT NOT NULL, 

    -- raw totals
    goldat10 INT NOT NULL,
    xpat10 INT NOT NULL,
    csat10 INT NOT NULL,
    opp_goldat10 INT NOT NULL,
    opp_xpat10 INT NOT NULL,
    opp_csat10 INT NOT NULL,
    killsat10 INT NOT NULL,
    assistsat10 INT NOT NULL,
    deathsat10 INT NOT NULL,
    opp_killsat10 INT NOT NULL,
    opp_assistsat10 INT NOT NULL,
    opp_deathsat10 INT NOT NULL,

    goldat15 INT NOT NULL,
    xpat15 INT NOT NULL,
    csat15 INT NOT NULL,
    opp_goldat15 INT NOT NULL,
    opp_xpat15 INT NOT NULL,
    opp_csat15 INT NOT NULL,
    killsat15 INT NOT NULL,
    assistsat15 INT NOT NULL,
    deathsat15 INT NOT NULL,
    opp_killsat15 INT NOT NULL,
    opp_assistsat15 INT NOT NULL,
    opp_deathsat15 INT NOT NULL,

    goldat20 INT NOT NULL,
    xpat20 INT NOT NULL,
    csat20 INT NOT NULL,
    opp_goldat20 INT NOT NULL,
    opp_xpat20 INT NOT NULL,
    opp_csat20 INT NOT NULL,
    killsat20 INT NOT NULL,
    assistsat20 INT NOT NULL,
    deathsat20 INT NOT NULL,
    opp_killsat20 INT NOT NULL,
    opp_assistsat20 INT NOT NULL,
    opp_deathsat20 INT NOT NULL,

    goldat25 INT NOT NULL,
    xpat25 INT NOT NULL,
    csat25 INT NOT NULL,
    opp_goldat25 INT NOT NULL,
    opp_xpat25 INT NOT NULL,
    opp_csat25 INT NOT NULL,
    killsat25 INT NOT NULL,
    assistsat25 INT NOT NULL,
    deathsat25 INT NOT NULL,
    opp_killsat25 INT NOT NULL,
    opp_assistsat25 INT NOT NULL,
    opp_deathsat25 INT NOT NULL,

    PRIMARY KEY(gameid, playerid),
    FOREIGN KEY(gameid, teamid) REFERENCES matches(gameid, teamid)
);

