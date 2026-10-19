"""H3C: executable routing witnesses, gap measurement and payment reconciliation.

The module contains one thin execution wrapper and read-only measurement.  It
never allocates a bank, stock cell, account or clock of its own: the real
:func:`hsm_lab.engine.material.tick_material` is called exactly once with the
H3C ``routing_allocator`` hook, then the existing accounting gate and (when a
policy is supplied) the H3B procurement-credit funnel are applied.

Only an ``LP-2`` witness with no free flow, no projection loss, no delivery
gap and a clean payment/stock gate is admitted.  ``LP-0`` and ``LP-1`` are
comparison arms: their executable projection is recorded, measured and then the
pre-tick state is restored, so a relaxation can never leak into the main path.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.engine import accounting
from hsm_lab.engine.accounting import ATOL, InvariantSummary, tolerance_for
from hsm_lab.engine.finance import (
    DOMESTIC_CURRENCY,
    AccountKind,
    build_account_directory,
)
from hsm_lab.engine.material import tick_material
from hsm_lab.engine.network import MaterialNetwork
from hsm_lab.engine.state import (
    MaterialForcing,
    MaterialState,
    MaterialStockSnapshot,
    MaterialTickFlows,
    capture_material_stocks,
)
from hsm_lab.institutions import procurement_credit_adapter
from hsm_lab.measurement import flow_funnel
from hsm_lab.planning import feasibility

SCHEMA_VERSION = "hist-routing-execution-v1"
GATE_PREFIX = "HIST_H3C_EXECUTION"
LEVELS: tuple[str, ...] = feasibility.LEVELS


def _reject(message: str) -> None:
    raise ResearchGateError(f"{GATE_PREFIX}: {message}")


@dataclass(frozen=True)
class RoutingJournalRow:
    """One raw journal leg decoded through the canonical account directory."""

    row_index: int
    transaction_index: int
    kind: str
    leg: int
    debit_account: int
    credit_account: int
    debit_owner_kind: str
    debit_owner_id: int
    debit_account_kind: str
    credit_owner_kind: str
    credit_owner_id: int
    credit_account_kind: str
    currency: str
    amount: float
    organization_id: int | None


@dataclass(frozen=True)
class RoutingEdgeRow:
    edge_index: int
    edge_id: int
    demand_index: int
    source_cell: int
    destination_cell: int
    buyer_organization: int
    seller_organization: int
    carrier_organization: int
    planned_x: float
    submitted_x: float
    allocated: float
    delivered: float
    service_used: float
    service_fee: float
    goods_payment: float
    freight_payment: float
    planned_gap: float
    submitted_gap: float
    delivery_gap: float


@dataclass(frozen=True)
class RoutingDemandRow:
    demand_index: int
    desired: float
    gross: float
    ordered: float
    planned: float
    submitted: float
    delivered: float
    used: float
    shortfall: float
    shortfall_residual: float
    delivery_gap: float
    financial_blocked: float
    physical_blocked: float


@dataclass(frozen=True)
class RoutingOrganizationPaymentRow:
    organization_id: int
    expected_purchases: float
    actual_purchases: float
    purchase_residual: float
    expected_receipts: float
    actual_receipts: float
    receipt_residual: float
    expected_pair_total: float
    actual_pair_total: float
    pair_residual: float


@dataclass(frozen=True)
class RoutingExecutionMeasurement:
    schema_version: str
    tick: int
    quarter: str
    level: str
    execution_status: str
    edge_rows: tuple[RoutingEdgeRow, ...]
    demand_rows: tuple[RoutingDemandRow, ...]
    organization_rows: tuple[RoutingOrganizationPaymentRow, ...]
    journal: tuple[RoutingJournalRow, ...]
    max_edge_gap: float
    max_delivery_gap: float
    max_shortfall_residual: float
    max_payment_residual: float
    max_stock_residual: float
    max_bank_residual: float
    free_source_flow: float
    free_demand_flow: float
    lost_free_delivery: float
    projected: bool
    project_note: str


@dataclass(frozen=True)
class RoutingExecutionResult:
    schema_version: str
    level: str
    certificates: tuple[feasibility.RoutingCertificate, ...]
    selected_certificate: feasibility.RoutingCertificate
    nested: feasibility.NestedCheck
    boundary: dict[str, Any]
    problems: tuple[feasibility.RoutingProblem, ...]
    flows: MaterialTickFlows
    gate: InvariantSummary
    measurement: RoutingExecutionMeasurement
    procurement_funnel: Any | None
    planned_x: np.ndarray
    submitted_x: np.ndarray
    actual_allocated: np.ndarray
    actual_delivered: np.ndarray
    execution_status: str


class RoutingExecutionFailure(ResearchGateError):
    """A failed H3C arm after the pre-tick rollback snapshot was captured."""

    def __init__(
        self,
        *,
        phase: str,
        cause: BaseException,
        failed_flows: MaterialTickFlows | None,
        failed_trace: dict[str, Any],
        certificates: tuple[feasibility.RoutingCertificate, ...],
    ) -> None:
        super().__init__(f"{GATE_PREFIX}: {phase} failed: {cause}")
        self.phase = phase
        self.cause = cause
        self.failed_flows = failed_flows
        self.failed_trace = failed_trace
        self.certificates = certificates

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe failure evidence, including arbitrary-dimensional arrays."""
        return {
            "phase": self.phase,
            "cause": f"{type(self.cause).__name__}: {self.cause}",
            "failed_flows": _jsonable(self.failed_flows),
            "failed_trace": _jsonable(self.failed_trace),
            "certificates": [
                _certificate_payload(certificate) for certificate in self.certificates
            ],
        }


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "__dataclass_fields__"):
        return {field: _jsonable(getattr(value, field)) for field in value.__dataclass_fields__}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    return value


def _certificate_payload(certificate: feasibility.RoutingCertificate) -> dict[str, Any]:
    return {
        "level": certificate.level,
        "status": certificate.status,
        "solver_status": certificate.solver_status,
        "solver_message": certificate.solver_message,
        "solver_feasible": certificate.solver_feasible,
        "problem_hash": certificate.problem_hash,
        "boundary_hash": certificate.boundary_hash,
        "demand_hash": certificate.demand_hash,
        "objective_hash": certificate.objective_hash,
        "constraint_hash": certificate.constraint_hash,
        "edge_id": certificate.edge_id.tolist(),
        "x": certificate.x.tolist(),
        "u": certificate.u.tolist(),
        "v": certificate.v.tolist(),
        "shortfall": certificate.shortfall.tolist(),
        "shortfall_total": certificate.shortfall_total,
        "dual_ub": certificate.dual_ub.tolist(),
        "dual_eq": certificate.dual_eq.tolist(),
        "dual_lower": certificate.dual_lower.tolist(),
        "dual_upper": certificate.dual_upper.tolist(),
        "row_names": list(certificate.row_names),
        "row_activity": certificate.row_activity.tolist(),
        "row_residual": certificate.row_residual.tolist(),
        "row_slack": certificate.row_slack.tolist(),
        "variable_count": certificate.variable_count,
        "row_count": certificate.row_count,
        "nnz": certificate.nnz,
        "build_wall_s": certificate.build_wall_s,
        "solve_wall_s": certificate.solve_wall_s,
        "no_demand": certificate.no_demand,
        "free_flow": certificate.free_flow,
        "max_abs_residual": certificate.max_abs_residual,
        "unique_bottleneck": certificate.unique_bottleneck,
    }


def _copy_trace(trace: dict[str, Any]) -> dict[str, Any]:
    return {key: _jsonable(value) for key, value in trace.items()}


def _restore_state(state: MaterialState, snapshot: MaterialState) -> None:
    for field_name in state.__dataclass_fields__:
        setattr(state, field_name, copy.deepcopy(getattr(snapshot, field_name)))


def _close(name: str, actual: np.ndarray, expected: np.ndarray) -> float:
    actual = np.asarray(actual, dtype=np.float64)
    expected = np.asarray(expected, dtype=np.float64)
    tolerance = np.asarray(tolerance_for(actual, expected), dtype=np.float64)
    residual = np.abs(actual - expected)
    if bool(np.any(residual > tolerance)):
        bad = int(np.argmax(residual - tolerance))
        _reject(
            f"{name}[{bad}] actual {float(actual.ravel()[bad])!r} != "
            f"expected {float(expected.ravel()[bad])!r}"
        )
    return float(np.max(residual)) if residual.size else 0.0


def _at_most(name: str, lhs: np.ndarray, rhs: np.ndarray) -> float:
    lhs = np.asarray(lhs, dtype=np.float64)
    rhs = np.asarray(rhs, dtype=np.float64)
    tolerance = np.asarray(tolerance_for(lhs, rhs), dtype=np.float64)
    residual = np.maximum(lhs - rhs, 0.0)
    if bool(np.any(residual > tolerance)):
        bad = int(np.argmax(residual - tolerance))
        _reject(f"{name}[{bad}] {float(lhs.ravel()[bad])!r} exceeds {float(rhs.ravel()[bad])!r}")
    return float(np.max(residual)) if residual.size else 0.0


