"""Information-capability / technology kernel (P04 politics layer).

This module maps an information-capability scalar to the seven declared
``INFORMATION_DIMENSION_IDS`` channels and advances capability over one
quarter.  It is deliberately a **channel-only** kernel: technology changes
only data latency, measurement error, forecast accuracy, optimization
capacity, inventory visibility, reporting speed and computational cost.

The module **never** contains a production, capacity, input-output or
productivity term.  Information capability is a constraint on observation and
optimization, not a factor of production; any mapping from these channels to
output lives in a different module and is out of scope here.

All functions are pure over their arguments, deterministic for identical
inputs, and free of I/O, registries and per-entity Python loops.
"""

from __future__ import annotations

import math

import numpy as np

from hsm_lab.contract.politics import (
    INFORMATION_DIMENSION_IDS,
    ExternalWorldSlice,
    InformationParameters,
    InformationState,
    PolicyVector,
)

#: Index of each declared information dimension (order is canonical).
_DIMENSIONS: tuple[str, ...] = INFORMATION_DIMENSION_IDS

if len(_DIMENSIONS) != 7:  # pragma: no cover - contract guard
    raise AssertionError("technology kernel expects exactly seven I dimensions")


def advance_information_capacity(
    previous: InformationState,
    policy: PolicyVector,
    external: ExternalWorldSlice,
    parameters: InformationParameters,
) -> InformationState:
    """Advance the information-capability scalar by one quarter.

    ``c' = clip((1 - depreciation) * c
               + learning * information_investment_weight
                 * policy.information_investment * technology_access * (1 - c),
               0, 1)``

    where ``technology_access`` is the immutable external-world channel.  The
    resulting state's dimensions and total lag are derived from ``c'``.
    """
    technology_access = external.get("technology_access")
    capability = float(previous.capability)
    updated = (1.0 - parameters.depreciation) * capability + (
        parameters.learning
        * parameters.information_investment_weight
        * float(policy.information_investment)
        * technology_access
        * (1.0 - capability)
    )
    clipped = float(np.clip(updated, 0.0, 1.0))
    return information_state(clipped, parameters)


def information_dimensions(capability: float, parameters: InformationParameters) -> np.ndarray:
    """Map a capability scalar to the seven declared information dimensions.

    Order matches ``INFORMATION_DIMENSION_IDS`` exactly::

        data_latency, measurement_error, forecast_accuracy,
        optimization_capacity, inventory_visibility, reporting_speed,
        computational_cost

    ``reporting_delay`` is an internal quantity (used only for ``total_lag``)
    and is therefore not one of the returned slots.
    """
    c = float(np.clip(capability, 0.0, 1.0))
    residual = 1.0 - c

    data_latency = float(math.floor(parameters.latency_scale * residual))
    measurement_error = parameters.measurement_sigma * residual
    forecast_accuracy = c
    optimization_capacity = c
    inventory_visibility = c

    reporting_delay = float(math.floor(parameters.reporting_scale * residual))
    reporting_speed = 1.0 / (1.0 + reporting_delay)

    candidate_count = 2.0 + float(math.floor(4.0 * c))
    computational_cost = parameters.computational_cost_scale * candidate_count * residual

    return np.array(
        [
            data_latency,
            measurement_error,
            forecast_accuracy,
            optimization_capacity,
            inventory_visibility,
            reporting_speed,
            computational_cost,
        ],
        dtype=np.float64,
    )


def information_state(capability: float, parameters: InformationParameters) -> InformationState:
    """Build an :class:`InformationState` for a capability scalar.

    ``total_lag = min(lag_cap, data_latency + reporting_delay)`` where the two
    lag components are the (floored) integer delays induced by ``capability``.
    """
    c = float(np.clip(capability, 0.0, 1.0))
    residual = 1.0 - c

    data_latency = int(math.floor(parameters.latency_scale * residual))
    reporting_delay = int(math.floor(parameters.reporting_scale * residual))
    total_lag = min(int(parameters.lag_cap), data_latency + reporting_delay)

    return InformationState(
        capability=c,
        dimensions=information_dimensions(c, parameters),
        total_lag=total_lag,
    )


__all__ = [
    "advance_information_capacity",
    "information_dimensions",
    "information_state",
]
