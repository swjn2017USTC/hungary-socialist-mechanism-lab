"""P04 state observation: independent measurement error vs strategic reporting bias.

The party-state never sees ground truth.  Two *separate* mechanisms deform each
published state feature:

* **measurement error** -- independent zero-mean uniform noise whose scale falls
  with information capability ``c`` and is drawn from its own RNG module; it is
  the only part technology improves;
* **strategic reporting bias** -- an enterprise reporting distortion
  (demand overstatement / inventory concealment / capacity misstatement)
  projected onto state features by a declared loading matrix; it is **never**
  multiplied by ``(1-c)`` and technology does not remove it.

The two are stored separately so the decompositions can be rebuilt, and the
ring buffer keeps the raw truth, noise, bias and clip delta per published slot.
"""

from __future__ import annotations

import numpy as np

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.politics import (
    INFORMATION_DIMENSION_IDS,
    POLITICAL_FEATURE_IDS,
    EnterpriseReports,
    F,
    InformationState,
    ObservationParameters,
    StateObservation,
    TruthSnapshot,
)
from hsm_lab.engine.rng import RngRegistry

MEASUREMENT_MODULE = "p04_observation.measurement"

_GROWTH_INDEX = POLITICAL_FEATURE_IDS.index("growth")

__all__ = ["MEASUREMENT_MODULE", "form_enterprise_reports", "observe_state"]


def form_enterprise_reports(
    true_need: np.ndarray,
    true_inventory: np.ndarray,
    true_capacity: np.ndarray,
    *,
    overstatement: float,
    concealment: float,
    misstatement: float,
) -> EnterpriseReports:
    """Project true own need/inventory/capacity into biased enterprise reports.

    ``reported_need = true_need*(1+overstatement)``,
    ``reported_inventory = true_inventory*(1-concealment)``,
    ``reported_capacity = true_capacity*(1+misstatement)``.  The bias is a
    deliberate reporting distortion; it is never ``(1-c)``-scaled.
    """
    need = np.asarray(true_need, dtype=np.float64)
    inventory = np.asarray(true_inventory, dtype=np.float64)
    capacity = np.asarray(true_capacity, dtype=np.float64)
    if not (0.0 <= concealment <= 1.0):
        raise ConfigError("enterprise concealment must lie in [0, 1]")
    if overstatement < 0.0:
        raise ConfigError("enterprise demand overstatement must be non-negative")
    if not -1.0 <= misstatement <= 1.0:
        raise ConfigError("enterprise capacity misstatement must lie in [-1, 1]")
    return EnterpriseReports(
        need=need,
        reported_need=need * (1.0 + float(overstatement)),
        inventory=inventory,
        reported_inventory=inventory * (1.0 - float(concealment)),
        capacity=capacity,
        reported_capacity=capacity * (1.0 + float(misstatement)),
        overstatement=float(overstatement),
        concealment=float(concealment),
        misstatement=float(misstatement),
    )


def _strategic_bias(
    reports: EnterpriseReports | None,
    parameters: ObservationParameters,
) -> np.ndarray:
    if reports is None:
        return np.zeros(F, dtype=np.float64)
    need_discrepancy = float(np.sum(np.maximum(reports.reported_need - reports.need, 0.0)))
    inventory_discrepancy = float(
        np.sum(np.maximum(reports.inventory - reports.reported_inventory, 0.0))
    )
    capacity_discrepancy = float(np.sum(np.abs(reports.reported_capacity - reports.capacity)))
    normalized = np.array(
        [
            need_discrepancy / float(parameters.need_reference),
            inventory_discrepancy / float(parameters.inventory_reference),
            capacity_discrepancy / float(parameters.capacity_reference),
        ],
        dtype=np.float64,
    )
    loading = np.asarray(parameters.feature_bias_loading, dtype=np.float64)
    return loading @ normalized


def observe_state(
    truth: TruthSnapshot,
    reports: EnterpriseReports | None,
    information: InformationState,
    rng: RngRegistry,
    parameters: ObservationParameters,
    *,
    quarter: str,
    measurement_quarter: int,
    published_quarter: int,
    stochastic: bool,
) -> StateObservation:
    """Form one quarter's published state observation from closing truth."""
    raw = np.asarray(truth.features, dtype=np.float64)
    if raw.shape != (F,):
        raise ConfigError(f"truth features must have shape ({F},), got {raw.shape}")
    if not np.all(np.isfinite(raw)):
        raise ConfigError("truth features contain non-finite entries")
    valid = np.asarray(
        [
            False
            if feature in ("growth", "shortage")
            and (truth.growth_base_zero if feature == "growth" else truth.shortage_denominator_zero)
            else True
            for feature in POLITICAL_FEATURE_IDS
        ],
        dtype=bool,
    )
    # A coordinate with an undefined base never receives a fabricated
    # measurement: its noise is pinned to zero while the draw count stays fixed
    # (CRN across arms).
    noise_scale = np.asarray(parameters.noise_scale, dtype=np.float64)
    declared = np.asarray(parameters.declared_scale, dtype=np.float64)
    sigma = float(
        np.asarray(information.dimensions, dtype=np.float64)[
            INFORMATION_DIMENSION_IDS.index("measurement_error")
        ]
    )
    if stochastic:
        draws = rng.uniform(MEASUREMENT_MODULE, (F,))
    else:
        draws = np.full(F, 0.5, dtype=np.float64)
    noise = (2.0 * draws - 1.0) * np.sqrt(3.0) * float(sigma) * noise_scale * declared
    noise = np.where(valid, noise, 0.0)
    bias = _strategic_bias(reports, parameters)
    reported = raw + noise + bias
    lower = np.full(F, 0.0, dtype=np.float64)
    upper = np.full(F, 1.0, dtype=np.float64)
    lower[_GROWTH_INDEX] = -1.0
    published = np.clip(reported, lower, upper)
    clipping_delta = published - reported
    return StateObservation(
        quarter=quarter,
        raw_truth=raw.copy(),
        measurement_noise=noise,
        strategic_bias=bias,
        reported=reported,
        published=published,
        clipping_delta=clipping_delta,
        valid=valid,
        measurement_quarter=int(measurement_quarter),
        published_quarter=int(published_quarter),
    )
