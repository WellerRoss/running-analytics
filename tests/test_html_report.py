from datetime import UTC, datetime, timedelta
from pathlib import Path

from garmin_running_data.models import Activity, ActivitySample
from garmin_running_data.storage import Storage

from running_analytics.html_report import build_html_document, build_html_report


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
            cadence=85 if i % 3 else 50,
        )
        for i in range(10)
    ]
    return activity, samples


def test_html_report_empty_state(tmp_path):
    storage = _storage(tmp_path)
    fragment = build_html_report(storage, days=14)
    assert "No activities in the last 14 days" in fragment
    assert "<style>" in fragment


def test_html_report_renders_run_and_stats(tmp_path):
    storage = _storage(tmp_path)
    activity, samples = _activity_with_samples()
    storage.save_activity(activity, samples)

    fragment = build_html_report(storage, days=14)
    assert "5.00 km" in fragment
    assert "rr-stat-value" in fragment
    assert "rr-split-run" in fragment
    assert "rr-split-walk" in fragment


def test_html_report_escapes_and_has_no_unclosed_style(tmp_path):
    storage = _storage(tmp_path)
    activity, samples = _activity_with_samples()
    storage.save_activity(activity, samples)

    fragment = build_html_report(storage, days=14)
    assert fragment.count("<style>") == fragment.count("</style>")
    assert fragment.count('<div class="rr-report">') == 1


def test_html_document_wraps_fragment_with_full_skeleton(tmp_path):
    storage = _storage(tmp_path)
    activity, samples = _activity_with_samples()
    storage.save_activity(activity, samples)

    doc = build_html_document(storage, days=14)
    assert doc.startswith("<!doctype html>")
    assert "<title>" in doc
    assert 'class="rr-report"' in doc
