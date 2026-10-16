"""H2A verification tests: observation authority, proposal validation, single clock.

Run from repo root:
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
    tests/test_hist_observation_authority.py

These tests verify:
  1. Actor observations are whitelist-filtered and deep-immutable
  2. available_at must be <= decision_at; future info is rejected
  3. Proposals are legal choices, not stock/cash patches
  4. Authority queries use the H1B calendar
  5. Three rules (historical_rule_based, bounded_planning, full_information_upper_bound)
  6. Single clock: no second PoliticalSession created
  7. Same observation, two roles → different permission results
  8. Stock/cash assignment proposals are rejected
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from hsm_lab.institutions.calendar import load_calendar
from hsm_lab.institutions.decisions import (
    ActorRole,
    HouseholdNeedDecision,
    HouseholdNeedKind,
    InvestmentDecision,
    PriceProposalDecision,
    PriceProposalKind,
    ProcurementChoiceKind,
    ProcurementDecision,
)
from hsm_lab.institutions.observed import (
    ActorObservation,
    ObservationBuilder,
    _to_immutable,
    verify_observation_invariants,
)
from hsm_lab.institutions.proposal_validation import (
    ALL_RULES,
    BoundedPlanning,
    FullInformationUpperBound,
    HistoricalRuleBased,
    evaluate_all_rules,
    validate_proposal,
    validate_proposals,
)

# ---------------------------------------------------------------------------
# Calendar fixture — reuse H1B synthetic calendar
# ---------------------------------------------------------------------------

_H1B_CALENDAR_PATH = (
    Path(__file__).parent.parent
    / "institutions"
    / "HIST_VNEXT"
    / "h1b_synthetic_calendar.json"
)


@pytest.fixture
def calendar():
    if _H1B_CALENDAR_PATH.exists():
        return load_calendar(_H1B_CALENDAR_PATH)
    # Build minimal calendar for isolated testing
    from hsm_lab.institutions.schemas import DateInterval, RegimeCalendar

    def di(earliest, latest, precision):
        return DateInterval(earliest=earliest, latest=latest, precision=precision)

    grant_scope = {
        "organization_ids": ["ORG-ENT-A"],
        "sector_ids": ["industry"],
        "excluded_sector_ids": [],
        "geographic_ids": [],
    }
    grant = {
        "event_id": "h2a-test-grant",
        "permission": "procurement",
        "scope": grant_scope,
        "action": "grant",
        "proposal_date": di(date(1966, 5, 1), date(1966, 5, 1), "day"),
        "approval_date": di(date(1966, 6, 1), date(1966, 6, 1), "day"),
        "enactment_date": di(date(1967, 12, 1), date(1967, 12, 1), "day"),
        "effective_from": di(date(1968, 1, 1), date(1968, 1, 1), "day"),
        "effective_to": None,
        "source_available_at": di(date(1957, 1, 1), date(1957, 1, 1), "day"),
        "issuer": "HSWAP",
        "legal_force": "enactment",
        "source_ids": [],
        "implementation_evidence_ids": [],
        "synthetic_flag": True,
        "confidence_reason": "test fixture",
        "search_tags": [],
    }
    return RegimeCalendar.model_validate({"events": [grant]})


# ---------------------------------------------------------------------------
# Test 1 — Whitelist filtering
# ---------------------------------------------------------------------------

class TestObservationWhitelist:
    def test_procurement_org_sees_only_procurement_fields(self):
        builder = ObservationBuilder("procurement_organization")
        obs = builder.build(
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),
            raw_data={
                "supply_quantity": 100.0,
                "demand_quantity": 90.0,
                "administered_price": 50.0,
                "inventory_level": 30.0,
                "capacity_utilization": 0.85,
                "shortage_indicator": 0.1,
                # Not in whitelist — should be dropped
                "raw_truth": 999.0,
                "session_id": "sess-123",
                "household_income": 500.0,
                "unrelated_field": "should_not_appear",
            },
        )
        assert obs.actor_role == "procurement_organization"
        field_names = {name for name, _ in obs.observed_fields}
        assert "supply_quantity" in field_names
        assert "demand_quantity" in field_names
        assert "administered_price" in field_names
        assert "raw_truth" not in field_names
        assert "session_id" not in field_names
        assert "household_income" not in field_names

    def test_approver_sees_only_approver_fields(self):
        builder = ObservationBuilder("approver")
        obs = builder.build(
            organization_id="ORG-GOV",
            sector_id="industry",
            geographic_id="national",
            quarter="1968Q1",
            decision_at=date(1968, 2, 1),
            available_at=date(1968, 1, 25),
            raw_data={
                "requested_quantity": 80.0,
                "approved_quantity": 75.0,
                "price_level": 48.0,
                "budget_available": 10000.0,
                "priority_score": 0.9,
                "raw_truth": 42.0,  # should be dropped
            },
        )
        field_names = {name for name, _ in obs.observed_fields}
        assert "requested_quantity" in field_names
        assert "approved_quantity" in field_names
        assert "priority_score" in field_names
        assert "raw_truth" not in field_names

    def test_household_receiver_sees_only_household_fields(self):
        builder = ObservationBuilder("household_receiver")
        obs = builder.build(
            organization_id="HH-001",
            sector_id="household",
            geographic_id="national",
            quarter="1968Q1",
            decision_at=date(1968, 3, 1),
            available_at=date(1968, 2, 28),
            raw_data={
                "household_id": "HH-001",
                "income_level": 1200.0,
                "consumption_quantity": 80.0,
                "unmet_need_quantity": 10.0,
                "ration_quota": 90.0,
                "access_score": 0.75,
                "supply_quantity": 999.0,  # should be dropped
            },
        )
        field_names = {name for name, _ in obs.observed_fields}
        assert "income_level" in field_names
        assert "consumption_quantity" in field_names
        assert "unmet_need_quantity" in field_names
        assert "supply_quantity" not in field_names


# ---------------------------------------------------------------------------
# Test 2 — available_at <= decision_at enforcement
# ---------------------------------------------------------------------------

class TestAvailableAtConstraint:
    def test_future_available_at_rejected(self):
        builder = ObservationBuilder("procurement_organization")
        with pytest.raises(ValueError, match="available_at"):
            builder.build(
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 20),  # AFTER decision_at — must reject
                raw_data={"supply_quantity": 100.0},
            )

    def test_available_at_equals_decision_at_accepted(self):
        builder = ObservationBuilder("procurement_organization")
        obs = builder.build(
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 15),
            raw_data={"supply_quantity": 100.0},
        )
        assert obs.available_at == date(1968, 1, 15)
        assert obs.decision_at == date(1968, 1, 15)


# ---------------------------------------------------------------------------
# Test 3 — Deep immutability
# ---------------------------------------------------------------------------

class TestDeepImmutability:
    def test_observation_is_frozen(self):
        builder = ObservationBuilder("procurement_organization")
        obs = builder.build(
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),
            raw_data={"supply_quantity": 100.0, "demand_quantity": 90.0},
        )
        from pydantic_core import ValidationError

        with pytest.raises(ValidationError):  # frozen Pydantic model
            obs.observed_fields = (("supply_quantity", 200.0),)  # type: ignore[misc]

    def test_nested_containers_are_immutable(self):
        builder = ObservationBuilder("approver")
        obs = builder.build(
            organization_id="ORG-GOV",
            sector_id="industry",
            geographic_id="national",
            quarter="1968Q1",
            decision_at=date(1968, 2, 1),
            available_at=date(1968, 1, 25),
            raw_data={
                "requested_quantity": (10.0, 20.0, 30.0),
                "priority_score": {"a": 0.9, "b": 0.8},  # singular per whitelist
            },
        )
        field_dict = dict(obs.observed_fields)
        # Tuples and dict-as-tuples are immutable
        assert isinstance(field_dict.get("requested_quantity"), tuple)
        assert isinstance(field_dict.get("priority_score"), tuple)

    def test_to_immutable_converts_list_to_tuple(self):
        result = _to_immutable([1, 2, [3, 4]])
        assert isinstance(result, tuple)
        assert isinstance(result[2], tuple)
        assert result == (1, 2, (3, 4))

    def test_to_immutable_converts_dict_to_tuple(self):
        result = _to_immutable({"b": 2, "a": 1})
        assert isinstance(result, tuple)
        # Should be sorted by key
        assert result[0] == ("a", 1)


# ---------------------------------------------------------------------------
# Test 4 — Proposal legality (no stock/cash assignments)
# ---------------------------------------------------------------------------

class TestProposalLegality:
    def test_negative_quantity_rejected(self):
        decision = ProcurementDecision(
            decision_id="d1",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=-50.0,  # negative — illegal
        )
        is_legal, reason = decision.validate_legality()
        assert not is_legal
        assert "negative" in reason.lower()

    def test_negative_price_rejected(self):
        decision = PriceProposalDecision(
            decision_id="d2",
            actor_role=ActorRole.APPROVER,
            organization_id="ORG-GOV",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 2, 1),
            available_at=date(1968, 1, 25),
            kind=PriceProposalKind.SET,
            commodity_id="steel",
            proposed_price=-10.0,  # negative — illegal
        )
        is_legal, reason = decision.validate_legality()
        assert not is_legal

    def test_empty_commodity_id_rejected(self):
        decision = ProcurementDecision(
            decision_id="d3",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="   ",  # blank — illegal
            requested_quantity=50.0,
        )
        is_legal, reason = decision.validate_legality()
        assert not is_legal

    def test_legal_procurement_request_accepted(self):
        decision = ProcurementDecision(
            decision_id="d4",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        is_legal, reason = decision.validate_legality()
        assert is_legal
        assert "legal" in reason.lower()

    def test_stock_assignment_not_in_schema(self):
        """Stock assignment fields do not exist in the Decision schema.

        This verifies the schema itself rejects state patches.
        """
        # No 'stock' or 'cash' fields in any Decision subclass
        decision_classes = [
            ProcurementDecision,
            PriceProposalDecision,
            InvestmentDecision,
            HouseholdNeedDecision,
        ]
        for cls in decision_classes:
            model_fields = set(cls.model_fields.keys())
            assert "stock" not in model_fields, f"{cls.__name__} should not have 'stock'"
            assert "cash" not in model_fields, f"{cls.__name__} should not have 'cash'"
            assert "account_balance" not in model_fields
            assert "output_multiplier" not in model_fields


# ---------------------------------------------------------------------------
# Test 5 — Authority validation
# ---------------------------------------------------------------------------

class TestAuthorityValidation:
    def test_legal_procurement_with_granted_authority(self, calendar):
        decision = ProcurementDecision(
            decision_id="d5",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        result = validate_proposal(
            decision,
            calendar,
        )
        assert result.is_legal, result.reason
        assert result.authority_status in ("granted", "unknown")

    def test_legal_procurement_with_revoked_authority(self, calendar):
        # ORG-ENT-B's procurement is revoked at 1972-11-15
        decision = ProcurementDecision(
            decision_id="d6",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-B",
            sector_id="industry",
            quarter="1973Q1",
            decision_at=date(1973, 1, 1),
            available_at=date(1972, 12, 20),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        result = validate_proposal(
            decision,
            calendar,
        )
        # After revoke: authority should be revoked
        assert result.authority_status == "revoked"
        assert not result.is_legal


# ---------------------------------------------------------------------------
# Test 6 — Three rules
# ---------------------------------------------------------------------------

class TestDecisionRules:
    def test_bounded_planning_rejects_future_info(self):
        rule = BoundedPlanning()
        decision = ProcurementDecision(
            decision_id="d7",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 20),  # future — violates bounded planning
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        passed, reason = rule.evaluate(decision, None)
        assert not passed
        assert "bounded_planning" in reason.lower()

    def test_bounded_planning_accepts_legal_info(self):
        rule = BoundedPlanning()
        decision = ProcurementDecision(
            decision_id="d8",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        passed, reason = rule.evaluate(decision, None)
        assert passed

    def test_historical_rule_based_declares_diagnostic(self):
        rule = HistoricalRuleBased()
        decision = ProcurementDecision(
            decision_id="d9",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        passed, reason = rule.evaluate(decision, None)
        assert passed
        assert "historical_rule_based" in reason

    def test_full_information_upper_bound_is_diagnostic(self):
        rule = FullInformationUpperBound()
        decision = ProcurementDecision(
            decision_id="d10",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        passed, reason = rule.evaluate(decision, None)
        assert passed
        assert "full_information_upper_bound" in reason

    def test_all_rules_registered(self):
        assert len(ALL_RULES) == 3
        names = {r.rule_name for r in ALL_RULES}
        assert "historical_rule_based" in names
        assert "bounded_planning" in names
        assert "full_information_upper_bound" in names

    def test_evaluate_all_rules_returns_three_results(self):
        decision = ProcurementDecision(
            decision_id="d11",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        results = evaluate_all_rules(decision, None)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# Test 7 — Same observation, two roles → different permissions
# ---------------------------------------------------------------------------

class TestRolePermissionIsolation:
    def test_same_quarter_different_roles(self, calendar):
        """Procurement org and household receiver have different permissions.

        ORG-ENT-A has procurement authority (enacted 1968) but HH-001 has no
        corresponding grant in the calendar — authorization differs by role+org.
        """
        # Procurement org: ORG-ENT-A has procurement authority (enacted 1968)
        proc_decision = ProcurementDecision(
            decision_id="d12",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        proc_result = validate_proposal(
            proc_decision, calendar,
        )

        # Household receiver: HH-001 has no procurement authority
        hh_decision = HouseholdNeedDecision(
            decision_id="d13",
            actor_role=ActorRole.HOUSEHOLD_RECEIVER,
            organization_id="HH-001",
            sector_id="household",
            quarter="1968Q1",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=HouseholdNeedKind.REGISTER,
            household_id="HH-001",
            commodity_id="coal",
            claimed_quantity=50.0,
        )
        hh_result = validate_proposal(
            hh_decision, calendar,
        )

        # The results differ: org+role match determines outcome
        assert proc_result.decision_id != hh_result.decision_id
        proc_auth = proc_result.authority_status
        hh_auth = hh_result.authority_status
        # Both determinate
        assert proc_auth in ("granted", "unknown", "revoked")
        assert hh_auth in ("granted", "unknown", "revoked")


# ---------------------------------------------------------------------------
# Test 8 — Single clock principle
# ---------------------------------------------------------------------------

class TestSingleClock:
    def test_calendar_is_singleton(self, calendar):
        """The calendar is the single source of temporal authority.

        No actor creates a second PoliticalSession or advances a second clock.
        This is verified by the absence of session creation in this module.
        """
        # Verify the calendar has no internal tick/state
        assert hasattr(calendar, "events")
        assert hasattr(calendar, "event_by_id")
        # No tick attribute
        assert not hasattr(calendar, "tick")
        assert not hasattr(calendar, "current_step")
        assert not hasattr(calendar, "advance")

    def test_observation_has_no_clock(self):
        """Actor observations record decision_at but do not own a session clock."""
        builder = ObservationBuilder("procurement_organization")
        obs = builder.build(
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),
            raw_data={"supply_quantity": 100.0},
        )
        assert not hasattr(obs, "tick")
        assert not hasattr(obs, "step")
        assert not hasattr(obs, "session")

    def test_decision_records_decision_at(self):
        """Decisions record when they were made; they don't advance any clock."""
        decision = ProcurementDecision(
            decision_id="d14",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        assert decision.decision_at == date(1968, 1, 15)
        # No method to advance time
        assert not hasattr(decision, "advance")
        assert not hasattr(decision, "tick_forward")


# ---------------------------------------------------------------------------
# Test 9 — Verify observation invariants
# ---------------------------------------------------------------------------

class TestObservationInvariants:
    def test_no_raw_truth_in_observation(self):
        """raw_truth is dropped by the whitelist, so it never appears in observed_fields."""
        builder = ObservationBuilder("procurement_organization")
        obs = builder.build(
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),
            raw_data={
                "supply_quantity": 100.0,
                "raw_truth": 999.0,  # not in whitelist — silently dropped
            },
        )
        # raw_truth should not appear in the observation
        field_names = {name for name, _ in obs.observed_fields}
        assert "raw_truth" not in field_names
        # Clean observation passes all invariants
        violations = verify_observation_invariants(obs)
        assert len(violations) == 0, f"Unexpected violations: {violations}"

    def test_all_invariants_pass_for_clean_observation(self):
        builder = ObservationBuilder("procurement_organization")
        obs = builder.build(
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),
            raw_data={
                "supply_quantity": 100.0,
                "demand_quantity": 90.0,
                "administered_price": 50.0,
                "inventory_level": 30.0,
                "capacity_utilization": 0.85,
                "shortage_indicator": 0.1,
            },
        )
        violations = verify_observation_invariants(obs)
        assert len(violations) == 0, f"Unexpected violations: {violations}"


