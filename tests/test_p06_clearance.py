"""P05 to P06 clearance gates that are independent of model validation."""

from __future__ import annotations

import json
from pathlib import Path

from hsm_lab.contract.guards import AVAILABLE_SCENARIOS

ROOT = Path(__file__).resolve().parents[1]


def test_control_scenario_names_are_registered() -> None:
    control = json.loads((ROOT / "config/calibration/p05.json").read_text())
    assert control["scenarios"]
    assert set(control["scenarios"].values()) <= set(AVAILABLE_SCENARIOS)
    assert control["scenarios"]["historical_replay"] == "historical_f2_replay"
