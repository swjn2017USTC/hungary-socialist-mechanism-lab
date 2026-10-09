"""Compact material-economy output tables (P02 plan step 7).

Nine tables — ``aggregates``, ``stage_balances``, ``national_accounts``,
``household_budgets``, ``organization_diagnostics``, ``financial_accounts``,
``departments``, ``tick_diagnostics``, ``events`` — all Parquet + DuckDB,
all derived from the authoritative stock-cell catalog and the pinned
``MaterialTickFlows`` surface. No per-tick household/edge micro panel is
ever written: the compact grid is the whole trajectory record.

Derivation rules (documented choices beyond the plan/interface text):

* per-cell *opening* stocks are reconstructed as closing ``state.stock_value``
  minus the tick's per-cell deltas (production via ``B @ activity_realized``,
  edge deliveries, consumption ``used``, imports, retail sales and the two
  plot household channels). This is the only opening source compatible with
  the pinned append signature; adjacent-tick continuity then holds exactly
  because closing values come from the authoritative state.
* plot self-use *quantity* per household is ``household_self_use`` (an
  imputed value) divided by the ready-food admin price; plot direct-market
  sales quantity is the regional food realization minus retail sales minus
  that self-use quantity.
* services_transport (non-stockable) stock columns are identically zero by
  ontology; its per-row ``expiry`` is the balancing term of the row identity.
* financial ``treasury`` opening comes from the runner-supplied
  ``invariant_summary["treasury_deposit_open"]`` when present, else from the
  previous tick's history row, else null (never fabricated).
* ``housing_completed`` (needed by ``derive_departments``) must be supplied
  by the runner through ``invariant_summary`` — a missing key fails closed.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import polars as pl

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.contract.material import (
    ORGANIZATION_TYPE_ORDER,
    PURPOSE_CODES,
    STAGE_CODES,
    CellOwnerKind,
    MaterialParameters,
    RoutePurpose,
    commodity_spec,
    legal_stages,
)
from hsm_lab.engine.state import (
    MaterialHistory,
    MaterialState,
    MaterialTickFlows,
    build_material_prices,
    material_tick_event,
    owner_kind_code,
)
from hsm_lab.provenance.manifest import canonical_json
from hsm_lab.storage.output import write_duckdb
from hsm_lab.storage.political_output import (
    INFORMATION_COLUMNS,
    INFORMATION_QUARTERS,
    OPPOSITION_COLUMNS,
    OPPOSITION_REGIONS,
    POLICY_DECISION_COLUMNS,
    POLICY_DECISIONS,
    POLITICAL_EVENT_COLUMNS,
    POLITICAL_EVENTS,
    POLITICAL_QUARTER_COLUMNS,
    POLITICAL_QUARTERS,
    POLITICAL_STRING_COLUMNS,
    POLITICAL_TABLES,
)

TABLES = (
    "aggregates",
    "stage_balances",
    "national_accounts",
    "household_budgets",
    "organization_diagnostics",
    "financial_accounts",
    "departments",
    "tick_diagnostics",
    "events",
    *POLITICAL_TABLES,
)

MATERIAL_TICK_EVENT = material_tick_event()

AGGREGATE_COLUMNS = [
    "tick",
    "quarter",
    "region_id",
    "commodity_id",
    "desired",
    "ordered",
    "ordered_gross",
    "unfunded",
    "allocated",
    "delivered",
    "used",
    "financial_delivery_blocked",
    "physical_delivery_blocked",
    "production",
    "production_raw",
    "production_ready",
    "input_open",
    "input_close",
    "output_open",
    "output_close",
    "wholesale_open",
    "wholesale_close",
    "retail_open",
    "retail_close",
    "household_desired",
    "household_budget_unmet",
    "household_availability_unmet",
    "plot_self_use",
    "plot_market_sales",
]

STAGE_COLUMNS = [
    "tick",
    "quarter",
    "region_id",
    "commodity_id",
    "stage",
    "opening",
    "closing",
    "receipts",
    "production",
    "used",
    "delivered_out",
    "expiry",
    "residual",
]

NATIONAL_COLUMNS = [
    "tick",
    "quarter",
    "commodity_id",
    "cmea_imports",
    "convertible_imports",
    "imports",
    "cmea_exports",
    "convertible_exports",
    "exports",
    "production",
    "production_raw",
    "production_ready",
    "used",
    "household_consumption",
    "expiry",
    "organization_input_open",
    "organization_input_close",
    "organization_output_open",
    "organization_output_close",
    "wholesale_open",
    "wholesale_close",
    "retail_open",
    "retail_close",
    "plot_open",
    "plot_close",
    "project_wip_open",
    "project_wip_close",
    "import_pool_open",
    "import_pool_close",
    "total_stock_open",
    "total_stock_close",
    "material_balance_residual",
    "material_balance_tolerance_ratio",
]

BUDGET_COLUMNS = [
    "tick",
    "quarter",
    "region_id",
    "cash_open",
    "cash_close",
    "pre_purchase_wages",
    "plot_income_formal",
    "plot_income_direct",
    "late_wage_payment",
    "spending",
    "self_use_imputed",
    "plot_input_funding",
    "budget_available",
    "voluntary_saving",
    "forced_saving",
    "deferred_open",
    "deferred_close",
]

ORGANIZATION_COLUMNS = [
    "tick",
    "quarter",
    "region_id",
    "organization_type",
    "organization_count",
    "capacity_sum",
    "capacity_mean",
    "labor_sum",
    "labor_mean",
    "target_sum",
    "realized_sum",
    "ordered_sum",
    "delivered_sum",
    "input_bottleneck_share",
    "credit_requested",
    "credit_approved",
    "credit_drawn",
    "investment_requested",
    "investment_approved",
    "investment_completed",
    "bailout_requested",
    "bailout_granted",
    "principal_sum",
    "wage_arrears_sum",
    "interest_arrears_sum",
    "cash_sum",
    "shortage_expectation_mean",
    "bailout_expectation_mean",
]

FINANCIAL_COLUMNS = [
    "tick",
    "quarter",
    "account_id",
    "currency",
    "account_label",
    "opening",
    "closing",
    "credit_drawn",
    "grant",
    "interest_accrued",
    "interest_paid",
    "principal_repaid",
    "residual",
]

DEPARTMENT_COLUMNS = [
    "tick",
    "quarter",
    "department",
    "actual_use_value",
    "attributed_output_value",
    "service_use_productive",
    "service_use_household",
]

DIAGNOSTIC_COLUMNS = [
    "tick",
    "quarter",
    "digest",
    "max_material_abs_residual",
    "max_material_tolerance_ratio",
    "max_finance_abs_residual",
    "max_finance_tolerance_ratio",
    "checked_cells",
    "bottleneck_demand_count",
    "financial_blocked_total",
    "forcing_segment",
    "expired_services",
]

EVENT_COLUMNS = ["tick", "quarter", "event_type", "details_json"]

DEPARTMENT_ROWS = (
    "department_I",
    "department_II",
    "services",
    "exports",
    "unclassified",
)

ORGANIZATION_TYPE_IDS = tuple(t.value for t in ORGANIZATION_TYPE_ORDER)

_STAGE_NAME_OF = {code: name for name, code in STAGE_CODES.items()}
def stockable_by_commodity(commodity_ids: Sequence[str]) -> np.ndarray:
    """Stockability per commodity, read from the declared registry.

    Never defaults an unknown commodity to stockable: an undeclared id is a
    configuration error, and silently treating a service as storable is exactly
    how F2's published expiry column became a structural zero.
    """
    return np.array([commodity_spec(commodity_id).stockable for commodity_id in commodity_ids])

_KIND_ORG = owner_kind_code(CellOwnerKind.ORGANIZATION)
_KIND_PLOT = owner_kind_code(CellOwnerKind.PLOT)
_KIND_PROJECT = owner_kind_code(CellOwnerKind.PROJECT)
_KIND_TREASURY = owner_kind_code(CellOwnerKind.TREASURY_IMPORT)

# Purposes whose ``used`` decrements the destination stock cell (production
# input consumption, project installation, plot input consumption). Trader
# release and boundary sinks are excluded: the physical movement of those is
# already counted on the edge/source side.
_CONSUMING_PURPOSES = tuple(
    PURPOSE_CODES[purpose]
    for purpose in (
        RoutePurpose.INTERMEDIATE,
        RoutePurpose.INVESTMENT,
        RoutePurpose.PRIVATE_PLOT,
    )
)

_DOMESTIC_CURRENCY = "p02_domestic_currency"
_USD_CURRENCY = "USD"
_CMEA_CURRENCY = "cmea_settlement_unit"


def _mean(total: float, count: int) -> float | None:
    return total / count if count > 0 else None


def _cell_scatter(size: int, indices: np.ndarray, values: np.ndarray) -> np.ndarray:
    out = np.zeros(size, dtype=np.float64)
    if indices.size:
        np.add.at(out, indices, values)
    return out


def _household_region_sums(state: MaterialState, values: np.ndarray, regions: int) -> np.ndarray:
    """Weighted regional sums of an (N,) or (N, G) per-household array."""
    weight = state.household_weight
    if values.ndim == 1:
        return np.bincount(
            state.household_region, weights=weight * values, minlength=regions
        ).astype(np.float64, copy=True)
    commodities = values.shape[1]
    out = np.zeros((regions, commodities), dtype=np.float64)
    for commodity in range(commodities):
        out[:, commodity] = np.bincount(
            state.household_region,
            weights=weight * values[:, commodity],
            minlength=regions,
        )
    return out


class _CellLedger:
    """Per-cell production/receipt/consumption/outflow views for one tick."""

    def __init__(
        self,
        state: MaterialState,
        flows: MaterialTickFlows,
        network: Any,
        parameters: MaterialParameters,
        commodity_ids: list[str],
        regions: int,
        commodities: int,
        opening_stock: np.ndarray | None = None,
    ) -> None:
        self.cell_owner_kind = np.asarray(network.cell_owner_kind)
        self.cell_owner_id = np.asarray(network.cell_owner_id)
        self.cell_region = np.asarray(network.cell_region)
        self.cell_pool = np.asarray(network.cell_pool)
        self.cell_commodity = np.asarray(network.cell_commodity)
        self.cell_stage = np.asarray(network.cell_stage)
        cell_count = int(self.cell_owner_kind.shape[0])
        self.cell_count = cell_count
        self.regions = regions
        self.commodities = commodities

        self.closing = np.asarray(state.stock_value, dtype=np.float64)

        # production into cells: B (CSR, P x S) column-scaled by realized output
        b_indptr = np.asarray(network.B.indptr)
        b_indices = np.asarray(network.B.indices)
        b_data = np.asarray(network.B.data, dtype=np.float64)
        b_rows = np.repeat(np.arange(b_indptr.size - 1), np.diff(b_indptr))
        self.production = _cell_scatter(
            cell_count, b_indices, b_data * flows.activity_realized[b_rows]
        )

        # edge deliveries in/out (destination -1 edges are boundary sinks)
        edge_dest = np.asarray(network.edge_destination_cell)
        edge_source = np.asarray(network.edge_source_cell)
        edge_delivered = np.asarray(flows.edge_delivered, dtype=np.float64)
        real_dest = edge_dest >= 0
        self.delivered_in = _cell_scatter(
            cell_count, edge_dest[real_dest], edge_delivered[real_dest]
        )
        # Household acquisition is also represented by retail_sales; exclude
        # retail→household boundary edges here because stage rows add that
        # authoritative regional sales flow separately as retail_out.
        edge_purpose = np.asarray(network.edge_purpose, dtype=np.int64)
        retail_household_edge = (
            (edge_purpose == PURPOSE_CODES[RoutePurpose.HOUSEHOLD])
            & (self.cell_owner_kind[edge_source] == _KIND_ORG)
            & (self.cell_pool[edge_source] == 3)
        )
        stock_edges = ~retail_household_edge
        self.delivered_out = _cell_scatter(
            cell_count, edge_source[stock_edges], edge_delivered[stock_edges]
        )

        demand_cell = np.asarray(network.demand_cell)
        demand_purpose = np.asarray(network.demand_purpose)
        consuming = np.isin(demand_purpose, _CONSUMING_PURPOSES)
        self.used = _cell_scatter(
            cell_count,
            demand_cell[consuming],
            np.asarray(flows.used, dtype=np.float64)[consuming],
        )
        # second-economy input draws also leave the formal stock cells
        self.used = self.used + np.asarray(flows.second_input_used, dtype=np.float64)

        # realized imports land in the treasury import pool cells
        self.imports = np.zeros(cell_count, dtype=np.float64)
        for g, cell in enumerate(np.asarray(network.import_pool_cell).tolist()):
            if cell >= 0:
                self.imports[cell] += float(flows.imports[g])

        # household retail acquisition drains the org-owned retail cells
        self.retail_out = np.zeros(cell_count, dtype=np.float64)
        for r, g, cell in self._retail_cell_iter(network):
            self.retail_out[cell] += float(flows.retail_sales[r, g])

        # plot household channels (quantities; food ready only)
        self.plot_self_use = np.zeros(regions, dtype=np.float64)
        self.plot_market_sales = np.zeros(regions, dtype=np.float64)
        food_index = commodity_ids.index("food") if "food" in commodity_ids else None
        if food_index is not None:
            ready_price = float(parameters.prices[food_index])
            if ready_price > 0.0:
                self.plot_self_use = _household_region_sums(
                    state, np.asarray(flows.household_self_use) / ready_price, regions
                )
                realized_food = _household_region_sums(
                    state, np.asarray(flows.household_realized)[:, food_index], regions
                )
                self.plot_market_sales = (
                    realized_food
                    - np.asarray(flows.retail_sales, dtype=np.float64)[:, food_index]
                    - self.plot_self_use
                )
        self.plot_out = np.zeros(cell_count, dtype=np.float64)
        ready_self = np.asarray(network.plot_ready_self_cell)
        ready_market = np.asarray(network.plot_ready_market_cell)
        for r in range(min(regions, ready_self.size)):
            if int(ready_self[r]) >= 0:
                self.plot_out[int(ready_self[r])] += self.plot_self_use[r]
        for r in range(min(regions, ready_market.size)):
            if int(ready_market[r]) >= 0:
                self.plot_out[int(ready_market[r])] += self.plot_market_sales[r]

        # The runner-provided snapshot is authoritative; reconstruction remains
        # only for isolated output fixtures that do not carry a tick boundary.
        if opening_stock is None:
            self.opening = (
                self.closing
                - self.production
                - self.delivered_in
                - self.imports
                + self.delivered_out
                + self.used
                + self.retail_out
                + self.plot_out
            )
        else:
            opening_values = np.asarray(opening_stock, dtype=np.float64)
            if opening_values.shape != self.closing.shape:
                raise ResearchGateError(
                    f"opening stock shape {opening_values.shape} != closing stock shape "
                    f"{self.closing.shape}"
                )
            self.opening = opening_values

        # non-stockable commodities never carry persistent stock
        self.non_stockable = np.zeros(cell_count, dtype=bool)
        stockable = stockable_by_commodity(commodity_ids)
        for g in range(len(commodity_ids)):
            if not stockable[g]:
                self.non_stockable |= self.cell_commodity == g
        self.closing_view = np.where(self.non_stockable, 0.0, self.closing)
        self.opening = np.where(self.non_stockable, 0.0, self.opening)

        org = self.cell_owner_kind == _KIND_ORG
        self.mask_input = org & (self.cell_pool == 0)
        self.mask_output = org & (self.cell_pool == 1)
        self.mask_wholesale = org & (self.cell_pool == 2)
        self.mask_retail = org & (self.cell_pool == 3)
        self.mask_plot = self.cell_owner_kind == _KIND_PLOT
        self.mask_wip = self.cell_owner_kind == _KIND_PROJECT
        self.mask_import = self.cell_owner_kind == _KIND_TREASURY
        # everything (used for total stock grids)
        self.mask_all = np.ones(cell_count, dtype=bool)

    @staticmethod
    def _retail_cell_iter(network: Any) -> Iterator[tuple[int, int, int]]:
        retail_cells = np.asarray(network.retail_cell)
        if retail_cells.ndim != 2:
            return
        for r in range(retail_cells.shape[0]):
            for g in range(retail_cells.shape[1]):
                cell = int(retail_cells[r, g])
                if cell >= 0:
                    yield r, g, cell

    def grid(self, mask: np.ndarray, values: np.ndarray) -> np.ndarray:
        """Sum regional cells into an (R, G) grid; exclude national-owner rows."""
        selected = np.nonzero(mask & (self.cell_region >= 0))[0]
        out = np.zeros((self.regions, self.commodities), dtype=np.float64)
        if selected.size:
            out += np.bincount(
                self.cell_region[selected] * self.commodities + self.cell_commodity[selected],
                weights=values[selected],
                minlength=self.regions * self.commodities,
            ).reshape(self.regions, self.commodities)
        return out

    def national_grid(self, mask: np.ndarray, values: np.ndarray) -> np.ndarray:
        """Like :meth:`grid` but national-owner cells also count (G,)."""
        selected = np.nonzero(mask)[0]
        out = np.zeros(self.commodities, dtype=np.float64)
        if selected.size:
            out += np.bincount(
                self.cell_commodity[selected],
                weights=values[selected],
                minlength=self.commodities,
            )
        return out


def append_material_rows(
    history: MaterialHistory,
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    network: Any,
    *,
    region_ids: list[str],
    commodity_ids: list[str],
    digest: str,
    invariant_summary: dict[str, Any],
    opening_stock: np.ndarray | None = None,
) -> None:
    """Append one admitted tick's compact rows to the history buffers."""
    regions = len(region_ids)
    commodities = len(commodity_ids)
    tick = int(flows.tick)
    quarter = str(flows.quarter)
    ledger = _CellLedger(
        state,
        flows,
        network,
        parameters,
        commodity_ids,
        regions,
        commodities,
        opening_stock=opening_stock,
    )

    expired_leftover = invariant_summary.get("expired_leftover_by_cell")
    if expired_leftover is None:
        raise ResearchGateError(
            "invariant_summary lacks the kernel's per-cell expiry sink "
            "(expired_leftover_by_cell); the publisher never re-derives expiry from a "
            "lighter ledger, which misses non-stockable opening stock and clips"
        )
    expired_leftover = np.asarray(expired_leftover, dtype=np.float64)
    if expired_leftover.shape != (ledger.cell_count,):
        raise ResearchGateError(
            f"kernel expiry sink shape {expired_leftover.shape} != "
            f"({ledger.cell_count},) closing cells"
        )

    _append_aggregate_rows(
        history, state, flows, network, ledger, tick, quarter, region_ids, commodity_ids
    )
    _append_stage_rows(history, ledger, tick, quarter, region_ids, commodity_ids)
    _append_national_rows(
        history, state, flows, ledger, tick, quarter, commodity_ids, expired_leftover
    )
    _append_budget_rows(history, state, flows, tick, quarter, region_ids)
    _append_organization_rows(history, state, flows, network, ledger, tick, quarter, region_ids)
    _append_financial_rows(history, state, flows, tick, quarter, invariant_summary)
    _append_department_rows(
        history, state, flows, parameters, network, tick, quarter, invariant_summary
    )
    _append_diagnostic_rows(history, flows, digest, invariant_summary, tick, quarter)


