from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trace_viewer.models import EventKind, TraceEvent, TraceSession


class ParseError(ValueError):
    pass


_SKIP = object()


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

        _apply_session_metadata(session, record)
        event = _record_to_event(record, source_path, line_number, strict)
        if event is _SKIP:
            continue
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
        if _is_duplicate_message(session, event):
            continue
        session.events.append(event)

    if session.events:
        session.started_at = session.events[0].timestamp
        session.ended_at = session.events[-1].timestamp
    return session


def _record_to_event(
    record: dict[str, Any], source_path: Path, line_number: int, strict: bool
) -> TraceEvent | object | None:
    event_type = record.get("type")
    event_id = f"{line_number}"
    timestamp = _optional_str(record.get("timestamp"))
    payload = record.get("payload")

    if event_type == "session_meta":
        return _SKIP

    if event_type in {"turn_context"}:
        return _SKIP

    if event_type == "event_msg" and isinstance(payload, dict):
        return _payload_event_to_event(payload, record, event_id, timestamp, line_number)

    if event_type == "response_item" and isinstance(payload, dict):
        return _payload_event_to_event(payload, record, event_id, timestamp, line_number)

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


def _apply_session_metadata(session: TraceSession, record: dict[str, Any]) -> None:
    if record.get("type") != "session_meta":
        return
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return
    session_id = payload.get("id")
    if session_id:
        session.session_id = str(session_id)
    timestamp = payload.get("timestamp")
    if timestamp and session.started_at is None:
        session.started_at = str(timestamp)


def _is_duplicate_message(session: TraceSession, event: TraceEvent) -> bool:
    if event.kind != EventKind.MESSAGE:
        return False
    return any(
        previous.kind == EventKind.MESSAGE
        and previous.role == event.role
        and previous.content == event.content
        for previous in session.events[-3:]
    )


def _payload_event_to_event(
    payload: dict[str, Any],
    raw: dict[str, Any],
    event_id: str,
    timestamp: str | None,
    line_number: int,
) -> TraceEvent | object | None:
    payload_type = payload.get("type")

    if payload_type == "user_message":
        return TraceEvent(
            id=event_id,
            kind=EventKind.MESSAGE,
            title="User",
            content=_stringify_content(payload.get("message")),
            timestamp=timestamp,
            raw=raw,
            role="user",
            line_number=line_number,
        )

    if payload_type == "agent_message":
        return TraceEvent(
            id=event_id,
            kind=EventKind.MESSAGE,
            title="Assistant",
            content=_stringify_content(payload.get("message")),
            timestamp=timestamp,
            raw=raw,
            role="assistant",
            line_number=line_number,
        )

    if payload_type == "message":
        role = _optional_str(payload.get("role")) or "unknown"
        return TraceEvent(
            id=event_id,
            kind=EventKind.MESSAGE,
            title=role.title(),
            content=_content_parts_to_text(payload.get("content")),
            timestamp=timestamp,
            raw=raw,
            role=role,
            line_number=line_number,
        )

    if payload_type in {"function_call", "custom_tool_call"}:
        tool_name = _optional_str(payload.get("name")) or "unknown"
        arguments = _parse_arguments(payload.get("arguments", payload.get("input", {})))
        return TraceEvent(
            id=event_id,
            kind=EventKind.TOOL_CALL,
            title=f"Tool: {tool_name}",
            content=_summarize_arguments(arguments),
            timestamp=timestamp,
            raw=raw,
            tool_name=tool_name,
            arguments=arguments,
            status=_optional_str(payload.get("status")),
            line_number=line_number,
        )

    if payload_type in {"function_call_output", "custom_tool_call_output"}:
        call_id = _optional_str(payload.get("call_id")) or "unknown"
        return TraceEvent(
            id=event_id,
            kind=EventKind.TOOL_RESULT,
            title=f"Result: {call_id}",
            content=_stringify_content(payload.get("output")),
            timestamp=timestamp,
            raw=raw,
            tool_name=call_id,
            status=_optional_str(payload.get("status")),
            line_number=line_number,
        )

    if payload_type in {
        "task_started",
        "task_complete",
        "token_count",
        "thread_goal_updated",
        "patch_apply_end",
        "reasoning",
    }:
        return _SKIP

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


def _content_parts_to_text(value: Any) -> str:
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("text")
                if text is None:
                    text = item.get("content")
                if text is not None:
                    parts.append(str(text))
            elif item is not None:
                parts.append(str(item))
        return "\n\n".join(parts)
    return _stringify_content(value)


def _parse_arguments(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _summarize_arguments(arguments: Any) -> str:
    if isinstance(arguments, dict):
        if "cmd" in arguments:
            return str(arguments["cmd"])
        return json.dumps(arguments, ensure_ascii=False, sort_keys=True)
    return _stringify_content(arguments)
