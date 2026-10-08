"""P03 household / social-contract / durables / second-economy contracts.

This module freezes the household consumption ontology, the entitlement axis,
the forced-substitution pairs and the synthetic county population recipe *before*
any household engine module is written.  Every numeric default is a declared
engineering fixture (``structural_assumption / not_calibrated / not_assessed``);
nothing here is a historical Hungarian estimate and no value is attributed to a
literature source.

Axis layout (all multi-axis fields are compiled by *name*, never by position):

* ``H`` — 11 household consumption sub-channels over the eight P02 parent
  commodities; the mapping ``to_material[H, G]`` is a declared synthetic
  equivalent conversion (never a physical meat/nutrition chain);
* ``D`` — 4 durable types (a strict subset of the durable ``H`` channels);
* ``E`` — 7 entitlement components: *experienced outcomes*, never political
  support;
* ``Q`` — 5 allowed one-step forced-substitution pairs, in source-priority
  order.  No pair is recursive, and there is no reverse/upgrade pair.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Literal, Self

import numpy as np
from pydantic import Field, model_validator

from hsm_lab.contract.base import ConfigError, FiniteFloat, StrictModel
from hsm_lab.contract.material import (
    COMMODITY_INDEX,
    P02_COMMODITY_IDS,
    MaterialParameters,
)

# ----------------------------------------------------------------------
# Axes (declared order is canonical and part of every compiled hash)
# ----------------------------------------------------------------------

HOUSEHOLD_GOOD_IDS: tuple[str, ...] = (
    "energy",
    "basic_food",
    "higher_value_food",
    "light_goods",
    "refrigerator",
    "washing_machine",
    "television",
    "passenger_car",
    "personal_services",
    "repair_services",
    "construction_services",
)
H_INDEX: dict[str, int] = {good: index for index, good in enumerate(HOUSEHOLD_GOOD_IDS)}

DURABLE_IDS: tuple[str, ...] = (
    "refrigerator",
    "washing_machine",
    "television",
    "passenger_car",
)
D_INDEX: dict[str, int] = {durable: index for index, durable in enumerate(DURABLE_IDS)}

ENTITLEMENT_IDS: tuple[str, ...] = (
    "job_security",
    "real_consumption",
    "price_stability",
    "housing",
    "welfare",
    "private_autonomy",
    "cultural_openness",
)
E_INDEX: dict[str, int] = {name: index for index, name in enumerate(ENTITLEMENT_IDS)}

SUBSTITUTION_IDS: tuple[str, ...] = (
    "higher_value_food->basic_food",
    "refrigerator->repair_services",
    "washing_machine->repair_services",
    "television->repair_services",
    "passenger_car->repair_services",
)
Q_INDEX: dict[str, int] = {name: index for index, name in enumerate(SUBSTITUTION_IDS)}

HOUSEHOLD_OCCUPATION_IDS: tuple[str, ...] = (
    "industrial_manual",
    "agricultural",
    "service",
    "clerical",
)
HOUSEHOLD_EDUCATION_IDS: tuple[str, ...] = ("primary", "secondary", "tertiary")
HOUSEHOLD_TENURE_IDS: tuple[str, ...] = ("state_rental", "cooperative", "private")
HOUSEHOLD_SECTOR_IDS: tuple[str, ...] = ("industry", "agriculture", "services", "administration")

#: Occupation ordinal -> household sector ordinal (industry/agriculture/services/administration).
OCCUPATION_SECTOR: tuple[int, ...] = (0, 1, 2, 3)

#: Schooling pay multiplier by education ordinal (primary/secondary/tertiary).
EDUCATION_PAY_MULTIPLIER: tuple[float, ...] = (1.0, 1.15, 1.30)

#: Default per-channel parent commodity and parent-equivalent conversion (A2).
DEFAULT_PARENT_COMMODITY_IDS: tuple[str, ...] = (
    "energy",
    "food",
    "food",
    "consumer_goods",
    "durable_goods",
    "durable_goods",
    "durable_goods",
    "durable_goods",
    "services_transport",
    "services_transport",
    "construction",
)
DEFAULT_MATERIAL_EQUIVALENT: tuple[float, ...] = (
    1.0,
    1.0,
    2.0,
    1.0,
    1.0,
    1.0,
    1.0,
    4.0,
    1.0,
    1.0,
    1.0,
)

#: Default retail quota share of the parent-equivalent availability per channel (A3).
DEFAULT_QUOTA_SHARE: tuple[float, ...] = (
    1.0,
    0.75,
    0.25,
    1.0,
    0.30,
    0.30,
    0.30,
    0.10,
    0.80,
    0.20,
    1.0,
)

#: ``construction_services`` never enters formal retail (G installs it privately).
FORMAL_RETAIL_EXCLUDED: frozenset[str] = frozenset({"construction_services"})

#: The four durable ``H`` channels are exactly ``DURABLE_IDS`` in order.
DURABLE_GOOD_ORDER: tuple[int, ...] = tuple(H_INDEX[durable] for durable in DURABLE_IDS)

NonNegativeFloat = Annotated[FiniteFloat, Field(ge=0.0)]
FiniteFraction = Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]
PositiveFloat = Annotated[FiniteFloat, Field(gt=0.0)]


# ----------------------------------------------------------------------
# Parameter groups (S defaults; fixtures may override explicitly)
# ----------------------------------------------------------------------


class DemandParameters(StrictModel):
    """Quarterly household demand coefficients (C3). All grade-S fixtures."""

    base_per_equivalent_person: list[FiniteFloat] = Field(
        default=[0.4, 1.5, 0.25, 1.0, 0.0, 0.0, 0.0, 0.0, 0.2, 0.0, 0.0],
        min_length=11,
        max_length=11,
    )
    minimum_per_equivalent_person: list[FiniteFloat] = Field(
        default=[0.2, 1.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        min_length=11,
        max_length=11,
    )
    children_equivalence: NonNegativeFloat = 0.7
    elderly_equivalence: NonNegativeFloat = 0.9
    higher_income_elasticity: FiniteFraction = 0.5
    higher_expectation_weight: FiniteFraction = 0.25
    light_income_elasticity: FiniteFraction = 0.25
    light_peer_weight: FiniteFraction = 0.10
    light_western_weight: FiniteFraction = 0.05
    personal_income_elasticity: FiniteFraction = 0.25
    urban_energy_multiplier: NonNegativeFloat = 0.9
    rural_energy_multiplier: NonNegativeFloat = 1.1
    occupation_multipliers: list[FiniteFloat] = Field(
        default=[1.0, 1.0, 1.0, 1.0], min_length=4, max_length=4
    )
    education_multipliers: list[FiniteFloat] = Field(
        default=[1.0, 1.0, 1.0], min_length=3, max_length=3
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        for name in ("base_per_equivalent_person", "minimum_per_equivalent_person"):
            if any(not math.isfinite(v) or v < 0.0 for v in getattr(self, name)):
                raise ConfigError(f"demand.{name} must be finite and non-negative")
        if any(v <= 0.0 for v in self.occupation_multipliers):
            raise ConfigError("demand.occupation_multipliers must be strictly positive")
        if any(v <= 0.0 for v in self.education_multipliers):
            raise ConfigError("demand.education_multipliers must be strictly positive")
        return self


class AllocationParameters(StrictModel):
    """Channel conversion, quota and substitution constants (A2/A3/D)."""

    parent_commodity_ids: list[str] = Field(
        default=list(DEFAULT_PARENT_COMMODITY_IDS), min_length=11, max_length=11
    )
    material_equivalent_per_unit: list[PositiveFloat] = Field(
        default=list(DEFAULT_MATERIAL_EQUIVALENT), min_length=11, max_length=11
    )
    quota_share: list[FiniteFraction] = Field(
        default=list(DEFAULT_QUOTA_SHARE), min_length=11, max_length=11
    )
    formal_food_shares: list[FiniteFraction] = Field(
        default=[0.75, 0.25], min_length=2, max_length=2
    )
    formal_durable_shares: list[FiniteFraction] = Field(
        default=[0.30, 0.30, 0.30, 0.10], min_length=4, max_length=4
    )
    formal_service_shares: list[FiniteFraction] = Field(
        default=[0.80, 0.20], min_length=2, max_length=2
    )
    plot_food_shares: list[FiniteFraction] = Field(default=[1.0, 0.0], min_length=2, max_length=2)
    substitution_ratios: list[PositiveFloat] = Field(
        default=[2.0, 1.0, 1.0, 1.0, 1.0], min_length=5, max_length=5
    )
    substitution_credits: list[FiniteFraction] = Field(
        default=[0.6, 0.25, 0.25, 0.25, 0.25], min_length=5, max_length=5
    )
    queue_hours_per_equivalent_unmet: NonNegativeFloat = 0.5
    search_hours_per_channel_shortage: NonNegativeFloat = 2.0
    access_learning_rate: FiniteFraction = 0.05
    access_learning_hours: PositiveFloat = 10.0
    savings_draw_fraction: FiniteFraction = 0.25

    @model_validator(mode="after")
    def _check(self) -> Self:
        if len(self.parent_commodity_ids) != len(HOUSEHOLD_GOOD_IDS):
            raise ConfigError("allocation.parent_commodity_ids must follow the H axis")
        for index, commodity_id in enumerate(self.parent_commodity_ids):
            if commodity_id not in COMMODITY_INDEX:
                raise ConfigError(
                    f"allocation.parent_commodity_ids[{index}]={commodity_id!r} is not a "
                    "declared P02 commodity"
                )
        if not math.isclose(sum(self.formal_food_shares), 1.0, abs_tol=1e-9):
            raise ConfigError("allocation.formal_food_shares must sum to one")
        if not math.isclose(sum(self.formal_durable_shares), 1.0, abs_tol=1e-9):
            raise ConfigError("allocation.formal_durable_shares must sum to one")
        if not math.isclose(sum(self.formal_service_shares), 1.0, abs_tol=1e-9):
            raise ConfigError("allocation.formal_service_shares must sum to one")
        if not math.isclose(sum(self.plot_food_shares), 1.0, abs_tol=1e-9):
            raise ConfigError("allocation.plot_food_shares must sum to one")
        if len(self.substitution_ratios) != len(SUBSTITUTION_IDS):
            raise ConfigError("allocation.substitution_ratios must follow the Q axis")
        if len(self.substitution_credits) != len(SUBSTITUTION_IDS):
            raise ConfigError("allocation.substitution_credits must follow the Q axis")
        return self


class DurablesParameters(StrictModel):
    """Durable diffusion / retirement / maintenance constants (E)."""

    retirement_hazard: list[NonNegativeFloat] = Field(
        default=[0.005, 0.005, 0.004, 0.003], min_length=4, max_length=4
    )
    aspiration_base: list[NonNegativeFloat] = Field(
        default=[0.25, 0.20, 0.50, 0.10], min_length=4, max_length=4
    )
    aspiration_income_weight: NonNegativeFloat = 0.10
    aspiration_peer_weight: NonNegativeFloat = 0.20
    aspiration_expectation_weight: NonNegativeFloat = 0.10
    new_intention_per_quarter: FiniteFraction = 0.02
    repair_effectiveness: FiniteFraction = 0.5
    waiting_priority_weight: NonNegativeFloat = 0.1

    @model_validator(mode="after")
    def _check(self) -> Self:
        if any(v > 1.0 for v in self.aspiration_base):
            raise ConfigError("durables.aspiration_base entries must lie in [0, 1]")
        return self


class HousingParameters(StrictModel):
    """Housing stock/occupancy/waiting constants (F)."""

    persons_per_dwelling: PositiveFloat = 3.0
    housing_construction_cap_per_person: NonNegativeFloat = 0.002
    private_construction_intention_per_quarter: FiniteFraction = 0.02
    severe_overcrowding_threshold: NonNegativeFloat = 1.0
    waiting_priority_weight: NonNegativeFloat = 0.1

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.persons_per_dwelling <= 0.0:
            raise ConfigError("housing.persons_per_dwelling must be strictly positive")
        return self


class TimeParameters(StrictModel):
    """Time endowment and work-effort feedback constants (G)."""

    time_endowment_hours: PositiveFloat = 1040.0
    formal_hours_per_worker: PositiveFloat = 520.0
    plot_hours_cap_per_worker: PositiveFloat = 52.0
    second_hours_cap_per_worker: PositiveFloat = 130.0
    plot_hours_per_activity: PositiveFloat = 4.0
    second_hours_base: FiniteFraction = 0.25
    second_shortage_weight: FiniteFraction = 0.5
    second_grievance_weight: FiniteFraction = 0.25
    effort_grievance_weight: FiniteFraction = 0.4
    effort_informal_hours_weight: FiniteFraction = 0.3
    effort_queue_search_weight: FiniteFraction = 0.2
    effort_floor: FiniteFraction = 0.25

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not 0.0 <= self.effort_floor <= 1.0:
            raise ConfigError("time.effort_floor must lie in [0, 1]")
        return self


class WelfareParameters(StrictModel):
    """Welfare accounting, entitlement and political-reaction constants (H)."""

    component_weights: list[NonNegativeFloat] = Field(
        default=[0.10, 0.30, 0.15, 0.15, 0.05, 0.04, 0.04, 0.05, 0.05, 0.04, 0.03],
        min_length=11,
        max_length=11,
    )
    component_cap: PositiveFloat = 2.0
    queue_cost_per_hour: NonNegativeFloat = 0.002
    search_cost_per_hour: NonNegativeFloat = 0.002
    durable_postponement_cost: NonNegativeFloat = 0.02
    housing_postponement_cost: NonNegativeFloat = 0.02
    basic_deficit_weight: NonNegativeFloat = 0.5
    satisfaction_slope: NonNegativeFloat = 4.0
    satisfaction_midpoint: FiniteFraction = 0.5
    welfare_provision: FiniteFraction = 0.5
    private_autonomy: FiniteFraction = 0.5
    cultural_openness: FiniteFraction = 0.5
    grievance_alpha: FiniteFraction = 0.2
    grievance_gap_weight: FiniteFraction = 0.7
    grievance_unfairness_weight: FiniteFraction = 0.3
    compliance_baseline: FiniteFraction = 0.7
    compliance_gap_weight: FiniteFraction = 0.3
    compliance_autonomy_weight: FiniteFraction = 0.1
    compliance_alpha: FiniteFraction = 0.1

    @model_validator(mode="after")
    def _check(self) -> Self:
        if abs(sum(self.component_weights)) <= 1e-12:
            raise ConfigError("welfare.component_weights must not be all zero")
        return self

    def durable_service_value(self, parent_admin_price: float, hazard: float) -> float:
        """Derived synthetic depreciation-service proxy (H4)."""
        return float(parent_admin_price) * float(hazard)


class ExpectationsParameters(StrictModel):
    """Adaptive expectation and ratchet constants (I)."""

    alpha_up: FiniteFraction = 0.25
    alpha_down: FiniteFraction = 0.02
    ratchet_strength: FiniteFraction = 0.10
    ratchet_quarters: Annotated[int, Field(strict=True, ge=1)] = 4
    consumption_reference_alpha: FiniteFraction = 0.25
    initial_entitlement: list[FiniteFraction] = Field(
        default=[1.0, 0.5, 1.0, 0.5, 0.5, 0.5, 0.5], min_length=7, max_length=7
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.ratchet_strength > 0.3:
            raise ConfigError("expectations.ratchet_strength exceeds the screening range [0, 0.3]")
        if not 0.05 <= self.alpha_up <= 0.5:
            raise ConfigError("expectations.alpha_up must lie in the screening range [0.05, 0.5]")
        if not 0.0 <= self.alpha_down <= 0.1:
            raise ConfigError("expectations.alpha_down must lie in the screening range [0, 0.1]")
        return self


class SecondEconomyRecipe(StrictModel):
    """Declared aggregate per-county second-economy activity (G; grade S)."""

    role: Literal["latent_parameter"] = "latent_parameter"
    evidence_status: Literal["structural_assumption"] = "structural_assumption"
    calibration_status: Literal["not_calibrated"] = "not_calibrated"
    sensitivity_status: Literal["not_assessed"] = "not_assessed"
    #: Positive input coefficient per P02 commodity (zero cells omitted by the compiler).
    input_coefficients: list[NonNegativeFloat] = Field(
        default=[0.02, 0.0, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0], min_length=8, max_length=8
    )
    output_coefficients: list[NonNegativeFloat] = Field(
        default=[0.0, 0.0, 0.0, 0.10, 0.0, 0.05, 0.0, 0.25], min_length=8, max_length=8
    )
    hours_per_activity: PositiveFloat = 4.0
    capacity_per_participating_worker: NonNegativeFloat = 10.0
    service_shares: list[FiniteFraction] = Field(default=[0.60, 0.40], min_length=2, max_length=2)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if len(self.input_coefficients) != len(P02_COMMODITY_IDS):
            raise ConfigError("second_economy.input_coefficients must follow the P02 axis")
        if len(self.output_coefficients) != len(P02_COMMODITY_IDS):
            raise ConfigError("second_economy.output_coefficients must follow the P02 axis")
        if not math.isclose(sum(self.service_shares), 1.0, abs_tol=1e-9):
            raise ConfigError("second_economy.service_shares must sum to one")
        if self.capacity_per_participating_worker > 20.0:
            raise ConfigError(
                "second_economy.capacity_per_participating_worker exceeds the "
                "screening range [0, 20]"
            )
        return self


class HouseholdParameters(StrictModel):
    """The complete P03 household parameter block (nested, hash-bound)."""

    role: Literal["latent_parameter"] = "latent_parameter"
    evidence_status: Literal["structural_assumption"] = "structural_assumption"
    calibration_status: Literal["not_calibrated"] = "not_calibrated"
    sensitivity_status: Literal["not_assessed"] = "not_assessed"
    eps: PositiveFloat = 1e-12
    demand: DemandParameters = Field(default_factory=DemandParameters)
    allocation: AllocationParameters = Field(default_factory=AllocationParameters)
    durables: DurablesParameters = Field(default_factory=DurablesParameters)
    housing: HousingParameters = Field(default_factory=HousingParameters)
    time: TimeParameters = Field(default_factory=TimeParameters)
    welfare: WelfareParameters = Field(default_factory=WelfareParameters)
    expectations: ExpectationsParameters = Field(default_factory=ExpectationsParameters)
    second_economy: SecondEconomyRecipe = Field(default_factory=SecondEconomyRecipe)

    def flatten(self) -> dict[str, float]:
        """Field/index-path flattening for the run's household-parameter hash."""
        vector: dict[str, float] = {"eps": self.eps}
        for group_name in (
            "demand",
            "allocation",
            "durables",
            "housing",
            "time",
            "welfare",
            "expectations",
            "second_economy",
        ):
            group = getattr(self, group_name)
            for name, value in group.model_dump().items():
                if isinstance(value, list):
                    for index, item in enumerate(value):
                        if isinstance(item, (int, float)) and not isinstance(item, bool):
                            vector[f"{group_name}.{name}.{index}"] = float(item)
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    vector[f"{group_name}.{name}"] = float(value)
        return vector


