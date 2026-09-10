"""The Textual application: browse runs, inspect stages, diff two runs."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    Tree,
)

from sfmkit.apps.tui.model import STAGES, RunSummary, compare, load_runs


class RunList(DataTable):
    """Runs, newest first. Selection drives everything else."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        for c, w in (("run", 22), ("config", 16), ("stages", 8), ("cams", 5),
                     ("points", 7), ("rot°", 7), ("when", 17)):
            self.add_column(c, width=w)

    def load(self, runs: list[RunSummary]) -> None:
        self.clear()
        for r in runs:
            h = r.headline
            rot = f"{h['mean_rot']:.2f}" if isinstance(h["mean_rot"], (int, float)) else "-"
            self.add_row(r.name, r.config_name, f"{len(r.completed)}/{len(STAGES)}",
                         str(h["cameras"]), str(h["points"]), rot, r.timestamp, key=r.name)


class StageDetail(Horizontal):
    """The selected run's stages, and the raw manifest of whichever is picked."""

    def compose(self) -> ComposeResult:
        yield Tree("stages", id="stage-tree")
        yield Static("", id="stage-body", markup=False)

    def show(self, run: RunSummary | None) -> None:
        tree: Tree = self.query_one("#stage-tree", Tree)
        tree.clear()
        body: Static = self.query_one("#stage-body", Static)
        if run is None:
            tree.root.label = "no run selected"
            body.update("")
            return
        tree.root.label = f"{run.name}  ({run.commit})"
        tree.root.expand()
        for stage in STAGES:
            if stage in run.stages:
                tree.root.add_leaf(f"[green]✓[/] {stage}", data=(run, stage))
            else:
                tree.root.add_leaf(f"[dim]·  {stage}[/]", data=None)
        body.update(_overview(run))

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        body: Static = self.query_one("#stage-body", Static)
        data = event.node.data
        if data is None:
            return
        run, stage = data
        body.update(json.dumps(run.stages[stage], indent=2)[:8000])


def _overview(run: RunSummary) -> str:
    h = run.headline
    lines = [
        f"path        {run.path}",
        f"config      {run.config_name}",
        f"commit      {run.commit}",
        f"stages      {', '.join(run.completed) or '-'}",
        "",
        f"cameras     {h['cameras']}",
        f"3D points   {h['points']}",
        f"tracks      {h['tracks']}",
    ]
    if isinstance(h["mean_rot"], (int, float)):
        lines.append(f"mean rot    {h['mean_rot']:.3f}°  vs COLMAP")
    if isinstance(h["scale"], (int, float)):
        lines.append(f"scale       {h['scale']:.4f}")
    figs = sorted((run.path / "figures").glob("*.png")) if (run.path / "figures").is_dir() else []
    if figs:
        lines += ["", "figures     " + ", ".join(f.name for f in figs)]
    return "\n".join(lines)


class CompareView(DataTable):
    """Side-by-side diff of the two most recently marked runs."""

    def on_mount(self) -> None:
        self.zebra_stripes = True
        self.add_column("field", width=26)
        self.add_column("A", width=48)
        self.add_column("B", width=48)

    def show(self, a: RunSummary | None, b: RunSummary | None, n_runs: int = 0) -> None:
        self.clear()
        if a is None or b is None:
            # An empty table with no explanation is the worst possible empty
            # state; say what to do, and why it might not be possible yet.
            self.add_row("[dim]nothing marked yet[/]", "", "")
            self.add_row("", "", "")
            self.add_row("[bold]go to the 'runs' tab[/]", "", "")
            self.add_row("select a run, press [bold yellow]a[/]", "-> column A", "")
            self.add_row("select another, press [bold yellow]b[/]", "", "-> column B")
            if n_runs < 2:
                self.add_row("", "", "")
                self.add_row(f"[yellow]only {n_runs} run available[/]",
                             "sfmkit run --config configs/valencia/star.yaml", "")
            return
        self.add_row("[bold]run[/]", f"[bold]{a.name}[/]", f"[bold]{b.name}[/]")
        for field, va, vb in compare(a, b):
            differs = va != vb
            self.add_row(field,
                         f"[yellow]{va}[/]" if differs else va,
                         f"[yellow]{vb}[/]" if differs else vb)


