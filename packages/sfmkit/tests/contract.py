"""The contracts at the repository's root, as the tests see them."""

import importlib.util
import json
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[3] / "contracts"

_spec = importlib.util.spec_from_file_location("contract_check", CONTRACTS / "check.py")
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

STEP = check.load("step")
STEP_EXAMPLES = json.loads((CONTRACTS / "step.examples.json").read_text())


def step_errors(message) -> list[str]:
    """What is wrong with a message, sent through JSON as the broker sends it."""
    return check.errors(json.loads(json.dumps(message)), STEP)
