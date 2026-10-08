"""P04 contracts: political coalitions, policy replay, external world, information.

Every numeric default here is a declared engineering fixture
(``structural_assumption / not_calibrated / not_assessed``).  Nothing in this
module is a historical Hungarian estimate, a fitted coefficient or an observed
policy magnitude.

Design rules encoded here (BASELINE §§7, 11-19, 20-24):

* an external event never carries a free-standing "support +20" effect: it only
  activates typed *signal channels*, and each channel has an explicit loading
  and decay parameter;
* coalition weights are latent state with provenance/parameter status, never
  observed data;
* the three political modes are structural: Mode A (historical replay) demands
  a replay registry, Mode B (endogenous) forbids one, Mode C (counterfactual)
  is only created by an explicit checkpoint fork;
* state observation separates independent measurement error from enterprise
  strategic reporting bias (technology lowers the former, never the latter);
* technology movements only ever touch information-processing channels.

All multi-axis records are ordered by declared name, never by position, and the
declared order is part of every compiled hash.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal, Self

import numpy as np
from pydantic import Field, model_validator

from hsm_lab.contract.base import ConfigError, FiniteFloat, StrictModel
from hsm_lab.contract.schemas import (
    EvidenceStatus,
    PoliticalMode,
    Quarter,
    QuarterLike,
)

# ---------------------------------------------------------------------------
# Declared axes (name order is canonical and hashed)
# ---------------------------------------------------------------------------

COALITION_IDS: tuple[str, ...] = (
    "reform_technocratic",
    "administrative_conservative",
    "social_contract_pragmatist",
    "sectoral_industrial",
)
W: int = len(COALITION_IDS)

POLITICAL_FEATURE_IDS: tuple[str, ...] = (
    "growth",
    "shortage",
    "debt_pressure",
    "worker_unrest",
    "contract_gap",
    "soviet_constraint",
    "external_pressure",
    "previous_policy_error",
    "elite_cohesion",
    "technology_capacity",
)
F: int = len(POLITICAL_FEATURE_IDS)

INTERACTION_IDS: tuple[str, ...] = ("growth_bad_soviet", "growth_bad_information")
F_INTERACTION: int = len(INTERACTION_IDS)

BROKER_OBJECTIVE_IDS: tuple[str, ...] = (
    "regime_stability",
    "soviet_acceptability",
    "living_standards",
    "elite_cohesion",
    "economic_viability",
)
J: int = len(BROKER_OBJECTIVE_IDS)

INFORMATION_DIMENSION_IDS: tuple[str, ...] = (
    "data_latency",
    "measurement_error",
    "forecast_accuracy",
    "optimization_capacity",
    "inventory_visibility",
    "reporting_speed",
    "computational_cost",
)
I: int = len(INFORMATION_DIMENSION_IDS)  # noqa: E741

OPPOSITION_AXIS_IDS: tuple[str, ...] = (
    "network_size",
    "intellectual_density",
    "worker_linkage",
    "samizdat_capacity",
    "foreign_linkage",
    "repression_exposure",
    "perceived_efficacy",
)
V: int = len(OPPOSITION_AXIS_IDS)

POLICY_COORDINATES: tuple[str, ...] = (
    "plan_utilization",
    "enterprise_autonomy",
    "investment_intensity",
    "industrial_priority",
    "admin_price_factor",
    "wage_factor",
    "credit_fraction",
    "budget_hardness",
    "housing_factor",
    "borrowing_factor",
    "consumer_import_factor",
    "second_economy_tolerance",
    "welfare_provision",
    "private_autonomy",
    "cultural_openness",
    "supported_boundary",
    "tolerance_boundary",
    "repression",
    "information_investment",
)
U: int = len(POLICY_COORDINATES)  # 19

POLICY_BOUNDS: dict[str, tuple[float, float]] = {
    "plan_utilization": (0.1, 1.0),
    "enterprise_autonomy": (0.0, 1.0),
    "investment_intensity": (0.0, 2.0),
    "industrial_priority": (0.0, 1.0),
    "admin_price_factor": (0.5, 2.0),
    "wage_factor": (0.5, 2.0),
    "credit_fraction": (0.0, 1.0),
    "budget_hardness": (0.0, 1.0),
    "housing_factor": (0.0, 2.0),
    "borrowing_factor": (0.0, 2.0),
    "consumer_import_factor": (0.0, 2.0),
    "second_economy_tolerance": (0.0, 1.0),
    "welfare_provision": (0.0, 1.0),
    "private_autonomy": (0.0, 1.0),
    "cultural_openness": (0.0, 1.0),
    "supported_boundary": (0.0, 1.0),
    "tolerance_boundary": (0.0, 1.0),
    "repression": (0.0, 1.0),
    "information_investment": (0.0, 1.0),
}

SIGNAL_CHANNELS: tuple[str, ...] = (
    "western_comparison",
    "official_policy",
    "opposition_success",
    "public_action_risk",
    "foreign_linkage",
    "intellectual_linkage",
    "worker_linkage",
    "regime_threat",
    "repression_cost",
)

#: Channels consumed directly from the immutable external world by the state /
#: broker (never filtered by domestic 3T censorship).
GOVERNMENT_CHANNELS: frozenset[str] = frozenset({"regime_threat", "repression_cost"})

#: Channels whose effect reaches households / opposition only after 3T filtering.
SOCIETAL_CHANNELS: frozenset[str] = frozenset(
    {
        "western_comparison",
        "official_policy",
        "opposition_success",
        "foreign_linkage",
        "intellectual_linkage",
        "worker_linkage",
    }
)

EXTERNAL_VARIABLE_IDS: tuple[str, ...] = (
    "world_oil_price",
    "global_usd_rate",
    "official_fx",
    "cmea_energy_price",
    "soviet_energy_availability",
    "western_demand",
    "cmea_demand",
    "western_inflation",
    "international_credit_availability",
    "technology_access",
    "geopolitical_tension",
    "soviet_constraint",
)

#: Variables whose quarter may legitimately be missing (legacy FX / CMEA windows).
EXTERNAL_OPTIONAL_VARIABLES: frozenset[str] = frozenset({"official_fx", "cmea_energy_price"})

#: What a political InterventionSpec may address (no inventories/debt/capacity).
INTERVENTION_POLICY_PREFIX = "policy."
INTERVENTION_TARGETS: frozenset[str] = frozenset(
    {
        "coalition_weights",
        "broker.objective_weights",
        "technology.capability",
        "soviet_constraint_multiplier",
        "information.broadcast",
    }
)

# ---------------------------------------------------------------------------
# Policy vector (tools, not realized outcomes)
# ---------------------------------------------------------------------------


class PolicyVector(StrictModel):
    """Complete 19-coordinate domestic policy vector (per-quarter, piecewise)."""

    plan_utilization: FiniteFloat
    enterprise_autonomy: FiniteFloat
    investment_intensity: FiniteFloat
    industrial_priority: FiniteFloat
    admin_price_factor: FiniteFloat
    wage_factor: FiniteFloat
    credit_fraction: FiniteFloat
    budget_hardness: FiniteFloat
    housing_factor: FiniteFloat
    borrowing_factor: FiniteFloat
    consumer_import_factor: FiniteFloat
    second_economy_tolerance: FiniteFloat
    welfare_provision: FiniteFloat
    private_autonomy: FiniteFloat
    cultural_openness: FiniteFloat
    supported_boundary: FiniteFloat
    tolerance_boundary: FiniteFloat
    repression: FiniteFloat
    information_investment: FiniteFloat

    @model_validator(mode="after")
    def _check_bounds(self) -> Self:
        for name, (low, high) in POLICY_BOUNDS.items():
            value = float(getattr(self, name))
            if not low - 1e-12 <= value <= high + 1e-12:
                raise ConfigError(
                    f"policy.{name}={value} lies outside its declared bounds [{low}, {high}]"
                )
        if self.supported_boundary > self.tolerance_boundary + 1e-12:
            raise ConfigError("policy.supported_boundary must not exceed policy.tolerance_boundary")
        return self

    def to_vector(self) -> np.ndarray:
        return np.array([getattr(self, name) for name in POLICY_COORDINATES], dtype=np.float64)

    def normalized(self) -> np.ndarray:
        return normalize_policy_vector(self.to_vector())

    @classmethod
    def from_vector(cls, values: np.ndarray) -> PolicyVector:
        array = np.asarray(values, dtype=np.float64)
        if array.shape != (U,):
            raise ConfigError(f"policy vector must have shape ({U},), got {array.shape}")
        return cls(**{name: float(array[index]) for index, name in enumerate(POLICY_COORDINATES)})

    def patch(self, changes: dict[str, float]) -> PolicyVector:
        unknown = sorted(set(changes) - set(POLICY_COORDINATES))
        if unknown:
            raise ConfigError(f"policy patch references unknown coordinates: {unknown}")
        updated = self.model_dump()
        updated.update(changes)
        return PolicyVector.model_validate(updated)


def policy_bounds_arrays() -> tuple[np.ndarray, np.ndarray]:
    lower = np.array([POLICY_BOUNDS[name][0] for name in POLICY_COORDINATES], dtype=np.float64)
    upper = np.array([POLICY_BOUNDS[name][1] for name in POLICY_COORDINATES], dtype=np.float64)
    return lower, upper


def normalize_policy_vector(values: np.ndarray) -> np.ndarray:
    """Map a raw policy vector into [0, 1]^U using the declared bounds."""
    lower, upper = policy_bounds_arrays()
    safe = np.maximum(upper - lower, 1e-12)
    return np.clip((np.asarray(values, dtype=np.float64) - lower) / safe, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Policy replay input (Mode A)
# ---------------------------------------------------------------------------


class DatePrecision(StrEnum):
    EXACT_QUARTER = "exact_quarter"
    RECONSTRUCTED_QUARTER = "reconstructed_quarter"


class PolicyReplayRecord(StrictModel):
    """One piecewise-constant domestic policy change-point (Mode A input)."""

    record_id: str = Field(min_length=1)
    effective_quarter: QuarterLike
    patch: dict[str, FiniteFloat] = Field(min_length=1)
    date_precision: DatePrecision
    date_evidence: list[str] = Field(min_length=1)
    magnitude_evidence_status: EvidenceStatus
    notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_patch(self) -> Self:
        unknown = sorted(set(self.patch) - set(POLICY_COORDINATES))
        if unknown:
            raise ConfigError(
                f"replay record {self.record_id} patches unknown coordinates: {unknown}"
            )
        return self


class PolicyReplayRegistry(StrictModel):
    """Declared domestic-policy replay registry (Mode A only)."""

    input_channel: Literal["domestic_policy_replay"] = "domestic_policy_replay"
    initial_policy: PolicyVector
    records: list[PolicyReplayRecord] = Field(default_factory=list)
    coverage_note: str = Field(min_length=1)
    schedule_sha256: str | None = None

    @model_validator(mode="after")
    def _check_records(self) -> Self:
        seen: set[tuple[int, str]] = set()
        for record in self.records:
            for coordinate in record.patch:
                key = (record.effective_quarter.to_ordinal(), coordinate)
                if key in seen:
                    raise ConfigError(
                        f"replay registry repeats quarter/coordinate {key} "
                        f"(record {record.record_id})"
                    )
                seen.add(key)
        return self

    def compiled_schedule(self, quarters: tuple[str, ...]) -> dict[str, list[float]]:
        """Compile the piecewise-constant complete vector per field.

        A missing change-point means "carry the previous policy", never
        interpolation.
        """
        schedule: dict[str, list[float]] = {name: [] for name in POLICY_COORDINATES}
        current = self.initial_policy.model_dump()
        by_quarter: dict[int, list[PolicyReplayRecord]] = {}
        for record in self.records:
            by_quarter.setdefault(record.effective_quarter.to_ordinal(), []).append(record)
        for quarter in quarters:
            ordinal = Quarter.parse(quarter).to_ordinal()
            for record in sorted(by_quarter.get(ordinal, []), key=lambda r: r.record_id):
                current.update(record.patch)
            PolicyVector.model_validate(current)  # re-validate bounds at each step
            for name in POLICY_COORDINATES:
                schedule[name].append(float(current[name]))
        return schedule


# ---------------------------------------------------------------------------
# Political parameter blocks (all latent; flattened with p04.* keys)
# ---------------------------------------------------------------------------


class CoalitionParameters(StrictModel):
    """Latent coalition-update coefficients (signed; direction not pre-set)."""

    intercept: list[FiniteFloat] = Field(default=[0.0] * W, min_length=W, max_length=W)
    beta: list[list[FiniteFloat]] = Field(default_factory=lambda: [[0.0] * F for _ in range(W)])
    interaction: list[list[FiniteFloat]] = Field(
        default_factory=lambda: [[0.0] * F_INTERACTION for _ in range(W)]
    )
    learning_rate: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.1
    eps: Annotated[FiniteFloat, Field(gt=0.0)] = 1e-12

    @model_validator(mode="after")
    def _check_shape(self) -> Self:
        if len(self.beta) != W or any(len(row) != F for row in self.beta):
            raise ConfigError(f"coalition.beta must be {W}x{F}")
        if len(self.interaction) != W or any(len(row) != F_INTERACTION for row in self.interaction):
            raise ConfigError(f"coalition.interaction must be {W}x{F_INTERACTION}")
        for name, matrix, bound in (
            ("beta", self.beta, 2.0),
            ("interaction", self.interaction, 2.0),
        ):
            for row in matrix:
                if any(abs(value) > bound + 1e-12 for value in row):
                    raise ConfigError(f"coalition.{name} entries must lie in [-{bound}, {bound}]")
        if any(abs(value) > 2.0 + 1e-12 for value in self.intercept):
            raise ConfigError("coalition.intercept entries must lie in [-2, 2]")
        return self

    def flatten(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for w, name in enumerate(COALITION_IDS):
            out[f"intercept.{name}"] = float(self.intercept[w])
            for f, feature in enumerate(POLITICAL_FEATURE_IDS):
                out[f"beta.{name}.{feature}"] = float(self.beta[w][f])
            for i, interaction in enumerate(INTERACTION_IDS):
                out[f"interaction.{name}.{interaction}"] = float(self.interaction[w][i])
        out["learning_rate"] = float(self.learning_rate)
        return out


class BrokerParameters(StrictModel):
    """Latent leadership-broker utility coefficients (structural surrogate)."""

    A: list[list[FiniteFloat]] = Field(default_factory=lambda: [[0.0] * U for _ in range(J)])
    q: list[FiniteFloat] = Field(default=[1.0] * J, min_length=J, max_length=J)
    target_base: list[FiniteFloat] = Field(
        default=[1.0, -1.0, 1.0, 0.5, 0.5], min_length=J, max_length=J
    )
    target_response: list[list[FiniteFloat]] = Field(
        default_factory=lambda: [[0.0] * F for _ in range(J)]
    )
    cohesion_penalty: Annotated[FiniteFloat, Field(ge=0.0)] = 0.1
    inertia_penalty: Annotated[FiniteFloat, Field(ge=0.0)] = 0.1
    repression_cost_penalty: Annotated[FiniteFloat, Field(ge=0.0)] = 0.1
    cohesion_alpha: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.1
    soviet_floor: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.2
    ideals: list[list[FiniteFloat]] = Field(default_factory=lambda: [[0.0] * U for _ in range(W)])
    objective_ids: list[str] = Field(default=list(BROKER_OBJECTIVE_IDS), min_length=J, max_length=J)

    @model_validator(mode="after")
    def _check_shape(self) -> Self:
        if len(self.A) != J or any(len(row) != U for row in self.A):
            raise ConfigError(f"broker.A must be {J}x{U}")
        if len(self.target_response) != J or any(len(row) != F for row in self.target_response):
            raise ConfigError(f"broker.target_response must be {J}x{F}")
        if len(self.ideals) != W or any(len(row) != U for row in self.ideals):
            raise ConfigError(f"broker.ideals must be {W}x{U}")
        if tuple(self.objective_ids) != BROKER_OBJECTIVE_IDS:
            raise ConfigError("broker.objective_ids must equal the declared objective axis")
        for row in self.target_response:
            if any(abs(value) > 2.0 + 1e-12 for value in row):
                raise ConfigError("broker.target_response entries must lie in [-2, 2]")
        for name, values in (("q", self.q), ("target_base", self.target_base)):
            if any(abs(value) > 2.0 + 1e-12 for value in values):
                raise ConfigError(f"broker.{name} entries must lie in [-2, 2]")
        return self

    def flatten(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for j, objective in enumerate(BROKER_OBJECTIVE_IDS):
            for u, coordinate in enumerate(POLICY_COORDINATES):
                out[f"A.{objective}.{coordinate}"] = float(self.A[j][u])
            out[f"q.{objective}"] = float(self.q[j])
            out[f"target_base.{objective}"] = float(self.target_base[j])
            for f, feature in enumerate(POLITICAL_FEATURE_IDS):
                out[f"target_response.{objective}.{feature}"] = float(self.target_response[j][f])
        out["cohesion_penalty"] = float(self.cohesion_penalty)
        out["inertia_penalty"] = float(self.inertia_penalty)
        out["repression_cost_penalty"] = float(self.repression_cost_penalty)
        out["cohesion_alpha"] = float(self.cohesion_alpha)
        out["soviet_floor"] = float(self.soviet_floor)
        for w, name in enumerate(COALITION_IDS):
            for u, coordinate in enumerate(POLICY_COORDINATES):
                out[f"ideal.{name}.{coordinate}"] = float(self.ideals[w][u])
        return out


class InformationParameters(StrictModel):
    """Latent information-capability mapping (channel-only; never productivity)."""

    depreciation: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.0
    learning: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.1
    information_investment_weight: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 1.0
    latency_scale: Annotated[FiniteFloat, Field(gt=0.0)] = 4.0
    reporting_scale: Annotated[FiniteFloat, Field(gt=0.0)] = 4.0
    measurement_sigma: Annotated[FiniteFloat, Field(ge=0.0)] = 0.1
    lag_cap: Annotated[int, Field(strict=True, ge=0)] = 8
    computational_cost_scale: Annotated[FiniteFloat, Field(gt=0.0)] = 1.0

    def flatten(self) -> dict[str, float]:
        return {
            "depreciation": float(self.depreciation),
            "learning": float(self.learning),
            "information_investment_weight": float(self.information_investment_weight),
            "latency_scale": float(self.latency_scale),
            "reporting_scale": float(self.reporting_scale),
            "measurement_sigma": float(self.measurement_sigma),
            "lag_cap": float(self.lag_cap),
            "computational_cost_scale": float(self.computational_cost_scale),
        }


class ObservationParameters(StrictModel):
    """State-observation parameters: measurement error and strategic bias."""

    noise_scale: list[FiniteFloat] = Field(default=[1.0] * F, min_length=F, max_length=F)
    declared_scale: list[FiniteFloat] = Field(default=[1.0] * F, min_length=F, max_length=F)
    ring_length: Annotated[int, Field(strict=True, ge=1)] = 9
    bias_incentive_loading: Annotated[FiniteFloat, Field(ge=0.0)] = 0.0
    initial_overstatement: Annotated[FiniteFloat, Field(ge=0.0)] = 0.2
    initial_concealment: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.2
    initial_misstatement: Annotated[FiniteFloat, Field(ge=-1.0, le=1.0)] = 0.0
    #: (F, 3) projection of normalized need/inventory/capacity discrepancy.
    feature_bias_loading: list[list[FiniteFloat]] = Field(
        default_factory=lambda: [[0.0, 0.0, 0.0] for _ in range(F)]
    )
    need_reference: Annotated[FiniteFloat, Field(gt=0.0)] = 1.0
    inventory_reference: Annotated[FiniteFloat, Field(gt=0.0)] = 1.0
    capacity_reference: Annotated[FiniteFloat, Field(gt=0.0)] = 1.0

    @model_validator(mode="after")
    def _check_shape(self) -> Self:
        if len(self.feature_bias_loading) != F or any(
            len(row) != 3 for row in self.feature_bias_loading
        ):
            raise ConfigError(f"observation.feature_bias_loading must be {F}x3")
        if any(value < 0.0 for value in self.noise_scale):
            raise ConfigError("observation.noise_scale must be non-negative")
        return self

    def flatten(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for index, feature in enumerate(POLITICAL_FEATURE_IDS):
            out[f"noise_scale.{feature}"] = float(self.noise_scale[index])
            out[f"declared_scale.{feature}"] = float(self.declared_scale[index])
            for k, label in enumerate(("need", "inventory", "capacity")):
                out[f"feature_bias_loading.{feature}.{label}"] = float(
                    self.feature_bias_loading[index][k]
                )
        out["ring_length"] = float(self.ring_length)
        out["bias_incentive_loading"] = float(self.bias_incentive_loading)
        out["initial_overstatement"] = float(self.initial_overstatement)
        out["initial_concealment"] = float(self.initial_concealment)
        out["initial_misstatement"] = float(self.initial_misstatement)
        out["need_reference"] = float(self.need_reference)
        out["inventory_reference"] = float(self.inventory_reference)
        out["capacity_reference"] = float(self.capacity_reference)
        return out


class CultureParameters(StrictModel):
    """Low-dimensional culture / Western-exposure kernel coefficients."""

    identification_alpha: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.1
    official_loading: Annotated[FiniteFloat, Field(ge=-2.0, le=2.0)] = 0.1
    western_loading: Annotated[FiniteFloat, Field(ge=-2.0, le=2.0)] = 0.1
    initial_ideology: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.5
    exposure_alpha: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.1
    initial_exposure: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.05
    supported_multiplier: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 1.0
    tolerated_multiplier: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 0.5
    prohibited_multiplier: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 0.0

    def flatten(self) -> dict[str, float]:
        return {
            "identification_alpha": float(self.identification_alpha),
            "official_loading": float(self.official_loading),
            "western_loading": float(self.western_loading),
            "initial_ideology": float(self.initial_ideology),
            "exposure_alpha": float(self.exposure_alpha),
            "initial_exposure": float(self.initial_exposure),
            "supported_multiplier": float(self.supported_multiplier),
            "tolerated_multiplier": float(self.tolerated_multiplier),
            "prohibited_multiplier": float(self.prohibited_multiplier),
        }


class OppositionParameters(StrictModel):
    """County opposition-capacity kernel coefficients (capacity, not headcounts)."""

    alpha: list[FiniteFloat] = Field(default=[0.1] * V, min_length=V, max_length=V)
    initial_state: list[FiniteFloat] = Field(
        default=[0.1, 0.0, 0.0, 0.1, 0.1, 0.1, 0.1], min_length=V, max_length=V
    )
    formation_rate: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 0.2
    attrition_rate: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 0.2
    samizdat_tolerance_weight: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 1.0
    samizdat_charter_weight: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 0.5
    foreign_western_weight: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 1.0
    foreign_linkage_weight: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 0.5
    efficacy_success_weight: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 1.0
    efficacy_risk_weight: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 1.0
    exposure_repression_weight: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 1.0
    exposure_decay: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.1
    household_exposure_alpha: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.1
    household_efficacy_alpha: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.1
    action_risk_weight: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 1.0
    formation_input_scale: Annotated[FiniteFloat, Field(gt=0.0)] = 1.0

    @model_validator(mode="after")
    def _check(self) -> Self:
        if any(not 0.0 <= value <= 1.0 for value in self.initial_state):
            raise ConfigError("opposition.initial_state entries must lie in [0, 1]")
        if any(not 0.0 <= value <= 1.0 for value in self.alpha):
            raise ConfigError("opposition.alpha entries must lie in [0, 1]")
        return self

    def flatten(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for index, axis in enumerate(OPPOSITION_AXIS_IDS):
            out[f"alpha.{axis}"] = float(self.alpha[index])
            out[f"initial_state.{axis}"] = float(self.initial_state[index])
        for name in (
            "formation_rate",
            "attrition_rate",
            "samizdat_tolerance_weight",
            "samizdat_charter_weight",
            "foreign_western_weight",
            "foreign_linkage_weight",
            "efficacy_success_weight",
            "efficacy_risk_weight",
            "exposure_repression_weight",
            "exposure_decay",
            "household_exposure_alpha",
            "household_efficacy_alpha",
            "action_risk_weight",
            "formation_input_scale",
        ):
            out[name] = float(getattr(self, name))
        return out


class ExternalRecipeParameters(StrictModel):
    """Latent external-signal recipe (loadings/decay; never a magic constant)."""

    signal_persistence: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.8
    signal_clip: Annotated[FiniteFloat, Field(gt=0.0)] = 1.0
    default_loading: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 0.2
    base_energy_quota: Annotated[FiniteFloat, Field(ge=0.0)] = 1.0
    base_western_demand: Annotated[FiniteFloat, Field(ge=0.0)] = 1.0
    base_cmea_demand: Annotated[FiniteFloat, Field(ge=0.0)] = 1.0
    base_western_inflation: Annotated[FiniteFloat, Field(gt=-100.0)] = 0.0
    base_credit_availability: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 1.0
    base_technology_access: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.5
    base_geopolitical_tension: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.3
    base_soviet_constraint: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.5
    western_price_index_initial: Annotated[FiniteFloat, Field(gt=0.0)] = 1.0
    tension_regime_weight: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 0.5
    debt_reference: Annotated[FiniteFloat, Field(gt=0.0)] = 10000.0
    soviet_constraint_multiplier: Annotated[FiniteFloat, Field(ge=0.0, le=2.0)] = 1.0
    signal_upper: Annotated[FiniteFloat, Field(gt=0.0, le=10.0)] = 1.0
    signal_lower: Annotated[FiniteFloat, Field(ge=-10.0, lt=0.0)] = -1.0

    def flatten(self) -> dict[str, float]:
        return {
            name: float(getattr(self, name))
            for name in (
                "signal_persistence",
                "signal_clip",
                "default_loading",
                "base_energy_quota",
                "base_western_demand",
                "base_cmea_demand",
                "base_western_inflation",
                "base_credit_availability",
                "base_technology_access",
                "base_geopolitical_tension",
                "base_soviet_constraint",
                "western_price_index_initial",
                "tension_regime_weight",
                "debt_reference",
                "soviet_constraint_multiplier",
                "signal_upper",
                "signal_lower",
            )
        }


class PoliticalParameters(StrictModel):
    """Complete P04 parameter block (nested; flattened into the run hash)."""

    role: Literal["latent_parameter"] = "latent_parameter"
    evidence_status: Literal["structural_assumption"] = "structural_assumption"
    calibration_status: Literal["not_calibrated"] = "not_calibrated"
    sensitivity_status: Literal["not_assessed"] = "not_assessed"
    notes: str = (
        "P04 political/external/information engineering fixtures; latent, not "
        "calibrated against any observed Hungarian series and carrying no "
        "historical-probability claim."
    )
    coalition: CoalitionParameters = Field(default_factory=CoalitionParameters)
    broker: BrokerParameters = Field(default_factory=BrokerParameters)
    information: InformationParameters = Field(default_factory=InformationParameters)
    observation: ObservationParameters = Field(default_factory=ObservationParameters)
    culture: CultureParameters = Field(default_factory=CultureParameters)
    opposition: OppositionParameters = Field(default_factory=OppositionParameters)
    external_recipe: ExternalRecipeParameters = Field(default_factory=ExternalRecipeParameters)

    def flatten(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for module in (
            "coalition",
            "broker",
            "information",
            "observation",
            "culture",
            "opposition",
            "external_recipe",
        ):
            group = getattr(self, module)
            for key, value in group.flatten().items():
                out[f"p04.{module}.{key}"] = float(value)
        return out


def default_coalition_parameters() -> CoalitionParameters:
    """Deterministic engineering defaults that only prove the interface works."""
    beta = [[0.0] * F for _ in range(W)]
    beta[COALITION_IDS.index("reform_technocratic")][POLITICAL_FEATURE_IDS.index("growth")] = -0.5
    beta[COALITION_IDS.index("administrative_conservative")][
        POLITICAL_FEATURE_IDS.index("growth")
    ] = -0.5
    beta[COALITION_IDS.index("social_contract_pragmatist")][
        POLITICAL_FEATURE_IDS.index("contract_gap")
    ] = 1.0
    beta[COALITION_IDS.index("sectoral_industrial")][POLITICAL_FEATURE_IDS.index("shortage")] = 0.5
    interaction = [[0.0] * F_INTERACTION for _ in range(W)]
    interaction[COALITION_IDS.index("reform_technocratic")][0] = -1.0
    interaction[COALITION_IDS.index("administrative_conservative")][0] = 1.0
    interaction[COALITION_IDS.index("reform_technocratic")][1] = 1.0
    interaction[COALITION_IDS.index("administrative_conservative")][1] = -1.0
    return CoalitionParameters(beta=beta, interaction=interaction)


def _identity_broker_A() -> list[list[float]]:
    A = [[0.0] * U for _ in range(J)]

    def set_objective(objective: str, weights: dict[str, float]) -> None:
        row = A[BROKER_OBJECTIVE_IDS.index(objective)]
        for coordinate, weight in weights.items():
            row[POLICY_COORDINATES.index(coordinate)] = weight

    set_objective(
        "regime_stability",
        {"welfare_provision": 1 / 3, "private_autonomy": 1 / 3, "cultural_openness": 1 / 3},
    )
    set_objective("soviet_acceptability", {"enterprise_autonomy": -1.0})
    set_objective(
        "living_standards",
        {
            "wage_factor": 1 / 3,
            "housing_factor": 1 / 3,
            "consumer_import_factor": 1 / 3,
        },
    )
    set_objective("elite_cohesion", {"supported_boundary": 0.5, "tolerance_boundary": 0.5})
    set_objective("economic_viability", {"budget_hardness": 0.5, "information_investment": 0.5})
    return A


def default_broker_parameters(initial_policy: PolicyVector) -> BrokerParameters:
    """Deterministic broker defaults with the declared faction ideals."""
    base = initial_policy.to_vector()
    ideals = np.tile(base, (W, 1))
    coordinates = {name: index for index, name in enumerate(POLICY_COORDINATES)}

    def ideal(name: str) -> np.ndarray:
        return ideals[COALITION_IDS.index(name)]

    ideal("reform_technocratic")[coordinates["enterprise_autonomy"]] = 0.8
    ideal("reform_technocratic")[coordinates["budget_hardness"]] = 0.2
    ideal("reform_technocratic")[coordinates["information_investment"]] = 0.8
    ideal("reform_technocratic")[coordinates["cultural_openness"]] = 0.7
    ideal("administrative_conservative")[coordinates["enterprise_autonomy"]] = 0.1
    ideal("administrative_conservative")[coordinates["repression"]] = 0.8
    ideal("administrative_conservative")[coordinates["cultural_openness"]] = 0.2
    ideal("administrative_conservative")[coordinates["industrial_priority"]] = 1.0
    ideal("social_contract_pragmatist")[coordinates["wage_factor"]] = 1.2
    ideal("social_contract_pragmatist")[coordinates["housing_factor"]] = 1.2
    ideal("social_contract_pragmatist")[coordinates["welfare_provision"]] = 0.8
    ideal("social_contract_pragmatist")[coordinates["budget_hardness"]] = 0.0
    ideal("social_contract_pragmatist")[coordinates["second_economy_tolerance"]] = 0.8
    ideal("sectoral_industrial")[coordinates["investment_intensity"]] = 1.5
    ideal("sectoral_industrial")[coordinates["credit_fraction"]] = 0.8
    ideal("sectoral_industrial")[coordinates["industrial_priority"]] = 1.0
    target_response = [[0.0] * F for _ in range(J)]
    target_response[BROKER_OBJECTIVE_IDS.index("living_standards")][
        POLITICAL_FEATURE_IDS.index("contract_gap")
    ] = -0.5
    target_response[BROKER_OBJECTIVE_IDS.index("economic_viability")][
        POLITICAL_FEATURE_IDS.index("debt_pressure")
    ] = 0.5
    return BrokerParameters(
        A=_identity_broker_A(),
        target_response=target_response,
        ideals=ideals.tolist(),
    )


def resolve_political_parameters(
    parameters: PoliticalParameters, initial_policy: PolicyVector
) -> PoliticalParameters:
    """Fill the declared engineering defaults for an all-zero parameter block.

    A scenario may declare ``parameters: {}``; the engine then substitutes the
    declared structural fixtures: the direction-reversal coalition betas, the
    faction ideals anchored on the scenario's *initial* policy vector, and the
    state-feature strategic-bias loading.  Every substituted value is still a
    latent, not_calibrated engineering fixture.
    """
    changes: dict[str, object] = {}
    coalition = parameters.coalition
    if (
        not any(coalition.intercept)
        and not any(any(row) for row in coalition.beta)
        and not any(any(row) for row in coalition.interaction)
    ):
        changes["coalition"] = default_coalition_parameters()
    broker = parameters.broker
    if not any(any(row) for row in broker.A):
        changes["broker"] = default_broker_parameters(initial_policy)
    observation = parameters.observation
    if not any(any(row) for row in observation.feature_bias_loading):
        changes["observation"] = observation.model_copy(
            update={"feature_bias_loading": default_feature_bias_loading()}
        )
    if not changes:
        return parameters
    return parameters.model_copy(update=changes)


def default_feature_bias_loading() -> list[list[float]]:
    """Declared (F, 3) state-feature strategic-bias projection (fixture)."""
    loading = [[0.0, 0.0, 0.0] for _ in range(F)]
    loading[POLITICAL_FEATURE_IDS.index("shortage")] = [0.5, 0.5, 0.0]
    loading[POLITICAL_FEATURE_IDS.index("growth")] = [0.0, 0.0, 0.5]
    return loading


# ---------------------------------------------------------------------------
# External event registry (loaded from data/manifests/external_events.yml)
# ---------------------------------------------------------------------------


class EvidenceLevel(StrEnum):
    RECONSTRUCTED = "reconstructed"
    STRUCTURAL = "structural"


class EventSpec(StrictModel):
    """One declared discrete external-history event (explicit channels only)."""

    event_id: str = Field(min_length=1)
    start: QuarterLike
    end: QuarterLike
    pulse: bool = False
    date_precision: DatePrecision
    date_evidence: list[str] = Field(min_length=1)
    economic_series_refs: list[str] = Field(default_factory=list)
    signal_channels: list[str] = Field(min_length=1)
    broadcast_ids: list[str] = Field(default_factory=list)
    mapping_parameter_paths: list[str] = Field(default_factory=list)
    notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.end.to_ordinal() < self.start.to_ordinal():
            raise ConfigError(f"event {self.event_id} ends before it starts")
        if self.pulse and self.start.to_ordinal() != self.end.to_ordinal():
            raise ConfigError(f"pulse event {self.event_id} must span exactly one quarter")
        unknown = sorted(set(self.signal_channels) - set(SIGNAL_CHANNELS))
        if unknown:
            raise ConfigError(
                f"event {self.event_id} references unknown signal channel(s) {unknown}"
            )
        if len(set(self.signal_channels)) != len(self.signal_channels):
            raise ConfigError(f"event {self.event_id} repeats a signal channel")
        for ref in self.economic_series_refs:
            if ref not in EXTERNAL_VARIABLE_IDS:
                raise ConfigError(
                    f"event {self.event_id} references unknown external series {ref!r}"
                )
        return self

    def active(self, quarter: Quarter) -> bool:
        return self.start.to_ordinal() <= quarter.to_ordinal() <= self.end.to_ordinal()

    def quarters(self) -> int:
        return self.end.to_ordinal() - self.start.to_ordinal() + 1


class EventRegistry(StrictModel):
    """The frozen 16-event external chronology (explicit channels only)."""

    schema_version: Literal["1"] = "1"
    events: list[EventSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_unique(self) -> Self:
        ids = [event.event_id for event in self.events]
        if len(set(ids)) != len(ids):
            raise ConfigError("external event registry repeats an event_id")
        return self

    def by_id(self) -> dict[str, EventSpec]:
        return {event.event_id: event for event in self.events}


# ---------------------------------------------------------------------------
# External world pack / slice
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExternalWorldPack:
    """Immutable quarterly external world for the whole horizon (A/B/C shared)."""

    quarters: tuple[str, ...]
    variable_ids: tuple[str, ...]
    values: np.ndarray  # float64 (T, V) with NaN for declared-missing cells
    origins: list[dict[str, str]]  # per (t, v): origin artifact/parameter path
    evidence_status: list[dict[str, str]]
    units: tuple[str, ...]
    information_program_path: str | None
    information_program_sha256: str | None
    input_artifact_hashes: dict[str, str]
    pack_hash: str

    def slice(self, tick: int) -> ExternalWorldSlice:
        if not 0 <= tick < len(self.quarters):
            raise ConfigError(f"external tick {tick} outside the pack horizon")
        row = {
            name: float(self.values[tick, index]) for index, name in enumerate(self.variable_ids)
        }
        return ExternalWorldSlice(
            quarter=self.quarters[tick],
            values=row,
            origins=self.origins[tick],
            evidence_status=self.evidence_status[tick],
        )


@dataclass(frozen=True)
class ExternalWorldSlice:
    """Read-only external world for one run boundary."""

    quarter: str
    values: dict[str, float]
    origins: dict[str, str]
    evidence_status: dict[str, str]

    def get(self, variable_id: str, default: float | None = None) -> float:
        value = self.values.get(variable_id, float("nan"))
        if value != value:  # NaN -> declared-default or refuse
            if default is None:
                raise ConfigError(f"external variable {variable_id} missing with no default")
            return float(default)
        return float(value)


# ---------------------------------------------------------------------------
# Political run specification / interventions / branch
# ---------------------------------------------------------------------------


class PoliticalInitialRecipe(StrictModel):
    """Declared latent political initial conditions (grade S)."""

    role: Literal["initial_state"] = "initial_state"
    grade: Literal["S"] = "S"
    evidence_status: Literal["structural_assumption"] = "structural_assumption"
    observation_at: None = None
    coalition_weights: list[FiniteFloat] = Field(
        default=[0.25, 0.25, 0.25, 0.25], min_length=W, max_length=W
    )
    elite_cohesion: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 1.0
    information_capability: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.2

    @model_validator(mode="after")
    def _check_weights(self) -> Self:
        weights = np.asarray(self.coalition_weights, dtype=np.float64)
        if np.any(weights < 0.0):
            raise ConfigError("political initial coalition weights must be non-negative")
        if not np.isclose(float(weights.sum()), 1.0, atol=1e-9):
            raise ConfigError("political initial coalition weights must sum to one")
        return self

    def flatten(self) -> dict[str, float]:
        out = {
            f"coalition_weights.{name}": float(value)
            for name, value in zip(COALITION_IDS, self.coalition_weights, strict=True)
        }
        out["elite_cohesion"] = float(self.elite_cohesion)
        out["information_capability"] = float(self.information_capability)
        return out


class PoliticalRunSpec(StrictModel):
    """Scenario-side P04 declaration; ``None`` means the layer is disabled."""

    mode: PoliticalMode
    external_pack: str = Field(min_length=1)
    event_registry: str = Field(min_length=1)
    replay_registry: str | None = None
    initial: PoliticalInitialRecipe = Field(default_factory=PoliticalInitialRecipe)
    parameters: PoliticalParameters = Field(default_factory=PoliticalParameters)
    study_id: str = Field(min_length=1)
    information_program: str | None = None

    @model_validator(mode="after")
    def _check_mode(self) -> Self:
        if self.mode is PoliticalMode.COUNTERFACTUAL:
            raise ConfigError(
                "counterfactual (Mode C) political runs are only created by an explicit "
                "checkpoint fork; a scenario may not declare mode=counterfactual"
            )
        if self.mode is PoliticalMode.HISTORICAL_REPLAY:
            if not self.replay_registry:
                raise ConfigError("Mode A (historical replay) requires a replay_registry")
        elif self.replay_registry:
            raise ConfigError("Mode B (endogenous) must not declare a replay_registry")
        return self


class InterventionOperation(StrEnum):
    SET = "set"
    BROADCAST = "broadcast"


class BroadcastAudience(StrictModel):
    """An intervention broadcast audience selector (all | region_id_in)."""

    all: bool | None = None
    region_id_in: list[str] | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        has_all = bool(self.all)
        has_regions = bool(self.region_id_in)
        if has_all == has_regions:
            raise ConfigError(
                "broadcast audience must select exactly one of all=True / region_id_in"
            )
        if self.region_id_in is not None and len(set(self.region_id_in)) != len(self.region_id_in):
            raise ConfigError("broadcast audience region_id_in repeats a region")
        return self


class BroadcastEnvelope(StrictModel):
    content: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    intensity: Annotated[FiniteFloat, Field(ge=-1.0, le=1.0)]
    content_sensitivity: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]
    audience: BroadcastAudience
    ttl: Annotated[int, Field(strict=True, ge=1)]

    @model_validator(mode="after")
    def _check_channel(self) -> Self:
        if self.channel not in SIGNAL_CHANNELS:
            raise ConfigError(f"broadcast channel {self.channel!r} is not a declared channel")
        return self


class InterventionSpec(StrictModel):
    """One declared counterfactual intervention applied by a fork."""

    intervention_id: str = Field(min_length=1)
    effective_quarter: QuarterLike
    until_quarter: QuarterLike | None = None
    operation: InterventionOperation = InterventionOperation.SET
    target: str = Field(min_length=1)
    value: FiniteFloat | list[FiniteFloat] | BroadcastEnvelope | None = None
    provenance: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.operation is InterventionOperation.BROADCAST:
            if self.target != "information.broadcast":
                raise ConfigError("broadcast operation requires target=information.broadcast")
            if not isinstance(self.value, BroadcastEnvelope):
                raise ConfigError("broadcast operation requires a typed BroadcastEnvelope value")
            if self.until_quarter is not None:
                raise ConfigError(
                    "broadcast TTL alone defines its validity; until_quarter is banned"
                )
            return self
        if self.value is None or isinstance(self.value, BroadcastEnvelope):
            raise ConfigError(f"set operation {self.intervention_id} requires a numeric value")
        if self.target == "information.broadcast":
            raise ConfigError("information.broadcast target only supports operation=broadcast")
        if self.target.startswith(INTERVENTION_POLICY_PREFIX):
            coordinate = self.target[len(INTERVENTION_POLICY_PREFIX) :]
            if coordinate not in POLICY_COORDINATES:
                raise ConfigError(f"intervention target {self.target!r} is not a policy coordinate")
        elif self.target == "coalition_weights":
            if not isinstance(self.value, list) or len(self.value) != W:
                raise ConfigError("coalition_weights intervention requires W weights")
            if self.until_quarter is not None:
                raise ConfigError("coalition_weights is a one-shot set; until_quarter is banned")
        elif self.target == "broker.objective_weights":
            if not isinstance(self.value, list) or len(self.value) != J:
                raise ConfigError("broker.objective_weights requires J weights")
            weights = np.asarray(self.value, dtype=np.float64)
            if np.any(weights < 0.0) or not np.any(weights > 0.0):
                raise ConfigError("broker.objective_weights must be non-negative and non-zero")
        elif self.target == "technology.capability":
            if self.until_quarter is not None:
                raise ConfigError(
                    "technology.capability is a one-shot set; until_quarter is banned"
                )
        elif self.target == "soviet_constraint_multiplier":
            pass
        else:
            raise ConfigError(
                f"intervention target {self.target!r} is outside the declared allowlist"
            )
        if self.until_quarter is not None and (
            self.until_quarter.to_ordinal() < self.effective_quarter.to_ordinal()
        ):
            raise ConfigError("intervention until_quarter precedes effective_quarter")
        if isinstance(self.value, list) and any(
            not isinstance(v, (int, float)) or isinstance(v, bool) for v in self.value
        ):
            raise ConfigError("list intervention values must be numeric")
        return self


class BranchSpec(StrictModel):
    """Recorded identity of a counterfactual fork (Mode C)."""

    branch_id: str = Field(min_length=1)
    source_checkpoint: str = Field(min_length=1)
    source_checkpoint_hash: str = Field(min_length=1)
    parent_run_id: str | None = None
    parent_version_id: str | None = None
    base_mode: PoliticalMode
    boundary_tick: Annotated[int, Field(strict=True, ge=1)]
    external_history_hash: str = Field(min_length=1)
    interventions: list[InterventionSpec] = Field(default_factory=list)
    intervention_hash: str = Field(min_length=1)
    inherited_interventions: list[InterventionSpec] = Field(default_factory=list)
    root_scenario_hash: str = Field(min_length=1)
    root_parameter_hash: str = Field(min_length=1)
    branch_parameter_hash: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Runtime state dataclasses (numpy; never positional-name dependent)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InformationState:
    """Information capability + the seven I dimensions (channel-only)."""

    capability: float
    dimensions: np.ndarray  # float64 (I,)
    total_lag: int


@dataclass
class CoalitionTransition:
    """Result of one coalition update (latent rule result, not a probability)."""

    previous_weights: np.ndarray  # float64 (W,)
    new_weights: np.ndarray  # float64 (W,)
    features_raw: np.ndarray  # float64 (F,)
    features_reported: np.ndarray  # float64 (F,)
    features: np.ndarray  # float64 (F,) clipped
    score: np.ndarray  # float64 (W,)
    contributions: np.ndarray  # float64 (W, F+1) beta/interaction contributions
    feature_valid: np.ndarray  # bool (F,)
    parameter_hash: str


@dataclass
class PolicyDecision:
    """Broker candidate diagnostics + selected policy (Mode B; replay for A)."""

    candidate_ids: list[str]
    candidate_utilities: np.ndarray  # float64 (C,)
    candidate_policies: np.ndarray  # float64 (C, U)
    selected_index: int
    selected_policy: np.ndarray  # float64 (U,)
    binding_constraints: list[str]
    source: str  # "broker" | "replay"
    elite_cohesion: float


@dataclass
class PoliticalFeedback:
    """Lagged domestic features + current external indices for the coalition rule."""

    features_raw: np.ndarray  # float64 (F,)
    features_reported: np.ndarray  # float64 (F,)
    features: np.ndarray  # float64 (F,)
    valid: np.ndarray  # bool (F,)
    growth_undefined: bool
    objective_vector: np.ndarray  # float64 (J,)
    policy_error: float


@dataclass
class PoliticalSignals:
    """Government-external signals separated from filtered societal signals."""

    government: dict[str, float]
    county: np.ndarray  # float64 (R, len(SIGNAL_CHANNELS)) - filtered societal
    delivered: dict[str, float]  # actually-delivered counterfactual intensities


@dataclass(frozen=True)
class TruthSnapshot:
    """Authoritative closing truth for observation (never a decision input)."""

    features: np.ndarray  # float64 (F,) raw true features
    output_value: float
    shortage_denominator_zero: bool
    growth_base_zero: bool


@dataclass
class EnterpriseReports:
    """Per-organization reported need/inventory/capacity (O x G / O)."""

    need: np.ndarray  # float64 (O, G) true input need
    reported_need: np.ndarray  # float64 (O, G)
    inventory: np.ndarray  # float64 (O, G) true own output-pool stock
    reported_inventory: np.ndarray  # float64 (O, G)
    capacity: np.ndarray  # float64 (O,)
    reported_capacity: np.ndarray  # float64 (O,)
    overstatement: float
    concealment: float
    misstatement: float


@dataclass
class StateObservation:
    """One published state observation with its error/bias decomposition."""

    quarter: str
    raw_truth: np.ndarray  # float64 (F,)
    measurement_noise: np.ndarray  # float64 (F,)
    strategic_bias: np.ndarray  # float64 (F,)
    reported: np.ndarray  # float64 (F,)
    published: np.ndarray  # float64 (F,)
    clipping_delta: np.ndarray  # float64 (F,)
    valid: np.ndarray  # bool (F,)
    measurement_quarter: int
    published_quarter: int


@dataclass
class OppositionState:
    """County opposition-capacity state (R x V capacity indices)."""

    capacity: np.ndarray  # float64 (R, V)


@dataclass(frozen=True)
class InformationMessage:
    """One scheduled broadcast with a typed causal signature (never parsed text)."""

    message_id: str
    at_step: int
    ttl: int
    audience_all: bool
    region_ids: tuple[str, ...]
    channel: str
    intensity: float
    content_sensitivity: float
    content: str
    display_only: bool

    def active_at(self, step: int) -> bool:
        return self.at_step <= step < self.at_step + self.ttl


@dataclass(frozen=True)
class InformationProgram:
    """Immutable broadcast program (event information + declared treatments)."""

    messages: tuple[InformationMessage, ...]
    program_hash: str


__all__ = [
    "BROKER_OBJECTIVE_IDS",
    "BroadcastAudience",
    "BroadcastEnvelope",
    "BranchSpec",
    "COALITION_IDS",
    "CoalitionParameters",
    "CoalitionTransition",
    "CultureParameters",
    "DatePrecision",
    "EXTERNAL_OPTIONAL_VARIABLES",
    "EXTERNAL_VARIABLE_IDS",
    "EnterpriseReports",
    "EventRegistry",
    "EventSpec",
    "EvidenceLevel",
    "ExternalRecipeParameters",
    "ExternalWorldPack",
    "ExternalWorldSlice",
    "F",
    "F_INTERACTION",
    "GOVERNMENT_CHANNELS",
    "I",  # noqa: E741 - the declared information-dimension axis count
    "INFORMATION_DIMENSION_IDS",
    "INTERACTION_IDS",
    "INTERVENTION_TARGETS",
    "InformationParameters",
    "InformationMessage",
    "InformationProgram",
    "InformationState",
    "InterventionOperation",
    "InterventionSpec",
    "J",
    "OPPOSITION_AXIS_IDS",
    "ObservationParameters",
    "OppositionParameters",
    "OppositionState",
    "POLICY_BOUNDS",
    "POLICY_COORDINATES",
    "POLITICAL_FEATURE_IDS",
    "PolicyDecision",
    "PolicyReplayRecord",
    "PolicyReplayRegistry",
    "PolicyVector",
    "PoliticalFeedback",
    "PoliticalInitialRecipe",
    "PoliticalParameters",
    "PoliticalRunSpec",
    "PoliticalSignals",
    "SIGNAL_CHANNELS",
    "SOCIETAL_CHANNELS",
    "StateObservation",
    "TruthSnapshot",
    "U",
    "V",
    "W",
    "default_broker_parameters",
    "default_coalition_parameters",
    "default_feature_bias_loading",
    "normalize_policy_vector",
    "policy_bounds_arrays",
    "resolve_political_parameters",
]
