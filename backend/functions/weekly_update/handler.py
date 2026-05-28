import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers/shared"))

from lastfm import get_scrobbles_for_week
from chart import (
    compute_week, get_week_start, get_week_end,
    str_to_week_start, week_start_to_str
)
from db import (
    get_user, get_all_weeks, get_latest_chart,
    put_chart, update_user_after_week, set_backfill_status
)
from datetime import datetime, timedelta, timezone


# ── entry point ───────────────────────────────────────────────────────────────

def handler(event, context):
    """
    Triggered by CloudWatch Events on a weekly schedule.
    Iterates all users with completed backfills and computes
    any missing weeks up to and including the current week.

    Also triggered lazily when a returning user opens the app —
    in that case event body contains { "username": "someuser" }
    so only that user gets updated.
    """
    try:
        # ── determine which users to update ───────────────────────────────────
        body     = _parse_body(event)
        username = body.get("username", "").strip().lower() if body else None

        if username:
            users = [username]
        else:
            # scheduled run — scan all complete users
            users = _get_all_complete_users()

        results = []
        for user in users:
            result = _update_user(user)
            results.append(result)

        return _response(200, {"updated": results})

    except Exception as e:
        print(f"weekly_update error: {e}")
        return _response(500, {"error": str(e)})


# ── per-user update ───────────────────────────────────────────────────────────

def _update_user(username: str) -> dict:
    """
    Computes and stores any weeks of chart data the user is missing
    up to and including the current week.
    """
    try:
        user = get_user(username)
        if not user or user.get("backfill_status") != "complete":
            return {"username": username, "status": "skipped"}

        current_week     = get_week_start(datetime.now(tz=timezone.utc))
        latest_stored    = user.get("latest_week", "")

        if not latest_stored:
            return {"username": username, "status": "skipped"}

        latest_stored_dt = str_to_week_start(latest_stored)

        # collect all weeks that need computing
        missing_weeks = []
        week          = latest_stored_dt + timedelta(weeks=1)
        while week <= current_week:
            missing_weeks.append(week)
            week += timedelta(weeks=1)

        if not missing_weeks:
            return {"username": username, "status": "up_to_date"}

        # ── get context for movement and history ──────────────────────────────
        previous_chart = _get_previous_chart_entries(username, latest_stored)
        chart_history  = _get_chart_history_entries(username)

        new_weeks = 0
        for week_start in missing_weeks:
            chart = compute_week(
                username       = username,
                week_start     = week_start,
                previous_chart = previous_chart,
                chart_history  = chart_history,
                scrobbles      = None,  # fetch live from last.fm
            )

            if chart is None:
                # no scrobbles this week — advance previous context anyway
                previous_chart = []
                continue

            put_chart(
                username       = username,
                week_start     = chart["week_start"],
                entries        = chart["entries"],
                records_broken = chart["records_broken"],
            )

            # advance context for next iteration
            chart_history.append(chart["entries"])
            previous_chart = chart["entries"]
            new_weeks     += 1

        # ── update user metadata ──────────────────────────────────────────────
        total_weeks   = int(user.get("total_weeks", 0)) + new_weeks
        latest_stored = week_start_to_str(
            missing_weeks[-1] if missing_weeks else latest_stored_dt
        )
        update_user_after_week(username, latest_stored, total_weeks)

        return {
            "username":  username,
            "status":    "updated",
            "new_weeks": new_weeks,
        }

    except Exception as e:
        print(f"error updating {username}: {e}")
        return {"username": username, "status": "error", "detail": str(e)}


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_previous_chart_entries(username: str, week_str: str) -> list:
    """Fetches entries from the most recently stored chart."""
    from db import get_chart
    chart = get_chart(username, week_str)
    return chart.get("entries", []) if chart else []


def _get_chart_history_entries(username: str) -> list[list]:
    """
    Fetches all stored chart entries for a user oldest first.
    Returns list of lists — each inner list is one week's entries.
    Used to reconstruct history context for enrichment.
    """
    from db import get_chart, get_all_weeks
    weeks  = get_all_weeks(username)
    result = []
    for week_str in weeks:
        chart = get_chart(username, week_str)
        if chart:
            result.append(chart.get("entries", []))
    return result


def _get_all_complete_users() -> list[str]:
    """
    Scans the users table for all users with backfill_status = complete.
    Only used during scheduled weekly runs.
    """
    import boto3
    import os
    dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    table    = dynamodb.Table(os.environ.get("USERS_TABLE", "top10fm-users"))

    response  = table.scan(
        FilterExpression="backfill_status = :s",
        ExpressionAttributeValues={":s": "complete"},
        ProjectionExpression="username",
    )
    return [item["username"] for item in response.get("Items", [])]


def _parse_body(event: dict) -> dict | None:
    try:
        return json.loads(event.get("body") or "{}")
    except Exception:
        return None


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type":                "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }