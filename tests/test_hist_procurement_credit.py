"""H3B: upstream procurement credit, bank approval and settlement closure.

Every fixture is the real kernel and the real finance step; no tick, account,
stock or journal is mocked.  The four-arm 2x2, the 12/10/0 debt counterexample,
priority ordering, scheduled principal, cross-bank reserves, policy rejection,
journal-lender identity and default-off legacy paths are exercised directly.
"""

from __future__ import annotations

import copy
from datetime import date

import numpy as np
import pytest

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.contract.material import RoutePurpose
from hsm_lab.engine import accounting, finance
from hsm_lab.engine.finance import AccountKind, treasury_account_id
from hsm_lab.engine.material import tick_material
from hsm_lab.engine.state import capture_material_stocks
from hsm_lab.institutions.procurement_credit_adapter import (
    CreditLimit,
    ProcurementCreditFailure,
    ProcurementCreditPolicy,
    build_credit_approval_caps,
    execute_procurement_credit_tick,
)
from hsm_lab.measurement import flow_funnel
from tests.test_material import (
    NO_CAPITAL_COMMODITIES,
    Fixture,
    bank,
    default_params,
    producer,
    route,
    tech,
)
from tests.test_material_finance import _case8_parameters, _credit_grant_fixture

# ---------------------------------------------------------------------------
# Fixtures and canonical comparison helpers
# ---------------------------------------------------------------------------


def _credit_parameters():
    """Synthetic 2x2 baseline: no wages, interest, repayment, bailout or trade."""
    base = default_params(
        prices=[1.0] * 8,
        utilization=1.0,
        transport_per_unit=0.0,
        credit_envelope_fraction=1.0,
        principal_repayment_fraction=0.0,
        bailout_envelope_fraction=0.0,
        domestic_credit_rate_annual=0.0,
    )
    return base.model_copy(
        update={
            "wage_rate": 0.0,
            "hunger_base": 0.0,
            "hunger_bailout": 0.0,
            "hunger_shortage": 0.0,
            "capital_depreciation_rate": 0.0,
            "overorder_strength": 0.0,
            "hoarding_quarters": 0.0,
        }
    )


def _two_by_two_fixture(
    *,
    cap: float = 10.0,
    source_open: float = 10.0,
    parameters=None,
) -> Fixture:
    source = producer(1, "energy_generation", capacity=1.0, cash=0.0)
    buyer = producer(2, "consumer_goods_production", capacity=10.0, cash=0.0)
    technologies = [
        tech("energy_generation", outputs=(("energy", "standard", 1.0),)),
        tech(
            "consumer_goods_production",
            inputs=(("energy", 1.0),),
            outputs=(("consumer_goods", "standard", 1.0),),
        ),
    ]
    routes = [
        route(
            1,
            "output",
            "energy",
            "standard",
            2,
            "input",
            "energy",
            "standard",
            RoutePurpose.INTERMEDIATE,
            1.0,
        )
    ]
    fixture = Fixture(
        [bank(0), source, buyer],
        technologies,
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters if parameters is not None else _credit_parameters(),
        households=[(0, 1.0, 1.0)],
        household_cash=0.0,
        routes=routes,
    )
    state = fixture.state
    state.stock_value[:] = 0.0
    state.stock_value[fixture.cell("organization", 1, 0, "output", "energy")] = source_open
    state.stock_value[fixture.cell("organization", 2, 0, "input", "energy")] = 0.0
    state.organization_capacity[1] = 0.0
    state.organization_labor_available[1] = 0.0
    state.organization_cash[:] = 0.0
    state.household_cash[:] = 0.0
    state.bank_reserves[:] = 0.0
    state.bank_equity[:] = 0.0
    state.bank_deposit_liability[:] = 0.0
    state.bank_loan_asset[:] = 0.0
    state.bank_interest_receivable[:] = 0.0
    state.treasury_deposit = 0.0
    state.credit_fund = 0.0
    return fixture


def _policy(
    limits: tuple[CreditLimit, ...],
    *,
    quarter: str = "1957Q1",
    policy_id: str = "h3b-test",
    decision_at: date = date(1957, 1, 1),
    available_at: date = date(1957, 1, 1),
) -> ProcurementCreditPolicy:
    return ProcurementCreditPolicy(
        policy_id=policy_id,
        quarter=quarter,
        decision_at=decision_at,
        available_at=available_at,
        limits=limits,
    )


def _two_by_two_policy(cap: float, *, quarter: str = "1957Q1") -> ProcurementCreditPolicy:
    return _policy(
        (CreditLimit(1, 0, 0.0), CreditLimit(2, 0, cap)),
        quarter=quarter,
    )


def _canonical_state(state) -> dict[str, object]:
    out: dict[str, object] = {}
    for name in state.__dataclass_fields__:
        value = getattr(state, name)
        out[name] = value.tobytes() if isinstance(value, np.ndarray) else value
    return out


def _canonical_flows(flows) -> dict[str, object]:
    out: dict[str, object] = {}
    for name in flows.__dataclass_fields__:
        value = getattr(flows, name)
        if isinstance(value, np.ndarray):
            out[name] = value.tobytes()
        elif isinstance(value, list):
            out[name] = tuple(value)
        else:
            out[name] = value
    return out


def _csr_bytes(network) -> dict[str, bytes]:
    return {
        "A_indptr": network.A.indptr.tobytes(),
        "A_indices": network.A.indices.tobytes(),
        "A_data": network.A.data.tobytes(),
        "B_indptr": network.B.indptr.tobytes(),
        "B_indices": network.B.indices.tobytes(),
        "B_data": network.B.data.tobytes(),
    }


def _assert_gate(result) -> None:
    assert result.gate.max_material_tolerance_ratio <= 1.0
    assert result.gate.max_finance_tolerance_ratio <= 1.0
    assert result.funnel.max_credit_residual <= 1e-6
    assert result.funnel.max_physical_residual <= 1e-6
    assert result.funnel.max_bank_residual <= 1e-6


def _credit_row(result, organization_id: int):
    return next(
        row
        for row in result.funnel.credit_budgets
        if row.organization_id == organization_id
    )


# ---------------------------------------------------------------------------
# 2x2: financing x source stock
# ---------------------------------------------------------------------------


def test_two_by_two_closes_request_approval_payment_delivery_use() -> None:
    source_cell = 0
    observed = {}
    for cap in (0.0, 10.0):
        for source_open in (0.0, 10.0):
            fixture = _two_by_two_fixture(cap=cap, source_open=source_open)
            source_cell = fixture.cell("organization", 1, 0, "output", "energy")
            result = execute_procurement_credit_tick(
                fixture.state,
                fixture.forcing(1),
                fixture.parameters,
                fixture.network,
                policy=_two_by_two_policy(cap),
            )
            _assert_gate(result)
            buyer = _credit_row(result, 2)
            source = _credit_row(result, 1)
            row = result.funnel.inputs[0]
            output = float(
                fixture.state.stock_value[
                    fixture.cell("organization", 2, 0, "output", "consumer_goods")
                ]
            )
            observed[(cap, source_open)] = {
                "buyer": buyer,
                "source": source,
                "input": row,
                "output": output,
                "state": fixture.state,
                "flows": result.flows,
            }

    # cap0/source0: no financing and no stock -> everything is zero.
    arm = observed[(0.0, 0.0)]
    assert arm["buyer"].drawn == 0.0
    assert arm["input"].ordered == 0.0
    assert arm["input"].allocated == 0.0
    assert arm["input"].delivered == 0.0
    assert arm["input"].used == 0.0
    assert arm["input"].upstream_unfunded == pytest.approx(10.0)
    assert arm["output"] == 0.0

    # cap0/source10: stock exists but no approval -> no order, no delivery.
    arm = observed[(0.0, 10.0)]
    assert arm["buyer"].drawn == 0.0
    assert arm["input"].ordered == 0.0
    assert arm["input"].delivered == 0.0
    assert arm["input"].upstream_unfunded == pytest.approx(10.0)
    assert arm["input"].financial_delivery_blocked == 0.0
    assert arm["output"] == 0.0
    assert float(arm["state"].stock_value[source_cell]) == pytest.approx(10.0)

    # cap10/source0: the deposit/loan is created but no material moves.
    arm = observed[(10.0, 0.0)]
    assert arm["buyer"].drawn == pytest.approx(10.0)
    assert arm["input"].ordered == pytest.approx(10.0)
    assert arm["input"].allocated == 0.0
    assert arm["input"].delivered == 0.0
    assert arm["input"].used == 0.0
    assert arm["input"].allocation_gap == pytest.approx(10.0)
    assert arm["output"] == 0.0
    assert float(arm["state"].organization_cash[2]) == pytest.approx(10.0)
    assert float(arm["state"].bank_loan_asset[0]) == pytest.approx(10.0)
    assert float(arm["state"].bank_deposit_liability[0]) == pytest.approx(10.0)

    # cap10/source10: the positive closure.
    arm = observed[(10.0, 10.0)]
    assert arm["buyer"].drawn == pytest.approx(10.0)
    assert arm["input"].ordered == pytest.approx(10.0)
    assert arm["input"].allocated == pytest.approx(10.0)
    assert arm["input"].delivered == pytest.approx(10.0)
    assert arm["input"].used == pytest.approx(10.0)
    assert arm["input"].goods_payment == pytest.approx(10.0)
    assert arm["input"].freight_payment == 0.0
    assert arm["input"].upstream_unfunded == 0.0
    assert arm["input"].allocation_gap == 0.0
    assert arm["input"].financial_delivery_blocked == 0.0
    assert arm["output"] == pytest.approx(10.0)
    assert float(arm["flows"].organization_sales_receipts[1]) == pytest.approx(10.0)
    assert float(arm["flows"].organization_purchases[2]) == pytest.approx(10.0)
    assert float(arm["state"].organization_principal[2]) == pytest.approx(10.0)
    assert float(arm["state"].organization_cash[2]) == pytest.approx(0.0)
    assert float(arm["state"].stock_value[source_cell]) == pytest.approx(0.0)
    assert arm["source"].drawn == 0.0
    assert arm["source"].approval_cap == 0.0


