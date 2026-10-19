"""H3E: four-quarter rolling plans with explicit capital and funding timing.

``plan_quarter`` solves the same four-layer lexicographic model for the two
optimization arms and computes the frozen historical rule without a solver.
The model keeps the legacy kernel's timing:

* opening inventory is the only source a quarter may route;
* ordinary output produced in a quarter enters next quarter's opening stock;
* services are produced and used or lost inside the same quarter;
* purchases and freight need available funding before same-quarter receipts.

The module never reads state, advances a tick, opens a target or runs a kernel.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, csr_matrix

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.engine.accounting import ATOL, tolerance_for
from hsm_lab.institutions.decisions import (
    ActorRole,
    ProcurementChoiceKind,
    ProcurementDecision,
)
from hsm_lab.planning.proposals import (
    ARMS,
    HORIZON_QUARTERS,
    PRIORITY,
    SCHEMA_VERSION,
    PlanningInputs,
)

GATE_PREFIX = "HIST_H3E_ROLLING"
EQUALS = 0
AT_MOST = 1
AT_LEAST = 2

PLAN_STATUSES = ("FEASIBLE", "INFEASIBLE", "TIMEOUT", "ERROR", "RULE")


def _reject(message: str) -> None:
    raise ResearchGateError(f"{GATE_PREFIX}: {message}")


def _array_digest(array: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(repr(tuple(array.shape)).encode("ascii"))
    digest.update(np.ascontiguousarray(array, dtype=np.float64).tobytes())
    return digest.hexdigest()


class _Rows:
    """Sparse row collection shared by every lexicographic layer."""

    def __init__(self) -> None:
        self.names: list[str] = []
        self.senses: list[int] = []
        self.rhs: list[float] = []
        self.cols: list[np.ndarray] = []
        self.vals: list[np.ndarray] = []

    def add(
        self,
        name: str,
        columns: Any,
        values: Any,
        rhs: float,
        sense: int,
    ) -> None:
        columns = np.asarray(columns, dtype=np.int64)
        values = np.asarray(values, dtype=np.float64)
        if columns.shape != values.shape:
            raise ValueError(f"row {name} columns/values disagree")
        if not math.isfinite(float(rhs)):
            raise ValueError(f"row {name} has non-finite rhs")
        self.names.append(name)
        self.senses.append(int(sense))
        self.rhs.append(float(rhs))
        self.cols.append(columns)
        self.vals.append(values)

    def add_le(self, name: str, columns: Any, values: Any, rhs: float) -> None:
        self.add(name, columns, values, rhs, AT_MOST)

    def matrices(
        self, variable_count: int
    ) -> tuple[csr_matrix, np.ndarray, csr_matrix, np.ndarray]:
        row_count = len(self.names)
        if row_count == 0:
            empty = csr_matrix((0, variable_count), dtype=np.float64)
            return empty, np.zeros(0), empty, np.zeros(0)
        cols = np.concatenate(self.cols)
        vals = np.concatenate(self.vals)
        rows = np.repeat(np.arange(row_count, dtype=np.int64), [c.size for c in self.cols])
        matrix = coo_matrix((vals, (rows, cols)), shape=(row_count, variable_count)).tocsr()
        sense = np.asarray(self.senses, dtype=np.int64)
        eq = sense == EQUALS
        le = sense == AT_MOST
        ge = sense == AT_LEAST
        a_eq = matrix[np.flatnonzero(eq)] if bool(np.any(eq)) else csr_matrix((0, variable_count))
        b_eq = np.asarray(self.rhs, dtype=np.float64)[eq] if bool(np.any(eq)) else np.zeros(0)
        ub_parts = []
        ub_rhs = []
        if bool(np.any(le)):
            ub_parts.append(matrix[np.flatnonzero(le)])
            ub_rhs.append(np.asarray(self.rhs, dtype=np.float64)[le])
        if bool(np.any(ge)):
            ub_parts.append(-matrix[np.flatnonzero(ge)])
            ub_rhs.append(-np.asarray(self.rhs, dtype=np.float64)[ge])
        if ub_parts:
            a_ub = _vstack(ub_parts)
            b_ub = np.concatenate(ub_rhs)
        else:
            a_ub = csr_matrix((0, variable_count), dtype=np.float64)
            b_ub = np.zeros(0)
        return a_eq, b_eq, a_ub, b_ub

    def witness(self, vector: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        activity = np.zeros(len(self.names), dtype=np.float64)
        for index, (columns, values) in enumerate(zip(self.cols, self.vals, strict=True)):
            if columns.size:
                activity[index] = float(np.dot(values, vector[columns]))
        rhs = np.asarray(self.rhs, dtype=np.float64)
        sense = np.asarray(self.senses, dtype=np.int64)
        residual = np.where(
            sense == EQUALS,
            np.abs(activity - rhs),
            np.where(
                sense == AT_MOST, np.maximum(activity - rhs, 0.0), np.maximum(rhs - activity, 0.0)
            ),
        )
        slack = np.where(sense == EQUALS, 0.0, np.maximum(rhs - activity, 0.0))
        return activity, residual, slack

    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        for name, sense, rhs, columns, values in zip(
            self.names, self.senses, self.rhs, self.cols, self.vals, strict=True
        ):
            digest.update(name.encode("utf-8"))
            digest.update(str(int(sense)).encode("ascii"))
            digest.update(repr(float(rhs)).encode("ascii"))
            digest.update(columns.astype(np.int64).tobytes())
            digest.update(values.astype(np.float64).tobytes())
        return digest.hexdigest()


def _vstack(parts: list[csr_matrix]) -> csr_matrix:
    from scipy.sparse import vstack

    return vstack(parts, format="csr")


# ---------------------------------------------------------------------------
# Public result containers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanningCertificate:
    """Solver- or rule-produced evidence for one planning decision."""

    schema_version: str
    status: str
    solver_status: int
    solver_message: str
    solver_feasible: bool
    matrix_rows: int
    matrix_cols: int
    nnz: int
    row_names: tuple[str, ...]
    row_sense: np.ndarray
    row_rhs: np.ndarray
    primal: np.ndarray
    dual_eq: np.ndarray
    dual_ub: np.ndarray
    row_activity: np.ndarray
    row_residual: np.ndarray
    row_slack: np.ndarray
    layer_index: int
    layer_objective: float
    wall_s: float
    input_hash: str
    constraint_hash: str
    failure_reason: str

    def __post_init__(self) -> None:
        for name in (
            "row_sense",
            "row_rhs",
            "primal",
            "dual_eq",
            "dual_ub",
            "row_activity",
            "row_residual",
            "row_slack",
        ):
            array = np.ascontiguousarray(getattr(self, name))
            object.__setattr__(
                self,
                name,
                np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape),
            )

    def digest(self) -> str:
        digest = hashlib.sha256()
        for value in (
            self.schema_version,
            self.status,
            str(self.solver_status),
            self.solver_message,
            str(self.solver_feasible),
            str(self.matrix_rows),
            str(self.matrix_cols),
            str(self.nnz),
            str(self.layer_index),
            repr(float(self.layer_objective)),
            repr(float(self.wall_s)),
            self.input_hash,
            self.constraint_hash,
            self.failure_reason,
        ):
            digest.update(value.encode("utf-8"))
        for array in (
            self.row_sense,
            self.row_rhs,
            self.primal,
            self.dual_eq,
            self.dual_ub,
            self.row_activity,
            self.row_residual,
            self.row_slack,
        ):
            digest.update(_array_digest(np.asarray(array, dtype=np.float64)).encode("ascii"))
        digest.update(repr(self.row_names).encode("utf-8"))
        return digest.hexdigest()


@dataclass(frozen=True)
class QuarterPlan:
    """Forecast and realised planning quantities for one quarter offset."""

    offset: int
    quarter: str
    active: bool
    purchases: np.ndarray
    inventory: np.ndarray
    cash: np.ndarray
    final_use: np.ndarray
    shortfall: np.ndarray
    service_produced: np.ndarray
    service_used: np.ndarray
    service_lost: np.ndarray
    service_produced_by_good: np.ndarray
    service_used_by_good: np.ndarray
    service_lost_by_good: np.ndarray
    financing: np.ndarray
    bank_cash: np.ndarray
    goods_payment: np.ndarray
    freight_payment: np.ndarray
    objective_layers: tuple[float, ...]
    certificate_index: int


@dataclass(frozen=True)
class RollingPlan:
    """One mode's complete four-quarter rolling plan and first-quarter action."""

    schema_version: str
    mode: str
    status: str
    decision_quarter: str
    horizon_quarters: int
    quarters: tuple[str, ...]
    terminal_mask: tuple[bool, ...]
    source_kind: str
    inputs: PlanningInputs
    input_hash: str
    observation_hash: str
    priority_hash: str
    forecast_hash: str
    matrix_hash: str
    comparison_status: str
    comparison_reason: str
    certificates: tuple[PlanningCertificate, ...]
    quarterly: tuple[QuarterPlan, ...]
    first_quarter_decisions: tuple[ProcurementDecision, ...]
    first_quarter_payload_hash: str
    objective_layers: tuple[float, ...]
    plan_hash: str = ""

    def __post_init__(self) -> None:
        if type(self.plan_hash) is not str:
            raise TypeError("plan_hash must be a string")
        if not self.plan_hash:
            object.__setattr__(self, "plan_hash", self.digest())

    def digest(self) -> str:
        digest = hashlib.sha256()
        digest.update(self.schema_version.encode("utf-8"))
        digest.update(self.mode.encode("utf-8"))
        digest.update(self.decision_quarter.encode("utf-8"))
        digest.update(self.input_hash.encode("ascii"))
        digest.update(self.observation_hash.encode("ascii"))
        digest.update(self.priority_hash.encode("ascii"))
        digest.update(self.forecast_hash.encode("ascii"))
        digest.update(self.matrix_hash.encode("ascii"))
        digest.update(self.first_quarter_payload_hash.encode("ascii"))
        digest.update(self.status.encode("ascii"))
        digest.update(str(len(self.certificates)).encode("ascii"))
        for certificate in self.certificates:
            digest.update(certificate.digest().encode("ascii"))
        # Future quarters are diagnostic forecasts; mutation there must not
        # alter the first-quarter executable payload.
        for item in self.quarterly[:1]:
            for array in (
                item.purchases,
                item.inventory,
                item.cash,
                item.final_use,
                item.shortfall,
                item.service_produced,
                item.service_used,
                item.service_lost,
            ):
                digest.update(_array_digest(np.asarray(array, dtype=np.float64)).encode("ascii"))
        return digest.hexdigest()


def derive_first_quarter_decisions(
    plan: RollingPlan,
) -> tuple[ProcurementDecision, ...]:
    if type(plan) is not RollingPlan:
        raise TypeError("plan must be a concrete RollingPlan")
    return _make_decisions(plan.inputs, plan.quarterly[0].purchases, mode=plan.mode)


def _same_decisions(
    left: tuple[ProcurementDecision, ...],
    right: tuple[ProcurementDecision, ...],
) -> bool:
    left_map = {
        (item.organization_id, item.commodity_id): float(item.requested_quantity) for item in left
    }
    right_map = {
        (item.organization_id, item.commodity_id): float(item.requested_quantity) for item in right
    }
    if set(left_map) != set(right_map):
        return False
    return all(
        abs(left_map[key] - right_map[key]) <= float(tolerance_for(left_map[key], right_map[key]))
        for key in left_map
    )


