"""H2A §1 & §4: actor observations — whitelist, available_at, deep immutable.

Each actor sees a filtered, immutable view of information that was available
at their decision date.  No future information, no raw_truth, no session
references, no callbacks, and no mutable aliases.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from hsm_lab.contract.base import StrictModel

# ---------------------------------------------------------------------------
# Field whitelist per role
# ---------------------------------------------------------------------------

# Each role sees only these field names in its observation.
# Field names here are structural keys, not raw truth keys.
_PROCUREMENT_ORG_WHITELIST: frozenset[str] = frozenset({
    "quarter",
    "supply_quantity",
    "demand_quantity",
    "administered_price",
    "inventory_level",
    "capacity_utilization",
    "shortage_indicator",
})

_APPROVER_WHITELIST: frozenset[str] = frozenset({
    "quarter",
    "requested_quantity",
    "approved_quantity",
    "price_level",
    "budget_available",
    "priority_score",
})

_HOUSEHOLD_RECEIVER_WHITELIST: frozenset[str] = frozenset({
    "quarter",
    "household_id",
    "income_level",
    "consumption_quantity",
    "unmet_need_quantity",
    "ration_quota",
    "access_score",
})

_INVESTMENT_ORG_WHITELIST: frozenset[str] = frozenset({
    "project_id", "requested_amount", "approved_amount", "allocation_quota",
})

_ROLE_WHITELISTS: dict[str, frozenset[str]] = {
    "procurement_organization": _PROCUREMENT_ORG_WHITELIST,
    "investment_organization": _INVESTMENT_ORG_WHITELIST,
    "approver": _APPROVER_WHITELIST,
    "household_receiver": _HOUSEHOLD_RECEIVER_WHITELIST,
}


# ---------------------------------------------------------------------------
# Observation container (frozen, no mutable aliases)
# ---------------------------------------------------------------------------


class ActorObservation(StrictModel):
    """A deep-immutable observation for one actor at one decision point.

    Only contains fields whitelisted for the actor's role.
    Every value is a tuple (immutable) or primitive — no dict/list/callback/closure.

    The ``available_at`` field records the information cutoff date.
    The ``decision_at`` field records when the decision is made.
    Constraint: ``available_at`` must be <= ``decision_at``.
    """

    model_config = {"frozen": True, "extra": "forbid"}

    actor_role: str
    organization_id: str
    sector_id: str
    geographic_id: str
    quarter: str
    decision_at: date
    available_at: date
    # All observed values are tuples (immutable) or primitives
    observed_fields: tuple[tuple[str, Any], ...]  # (field_name, value) pairs

    def __init__(self, **data):
        super().__init__(**data)
        # Reject date subclasses BEFORE comparison to prevent __gt__ callback execution
        for field_name in ("decision_at", "available_at"):
            value = getattr(self, field_name)
            if type(value) is not date:
                raise TypeError(
                    f"{field_name} must be a plain date, not {type(value).__name__}; "
                    f"date subclasses may carry mutable state"
                )
        # Enforce available_at <= decision_at (after type validation)
        if self.available_at > self.decision_at:
            raise ValueError(
                f"available_at {self.available_at} cannot be after "
                f"decision_at {self.decision_at}"
            )
        # Enforce actor_role is registered
        if self.actor_role not in _ROLE_WHITELISTS:
            raise ValueError(
                f"actor_role {self.actor_role!r} is not a registered role; "
                f"allowed: {list(_ROLE_WHITELISTS.keys())}"
            )
        # Enforce all field names are in the role whitelist
        role_whitelist = _ROLE_WHITELISTS[self.actor_role]
        for name, _ in self.observed_fields:
            if name not in role_whitelist:
                raise ValueError(
                    f"Field {name!r} is not in the whitelist for role "
                    f"{self.actor_role!r}; allowed: {sorted(role_whitelist)}"
                )
        # Enforce all values are deep-immutable and contain no prohibited keys
        for name, value in self.observed_fields:
            if not _is_deep_immutable(value):
                raise TypeError(
                    f"Value for field {name!r} is not deep-immutable: "
                    f"type={type(value).__name__}"
                )
            if _value_has_prohibited_keys(value):
                raise TypeError(
                    f"Value for field {name!r} contains a prohibited key"
                )

    def get_field(self, field_name: str) -> Any:
        """Return the value for a whitelisted field, or raise KeyError."""
        for name, value in self.observed_fields:
            if name == field_name:
                return value
        raise KeyError(f"Field '{field_name}' not in observation for role {self.actor_role}")

    def has_field(self, field_name: str) -> bool:
        """Return True if the field is present in the observation."""
        return any(name == field_name for name, _ in self.observed_fields)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict for serialization (no references to runtime objects)."""
        return {
            "actor_role": self.actor_role,
            "organization_id": self.organization_id,
            "sector_id": self.sector_id,
            "geographic_id": self.geographic_id,
            "quarter": self.quarter,
            "decision_at": self.decision_at.isoformat(),
            "available_at": self.available_at.isoformat(),
            "observed_fields": {k: v for k, v in self.observed_fields},
        }


# ---------------------------------------------------------------------------
# Builder — constructs observations from raw data
# ---------------------------------------------------------------------------


class ObservationBuilder:
    """Build ActorObservation objects with whitelist filtering and deep immutability.

    No callbacks, no closures, no session references, no raw_truth exposure.
    All container values are converted to tuples.
    """

    def __init__(self, actor_role: str):
        if actor_role not in _ROLE_WHITELISTS:
            raise ValueError(f"Unknown actor role: {actor_role}")
        self.actor_role = actor_role
        self._whitelist = _ROLE_WHITELISTS[actor_role]

    def build(
        self,
        *,
        organization_id: str,
        sector_id: str,
        geographic_id: str,
        quarter: str,
        decision_at: date,
        available_at: date,
        raw_data: dict[str, Any],
    ) -> ActorObservation:
        """Build a filtered, deep-immutable observation from raw data.

        Parameters
        ----------
        raw_data:
            A flat dict of field_name -> value.  May contain fields NOT in the
            whitelist; those are silently dropped.

        Returns
        -------
        ActorObservation
            Frozen object with only whitelisted fields, all values deep-immutable.

        Raises
        ------
        ValueError
            If available_at > decision_at.
        """
        # Validate date types BEFORE comparison to prevent subclass __gt__ callback execution
        if type(available_at) is not date:
            raise TypeError(
                f"available_at must be a plain date, got {type(available_at).__name__}; "
                f"date subclasses may carry forged comparison methods"
            )
        if type(decision_at) is not date:
            raise TypeError(
                f"decision_at must be a plain date, got {type(decision_at).__name__}; "
                f"date subclasses may carry forged comparison methods"
            )
        if available_at > decision_at:
            raise ValueError(
                f"available_at {available_at} cannot be after decision_at {decision_at}"
            )

        # Reject dict subclasses: arbitrary dict subclasses can execute callbacks
        # through overridden methods (keys, __getitem__, etc.)
        if type(raw_data) is not dict:
            raise TypeError(
                f"raw_data must be a plain dict, got {type(raw_data).__name__}; "
                f"dict subclasses may execute arbitrary callbacks"
            )

        # Filter to whitelist, deep-immutable conversion
        filtered: list[tuple[str, Any]] = []
        for field_name, value in raw_data.items():
            # Reject non-string keys: whitelist is string-keyed, non-strings can never match
            # Avoid {field_name!r} to prevent __repr__ callback on untrusted key
            if type(field_name) is not str:
                raise TypeError(
                    f"raw_data key type is {type(field_name).__name__}, not str; "
                    f"non-string keys cannot match the string whitelist"
                )
            # Reject prohibited top-level keys immediately (before whitelist filter)
            # Use str.lower() builtin to bypass str-subclass .lower() override
            fn_lower = str.lower(field_name)
            for prohibited in _PROHIBITED_KEYS:
                if prohibited in fn_lower:
                    raise TypeError(
                        f"Prohibited key {field_name!r} (contains '{prohibited}') "
                        f"found in raw_data; not allowed at any nesting level"
                    )
            if field_name not in self._whitelist:
                continue
            immutable_value = _to_immutable(value)
            filtered.append((field_name, immutable_value))

        # Sort for deterministic output
        filtered.sort(key=lambda x: x[0])

        return ActorObservation(
            actor_role=self.actor_role,
            organization_id=organization_id,
            sector_id=sector_id,
            geographic_id=geographic_id,
            quarter=quarter,
            decision_at=decision_at,
            available_at=available_at,
            observed_fields=tuple(filtered),
        )

    def available_fields(self) -> frozenset[str]:
        """Return the whitelist of field names for this role."""
        return self._whitelist


# Prohibited keys that must never appear at any nesting level
_PROHIBITED_KEYS: frozenset[str] = frozenset({
    "raw_truth", "truth", "session", "callback", "closure",
    "target", "calibration_target",
    "role",  # indicates target-role perspective — not an allowed information source
})


def _check_no_prohibited_keys(value: Any, path: str = "") -> None:
    """Recursively check for prohibited keys (case-insensitive); raise TypeError if found."""
    t = type(value)
    if t is dict:
        for k, v in value.items():
            # Guard: only call str() on keys that are exactly str type.
            # Non-string keys are rejected as a side-effect here (they would be
            # caught later by _to_immutable's non-string-key guard), but we
            # must NOT invoke str(k) on an untrusted object as that executes
            # its __str__ callback before any type check runs.
            # We also avoid {k!r} (calls __repr__) and use only type(k).__name__
            # to prevent __repr__ callbacks on untrusted key objects.
            if type(k) is not str:
                raise TypeError(
                    f"Dict key type is {type(k).__name__}, not str; "
                    f"non-string keys are not permitted in observations"
                )
            key_str = str.lower(k)  # use built-in str.lower to bypass subclass override
            for prohibited in _PROHIBITED_KEYS:
                if prohibited in key_str:
                    raise TypeError(
                        f"Prohibited key {k!r} (contains '{prohibited}') "
                        f"found in observation at {path}"
                    )
            _check_no_prohibited_keys(v, path=f"{path}.{k}")
    elif t is tuple:
        # Handle (key, value) pairs — check key, recurse into value
        for i, v in enumerate(value):
            # Use exact type checks to avoid subclass __iter__ callback execution
            if type(v) in (tuple, dict, frozenset):
                _check_no_prohibited_keys(v, path=f"{path}[{i}]")
            elif type(v) is str:
                # It's a key in a (key, value) pair — check case-insensitively
                # Use str.lower() built-in to bypass str subclass .lower() override
                v_lower = str.lower(v)
                for prohibited in _PROHIBITED_KEYS:
                    if prohibited in v_lower:
                        raise TypeError(
                            f"Prohibited key {v!r} (contains '{prohibited}') "
                            f"found in observation at {path}[{i}]"
                        )
    elif t is frozenset:
        for i, v in enumerate(value):
            if type(v) is str:
                v_lower = str.lower(v)
                for prohibited in _PROHIBITED_KEYS:
                    if prohibited in v_lower:
                        raise TypeError(
                            f"Prohibited content {v!r} (contains '{prohibited}') "
                            f"found in frozenset at {path}[{i}]"
                        )
            elif type(v) is tuple or type(v) is dict or type(v) is frozenset:
                _check_no_prohibited_keys(v, path=f"{path}[{i}]")
    elif t is list:
        for i, v in enumerate(value):
            # Use `is` comparisons to avoid tuple membership `in` which triggers __eq__
            if type(v) is tuple or type(v) is dict:
                _check_no_prohibited_keys(v, path=f"{path}[{i}]")


def _to_immutable(value: Any) -> Any:
    """Convert a value to a deep-immutable representation.

    Only the following types are accepted; all others raise TypeError:
    - None, bool, int, float, str (primitives — returned as-is)
    - tuple: recursively convert elements
    - frozenset: recursively convert elements
    - list: converted to tuple
    - dict: converted to sorted tuple of (k, v) pairs
    - set: converted to frozenset

    Rejected: callable, object with __dict__, subclasses of primitives
    carrying mutable state, or any type not in the above list.
    Prohibited keys (raw_truth, session, callback, closure, target, etc.)
    are rejected at any nesting level.
    """
    # Primitives — exact types only (not subclasses)
    if value is None or type(value) is type(None):  # noqa: E721
        return None
    if type(value) is bool:  # noqa: E721
        return value
    if type(value) is int:  # noqa: E721
        return value
    if type(value) is float:  # noqa: E721 — not subclasses
        if not (value == value):  # NaN check
            raise TypeError(f"NaN is not allowed in observations: {value!r}")
        if abs(value) == float("inf"):
            raise TypeError(f"Non-finite float is not allowed: {value!r}")
        return value
    if type(value) is str:  # noqa: E721
        return value
    # Container types
    if type(value) is tuple:
        return tuple(_to_immutable(v) for v in value)
    if type(value) is frozenset:
        return frozenset(_to_immutable(v) for v in value)
    if type(value) is list:
        return tuple(_to_immutable(v) for v in value)
    if type(value) is set:
        return frozenset(_to_immutable(v) for v in value)
    if type(value) is dict:
        # Reject non-string keys BEFORE str(k) conversion to prevent __str__ callbacks
        # Also avoid {k!r} (calls __repr__) — use type(k).__name__ only
        for k in value.keys():
            if type(k) is not str:
                raise TypeError(
                    f"Dict key type is {type(k).__name__}, not str; "
                    f"non-string dict keys cannot be safely converted"
                )
        # Check for prohibited keys before converting
        _check_no_prohibited_keys(value)
        return tuple(sorted(
            (str(k), _to_immutable(v)) for k, v in value.items()
        ))
    # Reject everything else: callable, object, subclassed primitive, etc.
    raise TypeError(
        f"Value of type {type(value).__name__!r} is not allowed in "
        f"observations; only primitive types and plain tuple/frozenset/dict "
        f"containers are accepted"
    )


