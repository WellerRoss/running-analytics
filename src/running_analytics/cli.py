from pathlib import Path

import typer
from garmin_running_data.config import get_settings
from garmin_running_data.storage import Storage

from running_analytics.report import build_report

app = typer.Typer(help="Derived running metrics and reports, built on garmin-running-data.")


@app.command()
def report(
    days: int = typer.Option(14, help="How many days back to summarize."),
    hr_ceiling: int | None = typer.Option(
        None, help="If set, report time-to-reach this HR (bpm) for each run."
    ),
    out: Path | None = typer.Option(  # noqa: B008
        None, help="Write Markdown to this file instead of stdout."
    ),
) -> None:
    """Generate a Markdown report of derived running metrics."""
    settings = get_settings()
    storage = Storage(settings.activities_db_path, settings.samples_dir)
    text = build_report(storage, days=days, hr_ceiling=hr_ceiling)

    if out is not None:
        out.write_text(text)
        typer.echo(f"Wrote report to {out}")
    else:
        typer.echo(text)


if __name__ == "__main__":
    app()
