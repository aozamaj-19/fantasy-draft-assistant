"""
Fetches player projections from Sleeper's public API (no auth required).

Uses week-1 projections scaled by 16 as a season-total proxy. This is far
lighter than summing all 18 weeks and keeps memory within Render's free-tier
limits (~400 MB total).
"""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

SLEEPER_BASE = "https://api.sleeper.app"
# Half-PPR is most common in modern leagues. Change to "pts_ppr" or "pts_std" as needed.
SCORING_FIELD = "pts_half_ppr"
FANTASY_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "K", "DEF"})
# Week-1 points × SEASON_SCALE ≈ season total (16 regular-season games played).
SEASON_SCALE = 16

_INJURY_STATUS_MAP: dict[str | None, str] = {
    None: "ACTIVE",
    "Active": "ACTIVE",
    "Probable": "ACTIVE",
    "Questionable": "QUESTIONABLE",
    "Doubtful": "DOUBTFUL",
    "Out": "OUT",
    "IR": "IR",
    "PUP-P": "PUP",
    "PUP-R": "PUP",
    "NA": "ACTIVE",
    "DNP": "OUT",
}


def _normalize_injury_status(raw: str | None) -> str:
    if raw in _INJURY_STATUS_MAP:
        return _INJURY_STATUS_MAP[raw]
    return raw.upper() if raw else "ACTIVE"


def fetch_season_projections(year: int = 2025, limit: int = 300) -> list[dict]:
    """
    Fetch week-1 projections and scale by 16 as a season-total proxy.

    Returns the top `limit` players by projected points. Uses sequential
    requests with a 5-second timeout each to keep memory and CPU usage low.

    Raises requests.HTTPError if either endpoint fails.
    """
    # 1. Fetch week-1 projections (one sequential request).
    url = f"{SLEEPER_BASE}/projections/nfl/{year}/1"
    resp = requests.get(url, params={"season_type": "regular"}, timeout=5)
    resp.raise_for_status()
    week_data: list[dict] = resp.json() or []

    # 2. Build {player_id: estimated_season_points}; skip players with no pts.
    player_pts: dict[str, float] = {}
    for entry in week_data:
        pid = entry.get("player_id", "")
        if not pid:
            continue
        pts = (entry.get("stats") or {}).get(SCORING_FIELD, 0.0) or 0.0
        if pts > 0.0:
            player_pts[pid] = pts * SEASON_SCALE

    # 3. Narrow to top `limit` player IDs before loading metadata so we don't
    #    iterate over thousands of irrelevant entries.
    top_pids = sorted(player_pts, key=lambda p: player_pts[p], reverse=True)[:limit]
    top_pts = {pid: player_pts[pid] for pid in top_pids}

    # 4. Fetch player metadata for names, positions, bye weeks, injury status.
    meta_resp = requests.get(f"{SLEEPER_BASE}/v1/players/nfl", timeout=5)
    meta_resp.raise_for_status()
    player_meta: dict[str, dict] = meta_resp.json() or {}

    # 5. Build player records, filtering to fantasy-relevant positions.
    players: list[dict] = []
    for pid in top_pids:
        meta = player_meta.get(pid, {})
        position = meta.get("position") or ""
        if position not in FANTASY_POSITIONS:
            continue

        team = meta.get("team") or (pid if position == "DEF" else "FA")
        full_name = meta.get("full_name") or (
            f"{meta.get('first_name', '')} {meta.get('last_name', '')}".strip() or pid
        )

        players.append({
            "sleeper_id": pid,
            "name": full_name,
            "first_name": meta.get("first_name", ""),
            "last_name": meta.get("last_name", ""),
            "position": position,
            "team": team,
            "projected_points": round(top_pts[pid], 2),
            "bye_week": meta.get("bye_week"),
            "injury_status": _normalize_injury_status(meta.get("injury_status")),
        })

    # Free the large metadata dict as soon as we're done with it.
    del player_meta

    players.sort(key=lambda p: p["projected_points"], reverse=True)
    logger.info(
        "Sleeper projections fetched: %d players for %d (week-1 × %d proxy)",
        len(players), year, SEASON_SCALE,
    )
    return players
