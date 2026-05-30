from __future__ import annotations
from collections import defaultdict

# ── record ids ────────────────────────────────────────────────────────────────

S1  = "s1_most_weeks_at_number_one"
S2  = "s2_longest_consecutive_run_at_number_one"
S3  = "s3_most_weeks_at_number_one_in_year"
S4  = "s4_longest_gap_between_number_one_runs"
S5  = "s5_longest_climb_to_number_one"
S6  = "s6_most_total_weeks_in_top_10"
S7  = "s7_most_consecutive_weeks_in_top_10"
S8  = "s8_most_weeks_in_top_10_without_number_one"
S9  = "s9_most_years_charted"
S10 = "s10_fastest_rise"
S11 = "s11_biggest_single_week_plays"
S12 = "s12_biggest_debut_plays"
S13 = "s13_most_played_all_time"

A1  = "a1_most_weeks_at_number_one"
A2  = "a2_longest_consecutive_run_at_number_one"
A3  = "a3_most_weeks_at_number_one_in_year"
A4  = "a4_most_songs_reached_number_one"
A5  = "a5_most_distinct_number_one_songs_in_year"
A6  = "a6_most_years_with_number_one"
A7  = "a7_longest_gap_between_number_one_weeks"
A8  = "a8_longest_gap_first_chart_to_first_number_one"
A9  = "a9_most_total_weeks_in_top_10"
A10 = "a10_most_consecutive_weeks_with_song_in_top_10"
A11 = "a11_most_weeks_in_top_10_without_number_one"
A12 = "a12_most_distinct_songs_in_top_10"
A13 = "a13_most_entries_in_single_week"
A14 = "a14_most_consecutive_top_positions_in_week"
A15 = "a15_biggest_single_week_plays"
A16 = "a16_biggest_debut_new_artist"
A17 = "a17_most_played_all_time"

ALL_RECORD_IDS = [
    S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, S12, S13,
    A1, A2, A3, A4, A5, A6, A7, A8, A9, A10, A11, A12,
    A13, A14, A15, A16, A17,
]

RECORD_NAMES = {
    S1:  "Most Weeks at #1 All Time",
    S2:  "Longest Consecutive Run at #1",
    S3:  "Most Weeks at #1 in a Calendar Year",
    S4:  "Longest Gap Between #1 Runs",
    S5:  "Longest Climb to #1",
    S6:  "Most Total Weeks in Top 10",
    S7:  "Most Consecutive Weeks in Top 10",
    S8:  "Most Weeks in Top 10 Without Reaching #1",
    S9:  "Most Years Charted",
    S10: "Fastest Rise",
    S11: "Biggest Single Week Play Count",
    S12: "Biggest Debut Play Count",
    S13: "Most Played Song All Time",
    A1:  "Most Weeks at #1 All Time",
    A2:  "Longest Consecutive Run at #1",
    A3:  "Most Weeks at #1 in a Calendar Year",
    A4:  "Most Songs That Reached #1",
    A5:  "Most Distinct #1 Songs in a Single Year",
    A6:  "Most Years With a #1 Song",
    A7:  "Longest Gap Between #1 Weeks",
    A8:  "Longest Gap: First Chart Appearance to First #1",
    A9:  "Most Total Weeks in Top 10",
    A10: "Most Consecutive Weeks With a Song in Top 10",
    A11: "Most Weeks in Top 10 Without Reaching #1",
    A12: "Most Distinct Songs in Top 10",
    A13: "Most Entries in a Single Week",
    A14: "Most Consecutive Top Positions in One Week",
    A15: "Biggest Single Week Play Count",
    A16: "Biggest Debut by a New Artist",
    A17: "Most Played Artist All Time",
}


# ── record result structure ───────────────────────────────────────────────────

def make_record(
    record_id: str,
    holder:    str,
    artist:    str | None,
    value:     int | float,
    week:      str,
    detail:    dict | None = None,
) -> dict:
    return {
        "record_id":   record_id,
        "record_name": RECORD_NAMES[record_id],
        "holder":      holder,
        "artist":      artist or "",
        "value":       value,
        "week":        week,
        "detail":      detail or {},
        "tied":        False,
    }


# ── song list helper ──────────────────────────────────────────────────────────

def build_song_list(songs_chronological: list[dict]) -> list[str]:
    if not songs_chronological:
        return []
    return [f"{s['song']} — {s['artist']}" for s in songs_chronological]


# ── tie-aware top 3 ───────────────────────────────────────────────────────────

def top3_with_ties(
    candidates: list[dict],
    value_key:  str = "value",
) -> list[dict]:
    if not candidates:
        return []

    sorted_c = sorted(
        candidates,
        key=lambda x: (-x[value_key], x.get("week", "9999-99-99")),
    )

    result = []
    for entry in sorted_c:
        e = dict(entry)
        if len(result) == 0:
            e["tied"] = False
            result.append(e)
        elif len(result) == 1:
            is_tied = e[value_key] == result[0][value_key]
            e["tied"] = is_tied
            if is_tied:
                result[0]["tied"] = True  # mark first entry too
            result.append(e)
        elif len(result) == 2:
            is_tied = e[value_key] == result[1][value_key]
            e["tied"] = is_tied
            if is_tied:
                # mark all previous entries with same value
                for prev in result:
                    if prev[value_key] == e[value_key]:
                        prev["tied"] = True
            result.append(e)
            break
        if len(result) == 3:
            break

    return result


