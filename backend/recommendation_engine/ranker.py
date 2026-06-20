"""
Main ranking function — assembles VOR scores, adjustments, and flags
into the final recommendation output.
"""
from __future__ import annotations

import re
import types

from recommendation_engine import config as _default_cfg
from recommendation_engine.vor import (
    apply_playoff_weight,
    calculate_vor,
    compute_replacement_levels,
    compute_replacement_ranks,
    playoff_weight_factor,
)
from recommendation_engine.roster import roster_need_bonus, unfilled_starting_positions
from recommendation_engine.flags import (
    check_bye_conflict,
    check_injury_penalized,
    collect_flags,
)
from projections import espn_projections as _espn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical_position(pos: str) -> str:
    """Normalize Yahoo display positions like 'RB,WR' or 'W/R/T' to primary position."""
    if not pos:
        return ""
    return pos.replace("/", ",").split(",")[0].strip().upper()


def _normalize_name(name: str) -> str:
    """Lowercase, strip punctuation and name suffixes for fuzzy matching."""
    name = name.lower()
    name = re.sub(r"['.,-]", "", name)
    name = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", name)
    return re.sub(r"\s+", " ", name).strip()


def _parse_bye(val) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _last_name(name: str) -> str:
    parts = name.strip().split()
    return parts[-1].lower() if parts else ""


def _build_config_override(base_cfg, num_teams: int):
    """Return a SimpleNamespace with all base_cfg values but NUM_TEAMS overridden."""
    if num_teams == base_cfg.NUM_TEAMS:
        return base_cfg
    oc = types.SimpleNamespace(
        **{k: getattr(base_cfg, k) for k in dir(base_cfg) if not k.startswith("_")}
    )
    oc.NUM_TEAMS = num_teams
    return oc


# ---------------------------------------------------------------------------
# Data merging
# ---------------------------------------------------------------------------

def _merge_with_projections(players: list[dict], projections: list[dict]) -> list[dict]:
    """
    Merge Yahoo player dicts with ESPN projection dicts matched by player name.

    Adds projected_points, injury_status, and bye_week to each player dict.
    Players with no ESPN match get projected_points=0.0 (will rank near bottom).
    """
    proj_index: dict[str, dict] = {_normalize_name(p["name"]): p for p in projections}

    merged = []
    for player in players:
        name = player.get("name", "")
        proj = proj_index.get(_normalize_name(name), {})

        # ESPN bye week takes priority over Yahoo's string bye_week field
        bye_week = proj.get("bye_week") or _parse_bye(player.get("bye_week"))

        merged.append({
            **player,
            "position": _canonical_position(
                player.get("position") or player.get("display_position", "")
            ),
            "projected_points": proj.get("projected_points") or 0.0,
            "injury_status": proj.get("injury_status", ""),
            "bye_week": bye_week,
        })

    return merged


# ---------------------------------------------------------------------------
# Reasoning text
# ---------------------------------------------------------------------------

def _generate_reasoning(
    player: dict,
    vor: float,
    playoff_vor: float,
    need_bonus: float,
    flags: list[str],
) -> str:
    parts = [
        f"VOR {vor:.1f} (playoff-adj {playoff_vor:.1f}) at {player.get('position', '?')}",
    ]

    pts = player.get("projected_points") or 0.0
    if pts > 0:
        parts.append(f"{pts:.0f} projected season pts")

    if need_bonus > 0:
        parts.append(f"fills needed {player.get('position')} starter slot")
    elif need_bonus < 0:
        parts.append(f"{player.get('position')} depth already adequate")

    if flags:
        parts.append("flags: " + ", ".join(flags))

    return "; ".join(parts) + "."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rank_players(
    available_players: list[dict],
    my_roster: list[dict],
    num_teams: int | None = None,
    round_number: int = 1,
    pick_number: int = 1,
) -> dict:
    """
    Score and rank available players using VOR + roster need + penalty adjustments.

    Returns:
      {
        "best_pick": {
          name, position, team, projected_points,
          vor, playoff_adjusted_vor, reasoning, flags
        },
        "ranked_list": [
          top RECOMMENDATION_LIST_SIZE players sorted alphabetically by last name,
          each with: name, position, team, projected_points, vor,
                      playoff_adjusted_vor, flags
        ]
      }
    """
    cfg = _build_config_override(_default_cfg, num_teams or _default_cfg.NUM_TEAMS)

    # 1. Fetch ESPN projections (cached after first call)
    projections = _espn.get_projections(cfg.ESPN_SEASON_YEAR)

    # 2. Merge Yahoo player data with ESPN projections
    split = len(available_players)
    all_merged = _merge_with_projections(available_players + my_roster, projections)
    available_merged = all_merged[:split]
    roster_merged = all_merged[split:]

    # 3. Compute replacement levels from the full ESPN player pool
    repl_ranks = compute_replacement_ranks(cfg, cfg.NUM_TEAMS)
    repl_levels = compute_replacement_levels(projections, repl_ranks)

    # 4. Compute the playoff weight factor once (same for all players)
    pw_factor = playoff_weight_factor(cfg)

    # 5. Score every available player
    scored: list[dict] = []
    for player in available_merged:
        vor = calculate_vor(player, repl_levels)
        playoff_vor = apply_playoff_weight(vor, pw_factor)
        need_bonus = roster_need_bonus(player.get("position", ""), roster_merged, cfg)
        bye_penalty = cfg.BYE_CONFLICT_PENALTY if check_bye_conflict(player, roster_merged, cfg) else 0.0
        inj_penalty = cfg.INJURY_PENALTY if check_injury_penalized(player, cfg) else 0.0
        flags = collect_flags(player, roster_merged, cfg)

        final_score = playoff_vor + need_bonus - bye_penalty - inj_penalty

        scored.append({
            "name": player.get("name", ""),
            "position": player.get("position", ""),
            "team": player.get("team", ""),
            "projected_points": round(player.get("projected_points") or 0.0, 1),
            "vor": vor,
            "playoff_adjusted_vor": playoff_vor,
            "flags": flags,
            "_final_score": final_score,
            "_need_bonus": need_bonus,
        })

    if not scored:
        return {"best_pick": None, "ranked_list": []}

    # 6. Pick the single best player (highest final_score)
    best_raw = max(scored, key=lambda p: p["_final_score"])
    best = {k: v for k, v in best_raw.items() if not k.startswith("_")}
    best["reasoning"] = _generate_reasoning(
        best,
        best_raw["vor"],
        best_raw["playoff_adjusted_vor"],
        best_raw["_need_bonus"],
        best_raw["flags"],
    )

    # 7. Top N by score, then sort alphabetically by last name for display
    top_n = sorted(scored, key=lambda p: p["_final_score"], reverse=True)[
        : cfg.RECOMMENDATION_LIST_SIZE
    ]
    ranked_list = sorted(top_n, key=lambda p: _last_name(p["name"]))
    for p in ranked_list:
        p.pop("_final_score", None)
        p.pop("_need_bonus", None)

    return {"best_pick": best, "ranked_list": ranked_list}
