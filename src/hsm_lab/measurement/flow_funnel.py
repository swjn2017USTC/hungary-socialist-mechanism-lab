"""H3B: read-only procurement-credit funnel and journal identity gate.

The measurement separates the financial credit funnel from the physical
procurement funnel and binds both to the real kernel flows and journal:

* one credit-budget row per non-bank organization (request, cap, approval,
  drawdown, wage/interest/principal priority and closing balances);
* one input row per real organization production input (desired/gross/ordered/
  allocated/delivered/used and the two blocked channels);
* one edge row per actual route serving those inputs;
* every raw journal row with its decoded owner/account, so payment evidence is
  auditable rather than inferred from state totals.

It never ticks, writes state/flows/clock or touches disk.  A missing trace key,
a wrong shape, a non-finite value, an unclosed identity or a loan journal that
does not name the actual bank is rejected with ``hist-procurement-credit-v1:``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.contract.material import (
    STAGE_CODES,
    MaterialParameters,
    commodity_spec,
)
from hsm_lab.engine.accounting import (
    ATOL,
    InvariantSummary,
    _reconstruct,
    tolerance_for,
)
from hsm_lab.engine.finance import (
    _BANK_TYPE_CODE,
    DOMESTIC_CURRENCY,
    AccountKind,
    bank_account_ids,
    build_account_directory,
    organization_account_ids,
)
from hsm_lab.engine.network import MaterialNetwork
from hsm_lab.engine.state import (
    MaterialState,
    MaterialStockSnapshot,
    MaterialTickFlows,
    build_material_prices,
)

SCHEMA_VERSION = "hist-procurement-credit-funnel-v1"
ONTOLOGY_ID = "hist-procurement-credit-v1"

_TRACE_KEYS = (
    "credit_approval_caps",
    "demand_unit_cost",
    "input_order_cost",
    "old_project_cost",
    "new_investment_request_cost",
    "cash_available_for_goods",
    "input_credit_earmarked",
    "edge_unit_price",
)

_OWNER_KIND_NAMES = {
    0: "organization",
    1: "plot",
    2: "project",
    3: "treasury_import",
    4: "second_economy",
}

_STAGE_NAMES = {code: name for name, code in STAGE_CODES.items()}


def _reject(message: str) -> None:
    raise ResearchGateError(f"{ONTOLOGY_ID}: {message}")


def _float_array(
    name: str,
    value: object,
    shape: tuple[int, ...],
    *,
    non_negative: bool = False,
) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != shape:
        _reject(f"{name} shape {array.shape} does not match {shape}")
    if not bool(np.all(np.isfinite(array))):
        _reject(f"{name} contains a non-finite value")
    if non_negative and bool(np.any(array < -ATOL)):
        bad = int(np.argmin(array))
        _reject(f"{name}[{bad}]={float(array.ravel()[bad])!r} is negative")
    return array


@dataclass(frozen=True)
class CreditBudgetRow:
    """One non-bank organization's credit budget and debt-service ordering."""

    organization_id: int
    bank_index: int
    requested: float
    approval_cap: float
    approved: float
    drawn: float
    opening_cash: float
    opening_principal: float
    wage_due: float
    wage_paid: float
    interest_due: float
    interest_paid: float
    scheduled_principal: float
    principal_paid: float
    principal_unpaid: float
    input_order_cost: float
    old_project_cost: float
    new_investment_request_cost: float
    cash_available_for_goods: float
    input_credit_earmarked: float
    purchases: float
    closing_cash: float
    closing_principal: float
    drawdown_journal_rows: tuple[int, ...]
    principal_journal_rows: tuple[int, ...]
    cash_account_id: int
    loan_liability_account_id: int
    bank_deposit_liability_account_id: int
    bank_loan_asset_account_id: int
    currency: str = DOMESTIC_CURRENCY


@dataclass(frozen=True)
class ProcurementInputRow:
    """One real organization production input on the demand axis."""

    organization_id: int
    input_index: int
    demand_index: int
    activity_index: int
    cell_index: int
    commodity_id: str
    stage: str
    unit: str
    desired: float
    ordered_gross: float
    ordered: float
    unfunded_order: float
    allocated: float
    delivered: float
    used: float
    inventory_open: float
    inventory_close: float
    goods_payment: float
    freight_payment: float
    upstream_unfunded: float
    allocation_gap: float
    physical_delivery_blocked: float
    financial_delivery_blocked: float


@dataclass(frozen=True)
class ProcurementEdgeRow:
    """One actual route edge serving a real organization input demand."""

    edge_index: int
    demand_index: int
    source_cell: int
    destination_cell: int
    source_owner_kind: str
    source_owner_id: int
    seller_organization_id: int
    buyer_organization_id: int
    transport_organization_id: int
    source_bank_index: int
    destination_bank_index: int
    allocated: float
    delivered: float
    goods_payment: float
    freight_payment: float


@dataclass(frozen=True)
class PaymentJournalRow:
    """One raw journal row with its decoded account owner and leg group."""

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
class ProcurementCreditFunnel:
    """The complete H3B measurement of one admitted tick."""

    tick: int
    quarter: str
    credit_budgets: tuple[CreditBudgetRow, ...]
    inputs: tuple[ProcurementInputRow, ...]
    edges: tuple[ProcurementEdgeRow, ...]
    journal: tuple[PaymentJournalRow, ...]
    max_credit_residual: float
    max_physical_residual: float
    max_bank_residual: float
    unlisted_default_zero: bool = True
    schema_version: str = SCHEMA_VERSION
    ontology_id: str = ONTOLOGY_ID