def verify_plan_certificates(plan: RollingPlan) -> tuple[bool, str]:
    """Reconstruct the frozen LP and verify each lex witness independently."""
    if type(plan) is not RollingPlan:
        return False, "plan is not a concrete RollingPlan"
    if plan.mode == "historical_rule_based":
        certificate = plan.certificates[0] if plan.certificates else None
        if certificate is None:
            return False, "reference plan has no certificate"
        if not np.isfinite(float(certificate.layer_objective)) or not np.isfinite(
            float(certificate.wall_s)
        ):
            return False, "reference certificate carries a non-finite scalar"
        if certificate.solver_status != -1 or not certificate.solver_feasible:
            return False, "reference certificate claims solver completion"
        if certificate.row_activity.size and bool(np.any(certificate.row_activity > ATOL)):
            return False, "reference certificate has a positive residual"
        reconstructed = _rule_plan_v2(plan.inputs, time_limit_s=60.0)
        if reconstructed.status != plan.status:
            return False, "reference status does not match a fresh simulation"
        if not np.allclose(
            reconstructed.quarterly[0].purchases,
            plan.quarterly[0].purchases,
            atol=1e-7,
            rtol=0.0,
        ):
            return False, "reference purchases do not match a fresh simulation"
        if not np.allclose(
            reconstructed.quarterly[0].cash,
            plan.quarterly[0].cash,
            atol=1e-7,
            rtol=0.0,
        ):
            return False, "reference cash does not match a fresh simulation"
        fresh = reconstructed.certificates[0]
        if (
            certificate.constraint_hash != fresh.constraint_hash
            or certificate.layer_index != fresh.layer_index
            or certificate.matrix_rows != fresh.matrix_rows
            or certificate.matrix_cols != fresh.matrix_cols
            or certificate.nnz != fresh.nnz
            or not np.array_equal(certificate.row_sense, fresh.row_sense)
            or not np.allclose(certificate.row_rhs, fresh.row_rhs, atol=1e-7, rtol=0.0)
            or not np.allclose(certificate.row_activity, fresh.row_activity, atol=1e-7, rtol=0.0)
            or not np.allclose(certificate.row_residual, fresh.row_residual, atol=1e-7, rtol=0.0)
            or not np.allclose(certificate.row_slack, fresh.row_slack, atol=1e-7, rtol=0.0)
            or abs(certificate.layer_objective - fresh.layer_objective) > 1e-7
            or tuple(certificate.row_names) != tuple(fresh.row_names)
        ):
            return False, "reference checks do not match a fresh simulation"
        if not _same_decisions(
            plan.first_quarter_decisions,
            reconstructed.first_quarter_decisions,
        ):
            return False, "reference requests do not match a fresh simulation"
        return True, ""
    inputs = plan.inputs
    axis = _Axis(inputs)
    base_rows = _build_base_rows(axis)
    objectives, constants, _ = _objective_layers(axis)
    bounds = _bounds(axis)
    rows = _Rows()
    for index in range(len(base_rows.names)):
        rows.add(
            base_rows.names[index],
            base_rows.cols[index],
            base_rows.vals[index],
            base_rows.rhs[index],
            base_rows.senses[index],
        )
    for layer, certificate in enumerate(plan.certificates):
        a_eq, b_eq, a_ub, b_ub = rows.matrices(axis.variable_count)
        vector = np.asarray(certificate.primal, dtype=np.float64)
        if vector.shape != (axis.variable_count,):
            return False, f"layer {layer} primal axis mismatch"
        if not bool(np.all(np.isfinite(vector))):
            return False, f"layer {layer} primal is non-finite"
        if certificate.solver_status != 0 or not certificate.solver_feasible:
            return False, f"layer {layer} certificate does not claim solver success"
        if certificate.constraint_hash != rows.fingerprint():
            return False, f"layer {layer} constraint hash does not match"
        if (
            certificate.matrix_rows != len(rows.names)
            or certificate.matrix_cols != axis.variable_count
            or tuple(certificate.row_names) != tuple(rows.names)
            or not bool(np.array_equal(certificate.row_sense, np.asarray(rows.senses)))
            or not bool(
                np.allclose(
                    certificate.row_rhs,
                    np.asarray(rows.rhs),
                    atol=ATOL,
                    rtol=0.0,
                )
            )
        ):
            return False, f"layer {layer} certificate metadata does not match"
        activity, residual, slack = rows.witness(vector)
        if not bool(
            np.allclose(certificate.row_activity, activity, atol=1e-7, rtol=0.0)
            and np.allclose(certificate.row_residual, residual, atol=1e-7, rtol=0.0)
            and np.allclose(certificate.row_slack, slack, atol=1e-7, rtol=0.0)
        ):
            return False, f"layer {layer} recorded residuals do not match"
        for position, (lower, upper) in enumerate(bounds):
            if float(vector[position]) < lower - ATOL:
                return False, f"layer {layer} violates a lower bound"
            if upper is not None and float(vector[position]) > upper + ATOL:
                return False, f"layer {layer} violates an upper bound"
        if a_eq.shape[0]:
            activity = np.asarray(a_eq @ vector).ravel()
            tolerance = np.asarray(tolerance_for(activity, b_eq), dtype=np.float64)
            if bool(np.any(np.abs(activity - b_eq) > tolerance)):
                return False, f"layer {layer} violates an equality row"
        if a_ub.shape[0]:
            activity = np.asarray(a_ub @ vector).ravel()
            tolerance = np.asarray(tolerance_for(activity, b_ub), dtype=np.float64)
            if bool(np.any(activity - b_ub > tolerance)):
                return False, f"layer {layer} violates an inequality row"
        layer_value = float(np.dot(objectives[layer], vector) + constants[layer])
        tolerance = float(tolerance_for(layer_value, certificate.layer_objective))
        if abs(layer_value - certificate.layer_objective) > tolerance:
            return False, f"layer {layer} objective does not match its witness"
        if layer < 3:
            rows.add_le(
                f"lex_lock[layer={layer}]",
                np.flatnonzero(objectives[layer] != 0.0),
                objectives[layer][np.flatnonzero(objectives[layer] != 0.0)],
                certificate.layer_objective - constants[layer] + tolerance,
            )
    final = np.asarray(plan.certificates[-1].primal, dtype=np.float64)
    flow = final[: HORIZON_QUARTERS * axis.e_count].reshape(HORIZON_QUARTERS, axis.e_count)
    first_purchases = np.zeros((axis.o_count, axis.g_count), dtype=np.float64)
    for edge in np.flatnonzero(flow[0] > ATOL):
        first_purchases[
            int(axis.declarations.edge_buyer[edge]),
            int(axis.declarations.edge_good[edge]),
        ] += float(flow[0, edge])
    derived = _make_decisions(inputs, first_purchases, mode=plan.mode)
    expected = {
        (decision.organization_id, decision.commodity_id): float(decision.requested_quantity)
        for decision in plan.first_quarter_decisions
    }
    actual = {
        (decision.organization_id, decision.commodity_id): float(decision.requested_quantity)
        for decision in derived
    }
    if set(expected) != set(actual):
        return False, "certificate witness does not produce the submitted requests"
    for key in expected:
        tolerance = float(tolerance_for(expected[key], actual[key]))
        if abs(expected[key] - actual[key]) > tolerance:
            return False, "certificate witness quantity does not match the payload"
    return True, ""


def _decision_payload_hash(decisions: tuple[ProcurementDecision, ...]) -> str:
    digest = hashlib.sha256()
    for decision in sorted(decisions, key=lambda item: item.decision_id):
        digest.update(decision.model_dump_json().encode("utf-8"))
    return digest.hexdigest()


def _make_decisions(
    inputs: PlanningInputs,
    purchases: np.ndarray,
    *,
    mode: str,
) -> tuple[ProcurementDecision, ...]:
    decisions: list[ProcurementDecision] = []
    budget_orgs = {item.organization_id for item in inputs.budget_observations}
    decision_orgs = set(inputs.declarations.decision_organization_ids)
    for org, label in enumerate(inputs.organization_ids):
        if label not in budget_orgs or label not in decision_orgs:
            continue
        by_commodity: dict[str, float] = {}
        for good, goods_id in enumerate(inputs.goods_id):
            quantity = float(purchases[org, good]) - float(
                inputs.baseline_procurement[0, org, good]
            )
            if quantity <= ATOL:
                continue
            commodity_id = goods_id.split("|", 1)[0]
            by_commodity[commodity_id] = by_commodity.get(commodity_id, 0.0) + quantity
        for commodity_id in sorted(by_commodity):
            quantity = by_commodity[commodity_id]
            if quantity <= ATOL:
                continue
            decision_id = (f"h3e-{mode}-{inputs.quarter}-{label}-{commodity_id}").replace(" ", "_")
            decisions.append(
                ProcurementDecision(
                    decision_id=decision_id,
                    actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
                    organization_id=label,
                    sector_id="industry",
                    quarter=inputs.quarter,
                    decision_at=inputs.decision_at,
                    available_at=max(item.observation.available_at for item in inputs.observations)
                    if inputs.observations
                    else inputs.decision_at,
                    kind=ProcurementChoiceKind.REQUEST,
                    commodity_id=commodity_id,
                    requested_quantity=float(quantity),
                )
            )
    return tuple(decisions)


# ---------------------------------------------------------------------------
# Model axes and variable indexing
# ---------------------------------------------------------------------------


