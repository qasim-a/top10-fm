import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers/shared"))

from lastfm import validate_user as lastfm_validate_user
from db import get_user


# ── entry point ───────────────────────────────────────────────────────────────

def handler(event, context):
    """
    API Gateway endpoint. Validates a Last.fm username and returns
    basic user info plus their status in our system.

    Query parameters:
        username — required

    Returns:
        lastfm_info  — profile data from Last.fm
        system_status — whether this user has been backfilled before
    """
    try:
        params   = event.get("queryStringParameters") or {}
        username = params.get("username", "").strip().lower()

        if not username:
            return _response(400, {"error": "username is required"})

        # ── check last.fm first ───────────────────────────────────────────────
        lastfm_info = lastfm_validate_user(username)
        if not lastfm_info:
            return _response(404, {"error": "Last.fm user not found"})

        # ── check our system ──────────────────────────────────────────────────
        existing = get_user(username)

        if not existing:
            system_status = "new"
        else:
            system_status = existing.get("backfill_status", "unknown")

        return _response(200, {
            "username":      username,
            "lastfm_info":   lastfm_info,
            "system_status": system_status,
            "meta": {
                "earliest_week": existing.get("earliest_week") if existing else None,
                "latest_week":   existing.get("latest_week")   if existing else None,
                "total_weeks":   existing.get("total_weeks", 0) if existing else 0,
            }
        })

    except Exception as e:
        print(f"validate_user error: {e}")
        return _response(500, {"error": str(e)})


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type":                "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }