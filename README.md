# Prometheus
Prometheus is a database of 'sabermetric' like stats that evaluate League of Legends esports teams and players. The `prometheus` repository will contain a database that records these stats as well as a self-hosted website to browse stats across different teams, seasons, and regions.
## Goals
- [ ] One advanced metric (LORE) that evaluates team performance
- [ ] One advanced metric that evaluates individual player performance
- [ ] SQL database that stores match, team, player, and stat tables
- [ ] Self-hosted webpage for exploring stat rankings
- [ ] Metrics span 5+ years of data over all major regions
## Metrics
### Team-based
These metrics evaluate the strength of a team. Their main purpose is to compare the strength of a given team compared to teams across regions. 

These metrics are heavily dependent on the strength of opposing teams and the meta. For example, a team that plays during the 2018 skirmish-heavy meta will tend to have higher scores than the control-meta of 2015, regardless of the truth strengths of their team.

To account for this, Prometheus calculates stats based on a per-season basis. Each metric is weighted appropriately for a single season. Thus, teams are scored based on how well they accomplish the goals of that specific "meta". 

Prometheus also includes z-scores to compare the strength of a team relative to other teams in its region. We can calculate which teams were most "dominant" in specific eras. 
#### League Outstanding Rankings Extrapolated (LORE)
LORE is prometheus' flagship stat for team performance. At a high level, it is a weighted sum of basic per-game stats listed below.

```
- GPM = team_gold / game_length_minutes
- GDPM = (team_gold - opponent_gold) / game_length_minutes
- Turrets_per_10 = turrets_taken / (game_length_minutes/10)
- Baron_per_10 = barons_taken / (game_length_minutes/10)
- Dragon_per_10 = dragons_taken / (game_length_minutes/10)
- Objective_conversion_rate = objectives_taken / contested_objectives
```

We also include slightly more advanced metrics in this calculation:

```
- Objective_conversion = fraction of team kills that directly preceded (within X seconds) an objective take
```

In LORE, weights are calculated using logistic regression with the winning team as a prediction target. 
#### League Outstanding Rankings Baseline (LORB)
LORB is very similar to LORE, except all categories are weighted equally. It provides a baseline to compare LORE against and is much easier to implement. 
### Player-based
`TBD`
## Implementation
Determining the weights for WOBA involves creating a table where each match has two rows: one for Blue side and one for Red side. The features in a row are the stats described above.

The match data will be stored in an sqlite3 database. Initially, the only table in the database will be a match table that stores the weights for LORB/LORE. 
## Challenges
#### Strength-based schedules
Unlike traditional sports, most modern League regions don't follow a traditional round-robin based format for their regular season. For example, here is the LTA North Split 1 season: 

![LTA North playoffs](./docs/images/playoffs.png)
As a team advances farther in the bracket, they face more difficult opponents, which results in worse metrics. Stronger teams that advance farther are "punished" by the metrics for winning their games and moving through the bracket. 

One solution to this problem is to factor in opponent team strength when calculating metrics. This can be simply by using opponent win percentage to adjust scores, or calculating a team's elo. 