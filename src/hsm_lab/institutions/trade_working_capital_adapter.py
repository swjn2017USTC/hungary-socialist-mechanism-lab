"""H3F-D1: limited, term-bound trade working-capital lending to the Treasury.

The legacy Treasury prepay path pays export procurement out of the Treasury's
domestic deposit.  This module adds one explicitly opt-in regime in which a
real bank creates a limited, interest-bearing, maturity-bound domestic loan to
the Treasury, and the draw is sized to the *actual deliverable export
procurement gap* measured by two real kernel probes on discarded state copies.

Design boundaries (all default-off):

* Importing this module registers nothing.  ``run_material`` never imports or
  calls it, and every legacy path is byte-identical.
* The draw/sizing probes run the real ``tick_material`` and never feed their
  results into the admitted tick except through the sized principal.
* The admitted tick is the same real kernel, followed by the ordinary
  material/financial invariant gate plus the D1 treasury-loan continuation
  gates in :mod:`hsm_lab.engine.accounting`.
* The Treasury's housing budget is capped at its pre-draw cash, so the loan can
  only fund export procurement.
* The maturity schedule lives in an immutable :class:`TradeWorkingCapitalBook`
  supplied by the caller; the aggregate principal/arrears are also mirrored in
  ``MaterialState`` so the accounting gate can reconcile them.
* On any failure every ``MaterialState`` field is restored, the book is not
  advanced, the clock is not advanced, and a :class:`TradeWorkingCapitalFailure`
  carrying the failed flows/state is raised.
"""

from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

import numpy as np
from pydantic import Field, model_validator

from hsm_lab.contract.base import ResearchGateError, StrictModel
from hsm_lab.contract.material import MaterialParameters
from hsm_lab.engine import accounting, finance
from hsm_lab.engine.accounting import InvariantSummary, tolerance_for
from hsm_lab.engine.finance import (
    DOMESTIC_CURRENCY,
    AccountKind,
    bank_account_ids,
    treasury_account_id,
    treasury_term_account_id,
)
from hsm_lab.engine.material import tick_material
from hsm_lab.engine.network import MaterialNetwork
from hsm_lab.engine.state import (
    MaterialForcing,
    MaterialState,
    MaterialTickFlows,
    capture_material_stocks,
)
from hsm_lab.institutions.export_finance_adapter import (
    LegacyTradeRegime,
    observe_legacy_trade_tick,
)

REGIME_SCHEMA_VERSION = "hist-trade-working-capital-regime-v1"
REGIME_ID = "limited_trade_working_capital"
SCHEMA_ID = "hist-trade-working-capital-observation-v1"
GATE_PREFIX = "HIST_H3F_D1"

_SERVICE_TOL = 1e-9

#: Strict JSON number: reject booleans and strings instead of coercing them
#: (pydantic's lax float field accepts ``true`` and ``"0.04"``).
StrictFiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]


def _reject(message: str) -> None:
    raise ResearchGateError(f"{GATE_PREFIX}: {message}")


class TradeWorkingCapitalRegime(StrictModel):
    """Frozen synthetic D1 regime: one bank, a limit, a term and a draw window."""

    schema_version: Literal["hist-trade-working-capital-regime-v1"]
    regime_id: Literal["limited_trade_working_capital"]
    source_kind: Literal["synthetic"]
    bank_index: Annotated[int, Field(strict=True, ge=0)]
    credit_limit: Annotated[StrictFiniteFloat, Field(ge=0.0)]
    annual_rate: Annotated[StrictFiniteFloat, Field(ge=0.0)]
    term_quarters: Annotated[int, Field(strict=True, ge=1)]
    draw_tick_start: Annotated[int, Field(strict=True, ge=0)]
    draw_tick_end: Annotated[int, Field(strict=True, ge=0)]

    @model_validator(mode="after")
    def _ordered_window(self) -> TradeWorkingCapitalRegime:
        if self.draw_tick_end < self.draw_tick_start:
            raise ValueError("draw_tick_end must be >= draw_tick_start")
        return self


