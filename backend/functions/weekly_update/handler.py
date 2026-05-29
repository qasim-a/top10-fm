from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers/shared"))

from chart import compute_week, get_week_start, get_week_end, str_to_week_start, week_start_to_str
from records import evaluate_week_records
from db import get_user, get_all_weeks, get_chart, get_latest_chart, put_chart, update_user_after_week
from datetime import datetime, timedelta, timezone


def handler(event, context):
    try:
        body     = _parse_body(event)
        username = body.get("username", "").strip().lower() if body else None

        if username:
            users = [username]
        else:
            users = _get_all_complete_users()

        results = []
        for user in users:
            result = _update_user(user)
            results.append(result)

        return _response(200, {"updated": results})

    except Exception as e:
        print(f"weekly_update error: {e}")
        return _response(500, {"error": str(e)})


def _update_user(username: str) -> dict:
    try:
        user = get_user(username)
        if not user or user.get("backfill_status") != "complete":
            return {"username": username, "status": "skipped"}

        current_week  = get_week_start(datetime.now(tz=timezone.utc))
        latest_stored = user.get("latest_week", "")
        if not latest_stored:
            return {"username": username, "status": "skipped"}

        latest_stored_dt = str_to_week_start(latest_stored)

        missing_weeks = []
        week = latest_stored_dt + timedelta(weeks=1)
        while week <= current_week:
            missing_weeks.append(week)
            week += timedelta(weeks=1)

        if not missing_weeks:
            return {"username": username, "status": "up_to_date"}

        # ── load all existing charts for records context ───────────────────────
        all_week_strs = get_all_weeks(username)
        all_charts    = []
        for ws in all_week_strs:
            c = get_chart(username, ws)
            if c:
                all_charts.append(c)

        previous_chart = all_charts[-1]["entries"] if all_charts else None
        chart_history  = [c["entries"] for c in all_charts]

        new_weeks = 0
        for week_start in missing_weeks:
            chart = compute_week(
                username       = username,
                week_start     = week_start,
                previous_chart = previous_chart,
                chart_history  = chart_history,
                scrobbles      = None,
            )

            if chart is None:
                previous_chart = []
                continue

            # compute records for this new week
            all_charts_for_records = all_charts + [chart]
            _, events = evaluate_week_records(
                all_charts_for_records,
                chart["week_start"]
            )
            chart["records_broken"] = events

            put_chart(
                username       = username,
                week_start     = chart["week_start"],
                entries        = chart["entries"],
                records_broken = events,
            )

            all_charts.append(chart)
            chart_history.append(chart["entries"])
            previous_chart = chart["entries"]
            new_weeks     += 1

        total_weeks   = int(user.get("total_weeks", 0)) + new_weeks
        latest_stored = week_start_to_str(missing_weeks[-1])
        update_user_after_week(username, latest_stored, total_weeks)

        return {"username": username, "status": "updated", "new_weeks": new_weeks}

    except Exception as e:
        print(f"error updating {username}: {e}")
        return {"username": username, "status": "error", "detail": str(e)}


def _get_all_complete_users() -> list:
    import boto3
    dynamodb = boto3.resource("dynamodb",
                              region_name=os.environ.get("AWS_REGION", "us-east-1"))
    table    = dynamodb.Table(os.environ.get("USERS_TABLE", "top10fm-users"))
    response = table.scan(
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
    from db import DecimalEncoder
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type":                "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }