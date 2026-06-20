# Recommendation Engine

Deterministic VOR-based fantasy football draft recommendation engine.
No AI or external ML dependencies — pure formula logic you can tune and test.

## Module layout

```
recommendation_engine/
  config.py   ← all tunable constants (edit this to retune)
  vor.py      ← VOR and playoff-weight math
  roster.py   ← roster need / saturation analysis
  flags.py    ← bye week conflict and injury flag checks
  ranker.py   ← assembles everything into the final ranked output

projections/
  espn_projections.py  ← fetches projected season points from ESPN's public API
```

## How it works

1. **Fetch projections** — `espn_projections.py` pulls season-long projected fantasy
   points from ESPN's public leaguedefaults API (no auth required) and caches them
   for `ESPN_PROJECTION_CACHE_TTL_SECONDS`.

2. **Merge** — Yahoo player data (available from your draft board) is matched to ESPN
   projection data by player name. Players with no ESPN match score 0 projected points
   and rank near the bottom.

3. **Replacement level** — For each position, the replacement level is the projected
   points of the Nth ranked player, where N = `NUM_TEAMS × effective_starting_slots`.
   Effective slots for flex-eligible positions include a weighted share of `FLEX` slots
   controlled by `FLEX_WEIGHT_BY_POSITION`.

4. **VOR** = `player_projected_points − replacement_level_at_position`

5. **Playoff adjustment** — VOR is multiplied by a blended factor that gives
   playoff weeks a `PLAYOFF_MULTIPLIER` boost relative to regular-season weeks.
   With defaults: `(12/17)×1.0 + (5/17)×1.15 ≈ 1.044` (a ~4.4% lift).

6. **Roster need bonus/penalty** — Added to playoff-adjusted VOR:
   - `+NEED_STARTER_BONUS` if the position still has unfilled starting slots
   - `−POSITION_SATURATION_PENALTY` if starters + bench depth target are already met

7. **Penalties** — Subtracted from the score:
   - `BYE_CONFLICT_PENALTY` if the player shares a bye week with ≥ `BYE_CONFLICT_THRESHOLD`
     existing roster players at the same position
   - `INJURY_PENALTY` if the player's ESPN injury status is in `INJURY_STATUSES_PENALIZED`

8. **Output** — The highest-scoring player is `best_pick`. The top
   `RECOMMENDATION_LIST_SIZE` players (by score) are returned as `ranked_list`,
   sorted alphabetically by last name.

## Config reference

All constants live in `config.py`. Change only that file to retune — no engine
logic changes needed for normal adjustments.

| Constant | Default | Effect of increasing |
|---|---|---|
| `NUM_TEAMS` | 12 | Replacement level moves to a later (worse) player — VOR scores drop |
| `PLAYOFF_START_WEEK` | 13 | More weeks counted as playoffs → playoff multiplier covers more of season |
| `PLAYOFF_MULTIPLIER` | 1.15 | Stronger preference for players with good late-season schedules |
| `STARTING_SLOTS` | see config | More starting slots at a position → higher replacement rank → lower VOR |
| `FLEX_WEIGHT_BY_POSITION` | RB 0.5, WR 0.4, TE 0.1 | Increase WR weight if your league fills FLEX with WR more often |
| `BENCH_SLOTS` | 6 | Affects saturation detection |
| `BENCH_DEPTH_TARGET` | see config | Lower → saturation penalty kicks in sooner |
| `NEED_STARTER_BONUS` | 8.0 | Stronger position-need tiebreaking |
| `POSITION_SATURATION_PENALTY` | 20.0 | Harder discouragement from stacking one position |
| `BYE_CONFLICT_THRESHOLD` | 2 | Lower → penalty triggers with fewer bye conflicts |
| `BYE_CONFLICT_PENALTY` | 10.0 | More aggressive bye-week spreading |
| `INJURY_PENALTY` | 20.0 | Stronger avoidance of players with bad injury status |
| `RECOMMENDATION_LIST_SIZE` | 10 | More/fewer players in the alphabetical ranked list |

## Swapping the projection source

`espn_projections.py` is the only data-fetching module. To replace ESPN with another
source (e.g., FantasyPros CSV export, Sleeper API), implement:

```python
def fetch_season_projections(year: int, limit: int) -> list[dict]:
    # Must return a list of dicts with at minimum:
    #   name: str, position: str, projected_points: float
    # Optional but used: bye_week: int | None, injury_status: str
    ...
```

Then update `get_projections()` to call your new function.
