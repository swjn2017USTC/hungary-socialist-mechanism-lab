"""F2 activity-level capacity alignment (E4-min, declared diagnostic).

Given the *declared* final demand and the compiled technology, this module
answers "what activity levels and capacities are needed, and are they feasible
under the existing capacity, labour and technology?"  It never writes capacity
back to a scenario and never invents resources.

Scope of v1 (stated in every certificate):

* national commodity balances over four quarters; stockable commodities carry
  inventory, non-stockable ones record an explicit expiry term;
* capacity and labour ceilings per activity and quarter, with seasonal factors;
* the demand channels the caller declares (by default the household basket);
* **not** modelled yet: inter-regional routing, the same-quarter service tier
  prefixes and the finance pre-audit.  The certificate therefore reports
  ``scope="national_v1"`` and cannot by itself claim execution feasibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

QUARTERS = 4


@dataclass
class AlignmentProblem:
    """Everything the alignment LP needs, already compiled to commodity axes."""

    activity_output: np.ndarray  # (A, G) gross output per unit of activity
    activity_input: np.ndarray  # (A, G) input use per unit of activity
    capacity: np.ndarray  # (A,) original capacity
    labor_cap: np.ndarray  # (A, T) ceiling per activity and quarter
    utilization: np.ndarray  # (A,)
    season: np.ndarray  # (T,)
    demand: np.ndarray  # (G, T) declared final demand
    stockable: np.ndarray  # (G,) bool
    commodity_ids: tuple[str, ...]
    activity_ids: tuple[str, ...] = ()
    scope: str = "national_v1"
    notes: tuple[str, ...] = field(default_factory=tuple)


def _to_dense_commodity(
    matrix: Any, column_commodity: np.ndarray, commodity_count: int
) -> np.ndarray:
    """Aggregate an activity x cell sparse matrix onto the commodity axis."""
    coo = matrix.tocoo()
    rows = coo.row.astype(np.int64)
    cols = np.asarray(column_commodity)[coo.col.astype(np.int64)]
    valid = cols >= 0
    out = coo_matrix(
        (coo.data[valid], (rows[valid], cols[valid])),
        shape=(matrix.shape[0], commodity_count),
    )
    return np.asarray(out.tocsr().todense(), dtype=np.float64)


def declared_household_demand(network: Any, *, equivalent_persons: float) -> np.ndarray:
    """The declared household basket on the material commodity axis."""
    parameters = network.household_parameters
    catalog = network.household_catalog
    base = np.asarray(parameters.demand.base_per_equivalent_person, dtype=np.float64)
    to_material = np.asarray(catalog.to_material, dtype=np.float64)
    return base.dot(to_material) * float(equivalent_persons)


def build_alignment_problem(
    network: Any,
    *,
    parameters: Any,
    equivalent_persons: float,
    demand: np.ndarray | None = None,
    quarters: int = QUARTERS,
) -> AlignmentProblem:
    """Compile the alignment problem from a built F2 network."""
    commodity_count = len(network.commodity_ids)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    input_cell = np.asarray(network.input_cell, dtype=np.int64)
    output = _to_dense_commodity(network.B, cell_commodity, commodity_count)
    used = _to_dense_commodity(network.A, cell_commodity[input_cell], commodity_count)

    activity_count = output.shape[0]
    capacity = np.asarray(network.activity_capacity, dtype=np.float64).copy()
    utilization = np.full(activity_count, float(parameters.utilization), dtype=np.float64)
    season_full = np.asarray(parameters.farm_seasonal_factors, dtype=np.float64)
    season = np.resize(season_full, quarters) if season_full.size else np.ones(quarters)

    if demand is None:
        declared = declared_household_demand(network, equivalent_persons=equivalent_persons)
        demand = np.repeat(declared[:, None], quarters, axis=1)
    demand = np.asarray(demand, dtype=np.float64)
    if demand.shape != (commodity_count, quarters):
        raise ValueError(f"demand must be ({commodity_count}, {quarters})")

    from hsm_lab.contract.material import commodity_spec

    stockable = np.asarray(
        [commodity_spec(cid).stockable for cid in network.commodity_ids], dtype=bool
    )
    # No separate activity-level labour axis is compiled yet, so the labour
    # ceiling equals the utilization-limited capacity ceiling; the certificate
    # records this approximation.
    labor_cap = np.repeat(
        (capacity * np.asarray(utilization))[:, None], quarters, axis=1
    )
    return AlignmentProblem(
        activity_output=output,
        activity_input=used,
        capacity=capacity,
        labor_cap=labor_cap,
        utilization=np.asarray(utilization),
        season=season,
        demand=demand,
        stockable=stockable,
        commodity_ids=tuple(network.commodity_ids),
        notes=(
            "labour ceiling approximated by utilization x capacity: the compiled "
            "network exposes no separate activity-level labour axis yet",
            "inter-regional routing and same-quarter service tiers are not modelled",
            "capacity is bounded by the original profile: E4 never creates resources",
        ),
    )


def _assemble(problem: AlignmentProblem) -> dict[str, Any]:
    net = problem.activity_output - problem.activity_input
    activities, commodities = problem.activity_input.shape
    quarters = problem.demand.shape[1]
    cap = np.asarray(problem.capacity, dtype=np.float64)
    util = np.asarray(problem.utilization, dtype=np.float64)
    season = np.asarray(problem.season, dtype=np.float64)

    # variables: q (A*T) | C (A) | S (G*T) | E (G*T) | z+ (A) | z- (A)
    n_q = activities * quarters
    n_c = activities
    n_s = commodities * quarters
    n_e = commodities * quarters
    n_z = activities
    n = n_q + n_c + n_s + n_e + 2 * n_z

    def q(a: int, t: int) -> int:
        return a * quarters + t

    def c(a: int) -> int:
        return n_q + a

    def s(g: int, t: int) -> int:
        return n_q + n_c + g * quarters + t

    def e(g: int, t: int) -> int:
        return n_q + n_c + n_s + g * quarters + t

    def zp(a: int) -> int:
        return n_q + n_c + n_s + n_e + a

    def zm(a: int) -> int:
        return n_q + n_c + n_s + n_e + n_z + a

    # --- equality: commodity balances -------------------------------------
    eq_r: list[int] = []
    eq_c: list[int] = []
    eq_v: list[float] = []
    b_eq: list[float] = []
    row = 0
    for g in range(commodities):
        for t in range(quarters):
            for a in range(activities):
                if net[a, g] != 0.0:
                    eq_r.append(row)
                    eq_c.append(q(a, t))
                    eq_v.append(float(net[a, g]))
            eq_r.append(row)
            eq_c.append(e(g, t))
            eq_v.append(-1.0)
            if problem.stockable[g]:
                eq_r.append(row)
                eq_c.append(s(g, t))
                eq_v.append(1.0)
                if t > 0:
                    eq_r.append(row)
                    eq_c.append(s(g, t - 1))
                    eq_v.append(-1.0)
            b_eq.append(float(problem.demand[g, t]))
            row += 1
    a_eq = coo_matrix((eq_v, (eq_r, eq_c)), shape=(row, n)).tocsr()
    b_eq_arr = np.asarray(b_eq, dtype=np.float64)

    # --- inequalities: capacity, capacity bound, labour, deviation --------
    ub_r: list[int] = []
    ub_c: list[int] = []
    ub_v: list[float] = []
    b_ub: list[float] = []
    row = 0
    for a in range(activities):
        for t in range(quarters):
            ub_r += [row, row]
            ub_c += [q(a, t), c(a)]
            ub_v += [1.0, -float(util[a]) * float(season[t])]
            b_ub.append(0.0)
            row += 1
    for a in range(activities):
        ub_r.append(row)
        ub_c.append(c(a))
        ub_v.append(1.0)
        b_ub.append(float(cap[a]))
        row += 1
    for a in range(activities):
        for t in range(quarters):
            ub_r.append(row)
            ub_c.append(q(a, t))
            ub_v.append(1.0)
            b_ub.append(float(problem.labor_cap[a, t]))
            row += 1
    for a in range(activities):
        ub_r += [row, row, row]
        ub_c += [c(a), zp(a), zm(a)]
        ub_v += [1.0, -1.0, 1.0]
        b_ub.append(float(cap[a]))
        row += 1
    a_ub = coo_matrix((ub_v, (ub_r, ub_c)), shape=(row, n)).tocsr()

    bounds = [(0.0, None)] * n
    for a in range(activities):
        bounds[c(a)] = (0.0, float(cap[a]))
    scale = np.maximum(np.abs(cap), 1.0)
    objective = np.zeros(n)
    objective[n_q + n_c + n_s + n_e : n_q + n_c + n_s + n_e + n_z] = 1.0 / scale
    objective[n_q + n_c + n_s + n_e + n_z :] = 1.0 / scale
    return {
        "n": n,
        "n_q": n_q,
        "n_c": n_c,
        "a_ub": a_ub,
        "b_ub": np.asarray(b_ub, dtype=np.float64),
        "a_eq": a_eq,
        "b_eq": b_eq_arr,
        "bounds": bounds,
        "objective": objective,
        "net": net,
        "scale": scale,
    }


def solve_alignment(problem: AlignmentProblem) -> dict[str, Any]:
    """Feasibility plus the minimal relative capacity realignment."""
    compiled = _assemble(problem)
    primal = linprog(
        compiled["objective"],
        A_ub=compiled["a_ub"],
        b_ub=compiled["b_ub"],
        A_eq=compiled["a_eq"],
        b_eq=compiled["b_eq"],
        bounds=compiled["bounds"],
        method="highs-ds",
        options={
            "presolve": True,
            "primal_feasibility_tolerance": 1e-8,
            "dual_feasibility_tolerance": 1e-8,
        },
    )
    base = {
        "scope": problem.scope,
        "solver_status": int(primal.status),
        "solver_message": str(primal.message),
        "notes": list(problem.notes),
        "quarters": int(problem.demand.shape[1]),
        "activities": int(problem.activity_input.shape[0]),
        "commodities": int(problem.activity_input.shape[1]),
        "matrix_shape": compiled["n"],
        "matrix_nnz": int(compiled["a_ub"].nnz + compiled["a_eq"].nnz),
    }
    if not primal.success:
        base["status"] = "INFEASIBLE" if primal.status == 2 else "SOLVER_FAULT"
        base["gaps"] = _static_gaps(problem)
        return base

    activities = problem.activity_input.shape[0]
    quarters = problem.demand.shape[1]
    q = primal.x[: compiled["n_q"]].reshape(activities, quarters)
    capacity_star = primal.x[compiled["n_q"] : compiled["n_q"] + compiled["n_c"]]
    base.update(
        {
            "status": "LP_FEASIBLE",
            "capacity": capacity_star,
            "activity": q,
            "capacity_deviation": float(
                np.sum(np.abs(capacity_star - problem.capacity) / compiled["scale"])
            ),
            "at_original_ceiling": int(
                np.count_nonzero(capacity_star >= problem.capacity - 1e-9)
            ),
            "max_balance_residual": float(
                np.max(
                    np.abs(
                        compiled["a_eq"] @ primal.x - compiled["b_eq"]
                    )
                )
            ),
        }
    )
    return base


def _static_gaps(problem: AlignmentProblem) -> list[dict[str, Any]]:
    """Cheapest static diagnostic: required final demand vs installed potential."""
    potential = np.asarray(problem.capacity) @ np.maximum(
        np.asarray(problem.activity_output) - np.asarray(problem.activity_input), 0.0
    )
    gaps = []
    for g, cid in enumerate(problem.commodity_ids):
        need = float(np.max(problem.demand[g]))
        have = float(potential[g])
        if need > have + 1e-9:
            gaps.append(
                {
                    "commodity_id": str(cid),
                    "required": need,
                    "potential": have,
                    "shortfall": need - have,
                }
            )
    return sorted(gaps, key=lambda item: item["shortfall"], reverse=True)