def _append_aggregate_rows(
    history: MaterialHistory,
    state: MaterialState,
    flows: MaterialTickFlows,
    network: Any,
    ledger: _CellLedger,
    tick: int,
    quarter: str,
    region_ids: list[str],
    commodity_ids: list[str],
) -> None:
    regions = len(region_ids)
    commodities = len(commodity_ids)

    # demand-cell attribution: by destination cell region x commodity
    demand_cell = np.asarray(network.demand_cell)
    landed = demand_cell[demand_cell >= 0]  # national/boundary sinks excluded
    valid = landed[ledger.cell_region[landed] >= 0]
    dest_region = ledger.cell_region[valid]
    dest_commodity = ledger.cell_commodity[valid]
    demand_keys = dest_region * commodities + dest_commodity
    demand_values_index = np.nonzero(demand_cell >= 0)[0][ledger.cell_region[landed] >= 0]

    def demand_sums(values: np.ndarray) -> np.ndarray:
        out = np.zeros((regions, commodities), dtype=np.float64)
        if demand_keys.size:
            out += np.bincount(
                demand_keys,
                weights=np.asarray(values, dtype=np.float64)[demand_values_index],
                minlength=regions * commodities,
            ).reshape(regions, commodities)
        return out

    columns: dict[str, np.ndarray] = {
        "desired": demand_sums(flows.desired),
        "ordered": demand_sums(flows.ordered),
        "ordered_gross": demand_sums(flows.ordered_gross),
        "unfunded": demand_sums(flows.unfunded_order),
        "allocated": demand_sums(flows.allocated),
        "delivered": demand_sums(flows.delivered),
        "used": demand_sums(flows.used),
        "financial_delivery_blocked": demand_sums(flows.financial_delivery_blocked),
        "physical_delivery_blocked": demand_sums(flows.physical_delivery_blocked),
        "production": ledger.grid(ledger.mask_all, ledger.production),
        "production_raw": ledger.grid(
            ledger.mask_all,
            np.where(ledger.cell_stage == STAGE_CODES["raw"], ledger.production, 0.0),
        ),
        "production_ready": ledger.grid(
            ledger.mask_all,
            np.where(ledger.cell_stage == STAGE_CODES["ready"], ledger.production, 0.0),
        ),
        "input_open": ledger.grid(ledger.mask_input, ledger.opening),
        "input_close": ledger.grid(ledger.mask_input, ledger.closing_view),
        "output_open": ledger.grid(ledger.mask_output, ledger.opening),
        "output_close": ledger.grid(ledger.mask_output, ledger.closing_view),
        "wholesale_open": ledger.grid(ledger.mask_wholesale, ledger.opening),
        "wholesale_close": ledger.grid(ledger.mask_wholesale, ledger.closing_view),
        "retail_open": ledger.grid(ledger.mask_retail, ledger.opening),
        "retail_close": ledger.grid(ledger.mask_retail, ledger.closing_view),
        "household_desired": _household_region_sums(state, flows.household_desired, regions),
        "household_budget_unmet": _household_region_sums(
            state, flows.household_budget_unmet, regions
        ),
        "household_availability_unmet": _household_region_sums(
            state, flows.household_availability_unmet, regions
        ),
    }
    food_index = commodity_ids.index("food") if "food" in commodity_ids else -1
    for region in range(regions):
        for commodity in range(commodities):
            row: dict[str, object] = {
                "tick": tick,
                "quarter": quarter,
                "region_id": region_ids[region],
                "commodity_id": commodity_ids[commodity],
            }
            for name, table in columns.items():
                row[name] = float(table[region, commodity])
            row["plot_self_use"] = (
                float(ledger.plot_self_use[region]) if commodity == food_index else 0.0
            )
            row["plot_market_sales"] = (
                float(ledger.plot_market_sales[region]) if commodity == food_index else 0.0
            )
            history.aggregate_rows.append(row)


