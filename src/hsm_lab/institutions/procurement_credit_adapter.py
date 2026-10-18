"""H3B: synthetic domestic procurement-credit approval and settlement closure.

The adapter is the only H3B entry point.  It validates a frozen quarterly
policy, builds dense per-borrower approval caps, runs exactly one real
``tick_material`` with the opt-in cap/trace interface, applies the existing
material/financial invariant gate, then applies the read-only procurement
credit funnel.  ``completed_ticks`` advances only after every gate passes.

The policy is a *synthetic institution* (``source_kind="synthetic"``), not a
historical bank contract.  Enterprises not listed in ``limits`` have a zero
limit; the default is exported explicitly rather than silently inheriting an
unlimited line.  The adapter never creates a bank, account, clock, stock or
ledger of its own.
"""

from __future__ import annotations

import calendar
import copy
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.contract.schemas import Quarter
from hsm_lab.engine import accounting, finance
from hsm_lab.engine.accounting import InvariantSummary
from hsm_lab.engine.material import tick_material
from hsm_lab.engine.network import MaterialNetwork
from hsm_lab.engine.state import (
    MaterialForcing,
    MaterialState,
    MaterialStockSnapshot,
    MaterialTickFlows,
    capture_material_stocks,
)
from hsm_lab.measurement import flow_funnel
from hsm_lab.measurement.flow_funnel import ProcurementCreditFunnel

POLICY_SCHEMA_VERSION = "hist-procurement-credit-policy-v1"
FUNNEL_SCHEMA_VERSION = "hist-procurement-credit-funnel-v1"
SOURCE_KIND = "synthetic"
DOMESTIC_CURRENCY = "p02_domestic_currency"
GATE_PREFIX = "hist-procurement-credit-v1"


def _reject(message: str) -> None:
    raise ResearchGateError(f"{GATE_PREFIX}: {message}")


@dataclass(frozen=True)
class CreditLimit:
    """One enterprise's synthetic quarterly approval limit at one bank."""

    organization_id: int
    bank_index: int
    max_draw: float


