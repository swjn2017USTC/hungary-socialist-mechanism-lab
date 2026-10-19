"""Counterfactual procurement action-space profile.

The profile separates the controlled action space from exogenous production:

* production is not a decision variable; the baseline kernel activity and edge
  flows supply the economy;
* the LP may only add procurement on edges whose buyer is one of the two
  registered procurement organizations;
* demand quantities and edge baselines are read from a real baseline
  ``tick_material`` run on a copy of the opening state, not from demand shares;
* a counterfactual no-plan tick on the same opening state is retained by the
  evidence runner, so plan effects are measured against a real baseline.

The module never reads a target, forcing array or session.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Any

import numpy as np

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.contract.material import PURPOSE_CODES, STAGE_CODES, RoutePurpose
from hsm_lab.contract.schemas import Quarter
from hsm_lab.engine.state import build_material_prices
from hsm_lab.institutions.observed import ObservationBuilder
from hsm_lab.planning.proposals import (
    PlanningBudgetObservation,
    PlanningDeclarations,
    PlanningInputs,
    PlanningObservation,
    build_planning_inputs,
)

_STAGE_NAMES = {value: key for key, value in STAGE_CODES.items()}
_MONEY_SCALE = 1e-6


@dataclass(frozen=True)
class CounterfactualWorld:
    declarations: PlanningDeclarations
    org_rows: tuple[int, ...]
    label_map: dict[str, int]
    goods: tuple[tuple[int, int], ...]
    edge_index: np.ndarray
    recipe_capacity_by_org_good: np.ndarray
    baseline_cash: np.ndarray


def _procurement_organizations(network: Any) -> tuple[int, ...]:
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    mask = (demand_purpose == PURPOSE_CODES[RoutePurpose.PROCUREMENT]) & (
        cell_owner_kind[demand_cell] == 0
    )
    organizations = sorted({int(value) for value in cell_owner_id[demand_cell[mask]]})
    if len(organizations) < 2:
        raise ResearchGateError("HIST_H3G_PROFILE: fewer than two procurement organizations")
    return tuple(organizations[:2])


def _demand_buyer(
    network: Any,
    demand: int,
    decision_set: set[int],
) -> int:
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    edge_demand = np.asarray(network.edge_demand, dtype=np.int64)
    edge_source = np.asarray(network.edge_source_cell, dtype=np.int64)
    if int(cell_owner_kind[demand_cell[demand]]) == 0:
        owner = int(cell_owner_id[demand_cell[demand]])
        if owner in decision_set:
            return owner
    sources = {
        int(cell_owner_id[edge_source[edge]])
        for edge in np.flatnonzero(edge_demand == demand)
        if int(cell_owner_kind[edge_source[edge]]) == 0
    }
    controlled = sources & decision_set
    if controlled:
        return min(controlled)
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    if int(demand_purpose[demand]) == PURPOSE_CODES[RoutePurpose.HOUSEHOLD] and sources:
        return min(sources)
    return -1


def build_counterfactual_world(
    network: Any,
    state: Any,
    parameters: Any,
    baseline_flows: Any,
    *,
    quarters: tuple[str, str, str, str] = (
        "1957Q1",
        "1957Q2",
        "1957Q3",
        "1957Q4",
    ),
) -> CounterfactualWorld:
    """Build a baseline-embedded controlled procurement LP world."""
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_stage = np.asarray(network.cell_stage, dtype=np.int64)
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    source_cell = np.asarray(network.edge_source_cell, dtype=np.int64)
    edge_buyer = np.asarray(network.edge_buyer_org, dtype=np.int64)
    edge_commodity = np.asarray(network.edge_commodity, dtype=np.int64)
    edge_stage = np.asarray(network.edge_stage, dtype=np.int64)
    edge_transport = np.asarray(network.edge_transport_org, dtype=np.int64)
    edge_service_cell = np.asarray(network.edge_transport_service_cell, dtype=np.int64)
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    edge_delivered = np.asarray(baseline_flows.edge_delivered, dtype=np.float64)
    demand_ordered = np.asarray(baseline_flows.ordered, dtype=np.float64)
    demand_desired = np.asarray(baseline_flows.desired, dtype=np.float64)
    demand_delivered = np.asarray(baseline_flows.delivered, dtype=np.float64)
    stock = np.asarray(state.stock_value, dtype=np.float64)
    prices = build_material_prices(parameters)

    decision_organizations = _procurement_organizations(network)
    decision_set = set(decision_organizations)
    edge_rows = np.flatnonzero(
        (cell_owner_kind[source_cell] == 0) & np.isin(edge_buyer, decision_organizations)
    )
    edge_rows = edge_rows[cell_owner_id[source_cell[edge_rows]] != edge_buyer[edge_rows]]

    demand_rows: list[tuple[int, int, bool, float, float]] = []
    for demand in range(len(demand_cell)):
        buyer = _demand_buyer(network, demand, decision_set)
        if buyer < 0:
            continue
        pair = (
            int(cell_commodity[demand_cell[demand]]),
            int(cell_stage[demand_cell[demand]]),
        )
        final = int(demand_purpose[demand]) == PURPOSE_CODES[RoutePurpose.HOUSEHOLD]
        delivered = float(demand_delivered[demand])
        ordered = max(0.0, float(demand_ordered[demand]) - delivered)
        gross = max(
            ordered,
            float(demand_desired[demand]) - delivered,
        )
        demand_rows.append((buyer, int(pair[0]), final, ordered, gross))

    selected_pairs = {(int(edge_commodity[edge]), int(edge_stage[edge])) for edge in edge_rows}
    selected_pairs |= {
        (pair[0], pair[1])
        for pair in [
            (
                int(cell_commodity[demand_cell[index]]),
                int(cell_stage[demand_cell[index]]),
            )
            for index in range(len(demand_cell))
        ]
    }
    for cell in edge_service_cell:
        if int(cell) >= 0:
            selected_pairs.add((int(cell_commodity[int(cell)]), int(cell_stage[int(cell)])))
    pairs = tuple(sorted(selected_pairs))
    pair_index = {pair: index for index, pair in enumerate(pairs)}
    commodity_ids = tuple(str(value) for value in network.commodity_ids)
    goods_id = tuple(
        f"{commodity_ids[commodity]}|{_STAGE_NAMES[stage]}" for commodity, stage in pairs
    )

    organization_rows = list(decision_organizations)
    organization_rows.extend(
        index for index in range(len(state.organization_id)) if index not in decision_set
    )
    labels = ["ORG-ENT-A", "ORG-ENT-B"]
    labels.extend(f"ORG-AUX-{int(state.organization_id[index])}" for index in organization_rows[2:])
    org_row_by_material = {
        material_index: row for row, material_index in enumerate(organization_rows)
    }
    label_map = {
        label: material_index
        for label, material_index in zip(labels, organization_rows, strict=True)
    }

    inventory = np.zeros((len(organization_rows), len(pairs)), dtype=np.float64)
    for material_index, row in org_row_by_material.items():
        for pair, good in pair_index.items():
            cells = np.flatnonzero(
                (cell_owner_kind == 0)
                & (cell_owner_id == material_index)
                & (cell_commodity == pair[0])
                & (cell_stage == pair[1])
            )
            inventory[row, good] = float(stock[cells].sum())

    seller_org = np.asarray(
        [org_row_by_material[int(cell_owner_id[source_cell[edge]])] for edge in edge_rows],
        dtype=np.int64,
    )
    buyer_org = np.asarray(
        [org_row_by_material[int(edge_buyer[edge])] for edge in edge_rows],
        dtype=np.int64,
    )
    good_row = np.asarray(
        [pair_index[(int(edge_commodity[edge]), int(edge_stage[edge]))] for edge in edge_rows],
        dtype=np.int64,
    )
    unit_price = np.asarray(
        [
            float(prices.price_for(int(edge_commodity[edge]), int(edge_stage[edge])))
            for edge in edge_rows
        ],
        dtype=np.float64,
    )
    transport_org = np.asarray(
        [
            org_row_by_material.get(int(edge_transport[edge]), -1)
            if int(edge_transport[edge]) >= 0
            else -1
            for edge in edge_rows
        ],
        dtype=np.int64,
    )
    edge_service_good = np.full(len(edge_rows), -1, dtype=np.int64)
    for position, edge in enumerate(edge_rows):
        service_cell = int(edge_service_cell[edge])
        if service_cell < 0:
            continue
        pair = (int(cell_commodity[service_cell]), int(cell_stage[service_cell]))
        if pair in pair_index:
            edge_service_good[position] = pair_index[pair]
    freight_per_unit = np.asarray(
        [
            float(network.edge_transport_per_unit[edge])
            if transport_org[position] >= 0 and edge_service_good[position] >= 0
            else 0.0
            for position, edge in enumerate(edge_rows)
        ],
        dtype=np.float64,
    )
    freight_price = np.zeros(len(edge_rows), dtype=np.float64)
    for position, _edge in enumerate(edge_rows):
        service_good = int(edge_service_good[position])
        if service_good >= 0:
            freight_price[position] = freight_per_unit[position] * float(
                prices.price_for(*pairs[service_good])
            )

    baseline = np.asarray(
        [float(edge_delivered[edge]) for edge in edge_rows],
        dtype=np.float64,
    )
    for position, baseline_flow in enumerate(baseline):
        if baseline_flow <= 0.0:
            continue
        seller = int(seller_org[position])
        buyer = int(buyer_org[position])
        good = int(good_row[position])
        inventory[seller, good] -= baseline_flow
        inventory[buyer, good] += baseline_flow
    inventory = np.maximum(inventory, 0.0)
    capacity = np.asarray(
        [
            max(0.0, float(inventory[int(seller_org[position]), int(good_row[position])]))
            for position in range(len(edge_rows))
        ],
        dtype=np.float64,
    )

    demand_buyer = np.asarray([org_row_by_material[row[0]] for row in demand_rows], dtype=np.int64)
    demand_pairs: list[tuple[int, int]] = []
    for demand in range(len(demand_cell)):
        buyer = _demand_buyer(network, demand, decision_set)
        if buyer < 0:
            continue
        demand_pairs.append(
            (
                int(cell_commodity[demand_cell[demand]]),
                int(cell_stage[demand_cell[demand]]),
            )
        )
    demand_good = np.asarray([pair_index[pair] for pair in demand_pairs], dtype=np.int64)
    demand_final = np.asarray([row[2] for row in demand_rows], dtype=bool)
    demand_ordered_vec = np.asarray([row[3] for row in demand_rows], dtype=np.float64)
    demand_gross_vec = np.asarray([row[4] for row in demand_rows], dtype=np.float64)

    baseline_procurement = np.zeros((len(organization_rows), len(pairs)), dtype=np.float64)
    baseline_cash = np.zeros(len(organization_rows), dtype=np.float64)

    declarations = PlanningDeclarations(
        source_kind="synthetic",
        quarters=quarters,
        terminal_mask=(True, True, True, True),
        currency="HUF",
        bank_count=int(len(state.bank_reserves)),
        organization_ids=tuple(labels),
        organization_bank=np.asarray(
            [max(0, int(state.organization_bank[index])) for index in organization_rows],
            dtype=np.int64,
        ),
        organization_cash_opening=np.asarray(
            [state.organization_cash[index] for index in organization_rows],
            dtype=np.float64,
        ),
        goods_id=goods_id,
        goods_is_service=np.asarray(
            [
                any(
                    int(cell_commodity[int(cell)]) == pair[0]
                    and int(cell_stage[int(cell)]) == pair[1]
                    for cell in edge_service_cell
                    if int(cell) >= 0
                )
                for pair in pairs
            ],
            dtype=bool,
        ),
        prices=np.tile(
            np.asarray(
                [
                    [float(prices.price_for(commodity, stage)) for commodity, stage in pairs]
                    for _ in range(4)
                ],
                dtype=np.float64,
            ),
            (1, 1),
        ),
        inventory_opening=inventory,
        wage=np.zeros((4, len(labels))),
        funding_capacity=np.tile(
            np.asarray(
                [state.organization_cash[index] for index in organization_rows],
                dtype=np.float64,
            ),
            (4, 1),
        ),
        service_capacity=np.zeros((4, len(labels))),
        handling_capacity=np.tile(
            np.maximum(
                np.asarray(
                    [state.organization_capacity[index] for index in organization_rows],
                    dtype=np.float64,
                ),
                1.0,
            ),
            (4, 1),
        ),
        bank_reserves=np.tile(
            np.maximum(np.asarray(state.bank_reserves, dtype=np.float64), 0.0),
            (4, 1),
        ),
        edge_id=np.asarray([int(network.edge_id[edge]) for edge in edge_rows], dtype=np.int64),
        edge_seller=seller_org,
        edge_buyer=buyer_org,
        edge_good=good_row,
        edge_unit_price=unit_price,
        edge_transport_org=transport_org,
        edge_freight_per_unit=freight_per_unit,
        edge_handling_per_unit=np.ones(len(edge_rows), dtype=np.float64),
        edge_capacity=np.tile(capacity, (4, 1)),
        edge_baseline=np.zeros((4, len(edge_rows)), dtype=np.float64),
        demand_id=tuple(f"D{index}" for index in range(len(demand_rows))),
        demand_buyer=demand_buyer,
        demand_good=demand_good,
        demand_final=demand_final,
        demand_ordered=np.tile(demand_ordered_vec, (4, 1)),
        demand_gross=np.tile(demand_gross_vec, (4, 1)),
        recipe_id=(),
        recipe_org=np.zeros(0, dtype=np.int64),
        recipe_output_good=np.zeros(0, dtype=np.int64),
        recipe_output_coeff=np.zeros(0),
        recipe_input_ptr=np.array([0], dtype=np.int64),
        recipe_input_good=np.zeros(0, dtype=np.int64),
        recipe_input_coeff=np.zeros(0),
        recipe_capacity=np.zeros((4, 0)),
        organization_interest=np.zeros((4, len(labels))),
        organization_order_financing=np.zeros((4, len(labels))),
        edge_service_good=edge_service_good,
        organization_service_good=np.full(len(labels), -1, dtype=np.int64),
        baseline_procurement=np.tile(baseline_procurement, (4, 1, 1)),
        edge_freight_price=freight_price,
        recipe_tier=np.zeros(0, dtype=np.int64),
        service_split=(1.0, 0.0, 0.0),
        decision_organization_ids=("ORG-ENT-A", "ORG-ENT-B"),
        required_reports=(),
        notes=("counterfactual controlled procurement; production exogenous baseline",),
    )
    declarations = replace(
        declarations,
        organization_cash_opening=declarations.organization_cash_opening * _MONEY_SCALE,
        prices=declarations.prices * _MONEY_SCALE,
        funding_capacity=declarations.funding_capacity * _MONEY_SCALE,
        bank_reserves=declarations.bank_reserves * _MONEY_SCALE,
        edge_unit_price=declarations.edge_unit_price * _MONEY_SCALE,
        goods_is_service=np.zeros_like(declarations.goods_is_service),
        edge_service_good=np.full_like(declarations.edge_service_good, -1),
        edge_freight_per_unit=np.zeros_like(declarations.edge_freight_per_unit),
        edge_freight_price=np.zeros_like(declarations.edge_freight_price),
    )
    return CounterfactualWorld(
        declarations=declarations,
        org_rows=tuple(organization_rows),
        label_map=label_map,
        goods=pairs,
        edge_index=edge_rows,
        recipe_capacity_by_org_good=np.zeros(
            (len(organization_rows), len(pairs)), dtype=np.float64
        ),
        baseline_cash=baseline_cash,
    )


def counterfactual_inputs(
    world: CounterfactualWorld,
    network: Any,
    state: Any,
    *,
    quarter: str,
    decision_at: date,
    available_at: date,
    information_mode: str = "bounded_planning",
) -> PlanningInputs:
    """Refresh inventory/cash/reserves for one quarter of the same world."""
    declarations = world.declarations
    inventory = np.array(declarations.inventory_opening, dtype=np.float64, copy=True)
    cash = (
        np.asarray(
            [state.organization_cash[index] for index in world.org_rows],
            dtype=np.float64,
        )
        * _MONEY_SCALE
        + world.baseline_cash
    )
    declarations = replace(
        declarations,
        quarters=tuple(str(Quarter.parse(quarter).advance(offset)) for offset in range(4)),
        inventory_opening=inventory,
        organization_cash_opening=cash,
        funding_capacity=np.tile(cash, (4, 1)),
        bank_reserves=np.tile(
            np.maximum(np.asarray(state.bank_reserves, dtype=np.float64), 0.0) * _MONEY_SCALE,
            (4, 1),
        ),
    )
    observations: list[PlanningObservation] = []
    for row, label in enumerate(declarations.organization_ids):
        for good, goods_id in enumerate(declarations.goods_id):
            commodity, stage = goods_id.split("|", 1)
            builder = ObservationBuilder("procurement_organization")
            observation = builder.build(
                organization_id=label,
                sector_id="industry",
                geographic_id="national",
                quarter=quarter,
                decision_at=decision_at,
                available_at=available_at,
                raw_data={
                    "quarter": quarter,
                    "supply_quantity": 0.0,
                    "demand_quantity": float(
                        np.sum(
                            declarations.demand_ordered[
                                0,
                                (declarations.demand_buyer == row)
                                & (declarations.demand_good == good),
                            ]
                        )
                    ),
                    "administered_price": float(declarations.prices[0, good]),
                    "inventory_level": float(declarations.inventory_opening[row, good]),
                    "capacity_utilization": 1.0,
                    "shortage_indicator": 0.0,
                },
            )
            observations.append(PlanningObservation(label, commodity, stage, observation))
    budgets: list[PlanningBudgetObservation] = []
    for row, label in enumerate(declarations.organization_ids):
        budget = float(declarations.organization_cash_opening[row])
        builder = ObservationBuilder("approver")
        observation = builder.build(
            organization_id="ORG-GOV",
            sector_id="industry",
            geographic_id="national",
            quarter=quarter,
            decision_at=decision_at,
            available_at=available_at,
            raw_data={
                "quarter": quarter,
                "requested_quantity": 1e9,
                "approved_quantity": 1e9,
                "price_level": 1.0,
                "budget_available": budget,
                "priority_score": 1.0,
            },
        )
        budgets.append(
            PlanningBudgetObservation(
                organization_id=label,
                payer_kind="funding_group",
                payer_id=row,
                currency=declarations.currency,
                observation=observation,
            )
        )
    for bank in range(declarations.bank_count):
        reserve = float(declarations.bank_reserves[0, bank])
        builder = ObservationBuilder("approver")
        observation = builder.build(
            organization_id="ORG-GOV",
            sector_id="industry",
            geographic_id="national",
            quarter=quarter,
            decision_at=decision_at,
            available_at=available_at,
            raw_data={
                "quarter": quarter,
                "requested_quantity": 1e9,
                "approved_quantity": 1e9,
                "price_level": 1.0,
                "budget_available": reserve,
                "priority_score": 1.0,
            },
        )
        budgets.append(
            PlanningBudgetObservation(
                organization_id=declarations.organization_ids[0],
                payer_kind="bank_prepayment",
                payer_id=bank,
                currency=declarations.currency,
                observation=observation,
            )
        )
    return build_planning_inputs(
        observations=tuple(observations),
        declarations=declarations,
        decision_at=decision_at,
        quarter=quarter,
        budget_observations=tuple(budgets),
        information_mode=information_mode,  # type: ignore[arg-type]
    )


__all__ = [
    "CounterfactualWorld",
    "build_counterfactual_world",
    "counterfactual_inputs",
]