def _append_stage_rows(
    history: MaterialHistory,
    ledger: _CellLedger,
    tick: int,
    quarter: str,
    region_ids: list[str],
    commodity_ids: list[str],
) -> None:
    regions = len(region_ids)
    commodities = len(commodity_ids)
    # slot: 0..R-1 regional, R = national owner (region_id null)
    slot = np.where(ledger.cell_region >= 0, ledger.cell_region, regions)
    key = (
        slot.astype(np.int64) * commodities * 10
        + ledger.cell_commodity.astype(np.int64) * 10
        + ledger.cell_stage.astype(np.int64)
    )
    grid_size = (regions + 1) * commodities * 10

    expiry = _ledger_expiry_by_cell(ledger, commodity_ids)
    views = {
        "opening": ledger.opening,
        "closing": ledger.closing_view,
        "receipts": ledger.delivered_in + ledger.imports,
        "production": ledger.production,
        "used": ledger.used,
        "delivered_out": ledger.delivered_out + ledger.retail_out + ledger.plot_out,
        "expiry": expiry,
    }
    residual = ledger.closing_view - (
        ledger.opening
        + views["receipts"]
        + ledger.production
        - views["used"]
        - views["delivered_out"]
        - expiry
    )

    def summed(values: np.ndarray) -> np.ndarray:
        if not ledger.cell_count:
            return np.zeros(grid_size, dtype=np.float64)
        return np.bincount(key, weights=values, minlength=grid_size)

    tables = {name: summed(values) for name, values in views.items()}
    residual_table = summed(residual)

    stage_combos = [
        (g, STAGE_CODES[stage])
        for g, commodity in enumerate(commodity_ids)
        for stage in legal_stages(commodity)
    ]
    labels: list[str | None] = [*region_ids, None]
    for slot_index, region_label in enumerate(labels):
        base = slot_index * commodities * 10
        for g, stage_code in stage_combos:
            index = base + g * 10 + stage_code
            history.stage_rows.append(
                {
                    "tick": tick,
                    "quarter": quarter,
                    "region_id": region_label,
                    "commodity_id": commodity_ids[g],
                    "stage": _STAGE_NAME_OF[stage_code],
                    **{name: float(table[index]) for name, table in tables.items()},
                    "residual": float(residual_table[index]),
                }
            )


