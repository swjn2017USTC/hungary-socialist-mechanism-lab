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


def test_terminal_floors_are_declared_research_thresholds() -> None:
    control = json.loads((ROOT / "config/calibration/p05.json").read_text())
    floors = control["gates"]["terminal_floor"]
    assert floors["t1_production_last_10_min"] == 35092
    assert floors["t2_household_consumption_last_10_min"] == 2085
    assert floors["t3_treasury_solvent_tick"] == 115
    assert floors["t3_rescue_grants_lookback_ticks"] == 20
    assert "Research declarations, not fitted values" in floors["note"]
