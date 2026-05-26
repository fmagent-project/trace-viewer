from pathlib import Path

import pytest
from textual.containers import VerticalScroll

from trace_viewer.parsers.codex import parse_codex_trace
from trace_viewer.tui.app import TraceViewerApp

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_tui_populates_navigator_from_session() -> None:
    session = parse_codex_trace(FIXTURES / "codex_session.jsonl")
    app = TraceViewerApp(session)

    async with app.run_test() as pilot:
        event_list = pilot.app.query_one("#event-list")
        assert len(event_list.children) == len(session.events)
        reader = pilot.app.query_one("#reader")
        assert "Inspect the repository." in str(reader.renderable)


@pytest.mark.asyncio
async def test_tui_reader_is_inside_scrollable_container() -> None:
    session = parse_codex_trace(FIXTURES / "codex_session.jsonl")
    app = TraceViewerApp(session)

    async with app.run_test() as pilot:
        scroll = pilot.app.query_one("#reader-scroll", VerticalScroll)
        reader = pilot.app.query_one("#reader")
        assert reader.parent is scroll


@pytest.mark.asyncio
async def test_tui_filters_navigator_by_visible_text() -> None:
    session = parse_codex_trace(FIXTURES / "codex_session.jsonl")
    app = TraceViewerApp(session)

    async with app.run_test() as pilot:
        await pilot.app.filter_events("pyproject")
        event_list = pilot.app.query_one("#event-list")
        assert len(event_list.children) == 1
        reader = pilot.app.query_one("#reader")
        assert "pyproject.toml" in str(reader.renderable)


@pytest.mark.asyncio
async def test_tui_export_action_writes_markdown(tmp_path: Path) -> None:
    trace = tmp_path / "session.jsonl"
    fixture_text = (FIXTURES / "codex_session.jsonl").read_text(encoding="utf-8")
    trace.write_text(fixture_text, encoding="utf-8")
    session = parse_codex_trace(trace)
    app = TraceViewerApp(session)

    async with app.run_test() as pilot:
        pilot.app.action_export()

    output = tmp_path / "session.md"
    assert output.exists()
    assert output.read_text(encoding="utf-8").startswith("# Codex Trace: session")
