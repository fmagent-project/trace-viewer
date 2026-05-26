from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class EventKind(str, Enum):
    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    WARNING = "warning"


@dataclass
class TraceEvent:
    id: str
    kind: EventKind
    title: str
    content: str
    timestamp: str | None = None
    raw: dict[str, Any] | str | None = None
    role: str | None = None
    tool_name: str | None = None
    arguments: dict[str, Any] | str | None = None
    status: str | None = None
    exit_code: int | None = None
    line_number: int | None = None


@dataclass
class TraceSession:
    session_id: str
    source_path: Path
    events: list[TraceEvent] = field(default_factory=list)
    warnings: list[TraceEvent] = field(default_factory=list)
    started_at: str | None = None
    ended_at: str | None = None

    @property
    def warning_count(self) -> int:
        return len(self.warnings)