def load_trade_working_capital_regime(path: str | Path) -> TradeWorkingCapitalRegime:
    """Load exactly one D1 regime file; reject every other shape or literal."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        _reject(f"regime file not found: {file_path}")
    except OSError as exc:
        _reject(f"could not read regime file {file_path}: {exc}")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        _reject(f"invalid JSON in regime file {file_path}: {exc.msg}")
    if not isinstance(payload, dict):
        _reject(f"regime file {file_path} must decode to a JSON object")
    expected_keys = {
        "schema_version",
        "regime_id",
        "source_kind",
        "bank_index",
        "credit_limit",
        "annual_rate",
        "term_quarters",
        "draw_tick_start",
        "draw_tick_end",
    }
    extra = set(payload) - expected_keys
    if extra:
        _reject(f"regime file {file_path} has unexpected keys: {sorted(extra)}")
    if set(payload) != expected_keys:
        _reject(
            f"regime file {file_path} must carry exactly the keys "
            f"{sorted(expected_keys)}; got {sorted(payload)}"
        )
    try:
        return TradeWorkingCapitalRegime.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - any validation rejection is a gate violation
        _reject(f"regime file {file_path} failed validation: {exc}")


@dataclass(frozen=True)
class WorkingCapitalBatch:
    """One drawn tranche with its own fixed maturity and contract rate."""

    draw_tick: int
    maturity_tick: int
    principal: float
    annual_rate: float

    def __post_init__(self) -> None:
        if self.draw_tick < 0 or self.maturity_tick <= self.draw_tick:
            raise ValueError("working-capital batch maturity must be after its draw")
        if not math.isfinite(self.principal) or self.principal < 0.0:
            raise ValueError("working-capital batch principal must be finite and non-negative")
        if not math.isfinite(self.annual_rate) or self.annual_rate < 0.0:
            raise ValueError("working-capital batch rate must be finite and non-negative")


@dataclass(frozen=True)
class TradeWorkingCapitalBook:
    """Immutable D1 loan book: per-batch maturities plus unpaid interest."""

    bank_index: int
    batches: tuple[WorkingCapitalBatch, ...] = ()
    interest_arrears: float = 0.0

    def __post_init__(self) -> None:
        if self.bank_index < 0:
            raise ValueError("working-capital book bank_index must be non-negative")
        if not math.isfinite(self.interest_arrears) or self.interest_arrears < 0.0:
            raise ValueError("working-capital book interest_arrears must be non-negative")

    @property
    def principal(self) -> float:
        return math.fsum(batch.principal for batch in self.batches)


@dataclass(frozen=True)
class TradeWorkingCapitalResult:
    """One admitted D1 tick; the caller must reuse ``book`` for the next tick."""

    flows: MaterialTickFlows
    gate: InvariantSummary
    observation: dict[str, Any]
    book: TradeWorkingCapitalBook


class TradeWorkingCapitalFailure(ResearchGateError):
    """The D1 wrapper refused the tick and restored every mutable state field."""

    def __init__(
        self,
        *,
        phase: str,
        cause: BaseException,
        failed_flows: MaterialTickFlows | None,
        failed_state: MaterialState | None,
        failed_book: TradeWorkingCapitalBook | None,
    ) -> None:
        super().__init__(f"{GATE_PREFIX}: {phase} failed: {cause}")
        self.phase = phase
        self.cause = cause
        self.failed_flows = failed_flows
        self.failed_state = failed_state
        self.failed_book = failed_book


def _restore_state(state: MaterialState, snapshot: MaterialState) -> None:
    for field_name in state.__dataclass_fields__:
        setattr(state, field_name, copy.deepcopy(getattr(snapshot, field_name)))


def _finite_non_negative(name: str, value: float) -> float:
    v = float(value)
    if not math.isfinite(v) or v < -_SERVICE_TOL:
        _reject(f"{name}={v!r} must be finite and non-negative")
    return max(v, 0.0)


def _validate_state(state: MaterialState, regime: TradeWorkingCapitalRegime) -> None:
    n_banks = int(np.asarray(state.bank_reserves).shape[0])
    if regime.bank_index >= n_banks:
        _reject(
            f"regime bank_index={regime.bank_index} outside the dense bank axis ({n_banks})"
        )
    if regime.bank_index != 0:
        # ``treasury_deposit`` is by contract the bank-0 fiscal deposit.  A
        # loan from another bank would require an explicit interbank deposit
        # transfer (reserve settlement), which this regime does not model.
        _reject(
            "D1 lends through dense bank 0 (the Treasury's deposit bank); "
            f"got bank_index={regime.bank_index}"
        )
    for name in (
        "treasury_deposit",
        "treasury_loan_principal",
        "treasury_interest_arrears",
        "treasury_loan_rate",
    ):
        _finite_non_negative(f"opening state {name}", getattr(state, name))
    maturity = float(state.treasury_loan_maturity_tick)
    if not math.isfinite(maturity) or maturity < -1.0 - _SERVICE_TOL:
        _reject(
            f"opening state treasury_loan_maturity_tick={maturity!r} must be -1 or a tick"
        )
    if float(state.treasury_loan_principal) > (
        float(regime.credit_limit) + _SERVICE_TOL
    ):
        _reject(
            f"opening principal {state.treasury_loan_principal!r} exceeds the "
            f"credit_limit {regime.credit_limit!r}"
        )
    for name in (
        "bank_reserves",
        "bank_loan_asset",
        "bank_deposit_liability",
        "bank_equity",
        "bank_interest_receivable",
    ):
        values = np.asarray(getattr(state, name), dtype=np.float64)
        if not np.all(np.isfinite(values)):
            _reject(f"opening state {name} contains non-finite values")
        if np.any(values < -_SERVICE_TOL):
            _reject(f"opening state {name} contains negative values")


def _close_enough(left: float, right: float) -> bool:
    return abs(float(left) - float(right)) <= tolerance_for(float(left), float(right))


def _validate_book(
    state: MaterialState,
    regime: TradeWorkingCapitalRegime,
    book: TradeWorkingCapitalBook | None,
    tick: int,
) -> TradeWorkingCapitalBook:
    principal = float(state.treasury_loan_principal)
    arrears = float(state.treasury_interest_arrears)
    maturity_state = float(state.treasury_loan_maturity_tick)
    rate_state = float(state.treasury_loan_rate)
    if principal > float(regime.credit_limit) + _SERVICE_TOL:
        _reject(
            f"opening principal {principal!r} exceeds the credit_limit "
            f"{regime.credit_limit!r}"
        )
    if book is None:
        if principal <= _SERVICE_TOL:
            if maturity_state != -1.0 or rate_state != 0.0:
                _reject("state has schedule scalars but no outstanding principal")
            return TradeWorkingCapitalBook(bank_index=regime.bank_index)
        draw_tick = int(round(maturity_state - int(regime.term_quarters)))
        if not _close_enough(draw_tick, maturity_state - int(regime.term_quarters)):
            _reject(
                "state maturity tick is inconsistent with the regime term; "
                "supply the original book"
            )
        if draw_tick < 0:
            _reject(
                "state maturity tick implies a negative draw tick; supply the original book"
            )
        book = TradeWorkingCapitalBook(
            bank_index=regime.bank_index,
            batches=(
                WorkingCapitalBatch(
                    draw_tick=draw_tick,
                    maturity_tick=int(round(maturity_state)),
                    principal=principal,
                    annual_rate=rate_state,
                ),
            ),
            interest_arrears=arrears,
        )
    if not isinstance(book, TradeWorkingCapitalBook):
        _reject("book must be a TradeWorkingCapitalBook")
    if book.bank_index != regime.bank_index:
        _reject(
            f"book bank_index={book.bank_index} differs from regime bank_index="
            f"{regime.bank_index}"
        )
    if len(book.batches) > 1:
        _reject("the D1 facility carries at most one outstanding batch")
    if not _close_enough(book.principal, principal):
        _reject(
            f"book principal {book.principal!r} disagrees with state "
            f"treasury_loan_principal {principal!r}"
        )
    if not _close_enough(book.interest_arrears, arrears):
        _reject(
            f"book interest_arrears {book.interest_arrears!r} disagrees with state "
            f"treasury_interest_arrears {arrears!r}"
        )
    if principal <= _SERVICE_TOL:
        if book.batches:
            _reject("book carries a batch with zero outstanding principal")
        if maturity_state != -1.0 or rate_state != 0.0:
            _reject("state schedule scalars disagree with a fully repaid book")
        return book
    batch = book.batches[0]
    if batch.draw_tick >= tick:
        _reject(
            f"batch draw_tick={batch.draw_tick} is not before the current tick {tick}"
        )
    if not (regime.draw_tick_start <= batch.draw_tick <= regime.draw_tick_end):
        _reject(
            f"batch draw_tick={batch.draw_tick} lies outside the regime draw window "
            f"[{regime.draw_tick_start}, {regime.draw_tick_end}]"
        )
    if batch.maturity_tick != batch.draw_tick + int(regime.term_quarters):
        _reject(
            "batch maturity does not equal draw_tick + regime.term_quarters"
        )
    if batch.maturity_tick != int(round(maturity_state)):
        _reject("batch maturity disagrees with state treasury_loan_maturity_tick")
    if not _close_enough(batch.annual_rate, rate_state):
        _reject("batch rate disagrees with state treasury_loan_rate")
    return book


def _append_journal(
    flows: MaterialTickFlows,
    *,
    kind: str,
    legs: list[tuple[int, int, str, float]],
) -> None:
    finance.append_transaction(
        flows,
        transaction_id=0,
        kind=kind,
        legs=legs,
        organization_id=None,
    )


def _service_book(
    state: MaterialState,
    book: TradeWorkingCapitalBook,
    parameters: MaterialParameters,
    tick: int,
) -> tuple[
    TradeWorkingCapitalBook,
    list[tuple[str, list[tuple[int, int, str, float]]]],
    dict[str, float],
]:
    """Accrue opening interest, pay what cash allows, then repay matured batches.

    Principal repayment is junior to interest and only uses cash that existed
    before this tick's draw.  Unpaid interest and matured principal stay with
    the same bank and batch; nothing is capitalized, forgiven or rolled over.
    """
    del parameters  # rate is per batch, contract-bound
    bank = book.bank_index
    cash = float(state.treasury_deposit) + 0.0
    interest_due = math.fsum(
        batch.principal * batch.annual_rate / 4.0 for batch in book.batches
    )
    arrears_open = book.interest_arrears
    interest_paid = min(cash, arrears_open + interest_due)
    cash -= interest_paid
    due_principal = math.fsum(
        batch.principal for batch in book.batches if batch.maturity_tick <= tick
    )
    principal_paid = min(cash, due_principal)

    events: list[tuple[str, list[tuple[int, int, str, float]]]] = []
    if interest_due > 0.0:
        state.bank_interest_receivable[bank] += interest_due
        state.bank_equity[bank] += interest_due
    if interest_paid > 0.0:
        state.treasury_deposit = float(state.treasury_deposit) - interest_paid
        state.bank_deposit_liability[bank] -= interest_paid
        state.bank_interest_receivable[bank] -= interest_paid
    state.treasury_interest_arrears = arrears_open + interest_due - interest_paid

    batches: list[WorkingCapitalBatch] = []
    remaining_pay = principal_paid
    for batch in book.batches:
        principal = batch.principal
        if batch.maturity_tick <= tick and remaining_pay > 0.0:
            paid = min(principal, remaining_pay)
            remaining_pay -= paid
            principal -= paid
        if principal > 0.0:
            batches.append(
                WorkingCapitalBatch(
                    draw_tick=batch.draw_tick,
                    maturity_tick=batch.maturity_tick,
                    principal=principal,
                    annual_rate=batch.annual_rate,
                )
            )
    if principal_paid > 0.0:
        state.treasury_deposit = float(state.treasury_deposit) - principal_paid
        state.bank_deposit_liability[bank] -= principal_paid
        state.bank_loan_asset[bank] -= principal_paid
        state.treasury_loan_principal = float(state.treasury_loan_principal) - principal_paid

    if interest_due > 0.0:
        events.append(
            (
                "treasury_working_capital_interest_accrual",
                [
                    (
                        int(bank_account_ids(state, AccountKind.INTEREST_RECEIVABLE)[bank]),
                        int(bank_account_ids(state, AccountKind.EQUITY)[bank]),
                        DOMESTIC_CURRENCY,
                        interest_due,
                    )
                ],
            )
        )
        events.append(
            (
                "treasury_working_capital_interest_accrual",
                [
                    (
                        int(treasury_term_account_id(state, AccountKind.INTEREST_EXPENSE)),
                        int(treasury_term_account_id(state, AccountKind.INTEREST_PAYABLE)),
                        DOMESTIC_CURRENCY,
                        interest_due,
                    )
                ],
            )
        )
    if interest_paid > 0.0:
        events.append(
            (
                "treasury_working_capital_interest_payment",
                [
                    (
                        int(treasury_term_account_id(state, AccountKind.INTEREST_PAYABLE)),
                        int(treasury_account_id(state, AccountKind.CASH_DEPOSIT)),
                        DOMESTIC_CURRENCY,
                        interest_paid,
                    )
                ],
            )
        )
        events.append(
            (
                "treasury_working_capital_interest_payment",
                [
                    (
                        int(bank_account_ids(state, AccountKind.DEPOSIT_LIABILITY)[bank]),
                        int(bank_account_ids(state, AccountKind.INTEREST_RECEIVABLE)[bank]),
                        DOMESTIC_CURRENCY,
                        interest_paid,
                    )
                ],
            )
        )
    if principal_paid > 0.0:
        events.append(
            (
                "treasury_working_capital_principal",
                [
                    (
                        int(treasury_term_account_id(state, AccountKind.LOAN_LIABILITY)),
                        int(treasury_account_id(state, AccountKind.CASH_DEPOSIT)),
                        DOMESTIC_CURRENCY,
                        principal_paid,
                    )
                ],
            )
        )
        events.append(
            (
                "treasury_working_capital_principal",
                [
                    (
                        int(bank_account_ids(state, AccountKind.DEPOSIT_LIABILITY)[bank]),
                        int(bank_account_ids(state, AccountKind.LOAN_ASSET)[bank]),
                        DOMESTIC_CURRENCY,
                        principal_paid,
                    )
                ],
            )
        )

    updated = TradeWorkingCapitalBook(
        bank_index=bank,
        batches=tuple(batches),
        interest_arrears=state.treasury_interest_arrears,
    )
    # Keep the checkpointed schedule scalars in lock-step with the book.
    if updated.batches:
        only = updated.batches[0]
        state.treasury_loan_maturity_tick = float(only.maturity_tick)
        state.treasury_loan_rate = float(only.annual_rate)
    else:
        state.treasury_loan_maturity_tick = -1.0
        state.treasury_loan_rate = 0.0
    return (
        updated,
        events,
        {
            "interest_due": interest_due,
            "interest_paid": interest_paid,
            "principal_due": due_principal,
            "principal_paid": principal_paid,
            "principal_unpaid": updated.principal,
            "interest_unpaid": updated.interest_arrears,
            "cash_after_service": float(state.treasury_deposit),
        },
    )


def _draw_journal(
    state: MaterialState, bank: int, amount: float
) -> list[tuple[str, list[tuple[int, int, str, float]]]]:
    return [
        (
            "treasury_working_capital_draw",
            [
                (
                    int(treasury_account_id(state, AccountKind.CASH_DEPOSIT)),
                    int(bank_account_ids(state, AccountKind.DEPOSIT_LIABILITY)[bank]),
                    DOMESTIC_CURRENCY,
                    amount,
                )
            ],
        ),
        (
            "treasury_working_capital_draw",
            [
                (
                    int(bank_account_ids(state, AccountKind.LOAN_ASSET)[bank]),
                    int(treasury_term_account_id(state, AccountKind.LOAN_LIABILITY)),
                    DOMESTIC_CURRENCY,
                    amount,
                )
            ],
        ),
    ]


def _probe_export_outlay(
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: MaterialParameters,
    network: MaterialNetwork,
    *,
    extra_cash: float,
    housing_payable: float,
) -> tuple[float, MaterialState]:
    """Run one real kernel tick on a discarded copy and return export outlay."""
    probe = copy.deepcopy(state)
    if extra_cash > 0.0:
        # The probe only measures the export demand envelope.  Keep its
        # internal deposit-coverage check satisfied; the result is discarded
        # and never reaches the admitted state or gate.
        probe.treasury_deposit = float(probe.treasury_deposit) + extra_cash
        probe.bank_deposit_liability[0] += extra_cash
        probe.bank_loan_asset[0] += extra_cash
    flows = tick_material(
        probe,
        forcing,
        parameters,
        network,
        treasury_housing_payable=housing_payable,
    )
    return float(flows.treasury_export_outlay), probe


def _identity_residuals(
    opening: Any,
    state: MaterialState,
    flows: MaterialTickFlows,
    bank: int,
) -> dict[str, float]:
    """Recompute the D1-side identities independently of the admission gate."""
    treasury_open = float(opening.treasury_deposit)
    treasury_close = float(state.treasury_deposit)
    # Treasury cash terms the gate reconstructs (imports/receipts/bailout/
    # housing/border are netted out by the ordinary gate; here we expose the
    # D1-specific part against the observed export outlay and service flows).
    d1_cash = (
        flows.treasury_loan_drawn
        - flows.treasury_principal_paid
        - flows.treasury_interest_paid
    )
    # The Treasury cash residual after removing D1 terms is the non-D1 net
    # outlay (exports/housing/imports/bailout).  It is not expected to be zero;
    # the admission gate owns the full continuity identity.
    return {
        "bank_sheet": float(
            state.bank_loan_asset[bank]
            + state.bank_interest_receivable[bank]
            + state.bank_reserves[bank]
            - state.bank_deposit_liability[bank]
            - state.bank_equity[bank]
        ),
        "treasury_loan_principal": float(
            state.treasury_loan_principal
            - opening.treasury_loan_principal
            - flows.treasury_loan_drawn
            + flows.treasury_principal_paid
        ),
        "treasury_interest_arrears": float(
            state.treasury_interest_arrears
            - opening.treasury_interest_arrears
            - flows.treasury_interest_due
            + flows.treasury_interest_paid
        ),
        "non_d1_treasury_net_outlay": float(treasury_open + d1_cash - treasury_close),
    }


def _build_observation(
    *,
    state: MaterialState,
    opening: Any,
    flows: MaterialTickFlows,
    regime: TradeWorkingCapitalRegime,
    book_before: TradeWorkingCapitalBook,
    book_after: TradeWorkingCapitalBook,
    service: dict[str, float],
    sizing: dict[str, float | None],
    draw: float,
) -> dict[str, Any]:
    bank = regime.bank_index
    d1_kinds = {
        "treasury_working_capital_draw",
        "treasury_working_capital_principal",
        "treasury_working_capital_interest_accrual",
        "treasury_working_capital_interest_payment",
    }
    journal_rows = []
    for index, kind in enumerate(flows.journal_kind):
        if kind not in d1_kinds:
            continue
        journal_rows.append(
            {
                "kind": kind,
                "tick": int(flows.journal_tick[index]),
                "debit": int(flows.journal_debit[index]),
                "credit": int(flows.journal_credit[index]),
                "currency": flows.journal_currency[index],
                "amount": float(flows.journal_amount[index]),
                "leg": int(flows.journal_leg[index]),
            }
        )
    return {
        "schema_version": SCHEMA_ID,
        "regime": regime.model_dump(mode="json"),
        "tick": int(flows.tick),
        "quarter": flows.quarter,
        "bank_index": bank,
        "credit_limit": float(regime.credit_limit),
        "limit_remaining": float(regime.credit_limit - book_after.principal),
        "treasury_cash_open": float(opening.treasury_deposit),
        "treasury_cash_after_service": float(service["cash_after_service"]),
        "treasury_cash_close": float(state.treasury_deposit),
        "loan_principal_open": float(book_before.principal),
        "loan_principal_close": float(state.treasury_loan_principal),
        "loan_maturity_tick": float(state.treasury_loan_maturity_tick),
        "loan_rate": float(state.treasury_loan_rate),
        "interest_arrears_open": float(book_before.interest_arrears),
        "interest_arrears_close": float(state.treasury_interest_arrears),
        "draw": float(draw),
        "draw_sizing": {
            key: (None if value is None else float(value)) for key, value in sizing.items()
        },
        "service": {key: float(value) for key, value in service.items()},
        "scheduled_batches": [
            {
                "draw_tick": batch.draw_tick,
                "maturity_tick": batch.maturity_tick,
                "principal": batch.principal,
                "annual_rate": batch.annual_rate,
            }
            for batch in book_after.batches
        ],
        "matured_this_tick": [
            {
                "draw_tick": batch.draw_tick,
                "maturity_tick": batch.maturity_tick,
                "principal": batch.principal,
            }
            for batch in book_before.batches
            if batch.maturity_tick <= flows.tick
        ],
        "export_outlay": float(flows.treasury_export_outlay),
        "identity_residuals": _identity_residuals(opening, state, flows, bank),
        "journal": journal_rows,
        "account_ids": {
            "treasury_cash": int(treasury_account_id(state, AccountKind.CASH_DEPOSIT)),
            "treasury_loan_liability": int(
                treasury_term_account_id(state, AccountKind.LOAN_LIABILITY)
            ),
            "treasury_interest_payable": int(
                treasury_term_account_id(state, AccountKind.INTEREST_PAYABLE)
            ),
            "bank_loan_asset": int(bank_account_ids(state, AccountKind.LOAN_ASSET)[bank]),
        },
    }


def execute_trade_working_capital_tick(
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: MaterialParameters,
    network: MaterialNetwork,
    *,
    regime: TradeWorkingCapitalRegime,
    book: TradeWorkingCapitalBook | None = None,
) -> TradeWorkingCapitalResult:
    """Run one real D1 tick and advance the clock only after a full pass."""
    if not isinstance(regime, TradeWorkingCapitalRegime):
        raise TradeWorkingCapitalFailure(
            phase="regime",
            cause=ResearchGateError(f"{GATE_PREFIX}: regime type is not D1"),
            failed_flows=None,
            failed_state=None,
            failed_book=book,
        )
    tick = int(state.completed_ticks)
    quarters = list(forcing.quarters)
    if not (0 <= tick < len(quarters)):
        raise TradeWorkingCapitalFailure(
            phase="forcing",
            cause=ResearchGateError(
                f"{GATE_PREFIX}: tick {tick} lies outside the forcing horizon "
                f"({len(quarters)} quarters)"
            ),
            failed_flows=None,
            failed_state=None,
            failed_book=book,
        )
    try:
        _validate_state(state, regime)
        if bool(getattr(parameters, "m2_neutral_credit", False)):
            _reject("D1 bank lending is incompatible with m2_neutral_credit=True")
        current_book = _validate_book(state, regime, book, tick)
    except ResearchGateError as exc:
        raise TradeWorkingCapitalFailure(
            phase="preflight",
            cause=exc,
            failed_flows=None,
            failed_state=None,
            failed_book=book,
        ) from exc

    before = copy.deepcopy(state)
    opening = capture_material_stocks(state)
    flows: MaterialTickFlows | None = None
    working_book = current_book
    phase = "service"
    try:
        working_book, service_events, service = _service_book(
            state, working_book, parameters, tick
        )
        cash_after_service = float(service["cash_after_service"])

        in_window = regime.draw_tick_start <= tick <= regime.draw_tick_end
        limit_remaining = float(regime.credit_limit - working_book.principal)
        if limit_remaining < 0.0 and limit_remaining > -_SERVICE_TOL:
            limit_remaining = 0.0
        if limit_remaining < -_SERVICE_TOL:
            _reject(
                f"outstanding principal {working_book.principal!r} exceeds the "
                f"credit_limit {regime.credit_limit!r}"
            )
        # A tick that has a batch due (matured or overdue) can never draw a
        # replacement facility: servicing happens before sizing, so allowing a
        # draw here would let new cash repay old debt (rollover).
        has_matured = any(
            batch.maturity_tick <= tick for batch in current_book.batches
        )
        single_facility_free = working_book.principal <= _SERVICE_TOL
        sizing: dict[str, float | None] = {
            "outlay_without_loan": None,
            "outlay_at_limit": None,
            "cash_after_service": cash_after_service,
            "limit_remaining": limit_remaining,
            "rollover_blocked": float(has_matured),
            "single_facility_free": float(single_facility_free),
        }
        draw = 0.0
        if (
            in_window
            and limit_remaining > _SERVICE_TOL
            and single_facility_free
            and not has_matured
        ):
            phase = "sizing"
            outlay_without_loan, _ = _probe_export_outlay(
                state,
                forcing,
                parameters,
                network,
                extra_cash=0.0,
                housing_payable=cash_after_service,
            )
            outlay_at_limit, _ = _probe_export_outlay(
                state,
                forcing,
                parameters,
                network,
                extra_cash=limit_remaining,
                housing_payable=cash_after_service,
            )
            sizing["outlay_without_loan"] = outlay_without_loan
            sizing["outlay_at_limit"] = outlay_at_limit
            incremental = outlay_at_limit - outlay_without_loan
            if incremental > _SERVICE_TOL:
                draw = min(limit_remaining, incremental)

        phase = "draw"
        draw_events: list[tuple[str, list[tuple[int, int, str, float]]]] = []
        if draw > _SERVICE_TOL:
            bank = regime.bank_index
            state.treasury_deposit = float(state.treasury_deposit) + draw
            state.treasury_loan_principal = float(state.treasury_loan_principal) + draw
            state.treasury_loan_maturity_tick = float(tick + int(regime.term_quarters))
            state.treasury_loan_rate = float(regime.annual_rate)
            state.bank_loan_asset[bank] += draw
            state.bank_deposit_liability[bank] += draw
            working_book = TradeWorkingCapitalBook(
                bank_index=working_book.bank_index,
                batches=tuple(working_book.batches)
                + (
                    WorkingCapitalBatch(
                        draw_tick=tick,
                        maturity_tick=tick + int(regime.term_quarters),
                        principal=draw,
                        annual_rate=float(regime.annual_rate),
                    ),
                ),
                interest_arrears=working_book.interest_arrears,
            )
            draw_events = _draw_journal(state, bank, draw)

        phase = "tick_material"
        flows = tick_material(
            state,
            forcing,
            parameters,
            network,
            treasury_housing_payable=cash_after_service,
        )
        flows.treasury_loan_drawn = float(draw)
        flows.treasury_principal_paid = float(service["principal_paid"])
        flows.treasury_interest_due = float(service["interest_due"])
        flows.treasury_interest_paid = float(service["interest_paid"])
        for kind, legs in service_events + draw_events:
            _append_journal(flows, kind=kind, legs=legs)

        phase = "sizing_verify"
        if draw > _SERVICE_TOL:
            outlay_without_loan = float(sizing["outlay_without_loan"] or 0.0)
            incremental_paid = float(flows.treasury_export_outlay) - outlay_without_loan
            if abs(incremental_paid - draw) > max(_SERVICE_TOL, 1e-12 * abs(draw)):
                _reject(
                    "loan draw was not fully absorbed by real export procurement: "
                    f"draw={draw!r} incremental_outlay={incremental_paid!r}"
                )
            if abs(float(state.treasury_loan_principal) - working_book.principal) > _SERVICE_TOL:
                _reject("state principal disagrees with the batch schedule after the tick")

        phase = "invariants"
        summary = accounting.check_material_invariants(
            opening, state, flows, parameters, network
        )
        phase = "observation"
        observation = _build_observation(
            state=state,
            opening=opening,
            flows=flows,
            regime=regime,
            book_before=current_book,
            book_after=working_book,
            service=service,
            sizing=sizing,
            draw=draw,
        )
        # Reuse the frozen D0 observer read-only for the unchanged legacy
        # trade part (receipts, Treasury goods payments, channel identities).
        observation["legacy_trade_observation"] = observe_legacy_trade_tick(
            opening,
            state,
            flows,
            parameters,
            network,
            regime=LegacyTradeRegime(
                schema_version="hist-trade-regime-v1",
                regime_id="legacy_treasury_prepay",
                source_kind="synthetic",
            ),
            oil_price=float(forcing.oil_price[tick]),
            cmea_contract_price=float(forcing.cmea_energy_price[tick]),
        )
    except Exception as exc:  # noqa: BLE001 - every failure must roll back
        failed_flows = copy.deepcopy(flows) if flows is not None else None
        failed_state = copy.deepcopy(state)
        _restore_state(state, before)
        raise TradeWorkingCapitalFailure(
            phase=phase,
            cause=exc,
            failed_flows=failed_flows,
            failed_state=failed_state,
            failed_book=working_book,
        ) from exc

    state.completed_ticks = tick + 1
    return TradeWorkingCapitalResult(
        flows=flows,
        gate=summary,
        observation=observation,
        book=working_book,
    )


__all__ = [
    "GATE_PREFIX",
    "REGIME_ID",
    "REGIME_SCHEMA_VERSION",
    "SCHEMA_ID",
    "TradeWorkingCapitalBook",
    "TradeWorkingCapitalFailure",
    "TradeWorkingCapitalRegime",
    "TradeWorkingCapitalResult",
    "WorkingCapitalBatch",
    "execute_trade_working_capital_tick",
    "load_trade_working_capital_regime",
]