def _decode_journal(
    state: MaterialState, flows: MaterialTickFlows
) -> tuple[RoutingJournalRow, ...]:
    directory = build_account_directory(state)
    reverse = {account: key for key, account in directory.items()}
    kind = np.asarray(flows.journal_kind, dtype=object)
    debit = np.asarray(flows.journal_debit, dtype=np.int64)
    credit = np.asarray(flows.journal_credit, dtype=np.int64)
    currency = np.asarray(flows.journal_currency, dtype=object)
    amount = np.asarray(flows.journal_amount, dtype=np.float64)
    org = np.asarray(flows.journal_org, dtype=object)
    leg = np.asarray(flows.journal_leg, dtype=np.int64)
    lengths = {array.shape[0] for array in (kind, debit, credit, currency, amount, org, leg)}
    if len(lengths) != 1:
        _reject("journal columns do not align")
    count = int(kind.shape[0])
    if count == 0:
        return ()
    if bool(np.any(~np.isfinite(amount))) or bool(np.any(amount <= 0.0)):
        _reject("journal amounts must be finite and strictly positive")
    if int(leg[0]) != 0:
        _reject("journal leg index must start at 0")
    if count > 1:
        sequential = np.diff(leg) == 1
        restart = leg[1:] == 0
        if not bool(np.all(sequential | restart)):
            _reject("journal leg indices must restart at 0 and increment by 1")
    run_id = np.cumsum(leg == 0) - 1
    rows: list[RoutingJournalRow] = []
    for row in range(count):
        debit_key = reverse.get(int(debit[row]))
        credit_key = reverse.get(int(credit[row]))
        if debit_key is None or credit_key is None:
            _reject(f"journal row {row} names an account outside the directory")
        rows.append(
            RoutingJournalRow(
                row_index=row,
                transaction_index=int(run_id[row]),
                kind=str(kind[row]),
                leg=int(leg[row]),
                debit_account=int(debit[row]),
                credit_account=int(credit[row]),
                debit_owner_kind=debit_key[0],
                debit_owner_id=int(debit_key[1]),
                debit_account_kind=debit_key[3],
                credit_owner_kind=credit_key[0],
                credit_owner_id=int(credit_key[1]),
                credit_account_kind=credit_key[3],
                currency=str(currency[row]),
                amount=float(amount[row]),
                organization_id=(
                    None if org[row] is None else int(org[row])  # type: ignore[arg-type]
                ),
            )
        )
    return tuple(rows)


def _organization_payment_rows(
    state: MaterialState,
    flows: MaterialTickFlows,
    network: MaterialNetwork,
    boundary: dict[str, np.ndarray],
    journal: tuple[RoutingJournalRow, ...],
) -> tuple[tuple[RoutingOrganizationPaymentRow, ...], float]:
    org_ids = np.asarray(state.organization_id, dtype=np.int64)
    row_by_id = {int(org_id): row for row, org_id in enumerate(org_ids)}
    org_count = int(org_ids.shape[0])
    edge_buyer = np.asarray(network.edge_buyer_org, dtype=np.int64)
    edge_source = np.asarray(network.edge_source_cell, dtype=np.int64)
    edge_transport = np.asarray(network.edge_transport_org, dtype=np.int64)
    edge_purpose = np.asarray(network.edge_purpose, dtype=np.int64)
    household_edges = edge_purpose == _purpose_code("household")
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    delivered = np.asarray(flows.edge_delivered, dtype=np.float64)
    fee = np.asarray(flows.edge_service_fee, dtype=np.float64)
    unit_price = np.asarray(boundary["edge_unit_price"], dtype=np.float64)
    goods = delivered * unit_price

    seller_rows = np.full(edge_source.shape[0], -1, dtype=np.int64)
    is_org_source = cell_owner_kind[edge_source] == 0
    for edge in np.flatnonzero(is_org_source):
        seller_rows[edge] = row_by_id.get(int(cell_owner_id[edge_source[edge]]), -1)

    expected_purchases = np.zeros(org_count, dtype=np.float64)
    buyer_mask = edge_buyer >= 0
    if bool(np.any(buyer_mask)):
        expected_purchases += np.bincount(
            edge_buyer[buyer_mask], weights=(goods + fee)[buyer_mask], minlength=org_count
        )
    expected_receipts = np.zeros(org_count, dtype=np.float64)
    seller_mask = (seller_rows >= 0) & (goods > 0.0) & ~household_edges
    if bool(np.any(seller_mask)):
        expected_receipts += np.bincount(
            seller_rows[seller_mask], weights=goods[seller_mask], minlength=org_count
        )
    carrier_mask = (edge_transport >= 0) & (fee > 0.0) & ~household_edges
    if bool(np.any(carrier_mask)):
        expected_receipts += np.bincount(
            edge_transport[carrier_mask], weights=fee[carrier_mask], minlength=org_count
        )

    expected_pairs: dict[tuple[int, int], float] = {}
    for edge in np.flatnonzero(buyer_mask & ~household_edges):
        buyer = int(edge_buyer[edge])
        seller = int(seller_rows[edge])
        if seller >= 0 and goods[edge] > 0.0:
            key = (buyer, seller)
            expected_pairs[key] = expected_pairs.get(key, 0.0) + float(goods[edge])
        carrier = int(edge_transport[edge])
        if carrier >= 0 and fee[edge] > 0.0:
            key = (buyer, carrier)
            expected_pairs[key] = expected_pairs.get(key, 0.0) + float(fee[edge])

    actual_purchases = np.zeros(org_count, dtype=np.float64)
    actual_receipts = np.zeros(org_count, dtype=np.float64)
    actual_pairs: dict[tuple[int, int], float] = {}
    for row in journal:
        if row.kind != "goods_payment" or row.currency != DOMESTIC_CURRENCY:
            continue
        debit_is_cash = (
            row.debit_owner_kind == "organization"
            and row.debit_account_kind == AccountKind.CASH_DEPOSIT
        )
        credit_is_cash = (
            row.credit_owner_kind == "organization"
            and row.credit_account_kind == AccountKind.CASH_DEPOSIT
        )
        if debit_is_cash:
            debit_row = row_by_id.get(int(row.debit_owner_id), -1)
            if debit_row >= 0:
                actual_purchases[debit_row] += row.amount
        if credit_is_cash:
            credit_row = row_by_id.get(int(row.credit_owner_id), -1)
            if credit_row >= 0:
                actual_receipts[credit_row] += row.amount
        if debit_is_cash and credit_is_cash:
            debit_row = row_by_id.get(int(row.debit_owner_id), -1)
            credit_row = row_by_id.get(int(row.credit_owner_id), -1)
            if debit_row >= 0 and credit_row >= 0:
                key = (debit_row, credit_row)
                actual_pairs[key] = actual_pairs.get(key, 0.0) + row.amount

    residual = max(
        _close("organization_purchases", actual_purchases, expected_purchases),
        _close("organization_receipts", actual_receipts, expected_receipts),
    )
    missing = sorted(set(expected_pairs) - set(actual_pairs))
    extra = sorted(set(actual_pairs) - set(expected_pairs))
    if missing:
        _reject(f"goods_payment journal is missing buyer/seller pair(s) {missing}")
    if extra:
        _reject(f"goods_payment journal has unexpected buyer/seller pair(s) {extra}")
    for key in sorted(expected_pairs):
        residual = max(
            residual,
            _close(
                f"goods_payment_pair[{key[0]}->{key[1]}]",
                np.asarray([actual_pairs[key]]),
                np.asarray([expected_pairs[key]]),
            ),
        )
    rows = tuple(
        RoutingOrganizationPaymentRow(
            organization_id=int(org_ids[row]),
            expected_purchases=float(expected_purchases[row]),
            actual_purchases=float(actual_purchases[row]),
            purchase_residual=float(abs(expected_purchases[row] - actual_purchases[row])),
            expected_receipts=float(expected_receipts[row]),
            actual_receipts=float(actual_receipts[row]),
            receipt_residual=float(abs(expected_receipts[row] - actual_receipts[row])),
            expected_pair_total=float(
                sum(value for (debit, _credit), value in expected_pairs.items() if debit == row)
            ),
            actual_pair_total=float(
                sum(value for (debit, _credit), value in actual_pairs.items() if debit == row)
            ),
            pair_residual=0.0,
        )
        for row in range(org_count)
    )
    return rows, residual


