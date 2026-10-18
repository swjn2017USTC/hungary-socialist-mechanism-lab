"""H3D: synthetic fixed lead-time staging (P->L and P->L->P->L) for the
material kernel.

This adapter is the only H3D entry point.  It validates a frozen quarterly
spec, runs exactly one real ``tick_material`` with the default-off
``micro_stage_count`` / ``micro_stage_trace`` hook, applies the existing
material/financial invariant gate, and verifies the stage trace.  Legacy
specs (``stage_count=None``) call ``tick_material`` *without* the hook so the
existing legacy allocation/delivery/production code path remains bit-for-bit
identical.

The default-off hook reuses the existing step-5/6 allocation, delivery,
payment and interbank leg blocks (no parallel ledger); ``completed_ticks``
advances only after every gate and stage-trace check passes.  The spec is a
*synthetic institution* (``source_kind="synthetic"``), not a historical
mechanism.  The adapter never creates a bank, account, clock, stock or
ledger of its own.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.contract.material import (
    ORGANIZATION_TYPE_ORDER,
    PURPOSE_CODES,
    OrganizationType,
    RoutePurpose,
)
from hsm_lab.engine import accounting
from hsm_lab.engine.accounting import InvariantSummary
from hsm_lab.engine.material import _fixed_network_vector, tick_material
from hsm_lab.engine.network import MaterialNetwork
from hsm_lab.engine.state import (
    MaterialForcing,
    MaterialState,
    MaterialStockSnapshot,
    MaterialTickFlows,
    capture_material_stocks,
)

SCHEMA_VERSION = "hist-lead-time-v1"
SOURCE_KIND = "synthetic"
ADAPTER_SCHEMA_VERSION = "hist-lead-time-v1"
GATE_PREFIX = "hist-lead-time-v1"
TRACE_STAGE_COUNT_KEY = "stage_count"
TRACE_N_KEY = "n"
TRACE_STAGES_KEY = "stages"
TRACE_FROZEN_BUDGETS_KEY = "frozen_quarter_budgets"

_ALLOWED_STAGE_COUNTS = (2, 4)


def _reject(message: str) -> None:
    raise ResearchGateError(f"{GATE_PREFIX}: {message}")


@dataclass(frozen=True)
class LeadTimeSpec:
    """Frozen synthetic quarterly lead-time spec for one quarter.

    ``stage_count`` is the number of P/L alternations inside the quarter:
    ``2`` (P->L) and ``4`` (P/2->L/2->P/2->L/2) are admitted; ``None`` is the
    legacy path with no extra staging.  The spec never enlarges the
    climate-controlled boundary -- the same opening, demand and finance prelude
    are admitted exactly once.
    """

    stage_count: Literal[2, 4] | None = None
    schema_version: str = SCHEMA_VERSION
    source_kind: str = SOURCE_KIND

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_kind": self.source_kind,
            "stage_count": self.stage_count,
        }


@dataclass(frozen=True)
class LeadTimeResult:
    """One admitted H3D tick; flows/gate/trace are the authoritative output."""

    spec: LeadTimeSpec
    flows: MaterialTickFlows
    gate: InvariantSummary
    trace: dict[str, Any]
    phase_times: dict[str, float]
    schema_version: str = ADAPTER_SCHEMA_VERSION


class LeadTimeFailure(ResearchGateError):
    """A tick/gate/trace failure after the rollback snapshot was taken."""

    def __init__(
        self,
        *,
        phase: str,
        cause: BaseException,
        failed_flows: MaterialTickFlows | None,
        failed_trace: dict[str, Any],
    ) -> None:
        super().__init__(f"{GATE_PREFIX}: {phase} failed: {cause}")
        self.phase = phase
        self.cause = cause
        self.failed_flows = failed_flows
        self.failed_trace = failed_trace


def load_lead_time_spec(path: Path) -> LeadTimeSpec:
    """Load and validate a frozen synthetic lead-time spec from disk."""
    if not isinstance(path, Path):
        path = Path(path)
    if not path.is_file():
        _reject(f"lead-time spec file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - JSON errors must be explicit
        _reject(f"invalid JSON in lead-time spec {path}: {exc}")
    if not isinstance(payload, dict):
        _reject("lead-time spec must be a JSON object")
    unknown = set(payload) - {"schema_version", "source_kind", "stage_count"}
    if unknown:
        _reject(f"unknown keys in lead-time spec: {sorted(unknown)}")
    schema = payload.get("schema_version", SCHEMA_VERSION)
    if not isinstance(schema, str) or schema != SCHEMA_VERSION:
        _reject(f"schema_version {schema!r} != {SCHEMA_VERSION!r}")
    source = payload.get("source_kind", SOURCE_KIND)
    if not isinstance(source, str) or source != SOURCE_KIND:
        _reject(f"source_kind {source!r} != {SOURCE_KIND!r}")
    stage = payload.get("stage_count", None)
    if stage is None:
        return LeadTimeSpec(stage_count=None)
    # bool is a subclass of int in Python; reject explicitly so True/False do
    # not silently pass as the integer 2 or 0.
    if isinstance(stage, bool) or not isinstance(stage, int):
        _reject(
            f"stage_count {stage!r} must be null, 2, or 4; got "
            f"{type(stage).__name__}"
        )
    if stage not in _ALLOWED_STAGE_COUNTS:
        _reject(f"stage_count {stage!r} not in {sorted(_ALLOWED_STAGE_COUNTS)}")
    if stage == 2:
        return LeadTimeSpec(stage_count=2)
    return LeadTimeSpec(stage_count=4)


def _restore_state(state: MaterialState, snapshot: MaterialState) -> None:
    """Restore every mutable field from a pre-tick deep copy."""
    for field_name in state.__dataclass_fields__:
        setattr(state, field_name, copy.deepcopy(getattr(snapshot, field_name)))


def _copy_trace(trace: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(value) for key, value in trace.items()}


def _validate_spec_clock(
    state: MaterialState, forcing: MaterialForcing, parameters: Any
) -> None:
    tick = int(state.completed_ticks)
    quarters = list(forcing.quarters)
    if tick < 0 or tick >= len(quarters):
        _reject(f"tick {tick} lies outside the forcing horizon")
    if bool(getattr(parameters, "m2_neutral_credit", False)):
        _reject("the H3D lead-time path rejects m2_neutral_credit=True")


def _verify_trace(
    *,
    spec: LeadTimeSpec,
    state: MaterialState,
    network: MaterialNetwork,
    parameters: Any,
    flows: MaterialTickFlows,
    trace: dict[str, Any],
    audit: dict[str, Any],
) -> None:
    """Admit the staged trace only after the running totals match the kernel.

    ``audit`` is the kernel's own internal snapshot dict (see
    ``tick_material(micro_stage_audit=...)``), never the trace.  Every trace
    stock/cash/bank field is compared against it, and the audit -- not the
    trace -- is the authoritative stock/bank walk, so a coherent rewrite of
    every trace field (for example +100 on the prelude and every stage stock)
    is rejected at the first mismatch.  All finite, non-negative, correctly
    shaped checks are required; envelopes are reconciled against the recorded
    per-round spend; and cumulative stage allocations/deliveries/use must
    match the authoritative ``flows`` arrays on every non-household /
    non-early-service row.
    """
    if not isinstance(trace, dict):
        _reject("trace must be a dict")
    expected_stage_count = spec.stage_count if spec.stage_count is not None else 0
    declared = trace.get(TRACE_STAGE_COUNT_KEY, None)
    if declared != expected_stage_count:
        _reject(
            f"trace {TRACE_STAGE_COUNT_KEY} {declared!r} != spec stage_count "
            f"{expected_stage_count!r}"
        )
    declared_n = trace.get(TRACE_N_KEY, None)
    expected_n = expected_stage_count // 2 if expected_stage_count else 0
    if declared_n != expected_n:
        _reject(
            f"trace {TRACE_N_KEY} {declared_n!r} != expected n={expected_n!r}"
        )

    # --- structural: frozen budgets ---------------------------------------
    declared_budgets = trace.get(TRACE_FROZEN_BUDGETS_KEY, None)
    if not isinstance(declared_budgets, dict):
        _reject("trace frozen_quarter_budgets must be a dict")
    org_count = int(state.organization_id.shape[0])
    bank_count = int(np.asarray(state.bank_reserves).shape[0])
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    activity_count = int(np.asarray(network.activity_capacity).shape[0])
    k_count = int(np.asarray(network.input_cell).shape[0])
    cell_count = int(np.asarray(network.cell_commodity).shape[0])
    d_count = int(np.asarray(network.demand_cell).shape[0])

    expected_budget_keys = {
        "organization_cash",
        "bank_reserves",
        "plot_pool",
        "logistics_pool_initial",
        "handling_capacity_initial",
        "treasury",
    }
    extra_budget_keys = set(declared_budgets.keys()) - expected_budget_keys
    if extra_budget_keys:
        _reject(
            f"trace frozen_quarter_budgets has unexpected keys: "
            f"{sorted(extra_budget_keys)}"
        )
    missing_budget_keys = expected_budget_keys - set(declared_budgets.keys())
    if missing_budget_keys:
        _reject(
            f"trace frozen_quarter_budgets missing keys: "
            f"{sorted(missing_budget_keys)}"
        )

    def _check_budget_array(name: str, expected_size: int) -> np.ndarray:
        value = declared_budgets[name]
        arr = np.asarray(value, dtype=np.float64)
        if arr.ndim != 1 or arr.shape[0] != expected_size:
            _reject(
                f"frozen_quarter_budgets.{name} must have shape "
                f"({expected_size},), got {arr.shape}"
            )
        if not bool(np.all(np.isfinite(arr))):
            _reject(f"frozen_quarter_budgets.{name} contains non-finite values")
        if bool(np.any(arr < 0.0)):
            _reject(f"frozen_quarter_budgets.{name} contains negative values")
        return arr

    def _p_field(
        index_i: int,
        stage_d: dict,
        name: str,
        expected_size: int,
    ) -> np.ndarray:
        if name not in stage_d:
            _reject(f"stage[{index_i}] (P) is missing required field {name!r}")
        value = stage_d[name]
        arr = np.asarray(value, dtype=np.float64)
        if arr.shape != (expected_size,):
            _reject(
                f"stage[{index_i}].{name} shape {arr.shape} != "
                f"expected ({expected_size},)"
            )
        if not bool(np.all(np.isfinite(arr))):
            _reject(f"stage[{index_i}].{name} contains non-finite values")
        if bool(np.any(arr < 0.0)):
            _reject(f"stage[{index_i}].{name} contains negative values")
        return arr

    def _l_array(
        index_i: int,
        stage_d: dict,
        name: str,
        expected_size: int,
    ) -> np.ndarray:
        if name not in stage_d:
            _reject(f"stage[{index_i}] (L) is missing required field {name!r}")
        value = stage_d[name]
        arr = np.asarray(value, dtype=np.float64)
        if arr.shape != (expected_size,):
            _reject(
                f"stage[{index_i}].{name} shape {arr.shape} != "
                f"expected ({expected_size},)"
            )
        if not bool(np.all(np.isfinite(arr))):
            _reject(f"stage[{index_i}].{name} contains non-finite values")
        if bool(np.any(arr < -accounting.ATOL)):
            _reject(f"stage[{index_i}].{name} contains negative values")
        return arr

    def _stock_field(
        index_i: int,
        stage_d: dict,
        name: str,
    ) -> np.ndarray:
        if name not in stage_d:
            _reject(f"stage[{index_i}] is missing required field {name!r}")
        arr = np.asarray(stage_d[name], dtype=np.float64)
        if arr.shape != (cell_count,):
            _reject(
                f"stage[{index_i}].{name} shape {arr.shape} != "
                f"expected ({cell_count},)"
            )
        if not bool(np.all(np.isfinite(arr))):
            _reject(f"stage[{index_i}].{name} contains non-finite values")
        if bool(np.any(arr < -accounting.ATOL)):
            _reject(f"stage[{index_i}].{name} contains negative values")
        return arr

    frozen_org_cash = _check_budget_array("organization_cash", org_count)
    frozen_bank_reserves = _check_budget_array("bank_reserves", bank_count)
    frozen_plot_pool = _check_budget_array("plot_pool", region_count)
    frozen_logistics_pool = _check_budget_array("logistics_pool_initial", org_count)
    frozen_handling_capacity = _check_budget_array(
        "handling_capacity_initial", org_count
    )
    treasury_value = declared_budgets["treasury"]
    if not isinstance(treasury_value, (int, float)) or isinstance(treasury_value, bool):
        _reject(
            f"frozen_quarter_budgets.treasury must be a numeric scalar, got "
            f"{type(treasury_value).__name__}"
        )
    if not bool(np.isfinite(float(treasury_value))):
        _reject("frozen_quarter_budgets.treasury must be finite")
    if float(treasury_value) < 0.0:
        _reject("frozen_quarter_budgets.treasury must be non-negative")
    frozen_treasury = float(treasury_value)

    def _require_close(message: str, lhs: Any, rhs: Any) -> None:
        lhs_arr = np.asarray(lhs, dtype=np.float64)
        rhs_arr = np.asarray(rhs, dtype=np.float64)
        if lhs_arr.shape != rhs_arr.shape:
            _reject(
                f"{message}: shape {lhs_arr.shape} != {rhs_arr.shape}"
            )
        # A NaN makes the tolerance comparison false and +inf can defeat it
        # through the tolerance scale; reject non-finite operands first.
        if not bool(np.all(np.isfinite(lhs_arr))) or not bool(
            np.all(np.isfinite(rhs_arr))
        ):
            _reject(f"{message}: non-finite comparison operand")
        tolerance = accounting.tolerance_for(lhs_arr, rhs_arr)
        if bool(np.any(np.abs(lhs_arr - rhs_arr) > tolerance)):
            _reject(message)

    # --- structural: physical stock path ----------------------------------
    if "prelude_stock" not in trace:
        _reject("trace is missing required field 'prelude_stock'")
    prelude_stock = np.asarray(trace["prelude_stock"], dtype=np.float64)
    if prelude_stock.shape != (cell_count,):
        _reject(
            f"trace prelude_stock shape {prelude_stock.shape} != "
            f"expected ({cell_count},)"
        )
    if not bool(np.all(np.isfinite(prelude_stock))):
        _reject("trace prelude_stock contains non-finite values")
    if bool(np.any(prelude_stock < -accounting.ATOL)):
        _reject("trace prelude_stock contains negative values")

    # --- structural: stages ----------------------------------------------
    stages = trace.get(TRACE_STAGES_KEY, None)
    if not isinstance(stages, list) or len(stages) != max(expected_stage_count, 0):
        _reject(
            f"trace stages must be a list of length {max(expected_stage_count, 0)}, "
            f"got {type(stages).__name__} of length "
            f"{len(stages) if isinstance(stages, list) else 'N/A'}"
        )
    expected_kinds = ("P", "L") * expected_n
    for expected_index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            _reject("each stage must be a dict")
        index = stage.get("index", None)
        kind = stage.get("kind", None)
        if index is None or kind is None:
            _reject("stage entries must declare index and kind")
        if not isinstance(index, int) or index < 0 or index >= expected_stage_count:
            _reject(
                f"stage index {index!r} is not an int in [0,{expected_stage_count})"
            )
        if index != expected_index:
            _reject(
                f"stage at position {expected_index} declares index {index}; "
                f"stages must stay in ascending order"
            )
        if expected_stage_count and kind != expected_kinds[expected_index]:
            _reject(
                f"stage[{index}] kind {kind!r} != expected "
                f"{expected_kinds[expected_index]!r}"
            )

    # --- independent kernel audit snapshot -------------------------------
    # The trace is an export, not the authority.  ``audit`` is populated by
    # the kernel itself at the same real state points and is never merged
    # into the trace, so a coherent rewrite of every trace stock/cash/bank
    # field is rejected here.
    if not isinstance(audit, dict) or not audit:
        _reject("kernel micro_stage_audit snapshot is required")
    if audit.get("stage_count") != expected_stage_count:
        _reject(
            f"kernel audit stage_count {audit.get('stage_count')!r} != "
            f"spec stage_count {expected_stage_count!r}"
        )
    if audit.get("n") != expected_n:
        _reject(
            f"kernel audit n {audit.get('n')!r} != expected n={expected_n!r}"
        )
    audit_stages = audit.get("stages", None)
    if not isinstance(audit_stages, list) or len(audit_stages) != len(stages):
        _reject(
            "kernel audit stages must be a list with one entry per trace stage"
        )
    if "prelude_stock" not in audit:
        _reject("kernel audit is missing 'prelude_stock'")
    audit_prelude = np.asarray(audit["prelude_stock"], dtype=np.float64)
    if audit_prelude.shape != (cell_count,):
        _reject(
            f"kernel audit prelude_stock shape {audit_prelude.shape} != "
            f"expected ({cell_count},)"
        )
    if not bool(np.all(np.isfinite(audit_prelude))):
        _reject("kernel audit prelude_stock contains non-finite values")
    if bool(np.any(audit_prelude < -accounting.ATOL)):
        _reject("kernel audit prelude_stock contains negative values")
    _require_close(
        "trace prelude_stock diverges from the kernel audit snapshot",
        prelude_stock,
        audit_prelude,
    )
    for position, (stage, audit_stage) in enumerate(zip(stages, audit_stages, strict=True)):
        if not isinstance(audit_stage, dict):
            _reject("each kernel audit stage must be a dict")
        if audit_stage.get("index") != stage.get("index"):
            _reject(
                f"kernel audit stage at position {position} declares index "
                f"{audit_stage.get('index')!r} != trace index "
                f"{stage.get('index')!r}"
            )
        if audit_stage.get("kind") != stage.get("kind"):
            _reject(
                f"kernel audit stage[{stage.get('index')!r}] kind "
                f"{audit_stage.get('kind')!r} != trace kind "
                f"{stage.get('kind')!r}"
            )

    def _audit_array(
        index_i: int, audit_stage: dict, name: str, expected_size: int
    ) -> np.ndarray:
        if name not in audit_stage:
            _reject(
                f"kernel audit stage[{index_i}] is missing required field "
                f"{name!r}"
            )
        arr = np.asarray(audit_stage[name], dtype=np.float64)
        if arr.shape != (expected_size,):
            _reject(
                f"kernel audit stage[{index_i}].{name} shape {arr.shape} != "
                f"expected ({expected_size},)"
            )
        if not bool(np.all(np.isfinite(arr))):
            _reject(
                f"kernel audit stage[{index_i}].{name} contains non-finite "
                f"values"
            )
        return arr

    # Compare every trace stock/cash/bank field against the kernel snapshot
    # before any arithmetic.  This is the first trace/audit mismatch point.
    for stage, audit_stage in zip(stages, audit_stages, strict=True):
        index_i = int(stage["index"])
        for name, size in (
            ("stock_before", cell_count),
            ("stock_after", cell_count),
            ("state_cash_after", org_count),
            ("state_bank_reserves_after", bank_count),
        ):
            if name not in stage:
                _reject(
                    f"stage[{index_i}] is missing required field {name!r}"
                )
            trace_value = np.asarray(stage[name], dtype=np.float64)
            if trace_value.shape != (size,):
                _reject(
                    f"stage[{index_i}].{name} shape {trace_value.shape} != "
                    f"expected ({size},)"
                )
            audit_value = _audit_array(index_i, audit_stage, name, size)
            _require_close(
                f"stage[{index_i}].{name} diverges from the kernel audit "
                f"snapshot",
                trace_value,
                audit_value,
            )

    # --- pre-computed helper arrays --------------------------------------
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    ordered = np.asarray(flows.ordered, dtype=np.float64)
    allocated_d = np.asarray(flows.allocated, dtype=np.float64)
    delivered_d = np.asarray(flows.delivered, dtype=np.float64)

    if bool(
        np.any(
            allocated_d > ordered + accounting.tolerance_for(allocated_d, ordered)
        )
    ):
        _reject("cumulative allocated exceeds the frozen ordered demand")
    if bool(
        np.any(
            delivered_d
            > allocated_d + accounting.tolerance_for(delivered_d, allocated_d)
        )
    ):
        _reject("cumulative delivered exceeds the cumulative allocated demand")

    # Non-household / non-early-service masks (used for cumulative reconciliation
    # at the end of the gate).
    _household_purpose = int(PURPOSE_CODES[RoutePurpose.HOUSEHOLD])
    non_household_demand = (
        demand_purpose[:d_count] != _household_purpose
    )
    early_service_acts = np.asarray(
        network.activity_early_service, dtype=bool
    )
    non_early_activities = ~early_service_acts
    non_transport_k_mask = ~early_service_acts[
        np.asarray(network.input_activity, dtype=np.int64)
    ]
    # K-axis slice in flows.used is the first k_count rows.
    non_early_input_rows = non_transport_k_mask

    input_cell_arr = np.asarray(network.input_cell, dtype=np.int64)
    input_activity_arr = np.asarray(network.input_activity, dtype=np.int64)
    a_csr = network.A.tocsr()
    coefficient_by_k = np.zeros(k_count, dtype=np.float64)
    coefficient_by_k[
        np.asarray(a_csr.indices, dtype=np.int64)
    ] = np.asarray(a_csr.data, dtype=np.float64)

    # The only destination credit that may flow back into an L source pool is
    # the current-quarter receipt on a RETAIL-owned cell (derived from the
    # network owner axes + the real OrganizationType ordinals, never guessed).
    retail_code = int(ORGANIZATION_TYPE_ORDER.index(OrganizationType.RETAIL))
    owner_kind_arr = np.asarray(network.cell_owner_kind, dtype=np.int64)
    owner_id_arr = np.asarray(network.cell_owner_id, dtype=np.int64)
    owner_org_arr = np.full(cell_count, -1, dtype=np.int64)
    org_owner_mask = owner_kind_arr == 0
    owner_org_arr[org_owner_mask] = owner_id_arr[org_owner_mask]
    valid_owner_mask = owner_org_arr >= 0
    org_type_arr = np.asarray(state.organization_type, dtype=np.int64)
    retail_source_mask = np.zeros(cell_count, dtype=bool)
    retail_source_mask[valid_owner_mask] = (
        org_type_arr[owner_org_arr[valid_owner_mask]] == retail_code
    )
    wholesale_code = int(
        ORGANIZATION_TYPE_ORDER.index(
            OrganizationType.WHOLESALE_PROCURMENT
        )
    )

    # Edge-axis authorities: every per-L source/destination quantity and
    # logistics/handling spend is recomputed from the authoritative network
    # routes and the round's real edge deliveries.
    edge_count = int(np.asarray(network.edge_source_cell).shape[0])
    edge_source_arr = np.asarray(network.edge_source_cell, dtype=np.int64)
    edge_destination_arr = np.asarray(
        network.edge_destination_cell, dtype=np.int64
    )
    edge_commodity_arr = np.asarray(network.edge_commodity, dtype=np.int64)
    edge_transport_org_arr = np.asarray(
        network.edge_transport_org, dtype=np.int64
    )
    edge_per_unit_arr = np.asarray(
        network.edge_transport_per_unit, dtype=np.float64
    )
    edge_needs_transport = (
        ~np.asarray(network.edge_self_hauled, dtype=bool)
    ) & (edge_transport_org_arr >= 0)
    edge_valid_destination = edge_destination_arr >= 0
    # Household edges are settled by ``allocate_household_baskets`` after the
    # L rounds and overwrite their rows on the quarterly edge vectors; the
    # staged L binding therefore covers the non-household demand edges only
    # (mirroring the existing per-demand reconciliation).
    non_household_edge_mask = (
        demand_purpose[np.asarray(network.edge_demand, dtype=np.int64)]
        != _household_purpose
    )
    source_edge_owner = owner_org_arr[edge_source_arr]
    wholesale_edge_mask = (source_edge_owner >= 0) & (
        org_type_arr[np.maximum(source_edge_owner, 0)] == wholesale_code
    )
    destination_edge_owner = np.full(edge_count, -1, dtype=np.int64)
    destination_edge_owner[edge_valid_destination] = owner_org_arr[
        edge_destination_arr[edge_valid_destination]
    ]
    retail_edge_mask = (destination_edge_owner >= 0) & (
        org_type_arr[np.maximum(destination_edge_owner, 0)] == retail_code
    )
    # The kernel normalizes non-positive ``handling_work_per_unit`` to 1.0
    # before using it; the verifier must recompute the spend with the same
    # effective coefficient or a clean all-zero-handling tick is rejected.
    handling_unit_work = _fixed_network_vector(
        parameters.handling_work_per_unit, network
    )
    handling_unit_work = np.where(
        handling_unit_work > 0.0, handling_unit_work, 1.0
    )

    # Inter-L continuity: every envelope/pool that must never refill between
    # stage rounds, keyed to the L trace field prefix.
    _l_envelope_prefixes = (
        "org_cash_envelope",
        "plot_pool_envelope",
        "bank_outflow",
        "logistics_pool",
        "handling",
    )
    previous_l_after: dict[str, np.ndarray] = {}
    previous_treasury_after: float | None = None

    # --- per-stage shape / value enforcement ----------------------------
    sum_alloc_L = np.zeros(d_count, dtype=np.float64)
    sum_delivered_L = np.zeros(d_count, dtype=np.float64)
    sum_edge_allocated_L = np.zeros(edge_count, dtype=np.float64)
    sum_edge_delivered_L = np.zeros(edge_count, dtype=np.float64)
    sum_edge_service_used_L = np.zeros(edge_count, dtype=np.float64)
    sum_edge_service_fee_L = np.zeros(edge_count, dtype=np.float64)
    sum_purchases = np.zeros(org_count, dtype=np.float64)
    sum_sales = np.zeros(org_count, dtype=np.float64)
    sum_realized_P = np.zeros(activity_count, dtype=np.float64)
    sum_used_P = np.zeros(k_count, dtype=np.float64)
    sum_produced_P = np.zeros(cell_count, dtype=np.float64)

    # Physical stock walk: each stage must open at the exact closing stock of
    # the previous stage (P1 opens at the prelude stock).  This is what binds
    # the P/L payloads to the real temporal path and rejects a P1/P2 swap.
    # The audit snapshot -- not the trace -- is the authoritative walk.
    expected_stock = audit_prelude
    # Cash/bank walk: the real prelude balances are frozen for the whole
    # quarter.  P cannot move them; every L carries its real bank delta, so
    # the next L's real snapshot must continue from the previous one exactly
    # (no arbitrary reserve inflation and no inter-stage refill).
    expected_cash_state = frozen_org_cash
    expected_bank_state = frozen_bank_reserves
    # Reconstructed cumulative L allocation, used to bind each round's
    # ``round_ordered`` to the frozen quarterly ordered demand.
    cumulative_allocated_l = np.zeros(d_count, dtype=np.float64)
    previous_state_cash: np.ndarray | None = None
    previous_state_bank: np.ndarray | None = None

    for stage, audit_stage in zip(stages, audit_stages, strict=True):
        index = int(stage["index"])
        kind = stage["kind"]
        audit_stock_before = _audit_array(
            index, audit_stage, "stock_before", cell_count
        )
        audit_stock_after = _audit_array(
            index, audit_stage, "stock_after", cell_count
        )
        audit_cash_after = _audit_array(
            index, audit_stage, "state_cash_after", org_count
        )
        audit_bank_after = _audit_array(
            index, audit_stage, "state_bank_reserves_after", bank_count
        )
        _require_close(
            f"kernel audit stage[{index}] stock_before diverges from the "
            f"previous stage's audited stock_after",
            audit_stock_before,
            expected_stock,
        )

        if kind == "P":
            target_p = _p_field(
                index, stage, "target", activity_count
            )
            realized_p = _p_field(
                index, stage, "activity_realized", activity_count
            )
            used_p = _p_field(
                index, stage, "used", k_count
            )
            produced_p = _p_field(
                index, stage, "produced", cell_count
            )
            input_available_before = _p_field(
                index, stage, "input_available_before", k_count
            )
            source_eligible_before_p = _p_field(
                index,
                stage,
                "source_eligible_before",
                cell_count,
            )
            source_eligible_after_p = _p_field(
                index,
                stage,
                "source_eligible_after",
                cell_count,
            )
            stock_before_p = _stock_field(index, stage, "stock_before")
            stock_after_p = _stock_field(index, stage, "stock_after")

            _require_close(
                f"stage[{index}] (P) target diverges from "
                f"flows.activity_target / n",
                target_p,
                np.asarray(flows.activity_target, dtype=np.float64)
                / float(max(expected_n, 1)),
            )
            if bool(
                np.any(
                    realized_p
                    > target_p + accounting.tolerance_for(realized_p, target_p)
                )
            ):
                _reject(
                    f"stage[{index}] (P) activity_realized exceeds target"
                )
            non_transport_k_indices = np.flatnonzero(non_transport_k_mask)
            if non_transport_k_indices.size:
                if bool(
                    np.any(
                        used_p[non_transport_k_indices]
                        > input_available_before[non_transport_k_indices]
                        + accounting.tolerance_for(
                            used_p[non_transport_k_indices],
                            input_available_before[non_transport_k_indices],
                        )
                    )
                ):
                    _reject(
                        f"stage[{index}] (P) used[] exceeds input_available_before[]"
                    )
                # Per-stage Leontief recipe: used_k = A[activity_k, k] *
                # realized[activity_k].  This rejects any per-stage recipe
                # substitution that preserves the quarterly total.
                required_used = (
                    coefficient_by_k[non_transport_k_indices]
                    * realized_p[
                        input_activity_arr[non_transport_k_indices]
                    ]
                )
                _require_close(
                    f"stage[{index}] (P) used[] diverges from the Leontief "
                    f"recipe A[input_activity, k] * activity_realized",
                    used_p[non_transport_k_indices],
                    required_used,
                )
                # The persisted pre-P availability must be the genuine
                # pre-production stock on the same cell (no opening+delivered
                # double count and no derived eligibility vector).
                _require_close(
                    f"stage[{index}] (P) input_available_before[] diverges "
                    f"from stock_before[input_cell[]]",
                    input_available_before[non_transport_k_indices],
                    stock_before_p[
                        input_cell_arr[non_transport_k_indices]
                    ],
                )

            expected_source_delta = produced_p - np.bincount(
                input_cell_arr,
                weights=used_p,
                minlength=cell_count,
            )
            _require_close(
                f"stage[{index}] (P) source_eligible_after - before diverges "
                f"from produced - consumed",
                source_eligible_after_p - source_eligible_before_p,
                expected_source_delta,
            )
            _require_close(
                f"stage[{index}] (P) stock_before diverges from the previous "
                f"stage's stock_after",
                stock_before_p,
                expected_stock,
            )
            _require_close(
                f"stage[{index}] (P) stock_after - stock_before diverges "
                f"from produced - bincount(input_cell, used)",
                stock_after_p - stock_before_p,
                expected_source_delta,
            )
            _require_close(
                f"stage[{index}] (P) must not move organization cash",
                audit_cash_after,
                expected_cash_state,
            )
            _require_close(
                f"stage[{index}] (P) must not move bank reserves",
                audit_bank_after,
                expected_bank_state,
            )
            expected_cash_state = audit_cash_after
            expected_bank_state = audit_bank_after
            expected_stock = audit_stock_after

            # Aggregate reconciliation: B.T @ realized over non-early-service
            # activities is the accounting identity that ties the per-stage
            # production vector to the Leontief recipe.  We bound the
            # per-stage equality with the same tolerance framework.
            b_indptr = np.asarray(network.B.indptr)
            b_rows_arr = np.repeat(
                np.arange(b_indptr.size - 1, dtype=np.int64),
                np.diff(b_indptr),
            )
            b_cells_arr = np.asarray(network.B.indices, dtype=np.int64)
            b_coefficient_arr = np.asarray(
                network.B.data, dtype=np.float64
            )
            b_mask = ~early_service_acts[b_rows_arr]
            production_amounts = (
                b_coefficient_arr[b_mask]
                * realized_p[b_rows_arr[b_mask]]
            )
            expected_produced = np.bincount(
                b_cells_arr[b_mask],
                weights=production_amounts,
                minlength=cell_count,
            )
            if bool(
                np.any(
                    np.abs(produced_p - expected_produced)
                    > 1e-7
                    + 1e-7
                    * np.maximum(
                        np.abs(produced_p), np.abs(expected_produced)
                    )
                )
            ):
                _reject(
                    f"stage[{index}] (P) produced vector diverges from "
                    f"B.T @ activity_realized over non-early rows"
                )

            sum_realized_P = sum_realized_P + realized_p
            sum_used_P = sum_used_P + used_p
            sum_produced_P = sum_produced_P + produced_p

        elif kind == "L":
            round_ordered_l = _l_array(index, stage, "round_ordered", d_count)
            round_allocated_l = _l_array(index, stage, "allocated", d_count)
            round_delivered_l = _l_array(index, stage, "delivered", d_count)
            source_outflow_l = _l_array(
                index, stage, "source_outflow", cell_count
            )
            destination_credit_l = _l_array(
                index, stage, "destination_credit", cell_count
            )
            source_eligible_before_l = _l_array(
                index, stage, "source_eligible_before", cell_count
            )
            source_eligible_after_l = _l_array(
                index, stage, "source_eligible_after", cell_count
            )
            logistics_pool_before = _l_array(
                index, stage, "logistics_pool_before", org_count
            )
            logistics_pool_after = _l_array(
                index, stage, "logistics_pool_after", org_count
            )
            logistics_round_cap = _l_array(
                index, stage, "logistics_round_cap", org_count
            )
            logistics_spend = _l_array(
                index, stage, "logistics_spend", org_count
            )
            handling_before = _l_array(
                index, stage, "handling_before", org_count
            )
            handling_after = _l_array(
                index, stage, "handling_after", org_count
            )
            handling_round_cap = _l_array(
                index, stage, "handling_round_cap", org_count
            )
            handling_spend = _l_array(
                index, stage, "handling_spend", org_count
            )
            edge_allocated_l = _l_array(
                index, stage, "edge_allocated", edge_count
            )
            edge_delivered_l = _l_array(
                index, stage, "edge_delivered", edge_count
            )
            edge_service_used_l = _l_array(
                index, stage, "edge_service_used", edge_count
            )
            edge_service_fee_l = _l_array(
                index, stage, "edge_service_fee", edge_count
            )
            org_cash_before = _l_array(
                index, stage, "org_cash_envelope_before", org_count
            )
            org_cash_after = _l_array(
                index, stage, "org_cash_envelope_after", org_count
            )
            org_purchases = _l_array(index, stage, "purchases", org_count)
            org_sales = _l_array(index, stage, "sales", org_count)
            plot_pool_before = _l_array(
                index, stage, "plot_pool_envelope_before", region_count
            )
            plot_pool_after = _l_array(
                index, stage, "plot_pool_envelope_after", region_count
            )
            plot_pool_spend = _l_array(
                index, stage, "plot_pool_spend", region_count
            )
            bank_outflow_before = _l_array(
                index, stage, "bank_outflow_before", bank_count
            )
            bank_outflow_after = _l_array(
                index, stage, "bank_outflow_after", bank_count
            )
            bank_outflow_spend = _l_array(
                index, stage, "bank_outflow_spend", bank_count
            )
            treasury_before = float(stage.get("treasury_before", float("nan")))
            treasury_after = float(stage.get("treasury_after", float("nan")))
            treasury_spend = float(stage.get("treasury_spend", float("nan")))
            stock_before_l = _stock_field(index, stage, "stock_before")
            stock_after_l = _stock_field(index, stage, "stock_after")
            state_cash_after = _l_array(
                index, stage, "state_cash_after", org_count
            )
            state_bank_reserves_after = _l_array(
                index, stage, "state_bank_reserves_after", bank_count
            )

            for name, value in (
                ("treasury_before", treasury_before),
                ("treasury_after", treasury_after),
                ("treasury_spend", treasury_spend),
            ):
                if not bool(np.isfinite(value)):
                    _reject(f"stage[{index}].{name} is not finite")

            envelope_before = {
                "org_cash_envelope": org_cash_before,
                "plot_pool_envelope": plot_pool_before,
                "bank_outflow": bank_outflow_before,
                "logistics_pool": logistics_pool_before,
                "handling": handling_before,
            }
            envelope_after = {
                "org_cash_envelope": org_cash_after,
                "plot_pool_envelope": plot_pool_after,
                "bank_outflow": bank_outflow_after,
                "logistics_pool": logistics_pool_after,
                "handling": handling_after,
            }
            for prefix, value in envelope_before.items():
                if bool(np.any(value < -accounting.ATOL)):
                    _reject(
                        f"stage[{index}] (L) {prefix}_before contains "
                        f"negative values"
                    )
            for prefix, value in envelope_after.items():
                if bool(np.any(value < -accounting.ATOL)):
                    _reject(
                        f"stage[{index}] (L) {prefix}_after contains "
                        f"negative values"
                    )
            if min(treasury_before, treasury_after, treasury_spend) < -accounting.ATOL:
                _reject(
                    f"stage[{index}] (L) treasury envelope contains "
                    f"negative values"
                )

            frozen_before = {
                "org_cash_envelope": frozen_org_cash,
                "plot_pool_envelope": frozen_plot_pool,
                "bank_outflow": frozen_bank_reserves,
                "logistics_pool": frozen_logistics_pool,
                "handling": frozen_handling_capacity,
            }
            if previous_treasury_after is None:
                # The first L must start from the frozen quarterly budgets;
                # this rejects a zeroed/rewritten frozen budget.
                for prefix, frozen in frozen_before.items():
                    _require_close(
                        f"stage[{index}] (L) {prefix}_before diverges from "
                        f"the frozen quarterly budget",
                        envelope_before[prefix],
                        frozen,
                    )
                _require_close(
                    f"stage[{index}] (L) treasury_before diverges from the "
                    f"frozen quarterly Treasury budget",
                    np.asarray(treasury_before),
                    np.asarray(frozen_treasury),
                )
            else:
                # Later L rounds inherit the previous round's closing
                # envelope exactly; no inter-stage refill is admitted.
                for prefix in frozen_before:
                    _require_close(
                        f"stage[{index}] (L) {prefix}_before diverges from "
                        f"the previous L's {prefix}_after (inter-stage refill)",
                        envelope_before[prefix],
                        previous_l_after[prefix],
                    )
                _require_close(
                    f"stage[{index}] (L) treasury_before diverges from the "
                    f"previous L's treasury_after (inter-stage refill)",
                    np.asarray(treasury_before),
                    np.asarray(previous_treasury_after),
                )

            tol_alloc = accounting.tolerance_for(
                round_allocated_l, round_ordered_l
            )
            if bool(np.any(round_allocated_l < -1e-9)):
                _reject(
                    f"stage[{index}] (L) round allocated is negative on "
                    f"{int(np.count_nonzero(round_allocated_l < -1e-9))} demand rows"
                )
            if bool(np.any(round_delivered_l < -1e-9)):
                _reject(
                    f"stage[{index}] (L) round delivered is negative on "
                    f"{int(np.count_nonzero(round_delivered_l < -1e-9))} demand rows"
                )
            if bool(np.any(round_allocated_l > round_ordered_l + tol_alloc)):
                _reject(
                    f"stage[{index}] (L) round allocated exceeds round_ordered"
                )
            tol_d = accounting.tolerance_for(round_delivered_l, round_allocated_l)
            if bool(np.any(round_delivered_l > round_allocated_l + tol_d)):
                _reject(
                    f"stage[{index}] (L) round delivered exceeds round allocated"
                )
            tol_so = accounting.tolerance_for(
                source_outflow_l, source_eligible_before_l
            )
            if bool(np.any(source_outflow_l < -1e-9)):
                _reject(f"stage[{index}] (L) source_outflow is negative")
            if bool(np.any(source_outflow_l > source_eligible_before_l + tol_so)):
                _reject(
                    f"stage[{index}] (L) source_outflow exceeds source_eligible_before"
                )
            tol_nn = accounting.tolerance_for(
                np.zeros_like(source_outflow_l), source_outflow_l
            )
            if bool(np.any(source_outflow_l < -1e-9 + tol_nn)):
                _reject(f"stage[{index}] (L) source_outflow is negative")

            # Envelope monotonicity.
            tol_org = accounting.tolerance_for(
                np.zeros_like(org_cash_after), org_cash_after
            )
            if bool(np.any(org_cash_after > org_cash_before + tol_org)):
                _reject(
                    f"stage[{index}] (L) org_cash_envelope_after exceeds before"
                )
            tol_plot = accounting.tolerance_for(
                np.zeros_like(plot_pool_after), plot_pool_after
            )
            if bool(np.any(plot_pool_after > plot_pool_before + tol_plot)):
                _reject(
                    f"stage[{index}] (L) plot_pool_envelope_after exceeds before"
                )
            tol_bank = accounting.tolerance_for(
                np.zeros_like(bank_outflow_after), bank_outflow_after
            )
            if bool(np.any(bank_outflow_after > bank_outflow_before + tol_bank)):
                _reject(
                    f"stage[{index}] (L) bank_outflow_after exceeds before"
                )
            if treasury_after > treasury_before + 1e-9:
                _reject(
                    f"stage[{index}] (L) treasury_after {treasury_after:.6f} "
                    f"exceeds before {treasury_before:.6f}"
                )
            tol_handling = accounting.tolerance_for(
                np.zeros_like(handling_after), handling_after
            )
            if bool(np.any(handling_after > handling_before + tol_handling)):
                _reject(
                    f"stage[{index}] (L) handling_after exceeds handling_before"
                )
            tol_logistics = accounting.tolerance_for(
                np.zeros_like(logistics_pool_after), logistics_pool_after
            )
            if bool(
                np.any(logistics_pool_after > logistics_pool_before + tol_logistics)
            ):
                _reject(
                    f"stage[{index}] (L) logistics_pool_after exceeds before"
                )

            # Round caps vs the per-round tranche (initial / n) and the
            # remaining cumulative pool.
            expected_rounds = max(int(expected_n), 1)
            logistics_tranche = (
                frozen_logistics_pool / float(expected_rounds)
            )
            handling_tranche = (
                frozen_handling_capacity / float(expected_rounds)
            )
            tol_cap = accounting.tolerance_for(
                logistics_round_cap, logistics_tranche
            )
            if bool(np.any(logistics_round_cap > logistics_tranche + tol_cap)):
                _reject(
                    f"stage[{index}] (L) logistics_round_cap exceeds the "
                    f"initial/{expected_rounds} tranche"
                )
            if bool(np.any(logistics_round_cap > logistics_pool_before + tol_cap)):
                _reject(
                    f"stage[{index}] (L) logistics_round_cap exceeds "
                    f"logistics_pool_before"
                )
            tol_cap2 = accounting.tolerance_for(
                handling_round_cap, handling_tranche
            )
            if bool(np.any(handling_round_cap > handling_tranche + tol_cap2)):
                _reject(
                    f"stage[{index}] (L) handling_round_cap exceeds the "
                    f"initial/{expected_rounds} tranche"
                )
            if bool(np.any(handling_round_cap > handling_before + tol_cap2)):
                _reject(
                    f"stage[{index}] (L) handling_round_cap exceeds handling_before"
                )
            if expected_rounds == 1:
                # A single P->L round gets the whole quarterly pool.
                _require_close(
                    f"stage[{index}] (L) logistics_round_cap must equal the "
                    f"initial pool when n=1",
                    logistics_round_cap,
                    frozen_logistics_pool,
                )
                _require_close(
                    f"stage[{index}] (L) handling_round_cap must equal the "
                    f"initial capacity when n=1",
                    handling_round_cap,
                    frozen_handling_capacity,
                )

            # Spend can never exceed the round's cap.
            tol_log_spend = accounting.tolerance_for(
                logistics_spend, logistics_round_cap
            )
            if bool(np.any(logistics_spend > logistics_round_cap + tol_log_spend)):
                _reject(
                    f"stage[{index}] (L) logistics_spend exceeds the round cap"
                )
            tol_hand_spend = accounting.tolerance_for(
                handling_spend, handling_round_cap
            )
            if bool(np.any(handling_spend > handling_round_cap + tol_hand_spend)):
                _reject(
                    f"stage[{index}] (L) handling_spend exceeds the round cap"
                )

            # L source/destination identity: only the retail-owned cells may
            # credit this quarter's receipts back to the L source pool.
            expected_source_after = (
                source_eligible_before_l
                - source_outflow_l
                + np.where(
                    retail_source_mask, destination_credit_l, 0.0
                )
            )
            _require_close(
                f"stage[{index}] (L) source_eligible_after diverges from "
                f"before - source_outflow + retail destination credit",
                source_eligible_after_l,
                expected_source_after,
            )
            _require_close(
                f"stage[{index}] (L) stock_before diverges from the previous "
                f"stage's stock_after",
                stock_before_l,
                expected_stock,
            )
            _require_close(
                f"stage[{index}] (L) stock_after - stock_before diverges "
                f"from -source_outflow + destination_credit",
                stock_after_l - stock_before_l,
                -source_outflow_l + destination_credit_l,
            )
            expected_stock = audit_stock_after

            # Bind the round's ordered tranche to the frozen quarterly
            # authority, reconstructing the cumulative allocation from the
            # preceding L rounds.
            # Household demand is settled by the later household step, so
            # its quarterly ``flows.ordered`` row is overwritten after the L
            # rounds; every other demand row remains the staged authority.
            _require_close(
                f"stage[{index}] (L) round_ordered diverges from "
                f"min(flows.ordered / n, flows.ordered - cumulative allocated)",
                round_ordered_l[non_household_demand],
                np.minimum(
                    ordered / float(max(expected_n, 1)),
                    ordered - cumulative_allocated_l,
                )[non_household_demand],
            )
            cumulative_allocated_l = (
                cumulative_allocated_l + round_allocated_l
            )

            # --- per-edge binding -------------------------------------
            # The edge arrays are the round's real pre-aggregation arrays.
            # Recompute every source/destination quantity and the logistics
            # spend from them, and require the demand-axis aggregates to be
            # their exact bincounts.
            if bool(
                np.any(
                    edge_delivered_l
                    > edge_allocated_l
                    + accounting.tolerance_for(
                        edge_delivered_l, edge_allocated_l
                    )
                )
            ):
                _reject(
                    f"stage[{index}] (L) edge_delivered exceeds "
                    f"edge_allocated"
                )
            _require_close(
                f"stage[{index}] (L) round allocated diverges from "
                f"bincount(edge_demand, edge_allocated)",
                round_allocated_l,
                np.bincount(
                    np.asarray(network.edge_demand, dtype=np.int64),
                    weights=edge_allocated_l,
                    minlength=d_count,
                ),
            )
            _require_close(
                f"stage[{index}] (L) round delivered diverges from "
                f"bincount(edge_demand, edge_delivered)",
                round_delivered_l,
                np.bincount(
                    np.asarray(network.edge_demand, dtype=np.int64),
                    weights=edge_delivered_l,
                    minlength=d_count,
                ),
            )
            _require_close(
                f"stage[{index}] (L) edge_service_used diverges from "
                f"edge_delivered * edge_transport_per_unit",
                edge_service_used_l,
                edge_delivered_l * edge_per_unit_arr,
            )
            _require_close(
                f"stage[{index}] (L) source_outflow diverges from "
                f"bincount(edge_source_cell, edge_delivered)",
                source_outflow_l,
                np.bincount(
                    edge_source_arr,
                    weights=edge_delivered_l,
                    minlength=cell_count,
                ),
            )
            _require_close(
                f"stage[{index}] (L) destination_credit diverges from "
                f"bincount(edge_destination_cell, edge_delivered)",
                destination_credit_l,
                np.bincount(
                    edge_destination_arr[edge_valid_destination],
                    weights=edge_delivered_l[edge_valid_destination],
                    minlength=cell_count,
                ),
            )
            _require_close(
                f"stage[{index}] (L) logistics_spend diverges from "
                f"bincount(edge_transport_org, edge_service_used) on "
                f"non-self-hauled edges",
                logistics_spend,
                np.bincount(
                    edge_transport_org_arr[edge_needs_transport],
                    weights=edge_service_used_l[edge_needs_transport],
                    minlength=org_count,
                ),
            )
            handling_work = edge_delivered_l * handling_unit_work[
                edge_commodity_arr
            ]
            expected_handling_spend = np.bincount(
                source_edge_owner[wholesale_edge_mask],
                weights=handling_work[wholesale_edge_mask],
                minlength=org_count,
            ) + np.bincount(
                destination_edge_owner[retail_edge_mask],
                weights=handling_work[retail_edge_mask],
                minlength=org_count,
            )
            _require_close(
                f"stage[{index}] (L) handling_spend diverges from "
                f"wholesale-source plus retail-destination handling work "
                f"on edge_delivered",
                handling_spend,
                expected_handling_spend,
            )

            sum_edge_allocated_L = sum_edge_allocated_L + edge_allocated_l
            sum_edge_delivered_L = sum_edge_delivered_L + edge_delivered_l
            sum_edge_service_used_L = (
                sum_edge_service_used_L + edge_service_used_l
            )
            sum_edge_service_fee_L = (
                sum_edge_service_fee_L + edge_service_fee_l
            )

            # Per-envelope spend reconciliation.
            tol_p = accounting.tolerance_for(
                org_cash_before - org_cash_after, org_purchases
            )
            org_spend_delta = org_cash_before - org_cash_after
            if bool(
                np.any(
                    np.abs(org_spend_delta - org_purchases) > tol_p
                )
            ):
                _reject(
                    f"stage[{index}] (L) org envelope before-after does not "
                    f"equal per-org purchases"
                )
            tol_p2 = accounting.tolerance_for(
                plot_pool_before - plot_pool_after, plot_pool_spend
            )
            plot_delta = plot_pool_before - plot_pool_after
            if bool(
                np.any(
                    np.abs(plot_delta - plot_pool_spend) > tol_p2
                )
            ):
                _reject(
                    f"stage[{index}] (L) plot envelope before-after does "
                    f"not equal plot_pool_spend"
                )
            tol_b = accounting.tolerance_for(
                bank_outflow_before - bank_outflow_after, bank_outflow_spend
            )
            bank_delta = bank_outflow_before - bank_outflow_after
            if bool(
                np.any(
                    np.abs(bank_delta - bank_outflow_spend) > tol_b
                )
            ):
                _reject(
                    f"stage[{index}] (L) bank envelope before-after does "
                    f"not equal bank_outflow_spend"
                )
            if abs(
                (treasury_before - treasury_after) - treasury_spend
            ) > max(1e-9, 1e-9 * max(abs(treasury_before), abs(treasury_after))):
                _reject(
                    f"stage[{index}] (L) treasury before-after does not "
                    f"equal treasury_spend"
                )
            tol_l = accounting.tolerance_for(
                logistics_pool_before - logistics_pool_after, logistics_spend
            )
            log_delta = logistics_pool_before - logistics_pool_after
            if bool(
                np.any(
                    np.abs(log_delta - logistics_spend) > tol_l
                )
            ):
                _reject(
                    f"stage[{index}] (L) logistics before-after does not "
                    f"equal logistics_spend"
                )
            tol_h = accounting.tolerance_for(
                handling_before - handling_after, handling_spend
            )
            hand_delta = handling_before - handling_after
            if bool(
                np.any(
                    np.abs(hand_delta - handling_spend) > tol_h
                )
            ):
                _reject(
                    f"stage[{index}] (L) handling before-after does not "
                    f"equal handling_spend"
                )

            # --- real cash/bank state evidence -------------------------
            # The L-round state snapshot must be the exact post-payment
            # organization cash; it starts from the frozen prelude cash for
            # the first L and from the previous L's closing state thereafter.
            expected_cash_start = (
                frozen_org_cash
                if previous_state_cash is None
                else previous_state_cash
            )
            _require_close(
                f"stage[{index}] (L) state_cash_after diverges from the "
                f"previous state cash plus sales minus purchases",
                state_cash_after,
                expected_cash_start + org_sales - org_purchases,
            )
            # Independent audit walk: every L starts from the previous real
            # snapshot (or the frozen prelude balance) and its bank snapshot
            # must equal that start plus the round's real interbank delta.
            # An arbitrary +1e6 on the snapshot (even mirrored in the trace)
            # cannot satisfy this identity.  P stages above assert that cash
            # and reserves are unchanged, so the walk covers the full quarter.
            _require_close(
                f"kernel audit stage[{index}] (L) cash diverges from the "
                f"previous audited balance plus sales minus purchases",
                audit_cash_after,
                expected_cash_state + org_sales - org_purchases,
            )
            audit_bank_delta = _audit_array(
                index, audit_stage, "bank_delta", bank_count
            )
            _require_close(
                f"kernel audit stage[{index}] (L) bank reserves diverge from "
                f"the previous audited balance plus the real bank delta",
                audit_bank_after,
                expected_bank_state + audit_bank_delta,
            )
            expected_cash_state = audit_cash_after
            expected_bank_state = audit_bank_after
            if previous_state_cash is not None:
                tol_cash_state = accounting.tolerance_for(
                    org_cash_before, previous_state_cash
                )
                if bool(
                    np.any(
                        org_cash_before > previous_state_cash + tol_cash_state
                    )
                ):
                    _reject(
                        f"stage[{index}] (L) org_cash_envelope_before exceeds "
                        f"the real organization cash at the L boundary"
                    )
                tol_bank_state = accounting.tolerance_for(
                    bank_outflow_before, previous_state_bank
                )
                if bool(
                    np.any(
                        bank_outflow_before
                        > previous_state_bank + tol_bank_state
                    )
                ):
                    _reject(
                        f"stage[{index}] (L) bank_outflow_before exceeds the "
                        f"real bank reserves at the L boundary"
                    )
            tol_cash_close = accounting.tolerance_for(
                state_cash_after, org_cash_after
            )
            if bool(
                np.any(state_cash_after + tol_cash_close < org_cash_after)
            ):
                _reject(
                    f"stage[{index}] (L) org_cash_envelope_after exceeds the "
                    f"real organization cash after the L"
                )
            tol_bank_close = accounting.tolerance_for(
                state_bank_reserves_after, bank_outflow_after
            )
            if bool(
                np.any(
                    state_bank_reserves_after + tol_bank_close
                    < bank_outflow_after
                )
            ):
                _reject(
                    f"stage[{index}] (L) bank_outflow_after exceeds the real "
                    f"bank reserves after the L"
                )
            previous_state_cash = state_cash_after
            previous_state_bank = state_bank_reserves_after

            sum_alloc_L = sum_alloc_L + round_allocated_l
            sum_delivered_L = sum_delivered_L + round_delivered_l
            sum_purchases = sum_purchases + org_purchases
            sum_sales = sum_sales + org_sales
            previous_l_after = dict(envelope_after)
            previous_treasury_after = treasury_after
        else:
            _reject(f"stage[{index}] has unknown kind {kind!r}")

    # --- aggregate reconciliation against flows --------------------------
    flows_delivered = np.asarray(flows.delivered, dtype=np.float64)
    flows_allocated = np.asarray(flows.allocated, dtype=np.float64)
    flows_purchases = np.asarray(flows.organization_purchases, dtype=np.float64)
    flows_sales_arr = np.asarray(
        flows.organization_sales_receipts, dtype=np.float64
    )
    flows_activity_realized = np.asarray(
        flows.activity_realized, dtype=np.float64
    )
    flows_used = np.asarray(flows.used, dtype=np.float64)
    flows_edge_allocated = np.asarray(
        flows.edge_allocated, dtype=np.float64
    )
    flows_edge_delivered = np.asarray(
        flows.edge_delivered, dtype=np.float64
    )
    flows_edge_service_used = np.asarray(
        flows.edge_service_used, dtype=np.float64
    )
    flows_edge_service_fee = np.asarray(
        flows.edge_service_fee, dtype=np.float64
    )

    # The per-L edge arrays must sum to the authoritative quarterly edge
    # flow vectors; this binds every stage round to the real deliveries and
    # spend rather than accepting internally consistent fabricated traces.
    _require_close(
        "sum of stage edge_allocated diverges from flows.edge_allocated on "
        "non-household edges",
        sum_edge_allocated_L[non_household_edge_mask],
        flows_edge_allocated[non_household_edge_mask],
    )
    _require_close(
        "sum of stage edge_delivered diverges from flows.edge_delivered on "
        "non-household edges",
        sum_edge_delivered_L[non_household_edge_mask],
        flows_edge_delivered[non_household_edge_mask],
    )
    _require_close(
        "sum of stage edge_service_used diverges from "
        "flows.edge_service_used on non-household edges",
        sum_edge_service_used_L[non_household_edge_mask],
        flows_edge_service_used[non_household_edge_mask],
    )
    _require_close(
        "sum of stage edge_service_fee diverges from "
        "flows.edge_service_fee on non-household edges",
        sum_edge_service_fee_L[non_household_edge_mask],
        flows_edge_service_fee[non_household_edge_mask],
    )

    # Cumulative L allocated / delivered must equal flows.allocated /
    # flows.delivered on non-household demand rows (household demand is
    # settled later by the household step).
    if bool(non_household_demand.any()):
        sum_alloc_nh = sum_alloc_L[non_household_demand]
        flows_alloc_nh = flows_allocated[non_household_demand]
        tol = accounting.tolerance_for(sum_alloc_nh, flows_alloc_nh)
        if bool(np.any(np.abs(sum_alloc_nh - flows_alloc_nh) > tol)):
            _reject(
                "sum of stage allocated diverges from flows.allocated on "
                "non-household demand cells"
            )
        sum_delivered_nh = sum_delivered_L[non_household_demand]
        flows_delivered_nh = flows_delivered[non_household_demand]
        tol = accounting.tolerance_for(sum_delivered_nh, flows_delivered_nh)
        if bool(np.any(np.abs(sum_delivered_nh - flows_delivered_nh) > tol)):
            _reject(
                "sum of stage delivered diverges from flows.delivered on "
                "non-household demand cells"
            )

    # Cumulative P realized must match flows.activity_realized on
    # non-early-service activities (early-service entries are written by the
    # transport prelude rather than the staged P rounds).
    if bool(non_early_activities.any()):
        tol = accounting.tolerance_for(
            sum_realized_P[non_early_activities],
            flows_activity_realized[non_early_activities],
        )
        if bool(
            np.any(
                np.abs(
                    sum_realized_P[non_early_activities]
                    - flows_activity_realized[non_early_activities]
                )
                > tol
            )
        ):
            _reject(
                "sum of P activity_realized diverges from "
                "flows.activity_realized on non-early-service rows"
            )

    if bool(non_early_input_rows.any()):
        tol = accounting.tolerance_for(
            sum_used_P[non_early_input_rows],
            flows_used[:k_count][non_early_input_rows],
        )
        if bool(
            np.any(
                np.abs(
                    sum_used_P[non_early_input_rows]
                    - flows_used[:k_count][non_early_input_rows]
                )
                > tol
            )
        ):
            _reject(
                "sum of P used diverges from flows.used[:K] on "
                "non-early-service input rows"
            )

    # Cumulative purchases must equal flows.organization_purchases; sales
    # receipts may be supplemented by household step receipts so the gate
    # permits flows >= sum_sales but rejects a negative per-org gap.
    if bool(
        np.any(
            np.abs(sum_purchases - flows_purchases)
            > 1e-6 + 1e-7 * np.maximum(np.abs(sum_purchases), np.abs(flows_purchases))
        )
    ):
        _reject(
            "sum of stage purchases diverges from flows.organization_purchases"
        )
    if bool(np.any(flows_sales_arr + 1e-6 < sum_sales)):
        _reject(
            "sum of stage sales exceeds flows.organization_sales_receipts"
        )


def execute_lead_time_tick(
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: Any,
    network: MaterialNetwork,
    *,
    spec: LeadTimeSpec,
    controls: Any = None,
) -> LeadTimeResult:
    """Run one H3D tick under ``spec`` and advance only on a full pass.

    Validation happens before any state mutation.  The single real tick is
    admitted only if the existing material/financial gate and the staged trace
    check both pass.  On any later failure, the failed flows/trace are copied
    for review, every mutable state field is restored, the clock is not
    advanced, and :class:`LeadTimeFailure` is raised.
    """
    if not isinstance(spec, LeadTimeSpec):
        _reject(f"spec must be LeadTimeSpec, got {type(spec).__name__}")
    if spec.schema_version != SCHEMA_VERSION:
        _reject(f"schema_version {spec.schema_version!r} != {SCHEMA_VERSION!r}")
    if spec.source_kind != SOURCE_KIND:
        _reject(f"source_kind {spec.source_kind!r} != {SOURCE_KIND!r}")
    _validate_spec_clock(state, forcing, parameters)
    before = copy.deepcopy(state)
    opening: MaterialStockSnapshot = capture_material_stocks(state)
    # The trace and the independent audit must both be empty at tick entry;
    # the kernel populates them.  The audit is internal (never returned).
    trace: dict[str, Any] = {}
    audit: dict[str, Any] = {}
    phase_times: dict[str, float] = {}
    flows: MaterialTickFlows | None = None
    stage_count = spec.stage_count
    phase = "tick"
    try:
        if stage_count is None:
            flows = tick_material(
                state,
                forcing,
                parameters,
                network,
                controls=controls,
                phase_times=phase_times,
            )
        else:
            flows = tick_material(
                state,
                forcing,
                parameters,
                network,
                controls=controls,
                phase_times=phase_times,
                micro_stage_count=stage_count,
                micro_stage_trace=trace,
                micro_stage_audit=audit,
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
        phase = "trace"
        if stage_count is not None:
            _verify_trace(
                spec=spec,
                state=state,
                network=network,
                parameters=parameters,
                flows=flows,
                trace=trace,
                audit=audit,
            )
    except Exception as exc:  # noqa: BLE001 - every failure must roll back
        failed_flows = copy.deepcopy(flows) if flows is not None else None
        failed_trace = _copy_trace(trace)
        _restore_state(state, before)
        raise LeadTimeFailure(
            phase=phase,
            cause=exc,
            failed_flows=failed_flows,
            failed_trace=failed_trace,
        ) from exc

    state.completed_ticks = int(state.completed_ticks) + 1
    return LeadTimeResult(
        spec=spec,
        flows=flows,
        gate=summary,
        trace=trace,
        phase_times=phase_times,
    )


__all__ = [
    "ADAPTER_SCHEMA_VERSION",
    "GATE_PREFIX",
    "LeadTimeFailure",
    "LeadTimeResult",
    "LeadTimeSpec",
    "SCHEMA_VERSION",
    "SOURCE_KIND",
    "execute_lead_time_tick",
    "load_lead_time_spec",
]