def test_unlisted_enterprises_default_to_zero() -> None:
    fixture = _two_by_two_fixture()
    policy = _policy((CreditLimit(2, 0, 10.0),))
    caps = build_credit_approval_caps(fixture.state, policy)
    assert caps[0] == 0.0  # bank
    assert caps[1] == 0.0  # unlisted source enterprise
    assert caps[2] == pytest.approx(10.0)
    exported = policy.to_dict()
    assert exported["unlisted_default_zero"] is True
    assert exported["source_kind"] == "synthetic"
    assert exported["currency"] == "p02_domestic_currency"


# ---------------------------------------------------------------------------
# 12/10/0 debt counterexample and next-quarter interest
# ---------------------------------------------------------------------------


def test_credit_grant_12_10_0_uses_actual_bank_and_keeps_zero_output() -> None:
    fixture = _credit_grant_fixture()
    params = _case8_parameters(fixture)
    policy = _policy((CreditLimit(1, 0, 12.0),), policy_id="debt-12-10-0")
    result = execute_procurement_credit_tick(
        fixture.state,
        fixture.forcing(1),
        params,
        fixture.network,
        policy=policy,
    )
    _assert_gate(result)
    state = fixture.state
    assert result.flows.organization_credit_drawn[1] == pytest.approx(12.0)
    assert result.flows.organization_wage_paid[1] == pytest.approx(10.0)
    assert state.organization_principal[1] == pytest.approx(12.0)
    assert state.bank_loan_asset[0] == pytest.approx(12.0)
    assert state.bank_deposit_liability[0] == pytest.approx(16.0)
    assert state.bank_reserves[0] == pytest.approx(24.0)
    assert state.bank_equity[0] == pytest.approx(20.0)
    assert float(np.sum(state.household_weight * state.household_cash)) == pytest.approx(10.0)
    assert float(np.sum(state.stock_value)) == pytest.approx(0.0)
    assert state.organization_cash[1] == pytest.approx(2.0)

    credit = _credit_row(result, 1)
    assert credit.drawdown_journal_rows
    for row_index in credit.drawdown_journal_rows:
        journal = result.funnel.journal[row_index]
        owners = {
            (journal.debit_owner_kind, journal.credit_owner_kind),
            (journal.credit_owner_kind, journal.debit_owner_kind),
        }
        assert ("bank_0", "organization") in owners
        assert all(kind != "treasury" for pair in owners for kind in pair)

    # Next quarter: no wages, no new credit, opening principal 12 pays .12.
    idle = params.model_copy(update={"credit_envelope_fraction": 0.0, "wage_rate": 0.0})
    second = execute_procurement_credit_tick(
        state,
        fixture.forcing(2),
        idle,
        fixture.network,
        policy=_policy((CreditLimit(1, 0, 0.0),), quarter="1957Q2", policy_id="debt-q2"),
    )
    _assert_gate(second)
    assert second.flows.organization_interest_due[1] == pytest.approx(0.12)
    assert second.flows.organization_interest_paid[1] == pytest.approx(0.12)
    assert state.organization_interest_arrears[1] == pytest.approx(0.0)
    assert state.bank_interest_receivable[0] == pytest.approx(0.0)
    assert state.bank_equity[0] == pytest.approx(20.12)
    assert second.flows.organization_credit_drawn[1] == 0.0
    assert state.organization_cash[1] == pytest.approx(1.88)
    assert state.organization_principal[1] == pytest.approx(12.0)


# ---------------------------------------------------------------------------
# Priority ordering and scheduled principal
# ---------------------------------------------------------------------------


def _debt_fixture(
    *,
    cash: float,
    principal: float,
    deposits: float,
    reserves: float,
    loan: float,
    equity: float,
    wage_rate: float,
    buyer_capacity: float,
    source_open: float = 10.0,
) -> Fixture:
    parameters = _credit_parameters().model_copy(
        update={
            "wage_rate": wage_rate,
            "domestic_credit_rate_annual": 0.04,
            "principal_repayment_fraction": 1.0,
        }
    )
    fixture = _two_by_two_fixture(
        cap=0.0,
        source_open=source_open,
        parameters=parameters,
    )
    state = fixture.state
    state.organization_cash[2] = cash
    state.organization_principal[2] = principal
    state.organization_capacity[2] = buyer_capacity
    state.organization_labor_available[2] = buyer_capacity
    state.bank_loan_asset[0] = loan
    state.bank_deposit_liability[0] = deposits
    state.bank_reserves[0] = reserves
    state.bank_equity[0] = equity
    return fixture


