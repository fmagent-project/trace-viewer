from __future__ import annotations

import json

from trace_viewer.export.common import event_heading, split_visible_and_full
from trace_viewer.models import EventKind, TraceSession


def render_markdown(session: TraceSession, *, max_output_lines: int = 80) -> str:
    parts: list[str] = [
        f"# Trace: {session.session_id}",
        "",
        "## Metadata",
        "",
        f"- Source: `{session.source_path}`",
        f"- Events: {len(session.events)}",
        f"- Warnings: {session.warning_count}",
        "",
    ]

    if session.warnings:
        parts.extend(["## Warnings", ""])
        for warning in session.warnings:
            parts.extend([f"- {warning.content}", ""])

    parts.extend(["## Transcript", ""])
    for event in session.events:
        parts.extend([f"### {event_heading(event)}", ""])
        if event.kind == EventKind.TOOL_CALL and event.arguments is not None:
            parts.extend([event.content, "", "<details>", "<summary>Arguments</summary>", ""])
            parts.extend(
                ["```json", json.dumps(event.arguments, ensure_ascii=False, indent=2), "```"]
            )
            parts.extend(["", "</details>", ""])
            continue

        visible, full = split_visible_and_full(event.content, max_output_lines)
        parts.extend([visible, ""])
        if full is not None:
            parts.extend(
                [
                    f"_Output truncated to {max_output_lines} line(s)._",
                    "",
                    "<details>",
                    "<summary>Full output</summary>",
                    "",
                    "```text",
                    full,
                    "```",
                    "",
                    "</details>",
                    "",
                ]
            )

    return "\n".join(parts).rstrip() + "\n"
