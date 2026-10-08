"""P04 endogenous politics: latent coalition update and broker policy choice.

Two pure, deterministic kernels operate on numpy state and the frozen P04
contracts:

* :func:`update_coalitions` advances the latent coalition-weight vector with a
  multinomial-logit rule around the previous weights (zero weights are never
  permanently disqualified because the rule takes ``log(eps)``);
* :func:`choose_policy` scores a fixed, deterministically-sliced candidate list
  by a structural surrogate utility and returns the arg-max policy.

Both results are **latent rule results, not historical probabilities or fitted
estimates**.  Nothing here is calibrated to data, no RNG is used, and identical
inputs always produce identical outputs.
"""

from __future__ import annotations

import numpy as np

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.politics import (
    BROKER_OBJECTIVE_IDS,
    COALITION_IDS,
    POLICY_COORDINATES,
    POLITICAL_FEATURE_IDS,
    BrokerParameters,
    CoalitionParameters,
    CoalitionTransition,
    ExternalWorldSlice,
    F,
    InformationState,
    PolicyDecision,
    PolicyVector,
    PoliticalFeedback,
    PoliticalSignals,
    U,
    W,
    normalize_policy_vector,
    policy_bounds_arrays,
)
from hsm_lab.provenance.manifest import canonical_digest

__all__ = ["update_coalitions", "choose_policy"]

# ---------------------------------------------------------------------------
# Declared-index lookups (never position-dependent elsewhere)
# ---------------------------------------------------------------------------

_COORDINATE_INDEX: dict[str, int] = {name: i for i, name in enumerate(POLICY_COORDINATES)}
_FEATURE_INDEX: dict[str, int] = {name: i for i, name in enumerate(POLITICAL_FEATURE_IDS)}

_GROWTH = _FEATURE_INDEX["growth"]
_SOVIET_CONSTRAINT = _FEATURE_INDEX["soviet_constraint"]
_TECHNOLOGY_CAPACITY = _FEATURE_INDEX["technology_capacity"]

_ENTERPRISE_AUTONOMY = _COORDINATE_INDEX["enterprise_autonomy"]
_CULTURAL_OPENNESS = _COORDINATE_INDEX["cultural_openness"]
_SUPPORTED_BOUNDARY = _COORDINATE_INDEX["supported_boundary"]
_TOLERANCE_BOUNDARY = _COORDINATE_INDEX["tolerance_boundary"]
_REPRESSION = _COORDINATE_INDEX["repression"]

_REGIME_STABILITY_OBJECTIVE = BROKER_OBJECTIVE_IDS.index("regime_stability")

#: Fixed broker candidate id order; the evaluated list is a prefix of this.
_CANDIDATE_IDS: tuple[str, ...] = (
    "previous",
    "weighted_ideals",
    *(f"ideal.{name}" for name in COALITION_IDS),
)


# ---------------------------------------------------------------------------
# Coalition update
# ---------------------------------------------------------------------------


