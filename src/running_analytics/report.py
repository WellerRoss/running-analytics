from datetime import UTC, datetime, timedelta

from garmin_running_data.models import Activity, ActivitySample
from garmin_running_data.storage import Storage

from running_analytics.metrics import (
    Interval,
    cardiac_drift,
    pace_at_hr,
    run_walk_intervals,
    seconds_to_hr_ceiling,
)


def _as_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _load_samples(storage: Storage, activity_id: str) -> list[ActivitySample]:
    df = storage.read_samples(activity_id)
    if df.is_empty():
        return []
    return [ActivitySample(**row) for row in df.iter_rows(named=True)]


def _recent_activities(storage: Storage, days: int) -> list[tuple[Activity, list[ActivitySample]]]:
    df = storage.read_activities()
    if df.is_empty():
        return []

    cutoff = datetime.now(UTC) - timedelta(days=days)
    results = []
    for row in df.iter_rows(named=True):
        if row["start_time"] is None:
            continue
        activity = Activity(**row)
        if _as_aware(activity.start_time) < cutoff:
            continue
        samples = _load_samples(storage, activity.activity_id)
        results.append((activity, samples))

    results.sort(key=lambda pair: pair[0].start_time, reverse=True)
    return results


def _format_pace(seconds_per_km: float) -> str:
    minutes, seconds = divmod(int(seconds_per_km), 60)
    return f"{minutes}:{seconds:02d}"


def _interval_summary(intervals: list[Interval]) -> str:
    runs = [i for i in intervals if i.kind == "run"]
    walks = [i for i in intervals if i.kind == "walk"]
    if not runs and not walks:
        return "no cadence data"

    parts = []
    if runs:
        avg_run = sum(i.duration_s for i in runs) / len(runs)
        parts.append(f"{len(runs)} run segments (avg {avg_run:.0f}s)")
    if walks:
        avg_walk = sum(i.duration_s for i in walks) / len(walks)
        recoveries = [
            i.start_hr - i.end_hr
            for i in walks
            if i.start_hr is not None and i.end_hr is not None and i.duration_s > 0
        ]
        recovery_str = ""
        if recoveries:
            avg_recovery = sum(recoveries) / len(recoveries)
            recovery_str = f", avg HR drop {avg_recovery:.0f} bpm"
        parts.append(f"{len(walks)} walk segments (avg {avg_walk:.0f}s{recovery_str})")
    return "; ".join(parts)


def build_report(storage: Storage, days: int, hr_ceiling: int | None = None) -> str:
    """Render a Markdown report of derived metrics for runs in the last `days` days.

    All metrics here are descriptive statistics computed directly from recorded
    samples, not predictions — but they're still estimates: GPS/HR-strap noise,
    missing samples, and heuristic run/walk classification (see metrics.py) mean
    small differences between runs shouldn't be over-interpreted.
    """
    activities = _recent_activities(storage, days)
    if not activities:
        return (
            f"No activities in the last {days} days. "
            "Run `grd sync` in garmin-running-data first."
        )

    lines = [f"# Running report: last {days} days", ""]

    drifts = []
    for activity, samples in activities:
        distance_km = activity.distance_m / 1000
        duration_min = activity.duration_s / 60
        lines.append(f"## {activity.start_time:%Y-%m-%d %H:%M} — {distance_km:.2f} km")
        lines.append("")
        lines.append(f"- Duration: {duration_min:.1f} min, avg HR: {activity.avg_hr or '?'}")

        drift = cardiac_drift(samples)
        if drift is not None:
            drifts.append(drift)
            lines.append(f"- Cardiac drift (2nd half vs 1st half HR/speed): {drift:+.1f}%")
        else:
            lines.append("- Cardiac drift: not enough HR/pace data")

        intervals = run_walk_intervals(samples)
        lines.append(f"- Run/walk segments: {_interval_summary(intervals)}")

        if hr_ceiling is not None:
            seconds = seconds_to_hr_ceiling(samples, hr_ceiling)
            if seconds is not None:
                lines.append(f"- Time to reach {hr_ceiling} bpm: {seconds / 60:.1f} min")
            else:
                lines.append(f"- Never reached {hr_ceiling} bpm")

        pace_150 = pace_at_hr(samples, hr_target=150)
        if pace_150 is not None:
            lines.append(f"- Pace at ~150 bpm: {_format_pace(pace_150)}/km")

        lines.append("")

    lines.append("## Period summary")
    lines.append("")
    total_km = sum(a.distance_m for a, _ in activities) / 1000
    lines.append(f"- {len(activities)} runs, {total_km:.1f} km total")
    if drifts:
        avg_drift = sum(drifts) / len(drifts)
        lines.append(f"- Average cardiac drift: {avg_drift:+.1f}% (n={len(drifts)} runs)")

    return "\n".join(lines)
