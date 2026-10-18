"""HIST_VNEXT H3A: read-only service capability/schedule/provision/use/loss metrics.

The measurement separates five quantities that the legacy kernel reports only
partly:

* nominal quarterly capability (``capacity``) from the active plan target
  (``scheduled``) and the Leontief-realised provision (``provided``);
* productive, logistics, household and other final uses;
* the authoritative expiry sink already applied by the gate
  (``InvariantSummary.expired_leftover_by_cell``).

Every number is derived from the runner-captured opening snapshot, the closing
state, the tick flows and the compiled network.  The function never ticks,
calibrates, writes state/flows/clock or touches disk.  It is never called by the
default runner: H3A is an explicitly invoked observation layer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.contract.material import PURPOSE_CODES, RoutePurpose, commodity_spec
from hsm_lab.engine.accounting import ATOL, InvariantSummary, tolerance_for
from hsm_lab.engine.network import MaterialNetwork
from hsm_lab.engine.state import MaterialState, MaterialStockSnapshot, MaterialTickFlows

SCHEMA_VERSION = "hist-service-metrics-v1"
ONTOLOGY_ID = "hist-service-semantics-v1"


@dataclass(frozen=True)
class ServiceInputUse:
    """One production input row of a same-tick service-producing activity."""

    activity_index: int
    input_index: int
    commodity_id: str
    unit: str
    used: float


@dataclass(frozen=True)
class HousingStockMeasurement:
    """Regional dwelling stock and this tick's completion/allocation flows."""

    region_id: str
    unit: str
    opening_stock: float
    closing_stock: float
    formal_completed: float
    private_completed: float
    allocated: float


@dataclass(frozen=True)
class ServiceCommodityMeasurement:
    """Capability, schedule, provision, use and loss of one service commodity."""

    commodity_id: str
    unit: str
    capacity: float
    scheduled: float
    provided: float
    unscheduled_capacity: float
    schedule_shortfall: float
    opening: float
    imports: float
    used_productive: float
    used_logistics: float
    used_household: float
    used_other: float
    exports: float
    lost: float
    closing: float
    balance_residual: float


@dataclass(frozen=True)
class ServiceTickMeasurement:
    """The complete H3A service measurement of one admitted tick."""

    tick: int
    quarter: str
    services: tuple[ServiceCommodityMeasurement, ...]
    inputs: tuple[ServiceInputUse, ...]
    housing: tuple[HousingStockMeasurement, ...]
    legacy_expired_services: float
    schema_version: str = SCHEMA_VERSION
    ontology_id: str = ONTOLOGY_ID


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
        index = int(np.argmin(array))
        _reject(f"{name}[{index}]={float(array.ravel()[index])!r} is negative")
    return array


def _index_array(name: str, value: object, shape: tuple[int, ...]) -> np.ndarray:
    array = np.asarray(value, dtype=np.int64)
    if array.shape != shape:
        _reject(f"{name} shape {array.shape} does not match {shape}")
    return array


def _sum_by_commodity(
    values: np.ndarray, cell_commodity: np.ndarray, commodity_count: int
) -> np.ndarray:
    return np.bincount(
        cell_commodity,
        weights=np.asarray(values, dtype=np.float64),
        minlength=commodity_count,
    )


def _validate_boundary(
    opening: MaterialStockSnapshot,
    state: MaterialState,
    flows: MaterialTickFlows,
    network: MaterialNetwork,
    invariant_summary: InvariantSummary,
) -> tuple[int, int, int, int, int, int, int, np.ndarray, np.ndarray]:
    cell_count = int(np.asarray(network.cell_commodity).shape[0])
    commodity_count = len(network.commodity_ids)
    activity_count = int(np.asarray(network.activity_kind).shape[0])
    input_count = int(np.asarray(network.input_cell).shape[0])
    demand_count = int(np.asarray(network.demand_cell).shape[0])
    edge_count = int(np.asarray(network.edge_source_cell).shape[0])
    region_count = len(network.region_ids)
    household_count = int(np.asarray(state.household_id).shape[0])
    organization_count = int(np.asarray(state.organization_id).shape[0])

    if not (
        int(opening.completed_ticks) == int(flows.tick) == int(state.completed_ticks)
    ):
        _reject(
            "the measurement must run after the gate and before the clock advance: "
            f"opening.completed_ticks={opening.completed_ticks!r}, "
            f"flows.tick={flows.tick!r}, state.completed_ticks={state.completed_ticks!r}"
        )
    if not isinstance(flows.quarter, str) or not flows.quarter:
        _reject(f"flows.quarter must be a non-empty string, got {flows.quarter!r}")

    cell_commodity = _index_array(
        "network.cell_commodity", network.cell_commodity, (cell_count,)
    )
    if cell_count and (
        int(cell_commodity.min()) < 0 or int(cell_commodity.max()) >= commodity_count
    ):
        _reject("network.cell_commodity contains an out-of-axis commodity index")

    # Resolve every declared commodity through the frozen registry (raises
    # ConfigError for an unknown id before any measurement is attempted).
    for commodity_id in network.commodity_ids:
        commodity_spec(commodity_id)

    input_cell = _index_array("network.input_cell", network.input_cell, (input_count,))
    demand_cell = _index_array("network.demand_cell", network.demand_cell, (demand_count,))
    _index_array("network.demand_input_index", network.demand_input_index, (demand_count,))
    _index_array("network.demand_purpose", network.demand_purpose, (demand_count,))
    _index_array("network.edge_purpose", network.edge_purpose, (edge_count,))
    edge_source_cell = _index_array(
        "network.edge_source_cell", network.edge_source_cell, (edge_count,)
    )
    edge_destination_cell = _index_array(
        "network.edge_destination_cell", network.edge_destination_cell, (edge_count,)
    )
    edge_transport_service_cell = _index_array(
        "network.edge_transport_service_cell",
        network.edge_transport_service_cell,
        (edge_count,),
    )
    edge_demand = _index_array("network.edge_demand", network.edge_demand, (edge_count,))
    for name, indices, limit in (
        ("network.input_cell", input_cell, cell_count),
        ("network.demand_cell", demand_cell, cell_count),
        ("network.edge_source_cell", edge_source_cell, cell_count),
        ("network.edge_destination_cell", edge_destination_cell, cell_count),
        ("network.edge_transport_service_cell", edge_transport_service_cell, cell_count),
        ("network.edge_demand", edge_demand, demand_count),
    ):
        valid = indices[indices >= 0]
        if valid.size and int(valid.max()) >= limit:
            _reject(f"{name} contains an out-of-axis index")

    _float_array(
        "opening.stock_value", opening.stock_value, (cell_count,), non_negative=True
    )
    _float_array("state.stock_value", state.stock_value, (cell_count,), non_negative=True)
    activity_org = _index_array(
        "network.activity_org_index", network.activity_org_index, (activity_count,)
    )
    if activity_org.size:
        valid_org = activity_org[activity_org >= 0]
        if valid_org.size and int(valid_org.max()) >= organization_count:
            _reject("network.activity_org_index contains an out-of-axis organization")
    _float_array(
        "opening.organization_capacity",
        opening.organization_capacity,
        (organization_count,),
        non_negative=True,
    )
    _float_array(
        "opening.dwelling_stock", opening.dwelling_stock, (region_count,), non_negative=True
    )
    _float_array(
        "state.dwelling_stock", state.dwelling_stock, (region_count,), non_negative=True
    )
    _float_array(
        "state.household_weight", state.household_weight, (household_count,), non_negative=True
    )
    household_region = _index_array(
        "state.household_region", state.household_region, (household_count,)
    )
    if household_region.size and (
        int(household_region.min()) < 0 or int(household_region.max()) >= region_count
    ):
        _reject("state.household_region contains an out-of-axis region")
    _float_array(
        "flows.activity_target", flows.activity_target, (activity_count,), non_negative=True
    )
    _float_array(
        "flows.activity_realized", flows.activity_realized, (activity_count,), non_negative=True
    )
    _float_array("flows.used", flows.used, (demand_count,), non_negative=True)
    _float_array("flows.delivered", flows.delivered, (demand_count,), non_negative=True)
    _float_array(
        "flows.second_input_used", flows.second_input_used, (cell_count,), non_negative=True
    )
    _float_array("flows.imports", flows.imports, (commodity_count,), non_negative=True)
    _float_array("flows.cmea_exports", flows.cmea_exports, (commodity_count,), non_negative=True)
    _float_array(
        "flows.convertible_exports",
        flows.convertible_exports,
        (commodity_count,),
        non_negative=True,
    )
    _float_array(
        "flows.edge_delivered", flows.edge_delivered, (edge_count,), non_negative=True
    )
    _float_array(
        "flows.edge_service_used", flows.edge_service_used, (edge_count,), non_negative=True
    )
    _float_array(
        "flows.private_completed", flows.private_completed, (household_count,), non_negative=True
    )
    _float_array(
        "flows.housing_allocated", flows.housing_allocated, (household_count,), non_negative=True
    )

    legacy_expired = float(flows.expired_services)
    if not np.isfinite(legacy_expired) or legacy_expired < -ATOL:
        _reject(f"flows.expired_services={legacy_expired!r} is not a valid scalar sink")

    for ratio_name in ("max_material_tolerance_ratio", "max_finance_tolerance_ratio"):
        ratio = float(getattr(invariant_summary, ratio_name))
        if not np.isfinite(ratio) or ratio > 1.0:
            _reject(f"invariant_summary.{ratio_name}={ratio!r} does not prove a passed gate")
    for residual_name in ("max_material_abs_residual", "max_finance_abs_residual"):
        residual = float(getattr(invariant_summary, residual_name))
        if not np.isfinite(residual):
            _reject(f"invariant_summary.{residual_name} is not finite")

    expired = _float_array(
        "invariant_summary.expired_leftover_by_cell",
        invariant_summary.expired_leftover_by_cell,
        (cell_count,),
        non_negative=True,
    )
    return (
        cell_count,
        commodity_count,
        activity_count,
        input_count,
        demand_count,
        edge_count,
        region_count,
        cell_commodity,
        expired,
    )