class _Axis:
    def __init__(self, inputs: PlanningInputs) -> None:
        self.inputs = inputs
        self.declarations = inputs.declarations
        self.e_count = int(self.declarations.edge_id.shape[0])
        self.r_count = int(self.declarations.recipe_org.shape[0])
        self.o_count = len(inputs.organization_ids)
        self.g_count = len(inputs.goods_id)
        self.d_count = int(self.declarations.demand_buyer.shape[0])
        self.b_count = int(self.declarations.bank_count)
        self.final_indices = np.flatnonzero(self.declarations.demand_final)
        self.df_count = int(self.final_indices.size)
        self.flow_off = 0
        self.act_off = self.flow_off + HORIZON_QUARTERS * self.e_count
        self.inv_off = self.act_off + HORIZON_QUARTERS * self.r_count
        self.cash_off = self.inv_off + HORIZON_QUARTERS * self.o_count * self.g_count
        self.fin_off = self.cash_off + HORIZON_QUARTERS * self.o_count
        self.bank_off = self.fin_off + HORIZON_QUARTERS * self.o_count
        self.use_off = self.bank_off + HORIZON_QUARTERS * self.b_count
        self.short_off = self.use_off + HORIZON_QUARTERS * self.d_count
        self.sloss_off = self.short_off + HORIZON_QUARTERS * self.d_count
        self.variable_count = self.sloss_off + HORIZON_QUARTERS * self.o_count * self.g_count
        self.rank = np.empty(self.e_count, dtype=np.int64)
        if self.e_count:
            order = np.argsort(self.declarations.edge_id)
            self.rank[order] = np.arange(self.e_count, dtype=np.int64)

    def f(self, offset: int, edge: int) -> int:
        return self.flow_off + offset * self.e_count + edge

    def a(self, offset: int, recipe: int) -> int:
        return self.act_off + offset * self.r_count + recipe

    def s(self, offset: int, org: int, good: int) -> int:
        return self.inv_off + (offset * self.o_count + org) * self.g_count + good

    def cash(self, offset: int, org: int) -> int:
        return self.cash_off + offset * self.o_count + org

    def fin(self, offset: int, org: int) -> int:
        return self.fin_off + offset * self.o_count + org

    def bank(self, offset: int, bank: int) -> int:
        return self.bank_off + offset * self.b_count + bank

    def u(self, offset: int, demand: int) -> int:
        return self.use_off + offset * self.d_count + demand

    def short(self, offset: int, demand: int) -> int:
        return self.short_off + offset * self.d_count + demand

    def sloss(self, offset: int, org: int, good: int) -> int:
        return self.sloss_off + (offset * self.o_count + org) * self.g_count + good

    def offset_variables(self, offset: int) -> list[int]:
        axis = self
        out: list[int] = []
        for start, size in (
            (axis.flow_off + offset * axis.e_count, axis.e_count),
            (axis.act_off + offset * axis.r_count, axis.r_count),
            (axis.inv_off + offset * axis.o_count * axis.g_count, axis.o_count * axis.g_count),
            (axis.cash_off + offset * axis.o_count, axis.o_count),
            (axis.fin_off + offset * axis.o_count, axis.o_count),
            (axis.bank_off + offset * axis.b_count, axis.b_count),
            (axis.use_off + offset * axis.d_count, axis.d_count),
            (axis.short_off + offset * axis.d_count, axis.d_count),
            (axis.sloss_off + offset * axis.o_count * axis.g_count, axis.o_count * axis.g_count),
        ):
            out.extend(range(start, start + size))
        return out


def _opening_columns(axis: _Axis, offset: int, org: int, good: int) -> tuple[np.ndarray, float]:
    """Return (columns, constant) for the opening inventory term."""
    if offset == 0:
        return np.zeros(0, dtype=np.int64), float(axis.inputs.inventory_initial[org, good])
    return np.asarray([axis.s(offset - 1, org, good)], dtype=np.int64), 0.0


def _append(
    columns: list[np.ndarray],
    values: list[float],
    cols: np.ndarray,
    vals: Any,
) -> None:
    columns.append(np.asarray(cols, dtype=np.int64))
    values.append(np.asarray(vals, dtype=np.float64))


