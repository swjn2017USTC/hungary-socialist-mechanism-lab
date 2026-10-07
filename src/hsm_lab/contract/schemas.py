"""Research contract schemas: quarters, data roles, contract, scenario spec.

All models are strict (``extra="forbid"``, frozen). Numbers reject NaN/Inf and
bool-as-int. These schemas encode the P00 research contract only; they do not
implement any historical simulation.

Error semantics (used by the CLI for exit codes):
- ``ConfigError``: input/configuration validation failure -> exit 2.
- ``ResearchGateError``: environment / I/O / research-gate failure -> exit 1.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ConfigError(ValueError):
    """Input/configuration validation failure (CLI exit code 2)."""


class ResearchGateError(RuntimeError):
    """Environment, I/O or research-gate failure (CLI exit code 1)."""


class StrictModel(BaseModel):
    """Shared strict base: unknown fields are errors, instances are frozen."""

    model_config = ConfigDict(extra="forbid", frozen=True)


StrictInt = Annotated[int, Field(strict=True)]
FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_require_utc)]

_QUARTER_RE = re.compile(r"^(\d{4})Q([1-4])$")


class Quarter(StrictModel):
    """A ``YYYYQ[1-4]`` calendar quarter with integer ordinal arithmetic."""

    year: StrictInt = Field(ge=1, le=9999)
    quarter: StrictInt = Field(ge=1, le=4)

    @classmethod
    def parse(cls, text: str) -> Quarter:
        match = _QUARTER_RE.match(text) if isinstance(text, str) else None
        if match is None:
            raise ConfigError(f"invalid quarter {text!r}: expected YYYYQ[1-4] (Q0/Q5 rejected)")
        return cls(year=int(match.group(1)), quarter=int(match.group(2)))

    def to_ordinal(self) -> int:
        return self.year * 4 + (self.quarter - 1)

    @classmethod
    def from_ordinal(cls, ordinal: int) -> Quarter:
        year, q0 = divmod(ordinal, 4)
        return cls(year=year, quarter=q0 + 1)

    def advance(self, ticks: int) -> Quarter:
        if ticks < 0:
            raise ConfigError(f"cannot advance quarter backwards by {ticks}")
        return Quarter.from_ordinal(self.to_ordinal() + ticks)

    def __str__(self) -> str:  # noqa: D105 - str() contract used everywhere
        return f"{self.year}Q{self.quarter}"


def _coerce_quarter(value: object) -> object:
    if isinstance(value, str):
        return Quarter.parse(value)
    return value


QuarterLike = Annotated[Quarter, BeforeValidator(_coerce_quarter)]


class DataRole(StrEnum):
    """The four research data roles (BASELINE §20). Input != Target != Parameter."""

    EXOGENOUS_FORCING = "exogenous_forcing"
    INITIAL_STATE = "initial_state"
    TARGET = "target"
    LATENT_PARAMETER = "latent_parameter"


class TargetUse(StrEnum):
    """How a TARGET artifact may be used; targets are never inputs."""

    CALIBRATION = "calibration"
    VALIDATION = "validation"
    HOLDOUT = "holdout"
    RESERVED = "reserved"


class PoliticalMode(StrEnum):
    """Declared vocabulary only; P00 executes none of these models."""

    HISTORICAL_REPLAY = "historical_replay"
    ENDOGENOUS_POLITICS = "endogenous_politics"
    COUNTERFACTUAL = "counterfactual"


class EvidenceStatus(StrEnum):
    OBSERVED = "observed"
    RECONSTRUCTED = "reconstructed"
    LITERATURE_PROXY = "literature_proxy"
    STRUCTURAL_ASSUMPTION = "structural_assumption"
    SYNTHETIC_FIXTURE = "synthetic_fixture"


class InitialGrade(StrEnum):
    """Initial-condition evidence grades (BASELINE §5.3)."""

    A = "A"
    B = "B"
    C = "C"
    S = "S"


class Frequency(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    DATED = "dated"
    STATIC = "static"


class OutputPolicy(StrEnum):
    RESEARCH_FULL = "research_full"
    ENSEMBLE_COMPACT = "ensemble_compact"


class MechanismVerdict(StrEnum):
    """Saved vocabulary only; P00 produces no M1-M11 verdicts."""

    SUPPORTED = "supported"
    CONDITIONAL = "conditional"
    WEAK = "weak"
    REJECTED = "rejected"
    UNIDENTIFIED = "unidentified"


class RegionSpec(StrictModel):
    region_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)


class MacroregionSpec(StrictModel):
    macroregion_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    member_region_ids: list[str] = Field(min_length=1)


class ResearchContract(StrictModel):
    """Frozen research contract pinned to the immutable BASELINE.md bytes."""

    schema_version: Literal["1"] = "1"
    baseline_version: str = Field(min_length=1)
    expected_baseline_sha256: Sha256Hex
    core_start: QuarterLike
    core_end: QuarterLike
    reserved_start: QuarterLike
    reserved_end: QuarterLike
    regions: list[RegionSpec] = Field(min_length=20, max_length=20)
    macroregions: list[MacroregionSpec] = Field(min_length=1)
    political_modes: list[PoliticalMode] = Field(min_length=1)
    output_policies: list[OutputPolicy] = Field(min_length=1)
    research_warnings: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        ids = [r.region_id for r in self.regions]
        if len(set(ids)) != len(ids):
            raise ConfigError("region ids must be unique")
        seen: set[str] = set()
        for macro in self.macroregions:
            members = macro.member_region_ids
            if len(set(members)) != len(members):
                raise ConfigError(f"macroregion {macro.macroregion_id} repeats a region")
            for rid in members:
                if rid not in ids:
                    raise ConfigError(
                        f"macroregion {macro.macroregion_id} references unknown region {rid}"
                    )
                if rid in seen:
                    raise ConfigError(f"region {rid} appears in more than one macroregion")
                seen.add(rid)
        if seen != set(ids):
            missing = sorted(set(ids) - seen)
            raise ConfigError(f"macroregions do not cover every region exactly once: {missing}")
        if self.core_start.to_ordinal() >= self.core_end.to_ordinal():
            raise ConfigError("core window is inverted or empty")
        if self.reserved_start.to_ordinal() != self.core_end.to_ordinal() + 1:
            raise ConfigError("reserved window must start immediately after the core window")
        if self.reserved_start.to_ordinal() >= self.reserved_end.to_ordinal():
            raise ConfigError("reserved window is inverted or empty")
        for field, values in (
            ("political_modes", self.political_modes),
            ("output_policies", self.output_policies),
        ):
            if len(set(values)) != len(values):
                raise ConfigError(f"{field} contains duplicates")
        return self

    @property
    def region_ids(self) -> list[str]:
        return [r.region_id for r in self.regions]

    @property
    def core_ticks(self) -> int:
        """Number of quarters in the inclusive core window."""
        return self.core_end.to_ordinal() - self.core_start.to_ordinal() + 1

    def in_core(self, quarter: Quarter) -> bool:
        return self.core_start.to_ordinal() <= quarter.to_ordinal() <= self.core_end.to_ordinal()

    def in_reserved(self, quarter: Quarter) -> bool:
        return (
            self.reserved_start.to_ordinal()
            <= quarter.to_ordinal()
            <= self.reserved_end.to_ordinal()
        )



TOY4_COMMODITY_IDS = ("energy", "capital_goods", "food", "consumer_goods")
# The research contract fixes exactly 20 region nodes; the Toy-4 access
# multiplier vector carries one entry per contract region, in that order.
TOY4_REGION_COUNT = 20

TOY4_FORCING_ARTIFACT_IDS = (
    "p01_toy4_import_supply",
    "p01_toy4_export_orders",
)


def _finite_vector(value: list[float], name: str) -> list[float]:
    if not all(math.isfinite(x) for x in value):
        raise ConfigError(f"{name} must contain only finite numbers")
    return value


class Toy4Parameters(StrictModel):
    """Toy-4 model constants. Structural assumptions, never calibrated values.

    Every number is a synthetic engineering fixture: BASELINE §9.3–9.7 supplies
    concepts (vector inputs/outputs, shortage accounting), not coefficients.
    """

    role: Literal["latent_parameter"] = "latent_parameter"
    evidence_status: Literal["structural_assumption"] = "structural_assumption"
    calibration_status: Literal["not_calibrated"] = "not_calibrated"
    sensitivity_status: Literal["not_assessed"] = "not_assessed"
    notes: str = (
        "Synthetic Toy-4 engineering constants; not historical Hungarian "
        "magnitudes and not calibrated against any observed series."
    )
    equivalent_households: FiniteFloat = Field(default=1600.0, gt=0)
    prices: list[FiniteFloat] = Field(
        default=[1.0, 4.0, 2.0, 3.0], min_length=4, max_length=4
    )
    desired_per_person: list[FiniteFloat] = Field(
        default=[0.4, 0.0, 2.0, 1.0], min_length=4, max_length=4
    )
    income_per_person: FiniteFloat = Field(default=6.0, ge=0)
    sector_capacity_totals: list[FiniteFloat] = Field(
        default=[2500.0, 600.0, 3500.0, 2300.0], min_length=4, max_length=4
    )
    target_utilization: FiniteFloat = Field(default=0.9, ge=0, le=1)
    input_coefficients: list[list[FiniteFloat]] = Field(
        default=[
            [0.05, 0.02, 0.0, 0.0],
            [0.4, 0.05, 0.0, 0.0],
            [0.2, 0.04, 0.0, 0.0],
            [0.35, 0.08, 0.1, 0.0],
        ],
        min_length=4,
        max_length=4,
    )
    retail_release_fraction: list[FiniteFloat] = Field(
        default=[0.2, 0.0, 1.0, 1.0], min_length=4, max_length=4
    )
    regional_access_multiplier: list[FiniteFloat] = Field(
        default=[0.5, 1.5] + [1.0] * 18, min_length=20, max_length=20
    )

    @model_validator(mode="after")
    def _check_shapes(self) -> Self:
        g = len(TOY4_COMMODITY_IDS)
        for name in ("prices", "desired_per_person", "sector_capacity_totals",
                     "retail_release_fraction"):
            vector = getattr(self, name)
            _finite_vector(vector, name)
            if len(vector) != g:
                raise ConfigError(
                    f"{name} must have exactly {g} entries (one per Toy-4 commodity)"
                )
        if any(price <= 0 for price in self.prices):
            raise ConfigError("prices must be strictly positive")
        if any(value < 0 for value in self.desired_per_person):
            raise ConfigError("desired_per_person must be non-negative")
        if any(value < 0 for value in self.sector_capacity_totals):
            raise ConfigError("sector_capacity_totals must be non-negative")
        if any(not 0 <= fraction <= 1 for fraction in self.retail_release_fraction):
            raise ConfigError("retail_release_fraction entries must lie in [0, 1]")
        matrix = self.input_coefficients
        if len(matrix) != g or any(len(row) != g for row in matrix):
            raise ConfigError(
                f"input_coefficients must be a {g}x{g} matrix "
                "(output-sector rows x input-commodity columns)"
            )
        _finite_vector([x for row in matrix for x in row], "input_coefficients")
        if any(x < 0 for row in matrix for x in row):
            raise ConfigError("input_coefficients must be non-negative")
        multipliers = _finite_vector(self.regional_access_multiplier,
                                     "regional_access_multiplier")
        if len(multipliers) != TOY4_REGION_COUNT:
            raise ConfigError(
                f"regional_access_multiplier must have exactly {TOY4_REGION_COUNT} "
                "entries (one per contract region, in contract order)"
            )
        if any(m < 0 for m in multipliers) or sum(multipliers) <= 0:
            raise ConfigError(
                "regional_access_multiplier entries must be non-negative with a "
                "positive sum"
            )
        return self

    def flatten(self) -> dict[str, float]:
        """Field/index-path flattening for the run's parameter hash."""
        vector: dict[str, float] = {
            "equivalent_households": self.equivalent_households,
            "income_per_person": self.income_per_person,
            "target_utilization": self.target_utilization,
        }
        for name in ("prices", "desired_per_person", "sector_capacity_totals",
                     "retail_release_fraction", "regional_access_multiplier"):
            for index, value in enumerate(getattr(self, name)):
                vector[f"{name}.{index}"] = value
        for row, sector_row in enumerate(self.input_coefficients):
            for col, value in enumerate(sector_row):
                vector[f"input_coefficients.{row}.{col}"] = value
        return vector