def _non_org_payment_residual(
    state: MaterialState,
    flows: MaterialTickFlows,
    network: MaterialNetwork,
    boundary: dict[str, np.ndarray],
    journal: tuple[RoutingJournalRow, ...],
) -> float:
    """Check plot and Treasury channels that do not use org-to-org journal pairs."""
    purpose = np.asarray(network.edge_purpose, dtype=np.int64)
    buyer = np.asarray(network.edge_buyer_org, dtype=np.int64)
    delivered = np.asarray(flows.edge_delivered, dtype=np.float64)
    fee = np.asarray(flows.edge_service_fee, dtype=np.float64)
    unit_price = np.asarray(boundary["edge_unit_price"], dtype=np.float64)
    goods = delivered * unit_price
    plot_purpose = _purpose_code("private_plot")
    treasury_purposes = {
        _purpose_code("housing"),
        _purpose_code("export_cmea"),
        _purpose_code("export_convertible"),
    }
    plot_mask = (buyer < 0) & (purpose == plot_purpose)
    edge_destination = np.asarray(network.edge_destination_cell, dtype=np.int64)
    edge_region = np.asarray(network.cell_region, dtype=np.int64)
    region_count = int(len(np.asarray(boundary["plot_pool"], dtype=np.float64)))
    expected_plot_by_region = np.zeros(region_count, dtype=np.float64)
    for edge in np.flatnonzero(plot_mask):
        destination = int(edge_destination[edge])
        region = int(edge_region[destination]) if destination >= 0 else -1
        if region >= 0:
            expected_plot_by_region[region] += float(goods[edge] + fee[edge])
    # The represented household -> clearing leg carries the weight-scaled
    # expenditure; reconcile it to the exact regional clearing account, not a
    # national total.
    actual_plot_by_region = np.zeros(region_count, dtype=np.float64)
    for row in journal:
        if (
            row.kind == "goods_payment"
            and row.currency == DOMESTIC_CURRENCY
            and row.debit_owner_kind == "household"
            and row.debit_account_kind == AccountKind.CASH_DEPOSIT
            and row.credit_owner_kind.startswith("plot_clearing")
            and row.credit_account_kind == AccountKind.PLOT_CLEARING
        ):
            region = int(row.credit_owner_id)
            if 0 <= region < region_count:
                actual_plot_by_region[region] += row.amount
    residual = _close(
        "plot_channel_funding_by_region",
        actual_plot_by_region,
        expected_plot_by_region,
    )
    treasury_mask = (buyer < 0) & np.isin(purpose, list(treasury_purposes))
    expected_treasury = float(np.sum((goods + fee)[treasury_mask]))
    actual_treasury = float(
        sum(
            row.amount
            for row in journal
            if row.kind == "goods_payment"
            and row.currency == DOMESTIC_CURRENCY
            and row.debit_owner_kind == "treasury"
            and row.debit_account_kind == AccountKind.CASH_DEPOSIT
        )
    )
    residual = max(
        residual,
        _close(
            "treasury_channel_spending",
            np.asarray([actual_treasury]),
            np.asarray([expected_treasury]),
        ),
    )

    # Counterparty-level checks for the two non-organization payer channels.
    org_ids = np.asarray(state.organization_id, dtype=np.int64)
    edge_source = np.asarray(network.edge_source_cell, dtype=np.int64)
    edge_transport = np.asarray(network.edge_transport_org, dtype=np.int64)
    seller_ids = np.asarray(network.cell_owner_id, dtype=np.int64)[edge_source]
    seller_is_org = np.asarray(network.cell_owner_kind, dtype=np.int64)[edge_source] == 0
    carrier_ids = np.full(edge_transport.shape[0], -1, dtype=np.int64)
    carrier_rows = edge_transport >= 0
    carrier_ids[carrier_rows] = org_ids[edge_transport[carrier_rows]]
    edge_destination = np.asarray(network.edge_destination_cell, dtype=np.int64)
    cell_region = np.asarray(network.cell_region, dtype=np.int64)
    expected_pairs: dict[tuple[str, int, int], float] = {}
    for edge in np.flatnonzero(plot_mask):
        destination = int(edge_destination[edge])
        region = int(cell_region[destination]) if destination >= 0 else -1
        if seller_is_org[edge] and goods[edge] > 0.0:
            key = ("plot_clearing", region, int(seller_ids[edge]))
            expected_pairs[key] = expected_pairs.get(key, 0.0) + float(goods[edge])
        if carrier_ids[edge] >= 0 and fee[edge] > 0.0:
            key = ("plot_clearing", region, int(carrier_ids[edge]))
            expected_pairs[key] = expected_pairs.get(key, 0.0) + float(fee[edge])
    for edge in np.flatnonzero(treasury_mask):
        if seller_is_org[edge] and goods[edge] > 0.0:
            key = ("treasury", 0, int(seller_ids[edge]))
            expected_pairs[key] = expected_pairs.get(key, 0.0) + float(goods[edge])
        if carrier_ids[edge] >= 0 and fee[edge] > 0.0:
            key = ("treasury", 0, int(carrier_ids[edge]))
            expected_pairs[key] = expected_pairs.get(key, 0.0) + float(fee[edge])
    actual_pairs: dict[tuple[str, int, int], float] = {}
    for row in journal:
        if row.kind != "goods_payment" or row.currency != DOMESTIC_CURRENCY:
            continue
        if (
            row.credit_owner_kind != "organization"
            or row.credit_account_kind != AccountKind.CASH_DEPOSIT
        ):
            continue
        if row.debit_owner_kind == "treasury":
            if row.debit_account_kind != AccountKind.CASH_DEPOSIT:
                continue
            payer_kind = "treasury"
        elif row.debit_owner_kind.startswith("plot_clearing"):
            if row.debit_account_kind != AccountKind.PLOT_CLEARING:
                continue
            payer_kind = "plot_clearing"
        else:
            continue
        payer_id = int(row.debit_owner_id) if payer_kind == "plot_clearing" else 0
        key = (payer_kind, payer_id, int(row.credit_owner_id))
        actual_pairs[key] = actual_pairs.get(key, 0.0) + row.amount
    missing = sorted(set(expected_pairs) - set(actual_pairs))
    extra = sorted(set(actual_pairs) - set(expected_pairs))
    if missing:
        _reject(f"non-organization payment journal is missing counterparties {missing}")
    if extra:
        _reject(f"non-organization payment journal has unexpected counterparties {extra}")
    for key in sorted(expected_pairs):
        residual = max(
            residual,
            _close(
                f"non_org_payment_pair[{key[0]}->{key[1]}]",
                np.asarray([actual_pairs[key]]),
                np.asarray([expected_pairs[key]]),
            ),
        )
    import_seller = (
        np.asarray(network.cell_owner_kind, dtype=np.int64)[
            np.asarray(network.edge_source_cell, dtype=np.int64)
        ]
        == 3
    )
    expected_import = float(np.sum(goods[import_seller]))
    actual_import = float(
        sum(
            row.amount
            for row in journal
            if row.kind == "goods_payment"
            and row.currency == DOMESTIC_CURRENCY
            and row.credit_owner_kind == "treasury"
            and row.credit_account_kind == AccountKind.CASH_DEPOSIT
        )
    )
    residual = max(
        residual,
        _close(
            "import_seller_receipts",
            np.asarray([actual_import]),
            np.asarray([expected_import]),
        ),
    )
    return residual


def _check_stock_cells_compatible(
    opening: MaterialStockSnapshot,
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: Any,
    network: MaterialNetwork,
) -> float:
    """Check the same stock ledgers as ``check_material_invariants``.

    The H3B per-cell helper treats a service-cell closing balance as a
    continuity residual, while the material gate reconciles service leftovers
    through ``expired_services``.  F2 has same-quarter service leftovers, so a
    direct ``_check_stock_cells`` call is not the gate's own model.  This
    helper mirrors the gate: non-retail stockable cells, retail groups and the
    expiry sink.
    """
    from hsm_lab.engine.state import build_material_prices

    prices = build_material_prices(parameters)
    continuity = accounting._reconstruct(opening, state, flows, network, prices, parameters)
    stockable = ~continuity.services_cells & ~continuity.retail_org_cells
    residual = 0.0
    if bool(np.any(stockable)):
        lhs = np.asarray(continuity.expected_close[stockable], dtype=np.float64)
        rhs = np.asarray(state.stock_value[stockable], dtype=np.float64)
        tol = np.asarray(tolerance_for(lhs, rhs), dtype=np.float64)
        residual = max(residual, float(np.max(np.abs(lhs - rhs) - tol, initial=0.0)))
    retail = continuity.retail_org_cells & ~continuity.services_cells
    if bool(np.any(retail)):
        lhs = np.asarray(continuity.retail_expected[retail], dtype=np.float64)
        rhs = np.asarray(continuity.retail_close[retail], dtype=np.float64)
        tol = np.asarray(tolerance_for(lhs, rhs), dtype=np.float64)
        residual = max(residual, float(np.max(np.abs(lhs - rhs) - tol, initial=0.0)))
    expiry = float(np.sum(np.asarray(continuity.services_leftover, dtype=np.float64)))
    expiry_residual = abs(expiry - float(flows.expired_services))
    expiry_tol = float(tolerance_for(expiry, float(flows.expired_services)))
    residual = max(residual, expiry_residual - expiry_tol)
    if residual > 0.0:
        _reject(f"stock continuity exceeds the gate tolerance by {residual!r}")
    return float(max(residual, 0.0))


def _purpose_code(name: str) -> int:
    from hsm_lab.contract.material import PURPOSE_CODES, RoutePurpose

    return int(PURPOSE_CODES[RoutePurpose(name)])


