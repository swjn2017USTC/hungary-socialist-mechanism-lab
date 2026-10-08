"""P04 opposition kernel: county opposition-capacity formation and action propensity.

Pure numpy functions.  ``update_region_capacity`` advances one quarter of the
latent (R, V) county opposition-capacity state from domestic policy, region
signals and the immutable external world; ``action_propensity`` maps household
grievance/exposure/efficacy and the region's capacity into an unnormalized
per-household propensity.

Capacity is a *capacity index*, never a headcount: the layer carries no
event -> support constant, only the declared monotone kernel.  All array values
are in [0, 1]; there is no I/O and no RNG, so identical inputs reproduce
identical outputs bit-for-bit.

Signal sourcing: ``region_signals`` rows carry one value per ``SIGNAL_CHANNELS``
entry.  Societal channels are expected to arrive already 3T/audience-filtered;
government channels (``regime_threat``, ``repression_cost``) are not filtered
domestically, so the *caller* decides whether to broadcast the scalar external
reading into every region row.  ``external`` is accepted for call-site parity
with the other P04 kernels and is intentionally not read here.
"""

from __future__ import annotations

import numpy as np

from hsm_lab.contract.politics import (
    OPPOSITION_AXIS_IDS,
    SIGNAL_CHANNELS,
    ExternalWorldSlice,
    OppositionParameters,
    PolicyVector,
    V,
)

# Canonical axis positions (declared order of OPPOSITION_AXIS_IDS).
NETWORK_SIZE: int = OPPOSITION_AXIS_IDS.index("network_size")
INTELLECTUAL_DENSITY: int = OPPOSITION_AXIS_IDS.index("intellectual_density")
WORKER_LINKAGE: int = OPPOSITION_AXIS_IDS.index("worker_linkage")
SAMIZDAT_CAPACITY: int = OPPOSITION_AXIS_IDS.index("samizdat_capacity")
FOREIGN_LINKAGE: int = OPPOSITION_AXIS_IDS.index("foreign_linkage")
REPRESSION_EXPOSURE: int = OPPOSITION_AXIS_IDS.index("repression_exposure")
PERCEIVED_EFFICACY: int = OPPOSITION_AXIS_IDS.index("perceived_efficacy")

# Canonical signal-channel positions (declared order of SIGNAL_CHANNELS).
WESTERN_EXPOSURE_SIGNAL: int = SIGNAL_CHANNELS.index("western_comparison")
OPPOSITION_SUCCESS_SIGNAL: int = SIGNAL_CHANNELS.index("opposition_success")
PUBLIC_ACTION_RISK_SIGNAL: int = SIGNAL_CHANNELS.index("public_action_risk")
FOREIGN_LINKAGE_SIGNAL: int = SIGNAL_CHANNELS.index("foreign_linkage")
INTELLECTUAL_LINKAGE_SIGNAL: int = SIGNAL_CHANNELS.index("intellectual_linkage")
REPRESSION_COST_SIGNAL: int = SIGNAL_CHANNELS.index("repression_cost")


def _column(array: np.ndarray, index: int) -> np.ndarray:
    """Return column ``index`` of a 2-D float array as a view."""
    return array[:, index]


