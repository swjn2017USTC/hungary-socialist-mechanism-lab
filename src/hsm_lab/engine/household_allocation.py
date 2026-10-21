"""P03 household acquisition: channels, rationing, substitution, saving (plan C/D).

One fixed execution order per tick (D1):

    plot self-use -> formal exact goods -> second-economy goods ->
    forced substitution -> queue/search hours -> budget decomposition

Every channel has its own availability; a shortage in one channel is never
reported as a shortage of its parent commodity or of a sibling channel.  Money
is moved from current receipts plus an explicitly declared bounded opening-cash
share; the budget is never overrun, and a forced substitution is only allowed
when the target goal was already affordable.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from hsm_lab.contract.households import (
    HouseholdCatalog,
    HouseholdParameters,
)
from hsm_lab.contract.material import PURPOSE_CODES, RoutePurpose
from hsm_lab.engine import finance
from hsm_lab.engine.households import household_equivalence
from hsm_lab.engine.state import MaterialState, MaterialStockSnapshot, MaterialTickFlows

_PURPOSE_HOUSEHOLD = PURPOSE_CODES[RoutePurpose.HOUSEHOLD]


def _household_budget_with_savings(
    opening_cash: np.ndarray, current_receipts: np.ndarray, reentry_fraction: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return income budget, total purchase cap and maximum opening-cash draw."""
    opening_cash = np.maximum(np.asarray(opening_cash, dtype=np.float64), 0.0)
    current_receipts = np.asarray(current_receipts, dtype=np.float64)
    income_budget = np.maximum(np.minimum(opening_cash, current_receipts), 0.0)
    eligible_cash = np.maximum(opening_cash - income_budget, 0.0)
    draw_cap = eligible_cash * float(reentry_fraction)
    total_budget = np.minimum(opening_cash, income_budget + draw_cap)
    return income_budget, total_budget, draw_cap


