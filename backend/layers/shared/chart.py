from datetime import datetime, timedelta, timezone
from typing import Optional
from lastfm import get_scrobbles_for_week, aggregate_play_counts

# ── constants ─────────────────────────────────────────────────────────────────

CHART_SIZE = 20  # compute top 20, display top 10 in UI


# ── week boundary utilities ───────────────────────────────────────────────────

def get_week_start(dt: datetime) -> datetime:
    """
    Given any datetime, returns the Monday 00:00:00 UTC of that week.
    All weeks in top10.fm are Monday-Sunday.
    """
    dt_utc = dt.astimezone(timezone.utc)
    monday = dt_utc - timedelta(days=dt_utc.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def get_week_end(week_start: datetime) -> datetime:
    """Returns Sunday 23:59:59 UTC for a given week_start."""
    return week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)


def week_start_to_str(week_start: datetime) -> str:
    """Converts a week_start datetime to ISO date string e.g. 2023-01-02"""
    return week_start.strftime("%Y-%m-%d")


def str_to_week_start(week_str: str) -> datetime:
    """Converts an ISO date string back to a UTC-aware datetime."""
    dt = datetime.strptime(week_str, "%Y-%m-%d")
    return dt.replace(tzinfo=timezone.utc)


def get_all_week_starts(earliest_ts: int) -> list[datetime]:
    """
    Given a unix timestamp of the earliest scrobble, returns a list of
    all Monday week_starts from that week up to and including the current week.
    """
    earliest_dt  = datetime.fromtimestamp(earliest_ts, tz=timezone.utc)
    current_week = get_week_start(datetime.now(tz=timezone.utc))
    week         = get_week_start(earliest_dt)
    weeks        = []

    while week <= current_week:
        weeks.append(week)
        week += timedelta(weeks=1)

    return weeks
# ── building a single week's raw chart ───────────────────────────────────────

def build_raw_chart(username: str, week_start: datetime) -> list:
    """
    Fetches scrobbles for a week and returns a ranked list of top CHART_SIZE
    tracks with basic play count data. No movement or history metadata yet.

    Returns list of dicts:
    {rank, song, artist, plays}
    """
    week_end  = get_week_end(week_start)
    scrobbles = get_scrobbles_for_week(username, week_start, week_end)

    if not scrobbles:
        return []

    aggregated = aggregate_play_counts(scrobbles)
    top        = aggregated[:CHART_SIZE]

    return [
        {
            "rank":             idx + 1,
            "song":             entry["song"],
            "artist":           entry["artist"],
            "plays":            entry["plays"],
            "latest_timestamp": entry.get("latest_timestamp", 0),
        }
        for idx, entry in enumerate(top)
    ]


def build_raw_chart_from_scrobbles(scrobbles: list) -> list:
    """
    Same as build_raw_chart but accepts pre-fetched scrobbles.
    Used during backfill where scrobbles are already in memory.
    """
    if not scrobbles:
        return []

    aggregated = aggregate_play_counts(scrobbles)
    top        = aggregated[:CHART_SIZE]

    return [
        {
            "rank":             idx + 1,
            "song":             entry["song"],
            "artist":           entry["artist"],
            "plays":            entry["plays"],
            "latest_timestamp": entry.get("latest_timestamp", 0),
        }
        for idx, entry in enumerate(top)
    ]
# ── movement and chart metadata ───────────────────────────────────────────────