# ----------------------------------------------------------------------
# Synthetic county population recipe (B; grade S)
# ----------------------------------------------------------------------


class CountyHouseholdSpec(StrictModel):
    """One declared county's synthetic household composition (B2/B3)."""

    county_id: str = Field(min_length=1)
    household_total: PositiveFloat
    persons_total: PositiveFloat
    urban_share: FiniteFraction
    size_probabilities: list[NonNegativeFloat] = Field(min_length=6, max_length=6)
    occupation_shares: list[FiniteFraction] = Field(min_length=4, max_length=4)
    education_shares: list[FiniteFraction] = Field(min_length=3, max_length=3)
    child_share: FiniteFraction
    elderly_share: FiniteFraction
    plot_share: FiniteFraction
    second_share: FiniteFraction
    informal_access: FiniteFraction
    western_exposure: FiniteFraction
    tenure_shares: list[FiniteFraction] = Field(min_length=3, max_length=3)
    durable_ownership: list[FiniteFraction] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.persons_total < self.household_total:
            raise ConfigError(f"county {self.county_id} persons_total < household_total (mean<1)")
        if not math.isclose(sum(self.size_probabilities), 1.0, abs_tol=1e-9):
            raise ConfigError(f"county {self.county_id} size_probabilities must sum to one")
        for name in ("occupation_shares", "education_shares", "tenure_shares"):
            if not math.isclose(sum(getattr(self, name)), 1.0, abs_tol=1e-9):
                raise ConfigError(f"county {self.county_id} {name} must sum to one")
        # durable_ownership holds per-durable ownership *rates* in [0, 1]; it is
        # not a probability distribution and does not sum to one.
        if self.child_share + self.elderly_share > 1.0:
            raise ConfigError(f"county {self.county_id} child_share + elderly_share exceeds 1")
        return self


