"""Research contract schemas: quarters, roles, run config and material profiles.

All models are strict (``extra='forbid'``, frozen). P02 material schemas
describe simulation configuration and synthetic mechanisms; historical data
roles remain gated and are never promoted into state by these models.

Error semantics (used by the CLI for exit codes):
- ``ConfigError``: input/configuration validation failure -> exit 2.
- ``ResearchGateError``: environment / I/O / research-gate failure -> exit 1.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    model_validator,
)

from hsm_lab.contract.base import (
    ConfigError,
    FiniteFloat,
    ResearchGateError,
    Sha256Hex,
    StrictInt,
    StrictModel,
)
from hsm_lab.contract.households import (
    HouseholdInitialRecipe,
    HouseholdParameters,
)
from hsm_lab.contract.material import (
    MATERIAL_FORCING_VARIABLE_IDS,
    ORGANIZATION_PROFILES,
    P02_COMMODITY_IDS,
    ForcingBinding,
    MaterialInitialRecipe,
    MaterialParameters,
    MaterialRouteSpec,
    OrganizationRecipe,
    TechnologySpec,
)

__all__ = [
    "ConfigError",
    "ResearchGateError",
    "StrictModel",
    "StrictInt",
    "FiniteFloat",
    "Sha256Hex",
]


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


FORBIDDEN_COMMODITY_IDS = {"goods"}


class ScenarioSpec(StrictModel):
    """P00 smoke or P02 Intermediate-8 material scenario."""

    schema_version: Literal["1"] = "1"
    scenario_id: str = Field(min_length=1)
    kind: Literal["smoke", "material"]
    start: QuarterLike
    ticks: StrictInt = Field(ge=1)
    households: StrictInt = Field(ge=1)
    enterprises: StrictInt | None = Field(default=None, ge=1)
    organizations: StrictInt | None = Field(default=None, ge=0)
    region_ids: list[str] = Field(min_length=1)
    commodities: list[str] = Field(min_length=2)
    seed: StrictInt = Field(ge=0)
    stochastic: bool
    output_policy: OutputPolicy
    forcing_ids: list[str]
    initial_ids: list[str]
    parameter_ids: list[str]
    material_parameters: MaterialParameters | None = None
    material_initial: MaterialInitialRecipe | None = None
    household_parameters: HouseholdParameters | None = None
    household_initial: HouseholdInitialRecipe | None = None
    organization_recipe: OrganizationRecipe | None = None
    technologies: list[TechnologySpec] | None = None
    routes: list[MaterialRouteSpec] | None = None
    forcing_pack: str | None = None
    forcing_bindings: list[ForcingBinding] = []
    #: P04 political/external layer.  ``None`` explicitly means the material-only
    #: P02/P03 scenario with no political engine (never a silent fallback).
    #: Typed as ``Any`` and coerced to ``PoliticalRunSpec`` in ``_check_lists`` so
    #: this module never imports ``contract.politics`` at module scope (the two
    #: modules would otherwise form an import cycle).
    politics: Any = None

    @model_validator(mode="after")
    def _check_lists(self) -> Self:
        if self.politics is not None:
            from hsm_lab.contract.politics import PoliticalRunSpec

            if not isinstance(self.politics, PoliticalRunSpec):
                coerced = PoliticalRunSpec.model_validate(self.politics)
                object.__setattr__(self, "politics", coerced)
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
            material_fields = (
                "material_parameters",
                "material_initial",
                "household_parameters",
                "household_initial",
                "organization_recipe",
                "technologies",
                "routes",
                "forcing_pack",
            )
            if any(getattr(self, name) is not None for name in material_fields):
                raise ConfigError("smoke scenarios must not carry material fields")
            if self.forcing_bindings or self.organizations is not None:
                raise ConfigError(
                    "smoke scenarios must not carry material bindings or organizations"
                )
            if self.politics is not None:
                raise ConfigError("smoke scenarios must not carry a political run specification")
            if self.enterprises is None:
                raise ConfigError("smoke scenarios must declare enterprises")
        else:
            if self.enterprises is not None:
                raise ConfigError("material scenarios must not declare enterprises")
            self._check_material_fields()
        return self

    def _check_material_fields(self) -> None:
        if self.material_parameters is None or self.material_initial is None:
            raise ConfigError(
                "material scenarios must declare material_parameters and material_initial"
            )
        if self.household_parameters is None or self.household_initial is None:
            raise ConfigError(
                "material scenarios must declare household_parameters and household_initial"
            )
        if self.organization_recipe is None or self.technologies is None:
            raise ConfigError(
                "material scenarios must declare organization_recipe and technologies"
            )
        if self.enterprises is not None:
            raise ConfigError(
                "material scenarios must not declare enterprises; the organization count "
                "comes from organizations/organization_recipe"
            )
        if self.organizations is not None:
            profile_total = sum(ORGANIZATION_PROFILES[self.organization_recipe.profile].values())
            if self.organizations != profile_total:
                raise ConfigError(
                    f"organizations={self.organizations} contradicts organization_recipe "
                    f"profile {self.organization_recipe.profile} (total {profile_total})"
                )
        if any(
            o.organization_id >= self._material_profile_count()
            for o in self.organization_recipe.overrides
        ):
            raise ConfigError("organization override references an id outside the profile")
        if self.forcing_pack is None or not self.forcing_pack:
            raise ConfigError(
                "material scenarios must declare forcing_pack "
                "(synthetic fixture or explicit external pack); runs never download"
            )
        if self.forcing_ids or self.initial_ids or self.parameter_ids:
            raise ConfigError(
                "material scenarios take forcing only via forcing_pack/forcing_bindings: "
                "forcing_ids/initial_ids/parameter_ids must be empty"
            )
        known = set(P02_COMMODITY_IDS)
        for binding in self.forcing_bindings:
            if binding.variable_id not in MATERIAL_FORCING_VARIABLE_IDS:
                raise ConfigError(
                    f"forcing binding variable {binding.variable_id} is not a material "
                    "external variable"
                )
        declared = set(self.commodities)
        if not declared <= known:
            raise ConfigError(
                f"material commodities must be declared CommoditySpec ids; unknown: "
                f"{sorted(declared - known)}"
            )

    def _material_profile_count(self) -> int:
        assert self.organization_recipe is not None
        return sum(ORGANIZATION_PROFILES[self.organization_recipe.profile].values())

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
        self._validate_material_for_run(contract)

    def _validate_material_for_run(self, contract: ResearchContract) -> None:
        """Formal material run gates (P02 plan step 1/7)."""
        declared = P02_COMMODITY_IDS
        unknown = [cid for cid in self.commodities if cid not in declared]
        if unknown:
            raise ConfigError(f"commodity ids are not declared in the registry: {unknown}")
        if len(set(self.commodities)) != len(self.commodities):
            raise ConfigError("commodity ids must be unique")
        missing = [cid for cid in declared if cid not in self.commodities]
        if missing:
            raise ConfigError(
                f"material scenarios must declare every registry commodity; missing {missing}"
            )
        # Commodity-indexed parameter vectors must match the declared axis length.
        if self.material_parameters is None:
            raise ConfigError("material scenarios must declare material_parameters")
        self.material_parameters.check_axis(self.commodities)
        if self.start.to_ordinal() != contract.core_start.to_ordinal():
            raise ConfigError(
                f"material scenarios must start at the core window start {contract.core_start}"
            )
        if not 1 <= self.ticks <= contract.core_ticks:
            raise ConfigError(
                f"material ticks must lie in [1, {contract.core_ticks}] "
                "(116 = full horizon; shorter windows are benchmark/pause-only)"
            )
        if not 1000 <= self.households <= 30000:
            raise ConfigError("material households must lie in [1000, 30000]")
        count = self._material_profile_count()
        if count not in (100, 200, 400):
            raise ConfigError(
                f"material organization profile total must be 100/200/400, got {count}"
            )
        if self.output_policy is OutputPolicy.RESEARCH_FULL:
            raise ConfigError(
                "material runs support ensemble_compact only in P02; research_full is "
                "not silently downgraded (full micro household panel is P03 scope)"
            )
