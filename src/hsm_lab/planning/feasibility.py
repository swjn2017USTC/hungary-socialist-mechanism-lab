"""H3C: explicit route, source and transport feasibility certificates.

The module is a read-only modelling layer over the real allocation boundary
exposed by :func:`hsm_lab.engine.material.tick_material`.  It never reads a
target, ticks the kernel, writes state or allocates a stock cell.  Every
certificate is a SciPy ``linprog(method="highs")`` feasibility result on the
same non-negative variable axis:

* ``x`` -- canonical real edge flow, shape ``(M,)``;
* ``u`` -- free source withdrawal, shape ``(S,)``;
* ``v`` -- free demand receipt, shape ``(D,)``.

The three levels are deliberately nested:

* ``LP-0`` -- physical quantity balance with explicit free transfer;
* ``LP-1`` -- ``u = v = 0`` plus real source release, logistics, handling and
  service-cell physical rows;
* ``LP-2`` -- LP-1 plus the real ordered cap, funding-group cash and bank
  prefunding/reserve rows.

``LP-0`` is a technical relaxation, not an executable certificate.  A feasible
solver result is accepted only after every row is independently recomputed from
the returned primal vector within the project accounting tolerance.
"""

from __future__ import annotations

import hashlib
import math
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, csr_matrix

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.engine.accounting import ATOL, tolerance_for

SCHEMA_VERSION = "hist-routing-feasibility-v1"
SOURCE_KIND = "synthetic"
SCOPE = "full_information_technical_routing_bound"
GATE_PREFIX = "HIST_H3C_ROUTING"
LEVELS: tuple[str, ...] = ("LP-0", "LP-1", "LP-2")
EQUALS = 0
AT_MOST = 1

_REQUIRED_ARRAYS = (
    "edge_id",
    "edge_source",
    "edge_destination",
    "edge_demand",
    "edge_commodity",
    "edge_stage",
    "edge_purpose",
    "edge_tier",
    "edge_unit_price",
    "edge_transport_per_unit",
    "edge_self_hauled",
    "edge_transport_org",
    "edge_transport_service_cell",
    "edge_weight",
    "demand_cell",
    "demand_gross",
    "demand_ordered",
    "demand_desired",
    "demand_active",
    "source_available",
    "stock_open",
    "import_into",
    "produced_into",
    "service_split",
    "logistics_pool",
    "handling_capacity",
    "handling_work_per_unit",
    "cell_commodity",
    "cell_stage",
    "cell_owner_kind",
    "cell_owner_id",
    "cell_pool",
    "source_valid",
    "funding_group",
    "funding_capacity",
    "buyer_bank",
    "seller_bank",
    "carrier_bank",
    "edge_buyer_id",
    "edge_carrier_id",
    "demand_purpose",
    "edge_unit_pay",
    "bank_reserves",
    "organization_cash",
    "plot_pool",
    "org_output_cell",
    "org_wholesale_cell",
    "retail_cell",
    "plot_raw_cell",
    "plot_ready_market_cell",
    "import_pool_cell",
)
_REQUIRED_SCALARS = ("tick", "quarter", "treasury_cash", "service_price", "currency")


def _reject(message: str) -> None:
    raise ResearchGateError(f"{GATE_PREFIX}: {message}")


def _frozen(
    value: Any, shape: tuple[int, ...], name: str, *, non_negative: bool = True
) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != shape:
        _reject(f"{name} shape {array.shape} does not match {shape}")
    if not bool(np.all(np.isfinite(array))):
        _reject(f"{name} contains a non-finite value")
    if non_negative and bool(np.any(array < -ATOL)):
        bad = int(np.argmin(array))
        _reject(f"{name}[{bad}]={float(array.ravel()[bad])!r} is negative")
    array = np.ascontiguousarray(array, dtype=np.float64).copy()
    array.setflags(write=False)
    return array


def _frozen_int(value: Any, shape: tuple[int, ...], name: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.int64)
    if array.shape != shape:
        _reject(f"{name} shape {array.shape} does not match {shape}")
    array = np.ascontiguousarray(array, dtype=np.int64).copy()
    array.setflags(write=False)
    return array


def _frozen_bool(value: Any, shape: tuple[int, ...], name: str) -> np.ndarray:
    array = np.asarray(value, dtype=bool)
    if array.shape != shape:
        _reject(f"{name} shape {array.shape} does not match {shape}")
    array = np.ascontiguousarray(array, dtype=bool).copy()
    array.setflags(write=False)
    return array


def _array_digest(array: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode("ascii"))
    digest.update(repr(tuple(array.shape)).encode("ascii"))
    digest.update(np.ascontiguousarray(array).tobytes())
    return digest.hexdigest()


def _hash_arrays(arrays: Mapping[str, np.ndarray], scalars: Mapping[str, Any]) -> str:
    digest = hashlib.sha256()
    for key in sorted(arrays):
        digest.update(key.encode("utf-8"))
        digest.update(_array_digest(arrays[key]).encode("ascii"))
    for key in sorted(scalars):
        digest.update(key.encode("utf-8"))
        digest.update(repr(scalars[key]).encode("utf-8"))
    return digest.hexdigest()


@dataclass(frozen=True)
class RoutingProblem:
    """One frozen allocation boundary and the complete shared variable axis."""

    schema_version: str
    tick: int
    quarter: str
    edge_id: np.ndarray
    edge_source: np.ndarray
    edge_destination: np.ndarray
    edge_demand: np.ndarray
    edge_commodity: np.ndarray
    edge_stage: np.ndarray
    edge_purpose: np.ndarray
    edge_tier: np.ndarray
    edge_unit_price: np.ndarray
    edge_transport_per_unit: np.ndarray
    edge_self_hauled: np.ndarray
    edge_transport_org: np.ndarray
    edge_transport_service_cell: np.ndarray
    edge_weight: np.ndarray
    demand_cell: np.ndarray
    demand_gross: np.ndarray
    demand_ordered: np.ndarray
    demand_desired: np.ndarray
    demand_active: np.ndarray
    demand: np.ndarray
    source_available: np.ndarray
    stock_open: np.ndarray
    import_into: np.ndarray
    produced_into: np.ndarray
    service_split: np.ndarray
    logistics_pool: np.ndarray
    handling_capacity: np.ndarray
    handling_work_per_unit: np.ndarray
    cell_commodity: np.ndarray
    cell_stage: np.ndarray
    cell_owner_kind: np.ndarray
    cell_owner_id: np.ndarray
    cell_pool: np.ndarray
    source_valid: np.ndarray
    funding_group: np.ndarray
    funding_capacity: np.ndarray
    funding_kind: tuple[str, ...]
    buyer_bank: np.ndarray
    seller_bank: np.ndarray
    carrier_bank: np.ndarray
    edge_buyer_id: np.ndarray
    edge_carrier_id: np.ndarray
    demand_purpose: np.ndarray
    edge_unit_pay: np.ndarray
    bank_reserves: np.ndarray
    organization_cash: np.ndarray
    plot_pool: np.ndarray
    treasury_cash: float
    service_price: float
    currency: str
    org_output_cell: np.ndarray
    org_wholesale_cell: np.ndarray
    retail_cell: np.ndarray
    plot_raw_cell: np.ndarray
    plot_ready_market_cell: np.ndarray
    import_pool_cell: np.ndarray
    demand_commodity: np.ndarray
    demand_stage: np.ndarray
    boundary_hash: str
    demand_hash: str
    objective_hash: str
    problem_hash: str
    variable_axis: tuple[int, int, int, int]


