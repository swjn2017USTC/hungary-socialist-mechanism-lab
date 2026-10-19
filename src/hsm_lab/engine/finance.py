"""Closed-ledger finance for the material economy (P02 plan section 4).

Domestic currency: ``p02_domestic_currency`` (never calibrated HUF). USD and
``cmea_settlement_unit`` are separate books; currencies are never netted.

Every Journal transaction has paired, same-currency, equal-amount legs with
PK ``(transaction_id, leg_index)``. Household state values are per represented
household; Journal amounts for households are represented amounts
(``weight *`` delta). Bank deposit liability equals
``sum(weighted household cash) + organization cash + treasury deposit``.

Implementation notes (deviations forced by the pinned surfaces, see the
function docstrings for details):

* ``MaterialTickFlows`` carries no ``transaction_id`` column (only ``tick`` /
  ``leg``), so ``transaction_id`` is accepted and consumed sequentially by
  caller convention; leg groups restart ``journal_leg`` at 0 per transaction.
* Wage accrual journals organization-side ``wage_expense``/``wage_payable``
  pairs; household wage claims are pooled nationally by equivalent-person
  share, so per-household legs are journaled when claims convert to cash
  (``wage_payment`` cash/receivable pairs) instead of an O*N accrual fan-out.
* Debt service (interest + principal cash payments) is settled inside
  :func:`run_domestic_finance_step` before the kernel's goods ordering; the
  returned goods budget is the post-debt-service cash. Opening principal is 0
  at t0, so early-tick interest is nil.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from hsm_lab.contract.material import (
    COMMODITY_INDEX,
    DEFAULT_STRATEGIC_IMPORTANCE,
    INDUSTRIAL_TECHNOLOGY_IDS,
    ORGANIZATION_TYPE_ORDER,
    MaterialInitialRecipe,
    MaterialParameters,
    OrganizationType,
)
from hsm_lab.engine.state import MaterialState, MaterialTickFlows

DOMESTIC_CURRENCY = "p02_domestic_currency"
USD_CURRENCY = "USD"
CMEA_CURRENCY = "cmea_settlement_unit"

_LEDGER_TOLERANCE = 1e-9

_BANK_TYPE_CODE = ORGANIZATION_TYPE_ORDER.index(OrganizationType.BANK)


class AccountKind:
    """Exact account_kind vocabulary (owner_kind distinguishes bank/borrower)."""

    CASH_DEPOSIT = "cash_deposit"
    DEPOSIT_LIABILITY = "deposit_liability"
    LOAN_ASSET = "loan_asset"
    LOAN_LIABILITY = "loan_liability"
    RESERVES = "reserves"
    EQUITY = "equity"
    INTEREST_RECEIVABLE = "interest_receivable"
    INTEREST_PAYABLE = "interest_payable"
    WAGE_RECEIVABLE = "wage_receivable"
    WAGE_PAYABLE = "wage_payable"
    SALES_INCOME = "sales_income"
    INPUT_EXPENSE = "input_expense"
    WAGE_EXPENSE = "wage_expense"
    INTEREST_EXPENSE = "interest_expense"
    GRANT_INCOME = "grant_income"
    FISCAL_EXPENSE = "fiscal_expense"
    TRADE_SETTLEMENT = "trade_settlement"
    PLOT_CLEARING = "plot_clearing"
    EXPORT_RECEIVABLE = "export_receivable"
    BAD_DEBT_ALLOWANCE = "bad_debt_allowance"
    BAD_DEBT_EXPENSE = "bad_debt_expense"
    EXPORT_SALES_INCOME = "export_sales_income"


class JournalError(RuntimeError):
    """A Journal leg violates pairing/equality/currency invariants."""


# ---------------------------------------------------------------------------
# Account directory: arithmetic id layout shared by directory and journals.
# ---------------------------------------------------------------------------

HOUSEHOLD_ACCOUNT_KINDS: tuple[str, ...] = (
    AccountKind.CASH_DEPOSIT,
    AccountKind.WAGE_RECEIVABLE,
)
ORGANIZATION_ACCOUNT_KINDS: tuple[str, ...] = (
    AccountKind.CASH_DEPOSIT,
    AccountKind.LOAN_LIABILITY,
    AccountKind.INTEREST_PAYABLE,
    AccountKind.WAGE_PAYABLE,
    AccountKind.WAGE_EXPENSE,
    AccountKind.INTEREST_EXPENSE,
    AccountKind.INPUT_EXPENSE,
    AccountKind.SALES_INCOME,
    AccountKind.GRANT_INCOME,
)
BANK_ACCOUNT_KINDS: tuple[str, ...] = (
    AccountKind.RESERVES,
    AccountKind.EQUITY,
    AccountKind.LOAN_ASSET,
    AccountKind.DEPOSIT_LIABILITY,
    AccountKind.INTEREST_RECEIVABLE,
)
TREASURY_ACCOUNT_KINDS: tuple[str, ...] = (
    AccountKind.CASH_DEPOSIT,
    AccountKind.FISCAL_EXPENSE,
    AccountKind.LOAN_ASSET,
)
#: H3F-D1 Treasury-side term-loan accounts.  They are appended *after* the
#: plot-clearing block (not inside ``TREASURY_ACCOUNT_KINDS``) so the legacy
#: foreign and plot account ids remain bit-identical on every existing path.
TREASURY_TERM_ACCOUNT_KINDS: tuple[str, ...] = (
    AccountKind.LOAN_LIABILITY,
    AccountKind.INTEREST_PAYABLE,
    AccountKind.INTEREST_EXPENSE,
)
#: H3F-D2 Treasury export-receivable accounts, one block per currency.  The
#: block starts after the D1 term block, so every legacy/D1 account id and
#: journal remains bit-identical when D2 is switched off.
TREASURY_RECEIVABLE_ACCOUNT_KINDS: tuple[str, ...] = (
    AccountKind.EXPORT_RECEIVABLE,
    AccountKind.BAD_DEBT_ALLOWANCE,
    AccountKind.BAD_DEBT_EXPENSE,
    AccountKind.EXPORT_SALES_INCOME,
)
_RECEIVABLE_CURRENCIES: tuple[str, ...] = (USD_CURRENCY, CMEA_CURRENCY)


def _axis_sizes(state: MaterialState) -> tuple[int, int, int, int]:
    return (
        int(state.household_id.shape[0]),
        int(state.organization_id.shape[0]),
        int(state.bank_reserves.shape[0]),
        int(state.dwelling_stock.shape[0]),
    )


def _account_bases(state: MaterialState) -> tuple[int, int, int, int, int, int]:
    """(household, organization, bank, treasury, foreign, plot) base ids."""
    n_households, n_orgs, n_banks, n_regions = _axis_sizes(state)
    base_org = len(HOUSEHOLD_ACCOUNT_KINDS) * n_households
    base_bank = base_org + len(ORGANIZATION_ACCOUNT_KINDS) * n_orgs
    base_treasury = base_bank + len(BANK_ACCOUNT_KINDS) * n_banks
    base_foreign = base_treasury + len(TREASURY_ACCOUNT_KINDS)
    base_plot = base_foreign + 2  # foreign_usd + foreign_cmea
    return base_org, base_bank, base_treasury, base_foreign, base_plot, 0


def household_account_ids(state: MaterialState, account_kind: str) -> np.ndarray:
    """Account ids (N,) for one household account kind (row = household row)."""
    position = HOUSEHOLD_ACCOUNT_KINDS.index(account_kind)
    return (
        np.arange(state.household_id.shape[0], dtype=np.int64) * len(HOUSEHOLD_ACCOUNT_KINDS)
        + position
    )


def organization_account_ids(state: MaterialState, account_kind: str) -> np.ndarray:
    """Account ids (O,) for one organization account kind."""
    position = ORGANIZATION_ACCOUNT_KINDS.index(account_kind)
    base_org = len(HOUSEHOLD_ACCOUNT_KINDS) * int(state.household_id.shape[0])
    return (
        base_org
        + np.arange(state.organization_id.shape[0], dtype=np.int64)
        * len(ORGANIZATION_ACCOUNT_KINDS)
        + position
    )


def bank_account_ids(state: MaterialState, account_kind: str) -> np.ndarray:
    """Account ids (B,) for one bank account kind (dense bank axis)."""
    position = BANK_ACCOUNT_KINDS.index(account_kind)
    n_households, n_orgs, _, _ = _axis_sizes(state)
    base_bank = (
        len(HOUSEHOLD_ACCOUNT_KINDS) * n_households + len(ORGANIZATION_ACCOUNT_KINDS) * n_orgs
    )
    return (
        base_bank
        + np.arange(state.bank_reserves.shape[0], dtype=np.int64) * len(BANK_ACCOUNT_KINDS)
        + position
    )


def treasury_account_id(state: MaterialState, account_kind: str) -> int:
    """Account id of the single treasury account of one kind."""
    position = TREASURY_ACCOUNT_KINDS.index(account_kind)
    n_households, n_orgs, n_banks, _ = _axis_sizes(state)
    base_treasury = (
        len(HOUSEHOLD_ACCOUNT_KINDS) * n_households
        + len(ORGANIZATION_ACCOUNT_KINDS) * n_orgs
        + len(BANK_ACCOUNT_KINDS) * n_banks
    )
    return base_treasury + position


def foreign_account_id(state: MaterialState, currency: str) -> int:
    """Account id of the foreign trade-settlement account of one currency."""
    if currency == USD_CURRENCY:
        offset = 0
    elif currency == CMEA_CURRENCY:
        offset = 1
    else:
        raise JournalError(f"unknown foreign currency: {currency!r}")
    n_households, n_orgs, n_banks, _ = _axis_sizes(state)
    base_foreign = (
        len(HOUSEHOLD_ACCOUNT_KINDS) * n_households
        + len(ORGANIZATION_ACCOUNT_KINDS) * n_orgs
        + len(BANK_ACCOUNT_KINDS) * n_banks
        + len(TREASURY_ACCOUNT_KINDS)
    )
    return base_foreign + offset


def treasury_term_account_id(state: MaterialState, account_kind: str) -> int:
    """Account id of one H3F-D1 Treasury term-loan account.

    The block starts after every pre-existing account block (including the
    per-region plot clearing accounts), so adding D1 never shifts the ids of
    legacy treasury/foreign/plot accounts or the journals that use them.
    """
    position = TREASURY_TERM_ACCOUNT_KINDS.index(account_kind)
    n_households, n_orgs, n_banks, n_regions = _axis_sizes(state)
    base_term = (
        len(HOUSEHOLD_ACCOUNT_KINDS) * n_households
        + len(ORGANIZATION_ACCOUNT_KINDS) * n_orgs
        + len(BANK_ACCOUNT_KINDS) * n_banks
        + len(TREASURY_ACCOUNT_KINDS)
        + 2  # foreign_usd + foreign_cmea
        + n_regions
    )
    return base_term + position


def treasury_receivable_account_id(
    state: MaterialState, currency: str, account_kind: str
) -> int:
    """Account id of one H3F-D2 Treasury receivable account in one currency.

    The block starts after the D1 term block, so no legacy or D1 id shifts.
    Each currency has its own four account ids; journals never mix currencies.
    """
    if account_kind not in TREASURY_RECEIVABLE_ACCOUNT_KINDS:
        raise JournalError(f"unknown receivable account kind: {account_kind!r}")
    if currency not in _RECEIVABLE_CURRENCIES:
        raise JournalError(f"unknown receivable currency: {currency!r}")
    position = TREASURY_RECEIVABLE_ACCOUNT_KINDS.index(account_kind)
    currency_offset = _RECEIVABLE_CURRENCIES.index(currency) * len(
        TREASURY_RECEIVABLE_ACCOUNT_KINDS
    )
    n_households, n_orgs, n_banks, n_regions = _axis_sizes(state)
    base_term = (
        len(HOUSEHOLD_ACCOUNT_KINDS) * n_households
        + len(ORGANIZATION_ACCOUNT_KINDS) * n_orgs
        + len(BANK_ACCOUNT_KINDS) * n_banks
        + len(TREASURY_ACCOUNT_KINDS)
        + 2  # foreign_usd + foreign_cmea
        + n_regions
    )
    base_receivable = base_term + len(TREASURY_TERM_ACCOUNT_KINDS)
    return base_receivable + currency_offset + position


def plot_clearing_account_ids(state: MaterialState) -> np.ndarray:
    """Account ids (R,) of the per-region ephemeral plot clearing accounts."""
    _, n_orgs, n_banks, _ = _axis_sizes(state)
    n_households = int(state.household_id.shape[0])
    base_plot = (
        len(HOUSEHOLD_ACCOUNT_KINDS) * n_households
        + len(ORGANIZATION_ACCOUNT_KINDS) * n_orgs
        + len(BANK_ACCOUNT_KINDS) * n_banks
        + len(TREASURY_ACCOUNT_KINDS)
        + 2
    )
    return base_plot + np.arange(state.dwelling_stock.shape[0], dtype=np.int64)


def build_account_directory(state: MaterialState) -> dict[tuple[str, int, str, str], int]:
    """Canonical ``(owner_kind, owner_id, currency, account_kind)`` -> account id.

    Owner kinds: household (owner_id = household id), organization (canonical
    organization id), bank_<dense>, treasury, foreign_usd, foreign_cmea,
    plot_clearing_<region>.  Ids follow the arithmetic layout of the
    ``*_account_ids`` helpers, so journals and the directory can never drift.
    """
    directory: dict[tuple[str, int, str, str], int] = {}

    household_ids = state.household_id.tolist()
    for _position, kind in enumerate(HOUSEHOLD_ACCOUNT_KINDS):
        ids = household_account_ids(state, kind)
        for owner_id, account_id in zip(household_ids, ids.tolist(), strict=False):
            directory[("household", owner_id, DOMESTIC_CURRENCY, kind)] = account_id

    organization_ids = state.organization_id.tolist()
    for kind in ORGANIZATION_ACCOUNT_KINDS:
        ids = organization_account_ids(state, kind)
        for owner_id, account_id in zip(organization_ids, ids.tolist(), strict=False):
            directory[("organization", owner_id, DOMESTIC_CURRENCY, kind)] = account_id

    for dense in range(state.bank_reserves.shape[0]):
        owner_kind = f"bank_{dense}"
        for kind in BANK_ACCOUNT_KINDS:
            directory[(owner_kind, dense, DOMESTIC_CURRENCY, kind)] = int(
                bank_account_ids(state, kind)[dense]
            )

    for kind in TREASURY_ACCOUNT_KINDS:
        directory[("treasury", 0, DOMESTIC_CURRENCY, kind)] = treasury_account_id(state, kind)
    for kind in TREASURY_TERM_ACCOUNT_KINDS:
        directory[("treasury", 0, DOMESTIC_CURRENCY, kind)] = treasury_term_account_id(
            state, kind
        )
    for currency in _RECEIVABLE_CURRENCIES:
        for kind in TREASURY_RECEIVABLE_ACCOUNT_KINDS:
            directory[("treasury", 0, currency, kind)] = treasury_receivable_account_id(
                state, currency, kind
            )
    directory[("foreign_usd", 0, USD_CURRENCY, AccountKind.TRADE_SETTLEMENT)] = foreign_account_id(
        state, USD_CURRENCY
    )
    directory[("foreign_cmea", 0, CMEA_CURRENCY, AccountKind.TRADE_SETTLEMENT)] = (
        foreign_account_id(state, CMEA_CURRENCY)
    )

    plot_ids = plot_clearing_account_ids(state)
    for region, account_id in enumerate(plot_ids.tolist()):
        directory[
            (f"plot_clearing_{region}", region, DOMESTIC_CURRENCY, AccountKind.PLOT_CLEARING)
        ] = account_id

    return directory


# ---------------------------------------------------------------------------
# Journal assembly (vectorized bulk appends; no per-org numeric loops).
# ---------------------------------------------------------------------------


def append_transaction(
    flows: MaterialTickFlows,
    *,
    transaction_id: int,
    kind: str,
    legs: list[tuple[int, int, str, float]],
    organization_id: int | None = None,
    event_id: str | None = None,
) -> None:
    """Append one transaction's paired legs after validating invariants.

    ``legs`` entries are ``(debit_account, credit_account, currency, amount)``.
    Raises :class:`JournalError` on empty legs, non-finite or non-positive
    amounts (zero-amount legs are rejected), mixed currencies within one
    transaction, or debit/credit sum mismatch (each leg debits its debit
    account and credits its credit account by the same amount, so the
    transaction-level balance check is structural).
    """
    if not legs:
        raise JournalError("transaction must carry at least one leg")
    currencies = {leg[2] for leg in legs}
    if len(currencies) != 1:
        raise JournalError(f"mixed currencies within one transaction: {sorted(currencies)}")
    amounts = np.asarray([leg[3] for leg in legs], dtype=np.float64)
    if not np.all(np.isfinite(amounts)) or np.any(amounts <= 0.0):
        raise JournalError("leg amounts must be finite and strictly positive")
    debit_total = math.fsum(amounts.tolist())
    credit_total = math.fsum(amounts.tolist())  # legs are self-balancing pairs
    if abs(debit_total - credit_total) > _LEDGER_TOLERANCE:
        raise JournalError(f"debit/credit sums differ by {abs(debit_total - credit_total):.3e}")
    _append_legs(
        flows,
        kind=kind,
        currency=legs[0][2],
        debit=np.asarray([leg[0] for leg in legs], dtype=np.int64),
        credit=np.asarray([leg[1] for leg in legs], dtype=np.int64),
        amount=amounts,
        organization_ids=organization_id,
        leg_offset=0,
        event_id=event_id,
    )


def _append_legs(
    flows: MaterialTickFlows,
    *,
    kind: str,
    currency: str,
    debit: np.ndarray,
    credit: np.ndarray,
    amount: np.ndarray,
    organization_ids: int | None | np.ndarray | list[Any] = None,
    leg_offset: int = 0,
    event_id: str | None = None,
) -> int:
    """Bulk-append prevalidated legs of one transaction (vectorized)."""
    amount = np.asarray(amount, dtype=np.float64)
    count = int(amount.shape[0])
    if count == 0:
        return 0
    if not np.all(np.isfinite(amount)) or np.any(amount <= 0.0):
        raise JournalError("journal legs must carry finite, strictly positive amounts")
    debit = np.asarray(debit, dtype=np.int64)
    credit = np.asarray(credit, dtype=np.int64)
    if debit.shape[0] != count or credit.shape[0] != count:
        raise JournalError("debit/credit/amount leg columns must align")
    org_column: list[int | None]
    if organization_ids is None or isinstance(organization_ids, (int, np.integer)):
        scalar = None if organization_ids is None else int(organization_ids)
        org_column = [scalar] * count
    else:
        org_column = [int(value) if value is not None else None for value in organization_ids]

    flows.journal_kind.extend([kind] * count)
    flows.journal_tick.extend([flows.tick] * count)
    flows.journal_debit.extend(debit.tolist())
    flows.journal_credit.extend(credit.tolist())
    flows.journal_currency.extend([currency] * count)
    flows.journal_amount.extend(amount.tolist())
    flows.journal_org.extend(org_column)
    flows.journal_leg.extend(range(leg_offset, leg_offset + count))
    flows.journal_event.extend([event_id] * count)
    return count


def _append_paired_transactions(
    flows: MaterialTickFlows,
    *,
    kind: str,
    amounts: np.ndarray,
    org_ids: np.ndarray,
    first_debit: np.ndarray,
    first_credit: np.ndarray,
    second_debit: np.ndarray,
    second_credit: np.ndarray,
) -> None:
    """One two-leg transaction per organization with ``amounts > 0``."""
    mask = amounts > 0.0
    count = int(np.count_nonzero(mask))
    if count == 0:
        return
    paired_amount = np.empty(2 * count, dtype=np.float64)
    debit = np.empty(2 * count, dtype=np.int64)
    credit = np.empty(2 * count, dtype=np.int64)
    org_column = np.empty(2 * count, dtype=object)
    paired_amount[0::2] = amounts[mask]
    paired_amount[1::2] = amounts[mask]
    debit[0::2] = np.asarray(first_debit, dtype=np.int64)[mask]
    debit[1::2] = np.asarray(second_debit, dtype=np.int64)[mask]
    credit[0::2] = np.asarray(first_credit, dtype=np.int64)[mask]
    credit[1::2] = np.asarray(second_credit, dtype=np.int64)[mask]
    org_column[0::2] = org_ids[mask]
    org_column[1::2] = org_ids[mask]
    _append_legs(
        flows,
        kind=kind,
        currency=DOMESTIC_CURRENCY,
        debit=debit,
        credit=credit,
        amount=paired_amount,
        organization_ids=org_column,
    )


# ---------------------------------------------------------------------------
# Shared pure helpers.
# ---------------------------------------------------------------------------


def quarter_domestic_credit_rate(parameters: MaterialParameters) -> float:
    """Annual domestic rate / 4 (P02 plan: .04 annual -> .01 quarterly)."""
    return float(parameters.domestic_credit_rate_annual) / 4.0


def quarter_external_rate(global_rate_percent: float, parameters: MaterialParameters) -> float:
    """``global_rate_percent/400 + hungary_spread_annual/4``."""
    return float(global_rate_percent) / 400.0 + float(parameters.hungary_spread_annual) / 4.0


def _person_shares(state: MaterialState) -> np.ndarray:
    """Per-represented-household share (N,) of one unit per represented person.

    ``share_h = size_h / sum(weight * size)`` so that
    ``sum(weight * share * total) == total`` for any pooled payment.
    """
    weight = np.asarray(state.household_weight, dtype=np.float64)
    size = np.asarray(state.household_size, dtype=np.float64)
    persons = float(np.sum(weight * size))
    if persons <= 0.0:
        return np.zeros_like(size)
    return size / persons


_TYPE_STRATEGIC_IMPORTANCE = np.array(
    [
        0.5,  # industrial_soe: replaced by technology-row lookup when resolvable
        DEFAULT_STRATEGIC_IMPORTANCE["field_farming"],
        DEFAULT_STRATEGIC_IMPORTANCE["field_farming"],
        DEFAULT_STRATEGIC_IMPORTANCE["building_construction"],
        DEFAULT_STRATEGIC_IMPORTANCE["freight_transport"],
        DEFAULT_STRATEGIC_IMPORTANCE["wholesale_procurement"],
        DEFAULT_STRATEGIC_IMPORTANCE["retail"],
        DEFAULT_STRATEGIC_IMPORTANCE["public_service"],
        DEFAULT_STRATEGIC_IMPORTANCE["bank"],
    ],
    dtype=np.float64,
)
_INDUSTRIAL_STRATEGIC_IMPORTANCE = np.array(
    [DEFAULT_STRATEGIC_IMPORTANCE[tid] for tid in INDUSTRIAL_TECHNOLOGY_IDS],
    dtype=np.float64,
)
_INDUSTRIAL_TYPE_CODE = ORGANIZATION_TYPE_ORDER.index(OrganizationType.INDUSTRIAL_SOE)


def _default_strategic_importance(state: MaterialState) -> np.ndarray:
    """Fallback strategic importance (O,) from org type + technology row."""
    org_type = np.asarray(state.organization_type, dtype=np.int64)
    strategic = _TYPE_STRATEGIC_IMPORTANCE[np.clip(org_type, 0, None)]
    industrial = org_type == _INDUSTRIAL_TYPE_CODE
    tech_row = np.asarray(state.organization_technology, dtype=np.int64)
    resolvable = industrial & (tech_row >= 0) & (tech_row < len(_INDUSTRIAL_STRATEGIC_IMPORTANCE))
    strategic[resolvable] = _INDUSTRIAL_STRATEGIC_IMPORTANCE[tech_row[resolvable]]
    return strategic


def _resolve_strategic_importance(state: MaterialState, override: np.ndarray | None) -> np.ndarray:
    if override is not None:
        return np.asarray(override, dtype=np.float64)
    return _default_strategic_importance(state)


def _masked_bincount(
    keys: np.ndarray, mask: np.ndarray, values: np.ndarray, minlength: int
) -> np.ndarray:
    """``bincount(keys[mask], weights=values[mask])`` with a zero fallback."""
    totals = np.zeros(minlength, dtype=np.float64)
    if np.any(mask):
        totals += np.bincount(keys[mask], weights=values[mask], minlength=minlength)
    return totals


def _borrower_axes(state: MaterialState) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """(org_bank, safe_bank, borrower_mask, n_banks)."""
    org_bank = np.asarray(state.organization_bank, dtype=np.int64)
    safe_bank = np.where(org_bank >= 0, org_bank, 0)
    bank_rows = np.asarray(state.organization_type, dtype=np.int64) == _BANK_TYPE_CODE
    borrower = (org_bank >= 0) & ~bank_rows
    return org_bank, safe_bank, borrower, int(state.bank_reserves.shape[0])


def _validate_credit_approval_caps(
    caps: np.ndarray,
    *,
    organization_count: int,
    borrower: np.ndarray,
) -> np.ndarray:
    """Validate the opt-in per-organization approval caps before any entry.

    Caps are domestic-currency amounts on the organization axis.  Banks, and
    organizations without a bank, must carry exactly zero: the cap is an
    approval limit for a real bank borrower, never a second credit source.
    """
    array = np.asarray(caps, dtype=np.float64)
    if array.shape != (organization_count,):
        raise ValueError(
            "credit_approval_caps must have shape "
            f"({organization_count},), got {array.shape}"
        )
    if not bool(np.all(np.isfinite(array))):
        raise ValueError("credit_approval_caps contains a non-finite value")
    if bool(np.any(array < 0.0)):
        bad = int(np.argmin(array))
        raise ValueError(f"credit_approval_caps[{bad}]={float(array[bad])!r} is negative")
    invalid = ~np.asarray(borrower, dtype=bool)
    if bool(np.any(array[invalid] != 0.0)):
        bad = int(np.flatnonzero(invalid & (array != 0.0))[0])
        raise ValueError(
            f"credit_approval_caps[{bad}] must be 0 for a bank or an organization "
            "without a bank"
        )
    return array


def _append_interbank_legs(
    state: MaterialState,
    flows: MaterialTickFlows,
    *,
    kind: str,
    delta: np.ndarray,
    leg_offset: int,
) -> int:
    """Reserve + deposit-liability migration legs for cross-bank settlement.

    ``delta[b]`` is bank b's net deposit inflow (== net reserve inflow,
    ``sum(delta) == 0``).  Legs pair gaining banks against losing banks.
    """
    remaining = np.asarray(delta, dtype=np.float64).copy()
    debit_liability = bank_account_ids(state, AccountKind.DEPOSIT_LIABILITY)
    reserves = bank_account_ids(state, AccountKind.RESERVES)
    appended = 0
    while True:
        gainers = np.flatnonzero(remaining > _LEDGER_TOLERANCE)
        losers = np.flatnonzero(remaining < -_LEDGER_TOLERANCE)
        if gainers.size == 0 or losers.size == 0:
            break
        gainer = int(gainers[0])
        loser = int(losers[0])
        amount = float(min(remaining[gainer], -remaining[loser]))
        appended += _append_legs(
            flows,
            kind=kind,
            currency=DOMESTIC_CURRENCY,
            debit=np.array([debit_liability[gainer], reserves[gainer]], dtype=np.int64),
            credit=np.array([debit_liability[loser], reserves[loser]], dtype=np.int64),
            amount=np.array([amount, amount], dtype=np.float64),
            organization_ids=None,
            leg_offset=leg_offset + appended,
        )
        remaining[gainer] -= amount
        remaining[loser] += amount
    return appended


def _execute_wage_payment(
    state: MaterialState,
    flows: MaterialTickFlows,
    *,
    org_paid: np.ndarray,
    household_receipt: np.ndarray,
) -> None:
    """Bank books + one pooled ``wage_payment`` transaction.

    Caller has already moved org cash / household cash / claims / arrears;
    this helper settles per-bank deposit liabilities, interbank reserves and
    journals the transaction (org payable/cash legs, household cash/receivable
    legs at represented amounts, interbank migration legs).
    """
    _, safe_bank, _, n_banks = _borrower_axes(state)
    org_paid = np.asarray(org_paid, dtype=np.float64)
    household_receipt = np.asarray(household_receipt, dtype=np.float64)

    paying = (org_paid > 0.0) & (np.asarray(state.organization_bank, dtype=np.int64) >= 0)
    org_out = _masked_bincount(safe_bank, paying, org_paid, n_banks)
    represented = np.asarray(state.household_weight, dtype=np.float64) * household_receipt
    household_bank = np.asarray(state.household_region, dtype=np.int64) % n_banks
    receiving = represented > 0.0
    household_in = _masked_bincount(household_bank, receiving, represented, n_banks)

    delta = household_in - org_out
    state.bank_deposit_liability = (
        np.asarray(state.bank_deposit_liability, dtype=np.float64) + delta
    )
    state.bank_reserves = np.asarray(state.bank_reserves, dtype=np.float64) + delta

    offset = 0
    wage_payable = organization_account_ids(state, AccountKind.WAGE_PAYABLE)
    org_cash = organization_account_ids(state, AccountKind.CASH_DEPOSIT)
    org_ids = np.asarray(state.organization_id, dtype=np.int64)
    offset += _append_legs(
        flows,
        kind="wage_payment",
        currency=DOMESTIC_CURRENCY,
        debit=wage_payable[paying],
        credit=org_cash[paying],
        amount=org_paid[paying],
        organization_ids=org_ids[paying],
        leg_offset=offset,
    )
    household_cash = household_account_ids(state, AccountKind.CASH_DEPOSIT)
    wage_receivable = household_account_ids(state, AccountKind.WAGE_RECEIVABLE)
    offset += _append_legs(
        flows,
        kind="wage_payment",
        currency=DOMESTIC_CURRENCY,
        debit=household_cash[receiving],
        credit=wage_receivable[receiving],
        amount=represented[receiving],
        organization_ids=None,
        leg_offset=offset,
    )
    _append_interbank_legs(state, flows, kind="wage_payment", delta=delta, leg_offset=offset)


# ---------------------------------------------------------------------------
# Step F: working-capital credit, wages, interest, principal.
# ---------------------------------------------------------------------------


def _settle_interest_payment(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    *,
    org_ids: np.ndarray,
    safe_bank: np.ndarray,
    borrower: np.ndarray,
    interest_paid: np.ndarray,
) -> None:
    """Destroy the legacy share and route the declared share to deposits."""
    paid = np.asarray(interest_paid, dtype=np.float64)
    paid_by_bank = _masked_bincount(safe_bank, borrower, paid, state.bank_reserves.size)
    fraction = float(parameters.interest_sink_remittance_fraction)
    if fraction <= 0.0:
        state.bank_deposit_liability = (
            np.asarray(state.bank_deposit_liability, dtype=np.float64) - paid_by_bank
        )
        state.bank_interest_receivable = (
            np.asarray(state.bank_interest_receivable, dtype=np.float64) - paid_by_bank
        )
        return

    remitted = paid * fraction
    remitted_by_bank = _masked_bincount(
        safe_bank, borrower, remitted, state.bank_reserves.size
    )
    state.bank_interest_receivable = (
        np.asarray(state.bank_interest_receivable, dtype=np.float64) - paid_by_bank
    )
    state.bank_equity = (
        np.asarray(state.bank_equity, dtype=np.float64) - remitted_by_bank
    )
    state.bank_deposit_liability = (
        np.asarray(state.bank_deposit_liability, dtype=np.float64) - paid_by_bank
    )

    recipient_by_bank = np.zeros_like(remitted_by_bank)
    total_remitted = float(remitted.sum())
    if total_remitted > 0.0 and parameters.interest_sink_recipient == "treasury":
        state.treasury_deposit = float(state.treasury_deposit) + total_remitted
        recipient_by_bank[0] = total_remitted
        _append_legs(
            flows,
            kind="interest_recipient_deposit",
            currency=DOMESTIC_CURRENCY,
            debit=np.asarray(
                [treasury_account_id(state, AccountKind.CASH_DEPOSIT)], dtype=np.int64
            ),
            credit=bank_account_ids(state, AccountKind.DEPOSIT_LIABILITY)[:1],
            amount=np.asarray([total_remitted]),
        )
    elif total_remitted > 0.0:
        shares = _person_shares(state)
        receipt = shares * total_remitted
        state.household_cash = np.asarray(state.household_cash, dtype=np.float64) + receipt
        represented = np.asarray(state.household_weight, dtype=np.float64) * receipt
        household_bank = np.asarray(state.household_region, dtype=np.int64) % len(recipient_by_bank)
        recipient_by_bank += np.bincount(
            household_bank, weights=represented, minlength=recipient_by_bank.size
        )
        positive = represented > 0.0
        _append_legs(
            flows,
            kind="interest_recipient_deposit",
            currency=DOMESTIC_CURRENCY,
            debit=household_account_ids(state, AccountKind.CASH_DEPOSIT)[positive],
            credit=bank_account_ids(state, AccountKind.DEPOSIT_LIABILITY)[
                household_bank[positive]
            ],
            amount=represented[positive],
        )

    # Interest payment shrinks the payer-bank deposit. Re-credit the recipient
    # bank and migrate reserves for any cross-bank portion; total deposits fall
    # only by the explicitly destroyed share.
    state.bank_deposit_liability = (
        np.asarray(state.bank_deposit_liability, dtype=np.float64) + recipient_by_bank
    )
    migration = recipient_by_bank - remitted_by_bank
    state.bank_reserves = np.asarray(state.bank_reserves, dtype=np.float64) + migration
    _append_interbank_legs(
        state,
        flows,
        kind="interest_recipient_deposit",
        delta=migration,
        leg_offset=0,
    )


def run_fiscal_turnover_remittance(
    state: MaterialState, flows: MaterialTickFlows, parameters: MaterialParameters
) -> float:
    """Transfer a junior share of sales receipts to the Treasury after purchases."""
    fraction = float(parameters.fiscal_turnover_remittance_fraction)
    if fraction <= 0.0:
        return 0.0
    receipts = np.asarray(flows.organization_sales_receipts, dtype=np.float64)
    cash = np.asarray(state.organization_cash, dtype=np.float64)
    paid = np.minimum(fraction * receipts, cash)
    org_bank, safe_bank, borrower, n_banks = _borrower_axes(state)
    paid[~borrower] = 0.0
    positive = paid > 0.0
    total = float(paid.sum())
    if total <= 0.0:
        return 0.0
    cash[positive] -= paid[positive]
    state.organization_cash = cash
    state.treasury_deposit = float(state.treasury_deposit) + total
    by_bank = _masked_bincount(safe_bank, borrower, paid, n_banks)
    delta = -by_bank
    delta[0] += total
    state.bank_deposit_liability = (
        np.asarray(state.bank_deposit_liability, dtype=np.float64) + delta
    )
    state.bank_reserves = np.asarray(state.bank_reserves, dtype=np.float64) + delta
    _append_legs(
        flows,
        kind="fiscal_turnover_remittance",
        currency=DOMESTIC_CURRENCY,
        debit=np.full(
            int(np.count_nonzero(positive)),
            treasury_account_id(state, AccountKind.CASH_DEPOSIT),
            dtype=np.int64,
        ),
        credit=organization_account_ids(state, AccountKind.CASH_DEPOSIT)[positive],
        amount=paid[positive],
        organization_ids=np.asarray(state.organization_id, dtype=np.int64)[positive],
    )
    _append_interbank_legs(
        state,
        flows,
        kind="fiscal_turnover_remittance",
        delta=delta,
        leg_offset=0,
    )
    return total


def run_domestic_finance_step(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    *,
    wage_bill_open: np.ndarray,
    input_order_cost: np.ndarray,
    old_project_cost: np.ndarray,
    new_investment_request_cost: np.ndarray,
    transaction_base: int,
    strategic_importance: np.ndarray | None = None,
    credit_approval_caps: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Working-capital credit, wage payments, interest, principal (plan step F).

    Order inside the step: credit approval -> wage accrual/payment -> interest
    accrual/payment -> scheduled principal (only from cash left above this
    quarter's input, old-project and new-project needs).  Input/goods payments
    are handled by the kernel from the returned cash budget after this step.
    Returns per-organization cash available for goods purchases.  All Journal
    legs are appended; reserves may never go negative.

    ``credit_approval_caps`` is the H3B opt-in interface.  ``None`` keeps the
    legacy Treasury-credit journals byte-for-byte.  When supplied it caps each
    borrower's total approval after the existing envelope/stock-cap/earmark
    rules, and journals the drawdown/repayment against the borrower's actual
    bank (loan asset and deposit liability) rather than the Treasury.

    Sequence detail: wage accrual and payment are senior; interest accrues on
    opening principal only (new drawdowns pay from next quarter); interest and
    principal cash payments are settled from post-wage cash so the returned
    goods budget is exactly the unspent, non-negative remainder.  Unpaid
    principal keeps its original principal (memo only, never capitalized).
    """
    org_bank, safe_bank, borrower, n_banks = _borrower_axes(state)
    caps = (
        None
        if credit_approval_caps is None
        else _validate_credit_approval_caps(
            credit_approval_caps,
            organization_count=int(state.organization_id.shape[0]),
            borrower=borrower,
        )
    )
    if caps is not None and bool(getattr(parameters, "m2_neutral_credit", False)):
        # The H3B bank-lender journals and the M2-neutral credit-fund path are
        # mutually exclusive; reject before any state or journal mutation.
        raise ValueError(
            "credit_approval_caps is incompatible with m2_neutral_credit=True"
        )
    org_ids = np.asarray(state.organization_id, dtype=np.int64)
    input_order_cost = np.asarray(input_order_cost, dtype=np.float64)
    old_project_cost = np.asarray(old_project_cost, dtype=np.float64)
    new_investment_request_cost = np.asarray(new_investment_request_cost, dtype=np.float64)

    # Account id arrays for the journals below.
    org_cash_ids = organization_account_ids(state, AccountKind.CASH_DEPOSIT)
    org_loan_ids = organization_account_ids(state, AccountKind.LOAN_LIABILITY)
    org_interest_payable_ids = organization_account_ids(state, AccountKind.INTEREST_PAYABLE)
    org_wage_payable_ids = organization_account_ids(state, AccountKind.WAGE_PAYABLE)
    org_wage_expense_ids = organization_account_ids(state, AccountKind.WAGE_EXPENSE)
    org_interest_expense_ids = organization_account_ids(state, AccountKind.INTEREST_EXPENSE)
    bank_deposit_liability_ids = bank_account_ids(state, AccountKind.DEPOSIT_LIABILITY)
    bank_loan_asset_ids = bank_account_ids(state, AccountKind.LOAN_ASSET)
    bank_interest_receivable_ids = bank_account_ids(state, AccountKind.INTEREST_RECEIVABLE)
    bank_equity_ids = bank_account_ids(state, AccountKind.EQUITY)

    # Fixed employment: the full wage bill accrues regardless of output.
    wage_due = float(parameters.wage_rate) * np.asarray(
        state.organization_labor_available, dtype=np.float64
    )
    flows.organization_wage_due = wage_due.copy()

    cash = np.asarray(state.organization_cash, dtype=np.float64).copy()
    wage_arrears_open = np.asarray(state.organization_wage_arrears, dtype=np.float64).copy()
    interest_arrears_open = np.asarray(state.organization_interest_arrears, dtype=np.float64).copy()
    principal_open = np.asarray(state.organization_principal, dtype=np.float64).copy()

    # --- working-capital credit -----------------------------------------
    wage_bill_open = np.asarray(wage_bill_open, dtype=np.float64)
    request = np.where(
        borrower,
        np.maximum(
            wage_due
            + wage_arrears_open
            + input_order_cost
            + old_project_cost
            + new_investment_request_cost
            - cash,
            0.0,
        ),
        0.0,
    )
    weight = (
        1.0
        + _resolve_strategic_importance(state, strategic_importance)
        + np.asarray(state.organization_bailout_expectation, dtype=np.float64)
    )
    earmarked_request = np.minimum(
        np.maximum(float(parameters.input_credit_earmark_fraction), 0.0) * input_order_cost,
        request,
    )
    general_request = np.maximum(request - earmarked_request, 0.0)
    earmarked_approve = earmarked_request.copy()
    approve = np.zeros_like(request)
    # P05 §0.5/§0.7: the working-capital envelope is sized to the bank's actual
    # quarterly financing need (wages + input orders + investment), not the wage
    # bill alone; a wage-bill-only envelope starves the goods circuit.
    bank_wage_bill = _masked_bincount(safe_bank, borrower, wage_bill_open, n_banks)
    bank_input_cost = _masked_bincount(safe_bank, borrower, input_order_cost, n_banks)
    bank_project_cost = _masked_bincount(
        safe_bank, borrower, old_project_cost + new_investment_request_cost, n_banks
    )
    for bank in range(n_banks):  # only loop over banks (B <= 2)
        contenders = borrower & (safe_bank == bank) & (general_request > 0.0)
        if not np.any(contenders):
            continue
        weight_sum = float(weight[contenders].sum())
        if weight_sum <= 0.0:
            continue
        envelope = float(parameters.credit_envelope_fraction) * float(
            bank_wage_bill[bank] + bank_input_cost[bank] + bank_project_cost[bank]
        )
        approve[contenders] = np.minimum(
            general_request[contenders], envelope * weight[contenders] / weight_sum
        )
    # P05 §0.6: optional cap on the standing principal keeps the money stock
    # stationary; once an organization reaches its line it may only borrow as
    # junior repayments free room.
    cap_quarters = float(parameters.credit_stock_cap_quarters)
    if cap_quarters > 0.0:
        cap = cap_quarters * wage_due
        room = np.maximum(cap - principal_open, 0.0)
        earmarked_approve = np.minimum(earmarked_approve, room)
        approve = np.minimum(approve, np.maximum(room - earmarked_approve, 0.0))
        approve += earmarked_approve
    else:
        # Purpose-tied input credit is an additional line above the general
        # working-capital envelope; it can only cover the declared input order.
        approve += earmarked_approve
    if caps is not None:
        # H3B: the policy limit caps the total (general + earmarked) approval
        # after every legacy rationing rule, and never exceeds the request.
        capped = np.minimum(np.minimum(approve, request), caps)
        earmarked_approve = np.minimum(earmarked_approve, capped)
        approve = capped
    draw = approve.copy()
    earmarked_draw = earmarked_approve.copy()
    if bool(getattr(parameters, "m2_neutral_credit", False)):
        # a deposit pool cannot go negative: scale the quarter's draws to the fund
        fund = float(state.credit_fund)
        total_requested = float(np.sum(draw))
        if total_requested > fund and total_requested > 0.0:
            scale = fund / total_requested
            draw = draw * scale
            earmarked_draw = earmarked_draw * scale
    total_draw = float(np.sum(draw))
    # Keep the purpose-tied tranche out of the wage-payment pool. It becomes
    # available to the goods circuit only after senior wages have been paid.
    general_draw = np.maximum(draw - earmarked_draw, 0.0)
    cash += general_draw
    state.organization_principal = principal_open + draw
    draw_by_bank = _masked_bincount(safe_bank, borrower & (draw > 0.0), draw, n_banks)
    # P05 §0.6: with M2-neutral credit the fixed credit-fund deposit (bank 0) is
    # redistributed to the borrowers instead of the banks creating new deposits;
    # otherwise the legacy bank money-creation path is used.
    if bool(getattr(parameters, "m2_neutral_credit", False)):
        state.credit_fund = float(state.credit_fund) - total_draw
        state.treasury_loan_asset = float(state.treasury_loan_asset) + total_draw
        deposit_delta = draw_by_bank.copy()
        deposit_delta[0] = deposit_delta[0] - total_draw
        state.bank_deposit_liability = (
            np.asarray(state.bank_deposit_liability, dtype=np.float64) + deposit_delta
        )
        state.bank_reserves = np.asarray(state.bank_reserves, dtype=np.float64) + deposit_delta
    else:
        state.bank_loan_asset = np.asarray(state.bank_loan_asset, dtype=np.float64) + draw_by_bank
        state.bank_deposit_liability = (
            np.asarray(state.bank_deposit_liability, dtype=np.float64) + draw_by_bank
        )
    flows.organization_credit_requested = request.copy()
    flows.organization_credit_approved = approve.copy()
    flows.organization_credit_drawn = draw.copy()
    treasury_cash_ids = np.full(
        draw.shape[0], treasury_account_id(state, AccountKind.CASH_DEPOSIT), dtype=np.int64
    )
    treasury_loan_ids = np.full(
        draw.shape[0], treasury_account_id(state, AccountKind.LOAN_ASSET), dtype=np.int64
    )
    if caps is None:
        _append_paired_transactions(
            flows,
            kind="loan_drawdown",
            amounts=draw,
            org_ids=org_ids,
            first_debit=org_cash_ids,
            first_credit=treasury_cash_ids,
            second_debit=treasury_loan_ids,
            second_credit=org_loan_ids,
        )
    else:
        # H3B: the bank creates the deposit and holds the loan asset.
        _append_paired_transactions(
            flows,
            kind="loan_drawdown",
            amounts=draw,
            org_ids=org_ids,
            first_debit=org_cash_ids,
            first_credit=bank_deposit_liability_ids[safe_bank],
            second_debit=bank_loan_asset_ids[safe_bank],
            second_credit=org_loan_ids,
        )

    # --- wage accrual (org expense/payable; household claims pooled) -----
    shares = _person_shares(state)
    total_due = float(wage_due.sum())
    state.household_wage_claim = (
        np.asarray(state.household_wage_claim, dtype=np.float64) + shares * total_due
    )
    state.organization_wage_arrears = wage_arrears_open + wage_due
    due_mask = wage_due > 0.0
    _append_legs(
        flows,
        kind="wage_accrual",
        currency=DOMESTIC_CURRENCY,
        debit=org_wage_expense_ids[due_mask],
        credit=org_wage_payable_ids[due_mask],
        amount=wage_due[due_mask],
        organization_ids=org_ids[due_mask],
    )

    # --- wage payment (senior; fixed employment, arrears included) -------
    payable = wage_due + wage_arrears_open
    wage_paid = np.minimum(cash, payable)
    cash -= wage_paid
    total_paid = float(wage_paid.sum())
    receipt = shares * total_paid
    state.household_cash = np.asarray(state.household_cash, dtype=np.float64) + receipt
    state.household_wage_claim = np.asarray(state.household_wage_claim, dtype=np.float64) - receipt
    state.organization_wage_arrears = wage_arrears_open + wage_due - wage_paid
    flows.organization_wage_paid = wage_paid.copy()
    flows.household_wage_income = receipt.copy()
    _execute_wage_payment(state, flows, org_paid=wage_paid, household_receipt=receipt)

    # The earmarked line can finance goods after wages; it cannot substitute
    # for the general line in the household wage transfer.
    cash += earmarked_draw

    # --- interest on opening principal (accrual, then cash payment) ------
    interest_due = principal_open * quarter_domestic_credit_rate(parameters)
    due_by_bank = _masked_bincount(
        safe_bank, borrower & (interest_due > 0.0), interest_due, n_banks
    )
    state.organization_interest_arrears = interest_arrears_open + interest_due
    state.bank_interest_receivable = (
        np.asarray(state.bank_interest_receivable, dtype=np.float64) + due_by_bank
    )
    state.bank_equity = np.asarray(state.bank_equity, dtype=np.float64) + due_by_bank
    flows.organization_interest_due = interest_due.copy()
    _append_paired_transactions(
        flows,
        kind="interest_accrual",
        amounts=interest_due,
        org_ids=org_ids,
        first_debit=bank_interest_receivable_ids[safe_bank],
        first_credit=bank_equity_ids[safe_bank],
        second_debit=org_interest_expense_ids,
        second_credit=org_interest_payable_ids,
    )
    interest_paid = np.minimum(cash, interest_arrears_open + interest_due)
    cash -= interest_paid
    state.organization_interest_arrears = interest_arrears_open + interest_due - interest_paid
    interest_paid_mask = borrower & (interest_paid > 0.0)
    if float(parameters.interest_sink_remittance_fraction) == 0.0:
        interest_paid_by_bank = _masked_bincount(
            safe_bank, interest_paid_mask, interest_paid, n_banks
        )
        state.bank_deposit_liability = (
            np.asarray(state.bank_deposit_liability, dtype=np.float64) - interest_paid_by_bank
        )
        state.bank_interest_receivable = (
            np.asarray(state.bank_interest_receivable, dtype=np.float64) - interest_paid_by_bank
        )
        _append_paired_transactions(
            flows,
            kind="interest_payment",
            amounts=interest_paid,
            org_ids=org_ids,
            first_debit=org_interest_payable_ids,
            first_credit=org_cash_ids,
            second_debit=bank_deposit_liability_ids[safe_bank],
            second_credit=bank_interest_receivable_ids[safe_bank],
        )
    else:
        _append_legs(
            flows,
            kind="interest_payment",
            currency=DOMESTIC_CURRENCY,
            debit=org_interest_payable_ids[interest_paid_mask],
            credit=org_cash_ids[interest_paid_mask],
            amount=interest_paid[interest_paid_mask],
            organization_ids=org_ids[interest_paid_mask],
        )
        _settle_interest_payment(
            state,
            flows,
            parameters,
            org_ids=org_ids,
            safe_bank=safe_bank,
            borrower=borrower,
            interest_paid=interest_paid,
        )
    flows.organization_interest_paid = interest_paid.copy()

    # --- scheduled principal repayment (unpaid stays, never capitalized) -
    # Repayment is junior to this quarter's input funding: it uses only cash
    # left after the purchases the borrower still has to make, so recycling
    # credit never starves the goods circuit.
    scheduled = principal_open * float(parameters.principal_repayment_fraction)
    remaining_need = input_order_cost + old_project_cost + new_investment_request_cost
    principal_paid = np.minimum(np.maximum(cash - remaining_need, 0.0), scheduled)
    cash -= principal_paid
    state.organization_principal = principal_open + draw - principal_paid
    total_paid = float(np.sum(principal_paid))
    paid_by_bank = _masked_bincount(
        safe_bank, borrower & (principal_paid > 0.0), principal_paid, n_banks
    )
    if bool(getattr(parameters, "m2_neutral_credit", False)):
        state.credit_fund = float(state.credit_fund) + total_paid
        state.treasury_loan_asset = float(state.treasury_loan_asset) - total_paid
        repay_delta = -paid_by_bank
        repay_delta[0] = repay_delta[0] + total_paid
        state.bank_deposit_liability = (
            np.asarray(state.bank_deposit_liability, dtype=np.float64) + repay_delta
        )
        state.bank_reserves = np.asarray(state.bank_reserves, dtype=np.float64) + repay_delta
    else:
        state.bank_loan_asset = np.asarray(state.bank_loan_asset, dtype=np.float64) - paid_by_bank
        state.bank_deposit_liability = (
            np.asarray(state.bank_deposit_liability, dtype=np.float64) - paid_by_bank
        )
    flows.organization_principal_paid = principal_paid.copy()
    if caps is None:
        _append_paired_transactions(
            flows,
            kind="principal_repayment",
            amounts=principal_paid,
            org_ids=org_ids,
            first_debit=treasury_cash_ids,
            first_credit=org_cash_ids,
            second_debit=org_loan_ids,
            second_credit=treasury_loan_ids,
        )
    else:
        # H3B: the borrower's liability and deposit fall, and the actual bank's
        # loan asset and deposit liability fall by the same amount.
        _append_paired_transactions(
            flows,
            kind="principal_repayment",
            amounts=principal_paid,
            org_ids=org_ids,
            first_debit=org_loan_ids,
            first_credit=org_cash_ids,
            second_debit=bank_deposit_liability_ids[safe_bank],
            second_credit=bank_loan_asset_ids[safe_bank],
        )

    state.organization_cash = cash
    return {
        "cash_available_for_goods": cash,
        "input_credit_earmarked": earmarked_draw,
    }


