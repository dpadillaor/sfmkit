"""The composition root: pick the adapters, build the app, serve it.

Settings come from the command line or, for containers, the environment.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request

import uvicorn

from sfmview.adapters.images_fs import FsImageStore
from sfmview.adapters.redis_steps import RedisStepSource
from sfmview.adapters.runs_fs import FsRunStore
from sfmview.api import create_app


def build_parser() -> argparse.ArgumentParser:
    env = os.environ.get
    p = argparse.ArgumentParser(prog="sfmview", description="A web viewer for sfmkit runs.")
    p.add_argument("--projects", default=env("SFMVIEW_PROJECTS", "projects"),
                   help="sfmkit's projects directory: a run and its photographs "
                        "are both inside one (env SFMVIEW_PROJECTS)")
    p.add_argument("--host", default=env("SFMVIEW_HOST", "127.0.0.1"),
                   help="address to listen on; 0.0.0.0 inside a container (env SFMVIEW_HOST)")
    p.add_argument("--port", type=int, default=int(env("SFMVIEW_PORT", "8000")),
                   help="port (env SFMVIEW_PORT)")
    p.add_argument("--broker", default=env("SFMVIEW_BROKER"),
                   help="Redis URL for live progress, e.g. redis://localhost:6379; "
                        "none, no live progress (env SFMVIEW_BROKER)")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    steps = RedisStepSource.from_url(args.broker) if args.broker else None
    app = create_app(FsRunStore(args.projects), steps, FsImageStore(args.projects))
    uvicorn.run(app, host=args.host, port=args.port)


def health(argv: list[str] | None = None) -> int:
    """0 if the server the same settings describe answers ``/api/health``, else 1.

    A container's healthcheck, run inside it: the image has Python, not curl.
    """
    args = build_parser().parse_args(argv)
    host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(args.host, args.host)
    if ":" in host:
        host = f"[{host}]"
    try:
        with urllib.request.urlopen(f"http://{host}:{args.port}/api/health", timeout=2) as r:
            return 0 if json.load(r).get("status") == "ok" else 1
    except (OSError, ValueError):
        return 1


if __name__ == "__main__":
    main()