@dataclass(frozen=True)
class RoutingCertificate:
    """One feasibility level's solver result and independently checked rows."""

    schema_version: str
    level: str
    status: str
    solver_status: int
    solver_message: str
    solver_feasible: bool
    edge_id: np.ndarray
    x: np.ndarray
    u: np.ndarray
    v: np.ndarray
    shortfall: np.ndarray
    shortfall_total: float
    dual_ub: np.ndarray
    dual_eq: np.ndarray
    dual_lower: np.ndarray
    dual_upper: np.ndarray
    row_names: tuple[str, ...]
    row_sense: np.ndarray
    row_rhs: np.ndarray
    row_activity: np.ndarray
    row_residual: np.ndarray
    row_slack: np.ndarray
    row_fingerprints: tuple[str, ...]
    variable_count: int
    row_count: int
    nnz: int
    build_wall_s: float
    solve_wall_s: float
    problem_hash: str
    boundary_hash: str
    demand_hash: str
    objective_hash: str
    constraint_hash: str
    no_demand: bool
    free_flow: bool
    max_abs_residual: float
    source_kind: str = SOURCE_KIND
    scope: str = SCOPE
    unique_bottleneck: str = "NOT_IDENTIFIED"


@dataclass(frozen=True)
class NestedCheck:
    """Prefix/witness comparison of the three levels for one common problem."""

    nested: bool
    reason: str
    unique_bottleneck: str = "NOT_IDENTIFIED"


@dataclass(frozen=True)
class _Rows:
    names: list[str]
    senses: list[int]
    rhs: list[float]
    cols: list[np.ndarray]
    vals: list[np.ndarray]

    def add(
        self,
        name: str,
        cols: np.ndarray | list[int],
        vals: np.ndarray | list[float],
        rhs: float,
        sense: int,
    ) -> None:
        columns = np.asarray(cols, dtype=np.int64)
        values = np.asarray(vals, dtype=np.float64)
        if columns.shape != values.shape:
            raise ValueError(f"row {name} columns/values disagree")
        if float(rhs) < -ATOL or not np.isfinite(rhs):
            raise ValueError(f"row {name} has invalid rhs {rhs!r}")
        self.names.append(name)
        self.senses.append(int(sense))
        self.rhs.append(float(rhs))
        self.cols.append(columns)
        self.vals.append(values)

    def add_x(self, name: str, edge: np.ndarray, coeff: np.ndarray, rhs: float) -> None:
        self.add(name, edge, coeff, rhs, AT_MOST)

    def matrices(
        self, variable_count: int
    ) -> tuple[csr_matrix, np.ndarray, csr_matrix, np.ndarray]:
        row_count = len(self.names)
        if row_count == 0:
            empty = csr_matrix((0, variable_count), dtype=np.float64)
            return empty, np.zeros(0), empty, np.zeros(0)
        cols = np.concatenate(self.cols) if self.cols else np.zeros(0, dtype=np.int64)
        vals = np.concatenate(self.vals) if self.vals else np.zeros(0)
        rows = np.repeat(np.arange(row_count, dtype=np.int64), [c.size for c in self.cols])
        matrix = coo_matrix((vals, (rows, cols)), shape=(row_count, variable_count)).tocsr()
        sense = np.asarray(self.senses, dtype=np.int64)
        rhs = np.asarray(self.rhs, dtype=np.float64)
        eq = sense == EQUALS
        if eq.any():
            a_eq = matrix[np.flatnonzero(eq)]
            b_eq = rhs[eq]
        else:
            a_eq = csr_matrix((0, matrix.shape[1]), dtype=np.float64)
            b_eq = np.zeros(0)
        le = ~eq
        if le.any():
            a_ub = matrix[np.flatnonzero(le)]
            b_ub = rhs[le]
        else:
            a_ub = csr_matrix((0, matrix.shape[1]), dtype=np.float64)
            b_ub = np.zeros(0)
        return a_eq, b_eq, a_ub, b_ub