def allocate_household_baskets(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: HouseholdParameters,
    network: Any,
    opening: MaterialStockSnapshot,
    price_net: np.ndarray,
    household_cash_open: np.ndarray,
    household_deferred_open: np.ndarray,
    stock_tick_open: np.ndarray | None = None,
    savings_reentry_fraction: float = 0.0,
) -> None:
    """Ration the desired basket across every channel and settle all flows."""
    catalog: HouseholdCatalog = network.household_catalog
    is_f2 = getattr(network, "f2_marker", None) is not None
    h_count = len(catalog.household_good_ids)
    region = np.asarray(state.household_region, dtype=np.int64)
    weight = np.asarray(state.household_weight, dtype=np.float64)
    size = np.asarray(state.household_size, dtype=np.float64)
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    n = weight.size
    eps = parameters.eps

    equivalent = household_equivalence(state)
    desired = np.asarray(flows.household_desired_h, dtype=np.float64).copy()
    price_h = np.asarray(catalog.price_h, dtype=np.float64)
    equity = np.asarray(catalog.material_equivalent, dtype=np.float64)
    quota = np.asarray(catalog.quota_share, dtype=np.float64)
    parent = np.asarray(catalog.parent_material_index, dtype=np.int64)

    # --- budget (this quarter's realised receipts; savings stay parked) -----
    pre_purchase_cash = np.asarray(state.household_cash, dtype=np.float64).copy()
    income = (
        np.asarray(flows.household_wage_income, dtype=np.float64)
        + np.asarray(flows.household_plot_income_formal, dtype=np.float64)
        + np.asarray(household_deferred_open, dtype=np.float64)
        - np.asarray(flows.household_plot_input_funding, dtype=np.float64)
    )
    if not is_f2:
        # The legacy F1 branch keeps its historical treatment of second-input
        # funding in the receipts budget.  F2 settle debits household cash
        # before allocation, so the F2 branch must not subtract the same
        # funding a second time.
        income -= np.asarray(flows.household_second_input_funding, dtype=np.float64)
    base_income_budget, budget, savings_reentry_cap = _household_budget_with_savings(
        pre_purchase_cash, income, savings_reentry_fraction
    )

    # --- plot self-use food (opening reserved stock, capacity share) --------
    plot_self = np.zeros((n, h_count), dtype=np.float64)
    participating = np.asarray(state.household_plot_participating, dtype=bool)
    represented_persons = np.bincount(
        region[participating], weights=(weight * size)[participating], minlength=region_count
    )
    safe_persons = np.where(represented_persons > 0.0, represented_persons, 1.0)
    plot_share = np.zeros(n, dtype=np.float64)
    plot_share[participating] = size[participating] / safe_persons[region[participating]]
    stock = np.asarray(state.stock_value, dtype=np.float64)
    ready_self = np.asarray(network.plot_ready_self_cell, dtype=np.int64)
    plot_self_value = np.zeros(n, dtype=np.float64)
    if ready_self.size and bool(np.all(ready_self >= 0)):
        self_pool_source = (
            np.asarray(stock_tick_open, dtype=np.float64) if stock_tick_open is not None else stock
        )
        # self-use is bound by the tick-opening reserved pool, never by this
        # quarter's production landing in the same cell.
        self_avail = np.maximum(self_pool_source[ready_self], 0.0)
        basic_h = catalog.channel("basic_food")
        want = desired[:, basic_h]
        # capacity share: each participant may take its represented-person
        # share of the region's reserved self-use pool (never another's share)
        plot_self[:, basic_h] = np.where(
            participating,
            np.minimum(want, plot_share * self_avail[region]),
            0.0,
        )
        consumed_region = np.bincount(
            region, weights=weight * plot_self[:, basic_h], minlength=region_count
        )
        stock[ready_self] = np.maximum(stock[ready_self] - consumed_region, 0.0)
        desired[:, basic_h] = np.maximum(desired[:, basic_h] - plot_self[:, basic_h], 0.0)
        plot_self_value = plot_self[:, basic_h] * price_h[basic_h]

    # --- budget-tier affordability (minimum basket protected) ---------------
    minimum = np.asarray(parameters.demand.minimum_per_equivalent_person, dtype=np.float64)
    min_h = minimum[None, :] * equivalent[:, None]
    cost_min = min_h @ price_h
    tier_one = np.where(cost_min > 0.0, np.minimum(1.0, budget / np.maximum(cost_min, eps)), 1.0)
    affordable = min_h * tier_one[:, None]
    remaining = np.maximum(budget - (affordable @ price_h), 0.0)
    extra = np.maximum(desired - min_h, 0.0)
    cost_extra = extra @ price_h
    tier_two = np.where(
        cost_extra > 0.0, np.minimum(1.0, remaining / np.maximum(cost_extra, eps)), 1.0
    )
    affordable = affordable + extra * tier_two[:, None]
    planned_spending = affordable @ price_h

    # --- channel availability (formal retail + second-economy pool) ---------
    retail_cell = np.asarray(network.retail_cell_by_commodity, dtype=np.int64)
    second_pool = np.asarray(state.second_output_stock, dtype=np.float64)
    second_outputs = set(network.second_output_commodities)
    formal_avail = np.zeros((region_count, h_count), dtype=np.float64)
    second_avail = np.zeros((region_count, h_count), dtype=np.float64)
    for h in range(h_count):
        g = int(parent[h])
        if g < 0 or equity[h] <= 0.0:
            continue
        for r in range(region_count):
            cell = int(retail_cell[r, g])
            if cell >= 0:
                formal_avail[r, h] = quota[h] * max(stock[cell], 0.0) / equity[h]
            if g in second_outputs:
                second_avail[r, h] = quota[h] * max(second_pool[r, g], 0.0) / equity[h]
    available = formal_avail + second_avail

    # --- county-weighted rationing of the affordable basket ------------------
    realized = np.zeros((n, h_count), dtype=np.float64)
    formal_bought = np.zeros((n, h_count), dtype=np.float64)
    second_bought = np.zeros((n, h_count), dtype=np.float64)
    availability_unmet = np.zeros((n, h_count), dtype=np.float64)
    for h in range(h_count):
        demand_region = np.bincount(
            region, weights=weight * affordable[:, h], minlength=region_count
        )
        got_region = np.minimum(demand_region, available[:, h])
        factor = np.where(demand_region > 0.0, got_region / np.maximum(demand_region, eps), 0.0)
        realized_h = affordable[:, h] * factor[region]
        realized[:, h] = realized_h
        share_of_got = np.where(
            got_region[region] > 0.0, realized_h / np.maximum(got_region[region], eps), 0.0
        )
        formal_bought[:, h] = np.minimum(got_region, formal_avail[:, h])[region] * share_of_got
        second_bought[:, h] = realized_h - formal_bought[:, h]
        availability_unmet[:, h] = np.maximum(affordable[:, h] - realized_h, 0.0)

    # --- plot direct market (G5): the participant cohort's ready market food ---
    plot_direct_receipt = np.zeros(n, dtype=np.float64)
    plot_direct_spend = np.zeros(n, dtype=np.float64)
    plot_market_h = np.zeros((n, h_count), dtype=np.float64)
    market_cells = np.asarray(network.plot_ready_market_cell, dtype=np.int64)
    # The budget already covers formal + second purchases; plot-direct buys must
    # fit the remainder so total household spending never overruns the budget
    # (otherwise the close-of-tick cash identity can dip below zero).
    budget_left = np.maximum(budget - (formal_bought @ price_h + second_bought @ price_h), 0.0)
    if market_cells.size and bool(np.all(market_cells >= 0)):
        shares = np.asarray(parameters.allocation.plot_food_shares, dtype=np.float64)
        for channel, share in (
            (catalog.channel("basic_food"), shares[0]),
            (catalog.channel("higher_food"), shares[1]),
        ):
            if share <= 0.0:
                continue
            market_h = np.zeros(region_count, dtype=np.float64)
            market_h = share * np.maximum(stock[market_cells], 0.0) / equity[channel]
            want = availability_unmet[:, channel]
            demand_region = np.bincount(region, weights=weight * want, minlength=region_count)
            got_region = np.minimum(demand_region, market_h)
            factor = np.where(demand_region > 0.0, got_region / np.maximum(demand_region, eps), 0.0)
            bought = want * factor[region]
            pay_region = np.bincount(
                region, weights=weight * bought * price_h[channel], minlength=region_count
            )
            cash_region = np.bincount(region, weights=weight * budget_left, minlength=region_count)
            pay_factor = np.where(
                pay_region > 0.0,
                np.minimum(1.0, cash_region / np.maximum(pay_region, eps)),
                1.0,
            )
            bought = bought * pay_factor[region]
            budget_left = np.maximum(budget_left - bought * price_h[channel], 0.0)
            realized[:, channel] += bought
            plot_market_h[:, channel] += bought
            plot_direct_spend += bought * price_h[channel]
            availability_unmet[:, channel] = np.maximum(
                availability_unmet[:, channel] - bought, 0.0
            )
            consumed_region = (
                np.bincount(region, weights=weight * bought, minlength=region_count)
                * equity[channel]
            )
            stock[market_cells] = np.maximum(stock[market_cells] - consumed_region, 0.0)
        # receipts go to the participating cohort (region size share), late.
        region_receipts = np.bincount(
            region, weights=weight * plot_direct_spend, minlength=region_count
        )
        participant = np.asarray(state.household_plot_participating, dtype=bool)
        region_participant_weight = np.bincount(
            region[participant], weights=weight[participant], minlength=region_count
        )
        for r in range(region_count):
            if region_receipts[r] <= 0.0 or region_participant_weight[r] <= 0.0:
                continue
            mask = (region == r) & participant
            if mask.any():
                # state-unit share: sum(weight * receipt) == region_receipts
                plot_direct_receipt[mask] = region_receipts[r] / region_participant_weight[r]

    # --- forced substitution (Q; one pass, availability-driven only) ---------
    substitution = np.zeros((n, len(catalog.substitution_ids)), dtype=np.float64)
    substitution_target_units = np.zeros((n, len(catalog.substitution_ids)), dtype=np.float64)
    goal_credit = realized.copy()
    substitution_spend = np.zeros(n, dtype=np.float64)
    formal_sub_h = np.zeros((n, h_count), dtype=np.float64)
    second_sub_h = np.zeros((n, h_count), dtype=np.float64)
    if is_f2:
        # F2 keeps formal and second-economy target sources separate.  Every
        # substitution consumes one of them exactly once, so four durable
        # shortages cannot share a single repair-service shelf.
        formal_room = np.maximum(
            formal_avail
            - np.stack(
                [
                    np.bincount(
                        region,
                        weights=weight * formal_bought[:, h],
                        minlength=region_count,
                    )
                    for h in range(h_count)
                ],
                axis=1,
            ),
            0.0,
        )
        second_room = np.maximum(
            second_avail
            - np.stack(
                [
                    np.bincount(
                        region,
                        weights=weight * second_bought[:, h],
                        minlength=region_count,
                    )
                    for h in range(h_count)
                ],
                axis=1,
            ),
            0.0,
        )
    for q in range(len(catalog.substitution_ids)):
        source_h = int(catalog.substitute_source_h[q])
        target_h = int(catalog.substitute_target_h[q])
        ratio = max(float(catalog.substitute_ratio[q]), eps)
        credit = float(catalog.substitute_credit[q])
        unmet = availability_unmet[:, source_h]
        if not np.any(unmet > 0.0):
            continue
        demand_region = np.bincount(region, weights=weight * unmet, minlength=region_count)
        if is_f2:
            room_region = formal_room[:, target_h] + second_room[:, target_h]
        else:
            room_region = np.maximum(
                available[:, target_h]
                - np.bincount(
                    region, weights=weight * realized[:, target_h], minlength=region_count
                ),
                0.0,
            )
        allowed_region = np.minimum(demand_region * ratio, room_region)
        factor = np.where(
            demand_region > 0.0, allowed_region / np.maximum(demand_region * ratio, eps), 0.0
        )
        substituted = unmet * ratio * factor[region]
        if is_f2:
            # Per-household budget cap before regional rationing: a household
            # cannot spend more than its remaining planned budget.
            budget_left = np.maximum(
                planned_spending - realized @ price_h - plot_direct_spend - substitution_spend,
                0.0,
            )
            if price_h[target_h] > 0.0:
                substituted = np.minimum(substituted, budget_left / price_h[target_h])
            got_region = np.bincount(
                region, weights=weight * substituted, minlength=region_count
            )
            avail_factor = np.where(
                got_region > 0.0,
                np.minimum(1.0, room_region / np.maximum(got_region, eps)),
                0.0,
            )
            substituted = substituted * avail_factor[region]
            got_region = np.bincount(
                region, weights=weight * substituted, minlength=region_count
            )
            formal_units_region = np.minimum(got_region, formal_room[:, target_h])
            second_units_region = np.maximum(got_region - formal_units_region, 0.0)
            share = np.divide(
                substituted,
                got_region[region],
                out=np.zeros_like(substituted),
                where=got_region[region] > 0.0,
            )
            formal_sub = formal_units_region[region] * share
            second_sub = second_units_region[region] * share
            formal_room[:, target_h] = np.maximum(
                formal_room[:, target_h] - formal_units_region, 0.0
            )
            second_room[:, target_h] = np.maximum(
                second_room[:, target_h] - second_units_region, 0.0
            )
            formal_sub_h[:, target_h] += formal_sub
            second_sub_h[:, target_h] += second_sub
            substitution_spend += (formal_sub + second_sub) * price_h[target_h]
        else:
            # budget: the substituted target units must be payable from the plan
            budget_left = np.maximum(planned_spending - realized @ price_h, 0.0)
            pay_region = np.bincount(
                region, weights=weight * substituted * price_h[target_h], minlength=region_count
            )
            cash_region = np.bincount(region, weights=weight * budget_left, minlength=region_count)
            pay_factor = np.where(
                pay_region > 0.0, np.minimum(1.0, cash_region / np.maximum(pay_region, eps)), 1.0
            )
            substituted = substituted * pay_factor[region]
            substitution_spend += substituted * price_h[target_h]
        substitution[:, q] = substituted / ratio
        substitution_target_units[:, q] = substituted
        goal_credit[:, source_h] += substituted * credit / ratio
        # D3: the substituted source units are relieved -- do not re-count them
        # in the residual availability gap / queue hours.
        availability_unmet[:, source_h] = np.maximum(
            availability_unmet[:, source_h] - substituted / ratio, 0.0
        )

    # physical realised units include the substituted target units; the target's
    # own goal credit is untouched (a substitute never upgrades its own goal).
    substitution_h = np.zeros((n, h_count), dtype=np.float64)
    if is_f2:
        substitution_h = formal_sub_h + second_sub_h
    else:
        for q in range(len(catalog.substitution_ids)):
            substitution_h[:, int(catalog.substitute_target_h[q])] += substitution_target_units[
                :, q
            ]
    realized = realized + substitution_h
    # D2: plot self-use is real household consumption and belongs in the
    # H-level realised basket and goal credit that welfare/entitlement consume.
    realized = realized + plot_self
    goal_credit = goal_credit + plot_self

    formal_spend = formal_bought @ price_h
    second_spend = second_bought @ price_h
    if is_f2:
        formal_purchase_h = formal_bought + formal_sub_h
        second_purchase_h = second_bought + second_sub_h
    else:
        formal_purchase_h = formal_bought
        second_purchase_h = second_bought
    second_spend_total = second_purchase_h @ price_h
    spending = formal_spend + second_spend + substitution_spend + plot_direct_spend

    # --- physical stock drawdown --------------------------------------------
    for h in range(h_count):
        g = int(parent[h])
        if g < 0:
            continue
        if is_f2:
            consumed_region = (
                np.bincount(
                    region,
                    weights=weight * formal_purchase_h[:, h],
                    minlength=region_count,
                )
                * equity[h]
            )
            flows.retail_sales[:, g] += consumed_region
            if g in second_outputs:
                consumed_second = (
                    np.bincount(
                        region,
                        weights=weight * second_purchase_h[:, h],
                        minlength=region_count,
                    )
                    * equity[h]
                )
                second_pool[:, g] = np.maximum(second_pool[:, g] - consumed_second, 0.0)
        else:
            consumed_region = (
                np.bincount(
                    region, weights=weight * formal_bought[:, h], minlength=region_count
                )
                * equity[h]
            )
            flows.retail_sales[:, g] += consumed_region
            if g in second_outputs:
                consumed_second = (
                    np.bincount(
                        region,
                        weights=weight * (second_bought[:, h] + substitution_h[:, h]),
                        minlength=region_count,
                    )
                    * equity[h]
                )
                second_pool[:, g] = np.maximum(second_pool[:, g] - consumed_second, 0.0)
            elif np.any(substitution_h[:, h] > 0.0):
                flows.retail_sales[:, g] += (
                    np.bincount(
                        region,
                        weights=weight * substitution_h[:, h],
                        minlength=region_count,
                    )
                    * equity[h]
                )
    # Retail cells release exactly the parent-equivalent household sales through
    # their own edges (matches the material ledger's edge-based continuity).
    # Aggregate cap: the per-channel availability is capped above, but summing
    # across channels by weight x equity can still oversell a cell, so scale the
    # (region, commodity) total to what the source cell actually holds.
    retail_by_commodity = np.asarray(network.retail_cell_by_commodity, dtype=np.int64)
    retail_sales_view = np.asarray(flows.retail_sales, dtype=np.float64)
    for g in sorted({int(parent[h]) for h in range(h_count) if int(parent[h]) >= 0}):
        cells = retail_by_commodity[:, g]
        valid = cells >= 0
        if not bool(valid.any()):
            continue
        shelf = np.where(valid, np.maximum(stock[cells], 0.0), 0.0)
        demand = retail_sales_view[:, g]
        scale = np.where(
            demand > 0.0, np.minimum(1.0, shelf / np.maximum(demand, eps)), 1.0
        )
        retail_sales_view[:, g] = demand * scale
    hh_edges_all = np.flatnonzero(
        np.asarray(network.edge_purpose, dtype=np.int64) == _PURPOSE_HOUSEHOLD
    )
    if hh_edges_all.size:
        edge_source_all = np.asarray(network.edge_source_cell, dtype=np.int64)[hh_edges_all]
        edge_g_all = np.asarray(network.edge_commodity, dtype=np.int64)[hh_edges_all]
        edge_w_all = np.asarray(network.edge_weight, dtype=np.float64)[hh_edges_all]
        edge_r_all = np.asarray(network.cell_region, dtype=np.int64)[edge_source_all]
        sales_view = np.asarray(flows.retail_sales, dtype=np.float64)
        stock[edge_source_all] = np.maximum(
            stock[edge_source_all] - sales_view[edge_r_all, edge_g_all] * edge_w_all, 0.0
        )
    state.stock_value = stock
    state.second_output_stock = second_pool

    # --- second-economy sale receipts to the participating cohort ------------
    participant = np.asarray(state.household_second_participating, dtype=bool)
    working = np.asarray(state.household_working_adults, dtype=np.float64)
    sale_region = np.bincount(
        region, weights=weight * second_spend_total, minlength=region_count
    )
    receipt = np.zeros(n, dtype=np.float64)
    if is_f2:
        # The cohort is fixed (participants with working adults); the state-unit
        # share is working_i / sum_cohort(weight*working), so
        # sum(weight_i * receipt_i) == sale_region exactly.
        cohort = participant & (working > 0.0)
        cap_person = np.bincount(
            region[cohort], weights=(weight * working)[cohort], minlength=region_count
        )
        for r in range(region_count):
            if sale_region[r] <= 0.0 or cap_person[r] <= 0.0:
                continue
            mask = (region == r) & cohort
            if mask.any():
                receipt[mask] = sale_region[r] * working[mask] / cap_person[r]
    else:
        cap_person = np.bincount(
            region[participant], weights=(weight * working)[participant], minlength=region_count
        )
        for r in range(region_count):
            if sale_region[r] <= 0.0 or cap_person[r] <= 0.0:
                continue
            mask = (region == r) & participant
            if mask.any():
                receipt[mask] = sale_region[r] * (weight[mask] * working[mask]) / cap_person[r]

    total_receipt = receipt + plot_direct_receipt
    state.household_cash = (
        np.asarray(state.household_cash, dtype=np.float64) - spending + total_receipt
    )
    state.household_deferred_receipt = total_receipt.copy()

    # --- queue/search hours (affordable-but-unavailable only) ----------------
    alloc = parameters.allocation
    unmet_equiv = availability_unmet * equity[None, :]
    queue_requested = alloc.queue_hours_per_equivalent_unmet * unmet_equiv.sum(axis=1)
    shortage_rate = np.where(
        affordable > 0.0, availability_unmet / np.maximum(affordable, eps), 0.0
    )
    informal = np.asarray(state.household_informal_access, dtype=np.float64)
    search_requested = (
        alloc.search_hours_per_channel_shortage * shortage_rate.sum(axis=1) * informal
    )

    time = parameters.time
    formal_hours = time.formal_hours_per_worker * working
    reserved = (
        formal_hours
        + np.asarray(state.household_reserved_plot_hours)
        + np.asarray(state.household_reserved_second_hours)
    )
    endowment = time.time_endowment_hours * working
    leftover = np.maximum(endowment - reserved, 0.0)
    total_requested = queue_requested + search_requested
    scale = np.where(total_requested > leftover, leftover / np.maximum(total_requested, eps), 1.0)
    queue_hours = queue_requested * scale
    search_hours = search_requested * scale

    # --- flows --------------------------------------------------------------
    flows.household_desired_h = desired
    flows.household_affordable_h = affordable
    flows.household_realized_h = realized
    flows.household_budget_unmet_h = np.maximum(desired - affordable, 0.0)
    flows.household_availability_unmet_h = availability_unmet
    flows.household_formal_h = formal_purchase_h if is_f2 else formal_bought
    flows.household_plot_self_h = plot_self
    flows.household_plot_market_h = plot_market_h
    flows.household_self_use = plot_self_value
    flows.household_second_h = second_purchase_h if is_f2 else second_bought
    flows.household_goal_credit_h = goal_credit
    flows.household_substitution = substitution
    flows.household_savings_draw = np.minimum(
        np.maximum(spending - base_income_budget, 0.0), savings_reentry_cap
    )
    flows.household_queue_hours = queue_hours
    flows.household_search_hours = search_hours
    flows.household_plot_hours = np.asarray(
        state.household_reserved_plot_hours, dtype=np.float64
    ).copy()
    flows.household_leisure_hours = leftover - queue_hours - search_hours
    flows.household_planned_spending = planned_spending
    flows.household_spending = spending
    flows.household_budget_available = budget
    flows.household_forced_saving = np.maximum(planned_spending - spending, 0.0)
    flows.household_voluntary_saving = np.maximum(base_income_budget - planned_spending, 0.0)
    flows.household_second_income_direct = receipt.copy()
    flows.household_plot_income_direct = plot_direct_receipt.copy()
    # Material-ledger acquisition view (N, G): every realised source projected
    # to its parent commodity (plot self-use is already inside ``realized``).
    realized_g = realized @ np.asarray(catalog.to_material, dtype=np.float64)
    desired_g = (desired + plot_self) @ np.asarray(catalog.to_material, dtype=np.float64)
    flows.household_desired = desired_g
    flows.household_realized = realized_g
    flows.household_budget_unmet = np.maximum(desired_g - realized_g, 0.0)
    flows.household_availability_unmet = np.maximum(desired_g - realized_g, 0.0)
    # per-(region, parent) retail unmet view for the material ledger
    for h in range(h_count):
        g = int(parent[h])
        if g < 0:
            continue
        has_cell = np.asarray(
            [int(retail_cell[r, g]) >= 0 for r in range(region_count)], dtype=np.float64
        )
        flows.retail_unmet[:, g] += (
            has_cell
            * np.bincount(region, weights=weight * availability_unmet[:, h], minlength=region_count)
            * equity[h]
        )

    # Mirror the parent-commodity purchases onto the network household demand
    # cells and edges so the material ledger sees the same retail channel.
    edge_purpose = np.asarray(network.edge_purpose, dtype=np.int64)
    if hasattr(network, "edge_source_cell"):
        demand_is_hh = np.asarray(network.demand_purpose, dtype=np.int64) == _PURPOSE_HOUSEHOLD
        hh_edges = np.flatnonzero(edge_purpose == _PURPOSE_HOUSEHOLD)
        if hh_edges.size:
            edge_source = np.asarray(network.edge_source_cell, dtype=np.int64)
            edge_commodity = np.asarray(network.edge_commodity, dtype=np.int64)
            edge_weight = np.asarray(network.edge_weight, dtype=np.float64)
            edge_demand = np.asarray(network.edge_demand, dtype=np.int64)[hh_edges]
            edge_region = np.asarray(network.cell_region, dtype=np.int64)[edge_source[hh_edges]]
            edge_g = edge_commodity[hh_edges]
            sales = np.asarray(flows.retail_sales, dtype=np.float64)
            flows.edge_delivered[hh_edges] = sales[edge_region, edge_g] * edge_weight[hh_edges]
            flows.edge_allocated[hh_edges] = flows.edge_delivered[hh_edges]
            delivered = np.bincount(
                edge_demand, weights=flows.edge_delivered[hh_edges], minlength=demand_is_hh.size
            )
            cell_sales = np.zeros(demand_is_hh.size, dtype=np.float64)
            cell_g = np.zeros(demand_is_hh.size, dtype=np.int64)
            cell_r = np.zeros(demand_is_hh.size, dtype=np.int64)
            cell_g[edge_demand] = edge_g
            cell_r[edge_demand] = edge_region
            cell_sales[edge_demand] = sales[edge_region, edge_g]
            ordered = np.where(cell_sales > 0.0, cell_sales, 0.0)
            flows.desired[demand_is_hh] = ordered[demand_is_hh]
            flows.ordered[demand_is_hh] = ordered[demand_is_hh]
            flows.ordered_gross[demand_is_hh] = ordered[demand_is_hh]
            flows.allocated[demand_is_hh] = np.minimum(
                delivered[demand_is_hh], ordered[demand_is_hh]
            )
            flows.delivered[demand_is_hh] = delivered[demand_is_hh]
            flows.used[demand_is_hh] = delivered[demand_is_hh]

    if is_f2:
        from hsm_lab.institutions.second_economy_f2_adapter import (
            append_f2_direct_sale_journal,
        )

        ledger_purchases = formal_purchase_h
        ledger_second_spend = second_spend_total
    else:
        ledger_purchases = formal_bought + substitution_h
        ledger_second_spend = second_spend
    _settle_ledger(
        state,
        flows,
        network,
        region,
        weight,
        ledger_purchases,
        price_h,
        ledger_second_spend,
        receipt,
        plot_direct_spend,
        plot_direct_receipt,
    )
    if is_f2:
        # Per-household buyer/seller matching for the direct second-economy
        # sales; this only appends journal legs (the cash/bank movement was
        # already netted in ``_settle_ledger``).
        append_f2_direct_sale_journal(
            state,
            flows,
            region=region,
            weight=weight,
            buyer_amount=second_spend_total,
            seller_amount=receipt,
        )


