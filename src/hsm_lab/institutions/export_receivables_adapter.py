"""H3F-D2: export receivables, contract terms and bad-debt reversal entries.

The legacy Treasury-prepay path settles every delivered export for cash in the
delivery quarter.  This module adds one explicitly opt-in, synthetic regime in
which a real delivery opens a same-currency receivable against a declared
foreign buyer, under a contract term, and only an actual receipt/recovery
increases the foreign settlement balance.

Design boundaries (all default-off):

* Importing this module registers nothing; ``run_material`` never imports it.
* The real kernel books the delivery and every event atomically in
  :func:`hsm_lab.engine.trade.settle_exports_on_receivables`.
* The accounting gate independently replays the opening book plus the flow
  event log, and cross-checks every journal leg, so a flow-only or
  state-only edit cannot pass.
* The book and event log live in ``MaterialState`` and are checkpointed.
* On any failure every ``MaterialState`` field is restored, the clock is not
  advanced, and a :class:`ExportReceivableFailure` carries the failed
  state/flows.
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from hsm_lab.contract.base import ResearchGateError, StrictModel
from hsm_lab.contract.material import MaterialParameters
from hsm_lab.engine import accounting
from hsm_lab.engine.accounting import InvariantSummary
from hsm_lab.engine.finance import (
    CMEA_CURRENCY,
    USD_CURRENCY,
    AccountKind,
    foreign_account_id,
    treasury_receivable_account_id,
)
from hsm_lab.engine.material import _tick_material_impl
from hsm_lab.engine.network import MaterialNetwork
from hsm_lab.engine.state import (
    ExportContract,
    ExportReceivable,
    ExportReceivableEvent,
    ExportReceivablePolicy,
    MaterialForcing,
    MaterialState,
    MaterialTickFlows,
    capture_material_stocks,
)
from hsm_lab.engine.trade import (
    apply_receivable_events,
    validate_export_policy,
    validate_receivable_book,
)

REGIME_SCHEMA_VERSION = "hist-export-receivables-regime-v1"
REGIME_ID = "export_receivables"
SCHEMA_ID = "hist-export-receivables-observation-v1"
GATE_PREFIX = "HIST_H3F_D2"

_TOL = 1e-9
_RECEIVABLE_JOURNAL_KINDS = frozenset(
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

StrictFiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
StrictNonNegativeInt = Annotated[int, Field(strict=True, ge=0)]


def _reject(message: str) -> None:
    raise ResearchGateError(f"{GATE_PREFIX}: {message}")


class ExportReceivableContract(StrictModel):
    """One declared synthetic contract; the buyer is never a settlement account."""

    contract_id: Annotated[str, Field(min_length=1)]
    currency: Literal["USD", "cmea_settlement_unit"]
    buyer_id: StrictNonNegativeInt
    seller_id: StrictNonNegativeInt
    commodity_id: Annotated[str, Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def _treasury_is_the_only_seller(self) -> ExportReceivableContract:
        if self.seller_id != 0:
            raise ValueError("the synthetic export seller is Treasury id 0")
        return self


class ExportReceivablesRegime(StrictModel):
    """Frozen synthetic D2 regime: term plus explicit contract identities."""

    schema_version: Literal["hist-export-receivables-regime-v1"]
    regime_id: Literal["export_receivables"]
    source_kind: Literal["synthetic"]
    term_quarters: Annotated[int, Field(strict=True, ge=1)]
    contracts: Annotated[tuple[ExportReceivableContract, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _unique_contracts(self) -> ExportReceivablesRegime:
        ids = [contract.contract_id for contract in self.contracts]
        if len(ids) != len(set(ids)):
            raise ValueError("contract_id values must be unique")
        keys = [
            (contract.currency, contract.commodity_id)
            for contract in self.contracts
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("contracts must not repeat a (currency, commodity) key")
        for currency in ("USD", "cmea_settlement_unit"):
            matching = [contract for contract in self.contracts if contract.currency == currency]
            if not matching:
                continue
            wildcards = [contract for contract in matching if contract.commodity_id is None]
            if len(wildcards) > 1:
                raise ValueError(f"{currency} carries more than one wildcard contract")
        return self


class ExportReceivableEventSpec(StrictModel):
    """Caller-declared receipt/loss/write-off/recovery for the current tick."""

    event_id: Annotated[str, Field(min_length=1)]
    tick: StrictNonNegativeInt
    kind: Literal["receipt", "loss", "writeoff", "recovery"]
    receivable_id: Annotated[str, Field(min_length=1)]
    contract_id: Annotated[str, Field(min_length=1)]
    currency: Literal["USD", "cmea_settlement_unit"]
    buyer_id: StrictNonNegativeInt
    seller_id: StrictNonNegativeInt
    amount: Annotated[StrictFiniteFloat, Field(gt=0.0)]

    @model_validator(mode="after")
    def _treasury_is_the_only_seller(self) -> ExportReceivableEventSpec:
        if self.seller_id != 0:
            raise ValueError("the synthetic export seller is Treasury id 0")
        return self


def load_export_receivables_regime(path: str | Path) -> ExportReceivablesRegime:
    """Load exactly one D2 regime file; reject every other shape or literal."""
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
        "term_quarters",
        "contracts",
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
        return ExportReceivablesRegime.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - any validation rejection is a gate violation
        _reject(f"regime file {file_path} failed validation: {exc}")


@dataclass(frozen=True)
class ExportReceivableResult:
    """One admitted D2 tick; the book is already stored in ``state``."""

    flows: MaterialTickFlows
    gate: InvariantSummary
    observation: dict[str, Any]


class ExportReceivableFailure(ResearchGateError):
    """The D2 wrapper refused the tick and restored every mutable state field."""

    def __init__(
        self,
        *,
        phase: str,
        cause: BaseException,
        failed_flows: MaterialTickFlows | None,
        failed_state: MaterialState | None,
    ) -> None:
        super().__init__(f"{GATE_PREFIX}: {phase} failed: {cause}")
        self.phase = phase
        self.cause = cause
        self.failed_flows = failed_flows
        self.failed_state = failed_state


def _restore_state(state: MaterialState, snapshot: MaterialState) -> None:
    for field_name in state.__dataclass_fields__:
        setattr(state, field_name, copy.deepcopy(getattr(snapshot, field_name)))


def _validate_state(state: MaterialState, network: MaterialNetwork) -> None:
    if state.treasury_loan_principal > _TOL or state.treasury_interest_arrears > _TOL:
        _reject("D2 positive ticks require the D1 term loan to be switched off")
    try:
        validate_receivable_book(
            tuple(state.export_receivables),
            tuple(state.export_receivable_event_ids),
            completed_ticks=int(state.completed_ticks),
            commodity_ids=tuple(network.commodity_ids),
        )
    except ValueError as exc:
        _reject(f"opening receivable book is invalid: {exc}")


def _event_from_spec(
    spec: ExportReceivableEventSpec,
    lots: dict[str, ExportReceivable],
) -> ExportReceivableEvent:
    lot = lots.get(spec.receivable_id)
    if lot is None:
        _reject(f"event {spec.event_id!r} targets unknown receivable {spec.receivable_id!r}")
    mismatched = [
        name
        for name, left, right in (
            ("contract_id", lot.contract_id, spec.contract_id),
            ("currency", lot.currency, spec.currency),
            ("buyer_id", lot.buyer_id, spec.buyer_id),
            ("seller_id", lot.seller_id, spec.seller_id),
        )
        if left != right
    ]
    if mismatched:
        _reject(f"event {spec.event_id!r} identity mismatch on {mismatched}")
    return ExportReceivableEvent(
        event_id=spec.event_id,
        tick=spec.tick,
        kind=spec.kind,
        receivable_id=spec.receivable_id,
        contract_id=lot.contract_id,
        currency=lot.currency,
        buyer_id=lot.buyer_id,
        seller_id=lot.seller_id,
        commodity_id=lot.commodity_id,
        delivery_tick=lot.delivery_tick,
        due_tick=lot.due_tick,
        amount=float(spec.amount),
    )


def _build_policy(
    state: MaterialState,
    regime: ExportReceivablesRegime,
    specs: tuple[ExportReceivableEventSpec, ...],
) -> ExportReceivablePolicy:
    lots = {lot.receivable_id: lot for lot in state.export_receivables}
    if len(lots) != len(state.export_receivables):
        _reject("opening book carries duplicate receivable ids")
    seen = set(state.export_receivable_event_ids)
    if len(seen) != len(state.export_receivable_event_ids):
        _reject("opening event log carries duplicate event ids")
    events: list[ExportReceivableEvent] = []
    for spec in specs:
        if spec.tick != int(state.completed_ticks):
            _reject(
                f"event {spec.event_id!r} carries tick {spec.tick}, "
                f"expected {state.completed_ticks}"
            )
        if spec.event_id in seen:
            _reject(f"duplicate event id {spec.event_id!r}")
        seen.add(spec.event_id)
        events.append(_event_from_spec(spec, lots))
    contracts = tuple(
        ExportContract(
            contract_id=contract.contract_id,
            currency=contract.currency,
            buyer_id=int(contract.buyer_id),
            seller_id=int(contract.seller_id),
            commodity_id=contract.commodity_id,
        )
        for contract in regime.contracts
    )
    policy = ExportReceivablePolicy(
        term_quarters=int(regime.term_quarters),
        contracts=contracts,
        events=tuple(events),
    )
    try:
        validate_export_policy(policy)
        apply_receivable_events(
            tuple(state.export_receivables),
            tuple(state.export_receivable_event_ids),
            policy.events,
            current_tick=int(state.completed_ticks),
        )
    except ValueError as exc:
        _reject(f"event preflight failed: {exc}")
    return policy


def _identity_residuals(
    state: MaterialState, opening: Any, flows: MaterialTickFlows
) -> dict[str, float]:
    lot_closure = 0.0
    provision_closure = 0.0
    for lot in state.export_receivables:
        lot_closure = max(
            lot_closure,
            abs(lot.gross + lot.received + lot.written_off - lot.principal),
        )
        provision_closure = max(
            provision_closure,
            abs(lot.provision_expense - lot.writeoffs - lot.provision_released - lot.provision),
        )
    usd_expected = (
        float(opening.usd_reserve)
        + float(flows.usd_export_receipt)
        - float(flows.usd_interest_paid)
        - float(flows.usd_principal_paid)
        - float(flows.usd_import_payment)
        + float(flows.usd_loan_drawn)
    )
    cmea_expected = (
        float(opening.cmea_settlement_balance)
        + float(flows.cmea_export_receipt)
        - float(flows.cmea_import_payment)
    )
    cash_closure = max(
        abs(float(state.usd_reserve) - usd_expected),
        abs(float(state.cmea_settlement_balance) - cmea_expected),
    )
    return {
        "principal_closure": float(lot_closure),
        "provision_closure": float(provision_closure),
        "cash_closure": float(cash_closure),
    }


def _build_observation(
    *,
    state: MaterialState,
    opening: Any,
    flows: MaterialTickFlows,
    regime: ExportReceivablesRegime,
) -> dict[str, Any]:
    lots = state.export_receivables
    journal_rows = [
        {
            "kind": flows.journal_kind[index],
            "tick": int(flows.journal_tick[index]),
            "debit": int(flows.journal_debit[index]),
            "credit": int(flows.journal_credit[index]),
            "currency": flows.journal_currency[index],
            "amount": float(flows.journal_amount[index]),
            "leg": int(flows.journal_leg[index]),
            "event_id": flows.journal_event[index],
        }
        for index, kind in enumerate(flows.journal_kind)
        if kind in _RECEIVABLE_JOURNAL_KINDS
    ]
    return {
        "schema_version": SCHEMA_ID,
        "source_kind": "synthetic",
        "historical": "UNIDENTIFIED",
        "regime": regime.model_dump(mode="json"),
        "tick": int(flows.tick),
        "quarter": flows.quarter,
        "receivable_open": [asdict(lot) for lot in opening.export_receivables],
        "receivable_close": [asdict(lot) for lot in lots],
        "event_log_open": list(opening.export_receivable_event_ids),
        "event_log_close": list(state.export_receivable_event_ids),
        "events": [asdict(event) for event in flows.export_receivable_events],
        "due": [
            {
                "receivable_id": lot.receivable_id,
                "currency": lot.currency,
                "outstanding": float(lot.gross),
            }
            for lot in lots
            if lot.due_tick == int(flows.tick) and lot.gross > 0.0
        ],
        "overdue": [
            {
                "receivable_id": lot.receivable_id,
                "currency": lot.currency,
                "outstanding": float(lot.gross),
                "age": int(flows.tick - lot.due_tick),
            }
            for lot in lots
            if lot.due_tick < int(flows.tick) and lot.gross > 0.0
        ],
        "flow_scalars": {
            suffix.upper(): {
                name: float(getattr(flows, f"export_receivable_{name}_{suffix}"))
                for name in (
                    "opened",
                    "received",
                    "recovered",
                    "written_off",
                    "loss_provision",
                    "provision_released",
                    "balance",
                    "overdue",
                )
            }
            for suffix in ("usd", "cmea")
        },
        "cash": {
            "usd_open": float(opening.usd_reserve),
            "usd_receipt": float(flows.usd_export_receipt),
            "usd_close": float(state.usd_reserve),
            "cmea_open": float(opening.cmea_settlement_balance),
            "cmea_receipt": float(flows.cmea_export_receipt),
            "cmea_close": float(state.cmea_settlement_balance),
        },
        "identity_residuals": _identity_residuals(state, opening, flows),
        "journal": journal_rows,
        "account_ids": {
            currency: {
                kind: int(treasury_receivable_account_id(state, currency, kind))
                for kind in (
                    AccountKind.EXPORT_RECEIVABLE,
                    AccountKind.BAD_DEBT_ALLOWANCE,
                    AccountKind.BAD_DEBT_EXPENSE,
                    AccountKind.EXPORT_SALES_INCOME,
                )
            }
            | {"trade_settlement": int(foreign_account_id(state, currency))}
            for currency in (USD_CURRENCY, CMEA_CURRENCY)
        },
    }


def execute_export_receivables_tick(
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: MaterialParameters,
    network: MaterialNetwork,
    *,
    regime: ExportReceivablesRegime,
    events: tuple[ExportReceivableEventSpec, ...] = (),
) -> ExportReceivableResult:
    """Run one real D2 tick and advance the clock only after a full pass."""
    if not isinstance(regime, ExportReceivablesRegime):
        raise ExportReceivableFailure(
            phase="regime",
            cause=ResearchGateError(f"{GATE_PREFIX}: regime type is not D2"),
            failed_flows=None,
            failed_state=None,
        )
    raw_tick = state.completed_ticks
    if isinstance(raw_tick, bool) or not isinstance(raw_tick, int):
        raise ExportReceivableFailure(
            phase="preflight",
            cause=ResearchGateError(
                f"{GATE_PREFIX}: state.completed_ticks must be a strict integer"
            ),
            failed_flows=None,
            failed_state=None,
        )
    tick = int(raw_tick)
    quarters = list(forcing.quarters)
    if not (0 <= tick < len(quarters)):
        raise ExportReceivableFailure(
            phase="forcing",
            cause=ResearchGateError(
                f"{GATE_PREFIX}: tick {tick} lies outside the forcing horizon "
                f"({len(quarters)} quarters)"
            ),
            failed_flows=None,
            failed_state=None,
        )
    try:
        _validate_state(state, network)
        policy = _build_policy(state, regime, events)
    except ResearchGateError as exc:
        raise ExportReceivableFailure(
            phase="preflight",
            cause=exc,
            failed_flows=None,
            failed_state=None,
        ) from exc

    before = copy.deepcopy(state)
    opening = capture_material_stocks(state)
    flows: MaterialTickFlows | None = None
    phase = "tick_material"
    try:
        flows = _tick_material_impl(
            state,
            forcing,
            parameters,
            network,
            export_receivable_policy=policy,
        )
        phase = "invariants"
        summary = accounting.check_material_invariants(
            opening,
            state,
            flows,
            parameters,
            network,
            forcing=forcing,
            export_receivable_policy=policy,
        )
        phase = "observation"
        observation = _build_observation(
            state=state,
            opening=opening,
            flows=flows,
            regime=regime,
        )
    except Exception as exc:  # noqa: BLE001 - every failure must roll back
        failed_flows = copy.deepcopy(flows) if flows is not None else None
        failed_state = copy.deepcopy(state)
        _restore_state(state, before)
        raise ExportReceivableFailure(
            phase=phase,
            cause=exc,
            failed_flows=failed_flows,
            failed_state=failed_state,
        ) from exc

    state.completed_ticks = tick + 1
    return ExportReceivableResult(flows=flows, gate=summary, observation=observation)


__all__ = [
    "GATE_PREFIX",
    "REGIME_ID",
    "REGIME_SCHEMA_VERSION",
    "SCHEMA_ID",
    "ExportReceivableContract",
    "ExportReceivableEventSpec",
    "ExportReceivableFailure",
    "ExportReceivableResult",
    "ExportReceivablesRegime",
    "execute_export_receivables_tick",
    "load_export_receivables_regime",
]