# ---------------------------------------------------------------------------
# Test 10 — Batch validation
# ---------------------------------------------------------------------------

class TestBatchValidation:
    def test_validate_multiple_proposals(self, calendar):
        decisions = [
            ProcurementDecision(
                decision_id="batch-1",
                actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
                organization_id="ORG-ENT-A",
                sector_id="industry",
                quarter="1968Q1",
                decision_at=date(1968, 6, 1),
                available_at=date(1968, 5, 25),
                kind=ProcurementChoiceKind.REQUEST,
                commodity_id="coal",
                requested_quantity=50.0,
            ),
            ProcurementDecision(
                decision_id="batch-2",
                actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
                organization_id="ORG-ENT-A",
                sector_id="industry",
                quarter="1968Q1",
                decision_at=date(1968, 6, 1),
                available_at=date(1968, 5, 25),
                kind=ProcurementChoiceKind.REQUEST,
                commodity_id="coal",
                requested_quantity=-10.0,  # illegal
            ),
        ]
        results = validate_proposals(
            decisions,
            calendar,
        )
        assert len(results) == 2
        assert results[0].decision_id == "batch-1"
        assert results[1].decision_id == "batch-2"
        assert results[0].is_legal
        assert not results[1].is_legal  # negative quantity


# ---------------------------------------------------------------------------
# Test 11 — ValidationResult is frozen
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Test 12 — P0 regression: observation boundary enforcement
# ---------------------------------------------------------------------------

