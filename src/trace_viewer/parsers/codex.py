from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trace_viewer.models import EventKind, TraceEvent, TraceSession


class ParseError(ValueError):
    pass


def parse_codex_trace(path: str | Path, *, strict: bool = False) -> TraceSession:
    source_path = Path(path)
    session = TraceSession(session_id=source_path.stem, source_path=source_path)

    lines = source_path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            _handle_warning(
                session,
                strict,
                source_path,
                line_number,
                f"Invalid JSON: {exc.msg}",
                raw=line,
            )
            continue

        event = _record_to_event(record, source_path, line_number, strict)
        if event is None:
            _handle_warning(
                session,
                strict,
                source_path,
                line_number,
                f"Unsupported event type: {record.get('type')!r}",
                raw=record,
            )
            continue
        session.events.append(event)

    if session.events:
        session.started_at = session.events[0].timestamp
        session.ended_at = session.events[-1].timestamp
    return session


def _record_to_event(
    record: dict[str, Any], source_path: Path, line_number: int, strict: bool
) -> TraceEvent | None:
    event_type = record.get("type")
    event_id = f"{line_number}"
    timestamp = _optional_str(record.get("timestamp"))

    if event_type == "message":
        role = _optional_str(record.get("role")) or "unknown"
        content = _stringify_content(record.get("content"))
        if strict and not content:
            raise ParseError(f"{source_path}:{line_number}: Message event is missing content")
        return TraceEvent(
            id=event_id,
            kind=EventKind.MESSAGE,
            title=role.title(),
            content=content,
            timestamp=timestamp,
            raw=record,
            role=role,
            line_number=line_number,
        )

    if event_type == "tool_call":
        tool_name = (
            _optional_str(record.get("tool")) or _optional_str(record.get("name")) or "unknown"
        )
        arguments = record.get("arguments") or record.get("args") or {}
        return TraceEvent(
            id=event_id,
            kind=EventKind.TOOL_CALL,
            title=f"Tool: {tool_name}",
            content=_summarize_arguments(arguments),
            timestamp=timestamp,
            raw=record,
            tool_name=tool_name,
            arguments=arguments,
            status=_optional_str(record.get("status")),
            line_number=line_number,
        )

    if event_type == "tool_result":
        tool_name = (
            _optional_str(record.get("tool")) or _optional_str(record.get("name")) or "unknown"
        )
        output = _stringify_content(record.get("output", record.get("content", "")))
        return TraceEvent(
            id=event_id,
            kind=EventKind.TOOL_RESULT,
            title=f"Result: {tool_name}",
            content=output,
            timestamp=timestamp,
            raw=record,
            tool_name=tool_name,
            status=_optional_str(record.get("status")),
            exit_code=_optional_int(record.get("exit_code")),
            line_number=line_number,
        )

    return None


def _handle_warning(
    session: TraceSession,
    strict: bool,
    source_path: Path,
    line_number: int,
    message: str,
    *,
    raw: dict[str, Any] | str,
) -> None:
    content = f"{source_path.name}: line {line_number}: {message}"
    if strict:
        raise ParseError(f"{source_path}:{line_number}: {message}")
    event = TraceEvent(
        id=f"{line_number}",
        kind=EventKind.WARNING,
        title="Warning",
        content=content,
        raw=raw,
        line_number=line_number,
    )
    session.events.append(event)
    session.warnings.append(event)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _stringify_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def _summarize_arguments(arguments: Any) -> str:
    if isinstance(arguments, dict):
        if "cmd" in arguments:
            return str(arguments["cmd"])
        return json.dumps(arguments, ensure_ascii=False, sort_keys=True)
    return _stringify_content(arguments)