def test_wage_interest_input_priority_and_principal_juniority() -> None:
    fixture = _debt_fixture(
        cash=12.0,
        principal=12.0,
        deposits=12.0,
        reserves=20.0,
        loan=12.0,
        equity=20.0,
        wage_rate=1.0,
        buyer_capacity=10.0,
    )
    result = execute_procurement_credit_tick(
        fixture.state,
        fixture.forcing(1),
        fixture.parameters,
        fixture.network,
        policy=_two_by_two_policy(0.0),
    )
    _assert_gate(result)
    flows = result.flows
    state = fixture.state
    assert flows.organization_wage_due[2] == pytest.approx(10.0)
    assert flows.organization_wage_paid[2] == pytest.approx(10.0)
    assert flows.organization_interest_due[2] == pytest.approx(0.12)
    assert flows.organization_interest_paid[2] == pytest.approx(0.12)
    assert flows.organization_principal_paid[2] == 0.0
    assert flows.ordered[0] == pytest.approx(1.88)
    assert flows.allocated[0] == pytest.approx(1.88)
    assert flows.delivered[0] == pytest.approx(1.88)
    assert flows.used[0] == pytest.approx(1.88)
    assert state.organization_cash[2] == pytest.approx(0.0)
    assert state.organization_principal[2] == pytest.approx(12.0)
    assert state.bank_deposit_liability[0] == pytest.approx(11.88)
    assert state.bank_loan_asset[0] == pytest.approx(12.0)
    assert state.bank_reserves[0] == pytest.approx(20.0)
    assert state.bank_equity[0] == pytest.approx(20.12)
    output = state.stock_value[
        fixture.cell("organization", 2, 0, "output", "consumer_goods")
    ]
    assert float(output) == pytest.approx(1.88)
    credit = _credit_row(result, 2)
    assert credit.principal_paid == 0.0
    assert credit.principal_unpaid == pytest.approx(12.0)


def test_scheduled_principal_full_payment() -> None:
    fixture = _debt_fixture(
        cash=20.0,
        principal=12.0,
        deposits=20.0,
        reserves=28.0,
        loan=12.0,
        equity=20.0,
        wage_rate=0.0,
        buyer_capacity=0.0,
    )
    result = execute_procurement_credit_tick(
        fixture.state,
        fixture.forcing(1),
        fixture.parameters,
        fixture.network,
        policy=_two_by_two_policy(0.0),
    )
    _assert_gate(result)
    state = fixture.state
    assert result.flows.organization_interest_due[2] == pytest.approx(0.12)
    assert result.flows.organization_principal_paid[2] == pytest.approx(12.0)
    assert state.organization_cash[2] == pytest.approx(7.88)
    assert state.organization_principal[2] == pytest.approx(0.0)
    assert state.bank_deposit_liability[0] == pytest.approx(7.88)
    assert state.bank_loan_asset[0] == pytest.approx(0.0)
    assert state.bank_equity[0] == pytest.approx(20.12)
    assert state.bank_reserves[0] == pytest.approx(28.0)


def test_scheduled_principal_insufficient_cash_is_not_capitalized() -> None:
    fixture = _debt_fixture(
        cash=0.05,
        principal=12.0,
        deposits=0.05,
        reserves=8.05,
        loan=12.0,
        equity=20.0,
        wage_rate=0.0,
        buyer_capacity=0.0,
    )
    result = execute_procurement_credit_tick(
        fixture.state,
        fixture.forcing(1),
        fixture.parameters,
        fixture.network,
        policy=_two_by_two_policy(0.0),
    )
    _assert_gate(result)
    state = fixture.state
    assert result.flows.organization_interest_due[2] == pytest.approx(0.12)
    assert result.flows.organization_interest_paid[2] == pytest.approx(0.05)
    assert state.organization_interest_arrears[2] == pytest.approx(0.07)
    assert result.flows.organization_principal_paid[2] == 0.0
    assert state.organization_principal[2] == pytest.approx(12.0)
    assert state.organization_cash[2] == pytest.approx(0.0)
    assert state.bank_deposit_liability[0] == pytest.approx(0.0)
    assert state.bank_loan_asset[0] == pytest.approx(12.0)
    assert state.bank_reserves[0] == pytest.approx(8.05)
    assert state.bank_equity[0] == pytest.approx(20.12)
    credit = _credit_row(result, 2)
    assert credit.principal_paid == 0.0
    assert credit.principal_unpaid == pytest.approx(12.0)
    assert credit.drawdown_journal_rows == ()


# ---------------------------------------------------------------------------
# Two banks: actual lender and reserve-constrained cross-bank settlement
# ---------------------------------------------------------------------------


