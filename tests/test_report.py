from datetime import UTC, datetime, timedelta
from pathlib import Path

from garmin_running_data.models import Activity, ActivitySample
from garmin_running_data.storage import Storage

from running_analytics.report import build_report


def _storage(tmp_path: Path) -> Storage:
    return Storage(tmp_path / "activities.db", tmp_path / "samples")


def _activity_with_samples(activity_id="a1", days_ago=1):
    start = datetime.now(UTC) - timedelta(days=days_ago)
    activity = Activity(
        activity_id=activity_id,
        start_time=start,
        activity_type="running",
        duration_s=1800.0,
        distance_m=5000.0,
        avg_hr=150,
        raw_fit_path=f"raw/{activity_id}.fit",
    )
    samples = [
        ActivitySample(
            activity_id=activity_id,
            timestamp=start + timedelta(seconds=i * 10),
            hr=140 + i,
            pace_s_per_km=300,
            cadence=170 if i % 3 else 100,
        )
        for i in range(10)
    ]
    return activity, samples


def test_report_empty(tmp_path):
    storage = _storage(tmp_path)
    text = build_report(storage, days=14)
    assert "No activities" in text


def test_report_includes_run_and_period_summary(tmp_path):
    storage = _storage(tmp_path)
    activity, samples = _activity_with_samples()
    storage.save_activity(activity, samples)

    text = build_report(storage, days=14)
    assert "5.00 km" in text
    assert "Period summary" in text
    assert "1 runs, 5.0 km total" in text


def test_report_excludes_old_runs(tmp_path):
    storage = _storage(tmp_path)
    activity, samples = _activity_with_samples(days_ago=30)
    storage.save_activity(activity, samples)

    text = build_report(storage, days=14)
    assert "No activities in the last 14 days" in text


def test_report_with_hr_ceiling(tmp_path):
    storage = _storage(tmp_path)
    activity, samples = _activity_with_samples()
    storage.save_activity(activity, samples)

    text = build_report(storage, days=14, hr_ceiling=145)
    assert "Time to reach 145 bpm" in text
