"""Data schemas: sources, rights, provenance, variables, role-tagged artifacts.

Every artifact carries a provenance block with role/source/digest evidence.
Admission rules (registry.py) enforce BASELINE §20-24 discipline: paths never
decide roles, targets are never inputs, and a 1960 observation can never be
renamed into a 1957 "observed" initial state.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from hsm_lab.contract.schemas import (
    ConfigError,
    DataRole,
    EvidenceStatus,
    FiniteFloat,
    Frequency,
    InitialGrade,
    StrictModel,
    TargetUse,
    UtcDatetime,
)

Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
_PLACEHOLDER_DIGEST = "0" * 64
_RELATIVE_PATH_RE = re.compile(r"^[A-Za-z0-9._\-]+(?:/[A-Za-z0-9._\-]+)*$")


class AccessStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    CATALOGUE_ONLY = "catalogue_only"
    PUBLIC_METADATA = "public_metadata"
    ACCESS_RESTRICTED = "access_restricted"
    UNAVAILABLE = "unavailable"


class AuditStatus(StrEnum):
    PENDING = "pending"
    METADATA_CHECKED = "metadata_checked"
    BLOCKED = "blocked"


class SemanticKind(StrEnum):
    EXTERNAL = "external"
    INITIAL_ANCHOR = "initial_anchor"
    OUTCOME = "outcome"
    LATENT = "latent"


ROLE_FOR_SEMANTIC_KIND: dict[SemanticKind, DataRole] = {
    SemanticKind.EXTERNAL: DataRole.EXOGENOUS_FORCING,
    SemanticKind.INITIAL_ANCHOR: DataRole.INITIAL_STATE,
    SemanticKind.OUTCOME: DataRole.TARGET,
    SemanticKind.LATENT: DataRole.LATENT_PARAMETER,
}

# Variables that may never enter the runtime as observed data.
RECONSTRUCTED_ONLY_VARIABLES = frozenset({"cmea_energy_price"})

AggregationMethod = Literal["sum", "mean", "end_of_period", "piecewise_constant", "event_date"]
TransformationMethod = Literal[
    "identity",
    "monthly_to_quarterly",
    "quarterly_to_annual",
    "anchor_reconstruction",
    "literature_prior",
    "synthetic_generation",
]


class RightsSpec(StrictModel):
    """License evidence for a source. Unknown never implies True."""

    license_status: Literal["unknown", "verified", "restricted"]
    license_name: str | None = None
    terms_locator: str | None = None
    evidence_quote: str | None = None
    checked_at: UtcDatetime | None = None
    download_allowed: bool | None = None
    redistribution_allowed: bool | None = None
    notes: str = ""

    @model_validator(mode="after")
    def _check_evidence(self) -> Self:
        if self.license_status == "verified":
            missing = [
                name
                for name, value in (
                    ("license_name", self.license_name),
                    ("terms_locator", self.terms_locator),
                    ("evidence_quote", self.evidence_quote),
                    ("checked_at", self.checked_at),
                )
                if not value
            ]
            if missing:
                raise ConfigError(
                    f"verified rights require {missing}; an HTTP 200 or a CC logo is not a licence"
                )
        if self.license_status == "unknown":
            if self.download_allowed or self.redistribution_allowed:
                raise ConfigError("unknown rights cannot grant download or redistribution")
        return self


class SourceSpec(StrictModel):
    """One concrete dataset/table candidate; network success != data obtained."""

    source_id: str = Field(min_length=1)
    institution: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    expected_format: list[str] = Field(min_length=1)
    expected_roles: list[DataRole] = Field(min_length=1)
    retrieval_method: str = Field(min_length=1)
    access_status: AccessStatus
    audit_status: AuditStatus
    rights: RightsSpec
    coverage_notes: str
    notes: str = ""

    @model_validator(mode="after")
    def _check_roles(self) -> Self:
        if len(set(self.expected_roles)) != len(self.expected_roles):
            raise ConfigError(f"source {self.source_id}: duplicate expected_roles")
        return self


class Transformation(StrictModel):
    method: TransformationMethod
    source_frequency: Frequency
    result_frequency: Frequency
    aggregation: AggregationMethod | None = None
    description: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_coherence(self) -> Self:
        flow = {"sum", "mean", "end_of_period"}
        if self.method == "identity":
            if self.source_frequency != self.result_frequency:
                raise ConfigError("identity transformation cannot change frequency")
            if self.aggregation is not None:
                raise ConfigError("identity transformation has no aggregation")
        elif self.method == "monthly_to_quarterly":
            if self.source_frequency is not Frequency.MONTHLY:
                raise ConfigError("monthly_to_quarterly needs a monthly source_frequency")
            if self.result_frequency is not Frequency.QUARTERLY:
                raise ConfigError("monthly_to_quarterly needs a quarterly result_frequency")
            if self.aggregation not in flow:
                raise ConfigError(f"monthly_to_quarterly aggregation must be one of {sorted(flow)}")
        elif self.method == "quarterly_to_annual":
            if self.source_frequency is not Frequency.QUARTERLY:
                raise ConfigError("quarterly_to_annual needs a quarterly source_frequency")
            if self.result_frequency is not Frequency.ANNUAL:
                raise ConfigError("quarterly_to_annual needs an annual result_frequency")
            if self.aggregation not in flow:
                raise ConfigError(f"quarterly_to_annual aggregation must be one of {sorted(flow)}")
        elif self.method in ("anchor_reconstruction", "literature_prior"):
            if self.aggregation not in ("piecewise_constant", "event_date", None):
                raise ConfigError(
                    "anchor_reconstruction/literature_prior aggregation must be "
                    "piecewise_constant, event_date or null"
                )
        else:  # synthetic_generation
            if self.source_frequency != self.result_frequency:
                raise ConfigError("synthetic_generation cannot change frequency")
            if self.aggregation is not None:
                raise ConfigError("synthetic_generation has no aggregation")
        return self


class Provenance(StrictModel):
    """BASELINE §23 provenance block plus P00 extensions (source/digests)."""

    variable: str = Field(min_length=1)
    role: DataRole
    source_institution: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    retrieved_at: UtcDatetime
    raw_sha256: Sha256Hex | None = None
    original_frequency: Frequency
    model_frequency: Frequency
    transformation: Transformation
    evidence_status: EvidenceStatus
    rights: RightsSpec
    notes: str
    source_id: str = Field(min_length=1)
    source_period: str | None = None
    raw_path: str | None = None
    derived_from: list[str] = []
    artifact_sha256: Sha256Hex | None = None

    @model_validator(mode="after")
    def _check_transformation(self) -> Self:
        if self.original_frequency != self.transformation.source_frequency:
            raise ConfigError(
                f"provenance original_frequency {self.original_frequency} disagrees with "
                f"transformation source_frequency {self.transformation.source_frequency}"
            )
        if self.model_frequency != self.transformation.result_frequency:
            raise ConfigError(
                f"provenance model_frequency {self.model_frequency} disagrees with "
                f"transformation result_frequency {self.transformation.result_frequency}"
            )
        return self


class VariableSpec(StrictModel):
    variable_id: str = Field(min_length=1)
    semantic_kind: SemanticKind
    allowed_roles: list[DataRole] = Field(min_length=1)
    unit: str | None = None
    original_frequency: Frequency | None = None
    aggregation: AggregationMethod | None = None
    notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_roles(self) -> Self:
        expected = ROLE_FOR_SEMANTIC_KIND[self.semantic_kind]
        if set(self.allowed_roles) != {expected}:
            raise ConfigError(
                f"variable {self.variable_id}: semantic_kind {self.semantic_kind.value} "
                f"allows exactly role {expected.value}, got {self.allowed_roles}"
            )
        return self


class PeriodRange(StrictModel):
    """Inclusive [start, end] period window at one frequency."""

    start: str = Field(min_length=1)
    end: str = Field(min_length=1)
    frequency: Frequency

    @model_validator(mode="after")
    def _check_bounds(self) -> Self:
        from hsm_lab.data.frequency import period_sort_key, validate_period

        validate_period(self.start, self.frequency)
        validate_period(self.end, self.frequency)
        if self.frequency is Frequency.STATIC and self.start != self.end:
            raise ConfigError("static period range must be a single value")
        if self.frequency is not Frequency.STATIC:
            if period_sort_key(self.start, self.frequency) > period_sort_key(
                self.end, self.frequency
            ):
                raise ConfigError(f"inverted period range {self.start}..{self.end}")
        return self

    def year_span(self) -> tuple[int, int]:
        return int(self.start[:4]), int(self.end[:4])


class Bounds(StrictModel):
    lower: FiniteFloat
    upper: FiniteFloat

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.lower > self.upper:
            raise ConfigError(f"bounds inverted: lower {self.lower} > upper {self.upper}")
        return self


def _check_repo_relative(path: str, artifact_id: str) -> None:
    if not _RELATIVE_PATH_RE.match(path) or ".." in PurePosixPath(path).parts:
        raise ConfigError(
            f"artifact {artifact_id}: path must be repo-relative POSIX without '..' (got {path!r})"
        )


def _anchor_key(text: str) -> tuple[int, int]:
    """Comparable (year, month-ordinal) for YYYY, YYYYQn and YYYY-MM-DD anchors."""
    if re.fullmatch(r"\d{4}Q[1-4]", text):
        return int(text[:4]), int(text[-1]) * 3
    if re.fullmatch(r"\d{4}", text):
        return int(text), 0
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return int(text[:4]), int(text[5:7])
    raise ConfigError(f"invalid anchor date/period {text!r}")


class _ArtifactBase(StrictModel):
    artifact_id: str = Field(min_length=1)
    variable_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    provenance: Provenance
    source_id: str = Field(min_length=1)
    allow_missing: bool = False

    @model_validator(mode="after")
    def _check_alignment(self) -> Self:
        _check_repo_relative(self.path, self.artifact_id)
        if self.provenance.source_id != self.source_id:
            raise ConfigError(
                f"artifact {self.artifact_id}: provenance.source_id "
                f"{self.provenance.source_id!r} != source_id {self.source_id!r}"
            )
        if self.provenance.variable != self.variable_id:
            raise ConfigError(
                f"artifact {self.artifact_id}: provenance.variable "
                f"{self.provenance.variable!r} != variable_id {self.variable_id!r}"
            )
        if self.provenance.role is not self.role:
            raise ConfigError(
                f"artifact {self.artifact_id}: provenance.role "
                f"{self.provenance.role.value} != artifact role {self.role.value}"
            )
        if self.provenance.artifact_sha256 in (None, _PLACEHOLDER_DIGEST) or (
            self.provenance.raw_sha256 == _PLACEHOLDER_DIGEST
        ):
            raise ConfigError(
                f"artifact {self.artifact_id}: real digests are required "
                "(no 'unknown' or zero placeholders)"
            )
        return self

    # ``role`` is declared as a field in each concrete subclass (Literal
    # discriminator); the base only sees it typed for shared validators.
    role: DataRole


class ForcingArtifact(_ArtifactBase):
    role: Literal[DataRole.EXOGENOUS_FORCING] = DataRole.EXOGENOUS_FORCING
    period: PeriodRange


class InitialArtifact(_ArtifactBase):
    role: Literal[DataRole.INITIAL_STATE] = DataRole.INITIAL_STATE
    grade: InitialGrade
    initial_at: str = Field(min_length=1)
    observation_at: str | None = None
    anchor_ids: list[str] = []

    @model_validator(mode="after")
    def _check_grade(self) -> Self:
        _anchor_key(self.initial_at)
        if self.observation_at is not None:
            _anchor_key(self.observation_at)
        evidence = self.provenance.evidence_status
        expected = {
            InitialGrade.A: EvidenceStatus.OBSERVED,
            InitialGrade.B: EvidenceStatus.RECONSTRUCTED,
            InitialGrade.C: EvidenceStatus.LITERATURE_PROXY,
            InitialGrade.S: EvidenceStatus.STRUCTURAL_ASSUMPTION,
        }
        if evidence is not expected[self.grade]:
            raise ConfigError(
                f"artifact {self.artifact_id}: grade {self.grade.value} requires "
                f"evidence_status {expected[self.grade].value}, got {evidence.value}"
            )
        if self.grade is InitialGrade.A:
            if self.observation_at is None:
                raise ConfigError(
                    f"artifact {self.artifact_id}: grade A must keep a real observation_at"
                )
        if self.grade is InitialGrade.B and not self.anchor_ids:
            raise ConfigError(
                f"artifact {self.artifact_id}: grade B requires anchor_ids of the "
                "historical anchors used for reconstruction"
            )
        if self.observation_at is not None and _anchor_key(self.observation_at) > _anchor_key(
            self.initial_at
        ):
            if self.grade is not InitialGrade.B:
                raise ConfigError(
                    f"artifact {self.artifact_id}: observation_at {self.observation_at} is "
                    f"later than initial_at {self.initial_at}; only grade B (reconstructed) "
                    "may bridge anchors - never rename a later observation as earlier "
                    "'observed'"
                )
            if self.provenance.evidence_status is not EvidenceStatus.RECONSTRUCTED:
                raise ConfigError(
                    f"artifact {self.artifact_id}: anchor bridging requires reconstructed "
                    "evidence"
                )
        return self


class TargetArtifact(_ArtifactBase):
    role: Literal[DataRole.TARGET] = DataRole.TARGET
    use: TargetUse
    observed_period: PeriodRange
    comparison_aggregation: Literal["sum", "mean", "end_of_period"]

    @model_validator(mode="after")
    def _check_frequency(self) -> Self:
        if self.observed_period.frequency is not self.provenance.original_frequency:
            raise ConfigError(
                f"artifact {self.artifact_id}: observed_period frequency "
                f"{self.observed_period.frequency.value} != provenance original_frequency "
                f"{self.provenance.original_frequency.value} (annual targets cannot claim "
                "quarterly observations)"
            )
        if self.observed_period.frequency is Frequency.STATIC:
            raise ConfigError(f"artifact {self.artifact_id}: targets cannot be static")
        return self


class ParameterArtifact(_ArtifactBase):
    role: Literal[DataRole.LATENT_PARAMETER] = DataRole.LATENT_PARAMETER
    literature_refs: list[str] = Field(min_length=1)
    prior_description: str = Field(min_length=1)
    bounds: Bounds
    calibration_status: Literal["not_calibrated"] = "not_calibrated"
    sensitivity_status: Literal["not_assessed"] = "not_assessed"
    uncertainty_notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_latent(self) -> Self:
        if self.provenance.evidence_status is EvidenceStatus.OBSERVED:
            raise ConfigError(
                f"artifact {self.artifact_id}: a historical latent parameter can never carry "
                "observed evidence (BASELINE §22.5)"
            )
        return self


class ParameterPriorFile(StrictModel):
    """On-disk JSON prior declaration for a latent parameter."""

    schema_version: str
    variable_id: str = Field(min_length=1)
    literature_refs: list[str] = Field(min_length=1)
    prior_description: str = Field(min_length=1)
    bounds: Bounds
    calibration_status: str = Field(min_length=1)
    sensitivity_status: str = Field(min_length=1)
    uncertainty_notes: str = Field(min_length=1)


ArtifactSpec = Annotated[
    ForcingArtifact | InitialArtifact | TargetArtifact | ParameterArtifact,
    Field(discriminator="role"),
]