def _two_bank_fixture(*, buyer_bank_reserves: float, buyer_bank_equity: float) -> Fixture:
    source = producer(2, "energy_generation", capacity=1.0, cash=0.0, bank_id=1)
    buyer = producer(3, "consumer_goods_production", capacity=10.0, cash=0.0, bank_id=0)
    technologies = [
        tech("energy_generation", outputs=(("energy", "standard", 1.0),)),
        tech(
            "consumer_goods_production",
            inputs=(("energy", 1.0),),
            outputs=(("consumer_goods", "standard", 1.0),),
        ),
    ]
    routes = [
        route(
            2,
            "output",
            "energy",
            "standard",
            3,
            "input",
            "energy",
            "standard",
            RoutePurpose.INTERMEDIATE,
            1.0,
        )
    ]
    fixture = Fixture(
        [bank(0), bank(1), source, buyer],
        technologies,
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=_credit_parameters(),
        households=[(0, 1.0, 1.0)],
        household_cash=0.0,
        routes=routes,
    )
    state = fixture.state
    state.stock_value[:] = 0.0
    state.stock_value[fixture.cell("organization", 2, 0, "output", "energy")] = 10.0
    state.stock_value[fixture.cell("organization", 3, 0, "input", "energy")] = 0.0
    state.organization_capacity[2] = 0.0
    state.organization_labor_available[2] = 0.0
    state.organization_cash[:] = 0.0
    state.household_cash[:] = 0.0
    state.bank_reserves[:] = 0.0
    state.bank_equity[:] = 0.0
    state.bank_deposit_liability[:] = 0.0
    state.bank_loan_asset[:] = 0.0
    state.bank_interest_receivable[:] = 0.0
    state.treasury_deposit = 0.0
    state.credit_fund = 0.0
    state.bank_reserves[0] = buyer_bank_reserves
    state.bank_equity[0] = buyer_bank_equity
    return fixture


def test_cross_bank_settlement_respects_buyer_bank_reserves() -> None:
    policy = _policy((CreditLimit(2, 1, 0.0), CreditLimit(3, 0, 10.0)))

    starved = _two_bank_fixture(buyer_bank_reserves=0.0, buyer_bank_equity=0.0)
    result = execute_procurement_credit_tick(
        starved.state,
        starved.forcing(1),
        starved.parameters,
        starved.network,
        policy=policy,
    )
    _assert_gate(result)
    state = starved.state
    assert result.flows.organization_credit_drawn[3] == pytest.approx(10.0)
    assert result.flows.delivered[0] == 0.0
    assert result.flows.organization_purchases[3] == 0.0
    assert state.organization_cash[3] == pytest.approx(10.0)
    assert state.organization_principal[3] == pytest.approx(10.0)
    assert state.bank_loan_asset[0] == pytest.approx(10.0)
    assert state.bank_deposit_liability[0] == pytest.approx(10.0)
    assert state.bank_reserves[0] == pytest.approx(0.0)
    assert state.bank_deposit_liability[1] == 0.0

    funded = _two_bank_fixture(buyer_bank_reserves=10.0, buyer_bank_equity=10.0)
    result = execute_procurement_credit_tick(
        funded.state,
        funded.forcing(1),
        funded.parameters,
        funded.network,
        policy=policy,
    )
    _assert_gate(result)
    state = funded.state
    assert result.flows.delivered[0] == pytest.approx(10.0)
    assert result.flows.organization_purchases[3] == pytest.approx(10.0)
    assert result.flows.organization_sales_receipts[2] == pytest.approx(10.0)
    assert state.organization_cash[3] == pytest.approx(0.0)
    assert state.organization_cash[2] == pytest.approx(10.0)
    assert state.organization_principal[3] == pytest.approx(10.0)
    assert state.bank_loan_asset[0] == pytest.approx(10.0)
    assert state.bank_deposit_liability[0] == pytest.approx(0.0)
    assert state.bank_reserves[0] == pytest.approx(0.0)
    assert state.bank_deposit_liability[1] == pytest.approx(10.0)
    assert state.bank_reserves[1] == pytest.approx(10.0)
    # Both bank balance sheets close and reserves stay non-negative.
    for bank_index in (0, 1):
        assets = (
            state.bank_reserves[bank_index]
            + state.bank_loan_asset[bank_index]
            + state.bank_interest_receivable[bank_index]
        )
        liabilities = (
            state.bank_deposit_liability[bank_index] + state.bank_equity[bank_index]
        )
        assert assets == pytest.approx(liabilities)
        assert state.bank_reserves[bank_index] >= 0.0
    credit = _credit_row(result, 3)
    assert credit.bank_deposit_liability_account_id != credit.bank_loan_asset_account_id
    assert credit.drawdown_journal_rows


# ---------------------------------------------------------------------------
# Rejection, rollback and identity gates
# ---------------------------------------------------------------------------


