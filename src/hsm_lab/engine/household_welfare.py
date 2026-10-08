"""P03 welfare, entitlement and political-reaction accounting (plan H/I).

Hard separation of accounts:

* ``material_satisfaction`` is a bounded logistic of the synthetic welfare index;
* ``household_entitlement`` is a 7-component vector of *experienced outcomes* --
  never political support, never a scalar legitimacy score;
* ``household_grievance`` and ``household_political_compliance`` are separate
  slow-moving state variables.  Grievance is **not** ``1 - compliance``, is not
  material satisfaction, and never triggers a protest: P03 emits no
  collective-action event at all.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from hsm_lab.contract.households import (
    H_INDEX,
    HOUSEHOLD_GOOD_IDS,
    HouseholdCatalog,
    HouseholdParameters,
)
from hsm_lab.engine.households import household_equivalence
from hsm_lab.engine.state import MaterialState, MaterialStockSnapshot, MaterialTickFlows


def _logistic(x: np.ndarray) -> np.ndarray:
    """Numerically bounded logistic."""
    return np.asarray(1.0 / (1.0 + np.exp(-np.clip(x, -60.0, 60.0))), dtype=np.float64)


def account_household_welfare(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: HouseholdParameters,
    network: Any,
    opening: MaterialStockSnapshot,
    price_net: np.ndarray,
) -> None:
    """Compute welfare components, entitlement and the next-grievance input (H)."""
    welfare = parameters.welfare
    catalog: HouseholdCatalog = network.household_catalog
    h_count = len(HOUSEHOLD_GOOD_IDS)
    n = int(np.asarray(state.household_weight).shape[0])
    region = np.asarray(state.household_region, dtype=np.int64)
    weight = np.asarray(state.household_weight, dtype=np.float64)

    reference = np.asarray(state.household_consumption_reference, dtype=np.float64)
    goal_credit = np.asarray(flows.household_goal_credit_h, dtype=np.float64)
    realized = np.asarray(flows.household_realized_h, dtype=np.float64)
    eps = parameters.eps

    # non-durable coverage uses realised physical units + source goal credit
    coverage = np.maximum(goal_credit, realized)
    for durable in catalog.durable_h_index:
        coverage[:, durable] = 0.0  # durable service is a stock, not a purchase

    components = np.zeros((n, h_count), dtype=np.float64)
    ref_positive = reference > eps
    components = np.where(
        ref_positive,
        np.minimum(coverage / np.maximum(reference, eps), welfare.component_cap),
        np.where(coverage > eps, 1.0, 0.0),
    )

    # durable service value from opening ownership (never this quarter's purchase)
    owned_open = np.asarray(opening.household_durable_owned, dtype=np.float64)
    durables = parameters.durables
    hazard = np.asarray(durables.retirement_hazard, dtype=np.float64)
    durable_weight_total = 0.0
    for column, h in enumerate(catalog.durable_h_index):
        parent_price = float(price_net[int(catalog.parent_material_index[h])])
        service = welfare.durable_service_value(parent_price, float(hazard[column]))
        denom = max(service, eps)
        components[:, h] = np.minimum(
            owned_open[:, column] * service / denom, welfare.component_cap
        )
        durable_weight_total += float(welfare.component_weights[h])

    # housing capacity component (construction channel position)
    construction_h = H_INDEX["construction_services"]
    access = np.asarray(state.household_dwelling_access, dtype=np.float64)
    size = np.asarray(state.household_size, dtype=np.float64)
    desired_access = np.maximum(1.0, size / parameters.housing.persons_per_dwelling)
    components[:, construction_h] = np.minimum(
        access / np.maximum(desired_access, eps), welfare.component_cap
    )

    weights = np.asarray(welfare.component_weights, dtype=np.float64)[None, :]
    utility = (weights * components).sum(axis=1)

    queue_hours = np.asarray(flows.household_queue_hours, dtype=np.float64)
    search_hours = np.asarray(flows.household_search_hours, dtype=np.float64)
    queue_cost = welfare.queue_cost_per_hour * queue_hours
    search_cost = welfare.search_cost_per_hour * search_hours

    # substitution loss: credit shortfall on the affected source channels
    substitution_loss = np.zeros(n, dtype=np.float64)
    for q, source_h in enumerate(catalog.substitute_source_h):
        credit = float(catalog.substitute_credit[q])
        loss_per_source = 1.0 - credit
        substitution_loss += (
            np.asarray(flows.household_substitution, dtype=np.float64)[:, q]
            * loss_per_source
            * float(welfare.component_weights[int(source_h)])
        )

    durable_backlog = np.asarray(state.household_durable_backlog, dtype=np.float64)
    durable_wait = np.asarray(state.household_durable_wait, dtype=np.float64)
    housing_gap_units = np.asarray(flows.household_overcrowding, dtype=np.float64)
    housing_wait = np.asarray(state.household_housing_wait, dtype=np.float64)
    postponement_cost = welfare.durable_postponement_cost * (
        durable_backlog.sum(axis=1) * (1.0 + durable_wait.mean(axis=1))
    ) + welfare.housing_postponement_cost * housing_gap_units * (1.0 + housing_wait)

    minimum = np.asarray(parameters.demand.minimum_per_equivalent_person, dtype=np.float64)
    basic_min = minimum[H_INDEX["basic_food"]] * household_equivalence(state)
    basic_consumed = (
        realized[:, H_INDEX["basic_food"]]
        + np.asarray(flows.household_plot_self_h, dtype=np.float64)[:, H_INDEX["basic_food"]]
    )
    basic_deficit = (
        welfare.basic_deficit_weight
        * np.maximum(basic_min - basic_consumed, 0.0)
        / np.maximum(basic_min, eps)
    )

    welfare_net = (
        utility - queue_cost - search_cost - substitution_loss - postponement_cost - basic_deficit
    )
    flows.household_substitution_loss = substitution_loss
    flows.household_postponement_cost = postponement_cost
    flows.household_welfare_net = welfare_net
    state.household_material_satisfaction = _logistic(
        welfare.satisfaction_slope * (welfare_net - welfare.satisfaction_midpoint)
    )

    # --- entitlement: experienced outcomes, not support ---------------------
    entitlement = np.zeros((n, len(catalog.entitlement_ids)), dtype=np.float64)
    job_security = np.where(np.asarray(state.household_working_adults) > 0.0, 1.0, 0.0)
    entitlement[:, 0] = job_security
    real_service_value = realized @ np.asarray(catalog.price_h, dtype=np.float64)
    initial_reference = np.asarray(
        state.household_initial_service_value, dtype=np.float64
    )
    entitlement[:, 1] = real_service_value / np.maximum(real_service_value + initial_reference, eps)
    # D1: the admin price index is a *fixed declared basket* priced at current
    # admin prices -- never a planned/affordable tautology.  With scenario-static
    # admin prices it stays at one, but it moves with prices by construction.
    basket_price = np.asarray(catalog.price_h, dtype=np.float64)
    declared_basket = np.asarray(parameters.demand.base_per_equivalent_person, dtype=np.float64)
    current_index = np.full(n, float(declared_basket @ basket_price), dtype=np.float64)
    current_index = np.where(
        np.isfinite(current_index) & (current_index > 0.0), current_index, 1.0
    )
    last_index = np.asarray(state.household_last_price_index, dtype=np.float64)
    entitlement[:, 2] = np.exp(
        -np.abs(np.log(np.maximum(current_index, eps) / np.maximum(last_index, eps)))
    )
    entitlement[:, 3] = np.minimum(access / np.maximum(desired_access, eps), 1.0)
    entitlement[:, 4] = welfare.welfare_provision
    entitlement[:, 5] = welfare.private_autonomy
    entitlement[:, 6] = welfare.cultural_openness
    entitlement = np.clip(entitlement, 0.0, 1.0)
    state.household_entitlement = entitlement

    # --- perceived unfairness and grievance update --------------------------
    welfare_positive = np.maximum(welfare_net, 0.0)
    region_welfare = np.bincount(
        region,
        weights=weight * welfare_positive,
        minlength=int(np.asarray(state.dwelling_stock).shape[0]),
    )
    region_weight = np.bincount(region, weights=weight, minlength=region_welfare.size)
    county_mean = region_welfare / np.maximum(region_weight, eps)
    unfairness = np.clip(
        np.maximum(county_mean[region] - welfare_positive, 0.0)
        / np.maximum(np.abs(county_mean[region]), eps),
        0.0,
        1.0,
    )
    gap = np.asarray(opening.household_expectation, dtype=np.float64) - entitlement
    flows.entitlement_gap = gap
    mean_positive_gap = np.maximum(gap, 0.0).mean(axis=1)
    next_target = (
        welfare.grievance_gap_weight * mean_positive_gap
        + welfare.grievance_unfairness_weight * unfairness
    )
    old_grievance = np.asarray(state.household_grievance, dtype=np.float64)
    new_grievance = np.clip(
        (1.0 - welfare.grievance_alpha) * old_grievance + welfare.grievance_alpha * next_target,
        0.0,
        1.0,
    )
    state.household_grievance = new_grievance
    state.household_last_price_index = current_index

    # --- political compliance: separate slow rule, never 1 - grievance ------
    compliance_target = np.clip(
        welfare.compliance_baseline
        - welfare.compliance_gap_weight * new_grievance
        + welfare.compliance_autonomy_weight * (welfare.private_autonomy - 0.5),
        0.0,
        1.0,
    )
    old_compliance = np.asarray(state.household_political_compliance, dtype=np.float64)
    state.household_political_compliance = (
        1.0 - welfare.compliance_alpha
    ) * old_compliance + welfare.compliance_alpha * compliance_target


def update_household_expectations(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: HouseholdParameters,
    opening: MaterialStockSnapshot,
) -> None:
    """Adaptive expectations with an experience ratchet (I)."""
    expectations = parameters.expectations
    entitlement = np.asarray(state.household_entitlement, dtype=np.float64)
    opening_expectation = np.asarray(opening.household_expectation, dtype=np.float64)
    opening_entitlement = np.asarray(opening.household_entitlement, dtype=np.float64)
    streak = np.asarray(state.household_improvement_streak, dtype=np.int32)

    improved = entitlement > opening_entitlement + 1e-12
    streak_next = np.where(improved, streak + 1, 0).astype(np.int32)

    up = expectations.alpha_up * np.maximum(entitlement - opening_expectation, 0.0)
    down = expectations.alpha_down * np.maximum(opening_expectation - entitlement, 0.0)
    ratchet = (
        expectations.ratchet_strength
        * (streak_next >= expectations.ratchet_quarters)
        * np.maximum(entitlement - opening_entitlement, 0.0)
    )
    expectation_next = np.clip(opening_expectation + up - down + ratchet, 0.0, 1.0)
    state.household_expectation = expectation_next
    state.household_improvement_streak = streak_next

    # consumption reference follows realised physical acquisition
    alpha = expectations.consumption_reference_alpha
    reference = np.asarray(state.household_consumption_reference, dtype=np.float64)
    realized = np.asarray(flows.household_realized_h, dtype=np.float64)
    state.household_consumption_reference = (1.0 - alpha) * reference + alpha * realized
    state.household_last_consumption = realized.copy()
    state.household_last_availability_unmet = np.asarray(
        flows.household_availability_unmet_h, dtype=np.float64
    ).copy()


__all__ = ["account_household_welfare", "update_household_expectations"]
