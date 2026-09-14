"""What sfmkit writes is what the contract says it writes.

The messages on the broker have been checked against a schema since there were
messages. The files a run leaves behind were described in prose, and the
viewer reads them: rename an array and every test here stays green, because
sfmkit reads back what it wrote, while the viewer -- which fabricates its own
fixtures and reads a frozen run made before the change -- stays green too. The
first thing to notice would be an empty page.
"""

from pathlib import Path

import numpy as np
import pytest
import yaml

from sfmcontracts import HERE, check, run
from sfmkit.core.types import Pose, Reconstruction, Track
from sfmkit.data.io import save_reconstruction

PROJECT = Path(__file__).resolve().parents[3] / "projects" / "valencia"
FROZEN = sorted(PROJECT.glob("runs/reference-*"))


@pytest.mark.parametrize("frozen", FROZEN, ids=lambda p: p.name)
def test_a_frozen_run_keeps_to_the_contract(frozen):
    assert run.errors(frozen) == []


def test_what_reconstruct_writes_keeps_to_the_contract(tmp_path):
    """Not only the frozen runs: what the writer produces today."""
    rec = Reconstruction(
        K=np.eye(3),
        poses={f"Img{i:02d}": Pose(np.eye(3), np.zeros(3)) for i in range(1, 4)},
        points=np.zeros((5, 3)),
        tracks=[Track({"Img01": i}) for i in range(5)],
    )
    save_reconstruction(rec, tmp_path / "reconstruct" / "reconstruction.npz")
    assert run.errors(tmp_path) == []


def test_the_contract_catches_a_renamed_array(tmp_path):
    out = tmp_path / "reconstruct"
    out.mkdir()
    np.savez(out / "reconstruction.npz", K=np.eye(3), image_names=np.array(["Img01"]),
             rotations=np.eye(3)[None], translations=np.zeros((1, 3)),
             points3d=np.zeros((5, 3)))       # `points` under another name
    problems = run.errors(tmp_path)
    assert any("missing array 'points'" in p for p in problems), problems


def test_the_contract_catches_a_shape_that_disagrees_with_itself(tmp_path):
    out = tmp_path / "reconstruct"
    out.mkdir()
    np.savez(out / "reconstruction.npz", K=np.eye(3), image_names=np.array(["Img01", "Img02"]),
             rotations=np.eye(3)[None], translations=np.zeros((1, 3)),  # one camera, not two
             points=np.zeros((5, 3)))
    assert any("cameras is" in p for p in run.errors(tmp_path))


def test_every_kind_of_message_is_in_the_asyncapi_document():
    """The document points at the schema rather than repeating it; nothing
    stopped it from pointing at fewer kinds than there are."""
    document = yaml.safe_load((HERE / "asyncapi.yaml").read_text())
    referenced = set()

    def walk(node):
        if isinstance(node, dict):
            ref = node.get("$ref", "")
            if "step.schema.json#/$defs/" in ref:
                referenced.add(ref.rsplit("/", 1)[1])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(document)
    kinds = {branch["$ref"].rsplit("/", 1)[1] for branch in check.load("step")["oneOf"]}
    assert referenced == kinds