def _build_model_rows(axis: _Axis) -> _Rows:
    inputs = axis.inputs
    d = axis.declarations
    rows = _Rows()
    e_count, r_count, o_count, g_count, d_count = (
        axis.e_count,
        axis.r_count,
        axis.o_count,
        axis.g_count,
        axis.d_count,
    )
    edge_seller = d.edge_seller
    edge_buyer = d.edge_buyer
    edge_good = d.edge_good
    edge_transport = d.edge_transport_org
    edge_service_good = inputs.edge_service_good
    is_service = inputs.goods_is_service
    org_bank = inputs.organization_bank

    recipe_inputs: list[list[tuple[int, float]]] = []
    for recipe in range(r_count):
        start = int(d.recipe_input_ptr[recipe])
        end = int(d.recipe_input_ptr[recipe + 1])
        recipe_inputs.append(
            [
                (int(d.recipe_input_good[k]), float(d.recipe_input_coeff[k]))
                for k in range(start, end)
            ]
        )
    output_incidence: dict[tuple[int, int], list[tuple[int, float]]] = {}
    input_incidence: dict[tuple[int, int], list[tuple[int, float]]] = {}
    early_input_incidence: dict[tuple[int, int], list[tuple[int, float]]] = {}
    for recipe in range(r_count):
        org = int(d.recipe_org[recipe])
        output_good = int(d.recipe_output_good[recipe])
        output_incidence.setdefault((org, output_good), []).append(
            (recipe, float(d.recipe_output_coeff[recipe]))
        )
        for input_good, coefficient in recipe_inputs[recipe]:
            input_incidence.setdefault((org, input_good), []).append((recipe, coefficient))
            if bool(is_service[output_good]):
                early_input_incidence.setdefault((org, input_good), []).append(
                    (recipe, coefficient)
                )

    for offset in range(HORIZON_QUARTERS):
        if not inputs.terminal_mask[offset]:
            continue
        for (org, input_good), entries in early_input_incidence.items():
            opening_input_cols, opening_input_constant = _opening_columns(
                axis, offset, org, input_good
            )
            if bool(is_service[input_good]):
                consumers_by_tier: dict[int, list[tuple[int, float]]] = {}
                for recipe, coefficient in entries:
                    consumers_by_tier.setdefault(int(inputs.recipe_tier[recipe]), []).append(
                        (recipe, coefficient)
                    )
                for tier in sorted(consumers_by_tier):
                    cumulative_consumers = [
                        (recipe, coefficient)
                        for consumer_tier in sorted(consumers_by_tier)
                        if consumer_tier <= tier
                        for recipe, coefficient in consumers_by_tier[consumer_tier]
                    ]
                    columns = [
                        np.asarray([axis.a(offset, recipe)]) for recipe, _ in cumulative_consumers
                    ]
                    values = [np.asarray([coefficient]) for _, coefficient in cumulative_consumers]
                    producers = [
                        (producer, output_coefficient)
                        for producer, output_coefficient in output_incidence.get(
                            (org, input_good), []
                        )
                        if int(inputs.recipe_tier[producer]) < tier
                    ]
                    for producer, output_coefficient in producers:
                        columns.append(np.asarray([axis.a(offset, producer)]))
                        values.append(np.asarray([-output_coefficient]))
                    rows.add_le(
                        f"service_dependency[o={offset},org={org},good={input_good},tier={tier}]",
                        np.concatenate(columns),
                        np.concatenate(values),
                        opening_input_constant,
                    )
                continue
            columns = [np.asarray([axis.a(offset, recipe)]) for recipe, _ in entries]
            values = [np.asarray([coefficient]) for _, coefficient in entries]
            if opening_input_cols.size:
                columns.append(opening_input_cols)
                values.append(-np.ones(opening_input_cols.size))
            rows.add_le(
                f"service_opening_pool[o={offset},org={org},good={input_good}]",
                np.concatenate(columns),
                np.concatenate(values),
                opening_input_constant,
            )

        for org in range(o_count):
            for good in range(g_count):
                produced_cols: list[np.ndarray] = []
                produced_vals: list[float] = []
                for recipe, coefficient in output_incidence.get((org, good), []):
                    _append(
                        produced_cols,
                        produced_vals,
                        np.asarray([axis.a(offset, recipe)]),
                        [coefficient],
                    )
                consumed_cols: list[np.ndarray] = []
                consumed_vals: list[float] = []
                for recipe, coefficient in input_incidence.get((org, good), []):
                    _append(
                        consumed_cols,
                        consumed_vals,
                        np.asarray([axis.a(offset, recipe)]),
                        [coefficient],
                    )
                demands = np.flatnonzero((d.demand_buyer == org) & (d.demand_good == good))
                for demand in demands:
                    _append(
                        consumed_cols,
                        consumed_vals,
                        np.asarray([axis.u(offset, int(demand))]),
                        [1.0],
                    )
                inflow_edges = np.flatnonzero((edge_buyer == org) & (edge_good == good))
                outflow_edges = np.flatnonzero((edge_seller == org) & (edge_good == good))
                opening_cols, opening_constant = _opening_columns(axis, offset, org, good)

                if bool(is_service[good]):
                    extra_service = (
                        float(inputs.service_capacity[offset, org])
                        if int(inputs.organization_service_good[org]) == good
                        else 0.0
                    )
                    freight_cols: list[np.ndarray] = []
                    freight_vals: list[float] = []
                    for edge in np.flatnonzero(
                        (edge_service_good == good) & (edge_transport == org)
                    ):
                        _append(
                            freight_cols,
                            freight_vals,
                            np.asarray([axis.f(offset, int(edge))]),
                            [float(d.edge_freight_per_unit[edge])],
                        )
                    productive_cols: list[np.ndarray] = []
                    productive_vals: list[float] = []
                    intermediate_cols: list[np.ndarray] = []
                    intermediate_vals: list[float] = []
                    for recipe, coefficient in input_incidence.get((org, good), []):
                        target = (
                            intermediate_cols
                            if bool(is_service[int(d.recipe_output_good[recipe])])
                            else productive_cols
                        )
                        target_vals = (
                            intermediate_vals if target is intermediate_cols else productive_vals
                        )
                        _append(
                            target,
                            target_vals,
                            np.asarray([axis.a(offset, recipe)]),
                            [coefficient],
                        )
                    household_cols: list[np.ndarray] = []
                    household_vals: list[float] = []
                    for demand in demands:
                        _append(
                            household_cols,
                            household_vals,
                            np.asarray([axis.u(offset, int(demand))]),
                            [1.0],
                        )
                    service_consumed_cols = [
                        *intermediate_cols,
                        *productive_cols,
                        *household_cols,
                        *freight_cols,
                    ]
                    service_consumed_vals = [
                        *intermediate_vals,
                        *productive_vals,
                        *household_vals,
                        *freight_vals,
                    ]
                    balance_cols: list[np.ndarray] = [
                        *produced_cols,
                        *intermediate_cols,
                        *productive_cols,
                        *household_cols,
                        *freight_cols,
                    ]
                    balance_vals: list[float] = [
                        *produced_vals,
                        *[-v for v in intermediate_vals],
                        *[-v for v in productive_vals],
                        *[-v for v in household_vals],
                        *[-v for v in freight_vals],
                    ]
                    if inflow_edges.size:
                        _append(
                            balance_cols,
                            balance_vals,
                            inflow_edges + axis.flow_off + offset * e_count,
                            np.ones(inflow_edges.size),
                        )
                    if outflow_edges.size:
                        _append(
                            balance_cols,
                            balance_vals,
                            outflow_edges + axis.flow_off + offset * e_count,
                            -np.ones(outflow_edges.size),
                        )
                    _append(
                        balance_cols,
                        balance_vals,
                        np.asarray([axis.sloss(offset, org, good)]),
                        [-1.0],
                    )
                    rows.add(
                        f"service_balance[o={offset},org={org},good={good}]",
                        np.concatenate(balance_cols),
                        np.concatenate(balance_vals),
                        -(opening_constant + extra_service),
                        EQUALS,
                    )
                    # Current use cannot exceed current production plus
                    # imported service; opening service is lost, not usable.
                    joint_cols: list[np.ndarray] = [
                        *service_consumed_cols,
                    ]
                    joint_vals: list[float] = [*service_consumed_vals]
                    if outflow_edges.size:
                        _append(
                            joint_cols,
                            joint_vals,
                            outflow_edges + axis.flow_off + offset * e_count,
                            np.ones(outflow_edges.size),
                        )
                    for cols, vals in zip(produced_cols, produced_vals, strict=True):
                        _append(joint_cols, joint_vals, cols, -vals)
                    if inflow_edges.size:
                        _append(
                            joint_cols,
                            joint_vals,
                            inflow_edges + axis.flow_off + offset * e_count,
                            -np.ones(inflow_edges.size),
                        )
                    if joint_cols:
                        rows.add_le(
                            f"service_joint[o={offset},org={org},good={good}]",
                            np.concatenate(joint_cols),
                            np.concatenate(joint_vals),
                            extra_service + opening_constant,
                        )
                    for channel, channel_cols, channel_vals, share in (
                        ("logistics", freight_cols, freight_vals, float(inputs.service_split[0])),
                        (
                            "productive",
                            productive_cols,
                            productive_vals,
                            float(inputs.service_split[1]),
                        ),
                        (
                            "household",
                            household_cols,
                            household_vals,
                            float(inputs.service_split[2]),
                        ),
                    ):
                        if share >= 1.0 - ATOL or not channel_cols:
                            continue
                        split_cols: list[np.ndarray] = [*channel_cols]
                        split_vals: list[float] = [*channel_vals]
                        for cols, vals in zip(produced_cols, produced_vals, strict=True):
                            _append(
                                split_cols,
                                split_vals,
                                cols,
                                [-share * value for value in vals],
                            )
                        if inflow_edges.size:
                            _append(
                                split_cols,
                                split_vals,
                                inflow_edges + axis.flow_off + offset * e_count,
                                -share * np.ones(inflow_edges.size),
                            )
                        rows.add_le(
                            f"service_reservation[o={offset},org={org},good={good},channel={channel}]",
                            np.concatenate(split_cols),
                            np.concatenate(split_vals),
                            share * (extra_service + opening_constant),
                        )
                    continue

                balance_cols: list[np.ndarray] = []
                balance_vals: list[float] = []
                if opening_cols.size:
                    _append(
                        balance_cols,
                        balance_vals,
                        opening_cols,
                        np.ones(opening_cols.size),
                    )
                if inflow_edges.size:
                    _append(
                        balance_cols,
                        balance_vals,
                        inflow_edges + axis.flow_off + offset * e_count,
                        np.ones(inflow_edges.size),
                    )
                for cols, vals in zip(produced_cols, produced_vals, strict=True):
                    _append(balance_cols, balance_vals, cols, vals)
                if outflow_edges.size:
                    _append(
                        balance_cols,
                        balance_vals,
                        outflow_edges + axis.flow_off + offset * e_count,
                        -np.ones(outflow_edges.size),
                    )
                for cols, vals in zip(consumed_cols, consumed_vals, strict=True):
                    _append(balance_cols, balance_vals, cols, -vals)
                _append(
                    balance_cols,
                    balance_vals,
                    np.asarray([axis.s(offset, org, good)]),
                    [-1.0],
                )
                rows.add(
                    f"goods_balance[o={offset},org={org},good={good}]",
                    np.concatenate(balance_cols),
                    np.concatenate(balance_vals),
                    -opening_constant,
                    EQUALS,
                )
                release_cols: list[np.ndarray] = []
                release_vals: list[float] = []
                if outflow_edges.size:
                    _append(
                        release_cols,
                        release_vals,
                        outflow_edges + axis.flow_off + offset * e_count,
                        np.ones(outflow_edges.size),
                    )
                if opening_cols.size:
                    _append(
                        release_cols,
                        release_vals,
                        opening_cols,
                        -np.ones(opening_cols.size),
                    )
                for recipe, coefficient in early_input_incidence.get((org, good), []):
                    _append(
                        release_cols,
                        release_vals,
                        np.asarray([axis.a(offset, recipe)]),
                        [coefficient],
                    )
                if release_cols:
                    rows.add_le(
                        f"source_release[o={offset},org={org},good={good}]",
                        np.concatenate(release_cols),
                        np.concatenate(release_vals),
                        opening_constant,
                    )
                # Joint current-resource row: current output cannot fund
                # same-quarter outflow or consumption.
                joint_cols = []
                joint_vals = []
                if outflow_edges.size:
                    _append(
                        joint_cols,
                        joint_vals,
                        outflow_edges + axis.flow_off + offset * e_count,
                        np.ones(outflow_edges.size),
                    )
                for cols, vals in zip(consumed_cols, consumed_vals, strict=True):
                    _append(joint_cols, joint_vals, cols, vals)
                if inflow_edges.size:
                    _append(
                        joint_cols,
                        joint_vals,
                        inflow_edges + axis.flow_off + offset * e_count,
                        -np.ones(inflow_edges.size),
                    )
                if opening_cols.size:
                    _append(
                        joint_cols,
                        joint_vals,
                        opening_cols,
                        -np.ones(opening_cols.size),
                    )
                if joint_cols:
                    rows.add_le(
                        f"joint_availability[o={offset},org={org},good={good}]",
                        np.concatenate(joint_cols),
                        np.concatenate(joint_vals),
                        opening_constant,
                    )

        for demand in range(d_count):
            ordered = float(inputs.demand_ordered[offset, demand])
            gross = float(inputs.demand_gross[offset, demand])
            rows.add(
                f"demand_need[o={offset},d={demand}]",
                [axis.u(offset, demand), axis.short(offset, demand)],
                [1.0, 1.0],
                gross,
                EQUALS,
            )
            rows.add_le(
                f"demand_ordered_cap[o={offset},d={demand}]",
                [axis.u(offset, demand)],
                [1.0],
                ordered,
            )

        for org in range(o_count):
            handling_edges = np.flatnonzero((edge_seller == org) | (edge_buyer == org))
            if handling_edges.size:
                rows.add_le(
                    f"handling[o={offset},org={org}]",
                    handling_edges + axis.flow_off + offset * e_count,
                    d.edge_handling_per_unit[handling_edges],
                    float(inputs.handling_capacity[offset, org]),
                )
            purchase_edges = np.flatnonzero(edge_buyer == org)
            cost_cols = purchase_edges + axis.flow_off + offset * e_count
            cost_vals = (
                inputs.prices[offset, d.edge_good[purchase_edges]]
                + inputs.edge_freight_price[purchase_edges]
            )
            receipt_cols: list[np.ndarray] = []
            receipt_vals: list[float] = []
            seller_edges = np.flatnonzero(edge_seller == org)
            if seller_edges.size:
                _append(
                    receipt_cols,
                    receipt_vals,
                    seller_edges + axis.flow_off + offset * e_count,
                    inputs.prices[offset, d.edge_good[seller_edges]],
                )
            carrier_edges = np.flatnonzero(edge_transport == org)
            if carrier_edges.size:
                _append(
                    receipt_cols,
                    receipt_vals,
                    carrier_edges + axis.flow_off + offset * e_count,
                    inputs.edge_freight_price[carrier_edges],
                )
            opening_cash_cols = np.zeros(0, dtype=np.int64)
            opening_cash = float(inputs.cash_initial[org])
            if offset > 0:
                opening_cash_cols = np.asarray([axis.cash(offset - 1, org)], dtype=np.int64)
                opening_cash = 0.0
            fin_now = axis.fin(offset, org)
            wage = float(inputs.wage[offset, org])
            interest = float(inputs.interest[offset, org])
            prepay_cols: list[np.ndarray] = []
            prepay_vals: list[float] = []
            if cost_cols.size:
                _append(prepay_cols, prepay_vals, cost_cols, cost_vals)
            _append(prepay_cols, prepay_vals, np.asarray([fin_now]), [-1.0])
            if opening_cash_cols.size:
                _append(prepay_cols, prepay_vals, opening_cash_cols, [-1.0])
            if prepay_cols:
                rows.add_le(
                    f"prepaid_funding[o={offset},org={org}]",
                    np.concatenate(prepay_cols),
                    np.concatenate(prepay_vals),
                    opening_cash - wage - interest,
                )
            cash_cols = [np.asarray([axis.cash(offset, org)]), *receipt_cols]
            cash_vals = [np.asarray([1.0]), *[-v for v in receipt_vals]]
            if cost_cols.size:
                cash_cols.append(cost_cols)
                cash_vals.append(np.asarray(cost_vals, dtype=np.float64))
            cash_cols.append(np.asarray([fin_now]))
            cash_vals.append(np.asarray([-1.0]))
            if opening_cash_cols.size:
                cash_cols.append(opening_cash_cols)
                cash_vals.append(np.asarray([-1.0]))
            rows.add(
                f"cash_balance[o={offset},org={org}]",
                np.concatenate(cash_cols),
                np.concatenate(cash_vals),
                opening_cash - wage - interest,
                EQUALS,
            )
            rows.add_le(
                f"financing_capacity[o={offset},org={org}]",
                [fin_now],
                [1.0],
                float(inputs.order_financing[offset, org]),
            )
            group = int(inputs.organization_funding_group[org])
            group_orgs = np.flatnonzero(inputs.organization_funding_group == group)
            rows.add_le(
                f"funding_group[o={offset},group={group}]",
                [axis.fin(offset, int(member)) for member in group_orgs],
                np.ones(group_orgs.size),
                float(inputs.funding_group_capacity[offset, group]),
            )

        for bank in range(axis.b_count):
            opening_bank_cols = np.zeros(0, dtype=np.int64)
            opening_bank = float(inputs.bank_reserves[0, bank])
            if offset > 0:
                opening_bank_cols = np.asarray([axis.bank(offset - 1, bank)], dtype=np.int64)
                opening_bank = 0.0
            out_cols: list[np.ndarray] = []
            out_vals: list[float] = []
            cross_goods = np.flatnonzero(
                (org_bank[edge_buyer] == bank) & (org_bank[edge_seller] != bank)
            )
            if cross_goods.size:
                _append(
                    out_cols,
                    out_vals,
                    cross_goods + axis.flow_off + offset * e_count,
                    inputs.prices[offset, d.edge_good[cross_goods]],
                )
            cross_freight = np.flatnonzero(
                (org_bank[edge_buyer] == bank)
                & (edge_transport >= 0)
                & (org_bank[np.maximum(edge_transport, 0)] != bank)
            )
            if cross_freight.size:
                _append(
                    out_cols,
                    out_vals,
                    cross_freight + axis.flow_off + offset * e_count,
                    inputs.edge_freight_price[cross_freight],
                )
            in_cols: list[np.ndarray] = []
            in_vals: list[float] = []
            in_goods = np.flatnonzero(
                (org_bank[edge_seller] == bank) & (org_bank[edge_buyer] != bank)
            )
            if in_goods.size:
                _append(
                    in_cols,
                    in_vals,
                    in_goods + axis.flow_off + offset * e_count,
                    inputs.prices[offset, d.edge_good[in_goods]],
                )
            in_freight = np.flatnonzero(
                (edge_transport >= 0)
                & (org_bank[np.maximum(edge_transport, 0)] == bank)
                & (org_bank[edge_buyer] != bank)
            )
            if in_freight.size:
                _append(
                    in_cols,
                    in_vals,
                    in_freight + axis.flow_off + offset * e_count,
                    inputs.edge_freight_price[in_freight],
                )
            balance_cols = [
                np.asarray([axis.bank(offset, bank)]),
                *in_cols,
                *out_cols,
            ]
            balance_vals = [np.asarray([1.0]), *[-v for v in in_vals], *out_vals]
            if opening_bank_cols.size:
                balance_cols.append(opening_bank_cols)
                balance_vals.append(np.asarray([-1.0]))
            rows.add(
                f"bank_cash[o={offset},bank={bank}]",
                np.concatenate(balance_cols),
                np.concatenate(balance_vals),
                opening_bank,
                EQUALS,
            )
            prepay_cols = [*out_cols]
            prepay_vals = [*out_vals]
            if opening_bank_cols.size:
                _append(prepay_cols, prepay_vals, opening_bank_cols, [-1.0])
            if prepay_cols:
                rows.add_le(
                    f"bank_prefunding[o={offset},bank={bank}]",
                    np.concatenate(
                        [np.atleast_1d(part) for part in prepay_cols if np.asarray(part).size]
                    ),
                    np.concatenate(
                        [np.atleast_1d(part) for part in prepay_vals if np.asarray(part).size]
                    ),
                    opening_bank,
                )
    return rows


