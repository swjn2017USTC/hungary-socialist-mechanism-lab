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
        # Exact-type gate BEFORE Pydantic processes any input.  Pydantic would
        # otherwise iterate a custom iterable passed as ``observed_fields`` or
        # coerce primitive subclasses, executing callbacks before our checks.
        # Every diagnostic below is static: never format an untrusted type.
        for key in data:
            if type(key) is not str:
                raise TypeError("observation field name must be exactly str")
        for field_name in (
            "actor_role",
            "organization_id",
            "sector_id",
            "geographic_id",
            "quarter",
        ):
            value = data.get(field_name)
            if type(value) is not str:
                raise TypeError(f"{field_name} must be exactly str")
        for field_name in ("decision_at", "available_at"):
            value = data.get(field_name)
            if type(value) is not date:
                raise TypeError(f"{field_name} must be a plain date")
        observed = data.get("observed_fields")
        if type(observed) is not tuple:
            raise TypeError("observed_fields must be exactly tuple")
        for element in observed:
            if type(element) is not tuple or len(element) != 2:
                raise TypeError("observed_fields elements must be 2-tuples")
            name = element[0]
            if type(name) is not str:
                raise TypeError("observed field name must be exactly str")
            if not _is_deep_immutable(element[1]):
                raise TypeError("observed field value is not deep-immutable")
            if _value_has_prohibited_keys(element[1]):
                raise TypeError("observed field value contains a prohibited key")
        super().__init__(**data)
        # Enforce available_at <= decision_at (types already exact)
        if self.available_at > self.decision_at:
            raise ValueError(
                f"available_at {self.available_at} cannot be after "
                f"decision_at {self.decision_at}"
            )
        # Enforce actor_role is registered (exact str membership is callback-free)
        if self.actor_role not in _ROLE_WHITELISTS:
            raise ValueError("actor_role is not a registered role; expected an H2A role")
        # Enforce all field names are in the role whitelist, unique, and
        # internally consistent.  Values passed the pre-gate, so comparisons
        # below cannot execute untrusted callbacks.
        role_whitelist = _ROLE_WHITELISTS[self.actor_role]
        seen_names: set[str] = set()
        for name, value in self.observed_fields:
            if name not in role_whitelist:
                raise ValueError(
                    "Observation field is not in the whitelist for this role"
                )
            if name in seen_names:
                raise ValueError("observed field names must be unique")
            seen_names.add(name)
            if name == "quarter" and value != self.quarter:
                raise ValueError(
                    "quarter observation field conflicts with the observation quarter"
                )
            if self.actor_role == "household_receiver" and name == "household_id":
                if value != self.organization_id:
                    raise ValueError(
                        "observed household_id must equal the observation "
                        "organization_id"
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
        # Exact-type gate: a str subclass can override __hash__/__eq__ and would
        # execute those callbacks during dict membership lookup below.
        if type(actor_role) is not str:
            raise TypeError("actor_role must be exactly str")
        if actor_role not in _ROLE_WHITELISTS:
            raise ValueError("Unknown actor role; expected a registered H2A role")
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
        # Validate exact types BEFORE any comparison.  Diagnostics are static:
        # formatting an untrusted type can execute a metaclass __getattribute__.
        if type(available_at) is not date:
            raise TypeError("available_at must be a plain date")
        if type(decision_at) is not date:
            raise TypeError("decision_at must be a plain date")
        for field_name, value in (
            ("actor_role", self.actor_role),
            ("organization_id", organization_id),
            ("sector_id", sector_id),
            ("geographic_id", geographic_id),
            ("quarter", quarter),
        ):
            if type(value) is not str:
                raise TypeError(f"{field_name} must be exactly str")
        if available_at > decision_at:
            raise ValueError(
                f"available_at {available_at} cannot be after decision_at {decision_at}"
            )

        # Reject dict subclasses: arbitrary dict subclasses can execute callbacks
        # through overridden methods (keys, __getitem__, etc.)
        if type(raw_data) is not dict:
            raise TypeError(
                "raw_data must be a plain dict; dict subclasses are rejected"
            )

        # Filter to whitelist, deep-immutable conversion
        filtered: list[tuple[str, Any]] = []
        for field_name, value in raw_data.items():
            # Reject non-string keys: whitelist is string-keyed, non-strings can never match
            # Avoid {field_name!r} to prevent __repr__ callback on untrusted key
            if type(field_name) is not str:
                raise TypeError(
                    "raw_data key must be exactly str; "
                    "non-string keys cannot match the string whitelist"
                )
            # Reject prohibited top-level keys immediately (before whitelist filter)
            # Use str.lower() builtin to bypass str-subclass .lower() override
            fn_lower = str.lower(field_name)
            for prohibited in _PROHIBITED_KEYS_ORDERED:
                if prohibited in fn_lower:
                    raise TypeError(
                        f"Prohibited key {field_name!r} (contains '{prohibited}') "
                        f"found in raw_data; not allowed at any nesting level"
                    )
            if field_name not in self._whitelist:
                continue
            if field_name == "quarter":
                # The observation owns exactly one quarter.  A duplicated
                # whitelisted quarter must not disagree with the context.
                if type(value) is not str:
                    raise TypeError("quarter observation field must be exactly str")
                if value != quarter:
                    raise ValueError(
                        "quarter observation field conflicts with the observation quarter"
                    )
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

# Deterministic, most-specific-first scan order (longest key first) so a
# message names ``raw_truth`` rather than its substring ``truth``.
_PROHIBITED_KEYS_ORDERED: tuple[str, ...] = tuple(
    sorted(_PROHIBITED_KEYS, key=len, reverse=True)
)

# Explicit nesting limit: acyclic but pathologically deep input must be
# rejected deterministically instead of exhausting the Python recursion limit.
_MAX_OBSERVATION_DEPTH = 64


def _is_container(value: Any) -> bool:
    """Identity-only container predicate (no ``__eq__`` on the value's type)."""
    t = type(value)
    return t is tuple or t is dict or t is frozenset or t is list


def _check_no_prohibited_keys(
    value: Any,
    path: str = "",
    _seen: set[int] | None = None,
    _depth: int = 0,
) -> None:
    """Recursively check for prohibited keys (case-insensitive); raise TypeError if found.

    Diagnostics are deliberately static: never format or stringify an untrusted
    object, because that can execute ``__str__``/``__repr__``/metaclass
    ``__getattribute__`` callbacks before any type check runs.
    """
    if _seen is None:
        _seen = set()
    t = type(value)
    if t is dict or t is tuple or t is frozenset or t is list:
        if _depth > _MAX_OBSERVATION_DEPTH:
            raise TypeError(
                "Observation nesting depth exceeds the supported limit"
            )
        identity = id(value)
        if identity in _seen:
            raise TypeError("Cyclic container is not allowed in observations")
        _seen.add(identity)
        try:
            if t is dict:
                for k, v in value.items():
                    if type(k) is not str:
                        raise TypeError(
                            "Dict key must be exactly str; "
                            "non-string keys are not permitted in observations"
                        )
                    key_str = str.lower(k)
                    for prohibited in _PROHIBITED_KEYS_ORDERED:
                        if prohibited in key_str:
                            raise TypeError(
                                f"Prohibited key (contains '{prohibited}') "
                                f"found in observation at {path}"
                            )
                    _check_no_prohibited_keys(
                        v, path=f"{path}.{k}", _seen=_seen, _depth=_depth + 1
                    )
            elif t is tuple:
                for i, v in enumerate(value):
                    if _is_container(v):
                        _check_no_prohibited_keys(
                            v, path=f"{path}[{i}]", _seen=_seen,
                            _depth=_depth + 1,
                        )
                    elif type(v) is str:
                        v_lower = str.lower(v)
                        for prohibited in _PROHIBITED_KEYS_ORDERED:
                            if prohibited in v_lower:
                                raise TypeError(
                                    f"Prohibited key (contains '{prohibited}') "
                                    f"found in observation at {path}[{i}]"
                                )
            elif t is frozenset:
                for i, v in enumerate(value):
                    if type(v) is str:
                        v_lower = str.lower(v)
                        for prohibited in _PROHIBITED_KEYS_ORDERED:
                            if prohibited in v_lower:
                                raise TypeError(
                                    f"Prohibited content (contains '{prohibited}') "
                                    f"found in frozenset at {path}[{i}]"
                                )
                    elif _is_container(v):
                        _check_no_prohibited_keys(
                            v, path=f"{path}[{i}]", _seen=_seen,
                            _depth=_depth + 1,
                        )
            elif t is list:
                for i, v in enumerate(value):
                    if type(v) is tuple or type(v) is dict or type(v) is list:
                        _check_no_prohibited_keys(
                            v, path=f"{path}[{i}]", _seen=_seen,
                            _depth=_depth + 1,
                        )
        finally:
            _seen.discard(identity)


def _to_immutable(
    value: Any, _seen: set[int] | None = None, _depth: int = 0
) -> Any:
    """Convert a value to a deep-immutable representation.

    Only the following types are accepted; all others raise TypeError:
    - None, bool, int, float, str (primitives — returned as-is)
    - tuple: recursively convert elements
    - frozenset: recursively convert elements
    - list: converted to tuple
    - dict: converted to sorted tuple of (k, v) pairs
    - set: converted to frozenset

    Rejected: callable, object with __dict__, subclasses of primitives
    carrying mutable state, cyclic containers, or any type not in the above
    list.  Prohibited keys (raw_truth, session, callback, closure, target,
    etc.) are rejected at any nesting level.
    """
    if _seen is None:
        _seen = set()
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
    # Container types — guard against cycles and excessive depth before recursing
    if _depth > _MAX_OBSERVATION_DEPTH:
        raise TypeError("Observation nesting depth exceeds the supported limit")
    identity = id(value)
    if identity in _seen:
        raise TypeError("Cyclic container is not allowed in observations")
    _seen.add(identity)
    try:
        if type(value) is tuple:
            return tuple(_to_immutable(v, _seen, _depth + 1) for v in value)
        if type(value) is frozenset:
            return frozenset(_to_immutable(v, _seen, _depth + 1) for v in value)
        if type(value) is list:
            return tuple(_to_immutable(v, _seen, _depth + 1) for v in value)
        if type(value) is set:
            return frozenset(_to_immutable(v, _seen, _depth + 1) for v in value)
        if type(value) is dict:
            # Reject non-string keys BEFORE str(k) conversion to prevent __str__ callbacks
            for k in value.keys():
                if type(k) is not str:
                    raise TypeError(
                        "Dict key must be exactly str; "
                        "non-string dict keys cannot be safely converted"
                    )
            # Check for prohibited keys before converting.  Use a fresh
            # cycle-tracking set: ``value`` itself is already in ``_seen``.
            _check_no_prohibited_keys(value, _depth=_depth + 1)
            return tuple(sorted(
                (str(k), _to_immutable(v, _seen, _depth + 1))
                for k, v in value.items()
            ))
    finally:
        _seen.discard(identity)
    # Reject everything else: callable, object, subclassed primitive, etc.
    # Static message: formatting an untrusted type executes a metaclass callback.
    raise TypeError(
        "Value type not allowed in observations; "
        "only None, bool, int, float, str, tuple, frozenset, list, dict, set allowed"
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

    # Reject unsupported containers before any attribute access.  The verifier
    # is a public boundary, not just an internal helper.
    if type(obs) is not ActorObservation:
        return ["verify_observation_invariants requires an exact ActorObservation"]

    # --- model metadata custody -------------------------------------------
    # ``model_construct`` can bypass every validator and inject unvalidated
    # names into ``__pydantic_fields_set__`` (readable via ``model_fields_set``)
    # or into ``__dict__``.  Structural failures return immediately: continuing
    # would access storage that has not been proven safe.
    declared = set(ActorObservation.model_fields.keys())
    try:
        extra = object.__getattribute__(obs, "__pydantic_extra__")
        private = object.__getattribute__(obs, "__pydantic_private__")
        fields_set = object.__getattribute__(obs, "__pydantic_fields_set__")
        instance = object.__getattribute__(obs, "__dict__")
    except AttributeError:
        return ["observation model storage is unavailable"]
    if extra is not None:
        return ["observation __pydantic_extra__ must be empty"]
    if private is not None:
        return ["observation __pydantic_private__ must be empty"]
    if type(fields_set) is not set:
        return ["observation model metadata is malformed"]
    for name in fields_set:
        if type(name) is not str or name not in declared:
            return ["observation model metadata contains an unvalidated field name"]
    if type(instance) is not dict:
        return ["observation model storage is malformed"]
    storage_count = 0
    for key in instance:
        # Exact-string key gate BEFORE any hashing/equality or set comparison.
        if type(key) is not str:
            return ["observation model storage has a non-exact-string key"]
        if key not in declared:
            return ["observation model storage contains an undeclared field"]
        storage_count += 1
    if storage_count != len(declared):
        return ["observation model storage is missing declared fields"]

    # Every declared context field must be an exact string; model_construct can
    # otherwise retain arbitrary mutable truth/session references.
    for field_name in (
        "actor_role",
        "organization_id",
        "sector_id",
        "geographic_id",
        "quarter",
    ):
        context_value = object.__getattribute__(obs, field_name)
        if type(context_value) is not str:
            violations.append(f"{field_name} must be exactly str")

    # Check date types BEFORE comparison to prevent __gt__ callback on date subclasses.
    raw_avail = object.__getattribute__(obs, "available_at")
    raw_decision = object.__getattribute__(obs, "decision_at")
    avail_is_plain = type(raw_avail) is date
    decision_is_plain = type(raw_decision) is date
    if not avail_is_plain:
        violations.append("available_at must be a plain date")
    if not decision_is_plain:
        violations.append("decision_at must be a plain date")
    if avail_is_plain and decision_is_plain and raw_avail > raw_decision:
        violations.append(
            f"available_at {raw_avail} > decision_at {raw_decision}"
        )

    # Guard against str-subclass __eq__ in the 'in' check for role whitelist
    actor_role_val = object.__getattribute__(obs, "actor_role")
    if type(actor_role_val) is not str or actor_role_val not in _ROLE_WHITELISTS:
        violations.append("actor_role is not an exact registered role")
        # Do NOT use a non-string actor_role for whitelist lookup
        return violations
    expected_whitelist = _ROLE_WHITELISTS.get(actor_role_val, frozenset())

    # Check observed_fields is a tuple before unpacking — prevents __iter__ callback
    # on custom iterables smuggled as observed_fields
    observed = object.__getattribute__(obs, "observed_fields")
    if type(observed) is not tuple:
        violations.append("observed_fields must be exactly tuple")
        # Cannot safely iterate; return early
        return violations

    raw_organization = object.__getattribute__(obs, "organization_id")
    organization_is_plain = type(raw_organization) is str

    # Check each element is a 2-tuple before unpacking — prevents __iter__ on custom elements
    seen_names: set[str] = set()
    for i, elem in enumerate(observed):
        if type(elem) is not tuple:
            violations.append(f"observed_fields[{i}] must be exactly tuple")
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
                f"observed_fields[{i}] field name must be exactly str"
            )
            continue
        if name in seen_names:
            violations.append("observed field names must be unique")
            continue
        seen_names.add(name)
        if name not in expected_whitelist:
            violations.append(
                f"Field '{name}' not in whitelist for role {actor_role_val}"
            )
        # Quarter duplication must agree with the observation context.
        # Type-gate the value before comparison: model_construct may smuggle
        # an object with a hostile __ne__.
        if name == "quarter":
            raw_quarter = object.__getattribute__(obs, "quarter")
            if type(value) is not str:
                violations.append("quarter observation field must be exactly str")
            elif type(raw_quarter) is not str or value != raw_quarter:
                violations.append(
                    "quarter observation field disagrees with the observation quarter"
                )
        # Household observations must present this household's own identity.
        if actor_role_val == "household_receiver" and name == "household_id":
            if type(value) is not str or not organization_is_plain:
                violations.append("household_id observation must be exactly str")
            elif value != raw_organization:
                violations.append(
                    "observed household_id must equal the observation "
                    "organization_id"
                )
        # Prohibited names in field names
        name_lower = str.lower(name)
        for p in _PROHIBITED_KEYS_ORDERED:
            if p in name_lower:
                violations.append(f"Prohibited name '{p}' found in field '{name}'")
        # Deep immutability and prohibited nested keys
        if not _is_deep_immutable(value):
            violations.append("Value for field is not deep-immutable")
        if type(value) is str and _value_has_prohibited_keys(value):
            violations.append("Value for field contains prohibited content")
        if (
            type(value) is tuple
            or type(value) is dict
            or type(value) is frozenset
            or type(value) is list
        ):
            try:
                _check_no_prohibited_keys(value)
            except TypeError as exc:
                violations.append(f"Prohibited content in field: {exc}")

    return violations


def _is_deep_immutable(
    value: Any, _seen: set[int] | None = None, _depth: int = 0
) -> bool:
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
    if t is tuple or t is frozenset:
        if _depth > _MAX_OBSERVATION_DEPTH:
            return False
        if _seen is None:
            _seen = set()
        identity = id(value)
        if identity in _seen:
            return False  # cyclic container cannot be immutable
        _seen.add(identity)
        try:
            return all(
                _is_deep_immutable(v, _seen, _depth + 1) for v in value
            )
        finally:
            _seen.discard(identity)
    return False


def _value_has_prohibited_keys(value: Any, _seen: set[int] | None = None) -> bool:
    """Return True if value contains a prohibited key string (case-insensitive)."""
    t = type(value)
    if t is str:
        val_lower = str.lower(value)
        for prohibited in _PROHIBITED_KEYS_ORDERED:
            if prohibited in val_lower:
                return True
        return False
    if t is tuple or t is frozenset or t is list or t is dict:
        if _seen is None:
            _seen = set()
        identity = id(value)
        if identity in _seen:
            return False  # cycles are rejected elsewhere
        _seen.add(identity)
        try:
            if t is dict:
                for k, v in value.items():
                    if type(k) is not str:
                        continue  # non-string keys are not prohibited-key strings
                    k_str = str.lower(k)
                    for prohibited in _PROHIBITED_KEYS_ORDERED:
                        if prohibited in k_str:
                            return True
                    if _value_has_prohibited_keys(v, _seen):
                        return True
                return False
            for v in value:
                if _value_has_prohibited_keys(v, _seen):
                    return True
            return False
        finally:
            _seen.discard(identity)
    return False
