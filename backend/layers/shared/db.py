from __future__ import annotations
import boto3
import os
import json
import decimal
from boto3.dynamodb.conditions import Key
from datetime import datetime


# ── decimal encoder ───────────────────────────────────────────────────────────

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


# ── client setup ──────────────────────────────────────────────────────────────

dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.environ.get("AWS_REGION", "us-east-1")
)

users_table   = dynamodb.Table(os.environ.get("USERS_TABLE",   "top10fm-users"))
charts_table  = dynamodb.Table(os.environ.get("CHARTS_TABLE",  "top10fm-charts"))
records_table = dynamodb.Table(os.environ.get("RECORDS_TABLE", "top10fm-records"))


# ── users ─────────────────────────────────────────────────────────────────────

def get_user(username: str) -> dict | None:
    response = users_table.get_item(Key={"username": username.lower()})
    return response.get("Item")


def put_user(username: str, backfill_status: str, earliest_week: str = None,
             latest_week: str = None, total_weeks: int = 0) -> None:
    users_table.put_item(Item={
        "username":        username.lower(),
        "backfill_status": backfill_status,
        "earliest_week":   earliest_week or "",
        "latest_week":     latest_week   or "",
        "last_updated":    datetime.utcnow().isoformat(),
        "total_weeks":     total_weeks,
    })


def update_user_after_week(username: str, latest_week: str,
                           total_weeks: int) -> None:
    users_table.update_item(
        Key={"username": username.lower()},
        UpdateExpression=(
            "SET latest_week = :lw, total_weeks = :tw, last_updated = :lu"
        ),
        ExpressionAttributeValues={
            ":lw": latest_week,
            ":tw": total_weeks,
            ":lu": datetime.utcnow().isoformat(),
        },
    )


def set_backfill_status(username: str, status: str) -> None:
    users_table.update_item(
        Key={"username": username.lower()},
        UpdateExpression="SET backfill_status = :s, last_updated = :lu",
        ExpressionAttributeValues={
            ":s":  status,
            ":lu": datetime.utcnow().isoformat(),
        },
    )


# ── charts ────────────────────────────────────────────────────────────────────

def get_chart(username: str, week_start: str) -> dict | None:
    response = charts_table.get_item(
        Key={"username": username.lower(), "week_start": week_start}
    )
    return response.get("Item")


def get_all_weeks(username: str) -> list[str]:
    """Returns all week_start values for a user, sorted ascending."""
    weeks = []
    last_evaluated_key = None

    while True:
        kwargs = {
            "KeyConditionExpression": Key("username").eq(username.lower()),
            "ProjectionExpression":   "week_start",
        }
        if last_evaluated_key:
            kwargs["ExclusiveStartKey"] = last_evaluated_key

        response = charts_table.query(**kwargs)
        weeks.extend(item["week_start"] for item in response.get("Items", []))

        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break

    return sorted(weeks)


def get_latest_chart(username: str) -> dict | None:
    response = charts_table.query(
        KeyConditionExpression=Key("username").eq(username.lower()),
        ScanIndexForward=False,
        Limit=1,
    )
    items = response.get("Items", [])
    return items[0] if items else None


def put_chart(username: str, week_start: str, entries: list,
              records_broken: list,
              records_snapshot: dict | None = None) -> None:
    item = {
        "username":       username.lower(),
        "week_start":     week_start,
        "entries":        entries,
        "records_broken": records_broken,
    }
    if records_snapshot is not None:
        item["records_snapshot"] = records_snapshot
    charts_table.put_item(Item=item)


def get_records_snapshot(username: str, week_start: str) -> dict | None:
    """
    Returns the records snapshot stored on the chart row for a given week.
    Returns None if no snapshot stored for that week.
    """
    response = charts_table.get_item(
        Key={"username": username.lower(), "week_start": week_start},
        ProjectionExpression="records_snapshot",
    )
    item = response.get("Item")
    if not item:
        return None
    return item.get("records_snapshot")


# ── records ───────────────────────────────────────────────────────────────────

def get_record(username: str, record_id: str) -> dict | None:
    response = records_table.get_item(
        Key={"username": username.lower(), "record_id": record_id}
    )
    return response.get("Item")


def get_all_records(username: str) -> list:
    response = records_table.query(
        KeyConditionExpression=Key("username").eq(username.lower())
    )
    return response.get("Items", [])


def put_record(username: str, record_id: str, record_name: str,
               holder: str, artist: str | None,
               value: int, history: list) -> None:
    records_table.put_item(Item={
        "username":       username.lower(),
        "record_id":      record_id,
        "record_name":    record_name,
        "current_holder": holder,
        "current_artist": artist or "",
        "current_value":  value,
        "history":        history,
    })