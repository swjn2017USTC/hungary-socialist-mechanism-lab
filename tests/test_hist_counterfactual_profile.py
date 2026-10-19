"""H3G: counterfactual procurement profile invariants."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np

from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.data.material import load_material_forcing
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.material import tick_material
from hsm_lab.engine.network import build_material_network
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import initialize_material
from hsm_lab.planning.counterfactual_profile import (
    build_counterfactual_world,
    counterfactual_inputs,
)
from hsm_lab.planning.rolling import plan_quarter

ROOT = Path(__file__).resolve().parents[1]


def _fixture():
    spec = load_scenario(ROOT, "historical_f2_replay")
    contract = load_research_contract(ROOT)
    initial = build_material_initial_conditions(spec, RngRegistry(spec.seed))
    network = build_material_network(spec, contract, initial)
    state = initialize_material(spec, initial, network)
    baseline_state = state.copy_dynamic()
    registry = DataRegistry.load(ROOT, allowed_commodities=spec.commodities)
    baseline = tick_material(
        baseline_state,
        load_material_forcing(spec, registry),
        spec.material_parameters,
        network,
    )
    world = build_counterfactual_world(network, state, spec.material_parameters, baseline)
    return spec, network, state, baseline, world


def test_profile_uses_residual_real_demand_and_no_recipes() -> None:
    _spec, network, _state, baseline, world = _fixture()
    declarations = world.declarations
    assert declarations.recipe_org.size == 0
    assert declarations.edge_baseline.shape == (4, declarations.edge_id.size)
    assert float(np.sum(declarations.edge_baseline)) == 0.0
    assert float(np.sum(declarations.baseline_procurement)) == 0.0
    assert bool(np.all(declarations.edge_buyer < 2))
    assert declarations.edge_id.size < network.edge_id.size
    assert float(np.sum(declarations.demand_ordered)) < float(np.sum(baseline.ordered))


def test_profile_plans_and_executes_against_a_baseline() -> None:
    spec, network, state, baseline, world = _fixture()
    inputs = counterfactual_inputs(
        world,
        network,
        state,
        quarter="1957Q1",
        decision_at=date(1957, 1, 15),
        available_at=date(1957, 1, 10),
    )
    plan = plan_quarter(inputs, mode="bounded_planning", time_limit_s=30)
    assert plan.status == "FEASIBLE"
    assert any(item.status == "FEASIBLE" for item in plan.certificates)
    assert len(plan.first_quarter_decisions) <= 2
    assert np.isfinite(float(np.sum(baseline.household_availability_unmet)))
    assert np.isfinite(float(np.sum(baseline.household_realized)))
