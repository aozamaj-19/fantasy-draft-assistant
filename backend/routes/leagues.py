import requests
from flask import Blueprint, jsonify, request

leagues_bp = Blueprint("leagues", __name__)

YAHOO_API_BASE = "https://fantasysports.yahooapis.com/fantasy/v2"


def _yahoo_get(path: str, access_token: str):
    return requests.get(
        f"{YAHOO_API_BASE}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"format": "json"},
        timeout=10,
    )


def _require_token(req) -> tuple[str | None, object | None]:
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, (jsonify({"error": "Missing access token"}), 401)
    return auth[7:], None


@leagues_bp.get("/leagues")
def get_leagues():
    token, err = _require_token(request)
    if err:
        return err

    resp = _yahoo_get("/users;use_login=1/games;game_keys=nfl/leagues", token)

    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch leagues", "details": resp.text}), resp.status_code

    data = resp.json()

    try:
        users_data = data["fantasy_content"]["users"]
        user = users_data["0"]["user"]
        games = user[1]["games"]
        leagues_list = []

        for i in range(games.get("count", 0)):
            game_entry = games[str(i)]["game"]
            game_info = game_entry[0]
            leagues_data = game_entry[1].get("leagues", {})

            for j in range(leagues_data.get("count", 0)):
                league_arr = leagues_data[str(j)]["league"]
                league = league_arr[0]
                leagues_list.append(
                    {
                        "league_key": league.get("league_key"),
                        "name": league.get("name"),
                        "num_teams": league.get("num_teams"),
                        "draft_status": league.get("draft_status"),
                        "season": league.get("season"),
                        "game_code": game_info.get("code"),
                    }
                )

        return jsonify({"leagues": leagues_list})
    except (KeyError, IndexError, TypeError) as exc:
        return jsonify({"error": f"Parse error: {exc}", "raw": data}), 500
