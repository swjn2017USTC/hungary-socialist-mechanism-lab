"""E4 activity-level alignment: declared demand, feasibility and infeasibility."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from hsm_lab.calibration.alignment import (
    AlignmentProblem,
    build_alignment_problem,
    declared_household_demand,
    solve_alignment,
)
from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.network import build_material_network
from hsm_lab.engine.rng import RngRegistry

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def f2_problem() -> tuple[AlignmentProblem, object]:
    spec = load_scenario(ROOT, "historical_f2_replay")
    initial = build_material_initial_conditions(spec, RngRegistry(spec.seed))
    network = build_material_network(spec, load_research_contract(ROOT), initial)
    problem = build_alignment_problem(
        network,
        parameters=spec.material_parameters,
        equivalent_persons=float(initial.equivalent_persons),
    )
    return problem, network


def test_declared_household_demand_matches_the_engine_basket(f2_problem) -> None:
    problem, network = f2_problem
    demand = declared_household_demand(network, equivalent_persons=17000.0)
    values = dict(zip(network.commodity_ids, demand, strict=True))
    # declared basket weights: public_services 0.1 and higher_food 0.2 x 2.0
    assert values["g16_housing_public_services"] == pytest.approx(1700.0)
    assert values["g09_basic_food"] == pytest.approx(8500.0)
    assert values["g10_animal_food"] == pytest.approx(6800.0)
    # commodities with no household channel carry no household demand
    assert values["g04_basic_metals_materials"] == 0.0
    # the compiled problem uses the same declared demand every quarter
    assert np.allclose(problem.demand[:, 0], problem.demand[:, 3])


def test_alignment_is_feasible_and_needs_no_capacity_change(f2_problem) -> None:
    problem, _network = f2_problem
    result = solve_alignment(problem)
    assert result["status"] == "LP_FEASIBLE"
    assert result["max_balance_residual"] < 1e-6
    # the declared household demand fits the existing profile: the LP keeps every
    # activity at its original ceiling and needs no capacity realignment
    assert result["capacity_deviation"] == pytest.approx(0.0, abs=1e-9)
    assert result["at_original_ceiling"] == result["activities"]
    assert "capacity" in result and "activity" in result


def _tiny_problem(*, capacity: float, demand: float) -> AlignmentProblem:
    return AlignmentProblem(
        activity_output=np.array([[1.0], [0.0]]),
        activity_input=np.array([[0.0], [0.0]]),
        capacity=np.array([capacity, 0.0]),
        labor_cap=np.full((2, 4), capacity),
        utilization=np.array([1.0, 1.0]),
        season=np.ones(4),
        demand=np.full((1, 4), demand),
        stockable=np.array([False]),
        commodity_ids=("only",),
        activity_ids=("producer", "idle"),
    )


def test_alignment_reports_infeasible_with_a_static_gap() -> None:
    problem = _tiny_problem(capacity=5.0, demand=10.0)
    result = solve_alignment(problem)
    assert result["status"] == "INFEASIBLE"
    assert result["gaps"][0]["commodity_id"] == "only"
    assert result["gaps"][0]["shortfall"] == pytest.approx(5.0)


def test_alignment_is_feasible_when_capacity_covers_demand() -> None:
    problem = _tiny_problem(capacity=10.0, demand=10.0)
    result = solve_alignment(problem)
    assert result["status"] == "LP_FEASIBLE"
    assert result["capacity_deviation"] == pytest.approx(0.0, abs=1e-9)
