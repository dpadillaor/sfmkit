"""What is inside an ``.npz``, read without numpy.

A run's arrays are the half of the contract that numpy usually reads, and
reading them here with the standard library alone is the point: this package
is what the two sides agree on, so it must not drag either side's dependencies
in. An ``.npz`` is a zip of ``.npy`` files, and an ``.npy`` file begins with a
header saying its dtype and its shape, which is all a contract needs.
"""

from __future__ import annotations

import ast
import struct
import zipfile
from pathlib import Path

MAGIC = b"\x93NUMPY"

#: The dtype letter, as the header spells it, to the word a contract uses.
KINDS = {"f": "float", "i": "int", "u": "uint", "U": "str", "S": "bytes", "b": "bool"}


class NotAnArray(ValueError):
    """The file is not an ``.npy``, or is one this cannot read."""


def arrays(path) -> dict[str, tuple[str, tuple[int, ...]]]:
    """Every array in an ``.npz``: its name to its kind and its shape."""
    out = {}
    with zipfile.ZipFile(Path(path)) as z:
        for entry in z.namelist():
            if not entry.endswith(".npy"):
                continue
            with z.open(entry) as f:
                out[entry[: -len(".npy")]] = header(f)
    return out


def header(f) -> tuple[str, tuple[int, ...]]:
    """The kind and shape an open ``.npy`` file declares."""
    if f.read(len(MAGIC)) != MAGIC:
        raise NotAnArray("not an .npy file")
    major, _minor = f.read(2)
    size = 2 if major == 1 else 4
    (length,) = struct.unpack("<H" if size == 2 else "<I", f.read(size))
    described = ast.literal_eval(f.read(length).decode("latin1"))
    descr = described["descr"]
    if not isinstance(descr, str):  # a structured dtype: no contract uses one
        raise NotAnArray(f"structured dtype {descr!r}")
    letter = descr[1] if descr[0] in "<>|=" else descr[0]
    return KINDS.get(letter, letter), tuple(described["shape"])