def _ledger_expiry_by_cell(ledger: _CellLedger, commodity_ids: Sequence[str]) -> np.ndarray:
    """Ledger-consistent expiry for the stage/regional grid.

    This is a *reconstruction* from the lighter cell ledger: it cannot see the
    non-stockable opening boundary or the same-quarter pool terms, so it is
    within a few percent of (never above) the kernel sink and it keeps the stage
    residual identity self-consistent.  The exact kernel sink is published in
    ``national_accounts.expiry``, which is what the frozen expiry gate reads.
    """
    stockable = stockable_by_commodity(commodity_ids)
    is_service_cell = ~stockable[ledger.cell_commodity]
    return np.where(
        is_service_cell,
        ledger.opening
        + ledger.production
        + ledger.delivered_in
        + ledger.imports
        - ledger.used
        - ledger.delivered_out
        - ledger.retail_out
        - ledger.plot_out
        - ledger.closing_view,
        0.0,
    )


def _append_national_rows(
    history: MaterialHistory,
    state: MaterialState,
    flows: MaterialTickFlows,
    ledger: _CellLedger,
    tick: int,
    quarter: str,
    commodity_ids: list[str],
    expired_leftover: np.ndarray,
) -> None:
    commodities = len(commodity_ids)
    household_consumption = _household_region_sums(
        state, flows.household_realized, ledger.regions
    ).sum(axis=0)
    # Expiry per commodity is the kernel's own sink, aggregated.  The scalar
    # ``flows.expired_services`` is one number for the whole economy and must
    # never be broadcast across commodities.
    expiry = np.bincount(
        ledger.cell_commodity, weights=expired_leftover, minlength=commodities
    )
    residual = (
        np.asarray(flows.material_balance_residual, dtype=np.float64)
        if flows.material_balance_residual is not None
        else np.zeros(commodities)
    )
    tolerance = (
        np.asarray(flows.material_balance_tolerance, dtype=np.float64)
        if flows.material_balance_tolerance is not None
        else np.zeros(commodities)
    )
    production_all = ledger.national_grid(ledger.mask_all, ledger.production)
    columns: dict[str, np.ndarray] = {
        "cmea_imports": np.asarray(flows.cmea_imports, dtype=np.float64),
        "convertible_imports": np.asarray(flows.convertible_imports, dtype=np.float64),
        "imports": np.asarray(flows.imports, dtype=np.float64),
        "cmea_exports": np.asarray(flows.cmea_exports, dtype=np.float64),
        "convertible_exports": np.asarray(flows.convertible_exports, dtype=np.float64),
        "exports": np.asarray(flows.cmea_exports, dtype=np.float64)
        + np.asarray(flows.convertible_exports, dtype=np.float64),
        "production": production_all,
        "production_raw": ledger.national_grid(
            ledger.mask_all,
            np.where(ledger.cell_stage == STAGE_CODES["raw"], ledger.production, 0.0),
        ),
        "production_ready": ledger.national_grid(
            ledger.mask_all,
            np.where(ledger.cell_stage == STAGE_CODES["ready"], ledger.production, 0.0),
        ),
        "used": ledger.national_grid(ledger.mask_all, ledger.used),
        "household_consumption": household_consumption,
        "expiry": expiry,
        "organization_input_open": ledger.national_grid(ledger.mask_input, ledger.opening),
        "organization_input_close": ledger.national_grid(ledger.mask_input, ledger.closing_view),
        "organization_output_open": ledger.national_grid(ledger.mask_output, ledger.opening),
        "organization_output_close": ledger.national_grid(ledger.mask_output, ledger.closing_view),
        "wholesale_open": ledger.national_grid(ledger.mask_wholesale, ledger.opening),
        "wholesale_close": ledger.national_grid(ledger.mask_wholesale, ledger.closing_view),
        "retail_open": ledger.national_grid(ledger.mask_retail, ledger.opening),
        "retail_close": ledger.national_grid(ledger.mask_retail, ledger.closing_view),
        "plot_open": ledger.national_grid(ledger.mask_plot, ledger.opening),
        "plot_close": ledger.national_grid(ledger.mask_plot, ledger.closing_view),
        "project_wip_open": ledger.national_grid(ledger.mask_wip, ledger.opening),
        "project_wip_close": ledger.national_grid(ledger.mask_wip, ledger.closing_view),
        "import_pool_open": ledger.national_grid(ledger.mask_import, ledger.opening),
        "import_pool_close": ledger.national_grid(ledger.mask_import, ledger.closing_view),
        "total_stock_open": ledger.national_grid(ledger.mask_all, ledger.opening),
        "total_stock_close": ledger.national_grid(ledger.mask_all, ledger.closing_view),
    }
    for g in range(commodities):
        row: dict[str, object] = {
            "tick": tick,
            "quarter": quarter,
            "commodity_id": commodity_ids[g],
        }
        for name, table in columns.items():
            row[name] = float(table[g])
        value = float(residual[g])
        row["material_balance_residual"] = value
        allowed = float(tolerance[g])
        row["material_balance_tolerance_ratio"] = abs(value) / allowed if allowed > 0 else 0.0
        history.national_rows.append(row)


