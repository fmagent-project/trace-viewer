from __future__ import annotations

from trace_viewer.models import EventKind, TraceEvent


def split_visible_and_full(content: str, max_output_lines: int) -> tuple[str, str | None]:
    lines = content.splitlines()
    if len(lines) <= max_output_lines:
        return content, None
    visible = "\n".join(lines[:max_output_lines])
    return visible, content


def event_heading(event: TraceEvent) -> str:
    if event.kind == EventKind.MESSAGE and event.role:
        return event.role.title()
    return event.title


def is_long_tool_result(event: TraceEvent, max_output_lines: int) -> bool:
    return (
        event.kind == EventKind.TOOL_RESULT
        and len(event.content.splitlines()) > max_output_lines
    )