def run_working_capital_cycle(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
) -> float:
    """P05 §0.6 joint closure: recycle the M2-neutral working capital, then
    redistribute the residual soft-budget deficit.

    With ``m2_neutral_credit`` the quarter's drawdowns came out of the credit
    fund; here the borrowers return whatever cash they hold above a one-quarter
    wage buffer, restoring the fund (no money created or destroyed).  Then
    ``run_sbc_redistribution`` tops any still-insolvent organization up from
    profitable peers' surplus.  Returns the total recycled to the fund.
    """
    if not bool(getattr(parameters, "m2_neutral_credit", False)):
        return run_sbc_redistribution(state, flows, parameters)
    fraction = float(parameters.principal_repayment_fraction)
    principal = np.asarray(state.organization_principal, dtype=np.float64)
    drawn = np.asarray(flows.organization_credit_drawn, dtype=np.float64)
    already = np.asarray(flows.organization_principal_paid, dtype=np.float64)
    opening = principal - drawn + already
    allowance = np.maximum(opening * fraction - already, 0.0)
    cash = np.asarray(state.organization_cash, dtype=np.float64)
    buffer = float(parameters.wage_rate) * np.asarray(
        state.organization_labor_available, dtype=np.float64
    )
    repay = np.minimum(np.minimum(principal, allowance), np.maximum(cash - buffer, 0.0))
    repaid = float(np.sum(repay))
    if repaid > 0.0:
        state.organization_cash = cash - repay
        state.organization_principal = principal - repay
        state.credit_fund = float(state.credit_fund) + repaid
        state.treasury_loan_asset = float(state.treasury_loan_asset) - repaid
        bank = np.asarray(state.organization_bank, dtype=np.int64)
        n_banks = int(state.bank_reserves.shape[0])
        safe_bank = np.where(bank >= 0, bank, 0)
        delta = _masked_bincount(safe_bank, repay > 0.0, -repay, n_banks)
        delta[0] = delta[0] + repaid
        state.bank_deposit_liability = (
            np.asarray(state.bank_deposit_liability, dtype=np.float64) + delta
        )
        state.bank_reserves = np.asarray(state.bank_reserves, dtype=np.float64) + delta
        flows.organization_principal_paid = already + repay
    run_sbc_redistribution(state, flows, parameters)
    return repaid


