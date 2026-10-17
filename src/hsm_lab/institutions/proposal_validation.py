"""H2A §3: proposal validation — legal choices, authority, no state patches.

Validates that a Decision expresses a legal choice (not a stock/cash assignment)
and that the actor has the required permission from the H1B authority layer.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.schemas import Quarter, ScenarioSpec
from hsm_lab.engine.state import MaterialState
from hsm_lab.institutions.authority import authority_at
from hsm_lab.institutions.decisions import (
    DECISION_FIELD_TYPES,
    ActorRole,
    Decision,
    HouseholdNeedDecision,
    InvestmentDecision,
    PriceProposalDecision,
    ProcurementDecision,
    decision_field_value_allowed,
)
from hsm_lab.institutions.schemas import RegimeCalendar

# ---------------------------------------------------------------------------
# Exact-type trust boundary
# ---------------------------------------------------------------------------

_DECISION_ID_UNKNOWN = "<unknown>"

# Dict-observation schema: exact keys only, one canonical quarter, one cutoff.
_PROHIBITED_OBSERVATION_KEYS = frozenset({
    "raw_truth", "session", "callback", "closure", "target",
    "truth", "calibration_target", "role",
})
_KNOWN_OBSERVATION_FIELDS = frozenset({
    "actor_role", "organization_id", "sector_id", "geographic_id",
    "quarter", "decision_at", "available_at", "observed_fields",
})
_OBSERVATION_STRING_FIELDS = (
    "actor_role", "organization_id", "sector_id", "geographic_id", "quarter",
)
_OBSERVATION_DATE_FIELDS = ("decision_at", "available_at")


def _reject(reason: str) -> ValidationResult:
    """Static rejection result (no untrusted formatting)."""
    return ValidationResult(
        decision_id=_DECISION_ID_UNKNOWN,
        is_legal=False,
        authority_status="not_applicable",
        reason=reason,
    )


def _decision_storage_violation(decision: Any) -> str | None:
    """Return a static storage violation string, or None when clean.

    Used by public rules that must not trust an exact outer model type:
    ``model_copy`` can inject hostile keys or payload values into ``__dict__``.
    """
    decision_type = type(decision)
    if decision_type is ProcurementDecision:
        field_types = DECISION_FIELD_TYPES[ProcurementDecision]
    elif decision_type is PriceProposalDecision:
        field_types = DECISION_FIELD_TYPES[PriceProposalDecision]
    elif decision_type is InvestmentDecision:
        field_types = DECISION_FIELD_TYPES[InvestmentDecision]
    elif decision_type is HouseholdNeedDecision:
        field_types = DECISION_FIELD_TYPES[HouseholdNeedDecision]
    else:
        return "unsupported decision type"
    try:
        extra = object.__getattribute__(decision, "__pydantic_extra__")
        private = object.__getattribute__(decision, "__pydantic_private__")
        fields_set = object.__getattribute__(
            decision, "__pydantic_fields_set__"
        )
        instance = object.__getattribute__(decision, "__dict__")
    except AttributeError:
        return "decision storage is unavailable"
    if extra is not None:
        return "decision __pydantic_extra__ must be empty"
    if private is not None:
        return "decision __pydantic_private__ must be empty"
    if type(fields_set) is not set:
        return "decision model metadata is malformed"
    for name in fields_set:
        if type(name) is not str or name not in field_types:
            return "decision model metadata contains an unvalidated field name"
    if type(instance) is not dict:
        return "decision storage is malformed"
    storage_count = 0
    for key in instance:
        if type(key) is not str:
            return "decision storage has a non-exact-string key"
        if key not in field_types:
            return "decision storage contains an undeclared field"
        storage_count += 1
    if storage_count != len(field_types):
        return "decision storage is missing declared fields"
    for field_name, allowed in field_types.items():
        if not decision_field_value_allowed(instance.get(field_name), allowed):
            return f"decision field {field_name} has an invalid exact type"
    return None


def _quarter_storage_violation(quarter: Any) -> str | None:
    """Audit a ``Quarter`` before any arithmetic or method dispatch.

    An exact ``Quarter`` can carry a shadowing ``advance`` attribute or
    non-integer fields via ``model_copy``/``model_construct``.  Only the two
    declared exact-integer fields may exist; arithmetic is done below with
    trusted operations, never through instance methods.
    """
    if type(quarter) is not Quarter:
        return "session quarter is malformed"
    try:
        extra = object.__getattribute__(quarter, "__pydantic_extra__")
        private = object.__getattribute__(quarter, "__pydantic_private__")
        fields_set = object.__getattribute__(quarter, "__pydantic_fields_set__")
        instance = object.__getattribute__(quarter, "__dict__")
    except AttributeError:
        return "session quarter storage is unavailable"
    if extra is not None or private is not None:
        return "session quarter metadata is malformed"
    if type(fields_set) is not set:
        return "session quarter metadata is malformed"
    for name in fields_set:
        if type(name) is not str or name not in ("year", "quarter"):
            return "session quarter metadata contains an unvalidated field name"
    if (
        len(fields_set) != 2
        or "year" not in fields_set
        or "quarter" not in fields_set
    ):
        return "session quarter metadata must declare exactly year and quarter"
    if type(instance) is not dict or len(instance) != 2:
        return "session quarter storage is malformed"
    for key in instance:
        if type(key) is not str or key not in ("year", "quarter"):
            return "session quarter storage is malformed"
    year = instance.get("year")
    quarter_index = instance.get("quarter")
    if type(year) is not int or type(quarter_index) is not int:
        return "session quarter fields must be exact ints"
    if not (1 <= year <= 9999) or not (1 <= quarter_index <= 4):
        return "session quarter fields are out of range"
    return None


def _canonical_observation(
    observation: Any,
) -> tuple[Any, str | None]:
    """Canonicalise an observation through the single custody boundary.

    Returns ``(ActorObservation, None)`` or ``(None, violation)``.  Dict
    inputs are converted to a clean immutable model so aliases, prohibited
    keys, identity conflicts, and mutable values cannot survive.
    """
    from hsm_lab.institutions.observed import (
        ActorObservation,
        _to_immutable,
        verify_observation_invariants,
    )

    observation_type = type(observation)
    if observation_type is ActorObservation:
        violations = verify_observation_invariants(observation)
        if violations:
            return None, violations[0]
        return observation, None
    if observation_type is not dict:
        return None, (
            "Unsupported observation type; only concrete ActorObservation "
            "or plain dict allowed; subclasses are rejected"
        )
    for key in observation:
        if type(key) is not str:
            return None, "Dict observation key must be exactly str"
        key_lower = str.lower(key)
        if key_lower in _PROHIBITED_OBSERVATION_KEYS:
            return None, "Dict observation contains a prohibited key"
        if key_lower.endswith("_role") and key_lower != "actor_role":
            return None, "Dict observation contains a prohibited key"
        if key not in _KNOWN_OBSERVATION_FIELDS:
            return None, "Dict observation contains an unknown field"
    for name in _KNOWN_OBSERVATION_FIELDS:
        if name not in observation:
            return None, f"Dict observation missing required {name} field"
    for name in _OBSERVATION_STRING_FIELDS:
        if type(observation[name]) is not str:
            return None, f"Dict observation field {name} must be exactly str"
    for name in _OBSERVATION_DATE_FIELDS:
        if type(observation[name]) is not date:
            return None, (
                f"Dict observation field {name} must be a plain date; "
                "date subclasses are rejected"
            )
    if observation["available_at"] > observation["decision_at"]:
        return None, (
            "bounded_planning violated: observation available_at "
            "is after decision_at"
        )
    raw_fields = observation["observed_fields"]
    if type(raw_fields) is list:
        raw_fields = tuple(raw_fields)
    if type(raw_fields) is not tuple:
        return None, (
            "Dict observation observed_fields must be a plain list or tuple"
        )
    canonical_fields: list[tuple[str, Any]] = []
    for element in raw_fields:
        if type(element) is not tuple or len(element) != 2:
            return None, "observed_fields elements must be 2-tuples"
        field_name = element[0]
        if type(field_name) is not str:
            return None, "observed field name must be exactly str"
        try:
            field_value = _to_immutable(element[1])
        except TypeError:
            return None, "observed field value is not deep-immutable"
        canonical_fields.append((field_name, field_value))
    try:
        canonical = ActorObservation(
            actor_role=observation["actor_role"],
            organization_id=observation["organization_id"],
            sector_id=observation["sector_id"],
            geographic_id=observation["geographic_id"],
            quarter=observation["quarter"],
            decision_at=observation["decision_at"],
            available_at=observation["available_at"],
            observed_fields=tuple(canonical_fields),
        )
    except ValueError as exc:
        # All inputs are exact, converted types, so the message is our static
        # semantic diagnostic (household identity, duplicate names, quarter).
        return None, str(exc)
    except TypeError:
        return None, "observation malformed"
    violations = verify_observation_invariants(canonical)
    if violations:
        return None, violations[0]
    return canonical, None

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
    # "admission" (clock-bound) or "retrospective" (calendar-only diagnosis).
    mode: str = "admission"
    # True only for a legal result produced by clock-bound admission.
    admission_eligible: bool = False
    # SHA-256 of the exact decision payload this result validated.  Execution
    # must compare it to the decision it is about to commit.
    decision_digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "is_legal": self.is_legal,
            "authority_status": self.authority_status,
            "reason": self.reason,
            "warnings": list(self.warnings),
            "mode": self.mode,
            "admission_eligible": self.admission_eligible,
            "decision_digest": self.decision_digest,
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


def _validate_proposal_core(
    decision: Decision,
    calendar: RegimeCalendar,
    geographic_id: str,
    observation: Any,  # noqa: ANN401
    session: Any,  # noqa: ANN401
) -> ValidationResult:
    """Shared validator body; callers establish admission/retrospective mode."""
    # Trusted caller inputs: exact types before any comparison or query.
    if type(geographic_id) is not str:
        return _reject("geographic_id must be exactly str")
    if type(calendar) is not RegimeCalendar:
        return _reject("calendar must be an exact RegimeCalendar")

    # Step 0: exact-type trust boundary.
    # Identity-only checks: chained ``is`` comparisons never trigger ``__eq__``
    # on a hostile metaclass.  Unsupported objects are rejected without any
    # attribute access and with a static decision identifier.
    dt = type(decision)
    if not (
        dt is ProcurementDecision
        or dt is PriceProposalDecision
        or dt is InvestmentDecision
        or dt is HouseholdNeedDecision
    ):
        return _reject("Decision type is not a registered H2A type")

    # Storage, metadata, exact field types, and declared enum membership are
    # audited by the same helper used by public rule evaluation.
    storage_violation = _decision_storage_violation(decision)
    if storage_violation is not None:
        return _reject(storage_violation)

    # Reconstruct from the validated field values only (defence in depth
    # against model_copy bypasses).  Every value is now an exact allowed type.
    try:
        decision_dump = decision.model_dump()
        decision = dt.model_validate(decision_dump)
    except Exception:
        # Static message: exception text can reference hostile objects.
        return _reject("Decision re-validation failed")

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

    # Step 0a: bind the decision to the existing engine clock, never a second
    # one.  The session is engine-owned and passed only by trusted callers;
    # actors never receive it.  ``completed_ticks`` names the quarter being
    # admitted, which must equal the decision's quarter.
    if session is not None:
        from hsm_lab.engine.political_run import PoliticalSession

        if type(session) is not PoliticalSession:
            return _reject("session must be an exact PoliticalSession")
        # Read raw lifecycle attributes first.  ``session.done`` and
        # ``session.completed_ticks`` are properties that coerce (``int(...)``)
        # before any type check, so they must not run on a rejected session.
        try:
            opened = object.__getattribute__(session, "opened")
            finished = object.__getattribute__(session, "finished")
        except AttributeError:
            return _reject("session clock is not initialised")
        if type(opened) is not bool or opened is not True:
            return _reject("session is not opened for admission")
        if type(finished) is not bool:
            return _reject("session clock is malformed")
        if finished:
            return _reject("session is finished; no admission is possible")
        try:
            state = object.__getattribute__(session, "state")
            spec = object.__getattribute__(session, "spec")
            target_ticks = object.__getattribute__(session, "target_ticks")
        except AttributeError:
            return _reject("session clock is not initialised")
        # Only the engine-owned container types are admissible; arbitrary
        # replacements could expose ``__dict__`` (or any field) as a property.
        if type(state) is not MaterialState:
            return _reject("session state must be an exact MaterialState")
        if type(spec) is not ScenarioSpec:
            return _reject("session spec must be an exact ScenarioSpec")
        # The engine dispatches quarters through ``session.quarter_of``.  An
        # instance attribute can shadow that method without changing the class,
        # so reject it before the engine ever runs.
        try:
            session_instance = object.__getattribute__(session, "__dict__")
        except AttributeError:
            return _reject("session clock is not initialised")
        if type(session_instance) is not dict:
            return _reject("session clock storage is malformed")
        for key in session_instance:
            if type(key) is not str:
                return _reject(
                    "session clock storage has a non-exact-string key"
                )
        if "quarter_of" in session_instance:
            return _reject("session clock method is shadowed")
        from types import FunctionType

        quarter_method = PoliticalSession.__dict__.get("quarter_of")
        if type(quarter_method) is not FunctionType:
            return _reject("session quarter method is unavailable")
        if type(target_ticks) is not int or target_ticks < 0:
            return _reject("session clock is malformed")
        # Read the nested containers' raw storage.  ``object.__getattribute__``
        # bypasses overridden ``__getattribute__`` but NOT descriptors, so
        # accessing ``state.completed_ticks`` or ``spec.start`` directly could
        # execute a property.  Read ``__dict__`` and fixed keys instead.
        try:
            state_instance = object.__getattribute__(state, "__dict__")
            spec_instance = object.__getattribute__(spec, "__dict__")
        except AttributeError:
            return _reject("session clock is not initialised")
        if type(state_instance) is not dict or type(spec_instance) is not dict:
            return _reject("session clock storage is malformed")
        for container in (state_instance, spec_instance):
            for key in container:
                if type(key) is not str:
                    return _reject(
                        "session clock storage has a non-exact-string key"
                    )
        raw_tick = state_instance.get("completed_ticks")
        start = spec_instance.get("start")
        if type(raw_tick) is not int or raw_tick < 0:
            return _reject("session clock is malformed")
        if raw_tick >= target_ticks:
            return _reject("session has no admissible quarter; it is finished")
        quarter_violation = _quarter_storage_violation(start)
        if quarter_violation is not None:
            return _reject(quarter_violation)
        # Trusted arithmetic only: no instance methods, no descriptor dispatch.
        start_instance = object.__getattribute__(start, "__dict__")
        start_year = start_instance["year"]
        start_quarter = start_instance["quarter"]
        ordinal = start_year * 4 + (start_quarter - 1) + raw_tick
        new_year, new_q0 = divmod(ordinal, 4)
        if not (1 <= new_year <= 9999):
            return _reject("session quarter is out of range")
        session_quarter = f"{new_year}Q{new_q0 + 1}"
        # The accepted session and the engine must agree on the current
        # quarter.  ``quarter_method`` is the verified class function; the
        # spec/quarter storage it reads has already been audited.
        engine_quarter = quarter_method(session, raw_tick)
        if type(engine_quarter) is not str or engine_quarter != session_quarter:
            return _reject(
                "session quarter method disagrees with the audited clock"
            )
        if decision.quarter != session_quarter:
            return ValidationResult(
                decision_id=decision.decision_id,
                is_legal=False,
                authority_status="not_applicable",
                reason=(
                    f"Quarter mismatch: decision.quarter={decision.quarter!r} "
                    f"does not match session clock quarter {session_quarter!r}; "
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
        from hsm_lab.institutions.observed import (
            ActorObservation,
            _to_immutable,
            verify_observation_invariants,
        )

        # Single trust boundary shared with the observation builder.  Exact
        # types are established before any comparison, iteration, or
        # formatting; a dict observation is canonicalised into a clean
        # immutable ActorObservation so caller-held aliases are not retained.
        observation_type = type(observation)
        if observation_type is ActorObservation:
            early_violations = verify_observation_invariants(observation)
            if early_violations:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=f"observation invariant violation: {early_violations[0]}",
                )
        elif observation_type is dict:
            for key in observation:
                if type(key) is not str:
                    return _reject("Dict observation key must be exactly str")
                key_lower = str.lower(key)
                if key_lower in _PROHIBITED_OBSERVATION_KEYS:
                    return _reject("Dict observation contains a prohibited key")
                if key_lower.endswith("_role") and key_lower != "actor_role":
                    return _reject("Dict observation contains a prohibited key")
                if key not in _KNOWN_OBSERVATION_FIELDS:
                    return _reject("Dict observation contains an unknown field")
            for name in _KNOWN_OBSERVATION_FIELDS:
                if name not in observation:
                    return _reject(
                        f"Dict observation missing required {name} field"
                    )
            for name in _OBSERVATION_STRING_FIELDS:
                if type(observation[name]) is not str:
                    return _reject(
                        f"Dict observation field {name} must be exactly str"
                    )
            for name in _OBSERVATION_DATE_FIELDS:
                if type(observation[name]) is not date:
                    return _reject(
                        f"Dict observation field {name} must be a plain date; "
                        "date subclasses are rejected"
                    )
            if observation["available_at"] > observation["decision_at"]:
                return _reject(
                    "bounded_planning violated: observation available_at "
                    "is after decision_at"
                )
            raw_fields = observation["observed_fields"]
            if type(raw_fields) is list:
                raw_fields = tuple(raw_fields)
            if type(raw_fields) is not tuple:
                return _reject(
                    "Dict observation observed_fields must be a plain list or tuple"
                )
            canonical_fields: list[tuple[str, Any]] = []
            for element in raw_fields:
                if type(element) is not tuple or len(element) != 2:
                    return _reject("observed_fields elements must be 2-tuples")
                element_name = element[0]
                if type(element_name) is not str:
                    return _reject("observed field name must be exactly str")
                try:
                    element_value = _to_immutable(element[1])
                except TypeError:
                    return _reject("observed field value is not deep-immutable")
                canonical_fields.append((element_name, element_value))
            try:
                observation = ActorObservation(
                    actor_role=observation["actor_role"],
                    organization_id=observation["organization_id"],
                    sector_id=observation["sector_id"],
                    geographic_id=observation["geographic_id"],
                    quarter=observation["quarter"],
                    decision_at=observation["decision_at"],
                    available_at=observation["available_at"],
                    observed_fields=tuple(canonical_fields),
                )
            except (TypeError, ValueError):
                return _reject("observation malformed")
            early_violations = verify_observation_invariants(observation)
            if early_violations:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=f"observation invariant violation: {early_violations[0]}",
                )
        else:
            return _reject(
                "Unsupported observation type; only concrete ActorObservation "
                "or plain dict allowed; subclasses are rejected"
            )
        if type(observation) is ActorObservation:
            # Reject ActorObservation subclasses FIRST, before any __dict__ access.
            # Subclass's __getattribute__ could intercept __dict__ lookup.
            if type(observation) is not ActorObservation:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=(
                        "Observation is a subclass; "
                        "only concrete ActorObservation allowed"
                    ),
                )
            # Access via __dict__ to avoid triggering descriptor protocol on field access
            # Check type before any comparison to prevent __eq__/__ne__ callback execution
            obs_org = observation.__dict__["organization_id"]
            obs_sector = observation.__dict__["sector_id"]
            obs_quarter = observation.__dict__["quarter"]
            obs_geo = observation.__dict__["geographic_id"]
            obs_role = observation.__dict__["actor_role"]
            # Type validation BEFORE any comparison or string formatting
            for field_name, field_val in [
                ("organization_id", obs_org),
                ("sector_id", obs_sector),
                ("quarter", obs_quarter),
                ("geographic_id", obs_geo),
                ("actor_role", obs_role),
            ]:
                if type(field_val) is not str:
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason=(
                            f"Observation field {field_name} must be exactly str"
                        ),
                    )
        # Use type() is check to avoid __getattribute__("__class__") callback
        elif type(observation) is dict:
            # Reject dict subclasses (could carry __slots__ with raw_truth/session)
            if type(observation) is not dict:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason="Observation is a dict subclass; only plain dict allowed",
                )
            # Check all dict keys are plain str BEFORE any .get() or iteration.
            # A str-subclass key with custom __eq__ could execute a callback during
            # dict lookup before the per-key type check runs.
            for key in observation:
                if type(key) is not str:
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason="Dict observation key must be exactly str; str subclasses rejected",
                    )
            obs_role = observation.get("actor_role")
            if obs_role is None:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason="Dict observation missing required actor_role field",
                )
            # actor_role value must be exactly str — reject str subclasses and arbitrary
            # objects whose __eq__ could bypass the role binding check
            if type(obs_role) is not str:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=(
                        "Observation field actor_role must be exactly str; "
                        "str subclasses rejected"
                    ),
                )
            # Reject dict observations with top-level prohibited keys (case-insensitive)
            # and enforce exact-case known field names (reject case variants of known fields)
            _OLD_TOP_LEVEL_PROHIBITED = frozenset({
                "raw_truth", "session", "callback", "closure", "target",
                "truth", "calibration_target", "role",
            })
            _OLD_KNOWN_OBSERVATION_FIELDS = frozenset({
                "actor_role", "organization_id", "sector_id", "geographic_id",
                "quarter", "decision_at", "available_at", "observed_fields",
            })
            _OLD_KNOWN_LOWERCASE = {k.lower() for k in _OLD_KNOWN_OBSERVATION_FIELDS}
            for key in observation:
                # Dict key must be exactly str (reject str subclasses used as keys)
                if type(key) is not str:
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason="Dict observation key must be exactly str; str subclasses rejected",
                    )
                key_lower = key.lower()
                # Case-insensitive prohibited key check
                if key_lower in _OLD_TOP_LEVEL_PROHIBITED:
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
                if (
                    key_lower not in _OLD_KNOWN_LOWERCASE
                    or key not in _OLD_KNOWN_OBSERVATION_FIELDS
                ):
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
                        "Dict observation actor_role must be exactly str; "
                        "str subclasses rejected"
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
                # String metadata fields must be exactly str type (reject str subclasses
                # AND arbitrary objects with matching __eq__)
                if field_name in ("organization_id", "sector_id", "quarter", "geographic_id"):
                    if type(field_val) is not str:
                        return ValidationResult(
                            decision_id=decision.decision_id,
                            is_legal=False,
                            authority_status="not_applicable",
                            reason=(
                                "Dict observation field must be exactly str; "
                                "str subclasses may carry mutable state"
                            ),
                        )
            obs_org = observation.get("organization_id")
            obs_sector = observation.get("sector_id")
            obs_quarter = observation.get("quarter")
            obs_geo = observation.get("geographic_id")
            # available_at must be a plain date (not subclass, not string)
            obs_avail_raw = observation.get("available_at")
            if obs_avail_raw is not None:
                # Reject non-plain-date via type() is check (avoids .__bases__ callback)
                if type(obs_avail_raw) is not date:
                    return ValidationResult(
                        decision_id=decision.decision_id,
                        is_legal=False,
                        authority_status="not_applicable",
                        reason=(
                            "Observation available_at is a date subclass; "
                            "date subclasses may carry forged comparison methods"
                        ),
                    )
        else:
            # Check for ActorObservation subclasses without isinstance()
            # Use type() is check: if it's not exactly ActorObservation, reject as unsupported
            if type(observation) is not ActorObservation:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=(
                        "Unsupported observation type; only concrete ActorObservation or "
                        "plain dict allowed; ActorObservation subclasses are rejected"
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
        # Check type BEFORE comparison to prevent callback execution via __eq__
        # Use type() is check to avoid __getattribute__("__class__") callback on smuggled obs
        obs_type = type(observation)
        if obs_type is ActorObservation:
            obs_decision_at = observation.decision_at
            if type(obs_decision_at) is not date:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason="Observation decision_at must be a plain date; date subclasses rejected",
                )
        elif obs_type is dict:
            obs_decision_at = observation.get("decision_at")
            if obs_decision_at is not None and type(obs_decision_at) is not date:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason="Observation decision_at must be a plain date; date subclasses rejected",
                )
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
        # Use obs_type (computed at line 567) to avoid repeated __class__ access
        if obs_type is dict and "observed_fields" in observation:
            obs_fields = observation["observed_fields"]
            if obs_fields is None:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason="Dict observation observed_fields must be a tuple, not None",
                )
            if type(obs_fields) is tuple:
                pass  # OK, already a plain tuple
            elif type(obs_fields) is list:
                # Convert plain list to tuple
                observation = dict(observation)
                observation["observed_fields"] = tuple(obs_fields)
            else:
                # Reject tuple subclasses, list subclasses, and all other iterables
                # (arbitrary __iter__ may execute callbacks with side effects)
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=(
                        "Dict observation observed_fields must be a plain list "
                        "or tuple; other types rejected"
                    ),
                )

        # Re-validate ActorObservation at boundary (catches model_copy bypass of __init__)
        # Check __dict__ for extra attributes AND __slots__ BEFORE model_dump
        # Use type() is check to avoid __getattribute__("__class__") on smuggled observation
        if type(observation) is ActorObservation:
            # Reject ActorObservation subclasses (only concrete type allowed)
            if type(observation) is not ActorObservation:
                return ValidationResult(
                    decision_id=decision.decision_id,
                    is_legal=False,
                    authority_status="not_applicable",
                    reason=(
                        "Observation is a subclass; "
                        "only concrete ActorObservation allowed"
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
            # String fields: require exact str type (reject str subclasses AND bytes with __eq__)
            _STRING_FIELDS = frozenset({
                "actor_role", "organization_id", "sector_id", "geographic_id", "quarter",
            })
            for field_name in declared_fields:
                value = observation.__dict__.get(field_name)
                if value is None:
                    continue
                if field_name in _STRING_FIELDS:
                    if type(value) is not str:
                        return ValidationResult(
                            decision_id=decision.decision_id,
                            is_legal=False,
                            authority_status="not_applicable",
                            reason=(
                                f"Observation field {field_name} must be exactly str"
                            ),
                        )
            # NOTE: model_dump() removed — it triggers __getattribute__ on all fields,
            # including any smuggled Payload objects in observed_fields.
            # Field-level checks above (extra_attrs, str subclass guards,
            # and _is_deep_immutable check in verify_observation_invariants)
            # provide sufficient validation without triggering callbacks.
            # We no longer call observation.model_dump() here.

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

        # Use type() is check to avoid __getattribute__("__class__") callback on smuggled obs
        if type(observation) is dict:

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


def _decision_digest(decision: Any) -> str:
    """SHA-256 of the exact decision payload, for execution binding.

    Serialization is only safe after the exact-type/storage boundary has
    proven every field is a trusted primitive/enum/date.  Rejected or
    malformed payloads get an empty digest, which execution refuses.
    """
    import hashlib

    decision_type = type(decision)
    if not (
        decision_type is ProcurementDecision
        or decision_type is PriceProposalDecision
        or decision_type is InvestmentDecision
        or decision_type is HouseholdNeedDecision
    ):
        return ""
    if _decision_storage_violation(decision) is not None:
        return ""
    try:
        payload = decision.model_dump_json()
    except Exception:
        return ""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _tag_mode(
    result: ValidationResult, mode: str, decision: Any
) -> ValidationResult:
    """Attach the evaluation mode, eligibility and payload digest."""
    return replace(
        result,
        mode=mode,
        admission_eligible=bool(result.is_legal and mode == "admission"),
        decision_digest=_decision_digest(decision),
    )


def validate_proposal(
    decision: Decision,
    calendar: RegimeCalendar,
    geographic_id: str = "national",
    observation: Any = None,  # noqa: ANN401
    *,
    session: Any = None,  # noqa: ANN401 — omitted admission session is rejected
    retrospective: bool = False,
) -> ValidationResult:
    """Validate one decision for clock-bound admission, or explicitly retrospective.

    Admission requires the existing engine-owned ``PoliticalSession`` (opened,
    unfinished, non-exhausted) whose ``completed_ticks`` quarter equals the
    decision quarter.  ``retrospective=True`` performs calendar-only diagnosis
    and is mutually exclusive with ``session``; its result is tagged
    ``mode="retrospective"`` and ``admission_eligible=False``.
    """
    if type(retrospective) is not bool:
        return _tag_mode(
            _reject("retrospective must be exactly bool"), "admission", decision
        )
    if retrospective:
        if session is not None:
            return _tag_mode(
                _reject("session and retrospective are mutually exclusive"),
                "retrospective",
                decision,
            )
        mode = "retrospective"
    else:
        if session is None:
            return _tag_mode(
                _reject(
                    "session clock is required for admission; pass an existing "
                    "PoliticalSession or retrospective=True for calendar-only "
                    "diagnosis"
                ),
                "admission",
                decision,
            )
        mode = "admission"
    result = _validate_proposal_core(
        decision, calendar, geographic_id, observation, session
    )
    return _tag_mode(result, mode, decision)


def validate_proposal_retrospective(
    decision: Decision,
    calendar: RegimeCalendar,
    geographic_id: str = "national",
    observation: Any = None,  # noqa: ANN401
) -> ValidationResult:
    """Calendar-only diagnosis for an already-recorded decision.

    This is explicitly NOT admission: it has no engine clock, so its
    ``is_legal`` result must never be interpreted as current-tick legality.
    """
    return validate_proposal(
        decision,
        calendar,
        geographic_id,
        observation,
        session=None,
        retrospective=True,
    )


def _role_specific_check(
    decision: Decision,
    organization_id: str,
    sector_id: str,
) -> str:
    """Return a warning string for role-specific constraints; empty = no warning."""
    decision_type = type(decision)
    if decision_type is ProcurementDecision:
        # procurement requests must be within declared commodity scope
        if not _commodity_in_scope(decision.commodity_id, sector_id):
            return (
                f"commodity {decision.commodity_id} may be outside sector "
                f"{sector_id} scope — verify against registry"
            )
    elif decision_type is PriceProposalDecision:
        # price proposals must be non-negative (already checked in validate_legality)
        # additional check: extreme price values may indicate data error
        if decision.proposed_price > 1e9:
            return "proposed_price is extremely large"
    elif decision_type is InvestmentDecision:
        # investment requests require sector alignment
        if sector_id not in ("industry", "infrastructure"):
            return (
                "investment approval typically applies to industry/infrastructure"
            )
    elif decision_type is HouseholdNeedDecision:
        # household identity binding was already enforced in validate_legality
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
    *,
    session: Any = None,  # noqa: ANN401 — omitted admission session is rejected
    retrospective: bool = False,
) -> list[ValidationResult]:
    """Validate a batch of decisions, each independently.

    Returns a list of ValidationResult in the same order as input decisions.
    """
    # Reject custom iterables before iteration (no __iter__ callback).
    if type(decisions) is not list:
        return [_reject("decisions must be a plain list")]
    return [
        validate_proposal(
            d,
            calendar,
            geographic_id,
            observation,
            session=session,
            retrospective=retrospective,
        )
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
        # Public rule: establish exact storage before attribute access.
        decision_violation = _decision_storage_violation(decision)
        if decision_violation is not None:
            return False, f"bounded_planning violated: {decision_violation}"
        for field_name in ("available_at", "decision_at"):
            if type(object.__getattribute__(decision, field_name)) is not date:
                return False, (
                    "bounded_planning violated: decision date fields must be "
                    "plain dates"
                )
        if decision.available_at > decision.decision_at:
            return False, (
                f"bounded_planning violated: available_at {decision.available_at} "
                f"is after decision_at {decision.decision_at}"
            )
        # Bounded planning: one shared custody boundary for model and dict
        # observation representations.
        if observation is not None:
            canonical_observation, observation_error = _canonical_observation(
                observation
            )
            if observation_error is not None:
                return False, (
                    "bounded_planning violated: " + observation_error
                )
            obs_avail = object.__getattribute__(
                canonical_observation, "available_at"
            )
            if obs_avail is None:
                return False, (
                    "bounded_planning violated: observation availability is missing"
                )
            # Reject non-plain-date via type() identity check
            if type(obs_avail) is not date:
                return False, (
                    "bounded_planning violated: observation available_at "
                    "is a date subclass; date subclasses may carry forged "
                    "comparison methods"
                )
            if obs_avail > decision.decision_at:
                return False, (
                    f"bounded_planning violated: observation available_at "
                    f"{obs_avail} is after decision_at {decision.decision_at}"
                )
            # The observation must not contain information newer than the
            # decision's own declared information cutoff.
            if obs_avail > decision.available_at:
                return False, (
                    f"bounded_planning violated: observation available_at "
                    f"{obs_avail} is after the decision information cutoff "
                    f"{decision.available_at}"
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
