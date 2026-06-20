import requests
from flask import Blueprint, jsonify, request

draft_bp = Blueprint("draft", __name__)

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


def _flatten_list_of_dicts(items: list) -> dict:
    merged = {}
    for item in items:
        if isinstance(item, dict):
            merged.update(item)
    return merged


@draft_bp.get("/leagues/<league_key>/draft")
def get_draft(league_key):
    token, err = _require_token(request)
    if err:
        return err

    draft_resp = _yahoo_get(f"/league/{league_key}/draftresults", token)
    if draft_resp.status_code != 200:
        return jsonify({"error": "Failed to fetch draft", "details": draft_resp.text}), draft_resp.status_code

    draft_data = draft_resp.json()

    # Also fetch teams to identify the current user's team
    teams_resp = _yahoo_get(f"/league/{league_key}/teams", token)
    teams_by_key: dict[str, str] = {}
    my_team_key: str | None = None

    if teams_resp.status_code == 200:
        try:
            league_arr = teams_resp.json()["fantasy_content"]["league"]
            league_info = league_arr[0]
            teams_raw = league_arr[1].get("teams", {})

            for i in range(teams_raw.get("count", 0)):
                team_arr = teams_raw[str(i)]["team"]
                info = _flatten_list_of_dicts(team_arr[0])
                team_key = info.get("team_key", "")
                team_name = info.get("name", "")
                teams_by_key[team_key] = team_name

                managers = info.get("managers", {})
                for m in range(managers.get("count", 0) if isinstance(managers, dict) else 0):
                    mgr = managers.get(str(m), {}).get("manager", {})
                    if str(mgr.get("is_current_login", "0")) == "1":
                        my_team_key = team_key
        except (KeyError, IndexError, TypeError):
            pass

    try:
        league_arr = draft_data["fantasy_content"]["league"]
        league_info = league_arr[0]
        draft_results = league_arr[1].get("draft_results", {})
        picks = []

        for i in range(draft_results.get("count", 0)):
            pick = draft_results[str(i)]["draft_result"]
            team_key = pick.get("team_key", "")
            picks.append(
                {
                    "pick": pick.get("pick"),
                    "round": pick.get("round"),
                    "team_key": team_key,
                    "team_name": teams_by_key.get(team_key, team_key),
                    "player_key": pick.get("player_key"),
                    "is_mine": team_key == my_team_key,
                }
            )

        return jsonify(
            {
                "picks": picks,
                "total_picks": len(picks),
                "num_teams": league_info.get("num_teams"),
                "draft_status": league_info.get("draft_status"),
                "my_team_key": my_team_key,
                "teams": teams_by_key,
            }
        )
    except (KeyError, IndexError, TypeError) as exc:
        return jsonify({"error": f"Parse error: {exc}", "raw": draft_data}), 500