@dataclass(frozen=True)
class ProcurementCreditPolicy:
    """Frozen synthetic domestic procurement-credit policy for one quarter."""

    policy_id: str
    quarter: str
    decision_at: date
    available_at: date
    limits: tuple[CreditLimit, ...]
    schema_version: str = POLICY_SCHEMA_VERSION
    source_kind: str = SOURCE_KIND
    currency: str = DOMESTIC_CURRENCY
    unlisted_default_zero: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Explicit export, including the zero default for unlisted enterprises."""
        return {
            "schema_version": self.schema_version,
            "source_kind": self.source_kind,
            "policy_id": self.policy_id,
            "quarter": self.quarter,
            "decision_at": self.decision_at.isoformat(),
            "available_at": self.available_at.isoformat(),
            "currency": self.currency,
            "unlisted_default_zero": bool(self.unlisted_default_zero),
            "limits": [
                {
                    "organization_id": int(limit.organization_id),
                    "bank_index": int(limit.bank_index),
                    "max_draw": float(limit.max_draw),
                }
                for limit in self.limits
            ],
        }


@dataclass(frozen=True)
class ProcurementCreditResult:
    """One admitted H3B tick; flows/gate/funnel are the authoritative output."""

    policy_id: str
    flows: MaterialTickFlows
    gate: InvariantSummary
    funnel: ProcurementCreditFunnel
    schema_version: str = FUNNEL_SCHEMA_VERSION


class ProcurementCreditFailure(ResearchGateError):
    """A tick/gate/measurement failure after the rollback snapshot was taken."""

    def __init__(
        self,
        *,
        phase: str,
        cause: BaseException,
        failed_flows: MaterialTickFlows | None,
        failed_trace: dict[str, np.ndarray],
    ) -> None:
        super().__init__(f"{GATE_PREFIX}: {phase} failed: {cause}")
        self.phase = phase
        self.cause = cause
        self.failed_flows = failed_flows
        self.failed_trace = failed_trace


def _quarter_end(quarter: str) -> date:
    parsed = Quarter.parse(quarter)
    month = parsed.quarter * 3
    return date(parsed.year, month, calendar.monthrange(parsed.year, month)[1])


def _validate_dates(policy: ProcurementCreditPolicy, current_quarter: str) -> None:
    if policy.quarter != current_quarter:
        _reject(
            f"policy quarter {policy.quarter!r} does not match the kernel quarter "
            f"{current_quarter!r}"
        )
    if policy.available_at > policy.decision_at:
        _reject(
            f"available_at {policy.available_at.isoformat()} is after decision_at "
            f"{policy.decision_at.isoformat()}"
        )
    end = _quarter_end(policy.quarter)
    if policy.decision_at > end:
        _reject(
            f"decision_at {policy.decision_at.isoformat()} is after the simulated "
            f"quarter end {end.isoformat()}"
        )
    if policy.available_at > end:
        _reject(
            f"available_at {policy.available_at.isoformat()} is after the simulated "
            f"quarter end {end.isoformat()}"
        )


def build_credit_approval_caps(
    state: MaterialState,
    policy: ProcurementCreditPolicy,
) -> np.ndarray:
    """Validate the policy limits and return dense (O,) approval caps."""
    if not isinstance(policy.policy_id, str) or not policy.policy_id.strip():
        _reject("policy_id must be a non-empty string")
    if policy.schema_version != POLICY_SCHEMA_VERSION:
        _reject(
            f"schema_version {policy.schema_version!r} != {POLICY_SCHEMA_VERSION!r}"
        )
    if policy.source_kind != SOURCE_KIND:
        _reject(f"source_kind {policy.source_kind!r} != {SOURCE_KIND!r}")
    if policy.currency != DOMESTIC_CURRENCY:
        _reject(f"currency {policy.currency!r} != {DOMESTIC_CURRENCY!r}")
    if not bool(policy.unlisted_default_zero):
        _reject("unlisted_default_zero must be True; the zero default is not optional")

    org_ids = np.asarray(state.organization_id, dtype=np.int64)
    org_bank = np.asarray(state.organization_bank, dtype=np.int64)
    org_type = np.asarray(state.organization_type, dtype=np.int64)
    bank_rows = org_type == finance._BANK_TYPE_CODE
    row_by_id = {int(org_id): row for row, org_id in enumerate(org_ids)}
    caps = np.zeros(int(org_ids.shape[0]), dtype=np.float64)
    seen: set[int] = set()
    for limit in policy.limits:
        org_id = int(limit.organization_id)
        if org_id in seen:
            _reject(f"duplicate credit limit for organization {org_id}")
        seen.add(org_id)
        row = row_by_id.get(org_id)
        if row is None:
            _reject(f"credit limit names unknown organization {org_id}")
        if bool(bank_rows[row]):
            _reject(f"organization {org_id} is a bank and cannot be a borrower")
        expected_bank = int(org_bank[row])
        if expected_bank < 0:
            _reject(f"organization {org_id} has no bank")
        bank = int(limit.bank_index)
        if bank < 0 or bank >= int(state.bank_reserves.shape[0]):
            _reject(f"organization {org_id} names unknown bank index {bank}")
        if bank != expected_bank:
            _reject(
                f"organization {org_id} names bank {bank} but its dense bank axis is "
                f"{expected_bank}"
            )
        amount = float(limit.max_draw)
        if not np.isfinite(amount) or amount < 0.0:
            _reject(f"organization {org_id} max_draw={amount!r} must be finite and non-negative")
        caps[row] = amount
    invalid = (~(org_bank >= 0)) | bank_rows
    if bool(np.any(caps[invalid] != 0.0)):
        _reject("approval caps for banks or organizations without a bank must be 0")
    return caps


def _validate_policy(
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: Any,
    policy: ProcurementCreditPolicy,
) -> np.ndarray:
    tick = int(state.completed_ticks)
    quarters = list(forcing.quarters)
    if tick < 0 or tick >= len(quarters):
        _reject(f"tick {tick} lies outside the forcing horizon")
    _validate_dates(policy, str(quarters[tick]))
    if bool(getattr(parameters, "m2_neutral_credit", False)):
        _reject("the H3B procurement-credit path rejects m2_neutral_credit=True")
    return build_credit_approval_caps(state, policy)


def _restore_state(state: MaterialState, snapshot: MaterialState) -> None:
    """Restore every mutable field from a pre-tick deep copy."""
    for field_name in state.__dataclass_fields__:
        setattr(state, field_name, copy.deepcopy(getattr(snapshot, field_name)))


def _copy_trace(trace: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {key: np.asarray(value).copy() for key, value in trace.items()}


def execute_procurement_credit_tick(
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: Any,
    network: MaterialNetwork,
    *,
    policy: ProcurementCreditPolicy,
    controls: Any = None,
) -> ProcurementCreditResult:
    """Run one H3B tick under ``policy`` and advance only on a full pass.

    Validation happens before any state mutation.  The single real tick is
    admitted only if the existing material/financial gate and the H3B funnel
    both pass.  On any later failure, the failed flows/trace are copied for
    diagnosis, every mutable state field is restored, the clock is not
    advanced, and :class:`ProcurementCreditFailure` is raised.
    """
    caps = _validate_policy(state, forcing, parameters, policy)
    before = copy.deepcopy(state)
    opening: MaterialStockSnapshot = capture_material_stocks(state)
    trace: dict[str, np.ndarray] = {}
    flows: MaterialTickFlows | None = None
    phase = "tick"
    try:
        flows = tick_material(
            state,
            forcing,
            parameters,
            network,
            controls=controls,
            credit_approval_caps=caps,
            procurement_trace=trace,
        )
        phase = "invariants"
        summary = accounting.check_material_invariants(
            opening,
            state,
            flows,
            parameters,
            network,
            controls=controls,
        )
        phase = "measurement"
        funnel = flow_funnel.measure_procurement_credit_tick(
            opening,
            state,
            flows,
            parameters,
            network,
            trace=trace,
            invariants=summary,
        )
    except Exception as exc:  # noqa: BLE001 - every failure must roll back
        failed_flows = copy.deepcopy(flows) if flows is not None else None
        failed_trace = _copy_trace(trace)
        _restore_state(state, before)
        raise ProcurementCreditFailure(
            phase=phase,
            cause=exc,
            failed_flows=failed_flows,
            failed_trace=failed_trace,
        ) from exc

    state.completed_ticks = int(state.completed_ticks) + 1
    return ProcurementCreditResult(
        policy_id=policy.policy_id,
        flows=flows,
        gate=summary,
        funnel=funnel,
    )
