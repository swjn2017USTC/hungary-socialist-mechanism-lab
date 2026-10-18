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
        return {
            field: _jsonable(getattr(value, field))
            for field in value.__dataclass_fields__
        }
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
        _reject(
            f"{name}[{bad}] {float(lhs.ravel()[bad])!r} exceeds "
            f"{float(rhs.ravel()[bad])!r}"
        )
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
    import_seller = np.asarray(network.cell_owner_kind, dtype=np.int64)[
        np.asarray(network.edge_source_cell, dtype=np.int64)
    ] == 3
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
    continuity = accounting._reconstruct(
        opening, state, flows, network, prices, parameters
    )
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
        seller = int(problem.cell_owner_id[problem.edge_source[edge]]) if bool(
            problem.cell_owner_kind[problem.edge_source[edge]] == 0
        ) else -1
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
                - (
                    problem.demand[demand_index]
                    - actual_delivered_by_demand[demand_index]
                )
            ),
            delivery_gap=float(
                problem.demand[demand_index] - actual_delivered_by_demand[demand_index]
            ),
            financial_blocked=float(flows.financial_delivery_blocked[demand_index]),
            physical_blocked=float(flows.physical_delivery_blocked[demand_index]),
        )
        demand_rows.append(row)
        max_delivery_gap = max(max_delivery_gap, abs(row.delivery_gap))
        max_shortfall_residual = max(
            max_shortfall_residual, abs(row.shortfall_residual)
        )

    journal = _decode_journal(state, flows)
    org_rows, payment_residual = _organization_payment_rows(
        state, flows, network, dict(problem.__dict__), journal
    )
    payment_residual = max(
        payment_residual,
        _non_org_payment_residual(state, flows, network, dict(problem.__dict__), journal),
    )
    stock_residual = _check_stock_cells_compatible(
        opening, state, flows, parameters, network
    )
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
                    _reject(
                        f"{item.level} solver ended with {item.status}: {item.solver_message}"
                    )
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
            submitted, projected, lost_free, project_note = _project_to_executable(
                problem, chosen
            )
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
            execution_status = (
                "PARTIAL" if float(selected.shortfall_total) > ATOL else "EXECUTED"
            )
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


__all__ = [
    "RoutingDemandRow",
    "RoutingEdgeRow",
    "RoutingExecutionFailure",
    "RoutingExecutionMeasurement",
    "RoutingExecutionResult",
    "RoutingJournalRow",
    "RoutingOrganizationPaymentRow",
    "execute_routing_certificate",
    "measure_routing_execution",
]
