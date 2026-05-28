import json
import os
import sys

# make shared layer importable locally and on Lambda
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers/shared"))

from lastfm import validate_user, get_earliest_scrobble_timestamp, get_scrobbles_for_week
from chart import compute_all_weeks, get_all_week_starts, str_to_week_start, get_week_end
from db import (
    get_user, put_user, set_backfill_status,
    update_user_after_week, put_chart
)
from datetime import datetime, timezone


# ── entry point ───────────────────────────────────────────────────────────────

def handler(event, context):
    """
    Lambda entry point. Triggered by API Gateway when a new user
    enters their Last.fm username for the first time.

    Expected event body:
    { "username": "someuser" }
    """
    try:
        body     = json.loads(event.get("body", "{}"))
        username = body.get("username", "").strip().lower()

        if not username:
            return _response(400, {"error": "username is required"})

        # ── check if already backfilled ───────────────────────────────────────
        existing = get_user(username)
        if existing:
            status = existing.get("backfill_status")
            if status == "complete":
                return _response(200, {
                    "status":   "already_complete",
                    "username": username,
                })
            if status == "in_progress":
                return _response(200, {
                    "status":   "in_progress",
                    "username": username,
                })

        # ── validate username exists on last.fm ───────────────────────────────
        user_info = validate_user(username)
        if not user_info:
            return _response(404, {"error": "Last.fm user not found"})

        # ── create user record and mark in progress ───────────────────────────
        put_user(username, backfill_status="in_progress")
        set_backfill_status(username, "in_progress")

        # ── find earliest scrobble ────────────────────────────────────────────
        earliest_ts = get_earliest_scrobble_timestamp(username)
        if not earliest_ts:
            set_backfill_status(username, "complete")
            return _response(200, {
                "status":   "complete",
                "username": username,
                "message":  "no scrobble history found",
            })

        # ── fetch all scrobbles in bulk ───────────────────────────────────────
        all_scrobbles = _fetch_all_scrobbles(username, earliest_ts)

        # ── compute all weekly charts ─────────────────────────────────────────
        charts = compute_all_weeks(username, earliest_ts, all_scrobbles)

        # ── write charts to dynamodb ──────────────────────────────────────────
        for chart in charts:
            put_chart(
                username        = username,
                week_start      = chart["week_start"],
                entries         = chart["entries"],
                records_broken  = chart["records_broken"],
            )

        # ── update user metadata ──────────────────────────────────────────────
        if charts:
            put_user(
                username        = username,
                backfill_status = "complete",
                earliest_week   = charts[0]["week_start"],
                latest_week     = charts[-1]["week_start"],
                total_weeks     = len(charts),
            )
        else:
            set_backfill_status(username, "complete")

        return _response(200, {
            "status":      "complete",
            "username":    username,
            "total_weeks": len(charts),
            "earliest":    charts[0]["week_start"] if charts else None,
            "latest":      charts[-1]["week_start"] if charts else None,
        })

    except Exception as e:
        print(f"backfill error for {username}: {e}")
        set_backfill_status(username, "failed")
        return _response(500, {"error": "backfill failed", "detail": str(e)})


# ── bulk scrobble fetcher ─────────────────────────────────────────────────────

def _fetch_all_scrobbles(username: str, earliest_ts: int) -> list:
    """
    Fetches the user's complete scrobble history week by week and
    returns a flat list of all scrobbles.

    We fetch week by week rather than all at once because Last.fm's
    pagination caps at 200 per page and bulk fetching thousands of
    pages is slower and less reliable than bounded weekly windows.
    """
    from chart import get_all_week_starts, get_week_end, week_start_to_str
    from lastfm import get_scrobbles_for_week

    week_starts   = get_all_week_starts(earliest_ts)
    all_scrobbles = []

    for week_start in week_starts:
        week_end  = get_week_end(week_start)
        scrobbles = get_scrobbles_for_week(username, week_start, week_end)
        all_scrobbles.extend(scrobbles)

    return all_scrobbles


# ── response helper ───────────────────────────────────────────────────────────

def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type":                "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }