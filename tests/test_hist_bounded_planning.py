"""H3E: bounded four-quarter planning, information isolation and execution.

Every execution case uses the real compiled material network and exactly one
``tick_material`` call.  No solver result, stock cell, account or journal is
mocked.  Solver monkeypatches are limited to unreliable-return boundaries; the
kernel itself is never mocked.
"""

from __future__ import annotations

import copy
import dataclasses
from datetime import date

import numpy as np
import pytest

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.contract.schemas import Quarter, ScenarioSpec
from hsm_lab.engine.policy import TickControls
from hsm_lab.engine.political_run import PoliticalSession
from hsm_lab.engine.state import MaterialState
from hsm_lab.institutions.observed import ObservationBuilder
from hsm_lab.institutions.schemas import (
    AuthorityScope,
    DateInterval,
    InstitutionEvent,
    RegimeCalendar,
)
from hsm_lab.measurement.plan_execution import (
    RollingExecutionFailure,
    execute_rolling_proposal,
)
from hsm_lab.planning.proposals import (
    ARMS,
    PlanningBudgetObservation,
    PlanningDeclarations,
    PlanningObservation,
    build_planning_inputs,
    observation_digest,
)
from hsm_lab.planning.rolling import plan_quarter
from tests.test_hist_tiny_execution import make_two_region

QUARTERS = ("1957Q1", "1957Q2", "1957Q3", "1957Q4")
DECISION_AT = date(1957, 1, 15)
AVAILABLE_AT = date(1957, 1, 10)


# ---------------------------------------------------------------------------
# Fixtures and builders
# ---------------------------------------------------------------------------


def _procurement_observation(
    organization_id: str,
    *,
    quarter: str = "1957Q1",
    supply: float = 0.0,
    demand: float = 10.0,
    inventory: float = 0.0,
    price: float = 1.0,
    utilization: float = 1.0,
    shortage: float = 0.0,
    decision_at: date = DECISION_AT,
    available_at: date = AVAILABLE_AT,
):
    builder = ObservationBuilder("procurement_organization")
    return builder.build(
        organization_id=organization_id,
        sector_id="industry",
        geographic_id="national",
        quarter=quarter,
        decision_at=decision_at,
        available_at=available_at,
        raw_data={
            "quarter": quarter,
            "supply_quantity": supply,
            "demand_quantity": demand,
            "administered_price": price,
            "inventory_level": inventory,
            "capacity_utilization": utilization,
            "shortage_indicator": shortage,
        },
    )


def _budget_observation(
    organization_id: str,
    budget: float,
    *,
    quarter: str = "1957Q1",
    payer_kind: str = "funding_group",
    payer_id: int = 0,
    decision_at: date = DECISION_AT,
    available_at: date = AVAILABLE_AT,
):
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
            "requested_quantity": budget,
            "approved_quantity": budget,
            "price_level": 1.0,
            "budget_available": budget,
            "priority_score": 1.0,
        },
    )
    return PlanningBudgetObservation(
        organization_id=organization_id,
        payer_kind=payer_kind,
        payer_id=payer_id,
        currency="HUF",
        observation=observation,
    )


def _declarations(**overrides):
    base = {
        "source_kind": "synthetic",
        "quarters": QUARTERS,
        "terminal_mask": (True, True, True, True),
        "currency": "HUF",
        "bank_count": 1,
        "organization_ids": ("ORG-ENT-A", "ORG-ENT-B"),
        "organization_bank": np.array([0, 0], dtype=np.int64),
        "organization_cash_opening": np.array([1000.0, 1000.0]),
        "goods_id": ("energy|standard",),
        "goods_is_service": np.array([False]),
        "prices": np.full((4, 1), 1.0),
        "inventory_opening": np.zeros((2, 1)),
        "wage": np.zeros((4, 2)),
        "funding_capacity": np.full((4, 2), 1000.0),
        "service_capacity": np.zeros((4, 2)),
        "handling_capacity": np.full((4, 2), 1000.0),
        "bank_reserves": np.full((4, 1), 1000.0),
        "edge_id": np.array([0], dtype=np.int64),
        "edge_seller": np.array([0], dtype=np.int64),
        "edge_buyer": np.array([1], dtype=np.int64),
        "edge_good": np.array([0], dtype=np.int64),
        "edge_unit_price": np.array([1.0]),
        "edge_transport_org": np.array([-1], dtype=np.int64),
        "edge_freight_per_unit": np.array([0.0]),
        "edge_handling_per_unit": np.array([1.0]),
        "edge_capacity": np.full((4, 1), 100.0),
        "demand_id": ("B-energy",),
        "demand_buyer": np.array([1], dtype=np.int64),
        "demand_good": np.array([0], dtype=np.int64),
        "demand_final": np.array([True]),
        "demand_ordered": np.full((4, 1), 10.0),
        "demand_gross": np.full((4, 1), 10.0),
        "recipe_id": ("A-energy",),
        "recipe_org": np.array([0], dtype=np.int64),
        "recipe_output_good": np.array([0], dtype=np.int64),
        "recipe_output_coeff": np.array([1.0]),
        "recipe_input_ptr": np.array([0, 0], dtype=np.int64),
        "recipe_input_good": np.zeros(0, dtype=np.int64),
        "recipe_input_coeff": np.zeros(0),
        "recipe_capacity": np.full((4, 1), 0.0),
        "required_reports": (("ORG-ENT-B", "energy|standard"),),
    }
    base.update(overrides)
    return PlanningDeclarations(**base)


def _default_observations(declarations):
    keys = set(declarations.required_reports)
    for edge in range(int(declarations.edge_id.shape[0])):
        good = int(declarations.edge_good[edge])
        keys.add(
            (
                declarations.organization_ids[int(declarations.edge_seller[edge])],
                declarations.goods_id[good],
            )
        )
        keys.add(
            (
                declarations.organization_ids[int(declarations.edge_buyer[edge])],
                declarations.goods_id[good],
            )
        )
        carrier = int(declarations.edge_transport_org[edge])
        service_good = int(declarations.edge_service_good[edge])
        if carrier >= 0 and service_good >= 0:
            keys.add(
                (
                    declarations.organization_ids[carrier],
                    declarations.goods_id[service_good],
                )
            )
    for demand in range(int(declarations.demand_buyer.shape[0])):
        good = int(declarations.demand_good[demand])
        keys.add(
            (
                declarations.organization_ids[int(declarations.demand_buyer[demand])],
                declarations.goods_id[good],
            )
        )
    for recipe in range(int(declarations.recipe_org.shape[0])):
        good = int(declarations.recipe_output_good[recipe])
        keys.add(
            (
                declarations.organization_ids[int(declarations.recipe_org[recipe])],
                declarations.goods_id[good],
            )
        )
        for position in range(
            int(declarations.recipe_input_ptr[recipe]),
            int(declarations.recipe_input_ptr[recipe + 1]),
        ):
            keys.add(
                (
                    declarations.organization_ids[int(declarations.recipe_org[recipe])],
                    declarations.goods_id[int(declarations.recipe_input_good[position])],
                )
            )
    for org in range(len(declarations.organization_ids)):
        for good in range(len(declarations.goods_id)):
            capacity = sum(
                float(declarations.recipe_capacity[0, recipe])
                for recipe in range(int(declarations.recipe_org.shape[0]))
                if int(declarations.recipe_org[recipe]) == org
                and int(declarations.recipe_output_good[recipe]) == good
            )
            if float(declarations.inventory_opening[org, good]) > 0.0 or capacity > 0.0:
                keys.add((declarations.organization_ids[org], declarations.goods_id[good]))
    observations = []
    for organization_id, goods_id in sorted(keys):
        commodity_id, stage = goods_id.split("|", 1)
        org = declarations.organization_ids.index(organization_id)
        good = declarations.goods_id.index(goods_id)
        supply = sum(
            float(declarations.recipe_capacity[0, recipe])
            for recipe in range(int(declarations.recipe_org.shape[0]))
            if int(declarations.recipe_org[recipe]) == org
            and int(declarations.recipe_output_good[recipe]) == good
        )
        demand = sum(
            float(declarations.demand_ordered[0, index])
            for index in range(int(declarations.demand_buyer.shape[0]))
            if int(declarations.demand_buyer[index]) == org
            and int(declarations.demand_good[index]) == good
        )
        observations.append(
            PlanningObservation(
                organization_id,
                commodity_id,
                stage,
                _procurement_observation(
                    organization_id,
                    supply=supply,
                    demand=demand,
                    inventory=float(declarations.inventory_opening[org, good]),
                    price=float(declarations.prices[0, good]),
                ),
            )
        )
    return tuple(observations)


def _inputs(
    declarations,
    *,
    observations=None,
    budgets=None,
    information_mode="bounded_planning",
    decision_at=DECISION_AT,
    include_defaults=True,
    quarter="1957Q1",
):
    if include_defaults:
        defaults = _default_observations(declarations)
        if observations is None:
            observations = defaults
        else:
            overlay = {
                (item.organization_id, item.commodity_id, item.stage): item for item in observations
            }
            merged = []
            for item in defaults:
                key = (item.organization_id, item.commodity_id, item.stage)
                merged.append(overlay.pop(key, item))
            merged.extend(overlay.values())
            observations = tuple(merged)
    elif observations is None:
        observations = ()
    if budgets is None:
        buyer_indices = set(int(value) for value in declarations.edge_buyer)
        buyer_indices |= set(int(value) for value in declarations.demand_buyer)
        buyer_indices |= set(int(value) for value in declarations.recipe_org)
        budgets = tuple(
            _budget_observation(declarations.organization_ids[index], 1000.0, payer_id=index)
            for index in sorted(buyer_indices)
        )
    return build_planning_inputs(
        observations=tuple(observations),
        declarations=declarations,
        decision_at=decision_at,
        quarter=quarter,
        budget_observations=tuple(budgets),
        information_mode=information_mode,
    )


def _session(state, *, start="1957Q1", ticks=4):
    session_state = object.__new__(MaterialState)
    object.__setattr__(session_state, "completed_ticks", int(state.completed_ticks))
    spec = ScenarioSpec.model_construct(start=Quarter.parse(start))
    session = object.__new__(PoliticalSession)
    object.__setattr__(session, "state", state)
    object.__setattr__(session, "spec", spec)
    object.__setattr__(session, "target_ticks", ticks)
    object.__setattr__(session, "opened", True)
    object.__setattr__(session, "finished", False)
    return session


