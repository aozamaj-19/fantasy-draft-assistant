import requests
from flask import Blueprint, jsonify, request

players_bp = Blueprint("players", __name__)

YAHOO_API_BASE = "https://fantasysports.yahooapis.com/fantasy/v2"


def _yahoo_get(path: str, access_token: str):
    return requests.get(
        f"{YAHOO_API_BASE}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"format": "json"},
        timeout=10,
    )


def _require_token(req):
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, (jsonify({"error": "Missing access token"}), 401)
    return auth[7:], None


def _parse_player(player_arr: list) -> dict:
    info = {}
    for item in player_arr[0]:
        if isinstance(item, dict):
            info.update(item)

    eligible_positions = []
    ep = info.get("eligible_positions", [])
    if isinstance(ep, list):
        eligible_positions = [p.get("position") for p in ep if isinstance(p, dict)]
    elif isinstance(ep, dict):
        eligible_positions = [ep.get("position")]

    return {
        "player_key": info.get("player_key"),
        "player_id": info.get("player_id"),
        "name": info.get("name", {}).get("full", ""),
        "team": info.get("editorial_team_abbr", ""),
        "display_position": info.get("display_position", ""),
        "eligible_positions": eligible_positions,
        "status": info.get("status", ""),
        "bye_week": info.get("bye_weeks", {}).get("week", ""),
    }


@players_bp.get("/leagues/<league_key>/players/by_keys")
def get_players_by_keys(league_key):
    token, err = _require_token(request)
    if err:
        return err

    keys = request.args.get("keys", "").strip()
    if not keys:
        return jsonify({"players": []})

    resp = _yahoo_get(f"/league/{league_key}/players;player_keys={keys}", token)

    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch players", "details": resp.text}), resp.status_code

    data = resp.json()

    try:
        players_raw = data["fantasy_content"]["league"][1]["players"]
        if isinstance(players_raw, dict):
            players_list = [
                _parse_player(players_raw[str(i)]["player"])
                for i in range(players_raw.get("count", 0))
            ]
        else:
            players_list = [_parse_player(p["player"]) for p in players_raw if isinstance(p, dict)]
        return jsonify({"players": players_list, "count": len(players_list)})
    except (KeyError, IndexError, TypeError) as exc:
        return jsonify({"error": f"Parse error: {exc}", "raw": data}), 500


@players_bp.get("/leagues/<league_key>/players")
def get_players(league_key):
    token, err = _require_token(request)
    if err:
        return err

    start = request.args.get("start", 0)
    count = request.args.get("count", 50)

    resp = _yahoo_get(
        f"/league/{league_key}/players;status=FA;sort=OR;count={count};start={start}",
        token,
    )

    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch players", "details": resp.text}), resp.status_code

    data = resp.json()

    try:
        players_raw = data["fantasy_content"]["league"][1]["players"]
        if isinstance(players_raw, dict):
            players_list = [
                _parse_player(players_raw[str(i)]["player"])
                for i in range(players_raw.get("count", 0))
            ]
        else:
            players_list = [_parse_player(p["player"]) for p in players_raw if isinstance(p, dict)]
        return jsonify({"players": players_list, "count": len(players_list)})
    except (KeyError, IndexError, TypeError) as exc:
        return jsonify({"error": f"Parse error: {exc}", "raw": data}), 500