def update_region_capacity(
    previous: np.ndarray,
    formation_inputs: np.ndarray,
    policy: PolicyVector,
    region_signals: np.ndarray,
    external: ExternalWorldSlice,
    parameters: OppositionParameters,
) -> np.ndarray:
    """Advance the (R, V) county opposition-capacity state by one quarter.

    ``previous`` and the result are (R, V) with columns ordered exactly as
    ``OPPOSITION_AXIS_IDS``.  ``formation_inputs`` is (R, 2) holding this
    quarter's ``[intellectual_density, worker_linkage]`` from the education /
    sector margins; they are copied straight into their axes (not smoothed).
    ``region_signals`` is (R, len(SIGNAL_CHANNELS)).

    ``intellectual_density`` and ``worker_linkage`` are *not* EMA'd; every other
    axis follows ``v' = clip((1 - alpha_v) * previous_v + alpha_v * target_v)``.
    """
    prev = np.asarray(previous, dtype=np.float64)
    inputs = np.asarray(formation_inputs, dtype=np.float64)
    signals = np.asarray(region_signals, dtype=np.float64)
    if prev.ndim != 2 or prev.shape[1] != V:
        raise ValueError(f"previous must be (R, {V}), got {prev.shape}")
    if inputs.ndim != 2 or inputs.shape[1] != 2:
        raise ValueError(f"formation_inputs must be (R, 2), got {inputs.shape}")
    if inputs.shape[0] != prev.shape[0]:
        raise ValueError(
            f"formation_inputs rows {inputs.shape[0]} != previous rows {prev.shape[0]}"
        )
    if signals.ndim != 2 or signals.shape[1] != len(SIGNAL_CHANNELS):
        raise ValueError(f"region_signals must be (R, {len(SIGNAL_CHANNELS)}), got {signals.shape}")
    if signals.shape[0] != prev.shape[0]:
        raise ValueError(f"region_signals rows {signals.shape[0]} != previous rows {prev.shape[0]}")

    # This quarter's directly-set formation axes.
    intellectual = np.clip(inputs[:, 0], 0.0, 1.0)
    worker = np.clip(inputs[:, 1], 0.0, 1.0)

    prev_network = _column(prev, NETWORK_SIZE)
    prev_samizdat = _column(prev, SAMIZDAT_CAPACITY)
    prev_foreign = _column(prev, FOREIGN_LINKAGE)
    prev_repression = _column(prev, REPRESSION_EXPOSURE)
    prev_efficacy = _column(prev, PERCEIVED_EFFICACY)

    repression = float(policy.repression)
    second_tolerance = float(policy.second_economy_tolerance)

    # Per-region signal columns.
    western = signals[:, WESTERN_EXPOSURE_SIGNAL]
    success = signals[:, OPPOSITION_SUCCESS_SIGNAL]
    action_risk = signals[:, PUBLIC_ACTION_RISK_SIGNAL]
    foreign_signal = signals[:, FOREIGN_LINKAGE_SIGNAL]
    intellectual_linkage = signals[:, INTELLECTUAL_LINKAGE_SIGNAL]
    repression_cost = signals[:, REPRESSION_COST_SIGNAL]

    # Targets (each already in [0, 1]).
    network = np.clip(
        prev_network
        + parameters.formation_rate * intellectual * worker * (1.0 - repression)
        - parameters.attrition_rate * prev_repression * prev_network,
        0.0,
        1.0,
    )
    # NB: every state-dependent target reads the *frozen previous closing*
    # values, never another axis' freshly computed target (no field-order
    # cascading) -- see P04_POLITICS_EXTERNAL_PLAN.md section F.
    samizdat = np.clip(
        parameters.samizdat_tolerance_weight * second_tolerance * prev_network
        + parameters.samizdat_charter_weight * intellectual_linkage,
        0.0,
        1.0,
    )
    foreign = np.clip(
        parameters.foreign_western_weight * western
        + parameters.foreign_linkage_weight * foreign_signal,
        0.0,
        1.0,
    )
    efficacy = np.clip(
        prev_efficacy
        + parameters.efficacy_success_weight * success
        - parameters.efficacy_risk_weight * action_risk,
        0.0,
        1.0,
    )
    repression_exposure = np.clip(
        (1.0 - parameters.exposure_decay) * prev_repression
        + parameters.exposure_decay
        * np.clip(
            repression + parameters.exposure_repression_weight * repression_cost,
            0.0,
            1.0,
        ),
        0.0,
        1.0,
    )

    alpha = np.asarray(parameters.alpha, dtype=np.float64)

    result = np.empty_like(prev)
    result[:, NETWORK_SIZE] = np.clip(
        (1.0 - alpha[NETWORK_SIZE]) * prev_network + alpha[NETWORK_SIZE] * network,
        0.0,
        1.0,
    )
    result[:, INTELLECTUAL_DENSITY] = intellectual
    result[:, WORKER_LINKAGE] = worker
    result[:, SAMIZDAT_CAPACITY] = np.clip(
        (1.0 - alpha[SAMIZDAT_CAPACITY]) * prev_samizdat + alpha[SAMIZDAT_CAPACITY] * samizdat,
        0.0,
        1.0,
    )
    result[:, FOREIGN_LINKAGE] = np.clip(
        (1.0 - alpha[FOREIGN_LINKAGE]) * prev_foreign + alpha[FOREIGN_LINKAGE] * foreign,
        0.0,
        1.0,
    )
    result[:, REPRESSION_EXPOSURE] = np.clip(
        (1.0 - alpha[REPRESSION_EXPOSURE]) * prev_repression
        + alpha[REPRESSION_EXPOSURE] * repression_exposure,
        0.0,
        1.0,
    )
    result[:, PERCEIVED_EFFICACY] = np.clip(
        (1.0 - alpha[PERCEIVED_EFFICACY]) * prev_efficacy + alpha[PERCEIVED_EFFICACY] * efficacy,
        0.0,
        1.0,
    )
    return result


