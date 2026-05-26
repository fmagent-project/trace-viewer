from pathlib import Path

import pytest

from trace_viewer.models import EventKind
from trace_viewer.parsers.codex import ParseError, parse_codex_trace

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_codex_session_maps_messages_and_tools() -> None:
    session = parse_codex_trace(FIXTURES / "codex_session.jsonl")

    assert session.session_id == "codex_session"
    assert session.source_path.name == "codex_session.jsonl"
    assert [event.kind for event in session.events] == [
        EventKind.MESSAGE,
        EventKind.MESSAGE,
        EventKind.TOOL_CALL,
        EventKind.TOOL_RESULT,
        EventKind.MESSAGE,
    ]
    assert session.events[0].title == "User"
    assert session.events[0].content == "Inspect the repository."
    assert session.events[2].title == "Tool: shell"
    assert session.events[2].tool_name == "shell"
    assert "rg --files" in session.events[2].content
    assert session.events[3].exit_code == 0
    assert session.warning_count == 0


def test_lenient_parser_turns_bad_records_into_warning_events() -> None:
    session = parse_codex_trace(FIXTURES / "codex_bad.jsonl")

    assert session.warning_count == 2
    assert [event.kind for event in session.events] == [
        EventKind.MESSAGE,
        EventKind.WARNING,
        EventKind.WARNING,
    ]
    assert "line 2" in session.events[1].content
    assert "Invalid JSON" in session.events[1].content
    assert "Unsupported event type" in session.events[2].content


def test_strict_parser_fails_on_bad_json_with_line_number() -> None:
    with pytest.raises(ParseError, match="codex_bad.jsonl:2: Invalid JSON"):
        parse_codex_trace(FIXTURES / "codex_bad.jsonl", strict=True)


def test_parse_real_codex_trace_format_maps_payload_events_without_telemetry_warnings() -> None:
    session = parse_codex_trace(FIXTURES / "codex_real_format.jsonl")

    assert session.warning_count == 0
    assert [event.kind for event in session.events] == [
        EventKind.MESSAGE,
        EventKind.MESSAGE,
        EventKind.TOOL_CALL,
        EventKind.TOOL_RESULT,
        EventKind.MESSAGE,
    ]
    assert session.session_id == "real-session"
    assert session.events[0].title == "User"
    assert session.events[0].content == "Build a trace viewer"
    assert session.events[1].title == "Assistant"
    assert session.events[2].title == "Tool: exec_command"
    assert session.events[2].arguments == {"cmd": "rg --files", "workdir": "/tmp/project"}
    assert session.events[2].content == "rg --files"
    assert session.events[3].title == "Result: call-1"
    assert "README.md" in session.events[3].content
    assert session.events[4].content == "Done."
