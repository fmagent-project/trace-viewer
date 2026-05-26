from pathlib import Path

import pytest

from trace_viewer.discovery import DiscoveryError, discover_traces


def test_discover_traces_accepts_file(tmp_path: Path) -> None:
    trace = tmp_path / "one.jsonl"
    trace.write_text("{}", encoding="utf-8")

    assert discover_traces(trace) == [trace]


def test_discover_traces_lists_jsonl_files_sorted(tmp_path: Path) -> None:
    (tmp_path / "b.jsonl").write_text("{}", encoding="utf-8")
    (tmp_path / "a.jsonl").write_text("{}", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("{}", encoding="utf-8")

    assert [path.name for path in discover_traces(tmp_path)] == ["a.jsonl", "b.jsonl"]


def test_discover_traces_reports_missing_path(tmp_path: Path) -> None:
    with pytest.raises(DiscoveryError, match="does not exist"):
        discover_traces(tmp_path / "missing")


def test_discover_traces_reports_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(DiscoveryError, match="No candidate trace files"):
        discover_traces(tmp_path)