def _settle_ledger(
    state: MaterialState,
    flows: MaterialTickFlows,
    network: Any,
    region: np.ndarray,
    weight: np.ndarray,
    purchased_h: np.ndarray,
    price_h: np.ndarray,
    second_spend: np.ndarray,
    receipt: np.ndarray,
    plot_direct_spend: np.ndarray,
    plot_direct_receipt: np.ndarray,
) -> None:
    """Credit sellers and move bank deposits for household spending (closed ledger)."""
    catalog: HouseholdCatalog = network.household_catalog
    org_count = int(state.organization_id.shape[0])
    bank_count = int(np.asarray(state.bank_reserves).shape[0])
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    retail_cell = np.asarray(network.retail_cell_by_commodity, dtype=np.int64)
    parent = np.asarray(catalog.parent_material_index, dtype=np.int64)
    cell_owner_org = np.where(
        np.asarray(network.cell_owner_kind) == 0, np.asarray(network.cell_owner_id), -1
    ).astype(np.int64)
    outlay = purchased_h * price_h[None, :]
    credit = np.zeros(org_count, dtype=np.float64)
    for h in range(len(network.household_catalog.household_good_ids)):
        g = int(parent[h])
        if g < 0:
            continue
        for r in range(region_count):
            cell = int(retail_cell[r, g])
            if cell < 0:
                continue
            owner = int(cell_owner_org[cell])
            if owner >= 0:
                credit[owner] += float((weight[region == r] * outlay[region == r, h]).sum())
    if np.any(credit > 0.0):
        state.organization_cash = np.asarray(state.organization_cash, dtype=np.float64) + credit
        flows.organization_sales_receipts += credit

    # Payers debit their bank; retail orgs and second-economy participants credit theirs.
    hh_bank = region % max(bank_count, 1)
    bank_delta = np.zeros(bank_count, dtype=np.float64)
    bank_delta -= np.bincount(hh_bank, weights=weight * outlay.sum(axis=1), minlength=bank_count)
    bank_delta -= np.bincount(hh_bank, weights=weight * second_spend, minlength=bank_count)
    bank_delta += np.bincount(hh_bank, weights=weight * receipt, minlength=bank_count)
    bank_delta -= np.bincount(hh_bank, weights=weight * plot_direct_spend, minlength=bank_count)
    bank_delta += np.bincount(hh_bank, weights=weight * plot_direct_receipt, minlength=bank_count)
    if np.any(credit > 0.0):
        org_bank = np.asarray(state.organization_bank, dtype=np.int64)
        safe = np.where(org_bank >= 0, org_bank, 0)
        bank_delta += np.bincount(safe, weights=credit, minlength=bank_count)
    if np.any(bank_delta != 0.0):
        state.bank_deposit_liability = (
            np.asarray(state.bank_deposit_liability, dtype=np.float64) + bank_delta
        )
        state.bank_reserves = np.asarray(state.bank_reserves, dtype=np.float64) + bank_delta
        finance._append_interbank_legs(
            state, flows, kind="goods_payment", delta=bank_delta, leg_offset=0
        )


__all__ = ["allocate_household_baskets"]
