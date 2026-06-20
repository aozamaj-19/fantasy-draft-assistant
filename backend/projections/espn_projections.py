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
import time

from projections.sleeper_projections import fetch_season_projections  # noqa: F401

logger = logging.getLogger(__name__)

_cache: list[dict] | None = None
_cache_year: int | None = None
_cache_timestamp: float = 0.0


def get_projections(year: int = 2025, cache_ttl: int = 3600) -> list[dict]:
    """
    Return cached Sleeper projections, refreshing if older than cache_ttl seconds.

    Falls back to an empty list (with a warning) if Sleeper is unreachable,
    so the recommendation engine degrades gracefully rather than crashing.
    """
    global _cache, _cache_year, _cache_timestamp
    now = time.time()

    if (
        _cache is not None
        and _cache_year == year
        and (now - _cache_timestamp) < cache_ttl
    ):
        return _cache

    try:
        _cache = fetch_season_projections(year)
        _cache_year = year
        _cache_timestamp = now
    except Exception as exc:
        logger.warning(
            "Failed to fetch Sleeper projections: %s — using cached/empty data", exc
        )
        if _cache is None:
            _cache = []

    return _cache
