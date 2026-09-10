"""Check a message against a JSON Schema, the part of it the contracts here use.

Both packages' tests load this file, so sfmkit and sfmview are held to one
reading of the schema. It covers ``type``, ``const``, ``required``,
``properties``, ``additionalProperties: false``, ``items``, ``minItems``,
``maxItems``, ``oneOf`` and local ``$ref``: the standard library only, as
neither package otherwise needs a validator. Swap it for ``jsonschema`` if one
joins.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
    "null": lambda v: v is None,
}


def load(name: str) -> dict:
    """A schema from this directory, e.g. ``load("step")``."""
    return json.loads((HERE / f"{name}.schema.json").read_text())


def errors(value, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    """What is wrong with ``value``; empty when it conforms."""
    root = root or schema
    if "$ref" in schema:
        schema = _resolve(root, schema["$ref"])
    if "oneOf" in schema:
        results = [errors(value, s, root, path) for s in schema["oneOf"]]
        passing = [r for r in results if not r]
        if len(passing) == 1:
            return []
        if passing:
            return [f"{path}: matches {len(passing)} alternatives of oneOf"]
        return [f"{path}: matches none of oneOf: " + "; ".join(min(results, key=len))]

    out: list[str] = []
    if "const" in schema and value != schema["const"]:
        return [f"{path}: {value!r} is not {schema['const']!r}"]
    if "type" in schema:
        kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_TYPES[k](value) for k in kinds):
            return [f"{path}: {type(value).__name__} is not {' or '.join(kinds)}"]
    if isinstance(value, dict):
        props = schema.get("properties", {})
        out += [f"{path}: missing {k!r}" for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            out += [f"{path}: unexpected {k!r}" for k in value if k not in props]
        for k, v in value.items():
            if k in props:
                out += errors(v, props[k], root, f"{path}.{k}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            out.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            out.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, v in enumerate(value):
                out += errors(v, schema["items"], root, f"{path}[{i}]")
    return out


def _resolve(root: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise ValueError(f"only local references: {ref}")
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node
