"""Toy-4 material-balance and cash accounting (P01 step C/G).

Every check is per-cell: a local ledger error cannot hide behind a national
aggregate. Violations raise :class:`AccountingError` immediately with the
quarter, ledger name, cell key, both sides, residual and tolerance - the
caller then fails the run closed.
"""

from __future__ import annotations

import math

import numpy as np

from hsm_lab.contract.schemas import ResearchGateError, Toy4Parameters
from hsm_lab.engine.state import TickFlows, Toy4State

ATOL = 1e-9
RTOL = 1e-10


class AccountingError(ResearchGateError):
    """A stock-flow or cash invariant violation; the run must fail closed."""


def tolerance_for(lhs: np.ndarray | float, rhs: np.ndarray | float) -> np.ndarray | float:
    return ATOL + RTOL * np.maximum(np.abs(lhs), np.abs(rhs))


def _cell_key(ledger: str, index: int, shape: tuple[int, ...]) -> str:
    parts: list[str] = []
    remainder = int(index)
    for dim in reversed(shape):
        parts.append(str(remainder % dim))
        remainder //= dim
    parts.reverse()
    return f"{ledger}[{','.join(parts)}]"


def _fail(quarter: str, ledger: str, key: str, lhs: float, rhs: float) -> None:
    residual = lhs - rhs
    tol = float(tolerance_for(lhs, rhs))
    raise AccountingError(
        f"accounting violation in {quarter} ledger={ledger} key={key}: "
        f"lhs={lhs!r} rhs={rhs!r} residual={residual!r} tolerance={tol!r}"
    )


def _compare_cells(
    quarter: str,
    ledger: str,
    lhs: np.ndarray,
    rhs: np.ndarray,
) -> tuple[float, float]:
    """Vectorized cell-wise equality within per-cell tolerance.

    Non-finite operands are violations, never silently-comparing values: NaN
    residuals compare False against any tolerance and must fail closed.
    """
    lhs = np.ascontiguousarray(lhs, dtype=np.float64)
    rhs = np.ascontiguousarray(rhs, dtype=np.float64)
    if lhs.shape != rhs.shape:
        raise AccountingError(
            f"accounting shape mismatch in {quarter} ledger={ledger}: "
            f"{lhs.shape} vs {rhs.shape}"
        )
    if not (np.all(np.isfinite(lhs)) and np.all(np.isfinite(rhs))):
        index = int(
            np.argmax(~(np.isfinite(lhs) & np.isfinite(rhs)).reshape(-1))
        )
        _fail(
            quarter,
            ledger,
            _cell_key(ledger, index, lhs.shape),
            float(lhs.reshape(-1)[index]),
            float(rhs.reshape(-1)[index]),
        )
    residual = lhs - rhs
    tol = np.asarray(tolerance_for(lhs, rhs), dtype=np.float64)
    bad = np.abs(residual) > tol
    if bad.any():
        index = int(np.argmax(bad))
        _fail(
            quarter,
            ledger,
            _cell_key(ledger, index, lhs.shape),
            float(lhs.reshape(-1)[index]),
            float(rhs.reshape(-1)[index]),
        )
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(tol > 0, np.abs(residual) / tol, 0.0)
    return (
        float(np.max(np.abs(residual))) if residual.size else 0.0,
        float(np.max(ratio)) if ratio.size else 0.0,
    )


def _check_array(
    values: np.ndarray, *, quarter: str, ledger: str, non_negative: bool = True
) -> None:
    values = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise AccountingError(
            f"non-finite value in {quarter} ledger={ledger} shape={values.shape}"
        )
    if non_negative and values.size and float(np.min(values)) < -ATOL:
        raise AccountingError(
            f"negative value {float(np.min(values))!r} in {quarter} "
            f"ledger={ledger} shape={values.shape}"
        )


