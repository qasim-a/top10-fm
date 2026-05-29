const express = require("express");
const cors    = require("cors");
const fs      = require("fs");
const path    = require("path");
const { execSync } = require("child_process");

const app  = express();
app.use(cors());
app.use(express.json());

// ── load chart data ───────────────────────────────────────────────────────────

const charts = JSON.parse(
  fs.readFileSync(
    path.join(__dirname, "../backend/output_qasim-.json"),
    "utf8"
  )
);

const chartByWeek = {};
charts.forEach(c => { chartByWeek[c.week_start] = c; });
const allWeeks = charts.map(c => c.week_start).sort();

// ── load records data (computed once at startup) ──────────────────────────────

let recordsByWeek = {};

function computeRecords() {
  console.log("computing records...");
  try {
    const scriptPath = path.join(__dirname, "_compute_records.py");
    const jsonPath   = path.join(__dirname, "../backend/output_qasim-.json");
    const sharedPath = path.join(__dirname, "../backend/layers/shared");

    const script = [
      "import sys, json",
      `sys.path.insert(0, '${sharedPath}')`,
      "from records import build_all_records_incremental",
      `with open('${jsonPath}') as f:`,
      "    charts = json.load(f)",
      "results = build_all_records_incremental(charts)",
      "output  = {}",
      "for week, snapshot, events in results:",
      "    output[week] = {",
      '        "records": {k: v for k, v in snapshot.items()},',
      '        "events":  events,',
      "    }",
      "print(json.dumps(output))",
    ].join("\n");

    fs.writeFileSync(scriptPath, script);

    const result = execSync(`python3 ${scriptPath}`, {
      maxBuffer: 50 * 1024 * 1024,
    });

    recordsByWeek = JSON.parse(result.toString());
    console.log(`records computed for ${Object.keys(recordsByWeek).length} weeks`);
    fs.unlinkSync(scriptPath);
  } catch (err) {
    console.error("failed to compute records:", err.message);
  }
}

computeRecords();


// ── helpers ───────────────────────────────────────────────────────────────────

function withNavigation(chart) {
  const idx = allWeeks.indexOf(chart.week_start);
  const weekData = recordsByWeek[chart.week_start] || {};
  return {
    ...chart,
    entries:        chart.entries.slice(0, 20),
    records_broken: weekData.events || [],
    navigation: {
      prev_week:     idx > 0 ? allWeeks[idx - 1] : null,
      next_week:     idx < allWeeks.length - 1 ? allWeeks[idx + 1] : null,
      total_weeks:   allWeeks.length,
      current_index: idx,
    },
  };
}


// ── routes ────────────────────────────────────────────────────────────────────

app.get("/validate", (req, res) => {
  const username = req.query.username?.toLowerCase();
  if (!username) return res.status(400).json({ error: "username required" });

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

app.get("/chart", (req, res) => {
  const username = req.query.username?.toLowerCase();
  const week     = req.query.week;
  const weeksAll = req.query.weeks;

  if (!username) return res.status(400).json({ error: "username required" });

  if (weeksAll === "true") {
    return res.json({ username, weeks: allWeeks });
  }

  const chart = week
    ? chartByWeek[week]
    : chartByWeek[allWeeks[allWeeks.length - 1]];

  if (!chart) return res.status(404).json({ error: "chart not found" });

  return res.json(withNavigation(chart));
});

app.get("/records", (req, res) => {
  const username = req.query.username?.toLowerCase();
  const week     = req.query.week || allWeeks[allWeeks.length - 1];

  if (!username) return res.status(400).json({ error: "username required" });

  const weekData = recordsByWeek[week];
  if (!weekData) return res.status(404).json({ error: "no records for this week" });

  return res.json({
    username,
    week,
    records: weekData.records,
  });
});

app.post("/backfill", (req, res) => {
  res.json({ status: "complete", username: "qasim-", total_weeks: allWeeks.length });
});

app.post("/update", (req, res) => {
  res.json({ status: "updated", username: "qasim-" });
});


// ── start ─────────────────────────────────────────────────────────────────────

app.listen(3001, () => {
  console.log("mock server running on http://localhost:3001");
});