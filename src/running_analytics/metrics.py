"""Derived per-run metrics computed from raw ActivitySample time-series.

These are heuristic v1 implementations, not validated statistical models. Thresholds
(e.g. what counts as "walking" cadence) are configurable defaults, not universal
constants — tune them against your own data as you gather more runs. Where a metric
can't be computed (e.g. no HR data, run never reaches a target HR), functions return
None rather than a misleading number.
"""

from dataclasses import dataclass
from datetime import datetime

from garmin_running_data.models import ActivitySample

# Garmin's raw FIT `cadence` field is single-leg strides/min (e.g. ~80 for an easy
# run), not the doubled "steps per minute" figure Garmin Connect displays in its UI.
# Observed real data: walking ~45-65, easy running ~75-95. 65 is a starting default —
# tune against your own data (e.g. by eyeballing a known walk break) as you gather more.
DEFAULT_WALK_CADENCE_THRESHOLD = 65.0


def seconds_to_hr_ceiling(samples: list[ActivitySample], hr_ceiling: int) -> float | None:
    """Seconds from the first sample until HR first reaches/exceeds hr_ceiling.

    Returns None if the run never reaches the ceiling (can't answer "how long until
    HR hits X" from data that never got there).
    """
    if not samples:
        return None
    start = samples[0].timestamp
    for sample in samples:
        if sample.hr is not None and sample.hr >= hr_ceiling:
            return (sample.timestamp - start).total_seconds()
    return None


def cardiac_drift(samples: list[ActivitySample]) -> float | None:
    """Percent increase in HR-per-speed (beats per m/s) from the first half of the
    run to the second half, split by elapsed time. A positive number means the same
    pace cost more heartbeats later in the run (classic cardiac drift / fatigue
    signal); a value near zero or negative suggests good durability.

    Requires at least a few samples with both hr and pace_s_per_km on each half;
    returns None otherwise (e.g. very short runs, missing HR strap data).
    """
    usable = [s for s in samples if s.hr is not None and s.pace_s_per_km and s.pace_s_per_km > 0]
    if len(usable) < 4:
        return None

    midpoint_time = usable[0].timestamp + (usable[-1].timestamp - usable[0].timestamp) / 2
    first_half = [s for s in usable if s.timestamp <= midpoint_time]
    second_half = [s for s in usable if s.timestamp > midpoint_time]
    if len(first_half) < 2 or len(second_half) < 2:
        return None

    first_ratio = _avg_hr_per_speed(first_half)
    second_ratio = _avg_hr_per_speed(second_half)
    if first_ratio is None or first_ratio == 0 or second_ratio is None:
        return None

    return (second_ratio - first_ratio) / first_ratio * 100


def _avg_hr_per_speed(samples: list[ActivitySample]) -> float | None:
    ratios = []
    for s in samples:
        if s.hr is None or not s.pace_s_per_km or s.pace_s_per_km <= 0:
            continue
        speed_m_s = 1000 / s.pace_s_per_km
        if speed_m_s > 0:
            ratios.append(s.hr / speed_m_s)
    if not ratios:
        return None
    return sum(ratios) / len(ratios)


@dataclass
class Interval:
    kind: str  # "run" or "walk"
    start: datetime
    end: datetime
    duration_s: float
    avg_hr: float | None
    start_hr: int | None
    end_hr: int | None


def run_walk_intervals(
    samples: list[ActivitySample],
    cadence_threshold: float = DEFAULT_WALK_CADENCE_THRESHOLD,
) -> list[Interval]:
    """Segment a run into contiguous run/walk intervals using cadence as the signal
    (walking cadence is reliably lower than running cadence, unlike pace which is
    noisy on GPS-only data). Samples with no cadence reading are assigned to
    whichever interval is currently open, or "run" if none is open yet.

    This is a heuristic, not a validated classifier — cadence_threshold is tunable.
    """
    if not samples:
        return []

    def classify(cadence: float | None, current_kind: str) -> str:
        if cadence is None:
            return current_kind
        return "walk" if cadence < cadence_threshold else "run"

    intervals: list[Interval] = []
    current_kind = classify(samples[0].cadence, "run")
    bucket: list[ActivitySample] = [samples[0]]

    for sample in samples[1:]:
        kind = classify(sample.cadence, current_kind)
        if kind != current_kind:
            intervals.append(_build_interval(current_kind, bucket))
            bucket = [sample]
            current_kind = kind
        else:
            bucket.append(sample)

    intervals.append(_build_interval(current_kind, bucket))
    return intervals


def _build_interval(kind: str, bucket: list[ActivitySample]) -> Interval:
    hrs = [s.hr for s in bucket if s.hr is not None]
    return Interval(
        kind=kind,
        start=bucket[0].timestamp,
        end=bucket[-1].timestamp,
        duration_s=(bucket[-1].timestamp - bucket[0].timestamp).total_seconds(),
        avg_hr=(sum(hrs) / len(hrs)) if hrs else None,
        start_hr=bucket[0].hr,
        end_hr=bucket[-1].hr,
    )


def pace_at_hr(samples: list[ActivitySample], hr_target: int, tolerance: int = 3) -> float | None:
    """Average pace (s/km) across samples where HR is within `tolerance` bpm of
    hr_target. Lets you track "what pace did I run at ~150bpm" over time. Returns
    None if no samples fall in that HR band.
    """
    matching = [
        s.pace_s_per_km
        for s in samples
        if s.hr is not None
        and abs(s.hr - hr_target) <= tolerance
        and s.pace_s_per_km
        and s.pace_s_per_km > 0
    ]
    if not matching:
        return None
    return sum(matching) / len(matching)
