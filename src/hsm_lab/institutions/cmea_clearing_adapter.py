"""H3F-D3: independent synthetic CMEA clearing with bilateral quotas.

The legacy trade path keeps one CMEA memo-credit scalar and one bridge
account.  This module adds one explicitly opt-in, synthetic regime in which
every counterparty has its own signed clearing position, cumulative credit
limit, frozen contract prices and a due/overdue entry trail.  USD and domestic
books stay separate; no cross-currency netting is possible.

Design boundaries (all default-off):

* Importing this module registers nothing; ``run_material`` never imports it.
* Real imports consume ``balance + credit_limit`` for one declared
  counterparty; a per-call envelope cannot be re-used.
* A real export delivery opens a pending claim.  Only an explicit settlement
  event at or after its due tick moves it into the clearing position and
  releases quota.
* Transfers of confirmed claims require the declared clearing group and keep
  every event id; there is no implicit multilateral netting.
* The book, transfer log and event ids live in ``MaterialState`` and are
  checkpointed in ``clearing.json``.
* On any failure every ``MaterialState`` field is restored, the clock is not
  advanced, and a :class:`CmeaClearingFailure` carries the failed state/flows.
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
    AccountKind,
    cmea_clearing_position_account_id,
    cmea_clearing_shared_account_id,
)
from hsm_lab.engine.material import _tick_material_impl
from hsm_lab.engine.network import MaterialNetwork
from hsm_lab.engine.state import (
    CmeaClearingContract,
    CmeaClearingCounterparty,
    CmeaClearingEvent,
    CmeaClearingPolicy,
    MaterialForcing,
    MaterialState,
    MaterialTickFlows,
    capture_material_stocks,
)
from hsm_lab.engine.trade import (
    apply_clearing_events,
    clearing_overdue,
    validate_clearing_book,
    validate_clearing_policy,
)

REGIME_SCHEMA_VERSION = "hist-cmea-clearing-regime-v1"
REGIME_ID = "cmea_clearing"
SCHEMA_ID = "hist-cmea-clearing-observation-v1"
GATE_PREFIX = "HIST_H3F_D3"

_TOL = 1e-9
_CLEARING_JOURNAL_KINDS = frozenset(
    {
        "cmea_clearing_import",
        "cmea_clearing_export",
        "cmea_clearing_settle",
        "cmea_clearing_transfer",
    }
)

StrictFiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
StrictNonNegativeInt = Annotated[int, Field(strict=True, ge=0)]


def _reject(message: str) -> None:
    raise ResearchGateError(f"{GATE_PREFIX}: {message}")


class CmeaCounterpartySpec(StrictModel):
    """One declared synthetic counterparty and its cumulative credit limit."""

    counterparty_id: StrictNonNegativeInt
    credit_limit: Annotated[StrictFiniteFloat, Field(ge=0.0)]


class CmeaContractSpec(StrictModel):
    """One frozen bilateral contract at an explicit synthetic price."""

    contract_id: Annotated[str, Field(min_length=1)]
    counterparty_id: StrictNonNegativeInt
    direction: Literal["import", "export"]
    commodity_id: Annotated[str, Field(min_length=1)]
    price: Annotated[StrictFiniteFloat, Field(gt=0.0)]


class CmeaClearingRegime(StrictModel):
    """Frozen synthetic D3 regime: term, counterparties and contracts."""

    schema_version: Literal["hist-cmea-clearing-regime-v1"]
    regime_id: Literal["cmea_clearing"]
    source_kind: Literal["synthetic"]
    term_quarters: Annotated[int, Field(strict=True, ge=1)]
    clearing_group: tuple[StrictNonNegativeInt, ...] = ()
    counterparties: Annotated[tuple[CmeaCounterpartySpec, ...], Field(min_length=1)]
    contracts: tuple[CmeaContractSpec, ...] = ()

    @model_validator(mode="after")
    def _unique_identities(self) -> CmeaClearingRegime:
        ids = [item.counterparty_id for item in self.counterparties]
        if len(ids) != len(set(ids)):
            raise ValueError("counterparty_id values must be unique")
        declared = set(ids)
        contract_ids = [contract.contract_id for contract in self.contracts]
        if len(contract_ids) != len(set(contract_ids)):
            raise ValueError("contract_id values must be unique")
        keys = [(contract.direction, contract.commodity_id) for contract in self.contracts]
        if len(keys) != len(set(keys)):
            raise ValueError("contracts must not repeat a (direction, commodity) key")
        for contract in self.contracts:
            if contract.counterparty_id not in declared:
                raise ValueError(
                    f"contract {contract.contract_id!r} names an undeclared counterparty"
                )
        group = list(self.clearing_group)
        if len(group) != len(set(group)):
            raise ValueError("clearing_group values must be unique")
        extra = set(group) - declared
        if extra:
            raise ValueError(f"clearing group names undeclared counterparties: {sorted(extra)}")
        return self


class CmeaClearingEventSpec(StrictModel):
    """Caller-declared settlement or authorised transfer for the current tick."""

    event_id: Annotated[str, Field(min_length=1)]
    tick: StrictNonNegativeInt
    kind: Literal["settle_export", "transfer"]
    entry_id: Annotated[str, Field(min_length=1)] | None = None
    source_counterparty_id: StrictNonNegativeInt | None = None
    target_counterparty_id: StrictNonNegativeInt | None = None
    amount: Annotated[StrictFiniteFloat, Field(gt=0.0)]

    @model_validator(mode="after")
    def _kind_shape(self) -> CmeaClearingEventSpec:
        if self.event_id.startswith(("import:", "export:")):
            raise ValueError("event ids may not use the generated entry namespace")
        if self.kind == "settle_export":
            if self.entry_id is None:
                raise ValueError("settle_export requires entry_id")
            if (
                self.source_counterparty_id is not None
                or self.target_counterparty_id is not None
            ):
                raise ValueError("settle_export carries no transfer counterparties")
        else:
            if self.entry_id is not None:
                raise ValueError("transfer carries no entry_id")
            if (
                self.source_counterparty_id is None
                or self.target_counterparty_id is None
            ):
                raise ValueError("transfer requires source and target counterparties")
            if self.source_counterparty_id == self.target_counterparty_id:
                raise ValueError("transfer source and target must differ")
        return self


def load_cmea_clearing_regime(path: str | Path) -> CmeaClearingRegime:
    """Load exactly one D3 regime file; reject every other shape or literal."""
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
        "clearing_group",
        "counterparties",
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
        return CmeaClearingRegime.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - any validation rejection is a gate violation
        _reject(f"regime file {file_path} failed validation: {exc}")


@dataclass(frozen=True)
class CmeaClearingResult:
    """One admitted D3 tick; the book is already stored in ``state``."""

    flows: MaterialTickFlows
    gate: InvariantSummary
    observation: dict[str, Any]


class CmeaClearingFailure(ResearchGateError):
    """The D3 wrapper refused the tick and restored every mutable state field."""

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
    if state.export_receivables or state.export_receivable_event_ids:
        _reject("D3 positive ticks require the D2 receivable book to be empty")
    if abs(float(state.cmea_settlement_balance)) > _TOL:
        _reject("D3 positive ticks require the legacy memo-credit scalar to be zero")
    clearing_present = bool(
        state.cmea_clearing_accounts
        or state.cmea_clearing_entries
        or state.cmea_clearing_transfers
        or state.cmea_clearing_event_ids
        or state.cmea_clearing_settlements
    )
    if clearing_present and state.cmea_clearing_regime is None:
        _reject("open clearing books lack their persisted regime")
    if (
        state.treasury_loan_principal > _TOL
        or state.treasury_interest_arrears > _TOL
        or state.treasury_loan_maturity_tick >= 0.0
    ):
        _reject("D3 positive ticks require the D1 term loan to be switched off")
    try:
        validate_clearing_book(
            tuple(state.cmea_clearing_accounts),
            tuple(state.cmea_clearing_entries),
            tuple(state.cmea_clearing_transfers),
            tuple(state.cmea_clearing_event_ids),
            settlements=tuple(state.cmea_clearing_settlements),
            completed_ticks=int(state.completed_ticks),
            commodity_ids=tuple(network.commodity_ids),
            policy=state.cmea_clearing_regime,
        )
    except ValueError as exc:
        _reject(f"opening clearing book is invalid: {exc}")


def _build_policy(
    state: MaterialState,
    regime: CmeaClearingRegime,
    specs: tuple[CmeaClearingEventSpec, ...],
) -> CmeaClearingPolicy:
    counterparties = tuple(
        CmeaClearingCounterparty(
            counterparty_id=int(item.counterparty_id),
            credit_limit=float(item.credit_limit),
        )
        for item in regime.counterparties
    )
    contracts = tuple(
        CmeaClearingContract(
            contract_id=item.contract_id,
            counterparty_id=int(item.counterparty_id),
            direction=item.direction,
            commodity_id=item.commodity_id,
            price=float(item.price),
        )
        for item in regime.contracts
    )
    seen = set(state.cmea_clearing_event_ids)
    if len(seen) != len(state.cmea_clearing_event_ids):
        _reject("opening event log carries duplicate event ids")
    events: list[CmeaClearingEvent] = []
    for spec in specs:
        if int(spec.tick) != int(state.completed_ticks):
            _reject(
                f"event {spec.event_id!r} carries tick {spec.tick}, "
                f"expected {state.completed_ticks}"
            )
        if spec.event_id in seen:
            _reject(f"duplicate event id {spec.event_id!r}")
        seen.add(spec.event_id)
        events.append(
            CmeaClearingEvent(
                event_id=spec.event_id,
                tick=int(spec.tick),
                kind=spec.kind,
                entry_id=spec.entry_id,
                source_counterparty_id=(
                    int(spec.source_counterparty_id)
                    if spec.source_counterparty_id is not None
                    else None
                ),
                target_counterparty_id=(
                    int(spec.target_counterparty_id)
                    if spec.target_counterparty_id is not None
                    else None
                ),
                amount=float(spec.amount),
            )
        )
    policy = CmeaClearingPolicy(
        term_quarters=int(regime.term_quarters),
        counterparties=counterparties,
        contracts=contracts,
        events=tuple(events),
        clearing_group=tuple(int(cid) for cid in regime.clearing_group),
    )
    try:
        validate_clearing_policy(policy)
        apply_clearing_events(
            tuple(state.cmea_clearing_accounts),
            tuple(state.cmea_clearing_entries),
            tuple(state.cmea_clearing_transfers),
            tuple(state.cmea_clearing_settlements),
            tuple(state.cmea_clearing_event_ids),
            policy.events,
            current_tick=int(state.completed_ticks),
            policy=policy,
        )
    except ValueError as exc:
        _reject(f"event preflight failed: {exc}")
    return policy


def _build_observation(
    *,
    state: MaterialState,
    opening: Any,
    flows: MaterialTickFlows,
    regime: CmeaClearingRegime,
) -> dict[str, Any]:
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
        if kind in _CLEARING_JOURNAL_KINDS
    ]
    positions = {
        int(account.counterparty_id): float(account.balance)
        for account in state.cmea_clearing_accounts
    }
    overdue = clearing_overdue(
        tuple(state.cmea_clearing_entries), int(flows.tick)
    )
    return {
        "schema_version": SCHEMA_ID,
        "source_kind": "synthetic",
        "historical": "UNIDENTIFIED",
        "regime": regime.model_dump(mode="json"),
        "tick": int(flows.tick),
        "quarter": flows.quarter,
        "account_open": [asdict(item) for item in opening.cmea_clearing_accounts],
        "account_close": [asdict(item) for item in state.cmea_clearing_accounts],
        "entry_open": [asdict(item) for item in opening.cmea_clearing_entries],
        "entry_close": [asdict(item) for item in state.cmea_clearing_entries],
        "transfer_open": [asdict(item) for item in opening.cmea_clearing_transfers],
        "transfer_close": [asdict(item) for item in state.cmea_clearing_transfers],
        "event_log_open": list(opening.cmea_clearing_event_ids),
        "event_log_close": list(state.cmea_clearing_event_ids),
        "events": [asdict(event) for event in flows.cmea_clearing_events],
        "positions": positions,
        "due": [
            {
                "entry_id": entry.entry_id,
                "counterparty_id": int(entry.counterparty_id),
                "outstanding": float(entry.amount) - float(entry.settled),
            }
            for entry in state.cmea_clearing_entries
            if entry.direction == "import" and entry.due_tick == int(flows.tick)
        ],
        "overdue": [
            {
                "counterparty_id": cid,
                "outstanding": float(amount),
            }
            for cid, amount in sorted(overdue.items())
        ],
        "flow_scalars": {
            "import_payment": float(flows.cmea_clearing_import_payment),
            "export_pending": float(flows.cmea_clearing_export_pending),
            "export_settled": float(flows.cmea_clearing_export_settled),
        },
        "cash": {
            "usd_open": float(opening.usd_reserve),
            "usd_receipt": float(flows.usd_export_receipt),
            "usd_close": float(state.usd_reserve),
            "cmea_open": float(opening.cmea_settlement_balance),
            "cmea_close": float(state.cmea_settlement_balance),
        },
        "journal": journal_rows,
        "account_ids": {
            "shared": {
                kind: int(cmea_clearing_shared_account_id(state, kind))
                for kind in (
                    AccountKind.CMEA_CLEARING_PENDING,
                    AccountKind.CMEA_CLEARING_INCOME,
                    AccountKind.CMEA_CLEARING_EXPENSE,
                )
            },
            "positions": {
                int(account.counterparty_id): int(
                    cmea_clearing_position_account_id(
                        state, int(account.counterparty_id)
                    )
                )
                for account in state.cmea_clearing_accounts
            },
        },
    }


def execute_cmea_clearing_tick(
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: MaterialParameters,
    network: MaterialNetwork,
    *,
    regime: CmeaClearingRegime,
    events: tuple[CmeaClearingEventSpec, ...] = (),
) -> CmeaClearingResult:
    """Run one real D3 tick and advance the clock only after a full pass."""
    if not isinstance(regime, CmeaClearingRegime):
        raise CmeaClearingFailure(
            phase="regime",
            cause=ResearchGateError(f"{GATE_PREFIX}: regime type is not D3"),
            failed_flows=None,
            failed_state=None,
        )
    raw_tick = state.completed_ticks
    if isinstance(raw_tick, bool) or not isinstance(raw_tick, int):
        raise CmeaClearingFailure(
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
        raise CmeaClearingFailure(
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
        raise CmeaClearingFailure(
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
            cmea_clearing_policy=policy,
        )
        phase = "invariants"
        summary = accounting.check_material_invariants(
            opening,
            state,
            flows,
            parameters,
            network,
            forcing=forcing,
            cmea_clearing_policy=policy,
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
        raise CmeaClearingFailure(
            phase=phase,
            cause=exc,
            failed_flows=failed_flows,
            failed_state=failed_state,
        ) from exc

    state.completed_ticks = tick + 1
    return CmeaClearingResult(flows=flows, gate=summary, observation=observation)


__all__ = [
    "GATE_PREFIX",
    "REGIME_ID",
    "REGIME_SCHEMA_VERSION",
    "SCHEMA_ID",
    "CmeaClearingEventSpec",
    "CmeaClearingFailure",
    "CmeaClearingRegime",
    "CmeaClearingResult",
    "CmeaContractSpec",
    "CmeaCounterpartySpec",
    "execute_cmea_clearing_tick",
    "load_cmea_clearing_regime",
]
