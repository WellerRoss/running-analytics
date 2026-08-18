from datetime import UTC, datetime, timedelta
from pathlib import Path

from garmin_running_data.models import (
    Activity,
    ActivityLap,
    ActivitySample,
    PrescribedWorkout,
    WorkoutStep,
)
from garmin_running_data.storage import Storage

from running_analytics.overlay_chart import build_overlay_chart, build_overlay_document

START = datetime(2026, 8, 13, 7, 0, tzinfo=UTC)


def _storage(tmp_path: Path) -> Storage:
    return Storage(tmp_path / "activities.db", tmp_path / "samples")


def _activity(activity_id="a1", duration_s=180.0):
    return Activity(
        activity_id=activity_id,
        start_time=START,
        activity_type="running",
        duration_s=duration_s,
        distance_m=500.0,
        raw_fit_path=f"raw/{activity_id}.fit",
    )


def _hr_samples(activity_id="a1", n=180, base_hr=140):
    return [
        ActivitySample(
            activity_id=activity_id,
            timestamp=START + timedelta(seconds=i),
            hr=base_hr + (i % 20),
        )
        for i in range(n)
    ]


def _laps(activity_id="a1"):
    return [
        ActivityLap(
            activity_id=activity_id,
            lap_index=0,
            step_type="interval_warmup",
            start_time=START,
            duration_s=60.0,
            avg_hr=140,
            max_hr=150,
        ),
        ActivityLap(
            activity_id=activity_id,
            lap_index=1,
            step_type="interval_active",
            start_time=START + timedelta(seconds=60),
            duration_s=60.0,
            avg_hr=155,
            max_hr=160,
        ),
        ActivityLap(
            activity_id=activity_id,
            lap_index=2,
            step_type="interval_cooldown",
            start_time=START + timedelta(seconds=120),
            duration_s=60.0,
            avg_hr=145,
            max_hr=150,
        ),
    ]


def _workout_with_hr_zone(workout_id="w1"):
    return PrescribedWorkout(
        workout_id=workout_id,
        template_workout_id=workout_id,
        scheduled_date=START.date(),
        pulled_date=START.date(),
        workout_name="Test Workout",
        sport_type="running",
        source="user_authored",
        steps=[
            WorkoutStep(step_order=1, step_type="warmup", end_condition="time"),
            WorkoutStep(
                step_order=2,
                step_type="interval",
                end_condition="time",
                target_type="heart_rate_zone",
                target_low=150.0,
                target_high=165.0,
            ),
            WorkoutStep(step_order=3, step_type="cooldown", end_condition="time"),
        ],
        raw_json_path="raw/w1.json",
    )


def _workout_with_hr_point(workout_id="w2"):
    return PrescribedWorkout(
        workout_id=workout_id,
        template_workout_id=workout_id,
        scheduled_date=START.date(),
        pulled_date=START.date(),
        workout_name="Point Target Workout",
        sport_type="running",
        source="coach_adaptive",
        steps=[
            WorkoutStep(step_order=1, step_type="warmup", end_condition="time"),
            WorkoutStep(
                step_order=2,
                step_type="interval",
                end_condition="time",
                target_type="heart_rate_point",
                target_low=157.0,
                target_high=157.0,
            ),
            WorkoutStep(step_order=3, step_type="cooldown", end_condition="time"),
        ],
        raw_json_path="raw/w2.json",
    )


def _workout_with_cadence_only(workout_id="w3"):
    return PrescribedWorkout(
        workout_id=workout_id,
        template_workout_id=workout_id,
        scheduled_date=START.date(),
        pulled_date=START.date(),
        workout_name="Cadence Workout",
        sport_type="running",
        source="user_authored",
        steps=[
            WorkoutStep(step_order=1, step_type="warmup", end_condition="time"),
            WorkoutStep(
                step_order=2,
                step_type="interval",
                end_condition="time",
                target_type="cadence",
                target_low=150.0,
                target_high=200.0,
            ),
            WorkoutStep(step_order=3, step_type="cooldown", end_condition="time"),
        ],
        raw_json_path="raw/w3.json",
    )


def test_unknown_activity_shows_empty_state(tmp_path):
    storage = _storage(tmp_path)
    fragment = build_overlay_chart(storage, "does-not-exist")

    assert "No activity found" in fragment
    assert "<style>" in fragment


def test_activity_without_overlay_shows_explanation(tmp_path):
    storage = _storage(tmp_path)
    storage.save_activity(_activity(), _hr_samples())

    fragment = build_overlay_chart(storage, "a1")

    assert "No target-vs-actual overlay available" in fragment


def test_renders_hr_zone_target_as_band(tmp_path):
    storage = _storage(tmp_path)
    storage.save_activity(_activity(), _hr_samples())
    storage.save_activity_laps("a1", _laps())
    storage.save_prescribed_workout(_workout_with_hr_zone())

    fragment = build_overlay_chart(storage, "a1")

    assert 'class="rr-target-band"' in fragment
    assert 'class="rr-legend-swatch rr-target"' in fragment  # the legend entry itself
    assert 'class="rr-hr-line"' in fragment
    assert fragment.count("<svg") == fragment.count("</svg>")


def test_renders_hr_point_target_as_line_not_band(tmp_path):
    storage = _storage(tmp_path)
    storage.save_activity(_activity(), _hr_samples())
    storage.save_activity_laps("a1", _laps())
    storage.save_prescribed_workout(_workout_with_hr_point())

    fragment = build_overlay_chart(storage, "a1")

    assert 'class="rr-target-line"' in fragment
    assert 'class="rr-target-band"' not in fragment


def test_non_hr_target_shows_no_band_and_explanatory_note(tmp_path):
    storage = _storage(tmp_path)
    storage.save_activity(_activity(), _hr_samples())
    storage.save_activity_laps("a1", _laps())
    storage.save_prescribed_workout(_workout_with_cadence_only())

    fragment = build_overlay_chart(storage, "a1")

    assert 'class="rr-target-band"' not in fragment
    assert 'class="rr-target-line"' not in fragment
    assert "rr-legend-swatch rr-target" not in fragment  # no legend entry
    assert "no heart-rate target" in fragment


def test_lap_table_included(tmp_path):
    storage = _storage(tmp_path)
    storage.save_activity(_activity(), _hr_samples())
    storage.save_activity_laps("a1", _laps())
    storage.save_prescribed_workout(_workout_with_hr_zone())

    fragment = build_overlay_chart(storage, "a1")

    assert "Lap-by-lap data (3 laps)" in fragment
    assert "interval_active" in fragment


def test_activity_without_hr_samples_shows_empty_state(tmp_path):
    storage = _storage(tmp_path)
    activity = _activity()
    storage.save_activity(
        activity,
        [ActivitySample(activity_id="a1", timestamp=START, hr=None)],
    )
    storage.save_activity_laps("a1", _laps())
    storage.save_prescribed_workout(_workout_with_hr_zone())

    fragment = build_overlay_chart(storage, "a1")

    assert "no heart-rate samples" in fragment


def test_document_wraps_fragment_with_full_skeleton(tmp_path):
    storage = _storage(tmp_path)
    storage.save_activity(_activity(), _hr_samples())
    storage.save_activity_laps("a1", _laps())
    storage.save_prescribed_workout(_workout_with_hr_zone())

    doc = build_overlay_document(storage, "a1")

    assert doc.startswith("<!doctype html>")
    assert "<title>" in doc
    assert 'class="rr-overlay"' in doc
