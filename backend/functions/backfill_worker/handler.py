from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import sys
import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers/shared"))

from lastfm import get_earliest_scrobble_timestamp, get_scrobbles_for_week
from chart import compute_all_weeks, get_all_week_starts, get_week_end
from records import build_all_records_incremental
from db import get_user, put_user, set_backfill_status, put_record


def handler(event, context):
    username = event.get("username", "").strip().lower()
    if not username:
        print("backfill_worker: no username provided")
        return

    print(f"backfill_worker: starting for {username}")

    try:
        # ── find earliest scrobble ────────────────────────────────────────────
        earliest_ts = get_earliest_scrobble_timestamp(username)
        if not earliest_ts:
            set_backfill_status(username, "complete")
            return

        # ── fetch all scrobbles ───────────────────────────────────────────────
        week_starts   = get_all_week_starts(earliest_ts)
        all_scrobbles = _fetch_all_scrobbles(username, week_starts)
        print(f"backfill_worker: fetched {len(all_scrobbles)} scrobbles")

        # ── compute all weekly charts ─────────────────────────────────────────
        charts = compute_all_weeks(username, earliest_ts, all_scrobbles)
        print(f"backfill_worker: computed {len(charts)} charts")

        if not charts:
            set_backfill_status(username, "complete")
            return

        # ── compute records incrementally ─────────────────────────────────────
        records_by_week = build_all_records_incremental(charts)
        snapshots_by_week = {week: snapshot for week, snapshot, _ in records_by_week}
        events_by_week    = {week: events   for week, _, events   in records_by_week}
        print(f"backfill_worker: computed records for {len(records_by_week)} weeks")

        # ── write charts in batches of 25 ─────────────────────────────────────
        dynamodb     = boto3.resource("dynamodb",
                        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
        charts_table = dynamodb.Table(os.environ.get("CHARTS_TABLE", "top10fm-charts"))

        batch_size = 25
        for i in range(0, len(charts), batch_size):
            batch = charts[i:i + batch_size]
            with charts_table.batch_writer() as writer:
                for chart in batch:
                    week     = chart["week_start"]
                    events   = events_by_week.get(week, [])
                    snapshot = snapshots_by_week.get(week, {})
                    writer.put_item(Item={
                        "username":         username.lower(),
                        "week_start":       week,
                        "entries":          chart["entries"],
                        "records_broken":   events,
                        "records_snapshot": snapshot,
                    })
            print(f"backfill_worker: wrote {min(i+batch_size, len(charts))}/{len(charts)} charts")

        # ── write latest records snapshot to records table ────────────────────
        if records_by_week:
            latest_week, latest_snapshot, _ = records_by_week[-1]
            for record_id, top3 in latest_snapshot.items():
                if not top3:
                    continue
                top1 = top3[0]
                put_record(
                    username    = username,
                    record_id   = record_id,
                    record_name = top1["record_name"],
                    holder      = top1["holder"],
                    artist      = top1.get("artist", ""),
                    value       = top1["value"],
                    history     = top3,
                )

        # ── update user metadata ──────────────────────────────────────────────
        put_user(
            username        = username,
            backfill_status = "complete",
            earliest_week   = charts[0]["week_start"],
            latest_week     = charts[-1]["week_start"],
            total_weeks     = len(charts),
        )

        print(f"backfill_worker: complete for {username} — {len(charts)} weeks")

    except Exception as e:
        print(f"backfill_worker error for {username}: {e}")
        try:
            set_backfill_status(username, "failed")
        except Exception:
            pass
        raise


def _fetch_all_scrobbles(username: str, week_starts: list) -> list:
    total        = len(week_starts)
    results      = {}
    completed    = 0

    def fetch_week(i: int, week_start):
        week_end  = get_week_end(week_start)
        scrobbles = get_scrobbles_for_week(username, week_start, week_end)
        return i, scrobbles

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(fetch_week, i, ws): i
            for i, ws in enumerate(week_starts)
        }
        for future in as_completed(futures):
            i, scrobbles   = future.result()
            results[i]     = scrobbles
            completed     += 1
            if completed % 20 == 0:
                print(f"backfill_worker: fetched week {completed}/{total}")

    # reassemble in chronological order
    all_scrobbles = []
    for i in range(total):
        all_scrobbles.extend(results.get(i, []))

    return all_scrobbles