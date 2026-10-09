"""Phase 0 contract checks for the input-credit experiment."""

from pathlib import Path

import numpy as np
import pytest
import yaml
from pydantic import ValidationError

from hsm_lab.contract.material import MaterialParameters
from hsm_lab.engine import finance
from tests.test_material_finance import _credit_grant_fixture

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


def test_full_earmark_adds_exact_input_goods_budget_without_flow_schema_change() -> None:
    fixture = _credit_grant_fixture()
    flows = fixture.tick(1)[0]
    fixture.state.organization_cash[:] = 0.0
    fixture.state.organization_principal[:] = 0.0
    fixture.state.organization_interest_arrears[:] = 0.0
    parameters = fixture.parameters.model_copy(
        update={
            "wage_rate": 0.0,
            "credit_envelope_fraction": 0.0,
            "input_credit_earmark_fraction": 1.0,
        }
    )
    result = finance.run_domestic_finance_step(
        fixture.state,
        flows,
        parameters,
        wage_bill_open=np.zeros_like(fixture.state.organization_cash),
        input_order_cost=np.array([0.0, 10.0]),
        old_project_cost=np.zeros_like(fixture.state.organization_cash),
        new_investment_request_cost=np.zeros_like(fixture.state.organization_cash),
        transaction_base=100_000,
    )
    assert result["input_credit_earmarked"][1] == pytest.approx(10.0)
    assert result["cash_available_for_goods"][1] == pytest.approx(10.0)
    assert "input_credit_earmarked" not in vars(flows)
