from __future__ import annotations

import html
import json

from trace_viewer.export.common import event_heading, split_visible_and_full
from trace_viewer.models import EventKind, TraceSession


def render_html(session: TraceSession, *, max_output_lines: int = 80) -> str:
    parts: list[str] = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>Trace: {html.escape(session.session_id)}</title>",
        "<style>"
        "body{font-family:system-ui,sans-serif;line-height:1.45;max-width:980px;"
        "margin:2rem auto;padding:0 1rem}"
        "pre{background:#f6f8fa;padding:1rem;overflow:auto}"
        "section{border-top:1px solid #ddd;padding:1rem 0}"
        "</style>",
        "</head>",
        "<body>",
        f"<h1>Trace: {html.escape(session.session_id)}</h1>",
        "<h2>Metadata</h2>",
        "<ul>",
        f"<li>Source: <code>{html.escape(str(session.source_path))}</code></li>",
        f"<li>Events: {len(session.events)}</li>",
        f"<li>Warnings: {session.warning_count}</li>",
        "</ul>",
    ]

    if session.warnings:
        parts.extend(["<h2>Warnings</h2>", "<ul>"])
        for warning in session.warnings:
            parts.append(f"<li>{html.escape(warning.content)}</li>")
        parts.append("</ul>")

    parts.append("<h2>Transcript</h2>")
    for event in session.events:
        parts.extend(["<section>", f"<h3>{html.escape(event_heading(event))}</h3>"])
        if event.kind == EventKind.TOOL_CALL and event.arguments is not None:
            parts.append(f"<p>{html.escape(event.content)}</p>")
            args = html.escape(json.dumps(event.arguments, ensure_ascii=False, indent=2))
            parts.extend(
                ["<details>", "<summary>Arguments</summary>", f"<pre>{args}</pre>", "</details>"]
            )
        else:
            visible, full = split_visible_and_full(event.content, max_output_lines)
            parts.append(f"<pre>{html.escape(visible)}</pre>")
            if full is not None:
                parts.append(f"<p><em>Output truncated to {max_output_lines} line(s).</em></p>")
                parts.extend(
                    [
                        "<details>",
                        "<summary>Full output</summary>",
                        f"<pre>{html.escape(full)}</pre>",
                        "</details>",
                    ]
                )
        parts.append("</section>")

    parts.extend(["</body>", "</html>"])
    return "\n".join(parts) + "\n"
