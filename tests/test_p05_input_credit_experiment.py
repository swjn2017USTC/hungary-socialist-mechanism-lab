"""Phase 0 contract checks for the input-credit experiment."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from hsm_lab.contract.material import MaterialParameters

ROOT = Path(__file__).resolve().parents[1]


def test_earmark_is_an_explicit_bounded_parameter_with_a_legacy_zero() -> None:
    parameters = MaterialParameters()

    assert parameters.input_credit_earmark_fraction == 0.0
    assert parameters.flatten()["input_credit_earmark_fraction"] == 0.0
    assert (
        MaterialParameters(input_credit_earmark_fraction=1.0).flatten()[
            "input_credit_earmark_fraction"
        ]
        == 1.0
    )
    with pytest.raises(ValidationError):
        MaterialParameters(input_credit_earmark_fraction=1.01)


def test_earmark_registry_classifies_a_structural_design_rule_as_fixed() -> None:
    control = __import__("json").loads((ROOT / "config" / "calibration" / "p05.json").read_text())
    registry = yaml.safe_load((ROOT / "config" / "calibration" / "p05_parameters.yml").read_text())
    entry = next(
        row
        for row in registry["parameters"]
        if row["artifact_id"] == "p05_input_credit_earmark_prior"
    )
    assert entry["variable_id"] == "input_credit_earmark_fraction"
    assert any("structural assumption" in ref for ref in entry["literature_refs"])
    assert control["identification"]["p05_input_credit_earmark_prior"] == "fixed"
    assert control["linkage"] == []
