"""P04 compact output tables: political quarters, opposition, information, decisions.

Five tables, each with a stable typed key.  They are empty typed frames for the
material-only (``politics=None``) case and for a Mode A run (no broker
candidates), and they never carry micro household panels.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from hsm_lab.contract.politics import (
    BROKER_OBJECTIVE_IDS,
    COALITION_IDS,
    INFORMATION_DIMENSION_IDS,
    OPPOSITION_AXIS_IDS,
    POLICY_COORDINATES,
    POLITICAL_FEATURE_IDS,
)
from hsm_lab.provenance.manifest import canonical_json

POLITICAL_QUARTERS = "political_quarters"
OPPOSITION_REGIONS = "opposition_regions"
INFORMATION_QUARTERS = "information_quarters"
POLICY_DECISIONS = "policy_decisions"
POLITICAL_EVENTS = "political_events"

POLITICAL_TABLES: tuple[str, ...] = (
    POLITICAL_QUARTERS,
    OPPOSITION_REGIONS,
    INFORMATION_QUARTERS,
    POLICY_DECISIONS,
    POLITICAL_EVENTS,
)

POLITICAL_QUARTER_COLUMNS: list[str] = [
    "tick",
    "quarter",
    "mode",
    "policy_source",
    *[f"weight_{name}" for name in COALITION_IDS],
    *[f"policy_{name}" for name in POLICY_COORDINATES],
    "elite_cohesion",
    "soviet_bound",
    "soviet_violation",
    "selected_candidate",
    "information_capability",
]

OPPOSITION_COLUMNS: list[str] = [
    "tick",
    "quarter",
    "region_id",
    *list(OPPOSITION_AXIS_IDS),
    "capacity",
    "weighted_grievance",
    "weighted_voice",
    "weighted_risk",
    "weighted_exposure",
]

INFORMATION_COLUMNS: list[str] = [
    "tick",
    "quarter",
    "feature_id",
    "capability",
    *list(INFORMATION_DIMENSION_IDS),
    "total_lag",
    "source_quarter",
    "truth",
    "noise",
    "bias",
    "published",
    "valid",
]

POLICY_DECISION_COLUMNS: list[str] = [
    "tick",
    "quarter",
    "candidate_id",
    "utility",
    "binding_constraints",
    "contributions_json",
]

POLITICAL_EVENT_COLUMNS: list[str] = [
    "tick",
    "quarter",
    "event_id",
    "channel",
    "message_id",
    "recipient_id",
    "source_id",
    "delivery",
    "classification",
    "attribution",
]

#: Integer-typed columns per P04 table (everything else is Float64/String).
POLITICAL_INT_COLUMNS: dict[str, set[str]] = {
    POLITICAL_QUARTERS: {"tick"},
    OPPOSITION_REGIONS: {"tick"},
    INFORMATION_QUARTERS: {"tick", "total_lag", "source_quarter"},
    POLICY_DECISIONS: {"tick"},
    POLITICAL_EVENTS: {"tick"},
}

POLITICAL_STRING_COLUMNS: dict[str, set[str]] = {
    POLITICAL_QUARTERS: {
        "quarter",
        "mode",
        "policy_source",
        "selected_candidate",
    },
    OPPOSITION_REGIONS: {"quarter", "region_id"},
    INFORMATION_QUARTERS: {"quarter", "feature_id", "source_quarter"},
    POLICY_DECISIONS: {"quarter", "candidate_id", "binding_constraints", "contributions_json"},
    POLITICAL_EVENTS: {
        "quarter",
        "event_id",
        "channel",
        "message_id",
        "recipient_id",
        "source_id",
        "delivery",
        "classification",
        "attribution",
    },
}

POLITICAL_KEYS: dict[str, list[str]] = {
    POLITICAL_QUARTERS: ["tick"],
    OPPOSITION_REGIONS: ["tick", "region_id"],
    INFORMATION_QUARTERS: ["tick", "feature_id"],
    POLICY_DECISIONS: ["tick", "candidate_id"],
    POLITICAL_EVENTS: ["tick", "event_id", "channel", "message_id", "recipient_id"],
}

POLITICAL_COLUMNS: dict[str, list[str]] = {
    POLITICAL_QUARTERS: POLITICAL_QUARTER_COLUMNS,
    OPPOSITION_REGIONS: OPPOSITION_COLUMNS,
    INFORMATION_QUARTERS: INFORMATION_COLUMNS,
    POLICY_DECISIONS: POLICY_DECISION_COLUMNS,
    POLITICAL_EVENTS: POLITICAL_EVENT_COLUMNS,
}


def political_quarter_row(
    *,
    tick: int,
    quarter: str,
    mode: str,
    policy_source: str,
    coalition_weights: np.ndarray,
    policy: np.ndarray,
    elite_cohesion: float,
    soviet_bound: bool,
    soviet_violation: float,
    selected_candidate: str,
    information_capability: float,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "tick": int(tick),
        "quarter": quarter,
        "mode": mode,
        "policy_source": policy_source,
        "elite_cohesion": float(elite_cohesion),
        "soviet_bound": 1.0 if soviet_bound else 0.0,
        "soviet_violation": float(soviet_violation),
        "selected_candidate": selected_candidate,
        "information_capability": float(information_capability),
    }
    for index, name in enumerate(COALITION_IDS):
        row[f"weight_{name}"] = float(coalition_weights[index])
    for index, name in enumerate(POLICY_COORDINATES):
        row[f"policy_{name}"] = float(policy[index])
    return row


def opposition_row(
    *,
    tick: int,
    quarter: str,
    region_id: str,
    opposition: np.ndarray,
    capacity: float,
    weighted_grievance: float,
    weighted_voice: float,
    weighted_risk: float,
    weighted_exposure: float,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "tick": int(tick),
        "quarter": quarter,
        "region_id": region_id,
        "capacity": float(capacity),
        "weighted_grievance": float(weighted_grievance),
        "weighted_voice": float(weighted_voice),
        "weighted_risk": float(weighted_risk),
        "weighted_exposure": float(weighted_exposure),
    }
    for index, axis in enumerate(OPPOSITION_AXIS_IDS):
        row[axis] = float(opposition[index])
    return row


def information_rows(
    *,
    tick: int,
    quarter: str,
    capability: float,
    dimensions: np.ndarray,
    total_lag: int,
    source_quarter: int | str,
    truth: np.ndarray,
    noise: np.ndarray,
    bias: np.ndarray,
    published: np.ndarray,
    valid: np.ndarray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, feature in enumerate(POLITICAL_FEATURE_IDS):
        row: dict[str, Any] = {
            "tick": int(tick),
            "quarter": quarter,
            "feature_id": feature,
            "capability": float(capability),
            "total_lag": int(total_lag),
            "source_quarter": str(source_quarter),
            "truth": float(truth[index]),
            "noise": float(noise[index]),
            "bias": float(bias[index]),
            "published": float(published[index]),
            "valid": 1.0 if bool(valid[index]) else 0.0,
        }
        for dim_index, dimension in enumerate(INFORMATION_DIMENSION_IDS):
            row[dimension] = float(dimensions[dim_index])
        rows.append(row)
    return rows


def policy_decision_rows(
    *,
    tick: int,
    quarter: str,
    candidate_ids: list[str],
    utilities: np.ndarray,
    binding_constraints: list[str],
    objective_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    objectives = list(objective_ids or BROKER_OBJECTIVE_IDS)
    rows: list[dict[str, Any]] = []
    for index, candidate_id in enumerate(candidate_ids):
        rows.append(
            {
                "tick": int(tick),
                "quarter": quarter,
                "candidate_id": candidate_id,
                "utility": float(utilities[index]),
                "binding_constraints": ",".join(binding_constraints),
                "contributions_json": canonical_json(objectives).decode("utf-8"),
            }
        )
    return rows


def political_event_row(
    *,
    tick: int,
    quarter: str,
    event_id: str,
    channel: str,
    message_id: str,
    recipient_id: str,
    source_id: str,
    delivery: str,
    classification: str,
    attribution: str,
) -> dict[str, Any]:
    return {
        "tick": int(tick),
        "quarter": quarter,
        "event_id": event_id,
        "channel": channel,
        "message_id": message_id,
        "recipient_id": recipient_id,
        "source_id": source_id,
        "delivery": delivery,
        "classification": classification,
        "attribution": attribution,
    }


def empty_political_frames() -> dict[str, list[dict[str, Any]]]:
    return {name: [] for name in POLITICAL_TABLES}


__all__ = [
    "INFORMATION_COLUMNS",
    "INFORMATION_QUARTERS",
    "OPPOSITION_COLUMNS",
    "OPPOSITION_REGIONS",
    "POLICY_DECISION_COLUMNS",
    "POLICY_DECISIONS",
    "POLITICAL_COLUMNS",
    "POLITICAL_EVENTS",
    "POLITICAL_EVENT_COLUMNS",
    "POLITICAL_INT_COLUMNS",
    "POLITICAL_KEYS",
    "POLITICAL_QUARTER_COLUMNS",
    "POLITICAL_QUARTERS",
    "POLITICAL_STRING_COLUMNS",
    "POLITICAL_TABLES",
    "empty_political_frames",
    "information_rows",
    "opposition_row",
    "policy_decision_rows",
    "political_event_row",
    "political_quarter_row",
]
