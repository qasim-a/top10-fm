from __future__ import annotations
import os
import time
import requests
from datetime import datetime, timezone

# ── client setup ──────────────────────────────────────────────────────────────

LASTFM_API_KEY  = os.environ.get("LASTFM_API_KEY", "")
LASTFM_BASE_URL = "https://ws.audioscrobbler.com/2.0/"
PAGE_SIZE       = 200  # max allowed by Last.fm


# ── user validation ───────────────────────────────────────────────────────────

def validate_user(username: str) -> dict | None:
    """
    Returns basic user info if the username exists on Last.fm, else None.
    """
    params = {
        "method":  "user.getInfo",
        "user":    username,
        "api_key": LASTFM_API_KEY,
        "format":  "json",
    }
    response = _get(params)
    if "error" in response:
        return None
    user = response.get("user", {})
    return {
        "username":    user.get("name"),
        "real_name":   user.get("realname", ""),
        "image":       _extract_image(user.get("image", [])),
        "scrobbles":   int(user.get("playcount", 0)),
        "registered":  int(user.get("registered", {}).get("unixtime", 0)),
    }


# ── scrobble fetching ─────────────────────────────────────────────────────────

def get_scrobbles_for_week(username: str, week_start: datetime,
                           week_end: datetime) -> list:
    """
    Fetches all scrobbles for a user within a given week window.
    week_start and week_end should be timezone-aware UTC datetimes.
    Returns a list of track dicts.
    """
    from_ts = int(week_start.timestamp())
    to_ts   = int(week_end.timestamp())

    all_tracks = []
    page       = 1

    while True:
        params = {
            "method":    "user.getRecentTracks",
            "user":      username,
            "api_key":   LASTFM_API_KEY,
            "format":    "json",
            "limit":     PAGE_SIZE,
            "from":      from_ts,
            "to":        to_ts,
            "page":      page,
        }
        response  = _get(params)
        recent    = response.get("recenttracks", {})
        tracks    = recent.get("track", [])
        attr      = recent.get("@attr", {})

        if not tracks:
            break

        # last.fm sometimes returns a single dict instead of a list
        if isinstance(tracks, dict):
            tracks = [tracks]

        for track in tracks:
            # skip currently playing track — it has no timestamp
            if track.get("@attr", {}).get("nowplaying"):
                continue
            all_tracks.append(_parse_track(track))

        total_pages = int(attr.get("totalPages", 1))
        if page >= total_pages:
            break

        page += 1
        time.sleep(0.25)  # stay well under last.fm rate limit

    return all_tracks


def get_earliest_scrobble_timestamp(username: str) -> int | None:
    """
    Fetches the very first scrobble timestamp for a user.
    Used to determine how far back to build charts.
    """
    params = {
        "method":    "user.getRecentTracks",
        "user":      username,
        "api_key":   LASTFM_API_KEY,
        "format":    "json",
        "limit":     1,
        "page":      1,
    }
    response = _get(params)
    attr     = response.get("recenttracks", {}).get("@attr", {})
    total    = int(attr.get("totalPages", 1))

    # fetch last page to get oldest scrobble
    params["page"] = total
    response       = _get(params)
    tracks         = response.get("recenttracks", {}).get("track", [])

    if not tracks:
        return None

    if isinstance(tracks, dict):
        tracks = [tracks]

    for track in reversed(tracks):
        ts = track.get("date", {}).get("uts")
        if ts:
            return int(ts)

    return None


# ── aggregation ───────────────────────────────────────────────────────────────

def aggregate_play_counts(scrobbles: list) -> list:
    """
    Takes a flat list of scrobble dicts and returns a list of
    {song, artist, plays, latest_timestamp} sorted by plays descending,
    with recency as tiebreaker.
    """
    counts     = {}
    latest_ts  = {}

    for s in scrobbles:
        key            = (s["song"], s["artist"])
        counts[key]    = counts.get(key, 0) + 1
        latest_ts[key] = max(latest_ts.get(key, 0), s.get("timestamp", 0))

    return sorted(
        [
            {
                "song":             k[0],
                "artist":           k[1],
                "plays":            v,
                "latest_timestamp": latest_ts[k],
            }
            for k, v in counts.items()
        ],
        key=lambda x: (x["plays"], x["latest_timestamp"]),
        reverse=True,
    )

# ── internal helpers ──────────────────────────────────────────────────────────

def _get(params: dict, retries: int = 3) -> dict:
    """
    Makes a GET request to the Last.fm API with basic retry logic.
    """
    for attempt in range(retries):
        try:
            response = requests.get(LASTFM_BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)  # exponential backoff
    return {}


def _parse_track(track: dict) -> dict:
    return {
        "song":      track.get("name", ""),
        "artist":    track.get("artist", {}).get("#text", ""),
        "album":     track.get("album",  {}).get("#text", ""),
        "timestamp": int(track.get("date", {}).get("uts", 0)),
    }


def _extract_image(images: list) -> str:
    """Returns the largest available image URL from Last.fm image array."""
    for size in ("extralarge", "large", "medium", "small"):
        for img in images:
            if img.get("size") == size and img.get("#text"):
                return img["#text"]
    return ""