class StageRunner(Vertical):
    """Launch a pipeline stage and stream its output.

    The stage runs as a subprocess of the same CLI the user would type. That is
    deliberate on two counts: nothing here duplicates pipeline logic, and a
    stage that crashes takes its own process down rather than the interface.
    The output is displayed, never parsed -- parsing it would quietly turn
    human-readable text into an API.
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="runner-controls"):
            yield Select([(s, s) for s in STAGES if s != "figures"] + [("figures", "figures")],
                         prompt="stage", id="stage-select", allow_blank=False)
            yield Static("", id="runner-status")
        yield RichLog(id="runner-log", highlight=True, markup=True, wrap=False)


class SfmkitApp(App):
    """Browse reconstruction runs and compare them."""

    CSS = """
    Screen { layout: vertical; }
    TabbedContent, ContentSwitcher, TabPane { height: 1fr; }
    #top { height: 1fr; }
    RunList { border: round $primary; height: auto; max-height: 40%; }
    StageDetail { border: round $secondary; height: 1fr; }
    #stage-tree { width: 36; }
    #stage-body { width: 1fr; padding: 0 1; overflow-y: auto; }
    CompareView { border: round $accent; }
    #runner-controls { height: 3; }
    #stage-select { width: 24; }
    #runner-status { padding: 1 2; }
    #runner-log { border: round $warning; }
    """

    BINDINGS = [
        Binding("q", "quit", "quit"),
        Binding("r", "refresh", "refresh"),
        Binding("a", "mark_a", "mark A"),
        Binding("b", "mark_b", "mark B"),
        Binding("x", "run_stage", "run stage"),
        Binding("ctrl+c", "cancel_stage", "cancel"),
    ]

    def __init__(self, root: str | Path = "runs") -> None:
        super().__init__()
        self.root = Path(root)
        self.runs: list[RunSummary] = []
        self.mark_a: RunSummary | None = None
        self.mark_b: RunSummary | None = None
        self._process: subprocess.Popen | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("runs", id="tab-runs"), Vertical(id="top"):
                yield RunList(id="runs")
                yield StageDetail()
            with TabPane("compare", id="tab-compare"):
                yield CompareView(id="compare")
            with TabPane("run", id="tab-run"):
                yield StageRunner()
        yield Footer()

    def on_mount(self) -> None:
        self.title = "sfmkit"
        self.action_refresh()
        self.query_one(RunList).focus()  # so the arrow keys move through runs at once

    # ---- actions ----------------------------------------------------------

    def action_refresh(self) -> None:
        self.runs = load_runs(self.root)
        self.query_one(RunList).load(self.runs)
        self.sub_title = f"{len(self.runs)} runs in {self.root}"
        self.query_one(StageDetail).show(self.runs[0] if self.runs else None)
        self._refresh_compare()  # so the compare tab explains itself before use

    def _selected(self) -> RunSummary | None:
        table = self.query_one(RunList)
        if not self.runs or table.cursor_row is None:
            return None
        try:
            return self.runs[table.cursor_row]
        except IndexError:
            return None

    def action_mark_a(self) -> None:
        self.mark_a = self._selected()
        self._refresh_compare()

    def action_mark_b(self) -> None:
        chosen = self._selected()
        if chosen is not None and self.mark_a is chosen:
            self.notify("A and B are the same run", severity="warning")
        self.mark_b = chosen
        self._refresh_compare()

    def _refresh_compare(self) -> None:
        self.query_one(CompareView).show(self.mark_a, self.mark_b, len(self.runs))
        marks = [r.name for r in (self.mark_a, self.mark_b) if r]
        suffix = f"  |  marked: {', '.join(marks)}" if marks else ""
        self.sub_title = f"{len(self.runs)} runs{suffix}"

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "runs":
            self.query_one(StageDetail).show(self._selected())


    # ---- running a stage ---------------------------------------------------

    def action_run_stage(self) -> None:
        """Run the selected stage on the highlighted run, in a subprocess."""
        if self._process is not None and self._process.poll() is None:
            self.notify("a stage is already running", severity="warning")
            return
        run = self._selected()
        if run is None:
            self.notify("select a run first, on the 'runs' tab", severity="warning")
            return
        config = run.config_path
        if config is None:
            self.notify(f"no config recorded for {run.name}; run it from the CLI once",
                        severity="error")
            return
        stage = self.query_one("#stage-select", Select).value
        if stage is None:
            self.notify("pick a stage", severity="warning")
            return

        cmd = ["sfmkit", str(stage), "--config", config, "--out", str(run.path)]
        log: RichLog = self.query_one("#runner-log", RichLog)
        log.clear()
        log.write(f"[bold]$ {' '.join(cmd)}[/]\n")
        self.query_one(TabbedContent).active = "tab-run"
        self.query_one("#runner-status", Static).update(f"[yellow]running {stage}…[/]")
        self._stream(cmd, str(stage))

    @work(thread=True, exclusive=True)
    def _stream(self, cmd: list[str], stage: str) -> None:
        log: RichLog = self.query_one("#runner-log", RichLog)
        status: Static = self.query_one("#runner-status", Static)
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "MPLBACKEND": "Agg",
               "COLUMNS": "120", "TERM": "dumb"}
        try:
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=env,
            )
        except FileNotFoundError:
            self.call_from_thread(status.update, "[red]sfmkit not on PATH[/]")
            return
        for line in self._process.stdout:
            self.call_from_thread(log.write, line.rstrip())
        code = self._process.wait()
        ok = code == 0
        self.call_from_thread(
            status.update,
            f"[green]{stage} finished[/]" if ok else f"[red]{stage} failed (exit {code})[/]")
        self.call_from_thread(self.action_refresh)
        self.call_from_thread(
            self.notify, f"{stage} {'finished' if ok else f'failed ({code})'}",
            severity="information" if ok else "error")

    def action_cancel_stage(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            self.query_one("#runner-status", Static).update("[yellow]cancelled[/]")
        else:
            self.exit()


def run(root: str | Path = "runs") -> None:
    SfmkitApp(root).run()
