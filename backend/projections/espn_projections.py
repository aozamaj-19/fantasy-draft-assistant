"""
Compatibility shim — projection data is now sourced from Sleeper (sleeper_projections.py).

This module's name is kept so that recommendation_engine.ranker, which imports
`from projections import espn_projections as _espn`, continues to work without
any changes to the recommendation engine.

`fetch_season_projections` is imported here from sleeper_projections so that
mock.patch("projections.espn_projections.fetch_season_projections", ...) still
intercepts calls made by get_projections() in this module.
"""
from __future__ import annotations

import logging

from projections.sleeper_projections import fetch_season_projections  # noqa: F401

logger = logging.getLogger(__name__)

# Populated once at first request and held for the life of the server process.
_cache: list[dict] | None = None


def get_projections(year: int = 2025) -> list[dict]:
    """
    Return Sleeper projections, fetching once per server startup.

    Falls back to an empty list (with a warning) if Sleeper is unreachable,
    so the recommendation engine degrades gracefully rather than crashing.
    """
    global _cache
    if _cache is not None:
        return _cache

    try:
        _cache = fetch_season_projections(year)
    except Exception as exc:
        logger.warning(
            "Failed to fetch Sleeper projections: %s — returning empty list", exc
        )
        _cache = []

    return _cache