def measure_routing_execution(
    opening: MaterialStockSnapshot,
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: Any,
    network: MaterialNetwork,
    *,
    problem: feasibility.RoutingProblem,
    certificate: feasibility.RoutingCertificate,
    planned_x: np.ndarray,
    submitted_x: np.ndarray,
    execution_status: str,
    lost_free_delivery: float,
    projected: bool,
    project_note: str,
    invariants: InvariantSummary,
) -> RoutingExecutionMeasurement:
    """Read-only gap and counterparty reconciliation for one executed arm."""
    if int(flows.tick) != int(state.completed_ticks):
        _reject(
            f"flows.tick {int(flows.tick)} does not match state.completed_ticks "
            f"{int(state.completed_ticks)}"
        )
    if certificate.problem_hash != problem.problem_hash:
        _reject("certificate problem hash does not match the measured boundary")
    if certificate.status != "FEASIBLE":
        _reject(f"certificate status {certificate.status!r} is not executable")
    edge_count = int(problem.edge_id.shape[0])
    planned = np.asarray(planned_x, dtype=np.float64)
    submitted = np.asarray(submitted_x, dtype=np.float64)
    if planned.shape != (edge_count,) or submitted.shape != (edge_count,):
        _reject("planned/submitted edge vectors do not match the canonical edge axis")
    for name, array in (("planned", planned), ("submitted", submitted)):
        if not bool(np.all(np.isfinite(array))) or bool(np.any(array < -ATOL)):
            _reject(f"{name} edge vector is non-finite or negative")
    allocated = np.asarray(flows.edge_allocated, dtype=np.float64)
    delivered = np.asarray(flows.edge_delivered, dtype=np.float64)
    service_used = np.asarray(flows.edge_service_used, dtype=np.float64)
    service_fee = np.asarray(flows.edge_service_fee, dtype=np.float64)
    goods = delivered * problem.edge_unit_price
    actual_delivered_by_demand = np.asarray(flows.delivered, dtype=np.float64)
    planned_by_demand = np.bincount(
        problem.edge_demand, weights=planned, minlength=problem.variable_axis[2]
    )
    submitted_by_demand = np.bincount(
        problem.edge_demand, weights=submitted, minlength=problem.variable_axis[2]
    )

    household_purpose = _purpose_code("household")
    edge_rows: list[RoutingEdgeRow] = []
    max_edge_gap = 0.0
    max_delivery_gap = 0.0
    for edge in range(edge_count):
        if int(problem.edge_purpose[edge]) == household_purpose:
            continue
        if (
            abs(planned[edge]) <= ATOL
            and abs(submitted[edge]) <= ATOL
            and abs(allocated[edge]) <= ATOL
            and abs(delivered[edge]) <= ATOL
        ):
            continue
        demand_index = int(problem.edge_demand[edge])
        seller = (
            int(problem.cell_owner_id[problem.edge_source[edge]])
            if bool(problem.cell_owner_kind[problem.edge_source[edge]] == 0)
            else -1
        )
        row = RoutingEdgeRow(
            edge_index=edge,
            edge_id=int(problem.edge_id[edge]),
            demand_index=demand_index,
            source_cell=int(problem.edge_source[edge]),
            destination_cell=int(problem.edge_destination[edge]),
            buyer_organization=int(problem.edge_buyer_id[edge]),
            seller_organization=seller,
            carrier_organization=int(problem.edge_carrier_id[edge]),
            planned_x=float(planned[edge]),
            submitted_x=float(submitted[edge]),
            allocated=float(allocated[edge]),
            delivered=float(delivered[edge]),
            service_used=float(service_used[edge]),
            service_fee=float(service_fee[edge]),
            goods_payment=float(goods[edge]),
            freight_payment=float(service_fee[edge]),
            planned_gap=float(planned[edge] - delivered[edge]),
            submitted_gap=float(submitted[edge] - allocated[edge]),
            delivery_gap=float(planned[edge] - delivered[edge]),
        )
        edge_rows.append(row)
        max_edge_gap = max(max_edge_gap, abs(row.planned_gap), abs(row.submitted_gap))
        max_delivery_gap = max(max_delivery_gap, abs(row.delivery_gap))

    shortfall = np.asarray(certificate.shortfall, dtype=np.float64)
    if shortfall.shape != (problem.variable_axis[2],):
        _reject("certificate shortfall axis does not match the demand axis")
    demand_rows: list[RoutingDemandRow] = []
    max_shortfall_residual = 0.0
    for demand_index in range(problem.variable_axis[2]):
        if int(problem.demand_purpose[demand_index]) == household_purpose:
            continue
        if (
            problem.demand_gross[demand_index] <= ATOL
            and problem.demand_ordered[demand_index] <= ATOL
        ):
            continue
        row = RoutingDemandRow(
            demand_index=demand_index,
            desired=float(problem.demand_desired[demand_index]),
            gross=float(problem.demand_gross[demand_index]),
            ordered=float(problem.demand_ordered[demand_index]),
            planned=float(planned_by_demand[demand_index]),
            submitted=float(submitted_by_demand[demand_index]),
            delivered=float(actual_delivered_by_demand[demand_index]),
            used=float(flows.used[demand_index]),
            shortfall=float(shortfall[demand_index]),
            shortfall_residual=float(
                shortfall[demand_index]
                - (problem.demand[demand_index] - actual_delivered_by_demand[demand_index])
            ),
            delivery_gap=float(
                problem.demand[demand_index] - actual_delivered_by_demand[demand_index]
            ),
            financial_blocked=float(flows.financial_delivery_blocked[demand_index]),
            physical_blocked=float(flows.physical_delivery_blocked[demand_index]),
        )
        demand_rows.append(row)
        max_delivery_gap = max(max_delivery_gap, abs(row.delivery_gap))
        max_shortfall_residual = max(max_shortfall_residual, abs(row.shortfall_residual))

    journal = _decode_journal(state, flows)
    org_rows, payment_residual = _organization_payment_rows(
        state, flows, network, dict(problem.__dict__), journal
    )
    payment_residual = max(
        payment_residual,
        _non_org_payment_residual(state, flows, network, dict(problem.__dict__), journal),
    )
    stock_residual = _check_stock_cells_compatible(opening, state, flows, parameters, network)
    bank_residual = flow_funnel._check_bank_books(opening, state, flows, parameters)
    if float(invariants.max_material_tolerance_ratio) > 1.0:
        _reject("material invariant gate did not pass")
    if float(invariants.max_finance_tolerance_ratio) > 1.0:
        _reject("finance invariant gate did not pass")
    free_source = float(np.sum(certificate.u)) if certificate.u.size else 0.0
    free_demand = float(np.sum(certificate.v)) if certificate.v.size else 0.0
    if execution_status in ("EXECUTED", "PARTIAL"):
        if free_source > ATOL or free_demand > ATOL:
            _reject("LP-2 witness carries a non-zero free flow")
        if projected:
            _reject("LP-2 witness was projected rather than executed directly")
        if max_edge_gap > ATOL or max_shortfall_residual > ATOL:
            _reject("LP-2 execution does not match the planned edges/shortfall")
        if execution_status == "EXECUTED":
            if float(certificate.shortfall_total) > ATOL:
                _reject("an EXECUTED certificate carries a non-zero shortfall")
            if max_delivery_gap > ATOL:
                _reject("EXECUTED certificate leaves a non-zero delivery gap")
        elif float(certificate.shortfall_total) <= ATOL:
            _reject("a PARTIAL certificate has no shortfall")
        if payment_residual > ATOL or stock_residual > ATOL or bank_residual > ATOL:
            _reject("LP-2 execution fails payment/stock/bank reconciliation")
    return RoutingExecutionMeasurement(
        schema_version=SCHEMA_VERSION,
        tick=int(flows.tick),
        quarter=str(flows.quarter),
        level=certificate.level,
        execution_status=execution_status,
        edge_rows=tuple(edge_rows),
        demand_rows=tuple(demand_rows),
        organization_rows=org_rows,
        journal=journal,
        max_edge_gap=float(max_edge_gap),
        max_delivery_gap=float(max_delivery_gap),
        max_shortfall_residual=float(max_shortfall_residual),
        max_payment_residual=float(payment_residual),
        max_stock_residual=float(stock_residual),
        max_bank_residual=float(bank_residual),
        free_source_flow=free_source,
        free_demand_flow=free_demand,
        lost_free_delivery=float(lost_free_delivery),
        projected=bool(projected),
        project_note=project_note,
    )


def _project_to_executable(
    problem: feasibility.RoutingProblem,
    certificate: feasibility.RoutingCertificate,
) -> tuple[np.ndarray, bool, float, str]:
    """Only decrease a relaxation witness to the real ordered/source bounds."""
    x = np.array(certificate.x, dtype=np.float64, copy=True)
    original = float(np.sum(x))
    ordered = problem.demand_ordered
    edge_demand = problem.edge_demand
    for demand_index in range(problem.variable_axis[2]):
        edges = np.flatnonzero(edge_demand == demand_index)
        if not edges.size:
            continue
        total = float(x[edges].sum())
        if total > ordered[demand_index] + ATOL:
            factor = max(0.0, float(ordered[demand_index])) / total
            x[edges] *= factor
    edge_source = problem.edge_source
    edge_tier = problem.edge_tier
    for source in range(problem.variable_axis[1]):
        edges = np.flatnonzero(edge_source == source)
        if not edges.size:
            continue
        for tier in (0, 1, 2):
            selected = edges[edge_tier[edges] <= tier]
            if not selected.size:
                continue
            split = float(problem.service_split[2 if tier == 2 else 1])
            cap = (
                float(problem.stock_open[source])
                + float(problem.import_into[source])
                + float(problem.produced_into[source]) * split
            )
            moved = float(x[selected].sum())
            if moved > cap + ATOL:
                x[selected] *= max(0.0, cap) / moved
        fallback = edges[edge_tier[edges] == 3]
        if fallback.size:
            prior = edges[edge_tier[edges] <= 2]
            cap = float(problem.stock_open[source]) + float(problem.import_into[source])
            prior_moved = float(x[prior].sum())
            if prior_moved > cap + ATOL:
                x[prior] *= max(0.0, cap) / prior_moved
                prior_moved = cap
            remaining = max(0.0, cap - prior_moved)
            fallback_moved = float(x[fallback].sum())
            if fallback_moved > remaining + ATOL:
                x[fallback] *= remaining / fallback_moved
        moved = float(x[edges].sum())
        cap = float(problem.source_available[source])
        if moved > cap + ATOL:
            x[edges] *= max(0.0, cap) / moved
    lost = max(0.0, original - float(np.sum(x)))
    projected = lost > ATOL
    note = (
        f"projected real-edge flow from {original!r} to {float(np.sum(x))!r}; "
        f"lost {lost!r} (free receipt is reported separately)"
    )
    return x, projected, lost, note


def _validate_existing_certificate(
    problem: feasibility.RoutingProblem, certificate: feasibility.RoutingCertificate
) -> None:
    ok, reason = feasibility.verify_certificate(problem, certificate)
    if not ok:
        _reject(f"supplied certificate is not reusable: {reason}")


