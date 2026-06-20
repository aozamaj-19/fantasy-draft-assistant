import base64
import os

import requests
from flask import Blueprint, jsonify, request

auth_bp = Blueprint("auth", __name__)

YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"


def _basic_auth_header() -> str:
    client_id = os.environ["YAHOO_CLIENT_ID"]
    client_secret = os.environ["YAHOO_CLIENT_SECRET"]
    print(f"[auth] YAHOO_CLIENT_ID={client_id[:6]}...{client_id[-6:]}", flush=True)
    return base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()


@auth_bp.post("/auth/token")
def exchange_token():
    body = request.get_json(force=True)
    code = body.get("code")
    code_verifier = body.get("code_verifier")
    redirect_uri = body.get("redirect_uri")

    if not code or not redirect_uri:
        return jsonify({"error": "Missing code or redirect_uri"}), 400

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if code_verifier:
        payload["code_verifier"] = code_verifier

    resp = requests.post(
        YAHOO_TOKEN_URL,
        headers={
            "Authorization": f"Basic {_basic_auth_header()}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=payload,
        timeout=10,
    )

    if resp.status_code != 200:
        print(f"[Yahoo token exchange] status={resp.status_code} body={resp.text}", flush=True)
        return jsonify({"error": "Token exchange failed", "details": resp.text}), 400

    return jsonify(resp.json())


@auth_bp.post("/auth/refresh")
def refresh_token():
    body = request.get_json(force=True)
    refresh_tok = body.get("refresh_token")
    redirect_uri = body.get("redirect_uri")

    if not refresh_tok or not redirect_uri:
        return jsonify({"error": "Missing refresh_token or redirect_uri"}), 400

    resp = requests.post(
        YAHOO_TOKEN_URL,
        headers={
            "Authorization": f"Basic {_basic_auth_header()}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_tok,
            "redirect_uri": redirect_uri,
        },
        timeout=10,
    )

    if resp.status_code != 200:
        print(f"[Yahoo token refresh] status={resp.status_code} body={resp.text}", flush=True)
        return jsonify({"error": "Token refresh failed", "details": resp.text}), 400

    return jsonify(resp.json())
