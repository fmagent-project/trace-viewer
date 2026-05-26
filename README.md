# Trace Viewer

Trace Viewer reads Codex trace files, displays them in a Textual TUI, and exports readable Markdown or HTML reports.

```bash
trace-viewer path/to/session.jsonl
trace-viewer path/to/traces/
trace-viewer export path/to/session.jsonl --format md --output report.md
trace-viewer export path/to/session.jsonl --format html --output report.html
```

Development:

```bash
pytest -q
ruff check .
python -m compileall src tests
```
