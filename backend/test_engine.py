"""
Standalone test script for the recommendation engine and Sleeper projections module.
Run from the backend/ directory: python test_engine.py

Mock targets note: ranker.py imports the espn_projections MODULE (not the function),
so mock.patch("projections.espn_projections.get_projections") patches the attribute
on the module object and correctly intercepts calls made through _espn.get_projections().
espn_projections.py is a compatibility shim over sleeper_projections.py.
"""
from __future__ import annotations

import sys
import unittest.mock as mock

# ---------------------------------------------------------------------------
# Minimal test harness (no pytest needed)
# ---------------------------------------------------------------------------

_passed = 0
_failed = 0


def _assert(label: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        print(f"  PASS  {label}")
        _passed += 1
    else:
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _failed += 1


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# Shared mock projection pool (stands in for ESPN API across all tests)
# ---------------------------------------------------------------------------
#
# 12-team league, standard slots: QB x1, RB x2, WR x2, TE x1, FLEX x1.
# Replacement ranks from config defaults:
#   QB  = 12th ranked QB   (12 teams x 1 starter)
#   RB  = 30th ranked RB   (12 teams x 2.5 effective starters with FLEX)
#   WR  = 29th ranked WR   (12 teams x ~2.4 effective starters with FLEX)
#   TE  = 13th ranked TE   (12 teams x ~1.1 effective starters with FLEX)

def _make_pool() -> list[dict]:
    pool = []

    # QBs: 16 players, projected pts descending from 400 (step -15)
    for i in range(16):
        pool.append({
            "name": f"QB Player {i+1:02d}",
            "position": "QB",
            "team": "KC" if i == 0 else f"T{i}",
            "projected_points": 400.0 - i * 15.0,
            "bye_week": (i % 14) + 1,
            "injury_status": "ACTIVE",
        })

    # RBs: 35 players, projected pts descending from 310 (step -7)
    for i in range(35):
        pool.append({
            "name": f"RB Player {i+1:02d}",
            "position": "RB",
            "team": f"T{i}",
            "projected_points": 310.0 - i * 7.0,
            "bye_week": (i % 14) + 1,
            "injury_status": "ACTIVE",
        })

    # WRs: 34 players, projected pts descending from 290 (step -6)
    for i in range(34):
        pool.append({
            "name": f"WR Player {i+1:02d}",
            "position": "WR",
            "team": f"T{i}",
            "projected_points": 290.0 - i * 6.0,
            "bye_week": (i % 14) + 1,
            "injury_status": "ACTIVE",
        })

    # TEs: 18 players, projected pts descending from 220 (step -10)
    for i in range(18):
        pool.append({
            "name": f"TE Player {i+1:02d}",
            "position": "TE",
            "team": f"T{i}",
            "projected_points": 220.0 - i * 10.0,
            "bye_week": (i % 14) + 1,
            "injury_status": "ACTIVE",
        })

    # Ks and DEFs (low VOR, usually drafted last)
    for i in range(14):
        pool.append({
            "name": f"K Player {i+1:02d}",
            "position": "K",
            "team": f"T{i}",
            "projected_points": 140.0 - i * 5.0,
            "bye_week": (i % 14) + 1,
            "injury_status": "ACTIVE",
        })
        pool.append({
            "name": f"DEF Player {i+1:02d}",
            "position": "DEF",
            "team": f"T{i}",
            "projected_points": 130.0 - i * 5.0,
            "bye_week": (i % 14) + 1,
            "injury_status": "ACTIVE",
        })

    return pool


MOCK_POOL = _make_pool()


# ===========================================================================
# SECTION 1: VOR math
# ===========================================================================

section("1. VOR MATH (vor.py)")

import recommendation_engine.config as cfg
from recommendation_engine.vor import (
    apply_playoff_weight,
    calculate_vor,
    compute_replacement_levels,
    compute_replacement_ranks,
    playoff_weight_factor,
)

ranks = compute_replacement_ranks(cfg)
print(f"\n  Replacement ranks (12 teams, standard slots):")
for pos, rank in sorted(ranks.items()):
    print(f"    {pos:4s} -> {rank:2d}th ranked player sets baseline")

_assert("QB replacement rank = 12  (12 teams x 1 starter)", ranks["QB"] == 12,
        f"got {ranks['QB']}")
_assert("RB replacement rank = 30  (12 teams x 2.5 effective starters)", ranks["RB"] == 30,
        f"got {ranks['RB']}")
_assert("WR replacement rank = 29  (12 teams x ~2.4 effective starters)", ranks["WR"] == 29,
        f"got {ranks['WR']}")
_assert("TE replacement rank = 13  (12 teams x ~1.1 effective starters)", ranks["TE"] == 13,
        f"got {ranks['TE']}")

levels = compute_replacement_levels(MOCK_POOL, ranks)
print(f"\n  Replacement level projected points:")
for pos, pts in sorted(levels.items()):
    print(f"    {pos:4s} -> {pts:.1f} pts  (baseline for VOR)")

# QB 12th: 400 - 11*15 = 235
_assert("QB replacement level = 235.0  (12th QB)", abs(levels["QB"] - 235.0) < 0.1,
        f"got {levels['QB']}")
# RB 30th: 310 - 29*7 = 107
_assert("RB replacement level = 107.0  (30th RB)", abs(levels["RB"] - 107.0) < 0.1,
        f"got {levels['RB']}")

# VOR: #1 QB (400 pts) -> 400 - 235 = 165
top_qb = {"position": "QB", "projected_points": 400.0}
vor_qb = calculate_vor(top_qb, levels)
_assert("VOR for 400-pt QB = 165.0", abs(vor_qb - 165.0) < 0.1, f"got {vor_qb}")

# VOR: below-replacement QB
below_repl = {"position": "QB", "projected_points": 200.0}
vor_below = calculate_vor(below_repl, levels)
_assert("VOR for below-replacement QB is negative", vor_below < 0, f"got {vor_below}")

# Playoff weight factor
pw = playoff_weight_factor(cfg)
playoff_weeks = cfg.TOTAL_SEASON_WEEKS - cfg.PLAYOFF_START_WEEK + 1
print(f"\n  Playoff weight factor: {pw:.4f}")
print(f"    ({playoff_weeks} playoff weeks at {cfg.PLAYOFF_MULTIPLIER}x,"
      f" blended across {cfg.TOTAL_SEASON_WEEKS} total weeks)")
_assert("Playoff factor is between 1.0 and PLAYOFF_MULTIPLIER",
        1.0 < pw < cfg.PLAYOFF_MULTIPLIER, f"got {pw}")

adj_vor = apply_playoff_weight(100.0, pw)
_assert("Playoff-adjusted VOR > base VOR", adj_vor > 100.0, f"got {adj_vor}")
print(f"    100.0 VOR -> {adj_vor:.2f} playoff-adjusted")

# Replacement level override
import types
cfg_override = types.SimpleNamespace(
    **{k: getattr(cfg, k) for k in dir(cfg) if not k.startswith("_")}
)
cfg_override.REPLACEMENT_LEVEL_OVERRIDE = {"QB": 8}
ranks_override = compute_replacement_ranks(cfg_override)
_assert("REPLACEMENT_LEVEL_OVERRIDE forces QB rank to 8", ranks_override["QB"] == 8,
        f"got {ranks_override['QB']}")


# ===========================================================================
# SECTION 2: Roster need bonus / saturation penalty
# ===========================================================================

section("2. ROSTER NEED (roster.py)")

from recommendation_engine.roster import roster_need_bonus, unfilled_starting_positions

# Empty roster
bonus = roster_need_bonus("QB", [], cfg)
_assert(f"Empty roster: QB bonus = +{cfg.NEED_STARTER_BONUS}", bonus == cfg.NEED_STARTER_BONUS,
        f"got {bonus}")

# 1 QB on roster (starter filled, bench slot still open)
bonus = roster_need_bonus("QB", [{"position": "QB"}], cfg)
_assert("1 QB on roster (starter filled, bench empty): bonus = 0.0", bonus == 0.0,
        f"got {bonus}")

# 2 QBs on roster (starter + 1 bench target = saturated for QB)
bonus = roster_need_bonus("QB", [{"position": "QB"}, {"position": "QB"}], cfg)
_assert(f"2 QBs on roster (saturated): penalty = -{cfg.POSITION_SATURATION_PENALTY}",
        bonus == -cfg.POSITION_SATURATION_PENALTY, f"got {bonus}")

# RB: 2 starters + 2 bench = saturated at 4 total
bonus = roster_need_bonus("RB", [{"position": "RB"}] * 4, cfg)
_assert("4 RBs on roster (2 starters + 2 bench): saturated",
        bonus == -cfg.POSITION_SATURATION_PENALTY, f"got {bonus}")

bonus = roster_need_bonus("RB", [{"position": "RB"}] * 3, cfg)
_assert("3 RBs on roster (2 starters + 1 bench): still useful, bonus = 0.0",
        bonus == 0.0, f"got {bonus}")

bonus = roster_need_bonus("RB", [{"position": "RB"}], cfg)
_assert("1 RB on roster: starter slot still open, bonus = +8.0",
        bonus == cfg.NEED_STARTER_BONUS, f"got {bonus}")

# unfilled_starting_positions
unfilled = unfilled_starting_positions([], cfg)
print(f"\n  Unfilled positions on empty roster: {unfilled}")
_assert("Empty roster has unfilled QB", "QB" in unfilled)
_assert("Empty roster has unfilled RB", "RB" in unfilled)

partial = [{"position": "QB"}, {"position": "RB"}, {"position": "RB"}]
unfilled2 = unfilled_starting_positions(partial, cfg)
_assert("QB filled -> not in unfilled", "QB" not in unfilled2, f"unfilled: {unfilled2}")
_assert("RB filled -> not in unfilled", "RB" not in unfilled2, f"unfilled: {unfilled2}")
_assert("WR still unfilled", "WR" in unfilled2, f"unfilled: {unfilled2}")

# Yahoo display_position format (must not crash)
roster_need_bonus("QB,K", [{"display_position": "QB,K"}], cfg)
_assert("Yahoo 'QB,K' display_position parses without crash", True)


# ===========================================================================
# SECTION 3: Flags - bye conflicts and injury
# ===========================================================================

section("3. FLAGS (flags.py)")

from recommendation_engine.flags import (
    check_bye_conflict,
    check_injury_flag,
    check_injury_penalized,
    collect_flags,
)

player_bye9 = {"name": "Test WR", "position": "WR", "bye_week": 9, "injury_status": "ACTIVE"}

# Bye conflict threshold is 2 (from config)
_assert("1 WR sharing bye week -> NO conflict (threshold=2)",
        not check_bye_conflict(player_bye9, [{"position": "WR", "bye_week": 9}], cfg))

two_wr_bye9 = [{"position": "WR", "bye_week": 9}, {"position": "WR", "bye_week": 9}]
_assert("2 WRs sharing bye week -> conflict triggered",
        check_bye_conflict(player_bye9, two_wr_bye9, cfg))

two_qb_bye9 = [{"position": "QB", "bye_week": 9}, {"position": "QB", "bye_week": 9}]
_assert("2 QBs on bye 9 do NOT trigger WR conflict",
        not check_bye_conflict(player_bye9, two_qb_bye9, cfg))

_assert("Player with bye_week=None -> no conflict",
        not check_bye_conflict(
            {"name": "X", "position": "WR", "bye_week": None, "injury_status": "ACTIVE"},
            two_wr_bye9, cfg
        ))

# Injury status checks
for status in ["OUT", "IR", "PUP", "SUSP"]:
    p = {"injury_status": status}
    _assert(f"Status '{status}' -> flagged AND penalized",
            check_injury_flag(p, cfg) and check_injury_penalized(p, cfg))

_assert("Status 'QUESTIONABLE' -> flagged but NOT penalized",
        check_injury_flag({"injury_status": "QUESTIONABLE"}, cfg)
        and not check_injury_penalized({"injury_status": "QUESTIONABLE"}, cfg))

_assert("Status 'ACTIVE' -> not flagged, not penalized",
        not check_injury_flag({"injury_status": "ACTIVE"}, cfg)
        and not check_injury_penalized({"injury_status": "ACTIVE"}, cfg))

# collect_flags output
bad_player = {"name": "Hurt WR", "position": "WR", "bye_week": 9, "injury_status": "OUT"}
flags = collect_flags(bad_player, two_wr_bye9, cfg)
print(f"\n  Flags for injured WR with bye conflict: {flags}")
_assert("collect_flags returns both bye_conflict and injury flags", len(flags) == 2)
_assert("Bye flag contains week number", any("week 9" in f for f in flags))
_assert("Injury flag contains status string", any("OUT" in f for f in flags))

_assert("Healthy player with no conflicts -> empty flags",
        collect_flags({"name": "OK", "position": "WR", "bye_week": 7, "injury_status": "ACTIVE"},
                      two_wr_bye9, cfg) == [])


# ===========================================================================
# SECTION 4: Full ranker - end-to-end with mock ESPN data
# ===========================================================================

section("4. FULL RANKER -- end-to-end with mock projections (ranker.py)")

from recommendation_engine.ranker import rank_players

# 6 available players as Yahoo would supply them (display_position, string bye_week)
available = [
    {"name": "QB Player 01", "display_position": "QB", "team": "KC",  "bye_week": "1"},
    {"name": "RB Player 01", "display_position": "RB", "team": "T0",  "bye_week": "1"},
    {"name": "WR Player 01", "display_position": "WR", "team": "T0",  "bye_week": "1"},
    {"name": "TE Player 01", "display_position": "TE", "team": "T0",  "bye_week": "1"},
    {"name": "RB Player 30", "display_position": "RB", "team": "T29", "bye_week": "2"},  # near replacement level
    {"name": "QB Player 14", "display_position": "QB", "team": "T13", "bye_week": "2"},  # below replacement level
]

# -- Empty roster, round 1 pick --
with mock.patch("projections.espn_projections.get_projections", return_value=MOCK_POOL):
    result = rank_players(available_players=available, my_roster=[], num_teams=12,
                          round_number=1, pick_number=1)

best = result["best_pick"]
ranked = result["ranked_list"]

print(f"\n  Best pick: {best['name']}  ({best['position']}, {best['team']})")
print(f"    Projected pts:    {best['projected_points']}")
print(f"    VOR:              {best['vor']}")
print(f"    Playoff-adj VOR:  {best['playoff_adjusted_vor']}")
print(f"    Flags:            {best['flags']}")
print(f"    Reasoning:        {best['reasoning']}")

print(f"\n  Ranked list (alphabetical by last name, top {cfg.RECOMMENDATION_LIST_SIZE}):")
for i, p in enumerate(ranked, 1):
    flag_str = f"  flags={p['flags']}" if p["flags"] else ""
    print(f"    {i}. {p['name']:<22s} {p['position']:4s} {p['team']:4s}"
          f"  pts={p['projected_points']:5.1f}  VOR={p['vor']:7.2f}"
          f"  pa_VOR={p['playoff_adjusted_vor']:7.2f}{flag_str}")

_assert("Best pick (empty roster, round 1) is RB Player 01 (VOR 203 beats QB VOR 165)",
        best["name"] == "RB Player 01", f"got {best['name']}")
_assert("Best pick position is RB", best["position"] == "RB")
_assert("Reasoning is a non-empty string",
        isinstance(best["reasoning"], str) and len(best["reasoning"]) > 10)
_assert(f"Ranked list has <= {cfg.RECOMMENDATION_LIST_SIZE} entries",
        len(ranked) <= cfg.RECOMMENDATION_LIST_SIZE)
_assert("Ranked list is alphabetical by last name",
        ranked == sorted(ranked, key=lambda p: p["name"].split()[-1].lower()))
_assert("Below-replacement QB (Player 14) has negative VOR",
        any(p["name"] == "QB Player 14" and p["vor"] < 0 for p in ranked),
        f"VORs: {[(p['name'], p['vor']) for p in ranked]}")

# -- Roster need shifts pick when QB already rostered --
print(f"\n  Re-ranking with QB already on roster...")
roster_with_qb = [{"name": "Some QB", "display_position": "QB", "team": "XX", "bye_week": "5"}]
with mock.patch("projections.espn_projections.get_projections", return_value=MOCK_POOL):
    result2 = rank_players(available_players=available, my_roster=roster_with_qb, num_teams=12)
best2 = result2["best_pick"]
print(f"  Best pick (QB on roster): {best2['name']}  ({best2['position']})")
_assert("Best pick is a skill position player",
        best2["position"] in ("QB", "RB", "WR", "TE"))

# -- Bye conflict penalty --
print(f"\n  Testing bye conflict penalty...")
roster_two_rb_bye1 = [
    {"name": "Roster RB A", "display_position": "RB", "team": "XX", "bye_week": "1"},
    {"name": "Roster RB B", "display_position": "RB", "team": "YY", "bye_week": "1"},
]
with mock.patch("projections.espn_projections.get_projections", return_value=MOCK_POOL):
    result3 = rank_players(available_players=available, my_roster=roster_two_rb_bye1, num_teams=12)
ranked3 = result3["ranked_list"]
rb1_entry = next((p for p in ranked3 if p["name"] == "RB Player 01"), None)
if rb1_entry:
    print(f"  RB Player 01 (bye wk 1, conflict): flags={rb1_entry['flags']}")
    _assert("RB Player 01 gets bye_conflict flag",
            any("bye_conflict" in f for f in (rb1_entry["flags"] or [])))
else:
    _assert("RB Player 01 present in ranked list", False, "not found")

# -- Injury penalty --
print(f"\n  Testing injury penalty...")
pool_injured_qb = [
    {**p, "injury_status": "OUT"} if p["name"] == "QB Player 01" else p
    for p in MOCK_POOL
]
with mock.patch("projections.espn_projections.get_projections", return_value=pool_injured_qb):
    result4 = rank_players(available_players=available, my_roster=[], num_teams=12)
ranked4 = result4["ranked_list"]
best4 = result4["best_pick"]
qb1_entry = next((p for p in ranked4 if p["name"] == "QB Player 01"), None)
if qb1_entry:
    print(f"  QB Player 01 (injured OUT): flags={qb1_entry['flags']}")
    _assert("Injured QB Player 01 has injury flag",
            any("injury" in f for f in (qb1_entry["flags"] or [])))
print(f"  Best pick with QB injured: {best4['name']}  ({best4['position']})")
_assert("Injured QB is no longer the best pick",
        best4["name"] != "QB Player 01")

# -- num_teams override --
print(f"\n  Testing num_teams override (8-team league)...")
with mock.patch("projections.espn_projections.get_projections", return_value=MOCK_POOL):
    result5 = rank_players(available_players=available, my_roster=[], num_teams=8)
best5 = result5["best_pick"]
_assert("8-team num_teams override accepted without error", best5 is not None)
print(f"  Best pick (8-team): {best5['name']} VOR={best5['vor']}")
# In an 8-team league, replacement level is the 20th RB (177 pts) instead of 30th (107 pts).
# A higher baseline means elite player VOR is lower in smaller leagues.
_assert("VOR is lower with 8 teams than 12 (smaller league = better replacement baseline)",
        best5["vor"] <= best["vor"])


# ===========================================================================
# SECTION 5: Sleeper projections module (mock HTTP + optional live call)
# ===========================================================================

section("5. SLEEPER PROJECTIONS MODULE (sleeper_projections.py)")

import requests
from projections.espn_projections import fetch_season_projections, get_projections
import projections.espn_projections as espn_mod
import projections.sleeper_projections as sleeper_mod

# --- Mock data ---
_MOCK_PLAYERS_META = {
    "4046": {
        "full_name": "Patrick Mahomes",
        "first_name": "Patrick",
        "last_name": "Mahomes",
        "position": "QB",
        "team": "KC",
        "bye_week": 10,
        "injury_status": None,
    },
    "4035": {
        "full_name": "Saquon Barkley",
        "first_name": "Saquon",
        "last_name": "Barkley",
        "position": "RB",
        "team": "PHI",
        "bye_week": 5,
        "injury_status": "Questionable",
    },
    "9999": {
        "full_name": "Bench Warmer",
        "first_name": "Bench",
        "last_name": "Warmer",
        "position": "P",   # punter — not in FANTASY_POSITIONS, should be filtered
        "team": "NE",
        "bye_week": 7,
        "injury_status": None,
    },
}

# Two weeks of non-zero projections; all other weeks return [].
_MOCK_WEEK1 = [
    {"player_id": "4046", "stats": {"pts_half_ppr": 25.0}},
    {"player_id": "4035", "stats": {"pts_half_ppr": 18.0}},
    {"player_id": "9999", "stats": {"pts_half_ppr": 3.0}},
]
_MOCK_WEEK2 = [
    {"player_id": "4046", "stats": {"pts_half_ppr": 22.0}},
    {"player_id": "4035", "stats": {"pts_half_ppr": 20.0}},
]


def _sleeper_mock_get(url, **kwargs):
    r = mock.MagicMock()
    r.raise_for_status = lambda: None
    r.status_code = 200
    if url.endswith("/players/nfl"):
        r.json.return_value = _MOCK_PLAYERS_META
    elif url.endswith("/2025/1"):
        r.json.return_value = _MOCK_WEEK1
    elif url.endswith("/2025/2"):
        r.json.return_value = _MOCK_WEEK2
    else:
        r.json.return_value = []   # empty for weeks 3-18
    return r


# --- Full parse from mocked HTTP ---
with mock.patch("requests.get", side_effect=_sleeper_mock_get):
    players = fetch_season_projections(year=2025)

print(f"\n  fetch_season_projections() with mocked HTTP:")
for p in players:
    print(f"    {p['name']:<22s} {p['position']:4s} {p['team']:4s}"
          f"  pts={p['projected_points']:6.1f}  bye={p['bye_week']}"
          f"  status={p['injury_status']}")

_assert("Returns 2 players (non-fantasy position filtered out)",
        len(players) == 2, f"got {len(players)}")

mahomes = next((p for p in players if "Mahomes" in p["name"]), None)
_assert("Patrick Mahomes present", mahomes is not None)
_assert("Mahomes position = QB",                mahomes and mahomes["position"] == "QB")
_assert("Mahomes team = KC",                    mahomes and mahomes["team"] == "KC")
_assert("Mahomes projected_points = 47.0 (sum of wk1+wk2)",
        mahomes and abs(mahomes["projected_points"] - 47.0) < 0.01,
        f"got {mahomes and mahomes['projected_points']}")
_assert("Mahomes bye week = 10",                mahomes and mahomes["bye_week"] == 10,
        f"got {mahomes and mahomes['bye_week']}")
_assert("Mahomes injury_status = ACTIVE",       mahomes and mahomes["injury_status"] == "ACTIVE")

barkley = next((p for p in players if "Barkley" in p["name"]), None)
_assert("Barkley present", barkley is not None)
_assert("Barkley projected_points = 38.0 (sum of wk1+wk2)",
        barkley and abs(barkley["projected_points"] - 38.0) < 0.01,
        f"got {barkley and barkley['projected_points']}")
_assert("Barkley injury_status normalized to QUESTIONABLE",
        barkley and barkley["injury_status"] == "QUESTIONABLE")

# --- Cache behavior ---
print(f"\n  Testing cache behavior...")
espn_mod._cache = None
espn_mod._cache_year = None
espn_mod._cache_timestamp = 0.0

with mock.patch("projections.espn_projections.fetch_season_projections",
                return_value=players) as mock_fetch:
    get_projections(year=2025, cache_ttl=60)
    get_projections(year=2025, cache_ttl=60)  # should hit cache
    _assert("fetch_season_projections called exactly once (cache hit on 2nd call)",
            mock_fetch.call_count == 1, f"call count: {mock_fetch.call_count}")

# --- Graceful degradation on fetch failure ---
espn_mod._cache = None
espn_mod._cache_timestamp = 0.0
with mock.patch("projections.espn_projections.fetch_season_projections",
                side_effect=Exception("connection timeout")):
    degraded = get_projections(year=2025)
    _assert("Sleeper fetch failure returns empty list (graceful degradation)",
            degraded == [])


# ===========================================================================
# SECTION 6 (optional): Live Sleeper API call
# ===========================================================================

section("6. LIVE SLEEPER API (optional)")

import os
if os.environ.get("TEST_LIVE_SLEEPER", "").lower() in ("1", "true", "yes"):
    print("\n  Making live request to Sleeper API...")
    espn_mod._cache = None
    try:
        live_players = fetch_season_projections(year=2025, limit=50)
        if live_players:
            top5 = sorted(live_players, key=lambda p: p["projected_points"], reverse=True)[:5]
            print(f"\n  Top 5 by projected points (live data):")
            for p in top5:
                print(f"    {p['name']:<22s} {p['position']:4s} {p['team']:4s}"
                      f"  pts={p['projected_points']:6.1f}  bye={p['bye_week']}")
            _assert("Live Sleeper call returns players", len(live_players) > 0)
        else:
            print("  WARNING: API returned 0 players.")
            print("  Preseason projections may not yet be loaded for this season.")
    except requests.HTTPError as e:
        print(f"  HTTP error: {e}")
    except Exception as e:
        print(f"  Error: {e}")
else:
    print("\n  Skipped (no live HTTP call made).")
    print("  To run with real Sleeper data: TEST_LIVE_SLEEPER=1 python test_engine.py")


# ===========================================================================
# Summary
# ===========================================================================

total = _passed + _failed
print(f"\n{'='*60}")
print(f"  Results: {_passed}/{total} passed", end="")
if _failed:
    print(f"  ({_failed} FAILED)")
else:
    print("  -- all green")
print(f"{'='*60}\n")

if _failed:
    sys.exit(1)