class Toy4InitialRecipe(StrictModel):
    """Declared synthetic initial state (grade S: structural assumption)."""

    role: Literal["initial_state"] = "initial_state"
    grade: Literal["S"] = "S"
    evidence_status: Literal["structural_assumption"] = "structural_assumption"
    observation_at: None = None
    wholesale_inventory: list[FiniteFloat] = Field(
        default=[2000.0, 700.0, 0.0, 0.0], min_length=4, max_length=4
    )
    retail_inventory_totals: list[FiniteFloat] = Field(
        default=[300.0, 0.0, 1000.0, 800.0], min_length=4, max_length=4
    )
    input_stock_target_quarters: FiniteFloat = Field(default=1.0, gt=0)
    household_cash: FiniteFloat = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def _check_shapes(self) -> Self:
        g = len(TOY4_COMMODITY_IDS)
        for name in ("wholesale_inventory", "retail_inventory_totals"):
            vector = getattr(self, name)
            _finite_vector(vector, name)
            if len(vector) != g:
                raise ConfigError(
                    f"{name} must have exactly {g} entries (one per Toy-4 commodity)"
                )
            if any(value < 0 for value in vector):
                raise ConfigError(f"{name} must be non-negative")
        return self

    def flatten(self) -> dict[str, float]:
        """Recipe numeric fields for the run's parameter hash."""
        vector: dict[str, float] = {
            "input_stock_target_quarters": self.input_stock_target_quarters,
            "household_cash": self.household_cash,
        }
        for name in ("wholesale_inventory", "retail_inventory_totals"):
            for index, value in enumerate(getattr(self, name)):
                vector[f"initial.{name}.{index}"] = value
        return vector