def execute_routing_certificate(
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: Any,
    network: MaterialNetwork,
    *,
    level: Literal["LP-0", "LP-1", "LP-2"] = "LP-2",
    demand: np.ndarray | None = None,
    credit_policy: Any | None = None,
    certificate: feasibility.RoutingCertificate | None = None,
    controls: Any = None,
    time_limit_s: float,
) -> RoutingExecutionResult:
    """Run exactly one real tick through a selected routing witness.

    ``LP-2`` commits only after the gate and measurement pass and advances the
    clock once.  ``LP-0``/``LP-1`` measure their projected executable flow and
    restore the pre-tick state, so comparison arms never touch the main path.
    """
    if level not in LEVELS:
        _reject(f"unknown level {level!r}")
    if not np.isfinite(time_limit_s) or time_limit_s <= 0.0:
        _reject("time_limit_s must be finite and positive")
    caps: np.ndarray | None = None
    procurement_trace: dict[str, np.ndarray] | None = None
    if credit_policy is not None:
        caps = procurement_credit_adapter._validate_policy(
            state, forcing, parameters, credit_policy
        )
        procurement_trace = {}
    before = copy.deepcopy(state)
    opening = capture_material_stocks(state)
    trace: dict[str, Any] = {}
    certificates: tuple[feasibility.RoutingCertificate, ...] = ()
    problems: tuple[feasibility.RoutingProblem, ...] = ()
    selected: feasibility.RoutingCertificate | None = None
    planned = np.zeros(int(np.asarray(network.edge_id).shape[0]), dtype=np.float64)
    submitted = np.zeros_like(planned)
    lost_free = 0.0
    projected = False
    project_note = ""
    nested = feasibility.NestedCheck(False, "not compared")
    flows: MaterialTickFlows | None = None
    phase = "allocation"

    def allocator(boundary: dict[str, Any]) -> np.ndarray:
        nonlocal certificates, problems, selected, planned, submitted
        nonlocal lost_free, projected, project_note, nested
        problem = feasibility.build_routing_problem(boundary, demand=demand)
        trace["boundary"] = boundary
        trace["problem"] = problem
        if certificate is not None:
            if certificate.level != level:
                _reject(
                    f"supplied certificate level {certificate.level!r} does not match "
                    f"requested level {level!r}"
                )
            _validate_existing_certificate(problem, certificate)
            chosen = certificate
            solved: tuple[feasibility.RoutingCertificate, ...] = (certificate,)
            nested = feasibility.NestedCheck(
                False, "single supplied certificate cannot prove three-level nesting"
            )
        else:
            levels = tuple(solved_level for solved_level in LEVELS)
            solved = tuple(
                feasibility.solve_routing_feasibility(
                    problem, level=solved_level, time_limit_s=time_limit_s
                )
                for solved_level in levels
            )
            certificates = solved
            problems = tuple(problem for _ in solved)
            trace["certificates"] = solved
            for item in solved:
                if item.status in ("TIMEOUT", "ERROR"):
                    _reject(f"{item.level} solver ended with {item.status}: {item.solver_message}")
            nested = feasibility.compare_routing_certificates(problem, solved)
            chosen = next(item for item in solved if item.level == level)
        selected = chosen
        certificates = solved
        problems = tuple(problem for _ in solved)
        trace["certificates"] = solved
        if chosen.status == "INFEASIBLE":
            _reject(f"selected {level} is infeasible")
        if chosen.status != "FEASIBLE":
            _reject(f"selected {level} is not feasible: {chosen.status}")
        planned = np.array(chosen.x, dtype=np.float64, copy=True)
        if level == "LP-2":
            submitted = planned.copy()
            lost_free = 0.0
            projected = False
            project_note = "LP-2 witness sent directly to the real kernel"
        else:
            submitted, projected, lost_free, project_note = _project_to_executable(problem, chosen)
        trace["planned_x"] = planned.copy()
        trace["submitted_x"] = submitted.copy()
        return submitted

    execution_status = "EXECUTING"
    procurement_funnel: Any | None = None
    try:
        flows = tick_material(
            state,
            forcing,
            parameters,
            network,
            controls=controls,
            credit_approval_caps=caps,
            procurement_trace=procurement_trace,
            routing_allocator=allocator,
            routing_trace=trace,
        )
        phase = "invariants"
        gate = accounting.check_material_invariants(
            opening, state, flows, parameters, network, controls=controls
        )
        phase = "measurement"
        if credit_policy is not None:
            procurement_funnel = flow_funnel.measure_procurement_credit_tick(
                opening,
                state,
                flows,
                parameters,
                network,
                trace=procurement_trace,
                invariants=gate,
            )
        if selected is None:  # pragma: no cover - defensive
            _reject("the allocator did not select a certificate")
        computed_no_demand = bool(float(np.sum(problems[0].demand)) <= ATOL)
        if bool(selected.no_demand) != computed_no_demand:
            _reject("selected certificate no_demand flag does not match the problem")
        if computed_no_demand:
            execution_status = "NO_DEMAND"
        elif level == "LP-2":
            execution_status = "PARTIAL" if float(selected.shortfall_total) > ATOL else "EXECUTED"
        elif level == "LP-0":
            execution_status = "RELAXATION_ONLY"
        else:
            execution_status = "EXECUTION_GAP"
        measurement = measure_routing_execution(
            opening,
            state,
            flows,
            parameters,
            network,
            problem=problems[0],
            certificate=selected,
            planned_x=planned,
            submitted_x=submitted,
            execution_status=execution_status,
            lost_free_delivery=lost_free,
            projected=projected,
            project_note=project_note,
            invariants=gate,
        )
        if level == "LP-2" and measurement.execution_status in ("EXECUTED", "PARTIAL"):
            state.completed_ticks = int(before.completed_ticks) + 1
        elif level == "LP-2" and measurement.execution_status == "NO_DEMAND":
            # A mathematical zero solution is reported explicitly and never
            # promoted to a non-zero execution positive.
            _restore_state(state, before)
        elif level == "LP-2":
            _reject("LP-2 measurement did not reach EXECUTED")
        else:
            _restore_state(state, before)
        return RoutingExecutionResult(
            schema_version=SCHEMA_VERSION,
            level=level,
            certificates=certificates,
            selected_certificate=selected,
            nested=nested,
            boundary=dict(trace.get("boundary", {})),
            problems=problems,
            flows=flows,
            gate=gate,
            measurement=measurement,
            procurement_funnel=procurement_funnel,
            planned_x=planned,
            submitted_x=submitted,
            actual_allocated=np.asarray(flows.edge_allocated, dtype=np.float64).copy(),
            actual_delivered=np.asarray(flows.edge_delivered, dtype=np.float64).copy(),
            execution_status=measurement.execution_status,
        )
    except Exception as exc:  # noqa: BLE001 - every failure must roll back
        candidate_flows = flows if flows is not None else trace.get("flows")
        failed_flows = copy.deepcopy(candidate_flows) if candidate_flows is not None else None
        failed_trace = _copy_trace(trace)
        _restore_state(state, before)
        if isinstance(exc, RoutingExecutionFailure):
            raise
        raise RoutingExecutionFailure(
            phase=phase,
            cause=exc,
            failed_flows=failed_flows,
            failed_trace=failed_trace,
            certificates=certificates,
        ) from exc


# ---------------------------------------------------------------------------
# H3E: first-quarter rolling proposal execution
# ---------------------------------------------------------------------------

H3E_SCHEMA_VERSION = "hist-bounded-execution-v1"
H3E_GATE_PREFIX = "HIST_H3E_EXECUTION"


def _rolling_reject(message: str) -> None:
    raise ResearchGateError(f"{H3E_GATE_PREFIX}: {message}")


@dataclass(frozen=True)
class RollingSubmissionRow:
    """One first-quarter procurement decision and its real kernel channel."""

    organization_id: str
    commodity_id: str
    organization_index: int
    commodity_index: int
    planned_quantity: float
    requested_quantity: float
    total_planned_quantity: float
    baseline_quantity: float
    incremental_quantity: float
    allocated_quantity: float
    delivered_quantity: float
    goods_payment: float
    freight_payment: float
    plan_actual_gap: float
    incremental_plan_actual_gap: float
    binding_status: str
    decision_digest: str


@dataclass(frozen=True)
class RollingExecutionMeasurement:
    """Read-only measurement of one executed rolling plan quarter."""

    schema_version: str
    tick: int
    quarter: str
    mode: str
    execution_status: str
    submissions: tuple[RollingSubmissionRow, ...]
    journal: tuple[RoutingJournalRow, ...]
    household_delivered: float
    household_used: float
    household_unmet: float
    household_realized_by_good: np.ndarray
    household_unmet_by_good: np.ndarray
    procurement_requested_by_commodity: np.ndarray
    procurement_total_planned_by_commodity: np.ndarray
    procurement_baseline_by_commodity: np.ndarray
    procurement_delivered_by_commodity: np.ndarray
    procurement_allocated_by_commodity: np.ndarray
    service_produced: float
    service_used: float
    service_lost: float
    service_produced_by_commodity: np.ndarray
    service_used_by_commodity: np.ndarray
    service_lost_by_commodity: np.ndarray
    expired_services: float
    goods_payment: float
    freight_payment: float
    sales_receipts: float
    closing_cash: np.ndarray
    closing_stock: np.ndarray
    max_material_ratio: float
    max_finance_ratio: float
    max_payment_residual: float
    max_stock_residual: float
    max_bank_residual: float
    plan_actual_gap: float
    total_plan_gap: float
    incremental_plan_gap: float
    plan_actual_gap_note: str


