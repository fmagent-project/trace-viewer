from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from trace_viewer.models import EventKind, TraceEvent, TraceSession
from trace_viewer.parsers.codex import ParseError

# OpenCode writes one JSON record per LLM round-trip to its TRACE_DIR. Each record
# is a provider request or response, tagged with a handful of underscore metadata
# keys (_kind, _id, _ts, _purpose, _url). Two wire formats appear depending on the
# provider endpoint:
#
#   * OpenAI chat-completions: requests carry role/content messages (system in
#     messages[0], tool results as role "tool"); responses carry `choices` with
#     an assistant message, optional `reasoning_content` and `tool_calls`.
#   * Anthropic messages: requests carry a top-level `system` plus messages whose
#     content is a list of typed blocks (text / tool_use / tool_result); responses
#     carry the assistant `content` block list at the top level (no `choices`).
#
# To keep the file small the writer diffs each record against the previous one of
# the same kind:
#
#   * a leading "*" on a key marks a changed subtree; the value that follows is
#     complete, so the marker is simply stripped on read.
#   * an unchanged container value is elided to ["..."] (nested unchanged strings
#     may appear as "..."); we substitute the previous request's value.
#   * "messages-"/"messages+" replace the messages list with an append delta:
#     drop len(messages-) items from the tail of the previous list, then append
#     the "messages+" items.
#
# A third record kind, "error", records a round-trip that failed in transport
# (_error/_stack instead of a payload). The model may already have streamed tool
# calls before the failure; OpenCode keeps that turn in the conversation, so it
# only survives as an assistant echo in a later request.
#
# Requests re-send conversation history (sometimes in full, with only volatile
# keys such as cache_control moved), so rendering dedups against what has already
# been shown: per purpose ("" for the main thread, "[meta]" for title calls) we
# keep the previously rendered message list and only emit the new tail. Assistant
# messages inside requests are echoes of earlier responses and are skipped once a
# response for that purpose has been rendered.


@dataclass
class _SessionState:
    call_tool_names: dict[str, str] = field(default_factory=dict)
    prev_request: dict[str, Any] = field(default_factory=dict)
    prev_messages: list[Any] = field(default_factory=list)
    rendered: dict[str, list[str]] = field(default_factory=dict)
    responses_seen: set[str] = field(default_factory=set)


def parse_opencode_trace(path: str | Path, *, strict: bool = False) -> TraceSession:
    source_path = Path(path)
    session = TraceSession(session_id=source_path.stem, source_path=source_path)

    records: list[tuple[int, dict[str, Any]]] = []
    lines = source_path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            _handle_warning(
                session, strict, source_path, line_number, f"Invalid JSON: {exc.msg}", raw=line
            )
            continue
        if not isinstance(record, dict):
            _handle_warning(
                session, strict, source_path, line_number, "Record is not a JSON object", raw=line
            )
            continue
        records.append((line_number, record))

    # Group each call's request and response together: _id is a per-call counter,
    # but the wire order interleaves concurrent calls. A stable sort by _id keeps
    # the request ahead of its response (requests are written first).
    records.sort(key=lambda item: _id_sort_key(item[1].get("_id"), item[0]))

    state = _SessionState()
    timestamps: list[str] = []
    for line_number, record in records:
        timestamp = _optional_str(record.get("_ts"))
        if timestamp:
            timestamps.append(timestamp)
        kind = record.get("_kind")
        if kind == "request":
            session.events.extend(_request_events(record, line_number, timestamp, state))
        elif kind == "response":
            session.events.extend(_response_events(record, line_number, timestamp, state))
        elif kind == "error":
            session.events.append(_error_event(record, line_number, timestamp))
        else:
            _handle_warning(
                session,
                strict,
                source_path,
                line_number,
                f"Unsupported record kind: {kind!r}",
                raw=record,
            )

    if timestamps:
        session.started_at = min(timestamps)
        session.ended_at = max(timestamps)
    return session