def enrich_chart(
    raw_chart: list,
    previous_chart: list | None,
    chart_history: list[list] | None,
) -> list:
    """
    Takes a raw chart (rank, song, artist, plays) and enriches each entry with:
    - movement delta and label (UP, DOWN, STABLE, NEW, REENTRY)
    - entry_label (NEW, REENTRY, or None)
    - peak position across all history
    - weeks on chart total
    - weeks at number one total

    Args:
        raw_chart:      this week's raw ranked entries
        previous_chart: last week's enriched entries, or None if first week
        chart_history:  all prior weeks' enriched entries oldest first,
                        or None if first week. used for peak and streak calcs.
    """
    previous_lookup  = _build_lookup(previous_chart or [])
    history_lookup   = _build_history_lookup(chart_history or [])

    enriched = []
    for entry in raw_chart:
        key    = _track_key(entry["song"], entry["artist"])
        prev   = previous_lookup.get(key)
        hist   = history_lookup.get(key, {})

        # ── movement ──────────────────────────────────────────────────────────
        if prev is None and not hist:
            movement       = 0
            movement_label = "NEW"
            entry_label    = "NEW"
        elif prev is None and hist:
            movement       = 0
            movement_label = "REENTRY"
            entry_label    = "REENTRY"
        else:
            delta          = prev["rank"] - entry["rank"]
            movement       = abs(delta)
            movement_label = "UP" if delta > 0 else "DOWN" if delta < 0 else "STABLE"
            entry_label    = None

        # ── peak position ─────────────────────────────────────────────────────
        all_ranks   = hist.get("ranks", []) + [entry["rank"]]
        peak        = min(all_ranks)

        # ── weeks on chart ────────────────────────────────────────────────────
        weeks_on_chart = hist.get("weeks_on_chart", 0) + 1

        # ── weeks at number one ───────────────────────────────────────────────
        prev_weeks_at_one = hist.get("weeks_at_number_one", 0)
        weeks_at_number_one = (
            prev_weeks_at_one + 1 if entry["rank"] == 1
            else prev_weeks_at_one
        )

        enriched.append({
            "rank":               entry["rank"],
            "song":               entry["song"],
            "artist":             entry["artist"],
            "plays":              entry["plays"],
            "latest_timestamp":    entry.get("latest_timestamp", 0),
            "movement":           movement,
            "movement_label":     movement_label,
            "entry_label":        entry_label,
            "peak":               peak,
            "weeks_on_chart":     weeks_on_chart,
            "weeks_at_number_one": weeks_at_number_one,
        })

    return enriched


# ── lookup helpers ────────────────────────────────────────────────────────────

def _track_key(song: str, artist: str) -> str:
    """Normalized key for consistent song identification."""
    return f"{song.lower().strip()}|{artist.lower().strip()}"


def _build_lookup(chart: list) -> dict:
    """
    Builds a dict keyed by track_key from a single week's chart entries.
    Used for previous week lookups.
    """
    return {
        _track_key(e["song"], e["artist"]): e
        for e in chart
    }


def _build_history_lookup(chart_history: list[list]) -> dict:
    """
    Builds a dict keyed by track_key summarizing each track's full history.
    Aggregates ranks, weeks_on_chart, and weeks_at_number_one across all
    prior weeks so enrich_chart can compute peaks and streaks in one pass.

    Returns:
    {
        track_key: {
            ranks:               [1, 2, 1, 3, ...],
            weeks_on_chart:      int,
            weeks_at_number_one: int,
        }
    }
    """
    history = {}

    for week_entries in chart_history:
        for entry in week_entries:
            key = _track_key(entry["song"], entry["artist"])
            if key not in history:
                history[key] = {
                    "ranks":               [],
                    "weeks_on_chart":      0,
                    "weeks_at_number_one": 0,
                }
            history[key]["ranks"].append(entry["rank"])
            history[key]["weeks_on_chart"] += 1
            if entry["rank"] == 1:
                history[key]["weeks_at_number_one"] += 1

    return history
# ── full chart pipeline ───────────────────────────────────────────────────────

