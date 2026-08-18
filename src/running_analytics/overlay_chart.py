"""Target-vs-actual HR chart for one activity — the same information Garmin
Connect's own "Workout Target" charts show (a real HR line with a shaded target
band/line per lap), reconstructed from garmin_running_data.joined.activity_overlay
rather than a dense API endpoint (none exists — see garmin-running-data's
docs/adaptive_plan_probe_findings.md).

Deliberately HR-only: a matched workout's steps can target HR, pace, cadence, or
power — plotting a non-HR target range on an HR-scaled y-axis would be actively
wrong, not just unhelpful, so any lap whose target_type isn't "heart_rate_zone" or
"heart_rate_point" renders with no band at all (same as Garmin's own chart, which
only shades HR-targeted steps).

A "zone" target (target_low != target_high) draws a filled band; a "point" target
(coach_adaptive's single-bpm case, target_low == target_high) draws a horizontal
reference line instead — a filled zero-height rect would just be invisible.
"""

import html as _html

from garmin_running_data.joined import LapOverlay, activity_overlay
from garmin_running_data.models import Activity
from garmin_running_data.storage import Storage

from running_analytics.data import as_aware, load_activity, load_samples

_STYLE = """
.rr-overlay {
  --bg: #f2f0e4;
  --page: #ebe8da;
  --surface: #fffdf8;
  --ink: #1b1a16;
  --ink-2: #5b5848;
  --muted: #726d5c;
  --border: rgba(27, 26, 22, 0.12);
  --heat: #b8720f;
  --target-fill: color-mix(in srgb, var(--ink) 14%, transparent);
  --target-line: color-mix(in srgb, var(--ink) 45%, transparent);
  color-scheme: light;
  background: var(--page);
  color: var(--ink);
  font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  padding: clamp(20px, 4vw, 48px);
  line-height: 1.45;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) .rr-overlay {
    --bg: #14140f;
    --page: #0f0f0b;
    --surface: #1d1c16;
    --ink: #f5f3ea;
    --ink-2: #b8b39f;
    --muted: #837f6c;
    --border: rgba(245, 243, 234, 0.14);
    --heat: #d99a35;
    color-scheme: dark;
  }
}
.rr-overlay[data-theme="dark"], :root[data-theme="dark"] .rr-overlay {
  --bg: #14140f;
  --page: #0f0f0b;
  --surface: #1d1c16;
  --ink: #f5f3ea;
  --ink-2: #b8b39f;
  --muted: #837f6c;
  --border: rgba(245, 243, 234, 0.14);
  --heat: #d99a35;
  color-scheme: dark;
}
.rr-overlay * { box-sizing: border-box; }
.rr-wrap { max-width: 820px; margin: 0 auto; }
.rr-head { margin-bottom: 20px; }
.rr-eyebrow {
  font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--muted); font-weight: 600; margin: 0 0 6px;
}
.rr-title {
  font-size: clamp(20px, 3vw, 26px); font-weight: 700; margin: 0 0 6px;
  text-wrap: balance; letter-spacing: -0.01em;
}
.rr-sub {
  font-family: ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono", monospace;
  font-size: 13px; color: var(--ink-2);
}
.rr-chart-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
  padding: 16px 18px 10px; margin-bottom: 16px;
}
.rr-chart-svg { width: 100%; height: auto; display: block; }
.rr-axis-line { stroke: var(--border); stroke-width: 1; }
.rr-axis-label { fill: var(--muted); font-size: 11px; }
.rr-hr-line { fill: none; stroke: var(--heat); stroke-width: 2; }
.rr-target-band { fill: var(--target-fill); }
.rr-target-line { stroke: var(--target-line); stroke-width: 3; }
.rr-legend { display: flex; gap: 16px; flex-wrap: wrap; margin: 10px 2px 2px; }
.rr-legend-item {
  display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px;
  color: var(--ink-2);
}
.rr-legend-swatch { width: 14px; height: 3px; border-radius: 2px; display: inline-block; }
.rr-legend-swatch.rr-target { background: var(--target-line); opacity: 0.7; }
.rr-details summary {
  cursor: pointer; font-size: 13px; color: var(--ink-2); font-weight: 600;
  padding: 4px 0;
}
.rr-lap-table { width: 100%; border-collapse: collapse; font-size: 12.5px; margin-top: 8px; }
.rr-lap-table th, .rr-lap-table td {
  text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--border);
  font-family: ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono", monospace;
}
.rr-lap-table th {
  font-family: -apple-system, "Segoe UI", Roboto, sans-serif; color: var(--muted);
  font-weight: 600; text-transform: uppercase; font-size: 10.5px; letter-spacing: 0.04em;
}
.rr-empty { color: var(--ink-2); font-size: 14px; }
.rr-foot-note {
  font-size: 12px; color: var(--muted); border-top: 1px solid var(--border);
  padding-top: 14px; margin-top: 8px;
}
"""