def _request_events(
    record: dict[str, Any],
    line_number: int,
    timestamp: str | None,
    state: _SessionState,
) -> list[TraceEvent]:
    purpose = _optional_str(record.get("_purpose")) or ""

    expanded: dict[str, Any] = {}
    appended: list[Any] | None = None
    removed: list[Any] | None = None
    for key, value in record.items():
        if key.startswith("_"):
            continue
        base = key.lstrip("*")
        value = _unstar(value)
        if base == "messages+":
            appended = value if isinstance(value, list) else []
            continue
        if base == "messages-":
            removed = value if isinstance(value, list) else []
            continue
        if _is_elided(value):
            if base not in state.prev_request:
                continue
            value = state.prev_request[base]
        expanded[base] = value

    if isinstance(expanded.get("messages"), list):
        messages = expanded["messages"]
        is_append = False
    elif appended is not None:
        messages = state.prev_messages[: len(state.prev_messages) - len(removed or [])]
        messages = messages + appended
        is_append = True
    else:
        messages = state.prev_messages
        is_append = False

    expanded["messages"] = messages
    state.prev_request = expanded
    state.prev_messages = messages

    # An Anthropic-style request keeps the system prompt outside the messages
    # list; fold it in as a virtual first message so it renders (and dedups)
    # like any other message.
    render_list = list(messages)
    system = expanded.get("system")
    if system is not None:
        render_list.insert(0, {"role": "system", "content": system})

    history = state.rendered.get(purpose, [])
    canon_list = [_canonical(message) for message in render_list]
    common = 0
    for previous, current in zip(history, canon_list, strict=False):
        if previous != current:
            break
        common += 1
    state.rendered[purpose] = canon_list

    events: list[TraceEvent] = []
    for index in range(common, len(render_list)):
        message = render_list[index]
        if not isinstance(message, dict):
            continue
        role = _optional_str(message.get("role")) or "unknown"
        # Assistant turns inside a request are normally the model's previous
        # replies echoed back and already shown from the response records —
        # except when the response was lost to a transport error: then its tool
        # ids were never registered and the echo is the only surviving copy.
        if role == "assistant":
            tool_ids = _assistant_tool_ids(message)
            if tool_ids:
                if all(tool_id in state.call_tool_names for tool_id in tool_ids):
                    continue
            elif is_append or purpose in state.responses_seen:
                continue
        events.extend(
            _message_events(message, line_number, index, timestamp, state.call_tool_names)
        )
    return events


def _message_events(
    message: dict[str, Any],
    line_number: int,
    index: int,
    timestamp: str | None,
    call_tool_names: dict[str, str],
) -> list[TraceEvent]:
    role = _optional_str(message.get("role")) or "unknown"
    event_id = f"{line_number}.{index}"
    content = message.get("content")

    if role == "tool":  # OpenAI-style tool result message
        call_id = _optional_str(message.get("tool_call_id"))
        tool_name = call_tool_names.get(call_id or "", call_id or "tool")
        return [
            TraceEvent(
                id=event_id,
                kind=EventKind.TOOL_RESULT,
                title=f"Result: {tool_name}",
                content=_message_text(content),
                timestamp=timestamp,
                raw=message,
                tool_name=tool_name,
                line_number=line_number,
            )
        ]

    tool_uses: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    text_content = content
    if isinstance(content, list):
        text_blocks: list[Any] = []
        for block in content:
            block_type = block.get("type") if isinstance(block, dict) else None
            if block_type == "tool_use":
                tool_uses.append(block)
            elif block_type == "tool_result":
                tool_results.append(block)
            else:
                text_blocks.append(block)
        text_content = text_blocks
    openai_calls = message.get("tool_calls") or []

    events: list[TraceEvent] = []
    text = _message_text(text_content)
    if text or not (tool_uses or tool_results or openai_calls):
        events.append(
            TraceEvent(
                id=event_id,
                kind=EventKind.MESSAGE,
                title=role.title(),
                content=text,
                timestamp=timestamp,
                raw=message,
                role=role,
                line_number=line_number,
            )
        )
    for block_index, block in enumerate(tool_uses):
        tool_name = _optional_str(block.get("name")) or "unknown"
        call_id = _optional_str(block.get("id"))
        if call_id:
            call_tool_names[call_id] = tool_name
        arguments = _parse_arguments(block.get("input", {}))
        events.append(
            TraceEvent(
                id=f"{event_id}.call.{block_index}",
                kind=EventKind.TOOL_CALL,
                title=f"Tool: {tool_name}",
                content=_summarize_arguments(arguments),
                timestamp=timestamp,
                raw=block,
                tool_name=tool_name,
                arguments=arguments,
                line_number=line_number,
            )
        )
    for block_index, block in enumerate(tool_results):
        call_id = _optional_str(block.get("tool_use_id"))
        tool_name = call_tool_names.get(call_id or "", call_id or "tool")
        events.append(
            TraceEvent(
                id=f"{event_id}.result.{block_index}",
                kind=EventKind.TOOL_RESULT,
                title=f"Result: {tool_name}",
                content=_message_text(block.get("content")),
                timestamp=timestamp,
                raw=block,
                tool_name=tool_name,
                line_number=line_number,
            )
        )
    events.extend(
        _openai_tool_call_events(openai_calls, event_id, line_number, timestamp, call_tool_names)
    )
    return events


