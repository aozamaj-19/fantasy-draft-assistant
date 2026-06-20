import random

from flask import Blueprint, jsonify, request

from projections.espn_projections import get_projections

mock_draft_bp = Blueprint("mock_draft", __name__)


def _format_player(p: dict) -> dict:
    """Convert Sleeper projection dict to the mock-draft player format used by both
    the frontend and the recommendation engine."""
    return {
        "player_key": f"sleeper_{p['sleeper_id']}",
        "player_id": str(p["sleeper_id"]),
        "name": p["name"],
        "team": p["team"],
        "display_position": p["position"],
        "position": p["position"],
        "projected_points": p["projected_points"],
        "bye_week": p.get("bye_week"),
        "injury_status": p.get("injury_status", "ACTIVE"),
        "status": p.get("injury_status", ""),
    }


@mock_draft_bp.get("/mock-draft/players")
def get_mock_players():
    """Return the Sleeper player pool sorted by projected points descending."""
    projections = get_projections()
    players = sorted(
        (_format_player(p) for p in projections),
        key=lambda p: p["projected_points"],
        reverse=True,
    )
    return jsonify({"players": players})


@mock_draft_bp.post("/mock-draft/simulate")
def simulate_picks():
    """
    Simulate auto-draft picks for other teams.

    Input:  { available_players: list, num_picks: int }
    Output: { auto_picked: list }

    For each pick: sort available by projected_points, then randomly select
    from the top 3 with weights [3, 2, 1] to add slight variance.
    """
    body = request.get_json(force=True)
    available: list[dict] = list(body.get("available_players", []))
    num_picks: int = int(body.get("num_picks", 1))

    auto_picked: list[dict] = []
    for _ in range(num_picks):
        if not available:
            break
        available.sort(key=lambda p: p.get("projected_points", 0), reverse=True)
        top_n = min(3, len(available))
        weights = [3, 2, 1][:top_n]
        idx = random.choices(range(top_n), weights=weights, k=1)[0]
        picked = available.pop(idx)
        auto_picked.append(picked)

    return jsonify({"auto_picked": auto_picked})
