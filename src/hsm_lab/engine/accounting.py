"""Material-economy accounting: per-cell invariants and departments (P02).

Every check is per-cell over the canonical stock-cell catalog (organization
retail pools are checked per ``(region, commodity, stage)`` group because
regional sales are not decomposed per retail organization): a local ledger
error cannot hide behind a national aggregate. Violations raise
:class:`AccountingError` immediately with the quarter, ledger name, cell key,
both sides, residual and tolerance — the caller then fails the run closed.

Stock continuity is reconstructed from flows plus the network catalog so each
physical movement is counted exactly once:

* inflows — production ``B.T @ activity_realized``, realized imports into the
  treasury import-pool cells, edge deliveries whose destination is a stock
  cell;
* outflows — internal edge deliveries by source cell, export- and
  housing-purpose boundary edges by source cell, household acquisition
  channels (regional ``retail_sales``, plot self-use from the imputed value
  at the ready-food admin price, plot direct-market sales from late cash
  receipts), production input use scattered through ``input_cell``,
  logistics services consumed by delivered edges (attributed to the
  transport organization's output cell) and project installation
  (``organization_investment_completed`` x per-unit into the project WIP
  cells);
* services cells are non-stockable: they must close at zero and the sum of
  their unexpired leftovers reconciles with ``flows.expired_services``.

Boundary household edges mirror ``retail_sales``/the plot direct channel and
export edges mirror the trade arrays; both equivalences are gated so the
edge view and the channel view can never drift apart.

Department attribution maps delivery purposes to departments exactly as
declared in plan section 5 (a convention over the purpose vocabulary, never
a permanent commodity label): intermediate, investment, procurement and
private-plot deliveries attribute output to Department I; housing, retail
and the plot household channels to Department II; export deliveries to the
exports column; services output splits into productive/household service
use; production without any same-tick outflow is unclassified.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from dataclasses import fields as dataclass_fields
from typing import TYPE_CHECKING, Any

import numpy as np

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.contract.material import (
    ORGANIZATION_TYPE_ORDER,
    PURPOSE_CODES,
    STAGE_CODES,
    MaterialParameters,
    OrganizationType,
    RoutePurpose,
)
from hsm_lab.engine.finance import (
    CMEA_CURRENCY,
    DOMESTIC_CURRENCY,
    USD_CURRENCY,
    AccountKind,
    bank_account_ids,
    cmea_clearing_account_floor,
    household_account_ids,
    organization_account_ids,
    quarter_domestic_credit_rate,
    treasury_account_id,
    treasury_receivable_account_id,
    treasury_term_account_id,
)
from hsm_lab.engine.state import (
    POOL_CODES,
    CmeaClearingRegimeState,
    MaterialForcing,
    MaterialPrices,
    MaterialState,
    MaterialStockSnapshot,
    MaterialTickFlows,
    build_material_prices,
)
from hsm_lab.engine.trade import (
    apply_clearing_events,
    apply_receivable_events,
    channel_prices,
    clearing_delivery_entries,
    clearing_event_journal_rows,
    clearing_import_allocation,
    clearing_journal_rows,
    clearing_overdue,
    receivable_journal_rows,
    resolve_export_contract,
    validate_clearing_book,
    validate_clearing_policy,
    validate_export_policy,
    validate_receivable_book,
)

if TYPE_CHECKING:  # pragma: no cover - annotation-only; avoids an import cycle
    from hsm_lab.engine.network import MaterialNetwork

ATOL = 1e-9
RTOL = 1e-10

_D2_FLOW_FIELDS: tuple[str, ...] = (
    "export_receivable_opened_usd",
    "export_receivable_opened_cmea",
    "export_receivable_received_usd",
    "export_receivable_received_cmea",
    "export_receivable_recovered_usd",
    "export_receivable_recovered_cmea",
    "export_receivable_written_off_usd",
    "export_receivable_written_off_cmea",
    "export_receivable_loss_provision_usd",
    "export_receivable_loss_provision_cmea",
    "export_receivable_provision_released_usd",
    "export_receivable_provision_released_cmea",
    "export_receivable_balance_usd",
    "export_receivable_balance_cmea",
    "export_receivable_overdue_usd",
    "export_receivable_overdue_cmea",
)
_D2_JOURNAL_KINDS: frozenset[str] = frozenset(
    {
        "export_receivable_delivery",
        "export_receivable_receipt",
        "export_receivable_loss",
        "export_receivable_writeoff",
        "export_receivable_recovery_restore",
        "export_receivable_recovery_receipt",
        "export_receivable_recovery_release",
    }
)

_D3_JOURNAL_KINDS: frozenset[str] = frozenset(
    {
        "cmea_clearing_import",
        "cmea_clearing_export",
        "cmea_clearing_settle",
        "cmea_clearing_transfer",
    }
)

_PER_UNIT_DEFAULT = 0.25  # plan default when parameters are unavailable

# Purpose codes used by the reconstruction.
_P_INTERMEDIATE = PURPOSE_CODES[RoutePurpose.INTERMEDIATE]
_P_INVESTMENT = PURPOSE_CODES[RoutePurpose.INVESTMENT]
_P_HOUSING = PURPOSE_CODES[RoutePurpose.HOUSING]
_P_PROCUREMENT = PURPOSE_CODES[RoutePurpose.PROCUREMENT]
_P_RETAIL = PURPOSE_CODES[RoutePurpose.RETAIL]
_P_PRIVATE_PLOT = PURPOSE_CODES[RoutePurpose.PRIVATE_PLOT]
_P_EXPORT_CMEA = PURPOSE_CODES[RoutePurpose.EXPORT_CMEA]
_P_EXPORT_CONVERTIBLE = PURPOSE_CODES[RoutePurpose.EXPORT_CONVERTIBLE]
_P_HOUSEHOLD = PURPOSE_CODES[RoutePurpose.HOUSEHOLD]

_POOL_WHOLESALE = POOL_CODES["wholesale"]
_POOL_RETAIL = POOL_CODES["retail"]

_KIND_ORG = 0
_KIND_PLOT = 1
_KIND_IMPORT = 3

_KIND_NAMES = {0: "org", 1: "plot", 2: "project", 3: "treasury_import"}
_POOL_NAMES = {code: name for name, code in POOL_CODES.items()}
_STAGE_NAMES = {code: name for name, code in STAGE_CODES.items()}
_PURPOSE_NAMES = {code: purpose.value for purpose, code in PURPOSE_CODES.items()}

# Identity (never axis-position) based commodity semantics; declared
_CAPITAL_ID = "capital_goods"


def _ephemeral_commodity_ids(network: Any) -> np.ndarray:
    """Commodity indices that are non-stockable (their cells must close at zero)."""
    from hsm_lab.contract.material import commodity_spec

    return np.asarray(
        [g for g, cid in enumerate(network.commodity_ids) if not commodity_spec(cid).stockable],
        dtype=np.int64,
    )


def _ephemeral_commodity_mask(network: Any, cell_commodity: np.ndarray) -> np.ndarray:
    """Cells of non-stockable commodities (they must close at zero)."""
    ephemeral = _ephemeral_commodity_ids(network)
    if ephemeral.size == 0:
        return np.zeros(cell_commodity.shape[0], dtype=bool)
    return np.isin(cell_commodity, ephemeral)


def _role_index(network: Any, role: str) -> int:
    """Commodity-axis index of the first channel in a catalog role (-1 none)."""
    from hsm_lab.contract.material import get_catalog

    catalog = get_catalog(network.catalog_id)
    for commodity_id in catalog.with_role(role):
        if commodity_id in network.commodity_ids:
            return network.commodity_ids.index(commodity_id)
    return -1


def _role_id(network: Any, role: str) -> str | None:
    """First commodity id in a catalog role (None if the role is absent)."""
    from hsm_lab.contract.material import get_catalog

    ids = get_catalog(network.catalog_id).with_role(role)
    return ids[0] if ids else None


def _household_parent_ids(network: Any) -> set[str]:
    """Commodity ids the network builds household demand cells for."""
    from hsm_lab.contract.material import get_catalog

    return set(get_catalog(network.catalog_id).household_channel_ids)


_FARM_TYPE_CODES = frozenset(
    ORGANIZATION_TYPE_ORDER.index(t)
    for t in (OrganizationType.AGRICULTURAL_COOPERATIVE, OrganizationType.STATE_FARM)
)

# Axis-index fields carrying the -1 sentinel by contract.
_SIGNED_INDEX_FIELDS = frozenset(
    {
        "organization_technology",
        "organization_activity",
        "organization_bank",
        "plot_activity",
    }
)

# Residual snapshot slots are signed diagnostics, never quantity ledgers.
_SIGNED_RESIDUAL_FIELDS = frozenset(
    {
        "material_balance_residual",
        "material_balance_tolerance",
        "finance_balance_residual",
        "finance_balance_tolerance",
    }
)


#: Signed P03 household flow diagnostics (welfare index and entitlement gap may
#: be negative; they are state/utility magnitudes, not quantity ledgers).
_SIGNED_FLOW_FIELDS = frozenset(
    {"household_welfare_net", "entitlement_gap", "organization_sbc_transfer"}
)


class AccountingError(ResearchGateError):
    """A stock-flow or cash invariant violation; the run must fail closed."""


# ---------------------------------------------------------------------------
# Shared helpers (toy-4 accounting style, behaviour kept verbatim).
# ---------------------------------------------------------------------------


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
    labels: list[str] | None = None,
) -> tuple[float, float]:
    """Vectorized cell-wise equality within per-cell tolerance.

    Non-finite operands are violations, never silently-comparing values: NaN
    residuals compare False against any tolerance and must fail closed.
    """
    lhs = np.ascontiguousarray(lhs, dtype=np.float64)
    rhs = np.ascontiguousarray(rhs, dtype=np.float64)
    if lhs.shape != rhs.shape:
        raise AccountingError(
            f"accounting shape mismatch in {quarter} ledger={ledger}: {lhs.shape} vs {rhs.shape}"
        )
    if not (np.all(np.isfinite(lhs)) and np.all(np.isfinite(rhs))):
        index = int(np.argmax(~(np.isfinite(lhs) & np.isfinite(rhs)).reshape(-1)))
        _fail(
            quarter,
            ledger,
            labels[index] if labels is not None else _cell_key(ledger, index, lhs.shape),
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
            labels[index] if labels is not None else _cell_key(ledger, index, lhs.shape),
            float(lhs.reshape(-1)[index]),
            float(rhs.reshape(-1)[index]),
        )
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(tol > 0, np.abs(residual) / tol, 0.0)
    return (
        float(np.max(np.abs(residual))) if residual.size else 0.0,
        float(np.max(ratio)) if ratio.size else 0.0,
    )


def _compare_at_most(
    quarter: str,
    ledger: str,
    lhs: np.ndarray,
    rhs: np.ndarray,
    labels: list[str] | None = None,
) -> tuple[float, float]:
    """Vectorized cell-wise ``lhs <= rhs`` within per-cell tolerance."""
    lhs = np.ascontiguousarray(lhs, dtype=np.float64)
    rhs = np.ascontiguousarray(rhs, dtype=np.float64)
    if lhs.shape != rhs.shape:
        raise AccountingError(
            f"accounting shape mismatch in {quarter} ledger={ledger}: {lhs.shape} vs {rhs.shape}"
        )
    if not (np.all(np.isfinite(lhs)) and np.all(np.isfinite(rhs))):
        index = int(np.argmax(~(np.isfinite(lhs) & np.isfinite(rhs)).reshape(-1)))
        _fail(
            quarter,
            ledger,
            labels[index] if labels is not None else _cell_key(ledger, index, lhs.shape),
            float(lhs.reshape(-1)[index]),
            float(rhs.reshape(-1)[index]),
        )
    residual = lhs - rhs
    tol = np.asarray(tolerance_for(lhs, rhs), dtype=np.float64)
    bad = residual > tol
    if bad.any():
        index = int(np.argmax(bad))
        _fail(
            quarter,
            ledger,
            labels[index] if labels is not None else _cell_key(ledger, index, lhs.shape),
            float(lhs.reshape(-1)[index]),
            float(rhs.reshape(-1)[index]),
        )
    excess = np.maximum(residual, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(tol > 0, excess / tol, 0.0)
    return (
        float(np.max(excess)) if excess.size else 0.0,
        float(np.max(ratio)) if ratio.size else 0.0,
    )


def _check_array(
    values: np.ndarray, *, quarter: str, ledger: str, non_negative: bool = True
) -> None:
    values = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise AccountingError(f"non-finite value in {quarter} ledger={ledger} shape={values.shape}")
    if non_negative and values.size and float(np.min(values)) < -ATOL:
        raise AccountingError(
            f"negative value {float(np.min(values))!r} in {quarter} "
            f"ledger={ledger} shape={values.shape}"
        )


def _require(condition: bool, quarter: str, message: str) -> None:
    if not condition:
        raise AccountingError(f"accounting structure violation in {quarter}: {message}")


def _check_unit_interval(
    quarter: str, ledger: str, values: np.ndarray, labels: list[str] | None = None
) -> tuple[float, float]:
    values = np.asarray(values, dtype=np.float64)
    return _compare_cells(quarter, ledger, values, np.clip(values, 0.0, 1.0), labels=labels)


def _accumulate(
    per_ledger: dict[str, tuple[float, float]], ledger: str, residual: float, ratio: float
) -> None:
    previous = per_ledger.get(ledger)
    if previous is None:
        per_ledger[ledger] = (residual, ratio)
    else:
        per_ledger[ledger] = (max(previous[0], residual), max(previous[1], ratio))


# ---------------------------------------------------------------------------
# Cell / axis labels (built once per check; only read when a gate fails).
# ---------------------------------------------------------------------------


def _stock_cell_labels(network: MaterialNetwork) -> list[str]:
    kinds = np.asarray(network.cell_owner_kind, dtype=np.int64)
    owners = np.asarray(network.cell_owner_id, dtype=np.int64)
    regions = np.asarray(network.cell_region, dtype=np.int64)
    pools = np.asarray(network.cell_pool, dtype=np.int64)
    commodities = np.asarray(network.cell_commodity, dtype=np.int64)
    stages = np.asarray(network.cell_stage, dtype=np.int64)
    commodity_ids = network.commodity_ids
    return [
        f"cell[{_KIND_NAMES.get(int(kinds[i]), int(kinds[i]))}/{int(owners[i])}"
        f"|r{int(regions[i])}|{_POOL_NAMES.get(int(pools[i]), int(pools[i]))}"
        f"|{commodity_ids[int(commodities[i])]}"
        f"|{_STAGE_NAMES.get(int(stages[i]), int(stages[i]))}]"
        for i in range(int(kinds.shape[0]))
    ]


def _purpose_labels(network: MaterialNetwork) -> list[str]:
    return [
        f"demand[{index}|{_PURPOSE_NAMES.get(int(code), int(code))}]"
        for index, code in enumerate(np.asarray(network.demand_purpose, dtype=np.int64))
    ]


def _edge_labels(network: MaterialNetwork) -> list[str]:
    return [f"edge[{int(edge_id)}]" for edge_id in np.asarray(network.edge_id)]


# ---------------------------------------------------------------------------
# Continuity reconstruction.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Continuity:
    """Per-cell reconstruction of one tick's stock movements."""

    production: np.ndarray  # (S,) B.T @ realized
    imports_in: np.ndarray  # (S,) channel imports into treasury pool cells
    edge_receipts: np.ndarray  # (S,) deliveries with a stock-cell destination
    edge_out_internal: np.ndarray  # (S,) deliveries leaving the source (dest >= 0)
    edge_out_all: np.ndarray  # (S,) every delivery leaving the source
    exports_out: np.ndarray  # (S,) export boundary deliveries by source
    housing_out: np.ndarray  # (S,) housing boundary deliveries by source
    household_edges_out: np.ndarray  # (S,) household boundary edges by source
    production_used: np.ndarray  # (S,) K-input consumption by input cell
    production_row_delivered: np.ndarray  # (S,) production-row deliveries by dest
    logistics_used: np.ndarray  # (S,) edge logistics services by transport cell
    project_installed: np.ndarray  # (S,) completed x per-unit into WIP cells
    household_channel: np.ndarray  # (S,) plot self-use + direct market outflow
    services_cells: np.ndarray  # (S,) bool services_transport cells
    retail_org_cells: np.ndarray  # (S,) bool organization retail pool cells
    retail_expected: np.ndarray  # (S,) group expected close (retail cells)
    retail_close: np.ndarray  # (S,) group actual close (retail cells)
    expected_close: np.ndarray  # (S,) expected closing stock (before expiry)
    services_leftover: np.ndarray  # (S,) expiry needed so services close at 0
    stock_residual: np.ndarray  # (S,) continuity residual (retail groups broadcast)
    stock_tolerance: np.ndarray  # (S,) matching tolerance


