"""The composition root: pick the adapters, build the app, serve it.

Settings come from the command line or, for containers, the environment.
"""

from __future__ import annotations

import argparse
import os

import uvicorn

from sfmview.adapters.runs_fs import FsRunStore
from sfmview.api import create_app


def build_parser() -> argparse.ArgumentParser:
    env = os.environ.get
    p = argparse.ArgumentParser(prog="sfmview", description="A web viewer for sfmkit runs.")
    p.add_argument("--runs", default=env("SFMVIEW_RUNS", "runs"),
                   help="sfmkit's runs directory (env SFMVIEW_RUNS)")
    p.add_argument("--host", default=env("SFMVIEW_HOST", "127.0.0.1"),
                   help="address to listen on; 0.0.0.0 inside a container (env SFMVIEW_HOST)")
    p.add_argument("--port", type=int, default=int(env("SFMVIEW_PORT", "8000")),
                   help="port (env SFMVIEW_PORT)")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    app = create_app(FsRunStore(args.runs))
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
