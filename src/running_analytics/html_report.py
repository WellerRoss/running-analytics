"""Static HTML report — an 'instrument panel' reading of the same data as report.py.

Renders a self-contained fragment (a root <div class="rr-report"> plus a scoped
<style> block). `build_html_document` wraps that fragment into a full standalone
HTML file for opening directly in a browser; the fragment alone is also what's
published as a one-off claude.ai artifact preview (the Artifact host supplies its
own <html>/<head>/<body> skeleton).

Design: run segments and walk segments get their own accent hues (amber = effort/
heat, teal = recovery) and every run row shows a proportional bar of its run/walk
split — the split is the load-bearing visual, not a decorative chart. Cardiac
drift gets a separate semantic good/warning/serious badge, deliberately a
different hue family from the run/walk accents so the two kinds of color never
get read as the same signal.
"""

import html as _html

from garmin_running_data.models import Activity, ActivitySample
from garmin_running_data.storage import Storage

from running_analytics.data import format_pace, recent_activities
from running_analytics.metrics import cardiac_drift, pace_at_hr, run_walk_intervals

_STYLE = """
.rr-report {
  --bg: #f2f0e4;
  --page: #ebe8da;
  --surface: #fffdf8;
  --ink: #1b1a16;
  --ink-2: #5b5848;
  --muted: #726d5c;
  --border: rgba(27, 26, 22, 0.12);
  --heat: #b8720f;
  --heat-soft: #b8720f26;
  --recovery: #1f6f66;
  --recovery-soft: #1f6f6626;
  --good: #0ca30c;
  --warning: #a66a06;
  --warning-bg: #fab21926;
  --serious: #b23a1f;
  --serious-bg: #ec835a26;
  color-scheme: light;
  background: var(--page);
  color: var(--ink);
  font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  padding: clamp(20px, 4vw, 48px);
  line-height: 1.45;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) .rr-report {
    --bg: #14140f;
    --page: #0f0f0b;
    --surface: #1d1c16;
    --ink: #f5f3ea;
    --ink-2: #b8b39f;
    --muted: #837f6c;
    --border: rgba(245, 243, 234, 0.14);
    --heat: #d99a35;
    --heat-soft: #d99a3530;
    --recovery: #35a394;
    --recovery-soft: #35a39430;
    --good: #0ca30c;
    --warning: #fab219;
    --warning-bg: #fab21930;
    --serious: #ec835a;
    --serious-bg: #ec835a30;
    color-scheme: dark;
  }
}
.rr-report[data-theme="dark"], :root[data-theme="dark"] .rr-report {
  --bg: #14140f;
  --page: #0f0f0b;
  --surface: #1d1c16;
  --ink: #f5f3ea;
  --ink-2: #b8b39f;
  --muted: #837f6c;
  --border: rgba(245, 243, 234, 0.14);
  --heat: #d99a35;
  --heat-soft: #d99a3530;
  --recovery: #35a394;
  --recovery-soft: #35a39430;
  --good: #0ca30c;
  --warning: #fab219;
  --warning-bg: #fab21930;
  --serious: #ec835a;
  --serious-bg: #ec835a30;
  color-scheme: dark;
}
.rr-report * { box-sizing: border-box; }
.rr-wrap { max-width: 760px; margin: 0 auto; }
.rr-head { margin-bottom: 28px; }
.rr-eyebrow {
  font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--muted); font-weight: 600; margin: 0 0 6px;
}
.rr-title {
  font-size: clamp(22px, 3vw, 30px); font-weight: 700; margin: 0;
  text-wrap: balance; letter-spacing: -0.01em;
}
.rr-stats {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1px; background: var(--border); border: 1px solid var(--border);
  border-radius: 10px; overflow: hidden; margin-bottom: 32px;
}
.rr-stat { background: var(--surface); padding: 16px 18px; }
.rr-stat-label {
  font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--muted); font-weight: 600; margin: 0 0 6px;
}
.rr-stat-value {
  font-family: ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono", monospace;
  font-size: 22px; font-weight: 600; font-variant-numeric: tabular-nums;
  margin: 0;
}
.rr-log { display: flex; flex-direction: column; gap: 10px; margin-bottom: 28px; }
.rr-run {
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
  padding: 14px 18px;
}
.rr-run-top {
  display: flex; justify-content: space-between; align-items: baseline;
  gap: 12px; flex-wrap: wrap; margin-bottom: 8px;
}
.rr-run-date { font-weight: 600; font-size: 14px; }
.rr-run-metrics {
  font-family: ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono", monospace;
  font-size: 13px; color: var(--ink-2); font-variant-numeric: tabular-nums;
  display: flex; gap: 14px; flex-wrap: wrap;
}
.rr-split {
  display: flex; height: 8px; border-radius: 4px; overflow: hidden;
  background: var(--border); margin-bottom: 8px;
}
.rr-split-run { background: var(--heat); }
.rr-split-walk { background: var(--recovery); }
.rr-run-foot {
  display: flex; justify-content: space-between; align-items: center;
  gap: 12px; flex-wrap: wrap; font-size: 12.5px; color: var(--ink-2);
}
.rr-legend { display: flex; gap: 14px; flex-wrap: wrap; }
.rr-legend-item { display: inline-flex; align-items: center; gap: 6px; }
.rr-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.rr-badge {
  display: inline-flex; align-items: center; gap: 5px; padding: 2px 9px;
  border-radius: 999px; font-size: 12px; font-weight: 600;
}
.rr-badge-good { color: var(--good); background: color-mix(in srgb, var(--good) 16%, transparent); }
.rr-badge-warning { color: var(--warning); background: var(--warning-bg); }
.rr-badge-serious { color: var(--serious); background: var(--serious-bg); }
.rr-empty { color: var(--ink-2); font-size: 14px; }
.rr-foot-note {
  font-size: 12px; color: var(--muted); border-top: 1px solid var(--border);
  padding-top: 14px; margin-top: 8px;
}
"""


