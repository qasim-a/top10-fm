from __future__ import annotations
import json
import os
import sys
import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers/shared"))

from lastfm import validate_user, get_earliest_scrobble_timestamp
from chart import get_all_week_starts
from db import get_user, put_user


def handler(event, context):
    try:
        body     = json.loads(event.get("body", "{}"))
        username = body.get("username", "").strip().lower()

        if not username:
            return _response(400, {"error": "username is required"})

        existing = get_user(username)
        if existing:
            status = existing.get("backfill_status")
            if status == "complete":
                return _response(200, {"status": "already_complete", "username": username})
            if status == "in_progress":
                return _response(200, {"status": "in_progress", "username": username})

        user_info = validate_user(username)
        if not user_info:
            return _response(404, {"error": "Last.fm user not found"})

        # ── check history length ──────────────────────────────────────
        earliest_ts = get_earliest_scrobble_timestamp(username)
        if earliest_ts:
            week_count = len(get_all_week_starts(earliest_ts))
            if week_count > 500:
                return _response(200, {
                    "status":   "too_large",
                    "username": username,
                })

        # mark as in_progress immediately so polling knows job started
        put_user(username, backfill_status="in_progress")

        # invoke worker asynchronously — returns immediately, no timeout
        lambda_client = boto3.client(
            "lambda",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        )
        lambda_client.invoke(
            FunctionName   = os.environ["BACKFILL_WORKER_ARN"],
            InvocationType = "Event",
            Payload        = json.dumps({"username": username}),
        )

        return _response(200, {"status": "in_progress", "username": username})

    except Exception as e:
        print(f"backfill trigger error: {e}")
        return _response(500, {"error": str(e)})


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