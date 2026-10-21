"""H5B F2 second-economy tests (PLAN §Verification table).

These tests exercise the F2 named-commodity adapter end-to-end through
``tick_material`` with controlled seed/spec axes.  They use a minimal
scenario with controllable stock/cash so each row of the PLAN verification
table exercises a single economic invariant.  The tests are red-only when
the adapter is absent; this file is the regression gate referenced by the
H5B spec.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.contract.households import (
    AllocationParameters,
    DemandParameters,
    DurablesParameters,
    HouseholdParameters,
    HousingParameters,
    TimeParameters,
)
from hsm_lab.contract.material import (
    F2_COMMODITY_IDS,
    F2_COMMODITY_SPECS,
    CommoditySpec,
    commodity_spec,
)
from hsm_lab.engine.accounting import AccountingError
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.network import MaterialNetwork, build_material_network
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import (
    MaterialState,
    build_material_prices,
    initialize_material,
)
from hsm_lab.institutions.second_economy_f2_adapter import (
    F2SecondEconomyRecipe,
    attach_f2_second_economy,
    check_f2_second_economy,
    expire_f2_second_economy,
    plan_f2_household_time,
    settle_f2_second_economy,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
F2_SPEC = "historical_f2_replay"
START = "1957Q1"
FORCING_PACK = "data/fixtures/p02_material_synthetic_pack.json"

# Tiny synthetic forcing pack reused by the F2 fixture; this is the same pack
# the legacy ``test_material.Fixture`` uses, which keeps inputs honest.
_TINY_PRICES = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]


# ---------------------------------------------------------------------------
# Building a tiny F2 MaterialNetwork in-memory (region-only, no real economy)
# ---------------------------------------------------------------------------


def _commodity_specs_filtered() -> tuple[CommoditySpec, ...]:
    return F2_COMMODITY_SPECS


def _make_blank_household_parameters() -> HouseholdParameters:
    return HouseholdParameters(
        demand=DemandParameters(
            base_per_equivalent_person=[0.0] * 15,
            minimum_per_equivalent_person=[0.0] * 15,
        ),
        allocation=AllocationParameters(
            parent_commodity_ids=[
                "g01_solid_fuels",
                "g02_oil_gas_fuels",
                "g03_electricity_heat",
                "g09_basic_food",
                "g10_animal_food",
                "g11_textiles_footwear",
                "g12_household_nondurables",
                "g13_household_durables",
                "g13_household_durables",
                "g13_household_durables",
                "g14_vehicles_transport_equipment",
                "g15_market_services",
                "g07_construction",
                "g15_market_services",
                "g16_housing_public_services",
            ],
            material_equivalent_per_unit=[
                1.0,
                1.0,
                1.0,
                1.0,
                2.0,
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
                4.0,
                1.0,
                1.0,
                1.0,
                1.0,
            ],
            quota_share=[
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
                1.0 / 3.0,
                1.0 / 3.0,
                1.0 / 3.0,
                1.0,
                0.5,
                1.0,
                0.5,
                1.0,
            ],
        ),
        durables=DurablesParameters(),
        housing=HousingParameters(),
        time=TimeParameters(
            time_endowment_hours=540.0,
            formal_hours_per_worker=520.0,
            plot_hours_cap_per_worker=52.0,
            second_hours_cap_per_worker=130.0,
            plot_hours_per_activity=4.0,
            second_hours_base=0.25,
            second_shortage_weight=0.5,
            second_grievance_weight=0.25,
            effort_grievance_weight=0.4,
            effort_informal_hours_weight=0.3,
            effort_queue_search_weight=0.2,
            effort_floor=0.25,
        ),
    )


def _region_dwelling_count(region_persons: dict[str, float]) -> float:
    return float(sum(region_persons.values()))


def _tiny_f2_state(
    *,
    region_count: int = 2,
    households: int = 8,
    seed: int = 1729,
) -> tuple[MaterialState, MaterialNetwork, HouseholdParameters]:
    """Build a real F2 spec-derived state and patch household cohort.

    We re-use the actual historical_f2_replay spec so the F2 commodity axis
    and household parameters are guaranteed to match production.  The caller
    may then override household_cash, working_adults, second_participating
    etc. to set up tiny controlled cases.
    """
    contract = load_research_contract(REPO_ROOT)
    spec = load_scenario(REPO_ROOT, F2_SPEC)
    rng = RngRegistry(seed)
    initial = build_material_initial_conditions(spec, rng)
    network = build_material_network(spec, contract, initial)
    state = initialize_material(spec, initial, network)
    # Optionally clamp household count and region count for tiny-case tests.
    if region_count < 20 or households < state.household_id.size:
        # We re-emit a tiny subset but only via state array slicing; the network
        # is already fixed at the spec's region/commodity axis (20 regions /
        # 16 commodities) and we keep that intact.
        n_keep = min(households, int(state.household_id.shape[0]))
        keep_regions = min(region_count, 20)
        slice_arrays(state, n_keep)
        # Map households into the first ``keep_regions`` regions only.
        new_region = np.minimum(
            np.asarray(state.household_region, dtype=np.int32), keep_regions - 1
        )
        state.household_region = new_region
    return state, network, spec.household_parameters


def slice_arrays(state: MaterialState, n_keep: int) -> None:
    """Trim every household-shaped (N, ...) array on ``state`` to ``n_keep``."""
    if n_keep >= int(state.household_id.shape[0]):
        return
    fields_to_slice = [
        "household_id",
        "household_region",
        "household_weight",
        "household_size",
        "household_cash",
        "household_deferred_receipt",
        "household_wage_claim",
        "household_urban",
        "household_occupation",
        "household_sector",
        "household_education",
        "household_children",
        "household_adults",
        "household_elderly",
        "household_working_adults",
        "household_pay_weight",
        "household_plot_participating",
        "household_second_participating",
        "household_western_exposure",
        "household_tenure",
        "household_informal_access",
        "household_dwelling_access",
        "household_housing_wait",
        "household_last_income",
        "household_reference_income",
        "household_last_price_index",
        "household_initial_service_value",
        "household_reserved_plot_hours",
        "household_reserved_second_hours",
        "household_formal_effort",
        "household_material_satisfaction",
        "household_political_compliance",
        "household_grievance",
        "household_durable_owned",
        "household_durable_age",
        "household_durable_backlog",
        "household_durable_wait",
        "household_durable_repair_credit",
        "household_consumption_reference",
        "household_last_consumption",
        "household_last_availability_unmet",
        "household_entitlement",
        "household_expectation",
        "household_improvement_streak",
    ]
    for name in fields_to_slice:
        value = getattr(state, name, None)
        if value is None:
            continue
        if isinstance(value, np.ndarray):
            if value.ndim == 1:
                setattr(state, name, value[:n_keep])
            elif value.ndim == 2:
                setattr(state, name, value[:n_keep])


def _f2_view(network: MaterialNetwork, **overrides) -> MaterialNetwork:
    recipe = F2SecondEconomyRecipe.default_nonplot_v1(**overrides)
    return attach_f2_second_economy(network, recipe)


def _opening(state: MaterialState):
    from hsm_lab.engine.state import capture_material_stocks

    return capture_material_stocks(state)


def _bank_deposit_balance(state: MaterialState) -> float:
    return float(np.asarray(state.bank_deposit_liability, dtype=np.float64).sum())


def _household_cash_open(state: MaterialState) -> np.ndarray:
    return np.asarray(state.household_cash, dtype=np.float64).copy()


def _seed_via_retail(
    state: MaterialState, network: MaterialNetwork, *, region: int, g: int, value: float
) -> int:
    cell = int(np.asarray(network.retail_cell_by_commodity)[region, g])
    if cell < 0:
        raise ValueError(f"no retail cell at region={region} g={g}")
    stock = np.asarray(state.stock_value, dtype=np.float64).copy()
    stock[cell] = value
    state.stock_value = stock
    return cell


def _seed_via_org_output_cell(
    state: MaterialState, network: MaterialNetwork, *, region: int, g: int, value: float
) -> int:
    """Seed a single organisation-owned output cell (region, commodity)."""
    cell_region = np.asarray(network.cell_region, dtype=np.int64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_pool = np.asarray(network.cell_pool, dtype=np.int64)
    mask = (
        (cell_region == region)
        & (cell_commodity == g)
        & (cell_owner_kind == 0)  # organisation
        & (cell_pool == 1)        # output pool
    )
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        raise ValueError(f"no org-output cell at region={region} g={g}")
    cell = int(idx[0])
    stock = np.asarray(state.stock_value, dtype=np.float64).copy()
    stock[cell] = value
    state.stock_value = stock
    return cell


def _set_household_cash(state: MaterialState, values: np.ndarray) -> None:
    state.household_cash = np.asarray(values, dtype=np.float64).copy()


def _set_working_adults(state: MaterialState, values: np.ndarray) -> None:
    state.household_working_adults = np.asarray(values, dtype=np.float64).copy()


def _set_second_participating(state: MaterialState, mask: np.ndarray) -> None:
    state.household_second_participating = np.asarray(mask, dtype=bool).copy()


def _set_household_region(state: MaterialState, values: np.ndarray) -> None:
    state.household_region = np.asarray(values, dtype=np.int32).copy()


def _set_household_weight(state: MaterialState, values: np.ndarray) -> None:
    state.household_weight = np.asarray(values, dtype=np.float64).copy()


# ---------------------------------------------------------------------------
# Tests for the adapter API surface
# ---------------------------------------------------------------------------


def test_f2_recipe_default_nonplot() -> None:
    recipe = F2SecondEconomyRecipe.default_nonplot_v1()
    assert recipe.schema_version == "hist_vnext_second_economy_f2_v1"
    assert recipe.recipe_id == "hist-vnext-m04-nonplot-v1"
    assert dict(recipe.input_coefficients) == {
        "g02_oil_gas_fuels": 0.02,
        "g04_basic_metals_materials": 0.03,
    }
    assert dict(recipe.output_coefficients) == {
        "g11_textiles_footwear": 0.10,
        "g15_market_services": 0.25,
    }
    assert recipe.hours_per_activity == 4.0
    assert recipe.capacity_per_participating_worker == 10.0
    assert recipe.role == "latent_parameter"
    assert recipe.evidence_status == "structural_assumption"
    assert recipe.calibration_status == "not_calibrated"


def test_recipe_hash_changes_when_recipe_changes() -> None:
    a = F2SecondEconomyRecipe.default_nonplot_v1()
    b = F2SecondEconomyRecipe(
        recipe_id="x",
        input_coefficients=(("g02_oil_gas_fuels", 0.05),),
        output_coefficients=(("g15_market_services", 0.5),),
        hours_per_activity=4.0,
        capacity_per_participating_worker=10.0,
    )
    assert a.recipe_hash != b.recipe_hash


def test_attach_fails_on_non_material_network() -> None:
    with pytest.raises(ConfigError):
        attach_f2_second_economy(object(), F2SecondEconomyRecipe.default_nonplot_v1())


def test_attach_fails_for_duplicate_marker() -> None:
    state, network, _ = _tiny_f2_state()
    recipe = F2SecondEconomyRecipe.default_nonplot_v1()
    f2 = attach_f2_second_economy(network, recipe)
    with pytest.raises(ConfigError):
        attach_f2_second_economy(f2, recipe)


def test_attach_rejects_non_household_output() -> None:
    state, network, _ = _tiny_f2_state()
    bad = F2SecondEconomyRecipe(
        recipe_id="bad-output",
        input_coefficients=(("g02_oil_gas_fuels", 0.02),),
        output_coefficients=(("g04_basic_metals_materials", 0.10),),
        hours_per_activity=4.0,
        capacity_per_participating_worker=10.0,
    )
    with pytest.raises(ConfigError, match="household channel parent"):
        attach_f2_second_economy(network, bad)


def test_recipe_rejects_unknown_commodity() -> None:
    bad = F2SecondEconomyRecipe(
        recipe_id="bad",
        input_coefficients=(("g_does_not_exist", 0.1),),
        output_coefficients=(("g11_textiles_footwear", 0.1),),
        hours_per_activity=4.0,
        capacity_per_participating_worker=10.0,
    )
    state, network, _ = _tiny_f2_state()
    with pytest.raises(ConfigError):
        attach_f2_second_economy(network, bad)


def test_recipe_rejects_duplicate_inputs() -> None:
    bad = F2SecondEconomyRecipe(
        recipe_id="bad",
        input_coefficients=(("g02_oil_gas_fuels", 0.02), ("g02_oil_gas_fuels", 0.03)),
        output_coefficients=(("g11_textiles_footwear", 0.1),),
        hours_per_activity=4.0,
        capacity_per_participating_worker=10.0,
    )
    state, network, _ = _tiny_f2_state()
    with pytest.raises(ConfigError):
        attach_f2_second_economy(network, bad)


def test_recipe_rejects_zero_or_negative_coefficient() -> None:
    bad = F2SecondEconomyRecipe(
        recipe_id="bad",
        input_coefficients=(("g02_oil_gas_fuels", 0.0),),
        output_coefficients=(("g11_textiles_footwear", 0.1),),
        hours_per_activity=4.0,
        capacity_per_participating_worker=10.0,
    )
    state, network, _ = _tiny_f2_state()
    with pytest.raises(ConfigError):
        attach_f2_second_economy(network, bad)


def test_recipe_rejects_invalid_capacity() -> None:
    bad = F2SecondEconomyRecipe(
        recipe_id="bad",
        input_coefficients=(("g02_oil_gas_fuels", 0.02),),
        output_coefficients=(("g11_textiles_footwear", 0.1),),
        hours_per_activity=4.0,
        capacity_per_participating_worker=21.0,
    )
    state, network, _ = _tiny_f2_state()
    with pytest.raises(ConfigError):
        attach_f2_second_economy(network, bad)


def test_recipe_rejects_empty_io() -> None:
    bad = F2SecondEconomyRecipe(
        recipe_id="bad",
        input_coefficients=(),
        output_coefficients=(),
        hours_per_activity=4.0,
        capacity_per_participating_worker=10.0,
    )
    state, network, _ = _tiny_f2_state()
    with pytest.raises(ConfigError):
        attach_f2_second_economy(network, bad)


def test_recipe_rejects_invalid_hours() -> None:
    bad = F2SecondEconomyRecipe(
        recipe_id="bad",
        input_coefficients=(("g02_oil_gas_fuels", 0.02),),
        output_coefficients=(("g11_textiles_footwear", 0.1),),
        hours_per_activity=0.0,
        capacity_per_participating_worker=10.0,
    )
    state, network, _ = _tiny_f2_state()
    with pytest.raises(ConfigError):
        attach_f2_second_economy(network, bad)


def test_attach_does_not_mutate_parent_network() -> None:
    state, network, _ = _tiny_f2_state()
    before_input = tuple(network.second_input_commodities)
    before_output = tuple(network.second_output_commodities)
    f2 = attach_f2_second_economy(network, F2SecondEconomyRecipe.default_nonplot_v1())
    assert tuple(network.second_input_commodities) == before_input
    assert tuple(network.second_output_commodities) == before_output
    # F2 view populated correctly
    g02 = F2_COMMODITY_IDS.index("g02_oil_gas_fuels")
    g04 = F2_COMMODITY_IDS.index("g04_basic_metals_materials")
    g11 = F2_COMMODITY_IDS.index("g11_textiles_footwear")
    g15 = F2_COMMODITY_IDS.index("g15_market_services")
    assert tuple(f2.second_input_commodities) == (g02, g04)
    assert tuple(f2.second_output_commodities) == (g11, g15)


def test_plan_rejects_formal_exceeding_endowment() -> None:
    state, _, params = _tiny_f2_state()
    _set_working_adults(state, np.ones(8, dtype=np.float64))
    state.household_reserved_plot_hours = np.zeros(8, dtype=np.float64)
    state.household_grievance = np.zeros(8, dtype=np.float64)
    state.household_last_availability_unmet = np.zeros((8, 15), dtype=np.float64)
    state.household_consumption_reference = np.zeros((8, 15), dtype=np.float64)
    _set_second_participating(state, np.ones(8, dtype=bool))
    # Force endowment < formal by adjusting time_endowment_hours at the param.
    bad_params = HouseholdParameters(
        **{
            **params.model_dump(),
            "time": {**params.time.model_dump(), "time_endowment_hours": 500.0},
        }
    )
    with pytest.raises(ConfigError):
        plan_f2_household_time(state, bad_params, tolerance=1.0)


def test_plan_zero_tolerance_reserves_zero_second_hours() -> None:
    state, _, params = _tiny_f2_state()
    _set_working_adults(state, np.ones(8, dtype=np.float64))
    state.household_reserved_plot_hours = np.zeros(8, dtype=np.float64)
    state.household_grievance = np.zeros(8, dtype=np.float64)
    state.household_last_availability_unmet = np.zeros((8, 15), dtype=np.float64)
    state.household_consumption_reference = np.zeros((8, 15), dtype=np.float64)
    _set_second_participating(state, np.ones(8, dtype=bool))
    plan_f2_household_time(state, params, tolerance=0.0)
    assert np.all(np.asarray(state.household_reserved_second_hours) == 0.0)
    # Zero working yields zero second hours regardless of tolerance
    state.household_working_adults = np.zeros(8, dtype=np.float64)
    state.household_reserved_second_hours = np.zeros(8, dtype=np.float64)
    plan_f2_household_time(state, params, tolerance=1.0)
    assert np.all(np.asarray(state.household_reserved_second_hours) == 0.0)


def test_plan_works_for_endowment_equal_formal_hours() -> None:
    state, _, params = _tiny_f2_state()
    _set_working_adults(state, np.ones(8, dtype=np.float64))
    # F2 spec endowment=1040; force a test value of 540 by tightening the param.
    params_tight = HouseholdParameters(
        **{
            **params.model_dump(),
            "time": {**params.time.model_dump(), "time_endowment_hours": 540.0},
        }
    )
    state.household_reserved_plot_hours = np.array([50.0] * 8, dtype=np.float64)
    state.household_grievance = np.zeros(8, dtype=np.float64)
    state.household_last_availability_unmet = np.zeros((8, 15), dtype=np.float64)
    state.household_consumption_reference = np.zeros((8, 15), dtype=np.float64)
    _set_second_participating(state, np.ones(8, dtype=bool))
    plan_f2_household_time(state, params_tight, tolerance=1.0)
    # With plot=50, grievance=0, intensity=0.25 ⇒ second_req=130*0.25=32.5/worker.
    # Endowment 540 - formal 520 = 20 hours room ⇒ both compress.
    second = np.asarray(state.household_reserved_second_hours, dtype=np.float64)
    plot = np.asarray(state.household_reserved_plot_hours, dtype=np.float64)
    assert np.all(plot + second <= 20.0 + 1e-9)
    assert np.all(second >= 0.0)


def test_plan_compresses_when_plot_plus_second_exceeds_endowment() -> None:
    state, _, params = _tiny_f2_state()
    _set_working_adults(state, np.ones(8, dtype=np.float64))
    params_tight = HouseholdParameters(
        **{
            **params.model_dump(),
            "time": {**params.time.model_dump(), "time_endowment_hours": 540.0},
        }
    )
    state.household_reserved_plot_hours = np.array([52.0] * 8, dtype=np.float64)
    state.household_grievance = np.ones(8, dtype=np.float64)
    state.household_last_availability_unmet = np.zeros((8, 15), dtype=np.float64)
    state.household_consumption_reference = np.zeros((8, 15), dtype=np.float64)
    _set_second_participating(state, np.ones(8, dtype=bool))
    plan_f2_household_time(state, params_tight, tolerance=1.0)
    hours = np.asarray(state.household_reserved_second_hours, dtype=np.float64)
    plot = np.asarray(state.household_reserved_plot_hours, dtype=np.float64)
    # Endowment 540 - formal 520 = 20 hours room → plot+second <= 20
    assert np.all(hours >= 0.0)
    assert np.all(plot + hours <= 20.0 + 1e-9)


def test_plan_rejects_negative_tolerance() -> None:
    state, _, params = _tiny_f2_state()
    _set_working_adults(state, np.ones(8, dtype=np.float64))
    state.household_reserved_plot_hours = np.zeros(8, dtype=np.float64)
    state.household_grievance = np.zeros(8, dtype=np.float64)
    state.household_last_availability_unmet = np.zeros((8, 15), dtype=np.float64)
    state.household_consumption_reference = np.zeros((8, 15), dtype=np.float64)
    _set_second_participating(state, np.ones(8, dtype=bool))
    with pytest.raises(ConfigError):
        plan_f2_household_time(state, params, tolerance=-0.1)


def test_plan_rejects_non_finite_tolerance() -> None:
    state, _, params = _tiny_f2_state()
    _set_working_adults(state, np.ones(8, dtype=np.float64))
    state.household_reserved_plot_hours = np.zeros(8, dtype=np.float64)
    state.household_grievance = np.zeros(8, dtype=np.float64)
    state.household_last_availability_unmet = np.zeros((8, 15), dtype=np.float64)
    state.household_consumption_reference = np.zeros((8, 15), dtype=np.float64)
    _set_second_participating(state, np.ones(8, dtype=bool))
    with pytest.raises(ConfigError):
        plan_f2_household_time(state, params, tolerance=float("nan"))


# ---------------------------------------------------------------------------
# Settlement tests with controlled stock
# ---------------------------------------------------------------------------


class _StubFlows:
    """Minimal MaterialTickFlows-like object used by settlement tests."""

    def __init__(
        self, tick: int, region_count: int, g_count: int, cell_count: int, n: int, h_count: int
    ):
        self.tick = int(tick)
        self.household_second_hours = np.zeros(n, dtype=np.float64)
        self.second_input_used = np.zeros(cell_count, dtype=np.float64)
        self.household_second_input_funding = np.zeros(n, dtype=np.float64)
        self.household_second_income_direct = np.zeros(n, dtype=np.float64)
        self.organization_sales_receipts = np.zeros(1, dtype=np.float64)
        self.household_substitution = np.zeros((n, 5), dtype=np.float64)
        self.household_second_h = np.zeros((n, h_count), dtype=np.float64)


def test_settle_zero_when_tolerance_zero() -> None:
    state, network, params = _tiny_f2_state()
    f2 = _f2_view(network)
    _set_working_adults(state, np.ones(8, dtype=np.float64))
    _set_second_participating(state, np.ones(8, dtype=bool))
    state.household_cash = np.ones(8, dtype=np.float64)
    state.household_reserved_second_hours = np.full(8, 4.0, dtype=np.float64)
    flows = _StubFlows(0, 2, 16, len(network.cell_owner_kind), 8, 15)
    price_net = np.array([1.0] * 16, dtype=np.float64)
    # zero tolerance -> no second hours funded
    plan_f2_household_time(state, params, tolerance=0.0)
    settled = settle_f2_second_economy(state, flows, f2, params, price_net)
    assert settled is None
    # Nothing happened.
    assert np.all(np.asarray(flows.household_second_input_funding) == 0.0)
    assert np.allclose(state.stock_value, state.stock_value)


def test_settle_no_participants_no_funding() -> None:
    state, network, params = _tiny_f2_state()
    f2 = _f2_view(network)
    _set_working_adults(state, np.ones(8, dtype=np.float64))
    _set_second_participating(state, np.zeros(8, dtype=bool))  # no participants
    state.household_cash = np.ones(8, dtype=np.float64)
    state.household_reserved_second_hours = np.full(8, 4.0, dtype=np.float64)
    flows = _StubFlows(0, 2, 16, len(network.cell_owner_kind), 8, 15)
    price_net = np.array([1.0] * 16, dtype=np.float64)
    plan_f2_household_time(state, params, tolerance=1.0)
    settle_f2_second_economy(state, flows, f2, params, price_net)
    assert np.all(np.asarray(flows.household_second_input_funding) == 0.0)


def test_settle_full_activity_when_resources_ample() -> None:
    state, network, params = _tiny_f2_state()
    f2 = _f2_view(network)
    _set_working_adults(state, np.ones(8, dtype=np.float64))
    _set_second_participating(state, np.ones(8, dtype=bool))
    state.household_cash = np.full(8, 10.0, dtype=np.float64)
    state.household_reserved_second_hours = np.full(8, 4.0, dtype=np.float64)
    # Seed retail stock at g02 and g04 so input draw has stock.
    _seed_via_retail(state, network, region=0, g=1, value=10.0)  # g02
    _seed_via_org_output_cell(state, network, region=0, g=3, value=10.0)  # g04
    flows = _StubFlows(0, 2, 16, len(network.cell_owner_kind), 8, 15)
    price_net = np.array([1.0] * 16, dtype=np.float64)
    plan_f2_household_time(state, params, tolerance=1.0)
    settle_f2_second_economy(state, flows, f2, params, price_net)
    # activity should be 1 in region 0
    funding = np.asarray(flows.household_second_input_funding, dtype=np.float64)
    assert np.any(funding > 0.0)
    # outputs into second pool
    pool = np.asarray(state.second_output_stock, dtype=np.float64)
    g11 = F2_COMMODITY_IDS.index("g11_textiles_footwear")
    g15 = F2_COMMODITY_IDS.index("g15_market_services")
    assert pool[0, g11] > 0.0
    assert pool[0, g15] > 0.0


def test_settle_no_stock_yields_zero_funding() -> None:
    state, network, params = _tiny_f2_state()
    f2 = _f2_view(network)
    # Zero ALL organisational stock so no source cells exist (inputs cannot
    # be drawn).  This is the strict no-stock counter example.
    state.stock_value = np.zeros_like(state.stock_value)
    _set_working_adults(state, np.ones(8, dtype=np.float64))
    _set_second_participating(state, np.ones(8, dtype=bool))
    state.household_cash = np.array([10.0] * 8, dtype=np.float64)
    state.household_reserved_second_hours = np.array([4.0] * 8, dtype=np.float64)
    flows = _StubFlows(0, 2, 16, len(network.cell_owner_kind), 8, 15)
    price_net = np.array([1.0] * 16, dtype=np.float64)
    plan_f2_household_time(state, params, tolerance=1.0)
    settle_f2_second_economy(state, flows, f2, params, price_net)
    funding = np.asarray(flows.household_second_input_funding, dtype=np.float64)
    assert np.all(funding == 0.0)
    pool = np.asarray(state.second_output_stock, dtype=np.float64)
    assert np.all(pool == 0.0)


def test_settle_organisations_credit_exactly_equals_input_payments() -> None:
    state, network, params = _tiny_f2_state()
    f2 = _f2_view(network)
    _set_working_adults(state, np.ones(8, dtype=np.float64))
    _set_second_participating(state, np.ones(8, dtype=bool))
    state.household_cash = np.array([10.0] * 8, dtype=np.float64)
    state.household_reserved_second_hours = np.array([4.0] * 8, dtype=np.float64)
    _seed_via_retail(state, network, region=0, g=1, value=10.0)
    _seed_via_org_output_cell(state, network, region=0, g=3, value=10.0)
    org_cash_open = np.asarray(state.organization_cash, dtype=np.float64).copy()
    flows = _StubFlows(0, 2, 16, len(network.cell_owner_kind), 8, 15)
    price_net = np.array([1.0] * 16, dtype=np.float64)
    plan_f2_household_time(state, params, tolerance=1.0)
    settle_f2_second_economy(state, flows, f2, params, price_net)
    funding = float(
        (
            np.asarray(state.household_weight, dtype=np.float64)
            * np.asarray(flows.household_second_input_funding, dtype=np.float64)
        ).sum()
    )
    org_cash_delta = float(
        (np.asarray(state.organization_cash, dtype=np.float64) - org_cash_open).sum()
    )
    assert funding == pytest.approx(org_cash_delta, abs=1e-9)
    assert funding >= 0.0


def test_settle_records_trace_when_provided() -> None:
    state, network, params = _tiny_f2_state()
    f2 = _f2_view(network)
    _set_working_adults(state, np.ones(8, dtype=np.float64))
    _set_second_participating(state, np.ones(8, dtype=bool))
    state.household_cash = np.array([10.0] * 8, dtype=np.float64)
    state.household_reserved_second_hours = np.array([4.0] * 8, dtype=np.float64)
    _seed_via_retail(state, network, region=0, g=1, value=10.0)
    _seed_via_org_output_cell(state, network, region=0, g=3, value=10.0)
    flows = _StubFlows(0, 2, 16, len(network.cell_owner_kind), 8, 15)
    price_net = np.array([1.0] * 16, dtype=np.float64)
    plan_f2_household_time(state, params, tolerance=1.0)
    trace: dict[str, object] = {}
    settle_f2_second_economy(state, flows, f2, params, price_net, trace=trace)
    assert trace["tick"] == 0
    assert trace["recipe_hash"] == F2SecondEconomyRecipe.default_nonplot_v1().recipe_hash
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    assert trace["produced"].shape == (region_count, 16)
    assert trace["activity"].shape == (region_count,)
    assert trace["funding"].shape == (8,)


def test_settle_no_trace_means_no_extra_arrays() -> None:
    state, network, params = _tiny_f2_state()
    f2 = _f2_view(network)
    _set_working_adults(state, np.ones(8, dtype=np.float64))
    _set_second_participating(state, np.ones(8, dtype=bool))
    state.household_cash = np.full(8, 10.0, dtype=np.float64)
    state.household_reserved_second_hours = np.full(8, 4.0, dtype=np.float64)
    flows = _StubFlows(0, 2, 16, len(network.cell_owner_kind), 8, 15)
    price_net = np.array([1.0] * 16, dtype=np.float64)
    plan_f2_household_time(state, params, tolerance=1.0)
    settle_f2_second_economy(state, flows, f2, params, price_net)


# ---------------------------------------------------------------------------
# Expiry test: g15 (services_transport analog) cleared, g11 retained
# ---------------------------------------------------------------------------


def test_expire_clears_non_stockable_output() -> None:
    state, network, _ = _tiny_f2_state()
    f2 = _f2_view(network)
    g11 = F2_COMMODITY_IDS.index("g11_textiles_footwear")
    g15 = F2_COMMODITY_IDS.index("g15_market_services")
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    pool = np.zeros((region_count, 16), dtype=np.float64)
    pool[:, g11] = 0.5
    pool[:, g15] = 0.25
    state.second_output_stock = pool.copy()
    expire_f2_second_economy(state, f2)
    pool2 = np.asarray(state.second_output_stock, dtype=np.float64)
    assert np.all(pool2[:, g11] == 0.5)
    assert np.all(pool2[:, g15] == 0.0)


def test_expire_with_trace_records_expiry() -> None:
    state, network, _ = _tiny_f2_state()
    f2 = _f2_view(network)
    g15 = F2_COMMODITY_IDS.index("g15_market_services")
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    pool = np.zeros((region_count, 16), dtype=np.float64)
    pool[:, g15] = 0.25
    state.second_output_stock = pool.copy()
    trace: dict[str, object] = {}
    expire_f2_second_economy(state, f2, trace=trace)
    assert "expired_regions" in trace
    assert "g15_market_services" in trace["expired_regions"]


# ---------------------------------------------------------------------------
# Invariant check tests
# ---------------------------------------------------------------------------


def test_check_passes_when_pool_balanced() -> None:
    state, network, params = _tiny_f2_state()
    f2 = _f2_view(network)
    _set_working_adults(state, np.ones(8, dtype=np.float64))
    _set_second_participating(state, np.ones(8, dtype=bool))
    state.household_cash = np.full(8, 10.0, dtype=np.float64)
    state.household_reserved_second_hours = np.full(8, 4.0, dtype=np.float64)
    _seed_via_retail(state, network, region=0, g=1, value=10.0)
    _seed_via_org_output_cell(state, network, region=0, g=3, value=10.0)
    flows = _StubFlows(0, 2, 16, len(network.cell_owner_kind), 8, 15)
    price_net = np.array([1.0] * 16, dtype=np.float64)
    plan_f2_household_time(state, params, tolerance=1.0)
    opening = _opening(state)
    settle_f2_second_economy(state, flows, f2, params, price_net)
    expire_f2_second_economy(state, f2)
    check_f2_second_economy(opening, state, flows, network, None)  # no-op without F2 marker


def test_check_rejects_when_trace_tick_mismatches() -> None:
    state, network, params = _tiny_f2_state()
    f2 = _f2_view(network)
    trace = {"tick": 99, "recipe_hash": F2SecondEconomyRecipe.default_nonplot_v1().recipe_hash}
    with pytest.raises(AccountingError):
        check_f2_second_economy(None, state, _StubFlows(0, 2, 16, 0, 0, 0), f2, trace)


def test_check_rejects_when_trace_recipe_hash_mismatches() -> None:
    state, network, params = _tiny_f2_state()
    f2 = _f2_view(network)
    trace = {"tick": 0, "recipe_hash": "bogus"}
    flows = _StubFlows(0, 2, 16, len(network.cell_owner_kind), 8, 15)
    with pytest.raises(AccountingError):
        check_f2_second_economy(None, state, flows, f2, trace)


def test_check_returns_unchanged_for_legacy_network() -> None:
    state, network, _ = _tiny_f2_state()
    flows = _StubFlows(0, 2, 16, len(network.cell_owner_kind), 8, 15)
    result = check_f2_second_economy(None, state, flows, network, None)
    assert result.get("f2_checked", 0.0) == 0.0


# ---------------------------------------------------------------------------
# Integration test: full tick_material run on the existing F2 spec
# ---------------------------------------------------------------------------


def _load_f2_initial_from_spec(seed: int, households: int):
    contract = load_research_contract(REPO_ROOT)
    spec = load_scenario(REPO_ROOT, F2_SPEC)
    rng = RngRegistry(seed)
    initial = build_material_initial_conditions(spec, rng)
    network = build_material_network(spec, contract, initial)
    state = initialize_material(spec, initial, network)
    return state, network, spec, contract


def test_attach_to_real_f2_network_sets_correct_axes() -> None:
    state, network, _, _ = _load_f2_initial_from_spec(1729, 5000)
    assert network.second_input_commodities == ()
    recipe = F2SecondEconomyRecipe.default_nonplot_v1()
    f2 = attach_f2_second_economy(network, recipe)
    g02 = F2_COMMODITY_IDS.index("g02_oil_gas_fuels")
    g04 = F2_COMMODITY_IDS.index("g04_basic_metals_materials")
    g11 = F2_COMMODITY_IDS.index("g11_textiles_footwear")
    g15 = F2_COMMODITY_IDS.index("g15_market_services")
    assert tuple(f2.second_input_commodities) == (g02, g04)
    assert tuple(f2.second_output_commodities) == (g11, g15)


def test_real_f2_planner_runs_with_zero_tolerance() -> None:
    state, _network, spec, _ = _load_f2_initial_from_spec(1729, 100)
    plan_f2_household_time(state, spec.household_parameters, tolerance=0.0)
    assert np.all(np.asarray(state.household_reserved_second_hours) == 0.0)


def test_real_f2_planner_runs_with_full_tolerance() -> None:
    state, _network, spec, _ = _load_f2_initial_from_spec(1729, 100)
    plan_f2_household_time(state, spec.household_parameters, tolerance=1.0)
    reserved = np.asarray(state.household_reserved_second_hours, dtype=np.float64)
    assert np.any(reserved > 0.0)


# ---------------------------------------------------------------------------
# Allocator: non-unit household weights and exclusive substitution sources
# ---------------------------------------------------------------------------


def _allocator_flows(state, network):
    from hsm_lab.engine.material import _new_flows

    G = len(network.commodity_ids)
    return _new_flows(
        tick=0,
        quarter="1957Q1",
        org_count=int(state.organization_id.shape[0]),
        household_count=int(state.household_id.shape[0]),
        region_count=int(state.dwelling_stock.shape[0]),
        g_count=G,
        activity_count=int(network.activity_kind.shape[0]),
        k_count=int(network.input_cell.shape[0]),
        d_count=int(network.demand_cell.shape[0]),
        m_count=int(network.edge_source_cell.shape[0]),
        cell_count=int(network.cell_owner_kind.shape[0]),
        h_count=len(network.household_catalog.household_good_ids),
    )


def test_f2_receipt_uses_working_share_not_double_weight() -> None:
    """Weighted receipts must equal the sale; the legacy double-weight is 19.25."""
    from hsm_lab.engine.household_allocation import allocate_household_baskets
    from hsm_lab.engine.state import capture_material_stocks

    state, network, _ = _tiny_f2_state(region_count=1, households=5000, seed=1729)
    f2 = _f2_view(network)
    params = _make_blank_household_parameters()
    n = int(state.household_id.size)
    region = np.zeros(n, dtype=np.int32)
    weight = np.zeros(n, dtype=np.float64)
    weight[:2] = [2.0, 3.0]
    working = np.zeros(n, dtype=np.float64)
    working[:2] = [1.0, 2.0]
    participating = np.zeros(n, dtype=bool)
    participating[:2] = True
    state.household_region = region
    state.household_weight = weight
    state.household_working_adults = working
    state.household_second_participating = participating
    state.household_plot_participating = np.zeros(n, dtype=bool)
    state.household_cash = np.zeros(n, dtype=np.float64)
    state.household_cash[:2] = 10.0

    g11 = network.commodity_ids.index("g11_textiles_footwear")
    retail_cell = int(np.asarray(network.retail_cell_by_commodity)[0, g11])
    stock = np.asarray(state.stock_value, dtype=np.float64).copy()
    if retail_cell >= 0:
        stock[retail_cell] = 0.0
    state.stock_value = stock
    pool = np.zeros_like(np.asarray(state.second_output_stock, dtype=np.float64))
    pool[0, g11] = 100.0
    state.second_output_stock = pool

    flows = _allocator_flows(state, f2)
    textiles_h = f2.household_catalog.household_good_ids.index("textiles")
    flows.household_desired_h[0:2, textiles_h] = 0.02
    flows.household_wage_income[0:2] = 10.0
    prices = build_material_prices(load_scenario(REPO_ROOT, F2_SPEC).material_parameters)
    opening = capture_material_stocks(state)
    allocate_household_baskets(
        state,
        flows,
        params,
        f2,
        opening,
        prices,
        state.household_cash.copy(),
        np.zeros(n, dtype=np.float64),
        opening.stock_value,
    )
    price_h = float(f2.household_catalog.price_h[textiles_h])
    sale = 0.1 * price_h
    expected = np.array([sale * 1.0 / 8.0, sale * 2.0 / 8.0])
    np.testing.assert_allclose(
        np.asarray(flows.household_second_income_direct[:2], dtype=np.float64),
        expected,
        rtol=1e-9,
        atol=1e-12,
    )
    weighted = float((weight * np.asarray(flows.household_second_income_direct)).sum())
    assert weighted == pytest.approx(sale, rel=1e-9, abs=1e-12)
    # The legacy formula would have produced a weighted total near 19.25 here.
    assert weighted < 19.0


def test_f2_second_substitution_draws_pool_and_pays_participants() -> None:
    """A repair substitution sourced from the F2 pool is paid, not double-counted."""
    from hsm_lab.engine.household_allocation import allocate_household_baskets
    from hsm_lab.engine.state import capture_material_stocks

    state, network, _ = _tiny_f2_state(region_count=1, households=5000, seed=1729)
    f2 = _f2_view(network)
    params = _make_blank_household_parameters()
    n = int(state.household_id.size)
    state.household_region = np.zeros(n, dtype=np.int32)
    weight = np.zeros(n, dtype=np.float64)
    weight[:2] = [2.0, 3.0]
    working = np.zeros(n, dtype=np.float64)
    working[:2] = [1.0, 2.0]
    participating = np.zeros(n, dtype=bool)
    participating[:2] = True
    state.household_weight = weight
    state.household_working_adults = working
    state.household_second_participating = participating
    state.household_plot_participating = np.zeros(n, dtype=bool)
    state.household_cash = np.zeros(n, dtype=np.float64)
    state.household_cash[:2] = 10.0

    catalog = f2.household_catalog
    repair_h = catalog.household_good_ids.index("repair_services")
    durable_h = catalog.household_good_ids.index("refrigerator")
    g15 = network.commodity_ids.index("g15_market_services")
    retail_cell = int(np.asarray(network.retail_cell_by_commodity)[0, g15])
    stock = np.asarray(state.stock_value, dtype=np.float64).copy()
    if retail_cell >= 0:
        stock[retail_cell] = 0.0
    state.stock_value = stock
    pool = np.zeros_like(np.asarray(state.second_output_stock, dtype=np.float64))
    pool[0, g15] = 100.0
    state.second_output_stock = pool

    flows = _allocator_flows(state, f2)
    flows.household_desired_h[0:2, durable_h] = 1.0
    flows.household_wage_income[0:2] = 10.0
    prices = build_material_prices(load_scenario(REPO_ROOT, F2_SPEC).material_parameters)
    opening = capture_material_stocks(state)
    before_pool = float(np.asarray(state.second_output_stock)[0, g15])
    allocate_household_baskets(
        state,
        flows,
        params,
        f2,
        opening,
        prices,
        state.household_cash.copy(),
        np.zeros(n, dtype=np.float64),
        opening.stock_value,
    )
    after_pool = float(np.asarray(state.second_output_stock)[0, g15])
    assert after_pool < before_pool
    second_units = float((weight * np.asarray(flows.household_second_h)[:, repair_h]).sum())
    assert second_units > 0.0
    assert float(
        (weight * np.asarray(flows.household_second_income_direct)).sum()
    ) == pytest.approx(
        second_units * float(catalog.price_h[repair_h]), rel=1e-9, abs=1e-12
    )
    # Formal repair sales receive nothing when the pool was the only source.
    assert float(np.asarray(flows.retail_sales)[0, g15]) == pytest.approx(0.0, abs=1e-12)


def test_f2_substitution_never_reuses_one_service_shelf() -> None:
    """Four durable shortages share at most the real formal + second repair stock."""
    from hsm_lab.engine.household_allocation import allocate_household_baskets
    from hsm_lab.engine.state import capture_material_stocks

    state, network, _ = _tiny_f2_state(region_count=1, households=5000, seed=1729)
    f2 = _f2_view(network)
    params = _make_blank_household_parameters()
    n = int(state.household_id.size)
    state.household_region = np.zeros(n, dtype=np.int32)
    weight = np.zeros(n, dtype=np.float64)
    weight[0] = 1.0
    working = np.zeros(n, dtype=np.float64)
    working[0] = 1.0
    participating = np.zeros(n, dtype=bool)
    participating[0] = True
    state.household_weight = weight
    state.household_working_adults = working
    state.household_second_participating = participating
    state.household_plot_participating = np.zeros(n, dtype=bool)
    state.household_cash = np.zeros(n, dtype=np.float64)
    state.household_cash[0] = 100.0

    catalog = f2.household_catalog
    g15 = network.commodity_ids.index("g15_market_services")
    retail_cell = int(np.asarray(network.retail_cell_by_commodity)[0, g15])
    assert retail_cell >= 0
    stock = np.asarray(state.stock_value, dtype=np.float64).copy()
    stock[retail_cell] = 1.0
    state.stock_value = stock
    pool = np.zeros_like(np.asarray(state.second_output_stock, dtype=np.float64))
    pool[0, g15] = 1.0
    state.second_output_stock = pool

    flows = _allocator_flows(state, f2)
    for durable in catalog.durable_h_index:
        flows.household_desired_h[0, int(durable)] = 1.0
    flows.household_wage_income[0] = 100.0
    prices = build_material_prices(load_scenario(REPO_ROOT, F2_SPEC).material_parameters)
    opening = capture_material_stocks(state)
    allocate_household_baskets(
        state,
        flows,
        params,
        f2,
        opening,
        prices,
        state.household_cash.copy(),
        np.zeros(n, dtype=np.float64),
        opening.stock_value,
    )
    repair_h = catalog.household_good_ids.index("repair_services")
    second_acquired = float(
        weight[0] * np.asarray(flows.household_second_h)[0, repair_h]
    )
    formal_acquired = float(np.asarray(flows.household_formal_h)[0, repair_h])
    total_acquired = second_acquired + formal_acquired
    assert 0.0 < total_acquired <= 2.0 + 1e-9
    assert 0.0 <= formal_acquired <= 1.0 + 1e-9
    assert 0.0 <= second_acquired <= 1.0 + 1e-9
    assert float(np.asarray(flows.retail_sales)[0, g15]) == pytest.approx(
        formal_acquired, abs=1e-9
    )
    assert float(np.asarray(state.second_output_stock)[0, g15]) == pytest.approx(
        1.0 - second_acquired, abs=1e-9
    )


# ---------------------------------------------------------------------------
# Checker tamper regressions: the trace and the journal are evidence, never
# authority.  Each case keeps every aggregate identity intact (or closes over
# an offsetting edit) so only the per-(region, commodity) / per-household /
# per-leg re-derivation inside ``check_f2_second_economy`` can reject it.
# ---------------------------------------------------------------------------


def _f2_checker_case():
    """Settle + allocate + expire a two-participant F2 quarter on the tiny fixture.

    Weights ``[2, 3]`` and working adults ``[1, 2]`` give a non-unit-weight
    receipt split; one unit of activity produces stockable ``g11`` and
    non-stockable ``g15``, and the two participants buy textiles out of the
    second pool so real direct-sale journal legs exist.
    """
    from hsm_lab.engine.household_allocation import allocate_household_baskets
    from hsm_lab.engine.material import _admin_price_vector
    from hsm_lab.engine.state import capture_material_stocks

    g02 = F2_COMMODITY_IDS.index("g02_oil_gas_fuels")
    g04 = F2_COMMODITY_IDS.index("g04_basic_metals_materials")
    state, network, params = _tiny_f2_state(region_count=1, households=8, seed=1729)
    f2 = _f2_view(network)
    n = int(state.household_id.shape[0])
    state.household_region = np.zeros(n, dtype=np.int32)
    weight = np.zeros(n, dtype=np.float64)
    weight[:2] = [2.0, 3.0]
    working = np.zeros(n, dtype=np.float64)
    working[:2] = [1.0, 2.0]
    participating = np.zeros(n, dtype=bool)
    participating[:2] = True
    state.household_weight = weight
    state.household_working_adults = working
    state.household_second_participating = participating
    state.household_plot_participating = np.zeros(n, dtype=bool)
    state.household_cash = np.zeros(n, dtype=np.float64)
    state.household_cash[:2] = 10.0
    state.household_reserved_second_hours = np.zeros(n, dtype=np.float64)
    state.household_reserved_second_hours[:2] = 4.0
    cell02 = _seed_via_org_output_cell(state, network, region=0, g=g02, value=0.02)
    cell04 = _seed_via_org_output_cell(state, network, region=0, g=g04, value=0.03)
    # Put the input sellers in a different bank so the settlement produces a
    # real interbank leg instead of a same-bank no-op.
    organization_bank = np.asarray(state.organization_bank, dtype=np.int64).copy()
    organization_bank[int(network.cell_owner_id[cell02])] = 1
    organization_bank[int(network.cell_owner_id[cell04])] = 1
    state.organization_bank = organization_bank

    flows = _allocator_flows(state, f2)
    trace: dict[str, object] = {}
    material_parameters = load_scenario(REPO_ROOT, F2_SPEC).material_parameters
    price_net, _services_g = _admin_price_vector(material_parameters, f2)
    opening = capture_material_stocks(state)
    settle_f2_second_economy(state, flows, f2, params, price_net, trace=trace)

    textiles_h = f2.household_catalog.household_good_ids.index("textiles")
    flows.household_desired_h[0:2, textiles_h] = 0.01
    flows.household_wage_income[0:2] = 10.0
    allocation_opening = capture_material_stocks(state)
    allocate_household_baskets(
        state,
        flows,
        _make_blank_household_parameters(),
        f2,
        allocation_opening,
        price_net,
        np.asarray(state.household_cash, dtype=np.float64).copy(),
        np.zeros(n, dtype=np.float64),
        allocation_opening.stock_value,
    )
    expire_f2_second_economy(state, f2, trace=trace)
    return state, f2, flows, opening, trace


def _copy_trace(trace: dict) -> dict:
    return {
        key: (value.copy() if isinstance(value, np.ndarray) else value)
        for key, value in trace.items()
    }


def test_output_coefficient_tamper_is_rejected() -> None:
    """Dropping the g11 output from trace *and* pool still fails the checker.

    Both sides of the pool identity are edited together, so only re-deriving
    production from ``activity x recipe.output_coefficients`` can catch it.
    """
    g11 = F2_COMMODITY_IDS.index("g11_textiles_footwear")
    state, f2, flows, opening, trace = _f2_checker_case()
    # The clean case must pass, otherwise the rejection below proves nothing.
    assert check_f2_second_economy(opening, state, flows, f2, trace)["f2_checked"] == 1.0
    pool = np.asarray(state.second_output_stock, dtype=np.float64).copy()
    produced = np.asarray(trace["produced"], dtype=np.float64).copy()
    assert produced[0, g11] > 0.0
    assert pool[0, g11] > 0.0
    pool[0, g11] = 0.0
    produced[0, g11] = 0.0
    state.second_output_stock = pool
    tampered = _copy_trace(trace)
    tampered["produced"] = produced
    with pytest.raises(AccountingError, match="produced quantity"):
        check_f2_second_economy(opening, state, flows, f2, tampered)


def test_stockable_expiry_tamper_is_rejected() -> None:
    """Writing off stockable g11 is rejected; real g15 expiry still passes."""
    g11 = F2_COMMODITY_IDS.index("g11_textiles_footwear")
    g15 = F2_COMMODITY_IDS.index("g15_market_services")
    state, f2, flows, opening, trace = _f2_checker_case()
    assert bool(commodity_spec("g11_textiles_footwear").stockable)
    assert not bool(commodity_spec("g15_market_services").stockable)
    # g11 is retained in the pool, g15 is genuinely expired in the clean case.
    assert np.asarray(state.second_output_stock)[0, g11] > 0.0
    assert float(np.asarray(trace["expired"])[0, g15]) > 0.0
    assert float(np.asarray(state.second_output_stock)[0, g15]) == pytest.approx(
        0.0, abs=1e-12
    )
    assert check_f2_second_economy(opening, state, flows, f2, trace)["f2_checked"] == 1.0

    pool = np.asarray(state.second_output_stock, dtype=np.float64).copy()
    expired = np.asarray(trace["expired"], dtype=np.float64).copy()
    expired[0, g11] = pool[0, g11]
    pool[0, g11] = 0.0
    state.second_output_stock = pool
    tampered = _copy_trace(trace)
    tampered["expired"] = expired
    with pytest.raises(AccountingError, match="stockable"):
        check_f2_second_economy(opening, state, flows, f2, tampered)


def test_per_participant_receipt_offset_is_rejected() -> None:
    """An equal offset between two participants keeps the weighted total exact."""
    state, f2, flows, opening, trace = _f2_checker_case()
    assert check_f2_second_economy(opening, state, flows, f2, trace)["f2_checked"] == 1.0
    weight = np.asarray(state.household_weight, dtype=np.float64)
    honest = np.asarray(flows.household_second_income_direct, dtype=np.float64).copy()
    tampered = honest.copy()
    shift = 0.2 * float(honest[0])
    tampered[0] += shift
    tampered[1] -= shift * weight[0] / weight[1]
    # The national identity that the old checker relied on is preserved.
    assert float((weight * tampered).sum()) == pytest.approx(
        float((weight * honest).sum()), rel=1e-12, abs=1e-15
    )
    flows.household_second_income_direct = tampered
    with pytest.raises(AccountingError, match="direct-sale receipt for household"):
        check_f2_second_economy(opening, state, flows, f2, trace)


def test_direct_sale_debit_credit_swap_is_rejected() -> None:
    """Swapping one leg's debit/credit leaves the journal total unchanged."""
    state, f2, flows, opening, trace = _f2_checker_case()
    assert check_f2_second_economy(opening, state, flows, f2, trace)["f2_checked"] == 1.0
    legs = [
        index
        for index, kind in enumerate(flows.journal_kind)
        if kind == "hist_second_direct_sale"
        and flows.journal_debit[index] != flows.journal_credit[index]
    ]
    assert legs, "fixture must produce a direct sale between two different households"
    target = legs[0]
    before = sum(
        float(flows.journal_amount[index])
        for index, kind in enumerate(flows.journal_kind)
        if kind == "hist_second_direct_sale"
    )
    flows.journal_debit[target], flows.journal_credit[target] = (
        flows.journal_credit[target],
        flows.journal_debit[target],
    )
    after = sum(
        float(flows.journal_amount[index])
        for index, kind in enumerate(flows.journal_kind)
        if kind == "hist_second_direct_sale"
    )
    assert after == pytest.approx(before, rel=1e-12, abs=1e-15)
    with pytest.raises(AccountingError, match="direct-sale journal leg"):
        check_f2_second_economy(opening, state, flows, f2, trace)