# ── helpers ───────────────────────────────────────────────────────────────────

def _tk(song: str, artist: str) -> str:
    return f"{song.lower().strip()}|{artist.lower().strip()}"


# ── incremental state initializer ────────────────────────────────────────────

def init_state() -> dict:
    """
    Returns a fresh incremental state object.
    All accumulators start empty. Pass this to process_week() for each
    week in chronological order.
    """
    return {
        # ── song accumulators ─────────────────────────────────────────────────
        "tk_display":              {},   # tk -> {song, artist}
        "song_plays_total":        defaultdict(int),
        "song_weeks_in_chart":     defaultdict(list),  # tk -> [{week,rank,plays,entry_label}]
        "song_weeks_at_1":         defaultdict(int),
        "song_number_one_weeks":   defaultdict(list),  # tk -> [week, ...]
        "song_years_charted":      defaultdict(set),
        "song_ever_reached_1":     set(),
        "song_first_seen":         {},   # tk -> {week, rank, song, artist}

        # streak tracking per song
        "song_consec_top10_cur":   defaultdict(int),
        "song_consec_top10_best":  defaultdict(lambda: {"length": 0, "start": "", "end": ""}),
        "song_consec_1_cur":       defaultdict(int),
        "song_consec_1_best":      defaultdict(lambda: {"length": 0, "start": "", "end": ""}),
        "song_consec_1_cur_start": defaultdict(str),
        "song_consec_top10_cur_start": defaultdict(str),

        # climb tracking: tk -> {climbing: bool, start_week, start_pos, length}
        "song_climb":              {},

        # gap tracking: tk -> last_1_week
        "song_last_1_week":        {},
        "song_best_gap":           defaultdict(lambda: {"gap": 0, "before": "", "after": ""}),

        # ── artist accumulators ───────────────────────────────────────────────
        "artist_plays_total":      defaultdict(int),
        "artist_weeks_in_chart":   defaultdict(list),
        "artist_weeks_at_1":       defaultdict(int),
        "artist_number_one_weeks": defaultdict(list),
        "artist_years_at_1":       defaultdict(set),
        "artist_ever_reached_1":   set(),
        "artist_first_seen":       {},   # artist -> {week, song}
        "artist_songs_at_1":       defaultdict(set),
        "artist_songs_in_top10":   defaultdict(set),
        "artist_songs_in_top20":   defaultdict(set),
        "artist_distinct_songs":   defaultdict(set),

        # streak tracking per artist
        "artist_consec_top10_cur":  defaultdict(int),
        "artist_consec_top10_best": defaultdict(lambda: {"length": 0, "start": "", "end": ""}),
        "artist_consec_top10_cur_start": defaultdict(str),
        "artist_consec_1_cur":      defaultdict(int),
        "artist_consec_1_best":     defaultdict(lambda: {"length": 0, "start": "", "end": ""}),
        "artist_consec_1_cur_start": defaultdict(str),

        # gap tracking: artist -> last_1_week
        "artist_last_1_week":      {},
        "artist_best_gap":         defaultdict(lambda: {"gap": 0, "before": "", "after": "",
                                                         "song_before": "", "song_after": ""}),
        # a8: artist -> {first_chart_week, first_chart_song, first_1_week, first_1_song}
        "artist_a8":               {},

        # single-week bests (reset each week for calendar year, persistent for all-time)
        "song_best_week_plays":    defaultdict(lambda: {"plays": 0, "week": ""}),
        "artist_best_week_plays":  defaultdict(lambda: {"plays": 0, "week": "", "songs": []}),
        "song_debut_plays":        defaultdict(lambda: {"plays": 0, "week": "", "rank": 0}),

        # a16: new artist debut
        "seen_artists":            set(),
        "artist_debut_plays":      {},  # artist -> {plays, week, songs}

        # a13: most entries in one week
        "artist_best_entries":     defaultdict(lambda: {"count": 0, "week": "", "entries": []}),

        # a14: most consecutive top positions
        "artist_best_consec_pos":  defaultdict(lambda: {"count": 0, "week": "", "positions": []}),

        # previous week tracking for rise calculation
        "prev_week_ranks":         {},  # tk -> rank

        # s10: best rise per song
        "song_best_rise":          defaultdict(lambda: {"gain": 0, "from": 0, "to": 0, "week": ""}),

        # week index for any ordering needs
        "week_count":              0,
        "all_weeks":               [],

        # current year records (reset-aware): year -> {record_id -> best}
        # stored inline in song/artist year accumulators above
    }


# ── incremental week processor ────────────────────────────────────────────────

