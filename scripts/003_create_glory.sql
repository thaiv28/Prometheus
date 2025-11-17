CREATE VIEW match_glory_stats AS
SELECT
    m.gameid,
    m.teamid,
    (ms.totalgold * 60.0) / NULLIF(m.gamelength, 0)  AS gpm,
    (ms.kills * 600.0) / NULLIF(m.gamelength, 0)     AS kills_per_10,
    (ms.towers * 600.0) / NULLIF(m.gamelength, 0)    AS turrets_per_10,
    (ms.barons * 600.0) / NULLIF(m.gamelength, 0)    AS baron_per_10,
    (ms.dragons * 600.0) / NULLIF(m.gamelength, 0)   AS dragon_per_10,
    ms.atakhans                                      AS atakhans,
    (ms.heralds * 600.0) / NULLIF(m.gamelength, 0)   AS heralds_per_10,
    ms.firstherald                                   AS firstherald,
    ms.firstdragon                                   AS firstdragon,
    ms.firstbaron                                    AS firstbaron,
    ms.firsttower                                    AS firsttower,
    (ms.visionscore * 600.0) / NULLIF(m.gamelength, 0) AS visionscore_per_10
FROM match_stats ms
JOIN matches m
  ON ms.gameid = m.gameid AND ms.teamid = m.teamid;