@dataclass(frozen=True)
class RollingExecutionResult:
    """Successful H3E execution: one tick, one clock advance, no fork."""

    schema_version: str
    mode: str
    plan: Any
    submitted: tuple[RollingSubmissionRow, ...]
    validations: tuple[Any, ...]
    flows: MaterialTickFlows
    gate: InvariantSummary
    measurement: RollingExecutionMeasurement
    completed_ticks_before: int
    completed_ticks_after: int
    execution_status: str


class RollingExecutionFailure(ResearchGateError):
    """A failed H3E execution after the rollback snapshot was captured."""

    def __init__(
        self,
        *,
        phase: str,
        cause: BaseException,
        failed_flows: MaterialTickFlows | None,
        failed_trace: dict[str, Any],
        submitted: tuple[RollingSubmissionRow, ...],
    ) -> None:
        super().__init__(f"{H3E_GATE_PREFIX}: {phase} failed: {cause}")
        self.phase = phase
        self.cause = cause
        self.failed_flows = failed_flows
        self.failed_trace = failed_trace
        self.submitted = submitted

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "cause": f"{type(self.cause).__name__}: {self.cause}",
            "failed_flows": _jsonable(self.failed_flows),
            "failed_trace": _jsonable(self.failed_trace),
            "submitted": _jsonable(self.submitted),
        }


def _decision_hash(decision: Any) -> str:
    import hashlib

    return hashlib.sha256(decision.model_dump_json().encode("utf-8")).hexdigest()


def _payload_hash(decisions: tuple[Any, ...]) -> str:
    import hashlib

    digest = hashlib.sha256()
    for decision in sorted(decisions, key=lambda item: item.decision_id):
        digest.update(decision.model_dump_json().encode("utf-8"))
    return digest.hexdigest()


def _procurement_demand_mask(
    network: MaterialNetwork, organization_index: int, commodity_index: int
) -> np.ndarray:
    from hsm_lab.contract.material import STAGE_CODES, commodity_spec

    consumable_stage = STAGE_CODES[
        commodity_spec(network.commodity_ids[int(commodity_index)]).consumable_stage()
    ]
    destination = np.asarray(network.demand_cell, dtype=np.int64)
    return (
        (np.asarray(network.demand_purpose, dtype=np.int64) == _purpose_code("procurement"))
        & (np.asarray(network.cell_commodity, dtype=np.int64)[destination] == commodity_index)
        & (np.asarray(network.cell_stage, dtype=np.int64)[destination] == consumable_stage)
        & (np.asarray(network.cell_owner_kind, dtype=np.int64)[destination] == 0)
        & (np.asarray(network.cell_owner_id, dtype=np.int64)[destination] == organization_index)
    )


def measure_rolling_execution(
    opening: MaterialStockSnapshot,
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: Any,
    network: MaterialNetwork,
    *,
    plan: Any,
    submissions: tuple[RollingSubmissionRow, ...],
    invariants: InvariantSummary,
    boundary: dict[str, Any] | None = None,
) -> RollingExecutionMeasurement:
    """Measure one real tick against the first-quarter submitted plan."""
    if int(flows.tick) != int(state.completed_ticks):
        _rolling_reject("measured flows do not match the engine clock")
    journal = _decode_journal(state, flows)
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    household_mask = demand_purpose == _purpose_code("household")
    delivered = np.asarray(flows.delivered, dtype=np.float64)
    used = np.asarray(flows.used, dtype=np.float64)
    desired = np.asarray(flows.desired, dtype=np.float64)
    household_delivered = float(np.sum(delivered[household_mask]))
    household_used = float(np.sum(used[household_mask]))
    household_unmet = float(
        np.maximum(desired[household_mask] - delivered[household_mask], 0.0).sum()
    )
    household_realized = np.asarray(flows.household_realized, dtype=np.float64)
    household_desired = np.asarray(flows.household_desired, dtype=np.float64)
    household_unmet = max(
        household_unmet,
        float(np.maximum(household_desired - household_realized, 0.0).sum()),
    )
    service_used = float(np.sum(flows.edge_service_used))
    expired = float(flows.expired_services)
    activity_realized = np.asarray(flows.activity_realized, dtype=np.float64)
    household_realized_by_good = np.asarray(flows.household_realized, dtype=np.float64).sum(axis=0)
    household_unmet_by_good = np.maximum(
        np.asarray(flows.household_desired, dtype=np.float64)
        - np.asarray(flows.household_realized, dtype=np.float64),
        0.0,
    ).sum(axis=0)
    commodity_count = len(network.commodity_ids)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    procurement_mask = demand_purpose == _purpose_code("procurement")
    procurement_delivered = np.zeros(commodity_count, dtype=np.float64)
    procurement_allocated = np.zeros(commodity_count, dtype=np.float64)
    for demand_index in np.flatnonzero(procurement_mask):
        commodity = int(cell_commodity[int(demand_cell[demand_index])])
        procurement_delivered[commodity] += float(flows.delivered[demand_index])
        procurement_allocated[commodity] += float(flows.allocated[demand_index])
    procurement_requested = np.zeros(commodity_count, dtype=np.float64)
    for row in submissions:
        procurement_requested[row.commodity_index] += row.requested_quantity
    procurement_total_planned = np.zeros(commodity_count, dtype=np.float64)
    procurement_baseline = np.zeros(commodity_count, dtype=np.float64)
    commodity_ids = tuple(str(value) for value in network.commodity_ids)
    for good_index, goods_id in enumerate(plan.inputs.goods_id):
        commodity_id = goods_id.split("|", 1)[0]
        if commodity_id not in commodity_ids:
            continue
        commodity_index = commodity_ids.index(commodity_id)
        procurement_total_planned[commodity_index] += float(
            np.sum(plan.quarterly[0].purchases[:, good_index])
        )
        procurement_baseline[commodity_index] += float(
            np.sum(plan.inputs.baseline_procurement[0, :, good_index])
        )
    b_matrix = network.B.tocsr()
    early_service = np.asarray(network.activity_early_service, dtype=bool)
    cell_count = int(cell_commodity.shape[0])
    production_cells = np.zeros(cell_count, dtype=np.float64)
    if (
        early_service.size
        and activity_realized.size == b_matrix.shape[0]
        and bool(np.any(early_service))
    ):
        production_cells = np.asarray(
            b_matrix[early_service].T @ activity_realized[early_service]
        ).ravel()
    service_produced_by_commodity = np.bincount(
        cell_commodity,
        weights=production_cells,
        minlength=commodity_count,
    )
    transport_service_cell = np.asarray(network.edge_transport_service_cell, dtype=np.int64)
    b_service_cells = set(
        int(cell)
        for cell in np.flatnonzero(np.asarray(b_matrix[early_service].sum(axis=0)).ravel() > ATOL)
    )
    transport_cells = set(int(cell) for cell in transport_service_cell if cell >= 0)
    service_commodities = {
        int(cell_commodity[cell]) for cell in (b_service_cells | transport_cells)
    }
    service_cells = np.asarray(
        [cell for cell in range(cell_count) if int(cell_commodity[cell]) in service_commodities],
        dtype=np.int64,
    )
    opening_stock = np.asarray(opening.stock_value, dtype=np.float64)
    service_opening = np.zeros(commodity_count, dtype=np.float64)
    for cell in service_cells:
        service_opening[int(cell_commodity[cell])] += float(opening_stock[cell])
    service_used_by_commodity = np.zeros(commodity_count, dtype=np.float64)
    for edge in np.flatnonzero(np.asarray(flows.edge_service_used) > ATOL):
        cell = int(transport_service_cell[edge])
        if cell >= 0:
            service_used_by_commodity[int(cell_commodity[cell])] += float(
                flows.edge_service_used[edge]
            )
    for demand_index in range(int(demand_cell.shape[0])):
        commodity = int(cell_commodity[int(demand_cell[demand_index])])
        if commodity in service_commodities:
            service_used_by_commodity[commodity] += float(flows.used[demand_index])
    service_lost_by_commodity = (
        service_opening + service_produced_by_commodity - service_used_by_commodity
    )
    service_produced = float(np.sum(service_produced_by_commodity))
    service_used = float(np.sum(service_used_by_commodity))
    service_lost = float(np.sum(np.maximum(service_lost_by_commodity, 0.0)))
    goods_debit = 0.0
    goods_credit = 0.0
    for row in journal:
        if row.kind != "goods_payment" or row.currency != DOMESTIC_CURRENCY:
            continue
        if (
            row.debit_owner_kind == "organization"
            and row.debit_account_kind == AccountKind.CASH_DEPOSIT
        ):
            goods_debit += row.amount
        if (
            row.credit_owner_kind == "organization"
            and row.credit_account_kind == AccountKind.CASH_DEPOSIT
        ):
            goods_credit += row.amount
    payment_residual = 0.0
    from hsm_lab.engine.state import build_material_prices

    prices = build_material_prices(parameters)
    edge_commodity = np.asarray(network.edge_commodity, dtype=np.int64)
    edge_stage = np.asarray(network.edge_stage, dtype=np.int64)
    if boundary is None:
        boundary = {
            "edge_unit_price": np.asarray(
                [
                    float(prices.price_for(int(edge_commodity[edge]), int(edge_stage[edge])))
                    for edge in range(edge_commodity.size)
                ],
                dtype=np.float64,
            ),
            "plot_pool": np.zeros(len(network.region_ids), dtype=np.float64),
        }
    _org_rows, counterparty_residual = _organization_payment_rows(
        state, flows, network, boundary, journal
    )
    counterparty_residual = max(
        counterparty_residual,
        _non_org_payment_residual(state, flows, network, boundary, journal),
    )
    payment_residual = max(payment_residual, counterparty_residual)
    stock_residual = _check_stock_cells_compatible(opening, state, flows, parameters, network)
    bank_residual = flow_funnel._check_bank_books(opening, state, flows, parameters)
    total_plan_gap = float(
        np.max(
            np.maximum(
                procurement_total_planned - procurement_delivered,
                0.0,
            ),
            initial=0.0,
        )
    )
    incremental_plan_gap = max(
        (row.incremental_plan_actual_gap for row in submissions), default=0.0
    )
    plan_gap = total_plan_gap
    return RollingExecutionMeasurement(
        schema_version=H3E_SCHEMA_VERSION,
        tick=int(flows.tick),
        quarter=str(flows.quarter),
        mode=str(plan.mode),
        execution_status="MEASURED",
        submissions=submissions,
        journal=journal,
        household_delivered=household_delivered,
        household_used=household_used,
        household_unmet=household_unmet,
        household_realized_by_good=household_realized_by_good,
        household_unmet_by_good=household_unmet_by_good,
        procurement_requested_by_commodity=procurement_requested,
        procurement_total_planned_by_commodity=procurement_total_planned,
        procurement_baseline_by_commodity=procurement_baseline,
        procurement_delivered_by_commodity=procurement_delivered,
        procurement_allocated_by_commodity=procurement_allocated,
        service_produced=service_produced,
        service_used=service_used,
        service_lost=service_lost,
        service_produced_by_commodity=service_produced_by_commodity,
        service_used_by_commodity=service_used_by_commodity,
        service_lost_by_commodity=service_lost_by_commodity,
        expired_services=expired,
        goods_payment=goods_debit,
        freight_payment=float(np.sum(flows.edge_service_fee)),
        sales_receipts=goods_credit,
        closing_cash=np.asarray(state.organization_cash, dtype=np.float64).copy(),
        closing_stock=np.asarray(state.stock_value, dtype=np.float64).copy(),
        max_material_ratio=float(invariants.max_material_tolerance_ratio),
        max_finance_ratio=float(invariants.max_finance_tolerance_ratio),
        max_payment_residual=float(payment_residual),
        max_stock_residual=float(stock_residual),
        max_bank_residual=float(bank_residual),
        plan_actual_gap=float(plan_gap),
        total_plan_gap=float(total_plan_gap),
        incremental_plan_gap=float(incremental_plan_gap),
        plan_actual_gap_note=(
            "plan gap is measured on the total procurement demand channel; "
            "baseline endogenous orders are retained by the kernel and are not "
            "subtracted by a counterfactual fork"
        ),
    )