def process_week(state: dict, chart: dict) -> None:
    """
    Updates all accumulators in state with one week's chart data.
    Call in strict chronological order.
    Mutates state in place.
    """
    week    = chart["week_start"]
    year    = week[:4]
    entries = chart.get("entries", [])

    state["all_weeks"].append(week)
    state["week_count"] += 1

    # build this week's artist data
    week_artists: dict[str, dict] = defaultdict(lambda: {
        "plays": 0, "songs": [], "ranks": [], "entries": []
    })

    this_week_tks: set = set()

    for entry in entries:
        song   = entry["song"]
        artist = entry["artist"]
        rank   = entry["rank"]
        plays  = entry["plays"]
        label  = entry.get("entry_label")
        tk     = _tk(song, artist)

        this_week_tks.add(tk)

        # ── display casing ────────────────────────────────────────────────────
        if tk not in state["tk_display"]:
            state["tk_display"][tk] = {"song": song, "artist": artist}

        # ── song first seen ───────────────────────────────────────────────────
        if tk not in state["song_first_seen"]:
            state["song_first_seen"][tk] = {
                "week": week, "rank": rank, "song": song, "artist": artist
            }

        # ── artist first seen ─────────────────────────────────────────────────
        if artist not in state["artist_first_seen"]:
            state["artist_first_seen"][artist] = {"week": week, "song": song}

        # ── song accumulators ─────────────────────────────────────────────────
        state["song_plays_total"][tk] += plays
        state["song_weeks_in_chart"][tk].append({
            "week": week, "rank": rank, "plays": plays, "entry_label": label
        })
        if rank <= 10:
            state["song_years_charted"][tk].add(year)

        # ── song debut plays ──────────────────────────────────────────────────
        if label == "NEW":
            if plays > state["song_debut_plays"][tk]["plays"]:
                state["song_debut_plays"][tk] = {"plays": plays, "week": week, "rank": rank}

        # ── song best week plays ──────────────────────────────────────────────
        if plays > state["song_best_week_plays"][tk]["plays"]:
            state["song_best_week_plays"][tk] = {"plays": plays, "week": week}

        # ── song rise (S10) ───────────────────────────────────────────────────
        prev_rank = state["prev_week_ranks"].get(tk)
        if prev_rank is not None:
            gain = prev_rank - rank
            if gain > state["song_best_rise"][tk]["gain"]:
                state["song_best_rise"][tk] = {
                    "gain": gain, "from": prev_rank, "to": rank, "week": week
                }

        # ── song #1 tracking ──────────────────────────────────────────────────
        if rank == 1:
            state["song_weeks_at_1"][tk]       += 1
            state["song_ever_reached_1"].add(tk)
            state["song_number_one_weeks"][tk].append(week)

            # consecutive run at #1
            cur   = state["song_consec_1_cur"][tk]
            start = state["song_consec_1_cur_start"].get(tk, week)
            if cur == 0:
                start = week
            cur  += 1
            state["song_consec_1_cur"][tk]       = cur
            state["song_consec_1_cur_start"][tk] = start
            best = state["song_consec_1_best"][tk]
            if cur > best["length"]:
                state["song_consec_1_best"][tk] = {"length": cur, "start": start, "end": week}

            # gap between #1 runs
            last_1 = state["song_last_1_week"].get(tk)
            if last_1 is not None:
                last_idx = state["all_weeks"].index(last_1)
                cur_idx  = len(state["all_weeks"]) - 1
                gap      = cur_idx - last_idx - 1
                if gap > state["song_best_gap"][tk]["gap"]:
                    state["song_best_gap"][tk] = {
                        "gap": gap, "before": last_1, "after": week
                    }
            state["song_last_1_week"][tk] = week

            # climb tracking — reset if reached #1
            climb = state["song_climb"].get(tk)
            if climb and climb.get("climbing") and rank == 1:
                climb["climbing"] = False
        else:
            # reset consecutive #1 streak
            state["song_consec_1_cur"][tk] = 0

        # ── song top 10 consecutive ───────────────────────────────────────────
        if rank <= 10:
            cur   = state["song_consec_top10_cur"][tk]
            start = state["song_consec_top10_cur_start"].get(tk, week)
            if cur == 0:
                start = week
            cur  += 1
            state["song_consec_top10_cur"][tk]       = cur
            state["song_consec_top10_cur_start"][tk] = start
            best = state["song_consec_top10_best"][tk]
            if cur > best["length"]:
                state["song_consec_top10_best"][tk] = {
                    "length": cur, "start": start, "end": week
                }
        else:
            state["song_consec_top10_cur"][tk] = 0

        # ── climb tracking (S5) ───────────────────────────────────────────────
        climb = state["song_climb"].get(tk)
        if label == "NEW" and rank > 1:
            # start a new climb
            state["song_climb"][tk] = {
                "climbing":   True,
                "start_week": week,
                "start_pos":  rank,
                "length":     1,
            }
        elif climb and climb.get("climbing"):
            if rank == 1:
                climb["length"] += 1
                climb["climbing"] = False
                climb["reached_week"] = week
            else:
                climb["length"] += 1

        # ── artist accumulators ───────────────────────────────────────────────
        week_artists[artist]["plays"]   += plays
        week_artists[artist]["songs"].append({
            "song": song, "artist": artist,
            "plays": plays, "first_week": week
        })
        week_artists[artist]["ranks"].append(rank)
        week_artists[artist]["entries"].append(f"#{rank} {song}")

        state["artist_plays_total"][artist] += plays
        state["artist_weeks_in_chart"][artist].append({
            "week": week, "rank": rank, "song": song, "plays": plays
        })
        state["artist_distinct_songs"][artist].add(song)
        if rank <= 10:
            state["artist_songs_in_top10"][artist].add(song)
        state["artist_songs_in_top20"][artist].add(song)

        if rank == 1:
            state["artist_weeks_at_1"][artist]       += 1
            state["artist_ever_reached_1"].add(artist)
            state["artist_number_one_weeks"][artist].append(week)
            state["artist_years_at_1"][artist].add(year)
            state["artist_songs_at_1"][artist].add(song)

            # a8: first #1
            if artist not in state["artist_a8"]:
                first = state["artist_first_seen"][artist]
                state["artist_a8"][artist] = {
                    "first_chart_week": first["week"],
                    "first_chart_song": first["song"],
                    "first_1_week":     week,
                    "first_1_song":     song,
                }

            # artist gap between #1 weeks
            last_1 = state["artist_last_1_week"].get(artist)
            if last_1 is not None:
                last_idx = state["all_weeks"].index(last_1)
                cur_idx  = len(state["all_weeks"]) - 1
                gap      = cur_idx - last_idx - 1
                best_gap = state["artist_best_gap"][artist]
                if gap > best_gap["gap"]:
                    state["artist_best_gap"][artist] = {
                        "gap":         gap,
                        "before":      last_1,
                        "after":       week,
                        "song_before": _song_before_gap(artist, last_1, state),
                        "song_after":  song,
                    }
            state["artist_last_1_week"][artist] = week

    # ── per-artist week aggregates ────────────────────────────────────────────
    for artist, data in week_artists.items():
        # artist best week plays
        if data["plays"] > state["artist_best_week_plays"][artist]["plays"]:
            state["artist_best_week_plays"][artist] = {
                "plays": data["plays"], "week": week,
                "songs": data["songs"]
            }

        # a13: most entries in one week
        n = len(data["entries"])
        if n > state["artist_best_entries"][artist]["count"]:
            state["artist_best_entries"][artist] = {
                "count": n, "week": week, "entries": data["entries"]
            }

        # a14: consecutive top positions from #1
        if 1 in data["ranks"]:
            sorted_entries = sorted(
                [(e["rank"], e["song"]) for e in chart["entries"]
                 if e["artist"] == artist],
                key=lambda x: x[0]
            )
            # count how many consecutive positions from 1 this artist holds
            all_ranks_this_week = sorted(
                [e["rank"] for e in chart["entries"] if e["artist"] == artist]
            )
            consec = 0
            positions = []
            for i, e in enumerate(sorted(chart["entries"], key=lambda x: x["rank"])):
                if e["rank"] == i + 1 and e["artist"] == artist:
                    consec += 1
                    positions.append(f"#{e['rank']} {e['song']}")
                else:
                    break
            if consec > state["artist_best_consec_pos"][artist]["count"]:
                state["artist_best_consec_pos"][artist] = {
                    "count": consec, "week": week, "positions": positions
                }

        # artist consecutive top 10
        has_top10 = any(r <= 10 for r in data["ranks"])
        if has_top10:
            cur   = state["artist_consec_top10_cur"][artist]
            start = state["artist_consec_top10_cur_start"].get(artist, week)
            if cur == 0:
                start = week
            cur  += 1
            state["artist_consec_top10_cur"][artist]       = cur
            state["artist_consec_top10_cur_start"][artist] = start
            best = state["artist_consec_top10_best"][artist]
            if cur > best["length"]:
                state["artist_consec_top10_best"][artist] = {
                    "length": cur, "start": start, "end": week
                }
        else:
            state["artist_consec_top10_cur"][artist] = 0

        # artist consecutive #1
        has_1 = 1 in data["ranks"]
        if has_1:
            cur   = state["artist_consec_1_cur"][artist]
            start = state["artist_consec_1_cur_start"].get(artist, week)
            if cur == 0:
                start = week
            cur  += 1
            state["artist_consec_1_cur"][artist]       = cur
            state["artist_consec_1_cur_start"][artist] = start
            best = state["artist_consec_1_best"][artist]
            if cur > best["length"]:
                state["artist_consec_1_best"][artist] = {
                    "length": cur, "start": start, "end": week
                }
        else:
            state["artist_consec_1_cur"][artist] = 0

    # ── a16: new artist debut ─────────────────────────────────────────────────
    for artist, data in week_artists.items():
        if artist not in state["seen_artists"]:
            state["artist_debut_plays"][artist] = {
                "plays": data["plays"], "week": week, "songs": data["songs"]
            }

    # mark all artists in this week as seen
    for artist in week_artists:
        state["seen_artists"].add(artist)
    # ── reset streaks for artists not present this week ───────────────────────
    artists_this_week = set(week_artists.keys())

    for artist in list(state["artist_consec_top10_cur"].keys()):
        if artist not in artists_this_week:
            state["artist_consec_top10_cur"][artist] = 0

    for artist in list(state["artist_consec_1_cur"].keys()):
        if artist not in artists_this_week:
            state["artist_consec_1_cur"][artist] = 0

    # same for songs not present this week
    for tk in list(state["song_consec_top10_cur"].keys()):
        if tk not in this_week_tks:
            state["song_consec_top10_cur"][tk] = 0

    for tk in list(state["song_consec_1_cur"].keys()):
        if tk not in this_week_tks:
            state["song_consec_1_cur"][tk] = 0

    # ── update prev week ranks ────────────────────────────────────────────────
    state["prev_week_ranks"] = {_tk(e["song"], e["artist"]): e["rank"] for e in entries}