def run_sbc_redistribution(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
) -> float:
    """P05 §0.6 explicit soft-budget-constraint transfer (SBC 显性化).

    Loss-making organizations are kept solvent by a *fiscal-style*
    redistribution of surplus cash from profitable organizations, not by
    creating new money: every unit transferred leaves a payer's deposit and
    reaches a receiver's, so the money stock is unchanged (M2-neutral).  This is
    the historically explicit state-budget subsidy channel, distinct from bank
    credit.  Returns the total transferred.
    """
    if not bool(getattr(parameters, "sbc_redistribution", False)):
        return 0.0
    cash = np.asarray(state.organization_cash, dtype=np.float64)
    org_type = np.asarray(state.organization_type, dtype=np.int64)
    bank = np.asarray(state.organization_bank, dtype=np.int64)
    is_bank = org_type == _BANK_TYPE_CODE
    buffer = float(parameters.wage_rate) * np.asarray(
        state.organization_labor_available, dtype=np.float64
    ) + np.asarray(flows.organization_purchases, dtype=np.float64)
    surplus = np.where(~is_bank, np.maximum(cash - buffer, 0.0), 0.0)
    deficit = np.where(~is_bank, np.maximum(buffer - cash, 0.0), 0.0)
    total_surplus = float(np.sum(surplus))
    total_deficit = float(np.sum(deficit))
    if total_deficit <= 0.0 or total_surplus <= 0.0:
        return 0.0
    scale = min(1.0, total_surplus / total_deficit)
    give = deficit * scale
    take = surplus * (float(np.sum(give)) / total_surplus)
    net = give - take
    state.organization_cash = cash + net
    flows.organization_sbc_transfer = net.copy()
    n_banks = int(state.bank_reserves.shape[0])
    safe_bank = np.where(bank >= 0, bank, 0)
    delta = _masked_bincount(safe_bank, ~is_bank, net, n_banks)
    state.bank_deposit_liability = (
        np.asarray(state.bank_deposit_liability, dtype=np.float64) + delta
    )
    state.bank_reserves = np.asarray(state.bank_reserves, dtype=np.float64) + delta
    return float(np.sum(give))


