"""
Roster construction analysis — determines how urgently each position is needed
relative to the league's starting lineup requirements.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType


def _canonical_position(pos: str) -> str:
    """
    Normalize Yahoo display positions to a single primary position string.
    Yahoo uses formats like "RB,WR" or "W/R/T"; we want just the first token.
    """
    if not pos:
        return ""
    return pos.replace("/", ",").split(",")[0].strip().upper()


def _count_at_position(roster: list[dict], position: str) -> int:
    """Count roster players at a given position."""
    return sum(
        1 for p in roster
        if _canonical_position(
            p.get("position") or p.get("display_position", "")
        ) == position
    )


def roster_need_bonus(
    player_position: str,
    my_roster: list[dict],
    config: "ModuleType",
) -> float:
    """
    Return a score adjustment based on how urgently we need this position:

      +NEED_STARTER_BONUS     → position's starting slots not yet filled
       0                      → starters filled, still want bench depth
      -POSITION_SATURATION_PENALTY → starters + bench depth target both met
    """
    pos = _canonical_position(player_position)
    if pos not in config.STARTING_SLOTS or pos == "FLEX":
        return 0.0

    count = _count_at_position(my_roster, pos)
    starters_needed = config.STARTING_SLOTS[pos]
    bench_target = config.BENCH_DEPTH_TARGET.get(pos, 1)

    if count < starters_needed:
        return config.NEED_STARTER_BONUS
    elif count < starters_needed + bench_target:
        return 0.0
    else:
        return -config.POSITION_SATURATION_PENALTY


def unfilled_starting_positions(my_roster: list[dict], config: "ModuleType") -> list[str]:
    """
    Return positions (excluding FLEX) that still have unfilled starting slots.
    Used for generating recommendation reasoning text.
    """
    return [
        pos
        for pos, slots in config.STARTING_SLOTS.items()
        if pos != "FLEX" and _count_at_position(my_roster, pos) < slots
    ]