def compute_week(
    username: str,
    week_start: datetime,
    previous_chart: list | None,
    chart_history: list[list] | None,
    scrobbles: list | None = None,
) -> dict | None:
    """
    Full pipeline for a single week. Fetches scrobbles if not provided,
    builds raw chart, enriches with movement and metadata.

    Returns a complete chart dict ready to write to DynamoDB, or None
    if there were no scrobbles that week.

    Args:
        username:       Last.fm username
        week_start:     Monday UTC datetime for this week
        previous_chart: enriched entries from last week or None
        chart_history:  all prior weeks' enriched entries oldest first or None
        scrobbles:      pre-fetched scrobbles — pass during backfill to avoid
                        redundant API calls, omit for single week updates
    """
    # ── fetch or use provided scrobbles ───────────────────────────────────────
    if scrobbles is None:
        raw_chart = build_raw_chart(username, week_start)
    else:
        raw_chart = build_raw_chart_from_scrobbles(scrobbles)

    if not raw_chart:
        return None

    # ── enrich ────────────────────────────────────────────────────────────────
    enriched = enrich_chart(raw_chart, previous_chart, chart_history)

    return {
        "username":       username.lower(),
        "week_start":     week_start_to_str(week_start),
        "entries":        enriched,
        "records_broken": [],  # populated by records engine in next step
    }


def compute_all_weeks(
    username: str,
    earliest_ts: int,
    all_scrobbles: list,
) -> list[dict]:
    """
    Builds every weekly chart from earliest scrobble to current week.
    Used during initial backfill.

    Scrobbles are pre-fetched in bulk and bucketed by week here to avoid
    making one API call per week.

    Returns list of computed chart dicts oldest first, skipping empty weeks.

    Args:
        username:       Last.fm username
        earliest_ts:    unix timestamp of user's first scrobble
        all_scrobbles:  complete scrobble history fetched in bulk
    """
    week_starts    = get_all_week_starts(earliest_ts)
    bucketed       = _bucket_scrobbles_by_week(all_scrobbles, week_starts)

    charts         = []
    chart_history  = []
    previous_chart = None

    for week_start in week_starts:
        week_str   = week_start_to_str(week_start)
        scrobbles  = bucketed.get(week_str, [])

        chart = compute_week(
            username       = username,
            week_start     = week_start,
            previous_chart = previous_chart,
            chart_history  = chart_history,
            scrobbles      = scrobbles,
        )

        if chart is None:
            continue

        charts.append(chart)
        chart_history.append(chart["entries"])
        previous_chart = chart["entries"]

    return charts


# ── scrobble bucketing ────────────────────────────────────────────────────────

def _bucket_scrobbles_by_week(
    scrobbles: list,
    week_starts: list[datetime],
) -> dict[str, list]:
    """
    Assigns each scrobble to its correct week bucket.
    Returns dict keyed by week_start string e.g. {"2023-01-02": [...]}

    This runs once during backfill so the pipeline never has to call
    the Last.fm API per-week — all scrobbles are already in memory.
    """
    # build a sorted list of (week_start_ts, week_str) for binary search
    boundaries = [
        (int(ws.timestamp()), week_start_to_str(ws))
        for ws in week_starts
    ]

    buckets = {week_start_to_str(ws): [] for ws in week_starts}

    for scrobble in scrobbles:
        ts       = scrobble.get("timestamp", 0)
        week_str = _find_week_for_timestamp(ts, boundaries)
        if week_str:
            buckets[week_str].append(scrobble)

    return buckets


def _find_week_for_timestamp(ts: int, boundaries: list[tuple]) -> str | None:
    """
    Binary search to find which week a timestamp belongs to.
    boundaries is a sorted list of (week_start_ts, week_str).
    """
    lo, hi = 0, len(boundaries) - 1

    while lo <= hi:
        mid        = (lo + hi) // 2
        mid_ts     = boundaries[mid][0]
        next_ts    = boundaries[mid + 1][0] if mid + 1 < len(boundaries) else float("inf")

        if mid_ts <= ts < next_ts:
            return boundaries[mid][1]
        elif ts < mid_ts:
            hi = mid - 1
        else:
            lo = mid + 1

    return None