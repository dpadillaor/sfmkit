"""What sfmkit and sfmview agree on, and the only thing they share.

Neither imports the other -- a CI job fails if the viewer's environment can so
much as `import sfmkit` -- so what passes between them is written down here
instead, and both test suites hold themselves to it:

- `step.schema.json`, the messages sfmkit publishes while it works, with
  `step.examples.json` beside it and `asyncapi.yaml` describing the channels
  they travel on.
- `run.schema.json`, the files a run leaves behind: what sfmkit writes and
  sfmview reads.

It imports nothing but the standard library, so that being underneath both
costs neither of them a dependency.
"""

from __future__ import annotations

import json
from pathlib import Path

from sfmcontracts import check, npy, run

HERE = Path(__file__).resolve().parent

__all__ = ["HERE", "STEP", "STEP_EXAMPLES", "check", "npy", "run", "step_errors"]

#: The schema of the messages on the broker, and one example of each kind.
STEP = check.load("step")
STEP_EXAMPLES = json.loads((HERE / "step.examples.json").read_text())


def step_errors(message) -> list[str]:
    """What is wrong with a message, sent through JSON as the broker sends it."""
    return check.errors(json.loads(json.dumps(message)), STEP)