# ── snapshot records from state ───────────────────────────────────────────────

def snapshot_records(state: dict, week: str) -> dict[str, list[dict]]:
    """
    Reads current accumulators and returns {record_id: [top3]} for all 30
    records. Called after process_week() for each week.
    """
    year    = week[:4]
    results = {}

    # ── S1: most weeks at #1 all time ────────────────────────────────────────
    cands = []
    for tk, count in state["song_weeks_at_1"].items():
        d = state["tk_display"][tk]
        cands.append(make_record(S1, d["song"], d["artist"], count, week,
            {"total_weeks_at_1": count, "peak": 1}))
    results[S1] = top3_with_ties(cands)

    # ── S2: longest consecutive run at #1 ────────────────────────────────────
    cands = []
    for tk, best in state["song_consec_1_best"].items():
        if best["length"] == 0:
            continue
        d = state["tk_display"][tk]
        cands.append(make_record(S2, d["song"], d["artist"], best["length"], best["start"],
            {"length": best["length"], "start": best["start"], "end": best["end"]}))
    results[S2] = top3_with_ties(cands)

    # ── S3: most weeks at #1 in calendar year ────────────────────────────────
    cands = []
    for tk, ones in state["song_number_one_weeks"].items():
        count = sum(1 for w in ones if w[:4] == year)
        if count == 0:
            continue
        d = state["tk_display"][tk]
        cands.append(make_record(S3, d["song"], d["artist"], count, week,
            {"weeks_at_1_in_year": count, "year": year}))
    results[S3] = top3_with_ties(cands)

    # ── S4: longest gap between #1 runs ──────────────────────────────────────
    cands = []
    for tk, gap_data in state["song_best_gap"].items():
        if gap_data["gap"] == 0:
            continue
        d = state["tk_display"][tk]
        cands.append(make_record(S4, d["song"], d["artist"], gap_data["gap"], gap_data["after"],
            {"gap_weeks": gap_data["gap"],
             "last_1_before": gap_data["before"],
             "first_1_after": gap_data["after"]}))
    results[S4] = top3_with_ties(cands)

    # ── S5: longest climb to #1 (debut to first #1) ───────────────────────────
    cands = []
    for tk, ones in state["song_number_one_weeks"].items():
        if not ones:
            continue
        first_1_week  = ones[0]
        first_seen    = state["song_first_seen"].get(tk)
        if not first_seen:
            continue
        debut_week    = first_seen["week"]
        first_idx     = state["all_weeks"].index(debut_week)  if debut_week  in state["all_weeks"] else 0
        one_idx       = state["all_weeks"].index(first_1_week) if first_1_week in state["all_weeks"] else 0
        gap           = one_idx - first_idx
        if gap <= 0:
            continue
        d = state["tk_display"][tk]
        cands.append(make_record(S5, d["song"], d["artist"], gap, first_1_week,
            {"gap_weeks":   gap,
            "debut_week":  debut_week,
            "debut_rank":  first_seen["rank"],
            "first_1_week": first_1_week}))
    results[S5] = top3_with_ties(cands)

    # ── S6: most total weeks in top 10 ───────────────────────────────────────
    cands = []
    for tk, weeks_data in state["song_weeks_in_chart"].items():
        top10 = [w for w in weeks_data if w["rank"] <= 10]
        if not top10:
            continue
        peak = min(w["rank"] for w in weeks_data)
        d    = state["tk_display"][tk]
        cands.append(make_record(S6, d["song"], d["artist"], len(top10), week,
            {"total_weeks": len(top10), "peak": peak}))
    results[S6] = top3_with_ties(cands)

    # ── S7: most consecutive weeks in top 10 ─────────────────────────────────
    cands = []
    for tk, best in state["song_consec_top10_best"].items():
        if best["length"] == 0:
            continue
        peak = min(w["rank"] for w in state["song_weeks_in_chart"][tk])
        d    = state["tk_display"][tk]
        cands.append(make_record(S7, d["song"], d["artist"], best["length"], best["start"],
            {"length": best["length"], "peak": peak,
             "start": best["start"], "end": best["end"]}))
    results[S7] = top3_with_ties(cands)

    # ── S8: most weeks in top 10 without reaching #1 ─────────────────────────
    cands = []
    for tk, weeks_data in state["song_weeks_in_chart"].items():
        if tk in state["song_ever_reached_1"]:
            continue
        top10 = [w for w in weeks_data if w["rank"] <= 10]
        if not top10:
            continue
        peak = min(w["rank"] for w in weeks_data)
        d    = state["tk_display"][tk]
        cands.append(make_record(S8, d["song"], d["artist"], len(top10), week,
            {"total_weeks": len(top10), "peak": peak}))
    results[S8] = top3_with_ties(cands)

    # ── S9: most years charted (top 10) ──────────────────────────────────────
    cands = []
    for tk, years in state["song_years_charted"].items():
        if not years:
            continue
        d = state["tk_display"][tk]
        cands.append(make_record(S9, d["song"], d["artist"], len(years), week,
            {"years_count": len(years), "years": sorted(years)}))
    results[S9] = top3_with_ties(cands)

    # ── S10: fastest rise ─────────────────────────────────────────────────────
    cands = []
    for tk, best in state["song_best_rise"].items():
        if best["gain"] == 0:
            continue
        d = state["tk_display"][tk]
        cands.append(make_record(S10, d["song"], d["artist"], best["gain"], best["week"],
            {"positions_gained": best["gain"],
             "from_rank": best["from"],
             "to_rank":   best["to"],
             "week":      best["week"]}))
    results[S10] = top3_with_ties(cands)

    # ── S11: biggest single week play count ───────────────────────────────────
    cands = []
    for tk, best in state["song_best_week_plays"].items():
        if best["plays"] == 0:
            continue
        d = state["tk_display"][tk]
        cands.append(make_record(S11, d["song"], d["artist"], best["plays"], best["week"],
            {"plays": best["plays"], "week": best["week"]}))
    results[S11] = top3_with_ties(cands)

    # ── S12: biggest debut play count ─────────────────────────────────────────
    cands = []
    for tk, best in state["song_debut_plays"].items():
        if best["plays"] == 0:
            continue
        d = state["tk_display"][tk]
        cands.append(make_record(S12, d["song"], d["artist"], best["plays"], best["week"],
            {"plays": best["plays"],
             "debut_position": best["rank"],
             "week": best["week"]}))
    results[S12] = top3_with_ties(cands)

    # ── S13: most played song all time ────────────────────────────────────────
    cands = []
    for tk, total in state["song_plays_total"].items():
        peak = min(w["rank"] for w in state["song_weeks_in_chart"][tk])
        d    = state["tk_display"][tk]
        cands.append(make_record(S13, d["song"], d["artist"], total, week,
            {"total_plays": total, "peak": peak}))
    results[S13] = top3_with_ties(cands)

    # ── A1: most weeks at #1 all time ────────────────────────────────────────
    cands = []
    for artist, count in state["artist_weeks_at_1"].items():
        songs_info = _songs_for_artist_at_1(artist, state)
        cands.append(make_record(A1, artist, None, count, week,
            {"total_weeks": count, "songs": build_song_list(songs_info)}))
    results[A1] = top3_with_ties(cands)

    # ── A2: longest consecutive run at #1 ────────────────────────────────────
    cands = []
    for artist, best in state["artist_consec_1_best"].items():
        if best["length"] == 0:
            continue
        songs_info = _songs_for_artist_at_1(artist, state)
        cands.append(make_record(A2, artist, None, best["length"], best["start"],
            {"length": best["length"], "start": best["start"], "end": best["end"],
             "songs": build_song_list(songs_info)}))
    results[A2] = top3_with_ties(cands)

    # ── A3: most weeks at #1 in calendar year ────────────────────────────────
    cands = []
    for artist, ones in state["artist_number_one_weeks"].items():
        count = sum(1 for w in ones if w[:4] == year)
        if count == 0:
            continue
        songs_info = _songs_for_artist_at_1(artist, state, year=year)
        cands.append(make_record(A3, artist, None, count, week,
            {"weeks_at_1": count, "year": year,
             "songs": build_song_list(songs_info)}))
    results[A3] = top3_with_ties(cands)

    # ── A4: most distinct songs that reached #1 ──────────────────────────────
    cands = []
    for artist, songs in state["artist_songs_at_1"].items():
        songs_info = [{"song": s, "artist": artist, "plays": 0,
                       "first_week": state["artist_first_seen"][artist]["week"]}
                      for s in songs]
        cands.append(make_record(A4, artist, None, len(songs), week,
            {"count": len(songs), "songs": build_song_list(songs_info)}))
    results[A4] = top3_with_ties(cands)

    # ── A5: most distinct #1 songs in calendar year ───────────────────────────
    cands = []
    artist_year_songs: dict[str, set] = defaultdict(set)
    for tk, ones in state["song_number_one_weeks"].items():
        d = state["tk_display"][tk]
        for w in ones:
            if w[:4] == year:
                artist_year_songs[d["artist"]].add(d["song"])
    for artist, songs in artist_year_songs.items():
        cands.append(make_record(A5, artist, None, len(songs), week,
            {"count": len(songs), "year": year, "songs": list(songs)}))
    results[A5] = top3_with_ties(cands)

    # ── A6: most years with a #1 song ────────────────────────────────────────
    cands = []
    for artist, years in state["artist_years_at_1"].items():
        cands.append(make_record(A6, artist, None, len(years), week,
            {"years_count": len(years), "years": sorted(years)}))
    results[A6] = top3_with_ties(cands)

    # ── A7: longest gap between #1 weeks ─────────────────────────────────────
    cands = []
    for artist, gap_data in state["artist_best_gap"].items():
        if gap_data["gap"] == 0:
            continue
        cands.append(make_record(A7, artist, None, gap_data["gap"], gap_data["after"],
            {"gap_weeks":   gap_data["gap"],
             "song_before": gap_data["song_before"],
             "song_after":  gap_data["song_after"],
             "week_before": gap_data["before"],
             "week_after":  gap_data["after"]}))
    results[A7] = top3_with_ties(cands)

    # ── A8: longest gap first chart to first #1 ──────────────────────────────
    cands = []
    for artist, a8 in state["artist_a8"].items():
        first_idx = state["all_weeks"].index(a8["first_chart_week"]) \
            if a8["first_chart_week"] in state["all_weeks"] else 0
        one_idx   = state["all_weeks"].index(a8["first_1_week"]) \
            if a8["first_1_week"] in state["all_weeks"] else 0
        gap = one_idx - first_idx
        if gap <= 0:
            continue
        cands.append(make_record(A8, artist, None, gap, a8["first_1_week"],
            {"gap_weeks":        gap,
             "first_chart_song": a8["first_chart_song"],
             "first_chart_week": a8["first_chart_week"],
             "first_1_song":     a8["first_1_song"],
             "first_1_week":     a8["first_1_week"]}))
    results[A8] = top3_with_ties(cands)

    # ── A9: most total weeks in top 10 ───────────────────────────────────────
    cands = []
    for artist, weeks_data in state["artist_weeks_in_chart"].items():
        # deduplicate: count distinct (artist, week) pairs in top 10
        top10_weeks = list({w["week"] for w in weeks_data if w["rank"] <= 10})
        if not top10_weeks:
            continue
        songs_info = _songs_for_artist_top10(artist, state)
        cands.append(make_record(A9, artist, None, len(top10_weeks), week,
            {"total_weeks": len(top10_weeks), "songs": build_song_list(songs_info)}))
    results[A9] = top3_with_ties(cands)

    # ── A10: most consecutive weeks with song in top 10 ──────────────────────
    cands = []
    for artist, best in state["artist_consec_top10_best"].items():
        if best["length"] == 0:
            continue
        cands.append(make_record(A10, artist, None, best["length"], best["start"],
            {"length": best["length"],
             "start":  best["start"],
             "end":    best["end"]}))
    results[A10] = top3_with_ties(cands)

    # ── A11: most weeks in top 10 without reaching #1 ────────────────────────
    cands = []
    for artist, weeks_data in state["artist_weeks_in_chart"].items():
        if artist in state["artist_ever_reached_1"]:
            continue
        top10_weeks = list({w["week"] for w in weeks_data if w["rank"] <= 10})
        if not top10_weeks:
            continue
        peak       = min(w["rank"] for w in weeks_data)
        songs_info = _songs_for_artist_top10(artist, state)
        cands.append(make_record(A11, artist, None, len(top10_weeks), week,
            {"total_weeks": len(top10_weeks), "peak": peak,
             "songs": build_song_list(songs_info)}))
    results[A11] = top3_with_ties(cands)

    # ── A12: most distinct songs in top 10 ───────────────────────────────────
    cands = []
    for artist, songs in state["artist_songs_in_top10"].items():
        songs_info = [{"song": s, "artist": artist, "plays": 0,
                       "first_week": state["artist_first_seen"][artist]["week"]}
                      for s in songs]
        cands.append(make_record(A12, artist, None, len(songs), week,
            {"count": len(songs), "songs": build_song_list(songs_info)}))
    results[A12] = top3_with_ties(cands)

    # ── A13: most entries in single week ─────────────────────────────────────
    cands = []
    for artist, best in state["artist_best_entries"].items():
        if best["count"] == 0:
            continue
        cands.append(make_record(A13, artist, None, best["count"], best["week"],
            {"count": best["count"], "entries": best["entries"], "week": best["week"]}))
    results[A13] = top3_with_ties(cands)

    # ── A14: most consecutive top positions in one week ───────────────────────
    cands = []
    for artist, best in state["artist_best_consec_pos"].items():
        if best["count"] == 0:
            continue
        cands.append(make_record(A14, artist, None, best["count"], best["week"],
            {"consecutive": best["count"],
             "positions":   best["positions"],
             "week":        best["week"]}))
    results[A14] = top3_with_ties(cands)

    # ── A15: biggest single week play count ───────────────────────────────────
    cands = []
    for artist, best in state["artist_best_week_plays"].items():
        if best["plays"] == 0:
            continue
        cands.append(make_record(A15, artist, None, best["plays"], best["week"],
            {"plays": best["plays"], "week": best["week"],
             "songs": build_song_list(best["songs"])}))
    results[A15] = top3_with_ties(cands)

    # ── A16: biggest debut by new artist ─────────────────────────────────────
    cands = []
    for artist, debut in state["artist_debut_plays"].items():
        cands.append(make_record(A16, artist, None, debut["plays"], debut["week"],
            {"plays": debut["plays"], "week": debut["week"],
             "songs": build_song_list(debut["songs"])}))
    results[A16] = top3_with_ties(cands)

    # ── A17: most played artist all time ─────────────────────────────────────
    cands = []
    for artist, total in state["artist_plays_total"].items():
        songs_info = _songs_for_artist_all(artist, state)
        cands.append(make_record(A17, artist, None, total, week,
            {"total_plays": total, "songs": build_song_list(songs_info)}))
    results[A17] = top3_with_ties(cands)

    return results


