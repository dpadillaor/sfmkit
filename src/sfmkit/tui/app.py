"""The Textual application: browse runs, inspect stages, diff two runs."""

from __future__ import annotations

import json
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane, Tree

from sfmkit.tui.model import STAGES, RunSummary, compare, load_runs


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


class StageDetail(Vertical):
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
        self.add_column("field", width=22)
        self.add_column("A", width=26)
        self.add_column("B", width=26)

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
                             "make all CONFIG=configs/valencia_star.yaml", "")
            return
        self.add_row("[bold]run[/]", f"[bold]{a.name}[/]", f"[bold]{b.name}[/]")
        for field, va, vb in compare(a, b):
            differs = va != vb
            self.add_row(field,
                         f"[yellow]{va}[/]" if differs else va,
                         f"[yellow]{vb}[/]" if differs else vb)


class SfmkitApp(App):
    """Browse reconstruction runs and compare them."""

    CSS = """
    Screen { layout: vertical; }
    #top { height: 45%; }
    RunList { border: round $primary; }
    StageDetail { border: round $secondary; width: 55%; }
    #stage-tree { height: 30%; }
    #stage-body { padding: 0 1; overflow-y: auto; }
    CompareView { border: round $accent; }
    """

    BINDINGS = [
        Binding("q", "quit", "quit"),
        Binding("r", "refresh", "refresh"),
        Binding("a", "mark_a", "mark A"),
        Binding("b", "mark_b", "mark B"),
    ]

    def __init__(self, root: str | Path = "runs") -> None:
        super().__init__()
        self.root = Path(root)
        self.runs: list[RunSummary] = []
        self.mark_a: RunSummary | None = None
        self.mark_b: RunSummary | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("runs", id="tab-runs"), Horizontal(id="top"):
                yield RunList(id="runs")
                yield StageDetail()
            with TabPane("compare", id="tab-compare"):
                yield CompareView(id="compare")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "sfmkit"
        self.action_refresh()

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


def run(root: str | Path = "runs") -> None:
    SfmkitApp(root).run()
