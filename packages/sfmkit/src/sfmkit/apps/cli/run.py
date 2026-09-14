"""The ``sfmkit run`` command: every stage, in order."""

from __future__ import annotations

import time

from sfmkit.apps.cli import (
    calibrate,
    changes,
    colmap,
    dense,
    evaluate,
    figures,
    localize,
    match,
    reconstruct,
    verify,
)
from sfmkit.apps.cli._common import console, run_dir
from sfmkit.data import live
from sfmkit.data.colmap import NO_CUDA, dense_available
from sfmkit.data.config import Config, load_config

#: Stage order. This is where it lives; module names carry no number.
STAGES = [
    ("calibrate", calibrate.cmd_calibrate),
    ("match", match.cmd_match),
    ("verify", verify.cmd_verify),
    ("reconstruct", reconstruct.cmd_reconstruct),
    ("localize", localize.cmd_localize),
    ("colmap", colmap.cmd_colmap),
    ("dense", dense.cmd_dense),
    ("evaluate", evaluate.cmd_evaluate),
    ("changes", changes.cmd_changes),
    ("figures", figures.cmd_figures),
]


def configured(cfg: Config, stage: str) -> bool:
    """Whether the config asks for a stage at all.

    `dense` already skips itself when it is off. The same holds for the rest: a
    project with no historical photograph has nothing to localise, and one with
    no COLMAP has nothing to be scored against. `run` walks past them; asking
    for one by name still says what is missing.
    """
    if stage in ("localize", "changes"):
        return bool(cfg.localize.query)
    if stage in ("colmap", "evaluate"):
        return bool(cfg.colmap.precomputed or cfg.colmap.matches)
    return True


def cmd_run(args) -> int:
    """Run the pipeline end to end, stopping at the first stage that fails."""
    cfg = load_config(args.config)  # fail early on a bad config, before any stage runs
    out = run_dir(cfg, args.out)

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
        stages = [(n, f) for n, f in STAGES[start:] if configured(cfg, n)]
        absent = [n for n, _ in STAGES[start:] if not configured(cfg, n)]
        if absent:
            console.print(f"[dim]not in this config: {', '.join(absent)}[/dim]")

    problem = _needs_missing_cuda(cfg, {n for n, _ in stages})
    if problem:
        console.print(f"[red]{problem}[/red]")
        return 1

    # Whoever watches this run sees every stage, not only the one that has
    # something to draw: `match` alone is minutes of silence, and a page with
    # nothing on it looks like a run that died. The heartbeat covers the whole
    # run for the same reason.
    run_name = live.name_of(out)
    broker = live.publisher(run_name)

    skipped = []
    with live.heartbeat(run_name):
        for name, fn in stages:
            if args.skip_done and (out / name / "manifest.json").is_file():
                skipped.append(name)
                continue
            console.rule(f"[bold]{name}")
            broker.publish(live.stage_message(run_name, name, "start"))
            began = time.monotonic()
            try:
                code = fn(_StageArgs(args, name))
            except BaseException as e:  # an interruption is a stage stopping too
                broker.publish(live.stage_message(run_name, name, "failed",
                                                  time.monotonic() - began,
                                                  type(e).__name__))
                raise
            if code != 0:
                broker.publish(live.stage_message(run_name, name, "failed",
                                                  time.monotonic() - began,
                                                  f"exit {code}"))
                console.print(f"[red]{name} failed[/red] (exit {code}); stopping")
                return code
            broker.publish(live.stage_message(run_name, name, "end",
                                              time.monotonic() - began))

    if skipped:
        console.print(f"[dim]skipped (already done): {', '.join(skipped)}[/dim]")
    console.rule("[green]done")
    console.print(f"run: {out}")
    return 0


def _needs_missing_cuda(cfg: Config, stages: set[str]) -> str | None:
    """Why the config asks for CUDA this machine lacks, before any stage runs."""
    if "dense" in stages and cfg.dense.enabled and not dense_available():
        return NO_CUDA
    if "match" in stages and cfg.sfm.device == "cuda":
        from sfmkit.data.features import pick_device  # imports torch, so only when asked

        try:
            pick_device("cuda")
        except ValueError as e:
            return str(e)
    return None


class _StageArgs:
    """Adapts ``run``'s arguments to what an individual stage expects."""

    def __init__(self, args, stage: str) -> None:
        self.config = args.config
        self.out = args.out
        self.trials = getattr(args, "trials", 20)
        self.against = None
        self.threshold = 0.38
        self._stage = stage
