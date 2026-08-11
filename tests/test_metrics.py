from datetime import UTC, datetime, timedelta

from garmin_running_data.models import ActivitySample

from running_analytics.metrics import (
    cardiac_drift,
    pace_at_hr,
    run_walk_intervals,
    seconds_to_hr_ceiling,
)

START = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC)


def _sample(offset_s, hr=None, pace=None, cadence=None):
    return ActivitySample(
        activity_id="a1",
        timestamp=START + timedelta(seconds=offset_s),
        hr=hr,
        pace_s_per_km=pace,
        cadence=cadence,
    )


def test_seconds_to_hr_ceiling_found():
    samples = [_sample(0, hr=120), _sample(60, hr=140), _sample(120, hr=160)]
    assert seconds_to_hr_ceiling(samples, 150) == 120


def test_seconds_to_hr_ceiling_never_reached():
    samples = [_sample(0, hr=120), _sample(60, hr=130)]
    assert seconds_to_hr_ceiling(samples, 150) is None


def test_seconds_to_hr_ceiling_empty():
    assert seconds_to_hr_ceiling([], 150) is None


def test_cardiac_drift_detects_positive_drift():
    # same pace throughout, but HR climbs in the second half -> positive drift
    samples = [_sample(i * 10, hr=140, pace=300) for i in range(5)]
    samples += [_sample(50 + i * 10, hr=160, pace=300) for i in range(5)]
    drift = cardiac_drift(samples)
    assert drift is not None
    assert drift > 0


def test_cardiac_drift_none_with_insufficient_data():
    samples = [_sample(0, hr=140, pace=300)]
    assert cardiac_drift(samples) is None


def test_cardiac_drift_none_without_hr():
    samples = [_sample(i * 10, pace=300) for i in range(10)]
    assert cardiac_drift(samples) is None


def test_run_walk_intervals_segments_by_cadence():
    # cadence here is single-leg strides/min, matching Garmin's raw FIT field
    # (~80-90 easy running, ~50-55 walking) — see DEFAULT_WALK_CADENCE_THRESHOLD.
    samples = (
        [_sample(i * 5, cadence=85) for i in range(4)]  # run
        + [_sample(20 + i * 5, cadence=52) for i in range(4)]  # walk
        + [_sample(40 + i * 5, cadence=85) for i in range(4)]  # run
    )
    intervals = run_walk_intervals(samples)
    kinds = [i.kind for i in intervals]
    assert kinds == ["run", "walk", "run"]
    assert intervals[1].duration_s == 15  # last walk sample minus first walk sample


def test_run_walk_intervals_empty():
    assert run_walk_intervals([]) == []


def test_pace_at_hr_averages_matching_samples():
    samples = [
        _sample(0, hr=150, pace=300),
        _sample(10, hr=151, pace=310),
        _sample(20, hr=170, pace=250),  # out of band, excluded
    ]
    result = pace_at_hr(samples, hr_target=150, tolerance=3)
    assert result == 305


def test_pace_at_hr_no_match_returns_none():
    samples = [_sample(0, hr=100, pace=300)]
    assert pace_at_hr(samples, hr_target=150, tolerance=3) is None
