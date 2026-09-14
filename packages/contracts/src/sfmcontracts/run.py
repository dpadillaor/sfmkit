"""Check a run's files against ``run.schema.json``.

sfmkit writes these files and sfmview reads them, and neither imports the
other: this is what holds them to one reading of the format. The messages on
the broker have had such a check since there were messages; the files had only
a paragraph of prose, and prose does not fail a build.
"""

from __future__ import annotations

import json
from pathlib import Path

from sfmcontracts import check
from sfmcontracts.npy import NotAnArray, arrays

HERE = Path(__file__).resolve().parent


def load() -> dict:
    return json.loads((HERE / "run.schema.json").read_text())


def errors(run_dir, spec: dict | None = None) -> list[str]:
    """What is wrong with the files in ``run_dir``; empty when they conform.

    A file the contract lists may be missing -- a run stops where it stops --
    but one that is there must be what the contract says.
    """
    run_dir = Path(run_dir)
    spec = spec or load()
    out: list[str] = []
    for pattern, rule in spec["files"].items():
        for path in sorted(run_dir.glob(pattern)):
            where = path.relative_to(run_dir).as_posix()
            if "arrays" in rule:
                out += _arrays(path, where, rule["arrays"])
            if "schema" in rule:
                out += _json(path, where, rule["schema"])
    return out


def _arrays(path: Path, where: str, wanted: dict) -> list[str]:
    try:
        found = arrays(path)
    except (NotAnArray, OSError, ValueError) as e:
        return [f"{where}: cannot be read as arrays: {e}"]
    out = []
    named: dict[str, int] = {}   # a dimension's name to the size first seen for it
    for name, rule in wanted.items():
        if name not in found:
            if rule.get("required", True):
                out.append(f"{where}: missing array {name!r}")
            continue
        kind, shape = found[name]
        if kind != rule["kind"]:
            out.append(f"{where}: {name} is {kind}, not {rule['kind']}")
        out += _shape(where, name, shape, rule["shape"], named)
    return out


def _shape(where: str, name: str, shape, wanted, named: dict) -> list[str]:
    if len(shape) != len(wanted):
        return [f"{where}: {name} has shape {shape}, not {tuple(wanted)}"]
    out = []
    for axis, (size, want) in enumerate(zip(shape, wanted, strict=True)):
        if isinstance(want, int):
            if size != want:
                out.append(f"{where}: {name} axis {axis} is {size}, not {want}")
        elif named.setdefault(want, size) != size:
            out.append(f"{where}: {name} axis {axis} is {size}, but {want} is "
                       f"{named[want]} elsewhere in this file")
    return out


def _json(path: Path, where: str, schema: dict) -> list[str]:
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return [f"{where}: cannot be read as JSON: {e}"]
    return [f"{where}: {problem}" for problem in check.errors(value, schema)]