def _build_base_rows(axis: _Axis) -> _Rows:
    return _build_model_rows(axis)


def _objective_layers(axis: _Axis) -> tuple[list[np.ndarray], list[float], list[str]]:
    inputs = axis.inputs
    d = axis.declarations
    objective1 = np.zeros(axis.variable_count, dtype=np.float64)
    objective2 = np.zeros(axis.variable_count, dtype=np.float64)
    objective3 = np.zeros(axis.variable_count, dtype=np.float64)
    objective4 = np.zeros(axis.variable_count, dtype=np.float64)
    constants = [0.0, 0.0, 0.0, 0.0]

    # Normalized demand denominators by good.
    active = np.asarray(inputs.terminal_mask, dtype=bool)
    denom = np.zeros(axis.g_count, dtype=np.float64)
    for demand in range(axis.d_count):
        good = int(d.demand_good[demand])
        denom[good] += float(inputs.demand_gross[active, demand].sum())
    input_denom = np.array(denom, dtype=np.float64, copy=True)
    for offset in range(HORIZON_QUARTERS):
        if not inputs.terminal_mask[offset]:
            continue
        for recipe in range(axis.r_count):
            start = int(d.recipe_input_ptr[recipe])
            end = int(d.recipe_input_ptr[recipe + 1])
            for position in range(start, end):
                good = int(d.recipe_input_good[position])
                input_denom[good] += float(
                    inputs.recipe_capacity[offset, recipe] * float(d.recipe_input_coeff[position])
                )

    for offset in range(HORIZON_QUARTERS):
        if not inputs.terminal_mask[offset]:
            continue
        for demand in range(axis.d_count):
            good = int(d.demand_good[demand])
            scale = 1.0 / denom[good] if denom[good] > ATOL else 0.0
            if scale == 0.0:
                continue
            if bool(d.demand_final[demand]):
                objective1[axis.short(offset, demand)] += scale
            else:
                objective2[axis.short(offset, demand)] += scale
        # Production-input shortfall, normalized in the input good's units.
        for recipe in range(axis.r_count):
            start = int(d.recipe_input_ptr[recipe])
            end = int(d.recipe_input_ptr[recipe + 1])
            for position in range(start, end):
                good = int(d.recipe_input_good[position])
                if input_denom[good] <= ATOL:
                    continue
                coefficient = float(d.recipe_input_coeff[position])
                scale = coefficient / input_denom[good]
                objective2[axis.a(offset, recipe)] -= scale
                constants[1] += float(inputs.recipe_capacity[offset, recipe]) * scale
        for edge in range(axis.e_count):
            objective3[axis.f(offset, edge)] += float(
                inputs.prices[offset, int(d.edge_good[edge])] + inputs.edge_freight_price[edge]
            )
            objective4[axis.f(offset, edge)] += float(1.0 + offset * axis.e_count + axis.rank[edge])
    scale = float(np.max(np.abs(objective4))) if objective4.size else 0.0
    if scale > 0.0:
        objective4 /= scale
    return (
        [objective1, objective2, objective3, objective4],
        constants,
        list(PRIORITY),
    )


def _bounds(axis: _Axis) -> list[tuple[float, float | None]]:
    bounds: list[tuple[float, float | None]] = [(0.0, None)] * axis.variable_count
    for offset in range(HORIZON_QUARTERS):
        if not axis.inputs.terminal_mask[offset]:
            for index in axis.offset_variables(offset):
                bounds[index] = (0.0, 0.0)
            continue
        controlled = set(axis.inputs.declarations.decision_organization_ids)
        for edge in range(axis.e_count):
            baseline = float(axis.inputs.declarations.edge_baseline[offset, edge])
            buyer_label = axis.inputs.organization_ids[
                int(axis.inputs.declarations.edge_buyer[edge])
            ]
            upper = (
                float(axis.inputs.edge_capacity[offset, edge])
                if buyer_label in controlled
                else baseline
            )
            bounds[axis.f(offset, edge)] = (baseline, max(baseline, upper))
        for recipe in range(axis.r_count):
            bounds[axis.a(offset, recipe)] = (
                0.0,
                float(axis.inputs.recipe_capacity[offset, recipe]),
            )
    for offset in range(HORIZON_QUARTERS):
        for org in range(axis.o_count):
            for good in range(axis.g_count):
                if bool(axis.inputs.goods_is_service[good]):
                    bounds[axis.s(offset, org, good)] = (0.0, 0.0)
                else:
                    bounds[axis.sloss(offset, org, good)] = (0.0, 0.0)
    return bounds


def _certificate(
    *,
    axis: _Axis,
    rows: _Rows,
    result: Any,
    vector: np.ndarray | None,
    status: str,
    message: str,
    feasible: bool,
    layer_index: int,
    layer_objective: float,
    wall_s: float,
    constraint_hash: str,
    failure_reason: str,
) -> PlanningCertificate:
    if vector is not None:
        activity, residual, slack = rows.witness(vector)
        dual_eq = np.asarray(
            getattr(getattr(result, "eqlin", None), "marginals", np.zeros(0)), dtype=np.float64
        )
        dual_ub = np.asarray(
            getattr(getattr(result, "ineqlin", None), "marginals", np.zeros(0)), dtype=np.float64
        )
        primal = np.asarray(vector, dtype=np.float64).copy()
    else:
        activity = np.zeros(0)
        residual = np.zeros(0)
        slack = np.zeros(0)
        dual_eq = np.zeros(0)
        dual_ub = np.zeros(0)
        primal = np.zeros(0)
    return PlanningCertificate(
        schema_version=SCHEMA_VERSION,
        status=status,
        solver_status=int(getattr(result, "status", 9)),
        solver_message=message,
        solver_feasible=feasible,
        matrix_rows=len(rows.names),
        matrix_cols=axis.variable_count,
        nnz=int(sum(columns.size for columns in rows.cols)),
        row_names=tuple(rows.names),
        row_sense=np.asarray(rows.senses, dtype=np.int64),
        row_rhs=np.asarray(rows.rhs, dtype=np.float64),
        primal=primal,
        dual_eq=dual_eq,
        dual_ub=dual_ub,
        row_activity=activity,
        row_residual=residual,
        row_slack=slack,
        layer_index=layer_index,
        layer_objective=float(layer_objective),
        wall_s=float(wall_s),
        input_hash=axis.inputs.input_hash,
        constraint_hash=constraint_hash,
        failure_reason=failure_reason,
    )


def _empty_quarter(offset: int, quarter: str, active: bool, axis: _Axis) -> QuarterPlan:
    return QuarterPlan(
        offset=offset,
        quarter=quarter,
        active=active,
        purchases=np.zeros((axis.o_count, axis.g_count), dtype=np.float64),
        inventory=np.zeros((axis.o_count, axis.g_count), dtype=np.float64),
        cash=np.zeros(axis.o_count, dtype=np.float64),
        final_use=np.zeros(axis.d_count, dtype=np.float64),
        shortfall=np.zeros(axis.d_count, dtype=np.float64),
        service_produced=np.zeros(axis.o_count, dtype=np.float64),
        service_used=np.zeros(axis.o_count, dtype=np.float64),
        service_lost=np.zeros(axis.o_count, dtype=np.float64),
        service_produced_by_good=np.zeros((axis.o_count, axis.g_count), dtype=np.float64),
        service_used_by_good=np.zeros((axis.o_count, axis.g_count), dtype=np.float64),
        service_lost_by_good=np.zeros((axis.o_count, axis.g_count), dtype=np.float64),
        financing=np.zeros(axis.o_count, dtype=np.float64),
        bank_cash=np.zeros(axis.b_count, dtype=np.float64),
        goods_payment=np.zeros(axis.o_count, dtype=np.float64),
        freight_payment=np.zeros(axis.o_count, dtype=np.float64),
        objective_layers=(0.0, 0.0, 0.0, 0.0),
        certificate_index=-1,
    )


def _failed_plan(
    inputs: PlanningInputs,
    *,
    mode: str,
    status: str,
    certificates: tuple[PlanningCertificate, ...],
    reason: str,
) -> RollingPlan:
    axis = _Axis(inputs)
    quarterly = tuple(
        _empty_quarter(offset, inputs.quarters[offset], inputs.terminal_mask[offset], axis)
        for offset in range(HORIZON_QUARTERS)
    )
    return RollingPlan(
        schema_version=SCHEMA_VERSION,
        mode=mode,
        status=status,
        decision_quarter=inputs.quarter,
        horizon_quarters=HORIZON_QUARTERS,
        quarters=inputs.quarters,
        terminal_mask=inputs.terminal_mask,
        source_kind=inputs.source_kind,
        inputs=inputs,
        input_hash=inputs.input_hash,
        observation_hash=inputs.observation_hash,
        priority_hash=inputs.priority_hash,
        forecast_hash=inputs.forecast_hash,
        matrix_hash=hashlib.sha256(f"{inputs.input_hash}:{status}:{reason}".encode()).hexdigest(),
        comparison_status="NOT_COMPARABLE",
        comparison_reason=reason,
        certificates=certificates,
        quarterly=quarterly,
        first_quarter_decisions=(),
        first_quarter_payload_hash=_decision_payload_hash(()),
        objective_layers=(0.0, 0.0, 0.0, 0.0),
    )