# ── event detection ───────────────────────────────────────────────────────────

def detect_events(
    prev_records: dict[str, list[dict]],
    curr_records: dict[str, list[dict]],
) -> list[dict]:
    """
    Compares two record snapshots and returns BROKEN / EXTENDED / TIED events.
    """
    events = []
    for record_id, top3_now in curr_records.items():
        if not top3_now:
            continue
        top3_prev   = prev_records.get(record_id, [])
        prev_value  = top3_prev[0]["value"] if top3_prev else 0
        prev_holder = top3_prev[0]["holder"] if top3_prev else None
        curr_value  = top3_now[0]["value"]
        curr_holder = top3_now[0]["holder"]
        curr_artist = top3_now[0].get("artist", "")

        if curr_value > prev_value:
            event_type = (
                "EXTENDED"
                if prev_holder and curr_holder == prev_holder
                else "BROKEN"
            )
            events.append({
                "record_id":   record_id,
                "record_name": RECORD_NAMES[record_id],
                "holder":      curr_holder,
                "artist":      curr_artist,
                "value":       curr_value,
                "type":        event_type,
            })
        elif curr_value == prev_value and curr_holder != prev_holder:
            events.append({
                "record_id":   record_id,
                "record_name": RECORD_NAMES[record_id],
                "holder":      curr_holder,
                "artist":      curr_artist,
                "value":       curr_value,
                "type":        "TIED",
            })
    return events


