from __future__ import annotations

import argparse
import sys
from pathlib import Path

from trace_viewer.discovery import DiscoveryError, discover_traces
from trace_viewer.export.html import render_html
from trace_viewer.export.markdown import render_markdown
from trace_viewer.parsers.codex import ParseError, parse_codex_trace
from trace_viewer.tui.app import TraceViewerApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trace-viewer")
    parser.add_argument("--strict", action="store_true", help="fail on malformed or unknown events")
    parser.add_argument(
        "--max-output-lines",
        type=int,
        default=80,
        help="maximum output lines shown before truncation",
    )
    parser.add_argument("path", nargs="?")
    return parser


def build_export_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trace-viewer export")
    parser.add_argument("path")
    parser.add_argument("--format", choices=["md", "html"], required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--max-output-lines", type=int, default=80)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["export"]:
        parser = build_export_parser()
        args = parser.parse_args(argv[1:])
        try:
            return _run_export(args)
        except (DiscoveryError, ParseError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 2

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if not args.path:
            parser.print_usage(sys.stderr)
            return 2
        return _run_tui(args)
    except (DiscoveryError, ParseError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _run_export(args: argparse.Namespace) -> int:
    traces = discover_traces(args.path)
    session = parse_codex_trace(traces[0], strict=args.strict)
    if args.format == "md":
        rendered = render_markdown(session, max_output_lines=args.max_output_lines)
    elif args.format == "html":
        rendered = render_html(session, max_output_lines=args.max_output_lines)
    else:
        raise ValueError(f"Unsupported export format: {args.format}")
    Path(args.output).write_text(rendered, encoding="utf-8")
    return 0


def _run_tui(args: argparse.Namespace) -> int:
    traces = discover_traces(args.path)
    selected = _select_trace(traces)
    session = parse_codex_trace(selected, strict=args.strict)
    TraceViewerApp(session, max_output_lines=args.max_output_lines).run()
    return 0


def _select_trace(traces: list[Path]) -> Path:
    if len(traces) == 1:
        return traces[0]
    print("Available trace sessions:")
    for index, trace in enumerate(traces, start=1):
        print(f"{index}. {trace.name}")
    while True:
        choice = input("Select session number: ")
        try:
            selected = int(choice)
        except ValueError:
            print("Enter a number.")
            continue
        if 1 <= selected <= len(traces):
            return traces[selected - 1]
        print(f"Enter a number between 1 and {len(traces)}.")