def _append_budget_rows(
    history: MaterialHistory,
    state: MaterialState,
    flows: MaterialTickFlows,
    tick: int,
    quarter: str,
    region_ids: list[str],
) -> None:
    regions = len(region_ids)
    columns = {
        "cash_open": _household_region_sums(state, flows.household_cash_open, regions),
        "cash_close": _household_region_sums(state, flows.household_cash_close, regions),
        "pre_purchase_wages": _household_region_sums(state, flows.household_wage_income, regions),
        "plot_income_formal": _household_region_sums(
            state, flows.household_plot_income_formal, regions
        ),
        "plot_income_direct": _household_region_sums(
            state, flows.household_plot_income_direct, regions
        ),
        "late_wage_payment": _household_region_sums(state, flows.household_late_wage, regions),
        "spending": _household_region_sums(state, flows.household_spending, regions),
        "self_use_imputed": _household_region_sums(state, flows.household_self_use, regions),
        "plot_input_funding": _household_region_sums(
            state, flows.household_plot_input_funding, regions
        ),
        "budget_available": _household_region_sums(
            state, flows.household_budget_available, regions
        ),
        "voluntary_saving": _household_region_sums(
            state, flows.household_voluntary_saving, regions
        ),
        "forced_saving": _household_region_sums(state, flows.household_forced_saving, regions),
        "deferred_close": _household_region_sums(
            state,
            np.asarray(flows.household_plot_income_direct, dtype=np.float64)
            + np.asarray(flows.household_late_wage, dtype=np.float64),
            regions,
        ),
    }
    previous: dict[str, dict[str, Any]] = {}
    for row in history.budget_rows:
        if row["tick"] == tick - 1:
            previous[str(row["region_id"])] = row
    for region in range(regions):
        prior = previous.get(region_ids[region])
        deferred_open = (
            float(prior["deferred_close"]) if prior is not None else 0.0
        )  # initial state opens with zero deferred receipts
        history.budget_rows.append(
            {
                "tick": tick,
                "quarter": quarter,
                "region_id": region_ids[region],
                **{
                    name: float(table[region])
                    for name, table in columns.items()
                    if name != "deferred_close"
                },
                "deferred_open": deferred_open,
                "deferred_close": float(columns["deferred_close"][region]),
            }
        )


