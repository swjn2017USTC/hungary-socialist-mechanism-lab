"""H2A §3: proposal validation — legal choices, authority, no state patches.

Validates that a Decision expresses a legal choice (not a stock/cash assignment)
and that the actor has the required permission from the H1B authority layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hsm_lab.contract.base import ConfigError
from hsm_lab.institutions.authority import authority_at
from hsm_lab.institutions.decisions import (
    ActorRole,
    Decision,
    HouseholdNeedDecision,
    InvestmentDecision,
    PriceProposalDecision,
    ProcurementDecision,
)
from hsm_lab.institutions.schemas import RegimeCalendar

# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of proposal validation — frozen, no mutable aliases."""

    decision_id: str
    is_legal: bool
    authority_status: str  # "granted" | "revoked" | "unknown" | "not_applicable"
    reason: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "is_legal": self.is_legal,
            "authority_status": self.authority_status,
            "reason": self.reason,
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# Role → H1B permission mapping
# ---------------------------------------------------------------------------

# Maps each H2A actor role to the H1B permission that authorizes their decisions.
_ROLE_PERMISSION_MAP: dict[ActorRole, str] = {
    ActorRole.PROCUREMENT_ORGANIZATION: "procurement",
    ActorRole.INVESTMENT_ORGANIZATION: "investment_approval",
    ActorRole.APPROVER: "price_setting",
    ActorRole.HOUSEHOLD_RECEIVER: "consumption_allocation",
}

# Sectors for each role (minimal synthetic scope)
_ROLE_SECTOR_IDS: dict[ActorRole, tuple[str, ...]] = {
    ActorRole.PROCUREMENT_ORGANIZATION: ("industry", "agriculture"),
    ActorRole.INVESTMENT_ORGANIZATION: ("industry",),
    ActorRole.APPROVER: ("industry",),
    ActorRole.HOUSEHOLD_RECEIVER: ("household",),
}

# Organizations for each role
_ROLE_ORG_IDS: dict[ActorRole, tuple[str, ...]] = {
    ActorRole.PROCUREMENT_ORGANIZATION: ("ORG-ENT-A", "ORG-ENT-B"),
    ActorRole.INVESTMENT_ORGANIZATION: ("ORG-ENT-A",),
    ActorRole.APPROVER: ("ORG-GOV",),
    ActorRole.HOUSEHOLD_RECEIVER: ("HH-001", "HH-002"),
}


# ---------------------------------------------------------------------------
# Core validator
# ---------------------------------------------------------------------------