def _reconstruct(
    opening: MaterialStockSnapshot,
    state: MaterialState,
    flows: MaterialTickFlows,
    network: MaterialNetwork,
    prices: MaterialPrices | None,
    parameters: MaterialParameters | None,
) -> _Continuity:
    quarter = flows.quarter
    S = int(np.asarray(network.cell_owner_kind).shape[0])
    K = int(np.asarray(network.input_cell).shape[0])
    G = len(network.commodity_ids)
    R = int(state.dwelling_stock.shape[0])

    if prices is None:
        prices = MaterialPrices(standard=np.ones(G, dtype=np.float64), food_raw=1.0)

    open_ = np.asarray(opening.stock_value, dtype=np.float64)
    close = np.asarray(state.stock_value, dtype=np.float64)
    realized = np.asarray(flows.activity_realized, dtype=np.float64)
    production = np.asarray(network.B.T @ realized).ravel().astype(np.float64)

    src = np.asarray(network.edge_source_cell, dtype=np.int64)
    dst = np.asarray(network.edge_destination_cell, dtype=np.int64)
    purpose = np.asarray(network.edge_purpose, dtype=np.int64)
    delivered_edges = np.asarray(flows.edge_delivered, dtype=np.float64)
    _require(
        bool(np.all((src >= 0) & (src < S))),
        quarter,
        "route edge source cell index outside the stock catalog",
    )
    _require(
        bool(np.all((dst >= -1) & (dst < S))),
        quarter,
        "route edge destination cell index outside the stock catalog",
    )
    demand_cells = np.asarray(network.demand_cell, dtype=np.int64)
    _require(
        bool(np.all((demand_cells >= -1) & (demand_cells < S))),
        quarter,
        "demand destination cell index outside the stock catalog",
    )

    imports_in = np.zeros(S, dtype=np.float64)
    import_cells = np.asarray(network.import_pool_cell, dtype=np.int64)
    importable = import_cells >= 0
    if bool(np.any(importable)):
        imports_in[import_cells[importable]] = (
            np.asarray(flows.cmea_imports, dtype=np.float64)[importable]
            + np.asarray(flows.convertible_imports, dtype=np.float64)[importable]
        )

    internal = dst >= 0
    edge_receipts = np.bincount(dst[internal], weights=delivered_edges[internal], minlength=S)
    edge_out_internal = np.bincount(src[internal], weights=delivered_edges[internal], minlength=S)
    edge_out_all = np.bincount(src, weights=delivered_edges, minlength=S)

    def _boundary_out(code: int) -> np.ndarray:
        mask = purpose == code
        if bool(np.any(mask)):
            return np.bincount(src[mask], weights=delivered_edges[mask], minlength=S)
        return np.zeros(S, dtype=np.float64)

    exports_out = _boundary_out(_P_EXPORT_CMEA) + _boundary_out(_P_EXPORT_CONVERTIBLE)
    housing_out = _boundary_out(_P_HOUSING)
    household_edges_out = _boundary_out(_P_HOUSEHOLD)

    # Production input consumption, scattered onto the input stock cells.
    input_index = np.asarray(network.demand_input_index, dtype=np.int64)
    production_rows = input_index >= 0
    k_rows = input_index[production_rows]
    _require(
        int(np.unique(k_rows).size) == int(k_rows.size),
        quarter,
        "production demand rows are not bijective with the K input axis",
    )
    k_used = np.zeros(K, dtype=np.float64)
    k_used[k_rows] = np.asarray(flows.used, dtype=np.float64)[production_rows]
    input_cells = np.asarray(network.input_cell, dtype=np.int64)
    _require(
        bool(np.all((input_cells >= 0) & (input_cells < S))),
        quarter,
        "technology input cell index outside the stock catalog",
    )
    production_used = np.bincount(input_cells, weights=k_used, minlength=S)
    production_row_delivered = np.bincount(
        demand_cells[production_rows],
        weights=np.asarray(flows.delivered, dtype=np.float64)[production_rows],
        minlength=S,
    )

    # Logistics services are consumed out of the transport org's output cell.
    logistics_used = np.zeros(S, dtype=np.float64)
    transport_orgs = np.asarray(network.edge_transport_org, dtype=np.int64)
    org_output = np.asarray(network.org_output_cell, dtype=np.int64)
    served = (transport_orgs >= 0) & (transport_orgs < org_output.shape[0])
    if bool(np.any(served)):
        cells = org_output[transport_orgs[served]]
        ok = cells >= 0
        if bool(np.any(ok)):
            np.add.at(
                logistics_used,
                cells[ok],
                np.asarray(flows.edge_service_used, dtype=np.float64)[served][ok],
            )

    # Project installation into the organization WIP cells.
    completed = np.asarray(flows.organization_investment_completed, dtype=np.float64)
    capital_unit = (
        float(parameters.capacity_capital_goods_per_unit)
        if parameters is not None
        else _PER_UNIT_DEFAULT
    )
    construction_unit = (
        float(parameters.capacity_construction_per_unit)
        if parameters is not None
        else _PER_UNIT_DEFAULT
    )
    project_installed = np.zeros(S, dtype=np.float64)
    capital_cells = np.asarray(network.project_capital_cell, dtype=np.int64)
    construction_wip_cells = np.asarray(network.project_construction_cell, dtype=np.int64)
    capital_ok = capital_cells >= 0
    construction_ok = construction_wip_cells >= 0
    if bool(np.any(capital_ok)):
        np.add.at(
            project_installed,
            capital_cells[capital_ok],
            completed[capital_ok] * capital_unit,
        )
    if bool(np.any(construction_ok)):
        np.add.at(
            project_installed,
            construction_wip_cells[construction_ok],
            completed[construction_ok] * construction_unit,
        )

    # Household acquisition channels outside the organization retail pools:
    # plot self-use (imputed value at the ready-food admin price) and the
    # plot direct market (late cash receipts at the same admin price).
    household_channel = np.zeros(S, dtype=np.float64)
    food_g = _role_index(network, "food")
    if food_g >= 0:
        ready_price = float(prices.standard[food_g])
        _require(
            ready_price > 0.0,
            quarter,
            "ready-food admin price must be positive to value plot channels",
        )
        weight = np.asarray(state.household_weight, dtype=np.float64)
        region = np.asarray(state.household_region, dtype=np.int64)
        self_use_value = np.bincount(
            region,
            weights=weight * np.asarray(flows.household_self_use, dtype=np.float64),
            minlength=R,
        )
        direct_value = np.bincount(
            region,
            weights=weight * np.asarray(flows.household_plot_income_direct, dtype=np.float64),
            minlength=R,
        )
        plot_self = np.asarray(network.plot_ready_self_cell, dtype=np.int64)
        plot_market = np.asarray(network.plot_ready_market_cell, dtype=np.int64)
        self_ok = plot_self >= 0
        market_ok = plot_market >= 0
        if bool(np.any(self_ok)):
            household_channel[plot_self[self_ok]] += self_use_value[self_ok] / ready_price
        if bool(np.any(market_ok)):
            household_channel[plot_market[market_ok]] += direct_value[market_ok] / ready_price
    services_g = _role_index(network, "service")
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_pool = np.asarray(network.cell_pool, dtype=np.int64)
    cell_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_region = np.asarray(network.cell_region, dtype=np.int64)
    cell_stage = np.asarray(network.cell_stage, dtype=np.int64)
    services_cells = _ephemeral_commodity_mask(network, cell_commodity)
    retail_org_cells = (cell_pool == _POOL_RETAIL) & (cell_kind == _KIND_ORG)

    inflow = open_ + production + imports_in + edge_receipts
    outflow = (
        edge_out_internal
        + household_edges_out
        + exports_out
        + housing_out
        + production_used
        + logistics_used
        + project_installed
        + household_channel
        + np.asarray(flows.second_input_used, dtype=np.float64)
    )
    expected_close = inflow - outflow

    stock_residual = np.where(services_cells, close, expected_close - close)
    stock_tolerance = np.where(
        services_cells,
        np.asarray(tolerance_for(close, np.zeros_like(close)), dtype=np.float64),
        np.asarray(tolerance_for(expected_close, close), dtype=np.float64),
    )
    retail_expected = expected_close.copy()
    retail_close = close.copy()
    if bool(np.any(retail_org_cells)):
        # Organization retail pools close via the regional sales channel;
        # (region, commodity, stage) is the finest decomposable unit.
        group_count = R * G * 3
        retail = np.nonzero(retail_org_cells)[0]
        keys = ((cell_region * G + cell_commodity) * 3 + cell_stage)[retail]
        open_g = np.bincount(keys, weights=open_[retail], minlength=group_count)
        receipts_g = np.bincount(keys, weights=edge_receipts[retail], minlength=group_count)
        close_g = np.bincount(keys, weights=close[retail], minlength=group_count)
        sales_g = np.zeros(group_count, dtype=np.float64)
        retail_sales = np.asarray(flows.retail_sales, dtype=np.float64)
        retail_cell_map = np.asarray(network.retail_cell, dtype=np.int64)
        mapped = retail_cell_map >= 0
        if bool(np.any(mapped)):
            sales_keys = (
                np.broadcast_to(np.arange(R, dtype=np.int64)[:, None], (R, G))[mapped] * G
                + np.broadcast_to(np.arange(G, dtype=np.int64)[None, :], (R, G))[mapped]
            ) * 3 + cell_stage[retail_cell_map[mapped]]
            sales_g = np.bincount(sales_keys, weights=retail_sales[mapped], minlength=group_count)
        second_used_g = np.bincount(
            keys,
            weights=np.asarray(flows.second_input_used, dtype=np.float64)[retail],
            minlength=group_count,
        )
        expected_g = open_g + receipts_g - sales_g - second_used_g
        group_residual = expected_g[keys] - close_g[keys]
        stock_residual[retail] = group_residual
        stock_tolerance[retail] = np.asarray(
            tolerance_for(expected_g[keys], close_g[keys]), dtype=np.float64
        )
        retail_expected[retail] = expected_g[keys]
        retail_close[retail] = close_g[keys]

    # Services are ephemeral: retail household service use drains the region's
    # same-tick service pool before the residual is expired. Retail cells are
    # pooled by region for this channel; allocate the remaining expiry across
    # that region's service cells without making any cell negative.
    # Ephemeral (non-stockable) cells: the modelled leftover is taken raw, so
    # the reconciliation with ``flows.expired_services`` is exact.  Per-cell
    # non-negativity is a separate property (cross-cell pool attribution) and is
    # reported, not silently clipped.
    pool_draw_at_cell = np.asarray(
        getattr(flows, "service_pool_draw_at_cell", np.zeros(S, dtype=np.float64)),
        dtype=np.float64,
    )
    pool_credit_at_cell = np.asarray(
        getattr(flows, "service_pool_credit_at_cell", np.zeros(S, dtype=np.float64)),
        dtype=np.float64,
    )
    # Same-quarter clearing entries (P05 §0.4): the consumer cell was charged
    # its own stock only (add back the pool-paid part ``S_c``), while the
    # producer cell's credit was reduced by ``N_c`` (subtract it).
    expected_services = expected_close + pool_draw_at_cell - pool_credit_at_cell
    services_leftover = np.where(services_cells, expected_services, 0.0)
    if services_g >= 0:
        regional_services = services_cells & (cell_region >= 0)
        available_by_region = np.bincount(
            cell_region[regional_services],
            weights=services_leftover[regional_services],
            minlength=R,
        )
        ephemeral_columns = _ephemeral_commodity_ids(network)
        service_sales = np.asarray(flows.retail_sales, dtype=np.float64)[
            :, ephemeral_columns
        ].sum(axis=1)
        # ``expected_close`` already nets the household service deliveries out
        # through ``household_edges_out``; the gross availability those sales
        # drew on is the remaining stock plus the sales themselves.
        _compare_at_most(
            quarter,
            "services_household_use_le_available",
            service_sales,
            available_by_region + service_sales,
            labels=[f"region[{region_id}]" for region_id in network.region_ids],
        )

    return _Continuity(
        production=production,
        imports_in=imports_in,
        edge_receipts=edge_receipts,
        edge_out_internal=edge_out_internal,
        edge_out_all=edge_out_all,
        exports_out=exports_out,
        housing_out=housing_out,
        household_edges_out=household_edges_out,
        production_used=production_used,
        production_row_delivered=production_row_delivered,
        logistics_used=logistics_used,
        project_installed=project_installed,
        household_channel=household_channel,
        services_cells=services_cells,
        retail_org_cells=retail_org_cells,
        retail_expected=retail_expected,
        retail_close=retail_close,
        expected_close=expected_close,
        services_leftover=services_leftover,
        stock_residual=stock_residual,
        stock_tolerance=stock_tolerance,
    )


# ---------------------------------------------------------------------------
# Residual helpers the kernel calls to fill the flow snapshot slots.
# ---------------------------------------------------------------------------


