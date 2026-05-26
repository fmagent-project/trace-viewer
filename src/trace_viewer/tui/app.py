from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Input, ListItem, ListView, Static

from trace_viewer.export.markdown import render_markdown
from trace_viewer.models import TraceEvent, TraceSession


class EventListItem(ListItem):
    def __init__(self, event: TraceEvent) -> None:
        self.event = event
        super().__init__(Static(event.title))


class Reader(Static):
    def __init__(self) -> None:
        self.renderable = ""
        super().__init__("", id="reader")

    def update(self, renderable: object = "") -> None:
        self.renderable = str(renderable)
        super().update(renderable)


class TraceViewerApp(App[None]):
    CSS = """
    Horizontal { height: 1fr; }
    #event-list { width: 34%; border: solid $accent; }
    #reader { width: 66%; border: solid $primary; padding: 1; }
    #search-input { height: 3; }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("/", "search", "Search"),
        ("e", "export", "Export"),
    ]

    def __init__(self, session: TraceSession, *, max_output_lines: int = 80) -> None:
        super().__init__()
        self.session = session
        self.max_output_lines = max_output_lines

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Input(placeholder="Search events", id="search-input")
        with Horizontal():
            items = [EventListItem(event) for event in self.session.events]
            yield ListView(*items, id="event-list")
            yield Reader()
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"Trace Viewer: {self.session.session_id}"
        event_list = self.query_one("#event-list", ListView)
        if self.session.events:
            event_list.index = 0
            self._show_event(self.session.events[0])

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, EventListItem):
            self._show_event(event.item.event)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, EventListItem):
            self._show_event(event.item.event)

    def action_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_export(self) -> None:
        output = self.session.source_path.with_suffix(".md")
        output.write_text(
            render_markdown(self.session, max_output_lines=self.max_output_lines),
            encoding="utf-8",
        )
        self.notify(f"Exported Markdown to {output}")

    async def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            await self.filter_events(event.value)

    async def filter_events(self, query: str) -> None:
        normalized = query.casefold().strip()
        if not normalized:
            events = self.session.events
        else:
            events = [
                event
                for event in self.session.events
                if normalized in event.title.casefold() or normalized in event.content.casefold()
            ]
        event_list = self.query_one("#event-list", ListView)
        await event_list.clear()
        await event_list.extend([EventListItem(event) for event in events])
        if events:
            event_list.index = 0
            self._show_event(events[0])
        else:
            self.query_one("#reader", Static).update("No matching events.")

    def _show_event(self, event: TraceEvent) -> None:
        reader = self.query_one("#reader", Static)
        content = event.content
        lines = content.splitlines()
        if len(lines) > self.max_output_lines:
            content = "\n".join(lines[: self.max_output_lines])
            content += f"\n\n[Output truncated to {self.max_output_lines} line(s).]"
        reader.update(f"{event.title}\n\n{content}")