def _read_boundary(
    boundary: Mapping[str, Any], demand: np.ndarray | None
) -> dict[str, Any]:
    if not isinstance(boundary, Mapping):
        _reject("boundary must be a mapping")
    missing = [
        key
        for key in (*_REQUIRED_ARRAYS, *_REQUIRED_SCALARS)
        if key not in boundary
    ]
    if missing:
        _reject(f"boundary is missing required key(s) {sorted(missing)}")
    tick = int(boundary["tick"])
    if tick < 0:
        _reject("tick must be non-negative")
    quarter = boundary["quarter"]
    if not isinstance(quarter, str) or not quarter:
        _reject("quarter must be a non-empty string")
    currency = boundary["currency"]
    if not isinstance(currency, str) or not currency:
        _reject("currency must be a non-empty string")
    edge_id = _frozen_int(boundary["edge_id"], (len(boundary["edge_id"]),), "edge_id")
    edge_count = int(edge_id.shape[0])
    shape_m = (edge_count,)
    edge_source = _frozen_int(boundary["edge_source"], shape_m, "edge_source")
    edge_destination = _frozen_int(boundary["edge_destination"], shape_m, "edge_destination")
    edge_demand = _frozen_int(boundary["edge_demand"], shape_m, "edge_demand")
    edge_commodity = _frozen_int(boundary["edge_commodity"], shape_m, "edge_commodity")
    edge_stage = _frozen_int(boundary["edge_stage"], shape_m, "edge_stage")
    edge_purpose = _frozen_int(boundary["edge_purpose"], shape_m, "edge_purpose")
    edge_tier = _frozen_int(boundary["edge_tier"], shape_m, "edge_tier")
    if edge_count and bool(np.any((edge_tier < 0) | (edge_tier > 3))):
        _reject("edge_tier must lie in {0,1,2,3}")
    if int(np.unique(edge_id).size) != edge_count:
        _reject("edge_id must be unique")
    edge_unit_price = _frozen(boundary["edge_unit_price"], shape_m, "edge_unit_price")
    edge_per_unit = _frozen(
        boundary["edge_transport_per_unit"], shape_m, "edge_transport_per_unit"
    )
    edge_self_hauled = _frozen_bool(boundary["edge_self_hauled"], shape_m, "edge_self_hauled")
    edge_transport = _frozen_int(boundary["edge_transport_org"], shape_m, "edge_transport_org")
    edge_service_cell = _frozen_int(
        boundary["edge_transport_service_cell"], shape_m, "edge_transport_service_cell"
    )
    edge_weight = _frozen(boundary["edge_weight"], shape_m, "edge_weight")

    demand_count = int(len(boundary["demand_gross"]))
    demand_shape = (demand_count,)
    demand_cell = _frozen_int(boundary["demand_cell"], demand_shape, "demand_cell")
    demand_gross = _frozen(boundary["demand_gross"], demand_shape, "demand_gross")
    demand_ordered = _frozen(boundary["demand_ordered"], demand_shape, "demand_ordered")
    demand_desired = _frozen(boundary["demand_desired"], demand_shape, "demand_desired")
    demand_active = _frozen_bool(boundary["demand_active"], demand_shape, "demand_active")
    if demand_count != len(boundary["demand_desired"]):
        _reject("demand axis is inconsistent")
    if demand is None:
        request = demand_gross.copy()
    else:
        request = np.asarray(demand, dtype=np.float64)
        if request.shape != demand_shape:
            _reject(f"demand shape {request.shape} does not match {demand_shape}")
        if not bool(np.all(np.isfinite(request))):
            _reject("demand contains a non-finite value")
        if bool(np.any(request < -ATOL)):
            _reject("demand must be non-negative")
        request = np.maximum(request, 0.0)
        if bool(np.any(request > demand_gross + tolerance_for(request, demand_gross))):
            _reject("explicit demand must not exceed the full gross request")
    # The default demand is the complete gross request, including every
    # early-service input replenishment order.  Do not filter by
    # ``demand_active``: that would silently shrink the research problem.
    request = np.ascontiguousarray(request, dtype=np.float64).copy()
    request.setflags(write=False)

    cell_count = int(len(boundary["cell_commodity"]))
    shape_s = (cell_count,)
    cell_commodity = _frozen_int(boundary["cell_commodity"], shape_s, "cell_commodity")
    cell_stage = _frozen_int(boundary["cell_stage"], shape_s, "cell_stage")
    cell_owner_kind = _frozen_int(boundary["cell_owner_kind"], shape_s, "cell_owner_kind")
    cell_owner_id = _frozen_int(boundary["cell_owner_id"], shape_s, "cell_owner_id")
    cell_pool = _frozen_int(boundary["cell_pool"], shape_s, "cell_pool")
    source_available = _frozen(boundary["source_available"], shape_s, "source_available")
    stock_open = _frozen(boundary["stock_open"], shape_s, "stock_open")
    import_into = _frozen(boundary["import_into"], shape_s, "import_into")
    produced_into = _frozen(boundary["produced_into"], shape_s, "produced_into")
    source_valid = _frozen_bool(boundary["source_valid"], shape_s, "source_valid")
    service_split = _frozen(boundary["service_split"], (3,), "service_split")
    if abs(float(service_split.sum()) - 1.0) > 1e-9:
        _reject("service_split must sum to 1")

    if edge_count:
        bad = (edge_source < 0) | (edge_source >= cell_count)
        if bool(np.any(bad)):
            _reject("edge_source names a cell outside the stock axis")
        bad = (edge_destination < -1) | (edge_destination >= cell_count)
        if bool(np.any(bad)):
            _reject("edge_destination names a cell outside the stock axis")
        bad = (edge_demand < 0) | (edge_demand >= demand_count)
        if bool(np.any(bad)):
            _reject("edge_demand names a demand outside the demand axis")
        bad = (edge_commodity < 0) | (edge_stage < 0)
        if bool(np.any(bad)):
            _reject("edge commodity/stage must be non-negative")
        bad = (edge_transport < -1) | (edge_transport >= len(boundary["organization_cash"]))
        if bool(np.any(bad)):
            _reject("edge_transport_org names an organization outside the axis")
        bad = (edge_service_cell < -1) | (edge_service_cell >= cell_count)
        if bool(np.any(bad)):
            _reject("edge_transport_service_cell names a cell outside the stock axis")
        if bool(np.any((edge_self_hauled) & (edge_transport >= 0))):
            _reject("a self-hauled edge cannot also name a carrier")

    org_count = int(len(boundary["organization_cash"]))
    shape_o = (org_count,)
    logistics_pool = _frozen(boundary["logistics_pool"], shape_o, "logistics_pool")
    handling_capacity = _frozen(boundary["handling_capacity"], shape_o, "handling_capacity")
    organization_cash = _frozen(boundary["organization_cash"], shape_o, "organization_cash")
    org_output_cell = _frozen_int(boundary["org_output_cell"], shape_o, "org_output_cell")
    org_wholesale_cell = _frozen_int(boundary["org_wholesale_cell"], shape_o, "org_wholesale_cell")
    region_count = int(len(boundary["plot_pool"]))
    shape_r = (region_count,)
    plot_pool = _frozen(boundary["plot_pool"], shape_r, "plot_pool")
    plot_raw_cell = _frozen_int(boundary["plot_raw_cell"], shape_r, "plot_raw_cell")
    plot_ready_market_cell = _frozen_int(
        boundary["plot_ready_market_cell"], shape_r, "plot_ready_market_cell"
    )
    retail_width = len(boundary["retail_cell"][0]) if region_count else 0
    retail_cell = _frozen_int(
        boundary["retail_cell"], (region_count, retail_width), "retail_cell"
    )
    import_pool_cell = _frozen_int(
        boundary["import_pool_cell"], (len(boundary["import_pool_cell"]),), "import_pool_cell"
    )
    handling_work = _frozen(
        boundary["handling_work_per_unit"],
        (len(boundary["handling_work_per_unit"]),),
        "handling_work_per_unit",
    )
    funding_group = _frozen_int(
        boundary["funding_group"], (len(boundary["funding_group"]),), "funding_group"
    )
    funding_capacity = _frozen(
        boundary["funding_capacity"],
        (len(boundary["funding_capacity"]),),
        "funding_capacity",
    )
    funding_kind_raw = boundary.get("funding_kind")
    if not isinstance(funding_kind_raw, (tuple, list)) or len(funding_kind_raw) != len(
        funding_capacity
    ):
        _reject("funding_kind must align with funding_capacity")
    funding_kind = tuple(str(item) for item in funding_kind_raw)
    bank_reserves = _frozen(
        boundary["bank_reserves"], (len(boundary["bank_reserves"]),), "bank_reserves"
    )
    bank_count = int(len(bank_reserves))
    buyer_bank = _frozen_int(boundary["buyer_bank"], shape_m, "buyer_bank")
    seller_bank = _frozen_int(boundary["seller_bank"], shape_m, "seller_bank")
    carrier_bank = _frozen_int(boundary["carrier_bank"], shape_m, "carrier_bank")
    edge_buyer_id = _frozen_int(boundary["edge_buyer_id"], shape_m, "edge_buyer_id")
    edge_carrier_id = _frozen_int(boundary["edge_carrier_id"], shape_m, "edge_carrier_id")
    demand_purpose = _frozen_int(
        boundary["demand_purpose"], demand_shape, "demand_purpose"
    )
    edge_unit_pay = _frozen(boundary["edge_unit_pay"], shape_m, "edge_unit_pay")
    if bool(np.any(buyer_bank < -1)) or bool(np.any(buyer_bank >= bank_count)):
        _reject("buyer_bank is outside the bank axis")
    if bool(np.any(seller_bank < 0)) or bool(np.any(seller_bank >= bank_count)):
        _reject("seller_bank is outside the bank axis")
    if bool(np.any(carrier_bank < -1)) or bool(np.any(carrier_bank >= bank_count)):
        _reject("carrier_bank is outside the bank axis")
    if demand_count and bool(
        np.any(funding_group < 0) | np.any(funding_group >= len(funding_capacity))
    ):
        _reject("funding_group is outside the funding axis")

    if demand_count and (
        bool(np.any(demand_cell < -1)) or bool(np.any(demand_cell >= cell_count))
    ):
        _reject("demand_cell names a cell outside the stock axis")
    demand_commodity = np.full(demand_count, -1, dtype=np.int64)
    demand_stage = np.full(demand_count, -1, dtype=np.int64)
    for demand_index in range(demand_count):
        destination = int(demand_cell[demand_index])
        if destination >= 0:
            demand_commodity[demand_index] = int(cell_commodity[destination])
            demand_stage[demand_index] = int(cell_stage[destination])
        else:
            edge_rows = np.flatnonzero(edge_demand == demand_index)
            if edge_rows.size:
                demand_commodity[demand_index] = int(edge_commodity[edge_rows[0]])
                demand_stage[demand_index] = int(edge_stage[edge_rows[0]])
    demand_commodity.setflags(write=False)
    demand_stage.setflags(write=False)

    arrays = {
        "edge_id": edge_id,
        "edge_source": edge_source,
        "edge_destination": edge_destination,
        "edge_demand": edge_demand,
        "edge_commodity": edge_commodity,
        "edge_stage": edge_stage,
        "edge_purpose": edge_purpose,
        "edge_tier": edge_tier,
        "edge_unit_price": edge_unit_price,
        "edge_transport_per_unit": edge_per_unit,
        "edge_self_hauled": edge_self_hauled.astype(np.float64),
        "edge_transport_org": edge_transport,
        "edge_transport_service_cell": edge_service_cell,
        "edge_weight": edge_weight,
        "demand_cell": demand_cell,
        "demand_gross": demand_gross,
        "demand_ordered": demand_ordered,
        "demand_desired": demand_desired,
        "demand_active": demand_active.astype(np.float64),
        "source_available": source_available,
        "stock_open": stock_open,
        "import_into": import_into,
        "produced_into": produced_into,
        "service_split": service_split,
        "logistics_pool": logistics_pool,
        "handling_capacity": handling_capacity,
        "handling_work_per_unit": handling_work,
        "cell_commodity": cell_commodity,
        "cell_stage": cell_stage,
        "cell_owner_kind": cell_owner_kind,
        "cell_owner_id": cell_owner_id,
        "cell_pool": cell_pool,
        "source_valid": source_valid.astype(np.float64),
        "funding_group": funding_group,
        "funding_capacity": funding_capacity,
        "buyer_bank": buyer_bank,
        "seller_bank": seller_bank,
        "carrier_bank": carrier_bank,
        "edge_buyer_id": edge_buyer_id,
        "edge_carrier_id": edge_carrier_id,
        "demand_purpose": demand_purpose,
        "edge_unit_pay": edge_unit_pay,
        "bank_reserves": bank_reserves,
        "organization_cash": organization_cash,
        "plot_pool": plot_pool,
        "org_output_cell": org_output_cell,
        "org_wholesale_cell": org_wholesale_cell,
        "retail_cell": retail_cell,
        "plot_raw_cell": plot_raw_cell,
        "plot_ready_market_cell": plot_ready_market_cell,
        "import_pool_cell": import_pool_cell,
        "demand_commodity": demand_commodity,
        "demand_stage": demand_stage,
    }
    scalars = {
        "tick": tick,
        "quarter": quarter,
        "treasury_cash": float(boundary["treasury_cash"]),
        "service_price": float(boundary["service_price"]),
        "currency": currency,
    }
    for name, value in scalars.items():
        if name in ("treasury_cash", "service_price"):
            if not np.isfinite(value) or value < -ATOL:
                _reject(f"{name} must be finite and non-negative")
    boundary_hash = _hash_arrays(arrays, scalars)
    demand_hash = _array_digest(request)
    objective = np.zeros(int(edge_id.shape[0]) + cell_count + 2 * demand_count)
    objective[int(edge_id.shape[0]) + cell_count + demand_count :] = 1.0
    objective_hash = _array_digest(objective)
    problem_hash = hashlib.sha256(
        f"{boundary_hash}:{demand_hash}:{objective_hash}".encode("ascii")
    ).hexdigest()
    return {
        "tick": tick,
        "quarter": quarter,
        "edge_id": edge_id,
        "edge_source": edge_source,
        "edge_destination": edge_destination,
        "edge_demand": edge_demand,
        "edge_commodity": edge_commodity,
        "edge_stage": edge_stage,
        "edge_purpose": edge_purpose,
        "edge_tier": edge_tier,
        "edge_unit_price": edge_unit_price,
        "edge_transport_per_unit": edge_per_unit,
        "edge_self_hauled": edge_self_hauled,
        "edge_transport_org": edge_transport,
        "edge_transport_service_cell": edge_service_cell,
        "edge_weight": edge_weight,
        "demand_cell": demand_cell,
        "demand_gross": demand_gross,
        "demand_ordered": demand_ordered,
        "demand_desired": demand_desired,
        "demand_active": demand_active,
        "demand": request,
        "source_available": source_available,
        "stock_open": stock_open,
        "import_into": import_into,
        "produced_into": produced_into,
        "service_split": service_split,
        "logistics_pool": logistics_pool,
        "handling_capacity": handling_capacity,
        "handling_work_per_unit": handling_work,
        "cell_commodity": cell_commodity,
        "cell_stage": cell_stage,
        "cell_owner_kind": cell_owner_kind,
        "cell_owner_id": cell_owner_id,
        "cell_pool": cell_pool,
        "source_valid": source_valid,
        "funding_group": funding_group,
        "funding_capacity": funding_capacity,
        "funding_kind": funding_kind,
        "buyer_bank": buyer_bank,
        "seller_bank": seller_bank,
        "carrier_bank": carrier_bank,
        "edge_buyer_id": edge_buyer_id,
        "edge_carrier_id": edge_carrier_id,
        "demand_purpose": demand_purpose,
        "edge_unit_pay": edge_unit_pay,
        "bank_reserves": bank_reserves,
        "organization_cash": organization_cash,
        "plot_pool": plot_pool,
        "treasury_cash": scalars["treasury_cash"],
        "service_price": scalars["service_price"],
        "currency": currency,
        "org_output_cell": org_output_cell,
        "org_wholesale_cell": org_wholesale_cell,
        "retail_cell": retail_cell,
        "plot_raw_cell": plot_raw_cell,
        "plot_ready_market_cell": plot_ready_market_cell,
        "import_pool_cell": import_pool_cell,
        "demand_commodity": demand_commodity,
        "demand_stage": demand_stage,
        "boundary_hash": boundary_hash,
        "demand_hash": demand_hash,
        "objective_hash": objective_hash,
        "problem_hash": problem_hash,
        "variable_axis": (
            int(edge_id.shape[0]),
            int(cell_count),
            int(demand_count),
            int(demand_count),
        ),
    }


