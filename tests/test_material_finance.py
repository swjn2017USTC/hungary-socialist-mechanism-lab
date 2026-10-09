"""P02 material finance: defaults, bank/capacity/housing invariants, rescue.

Fixtures use the real kernel (``tick_material``) and the real finance step
functions; nothing here mocks the engine.
"""

from __future__ import annotations

import numpy as np
import pytest

from hsm_lab.contract.material import (
    P02_COMMODITY_IDS,
    MaterialParameters,
)
from hsm_lab.engine import accounting, finance
from hsm_lab.engine.accounting import ATOL
from hsm_lab.engine.material import tick_material
from hsm_lab.engine.state import capture_material_stocks
from tests.test_material import (
    NO_CAPITAL_COMMODITIES,
    Fixture,
    bank,
    default_params,
    idle_source_tech,
    producer,
    tech,
)

# Intermediate-8 minus capital_goods: a housing fixture declares construction
# but has no capital-goods producer, so the capital axis is omitted.
CONSTRUCTION_COMMODITIES = tuple(c for c in P02_COMMODITY_IDS if c != "capital_goods")


def test_default_parameters_disable_overorder_and_hoarding() -> None:
    defaults = MaterialParameters()
    assert defaults.overorder_strength == 0.0
    assert defaults.hoarding_quarters == 0.0

    source = producer(1, "energy_generation", capacity=1.0)
    buyer = producer(2, "consumer_goods_production", capacity=8.0)
    technologies = [
        idle_source_tech("energy_generation", "energy"),
        tech(
            "consumer_goods_production",
            inputs=(("energy", 1.0),),
            outputs=(("consumer_goods", "standard", 1.0),),
        ),
    ]
    fixture = Fixture([bank(0), source, buyer], technologies, commodities=NO_CAPITAL_COMMODITIES)
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "output", "energy")] = 100.0
    fixture.state.stock_value[fixture.cell("organization", 2, 0, "input", "energy")] = 2.0
    flows = fixture.tick(1)[0]
    k = fixture.k_of(fixture.cell("organization", 2, 0, "input", "energy"))

    assert flows.desired[k] == pytest.approx(8.0)
    # projected-closing rule: the 2 opening units are consumed this quarter, so
    # the full replacement pipeline is ordered (not desired - opening).
    assert flows.ordered[k] == pytest.approx(8.0)
    assert flows.delivered[k] == pytest.approx(8.0)
    assert flows.used[k] == pytest.approx(8.0)


def test_bank_balance_sheet_identity_and_non_negative_reserves() -> None:
    technologies = [idle_source_tech("energy_generation", "energy")]
    first = producer(2, "energy_generation", capacity=10.0, cash=0.0, bank_id=0)
    second = producer(3, "energy_generation", capacity=10.0, cash=1000.0, bank_id=1)
    fixture = Fixture(
        [bank(0), bank(1), first, second],
        technologies,
        commodities=NO_CAPITAL_COMMODITIES,
    )
    fixture.tick(2)

    state = fixture.state
    assets = (
        np.asarray(state.bank_reserves)
        + np.asarray(state.bank_loan_asset)
        + np.asarray(state.bank_interest_receivable)
    )
    liabilities = np.asarray(state.bank_deposit_liability) + np.asarray(state.bank_equity)
    assert np.allclose(assets, liabilities, atol=1e-9)
    assert np.all(np.asarray(state.bank_reserves) >= -ATOL)
    # the cash-poor producer had to borrow; the solvent one did not
    assert state.organization_principal[2] > 0.0
    assert state.organization_principal[3] == pytest.approx(0.0)


def test_capacity_and_dwelling_unchanged_without_investment_or_housing() -> None:
    source = producer(1, "energy_generation", capacity=1.0)
    buyer = producer(2, "consumer_goods_production", capacity=8.0)
    technologies = [
        idle_source_tech("energy_generation", "energy"),
        tech(
            "consumer_goods_production",
            inputs=(("energy", 1.0),),
            outputs=(("consumer_goods", "standard", 1.0),),
        ),
    ]
    fixture = Fixture([bank(0), source, buyer], technologies, commodities=NO_CAPITAL_COMMODITIES)
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "output", "energy")] = 10.0
    capacity_open = np.asarray(fixture.state.organization_capacity).copy()
    dwelling_open = np.asarray(fixture.state.dwelling_stock).copy()
    flows = fixture.tick(1)[0]

    assert np.array_equal(fixture.state.organization_capacity, capacity_open)
    assert np.array_equal(fixture.state.dwelling_stock, dwelling_open)
    assert np.all(np.asarray(fixture.state.organization_capacity) >= 0.0)
    assert np.all(flows.organization_investment_completed == 0.0)