def test_policy_rejections_leave_state_unchanged() -> None:
    fixture = _two_by_two_fixture()
    forcing = fixture.forcing(1)
    before = _canonical_state(fixture.state)
    m2 = fixture.parameters.model_copy(update={"m2_neutral_credit": True})

    cases = [
        (_policy((CreditLimit(2, 1, 10.0),)), fixture.parameters),
        (_policy((CreditLimit(99, 0, 10.0),)), fixture.parameters),
        (
            _policy((CreditLimit(2, 0, 10.0), CreditLimit(2, 0, 5.0))),
            fixture.parameters,
        ),
        (
            _policy((CreditLimit(1, 0, 0.0),), quarter="1956Q4"),
            fixture.parameters,
        ),
        (
            _policy(
                (CreditLimit(2, 0, 10.0),),
                decision_at=date(1957, 4, 1),
                available_at=date(1957, 4, 1),
            ),
            fixture.parameters,
        ),
        (_policy((CreditLimit(2, 0, -1.0),)), fixture.parameters),
        (_policy((CreditLimit(2, 0, float("inf")),)), fixture.parameters),
        (_policy((CreditLimit(0, 0, 10.0),)), fixture.parameters),
        (_policy((CreditLimit(2, 0, 10.0),), policy_id=""), fixture.parameters),
        (
            _policy(
                (CreditLimit(2, 0, 10.0),),
                decision_at=date(1957, 1, 1),
                available_at=date(1957, 1, 2),
            ),
            fixture.parameters,
        ),
        (
            ProcurementCreditPolicy(
                policy_id="bad-default",
                quarter="1957Q1",
                decision_at=date(1957, 1, 1),
                available_at=date(1957, 1, 1),
                limits=(CreditLimit(2, 0, 10.0),),
                unlisted_default_zero=False,
            ),
            fixture.parameters,
        ),
        (
            ProcurementCreditPolicy(
                policy_id="historical-claim",
                quarter="1957Q1",
                decision_at=date(1957, 1, 1),
                available_at=date(1957, 1, 1),
                limits=(CreditLimit(2, 0, 10.0),),
                source_kind="historical",
            ),
            fixture.parameters,
        ),
        (
            ProcurementCreditPolicy(
                policy_id="usd-claim",
                quarter="1957Q1",
                decision_at=date(1957, 1, 1),
                available_at=date(1957, 1, 1),
                limits=(CreditLimit(2, 0, 10.0),),
                currency="USD",
            ),
            fixture.parameters,
        ),
        (_policy((CreditLimit(2, 0, 10.0),)), m2),
    ]
    for policy, parameters in cases:
        with pytest.raises(ResearchGateError, match="hist-procurement-credit-v1:"):
            execute_procurement_credit_tick(
                fixture.state,
                forcing,
                parameters,
                fixture.network,
                policy=policy,
            )
        assert _canonical_state(fixture.state) == before
        assert fixture.state.completed_ticks == 0


def test_measurement_failure_rolls_back_and_keeps_failed_diagnostics(monkeypatch) -> None:
    fixture = _two_by_two_fixture()
    before = _canonical_state(fixture.state)

    def _boom(*args, **kwargs):
        raise RuntimeError("synthetic measurement failure")

    monkeypatch.setattr(flow_funnel, "measure_procurement_credit_tick", _boom)
    with pytest.raises(ProcurementCreditFailure) as excinfo:
        execute_procurement_credit_tick(
            fixture.state,
            fixture.forcing(1),
            fixture.parameters,
            fixture.network,
            policy=_two_by_two_policy(10.0),
        )
    failure = excinfo.value
    assert failure.phase == "measurement"
    assert failure.failed_flows is not None
    assert "credit_approval_caps" in failure.failed_trace
    assert isinstance(failure.__cause__, RuntimeError)
    assert _canonical_state(fixture.state) == before
    assert fixture.state.completed_ticks == 0


def _valid_measurement_inputs(fixture: Fixture):
    policy = _two_by_two_policy(10.0)
    caps = build_credit_approval_caps(fixture.state, policy)
    opening = capture_material_stocks(fixture.state)
    trace: dict[str, np.ndarray] = {}
    flows = tick_material(
        fixture.state,
        fixture.forcing(1),
        fixture.parameters,
        fixture.network,
        credit_approval_caps=caps,
        procurement_trace=trace,
    )
    summary = accounting.check_material_invariants(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
    )
    return opening, flows, trace, summary


def test_measurement_rejects_wrong_lender_and_missing_journal_leg() -> None:
    fixture = _two_by_two_fixture()
    opening, flows, trace, summary = _valid_measurement_inputs(fixture)
    funnel = flow_funnel.measure_procurement_credit_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        trace=trace,
        invariants=summary,
    )
    assert funnel.credit_budgets

    wrong = copy.deepcopy(flows)
    drawdown_row = next(
        row
        for row in funnel.journal
        if row.kind == "loan_drawdown" and row.organization_id == 2
    )
    wrong.journal_credit[drawdown_row.row_index] = treasury_account_id(
        fixture.state, AccountKind.CASH_DEPOSIT
    )
    with pytest.raises(ResearchGateError, match="loan_drawdown"):
        flow_funnel.measure_procurement_credit_tick(
            opening,
            fixture.state,
            wrong,
            fixture.parameters,
            fixture.network,
            trace=trace,
            invariants=summary,
        )

    missing = copy.deepcopy(flows)
    dropped = drawdown_row.row_index
    for column in (
        "journal_kind",
        "journal_tick",
        "journal_debit",
        "journal_credit",
        "journal_currency",
        "journal_amount",
        "journal_org",
        "journal_leg",
    ):
        getattr(missing, column).pop(dropped)
    with pytest.raises(ResearchGateError, match="hist-procurement-credit-v1:"):
        flow_funnel.measure_procurement_credit_tick(
            opening,
            fixture.state,
            missing,
            fixture.parameters,
            fixture.network,
            trace=trace,
            invariants=summary,
        )