def capture_mutable_stocks(state: Toy4State) -> Toy4State:
    """Snapshot the four accounting-mutable stocks before a tick executes.

    Shares the static columns with the live state; unlike
    :func:`snapshot_opening_stocks`, the mutable pools are copied from the
    *pre-call* state rather than from the returned flows, so continuity is
    established against the actual previously admitted state.
    """
    return Toy4State(
        schema_version=state.schema_version,
        completed_ticks=state.completed_ticks,
        household_id=state.household_id,
        household_region=state.household_region,
        household_weight=state.household_weight,
        household_size=state.household_size,
        household_cash=state.household_cash.copy(),
        organization_id=state.organization_id,
        organization_region=state.organization_region,
        organization_output_sector=state.organization_output_sector,
        organization_capacity=state.organization_capacity,
        organization_labor_capacity=state.organization_labor_capacity,
        organization_input_coefficients=state.organization_input_coefficients,
        organization_output_mix=state.organization_output_mix,
        organization_input_inventory=state.organization_input_inventory.copy(),
        wholesale_inventory=state.wholesale_inventory.copy(),
        retail_inventory=state.retail_inventory.copy(),
        region_equivalent_persons=state.region_equivalent_persons,
        regional_share=state.regional_share,
    )


def snapshot_opening_stocks(state: Toy4State, flows: TickFlows) -> Toy4State:
    """Cheap opening copy: shares static columns, copies mutable stocks."""
    return Toy4State(
        schema_version=state.schema_version,
        completed_ticks=flows.tick,
        household_id=state.household_id,
        household_region=state.household_region,
        household_weight=state.household_weight,
        household_size=state.household_size,
        household_cash=flows.household_cash_open,
        organization_id=state.organization_id,
        organization_region=state.organization_region,
        organization_output_sector=state.organization_output_sector,
        organization_capacity=state.organization_capacity,
        organization_labor_capacity=state.organization_labor_capacity,
        organization_input_coefficients=state.organization_input_coefficients,
        organization_output_mix=state.organization_output_mix,
        organization_input_inventory=flows.organization_input_open,
        wholesale_inventory=flows.wholesale_open,
        retail_inventory=flows.retail_open,
        region_equivalent_persons=state.region_equivalent_persons,
        regional_share=state.regional_share,
    )


def total_stocks(state: Toy4State) -> np.ndarray:
    """S_g = wholesale + sum_j organization input + sum_r regional retail."""
    total: np.ndarray = (
        state.wholesale_inventory
        + state.organization_input_inventory.sum(axis=0)
        + state.retail_inventory.sum(axis=0)
    )
    return total


def _global_material_sides(
    opening: Toy4State, closing: Toy4State, flows: TickFlows
) -> tuple[np.ndarray, np.ndarray]:
    lhs = total_stocks(closing) - total_stocks(opening)
    rhs = (
        flows.imports
        + flows.organization_output.sum(axis=0)
        - flows.used_input.sum(axis=0)
        - flows.export_realized
        - flows.retail_sales.sum(axis=0)
    )
    return lhs, rhs


def material_balance_residuals(
    closing: Toy4State, flows: TickFlows
) -> tuple[np.ndarray, np.ndarray]:
    """Per-commodity global residual Sclose-Sopen-(M+Y-U-X-C) + tolerances."""
    opening = snapshot_opening_stocks(closing, flows)
    lhs, rhs = _global_material_sides(opening, closing, flows)
    return lhs - rhs, np.asarray(tolerance_for(lhs, rhs), dtype=np.float64)


