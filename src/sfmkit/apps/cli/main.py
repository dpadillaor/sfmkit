"""Argument parsing and dispatch.

One subcommand per module. Stage order lives in the Makefile and in the config,
not in module names, so inserting a stage renames nothing.
"""

from __future__ import annotations

import argparse
import sys

from sfmkit.apps.cli import (
    changes,
    evaluate,
    figures,
    localize,
    match,
    reconstruct,
    ui,
    verify,
)
from sfmkit.apps.cli._common import console


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sfmkit",
        description="Structure from Motion: match, reconstruct, localise, evaluate.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def stage(name, fn, help_):
        s = sub.add_parser(name, help=help_)
        s.add_argument("--config", required=True, help="YAML experiment config")
        s.add_argument("--out", required=True, help="run directory for inputs and outputs")
        s.set_defaults(func=fn)
        return s

    stage("match", match.cmd_match, "detect and match features for every configured pair")
    stage("verify", verify.cmd_verify, "fit fundamental matrices and keep geometric inliers")
    stage("reconstruct", reconstruct.cmd_reconstruct, "build tracks and run incremental SfM + BA")

    loc = stage("localize", localize.cmd_localize,
                "localise the query image against the reconstruction")
    loc.add_argument("--trials", type=int, default=20,
                     help="seeds to run, so the pose is reported as a distribution")

    stage("evaluate", evaluate.cmd_evaluate, "compare the reconstruction against a COLMAP model")
    stage("figures", figures.cmd_figures, "render figures for a finished run")

    ch = stage("changes", changes.cmd_changes,
               "detect scene change between the query and a modern image")
    ch.add_argument("--against", help="modern image to compare against (default: the reference)")
    ch.add_argument("--threshold", type=float, default=0.38,
                    help="dissimilarity threshold in [0, 1]")

    u = sub.add_parser("ui", help="browse and compare runs in a terminal interface")
    u.add_argument("--runs", default="runs", help="directory holding run outputs")
    u.set_defaults(func=ui.cmd_ui)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        console.print(f"[red]missing file:[/red] {e}")
        return 1
    except Exception as e:  # surface the failure, not a bare traceback
        console.print(f"[red]{type(e).__name__}:[/red] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