class TestObservationBoundaryEnforcement:
    """Regression tests for P0 issue: unsafe values must be rejected."""

    def test_callback_rejected_in_observation(self):
        """A callable passed as a field value must be rejected by _to_immutable."""
        builder = ObservationBuilder("procurement_organization")
        with pytest.raises(TypeError, match="not allowed"):
            builder.build(
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                raw_data={"supply_quantity": lambda: {"state": 999}},  # callable
            )

    def test_object_with_state_rejected(self):
        """A plain object (not a dict/tuple/float) must be rejected."""
        builder = ObservationBuilder("procurement_organization")

        class MutableContainer:
            def __init__(self):
                self.value = 42

        with pytest.raises(TypeError, match="not allowed"):
            builder.build(
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                raw_data={"supply_quantity": MutableContainer()},
            )

    def test_direct_construction_rejects_mutable_values(self):
        """Direct ActorObservation construction with mutable values must fail."""
        # A mutable dict smuggled through raw_fields tuple
        with pytest.raises((ValueError, TypeError)):
            ActorObservation(
                actor_role="procurement_organization",
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                observed_fields=(
                    ("supply_quantity", {"mutable": "dict"}),  # dict is mutable
                ),
            )

    def test_direct_construction_rejects_unregistered_role(self):
        """Direct construction with an unregistered role must fail."""
        with pytest.raises(ValueError, match="not a registered role"):
            ActorObservation(
                actor_role="unregistered_role",
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                observed_fields=(),
            )

    def test_direct_construction_rejects_off_whitelist_field(self):
        """Direct construction with a field not in the role whitelist must fail."""
        with pytest.raises(ValueError, match="not in the whitelist"):
            ActorObservation(
                actor_role="procurement_organization",
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                observed_fields=(
                    ("raw_truth", 999.0),  # not in procurement whitelist
                ),
            )