def build_routing_problem(
    boundary: Mapping[str, Any], *, demand: np.ndarray | None = None
) -> RoutingProblem:
    """Validate one material allocation boundary and freeze the shared axes.

    ``demand=None`` always uses the complete gross request.  An explicit
    demand vector is allowed only for a preregistered tiny sub-problem and may
    never exceed gross.
    """
    data = _read_boundary(boundary, demand)
    return RoutingProblem(schema_version=SCHEMA_VERSION, **data)


def _edge_groups(edge_demand: np.ndarray, high: int) -> list[np.ndarray]:
    groups: list[np.ndarray] = []
    for value in range(high):
        groups.append(np.flatnonzero(edge_demand == value).astype(np.int64))
    return groups


def _build_rows(problem: RoutingProblem, level: str) -> _Rows:
    if level not in LEVELS:
        _reject(f"unknown level {level!r}")
    m_count, s_count, d_count, _ = problem.variable_axis
    x_offset = 0
    u_offset = m_count
    v_offset = m_count + s_count
    shortfall_offset = v_offset + d_count
    rows = _Rows([], [], [], [], [])

    edges_by_demand = _edge_groups(problem.edge_demand, d_count)
    for demand_index, edges in enumerate(edges_by_demand):
        columns = np.concatenate(
            [
                edges + x_offset,
                np.asarray([v_offset + demand_index, shortfall_offset + demand_index]),
            ]
        )
        values = np.ones(columns.size, dtype=np.float64)
        rows.add(
            f"demand_balance[{demand_index}]",
            columns,
            values,
            float(problem.demand[demand_index]),
            EQUALS,
        )

    edges_by_source: list[list[int]] = [[] for _ in range(s_count)]
    for edge, source in enumerate(problem.edge_source.tolist()):
        edges_by_source[int(source)].append(edge)
    for source, edge_list in enumerate(edges_by_source):
        edges = np.asarray(edge_list, dtype=np.int64)
        columns = np.concatenate([edges + x_offset, np.asarray([u_offset + source])])
        values = np.ones(columns.size, dtype=np.float64)
        rows.add(
            f"source_balance[{source}]",
            columns,
            values,
            float(problem.source_available[source]),
            AT_MOST,
        )

    stage_width = max(int(problem.cell_stage.max()) if s_count else 0, 0) + 1
    source_groups = problem.cell_commodity * stage_width + problem.cell_stage
    demand_groups = problem.demand_commodity * stage_width + problem.demand_stage
    universe = sorted(
        {
            int(value)
            for value in np.concatenate([source_groups, demand_groups]).tolist()
            if int(value) >= 0
        }
    )
    for group in universe:
        sources = np.flatnonzero(source_groups == group)
        demands = np.flatnonzero(demand_groups == group)
        if not sources.size and not demands.size:
            continue
        columns = np.concatenate(
            [sources + u_offset, demands + v_offset]
        )
        values = np.concatenate(
            [np.ones(sources.size), -np.ones(demands.size)]
        )
        rows.add(f"free_pool[{group}]", columns, values, 0.0, EQUALS)

    if level == "LP-0":
        return rows

    for source, edge_list in enumerate(edges_by_source):
        if not edge_list:
            continue
        edges = np.asarray(edge_list, dtype=np.int64)
        for tier in (0, 1, 2):
            selected = edges[problem.edge_tier[edges] <= tier]
            if not selected.size:
                continue
            split = float(problem.service_split[2 if tier == 2 else 1])
            cap = (
                float(problem.stock_open[source])
                + float(problem.import_into[source])
                + float(problem.produced_into[source]) * split
            )
            rows.add_x(
                f"source_release[source={source},tier={tier}]",
                selected + x_offset,
                np.ones(selected.size),
                cap,
            )
        fallback = edges[problem.edge_tier[edges] == 3]
        if fallback.size:
            prior = edges[problem.edge_tier[edges] <= 2]
            cap = float(problem.stock_open[source]) + float(problem.import_into[source])
            rows.add_x(
                f"source_fallback[source={source}]",
                np.concatenate([prior, fallback]) + x_offset,
                np.ones(prior.size + fallback.size),
                cap,
            )

    for source, edge_list in enumerate(edges_by_source):
        if not edge_list:
            continue
        edges = np.asarray(edge_list, dtype=np.int64)
        rows.add_x(
            f"source_physical[source={source}]",
            edges + x_offset,
            np.ones(edges.size),
            float(problem.source_available[source]),
        )

    transported = (~problem.edge_self_hauled) & (problem.edge_transport_org >= 0)
    for org in range(len(problem.logistics_pool)):
        mask = transported & (problem.edge_transport_org == org)
        edges = np.flatnonzero(mask)
        if not edges.size:
            continue
        rows.add_x(
            f"logistics_pool[org={org}]",
            edges + x_offset,
            problem.edge_transport_per_unit[edges],
            float(problem.logistics_pool[org]),
        )

    for org, service_cell in enumerate(problem.org_output_cell.tolist()):
        if service_cell < 0:
            continue
        direct = problem.edge_source == int(service_cell)
        logistics = transported & (problem.edge_transport_org == org)
        direct_edges = np.flatnonzero(direct)
        logistics_edges = np.flatnonzero(logistics)
        if not direct_edges.size and not logistics_edges.size:
            continue
        columns = np.concatenate([direct_edges + x_offset, logistics_edges + x_offset])
        values = np.concatenate(
            [
                np.ones(direct_edges.size),
                problem.edge_transport_per_unit[logistics_edges],
            ]
        )
        rows.add_x(
            f"service_cell_joint[org={org},cell={int(service_cell)}]",
            columns,
            values,
            float(problem.source_available[int(service_cell)]),
        )

    org_cells = problem.cell_owner_kind == 0
    wholesale_cells = org_cells & (problem.cell_pool == 2)
    retail_cells = org_cells & (problem.cell_pool == 3)
    for org in range(len(problem.handling_capacity)):
        mask = wholesale_cells & (problem.cell_owner_id == org)
        edges = np.flatnonzero(mask[problem.edge_source])
        if edges.size:
            rows.add_x(
                f"wholesale_handling[org={org}]",
                edges + x_offset,
                problem.handling_work_per_unit[problem.edge_commodity[edges]],
                float(problem.handling_capacity[org]),
            )
        dest_ok = problem.edge_destination >= 0
        dest_retail = np.zeros(problem.edge_destination.shape[0], dtype=bool)
        dest_retail[dest_ok] = retail_cells[problem.edge_destination[dest_ok]]
        target = dest_retail & (
            problem.cell_owner_id[np.maximum(problem.edge_destination, 0)] == org
        )
        edges = np.flatnonzero(target)
        if edges.size:
            rows.add_x(
                f"retail_handling[org={org}]",
                edges + x_offset,
                problem.handling_work_per_unit[problem.edge_commodity[edges]],
                float(problem.handling_capacity[org]),
            )

    if level == "LP-1":
        return rows

    for demand_index, edges in enumerate(edges_by_demand):
        if not edges.size:
            continue
        rows.add_x(
            f"demand_ordered[{demand_index}]",
            edges + x_offset,
            np.ones(edges.size),
            float(problem.demand_ordered[demand_index]),
        )

    for group in range(len(problem.funding_capacity)):
        edges = np.flatnonzero(problem.funding_group[problem.edge_demand] == group)
        if not edges.size:
            continue
        rows.add_x(
            f"funding_group[{group}:{problem.funding_kind[group]}]",
            edges + x_offset,
            problem.edge_unit_pay[edges],
            float(problem.funding_capacity[group]),
        )

    for bank in range(len(problem.bank_reserves)):
        cross = (problem.buyer_bank == bank) & (problem.seller_bank != bank)
        edges = np.flatnonzero(cross)
        if not edges.size:
            continue
        rows.add_x(
            f"bank_prefunding[bank={bank}]",
            edges + x_offset,
            problem.edge_unit_pay[edges],
            float(problem.bank_reserves[bank]),
        )

    for bank in range(len(problem.bank_reserves)):
        columns: list[np.ndarray] = []
        values: list[np.ndarray] = []
        buyer = np.flatnonzero(problem.buyer_bank == bank)
        if buyer.size:
            columns.append(buyer + x_offset)
            values.append(problem.edge_unit_pay[buyer])
        seller = np.flatnonzero((problem.seller_bank == bank) & (problem.edge_unit_price > 0.0))
        if seller.size:
            columns.append(seller + x_offset)
            values.append(-problem.edge_unit_price[seller])
        carrier = np.flatnonzero(
            (problem.carrier_bank == bank)
            & (problem.edge_transport_per_unit * problem.service_price > 0.0)
        )
        if carrier.size:
            columns.append(carrier + x_offset)
            values.append(
                -(problem.edge_transport_per_unit[carrier] * problem.service_price)
            )
        if not columns:
            continue
        rows.add_x(
            f"bank_reserve_nonnegative[bank={bank}]",
            np.concatenate(columns),
            np.concatenate(values),
            float(problem.bank_reserves[bank]),
        )
    return rows


