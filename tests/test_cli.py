from pathlib import Path

from trace_viewer.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_cli_export_writes_markdown(tmp_path: Path) -> None:
    output = tmp_path / "report.md"

    code = main(
        ["export", str(FIXTURES / "codex_session.jsonl"), "--format", "md", "--output", str(output)]
    )

    assert code == 0
    assert output.read_text(encoding="utf-8").startswith("# Trace: codex_session")


def test_cli_export_writes_html(tmp_path: Path) -> None:
    output = tmp_path / "report.html"

    code = main(
        [
            "export",
            str(FIXTURES / "codex_session.jsonl"),
            "--format",
            "html",
            "--output",
            str(output),
        ]
    )

    assert code == 0
    assert output.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_cli_missing_path_returns_error(capsys) -> None:
    code = main(["missing.jsonl"])

    assert code == 2
    assert "does not exist" in capsys.readouterr().err