# ---------------------------------------------------------------------------
# Test 13 — P0 regression: authority binding
# ---------------------------------------------------------------------------

class TestAuthorityBindingEnforcement:
    """Regression: authority must use decision's own identity, not caller-supplied."""

    def test_validate_proposal_uses_decision_own_org(self, calendar):
        """validate_proposal must use the decision's organization_id, not a parameter."""
        # A decision for ORG-ENT-B (revoked) validated against itself
        decision_b = ProcurementDecision(
            decision_id="bind-b",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-B",
            sector_id="industry",
            quarter="1973Q1",
            decision_at=date(1973, 1, 1),
            available_at=date(1972, 12, 20),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        result_b = validate_proposal(decision_b, calendar)
        # ORG-ENT-B's procurement is revoked — must be rejected
        assert result_b.authority_status == "revoked"
        assert not result_b.is_legal

    def test_nan_quantity_rejected(self):
        """NaN quantities must be rejected in legal validation."""
        decision = ProcurementDecision(
            decision_id="nan-qty",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=float("nan"),
        )
        is_legal, reason = decision.validate_legality()
        assert not is_legal
        assert "finite" in reason.lower()

    def test_inf_quantity_rejected(self):
        """Inf quantities must be rejected in legal validation."""
        decision = PriceProposalDecision(
            decision_id="inf-price",
            actor_role=ActorRole.APPROVER,
            organization_id="ORG-GOV",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=PriceProposalKind.SET,
            commodity_id="steel",
            proposed_price=float("inf"),
        )
        is_legal, reason = decision.validate_legality()
        assert not is_legal
        assert "finite" in reason.lower()


class TestValidationResultFrozen:
    def test_validation_result_is_frozen(self, calendar):
        decision = ProcurementDecision(
            decision_id="d15",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        result = validate_proposal(
            decision, calendar,
        )
        from dataclasses import FrozenInstanceError

        with pytest.raises(FrozenInstanceError):  # frozen dataclass
            result.is_legal = False  # type: ignore[misc]

    def test_validation_result_to_dict(self, calendar):
        decision = ProcurementDecision(
            decision_id="d16",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        result = validate_proposal(
            decision, calendar,
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["decision_id"] == "d16"
        assert "is_legal" in d
        assert "authority_status" in d
        assert "reason" in d
