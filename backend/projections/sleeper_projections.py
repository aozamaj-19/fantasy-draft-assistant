"""
Fetches season-long player projections from Sleeper's public API (no auth required).

Season totals are built by summing weekly projections across all regular-season weeks,
since Sleeper does not expose a single season-total projection endpoint.

Swap this module for another projection source by implementing the same
fetch_season_projections(year, limit) -> list[dict] interface.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

logger = logging.getLogger(__name__)

SLEEPER_BASE = "https://api.sleeper.app"
# Half-PPR is most common in modern leagues. Change to "pts_ppr" or "pts_std" as needed.
SCORING_FIELD = "pts_half_ppr"
REGULAR_SEASON_WEEKS = 18
FANTASY_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "K", "DEF"})

# Sleeper uses Title Case; recommendation_engine expects uppercase ESPN-style strings.
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


def _fetch_week(year: int, week: int) -> list[dict]:
    """Fetch projections for one regular-season week. Returns [] on 404 or error."""
    url = f"{SLEEPER_BASE}/projections/nfl/{year}/{week}"
    try:
        resp = requests.get(url, params={"season_type": "regular"}, timeout=20)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json() or []
    except requests.RequestException as exc:
        logger.warning("Sleeper week %d fetch failed: %s", week, exc)
        return []


def fetch_season_projections(year: int = 2025, limit: int = 500) -> list[dict]:
    """
    Fetch season-long fantasy projections by summing Sleeper's weekly projections.

    Returns a list of player dicts:
      {
        sleeper_id: str,
        name: str,
        first_name: str,
        last_name: str,
        position: str,           # "QB", "RB", "WR", "TE", "K", "DEF"
        team: str,               # NFL team abbreviation, e.g. "KC"
        projected_points: float, # season total (sum of half-PPR weekly projections)
        bye_week: int | None,
        injury_status: str,      # normalized to ESPN-style uppercase, e.g. "ACTIVE"
      }

    Raises requests.HTTPError if the player metadata endpoint fails.
    Weekly fetch failures are silently skipped (logged at WARNING level).
    """
    # 1. Fetch player metadata for names, positions, teams, bye weeks, injury status.
    meta_resp = requests.get(f"{SLEEPER_BASE}/v1/players/nfl", timeout=30)
    meta_resp.raise_for_status()
    player_meta: dict[str, dict] = meta_resp.json() or {}

    # 2. Fetch all weeks in parallel and accumulate points per player.
    season_pts: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(_fetch_week, year, week): week
            for week in range(1, REGULAR_SEASON_WEEKS + 1)
        }
        for future in as_completed(futures):
            for entry in future.result():
                pid = entry.get("player_id", "")
                if not pid:
                    continue
                pts = (entry.get("stats") or {}).get(SCORING_FIELD, 0.0) or 0.0
                season_pts[pid] = season_pts.get(pid, 0.0) + pts

    # 3. Build player records, filtering to fantasy-relevant positions.
    players: list[dict] = []
    for pid, total_pts in season_pts.items():
        if total_pts <= 0.0:
            continue
        meta = player_meta.get(pid, {})
        position = meta.get("position") or ""
        if position not in FANTASY_POSITIONS:
            continue

        # DEF entries use the team abbreviation as their player_id in Sleeper.
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
            "projected_points": round(total_pts, 2),
            "bye_week": meta.get("bye_week"),
            "injury_status": _normalize_injury_status(meta.get("injury_status")),
        })

    players.sort(key=lambda p: p["projected_points"], reverse=True)
    logger.info("Sleeper projections fetched: %d players for %d season", len(players), year)
    return players[:limit]
