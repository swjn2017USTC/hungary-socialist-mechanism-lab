"""P04 information tests: measurement error vs strategic bias, technology channels."""

from __future__ import annotations

import numpy as np

from hsm_lab.contract.politics import (
    POLITICAL_FEATURE_IDS,
    EnterpriseReports,
    F,
    InformationParameters,
    InformationState,
    ObservationParameters,
    TruthSnapshot,
    default_feature_bias_loading,
)
from hsm_lab.engine.observation import MEASUREMENT_MODULE, form_enterprise_reports, observe_state
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.technology import information_dimensions


def _info(capability: float) -> InformationState:
    parameters = InformationParameters()
    return InformationState(
        capability=capability,
        dimensions=information_dimensions(capability, parameters),
        total_lag=0,
    )


def _reports() -> EnterpriseReports:
    return form_enterprise_reports(
        np.full((2, 3), 10.0),
        np.full((2, 3), 10.0),
        np.full(2, 10.0),
        overstatement=0.2,
        concealment=0.2,
        misstatement=0.0,
    )


def _truth() -> TruthSnapshot:
    return TruthSnapshot(
        features=np.full(F, 0.5),
        output_value=1.0,
        shortage_denominator_zero=False,
        growth_base_zero=False,
    )


def test_enterprise_reports_scale_by_declared_bias() -> None:
    reports = _reports()
    assert np.allclose(reports.reported_need, reports.need * 1.2)
    assert np.allclose(reports.reported_inventory, reports.inventory * 0.8)
    assert np.allclose(reports.reported_capacity, reports.capacity)


def test_observation_decomposition_is_exact_and_separated() -> None:
    parameters = ObservationParameters(feature_bias_loading=default_feature_bias_loading())
    observation = observe_state(
        _truth(),
        _reports(),
        _info(0.5),
        RngRegistry(1729),
        parameters,
        quarter="1968Q1",
        measurement_quarter=0,
        published_quarter=0,
        stochastic=True,
    )
    assert np.allclose(
        observation.reported,
        observation.raw_truth + observation.measurement_noise + observation.strategic_bias,
    )
    assert np.allclose(observation.published, np.clip(observation.reported, -1.0, 1.0))
    shortage = POLITICAL_FEATURE_IDS.index("shortage")
    assert observation.strategic_bias[shortage] > 0.0


def test_higher_capability_reduces_measurement_noise_only() -> None:
    parameters = ObservationParameters(feature_bias_loading=default_feature_bias_loading())
    low = observe_state(
        _truth(),
        _reports(),
        _info(0.2),
        RngRegistry(1729),
        parameters,
        quarter="1968Q1",
        measurement_quarter=0,
        published_quarter=0,
        stochastic=True,
    )
    high = observe_state(
        _truth(),
        _reports(),
        _info(1.0),
        RngRegistry(1729),
        parameters,
        quarter="1968Q1",
        measurement_quarter=0,
        published_quarter=0,
        stochastic=True,
    )
    # Same seed -> same draws, so the higher-capability arm has strictly smaller
    # measurement error while the strategic bias is identical: technology never
    # removes the enterprise reporting distortion.
    assert np.all(np.abs(high.measurement_noise) <= np.abs(low.measurement_noise) + 1e-12)
    assert not np.allclose(high.measurement_noise, low.measurement_noise)
    assert np.allclose(high.strategic_bias, low.strategic_bias)


def test_deterministic_mode_consumes_no_draws() -> None:
    rng = RngRegistry(1729)
    observe_state(
        _truth(),
        None,
        _info(0.5),
        rng,
        ObservationParameters(),
        quarter="1968Q1",
        measurement_quarter=0,
        published_quarter=0,
        stochastic=False,
    )
    assert rng.draws_by_module().get(MEASUREMENT_MODULE, 0) == 0


def test_information_dimensions_follow_capability_monotonically() -> None:
    parameters = InformationParameters()
    low = information_dimensions(0.1, parameters)
    high = information_dimensions(0.9, parameters)
    assert low.shape == (7,) and high.shape == (7,)
    # latency / measurement error / computational cost fall; accuracy/visibility rise.
    for index in (0, 1, 6):
        assert high[index] <= low[index] + 1e-12
    for index in (2, 3, 4):
        assert high[index] >= low[index] - 1e-12