def _append_organization_rows(
    history: MaterialHistory,
    state: MaterialState,
    flows: MaterialTickFlows,
    network: Any,
    ledger: _CellLedger,
    tick: int,
    quarter: str,
    region_ids: list[str],
) -> None:
    regions = len(region_ids)
    types = len(ORGANIZATION_TYPE_ORDER)
    org_count = int(state.organization_id.shape[0])
    keys = state.organization_region.astype(np.int64) * types + state.organization_type

    def org_sums(values: np.ndarray) -> np.ndarray:
        out = np.zeros(regions * types, dtype=np.float64)
        if org_count:
            out += np.bincount(
                keys, weights=np.asarray(values, dtype=np.float64), minlength=regions * types
            )
        return out

    counts = org_sums(np.ones(org_count))
    columns = {
        "capacity_sum": org_sums(state.organization_capacity),
        "labor_sum": org_sums(state.organization_labor_available),
        "target_sum": org_sums(flows.organization_target),
        "realized_sum": org_sums(flows.organization_realized),
        "credit_requested": org_sums(flows.organization_credit_requested),
        "credit_approved": org_sums(flows.organization_credit_approved),
        "credit_drawn": org_sums(flows.organization_credit_drawn),
        "investment_requested": org_sums(flows.organization_investment_requested),
        "investment_approved": org_sums(flows.organization_investment_approved),
        "investment_completed": org_sums(flows.organization_investment_completed),
        "bailout_requested": org_sums(flows.organization_bailout_requested),
        "bailout_granted": org_sums(flows.organization_bailout_granted),
        "principal_sum": org_sums(state.organization_principal),
        "wage_arrears_sum": org_sums(state.organization_wage_arrears),
        "interest_arrears_sum": org_sums(state.organization_interest_arrears),
        "cash_sum": org_sums(state.organization_cash),
        "shortage_expectation_sum": org_sums(state.organization_shortage_expectation),
        "bailout_expectation_sum": org_sums(state.organization_bailout_expectation),
    }

    # demand-cell quantities attributed to the owning organization
    ordered = np.zeros(org_count, dtype=np.float64)
    delivered = np.zeros(org_count, dtype=np.float64)
    id_to_row = {
        int(canonical): row for row, canonical in enumerate(state.organization_id.tolist())
    }
    demand_cell = np.asarray(network.demand_cell)
    landed = demand_cell[demand_cell >= 0]
    landed_positions = np.nonzero(demand_cell >= 0)[0]
    owned = landed_positions[ledger.cell_owner_kind[landed] == _KIND_ORG]
    owner_rows = np.array(
        [id_to_row.get(int(owner), -1) for owner in ledger.cell_owner_id[landed]],
        dtype=np.int64,
    )
    keep_mask = ledger.cell_owner_kind[landed] == _KIND_ORG
    rows_keep = owner_rows[keep_mask]
    if rows_keep.size:
        np.add.at(
            ordered,
            rows_keep,
            np.asarray(flows.ordered, dtype=np.float64)[owned],
        )
        np.add.at(
            delivered,
            rows_keep,
            np.asarray(flows.delivered, dtype=np.float64)[owned],
        )
    ordered_grid = org_sums(ordered)
    delivered_grid = org_sums(delivered)

    for region in range(regions):
        for type_index, type_id in enumerate(ORGANIZATION_TYPE_IDS):
            index = region * types + type_index
            count = int(counts[index])
            bottleneck = (
                float(delivered_grid[index] / ordered_grid[index])
                if ordered_grid[index] > 0
                else None
            )
            history.organization_rows.append(
                {
                    "tick": tick,
                    "quarter": quarter,
                    "region_id": region_ids[region],
                    "organization_type": type_id,
                    "organization_count": count,
                    "capacity_sum": float(columns["capacity_sum"][index]),
                    "capacity_mean": _mean(float(columns["capacity_sum"][index]), count),
                    "labor_sum": float(columns["labor_sum"][index]),
                    "labor_mean": _mean(float(columns["labor_sum"][index]), count),
                    "target_sum": float(columns["target_sum"][index]),
                    "realized_sum": float(columns["realized_sum"][index]),
                    "ordered_sum": float(ordered_grid[index]),
                    "delivered_sum": float(delivered_grid[index]),
                    "input_bottleneck_share": bottleneck,
                    "credit_requested": float(columns["credit_requested"][index]),
                    "credit_approved": float(columns["credit_approved"][index]),
                    "credit_drawn": float(columns["credit_drawn"][index]),
                    "investment_requested": float(columns["investment_requested"][index]),
                    "investment_approved": float(columns["investment_approved"][index]),
                    "investment_completed": float(columns["investment_completed"][index]),
                    "bailout_requested": float(columns["bailout_requested"][index]),
                    "bailout_granted": float(columns["bailout_granted"][index]),
                    "principal_sum": float(columns["principal_sum"][index]),
                    "wage_arrears_sum": float(columns["wage_arrears_sum"][index]),
                    "interest_arrears_sum": float(columns["interest_arrears_sum"][index]),
                    "cash_sum": float(columns["cash_sum"][index]),
                    "shortage_expectation_mean": _mean(
                        float(columns["shortage_expectation_sum"][index]), count
                    ),
                    "bailout_expectation_mean": _mean(
                        float(columns["bailout_expectation_sum"][index]), count
                    ),
                }
            )