def test_measurement_rejects_missing_or_misshaped_trace() -> None:
    fixture = _two_by_two_fixture()
    opening, flows, trace, summary = _valid_measurement_inputs(fixture)
    missing = dict(trace)
    del missing["edge_unit_price"]
    with pytest.raises(ResearchGateError, match="missing required key"):
        flow_funnel.measure_procurement_credit_tick(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            trace=missing,
            invariants=summary,
        )
    wrong = dict(trace)
    wrong["input_order_cost"] = np.zeros(1, dtype=np.float64)
    with pytest.raises(ResearchGateError, match="shape"):
        flow_funnel.measure_procurement_credit_tick(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            trace=wrong,
            invariants=summary,
        )


def test_payment_identity_rejects_swapped_purchases_and_missing_goods_journal() -> None:
    fixture = _two_by_two_fixture()
    opening, flows, trace, summary = _valid_measurement_inputs(fixture)

    corrupt = copy.deepcopy(flows)
    corrupt.organization_purchases[[1, 2]] = corrupt.organization_purchases[[2, 1]]
    corrupt_state = copy.deepcopy(fixture.state)
    corrupt_state.organization_cash[[1, 2]] = corrupt_state.organization_cash[[2, 1]]
    with pytest.raises(ResearchGateError, match="organization_purchases_by_buyer"):
        flow_funnel.measure_procurement_credit_tick(
            opening,
            corrupt_state,
            corrupt,
            fixture.parameters,
            fixture.network,
            trace=trace,
            invariants=summary,
        )

    missing = copy.deepcopy(flows)
    goods_rows = [
        row
        for row, kind in enumerate(missing.journal_kind)
        if kind == "goods_payment"
    ]
    for column in (
        "journal_kind",
        "journal_tick",
        "journal_debit",
        "journal_credit",
        "journal_currency",
        "journal_amount",
        "journal_org",
        "journal_leg",
    ):
        values = getattr(missing, column)
        for row in sorted(goods_rows, reverse=True):
            values.pop(row)
    with pytest.raises(ResearchGateError, match="goods_payment journal is missing"):
        flow_funnel.measure_procurement_credit_tick(
            opening,
            fixture.state,
            missing,
            fixture.parameters,
            fixture.network,
            trace=trace,
            invariants=summary,
        )


def test_funnel_rejects_stock_creation_and_missing_stock() -> None:
    fixture = _two_by_two_fixture()
    opening, flows, trace, summary = _valid_measurement_inputs(fixture)
    output_cell = fixture.cell("organization", 2, 0, "output", "consumer_goods")

    created = copy.deepcopy(fixture.state)
    created.stock_value[output_cell] += 1.0
    with pytest.raises(ResearchGateError, match="stock_cell_continuity"):
        flow_funnel.measure_procurement_credit_tick(
            opening,
            created,
            flows,
            fixture.parameters,
            fixture.network,
            trace=trace,
            invariants=summary,
        )

    missing = copy.deepcopy(fixture.state)
    missing.stock_value[output_cell] -= 1.0
    with pytest.raises(ResearchGateError, match="stock_cell_continuity"):
        flow_funnel.measure_procurement_credit_tick(
            opening,
            missing,
            flows,
            fixture.parameters,
            fixture.network,
            trace=trace,
            invariants=summary,
        )


def test_direct_finance_rejects_m2_neutral_with_caps() -> None:
    parameters = _credit_parameters().model_copy(
        update={"m2_neutral_credit": True}
    )
    fixture = _two_by_two_fixture(parameters=parameters)
    flows = tick_material(
        fixture.state,
        fixture.forcing(1),
        fixture.parameters,
        fixture.network,
    )
    caps = build_credit_approval_caps(fixture.state, _two_by_two_policy(10.0))
    before = _canonical_state(fixture.state)
    zeros = np.zeros(3, dtype=np.float64)
    with pytest.raises(ValueError, match="m2_neutral"):
        finance.run_domestic_finance_step(
            fixture.state,
            flows,
            parameters,
            wage_bill_open=zeros,
            input_order_cost=zeros,
            old_project_cost=zeros,
            new_investment_request_cost=zeros,
            transaction_base=0,
            credit_approval_caps=caps,
        )
    assert _canonical_state(fixture.state) == before


