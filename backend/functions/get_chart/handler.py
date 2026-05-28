import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers/shared"))

from db import get_chart, get_all_weeks, get_latest_chart, get_user
from chart import week_start_to_str, get_week_start
from datetime import datetime, timezone


# ── entry point ───────────────────────────────────────────────────────────────

def handler(event, context):
    """
    API Gateway endpoint. Returns a single week's chart for a user.

    Query parameters:
        username  — required
        week      — optional ISO date string e.g. 2023-01-02
                    if omitted returns the latest stored week

    Also accepts:
        /chart?username=x&weeks=all
        returns the full list of available week strings for the week picker
    """
    try:
        params   = event.get("queryStringParameters") or {}
        username = params.get("username", "").strip().lower()
        week     = params.get("week",     "").strip()
        all_weeks = params.get("weeks",   "").strip()

        if not username:
            return _response(400, {"error": "username is required"})

        # ── check user exists and is ready ────────────────────────────────────
        user = get_user(username)
        if not user:
            return _response(404, {"error": "user not found"})

        status = user.get("backfill_status")
        if status == "in_progress" or status == "pending":
            return _response(202, {
                "status":   status,
                "username": username,
                "message":  "chart history is still being built",
            })
        if status == "failed":
            return _response(500, {
                "status":  "failed",
                "message": "backfill failed — please try again",
            })

        # ── return all available weeks for week picker ────────────────────────
        if all_weeks == "true":
            weeks = get_all_weeks(username)
            return _response(200, {
                "username": username,
                "weeks":    weeks,
            })

        # ── fetch specific or latest chart ────────────────────────────────────
        if week:
            chart = get_chart(username, week)
            if not chart:
                return _response(404, {
                    "error": f"no chart found for week {week}"
                })
        else:
            chart = get_latest_chart(username)
            if not chart:
                return _response(404, {
                    "error": "no charts found for this user"
                })

        # ── attach navigation context ─────────────────────────────────────────
        all_week_list  = get_all_weeks(username)
        current_index  = _find_week_index(all_week_list, chart["week_start"])

        prev_week = all_week_list[current_index - 1] if current_index > 0 else None
        next_week = (
            all_week_list[current_index + 1]
            if current_index < len(all_week_list) - 1
            else None
        )

        return _response(200, {
            "username":   username,
            "week_start": chart["week_start"],
            "entries":    chart["entries"],
            "records_broken": chart.get("records_broken", []),
            "navigation": {
                "prev_week":    prev_week,
                "next_week":    next_week,
                "total_weeks":  len(all_week_list),
                "current_index": current_index,
            },
        })

    except Exception as e:
        print(f"get_chart error: {e}")
        return _response(500, {"error": str(e)})


# ── helpers ───────────────────────────────────────────────────────────────────

def _find_week_index(weeks: list[str], week_str: str) -> int:
    try:
        return weeks.index(week_str)
    except ValueError:
        return len(weeks) - 1


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type":                "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }