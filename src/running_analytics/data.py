from datetime import UTC, datetime, timedelta

from garmin_running_data.models import Activity, ActivitySample
from garmin_running_data.storage import Storage


def as_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def load_samples(storage: Storage, activity_id: str) -> list[ActivitySample]:
    df = storage.read_samples(activity_id)
    if df.is_empty():
        return []
    return [ActivitySample(**row) for row in df.iter_rows(named=True)]


def recent_activities(storage: Storage, days: int) -> list[tuple[Activity, list[ActivitySample]]]:
    df = storage.read_activities()
    if df.is_empty():
        return []

    cutoff = datetime.now(UTC) - timedelta(days=days)
    results = []
    for row in df.iter_rows(named=True):
        if row["start_time"] is None:
            continue
        activity = Activity(**row)
        if as_aware(activity.start_time) < cutoff:
            continue
        samples = load_samples(storage, activity.activity_id)
        results.append((activity, samples))

    results.sort(key=lambda pair: pair[0].start_time, reverse=True)
    return results


def format_pace(seconds_per_km: float) -> str:
    minutes, seconds = divmod(int(seconds_per_km), 60)
    return f"{minutes}:{seconds:02d}"