def _calendar(*organization_ids: str) -> RegimeCalendar:
    def day(year: int, month: int) -> DateInterval:
        return DateInterval(
            earliest=date(year, month, 1),
            latest=date(year, month, 1),
            precision="day",
        )

    events = tuple(
        InstitutionEvent(
            event_id=f"GRANT-{organization_id}",
            permission="procurement",
            scope=AuthorityScope(
                organization_ids=(organization_id,),
                sector_ids=("industry",),
                excluded_sector_ids=(),
                geographic_ids=(),
            ),
            action="grant",
            proposal_date=day(1955, 1),
            approval_date=day(1955, 6),
            enactment_date=day(1956, 1),
            effective_from=day(1956, 1),
            effective_to=None,
            observed_implementation_at=None,
            source_available_at=day(1955, 1),
            issuer="synthetic",
            legal_force="enactment",
            source_ids=("synthetic:h3e-test",),
            synthetic_flag=True,
            confidence_reason="synthetic test",
            search_tags=(),
        )
        for organization_id in organization_ids
    )
    return RegimeCalendar(events=events)


# ---------------------------------------------------------------------------
# 1. Legacy timing and rule/reference behaviour
# ---------------------------------------------------------------------------


def test_current_production_is_not_borrowed_and_next_quarter_is_legal() -> None:
    declarations = _declarations(recipe_capacity=np.full((4, 1), 10.0))
    inputs = _inputs(declarations)
    plan = plan_quarter(inputs, mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert plan.first_quarter_decisions == ()
    assert plan.quarterly[0].shortfall[0] == pytest.approx(10.0)
    assert plan.quarterly[1].shortfall[0] == pytest.approx(0.0)
    assert plan.quarterly[1].purchases[1, 0] == pytest.approx(10.0)


def test_rule_and_bounded_share_the_observation_hash() -> None:
    inputs = _inputs(_declarations())
    rule = plan_quarter(inputs, mode="historical_rule_based", time_limit_s=10)
    bounded = plan_quarter(inputs, mode="bounded_planning", time_limit_s=10)
    assert rule.observation_hash == bounded.observation_hash
    assert rule.input_hash == bounded.input_hash
    assert rule.matrix_hash != bounded.matrix_hash


def test_zero_freight_capacity_blocks_a_freight_using_edge() -> None:
    declarations = _declarations(
        goods_id=("energy|standard", "transport|service"),
        goods_is_service=np.array([False, True]),
        prices=np.ones((4, 2)),
        inventory_opening=np.array([[10.0, 0.0], [0.0, 0.0]]),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.zeros((4, 2)),
        handling_capacity=np.full((4, 2), 1000.0),
        recipe_capacity=np.zeros((4, 1)),
        edge_transport_org=np.array([0], dtype=np.int64),
        edge_freight_per_unit=np.array([1.0]),
    )
    plan = plan_quarter(_inputs(declarations), mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert plan.first_quarter_decisions == ()
    assert plan.quarterly[0].purchases[1, 0] == pytest.approx(0.0)
    assert plan.quarterly[0].shortfall[0] == pytest.approx(10.0)


def test_service_output_is_used_or_lost_in_the_same_quarter() -> None:
    declarations = _declarations(
        goods_id=("energy|standard", "transport|service"),
        goods_is_service=np.array([False, True]),
        inventory_opening=np.zeros((2, 2)),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.array([[5.0, 0.0]] * 4),
        handling_capacity=np.full((4, 2), 1000.0),
        edge_good=np.array([0], dtype=np.int64),
        demand_good=np.array([0], dtype=np.int64),
        recipe_id=("A-energy", "A-service"),
        recipe_org=np.array([0, 0], dtype=np.int64),
        recipe_output_good=np.array([0, 1], dtype=np.int64),
        recipe_output_coeff=np.array([1.0, 1.0]),
        recipe_input_ptr=np.array([0, 0, 0], dtype=np.int64),
        recipe_input_good=np.zeros(0, dtype=np.int64),
        recipe_input_coeff=np.zeros(0),
        recipe_capacity=np.array([[0.0, 5.0]] * 4),
        prices=np.ones((4, 2)),
    )
    plan = plan_quarter(_inputs(declarations), mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert plan.quarterly[0].inventory[0, 1] == pytest.approx(0.0)
    assert plan.quarterly[0].service_lost[0] >= 5.0 - 1e-9


# ---------------------------------------------------------------------------
# 2. Information boundaries
# ---------------------------------------------------------------------------


def test_future_quarters_do_not_change_the_first_quarter() -> None:
    base = _declarations(inventory_opening=np.array([[10.0], [0.0]]))
    future_shifted = _declarations(
        inventory_opening=np.array([[10.0], [0.0]]),
        demand_ordered=np.array([[10.0], [999.0], [999.0], [999.0]]),
        demand_gross=np.array([[10.0], [999.0], [999.0], [999.0]]),
        recipe_capacity=np.array([[0.0], [50.0], [50.0], [50.0]]),
    )
    first = plan_quarter(_inputs(base), mode="bounded_planning", time_limit_s=10)
    second = plan_quarter(_inputs(future_shifted), mode="bounded_planning", time_limit_s=10)
    assert first.first_quarter_decisions == second.first_quarter_decisions
    assert np.array_equal(first.quarterly[0].purchases, second.quarterly[0].purchases)
    assert np.array_equal(first.quarterly[0].shortfall, second.quarterly[0].shortfall)


def test_late_report_is_rejected_before_the_solver() -> None:
    late = _procurement_observation(
        "ORG-ENT-B",
        decision_at=date(1957, 2, 15),
        available_at=date(1957, 2, 10),
    )
    observations = (PlanningObservation("ORG-ENT-B", "energy", "standard", late),)
    with pytest.raises(ResearchGateError, match="decision_at"):
        _inputs(_declarations(), observations=observations)


def test_duplicate_conflicting_reports_are_rejected() -> None:
    observations = (
        PlanningObservation(
            "ORG-ENT-B", "energy", "standard", _procurement_observation("ORG-ENT-B")
        ),
        PlanningObservation(
            "ORG-ENT-B",
            "energy",
            "standard",
            _procurement_observation("ORG-ENT-B", demand=99.0),
        ),
    )
    with pytest.raises(ResearchGateError, match="duplicate"):
        _inputs(_declarations(), observations=observations, include_defaults=False)


def test_missing_budget_blocks_the_run() -> None:
    with pytest.raises(ResearchGateError, match="report"):
        _inputs(_declarations(), budgets=())


def test_missing_required_report_blocks_the_run() -> None:
    with pytest.raises(ResearchGateError, match="required report"):
        _inputs(_declarations(), observations=(), include_defaults=False)


def test_target_key_is_rejected_by_the_observation_builder() -> None:
    builder = ObservationBuilder("procurement_organization")
    with pytest.raises(TypeError, match="Prohibited"):
        builder.build(
            organization_id="ORG-ENT-B",
            sector_id="industry",
            geographic_id="national",
            quarter="1957Q1",
            decision_at=DECISION_AT,
            available_at=AVAILABLE_AT,
            raw_data={"quarter": "1957Q1", "target_inventory": 1.0},
        )


def test_full_information_non_nesting_is_reported_not_silently_ranked() -> None:
    declarations = _declarations(inventory_opening=np.zeros((2, 1)))
    observations = (
        PlanningObservation(
            "ORG-ENT-B",
            "energy",
            "standard",
            _procurement_observation("ORG-ENT-B", inventory=5.0),
        ),
    )
    full = _inputs(
        declarations,
        observations=observations,
        information_mode="full_information_upper_bound",
    )
    assert full.nested_bounded is False
    plan = plan_quarter(full, mode="full_information_upper_bound", time_limit_s=10)
    assert plan.comparison_status == "NOT_COMPARABLE"


def test_observation_hash_recomputes_exactly() -> None:
    inputs = _inputs(_declarations())
    assert (
        observation_digest(
            inputs.observations,
            inputs.budget_observations,
            quarter=inputs.quarter,
        )
        == inputs.observation_hash
    )


# ---------------------------------------------------------------------------
# 3. Solver failure boundaries
# ---------------------------------------------------------------------------


def test_contradictory_funding_is_infeasible_and_never_executed() -> None:
    declarations = _declarations(
        organization_cash_opening=np.array([10.0, 10.0]),
        wage=np.full((4, 2), 100.0),
    )
    inputs = _inputs(
        declarations,
        budgets=(
            _budget_observation("ORG-ENT-A", 10.0, payer_id=0),
            _budget_observation("ORG-ENT-B", 10.0, payer_id=1),
        ),
    )
    plan = plan_quarter(inputs, mode="bounded_planning", time_limit_s=10)
    assert plan.status == "INFEASIBLE"
    assert plan.first_quarter_decisions == ()
    assert plan.certificates[-1].status == "INFEASIBLE"


def test_solver_timeout_is_not_an_executable_incumbent(monkeypatch) -> None:
    import hsm_lab.planning.rolling as rolling

    class Result:
        status = 1
        message = "synthetic timeout"
        x = np.array([1.0])
        ineqlin = None
        eqlin = None
        lower = None
        upper = None

    monkeypatch.setattr(rolling, "linprog", lambda *args, **kwargs: Result())
    plan = plan_quarter(_inputs(_declarations()), mode="bounded_planning", time_limit_s=1)
    assert plan.status == "TIMEOUT"
    assert plan.first_quarter_decisions == ()


def test_solver_nan_vector_is_rejected(monkeypatch) -> None:
    import hsm_lab.planning.rolling as rolling

    class Result:
        status = 0
        message = "synthetic malformed"
        x = np.array([np.nan])
        ineqlin = None
        eqlin = None
        lower = None
        upper = None

    monkeypatch.setattr(rolling, "linprog", lambda *args, **kwargs: Result())
    plan = plan_quarter(_inputs(_declarations()), mode="bounded_planning", time_limit_s=1)
    assert plan.status == "ERROR"
    assert plan.first_quarter_decisions == ()


# ---------------------------------------------------------------------------
# 4. Real kernel execution
# ---------------------------------------------------------------------------


def _execution_declarations(**overrides):
    base = {
        "organization_ids": ("ORG-ENT-B", "ORG-ENT-A"),
        "organization_bank": np.array([0, 0], dtype=np.int64),
        "organization_cash_opening": np.array([1000.0, 1000.0]),
        "inventory_opening": np.array([[10.0], [0.0]]),
        "edge_seller": np.array([0], dtype=np.int64),
        "edge_buyer": np.array([1], dtype=np.int64),
        "demand_buyer": np.array([1], dtype=np.int64),
        "demand_final": np.array([False]),
        "demand_id": ("A-procurement",),
        "recipe_id": (),
        "recipe_org": np.zeros(0, dtype=np.int64),
        "recipe_output_good": np.zeros(0, dtype=np.int64),
        "recipe_output_coeff": np.zeros(0),
        "recipe_input_ptr": np.array([0], dtype=np.int64),
        "recipe_capacity": np.zeros((4, 0)),
        "required_reports": (("ORG-ENT-A", "energy|standard"),),
    }
    base.update(overrides)
    return _declarations(**base)


def _execution_case(mode="bounded_planning"):
    fixture = make_two_region()
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "output", "energy")] = 10.0
    declarations = _execution_declarations()
    observations = (
        PlanningObservation(
            "ORG-ENT-A",
            "energy",
            "standard",
            _procurement_observation("ORG-ENT-A", supply=0.0, demand=10.0, inventory=0.0),
        ),
    )
    budgets = (_budget_observation("ORG-ENT-A", 1000.0, payer_id=1),)
    information_mode = (
        "full_information_upper_bound"
        if mode == "full_information_upper_bound"
        else "bounded_planning"
    )
    inputs = _inputs(
        declarations,
        observations=observations,
        budgets=budgets,
        information_mode=information_mode,
    )
    plan = plan_quarter(inputs, mode=mode, time_limit_s=10)
    return fixture, plan, inputs.observations, inputs.budget_observations, inputs


def test_real_kernel_executes_one_quarter_and_reconciles() -> None:
    fixture, plan, observations, budgets, inputs = _execution_case()
    assert plan.status == "FEASIBLE"
    assert len(plan.first_quarter_decisions) == 1
    assert plan.first_quarter_decisions[0].requested_quantity == pytest.approx(10.0)
    calendar = _calendar("ORG-ENT-A", "ORG-ENT-B")
    session = _session(fixture.state)
    result = execute_rolling_proposal(
        plan,
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        calendar=calendar,
        session=session,
        observations=observations,
        budget_observations=budgets,
        inputs=inputs,
        organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
    )
    assert result.execution_status in ("EXECUTED", "PARTIAL")
    assert result.completed_ticks_before == 0
    assert result.completed_ticks_after == 1
    assert fixture.state.completed_ticks == 1
    assert result.submitted[0].delivered_quantity > 0.0
    assert result.submitted[0].goods_payment > 0.0
    assert result.measurement.max_material_ratio <= 1.0
    assert result.measurement.max_finance_ratio <= 1.0
    assert result.measurement.max_payment_residual <= 1e-9
    assert result.measurement.max_stock_residual <= 1e-9
    assert result.measurement.max_bank_residual <= 1e-9
    assert any(row.kind == "goods_payment" for row in result.measurement.journal)


def test_future_quarter_mutation_is_ignored_by_execution() -> None:
    fixture, plan, observations, budgets, inputs = _execution_case()
    mutated_quarters = list(plan.quarterly)
    quarter_two = mutated_quarters[1]
    mutated_quarters[1] = dataclasses.replace(
        quarter_two,
        purchases=quarter_two.purchases + 1_000_000.0,
        shortfall=quarter_two.shortfall + 1_000_000.0,
    )
    mutated = dataclasses.replace(plan, quarterly=tuple(mutated_quarters))
    calendar = _calendar("ORG-ENT-A", "ORG-ENT-B")
    session = _session(fixture.state)
    result = execute_rolling_proposal(
        mutated,
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        calendar=calendar,
        session=session,
        observations=observations,
        budget_observations=budgets,
        inputs=inputs,
        organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
    )
    assert result.completed_ticks_after == 1
    assert result.submitted[0].requested_quantity == pytest.approx(10.0)


def test_future_decision_quarter_is_rejected_without_mutation() -> None:
    fixture, plan, observations, budgets, inputs = _execution_case()
    from hsm_lab.institutions.decisions import ActorRole, ProcurementDecision

    future = ProcurementDecision(
        decision_id="future",
        actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
        organization_id="ORG-ENT-A",
        sector_id="industry",
        quarter="1957Q2",
        decision_at=date(1957, 4, 15),
        available_at=date(1957, 4, 10),
        commodity_id="energy",
        requested_quantity=10.0,
    )
    mutated = dataclasses.replace(plan, first_quarter_decisions=(future,))
    before = copy.deepcopy(fixture.state)
    calendar = _calendar("ORG-ENT-A", "ORG-ENT-B")
    session = _session(fixture.state)
    with pytest.raises(ResearchGateError):
        execute_rolling_proposal(
            mutated,
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            calendar=calendar,
            session=session,
            observations=observations,
            budget_observations=budgets,
            inputs=inputs,
            organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
        )
    assert fixture.state.completed_ticks == before.completed_ticks
    assert np.array_equal(fixture.state.stock_value, before.stock_value)
    assert np.array_equal(fixture.state.organization_cash, before.organization_cash)


def test_existing_controls_conflict_is_rejected_before_tick() -> None:
    fixture, plan, observations, budgets, inputs = _execution_case()
    controls = TickControls(
        material_parameters=fixture.parameters,
        household_parameters=fixture.network.household_parameters,
        household_catalog=fixture.network.household_catalog,
        autonomy=0.0,
        central_target=None,
        policy=None,
        procurement_requests=((3, fixture.network.commodity_ids.index("energy"), 5.0),),
    )
    calendar = _calendar("ORG-ENT-A", "ORG-ENT-B")
    session = _session(fixture.state)
    with pytest.raises(ResearchGateError, match="controls"):
        execute_rolling_proposal(
            plan,
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            calendar=calendar,
            session=session,
            observations=observations,
            budget_observations=budgets,
            inputs=inputs,
            organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
            controls=controls,
        )
    assert fixture.state.completed_ticks == 0


def test_empty_plan_still_advances_one_legal_quarter() -> None:
    fixture = make_two_region()
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "output", "energy")] = 0.0
    declarations = _execution_declarations(
        inventory_opening=np.array([[0.0], [10.0]]),
        demand_ordered=np.full((4, 1), 10.0),
        demand_gross=np.full((4, 1), 10.0),
    )
    inputs = _inputs(declarations)
    empty = plan_quarter(inputs, mode="bounded_planning", time_limit_s=10)
    assert empty.first_quarter_decisions == ()
    result = execute_rolling_proposal(
        empty,
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        calendar=_calendar("ORG-ENT-A", "ORG-ENT-B"),
        session=_session(fixture.state),
        observations=inputs.observations,
        budget_observations=inputs.budget_observations,
        inputs=inputs,
        organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
    )
    assert result.execution_status == "NO_REQUESTS"
    assert fixture.state.completed_ticks == 1


