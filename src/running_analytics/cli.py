from enum import StrEnum
from pathlib import Path

import typer
from garmin_running_data.config import get_settings
from garmin_running_data.storage import Storage

from running_analytics.html_report import build_html_document
from running_analytics.report import build_report

app = typer.Typer(help="Derived running metrics and reports, built on garmin-running-data.")


class ReportFormat(StrEnum):
    markdown = "markdown"
    html = "html"


@app.command()
def report(
    days: int = typer.Option(14, help="How many days back to summarize."),
    hr_ceiling: int | None = typer.Option(
        None, help="If set, report time-to-reach this HR (bpm) for each run."
    ),
    format: ReportFormat = typer.Option(  # noqa: B008
        ReportFormat.markdown, help="Output format."
    ),
    out: Path | None = typer.Option(  # noqa: B008
        None, help="Write the report to this file instead of stdout."
    ),
) -> None:
    """Generate a report (Markdown or standalone HTML) of derived running metrics."""
    settings = get_settings()
    storage = Storage(settings.activities_db_path, settings.samples_dir)

    if format is ReportFormat.html:
        text = build_html_document(storage, days=days, hr_ceiling=hr_ceiling)
    else:
        text = build_report(storage, days=days, hr_ceiling=hr_ceiling)

    if out is not None:
        out.write_text(text)
        typer.echo(f"Wrote {format.value} report to {out}")
    else:
        typer.echo(text)


if __name__ == "__main__":
    app()
