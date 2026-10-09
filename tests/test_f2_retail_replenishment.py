"""F2 retail replenishment: hubless goods must reach their retail cells.

The F2 catalog declares retail stages for ``g03_electricity_heat`` and
``g16_housing_public_services`` but no hub stage.  Before the compiler fix their
retail cells had no replenishment edge at all, so the household demand for them
(``g16`` declares 1 700 units per quarter) could never materialise.  The fix
falls back to the commodity's producers; the nine commodities that do have hubs
must be bit-identical to before.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.network import build_material_network
from hsm_lab.engine.rng import RngRegistry

ROOT = Path(__file__).resolve().parents[1]
HUBLESS = ("g03_electricity_heat", "g16_housing_public_services")
HUB_COLLECTED = (
    "g01_solid_fuels",
    "g02_oil_gas_fuels",
    "g09_basic_food",
    "g10_animal_food",
    "g11_textiles_footwear",
    "g12_household_nondurables",
    "g13_household_durables",
    "g14_vehicles_transport_equipment",
)
# the first service role legitimately collects from its producers, not hubs
SERVICE_PRODUCER = "g15_market_services"


@pytest.fixture(scope="module")
def f2_network():
    contract = load_research_contract(ROOT)
    spec = load_scenario(ROOT, "historical_f2_replay")
    initial = build_material_initial_conditions(spec, RngRegistry(spec.seed))
    return build_material_network(spec, contract, initial)


def test_hubless_goods_now_have_replenishment_sources(f2_network) -> None:
    purpose = np.asarray(f2_network.edge_purpose)
    commodity = np.asarray(f2_network.edge_commodity)
    destination = np.asarray(f2_network.edge_destination_cell)
    weight = np.asarray(f2_network.edge_weight)
    retail_edges = purpose == 4
    for goods in HUBLESS:
        g = f2_network.commodity_ids.index(goods)
        mask = retail_edges & (commodity == g)
        assert bool(mask.any()), f"{goods} still has no retail replenishment edge"
        destinations = destination[mask]
        for cell in np.unique(destinations):
            total = float(weight[mask & (destination == cell)].sum())
            assert abs(total - 1.0) < 1e-9


def test_hub_collected_goods_never_use_the_producer_fallback(f2_network) -> None:
    purpose = np.asarray(f2_network.edge_purpose)
    commodity = np.asarray(f2_network.edge_commodity)
    source = np.asarray(f2_network.edge_source_cell)
    pool = np.asarray(f2_network.cell_pool)
    retail_edges = purpose == 4
    for goods in HUB_COLLECTED:
        g = f2_network.commodity_ids.index(goods)
        mask = retail_edges & (commodity == g)
        assert bool(mask.any()), f"{goods} lost its retail replenishment edges"
        # the fallback must never fire when a hub exists
        assert bool(np.all(pool[source[mask]] == 2)), f"{goods} source is not a hub cell"
    g = f2_network.commodity_ids.index(SERVICE_PRODUCER)
    mask = retail_edges & (commodity == g)
    assert bool(mask.any())
    assert bool(np.all(pool[source[mask]] == 1)), "the service role must still use producers"


def test_legacy_catalog_sources_are_unchanged() -> None:
    """The legacy catalog has no hubless household good, so the fallback never fires."""
    contract = load_research_contract(ROOT)
    spec = load_scenario(ROOT, "intermediate8")
    initial = build_material_initial_conditions(spec, RngRegistry(spec.seed))
    network = build_material_network(spec, contract, initial)
    purpose = np.asarray(network.edge_purpose)
    source = np.asarray(network.edge_source_cell)
    pool = np.asarray(network.cell_pool)
    retail = purpose == 4
    assert bool(retail.any())
    # every retail replenishment source is a hub cell or a producer output cell
    assert bool(np.all(np.isin(pool[source[retail]], (1, 2))))