def measure_service_tick(
    opening: MaterialStockSnapshot,
    state: MaterialState,
    flows: MaterialTickFlows,
    network: MaterialNetwork,
    invariant_summary: InvariantSummary,
) -> ServiceTickMeasurement:
    """Measure one gated service tick without mutating or copying kernel state."""
    (
        cell_count,
        commodity_count,
        activity_count,
        input_count,
        demand_count,
        edge_count,
        region_count,
        cell_commodity,
        expired_by_cell,
    ) = _validate_boundary(opening, state, flows, network, invariant_summary)

    stock_open = np.asarray(opening.stock_value, dtype=np.float64)
    stock_close = np.asarray(state.stock_value, dtype=np.float64)
    activity_org = _index_array(
        "network.activity_org_index", network.activity_org_index, (activity_count,)
    )
    activity_capacity = np.asarray(network.activity_capacity, dtype=np.float64).copy()
    output_activity = np.asarray(activity_org, dtype=np.int64)
    valid_org = output_activity >= 0
    if bool(np.any(valid_org)):
        organization_capacity = np.asarray(
            opening.organization_capacity, dtype=np.float64
        )
        activity_capacity[valid_org] = organization_capacity[output_activity[valid_org]]

    matrix_b = network.B
    capacity_by_cell = np.asarray(matrix_b.T @ activity_capacity, dtype=np.float64)
    scheduled_by_cell = np.asarray(matrix_b.T @ np.asarray(flows.activity_target, dtype=np.float64))
    provided_by_cell = np.asarray(
        matrix_b.T @ np.asarray(flows.activity_realized, dtype=np.float64)
    )
    capacity_by_g = _sum_by_commodity(capacity_by_cell, cell_commodity, commodity_count)
    scheduled_by_g = _sum_by_commodity(scheduled_by_cell, cell_commodity, commodity_count)
    provided_by_g = _sum_by_commodity(provided_by_cell, cell_commodity, commodity_count)

    nonstockable = np.asarray(
        [not commodity_spec(commodity_id).stockable for commodity_id in network.commodity_ids],
        dtype=bool,
    )
    service_cells = np.flatnonzero(nonstockable[cell_commodity])
    service_indices = [g for g in range(commodity_count) if nonstockable[g]]
    missing_cells = [
        network.commodity_ids[g] for g in service_indices if not np.any(cell_commodity == g)
    ]
    if missing_cells:
        _reject(
            "declared non-stockable service(s) have no stock cell: "
            + ", ".join(repr(commodity_id) for commodity_id in missing_cells)
        )

    # --- productive use: each K row is one production input ------------------
    used_by_k = np.full(input_count, np.nan, dtype=np.float64)
    for demand_index in range(demand_count):
        input_index = int(network.demand_input_index[demand_index])
        if input_index < 0:
            continue
        if input_index >= input_count:
            _reject(f"demand cell {demand_index} references input row {input_index} out of axis")
        if np.isfinite(used_by_k[input_index]):
            _reject(f"input row {input_index} is referenced by more than one demand cell")
        used_by_k[input_index] = float(flows.used[demand_index])
    if bool(np.any(~np.isfinite(used_by_k))):
        missing = np.flatnonzero(~np.isfinite(used_by_k))
        _reject(f"input rows {missing.tolist()} have no matching demand cell")

    input_cell = np.asarray(network.input_cell, dtype=np.int64)
    used_productive_by_g = np.zeros(commodity_count, dtype=np.float64)
    for input_index in range(input_count):
        g = int(cell_commodity[input_cell[input_index]])
        if nonstockable[g]:
            used_productive_by_g[g] += float(used_by_k[input_index])

    # --- logistics use: only declared carrier service cells -------------------
    edge_service_used = np.asarray(flows.edge_service_used, dtype=np.float64)
    transport_cell = np.asarray(network.edge_transport_service_cell, dtype=np.int64)
    used_logistics_by_g = np.zeros(commodity_count, dtype=np.float64)
    for edge_index in range(edge_count):
        used = float(edge_service_used[edge_index])
        if used <= 0.0:
            continue
        carrier_cell = int(transport_cell[edge_index])
        if carrier_cell < 0:
            _reject(f"edge {edge_index} consumes logistics without a carrier service cell")
        carrier_commodity = int(cell_commodity[carrier_cell])
        if not nonstockable[carrier_commodity]:
            _reject(
                f"edge {edge_index} consumes logistics from stockable commodity "
                f"{network.commodity_ids[carrier_commodity]!r}"
            )
        used_logistics_by_g[carrier_commodity] += used

    # --- household use: boundary edges by source commodity --------------------
    household_purpose = PURPOSE_CODES[RoutePurpose.HOUSEHOLD]
    edge_purpose = np.asarray(network.edge_purpose, dtype=np.int64)
    edge_source_cell = np.asarray(network.edge_source_cell, dtype=np.int64)
    edge_delivered = np.asarray(flows.edge_delivered, dtype=np.float64)
    used_household_by_g = np.zeros(commodity_count, dtype=np.float64)
    boundary_purposes = {
        PURPOSE_CODES[RoutePurpose.HOUSEHOLD],
        PURPOSE_CODES[RoutePurpose.HOUSING],
        PURPOSE_CODES[RoutePurpose.EXPORT_CMEA],
        PURPOSE_CODES[RoutePurpose.EXPORT_CONVERTIBLE],
    }
    edge_destination_cell = np.asarray(network.edge_destination_cell, dtype=np.int64)
    for edge_index in range(edge_count):
        source_cell = int(edge_source_cell[edge_index])
        source_commodity = int(cell_commodity[source_cell])
        if not nonstockable[source_commodity]:
            continue
        purpose = int(edge_purpose[edge_index])
        if int(edge_destination_cell[edge_index]) < 0 and purpose not in boundary_purposes:
            _reject(
                f"service commodity {network.commodity_ids[source_commodity]!r} leaves through "
                f"uncovered boundary purpose code {purpose}"
            )
        if purpose == household_purpose:
            used_household_by_g[source_commodity] += float(edge_delivered[edge_index])

    # --- other use: second economy, investment installation, housing ----------
    used_other_by_g = np.zeros(commodity_count, dtype=np.float64)
    second_input_used = np.asarray(flows.second_input_used, dtype=np.float64)
    for cell in service_cells:
        used_other_by_g[int(cell_commodity[cell])] += float(second_input_used[cell])

    investment_purpose = PURPOSE_CODES[RoutePurpose.INVESTMENT]
    housing_purpose = PURPOSE_CODES[RoutePurpose.HOUSING]
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    for demand_index in range(demand_count):
        purpose = int(demand_purpose[demand_index])
        if purpose == investment_purpose:
            destination = int(demand_cell[demand_index])
            if destination >= 0:
                g = int(cell_commodity[destination])
                if nonstockable[g]:
                    used_other_by_g[g] += float(flows.used[demand_index])
        elif purpose == housing_purpose:
            destination = int(demand_cell[demand_index])
            if destination < 0:
                # A housing boundary demand has no destination cell; attribute
                # its delivered construction to a non-stockable source commodity.
                housing_edges = np.flatnonzero(
                    edge_purpose == housing_purpose
                )
                for edge_index in housing_edges:
                    if int(network.edge_demand[edge_index]) != demand_index:
                        continue
                    source_commodity = int(cell_commodity[int(edge_source_cell[edge_index])])
                    if nonstockable[source_commodity]:
                        used_other_by_g[source_commodity] += float(edge_delivered[edge_index])

    # --- stocks, trade and the authoritative expiry sink ---------------------
    opening_by_g = _sum_by_commodity(stock_open, cell_commodity, commodity_count)
    closing_by_g = _sum_by_commodity(stock_close, cell_commodity, commodity_count)
    imports_by_g = np.asarray(flows.imports, dtype=np.float64)
    exports_by_g = np.asarray(flows.cmea_exports, dtype=np.float64) + np.asarray(
        flows.convertible_exports, dtype=np.float64
    )
    lost_by_g = _sum_by_commodity(expired_by_cell, cell_commodity, commodity_count)

    expired_total = float(np.sum(expired_by_cell))
    legacy_expired = float(flows.expired_services)
    if abs(expired_total - legacy_expired) > float(tolerance_for(expired_total, legacy_expired)):
        _reject(
            "the invariant summary expiry sink does not reconcile with flows.expired_services: "
            f"{expired_total!r} vs {legacy_expired!r}"
        )

    # --- per-service commodity report ----------------------------------------
    services: list[ServiceCommodityMeasurement] = []
    for g in service_indices:
        commodity_id = network.commodity_ids[g]
        spec = commodity_spec(commodity_id)
        capacity = float(capacity_by_g[g])
        scheduled = float(scheduled_by_g[g])
        provided = float(provided_by_g[g])
        unscheduled = capacity - scheduled
        shortfall = scheduled - provided
        if unscheduled < -float(tolerance_for(capacity, scheduled)):
            _reject(
                f"{commodity_id} in {flows.quarter}: scheduled={scheduled!r} exceeds "
                f"capacity={capacity!r}"
            )
        if shortfall < -float(tolerance_for(scheduled, provided)):
            _reject(
                f"{commodity_id} in {flows.quarter}: provided={provided!r} exceeds "
                f"scheduled={scheduled!r}"
            )
        components = {
            "opening": float(opening_by_g[g]),
            "imports": float(imports_by_g[g]),
            "provided": provided,
            "used_productive": float(used_productive_by_g[g]),
            "used_logistics": float(used_logistics_by_g[g]),
            "used_household": float(used_household_by_g[g]),
            "used_other": float(used_other_by_g[g]),
            "exports": float(exports_by_g[g]),
            "lost": float(lost_by_g[g]),
            "closing": float(closing_by_g[g]),
        }
        for name, value in components.items():
            if value < -ATOL:
                _reject(f"{commodity_id} in {flows.quarter}: {name}={value!r} is negative")
        lhs = components["opening"] + components["provided"] + components["imports"]
        rhs = (
            components["used_productive"]
            + components["used_logistics"]
            + components["used_household"]
            + components["used_other"]
            + components["exports"]
            + components["lost"]
            + components["closing"]
        )
        residual = lhs - rhs
        if abs(residual) > float(tolerance_for(lhs, rhs)):
            _reject(
                f"{commodity_id} in {flows.quarter}: service balance does not close "
                f"(opening+provided+imports={lhs!r}, uses+exports+lost+closing={rhs!r}, "
                f"residual={residual!r})"
            )
        services.append(
            ServiceCommodityMeasurement(
                commodity_id=commodity_id,
                unit=spec.unit,
                capacity=capacity,
                scheduled=scheduled,
                provided=provided,
                unscheduled_capacity=unscheduled,
                schedule_shortfall=shortfall,
                opening=components["opening"],
                imports=components["imports"],
                used_productive=components["used_productive"],
                used_logistics=components["used_logistics"],
                used_household=components["used_household"],
                used_other=components["used_other"],
                exports=components["exports"],
                lost=components["lost"],
                closing=components["closing"],
                balance_residual=residual,
            )
        )

    # --- production inputs of service-producing activities --------------------
    matrix_a = network.A
    matrix_b = network.B
    produced_services = np.zeros(activity_count, dtype=bool)
    for activity_index in range(activity_count):
        start = int(matrix_b.indptr[activity_index])
        end = int(matrix_b.indptr[activity_index + 1])
        cells = np.asarray(matrix_b.indices[start:end], dtype=np.int64)
        if cells.size and bool(np.any(nonstockable[cell_commodity[cells]])):
            produced_services[activity_index] = True

    inputs: list[ServiceInputUse] = []
    for activity_index in range(activity_count):
        if not produced_services[activity_index]:
            continue
        start = int(matrix_a.indptr[activity_index])
        end = int(matrix_a.indptr[activity_index + 1])
        for input_index in np.asarray(matrix_a.indices[start:end], dtype=np.int64):
            cell = int(input_cell[int(input_index)])
            commodity_id = network.commodity_ids[int(cell_commodity[cell])]
            inputs.append(
                ServiceInputUse(
                    activity_index=int(activity_index),
                    input_index=int(input_index),
                    commodity_id=commodity_id,
                    unit=commodity_spec(commodity_id).unit,
                    used=float(used_by_k[int(input_index)]),
                )
            )

    # --- housing: an independent dwelling stock, never a quarterly service ---
    dwelling_open = np.asarray(opening.dwelling_stock, dtype=np.float64)
    dwelling_close = np.asarray(state.dwelling_stock, dtype=np.float64)
    household_weight = np.asarray(state.household_weight, dtype=np.float64)
    household_region = np.asarray(state.household_region, dtype=np.int64)
    private_completed = np.bincount(
        household_region,
        weights=household_weight * np.asarray(flows.private_completed, dtype=np.float64),
        minlength=region_count,
    )
    allocated = np.bincount(
        household_region,
        weights=household_weight * np.asarray(flows.housing_allocated, dtype=np.float64),
        minlength=region_count,
    )
    housing_demands = np.flatnonzero(np.asarray(network.demand_purpose) == housing_purpose)
    if housing_demands.size != region_count:
        _reject(
            f"housing demand cells {housing_demands.size} do not match regions {region_count}"
        )
    if housing_demands.size > 1 and not bool(np.all(np.diff(housing_demands) > 0)):
        _reject("housing demand cells are not in region order")
    formal_completed = np.zeros(region_count, dtype=np.float64)
    for region in range(region_count):
        demand_index = int(housing_demands[region])
        formal_completed[region] = float(flows.delivered[demand_index])

    housing: list[HousingStockMeasurement] = []
    for region in range(region_count):
        expected_delta = float(formal_completed[region] + private_completed[region])
        actual_delta = float(dwelling_close[region] - dwelling_open[region])
        if abs(actual_delta - expected_delta) > float(tolerance_for(actual_delta, expected_delta)):
            _reject(
                f"region {network.region_ids[region]} in {flows.quarter}: dwelling delta "
                f"{actual_delta!r} does not equal formal+private completion {expected_delta!r}"
            )
        housing.append(
            HousingStockMeasurement(
                region_id=network.region_ids[region],
                unit="dwelling_unit",
                opening_stock=float(dwelling_open[region]),
                closing_stock=float(dwelling_close[region]),
                formal_completed=float(formal_completed[region]),
                private_completed=float(private_completed[region]),
                allocated=float(allocated[region]),
            )
        )

    return ServiceTickMeasurement(
        tick=int(flows.tick),
        quarter=str(flows.quarter),
        services=tuple(services),
        inputs=tuple(inputs),
        housing=tuple(housing),
        legacy_expired_services=legacy_expired,
    )


__all__ = [
    "ONTOLOGY_ID",
    "SCHEMA_VERSION",
    "HousingStockMeasurement",
    "ServiceCommodityMeasurement",
    "ServiceInputUse",
    "ServiceTickMeasurement",
    "measure_service_tick",
]
