"""P03 durable and housing stocks (plan E/F).

Durable ownership is a *stock* held per household (fractional ownership over the
synthetic cohort), never a flow and never a second regional stock.  Housing is an
independent stock: per-household dwelling access plus a regional vacant pool, with
``dwelling_stock = sum(weight * access) + vacant`` maintained every tick.
"""

from __future__ import annotations

import numpy as np

from hsm_lab.contract.households import DURABLE_IDS, H_INDEX, HouseholdParameters
from hsm_lab.engine.state import MaterialState, MaterialStockSnapshot, MaterialTickFlows


def durable_desire(state: MaterialState, parameters: HouseholdParameters) -> np.ndarray:
    """Desired durable units per household (E3): ``(N, D)`` request backlog gap."""
    durables = parameters.durables
    owned = np.asarray(state.household_durable_owned, dtype=np.float64)
    backlog = np.asarray(state.household_durable_backlog, dtype=np.float64)
    hazard = np.asarray(durables.retirement_hazard, dtype=np.float64)
    raw_retired = owned * hazard
    repair_credit = np.asarray(state.household_durable_repair_credit, dtype=np.float64)
    avoided = np.minimum(raw_retired, 0.5 * repair_credit)
    effective_retired = np.maximum(raw_retired - avoided, 0.0)
    surviving = np.maximum(owned - effective_retired, 0.0)

    last_income = np.asarray(state.household_last_income, dtype=np.float64)
    reference = np.asarray(state.household_reference_income, dtype=np.float64)
    z = np.maximum(
        np.log(np.maximum(last_income, parameters.eps) / np.maximum(reference, parameters.eps)), 0.0
    )
    region = np.asarray(state.household_region, dtype=np.int64)
    weight = np.asarray(state.household_weight, dtype=np.float64)
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    peer_num = np.bincount(region, weights=weight * owned.sum(axis=1), minlength=region_count)
    peer_den = np.bincount(region, weights=weight, minlength=region_count)
    peer = peer_num / np.maximum(peer_den, parameters.eps)
    expectation_real = np.asarray(state.household_expectation, dtype=np.float64)[:, 4]
    target = np.clip(
        np.asarray(durables.aspiration_base, dtype=np.float64)[None, :]
        + durables.aspiration_income_weight * z[:, None]
        + durables.aspiration_peer_weight * peer[region, None] / max(len(DURABLE_IDS), 1)
        + durables.aspiration_expectation_weight * expectation_real[:, None],
        0.0,
        1.0,
    )
    diffusion = np.minimum(
        durables.new_intention_per_quarter,
        np.maximum(target - owned - backlog, 0.0),
    )
    request = np.minimum(1.0 - surviving, backlog + diffusion + effective_retired)
    request = np.maximum(request, 0.0)
    state.household_durable_backlog = np.where(request > 0.0, request, backlog)
    return np.asarray(request, dtype=np.float64)


def update_durable_stocks(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: HouseholdParameters,
    opening: MaterialStockSnapshot,
) -> None:
    """Advance durable ownership/age/backlog/wait from realised purchases (E)."""
    durables = parameters.durables
    owned_open = np.asarray(opening.household_durable_owned, dtype=np.float64)
    acquired = np.asarray(flows.durable_acquired, dtype=np.float64)
    hazard = np.asarray(durables.retirement_hazard, dtype=np.float64)
    raw_retired = owned_open * hazard
    repair_credit = np.asarray(state.household_durable_repair_credit, dtype=np.float64)
    avoided = np.minimum(raw_retired, 0.5 * repair_credit)
    effective_retired = np.maximum(raw_retired - avoided, 0.0)
    surviving = np.maximum(owned_open - effective_retired, 0.0)
    owned = surviving + acquired
    age_open = np.asarray(state.household_durable_age, dtype=np.float64)
    age = np.where(
        owned > 0.0, (age_open * surviving + 0.0 * acquired) / np.maximum(owned, 1e-12) + 1.0, 0.0
    )

    state.household_durable_owned = owned
    state.household_durable_age = age
    flows.durable_retired = effective_retired

    repair_g = H_INDEX["repair_services"]
    maintenance = np.asarray(flows.household_realized_h, dtype=np.float64)[:, repair_g]
    state.household_durable_repair_credit = np.minimum(
        owned, maintenance[:, None] / max(owned.shape[1], 1)
    )

    backlog = np.asarray(state.household_durable_backlog, dtype=np.float64) - acquired
    backlog = np.maximum(backlog, 0.0)
    state.household_durable_backlog = backlog
    wait = np.asarray(state.household_durable_wait, dtype=np.int32)
    wait = np.where(backlog > 1e-9, wait + 1, 0).astype(np.int32)
    state.household_durable_wait = wait