# ── main pipeline entry point ─────────────────────────────────────────────────

def build_all_records_incremental(
    charts: list[dict],
) -> list[tuple[str, dict, list[dict]]]:
    """
    Processes all charts in one pass.
    Returns list of (week_start, records_snapshot, events) tuples
    in chronological order.

    This is called once during backfill. O(n) in number of weeks.
    """
    sorted_charts = sorted(charts, key=lambda c: c["week_start"])
    state         = init_state()
    results       = []
    prev_records  = {}

    for chart in sorted_charts:
        process_week(state, chart)
        week         = chart["week_start"]
        curr_records = snapshot_records(state, week)
        events       = detect_events(prev_records, curr_records)
        results.append((week, curr_records, events))
        prev_records = curr_records

    return results


def evaluate_week_records(
    all_charts:   list[dict],
    current_week: str,
) -> tuple[dict, list[dict]]:
    """
    Compatibility wrapper — returns (records_state, events) for a single week.
    Uses incremental processing internally for efficiency.
    Used by weekly_update handler for new weeks only.
    """
    sorted_charts = sorted(
        [c for c in all_charts if c["week_start"] <= current_week],
        key=lambda c: c["week_start"]
    )
    if not sorted_charts:
        return {rid: [] for rid in ALL_RECORD_IDS}, []

    state        = init_state()
    prev_records = {}

    for chart in sorted_charts:
        process_week(state, chart)
        week         = chart["week_start"]
        curr_records = snapshot_records(state, week)
        if week == current_week:
            events = detect_events(prev_records, curr_records)
            return curr_records, events
        prev_records = curr_records

    return {rid: [] for rid in ALL_RECORD_IDS}, []


