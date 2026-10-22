"""Read-only household expectation adapter for the H5C M1 matched experiment.

The adapter only *reads* :class:`MaterialState` and returns independent
JSON-safe copies.  It never calls the expectation updater, never writes state and
never returns an ndarray alias, so measurement cannot feed back into the
experiment.  Axes come from the state/household catalog; values are not filled,
clipped or repaired.
"""

from __future__ import annotations

import numpy as np

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.households import HouseholdCatalog
from hsm_lab.engine.state import MaterialState

SCHEMA_VERSION = "hist_vnext_h5c_m01_read_expectations_v1"


def _numeric(name: str, value: np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    array = np.asarray(value)
    if array.shape != shape:
        raise ConfigError(f"{name} shape {array.shape} != expected {shape}")
    if array.dtype.kind not in "iuf":
        raise ConfigError(f"{name} dtype {array.dtype} is not numeric")
    out = np.array(array, dtype=np.float64, copy=True)
    if not np.all(np.isfinite(out)):
        raise ConfigError(f"{name} contains non-finite values")
    return out


def read_expectations(state: MaterialState, catalog: HouseholdCatalog) -> dict[str, object]:
    """Return independent JSON-safe copies of the household memory state.

    Axes are named ``household``, ``entitlement`` and ``channel``.  Household
    ids come from the state; entitlement and channel labels come from the
    compiled catalog, so a mismatched state/catalog pair is rejected instead of
    being silently relabelled.
    """
    household_id = np.asarray(state.household_id, dtype=np.int64)
    n = int(household_id.shape[0])
    e = len(catalog.entitlement_ids)
    h = len(catalog.household_good_ids)

    expectation = _numeric("household_expectation", state.household_expectation, (n, e))
    entitlement = _numeric("household_entitlement", state.household_entitlement, (n, e))
    streak_raw = np.asarray(state.household_improvement_streak)
    streak = _numeric("household_improvement_streak", streak_raw, (n, e))
    if np.any(streak < 0.0):
        raise ConfigError("household_improvement_streak contains a negative value")
    if not np.all(streak == np.floor(streak)):
        raise ConfigError("household_improvement_streak must be integral")
    reference = _numeric(
        "household_consumption_reference", state.household_consumption_reference, (n, h)
    )
    grievance = _numeric("household_grievance", state.household_grievance, (n,))
    compliance = _numeric(
        "household_political_compliance", state.household_political_compliance, (n,)
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "axes": {
            "household": [int(value) for value in household_id],
            "entitlement": list(catalog.entitlement_ids),
            "channel": list(catalog.household_good_ids),
        },
        "expectation": expectation.tolist(),
        "entitlement": entitlement.tolist(),
        "improvement_streak": [[int(value) for value in row] for row in streak.tolist()],
        "consumption_reference": reference.tolist(),
        "grievance": grievance.tolist(),
        "compliance": compliance.tolist(),
        "summary": {
            "expectation_real_consumption_mean": float(
                np.mean(expectation[:, list(catalog.entitlement_ids).index("real_consumption")])
            ),
            "improvement_streak_real_consumption_max": int(
                np.max(streak[:, list(catalog.entitlement_ids).index("real_consumption")])
            ),
            "consumption_reference_total": float(np.sum(reference)),
            "grievance_weighted_mean": float(
                np.average(grievance, weights=np.asarray(state.household_weight, dtype=np.float64))
            ),
            "compliance_weighted_mean": float(
                np.average(compliance, weights=np.asarray(state.household_weight, dtype=np.float64))
            ),
        },
    }


__all__ = ["SCHEMA_VERSION", "read_expectations"]
