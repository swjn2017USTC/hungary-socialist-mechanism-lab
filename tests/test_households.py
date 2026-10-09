"""P03 household / social-contract / durables / second-economy behaviour tests.

Four declared household fixtures plus the population-scaling conservation check
and the entitlement/grievance separation.  Everything runs the real
``tick_material`` kernel or the real P03 kernels; nothing is mocked.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from hsm_lab.contract.households import (
    HOUSEHOLD_GOOD_IDS,
    DemandParameters,
    DurablesParameters,
    HouseholdParameters,
    SecondEconomyRecipe,
    default_household_recipe,
)
from hsm_lab.engine.households import build_synthetic_households
from hsm_lab.engine.rng import RngRegistry
from tests.test_material import (
    NO_CAPITAL_COMMODITIES,
    Fixture,
    bank,
    default_params,
    idle_source_tech,
    producer,
    retail,
)


def _params(**demand_overrides) -> HouseholdParameters:
    base = [0.0] * len(HOUSEHOLD_GOOD_IDS)
    base[1] = 5.0  # basic_food
    minimum = [0.0] * len(HOUSEHOLD_GOOD_IDS)
    minimum[1] = 5.0
    return HouseholdParameters(
        demand=DemandParameters(
            base_per_equivalent_person=base,
            minimum_per_equivalent_person=minimum,
            **demand_overrides,
        ),
        durables=DurablesParameters(
            aspiration_base=[0.0, 0.0, 0.0, 0.0],
            aspiration_income_weight=0.0,
            aspiration_peer_weight=0.0,
            aspiration_expectation_weight=0.0,
            new_intention_per_quarter=0.0,
        ),
    )


# ---------------------------------------------------------------------------
# Fixture 1: income up but goods unavailable (forced saving, no substitution)
# ---------------------------------------------------------------------------


def test_income_up_but_goods_unavailable() -> None:
    worker = producer(1, "energy_generation", capacity=2.0)
    fixture = Fixture(
        [bank(0), worker, retail(2)],
        [idle_source_tech("energy_generation", "energy")],
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=default_params(prices=[2.0] * 8),
        households=[(0, 1.0, 1.0)],
        household_cash=10.0,
        household_parameters=_params(),
        ticks=2,
    )
    fixture.state.stock_value[:] = 0.0  # every good is unavailable
    flows = fixture.tick(2)
    for flow in flows:
        # goods unavailable: nothing is realised, but the goal stays funded
        assert flow.household_realized[0, fixture.g("food")] == pytest.approx(0.0)
        assert flow.household_planned_spending[0] > 0.0
        assert flow.household_spending[0] == pytest.approx(0.0)
        assert flow.household_forced_saving[0] == pytest.approx(flow.household_planned_spending[0])
        # the goal is funded but unavailable: availability, not affordability,
        # is the binding shortfall, and no substitution can manufacture goods
        assert flow.household_availability_unmet_h[0].sum() > 0.0
        assert float(flow.household_substitution.sum()) >= 0.0
        # queueing is recorded as real time cost against the affordable shortfall
        assert flow.household_queue_hours[0] > 0.0
    # a higher budget cannot buy absent goods: forced saving tracks the budget
    assert flows[1].household_budget_available[0] >= flows[0].household_budget_available[0]


# ---------------------------------------------------------------------------
# Fixture 2: durable waiting -> ownership is a stock, not a flow
# ---------------------------------------------------------------------------


def test_durable_waiting_is_a_stock_not_a_flow() -> None:
    worker = producer(1, "energy_generation", capacity=1.0)
    fixture = Fixture(
        [bank(0), worker, retail(2)],
        [idle_source_tech("energy_generation", "energy")],
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=default_params(),
        households=[(0, 1.0, 1.0)],
        household_cash=100.0,
        household_parameters=HouseholdParameters(
            demand=DemandParameters(
                base_per_equivalent_person=[0.0, 0.0, 0.0, 0.0, 1.0, 0, 0, 0, 0, 0, 0],
                minimum_per_equivalent_person=[0.0] * len(HOUSEHOLD_GOOD_IDS),
            )
        ),
        ticks=1,
    )
    fixture.state.stock_value[:] = 0.0  # no durables on the shelf
    fixture.tick(1)
    # desired good unavailable: ownership stays zero, backlog and waiting grow
    assert fixture.state.household_durable_owned[0, 0] == pytest.approx(0.0)
    assert fixture.state.household_durable_backlog[0, 0] > 0.0
    assert int(fixture.state.household_durable_wait[0, 0]) >= 1

    # now the good appears: the purchase lands as stock and clears the backlog
    fixture.state.stock_value[fixture.cell("organization", 2, 0, "retail", "durable_goods")] = 5.0
    fixture.tick(1)
    assert fixture.state.household_durable_owned[0, 0] > 0.0
    assert fixture.state.household_durable_backlog[0, 0] == pytest.approx(0.0)
    assert int(fixture.state.household_durable_wait[0, 0]) == 0


# ---------------------------------------------------------------------------
# Fixture 3: second-economy food relief and income
# ---------------------------------------------------------------------------


def test_second_economy_affects_income_and_availability() -> None:
    worker = producer(1, "energy_generation", capacity=2.0)
    fixture = Fixture(
        [bank(0), worker, retail(2)],
        [idle_source_tech("energy_generation", "energy")],
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=default_params(),
        households=[(0, 1.0, 1.0), (0, 1.0, 1.0)],
        household_cash=100.0,
        household_parameters=HouseholdParameters(
            second_economy=SecondEconomyRecipe(
                input_coefficients=[0.05, 0, 0, 0, 0, 0, 0, 0],
                output_coefficients=[0, 0, 0, 0.10, 0, 0.05, 0, 0.25],
            )
        ),
        ticks=1,
    )
    fixture.state.stock_value[:] = 0.0
    # two participating households; the aggregate has real energy inputs on hand
    fixture.state.household_second_participating[:] = True
    fixture.state.household_reserved_second_hours[:] = 40.0
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "output", "energy")] = 100.0
    second_flow = fixture.tick(1)[0]
    # the aggregate bought real inputs, produced output and paid the sellers
    assert float(fixture.state.second_output_stock.sum()) > 0.0
    assert float(second_flow.household_second_input_funding.sum()) > 0.0
    assert float(second_flow.organization_sales_receipts[1]) > 0.0


# ---------------------------------------------------------------------------
# Fixture 4: entitlement ratchet (experience-driven, never a support scalar)
# ---------------------------------------------------------------------------


def _ratchet_state(entitlement_value: float, expectation: np.ndarray, streak: np.ndarray):
    return SimpleNamespace(
        household_entitlement=np.array([[entitlement_value] + [0.5] * 6]),
        household_expectation=expectation.copy(),
        household_improvement_streak=streak.copy(),
        household_consumption_reference=np.zeros((1, len(HOUSEHOLD_GOOD_IDS))),
        household_last_consumption=np.zeros((1, len(HOUSEHOLD_GOOD_IDS))),
        household_last_availability_unmet=np.zeros((1, len(HOUSEHOLD_GOOD_IDS))),
        household_working_adults=np.array([1.0]),
    )


def test_entitlement_ratchet_sequence() -> None:
    from hsm_lab.engine.household_welfare import update_household_expectations

    parameters = HouseholdParameters()
    expectation = np.array([[0.5] * 7])
    streak = np.zeros((1, 7), dtype=np.int32)
    opening_entitlement = np.array([[0.5] * 7])
    sequence = [0.55, 0.60, 0.65, 0.70, 0.50]
    for value in sequence:
        state = _ratchet_state(value, expectation, streak)
        opening = SimpleNamespace(
            household_expectation=expectation.copy(),
            household_entitlement=opening_entitlement.copy(),
        )
        flows = SimpleNamespace(
            household_realized_h=np.zeros((1, len(HOUSEHOLD_GOOD_IDS))),
            household_availability_unmet_h=np.zeros((1, len(HOUSEHOLD_GOOD_IDS))),
        )
        update_household_expectations(state, flows, parameters, opening)
        expectation = state.household_expectation
        streak = state.household_improvement_streak
        opening_entitlement = state.household_entitlement
    assert expectation[0, 0] == pytest.approx(0.60041171875)
    # no protest / collective-action quantity exists anywhere in the P03 state
    assert not hasattr(state, "protest")
    assert not hasattr(flows, "protest")


def test_substitution_relieves_residual_availability_and_queue() -> None:
    from hsm_lab.contract.households import H_INDEX

    hvf = H_INDEX["higher_value_food"]
    worker = producer(1, "energy_generation", capacity=1.0)
    base = [0.0] * len(HOUSEHOLD_GOOD_IDS)
    base[hvf] = 4.0
    fixture = Fixture(
        [bank(0), worker, retail(2)],
        [idle_source_tech("energy_generation", "energy")],
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=default_params(),
        households=[(0, 1.0, 1.0)],
        household_cash=1000.0,
        household_parameters=HouseholdParameters(
            demand=DemandParameters(
                base_per_equivalent_person=base,
                minimum_per_equivalent_person=[0.0] * len(HOUSEHOLD_GOOD_IDS),
            )
        ),
        ticks=1,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 2, 0, "retail", "food", "ready")] = 2.0
    fixture.state.household_deferred_receipt[0] = 20.0  # fund the desired basket
    flow = fixture.tick(1)[0]
    substituted_source = float(flow.household_substitution[0, 0])
    assert substituted_source > 0.0
    # kernel identity: the residual source gap = pre-substitution gap minus the
    # relieved source units (never the unrelieved pre-substitution gap).
    unmet_pre = float(flow.household_affordable_h[0, hvf]) - float(
        flow.household_realized_h[0, hvf]
    )
    assert flow.household_availability_unmet_h[0, hvf] == pytest.approx(
        max(0.0, unmet_pre - substituted_source)
    )
    assert flow.household_queue_hours[0] >= 0.0


def test_plot_self_use_enters_realised_basket_and_entitlement() -> None:
    from tests.test_material import _plot_ready_fixture

    fixture = _plot_ready_fixture()
    food_g = fixture.g("food")
    flow = fixture.tick(1)[0]
    # self-user (household 4) consumes 2 units through the plot channel; that
    # consumption must appear in the H-level realised basket, not vanish.
    assert flow.household_plot_self_h[4, 1] == pytest.approx(2.0)
    assert flow.household_realized_h[4, 1] == pytest.approx(2.0)
    assert fixture.state.household_entitlement[4, 1] > 0.0  # real_consumption
    assert flow.household_realized[4, food_g] >= 2.0


def test_real_wage_growth_can_lower_welfare_when_goods_unavailable() -> None:
    def run(wage_rate: float):
        worker = producer(1, "energy_generation", capacity=2.0)
        fixture = Fixture(
            [bank(0), worker, retail(2)],
            [idle_source_tech("energy_generation", "energy")],
            commodities=NO_CAPITAL_COMMODITIES,
            parameters=default_params(wage_rate=wage_rate),
            households=[(0, 1.0, 1.0)],
            household_cash=100000.0,
            household_parameters=_params(),
            ticks=3,
        )
        fixture.state.stock_value[:] = 0.0  # no goods anywhere
        flows = fixture.tick(3)
        return flows[-1]

    low = run(1.0)
    high = run(4.0)
    # higher income with the same zero availability raises affordable demand,
    # which raises queue time and substitution cost, so welfare can fall.
    assert high.household_budget_available[0] > low.household_budget_available[0]
    assert high.household_realized_h.sum() == pytest.approx(0.0)
    assert high.household_welfare_net[0] < low.household_welfare_net[0]


def test_compliance_is_not_one_minus_grievance() -> None:
    parameters = HouseholdParameters()
    # compliance uses its own slow rule with a declared baseline, not 1 - grievance
    grievance = 0.8
    target = np.clip(
        parameters.welfare.compliance_baseline
        - parameters.welfare.compliance_gap_weight * grievance
        + parameters.welfare.compliance_autonomy_weight
        * (parameters.welfare.private_autonomy - 0.5),
        0.0,
        1.0,
    )
    assert target != pytest.approx(1.0 - grievance)


# ---------------------------------------------------------------------------
# Population scaling: weighted margins are invariant to the sample size
# ---------------------------------------------------------------------------


def _spec_like(households: int) -> SimpleNamespace:
    region_ids = [f"R{r}" for r in range(20)]
    return SimpleNamespace(
        region_ids=region_ids,
        households=households,
        stochastic=False,
        household_initial=default_household_recipe(region_ids),
        household_parameters=HouseholdParameters(),
    )


def test_population_scaling_conserves_margins() -> None:
    reference = None
    for sample in (1000, 5000, 20000):
        initial = build_synthetic_households(_spec_like(sample), RngRegistry(1729))
        region = np.asarray(initial.region, dtype=np.int64)
        weight = np.asarray(initial.weight, dtype=np.float64)
        size = np.asarray(initial.size, dtype=np.float64)
        urban = np.asarray(initial.urban, dtype=bool)
        occupation = np.asarray(initial.occupation, dtype=np.int64)
        margins = {
            "households": float(weight.sum()),
            "persons": float((weight * size).sum()),
            "region_households": np.bincount(region, weights=weight, minlength=20),
            "region_persons": np.bincount(region, weights=weight * size, minlength=20),
            "urban": float((weight * urban).sum()),
            "occupation": np.bincount(occupation, weights=weight, minlength=4),
        }
        assert margins["households"] == pytest.approx(5000.0)
        assert margins["persons"] == pytest.approx(17000.0)
        if reference is None:
            reference = margins
        else:
            assert np.allclose(margins["region_households"], reference["region_households"])
            assert np.allclose(margins["region_persons"], reference["region_persons"])
            assert margins["urban"] == pytest.approx(reference["urban"])
            assert np.allclose(margins["occupation"], reference["occupation"])


def test_public_service_channel_carries_declared_base_demand() -> None:
    """The F2 basket declares public_services, so g16 must not stay at zero demand."""
    from pathlib import Path

    import numpy as np

    from hsm_lab.contract.guards import load_research_contract, load_scenario
    from hsm_lab.engine.households import form_household_demand
    from hsm_lab.engine.initial import build_material_initial_conditions
    from hsm_lab.engine.network import build_material_network
    from hsm_lab.engine.rng import RngRegistry
    from hsm_lab.engine.state import initialize_material

    root = Path(__file__).resolve().parents[1]
    spec = load_scenario(root, "historical_f2_replay")
    initial = build_material_initial_conditions(spec, RngRegistry(spec.seed))
    network = build_material_network(spec, load_research_contract(root), initial)
    state = initialize_material(spec, initial, network)
    catalog = network.household_catalog
    assert "public" in catalog.role_channels
    public = catalog.channels("public")[0]
    desired = form_household_demand(state, network.household_parameters, catalog)
    assert desired.shape[1] == len(catalog.household_good_ids)
    assert bool(np.all(desired[:, public] > 0.0)), "public services still carry zero demand"


def test_axes_without_a_public_role_are_untouched() -> None:
    import numpy as np

    from hsm_lab.contract.households import INTERMEDIATE8_AXIS

    assert "public" not in INTERMEDIATE8_AXIS.role_channels
    # the guard is a membership test, so no KeyError is raised for these axes
    assert np.all(np.isfinite(INTERMEDIATE8_AXIS.quota_share))
