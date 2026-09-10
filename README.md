# running-analytics

Derived running metrics and a Markdown report, computed from data stored by
[`garmin-running-data`](../garmin-running-data). Phase 2 of the personal running/
analytics/gamification ecosystem — this repo owns no canonical data of its own; it reads
`garmin-running-data`'s SQLite/Parquet storage via a local editable path dependency
(`[tool.uv.sources]` in `pyproject.toml`) and its typed `Activity`/`ActivitySample` models.

## Setup

```bash
uv sync   # resolves garmin-running-data from ../garmin-running-data
```

Uses `garmin_running_data.config.get_settings()`, which reads `DATA_DIR` from a `.env` in
the **current working directory** — so run `uv run ra` from this repo's `.env` if you set
one here, or rely on the same default (`~/data/garmin-running-data/`) `garmin-running-data`
uses if you haven't overridden `DATA_DIR`. Either way, run `grd sync` in
`garmin-running-data` at least once first so there's data to report on.

## Usage

```bash
uv run ra --days 14                                    # Markdown report to stdout
uv run ra --days 14 --hr-ceiling 165                   # also report time-to-reach 165bpm per run
uv run ra --days 14 --out report.md                    # write Markdown to a file instead
uv run ra --days 14 --format html --out report.html    # standalone HTML report
uv run ra overlay <activity_id> --out overlay.html     # HR-vs-target overlay chart for one run
```

The report is the default command — `ra --days 14 ...` runs it directly, no
subcommand name needed. `ra overlay <activity_id>` is the one other command.

The HTML report (`html_report.py`) renders the same data as a self-contained "instrument
panel": stat tiles up top, then one card per run with a proportional run/walk segment bar
(amber = run, teal = walk/recovery) and a cardiac-drift badge. It's what
`garmin-running-data`'s scheduled sync regenerates nightly at
`$DATA_DIR/report.html` — open that file directly in a browser, no server needed.

## What's in the report

For each run in the window: distance/duration/avg HR, cardiac drift, a run/walk segment
breakdown (count, avg duration, avg HR drop during walk segments), pace at ~150bpm, and
optionally time-to-reach a target HR ceiling. Plus a period summary (total distance,
average cardiac drift).

## Metric definitions and known limitations

These are v1 heuristics computed directly from recorded samples — descriptive stats, not
validated models or predictions. See `src/running_analytics/metrics.py` for the
implementations and docstrings. Notably:

- **Run/walk segmentation** uses Garmin's raw FIT `cadence` field, which is **single-leg**
  strides/min (e.g. ~80 for an easy run), *not* the doubled "steps per minute" Garmin
  Connect's UI shows. The default walk/run threshold (65) was picked by inspecting real
  data (observed: walking ~45-65, easy running ~75-95) — tune
  `DEFAULT_WALK_CADENCE_THRESHOLD` as you gather more runs, ideally against a run where
  you know exactly when you walked.
- **Cardiac drift** compares average HR-per-speed in the second half of a run vs the
  first half (by elapsed time, not distance). A positive number means the same pace cost
  more heartbeats later on. It's noisy for short or highly variable-effort runs (e.g. lots
  of run/walk switching) — the period average is more informative than any single run.
- **Time to reach an HR ceiling** and **pace at ~150bpm** are read directly off samples;
  GPS pace and chest-strap HR both have real-world noise, so treat single-run numbers as
  rough, not precise.

Nothing here is a prediction — no uncertainty intervals are implied by a metric value
alone. Model-based prediction (e.g. workout distance forecasting) is a later phase.

## Development

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

Tests use synthetic `ActivitySample` sequences (see `tests/`) — no dependency on real
Garmin data.