def _bounds(
    problem: RoutingProblem, level: str
) -> list[tuple[float, float | None]]:
    m_count, s_count, d_count, _ = problem.variable_axis
    bounds: list[tuple[float, float | None]] = [(0.0, None)] * m_count
    for source in range(s_count):
        if level == "LP-0" and bool(problem.source_valid[source]):
            bounds.append((0.0, float(problem.source_available[source])))
        else:
            bounds.append((0.0, 0.0))
    for demand_index in range(d_count):
        if level == "LP-0" and int(problem.demand_commodity[demand_index]) >= 0:
            bounds.append((0.0, float(problem.demand[demand_index])))
        else:
            bounds.append((0.0, 0.0))
    for demand_index in range(d_count):
        bounds.append((0.0, float(problem.demand[demand_index])))
    return bounds


def _row_fingerprint(
    name: str, sense: int, rhs: float, columns: np.ndarray, values: np.ndarray
) -> str:
    digest = hashlib.sha256()
    digest.update(name.encode("utf-8"))
    digest.update(str(int(sense)).encode("ascii"))
    digest.update(repr(float(rhs)).encode("ascii"))
    digest.update(columns.astype(np.int64).tobytes())
    digest.update(values.astype(np.float64).tobytes())
    return digest.hexdigest()