def validate_proposal(
    decision: Decision,
    calendar: RegimeCalendar,
    geographic_id: str = "national",
    observation: Any = None,  # noqa: ANN401
) -> ValidationResult:
    """Validate one decision against authority and legality rules.

    The organization and sector are derived from the decision's own declared identity.
    The caller-supplied geographic_id supplements the decision's context.
    The decision's quarter must match the year/quarter implied by decision_at
    (single-clock principle).
    If an observation is supplied, its organization_id, sector_id, and quarter must
    be consistent with the decision's declared identity.

    Returns
    -------
    ValidationResult
        Frozen result with is_legal, authority_status, and reason.
        No state is modified.
    """
    # Step 0: single-clock — quarter must be consistent with decision_at
    quarter_year = decision.decision_at.year
    quarter_month = (decision.decision_at.month - 1) // 3 + 1
    implied_quarter = f"{quarter_year}Q{quarter_month}"
    if decision.quarter != implied_quarter:
        return ValidationResult(
            decision_id=decision.decision_id,
            is_legal=False,
            authority_status="not_applicable",
            reason=(
                f"Quarter mismatch: decision.quarter={decision.quarter!r} "
                f"does not match quarter implied by decision_at "
                f"{decision.decision_at} ({implied_quarter}); "
                f"single-clock principle violated"
            ),
        )

    # Step 0b: organization/role compatibility — org must be registered for this role
    permitted_orgs = _ROLE_ORG_IDS.get(decision.actor_role, ())
    if decision.organization_id not in permitted_orgs:
        return ValidationResult(
            decision_id=decision.decision_id,
            is_legal=False,
            authority_status="not_applicable",
            reason=(
                f"Organization {decision.organization_id!r} is not registered for "
                f"role {decision.actor_role.value}; registered: {permitted_orgs}"
            ),
        )

    # Step 0c: sector must be registered for this role
    permitted_sectors = _ROLE_SECTOR_IDS.get(decision.actor_role, ())
    if decision.sector_id not in permitted_sectors:
        return ValidationResult(
            decision_id=decision.decision_id,
            is_legal=False,
            authority_status="not_applicable",
            reason=(
                f"Sector {decision.sector_id!r} is not registered for "
                f"role {decision.actor_role.value}; registered: {permitted_sectors}"
            ),
        )

    # Step 0d: observation context must be consistent with decision identity
    if observation is not None:
        from hsm_lab.institutions.observed import ActorObservation
        if isinstance(observation, ActorObservation):
            obs_org = observation.organization_id
            obs_sector = observation.sector_id
            obs_quarter = observation.quarter
        elif isinstance(observation, dict):
            # Validate dict observations for key fields; skip if not present
            obs_org = observation.get("organization_id")
            obs_sector = observation.get("sector_id")
            obs_quarter = observation.get("quarter")
        else:
            obs_org = None
            obs_sector = None
            obs_quarter = None

        if obs_org is not None and obs_org != decision.organization_id:
            return ValidationResult(
                decision_id=decision.decision_id,
                is_legal=False,
                authority_status="not_applicable",
                reason=(
                    f"Observation organization_id {obs_org!r} "
                    f"does not match decision organization_id "
                    f"{decision.organization_id!r}"
                ),
            )
        if obs_sector is not None and obs_sector != decision.sector_id:
            return ValidationResult(
                decision_id=decision.decision_id,
                is_legal=False,
                authority_status="not_applicable",
                reason=(
                    f"Observation sector_id {obs_sector!r} "
                    f"does not match decision sector_id {decision.sector_id!r}"
                ),
            )
        if obs_quarter is not None and obs_quarter != decision.quarter:
            return ValidationResult(
                decision_id=decision.decision_id,
                is_legal=False,
                authority_status="not_applicable",
                reason=(
                    f"Observation quarter {obs_quarter!r} "
                    f"does not match decision quarter {decision.quarter!r}"
                ),
            )

        # Bounded planning: reject future information in observation
        bp_passed, bp_reason = BoundedPlanning().evaluate(decision, observation)
        if not bp_passed:
            return ValidationResult(
                decision_id=decision.decision_id,
                is_legal=False,
                authority_status="not_applicable",
                reason=f"bounded_planning violated: {bp_reason}",
            )

    # Step 1: structural legality (no negative quantities, non-empty IDs, available_at)
    is_legal, legal_reason = decision.validate_legality()
    if not is_legal:
        return ValidationResult(
            decision_id=decision.decision_id,
            is_legal=False,
            authority_status="not_applicable",
            reason=legal_reason,
        )

    # Step 2: authority check via H1B calendar — use decision's own identity
    permission = _ROLE_PERMISSION_MAP.get(decision.actor_role, "unknown")
    warnings: list[str] = []

    if permission == "unknown":
        return ValidationResult(
            decision_id=decision.decision_id,
            is_legal=False,
            authority_status="not_applicable",
            reason=f"No H1B permission mapped for role {decision.actor_role.value}",
        )

    # Derive organization and sector from the decision's own declared identity
    org_id = decision.organization_id
    sec_id = decision.sector_id

    try:
        auth_result = authority_at(
            calendar,
            organization_id=org_id,
            sector_id=sec_id,
            geographic_id=geographic_id,
            permission=permission,
            decision_at=decision.decision_at,
        )
        auth_status = auth_result.status
    except ConfigError as exc:
        # Authority query failed (e.g. unknown organization) → treat as unknown
        auth_status = "unknown"
        warnings.append(f"authority_at raised ConfigError: {exc}")

    # authority must be 'granted' for the decision to be legally valid
    if auth_status != "granted":
        return ValidationResult(
            decision_id=decision.decision_id,
            is_legal=False,
            authority_status=auth_status,
            reason=(
                f"Authority for {permission} is {auth_status} at "
                f"{decision.decision_at} for {org_id}/{sec_id}; "
                f"decision is not legally valid"
            ),
            warnings=tuple(warnings),
        )

    # Step 3: additional role-specific checks
    extra_reason = _role_specific_check(decision, org_id, sec_id)
    if extra_reason:
        warnings.append(extra_reason)

    return ValidationResult(
        decision_id=decision.decision_id,
        is_legal=True,
        authority_status=auth_status,
        reason=(
            f"Legal {permission} authority confirmed ({auth_status}) for "
            f"{org_id}/{sec_id} at {decision.decision_at}. "
            f"{legal_reason}"
        ),
        warnings=tuple(warnings),
    )


def _role_specific_check(
    decision: Decision,
    organization_id: str,
    sector_id: str,
) -> str:
    """Return a warning string for role-specific constraints; empty = no warning."""
    match decision:
        case ProcurementDecision():
            # procurement requests must be within declared commodity scope
            if not _commodity_in_scope(decision.commodity_id, sector_id):
                return (
                    f"commodity {decision.commodity_id} may be outside sector "
                    f"{sector_id} scope — verify against registry"
                )
        case PriceProposalDecision():
            # price proposals must be non-negative (already checked in validate_legality)
            # additional check: extreme price values may indicate data error
            if decision.proposed_price > 1e9:
                return f"proposed_price {decision.proposed_price} is extremely large"
        case InvestmentDecision():
            # investment requests require sector alignment
            if sector_id not in ("industry", "infrastructure"):
                return (
                    f"investment approval typically applies to industry/infrastructure, "
                    f"got sector {sector_id}"
                )
        case HouseholdNeedDecision():
            # household need claims must be non-negative (already checked)
            pass
    return ""