def _append_financial_rows(
    history: MaterialHistory,
    state: MaterialState,
    flows: MaterialTickFlows,
    tick: int,
    quarter: str,
    invariant_summary: dict[str, Any],
) -> None:
    from hsm_lab.engine.finance import (
        CMEA_CURRENCY,
        DOMESTIC_CURRENCY,
        USD_CURRENCY,
        AccountKind,
        bank_account_ids,
        foreign_account_id,
        treasury_account_id,
    )

    bank_count = int(state.bank_reserves.shape[0])
    nonbank = state.organization_bank >= 0
    bank_index = state.organization_bank[nonbank]

    def by_bank(values: np.ndarray) -> np.ndarray:
        out = np.zeros(bank_count, dtype=np.float64)
        if bank_index.size:
            out += np.bincount(
                bank_index,
                weights=np.asarray(values, dtype=np.float64)[nonbank],
                minlength=bank_count,
            )
        return out

    drawn = by_bank(flows.organization_credit_drawn)
    repaid = by_bank(flows.organization_principal_paid)
    accrued = by_bank(flows.organization_interest_due)
    interest_paid = by_bank(flows.organization_interest_paid)
    loan_open = np.asarray(state.bank_loan_asset, dtype=np.float64) - drawn + repaid
    residual = (
        np.asarray(state.bank_loan_asset, dtype=np.float64)
        + np.asarray(state.bank_interest_receivable, dtype=np.float64)
        + np.asarray(state.bank_reserves, dtype=np.float64)
        - np.asarray(state.bank_deposit_liability, dtype=np.float64)
        - np.asarray(state.bank_equity, dtype=np.float64)
    )
    loan_ids = bank_account_ids(state, AccountKind.LOAN_ASSET)
    for bank in range(bank_count):
        history.financial_rows.append(
            {
                "tick": tick,
                "quarter": quarter,
                "account_id": int(loan_ids[bank]),
                "currency": DOMESTIC_CURRENCY,
                "account_label": f"bank_{bank}_loan_asset",
                "opening": float(loan_open[bank]),
                "closing": float(state.bank_loan_asset[bank]),
                "credit_drawn": float(drawn[bank]),
                "grant": 0.0,
                "interest_accrued": float(accrued[bank]),
                "interest_paid": float(interest_paid[bank]),
                "principal_repaid": float(repaid[bank]),
                "residual": float(residual[bank]),
            }
        )

    grant_total = float(np.sum(np.asarray(flows.organization_bailout_granted)))
    treasury_open: float | None = None
    runner_open = invariant_summary.get("treasury_deposit_open")
    if isinstance(runner_open, (int, float)) and not isinstance(runner_open, bool):
        treasury_open = float(runner_open)
    else:
        for row in reversed(history.financial_rows):
            if row["tick"] == tick - 1 and row["account_label"] == "treasury_cash":
                treasury_open = float(cast("float", row["closing"]))
                break
    history.financial_rows.append(
        {
            "tick": tick,
            "quarter": quarter,
            "account_id": int(treasury_account_id(state, AccountKind.CASH_DEPOSIT)),
            "currency": DOMESTIC_CURRENCY,
            "account_label": "treasury_cash",
            "opening": treasury_open,
            "closing": float(state.treasury_deposit),
            "credit_drawn": 0.0,
            "grant": grant_total,
            "interest_accrued": 0.0,
            "interest_paid": 0.0,
            "principal_repaid": 0.0,
            "residual": None,
        }
    )

    usd_open = (
        float(state.usd_reserve)
        - float(flows.usd_export_receipt)
        + float(flows.usd_import_payment)
        + float(flows.usd_interest_paid)
        + float(flows.usd_principal_paid)
        - float(flows.usd_loan_drawn)
    )
    usd_residual = (
        usd_open
        + float(flows.usd_export_receipt)
        - float(flows.usd_import_payment)
        - float(flows.usd_interest_paid)
        - float(flows.usd_principal_paid)
        + float(flows.usd_loan_drawn)
        - float(state.usd_reserve)
    )
    history.financial_rows.append(
        {
            "tick": tick,
            "quarter": quarter,
            "account_id": int(foreign_account_id(state, USD_CURRENCY)),
            "currency": USD_CURRENCY,
            "account_label": "foreign_usd_reserve",
            "opening": usd_open,
            "closing": float(state.usd_reserve),
            "credit_drawn": float(flows.usd_loan_drawn),
            "grant": 0.0,
            "interest_accrued": float(flows.usd_interest_accrued),
            "interest_paid": float(flows.usd_interest_paid),
            "principal_repaid": float(flows.usd_principal_paid),
            "residual": usd_residual,
        }
    )
    cmea_open = (
        float(state.cmea_settlement_balance)
        - float(flows.cmea_export_receipt)
        + float(flows.cmea_import_payment)
    )
    history.financial_rows.append(
        {
            "tick": tick,
            "quarter": quarter,
            "account_id": int(foreign_account_id(state, CMEA_CURRENCY)),
            "currency": CMEA_CURRENCY,
            "account_label": "foreign_cmea_settlement",
            "opening": cmea_open,
            "closing": float(state.cmea_settlement_balance),
            "credit_drawn": 0.0,
            "grant": 0.0,
            "interest_accrued": 0.0,
            "interest_paid": 0.0,
            "principal_repaid": 0.0,
            "residual": (
                cmea_open
                + float(flows.cmea_export_receipt)
                - float(flows.cmea_import_payment)
                - float(state.cmea_settlement_balance)
            ),
        }
    )


def _append_department_rows(
    history: MaterialHistory,
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    network: Any,
    tick: int,
    quarter: str,
    invariant_summary: dict[str, Any],
) -> None:
    from hsm_lab.engine.accounting import derive_departments

    housing = invariant_summary.get("housing_completed")
    if not isinstance(housing, (int, float)) or isinstance(housing, bool):
        raise ResearchGateError(
            "append_material_rows requires invariant_summary['housing_completed'] "
            "(dwelling units completed at the tick boundary) for department "
            "attribution; the runner must pass the opening-boundary value"
        )
    prices = build_material_prices(parameters)
    summary = derive_departments(
        flows,
        prices,
        network,
        state=state,
        housing_completed=float(housing),
    )
    use = summary.use_value
    attributed = summary.attributed_output_value
    for department in DEPARTMENT_ROWS:
        history.department_rows.append(
            {
                "tick": tick,
                "quarter": quarter,
                "department": department,
                "actual_use_value": float(use.get(department, 0.0)),
                "attributed_output_value": float(attributed.get(department, 0.0)),
                "service_use_productive": (
                    float(summary.service_use_productive) if department == "services" else 0.0
                ),
                "service_use_household": (
                    float(summary.service_use_household) if department == "services" else 0.0
                ),
            }
        )