FORBIDDEN_COMMODITY_IDS = {"goods"}


class ScenarioSpec(StrictModel):
    """A synthetic scenario. P00 ships ``smoke``; P01 adds the Toy-4 slice."""

    schema_version: Literal["1"] = "1"
    scenario_id: str = Field(min_length=1)
    kind: Literal["smoke", "toy4"]
    start: QuarterLike
    ticks: StrictInt = Field(ge=1)
    households: StrictInt = Field(ge=1)
    enterprises: StrictInt = Field(ge=1)
    region_ids: list[str] = Field(min_length=1)
    commodities: list[str] = Field(min_length=2)
    seed: StrictInt = Field(ge=0)
    stochastic: bool
    output_policy: OutputPolicy
    forcing_ids: list[str]
    initial_ids: list[str]
    parameter_ids: list[str]
    toy4_parameters: Toy4Parameters | None = None
    toy4_initial: Toy4InitialRecipe | None = None

    @model_validator(mode="after")
    def _check_lists(self) -> Self:
        if len(set(self.commodities)) != len(self.commodities):
            raise ConfigError("commodity ids must be unique")
        bad = sorted(set(self.commodities) & FORBIDDEN_COMMODITY_IDS)
        if bad:
            raise ConfigError(
                f"forbidden commodity id(s) {bad}: a single aggregated 'goods' runtime is banned"
            )
        if len(set(self.region_ids)) != len(self.region_ids):
            raise ConfigError("region_ids must be unique")
        if self.kind == "smoke":
            if self.toy4_parameters is not None or self.toy4_initial is not None:
                raise ConfigError(
                    "smoke scenarios must not carry toy4_parameters/toy4_initial"
                )
        else:
            if self.toy4_parameters is None or self.toy4_initial is None:
                raise ConfigError(
                    "toy4 scenarios must declare both toy4_parameters and toy4_initial"
                )
        return self

    def validate_for_run(self, contract: ResearchContract) -> None:
        """Gate a run against the contract (called before any output exists)."""
        if self.region_ids != contract.region_ids:
            raise ConfigError(
                "scenario region_ids must equal the contract's 20 region nodes in order"
            )
        end = self.start.advance(self.ticks - 1)
        if not contract.in_core(end) or not contract.in_core(self.start):
            raise ConfigError(
                f"scenario window {self.start}..{end} leaves the core window "
                f"{contract.core_start}..{contract.core_end}"
            )
        if self.kind == "smoke":
            for name in ("forcing_ids", "initial_ids", "parameter_ids"):
                if getattr(self, name):
                    raise ConfigError(
                        f"{name} must be empty: the smoke workload takes no data inputs"
                    )
            return
        self._validate_toy4_for_run(contract)

    def _validate_toy4_for_run(self, contract: ResearchContract) -> None:
        if self.commodities != list(TOY4_COMMODITY_IDS):
            raise ConfigError(
                "toy4 commodity ids and order must equal "
                f"{list(TOY4_COMMODITY_IDS)}"
            )
        if self.start.to_ordinal() != contract.core_start.to_ordinal():
            raise ConfigError(
                f"toy4 scenarios must start at the core window start {contract.core_start}"
            )
        if not 1 <= self.ticks <= contract.core_ticks:
            raise ConfigError(
                f"toy4 ticks must lie in [1, {contract.core_ticks}] "
                "(116 = full horizon; shorter windows are benchmark-only)"
            )
        if not 1000 <= self.households <= 2000:
            raise ConfigError("toy4 households must lie in [1000, 2000]")
        if not 30 <= self.enterprises <= 50:
            raise ConfigError("toy4 enterprises must lie in [30, 50]")
        if self.output_policy is OutputPolicy.RESEARCH_FULL:
            raise ConfigError(
                "toy4 runs support ensemble_compact only in P01; research_full is "
                "not silently downgraded"
            )
        if self.forcing_ids != list(TOY4_FORCING_ARTIFACT_IDS):
            raise ConfigError(
                "toy4 forcing_ids must be exactly "
                f"{list(TOY4_FORCING_ARTIFACT_IDS)}"
            )
        if self.initial_ids or self.parameter_ids:
            raise ConfigError(
                "toy4 initialization is a declared synthetic recipe: initial_ids "
                "and parameter_ids must be empty"
            )
