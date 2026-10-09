"""Material tick kernel and end-to-end runner (P02 plan sections 3-5).

``tick_material`` executes the pinned quarter sequence:

1. targets — farm/plot seasonality, labor caps, ``A @ target`` desires;
2. transport-first services production from OPENING fuel with the
   ``service_split`` logistics/productive/household reservation (the only
   same-tick production exception);
3. orders — hoarding/overorder toggles, trader collection intents from
   current-quarter targets and static household baskets, plot inputs,
   investment hunger and housing requests — cleared against the closed-ledger
   domestic finance step with purpose-priority cash scaling (wages first
   inside the finance step, then inputs incl. freight, old project, new
   project; proportional within each purpose);
4. external trade pre-pass — USD debt service on the opening principal,
   channel-separated imports landing in the treasury import-pool cells, and
   export claims scaled to Treasury-payable domestic cash;
5. two-round tiered allocation over opening seller/wholesale/retail/import
   stocks plus same-tick imports and transport services
   (``production_first`` / ``investment_first``);
6. single-pass delivery gated by transport service, wholesale outgoing /
   retail incoming handling work, buyer cash and one round of gross
   cross-bank prefunding; cash-blocked quantities land in
   ``financial_delivery_blocked`` and never double-count as material
   shortage;
7. production from opening + delivered inputs, investment installation and
   housing completion (dwellings only — never consumption or durables);
8. the household step — self-use plot food first, formal retail with the
   weighted budget/availability rationing, direct plot market through
   per-region ephemeral clearing, durable stock, late receipts credited
   after rationing;
9. shortage/bailout expectation updates, services expiry and the external
   closing settlement (export receipts book on the closing accounts);
10. ``MaterialTickFlows`` assembly with every pinned field.

The runner's manifest lifecycle is bound to fresh output directories, atomic
fail-closed output, and outer per-tick quarter / forcing / opening-closing
checks; ``completed_ticks`` advances only after ``check_material_invariants``
passes.

Numeric discipline: no per-organization or per-edge Python loops (segmented
``bincount``/scatter sums; bank pairing loops stay at B <= 2; the fixed
8-commodity and 3-purpose tier loops are allowed); every quantity stays
finite; per tick the kernel asserts ``delivered <= allocated <= ordered``
and per-cell non-negativity before returning.
"""

from __future__ import annotations

import hashlib
import json
import struct
import time
from dataclasses import dataclass, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

import numpy as np

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.guards import BASELINE_FILENAME, verify_baseline
from hsm_lab.contract.material import (
    COMMODITY_INDEX,
    ORGANIZATION_TYPE_ORDER,
    PURPOSE_CODES,
    RETAIL_HANDLING_TOTAL,
    WHOLESALE_HANDLING_TOTAL,
    CommoditySpec,
    MaterialParameters,
    PrivatePlotRecipe,
    RoutePurpose,
    commodity_spec,
    get_catalog,
)
from hsm_lab.contract.schemas import (
    Quarter,
    ResearchContract,
    ResearchGateError,
    ScenarioSpec,
)
from hsm_lab.engine import finance
from hsm_lab.engine.finance import (
    DOMESTIC_CURRENCY,
    household_account_ids,
    organization_account_ids,
    plot_clearing_account_ids,
    treasury_account_id,
)
from hsm_lab.engine.household_allocation import allocate_household_baskets
from hsm_lab.engine.household_stocks import (
    allocate_housing,
    durable_desire,
    housing_gap,
    private_construction_installation,
    update_durable_stocks,
)
from hsm_lab.engine.household_welfare import (
    account_household_welfare,
    update_household_expectations,
)
from hsm_lab.engine.households import form_household_demand
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.network import (
    MaterialNetwork,
    build_material_network,
    produce_leontief,
)
from hsm_lab.engine.rng import RNG_SCHEME_VERSION, RngRegistry
from hsm_lab.engine.second_economy import (
    plan_household_time,
    second_expiry,
    settle_second_economy,
)
from hsm_lab.engine.state import (
    MATERIAL_STATE_VERSION,
    N_D,
    N_E,
    N_Q,
    MaterialForcing,
    MaterialHistory,
    MaterialState,
    MaterialStockSnapshot,
    MaterialTickFlows,
    build_material_prices,
    capture_material_stocks,
    initialize_material,
)
from hsm_lab.engine.trade import (
    build_export_demands,
    realize_external_debt_service,
    realize_imports,
    settle_exports_and_closing,
)
from hsm_lab.provenance.manifest import (
    RunManifest,
    canonical_digest,
    canonical_json,
    compute_lock_hash,
    compute_parameter_hash,
    compute_scenario_hash,
    finalize_manifest,
    hash_output_tree,
    manifest_preamble,
    p05_manifest_fields,
    write_manifest_atomic,
)
from hsm_lab.storage.output import write_summary

if TYPE_CHECKING:  # pragma: no cover - annotation-only; avoids an import cycle
    from hsm_lab.data.registry import DataRegistry

MATERIAL_ENGINE_VERSION = "material-engine-v4"
MATERIAL_RUN_KIND: Literal["material_household_simulation"] = "material_household_simulation"
MATERIAL_RESEARCH_WARNING = "material_synthetic_fixture_not_historical_fit"

_ATOL = 1e-9
_STOCK_DUST = 1e-9

_ORG_TYPES = {t.value: i for i, t in enumerate(ORGANIZATION_TYPE_ORDER)}
_CODE_COOP = _ORG_TYPES["agricultural_cooperative"]
_CODE_STATE_FARM = _ORG_TYPES["state_farm"]
_CODE_TRANSPORT = _ORG_TYPES["transport"]
_CODE_WHOLESALE = _ORG_TYPES["wholesale_procurement"]
_CODE_RETAIL = _ORG_TYPES["retail"]

_PURPOSE_INTERMEDIATE = PURPOSE_CODES[RoutePurpose.INTERMEDIATE]
_PURPOSE_INVESTMENT = PURPOSE_CODES[RoutePurpose.INVESTMENT]
_PURPOSE_HOUSING = PURPOSE_CODES[RoutePurpose.HOUSING]
_PURPOSE_PROCUREMENT = PURPOSE_CODES[RoutePurpose.PROCUREMENT]
_PURPOSE_RETAIL = PURPOSE_CODES[RoutePurpose.RETAIL]
_PURPOSE_PRIVATE_PLOT = PURPOSE_CODES[RoutePurpose.PRIVATE_PLOT]
_PURPOSE_EXPORT_CMEA = PURPOSE_CODES[RoutePurpose.EXPORT_CMEA]
_PURPOSE_EXPORT_CONVERTIBLE = PURPOSE_CODES[RoutePurpose.EXPORT_CONVERTIBLE]
_PURPOSE_HOUSEHOLD = PURPOSE_CODES[RoutePurpose.HOUSEHOLD]

