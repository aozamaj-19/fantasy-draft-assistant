# =============================================================
# VOR Recommendation Engine — Tunable Configuration
#
# This is the ONLY file you need to edit to retune the formula.
# All constants have an inline comment explaining what they control.
# =============================================================

# ---- League Structure -------------------------------------------

NUM_TEAMS = 12
# Number of teams in your fantasy league.
# Directly controls replacement level ranks: higher N → later (worse) replacement player.

TOTAL_SEASON_WEEKS = 17
# Total number of scored fantasy weeks (regular season + playoffs combined).

PLAYOFF_START_WEEK = 13
# First week of the fantasy playoffs.
# Weeks >= this value receive the PLAYOFF_MULTIPLIER boost on projected points.

PLAYOFF_MULTIPLIER = 1.15
# Weight applied to points projected during playoff weeks (PLAYOFF_START_WEEK onward).
# 1.15 = a 15% boost. Reasonable range: 1.05 – 1.25.
# Higher values bias picks toward players with strong late-season schedules.

# ---- Starting Lineup Slots --------------------------------------

STARTING_SLOTS: dict[str, int] = {
    "QB": 1,    # Starting quarterbacks
    "RB": 2,    # Starting running backs
    "WR": 2,    # Starting wide receivers
    "TE": 1,    # Starting tight ends
    "FLEX": 1,  # RB/WR/TE flex spot
    "K": 1,     # Kicker
    "DEF": 1,   # Team defense / special teams
}

FLEX_ELIGIBLE_POSITIONS: list[str] = ["RB", "WR", "TE"]
# Positions that can start in the FLEX slot.
# Affects effective replacement level rank for each flex-eligible position.

FLEX_WEIGHT_BY_POSITION: dict[str, float] = {
    "RB": 0.50,  # 50% of FLEX slots expected to be filled by RBs
    "WR": 0.40,  # 40% by WRs
    "TE": 0.10,  # 10% by TEs
}
# Must sum to 1.0. Controls how FLEX starting slots are distributed across positions
# when computing replacement level. Increase WR weight if your league starts more WR FLEX.

BENCH_SLOTS = 6
# Total bench roster spots (excluding IR). Used to detect when a position is oversaturated.

BENCH_DEPTH_TARGET: dict[str, int] = {
    "QB": 1,   # Desired backups beyond starters
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "K": 0,
    "DEF": 0,
}
# After starters + these bench targets are filled at a position, drafting more
# there incurs the POSITION_SATURATION_PENALTY.

# ---- Replacement Level Overrides --------------------------------

REPLACEMENT_LEVEL_OVERRIDE: dict[str, int] = {}
# Manually fix the replacement level rank for specific positions.
# Default is dynamically computed: NUM_TEAMS × (starting_slots + flex_allocation).
# Example to force 12th QB as replacement level: {"QB": 12}
# Example to force 30th RB: {"RB": 30}

# ---- Roster Need Adjustments ------------------------------------

NEED_STARTER_BONUS = 8.0
# Score bonus (in VOR points) when drafting this player fills an unfilled starting slot.
# Acts as a tiebreaker between similarly-valued players. Set 0 to disable.

POSITION_SATURATION_PENALTY = 20.0
# Score deduction (in VOR points) when the position already has full starters + bench depth.
# Discourages stacking one position well beyond useful depth. Set 0 to disable.

# ---- Penalty Weights --------------------------------------------

BYE_CONFLICT_THRESHOLD = 2
# Minimum number of same-position roster players sharing a bye week before
# the BYE_CONFLICT_PENALTY triggers. Default 2 means if 2+ existing players
# share the same bye, adding a third triggers the penalty.

BYE_CONFLICT_PENALTY = 10.0
# Score deduction (in VOR points) when a player's bye week conflicts with
# BYE_CONFLICT_THRESHOLD or more existing roster players at the same position.

INJURY_STATUSES_PENALIZED: frozenset[str] = frozenset({"OUT", "IR", "PUP", "SUSP"})
# ESPN injury status strings that trigger the score penalty.
# "QUESTIONABLE" is flagged but NOT penalized — still worth drafting.

INJURY_PENALTY = 20.0
# Score deduction (in VOR points) for players whose ESPN injury status is
# in INJURY_STATUSES_PENALIZED.

INJURY_STATUSES_FLAGGED: frozenset[str] = frozenset(
    {"QUESTIONABLE", "DOUBTFUL", "OUT", "IR", "PUP", "SUSP"}
)
# All statuses shown as warning flags in output, even if not score-penalized.
# Extend this set to surface more injury warnings.

# ---- ESPN Data --------------------------------------------------

ESPN_SEASON_YEAR = 2025
# NFL season year used when fetching projections from ESPN.

ESPN_PROJECTION_PLAYER_LIMIT = 500
# Maximum players returned per ESPN API request. 500 covers all relevant fantasy players.

ESPN_PROJECTION_CACHE_TTL_SECONDS = 3600
# Seconds to cache ESPN projection data in memory.
# Projections rarely change mid-draft; 1 hour avoids redundant API calls.

# ---- Output -----------------------------------------------------

RECOMMENDATION_LIST_SIZE = 10
# Number of players in the ranked recommendation output (sorted alphabetically by last name).
