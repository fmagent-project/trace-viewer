from __future__ import annotations

from pathlib import Path


class DiscoveryError(ValueError):
    pass


def discover_traces(path: str | Path) -> list[Path]:
    candidate = Path(path)
    if not candidate.exists():
        raise DiscoveryError(f"Input path does not exist: {candidate}")
    if candidate.is_file():
        return [candidate]
    if candidate.is_dir():
        traces = sorted(p for p in candidate.iterdir() if p.is_file() and p.suffix == ".jsonl")
        if not traces:
            raise DiscoveryError(f"No candidate trace files found in {candidate}")
        return traces
    raise DiscoveryError(f"Input path is neither a file nor a directory: {candidate}")