def _constraint_hash(rows: _Rows) -> str:
    digest = hashlib.sha256()
    for name, sense, rhs, columns, values in zip(
        rows.names, rows.senses, rows.rhs, rows.cols, rows.vals, strict=True
    ):
        digest.update(
            _row_fingerprint(name, sense, rhs, columns, values).encode("ascii")
        )
    return digest.hexdigest()


def _witness_residuals(
    rows: _Rows, variable_count: int, vector: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    activity = np.zeros(len(rows.names), dtype=np.float64)
    for index, (columns, values) in enumerate(zip(rows.cols, rows.vals, strict=True)):
        if columns.size:
            activity[index] = float(np.dot(values, vector[columns]))
    rhs = np.asarray(rows.rhs, dtype=np.float64)
    sense = np.asarray(rows.senses, dtype=np.int64)
    residual = np.where(sense == EQUALS, np.abs(activity - rhs), np.maximum(activity - rhs, 0.0))
    slack = np.where(sense == EQUALS, 0.0, np.maximum(rhs - activity, 0.0))
    return activity, residual, slack


def solve_routing_feasibility(
    problem: RoutingProblem, *, level: Literal["LP-0", "LP-1", "LP-2"], time_limit_s: float
) -> RoutingCertificate:
    """Solve one registered level and independently recheck every row."""
    if not isinstance(problem, RoutingProblem):
        _reject("problem must be a RoutingProblem")
    if level not in LEVELS:
        _reject(f"unknown level {level!r}")
    if not np.isfinite(time_limit_s) or time_limit_s <= 0.0:
        _reject("time_limit_s must be finite and positive")
    build_start = time.perf_counter()
    rows = _build_rows(problem, level)
    bounds = _bounds(problem, level)
    m_count, s_count, d_count, _ = problem.variable_axis
    variable_count = m_count + s_count + 2 * d_count
    a_eq, b_eq, a_ub, b_ub = rows.matrices(variable_count)
    build_wall = time.perf_counter() - build_start
    constraint_hash = _constraint_hash(rows)
    no_demand = bool(float(np.sum(problem.demand)) <= ATOL)
    objective = np.zeros(variable_count, dtype=np.float64)
    objective[m_count + s_count + d_count :] = 1.0
    solve_start = time.perf_counter()
    result = linprog(
        objective,
        A_ub=a_ub if a_ub.shape[0] else None,
        b_ub=b_ub if a_ub.shape[0] else None,
        A_eq=a_eq if a_eq.shape[0] else None,
        b_eq=b_eq if b_eq.shape[0] else None,
        bounds=bounds,
        method="highs",
        options={"time_limit": float(time_limit_s), "presolve": True},
    )
    solve_wall = time.perf_counter() - solve_start
    status_code = int(getattr(result, "status", 4))
    message = str(getattr(result, "message", ""))
    if status_code == 0:
        vector = np.asarray(result.x, dtype=np.float64)
        if vector.shape != (variable_count,) or not bool(np.all(np.isfinite(vector))):
            status = "ERROR"
            feasible = False
            message = "solver returned a malformed primal vector"
        else:
            activity, residual, slack = _witness_residuals(rows, variable_count, vector)
            bound_residual = 0.0
            for index, (lower, upper) in enumerate(bounds):
                bound_residual = max(
                    bound_residual,
                    max(lower - float(vector[index]), 0.0),
                    max(float(vector[index]) - upper, 0.0) if upper is not None else 0.0,
                )
            tolerance = np.asarray(tolerance_for(activity, np.asarray(rows.rhs)), dtype=np.float64)
            if bool(np.any(residual > tolerance)) or bound_residual > ATOL:
                status = "ERROR"
                feasible = False
                message = "recomputed primal residual exceeds the accounting tolerance"
            else:
                status = "FEASIBLE"
                feasible = True
    elif status_code == 2:
        status = "INFEASIBLE"
        feasible = False
    elif status_code == 1:
        status = "TIMEOUT"
        feasible = False
    else:
        status = "ERROR"
        feasible = False
    if status == "FEASIBLE":
        x = np.ascontiguousarray(vector[:m_count], dtype=np.float64).copy()
        u = np.ascontiguousarray(vector[m_count : m_count + s_count], dtype=np.float64).copy()
        v = np.ascontiguousarray(
            vector[m_count + s_count : m_count + s_count + d_count], dtype=np.float64
        ).copy()
        shortfall = np.ascontiguousarray(
            vector[m_count + s_count + d_count :], dtype=np.float64
        ).copy()
        activity, residual, slack = _witness_residuals(rows, variable_count, vector)
        max_abs = float(np.max(residual)) if residual.size else 0.0
        free_flow = bool(np.any(u > ATOL) or np.any(v > ATOL))
        x.setflags(write=False)
        u.setflags(write=False)
        v.setflags(write=False)
        shortfall.setflags(write=False)
        dual_ub = np.ascontiguousarray(
            np.asarray(result.ineqlin.marginals, dtype=np.float64)
        ).copy()
        dual_eq = np.ascontiguousarray(
            np.asarray(result.eqlin.marginals, dtype=np.float64)
        ).copy()
        dual_lower = np.ascontiguousarray(
            np.asarray(result.lower.marginals, dtype=np.float64)
        ).copy()
        dual_upper = np.ascontiguousarray(
            np.asarray(result.upper.marginals, dtype=np.float64)
        ).copy()
        for dual in (dual_ub, dual_eq, dual_lower, dual_upper):
            dual.setflags(write=False)
    else:
        x = np.zeros(0, dtype=np.float64)
        u = np.zeros(0, dtype=np.float64)
        v = np.zeros(0, dtype=np.float64)
        shortfall = np.zeros(0, dtype=np.float64)
        dual_ub = np.zeros(0, dtype=np.float64)
        dual_eq = np.zeros(0, dtype=np.float64)
        dual_lower = np.zeros(0, dtype=np.float64)
        dual_upper = np.zeros(0, dtype=np.float64)
        activity = np.zeros(0, dtype=np.float64)
        residual = np.zeros(0, dtype=np.float64)
        slack = np.zeros(0, dtype=np.float64)
        max_abs = float("inf")
        free_flow = False
    fingerprints = tuple(
        _row_fingerprint(name, sense, rhs, columns, values)
        for name, sense, rhs, columns, values in zip(
            rows.names, rows.senses, rows.rhs, rows.cols, rows.vals, strict=True
        )
    )
    return RoutingCertificate(
        schema_version=SCHEMA_VERSION,
        level=level,
        status=status,
        solver_status=status_code,
        solver_message=message,
        solver_feasible=feasible,
        edge_id=problem.edge_id,
        x=x,
        u=u,
        v=v,
        shortfall=shortfall,
        shortfall_total=float(np.sum(shortfall)) if shortfall.size else float("inf"),
        dual_ub=dual_ub,
        dual_eq=dual_eq,
        dual_lower=dual_lower,
        dual_upper=dual_upper,
        row_names=tuple(rows.names),
        row_sense=np.asarray(rows.senses, dtype=np.int64),
        row_rhs=np.asarray(rows.rhs, dtype=np.float64),
        row_activity=activity,
        row_residual=residual,
        row_slack=slack,
        row_fingerprints=fingerprints,
        variable_count=variable_count,
        row_count=len(rows.names),
        nnz=int(sum(columns.size for columns in rows.cols)),
        build_wall_s=float(build_wall),
        solve_wall_s=float(solve_wall),
        problem_hash=problem.problem_hash,
        boundary_hash=problem.boundary_hash,
        demand_hash=problem.demand_hash,
        objective_hash=problem.objective_hash,
        constraint_hash=constraint_hash,
        no_demand=no_demand,
        free_flow=free_flow,
        max_abs_residual=max_abs,
    )


def _certificate_vector(certificate: RoutingCertificate) -> np.ndarray | None:
    if certificate.status != "FEASIBLE":
        return None
    return np.concatenate(
        [certificate.x, certificate.u, certificate.v, certificate.shortfall]
    ).astype(np.float64)


def verify_certificate(
    problem: RoutingProblem, certificate: RoutingCertificate
) -> tuple[bool, str]:
    """Recheck a supplied certificate against the current common problem.

    The stored hashes, fingerprints and flags are never trusted: every matrix
    and every primal value is rebuilt/recomputed.  NaNs, non-finite derived
    values, a modified constraint hash or a mismatched row set are rejected
    before an execution status can be issued.
    """
    if not isinstance(certificate, RoutingCertificate):
        return False, "certificate is not a RoutingCertificate"
    if certificate.schema_version != SCHEMA_VERSION:
        return False, f"certificate schema {certificate.schema_version!r} is unknown"
    if certificate.status != "FEASIBLE":
        return False, f"certificate status is {certificate.status}"
    if certificate.level not in LEVELS:
        return False, f"certificate level {certificate.level!r} is unknown"
    for flag_name in ("solver_feasible", "no_demand", "free_flow"):
        if type(getattr(certificate, flag_name)) is not bool:
            return False, f"certificate {flag_name} must be a boolean"
    if certificate.solver_status != 0 or certificate.solver_feasible is not True:
        return False, "certificate solver status/flag contradicts FEASIBLE"
    for name in ("build_wall_s", "solve_wall_s", "max_abs_residual"):
        value = float(getattr(certificate, name))
        if not math.isfinite(value) or value < 0.0:
            return False, f"certificate {name} must be finite and non-negative"
    if certificate.problem_hash != problem.problem_hash:
        return False, "problem hash differs"
    if certificate.boundary_hash != problem.boundary_hash:
        return False, "boundary hash differs"
    if certificate.demand_hash != problem.demand_hash:
        return False, "demand hash differs"
    if certificate.objective_hash != problem.objective_hash:
        return False, "objective hash differs"
    if certificate.edge_id.shape != problem.edge_id.shape or not bool(
        np.array_equal(certificate.edge_id, problem.edge_id)
    ):
        return False, "canonical edge axis differs"
    expected_no_demand = bool(float(np.sum(problem.demand)) <= ATOL)
    if certificate.no_demand is not expected_no_demand:
        return False, "certificate no_demand flag does not match the problem"
    m_count, s_count, d_count, _ = problem.variable_axis
    if certificate.variable_count != m_count + s_count + 2 * d_count:
        return False, "certificate variable count differs"
    x = np.asarray(certificate.x, dtype=np.float64)
    u = np.asarray(certificate.u, dtype=np.float64)
    v = np.asarray(certificate.v, dtype=np.float64)
    shortfall = np.asarray(certificate.shortfall, dtype=np.float64)
    if (
        x.shape != (m_count,)
        or u.shape != (s_count,)
        or v.shape != (d_count,)
        or shortfall.shape != (d_count,)
    ):
        return False, "certificate x/u/v/shortfall shapes differ from the common axis"
    if (
        not bool(np.all(np.isfinite(x)))
        or not bool(np.all(np.isfinite(u)))
        or not bool(np.all(np.isfinite(v)))
        or not bool(np.all(np.isfinite(shortfall)))
    ):
        return False, "certificate x/u/v/shortfall contains a non-finite value"
    if (
        bool(np.any(x < -ATOL))
        or bool(np.any(u < -ATOL))
        or bool(np.any(v < -ATOL))
        or bool(np.any(shortfall < -ATOL))
    ):
        return False, "certificate x/u/v/shortfall contains a negative value"
    if not math.isfinite(float(certificate.shortfall_total)):
        return False, "certificate shortfall_total is non-finite"
    if abs(float(np.sum(shortfall)) - float(certificate.shortfall_total)) > ATOL:
        return False, "certificate shortfall_total does not match the shortfall vector"
    vector = np.concatenate([x, u, v, shortfall])
    rows = _build_rows(problem, certificate.level)
    expected_rows = len(rows.names)
    expected_nnz = int(sum(columns.size for columns in rows.cols))
    if certificate.row_count != expected_rows:
        return False, "certificate row count differs from the rebuilt constraints"
    if certificate.nnz != expected_nnz:
        return False, "certificate nnz differs from the rebuilt constraints"
    if certificate.constraint_hash != _constraint_hash(rows):
        return False, "certificate constraint hash differs from the rebuilt constraints"
    expected_fingerprints = tuple(
        _row_fingerprint(name, sense, rhs, columns, values)
        for name, sense, rhs, columns, values in zip(
            rows.names, rows.senses, rows.rhs, rows.cols, rows.vals, strict=True
        )
    )
    if certificate.row_fingerprints != expected_fingerprints:
        return False, "certificate row fingerprints differ from the rebuilt constraints"
    activity, residual, slack = _witness_residuals(rows, vector.size, vector)
    if not bool(np.all(np.isfinite(activity))) or not bool(np.all(np.isfinite(residual))):
        return False, "recomputed activity/residual is non-finite"
    tolerance = np.asarray(tolerance_for(activity, np.asarray(rows.rhs)), dtype=np.float64)
    if bool(np.any(residual > tolerance)):
        return False, "recomputed primal residual exceeds the accounting tolerance"
    expected_free_flow = bool(np.any(u > ATOL) or np.any(v > ATOL))
    if certificate.free_flow is not expected_free_flow:
        return False, "certificate free_flow flag contradicts its witness"
    recomputed_max_residual = float(np.max(residual)) if residual.size else 0.0
    if abs(float(certificate.max_abs_residual) - recomputed_max_residual) > float(
        tolerance_for(certificate.max_abs_residual, recomputed_max_residual)
    ):
        return False, "certificate max_abs_residual contradicts the rebuilt witness"
    if certificate.row_names != tuple(rows.names):
        return False, "stored row names differ from the rebuilt rows"
    stored_sense = np.asarray(certificate.row_sense, dtype=np.int64)
    stored_rhs = np.asarray(certificate.row_rhs, dtype=np.float64)
    rebuilt_rhs = np.asarray(rows.rhs, dtype=np.float64)
    if stored_sense.shape != rebuilt_rhs.shape or stored_rhs.shape != rebuilt_rhs.shape:
        return False, "stored row metadata has the wrong shape"
    if not bool(np.all(np.isfinite(stored_rhs))) or not bool(
        np.all(np.isfinite(rebuilt_rhs))
    ):
        return False, "stored row rhs is non-finite"
    if not bool(np.array_equal(stored_sense, np.asarray(rows.senses, dtype=np.int64))):
        return False, "stored row senses differ from the rebuilt rows"
    if bool(np.any(np.abs(stored_rhs - rebuilt_rhs) > tolerance_for(stored_rhs, rebuilt_rhs))):
        return False, "stored row rhs differs from the rebuilt rows"
    stored_activity = np.asarray(certificate.row_activity, dtype=np.float64)
    stored_residual = np.asarray(certificate.row_residual, dtype=np.float64)
    stored_slack = np.asarray(certificate.row_slack, dtype=np.float64)
    if (
        stored_activity.shape != activity.shape
        or stored_residual.shape != residual.shape
        or stored_slack.shape != slack.shape
    ):
        return False, "stored row evidence has the wrong shape"
    if (
        not bool(np.all(np.isfinite(stored_activity)))
        or not bool(np.all(np.isfinite(stored_residual)))
        or not bool(np.all(np.isfinite(stored_slack)))
    ):
        return False, "stored row evidence is non-finite"
    rebuilt_tolerance = np.asarray(tolerance_for(activity, rebuilt_rhs), dtype=np.float64)
    if bool(np.any(np.abs(stored_activity - activity) > rebuilt_tolerance)):
        return False, "stored row activity contradicts the rebuilt witness"
    if bool(np.any(np.abs(stored_residual - residual) > rebuilt_tolerance)):
        return False, "stored row residual contradicts the rebuilt witness"
    if bool(np.any(np.abs(stored_slack - slack) > rebuilt_tolerance)):
        return False, "stored row slack contradicts the rebuilt witness"
    objective = np.zeros(vector.size, dtype=np.float64)
    objective[m_count + s_count + d_count :] = 1.0
    objective_value = float(np.dot(objective, vector))
    if abs(objective_value - float(np.sum(shortfall))) > ATOL:
        return False, "certificate objective does not equal its shortfall sum"
    bounds = _bounds(problem, certificate.level)
    a_eq, b_eq, a_ub, b_ub = rows.matrices(vector.size)
    dual_ub = np.asarray(certificate.dual_ub, dtype=np.float64)
    dual_eq = np.asarray(certificate.dual_eq, dtype=np.float64)
    dual_lower = np.asarray(certificate.dual_lower, dtype=np.float64)
    dual_upper = np.asarray(certificate.dual_upper, dtype=np.float64)
    if (
        dual_ub.shape != (a_ub.shape[0],)
        or dual_eq.shape != (a_eq.shape[0],)
        or dual_lower.shape != (vector.size,)
        or dual_upper.shape != (vector.size,)
    ):
        return False, "certificate dual evidence has the wrong shape"
    for name, dual in (
        ("dual_ub", dual_ub),
        ("dual_eq", dual_eq),
        ("dual_lower", dual_lower),
        ("dual_upper", dual_upper),
    ):
        if not bool(np.all(np.isfinite(dual))):
            return False, f"certificate {name} is non-finite"
    if bool(np.any(dual_ub > ATOL)) or bool(np.any(dual_lower < -ATOL)):
        # SciPy reports the negated <= dual and the lower-bound multiplier
        # with the opposite sign; see the stationarity identity below.
        return False, "certificate dual signs are infeasible"
    if bool(np.any(dual_upper > ATOL)):
        return False, "certificate upper-bound dual is positive"
    stationarity = (
        objective
        - a_ub.T @ dual_ub
        - a_eq.T @ dual_eq
        - dual_lower
        - dual_upper
    )
    stationarity_tol = ATOL + 1e-7 * np.maximum(
        1.0, np.abs(objective) + np.abs(a_ub.T @ dual_ub) + np.abs(a_eq.T @ dual_eq)
    )
    if bool(np.any(np.abs(stationarity) > stationarity_tol)):
        return False, "certificate dual stationarity fails"
    lower = np.asarray([item[0] for item in bounds], dtype=np.float64)
    upper = np.asarray(
        [np.inf if item[1] is None else item[1] for item in bounds], dtype=np.float64
    )
    ub_slack = b_ub - a_ub @ vector
    lower_slack = vector - lower
    upper_slack = upper - vector
    if bool(np.any(np.abs(dual_ub * ub_slack) > 1e-7 * np.maximum(1.0, np.abs(ub_slack)))):
        return False, "certificate upper-constraint complementarity fails"
    if bool(
        np.any(np.abs(dual_lower * lower_slack) > 1e-7 * np.maximum(1.0, np.abs(lower_slack)))
    ):
        return False, "certificate lower-bound complementarity fails"
    finite_upper = np.isfinite(upper)
    if bool(np.any(~finite_upper & (np.abs(dual_upper) > ATOL))):
        return False, "certificate has an upper-bound dual for an infinite bound"
    if bool(
        np.any(
            np.abs(dual_upper[finite_upper] * upper_slack[finite_upper])
            > 1e-7 * np.maximum(1.0, np.abs(upper_slack[finite_upper]))
        )
    ):
        return False, "certificate upper-bound complementarity fails"
    # The KKT identity above certifies the minimum-shortfall objective without
    # invoking the optimizer again.
    for index, (lower, upper) in enumerate(bounds):
        if not np.isfinite(vector[index]):
            return False, f"variable {index} is non-finite"
        if float(vector[index]) < lower - ATOL:
            return False, f"variable {index} violates its lower bound"
        if upper is not None and float(vector[index]) > upper + ATOL:
            return False, f"variable {index} violates its upper bound"
    return True, ""


def compare_routing_certificates(
    problem: RoutingProblem, certificates: tuple[RoutingCertificate, ...]
) -> NestedCheck:
    """Check nested row prefixes and send each witness back to lower levels."""
    by_level = {certificate.level: certificate for certificate in certificates}
    if set(by_level) != set(LEVELS):
        return NestedCheck(False, "the comparison does not contain exactly LP-0/LP-1/LP-2")
    for level in LEVELS:
        certificate = by_level[level]
        if certificate.problem_hash != problem.problem_hash:
            return NestedCheck(False, f"{level} problem hash differs")
        if certificate.boundary_hash != problem.boundary_hash:
            return NestedCheck(False, f"{level} boundary hash differs")
        if certificate.demand_hash != problem.demand_hash:
            return NestedCheck(False, f"{level} demand hash differs")
        if certificate.objective_hash != problem.objective_hash:
            return NestedCheck(False, f"{level} objective hash differs")
        if certificate.variable_count != sum(problem.variable_axis):
            return NestedCheck(False, f"{level} variable axis differs")
        if certificate.edge_id.shape != problem.edge_id.shape or not bool(
            np.array_equal(certificate.edge_id, problem.edge_id)
        ):
            return NestedCheck(False, f"{level} canonical edge axis differs")
        rows = _build_rows(problem, level)
        expected_fingerprints = tuple(
            _row_fingerprint(name, sense, rhs, columns, values)
            for name, sense, rhs, columns, values in zip(
                rows.names, rows.senses, rows.rhs, rows.cols, rows.vals, strict=True
            )
        )
        if certificate.row_fingerprints != expected_fingerprints:
            return NestedCheck(False, f"{level} stored row fingerprints are not rebuilt rows")
        if certificate.constraint_hash != _constraint_hash(rows):
            return NestedCheck(False, f"{level} constraint hash is not the rebuilt hash")
        if certificate.status == "FEASIBLE":
            ok, reason = verify_certificate(problem, certificate)
            if not ok:
                return NestedCheck(False, f"{level} witness rejected: {reason}")
    lp0 = by_level["LP-0"]
    lp1 = by_level["LP-1"]
    lp2 = by_level["LP-2"]
    if lp1.row_fingerprints[: len(lp0.row_fingerprints)] != lp0.row_fingerprints:
        return NestedCheck(False, "LP-1 rows do not extend the LP-0 rows")
    if lp2.row_fingerprints[: len(lp1.row_fingerprints)] != lp1.row_fingerprints:
        return NestedCheck(False, "LP-2 rows do not extend the LP-1 rows")
    for level, lower in (("LP-1", (lp0,)), ("LP-2", (lp0, lp1))):
        certificate = by_level[level]
        vector = _certificate_vector(certificate)
        if vector is None:
            continue
        for lower_certificate in lower:
            rows = _build_rows(problem, lower_certificate.level)
            activity, residual, _ = _witness_residuals(rows, vector.size, vector)
            tolerance = np.asarray(tolerance_for(activity, np.asarray(rows.rhs)), dtype=np.float64)
            if bool(np.any(residual > tolerance)):
                return NestedCheck(
                    False,
                    f"{level} witness violates {lower_certificate.level} rows",
                )
    return NestedCheck(True, "nested row prefixes and lower-level witness checks pass")


__all__ = [
    "LEVELS",
    "NestedCheck",
    "RoutingCertificate",
    "RoutingProblem",
    "SCHEMA_VERSION",
    "build_routing_problem",
    "compare_routing_certificates",
    "solve_routing_feasibility",
    "verify_certificate",
]
