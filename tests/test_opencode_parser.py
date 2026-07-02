from pathlib import Path

import pytest

from trace_viewer.models import EventKind
from trace_viewer.parsers import ParseError, detect_format, parse_trace
from trace_viewer.parsers.opencode import parse_opencode_trace

FIXTURES = Path(__file__).parent / "fixtures"


def test_detect_format_recognizes_opencode_and_codex() -> None:
    assert detect_format(FIXTURES / "opencode_session.jsonl") == "opencode"
    assert detect_format(FIXTURES / "codex_session.jsonl") == "codex"


def test_parse_opencode_groups_calls_and_maps_messages_and_tools() -> None:
    session = parse_opencode_trace(FIXTURES / "opencode_session.jsonl")

    assert session.session_id == "opencode_session"
    assert session.warning_count == 0
    # Calls are grouped by _id (request then response), so the meta title call
    # (id 1) comes first even though id 2's request was written before id 1's
    # response on the wire.
    assert [(event.kind, event.title) for event in session.events] == [
        (EventKind.MESSAGE, "System"),  # id1 request
        (EventKind.MESSAGE, "User"),
        (EventKind.MESSAGE, "Assistant"),  # id1 response (title)
        (EventKind.MESSAGE, "System"),  # id2 request
        (EventKind.MESSAGE, "User"),
        (EventKind.MESSAGE, "Assistant"),  # id2 response
        (EventKind.TOOL_CALL, "Tool: shell"),
        (EventKind.TOOL_RESULT, "Result: shell"),  # id3 request delta (tool result)
        (EventKind.MESSAGE, "Assistant"),  # id3 response
    ]


def test_parse_opencode_extracts_content_reasoning_and_arguments() -> None:
    session = parse_opencode_trace(FIXTURES / "opencode_session.jsonl")

    def by_kind(kind: EventKind) -> list:
        return [e for e in session.events if e.kind == kind]

    # User content arrives as a list of {type,text} parts and is flattened.
    user = [e for e in session.events if e.title == "User"][1]
    assert user.content == "Inspect the repository."

    # Assistant reasoning is preserved alongside the visible content.
    task_reply = by_kind(EventKind.MESSAGE)[5]
    assert "I should list the files first." in task_reply.content
    assert "Let me list the files." in task_reply.content

    tool_call = by_kind(EventKind.TOOL_CALL)[0]
    assert tool_call.tool_name == "shell"
    assert tool_call.arguments == {"cmd": "rg --files"}
    assert tool_call.content == "rg --files"

    # The tool result is matched back to its call's tool name via tool_call_id.
    tool_result = by_kind(EventKind.TOOL_RESULT)[0]
    assert tool_result.tool_name == "shell"
    assert "README.md" in tool_result.content


def test_parse_opencode_skips_echoed_assistant_in_delta_and_strips_markers() -> None:
    session = parse_opencode_trace(FIXTURES / "opencode_session.jsonl")

    # The append-delta echoes the prior assistant turn; it must not be duplicated.
    assistants = [e for e in session.events if e.title == "Assistant"]
    assert len(assistants) == 3

    # The final response uses *-prefixed keys (*choices/*usage); markers are
    # stripped so the assistant message is still parsed.
    assert session.events[-1].title == "Assistant"
    assert "Done." in session.events[-1].content


def test_detect_format_recognizes_anthropic_variant() -> None:
    assert detect_format(FIXTURES / "opencode_anthropic_session.jsonl") == "opencode"


def test_parse_opencode_anthropic_renders_full_conversation() -> None:
    session = parse_opencode_trace(FIXTURES / "opencode_anthropic_session.jsonl")

    assert session.warning_count == 0
    assert [(event.kind, event.title) for event in session.events] == [
        (EventKind.MESSAGE, "System"),  # id1 request ([meta] title call)
        (EventKind.MESSAGE, "User"),
        (EventKind.MESSAGE, "Assistant"),  # id1 response (title)
        (EventKind.MESSAGE, "System"),  # id2 request (main thread)
        (EventKind.MESSAGE, "User"),
        (EventKind.MESSAGE, "Assistant"),  # id2 response
        (EventKind.TOOL_CALL, "Tool: read"),
        (EventKind.TOOL_RESULT, "Result: read"),  # id3 request (full re-send)
        (EventKind.MESSAGE, "Assistant"),  # id3 response
        (EventKind.TOOL_CALL, "Tool: bash"),
        (EventKind.TOOL_RESULT, "Result: bash"),  # id4 request (append delta)
        (EventKind.MESSAGE, "Assistant"),  # id4 response
    ]