def test_housing_delivery_only_adds_dwelling() -> None:
    energy = producer(1, "energy_generation", capacity=5.0)
    builder = producer(2, "building_construction", capacity=5.0)
    technologies = [
        idle_source_tech("energy_generation", "energy"),
        tech(
            "building_construction",
            inputs=(("energy", 1.0),),
            outputs=(("construction", "standard", 1.0),),
        ),
    ]
    parameters = default_params(housing_request_per_person=1.0)
    fixture = Fixture(
        [bank(0), energy, builder],
        technologies,
        commodities=CONSTRUCTION_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 1.0)],
        ticks=1,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "output", "energy")] = 5.0
    fixture.state.stock_value[fixture.cell("organization", 2, 0, "output", "construction")] = 5.0
    dwelling_open = float(fixture.state.dwelling_stock[0])
    capacity_open = float(fixture.state.organization_capacity[2])
    flows = fixture.tick(1)[0]

    # P03 housing request is the access gap: access 0.4 vs desired 1.0 = 0.6.
    housing_demand = int(np.flatnonzero(np.asarray(fixture.network.demand_purpose) == 2)[0])
    assert flows.used[housing_demand] == pytest.approx(0.6)
    assert float(fixture.state.dwelling_stock[0]) - dwelling_open == pytest.approx(0.6)
    # housing is not physical capacity for the builder
    assert fixture.state.organization_capacity[2] == pytest.approx(capacity_open)


def _rescue_fixture(*, treasury: float):
    worker = producer(1, "energy_generation", capacity=100.0, cash=0.0)
    technologies = [idle_source_tech("energy_generation", "energy")]
    fixture = Fixture([bank(0), worker], technologies, commodities=NO_CAPITAL_COMMODITIES)
    flows = fixture.tick(1)[0]
    # set up a controlled second rescue pass on the real kernel-produced flows
    fixture.state.organization_wage_arrears[1] = 10.0
    fixture.state.organization_interest_arrears[1] = 0.0
    fixture.state.organization_bailout_expectation[1] = 0.5
    fixture.state.treasury_deposit = treasury
    return fixture, flows


def test_bailout_expectation_updates_with_rescued_fraction() -> None:
    fixture, flows = _rescue_fixture(treasury=100.0)
    parameters = fixture.parameters.model_copy(
        update={"bailout_envelope_fraction": 1.0, "bailout_alpha": 0.25}
    )
    capacity_open = float(fixture.state.organization_capacity[1])
    requested, granted = finance.run_bailout_step(
        fixture.state,
        flows,
        parameters,
        opening_wage_bill=10.0,
        transaction_base=200,
    )
    assert requested[1] == pytest.approx(10.0)
    assert granted[1] == pytest.approx(10.0)  # full rescue
    assert fixture.state.organization_bailout_expectation[1] == pytest.approx(0.625)
    # rescue is liquidity only: no capacity is created
    assert fixture.state.organization_capacity[1] == pytest.approx(capacity_open)

    starved, starved_flows = _rescue_fixture(treasury=0.0)
    parameters = starved.parameters.model_copy(
        update={"bailout_envelope_fraction": 1.0, "bailout_alpha": 0.25}
    )
    _, granted = finance.run_bailout_step(
        starved.state,
        starved_flows,
        parameters,
        opening_wage_bill=10.0,
        transaction_base=300,
    )
    assert granted[1] == pytest.approx(0.0)
    assert starved.state.organization_bailout_expectation[1] == pytest.approx(0.375)


def test_hunger_request_scales_with_bailout_expectation() -> None:
    def request_for(expectation: float) -> float:
        worker = producer(1, "energy_generation", capacity=100.0)
        fixture = Fixture(
            [bank(0), worker],
            [idle_source_tech("energy_generation", "energy")],
            commodities=NO_CAPITAL_COMMODITIES,
            parameters=default_params(hunger_base=0.02, hunger_bailout=0.05, hunger_shortage=0.05),
        )
        fixture.state.organization_bailout_expectation[1] = expectation
        fixture.state.organization_shortage_expectation[1] = 0.0
        flows = fixture.tick(1)[0]
        return float(flows.organization_investment_requested[1])

    assert request_for(0.0) == pytest.approx(2.0)  # 0.02 * 100
    assert request_for(1.0) == pytest.approx(7.0)  # (0.02 + 0.05) * 100


# ---------------------------------------------------------------------------
# Bottleneck fixture 8: credit/grant/debt/wage counterpart closure
# ---------------------------------------------------------------------------


def _credit_grant_fixture() -> Fixture:
    """Plan §8 case 8.

    Treasury deposit 4, bank reserves 24, bank equity 20, no loan asset: the
    deposit liability is exactly the Treasury's 4.  The single borrower opens
    with zero cash and a 10-unit wage bill (wage_rate 1 x labor 10), and its
    only input (durable goods) has no supplier, so it produces nothing and no
    grant can create material.
    """
    worker = producer(1, "energy_generation", capacity=10.0, cash=0.0)
    fixture = Fixture(
        [bank(0), worker],
        [idle_source_tech("energy_generation", "energy")],
        commodities=NO_CAPITAL_COMMODITIES,
        households=[(0, 1.0, 1.0)],
        household_cash=0.0,
    )
    state = fixture.state
    state.stock_value[:] = 0.0
    state.treasury_deposit = 4.0
    state.bank_reserves[:] = 24.0
    state.bank_equity[:] = 20.0
    state.bank_loan_asset[:] = 0.0
    state.bank_deposit_liability[:] = 4.0
    state.organization_cash[:] = 0.0
    return fixture


