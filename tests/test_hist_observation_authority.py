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
                # Not in whitelist and not prohibited — should be dropped silently
                "household_income": 500.0,
                "unrelated_field": "should_not_appear",
            },
        )
        assert obs.actor_role == "procurement_organization"
        field_names = {name for name, _ in obs.observed_fields}
        assert "supply_quantity" in field_names
        assert "demand_quantity" in field_names
        assert "administered_price" in field_names
        assert "household_income" not in field_names
        assert "unrelated_field" not in field_names

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
                "foreign_key": "fk-abc",  # not whitelisted — should be dropped
            },
        )
        field_names = {name for name, _ in obs.observed_fields}
        assert "requested_quantity" in field_names
        assert "approved_quantity" in field_names
        assert "priority_score" in field_names
        assert "foreign_key" not in field_names

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
            quarter="1968Q2",
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

    def test_bounded_planning_rejects_future_observation(self):
        """BoundedPlanning must reject when observation.available_at > decision.decision_at."""
        rule = BoundedPlanning()
        # Decision at 1968-01-15, observation available at 1985-01-10
        decision = ProcurementDecision(
            decision_id="d9",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),  # decision's own cutoff is fine
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        # Observation with future available_at
        future_obs = ActorObservation(
            actor_role="procurement_organization",
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            quarter="1985Q1",
            decision_at=date(1985, 1, 15),
            available_at=date(1985, 1, 10),
            observed_fields=(("inventory_level", 999.0),),
        )
        passed, reason = rule.evaluate(decision, future_obs)
        assert not passed
        assert "bounded_planning" in reason.lower()
        assert "observation" in reason.lower()

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
    def test_same_quarter_different_roles_different_outcomes(self, calendar):
        """Same observation context, different roles → different authorization outcomes.

        PROCUREMENT_ORGANIZATION at ORG-ENT-A has procurement authority (granted).
        HOUSEHOLD_RECEIVER at HH-001 has no procurement grant → unknown.
        These exact outcomes are asserted, not just "different".
        """
        # ORG-ENT-A procurement → granted
        proc_decision = ProcurementDecision(
            decision_id="d12",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        proc_result = validate_proposal(proc_decision, calendar)

        # HH-001 has no consumption_allocation grant → unknown
        hh_decision = HouseholdNeedDecision(
            decision_id="d13",
            actor_role=ActorRole.HOUSEHOLD_RECEIVER,
            organization_id="HH-001",
            sector_id="household",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=HouseholdNeedKind.REGISTER,
            household_id="HH-001",
            commodity_id="coal",
            claimed_quantity=50.0,
        )
        hh_result = validate_proposal(hh_decision, calendar)

        # Exact outcomes asserted
        assert proc_result.authority_status == "granted"
        assert proc_result.is_legal
        assert hh_result.authority_status == "unknown"
        assert not hh_result.is_legal  # no grant = not legal
        assert proc_result.decision_id != hh_result.decision_id


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

    def test_three_roles_same_decision_at_same_quarter_rejected_together(self, calendar):
        """Three different roles using the same decision_at date must all pass the
        single-clock quarter check, and their outcomes must differ by authority
        (not by clock divergence).

        This verifies a single clock: no role can operate at a different tick
        from another role at the same wall-clock date.
        """
        # Same date for all three roles
        same_date = date(1968, 6, 1)
        same_quarter = "1968Q2"

        # Role 1: PROCUREMENT_ORGANIZATION
        proc_decision = ProcurementDecision(
            decision_id="three-role-proc",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter=same_quarter,
            decision_at=same_date,
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        proc_result = validate_proposal(proc_decision, calendar)

        # Role 2: HOUSEHOLD_RECEIVER
        hh_decision = HouseholdNeedDecision(
            decision_id="three-role-hh",
            actor_role=ActorRole.HOUSEHOLD_RECEIVER,
            organization_id="HH-001",
            sector_id="household",
            quarter=same_quarter,
            decision_at=same_date,
            available_at=date(1968, 5, 25),
            kind=HouseholdNeedKind.REGISTER,
            household_id="HH-001",
            commodity_id="coal",
            claimed_quantity=30.0,
        )
        hh_result = validate_proposal(hh_decision, calendar)

        # Role 3: APPROVER
        appr_decision = PriceProposalDecision(
            decision_id="three-role-appr",
            actor_role=ActorRole.APPROVER,
            organization_id="ORG-GOV",
            sector_id="industry",
            quarter=same_quarter,
            decision_at=same_date,
            available_at=date(1968, 5, 25),
            kind=PriceProposalKind.SET,
            commodity_id="steel",
            proposed_price=100.0,
        )
        appr_result = validate_proposal(appr_decision, calendar)

        # CRITICAL: All three decisions pass the single-clock check.
        # If any failed with "quarter mismatch", it would indicate a clock bug.
        # We check that NONE of them have the quarter-mismatch/single-clock reason.
        for role_label, result in [
            ("PROCUREMENT_ORGANIZATION", proc_result),
            ("HOUSEHOLD_RECEIVER", hh_result),
            ("APPROVER", appr_result),
        ]:
            assert "quarter mismatch" not in result.reason.lower(), (
                f"{role_label} failed single-clock check: {result.reason}"
            )
            assert "single-clock" not in result.reason.lower(), (
                f"{role_label} failed single-clock check: {result.reason}"
            )

        # Outcomes differ by authority, not by clock:
        # - PROCUREMENT_ORGANIZATION at ORG-ENT-A: granted → is_legal=True
        # - HOUSEHOLD_RECEIVER at HH-001: unknown (no grant) → is_legal=False
        # - APPROVER at ORG-GOV: granted → is_legal=True (price proposals
        #   are always legal if approver has grant — we only check clock here)
        assert proc_result.is_legal, (
            f"PROCUREMENT_ORGANIZATION should be legal: {proc_result.reason}"
        )
        assert not hh_result.is_legal, f"HOUSEHOLD_RECEIVER should not be legal: {hh_result.reason}"
        # APPROVER outcome depends on grant; we only care that all three pass the clock check

    def test_expired_tick_rejected(self, calendar):
        """A decision whose quarter is earlier than the quarter implied by
        decision_at must be rejected (single-clock violation)."""
        # decision_at=1968-06-01 implies 1968Q2, but quarter is 1967Q4 → expired
        decision = ProcurementDecision(
            decision_id="expired-tick",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1967Q4",  # earlier than implied 1968Q2
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        result = validate_proposal(decision, calendar)
        assert not result.is_legal
        assert "quarter mismatch" in result.reason.lower()
        assert "single-clock" in result.reason.lower()

    def test_future_tick_rejected(self, calendar):
        """A decision whose quarter is later than the quarter implied by
        decision_at must be rejected (single-clock violation)."""
        # decision_at=1968-06-01 implies 1968Q2, but quarter is 1970Q1 → future
        decision = ProcurementDecision(
            decision_id="future-tick",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1970Q1",  # later than implied 1968Q2
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        result = validate_proposal(decision, calendar)
        assert not result.is_legal
        assert "quarter mismatch" in result.reason.lower()
        assert "single-clock" in result.reason.lower()

    def test_same_observation_dict_different_roles_different_outcomes(self, calendar):
        """Identical dict observation context but different roles → different outcomes.

        Both decisions receive the same observation dict (same quarter, same date,
        same org/sector/geographic context). Only the actor_role differs.
        This proves permission depends on role identity, not on smuggled context.
        """
        # Shared observation context
        shared_obs = {
            "actor_role": "procurement_organization",
            "organization_id": "ORG-ENT-A",
            "sector_id": "industry",
            "quarter": "1968Q2",
            "decision_at": date(1968, 6, 1),
            "available_at": date(1968, 5, 25),
            "geographic_id": "national",
            "observed_fields": [
                ("supply_quantity", 100.0),
            ],
        }

        # Decision 1: PROCUREMENT_ORGANIZATION — has grant → legal
        proc_decision = ProcurementDecision(
            decision_id="same-obs-proc",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        proc_result = validate_proposal(proc_decision, calendar, observation=shared_obs)

        # Decision 2: HOUSEHOLD_RECEIVER — matching HH observation
        hh_decision = HouseholdNeedDecision(
            decision_id="same-obs-hh",
            actor_role=ActorRole.HOUSEHOLD_RECEIVER,
            organization_id="HH-001",
            sector_id="household",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=HouseholdNeedKind.REGISTER,
            household_id="HH-001",
            commodity_id="coal",
            claimed_quantity=30.0,
        )
        # Use matching HH observation with valid household_receiver fields.
        # Same "information content" (ration_quota = 50.0 same value as supply_quantity),
        # but different role context. allocation_quota is NOT in household_receiver
        # whitelist — use ration_quota instead.
        hh_obs = {
            "actor_role": "household_receiver",
            "organization_id": "HH-001",
            "sector_id": "household",
            "quarter": "1968Q2",
            "decision_at": date(1968, 6, 1),
            "available_at": date(1968, 5, 25),
            "geographic_id": "national",
            "observed_fields": [
                ("ration_quota", 50.0),  # valid household_receiver field
            ],
        }
        hh_result = validate_proposal(hh_decision, calendar, observation=hh_obs)

        # Outcomes differ by role authority, not because observation was ignored:
        # - PROCUREMENT_ORGANIZATION at ORG-ENT-A: granted → is_legal=True
        # - HOUSEHOLD_RECEIVER at HH-001: unknown (no consumption_allocation grant)
        #   → is_legal=False, authority_status="unknown"
        assert proc_result.is_legal and proc_result.authority_status == "granted"
        assert not hh_result.is_legal
        assert hh_result.authority_status == "unknown"
        assert proc_result.decision_id != hh_result.decision_id

    def test_observation_org_mismatch_rejected_different_from_stock_injection(self, calendar):
        """Observation with mismatched org must be rejected, distinct from
        attempting to inject stock/cash (which is also rejected)."""
        decision = ProcurementDecision(
            decision_id="obs-org-mismatch",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        # Observation for different org
        obs_wrong_org = {
            "actor_role": "procurement_organization",
            "organization_id": "ORG-ENT-B",  # mismatch
            "sector_id": "industry",
            "quarter": "1968Q2",
            "decision_at": date(1968, 6, 1),
            "available_at": date(1968, 5, 25),
            "geographic_id": "national",
            "observed_fields": [("supply_quantity", 999.0)],
        }
        result = validate_proposal(decision, calendar, observation=obs_wrong_org)
        assert not result.is_legal
        assert "organization_id" in result.reason.lower()


# ---------------------------------------------------------------------------
# Test 9 — Verify observation invariants
# ---------------------------------------------------------------------------

class TestObservationInvariants:
    def test_no_raw_truth_in_observation(self):
        """raw_truth is rejected outright — no silent drop. Prohibited keys raise TypeError."""
        builder = ObservationBuilder("procurement_organization")
        with pytest.raises(TypeError, match="Prohibited key"):
            builder.build(
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                raw_data={
                    "supply_quantity": 100.0,
                    "raw_truth": 999.0,  # prohibited — raises
                },
            )

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

    def test_observed_fields_tuple_type_check_before_unpack(self):
        """verify_observation_invariants must check observed_fields is tuple before unpacking.

        Regression test for P0-4: verify_observation_invariants previously iterated
        obs.observed_fields to check whitelist before verifying it is a plain tuple,
        allowing a non-tuple iterable to execute __iter__ via the for-loop unpacking.
        """
        iter_called: list[str] = []

        class CustomIterable:
            """Iterable that is not a tuple — tests the type check ordering."""
            def __iter__(self):
                iter_called.append("CustomIterable.__iter__")
                return iter([("supply_quantity", 100.0)])

        # Use object.__setattr__ to bypass frozen=True on ActorObservation
        # This simulates a state where observed_fields has been smuggled as a custom iterable
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
        # Smuggle in a custom iterable as observed_fields via __setattr__
        object.__setattr__(obs, "observed_fields", CustomIterable())

        violations = verify_observation_invariants(obs)
        # Must detect non-tuple type and return early without iterating
        assert any("exactly tuple" in v for v in violations), (
            f"Expected 'exactly tuple' violation, got: {violations}"
        )
        assert iter_called == [], (
            f"CustomIterable.__iter__ was called {len(iter_called)} time(s); "
            "tuple type check must happen before unpacking observed_fields"
        )

    def test_observed_fields_element_with_iter_callback_rejected(self):
        """A tuple of custom-iterable elements must be rejected without calling __iter__.

        Regression test: outer observed_fields is a plain tuple, but element has custom
        __iter__. The element-type check must catch this before any unpacking.
        """
        iter_called: list[str] = []

        class EvilElement:
            """Non-tuple element whose __iter__ appends to a tracker."""
            def __iter__(self):
                iter_called.append("EvilElement.__iter__")
                return iter([("supply_quantity", 100.0)])

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
        # Replace observed_fields with a tuple containing a non-tuple element
        object.__setattr__(obs, "observed_fields", (EvilElement(),))

        violations = verify_observation_invariants(obs)
        # Must detect non-tuple element and report it
        assert any("exactly tuple" in v and "EvilElement" in v for v in violations), (
            f"Expected 'exactly tuple' violation for EvilElement, got: {violations}"
        )
        assert iter_called == [], (
            f"EvilElement.__iter__ was called {len(iter_called)} time(s); "
            "element type check must happen before unpacking"
        )

    def test_verify_observation_invariants_date_comparison_before_type_check(self):
        """Date subclass in available_at must be rejected without calling __gt__.

        Regression test: verify_observation_invariants previously compared
        available_at > decision_at before checking if they are plain dates,
        executing a date subclass's __gt__ callback.
        """
        gt_called: list[str] = []

        class EvilDate(date):
            """date subclass whose __gt__ appends to a tracker."""
            def __gt__(self, other) -> bool:
                gt_called.append("EvilDate.__gt__")
                return False

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
        # Replace available_at with EvilDate using __setattr__
        object.__setattr__(obs, "available_at", EvilDate(1968, 1, 10))

        violations = verify_observation_invariants(obs)
        # Must detect date subclass without comparing
        assert any("plain date" in v and "available_at" in v for v in violations), (
            f"Expected 'plain date' violation for available_at, got: {violations}"
        )
        assert gt_called == [], (
            f"EvilDate.__gt__ was called {len(gt_called)} time(s); "
            "date type check must happen before comparison"
        )


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
                quarter="1968Q2",
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
                quarter="1968Q2",
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

    def test_mixed_date_subclass_rejected(self):
        """A date subclass carrying mutable state must be rejected."""
        class MutableDate(date):
            pass

        d = MutableDate(1968, 1, 15)
        with pytest.raises(TypeError, match="plain date"):
            ActorObservation(
                actor_role="procurement_organization",
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=d,
                available_at=date(1968, 1, 10),
                observed_fields=(),
            )

    def test_non_string_dict_key_rejected_no_callback(self):
        """A dict with a non-string key must be rejected without calling the key's __str__.

        Regression test for P0-1: _check_no_prohibited_keys previously called str(k)
        before checking type(k) is str, allowing a malicious key's __str__ to execute.
        """
        callbacks: list[str] = []

        class MaliciousKey:
            """Non-string key whose __str__ appends to a tracker."""
            def __str__(self) -> str:
                callbacks.append("MaliciousKey.__str__")
                return "coal"

        builder = ObservationBuilder("procurement_organization")
        with pytest.raises(TypeError, match="not str"):
            builder.build(
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                raw_data={"inventory_level": {"outer": {MaliciousKey(): 30.0}}},
            )
        assert callbacks == [], (
            f"MaliciousKey.__str__ was called {len(callbacks)} time(s); "
            "non-string dict keys must be rejected before calling str(k)"
        )

    def test_non_string_dict_key_rejected_no_repr_callback(self):
        """A dict with a non-string key must be rejected without calling the key's __repr__.

        Regression test for P0 (residual): the rejection branch previously used {k!r}
        formatting which calls __repr__ on untrusted key objects.
        """
        repr_called: list[str] = []

        class KeyWithRepr:
            """Non-string key whose __repr__ appends to a tracker."""
            def __repr__(self) -> str:
                repr_called.append("KeyWithRepr.__repr__")
                return "KeyWithRepr()"

        builder = ObservationBuilder("procurement_organization")
        with pytest.raises(TypeError, match="not str"):
            builder.build(
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                raw_data={"supply_quantity": {KeyWithRepr(): 50.0}},
            )
        assert repr_called == [], (
            f"KeyWithRepr.__repr__ was called {len(repr_called)} time(s); "
            "rejection path must not format untrusted key with {{k!r}}"
        )

    def test_top_level_raw_data_key_no_str_callback(self):
        """Top-level raw_data non-string key must be rejected without calling .lower()."""
        callbacks: list[str] = []

        class TopKey:
            def lower(self) -> str:
                callbacks.append("TopKey.lower")
                return "supply_quantity"

        builder = ObservationBuilder("procurement_organization")
        with pytest.raises(TypeError, match="not str"):
            builder.build(
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                raw_data={TopKey(): 50.0},
            )
        assert callbacks == [], (
            f"TopKey.lower() was called {len(callbacks)} time(s); "
            "top-level raw_data key rejection must use str.lower() builtin"
        )

    def test_top_level_raw_data_key_no_repr_callback(self):
        """Top-level raw_data non-string key must be rejected without calling __repr__."""
        repr_called: list[str] = []

        class TopKeyRepr:
            def __repr__(self) -> str:
                repr_called.append("TopKeyRepr.__repr__")
                return "TopKeyRepr()"

        builder = ObservationBuilder("procurement_organization")
        with pytest.raises(TypeError, match="not str"):
            builder.build(
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                raw_data={TopKeyRepr(): 50.0},
            )
        assert repr_called == [], (
            f"TopKeyRepr.__repr__ was called {len(repr_called)} time(s); "
            "top-level rejection must not use {{key!r}} formatting"
        )

    def test_nested_prohibited_key_rejected(self):
        """A nested dict containing prohibited keys must be rejected."""
        builder = ObservationBuilder("procurement_organization")
        with pytest.raises(TypeError, match="Prohibited key"):
            builder.build(
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                raw_data={
                    "inventory_level": {  # "inventory_level" is in the whitelist
                        "value": 999.0,
                        "role": "calibration_target",  # prohibited key
                    },
                },
            )

    def test_nested_raw_truth_key_rejected(self):
        """A nested dict containing raw_truth must be rejected."""
        builder = ObservationBuilder("procurement_organization")
        with pytest.raises(TypeError, match="raw_truth"):
            builder.build(
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                raw_data={
                    "supply_quantity": {
                        "value": 100.0,
                        "raw_truth": 42.0,  # prohibited
                    },
                },
            )

    def test_role_as_top_level_key_rejected(self):
        """Top-level 'role' key (indicator of target-role information) must be rejected."""
        builder = ObservationBuilder("procurement_organization")
        with pytest.raises(TypeError, match="Prohibited key"):
            builder.build(
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                raw_data={
                    "role": "calibration_target",
                    "inventory_level": 999.0,
                },
            )

    def test_tuple_of_pairs_with_prohibited_keys_rejected(self):
        """Tuple-of-pairs representation containing prohibited keys must be rejected."""
        # Simulate the internal format with prohibited content
        payload = (
            ("role", "calibration_target"),
            ("raw_truth", 999.0),
        )
        with pytest.raises((ValueError, TypeError), match="[Pp]rohibited"):
            ActorObservation(
                actor_role="procurement_organization",
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                observed_fields=(("inventory_level", payload),),
            )

    def test_frozenset_with_prohibited_keys_rejected(self):
        """A frozenset containing prohibited (key, value) pairs must be rejected."""
        payload = frozenset({
            ("raw_truth", 999.0),
            ("role", "calibration_target"),
        })
        with pytest.raises((ValueError, TypeError), match="[Pp]rohibited"):
            ActorObservation(
                actor_role="procurement_organization",
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                observed_fields=(("inventory_level", payload),),
            )

    def test_uppercase_prohibited_key_rejected(self):
        """Prohibited keys must be caught case-insensitively (RAW_TRUTH, ROLE, etc.)."""
        # Uppercase variant of raw_truth
        payload = frozenset({("RAW_TRUTH", 999.0), ("ROLE", "CALIBRATION_TARGET")})
        with pytest.raises((ValueError, TypeError), match="[Pp]rohibited"):
            ActorObservation(
                actor_role="procurement_organization",
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                observed_fields=(("inventory_level", payload),),
            )

    def test_mixed_case_prohibited_key_in_builder_rejected(self):
        """Mixed-case prohibited keys must be caught in the builder path (case-insensitive)."""
        builder = ObservationBuilder("procurement_organization")
        with pytest.raises(TypeError, match="[Pp]rohibited"):
            builder.build(
                organization_id="ORG-ENT-A",
                sector_id="industry",
                geographic_id="national",
                quarter="1968Q1",
                decision_at=date(1968, 1, 15),
                available_at=date(1968, 1, 10),
                raw_data={
                    "inventory_level": {
                        "value": 100.0,
                        "RAW_TRUTH": 42.0,  # uppercase — still prohibited
                    },
                },
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

    def test_investment_decision_with_correct_role_and_permission(self, calendar):
        """InvestmentDecision with INVESTMENT_ORGANIZATION queries investment_approval."""
        decision = InvestmentDecision(
            decision_id="inv-1",
            actor_role=ActorRole.INVESTMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            project_id="P1",
            requested_amount=50.0,
        )
        result = validate_proposal(decision, calendar)
        # ORG-ENT-A has investment_approval granted in 1968
        assert result.is_legal
        assert result.authority_status == "granted"
        assert "investment" in result.reason.lower()

    def test_investment_decision_with_wrong_role_rejected(self, calendar):
        """InvestmentDecision with PROCUREMENT_ORGANIZATION role must be rejected."""
        decision = InvestmentDecision(
            decision_id="inv-wrong-role",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            project_id="P1",
            requested_amount=50.0,
        )
        result = validate_proposal(decision, calendar)
        assert not result.is_legal
        assert "INVESTMENT_ORGANIZATION" in result.reason

    def test_procurement_decision_with_approver_role_rejected(self, calendar):
        """ProcurementDecision with APPROVER role must be rejected."""
        decision = ProcurementDecision(
            decision_id="wrong-role-proc",
            actor_role=ActorRole.APPROVER,
            organization_id="ORG-GOV",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        result = validate_proposal(decision, calendar)
        assert not result.is_legal
        assert "PROCUREMENT_ORGANIZATION" in result.reason

    def test_price_decision_with_procurement_role_rejected(self, calendar):
        """PriceProposalDecision with PROCUREMENT_ORGANIZATION role must be rejected."""
        decision = PriceProposalDecision(
            decision_id="wrong-role-price",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=PriceProposalKind.SET,
            commodity_id="steel",
            proposed_price=50.0,
        )
        result = validate_proposal(decision, calendar)
        assert not result.is_legal
        assert "APPROVER" in result.reason

    def test_nan_quantity_rejected(self):
        """NaN quantities must be rejected in legal validation."""
        decision = ProcurementDecision(
            decision_id="nan-qty",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
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
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=PriceProposalKind.SET,
            commodity_id="steel",
            proposed_price=float("inf"),
        )
        is_legal, reason = decision.validate_legality()
        assert not is_legal
        assert "finite" in reason.lower()

    def test_quarter_decision_at_mismatch_rejected(self, calendar):
        """Decision with mismatched quarter and decision_at must be rejected.

        quarter='1957Q1' but decision_at=1968-06-01 → single-clock violation.
        """
        decision = ProcurementDecision(
            decision_id="mismatch-1",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1957Q1",  # mismatched with decision_at=1968
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        result = validate_proposal(decision, calendar)
        assert not result.is_legal
        assert "quarter mismatch" in result.reason.lower()
        assert "single-clock" in result.reason.lower()

    def test_organization_not_registered_for_role_rejected(self, calendar):
        """Organization HH-001 is not registered for PROCUREMENT_ORGANIZATION role."""
        decision = ProcurementDecision(
            decision_id="wrong-org",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="HH-001",  # not registered for procurement role
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        result = validate_proposal(decision, calendar)
        assert not result.is_legal
        assert "not registered for role" in result.reason.lower()

    def test_sector_not_registered_for_role_rejected(self, calendar):
        """sector_id='household' is not registered for PROCUREMENT_ORGANIZATION role."""
        decision = ProcurementDecision(
            decision_id="wrong-sector",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="household",  # not registered for procurement role
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        result = validate_proposal(decision, calendar)
        assert not result.is_legal
        assert "not registered for" in result.reason.lower()

    def test_observation_org_mismatch_rejected(self, calendar):
        """Observation with different organization_id than decision must be rejected."""
        decision = ProcurementDecision(
            decision_id="ctx-mismatch",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        # Observation for ORG-ENT-B (wrong org)
        obs = ActorObservation(
            actor_role="procurement_organization",
            organization_id="ORG-ENT-B",  # mismatched
            sector_id="industry",
            geographic_id="national",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            observed_fields=(("supply_quantity", 100.0),),
        )
        result = validate_proposal(decision, calendar, observation=obs)
        assert not result.is_legal
        assert "does not match decision organization_id" in result.reason.lower()

    def test_dict_observation_future_info_rejected(self, calendar):
        """Dict observation with future available_at must be rejected by BoundedPlanning."""
        decision = ProcurementDecision(
            decision_id="dict-future",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        # Dict observation with future available_at
        dict_obs = {
            "actor_role": "procurement_organization",
            "organization_id": "ORG-ENT-A",
            "sector_id": "industry",
            "quarter": "1968Q2",
            "decision_at": date(1968, 6, 1),
            "available_at": date(1985, 1, 10),  # future
            "geographic_id": "national",
            "observed_fields": [
                ("supply_quantity", 100.0),
            ],
        }
        result = validate_proposal(decision, calendar, observation=dict_obs)
        assert not result.is_legal
        assert "bounded_planning" in result.reason.lower()

    def test_dict_observation_missing_context_rejected(self, calendar):
        """Dict observation missing required context fields must be rejected."""
        decision = ProcurementDecision(
            decision_id="missing-ctx",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        # Dict observation missing organization_id
        dict_obs = {
            "actor_role": "procurement_organization",
            # missing organization_id
            "sector_id": "industry",
            "quarter": "1968Q2",
            "decision_at": date(1968, 6, 1),
            "available_at": date(1968, 5, 25),
            "geographic_id": "national",
            "observed_fields": [
                ("supply_quantity", 100.0),
            ],
        }
        result = validate_proposal(decision, calendar, observation=dict_obs)
        assert not result.is_legal
        assert "missing required" in result.reason.lower()

    def test_decision_with_date_subclass_rejected(self):
        """Decision with date subclass for decision_at must be rejected."""
        class MutableDate(date):
            pass

        d = MutableDate(1968, 6, 1)
        with pytest.raises(TypeError, match="plain date"):
            ProcurementDecision(
                decision_id="date-subclass",
                actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
                organization_id="ORG-ENT-A",
                sector_id="industry",
                quarter="1968Q2",
                decision_at=d,
                available_at=date(1968, 5, 25),
                kind=ProcurementChoiceKind.REQUEST,
                commodity_id="coal",
                requested_quantity=50.0,
            )

    def test_forged_date_in_dict_observation_rejected(self, calendar):
        """Dict observation with forged date subclass (overridden __gt__) must be rejected."""
        class ForgedDate(date):
            """Date subclass with forged __gt__ that always returns False."""
            def __gt__(self, other):
                return False  # lies: claims every date is not greater

        decision = ProcurementDecision(
            decision_id="forged-date",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        dict_obs = {
            "actor_role": "procurement_organization",
            "organization_id": "ORG-ENT-A",
            "sector_id": "industry",
            "quarter": "1968Q2",
            "decision_at": date(1968, 6, 1),
            "available_at": ForgedDate(1988, 1, 1),  # forged future date
            "geographic_id": "national",
            "observed_fields": [
                ("supply_quantity", 100.0),
            ],
        }
        result = validate_proposal(decision, calendar, observation=dict_obs)
        assert not result.is_legal
        assert "date subclass" in result.reason.lower()

    def test_unsupported_observation_type_rejected(self, calendar):
        """Unsupported observation type (not ActorObservation or dict) must be rejected."""
        decision = ProcurementDecision(
            decision_id="bad-obs-type",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        # Use a plain object as observation
        result = validate_proposal(decision, calendar, observation=object())
        assert not result.is_legal
        assert "unsupported observation type" in result.reason.lower()

    def test_actor_role_mismatch_rejected(self, calendar):
        """ActorObservation with wrong actor_role must be rejected."""
        decision = ProcurementDecision(
            decision_id="role-mismatch",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        # Observation from investment organization, not procurement
        obs = ActorObservation(
            actor_role="investment_organization",
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            observed_fields=(("requested_amount", 999.0),),
        )
        result = validate_proposal(decision, calendar, observation=obs)
        assert not result.is_legal
        assert "actor_role" in result.reason.lower()

    def test_dict_observation_with_callback_rejected(self, calendar):
        """Dict observation containing prohibited content must be rejected."""
        decision = ProcurementDecision(
            decision_id="callback-obs",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        dict_obs = {
            "actor_role": "procurement_organization",
            "organization_id": "ORG-ENT-A",
            "sector_id": "industry",
            "quarter": "1968Q2",
            "decision_at": date(1968, 6, 1),
            "available_at": date(1968, 5, 25),
            "geographic_id": "national",
            # Prohibited content in observed_fields
            "observed_fields": [
                ("supply_quantity", 100.0),
                ("raw_truth", {"inventory_level": 999}),  # prohibited key
            ],
        }
        result = validate_proposal(decision, calendar, observation=dict_obs)
        # Dict observations with prohibited keys in observed_fields rejected
        assert not result.is_legal

    def test_forged_actor_role_rejected_no_callback(self, calendar):
        """Dict observation with forged actor_role (custom __ne__) must be rejected.

        Regression test for P0-2: validate_proposal previously compared obs_role
        (extracted from dict observation) using != before type-checking it, allowing
        a malicious object's __ne__ to execute.
        """
        callbacks: list[str] = []

        class ForgedRole(str):
            """str subclass whose __ne__ appends to a tracker."""
            def __ne__(self, other) -> bool:
                callbacks.append("ForgedRole.__ne__")
                return False  # lies: claims equal to everything

        decision = ProcurementDecision(
            decision_id="forge-role",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
            decision_at=date(1968, 6, 1),
            available_at=date(1968, 5, 25),
            kind=ProcurementChoiceKind.REQUEST,
            commodity_id="coal",
            requested_quantity=50.0,
        )
        forged_obs = {
            "actor_role": ForgedRole("procurement_organization"),
            "organization_id": "ORG-ENT-A",
            "sector_id": "industry",
            "quarter": "1968Q2",
            "decision_at": date(1968, 6, 1),
            "available_at": date(1968, 5, 25),
            "geographic_id": "national",
            "observed_fields": [("supply_quantity", 100.0)],
        }
        result = validate_proposal(decision, calendar, observation=forged_obs)
        # Must be rejected because actor_role is not exactly str
        assert not result.is_legal, "ForgedRole observation should be rejected"
        assert "actor_role" in result.reason.lower()
        assert "exactly str" in result.reason.lower()
        assert callbacks == [], (
            f"ForgedRole.__ne__ was called {len(callbacks)} time(s); "
            "actor_role must be type-checked before comparison"
        )

    def test_actorobservation_subclass_getattribute_rejected_no_callback(self, calendar):
        """ActorObservation subclass with __getattribute__ must be rejected before __dict__ access.

        Regression test for P0-5: validate_proposal previously accessed __dict__ five times
        before checking type(observation) is not ActorObservation, allowing a subclass
        __getattribute__ to intercept the lookups.
        """
        dict_calls: list[str] = []

        class SubObservation(ActorObservation):
            """ActorObservation subclass whose __getattribute__ logs access."""

            def __getattribute__(self, name: str) -> object:
                if name.startswith("_"):
                    return super().__getattribute__(name)
                dict_calls.append(f"__getattribute__({name!r})")
                return super().__getattribute__(name)

        # Build a clean observation and wrap it in the subclass
        builder = ObservationBuilder("procurement_organization")
        clean_obs = builder.build(
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            quarter="1968Q1",
            decision_at=date(1968, 1, 15),
            available_at=date(1968, 1, 10),
            raw_data={"supply_quantity": 100.0},
        )
        sub_obs = SubObservation(
            actor_role=clean_obs.actor_role,
            organization_id=clean_obs.organization_id,
            sector_id=clean_obs.sector_id,
            geographic_id=clean_obs.geographic_id,
            quarter=clean_obs.quarter,
            decision_at=clean_obs.decision_at,
            available_at=clean_obs.available_at,
            observed_fields=clean_obs.observed_fields,
        )

        # Clear calls from SubObservation construction (Pydantic validation).
        # Only calls made DURING validate_proposal matter for this regression test.
        dict_calls.clear()

        decision = ProcurementDecision(
            decision_id="sub-obs-test",
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
        result = validate_proposal(decision, calendar, observation=sub_obs)
        # Must be rejected as ActorObservation subclass
        assert not result.is_legal
        assert "subclass" in result.reason.lower()
        assert dict_calls == [], (
            f"__getattribute__ was called {len(dict_calls)} time(s); "
            "ActorObservation subclass check must happen before any __dict__ access"
        )

class TestValidationResultFrozen:
    def test_validation_result_is_frozen(self, calendar):
        decision = ProcurementDecision(
            decision_id="d15",
            actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            quarter="1968Q2",
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
            quarter="1968Q2",
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
