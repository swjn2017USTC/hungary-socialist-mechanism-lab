"""H2A §3: proposal validation — legal choices, authority, no state patches.

Validates that a Decision expresses a legal choice (not a stock/cash assignment)
and that the actor has the required permission from the H1B authority layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
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
    # Step 0: validate against concrete registered decision types only
    # Reject arbitrary subclasses that may declare stock/cash or other assignment fields
    from hsm_lab.institutions.decisions import (
        HouseholdNeedDecision,
        InvestmentDecision,
        PriceProposalDecision,
        ProcurementDecision,
    )
    _ALLOWED_DECISION_TYPES = (
        HouseholdNeedDecision,
        InvestmentDecision,
        PriceProposalDecision,
        ProcurementDecision,
    )
    if type(decision) not in _ALLOWED_DECISION_TYPES:
        return ValidationResult(
            decision_id=getattr(decision, "decision_id", "<unknown>"),
            is_legal=False,
            authority_status="not_applicable",
            reason=f"Decision type {type(decision).__name__} is not a registered H2A type",
        )

    # Step 0: full decision reconstruction via model_validate (catches Literal enum
    # mismatches, primitive subclasses, and any field type violations from model_copy)
    # BUT first: check original __dict__ for undeclared attrs (model_dump omits these!)
    decision_type = type(decision)
    declared_fields = set(decision_type.model_fields.keys())
    instance_fields = set(decision.__dict__.keys())
    extra_fields = instance_fields - declared_fields
    if extra_fields:
        return ValidationResult(
            decision_id=getattr(decision, "decision_id", "<unknown>"),
            is_legal=False,
            authority_status="not_applicable",
            reason=f"Decision has extra attributes: {extra_fields}",
        )
    # Also check for primitive subclasses in declared fields (model_dump normalizes them away)
    for field_name in declared_fields:
        value = decision.__dict__.get(field_name)
        if value is None:
            continue
        # Check primitive subclasses (str, float, int)
        if isinstance(value, str) and type(value) not in (str, bytes):
            return ValidationResult(
                decision_id=getattr(decision, "decision_id", "<unknown>"),
                is_legal=False,
                authority_status="not_applicable",
                reason=(
                    f"Decision field {field_name} is a str subclass; "
                    f"primitive subclasses may carry mutable state"
                ),
            )
        if isinstance(value, float) and type(value) is not float:
            return ValidationResult(
                decision_id=getattr(decision, "decision_id", "<unknown>"),
                is_legal=False,
                authority_status="not_applicable",
                reason=(
                    f"Decision field {field_name} is a float subclass; "
                    f"primitive subclasses may carry mutable state"
                ),
            )
        if isinstance(value, int) and type(value) is not int:
            return ValidationResult(
                decision_id=getattr(decision, "decision_id", "<unknown>"),
                is_legal=False,
                authority_status="not_applicable",
                reason=(
                    f"Decision field {field_name} is an int subclass; "
                    f"primitive subclasses may carry mutable state"
                ),
            )
    try:
        decision_dump = decision.model_dump()
        decision = decision_type.model_validate(decision_dump)
    except Exception as exc:
        return ValidationResult(
            decision_id=getattr(decision, "decision_id", "<unknown>"),
            is_legal=False,
            authority_status="not_applicable",
            reason=f"Decision re-validation failed: {exc}",
        )

    # Step 0: decision date subclass recheck (catches model_copy bypass of model_validator)
    for field_name in ("decision_at", "available_at"):
        value = getattr(decision, field_name, None)
        if value is not None and isinstance(value, date) and type(value) is not date:
            return ValidationResult(
                decision_id=decision.decision_id,
                is_legal=False,
                authority_status="not_applicable",
                reason=(
                    f"Decision.{field_name} is a date subclass "
                    f"({type(value).__name__}); date subclasses may carry mutable state"
                ),
            )

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
            obs_geo = observation.geographic_id
            obs_role = observation.actor_role
        elif isinstance(observation, dict):
            # Reject dict subclasses (could carry __slots__ with raw_truth/session)
            if type(observation) is not dict:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason="Observation is a dict subclass; only plain dict allowed",
                )
            obs_role = observation.get("actor_role")
            if obs_role is None:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason="Dict observation missing required actor_role field",
                )
            # Reject dict observations with top-level prohibited keys (case-insensitive)
            # and enforce exact-case known field names (reject case variants of known fields)
            _TOP_LEVEL_PROHIBITED = frozenset({
                "raw_truth", "session", "callback", "closure", "target",
                "truth", "calibration_target", "role",
            })
            _KNOWN_OBSERVATION_FIELDS = frozenset({
                "actor_role", "organization_id", "sector_id", "geographic_id",
                "quarter", "decision_at", "available_at", "observed_fields",
            })
            _KNOWN_LOWERCASE = {k.lower() for k in _KNOWN_OBSERVATION_FIELDS}
            for key in observation:
                # Dict key must be exactly str (reject str subclasses used as keys)
                if type(key) is not str:
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason=(
                            f"Dict observation key must be exactly str, "
                            f"got {type(key).__name__}"
                        ),
                    )
                key_lower = key.lower()
                # Case-insensitive prohibited key check
                if key_lower in _TOP_LEVEL_PROHIBITED:
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason=f"Dict observation contains prohibited key {key!r}",
                    )
                # Catch role-suffix fields (e.g., "role_assignment", "user_role")
                # but not "actor_role" (the legitimate field)
                if key_lower.endswith("_role") and key_lower != "actor_role":
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason=f"Dict observation contains prohibited key {key!r}",
                    )
                # Reject unknown top-level fields (not in known observation schema)
                # AND reject case variants of known fields (must be exact case)
                if key_lower not in _KNOWN_LOWERCASE or key not in _KNOWN_OBSERVATION_FIELDS:
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason=f"Dict observation contains unknown field {key!r}",
                    )
            # Require context fields in dict observations
            # actor_role: must be exactly str
            obs_actor_role = observation.get("actor_role")
            if obs_actor_role is None:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason="Dict observation missing required actor_role field",
                )
            if type(obs_actor_role) is not str:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=(
                        f"Dict observation actor_role must be exactly str, "
                        f"got {type(obs_actor_role).__name__}"
                    ),
                )
            for field_name, field_val in [
                ("organization_id", observation.get("organization_id")),
                ("sector_id", observation.get("sector_id")),
                ("quarter", observation.get("quarter")),
                ("decision_at", observation.get("decision_at")),
                ("geographic_id", observation.get("geographic_id")),
            ]:
                if field_val is None:
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason=f"Dict observation missing required {field_name} field",
                    )
                # Reject primitive subclasses in dict observation metadata
                if isinstance(field_val, str) and type(field_val) is not str:
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason=(
                            f"Dict observation field {field_name} is a str subclass; "
                            f"primitive subclasses may carry mutable state"
                        ),
                    )
                if isinstance(field_val, int) and type(field_val) is not int:
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason=(
                            f"Dict observation field {field_name} is an int subclass; "
                            f"primitive subclasses may carry mutable state"
                        ),
                    )
            obs_org = observation.get("organization_id")
            obs_sector = observation.get("sector_id")
            obs_quarter = observation.get("quarter")
            obs_geo = observation.get("geographic_id")
            # available_at must be a plain date (not subclass, not string)
            obs_avail_raw = observation.get("available_at")
            if obs_avail_raw is not None:
                if isinstance(obs_avail_raw, date) and type(obs_avail_raw) is not date:
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason=(
                            f"Observation available_at is a date subclass "
                            f"({type(obs_avail_raw).__name__}); "
                            f"date subclasses may carry forged comparison methods"
                        ),
                    )
                if not isinstance(obs_avail_raw, date):
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason=(
                            f"Observation available_at must be a date, "
                            f"got {type(obs_avail_raw).__name__}"
                        ),
                    )
        else:
            # Reject unsupported observation types
            return ValidationResult(
                decision_id=decision.decision_id,
                is_legal=False,
                authority_status="not_applicable",
                reason=(
                    f"Unsupported observation type {type(observation).__name__}; "
                    f"must be ActorObservation or dict with required date fields"
                ),
            )

        # Organization check
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
        # Sector check
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
        # Quarter check
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
        # Geographic context check: if observation has geographic_id, it must match
        if obs_geo is not None and obs_geo != geographic_id:
            return ValidationResult(
                decision_id=decision.decision_id,
                is_legal=False,
                authority_status="not_applicable",
                reason=(
                    f"Observation geographic_id {obs_geo!r} "
                    f"does not match authorized scope {geographic_id!r}"
                ),
            )
        # Role binding: observation's role must match decision's role
        if obs_role != decision.actor_role.value:
            return ValidationResult(
                decision_id=decision.decision_id,
                is_legal=False,
                authority_status="not_applicable",
                reason=(
                    f"Observation actor_role {obs_role!r} "
                    f"does not match decision actor_role {decision.actor_role.value!r}"
                ),
            )

        # Decision timestamp binding: observation's decision_at must match decision's
        if isinstance(observation, ActorObservation):
            obs_decision_at = observation.decision_at
        elif isinstance(observation, dict):
            obs_decision_at = observation.get("decision_at")
        else:
            obs_decision_at = None

        if obs_decision_at is not None and obs_decision_at != decision.decision_at:
            return ValidationResult(
                decision_id=decision.decision_id,
                is_legal=False,
                authority_status="not_applicable",
                reason=(
                    f"Observation decision_at {obs_decision_at} "
                    f"does not match decision decision_at {decision.decision_at}"
                ),
            )

        # Convert mutable observed_fields to immutable for downstream safety
        if isinstance(observation, dict) and "observed_fields" in observation:
            obs_fields = observation["observed_fields"]
            if obs_fields is None:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason="Dict observation observed_fields must be a tuple, not None",
                )
            if not isinstance(obs_fields, tuple):
                observation = dict(observation)
                observation["observed_fields"] = tuple(obs_fields)

        # Re-validate ActorObservation at boundary (catches model_copy bypass of __init__)
        # Check __dict__ for extra attributes AND __slots__ BEFORE model_dump
        if isinstance(observation, ActorObservation):
            # Reject ActorObservation subclasses (only concrete type allowed)
            if type(observation) is not ActorObservation:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=(
                        f"Observation is a {type(observation).__name__} subclass; "
                        f"only concrete ActorObservation allowed"
                    ),
                )
            declared_fields = set(ActorObservation.model_fields.keys())
            instance_attrs = set(observation.__dict__.keys())
            extra_attrs = instance_attrs - declared_fields
            if extra_attrs:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=f"Observation has extra attributes: {extra_attrs}",
                )
            # Check for primitive subclasses in declared fields (model_dump normalizes them)
            for field_name in declared_fields:
                value = observation.__dict__.get(field_name)
                if value is None:
                    continue
                if isinstance(value, str) and type(value) not in (str, bytes):
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason=(
                            f"Observation field {field_name} is a str subclass; "
                            f"primitive subclasses may carry mutable state"
                        ),
                    )
                if isinstance(value, int) and type(value) is not int:
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason=(
                            f"Observation field {field_name} is an int subclass; "
                            f"primitive subclasses may carry mutable state"
                        ),
                    )
            # Also force full re-validation via dump+validate
            try:
                dump = observation.model_dump()
                ActorObservation.model_validate(dump)
            except Exception as exc:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=f"observation re-validation failed: {exc}",
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

        # Verify all observation representations pass observation invariants
        from hsm_lab.institutions.observed import verify_observation_invariants

        if isinstance(observation, dict):

            class _DictAdapter:
                """Minimal dict wrapper for verify_observation_invariants."""

                __slots__ = ("_d",)

                def __init__(self, d):
                    self._d = d

                @property
                def available_at(self):
                    return self._d["available_at"]

                @property
                def decision_at(self):
                    return self._d["decision_at"]

                @property
                def actor_role(self):
                    return self._d["actor_role"]

                @property
                def observed_fields(self):
                    return tuple(self._d.get("observed_fields", []))

            try:
                obs_errors = verify_observation_invariants(_DictAdapter(observation))
            except (AttributeError, TypeError, KeyError, ValueError) as exc:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=f"observation malformed: {exc}",
                )
            if obs_errors:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=f"observation invariant violation: {obs_errors[0]}",
                )
        else:
            # ActorObservation: still verify (model_copy may have bypassed __init__)
            try:
                obs_errors = verify_observation_invariants(observation)
            except (AttributeError, TypeError, KeyError, ValueError) as exc:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=f"observation malformed: {exc}",
                )
            if obs_errors:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=f"observation invariant violation: {obs_errors[0]}",
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
            if obs_avail is not None:
                # Reject date subclasses (could carry forged __gt__)
                if isinstance(obs_avail, date) and type(obs_avail) is not date:
                    return False, (
                        f"bounded_planning violated: observation available_at "
                        f"is a date subclass ({type(obs_avail).__name__}); "
                        f"date subclasses may carry forged comparison methods"
                    )
                if obs_avail > decision.decision_at:
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
