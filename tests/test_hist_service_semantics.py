"""HIST_VNEXT H3A: service capability/schedule/provision/use/loss tests.

The tests exercise the real material kernel (no mocks): the tiny service and
housing fixtures from ``test_material`` plus the frozen F2 replay scenario.  The
measurement is read-only; every rejection case proves the canonical kernel bytes
are unchanged.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.contract.material import commodity_spec
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.accounting import check_material_invariants, tolerance_for
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.material import (
    canonical_material_bytes,
    load_material_forcing,
    tick_material,
)
from hsm_lab.engine.network import build_material_network
from hsm_lab.engine.policy import TickControls
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import capture_material_stocks, initialize_material
from hsm_lab.measurement.service_semantics import (
    HousingStockMeasurement,
    ServiceCommodityMeasurement,
    ServiceInputUse,
    ServiceTickMeasurement,
    measure_service_tick,
)
from tests.test_material import (
    NO_CAPITAL_COMMODITIES,
    Fixture,
    _housing_fixture,
    _org_activity,
    _services_fixture,
    bank,
    default_params,
    hub,
    idle_source_tech,
    producer,
    retail,
    tech,
    transport,
)

ROOT = Path(__file__).resolve().parents[1]


def _measure(
    fixture: Fixture,
    *,
    service_org_row: int | None = None,
    central: float | None = None,
    autonomy: float = 0.0,
):
    controls = None
    if central is not None:
        assert service_org_row is not None
        activity = _org_activity(fixture, service_org_row)
        target = np.asarray(fixture.network.activity_capacity, dtype=np.float64).copy()
        target[activity] = central
        controls = TickControls(
            material_parameters=fixture.parameters,
            household_parameters=fixture.household_parameters,
            household_catalog=fixture.network.household_catalog,
            autonomy=autonomy,
            central_target=target,
        )
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        fixture.forcing(1),
        fixture.parameters,
        fixture.network,
        controls=controls,
    )
    summary = check_material_invariants(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        controls=controls,
    )
    measurement = measure_service_tick(opening, fixture.state, flows, fixture.network, summary)
    return opening, flows, summary, measurement, controls, activity if central is not None else None


def test_service_target_controls_real_provision() -> None:
    arms = [
        # label, central, autonomy, scheduled, provided, unscheduled,
        # shortfall, logistics, lost, delivered
        ("legacy", None, 0.0, 5.0, 5.0, 0.0, 0.0, 3.0, 2.0, 10.0),
        ("central_3_autonomy_0", 3.0, 0.0, 3.0, 3.0, 2.0, 0.0, 3.0, 0.0, 10.0),
        ("central_0_autonomy_0", 0.0, 0.0, 0.0, 0.0, 5.0, 0.0, 0.0, 0.0, 0.0),
        ("central_3_autonomy_1", 3.0, 1.0, 5.0, 5.0, 0.0, 0.0, 3.0, 2.0, 10.0),
    ]
    for (
        label,
        central,
        autonomy,
        scheduled,
        provided,
        unscheduled,
        shortfall,
        logistics,
        lost,
        delivered,
    ) in arms:
        fixture = _services_fixture()
        activity = _org_activity(fixture, 4)
        opening, flows, _summary, measurement, _controls, _activity = _measure(
            fixture, service_org_row=4, central=central, autonomy=autonomy
        )
        service = measurement.services[0]
        assert service.commodity_id == "services_transport", label
        assert service.capacity == pytest.approx(5.0), label
        assert service.scheduled == pytest.approx(scheduled), label
        assert service.provided == pytest.approx(provided), label
        assert service.unscheduled_capacity == pytest.approx(unscheduled), label
        assert service.schedule_shortfall == pytest.approx(shortfall), label
        assert service.used_productive == pytest.approx(0.0), label
        assert service.used_logistics == pytest.approx(logistics), label
        assert service.used_household == pytest.approx(0.0), label
        assert service.used_other == pytest.approx(0.0), label
        assert service.lost == pytest.approx(lost), label
        assert service.closing == pytest.approx(0.0), label
        assert service.balance_residual == pytest.approx(0.0, abs=1e-9), label
        assert flows.activity_target[activity] == pytest.approx(scheduled), label
        assert flows.activity_realized[activity] == pytest.approx(provided), label
        seller_cell = fixture.cell("organization", 1, 1, "output", "energy")
        hub_cell = fixture.cell("organization", 2, 0, "wholesale", "energy")
        edge = fixture.edge(seller_cell, hub_cell)
        assert flows.edge_delivered[edge] == pytest.approx(delivered), label
        assert measurement.legacy_expired_services == pytest.approx(lost), label


def _fuel_fixture() -> Fixture:
    """The service fixture with a real energy input (not a durable proxy) and
    a 10-unit consumer-goods delivery that needs 3 service units."""
    seller = producer(1, "h3a_goods_source", region="R1", capacity=1.0)
    wholesale = hub(2, region="R0")
    shop = retail(3, region="R0")
    hauler = transport(4, region="R0", capacity=5.0)
    technologies = [
        idle_source_tech("h3a_goods_source", "consumer_goods"),
        tech(
            "freight_transport",
            inputs=(("energy", 1.0),),
            outputs=(("services_transport", "standard", 1.0),),
        ),
    ]
    parameters = default_params(
        desired_per_person=[0.0, 0.0, 0.0, 0.4, 0.0, 0.0, 0.0, 0.0],
        transport_per_unit=0.3,
        service_split=[1.0, 0.0, 0.0],
    )
    fixture = Fixture(
        [bank(0), seller, wholesale, shop, hauler],
        technologies,
        region_ids=("R0", "R1"),
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 25.0)],
        household_cash=1000.0,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 1, "output", "consumer_goods")] = 10.0
    fixture.state.stock_value[fixture.cell("organization", 4, 0, "input", "energy")] = 5.0
    return fixture


def test_fuel_consumption_survives_unused_service() -> None:
    arms = [
        ("legacy", None, 0.0, 5.0, 5.0, 3.0, 2.0, 10.0),
        ("target_3", 3.0, 0.0, 3.0, 3.0, 3.0, 0.0, 10.0),
        ("target_0", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    ]
    for label, central, autonomy, fuel, provided, logistics, lost, delivered in arms:
        fixture = _fuel_fixture()
        activity = _org_activity(fixture, 4)
        fuel_cell = fixture.cell("organization", 4, 0, "input", "energy")
        fuel_input = fixture.k_of(fuel_cell)
        opening, flows, _summary, measurement, _controls, _activity = _measure(
            fixture, service_org_row=4, central=central, autonomy=autonomy
        )
        service = measurement.services[0]
        coefficient = float(np.asarray(fixture.network.A[activity, fuel_input]))
        assert coefficient == pytest.approx(1.0), label
        # opening + delivered - used == closing, with the real fuel input row.
        assert (
            opening.stock_value[fuel_cell]
            + flows.delivered[fuel_input]
            - flows.used[fuel_input]
            == pytest.approx(fixture.state.stock_value[fuel_cell])
        ), label
        assert flows.used[fuel_input] == pytest.approx(fuel), label
        assert coefficient * flows.activity_realized[activity] == pytest.approx(
            flows.used[fuel_input]
        ), label
        assert service.provided == pytest.approx(provided), label
        assert service.used_logistics == pytest.approx(logistics), label
        assert service.lost == pytest.approx(lost), label
        assert measurement.legacy_expired_services == pytest.approx(lost), label
        assert service.balance_residual == pytest.approx(0.0, abs=1e-9), label
        assert flows.edge_delivered.sum() == pytest.approx(delivered), label
        assert measurement.inputs == (
            ServiceInputUse(
                activity_index=activity,
                input_index=fuel_input,
                commodity_id="energy",
                unit="p02_energy_unit",
                used=fuel,
            ),
        ), label


def test_housing_stock_is_not_quarterly_public_service() -> None:
    fixture = _housing_fixture()
    opening, _flows, _summary, measurement, _controls, _activity = _measure(fixture)
    assert measurement.services == ()
    housing = measurement.housing[0]
    assert isinstance(housing, HousingStockMeasurement)
    assert housing.region_id == "R0"
    assert housing.unit == "dwelling_unit"
    assert housing.formal_completed == pytest.approx(1.2)
    assert housing.private_completed == pytest.approx(0.0)
    assert housing.closing_stock - housing.opening_stock == pytest.approx(1.2)
    assert housing.allocated == pytest.approx(1.2)
    # Allocation is an assignment of existing dwellings, never a new completion.
    assert housing.closing_stock - housing.opening_stock == pytest.approx(
        housing.formal_completed + housing.private_completed
    )
    # The builder's capacity did not rise from housing delivery, and no
    # commodity service carries the dwelling stock.
    assert fixture.state.organization_capacity == pytest.approx(opening.organization_capacity)
    public_spec = commodity_spec("g16_housing_public_services")
    assert public_spec.unit == "f2_public_service_1960_unit"
    assert public_spec.stockable is False
    assert public_spec.unit != "dwelling_unit"


def test_service_measurement_preserves_kernel_bytes() -> None:
    fixture = _services_fixture()
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(fixture.state, fixture.forcing(1), fixture.parameters, fixture.network)
    summary = check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    before = canonical_material_bytes(fixture.state, flows)
    clock = fixture.state.completed_ticks
    measurement = measure_service_tick(opening, fixture.state, flows, fixture.network, summary)
    after = canonical_material_bytes(fixture.state, flows)
    assert before == after
    assert fixture.state.completed_ticks == clock
    assert isinstance(measurement, ServiceTickMeasurement)
    for service in measurement.services:
        assert isinstance(service, ServiceCommodityMeasurement)
        for field in dataclasses.fields(service):
            value = getattr(service, field.name)
            assert not isinstance(value, np.ndarray)
    for entry in measurement.inputs:
        assert not isinstance(entry.used, np.ndarray)


def _reject_unchanged(
    opening,
    state,
    flows,
    network,
    summary,
    *,
    match: str,
) -> None:
    before = canonical_material_bytes(state, flows)
    with pytest.raises(ResearchGateError, match=match):
        measure_service_tick(opening, state, flows, network, summary)
    assert canonical_material_bytes(state, flows) == before


def test_service_measurement_rejects_unreconciled_boundary() -> None:
    fixture = _services_fixture()
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(fixture.state, fixture.forcing(1), fixture.parameters, fixture.network)
    summary = check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    service_cells = np.flatnonzero(
        ~np.asarray([commodity_spec(c).stockable for c in fixture.network.commodity_ids])[
            np.asarray(fixture.network.cell_commodity)
        ]
    )
    assert service_cells.size

    _reject_unchanged(
        dataclasses.replace(opening, completed_ticks=opening.completed_ticks + 1),
        fixture.state,
        flows,
        fixture.network,
        summary,
        match="clock advance",
    )
    _reject_unchanged(
        opening,
        fixture.state,
        flows,
        fixture.network,
        dataclasses.replace(summary, expired_leftover_by_cell=np.zeros(3)),
        match="shape",
    )

    nonfinite = np.asarray(summary.expired_leftover_by_cell, dtype=np.float64).copy()
    nonfinite[int(service_cells[0])] = np.nan
    _reject_unchanged(
        opening,
        fixture.state,
        flows,
        fixture.network,
        dataclasses.replace(summary, expired_leftover_by_cell=nonfinite),
        match="non-finite",
    )

    negative = np.asarray(flows.second_input_used, dtype=np.float64).copy()
    negative[int(service_cells[0])] = -1.0
    _reject_unchanged(
        opening,
        fixture.state,
        dataclasses.replace(flows, second_input_used=negative),
        fixture.network,
        summary,
        match="negative",
    )

    # Changing the legacy loss 2 -> 0 (summary only) must not relabel the sink.
    _reject_unchanged(
        opening,
        fixture.state,
        flows,
        fixture.network,
        dataclasses.replace(
            summary, expired_leftover_by_cell=np.zeros_like(summary.expired_leftover_by_cell)
        ),
        match="expiry sink",
    )

    # Changing both the summary and the legacy scalar must still fail the
    # service balance instead of silently removing the loss.
    zero_summary = dataclasses.replace(
        summary, expired_leftover_by_cell=np.zeros_like(summary.expired_leftover_by_cell)
    )
    _reject_unchanged(
        opening,
        fixture.state,
        dataclasses.replace(flows, expired_services=0.0),
        fixture.network,
        zero_summary,
        match="balance does not close",
    )

    _reject_unchanged(
        opening,
        fixture.state,
        flows,
        fixture.network,
        dataclasses.replace(summary, max_material_tolerance_ratio=1.5),
        match="passed gate",
    )


@pytest.fixture(scope="module")
def f2_two_ticks():
    spec = load_scenario(ROOT, "historical_f2_replay")
    contract = load_research_contract(ROOT)
    initial = build_material_initial_conditions(spec, RngRegistry(spec.seed))
    network = build_material_network(spec, contract, initial)
    state = initialize_material(spec, initial, network)
    registry = DataRegistry.load(ROOT, allowed_commodities=spec.commodities)
    forcing = load_material_forcing(spec, registry)
    measured = []
    for _ in range(2):
        opening = capture_material_stocks(state)
        flows = tick_material(state, forcing, spec.material_parameters, network)
        summary = check_material_invariants(
            opening, state, flows, spec.material_parameters, network
        )
        measurement = measure_service_tick(opening, state, flows, network, summary)
        measured.append((opening, flows, summary, measurement, state.copy_dynamic()))
        state.completed_ticks += 1
    return network, state, measured


def test_service_input_pool_is_not_double_counted(f2_two_ticks) -> None:
    network, _state, measured = f2_two_ticks
    _opening, flows, _summary, measurement, _state_snapshot = measured[1]
    assert flows.quarter == "1957Q2"
    commodity_id = "g03_electricity_heat"
    g = network.commodity_ids.index(commodity_id)
    cells = np.flatnonzero(np.asarray(network.cell_commodity) == g)
    draw = float(np.asarray(flows.service_pool_draw_at_cell)[cells].sum())
    credit = float(np.asarray(flows.service_pool_credit_at_cell)[cells].sum())
    assert draw > 0.0
    assert credit == pytest.approx(draw)

    service = next(s for s in measurement.services if s.commodity_id == commodity_id)
    gross = network.B.T @ np.asarray(flows.activity_realized, dtype=np.float64)
    gross_g = float(np.asarray(gross).ravel()[cells].sum())
    assert service.provided == pytest.approx(gross_g)
    # The same-quarter pool draw is already part of the production-input use;
    # netting ``provided`` by the pool credit would break this conservation.
    used_from_k = 0.0
    input_cell = np.asarray(network.input_cell)
    cell_commodity = np.asarray(network.cell_commodity)
    for demand_index, input_index in enumerate(np.asarray(network.demand_input_index)):
        if int(input_index) < 0:
            continue
        if int(cell_commodity[int(input_cell[int(input_index)])]) == g:
            used_from_k += float(flows.used[demand_index])
    assert service.used_productive == pytest.approx(used_from_k)
    assert service.used_productive >= draw
    assert service.provided > 0.0
    assert service.balance_residual == pytest.approx(0.0, abs=1e-8)
    assert abs(
        service.opening
        + service.provided
        + service.imports
        - (
            service.used_productive
            + service.used_logistics
            + service.used_household
            + service.used_other
            + service.exports
            + service.lost
            + service.closing
        )
    ) <= float(tolerance_for(service.provided, service.used_productive))


def test_service_measurement_does_not_sort_network_matrices(f2_two_ticks) -> None:
    network, _state, measured = f2_two_ticks
    opening, flows, summary, _measurement, state = measured[0]
    matrix_a = network.A.copy()
    matrix_b = network.B.copy()

    def unsort(matrix):
        for row in range(matrix.shape[0]):
            lo, hi = int(matrix.indptr[row]), int(matrix.indptr[row + 1])
            if hi - lo > 1:
                matrix.indices[lo:hi] = matrix.indices[lo:hi][::-1]
                matrix.data[lo:hi] = matrix.data[lo:hi][::-1]
                matrix.has_sorted_indices = False
                return True
        return False

    assert unsort(matrix_a) and unsort(matrix_b)
    patched = dataclasses.replace(network, A=matrix_a, B=matrix_b)
    before = (
        matrix_a.indptr.tobytes(),
        matrix_a.indices.tobytes(),
        matrix_a.data.tobytes(),
        matrix_b.indptr.tobytes(),
        matrix_b.indices.tobytes(),
        matrix_b.data.tobytes(),
    )
    measure_service_tick(opening, state, flows, patched, summary)
    after = (
        matrix_a.indptr.tobytes(),
        matrix_a.indices.tobytes(),
        matrix_a.data.tobytes(),
        matrix_b.indptr.tobytes(),
        matrix_b.indices.tobytes(),
        matrix_b.data.tobytes(),
    )
    assert before == after


def test_service_measurement_rejects_partial_missing_service_cells() -> None:
    fixture = _services_fixture()
    opening, flows, summary, _measurement, _controls, _activity = _measure(fixture)
    network = dataclasses.replace(
        fixture.network,
        commodity_ids=(*fixture.network.commodity_ids, "g16_housing_public_services"),
    )
    extended_flows = dataclasses.replace(
        flows,
        imports=np.append(flows.imports, 0.0),
        cmea_exports=np.append(flows.cmea_exports, 0.0),
        convertible_exports=np.append(flows.convertible_exports, 0.0),
    )
    with pytest.raises(ResearchGateError, match="no stock cell"):
        measure_service_tick(opening, fixture.state, extended_flows, network, summary)


def test_no_nonstockable_services_has_no_fake_zero_row() -> None:
    fixture = _housing_fixture()
    _opening, _flows, _summary, measurement, _controls, _activity = _measure(fixture)
    nonstockable = [
        commodity_id
        for commodity_id in fixture.network.commodity_ids
        if not commodity_spec(commodity_id).stockable
    ]
    assert nonstockable == []
    assert measurement.services == ()
    assert len(measurement.housing) == len(fixture.region_ids)
    assert measurement.housing[0].formal_completed == pytest.approx(1.2)
