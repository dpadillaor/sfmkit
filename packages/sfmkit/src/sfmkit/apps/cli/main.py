"""Argument parsing and dispatch.

One subcommand per module. Stage order lives in ``run.STAGES``, not in module
names, so inserting a stage renames nothing.
"""

from __future__ import annotations

import argparse
import sys

from sfmkit.apps.cli import (
    calibrate,
    changes,
    colmap,
    dense,
    evaluate,
    figures,
    localize,
    match,
    new,
    reconstruct,
    run,
    verify,
)
from sfmkit.apps.cli._common import console
from sfmkit.data.features import WeightsUnavailable


def _stages(helps: dict[str, str]) -> str:
    """The pipeline's stages in order, for ``run``'s help: the order is run.STAGES's."""
    lines = ["stages, in the order `run` does them:"]
    lines += [f"  {name:<12}{helps.get(name, '')}" for name, _ in run.STAGES]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sfmkit",
        description="Structure from Motion: match, reconstruct, localise, evaluate.",
    )
    sub = p.add_subparsers(dest="command", required=True)
    helps: dict[str, str] = {}

    def stage(name, fn, help_):
        helps[name] = help_
        s = sub.add_parser(name, help=help_)
        s.add_argument("--config", required=True, help="YAML experiment config")
        s.add_argument("--out", help="run directory (default: the project's runs/<config>)")
        s.set_defaults(func=fn)
        return s

    n = sub.add_parser("new", help="lay out a new project: data/, configs/ and a config")
    n.add_argument("name", help="the project's name, and the directory it gets")
    n.add_argument("--in", dest="inside", default="projects", metavar="DIR",
                   help="where projects live (default: projects)")
    n.add_argument("--photos", metavar="DIR",
                   help="photographs to copy into the project, and to list in the config")
    n.set_defaults(func=new.cmd_new)

    stage("calibrate", calibrate.cmd_calibrate,
          "intrinsics from chessboard photos, or a precomputed K")
    stage("match", match.cmd_match, "detect and match features for every configured pair")
    stage("verify", verify.cmd_verify, "fit fundamental matrices and keep geometric inliers")
    stage("reconstruct", reconstruct.cmd_reconstruct, "build tracks and run incremental SfM + BA")

    loc = stage("localize", localize.cmd_localize,
                "localise the query image against the reconstruction")
    loc.add_argument("--trials", type=int, default=20,
                     help="seeds to run, so the pose is reported as a distribution")

    stage("colmap", colmap.cmd_colmap, "the COLMAP model the run is scored against")
    stage("dense", dense.cmd_dense, "COLMAP's dense point cloud of the scene (needs CUDA)")
    stage("evaluate", evaluate.cmd_evaluate, "compare the reconstruction against COLMAP")
    stage("figures", figures.cmd_figures, "render figures for a finished run")

    ch = stage("changes", changes.cmd_changes,
               "detect scene change between the query and a modern image")
    ch.add_argument("--against", help="modern image to compare against (default: the reference)")
    ch.add_argument("--threshold", type=float, default=0.38,
                    help="dissimilarity threshold in [0, 1]")

    r = stage("run", run.cmd_run, "run every stage in order")
    r.add_argument("--from", dest="From", metavar="STAGE",
                   help="start at this stage instead of the first")
    r.add_argument("--only", metavar="A,B", help="run only these stages")
    r.add_argument("--skip-done", action="store_true",
                   help="skip stages whose manifest already exists")
    r.add_argument("--trials", type=int, default=20, help="seeds for localize")
    r.formatter_class = argparse.RawDescriptionHelpFormatter
    r.epilog = _stages(helps)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except WeightsUnavailable as e:  # its message is the instructions
        console.print(f"[red]{e}[/red]")
        return 1
    except FileNotFoundError as e:
        console.print(f"[red]missing file:[/red] {e}")
        return 1
    except Exception as e:  # surface the failure, not a bare traceback
        console.print(f"[red]{type(e).__name__}:[/red] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