# ---------------------------------------------------------------------------
# Verification helpers (no callbacks, no runtime state)
# ---------------------------------------------------------------------------


def verify_observation_invariants(obs: ActorObservation) -> list[str]:
    """Return a list of violation strings (empty = all invariants hold).

    Checks:
    - available_at <= decision_at
    - decision_at and available_at are plain date (not subclasses)
    - actor_role is a registered role
    - all observed field names are in the role whitelist
    - all values are deep-immutable (primitives, tuples, frozensets)
    - no prohibited keys (raw_truth, session, callback, closure, target) at any nesting level
    """
    violations: list[str] = []

    # Check date types BEFORE comparison to prevent __gt__ callback on date subclasses.
    # Use object.__getattribute__ to bypass any custom __getattribute__ on the observation.
    raw_avail = object.__getattribute__(obs, "available_at")
    raw_decision = object.__getattribute__(obs, "decision_at")
    avail_is_plain = type(raw_avail) is date
    decision_is_plain = type(raw_decision) is date
    if not avail_is_plain:
        violations.append(
            f"available_at must be plain date, not {type(raw_avail).__name__}"
        )
    if not decision_is_plain:
        violations.append(
            f"decision_at must be plain date, not {type(raw_decision).__name__}"
        )
    if avail_is_plain and decision_is_plain and raw_avail > raw_decision:
        violations.append(
            f"available_at {raw_avail} > decision_at {raw_decision}"
        )

    # Guard against str-subclass __eq__ in the 'in' check for role whitelist
    actor_role_val = object.__getattribute__(obs, "actor_role")
    if type(actor_role_val) is not str or actor_role_val not in _ROLE_WHITELISTS:
        # Avoid {actor_role_val!r} which calls __repr__ on non-string values
        violations.append(
            f"actor_role type is {type(actor_role_val).__name__} "
            f"(not registered)"
        )
        # Return early: do NOT use non-string actor_role_val for whitelist lookup
        # (would trigger __hash__/__eq__ on untrusted object)
        return violations
    expected_whitelist = _ROLE_WHITELISTS.get(actor_role_val, frozenset())

    # Check observed_fields is a tuple before unpacking — prevents __iter__ callback
    # on custom iterables smuggled as observed_fields
    if type(obs.observed_fields) is not tuple:
        violations.append(
            f"observed_fields must be exactly tuple, got {type(obs.observed_fields).__name__}"
        )
        # Cannot safely iterate; return early
        return violations

    # Check each element is a 2-tuple before unpacking — prevents __iter__ on custom elements
    for i, elem in enumerate(obs.observed_fields):
        if type(elem) is not tuple:
            violations.append(
                f"observed_fields[{i}] must be exactly tuple, got {type(elem).__name__}"
            )
            continue
        if len(elem) != 2:
            violations.append(
                f"observed_fields[{i}] must have exactly 2 elements, got {len(elem)}"
            )
            continue
        name, value = elem
        # Check name is str before any use
        if type(name) is not str:
            violations.append(
                f"observed_fields[{i}] field name must be exactly str, "
                f"got {type(name).__name__}"
            )
            continue
        if name not in expected_whitelist:
            violations.append(f"Field '{name}' not in whitelist for role {obs.actor_role}")

    # Check for prohibited names in field names
    # Use str.lower() builtin to bypass str-subclass .lower() override
    for elem in obs.observed_fields:
        if type(elem) is not tuple or len(elem) != 2:
            continue  # already reported above
        name = elem[0]
        if type(name) is not str:
            continue  # already reported above
        name_lower = str.lower(name)
        for p in _PROHIBITED_KEYS:
            if p in name_lower:
                violations.append(f"Prohibited name '{p}' found in field '{name}'")

    # Verify deep immutability of values and check for prohibited nested keys
    # Check that observed_fields itself is deep-immutable
    if not _is_deep_immutable(obs.observed_fields):
        violations.append(
            f"observed_fields is not deep-immutable: "
            f"{type(obs.observed_fields).__name__}"
        )

    # Safe single-pass iteration: check element type BEFORE unpacking
    for elem in obs.observed_fields:
        # Check element is a 2-tuple before any unpacking or method calls
        if type(elem) is not tuple:
            continue  # already reported above
        if len(elem) != 2:
            continue  # already reported above
        name, value = elem  # safe: checked type and length above
        if not _is_deep_immutable(value):
            # Use plain "field" instead of {name} to avoid __str__ on untrusted name
            # Use plain "value" instead of type(value).__name__ to avoid Meta.__getattribute__
            violations.append(
                "Value for field is not deep-immutable"
            )
        # Check string values for prohibited substrings
        # Use type() check instead of isinstance() to prevent str-subclass __str__ callback
        if type(value) is str and _value_has_prohibited_keys(value):
            # Use plain "field" to avoid Meta.__getattribute__ via type(name).__name__
            violations.append(
                "Value for field contains prohibited content"
            )
        # Check for prohibited keys in nested containers
        # Use chained `is` comparisons to avoid tuple membership `in` which triggers __eq__
        if type(value) is tuple or type(value) is dict or type(value) is frozenset:
            try:
                _check_no_prohibited_keys(value)
            except TypeError as exc:
                # Use plain "field" to avoid Meta.__getattribute__
                violations.append(
                    f"Prohibited content in field: {exc}"
                )

    return violations


