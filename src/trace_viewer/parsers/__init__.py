from __future__ import annotations

import json
from pathlib import Path

from trace_viewer.models import TraceSession
from trace_viewer.parsers.codex import ParseError, parse_codex_trace
from trace_viewer.parsers.opencode import parse_opencode_trace

__all__ = [
    "ParseError",
    "detect_format",
    "parse_codex_trace",
    "parse_opencode_trace",
    "parse_trace",
]


def detect_format(path: str | Path) -> str:
    """Sniff a trace file's format. Returns ``"opencode"`` or ``"codex"``."""
    source_path = Path(path)
    with source_path.open(encoding="utf-8") as handle:
        for _ in range(5):
            line = handle.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and record.get("_kind") in {"request", "response"}:
                return "opencode"
            break
    return "codex"


def parse_trace(path: str | Path, *, strict: bool = False) -> TraceSession:
    """Parse a trace file, auto-detecting whether it is a Codex or OpenCode trace."""
    if detect_format(path) == "opencode":
        return parse_opencode_trace(path, strict=strict)
    return parse_codex_trace(path, strict=strict)
