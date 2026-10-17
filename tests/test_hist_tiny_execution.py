"""H2B acceptance tests: validated decision → TickControls → material kernel.

The tests use the tiny material fixture from ``test_material`` and assert the
control bridge, one-quarter admission lifecycle, kernel delivery/payment, and
state/clock isolation on rejection.
"""

from __future__ import annotations

from datetime import date
from importlib import util
from pathlib import Path

import numpy as np
import pytest

from hsm_lab.contract.schemas import Quarter
from hsm_lab.institutions.decisions import (
    ActorRole,
    ProcurementChoiceKind,
    ProcurementDecision,
)
from hsm_lab.institutions.execution_adapter import commit_proposal
from hsm_lab.institutions.proposal_validation import (
    ValidationResult,
    validate_proposal,
)
from hsm_lab.institutions.schemas import (
    AuthorityScope,
    DateInterval,
    InstitutionEvent,
    RegimeCalendar,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = util.spec_from_file_location(
    "test_material_module", REPO_ROOT / "tests" / "test_material.py"
)
_test_mat = util.module_from_spec(_spec)
_spec.loader.exec_module(_test_mat)


def make_tiny(
    *,
    hub_cash: float = 1_000_000.0,
    transport: float = 100.0,
    transport_per_unit: float = 0.0,
):
    hub = _test_mat.hub(3, handling=1_000_000.0).model_copy(
        update={"initial_cash": hub_cash}
    )
    return _test_mat.Fixture(
        orgs=[
            _test_mat.bank(0),
            _test_mat.producer(1, "tech_energy", capacity=100.0, cash=1_000_000.0),
            _test_mat.producer(2, "tech_capital", capacity=100.0, cash=1_000_000.0),
            hub,
            _test_mat.retail(4, handling=1_000_000.0),
            _test_mat.transport(5, capacity=transport),
        ],
        technologies=[
            _test_mat.tech("tech_energy", outputs=(("energy", "standard", 1.0),)),
            _test_mat.tech(
                "tech_capital", outputs=(("capital_goods", "standard", 1.0),)
            ),
            _test_mat.tech(
                "freight_transport",
                outputs=(("services_transport", "standard", 1.0),),
            ),
        ],
        commodities=_test_mat.TINY_COMMODITIES,
        region_ids=("R0",),
        parameters=_test_mat.default_params(
            desired_per_person=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            wage_rate=100.0,
            transport_per_unit=transport_per_unit,
        ),
        households=[(0, 3.0, 1.0)] * 5,
        household_cash=0.0,
        ticks=4,
    )


def make_two_region(
    *,
    desired_per_person: list[float] | None = None,
    prices: list[float] | None = None,
    food_raw_price: float = 1.0,
) -> _test_mat.Fixture:
    return _test_mat.Fixture(
        orgs=[
            _test_mat.bank(0),
            _test_mat.producer(1, "tech_energy", capacity=100.0, cash=1_000_000.0),
            _test_mat.producer(2, "tech_capital", capacity=100.0, cash=1_000_000.0),
            _test_mat.hub(3, handling=1_000_000.0),
            _test_mat.retail(4, handling=1_000_000.0),
            _test_mat.transport(5, capacity=100.0),
            _test_mat.producer(
                6,
                "tech_food",
                capacity=100.0,
                cash=1_000_000.0,
                region="R1",
            ),
        ],
        technologies=[
            _test_mat.tech("tech_energy", outputs=(("energy", "standard", 1.0),)),
            _test_mat.tech(
                "tech_capital", outputs=(("capital_goods", "standard", 1.0),)
            ),
            _test_mat.tech(
                "freight_transport",
                outputs=(("services_transport", "standard", 1.0),),
            ),
            _test_mat.tech("tech_food", outputs=(("food", "ready", 1.0),)),
        ],
        commodities=_test_mat.TINY_COMMODITIES,
        region_ids=("R0", "R1"),
        parameters=_test_mat.default_params(
            **{
                "desired_per_person": desired_per_person
                or [1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "food_raw_price": food_raw_price,
                "wage_rate": 100.0,
                **({"prices": prices} if prices is not None else {}),
            }
        ),
        households=[(0, 3.0, 1.0), (1, 3.0, 1.0)],
        household_cash=0.0,
        ticks=4,
    )


@pytest.fixture
def tiny():
    return make_tiny()


def _decision(
    *,
    decision_id: str = "proc",
    organization_id: str = "3",
    quarter: str = "1957Q1",
    quantity: float = 50.0,
    commodity_id: str = "energy",
    kind: ProcurementChoiceKind = ProcurementChoiceKind.REQUEST,
) -> ProcurementDecision:
    month = {"1957Q1": 1, "1957Q2": 4, "1957Q3": 7, "1957Q4": 10}[quarter]
    return ProcurementDecision(
        decision_id=decision_id,
        actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
        organization_id=organization_id,
        sector_id="industry",
        quarter=quarter,
        decision_at=date(1957, month, 15),
        available_at=date(1957, month, 10),
        kind=kind,
        commodity_id=commodity_id,
        requested_quantity=quantity,
    )


def _validation(decision: ProcurementDecision, *, legal: bool = True) -> ValidationResult:
    import hashlib

    digest = hashlib.sha256(
        decision.model_dump_json().encode("utf-8")
    ).hexdigest()
    return ValidationResult(
        decision_id=decision.decision_id,
        is_legal=legal,
        authority_status="granted" if legal else "revoked",
        reason="legal" if legal else "revoked",
        mode="admission",
        admission_eligible=legal,
        decision_digest=digest,
    )


def _commit(tiny, decision, *, legal: bool = True, **kwargs):
    kwargs.setdefault("organization_index", {"3": 3})
    return commit_proposal(
        decision,
        _validation(decision, legal=legal),
        tiny.state,
        tiny.forcing(4),
        tiny.parameters,
        tiny.network,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Positive admission and delivery
# ---------------------------------------------------------------------------


def test_legal_procurement_delivers_and_pays(tiny) -> None:
    decision = _decision()
    result = _commit(tiny, decision)

    assert result.is_committed, result.reason
    assert result.flows is not None
    trace = dict(result.trace)
    assert trace["tick"] == 0
    assert trace["quarter"] == "1957Q1"
    assert trace["control"] == "procurement_requests"
    assert trace["control_applied"] is True
    assert trace["delivered_quantity"] > 0.0
    assert trace["buyer_payment"] > 0.0
    assert result.flows.organization_sales_receipts[1] > 0.0
    assert trace["binding_status"] in {"satisfied", "binding"}
    assert tiny.state.completed_ticks == 1


def test_real_h2a_admission_executes_and_revoked_authority_rejects(
    tiny,
) -> None:
    from hsm_lab.contract.schemas import ScenarioSpec
    from hsm_lab.engine.political_run import PoliticalSession
    from hsm_lab.engine.state import MaterialState

    def day(year: int, month: int) -> DateInterval:
        return DateInterval(
            earliest=date(year, month, 1),
            latest=date(year, month, 1),
            precision="day",
        )
    grant = InstitutionEvent(
        event_id="GRANT-PROC",
        permission="procurement",
        scope=AuthorityScope(
            organization_ids=("ORG-ENT-A",),
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
        source_ids=("synthetic:h2b-test",),
        synthetic_flag=True,
        confidence_reason="synthetic test",
        search_tags=(),
    )
    calendar = RegimeCalendar(events=(grant,))
    session_state = object.__new__(MaterialState)
    object.__setattr__(session_state, "completed_ticks", 0)
    session_spec = ScenarioSpec.model_construct(
        start=Quarter.parse("1957Q1")
    )
    session = object.__new__(PoliticalSession)
    object.__setattr__(session, "state", session_state)
    object.__setattr__(session, "spec", session_spec)
    object.__setattr__(session, "target_ticks", 4)
    object.__setattr__(session, "opened", True)
    object.__setattr__(session, "finished", False)

    decision = _decision(organization_id="ORG-ENT-A")
    validation = validate_proposal(decision, calendar, session=session)
    assert validation.is_legal and validation.admission_eligible

    result = commit_proposal(
        decision,
        validation,
        tiny.state,
        tiny.forcing(4),
        tiny.parameters,
        tiny.network,
        organization_index={"ORG-ENT-A": 3},
    )
    assert result.is_committed
    assert tiny.state.completed_ticks == 1

    # An organization without the grant is rejected before execution.
    revoked = _decision(
        decision_id="revoked",
        organization_id="ORG-ENT-B",
        quarter="1957Q1",
    )
    revoked_validation = validate_proposal(revoked, calendar, session=session)
    assert not revoked_validation.is_legal
    before_clock = tiny.state.completed_ticks
    before_stock = tiny.state.stock_value.copy()
    rejected = commit_proposal(
        revoked,
        revoked_validation,
        tiny.state,
        tiny.forcing(4),
        tiny.parameters,
        tiny.network,
        organization_index={"ORG-ENT-B": 3},
    )
    assert not rejected.is_committed
    assert tiny.state.completed_ticks == before_clock
    assert np.array_equal(tiny.state.stock_value, before_stock)


def test_cancel_is_a_nonbinding_control(tiny) -> None:
    decision = _decision(
        decision_id="cancel",
        kind=ProcurementChoiceKind.CANCEL,
        quantity=0.0,
    )
    result = _commit(tiny, decision)
    assert result.is_committed
    assert dict(result.trace)["binding_status"] == "nonbinding"
    assert tiny.state.completed_ticks == 1


# ---------------------------------------------------------------------------
# Rejection isolation
# ---------------------------------------------------------------------------


def test_illegal_decision_does_not_touch_state(tiny) -> None:
    decision = _decision(quantity=-10.0)
    before_stock = tiny.state.stock_value.copy()
    before_cash = tiny.state.organization_cash.copy()
    before_clock = tiny.state.completed_ticks

    result = _commit(tiny, decision, legal=False)

    assert not result.is_committed
    assert np.array_equal(tiny.state.stock_value, before_stock)
    assert np.array_equal(tiny.state.organization_cash, before_cash)
    assert tiny.state.completed_ticks == before_clock


def test_quarter_mismatch_is_rejected_without_advancing(tiny) -> None:
    decision = _decision(quarter="1957Q2")
    before_clock = tiny.state.completed_ticks

    result = _commit(tiny, decision)

    assert not result.is_committed
    assert "kernel quarter" in result.reason
    assert tiny.state.completed_ticks == before_clock


def test_unmapped_institutional_identity_is_rejected(tiny) -> None:
    decision = _decision(organization_id="ORG-ENT-A")

    result = _commit(tiny, decision)
    assert not result.is_committed
    assert "crosswalk" in result.reason
    assert tiny.state.completed_ticks == 0

    result = _commit(
        tiny,
        decision,
        organization_index={"ORG-ENT-A": 3},
    )
    assert result.is_committed
    assert tiny.state.completed_ticks == 1


def test_unknown_commodity_is_rejected(tiny) -> None:
    decision = _decision(commodity_id="unobtainium")
    result = _commit(tiny, decision)
    assert not result.is_committed
    assert "commodity" in result.reason
    assert tiny.state.completed_ticks == 0


# ---------------------------------------------------------------------------
# Clock lifecycle
# ---------------------------------------------------------------------------


def test_two_quarters_then_failure_advances_once_per_quarter(tiny) -> None:
    first = _commit(tiny, _decision(decision_id="q1", quarter="1957Q1"))
    assert first.is_committed
    assert tiny.state.completed_ticks == 1

    second = _commit(tiny, _decision(decision_id="q2", quarter="1957Q2"))
    assert second.is_committed
    assert tiny.state.completed_ticks == 2

    failed = _commit(
        tiny,
        _decision(decision_id="q2-replay", quarter="1957Q2"),
    )
    assert not failed.is_committed
    assert tiny.state.completed_ticks == 2


def test_zero_buyer_cash_does_not_overdraw(tiny) -> None:
    tiny = make_tiny(hub_cash=0.0)
    result = _commit(tiny, _decision())

    assert result.is_committed
    assert tiny.state.organization_cash[3] >= -1e-9


# ---------------------------------------------------------------------------
# Existing TickControls preservation and central planning
# ---------------------------------------------------------------------------


def test_existing_controls_are_preserved(tiny) -> None:
    from hsm_lab.engine.policy import TickControls

    target = np.zeros(4, dtype=np.float64)
    target[0] = 7.0
    controls = TickControls(
        material_parameters=tiny.parameters,
        household_parameters=tiny.network.household_parameters,
        household_catalog=tiny.network.household_catalog,
        autonomy=0.25,
        central_target=target,
        policy=None,
        procurement_requests=None,
    )
    result = _commit(tiny, _decision(), controls=controls)
    trace = dict(result.trace)
    assert result.is_committed
    assert trace["autonomy"] == pytest.approx(0.25)
    assert trace["central_target_preserved"] is True


def test_retrospective_validation_cannot_execute(tiny) -> None:
    decision = _decision()
    result = commit_proposal(
        decision,
        ValidationResult(
            decision_id=decision.decision_id,
            is_legal=True,
            authority_status="granted",
            reason="calendar-only",
            mode="retrospective",
            admission_eligible=False,
            decision_digest=__import__("hashlib").sha256(
                decision.model_dump_json().encode("utf-8")
            ).hexdigest(),
        ),
        tiny.state,
        tiny.forcing(4),
        tiny.parameters,
        tiny.network,
        organization_index={"3": 3},
    )
    assert not result.is_committed
    assert "admission-eligible" in result.reason
    assert tiny.state.completed_ticks == 0


def test_malformed_decision_id_rejected_without_callbacks(tiny) -> None:
    calls: list[str] = []

    class HostileStr(str):
        def __ne__(self, other: object) -> bool:
            calls.append("__ne__")
            return False

    original = _decision()
    forged = original.model_copy(
        update={"decision_id": HostileStr(original.decision_id)}
    )
    before_stock = tiny.state.stock_value.copy()
    before_clock = tiny.state.completed_ticks
    result = commit_proposal(
        forged,
        _validation(original),
        tiny.state,
        tiny.forcing(4),
        tiny.parameters,
        tiny.network,
        organization_index={"3": 3},
    )
    assert not result.is_committed
    assert "malformed" in result.reason
    assert calls == []
    assert np.array_equal(tiny.state.stock_value, before_stock)
    assert tiny.state.completed_ticks == before_clock


def test_payload_substitution_is_rejected(tiny) -> None:
    original = _decision(quantity=50.0)
    validation = _validation(original)
    substituted = _decision(quantity=99.0)
    result = commit_proposal(
        substituted,
        validation,
        tiny.state,
        tiny.forcing(4),
        tiny.parameters,
        tiny.network,
        organization_index={"3": 3},
    )
    assert not result.is_committed
    assert "payload" in result.reason
    assert tiny.state.completed_ticks == 0


def test_invariant_failure_rolls_back_state(tiny, monkeypatch) -> None:
    before_stock = tiny.state.stock_value.copy()
    before_cash = tiny.state.organization_cash.copy()
    before_clock = tiny.state.completed_ticks

    def fail(*args, **kwargs):
        raise RuntimeError("invariant gate failure")

    monkeypatch.setattr(
        "hsm_lab.engine.accounting.check_material_invariants", fail
    )
    result = _commit(tiny, _decision())

    assert not result.is_committed
    assert np.array_equal(tiny.state.stock_value, before_stock)
    assert np.array_equal(tiny.state.organization_cash, before_cash)
    assert tiny.state.completed_ticks == before_clock


def test_wrong_destination_organization_is_rejected(tiny) -> None:
    decision = _decision(organization_id="1")
    result = _commit(
        tiny, decision, organization_index={"1": 1}
    )
    assert not result.is_committed
    assert "no procurement destination" in result.reason
    assert tiny.state.completed_ticks == 0


def test_two_regions_two_commodities_two_quarters() -> None:
    """The minimal bridge covers 2 regions × 2 commodities × 2 quarters."""
    tiny = make_two_region()

    first = _commit(
        tiny, _decision(decision_id="energy-q1", quarter="1957Q1")
    )
    assert first.is_committed
    assert dict(first.trace)["delivered_quantity"] > 0.0
    assert tiny.state.completed_ticks == 1

    second = _commit(
        tiny,
        _decision(
            decision_id="food-q2",
            quarter="1957Q2",
            commodity_id="food",
        ),
    )
    assert second.is_committed
    assert dict(second.trace)["delivered_quantity"] > 0.0
    assert tiny.state.completed_ticks == 2
    assert len(set(tiny.network.region_ids)) == 2
    source_region = np.asarray(
        tiny.network.cell_region[tiny.network.edge_source_cell]
    )
    edge_delivered = np.asarray(second.flows.edge_delivered)
    assert np.any((source_region == 1) & (edge_delivered > 0.0))


def test_procurement_order_targets_only_the_consumable_stage() -> None:
    import copy

    from hsm_lab.engine.material import tick_material

    tiny = make_two_region(
        desired_per_person=[1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    )
    result = _commit(
        tiny,
        _decision(
            decision_id="food-full",
            quarter="1957Q1",
            commodity_id="food",
            quantity=100.0,
        ),
    )
    assert result.is_committed
    network = tiny.network
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    stage = np.asarray(network.cell_stage, dtype=np.int64)[demand_cell]
    base_mask = (
        (purpose == 3)
        & (commodity[demand_cell] == 2)  # food
        & (owner_kind[demand_cell] == 0)
        & (owner_id[demand_cell] == 3)
    )
    raw_mask = base_mask & (stage == 1)
    ready_mask = base_mask & (stage == 2)

    baseline = copy.deepcopy(tiny.state)
    base_flows = tick_material(
        baseline,
        tiny.forcing(4),
        tiny.parameters,
        tiny.network,
        controls=None,
    )
    # The raw channel receives no part of the admitted order.
    assert np.allclose(
        result.flows.desired[raw_mask], base_flows.desired[raw_mask]
    )
    assert np.allclose(result.flows.delivered[raw_mask], 0.0)
    # The consumable channel receives it in full.
    assert np.all(
        result.flows.desired[ready_mask] > base_flows.desired[ready_mask]
    )


def test_unmatched_procurement_request_fails_loudly() -> None:
    from hsm_lab.engine.material import tick_material
    from hsm_lab.engine.policy import TickControls

    tiny = make_tiny()
    controls = TickControls(
        material_parameters=tiny.parameters,
        household_parameters=tiny.network.household_parameters,
        household_catalog=tiny.network.household_catalog,
        autonomy=0.0,
        central_target=None,
        policy=None,
        procurement_requests=((99, 0, 10.0),),
    )
    with pytest.raises(ValueError, match="no owner-matched procurement"):
        tick_material(
            tiny.state,
            tiny.forcing(4),
            tiny.parameters,
            tiny.network,
            controls=controls,
        )


def test_food_stage_payment_reconciles_with_settlement_edges() -> None:
    """Buyer goods payment prices each delivered stage, not one blended sum."""
    from hsm_lab.engine.material import build_material_prices

    tiny = make_two_region(
        desired_per_person=[1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        prices=[1.0, 1.0, 5.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        food_raw_price=0.25,
    )
    result = _commit(
        tiny,
        _decision(
            decision_id="food-stage",
            quarter="1957Q1",
            commodity_id="food",
        ),
    )
    assert result.is_committed
    network = tiny.network
    prices = build_material_prices(tiny.parameters)
    expected = 0.0
    for edge in range(len(network.edge_id)):
        if (
            network.edge_purpose[edge] == 3  # procurement
            and network.edge_commodity[edge] == 2  # food
            and network.edge_buyer_org[edge] == 3
        ):
            stage = int(network.edge_stage[edge])
            expected += float(result.flows.edge_delivered[edge]) * prices.price_for(
                2, stage
            )
    assert expected > 0.0
    assert dict(result.trace)["buyer_payment"] == pytest.approx(expected)


def test_central_target_binds_only_at_zero_autonomy() -> None:
    from hsm_lab.engine.material import tick_material
    from hsm_lab.engine.policy import TickControls

    for autonomy, expected in ((0.0, 3.0), (1.0, 5.0)):
        tiny = make_tiny()
        activity_org = np.asarray(tiny.network.activity_org_index)
        energy_activity = int(np.flatnonzero(activity_org == 1)[0])
        target = np.zeros(len(activity_org), dtype=np.float64)
        target[energy_activity] = 3.0
        # Capacity 5 makes the local rule produce 5.
        tiny.state.organization_capacity[1] = 5.0
        controls = TickControls(
            material_parameters=tiny.parameters,
            household_parameters=tiny.network.household_parameters,
            household_catalog=tiny.network.household_catalog,
            autonomy=autonomy,
            central_target=target,
            policy=None,
            procurement_requests=None,
        )
        flows = tick_material(
            tiny.state,
            tiny.forcing(4),
            tiny.parameters,
            tiny.network,
            controls=controls,
        )
        assert flows.activity_target[energy_activity] == pytest.approx(expected)
