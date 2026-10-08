"""P02 material network compiler: edges, weights, stages, determinism.

These tests build real networks with ``compile_material_network`` (no mocks)
and assert the pinned invariants: <=2 suppliers per demand cell, per-demand
weights summing to one, canonical edge order, no bank material cells, free
same-region transfers, stage immutability, and the Leontief minimum behaviour
including absent (zero-coefficient) inputs.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.material import (
    ORGANIZATION_TYPE_ORDER,
    CellOwnerKind,
    MaterialRouteSpec,
    OrganizationType,
    RoutePurpose,
    StockCellRef,
)
from hsm_lab.contract.schemas import ScenarioSpec
from hsm_lab.engine.network import produce_leontief
from hsm_lab.storage.checkpoint import network_static_hash
from tests.test_material import (
    NO_CAPITAL_COMMODITIES,
    Fixture,
    bank,
    hub,
    idle_source_tech,
    producer,
    retail,
    route,
    tech,
)


def test_ksh_outcome_cannot_be_bound_as_material_forcing() -> None:
    """Outcome/target variables remain outside the runtime forcing contract."""
    root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (root / "config" / "scenarios" / "intermediate8_external.json").read_text(
            encoding="utf-8"
        )
    )
    payload["forcing_bindings"][0]["variable_id"] = "gdp"
    with pytest.raises(ValidationError, match="forcing binding variable"):
        ScenarioSpec.model_validate(payload)


def _default_network() -> Fixture:
    """A two-region network with real producers, a hub and a retail node."""
    processor = producer(1, "food_processing", region="R0", capacity=10.0)
    seller = producer(2, "energy_generation", region="R1", capacity=10.0)
    wholesale = hub(3, region="R0")
    shop = retail(4, region="R0")
    technologies = [
        tech(
            "food_processing",
            inputs=(("energy", 0.5),),
            outputs=(("food", "ready", 1.0),),
        ),
        idle_source_tech("energy_generation", "energy"),
    ]
    return Fixture(
        [bank(0), processor, seller, wholesale, shop],
        technologies,
        region_ids=("R0", "R1"),
        commodities=NO_CAPITAL_COMMODITIES,
        ticks=2,
    )


def test_default_graph_weights_sum_to_one_and_at_most_two_suppliers() -> None:
    fixture = _default_network()
    network = fixture.network
    demand = np.asarray(network.edge_demand)
    weight = np.asarray(network.edge_weight)
    counts = np.bincount(demand, minlength=len(network.demand_cell))
    sums = np.bincount(demand, weights=weight, minlength=len(network.demand_cell))
    served = counts > 0
    assert int(counts.max()) <= 2
    assert np.allclose(sums[served], 1.0, atol=1e-9)
    # every served production/trader demand is backed by a real selling pool
    selling = {1, 2, 3, 5}  # output, wholesale, retail, import_pool
    assert set(np.unique(network.cell_pool[network.edge_source_cell])) <= selling


def test_default_graph_edge_order_is_canonical() -> None:
    network = _default_network().network
    assert np.array_equal(network.edge_id, np.arange(len(network.edge_id)))
    # edges are sorted by (source, destination, demand, purpose, source-stage)
    key = np.lexsort(
        (
            network.cell_stage[network.edge_source_cell],
            network.edge_purpose,
            network.edge_demand,
            network.edge_destination_cell,
            network.edge_source_cell,
        )
    )
    assert np.array_equal(key, np.arange(len(key)))
    # edge commodity/stage mirror the source cell (transfers never convert)
    assert np.array_equal(
        network.edge_commodity, network.cell_commodity[network.edge_source_cell]
    )
    assert np.array_equal(
        network.edge_stage, network.cell_stage[network.edge_source_cell]
    )


def test_every_served_supplier_has_at_least_one_buyer() -> None:
    fixture = _default_network()
    network = fixture.network
    state = fixture.state
    sources = np.unique(network.edge_source_cell)
    producer_type_codes = {
        ORGANIZATION_TYPE_ORDER.index(t)
        for t in (
            OrganizationType.INDUSTRIAL_SOE,
            OrganizationType.AGRICULTURAL_COOPERATIVE,
            OrganizationType.STATE_FARM,
            OrganizationType.TRANSPORT,
        )
    }
    producer_outputs = [
        int(network.org_output_cell[row])
        for row in range(len(state.organization_id))
        if int(state.organization_type[row]) in producer_type_codes
        and int(network.org_output_cell[row]) >= 0
    ]
    output_cells = {cell for cell in producer_outputs if network.cell_pool[cell] == 1}
    assert output_cells <= set(int(s) for s in sources)


def test_same_region_edges_are_free() -> None:
    network = _default_network().network
    source_region = network.cell_region[network.edge_source_cell]
    dest_region = network.cell_region[
        np.maximum(network.edge_destination_cell, 0)
    ]
    local = (network.edge_destination_cell >= 0) & (source_region == dest_region)
    assert np.all(network.edge_transport_per_unit[local] == 0.0)
    assert np.all(network.edge_transport_org[local] == -1)


def test_network_compile_is_deterministic_and_order_independent() -> None:
    first = _default_network().network
    second = _default_network().network
    assert network_static_hash(first) == network_static_hash(second)

    # an explicitly reversed route list compiles to the same canonical network
    routes = [
        route(1, "output", "food", "ready", 4, "retail", "food", "ready", RoutePurpose.RETAIL),
        route(
            2, "output", "energy", "standard", 3, "wholesale", "energy", "standard",
            RoutePurpose.PROCUREMENT,
        ),
    ]
    forward = Fixture(
        [
            bank(0),
            producer(1, "food_processing", capacity=10.0),
            producer(2, "energy_generation", capacity=10.0),
            hub(3),
            retail(4),
        ],
        [
            tech("food_processing", inputs=(("energy", 0.5),), outputs=(("food", "ready", 1.0),)),
            idle_source_tech("energy_generation", "energy"),
        ],
        commodities=NO_CAPITAL_COMMODITIES,
        routes=routes,
    )
    reversed_fixture = Fixture(
        [
            bank(0),
            producer(1, "food_processing", capacity=10.0),
            producer(2, "energy_generation", capacity=10.0),
            hub(3),
            retail(4),
        ],
        [
            tech("food_processing", inputs=(("energy", 0.5),), outputs=(("food", "ready", 1.0),)),
            idle_source_tech("energy_generation", "energy"),
        ],
        commodities=NO_CAPITAL_COMMODITIES,
        routes=list(reversed(routes)),
    )
    assert network_static_hash(forward.network) == network_static_hash(reversed_fixture.network)


# ---------------------------------------------------------------------------
# Leontief minimum: zero coefficients absent, disconnected inputs bind
# ---------------------------------------------------------------------------


def test_zero_coefficient_inputs_are_absent_and_disconnected_inputs_bind() -> None:
    # activity 0 needs two inputs; the second is unavailable, so it binds the
    # whole activity to zero.  activity 1 has no K rows at all -> unconstrained.
    available = np.array([5.0, 0.0])
    coefficient = np.array([1.0, 2.0])
    activity_index = np.array([0, 0])
    target = np.array([10.0, 7.0])
    realized, used = produce_leontief(available, coefficient, activity_index, target)
    assert realized[0] == pytest.approx(0.0)  # second required input is empty
    assert realized[1] == pytest.approx(7.0)  # no required inputs at all
    assert used[0] == pytest.approx(0.0)
    assert used[1] == pytest.approx(0.0)

    # with both inputs available the minimum is the binding ratio times coeff
    realized, used = produce_leontief(
        np.array([5.0, 100.0]), np.array([1.0, 2.0]), np.array([0, 0]), np.array([10.0])
    )
    assert realized[0] == pytest.approx(5.0)
    assert used[0] == pytest.approx(5.0)
    assert used[1] == pytest.approx(10.0)

    # feeding zero into the binding input legally yields zero output
    starved, used_starved = produce_leontief(
        np.array([0.0]), np.array([3.0]), np.array([0]), np.array([9.0])
    )
    assert starved[0] == pytest.approx(0.0)
    assert used_starved[0] == pytest.approx(0.0)


@pytest.mark.parametrize(
    "available, coefficient, index, target",
    [
        (np.array([-1.0]), np.array([1.0]), np.array([0]), np.array([1.0])),
        (np.array([np.nan]), np.array([1.0]), np.array([0]), np.array([1.0])),
        (np.array([1.0]), np.array([0.0]), np.array([0]), np.array([1.0])),
        (np.array([1.0]), np.array([1.0]), np.array([5]), np.array([1.0])),
        (np.array([1.0, 1.0]), np.array([1.0]), np.array([0]), np.array([1.0])),
        (np.array([1.0]), np.array([1.0]), np.array([0]), np.array([-1.0])),
    ],
)
def test_produce_leontief_rejects_bad_inputs(available, coefficient, index, target) -> None:
    with pytest.raises(ValueError):
        produce_leontief(available, coefficient, index, target)


# ---------------------------------------------------------------------------
# Bank / retail / route validation
# ---------------------------------------------------------------------------


def test_banks_hold_no_material_cells() -> None:
    fixture = _default_network()
    network = fixture.network
    state = fixture.state
    bank_ids = {
        int(state.organization_id[row])
        for row in range(len(state.organization_id))
        if int(state.organization_type[row])
        == ORGANIZATION_TYPE_ORDER.index(OrganizationType.BANK)
    }
    org_cells = network.cell_owner_kind == 0
    assert bank_ids
    assert not (set(int(v) for v in network.cell_owner_id[org_cells]) & bank_ids)
    # the import pool is national (region -1), never folded into a region
    treasury = network.cell_owner_kind == 3
    assert np.all(network.cell_region[treasury] == -1)


def test_retail_only_stocks_ready_food() -> None:
    network = _default_network().network
    retail_cells = network.cell_pool == 3  # retail pool code
    food_g = network.commodity_ids.index("food")
    food_retail = retail_cells & (network.cell_commodity == food_g)
    assert food_retail.any()
    assert np.all(network.cell_stage[food_retail] == 2)  # ready only, never raw


def test_retail_route_must_match_purpose() -> None:
    bad = route(
        1, "output", "food", "ready", 3, "retail", "food", "ready",
        RoutePurpose.INTERMEDIATE,
    )
    with pytest.raises(ConfigError):
        Fixture(
            [bank(0), producer(1, "food_processing", capacity=10.0), hub(2), retail(3)],
            [tech("food_processing", inputs=(("energy", 0.5),), outputs=(("food", "ready", 1.0),))],
            commodities=NO_CAPITAL_COMMODITIES,
            routes=[bad],
        )


def test_route_weights_must_sum_to_one() -> None:
    routes = [
        route(1, "output", "food", "ready", 3, "retail", "food", "ready", RoutePurpose.RETAIL, 0.6),
        route(
            2, "wholesale", "food", "ready", 3, "retail", "food", "ready",
            RoutePurpose.RETAIL,
            0.3,
        ),
    ]
    with pytest.raises(ConfigError, match="sum"):
        Fixture(
            [bank(0), producer(1, "food_processing", capacity=10.0), hub(2), retail(3)],
            [tech("food_processing", inputs=(("energy", 0.5),), outputs=(("food", "ready", 1.0),))],
            commodities=NO_CAPITAL_COMMODITIES,
            routes=routes,
        )


def test_at_most_two_suppliers_per_demand_cell() -> None:
    routes = [
        route(
            1, "output", "food", "ready", 3, "retail", "food", "ready",
            RoutePurpose.RETAIL,
            0.34,
        ),
        route(
            2, "wholesale", "food", "ready", 3, "retail", "food", "ready",
            RoutePurpose.RETAIL,
            0.33,
        ),
        route(
            4, "wholesale", "food", "ready", 3, "retail", "food", "ready",
            RoutePurpose.RETAIL,
            0.33,
        ),
    ]
    with pytest.raises(ConfigError, match="suppliers"):
        Fixture(
            [bank(0), producer(1, "food_processing", capacity=10.0), hub(2), retail(3), hub(4)],
            [tech("food_processing", inputs=(("energy", 0.5),), outputs=(("food", "ready", 1.0),))],
            commodities=NO_CAPITAL_COMMODITIES,
            routes=routes,
        )


def test_stage_changing_route_is_refused_at_construction() -> None:
    with pytest.raises((ConfigError, ValidationError), match="stage"):
        route(1, "output", "food", "raw", 3, "retail", "food", "ready", RoutePurpose.RETAIL)


def test_unknown_route_endpoint_is_refused() -> None:
    bad_source = StockCellRef(
        owner_kind=CellOwnerKind.ORGANIZATION,
        organization_id=99,
        pool="output",
        commodity_id="food",
        stage="ready",
    )
    bad = MaterialRouteSpec(
        source=bad_source,
        destination=StockCellRef(
            owner_kind=CellOwnerKind.ORGANIZATION,
            organization_id=3,
            pool="retail",
            commodity_id="food",
            stage="ready",
        ),
        purpose=RoutePurpose.RETAIL,
        weight=1.0,
    )
    with pytest.raises(ConfigError):
        Fixture(
            [bank(0), producer(1, "food_processing", capacity=10.0), hub(2), retail(3)],
            [tech("food_processing", inputs=(("energy", 0.5),), outputs=(("food", "ready", 1.0),))],
            commodities=NO_CAPITAL_COMMODITIES,
            routes=[bad],
        )
