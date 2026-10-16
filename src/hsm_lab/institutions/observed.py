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

_ROLE_WHITELISTS: dict[str, frozenset[str]] = {
    "procurement_organization": _PROCUREMENT_ORG_WHITELIST,
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
        # Enforce available_at <= decision_at
        if self.available_at > self.decision_at:
            raise ValueError(
                f"available_at {self.available_at} cannot be after "
                f"decision_at {self.decision_at}"
            )
        # Reject date subclasses that may carry mutable state
        for field_name in ("decision_at", "available_at"):
            value = getattr(self, field_name)
            if type(value) is not date:
                raise TypeError(
                    f"{field_name} must be a plain date, not {type(value).__name__}; "
                    f"date subclasses may carry mutable state"
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
        # Enforce all values are deep-immutable
        for name, value in self.observed_fields:
            if not _is_deep_immutable(value):
                raise TypeError(
                    f"Value for field {name!r} is not deep-immutable: "
                    f"type={type(value).__name__}"
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
        if available_at > decision_at:
            raise ValueError(
                f"available_at {available_at} cannot be after decision_at {decision_at}"
            )

        # Filter to whitelist, deep-immutable conversion
        filtered: list[tuple[str, Any]] = []
        for field_name, value in raw_data.items():
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
    """Recursively check for prohibited keys; raise TypeError if found."""
    t = type(value)
    if t is dict:
        for k, v in value.items():
            key_str = str(k).lower()
            for prohibited in _PROHIBITED_KEYS:
                if prohibited in key_str:
                    raise TypeError(
                        f"Prohibited key {k!r} (contains '{prohibited}') "
                        f"found in observation at {path}"
                    )
            _check_no_prohibited_keys(v, path=f"{path}.{k}")
    elif t is tuple:
        for i, v in enumerate(value):
            if isinstance(v, (tuple, dict)):
                _check_no_prohibited_keys(v, path=f"{path}[{i}]")
    elif t is list:
        for i, v in enumerate(value):
            if isinstance(v, (tuple, dict)):
                _check_no_prohibited_keys(v, path=f"{path}[{i}]")
    elif t is frozenset:
        for v in value:
            if isinstance(v, (tuple, dict)):
                _check_no_prohibited_keys(v, path=f"{path}[]")


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

    if obs.available_at > obs.decision_at:
        violations.append(
            f"available_at {obs.available_at} > decision_at {obs.decision_at}"
        )

    # Check date types are plain (not subclasses with mutable state)
    for field_name in ("decision_at", "available_at"):
        value = getattr(obs, field_name)
        if type(value) is not date:
            violations.append(
                f"{field_name} must be plain date, not {type(value).__name__}"
            )

    expected_whitelist = _ROLE_WHITELISTS.get(obs.actor_role, frozenset())
    if obs.actor_role not in _ROLE_WHITELISTS:
        violations.append(f"actor_role {obs.actor_role!r} not in registered roles")

    for name, _ in obs.observed_fields:
        if name not in expected_whitelist:
            violations.append(f"Field '{name}' not in whitelist for role {obs.actor_role}")

    # Check for prohibited names in field names
    for name, _ in obs.observed_fields:
        for p in _PROHIBITED_KEYS:
            if p in name.lower():
                violations.append(f"Prohibited name '{p}' found in field '{name}'")

    # Verify deep immutability of values and check for prohibited nested keys
    for name, value in obs.observed_fields:
        if not _is_deep_immutable(value):
            violations.append(
                f"Value for '{name}' is not deep-immutable: {type(value).__name__}"
            )
        # Check for prohibited keys in nested containers
        if isinstance(value, (tuple, dict)):
            try:
                _check_no_prohibited_keys(value)
            except TypeError as exc:
                violations.append(f"Prohibited content in '{name}': {exc}")

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


def _dict_has_prohibited_keys(value: dict[Any, Any]) -> bool:
    """Return True if any key in the dict or its nested values is prohibited."""
    for k, v in value.items():
        key_str = str(k).lower()
        if any(p in key_str for p in _PROHIBITED_KEYS):
            return True
        t = type(v)
        if t is dict:
            if _dict_has_prohibited_keys(v):
                return True
        elif t is tuple:
            for elem in v:
                if isinstance(elem, dict) and _dict_has_prohibited_keys(elem):
                    return True
        elif t is list:
            for elem in v:
                if isinstance(elem, dict) and _dict_has_prohibited_keys(elem):
                    return True
    return False