def _case8_parameters(fixture: Fixture) -> MaterialParameters:
    return fixture.parameters.model_copy(
        update={"credit_envelope_fraction": 0.6, "bailout_envelope_fraction": 0.4}
    )


def test_credit_grant_debt_and_wage_counterpart() -> None:
    fixture = _credit_grant_fixture()
    params = _case8_parameters(fixture)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(fixture.state, fixture.forcing(1), params, fixture.network)
    state = fixture.state

    # P05 §0.5: the credit envelope is now sized to the bank's quarterly
    # financing need (wages + input orders + investment), so the 0.6 envelope
    # funds the full wage bill instead of leaving arrears.
    assert flows.organization_wage_due[1] == pytest.approx(10.0)
    assert flows.organization_credit_approved[1] == pytest.approx(12.0)
    assert flows.organization_credit_drawn[1] == pytest.approx(12.0)
    assert flows.organization_wage_paid[1] == pytest.approx(10.0)
    # No arrears remain, so no rescue is requested or granted.
    assert flows.organization_bailout_requested[1] == pytest.approx(0.0)
    assert flows.organization_bailout_granted[1] == pytest.approx(0.0)
    assert flows.household_late_wage[0] == pytest.approx(0.0)
    assert state.household_deferred_receipt[0] == pytest.approx(0.0)
    assert state.organization_wage_arrears[1] == pytest.approx(0.0)
    assert state.household_wage_claim[0] == pytest.approx(0.0)
    # Closing counterpart identities: every dollar of HH cash is a bank
    # deposit and the borrower still owes the full drawdown.
    assert float(np.sum(state.household_weight * state.household_cash)) == pytest.approx(10.0)
    assert state.organization_principal[1] == pytest.approx(12.0)
    assert state.bank_deposit_liability[0] == pytest.approx(16.0)
    assert state.bank_reserves[0] == pytest.approx(24.0)
    assert state.bank_loan_asset[0] == pytest.approx(12.0)
    assert state.bank_equity[0] == pytest.approx(20.0)
    assert (state.bank_reserves[0] + state.bank_loan_asset[0]) == pytest.approx(
        state.bank_deposit_liability[0] + state.bank_equity[0]
    )
    assert state.bank_reserves[0] + state.bank_loan_asset[0] == pytest.approx(36.0)
    # the grant neither forgives principal nor creates material stock
    assert state.stock_value.sum() == pytest.approx(0.0)
    summary = accounting.check_material_invariants(opening, state, flows, params, fixture.network)
    assert summary.max_finance_tolerance_ratio <= 1.0

    # Next quarter: no new credit and no wage bill isolate interest.  Opening
    # principal 12 at the .04 annual rate is .12 due, paid from residual cash.
    idle = params.model_copy(update={"credit_envelope_fraction": 0.0, "wage_rate": 0.0})
    opening_two = capture_material_stocks(state)
    flows_two = tick_material(state, fixture.forcing(1), idle, fixture.network)
    assert finance.quarter_domestic_credit_rate(idle) == pytest.approx(0.01)
    assert flows_two.organization_interest_due[1] == pytest.approx(0.12)
    assert flows_two.organization_interest_paid[1] == pytest.approx(0.12)
    assert state.organization_interest_arrears[1] == pytest.approx(0.0)
    assert state.bank_interest_receivable[0] == pytest.approx(0.0)
    assert state.bank_equity[0] == pytest.approx(20.12)
    assert flows_two.organization_credit_approved[1] == pytest.approx(0.0)
    assert flows_two.organization_bailout_granted[1] == pytest.approx(0.0)
    assert state.organization_cash[1] == pytest.approx(1.88)
    assert state.organization_principal[1] == pytest.approx(12.0)
    assert float(np.sum(state.household_weight * state.household_cash)) == pytest.approx(10.0)
    summary_two = accounting.check_material_invariants(
        opening_two, state, flows_two, idle, fixture.network
    )
    assert summary_two.max_finance_tolerance_ratio <= 1.0


def test_missing_journal_counterpart_leg_is_rejected() -> None:
    fixture = _credit_grant_fixture()
    params = _case8_parameters(fixture)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(fixture.state, fixture.forcing(1), params, fixture.network)
    summary = accounting.check_material_invariants(
        opening, fixture.state, flows, params, fixture.network
    )
    assert summary.max_finance_tolerance_ratio <= 1.0

    # A transaction that lost a counterpart leg must fail the admitted-tick
    # gate rather than close the quarter.
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
        getattr(flows, column).pop()
    with pytest.raises(accounting.AccountingError, match="journal"):
        accounting.check_material_invariants(opening, fixture.state, flows, params, fixture.network)