def housing_gap(state: MaterialState, parameters: HouseholdParameters) -> np.ndarray:
    """Per-household desired-minus-actual dwelling access (F2)."""
    access = np.asarray(state.household_dwelling_access, dtype=np.float64)
    size = np.asarray(state.household_size, dtype=np.float64)
    desired = np.maximum(1.0, size / parameters.housing.persons_per_dwelling)
    return np.asarray(np.maximum(desired - access, 0.0), dtype=np.float64)


def overcrowding(state: MaterialState, parameters: HouseholdParameters) -> np.ndarray:
    """Ratio ``size / (persons_per_dwelling * access) - 1`` floored at zero (F2)."""
    access = np.asarray(state.household_dwelling_access, dtype=np.float64)
    size = np.asarray(state.household_size, dtype=np.float64)
    safe = np.maximum(access, parameters.eps)
    return np.maximum(size / (parameters.housing.persons_per_dwelling * safe) - 1.0, 0.0)


def allocate_housing(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: HouseholdParameters,
) -> None:
    """Distribute each region's vacant dwellings by overcrowding/waiting priority (F3)."""
    region = np.asarray(state.household_region, dtype=np.int64)
    weight = np.asarray(state.household_weight, dtype=np.float64)
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    vacant = np.asarray(state.housing_vacant, dtype=np.float64)
    gap = housing_gap(state, parameters)
    access = np.asarray(state.household_dwelling_access, dtype=np.float64)
    wait = np.asarray(state.household_housing_wait, dtype=np.int32)
    over = overcrowding(state, parameters)
    allocated = np.zeros(weight.size, dtype=np.float64)
    for r in range(region_count):
        if vacant[r] <= 0.0:
            continue
        mask = region == r
        if not mask.any():
            continue
        need = gap[mask]
        if not np.any(need > 0.0):
            continue
        severe = (over[mask] > parameters.housing.severe_overcrowding_threshold).astype(np.float64)
        mild = (over[mask] > 0.0).astype(np.float64)
        tier = severe * 2.0 + mild
        order = np.lexsort((-need, -tier, np.arange(mask.sum())))
        remaining = vacant[r]
        local = np.flatnonzero(mask)
        for position in order:
            if remaining <= 0.0:
                break
            index = local[position]
            want = min(need[position], remaining)
            if want <= 0.0:
                continue
            allocated[index] = want
            remaining -= want
        vacant[r] = max(remaining, 0.0)
    access = access + allocated
    state.household_dwelling_access = access
    state.housing_vacant = vacant
    flows.housing_allocated = allocated
    closing_gap = np.maximum(housing_gap(state, parameters), 0.0)
    state.household_housing_wait = np.where(closing_gap > 1e-9, wait + 1, 0).astype(np.int32)
    flows.household_overcrowding = overcrowding(state, parameters)


def private_construction_installation(
    state: MaterialState, flows: MaterialTickFlows, parameters: HouseholdParameters
) -> None:
    """Install private second-economy construction as new dwelling stock (F4)."""
    construction_h = H_INDEX["construction_services"]
    realized = np.asarray(flows.household_realized_h, dtype=np.float64)[:, construction_h]
    if not np.any(realized > 0.0):
        return
    region = np.asarray(state.household_region, dtype=np.int64)
    weight = np.asarray(state.household_weight, dtype=np.float64)
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    gap = housing_gap(state, parameters)
    install = np.minimum(realized, gap)
    added_region = np.bincount(region, weights=weight * install, minlength=region_count)
    state.dwelling_stock = np.asarray(state.dwelling_stock, dtype=np.float64) + added_region
    access = np.asarray(state.household_dwelling_access, dtype=np.float64) + install
    state.household_dwelling_access = access
    flows.private_completed = install


__all__ = [
    "allocate_housing",
    "durable_desire",
    "housing_gap",
    "overcrowding",
    "private_construction_installation",
    "update_durable_stocks",
]