def _validate_trace(
    trace: Mapping[str, np.ndarray],
    *,
    organization_count: int,
    demand_count: int,
    edge_count: int,
) -> dict[str, np.ndarray]:
    if not isinstance(trace, Mapping):
        _reject("trace must be a mapping")
    missing = [key for key in _TRACE_KEYS if key not in trace]
    if missing:
        _reject(f"trace is missing required key(s): {missing}")
    shapes = {
        "credit_approval_caps": (organization_count,),
        "demand_unit_cost": (demand_count,),
        "input_order_cost": (organization_count,),
        "old_project_cost": (organization_count,),
        "new_investment_request_cost": (organization_count,),
        "cash_available_for_goods": (organization_count,),
        "input_credit_earmarked": (organization_count,),
        "edge_unit_price": (edge_count,),
    }
    arrays: dict[str, np.ndarray] = {}
    for key, shape in shapes.items():
        arrays[key] = _float_array(key, trace[key], shape, non_negative=True)
    return arrays


def _transaction_groups(flows: MaterialTickFlows) -> np.ndarray:
    leg = np.asarray(flows.journal_leg, dtype=np.int64)
    count = int(leg.shape[0])
    if count == 0:
        return np.zeros(0, dtype=np.int64)
    if int(leg[0]) != 0:
        _reject("journal leg index must start at 0")
    if count > 1:
        restart = leg[1:] == 0
        sequential = np.diff(leg) == 1
        if not bool(np.all(restart | sequential)):
            _reject("journal leg indices must restart at 0 and increment by 1 per transaction")
    return np.cumsum(leg == 0) - 1