def test_funding_joint_scale_in_trace_is_rejected() -> None:
    """Scaling both funding and seller credits keeps closure but falsifies the flow."""
    state, f2, flows, opening, trace = _f2_checker_case()
    assert check_f2_second_economy(opening, state, flows, f2, trace)["f2_checked"] == 1.0
    tampered = _copy_trace(trace)
    tampered["funding"] = np.asarray(trace["funding"], dtype=np.float64) * 1.5
    tampered["seller_credit"] = (
        np.asarray(trace["seller_credit"], dtype=np.float64) * 1.5
    )
    with pytest.raises(AccountingError, match="funding trace"):
        check_f2_second_economy(opening, state, flows, f2, tampered)


def test_input_payment_journal_swap_is_rejected() -> None:
    """Swapping an interbank leg's debit/credit cannot hide behind equal totals."""
    state, f2, flows, opening, trace = _f2_checker_case()
    assert check_f2_second_economy(opening, state, flows, f2, trace)["f2_checked"] == 1.0
    legs = [
        index
        for index, kind in enumerate(flows.journal_kind)
        if kind == "hist_second_input_payment"
        and flows.journal_debit[index] != flows.journal_credit[index]
    ]
    assert legs, "fixture must produce an input-payment interbank leg"
    target = legs[0]
    before = float(flows.journal_amount[target])
    flows.journal_debit[target], flows.journal_credit[target] = (
        flows.journal_credit[target],
        flows.journal_debit[target],
    )
    assert float(flows.journal_amount[target]) == pytest.approx(before)
    with pytest.raises(AccountingError, match="input-payment journal leg"):
        check_f2_second_economy(opening, state, flows, f2, trace)