def _rule_plan_v2(inputs: PlanningInputs, *, time_limit_s: float) -> RollingPlan:
    axis = _Axis(inputs)
    d = inputs.declarations
    start = time.perf_counter()
    o_count, g_count, e_count, r_count = (
        axis.o_count,
        axis.g_count,
        axis.e_count,
        axis.r_count,
    )
    inventory = np.array(inputs.inventory_initial, dtype=np.float64, copy=True)
    cash = np.array(inputs.cash_initial, dtype=np.float64, copy=True)
    bank_cash = np.array(inputs.bank_reserves[0], dtype=np.float64, copy=True)
    quarters: list[QuarterPlan] = []
    checks: list[tuple[str, float]] = []
    first_flow = np.zeros(e_count, dtype=np.float64)

    for offset in range(HORIZON_QUARTERS):
        if not inputs.terminal_mask[offset]:
            quarters.append(_empty_quarter(offset, inputs.quarters[offset], False, axis))
            continue
        opening_inventory = np.array(inventory, dtype=np.float64, copy=True)
        shippable = np.array(opening_inventory, dtype=np.float64, copy=True)
        opening_cash = np.array(cash, dtype=np.float64, copy=True)
        opening_bank = np.array(bank_cash, dtype=np.float64, copy=True)
        financing = np.zeros(o_count, dtype=np.float64)
        handling_used = np.zeros(o_count, dtype=np.float64)
        flow = np.zeros(e_count, dtype=np.float64)
        produced_next = np.zeros((o_count, g_count), dtype=np.float64)
        service_produced = np.zeros((o_count, g_count), dtype=np.float64)
        service_used = np.zeros((o_count, g_count), dtype=np.float64)
        service_logistics = np.zeros((o_count, g_count), dtype=np.float64)
        service_intermediate = np.zeros((o_count, g_count), dtype=np.float64)
        service_productive = np.zeros((o_count, g_count), dtype=np.float64)
        service_household = np.zeros((o_count, g_count), dtype=np.float64)
        activity = np.zeros(r_count, dtype=np.float64)
        demands_use = np.zeros(axis.d_count, dtype=np.float64)
        shortfall = np.zeros(axis.d_count, dtype=np.float64)
        goods_payment = np.zeros(o_count, dtype=np.float64)
        freight_payment = np.zeros(o_count, dtype=np.float64)
        receipts = np.zeros(o_count, dtype=np.float64)
        group_drawn = np.zeros(int(inputs.funding_group_capacity.shape[1]), dtype=np.float64)

        # 1. Production from opening inputs in dependency-tier order.  Current
        #    output is not available to this quarter's demand or sales.
        service_available = np.zeros((o_count, g_count), dtype=np.float64)
        for org in range(o_count):
            for good in range(g_count):
                if bool(inputs.goods_is_service[good]):
                    service_available[org, good] = float(opening_inventory[org, good])
            exogenous_good = int(inputs.organization_service_good[org])
            if exogenous_good >= 0:
                service_available[org, exogenous_good] += float(
                    inputs.service_capacity[offset, org]
                )
                service_produced[org, exogenous_good] += float(inputs.service_capacity[offset, org])
        recipe_tiers = sorted(set(int(value) for value in inputs.recipe_tier))
        for tier in recipe_tiers:
            produced_this_tier = np.zeros((o_count, g_count), dtype=np.float64)
            for recipe in range(r_count):
                if int(inputs.recipe_tier[recipe]) != tier:
                    continue
                org = int(d.recipe_org[recipe])
                limit = float(inputs.recipe_capacity[offset, recipe])
                for position in range(
                    int(d.recipe_input_ptr[recipe]),
                    int(d.recipe_input_ptr[recipe + 1]),
                ):
                    good = int(d.recipe_input_good[position])
                    coefficient = float(d.recipe_input_coeff[position])
                    if coefficient <= 0.0:
                        continue
                    if bool(inputs.goods_is_service[good]):
                        available = float(service_available[org, good])
                    elif bool(inputs.goods_is_service[int(d.recipe_output_good[recipe])]):
                        available = float(shippable[org, good])
                    else:
                        available = float(inventory[org, good])
                    limit = min(limit, available / coefficient)
                activity[recipe] = max(0.0, limit)
                for position in range(
                    int(d.recipe_input_ptr[recipe]),
                    int(d.recipe_input_ptr[recipe + 1]),
                ):
                    good = int(d.recipe_input_good[position])
                    coefficient = float(d.recipe_input_coeff[position])
                    amount = activity[recipe] * coefficient
                    if bool(inputs.goods_is_service[good]):
                        service_available[org, good] -= amount
                        service_used[org, good] += amount
                        if bool(inputs.goods_is_service[int(d.recipe_output_good[recipe])]):
                            service_intermediate[org, good] += amount
                        else:
                            service_productive[org, good] += amount
                    else:
                        inventory[org, good] -= amount
                        if bool(inputs.goods_is_service[int(d.recipe_output_good[recipe])]):
                            shippable[org, good] -= amount
                output_good = int(d.recipe_output_good[recipe])
                output_amount = activity[recipe] * float(d.recipe_output_coeff[recipe])
                if bool(inputs.goods_is_service[output_good]):
                    produced_this_tier[org, output_good] += output_amount
                else:
                    produced_next[org, output_good] += output_amount
            service_produced += produced_this_tier
            service_available += produced_this_tier

        # 2. Purchase gaps using observable seller stock, edge capacity, cash
        #    and the shared authorized financing envelope.
        required = np.zeros((o_count, g_count), dtype=np.float64)
        for demand in range(axis.d_count):
            org = int(d.demand_buyer[demand])
            good = int(d.demand_good[demand])
            if bool(inputs.goods_is_service[good]):
                continue
            need = min(
                float(inputs.demand_ordered[offset, demand]),
                float(inputs.demand_gross[offset, demand]),
            )
            required[org, good] += need
        for org in range(o_count):
            for good in range(g_count):
                if bool(inputs.goods_is_service[good]):
                    continue
                gap = max(0.0, required[org, good] - inventory[org, good])
                if gap <= ATOL:
                    continue
                edges = np.flatnonzero((d.edge_buyer == org) & (d.edge_good == good))
                for edge in edges:
                    if gap <= ATOL:
                        break
                    seller = int(d.edge_seller[edge])
                    if shippable[seller, good] <= ATOL:
                        continue
                    unit_cost = float(
                        inputs.prices[offset, int(d.edge_good[edge])]
                        + inputs.edge_freight_price[edge]
                    )
                    group = int(inputs.organization_funding_group[org])
                    group_left = max(
                        0.0,
                        float(inputs.funding_group_capacity[offset, group])
                        - float(group_drawn[group]),
                    )
                    financing_room = max(
                        0.0,
                        min(
                            float(inputs.order_financing[offset, org]) - float(financing[org]),
                            group_left,
                        ),
                    )
                    available_funding = max(
                        0.0,
                        float(opening_cash[org])
                        + float(financing[org])
                        + financing_room
                        - float(inputs.wage[offset, org])
                        - float(inputs.interest[offset, org])
                        - float(goods_payment[org])
                        - float(freight_payment[org]),
                    )
                    affordable = available_funding / unit_cost if unit_cost > ATOL else gap
                    handling_per_unit = float(d.edge_handling_per_unit[edge])
                    handling_left = min(
                        float(inputs.handling_capacity[offset, org]) - float(handling_used[org]),
                        float(inputs.handling_capacity[offset, seller])
                        - float(handling_used[seller]),
                    )
                    affordable_handling = (
                        max(0.0, handling_left) / handling_per_unit
                        if handling_per_unit > ATOL
                        else gap
                    )
                    carrier = int(d.edge_transport_org[edge])
                    service_good = int(inputs.edge_service_good[edge])
                    service_per_unit = float(d.edge_freight_per_unit[edge])
                    if carrier >= 0 and service_good >= 0 and service_per_unit > ATOL:
                        service_left = max(0.0, float(service_available[carrier, service_good]))
                        affordable_service = service_left / service_per_unit
                    else:
                        affordable_service = gap
                    quantity = min(
                        gap,
                        float(inputs.edge_capacity[offset, edge]),
                        float(shippable[seller, good]),
                        affordable,
                        affordable_handling,
                        affordable_service,
                    )
                    if quantity <= ATOL:
                        continue
                    purchase_cost = quantity * unit_cost
                    draw = min(purchase_cost, financing_room)
                    financing[org] += draw
                    group_drawn[group] += draw
                    shippable[seller, good] -= quantity
                    inventory[seller, good] -= quantity
                    inventory[org, good] += quantity
                    flow[edge] += quantity
                    gap -= quantity
                    handling_used[org] += quantity * handling_per_unit
                    handling_used[seller] += quantity * handling_per_unit
                    goods_payment[org] += quantity * float(
                        inputs.prices[offset, int(d.edge_good[edge])]
                    )
                    freight_payment[org] += quantity * float(inputs.edge_freight_price[edge])
                    receipts[seller] += quantity * float(
                        inputs.prices[offset, int(d.edge_good[edge])]
                    )
                    if carrier >= 0:
                        receipts[carrier] += quantity * float(inputs.edge_freight_price[edge])
                        if service_good >= 0 and service_per_unit > ATOL:
                            service_amount = quantity * service_per_unit
                            service_available[carrier, service_good] -= service_amount
                            service_used[carrier, service_good] += service_amount
                            service_logistics[carrier, service_good] += service_amount

        for org in range(o_count):
            group = int(inputs.organization_funding_group[org])
            expense = (
                float(goods_payment[org])
                + float(freight_payment[org])
                + float(inputs.wage[offset, org])
                + float(inputs.interest[offset, org])
            )
            group_left = max(
                0.0,
                float(inputs.funding_group_capacity[offset, group]) - float(group_drawn[group]),
            )
            draw = min(
                expense,
                float(inputs.order_financing[offset, org]) - float(financing[org]),
                group_left,
            )
            financing[org] += draw
            group_drawn[group] += draw
            cash[org] = (
                float(opening_cash[org]) + float(financing[org]) - expense + float(receipts[org])
            )

        # 3. Fulfil demands from opening inventory (plus purchases) or
        #    same-quarter service production.
        for demand in range(axis.d_count):
            org = int(d.demand_buyer[demand])
            good = int(d.demand_good[demand])
            ordered = float(inputs.demand_ordered[offset, demand])
            gross = float(inputs.demand_gross[offset, demand])
            need = min(ordered, gross)
            if bool(inputs.goods_is_service[good]):
                available = max(
                    0.0,
                    float(service_produced[org, good] + opening_inventory[org, good])
                    - float(service_used[org, good]),
                )
            else:
                available = max(0.0, float(inventory[org, good]))
            used = min(need, available)
            demands_use[demand] = used
            shortfall[demand] = gross - used
            if bool(inputs.goods_is_service[good]):
                service_used[org, good] += used
                service_household[org, good] += used
            else:
                inventory[org, good] -= used

        # 4. Freight service was reserved and consumed in the edge loop.

        # 5. Cash receipts and bank settlement.
        service_lost = np.zeros((o_count, g_count), dtype=np.float64)
        for org in range(o_count):
            for good in range(g_count):
                if not bool(inputs.goods_is_service[good]):
                    continue
                opening_service = float(inputs.inventory_initial[org, good]) if offset == 0 else 0.0
                service_lost[org, good] = (
                    opening_service + service_produced[org, good] - service_used[org, good]
                )

        out_by_bank = np.zeros(axis.b_count, dtype=np.float64)
        in_by_bank = np.zeros(axis.b_count, dtype=np.float64)
        for edge in np.flatnonzero(flow > ATOL):
            buyer_bank = int(inputs.organization_bank[int(d.edge_buyer[edge])])
            seller_bank = int(inputs.organization_bank[int(d.edge_seller[edge])])
            amount = float(flow[edge]) * float(inputs.prices[offset, int(d.edge_good[edge])])
            if buyer_bank != seller_bank:
                out_by_bank[buyer_bank] += amount
                in_by_bank[seller_bank] += amount
            carrier = int(d.edge_transport_org[edge])
            if carrier >= 0:
                carrier_bank = int(inputs.organization_bank[carrier])
                fee = float(flow[edge]) * float(inputs.edge_freight_price[edge])
                if buyer_bank != carrier_bank:
                    out_by_bank[buyer_bank] += fee
                    in_by_bank[carrier_bank] += fee
        bank_cash = opening_bank + in_by_bank - out_by_bank

        # 6. Independent conservation checks.
        for org in range(o_count):
            checks.append((f"cash[o={offset},org={org}]", max(0.0, -float(cash[org]))))
            if float(cash[org]) < -ATOL:
                checks.append((f"cash_negative[o={offset},org={org}]", -float(cash[org])))
            expense = (
                float(goods_payment[org])
                + float(freight_payment[org])
                + float(inputs.wage[offset, org])
                + float(inputs.interest[offset, org])
            )
            pre_receipt_cash = float(opening_cash[org]) + float(financing[org]) - expense
            checks.append(
                (
                    f"pre_receipt_funding[o={offset},org={org}]",
                    max(0.0, -pre_receipt_cash),
                )
            )
            expected_cash = (
                float(opening_cash[org]) + float(financing[org]) + float(receipts[org]) - expense
            )
            checks.append(
                (f"cash_identity[o={offset},org={org}]", abs(float(cash[org]) - expected_cash))
            )
            checks.append(
                (
                    f"handling[o={offset},org={org}]",
                    max(
                        0.0,
                        float(handling_used[org]) - float(inputs.handling_capacity[offset, org]),
                    ),
                )
            )
        for group in range(int(inputs.funding_group_capacity.shape[1])):
            group_orgs = np.flatnonzero(inputs.organization_funding_group == group)
            group_total = float(np.sum(financing[group_orgs]))
            checks.append(
                (
                    f"funding_group[o={offset},group={group}]",
                    max(
                        0.0,
                        group_total - float(inputs.funding_group_capacity[offset, group]),
                    ),
                )
            )
        for org in range(o_count):
            for good in range(g_count):
                if float(inventory[org, good]) < -ATOL:
                    checks.append(
                        (
                            f"inventory_negative[o={offset},org={org},good={good}]",
                            -float(inventory[org, good]),
                        )
                    )
                if service_lost[org, good] < -ATOL:
                    checks.append(
                        (
                            f"service_lost_negative[o={offset},org={org},good={good}]",
                            -float(service_lost[org, good]),
                        )
                    )
                if bool(inputs.goods_is_service[good]):
                    for channel, used_by_channel, share in (
                        ("logistics", service_logistics, inputs.service_split[0]),
                        ("productive", service_productive, inputs.service_split[1]),
                        ("household", service_household, inputs.service_split[2]),
                    ):
                        if float(share) >= 1.0 - ATOL:
                            continue
                        allowed = float(share) * (
                            float(service_produced[org, good]) + float(opening_inventory[org, good])
                        )
                        checks.append(
                            (
                                f"service_reservation[o={offset},org={org},good={good},channel={channel}]",
                                max(
                                    0.0,
                                    float(used_by_channel[org, good]) - allowed,
                                ),
                            )
                        )
        for bank in range(axis.b_count):
            if out_by_bank[bank] > opening_bank[bank] + ATOL:
                checks.append(
                    (
                        f"bank_prefunding[o={offset},bank={bank}]",
                        out_by_bank[bank] - opening_bank[bank],
                    )
                )
        if offset == 0:
            first_flow = flow.copy()
        closing_inventory = inventory + produced_next
        for org in range(o_count):
            for good in range(g_count):
                if bool(inputs.goods_is_service[good]):
                    closing_inventory[org, good] = 0.0
        quarter_purchases = np.zeros((o_count, g_count), dtype=np.float64)
        for edge in np.flatnonzero(flow > ATOL):
            quarter_purchases[int(d.edge_buyer[edge]), int(d.edge_good[edge])] += float(flow[edge])
        quarters.append(
            QuarterPlan(
                offset=offset,
                quarter=inputs.quarters[offset],
                active=True,
                purchases=quarter_purchases,
                inventory=closing_inventory.copy(),
                cash=cash.copy(),
                final_use=np.where(d.demand_final, demands_use, 0.0),
                shortfall=shortfall,
                service_produced=service_produced.sum(axis=1),
                service_used=service_used.sum(axis=1),
                service_lost=service_lost.sum(axis=1),
                service_produced_by_good=service_produced,
                service_used_by_good=service_used,
                service_lost_by_good=service_lost,
                financing=financing.copy(),
                bank_cash=bank_cash.copy(),
                goods_payment=goods_payment,
                freight_payment=freight_payment,
                objective_layers=(0.0, 0.0, 0.0, 0.0),
                certificate_index=0,
            )
        )
        inventory = closing_inventory
        shippable = closing_inventory.copy()

    # Purchases per organization/good use the edge-level flow above; the
    # first-quarter block is already reduced to the incremental request by
    # _make_decisions.
    first_purchases = np.zeros((o_count, g_count), dtype=np.float64)
    for edge in np.flatnonzero(first_flow > ATOL):
        first_purchases[int(d.edge_buyer[edge]), int(d.edge_good[edge])] += float(first_flow[edge])
    decisions = _make_decisions(inputs, first_purchases, mode="historical_rule_based")
    elapsed = time.perf_counter() - start
    max_violation = max((value for _, value in checks), default=0.0)
    status = "FEASIBLE"
    failure = ""
    if elapsed > time_limit_s:
        status = "TIMEOUT"
        failure = "rule time budget exhausted"
    elif max_violation > ATOL:
        status = "INFEASIBLE"
        failure = "conservation check failed"
    certificate = PlanningCertificate(
        schema_version=SCHEMA_VERSION,
        status=status,
        solver_status=-1,
        solver_message="historical rule: conserving sequential arithmetic",
        solver_feasible=status == "FEASIBLE",
        matrix_rows=len(checks),
        matrix_cols=0,
        nnz=0,
        row_names=tuple(name for name, _ in checks),
        row_sense=np.ones(len(checks), dtype=np.int64),
        row_rhs=np.zeros(len(checks), dtype=np.float64),
        primal=np.zeros(0),
        dual_eq=np.zeros(0),
        dual_ub=np.zeros(0),
        row_activity=np.asarray([value for _, value in checks], dtype=np.float64),
        row_residual=np.asarray([value for _, value in checks], dtype=np.float64),
        row_slack=np.zeros(len(checks), dtype=np.float64),
        layer_index=0,
        layer_objective=float(max_violation),
        wall_s=elapsed,
        input_hash=inputs.input_hash,
        constraint_hash=hashlib.sha256(b"historical_rule_based_v2").hexdigest(),
        failure_reason=failure,
    )
    matrix_hash = hashlib.sha256(
        f"{inputs.input_hash}:{first_flow.tobytes().hex()}:historical_rule_based_v2".encode()
    ).hexdigest()
    return RollingPlan(
        schema_version=SCHEMA_VERSION,
        mode="historical_rule_based",
        status=status,
        decision_quarter=inputs.quarter,
        horizon_quarters=HORIZON_QUARTERS,
        quarters=inputs.quarters,
        terminal_mask=inputs.terminal_mask,
        source_kind=inputs.source_kind,
        inputs=inputs,
        input_hash=inputs.input_hash,
        observation_hash=inputs.observation_hash,
        priority_hash=inputs.priority_hash,
        forecast_hash=inputs.forecast_hash,
        matrix_hash=matrix_hash,
        comparison_status="REFERENCE_ONLY",
        comparison_reason="historical rule is an auditable reference arm, not an optimizer",
        certificates=(certificate,),
        quarterly=tuple(quarters),
        first_quarter_decisions=decisions if status == "FEASIBLE" else (),
        first_quarter_payload_hash=_decision_payload_hash(
            decisions if status == "FEASIBLE" else ()
        ),
        objective_layers=(0.0, 0.0, 0.0, 0.0),
    )