def _append_diagnostic_rows(
    history: MaterialHistory,
    flows: MaterialTickFlows,
    digest: str,
    invariant_summary: dict[str, Any],
    tick: int,
    quarter: str,
) -> None:
    ordered = np.asarray(flows.ordered, dtype=np.float64)
    delivered = np.asarray(flows.delivered, dtype=np.float64)
    bottleneck = int(np.count_nonzero((ordered > 0.0) & (delivered <= 0.0)))
    blocked_total = float(np.sum(np.asarray(flows.financial_delivery_blocked, dtype=np.float64)))
    missing = [
        name
        for name in (
            "max_material_abs_residual",
            "max_material_tolerance_ratio",
            "max_finance_abs_residual",
            "max_finance_tolerance_ratio",
            "checked_cells",
        )
        if name not in invariant_summary
    ]
    if missing:
        raise ResearchGateError(
            f"append_material_rows requires invariant summary fields {missing}; "
            "the runner must pass the full check_material_invariants summary"
        )
    scalars = {
        name: float(invariant_summary[name])
        for name in (
            "max_material_abs_residual",
            "max_material_tolerance_ratio",
            "max_finance_abs_residual",
            "max_finance_tolerance_ratio",
            "checked_cells",
        )
    }
    segment = str(invariant_summary.get("forcing_segment", ""))
    row = {
        "tick": tick,
        "quarter": quarter,
        "digest": digest,
        "bottleneck_demand_count": bottleneck,
        "financial_blocked_total": blocked_total,
        "forcing_segment": segment,
        "expired_services": float(flows.expired_services),
        **scalars,
    }
    history.diagnostic_rows.append(row)
    details = _jsonable(
        {
            "digest": digest,
            "bottleneck_demand_count": bottleneck,
            "financial_blocked_total": blocked_total,
            "forcing_segment": segment,
            "expired_services": float(flows.expired_services),
            **{name: value for name, value in invariant_summary.items() if name != "per_ledger"},
        }
    )
    history.event_rows.append(
        {
            "tick": tick,
            "quarter": quarter,
            "event_type": MATERIAL_TICK_EVENT,
            "details_json": canonical_json(details).decode("utf-8"),
        }
    )


_COLUMN_DTYPES: dict[str, dict[str, type[pl.DataType]]] = {
    "aggregates": {"tick": pl.Int64},
    "stage_balances": {"tick": pl.Int64},
    "national_accounts": {"tick": pl.Int64},
    "household_budgets": {"tick": pl.Int64},
    "organization_diagnostics": {"tick": pl.Int64, "organization_count": pl.Int64},
    "financial_accounts": {"tick": pl.Int64, "account_id": pl.Int64},
    "departments": {"tick": pl.Int64},
    "tick_diagnostics": {
        "tick": pl.Int64,
        "checked_cells": pl.Int64,
        "bottleneck_demand_count": pl.Int64,
    },
    "events": {"tick": pl.Int64},
    POLITICAL_QUARTERS: {"tick": pl.Int64},
    OPPOSITION_REGIONS: {"tick": pl.Int64},
    INFORMATION_QUARTERS: {"tick": pl.Int64, "total_lag": pl.Int64, "source_quarter": pl.Int64},
    POLICY_DECISIONS: {"tick": pl.Int64},
    POLITICAL_EVENTS: {"tick": pl.Int64},
}

_STRING_COLUMNS: dict[str, set[str]] = {
    "aggregates": {"quarter", "region_id", "commodity_id"},
    "stage_balances": {"quarter", "region_id", "commodity_id", "stage"},
    "national_accounts": {"quarter", "commodity_id"},
    "household_budgets": {"quarter", "region_id"},
    "organization_diagnostics": {"quarter", "region_id", "organization_type"},
    "financial_accounts": {"quarter", "currency", "account_label"},
    "departments": {"quarter", "department"},
    "tick_diagnostics": {"quarter", "digest", "forcing_segment"},
    "events": {"quarter", "event_type", "details_json"},
    **POLITICAL_STRING_COLUMNS,
}

_COLUMNS_OF = {
    "aggregates": AGGREGATE_COLUMNS,
    "stage_balances": STAGE_COLUMNS,
    "national_accounts": NATIONAL_COLUMNS,
    "household_budgets": BUDGET_COLUMNS,
    "organization_diagnostics": ORGANIZATION_COLUMNS,
    "financial_accounts": FINANCIAL_COLUMNS,
    "departments": DEPARTMENT_COLUMNS,
    "tick_diagnostics": DIAGNOSTIC_COLUMNS,
    "events": EVENT_COLUMNS,
    POLITICAL_QUARTERS: POLITICAL_QUARTER_COLUMNS,
    OPPOSITION_REGIONS: OPPOSITION_COLUMNS,
    INFORMATION_QUARTERS: INFORMATION_COLUMNS,
    POLICY_DECISIONS: POLICY_DECISION_COLUMNS,
    POLITICAL_EVENTS: POLITICAL_EVENT_COLUMNS,
}


def _jsonable(value: Any) -> Any:
    """Convert numpy scalars/arrays to plain JSON types (canonical_json input)."""
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def _cast_frame(rows: list[dict[str, object]], table: str) -> pl.DataFrame:
    columns = _COLUMNS_OF[table]
    casts: dict[str, type[pl.DataType]] = {}
    for column in columns:
        if column in _COLUMN_DTYPES[table]:
            casts[column] = _COLUMN_DTYPES[table][column]
        elif column in _STRING_COLUMNS[table]:
            casts[column] = pl.String
        else:
            casts[column] = pl.Float64
    schema = pl.Schema(casts)
    if not rows:
        return pl.DataFrame({column: [] for column in columns}).cast(schema)
    frame = pl.DataFrame(rows)
    return frame.select(columns).cast(schema)


def history_frames(history: MaterialHistory) -> dict[str, pl.DataFrame]:
    """Build the nine compact frames from the accumulated history rows."""
    return {
        "aggregates": _cast_frame(history.aggregate_rows, "aggregates"),
        "stage_balances": _cast_frame(history.stage_rows, "stage_balances"),
        "national_accounts": _cast_frame(history.national_rows, "national_accounts"),
        "household_budgets": _cast_frame(history.budget_rows, "household_budgets"),
        "organization_diagnostics": _cast_frame(
            history.organization_rows, "organization_diagnostics"
        ),
        "financial_accounts": _cast_frame(history.financial_rows, "financial_accounts"),
        "departments": _cast_frame(history.department_rows, "departments"),
        "tick_diagnostics": _cast_frame(history.diagnostic_rows, "tick_diagnostics"),
        "events": _cast_frame(history.event_rows, "events"),
        POLITICAL_QUARTERS: _cast_frame(history.political_quarter_rows, POLITICAL_QUARTERS),
        OPPOSITION_REGIONS: _cast_frame(history.opposition_rows, OPPOSITION_REGIONS),
        INFORMATION_QUARTERS: _cast_frame(history.information_rows, INFORMATION_QUARTERS),
        POLICY_DECISIONS: _cast_frame(history.policy_decision_rows, POLICY_DECISIONS),
        POLITICAL_EVENTS: _cast_frame(history.political_event_rows, POLITICAL_EVENTS),
    }


def write_material_tables(output_dir: Path, frames: dict[str, pl.DataFrame]) -> dict[str, Path]:
    """Write all compact Parquet files and the DuckDB trajectory file."""
    paths: dict[str, Path] = {}
    for name in TABLES:
        path = output_dir / f"{name}.parquet"
        frames[name].write_parquet(path)
        paths[name] = path
    write_duckdb(output_dir, frames)
    return paths