def _response_events(
    record: dict[str, Any],
    line_number: int,
    timestamp: str | None,
    state: _SessionState,
) -> list[TraceEvent]:
    choices = _lookup(record, "choices")
    if isinstance(choices, list) and choices:
        events = _openai_response_events(choices, line_number, timestamp, state.call_tool_names)
    else:
        events = _anthropic_response_events(record, line_number, timestamp, state.call_tool_names)
    if events:
        purpose = _optional_str(record.get("_purpose")) or ""
        state.responses_seen.add(purpose)
    return events


def _openai_response_events(
    choices: list[Any],
    line_number: int,
    timestamp: str | None,
    call_tool_names: dict[str, str],
) -> list[TraceEvent]:
    message = _unstar(choices[0]).get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return []

    events: list[TraceEvent] = []
    text = _assistant_text(message)
    tool_calls = message.get("tool_calls") or []
    if text or not tool_calls:
        events.append(
            TraceEvent(
                id=f"{line_number}.msg",
                kind=EventKind.MESSAGE,
                title="Assistant",
                content=text,
                timestamp=timestamp,
                raw=message,
                role="assistant",
                line_number=line_number,
            )
        )

    events.extend(
        _openai_tool_call_events(
            tool_calls, str(line_number), line_number, timestamp, call_tool_names
        )
    )
    return events


def _openai_tool_call_events(
    tool_calls: list[Any],
    base_id: str,
    line_number: int,
    timestamp: str | None,
    call_tool_names: dict[str, str],
) -> list[TraceEvent]:
    events: list[TraceEvent] = []
    for index, call in enumerate(tool_calls):
        if not isinstance(call, dict):
            continue
        function = call.get("function") or {}
        tool_name = _optional_str(function.get("name")) or "unknown"
        call_id = _optional_str(call.get("id"))
        if call_id:
            call_tool_names[call_id] = tool_name
        arguments = _parse_arguments(function.get("arguments", {}))
        events.append(
            TraceEvent(
                id=f"{base_id}.call.{index}",
                kind=EventKind.TOOL_CALL,
                title=f"Tool: {tool_name}",
                content=_summarize_arguments(arguments),
                timestamp=timestamp,
                raw=call,
                tool_name=tool_name,
                arguments=arguments,
                line_number=line_number,
            )
        )
    return events


