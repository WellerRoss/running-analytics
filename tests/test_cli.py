from typer.testing import CliRunner

from running_analytics.cli import app

runner = CliRunner()


def test_report_runs_as_the_default_command_with_no_subcommand(tmp_path, monkeypatch):
    # `ra --days N ...` (no `report` subcommand) is the documented invocation and
    # the one the nightly automation uses — adding the `overlay` command must not
    # break it back into a "No such option: --days" error.
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["--days", "14", "--format", "markdown"])

    assert result.exit_code == 0
    assert "No activities in the last 14 days" in result.stdout


def test_report_writes_html_to_a_file_with_no_subcommand(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    out = tmp_path / "report.html"

    result = runner.invoke(app, ["--days", "14", "--format", "html", "--out", str(out)])

    assert result.exit_code == 0
    assert out.exists()


def test_overlay_subcommand_still_dispatches(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["overlay", "does-not-exist"])

    assert result.exit_code == 0
    assert "No activity found with id" in result.stdout
    assert "does-not-exist" in result.stdout
