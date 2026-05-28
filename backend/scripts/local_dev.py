import sys
import os
import json

# make shared layer importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../layers/shared"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../functions/backfill"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../functions/get_chart"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../functions/validate_user"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../functions/weekly_update"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

from lastfm import (
    validate_user,
    get_earliest_scrobble_timestamp,
    get_scrobbles_for_week,
)
from chart import (
    compute_all_weeks,
    get_all_week_starts,
    get_week_start,
    get_week_end,
    week_start_to_str,
    str_to_week_start,
)
from datetime import datetime, timezone


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    username = input("Enter your Last.fm username: ").strip().lower()
    if not username:
        print("no username provided")
        return

    # ── validate ──────────────────────────────────────────────────────────────
    print(f"\nvalidating {username} on Last.fm...")
    user_info = validate_user(username)
    if not user_info:
        print("user not found on Last.fm")
        return

    print(f"found: {user_info['username']} — {user_info['scrobbles']:,} total scrobbles")

    # ── find earliest scrobble ────────────────────────────────────────────────
    print("\nfinding earliest scrobble...")
    earliest_ts = get_earliest_scrobble_timestamp(username)
    if not earliest_ts:
        print("no scrobble history found")
        return

    earliest_dt = datetime.fromtimestamp(earliest_ts, tz=timezone.utc)
    print(f"earliest scrobble: {earliest_dt.strftime('%Y-%m-%d')}")

    week_starts = get_all_week_starts(earliest_ts)
    print(f"total weeks to process: {len(week_starts)}")

    # ── offer options ─────────────────────────────────────────────────────────
    print("\nwhat would you like to do?")
    print("  1. build full chart history (all weeks)")
    print("  2. build last 4 weeks only (fast test)")
    print("  3. build a single specific week")
    choice = input("\nchoice (1/2/3): ").strip()

    if choice == "1":
        _run_full_backfill(username, earliest_ts, week_starts)
    elif choice == "2":
        _run_recent_weeks(username, week_starts, n=4)
    elif choice == "3":
        _run_single_week(username)
    else:
        print("invalid choice")


# ── options ───────────────────────────────────────────────────────────────────

def _run_full_backfill(username: str, earliest_ts: int, week_starts: list):
    print(f"\nfetching all scrobbles — this may take a few minutes...")
    all_scrobbles = _fetch_all_scrobbles(username, week_starts)
    print(f"fetched {len(all_scrobbles):,} scrobbles total")

    print("\ncomputing charts...")
    charts = compute_all_weeks(username, earliest_ts, all_scrobbles)
    print(f"computed {len(charts)} weekly charts")

    _save_and_display(charts, username)


def _run_recent_weeks(username: str, week_starts: list, n: int = 4):
    recent        = week_starts[-n:]
    all_scrobbles = _fetch_all_scrobbles(username, recent)
    print(f"\nfetched {len(all_scrobbles):,} scrobbles for last {n} weeks")

    # need a small history window for movement context
    # use the week before our window as previous if available
    previous_chart = None
    chart_history  = []

    charts = []
    for i, week_start in enumerate(recent):
        week_end  = get_week_end(week_start)
        scrobbles = [
            s for s in all_scrobbles
            if int(week_start.timestamp()) <= s["timestamp"] < int(week_end.timestamp())
        ]

        from chart import compute_week
        chart = compute_week(
            username       = username,
            week_start     = week_start,
            previous_chart = previous_chart,
            chart_history  = chart_history,
            scrobbles      = scrobbles,
        )

        if chart:
            charts.append(chart)
            chart_history.append(chart["entries"])
            previous_chart = chart["entries"]

    _save_and_display(charts, username)


def _run_single_week(username: str):
    week_str = input("enter week start date (YYYY-MM-DD, must be a Monday): ").strip()
    try:
        week_start = str_to_week_start(week_str)
    except ValueError:
        print("invalid date format")
        return

    week_end  = get_week_end(week_start)
    print(f"\nfetching scrobbles for {week_str}...")
    scrobbles = get_scrobbles_for_week(username, week_start, week_end)
    print(f"fetched {len(scrobbles):,} scrobbles")

    from chart import compute_week
    chart = compute_week(
        username       = username,
        week_start     = week_start,
        previous_chart = None,
        chart_history  = None,
        scrobbles      = scrobbles,
    )

    if not chart:
        print("no chart data for this week")
        return

    _save_and_display([chart], username)


# ── helpers ───────────────────────────────────────────────────────────────────

def _fetch_all_scrobbles(username: str, week_starts: list) -> list:
    all_scrobbles = []
    total         = len(week_starts)

    for i, week_start in enumerate(week_starts):
        week_end  = get_week_end(week_start)
        scrobbles = get_scrobbles_for_week(username, week_start, week_end)
        all_scrobbles.extend(scrobbles)

        # progress indicator
        pct = int((i + 1) / total * 100)
        bar = ("█" * (pct // 5)).ljust(20)
        print(f"\r  [{bar}] {pct}% — week {i+1}/{total}", end="", flush=True)

    print()
    return all_scrobbles


def _save_and_display(charts: list, username: str):
    if not charts:
        print("no charts to display")
        return

    # save to local json file for inspection
    output_path = os.path.join(
        os.path.dirname(__file__), f"../output_{username}.json"
    )
    with open(output_path, "w") as f:
        json.dump(charts, f, indent=2)
    print(f"\ncharts saved to {output_path}")

    # display latest chart in terminal
    latest = charts[-1]
    print(f"\n{'─' * 50}")
    print(f"  top10.fm — week of {latest['week_start']}")
    print(f"  {username}")
    print(f"{'─' * 50}")

    for entry in latest["entries"][:10]:
        rank    = entry["rank"]
        song    = entry["song"][:28]
        artist  = entry["artist"][:20]
        plays   = entry["plays"]
        label   = entry.get("entry_label") or ""
        move    = entry.get("movement_label", "")
        delta   = entry.get("movement", 0)
        peak    = entry.get("peak", rank)
        weeks   = entry.get("weeks_on_chart", 1)

        # movement indicator
        if move == "UP":
            indicator = f"▲{delta}"
        elif move == "DOWN":
            indicator = f"▼{delta}"
        elif move in ("NEW", "REENTRY"):
            indicator = move
        else:
            indicator = "—"

        peak_str  = f"pk:{peak}" if peak < rank else f"pk:{peak}"
        weeks_str = f"{weeks}wk"

        print(
            f"  {rank:>2}. {indicator:<8} {song:<30} {artist:<22} "
            f"{plays:>3} plays  {peak_str}  {weeks_str}"
        )

    print(f"{'─' * 50}")
    print(f"  {len(charts)} total weeks computed")
    print(f"{'─' * 50}\n")


if __name__ == "__main__":
    main()