def material_balance_residuals(
    opening: MaterialStockSnapshot,
    state: MaterialState,
    flows: MaterialTickFlows,
    network: MaterialNetwork,
    *,
    prices: MaterialPrices | None = None,
    parameters: MaterialParameters | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-cell continuity residual ``(S,)`` plus matching tolerances.

    Organization retail pools carry their ``(region, commodity, stage)``
    group residual (regional sales are not decomposed per retail org);
    services cells carry their deviation from the mandatory zero closing
    stock.  ``prices``/``parameters`` default to the plan constants and must
    be supplied whenever the scenario declares private-plot food channels or
    non-default investment per-unit coefficients.
    """
    if prices is None and bool(
        np.any(np.asarray(network.plot_ready_self_cell, dtype=np.int64) >= 0)
    ):
        raise AccountingError(
            "material_balance_residuals requires prices when the network "
            "declares private-plot food channels"
        )
    continuity = _reconstruct(opening, state, flows, network, prices, parameters)
    return continuity.stock_residual.copy(), continuity.stock_tolerance.copy()


def finance_balance_residuals(
    state: MaterialState, flows: MaterialTickFlows
) -> tuple[np.ndarray, np.ndarray]:
    """Bank-sheet and deposit-composition residuals with tolerances.

    Pure measurement (no gate): ``assets - liabilities`` then
    ``deposit_liability - (weighted household cash + organization cash +
    treasury)`` per bank.  The domestic-currency Treasury fiscal account is
    held at dense bank index 0; households bank at ``region % B`` and
    organizations at their declared dense bank index.
    """
    banks = int(state.bank_reserves.shape[0])
    loan = np.asarray(state.bank_loan_asset, dtype=np.float64)
    receivable = np.asarray(state.bank_interest_receivable, dtype=np.float64)
    reserves = np.asarray(state.bank_reserves, dtype=np.float64)
    deposits = np.asarray(state.bank_deposit_liability, dtype=np.float64)
    equity = np.asarray(state.bank_equity, dtype=np.float64)
    assets = loan + receivable + reserves
    liabilities = deposits + equity

    sources = np.zeros(banks, dtype=np.float64)
    if banks:
        weight = np.asarray(state.household_weight, dtype=np.float64)
        household_cash = np.asarray(state.household_cash, dtype=np.float64)
        household_bank = np.asarray(state.household_region, dtype=np.int64) % banks
        sources += np.bincount(household_bank, weights=weight * household_cash, minlength=banks)
        org_bank = np.asarray(state.organization_bank, dtype=np.int64)
        borrower = org_bank >= 0
        if bool(np.any(borrower)):
            sources += np.bincount(
                org_bank[borrower],
                weights=np.asarray(state.organization_cash, dtype=np.float64)[borrower],
                minlength=banks,
            )
        sources[0] += float(state.treasury_deposit)

    residual = np.concatenate([assets - liabilities, deposits - sources])
    tolerance = np.concatenate(
        [
            np.asarray(tolerance_for(assets, liabilities), dtype=np.float64),
            np.asarray(tolerance_for(deposits, sources), dtype=np.float64),
        ]
    )
    return residual, tolerance


# ---------------------------------------------------------------------------
# Invariant summary and the outer admission gate.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InvariantSummary:
    """Maxima of every per-cell gate; ``per_ledger`` maps ledger name to
    ``(max absolute residual, max tolerance ratio)``."""

    max_material_abs_residual: float
    max_material_tolerance_ratio: float
    max_finance_abs_residual: float
    max_finance_tolerance_ratio: float
    checked_cells: int
    per_ledger: dict[str, tuple[float, float]] = field(default_factory=dict)
    # Exact expiry sink the kernel applied this tick, per stock cell.  It is the
    # authoritative per-commodity/per-region split of ``flows.expired_services``
    # and the only source publishers may use: re-deriving it from a lighter
    # ledger misses the non-stockable opening stock and clips per cell.
    expired_leftover_by_cell: np.ndarray = field(
        default_factory=lambda: np.zeros(0, dtype=np.float64)
    )


def _sweep_flows(flows: MaterialTickFlows, quarter: str) -> None:
    """Every flow array is finite; quantity/money flows are non-negative."""
    for field_info in dataclass_fields(MaterialTickFlows):
        value = getattr(flows, field_info.name)
        if not isinstance(value, np.ndarray):
            continue
        _check_array(
            value,
            quarter=quarter,
            ledger=f"flows.{field_info.name}",
            non_negative=field_info.name not in (_SIGNED_RESIDUAL_FIELDS | _SIGNED_FLOW_FIELDS),
        )
    for name in (
        "cmea_import_payment",
        "cmea_export_receipt",
        "usd_import_payment",
        "usd_export_receipt",
        "usd_interest_paid",
        "usd_interest_accrued",
        "usd_principal_paid",
        "usd_loan_drawn",
        "treasury_loan_drawn",
        "treasury_principal_paid",
        "treasury_interest_due",
        "treasury_interest_paid",
        "treasury_export_outlay",
        "expired_services",
    ):
        value = float(getattr(flows, name))
        if not math.isfinite(value) or value < -ATOL:
            raise AccountingError(
                f"invalid flows.{name}={value!r} in {quarter} (must be finite, non-negative)"
            )
    if flows.official_fx_translation is not None:
        value = float(flows.official_fx_translation)
        if not math.isfinite(value) or value < -ATOL:
            raise AccountingError(f"invalid flows.official_fx_translation={value!r} in {quarter}")


def _sweep_arrays(obj: MaterialState | MaterialStockSnapshot, quarter: str, prefix: str) -> None:
    """State/snapshot arrays are finite; quantity arrays are non-negative.

    Axis-index fields carry ``-1`` sentinels by contract and stay signed.
    """
    for field_info in dataclass_fields(obj):
        value = getattr(obj, field_info.name)
        if isinstance(value, np.ndarray):
            _check_array(
                value,
                quarter=quarter,
                ledger=f"{prefix}.{field_info.name}",
                non_negative=field_info.name not in _SIGNED_INDEX_FIELDS,
            )


def _check_journal(
    flows: MaterialTickFlows, quarter: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Structural journal gates; returns typed columns for cross-checks."""
    columns = (
        flows.journal_kind,
        flows.journal_tick,
        flows.journal_debit,
        flows.journal_credit,
        flows.journal_currency,
        flows.journal_amount,
        flows.journal_org,
        flows.journal_leg,
        flows.journal_event,
    )
    lengths = {len(column) for column in columns}
    _require(
        len(lengths) == 1,
        quarter,
        f"journal column lengths differ: {sorted(lengths)}",
    )
    kind = np.asarray(flows.journal_kind, dtype=object)
    debit = np.asarray(flows.journal_debit, dtype=np.int64)
    credit = np.asarray(flows.journal_credit, dtype=np.int64)
    amount = np.asarray(flows.journal_amount, dtype=np.float64)
    currency = np.asarray(flows.journal_currency, dtype=object)
    leg = np.asarray(flows.journal_leg, dtype=np.int64)
    count = int(kind.shape[0])
    if count == 0:
        return kind, debit, credit, amount, currency
    _check_array(amount, quarter=quarter, ledger="journal_amount")
    tick = np.asarray(flows.journal_tick, dtype=np.int64)
    _require(
        bool(np.all(tick == flows.tick)),
        quarter,
        "journal legs must all carry the flow tick",
    )
    _require(int(leg[0]) == 0, quarter, "first journal leg must start at index 0")
    if count > 1:
        restart = leg[1:] == 0
        sequential = np.diff(leg) == 1
        _require(
            bool(np.all(restart | sequential)),
            quarter,
            "journal leg indices must restart at 0 and increment by 1 per transaction",
        )
    starts = np.nonzero(leg == 0)[0]
    run_id = np.cumsum(leg == 0) - 1
    _require(
        bool(np.all(currency == currency[starts][run_id])),
        quarter,
        "a journal transaction mixes currencies",
    )
    debit_side = np.where(debit >= 0, amount, 0.0)
    credit_side = np.where(credit >= 0, amount, 0.0)
    debit_totals = np.add.reduceat(debit_side, starts)
    credit_totals = np.add.reduceat(credit_side, starts)
    mismatch = np.abs(debit_totals - credit_totals) > ATOL
    if bool(np.any(mismatch)):
        run = int(np.argmax(mismatch))
        _fail(
            quarter,
            "journal_transaction_balance",
            f"transaction_at_row[{int(starts[run])}]",
            float(debit_totals[run]),
            float(credit_totals[run]),
        )
    return kind, debit, credit, amount, currency


def check_material_invariants(
    opening: MaterialStockSnapshot,
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    network: MaterialNetwork,
    *,
    controls: Any = None,
    forcing: MaterialForcing | None = None,
    export_receivable_policy: Any = None,
    cmea_clearing_policy: Any = None,
    labor_plan: Any = None,
) -> InvariantSummary:
    """Verify every material/financial ledger of one completed tick.

    Compares the authoritative closing ``state`` against the runner-captured
    ``opening`` boundary and the returned flows; raises
    :class:`AccountingError` on the first failing cell, otherwise returns
    the residual maxima and fills the four flow residual snapshot slots.
    """
    quarter = flows.quarter
    prices = build_material_prices(parameters)

    S = int(np.asarray(network.cell_owner_kind).shape[0])
    D = int(np.asarray(network.demand_cell).shape[0])
    M = int(np.asarray(network.edge_source_cell).shape[0])
    G = len(network.commodity_ids)
    K = int(np.asarray(network.input_cell).shape[0])
    ORG = int(state.organization_id.shape[0])
    N = int(state.household_id.shape[0])
    R = int(state.dwelling_stock.shape[0])
    B = int(state.bank_reserves.shape[0])
    P = int(np.asarray(network.activity_kind).shape[0])

    max_material = 0.0
    max_material_ratio = 0.0
    max_finance = 0.0
    max_finance_ratio = 0.0
    per_ledger: dict[str, tuple[float, float]] = {}

    def material(
        ledger: str, lhs: np.ndarray, rhs: np.ndarray, labels: list[str] | None = None
    ) -> None:
        nonlocal max_material, max_material_ratio
        a, b = _compare_cells(quarter, ledger, lhs, rhs, labels=labels)
        max_material = max(max_material, a)
        max_material_ratio = max(max_material_ratio, b)
        _accumulate(per_ledger, ledger, a, b)

    def material_at_most(
        ledger: str, lhs: np.ndarray, rhs: np.ndarray, labels: list[str] | None = None
    ) -> None:
        nonlocal max_material, max_material_ratio
        a, b = _compare_at_most(quarter, ledger, lhs, rhs, labels=labels)
        max_material = max(max_material, a)
        max_material_ratio = max(max_material_ratio, b)
        _accumulate(per_ledger, ledger, a, b)

    def finance(
        ledger: str, lhs: np.ndarray, rhs: np.ndarray, labels: list[str] | None = None
    ) -> None:
        nonlocal max_finance, max_finance_ratio
        a, b = _compare_cells(quarter, ledger, lhs, rhs, labels=labels)
        max_finance = max(max_finance, a)
        max_finance_ratio = max(max_finance_ratio, b)
        _accumulate(per_ledger, ledger, a, b)

    def finance_at_most(
        ledger: str, lhs: np.ndarray, rhs: np.ndarray, labels: list[str] | None = None
    ) -> None:
        nonlocal max_finance, max_finance_ratio
        a, b = _compare_at_most(quarter, ledger, lhs, rhs, labels=labels)
        max_finance = max(max_finance, a)
        max_finance_ratio = max(max_finance_ratio, b)
        _accumulate(per_ledger, ledger, a, b)

    def some(labels: list[str], mask: np.ndarray) -> list[str]:
        return [labels[int(i)] for i in np.nonzero(mask)[0]]

    # --- 0. structural shapes and finiteness ------------------------------
    expected_shapes: dict[str, tuple[int, ...]] = {
        "stock_value": (S,),
        "household_cash": (N,),
        "household_deferred_receipt": (N,),
        "household_wage_claim": (N,),
        "dwelling_stock": (R,),
        "housing_vacant": (R,),
        "household_dwelling_access": (N,),
        "second_output_stock": (R, G),
        "organization_cash": (ORG,),
        "organization_wage_arrears": (ORG,),
        "organization_interest_arrears": (ORG,),
        "organization_principal": (ORG,),
        "organization_shortage_expectation": (ORG,),
        "organization_bailout_expectation": (ORG,),
        "organization_project_approved": (ORG,),
        "organization_capital_wip": (ORG,),
        "organization_construction_wip": (ORG,),
        "bank_reserves": (B,),
        "bank_loan_asset": (B,),
        "bank_deposit_liability": (B,),
        "bank_equity": (B,),
        "bank_interest_receivable": (B,),
    }
    for name, shape in expected_shapes.items():
        actual = np.asarray(getattr(state, name)).shape
        _require(actual == shape, quarter, f"state.{name} shape {actual} != {shape}")
    flow_shapes: dict[str, tuple[int, ...]] = {
        "activity_target": (P,),
        "activity_realized": (P,),
        "desired": (D,),
        "ordered": (D,),
        "ordered_gross": (D,),
        "unfunded_order": (D,),
        "allocated": (D,),
        "delivered": (D,),
        "used": (D,),
        "inventory_open": (D,),
        "inventory_close": (D,),
        "financial_delivery_blocked": (D,),
        "physical_delivery_blocked": (D,),
        "edge_delivered": (M,),
        "edge_allocated": (M,),
        "edge_service_used": (M,),
        "edge_service_fee": (M,),
        "organization_target": (ORG,),
        "organization_realized": (ORG,),
        "organization_wage_due": (ORG,),
        "organization_wage_paid": (ORG,),
        "organization_interest_due": (ORG,),
        "organization_interest_paid": (ORG,),
        "organization_principal_paid": (ORG,),
        "organization_credit_requested": (ORG,),
        "organization_credit_approved": (ORG,),
        "organization_credit_drawn": (ORG,),
        "organization_investment_requested": (ORG,),
        "organization_investment_approved": (ORG,),
        "organization_investment_completed": (ORG,),
        "organization_bailout_requested": (ORG,),
        "organization_bailout_granted": (ORG,),
        "organization_sales_receipts": (ORG,),
        "organization_purchases": (ORG,),
        "household_wage_income": (N,),
        "household_plot_income_formal": (N,),
        "household_plot_income_direct": (N,),
        "household_late_wage": (N,),
        "household_desired": (N, G),
        "household_affordable": (N, G),
        "household_realized": (N, G),
        "household_budget_unmet": (N, G),
        "household_availability_unmet": (N, G),
        "household_spending": (N,),
        "household_self_use": (N,),
        "household_plot_input_funding": (N,),
        "household_budget_available": (N,),
        "household_forced_saving": (N,),
        "household_voluntary_saving": (N,),
        "household_cash_open": (N,),
        "household_cash_close": (N,),
        "retail_available": (R, G),
        "retail_sales": (R, G),
        "retail_unmet": (R, G),
        "imports": (G,),
        "cmea_imports": (G,),
        "convertible_imports": (G,),
        "cmea_exports": (G,),
        "convertible_exports": (G,),
    }
    for name, shape in flow_shapes.items():
        actual = np.asarray(getattr(flows, name)).shape
        _require(actual == shape, quarter, f"flows.{name} shape {actual} != {shape}")
    _sweep_flows(flows, quarter)
    _sweep_arrays(state, quarter, "closing")
    _sweep_arrays(opening, quarter, "opening")
    for name, value in (
        ("closing.treasury_deposit", state.treasury_deposit),
        ("closing.usd_reserve", state.usd_reserve),
        ("closing.usd_principal", state.usd_principal),
        ("closing.usd_interest_arrears", state.usd_interest_arrears),
        ("opening.treasury_deposit", opening.treasury_deposit),
        ("opening.usd_reserve", opening.usd_reserve),
        ("opening.usd_principal", opening.usd_principal),
        ("opening.usd_interest_arrears", opening.usd_interest_arrears),
    ):
        if not math.isfinite(float(value)) or float(value) < -ATOL:
            raise AccountingError(f"invalid {name}={value!r} in {quarter}")

    cell_labels = _stock_cell_labels(network)
    demand_labels = _purpose_labels(network)
    edge_labels = _edge_labels(network)
    org_labels = [f"org[{int(org_id)}]" for org_id in np.asarray(state.organization_id)]
    household_labels = [f"household[{int(h)}]" for h in np.asarray(state.household_id)]
    region_labels = [f"region[{region_id}]" for region_id in network.region_ids]
    commodity_labels = list(network.commodity_ids)
    bank_labels = [f"bank[{index}]" for index in range(B)]

    continuity = _reconstruct(opening, state, flows, network, prices, parameters)

    # --- 1. flows snapshots bound to the authoritative boundaries ----------
    material(
        "household_cash_open_snapshot",
        flows.household_cash_open,
        opening.household_cash,
        labels=household_labels,
    )
    material(
        "household_cash_close_snapshot",
        flows.household_cash_close,
        state.household_cash,
        labels=household_labels,
    )
    demand_cells = np.asarray(network.demand_cell, dtype=np.int64)
    resident = demand_cells >= 0
    material(
        "demand_inventory_open_view",
        flows.inventory_open[resident],
        opening.stock_value[demand_cells][resident],
        labels=[demand_labels[int(d)] for d in np.nonzero(resident)[0]],
    )
    material(
        "demand_inventory_close_view",
        flows.inventory_close[resident],
        state.stock_value[demand_cells][resident],
        labels=[demand_labels[int(d)] for d in np.nonzero(resident)[0]],
    )
    capital_cells = np.asarray(network.project_capital_cell, dtype=np.int64)
    construction_wip_cells = np.asarray(network.project_construction_cell, dtype=np.int64)
    wip_capital = capital_cells >= 0
    wip_construction = construction_wip_cells >= 0
    material(
        "project_capital_wip_state_binding",
        state.stock_value[capital_cells[wip_capital]],
        state.organization_capital_wip[wip_capital],
        labels=some(org_labels, wip_capital),
    )
    material(
        "project_construction_wip_state_binding",
        state.stock_value[construction_wip_cells[wip_construction]],
        state.organization_construction_wip[wip_construction],
        labels=some(org_labels, wip_construction),
    )
    material(
        "project_capital_wip_opening_binding",
        opening.stock_value[capital_cells[wip_capital]],
        opening.organization_capital_wip[wip_capital],
        labels=some(org_labels, wip_capital),
    )
    material(
        "project_construction_wip_opening_binding",
        opening.stock_value[construction_wip_cells[wip_construction]],
        opening.organization_construction_wip[wip_construction],
        labels=some(org_labels, wip_construction),
    )
    orphan_capital = ~wip_capital
    orphan_construction = ~wip_construction
    if bool(np.any(orphan_capital)):
        material(
            "project_capital_wip_orphan_zero",
            state.organization_capital_wip[orphan_capital],
            np.zeros(int(np.count_nonzero(orphan_capital))),
            labels=some(org_labels, orphan_capital),
        )
    if bool(np.any(orphan_construction)):
        material(
            "project_construction_wip_orphan_zero",
            state.organization_construction_wip[orphan_construction],
            np.zeros(int(np.count_nonzero(orphan_construction))),
            labels=some(org_labels, orphan_construction),
        )

    # --- 2. per-cell stock continuity --------------------------------------
    stockable = ~continuity.services_cells & ~continuity.retail_org_cells
    material(
        "stock_continuity",
        continuity.expected_close[stockable],
        state.stock_value[stockable],
        labels=some(cell_labels, stockable),
    )
    retail_mask = continuity.retail_org_cells & ~continuity.services_cells
    if bool(np.any(retail_mask)):
        material(
            "retail_stock_continuity",
            continuity.retail_expected[retail_mask],
            continuity.retail_close[retail_mask],
            labels=some(cell_labels, retail_mask),
        )
    material(
        "services_cells_close_zero",
        state.stock_value[continuity.services_cells],
        np.zeros(int(np.count_nonzero(continuity.services_cells))),
        labels=some(cell_labels, continuity.services_cells),
    )
    material(
        "expired_services_reconciliation",
        np.asarray([float(np.sum(continuity.services_leftover))]),
        np.asarray([float(flows.expired_services)]),
        labels=["expired_services"],
    )
    material_at_most(
        "services_expiry_nonnegative",
        np.zeros(S),
        continuity.services_leftover,
        labels=cell_labels,
    )

    # --- 3. six-segment identities and edge ceilings ------------------------
    material_at_most(
        "delivered_le_allocated",
        flows.delivered,
        flows.allocated,
        labels=demand_labels,
    )
    material_at_most(
        "allocated_le_ordered",
        flows.allocated,
        flows.ordered,
        labels=demand_labels,
    )
    material(
        "unfunded_plus_ordered_is_gross",
        flows.unfunded_order + flows.ordered,
        flows.ordered_gross,
        labels=demand_labels,
    )
    material(
        "delivered_plus_blocked_is_allocated",
        flows.delivered + flows.financial_delivery_blocked + flows.physical_delivery_blocked,
        flows.allocated,
        labels=demand_labels,
    )
    material_at_most(
        "edge_delivered_le_allocated",
        flows.edge_delivered,
        np.asarray(flows.edge_allocated, dtype=np.float64) * (1.0 + 1e-9),
        labels=edge_labels,
    )
    edge_demand = np.asarray(network.edge_demand, dtype=np.int64)
    _require(
        bool(np.all((edge_demand >= 0) & (edge_demand < D))),
        quarter,
        "route edge demand index outside the demand axis",
    )
    material(
        "edge_sum_per_demand_is_delivered",
        np.bincount(edge_demand, weights=flows.edge_delivered, minlength=D),
        flows.delivered,
        labels=demand_labels,
    )
    # Retail may resell same-tick deliveries to households (plan section 2:
    # "retail can sell opening + this tick's delivered stock"); every other
    # source sells only out of opening stock plus its own same-tick
    # production (transport) or realized imports.
    source_ceiling = (
        np.asarray(opening.stock_value, dtype=np.float64)
        + continuity.production
        + continuity.imports_in
    )
    source_ceiling = np.where(
        continuity.retail_org_cells,
        source_ceiling + continuity.edge_receipts,
        source_ceiling,
    )
    material_at_most(
        "source_stock_ceiling",
        continuity.edge_out_all,
        source_ceiling,
        labels=cell_labels,
    )
    # A same-quarter input may also be paid out of the tick's production pool,
    # so the cell ceiling adds the pool part actually drawn for that cell.
    pool_draw_ceiling = np.asarray(
        getattr(flows, "service_pool_draw_at_cell", np.zeros(S, dtype=np.float64)),
        dtype=np.float64,
    )
    material_at_most(
        "production_input_availability_ceiling",
        continuity.production_used,
        np.asarray(opening.stock_value, dtype=np.float64)
        + continuity.production_row_delivered
        + pool_draw_ceiling,
        labels=cell_labels,
    )
    material_at_most(
        "activity_realized_le_target",
        flows.activity_realized,
        flows.activity_target,
        labels=[f"activity[{p}]" for p in range(P)],
    )

    # Leontief bottleneck rule: used[k] == realized(activity) * coefficient.
    column_coefficients = np.asarray(network.A.sum(axis=0)).ravel().astype(np.float64)
    input_activity = np.asarray(network.input_activity, dtype=np.int64)
    input_index = np.asarray(network.demand_input_index, dtype=np.int64)
    production_rows = input_index >= 0
    k_rows = input_index[production_rows]
    k_used = np.zeros(K, dtype=np.float64)
    k_used[k_rows] = np.asarray(flows.used, dtype=np.float64)[production_rows]
    material(
        "production_used_matches_leontief",
        k_used,
        column_coefficients * flows.activity_realized[input_activity],
        labels=[f"input[{k}]" for k in range(K)],
    )

    # Target binding: org target = min(utilization * capacity * season, labor cap).
    org_types = np.asarray(state.organization_type, dtype=np.int64)
    org_activity = np.asarray(state.organization_activity, dtype=np.int64)
    producers = org_activity >= 0
    if bool(np.any(producers)):
        rows = np.nonzero(producers)[0]
        activities = org_activity[rows]
        season = np.where(
            np.isin(org_types[rows], list(_FARM_TYPE_CODES)),
            float(parameters.farm_seasonal_factors[int(flows.tick) % 4]),
            1.0,
        )
        labor_per_activity = np.asarray(state.organization_labor_per_activity, dtype=np.float64)[
            rows
        ]
        _require(
            bool(np.all(labor_per_activity > 0.0)),
            quarter,
            "productive organization lacks a positive labor_per_activity",
        )
        labor_cap_rows = (
            np.asarray(state.organization_labor_available, dtype=np.float64)[rows]
            / labor_per_activity
        )
        if labor_plan is not None:
            # H5D: independently recompute every labour identity from the plan's
            # carriers (H, A, e, recipe) rather than trusting a bare cap array.
            if int(labor_plan.tick) != int(flows.tick):
                raise AccountingError(
                    f"labor plan tick {labor_plan.tick} does not match flows tick {flows.tick}"
                )
            if not np.array_equal(
                np.asarray(labor_plan.organization_ids, dtype=np.int64),
                np.asarray(state.organization_id, dtype=np.int64),
            ):
                raise AccountingError("labor plan organization axis does not match the state")
            region_count = int(np.asarray(state.dwelling_stock).shape[0])
            if not np.array_equal(
                np.asarray(labor_plan.region_ids, dtype=np.int64),
                np.arange(region_count, dtype=np.int64),
            ):
                raise AccountingError("labor plan region axis does not match the state")
            capacity_axis = np.asarray(labor_plan.capacity_open, dtype=np.float64)
            material(
                "labor_capacity_identity",
                capacity_axis,
                np.asarray(opening.organization_capacity, dtype=np.float64),
            )
            material(
                "labor_labor_per_activity_identity",
                np.asarray(labor_plan.labor_per_activity, dtype=np.float64),
                np.asarray(state.organization_labor_per_activity, dtype=np.float64),
            )
            productive_axis = capacity_axis > 0.0
            establishment_raw = np.zeros(capacity_axis.shape[0], dtype=np.float64)
            establishment_raw[productive_axis] = (
                capacity_axis[productive_axis]
                * np.asarray(state.organization_labor_per_activity, dtype=np.float64)[
                    productive_axis
                ]
                * float(parameters.utilization)
            )
            raw_total = float(establishment_raw.sum())
            establishment_scale = (
                min(1.0, float(np.asarray(state.household_working_adults).sum()) / raw_total)
                if raw_total > 0.0
                else 1.0
            )
            material(
                "labor_establishment_rule",
                np.asarray(labor_plan.establishment, dtype=np.float64),
                establishment_raw * establishment_scale,
            )
            n_working = float(np.asarray(state.household_working_adults, dtype=np.float64).sum())
            material_at_most(
                "labor_establishment_supply",
                np.asarray([float(np.asarray(labor_plan.establishment).sum())]),
                np.asarray([n_working]),
            )
            plan_headcount = np.asarray(labor_plan.headcount, dtype=np.float64)
            material_at_most(
                "labor_headcount_supply",
                np.asarray([float(plan_headcount.sum())]),
                np.asarray([n_working]),
            )
            material(
                "labor_effective_hours_identity",
                np.asarray(labor_plan.effective_hours, dtype=np.float64),
                plan_headcount
                * float(labor_plan.recipe.hours_per_we)
                * (1.0 - np.asarray(labor_plan.absence_rate, dtype=np.float64))
                * np.asarray(labor_plan.effort, dtype=np.float64),
            )
            plan_release = np.asarray(labor_plan.release, dtype=np.float64)
            plan_hire_raw = np.asarray(labor_plan.hire_raw, dtype=np.float64)
            plan_hire = np.asarray(labor_plan.hire, dtype=np.float64)
            if labor_plan.previous is not None:
                previous = labor_plan.previous
                previous_headcount = np.asarray(previous.headcount, dtype=np.float64)
                material(
                    "labor_headcount_evolution",
                    plan_headcount,
                    previous_headcount - plan_release + plan_hire,
                )
                material(
                    "labor_release_rule",
                    plan_release,
                    np.clip(
                        previous_headcount
                        - np.asarray(labor_plan.establishment, dtype=np.float64),
                        0.0,
                        float(labor_plan.recipe.max_release_fraction) * previous_headcount,
                    ),
                )
                retained = previous_headcount - plan_release
                expected_hire_raw = np.clip(
                    np.asarray(labor_plan.establishment, dtype=np.float64) - retained,
                    0.0,
                    float(labor_plan.recipe.hire_capacity_share)
                    * np.asarray(previous.establishment, dtype=np.float64),
                )
                material(
                    "labor_hire_raw_rule",
                    plan_hire_raw,
                    expected_hire_raw,
                )
                retained_total = float(retained.sum())
                available_workers = n_working - retained_total
                material(
                    "labor_available_workers",
                    np.asarray([float(labor_plan.available_workers)]),
                    np.asarray([available_workers]),
                )
                raw_total = float(expected_hire_raw.sum())
                expected_scale = (
                    available_workers / raw_total
                    if raw_total > available_workers
                    else 1.0
                )
                material(
                    "labor_hire_scale",
                    np.asarray([float(labor_plan.hire_scale)]),
                    np.asarray([expected_scale]),
                )
                material(
                    "labor_hire_rule",
                    plan_hire,
                    expected_scale * expected_hire_raw,
                )
                material_at_most(
                    "labor_hire_supply",
                    np.asarray([float(plan_hire.sum())]),
                    np.asarray([available_workers]),
                )
            else:
                zeros = np.zeros(plan_headcount.shape[0], dtype=np.float64)
                material("labor_initial_transition", plan_release + plan_hire_raw, zeros)
                material("labor_initial_hire", plan_hire, zeros)
            effective_hours_axis = np.asarray(labor_plan.effective_hours, dtype=np.float64)
            hours_used_axis = (
                float(labor_plan.recipe.hours_per_we)
                * np.asarray(state.organization_labor_per_activity, dtype=np.float64)
                * np.asarray(flows.organization_realized, dtype=np.float64)
            )
            material_at_most(
                "labor_effective_hours_used",
                hours_used_axis,
                effective_hours_axis,
                labels=[f"organization[{int(o)}]" for o in state.organization_id],
            )
            labor_cap_rows = np.minimum(
                np.asarray(state.organization_labor_available, dtype=np.float64)[rows],
                effective_hours_axis[rows] / float(labor_plan.recipe.hours_per_we),
            ) / labor_per_activity
        expected_local = np.minimum(
            float(parameters.utilization)
            * np.asarray(opening.organization_capacity, dtype=np.float64)[rows]
            * season,
            labor_cap_rows,
        )
        if controls is not None and getattr(controls, "central_target", None) is not None:
            autonomy = float(np.clip(controls.autonomy, 0.0, 1.0))
            central = np.asarray(controls.central_target, dtype=np.float64)[activities]
            mixed = np.maximum((1.0 - autonomy) * central + autonomy * expected_local, 0.0)
            ceiling = np.maximum(
                np.minimum(
                    np.asarray(opening.organization_capacity, dtype=np.float64)[rows] * season,
                    labor_cap_rows,
                ),
                0.0,
            )
            expected_target = np.minimum(mixed, ceiling)
            material_at_most(
                "organization_target_capacity",
                expected_target,
                ceiling,
                labels=[f"activity[{int(a)}]" for a in activities],
            )
        else:
            expected_target = expected_local
        if str(getattr(parameters, "production_target_rule", "legacy")) == "lean_plan":
            # the lean plan only lowers the target; the LP itself is validated by
            # the alignment certificate, not by this per-tick rule gate
            material_at_most(
                "organization_target_rule",
                flows.activity_target[activities],
                expected_target,
                labels=[f"activity[{int(a)}]" for a in activities],
            )
        elif bool(getattr(parameters, "demand_limited_targets", False)):
            # The demand cap is an engine-level policy: bound the target by the
            # uncapped rule here and let the periodicity certificate judge the
            # capped trajectory (the cap reads live order/consumption state).
            material_at_most(
                "organization_target_rule",
                flows.activity_target[activities],
                expected_target,
                labels=[f"activity[{int(a)}]" for a in activities],
            )
        else:
            material(
                "organization_target_rule",
                flows.activity_target[activities],
                expected_target,
                labels=[f"activity[{int(a)}]" for a in activities],
            )
        material(
            "organization_realized_view",
            flows.organization_realized[rows],
            flows.activity_realized[activities],
            labels=[org_labels[int(o)] for o in rows],
        )
        material(
            "organization_target_view",
            flows.organization_target[rows],
            flows.activity_target[activities],
            labels=[org_labels[int(o)] for o in rows],
        )

    # --- 4. household acquisition channels vs boundary edges ---------------
    retail_sales = np.asarray(flows.retail_sales, dtype=np.float64)
    household_edges = np.asarray(network.edge_purpose, dtype=np.int64) == _P_HOUSEHOLD
    cell_kind_arr = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_region_arr = np.asarray(network.cell_region, dtype=np.int64)
    cell_commodity_arr = np.asarray(network.cell_commodity, dtype=np.int64)
    hh_by_region_commodity = np.zeros(R * G, dtype=np.float64)
    plot_hh_edges = np.zeros(R, dtype=np.float64)
    if bool(np.any(household_edges)):
        hh_src = np.asarray(network.edge_source_cell, dtype=np.int64)[household_edges]
        hh_amounts = np.asarray(flows.edge_delivered, dtype=np.float64)[household_edges]
        org_sources = cell_kind_arr[hh_src] == _KIND_ORG
        if bool(np.any(org_sources)):
            np.add.at(
                hh_by_region_commodity,
                cell_region_arr[hh_src[org_sources]] * G + cell_commodity_arr[hh_src[org_sources]],
                hh_amounts[org_sources],
            )
        plot_sources = cell_kind_arr[hh_src] == _KIND_PLOT
        if bool(np.any(plot_sources)):
            np.add.at(
                plot_hh_edges,
                cell_region_arr[hh_src[plot_sources]],
                hh_amounts[plot_sources],
            )
    material(
        "household_edges_mirror_retail_sales",
        hh_by_region_commodity.reshape(R, G),
        retail_sales,
        labels=[
            f"retail[{network.region_ids[r]},{network.commodity_ids[g]}]"
            for r in range(R)
            for g in range(G)
        ],
    )
    commodity_ids = network.commodity_ids
    food_g = _role_index(network, "food")
    weight = np.asarray(state.household_weight, dtype=np.float64)
    household_region = np.asarray(state.household_region, dtype=np.int64)
    if food_g >= 0:
        ready_price = float(prices.standard[food_g])
        direct_quantity = (
            np.bincount(
                household_region,
                weights=weight * np.asarray(flows.household_plot_income_direct, dtype=np.float64),
                minlength=R,
            )
            / ready_price
        )
        self_quantity = (
            np.bincount(
                household_region,
                weights=weight * np.asarray(flows.household_self_use, dtype=np.float64),
                minlength=R,
            )
            / ready_price
        )
        direct_from_households = (
            np.bincount(
                household_region,
                weights=weight * np.asarray(flows.household_realized, dtype=np.float64)[:, food_g],
                minlength=R,
            )
            - retail_sales[:, food_g]
            - self_quantity
        )
        material(
            "plot_market_direct_channel_mirror_households",
            direct_from_households,
            direct_quantity,
            labels=region_labels,
        )
        plot_self_cells = np.asarray(network.plot_ready_self_cell, dtype=np.int64)
        self_ok = plot_self_cells >= 0
        material_at_most(
            "plot_self_use_le_opening_pool",
            self_quantity[self_ok],
            np.asarray(opening.stock_value, dtype=np.float64)[plot_self_cells[self_ok]],
            labels=[region_labels[int(r)] for r in np.nonzero(self_ok)[0]],
        )

    # Household demand cells (region-major pinned D order) mirror retail sales.
    household_goods = [g for g in range(G) if commodity_ids[g] in _household_parent_ids(network)]
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    household_demand = np.nonzero(demand_purpose == _P_HOUSEHOLD)[0]
    _require(
        int(household_demand.shape[0]) == R * len(household_goods),
        quarter,
        "household demand block size contradicts the pinned region-major order",
    )
    if household_goods:
        material(
            "household_demand_delivered_is_retail_sales",
            flows.delivered[household_demand].reshape(R, len(household_goods)),
            retail_sales[:, household_goods],
            labels=[
                f"household_demand[{network.region_ids[r]},{network.commodity_ids[g]}]"
                for r in range(R)
                for g in household_goods
            ],
        )

    # Retail availability = opening + delivered-in, per (region, commodity).
    retail_available = np.asarray(flows.retail_available, dtype=np.float64)
    open_map = np.zeros((R, G), dtype=np.float64)
    receipts_map = np.zeros((R, G), dtype=np.float64)
    retail_presence = continuity.retail_org_cells
    if bool(np.any(retail_presence)):
        np.add.at(
            open_map,
            (cell_region_arr[retail_presence], cell_commodity_arr[retail_presence]),
            np.asarray(opening.stock_value, dtype=np.float64)[retail_presence],
        )
        np.add.at(
            receipts_map,
            (cell_region_arr[retail_presence], cell_commodity_arr[retail_presence]),
            continuity.edge_receipts[retail_presence],
        )
    present = np.zeros((R, G), dtype=bool)
    if bool(np.any(retail_presence)):
        present[cell_region_arr[retail_presence], cell_commodity_arr[retail_presence]] = True
    rows_rg, columns_rg = np.nonzero(present)
    if rows_rg.size:
        material(
            "retail_available_is_open_plus_delivered",
            retail_available[rows_rg, columns_rg],
            open_map[rows_rg, columns_rg] + receipts_map[rows_rg, columns_rg],
            labels=[
                f"retail[{network.region_ids[int(r)]},{network.commodity_ids[int(c)]}]"
                for r, c in zip(rows_rg, columns_rg, strict=True)
            ],
        )
    absent = ~present
    if bool(np.any(absent)):
        material(
            "retail_columns_without_cells_are_zero",
            np.concatenate(
                [
                    retail_available[absent],
                    retail_sales[absent],
                    np.asarray(flows.retail_unmet, dtype=np.float64)[absent],
                ]
            ),
            np.zeros(3 * int(np.count_nonzero(absent))),
            labels=[
                f"retail[{network.region_ids[int(r)]},{network.commodity_ids[int(c)]}:{field_name}]"
                for r, c in zip(*np.nonzero(absent), strict=True)
                for field_name in ("available", "sales", "unmet")
            ],
        )

    # --- 5. trade identities -------------------------------------------------
    material(
        "imports_split_into_channels",
        flows.imports,
        flows.cmea_imports + flows.convertible_imports,
        labels=commodity_labels,
    )
    export_cells = np.asarray(network.export_demand_cell, dtype=np.int64)
    channel_arrays = (flows.cmea_exports, flows.convertible_exports)
    channel_names = ("cmea", "convertible")
    for channel in (0, 1):
        channel_present = export_cells[channel] >= 0
        if bool(np.any(channel_present)):
            material(
                f"export_demand_delivered_{channel_names[channel]}",
                flows.delivered[export_cells[channel][channel_present]],
                channel_arrays[channel][channel_present],
                labels=[
                    f"export_{channel_names[channel]}[{network.commodity_ids[int(g)]}]"
                    for g in np.nonzero(channel_present)[0]
                ],
            )
        channel_absent = ~channel_present
        if bool(np.any(channel_absent)):
            material(
                f"exports_without_demand_cell_{channel_names[channel]}",
                channel_arrays[channel][channel_absent],
                np.zeros(int(np.count_nonzero(channel_absent))),
                labels=[
                    f"export_{channel_names[channel]}[{network.commodity_ids[int(g)]}]"
                    for g in np.nonzero(channel_absent)[0]
                ],
            )

    # --- 6. finance -----------------------------------------------------------
    bank_loan_open = np.asarray(opening.bank_loan_asset, dtype=np.float64)
    bank_receivable_open = np.asarray(opening.bank_interest_receivable, dtype=np.float64)
    bank_equity_open = np.asarray(opening.bank_equity, dtype=np.float64)
    org_bank = np.asarray(state.organization_bank, dtype=np.int64)
    borrower = org_bank >= 0

    def _bank_sum(values: np.ndarray) -> np.ndarray:
        out = np.zeros(B, dtype=np.float64)
        if B and bool(np.any(borrower)):
            out += np.bincount(org_bank[borrower], weights=values[borrower], minlength=B)
        return out

    journal_kind = np.asarray(flows.journal_kind, dtype=object)
    journal_debit = np.asarray(flows.journal_debit, dtype=np.int64)
    journal_credit = np.asarray(flows.journal_credit, dtype=np.int64)
    journal_amount = np.asarray(flows.journal_amount, dtype=np.float64)
    journal_org = np.asarray(flows.journal_org, dtype=object)
    turnover_by_org = np.zeros(ORG, dtype=np.float64)
    org_cash_ids = organization_account_ids(state, AccountKind.CASH_DEPOSIT)
    org_row_by_id = {int(org_id): row for row, org_id in enumerate(state.organization_id)}
    turnover_rows = (journal_kind == "fiscal_turnover_remittance") & np.isin(
        journal_credit, org_cash_ids
    )
    for row in np.flatnonzero(turnover_rows):
        org_row = org_row_by_id.get(int(journal_org[row]))
        if org_row is not None:
            turnover_by_org[org_row] += journal_amount[row]

    interest_recipient_by_household = np.zeros(N, dtype=np.float64)
    household_cash_ids = household_account_ids(state, AccountKind.CASH_DEPOSIT)
    household_row_by_account = {
        int(account): row for row, account in enumerate(household_cash_ids)
    }
    interest_household_rows = (journal_kind == "interest_recipient_deposit") & np.isin(
        journal_debit, household_cash_ids
    )
    for row in np.flatnonzero(interest_household_rows):
        household_row = household_row_by_account[int(journal_debit[row])]
        represented_weight = float(state.household_weight[household_row])
        if represented_weight > 0.0:
            interest_recipient_by_household[household_row] += (
                journal_amount[row] / represented_weight
            )
    terminal_remittance_kinds = np.isin(
        journal_kind, ["interest_recipient_deposit", "fiscal_turnover_remittance"]
    )
    treasury_cash = treasury_account_id(state, AccountKind.CASH_DEPOSIT)
    treasury_remittance = float(
        journal_amount[
            terminal_remittance_kinds & (journal_debit == treasury_cash)
        ].sum()
    )
    interest_remit_by_bank = _bank_sum(
        np.asarray(flows.organization_interest_paid, dtype=np.float64)
        * float(parameters.interest_sink_remittance_fraction)
    )

    finance(
        "bank_assets_equal_liabilities",
        np.asarray(state.bank_loan_asset, dtype=np.float64)
        + np.asarray(state.bank_interest_receivable, dtype=np.float64)
        + np.asarray(state.bank_reserves, dtype=np.float64),
        np.asarray(state.bank_deposit_liability, dtype=np.float64)
        + np.asarray(state.bank_equity, dtype=np.float64),
        labels=bank_labels,
    )
    deposit_sources = np.zeros(B, dtype=np.float64)
    if B:
        deposit_sources += np.bincount(
            household_region % B,
            weights=weight * np.asarray(state.household_cash, dtype=np.float64),
            minlength=B,
        )
        if bool(np.any(borrower)):
            deposit_sources += np.bincount(
                org_bank[borrower],
                weights=np.asarray(state.organization_cash, dtype=np.float64)[borrower],
                minlength=B,
            )
        deposit_sources[0] += float(state.treasury_deposit) + float(state.credit_fund)
    finance(
        "deposit_liability_composition",
        np.asarray(state.bank_deposit_liability, dtype=np.float64),
        deposit_sources,
        labels=bank_labels,
    )
    m2_neutral = bool(getattr(parameters, "m2_neutral_credit", False))
    # H3F-D1 Treasury term loans are real bank assets booked on the same
    # ledger as organization credit.  Their bank row is reconstructed from the
    # journal legs (never from an adapter-supplied hint), and all terms are
    # exactly zero on every legacy path, so these formulas are unchanged when
    # D1 is off.
    treasury_loan_drawn = float(flows.treasury_loan_drawn)
    treasury_principal_paid = float(flows.treasury_principal_paid)
    treasury_interest_due = float(flows.treasury_interest_due)
    treasury_interest_paid = float(flows.treasury_interest_paid)

    def _treasury_bank_delta(account_kind: str, kind_names: tuple[str, ...], *, debit: bool):
        """Per-bank delta from journal rows of the D1 kinds on one side."""
        ids = bank_account_ids(state, account_kind)
        if not B or journal_kind.size == 0:
            return np.zeros(B, dtype=np.float64)
        row_of_account = {int(account): row for row, account in enumerate(ids.tolist())}
        side = journal_debit if debit else journal_credit
        mask = np.isin(journal_kind, kind_names) & np.isin(side, ids)
        out = np.zeros(B, dtype=np.float64)
        for journal_row in np.flatnonzero(mask):
            bank_row = row_of_account.get(int(side[journal_row]))
            if bank_row is not None:
                out[bank_row] += journal_amount[journal_row]
        return out

    d1_draw_kinds = ("treasury_working_capital_draw",)
    d1_principal_kinds = ("treasury_working_capital_principal",)
    d1_accrual_kinds = ("treasury_working_capital_interest_accrual",)
    d1_interest_kinds = ("treasury_working_capital_interest_payment",)
    treasury_loan_bank_delta = _treasury_bank_delta(
        AccountKind.LOAN_ASSET, d1_draw_kinds, debit=True
    ) - _treasury_bank_delta(AccountKind.LOAN_ASSET, d1_principal_kinds, debit=False)
    treasury_receivable_bank_delta = _treasury_bank_delta(
        AccountKind.INTEREST_RECEIVABLE, d1_accrual_kinds, debit=True
    ) - _treasury_bank_delta(
        AccountKind.INTEREST_RECEIVABLE, d1_interest_kinds, debit=False
    )
    treasury_equity_bank_delta = _treasury_bank_delta(
        AccountKind.EQUITY, d1_accrual_kinds, debit=False
    )
    finance(
        "bank_loan_asset_continuity",
        np.asarray(state.bank_loan_asset, dtype=np.float64),
        bank_loan_open
        + (
            np.zeros(B, dtype=np.float64)
            if m2_neutral
            else (
                _bank_sum(np.asarray(flows.organization_credit_drawn, dtype=np.float64))
                - _bank_sum(np.asarray(flows.organization_principal_paid, dtype=np.float64))
            )
        )
        + treasury_loan_bank_delta,
        labels=bank_labels,
    )
    finance(
        "bank_interest_receivable_continuity",
        np.asarray(state.bank_interest_receivable, dtype=np.float64),
        bank_receivable_open
        + _bank_sum(np.asarray(flows.organization_interest_due, dtype=np.float64))
        - _bank_sum(np.asarray(flows.organization_interest_paid, dtype=np.float64))
        + treasury_receivable_bank_delta,
        labels=bank_labels,
    )
    finance(
        "bank_equity_interest_accrual",
        np.asarray(state.bank_equity, dtype=np.float64),
        bank_equity_open
        + _bank_sum(np.asarray(flows.organization_interest_due, dtype=np.float64))
        - interest_remit_by_bank
        + treasury_equity_bank_delta,
        labels=bank_labels,
    )

    finance(
        "organization_cash_continuity",
        np.asarray(state.organization_cash, dtype=np.float64),
        np.asarray(opening.organization_cash, dtype=np.float64)
        + np.asarray(flows.organization_credit_drawn, dtype=np.float64)
        + np.asarray(flows.organization_bailout_granted, dtype=np.float64)
        + np.asarray(flows.organization_sbc_transfer, dtype=np.float64)
        + np.asarray(flows.organization_sales_receipts, dtype=np.float64)
        - np.asarray(flows.organization_wage_paid, dtype=np.float64)
        - np.asarray(flows.organization_interest_paid, dtype=np.float64)
        - np.asarray(flows.organization_principal_paid, dtype=np.float64)
        - np.asarray(flows.organization_purchases, dtype=np.float64)
        - turnover_by_org,
        labels=org_labels,
    )
    finance(
        "organization_principal_continuity",
        np.asarray(state.organization_principal, dtype=np.float64),
        np.asarray(opening.organization_principal, dtype=np.float64)
        + np.asarray(flows.organization_credit_drawn, dtype=np.float64)
        - np.asarray(flows.organization_principal_paid, dtype=np.float64),
        labels=org_labels,
    )
    finance(
        "organization_wage_arrears_continuity",
        np.asarray(state.organization_wage_arrears, dtype=np.float64),
        np.asarray(opening.organization_wage_arrears, dtype=np.float64)
        + np.asarray(flows.organization_wage_due, dtype=np.float64)
        - np.asarray(flows.organization_wage_paid, dtype=np.float64),
        labels=org_labels,
    )
    finance(
        "organization_interest_arrears_continuity",
        np.asarray(state.organization_interest_arrears, dtype=np.float64),
        np.asarray(opening.organization_interest_arrears, dtype=np.float64)
        + np.asarray(flows.organization_interest_due, dtype=np.float64)
        - np.asarray(flows.organization_interest_paid, dtype=np.float64),
        labels=org_labels,
    )
    finance(
        "organization_wage_due_rule",
        np.asarray(flows.organization_wage_due, dtype=np.float64),
        float(parameters.wage_rate)
        * np.asarray(state.organization_labor_available, dtype=np.float64),
        labels=org_labels,
    )
    finance(
        "organization_interest_due_rule",
        np.asarray(flows.organization_interest_due, dtype=np.float64),
        quarter_domestic_credit_rate(parameters)
        * np.asarray(opening.organization_principal, dtype=np.float64),
        labels=org_labels,
    )
    finance_at_most(
        "organization_wage_paid_ceiling",
        np.asarray(flows.organization_wage_paid, dtype=np.float64),
        np.asarray(flows.organization_wage_due, dtype=np.float64)
        + np.asarray(opening.organization_wage_arrears, dtype=np.float64),
        labels=org_labels,
    )
    finance_at_most(
        "organization_interest_paid_ceiling",
        np.asarray(flows.organization_interest_paid, dtype=np.float64),
        np.asarray(flows.organization_interest_due, dtype=np.float64)
        + np.asarray(opening.organization_interest_arrears, dtype=np.float64),
        labels=org_labels,
    )
    finance_at_most(
        "organization_principal_paid_ceiling",
        np.asarray(flows.organization_principal_paid, dtype=np.float64),
        float(parameters.principal_repayment_fraction)
        * np.asarray(opening.organization_principal, dtype=np.float64),
        labels=org_labels,
    )
    finance_at_most(
        "bailout_granted_le_requested",
        np.asarray(flows.organization_bailout_granted, dtype=np.float64),
        np.asarray(flows.organization_bailout_requested, dtype=np.float64),
        labels=org_labels,
    )
    # The opening snapshot carries no capacity axis (mutable-only capture),
    # so capacity growth is gated as "closing capacity covers this tick's
    # completions"; exact capacity continuity is pinned through the WIP
    # installation gates below.
    finance_at_most(
        "capacity_covers_completions",
        np.asarray(flows.organization_investment_completed, dtype=np.float64),
        np.asarray(state.organization_capacity, dtype=np.float64),
        labels=org_labels,
    )
    capital_unit = float(parameters.capacity_capital_goods_per_unit)
    construction_unit = float(parameters.capacity_construction_per_unit)
    completed = np.asarray(flows.organization_investment_completed, dtype=np.float64)
    delivered_capital_wip = np.zeros(ORG, dtype=np.float64)
    delivered_construction_wip = np.zeros(ORG, dtype=np.float64)
    if bool(np.any(wip_capital)):
        delivered_capital_wip[wip_capital] = continuity.edge_receipts[capital_cells[wip_capital]]
    if bool(np.any(wip_construction)):
        delivered_construction_wip[wip_construction] = continuity.edge_receipts[
            construction_wip_cells[wip_construction]
        ]
    finance(
        "capital_wip_continuity",
        np.asarray(state.organization_capital_wip, dtype=np.float64),
        np.asarray(opening.organization_capital_wip, dtype=np.float64)
        + delivered_capital_wip
        - completed * capital_unit,
        labels=org_labels,
    )
    finance(
        "construction_wip_continuity",
        np.asarray(state.organization_construction_wip, dtype=np.float64),
        np.asarray(opening.organization_construction_wip, dtype=np.float64)
        + delivered_construction_wip
        - completed * construction_unit,
        labels=org_labels,
    )
    _unit_residual, ratio = _check_unit_interval(
        quarter,
        "shortage_expectation_unit_interval",
        np.asarray(state.organization_shortage_expectation, dtype=np.float64),
        labels=org_labels,
    )
    max_material_ratio = max(max_material_ratio, ratio)
    _accumulate(per_ledger, "shortage_expectation_unit_interval", 0.0, ratio)
    _unit_residual, ratio = _check_unit_interval(
        quarter,
        "bailout_expectation_unit_interval",
        np.asarray(state.organization_bailout_expectation, dtype=np.float64),
        labels=org_labels,
    )
    max_material_ratio = max(max_material_ratio, ratio)
    _accumulate(per_ledger, "bailout_expectation_unit_interval", 0.0, ratio)

    # Household cash identity and deferred receipts.
    finance(
        "household_cash_continuity",
        np.asarray(state.household_cash, dtype=np.float64)
        - np.asarray(opening.household_cash, dtype=np.float64),
        np.asarray(flows.household_wage_income, dtype=np.float64)
        + np.asarray(flows.household_plot_income_formal, dtype=np.float64)
        + np.asarray(flows.household_plot_income_direct, dtype=np.float64)
        + np.asarray(flows.household_second_income_direct, dtype=np.float64)
        + np.asarray(flows.household_late_wage, dtype=np.float64)
        - np.asarray(flows.household_plot_input_funding, dtype=np.float64)
        - np.asarray(flows.household_second_input_funding, dtype=np.float64)
        - np.asarray(flows.household_spending, dtype=np.float64)
        + interest_recipient_by_household,
        labels=household_labels,
    )
    finance(
        "household_deferred_receipt_close",
        np.asarray(state.household_deferred_receipt, dtype=np.float64),
        np.asarray(flows.household_plot_income_direct, dtype=np.float64)
        + np.asarray(flows.household_second_income_direct, dtype=np.float64)
        + np.asarray(flows.household_late_wage, dtype=np.float64),
        labels=household_labels,
    )

    # Treasury domestic account (bank 0): import sales at admin prices fund
    # export procurement, housing construction, border freight and bailouts.
    import_stage = np.zeros(G, dtype=np.int64)
    if bool(np.any(importable := (np.asarray(network.import_pool_cell, dtype=np.int64) >= 0))):
        pool_cells = np.asarray(network.import_pool_cell, dtype=np.int64)[importable]
        import_stage[importable] = np.asarray(network.cell_stage, dtype=np.int64)[pool_cells]
    import_prices = np.asarray(
        [prices.price_for(g, int(import_stage[g])) for g in range(G)], dtype=np.float64
    )
    import_sales = np.zeros(G, dtype=np.float64)
    edge_sources = np.asarray(network.edge_source_cell, dtype=np.int64)
    import_edges = np.asarray(network.cell_owner_kind, dtype=np.int64)[edge_sources] == _KIND_IMPORT
    if bool(np.any(import_edges)):
        import_sales = np.bincount(
            np.asarray(network.edge_commodity, dtype=np.int64)[import_edges],
            weights=np.asarray(flows.edge_delivered, dtype=np.float64)[import_edges]
            * import_prices[np.asarray(network.edge_commodity, dtype=np.int64)[import_edges]],
            minlength=G,
        )
    imports_value = float(import_sales.sum())
    export_stage = np.asarray(
        [
            STAGE_CODES["ready"] if cid == _role_id(network, "food") else STAGE_CODES["standard"]
            for cid in commodity_ids
        ],
        dtype=np.int64,
    )
    export_prices = np.asarray(
        [prices.price_for(g, int(export_stage[g])) for g in range(G)], dtype=np.float64
    )
    exports_quantity_total = np.asarray(flows.cmea_exports, dtype=np.float64) + np.asarray(
        flows.convertible_exports, dtype=np.float64
    )
    exports_value = float(np.sum(exports_quantity_total * export_prices))
    housing_cells = np.nonzero(demand_purpose == _P_HOUSING)[0]
    _require(
        int(housing_cells.shape[0]) == R,
        quarter,
        "housing demand block must carry exactly one cell per region",
    )
    construction_g = (
        _role_index(network, "construction")
    )
    housing_value = 0.0
    if construction_g >= 0:
        housing_value = float(np.sum(flows.delivered[housing_cells])) * prices.price_for(
            construction_g, STAGE_CODES["standard"]
        )
    border_purposes = np.isin(
        np.asarray(network.edge_purpose, dtype=np.int64),
        [_P_EXPORT_CMEA, _P_EXPORT_CONVERTIBLE, _P_HOUSING],
    )
    border_fees = float(
        np.sum(np.asarray(flows.edge_service_fee, dtype=np.float64)[border_purposes])
    )
    export_purpose_border = np.isin(
        np.asarray(network.edge_purpose, dtype=np.int64),
        [_P_EXPORT_CMEA, _P_EXPORT_CONVERTIBLE],
    )
    export_service_fees = float(
        np.sum(np.asarray(flows.edge_service_fee, dtype=np.float64)[export_purpose_border])
    )
    finance(
        "treasury_export_outlay_rule",
        np.asarray([float(flows.treasury_export_outlay)]),
        np.asarray([exports_value + export_service_fees]),
        labels=["treasury_export_outlay"],
    )
    finance(
        "treasury_deposit_continuity",
        np.asarray([float(state.treasury_deposit)]),
        np.asarray(
            [
                float(opening.treasury_deposit)
                + imports_value
                - exports_value
                - float(np.sum(flows.organization_bailout_granted))
                - housing_value
                - border_fees
                + treasury_remittance
                + treasury_loan_drawn
                - treasury_principal_paid
                - treasury_interest_paid
            ]
        ),
        labels=["treasury"],
    )
    # H3F-D1: the Treasury's outstanding term principal and unpaid interest
    # are real liabilities with the lending bank.  Zero on every legacy path.
    finance(
        "treasury_loan_liability_continuity",
        np.asarray([float(state.treasury_loan_principal)]),
        np.asarray(
            [
                float(opening.treasury_loan_principal)
                + treasury_loan_drawn
                - treasury_principal_paid
            ]
        ),
        labels=["treasury_loan_principal"],
    )
    finance(
        "treasury_interest_arrears_continuity",
        np.asarray([float(state.treasury_interest_arrears)]),
        np.asarray(
            [
                float(opening.treasury_interest_arrears)
                + treasury_interest_due
                - treasury_interest_paid
            ]
        ),
        labels=["treasury_interest_arrears"],
    )
    if m2_neutral:
        drawn_total = float(np.sum(flows.organization_credit_drawn))
        paid_total = float(np.sum(flows.organization_principal_paid))
        finance(
            "treasury_loan_asset_continuity",
            np.asarray([float(state.treasury_loan_asset)]),
            np.asarray([float(opening.treasury_loan_asset) + drawn_total - paid_total]),
            labels=["treasury"],
        )
        finance(
            "credit_fund_continuity",
            np.asarray([float(state.credit_fund)]),
            np.asarray([float(opening.credit_fund) + paid_total - drawn_total]),
            labels=["credit_fund"],
        )

    # Foreign accounts (USD and CMEA close separately; CMEA may go negative).
    finance(
        "usd_reserve_continuity",
        np.asarray([float(state.usd_reserve)]),
        np.asarray(
            [
                float(opening.usd_reserve)
                + float(flows.usd_export_receipt)
                - float(flows.usd_interest_paid)
                - float(flows.usd_principal_paid)
                - float(flows.usd_import_payment)
                + float(flows.usd_loan_drawn)
            ]
        ),
        labels=["usd_reserve"],
    )
    finance(
        "usd_principal_continuity",
        np.asarray([float(state.usd_principal)]),
        np.asarray(
            [
                float(opening.usd_principal)
                + float(flows.usd_loan_drawn)
                - float(flows.usd_principal_paid)
            ]
        ),
        labels=["usd_principal"],
    )
    finance(
        "usd_interest_arrears_continuity",
        np.asarray([float(state.usd_interest_arrears)]),
        np.asarray(
            [
                float(opening.usd_interest_arrears)
                + float(flows.usd_interest_accrued)
                - float(flows.usd_interest_paid)
            ]
        ),
        labels=["usd_interest_arrears"],
    )
    finance(
        "cmea_settlement_continuity",
        np.asarray([float(state.cmea_settlement_balance)]),
        np.asarray(
            [
                float(opening.cmea_settlement_balance)
                + float(flows.cmea_export_receipt)
                - float(flows.cmea_import_payment)
            ]
        ),
        labels=["cmea_settlement_balance"],
    )

    # --- 7. journal -----------------------------------------------------------
    kind, debit, credit, amount, currency = _check_journal(flows, quarter)
    wage_journal_total = np.asarray([0.0])
    bailout_journal_total = np.asarray([0.0])
    if amount.size:
        household_cash_ids = np.asarray(
            household_account_ids(state, AccountKind.CASH_DEPOSIT), dtype=np.int64
        )
        organization_cash_ids = np.asarray(
            organization_account_ids(state, AccountKind.CASH_DEPOSIT), dtype=np.int64
        )
        domestic = currency == DOMESTIC_CURRENCY
        to_households = (kind == "wage_payment") & domestic & np.isin(debit, household_cash_ids)
        wage_journal_total = np.asarray([float(np.sum(amount[to_households]))])
        to_borrowers = (kind == "bailout_grant") & domestic & np.isin(credit, organization_cash_ids)
        bailout_journal_total = np.asarray([float(np.sum(amount[to_borrowers]))])
    finance(
        "journal_wage_payment_vs_households",
        wage_journal_total,
        np.asarray(
            [
                float(
                    np.sum(
                        weight
                        * (
                            np.asarray(flows.household_wage_income, dtype=np.float64)
                            + np.asarray(flows.household_late_wage, dtype=np.float64)
                        )
                    )
                )
            ]
        ),
        labels=["wage_payment"],
    )
    finance(
        "journal_bailout_grant_vs_organizations",
        bailout_journal_total,
        np.asarray([float(np.sum(flows.organization_bailout_granted))]),
        labels=["bailout_grant"],
    )

    # H3F-D1: every loan flow scalar must be backed by the matching journal
    # leg on the Treasury/bank side.  This closes the "fake flow, no entry"
    # hole the engine's structural journal check leaves open.
    if amount.size:
        treasury_cash_id = treasury_account_id(state, AccountKind.CASH_DEPOSIT)
        treasury_liability_id = treasury_term_account_id(state, AccountKind.LOAN_LIABILITY)
        treasury_payable_id = treasury_term_account_id(state, AccountKind.INTEREST_PAYABLE)
        bank_receivable_ids = bank_account_ids(state, AccountKind.INTEREST_RECEIVABLE)
        d1_draw_journal = np.asarray(
            [
                float(
                    np.sum(
                        amount[
                            (kind == "treasury_working_capital_draw")
                            & (debit == treasury_cash_id)
                        ]
                    )
                )
            ]
        )
        d1_principal_journal = np.asarray(
            [
                float(
                    np.sum(
                        amount[
                            (kind == "treasury_working_capital_principal")
                            & (debit == treasury_liability_id)
                        ]
                    )
                )
            ]
        )
        d1_accrual_journal = np.asarray(
            [
                float(
                    np.sum(
                        amount[
                            (kind == "treasury_working_capital_interest_accrual")
                            & np.isin(debit, bank_receivable_ids)
                        ]
                    )
                )
            ]
        )
        d1_interest_journal = np.asarray(
            [
                float(
                    np.sum(
                        amount[
                            (kind == "treasury_working_capital_interest_payment")
                            & (debit == treasury_payable_id)
                        ]
                    )
                )
            ]
        )
    else:
        d1_draw_journal = np.zeros(1)
        d1_principal_journal = np.zeros(1)
        d1_accrual_journal = np.zeros(1)
        d1_interest_journal = np.zeros(1)
    finance(
        "journal_treasury_working_capital_draw_vs_flow",
        d1_draw_journal,
        np.asarray([treasury_loan_drawn]),
        labels=["treasury_working_capital_draw"],
    )
    finance(
        "journal_treasury_working_capital_principal_vs_flow",
        d1_principal_journal,
        np.asarray([treasury_principal_paid]),
        labels=["treasury_working_capital_principal"],
    )
    finance(
        "journal_treasury_working_capital_interest_accrual_vs_flow",
        d1_accrual_journal,
        np.asarray([treasury_interest_due]),
        labels=["treasury_working_capital_interest_accrual"],
    )
    finance(
        "journal_treasury_working_capital_interest_payment_vs_flow",
        d1_interest_journal,
        np.asarray([treasury_interest_paid]),
        labels=["treasury_working_capital_interest_payment"],
    )

    # --- H3F-D2 export receivables ------------------------------------------
    # The closing book is reconstructed independently from the opening
    # snapshot and the flow event log; no state delta is trusted on its own.
    d2_account_ids = {
        int(treasury_receivable_account_id(state, currency, account_kind))
        for currency in (USD_CURRENCY, CMEA_CURRENCY)
        for account_kind in (
            AccountKind.EXPORT_RECEIVABLE,
            AccountKind.BAD_DEBT_ALLOWANCE,
            AccountKind.BAD_DEBT_EXPENSE,
            AccountKind.EXPORT_SALES_INCOME,
        )
    }
    touches_d2_account = bool(
        np.any(np.isin(debit, list(d2_account_ids)))
        or np.any(np.isin(credit, list(d2_account_ids)))
    )
    d2_active = bool(
        opening.export_receivables
        or state.export_receivables
        or opening.export_receivable_event_ids
        or state.export_receivable_event_ids
        or flows.export_receivable_events
        or any(float(getattr(flows, name)) != 0.0 for name in _D2_FLOW_FIELDS)
        or any(kind_name in _D2_JOURNAL_KINDS for kind_name in flows.journal_kind)
        or any(
            value is not None and flows.journal_kind[index] not in _D3_JOURNAL_KINDS
            for index, value in enumerate(flows.journal_event)
        )
        or touches_d2_account
    )
    if d2_active:
        if export_receivable_policy is None:
            raise AccountingError(
                f"{quarter}: D2 activity requires the admitted export_receivable_policy"
            )
        try:
            validate_export_policy(export_receivable_policy)
            applied = tuple(flows.export_receivable_events)
            first_caller = next(
                (index for index, event in enumerate(applied) if event.kind != "delivery"),
                len(applied),
            )
            if any(event.kind != "delivery" for event in applied[:first_caller]):
                raise ValueError("delivery events must precede caller events")
            if any(event.kind == "delivery" for event in applied[first_caller:]):
                raise ValueError("delivery events must precede caller events")
            if tuple(applied[first_caller:]) != tuple(export_receivable_policy.events):
                raise ValueError(
                    "applied caller events differ from the admitted policy events"
                )
            admitted_events = applied
            validate_receivable_book(
                tuple(opening.export_receivables),
                tuple(opening.export_receivable_event_ids),
                completed_ticks=int(flows.tick),
                commodity_ids=tuple(network.commodity_ids),
            )
            recomputed_book, recomputed_ids = apply_receivable_events(
                tuple(opening.export_receivables),
                tuple(opening.export_receivable_event_ids),
                admitted_events,
                current_tick=int(flows.tick),
            )
            validate_receivable_book(
                tuple(state.export_receivables),
                tuple(state.export_receivable_event_ids),
                completed_ticks=int(flows.tick) + 1,
                commodity_ids=tuple(network.commodity_ids),
            )
        except ValueError as exc:
            raise AccountingError(
                f"{quarter}: export receivable continuity rejected: {exc}"
            ) from exc
        closing_book = {lot.receivable_id: lot for lot in state.export_receivables}
        recomputed = {lot.receivable_id: lot for lot in recomputed_book}
        if set(closing_book) != set(recomputed):
            missing = sorted(set(recomputed) - set(closing_book))
            extra = sorted(set(closing_book) - set(recomputed))
            raise AccountingError(
                f"{quarter}: export receivable lot set mismatch: "
                f"missing={missing} extra={extra}"
            )
        if tuple(state.export_receivable_event_ids) != recomputed_ids:
            raise AccountingError(
                f"{quarter}: export receivable event log is not the opening log plus "
                "this tick's applied events"
            )
        lot_ids = sorted(closing_book)
        if lot_ids:
            for field_name in (
                "contract_id",
                "currency",
                "buyer_id",
                "seller_id",
                "commodity_id",
                "delivery_tick",
                "due_tick",
            ):
                for key in lot_ids:
                    if getattr(closing_book[key], field_name) != getattr(
                        recomputed[key], field_name
                    ):
                        raise AccountingError(
                            f"{quarter}: receivable {key!r} identity field "
                            f"{field_name} differs from replay"
                        )
            for field_name in (
                "principal",
                "gross",
                "provision",
                "written_off",
                "received",
                "recovered",
                "writeoffs",
                "provision_expense",
                "provision_released",
            ):
                finance(
                    f"export_receivable_{field_name}_continuity",
                    np.asarray([getattr(closing_book[key], field_name) for key in lot_ids]),
                    np.asarray([getattr(recomputed[key], field_name) for key in lot_ids]),
                    labels=lot_ids,
                )
        for receivable_currency, suffix in (
            (USD_CURRENCY, "usd"),
            (CMEA_CURRENCY, "cmea"),
        ):
            finance(
                f"export_receivable_balance_{suffix}_vs_book",
                np.asarray([float(getattr(flows, f"export_receivable_balance_{suffix}"))]),
                np.asarray(
                    [
                        float(
                            sum(
                                lot.gross
                                for lot in closing_book.values()
                                if lot.currency == receivable_currency
                            )
                        )
                    ]
                ),
                labels=[f"export_receivable_balance_{suffix}"],
            )
            finance(
                f"export_receivable_overdue_{suffix}_vs_book",
                np.asarray([float(getattr(flows, f"export_receivable_overdue_{suffix}"))]),
                np.asarray(
                    [
                        float(
                            sum(
                                lot.gross
                                for lot in closing_book.values()
                                if lot.currency == receivable_currency
                                and lot.due_tick < int(flows.tick)
                            )
                        )
                    ]
                ),
                labels=[f"export_receivable_overdue_{suffix}"],
            )
        event_kinds = ("receipt", "loss", "writeoff", "recovery", "delivery")
        expected_flows: dict[str, float] = {}
        for receivable_currency, suffix in (
            (USD_CURRENCY, "usd"),
            (CMEA_CURRENCY, "cmea"),
        ):
            expected_flows[f"export_receivable_opened_{suffix}"] = sum(
                event.amount
                for event in admitted_events
                if event.kind == "delivery" and event.currency == receivable_currency
            )
            expected_flows[f"export_receivable_received_{suffix}"] = sum(
                event.amount
                for event in admitted_events
                if event.kind in ("receipt", "recovery") and event.currency == receivable_currency
            )
            expected_flows[f"export_receivable_recovered_{suffix}"] = sum(
                event.amount
                for event in admitted_events
                if event.kind == "recovery" and event.currency == receivable_currency
            )
            expected_flows[f"export_receivable_written_off_{suffix}"] = sum(
                event.amount
                for event in admitted_events
                if event.kind == "writeoff" and event.currency == receivable_currency
            )
            expected_flows[f"export_receivable_loss_provision_{suffix}"] = sum(
                event.amount
                for event in admitted_events
                if event.kind == "loss" and event.currency == receivable_currency
            )
            expected_flows[f"export_receivable_provision_released_{suffix}"] = sum(
                event.amount
                for event in admitted_events
                if event.kind == "recovery" and event.currency == receivable_currency
            )
        for flow_name, expected in expected_flows.items():
            finance(
                f"{flow_name}_vs_events",
                np.asarray([float(getattr(flows, flow_name))]),
                np.asarray([float(expected)]),
                labels=[flow_name],
            )
        # Delivery principals are frozen at the real delivered quantity times
        # the channel price recomputed from the admitted forcing slice, not
        # from the mutable flows object.  A coherent edit of every flow field
        # therefore still fails against the scenario's price context.
        if forcing is None:
            raise AccountingError(
                f"{quarter}: D2 delivery valuation requires the admitted forcing"
            )
        cmea_expected, usd_expected = channel_prices(
            parameters,
            network,
            oil_price=float(forcing.oil_price[int(flows.tick)]),
            cmea_contract_price=float(forcing.cmea_energy_price[int(flows.tick)]),
        )
        prices_pair = flows.export_receivable_channel_prices
        if len(prices_pair) != 2:
            raise AccountingError(
                f"{quarter}: export receivable delivery events lack channel prices"
            )
        cmea_prices = np.asarray(prices_pair[0], dtype=np.float64)
        usd_prices = np.asarray(prices_pair[1], dtype=np.float64)
        commodity_axis = list(network.commodity_ids)
        if (
            cmea_prices.shape != (G,)
            or usd_prices.shape != (G,)
            or cmea_expected.shape != (G,)
            or usd_expected.shape != (G,)
        ):
            raise AccountingError(
                f"{quarter}: export receivable channel price axes disagree with G={G}"
            )
        finance(
            "export_receivable_cmea_prices_vs_forcing",
            cmea_prices,
            cmea_expected,
            labels=commodity_axis,
        )
        finance(
            "export_receivable_usd_prices_vs_forcing",
            usd_prices,
            usd_expected,
            labels=commodity_axis,
        )
        delivered_channels = {
            CMEA_CURRENCY: np.asarray(flows.cmea_exports, dtype=np.float64),
            USD_CURRENCY: np.asarray(flows.convertible_exports, dtype=np.float64),
        }
        delivery_keys: set[tuple[str, int]] = set()
        for event in admitted_events:
            if event.kind != "delivery":
                continue
            if event.commodity_id not in commodity_axis:
                raise AccountingError(
                    f"{quarter}: delivery event {event.event_id!r} names an unknown "
                    f"commodity {event.commodity_id!r}"
                )
            g = commodity_axis.index(event.commodity_id)
            prices = cmea_expected if event.currency == CMEA_CURRENCY else usd_expected
            expected_principal = float(delivered_channels[event.currency][g] * prices[g])
            finance(
                "export_receivable_delivery_principal_vs_delivery",
                np.asarray([float(event.amount)]),
                np.asarray([expected_principal]),
                labels=[event.event_id],
            )
            contract = resolve_export_contract(
                tuple(export_receivable_policy.contracts),
                event.currency,
                event.commodity_id,
            )
            if (
                event.contract_id != contract.contract_id
                or event.buyer_id != contract.buyer_id
                or event.seller_id != contract.seller_id
            ):
                raise AccountingError(
                    f"{quarter}: delivery event {event.event_id!r} disagrees with "
                    "the admitted contract identity"
                )
            if event.due_tick != event.delivery_tick + int(
                export_receivable_policy.term_quarters
            ):
                raise AccountingError(
                    f"{quarter}: delivery event {event.event_id!r} due tick disagrees "
                    "with the admitted term"
                )
            key = (event.currency, g)
            if key in delivery_keys:
                raise AccountingError(
                    f"{quarter}: duplicate delivery event for {event.currency} commodity {g}"
                )
            delivery_keys.add(key)
        expected_delivery_keys = {
            (currency, int(g))
            for currency, delivered in delivered_channels.items()
            for g in np.nonzero(delivered > 0.0)[0]
        }
        if delivery_keys != expected_delivery_keys:
            raise AccountingError(
                f"{quarter}: delivery event set {sorted(delivery_keys)} disagrees "
                f"with real deliveries {sorted(expected_delivery_keys)}"
            )
        cash_by_currency = {USD_CURRENCY: 0.0, CMEA_CURRENCY: 0.0}
        for event in admitted_events:
            if event.kind in ("receipt", "recovery"):
                cash_by_currency[event.currency] += float(event.amount)
        finance(
            "export_receivable_usd_cash_vs_events",
            np.asarray([float(flows.usd_export_receipt)]),
            np.asarray([cash_by_currency[USD_CURRENCY]]),
            labels=["usd_export_receipt"],
        )
        finance(
            "export_receivable_cmea_cash_vs_events",
            np.asarray([float(flows.cmea_export_receipt)]),
            np.asarray([cash_by_currency[CMEA_CURRENCY]]),
            labels=["cmea_export_receipt"],
        )

        # Exact event-to-journal correspondence.  Every expected row (count,
        # kind, accounts, currency, amount and event id) must appear exactly
        # once; split, merged, duplicated or re-orged rows are rejected.
        expected_rows: list[tuple[str, int, int, str, float, str]] = []
        for event in admitted_events:
            expected_rows.extend(receivable_journal_rows(state, event))
        def _d2_journal_int(value: object, label: str, index: int) -> int:
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
                raise AccountingError(
                    f"{quarter}: D2 journal row {index} {label} must be a strict "
                    f"integer; got {value!r}"
                )
            return int(value)

        def _touches_d2_account(value: object) -> bool:
            if isinstance(value, bool):
                return False
            if isinstance(value, (int, np.integer)):
                return int(value) in d2_account_ids
            if isinstance(value, (float, np.floating)):
                if not np.isfinite(float(value)):
                    return False
                return int(value) in d2_account_ids
            return False

        actual_rows: list[tuple[str, int, int, str, float, str]] = []
        for index, journal_kind in enumerate(flows.journal_kind):
            raw_debit = flows.journal_debit[index]
            raw_credit = flows.journal_credit[index]
            event_id = flows.journal_event[index]
            touches_d2 = _touches_d2_account(raw_debit) or _touches_d2_account(
                raw_credit
            )
            is_d2 = journal_kind in _D2_JOURNAL_KINDS
            if not (touches_d2 or is_d2 or event_id is not None):
                continue
            if (
                not is_d2
                or event_id is None
                or not isinstance(event_id, str)
                or not touches_d2
            ):
                raise AccountingError(
                    f"{quarter}: journal row {index} ({journal_kind!r}) mixes D2 "
                    "state, accounts or event identity with a non-D2 transaction"
                )
            raw_debit_i = _d2_journal_int(raw_debit, "debit", index)
            raw_credit_i = _d2_journal_int(raw_credit, "credit", index)
            raw_tick = _d2_journal_int(flows.journal_tick[index], "tick", index)
            if raw_tick != int(flows.tick):
                raise AccountingError(
                    f"{quarter}: D2 journal row {index} tick {raw_tick} != "
                    f"flow tick {flows.tick}"
                )
            raw_leg = _d2_journal_int(flows.journal_leg[index], "leg", index)
            if raw_leg != 0:
                raise AccountingError(
                    f"{quarter}: D2 journal row {index} starts at leg {raw_leg!r}; "
                    "every D2 event is its own one-leg transaction"
                )
            if index + 1 < len(flows.journal_leg):
                next_leg = flows.journal_leg[index + 1]
                if (
                    isinstance(next_leg, bool)
                    or not isinstance(next_leg, (int, np.integer))
                    or int(next_leg) != 0
                ):
                    raise AccountingError(
                        f"{quarter}: D2 journal row {index} does not end its "
                        f"transaction; next leg is {next_leg!r}, expected a new "
                        "leg-0 transaction"
                    )
            raw_currency = flows.journal_currency[index]
            if not isinstance(raw_currency, str):
                raise AccountingError(
                    f"{quarter}: D2 journal row {index} currency must be a string"
                )
            raw_amount = flows.journal_amount[index]
            if (
                isinstance(raw_amount, bool)
                or not isinstance(raw_amount, (int, float, np.integer, np.floating))
                or not np.isfinite(float(raw_amount))
            ):
                raise AccountingError(
                    f"{quarter}: D2 journal row {index} amount must be a finite number"
                )
            if flows.journal_org[index] is not None:
                raise AccountingError(
                    f"{quarter}: D2 journal row {index} carries journal_org="
                    f"{flows.journal_org[index]!r}; D2 rows are contract-identified "
                    "by journal_event"
                )
            actual_rows.append(
                (
                    str(journal_kind),
                    raw_debit_i,
                    raw_credit_i,
                    raw_currency,
                    float(raw_amount),
                    event_id,
                )
            )

        def _row_key(
            row: tuple[str, int, int, str, float, str],
        ) -> tuple[str, int, int, str, float, str]:
            return (
                row[0],
                row[1],
                row[2],
                row[3],
                round(row[4], 12),
                row[5],
            )

        expected_keys = sorted(_row_key(row) for row in expected_rows)
        actual_keys = sorted(_row_key(row) for row in actual_rows)
        if expected_keys != actual_keys:
            raise AccountingError(
                f"{quarter}: D2 journal rows do not match applied events exactly: "
                f"expected={expected_keys} actual={actual_keys}"
            )
        for event in admitted_events:
            if event.kind not in event_kinds:  # pragma: no cover - apply already guards
                raise AccountingError(
                    f"{quarter}: unknown export receivable event kind {event.kind!r}"
                )

    # --- 7b. H3F-D3 independent CMEA clearing --------------------------------
    d3_event_ids = {
        *state.cmea_clearing_event_ids,
        *opening.cmea_clearing_event_ids,
        *(event.event_id for event in flows.cmea_clearing_events),
    }
    d3_floor = int(cmea_clearing_account_floor(state))
    touches_d3_account = bool(
        np.any(np.asarray(debit, dtype=np.int64) >= d3_floor)
        or np.any(np.asarray(credit, dtype=np.int64) >= d3_floor)
    )
    d3_active = bool(
        opening.cmea_clearing_accounts
        or opening.cmea_clearing_entries
        or opening.cmea_clearing_transfers
        or opening.cmea_clearing_event_ids
        or opening.cmea_clearing_regime is not None
        or opening.cmea_clearing_settlements
        or state.cmea_clearing_accounts
        or state.cmea_clearing_entries
        or state.cmea_clearing_transfers
        or state.cmea_clearing_event_ids
        or state.cmea_clearing_regime is not None
        or state.cmea_clearing_settlements
        or flows.cmea_clearing_events
        or flows.cmea_clearing_import_payment
        or flows.cmea_clearing_export_pending
        or flows.cmea_clearing_export_settled
        or flows.cmea_clearing_positions
        or flows.cmea_clearing_overdue
        or flows.cmea_clearing_contract_prices
        or any(kind_name in _D3_JOURNAL_KINDS for kind_name in flows.journal_kind)
        or any(
            isinstance(value, str) and value in d3_event_ids
            for value in flows.journal_event
        )
        or touches_d3_account
    )
    if d3_active:
        if cmea_clearing_policy is None:
            raise AccountingError(
                f"{quarter}: D3 clearing activity requires the admitted "
                "cmea_clearing_policy"
            )
        if d2_active:
            raise AccountingError(
                f"{quarter}: D2 and D3 activity may not share one tick"
            )
        if (
            state.treasury_loan_principal > 0.0
            or state.treasury_interest_arrears > 0.0
            or state.treasury_loan_maturity_tick >= 0.0
        ):
            raise AccountingError(
                f"{quarter}: D3 clearing may not run with a D1 Treasury loan"
            )
        try:
            validate_clearing_policy(cmea_clearing_policy)
            expected_regime = CmeaClearingRegimeState(
                term_quarters=int(cmea_clearing_policy.term_quarters),
                counterparties=tuple(cmea_clearing_policy.counterparties),
                contracts=tuple(cmea_clearing_policy.contracts),
                clearing_group=tuple(cmea_clearing_policy.clearing_group),
            )
            if state.cmea_clearing_regime != expected_regime:
                raise ValueError(
                    "the persisted clearing regime differs from the admitted policy"
                )
            validate_clearing_book(
                tuple(opening.cmea_clearing_accounts),
                tuple(opening.cmea_clearing_entries),
                tuple(opening.cmea_clearing_transfers),
                tuple(opening.cmea_clearing_event_ids),
                settlements=tuple(opening.cmea_clearing_settlements),
                completed_ticks=int(flows.tick),
                commodity_ids=tuple(network.commodity_ids),
                policy=cmea_clearing_policy,
            )
            (
                expected_imports,
                after_import_accounts,
                after_import_entries,
                after_import_ids,
                generated_imports,
            ) = clearing_import_allocation(
                opening, parameters, network, cmea_clearing_policy
            )
            expected_deliveries = clearing_delivery_entries(
                state,
                network,
                cmea_clearing_policy,
                np.asarray(flows.cmea_exports, dtype=np.float64),
            )
            combined_entries = tuple(after_import_entries) + tuple(expected_deliveries)
            combined_ids = tuple(after_import_ids) + tuple(
                entry.entry_id for entry in expected_deliveries
            )
            (
                expected_accounts,
                expected_entries,
                expected_transfers,
                expected_settlements,
                expected_event_ids,
            ) = apply_clearing_events(
                tuple(after_import_accounts),
                combined_entries,
                tuple(opening.cmea_clearing_transfers),
                tuple(opening.cmea_clearing_settlements),
                combined_ids,
                tuple(cmea_clearing_policy.events),
                current_tick=int(flows.tick),
                policy=cmea_clearing_policy,
            )
            validate_clearing_book(
                tuple(state.cmea_clearing_accounts),
                tuple(state.cmea_clearing_entries),
                tuple(state.cmea_clearing_transfers),
                tuple(state.cmea_clearing_event_ids),
                settlements=tuple(state.cmea_clearing_settlements),
                completed_ticks=int(flows.tick) + 1,
                commodity_ids=tuple(network.commodity_ids),
                policy=cmea_clearing_policy,
            )
        except ValueError as exc:
            raise AccountingError(
                f"{quarter}: CMEA clearing continuity rejected: {exc}"
            ) from exc
        finance(
            "cmea_clearing_imports_vs_allocation",
            np.asarray(flows.cmea_imports, dtype=np.float64),
            np.asarray(expected_imports, dtype=np.float64),
            labels=list(network.commodity_ids),
        )
        if tuple(state.cmea_clearing_accounts) != expected_accounts:
            raise AccountingError(
                f"{quarter}: CMEA clearing account book differs from replay"
            )
        if tuple(state.cmea_clearing_entries) != expected_entries:
            raise AccountingError(
                f"{quarter}: CMEA clearing entry book differs from replay"
            )
        if tuple(state.cmea_clearing_transfers) != expected_transfers:
            raise AccountingError(
                f"{quarter}: CMEA clearing transfer log differs from replay"
            )
        if tuple(state.cmea_clearing_settlements) != expected_settlements:
            raise AccountingError(
                f"{quarter}: CMEA clearing settlement log differs from replay"
            )
        if tuple(state.cmea_clearing_event_ids) != expected_event_ids:
            raise AccountingError(
                f"{quarter}: CMEA clearing event log is not the opening log plus "
                "this tick's generated and admitted ids"
            )
        expected_positions = tuple(
            (int(account.counterparty_id), float(account.balance))
            for account in expected_accounts
        )
        if tuple(flows.cmea_clearing_positions) != expected_positions:
            raise AccountingError(
                f"{quarter}: CMEA clearing flow positions differ from the book"
            )
        expected_overdue = tuple(
            (cid, float(amount))
            for cid, amount in sorted(
                clearing_overdue(expected_entries, int(flows.tick)).items()
            )
        )
        if tuple(flows.cmea_clearing_overdue) != expected_overdue:
            raise AccountingError(
                f"{quarter}: CMEA clearing overdue amounts differ from the book"
            )
        finance(
            "cmea_clearing_import_payment_vs_entries",
            np.asarray([float(flows.cmea_clearing_import_payment)]),
            np.asarray(
                [float(sum(entry.amount for entry in generated_imports))]
            ),
            labels=["cmea_clearing_import_payment"],
        )
        finance(
            "cmea_clearing_export_pending_vs_entries",
            np.asarray([float(flows.cmea_clearing_export_pending)]),
            np.asarray(
                [float(sum(entry.amount for entry in expected_deliveries))]
            ),
            labels=["cmea_clearing_export_pending"],
        )
        finance(
            "cmea_clearing_export_settled_vs_events",
            np.asarray([float(flows.cmea_clearing_export_settled)]),
            np.asarray(
                [
                    float(
                        sum(
                            event.amount
                            for event in cmea_clearing_policy.events
                            if event.kind == "settle_export"
                        )
                    )
                ]
            ),
            labels=["cmea_clearing_export_settled"],
        )
        expected_contract_prices = tuple(
            (contract.contract_id, float(contract.price))
            for contract in cmea_clearing_policy.contracts
        )
        if tuple(flows.cmea_clearing_contract_prices) != expected_contract_prices:
            raise AccountingError(
                f"{quarter}: CMEA clearing contract prices differ from the policy"
            )
        expected_rows: list[tuple[str, int, int, str, float, str]] = []
        expected_rows.extend(
            clearing_journal_rows(
                state, tuple(generated_imports) + tuple(expected_deliveries)
            )
        )
        expected_rows.extend(
            clearing_event_journal_rows(
                state, expected_entries, tuple(cmea_clearing_policy.events)
            )
        )
        actual_rows: list[tuple[str, int, int, str, float, str]] = []
        for index, journal_kind in enumerate(flows.journal_kind):
            raw_debit = flows.journal_debit[index]
            raw_credit = flows.journal_credit[index]
            event_id = flows.journal_event[index]
            def _touches_d3_block(value: object) -> bool:
                if isinstance(value, bool):
                    return False
                if isinstance(value, (int, np.integer)):
                    return int(value) >= d3_floor
                if isinstance(value, (float, np.floating)):
                    return bool(np.isfinite(float(value)) and float(value) >= d3_floor)
                return False

            touches_d3 = _touches_d3_block(raw_debit) or _touches_d3_block(
                raw_credit
            )
            is_d3 = journal_kind in _D3_JOURNAL_KINDS
            event_matches = isinstance(event_id, str) and event_id in d3_event_ids
            if not (touches_d3 or is_d3 or event_matches):
                continue
            if (
                not is_d3
                or event_id is None
                or not isinstance(event_id, str)
                or not touches_d3
            ):
                raise AccountingError(
                    f"{quarter}: journal row {index} ({journal_kind!r}) mixes D3 "
                    "state, accounts or event identity with a non-D3 transaction"
                )
            if (
                isinstance(raw_debit, bool)
                or not isinstance(raw_debit, (int, np.integer))
                or isinstance(raw_credit, bool)
                or not isinstance(raw_credit, (int, np.integer))
            ):
                raise AccountingError(
                    f"{quarter}: D3 journal row {index} accounts must be strict integers"
                )
            raw_tick = flows.journal_tick[index]
            if isinstance(raw_tick, bool) or not isinstance(raw_tick, (int, np.integer)):
                raise AccountingError(
                    f"{quarter}: D3 journal row {index} tick must be a strict integer"
                )
            if int(raw_tick) != int(flows.tick):
                raise AccountingError(
                    f"{quarter}: D3 journal row {index} tick {raw_tick} != "
                    f"flow tick {flows.tick}"
                )
            raw_leg = flows.journal_leg[index]
            if isinstance(raw_leg, bool) or not isinstance(raw_leg, (int, np.integer)):
                raise AccountingError(
                    f"{quarter}: D3 journal row {index} leg must be a strict integer"
                )
            if int(raw_leg) != 0:
                raise AccountingError(
                    f"{quarter}: D3 journal row {index} starts at leg {raw_leg!r}; "
                    "every D3 row is its own one-leg transaction"
                )
            if index + 1 < len(flows.journal_leg):
                next_leg = flows.journal_leg[index + 1]
                if (
                    isinstance(next_leg, bool)
                    or not isinstance(next_leg, (int, np.integer))
                    or int(next_leg) != 0
                ):
                    raise AccountingError(
                        f"{quarter}: D3 journal row {index} does not end its "
                        "transaction"
                    )
            raw_currency = flows.journal_currency[index]
            if raw_currency != CMEA_CURRENCY:
                raise AccountingError(
                    f"{quarter}: D3 journal row {index} currency must be "
                    f"{CMEA_CURRENCY!r}, got {raw_currency!r}"
                )
            raw_amount = flows.journal_amount[index]
            if (
                isinstance(raw_amount, bool)
                or not isinstance(raw_amount, (int, float, np.integer, np.floating))
                or not np.isfinite(float(raw_amount))
            ):
                raise AccountingError(
                    f"{quarter}: D3 journal row {index} amount must be a finite number"
                )
            if flows.journal_org[index] is not None:
                raise AccountingError(
                    f"{quarter}: D3 journal row {index} carries journal_org"
                )
            actual_rows.append(
                (
                    str(journal_kind),
                    int(raw_debit),
                    int(raw_credit),
                    str(raw_currency),
                    float(raw_amount),
                    event_id,
                )
            )
        def _d3_row_key(
            row: tuple[str, int, int, str, float, str],
        ) -> tuple[str, int, int, str, float, str]:
            return (row[0], row[1], row[2], row[3], round(row[4], 12), row[5])

        if sorted(map(_d3_row_key, actual_rows)) != sorted(
            map(_d3_row_key, expected_rows)
        ):
            raise AccountingError(
                f"{quarter}: D3 journal rows do not match generated entries and "
                "events exactly"
            )

    # --- 8. regional household-channel stocks ---------------------------------
    dwelling_delta = np.asarray(state.dwelling_stock, dtype=np.float64) - np.asarray(
        opening.dwelling_stock, dtype=np.float64
    )
    hh_region = np.asarray(state.household_region, dtype=np.int64)
    hh_weight = np.asarray(state.household_weight, dtype=np.float64)
    # P03: dwelling stock grows from formal housing delivery AND private
    # second-economy construction installation; both are real completions.
    housing_delivered = flows.delivered[housing_cells] + np.bincount(
        hh_region,
        weights=hh_weight * np.asarray(flows.private_completed, dtype=np.float64),
        minlength=R,
    )
    material_at_most(
        "dwelling_completion_le_housing_delivery",
        dwelling_delta,
        housing_delivered,
        labels=region_labels,
    )
    material_at_most(
        "dwelling_delta_nonnegative",
        np.zeros(R),
        dwelling_delta,
        labels=region_labels,
    )
    # P03: durable ownership is a per-household stock; continuity holds against
    # the household-level acquired/retired flows (never a regional stock).
    durable_close = np.asarray(state.household_durable_owned, dtype=np.float64)
    durable_open = np.asarray(opening.household_durable_owned, dtype=np.float64)
    durable_delta = np.bincount(
        hh_region, weights=hh_weight * (durable_close - durable_open).sum(axis=1), minlength=R
    )
    durable_trans = np.bincount(
        hh_region,
        weights=hh_weight
        * (
            np.asarray(flows.durable_acquired, dtype=np.float64).sum(axis=1)
            - np.asarray(flows.durable_retired, dtype=np.float64).sum(axis=1)
        ),
        minlength=R,
    )
    material(
        "durable_stock_continuity",
        durable_delta,
        durable_trans,
        labels=region_labels,
    )

    # --- 9. distribution used views (memo tying flows.used to real releases) --
    distribution_rows = np.nonzero(
        np.isin(demand_purpose, [_P_PROCUREMENT, _P_RETAIL])
        & (demand_cells >= 0)
        & np.isin(
            np.asarray(network.cell_pool, dtype=np.int64)[np.clip(demand_cells, 0, S - 1)],
            [_POOL_WHOLESALE, _POOL_RETAIL],
        )
    )[0]
    if distribution_rows.size:
        release = continuity.edge_out_all + continuity.household_channel
        material(
            "distribution_used_views_match_release",
            flows.used[distribution_rows],
            release[demand_cells[distribution_rows]],
            labels=[demand_labels[int(d)] for d in distribution_rows],
        )

    # --- residual snapshot slots -------------------------------------------
    flows.material_balance_residual = continuity.stock_residual.copy()
    flows.material_balance_tolerance = continuity.stock_tolerance.copy()
    finance_residual, finance_tolerance = finance_balance_residuals(state, flows)
    flows.finance_balance_residual = finance_residual
    flows.finance_balance_tolerance = finance_tolerance

    # --- P03 household identities: time endowment, postponement, sources ----
    household_parameters = getattr(network, "household_parameters", None)
    if household_parameters is not None:
        time = household_parameters.time
        welfare_p = household_parameters.welfare
        working = np.asarray(state.household_working_adults, dtype=np.float64)
        time_lhs = (
            time.formal_hours_per_worker * working
            + np.asarray(flows.household_plot_hours, dtype=np.float64)
            + np.asarray(flows.household_second_hours, dtype=np.float64)
            + np.asarray(flows.household_queue_hours, dtype=np.float64)
            + np.asarray(flows.household_search_hours, dtype=np.float64)
            + np.asarray(flows.household_leisure_hours, dtype=np.float64)
        )
        material(
            "household_time_endowment",
            time_lhs,
            time.time_endowment_hours * working,
            labels=household_labels,
        )
        durable_backlog = np.asarray(state.household_durable_backlog, dtype=np.float64)
        durable_wait = np.asarray(state.household_durable_wait, dtype=np.float64)
        housing_wait = np.asarray(state.household_housing_wait, dtype=np.float64)
        expected_postponement = welfare_p.durable_postponement_cost * (
            durable_backlog.sum(axis=1) * (1.0 + durable_wait.mean(axis=1))
        ) + welfare_p.housing_postponement_cost * np.asarray(
            flows.household_overcrowding, dtype=np.float64
        ) * (1.0 + housing_wait)
        material(
            "household_postponement_cost",
            np.asarray(flows.household_postponement_cost, dtype=np.float64),
            expected_postponement,
            labels=household_labels,
        )
        sources = (
            np.asarray(flows.household_formal_h, dtype=np.float64)
            + np.asarray(flows.household_plot_self_h, dtype=np.float64)
            + np.asarray(flows.household_plot_market_h, dtype=np.float64)
            + np.asarray(flows.household_second_h, dtype=np.float64)
        )
        _require(
            bool(
                np.all(sources <= np.asarray(flows.household_realized_h, dtype=np.float64) + 1e-6)
            ),
            quarter,
            "household source channels exceed the realised H-level basket",
        )

    return InvariantSummary(
        max_material_abs_residual=max_material,
        max_material_tolerance_ratio=max_material_ratio,
        max_finance_abs_residual=max_finance,
        max_finance_tolerance_ratio=max_finance_ratio,
        checked_cells=S,
        per_ledger=per_ledger,
        expired_leftover_by_cell=np.asarray(continuity.services_leftover, dtype=np.float64).copy(),
    )


# ---------------------------------------------------------------------------
# Department aggregation (plan section 5; use-derived analytical layer).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DepartmentSummary:
    """Use-derived Department I/II aggregation of one tick (admin prices).

    Realized use values measure this tick's actual uses; attributed output
    values split each source's gross production by its same-tick delivery
    purpose shares, so the five buckets sum exactly to the gross domestic
    output value.  ``service_attributed_output_value`` complements the pinned
    field list with the services attribution bucket.
    """

    department_I_realized_use_value: float = 0.0
    department_II_realized_use_value: float = 0.0
    service_use_productive: float = 0.0
    service_use_household: float = 0.0
    exports_value: float = 0.0
    unclassified_output_value: float = 0.0
    department_I_attributed_output_value: float = 0.0
    department_II_attributed_output_value: float = 0.0
    service_attributed_output_value: float = 0.0
    gross_domestic_output_value: float = 0.0
    commodity_use_quantities: dict[str, dict[str, float]] = field(default_factory=dict)

    @property
    def use_value(self) -> dict[str, float]:
        """Five-bucket use view (services = productive + household)."""
        return {
            "department_I": self.department_I_realized_use_value,
            "department_II": self.department_II_realized_use_value,
            "services": self.service_use_productive + self.service_use_household,
            "exports": self.exports_value,
            "unclassified": self.unclassified_output_value,
        }

    @property
    def attributed_output_value(self) -> dict[str, float]:
        """Five-bucket attributed gross output view."""
        return {
            "department_I": self.department_I_attributed_output_value,
            "department_II": self.department_II_attributed_output_value,
            "services": self.service_attributed_output_value,
            "exports": self.exports_value,
            "unclassified": self.unclassified_output_value,
        }


def derive_departments(
    flows: MaterialTickFlows,
    prices: MaterialPrices,
    network: MaterialNetwork | None = None,
    *,
    state: MaterialState | None = None,
    housing_completed: float | None = None,
) -> DepartmentSummary:
    """Aggregate one tick's flows into Department I/II use and output views.

    Requires the network catalog (delivery purposes, cell ownership and the
    commodity axis are not derivable from the flows alone) and the closing
    state (household weights/regions for represented totals); both fail
    closed with :class:`AccountingError` when omitted.  ``housing_completed``
    is the total dwelling units completed this tick — a runner-boundary
    quantity that must be supplied whenever construction is declared.
    """
    if network is None:
        raise AccountingError(
            "derive_departments requires the material network catalog "
            "(delivery purposes are not derivable from flows alone)"
        )
    if state is None:
        raise AccountingError(
            "derive_departments requires the closing state "
            "(household weights/regions for represented totals)"
        )
    commodity_ids = network.commodity_ids
    G = len(commodity_ids)
    S = int(np.asarray(network.cell_owner_kind).shape[0])
    K = int(np.asarray(network.input_cell).shape[0])
    R = int(state.dwelling_stock.shape[0])
    services_g = _role_index(network, "service")
    construction_g = (
        _role_index(network, "construction")
    )
    food_g = _role_index(network, "food")
    if housing_completed is None:
        if construction_g >= 0:
            raise AccountingError(
                "derive_departments requires housing_completed (dwelling units "
                "completed this tick) when construction is declared"
            )
        housing_completed = 0.0

    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_stage = np.asarray(network.cell_stage, dtype=np.int64)
    src = np.asarray(network.edge_source_cell, dtype=np.int64)
    purpose = np.asarray(network.edge_purpose, dtype=np.int64)
    edge_delivered = np.asarray(flows.edge_delivered, dtype=np.float64)

    def _out(mask: np.ndarray) -> np.ndarray:
        if bool(np.any(mask)):
            return np.bincount(src[mask], weights=edge_delivered[mask], minlength=S)
        return np.zeros(S, dtype=np.float64)

    production = np.asarray(network.B.T @ np.asarray(flows.activity_realized)).ravel()
    production = production.astype(np.float64)
    services_cells = _ephemeral_commodity_mask(network, cell_commodity)

    # Logistics services are consumed out of transport output cells.
    logistics = np.zeros(S, dtype=np.float64)
    transport_orgs = np.asarray(network.edge_transport_org, dtype=np.int64)
    org_output = np.asarray(network.org_output_cell, dtype=np.int64)
    served = (transport_orgs >= 0) & (transport_orgs < org_output.shape[0])
    if bool(np.any(served)):
        cells = org_output[transport_orgs[served]]
        ok = cells >= 0
        if bool(np.any(ok)):
            np.add.at(
                logistics,
                cells[ok],
                np.asarray(flows.edge_service_used, dtype=np.float64)[served][ok],
            )

    # Plot household channels (self-use and direct market), region-weighted.
    plot_channel = np.zeros(S, dtype=np.float64)
    self_quantity = np.zeros(R, dtype=np.float64)
    direct_quantity = np.zeros(R, dtype=np.float64)
    if food_g >= 0:
        ready_price = float(prices.standard[food_g])
        weight = np.asarray(state.household_weight, dtype=np.float64)
        region = np.asarray(state.household_region, dtype=np.int64)
        self_quantity = (
            np.bincount(
                region,
                weights=weight * np.asarray(flows.household_self_use, dtype=np.float64),
                minlength=R,
            )
            / ready_price
        )
        direct_quantity = (
            np.bincount(
                region,
                weights=weight * np.asarray(flows.household_plot_income_direct, dtype=np.float64),
                minlength=R,
            )
            / ready_price
        )
        plot_self = np.asarray(network.plot_ready_self_cell, dtype=np.int64)
        plot_market = np.asarray(network.plot_ready_market_cell, dtype=np.int64)
        self_ok = plot_self >= 0
        market_ok = plot_market >= 0
        if bool(np.any(self_ok)):
            plot_channel[plot_self[self_ok]] += self_quantity[self_ok]
        if bool(np.any(market_ok)):
            plot_channel[plot_market[market_ok]] += direct_quantity[market_ok]

    i_purpose_out = (
        _out(purpose == _P_INTERMEDIATE)
        + _out(purpose == _P_INVESTMENT)
        + _out(purpose == _P_PROCUREMENT)
        + _out(purpose == _P_PRIVATE_PLOT)
    )
    ii_purpose_out = _out(purpose == _P_HOUSING) + _out(purpose == _P_RETAIL)
    exports_purpose_out = _out(purpose == _P_EXPORT_CMEA) + _out(purpose == _P_EXPORT_CONVERTIBLE)
    services_productive_out = (
        logistics + _out(purpose == _P_INTERMEDIATE) + _out(purpose == _P_PRIVATE_PLOT)
    )
    services_household_out = _out(purpose == _P_RETAIL)

    cell_price = np.asarray(
        [prices.price_for(int(cell_commodity[c]), int(cell_stage[c])) for c in range(S)],
        dtype=np.float64,
    )
    production_value = production * cell_price
    gross_output = float(np.sum(production_value))

    # Household edges never source producer cells (they mirror the retail and
    # plot channels), so the channel terms complete the attribution outflows.
    total_out = (
        i_purpose_out
        + ii_purpose_out
        + exports_purpose_out
        + services_productive_out
        + services_household_out
        + plot_channel
    )
    share = np.zeros(S, dtype=np.float64)
    positive = total_out > 1e-300
    np.divide(1.0, total_out, out=share, where=positive)
    # A cell whose recorded outflow has decayed into subnormal dust would give
    # share = inf and poison the whole attribution; such output is nil.
    share[~np.isfinite(share)] = 0.0

    def _attributed(outflow: np.ndarray, mask: np.ndarray) -> float:
        return float(np.sum(production_value * outflow * share * mask))

    goods_mask = ~services_cells
    attributed_i = _attributed(i_purpose_out, goods_mask)
    attributed_ii = _attributed(ii_purpose_out + plot_channel, goods_mask)
    attributed_exports = _attributed(exports_purpose_out, goods_mask)
    attributed_services = _attributed(services_productive_out, services_cells) + (
        _attributed(services_household_out, services_cells)
    )
    unclassified = max(
        0.0,
        gross_output - attributed_i - attributed_ii - attributed_exports - attributed_services,
    )

    # --- realized use values -------------------------------------------------
    input_cells = np.asarray(network.input_cell, dtype=np.int64)
    input_commodity = cell_commodity[input_cells]
    input_index = np.asarray(network.demand_input_index, dtype=np.int64)
    production_rows = input_index >= 0
    k_rows = input_index[production_rows]
    k_used = np.zeros(K, dtype=np.float64)
    k_used[k_rows] = np.asarray(flows.used, dtype=np.float64)[production_rows]
    input_price = cell_price[input_cells]
    input_is_services = services_cells[input_cells]
    intermediate_value = float(np.sum(k_used[~input_is_services] * input_price[~input_is_services]))
    services_input_value = float(np.sum(k_used[input_is_services] * input_price[input_is_services]))
    logistics_quantity = float(np.sum(np.asarray(flows.edge_service_used, dtype=np.float64)))
    services_price = float(prices.standard[services_g]) if services_g >= 0 else 0.0
    logistics_value = logistics_quantity * services_price

    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    demand_cells = np.asarray(network.demand_cell, dtype=np.int64)
    investment_rows = (demand_purpose == _P_INVESTMENT) & (demand_cells >= 0)
    investment_quantities = np.bincount(
        cell_commodity[demand_cells[investment_rows]],
        weights=np.asarray(flows.used, dtype=np.float64)[investment_rows],
        minlength=G,
    )
    investment_stages = cell_stage[demand_cells[investment_rows]]
    investment_goods = cell_commodity[demand_cells[investment_rows]]
    investment_prices = np.asarray(prices.standard, dtype=np.float64)[investment_goods].copy()
    if food_g >= 0:
        raw_food_investment = (investment_goods == food_g) & (
            investment_stages == STAGE_CODES["raw"]
        )
        investment_prices[raw_food_investment] = float(prices.food_raw)
    investment_value = float(
        np.sum(np.asarray(flows.used, dtype=np.float64)[investment_rows] * investment_prices)
    )

    household_goods = [
        g
        for g in range(G)
        if commodity_ids[g] in _household_parent_ids(network) and g != services_g
    ]
    realized = np.asarray(flows.household_realized, dtype=np.float64)
    weight = np.asarray(state.household_weight, dtype=np.float64)
    household_quantities = weight @ realized if realized.size else np.zeros(G, dtype=np.float64)
    household_value = float(
        sum(float(household_quantities[g]) * float(prices.standard[g]) for g in household_goods)
    )
    services_household_qty = float(household_quantities[services_g]) if services_g >= 0 else 0.0
    services_household_value = services_household_qty * services_price
    housing_value = (
        float(housing_completed) * float(prices.standard[construction_g])
        if construction_g >= 0
        else 0.0
    )
    exports_quantity = np.asarray(flows.cmea_exports, dtype=np.float64) + np.asarray(
        flows.convertible_exports, dtype=np.float64
    )
    export_stage = np.asarray(
        [
            STAGE_CODES["ready"] if cid == _role_id(network, "food") else STAGE_CODES["standard"]
            for cid in commodity_ids
        ],
        dtype=np.int64,
    )
    export_prices = np.asarray(
        [prices.price_for(g, int(export_stage[g])) for g in range(G)], dtype=np.float64
    )
    exports_total_value = float(np.sum(exports_quantity * export_prices))

    # --- per-commodity realized use quantities -------------------------------
    commodity_use: dict[str, dict[str, float]] = {}
    for g, cid in enumerate(commodity_ids):
        is_services = services_g == g
        input_qty = float(np.sum(k_used[input_commodity == g]))
        department_i = 0.0 if is_services else input_qty
        department_i += float(investment_quantities[g])
        department_ii = float(household_quantities[g]) if g in household_goods else 0.0
        if g == construction_g:
            department_ii += float(housing_completed)
        commodity_use[cid] = {
            "department_I": department_i,
            "department_II": department_ii,
            "service_use_productive": (input_qty + logistics_quantity) if is_services else 0.0,
            "service_use_household": services_household_qty if is_services else 0.0,
            "exports": float(exports_quantity[g]),
        }

    return DepartmentSummary(
        department_I_realized_use_value=intermediate_value + investment_value,
        department_II_realized_use_value=household_value + housing_value,
        service_use_productive=services_input_value + logistics_value,
        service_use_household=services_household_value,
        exports_value=exports_total_value,
        unclassified_output_value=unclassified,
        department_I_attributed_output_value=attributed_i,
        department_II_attributed_output_value=attributed_ii,
        service_attributed_output_value=attributed_services,
        gross_domestic_output_value=gross_output,
        commodity_use_quantities=commodity_use,
    )


__all__ = [
    "ATOL",
    "RTOL",
    "AccountingError",
    "DepartmentSummary",
    "InvariantSummary",
    "check_material_invariants",
    "derive_departments",
    "finance_balance_residuals",
    "material_balance_residuals",
    "tolerance_for",
]
