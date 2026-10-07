"""Toy-4 runtime state, flows and the economic tick kernel (P01).

Typed dataclasses over NumPy column arrays. Every commodity axis is the last
array axis: extending the commodity list to 8/16 later changes the declared
vectors in ``Toy4Parameters``/``Toy4InitialRecipe`` only - no loop in this
module is written over a hard-coded commodity count or a single goods scalar.

Units: household income/cash are per represented household; material pools
(organization input inventories, wholesale, regional retail) are weighted
cohort totals. Household aggregates multiply by ``household_weight``;
organization stocks are never multiplied by a weight again.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from hsm_lab.contract.schemas import ScenarioSpec, Toy4Parameters
from hsm_lab.engine.rng import RngRegistry

TOY4_STATE_VERSION = "toy4-state-v1"


@dataclass
class Toy4State:
    """The complete mutable simulation state at an end-of-quarter boundary."""

    schema_version: str
    completed_ticks: int
    household_id: np.ndarray  # int64 (N,)
    household_region: np.ndarray  # int32 (N,)
    household_weight: np.ndarray  # float64 (N,)
    household_size: np.ndarray  # float64 (N,)
    household_cash: np.ndarray  # float64 (N,)
    organization_id: np.ndarray  # int64 (E,)
    organization_region: np.ndarray  # int32 (E,)
    organization_output_sector: np.ndarray  # int32 (E,)
    organization_capacity: np.ndarray  # float64 (E,)
    organization_labor_capacity: np.ndarray  # float64 (E,)
    organization_input_coefficients: np.ndarray  # float64 (E, G)
    organization_output_mix: np.ndarray  # float64 (E, G)
    organization_input_inventory: np.ndarray  # float64 (E, G)
    wholesale_inventory: np.ndarray  # float64 (G,)
    retail_inventory: np.ndarray  # float64 (R, G)
    region_equivalent_persons: np.ndarray  # float64 (R,)
    regional_share: np.ndarray  # float64 (R,)


@dataclass
class Toy4Forcing:
    """Admitted deterministic quarterly forcing for the full 116-quarter grid."""

    quarters: list[str]
    imports: np.ndarray  # float64 (116, G)
    export_orders: np.ndarray  # float64 (116, G)
    input_artifact_hashes: dict[str, str]


@dataclass
class TickFlows:
    """All entity flows of one completed tick (micro quantities)."""

    tick: int
    quarter: str
    # Organizations (E,) / (E, G)
    organization_target: np.ndarray
    organization_realized: np.ndarray
    desired_input: np.ndarray
    ordered_input: np.ndarray
    allocated_input: np.ndarray
    delivered_input: np.ndarray
    available_input: np.ndarray
    used_input: np.ndarray
    input_unmet: np.ndarray
    organization_output: np.ndarray
    organization_output_shortfall: np.ndarray
    # Households (N,) / (N, G)
    household_income: np.ndarray
    household_desired: np.ndarray
    household_affordable: np.ndarray
    household_realized: np.ndarray
    budget_unmet: np.ndarray
    availability_unmet: np.ndarray
    total_unmet: np.ndarray
    household_spending: np.ndarray
    voluntary_saving: np.ndarray
    forced_saving: np.ndarray
    # National (G,)
    imports: np.ndarray
    export_desired: np.ndarray
    export_realized: np.ndarray
    export_unmet: np.ndarray
    # Regional retail (R, G)
    retail_planned: np.ndarray
    retail_incoming: np.ndarray
    retail_available: np.ndarray
    retail_sales: np.ndarray
    # Opening/closing stock snapshots (mutable pools only)
    organization_input_open: np.ndarray
    organization_input_close: np.ndarray
    wholesale_open: np.ndarray
    wholesale_close: np.ndarray
    retail_open: np.ndarray
    retail_close: np.ndarray
    household_cash_open: np.ndarray
    household_cash_close: np.ndarray
    # Accounting residual snapshots (filled by engine.accounting)
    material_balance_residual: np.ndarray  # (G,)
    material_balance_tolerance: np.ndarray  # (G,)
    cash_balance_residual: np.ndarray  # (R,)
    cash_balance_tolerance: np.ndarray  # (R,)


@dataclass
class Toy4History:
    """Compact per-tick trajectory: O(T*R*G), never a household micro panel."""

    aggregate_rows: list[dict[str, object]] = field(default_factory=list)
    national_rows: list[dict[str, object]] = field(default_factory=list)
    budget_rows: list[dict[str, object]] = field(default_factory=list)
    diagnostic_rows: list[dict[str, object]] = field(default_factory=list)
    event_rows: list[dict[str, object]] = field(default_factory=list)
    digest_chain: str = ""


def produce_leontief(
    available: np.ndarray, coefficients: np.ndarray, target: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """One-round Leontief production: returns (realized output, used inputs).

    ``y_j = min(target_j, min over commodities with a_jg > 0 of
    available_jg / a_jg)``; zero coefficients never bind and never divide by
    zero. Same-tick output is not an input to this round by construction.
    """
    ratio_lims = np.full(coefficients.shape, np.inf)
    positive = coefficients > 0
    np.divide(available, coefficients, out=ratio_lims, where=positive)
    realized = np.minimum(target, np.min(ratio_lims, axis=1))
    realized = np.where(np.isfinite(realized), realized, target)
    used = coefficients * realized[:, None]
    return realized, used


def _region_bincount(state: Toy4State, values: np.ndarray) -> np.ndarray:
    """Weighted (R, G) region sums of a per-household (N, G) matrix."""
    regions = state.retail_inventory.shape[0]
    return np.stack(
        [
            np.bincount(
                state.household_region,
                weights=state.household_weight * values[:, commodity],
                minlength=regions,
            )
            for commodity in range(values.shape[1])
        ],
        axis=1,
    )


def initialize_toy4(spec: ScenarioSpec, rng: RngRegistry) -> Toy4State:
    """Build the initial end-of-quarter-0 state from the declared recipe."""
    parameters = spec.toy4_parameters
    recipe = spec.toy4_initial
    if parameters is None or recipe is None:  # pragma: no cover - guarded earlier
        raise ValueError("toy4 scenario is missing parameters/initial recipe")
    n = spec.households
    e = spec.enterprises
    r = len(spec.region_ids)
    g = len(spec.commodities)

    household_id = np.arange(n, dtype=np.int64)
    household_region = (household_id % r).astype(np.int32)
    household_weight = np.full(n, parameters.equivalent_households / n, dtype=np.float64)
    if spec.stochastic:
        uniforms = rng.uniform("toy4.initial_households", n)
        household_size = (2.0 + np.floor(3.0 * uniforms)).astype(np.float64)
    else:
        household_size = np.full(n, 3.0, dtype=np.float64)
    household_cash = np.full(n, recipe.household_cash, dtype=np.float64)

    organization_id = np.arange(e, dtype=np.int64)
    organization_region = (organization_id % r).astype(np.int32)
    output_sector = (organization_id % g).astype(np.int32)
    sector_counts = np.bincount(output_sector, minlength=g).astype(np.float64)
    capacity = np.asarray(parameters.sector_capacity_totals, dtype=np.float64)[
        output_sector
    ] / sector_counts[output_sector]
    labor_capacity = capacity.copy()
    output_mix = np.zeros((e, g), dtype=np.float64)
    output_mix[np.arange(e), output_sector] = 1.0
    coefficients = np.asarray(parameters.input_coefficients, dtype=np.float64)[
        output_sector
    ].copy()
    target = np.minimum(parameters.target_utilization * capacity, labor_capacity)
    input_inventory = coefficients * target[:, None] * recipe.input_stock_target_quarters

    wholesale = np.asarray(recipe.wholesale_inventory, dtype=np.float64).copy()
    region_persons = np.bincount(
        household_region, weights=household_weight * household_size, minlength=r
    )
    access = np.asarray(parameters.regional_access_multiplier, dtype=np.float64)
    share = region_persons * access
    share = share / share.sum()
    retail = share[:, None] * np.asarray(
        recipe.retail_inventory_totals, dtype=np.float64
    )[None, :]

    return Toy4State(
        schema_version=TOY4_STATE_VERSION,
        completed_ticks=0,
        household_id=household_id,
        household_region=household_region,
        household_weight=household_weight,
        household_size=household_size,
        household_cash=household_cash,
        organization_id=organization_id,
        organization_region=organization_region,
        organization_output_sector=output_sector,
        organization_capacity=capacity,
        organization_labor_capacity=labor_capacity,
        organization_input_coefficients=coefficients,
        organization_output_mix=output_mix,
        organization_input_inventory=input_inventory,
        wholesale_inventory=wholesale,
        retail_inventory=retail,
        region_equivalent_persons=region_persons,
        regional_share=share,
    )


def tick_toy4(
    state: Toy4State, forcing: Toy4Forcing, parameters: Toy4Parameters
) -> TickFlows:
    """Advance exactly one quarter; invariant-checked before it counts.

    Executes the fixed P01 order: (1) freeze opening stocks + forcing,
    (2) organization orders/allocation on pre-production wholesale, (3) one
    production round whose output enters wholesale immediately, (4) exports
    then retail release, (5) household budget/availability rationing,
    (6) accounting invariants; only then does ``completed_ticks`` advance.
    """
    from hsm_lab.engine.accounting import (
        cash_balance_residuals,
        check_toy4_invariants,
        material_balance_residuals,
        snapshot_opening_stocks,
    )

    tick = state.completed_ticks
    if tick >= len(forcing.quarters):
        raise ValueError(
            f"tick {tick} beyond forcing coverage ({len(forcing.quarters)} quarters)"
        )
    quarter = forcing.quarters[tick]
    r = state.retail_inventory.shape[0]
    g = state.wholesale_inventory.shape[0]

    # --- Step 1: opening snapshots -------------------------------------
    org_open = state.organization_input_inventory.copy()
    wholesale_open = state.wholesale_inventory.copy()
    retail_open = state.retail_inventory.copy()
    cash_open = state.household_cash.copy()
    imports = forcing.imports[tick].copy()
    export_orders = forcing.export_orders[tick].copy()

    # --- Step 2: organization demand, orders, allocation ---------------
    target = np.minimum(
        parameters.target_utilization * state.organization_capacity,
        state.organization_labor_capacity,
    )
    desired_input = state.organization_input_coefficients * target[:, None]
    ordered_input = np.maximum(desired_input - org_open, 0.0)
    total_orders = ordered_input.sum(axis=0)
    pre_wholesale = wholesale_open + imports
    rho = np.ones(g)
    ordered_mask = total_orders > 0
    rho[ordered_mask] = np.minimum(
        1.0, pre_wholesale[ordered_mask] / total_orders[ordered_mask]
    )
    allocated_input = ordered_input * rho[None, :]
    delivered_input = allocated_input.copy()
    available_input = org_open + delivered_input
    input_unmet = ordered_input - delivered_input
    delivered_total = delivered_input.sum(axis=0)

    # --- Step 3: one production round ----------------------------------
    realized, used_input = produce_leontief(
        available_input, state.organization_input_coefficients, target
    )
    organization_output = state.organization_output_mix * realized[:, None]
    org_close = available_input - used_input
    output_total = organization_output.sum(axis=0)

    # --- Step 4: exports, retail release --------------------------------
    after_production = pre_wholesale - delivered_total + output_total
    export_realized = np.minimum(export_orders, after_production)
    export_unmet = export_orders - export_realized
    after_export = after_production - export_realized
    offer = (
        np.asarray(parameters.retail_release_fraction, dtype=np.float64) * after_export
    )
    retail_incoming = state.regional_share[:, None] * offer[None, :]
    retail_planned = retail_incoming.copy()
    retail_available = retail_open + retail_incoming
    wholesale_close = after_export - offer

    # --- Step 5: household demand, budget, availability -----------------
    income = parameters.income_per_person * state.household_size
    desired = (
        np.asarray(parameters.desired_per_person, dtype=np.float64)[None, :]
        * state.household_size[:, None]
    )
    prices = np.asarray(parameters.prices, dtype=np.float64)
    cost = desired @ prices
    alpha = np.ones(state.household_id.shape[0])
    binding = cost > 0
    alpha[binding] = np.minimum(1.0, income[binding] / cost[binding])
    affordable = desired * alpha[:, None]
    budget_unmet = desired - affordable

    weighted_affordable = _region_bincount(state, affordable)
    beta = np.ones((r, g))
    demand_mask = weighted_affordable > 0
    np.divide(retail_available, weighted_affordable, out=beta, where=demand_mask)
    beta = np.minimum(beta, 1.0)
    realized_household = affordable * beta[state.household_region, :]
    availability_unmet = affordable - realized_household
    total_unmet = desired - realized_household
    spending = realized_household @ prices
    voluntary_saving = income - affordable @ prices
    forced_saving = availability_unmet @ prices
    cash_close = cash_open + income - spending

    retail_sales = _region_bincount(state, realized_household)
    retail_close = retail_available - retail_sales

    # --- Step 6: write back, verify accounting, then advance ------------
    state.organization_input_inventory = org_close
    state.wholesale_inventory = wholesale_close
    state.retail_inventory = retail_close
    state.household_cash = cash_close

    flows = TickFlows(
        tick=tick,
        quarter=quarter,
        organization_target=target,
        organization_realized=realized,
        desired_input=desired_input,
        ordered_input=ordered_input,
        allocated_input=allocated_input,
        delivered_input=delivered_input,
        available_input=available_input,
        used_input=used_input,
        input_unmet=input_unmet,
        organization_output=organization_output,
        organization_output_shortfall=target - realized,
        household_income=income,
        household_desired=desired,
        household_affordable=affordable,
        household_realized=realized_household,
        budget_unmet=budget_unmet,
        availability_unmet=availability_unmet,
        total_unmet=total_unmet,
        household_spending=spending,
        voluntary_saving=voluntary_saving,
        forced_saving=forced_saving,
        imports=imports,
        export_desired=export_orders,
        export_realized=export_realized,
        export_unmet=export_unmet,
        retail_planned=retail_planned,
        retail_incoming=retail_incoming,
        retail_available=retail_available,
        retail_sales=retail_sales,
        organization_input_open=org_open,
        organization_input_close=org_close,
        wholesale_open=wholesale_open,
        wholesale_close=wholesale_close,
        retail_open=retail_open,
        retail_close=retail_close,
        household_cash_open=cash_open,
        household_cash_close=cash_close,
        material_balance_residual=np.zeros(g),
        material_balance_tolerance=np.zeros(g),
        cash_balance_residual=np.zeros(r),
        cash_balance_tolerance=np.zeros(r),
    )
    flows.material_balance_residual, flows.material_balance_tolerance = (
        material_balance_residuals(state, flows)
    )
    flows.cash_balance_residual, flows.cash_balance_tolerance = (
        cash_balance_residuals(state, flows, prices)
    )
    check_toy4_invariants(
        snapshot_opening_stocks(state, flows), state, flows, parameters
    )
    state.completed_ticks = tick + 1
    return flows