def test_parse_opencode_anthropic_extracts_blocks() -> None:
    session = parse_opencode_trace(FIXTURES / "opencode_anthropic_session.jsonl")

    def by_kind(kind: EventKind) -> list:
        return [e for e in session.events if e.kind == kind]

    # The top-level `system` key renders as a System message.
    systems = [e for e in session.events if e.title == "System"]
    assert systems[1].content == "You are a coding agent."

    # Thinking blocks are surfaced like reasoning_content.
    reply = [e for e in session.events if e.title == "Assistant"][1]
    assert "Reasoning:" in reply.content
    assert "I should read the README first." in reply.content
    assert "Let me read the README." in reply.content

    # tool_use blocks become tool calls with parsed input.
    read_call = by_kind(EventKind.TOOL_CALL)[0]
    assert read_call.tool_name == "read"
    assert read_call.arguments == {"filePath": "README.md"}
    bash_call = by_kind(EventKind.TOOL_CALL)[1]
    assert bash_call.content == "ls tests"

    # tool_result blocks resolve their tool name via tool_use_id; content may
    # be a plain string or a list of text blocks.
    read_result, bash_result = by_kind(EventKind.TOOL_RESULT)
    assert read_result.tool_name == "read"
    assert "# My Project" in read_result.content
    assert bash_result.tool_name == "bash"
    assert bash_result.content == "test_app.py"


def test_parse_opencode_anthropic_deduplicates_resent_history() -> None:
    session = parse_opencode_trace(FIXTURES / "opencode_anthropic_session.jsonl")

    # The id3 request re-sends the full history (only cache_control moved) and
    # the id4 delta re-sends the previous tail; neither may render twice.
    task_messages = [
        e
        for e in session.events
        if e.kind == EventKind.MESSAGE and "Inspect the repository." in e.content
    ]
    assert len(task_messages) == 2  # echoed inside the [meta] prompt + the task itself
    assert [e.title for e in task_messages] == ["User", "User"]

    read_results = [
        e for e in session.events if e.kind == EventKind.TOOL_RESULT and e.tool_name == "read"
    ]
    assert len(read_results) == 1

    # Assistant echoes inside requests must not duplicate the response events.
    assistants = [e for e in session.events if e.title == "Assistant"]
    assert len(assistants) == 4

    # The elided system prompt (["..."]) must not render as a new message.
    systems = [e for e in session.events if e.title == "System"]
    assert len(systems) == 2


def test_parse_opencode_renders_error_records_and_recovers_lost_turns() -> None:
    session = parse_opencode_trace(FIXTURES / "opencode_error_session.jsonl")

    # An error record is trace content (a failed round-trip), not a parse
    # problem: it renders as an event but does not count as a parser warning
    # and must not raise in strict mode.
    assert session.warning_count == 0
    assert [(event.kind, event.title) for event in session.events] == [
        (EventKind.MESSAGE, "System"),
        (EventKind.MESSAGE, "User"),
        (EventKind.MESSAGE, "Assistant"),  # id1 response
        (EventKind.TOOL_CALL, "Tool: read"),
        (EventKind.TOOL_RESULT, "Result: read"),  # id2 request
        (EventKind.WARNING, "Error"),  # id2 failed round-trip
        (EventKind.MESSAGE, "Assistant"),  # id3 request: turn lost to the error
        (EventKind.TOOL_CALL, "Tool: edit"),
        (EventKind.TOOL_RESULT, "Result: edit"),
        (EventKind.MESSAGE, "Assistant"),  # id3 response
    ]

    error = [e for e in session.events if e.kind == EventKind.WARNING][0]
    assert "socket connection was closed" in error.content

    # The id2 response died mid-stream, so its assistant turn only exists as
    # an echo in the id3 request; the echo is rendered (not skipped) because
    # its tool_use id never appeared in a response, and the tool result then
    # resolves its name from that echo.
    lost_turn = [e for e in session.events if e.title == "Assistant"][1]
    assert "I will patch main." in lost_turn.content
    edit_result = [e for e in session.events if e.kind == EventKind.TOOL_RESULT][1]
    assert edit_result.tool_name == "edit"

    parse_opencode_trace(FIXTURES / "opencode_error_session.jsonl", strict=True)


def test_parse_trace_dispatches_to_opencode() -> None:
    session = parse_trace(FIXTURES / "opencode_session.jsonl")
    assert any(e.kind == EventKind.TOOL_CALL for e in session.events)
    assert session.started_at == "2026-06-28T13:58:04.690Z"
    assert session.ended_at == "2026-06-28T13:58:41.566Z"


def test_lenient_opencode_parser_records_warnings() -> None:
    session = parse_opencode_trace(FIXTURES / "opencode_bad.jsonl")

    assert session.warning_count == 2
    kinds = [e.kind for e in session.events]
    assert EventKind.WARNING in kinds
    contents = " ".join(e.content for e in session.warnings)
    assert "Invalid JSON" in contents
    assert "Unsupported record kind" in contents


def test_strict_opencode_parser_raises_on_bad_record() -> None:
    with pytest.raises(ParseError, match="opencode_bad.jsonl:2"):
        parse_opencode_trace(FIXTURES / "opencode_bad.jsonl", strict=True)
