"""Phase 0 contract checks for the interest/fiscal circuit experiment."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from hsm_lab.contract.guards import load_scenario
from hsm_lab.contract.material import MaterialParameters
from hsm_lab.engine.material import material_parameter_vector

ROOT = Path(__file__).resolve().parents[1]


def test_interest_and_fiscal_parameters_are_declared_and_bounded() -> None:
    parameters = MaterialParameters()
    assert parameters.interest_sink_remittance_fraction == 0.0
    assert parameters.interest_sink_recipient == "treasury"
    assert parameters.fiscal_turnover_remittance_fraction == 0.0
    assert parameters.flatten()["interest_sink_remittance_fraction"] == 0.0
    assert parameters.flatten()["interest_sink_recipient.households"] == 0.0
    assert parameters.flatten()["fiscal_turnover_remittance_fraction"] == 0.0
    with pytest.raises(ValidationError):
        MaterialParameters(interest_sink_remittance_fraction=1.01)
    with pytest.raises(ValidationError):
        MaterialParameters(fiscal_turnover_remittance_fraction=1.01)
    with pytest.raises(ValidationError):
        MaterialParameters(interest_sink_recipient="banks")


def test_default_zero_parameters_are_omitted_but_nonzero_values_are_hash_bound() -> None:
    spec = load_scenario(ROOT, "historical_f2_replay")
    base = material_parameter_vector(spec)
    assert "interest_sink_remittance_fraction" not in base
    assert "interest_sink_recipient.households" not in base
    assert "fiscal_turnover_remittance_fraction" not in base
    armed = spec.model_copy(
        update={
            "material_parameters": spec.material_parameters.model_copy(
                update={
                    "interest_sink_remittance_fraction": 0.5,
                    "interest_sink_recipient": "households",
                    "fiscal_turnover_remittance_fraction": 0.02,
                }
            )
        }
    )
    vector = material_parameter_vector(armed)
    assert vector["interest_sink_remittance_fraction"] == 0.5
    assert vector["interest_sink_recipient.households"] == 1.0
    assert vector["fiscal_turnover_remittance_fraction"] == 0.02


def test_interest_fiscal_registry_marks_design_rules_fixed_not_calibrated() -> None:
    control = json.loads((ROOT / "config/calibration/p05.json").read_text())
    registry = yaml.safe_load((ROOT / "config/calibration/p05_parameters.yml").read_text())
    expected = {
        "p05_interest_sink_remittance_prior": "interest_sink_remittance_fraction",
        "p05_interest_sink_recipient_prior": "interest_sink_recipient.households",
        "p05_fiscal_turnover_remittance_prior": "fiscal_turnover_remittance_fraction",
    }
    entries = {row["artifact_id"]: row for row in registry["parameters"]}
    for artifact_id, variable_id in expected.items():
        entry = entries[artifact_id]
        assert entry["variable_id"] == variable_id
        assert any("structural design rule" in ref for ref in entry["literature_refs"])
        assert control["identification"][artifact_id] == "fixed"
        assert artifact_id not in control.get("calibrated", [])
