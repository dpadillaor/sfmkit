"""The ``sfmkit run`` command: every stage, in order."""

from __future__ import annotations

from pathlib import Path

from sfmkit.apps.cli import changes, evaluate, figures, localize, match, reconstruct, verify
from sfmkit.apps.cli._common import console
from sfmkit.data.config import load_config

#: Stage order. This is where it lives; module names carry no number.
STAGES = [
    ("match", match.cmd_match),
    ("verify", verify.cmd_verify),
    ("reconstruct", reconstruct.cmd_reconstruct),
    ("localize", localize.cmd_localize),
    ("evaluate", evaluate.cmd_evaluate),
    ("changes", changes.cmd_changes),
    ("figures", figures.cmd_figures),
]


def cmd_run(args) -> int:
    """Run the pipeline end to end, stopping at the first stage that fails."""
    load_config(args.config)  # fail early on a bad config, before any stage runs
    out = Path(args.out)

    names = [n for n, _ in STAGES]
    if args.only:
        wanted = set(args.only.split(","))
        unknown = wanted - set(names)
        if unknown:
            console.print(f"[red]unknown stages:[/red] {', '.join(sorted(unknown))}")
            console.print(f"available: {', '.join(names)}")
            return 1
        stages = [(n, f) for n, f in STAGES if n in wanted]
    else:
        start = names.index(args.From) if args.From else 0
        stages = STAGES[start:]

    skipped = []
    for name, fn in stages:
        if args.skip_done and (out / f"manifest_{name}.json").is_file():
            skipped.append(name)
            continue
        console.rule(f"[bold]{name}")
        code = fn(_StageArgs(args, name))
        if code != 0:
            console.print(f"[red]{name} failed[/red] (exit {code}); stopping")
            return code

    if skipped:
        console.print(f"[dim]skipped (already done): {', '.join(skipped)}[/dim]")
    console.rule("[green]done")
    console.print(f"run: {out}")
    return 0


class _StageArgs:
    """Adapts ``run``'s arguments to what an individual stage expects."""

    def __init__(self, args, stage: str) -> None:
        self.config = args.config
        self.out = args.out
        self.trials = getattr(args, "trials", 20)
        self.against = None
        self.threshold = 0.38
        self._stage = stage