def _coerce_feature_vector(name: str, values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.shape != (F,):
        raise ConfigError(f"{name} must have shape ({F},), got {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ConfigError(f"{name} contains non-finite entries")
    return array


def update_coalitions(
    previous_weights: np.ndarray,
    feedback: PoliticalFeedback,
    external: ExternalWorldSlice,
    parameters: CoalitionParameters,
) -> CoalitionTransition:
    """Advance latent coalition weights by one multinomial-logit rule.

    The rule input is ``feedback.features`` (the clipped vector, ordered by
    ``POLITICAL_FEATURE_IDS``); ``feedback.features_raw`` / ``features_reported``
    are carried through unchanged.  The score of coalition ``w`` is

    ``intercept[w] + sum_f beta[w][f]*features[f] + J[w]`` with the declared
    interaction term
    ``J[w] = interaction[w][0]*max(-growth,0)*soviet_constraint
            + interaction[w][1]*max(-growth,0)*technology_capacity``.

    The new weights are a stable softmax of ``log(max(previous, eps)) +
    learning_rate*score``.  Zero weights stay admissible (only ``log(eps)``).

    Returns a latent rule result -- never a historical probability.
    """
    weights = np.asarray(previous_weights, dtype=np.float64)
    if weights.shape != (W,):
        raise ConfigError(f"previous_weights must have shape ({W},), got {weights.shape}")
    if not np.all(np.isfinite(weights)):
        raise ConfigError("previous_weights contains non-finite entries")
    if np.any(weights < 0.0):
        raise ConfigError("previous_weights must be non-negative")
    if not np.isclose(float(weights.sum()), 1.0, atol=1e-9):
        raise ConfigError(f"previous_weights must sum to one, got {float(weights.sum())}")

    features = _coerce_feature_vector("feedback.features", feedback.features)
    features_raw = _coerce_feature_vector("feedback.features_raw", feedback.features_raw)
    features_reported = _coerce_feature_vector(
        "feedback.features_reported", feedback.features_reported
    )
    valid = np.asarray(feedback.valid, dtype=bool)
    if valid.shape != (F,):
        raise ConfigError(f"feedback.valid must have shape ({F},), got {valid.shape}")

    intercept = np.asarray(parameters.intercept, dtype=np.float64)
    beta = np.asarray(parameters.beta, dtype=np.float64)
    interaction = np.asarray(parameters.interaction, dtype=np.float64)

    growth_bad = max(-float(features[_GROWTH]), 0.0)
    interaction_contribution = interaction[:, 0] * growth_bad * float(
        features[_SOVIET_CONSTRAINT]
    ) + interaction[:, 1] * growth_bad * float(features[_TECHNOLOGY_CAPACITY])

    contributions = np.empty((W, F + 1), dtype=np.float64)
    contributions[:, :F] = beta * features[np.newaxis, :]
    # Both declared interactions are growth-conditional, so they accumulate into
    # the growth feature column; the last column is the exact intercept.  The
    # row sum therefore reconstructs ``score`` exactly.
    contributions[:, _GROWTH] += interaction_contribution
    contributions[:, F] = intercept

    score = contributions.sum(axis=1)

    logits = (
        np.log(np.maximum(weights, float(parameters.eps))) + float(parameters.learning_rate) * score
    )
    logits = logits - float(np.max(logits))
    expo = np.exp(logits)
    new_weights = expo / expo.sum()
    new_weights = new_weights / new_weights.sum()

    return CoalitionTransition(
        previous_weights=weights.copy(),
        new_weights=np.asarray(new_weights, dtype=np.float64),
        features_raw=np.asarray(features_raw, dtype=np.float64).copy(),
        features_reported=np.asarray(features_reported, dtype=np.float64).copy(),
        features=np.asarray(features, dtype=np.float64).copy(),
        score=np.asarray(score, dtype=np.float64),
        contributions=contributions,
        feature_valid=valid.copy(),
        parameter_hash=canonical_digest(parameters.flatten()),
    )


# ---------------------------------------------------------------------------
# Broker policy choice
# ---------------------------------------------------------------------------


def _project_candidate(
    raw: np.ndarray,
    *,
    soviet_cap: float,
    bounds_lower: np.ndarray,
    bounds_upper: np.ndarray,
) -> tuple[np.ndarray, list[str]]:
    """Apply the declared soviet / 3T projections, then clip to declared bounds."""
    policy = np.array(raw, dtype=np.float64, copy=True)
    constraints: list[str] = []

    soviet_bound = False
    for index in (_ENTERPRISE_AUTONOMY, _CULTURAL_OPENNESS):
        if policy[index] > soviet_cap:
            policy[index] = soviet_cap
            soviet_bound = True
    if soviet_bound:
        constraints.append("soviet_bound")

    if policy[_SUPPORTED_BOUNDARY] > policy[_TOLERANCE_BOUNDARY]:
        policy[_SUPPORTED_BOUNDARY] = policy[_TOLERANCE_BOUNDARY]
        constraints.append("3t_boundary")

    policy = np.clip(policy, bounds_lower, bounds_upper)
    # from_vector both validates the declared bounds and the 3T ordering.
    policy = PolicyVector.from_vector(policy).to_vector()
    return policy, constraints


def choose_policy(
    weights: np.ndarray,
    previous_policy: PolicyVector,
    feedback: PoliticalFeedback,
    external: ExternalWorldSlice,
    information: InformationState,
    parameters: BrokerParameters,
    *,
    signals: PoliticalSignals,
) -> PolicyDecision:
    """Select one policy from a fixed, deterministically-sliced candidate list.

    The candidate order is ``[previous, weighted_ideals, ideal_reform,
    ideal_conservative, ideal_contract, ideal_industrial]`` where the four
    ideals follow the declared ``COALITION_IDS`` order and ``weighted_ideals``
    is ``sum_w weights[w]*ideals[w]``.  Only the first
    ``2 + floor(4*capability)`` candidates are evaluated.

    Each evaluated candidate is projected (``soviet_constraint`` caps
    ``enterprise_autonomy`` / ``cultural_openness`` at
    ``1 - s*(1-soviet_floor)``; ``supported_boundary`` is capped at
    ``tolerance_boundary``) and clipped into its declared bounds.  The selected
    candidate maximises a structural surrogate utility (objective residuals,
    cohesion, inertia and repression-cost terms); ties go to the lowest index.

    The utility is a latent rule result, not a historical probability.
    """
    coalition_weights = np.asarray(weights, dtype=np.float64)
    if coalition_weights.shape != (W,):
        raise ConfigError(f"weights must have shape ({W},), got {coalition_weights.shape}")
    if not np.all(np.isfinite(coalition_weights)):
        raise ConfigError("weights contains non-finite entries")

    features = _coerce_feature_vector("feedback.features", feedback.features)

    capability = float(information.capability)
    if not np.isfinite(capability):
        raise ConfigError("information.capability must be finite")
    capability = float(np.clip(capability, 0.0, 1.0))
    candidate_count = 2 + int(np.floor(4.0 * capability))
    candidate_count = max(1, min(candidate_count, len(_CANDIDATE_IDS)))

    ideals = np.asarray(parameters.ideals, dtype=np.float64)
    weighted_ideals = coalition_weights @ ideals
    previous_raw = previous_policy.to_vector()

    raw_candidates = [
        previous_raw,
        weighted_ideals,
        *(ideals[w] for w in range(W)),
    ][:candidate_count]
    candidate_ids = list(_CANDIDATE_IDS[:candidate_count])

    soviet_constraint = float(np.clip(external.get("soviet_constraint"), 0.0, 1.0))
    soviet_cap = 1.0 - soviet_constraint * (1.0 - float(parameters.soviet_floor))

    bounds_lower, bounds_upper = policy_bounds_arrays()

    policies = np.empty((candidate_count, U), dtype=np.float64)
    constraints_per_candidate: list[list[str]] = []
    for index, raw in enumerate(raw_candidates):
        policy, constraints = _project_candidate(
            raw,
            soviet_cap=soviet_cap,
            bounds_lower=bounds_lower,
            bounds_upper=bounds_upper,
        )
        policies[index] = policy
        constraints_per_candidate.append(constraints)

    normalized_previous = normalize_policy_vector(previous_raw)
    normalized_ideals = normalize_policy_vector(ideals)

    a_matrix = np.asarray(parameters.A, dtype=np.float64)
    q = np.asarray(parameters.q, dtype=np.float64).copy()
    target_base = np.asarray(parameters.target_base, dtype=np.float64)
    target_response = np.asarray(parameters.target_response, dtype=np.float64)

    regime_threat = float(signals.government.get("regime_threat", 0.0))
    repression_cost = float(signals.government.get("repression_cost", 0.0))
    q[_REGIME_STABILITY_OBJECTIVE] *= 1.0 + regime_threat

    targets = np.clip(target_base + target_response @ features, -1.0, 1.0)

    utilities = np.empty(candidate_count, dtype=np.float64)
    terms = np.zeros((candidate_count, 4), dtype=np.float64)
    for index in range(candidate_count):
        normalized_policy = normalize_policy_vector(policies[index])
        residual = a_matrix @ normalized_policy - targets
        objective_term = -float(np.sum(q * residual * residual))

        cohesion = float(
            np.sum(coalition_weights * np.sum((normalized_policy - normalized_ideals) ** 2, axis=1))
        )
        cohesion_term = -float(parameters.cohesion_penalty) * cohesion

        inertia = float(np.sum((normalized_policy - normalized_previous) ** 2))
        inertia_term = -float(parameters.inertia_penalty) * inertia

        normalized_repression = float(normalized_policy[_REPRESSION])
        repression_term = (
            -float(parameters.repression_cost_penalty) * normalized_repression * repression_cost
        )

        terms[index] = (objective_term, cohesion_term, inertia_term, repression_term)
        utilities[index] = objective_term + cohesion_term + inertia_term + repression_term

    selected_index = int(np.argmax(utilities))
    selected_policy = policies[selected_index].copy()

    return PolicyDecision(
        candidate_ids=candidate_ids,
        candidate_utilities=utilities,
        candidate_policies=policies,
        selected_index=selected_index,
        selected_policy=selected_policy,
        binding_constraints=list(constraints_per_candidate[selected_index]),
        source="broker",
        elite_cohesion=0.0,
        candidate_terms=terms,
        candidate_binding=[list(items) for items in constraints_per_candidate],
    )