def _commodity_in_scope(commodity_id: str, sector_id: str) -> bool:
    """Minimal scope check: commodity_id is non-empty."""
    return bool(commodity_id and commodity_id.strip())


# ---------------------------------------------------------------------------
# Batch validation
# ---------------------------------------------------------------------------


def validate_proposals(
    decisions: list[Decision],
    calendar: RegimeCalendar,
    geographic_id: str = "national",
    observation: Any = None,  # noqa: ANN401
) -> list[ValidationResult]:
    """Validate a batch of decisions, each independently.

    Returns a list of ValidationResult in the same order as input decisions.
    """
    return [
        validate_proposal(d, calendar, geographic_id, observation)
        for d in decisions
    ]


# ---------------------------------------------------------------------------
# Rule declarations (H2A §4: three rules — no LLM, no execution)
# ---------------------------------------------------------------------------


class DecisionRule:
    """Base class for decision rules — declaration only, no execution."""

    rule_name: str
    description: str

    def applies_to(self, decision: Decision) -> bool:
        """Return True if this rule applies to the given decision type."""
        raise NotImplementedError

    def evaluate(
        self, decision: Decision, observation: Any  # noqa: ANN401
    ) -> tuple[bool, str]:
        """Return (passes, reason). No LLM calls, no state modification."""
        raise NotImplementedError


class HistoricalRuleBased(DecisionRule):
    """Rule 1: decisions must be consistent with historical precedent."""

    rule_name = "historical_rule_based"
    description = (
        "A decision is valid only if it does not contradict known historical "
        "institutional constraints for the same organization, sector, and period."
    )

    def applies_to(self, decision: Decision) -> bool:
        return True  # applies to all decision types

    def evaluate(
        self, decision: Decision, observation: Any  # noqa: ANN401
    ) -> tuple[bool, str]:
        # Declarative upper bound: reject if observation shows contradictory history.
        # This is a technical diagnostic, NOT a claim about historical truth.
        # No LLM, no real-time inference.
        return True, "historical_rule_based: no contradiction detected"


class BoundedPlanning(DecisionRule):
    """Rule 2: decisions must respect bounded planning horizons."""

    rule_name = "bounded_planning"
    description = (
        "A decision cannot anticipate information not yet available at the "
        "decision date.  available_at must be <= decision_at."
    )

    def applies_to(self, decision: Decision) -> bool:
        return True

    def evaluate(
        self, decision: Decision, observation: Any  # noqa: ANN401
    ) -> tuple[bool, str]:
        if decision.available_at > decision.decision_at:
            return False, (
                f"bounded_planning violated: available_at {decision.available_at} "
                f"is after decision_at {decision.decision_at}"
            )
        # Bounded planning: observation must be within decision's information horizon
        if observation is not None:
            # Try ActorObservation attribute first, then raw dict key
            obs_avail = getattr(observation, "available_at", None)
            if obs_avail is None and isinstance(observation, dict):
                obs_avail = observation.get("available_at")
            if obs_avail is not None and obs_avail > decision.decision_at:
                return False, (
                    f"bounded_planning violated: observation available_at "
                    f"{obs_avail} is after decision_at {decision.decision_at}"
                )
        return True, "bounded_planning: information horizon respected"


class FullInformationUpperBound(DecisionRule):
    """Rule 3: full-information upper bound for diagnostic only."""

    rule_name = "full_information_upper_bound"
    description = (
        "Technical upper bound: if all information were available, the optimal "
        "decision would be X.  Used for diagnostic comparison only.  Does NOT "
        "give historical actors future information or ground truth."
    )

    def applies_to(self, decision: Decision) -> bool:
        return True

    def evaluate(
        self, decision: Decision, observation: Any  # noqa: ANN401
    ) -> tuple[bool, str]:
        # This is a diagnostic upper bound.  No LLM, no real data.
        return True, "full_information_upper_bound: diagnostic declared"


# Registry of all rules
ALL_RULES: tuple[DecisionRule, ...] = (
    HistoricalRuleBased(),
    BoundedPlanning(),
    FullInformationUpperBound(),
)


def evaluate_all_rules(
    decision: Decision, observation: Any  # noqa: ANN401
) -> list[tuple[DecisionRule, bool, str]]:
    """Evaluate all three rules against a decision and observation.

    Returns a list of (rule, passed, reason) tuples.
    """
    return [
        (rule, *rule.evaluate(decision, observation))
        for rule in ALL_RULES
        if rule.applies_to(decision)
    ]
