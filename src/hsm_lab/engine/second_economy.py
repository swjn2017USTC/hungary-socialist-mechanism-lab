"""P03 second economy: aggregate per-county informal production (plan G).

One aggregate second-economy activity per region, owned by its participating
households.  Participants reserve labour hours, the aggregate buys real inputs
from the regional formal stock (paying cash), produces real light goods,
services and construction into a per-region second-economy pool, and any
household -- participant or not -- can buy from that pool.  Sale receipts flow
back to the participating cohort as deferred income.

Scope note (documented in P03_REPORT): this is the *mechanism nucleus*
implementation.  It reproduces the plan's income + availability channel without
the full network-cell/route integration of G1/G2, so the second-economy pool is
a separate state array whose continuity is checked explicitly rather than
through the shared stock-cell catalog.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from hsm_lab.contract.households import HouseholdParameters
from hsm_lab.contract.material import COMMODITY_INDEX
from hsm_lab.engine import finance
from hsm_lab.engine.state import POOL_CODES, MaterialState, MaterialTickFlows

_SELLING_POOLS = (
    POOL_CODES["output"],
    POOL_CODES["wholesale"],
    POOL_CODES["retail"],
)


def plan_household_time(state: MaterialState, parameters: HouseholdParameters) -> None:
    """Reserve plot and second-economy labour hours from each household's budget (G3)."""
    time = parameters.time
    working = np.asarray(state.household_working_adults, dtype=np.float64)
    participating = np.asarray(state.household_plot_participating, dtype=bool)
    second = np.asarray(state.household_second_participating, dtype=bool)
    grievance = np.asarray(state.household_grievance, dtype=np.float64)
    last_unmet = np.asarray(state.household_last_availability_unmet, dtype=np.float64)
    desired_ref = np.asarray(state.household_consumption_reference, dtype=np.float64)
    shortage = np.where(
        desired_ref.sum(axis=1) > 0.0,
        last_unmet.sum(axis=1) / np.maximum(desired_ref.sum(axis=1), parameters.eps),
        0.0,
    )
    shortage = np.clip(shortage, 0.0, 1.0)

    plot_hours = np.where(participating, time.plot_hours_cap_per_worker * working, 0.0)
    intensity = np.clip(
        time.second_hours_base
        + time.second_shortage_weight * shortage
        + time.second_grievance_weight * grievance,
        0.0,
        1.0,
    )
    second_hours = np.where(second, time.second_hours_cap_per_worker * working * intensity, 0.0)

    formal_hours = time.formal_hours_per_worker * working
    endowment = time.time_endowment_hours * working
    reserved = formal_hours + plot_hours + second_hours
    scale = np.where(reserved > endowment, endowment / np.maximum(reserved, parameters.eps), 1.0)
    plot_hours = plot_hours * scale
    second_hours = second_hours * scale

    state.household_reserved_plot_hours = plot_hours
    state.household_reserved_second_hours = second_hours