def test_small_positive_drawdown_and_principal_keep_their_journals() -> None:
    fixture = _two_by_two_fixture(cap=1e-10, source_open=10.0)
    result = execute_procurement_credit_tick(
        fixture.state,
        fixture.forcing(1),
        fixture.parameters,
        fixture.network,
        policy=_two_by_two_policy(1e-10),
    )
    _assert_gate(result)
    credit = _credit_row(result, 2)
    assert credit.drawn == pytest.approx(1e-10)
    assert credit.drawdown_journal_rows
    assert result.flows.organization_credit_drawn[2] == pytest.approx(1e-10)

    principal_fixture = _debt_fixture(
        cash=1.0,
        principal=1e-10,
        deposits=1.0,
        reserves=1.0,
        loan=1e-10,
        equity=1e-10,
        wage_rate=0.0,
        buyer_capacity=0.0,
    )
    principal_result = execute_procurement_credit_tick(
        principal_fixture.state,
        principal_fixture.forcing(1),
        principal_fixture.parameters,
        principal_fixture.network,
        policy=_two_by_two_policy(0.0),
    )
    _assert_gate(principal_result)
    principal_credit = _credit_row(principal_result, 2)
    assert principal_credit.principal_paid == pytest.approx(1e-10)
    assert principal_credit.principal_journal_rows


def test_direct_tick_rejects_bad_caps_and_trace_before_state_change() -> None:
    fixture = _two_by_two_fixture()
    before = _canonical_state(fixture.state)
    forcing = fixture.forcing(1)
    with pytest.raises(ValueError, match="shape"):
        tick_material(
            fixture.state,
            forcing,
            fixture.parameters,
            fixture.network,
            credit_approval_caps=np.zeros(1),
        )
    with pytest.raises(ValueError, match="negative"):
        tick_material(
            fixture.state,
            forcing,
            fixture.parameters,
            fixture.network,
            credit_approval_caps=np.asarray([0.0, 0.0, -1.0]),
        )
    with pytest.raises(ValueError, match="must be 0"):
        tick_material(
            fixture.state,
            forcing,
            fixture.parameters,
            fixture.network,
            credit_approval_caps=np.asarray([1.0, 0.0, 10.0]),
        )
    with pytest.raises(ValueError, match="empty"):
        tick_material(
            fixture.state,
            forcing,
            fixture.parameters,
            fixture.network,
            credit_approval_caps=np.asarray([0.0, 0.0, 10.0]),
            procurement_trace={"x": np.zeros(1)},
        )
    with pytest.raises(ValueError, match="requires credit_approval_caps"):
        tick_material(
            fixture.state,
            forcing,
            fixture.parameters,
            fixture.network,
            procurement_trace={},
        )
    assert _canonical_state(fixture.state) == before


# ---------------------------------------------------------------------------
# Default-off legacy invariance and read-only measurement
# ---------------------------------------------------------------------------


def test_legacy_defaults_are_byte_identical() -> None:
    plain = _two_by_two_fixture(cap=10.0, source_open=10.0)
    explicit = _two_by_two_fixture(cap=10.0, source_open=10.0)
    plain_flows = tick_material(
        plain.state,
        plain.forcing(1),
        plain.parameters,
        plain.network,
    )
    explicit_flows = tick_material(
        explicit.state,
        explicit.forcing(1),
        explicit.parameters,
        explicit.network,
        credit_approval_caps=None,
        procurement_trace=None,
    )
    assert _canonical_state(plain.state) == _canonical_state(explicit.state)
    assert _canonical_flows(plain_flows) == _canonical_flows(explicit_flows)


def test_measurement_is_read_only_and_does_not_sort_csr() -> None:
    fixture = _two_by_two_fixture()
    opening, flows, trace, summary = _valid_measurement_inputs(fixture)
    before_state = _canonical_state(fixture.state)
    before_flows = _canonical_flows(flows)

    # Deliberately reverse the entries of two multi-entry CSR rows.
    for matrix in (fixture.network.A, fixture.network.B):
        lengths = np.diff(matrix.indptr)
        row = int(np.flatnonzero(lengths > 1)[0])
        start, end = int(matrix.indptr[row]), int(matrix.indptr[row + 1])
        matrix.indices[start:end] = matrix.indices[start:end][::-1]
        matrix.data[start:end] = matrix.data[start:end][::-1]
    before_csr = _csr_bytes(fixture.network)

    flow_funnel.measure_procurement_credit_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        trace=trace,
        invariants=summary,
    )
    assert _canonical_state(fixture.state) == before_state
    assert _canonical_flows(flows) == before_flows
    assert _csr_bytes(fixture.network) == before_csr


def test_empty_real_input_axis_returns_empty_tuples() -> None:
    producer_org = producer(1, "energy_generation", capacity=10.0, cash=0.0)
    fixture = Fixture(
        [bank(0), producer_org],
        [tech("energy_generation", outputs=(("energy", "standard", 1.0),))],
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=_credit_parameters(),
        households=[(0, 1.0, 1.0)],
        household_cash=0.0,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.organization_cash[:] = 0.0
    fixture.state.bank_reserves[:] = 0.0
    fixture.state.bank_equity[:] = 0.0
    fixture.state.bank_deposit_liability[:] = 0.0
    result = execute_procurement_credit_tick(
        fixture.state,
        fixture.forcing(1),
        fixture.parameters,
        fixture.network,
        policy=_policy((CreditLimit(1, 0, 0.0),)),
    )
    _assert_gate(result)
    assert result.funnel.inputs == ()
    assert result.funnel.edges == ()
    assert result.funnel.credit_budgets
