"""P04 culture / information-exposure kernels (information dimension ``I``).

Pure numpy kernels over per-household arrays.  They translate an already
*visibility-filtered* societal signal (``western_signal_visible``) and the
domestic official signal into three slow-moving household state variables:

* ``identification`` -- regime identification, nudged by the official signal
  and eroded by Western exposure;
* ``exposure`` -- accumulated contact with the Western comparison signal;
* ``efficacy`` -- perceived collective-action efficacy, pulled toward the
  county target.

No I/O, no RNG, no decision client, and **no event -> support constant**: every
coefficient lives in :class:`~hsm_lab.contract.politics.CultureParameters`.
The three output arrays are clipped to ``[0, 1]`` and are state, never
political support.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from hsm_lab.contract.schemas import ConfigError

if TYPE_CHECKING:  # pragma: no cover - import for annotations only
    # ``contract.schemas`` defers its ``contract.politics`` import to module end
    # to break the schemas<->politics cycle.  ``CultureParameters`` is used only
    # in (lazily evaluated) annotations, so importing it at runtime here would
    # re-trigger that cycle when this module is imported first.
    from hsm_lab.contract.politics import CultureParameters

#: Content classes, ordered from least to most restricted.
_SUPPORTED = "supported"
_TOLERATED = "tolerated"
_PROHIBITED = "prohibited"

_CONTENT_CLASSES: tuple[str, ...] = (_SUPPORTED, _TOLERATED, _PROHIBITED)

#: Canonical dtype for every household state array.
_DTYPE = np.float64


def classify_content(
    content_sensitivity: float,
    supported_boundary: float,
    tolerance_boundary: float,
) -> str:
    """Classify one content item against the two declared tolerance boundaries.

    Boundaries are inclusive at the *lower* restriction class: a sensitivity
    exactly at ``supported_boundary`` is ``"supported"`` and one exactly at
    ``tolerance_boundary`` is ``"tolerated"``.  Every argument must be finite.
    """
    for name, value in (
        ("content_sensitivity", content_sensitivity),
        ("supported_boundary", supported_boundary),
        ("tolerance_boundary", tolerance_boundary),
    ):
        if not np.isfinite(value):
            raise ConfigError(f"classify_content: {name} must be finite, got {value!r}")
    if supported_boundary > tolerance_boundary:
        raise ConfigError(
            "classify_content: supported_boundary must not exceed tolerance_boundary "
            f"({supported_boundary!r} > {tolerance_boundary!r})"
        )
    if content_sensitivity <= supported_boundary:
        return _SUPPORTED
    if content_sensitivity <= tolerance_boundary:
        return _TOLERATED
    return _PROHIBITED


def visibility_multiplier(classification: str, parameters: CultureParameters) -> float:
    """Visibility multiplier applied to a content item by its classification."""
    if classification == _SUPPORTED:
        return float(parameters.supported_multiplier)
    if classification == _TOLERATED:
        return float(parameters.tolerated_multiplier)
    if classification == _PROHIBITED:
        return float(parameters.prohibited_multiplier)
    raise ConfigError(
        f"visibility_multiplier: unknown content classification {classification!r}; "
        f"expected one of {_CONTENT_CLASSES}"
    )


def _as_vector(name: str, value: np.ndarray, n: int) -> np.ndarray:
    array = np.asarray(value, dtype=_DTYPE)
    if array.ndim != 1 or array.shape[0] != n:
        raise ConfigError(
            f"update_household_culture: {name} must be 1-D of length {n}, got shape {array.shape}"
        )
    if not np.all(np.isfinite(array)):
        raise ConfigError(f"update_household_culture: {name} contains non-finite values")
    return array


def update_household_culture(
    previous_identification: np.ndarray,
    previous_exposure: np.ndarray,
    previous_efficacy: np.ndarray,
    official_signal_visible: float,
    western_signal_visible: np.ndarray,
    region_exposure_target: np.ndarray,
    region_efficacy: np.ndarray,
    household_region: np.ndarray,
    exposure_contact: np.ndarray,
    parameters: CultureParameters,
    *,
    openness: float,
    efficacy_alpha: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Advance household identification / exposure / efficacy by one quarter.

    All per-household arrays are ``(N,)`` and must share one length (else
    :class:`ConfigError`).  ``region_efficacy`` (and ``region_exposure_target``)
    are ``(R,)``; ``household_region`` indexes them with ``int64`` county ids.

    Rules (all targets clipped to ``[0, 1]`` before the EMA):

    * ``identification_target = clip(initial_ideology
      + official_loading * official_signal_visible - western_loading * exposure, 0, 1)``,
      EMA with ``identification_alpha``;
    * ``exposure_target = clip(openness * (exposure_contact
      + western_signal_visible) / 2, 0, 1)``, EMA with ``exposure_alpha``;
    * ``efficacy`` EMA toward ``region_efficacy[household_region]``.

    ``openness`` is the caller's per-quarter societal aperture (a finite scalar;
    the composition inside is clipped, not the signal itself).

    ``region_exposure_target`` is accepted for interface symmetry and shape
    validation with the caller's county bookkeeping; the exposure rule above
    consumes the per-household ``exposure_contact`` directly, as specified.

    ``efficacy_alpha`` defaults to ``parameters.exposure_alpha`` (the contract
    block declares no separate efficacy rate); pass an explicit value to
    override.  ``exposure_contact`` is the household's fixed initial
    county-contact level (the county weighted mean), supplied by the caller.
    """
    identification = np.asarray(previous_identification, dtype=_DTYPE)
    if identification.ndim != 1:
        raise ConfigError(
            "update_household_culture: previous_identification must be 1-D, "
            f"got shape {identification.shape}"
        )
    n = int(identification.shape[0])

    previous_identification = _as_vector("previous_identification", previous_identification, n)
    previous_exposure = _as_vector("previous_exposure", previous_exposure, n)
    previous_efficacy = _as_vector("previous_efficacy", previous_efficacy, n)
    western_signal_visible = _as_vector("western_signal_visible", western_signal_visible, n)
    exposure_contact = _as_vector("exposure_contact", exposure_contact, n)

    region = np.asarray(household_region)
    if region.ndim != 1 or region.shape[0] != n:
        raise ConfigError(
            "update_household_culture: household_region must be 1-D of length "
            f"{n}, got shape {region.shape}"
        )
    if not np.issubdtype(region.dtype, np.integer):
        raise ConfigError(
            f"update_household_culture: household_region must be integer, got {region.dtype}"
        )
    region = region.astype(np.int64, copy=False)

    region_efficacy = np.asarray(region_efficacy, dtype=_DTYPE)
    if region_efficacy.ndim != 1 or region_efficacy.shape[0] == 0:
        raise ConfigError(
            "update_household_culture: region_efficacy must be a non-empty 1-D array, "
            f"got shape {region_efficacy.shape}"
        )
    if not np.all(np.isfinite(region_efficacy)):
        raise ConfigError("update_household_culture: region_efficacy contains non-finite values")
    r_count = int(region_efficacy.shape[0])

    region_target = np.asarray(region_exposure_target, dtype=_DTYPE)
    if region_target.shape != (r_count,):
        raise ConfigError(
            "update_household_culture: region_exposure_target must match region_efficacy "
            f"shape ({r_count},), got {region_target.shape}"
        )
    if not np.all(np.isfinite(region_target)):
        raise ConfigError(
            "update_household_culture: region_exposure_target contains non-finite values"
        )

    if region.size and (int(region.min()) < 0 or int(region.max()) >= r_count):
        raise ConfigError(
            f"update_household_culture: household_region indexes outside [0, {r_count})"
        )

    if not np.isfinite(official_signal_visible):
        raise ConfigError(
            f"update_household_culture: official_signal_visible must be finite, "
            f"got {official_signal_visible!r}"
        )
    if not np.isfinite(openness):
        raise ConfigError(f"update_household_culture: openness must be finite, got {openness!r}")

    alpha_id = float(parameters.identification_alpha)
    alpha_exposure = float(parameters.exposure_alpha)
    alpha_efficacy = alpha_exposure if efficacy_alpha is None else float(efficacy_alpha)
    for name, alpha in (
        ("efficacy_alpha", alpha_efficacy),
        ("parameters.identification_alpha", alpha_id),
        ("parameters.exposure_alpha", alpha_exposure),
    ):
        if not np.isfinite(alpha) or alpha < 0.0 or alpha > 1.0:
            raise ConfigError(f"update_household_culture: {name} must lie in [0, 1], got {alpha!r}")

    identification_target = np.clip(
        float(parameters.initial_ideology)
        + float(parameters.official_loading) * float(official_signal_visible)
        - float(parameters.western_loading) * previous_exposure,
        0.0,
        1.0,
    )
    exposure_target = np.clip(
        float(openness) * (exposure_contact + western_signal_visible) / 2.0,
        0.0,
        1.0,
    )
    efficacy_target = region_efficacy[region]

    next_identification = np.clip(
        (1.0 - alpha_id) * previous_identification + alpha_id * identification_target, 0.0, 1.0
    )
    next_exposure = np.clip(
        (1.0 - alpha_exposure) * previous_exposure + alpha_exposure * exposure_target, 0.0, 1.0
    )
    next_efficacy = np.clip(
        (1.0 - alpha_efficacy) * previous_efficacy + alpha_efficacy * efficacy_target, 0.0, 1.0
    )
    return next_identification, next_exposure, next_efficacy


__all__ = [
    "classify_content",
    "update_household_culture",
    "visibility_multiplier",
]
