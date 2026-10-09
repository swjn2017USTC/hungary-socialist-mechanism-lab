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


def test_full_interest_remittance_routes_paid_interest_without_money_creation() -> None:

    from hsm_lab.engine import accounting
    from hsm_lab.engine.material import tick_material
    from hsm_lab.engine.state import capture_material_stocks
    from tests.test_material_finance import _case8_parameters, _credit_grant_fixture

    for recipient in ("treasury", "households"):
        fixture = _credit_grant_fixture()
        base = _case8_parameters(fixture)
        tick_material(fixture.state, fixture.forcing(1), base, fixture.network)
        opening = capture_material_stocks(fixture.state)
        parameters = base.model_copy(
            update={
                "credit_envelope_fraction": 0.0,
                "wage_rate": 0.0,
                "interest_sink_remittance_fraction": 1.0,
                "interest_sink_recipient": recipient,
            }
        )
        flows = tick_material(fixture.state, fixture.forcing(1), parameters, fixture.network)
        assert flows.organization_interest_paid[1] == pytest.approx(0.12)
        assert "organization_interest_remitted" not in vars(flows)
        assert "interest_recipient_deposit" in flows.journal_kind
        assert fixture.state.bank_deposit_liability[0] == pytest.approx(16.0)
        assert fixture.state.bank_interest_receivable[0] == pytest.approx(0.0)
        assert fixture.state.bank_equity[0] == pytest.approx(20.0)
        if recipient == "treasury":
            assert fixture.state.treasury_deposit == pytest.approx(4.12)
            assert fixture.state.household_cash[0] == pytest.approx(10.0)
        else:
            assert fixture.state.treasury_deposit == pytest.approx(4.0)
            assert fixture.state.household_cash[0] == pytest.approx(10.12)
        summary = accounting.check_material_invariants(
            opening, fixture.state, flows, parameters, fixture.network
        )
        assert summary.max_finance_tolerance_ratio <= 1.0


def test_turnover_transfer_uses_only_cash_left_after_goods_payments() -> None:
    from hsm_lab.engine import accounting, finance
    from hsm_lab.engine.material import tick_material
    from tests.test_material_finance import _case8_parameters, _credit_grant_fixture

    fixture = _credit_grant_fixture()
    parameters = _case8_parameters(fixture)
    flows = tick_material(fixture.state, fixture.forcing(1), parameters, fixture.network)
    # Prepare an explicit closing-cash edge: sales receipts exceed cash left after
    # wages and goods, so the junior remittance must be limited to available cash.
    fixture.state.organization_cash[1] = 2.0
    fixture.state.treasury_deposit = 4.0
    flows.organization_sales_receipts[1] = 20.0
    transfer_parameters = parameters.model_copy(
        update={"fiscal_turnover_remittance_fraction": 0.5}
    )

    remitted = finance.run_fiscal_turnover_remittance(
        fixture.state, flows, transfer_parameters
    )

    assert remitted == pytest.approx(2.0)
    assert fixture.state.organization_cash[1] == pytest.approx(0.0)
    assert fixture.state.treasury_deposit == pytest.approx(6.0)
    assert fixture.state.bank_deposit_liability[0] == pytest.approx(16.0)
    assert fixture.state.bank_reserves[0] == pytest.approx(24.0)
    assert accounting._check_journal(flows, flows.quarter)[0].size > 0
