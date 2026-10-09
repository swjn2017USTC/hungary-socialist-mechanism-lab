"""P05 rule-level closure audit (P05_HISTORICAL_F2_PLAN.md §0.7).

This module is the diagnostic gate for the material-service-money closure
repairs.  It never writes certified LP flows back into a historical run: the
certificate is offline feasibility/price evidence, and the kernel must
reproduce it on its own.

Two pieces:

* ``diagnose_kernel_closure`` drives the *real* kernel from one admitted
  initial state over an ``H0`` diagnostic control (investment growth, foreign
  trade, interest/repayment and behavioural feedback switched off) and measures
  whether stock/cash/output return to a periodic fixed point.  The diagnostic
  ticks carry synthetic labels, never historical or reserved (1986-88) dates.
* ``audit_material_closure`` writes the certificate JSON and returns it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from hsm_lab.contract.material import ORGANIZATION_TYPE_ORDER, MaterialParameters
from hsm_lab.contract.schemas import ScenarioSpec
from hsm_lab.engine import accounting as accounting_module
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.material import MATERIAL_ENGINE_VERSION, tick_material
from hsm_lab.engine.network import build_material_network
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import MaterialForcing, capture_material_stocks, initialize_material

#: Periodic-fixed-point tolerance on the normalised same-season deviation.
PERIODIC_TOLERANCE = 1e-6
# C2 is judged on the stock/output ratio (P05 §0.7): a socialist shortage
# economy carries buffer stocks, so the level drifts while the *ratio* stays
# inside this annual band (observed historical inventory/output ratios cluster
# in the 30-50 range).
STOCK_OUTPUT_RATIO_TOLERANCE = 0.05
#: Window (complete years of same-season pairs) used for the fixed-point check.
PERIODIC_WINDOW = 8


@dataclass
class ClosureCertificate:
    """Result of the offline closure audit for one scenario/catalog."""

    status: str
    scenario_id: str
    catalog_id: str
    engine_version: str
    diagnostic_ticks: int
    periodic_tolerance: float
    max_periodic_residual: float
    periodic_residuals: dict[str, float] = field(default_factory=dict)
    stock_output_ratio_residual: float = 0.0
    stock_output_ratio_tolerance: float = STOCK_OUTPUT_RATIO_TOLERANCE
    stock_output_ratio_annual_drift: float = 0.0
    output_liveness: float = 1.0
    min_liveness: float = 0.5
    credit_debt_growth: float = 0.0
    debt_to_output: float = 0.0
    sbc_transfer_ratio: float = 0.0
    forced_saving_ratio: float = 0.0
    max_material_tolerance_ratio: float = 0.0
    max_finance_tolerance_ratio: float = 0.0
    dead_commodities: list[str] = field(default_factory=list)
    lambda_common: float | None = None
    certified_prices: list[float] | None = None
    notes: str = ""
    diagnostic_rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.status == "ok"
            and self.periodic_residuals.get("output", 0.0) <= self.periodic_tolerance
            and self.periodic_residuals.get("cash", 0.0) <= self.periodic_tolerance
            and self.stock_output_ratio_residual <= self.stock_output_ratio_tolerance
            and self.output_liveness >= self.min_liveness
            and not self.dead_commodities
        )

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["passed"] = self.passed
        return payload


def _h0_material_parameters(parameters: MaterialParameters) -> MaterialParameters:
    """Diagnostic control: growth, trade, interest and repayment off.

    This is a declared static H0 control, not a historical parameter set.
    """
    trade = parameters.trade.model_copy(
        update={
            "cmea_desired_imports": [0.0] * len(parameters.trade.cmea_desired_imports),
            "convertible_desired_imports": [0.0] * len(
                parameters.trade.convertible_desired_imports
            ),
            "cmea_export_demands": [0.0] * len(parameters.trade.cmea_export_demands),
            "convertible_export_demands": [0.0] * len(
                parameters.trade.convertible_export_demands
            ),
            "convertible_opening_reserve": 0.0,
            "convertible_loan_limit": 0.0,
            "convertible_opening_principal": 0.0,
        }
    )
    return parameters.model_copy(
        update={
            "hunger_base": 0.0,
            "hunger_bailout": 0.0,
            "hunger_shortage": 0.0,
            "overorder_strength": 0.0,
            "hoarding_quarters": 0.0,
            "domestic_credit_rate_annual": 0.0,
            "hungary_spread_annual": 0.0,
            "distribution_margins_enabled": True,
            "sbc_redistribution": True,
            "m2_neutral_credit": True,
            "principal_repayment_fraction": 1.0,
            "demand_limited_targets": True,
            "demand_cover": 1.0,
            "demand_floor": 1.0,
            "trade": trade,
        }
    )


def _h0_household_parameters(spec: ScenarioSpec) -> Any:
    """Switch off durable diffusion, private construction and expectation feedback."""
    household = spec.household_parameters
    if household is None:
        return None
    durables = household.durables.model_copy(
        update={
            "new_intention_per_quarter": 0.0,
            "retirement_hazard": [0.0] * len(household.durables.retirement_hazard),
        }
    )
    housing = household.housing.model_copy(
        update={"private_construction_intention_per_quarter": 0.0}
    )
    expectations = household.expectations.model_copy(
        update={"ratchet_strength": 0.0, "ratchet_quarters": 1}
    )
    return household.model_copy(
        update={"durables": durables, "housing": housing, "expectations": expectations}
    )


def _diagnostic_spec(spec: ScenarioSpec) -> ScenarioSpec:
    if spec.material_parameters is None:
        raise ValueError("closure audit requires a material scenario with parameters")
    update: dict[str, Any] = {
        "material_parameters": _h0_material_parameters(spec.material_parameters),
    }
    if spec.material_initial is not None:
        update["material_initial"] = spec.material_initial.model_copy(
            update={"credit_fund_quarters": 20.0, "treasury_deposit_quarters": 1000.0}
        )
    household = _h0_household_parameters(spec)
    if household is not None:
        update["household_parameters"] = household
    return spec.model_copy(update=update)


def _diagnostic_forcing(ticks: int, oil_reference: float) -> MaterialForcing:
    quarters = [f"diag{t:04d}" for t in range(ticks)]
    return MaterialForcing(
        quarters=quarters,
        oil_price=np.full(ticks, oil_reference, dtype=np.float64),
        global_usd_rate=np.zeros(ticks, dtype=np.float64),
        official_fx=np.full(ticks, np.nan, dtype=np.float64),
        cmea_energy_price=np.full(ticks, np.nan, dtype=np.float64),
        segment=["h0_diagnostic"] * ticks,
        input_artifact_hashes={},
    )


def _total_state_metrics(state: Any, flows: Any) -> dict[str, float]:
    weight = np.asarray(state.household_weight, dtype=np.float64)
    cash = float(
        np.sum(weight * np.asarray(state.household_cash, dtype=np.float64))
        + np.sum(np.asarray(state.organization_cash, dtype=np.float64))
        + float(state.treasury_deposit)
    )
    return {
        "output": float(np.sum(np.asarray(flows.activity_realized, dtype=np.float64))),
        "stock": float(np.sum(np.asarray(state.stock_value, dtype=np.float64))),
        "cash": cash,
    }


def _activity_caps(spec: ScenarioSpec, network: Any, state: Any) -> np.ndarray:
    """(4, P) capacity/labor ceiling per diagnostic quarter (declared, not fitted)."""
    from hsm_lab.contract.material import OrganizationType

    parameters = spec.material_parameters
    assert parameters is not None
    activity_org = np.asarray(network.activity_org_index, dtype=np.int64)
    activity_region = np.asarray(network.activity_region, dtype=np.int64)
    capacity = np.asarray(network.activity_capacity, dtype=np.float64).copy()
    labor_cap = np.zeros(capacity.shape[0], dtype=np.float64)
    org_rows = activity_org >= 0
    rows = activity_org[org_rows]
    labor_cap[org_rows] = np.asarray(
        state.organization_labor_available, dtype=np.float64
    )[rows] / np.asarray(state.organization_labor_per_activity, dtype=np.float64)[rows]
    plot_rows = ~org_rows
    if bool(np.any(plot_rows)):
        regions = activity_region[plot_rows]
        labor_cap[plot_rows] = np.asarray(state.plot_labor_budget, dtype=np.float64)[regions] / 0.2
    farm = np.zeros(capacity.shape[0], dtype=bool)
    coop_codes = (
        ORGANIZATION_TYPE_ORDER.index(OrganizationType.AGRICULTURAL_COOPERATIVE),
        ORGANIZATION_TYPE_ORDER.index(OrganizationType.STATE_FARM),
    )
    org_type_arr = np.asarray(state.organization_type, dtype=np.int64)
    farm[org_rows] = np.isin(org_type_arr[rows], coop_codes)
    farm[plot_rows] = True
    factors = parameters.farm_seasonal_factors
    caps = np.zeros((4, capacity.shape[0]), dtype=np.float64)
    for q in range(4):
        season = np.ones(capacity.shape[0], dtype=np.float64)
        season[farm] = float(factors[q % 4])
        caps[q] = np.maximum(
            np.minimum(float(parameters.utilization) * capacity * season, labor_cap), 0.0
        )
    return caps


def physical_feasibility_lambda(
    spec: ScenarioSpec,
    contract: Any,
    *,
    seed: int | None = None,
    region_distance: np.ndarray | None = None,
) -> dict[str, Any]:
    """4-quarter periodic Leontief feasibility bound (P05 §0.7).

    This is the *aggregate* feasibility certificate: it maximises the common
    satisfaction ratio ``lambda`` of the declared household basket subject to
    activity capacity/labor, Leontief input requirements, non-negative
    periodic commodity stocks and same-quarter service production.  It ignores
    per-cell routing, handling work and cash, so ``lambda`` is an upper bound
    that a passing 232-tick kernel certificate still has to confirm.
    """
    from scipy.optimize import linprog
    from scipy.sparse import coo_matrix

    diag_spec = _diagnostic_spec(spec)
    rng = RngRegistry(int(diag_spec.seed if seed is None else seed))
    initial = build_material_initial_conditions(diag_spec, rng)
    network = build_material_network(diag_spec, contract, initial, region_distance)
    state = initialize_material(diag_spec, initial, network)
    parameters = diag_spec.material_parameters
    assert parameters is not None

    P = int(network.activity_capacity.shape[0])
    G = len(network.commodity_ids)
    caps = _activity_caps(diag_spec, network, state)

    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    prod = np.zeros((P, G), dtype=np.float64)
    B = network.B.tocoo()
    np.add.at(prod, (B.row, cell_commodity[B.col]), B.data)
    use = np.zeros((P, G), dtype=np.float64)
    A = network.A.tocoo()
    input_cell = np.asarray(network.input_cell, dtype=np.int64)
    np.add.at(use, (A.row, cell_commodity[input_cell[A.col]]), A.data)

    # Declared final household basket per parent commodity (reference, not observed).
    catalog = network.household_catalog
    to_material = np.asarray(catalog.to_material, dtype=np.float64)  # (H, G)
    household = diag_spec.household_parameters
    if household is None:
        base = np.zeros(to_material.shape[0], dtype=np.float64)
    else:
        base = np.asarray(household.demand.base_per_equivalent_person, dtype=np.float64)
    equivalent = float(initial.equivalent_persons)
    final_demand = to_material.T @ (base * equivalent)  # (G,)

    from hsm_lab.contract.material import commodity_spec

    nonstockable = np.asarray(
        [not commodity_spec(cid).stockable for cid in network.commodity_ids], dtype=bool
    )

    # variable layout: [ y (4P) | s (4G) | f (4G) | lambda ]
    ny, ns, nf = 4 * P, 4 * G, 4 * G
    offset_y, offset_s, offset_f, offset_l = 0, ny, ny + ns, ny + ns + nf
    n = ny + ns + nf + 1
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    b_ub: list[float] = []
    row = 0

    def add(r: int, c: int, v: float) -> None:
        rows.append(r)
        cols.append(c)
        vals.append(v)

    # A. capacity ceilings
    for q in range(4):
        for p in range(P):
            add(row, offset_y + q * P + p, 1.0)
            b_ub.append(float(caps[q, p]))
            row += 1
    n_cap = row

    # B. final basket floor:  D_g * lambda - f[q,g] <= 0
    for q in range(4):
        for g in range(G):
            if final_demand[g] > 0.0:
                add(row, offset_f + q * G + g, -1.0)
                add(row, offset_l, float(final_demand[g]))
                b_ub.append(0.0)
                row += 1

    A_ub = coo_matrix((vals, (rows, cols)), shape=(row, n)).tocsr()
    b_ub_arr = np.asarray(b_ub, dtype=np.float64)

    # C. periodic commodity balance equalities
    erows: list[int] = []
    ecols: list[int] = []
    evals: list[float] = []
    b_eq: list[float] = []
    erow = 0
    for q in range(4):
        q_next = (q + 1) % 4
        for g in range(G):
            for p in range(P):
                coef = prod[p, g] - use[p, g]
                if coef != 0.0:
                    erows.append(erow)
                    ecols.append(offset_y + q * P + p)
                    evals.append(float(coef))
            erows.append(erow)
            ecols.append(offset_s + q * G + g)
            evals.append(1.0)
            erows.append(erow)
            ecols.append(offset_s + q_next * G + g)
            evals.append(-1.0)
            erows.append(erow)
            ecols.append(offset_f + q * G + g)
            evals.append(-1.0)
            b_eq.append(0.0)
            erow += 1
    A_eq = coo_matrix((evals, (erows, ecols)), shape=(erow, n)).tocsr()
    b_eq_arr = np.zeros(erow, dtype=np.float64)

    objective = np.zeros(n, dtype=np.float64)
    objective[offset_l] = -1e6  # maximise lambda first
    objective[offset_s : offset_s + ns] = 1e-6  # then minimise standing inventory

    bounds: list[tuple[float | None, float | None]] = []
    bounds += [(0.0, None)] * ny
    bounds += [(0.0, 0.0 if nonstockable[g] else None) for _q in range(4) for g in range(G)]
    bounds += [(0.0, None)] * nf
    bounds += [(0.0, 1.0)]

    result = linprog(
        objective,
        A_ub=A_ub,
        b_ub=b_ub_arr,
        A_eq=A_eq,
        b_eq=b_eq_arr,
        bounds=bounds,
        method="highs",
    )
    if not result.success:
        return {"status": "lp_infeasible", "lambda_common": 0.0, "message": str(result.message)}
    lam = float(result.x[offset_l])
    stock_total = float(np.sum(result.x[offset_s : offset_s + ns]))
    activity_output = np.asarray(result.x[offset_y : offset_y + ny], dtype=np.float64).reshape(
        4, P
    ).mean(axis=0)
    return {
        "status": "ok",
        "lambda_common": lam,
        "lambda_floor": 0.5,
        "lambda_ok": lam >= 0.5,
        "standing_inventory": stock_total,
        "n_capacity_rows": n_cap,
        "activity_count": P,
        "commodity_count": G,
        "activity_output": activity_output,
        "activity_caps": caps,
    }


def zero_dead_demand_capacity(
    initial: Any, network: Any, certified: dict[str, Any], *, floor: float = 1e-3
) -> Any:
    """P05 §0.7 S-grade recipe: set the capacity/labor of *stockable-output*
    activities whose certified flow is zero to zero, so a closed-demand control
    stops paying wages for output nobody buys.  Non-stockable service producers
    (logistics, utilities) keep their declared capacity because the aggregate LP
    ignores routing and would otherwise starve delivery.

    Returns a new ``MaterialInitialConditions`` (dataclasses.replace), or the
    input unchanged when the certified vectors do not match the network.
    """
    import dataclasses

    from hsm_lab.contract.material import commodity_spec

    y_star = np.asarray(certified.get("activity_output", []), dtype=np.float64)
    declared = np.asarray(certified.get("activity_caps", []), dtype=np.float64)
    if declared.ndim == 2:
        declared = declared.mean(axis=0)
    if y_star.size != int(network.activity_capacity.shape[0]) or declared.shape != y_star.shape:
        return initial
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    stockable_activity = np.zeros(y_star.shape[0], dtype=bool)
    b = network.B.tocoo()
    for activity, cell in zip(b.row.tolist(), b.col.tolist(), strict=True):
        cid = network.commodity_ids[int(cell_commodity[cell])]
        if commodity_spec(cid).stockable:
            stockable_activity[int(activity)] = True
    scale = np.ones(y_star.shape[0], dtype=np.float64)
    positive_declared = declared > 0.0
    scale[positive_declared & stockable_activity] = np.clip(
        y_star[positive_declared & stockable_activity]
        / declared[positive_declared & stockable_activity],
        floor,
        1.0,
    )
    activity_org = np.asarray(network.activity_org_index, dtype=np.int64)
    org_scale: dict[int, float] = {}
    for activity in range(y_star.shape[0]):
        row = int(activity_org[activity])
        if row >= 0:
            org_scale[row] = min(org_scale.get(row, 1.0), float(scale[activity]))
    organizations = tuple(
        org.model_copy(
            update={
                "capacity": org.capacity * org_scale.get(row, 1.0),
                "labor_available": org.labor_available * org_scale.get(row, 1.0),
            }
        )
        if row in org_scale
        else org
        for row, org in enumerate(initial.organizations)
    )
    return dataclasses.replace(initial, organizations=organizations)


def certified_cost_recovery_prices(
    spec: ScenarioSpec, network: Any, state: Any
) -> np.ndarray | None:
    """Leontief unit-cost prices ``p = (I - A^T)^-1 (w * l)`` (P05 §0.7).

    Solves the static price/cash-circulation system so each sector's declared
    unit revenue covers its declared unit intermediate inputs and wage bill.
    Returns ``None`` when the aggregate technology is not productive (spectral
    radius >= 1) or singular, in which case the caller keeps the declared
    admin prices rather than inventing a certified one.
    """
    parameters = spec.material_parameters
    if parameters is None:
        return None
    P = int(network.activity_capacity.shape[0])
    G = len(network.commodity_ids)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    prod = np.zeros((P, G), dtype=np.float64)
    B = network.B.tocoo()
    np.add.at(prod, (B.row, cell_commodity[B.col]), B.data)
    use = np.zeros((P, G), dtype=np.float64)
    A = network.A.tocoo()
    input_cell = np.asarray(network.input_cell, dtype=np.int64)
    np.add.at(use, (A.row, cell_commodity[input_cell[A.col]]), A.data)

    activity_org = np.asarray(network.activity_org_index, dtype=np.int64)
    target = np.asarray(network.activity_capacity, dtype=np.float64) * float(parameters.utilization)
    # aggregate input-output and labor coefficients by output commodity
    tech = np.zeros((G, G), dtype=np.float64)
    labor = np.zeros(G, dtype=np.float64)
    wage = float(parameters.wage_rate)
    for p in range(P):
        outputs = np.flatnonzero(prod[p] > 0.0)
        if outputs.size == 0:
            continue
        unit = float(target[p]) if target[p] > 0.0 else 1.0
        for g_out in outputs:
            share = prod[p, g_out] / float(np.sum(prod[p, outputs]))
            tech[g_out] += share * (use[p] / (prod[p, g_out] * unit))
            labor[g_out] += share * (
                (np.asarray(state.organization_labor_available, dtype=np.float64)[activity_org[p]]
                 if activity_org[p] >= 0 else 0.0)
                / (prod[p, g_out] * unit)
            )
    try:
        prices = np.linalg.solve(np.eye(G) - tech.T, wage * labor)
    except np.linalg.LinAlgError:
        return None
    if not np.all(np.isfinite(prices)) or bool(np.any(prices <= 0.0)):
        return None
    return prices


def diagnose_kernel_closure(
    spec: ScenarioSpec,
    contract: Any,
    *,
    diagnostic_ticks: int = 232,
    seed: int | None = None,
    region_distance: np.ndarray | None = None,
    use_certified_prices: bool = False,
    use_certified_capacity: bool = False,
) -> ClosureCertificate:
    """Drive the real kernel over the H0 control and measure periodicity.

    ``use_certified_prices`` is off by default: the certified cost-recovery
    price vector is compiled and reported, but the kernel cannot yet consume it
    without aligning the household catalog / plot valuation prices (§0.5/§0.6),
    so feeding it in currently breaks a plot-channel stock invariant.
    """
    diag_spec = _diagnostic_spec(spec)
    effective_seed = int(diag_spec.seed if seed is None else seed)
    rng = RngRegistry(effective_seed)
    initial = build_material_initial_conditions(diag_spec, rng)
    network = build_material_network(diag_spec, contract, initial, region_distance)
    state = initialize_material(diag_spec, initial, network)
    parameters = diag_spec.material_parameters
    assert parameters is not None
    certified = certified_cost_recovery_prices(diag_spec, network, state)
    if use_certified_prices and certified is not None:
        priced = parameters.model_copy(update={"prices": [float(v) for v in certified]})
        diag_spec = diag_spec.model_copy(update={"material_parameters": priced})
        # S-grade diagnostic recipe (§0.7): size the Treasury's opening deposit
        # from the certified working capital so it can fund the distribution
        # bridge under the cost-recovery price system, keeping the declared net
        # treasury (treasury_deposit_quarters x wage bill) intact.
        probe = build_material_initial_conditions(diag_spec, RngRegistry(effective_seed))
        national_wage = float(priced.wage_rate) * float(
            sum(float(org.labor_available) for org in probe.organizations)
        )
        recipe = diag_spec.material_initial
        assert recipe is not None
        if national_wage > 0.0 and probe.distribution_working_capital > 0.0:
            quarters = float(recipe.treasury_deposit_quarters) + (
                probe.distribution_working_capital / national_wage
            )
            diag_spec = diag_spec.model_copy(
                update={"material_initial": recipe.model_copy(update={
                    "treasury_deposit_quarters": quarters
                })}
            )
        initial = build_material_initial_conditions(diag_spec, RngRegistry(effective_seed))
        network = build_material_network(diag_spec, contract, initial, region_distance)
        state = initialize_material(diag_spec, initial, network)
        parameters = priced
    # Size the Treasury's opening deposit from the current working capital so it
    # stays fundable (before any capacity change, which alters the wage bill).
    national_wage = float(parameters.wage_rate) * float(
        sum(float(org.labor_available) for org in initial.organizations)
    )
    recipe = diag_spec.material_initial
    assert recipe is not None
    if national_wage > 0.0 and initial.distribution_working_capital > 0.0:
        quarters = float(recipe.treasury_deposit_quarters) + (
            initial.distribution_working_capital / national_wage
        )
        diag_spec = diag_spec.model_copy(
            update={
                "material_initial": recipe.model_copy(
                    update={"treasury_deposit_quarters": quarters}
                )
            }
        )
        initial = build_material_initial_conditions(diag_spec, RngRegistry(effective_seed))
        network = build_material_network(diag_spec, contract, initial, region_distance)
        state = initialize_material(diag_spec, initial, network)
    if use_certified_capacity:
        feasibility = physical_feasibility_lambda(
            spec, contract, seed=seed, region_distance=region_distance
        )
        if feasibility.get("status") == "ok":
            initial = zero_dead_demand_capacity(initial, network, feasibility)
            network = build_material_network(diag_spec, contract, initial, region_distance)
            state = initialize_material(diag_spec, initial, network)
    forcing = _diagnostic_forcing(diagnostic_ticks, float(parameters.world_oil_reference))

    rows: list[dict[str, Any]] = []
    max_material_ratio = 0.0
    max_finance_ratio = 0.0
    for tick in range(diagnostic_ticks):
        opening = capture_material_stocks(state)
        flows = tick_material(state, forcing, parameters, network)
        summary = accounting_module.check_material_invariants(
            opening, state, flows, parameters, network
        )
        max_material_ratio = max(max_material_ratio, float(summary.max_material_tolerance_ratio))
        max_finance_ratio = max(max_finance_ratio, float(summary.max_finance_tolerance_ratio))
        state.completed_ticks += 1
        metrics = _total_state_metrics(state, flows)
        rows.append(
            {
                "tick": tick,
                "output": metrics["output"],
                "stock": metrics["stock"],
                "cash": metrics["cash"],
                "debt": float(np.sum(np.asarray(state.organization_principal, dtype=np.float64))),
                "sbc": float(np.sum(np.asarray(flows.organization_sbc_transfer, dtype=np.float64)[
                    np.asarray(flows.organization_sbc_transfer, dtype=np.float64) > 0.0
                ])),
                "forced": float(
                    np.sum(
                        np.asarray(state.household_weight, dtype=np.float64)
                        * np.asarray(flows.household_forced_saving, dtype=np.float64)
                    )
                ),
                "max_material_tolerance_ratio": float(summary.max_material_tolerance_ratio),
                "max_finance_tolerance_ratio": float(summary.max_finance_tolerance_ratio),
            }
        )

    residuals = _periodic_residuals(rows, diagnostic_ticks)
    ratio_residual, ratio_drift = _stock_output_ratio(rows, diagnostic_ticks)
    dead = _dead_commodities(spec, rows)
    liveness = _output_liveness(rows)
    final_debt = float(np.sum(np.asarray(state.organization_principal, dtype=np.float64)))
    first_debt = float(rows[0]["debt"]) if rows else 0.0
    debt_growth = (
        (final_debt - first_debt) / first_debt if first_debt > 0.0 else 0.0
    )
    tail = rows[-PERIODIC_WINDOW:] if len(rows) >= PERIODIC_WINDOW else rows
    tail_output = sum(row["output"] for row in tail)
    debt_to_output = (final_debt / tail_output) if tail_output > 0.0 else 0.0
    sbc_total = sum(row["sbc"] for row in tail)
    forced_total = sum(row["forced"] for row in tail)
    sbc_transfer_ratio = (sbc_total / tail_output) if tail_output > 0.0 else 0.0
    forced_saving_ratio = (forced_total / tail_output) if tail_output > 0.0 else 0.0
    # A dead economy is not a passing closure: mirror the collapse verdict that
    # audit_material_closure applies, so a certificate can never call it 'ok'.
    cert = ClosureCertificate(
        status=("collapsed" if liveness < 0.5 else "ok"),
        scenario_id=spec.scenario_id,
        catalog_id=network.catalog_id,
        engine_version=MATERIAL_ENGINE_VERSION,
        diagnostic_ticks=diagnostic_ticks,
        periodic_tolerance=PERIODIC_TOLERANCE,
        max_periodic_residual=max(residuals.values()) if residuals else float("inf"),
        periodic_residuals=residuals,
        stock_output_ratio_residual=ratio_residual,
        stock_output_ratio_annual_drift=ratio_drift,
        max_material_tolerance_ratio=max_material_ratio,
        max_finance_tolerance_ratio=max_finance_ratio,
        dead_commodities=dead,
        output_liveness=liveness,
        credit_debt_growth=debt_growth,
        debt_to_output=debt_to_output,
        sbc_transfer_ratio=sbc_transfer_ratio,
        forced_saving_ratio=forced_saving_ratio,
        certified_prices=(None if certified is None else [float(v) for v in certified]),
        notes=(
            "H0 diagnostic control (growth/trade/interest/feedback off); synthetic "
            "diag-tick labels, no historical or reserved dates."
        ),
        diagnostic_rows=rows,
    )
    return cert


#: Mandatory commodity groups that must keep producing under the diagnostic.
MANDATORY_COMMODITIES = ("energy",)


def _dead_commodities(spec: ScenarioSpec, rows: list[dict[str, Any]]) -> list[str]:
    window = rows[-PERIODIC_WINDOW:] if len(rows) >= PERIODIC_WINDOW else rows
    tail_output = float(np.sum([row["output"] for row in window]))
    return [] if tail_output > 0.0 else list(MANDATORY_COMMODITIES)


def _output_liveness(rows: list[dict[str, Any]]) -> float:
    """Tail output relative to the opening output (1.0 = no decay).

    A decaying economy eventually reaches its floor, where same-season
    deviations shrink and a naive periodicity check would read as converged;
    liveness must therefore be reported alongside the residual.
    """
    window = min(PERIODIC_WINDOW, len(rows))
    if window == 0:
        return 0.0
    head = float(np.median([row["output"] for row in rows[:window]]))
    tail = float(np.median([row["output"] for row in rows[-window:]]))
    if head <= 0.0:
        return 0.0
    return tail / head


def _stock_output_ratio(rows: list[dict[str, Any]], ticks: int) -> tuple[float, float]:
    """Same-season residual and annual drift of the stock/output ratio (C2')."""
    if ticks < 2 * 4 or not rows:
        return 0.0, 0.0
    ratio = np.asarray(
        [
            row["stock"] / row["output"] if abs(row["output"]) > 0.0 else np.inf
            for row in rows
        ],
        dtype=np.float64,
    )
    worst = 0.0
    for tick in range(ticks - PERIODIC_WINDOW, ticks):
        prev = ratio[tick - 4]
        current = ratio[tick]
        if not np.isfinite(prev) or not np.isfinite(current):
            continue
        worst = max(worst, abs(current - prev) / max(abs(current), abs(prev), 1.0))
    first = ratio[0]
    last = ratio[-1]
    drift = (
        float(np.log(last / first)) / (ticks / 4.0)
        if first > 0.0 and last > 0.0 and np.isfinite(first) and np.isfinite(last)
        else 0.0
    )
    return float(worst), drift


def _periodic_residuals(rows: list[dict[str, Any]], ticks: int) -> dict[str, float]:
    """Max same-season deviation between the last two complete years."""
    if ticks < 2 * 4:
        return {}
    out: dict[str, float] = {}
    for metric in ("output", "stock", "cash"):
        worst = 0.0
        for tick in range(ticks - PERIODIC_WINDOW, ticks):
            prev = rows[tick - 4][metric]
            current = rows[tick][metric]
            scale = max(abs(current), abs(prev), 1.0)
            worst = max(worst, abs(current - prev) / scale)
        out[metric] = worst
    return out


def audit_material_closure(
    spec: ScenarioSpec,
    contract: Any,
    *,
    output_dir: Path,
    diagnostic_ticks: int = 232,
    seed: int | None = None,
    region_distance: np.ndarray | None = None,
) -> ClosureCertificate:
    """Run the offline closure audit and write its certificate (P05 §0.7)."""
    if output_dir.exists():
        raise FileExistsError(f"closure output dir {output_dir} already exists")
    certificate = diagnose_kernel_closure(
        spec,
        contract,
        diagnostic_ticks=diagnostic_ticks,
        seed=seed,
        region_distance=region_distance,
    )
    feasibility = physical_feasibility_lambda(
        spec, contract, seed=seed, region_distance=region_distance
    )
    certificate.lambda_common = float(feasibility.get("lambda_common", 0.0))
    certificate.notes = (
        certificate.notes
        + f" Aggregate Leontief feasibility lambda={certificate.lambda_common:.3f} "
        f"({feasibility.get('status')}); upper bound ignoring routing/handling/cash."
    )
    if certificate.output_liveness < certificate.min_liveness:
        certificate.status = "collapsed"
    elif (
        max(
            certificate.periodic_residuals.get("output", 0.0),
            certificate.periodic_residuals.get("cash", 0.0),
        )
        > certificate.periodic_tolerance
        or certificate.stock_output_ratio_residual > certificate.stock_output_ratio_tolerance
    ):
        # P05 Gate 1 is not satisfied: output/cash are not periodic, or the
        # buffer-stock ratio drifts beyond its band while output is periodic.
        if certificate.periodic_residuals.get("output", 1.0) <= 1e-3:
            certificate.status = "stable_credit_financed"
        else:
            certificate.status = "closure_failed"
    elif certificate.dead_commodities:
        certificate.status = "dead_sector"
    elif not feasibility.get("lambda_ok", False):
        certificate.status = "lp_infeasible"
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "certificate.json").write_text(
        json.dumps(certificate.to_json(), indent=2, sort_keys=True) + "\n"
    )
    return certificate