_CHART_W = 900.0
_CHART_H = 320.0
_MARGIN_LEFT = 46.0
_MARGIN_RIGHT = 16.0
_MARGIN_TOP = 16.0
_MARGIN_BOTTOM = 32.0
_PLOT_W = _CHART_W - _MARGIN_LEFT - _MARGIN_RIGHT
_PLOT_H = _CHART_H - _MARGIN_TOP - _MARGIN_BOTTOM


def _esc(value: object) -> str:
    return _html.escape(str(value))


def _nice_step(span: float, target_ticks: int = 5) -> float:
    if span <= 0:
        return 1.0
    raw = span / target_ticks
    for step in (5, 10, 20, 25, 50, 100):
        if raw <= step:
            return float(step)
    return float(raw)


def _format_mmss(seconds: float) -> str:
    total = int(seconds)
    m, s = divmod(total, 60)
    return f"{m}:{s:02d}"


def _format_target(lap: LapOverlay) -> str:
    if lap.target_type is None or lap.target_low is None:
        return "—"
    if lap.target_low == lap.target_high:
        return f"{lap.target_low:g} {lap.target_type}"
    return f"{lap.target_low:g}–{lap.target_high:g} {lap.target_type}"


def _lap_boundaries(overlay: list[LapOverlay]) -> list[tuple[float, float, LapOverlay]]:
    """Real laps are contiguous in time (confirmed against real data), so cumulative
    duration reconstructs each lap's [start, end) offset from the activity start
    without needing lap-level timestamps."""
    bounds = []
    t = 0.0
    for lap in overlay:
        t0, t1 = t, t + lap.actual_duration_s
        bounds.append((t0, t1, lap))
        t = t1
    return bounds


def _hr_scale_domain(
    hr_points: list[tuple[float, int]], bounds: list[tuple[float, float, LapOverlay]]
) -> tuple[float, float]:
    values: list[float] = [hr for _, hr in hr_points]
    for _, _, lap in bounds:
        if (
            lap.target_type in ("heart_rate_zone", "heart_rate_point")
            and lap.target_low is not None
        ):
            values.append(lap.target_low)
            values.append(lap.target_high or lap.target_low)
    if not values:
        return 60.0, 200.0
    return max(0.0, min(values) - 10), max(values) + 10