def _is_deep_immutable(value: Any) -> bool:
    """Return True only for exact immutable-primitive types and plain tuple/frozenset."""
    t = type(value)
    if value is None or t is type(None):  # noqa: E721
        return True
    if t is bool:
        return True
    if t is int:
        return True
    if t is float:
        # Reject non-finite floats
        if not (value == value) or abs(value) == float("inf"):
            return False
        return True
    if t is str:
        return True
    if t is tuple:
        return all(_is_deep_immutable(v) for v in value)
    if t is frozenset:
        return all(_is_deep_immutable(v) for v in value)
    return False


def _value_has_prohibited_keys(value: Any) -> bool:
    """Return True if value contains a prohibited key string (case-insensitive)."""
    t = type(value)
    if t is str:
        val_lower = value.lower()
        for prohibited in _PROHIBITED_KEYS:
            if prohibited in val_lower:
                return True
        return False
    if t is tuple:
        for v in value:
            if _value_has_prohibited_keys(v):
                return True
        return False
    if t is frozenset:
        for v in value:
            if _value_has_prohibited_keys(v):
                return True
        return False
    if t is list:
        for v in value:
            if _value_has_prohibited_keys(v):
                return True
        return False
    if t is dict:
        for k, v in value.items():
            if type(k) is not str:
                continue  # non-string keys are not prohibited-key strings
            k_str = str.lower(k)
            for prohibited in _PROHIBITED_KEYS:
                if prohibited in k_str:
                    return True
            if _value_has_prohibited_keys(v):
                return True
        return False
    return False


def _dict_has_prohibited_keys(value: dict[Any, Any]) -> bool:
    """Return True if any key in the dict or its nested values is prohibited."""
    for k, v in value.items():
        if type(k) is not str:
            continue  # non-string keys are not prohibited-key strings
        key_str = str.lower(k)
        if any(p in key_str for p in _PROHIBITED_KEYS):
            return True
        t = type(v)
        if t is dict:
            if _dict_has_prohibited_keys(v):
                return True
        elif t is tuple:
            for elem in v:
                # Use `is` comparisons to avoid tuple membership `in` which triggers __eq__
                if type(elem) is dict and _dict_has_prohibited_keys(elem):
                    return True
        elif t is list:
            for elem in v:
                # Use `is` comparisons to avoid tuple membership `in` which triggers __eq__
                if type(elem) is dict and _dict_has_prohibited_keys(elem):
                    return True
    return False