def _rule_plan(inputs: PlanningInputs, *, time_limit_s: float) -> RollingPlan:
    return _rule_plan_v2(inputs, time_limit_s=time_limit_s)


def plan_quarter(
    inputs: PlanningInputs,
    *,
    mode: Literal["historical_rule_based", "bounded_planning", "full_information_upper_bound"],
    time_limit_s: float,
) -> RollingPlan:
    """Produce one four-quarter plan and the executable first-quarter action."""
    if type(inputs) is not PlanningInputs:
        _reject("inputs must be a concrete PlanningInputs")
    if mode not in ARMS:
        _reject(f"unknown planning mode {mode!r}")
    if not np.isfinite(time_limit_s) or time_limit_s <= 0.0:
        _reject("time_limit_s must be finite and positive")
    if mode == "full_information_upper_bound":
        if inputs.information_mode != "full_information_upper_bound":
            _reject("full-information arm requires full-information inputs")
    elif inputs.information_mode != "bounded_planning":
        _reject("rule/bounded arms require bounded inputs")
    if mode == "historical_rule_based":
        return _rule_plan(inputs, time_limit_s=time_limit_s)

    axis = _Axis(inputs)
    deadline = time.perf_counter() + float(time_limit_s)
    base_rows = _build_base_rows(axis)
    constraint_hash = base_rows.fingerprint()
    objectives, constants, _ = _objective_layers(axis)
    bounds = _bounds(axis)
    bounds_digest = _array_digest(
        np.asarray(
            [np.nan if upper is None else upper for _lower, upper in bounds],
            dtype=np.float64,
        )
    )
    objective_digest = hashlib.sha256()
    for objective in objectives:
        objective_digest.update(_array_digest(objective).encode("ascii"))
    matrix_key = (
        f"{inputs.input_hash}:{inputs.priority_hash}:{constraint_hash}:"
        f"{axis.variable_count}:{bounds_digest}:{objective_digest.hexdigest()}"
    )
    matrix_hash = hashlib.sha256(matrix_key.encode("ascii")).hexdigest()
    certificates: list[PlanningCertificate] = []
    vector: np.ndarray | None = None
    layer_values = [0.0, 0.0, 0.0, 0.0]
    rows = _Rows()
    for index in range(len(base_rows.names)):
        rows.add(
            base_rows.names[index],
            base_rows.cols[index],
            base_rows.vals[index],
            base_rows.rhs[index],
            base_rows.senses[index],
        )
    for layer in range(len(objectives)):
        current_constraint_hash = rows.fingerprint()
        a_eq, b_eq, a_ub, b_ub = rows.matrices(axis.variable_count)
        remaining = deadline - time.perf_counter()
        if remaining <= 0.0:
            certificate = _certificate(
                axis=axis,
                rows=rows,
                result=None,
                vector=None,
                status="TIMEOUT",
                message="shared planning time budget exhausted before the layer",
                feasible=False,
                layer_index=layer,
                layer_objective=float("inf"),
                wall_s=0.0,
                constraint_hash=current_constraint_hash,
                failure_reason="time budget exhausted",
            )
            certificates.append(certificate)
            return _failed_plan(
                inputs,
                mode=mode,
                status="TIMEOUT",
                certificates=tuple(certificates),
                reason="planning time budget exhausted",
            )
        solve_start = time.perf_counter()
        try:
            result = linprog(
                objectives[layer],
                A_ub=a_ub if a_ub.shape[0] else None,
                b_ub=b_ub if b_ub.shape[0] else None,
                A_eq=a_eq if a_eq.shape[0] else None,
                b_eq=b_eq if b_eq.shape[0] else None,
                bounds=bounds,
                method="highs",
                options={
                    "time_limit": float(max(remaining, 1e-6)),
                    "presolve": True,
                    "primal_feasibility_tolerance": 1e-9,
                    "dual_feasibility_tolerance": 1e-9,
                },
            )
        except Exception as exc:  # noqa: BLE001 - solver failure must be a certificate
            result = None
            solver_exception = f"{type(exc).__name__}: {exc}"
        else:
            solver_exception = ""
        solve_wall = time.perf_counter() - solve_start
        status_code = int(getattr(result, "status", 9))
        message = solver_exception if solver_exception else str(getattr(result, "message", ""))
        if result is None:
            status = "ERROR"
            feasible = False
            failure = "solver raised an exception"
            chosen = None
            candidate = None
        elif status_code == 0:
            candidate = np.asarray(result.x, dtype=np.float64)
            if candidate.shape != (axis.variable_count,) or not bool(
                np.all(np.isfinite(candidate))
            ):
                status = "ERROR"
                feasible = False
                message = "solver returned a malformed primal vector"
                failure = "malformed primal vector"
                chosen = None
            else:
                activity, residual, _slack = rows.witness(candidate)
                tolerance = np.asarray(
                    tolerance_for(activity, np.asarray(rows.rhs)), dtype=np.float64
                )
                bound_violation = 0.0
                for position, (lower, upper) in enumerate(bounds):
                    bound_violation = max(
                        bound_violation,
                        max(lower - float(candidate[position]), 0.0),
                        max(float(candidate[position]) - upper, 0.0) if upper is not None else 0.0,
                    )
                if bool(np.any(residual > tolerance)) or bound_violation > ATOL:
                    status = "ERROR"
                    feasible = False
                    message = "independently recomputed primal residual exceeds tolerance"
                    failure = "primal residual verification failed"
                    chosen = None
                else:
                    status = "FEASIBLE"
                    feasible = True
                    failure = ""
                    chosen = candidate
                    vector = candidate
        elif status_code == 2:
            status = "INFEASIBLE"
            feasible = False
            failure = "solver reported infeasible; no incumbent is executable"
            chosen = None
        elif status_code == 1:
            status = "TIMEOUT"
            feasible = False
            failure = "solver time limit reached; incumbent is diagnostic only"
            raw = getattr(result, "x", None)
            candidate = None
            if raw is not None:
                raw = np.asarray(raw, dtype=np.float64)
                if raw.shape == (axis.variable_count,) and bool(np.all(np.isfinite(raw))):
                    candidate = raw
            chosen = candidate
        else:
            status = "ERROR"
            feasible = False
            failure = "solver returned an unregistered status"
            chosen = None
        if status == "FEASIBLE" and time.perf_counter() > deadline:
            status = "TIMEOUT"
            feasible = False
            failure = "hard deadline passed after the solver returned"
            chosen = candidate
            vector = None
        layer_value = (
            float(np.dot(objectives[layer], chosen) + constants[layer])
            if chosen is not None
            else float("inf")
        )
        layer_values[layer] = layer_value
        certificate = _certificate(
            axis=axis,
            rows=rows,
            result=result,
            vector=chosen,
            status=status,
            message=message,
            feasible=feasible,
            layer_index=layer,
            layer_objective=layer_value,
            wall_s=solve_wall,
            constraint_hash=current_constraint_hash,
            failure_reason=failure,
        )
        certificates.append(certificate)
        if status != "FEASIBLE":
            return _failed_plan(
                inputs,
                mode=mode,
                status=status,
                certificates=tuple(certificates),
                reason=f"layer {layer} ended {status}: {failure}",
            )
        if layer < 3:
            # Lock the layer optimum within the accounting tolerance.
            tolerance = float(tolerance_for(layer_value, layer_value))
            rows.add_le(
                f"lex_lock[layer={layer}]",
                np.flatnonzero(objectives[layer] != 0.0),
                objectives[layer][np.flatnonzero(objectives[layer] != 0.0)],
                layer_value - constants[layer] + tolerance,
            )
    assert vector is not None
    vector = np.asarray(vector, dtype=np.float64)
    flow = vector[axis.flow_off : axis.flow_off + HORIZON_QUARTERS * axis.e_count].reshape(
        HORIZON_QUARTERS, axis.e_count
    )
    activity = vector[axis.act_off : axis.act_off + HORIZON_QUARTERS * axis.r_count].reshape(
        HORIZON_QUARTERS, axis.r_count
    )
    inventory = vector[
        axis.inv_off : axis.inv_off + HORIZON_QUARTERS * axis.o_count * axis.g_count
    ].reshape(HORIZON_QUARTERS, axis.o_count, axis.g_count)
    cash = vector[axis.cash_off : axis.cash_off + HORIZON_QUARTERS * axis.o_count].reshape(
        HORIZON_QUARTERS, axis.o_count
    )
    demand_use = vector[axis.use_off : axis.use_off + HORIZON_QUARTERS * axis.d_count].reshape(
        HORIZON_QUARTERS, axis.d_count
    )
    short = vector[axis.short_off : axis.short_off + HORIZON_QUARTERS * axis.d_count].reshape(
        HORIZON_QUARTERS, axis.d_count
    )
    financing = vector[axis.fin_off : axis.fin_off + HORIZON_QUARTERS * axis.o_count].reshape(
        HORIZON_QUARTERS, axis.o_count
    )
    bank_cash = vector[axis.bank_off : axis.bank_off + HORIZON_QUARTERS * axis.b_count].reshape(
        HORIZON_QUARTERS, axis.b_count
    )
    service_loss = vector[
        axis.sloss_off : axis.sloss_off + HORIZON_QUARTERS * axis.o_count * axis.g_count
    ].reshape(HORIZON_QUARTERS, axis.o_count, axis.g_count)
    final_use = np.zeros((HORIZON_QUARTERS, axis.d_count), dtype=np.float64)
    if axis.df_count:
        final_use[:, axis.final_indices] = demand_use[:, axis.final_indices]

    quarterly: list[QuarterPlan] = []
    purchases_all = np.zeros((HORIZON_QUARTERS, axis.o_count, axis.g_count))
    for offset in range(HORIZON_QUARTERS):
        if not inputs.terminal_mask[offset]:
            quarterly.append(_empty_quarter(offset, inputs.quarters[offset], False, axis))
            continue
        purchase = np.zeros((axis.o_count, axis.g_count), dtype=np.float64)
        goods_payment = np.zeros(axis.o_count, dtype=np.float64)
        freight_payment = np.zeros(axis.o_count, dtype=np.float64)
        service_produced_by_good = np.zeros((axis.o_count, axis.g_count), dtype=np.float64)
        service_used_by_good = np.zeros((axis.o_count, axis.g_count), dtype=np.float64)
        for edge in range(axis.e_count):
            buyer = int(axis.declarations.edge_buyer[edge])
            good = int(axis.declarations.edge_good[edge])
            purchase[buyer, good] += float(flow[offset, edge])
            goods_payment[buyer] += float(flow[offset, edge]) * float(
                inputs.prices[offset, int(axis.declarations.edge_good[edge])]
            )
            freight_payment[buyer] += float(flow[offset, edge]) * float(
                inputs.edge_freight_price[edge]
            )
        for recipe in range(axis.r_count):
            org = int(axis.declarations.recipe_org[recipe])
            output_good = int(axis.declarations.recipe_output_good[recipe])
            amount = float(activity[offset, recipe]) * float(
                axis.declarations.recipe_output_coeff[recipe]
            )
            if bool(inputs.goods_is_service[output_good]):
                service_produced_by_good[org, output_good] += amount
            start = int(axis.declarations.recipe_input_ptr[recipe])
            end = int(axis.declarations.recipe_input_ptr[recipe + 1])
            for position in range(start, end):
                input_good = int(axis.declarations.recipe_input_good[position])
                if bool(inputs.goods_is_service[input_good]):
                    service_used_by_good[org, input_good] += float(
                        activity[offset, recipe]
                    ) * float(axis.declarations.recipe_input_coeff[position])
        for org in range(axis.o_count):
            good = int(inputs.organization_service_good[org])
            if good >= 0:
                service_produced_by_good[org, good] += float(inputs.service_capacity[offset, org])
        for demand in range(axis.d_count):
            org = int(axis.declarations.demand_buyer[demand])
            good = int(axis.declarations.demand_good[demand])
            if bool(inputs.goods_is_service[good]):
                service_used_by_good[org, good] += float(demand_use[offset, demand])
        for edge in np.flatnonzero(flow[offset] > ATOL):
            good = int(inputs.edge_service_good[edge])
            carrier = int(axis.declarations.edge_transport_org[edge])
            if good >= 0 and carrier >= 0:
                service_used_by_good[carrier, good] += float(flow[offset, edge]) * float(
                    axis.declarations.edge_freight_per_unit[edge]
                )
        service_produced = service_produced_by_good.sum(axis=1)
        service_used = service_used_by_good.sum(axis=1)
        service_lost_by_good = np.array(service_loss[offset], copy=True)
        service_lost = service_lost_by_good.sum(axis=1)
        purchases_all[offset] = purchase
        quarterly.append(
            QuarterPlan(
                offset=offset,
                quarter=inputs.quarters[offset],
                active=True,
                purchases=purchase,
                inventory=inventory[offset].copy(),
                cash=cash[offset].copy(),
                final_use=final_use[offset].copy(),
                shortfall=short[offset].copy(),
                service_produced=service_produced,
                service_used=service_used,
                service_lost=service_lost,
                service_produced_by_good=service_produced_by_good,
                service_used_by_good=service_used_by_good,
                service_lost_by_good=service_lost_by_good,
                financing=financing[offset].copy(),
                bank_cash=bank_cash[offset].copy(),
                goods_payment=goods_payment,
                freight_payment=freight_payment,
                objective_layers=tuple(layer_values),
                certificate_index=len(certificates) - 1,
            )
        )
    decisions = _make_decisions(inputs, purchases_all[0], mode=mode)
    comparison_status = "COMPARABLE"
    comparison_reason = inputs.nested_reason
    if mode == "full_information_upper_bound" and not inputs.nested_bounded:
        comparison_status = "NOT_COMPARABLE"
    return RollingPlan(
        schema_version=SCHEMA_VERSION,
        mode=mode,
        status="FEASIBLE",
        decision_quarter=inputs.quarter,
        horizon_quarters=HORIZON_QUARTERS,
        quarters=inputs.quarters,
        terminal_mask=inputs.terminal_mask,
        source_kind=inputs.source_kind,
        inputs=inputs,
        input_hash=inputs.input_hash,
        observation_hash=inputs.observation_hash,
        priority_hash=inputs.priority_hash,
        forecast_hash=inputs.forecast_hash,
        matrix_hash=matrix_hash,
        comparison_status=comparison_status,
        comparison_reason=comparison_reason,
        certificates=tuple(certificates),
        quarterly=tuple(quarterly),
        first_quarter_decisions=decisions,
        first_quarter_payload_hash=_decision_payload_hash(decisions),
        objective_layers=tuple(layer_values),
    )


__all__ = [
    "PlanningCertificate",
    "QuarterPlan",
    "RollingPlan",
    "plan_quarter",
    "verify_plan_certificates",
]