def settle_second_economy(
    state: MaterialState,
    flows: MaterialTickFlows,
    network: Any,
    parameters: HouseholdParameters,
    price_net: np.ndarray,
) -> None:
    """Buy inputs, produce output into the regional pool, and pay the sellers (G)."""
    recipe = parameters.second_economy
    region = np.asarray(state.household_region, dtype=np.int64)
    weight = np.asarray(state.household_weight, dtype=np.float64)
    working = np.asarray(state.household_working_adults, dtype=np.float64)
    hours = np.asarray(state.household_reserved_second_hours, dtype=np.float64)
    participant = np.asarray(state.household_second_participating, dtype=bool)
    household_cash = np.asarray(state.household_cash, dtype=np.float64)
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    g_count = len(network.commodity_ids)
    flows.household_second_hours = np.asarray(
        state.household_reserved_second_hours, dtype=np.float64
    ).copy()

    capacity = np.zeros(region_count, dtype=np.float64)
    reserved = np.zeros(region_count, dtype=np.float64)
    cap_person = np.zeros(region_count, dtype=np.float64)
    np.add.at(capacity, region[participant], weight[participant] * working[participant])
    np.add.at(reserved, region[participant], weight[participant] * hours[participant])
    np.add.at(cap_person, region[participant], weight[participant] * working[participant])

    activity_capacity = capacity * recipe.capacity_per_participating_worker
    activity_labor = reserved / max(recipe.hours_per_activity, 1e-12)
    target = np.maximum(np.minimum(activity_capacity, activity_labor), 0.0)

    if not np.any(target > 0.0) or not network.second_input_commodities:
        return

    # Regional availability of each declared second-economy input.
    cell_region = np.asarray(network.cell_region, dtype=np.int64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_pool = np.asarray(network.cell_pool, dtype=np.int64)
    stock = np.asarray(state.stock_value, dtype=np.float64)
    selling = np.isin(cell_pool, _SELLING_POOLS)
    avail = np.zeros((region_count, g_count), dtype=np.float64)
    for r in range(region_count):
        mask = selling & (cell_region == r)
        if mask.any():
            avail[r] = np.bincount(cell_commodity[mask], weights=stock[mask], minlength=g_count)

    axis = list(network.commodity_ids)
    realized = target.copy()
    for g in network.second_input_commodities:
        axis_index = COMMODITY_INDEX.get(axis[g], -1)
        if axis_index < 0:
            continue
        coefficient = recipe.input_coefficients[axis_index]
        if coefficient <= 0.0:
            continue
        limit = avail[:, g] / coefficient
        realized = np.minimum(realized, limit)
    realized = np.maximum(realized, 0.0)
    if not np.any(realized > 0.0):
        return

    # Input purchase: participants fund, sellers (cell owners) receive.
    payment_region = np.zeros(region_count, dtype=np.float64)
    region_cash = np.bincount(region, weights=weight * household_cash, minlength=region_count)
    for g in network.second_input_commodities:
        axis_index = COMMODITY_INDEX.get(axis[g], -1)
        if axis_index >= 0:
            payment_region += realized * recipe.input_coefficients[axis_index] * float(price_net[g])

    # Fund from participating households, scaled by available regional cash.
    allowed = np.divide(
        np.maximum(region_cash, 0.0),
        payment_region,
        out=np.zeros(region_count, dtype=np.float64),
        where=payment_region > 0.0,
    )
    allowed = np.minimum(allowed, 1.0)
    funded_region = payment_region * allowed
    realized = realized * allowed

    input_funding = np.zeros(weight.size, dtype=np.float64)
    for r in range(region_count):
        if funded_region[r] <= 0.0 or cap_person[r] <= 0.0:
            continue
        mask = (region == r) & participant
        if not mask.any():
            continue
        cohort = cap_person[r]
        input_funding[mask] = funded_region[r] * (weight[mask] * working[mask]) / cohort
    household_cash = household_cash - input_funding

    # Pay the sellers (cell owners); Treasury for import cells.
    seller_credit = np.zeros(int(state.organization_id.shape[0]), dtype=np.float64)
    treasury_credit = 0.0
    for g in network.second_input_commodities:
        axis_index = COMMODITY_INDEX.get(axis[g], -1)
        if axis_index < 0:
            continue
        coefficient = recipe.input_coefficients[axis_index]
        if coefficient <= 0.0:
            continue
        quantity_region = realized * coefficient
        for r in range(region_count):
            quantity = quantity_region[r]
            if quantity <= 1e-12:
                continue
            mask = selling & (cell_region == r) & (cell_commodity == g)
            if not mask.any():
                continue
            cell_stock = stock[mask]
            total = float(cell_stock.sum())
            if total <= 0.0:
                continue
            take = min(quantity, total)
            share = cell_stock / total
            idx = np.flatnonzero(mask)
            for pos, cell in enumerate(idx.tolist()):
                amount = take * share[pos]
                if amount <= 0.0:
                    continue
                stock[cell] -= amount
                flows.second_input_used[cell] += amount
                owner_id = int(np.asarray(network.cell_owner_id)[cell])
                kind = int(np.asarray(network.cell_owner_kind)[cell])
                value = amount * float(price_net[g])
                if kind == 0:  # organization
                    seller_credit[owner_id] += value
                else:
                    treasury_credit += value
    state.stock_value = stock
    state.household_cash = household_cash
    if np.any(seller_credit > 0.0):
        state.organization_cash = (
            np.asarray(state.organization_cash, dtype=np.float64) + seller_credit
        )
        flows.organization_sales_receipts += seller_credit
    if treasury_credit > 0.0:
        state.treasury_deposit = float(state.treasury_deposit) + treasury_credit

    # Produce outputs into the regional second-economy pool.
    pool = np.zeros((region_count, g_count), dtype=np.float64)
    for g in network.second_output_commodities:
        axis_index = COMMODITY_INDEX.get(axis[g], -1)
        if axis_index >= 0:
            pool[:, g] = realized * recipe.output_coefficients[axis_index]
    state.second_output_stock = np.asarray(state.second_output_stock, dtype=np.float64) + pool

    flows.household_second_input_funding += input_funding

    # Journal: aggregated household debit -> organization/treasury credit.
    represented = float((weight * input_funding).sum())
    if represented > 0.0:
        bank_count = int(np.asarray(state.bank_reserves).shape[0])
        bank_delta = np.zeros(bank_count, dtype=np.float64)
        represented_by_bank = np.bincount(
            region % max(bank_count, 1),
            weights=weight * input_funding,
            minlength=bank_count,
        )
        bank_delta -= represented_by_bank
        if treasury_credit > 0.0:
            bank_delta[0] += treasury_credit
        credited = seller_credit > 0.0
        if credited.any():
            org_bank = np.asarray(state.organization_bank, dtype=np.int64)
            safe = np.where(org_bank >= 0, org_bank, 0)
            bank_delta += np.bincount(
                safe[credited], weights=seller_credit[credited], minlength=bank_count
            )
        if np.any(bank_delta != 0.0):
            state.bank_deposit_liability = (
                np.asarray(state.bank_deposit_liability, dtype=np.float64) + bank_delta
            )
            state.bank_reserves = np.asarray(state.bank_reserves, dtype=np.float64) + bank_delta
            finance._append_interbank_legs(
                state, flows, kind="second_economy_input_payment", delta=bank_delta, leg_offset=0
            )


def second_expiry(state: MaterialState, network: Any) -> None:
    """Non-stockable second-economy services expire at the end of the quarter (G6)."""
    services_g = (
        network.commodity_ids.index("services_transport")
        if ("services_transport" in network.commodity_ids)
        else -1
    )
    if services_g >= 0:
        pool = np.asarray(state.second_output_stock, dtype=np.float64)
        pool[:, services_g] = 0.0
        state.second_output_stock = pool


__all__ = ["plan_household_time", "second_expiry", "settle_second_economy"]
