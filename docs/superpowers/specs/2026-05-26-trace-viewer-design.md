# Trace Viewer v1 Design

Date: 2026-05-26

## Purpose

Build a Python command-line application for reading Codex trace files in a human-friendly Textual TUI and exporting readable Markdown or HTML reports. Version 1 focuses on Codex traces only. Claude support is out of scope for v1, but the parser boundary and internal event model should make it straightforward to add later.

## Product Scope

Version 1 supports:

- Opening a single Codex trace file.
- Opening a directory of trace files and choosing one session from a simple picker.
- Rendering a selected session in a two-pane TUI.
- Exporting a selected trace to Markdown or HTML.
- Continuing through malformed or unknown events in interactive mode while surfacing warnings.
- Failing fast with `--strict` for parser development and automated tests.

Version 1 does not support:

- Claude trace parsing.
- Automatic discovery of Codex default log directories.
- Editing, replaying, or resuming traces.
- Full plugin registration for external parser/exporter packages.

## Command Interface

The CLI has two primary flows:

```bash
trace-viewer path/to/session.jsonl
trace-viewer path/to/traces/
trace-viewer export path/to/session.jsonl --format md --output report.md
trace-viewer export path/to/session.jsonl --format html --output report.html
```

File input opens that trace directly. Directory input scans for candidate trace files, presents a simple session picker, then opens the selected session. Export commands are non-interactive and write the requested report format.

Common options:

- `--strict`: treat malformed or unknown events as fatal errors.
- `--max-output-lines N`: cap long tool outputs in the readable view and export body.
- `--format md|html`: select export format for the `export` subcommand.
- `--output PATH`: destination file for export.

## Architecture

The project uses a small layered architecture:

1. **Input discovery** finds trace files from a file or directory argument.
2. **Codex parser** reads Codex trace JSONL and converts records into the internal model.
3. **Internal model** represents sessions, messages, tool calls, tool results, warnings, and raw event metadata.
4. **TUI renderer** consumes only the internal model and renders the Navigator + Reader interface.
5. **Exporters** consume only the internal model and write Markdown or HTML.

The parser is the only layer that knows Codex's raw trace format. This keeps Claude support, parser fixes, and export changes isolated from each other.

## Internal Model

The internal model should be explicit but small:

- `TraceSession`: session id or filename, source path, event list, warnings, optional start/end timestamps.
- `TraceEvent`: base event shape with id, kind, title, timestamp, raw payload, and optional parent turn id.
- `MessageEvent`: user or assistant content.
- `ToolCallEvent`: tool name, command or arguments summary, full arguments, and status when known.
- `ToolResultEvent`: result text, exit status when known, and truncation metadata.
- `WarningEvent`: parser warning tied to a source line or raw payload.

Every parsed event keeps a `raw` field for later inspection and debugging. The v1 TUI does not need a full raw JSON inspector, but retaining raw data prevents the model from becoming lossy too early.

## Parsing Behavior

Default parsing is lenient:

- Valid events become typed model events.
- Unknown or malformed records become warnings and do not stop interactive reading.
- Warnings include source line numbers when available.
- The TUI exposes warning count and warning events in the event navigator.
- Export output includes a warnings section when warnings exist.

Strict mode is available through `--strict`. In strict mode, the parser raises an error on malformed JSON, unknown required fields, or unsupported event shapes that cannot be mapped safely.

## TUI Design

The Textual UI uses a Navigator + Reader layout:

- Left pane: event navigator.
- Right pane: readable content for the selected event.
- Footer/status bar: source session, current event position, warning count, and key hints.

The navigator lists events in chronological order with concise labels such as:

- `User`
- `Assistant`
- `Tool: shell`
- `Result: shell`
- `Warning`

Expected v1 interactions:

- Up/down or `j`/`k`: move selection.
- Enter: focus selected event in the reader.
- `/`: search event titles and visible text.
- `e`: export current session.
- `q`: quit.

The reader prioritizes human-readable text. Tool calls show the tool name and compact argument summary. Long outputs are truncated in the main view according to `--max-output-lines`, with a clear note that additional output exists.

## Export Design

Markdown and HTML exports are readable reports, not raw archives.

Both formats include:

- Title with source filename/session id.
- Optional metadata summary.
- Warning section when parser warnings exist.
- Chronological transcript of user messages, assistant messages, tool calls, and tool results.

Tool output handling:

- The main body shows a concise summary.
- Long output is truncated in the main reading flow.
- Full output is preserved in a collapsible details block where the format supports it.
- Markdown uses HTML `<details>` blocks for full output.
- HTML uses native `<details>` elements.

This keeps exported reports useful for humans while preserving enough detail for debugging.

## Error Handling

User-facing failures should be concrete:

- Missing path: report that the input path does not exist.
- Empty directory: report that no candidate trace files were found.
- Invalid export format: list supported formats.
- Output write failure: include the destination path and underlying error.
- Strict parser failure: include source path, line number when available, and reason.

Interactive parsing warnings are part of the model and visible in the TUI instead of being printed once and lost.

## Testing Strategy

Tests focus on stable boundaries:

- Parser fixture tests convert sample Codex JSONL records into the internal model.
- Strict-mode tests prove malformed inputs fail with useful error messages.
- Lenient-mode tests prove malformed inputs produce warnings and preserve readable events.
- Export snapshot tests verify Markdown and HTML structure for a representative session.
- TUI smoke tests verify the Textual app loads a fixture session and renders the expected number of navigator entries.

The first implementation should include a small synthetic Codex fixture in the test suite. Real trace samples can be added later after sensitive data is redacted.

## Implementation Notes

Use Textual for the TUI because the v1 interaction model needs a durable two-pane layout, keyboard navigation, search, status bars, and future room for richer inspection. Use standard Python libraries for JSON parsing, dataclasses, pathlib, and HTML escaping unless the project later needs stronger schema validation.

Keep modules small and boundary-focused:

- `trace_viewer.cli`: argument parsing and command dispatch.
- `trace_viewer.discovery`: file and directory input handling.
- `trace_viewer.models`: internal dataclasses and enums.
- `trace_viewer.parsers.codex`: Codex JSONL parser.
- `trace_viewer.tui.app`: Textual application.
- `trace_viewer.export.markdown`: Markdown exporter.
- `trace_viewer.export.html`: HTML exporter.

The package name should be `trace_viewer`; the console command should be `trace-viewer`.
