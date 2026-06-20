from flask import Blueprint, jsonify, request

from recommendation_engine import rank_players

recommendations_bp = Blueprint("recommendations", __name__)


@recommendations_bp.post("/recommendations")
def get_recommendation():
    body = request.get_json(force=True)

    my_roster: list = body.get("my_roster", [])
    available_players: list = body.get("available_players", [])
    pick_number: int = body.get("pick_number", 1)
    round_number: int = body.get("round_number", 1)
    num_teams: int | None = body.get("num_teams")

    if not available_players:
        return jsonify({"error": "available_players is required"}), 400

    result = rank_players(
        available_players=available_players,
        my_roster=my_roster,
        num_teams=num_teams,
        round_number=round_number,
        pick_number=pick_number,
    )

    return jsonify({
        "best_pick": result["best_pick"],
        "ranked_list": result["ranked_list"],
        "pick_number": pick_number,
        "round_number": round_number,
    })
