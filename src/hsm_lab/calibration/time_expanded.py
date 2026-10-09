"""F2 time-expanded feasibility (E4-min step 3, declared diagnostic).

The national alignment LP is a *static* feasibility question: it ignores where
production happens, how goods move and when a same-quarter service becomes
available.  The kernel cannot realise such a plan (measured: a national lean-plan
target rule collapses production to zero).  This module answers the next question
— **is there a plan the kernel could actually execute?** — by adding:

* **regional balances**: every activity keeps its own region, and each region must
  cover its own consumption from its own production and opening stock.  No
  inter-regional transfer variables exist in v1, so the certificate answers the
  strictest routing question ("can regions be self-sufficient?"); a region that
  cannot is exactly where routing is required.
* **same-quarter service prefixes**: a non-stockable commodity must be produced in
  the quarter it is consumed (its balance carries no stock), so consumption in a
  quarter may never exceed that quarter's output plus the region's opening stock.

Scope statement in every certificate: no explicit edge flows, no transport or
handling capacity, no finance pre-audit.  It can prove that a plan is *not*
executable (missing capacity/routing) but never that one is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix


@dataclass
class RegionalProblem:
    """Regional activity limits and demand for one catalogue."""

    region_output: np.ndarray  # (R, A, G) gross output per unit of activity
    region_input: np.ndarray  # (R, A, G) input use per unit of activity
    capacity: np.ndarray  # (R, A) capacity of activity a in region r
    labor_cap: np.ndarray  # (R, A, T)
    utilization: np.ndarray  # (R, A)
    season: np.ndarray  # (T,)
    demand: np.ndarray  # (R, G, T)
    opening_stock: np.ndarray  # (R, G)
    stockable: np.ndarray  # (G,)
    commodity_ids: tuple[str, ...]
    region_ids: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)
    scope: str = "regional_v1"
    notes: tuple[str, ...] = field(default_factory=tuple)


def build_regional_problem(
    network: Any,
    *,
    parameters: Any,
    equivalent_persons_by_region: np.ndarray,
    opening_stock_by_region: np.ndarray,
    quarters: int = 4,
) -> RegionalProblem:
    """Compile a regional, time-expanded problem from a built network."""
    from hsm_lab.calibration.alignment import declared_household_demand
    from hsm_lab.contract.material import commodity_spec

    commodity_count = len(network.commodity_ids)
    region_count = len(network.region_ids)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    activity_region = np.asarray(network.activity_region, dtype=np.int64)
    activity_count = int(np.asarray(network.activity_capacity).shape[0])

    from hsm_lab.calibration.alignment import _to_dense_commodity

    input_cell = np.asarray(network.input_cell, dtype=np.int64)
    output = _to_dense_commodity(network.B, cell_commodity, commodity_count)
    used = _to_dense_commodity(network.A, cell_commodity[input_cell], commodity_count)

    region_output = np.zeros((region_count, activity_count, commodity_count))
    region_input = np.zeros_like(region_output)
    for a in range(activity_count):
        r = int(activity_region[a]) if activity_region[a] >= 0 else 0
        region_output[r, a] = output[a]
        region_input[r, a] = used[a]

    capacity = np.zeros((region_count, activity_count))
    for a in range(activity_count):
        r = int(activity_region[a]) if activity_region[a] >= 0 else 0
        capacity[r, a] = float(np.asarray(network.activity_capacity)[a])

    utilization = np.full((region_count, activity_count), float(parameters.utilization))
    season_full = np.asarray(parameters.farm_seasonal_factors, dtype=np.float64)
    season = np.resize(season_full, quarters) if season_full.size else np.ones(quarters)
    labor_cap = np.repeat(
        (capacity * np.asarray(utilization))[:, :, None], quarters, axis=2
    )

    basket = declared_household_demand(
        network, equivalent_persons=float(np.sum(equivalent_persons_by_region))
    )
    demand = np.zeros((region_count, commodity_count, quarters))
    persons = np.asarray(equivalent_persons_by_region, dtype=np.float64)
    if float(persons.sum()) > 0.0:
        share = persons / float(persons.sum())
    else:  # pragma: no cover - defensive
        share = np.full(region_count, 1.0 / region_count)
    for r in range(region_count):
        demand[r, :, :] = (basket * share[r])[:, None]

    stockable = np.asarray(
        [commodity_spec(cid).stockable for cid in network.commodity_ids], dtype=bool
    )
    return RegionalProblem(
        region_output=region_output,
        region_input=region_input,
        capacity=capacity,
        labor_cap=labor_cap,
        utilization=np.asarray(utilization),
        season=season,
        demand=demand,
        opening_stock=np.asarray(opening_stock_by_region, dtype=np.float64),
        stockable=stockable,
        commodity_ids=tuple(network.commodity_ids),
        region_ids=tuple(network.region_ids),
        notes=(
            "no inter-regional transfers in v1: a region must be self-sufficient",
            "no explicit edge flows, transport/handling capacity or finance pre-audit",
            "same-quarter services are non-stockable, so a quarter's use cannot exceed "
            "that quarter's output plus the region's opening stock",
        ),
    )


def solve_regional_feasibility(
    problem: RegionalProblem, *, transfers: str = "none", objective: str = "feasibility"
) -> dict[str, Any]:
    """Feasibility of the regional, time-expanded material plan.

    ``transfers="none"`` keeps the strict autarky question.  ``transfers="free"``
    adds non-negative net-import/export variables M+, M- per region, commodity and
    quarter, constrained so that the national sum is zero (goods move between
    regions, they are not created), and minimises the total transferred volume.
    That minimisation is the **routing requirement**: if the free-transfer problem
    is still infeasible the plan fails on capacity or timing, not on routing.
    """
    R, A, G = problem.region_output.shape
    T = problem.demand.shape[2]
    net = problem.region_output - problem.region_input  # (R, A, G)

    # variables: q (R*A*T) | S (R*G*T) | E (R*G*T)
    free = transfers != "none"
    n_q = R * A * T
    n_s = R * G * T
    n_e = R * G * T
    n_t = 2 * R * G * T if free else 0
    n = n_q + n_s + n_e + n_t

    def q(r: int, a: int, t: int) -> int:
        return (r * A + a) * T + t

    def s(r: int, g: int, t: int) -> int:
        return n_q + (r * G + g) * T + t

    def e(r: int, g: int, t: int) -> int:
        return n_q + n_s + (r * G + g) * T + t

    def m_plus(r: int, g: int, t: int) -> int:
        return n_q + n_s + n_e + (r * G + g) * T + t

    def m_minus(r: int, g: int, t: int) -> int:
        return n_q + n_s + n_e + R * G * T + (r * G + g) * T + t

    eq_r: list[int] = []
    eq_c: list[int] = []
    eq_v: list[float] = []
    b_eq: list[float] = []
    row = 0
    for r in range(R):
        for g in range(G):
            for t in range(T):
                for a in range(A):
                    value = float(net[r, a, g])
                    if value != 0.0:
                        eq_r.append(row)
                        eq_c.append(q(r, a, t))
                        eq_v.append(value)
                eq_r.append(row)
                eq_c.append(e(r, g, t))
                eq_v.append(-1.0)
                if problem.stockable[g]:
                    eq_r.append(row)
                    eq_c.append(s(r, g, t))
                    eq_v.append(-1.0)
                    if t > 0:
                        eq_r.append(row)
                        eq_c.append(s(r, g, t - 1))
                        eq_v.append(1.0)
                if free:
                    eq_r.append(row)
                    eq_c.append(m_plus(r, g, t))
                    eq_v.append(-1.0)
                    eq_r.append(row)
                    eq_c.append(m_minus(r, g, t))
                    eq_v.append(1.0)
                rhs = float(problem.demand[r, g, t])
                if t == 0 and problem.stockable[g]:
                    rhs -= float(problem.opening_stock[r, g])
                b_eq.append(rhs)
                row += 1
    a_eq = coo_matrix((eq_v, (eq_r, eq_c)), shape=(row, n)).tocsr()

    ub_r: list[int] = []
    ub_c: list[int] = []
    ub_v: list[float] = []
    b_ub: list[float] = []
    row = 0
    for r in range(R):
        for a in range(A):
            for t in range(T):
                ub_r.append(row)
                ub_c.append(q(r, a, t))
                ub_v.append(1.0)
                b_ub.append(
                    min(
                        float(problem.utilization[r, a])
                        * float(problem.capacity[r, a])
                        * float(problem.season[t]),
                        float(problem.labor_cap[r, a, t]),
                    )
                )
                row += 1
    a_ub = coo_matrix((ub_v, (ub_r, ub_c)), shape=(row, n)).tocsr()
    nodes = a_eq.shape[1]
    if free:
        # national balance: total net imports across regions are zero per (g, t)
        eq_r2: list[int] = []
        eq_c2: list[int] = []
        eq_v2: list[float] = []
        b_eq2: list[float] = []
        for g in range(G):
            for t in range(T):
                row = len(b_eq2)
                for r in range(R):
                    eq_r2.append(row)
                    eq_c2.append(m_plus(r, g, t))
                    eq_v2.append(1.0)
                    eq_r2.append(row)
                    eq_c2.append(m_minus(r, g, t))
                    eq_v2.append(-1.0)
                b_eq2.append(0.0)
        extra = coo_matrix((eq_v2, (eq_r2, eq_c2)), shape=(len(b_eq2), nodes)).tocsr()
        a_eq = __import__("scipy.sparse", fromlist=["vstack"]).vstack([a_eq, extra]).tocsr()
        b_eq = list(b_eq) + b_eq2
    bounds = [(0.0, None)] * nodes
    cost = np.zeros(nodes)
    if objective == "min_output":
        # lean regional plan: least gross output that still meets demand
        for r in range(R):
            for a in range(A):
                for t in range(T):
                    cost[q(r, a, t)] = 1.0
    if free:
        for r in range(R):
            for g in range(G):
                for t in range(T):
                    cost[m_plus(r, g, t)] = 1.0
                    cost[m_minus(r, g, t)] = 1.0

    primal = linprog(
        cost,
        A_ub=a_ub if row else None,
        b_ub=np.asarray(b_ub, dtype=np.float64) if row else None,
        A_eq=a_eq,
        b_eq=np.asarray(b_eq, dtype=np.float64),
        bounds=bounds,
        method="highs-ds",
        options={"presolve": True, "primal_feasibility_tolerance": 1e-8},
    )
    result: dict[str, Any] = {
        "scope": problem.scope,
        "solver_status": int(primal.status),
        "solver_message": str(primal.message),
        "notes": list(problem.notes),
        "regions": R,
        "activities": A,
        "commodities": G,
        "quarters": T,
        "matrix_shape": n,
        "matrix_nnz": int(a_eq.nnz + a_ub.nnz),
    }
    result["transfers"] = transfers
    if not primal.success:
        result["status"] = "INFEASIBLE" if primal.status == 2 else "SOLVER_FAULT"
        result["regional_gaps"] = regional_gaps(problem)
        return result
    q = primal.x[:n_q].reshape(R, A, T)
    result.update({"status": "LP_FEASIBLE", "activity": q})
    if free:
        net_import = (primal.x[n_q + n_s + n_e : n_q + n_s + n_e + R * G * T] - primal.x[
            n_q + n_s + n_e + R * G * T :
        ]).reshape(R, G, T)
        by_commodity: dict[str, float] = {}
        for g, cid in enumerate(problem.commodity_ids):
            moved = float(np.sum(np.abs(net_import[:, g, :])) / 2.0)
            if moved > 1e-6:
                by_commodity[str(cid)] = moved
        result["transferred_by_commodity"] = dict(
            sorted(by_commodity.items(), key=lambda item: item[1], reverse=True)
        )
        result["total_transferred"] = float(sum(by_commodity.values()))
    return result


def regional_gaps(problem: RegionalProblem) -> list[dict[str, Any]]:
    """Per region/commodity: local potential versus local demand."""
    potential = np.einsum(
        "ra,rag->rg",
        np.asarray(problem.capacity) * np.asarray(problem.utilization),
        np.maximum(np.asarray(problem.region_output) - np.asarray(problem.region_input), 0.0),
    )
    gaps: list[dict[str, Any]] = []
    for r, region in enumerate(problem.region_ids):
        for g, commodity in enumerate(problem.commodity_ids):
            need = float(np.max(problem.demand[r, g]))
            if need <= 0.0:
                continue
            have = float(potential[r, g])
            if need > have + 1e-9:
                gaps.append(
                    {
                        "region_id": str(region),
                        "commodity_id": str(commodity),
                        "required": need,
                        "local_potential": have,
                        "shortfall": need - have,
                    }
                )
    return sorted(gaps, key=lambda item: item["shortfall"], reverse=True)
