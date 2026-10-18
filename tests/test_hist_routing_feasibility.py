"""H3C: explicit routing feasibility, execution and reconciliation tests.

Every fixture is the real compiled material network and the real
``tick_material`` kernel; no solver result, stock cell, journal or account is
mocked.  The test matrix covers the frozen-plan counterexamples, the three
nested levels, projection gaps, source/service sharing, funding preludes,
bank reserves, journal tampering, rollback and nested-hash rejection.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib

import numpy as np
import pytest

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.contract.material import PURPOSE_CODES, OrganizationType, RoutePurpose
from hsm_lab.engine.material import tick_material
from hsm_lab.engine.network import MaterialNetwork
from hsm_lab.engine.state import capture_material_stocks
from hsm_lab.measurement.plan_execution import (
    RoutingExecutionFailure,
    execute_routing_certificate,
    measure_routing_execution,
)
from hsm_lab.planning import feasibility
from tests.test_material import (
    NO_CAPITAL_COMMODITIES,
    Fixture,
    _mixed_energy_fixture,
    _transport_fixture,
    _transport_hub_edge,
    bank,
    default_params,
    hub,
    org,
    producer,
    tech,
)

_EDGE_FIELDS = (
    "edge_source_cell",
    "edge_destination_cell",
    "edge_demand",
    "edge_commodity",
    "edge_stage",
    "edge_purpose",
    "edge_weight",
    "edge_transport_org",
    "edge_transport_per_unit",
    "edge_buyer_org",
    "edge_self_hauled",
    "edge_is_fallback",
    "edge_transport_service_cell",
    "edge_distance",
    "edge_id",
)


def _no_credit(parameters):
    return parameters.model_copy(
        update={"credit_envelope_fraction": 0.0, "input_credit_earmark_fraction": 0.0}
    )


def _demand_for(fixture: Fixture, edge: int, quantity: float) -> np.ndarray:
    demand = np.zeros(len(fixture.network.demand_cell), dtype=np.float64)
    demand[int(fixture.network.edge_demand[edge])] = float(quantity)
    return demand


def _remove_edge(network: MaterialNetwork, edge: int) -> MaterialNetwork:
    keep = np.arange(int(network.edge_source_cell.shape[0])) != int(edge)
    changes = {}
    for field in _EDGE_FIELDS:
        value = getattr(network, field)
        if isinstance(value, np.ndarray) and value.shape[:1] == (keep.size,):
            changes[field] = value[keep]
    return dataclasses.replace(network, **changes)


def _append_edge(
    network: MaterialNetwork,
    template: int,
    *,
    source: int,
    destination: int,
    demand: int,
    purpose: int,
    buyer_org: int,
    transport_org: int,
) -> MaterialNetwork:
    changes = {}
    for field in _EDGE_FIELDS:
        value = getattr(network, field)
        if field == "edge_id":
            row = np.asarray([int(value.max()) + 1], dtype=value.dtype)
        elif field == "edge_source_cell":
            row = np.asarray([source], dtype=value.dtype)
        elif field == "edge_destination_cell":
            row = np.asarray([destination], dtype=value.dtype)
        elif field == "edge_demand":
            row = np.asarray([demand], dtype=value.dtype)
        elif field == "edge_commodity":
            row = np.asarray([int(network.cell_commodity[source])], dtype=value.dtype)
        elif field == "edge_stage":
            row = np.asarray([int(network.cell_stage[source])], dtype=value.dtype)
        elif field == "edge_purpose":
            row = np.asarray([purpose], dtype=value.dtype)
        elif field == "edge_weight":
            row = np.asarray([1.0], dtype=value.dtype)
        elif field == "edge_transport_org":
            row = np.asarray([transport_org], dtype=value.dtype)
        elif field == "edge_transport_per_unit":
            row = np.asarray([float(value[template])], dtype=value.dtype)
        elif field == "edge_buyer_org":
            row = np.asarray([buyer_org], dtype=value.dtype)
        elif field == "edge_self_hauled":
            row = np.asarray([transport_org < 0], dtype=value.dtype)
        elif field == "edge_is_fallback":
            row = np.asarray([False], dtype=value.dtype)
        elif field == "edge_transport_service_cell":
            row = np.asarray(
                [int(network.org_output_cell[transport_org]) if transport_org >= 0 else -1],
                dtype=value.dtype,
            )
        elif field == "edge_distance":
            row = np.asarray([float(value[template])], dtype=value.dtype)
        else:  # pragma: no cover - exhaustive edge field list
            raise AssertionError(field)
        changes[field] = np.concatenate([value, row])
    return dataclasses.replace(network, **changes)


def _digest_state_flows(state, flows) -> str:
    digest = hashlib.sha256()
    for field in state.__dataclass_fields__:
        value = getattr(state, field)
        if isinstance(value, np.ndarray):
            digest.update(field.encode("utf-8"))
            digest.update(np.ascontiguousarray(value).tobytes())
    for field in flows.__dataclass_fields__:
        value = getattr(flows, field)
        if isinstance(value, np.ndarray):
            digest.update(field.encode("utf-8"))
            digest.update(np.ascontiguousarray(value).tobytes())
        elif isinstance(value, list):
            digest.update(field.encode("utf-8"))
            digest.update(repr(value).encode("utf-8"))
    return digest.hexdigest()


def _capture_boundary(fixture: Fixture, demand: np.ndarray) -> dict:
    holder: dict = {}

    def allocator(boundary):
        holder["boundary"] = boundary
        raise RuntimeError("capture only")

    with pytest.raises(RuntimeError, match="capture only"):
        tick_material(
            fixture.state,
            fixture.forcing(1),
            fixture.parameters,
            fixture.network,
            routing_allocator=allocator,
        )
    return holder["boundary"]


def _solved(boundary, demand):
    problem = feasibility.build_routing_problem(boundary, demand=demand)
    certificates = {
        level: feasibility.solve_routing_feasibility(problem, level=level, time_limit_s=10)
        for level in feasibility.LEVELS
    }
    return problem, certificates


def _execute(fixture, demand, level="LP-2", **kwargs):
    return execute_routing_certificate(
        fixture.state,
        fixture.forcing(1),
        fixture.parameters,
        fixture.network,
        level=level,
        demand=demand,
        time_limit_s=10,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 1. Legacy counterexample and positive executable witness
# ---------------------------------------------------------------------------


def test_transport_opening_zero_is_relaxation_only_and_partial_lp1_lp2() -> None:
    frozen = _transport_fixture(transport_opening=0.0)
    edge = _transport_hub_edge(frozen)
    demand_index = int(frozen.network.edge_demand[edge])
    demand = _demand_for(frozen, edge, 10.0)
    legacy = frozen.tick(1)[0]
    assert legacy.edge_allocated[edge] == pytest.approx(10.0)
    assert legacy.edge_delivered[edge] == pytest.approx(0.0)
    assert legacy.edge_service_used[edge] == pytest.approx(0.0)
    assert legacy.edge_service_fee[edge] == pytest.approx(0.0)

    relaxed = _execute(_transport_fixture(transport_opening=0.0), demand, level="LP-0")
    assert relaxed.execution_status == "RELAXATION_ONLY"
    assert relaxed.actual_delivered[edge] == pytest.approx(0.0)
    assert relaxed.measurement.max_delivery_gap > 0.0

    for level in ("LP-1", "LP-2"):
        partial = _execute(
            _transport_fixture(transport_opening=0.0), demand, level=level
        )
        assert partial.selected_certificate.shortfall_total == pytest.approx(10.0)
        assert partial.actual_delivered[edge] == pytest.approx(0.0)
        assert partial.measurement.max_shortfall_residual == pytest.approx(0.0)
        if level == "LP-2":
            assert partial.execution_status == "PARTIAL"
            assert partial.selected_certificate.shortfall[demand_index] == pytest.approx(10.0)


def test_positive_witness_executes_goods_and_freight_exactly() -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    edge = _transport_hub_edge(fixture)
    demand = _demand_for(fixture, edge, 10.0)
    result = _execute(fixture, demand, level="LP-2")
    assert result.execution_status == "EXECUTED"
    assert result.selected_certificate.shortfall_total == pytest.approx(0.0)
    assert fixture.state.completed_ticks == 1
    assert result.actual_delivered[edge] == pytest.approx(10.0)
    assert result.flows.edge_service_used[edge] == pytest.approx(1.0)
    fee = float(result.flows.edge_service_fee[edge])
    assert fee > 0.0
    assert result.flows.organization_sales_receipts[1] == pytest.approx(10.0)
    assert result.flows.organization_sales_receipts[4] == pytest.approx(fee)
    assert result.flows.organization_purchases[2] == pytest.approx(10.0 + fee)
    assert result.measurement.max_edge_gap == pytest.approx(0.0)
    assert result.measurement.max_delivery_gap == pytest.approx(0.0)
    assert result.nested.nested is True


# ---------------------------------------------------------------------------
# 2. A broken unique edge: LP-0 free flow, LP-1/2 infeasible
# ---------------------------------------------------------------------------


def test_broken_unique_edge_is_free_only_in_lp0() -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    edge = _transport_hub_edge(fixture)
    demand_index = int(fixture.network.edge_demand[edge])
    broken_network = _remove_edge(fixture.network, edge)
    demand = np.zeros(len(fixture.network.demand_cell))
    demand[demand_index] = 10.0
    holder: dict = {}

    def allocator(b):
        holder["boundary"] = b
        raise RuntimeError("stop")

    with pytest.raises(RuntimeError, match="stop"):
        tick_material(
            fixture.state,
            fixture.forcing(1),
            fixture.parameters,
            broken_network,
            routing_allocator=allocator,
        )
    problem, certificates = _solved(holder["boundary"], demand)
    assert certificates["LP-0"].status == "FEASIBLE"
    assert certificates["LP-0"].free_flow is True
    assert certificates["LP-0"].shortfall_total == pytest.approx(0.0)
    for level in ("LP-1", "LP-2"):
        assert certificates[level].status == "FEASIBLE"
        assert certificates[level].x.sum() == pytest.approx(0.0)
        assert certificates[level].shortfall_total == pytest.approx(10.0)
    assert problem.edge_source.shape[0] == int(fixture.network.edge_source_cell.shape[0]) - 1
    attempt_fixture = _transport_fixture(transport_opening=1.0)
    attempt_fixture.network = _remove_edge(attempt_fixture.network, edge)
    attempt = _execute(
        attempt_fixture,
        demand,
        level="LP-0",
        certificate=certificates["LP-0"],
    )
    assert attempt.execution_status == "RELAXATION_ONLY"
    assert float(np.sum(attempt.actual_delivered)) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 3. Capacity vs logistics pool and shared source/service constraints
# ---------------------------------------------------------------------------


def test_zero_carrier_capacity_and_zero_logistics_pool_both_block_lp1() -> None:
    for opening, capacity in ((0.0, 1.0), (1.0, 0.0)):
        fixture = _transport_fixture(transport_opening=opening)
        edge = _transport_hub_edge(fixture)
        fixture.state.organization_capacity[4] = capacity
        demand = _demand_for(fixture, edge, 10.0)
        _, certificates = _solved(_capture_boundary(fixture, demand), demand)
        assert certificates["LP-0"].status == "FEASIBLE"
        assert certificates["LP-0"].shortfall_total == pytest.approx(0.0)
        for level in ("LP-1", "LP-2"):
            assert certificates[level].status == "FEASIBLE"
            assert certificates[level].shortfall_total == pytest.approx(10.0)
        attempt_fixture = _transport_fixture(transport_opening=opening)
        attempt_fixture.state.organization_capacity[4] = capacity
        attempt = _execute(
            attempt_fixture,
            demand,
            level="LP-0",
            certificate=certificates["LP-0"],
        )
        assert attempt.execution_status == "RELAXATION_ONLY"
        assert float(np.sum(attempt.actual_delivered)) == pytest.approx(0.0)


def test_two_demands_share_source_and_carrier_without_overcommitment() -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    source_cell = fixture.cell("organization", 1, 1, "output", "energy")
    hub_edge = _transport_hub_edge(fixture)
    retail_edges = np.flatnonzero(
        fixture.network.edge_purpose == PURPOSE_CODES[RoutePurpose.RETAIL]
    )
    assert retail_edges.size
    retail_edge = int(retail_edges[0])
    shared_network = _append_edge(
        fixture.network,
        hub_edge,
        source=source_cell,
        destination=int(fixture.network.edge_destination_cell[retail_edge]),
        demand=int(fixture.network.edge_demand[retail_edge]),
        purpose=PURPOSE_CODES[RoutePurpose.RETAIL],
        buyer_org=int(fixture.network.edge_buyer_org[retail_edge]),
        transport_org=int(fixture.network.edge_transport_org[hub_edge]),
    )
    demand = np.zeros(len(fixture.network.demand_cell))
    demand[int(fixture.network.edge_demand[hub_edge])] = 5.0
    demand[int(fixture.network.edge_demand[retail_edge])] = 5.0
    fixture.network = shared_network
    problem, certificates = _solved(_capture_boundary(fixture, demand), demand)
    assert certificates["LP-2"].status == "FEASIBLE"
    x = certificates["LP-2"].x
    assert float(x[problem.edge_source == source_cell].sum()) <= 10.0 + 1e-9
    transported = (problem.edge_transport_org >= 0) & (~problem.edge_self_hauled)
    transport_need = float(
        np.sum(x[transported] * problem.edge_transport_per_unit[transported])
    )
    assert transport_need <= float(problem.logistics_pool.sum()) + 1e-9
    attempt_fixture = _transport_fixture(transport_opening=1.0)
    attempt_source = attempt_fixture.cell("organization", 1, 1, "output", "energy")
    attempt_hub = _transport_hub_edge(attempt_fixture)
    attempt_retail = int(
        np.flatnonzero(
            attempt_fixture.network.edge_purpose == PURPOSE_CODES[RoutePurpose.RETAIL]
        )[0]
    )
    attempt_fixture.network = _append_edge(
        attempt_fixture.network,
        attempt_hub,
        source=attempt_source,
        destination=int(attempt_fixture.network.edge_destination_cell[attempt_retail]),
        demand=int(attempt_fixture.network.edge_demand[attempt_retail]),
        purpose=PURPOSE_CODES[RoutePurpose.RETAIL],
        buyer_org=int(attempt_fixture.network.edge_buyer_org[attempt_retail]),
        transport_org=int(attempt_fixture.network.edge_transport_org[attempt_hub]),
    )
    attempt_demand = np.zeros(len(attempt_fixture.network.demand_cell))
    attempt_demand[int(attempt_fixture.network.edge_demand[attempt_hub])] = 5.0
    attempt_demand[int(attempt_fixture.network.edge_demand[attempt_retail])] = 5.0
    attempt = _execute(
        attempt_fixture,
        attempt_demand,
        level="LP-2",
        certificate=certificates["LP-2"],
    )
    assert attempt.execution_status == "EXECUTED"


# ---------------------------------------------------------------------------
# 4. Timing: current production is not borrowable, next quarter is available
# ---------------------------------------------------------------------------


def _timing_fixture() -> Fixture:
    energy = producer(1, "energy_generation", capacity=10.0, cash=0.0)
    buyer = producer(2, "consumer_goods_production", capacity=10.0, cash=100000.0)
    technologies = [
        tech("energy_generation", outputs=(("energy", "standard", 1.0),)),
        tech(
            "consumer_goods_production",
            inputs=(("energy", 1.0),),
            outputs=(("consumer_goods", "standard", 1.0),),
        ),
    ]
    parameters = default_params(
        desired_per_person=[0.0] * 8,
        transport_per_unit=0.0,
    )
    fixture = Fixture(
        [bank(0), energy, buyer],
        technologies,
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 1.0)],
        household_cash=0.0,
        ticks=2,
    )
    fixture.state.stock_value[:] = 0.0
    return fixture


def test_current_production_is_a_shortfall_not_a_future_stock_loan() -> None:
    fixture = _timing_fixture()
    source_cell = fixture.cell("organization", 1, 0, "output", "energy")
    buyer_cell = fixture.cell("organization", 2, 0, "input", "energy")
    edge = fixture.edge(source_cell, buyer_cell)
    demand = _demand_for(fixture, edge, 5.0)
    q1 = _execute(fixture, demand, level="LP-2")
    assert q1.execution_status == "PARTIAL"
    assert q1.selected_certificate.shortfall_total == pytest.approx(5.0)
    assert q1.actual_delivered[edge] == pytest.approx(0.0)
    assert fixture.state.completed_ticks == 1
    assert fixture.state.stock_value[source_cell] == pytest.approx(10.0)
    result = execute_routing_certificate(
        fixture.state,
        fixture.forcing(2),
        fixture.parameters,
        fixture.network,
        level="LP-2",
        demand=demand,
        time_limit_s=10,
    )
    assert result.execution_status == "EXECUTED"
    assert result.selected_certificate.shortfall_total == pytest.approx(0.0)
    assert result.actual_delivered[edge] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# 5. Funding: cash only for goods, not freight; wages first
# ---------------------------------------------------------------------------


def _cash_limited_transport_fixture(cash: float) -> Fixture:
    fixture = _transport_fixture(transport_opening=1.0)
    fixture.parameters = _no_credit(fixture.parameters)
    hub_row = 2
    reduction = float(fixture.state.organization_cash[hub_row]) - cash
    fixture.state.organization_cash[hub_row] = cash
    fixture.state.bank_deposit_liability[0] -= reduction
    fixture.state.bank_reserves[0] -= reduction
    return fixture


def test_lp1_ignores_funding_but_lp2_blocks_goods_plus_freight() -> None:
    fixture = _cash_limited_transport_fixture(10.0)
    edge = _transport_hub_edge(fixture)
    demand = _demand_for(fixture, edge, 10.0)
    boundary = _capture_boundary(fixture, demand)
    problem, certificates = _solved(boundary, demand)
    assert certificates["LP-1"].status == "FEASIBLE"
    assert certificates["LP-1"].shortfall_total == pytest.approx(0.0)
    assert certificates["LP-2"].status == "FEASIBLE"
    assert certificates["LP-2"].shortfall_total > 0.0
    executed = _execute(_cash_limited_transport_fixture(10.0), demand, level="LP-2")
    assert executed.execution_status == "PARTIAL"
    assert executed.measurement.max_shortfall_residual == pytest.approx(0.0)
    assert executed.actual_delivered[edge] < 10.0


def test_wage_prelude_reduces_the_funding_boundary_not_opening_cash() -> None:
    energy = producer(1, "energy_generation", capacity=10.0, cash=0.0)
    buyer = producer(2, "consumer_goods_production", capacity=10.0, cash=12.0)
    technologies = [
        tech("energy_generation", outputs=(("energy", "standard", 1.0),)),
        tech(
            "consumer_goods_production",
            inputs=(("energy", 1.0),),
            outputs=(("consumer_goods", "standard", 1.0),),
        ),
    ]
    parameters = _no_credit(
        default_params(
            desired_per_person=[0.0] * 8,
            transport_per_unit=0.0,
            wage_rate=1.0,
        )
    )
    fixture = Fixture(
        [bank(0), energy, buyer],
        technologies,
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 1.0)],
        household_cash=0.0,
        ticks=1,
    )
    fixture.state.stock_value[:] = 0.0
    source_cell = fixture.cell("organization", 1, 0, "output", "energy")
    fixture.state.stock_value[source_cell] = 10.0
    edge = fixture.edge(source_cell, fixture.cell("organization", 2, 0, "input", "energy"))
    demand = _demand_for(fixture, edge, 10.0)
    pre_tick = copy.deepcopy(fixture)
    boundary = _capture_boundary(fixture, demand)
    problem, certificates = _solved(boundary, demand)
    assert problem.organization_cash[2] == pytest.approx(2.0)
    assert certificates["LP-1"].status == "FEASIBLE"
    assert certificates["LP-2"].status == "FEASIBLE"
    assert certificates["LP-2"].shortfall_total > 0.0
    attempt = _execute(
        pre_tick,
        demand,
        level="LP-1",
        certificate=certificates["LP-1"],
    )
    assert attempt.execution_status == "EXECUTION_GAP"
    assert attempt.measurement.max_delivery_gap > 0.0


# ---------------------------------------------------------------------------
# 6. Two banks: prefunding/reserve constraints and actual settlement
# ---------------------------------------------------------------------------


def _two_bank_transport_fixture(*, buyer_bank_reserves: float) -> Fixture:
    seller = producer(1, "energy_generation", region="R1", cash=0.0, bank_id=5)
    wholesale = hub(2, region="R0")
    shop = org_retail_zero_cash()
    hauler = transport_zero_cash(4)
    technologies = [
        tech("energy_generation", outputs=(("energy", "standard", 1.0),)),
        tech(
            "freight_transport",
            inputs=(("durable_goods", 1.0),),
            outputs=(("services_transport", "standard", 1.0),),
        ),
    ]
    parameters = default_params(
        desired_per_person=[0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        transport_per_unit=0.1,
    )
    fixture = Fixture(
        [bank(0), seller, wholesale, shop, hauler, bank(5)],
        technologies,
        region_ids=("R0", "R1"),
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 25.0)],
        household_cash=0.0,
        ticks=1,
    )
    fixture.state.stock_value[:] = 0.0
    source = fixture.cell("organization", 1, 1, "output", "energy")
    fixture.parameters = _no_credit(fixture.parameters)
    fixture.state.stock_value[source] = 10.0
    fixture.state.stock_value[fixture.cell("organization", 4, 0, "input", "durable_goods")] = 1.0
    # Keep the buyer's cash/deposit consistent with the one bank that matters.
    fixture.state.treasury_deposit = 0.0
    fixture.state.credit_fund = 0.0
    buyer_row = 2
    buyer_cash = float(fixture.state.organization_cash[buyer_row])
    fixture.state.bank_deposit_liability[:] = 0.0
    fixture.state.bank_deposit_liability[0] = buyer_cash
    fixture.state.bank_loan_asset[:] = 0.0
    fixture.state.bank_equity[:] = 0.0
    fixture.state.bank_reserves[:] = 0.0
    fixture.state.bank_reserves[0] = buyer_bank_reserves
    if buyer_bank_reserves < buyer_cash:
        fixture.state.bank_loan_asset[0] = buyer_cash - buyer_bank_reserves
    return fixture


def org_retail_zero_cash():
    return org(
        3,
        OrganizationType.RETAIL,
        region="R0",
        handling_capacity=1_000_000.0,
        initial_cash=0.0,
        bank_id=0,
    )


def transport_zero_cash(organization_id: int):
    return org(
        organization_id,
        OrganizationType.TRANSPORT,
        region="R0",
        technology_id="freight_transport",
        capacity=1.0,
        labor_available=1.0,
        labor_per_activity=1.0,
        initial_cash=0.0,
        bank_id=5,
    )


def test_zero_buyer_bank_reserve_blocks_lp2_and_funded_control_settles() -> None:
    starved = _two_bank_transport_fixture(buyer_bank_reserves=0.0)
    edge = _transport_hub_edge(starved)
    demand = _demand_for(starved, edge, 10.0)
    problem, certificates = _solved(_capture_boundary(starved, demand), demand)
    assert certificates["LP-1"].status == "FEASIBLE"
    assert certificates["LP-2"].status == "FEASIBLE"
    assert certificates["LP-2"].shortfall_total == pytest.approx(10.0)
    assert problem.bank_reserves[0] == 0.0
    starved_result = _execute(
        _two_bank_transport_fixture(buyer_bank_reserves=0.0), demand, level="LP-2"
    )
    assert starved_result.execution_status == "PARTIAL"
    assert starved_result.actual_delivered[edge] == pytest.approx(0.0)

    funded = _two_bank_transport_fixture(buyer_bank_reserves=10.909090909090908)
    result = _execute(funded, demand, level="LP-2")
    assert result.execution_status == "EXECUTED"
    assert result.actual_delivered[edge] == pytest.approx(10.0)
    assert funded.state.bank_reserves[0] >= -1e-9
    assert funded.state.bank_reserves[1] >= -1e-9
    assert result.flows.organization_sales_receipts[1] == pytest.approx(10.0)
    assert result.flows.organization_sales_receipts[4] > 0.0


# ---------------------------------------------------------------------------
# 7. Journal tampering, rollback and failure serialization
# ---------------------------------------------------------------------------


def test_swapped_goods_recipient_is_rejected_by_measurement() -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    edge = _transport_hub_edge(fixture)
    demand = _demand_for(fixture, edge, 10.0)
    opening = capture_material_stocks(fixture.state)
    result = _execute(fixture, demand, level="LP-2")
    tampered = copy.deepcopy(result.flows)
    goods_rows = [i for i, kind in enumerate(tampered.journal_kind) if kind == "goods_payment"]
    assert goods_rows
    tampered.journal_credit[goods_rows[0]] = int(tampered.journal_credit[goods_rows[1]])
    saved_tick = fixture.state.completed_ticks
    fixture.state.completed_ticks = int(tampered.tick)
    with pytest.raises(ResearchGateError):
        measure_routing_execution(
            opening,
            fixture.state,
            tampered,
            fixture.parameters,
            fixture.network,
            problem=result.problems[0],
            certificate=result.selected_certificate,
            planned_x=result.planned_x,
            submitted_x=result.submitted_x,
            execution_status="EXECUTED",
            lost_free_delivery=0.0,
            projected=False,
            project_note="tamper",
            invariants=result.gate,
        )
    fixture.state.completed_ticks = saved_tick


def test_goods_receipt_on_wrong_account_kind_is_rejected() -> None:
    from hsm_lab.engine.finance import AccountKind, build_account_directory

    fixture = _transport_fixture(transport_opening=1.0)
    edge = _transport_hub_edge(fixture)
    demand = _demand_for(fixture, edge, 10.0)
    opening = capture_material_stocks(fixture.state)
    result = _execute(fixture, demand, level="LP-2")
    tampered = copy.deepcopy(result.flows)
    directory = build_account_directory(fixture.state)
    seller_loan = directory[
        ("organization", 1, "p02_domestic_currency", AccountKind.LOAN_LIABILITY)
    ]
    reverse = {account: key for key, account in directory.items()}
    for row in range(len(tampered.journal_kind)):
        if tampered.journal_kind[row] != "goods_payment":
            continue
        credit_key = reverse.get(int(tampered.journal_credit[row]), ("",))
        if credit_key[:2] == ("organization", 1):
            tampered.journal_credit[row] = int(seller_loan)
    saved_tick = fixture.state.completed_ticks
    fixture.state.completed_ticks = int(tampered.tick)
    with pytest.raises(ResearchGateError):
        measure_routing_execution(
            opening,
            fixture.state,
            tampered,
            fixture.parameters,
            fixture.network,
            problem=result.problems[0],
            certificate=result.selected_certificate,
            planned_x=result.planned_x,
            submitted_x=result.submitted_x,
            execution_status="EXECUTED",
            lost_free_delivery=0.0,
            projected=False,
            project_note="account-kind tamper",
            invariants=result.gate,
        )
    fixture.state.completed_ticks = saved_tick


def test_suboptimal_and_non_finite_certificates_are_rejected() -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    edge = _transport_hub_edge(fixture)
    demand = _demand_for(fixture, edge, 10.0)
    result = _execute(_transport_fixture(transport_opening=1.0), demand, level="LP-2")
    problem = result.problems[0]
    suboptimal = dataclasses.replace(
        result.selected_certificate,
        x=np.zeros_like(result.selected_certificate.x),
        shortfall=problem.demand.copy(),
        shortfall_total=float(problem.demand.sum()),
    )
    ok, reason = feasibility.verify_certificate(problem, suboptimal)
    assert ok is False and reason
    nan_total = dataclasses.replace(
        result.selected_certificate, shortfall_total=float("nan")
    )
    ok, reason = feasibility.verify_certificate(problem, nan_total)
    assert ok is False and "non-finite" in reason
    nan_activity = dataclasses.replace(
        result.selected_certificate,
        row_activity=np.full_like(result.selected_certificate.row_activity, np.nan),
    )
    ok, reason = feasibility.verify_certificate(problem, nan_activity)
    assert ok is False and "non-finite" in reason
    forged = dataclasses.replace(
        result.selected_certificate,
        row_names=("forged",) + result.selected_certificate.row_names[1:],
        row_rhs=np.full_like(result.selected_certificate.row_rhs, np.inf),
        row_activity=result.selected_certificate.row_activity + 1e6,
    )
    ok, reason = feasibility.verify_certificate(problem, forged)
    assert ok is False
    for replacement in (
        {"max_abs_residual": float("nan")},
        {"build_wall_s": float("nan")},
        {"solve_wall_s": float("inf")},
        {"solver_feasible": False},
        {"solver_feasible": float("nan")},
        {"solver_feasible": "False"},
        {"no_demand": "False"},
        {"free_flow": 1},
        {"free_flow": True},
    ):
        bad_meta = dataclasses.replace(
            result.selected_certificate, **replacement
        )
        ok, reason = feasibility.verify_certificate(problem, bad_meta)
        assert ok is False and reason
    malformed_flag = dataclasses.replace(
        result.selected_certificate, solver_feasible=float("nan")
    )
    fresh = _transport_fixture(transport_opening=1.0)
    with pytest.raises(RoutingExecutionFailure):
        _execute(fresh, demand, level="LP-2", certificate=malformed_flag)
    assert fresh.state.completed_ticks == 0
    rows = feasibility._build_rows(problem, "LP-2")
    vector = np.concatenate(
        [
            np.zeros_like(result.selected_certificate.x),
            result.selected_certificate.u,
            result.selected_certificate.v,
            problem.demand,
        ]
    )
    activity, residual, slack = feasibility._witness_residuals(rows, vector.size, vector)
    consistent_suboptimal = dataclasses.replace(
        suboptimal,
        row_activity=activity,
        row_residual=residual,
        row_slack=slack,
    )
    ok, reason = feasibility.verify_certificate(problem, consistent_suboptimal)
    assert ok is False and ("complementarity" in reason or "minimum-shortfall" in reason)
    with pytest.raises(RoutingExecutionFailure):
        _execute(
            _transport_fixture(transport_opening=1.0),
            demand,
            level="LP-2",
            certificate=suboptimal,
        )


def test_supplied_certificate_reuse_does_not_call_solver(monkeypatch) -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    edge = _transport_hub_edge(fixture)
    demand = _demand_for(fixture, edge, 10.0)
    result = _execute(_transport_fixture(transport_opening=1.0), demand, level="LP-2")
    calls: list[float] = []

    def forbidden(*args, **kwargs):
        calls.append(float(kwargs.get("time_limit_s", -1.0)))
        raise AssertionError("solver called during certificate reuse")

    monkeypatch.setattr(feasibility, "solve_routing_feasibility", forbidden)
    fresh = _transport_fixture(transport_opening=1.0)
    reused = execute_routing_certificate(
        fresh.state,
        fresh.forcing(1),
        fresh.parameters,
        fresh.network,
        level="LP-2",
        demand=demand,
        certificate=result.selected_certificate,
        time_limit_s=0.001,
    )
    assert calls == []
    assert reused.execution_status == "EXECUTED"


def test_bad_certificate_rolls_back_state_and_preserves_trace() -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    edge = _transport_hub_edge(fixture)
    demand = _demand_for(fixture, edge, 10.0)
    result = _execute(_transport_fixture(transport_opening=1.0), demand, level="LP-2")
    before = copy.deepcopy(fixture.state)
    bad = dataclasses.replace(result.selected_certificate, demand_hash="mismatch")
    with pytest.raises(RoutingExecutionFailure) as caught:
        _execute(fixture, demand, level="LP-2", certificate=bad)
    failure = caught.value
    assert failure.phase == "allocation"
    assert failure.failed_trace.get("boundary") is not None
    assert fixture.state.completed_ticks == before.completed_ticks
    for field in before.__dataclass_fields__:
        left = getattr(fixture.state, field)
        right = getattr(before, field)
        if isinstance(left, np.ndarray):
            assert np.array_equal(left, right), field
        else:
            assert left == right, field
    payload = failure.to_dict()
    assert payload["phase"] == "allocation"
    assert "boundary" in payload["failed_trace"]


# ---------------------------------------------------------------------------
# 8. Nested comparison and trace-only/default equivalence
# ---------------------------------------------------------------------------


def test_nested_comparison_accepts_same_problem_and_rejects_changed_price() -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    edge = _transport_hub_edge(fixture)
    demand = _demand_for(fixture, edge, 10.0)
    boundary = _capture_boundary(fixture, demand)
    problem, certificates = _solved(boundary, demand)
    assert feasibility.compare_routing_certificates(
        problem, tuple(certificates[level] for level in feasibility.LEVELS)
    ).nested is True

    changed = dict(boundary)
    price = np.array(boundary["edge_unit_price"], copy=True)
    price[0] *= 2.0
    changed["edge_unit_price"] = price
    other = feasibility.build_routing_problem(changed, demand=demand)
    assert feasibility.compare_routing_certificates(
        other, tuple(certificates[level] for level in feasibility.LEVELS)
    ).nested is False


def test_trace_only_matches_default_bytes_and_invalid_vectors_are_rejected() -> None:
    default_fixture = _transport_fixture(transport_opening=1.0)
    default_flows = tick_material(
        default_fixture.state,
        default_fixture.forcing(1),
        default_fixture.parameters,
        default_fixture.network,
    )
    trace_fixture = _transport_fixture(transport_opening=1.0)
    trace = {}
    trace_flows = tick_material(
        trace_fixture.state,
        trace_fixture.forcing(1),
        trace_fixture.parameters,
        trace_fixture.network,
        routing_trace=trace,
    )
    assert _digest_state_flows(default_fixture.state, default_flows) == _digest_state_flows(
        trace_fixture.state, trace_flows
    )
    assert "boundary" in trace and "requested_edge_flow" in trace

    bad = _transport_fixture(transport_opening=1.0)
    edge = _transport_hub_edge(bad)
    demand = _demand_for(bad, edge, 10.0)
    boundary = _capture_boundary(bad, demand)
    from hsm_lab.engine.material import _validate_routing_allocation

    m_count = int(boundary["edge_source"].shape[0])
    for vector in (
        np.zeros(m_count - 1),
        np.full(m_count, np.nan),
        np.full(m_count, -1.0),
    ):
        with pytest.raises(ResearchGateError, match="HIST_H3C_ROUTING"):
            _validate_routing_allocation(vector, boundary)


def test_zero_demand_is_reported_not_executed() -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    demand = np.zeros(len(fixture.network.demand_cell), dtype=np.float64)
    result = _execute(fixture, demand, level="LP-2")
    assert result.execution_status == "NO_DEMAND"
    assert result.selected_certificate.no_demand is True
    assert fixture.state.completed_ticks == 0


# ---------------------------------------------------------------------------
# 9. Review regressions: full gross, imports, fallback, certificate reuse
# ---------------------------------------------------------------------------


def test_default_demand_is_the_complete_gross_request() -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    edge = _transport_hub_edge(fixture)
    boundary = _capture_boundary(fixture, _demand_for(fixture, edge, 10.0))
    problem = feasibility.build_routing_problem(boundary)
    assert np.array_equal(problem.demand, boundary["demand_gross"])
    assert float(problem.demand.sum()) == pytest.approx(
        float(boundary["demand_gross"].sum())
    )


def test_import_stock_is_counted_once_in_source_availability() -> None:
    fixture = _mixed_energy_fixture()
    boundary = _capture_boundary(fixture, np.zeros(len(fixture.network.demand_cell)))
    assert np.allclose(boundary["source_available"], fixture.state.stock_value)
    import_cell = int(fixture.network.import_pool_cell[fixture.g("energy")])
    assert boundary["source_available"][import_cell] == pytest.approx(
        float(fixture.state.stock_value[import_cell])
    )
    assert boundary["source_available"][import_cell] < 200.0


def test_fallback_must_fit_after_prior_tier_withdrawals() -> None:
    from hsm_lab.engine.material import _validate_routing_allocation

    boundary = {
        "edge_source": np.asarray([0, 0], dtype=np.int64),
        "edge_demand": np.asarray([0, 1], dtype=np.int64),
        "edge_tier": np.asarray([0, 3], dtype=np.int64),
        "demand_ordered": np.asarray([10.0, 10.0]),
        "source_available": np.asarray([20.0]),
        "stock_open": np.asarray([10.0]),
        "import_into": np.asarray([0.0]),
        "produced_into": np.asarray([10.0]),
        "service_split": np.asarray([0.0, 1.0, 0.0]),
    }
    with pytest.raises(ResearchGateError, match="fallback allocation"):
        _validate_routing_allocation(np.asarray([10.0, 10.0]), boundary)


def test_malformed_supplied_certificate_is_rejected_and_rolled_back() -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    edge = _transport_hub_edge(fixture)
    demand = _demand_for(fixture, edge, 10.0)
    result = _execute(_transport_fixture(transport_opening=1.0), demand, level="LP-2")
    bad_nan = dataclasses.replace(
        result.selected_certificate,
        u=np.full_like(result.selected_certificate.u, np.nan),
        constraint_hash="not-the-constraints",
    )
    ok, reason = feasibility.verify_certificate(result.problems[0], bad_nan)
    assert ok is False and "non-finite" in reason
    before = copy.deepcopy(fixture.state)
    with pytest.raises(RoutingExecutionFailure):
        _execute(fixture, demand, level="LP-2", certificate=bad_nan)
    assert fixture.state.completed_ticks == before.completed_ticks
    for field in before.__dataclass_fields__:
        left = getattr(fixture.state, field)
        right = getattr(before, field)
        if isinstance(left, np.ndarray):
            assert np.array_equal(left, right), field
        else:
            assert left == right, field
    bad_hash = dataclasses.replace(
        result.selected_certificate, constraint_hash="not-the-constraints"
    )
    ok, reason = feasibility.verify_certificate(result.problems[0], bad_hash)
    assert ok is False and "constraint hash" in reason


def test_mixed_energy_channel_executes_with_household_checkout() -> None:
    fixture = _mixed_energy_fixture()
    source = fixture.cell("organization", 1, 0, "output", "energy")
    edge = fixture.edge(source, fixture.cell("organization", 2, 0, "input", "energy"))
    demand = _demand_for(fixture, edge, 6.0)
    result = _execute(fixture, demand, level="LP-2")
    assert result.execution_status == "EXECUTED"
    demand_index = int(fixture.network.edge_demand[edge])
    assert result.flows.delivered[demand_index] == pytest.approx(6.0)
    assert result.selected_certificate.shortfall_total == pytest.approx(0.0)
    assert result.measurement.max_payment_residual == pytest.approx(0.0)


def test_no_demand_flag_is_derived_not_trusted() -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    zero = np.zeros(len(fixture.network.demand_cell))
    result = _execute(fixture, zero, level="LP-2")
    bad = dataclasses.replace(result.selected_certificate, no_demand=False)
    ok, reason = feasibility.verify_certificate(result.problems[0], bad)
    assert ok is False and "no_demand" in reason
    fresh = _transport_fixture(transport_opening=1.0)
    with pytest.raises(RoutingExecutionFailure):
        _execute(fresh, zero, level="LP-2", certificate=bad)
    assert fresh.state.completed_ticks == 0


def test_weighted_plot_channel_reconciles_represented_funding() -> None:
    energy = producer(1, "energy_generation", capacity=10.0)
    technologies = [tech("energy_generation", outputs=(("energy", "standard", 1.0),))]
    parameters = default_params(
        desired_per_person=[0.0] * 8,
        transport_per_unit=0.0,
    )
    fixture = Fixture(
        [bank(0), energy],
        technologies,
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 2.0, 1.0)],
        household_cash=1000.0,
        plot_participating=np.asarray([True]),
        ticks=1,
    )
    fixture.state.stock_value[:] = 0.0
    source = fixture.cell("organization", 1, 0, "output", "energy")
    fixture.state.stock_value[source] = 10.0
    plot_demands = np.flatnonzero(
        fixture.network.demand_purpose == PURPOSE_CODES[RoutePurpose.PRIVATE_PLOT]
    )
    assert plot_demands.size
    demand = np.zeros(len(fixture.network.demand_cell))
    demand[int(plot_demands[0])] = 0.001
    result = _execute(fixture, demand, level="LP-2")
    assert result.execution_status == "EXECUTED"
    assert result.measurement.max_payment_residual == pytest.approx(0.0)


def test_wrong_regional_plot_clearing_account_is_rejected() -> None:
    from hsm_lab.engine.finance import DOMESTIC_CURRENCY, build_account_directory

    energy = producer(1, "energy_generation", capacity=10.0)
    technologies = [tech("energy_generation", outputs=(("energy", "standard", 1.0),))]
    parameters = default_params(
        desired_per_person=[0.0] * 8,
        transport_per_unit=0.0,
    )
    fixture = Fixture(
        [bank(0), energy],
        technologies,
        region_ids=("R0", "R1"),
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 1.0), (1, 1.0, 1.0)],
        household_cash=1000.0,
        plot_participating=np.asarray([True, True]),
        ticks=1,
    )
    fixture.state.stock_value[:] = 0.0
    source = fixture.cell("organization", 1, 0, "output", "energy")
    fixture.state.stock_value[source] = 10.0
    plot_demands = np.flatnonzero(
        fixture.network.demand_purpose == PURPOSE_CODES[RoutePurpose.PRIVATE_PLOT]
    )
    demand_index = next(
        int(index)
        for index in plot_demands
        if np.any(fixture.network.edge_demand == index)
        and int(
            fixture.network.cell_region[int(fixture.network.demand_cell[index])]
        )
        == 0
    )
    demand = np.zeros(len(fixture.network.demand_cell))
    demand[demand_index] = 0.001
    opening = capture_material_stocks(fixture.state)
    result = _execute(fixture, demand, level="LP-2")
    assert result.execution_status == "EXECUTED"
    directory = build_account_directory(fixture.state)
    reverse = {account: key for key, account in directory.items()}
    tampered = copy.deepcopy(result.flows)
    wrong = directory[
        ("plot_clearing_1", 1, DOMESTIC_CURRENCY, "plot_clearing")
    ]
    for row in range(len(tampered.journal_kind)):
        if tampered.journal_kind[row] != "goods_payment":
            continue
        debit_key = reverse.get(int(tampered.journal_debit[row]), ("",))
        credit_key = reverse.get(int(tampered.journal_credit[row]), ("",))
        if debit_key[0] == "plot_clearing_0":
            tampered.journal_debit[row] = wrong
        if credit_key[0] == "plot_clearing_0":
            tampered.journal_credit[row] = wrong
    saved_tick = fixture.state.completed_ticks
    fixture.state.completed_ticks = int(tampered.tick)
    with pytest.raises(
        ResearchGateError, match="plot_channel_funding|non-organization payment"
    ):
        measure_routing_execution(
            opening,
            fixture.state,
            tampered,
            fixture.parameters,
            fixture.network,
            problem=result.problems[0],
            certificate=result.selected_certificate,
            planned_x=result.planned_x,
            submitted_x=result.submitted_x,
            execution_status="EXECUTED",
            lost_free_delivery=0.0,
            projected=False,
            project_note="regional tamper",
            invariants=result.gate,
        )
    fixture.state.completed_ticks = saved_tick


def test_incoming_only_regional_clearing_tamper_is_rejected() -> None:
    from hsm_lab.engine.finance import DOMESTIC_CURRENCY, build_account_directory

    energy = producer(1, "energy_generation", capacity=10.0)
    technologies = [tech("energy_generation", outputs=(("energy", "standard", 1.0),))]
    parameters = default_params(
        desired_per_person=[0.0] * 8,
        transport_per_unit=0.0,
    )
    fixture = Fixture(
        [bank(0), energy],
        technologies,
        region_ids=("R0", "R1"),
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 1.0), (1, 1.0, 1.0)],
        household_cash=1000.0,
        plot_participating=np.asarray([True, True]),
        ticks=1,
    )
    fixture.state.stock_value[:] = 0.0
    source = fixture.cell("organization", 1, 0, "output", "energy")
    fixture.state.stock_value[source] = 10.0
    plot_demands = np.flatnonzero(
        fixture.network.demand_purpose == PURPOSE_CODES[RoutePurpose.PRIVATE_PLOT]
    )
    demand_index = next(
        int(index)
        for index in plot_demands
        if np.any(fixture.network.edge_demand == index)
        and int(
            fixture.network.cell_region[int(fixture.network.demand_cell[index])]
        )
        == 0
    )
    demand = np.zeros(len(fixture.network.demand_cell))
    demand[demand_index] = 0.001
    opening = capture_material_stocks(fixture.state)
    result = _execute(fixture, demand, level="LP-2")
    assert result.execution_status == "EXECUTED"
    directory = build_account_directory(fixture.state)
    reverse = {account: key for key, account in directory.items()}
    wrong = directory[("plot_clearing_1", 1, DOMESTIC_CURRENCY, "plot_clearing")]
    tampered = copy.deepcopy(result.flows)
    for row in range(len(tampered.journal_kind)):
        if tampered.journal_kind[row] != "goods_payment":
            continue
        debit_key = reverse.get(int(tampered.journal_debit[row]), ("",))
        if debit_key[0] == "household":
            tampered.journal_credit[row] = wrong
    saved_tick = fixture.state.completed_ticks
    fixture.state.completed_ticks = int(tampered.tick)
    with pytest.raises(ResearchGateError, match="plot_channel_funding"):
        measure_routing_execution(
            opening,
            fixture.state,
            tampered,
            fixture.parameters,
            fixture.network,
            problem=result.problems[0],
            certificate=result.selected_certificate,
            planned_x=result.planned_x,
            submitted_x=result.submitted_x,
            execution_status="EXECUTED",
            lost_free_delivery=0.0,
            projected=False,
            project_note="incoming-only regional tamper",
            invariants=result.gate,
        )
    fixture.state.completed_ticks = saved_tick