def execute_rolling_proposal(
    plan: Any,
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: Any,
    network: MaterialNetwork,
    *,
    calendar: Any,
    session: Any,
    observations: tuple[Any, ...],
    organization_index: dict[str, int],
    controls: Any = None,
    budget_observations: tuple[Any, ...] = (),
    inputs: Any = None,
) -> RollingExecutionResult:
    """Execute only the first-quarter decisions, with exactly one real tick.

    The wrapper never calls the per-decision ``commit_proposal`` path (which
    ticks and forks a baseline per decision) and never runs a counterfactual on
    the real state.  All admission checks happen before the tick; any failure
    restores every ``MaterialState`` field and leaves the clock unchanged.
    """
    from hsm_lab.engine.policy import TickControls
    from hsm_lab.engine.political_run import PoliticalSession
    from hsm_lab.institutions.decisions import ProcurementDecision
    from hsm_lab.institutions.proposal_validation import validate_proposal
    from hsm_lab.planning.proposals import PlanningObservation, observation_digest
    from hsm_lab.planning.rolling import RollingPlan

    if type(plan) is not RollingPlan:
        _rolling_reject("plan must be a concrete RollingPlan")
    if plan.status != "FEASIBLE":
        _rolling_reject(f"plan status {plan.status!r} is not executable")
    if plan.horizon_quarters != 4:
        _rolling_reject("plan horizon is not four quarters")
    if plan.decision_quarter != plan.quarters[0]:
        _rolling_reject("plan decision quarter is not the first horizon quarter")
    if not plan.certificates:
        _rolling_reject("plan carries no planning certificate")
    for certificate in plan.certificates:
        if not np.isfinite(float(certificate.layer_objective)) or not np.isfinite(
            float(certificate.wall_s)
        ):
            _rolling_reject("certificate carries a non-finite scalar")
        for array in (
            certificate.row_rhs,
            certificate.row_activity,
            certificate.row_residual,
            certificate.row_slack,
            certificate.primal,
            certificate.dual_eq,
            certificate.dual_ub,
        ):
            if array.size and not bool(np.all(np.isfinite(array))):
                _rolling_reject("certificate contains a non-finite value")
    if plan.mode == "historical_rule_based":
        if len(plan.certificates) != 1 or plan.certificates[0].status != "FEASIBLE":
            _rolling_reject("reference plan certificate is incomplete or not feasible")
    else:
        if len(plan.certificates) != 4:
            _rolling_reject("optimization plan does not carry four lex certificates")
        for index, certificate in enumerate(plan.certificates):
            if certificate.layer_index != index or certificate.status != "FEASIBLE":
                _rolling_reject("optimization plan certificate is out of order or not feasible")
            if certificate.primal.size != certificate.matrix_cols:
                _rolling_reject("certificate primal axis does not match its model")
            for array in (
                certificate.primal,
                certificate.row_rhs,
                certificate.row_activity,
                certificate.row_residual,
                certificate.row_slack,
                certificate.dual_eq,
                certificate.dual_ub,
            ):
                if array.size and not bool(np.all(np.isfinite(array))):
                    _rolling_reject("certificate contains a non-finite value")
    from hsm_lab.planning.rolling import verify_plan_certificates

    verified, reason = verify_plan_certificates(plan)
    if not verified:
        _rolling_reject(f"certificate verification failed: {reason}")
    if type(session) is not PoliticalSession:
        _rolling_reject("session must be an exact PoliticalSession")
    if type(observations) is not tuple or any(
        type(item) is not PlanningObservation for item in observations
    ):
        _rolling_reject("observations must be a tuple of PlanningObservation")
    if type(budget_observations) is not tuple:
        _rolling_reject("budget_observations must be a tuple")
    if object.__getattribute__(session, "state") is not state:
        _rolling_reject("session.state is not the supplied material state")
    if object.__getattribute__(session, "opened") is not True:
        _rolling_reject("session is not open for admission")
    if object.__getattribute__(session, "finished") is not False:
        _rolling_reject("session is finished")
    tick = int(state.completed_ticks)
    if int(session.completed_ticks) != tick:
        _rolling_reject("session and state clocks disagree")
    quarters = list(forcing.quarters)
    if tick < 0 or tick >= len(quarters):
        _rolling_reject("decision tick lies outside the forcing horizon")
    if str(quarters[tick]) != plan.decision_quarter:
        _rolling_reject("plan decision quarter does not match the kernel quarter")
    if str(session.quarter_of(tick)) != plan.decision_quarter:
        _rolling_reject("session quarter does not match the plan decision quarter")
    current_observations = tuple(
        item for item in observations if item.observation.quarter == plan.decision_quarter
    )
    if len(current_observations) != len(observations):
        _rolling_reject("observations contain a report from another quarter")
    observed_hash = observation_digest(
        observations,
        budget_observations,
        quarter=plan.decision_quarter,
    )
    if observed_hash != plan.observation_hash:
        _rolling_reject("observation hash does not match the frozen plan")
    from hsm_lab.planning.proposals import PlanningInputs

    frozen_inputs = plan.inputs
    if type(frozen_inputs) is not PlanningInputs:
        _rolling_reject("plan does not carry concrete frozen inputs")
    if inputs is not None:
        if type(inputs) is not PlanningInputs:
            _rolling_reject("inputs must be a concrete PlanningInputs")
        if inputs.digest() != frozen_inputs.digest():
            _rolling_reject("supplied inputs do not match the plan's frozen inputs")
    if frozen_inputs.digest() != frozen_inputs.input_hash:
        _rolling_reject("frozen input arrays or scalars were modified")
    if plan.plan_hash != plan.digest():
        _rolling_reject("plan payload was modified after sealing")
    if frozen_inputs.input_hash != plan.input_hash:
        _rolling_reject("plan input hash does not match the frozen inputs")
    if frozen_inputs.observation_hash != plan.observation_hash:
        _rolling_reject("plan observation hash does not match the frozen inputs")
    if frozen_inputs.priority_hash != plan.priority_hash:
        _rolling_reject("plan priority hash does not match the frozen inputs")
    if frozen_inputs.forecast_hash != plan.forecast_hash:
        _rolling_reject("plan forecast hash does not match the frozen inputs")
    if (
        observation_digest(
            frozen_inputs.observations,
            frozen_inputs.budget_observations,
            quarter=plan.decision_quarter,
        )
        != plan.observation_hash
    ):
        _rolling_reject("frozen observation payload was modified")
    if not plan.matrix_hash:
        _rolling_reject("plan has no matrix hash")
    for certificate in plan.certificates:
        if certificate.input_hash != plan.input_hash:
            _rolling_reject("certificate is not bound to the plan input hash")
    for name in (
        "organization_bank",
        "inventory_initial",
        "cash_initial",
        "prices",
        "demand_ordered",
        "demand_gross",
        "recipe_capacity",
        "funding_capacity",
        "service_capacity",
        "handling_capacity",
        "edge_capacity",
        "bank_reserves",
        "wage",
        "organization_funding_group",
        "funding_group_capacity",
        "interest",
        "order_financing",
        "edge_service_good",
        "organization_service_good",
        "baseline_procurement",
    ):
        if bool(getattr(frozen_inputs, name).flags.writeable):
            _rolling_reject(f"frozen input array {name} is writable")
    decisions = tuple(plan.first_quarter_decisions)
    if any(type(item) is not ProcurementDecision for item in decisions):
        _rolling_reject("plan contains a non-procurement decision")
    if _payload_hash(decisions) != plan.first_quarter_payload_hash:
        _rolling_reject("first-quarter payload hash does not match the plan")
    from hsm_lab.planning.rolling import derive_first_quarter_decisions

    derived = derive_first_quarter_decisions(plan)
    expected_map = {
        (item.organization_id, item.commodity_id): float(item.requested_quantity)
        for item in decisions
    }
    derived_map = {
        (item.organization_id, item.commodity_id): float(item.requested_quantity)
        for item in derived
    }
    if set(expected_map) != set(derived_map):
        _rolling_reject("submitted payload does not match the plan forecast")
    for key in expected_map:
        if abs(expected_map[key] - derived_map[key]) > 1e-6:
            _rolling_reject("submitted payload quantity does not match the plan forecast")
    seen: set[tuple[str, str]] = set()
    existing = set()
    if controls is not None:
        for org_idx, commodity_idx, _quantity in controls.procurement_requests or ():
            existing.add((int(org_idx), int(commodity_idx)))
    request_rows: list[tuple[int, int, float]] = []
    validations: list[Any] = []
    observation_by_key = {
        (item.organization_id, item.commodity_id): item for item in current_observations
    }
    for decision in decisions:
        if decision.quarter != plan.decision_quarter:
            _rolling_reject("plan contains a decision for a future quarter")
        key = (decision.organization_id, decision.commodity_id)
        if key in seen:
            _rolling_reject(f"duplicate organization/commodity decision {key!r}")
        seen.add(key)
        if decision.organization_id not in organization_index:
            _rolling_reject(
                f"organization {decision.organization_id!r} is outside the scenario crosswalk"
            )
        org_idx = int(organization_index[decision.organization_id])
        commodity_ids = tuple(str(value) for value in network.commodity_ids)
        if decision.commodity_id not in commodity_ids:
            _rolling_reject(f"commodity {decision.commodity_id!r} is not in the network")
        commodity_idx = commodity_ids.index(decision.commodity_id)
        if (org_idx, commodity_idx) in existing:
            _rolling_reject("controls already carry a request for this organization/commodity")
        if not bool(_procurement_demand_mask(network, org_idx, commodity_idx).any()):
            _rolling_reject("organization has no procurement destination for the commodity")
        observation = observation_by_key.get(key)
        if observation is None:
            _rolling_reject("decision has no bound observation")
        validation = validate_proposal(
            decision,
            calendar,
            observation=observation.observation,
            session=session,
        )
        if not validation.admission_eligible or not validation.is_legal:
            _rolling_reject(f"proposal admission rejected: {validation.reason}")
        if validation.decision_digest != _decision_hash(decision):
            _rolling_reject("validated payload digest does not match the decision")
        validations.append(validation)
        request_rows.append((org_idx, commodity_idx, float(decision.requested_quantity)))

    if controls is None:
        base = TickControls(
            material_parameters=parameters,
            household_parameters=network.household_parameters,
            household_catalog=network.household_catalog,
            autonomy=0.0,
            central_target=None,
            policy=None,
            procurement_requests=None,
        )
    else:
        base = controls
    new_controls = TickControls(
        material_parameters=base.material_parameters,
        household_parameters=base.household_parameters,
        household_catalog=base.household_catalog,
        autonomy=base.autonomy,
        central_target=base.central_target,
        policy=base.policy,
        procurement_requests=(
            (*(base.procurement_requests or ()), *request_rows)
            if (base.procurement_requests or request_rows)
            else None
        ),
    )

    before = copy.deepcopy(state)
    opening = capture_material_stocks(state)
    trace: dict[str, Any] = {}
    flows: MaterialTickFlows | None = None
    submissions: tuple[RollingSubmissionRow, ...] = ()
    phase = "tick"
    try:
        flows = tick_material(
            state,
            forcing,
            parameters,
            network,
            controls=new_controls,
            routing_trace=trace,
        )
        phase = "invariants"
        gate = accounting.check_material_invariants(
            opening, state, flows, parameters, network, controls=new_controls
        )
        if float(gate.max_material_tolerance_ratio) > 1.0:
            _rolling_reject("material invariant gate did not pass")
        if float(gate.max_finance_tolerance_ratio) > 1.0:
            _rolling_reject("finance invariant gate did not pass")
        phase = "measurement"
        from hsm_lab.engine.state import build_material_prices

        prices = build_material_prices(parameters)
        rows: list[RollingSubmissionRow] = []
        for decision, request in zip(decisions, request_rows, strict=True):
            org_idx, commodity_idx, quantity = request
            mask = _procurement_demand_mask(network, org_idx, commodity_idx)
            demand_indices = np.flatnonzero(mask)
            delivered_quantity = float(np.sum(np.asarray(flows.delivered, dtype=np.float64)[mask]))
            allocated_quantity = float(np.sum(np.asarray(flows.allocated, dtype=np.float64)[mask]))
            edge_mask = np.isin(np.asarray(network.edge_demand, dtype=np.int64), demand_indices)
            freight = float(np.sum(np.asarray(flows.edge_service_fee, dtype=np.float64)[edge_mask]))
            demand_index = int(np.flatnonzero(mask)[0])
            destination_cell = int(network.demand_cell[demand_index])
            stage = int(np.asarray(network.cell_stage, dtype=np.int64)[destination_cell])
            unit_price = float(prices.price_for(commodity_idx, stage))
            total_planned = 0.0
            baseline = 0.0
            planning_org_index = frozen_inputs.organization_ids.index(decision.organization_id)
            for good_index, goods_id in enumerate(frozen_inputs.goods_id):
                if goods_id.split("|", 1)[0] != decision.commodity_id:
                    continue
                total_planned += float(plan.quarterly[0].purchases[planning_org_index, good_index])
                baseline += float(
                    frozen_inputs.baseline_procurement[0, planning_org_index, good_index]
                )
            incremental = float(quantity)
            gap = max(0.0, total_planned - delivered_quantity)
            incremental_gap = max(0.0, incremental - delivered_quantity)
            rows.append(
                RollingSubmissionRow(
                    organization_id=decision.organization_id,
                    commodity_id=decision.commodity_id,
                    organization_index=org_idx,
                    commodity_index=commodity_idx,
                    planned_quantity=total_planned,
                    requested_quantity=incremental,
                    total_planned_quantity=total_planned,
                    baseline_quantity=baseline,
                    incremental_quantity=incremental,
                    allocated_quantity=allocated_quantity,
                    delivered_quantity=delivered_quantity,
                    goods_payment=delivered_quantity * unit_price,
                    freight_payment=freight,
                    plan_actual_gap=gap,
                    incremental_plan_actual_gap=incremental_gap,
                    binding_status="satisfied" if gap <= ATOL else "binding",
                    decision_digest=_decision_hash(decision),
                )
            )
        submissions = tuple(rows)
        measurement = measure_rolling_execution(
            opening,
            state,
            flows,
            parameters,
            network,
            plan=plan,
            submissions=submissions,
            invariants=gate,
            boundary=trace.get("boundary"),
        )
        if measurement.max_payment_residual > ATOL:
            _rolling_reject("journal does not reconcile to organization payments")
        if measurement.max_stock_residual > ATOL:
            _rolling_reject("stock continuity does not reconcile")
        if measurement.max_bank_residual > ATOL:
            _rolling_reject("bank books do not reconcile")
        before_clock = int(before.completed_ticks)
        state.completed_ticks = before_clock + 1
        if submissions and any(row.plan_actual_gap > ATOL for row in submissions):
            status = "PARTIAL"
        elif submissions:
            status = "EXECUTED"
        else:
            status = "NO_REQUESTS"
        return RollingExecutionResult(
            schema_version=H3E_SCHEMA_VERSION,
            mode=plan.mode,
            plan=plan,
            submitted=submissions,
            validations=tuple(validations),
            flows=flows,
            gate=gate,
            measurement=measurement,
            completed_ticks_before=before_clock,
            completed_ticks_after=int(state.completed_ticks),
            execution_status=status,
        )
    except Exception as exc:  # noqa: BLE001 - every failure must roll back
        failed_flows = copy.deepcopy(flows) if flows is not None else None
        failed_trace = {
            "tick": tick,
            "quarter": plan.decision_quarter,
            "mode": plan.mode,
            "submitted": _jsonable(submissions),
            "requests": _jsonable(request_rows),
        }
        _restore_state(state, before)
        if isinstance(exc, RollingExecutionFailure):
            raise
        raise RollingExecutionFailure(
            phase=phase,
            cause=exc,
            failed_flows=failed_flows,
            failed_trace=failed_trace,
            submitted=submissions,
        ) from exc


__all__ = [
    "H3E_SCHEMA_VERSION",
    "RollingExecutionFailure",
    "RollingExecutionMeasurement",
    "RollingExecutionResult",
    "RollingSubmissionRow",
    "RoutingDemandRow",
    "RoutingEdgeRow",
    "RoutingExecutionFailure",
    "RoutingExecutionMeasurement",
    "RoutingExecutionResult",
    "RoutingJournalRow",
    "RoutingOrganizationPaymentRow",
    "execute_rolling_proposal",
    "execute_routing_certificate",
    "measure_rolling_execution",
    "measure_routing_execution",
]
