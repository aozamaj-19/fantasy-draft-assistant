"""
Player flag checks — bye week conflicts and injury concerns.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType


def _primary_position(player: dict) -> str:
    pos = player.get("position") or player.get("display_position", "")
    return pos.replace("/", ",").split(",")[0].strip().upper()


def check_bye_conflict(player: dict, my_roster: list[dict], config: "ModuleType") -> bool:
    """
    Return True if drafting this player creates a problematic bye week pile-up:
    the player's bye week matches BYE_CONFLICT_THRESHOLD or more existing
    roster players at the same position.
    """
    player_bye = player.get("bye_week")
    if player_bye is None:
        return False

    player_pos = _primary_position(player)
    same_pos_on_bye = sum(
        1 for p in my_roster
        if _primary_position(p) == player_pos
        and _coerce_week(p.get("bye_week")) == _coerce_week(player_bye)
    )
    return same_pos_on_bye >= config.BYE_CONFLICT_THRESHOLD


def check_injury_flag(player: dict, config: "ModuleType") -> bool:
    """Return True if the player's status should appear as a warning flag."""
    status = (player.get("injury_status") or "").strip().upper()
    return status in config.INJURY_STATUSES_FLAGGED


def check_injury_penalized(player: dict, config: "ModuleType") -> bool:
    """Return True if the player's status triggers a score penalty."""
    status = (player.get("injury_status") or "").strip().upper()
    return status in config.INJURY_STATUSES_PENALIZED


def collect_flags(player: dict, my_roster: list[dict], config: "ModuleType") -> list[str]:
    """Return a list of human-readable warning flag strings for display."""
    flags: list[str] = []

    if check_bye_conflict(player, my_roster, config):
        flags.append(f"bye_conflict (week {player.get('bye_week')})")

    if check_injury_flag(player, config):
        status = (player.get("injury_status") or "").strip().upper()
        flags.append(f"injury_status ({status})")

    return flags


def _coerce_week(val) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None
