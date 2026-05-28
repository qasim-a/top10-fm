# DynamoDB Schema — top10.fm

## Table 1: `users`
| Attribute | Type | Notes |
|-----------|------|-------|
| `username` (PK) | String | Last.fm username, lowercase |
| `backfill_status` | String | `pending` / `in_progress` / `complete` |
| `earliest_week` | String | ISO date of first week with data e.g. `2023-01-02` |
| `latest_week` | String | ISO date of most recently computed week |
| `last_updated` | String | ISO timestamp of last update |
| `total_weeks` | Number | total number of computed weeks |

## Table 2: `charts`
| Attribute | Type | Notes |
|-----------|------|-------|
| `username` (PK) | String | |
| `week_start` (SK) | String | ISO date e.g. `2023-01-02`, always a Monday |
| `entries` | List | ordered list of chart entry objects (see below) |
| `records_broken` | List | records broken or tied this week (see below) |

### Chart Entry Object
```json
{
  "rank": 1,
  "song": "Espresso",
  "artist": "Sabrina Carpenter",
  "plays": 47,
  "movement": 3,
  "movement_label": "UP",
  "peak": 1,
  "weeks_on_chart": 4,
  "entry_label": null
}
```
`entry_label` is `NEW`, `REENTRY`, or `null`.
`movement_label` is `UP`, `DOWN`, `STABLE`, `NEW`, or `REENTRY`.

### Records Broken Object
```json
{
  "record_id": "most_weeks_at_number_one",
  "record_name": "Most Weeks at #1",
  "holder": "Espresso",
  "artist": "Sabrina Carpenter",
  "value": 6,
  "type": "BROKEN"
}
```
`type` is `BROKEN`, `TIED`, or `APPROACHED`.

## Table 3: `records`
| Attribute | Type | Notes |
|-----------|------|-------|
| `username` (PK) | String | |
| `record_id` (SK) | String | snake_case identifier e.g. `most_weeks_at_number_one` |
| `record_name` | String | human readable |
| `current_holder` | String | song or artist name |
| `current_artist` | String | null for artist-level records |
| `current_value` | Number | the actual number |
| `history` | List | past holders `[{holder, artist, value, week_start}]` |

### Record IDs (initial 8)
- `most_weeks_at_number_one`
- `most_weeks_on_chart`
- `highest_single_week_plays`
- `longest_consecutive_weeks`
- `most_top10_entries_by_artist`
- `fastest_rise_to_number_one`
- `most_reentries`
- `most_simultaneous_songs_by_artist`

## GSIs on `charts` table

### GSI 1: `song-index`
- PK: `song_key` = `username#song#artist`
- SK: `week_start`
- Use: full chart history for a specific song

### GSI 2: `artist-index`
- PK: `artist_key` = `username#artist`
- SK: `week_start`
- Use: all charted songs and positions for an artist