def _svg_chart(
    hr_points: list[tuple[float, int]], bounds: list[tuple[float, float, LapOverlay]]
) -> str:
    total_s = bounds[-1][1] if bounds else (hr_points[-1][0] if hr_points else 1.0)
    y_min, y_max = _hr_scale_domain(hr_points, bounds)

    def x(t: float) -> float:
        return _MARGIN_LEFT + (t / total_s) * _PLOT_W if total_s > 0 else _MARGIN_LEFT

    def y(hr: float) -> float:
        return _MARGIN_TOP + _PLOT_H - ((hr - y_min) / (y_max - y_min)) * _PLOT_H

    parts = []

    # Target bands/lines, drawn under the HR line.
    for t0, t1, lap in bounds:
        if lap.target_type not in ("heart_rate_zone", "heart_rate_point") or lap.target_low is None:
            continue
        lo = lap.target_low
        hi = lap.target_high if lap.target_high is not None else lo
        title = (
            f"{_esc(lap.step_type)}: target {_format_target(lap)}, "
            f"actual avg {lap.actual_avg_hr} bpm"
        )
        if lo == hi:
            yy = y(lo)
            parts.append(
                f'<line class="rr-target-line" x1="{x(t0):.1f}" y1="{yy:.1f}" '
                f'x2="{x(t1):.1f}" y2="{yy:.1f}"><title>{title}</title></line>'
            )
        else:
            y_hi, y_lo = y(hi), y(lo)
            parts.append(
                f'<rect class="rr-target-band" x="{x(t0):.1f}" y="{y_hi:.1f}" '
                f'width="{(x(t1) - x(t0)):.1f}" height="{(y_lo - y_hi):.1f}">'
                f"<title>{title}</title></rect>"
            )

    # Y-axis gridlines + labels.
    y_step = _nice_step(y_max - y_min)
    tick = y_min - (y_min % y_step) + y_step
    while tick < y_max:
        yy = y(tick)
        parts.append(
            f'<line class="rr-axis-line" x1="{_MARGIN_LEFT:.1f}" y1="{yy:.1f}" '
            f'x2="{_CHART_W - _MARGIN_RIGHT:.1f}" y2="{yy:.1f}"/>'
        )
        parts.append(
            f'<text class="rr-axis-label" x="{_MARGIN_LEFT - 8:.1f}" y="{yy + 3:.1f}" '
            f'text-anchor="end">{int(tick)}</text>'
        )
        tick += y_step

    # X-axis ticks (time).
    x_step = _nice_step(total_s, target_ticks=6)
    t_tick = 0.0
    while t_tick <= total_s:
        xx = x(t_tick)
        parts.append(
            f'<text class="rr-axis-label" x="{xx:.1f}" y="{_CHART_H - 8:.1f}" '
            f'text-anchor="middle">{_format_mmss(t_tick)}</text>'
        )
        t_tick += x_step

    # HR line, drawn on top.
    if hr_points:
        path = " ".join(
            f"{'M' if i == 0 else 'L'}{x(t):.1f},{y(hr):.1f}" for i, (t, hr) in enumerate(hr_points)
        )
        parts.append(f'<path class="rr-hr-line" d="{path}"/>')

    body = "".join(parts)
    return (
        f'<svg class="rr-chart-svg" viewBox="0 0 {_CHART_W:.0f} {_CHART_H:.0f}" '
        f'role="img" aria-label="Heart rate vs. workout target over time">{body}</svg>'
    )


def _lap_table(overlay: list[LapOverlay]) -> str:
    rows = "".join(
        f"<tr><td>{lap.lap_index}</td><td>{_esc(lap.step_type)}</td>"
        f"<td>{_esc(_format_target(lap))}</td>"
        f"<td>{lap.actual_avg_hr if lap.actual_avg_hr is not None else '—'}</td>"
        f"<td>{lap.actual_max_hr if lap.actual_max_hr is not None else '—'}</td>"
        f"<td>{_format_mmss(lap.actual_duration_s)}</td></tr>"
        for lap in overlay
    )
    return f"""
    <details class="rr-details">
      <summary>Lap-by-lap data ({len(overlay)} laps)</summary>
      <table class="rr-lap-table">
        <thead><tr>
          <th>#</th><th>Step</th><th>Target</th><th>Avg HR</th><th>Max HR</th><th>Duration</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </details>
    """