# ---------------------------------------------------------------------------
# Treasury liquidity rescue.
# ---------------------------------------------------------------------------


def run_bailout_step(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    *,
    opening_wage_bill: float,
    transaction_base: int,
    strategic_importance: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Treasury liquidity rescue: request, envelope rationing, expectation update.

    Returns ``(requested, granted)`` per organization. ``rescued_fraction``
    observation drives ``p_next = (1-a) p_old + a * fraction`` (alpha .25).

    The grant is rationed to ``min(request, share of min(bailout envelope,
    remaining treasury deposit))`` by weights ``strategic_importance +
    labor_share + .01`` over requesting orgs; grants never exceed the request
    so the rescued fraction (and the expectation) stays within [0, 1].  Right
    after the grant, orgs spend available cash on wage arrears first (paid to
    households as late receipts that enter ``household_deferred_receipt`` and
    are spendable next tick) and interest arrears second — this runs at tick
    end, i.e. after household rationing, so no separate post-rationing hook
    is needed.  Treasury grants debit the treasury deposit (bank 0) and credit
    borrower deposits; no money is printed.
    """
    org_bank, safe_bank, borrower, n_banks = _borrower_axes(state)
    org_ids = np.asarray(state.organization_id, dtype=np.int64)

    wage_arrears = np.asarray(state.organization_wage_arrears, dtype=np.float64).copy()
    interest_arrears = np.asarray(state.organization_interest_arrears, dtype=np.float64).copy()
    request = np.where(borrower, wage_arrears + interest_arrears, 0.0)

    labor = np.asarray(state.organization_labor_available, dtype=np.float64)
    total_labor = float(labor.sum())
    labor_share = np.divide(labor, total_labor, out=np.zeros_like(labor), where=total_labor > 0)
    weight = _resolve_strategic_importance(state, strategic_importance) + labor_share + 0.01
    eligible = request > 0.0
    grant = np.zeros_like(request)
    weight_sum = float(weight[eligible].sum())
    if np.any(eligible) and weight_sum > 0.0:
        envelope = float(parameters.bailout_envelope_fraction) * float(opening_wage_bill)
        treasury_available = float(state.treasury_deposit)
        grant[eligible] = np.minimum(
            request[eligible],
            min(envelope, treasury_available) * weight[eligible] / weight_sum,
        )
    total_grant = float(grant.sum())

    cash = np.asarray(state.organization_cash, dtype=np.float64) + grant
    state.treasury_deposit = float(state.treasury_deposit) - total_grant
    grant_by_bank = _masked_bincount(safe_bank, borrower & (grant > 0.0), grant, n_banks)
    settlement = grant_by_bank.copy()
    settlement[0] -= total_grant  # treasury deposits at bank 0
    state.bank_deposit_liability = (
        np.asarray(state.bank_deposit_liability, dtype=np.float64) + settlement
    )
    state.bank_reserves = np.asarray(state.bank_reserves, dtype=np.float64) + settlement

    treasury_cash_id = treasury_account_id(state, AccountKind.CASH_DEPOSIT)
    org_cash_ids = organization_account_ids(state, AccountKind.CASH_DEPOSIT)
    granted = grant > 0.0
    offset = _append_legs(
        flows,
        kind="bailout_grant",
        currency=DOMESTIC_CURRENCY,
        debit=np.full(int(np.count_nonzero(granted)), treasury_cash_id, dtype=np.int64),
        credit=org_cash_ids[granted],
        amount=grant[granted],
        organization_ids=org_ids[granted],
    )
    _append_interbank_legs(state, flows, kind="bailout_grant", delta=settlement, leg_offset=offset)

    # Same-tick arrears clearance: wages senior (late receipts), then interest.
    wage_pay = np.minimum(cash, wage_arrears)
    cash -= wage_pay
    interest_pay = np.minimum(cash, interest_arrears)
    cash -= interest_pay
    shares = _person_shares(state)
    receipt = shares * float(wage_pay.sum())
    state.household_cash = np.asarray(state.household_cash, dtype=np.float64) + receipt
    state.household_deferred_receipt = (
        np.asarray(state.household_deferred_receipt, dtype=np.float64) + receipt
    )
    state.household_wage_claim = np.asarray(state.household_wage_claim, dtype=np.float64) - receipt
    state.organization_wage_arrears = wage_arrears - wage_pay
    state.organization_interest_arrears = interest_arrears - interest_pay
    flows.household_late_wage = np.asarray(flows.household_late_wage, dtype=np.float64) + receipt
    flows.organization_wage_paid = (
        np.asarray(flows.organization_wage_paid, dtype=np.float64) + wage_pay
    )
    flows.organization_interest_paid = (
        np.asarray(flows.organization_interest_paid, dtype=np.float64) + interest_pay
    )
    flows.household_cash_close = np.asarray(flows.household_cash_close, dtype=np.float64) + receipt
    _execute_wage_payment(state, flows, org_paid=wage_pay, household_receipt=receipt)
    interest_pay_mask = borrower & (interest_pay > 0.0)
    if float(parameters.interest_sink_remittance_fraction) == 0.0:
        interest_paid_by_bank = _masked_bincount(
            safe_bank, interest_pay_mask, interest_pay, n_banks
        )
        state.bank_deposit_liability = (
            np.asarray(state.bank_deposit_liability, dtype=np.float64) - interest_paid_by_bank
        )
        state.bank_interest_receivable = (
            np.asarray(state.bank_interest_receivable, dtype=np.float64) - interest_paid_by_bank
        )
        _append_paired_transactions(
            flows,
            kind="interest_payment",
            amounts=interest_pay,
            org_ids=org_ids,
            first_debit=organization_account_ids(state, AccountKind.INTEREST_PAYABLE),
            first_credit=org_cash_ids,
            second_debit=bank_account_ids(state, AccountKind.DEPOSIT_LIABILITY)[safe_bank],
            second_credit=bank_account_ids(state, AccountKind.INTEREST_RECEIVABLE)[safe_bank],
        )
    else:
        _append_legs(
            flows,
            kind="interest_payment",
            currency=DOMESTIC_CURRENCY,
            debit=organization_account_ids(state, AccountKind.INTEREST_PAYABLE)[interest_pay_mask],
            credit=org_cash_ids[interest_pay_mask],
            amount=interest_pay[interest_pay_mask],
            organization_ids=org_ids[interest_pay_mask],
        )
        _settle_interest_payment(
            state,
            flows,
            parameters,
            org_ids=org_ids,
            safe_bank=safe_bank,
            borrower=borrower,
            interest_paid=interest_pay,
        )

    rescued_fraction = np.divide(grant, request, out=np.zeros_like(grant), where=request > 0.0)
    alpha = float(parameters.bailout_alpha)
    state.organization_bailout_expectation = (1.0 - alpha) * np.asarray(
        state.organization_bailout_expectation, dtype=np.float64
    ) + alpha * rescued_fraction
    flows.organization_bailout_requested = request.copy()
    flows.organization_bailout_granted = grant.copy()
    state.organization_cash = cash
    return request, grant


# ---------------------------------------------------------------------------
# Rolling one-project-per-org investment expansion.
# ---------------------------------------------------------------------------


def plan_investment(
    state: MaterialState,
    parameters: MaterialParameters,
    *,
    delivered_capital_wip: np.ndarray,
    delivered_construction_wip: np.ndarray,
    investment_cash_budget: np.ndarray | None = None,
    new_request: np.ndarray | None = None,
    new_capacity_cost_per_unit: float | None = None,
) -> dict[str, np.ndarray]:
    """Pure investment plan (no state mutation, no journal — physical flows).

    Old commitments are funded first, each org proportionally from its own
    investment cash budget (appropriation only: cash actually moves at the
    kernel's goods delivery); only fully funded old commitments leave budget
    for new approvals ``min(new_request, remaining_budget / unit_cost)``.
    Completion applies the min rule ``min(capital_wip/cu_k,
    construction_wip/cu_c, approved_not_completed)`` on opening WIP plus this
    tick's deliveries and consumes ``completed * cu`` of each WIP stock.
    """
    capital_unit = float(parameters.capacity_capital_goods_per_unit)
    construction_unit = float(parameters.capacity_construction_per_unit)
    n_orgs = state.organization_capacity.shape[0]
    delivered_capital = np.asarray(delivered_capital_wip, dtype=np.float64)
    delivered_construction = np.asarray(delivered_construction_wip, dtype=np.float64)
    budget = (
        np.zeros(n_orgs, dtype=np.float64)
        if investment_cash_budget is None
        else np.asarray(investment_cash_budget, dtype=np.float64)
    )
    requested = (
        np.zeros(n_orgs, dtype=np.float64)
        if new_request is None
        else np.asarray(new_request, dtype=np.float64)
    )

    capital_wip = np.asarray(state.organization_capital_wip, dtype=np.float64) + delivered_capital
    construction_wip = (
        np.asarray(state.organization_construction_wip, dtype=np.float64) + delivered_construction
    )
    approved_open = np.asarray(state.organization_project_approved, dtype=np.float64).copy()

    completed = np.maximum(
        np.minimum(
            np.minimum(capital_wip / capital_unit, construction_wip / construction_unit),
            approved_open,
        ),
        0.0,
    )
    capital_wip_close = capital_wip - completed * capital_unit
    construction_wip_close = construction_wip - completed * construction_unit

    capital_price = float(parameters.prices[COMMODITY_INDEX["capital_goods"]])
    construction_price = float(parameters.prices[COMMODITY_INDEX["construction"]])
    old_required_capital = np.maximum(capital_unit * approved_open - capital_wip, 0.0)
    old_required_construction = np.maximum(
        construction_unit * approved_open - construction_wip, 0.0
    )
    old_cost = old_required_capital * capital_price + old_required_construction * construction_price
    funded_fraction = np.where(
        old_cost > 0.0,
        np.minimum(1.0, budget / np.where(old_cost > 0.0, old_cost, 1.0)),
        0.0,
    )
    remaining_budget = np.maximum(budget - old_cost * funded_fraction, 0.0)
    unit_cost = (
        capital_unit * capital_price + construction_unit * construction_price
        if new_capacity_cost_per_unit is None
        else float(new_capacity_cost_per_unit)
    )
    approved_new = (
        np.minimum(requested, remaining_budget / unit_cost)
        if unit_cost > 0.0
        else np.zeros_like(requested)
    )
    return {
        "requested": requested,
        "approved_new": approved_new,
        "completed": completed,
        "funded_old_capital": old_required_capital * funded_fraction,
        "funded_old_construction": old_required_construction * funded_fraction,
        "new_capital_orders": approved_new * capital_unit,
        "new_construction_orders": approved_new * construction_unit,
        "remaining_budget": remaining_budget,
        "capital_wip_close": capital_wip_close,
        "construction_wip_close": construction_wip_close,
        "approved_close": approved_open - completed + approved_new,
    }


def run_investment_step(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    *,
    delivered_capital_wip: np.ndarray,
    delivered_construction_wip: np.ndarray,
    investment_cash_budget: np.ndarray | None = None,
    new_request: np.ndarray | None = None,
    new_capacity_cost_per_unit: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rolling one-project-per-org expansion (plan section 4).

    Old commitment funding first; new approval only from the remaining cash
    budget; completion consumes matched WIP; ``capacity_close = capacity_open
    + completed`` (applied by the kernel, which owns production state).
    Returns ``(requested, approved, completed)``.  No Journal legs: WIP
    installation is physical, and investment purchases are journaled by the
    kernel as goods payments on actual delivery only.
    """
    plan = plan_investment(
        state,
        parameters,
        delivered_capital_wip=delivered_capital_wip,
        delivered_construction_wip=delivered_construction_wip,
        investment_cash_budget=investment_cash_budget,
        new_request=new_request,
        new_capacity_cost_per_unit=new_capacity_cost_per_unit,
    )
    state.organization_capital_wip = plan["capital_wip_close"]
    state.organization_construction_wip = plan["construction_wip_close"]
    state.organization_project_approved = plan["approved_close"]
    flows.organization_investment_requested = plan["requested"].copy()
    flows.organization_investment_approved = plan["approved_new"].copy()
    flows.organization_investment_completed = plan["completed"].copy()
    return plan["requested"], plan["approved_new"], plan["completed"]


# ---------------------------------------------------------------------------
# Initialization.
# ---------------------------------------------------------------------------


def initialize_finance(
    state: MaterialState, parameters: MaterialParameters, initial_recipe: MaterialInitialRecipe
) -> None:
    """Initial deposits/equity/reserves per the recipe (2q/10q/1q wage bills).

    Organization deposits = ``organization_deposit_quarters`` x own wage bill;
    treasury deposit = ``treasury_deposit_quarters`` x national wage bill (at
    bank 0); each bank's equity = ``bank_equity_quarters`` x national wage
    bill; reserves = deposit liability + equity - loan assets.  Household cash
    starts from ``initial_recipe.household_cash`` per represented household;
    USD/CMEA accounts come from ``parameters.trade``.  Loan principal, arrears
    and expectations are the state builder's fields and are left untouched.
    """
    wage_rate = float(parameters.wage_rate)
    labor = np.asarray(state.organization_labor_available, dtype=np.float64)
    national_wage_bill = wage_rate * float(labor.sum())
    n_banks = int(state.bank_reserves.shape[0])
    org_bank = np.asarray(state.organization_bank, dtype=np.int64)
    safe_bank = np.where(org_bank >= 0, org_bank, 0)
    bank_rows = np.asarray(state.organization_type, dtype=np.int64) == _BANK_TYPE_CODE
    customer = (org_bank >= 0) & ~bank_rows

    state.household_cash = np.full(
        state.household_id.shape[0], float(initial_recipe.household_cash), dtype=np.float64
    )
    state.organization_cash = (
        float(initial_recipe.organization_deposit_quarters) * wage_rate * labor
    )
    state.treasury_deposit = float(initial_recipe.treasury_deposit_quarters) * national_wage_bill

    state.bank_equity = np.full(
        n_banks, float(initial_recipe.bank_equity_quarters) * national_wage_bill
    )
    state.bank_loan_asset = np.zeros(n_banks, dtype=np.float64)
    state.bank_interest_receivable = np.zeros(n_banks, dtype=np.float64)

    org_deposits = _masked_bincount(safe_bank, customer, state.organization_cash, n_banks)
    household_deposits = _masked_bincount(
        np.asarray(state.household_region, dtype=np.int64) % n_banks,
        np.ones(state.household_id.shape[0], dtype=bool),
        np.asarray(state.household_weight, dtype=np.float64) * state.household_cash,
        n_banks,
    )
    deposits = org_deposits + household_deposits
    deposits[0] += state.treasury_deposit
    state.bank_deposit_liability = deposits
    state.bank_reserves = deposits + state.bank_equity - state.bank_loan_asset

    state.usd_reserve = float(parameters.trade.convertible_opening_reserve)
    state.usd_principal = float(parameters.trade.convertible_opening_principal)
    state.usd_interest_arrears = 0.0
    state.cmea_settlement_balance = 0.0
