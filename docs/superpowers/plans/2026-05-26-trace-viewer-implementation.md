# Trace Viewer v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved Trace Viewer v1 Python application with Codex trace parsing, Textual TUI reading, and Markdown/HTML export.

**Architecture:** Keep Codex-specific parsing isolated behind a small internal event model. Discovery, TUI rendering, and exporters consume only that model so Claude support can be added later without rewriting readers/exporters.

**Tech Stack:** Python 3.11+, `textual`, `pytest`, `ruff`, standard-library `argparse`, `dataclasses`, `json`, `pathlib`, and `html`.

---

## File Structure

- `pyproject.toml`: package metadata, dependencies, console script, pytest/ruff config.
- `README.md`: quick usage and development commands.
- `src/trace_viewer/__init__.py`: package version.
- `src/trace_viewer/__main__.py`: `python -m trace_viewer` entrypoint.
- `src/trace_viewer/models.py`: internal dataclasses and event kind enum.
- `src/trace_viewer/discovery.py`: file/directory trace candidate discovery.
- `src/trace_viewer/parsers/__init__.py`: parser exports.
- `src/trace_viewer/parsers/codex.py`: lenient/strict Codex JSONL parser.
- `src/trace_viewer/export/__init__.py`: exporter exports.
- `src/trace_viewer/export/common.py`: shared formatting/truncation helpers.
- `src/trace_viewer/export/markdown.py`: Markdown report exporter.
- `src/trace_viewer/export/html.py`: HTML report exporter.
- `src/trace_viewer/tui/__init__.py`: TUI package.
- `src/trace_viewer/tui/app.py`: Textual Navigator + Reader app.
- `src/trace_viewer/cli.py`: CLI dispatch, export handling, TUI startup.
- `tests/fixtures/codex_session.jsonl`: representative synthetic trace.
- `tests/fixtures/codex_bad.jsonl`: malformed/unknown trace input.
- `tests/test_discovery.py`: discovery behavior.
- `tests/test_codex_parser.py`: parser model, strict mode, lenient warnings.
- `tests/test_export.py`: Markdown/HTML report behavior.
- `tests/test_cli.py`: export command and error handling.
- `tests/test_tui.py`: Textual smoke test.

## Task 1: Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: package directories under `src/trace_viewer`

- [ ] **Step 1: Write package metadata and tool config**

Create `pyproject.toml` with package name `trace-viewer`, console script `trace-viewer = "trace_viewer.cli:main"`, runtime dependency `textual>=0.80`, and dev dependencies `pytest` and `ruff`.

- [ ] **Step 2: Add package entrypoints**

Create `src/trace_viewer/__init__.py` with `__version__`, and `src/trace_viewer/__main__.py` that calls `trace_viewer.cli.main()`.

- [ ] **Step 3: Add README usage**

Document `trace-viewer path/to/session.jsonl`, directory input, and `trace-viewer export ...`.

- [ ] **Step 4: Run package metadata check**

Run: `python -m compileall src`
Expected: compiles package files without errors.

## Task 2: Internal Model and Codex Parser

**Files:**
- Create: `src/trace_viewer/models.py`
- Create: `src/trace_viewer/parsers/__init__.py`
- Create: `src/trace_viewer/parsers/codex.py`
- Create: `tests/fixtures/codex_session.jsonl`
- Create: `tests/fixtures/codex_bad.jsonl`
- Create: `tests/test_codex_parser.py`

- [ ] **Step 1: Write failing parser tests**

Cover message events, tool call/result events, warning events in lenient mode, and strict-mode failure with line numbers.

- [ ] **Step 2: Run parser tests and verify they fail**

Run: `pytest tests/test_codex_parser.py -q`
Expected: fail because modules do not exist yet.

- [ ] **Step 3: Implement dataclasses and parser**

Implement `TraceSession`, `TraceEvent`, `EventKind`, `ParseError`, and `parse_codex_trace(path, strict=False)`.

- [ ] **Step 4: Run parser tests**

Run: `pytest tests/test_codex_parser.py -q`
Expected: pass.

## Task 3: Discovery and Exporters

**Files:**
- Create: `src/trace_viewer/discovery.py`
- Create: `src/trace_viewer/export/__init__.py`
- Create: `src/trace_viewer/export/common.py`
- Create: `src/trace_viewer/export/markdown.py`
- Create: `src/trace_viewer/export/html.py`
- Create: `tests/test_discovery.py`
- Create: `tests/test_export.py`

- [ ] **Step 1: Write failing discovery/export tests**

Cover file input, directory candidate sorting, empty directory failure, Markdown headings, warning section, truncated tool output, and HTML escaping/details blocks.

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/test_discovery.py tests/test_export.py -q`
Expected: fail because modules do not exist yet.

- [ ] **Step 3: Implement discovery and exporters**

Implement `discover_traces(path)` and `render_markdown(session, max_output_lines=80)`, `render_html(session, max_output_lines=80)`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_discovery.py tests/test_export.py -q`
Expected: pass.

## Task 4: CLI and Textual TUI

**Files:**
- Create: `src/trace_viewer/cli.py`
- Create: `src/trace_viewer/tui/__init__.py`
- Create: `src/trace_viewer/tui/app.py`
- Create: `tests/test_cli.py`
- Create: `tests/test_tui.py`

- [ ] **Step 1: Write failing CLI/TUI tests**

Cover export command output, missing path error, invalid format handling, and Textual app navigator population from fixture session.

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/test_cli.py tests/test_tui.py -q`
Expected: fail because CLI/TUI modules are incomplete.

- [ ] **Step 3: Implement CLI**

Implement `main(argv=None)`, `build_parser()`, file/directory input, export writing, strict parsing, and output format validation.

- [ ] **Step 4: Implement Textual app**

Implement Navigator + Reader with left event list, right readable content, footer, search action, export key placeholder, and quit binding.

- [ ] **Step 5: Run CLI/TUI tests**

Run: `pytest tests/test_cli.py tests/test_tui.py -q`
Expected: pass.

## Task 5: Verification and Commit

**Files:**
- Modify as needed based on verification failures.

- [ ] **Step 1: Run full test suite**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 2: Run lint**

Run: `ruff check .`
Expected: no lint errors.

- [ ] **Step 3: Run compile check**

Run: `python -m compileall src tests`
Expected: all files compile.

- [ ] **Step 4: Verify CLI manually**

Run:

```bash
python -m trace_viewer export tests/fixtures/codex_session.jsonl --format md --output /tmp/trace-viewer-report.md
python -m trace_viewer export tests/fixtures/codex_session.jsonl --format html --output /tmp/trace-viewer-report.html
```

Expected: both commands exit 0 and produce non-empty reports.

- [ ] **Step 5: Commit implementation**

Run:

```bash
git add .
git commit -m "Implement trace viewer v1"
```

Expected: implementation committed after verification passes.

## Self-Review

- Spec coverage: single file input, directory input, Codex parser, internal model, lenient warnings, strict errors, Textual Navigator + Reader, Markdown export, HTML export, and concrete error handling are covered.
- Placeholder scan: no implementation placeholders are intentionally left in the plan.
- Type consistency: model names and function names are consistent across parser, discovery, exporters, TUI, and CLI tasks.
