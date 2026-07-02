from pathlib import Path

from trace_viewer.export.html import render_html
from trace_viewer.export.markdown import render_markdown
from trace_viewer.parsers.codex import parse_codex_trace

FIXTURES = Path(__file__).parent / "fixtures"


def test_render_markdown_exports_readable_report_with_details() -> None:
    session = parse_codex_trace(FIXTURES / "codex_session.jsonl")

    markdown = render_markdown(session, max_output_lines=1)

    assert markdown.startswith("# Trace: codex_session")
    assert "## Transcript" in markdown
    assert "### User" in markdown
    assert "Inspect the repository." in markdown
    assert "### Tool: shell" in markdown
    assert "<details>" in markdown
    assert "Output truncated" in markdown


def test_render_markdown_includes_warnings() -> None:
    session = parse_codex_trace(FIXTURES / "codex_bad.jsonl")

    markdown = render_markdown(session)

    assert "## Warnings" in markdown
    assert "Invalid JSON" in markdown


def test_render_html_escapes_content_and_uses_details() -> None:
    session = parse_codex_trace(FIXTURES / "codex_session.jsonl")
    session.events[0].content = "<unsafe>"

    html = render_html(session, max_output_lines=1)

    assert "<!doctype html>" in html
    assert "<h1>Trace: codex_session</h1>" in html
    assert "&lt;unsafe&gt;" in html
    assert "<details>" in html
    assert "Output truncated" in html
