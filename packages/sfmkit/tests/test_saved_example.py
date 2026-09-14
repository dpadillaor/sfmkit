"""The saved example is a frozen reference, and must not drift from its config.

The regression check re-runs `verify`...`evaluate` on `examples/valencia/*` and
scores the result against the COLMAP model saved beside it. That is only a
check while the example was made by the config it names: change a threshold and
forget to regenerate, and the check goes on passing against rules nobody uses.

Every stage records the whole config it ran with, so the two can be compared.
"""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from sfmkit.data.config import PATH_FIELDS, load_config

REPO = Path(__file__).resolve().parents[3]
EXAMPLES = REPO / "examples" / "valencia"
CONFIGS = REPO / "configs" / "valencia"


def portable(config: dict) -> dict:
    """A config as it decides a result.

    Absolute paths say where it ran, not what it did: the data root moves
    between a laptop, a container and a runner.
    """
    out = json.loads(json.dumps(config))
    out.pop("dataset_dir", None)
    for section, fields in PATH_FIELDS.items():
        for name in fields:
            value = out.get(section, {}).get(name)
            if value:
                out[section][name] = Path(value).name
    return out


@pytest.mark.parametrize("name", [p.name for p in sorted(EXAMPLES.iterdir()) if p.is_dir()])
def test_the_saved_example_was_made_by_the_config_it_names(name):
    manifest = json.loads((EXAMPLES / name / "reconstruct" / "manifest.json").read_text())
    current = portable(asdict(load_config(CONFIGS / f"{name}.yaml")))
    saved = portable(manifest["config"])
    moved = sorted(k for k in current | saved if current.get(k) != saved.get(k))
    assert not moved, (
        f"examples/valencia/{name} was made with a different {', '.join(moved)}: "
        f"re-run the stages and commit the result, or the regression check is "
        f"scoring against rules that are no longer in the config"
    )
