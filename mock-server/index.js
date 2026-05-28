const express = require("express");
const cors    = require("cors");
const fs      = require("fs");
const path    = require("path");

const app  = express();
app.use(cors());
app.use(express.json());

// load your real chart data
const charts = JSON.parse(
  fs.readFileSync(
    path.join(__dirname, "../backend/output_qasim-.json"),
    "utf8"
  )
);

// build lookup by week_start
const chartByWeek = {};
charts.forEach(c => { chartByWeek[c.week_start] = c; });

// sorted week list
const allWeeks = charts.map(c => c.week_start).sort();


// ── helper: attach navigation to a chart ─────────────────────────────────────

function withNavigation(chart) {
  const idx      = allWeeks.indexOf(chart.week_start);
  return {
    ...chart,
    entries:        chart.entries.slice(0, 20), // top 20 stored
    records_broken: [],
    navigation: {
      prev_week:     idx > 0 ? allWeeks[idx - 1] : null,
      next_week:     idx < allWeeks.length - 1 ? allWeeks[idx + 1] : null,
      total_weeks:   allWeeks.length,
      current_index: idx,
    },
  };
}


// ── routes ────────────────────────────────────────────────────────────────────

// validate user
app.get("/validate", (req, res) => {
  const username = req.query.username?.toLowerCase();
  if (!username) return res.status(400).json({ error: "username required" });

  // accept your own username
  if (username === "qasim-") {
    return res.json({
      username:      "qasim-",
      lastfm_info: {
        username:  "qasim-",
        real_name: "",
        image:     "",
        scrobbles: 57563,
      },
      system_status: "complete",
      meta: {
        earliest_week: allWeeks[0],
        latest_week:   allWeeks[allWeeks.length - 1],
        total_weeks:   allWeeks.length,
      },
    });
  }

  return res.status(404).json({ error: "Last.fm user not found" });
});

// get chart
app.get("/chart", (req, res) => {
  const username  = req.query.username?.toLowerCase();
  const week      = req.query.week;
  const weeksAll  = req.query.weeks;

  if (!username) return res.status(400).json({ error: "username required" });

  // return all weeks for calendar
  if (weeksAll === "true") {
    return res.json({ username, weeks: allWeeks });
  }

  // specific week or latest
  const chart = week
    ? chartByWeek[week]
    : chartByWeek[allWeeks[allWeeks.length - 1]];

  if (!chart) return res.status(404).json({ error: "chart not found" });

  return res.json(withNavigation(chart));
});

// backfill — instant for mock
app.post("/backfill", (req, res) => {
  res.json({
    status:      "complete",
    username:    "qasim-",
    total_weeks: allWeeks.length,
  });
});

// update — no-op for mock
app.post("/update", (req, res) => {
  res.json({ status: "updated", username: "qasim-" });
});


// ── start ─────────────────────────────────────────────────────────────────────

app.listen(3001, () => {
  console.log("mock server running on http://localhost:3001");
});