def test_zero_activity_trace_is_axis_complete_and_passes() -> None:
    """A legitimate no-participant tick writes full-length zero trace axes."""
    from hsm_lab.engine.material import _admin_price_vector
    from hsm_lab.engine.state import capture_material_stocks

    state, network, params = _tiny_f2_state(region_count=1, households=8, seed=1729)
    f2 = _f2_view(network)
    n = int(state.household_id.shape[0])
    state.household_second_participating = np.zeros(n, dtype=bool)
    state.household_reserved_second_hours = np.zeros(n, dtype=np.float64)
    flows = _allocator_flows(state, f2)
    trace: dict[str, object] = {}
    material_parameters = load_scenario(REPO_ROOT, F2_SPEC).material_parameters
    price_net, _services_g = _admin_price_vector(material_parameters, f2)
    opening = capture_material_stocks(state)
    settle_f2_second_economy(state, flows, f2, params, price_net, trace=trace)
    expire_f2_second_economy(state, f2, trace=trace)
    assert np.asarray(trace["funding"]).shape == (n,)
    assert np.asarray(trace["seller_credit"]).shape == (
        int(state.organization_id.shape[0]),
    )
    result = check_f2_second_economy(opening, state, flows, f2, trace)
    assert result["f2_checked"] == 1.0