def _anthropic_response_events(
    record: dict[str, Any],
    line_number: int,
    timestamp: str | None,
    call_tool_names: dict[str, str],
) -> list[TraceEvent]:
    content = _lookup(record, "content")
    if not isinstance(content, list):
        return []

    text_parts: list[str] = []
    tool_uses: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "thinking":
            thinking = block.get("thinking")
            if thinking:
                text_parts.append(f"Reasoning:\n{_message_text(thinking)}")
        elif block_type == "tool_use":
            tool_uses.append(block)
        else:
            text = block.get("text")
            if text:
                text_parts.append(str(text))

    events: list[TraceEvent] = []
    text = "\n\n".join(text_parts)
    if text or not tool_uses:
        events.append(
            TraceEvent(
                id=f"{line_number}.msg",
                kind=EventKind.MESSAGE,
                title="Assistant",
                content=text,
                timestamp=timestamp,
                raw=record,
                role="assistant",
                line_number=line_number,
            )
        )
    for index, block in enumerate(tool_uses):
        tool_name = _optional_str(block.get("name")) or "unknown"
        call_id = _optional_str(block.get("id"))
        if call_id:
            call_tool_names[call_id] = tool_name
        arguments = _parse_arguments(block.get("input", {}))
        events.append(
            TraceEvent(
                id=f"{line_number}.call.{index}",
                kind=EventKind.TOOL_CALL,
                title=f"Tool: {tool_name}",
                content=_summarize_arguments(arguments),
                timestamp=timestamp,
                raw=block,
                tool_name=tool_name,
                arguments=arguments,
                line_number=line_number,
            )
        )
    return events


def _error_event(record: dict[str, Any], line_number: int, timestamp: str | None) -> TraceEvent:
    return TraceEvent(
        id=f"{line_number}.error",
        kind=EventKind.WARNING,
        title="Error",
        content=_optional_str(record.get("_error")) or "Unknown error",
        timestamp=timestamp,
        raw=record,
        line_number=line_number,
    )


def _assistant_tool_ids(message: dict[str, Any]) -> list[str]:
    """Collect the tool call ids an assistant message carries, in either format."""
    ids: list[str] = []
    content = message.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                call_id = _optional_str(block.get("id"))
                if call_id:
                    ids.append(call_id)
    for call in message.get("tool_calls") or []:
        if isinstance(call, dict):
            call_id = _optional_str(call.get("id"))
            if call_id:
                ids.append(call_id)
    return ids


def _is_elided(value: Any) -> bool:
    return value == ["..."] or value == "..."


def _canonical(message: Any) -> str:
    return json.dumps(_strip_volatile(message), sort_keys=True, ensure_ascii=False)


def _strip_volatile(obj: Any) -> Any:
    """Drop keys the writer moves between otherwise-identical re-sends."""
    if isinstance(obj, dict):
        return {
            key: _strip_volatile(value) for key, value in obj.items() if key != "cache_control"
        }
    if isinstance(obj, list):
        return [_strip_volatile(item) for item in obj]
    return obj


def _lookup(record: dict[str, Any], base_key: str) -> Any:
    """Find a key ignoring the ``*`` change-marker prefix, returning its value."""
    for key, value in record.items():
        if key.lstrip("*") == base_key:
            return _unstar(value)
    return None


def _unstar(obj: Any) -> Any:
    """Strip the ``*`` change-marker prefix from dict keys, recursively."""
    if isinstance(obj, dict):
        return {key.lstrip("*"): _unstar(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_unstar(item) for item in obj]
    return obj


def _assistant_text(message: dict[str, Any]) -> str:
    parts: list[str] = []
    reasoning = message.get("reasoning_content")
    if reasoning:
        parts.append(f"Reasoning:\n{_message_text(reasoning)}")
    content = message.get("content")
    if content:
        parts.append(_message_text(content))
    return "\n\n".join(parts)


def _handle_warning(
    session: TraceSession,
    strict: bool,
    source_path: Path,
    line_number: int,
    message: str,
    *,
    raw: dict[str, Any] | str,
) -> None:
    if strict:
        raise ParseError(f"{source_path}:{line_number}: {message}")
    event = TraceEvent(
        id=f"{line_number}",
        kind=EventKind.WARNING,
        title="Warning",
        content=f"{source_path.name}: line {line_number}: {message}",
        raw=raw,
        line_number=line_number,
    )
    session.events.append(event)
    session.warnings.append(event)


def _id_sort_key(value: Any, fallback_index: int) -> tuple[int, int, int]:
    try:
        return (0, int(value), fallback_index)
    except (TypeError, ValueError):
        return (1, fallback_index, 0)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _message_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
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
    return json.dumps(value, ensure_ascii=False, indent=2)


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
        if "command" in arguments:
            return str(arguments["command"])
        return json.dumps(arguments, ensure_ascii=False, sort_keys=True)
    if arguments is None:
        return ""
    return str(arguments)
