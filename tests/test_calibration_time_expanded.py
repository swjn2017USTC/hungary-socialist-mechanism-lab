"""Tests for the regional, time-expanded feasibility certificate."""

from __future__ import annotations

import numpy as np
import pytest

from hsm_lab.calibration.time_expanded import (
    RegionalProblem,
    solve_regional_feasibility,
)


def _problem(
    *,
    output: np.ndarray,
    used: np.ndarray,
    capacity: np.ndarray,
    demand: np.ndarray,
    stockable: bool,
    opening: np.ndarray | None = None,
    quarters: int = 4,
) -> RegionalProblem:
    regions, activities, commodities = output.shape
    season = np.ones(quarters)
    labor = np.repeat(capacity[:, :, None], quarters, axis=2)
    return RegionalProblem(
        region_output=output,
        region_input=used,
        capacity=capacity,
        labor_cap=labor,
        utilization=np.ones_like(capacity),
        season=season,
        demand=demand,
        opening_stock=np.zeros((regions, commodities)) if opening is None else opening,
        stockable=np.full(commodities, stockable, dtype=bool),
        commodity_ids=tuple(f"g{i}" for i in range(commodities)),
        region_ids=tuple(f"r{i}" for i in range(regions)),
    )


def test_autarky_infeasible_but_free_transfers_feasible() -> None:
    """A region that cannot cover its own demand proves routing is required."""
    output = np.array([[[10.0]], [[1.0]]])  # (R=2, A=1, G=1)
    used = np.zeros_like(output)
    capacity = np.array([[10.0], [1.0]])
    demand = np.zeros((2, 1, 4))
    demand[1, 0, :] = 50.0  # region 1 needs far more than it can make

    problem = _problem(
        output=output, used=used, capacity=capacity, demand=demand, stockable=True
    )

    autarky = solve_regional_feasibility(problem, transfers="none")
    assert autarky["status"] == "INFEASIBLE"
    assert autarky["regional_gaps"][0]["region_id"] == "r1"
    assert autarky["regional_gaps"][0]["commodity_id"] == "g0"

    freely = solve_regional_feasibility(problem, transfers="free")
    assert freely["status"] == "LP_FEASIBLE"
    assert freely["transferred_by_commodity"]["g0"] == pytest.approx(196.0, rel=1e-6)
    assert freely["total_transferred"] == pytest.approx(196.0, rel=1e-6)


def test_self_sufficient_regions_need_no_transfers() -> None:
    output = np.array([[[10.0]], [[10.0]]])
    capacity = np.array([[10.0], [10.0]])
    demand = np.zeros((2, 1, 4))
    demand[:, 0, :] = 5.0
    problem = _problem(
        output=output,
        used=np.zeros_like(output),
        capacity=capacity,
        demand=demand,
        stockable=True,
    )
    result = solve_regional_feasibility(problem, transfers="free")
    assert result["status"] == "LP_FEASIBLE"
    assert result["total_transferred"] == pytest.approx(0.0, abs=1e-9)


def test_non_stockable_demand_must_be_produced_in_its_quarter() -> None:
    """Same-quarter services cannot be carried, so late demand cannot be pre-built."""
    output = np.array([[[10.0]]])
    capacity = np.array([[10.0]])
    demand = np.zeros((1, 1, 4))
    demand[0, 0, 3] = 40.0  # only the last quarter consumes

    problem = _problem(
        output=output,
        used=np.zeros_like(output),
        capacity=capacity,
        demand=demand,
        stockable=False,
    )
    result = solve_regional_feasibility(problem, objective="min_output")
    assert result["status"] == "LP_FEASIBLE"
    activity = result["activity"]
    assert np.all(activity[0, 0, :3] == pytest.approx(0.0, abs=1e-9))
    assert activity[0, 0, 3] == pytest.approx(4.0, rel=1e-9)


def test_stockable_demand_may_be_covered_from_opening_stock() -> None:
    output = np.array([[[10.0]]])
    capacity = np.array([[10.0]])
    demand = np.zeros((1, 1, 4))
    demand[0, 0, 0] = 40.0
    problem = _problem(
        output=output,
        used=np.zeros_like(output),
        capacity=capacity,
        demand=demand,
        stockable=True,
        opening=np.array([[40.0]]),
    )
    result = solve_regional_feasibility(problem, objective="min_output")
    assert result["status"] == "LP_FEASIBLE"
    # opening stock covers quarter 0, so nothing is produced there
    assert result["activity"][0, 0, 0] == pytest.approx(0.0, abs=1e-9)
