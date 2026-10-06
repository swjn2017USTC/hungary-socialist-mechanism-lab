"""Research contract schemas: quarters, data roles, contract, scenario spec.

All models are strict (``extra="forbid"``, frozen). Numbers reject NaN/Inf and
bool-as-int. These schemas encode the P00 research contract only; they do not
implement any historical simulation.

Error semantics (used by the CLI for exit codes):
- ``ConfigError``: input/configuration validation failure -> exit 2.
- ``ResearchGateError``: environment / I/O / research-gate failure -> exit 1.
"""

from __future__ import annotations

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


FORBIDDEN_COMMODITY_IDS = {"goods"}


class ScenarioSpec(StrictModel):
    """A synthetic smoke scenario. P00 implements exactly one: ``smoke``."""

    schema_version: Literal["1"] = "1"
    scenario_id: str = Field(min_length=1)
    kind: Literal["smoke"]
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
        for name in ("forcing_ids", "initial_ids", "parameter_ids"):
            if getattr(self, name):
                raise ConfigError(
                    f"{name} must be empty: the P00 smoke workload takes no data inputs"
                )