def _esc(value: object) -> str:
    return _html.escape(str(value))


def _drift_badge(drift: float | None) -> str:
    if drift is None:
        return '<span class="rr-badge" style="color:var(--muted)">no data</span>'
    if drift < 15:
        cls, label = "good", "steady"
    elif drift < 30:
        cls, label = "warning", "drifting"
    else:
        cls, label = "serious", "high drift"
    return f'<span class="rr-badge rr-badge-{cls}">{drift:+.0f}% &middot; {label}</span>'


def _split_bar(samples: list[ActivitySample]) -> str:
    intervals = run_walk_intervals(samples)
    run_s = sum(i.duration_s for i in intervals if i.kind == "run")
    walk_s = sum(i.duration_s for i in intervals if i.kind == "walk")
    total = run_s + walk_s
    if total <= 0:
        return ""
    run_pct = run_s / total * 100
    walk_pct = 100 - run_pct
    n_run = sum(1 for i in intervals if i.kind == "run")
    n_walk = sum(1 for i in intervals if i.kind == "walk")
    bar = (
        '<div class="rr-split">'
        f'<div class="rr-split-run" style="width:{run_pct:.1f}%"></div>'
        f'<div class="rr-split-walk" style="width:{walk_pct:.1f}%"></div>'
        "</div>"
    )
    run_label = f"{n_run} run seg{'s' if n_run != 1 else ''}"
    walk_label = f"{n_walk} walk seg{'s' if n_walk != 1 else ''}"
    legend = (
        '<div class="rr-legend">'
        '<span class="rr-legend-item">'
        '<span class="rr-dot" style="background:var(--heat)"></span>'
        f"{run_label}</span>"
        '<span class="rr-legend-item">'
        '<span class="rr-dot" style="background:var(--recovery)"></span>'
        f"{walk_label}</span>"
        "</div>"
    )
    return bar + legend