# ── internal helpers ──────────────────────────────────────────────────────────

def _song_before_gap(artist: str, week: str, state: dict) -> str:
    """Returns song name that was at #1 for artist in given week."""
    for entry in state.get("charts_by_week", {}).get(week, {}).get("entries", []):
        if entry["artist"] == artist and entry["rank"] == 1:
            return entry["song"]
    # fallback: find in artist_weeks_in_chart
    for w in state["artist_weeks_in_chart"].get(artist, []):
        if w["week"] == week and w["rank"] == 1:
            return w["song"]
    return ""


def _songs_for_artist_at_1(
    artist: str,
    state:  dict,
    year:   str | None = None,
) -> list[dict]:
    result = []
    seen   = set()
    for tk, ones in state["song_number_one_weeks"].items():
        d = state["tk_display"].get(tk, {})
        if d.get("artist", "").lower() != artist.lower():
            continue
        if year and not any(w[:4] == year for w in ones):
            continue
        song = d.get("song", "")
        if song not in seen:
            seen.add(song)
            first = state["song_first_seen"].get(tk, {})
            result.append({
                "song":       song,
                "artist":     artist,
                "plays":      state["song_plays_total"].get(tk, 0),
                "first_week": first.get("week", ""),
            })
    return sorted(result, key=lambda x: x["first_week"])


def _songs_for_artist_top10(artist: str, state: dict) -> list[dict]:
    seen   = set()
    result = []
    for w in state["artist_weeks_in_chart"].get(artist, []):
        if w["rank"] <= 10 and w["song"] not in seen:
            seen.add(w["song"])
            tk    = _tk(w["song"], artist)
            first = state["song_first_seen"].get(tk, {})
            result.append({
                "song":       w["song"],
                "artist":     artist,
                "plays":      state["song_plays_total"].get(tk, 0),
                "first_week": first.get("week", ""),
            })
    return sorted(result, key=lambda x: x["first_week"])


def _songs_for_artist_all(artist: str, state: dict) -> list[dict]:
    seen   = set()
    result = []
    for w in state["artist_weeks_in_chart"].get(artist, []):
        if w["song"] not in seen:
            seen.add(w["song"])
            tk    = _tk(w["song"], artist)
            first = state["song_first_seen"].get(tk, {})
            result.append({
                "song":       w["song"],
                "artist":     artist,
                "plays":      state["song_plays_total"].get(tk, 0),
                "first_week": first.get("week", ""),
            })
    return sorted(result, key=lambda x: x["first_week"])