class HouseholdInitialRecipe(StrictModel):
    """Declared synthetic initial household population (grade S structural assumption)."""

    role: Literal["initial_state"] = "initial_state"
    grade: Literal["S"] = "S"
    evidence_status: Literal["structural_assumption"] = "structural_assumption"
    observation_at: None = None
    population_kind: Literal["synthetic"] = "synthetic"
    counties: list[CountyHouseholdSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        ids = [county.county_id for county in self.counties]
        if len(set(ids)) != len(ids):
            raise ConfigError("household_initial.counties repeat a county id")
        return self


def default_household_recipe(region_ids: Sequence[str]) -> HouseholdInitialRecipe:
    """The declared pure-engineering 20-county recipe (B3).

    ``r`` is the county ordinal; ``urban_share`` and the county scale are a
    deliberate synthetic gradient, *not* Hungarian urban/rural facts.
    """
    region_list = list(region_ids)
    count = len(region_list)
    if count == 0:
        raise ConfigError("default_household_recipe needs at least one region")
    scales = np.array([1.0 + r / 40.0 for r in range(count)], dtype=np.float64)
    household_totals = 5000.0 * scales / float(scales.sum())
    counties: list[CountyHouseholdSpec] = []
    for r, region_id in enumerate(region_list):
        urban_share = 0.35 + 0.30 * (r / max(count - 1, 1))
        household_total = float(household_totals[r])
        counties.append(
            CountyHouseholdSpec(
                county_id=str(region_id),
                household_total=household_total,
                persons_total=3.4 * household_total,
                urban_share=urban_share,
                size_probabilities=[0.10, 0.20, 0.25, 0.20, 0.15, 0.10],
                occupation_shares=[0.35, 0.25, 0.25, 0.15],
                education_shares=[0.60, 0.30, 0.10],
                child_share=0.20,
                elderly_share=0.15,
                plot_share=0.30 * (1.0 - urban_share),
                second_share=0.20,
                informal_access=0.5,
                western_exposure=0.0,
                tenure_shares=[0.4, 0.2, 0.4],
                durable_ownership=[0.05, 0.03, 0.10, 0.005],
            )
        )
    return HouseholdInitialRecipe(counties=counties)


# ----------------------------------------------------------------------
# Compiled read-only catalog
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class HouseholdCatalog:
    """Compiled read-only household channel mapping (A/J).

    Every array is a pure function of ``(HouseholdParameters,
    MaterialParameters, commodity_ids)``; nothing here is re-drawn per tick.
    """

    commodity_ids: tuple[str, ...]
    household_good_ids: tuple[str, ...]
    durable_ids: tuple[str, ...]
    entitlement_ids: tuple[str, ...]
    substitution_ids: tuple[str, ...]
    to_material: np.ndarray  # float64 (H, G) equivalent units of parent per H unit
    parent_material_index: np.ndarray  # int32 (H,) parent commodity axis index or -1
    material_equivalent: np.ndarray  # float64 (H,) parent units per H unit
    quota_share: np.ndarray  # float64 (H,) share of parent availability per channel
    quota_group: np.ndarray  # int32 (H,) group id (channels sharing a parent)
    price_h: np.ndarray  # float64 (H,) admin price per H unit
    formal_retail_mask: np.ndarray  # bool (H,) channel participates in formal retail
    durable_h_index: np.ndarray  # int32 (J,) H index of each durable
    substitute_source_h: np.ndarray  # int32 (Q,) source channel H index
    substitute_target_h: np.ndarray  # int32 (Q,) target channel H index
    substitute_ratio: np.ndarray  # float64 (Q,) target units per source unit
    substitute_credit: np.ndarray  # float64 (Q,) goal-credit per substituted source unit


def compile_household_catalog(
    parameters: HouseholdParameters,
    material_parameters: MaterialParameters,
    commodity_ids: tuple[str, ...],
) -> HouseholdCatalog:
    """Compile the read-only household catalog (A2/A3).

    ``to_material[h, g]`` is positive only on the declared parent commodity;
    ``price_h = to_material @ material_prices`` prices one H unit in admin
    prices.  Quota shares partition each parent commodity's retail availability
    across its channels (the channels of one parent sum to one).
    """
    ids = tuple(commodity_ids)
    g_count = len(ids)
    axis_index = {commodity_id: g for g, commodity_id in enumerate(ids)}
    h_count = len(HOUSEHOLD_GOOD_IDS)

    parent_ids = list(parameters.allocation.parent_commodity_ids)
    equivalent = np.asarray(parameters.allocation.material_equivalent_per_unit, dtype=np.float64)
    quota = np.asarray(parameters.allocation.quota_share, dtype=np.float64)

    to_material = np.zeros((h_count, g_count), dtype=np.float64)
    parent_index = np.full(h_count, -1, dtype=np.int32)
    for h, commodity_id in enumerate(parent_ids):
        if commodity_id not in axis_index:
            # A reduced tiny test axis may omit a parent commodity; the channel
            # then has no availability, no price and no material counterpart.
            continue
        g = axis_index[commodity_id]
        parent_index[h] = g
        to_material[h, g] = equivalent[h]

    declared_parent = tuple(DEFAULT_PARENT_COMMODITY_IDS)
    if tuple(parent_ids) != declared_parent:
        raise ConfigError("allocation.parent_commodity_ids must equal the declared A2 mapping")

    group_of: dict[str, int] = {}
    quota_group = np.zeros(h_count, dtype=np.int32)
    for h, commodity_id in enumerate(parent_ids):
        if commodity_id not in group_of:
            group_of[commodity_id] = len(group_of)
        quota_group[h] = group_of[commodity_id]
    for parent in group_of:
        members = [h for h in range(h_count) if parent_ids[h] == parent]
        if abs(float(quota[members].sum()) - 1.0) > 1e-9:
            raise ConfigError(
                f"allocation.quota_share for parent {parent!r} must sum to one, "
                f"got {float(quota[members].sum())!r}"
            )

    price_axis = np.asarray(material_parameters.prices, dtype=np.float64)
    # material_parameters.prices is indexed by the declared P02 commodity axis.
    price_by_commodity = {
        commodity_id: float(price_axis[COMMODITY_INDEX[commodity_id]])
        for commodity_id in ids
        if commodity_id in COMMODITY_INDEX
    }
    price_h = np.zeros(h_count, dtype=np.float64)
    for h, commodity_id in enumerate(parent_ids):
        if parent_index[h] < 0:
            continue  # reduced axis: channel inactive
        if commodity_id not in price_by_commodity:
            raise ConfigError(f"no admin price for household parent commodity {commodity_id!r}")
        price_h[h] = equivalent[h] * price_by_commodity[commodity_id]

    formal_retail = np.array(
        [good not in FORMAL_RETAIL_EXCLUDED for good in HOUSEHOLD_GOOD_IDS], dtype=bool
    )

    durable_h_index = np.asarray(DURABLE_GOOD_ORDER, dtype=np.int32)
    substitute_source_h = np.asarray(
        [H_INDEX[name.split("->")[0]] for name in SUBSTITUTION_IDS], dtype=np.int32
    )
    substitute_target_h = np.asarray(
        [H_INDEX[name.split("->")[1]] for name in SUBSTITUTION_IDS], dtype=np.int32
    )
    substitute_ratio = np.asarray(parameters.allocation.substitution_ratios, dtype=np.float64)
    substitute_credit = np.asarray(parameters.allocation.substitution_credits, dtype=np.float64)

    return HouseholdCatalog(
        commodity_ids=ids,
        household_good_ids=HOUSEHOLD_GOOD_IDS,
        durable_ids=DURABLE_IDS,
        entitlement_ids=ENTITLEMENT_IDS,
        substitution_ids=SUBSTITUTION_IDS,
        to_material=to_material,
        parent_material_index=parent_index,
        material_equivalent=equivalent,
        quota_share=quota,
        quota_group=quota_group,
        price_h=price_h,
        formal_retail_mask=formal_retail,
        durable_h_index=durable_h_index,
        substitute_source_h=substitute_source_h,
        substitute_target_h=substitute_target_h,
        substitute_ratio=substitute_ratio,
        substitute_credit=substitute_credit,
    )


__all__ = [
    "AllocationParameters",
    "CountyHouseholdSpec",
    "DURABLE_IDS",
    "D_INDEX",
    "DemandParameters",
    "DurablesParameters",
    "EDUCATION_PAY_MULTIPLIER",
    "ENTITLEMENT_IDS",
    "E_INDEX",
    "ExpectationsParameters",
    "H_INDEX",
    "HOUSEHOLD_EDUCATION_IDS",
    "HOUSEHOLD_GOOD_IDS",
    "HOUSEHOLD_OCCUPATION_IDS",
    "HOUSEHOLD_SECTOR_IDS",
    "HOUSEHOLD_TENURE_IDS",
    "HouseholdCatalog",
    "HouseholdInitialRecipe",
    "HouseholdParameters",
    "HousingParameters",
    "OCCUPATION_SECTOR",
    "Q_INDEX",
    "SUBSTITUTION_IDS",
    "SecondEconomyRecipe",
    "TimeParameters",
    "WelfareParameters",
    "compile_household_catalog",
    "default_household_recipe",
]