def _regional_cash_sides(
    closing: Toy4State, flows: TickFlows, prices: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Weighted cash change vs income source minus retail receipts, per region."""
    regions = closing.retail_inventory.shape[0]
    lhs = np.zeros(regions)
    rhs = np.zeros(regions)
    for region in range(regions):
        mask = closing.household_region == region
        weight = closing.household_weight[mask]
        lhs[region] = np.sum(
            weight * (flows.household_cash_close[mask] - flows.household_cash_open[mask])
        )
        income = np.sum(weight * flows.household_income[mask])
        receipts = float(np.dot(prices, flows.retail_sales[region]))
        rhs[region] = income - receipts
    return lhs, rhs


def cash_balance_residuals(
    closing: Toy4State, flows: TickFlows, prices: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    lhs, rhs = _regional_cash_sides(closing, flows, prices)
    return lhs - rhs, np.asarray(tolerance_for(lhs, rhs), dtype=np.float64)


def _weighted_realized(closing: Toy4State, flows: TickFlows) -> np.ndarray:
    regions = closing.retail_inventory.shape[0]
    out = np.zeros((regions, flows.household_realized.shape[1]))
    for region in range(regions):
        mask = closing.household_region == region
        if mask.any():
            out[region] = (
                closing.household_weight[mask, None] * flows.household_realized[mask]
            ).sum(axis=0)
    return out


def check_toy4_state_identities(
    state: Toy4State,
    parameters: Toy4Parameters,
    quarter: str,
    initial_household_cash: float,
) -> None:
    """Static/derived state identities recomputed from the declared parameters.

    Organization capacities, labor capacities, input coefficients, output mix,
    regional equivalent persons, shares and household weights are deterministic
    functions of the scenario parameters and the index arrays; a state that
    disagrees with them is not a valid Toy-4 state. Used by the runner's
    per-tick gate and by checkpoint admission.
    """
    g = state.wholesale_inventory.shape[0]
    sector_counts = np.bincount(
        state.organization_output_sector, minlength=g
    ).astype(np.float64)
    expected_capacity = (
        np.asarray(parameters.sector_capacity_totals, dtype=np.float64)[
            state.organization_output_sector
        ]
        / sector_counts[state.organization_output_sector]
    )
    _compare_cells(
        quarter,
        "state.organization_capacity_identity",
        state.organization_capacity,
        expected_capacity,
    )
    _compare_cells(
        quarter,
        "state.organization_labor_capacity_identity",
        state.organization_labor_capacity,
        expected_capacity,
    )
    expected_coefficients = np.asarray(
        parameters.input_coefficients, dtype=np.float64
    )[state.organization_output_sector]
    _compare_cells(
        quarter,
        "state.organization_input_coefficients_identity",
        state.organization_input_coefficients,
        expected_coefficients,
    )
    expected_mix = np.zeros_like(state.organization_output_mix)
    expected_mix[np.arange(state.organization_id.shape[0]), state.organization_output_sector] = 1.0
    _compare_cells(
        quarter,
        "state.organization_output_mix_identity",
        state.organization_output_mix,
        expected_mix,
    )
    expected_persons = np.bincount(
        state.household_region,
        weights=state.household_weight * state.household_size,
        minlength=state.retail_inventory.shape[0],
    )
    _compare_cells(
        quarter,
        "state.region_equivalent_persons_identity",
        state.region_equivalent_persons,
        expected_persons,
    )
    access = np.asarray(parameters.regional_access_multiplier, dtype=np.float64)
    expected_share = expected_persons * access
    expected_share = expected_share / expected_share.sum()
    _compare_cells(
        quarter,
        "state.regional_share_identity",
        state.regional_share,
        expected_share,
    )
    n = state.household_id.shape[0]
    expected_weight = np.full(
        n, float(parameters.equivalent_households) / n, dtype=np.float64
    )
    _compare_cells(
        quarter,
        "state.household_weight_identity",
        state.household_weight,
        expected_weight,
    )
    e = state.organization_id.shape[0]
    _compare_cells(
        quarter,
        "state.household_id_identity",
        state.household_id,
        np.arange(n, dtype=np.int64),
    )
    _compare_cells(
        quarter,
        "state.organization_id_identity",
        state.organization_id,
        np.arange(e, dtype=np.int64),
    )
    r = state.retail_inventory.shape[0]
    _compare_cells(
        quarter,
        "state.household_region_identity",
        state.household_region.astype(np.int64),
        (np.arange(n, dtype=np.int64) % r),
    )
    _compare_cells(
        quarter,
        "state.organization_region_identity",
        state.organization_region.astype(np.int64),
        (np.arange(e, dtype=np.int64) % r),
    )
    _compare_cells(
        quarter,
        "state.organization_output_sector_identity",
        state.organization_output_sector.astype(np.int64),
        (np.arange(e, dtype=np.int64) % g),
    )
    # Toy-4 algebraic invariants of the fixed kernel: within a region all
    # households share the same size-independent budget/rationing factors, so
    # cash is proportional to household size; same-sector organizations are
    # initialized identically and receive identical allocation and Leontief
    # updates, so their input inventories stay equal.
    for region in range(state.retail_inventory.shape[0]):
        mask = state.household_region == region
        if int(mask.sum()) > 1:
            # cash_h = C0 + size_h * K_region (C0 uniform per household).
            ratio = (
                state.household_cash[mask] - float(initial_household_cash)
            ) / state.household_size[mask]
            if float(ratio.max() - ratio.min()) > 1e-9:
                raise AccountingError(
                    f"{quarter}: household cash minus the declared initial cash is "
                    f"not proportional to size within region {region}"
                )
    for sector in range(g):
        mask = state.organization_output_sector == sector
        rows = state.organization_input_inventory[mask]
        if rows.shape[0] > 1 and float(np.abs(rows - rows[0]).max()) > 1e-9:
            raise AccountingError(
                f"{quarter}: same-sector organization inventories diverge for sector "
                f"{sector}"
            )


def _check_all_state_arrays(state: Toy4State, quarter: str) -> None:
    """Every numeric state array must be finite; stocks/cash/shares non-negative;
    index arrays inside their axes and id arrays unique."""
    n = state.household_id.shape[0]
    e = state.organization_id.shape[0]
    r = state.retail_inventory.shape[0]
    g = state.wholesale_inventory.shape[0]
    non_negative = (
        "household_weight",
        "household_size",
        "household_cash",
        "organization_capacity",
        "organization_labor_capacity",
        "organization_input_coefficients",
        "organization_output_mix",
        "organization_input_inventory",
        "wholesale_inventory",
        "retail_inventory",
        "region_equivalent_persons",
        "regional_share",
    )
    for name, values in (
        ("household_id", state.household_id),
        ("household_region", state.household_region),
        ("household_weight", state.household_weight),
        ("household_size", state.household_size),
        ("household_cash", state.household_cash),
        ("organization_id", state.organization_id),
        ("organization_region", state.organization_region),
        ("organization_output_sector", state.organization_output_sector),
        ("organization_capacity", state.organization_capacity),
        ("organization_labor_capacity", state.organization_labor_capacity),
        ("organization_input_coefficients", state.organization_input_coefficients),
        ("organization_output_mix", state.organization_output_mix),
        ("organization_input_inventory", state.organization_input_inventory),
        ("wholesale_inventory", state.wholesale_inventory),
        ("retail_inventory", state.retail_inventory),
        ("region_equivalent_persons", state.region_equivalent_persons),
        ("regional_share", state.regional_share),
    ):
        values = np.asarray(values)
        if not np.all(np.isfinite(values)):
            raise AccountingError(
                f"{quarter}: state array {name} is not finite"
            )
        if name in non_negative and values.size and float(np.min(values)) < -ATOL:
            raise AccountingError(f"{quarter}: state array {name} is negative")
    if (
        int(state.household_region.min()) < 0
        or int(state.household_region.max()) >= r
        or int(state.organization_region.min()) < 0
        or int(state.organization_region.max()) >= r
        or int(state.organization_output_sector.min()) < 0
        or int(state.organization_output_sector.max()) >= g
        or state.organization_output_mix.shape != (e, g)
        or state.organization_input_coefficients.shape != (e, g)
    ):
        raise AccountingError(f"{quarter}: state index/coefficient shapes are invalid")
    if len(set(state.household_id.tolist())) != n or len(
        set(state.organization_id.tolist())
    ) != e:
        raise AccountingError(f"{quarter}: state ids are not unique")
    if abs(float(state.regional_share.sum()) - 1.0) > 1e-9 or float(
        state.regional_share.min()
    ) < 0:
        raise AccountingError(f"{quarter}: regional shares are not a valid distribution")


def _weighted_affordable(closing: Toy4State, flows: TickFlows) -> np.ndarray:
    regions = closing.retail_inventory.shape[0]
    out = np.zeros((regions, flows.household_affordable.shape[1]))
    for region in range(regions):
        mask = closing.household_region == region
        if mask.any():
            out[region] = (
                closing.household_weight[mask, None] * flows.household_affordable[mask]
            ).sum(axis=0)
    return out


def check_toy4_invariants(
    opening: Toy4State,
    closing: Toy4State,
    flows: TickFlows,
    parameters: Toy4Parameters,
) -> dict[str, float]:
    """Verify every material/cash ledger; returns max residual/ratio summary."""
    quarter = flows.quarter
    prices = np.asarray(parameters.prices, dtype=np.float64)

    max_material = 0.0
    max_material_ratio = 0.0
    max_cash = 0.0
    max_cash_ratio = 0.0

    def material(ledger: str, lhs: np.ndarray, rhs: np.ndarray) -> None:
        nonlocal max_material, max_material_ratio
        a, b = _compare_cells(quarter, ledger, lhs, rhs)
        max_material = max(max_material, a)
        max_material_ratio = max(max_material_ratio, b)

    def cash(ledger: str, lhs: np.ndarray, rhs: np.ndarray) -> None:
        nonlocal max_cash, max_cash_ratio
        a, b = _compare_cells(quarter, ledger, lhs, rhs)
        max_cash = max(max_cash, a)
        max_cash_ratio = max(max_cash_ratio, b)

    # --- finiteness / non-negativity over every state and flow array -----
    from dataclasses import fields as dataclass_fields

    non_negative_flow_fields = {
        "imports",
        "export_desired",
        "export_realized",
        "export_unmet",
        "organization_target",
        "organization_realized",
        "desired_input",
        "ordered_input",
        "allocated_input",
        "delivered_input",
        "available_input",
        "used_input",
        "input_unmet",
        "organization_output",
        "organization_output_shortfall",
        "household_income",
        "household_desired",
        "household_affordable",
        "household_realized",
        "budget_unmet",
        "availability_unmet",
        "total_unmet",
        "household_spending",
        "voluntary_saving",
        "forced_saving",
        "retail_planned",
        "retail_incoming",
        "retail_available",
        "retail_sales",
        "organization_input_open",
        "organization_input_close",
        "wholesale_open",
        "wholesale_close",
        "retail_open",
        "retail_close",
        "household_cash_open",
        "household_cash_close",
    }
    for field_info in dataclass_fields(TickFlows):
        value = getattr(flows, field_info.name)
        if not isinstance(value, np.ndarray):
            continue
        _check_array(
            np.asarray(value, dtype=np.float64),
            quarter=quarter,
            ledger=f"flows.{field_info.name}",
            non_negative=field_info.name in non_negative_flow_fields,
        )
    for name, values in (
        ("opening.organization_input_inventory", opening.organization_input_inventory),
        ("closing.organization_input_inventory", closing.organization_input_inventory),
        ("opening.wholesale_inventory", opening.wholesale_inventory),
        ("closing.wholesale_inventory", closing.wholesale_inventory),
        ("opening.retail_inventory", opening.retail_inventory),
        ("closing.retail_inventory", closing.retail_inventory),
        ("opening.household_cash", opening.household_cash),
        ("closing.household_cash", closing.household_cash),
        ("closing.organization_capacity", closing.organization_capacity),
        ("closing.organization_labor_capacity", closing.organization_labor_capacity),
    ):
        _check_array(np.asarray(values, dtype=np.float64), quarter=quarter, ledger=name)
    _check_all_state_arrays(opening, quarter)
    _check_all_state_arrays(closing, quarter)

    # --- state <-> flow snapshot binding (the state is authoritative) -----
    material(
        "opening_org_input_vs_flows",
        opening.organization_input_inventory,
        flows.organization_input_open,
    )
    material(
        "closing_org_input_vs_flows",
        closing.organization_input_inventory,
        flows.organization_input_close,
    )
    material("opening_wholesale_vs_flows", opening.wholesale_inventory, flows.wholesale_open)
    material("closing_wholesale_vs_flows", closing.wholesale_inventory, flows.wholesale_close)
    material("opening_retail_vs_flows", opening.retail_inventory, flows.retail_open)
    material("closing_retail_vs_flows", closing.retail_inventory, flows.retail_close)
    cash("opening_cash_vs_flows", opening.household_cash, flows.household_cash_open)
    cash("closing_cash_vs_flows", closing.household_cash, flows.household_cash_close)

    # --- declared flow identities (equalities, not just inequalities) ------
    material(
        "delivered_equals_allocated",
        flows.delivered_input,
        flows.allocated_input,
    )
    material(
        "available_equals_open_plus_delivered",
        flows.available_input,
        flows.organization_input_open + flows.delivered_input,
    )
    material(
        "input_unmet_equals_ordered_minus_delivered",
        flows.input_unmet,
        flows.ordered_input - flows.delivered_input,
    )
    material(
        "ordered_input_equals_desired_minus_opening",
        flows.ordered_input,
        np.maximum(flows.desired_input - flows.organization_input_open, 0.0),
    )
    material(
        "org_close_equals_available_minus_used",
        flows.organization_input_close,
        flows.available_input - flows.used_input,
    )
    material(
        "desired_input_equals_a_times_target",
        flows.desired_input,
        closing.organization_input_coefficients * flows.organization_target[:, None],
    )
    pre_wholesale = flows.wholesale_open + flows.imports
    allocated_total = flows.allocated_input.sum(axis=0)
    if allocated_total.size and np.any(
        allocated_total > pre_wholesale + np.asarray(tolerance_for(allocated_total, pre_wholesale))
    ):
        raise AccountingError(
            f"{quarter}: total allocated input exceeds available pre-production "
            "wholesale per commodity"
        )
    material(
        "household_income_definition",
        flows.household_income,
        np.asarray(closing.household_size) * float(parameters.income_per_person),
    )
    material(
        "household_desired_definition",
        flows.household_desired,
        np.asarray(closing.household_size)[:, None]
        * np.asarray(parameters.desired_per_person, dtype=np.float64)[None, :],
    )
    material(
        "budget_unmet_definition",
        flows.budget_unmet,
        flows.household_desired - flows.household_affordable,
    )
    material(
        "availability_unmet_definition",
        flows.availability_unmet,
        flows.household_affordable - flows.household_realized,
    )
    # Declared rationing rule: household realization is the affordable basket
    # scaled by the regional availability factor beta.
    weighted_affordable = _weighted_affordable(closing, flows)
    beta = np.ones_like(weighted_affordable)
    demand_mask = weighted_affordable > 0
    np.divide(
        flows.retail_available,
        weighted_affordable,
        out=beta,
        where=demand_mask,
    )
    beta = np.minimum(beta, 1.0)
    material(
        "household_realized_equals_affordable_times_beta",
        flows.household_realized,
        flows.household_affordable * beta[closing.household_region, :],
    )
    material(
        "total_unmet_definition",
        flows.total_unmet,
        flows.household_desired - flows.household_realized,
    )
    material(
        "household_spending_definition",
        flows.household_spending,
        flows.household_realized @ np.asarray(parameters.prices, dtype=np.float64),
    )
    material(
        "retail_planned_equals_incoming",
        flows.retail_planned,
        flows.retail_incoming,
    )
    # Declared distribution rule: release fraction and regional share bind the
    # regional incoming transfer to the post-export wholesale supply.
    after_production = (
        flows.wholesale_open
        + flows.imports
        + flows.organization_output.sum(axis=0)
        - flows.delivered_input.sum(axis=0)
    )
    material(
        "export_realized_equals_min_orders_supply",
        flows.export_realized,
        np.minimum(flows.export_desired, after_production),
    )
    after_export = after_production - flows.export_realized
    offer = (
        np.asarray(parameters.retail_release_fraction, dtype=np.float64) * after_export
    )
    material(
        "retail_incoming_equals_share_times_offer",
        flows.retail_incoming,
        closing.regional_share[:, None] * offer[None, :],
    )
    material(
        "wholesale_close_equals_after_export_minus_offer",
        flows.wholesale_close,
        after_export - offer,
    )
    # Declared production rule: realized output is the Leontief minimum of the
    # target and the positive-coefficient available-input limits.
    ratio_limits = np.full(flows.available_input.shape, np.inf)
    positive = closing.organization_input_coefficients > 0
    np.divide(
        flows.available_input,
        closing.organization_input_coefficients,
        out=ratio_limits,
        where=positive,
    )
    expected_realized = np.minimum(flows.organization_target, np.min(ratio_limits, axis=1))
    expected_realized = np.where(
        np.isfinite(expected_realized), expected_realized, flows.organization_target
    )
    material(
        "realized_equals_leontief_min",
        flows.organization_realized,
        expected_realized,
    )
    material(
        "retail_available_definition",
        flows.retail_available,
        flows.retail_open + flows.retail_incoming,
    )
    material(
        "retail_close_definition",
        flows.retail_close,
        flows.retail_available - flows.retail_sales,
    )
    material(
        "weighted_sales_definition",
        flows.retail_sales,
        _weighted_realized(closing, flows),
    )
    weighted_cash_state_change = closing.household_cash - opening.household_cash
    cash(
        "state_cash_change",
        weighted_cash_state_change,
        flows.household_income - flows.household_spending,
    )

    if closing.household_id.shape != opening.household_id.shape:
        raise AccountingError(f"{quarter}: household axis changed across the tick")
    if closing.organization_id.shape != opening.organization_id.shape:
        raise AccountingError(f"{quarter}: organization axis changed across the tick")
    if closing.retail_inventory.shape != opening.retail_inventory.shape:
        raise AccountingError(f"{quarter}: region/commodity axes changed across the tick")
    if not np.array_equal(closing.household_id, opening.household_id):
        raise AccountingError(f"{quarter}: household ids changed across the tick")
    if not np.array_equal(closing.organization_id, opening.organization_id):
        raise AccountingError(f"{quarter}: organization ids changed across the tick")

    # --- organization ledger ----------------------------------------------
    material(
        "organization_input",
        closing.organization_input_inventory,
        opening.organization_input_inventory + flows.delivered_input - flows.used_input,
    )

    # --- wholesale ledger ---------------------------------------------------
    material(
        "wholesale",
        closing.wholesale_inventory,
        (
            opening.wholesale_inventory
            + flows.imports
            + flows.organization_output.sum(axis=0)
            - flows.delivered_input.sum(axis=0)
            - flows.export_realized
            - flows.retail_incoming.sum(axis=0)
        ),
    )

    # --- retail ledger --------------------------------------------------------
    weighted_realized = _weighted_realized(closing, flows)
    material(
        "retail",
        closing.retail_inventory,
        opening.retail_inventory + flows.retail_incoming - weighted_realized,
    )

    # --- global stock equation --------------------------------------------------
    lhs, rhs = _global_material_sides(opening, closing, flows)
    material("global_stock", lhs, rhs)

    # --- production boundaries ---------------------------------------------------
    material(
        "output_equals_mix_times_y",
        flows.organization_output,
        closing.organization_output_mix * flows.organization_realized[:, None],
    )
    material(
        "used_equals_a_times_y",
        flows.used_input,
        closing.organization_input_coefficients * flows.organization_realized[:, None],
    )
    material(
        "delivered_le_ordered",
        flows.delivered_input,
        np.minimum(flows.delivered_input, flows.ordered_input),
    )
    material(
        "used_le_available",
        flows.used_input,
        np.minimum(flows.used_input, flows.available_input),
    )
    material(
        "realized_le_target",
        flows.organization_realized,
        np.minimum(
            flows.organization_realized,
            np.minimum(flows.organization_target, closing.organization_labor_capacity),
        ),
    )
    material(
        "target_le_capacity",
        flows.organization_target,
        np.minimum(flows.organization_target, closing.organization_capacity),
    )
    material(
        "target_equals_min_util_capacity_labor",
        flows.organization_target,
        np.minimum(
            float(parameters.target_utilization) * closing.organization_capacity,
            closing.organization_labor_capacity,
        ),
    )
    if closing.organization_input_coefficients.size and np.any(
        flows.used_input[closing.organization_input_coefficients <= 0] > ATOL
    ):
        raise AccountingError(
            f"{quarter}: organizations with zero coefficients must use no input"
        )
    material(
        "exports_le_orders",
        flows.export_realized,
        np.minimum(flows.export_realized, flows.export_desired),
    )
    material(
        "export_unmet_definition",
        flows.export_unmet,
        flows.export_desired - flows.export_realized,
    )
    material(
        "production_shortfall_definition",
        flows.organization_output_shortfall,
        flows.organization_target - flows.organization_realized,
    )

    # --- household boundaries ------------------------------------------------------
    material(
        "affordable_le_desired",
        flows.household_affordable,
        np.minimum(flows.household_affordable, flows.household_desired),
    )
    material(
        "realized_le_affordable",
        flows.household_realized,
        np.minimum(flows.household_realized, flows.household_affordable),
    )
    material(
        "spending_le_income",
        flows.household_spending,
        np.minimum(flows.household_spending, flows.household_income),
    )
    material(
        "total_unmet_decomposition",
        flows.total_unmet,
        flows.budget_unmet + flows.availability_unmet,
    )
    material(
        "forced_saving_decomposition",
        flows.forced_saving,
        (flows.household_affordable - flows.household_realized) @ prices,
    )
    material(
        "voluntary_saving_decomposition",
        flows.voluntary_saving,
        flows.household_income - flows.household_affordable @ prices,
    )
    material(
        "sales_le_retail_available",
        flows.retail_sales,
        np.minimum(flows.retail_sales, flows.retail_available),
    )

    # --- cash ledgers ------------------------------------------------------------------
    cash(
        "household_cash",
        flows.household_cash_close - flows.household_cash_open,
        flows.household_income - flows.household_spending,
    )
    cash_lhs, cash_rhs = _regional_cash_sides(closing, flows, prices)
    cash("regional_cash", cash_lhs, cash_rhs)
    weighted_cash_change = float(
        np.sum(
            closing.household_weight
            * (flows.household_cash_close - flows.household_cash_open)
        )
    )
    weighted_income = float(np.sum(closing.household_weight * flows.household_income))
    weighted_receipts = float(np.sum(prices @ flows.retail_sales.T))
    if abs(weighted_cash_change - (weighted_income - weighted_receipts)) > float(
        tolerance_for(weighted_cash_change, weighted_income - weighted_receipts)
    ):
        _fail(
            quarter,
            "national_cash",
            "weighted",
            weighted_cash_change,
            weighted_income - weighted_receipts,
        )

    # --- recorded residual snapshots must equal recomputation --------------------------
    recomputed, recomputed_tol = material_balance_residuals(closing, flows)
    if not np.allclose(flows.material_balance_residual, recomputed, rtol=0, atol=ATOL):
        raise AccountingError(
            f"{quarter}: recorded material balance residual snapshot diverges from "
            "recomputation"
        )
    if not np.allclose(
        flows.material_balance_tolerance, recomputed_tol, rtol=0, atol=ATOL
    ):
        raise AccountingError(
            f"{quarter}: recorded material tolerance snapshot diverges from "
            "recomputation"
        )
    recomputed_cash, recomputed_cash_tol = cash_balance_residuals(closing, flows, prices)
    if not np.allclose(flows.cash_balance_residual, recomputed_cash, rtol=0, atol=ATOL):
        raise AccountingError(
            f"{quarter}: recorded cash balance residual snapshot diverges from "
            "recomputation"
        )
    if not np.allclose(
        flows.cash_balance_tolerance, recomputed_cash_tol, rtol=0, atol=ATOL
    ):
        raise AccountingError(
            f"{quarter}: recorded cash tolerance snapshot diverges from recomputation"
        )
    if recomputed.size:
        max_material = max(max_material, float(np.max(np.abs(recomputed))))
        if np.all(recomputed_tol > 0):
            max_material_ratio = max(
                max_material_ratio,
                float(np.max(np.abs(recomputed) / recomputed_tol)),
            )
    cash_residual_scalar = float(np.max(np.abs(recomputed_cash))) if recomputed_cash.size else 0.0
    max_cash = max(max_cash, cash_residual_scalar)
    if recomputed_cash.size and np.all(recomputed_cash_tol > 0):
        max_cash_ratio = max(
            max_cash_ratio,
            float(np.max(np.abs(recomputed_cash) / recomputed_cash_tol)),
        )

    summary = {
        "max_material_abs_residual": max_material,
        "max_material_tolerance_ratio": max_material_ratio,
        "max_cash_abs_residual": max_cash,
        "max_cash_tolerance_ratio": max_cash_ratio,
    }
    if not all(math.isfinite(value) for value in summary.values()):
        raise AccountingError(f"{quarter}: accounting summary is not finite")
    return summary