def test_tampered_observation_hash_is_rejected() -> None:
    fixture, plan, observations, budgets, inputs = _execution_case()
    wrong = dataclasses.replace(plan, observation_hash="0" * 64)
    calendar = _calendar("ORG-ENT-A", "ORG-ENT-B")
    session = _session(fixture.state)
    with pytest.raises(ResearchGateError, match="observation hash"):
        execute_rolling_proposal(
            wrong,
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            calendar=calendar,
            session=session,
            observations=observations,
            budget_observations=budgets,
            inputs=inputs,
            organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
        )
    assert fixture.state.completed_ticks == 0


# ---------------------------------------------------------------------------
# 5. Lexicographic priority, terminal mask and execution admission
# ---------------------------------------------------------------------------


def test_household_shortfall_is_minimized_before_other_demand() -> None:
    declarations = _declarations(
        inventory_opening=np.array([[10.0], [0.0]]),
        demand_id=("B-final", "B-other"),
        demand_buyer=np.array([1, 1], dtype=np.int64),
        demand_good=np.array([0, 0], dtype=np.int64),
        demand_final=np.array([True, False]),
        demand_ordered=np.array([[10.0, 10.0]] * 4),
        demand_gross=np.array([[10.0, 10.0]] * 4),
    )
    plan = plan_quarter(_inputs(declarations), mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert abs(float(plan.quarterly[0].shortfall[0])) <= 1e-6
    assert plan.quarterly[0].shortfall[1] == pytest.approx(10.0, abs=1e-6)


def test_terminal_mask_keeps_inactive_slots_inactive() -> None:
    declarations = _declarations(
        terminal_mask=(True, False, False, False),
        inventory_opening=np.array([[10.0], [0.0]]),
    )
    plan = plan_quarter(_inputs(declarations), mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert plan.quarterly[0].active is True
    for quarter in plan.quarterly[1:]:
        assert quarter.active is False
        assert float(np.sum(quarter.purchases)) == pytest.approx(0.0)
        assert float(np.sum(quarter.inventory)) == pytest.approx(0.0)


def test_funding_budget_binds_before_the_solver_invents_money() -> None:
    declarations = _declarations(
        inventory_opening=np.array([[10.0], [0.0]]),
        organization_cash_opening=np.zeros(2),
    )
    inputs = _inputs(
        declarations,
        budgets=(
            _budget_observation("ORG-ENT-A", 1000.0, payer_id=0),
            _budget_observation("ORG-ENT-B", 5.0, payer_id=1),
        ),
    )
    plan = plan_quarter(inputs, mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert plan.first_quarter_decisions[0].requested_quantity == pytest.approx(5.0)
    assert plan.quarterly[0].purchases[1, 0] == pytest.approx(5.0)
    assert plan.quarterly[0].financing[1] == pytest.approx(5.0)


def test_bounded_opening_cash_report_is_used() -> None:
    declarations = _declarations(
        inventory_opening=np.array([[10.0], [0.0]]),
        organization_cash_opening=np.array([0.0, 10.0]),
        funding_group_capacity=np.zeros((4, 2)),
        organization_order_financing=np.zeros((4, 2)),
    )
    inputs = _inputs(
        declarations,
        budgets=(
            _budget_observation("ORG-ENT-A", 0.0, payer_id=0),
            _budget_observation("ORG-ENT-B", 0.0, payer_id=1),
        ),
    )
    assert inputs.cash_initial[1] == pytest.approx(10.0)
    plan = plan_quarter(inputs, mode="historical_rule_based", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert sum(item.requested_quantity for item in plan.first_quarter_decisions) == pytest.approx(
        10.0
    )


def test_rule_reserves_shared_financing_across_two_goods() -> None:
    declarations = _declarations(
        goods_id=("energy|standard", "capital_goods|standard"),
        goods_is_service=np.array([False, False]),
        prices=np.ones((4, 2)),
        inventory_opening=np.array([[10.0, 10.0], [0.0, 0.0]]),
        organization_cash_opening=np.zeros(2),
        edge_id=np.array([0, 1], dtype=np.int64),
        edge_seller=np.array([0, 0], dtype=np.int64),
        edge_buyer=np.array([1, 1], dtype=np.int64),
        edge_good=np.array([0, 1], dtype=np.int64),
        edge_unit_price=np.array([1.0, 1.0]),
        edge_transport_org=np.full(2, -1, dtype=np.int64),
        edge_freight_per_unit=np.zeros(2),
        edge_handling_per_unit=np.ones(2),
        edge_capacity=np.full((4, 2), 100.0),
        demand_id=("B-energy", "B-capital"),
        demand_buyer=np.array([1, 1], dtype=np.int64),
        demand_good=np.array([0, 1], dtype=np.int64),
        demand_final=np.array([True, True]),
        demand_ordered=np.full((4, 2), 10.0),
        demand_gross=np.full((4, 2), 10.0),
        recipe_id=(),
        recipe_org=np.zeros(0, dtype=np.int64),
        recipe_output_good=np.zeros(0, dtype=np.int64),
        recipe_output_coeff=np.zeros(0),
        recipe_input_ptr=np.array([0], dtype=np.int64),
        recipe_capacity=np.zeros((4, 0)),
        required_reports=(),
    )
    budgets = (
        _budget_observation("ORG-ENT-A", 0.0, payer_id=0),
        _budget_observation("ORG-ENT-B", 5.0, payer_id=1),
    )
    plan = plan_quarter(
        _inputs(declarations, budgets=budgets),
        mode="historical_rule_based",
        time_limit_s=10,
    )
    assert plan.status == "FEASIBLE"
    total = sum(item.requested_quantity for item in plan.first_quarter_decisions)
    assert total == pytest.approx(5.0)
    assert plan.quarterly[0].cash[1] >= -1e-9


def test_edge_baseline_is_a_lower_bound_and_incremental_request() -> None:
    declarations = _declarations(
        inventory_opening=np.array([[10.0], [0.0]]),
        edge_baseline=np.array([[5.0], [0.0], [0.0], [0.0]]),
        baseline_procurement=np.array(
            [[[0.0], [5.0]], [[0.0], [0.0]], [[0.0], [0.0]], [[0.0], [0.0]]]
        ),
    )
    plan = plan_quarter(
        _inputs(declarations),
        mode="bounded_planning",
        time_limit_s=10,
    )
    assert plan.status == "FEASIBLE"
    assert plan.quarterly[0].purchases[1, 0] == pytest.approx(10.0)
    assert plan.first_quarter_decisions[0].requested_quantity == pytest.approx(5.0)


def _payload_hash(decisions):
    import hashlib

    digest = hashlib.sha256()
    for decision in sorted(decisions, key=lambda item: item.decision_id):
        digest.update(decision.model_dump_json().encode("utf-8"))
    return digest.hexdigest()


def test_duplicate_decisions_are_rejected_before_tick() -> None:
    fixture, plan, observations, budgets, inputs = _execution_case()
    first = plan.first_quarter_decisions[0]
    duplicate = first.model_copy(update={"decision_id": first.decision_id + "-dup"})
    mutated = dataclasses.replace(
        plan,
        first_quarter_decisions=(first, duplicate),
        first_quarter_payload_hash=_payload_hash((first, duplicate)),
        plan_hash="",
    )
    calendar = _calendar("ORG-ENT-A", "ORG-ENT-B")
    session = _session(fixture.state)
    with pytest.raises(ResearchGateError, match="duplicate"):
        execute_rolling_proposal(
            mutated,
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            calendar=calendar,
            session=session,
            observations=observations,
            budget_observations=budgets,
            inputs=inputs,
            organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
        )
    assert fixture.state.completed_ticks == 0


def test_non_feasible_plan_is_not_executable() -> None:
    fixture, plan, observations, budgets, inputs = _execution_case()
    bad = dataclasses.replace(plan, status="INFEASIBLE")
    calendar = _calendar("ORG-ENT-A", "ORG-ENT-B")
    session = _session(fixture.state)
    with pytest.raises(ResearchGateError, match="not executable"):
        execute_rolling_proposal(
            bad,
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            calendar=calendar,
            session=session,
            observations=observations,
            budget_observations=budgets,
            inputs=inputs,
            organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
        )
    assert fixture.state.completed_ticks == 0


@pytest.mark.parametrize("mode", ARMS)
def test_three_arms_execute_on_the_real_network(mode: str) -> None:
    fixture, plan, observations, budgets, inputs = _execution_case(mode)
    assert plan.status == "FEASIBLE"
    assert plan.first_quarter_decisions
    calendar = _calendar("ORG-ENT-A", "ORG-ENT-B")
    session = _session(fixture.state)
    result = execute_rolling_proposal(
        plan,
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        calendar=calendar,
        session=session,
        observations=observations,
        budget_observations=budgets,
        inputs=inputs,
        organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
    )
    assert result.execution_status in ("EXECUTED", "PARTIAL")
    assert result.completed_ticks_before == 0
    assert result.completed_ticks_after == 1
    assert result.submitted[0].delivered_quantity > 0.0
    assert result.submitted[0].goods_payment > 0.0
    assert any(row.kind == "goods_payment" for row in result.measurement.journal)


def test_gross_demand_not_ordered_cap_drives_shortfall() -> None:
    declarations = _declarations(
        demand_ordered=np.full((4, 1), 10.0),
        demand_gross=np.full((4, 1), 100.0),
    )
    inputs = _inputs(declarations)
    plan = plan_quarter(inputs, mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert plan.quarterly[0].shortfall[0] == pytest.approx(100.0, abs=1e-6)
    assert float(np.sum(plan.quarterly[0].final_use)) <= 10.0 + 1e-6


def test_two_demands_cannot_double_spend_the_same_opening_stock() -> None:
    declarations = _declarations(
        inventory_opening=np.array([[10.0], [0.0]]),
        demand_id=("B-final", "B-other"),
        demand_buyer=np.array([1, 1], dtype=np.int64),
        demand_good=np.array([0, 0], dtype=np.int64),
        demand_final=np.array([True, False]),
        demand_ordered=np.array([[10.0, 10.0]] * 4),
        demand_gross=np.array([[10.0, 10.0]] * 4),
    )
    plan = plan_quarter(_inputs(declarations), mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    total_use = float(plan.quarterly[0].final_use[0]) + (
        10.0 - float(plan.quarterly[0].shortfall[1])
    )
    assert total_use <= 10.0 + 1e-6


def test_unlike_services_cannot_substitute() -> None:
    declarations = _declarations(
        goods_id=("energy|standard", "heat|service", "freight|service"),
        goods_is_service=np.array([False, True, True]),
        prices=np.ones((4, 3)),
        inventory_opening=np.zeros((2, 3)),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.array([[5.0, 0.0]] * 4),
        handling_capacity=np.full((4, 2), 1000.0),
        edge_good=np.array([0], dtype=np.int64),
        demand_id=("B-freight",),
        demand_buyer=np.array([1], dtype=np.int64),
        demand_good=np.array([2], dtype=np.int64),
        demand_final=np.array([True]),
        demand_ordered=np.full((4, 1), 5.0),
        demand_gross=np.full((4, 1), 5.0),
        recipe_id=("A-energy", "A-heat"),
        recipe_org=np.array([0, 0], dtype=np.int64),
        recipe_output_good=np.array([0, 1], dtype=np.int64),
        recipe_output_coeff=np.array([1.0, 1.0]),
        recipe_input_ptr=np.array([0, 0, 0], dtype=np.int64),
        recipe_input_good=np.zeros(0, dtype=np.int64),
        recipe_input_coeff=np.zeros(0),
        recipe_capacity=np.array([[0.0, 5.0]] * 4),
        service_split=(0.0, 0.0, 1.0),
    )
    plan = plan_quarter(_inputs(declarations), mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert plan.quarterly[0].shortfall[0] == pytest.approx(5.0, abs=1e-6)
    assert plan.quarterly[0].service_lost_by_good[0, 1] >= 5.0 - 1e-6


def test_cross_bank_prepayment_blocks_without_a_bank_report_value() -> None:
    declarations = _declarations(
        bank_count=2,
        organization_bank=np.array([0, 1], dtype=np.int64),
        bank_reserves=np.zeros((4, 2)),
        inventory_opening=np.array([[10.0], [0.0]]),
    )
    budgets = (
        _budget_observation("ORG-ENT-A", 1000.0, payer_id=0),
        _budget_observation("ORG-ENT-B", 1000.0, payer_id=1),
        _budget_observation(
            "ORG-ENT-B",
            0.0,
            payer_id=0,
            payer_kind="bank_prepayment",
        ),
        _budget_observation(
            "ORG-ENT-B",
            0.0,
            payer_id=1,
            payer_kind="bank_prepayment",
        ),
    )
    plan = plan_quarter(
        _inputs(declarations, budgets=budgets),
        mode="bounded_planning",
        time_limit_s=10,
    )
    assert plan.status == "FEASIBLE"
    assert plan.first_quarter_decisions == ()
    assert plan.quarterly[0].shortfall[0] == pytest.approx(10.0, abs=1e-6)


def test_shared_funding_group_caps_total_purchases() -> None:
    declarations = _declarations(
        organization_funding_group=np.array([0, 0], dtype=np.int64),
        funding_group_capacity=np.full((4, 1), 5.0),
        inventory_opening=np.array([[10.0], [0.0]]),
        organization_cash_opening=np.zeros(2),
    )
    budgets = (
        _budget_observation("ORG-ENT-A", 5.0, payer_id=0),
        _budget_observation("ORG-ENT-B", 5.0, payer_id=0),
    )
    plan = plan_quarter(
        _inputs(declarations, budgets=budgets),
        mode="bounded_planning",
        time_limit_s=10,
    )
    assert plan.status == "FEASIBLE"
    assert float(np.sum(plan.quarterly[0].purchases)) <= 5.0 + 1e-6


def test_wage_and_interest_are_pre_deducted_before_purchase() -> None:
    declarations = _declarations(
        inventory_opening=np.array([[10.0], [0.0]]),
        wage=np.array([[0.0, 5.0]] * 4),
        organization_interest=np.array([[0.0, 5.0]] * 4),
        organization_cash_opening=np.zeros(2),
    )
    budgets = (
        _budget_observation("ORG-ENT-A", 10.0, payer_id=0),
        _budget_observation("ORG-ENT-B", 10.0, payer_id=1),
    )
    plan = plan_quarter(
        _inputs(declarations, budgets=budgets),
        mode="bounded_planning",
        time_limit_s=10,
    )
    assert plan.status == "FEASIBLE"
    assert plan.first_quarter_decisions == ()
    assert plan.quarterly[0].shortfall[0] == pytest.approx(10.0, abs=1e-6)


def _state_inventory(fixture, organization_index: int, commodity_id: str = "energy") -> float:
    commodity_index = fixture.network.commodity_ids.index(commodity_id)
    cells = np.flatnonzero(
        (np.asarray(fixture.network.cell_owner_kind) == 0)
        & (np.asarray(fixture.network.cell_owner_id) == organization_index)
        & (np.asarray(fixture.network.cell_commodity) == commodity_index)
    )
    return float(np.sum(fixture.state.stock_value[cells]))


def test_second_quarter_replans_from_refreshed_observations() -> None:
    fixture, plan, observations, budgets, inputs = _execution_case()
    calendar = _calendar("ORG-ENT-A", "ORG-ENT-B")
    first = execute_rolling_proposal(
        plan,
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        calendar=calendar,
        session=_session(fixture.state),
        observations=observations,
        budget_observations=budgets,
        inputs=inputs,
        organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
    )
    assert first.completed_ticks_after == 1
    decision_at = date(1957, 4, 15)
    available_at = date(1957, 4, 10)
    observations_two = tuple(
        PlanningObservation(
            label,
            "energy",
            "standard",
            _procurement_observation(
                label,
                quarter="1957Q2",
                supply=0.0,
                demand=10.0 if label == "ORG-ENT-A" else 0.0,
                inventory=_state_inventory(fixture, organization_index),
                decision_at=decision_at,
                available_at=available_at,
            ),
        )
        for label, organization_index in (("ORG-ENT-B", 1), ("ORG-ENT-A", 3))
    )
    budgets_two = (
        _budget_observation(
            "ORG-ENT-A",
            1000.0,
            payer_id=1,
            quarter="1957Q2",
            decision_at=decision_at,
            available_at=available_at,
        ),
    )
    declarations_two = dataclasses.replace(
        _execution_declarations(),
        quarters=("1957Q2", "1957Q3", "1957Q4", "1958Q1"),
    )
    inputs_two = _inputs(
        declarations_two,
        observations=observations_two,
        budgets=budgets_two,
        include_defaults=False,
        quarter="1957Q2",
        decision_at=decision_at,
    )
    plan_two = plan_quarter(inputs_two, mode="bounded_planning", time_limit_s=10)
    assert plan_two.observation_hash != plan.observation_hash
    second = execute_rolling_proposal(
        plan_two,
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        calendar=calendar,
        session=_session(fixture.state),
        observations=inputs_two.observations,
        budget_observations=inputs_two.budget_observations,
        inputs=inputs_two,
        organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
    )
    assert second.completed_ticks_before == 1
    assert second.completed_ticks_after == 2
    assert fixture.state.completed_ticks == 2


def _state_digest(state) -> str:
    import hashlib

    digest = hashlib.sha256()
    for field in state.__dataclass_fields__:
        value = getattr(state, field)
        digest.update(field.encode("utf-8"))
        if isinstance(value, np.ndarray):
            digest.update(np.ascontiguousarray(value).tobytes())
        else:
            digest.update(repr(value).encode("utf-8"))
    return digest.hexdigest()


def test_tick_failure_rolls_back_every_state_field(monkeypatch) -> None:
    fixture, plan, observations, budgets, inputs = _execution_case()
    before = _state_digest(fixture.state)

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic gate failure")

    monkeypatch.setattr("hsm_lab.engine.accounting.check_material_invariants", fail)
    with pytest.raises(RollingExecutionFailure):
        execute_rolling_proposal(
            plan,
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            calendar=_calendar("ORG-ENT-A", "ORG-ENT-B"),
            session=_session(fixture.state),
            observations=observations,
            budget_observations=budgets,
            inputs=inputs,
            organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
        )
    assert _state_digest(fixture.state) == before
    assert fixture.state.completed_ticks == 0


def test_solver_exception_becomes_an_error_certificate(monkeypatch) -> None:
    import hsm_lab.planning.rolling as rolling

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic solver exception")

    monkeypatch.setattr(rolling, "linprog", fail)
    plan = plan_quarter(_inputs(_declarations()), mode="bounded_planning", time_limit_s=10)
    assert plan.status == "ERROR"
    assert plan.first_quarter_decisions == ()
    assert "solver raised" in plan.certificates[-1].failure_reason


def test_hard_deadline_marks_a_late_optimal_solve_timeout(monkeypatch) -> None:
    import time as _time

    import hsm_lab.planning.rolling as rolling

    real = rolling.linprog

    def slow(*args, **kwargs):
        _time.sleep(0.05)
        return real(*args, **kwargs)

    monkeypatch.setattr(rolling, "linprog", slow)
    plan = plan_quarter(_inputs(_declarations()), mode="bounded_planning", time_limit_s=0.01)
    assert plan.status == "TIMEOUT"
    assert plan.first_quarter_decisions == ()


def test_frozen_input_arrays_cannot_be_mutated() -> None:
    inputs = _inputs(_declarations())
    with pytest.raises(ValueError):
        inputs.inventory_initial.setflags(write=True)
    assert inputs.digest() == inputs.input_hash


def test_early_service_cannot_consume_same_quarter_fuel() -> None:
    declarations = _declarations(
        goods_id=("fuel|standard", "transport|service"),
        goods_is_service=np.array([False, True]),
        prices=np.ones((4, 2)),
        inventory_opening=np.array([[0.0, 0.0], [10.0, 0.0]]),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.zeros((4, 2)),
        handling_capacity=np.full((4, 2), 1000.0),
        edge_id=np.array([0], dtype=np.int64),
        edge_seller=np.array([1], dtype=np.int64),
        edge_buyer=np.array([0], dtype=np.int64),
        edge_good=np.array([0], dtype=np.int64),
        edge_transport_org=np.array([0], dtype=np.int64),
        edge_freight_per_unit=np.array([1.0]),
        edge_handling_per_unit=np.array([1.0]),
        demand_id=("A-fuel",),
        demand_buyer=np.array([0], dtype=np.int64),
        demand_good=np.array([0], dtype=np.int64),
        demand_final=np.array([False]),
        demand_ordered=np.full((4, 1), 10.0),
        demand_gross=np.full((4, 1), 10.0),
        recipe_id=("carrier-service",),
        recipe_org=np.array([0], dtype=np.int64),
        recipe_output_good=np.array([1], dtype=np.int64),
        recipe_output_coeff=np.array([1.0]),
        recipe_input_ptr=np.array([0, 1], dtype=np.int64),
        recipe_input_good=np.array([0], dtype=np.int64),
        recipe_input_coeff=np.array([1.0]),
        recipe_capacity=np.full((4, 1), 10.0),
        required_reports=(),
    )
    plan = plan_quarter(_inputs(declarations), mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert plan.first_quarter_decisions == ()
    assert plan.quarterly[0].shortfall[0] == pytest.approx(10.0, abs=1e-6)
    assert float(np.sum(plan.quarterly[0].purchases)) == pytest.approx(0.0, abs=1e-6)


def test_declared_service_split_caps_current_use() -> None:
    declarations = _declarations(
        goods_id=("energy|standard", "transport|service"),
        goods_is_service=np.array([False, True]),
        prices=np.ones((4, 2)),
        inventory_opening=np.zeros((2, 2)),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.zeros((4, 2)),
        handling_capacity=np.full((4, 2), 1000.0),
        edge_good=np.array([0], dtype=np.int64),
        demand_id=("A-service",),
        demand_buyer=np.array([0], dtype=np.int64),
        demand_good=np.array([1], dtype=np.int64),
        demand_final=np.array([True]),
        demand_ordered=np.full((4, 1), 10.0),
        demand_gross=np.full((4, 1), 10.0),
        recipe_id=("A-energy", "A-service"),
        recipe_org=np.array([0, 0], dtype=np.int64),
        recipe_output_good=np.array([0, 1], dtype=np.int64),
        recipe_output_coeff=np.array([1.0, 1.0]),
        recipe_input_ptr=np.array([0, 1, 1], dtype=np.int64),
        recipe_input_good=np.array([0], dtype=np.int64),
        recipe_input_coeff=np.array([1.0]),
        recipe_capacity=np.array([[0.0, 10.0]] * 4),
        service_split=(0.25, 0.25, 0.5),
    )
    plan = plan_quarter(_inputs(declarations), mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert plan.quarterly[0].service_used[0] <= 5.0 + 1e-6
    assert plan.quarterly[0].shortfall[0] == pytest.approx(5.0, abs=1e-6)


def test_bank_stock_is_carried_across_quarters() -> None:
    declarations = _declarations(
        bank_reserves=np.full((4, 1), 100.0),
        inventory_opening=np.zeros((2, 1)),
    )
    inputs = _inputs(declarations, information_mode="full_information_upper_bound")
    plan = plan_quarter(inputs, mode="full_information_upper_bound", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert all(quarter.bank_cash[0] == pytest.approx(100.0) for quarter in plan.quarterly)


def test_cross_currency_trade_is_rejected() -> None:
    with pytest.raises(ResearchGateError, match="cross-currency"):
        _declarations(organization_currency=("USD", "HUF"))


def test_rule_obeys_wage_interest_and_handling() -> None:
    wage_inputs = _inputs(
        _declarations(
            inventory_opening=np.array([[10.0], [0.0]]),
            wage=np.array([[0.0, 5.0]] * 4),
            organization_interest=np.array([[0.0, 5.0]] * 4),
            organization_cash_opening=np.zeros(2),
        ),
        budgets=(
            _budget_observation("ORG-ENT-A", 10.0, payer_id=0),
            _budget_observation("ORG-ENT-B", 10.0, payer_id=1),
        ),
    )
    rule = plan_quarter(wage_inputs, mode="historical_rule_based", time_limit_s=10)
    assert rule.status == "FEASIBLE"
    assert rule.first_quarter_decisions == ()
    handling_inputs = _inputs(
        _declarations(
            inventory_opening=np.array([[10.0], [0.0]]),
            handling_capacity=np.zeros((4, 2)),
        )
    )
    handling_rule = plan_quarter(handling_inputs, mode="historical_rule_based", time_limit_s=10)
    assert handling_rule.status == "FEASIBLE"
    assert handling_rule.first_quarter_decisions == ()


def test_missing_or_mutated_certificates_are_rejected() -> None:
    fixture, plan, observations, budgets, inputs = _execution_case()
    empty = dataclasses.replace(plan, certificates=(), plan_hash="")
    calendar = _calendar("ORG-ENT-A", "ORG-ENT-B")
    with pytest.raises(ResearchGateError, match="certificate"):
        execute_rolling_proposal(
            empty,
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            calendar=calendar,
            session=_session(fixture.state),
            observations=observations,
            budget_observations=budgets,
            inputs=inputs,
            organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
        )
    bad_certificate = dataclasses.replace(plan.certificates[0], status="ERROR")
    mutated = dataclasses.replace(
        plan,
        certificates=(bad_certificate, *plan.certificates[1:]),
        plan_hash="",
    )
    with pytest.raises(ResearchGateError, match="certificate|not feasible"):
        execute_rolling_proposal(
            mutated,
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            calendar=calendar,
            session=_session(fixture.state),
            observations=observations,
            budget_observations=budgets,
            inputs=inputs,
            organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
        )


def test_goods_is_service_is_frozen_and_hashed() -> None:
    inputs = _inputs(_declarations())
    with pytest.raises(ValueError):
        inputs.goods_is_service.setflags(write=True)
    assert inputs.digest() == inputs.input_hash


def test_total_plan_and_incremental_request_are_measured_separately() -> None:
    fixture = make_two_region()
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "output", "energy")] = 20.0
    declarations = _execution_declarations(
        inventory_opening=np.array([[20.0], [0.0]]),
        demand_ordered=np.full((4, 1), 20.0),
        demand_gross=np.full((4, 1), 20.0),
        baseline_procurement=np.array([[[0.0], [4.0]]] * 4),
    )
    inputs = _inputs(declarations)
    plan = plan_quarter(inputs, mode="bounded_planning", time_limit_s=10)
    assert plan.first_quarter_decisions[0].requested_quantity == pytest.approx(16.0, abs=1e-6)
    result = execute_rolling_proposal(
        plan,
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        calendar=_calendar("ORG-ENT-A", "ORG-ENT-B"),
        session=_session(fixture.state),
        observations=inputs.observations,
        budget_observations=inputs.budget_observations,
        inputs=inputs,
        organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
    )
    row = result.submitted[0]
    assert row.total_planned_quantity == pytest.approx(20.0, abs=1e-6)
    assert row.baseline_quantity == pytest.approx(4.0, abs=1e-6)
    assert row.incremental_quantity == pytest.approx(16.0, abs=1e-6)
    assert row.plan_actual_gap == pytest.approx(
        max(0.0, row.total_planned_quantity - row.delivered_quantity)
    )
    assert result.measurement.procurement_delivered_by_commodity.any()


def test_missing_service_report_blocks_before_the_solver() -> None:
    declarations = _declarations(
        goods_id=("energy|standard", "transport|service"),
        goods_is_service=np.array([False, True]),
        prices=np.ones((4, 2)),
        inventory_opening=np.zeros((2, 2)),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.zeros((4, 2)),
        handling_capacity=np.full((4, 2), 1000.0),
        demand_id=("A-service",),
        demand_buyer=np.array([0], dtype=np.int64),
        demand_good=np.array([1], dtype=np.int64),
        demand_final=np.array([True]),
        demand_ordered=np.full((4, 1), 5.0),
        demand_gross=np.full((4, 1), 5.0),
        recipe_id=("A-service",),
        recipe_org=np.array([0], dtype=np.int64),
        recipe_output_good=np.array([1], dtype=np.int64),
        recipe_output_coeff=np.array([1.0]),
        recipe_input_ptr=np.array([0, 0], dtype=np.int64),
        recipe_input_good=np.zeros(0, dtype=np.int64),
        recipe_input_coeff=np.zeros(0),
        recipe_capacity=np.full((4, 1), 5.0),
        required_reports=(),
    )
    with pytest.raises(ResearchGateError, match="required report"):
        _inputs(declarations, observations=(), include_defaults=False)


def test_early_service_recipes_share_one_opening_fuel_pool() -> None:
    declarations = _declarations(
        goods_id=("fuel|standard", "heat|service", "freight|service"),
        goods_is_service=np.array([False, True, True]),
        prices=np.ones((4, 3)),
        inventory_opening=np.array([[5.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.zeros((4, 2)),
        handling_capacity=np.full((4, 2), 1000.0),
        edge_good=np.array([0], dtype=np.int64),
        demand_id=("A-heat",),
        demand_buyer=np.array([0], dtype=np.int64),
        demand_good=np.array([1], dtype=np.int64),
        demand_final=np.array([True]),
        demand_ordered=np.full((4, 1), 10.0),
        demand_gross=np.full((4, 1), 10.0),
        recipe_id=("heat", "freight"),
        recipe_org=np.array([0, 0], dtype=np.int64),
        recipe_output_good=np.array([1, 2], dtype=np.int64),
        recipe_output_coeff=np.array([1.0, 1.0]),
        recipe_input_ptr=np.array([0, 1, 2], dtype=np.int64),
        recipe_input_good=np.array([0, 0], dtype=np.int64),
        recipe_input_coeff=np.array([1.0, 1.0]),
        recipe_capacity=np.array([[5.0, 5.0]] * 4),
        service_split=(0.0, 0.0, 1.0),
        required_reports=(),
    )
    plan = plan_quarter(_inputs(declarations), mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert float(np.sum(plan.quarterly[0].service_produced_by_good[0])) <= 5.0 + 1e-6


def test_rule_rejects_wage_before_receipts_without_funding() -> None:
    declarations = _declarations(
        inventory_opening=np.array([[10.0], [0.0]]),
        wage=np.array([[0.0, 5.0]] * 4),
        funding_group_capacity=np.zeros((4, 2)),
        organization_order_financing=np.zeros((4, 2)),
        organization_cash_opening=np.zeros(2),
    )
    budgets = (
        _budget_observation("ORG-ENT-A", 0.0, payer_id=0),
        _budget_observation("ORG-ENT-B", 0.0, payer_id=1),
    )
    rule = plan_quarter(
        _inputs(declarations, budgets=budgets),
        mode="historical_rule_based",
        time_limit_s=10,
    )
    assert rule.status == "INFEASIBLE"
    assert any("pre_receipt" in name for name in rule.certificates[0].row_names)


def test_certificate_primal_contents_are_bound_and_finite() -> None:
    fixture, plan, observations, budgets, inputs = _execution_case()
    certificate = dataclasses.replace(
        plan.certificates[0],
        primal=np.full_like(plan.certificates[0].primal, np.nan),
    )
    mutated = dataclasses.replace(
        plan,
        certificates=(certificate, *plan.certificates[1:]),
        plan_hash="",
    )
    with pytest.raises(ResearchGateError, match="certificate"):
        execute_rolling_proposal(
            mutated,
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            calendar=_calendar("ORG-ENT-A", "ORG-ENT-B"),
            session=_session(fixture.state),
            observations=observations,
            budget_observations=budgets,
            inputs=inputs,
            organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
        )


def test_published_price_binds_purchase_affordability() -> None:
    declarations = _declarations(inventory_opening=np.array([[10.0], [0.0]]))
    observations = (
        PlanningObservation(
            "ORG-ENT-B",
            "energy",
            "standard",
            _procurement_observation("ORG-ENT-B", price=100.0),
        ),
        PlanningObservation(
            "ORG-ENT-A",
            "energy",
            "standard",
            _procurement_observation("ORG-ENT-A", price=100.0),
        ),
    )
    inputs = _inputs(
        declarations,
        observations=observations,
        budgets=(
            _budget_observation("ORG-ENT-A", 1000.0, payer_id=0),
            _budget_observation("ORG-ENT-B", 10.0, payer_id=1),
        ),
    )
    plan = plan_quarter(inputs, mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert (
        float(np.sum([np.sum(quarter.purchases[1, 0]) for quarter in plan.quarterly])) <= 0.1 + 1e-6
    )
    assert (
        float(np.sum([np.sum(quarter.goods_payment) for quarter in plan.quarterly])) <= 10.0 + 1e-6
    )


def test_finite_but_invalid_certificate_is_rejected() -> None:
    fixture, plan, observations, budgets, inputs = _execution_case()
    certificate = plan.certificates[0]
    invalid = dataclasses.replace(
        certificate,
        primal=np.full_like(certificate.primal, -123.0),
        row_activity=np.full_like(certificate.row_activity, 999.0),
        row_residual=np.full_like(certificate.row_residual, 999.0),
    )
    mutated = dataclasses.replace(
        plan,
        certificates=(invalid, *plan.certificates[1:]),
        plan_hash="",
    )
    with pytest.raises(ResearchGateError, match="certificate verification"):
        execute_rolling_proposal(
            mutated,
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            calendar=_calendar("ORG-ENT-A", "ORG-ENT-B"),
            session=_session(fixture.state),
            observations=observations,
            budget_observations=budgets,
            inputs=inputs,
            organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
        )


def test_service_dependency_tiers_allow_heat_then_freight() -> None:
    declarations = _declarations(
        goods_id=("fuel|standard", "heat|service", "freight|service"),
        goods_is_service=np.array([False, True, True]),
        prices=np.ones((4, 3)),
        inventory_opening=np.array([[5.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.zeros((4, 2)),
        handling_capacity=np.full((4, 2), 1000.0),
        edge_good=np.array([0], dtype=np.int64),
        demand_id=("A-freight",),
        demand_buyer=np.array([0], dtype=np.int64),
        demand_good=np.array([2], dtype=np.int64),
        demand_final=np.array([True]),
        demand_ordered=np.full((4, 1), 5.0),
        demand_gross=np.full((4, 1), 5.0),
        recipe_id=("heat", "freight"),
        recipe_org=np.array([0, 0], dtype=np.int64),
        recipe_output_good=np.array([1, 2], dtype=np.int64),
        recipe_output_coeff=np.array([1.0, 1.0]),
        recipe_input_ptr=np.array([0, 1, 2], dtype=np.int64),
        recipe_input_good=np.array([0, 1], dtype=np.int64),
        recipe_input_coeff=np.array([1.0, 1.0]),
        recipe_capacity=np.array([[5.0, 5.0]] * 4),
        recipe_tier=np.array([0, 1], dtype=np.int64),
        terminal_mask=(True, False, False, False),
        service_split=(0.0, 0.0, 1.0),
        required_reports=(),
    )
    plan = plan_quarter(_inputs(declarations), mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert plan.quarterly[0].shortfall[0] == pytest.approx(0.0, abs=1e-6)
    assert plan.quarterly[0].service_produced_by_good[0, 2] >= 5.0 - 1e-6


def test_conflicting_published_prices_are_rejected() -> None:
    declarations = _declarations(inventory_opening=np.array([[10.0], [0.0]]))
    observations = (
        PlanningObservation(
            "ORG-ENT-B",
            "energy",
            "standard",
            _procurement_observation("ORG-ENT-B", price=100.0),
        ),
        PlanningObservation(
            "ORG-ENT-A",
            "energy",
            "standard",
            _procurement_observation("ORG-ENT-A", price=1.0),
        ),
    )
    with pytest.raises(ResearchGateError, match="conflicting published prices"):
        _inputs(declarations, observations=observations)


def test_reserved_validation_window_must_be_terminal_masked() -> None:
    declarations = _declarations(
        quarters=("1985Q4", "1986Q1", "1986Q2", "1986Q3"),
        terminal_mask=(True, True, True, True),
        inventory_opening=np.zeros((2, 1)),
        required_reports=(),
    )
    with pytest.raises(ResearchGateError, match="historical core"):
        build_planning_inputs(
            observations=(),
            declarations=declarations,
            decision_at=date(1985, 10, 15),
            quarter="1985Q4",
            budget_observations=(),
        )
    masked = dataclasses.replace(declarations, terminal_mask=(True, False, False, False))
    quarter = "1985Q4"
    observations = tuple(
        PlanningObservation(
            item.organization_id,
            item.commodity_id,
            item.stage,
            _procurement_observation(
                item.organization_id,
                quarter=quarter,
                decision_at=date(1985, 10, 15),
                available_at=date(1985, 10, 10),
            ),
        )
        for item in _default_observations(masked)
    )
    budgets = (
        _budget_observation(
            "ORG-ENT-A",
            1000.0,
            payer_id=0,
            quarter=quarter,
            decision_at=date(1985, 10, 15),
            available_at=date(1985, 10, 10),
        ),
        _budget_observation(
            "ORG-ENT-B",
            1000.0,
            payer_id=1,
            quarter=quarter,
            decision_at=date(1985, 10, 15),
            available_at=date(1985, 10, 10),
        ),
    )
    inputs = build_planning_inputs(
        observations=observations,
        declarations=masked,
        decision_at=date(1985, 10, 15),
        quarter=quarter,
        budget_observations=budgets,
    )
    assert inputs.terminal_mask == (True, False, False, False)


def test_rule_certificate_and_payload_mutation_are_rejected() -> None:
    fixture, plan, observations, budgets, inputs = _execution_case("historical_rule_based")
    certificate = dataclasses.replace(
        plan.certificates[0],
        solver_status=123,
        solver_feasible=False,
        row_activity=np.full_like(plan.certificates[0].row_activity, 999.0),
    )
    mutated = dataclasses.replace(plan, certificates=(certificate,), plan_hash="")
    with pytest.raises(ResearchGateError, match="certificate"):
        execute_rolling_proposal(
            mutated,
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            calendar=_calendar("ORG-ENT-A", "ORG-ENT-B"),
            session=_session(fixture.state),
            observations=observations,
            budget_observations=budgets,
            inputs=inputs,
            organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
        )
    decision = plan.first_quarter_decisions[0].model_copy(update={"requested_quantity": 100.0})
    forged = dataclasses.replace(
        plan,
        first_quarter_decisions=(decision,),
        first_quarter_payload_hash=_payload_hash((decision,)),
        plan_hash="",
    )
    with pytest.raises(ResearchGateError, match="certificate|forecast"):
        execute_rolling_proposal(
            forged,
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            calendar=_calendar("ORG-ENT-A", "ORG-ENT-B"),
            session=_session(fixture.state),
            observations=observations,
            budget_observations=budgets,
            inputs=inputs,
            organization_index={"ORG-ENT-A": 3, "ORG-ENT-B": 1},
        )


def test_service_tier_balance_has_no_double_counted_loss() -> None:
    declarations = _declarations(
        goods_id=("fuel|standard", "heat|service", "freight|service"),
        goods_is_service=np.array([False, True, True]),
        prices=np.ones((4, 3)),
        inventory_opening=np.array([[5.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.zeros((4, 2)),
        handling_capacity=np.full((4, 2), 1000.0),
        edge_good=np.array([0], dtype=np.int64),
        demand_id=("A-freight",),
        demand_buyer=np.array([0], dtype=np.int64),
        demand_good=np.array([2], dtype=np.int64),
        demand_final=np.array([True]),
        demand_ordered=np.full((4, 1), 5.0),
        demand_gross=np.full((4, 1), 5.0),
        recipe_id=("heat", "freight"),
        recipe_org=np.array([0, 0], dtype=np.int64),
        recipe_output_good=np.array([1, 2], dtype=np.int64),
        recipe_output_coeff=np.array([1.0, 1.0]),
        recipe_input_ptr=np.array([0, 1, 2], dtype=np.int64),
        recipe_input_good=np.array([0, 1], dtype=np.int64),
        recipe_input_coeff=np.array([1.0, 1.0]),
        recipe_capacity=np.array([[5.0, 5.0]] * 4),
        recipe_tier=np.array([0, 1], dtype=np.int64),
        terminal_mask=(True, False, False, False),
        service_split=(0.0, 0.0, 1.0),
        required_reports=(),
    )
    plan = plan_quarter(_inputs(declarations), mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert plan.quarterly[0].service_lost_by_good[0, 1] == pytest.approx(0.0, abs=1e-6)


def test_rule_expires_service_inventory_each_quarter() -> None:
    declarations = _declarations(
        goods_id=("energy|standard", "heat|service"),
        goods_is_service=np.array([False, True]),
        prices=np.ones((4, 2)),
        inventory_opening=np.array([[0.0, 5.0], [0.0, 0.0]]),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.zeros((4, 2)),
        handling_capacity=np.full((4, 2), 1000.0),
        demand_id=("A-energy",),
        demand_buyer=np.array([0], dtype=np.int64),
        demand_good=np.array([0], dtype=np.int64),
        demand_final=np.array([True]),
        demand_ordered=np.zeros((4, 1)),
        demand_gross=np.zeros((4, 1)),
        recipe_id=(),
        recipe_org=np.zeros(0, dtype=np.int64),
        recipe_output_good=np.zeros(0, dtype=np.int64),
        recipe_output_coeff=np.zeros(0),
        recipe_input_ptr=np.array([0], dtype=np.int64),
        recipe_input_good=np.zeros(0, dtype=np.int64),
        recipe_input_coeff=np.zeros(0),
        recipe_capacity=np.zeros((4, 0)),
        required_reports=(),
    )
    rule = plan_quarter(_inputs(declarations), mode="historical_rule_based", time_limit_s=10)
    assert rule.status == "FEASIBLE"
    assert [float(q.inventory[0, 1]) for q in rule.quarterly] == [0.0] * 4
    assert rule.quarterly[0].service_lost[0] >= 5.0 - 1e-9


def test_productive_service_input_is_in_physical_balance() -> None:
    declarations = _declarations(
        goods_id=("fuel|standard", "heat|service", "steel|standard"),
        goods_is_service=np.array([False, True, False]),
        prices=np.ones((4, 3)),
        inventory_opening=np.array([[5.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.zeros((4, 2)),
        handling_capacity=np.full((4, 2), 1000.0),
        edge_good=np.array([0], dtype=np.int64),
        demand_id=("A-steel",),
        demand_buyer=np.array([0], dtype=np.int64),
        demand_good=np.array([2], dtype=np.int64),
        demand_final=np.array([True]),
        demand_ordered=np.full((4, 1), 5.0),
        demand_gross=np.full((4, 1), 5.0),
        recipe_id=("heat", "steel"),
        recipe_org=np.array([0, 0], dtype=np.int64),
        recipe_output_good=np.array([1, 2], dtype=np.int64),
        recipe_output_coeff=np.array([1.0, 1.0]),
        recipe_input_ptr=np.array([0, 1, 2], dtype=np.int64),
        recipe_input_good=np.array([0, 1], dtype=np.int64),
        recipe_input_coeff=np.array([1.0, 1.0]),
        recipe_capacity=np.array([[5.0, 5.0]] * 4),
        recipe_tier=np.array([0, 0], dtype=np.int64),
        terminal_mask=(True, False, False, False),
        service_split=(0.0, 1.0, 0.0),
        required_reports=(),
    )
    plan = plan_quarter(_inputs(declarations), mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert plan.quarterly[0].service_lost_by_good[0, 1] == pytest.approx(0.0, abs=1e-6)
    assert plan.quarterly[0].service_produced_by_good[0, 1] >= 5.0 - 1e-6


def test_opening_service_is_usable_in_the_current_quarter() -> None:
    declarations = _declarations(
        goods_id=("energy|standard", "heat|service"),
        goods_is_service=np.array([False, True]),
        prices=np.ones((4, 2)),
        inventory_opening=np.array([[0.0, 5.0], [0.0, 0.0]]),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.zeros((4, 2)),
        handling_capacity=np.full((4, 2), 1000.0),
        demand_id=("A-heat",),
        demand_buyer=np.array([0], dtype=np.int64),
        demand_good=np.array([1], dtype=np.int64),
        demand_final=np.array([True]),
        demand_ordered=np.full((4, 1), 5.0),
        demand_gross=np.full((4, 1), 5.0),
        recipe_id=(),
        recipe_org=np.zeros(0, dtype=np.int64),
        recipe_output_good=np.zeros(0, dtype=np.int64),
        recipe_output_coeff=np.zeros(0),
        recipe_input_ptr=np.array([0], dtype=np.int64),
        recipe_input_good=np.zeros(0, dtype=np.int64),
        recipe_input_coeff=np.zeros(0),
        recipe_capacity=np.zeros((4, 0)),
        terminal_mask=(True, False, False, False),
        service_split=(0.0, 0.0, 1.0),
        required_reports=(),
    )
    plan = plan_quarter(_inputs(declarations), mode="bounded_planning", time_limit_s=10)
    assert plan.status == "FEASIBLE"
    assert plan.quarterly[0].shortfall[0] == pytest.approx(0.0, abs=1e-6)
    assert plan.quarterly[0].service_lost_by_good[0, 1] == pytest.approx(0.0, abs=1e-6)


def _opening_service_declarations() -> PlanningDeclarations:
    return _declarations(
        goods_id=("energy|standard", "heat|service"),
        goods_is_service=np.array([False, True]),
        prices=np.ones((4, 2)),
        inventory_opening=np.array([[0.0, 10.0], [0.0, 0.0]]),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.zeros((4, 2)),
        handling_capacity=np.full((4, 2), 1000.0),
        demand_id=("A-heat",),
        demand_buyer=np.array([0], dtype=np.int64),
        demand_good=np.array([1], dtype=np.int64),
        demand_final=np.array([True]),
        demand_ordered=np.full((4, 1), 5.0),
        demand_gross=np.full((4, 1), 5.0),
        recipe_id=(),
        recipe_org=np.zeros(0, dtype=np.int64),
        recipe_output_good=np.zeros(0, dtype=np.int64),
        recipe_output_coeff=np.zeros(0),
        recipe_input_ptr=np.array([0], dtype=np.int64),
        recipe_input_good=np.zeros(0, dtype=np.int64),
        recipe_input_coeff=np.zeros(0),
        recipe_capacity=np.zeros((4, 0)),
        terminal_mask=(True, False, False, False),
        service_split=(0.5, 0.0, 0.5),
        required_reports=(),
    )


def test_mixed_service_reservation_matches_rule_and_lp() -> None:
    inputs = _inputs(_opening_service_declarations())
    lp = plan_quarter(inputs, mode="bounded_planning", time_limit_s=10)
    rule = plan_quarter(inputs, mode="historical_rule_based", time_limit_s=10)
    assert lp.status == "FEASIBLE"
    assert rule.status == "FEASIBLE"
    assert lp.quarterly[0].shortfall[0] == pytest.approx(0.0, abs=1e-6)
    assert rule.quarterly[0].shortfall[0] == pytest.approx(0.0, abs=1e-6)
    assert lp.quarterly[0].service_lost[0] == pytest.approx(5.0, abs=1e-6)
    assert rule.quarterly[0].service_lost[0] == pytest.approx(5.0, abs=1e-6)


def test_f2_second_tick_counterparty_reconciliation() -> None:
    from pathlib import Path

    from hsm_lab.contract.guards import load_research_contract, load_scenario
    from hsm_lab.data.registry import DataRegistry
    from hsm_lab.engine.initial import build_material_initial_conditions
    from hsm_lab.engine.material import load_material_forcing, tick_material
    from hsm_lab.engine.network import build_material_network
    from hsm_lab.engine.rng import RngRegistry
    from hsm_lab.engine.state import capture_material_stocks, initialize_material
    from hsm_lab.measurement.plan_execution import (
        _decode_journal,
        _non_org_payment_residual,
        _organization_payment_rows,
    )

    root = Path(__file__).resolve().parents[1]
    spec = load_scenario(root, "historical_f2_replay")
    contract = load_research_contract(root)
    initial = build_material_initial_conditions(spec, RngRegistry(spec.seed))
    network = build_material_network(spec, contract, initial)
    state = initialize_material(spec, initial, network)
    registry = DataRegistry.load(root, allowed_commodities=spec.commodities)
    forcing = load_material_forcing(spec, registry)
    for _ in range(2):
        capture_material_stocks(state)
        trace: dict = {}
        flows = tick_material(
            state,
            forcing,
            spec.material_parameters,
            network,
            routing_trace=trace,
        )
        state.completed_ticks += 1
    boundary = trace["boundary"]
    journal = _decode_journal(state, flows)
    _rows, residual = _organization_payment_rows(state, flows, network, boundary, journal)
    residual = max(
        residual,
        _non_org_payment_residual(state, flows, network, boundary, journal),
    )
    assert residual <= 1e-9


def test_same_tier_service_cycle_is_not_borrowed() -> None:
    declarations = _declarations(
        goods_id=("heat|service", "freight|service"),
        goods_is_service=np.array([True, True]),
        prices=np.ones((4, 2)),
        inventory_opening=np.array([[0.0, 0.0], [0.0, 0.0]]),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.zeros((4, 2)),
        handling_capacity=np.full((4, 2), 1000.0),
        edge_good=np.array([0], dtype=np.int64),
        demand_id=("A-freight",),
        demand_buyer=np.array([0], dtype=np.int64),
        demand_good=np.array([1], dtype=np.int64),
        demand_final=np.array([True]),
        demand_ordered=np.full((4, 1), 5.0),
        demand_gross=np.full((4, 1), 5.0),
        recipe_id=("freight", "heat"),
        recipe_org=np.array([0, 0], dtype=np.int64),
        recipe_output_good=np.array([1, 0], dtype=np.int64),
        recipe_output_coeff=np.array([1.0, 1.0]),
        recipe_input_ptr=np.array([0, 1, 2], dtype=np.int64),
        recipe_input_good=np.array([0, 1], dtype=np.int64),
        recipe_input_coeff=np.array([1.0, 1.0]),
        recipe_capacity=np.array([[5.0, 5.0]] * 4),
        recipe_tier=np.array([0, 0], dtype=np.int64),
        terminal_mask=(True, False, False, False),
        service_split=(0.0, 0.0, 1.0),
        required_reports=(),
    )
    inputs = _inputs(
        declarations,
        observations=(
            PlanningObservation(
                "ORG-ENT-A",
                "heat",
                "service",
                _procurement_observation("ORG-ENT-A", supply=5.0, demand=0.0),
            ),
            PlanningObservation(
                "ORG-ENT-B",
                "freight",
                "service",
                _procurement_observation("ORG-ENT-B", supply=0.0, demand=5.0),
            ),
        ),
    )
    lp = plan_quarter(inputs, mode="bounded_planning", time_limit_s=10)
    rule = plan_quarter(inputs, mode="historical_rule_based", time_limit_s=10)
    assert lp.status == "FEASIBLE" and rule.status == "FEASIBLE"
    assert lp.quarterly[0].shortfall[0] == pytest.approx(5.0, abs=1e-6)
    assert rule.quarterly[0].shortfall[0] == pytest.approx(5.0, abs=1e-6)


def test_opening_service_can_feed_a_service_recipe() -> None:
    declarations = _declarations(
        goods_id=("heat|service", "freight|service"),
        goods_is_service=np.array([True, True]),
        prices=np.ones((4, 2)),
        inventory_opening=np.array([[5.0, 0.0], [0.0, 0.0]]),
        funding_capacity=np.full((4, 2), 1000.0),
        service_capacity=np.zeros((4, 2)),
        handling_capacity=np.full((4, 2), 1000.0),
        edge_good=np.array([0], dtype=np.int64),
        demand_id=("A-freight",),
        demand_buyer=np.array([0], dtype=np.int64),
        demand_good=np.array([1], dtype=np.int64),
        demand_final=np.array([True]),
        demand_ordered=np.full((4, 1), 5.0),
        demand_gross=np.full((4, 1), 5.0),
        recipe_id=("freight",),
        recipe_org=np.array([0], dtype=np.int64),
        recipe_output_good=np.array([1], dtype=np.int64),
        recipe_output_coeff=np.array([1.0]),
        recipe_input_ptr=np.array([0, 1], dtype=np.int64),
        recipe_input_good=np.array([0], dtype=np.int64),
        recipe_input_coeff=np.array([1.0]),
        recipe_capacity=np.full((4, 1), 5.0),
        recipe_tier=np.array([1], dtype=np.int64),
        terminal_mask=(True, False, False, False),
        service_split=(0.0, 0.0, 1.0),
        required_reports=(),
    )
    plan = plan_quarter(_inputs(declarations), mode="bounded_planning", time_limit_s=10)
    rule = plan_quarter(_inputs(declarations), mode="historical_rule_based", time_limit_s=10)
    assert plan.status == "FEASIBLE" and rule.status == "FEASIBLE"
    assert plan.quarterly[0].shortfall[0] == pytest.approx(0.0, abs=1e-6)
    assert rule.quarterly[0].shortfall[0] == pytest.approx(0.0, abs=1e-6)