_TIERS_PRODUCTION_FIRST: tuple[tuple[int, ...], ...] = (
    (_PURPOSE_INTERMEDIATE, _PURPOSE_PRIVATE_PLOT),
    (_PURPOSE_INVESTMENT, _PURPOSE_HOUSING),
    (_PURPOSE_PROCUREMENT, _PURPOSE_RETAIL, _PURPOSE_EXPORT_CMEA, _PURPOSE_EXPORT_CONVERTIBLE),
)
_TIERS_INVESTMENT_FIRST: tuple[tuple[int, ...], ...] = (
    (_PURPOSE_INVESTMENT, _PURPOSE_HOUSING),
    (_PURPOSE_INTERMEDIATE, _PURPOSE_PRIVATE_PLOT),
    (_PURPOSE_PROCUREMENT, _PURPOSE_RETAIL, _PURPOSE_EXPORT_CMEA, _PURPOSE_EXPORT_CONVERTIBLE),
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _finite(name: str, *arrays: np.ndarray) -> None:
    for array in arrays:
        _require(bool(np.all(np.isfinite(array))), f"{name} carries non-finite values")


def _leontief_activity_cap(network: Any, final_demand: np.ndarray) -> np.ndarray:
    """Per-activity gross-output ceiling from (I - M) x = d (P05 §0.6).

    ``M[h, g]`` is the aggregate input of commodity ``h`` per unit of gross
    output of commodity ``g``; ``x_g`` is the gross output that satisfies the
    declared final demand ``d``.  The ceiling is distributed across the
    producers of each commodity in proportion to capacity, so the producers of
    one commodity can never together exceed its requirement.
    """
    commodity_count = int(final_demand.shape[0])
    activity_count = int(np.asarray(network.activity_capacity).shape[0])
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    out_g = np.full(activity_count, -1, dtype=np.int64)
    seen = np.zeros(activity_count, dtype=bool)
    B = network.B.tocoo()
    for r, c in zip(B.row.tolist(), B.col.tolist(), strict=True):
        if not seen[r]:
            seen[r] = True
            out_g[r] = int(cell_commodity[c])
    A = network.A.tocoo()
    input_cell = np.asarray(network.input_cell, dtype=np.int64)
    use = np.zeros((activity_count, commodity_count), dtype=np.float64)
    np.add.at(use, (A.row, cell_commodity[input_cell[A.col]]), A.data)
    # Producers of one commodity share its gross output, so the aggregate
    # coefficient per unit of commodity output is the *capacity-weighted
    # average* of the per-activity coefficients (summing would multiply it by
    # the number of producers).
    capacity = np.asarray(network.activity_capacity, dtype=np.float64)
    valid0 = out_g >= 0
    total0 = np.zeros(commodity_count, dtype=np.float64)
    np.add.at(total0, out_g[valid0], capacity[valid0])
    weight = np.zeros(activity_count, dtype=np.float64)
    weight[valid0] = capacity[valid0] / np.maximum(total0[out_g[valid0]], 1e-12)
    matrix = np.zeros((commodity_count, commodity_count), dtype=np.float64)
    for h in range(commodity_count):
        np.add.at(matrix[h], out_g[valid0], use[valid0, h] * weight[valid0])
    try:
        gross = np.linalg.solve(np.eye(commodity_count) - matrix, np.maximum(final_demand, 0.0))
    except np.linalg.LinAlgError:
        return np.full(activity_count, np.inf, dtype=np.float64)
    gross = np.maximum(gross, 0.0)
    cap = np.full(activity_count, np.inf, dtype=np.float64)
    cap[valid0] = gross[out_g[valid0]] * weight[valid0]
    return cap


def _group_factor(need: np.ndarray, capacity: np.ndarray) -> np.ndarray:
    """``min(1, capacity / need)``; zero-need groups pass untouched."""
    safe = np.where(need > 0.0, need, 1.0)
    return np.where(need > 0.0, np.minimum(1.0, np.maximum(capacity, 0.0) / safe), 1.0)


def _projected_closing_order(
    opening: np.ndarray,
    scheduled_use: np.ndarray,
    next_pipeline_use: np.ndarray,
    *,
    hoarding_quarters: float,
    overorder_strength: float,
    lagged_shortage: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Unified projected-closing net-order rule (P05 §0.1).

    Only the opening stock *not* consumed this quarter offsets next quarter's
    pipeline cover, so a destination that is short today orders the full
    replacement need rather than ``max(desired - opening, 0)``.  Returns
    ``(gross_order, projected_use)`` with the elementwise transaction above.
    """
    usable_open = np.maximum(opening, 0.0)
    planned = np.maximum(scheduled_use, 0.0)
    projected_use = np.minimum(usable_open, planned)
    projected_remaining = np.maximum(usable_open - projected_use, 0.0)
    closing_target = np.maximum(next_pipeline_use, 0.0) * (1.0 + float(hoarding_quarters))
    baseline_order = np.maximum(closing_target - projected_remaining, 0.0)
    gross = baseline_order * (1.0 + float(overorder_strength) * np.maximum(lagged_shortage, 0.0))
    return gross, projected_use


def _append_leg_transactions(
    flows: MaterialTickFlows,
    *,
    kind: str,
    debit: np.ndarray,
    credit: np.ndarray,
    amount: np.ndarray,
    groups: np.ndarray,
    org_column: list[Any] | None = None,
) -> None:
    """Bulk-append self-balancing legs, numbered per ``groups`` transaction.

    Every leg carries ``(debit account, credit account, amount)`` and is
    balanced by construction (the landed finance journal convention); legs of
    one transaction are contiguous with ``leg_index`` restarting at 0.
    """
    amount = np.asarray(amount, dtype=np.float64)
    count = int(amount.shape[0])
    if count == 0:
        return
    _require(
        bool(np.all(np.isfinite(amount))) and bool(np.all(amount > 0.0)),
        f"{kind} legs must be finite and strictly positive",
    )
    debit = np.asarray(debit, dtype=np.int64)
    credit = np.asarray(credit, dtype=np.int64)
    groups = np.asarray(groups, dtype=np.int64)
    _require(
        debit.shape[0] == count and credit.shape[0] == count and groups.shape[0] == count,
        f"{kind} leg columns must align",
    )
    order = np.argsort(groups, kind="stable")
    groups_sorted = groups[order]
    boundaries = np.flatnonzero(np.diff(groups_sorted)) + 1
    starts = np.concatenate(([0], boundaries)).astype(np.int64)
    leg_index = np.arange(count, dtype=np.int64) - np.repeat(
        starts, np.diff(np.concatenate((starts, [count])))
    )
    org_sorted: list[Any] = [None] * count
    if org_column is not None:
        _require(len(org_column) == count, "org column must align with legs")
        org_sorted = [org_column[position] for position in order.tolist()]
    finance._append_legs(
        flows,
        kind=kind,
        currency=DOMESTIC_CURRENCY,
        debit=debit[order],
        credit=credit[order],
        amount=amount[order],
        organization_ids=org_sorted,
        leg_offset=0,
    )
    flows.journal_leg[-count:] = leg_index.tolist()


# ---------------------------------------------------------------------------
# Per-network tick index (derived once, cached by network identity).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _TickIndex:
    """Read-only derived arrays shared by every tick of one network."""

    k_coefficient: np.ndarray  # (K,) A.data aligned to the k axis
    cell_owner_org: np.ndarray  # (S,) org row for org cells else -1
    demand_buyer: np.ndarray  # (D,) buyer org row else -1
    demand_freight_units: np.ndarray  # (D,) sum(weight * transport_per_unit)
    b_rows: np.ndarray  # (nnz,) activity of each B entry
    b_cells: np.ndarray  # (nnz,) stock cell of each B entry
    b_coefficient: np.ndarray  # (nnz,)
    household_edges: np.ndarray  # (Eh,) edges with purpose household
    household_edge_region: np.ndarray  # (Eh,)
    household_edge_commodity: np.ndarray  # (Eh,)
    household_demand_region: np.ndarray  # (D,) region of household demands
    household_demand_commodity: np.ndarray  # (D,)
    housing_demand: np.ndarray  # (R,) demand index per region (rank order)
    plot_input_demand_region: np.ndarray  # (D,) region for plot demands else -1
    org_input_mask: np.ndarray  # (D,) org-bought goods purposes
    tier_masks: dict[str, np.ndarray]


_INDEX_CACHE: dict[int, tuple[MaterialNetwork, _TickIndex]] = {}


def _tick_index(network: MaterialNetwork) -> _TickIndex:
    cached = _INDEX_CACHE.get(id(network))
    if cached is not None and cached[0] is network:
        return cached[1]
    index = _build_tick_index(network)
    _INDEX_CACHE[id(network)] = (network, index)
    return index


def _build_tick_index(network: MaterialNetwork) -> _TickIndex:
    k_count = int(network.input_cell.shape[0])
    d_count = int(network.demand_cell.shape[0])

    k_coefficient = np.zeros(k_count, dtype=np.float64)
    k_coefficient[np.asarray(network.A.indices, dtype=np.int64)] = np.asarray(
        network.A.data, dtype=np.float64
    )

    cell_owner_org = np.where(
        np.asarray(network.cell_owner_kind) == 0,
        np.asarray(network.cell_owner_id, dtype=np.int64),
        -1,
    ).astype(np.int64, copy=False)

    edge_demand = np.asarray(network.edge_demand, dtype=np.int64)
    demand_buyer = np.full(d_count, -1, dtype=np.int64)
    demand_buyer[edge_demand] = np.asarray(network.edge_buyer_org, dtype=np.int64)
    activity_org = np.asarray(network.activity_org_index, dtype=np.int64)
    demand_buyer[:k_count] = activity_org[np.asarray(network.input_activity, dtype=np.int64)]

    edge_weight = np.asarray(network.edge_weight, dtype=np.float64)
    edge_per_unit = np.asarray(network.edge_transport_per_unit, dtype=np.float64)
    freight = np.bincount(edge_demand, weights=edge_weight * edge_per_unit, minlength=d_count)

    indptr = np.asarray(network.B.indptr)
    b_rows = np.repeat(np.arange(indptr.size - 1, dtype=np.int64), np.diff(indptr))
    b_cells = np.asarray(network.B.indices, dtype=np.int64)
    b_coefficient = np.asarray(network.B.data, dtype=np.float64)

    edge_purpose = np.asarray(network.edge_purpose, dtype=np.int64)
    edge_source = np.asarray(network.edge_source_cell, dtype=np.int64)
    household_edges = np.flatnonzero(edge_purpose == _PURPOSE_HOUSEHOLD)
    household_edge_region = np.asarray(network.cell_region, dtype=np.int64)[
        edge_source[household_edges]
    ]
    household_edge_commodity = np.asarray(network.edge_commodity, dtype=np.int64)[household_edges]

    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    household_goods = [
        g for g, spec in enumerate(_commodity_specs(network)) if spec.household_channel
    ]
    household_demand_region = np.full(d_count, -1, dtype=np.int64)
    household_demand_commodity = np.full(d_count, -1, dtype=np.int64)
    household_demand_idx = np.flatnonzero(demand_purpose == _PURPOSE_HOUSEHOLD)
    if household_demand_idx.size:
        household_demand_region[household_demand_idx] = np.arange(
            household_demand_idx.size, dtype=np.int64
        ) // max(len(household_goods), 1)
        household_demand_commodity[household_demand_idx] = np.tile(
            np.asarray(household_goods, dtype=np.int64),
            max(household_demand_idx.size // max(len(household_goods), 1), 1),
        )[: household_demand_idx.size]

    housing_demand = np.flatnonzero(demand_purpose == _PURPOSE_HOUSING).astype(np.int64)

    plot_region = np.full(d_count, -1, dtype=np.int64)
    plot_demand = np.flatnonzero(demand_purpose[:k_count] == _PURPOSE_PRIVATE_PLOT)
    if plot_demand.size:
        plot_region[plot_demand] = np.asarray(network.cell_region, dtype=np.int64)[
            np.asarray(network.demand_cell, dtype=np.int64)[plot_demand]
        ]

    org_input_mask = np.isin(
        demand_purpose,
        (_PURPOSE_INTERMEDIATE, _PURPOSE_PROCUREMENT, _PURPOSE_RETAIL),
    ) & (demand_buyer >= 0)

    edge_fallback = np.asarray(network.edge_is_fallback, dtype=bool)
    tier_masks = {
        "production_first": np.stack(
            [
                np.isin(edge_purpose, purposes) & ~edge_fallback
                for purposes in _TIERS_PRODUCTION_FIRST
            ]
        ),
        "investment_first": np.stack(
            [
                np.isin(edge_purpose, purposes) & ~edge_fallback
                for purposes in _TIERS_INVESTMENT_FIRST
            ]
        ),
    }

    return _TickIndex(
        k_coefficient=k_coefficient,
        cell_owner_org=cell_owner_org,
        demand_buyer=demand_buyer,
        demand_freight_units=freight,
        b_rows=b_rows,
        b_cells=b_cells,
        b_coefficient=b_coefficient,
        household_edges=household_edges,
        household_edge_region=household_edge_region,
        household_edge_commodity=household_edge_commodity,
        household_demand_region=household_demand_region,
        household_demand_commodity=household_demand_commodity,
        housing_demand=housing_demand,
        plot_input_demand_region=plot_region,
        org_input_mask=org_input_mask,
        tier_masks=tier_masks,
    )


def _ephemeral_commodity_ids(network: MaterialNetwork) -> np.ndarray:
    """Commodity indices that are non-stockable, so their cells must close at 0."""
    return np.asarray(
        [g for g, spec in enumerate(_commodity_specs(network)) if not spec.stockable],
        dtype=np.int64,
    )


def _commodity_specs(network: MaterialNetwork) -> list[CommoditySpec]:
    """Declared CommoditySpec view aligned with the network commodity axis."""
    return [commodity_spec(cid) for cid in network.commodity_ids]


def _fixed_network_vector(values: list[float], network: MaterialNetwork) -> np.ndarray:
    """Map a catalog-indexed parameter vector onto the network commodity axis.

    Vectors are indexed by the scenario's frozen catalog axis (P05 §A), so the
    engine carries no hardcoded commodity count and reordering the declared
    axis never silently mixes parameters.
    """
    index = get_catalog(network.catalog_id).index
    if len(values) != len(index):
        raise ConfigError(
            f"parameter vector has {len(values)} entries but catalog "
            f"{network.catalog_id!r} has {len(index)} commodities"
        )
    mapped = np.zeros(len(network.commodity_ids), dtype=np.float64)
    for g, commodity_id in enumerate(network.commodity_ids):
        position = index.get(commodity_id)
        if position is not None:
            mapped[g] = float(values[position])
    return mapped


def _admin_price_vector(
    parameters: MaterialParameters, network: MaterialNetwork
) -> tuple[np.ndarray, int]:
    """(G,) standard admin prices and the services commodity index (-1 none)."""
    mapped = _fixed_network_vector(parameters.prices, network)
    catalog = get_catalog(network.catalog_id)
    service_ids = catalog.with_role("service")
    services_g = -1
    for commodity_id in service_ids:
        if commodity_id in network.commodity_ids:
            services_g = network.commodity_ids.index(commodity_id)
            break
    return mapped, services_g


def _cell_price_vector(parameters: MaterialParameters, network: MaterialNetwork) -> np.ndarray:
    """(S,) admin price per stock cell (raw-food cells at ``food_raw_price``)."""
    price_view = build_material_prices(parameters)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_price = price_view.standard[cell_commodity].astype(np.float64, copy=True)
    cell_stage = np.asarray(network.cell_stage, dtype=np.int64)
    catalog = get_catalog(network.catalog_id)
    for commodity_id in catalog.with_role("food_raw"):
        if commodity_id not in network.commodity_ids:
            continue
        net_g = network.commodity_ids.index(commodity_id)
        raw_cells = (cell_commodity == net_g) & (cell_stage == 1)
        cell_price[raw_cells] = price_view.food_raw
    return cell_price


def _handling_capacity(state: MaterialState) -> np.ndarray:
    """Trader handling work per tick (wholesale/retail totals split evenly)."""
    org_type = np.asarray(state.organization_type, dtype=np.int64)
    capacity = np.zeros(org_type.size, dtype=np.float64)
    wholesale = org_type == _CODE_WHOLESALE
    retail = org_type == _CODE_RETAIL
    if wholesale.any():
        capacity[wholesale] = WHOLESALE_HANDLING_TOTAL / float(np.count_nonzero(wholesale))
    if retail.any():
        capacity[retail] = RETAIL_HANDLING_TOTAL / float(np.count_nonzero(retail))
    return capacity


# ---------------------------------------------------------------------------
# Tick kernel
# ---------------------------------------------------------------------------


def tick_material(
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: MaterialParameters,
    network: MaterialNetwork,
    *,
    phase_times: dict[str, float] | None = None,
    controls: Any = None,
) -> MaterialTickFlows:
    """Advance the material economy by one admitted quarter (plan section 3).

    The caller (runner) captures the opening snapshot and runs the invariant
    gate; this function advances every mutable array to the closing boundary
    but deliberately leaves ``completed_ticks`` untouched so a rejected
    quarter never enters the admitted record.

    ``controls`` (a :class:`~hsm_lab.engine.policy.TickControls`, optional)
    carries the runtime household parameters/catalog and the central-vs-local
    planning mix; ``None`` reproduces the P02/P03 behaviour exactly (the
    runtime catalog/parameters then come from ``network``).
    """
    mark = time.perf_counter()

    def _phase(name: str) -> None:
        nonlocal mark
        if phase_times is not None:
            now = time.perf_counter()
            phase_times[name] = phase_times.get(name, 0.0) + (now - mark)
            mark = now

    tick = int(state.completed_ticks)
    quarters = list(forcing.quarters)
    _require(0 <= tick < len(quarters), f"tick {tick} lies outside the forcing horizon")
    quarter = str(quarters[tick])

    org_count = int(state.organization_id.shape[0])
    household_count = int(state.household_id.shape[0])
    region_count = int(state.dwelling_stock.shape[0])
    bank_count = int(state.bank_reserves.shape[0])
    g_count = len(network.commodity_ids)
    k_count = int(network.input_cell.shape[0])
    d_count = int(network.demand_cell.shape[0])
    m_count = int(network.edge_source_cell.shape[0])
    activity_count = int(network.activity_kind.shape[0])
    cell_count = int(network.cell_owner_kind.shape[0])

    index = _tick_index(network)
    price_net, services_g = _admin_price_vector(parameters, network)
    service_price = float(price_net[services_g]) if services_g >= 0 else 0.0
    cell_price = _cell_price_vector(parameters, network)
    hw_net = _fixed_network_vector(parameters.handling_work_per_unit, network)
    hw_net = np.where(hw_net > 0.0, hw_net, 1.0)
    _catalog = get_catalog(network.catalog_id)

    # P05 §0.5: the distribution layer (wholesale/retail) sells at the producer
    # price plus a margin that recovers its declared wage bill over its declared
    # handling work, so traders are not structurally loss-making.
    handling_capacity = _handling_capacity(state)
    org_type_arr = np.asarray(state.organization_type, dtype=np.int64)
    labor_arr = np.asarray(state.organization_labor_available, dtype=np.float64)
    wholesale_wage = float(parameters.wage_rate) * float(
        labor_arr[org_type_arr == _CODE_WHOLESALE].sum()
    )
    retail_wage = float(parameters.wage_rate) * float(labor_arr[org_type_arr == _CODE_RETAIL].sum())
    wholesale_work = float(handling_capacity[org_type_arr == _CODE_WHOLESALE].sum())
    retail_work = float(handling_capacity[org_type_arr == _CODE_RETAIL].sum())
    margin_w = wholesale_wage / wholesale_work if wholesale_work > 0.0 else 0.0
    margin_r = retail_wage / retail_work if retail_work > 0.0 else 0.0
    if not bool(getattr(parameters, "distribution_margins_enabled", False)):
        margin_w = 0.0
        margin_r = 0.0
    owner_org = index.cell_owner_org
    hub_cells = (owner_org >= 0) & (org_type_arr[np.maximum(owner_org, 0)] == _CODE_WHOLESALE)
    retail_cells_mask = (owner_org >= 0) & (org_type_arr[np.maximum(owner_org, 0)] == _CODE_RETAIL)
    cell_release_price = cell_price.copy()
    cell_release_price = np.where(hub_cells, cell_release_price + margin_w, cell_release_price)
    cell_release_price = np.where(
        retail_cells_mask, cell_release_price + margin_w + margin_r, cell_release_price
    )

    def _role_g(role: str) -> int:
        for commodity_id in _catalog.with_role(role):
            if commodity_id in network.commodity_ids:
                return network.commodity_ids.index(commodity_id)
        return -1

    capital_g = _role_g("capital")
    construction_g = _role_g("construction")

    flows = _new_flows(
        tick,
        quarter,
        org_count,
        household_count,
        region_count,
        g_count,
        activity_count,
        k_count,
        d_count,
        m_count,
        cell_count,
        len(network.household_catalog.household_good_ids),
    )

    household_parameters = (
        controls.household_parameters if controls is not None else network.household_parameters
    )
    catalog = controls.household_catalog if controls is not None else network.household_catalog

    # ---------------- opening boundary (frozen) --------------------------
    stock_open = np.asarray(state.stock_value, dtype=np.float64).copy()
    household_cash_open = np.asarray(state.household_cash, dtype=np.float64).copy()
    household_deferred_open = np.asarray(state.household_deferred_receipt, dtype=np.float64).copy()
    flows.household_cash_open = household_cash_open.copy()
    shortage_open = np.asarray(state.organization_shortage_expectation, dtype=np.float64).copy()
    approved_open = np.asarray(state.organization_project_approved, dtype=np.float64).copy()
    capital_wip_open = np.asarray(state.organization_capital_wip, dtype=np.float64).copy()
    construction_wip_open = np.asarray(state.organization_construction_wip, dtype=np.float64).copy()
    treasury_open = float(state.treasury_deposit)
    _finite("opening stock", stock_open)
    _require(bool(np.all(stock_open >= -_STOCK_DUST)), "opening stock must be non-negative")
    _require(
        bool(np.all(shortage_open >= 0.0) and np.all(shortage_open <= 1.0)),
        "opening shortage expectations must lie in [0, 1]",
    )
    state.stock_value = np.maximum(state.stock_value, 0.0)

    org_type = np.asarray(state.organization_type, dtype=np.int64)
    org_bank = np.asarray(state.organization_bank, dtype=np.int64)
    safe_org_bank = np.where(org_bank >= 0, org_bank, 0)
    hh_region = np.asarray(state.household_region, dtype=np.int64)
    hh_weight = np.asarray(state.household_weight, dtype=np.float64)
    hh_size = np.asarray(state.household_size, dtype=np.float64)
    hh_bank = hh_region % bank_count if bank_count else np.zeros(household_count, dtype=np.int64)
    region_persons = np.bincount(hh_region, weights=hh_weight * hh_size, minlength=region_count)

    # --- P03 household demand, frozen for the whole quarter (C1) -----------
    plan_household_time(state, household_parameters)
    desired_h = form_household_demand(state, household_parameters, catalog)
    durable_owned_open = np.asarray(state.household_durable_owned, dtype=np.float64)
    desired_durable = durable_desire(state, household_parameters)
    for column, channel in enumerate(catalog.durable_h_index):
        desired_h[:, int(channel)] += desired_durable[:, column]
    hazard = np.asarray(household_parameters.durables.retirement_hazard, dtype=np.float64)
    repair_want = (durable_owned_open * hazard).sum(
        axis=1
    ) * household_parameters.durables.repair_effectiveness
    desired_h[:, catalog.channel("repair")] = repair_want
    construction_want = np.minimum(
        housing_gap(state, household_parameters),
        household_parameters.housing.private_construction_intention_per_quarter,
    )
    desired_h[:, catalog.channel("construction")] = construction_want
    flows.household_desired_h = desired_h
    to_material = np.asarray(catalog.to_material, dtype=np.float64)
    parent_demand_region = np.zeros((region_count, g_count), dtype=np.float64)
    for h in range(to_material.shape[0]):
        channel_region = np.bincount(
            hh_region, weights=hh_weight * desired_h[:, h], minlength=region_count
        )
        parent_demand_region += channel_region[:, None] * to_material[h][None, :]
    _finite("household demand", desired_h)
    _require(bool(np.all(desired_h >= 0.0)), "household demand must be non-negative")

    activity_org = np.asarray(network.activity_org_index, dtype=np.int64)
    activity_region = np.asarray(network.activity_region, dtype=np.int64)
    activity_is_org = activity_org >= 0
    plot_rows = np.flatnonzero(np.asarray(network.activity_kind) == 1)
    farm_org = np.isin(org_type, (_CODE_COOP, _CODE_STATE_FARM))
    transport_org_mask = org_type == _CODE_TRANSPORT

    edge_demand = np.asarray(network.edge_demand, dtype=np.int64)
    edge_source = np.asarray(network.edge_source_cell, dtype=np.int64)
    edge_destination = np.asarray(network.edge_destination_cell, dtype=np.int64)
    edge_purpose = np.asarray(network.edge_purpose, dtype=np.int64)
    edge_weight = np.asarray(network.edge_weight, dtype=np.float64)
    edge_per_unit = np.asarray(network.edge_transport_per_unit, dtype=np.float64)
    edge_transport = np.asarray(network.edge_transport_org, dtype=np.int64)
    edge_commodity = np.asarray(network.edge_commodity, dtype=np.int64)
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    demand_share = np.asarray(network.demand_share, dtype=np.float64)
    input_activity = np.asarray(network.input_activity, dtype=np.int64)
    input_cell = np.asarray(network.input_cell, dtype=np.int64)
    cell_region = np.asarray(network.cell_region, dtype=np.int64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    has_dest = demand_cell >= 0
    # Exports/housing are valued at the producer price (no domestic retail
    # margin), so the treasury border continuity stays margin-free.
    border_purpose = np.isin(
        edge_purpose, (_PURPOSE_HOUSING, _PURPOSE_EXPORT_CMEA, _PURPOSE_EXPORT_CONVERTIBLE)
    )
    edge_unit_price = np.where(
        border_purpose, cell_price[edge_source], cell_release_price[edge_source]
    )

    demand_unit_cost = np.zeros(d_count, dtype=np.float64)
    demand_unit_cost[has_dest] = cell_price[demand_cell[has_dest]]
    demand_unit_cost += index.demand_freight_units * service_price

    # ---------------- step 1: targets ------------------------------------
    season = np.ones(activity_count, dtype=np.float64)
    season_factor = float(parameters.farm_seasonal_factors[tick % 4])
    act_farm = np.zeros(activity_count, dtype=bool)
    act_farm[activity_is_org] = farm_org[activity_org[activity_is_org]]
    season[act_farm] = season_factor
    season[plot_rows] = season_factor

    plot_recipe = PrivatePlotRecipe()
    labor_cap = np.zeros(activity_count, dtype=np.float64)
    capacity = np.asarray(network.activity_capacity, dtype=np.float64).copy()
    org_rows = activity_org[activity_is_org]
    capacity[activity_is_org] = np.asarray(state.organization_capacity, dtype=np.float64)[org_rows]
    labor_cap[activity_is_org] = (
        np.asarray(state.organization_labor_available, dtype=np.float64)[org_rows]
        / np.asarray(state.organization_labor_per_activity, dtype=np.float64)[org_rows]
    )
    if plot_rows.size:
        plot_regions = activity_region[plot_rows]
        capacity[plot_rows] = np.asarray(state.plot_capacity, dtype=np.float64)[plot_regions]
        labor_cap[plot_rows] = np.asarray(state.plot_labor_budget, dtype=np.float64)[
            plot_regions
        ] / float(plot_recipe.plot_labor_per_activity)
    local_target = np.maximum(
        np.minimum(float(parameters.utilization) * capacity * season, labor_cap),
        0.0,
    )
    if controls is not None and getattr(controls, "central_target", None) is not None:
        autonomy = float(np.clip(controls.autonomy, 0.0, 1.0))
        central = np.asarray(controls.central_target, dtype=np.float64)
        if central.shape != local_target.shape:
            raise ValueError("central planning target shape does not match the activity axis")
        target = np.maximum((1.0 - autonomy) * central + autonomy * local_target, 0.0)
        ceiling = np.maximum(np.minimum(capacity * season, labor_cap), 0.0)
        target = np.minimum(target, ceiling)
    else:
        target = local_target
    if bool(getattr(parameters, "demand_limited_targets", False)):
        # Cap each organization by last quarter's order signal for its output
        # commodity (never silently drop a cell that had demand).
        signal = np.asarray(state.organization_demand_signal, dtype=np.float64)
        act_org = np.asarray(network.activity_org_index, dtype=np.int64)
        has = act_org >= 0
        sig_act = np.zeros(activity_count, dtype=np.float64)
        sig_act[has] = signal[act_org[has]]
        cap = float(getattr(parameters, "demand_cover", 1.0)) * sig_act
        # A zero signal means the output cell had no takers: produce nothing.
        target = np.where(has, np.minimum(target, cap), target)
    if str(getattr(parameters, "production_target_rule", "legacy")) == "lean_plan":
        # MEASURED (P05 §10c): both variants of this rule collapse.  Capping every
        # activity to the national lean plan gives a 116-tick ratio of 0.000, and
        # capping only the non-stockable outputs gives 0.0008 even though expiry
        # falls from a 10 193 tail to 96.  The plan is a *national* static
        # feasibility solution with no routing, timing or finance, so the kernel
        # cannot realise it; it is kept as a gated, default-off lever alongside
        # leontief_upper_bound, and the next step is a time-expanded feasibility
        # problem rather than another target rule.
        #
        # Produce to the declared requirement instead of to capacity: an
        # activity-level feasibility problem (minimum gross output meeting the
        # declared household demand and the technology, with the physical opening
        # stock seeded) caps each activity.  Without this the kernel produces
        # min(u*C*season, labour) whatever demand says, so non-stockable
        # surpluses can only expire.
        from hsm_lab.calibration.alignment import build_alignment_problem, solve_alignment

        opening_by_commodity = np.bincount(
            cell_commodity,
            weights=np.asarray(stock_open, dtype=np.float64),
            minlength=g_count,
        )
        problem = build_alignment_problem(
            network,
            parameters=parameters,
            equivalent_persons=float(
                np.sum(np.asarray(state.household_weight) * np.asarray(state.household_size))
            ),
            opening_stock=opening_by_commodity,
        )
        lean = solve_alignment(problem, objective="min_output")
        if lean.get("status") == "LP_FEASIBLE":
            from hsm_lab.contract.material import commodity_spec

            lean_q = np.asarray(lean["activity"], dtype=np.float64)[:, tick % 4]
            # Only non-stockable output is capped: its surplus cannot be carried
            # and can only expire (the observed revenue loss).  Stockable goods
            # keep producing to capacity because the national lean plan carries no
            # routing or timing information, and capping them starves the delivery
            # chain (measured: production collapses to zero).
            act_org = np.asarray(network.activity_org_index, dtype=np.int64)
            org_out = np.asarray(network.org_output_cell, dtype=np.int64)
            ephemeral = np.zeros(activity_count, dtype=bool)
            valid = act_org >= 0
            cells = org_out[np.maximum(act_org, 0)]
            ok = valid & (cells >= 0)
            g_of_act = np.full(activity_count, -1, dtype=np.int64)
            g_of_act[ok] = cell_commodity[cells[ok]]
            for g, cid in enumerate(network.commodity_ids):
                if not commodity_spec(cid).stockable:
                    ephemeral |= g_of_act == g
            target = np.where(ephemeral, np.minimum(target, lean_q), target)
    elif str(getattr(parameters, "production_target_rule", "legacy")) == "leontief_upper_bound":
        # P05 §0.6: cap each commodity's gross output at the Leontief requirement
        # for declared final demand, damped toward the capacity rule and floored
        # above zero so the demand-driven cap cannot collapse the economy.
        cap_a = _leontief_activity_cap(network, parent_demand_region.sum(axis=0))
        damping = float(np.clip(float(parameters.leontief_damping), 0.0, 1.0))
        blended = (1.0 - damping) * target + damping * cap_a
        floored = np.maximum(blended, float(parameters.leontief_floor) * target)
        target = np.minimum(target, floored)
    flows.activity_target = target.copy()
    org_activity = np.asarray(state.organization_activity, dtype=np.int64)
    with_activity = org_activity >= 0
    flows.organization_target[with_activity] = target[org_activity[with_activity]]
    _phase("target")

    # ---------------- step 2: same-quarter services ----------------------
    # P05 §0.4: every activity the compiler scheduled early (produces a
    # non-stockable service from opening stock only) runs before the general
    # material pass.  For the legacy catalog this is exactly the transport
    # sector, so behaviour is unchanged.
    transport_acts = activity_is_org & transport_org_mask[activity_org]
    early_service_acts = np.asarray(network.activity_early_service, dtype=bool)
    kt_mask = early_service_acts[input_activity]
    transport_realized = np.zeros(activity_count, dtype=np.float64)
    transport_used_k = np.zeros(k_count, dtype=np.float64)
    logistics_pool = np.zeros(org_count, dtype=np.float64)
    produced_into = np.zeros(cell_count, dtype=np.float64)
    if kt_mask.any():
        # P05 §0.4: produce same-quarter services in dependency tiers, feeding
        # an earlier tier's non-stockable output to later tiers' inputs.
        input_timing_net = np.asarray(network.input_timing, dtype=np.int64)
        produced_service_by_commodity = np.zeros(g_count, dtype=np.float64)
        # Same-quarter service output that is consumed straight out of the
        # tick's production pool never reaches a cell: it must be netted out of
        # the production credit instead of being debited from the consumer's
        # input cell (which would drive that cell negative, P05 §0.4).
        same_quarter_consumed = np.zeros(g_count, dtype=np.float64)
        for tier in network.early_service_tiers:
            tier_mask = np.zeros(activity_count, dtype=bool)
            tier_mask[np.asarray(tier, dtype=np.int64)] = True
            tier_inputs = tier_mask[input_activity]
            if not tier_inputs.any():
                continue
            available = stock_open[input_cell[tier_inputs]].copy()
            same_quarter = input_timing_net[tier_inputs] == 1
            if same_quarter.any():
                g_in = cell_commodity[input_cell[tier_inputs]]
                available = available + np.where(
                    same_quarter, produced_service_by_commodity[g_in], 0.0
                )
            realized, used = produce_leontief(
                available,
                index.k_coefficient[tier_inputs],
                input_activity[tier_inputs],
                target,
            )
            transport_realized[tier_mask] = realized[tier_mask]
            transport_used_k[tier_inputs] = used
            if same_quarter.any():
                own_stock = np.minimum(used, stock_open[input_cell[tier_inputs]])
                drawn_from_pool = np.where(same_quarter, used - own_stock, 0.0)
                np.add.at(same_quarter_consumed, g_in, drawn_from_pool)
                np.add.at(flows.service_pool_draw_at_cell, input_cell[tier_inputs], drawn_from_pool)
                debit = np.where(same_quarter, own_stock, used)
            else:
                debit = used
            state.stock_value[input_cell[tier_inputs]] -= debit
            tier_b = tier_mask[index.b_rows]
            amounts = index.b_coefficient[tier_b] * realized[index.b_rows[tier_b]]
            produced_into += np.bincount(
                index.b_cells[tier_b], weights=amounts, minlength=cell_count
            )
            np.add.at(
                produced_service_by_commodity,
                cell_commodity[index.b_cells[tier_b]],
                amounts,
            )
        for g_index in np.flatnonzero(same_quarter_consumed):
            commodity_cells = np.flatnonzero(cell_commodity == g_index)
            produced_here = produced_into[commodity_cells]
            total_here = float(produced_here.sum())
            if total_here <= 0.0:
                continue
            take = min(float(same_quarter_consumed[g_index]), total_here)
            taken = produced_here * (take / total_here)
            produced_into[commodity_cells] -= taken
            np.add.at(flows.service_pool_credit_at_cell, commodity_cells, taken)
        state.stock_value += produced_into
        # Only transport carriers contribute to the logistics pool.
        logistics_pool += np.bincount(
            activity_org[transport_acts],
            weights=transport_realized[transport_acts],
            minlength=org_count,
        ) * float(parameters.service_split[0])
    flows.activity_realized[early_service_acts] = transport_realized[early_service_acts]
    _phase("transport")

    # ---------------- step 3: orders and finance -------------------------
    desired = np.zeros(d_count, dtype=np.float64)
    gross = np.zeros(d_count, dtype=np.float64)
    desired[:k_count] = index.k_coefficient * target[input_activity]
    inv_open = np.zeros(d_count, dtype=np.float64)
    inv_open[has_dest] = stock_open[demand_cell[has_dest]]

    hoarding = float(parameters.hoarding_quarters)
    strength = float(parameters.overorder_strength)
    k_buyer = activity_org[input_activity]
    org_k = k_buyer >= 0
    exp_k = np.zeros(k_count, dtype=np.float64)
    exp_k[org_k] = shortage_open[k_buyer[org_k]]
    # Agriculture draws down its pipeline at next quarter's declared seasonal
    # factor; every other activity keeps the current target as the next use.
    next_season = float(parameters.farm_seasonal_factors[(tick + 1) % 4])
    activity_season_ratio = np.ones(activity_count, dtype=np.float64)
    ratio = next_season / float(season_factor) if season_factor > 0.0 else 1.0
    activity_season_ratio[act_farm] = ratio
    activity_season_ratio[plot_rows] = ratio
    next_use_k = desired[:k_count] * activity_season_ratio[input_activity]
    gross_k, _ = _projected_closing_order(
        inv_open[:k_count],
        desired[:k_count],
        next_use_k,
        hoarding_quarters=hoarding,
        overorder_strength=strength,
        lagged_shortage=exp_k,
    )
    gross[:k_count] = gross_k

    retail_mask = demand_purpose == _PURPOSE_RETAIL
    if retail_mask.any():
        retail_dest = demand_cell[retail_mask]
        basket = parent_demand_region[cell_region[retail_dest], cell_commodity[retail_dest]]
        desired[retail_mask] = basket
        retail_zero = np.zeros(int(np.count_nonzero(retail_mask)), dtype=np.float64)
        gross[retail_mask] = _projected_closing_order(
            inv_open[retail_mask],
            basket,
            basket,
            hoarding_quarters=hoarding,
            overorder_strength=0.0,
            lagged_shortage=retail_zero,
        )[0]

    procurement_mask = demand_purpose == _PURPOSE_PROCUREMENT
    if procurement_mask.any():
        inflow_need = np.zeros(cell_count, dtype=np.float64)
        intermediate_edges = edge_purpose == _PURPOSE_INTERMEDIATE
        if intermediate_edges.any():
            inflow_need += np.bincount(
                edge_source[intermediate_edges],
                weights=desired[edge_demand[intermediate_edges]],
                minlength=cell_count,
            )
        retail_edges = edge_purpose == _PURPOSE_RETAIL
        if retail_edges.any():
            inflow_need += np.bincount(
                edge_source[retail_edges],
                weights=gross[edge_demand[retail_edges]],
                minlength=cell_count,
            )
        proc_dest = demand_cell[procurement_mask]
        proc_share = demand_share[procurement_mask]
        # One hub cell may carry several collection intents; aggregate their
        # capacity shares so the shared opening stock offsets the buffer once.
        need_by_cell = np.zeros(cell_count, dtype=np.float64)
        np.add.at(need_by_cell, proc_dest, proc_share * inflow_need[proc_dest])
        order_by_cell, _ = _projected_closing_order(
            stock_open,
            need_by_cell,
            need_by_cell,
            hoarding_quarters=hoarding,
            overorder_strength=0.0,
            lagged_shortage=np.zeros(cell_count, dtype=np.float64),
        )
        desired[procurement_mask] = proc_share * need_by_cell[proc_dest]
        gross[procurement_mask] = proc_share * order_by_cell[proc_dest]

    # Investment hunger (physical producers only) and housing requests.
    has_k_cells = (
        np.bincount(np.where(org_k, k_buyer, 0), weights=org_k.astype(float), minlength=org_count)
        > 0
    )
    hunger = (
        float(parameters.hunger_base)
        + float(parameters.hunger_bailout)
        * np.asarray(state.organization_bailout_expectation, dtype=np.float64)
        + float(parameters.hunger_shortage) * np.where(has_k_cells, shortage_open, 0.0)
        + float(getattr(parameters, "capital_depreciation_rate", 0.0))
    )
    new_request = np.where(
        with_activity,
        np.asarray(state.organization_capacity, dtype=np.float64) * hunger,
        0.0,
    )

    capital_unit = float(parameters.capacity_capital_goods_per_unit)
    construction_unit = float(parameters.capacity_construction_per_unit)
    old_required_capital = np.maximum(capital_unit * approved_open - capital_wip_open, 0.0)
    old_required_construction = np.maximum(
        construction_unit * approved_open - construction_wip_open, 0.0
    )
    if capital_g >= 0 and construction_g >= 0:
        old_project_cost = (
            old_required_capital * price_net[capital_g]
            + old_required_construction * price_net[construction_g]
        )
        unit_capacity_cost = (
            capital_unit * price_net[capital_g] + construction_unit * price_net[construction_g]
        )
    else:
        old_project_cost = np.zeros(org_count, dtype=np.float64)
        unit_capacity_cost = 0.0
    new_investment_request_cost = new_request * unit_capacity_cost

    org_input = index.org_input_mask
    input_order_cost = np.bincount(
        index.demand_buyer[org_input],
        weights=demand_unit_cost[org_input] * gross[org_input],
        minlength=org_count,
    )

    wage_bill_open = float(parameters.wage_rate) * np.asarray(
        state.organization_labor_available, dtype=np.float64
    )
    finance_result = finance.run_domestic_finance_step(
        state,
        flows,
        parameters,
        wage_bill_open=wage_bill_open,
        input_order_cost=input_order_cost,
        old_project_cost=old_project_cost,
        new_investment_request_cost=new_investment_request_cost,
        transaction_base=0,
    )
    cash_for_goods = np.asarray(finance_result["cash_available_for_goods"], dtype=np.float64).copy()
    _phase("finance")

    # Purpose-priority cash scaling: inputs (incl. freight) first, then the
    # old project, then the new project; proportional within each purpose.
    input_cost_by_org = input_order_cost
    funded_inputs = np.minimum(input_cost_by_org, cash_for_goods)
    scale_inputs = _group_factor(input_cost_by_org, cash_for_goods)
    cash_for_goods = cash_for_goods - funded_inputs
    # P05 §0.6: replacement investment is funded cash-first, its residual gap
    # drawn from the credit fund (a transfer between two deposit-type accounts,
    # so the money-coverage identity is untouched).
    dep_rate = float(getattr(parameters, "capital_depreciation_rate", 0.0))
    if dep_rate > 0.0:
        replacement_cost = new_request * unit_capacity_cost
        gap = np.maximum(replacement_cost - cash_for_goods, 0.0)
        if float(gap.sum()) > 0.0:
            scale = min(1.0, float(state.credit_fund) / float(gap.sum()))
            extra = gap * scale
            state.credit_fund = float(state.credit_fund) - float(extra.sum())
            state.organization_cash = np.asarray(state.organization_cash, dtype=np.float64) + extra
            cash_for_goods = cash_for_goods + extra
    investment = finance.plan_investment(
        state,
        parameters,
        delivered_capital_wip=np.zeros(org_count, dtype=np.float64),
        delivered_construction_wip=np.zeros(org_count, dtype=np.float64),
        investment_cash_budget=cash_for_goods,
        new_request=new_request,
    )

    ordered = gross.copy()
    ordered[org_input] = gross[org_input] * scale_inputs[index.demand_buyer[org_input]]

    # Plot input orders: household-funded, capacity-shared wage/deferred pool.
    participating = np.asarray(state.household_plot_participating, dtype=bool)
    represented_persons = np.bincount(
        hh_region[participating],
        weights=(hh_weight * hh_size)[participating],
        minlength=region_count,
    )
    safe_persons = np.where(represented_persons > 0.0, represented_persons, 1.0)
    plot_share = np.zeros(household_count, dtype=np.float64)
    plot_share[participating] = hh_size[participating] / safe_persons[hh_region[participating]]
    plot_demand_mask = np.zeros(d_count, dtype=bool)
    plot_demand_mask[:k_count] = demand_purpose[:k_count] == _PURPOSE_PRIVATE_PLOT
    plot_pool = np.zeros(region_count, dtype=np.float64)
    if plot_demand_mask.any():
        plot_region = index.plot_input_demand_region[plot_demand_mask]
        wages_received = np.asarray(flows.household_wage_income, dtype=np.float64)
        pool_hh = np.where(participating, wages_received + household_deferred_open, 0.0)
        plot_pool = np.bincount(hh_region, weights=pool_hh, minlength=region_count)
        plot_cost = np.bincount(
            plot_region,
            weights=demand_unit_cost[plot_demand_mask] * gross[plot_demand_mask],
            minlength=region_count,
        )
        plot_scale = _group_factor(plot_cost, plot_pool)
        ordered[plot_demand_mask] = gross[plot_demand_mask] * plot_scale[plot_region]

    investment_mask = demand_purpose == _PURPOSE_INVESTMENT
    if investment_mask.any():
        inv_dest = demand_cell[investment_mask]
        inv_owner = np.asarray(network.cell_owner_id, dtype=np.int64)[inv_dest]
        inv_goods = cell_commodity[inv_dest]
        is_capital = inv_goods == capital_g
        is_construction = inv_goods == construction_g
        quantities = np.where(
            is_capital,
            investment["funded_old_capital"][inv_owner]
            + investment["new_capital_orders"][inv_owner],
            np.where(
                is_construction,
                investment["funded_old_construction"][inv_owner]
                + investment["new_construction_orders"][inv_owner],
                0.0,
            ),
        )
        ordered[investment_mask] = quantities
        pre_funding = (
            old_required_capital[inv_owner] * is_capital
            + old_required_construction[inv_owner] * is_construction
            + new_request[inv_owner]
            * np.where(is_capital, capital_unit, np.where(is_construction, construction_unit, 0.0))
        )
        desired[investment_mask] = pre_funding
        gross[investment_mask] = pre_funding
    _phase("orders")

    # P05 §0.5: the freight price is derived from the carriers' declared wage
    # bill over the certified logistics work this quarter, not the admin
    # service price.  Without this the transport sector is structurally
    # insolvent: it pays wages for services the route graph never buys.
    edge_self_hauled_flag = np.asarray(network.edge_self_hauled, dtype=bool)
    non_self_haul = (~edge_self_hauled_flag) & (edge_transport >= 0)
    certified_work = float(
        np.sum(
            ordered[edge_demand[non_self_haul]]
            * edge_weight[non_self_haul]
            * edge_per_unit[non_self_haul]
        )
    )
    carrier_wage = float(parameters.wage_rate) * float(
        np.sum(np.asarray(state.organization_labor_available, dtype=np.float64)[transport_org_mask])
    )
    if certified_work > 1e-12:
        service_price = carrier_wage / certified_work

    # ---------------- step 4: trade pre-pass -----------------------------
    oil_price = float(forcing.oil_price[tick])
    global_rate = float(forcing.global_usd_rate[tick])
    cmea_quote = float(forcing.cmea_energy_price[tick])
    fx_quote = float(forcing.official_fx[tick])

    desired_usd_outlay = 0.0
    convertible_prices = np.asarray(parameters.trade.convertible_prices, dtype=np.float64)
    for g in range(g_count):
        fixed = COMMODITY_INDEX.get(network.commodity_ids[g])
        if fixed is None:
            continue
        unit = convertible_prices[fixed]
        if network.commodity_ids[g] == "energy":
            unit = unit * oil_price / float(parameters.world_oil_reference)
        desired_usd_outlay += float(parameters.trade.convertible_desired_imports[fixed]) * unit

    realize_external_debt_service(
        state,
        flows,
        parameters,
        global_rate_percent=global_rate,
        desired_usd_outlay=desired_usd_outlay,
        transaction_base=1,
    )
    realize_imports(
        state,
        flows,
        parameters,
        network,
        oil_price=oil_price,
        cmea_contract_price=cmea_quote,
        transaction_base=10,
    )
    import_into = np.zeros(cell_count, dtype=np.float64)
    import_cell = np.asarray(network.import_pool_cell, dtype=np.int64)
    has_import_cell = import_cell >= 0
    import_into[import_cell[has_import_cell]] = flows.imports[has_import_cell]

    # Treasury-payable scaling: housing first, exports from the remainder.
    housing_mask = demand_purpose == _PURPOSE_HOUSING
    region_gap = np.bincount(
        hh_region,
        weights=hh_weight * housing_gap(state, household_parameters),
        minlength=region_count,
    )
    housing_request = np.minimum(
        region_gap,
        household_parameters.housing.housing_construction_cap_per_person * region_persons,
    )
    if housing_mask.any() and construction_g >= 0:
        housing_unit_cost = (
            price_net[construction_g] + index.demand_freight_units[housing_mask] * service_price
        )
        housing_cost = float(np.dot(housing_request, housing_unit_cost))
        housing_scale = min(1.0, treasury_open / housing_cost) if housing_cost > 0.0 else 0.0
        treasury_after_housing = treasury_open - housing_cost * housing_scale
        desired[housing_mask] = housing_request
        gross[housing_mask] = housing_request
        ordered[housing_mask] = housing_request * housing_scale
    else:
        housing_cost = 0.0
        treasury_after_housing = treasury_open

    export_demand_cell = np.asarray(network.export_demand_cell, dtype=np.int64)
    export_freight = np.zeros((2, g_count), dtype=np.float64)
    for channel in (0, 1):
        for g in range(g_count):
            demand_index = int(export_demand_cell[channel, g])
            if demand_index >= 0:
                export_freight[channel, g] = (
                    index.demand_freight_units[demand_index] * service_price
                )
    export_desired, export_ordered = build_export_demands(
        parameters,
        network,
        treasury_payable=treasury_after_housing,
        admin_price=price_net,
        freight_per_unit=export_freight,
    )
    for channel in (0, 1):
        for g in range(g_count):
            demand_index = int(export_demand_cell[channel, g])
            if demand_index >= 0:
                desired[demand_index] = export_desired[channel, g]
                gross[demand_index] = export_desired[channel, g]
                ordered[demand_index] = export_ordered[channel, g]
    _phase("trade")

    unfunded = np.maximum(gross - ordered, 0.0)

    # ---------------- step 5: two-round tiered allocation ----------------
    avail = stock_open + import_into
    tier_stack = index.tier_masks[str(parameters.allocation_order)]
    edge_allocated = np.zeros(m_count, dtype=np.float64)
    for tier_index in range(tier_stack.shape[0]):
        tier_edges = tier_stack[tier_index]
        if not tier_edges.any():
            continue
        tier_avail = avail + produced_into * float(
            parameters.service_split[2 if tier_index == 2 else 1]
        )
        src = edge_source[tier_edges]
        demand_of_tier = edge_demand[tier_edges]
        claim1 = ordered[demand_of_tier] * edge_weight[tier_edges]
        need1 = np.bincount(src, weights=claim1, minlength=cell_count)
        factor1 = _group_factor(need1, tier_avail)
        alloc1 = claim1 * factor1[src]
        avail -= np.bincount(src, weights=alloc1, minlength=cell_count)
        got = np.bincount(demand_of_tier, weights=alloc1, minlength=d_count)
        unmet = np.maximum(ordered - got, 0.0)
        claim2 = unmet[demand_of_tier] * edge_weight[tier_edges]
        need2 = np.bincount(src, weights=claim2, minlength=cell_count)
        factor2 = _group_factor(need2, avail)
        alloc2 = claim2 * factor2[src]
        avail -= np.bincount(src, weights=alloc2, minlength=cell_count)
        edge_allocated[tier_edges] = alloc1 + alloc2
    # P05 §0.3 fallback round: unmet demand may draw from additional
    # same-commodity sources once the declared sources are exhausted.
    fallback_edges = np.asarray(network.edge_is_fallback, dtype=bool)
    if fallback_edges.any():
        allocated_so_far = np.bincount(edge_demand, weights=edge_allocated, minlength=d_count)
        unmet = np.maximum(ordered - allocated_so_far, 0.0)
        fb_src = edge_source[fallback_edges]
        fb_demand = edge_demand[fallback_edges]
        claim = unmet[fb_demand] * edge_weight[fallback_edges]
        need = np.bincount(fb_src, weights=claim, minlength=cell_count)
        factor = _group_factor(need, avail)
        alloc = claim * factor[fb_src]
        avail -= np.bincount(fb_src, weights=alloc, minlength=cell_count)
        edge_allocated[fallback_edges] = alloc
    allocated = np.bincount(edge_demand, weights=edge_allocated, minlength=d_count)
    _phase("allocation")

    # ---------------- step 6: delivery ------------------------------------
    active = edge_allocated > 0.0
    phys_factor = np.ones(m_count, dtype=np.float64)

    # P05 §0.2: self-hauled routes (a carrier's own inputs, non-stockable
    # service deliveries, and — for the legacy catalog — every unmetered
    # same-region leg) never claim the shared carrier service pool.
    edge_self_hauled = np.asarray(network.edge_self_hauled, dtype=bool)
    service_need = edge_allocated * edge_per_unit
    needs_transport = (~edge_self_hauled) & (edge_transport >= 0)
    if (needs_transport & active).any():
        transport_need = np.bincount(
            edge_transport[needs_transport],
            weights=service_need[needs_transport],
            minlength=org_count,
        )
        transport_factor_org = _group_factor(transport_need, logistics_pool)
        phys_factor = np.where(
            needs_transport,
            transport_factor_org[np.where(needs_transport, edge_transport, 0)],
            1.0,
        )

    handling_capacity = _handling_capacity(state)
    org_cells = index.cell_owner_org >= 0
    wholesale_cells = np.zeros(cell_count, dtype=bool)
    retail_cells = np.zeros(cell_count, dtype=bool)
    retail_owner = np.zeros(cell_count, dtype=np.int64)
    wholesale_cells[org_cells] = org_type[index.cell_owner_org[org_cells]] == _CODE_WHOLESALE
    retail_cells[org_cells] = org_type[index.cell_owner_org[org_cells]] == _CODE_RETAIL
    retail_owner[retail_cells] = index.cell_owner_org[retail_cells]

    source_wholesale = wholesale_cells[edge_source]
    if (source_wholesale & active).any():
        wholesale_edges = source_wholesale & active
        work = edge_allocated[wholesale_edges] * hw_net[edge_commodity[wholesale_edges]]
        wholesale_org = index.cell_owner_org[edge_source[wholesale_edges]]
        wholesale_need = np.bincount(wholesale_org, weights=work, minlength=org_count)
        wholesale_factor = _group_factor(wholesale_need, handling_capacity)
        phys_factor = np.minimum(
            phys_factor,
            np.where(
                source_wholesale,
                wholesale_factor[np.maximum(index.cell_owner_org[edge_source], 0)],
                1.0,
            ),
        )
    dest_retail = np.zeros(m_count, dtype=bool)
    valid_dest = edge_destination >= 0
    dest_retail[valid_dest] = retail_cells[edge_destination[valid_dest]]
    retail_work_used = np.zeros(org_count, dtype=np.float64)
    if (dest_retail & active).any():
        retail_edges = dest_retail & active
        work_dest = edge_allocated[retail_edges] * hw_net[edge_commodity[retail_edges]]
        retail_org = retail_owner[edge_destination[retail_edges]]
        retail_work_used = np.bincount(retail_org, weights=work_dest, minlength=org_count)
        retail_factor = _group_factor(retail_work_used, handling_capacity)
        safe_retail_org = np.maximum(retail_owner[np.maximum(edge_destination, 0)], 0)
        phys_factor = np.minimum(
            phys_factor,
            np.where(dest_retail, retail_factor[safe_retail_org], 1.0),
        )

    candidate = edge_allocated * phys_factor
    pay_goods = candidate * edge_unit_price
    pay_fee = candidate * edge_per_unit * service_price
    unit_pay = pay_goods + pay_fee

    fin_factor = np.ones(m_count, dtype=np.float64)
    buyer_org = index.demand_buyer[edge_demand]
    org_buyer = buyer_org >= 0
    if (org_buyer & active).any():
        org_need = np.bincount(
            buyer_org[org_buyer], weights=unit_pay[org_buyer], minlength=org_count
        )
        org_cash_factor = _group_factor(
            org_need, np.asarray(state.organization_cash, dtype=np.float64)
        )
        fin_factor = np.where(org_buyer, org_cash_factor[np.where(org_buyer, buyer_org, 0)], 1.0)
    plot_pool_remaining = plot_pool.copy()
    plot_buyer = (~org_buyer) & (edge_purpose == _PURPOSE_PRIVATE_PLOT)
    if (plot_buyer & active).any():
        plot_need = np.bincount(
            cell_region[edge_destination[plot_buyer]],
            weights=unit_pay[plot_buyer],
            minlength=region_count,
        )
        plot_factor = _group_factor(plot_need, plot_pool_remaining)
        fin_factor = np.minimum(
            fin_factor,
            np.where(
                plot_buyer,
                plot_factor[cell_region[np.where(plot_buyer, edge_destination, 0)]],
                1.0,
            ),
        )
    treasury_buyer = (~org_buyer) & np.isin(
        edge_purpose, (_PURPOSE_HOUSING, _PURPOSE_EXPORT_CMEA, _PURPOSE_EXPORT_CONVERTIBLE)
    )
    if (treasury_buyer & active).any():
        treasury_need = float(np.sum(unit_pay[treasury_buyer & active]))
        treasury_factor = (
            min(1.0, float(state.treasury_deposit) / treasury_need) if treasury_need > 0.0 else 1.0
        )
        fin_factor = np.minimum(fin_factor, np.where(treasury_buyer, treasury_factor, 1.0))

    seller_is_org = org_cells[edge_source]
    seller_kind_plot = cell_owner_kind[edge_source] == 1
    seller_bank = np.where(
        seller_is_org,
        safe_org_bank[index.cell_owner_org[edge_source]],
        np.where(seller_kind_plot, cell_region[edge_source] % max(bank_count, 1), 0),
    )
    buyer_bank = np.where(
        org_buyer,
        safe_org_bank[np.where(org_buyer, buyer_org, 0)],
        np.where(
            plot_buyer,
            cell_region[np.where(plot_buyer, edge_destination, 0)] % max(bank_count, 1),
            0,
        ),
    )
    cross_bank = buyer_bank != seller_bank
    if (cross_bank & active).any():
        outgoing = np.bincount(
            buyer_bank[cross_bank], weights=unit_pay[cross_bank], minlength=bank_count
        )
        bank_factor = _group_factor(outgoing, np.asarray(state.bank_reserves, dtype=np.float64))
        fin_factor = np.minimum(fin_factor, np.where(cross_bank, bank_factor[buyer_bank], 1.0))

    delivered_edges = candidate * fin_factor
    blocked_edges = candidate * (1.0 - fin_factor)
    # Buyers pay only for what is actually delivered: the cash/clearing factors
    # scale the goods and freight charges together with the delivery, so a
    # cash-limited buyer can never overdraw its deposit.
    pay_goods = delivered_edges * edge_unit_price
    pay_fee = delivered_edges * edge_per_unit * service_price
    unit_pay = pay_goods + pay_fee
    flows.edge_allocated = edge_allocated
    flows.edge_delivered = delivered_edges
    flows.edge_service_used = delivered_edges * edge_per_unit
    flows.edge_service_fee = delivered_edges * edge_per_unit * service_price
    flows.delivered = np.bincount(edge_demand, weights=delivered_edges, minlength=d_count)
    flows.financial_delivery_blocked = np.bincount(
        edge_demand, weights=blocked_edges, minlength=d_count
    )
    # Physical shortfall: allocated on an edge but not moved because the sourcing
    # wholesaler or the destination retailer is at its handling ceiling.  Without
    # this ledger the allocation-to-delivery gap is invisible (financial blocked is
    # zero while half the plan never moves).
    flows.physical_delivery_blocked = np.bincount(
        edge_demand,
        weights=np.maximum(edge_allocated - candidate, 0.0),
        minlength=d_count,
    )

    state.stock_value -= np.bincount(edge_source, weights=delivered_edges, minlength=cell_count)
    state.stock_value += np.bincount(
        edge_destination[valid_dest],
        weights=delivered_edges[valid_dest],
        minlength=cell_count,
    )
    logistics_pool -= np.bincount(
        edge_transport[needs_transport],
        weights=flows.edge_service_used[needs_transport],
        minlength=org_count,
    )

    # --- payments, bank books and journal legs ---------------------------
    org_cash = np.asarray(state.organization_cash, dtype=np.float64)
    household_cash = np.asarray(state.household_cash, dtype=np.float64)
    sales_receipts = np.zeros(org_count, dtype=np.float64)
    purchases = np.zeros(org_count, dtype=np.float64)
    org_cash_account = organization_account_ids(state, finance.AccountKind.CASH_DEPOSIT)
    household_cash_account = household_account_ids(state, finance.AccountKind.CASH_DEPOSIT)
    clearing_accounts = plot_clearing_account_ids(state)
    treasury_cash_account = treasury_account_id(state, finance.AccountKind.CASH_DEPOSIT)
    org_ids = np.asarray(state.organization_id, dtype=np.int64)
    bank_delta = np.zeros(bank_count, dtype=np.float64)
    seller_org = index.cell_owner_org[edge_source]
    seller_is_import = cell_owner_kind[edge_source] == 3

    leg_debit: list[np.ndarray] = []
    leg_credit: list[np.ndarray] = []
    leg_amount: list[np.ndarray] = []
    leg_group: list[np.ndarray] = []
    leg_org: list[list[Any]] = []

    def _legs(
        debit: int | np.ndarray,
        credit: int | np.ndarray,
        amount: np.ndarray,
        group: int | np.ndarray,
        org: np.ndarray | None,
    ) -> None:
        amount = np.asarray(amount, dtype=np.float64)
        debit = np.broadcast_to(np.asarray(debit, dtype=np.int64), amount.shape)
        credit = np.broadcast_to(np.asarray(credit, dtype=np.int64), amount.shape)
        group = np.broadcast_to(np.asarray(group, dtype=np.int64), amount.shape)
        mask = amount > 0.0
        if np.count_nonzero(mask):
            leg_debit.append(debit[mask])
            leg_credit.append(credit[mask])
            leg_amount.append(amount[mask])
            leg_group.append(group[mask])
            column: list[Any] = [None] * int(np.count_nonzero(mask))
            if org is not None:
                column = [
                    int(value) if value is not None and value >= 0 else None
                    for value in np.asarray(org, dtype=np.int64)[mask].tolist()
                ]
            leg_org.append(column)

    pay_active = active & (delivered_edges > 0.0)

    # Org buyers: goods payments + freight fees.
    org_paying = org_buyer & pay_active
    if org_paying.any():
        buyers = buyer_org
        pay = pay_goods
        fee = pay_fee
        transports = edge_transport
        paid_now = (pay + fee)[org_paying]
        org_cash -= np.bincount(buyers[org_paying], weights=paid_now, minlength=org_count)
        purchases += np.bincount(buyers[org_paying], weights=paid_now, minlength=org_count)
        bank_delta -= np.bincount(
            safe_org_bank[buyers[org_paying]], weights=paid_now, minlength=bank_count
        )

        to_org = org_paying & seller_is_org
        if to_org.any():
            rows = seller_org[to_org]
            paid = pay_goods[to_org]
            org_cash += np.bincount(rows, weights=paid, minlength=org_count)
            sales_receipts += np.bincount(rows, weights=paid, minlength=org_count)
            bank_delta += np.bincount(safe_org_bank[rows], weights=paid, minlength=bank_count)
            _legs(
                org_cash_account[buyers[to_org]],
                org_cash_account[rows],
                paid,
                1_000_000 + np.flatnonzero(to_org),
                org_ids[rows],
            )
        to_plot = org_paying & seller_kind_plot
        if to_plot.any():
            source_regions = cell_region[edge_source[to_plot]]
            region_receipts = np.bincount(
                source_regions, weights=pay_goods[to_plot], minlength=region_count
            )
            receipt_hh = plot_share * region_receipts[hh_region]
            household_cash += receipt_hh
            flows.household_plot_income_formal += receipt_hh
            represented_receipt = hh_weight * receipt_hh
            bank_delta += np.bincount(hh_bank, weights=represented_receipt, minlength=bank_count)
            paying_orgs = buyers[to_plot]
            _legs(
                org_cash_account[paying_orgs],
                clearing_accounts[source_regions],
                pay_goods[to_plot],
                source_regions,
                org_ids[paying_orgs],
            )
            receiving = represented_receipt > 0.0
            _legs(
                clearing_accounts[hh_region[receiving]],
                household_cash_account[receiving],
                represented_receipt[receiving],
                hh_region[receiving] + region_count,
                None,
            )
        to_import = org_paying & seller_is_import
        if to_import.any():
            paid = pay_goods[to_import]
            total = float(paid.sum())
            state.treasury_deposit = float(state.treasury_deposit) + total
            bank_delta[0] += total
            _legs(
                org_cash_account[buyers[to_import]],
                treasury_cash_account,
                paid,
                1_000_000 + np.flatnonzero(to_import),
                org_ids[buyers[to_import]],
            )
        has_fee = org_paying & (pay_fee > 0.0) & (transports >= 0)
        if has_fee.any():
            fee_rows = transports[has_fee]
            fee_paid = pay_fee[has_fee]
            org_cash += np.bincount(fee_rows, weights=fee_paid, minlength=org_count)
            sales_receipts += np.bincount(fee_rows, weights=fee_paid, minlength=org_count)
            bank_delta += np.bincount(
                safe_org_bank[fee_rows], weights=fee_paid, minlength=bank_count
            )
            _legs(
                org_cash_account[buyers[has_fee]],
                org_cash_account[fee_rows],
                fee_paid,
                1_000_000 + np.flatnonzero(has_fee),
                org_ids[fee_rows],
            )

    # Plot-buyer edges: households fund their region's plot inputs.
    plot_paying = plot_buyer & pay_active
    if plot_paying.any():
        dest_regions = cell_region[edge_destination[plot_paying]]
        region_paid = np.bincount(
            dest_regions, weights=unit_pay[plot_paying], minlength=region_count
        )
        funding_hh = plot_share * region_paid[hh_region]
        household_cash -= funding_hh
        flows.household_plot_input_funding += funding_hh
        bank_delta -= np.bincount(hh_bank, weights=hh_weight * funding_hh, minlength=bank_count)
        rows = seller_org[plot_paying]
        paid = pay_goods[plot_paying]
        to_org = plot_paying & seller_is_org
        to_import = plot_paying & seller_is_import
        if to_org.any():
            org_rows = seller_org[to_org]
            org_cash += np.bincount(org_rows, weights=pay_goods[to_org], minlength=org_count)
            sales_receipts += np.bincount(org_rows, weights=pay_goods[to_org], minlength=org_count)
            bank_delta += np.bincount(
                safe_org_bank[org_rows], weights=pay_goods[to_org], minlength=bank_count
            )
        if to_import.any():
            # A plot input may be sourced from the national import buffer, so the
            # Treasury (not an organization) is the seller on that leg.
            import_total = float(pay_goods[to_import].sum())
            state.treasury_deposit = float(state.treasury_deposit) + import_total
            bank_delta[0] += import_total
        safe_rows = np.where(seller_is_import[plot_paying], 0, np.maximum(rows, 0))
        credit_accounts = np.where(
            seller_is_import[plot_paying],
            treasury_cash_account,
            org_cash_account[safe_rows],
        )
        _legs(
            clearing_accounts[dest_regions],
            credit_accounts,
            paid,
            1_000_000 + np.flatnonzero(plot_paying),
            org_ids[safe_rows],
        )
        paying_hh = (hh_weight * funding_hh) > 0.0
        _legs(
            household_cash_account[paying_hh],
            clearing_accounts[hh_region[paying_hh]],
            (hh_weight * funding_hh)[paying_hh],
            hh_region[paying_hh] + 2 * region_count,
            None,
        )
        fee_rows = edge_transport[plot_paying]
        has_fee = (pay_fee[plot_paying] > 0.0) & (fee_rows >= 0)
        if has_fee.any():
            fee_paid = pay_fee[plot_paying][has_fee]
            fee_orgs = fee_rows[has_fee]
            org_cash += np.bincount(fee_orgs, weights=fee_paid, minlength=org_count)
            sales_receipts += np.bincount(fee_orgs, weights=fee_paid, minlength=org_count)
            bank_delta += np.bincount(
                safe_org_bank[fee_orgs], weights=fee_paid, minlength=bank_count
            )
            _legs(
                clearing_accounts[dest_regions[has_fee]],
                org_cash_account[fee_orgs],
                fee_paid,
                1_000_000 + np.flatnonzero(plot_paying)[has_fee],
                org_ids[fee_orgs],
            )

    # Treasury-buyer edges: housing and export purchases (goods + fees).
    treasury_paying = treasury_buyer & pay_active
    if treasury_paying.any():
        rows = seller_org[treasury_paying]
        paid = pay_goods[treasury_paying]
        fee_paid = pay_fee[treasury_paying]
        fee_rows = edge_transport[treasury_paying]
        has_fee = (fee_paid > 0.0) & (fee_rows >= 0)
        state.treasury_deposit = float(state.treasury_deposit) - float(
            unit_pay[treasury_paying].sum()
        )
        org_cash += np.bincount(rows, weights=paid, minlength=org_count)
        sales_receipts += np.bincount(rows, weights=paid, minlength=org_count)
        bank_delta += np.bincount(safe_org_bank[rows], weights=paid, minlength=bank_count)
        bank_delta[0] -= float(unit_pay[treasury_paying].sum())
        _legs(
            treasury_cash_account,
            org_cash_account[rows],
            paid,
            np.full(int(np.count_nonzero(treasury_paying)), -2, dtype=np.int64),
            org_ids[rows],
        )
        if has_fee.any():
            fee_orgs = fee_rows[has_fee]
            org_cash += np.bincount(fee_orgs, weights=fee_paid[has_fee], minlength=org_count)
            sales_receipts += np.bincount(fee_orgs, weights=fee_paid[has_fee], minlength=org_count)
            bank_delta += np.bincount(
                safe_org_bank[fee_orgs], weights=fee_paid[has_fee], minlength=bank_count
            )
            _legs(
                treasury_cash_account,
                org_cash_account[fee_orgs],
                fee_paid[has_fee],
                np.full(int(np.count_nonzero(has_fee)), -3, dtype=np.int64),
                org_ids[fee_orgs],
            )

    state.organization_cash = org_cash
    state.household_cash = household_cash
    if leg_amount:
        debit = np.concatenate(leg_debit)
        credit = np.concatenate(leg_credit)
        amount = np.concatenate(leg_amount)
        group = np.concatenate(leg_group)
        org_column = [value for column in leg_org for value in column]
        _append_leg_transactions(
            flows,
            kind="goods_payment",
            debit=debit,
            credit=credit,
            amount=amount,
            groups=group,
            org_column=org_column,
        )
    if bank_count and np.any(bank_delta != 0.0):
        state.bank_deposit_liability = (
            np.asarray(state.bank_deposit_liability, dtype=np.float64) + bank_delta
        )
        state.bank_reserves = np.asarray(state.bank_reserves, dtype=np.float64) + bank_delta
        finance._append_interbank_legs(
            state, flows, kind="goods_payment", delta=bank_delta, leg_offset=0
        )
    _phase("delivery")

    # ---------------- step 7: production and installation ----------------
    final_realized = np.zeros(activity_count, dtype=np.float64)
    used_full = np.zeros(k_count, dtype=np.float64)
    non_transport_k = ~kt_mask
    if non_transport_k.any():
        available = (
            stock_open[input_cell[non_transport_k]]
            + flows.delivered[np.arange(k_count, dtype=np.int64)[non_transport_k]]
        )
        realized, used = produce_leontief(
            available,
            index.k_coefficient[non_transport_k],
            input_activity[non_transport_k],
            target,
        )
        final_realized = realized
        used_full[non_transport_k] = used
    final_realized[early_service_acts] = transport_realized[early_service_acts]
    used_full[kt_mask] = transport_used_k[kt_mask]
    flows.activity_realized = np.where(early_service_acts, transport_realized, final_realized)
    state.stock_value[input_cell[non_transport_k]] -= used_full[non_transport_k]
    non_transport_b = ~early_service_acts[index.b_rows]
    production_amounts = (
        index.b_coefficient[non_transport_b] * final_realized[index.b_rows[non_transport_b]]
    )
    state.stock_value += np.bincount(
        index.b_cells[non_transport_b], weights=production_amounts, minlength=cell_count
    )
    flows.used[:k_count] = used_full

    # Investment installation: delivered WIP into capacity (finance plan).
    project_capital = np.asarray(network.project_capital_cell, dtype=np.int64)
    project_construction = np.asarray(network.project_construction_cell, dtype=np.int64)
    project_owner_by_cell = np.full(cell_count, -1, dtype=np.int64)
    capital_project_rows = np.flatnonzero(project_capital >= 0)
    construction_project_rows = np.flatnonzero(project_construction >= 0)
    project_owner_by_cell[project_capital[capital_project_rows]] = capital_project_rows
    project_owner_by_cell[project_construction[construction_project_rows]] = (
        construction_project_rows
    )
    delivered_capital_wip = np.zeros(org_count, dtype=np.float64)
    delivered_construction_wip = np.zeros(org_count, dtype=np.float64)
    investment_owner_by_demand = np.full(d_count, -1, dtype=np.int64)
    if investment_mask.any():
        inv_dest_cells = demand_cell[investment_mask]
        inv_owner_all = index.demand_buyer[investment_mask].copy()
        owner_missing = inv_owner_all < 0
        if owner_missing.any():
            inv_owner_all[owner_missing] = project_owner_by_cell[inv_dest_cells[owner_missing]]
        _require(
            bool(np.all((inv_owner_all >= 0) & (inv_owner_all < org_count))),
            "investment demand cell has no owning productive organization",
        )
        investment_owner_by_demand[investment_mask] = inv_owner_all
        inv_goods_all = cell_commodity[inv_dest_cells]
        delivered_inv = flows.delivered[investment_mask]
        if capital_g >= 0:
            capital_orders = inv_goods_all == capital_g
            delivered_capital_wip += np.bincount(
                inv_owner_all[capital_orders],
                weights=delivered_inv[capital_orders],
                minlength=org_count,
            )
        if construction_g >= 0:
            construction_orders = inv_goods_all == construction_g
            delivered_construction_wip += np.bincount(
                inv_owner_all[construction_orders],
                weights=delivered_inv[construction_orders],
                minlength=org_count,
            )
    _requested, _approved, completed = finance.run_investment_step(
        state,
        flows,
        parameters,
        delivered_capital_wip=delivered_capital_wip,
        delivered_construction_wip=delivered_construction_wip,
        investment_cash_budget=cash_for_goods,
        new_request=new_request,
    )
    installed_capital = completed * capital_unit
    installed_construction = completed * construction_unit
    if capital_g >= 0:
        capital_cells = project_capital[project_capital >= 0]
        state.stock_value[capital_cells] -= installed_capital[project_capital >= 0]
        inv_capital_demand = investment_mask & (cell_commodity[demand_cell] == capital_g)
        flows.used[inv_capital_demand] = installed_capital[
            investment_owner_by_demand[inv_capital_demand]
        ]
    if construction_g >= 0:
        construction_cells = project_construction[project_construction >= 0]
        state.stock_value[construction_cells] -= installed_construction[project_construction >= 0]
        inv_construction_demand = investment_mask & (cell_commodity[demand_cell] == construction_g)
        flows.used[inv_construction_demand] = installed_construction[
            investment_owner_by_demand[inv_construction_demand]
        ]
    state.organization_capacity = (
        np.asarray(state.organization_capacity, dtype=np.float64) + completed
    )
    state.organization_capital_age = (
        np.asarray(state.organization_capital_age, dtype=np.float64) + with_activity
    )

    # Housing completion: delivered construction becomes dwellings only.
    housing_delivered = np.zeros(region_count, dtype=np.float64)
    if housing_mask.any():
        housing_delivered = flows.delivered[index.housing_demand]
        state.dwelling_stock = np.asarray(state.dwelling_stock, dtype=np.float64) + (
            housing_delivered
        )
        state.housing_vacant = np.asarray(state.housing_vacant, dtype=np.float64) + (
            housing_delivered
        )
        flows.used[index.housing_demand] = housing_delivered

    # Export deliveries recorded on the boundary demand cells.
    for channel in (0, 1):
        for g in range(g_count):
            demand_index = int(export_demand_cell[channel, g])
            if demand_index >= 0:
                flows.used[demand_index] = flows.delivered[demand_index]

    flows.organization_realized[with_activity] = flows.activity_realized[
        org_activity[with_activity]
    ]
    flows.organization_sales_receipts = sales_receipts
    flows.organization_purchases = purchases
    _phase("production")

    # ---------------- step 8: households ----------------------------------
    # Step 8: P03 household subsystem (demand was frozen at tick start).
    retail_map = np.asarray(network.retail_cell_by_commodity, dtype=np.int64)
    retail_open_stock = np.asarray(state.stock_value, dtype=np.float64)
    for r in range(region_count):
        for g in range(g_count):
            cell = int(retail_map[r, g])
            if cell >= 0:
                flows.retail_available[r, g] = max(retail_open_stock[cell], 0.0)
    settle_second_economy(state, flows, network, household_parameters, price_net)
    allocation_opening = capture_material_stocks(state)
    # restore the true opening boundary for the household step's lagged terms
    allocation_opening.household_durable_owned = durable_owned_open.copy()
    allocate_household_baskets(
        state,
        flows,
        household_parameters,
        network,
        allocation_opening,
        price_net,
        household_cash_open,
        household_deferred_open,
        stock_open,
    )
    for column, channel in enumerate(catalog.durable_h_index):
        flows.durable_acquired[:, column] = np.asarray(
            flows.household_realized_h, dtype=np.float64
        )[:, int(channel)]
    update_durable_stocks(state, flows, household_parameters, allocation_opening, catalog)
    private_construction_installation(state, flows, household_parameters, catalog)
    allocate_housing(state, flows, household_parameters)
    account_household_welfare(
        state, flows, household_parameters, network, allocation_opening, price_net
    )
    update_household_expectations(state, flows, household_parameters, allocation_opening)
    _phase("households")

    # ---------------- step 9: expectations, bailout, expiry, trade --------
    delivered_k = flows.delivered[:k_count]
    blocked_k = flows.financial_delivery_blocked[:k_count]
    served = np.bincount(
        k_buyer[org_k], weights=(delivered_k + blocked_k)[org_k], minlength=org_count
    )
    ordered_k = flows.ordered[:k_count]
    demanded_k = np.bincount(k_buyer[org_k], weights=ordered_k[org_k], minlength=org_count)
    observation = np.where(
        demanded_k > 0.0,
        1.0 - served / np.where(demanded_k > 0.0, demanded_k, 1.0),
        0.0,
    )
    alpha = float(parameters.shortage_alpha)
    state.organization_shortage_expectation = np.where(
        has_k_cells,
        (1.0 - alpha) * shortage_open + alpha * observation,
        shortage_open,
    )

    finance.run_bailout_step(
        state,
        flows,
        parameters,
        opening_wage_bill=float(wage_bill_open.sum()),
        transaction_base=100,
    )

    # Services expiry: logistics consumption leaves the transport orgs' own
    # output cells, then every services cell closes at zero.  Household-
    # acquired retail services are consumed on purchase (never stocked), so
    # they close through the same expiry sink in the flow record.
    if services_g >= 0:
        org_output = np.asarray(network.org_output_cell, dtype=np.int64)
        needs_transport_edge = edge_transport >= 0
        if needs_transport_edge.any():
            service_by_org = np.bincount(
                edge_transport[needs_transport_edge],
                weights=flows.edge_service_used[needs_transport_edge],
                minlength=org_count,
            )
            transport_rows_used = np.unique(edge_transport[needs_transport_edge])
            cells_t = org_output[transport_rows_used]
            valid_cells = cells_t >= 0
            state.stock_value[cells_t[valid_cells]] -= service_by_org[
                transport_rows_used[valid_cells]
            ]
        ephemeral_cells = np.flatnonzero(np.isin(cell_commodity, _ephemeral_commodity_ids(network)))
        leftovers = state.stock_value[ephemeral_cells]
        flows.expired_services = float(leftovers.sum())
        state.stock_value[ephemeral_cells] = 0.0

    second_expiry(state, network)

    export_delivered_cmea = np.zeros(g_count, dtype=np.float64)
    export_delivered_convertible = np.zeros(g_count, dtype=np.float64)
    for g in range(g_count):
        if export_demand_cell[0, g] >= 0:
            export_delivered_cmea[g] = flows.delivered[int(export_demand_cell[0, g])]
        if export_demand_cell[1, g] >= 0:
            export_delivered_convertible[g] = flows.delivered[int(export_demand_cell[1, g])]
    settle_exports_and_closing(
        state,
        flows,
        parameters,
        network,
        cmea_export_delivered=export_delivered_cmea,
        convertible_export_delivered=export_delivered_convertible,
        oil_price=oil_price,
        cmea_contract_price=cmea_quote,
        official_fx_quote=fx_quote,
        transaction_base=200,
    )
    flows.household_cash_close = np.asarray(state.household_cash, dtype=np.float64).copy()
    _phase("finance")

    # ---------------- step 10: flow assembly and cheap gates --------------
    household_view = index.household_demand_region >= 0
    saved_household_views = {
        name: getattr(flows, name)[household_view].copy()
        for name in ("desired", "ordered", "ordered_gross", "allocated", "delivered", "used")
    }
    flows.desired = desired
    flows.ordered = ordered
    flows.ordered_gross = gross
    flows.unfunded_order = unfunded
    flows.allocated = allocated
    for name, values in saved_household_views.items():
        getattr(flows, name)[household_view] = values
    flows.inventory_open = inv_open
    close_view = np.zeros(d_count, dtype=np.float64)
    close_view[has_dest] = state.stock_value[demand_cell[has_dest]]
    flows.inventory_close = close_view

    # Trader demand cells: used = the destination cell's outgoing release.
    trader_mask = np.isin(demand_purpose, (_PURPOSE_PROCUREMENT, _PURPOSE_RETAIL))
    if trader_mask.any():
        outgoing = np.bincount(edge_source, weights=flows.edge_delivered, minlength=cell_count)
        trader_dest = demand_cell[trader_mask]
        flows.used[trader_mask] = outgoing[trader_dest]

    _finite(
        "flows",
        flows.desired,
        flows.ordered,
        flows.allocated,
        flows.delivered,
        flows.used,
        flows.edge_delivered,
        flows.activity_realized,
        flows.household_realized,
    )
    over = np.flatnonzero(flows.allocated > flows.ordered + _ATOL)
    _require(
        over.size == 0,
        f"allocation exceeded the funded order at demand cells {over[:8].tolist()} "
        f"(purpose {np.asarray(network.demand_purpose)[over[:8]].tolist()})",
    )
    _require(
        bool(np.all(flows.delivered <= flows.allocated + _ATOL)),
        "delivery exceeded the allocation",
    )
    _require(
        bool(np.all(state.stock_value >= -_STOCK_DUST)),
        "stock cells went negative",
    )
    state.stock_value = np.maximum(state.stock_value, 0.0)
    # P05 §0.6: M2-neutral working-capital recycling + explicit SBC redistribution.
    finance.run_working_capital_cycle(state, flows, parameters)
    if bool(getattr(parameters, "demand_limited_targets", False)):
        # Next quarter's production cap tracks *realized* consumption of each
        # commodity (intermediate use + household retail + exports actually
        # delivered), floored by exogenous household demand so the rule cannot
        # collapse to the trivial zero fixed point.
        delivered_by_demand = np.bincount(
            edge_demand,
            weights=np.asarray(flows.edge_delivered, dtype=np.float64),
            minlength=d_count,
        )
        consuming = (
            (demand_purpose == _PURPOSE_INTERMEDIATE)
            | (demand_purpose == _PURPOSE_RETAIL)
            | (demand_purpose == _PURPOSE_EXPORT_CMEA)
            | (demand_purpose == _PURPOSE_EXPORT_CONVERTIBLE)
            | (demand_purpose == _PURPOSE_INVESTMENT)
            | (demand_purpose == _PURPOSE_HOUSING)
        )
        cons_by_g = np.bincount(
            cell_commodity[demand_cell[consuming]],
            weights=delivered_by_demand[consuming],
            minlength=g_count,
        )
        floor_by_g = np.asarray(parent_demand_region, dtype=np.float64).sum(axis=0)
        floor_mix = float(getattr(parameters, "demand_floor", 1.0))
        need_by_g = np.maximum(cons_by_g, floor_mix * floor_by_g)
        org_out_cell_sig = np.asarray(network.org_output_cell, dtype=np.int64)
        org_out_g = np.where(
            org_out_cell_sig >= 0, cell_commodity[np.maximum(org_out_cell_sig, 0)], -1
        )
        state.organization_demand_signal = np.where(
            org_out_g >= 0, need_by_g[np.maximum(org_out_g, 0)], 0.0
        )
    if services_g >= 0:
        ephemeral_now = np.isin(cell_commodity, _ephemeral_commodity_ids(network))
        _require(
            bool(np.all(state.stock_value[ephemeral_now] == 0.0)),
            "services cells must close at zero",
        )
    _require(
        bool(np.all(state.organization_shortage_expectation >= 0.0))
        and bool(np.all(state.organization_shortage_expectation <= 1.0)),
        "closing shortage expectations must lie in [0, 1]",
    )
    # Bank sheet identity and the deposit-liability coverage identity.
    assets = (
        np.asarray(state.bank_loan_asset, dtype=np.float64)
        + np.asarray(state.bank_interest_receivable, dtype=np.float64)
        + np.asarray(state.bank_reserves, dtype=np.float64)
    )
    liabilities = np.asarray(state.bank_deposit_liability, dtype=np.float64) + np.asarray(
        state.bank_equity, dtype=np.float64
    )
    _require(
        bool(np.all(np.abs(assets - liabilities) <= 1e-6)),
        "bank balance sheet identity broken",
    )
    deposits = np.asarray(state.bank_deposit_liability, dtype=np.float64)
    covered = (
        float(np.sum(hh_weight * np.asarray(state.household_cash, dtype=np.float64)))
        + float(np.sum(np.asarray(state.organization_cash, dtype=np.float64)))
        + float(state.treasury_deposit)
        + float(state.credit_fund)
    )
    money_gap = abs(float(deposits.sum()) - covered)
    money_tol = 1e-6 + float(getattr(parameters, "money_tolerance_rel", 0.0)) * max(
        abs(float(deposits.sum())), abs(covered)
    )
    _require(
        bool(money_gap <= money_tol),
        "deposit liability no longer covers household, organization and treasury cash",
    )
    _require(
        bool(np.all(np.asarray(state.bank_reserves, dtype=np.float64) >= -1e-6)),
        "bank reserves went negative",
    )
    household_cash_close = np.asarray(state.household_cash, dtype=np.float64)
    expected_cash = (
        household_cash_open
        + flows.household_wage_income
        + flows.household_plot_income_formal
        + flows.household_plot_income_direct
        + flows.household_second_income_direct
        + flows.household_late_wage
        - flows.household_plot_input_funding
        - flows.household_second_input_funding
        - flows.household_spending
    )
    _require(
        bool(np.all(np.abs(household_cash_close - expected_cash) <= 1e-6)),
        "household cash identity broken",
    )
    _phase("gates")
    return flows


def _new_flows(
    tick: int,
    quarter: str,
    org_count: int,
    household_count: int,
    region_count: int,
    g_count: int,
    activity_count: int,
    k_count: int,
    d_count: int,
    m_count: int,
    cell_count: int,
    h_count: int,
) -> MaterialTickFlows:
    return MaterialTickFlows(
        tick=tick,
        quarter=quarter,
        activity_target=np.zeros(activity_count, dtype=np.float64),
        activity_realized=np.zeros(activity_count, dtype=np.float64),
        desired=np.zeros(d_count, dtype=np.float64),
        ordered=np.zeros(d_count, dtype=np.float64),
        ordered_gross=np.zeros(d_count, dtype=np.float64),
        unfunded_order=np.zeros(d_count, dtype=np.float64),
        allocated=np.zeros(d_count, dtype=np.float64),
        delivered=np.zeros(d_count, dtype=np.float64),
        used=np.zeros(d_count, dtype=np.float64),
        inventory_open=np.zeros(d_count, dtype=np.float64),
        inventory_close=np.zeros(d_count, dtype=np.float64),
        financial_delivery_blocked=np.zeros(d_count, dtype=np.float64),
        physical_delivery_blocked=np.zeros(d_count, dtype=np.float64),
        edge_delivered=np.zeros(m_count, dtype=np.float64),
        edge_allocated=np.zeros(m_count, dtype=np.float64),
        edge_service_used=np.zeros(m_count, dtype=np.float64),
        edge_service_fee=np.zeros(m_count, dtype=np.float64),
        organization_target=np.zeros(org_count, dtype=np.float64),
        organization_realized=np.zeros(org_count, dtype=np.float64),
        organization_wage_due=np.zeros(org_count, dtype=np.float64),
        organization_wage_paid=np.zeros(org_count, dtype=np.float64),
        organization_interest_due=np.zeros(org_count, dtype=np.float64),
        organization_interest_paid=np.zeros(org_count, dtype=np.float64),
        organization_principal_paid=np.zeros(org_count, dtype=np.float64),
        organization_credit_requested=np.zeros(org_count, dtype=np.float64),
        organization_credit_approved=np.zeros(org_count, dtype=np.float64),
        organization_credit_drawn=np.zeros(org_count, dtype=np.float64),
        organization_investment_requested=np.zeros(org_count, dtype=np.float64),
        organization_investment_approved=np.zeros(org_count, dtype=np.float64),
        organization_investment_completed=np.zeros(org_count, dtype=np.float64),
        organization_bailout_requested=np.zeros(org_count, dtype=np.float64),
        organization_bailout_granted=np.zeros(org_count, dtype=np.float64),
        organization_sbc_transfer=np.zeros(org_count, dtype=np.float64),
        organization_sales_receipts=np.zeros(org_count, dtype=np.float64),
        organization_purchases=np.zeros(org_count, dtype=np.float64),
        household_wage_income=np.zeros(household_count, dtype=np.float64),
        household_plot_income_formal=np.zeros(household_count, dtype=np.float64),
        household_plot_income_direct=np.zeros(household_count, dtype=np.float64),
        household_late_wage=np.zeros(household_count, dtype=np.float64),
        household_desired=np.zeros((household_count, g_count), dtype=np.float64),
        household_affordable=np.zeros((household_count, g_count), dtype=np.float64),
        household_realized=np.zeros((household_count, g_count), dtype=np.float64),
        household_budget_unmet=np.zeros((household_count, g_count), dtype=np.float64),
        household_availability_unmet=np.zeros((household_count, g_count), dtype=np.float64),
        household_spending=np.zeros(household_count, dtype=np.float64),
        household_self_use=np.zeros(household_count, dtype=np.float64),
        household_plot_input_funding=np.zeros(household_count, dtype=np.float64),
        household_budget_available=np.zeros(household_count, dtype=np.float64),
        household_forced_saving=np.zeros(household_count, dtype=np.float64),
        household_voluntary_saving=np.zeros(household_count, dtype=np.float64),
        household_cash_open=np.zeros(household_count, dtype=np.float64),
        household_cash_close=np.zeros(household_count, dtype=np.float64),
        household_desired_h=np.zeros((household_count, h_count), dtype=np.float64),
        household_affordable_h=np.zeros((household_count, h_count), dtype=np.float64),
        household_realized_h=np.zeros((household_count, h_count), dtype=np.float64),
        household_budget_unmet_h=np.zeros((household_count, h_count), dtype=np.float64),
        household_availability_unmet_h=np.zeros((household_count, h_count), dtype=np.float64),
        household_formal_h=np.zeros((household_count, h_count), dtype=np.float64),
        household_plot_self_h=np.zeros((household_count, h_count), dtype=np.float64),
        household_plot_market_h=np.zeros((household_count, h_count), dtype=np.float64),
        household_second_h=np.zeros((household_count, h_count), dtype=np.float64),
        household_goal_credit_h=np.zeros((household_count, h_count), dtype=np.float64),
        household_substitution=np.zeros((household_count, N_Q), dtype=np.float64),
        household_queue_hours=np.zeros(household_count, dtype=np.float64),
        household_search_hours=np.zeros(household_count, dtype=np.float64),
        household_plot_hours=np.zeros(household_count, dtype=np.float64),
        household_second_hours=np.zeros(household_count, dtype=np.float64),
        household_leisure_hours=np.zeros(household_count, dtype=np.float64),
        household_planned_spending=np.zeros(household_count, dtype=np.float64),
        household_savings_draw=np.zeros(household_count, dtype=np.float64),
        household_second_input_funding=np.zeros(household_count, dtype=np.float64),
        household_second_income_direct=np.zeros(household_count, dtype=np.float64),
        household_substitution_loss=np.zeros(household_count, dtype=np.float64),
        household_postponement_cost=np.zeros(household_count, dtype=np.float64),
        household_welfare_net=np.zeros(household_count, dtype=np.float64),
        durable_acquired=np.zeros((household_count, N_D), dtype=np.float64),
        durable_retired=np.zeros((household_count, N_D), dtype=np.float64),
        durable_repaired=np.zeros((household_count, N_D), dtype=np.float64),
        housing_allocated=np.zeros(household_count, dtype=np.float64),
        private_completed=np.zeros(household_count, dtype=np.float64),
        household_overcrowding=np.zeros(household_count, dtype=np.float64),
        entitlement_gap=np.zeros((household_count, N_E), dtype=np.float64),
        second_input_used=np.zeros(cell_count, dtype=np.float64),
        retail_available=np.zeros((region_count, g_count), dtype=np.float64),
        retail_sales=np.zeros((region_count, g_count), dtype=np.float64),
        retail_unmet=np.zeros((region_count, g_count), dtype=np.float64),
        imports=np.zeros(g_count, dtype=np.float64),
        cmea_imports=np.zeros(g_count, dtype=np.float64),
        convertible_imports=np.zeros(g_count, dtype=np.float64),
        cmea_exports=np.zeros(g_count, dtype=np.float64),
        convertible_exports=np.zeros(g_count, dtype=np.float64),
        cmea_import_payment=0.0,
        cmea_export_receipt=0.0,
        usd_import_payment=0.0,
        usd_export_receipt=0.0,
        usd_interest_paid=0.0,
        usd_interest_accrued=0.0,
        usd_principal_paid=0.0,
        usd_loan_drawn=0.0,
        official_fx_translation=None,
        expired_services=0.0,
        service_pool_draw_at_cell=np.zeros(cell_count, dtype=np.float64),
        service_pool_credit_at_cell=np.zeros(cell_count, dtype=np.float64),
    )


# ---------------------------------------------------------------------------
# Canonical digests (single field-spec over every state/flow array)
# ---------------------------------------------------------------------------


def _block(field: str, array: np.ndarray) -> bytes:
    """Canonical ``field`` block: JSON header + length prefix + payload."""
    dtype = np.dtype(array.dtype.newbyteorder("<"))
    contiguous = np.ascontiguousarray(array, dtype=dtype)
    header = canonical_json(
        {
            "field": field,
            "shape": list(contiguous.shape),
            "dtype": contiguous.dtype.str,
            "byte_length": int(contiguous.nbytes),
        }
    )
    return struct.pack("<Q", len(header)) + header + contiguous.tobytes()


def _state_scalar_header(state: MaterialState) -> dict[str, Any]:
    return {
        "state_version": state.schema_version,
        "completed_ticks": int(state.completed_ticks),
        "treasury_deposit": float(state.treasury_deposit),
        "usd_reserve": float(state.usd_reserve),
        "usd_principal": float(state.usd_principal),
        "usd_interest_arrears": float(state.usd_interest_arrears),
        "cmea_settlement_balance": float(state.cmea_settlement_balance),
    }


def _flow_scalar_header(flows: MaterialTickFlows) -> dict[str, Any]:
    return {
        "tick": int(flows.tick),
        "quarter": flows.quarter,
        "cmea_import_payment": float(flows.cmea_import_payment),
        "cmea_export_receipt": float(flows.cmea_export_receipt),
        "usd_import_payment": float(flows.usd_import_payment),
        "usd_export_receipt": float(flows.usd_export_receipt),
        "usd_interest_paid": float(flows.usd_interest_paid),
        "usd_interest_accrued": float(flows.usd_interest_accrued),
        "usd_principal_paid": float(flows.usd_principal_paid),
        "usd_loan_drawn": float(flows.usd_loan_drawn),
        "official_fx_translation": flows.official_fx_translation,
        "expired_services": float(flows.expired_services),
    }


def canonical_material_bytes(state: MaterialState, flows: MaterialTickFlows | None = None) -> bytes:
    """Deterministic bytes over every state (and optional flow) field.

    The field list is derived from the dataclass field specs themselves, so
    no ndarray or scalar state field can escape the digest.  Timers, UUIDs,
    paths and writer objects never enter; journal columns hash through
    canonical JSON.
    """
    header: dict[str, Any] = {"state": _state_scalar_header(state)}
    if flows is not None:
        header["flows"] = _flow_scalar_header(flows)
    header_bytes = canonical_json(header)
    chunks = [struct.pack("<Q", len(header_bytes)) + header_bytes]
    state_arrays = sorted(
        (f.name, getattr(state, f.name))
        for f in fields(MaterialState)
        if isinstance(getattr(state, f.name), np.ndarray)
    )
    for name, array in state_arrays:
        chunks.append(_block(name, array))
    if flows is not None:
        flow_arrays = sorted(
            (f.name, getattr(flows, f.name))
            for f in fields(MaterialTickFlows)
            if isinstance(getattr(flows, f.name), np.ndarray)
        )
        for name, array in flow_arrays:
            chunks.append(_block(name, array))
        journal = {
            "journal_kind": list(flows.journal_kind),
            "journal_tick": list(flows.journal_tick),
            "journal_debit": list(flows.journal_debit),
            "journal_credit": list(flows.journal_credit),
            "journal_currency": list(flows.journal_currency),
            "journal_amount": [float(value) for value in flows.journal_amount],
            "journal_org": list(flows.journal_org),
            "journal_leg": list(flows.journal_leg),
        }
        journal_bytes = canonical_json(journal)
        chunks.append(struct.pack("<Q", len(journal_bytes)) + journal_bytes)
    return b"".join(chunks)


def initial_digest_chain(
    *,
    spec: ScenarioSpec,
    baseline_hash: str,
    lock_hash: str,
    parameter_hash: str,
    initial_recipe_hash: str,
    input_artifact_hashes: dict[str, str],
    initial_state: MaterialState,
) -> str:
    """Bind the run's provenance hashes to the initial state hash."""
    initial_state_hash = hashlib.sha256(canonical_material_bytes(initial_state)).hexdigest()
    return canonical_digest(
        {
            "engine_version": MATERIAL_ENGINE_VERSION,
            "state_version": MATERIAL_STATE_VERSION,
            "baseline_hash": baseline_hash,
            "lock_hash": lock_hash,
            "seed": spec.seed,
            "stochastic": spec.stochastic,
            "households": spec.households,
            "organizations": spec.organizations,
            "region_ids": list(spec.region_ids),
            "commodity_ids": list(spec.commodities),
            "initial_recipe_hash": initial_recipe_hash,
            "parameter_hash": parameter_hash,
            "input_artifact_hashes": dict(input_artifact_hashes),
            "initial_state_hash": initial_state_hash,
        }
    )


def advance_chain(previous: str, state: MaterialState, flows: MaterialTickFlows) -> str:
    """Extend the replay chain with one admitted tick's closing state."""
    digest = hashlib.sha256()
    digest.update(bytes.fromhex(previous))
    digest.update(canonical_material_bytes(state, flows))
    return digest.hexdigest()


def material_parameter_vector(spec: ScenarioSpec) -> dict[str, float]:
    """``MaterialParameters.flatten`` + ``MaterialInitialRecipe.flatten``."""
    parameters = spec.material_parameters
    recipe = spec.material_initial
    if parameters is None or recipe is None:
        raise ConfigError("material scenario lacks parameters/initial recipe")
    flattened = parameters.flatten()
    # Preserve the pre-earmark parameter identity for the default arm.  The
    # field remains declared and flattened, but a zero earmark is a no-op and
    # must not invalidate legacy replay digests or output rows that carry the
    # parameter hash. Non-zero experimental arms are fully hash-bound.
    for name in (
        "input_credit_earmark_fraction",
        "interest_sink_remittance_fraction",
        "interest_sink_recipient.households",
        "fiscal_turnover_remittance_fraction",
    ):
        if flattened.get(name) == 0.0:
            flattened.pop(name)
    return {**flattened, **recipe.flatten()}


def material_recipe_hash(spec: ScenarioSpec) -> str:
    """Canonical digest of recipe + technologies + routes + plot recipe."""
    if spec.organization_recipe is None or spec.technologies is None:
        raise ConfigError("material scenario lacks organization_recipe/technologies")
    return canonical_digest(
        {
            "organization_recipe": spec.organization_recipe.model_dump(mode="json"),
            "technologies": [tech.model_dump(mode="json") for tech in spec.technologies],
            "routes": None
            if spec.routes is None
            else [route.model_dump(mode="json") for route in spec.routes],
            "plot_recipe": PrivatePlotRecipe().model_dump(mode="json"),
        }
    )


def load_material_forcing(spec: ScenarioSpec, registry: DataRegistry) -> MaterialForcing:
    """Re-export of the DATA2 loader (forcing pack, never a download)."""
    from hsm_lab.data.material import load_material_forcing as _load

    return _load(spec, registry)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _parse_until(until: Quarter | str | None) -> Quarter | None:
    if until is None:
        return None
    if isinstance(until, str):
        return Quarter.parse(until)
    return until


def _target_ticks(spec: ScenarioSpec, until: Quarter | None, start_tick: int) -> int:
    if until is None:
        return spec.ticks
    end = spec.start.advance(spec.ticks - 1)
    first = spec.start.advance(start_tick)
    if until.to_ordinal() < first.to_ordinal():
        raise ConfigError(f"--until {until} precedes the first executed quarter {first}")
    if until.to_ordinal() > end.to_ordinal():
        raise ConfigError(f"--until {until} lies beyond the scenario end {end}")
    return until.to_ordinal() - spec.start.to_ordinal() + 1


def _material_residuals(
    opening: MaterialStockSnapshot,
    state: MaterialState,
    flows: MaterialTickFlows,
    network: MaterialNetwork,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-commodity max per-cell continuity residual and its tolerance."""
    index = _tick_index(network)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    g_count = len(network.commodity_ids)
    cell_count = cell_commodity.size
    open_ = np.asarray(opening.stock_value, dtype=np.float64)
    close = np.asarray(state.stock_value, dtype=np.float64)

    inflow = np.zeros(cell_count, dtype=np.float64)
    inflow += np.bincount(
        index.b_cells,
        weights=index.b_coefficient * flows.activity_realized[index.b_rows],
        minlength=cell_count,
    )
    import_cell = np.asarray(network.import_pool_cell, dtype=np.int64)
    has_import = import_cell >= 0
    if has_import.any():
        inflow[import_cell[has_import]] += flows.imports[has_import]
    edge_destination = np.asarray(network.edge_destination_cell, dtype=np.int64)
    edge_source = np.asarray(network.edge_source_cell, dtype=np.int64)
    valid_dest = edge_destination >= 0
    inflow += np.bincount(
        edge_destination[valid_dest], weights=flows.edge_delivered[valid_dest], minlength=cell_count
    )
    outflow = np.bincount(edge_source, weights=flows.edge_delivered, minlength=cell_count)
    # logistics services leave the transport orgs' own output cells
    org_output = np.asarray(network.org_output_cell, dtype=np.int64)
    edge_transport = np.asarray(network.edge_transport_org, dtype=np.int64)
    needs_transport = edge_transport >= 0
    services_g = (
        network.commodity_ids.index("services_transport")
        if "services_transport" in network.commodity_ids
        else -1
    )
    if services_g >= 0 and needs_transport.any():
        service_by_org = np.bincount(
            edge_transport[needs_transport],
            weights=flows.edge_service_used[needs_transport],
            minlength=org_output.size,
        )
        transport_rows = np.unique(edge_transport[needs_transport])
        cells_t = org_output[transport_rows]
        valid = cells_t >= 0
        outflow[cells_t[valid]] += service_by_org[transport_rows[valid]]
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    k_count = int(network.input_cell.shape[0])
    production_use = np.isin(
        demand_purpose[:k_count], (_PURPOSE_INTERMEDIATE, _PURPOSE_PRIVATE_PLOT)
    )
    if production_use.any():
        outflow += np.bincount(
            demand_cell[:k_count][production_use],
            weights=flows.used[:k_count][production_use],
            minlength=cell_count,
        )
    investment_use = demand_purpose == _PURPOSE_INVESTMENT
    if investment_use.any():
        outflow += np.bincount(
            demand_cell[investment_use],
            weights=flows.used[investment_use],
            minlength=cell_count,
        )
    if services_g >= 0:
        services_cells = np.isin(cell_commodity, _ephemeral_commodity_ids(network))
        expiry = np.maximum(open_ + inflow - outflow, 0.0)[services_cells]
        outflow[services_cells] += expiry
    residual_cells = np.abs(close - open_ - inflow + outflow)
    residual = np.zeros(g_count, dtype=np.float64)
    np.maximum.at(residual, cell_commodity, residual_cells)
    closing_by_commodity = np.bincount(
        cell_commodity, weights=np.maximum(close, 0.0), minlength=g_count
    )
    tolerance = _ATOL + 1e-10 * closing_by_commodity
    return residual, tolerance


def _build_summary(
    *,
    run_id: str,
    spec: ScenarioSpec,
    state: MaterialState,
    history: MaterialHistory,
    frames: dict[str, Any],
    rng: RngRegistry,
    parameter_hash: str,
    initial_recipe_hash: str,
    input_artifact_hashes: dict[str, str],
    performance: dict[str, Any],
    checkpoint_paths: list[str],
    research_warnings: list[str],
    tallies: dict[str, Any],
    dimensions: dict[str, int],
) -> dict[str, Any]:
    """Build a material-run summary from compact material tables."""
    draws_by_module = rng.draws_by_module()
    draws_count = sum(draws_by_module.values())
    boundary = state.completed_ticks
    summary: dict[str, Any] = {
        "schema_version": "1",
        "run_id": run_id,
        "run_kind": MATERIAL_RUN_KIND,
        "engine_version": MATERIAL_ENGINE_VERSION,
        "political_mode": None,
        "scenario_id": spec.scenario_id,
        "start": str(spec.start),
        "end": str(spec.start.advance(spec.ticks - 1)),
        "last_completed_quarter": (str(spec.start.advance(boundary - 1)) if boundary else None),
        "planned_ticks": spec.ticks,
        "completed_ticks": boundary,
        "horizon_reached": boundary == spec.ticks,
        "households": spec.households,
        "organizations": spec.organizations,
        "region_ids": list(spec.region_ids),
        "commodity_ids": list(spec.commodities),
        "seed": spec.seed,
        "output_policy": spec.output_policy.value,
        "parameter_hash": parameter_hash,
        "initial_recipe_hash": initial_recipe_hash,
        "input_artifact_hashes": dict(input_artifact_hashes),
        "deterministic_replay_digest": history.digest_chain,
        "rng_scheme_version": RNG_SCHEME_VERSION,
        "rng_draws_count": draws_count,
        "rng_draws_by_module": draws_by_module,
        "stochastic_modules_active": [
            module for module, count in draws_by_module.items() if count > 0
        ],
        "row_counts": {name: frame.height for name, frame in frames.items()},
        "dimensions": dimensions,
        "by_commodity": tallies["by_commodity"],
        "household_budget": tallies["household_budget"],
        "invariants": tallies["invariants"],
        "performance": performance,
        "checkpoint_paths": list(checkpoint_paths),
        "research_warnings": research_warnings + [MATERIAL_RESEARCH_WARNING],
        "mechanism_diagnostics": {
            "assessment_status": "not_assessed",
            "shortage_expectation_mean_close": float(
                np.mean(state.organization_shortage_expectation)
            ),
            "bailout_expectation_mean_close": float(
                np.mean(state.organization_bailout_expectation)
            ),
            "bailout_ticks_with_grants": int(tallies["bailout_ticks"]),
            "financial_delivery_blocked_total": float(tallies["blocked_total"]),
            "expired_services_total": float(tallies["expired_services_total"]),
        },
        "mechanism_note": (
            "Intermediate-8 economic quantities are synthetic engineering fixture "
            "values, not historical Hungarian magnitudes; mechanism diagnostics "
            "carry numeric counts only and no theory verdict."
        ),
    }
    if not spec.stochastic:
        summary["deterministic_mode"] = {
            "warning": "deterministic_no_replicates",
            "note": "zero stochastic tick draws: this run is not a stochastic replicate",
        }
    return summary


def run_material(
    spec: ScenarioSpec,
    output_dir: Path,
    contract: ResearchContract,
    registry: DataRegistry,
    *,
    until: Quarter | str | None = None,
    checkpoint_every: int = 0,
    resume_from: Path | None = None,
) -> RunManifest:
    """Run Intermediate-8 material simulation into a fresh output directory."""
    from hsm_lab.storage.checkpoint import (
        checkpoint_dir,
        load_material_checkpoint,
        save_material_checkpoint,
    )
    from hsm_lab.storage.material_output import (
        append_material_rows,
        history_frames,
        write_material_tables,
    )

    if spec.kind != "material":
        raise ConfigError(f"run_material requires kind='material', got {spec.kind!r}")
    root = registry.root
    baseline_hash = verify_baseline(root / BASELINE_FILENAME, contract)
    spec.validate_for_run(contract)  # refuses research_full, pins profile gates
    if checkpoint_every < 0:
        raise ConfigError("checkpoint_every must be non-negative")

    # ---------------- preflight (before any output exists) ----------------
    preflight_started = time.perf_counter()
    forcing = load_material_forcing(spec, registry)
    lock_hash = compute_lock_hash(root)
    parameter_hash = compute_parameter_hash(material_parameter_vector(spec))
    initial_recipe_hash = material_recipe_hash(spec)

    parent_run_id: str | None = None
    resume_state = None
    resume_history = None
    resume_rng = None
    network: MaterialNetwork | None = None
    if resume_from is not None:
        probe_rng = RngRegistry(spec.seed)
        probe_initial = build_material_initial_conditions(spec, probe_rng)
        network = build_material_network(spec, contract, probe_initial)
        resume_state, resume_history, resume_rng, metadata = load_material_checkpoint(
            resume_from, spec, contract, network
        )
        restored = ScenarioSpec.model_validate(metadata["scenario"])
        restored.validate_for_run(contract)
        if compute_scenario_hash(restored) != metadata.get("scenario_hash"):
            raise ResearchGateError("restored scenario hash mismatch")
        if (
            restored.seed != spec.seed
            or restored.households != spec.households
            or restored.organizations != spec.organizations
        ):
            raise ResearchGateError("--resume must not override seed, households or organizations")
        if compute_scenario_hash(restored) != compute_scenario_hash(spec):
            spec = restored
            forcing = load_material_forcing(spec, registry)
            rebuild_rng = RngRegistry(spec.seed)
            rebuild_initial = build_material_initial_conditions(spec, rebuild_rng)
            network = build_material_network(spec, contract, rebuild_initial)
        parent_run_id = str(metadata.get("source_run_id") or "")
        next_quarter = spec.start.advance(resume_state.completed_ticks)
        if next_quarter.to_ordinal() > spec.start.advance(spec.ticks - 1).to_ordinal():
            raise ConfigError(
                f"checkpoint boundary {next_quarter} already ends the scenario; "
                "a zero-tick replay is refused"
            )
    until_quarter = _parse_until(until)
    start_tick = resume_state.completed_ticks if resume_state is not None else 0
    target_ticks = _target_ticks(spec, until_quarter, start_tick)

    if output_dir.exists() or output_dir.is_symlink():
        raise ResearchGateError(
            f"output directory {output_dir} already exists; refusing to overwrite any previous run"
        )

    run_id = uuid4().hex
    # P05 §195: ontology/fidelity/retention and the sealed target split are
    # declared explicitly and kept out of the replay behaviour digest.
    running = manifest_preamble(
        run_id=run_id,
        spec=spec,
        contract=contract,
        root=root,
        baseline_hash=baseline_hash,
        run_kind=MATERIAL_RUN_KIND,
        parameter_vector=material_parameter_vector(spec),
        input_artifact_hashes=forcing.input_artifact_hashes,
        initial_recipe_hash=initial_recipe_hash,
        engine_version=MATERIAL_ENGINE_VERSION,
        parent_run_id=parent_run_id or None,
        resumed_from_checkpoint=str(resume_from) if resume_from is not None else None,
        **p05_manifest_fields(root, spec),
    )
    output_dir.mkdir(parents=True)
    write_manifest_atomic(output_dir, running)
    preflight_s = time.perf_counter() - preflight_started

    state: MaterialState | None = None
    history: MaterialHistory | None = None
    rng: RngRegistry | None = None
    checkpoint_paths: list[str] = []
    saved_boundaries: set[int] = set()
    admitted_ticks = 0
    phase_totals: dict[str, float] = {}
    try:
        init_started = time.perf_counter()
        if resume_from is None:
            rng = RngRegistry(spec.seed)
            initial = build_material_initial_conditions(spec, rng)
            network = build_material_network(spec, contract, initial)
            state = initialize_material(spec, initial, network)
            history = MaterialHistory()
            history.digest_chain = initial_digest_chain(
                spec=spec,
                baseline_hash=baseline_hash,
                lock_hash=lock_hash,
                parameter_hash=parameter_hash,
                initial_recipe_hash=initial_recipe_hash,
                input_artifact_hashes=forcing.input_artifact_hashes,
                initial_state=state,
            )
        else:
            state, history, rng = resume_state, resume_history, resume_rng
            assert network is not None
        init_s = time.perf_counter() - init_started
        assert state is not None and history is not None and rng is not None
        parameters = spec.material_parameters
        assert parameters is not None and network is not None

        from hsm_lab.engine import accounting as accounting_module

        index = _tick_index(network)
        g_count = len(network.commodity_ids)
        cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
        tallies: dict[str, Any] = {
            "production": np.zeros(g_count, dtype=np.float64),
            "imports": np.zeros(g_count, dtype=np.float64),
            "exports": np.zeros(g_count, dtype=np.float64),
            "consumption": np.zeros(g_count, dtype=np.float64),
            "desired": np.zeros(g_count, dtype=np.float64),
            "availability_unmet": np.zeros(g_count, dtype=np.float64),
            "income": 0.0,
            "spending": 0.0,
            "forced": 0.0,
            "voluntary": 0.0,
            "bailout_ticks": 0,
            "blocked_total": 0.0,
            "expired_services_total": 0.0,
            "max_material_abs_residual": 0.0,
            "max_material_tolerance_ratio": 0.0,
            "max_finance_abs_residual": 0.0,
            "max_finance_tolerance_ratio": 0.0,
        }
        compute_s = 0.0
        aggregate_s = 0.0
        checkpoint_s = 0.0
        gates_s = 0.0
        digest_s = 0.0
        run_started = time.perf_counter()
        cpu_started = time.process_time()

        admitted_ticks = state.completed_ticks
        while state.completed_ticks < target_ticks:
            started = time.perf_counter()
            expected_tick = state.completed_ticks
            opening = capture_material_stocks(state)
            quarter_expected = str(spec.start.advance(expected_tick))
            if list(forcing.quarters)[expected_tick] != quarter_expected:
                raise ResearchGateError(
                    f"tick {expected_tick} forcing slice does not bind quarter {quarter_expected}"
                )
            flows = tick_material(state, forcing, parameters, network, phase_times=phase_totals)
            if flows.tick != expected_tick or flows.quarter != quarter_expected:
                raise ResearchGateError(
                    f"tick {flows.tick} does not describe the next admitted quarter {expected_tick}"
                )
            compute_s += time.perf_counter() - started

            started = time.perf_counter()
            invariant_summary = accounting_module.check_material_invariants(
                opening, state, flows, parameters, network
            )
            residual, tolerance = _material_residuals(opening, state, flows, network)
            flows.material_balance_residual = residual
            flows.material_balance_tolerance = tolerance
            finance_residual, finance_tolerance = accounting_module.finance_balance_residuals(
                state, flows
            )
            flows.finance_balance_residual = finance_residual
            flows.finance_balance_tolerance = finance_tolerance
            gates_s += time.perf_counter() - started

            started = time.perf_counter()
            state.completed_ticks += 1
            history.digest_chain = advance_chain(history.digest_chain, state, flows)
            digest_s += time.perf_counter() - started
            admitted_ticks = state.completed_ticks

            started = time.perf_counter()
            invariant_dict: dict[str, Any] = {
                "max_material_abs_residual": float(invariant_summary.max_material_abs_residual),
                "max_material_tolerance_ratio": float(
                    invariant_summary.max_material_tolerance_ratio
                ),
                "max_finance_abs_residual": float(invariant_summary.max_finance_abs_residual),
                "max_finance_tolerance_ratio": float(invariant_summary.max_finance_tolerance_ratio),
                "checked_cells": int(invariant_summary.checked_cells),
                "per_ledger": dict(invariant_summary.per_ledger),
                "expired_leftover_by_cell": invariant_summary.expired_leftover_by_cell,
                "forcing_segment": str(forcing.segment[expected_tick]),
                "treasury_deposit_open": float(opening.treasury_deposit),
                "bank_reserves_open": [float(v) for v in opening.bank_reserves],
                "housing_completed": float(
                    np.sum(
                        np.asarray(state.dwelling_stock, dtype=np.float64) - opening.dwelling_stock
                    )
                ),
                "material_balance_residual": [float(v) for v in residual],
                "material_balance_tolerance": [float(v) for v in tolerance],
            }
            append_material_rows(
                history,
                state,
                flows,
                parameters,
                network,
                region_ids=list(spec.region_ids),
                commodity_ids=list(spec.commodities),
                digest=history.digest_chain,
                invariant_summary=invariant_dict,
                opening_stock=opening.stock_value,
            )
            aggregate_s += time.perf_counter() - started

            production_by_cell = np.bincount(
                index.b_cells,
                weights=index.b_coefficient * flows.activity_realized[index.b_rows],
                minlength=cell_commodity.size,
            )
            tallies["production"] += np.bincount(
                cell_commodity, weights=production_by_cell, minlength=g_count
            )
            tallies["imports"] += flows.imports
            tallies["exports"] += flows.cmea_exports + flows.convertible_exports
            tallies["consumption"] += (
                np.asarray(state.household_weight, dtype=np.float64)[:, None]
                * flows.household_realized
            ).sum(axis=0)
            tallies["desired"] += (
                np.asarray(state.household_weight, dtype=np.float64)[:, None]
                * flows.household_desired
            ).sum(axis=0)
            tallies["availability_unmet"] += (
                np.asarray(state.household_weight, dtype=np.float64)[:, None]
                * flows.household_availability_unmet
            ).sum(axis=0)
            weights = np.asarray(state.household_weight, dtype=np.float64)
            tallies["income"] += float(
                np.sum(
                    weights
                    * (
                        flows.household_wage_income
                        + flows.household_plot_income_formal
                        + flows.household_plot_income_direct
                        + flows.household_late_wage
                    )
                )
            )
            tallies["spending"] += float(np.sum(weights * flows.household_spending))
            tallies["forced"] += float(np.sum(weights * flows.household_forced_saving))
            tallies["voluntary"] += float(np.sum(weights * flows.household_voluntary_saving))
            tallies["bailout_ticks"] += int(
                np.any(np.asarray(flows.organization_bailout_granted) > 0.0)
            )
            tallies["blocked_total"] += float(np.sum(flows.financial_delivery_blocked))
            tallies["expired_services_total"] += float(flows.expired_services)
            tallies["max_material_abs_residual"] = max(
                tallies["max_material_abs_residual"],
                float(invariant_summary.max_material_abs_residual),
            )
            tallies["max_material_tolerance_ratio"] = max(
                tallies["max_material_tolerance_ratio"],
                float(invariant_summary.max_material_tolerance_ratio),
            )
            tallies["max_finance_abs_residual"] = max(
                tallies["max_finance_abs_residual"],
                float(invariant_summary.max_finance_abs_residual),
            )
            tallies["max_finance_tolerance_ratio"] = max(
                tallies["max_finance_tolerance_ratio"],
                float(invariant_summary.max_finance_tolerance_ratio),
            )

            boundary = state.completed_ticks
            paused_here = boundary == target_ticks and target_ticks < spec.ticks
            due = (
                (checkpoint_every > 0 and boundary % checkpoint_every == 0)
                or paused_here
                or (checkpoint_every > 0 and boundary == spec.ticks)
            )
            if due and boundary not in saved_boundaries:
                started = time.perf_counter()
                path = save_material_checkpoint(
                    checkpoint_dir(output_dir, boundary),
                    state,
                    network,
                    history,
                    rng,
                    {
                        "scenario": spec.model_dump(mode="json"),
                        "scenario_hash": compute_scenario_hash(spec),
                        "baseline_hash": baseline_hash,
                        "lock_hash": lock_hash,
                        "parameter_hash": parameter_hash,
                        "initial_recipe_hash": initial_recipe_hash,
                        "engine_version": MATERIAL_ENGINE_VERSION,
                        "state_version": MATERIAL_STATE_VERSION,
                        "input_artifact_hashes": dict(forcing.input_artifact_hashes),
                        "region_ids": list(spec.region_ids),
                        "commodity_ids": list(spec.commodities),
                        "last_completed_quarter": str(spec.start.advance(boundary - 1)),
                        "next_quarter": str(spec.start.advance(boundary)),
                        "source_run_id": run_id,
                    },
                )
                checkpoint_s += time.perf_counter() - started
                saved_boundaries.add(boundary)
                checkpoint_paths.append(str(path.relative_to(output_dir)))

        write_started = time.perf_counter()
        frames = history_frames(history)
        write_material_tables(output_dir, frames)
        final_stock = np.bincount(
            cell_commodity,
            weights=np.asarray(state.stock_value, dtype=np.float64),
            minlength=g_count,
        )
        by_commodity: dict[str, dict[str, float]] = {}
        for g, commodity_id in enumerate(network.commodity_ids):
            by_commodity[commodity_id] = {
                "production": float(tallies["production"][g]),
                "imports": float(tallies["imports"][g]),
                "exports": float(tallies["exports"][g]),
                "household_consumption": float(tallies["consumption"][g]),
                "household_desired": float(tallies["desired"][g]),
                "availability_unmet": float(tallies["availability_unmet"][g]),
                "final_stock": float(final_stock[g]),
            }
        household_budget = {
            "income": float(tallies["income"]),
            "spending": float(tallies["spending"]),
            "voluntary_saving": float(tallies["voluntary"]),
            "forced_saving": float(tallies["forced"]),
            "final_cash": float(
                np.sum(
                    np.asarray(state.household_weight, dtype=np.float64)
                    * np.asarray(state.household_cash, dtype=np.float64)
                )
            ),
        }
        summary_tallies = {
            "by_commodity": by_commodity,
            "household_budget": household_budget,
            "invariants": {
                "max_material_abs_residual": tallies["max_material_abs_residual"],
                "max_material_tolerance_ratio": tallies["max_material_tolerance_ratio"],
                "max_finance_abs_residual": tallies["max_finance_abs_residual"],
                "max_finance_tolerance_ratio": tallies["max_finance_tolerance_ratio"],
                "checked_ticks": int(state.completed_ticks),
            },
            "bailout_ticks": tallies["bailout_ticks"],
            "blocked_total": tallies["blocked_total"],
            "expired_services_total": tallies["expired_services_total"],
        }
        dimensions = {
            "households": int(state.household_id.shape[0]),
            "organizations": int(state.organization_id.shape[0]),
            "regions": int(state.dwelling_stock.shape[0]),
            "commodities": g_count,
            "K": int(network.input_cell.shape[0]),
            "D": int(network.demand_cell.shape[0]),
            "M": int(network.edge_source_cell.shape[0]),
            "S": int(cell_commodity.size),
            "P": int(network.activity_kind.shape[0]),
        }
        effective_scalar_updates = int(
            state.completed_ticks
            * (
                8 * dimensions["households"]
                + dimensions["K"]
                + dimensions["D"]
                + dimensions["M"]
                + dimensions["S"]
            )
        )
        performance: dict[str, Any] = {
            "preflight_wall_s": preflight_s,
            "init_wall_s": init_s,
            "compute_wall_s": compute_s,
            "gates_wall_s": gates_s,
            "digest_wall_s": digest_s,
            "aggregate_wall_s": aggregate_s,
            "checkpoint_wall_s": checkpoint_s,
            "total_wall_s": time.perf_counter() - run_started,
            "cpu_s": time.process_time() - cpu_started,
            "effective_scalar_updates": effective_scalar_updates,
        }
        for phase, seconds in phase_totals.items():
            performance[f"{phase}_wall_s"] = float(seconds)
        summary = _build_summary(
            run_id=run_id,
            spec=spec,
            state=state,
            history=history,
            frames=frames,
            rng=rng,
            parameter_hash=parameter_hash,
            initial_recipe_hash=initial_recipe_hash,
            input_artifact_hashes=dict(forcing.input_artifact_hashes),
            performance={
                **performance,
                "write_wall_s": time.perf_counter() - write_started,
            },
            checkpoint_paths=checkpoint_paths,
            research_warnings=list(contract.research_warnings),
            tallies=summary_tallies,
            dimensions=dimensions,
        )
        write_summary(summary, output_dir)
        parameters_declaration = spec.material_parameters
        recipe_declaration = spec.material_initial
        assert parameters_declaration is not None and recipe_declaration is not None
        (output_dir / "parameters.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "scenario_id": spec.scenario_id,
                    "parameter_hash": parameter_hash,
                    "declaration": parameters_declaration.model_dump(mode="json"),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (output_dir / "initial_recipe.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "scenario_id": spec.scenario_id,
                    "initial_recipe_hash": initial_recipe_hash,
                    "declaration": recipe_declaration.model_dump(mode="json"),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        hashes = hash_output_tree(output_dir)
        boundary = state.completed_ticks
        status: Literal["completed", "paused"] = "completed" if boundary == spec.ticks else "paused"
        final = finalize_manifest(
            running,
            status=status,
            output_hashes=hashes,
            rng_draws_count=rng.draws_count(),
            rng_draws_by_module=rng.draws_by_module(),
            stochastic_modules_active=[
                module for module, count in rng.draws_by_module().items() if count > 0
            ],
            deterministic_replay_digest=history.digest_chain,
            completed_ticks=boundary,
            last_completed_quarter=(str(spec.start.advance(boundary - 1)) if boundary else None),
        )
        write_manifest_atomic(output_dir, final)
        return final
    except Exception as exc:  # noqa: BLE001 - record evidence, then re-raise
        draws_by_module = rng.draws_by_module() if rng is not None else {}
        boundary = admitted_ticks
        failed = finalize_manifest(
            running,
            status="failed",
            output_hashes={},
            rng_draws_count=sum(draws_by_module.values()),
            rng_draws_by_module=draws_by_module,
            stochastic_modules_active=[
                module for module, count in draws_by_module.items() if count > 0
            ],
            deterministic_replay_digest="",
            failure_message=f"{type(exc).__name__}: {exc}",
            completed_ticks=boundary,
            last_completed_quarter=(str(spec.start.advance(boundary - 1)) if boundary else None),
        )
        try:
            write_manifest_atomic(output_dir, failed)
        except OSError:  # pragma: no cover - evidence already lost
            pass
        raise


__all__ = [
    "MATERIAL_ENGINE_VERSION",
    "MATERIAL_RUN_KIND",
    "advance_chain",
    "canonical_material_bytes",
    "initial_digest_chain",
    "load_material_forcing",
    "material_parameter_vector",
    "material_recipe_hash",
    "run_material",
    "tick_material",
]
