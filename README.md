# Trace Viewer

Trace Viewer reads Codex and OpenCode trace files, browses them in a terminal UI (TUI), and exports readable Markdown or HTML reports. The trace format is auto-detected, so the same commands work for either kind of file.

## Install

Requires Python 3.10+.

```bash
pip install -e .
```

This installs the `trace-viewer` command. (You can also run it without installing via `python -m trace_viewer`.)

## Usage

### Open a trace in the TUI

Pass a single `.jsonl` trace file:

```bash
trace-viewer path/to/session.jsonl
```

Or pass a directory — Trace Viewer finds every `.jsonl` file inside and, if there is more than one, prompts you to pick a session:

```bash
trace-viewer path/to/traces/
```

Once the TUI is open:

| Key | Action |
| --- | ------ |
| `↑` / `↓` | Move between events in the list |
| `/` | Search events |
| `e` | Export the current session |
| `q` | Quit |

The event list is on the left; the selected event's detail is shown in a scrollable reader on the right.

### Export a report

Write a session to Markdown or HTML without opening the TUI:

```bash
trace-viewer export path/to/session.jsonl --format md   --output report.md
trace-viewer export path/to/session.jsonl --format html --output report.html
```

`--format` (`md` or `html`) and `--output` are required.

### Options

These flags work for both the viewer and `export`:

- `--max-output-lines N` — cap how many output lines are shown per event before truncation (default `80`).
- `--strict` — fail on malformed or unknown events instead of skipping them.

```bash
trace-viewer path/to/session.jsonl --max-output-lines 200 --strict
```

## Development

```bash
pytest -q
ruff check .
python -m compileall src tests
```