def _journal_rows(
    flows: MaterialTickFlows,
    run_id: np.ndarray,
    directory: dict[tuple[str, int, str, str], int],
) -> tuple[PaymentJournalRow, ...]:
    reverse = {account: key for key, account in directory.items()}
    kind = np.asarray(flows.journal_kind, dtype=object)
    debit = np.asarray(flows.journal_debit, dtype=np.int64)
    credit = np.asarray(flows.journal_credit, dtype=np.int64)
    currency = np.asarray(flows.journal_currency, dtype=object)
    amount = np.asarray(flows.journal_amount, dtype=np.float64)
    org = np.asarray(flows.journal_org, dtype=object)
    leg = np.asarray(flows.journal_leg, dtype=np.int64)
    if not (kind.shape[0] == debit.shape[0] == credit.shape[0] == currency.shape[0]):
        _reject("journal columns do not align")
    if not (amount.shape[0] == org.shape[0] == leg.shape[0] == kind.shape[0]):
        _reject("journal columns do not align")
    if bool(np.any(currency != DOMESTIC_CURRENCY)):
        _reject("H3B journal must use the domestic currency only")
    if bool(np.any(~np.isfinite(amount))) or bool(np.any(amount <= 0.0)):
        _reject("H3B journal amounts must be finite and strictly positive")
    rows: list[PaymentJournalRow] = []
    for row in range(int(kind.shape[0])):
        debit_key = reverse.get(int(debit[row]))
        credit_key = reverse.get(int(credit[row]))
        if debit_key is None or credit_key is None:
            _reject(f"journal row {row} names an account outside the directory")
        rows.append(
            PaymentJournalRow(
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


def _check_lender_journals(
    *,
    org_id: int,
    org_row: int,
    bank_index: int,
    drawn: float,
    principal_paid: float,
    journal: tuple[PaymentJournalRow, ...],
    state: MaterialState,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    cash_id = int(organization_account_ids(state, AccountKind.CASH_DEPOSIT)[org_row])
    loan_id = int(organization_account_ids(state, AccountKind.LOAN_LIABILITY)[org_row])
    if bank_index < 0:
        deposit_id = -1
        asset_id = -1
    else:
        deposit_id = int(bank_account_ids(state, AccountKind.DEPOSIT_LIABILITY)[bank_index])
        asset_id = int(bank_account_ids(state, AccountKind.LOAN_ASSET)[bank_index])

    by_transaction: dict[int, list[PaymentJournalRow]] = {}
    for row in journal:
        if row.organization_id != org_id:
            continue
        if row.kind not in ("loan_drawdown", "principal_repayment"):
            continue
        by_transaction.setdefault(row.transaction_index, []).append(row)

    draw_rows: tuple[int, ...] = ()
    principal_rows: tuple[int, ...] = ()
    seen_draw = 0
    seen_principal = 0
    for transaction_index, rows in by_transaction.items():
        kinds = {row.kind for row in rows}
        if len(kinds) != 1:
            _reject(f"organization {org_id} transaction {transaction_index} mixes journal kinds")
        kind = next(iter(kinds))
        if len(rows) != 2:
            _reject(
                f"{kind} for organization {org_id} has {len(rows)} legs; expected exactly 2"
            )
        expected_amount = drawn if kind == "loan_drawdown" else principal_paid
        if not bool(np.allclose([row.amount for row in rows], expected_amount, atol=ATOL, rtol=0)):
            _reject(
                f"{kind} for organization {org_id} amount does not match the flow value"
            )
        pairs = {(row.debit_account, row.credit_account) for row in rows}
        if kind == "loan_drawdown":
            expected = {(cash_id, deposit_id), (asset_id, loan_id)}
            row_indexes = tuple(sorted(row.row_index for row in rows))
            if pairs != expected:
                _reject(
                    f"loan_drawdown for organization {org_id} does not debit its cash and "
                    "its bank's loan asset / credit its loan liability and bank deposit"
                )
            draw_rows = row_indexes
            seen_draw += 1
        else:
            expected = {(loan_id, cash_id), (deposit_id, asset_id)}
            row_indexes = tuple(sorted(row.row_index for row in rows))
            if pairs != expected:
                _reject(
                    f"principal_repayment for organization {org_id} does not debit its loan "
                    "liability and its bank's deposit / credit its cash and bank loan asset"
                )
            principal_rows = row_indexes
            seen_principal += 1

    if seen_draw > 1 or seen_principal > 1:
        _reject(f"organization {org_id} has more than one drawdown/repayment transaction")
    if drawn > 0.0 and seen_draw != 1:
        _reject(f"organization {org_id} drew {drawn!r} without a loan_drawdown journal")
    if drawn <= 0.0 and seen_draw:
        _reject(f"organization {org_id} has a zero drawdown but a loan_drawdown journal")
    if principal_paid > 0.0 and seen_principal != 1:
        _reject(
            f"organization {org_id} repaid {principal_paid!r} without a "
            "principal_repayment journal"
        )
    if principal_paid <= 0.0 and seen_principal:
        _reject(
            f"organization {org_id} has a zero principal payment but a "
            "principal_repayment journal"
        )
    return draw_rows, principal_rows


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


def _check_payment_journals(
    state: MaterialState,
    flows: MaterialTickFlows,
    network: MaterialNetwork,
    journal: tuple[PaymentJournalRow, ...],
    unit_price: np.ndarray,
) -> float:
    """Bind per-buyer purchases and per-seller/carrier receipts to journals."""
    org_ids = np.asarray(state.organization_id, dtype=np.int64)
    org_row_by_id = {int(org_id): row for row, org_id in enumerate(org_ids)}
    edge_buyer = np.asarray(network.edge_buyer_org, dtype=np.int64)
    edge_source = np.asarray(network.edge_source_cell, dtype=np.int64)
    edge_transport = np.asarray(network.edge_transport_org, dtype=np.int64)
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    delivered = np.asarray(flows.edge_delivered, dtype=np.float64)
    fee = np.asarray(flows.edge_service_fee, dtype=np.float64)
    goods = delivered * np.asarray(unit_price, dtype=np.float64)
    org_count = int(org_ids.shape[0])

    buyer_mask = edge_buyer >= 0
    expected_purchases = np.zeros(org_count, dtype=np.float64)
    if bool(np.any(buyer_mask)):
        expected_purchases += np.bincount(
            edge_buyer[buyer_mask],
            weights=(goods + fee)[buyer_mask],
            minlength=org_count,
        )
    seller_rows = np.full(edge_source.shape[0], -1, dtype=np.int64)
    is_org_source = cell_owner_kind[edge_source] == 0
    for edge in np.flatnonzero(is_org_source):
        seller_rows[edge] = org_row_by_id.get(int(cell_owner_id[edge_source[edge]]), -1)
    seller_mask = (seller_rows >= 0) & (goods > 0.0)
    carrier_mask = (edge_transport >= 0) & (fee > 0.0)
    expected_receipts = np.zeros(org_count, dtype=np.float64)
    if bool(np.any(seller_mask)):
        expected_receipts += np.bincount(
            seller_rows[seller_mask], weights=goods[seller_mask], minlength=org_count
        )
    if bool(np.any(carrier_mask)):
        expected_receipts += np.bincount(
            edge_transport[carrier_mask], weights=fee[carrier_mask], minlength=org_count
        )
    residual = max(
        _close(
            "organization_purchases_by_buyer",
            np.asarray(flows.organization_purchases, dtype=np.float64),
            expected_purchases,
        ),
        _close(
            "organization_sales_receipts_by_seller_carrier",
            np.asarray(flows.organization_sales_receipts, dtype=np.float64),
            expected_receipts,
        ),
    )

    expected_pairs: dict[tuple[int, int], float] = {}
    for edge in np.flatnonzero(buyer_mask):
        buyer = int(edge_buyer[edge])
        seller = int(seller_rows[edge])
        if seller >= 0 and goods[edge] > 0.0:
            key = (buyer, seller)
            expected_pairs[key] = expected_pairs.get(key, 0.0) + float(goods[edge])
        carrier = int(edge_transport[edge])
        if carrier >= 0 and fee[edge] > 0.0:
            key = (buyer, carrier)
            expected_pairs[key] = expected_pairs.get(key, 0.0) + float(fee[edge])

    actual_pairs: dict[tuple[int, int], float] = {}
    for row in journal:
        if row.kind != "goods_payment":
            continue
        if row.debit_owner_kind != "organization" or row.credit_owner_kind != "organization":
            continue
        debit_row = org_row_by_id.get(int(row.debit_owner_id), -1)
        credit_row = org_row_by_id.get(int(row.credit_owner_id), -1)
        if debit_row < 0 or credit_row < 0:
            continue
        key = (debit_row, credit_row)
        actual_pairs[key] = actual_pairs.get(key, 0.0) + float(row.amount)

    missing = sorted(set(expected_pairs) - set(actual_pairs))
    if missing:
        _reject(f"goods_payment journal is missing buyer/seller pair(s) {missing}")
    extra = sorted(set(actual_pairs) - set(expected_pairs))
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
    return residual


def _check_stock_cells(
    opening: MaterialStockSnapshot,
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    network: MaterialNetwork,
) -> float:
    """Reconstruct every stock cell with the gate's own continuity model."""
    prices = build_material_prices(parameters)
    continuity = _reconstruct(opening, state, flows, network, prices, parameters)
    residual = np.abs(np.asarray(continuity.stock_residual, dtype=np.float64))
    tolerance = np.asarray(continuity.stock_tolerance, dtype=np.float64)
    if bool(np.any(residual > tolerance)):
        bad = int(np.argmax(residual - tolerance))
        _reject(
            f"stock_cell_continuity[cell={bad}] absolute residual {float(residual[bad])!r} "
            f"exceeds tolerance {float(tolerance[bad])!r}"
        )
    expiry = float(np.sum(np.asarray(continuity.services_leftover, dtype=np.float64)))
    expiry_residual = _close(
        "expired_services_reconciliation",
        np.asarray([expiry]),
        np.asarray([float(flows.expired_services)]),
    )
    return max(float(np.max(residual)) if residual.size else 0.0, expiry_residual)


def _check_bank_books(
    opening: MaterialStockSnapshot,
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
) -> float:
    reserves = np.asarray(state.bank_reserves, dtype=np.float64)
    if bool(np.any(reserves < -ATOL)):
        _reject("bank reserves went negative")
    assets = (
        np.asarray(state.bank_loan_asset, dtype=np.float64)
        + np.asarray(state.bank_interest_receivable, dtype=np.float64)
        + reserves
    )
    liabilities = np.asarray(state.bank_deposit_liability, dtype=np.float64) + np.asarray(
        state.bank_equity, dtype=np.float64
    )
    residual = _close("bank_assets_equal_liabilities", assets, liabilities)

    org_bank = np.asarray(state.organization_bank, dtype=np.int64)
    banks = int(reserves.shape[0])
    org_type = np.asarray(state.organization_type, dtype=np.int64)
    borrower = (org_bank >= 0) & (org_type != _BANK_TYPE_CODE)
    drawn = np.asarray(flows.organization_credit_drawn, dtype=np.float64)
    paid = np.asarray(flows.organization_principal_paid, dtype=np.float64)
    drawn_by_bank = np.zeros(banks, dtype=np.float64)
    paid_by_bank = np.zeros(banks, dtype=np.float64)
    if banks and bool(np.any(borrower)):
        drawn_by_bank += np.bincount(
            org_bank[borrower], weights=drawn[borrower], minlength=banks
        )
        paid_by_bank += np.bincount(
            org_bank[borrower], weights=paid[borrower], minlength=banks
        )
    residual = max(
        residual,
        _close(
            "bank_loan_asset_continuity",
            np.asarray(state.bank_loan_asset, dtype=np.float64),
            np.asarray(opening.bank_loan_asset, dtype=np.float64)
            + drawn_by_bank
            - paid_by_bank,
        ),
    )
    due = np.asarray(flows.organization_interest_due, dtype=np.float64)
    paid_interest = np.asarray(flows.organization_interest_paid, dtype=np.float64)
    due_by_bank = np.zeros(banks, dtype=np.float64)
    paid_interest_by_bank = np.zeros(banks, dtype=np.float64)
    if banks and bool(np.any(borrower)):
        due_by_bank += np.bincount(
            org_bank[borrower], weights=due[borrower], minlength=banks
        )
        paid_interest_by_bank += np.bincount(
            org_bank[borrower], weights=paid_interest[borrower], minlength=banks
        )
    residual = max(
        residual,
        _close(
            "bank_interest_receivable_continuity",
            np.asarray(state.bank_interest_receivable, dtype=np.float64),
            np.asarray(opening.bank_interest_receivable, dtype=np.float64)
            + due_by_bank
            - paid_interest_by_bank,
        ),
    )
    fraction = float(parameters.interest_sink_remittance_fraction)
    remitted_by_bank = np.zeros(banks, dtype=np.float64)
    if banks and bool(np.any(borrower)):
        remitted_by_bank += np.bincount(
            org_bank[borrower],
            weights=paid_interest[borrower] * fraction,
            minlength=banks,
        )
    residual = max(
        residual,
        _close(
            "bank_equity_interest_continuity",
            np.asarray(state.bank_equity, dtype=np.float64),
            np.asarray(opening.bank_equity, dtype=np.float64)
            + due_by_bank
            - remitted_by_bank,
        ),
    )
    deposit_sources = np.zeros(banks, dtype=np.float64)
    if banks:
        deposit_sources += np.bincount(
            np.asarray(state.household_region, dtype=np.int64) % banks,
            weights=np.asarray(state.household_weight, dtype=np.float64)
            * np.asarray(state.household_cash, dtype=np.float64),
            minlength=banks,
        )
        if bool(np.any(borrower)):
            deposit_sources += np.bincount(
                org_bank[borrower],
                weights=np.asarray(state.organization_cash, dtype=np.float64)[borrower],
                minlength=banks,
            )
        deposit_sources[0] += float(state.treasury_deposit) + float(state.credit_fund)
    residual = max(
        residual,
        _close(
            "deposit_liability_composition",
            np.asarray(state.bank_deposit_liability, dtype=np.float64),
            deposit_sources,
        ),
    )
    return residual


def _credit_rows(
    opening: MaterialStockSnapshot,
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    trace: dict[str, np.ndarray],
    journal: tuple[PaymentJournalRow, ...],
) -> tuple[tuple[CreditBudgetRow, ...], float]:
    org_ids = np.asarray(state.organization_id, dtype=np.int64)
    org_bank = np.asarray(state.organization_bank, dtype=np.int64)
    org_type = np.asarray(state.organization_type, dtype=np.int64)
    non_bank = org_type != _BANK_TYPE_CODE
    requested = np.asarray(flows.organization_credit_requested, dtype=np.float64)
    approved = np.asarray(flows.organization_credit_approved, dtype=np.float64)
    drawn = np.asarray(flows.organization_credit_drawn, dtype=np.float64)
    paid = np.asarray(flows.organization_principal_paid, dtype=np.float64)
    wage_due = np.asarray(flows.organization_wage_due, dtype=np.float64)
    wage_paid = np.asarray(flows.organization_wage_paid, dtype=np.float64)
    interest_due = np.asarray(flows.organization_interest_due, dtype=np.float64)
    interest_paid = np.asarray(flows.organization_interest_paid, dtype=np.float64)
    purchases = np.asarray(flows.organization_purchases, dtype=np.float64)
    opening_cash = np.asarray(opening.organization_cash, dtype=np.float64)
    opening_principal = np.asarray(opening.organization_principal, dtype=np.float64)
    opening_wage_arrears = np.asarray(opening.organization_wage_arrears, dtype=np.float64)
    opening_interest_arrears = np.asarray(
        opening.organization_interest_arrears, dtype=np.float64
    )
    closing_cash = np.asarray(state.organization_cash, dtype=np.float64)
    closing_principal = np.asarray(state.organization_principal, dtype=np.float64)
    closing_wage_arrears = np.asarray(state.organization_wage_arrears, dtype=np.float64)
    closing_interest_arrears = np.asarray(
        state.organization_interest_arrears, dtype=np.float64
    )
    caps = np.asarray(trace["credit_approval_caps"], dtype=np.float64)
    input_cost = np.asarray(trace["input_order_cost"], dtype=np.float64)
    old_cost = np.asarray(trace["old_project_cost"], dtype=np.float64)
    new_cost = np.asarray(trace["new_investment_request_cost"], dtype=np.float64)
    goods_cash = np.asarray(trace["cash_available_for_goods"], dtype=np.float64)
    earmarked = np.asarray(trace["input_credit_earmarked"], dtype=np.float64)
    fraction = float(parameters.principal_repayment_fraction)

    invalid = (~non_bank) | (org_bank < 0)
    if bool(np.any(caps[invalid] != 0.0)):
        bad = int(np.flatnonzero(invalid & (caps != 0.0))[0])
        _reject(
            f"credit_approval_caps[{bad}] must be 0 for a bank or an "
            "organization without a bank"
        )

    residual = 0.0
    rows: list[CreditBudgetRow] = []
    for row in np.flatnonzero(non_bank):
        org_id = int(org_ids[row])
        bank = int(org_bank[row])
        scheduled = float(opening_principal[row]) * fraction
        unpaid = max(scheduled - float(paid[row]), 0.0)
        draw_rows, principal_rows = _check_lender_journals(
            org_id=org_id,
            org_row=int(row),
            bank_index=bank,
            drawn=float(drawn[row]),
            principal_paid=float(paid[row]),
            journal=journal,
            state=state,
        )
        if bank < 0 and float(drawn[row]) > ATOL:
            _reject(f"organization {org_id} has no bank but drew credit")
        residual = max(
            residual,
            _at_most(
                f"credit_approved_le_request[org={org_id}]",
                np.asarray([approved[row]]),
                np.asarray([requested[row]]),
            ),
            _at_most(
                f"credit_drawn_le_approved[org={org_id}]",
                np.asarray([drawn[row]]),
                np.asarray([approved[row]]),
            ),
            _at_most(
                f"credit_drawn_le_cap[org={org_id}]",
                np.asarray([drawn[row]]),
                np.asarray([caps[row]]),
            ),
            _close(
                f"principal_continuity[org={org_id}]",
                np.asarray([closing_principal[row]]),
                np.asarray([opening_principal[row] + drawn[row] - paid[row]]),
            ),
            _at_most(
                f"principal_paid_le_scheduled[org={org_id}]",
                np.asarray([paid[row]]),
                np.asarray([scheduled]),
            ),
            _at_most(
                f"earmarked_le_drawn[org={org_id}]",
                np.asarray([earmarked[row]]),
                np.asarray([drawn[row]]),
            ),
            _close(
                f"wage_arrears_continuity[org={org_id}]",
                np.asarray([closing_wage_arrears[row]]),
                np.asarray(
                    [opening_wage_arrears[row] + wage_due[row] - wage_paid[row]]
                ),
            ),
            _close(
                f"interest_arrears_continuity[org={org_id}]",
                np.asarray([closing_interest_arrears[row]]),
                np.asarray(
                    [
                        opening_interest_arrears[row]
                        + interest_due[row]
                        - interest_paid[row]
                    ]
                ),
            ),
        )
        if bank >= 0:
            deposit_id = int(bank_account_ids(state, AccountKind.DEPOSIT_LIABILITY)[bank])
            asset_id = int(bank_account_ids(state, AccountKind.LOAN_ASSET)[bank])
        else:
            deposit_id = -1
            asset_id = -1
        rows.append(
            CreditBudgetRow(
                organization_id=org_id,
                bank_index=bank,
                requested=float(requested[row]),
                approval_cap=float(caps[row]),
                approved=float(approved[row]),
                drawn=float(drawn[row]),
                opening_cash=float(opening_cash[row]),
                opening_principal=float(opening_principal[row]),
                wage_due=float(wage_due[row]),
                wage_paid=float(wage_paid[row]),
                interest_due=float(interest_due[row]),
                interest_paid=float(interest_paid[row]),
                scheduled_principal=float(scheduled),
                principal_paid=float(paid[row]),
                principal_unpaid=float(unpaid),
                input_order_cost=float(input_cost[row]),
                old_project_cost=float(old_cost[row]),
                new_investment_request_cost=float(new_cost[row]),
                cash_available_for_goods=float(goods_cash[row]),
                input_credit_earmarked=float(earmarked[row]),
                purchases=float(purchases[row]),
                closing_cash=float(closing_cash[row]),
                closing_principal=float(closing_principal[row]),
                drawdown_journal_rows=draw_rows,
                principal_journal_rows=principal_rows,
                cash_account_id=int(organization_account_ids(state, AccountKind.CASH_DEPOSIT)[row]),
                loan_liability_account_id=int(
                    organization_account_ids(state, AccountKind.LOAN_LIABILITY)[row]
                ),
                bank_deposit_liability_account_id=deposit_id,
                bank_loan_asset_account_id=asset_id,
            )
        )
    return tuple(rows), residual


def _input_and_edge_rows(
    state: MaterialState,
    flows: MaterialTickFlows,
    network: MaterialNetwork,
    trace: dict[str, np.ndarray],
) -> tuple[tuple[ProcurementInputRow, ...], tuple[ProcurementEdgeRow, ...], float]:
    k_count = int(network.input_cell.shape[0])
    activity_org = np.asarray(network.activity_org_index, dtype=np.int64)
    input_activity = np.asarray(network.input_activity, dtype=np.int64)
    input_cell = np.asarray(network.input_cell, dtype=np.int64)
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_stage = np.asarray(network.cell_stage, dtype=np.int64)
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    cell_region = np.asarray(network.cell_region, dtype=np.int64)
    edge_demand = np.asarray(network.edge_demand, dtype=np.int64)
    edge_count = int(edge_demand.shape[0])
    edge_source = np.asarray(network.edge_source_cell, dtype=np.int64)
    edge_destination = np.asarray(network.edge_destination_cell, dtype=np.int64)
    edge_transport = np.asarray(network.edge_transport_org, dtype=np.int64)
    edge_buyer = np.asarray(network.edge_buyer_org, dtype=np.int64)
    org_ids = np.asarray(state.organization_id, dtype=np.int64)
    org_bank = np.asarray(state.organization_bank, dtype=np.int64)
    org_row_by_id = {int(org_id): row for row, org_id in enumerate(org_ids)}
    banks = int(state.bank_reserves.shape[0])

    buyer_rows = activity_org[input_activity[:k_count]]
    selected = np.flatnonzero(buyer_rows >= 0)
    if selected.size == 0:
        return (), (), 0.0

    desired = np.asarray(flows.desired, dtype=np.float64)
    ordered_gross = np.asarray(flows.ordered_gross, dtype=np.float64)
    ordered = np.asarray(flows.ordered, dtype=np.float64)
    unfunded = np.asarray(flows.unfunded_order, dtype=np.float64)
    allocated = np.asarray(flows.allocated, dtype=np.float64)
    delivered = np.asarray(flows.delivered, dtype=np.float64)
    used = np.asarray(flows.used, dtype=np.float64)
    inventory_open = np.asarray(flows.inventory_open, dtype=np.float64)
    inventory_close = np.asarray(flows.inventory_close, dtype=np.float64)
    physical_blocked = np.asarray(flows.physical_delivery_blocked, dtype=np.float64)
    financial_blocked = np.asarray(flows.financial_delivery_blocked, dtype=np.float64)
    edge_allocated = np.asarray(flows.edge_allocated, dtype=np.float64)
    edge_delivered = np.asarray(flows.edge_delivered, dtype=np.float64)
    edge_fee = np.asarray(flows.edge_service_fee, dtype=np.float64)
    unit_price = np.asarray(trace["edge_unit_price"], dtype=np.float64)

    selected_set = set(int(value) for value in selected)
    edge_selected = np.flatnonzero(
        np.isin(edge_demand, np.fromiter(selected_set, dtype=np.int64))
    )
    goods_by_demand = np.zeros(int(demand_cell.shape[0]), dtype=np.float64)
    fee_by_demand = np.zeros(int(demand_cell.shape[0]), dtype=np.float64)
    if edge_selected.size:
        goods = edge_delivered[edge_selected] * unit_price[edge_selected]
        goods_by_demand += np.bincount(
            edge_demand[edge_selected], weights=goods, minlength=goods_by_demand.size
        )
        fee_by_demand += np.bincount(
            edge_demand[edge_selected],
            weights=edge_fee[edge_selected],
            minlength=fee_by_demand.size,
        )

    residual = 0.0
    input_rows: list[ProcurementInputRow] = []
    for demand in selected:
        input_index = int(network.demand_input_index[demand])
        if input_index < 0:
            _reject(f"input demand {demand} has no K-axis index")
        activity = int(input_activity[input_index])
        cell = int(input_cell[input_index])
        commodity_id = str(network.commodity_ids[int(cell_commodity[cell])])
        spec = commodity_spec(commodity_id)
        org_id = int(org_ids[int(buyer_rows[demand])])
        residual = max(
            residual,
            _close(
                f"gross_is_ordered_plus_unfunded[input={input_index}]",
                np.asarray([ordered[demand] + unfunded[demand]]),
                np.asarray([ordered_gross[demand]]),
            ),
            _at_most(
                f"allocated_le_ordered[input={input_index}]",
                np.asarray([allocated[demand]]),
                np.asarray([ordered[demand]]),
            ),
            _at_most(
                f"delivered_le_allocated[input={input_index}]",
                np.asarray([delivered[demand]]),
                np.asarray([allocated[demand]]),
            ),
            _close(
                f"blocked_is_allocated_minus_delivered[input={input_index}]",
                np.asarray([physical_blocked[demand] + financial_blocked[demand]]),
                np.asarray([allocated[demand] - delivered[demand]]),
            ),
        )
        if spec.stockable:
            residual = max(
                residual,
                _at_most(
                    f"input_availability[input={input_index}]",
                    np.asarray([used[demand]]),
                    np.asarray([inventory_open[demand] + delivered[demand]]),
                ),
                _close(
                    f"input_inventory_closure[input={input_index}]",
                    np.asarray([inventory_close[demand]]),
                    np.asarray([inventory_open[demand] + delivered[demand] - used[demand]]),
                ),
            )
        input_rows.append(
            ProcurementInputRow(
                organization_id=org_id,
                input_index=input_index,
                demand_index=int(demand),
                activity_index=activity,
                cell_index=cell,
                commodity_id=commodity_id,
                stage=_STAGE_NAMES[int(cell_stage[cell])],
                unit=spec.unit,
                desired=float(desired[demand]),
                ordered_gross=float(ordered_gross[demand]),
                ordered=float(ordered[demand]),
                unfunded_order=float(unfunded[demand]),
                allocated=float(allocated[demand]),
                delivered=float(delivered[demand]),
                used=float(used[demand]),
                inventory_open=float(inventory_open[demand]),
                inventory_close=float(inventory_close[demand]),
                goods_payment=float(goods_by_demand[demand]),
                freight_payment=float(fee_by_demand[demand]),
                upstream_unfunded=float(ordered_gross[demand] - ordered[demand]),
                allocation_gap=float(ordered[demand] - allocated[demand]),
                physical_delivery_blocked=float(physical_blocked[demand]),
                financial_delivery_blocked=float(financial_blocked[demand]),
            )
        )

    # A cell shared by several K rows is reconciled once, after aggregation.
    by_cell: dict[int, list[int]] = {}
    for input_row in input_rows:
        by_cell.setdefault(input_row.cell_index, []).append(input_row.demand_index)
    for cell, demands in by_cell.items():
        indexes = np.asarray(demands, dtype=np.int64)
        if not commodity_spec(str(network.commodity_ids[int(cell_commodity[cell])])).stockable:
            continue
        delivered_total = float(np.sum(delivered[indexes]))
        used_total = float(np.sum(used[indexes]))
        open_value = float(inventory_open[indexes[0]])
        close_value = float(inventory_close[indexes[0]])
        residual = max(
            residual,
            _close(
                f"cell_inventory_closure[cell={cell}]",
                np.asarray([close_value]),
                np.asarray([open_value + delivered_total - used_total]),
            ),
        )

    edge_rows: list[ProcurementEdgeRow] = []
    for edge in edge_selected:
        source = int(edge_source[edge])
        destination = int(edge_destination[edge])
        source_kind = int(cell_owner_kind[source])
        seller_org_id = int(cell_owner_id[source]) if source_kind == 0 else -1
        buyer_org_row = int(edge_buyer[edge])
        buyer_org_id = int(org_ids[buyer_org_row]) if buyer_org_row >= 0 else -1
        transport_row = int(edge_transport[edge])
        transport_org_id = int(org_ids[transport_row]) if transport_row >= 0 else -1
        owner_row = org_row_by_id.get(int(cell_owner_id[source]), -1)
        source_bank = (
            int(org_bank[owner_row])
            if source_kind == 0 and owner_row >= 0
            else (int(cell_region[source]) % banks if source_kind == 1 and banks else -1)
        )
        destination_bank = (
            int(org_bank[buyer_org_row])
            if buyer_org_row >= 0
            else (
                int(cell_region[destination]) % banks
                if destination >= 0 and banks
                else -1
            )
        )
        goods_payment = float(edge_delivered[edge]) * float(unit_price[edge])
        residual = max(
            residual,
            _at_most(
                f"edge_delivered_le_allocated[edge={edge}]",
                np.asarray([edge_delivered[edge]]),
                np.asarray([edge_allocated[edge]]),
            ),
        )
        edge_rows.append(
            ProcurementEdgeRow(
                edge_index=int(edge),
                demand_index=int(edge_demand[edge]),
                source_cell=source,
                destination_cell=destination,
                source_owner_kind=_OWNER_KIND_NAMES.get(source_kind, f"kind_{source_kind}"),
                source_owner_id=int(cell_owner_id[source]),
                seller_organization_id=seller_org_id,
                buyer_organization_id=buyer_org_id,
                transport_organization_id=transport_org_id,
                source_bank_index=source_bank,
                destination_bank_index=destination_bank,
                allocated=float(edge_allocated[edge]),
                delivered=float(edge_delivered[edge]),
                goods_payment=goods_payment,
                freight_payment=float(edge_fee[edge]),
            )
        )

    delivered_by_demand = np.bincount(
        edge_demand[edge_selected],
        weights=edge_delivered[edge_selected],
        minlength=delivered.shape[0],
    )
    for demand in selected:
        residual = max(
            residual,
            _close(
                f"edge_sum_is_delivered[input={int(network.demand_input_index[demand])}]",
                np.asarray([delivered_by_demand[demand]]),
                np.asarray([delivered[demand]]),
            ),
        )

    all_edges = np.arange(edge_count, dtype=np.int64)
    if all_edges.size:
        all_goods = edge_delivered[all_edges] * unit_price[all_edges]
        org_buying = edge_buyer[all_edges] >= 0
        if bool(np.any(org_buying)):
            purchased = all_goods + edge_fee[all_edges]
            residual = max(
                residual,
                _close(
                    "organization_purchases_equal_delivered_payments",
                    np.asarray([float(np.sum(purchased[org_buying]))]),
                    np.asarray([float(np.sum(flows.organization_purchases))]),
                ),
            )
        seller = cell_owner_kind[edge_source[all_edges]] == 0
        carrier = edge_transport[all_edges] >= 0
        receipts = np.where(seller, all_goods, 0.0) + np.where(
            carrier, edge_fee[all_edges], 0.0
        )
        residual = max(
            residual,
            _close(
                "organization_sales_receipts_equal_delivered_payments",
                np.asarray([float(np.sum(receipts))]),
                np.asarray([float(np.sum(flows.organization_sales_receipts))]),
            ),
        )
    return tuple(input_rows), tuple(edge_rows), residual


def measure_procurement_credit_tick(
    opening: MaterialStockSnapshot,
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    network: MaterialNetwork,
    *,
    trace: Mapping[str, np.ndarray],
    invariants: InvariantSummary,
) -> ProcurementCreditFunnel:
    """Measure one admitted H3B tick without mutating state, flows or network."""
    if int(flows.tick) != int(state.completed_ticks):
        _reject(
            f"flows.tick {int(flows.tick)} does not match state.completed_ticks "
            f"{int(state.completed_ticks)}"
        )
    organization_count = int(state.organization_id.shape[0])
    demand_count = int(network.demand_cell.shape[0])
    edge_count = int(network.edge_source_cell.shape[0])
    arrays = _validate_trace(
        trace,
        organization_count=organization_count,
        demand_count=demand_count,
        edge_count=edge_count,
    )
    expiry = np.asarray(invariants.expired_leftover_by_cell, dtype=np.float64)
    if expiry.shape != (int(network.cell_owner_kind.shape[0]),):
        _reject("invariant expiry sink shape does not match the stock-cell axis")
    if not bool(np.all(np.isfinite(expiry))) or bool(np.any(expiry < -ATOL)):
        _reject("invariant expiry sink must be finite and non-negative")
    if float(invariants.max_material_tolerance_ratio) > 1.0:
        _reject("material invariant gate did not pass")
    if float(invariants.max_finance_tolerance_ratio) > 1.0:
        _reject("finance invariant gate did not pass")

    directory = build_account_directory(state)
    run_id = _transaction_groups(flows)
    journal = _journal_rows(flows, run_id, directory)
    credit_rows, credit_residual = _credit_rows(
        opening,
        state,
        flows,
        parameters,
        arrays,
        journal,
    )
    credit_residual = max(
        credit_residual,
        _check_payment_journals(
            state, flows, network, journal, arrays["edge_unit_price"]
        ),
    )
    stock_residual = _check_stock_cells(opening, state, flows, parameters, network)
    input_rows, edge_rows, physical_residual = _input_and_edge_rows(
        state, flows, network, arrays
    )
    physical_residual = max(physical_residual, stock_residual)
    bank_residual = _check_bank_books(opening, state, flows, parameters)
    return ProcurementCreditFunnel(
        tick=int(flows.tick),
        quarter=str(flows.quarter),
        credit_budgets=credit_rows,
        inputs=input_rows,
        edges=edge_rows,
        journal=journal,
        max_credit_residual=credit_residual,
        max_physical_residual=physical_residual,
        max_bank_residual=bank_residual,
    )