def _empty_fragment(message: str) -> str:
    body = f"""
    <div class="rr-wrap">
      <div class="rr-head">
        <p class="rr-eyebrow">Workout target overlay</p>
        <h1 class="rr-title">No chart available</h1>
      </div>
      <p class="rr-empty">{_esc(message)}</p>
    </div>
    """
    return f'<style>{_STYLE}</style><div class="rr-overlay">{body}</div>'


def build_overlay_chart(storage: Storage, activity_id: str) -> str:
    """Renders a self-contained HTML fragment: a real HR line for the activity with
    the matched workout's HR target (if any) shaded per lap, plus a lap-by-lap data
    table. Returns an explanatory empty-state fragment if the activity doesn't exist,
    has no matched/reconstructable workout, or has no HR samples."""
    activity: Activity | None = load_activity(storage, activity_id)
    if activity is None:
        return _empty_fragment(f'No activity found with id "{activity_id}".')

    overlay = activity_overlay(storage, activity_id)
    if overlay is None:
        return _empty_fragment(
            "No target-vs-actual overlay available for this activity — it may not be "
            "matched to a prescribed workout, lack lap data (run `grd "
            "sync-activity-details`), or its lap count may not line up with the "
            "matched workout's step count."
        )

    samples = load_samples(storage, activity_id)
    start = as_aware(activity.start_time)
    hr_points = sorted(
        (
            (as_aware(s.timestamp) - start).total_seconds(),
            s.hr,
        )
        for s in samples
        if s.hr is not None
    )
    if not hr_points:
        return _empty_fragment("This activity has no heart-rate samples to chart.")

    bounds = _lap_boundaries(overlay)
    has_hr_target = any(
        lap.target_type in ("heart_rate_zone", "heart_rate_point") for lap in overlay
    )

    chart_svg = _svg_chart(hr_points, bounds)
    legend_items = [
        '<span class="rr-legend-item"><span class="rr-legend-swatch" '
        'style="background:var(--heat)"></span>Heart rate</span>'
    ]
    if has_hr_target:
        legend_items.append(
            '<span class="rr-legend-item"><span class="rr-legend-swatch rr-target">'
            "</span>Workout target</span>"
        )
    legend_html = f'<div class="rr-legend">{"".join(legend_items)}</div>'

    date_label = _esc(f"{activity.start_time:%a %b %-d, %Y %H:%M}")
    distance_km = activity.distance_m / 1000
    duration_min = activity.duration_s / 60
    sub = f"{date_label} &middot; {distance_km:.2f} km &middot; {duration_min:.0f} min"
    if not has_hr_target:
        note = (
            "This activity's matched workout has no heart-rate target (its targets "
            "are pace/cadence/power-based), so no target band is shown — matches "
            "Garmin's own chart behavior for non-HR-targeted steps."
        )
    else:
        note = (
            "Shaded band = target HR zone for that lap; a thin line = a single-value "
            "target (no range). Reconstructed from workout step targets + real "
            "per-lap execution data — see garmin-running-data's "
            "docs/adaptive_plan_probe_findings.md for how."
        )

    body = f"""
    <div class="rr-wrap">
      <div class="rr-head">
        <p class="rr-eyebrow">Workout target overlay</p>
        <h1 class="rr-title">{_esc(activity.activity_id)}</h1>
        <p class="rr-sub">{sub}</p>
      </div>
      <div class="rr-chart-card">
        {chart_svg}
        {legend_html}
      </div>
      {_lap_table(overlay)}
      <p class="rr-foot-note">{note}</p>
    </div>
    """
    return f'<style>{_STYLE}</style><div class="rr-overlay">{body}</div>'


def build_overlay_document(storage: Storage, activity_id: str) -> str:
    """Wraps the fragment into a full standalone HTML document."""
    fragment = build_overlay_chart(storage, activity_id)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Workout target overlay — {_esc(activity_id)}</title>
</head>
<body style="margin:0">
{fragment}
</body>
</html>
"""
