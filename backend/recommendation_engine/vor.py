"""
Value Over Replacement (VOR) calculation functions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType


def compute_replacement_ranks(config: "ModuleType", num_teams: int | None = None) -> dict[str, int]:
    """
    Return the replacement level rank (1-indexed) for each starting position.

    Rank N means the Nth-ranked player at that position sets the baseline:
    anyone above them has positive VOR; anyone below has negative VOR.

    FLEX slots are distributed across flex-eligible positions via
    config.FLEX_WEIGHT_BY_POSITION.
    """
    n = num_teams if num_teams is not None else config.NUM_TEAMS
    flex_slots = config.STARTING_SLOTS.get("FLEX", 0)
    ranks: dict[str, int] = {}

    for pos, starters in config.STARTING_SLOTS.items():
        if pos == "FLEX":
            continue

        if pos in config.REPLACEMENT_LEVEL_OVERRIDE:
            ranks[pos] = config.REPLACEMENT_LEVEL_OVERRIDE[pos]
            continue

        flex_contribution = flex_slots * config.FLEX_WEIGHT_BY_POSITION.get(pos, 0.0)
        effective_starters = starters + flex_contribution
        ranks[pos] = max(1, round(n * effective_starters))

    return ranks


def compute_replacement_levels(
    all_players: list[dict],
    replacement_ranks: dict[str, int],
) -> dict[str, float]:
    """
    Return the projected-points value at replacement level for each position.

    Scans the full player pool (not just available players) so the baseline
    reflects the entire draft, not just remaining picks.
    """
    by_position: dict[str, list[float]] = {}
    for p in all_players:
        pos = p.get("position", "")
        pts = p.get("projected_points", 0.0) or 0.0
        by_position.setdefault(pos, []).append(pts)

    levels: dict[str, float] = {}
    for pos, rank in replacement_ranks.items():
        sorted_pts = sorted(by_position.get(pos, [0.0]), reverse=True)
        idx = rank - 1  # rank is 1-indexed
        levels[pos] = sorted_pts[idx] if idx < len(sorted_pts) else 0.0

    return levels


def calculate_vor(player: dict, replacement_levels: dict[str, float]) -> float:
    """
    VOR = player projected_points − replacement level at their position.
    Negative VOR means the player projects below replacement level.
    """
    pos = player.get("position", "")
    repl = replacement_levels.get(pos, 0.0)
    return round((player.get("projected_points") or 0.0) - repl, 2)


def playoff_weight_factor(config: "ModuleType") -> float:
    """
    Scalar that blends regular-season (1.0×) and playoff-week (PLAYOFF_MULTIPLIER×)
    contributions based on the fraction of weeks each represents.

    Example with defaults (17 weeks, playoffs start week 13, multiplier 1.15):
      regular = 12 weeks, playoff = 5 weeks
      factor = (12/17)*1.0 + (5/17)*1.15 = 0.706 + 0.338 = 1.044
    """
    total = config.TOTAL_SEASON_WEEKS
    playoff_weeks = total - config.PLAYOFF_START_WEEK + 1
    regular_weeks = total - playoff_weeks
    return (regular_weeks / total) + (playoff_weeks / total) * config.PLAYOFF_MULTIPLIER


def apply_playoff_weight(vor: float, factor: float) -> float:
    """Return playoff-adjusted VOR given the blended weight factor."""
    return round(vor * factor, 2)
