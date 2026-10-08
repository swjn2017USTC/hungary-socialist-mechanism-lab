"""P04 political runtime state: typed arrays, spec-driven serialization, digest.

The political layer owns a compact, flat set of numpy arrays (coalition weights,
policy, information capability/dimensions, county opposition capacity, four
per-household attitude arrays, the broadcast signal state, the enterprise
reporting rings and the state-observation rings).  Every array is declared once
in :data:`_POLITICAL_ARRAY_SPEC`, so no political state can silently escape the
checkpoint or the canonical digest.

``canonical_political_bytes`` mirrors
:func:`hsm_lab.engine.material.canonical_material_bytes`: audit-only labels
(mode, policy source, intervention provenance, run ids) never enter the
behavior digest.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, fields

import numpy as np

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.politics import (
    SIGNAL_CHANNELS,
    F,
    I,
    J,
    PolicyVector,
    U,
    V,
    W,
)
from hsm_lab.provenance.manifest import canonical_json

POLITICAL_STATE_VERSION = "political-state-v1"
POLITICAL_ENGINE_VERSION = "political-engine-v1"
POLITICAL_RING_LENGTH = 9
POLITICAL_PARAMETER_PREFIX = "p04."

_C = len(SIGNAL_CHANNELS)

#: name -> (dtype, axes) where axes are resolved by :func:`resolve_political_axes`.
_POLITICAL_ARRAY_SPEC: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("coalition_weights", "<f8", ("W",)),
    ("policy", "<f8", ("U",)),
    ("elite_cohesion", "<f8", ("ONE",)),
    ("information_capability", "<f8", ("ONE",)),
    ("information_dimensions", "<f8", ("I",)),
    ("soviet_constraint_multiplier", "<f8", ("ONE",)),
    ("objective_weights", "<f8", ("J",)),
    ("signals", "<f8", ("C",)),
    ("opposition", "<f8", ("R", "V")),
    ("household_identification", "<f8", ("N",)),
    ("household_exposure", "<f8", ("N",)),
    ("household_efficacy", "<f8", ("N",)),
    ("household_action", "<f8", ("N",)),
    ("state_truth", "<f8", ("L", "F")),
    ("state_noise", "<f8", ("L", "F")),
    ("state_bias", "<f8", ("L", "F")),
    ("state_reported", "<f8", ("L", "F")),
    ("state_published", "<f8", ("L", "F")),
    ("state_clip_delta", "<f8", ("L", "F")),
    ("state_valid", "<i8", ("L", "F")),
    ("state_report_quarters", "<i8", ("L",)),
    ("state_report_valid", "<i8", ("L",)),
    ("prediction_history", "<f8", ("L", "J")),
    ("objective_history", "<f8", ("L", "J")),
    ("policy_error", "<f8", ("ONE",)),
    ("publication_cursor", "<i8", ("ONE",)),
    ("last_output_value", "<f8", ("ONE",)),
    ("planner_inventory_estimate", "<f8", ("O", "G")),
    ("planner_capacity_forecast", "<f8", ("O",)),
    ("enterprise_inventory_history", "<f8", ("L", "O", "G")),
    ("enterprise_need_history", "<f8", ("L", "O", "G")),
    (
        "enterprise_capacity_history",
        "<f8",
        (
            "L",
            "O",
        ),
    ),
    ("report_normalization", "<f8", ("THREE",)),
    ("intervention_ttl", "<i8", ("K",)),
)

_POLITICAL_NON_NEGATIVE = frozenset(
    {
        "coalition_weights",
        "policy",
        "elite_cohesion",
        "information_capability",
        "information_dimensions",
        "soviet_constraint_multiplier",
        "objective_weights",
        "opposition",
        "household_identification",
        "household_exposure",
        "household_efficacy",
        "household_action",
        "planner_inventory_estimate",
        "planner_capacity_forecast",
        "report_normalization",
        "state_report_quarters",
        "intervention_ttl",
    }
)
_POLITICAL_UNIT_RANGE = frozenset(
    {
        "elite_cohesion",
        "information_capability",
        "information_dimensions",
        "opposition",
        "household_identification",
        "household_exposure",
        "household_efficacy",
        "household_action",
    }
)


@dataclass
class PoliticalState:
    """Mutable P04 political state at an end-of-quarter boundary."""

    schema_version: str
    coalition_weights: np.ndarray  # (W,)
    policy: np.ndarray  # (U,)
    elite_cohesion: np.ndarray  # (1,)
    information_capability: np.ndarray  # (1,)
    information_dimensions: np.ndarray  # (I,)
    soviet_constraint_multiplier: np.ndarray  # (1,)
    objective_weights: np.ndarray  # (J,)
    signals: np.ndarray  # (C,)
    opposition: np.ndarray  # (R, V)
    household_identification: np.ndarray  # (N,)
    household_exposure: np.ndarray  # (N,)
    household_efficacy: np.ndarray  # (N,)
    household_action: np.ndarray  # (N,)
    state_truth: np.ndarray  # (L, F)
    state_noise: np.ndarray  # (L, F)
    state_bias: np.ndarray  # (L, F)
    state_reported: np.ndarray  # (L, F)
    state_published: np.ndarray  # (L, F)
    state_clip_delta: np.ndarray  # (L, F)
    state_valid: np.ndarray  # (L, F) int8
    state_report_quarters: np.ndarray  # (L,) int64 (-1 = empty slot)
    state_report_valid: np.ndarray  # (L,) int64
    prediction_history: np.ndarray  # (L, J)
    objective_history: np.ndarray  # (L, J)
    policy_error: np.ndarray  # (1,)
    publication_cursor: np.ndarray  # (1,) int64 (-1 = no published source yet)
    last_output_value: np.ndarray  # (1,)
    planner_inventory_estimate: np.ndarray  # (O, G)
    planner_capacity_forecast: np.ndarray  # (O,)
    enterprise_inventory_history: np.ndarray  # (L, O, G)
    enterprise_need_history: np.ndarray  # (L, O, G)
    enterprise_capacity_history: np.ndarray  # (L, O)
    report_normalization: np.ndarray  # (3,)
    intervention_ttl: np.ndarray  # (K,) remaining TTL per branch broadcast

    def copy_dynamic(self) -> PoliticalState:
        clone = PoliticalState(**{f.name: getattr(self, f.name) for f in fields(self)})
        for f in fields(self):
            value = getattr(clone, f.name)
            if isinstance(value, np.ndarray):
                setattr(clone, f.name, value.copy())
        return clone


def flag(name: str) -> int:
    return SIGNAL_CHANNELS.index(name)


def resolve_political_axes(
    *, households: int, regions: int, organizations: int, commodities: int, interventions: int
) -> dict[str, int]:
    return {
        "W": W,
        "U": U,
        "I": I,
        "V": V,
        "J": J,
        "F": F,
        "C": _C,
        "L": POLITICAL_RING_LENGTH,
        "THREE": 3,
        "ONE": 1,
        "N": int(households),
        "R": int(regions),
        "O": int(organizations),
        "G": int(commodities),
        "K": int(interventions),
    }


def political_shapes(state: PoliticalState) -> dict[str, tuple[str, ...]]:
    return {name: axes for name, _dtype, axes in _POLITICAL_ARRAY_SPEC}


def political_arrays(state: PoliticalState, axes: dict[str, int]) -> dict[str, np.ndarray]:
    """Every political array, validated against the declared spec."""
    walked = {f.name for f in fields(state) if isinstance(getattr(state, f.name), np.ndarray)}
    expected = {name for name, _d, _a in _POLITICAL_ARRAY_SPEC}
    if walked != expected:
        raise ConfigError(
            f"political state field-spec drift: {sorted(walked ^ expected)}; update the "
            "shared spec deliberately (no silent state escape)"
        )
    arrays: dict[str, np.ndarray] = {}
    for name, dtype, axis_names in _POLITICAL_ARRAY_SPEC:
        array = np.ascontiguousarray(getattr(state, name))
        if array.dtype != np.dtype(dtype):
            raise ConfigError(f"political array {name} has dtype {array.dtype}, expected {dtype}")
        # The intervention-TTL axis length is branch-defined (may be 0); it is
        # read from the stored array rather than the run's declared axes.
        resolved = tuple(
            array.shape[index] if axis == "K" else axes[axis]
            for index, axis in enumerate(axis_names)
        )
        if tuple(array.shape) != resolved:
            raise ConfigError(
                f"political array {name} has shape {array.shape}, expected {resolved}"
            )
        arrays[name] = array
    return arrays


def state_from_political_arrays(
    arrays: dict[str, np.ndarray], axes: dict[str, int]
) -> PoliticalState:
    expected = {name for name, _d, _a in _POLITICAL_ARRAY_SPEC}
    if set(arrays) != expected:
        raise ConfigError(f"political payload field set mismatch: {sorted(set(arrays) ^ expected)}")
    for name, dtype, axis_names in _POLITICAL_ARRAY_SPEC:
        array = np.asarray(arrays[name])
        if array.dtype != np.dtype(dtype):
            raise ConfigError(f"political array {name} has dtype {array.dtype}, expected {dtype}")
        resolved = tuple(
            array.shape[index] if axis == "K" else axes[axis]
            for index, axis in enumerate(axis_names)
        )
        if tuple(array.shape) != resolved:
            raise ConfigError(
                f"political array {name} has shape {array.shape}, expected {resolved}"
            )
    return PoliticalState(schema_version=POLITICAL_STATE_VERSION, **arrays)


def _block(field: str, array: np.ndarray) -> bytes:
    dtype = np.dtype(array.dtype.newbyteorder("<"))
    contiguous = np.ascontiguousarray(array, dtype=dtype)
    header = canonical_json(
        {
            "field": field,
            "shape": list(contiguous.shape),
            "dtype": contiguous.dtype.str,
            "byte_length": int(contiguous.nbytes),
        }
    )
    return struct.pack("<Q", len(header)) + header + contiguous.tobytes()


def canonical_political_bytes(state: PoliticalState) -> bytes:
    """Deterministic bytes over every political state array (no audit labels)."""
    chunks: list[bytes] = []
    for name, _dtype, _axes in _POLITICAL_ARRAY_SPEC:
        chunks.append(_block(name, np.asarray(getattr(state, name))))
    return b"".join(chunks)


def canonical_political_hash(state: PoliticalState) -> str:
    return hashlib.sha256(canonical_political_bytes(state)).hexdigest()


def _feature_index_lookup() -> dict[str, int]:
    from hsm_lab.contract.politics import POLITICAL_FEATURE_IDS

    return {name: index for index, name in enumerate(POLITICAL_FEATURE_IDS)}


def initial_political_state(
    *,
    households: int,
    regions: int,
    organizations: int,
    commodities: int,
    interventions: int,
    coalition_weights: np.ndarray,
    policy: PolicyVector,
    elite_cohesion: float,
    information_capability: float,
    information_dimensions: np.ndarray,
    objective_weights: np.ndarray,
    opposition_initial: np.ndarray,
    household_initial_ideology: np.ndarray,
    household_initial_exposure: np.ndarray,
    household_initial_efficacy: np.ndarray,
    report_normalization: np.ndarray,
) -> PoliticalState:
    """Build the declared initial political state (grade-S structural recipe)."""
    L = POLITICAL_RING_LENGTH
    return PoliticalState(
        schema_version=POLITICAL_STATE_VERSION,
        coalition_weights=np.asarray(coalition_weights, dtype=np.float64),
        policy=policy.to_vector(),
        elite_cohesion=np.array([float(elite_cohesion)], dtype=np.float64),
        information_capability=np.array([float(information_capability)], dtype=np.float64),
        information_dimensions=np.asarray(information_dimensions, dtype=np.float64),
        soviet_constraint_multiplier=np.ones(1, dtype=np.float64),
        objective_weights=np.asarray(objective_weights, dtype=np.float64),
        signals=np.zeros(_C, dtype=np.float64),
        opposition=np.asarray(opposition_initial, dtype=np.float64),
        household_identification=np.asarray(household_initial_ideology, dtype=np.float64),
        household_exposure=np.asarray(household_initial_exposure, dtype=np.float64),
        household_efficacy=np.asarray(household_initial_efficacy, dtype=np.float64),
        household_action=np.zeros(households, dtype=np.float64),
        state_truth=np.zeros((L, F), dtype=np.float64),
        state_noise=np.zeros((L, F), dtype=np.float64),
        state_bias=np.zeros((L, F), dtype=np.float64),
        state_reported=np.zeros((L, F), dtype=np.float64),
        state_published=np.zeros((L, F), dtype=np.float64),
        state_clip_delta=np.zeros((L, F), dtype=np.float64),
        state_valid=np.zeros((L, F), dtype=np.int64),
        state_report_quarters=np.full(L, -1, dtype=np.int64),
        state_report_valid=np.zeros(L, dtype=np.int64),
        prediction_history=np.zeros((L, J), dtype=np.float64),
        objective_history=np.zeros((L, J), dtype=np.float64),
        policy_error=np.zeros(1, dtype=np.float64),
        publication_cursor=np.full(1, -1, dtype=np.int64),
        last_output_value=np.zeros(1, dtype=np.float64),
        planner_inventory_estimate=np.zeros((organizations, commodities), dtype=np.float64),
        planner_capacity_forecast=np.zeros(organizations, dtype=np.float64),
        enterprise_inventory_history=np.zeros((L, organizations, commodities), dtype=np.float64),
        enterprise_need_history=np.zeros((L, organizations, commodities), dtype=np.float64),
        enterprise_capacity_history=np.zeros((L, organizations), dtype=np.float64),
        report_normalization=np.asarray(report_normalization, dtype=np.float64),
        intervention_ttl=np.zeros(int(interventions), dtype=np.int64),
    )


__all__ = [
    "POLITICAL_ENGINE_VERSION",
    "POLITICAL_RING_LENGTH",
    "POLITICAL_STATE_VERSION",
    "PoliticalState",
    "canonical_political_bytes",
    "canonical_political_hash",
    "flag",
    "initial_political_state",
    "political_arrays",
    "political_shapes",
    "resolve_political_axes",
    "state_from_political_arrays",
]
