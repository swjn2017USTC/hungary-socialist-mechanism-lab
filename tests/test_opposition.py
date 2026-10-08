"""P04 opposition tests: grievance vs capacity, Poland dual-channel, action risk."""

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
from hsm_lab.engine.opposition import action_propensity, update_region_capacity

_NETWORK = OPPOSITION_AXIS_IDS.index("network_size")
_WORKER = OPPOSITION_AXIS_IDS.index("worker_linkage")
_SAMIZDAT = OPPOSITION_AXIS_IDS.index("samizdat_capacity")
_EFFICACY = OPPOSITION_AXIS_IDS.index("perceived_efficacy")
_REPRESSION_EXPOSURE = OPPOSITION_AXIS_IDS.index("repression_exposure")


def _policy(**overrides: float) -> PolicyVector:
    base = dict(
        plan_utilization=0.9,
        enterprise_autonomy=0.1,
        investment_intensity=1.0,
        industrial_priority=0.0,
        admin_price_factor=1.0,
        wage_factor=1.0,
        credit_fraction=0.5,
        budget_hardness=0.0,
        housing_factor=1.0,
        borrowing_factor=1.0,
        consumer_import_factor=1.0,
        second_economy_tolerance=1.0,
        welfare_provision=0.5,
        private_autonomy=0.5,
        cultural_openness=0.5,
        supported_boundary=0.3,
        tolerance_boundary=0.7,
        repression=0.3,
        information_investment=0.0,
    )
    base.update(overrides)
    return PolicyVector(**base)


def _signals(**channels: float) -> np.ndarray:
    array = np.zeros((1, len(SIGNAL_CHANNELS)), dtype=np.float64)
    for name, value in channels.items():
        array[0, SIGNAL_CHANNELS.index(name)] = value
    return array


def test_zero_capacity_gives_zero_action_despite_grievance() -> None:
    parameters = OppositionParameters()
    capacity = np.zeros((1, V), dtype=np.float64)  # network_size = 0
    propensity = action_propensity(
        np.array([1.0]),
        np.array([0], dtype=np.int64),
        np.array([0.5]),
        np.array([0.5]),
        capacity,
        _policy(),
        np.zeros(1, dtype=np.float64),
        parameters,
        1,
    )
    assert propensity[0] == 0.0


def test_positive_network_produces_action() -> None:
    parameters = OppositionParameters()
    capacity = np.zeros((1, V), dtype=np.float64)
    capacity[0, _NETWORK] = 0.8
    capacity[0, _WORKER] = 0.7
    capacity[0, _SAMIZDAT] = 0.6
    capacity[0, _EFFICACY] = 0.9
    propensity = action_propensity(
        np.array([1.0]),
        np.array([0], dtype=np.int64),
        np.array([0.5]),
        np.array([0.9]),
        capacity,
        _policy(repression=0.1),
        np.zeros(1, dtype=np.float64),
        parameters,
        1,
    )
    assert propensity[0] > 0.0


def test_poland_dual_channel_and_martial_law_risk() -> None:
    parameters = OppositionParameters()
    previous = np.full((1, V), 0.2, dtype=np.float64)
    formation = np.array([[0.6, 0.7]])
    external = ExternalWorldSlice(quarter="1980Q1", values={}, origins={}, evidence_status={})
    # Solidarity: opposition success + worker linkage (and leader threat handled by
    # the government channel upstream).
    solidarity = update_region_capacity(
        previous,
        formation,
        _policy(),
        _signals(opposition_success=0.8, worker_linkage=0.8),
        external,
        parameters,
    )
    assert solidarity[0, _EFFICACY] > previous[0, _EFFICACY]
    assert solidarity[0, _WORKER] >= previous[0, _WORKER]

    # Martial law (1981Q4): public action risk rises; action can fall while
    # grievance stays high and repression exposure grows.
    repression_before = update_region_capacity(
        solidarity,
        formation,
        _policy(),
        _signals(public_action_risk=0.0),
        external,
        parameters,
    )
    repression_after = update_region_capacity(
        solidarity,
        formation,
        _policy(),
        _signals(public_action_risk=0.9, repression_cost=0.9),
        external,
        parameters,
    )
    assert repression_after[0, _REPRESSION_EXPOSURE] >= repression_before[0, _REPRESSION_EXPOSURE]

    grievance = np.array([1.0])
    action_before = action_propensity(
        grievance,
        np.array([0], dtype=np.int64),
        np.array([0.5]),
        np.array([0.9]),
        repression_before,
        _policy(),
        np.array([0.0]),
        parameters,
        1,
    )
    action_after = action_propensity(
        grievance,
        np.array([0], dtype=np.int64),
        np.array([0.5]),
        np.array([0.9]),
        repression_after,
        _policy(),
        np.array([0.9]),
        parameters,
        1,
    )
    assert action_after[0] < action_before[0]
    assert grievance[0] == 1.0  # grievance itself is never deleted by the risk channel