def action_propensity(
    household_grievance: np.ndarray,
    household_region: np.ndarray,
    household_exposure: np.ndarray,
    household_efficacy: np.ndarray,
    region_capacity: np.ndarray,
    policy: PolicyVector,
    risk_signal: np.ndarray,
    parameters: OppositionParameters,
    region_count: int,
) -> np.ndarray:
    """Per-household unnormalized action propensity ``(N,)``.

    The regional organizing capacity is
    ``network_size * sqrt(worker_linkage * samizdat_capacity) * perceived_efficacy``;
    the per-household perceived risk is ``clip(repression + action_risk_weight *
    risk_signal, 0, 1)``.  A household with no resolvable region (outside
    ``[0, region_count)``, e.g. the caller's invalid sentinel) gets exactly 0.0.
    Zero capacity, exposure or efficacy likewise yields exactly 0.0.
    """
    grievance = np.asarray(household_grievance, dtype=np.float64)
    region = np.asarray(household_region, dtype=np.int64)
    exposure = np.asarray(household_exposure, dtype=np.float64)
    efficacy = np.asarray(household_efficacy, dtype=np.float64)
    capacity = np.asarray(region_capacity, dtype=np.float64)
    risk = np.asarray(risk_signal, dtype=np.float64)

    if capacity.ndim != 2 or capacity.shape[1] != V:
        raise ValueError(f"region_capacity must be (R, {V}), got {capacity.shape}")
    if risk.shape != (capacity.shape[0],):
        raise ValueError(f"risk_signal must be ({capacity.shape[0]},), got {risk.shape}")

    # Regional capacity index: geometric mean of the social-organization axes
    # multiplied by perceived efficacy.
    worker = _column(capacity, WORKER_LINKAGE)
    samizdat = _column(capacity, SAMIZDAT_CAPACITY)
    region_index = (
        _column(capacity, NETWORK_SIZE)
        * np.sqrt(np.clip(worker, 0.0, None) * np.clip(samizdat, 0.0, None))
        * _column(capacity, PERCEIVED_EFFICACY)
    )
    perceived_risk = np.clip(
        float(policy.repression) + parameters.action_risk_weight * risk,
        0.0,
        1.0,
    )
    region_weight = region_index * (1.0 - perceived_risk)

    valid = (region >= 0) & (region < region_count)
    safe_region = np.where(valid, region, 0)
    propensity = grievance * region_weight[safe_region] * exposure * efficacy
    return np.where(valid, propensity, 0.0)


__all__ = [
    "FOREIGN_LINKAGE",
    "FOREIGN_LINKAGE_SIGNAL",
    "INTELLECTUAL_DENSITY",
    "INTELLECTUAL_LINKAGE_SIGNAL",
    "NETWORK_SIZE",
    "OPPOSITION_SUCCESS_SIGNAL",
    "PERCEIVED_EFFICACY",
    "PUBLIC_ACTION_RISK_SIGNAL",
    "REPRESSION_COST_SIGNAL",
    "REPRESSION_EXPOSURE",
    "SAMIZDAT_CAPACITY",
    "WESTERN_EXPOSURE_SIGNAL",
    "WORKER_LINKAGE",
    "action_propensity",
    "update_region_capacity",
]
