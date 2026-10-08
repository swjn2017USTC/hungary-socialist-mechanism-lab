"""P04 politics tests: coalition rule, broker/Soviet bounds, candidate slicing."""

from __future__ import annotations

import numpy as np
import pytest

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.politics import (
    COALITION_IDS,
    POLICY_COORDINATES,
    POLITICAL_FEATURE_IDS,
    ExternalWorldSlice,
    F,
    InformationState,
    PolicyVector,
    PoliticalFeedback,
    PoliticalSignals,
    W,
    default_broker_parameters,
    default_coalition_parameters,
)
from hsm_lab.engine.politics import choose_policy, update_coalitions

_AUTONOMY = POLICY_COORDINATES.index("enterprise_autonomy")
_OPENNESS = POLICY_COORDINATES.index("cultural_openness")
_GROWTH = POLITICAL_FEATURE_IDS.index("growth")
_SOVIET = POLITICAL_FEATURE_IDS.index("soviet_constraint")
_TECHNOLOGY = POLITICAL_FEATURE_IDS.index("technology_capacity")


def _slice(**values: float) -> ExternalWorldSlice:
    return ExternalWorldSlice(quarter="1968Q1", values=dict(values), origins={}, evidence_status={})


def _feedback(*, growth: float, soviet: float = 0.5, technology: float = 0.2) -> PoliticalFeedback:
    features = np.zeros(F, dtype=np.float64)
    features[_GROWTH] = growth
    features[_SOVIET] = soviet
    features[_TECHNOLOGY] = technology
    return PoliticalFeedback(
        features_raw=features.copy(),
        features_reported=features.copy(),
        features=features,
        valid=np.ones(F, dtype=bool),
        growth_undefined=False,
        objective_vector=np.zeros(5, dtype=np.float64),
        policy_error=0.0,
    )


def _initial_policy() -> PolicyVector:
    return PolicyVector(
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


def _signals(threat: float = 0.0, cost: float = 0.0) -> PoliticalSignals:
    return PoliticalSignals(
        government={"regime_threat": threat, "repression_cost": cost},
        county=np.zeros((1, 9), dtype=np.float64),
        delivered={},
    )


def test_coalition_interaction_sign_reverses_direction() -> None:
    weights = np.full(W, 1.0 / W)
    feedback = _feedback(growth=-0.5)
    external = _slice()
    positive = default_coalition_parameters()
    flipped = positive.model_copy(
        update={"interaction": [[-value for value in row] for row in positive.interaction]}
    )
    a = update_coalitions(weights, feedback, external, positive)
    b = update_coalitions(weights, feedback, external, flipped)
    reform = COALITION_IDS.index("reform_technocratic")
    conservative = COALITION_IDS.index("administrative_conservative")
    delta_a = a.new_weights - weights
    delta_b = b.new_weights - weights
    # The declared interaction makes a bad-growth/Soviet quarter favour the
    # conservative coalition; flipping the interaction sign reverses that.
    assert delta_a[reform] < delta_a[conservative]
    assert delta_b[reform] > delta_b[conservative]
    assert delta_a[reform] < delta_b[reform]
    assert delta_a[conservative] > delta_b[conservative]
    assert np.isclose(a.new_weights.sum(), 1.0)
    assert np.all(np.isfinite(a.new_weights))
    assert np.allclose(a.contributions.sum(axis=1), a.score)


def test_coalition_rejects_non_simplex_weights() -> None:
    with pytest.raises(ConfigError):
        update_coalitions(
            np.full(W, 0.2), _feedback(growth=0.0), _slice(), default_coalition_parameters()
        )


def test_broker_soviet_bound_caps_candidates() -> None:
    initial = _initial_policy()
    parameters = default_broker_parameters(initial)
    weights = np.full(W, 1.0 / W)
    feedback = _feedback(growth=-0.2)
    external = _slice(soviet_constraint=1.0)
    information = InformationState(
        capability=1.0, dimensions=np.ones(7, dtype=np.float64), total_lag=0
    )
    decision = choose_policy(
        weights,
        initial,
        feedback,
        external,
        information,
        parameters,
        signals=_signals(threat=0.4, cost=0.2),
    )
    cap = 1.0 - 1.0 * (1.0 - float(parameters.soviet_floor))
    assert decision.selected_policy[_AUTONOMY] <= cap + 1e-12
    assert decision.selected_policy[_OPENNESS] <= cap + 1e-12
    selected = decision.selected_index
    assert decision.candidate_utilities[selected] == decision.candidate_utilities.max()


def test_broker_candidate_count_follows_capability() -> None:
    initial = _initial_policy()
    parameters = default_broker_parameters(initial)
    weights = np.full(W, 1.0 / W)
    feedback = _feedback(growth=0.0)
    external = _slice(soviet_constraint=0.5)
    for capability, expected in ((0.0, 2), (0.6, 4), (1.0, 6)):
        information = InformationState(
            capability=capability, dimensions=np.ones(7, dtype=np.float64), total_lag=0
        )
        decision = choose_policy(
            weights,
            initial,
            feedback,
            external,
            information,
            parameters,
            signals=_signals(),
        )
        assert len(decision.candidate_ids) == expected
        assert decision.candidate_ids[0] == "previous"