def _run_row(activity: Activity, samples: list[ActivitySample]) -> str:
    distance_km = activity.distance_m / 1000
    duration_min = activity.duration_s / 60
    drift = cardiac_drift(samples)
    pace_150 = pace_at_hr(samples, hr_target=150)
    pace_str = f"{format_pace(pace_150)}/km @150bpm" if pace_150 is not None else None

    metrics = [f"{distance_km:.2f} km", f"{duration_min:.0f} min"]
    if activity.avg_hr:
        metrics.append(f"{activity.avg_hr} bpm avg")
    if pace_str:
        metrics.append(pace_str)

    date_label = _esc(f"{activity.start_time:%a %b %-d, %H:%M}")
    metrics_label = " &nbsp;&middot;&nbsp; ".join(_esc(m) for m in metrics)

    return f"""
    <div class="rr-run">
      <div class="rr-run-top">
        <span class="rr-run-date">{date_label}</span>
        <span class="rr-run-metrics">{metrics_label}</span>
      </div>
      {_split_bar(samples)}
      <div class="rr-run-foot">
        {_drift_badge(drift)}
        <span>cardiac drift, 1st half &rarr; 2nd half</span>
      </div>
    </div>
    """


def build_html_report(storage: Storage, days: int, hr_ceiling: int | None = None) -> str:
    """Render the report as a self-contained HTML fragment (root div + scoped style)."""
    activities = recent_activities(storage, days)

    if not activities:
        body = f"""
        <div class="rr-wrap">
          <div class="rr-head">
            <p class="rr-eyebrow">Running log</p>
            <h1 class="rr-title">Last {days} days</h1>
          </div>
          <p class="rr-empty">No activities in the last {days} days.
          Run <code>grd sync</code> in garmin-running-data first.</p>
        </div>
        """
        return f'<style>{_STYLE}</style><div class="rr-report">{body}</div>'

    total_km = sum(a.distance_m for a, _ in activities) / 1000
    total_min = sum(a.duration_s for a, _ in activities) / 60
    drifts = [d for _, s in activities if (d := cardiac_drift(s)) is not None]
    avg_drift = sum(drifts) / len(drifts) if drifts else None

    stats = [
        ("Runs", str(len(activities))),
        ("Distance", f"{total_km:.1f} km"),
        ("Time", f"{total_min / 60:.1f} hr"),
        ("Avg drift", f"{avg_drift:+.0f}%" if avg_drift is not None else "—"),
    ]
    stats_html = "".join(
        f'<div class="rr-stat"><p class="rr-stat-label">{_esc(label)}</p>'
        f'<p class="rr-stat-value">{_esc(value)}</p></div>'
        for label, value in stats
    )

    rows_html = "".join(_run_row(activity, samples) for activity, samples in activities)

    oldest, newest = activities[-1][0].start_time, activities[0][0].start_time
    date_range = f"{oldest:%b %-d} &ndash; {newest:%b %-d}"

    body = f"""
    <div class="rr-wrap">
      <div class="rr-head">
        <p class="rr-eyebrow">Running log &middot; {date_range}</p>
        <h1 class="rr-title">Last {days} days</h1>
      </div>
      <div class="rr-stats">{stats_html}</div>
      <div class="rr-log">{rows_html}</div>
      <p class="rr-foot-note">
        Cardiac drift compares HR-per-speed in the second half of each run vs the
        first half — a rough fatigue signal, not a validated metric. Run/walk
        segments are inferred from stride cadence. Generated by running-analytics.
      </p>
    </div>
    """
    return f'<style>{_STYLE}</style><div class="rr-report">{body}</div>'


def build_html_document(storage: Storage, days: int, hr_ceiling: int | None = None) -> str:
    """Wrap the fragment into a full standalone HTML document for local file output."""
    fragment = build_html_report(storage, days, hr_ceiling)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Running report — last {days} days</title>
</head>
<body style="margin:0">
{fragment}
</body>
</html>
"""
