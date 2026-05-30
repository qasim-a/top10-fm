from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers/shared"))

from db import get_user, get_all_records, get_records_snapshot, DecimalEncoder


def handler(event, context):
    """
    Returns records state for a user as of a given week.

    For latest week: reads from records table (written during backfill).
    For past weeks: reads records_snapshot stored on the chart row.

    Both paths are single DynamoDB reads — instant regardless of history length.

    Query parameters:
        username — required
        week     — optional, defaults to latest week
    """
    try:
        params   = event.get("queryStringParameters") or {}
        username = params.get("username", "").strip().lower()
        week     = params.get("week", "").strip()

        if not username:
            return _response(400, {"error": "username is required"})

        user = get_user(username)
        if not user:
            return _response(404, {"error": "user not found"})

        if user.get("backfill_status") != "complete":
            return _response(202, {
                "status":  user.get("backfill_status"),
                "message": "chart history still building",
            })

        latest_week = user.get("latest_week", "")
        if not week:
            week = latest_week

        # ── latest week — read from records table ─────────────────────────────
        if week == latest_week:
            stored = get_all_records(username)
            if stored:
                records = {r["record_id"]: r.get("history", []) for r in stored}
                return _response(200, {
                    "username": username,
                    "week":     week,
                    "records":  records,
                })

        # ── past week — read snapshot stored on chart row ─────────────────────
        snapshot = get_records_snapshot(username, week)
        if snapshot:
            return _response(200, {
                "username": username,
                "week":     week,
                "records":  snapshot,
            })

        return _response(404, {"error": "no records snapshot found for this week"})

    except Exception as e:
        print(f"get_records error: {e}")
        return _response(500, {"error": str(e)})


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type":                "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }