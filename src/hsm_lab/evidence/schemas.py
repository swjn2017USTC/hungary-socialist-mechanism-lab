"""P07A1 §2: typed evidence schemas.

MetricSpec, InterventionBinding, ObservedState, EvidenceRecord.

These schemas validate the shape of declared metrics and interventions.
They do NOT run experiments, read target values, or modify the production engine.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DataRole(StrEnum):
    """Data-role boundary following BASELINE §3–§4 and research_contract.json."""

    FORCING = "forcing"               # external historical driver
    PARAMETER = "parameter"           # calibrated constant (frozen or identified)
    TARGET = "target"                 # admitted comparison target
    RECONSTRUCTED_INITIAL = "reconstructed_initial"  # initial-state anchor
    EXPOSURE = "exposure"             # manually admitted observational series
    CANDIDATE_LINKAGE = "candidate_linkage"  # proposed but not yet admitted
    NOT_ADMITTED = "not_admitted"     # in repository but not cleared for this study


class FidelityLevel(StrEnum):
    """Model-layer fidelity; F1 and F2 must NOT be mixed in one metric."""

    F1_INTERMEDIATE = "F1_intermediate_8"   # 8-good toy layer
    F2_RUN = "F2_run"                       # 16-good formal layer
    F2_DIAGNOSTIC = "F2_diagnostic"          # diagnostic-only F2
    SYNTHETIC = "synthetic"                  # analytical/synthetic probe


class ValidationFidelity(StrEnum):
    """What kind of evidence the metric comparison is made at."""

    EXACT = "exact"                 # same commodity, same aggregation, same unit
    NORMALIZED_INDEX = "normalized_index"   # own-base-year normalised index
    PROXY = "proxy"                 # related but not like-for-like
    NO_COUNTERPART = "no_counterpart"      # no model counterpart at any fidelity


class EvidenceStatus(StrEnum):
    """Lifecycle status of an EvidenceRecord."""

    DECLARED = "declared"          # pre-registered, experiment not run
    INCONCLUSIVE = "inconclusive"   # run completed but result does not support/reject
    SUPPORTED = "supported"        # experiment result supports hypothesis
    REJECTED = "rejected"          # experiment result falsifies hypothesis
    CONDITIONAL = "conditional"    # result depends on unverified assumptions
    WEAK = "weak"                  # underpowered or fragile result
    BLOCKED = "blocked"            # experiment prerequisites not met
    NOT_RUN = "not_run"            # registered but experiment never executed


# ---------------------------------------------------------------------------
# Axis descriptors (non-empty commodity / region selectors)
# ---------------------------------------------------------------------------


class CommodityAxis(BaseModel):
    """A non-empty commodity selector within a MetricSpec or InterventionBinding."""

    model_config = ConfigDict(frozen=True)

    commodities: Annotated[list[str], Field(min_length=1)]  # e.g. ["g03", "g15"]
    unit: str = Field(min_length=1)
    source_recipe: str | None = Field(default=None, description="F1/F2 recipe path if applicable")

    @field_validator("commodities", mode="after")
    @classmethod
    def _no_empty_commodities(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("commodity axis must have at least one commodity")
        return v


class RegionAxis(BaseModel):
    """A spatial axis for regional metrics."""

    model_config = ConfigDict(frozen=True)

    regions: Annotated[list[str], Field(min_length=1)]  # e.g. ["budapest", "pest"]
    unit: str = Field(min_length=1)
    aggregation: str = Field(min_length=1, description="sum | mean | weighted_mean | max")

    @field_validator("regions", mode="after")
    @classmethod
    def _no_empty_regions(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("region axis must have at least one region")
        return v


# ---------------------------------------------------------------------------
# Time window
# ---------------------------------------------------------------------------


class TimeWindow(BaseModel):
    """Temporal extent of a metric or intervention, restricted to the open study window."""

    model_config = ConfigDict(frozen=True)

    start_quarter: str = Field(
        pattern=r"^\d{4}Q[1-4]$",
        description="First quarter (inclusive); must be 1957Q1 or later",
    )
    end_quarter: str = Field(
        pattern=r"^\d{4}Q[1-4]$",
        description="Last quarter (inclusive); must be 1985Q4 or earlier",
    )
    missing_policy: str = Field(
        min_length=1,
        description="Policy when data is absent: zero_fill | skip | interpolate | abort",
    )

    @model_validator(mode="after")
    def _window_order(self) -> TimeWindow:
        if self.start_quarter > self.end_quarter:
            raise ValueError(
                f"start_quarter {self.start_quarter} must not exceed end_quarter {self.end_quarter}"
            )
        return self

    @model_validator(mode="after")
    def _reserved_window_blocked(self) -> TimeWindow:
        """Block the reserved 1986Q1–1988Q4 window per BASELINE §3.1."""
        if self.start_quarter >= "1986Q1":
            raise ValueError(
                f"TimeWindow start {self.start_quarter} violates reserved-window policy "
                "(1986Q1–1988Q4 is closed for this study)"
            )
        return self


# ---------------------------------------------------------------------------
# MetricSpec — declared metric with typed axis, fidelity, unit, and source role
# ---------------------------------------------------------------------------


class MetricSpec(BaseModel):
    """One measurable quantity declared before an experiment is run.

    Attributes
    ----------
    metric_id
        Stable identifier, e.g. ``"M2.bottleneck_demand_count"``.
    table_or_sidecar
        Which output table or sidecar file contains this quantity.
        Must be a real path that exists in the run output tree.
    column
        Column name within ``table_or_sidecar``.
    commodity_axis
        Required if the commodity dimension is present; blocked if empty list.
    region_axis
        Required if the spatial dimension is present; blocked if empty list.
    time_window
        Start/end quarters; must be inside the open study window.
    unit
        Human-readable unit string.
    fidelity
        Model layer (F1_intermediate_8 | F2_run | F2_diagnostic | synthetic).
    data_role
        Role of the source data in the study design.
    validation_fidelity
        How the metric maps to the historical target (if any).
    comparison_grade
        Outcome of the mapping assessment.
    missing_policy
        What to do when the column/row is absent or empty; must NOT be silently填0.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_id: str = Field(min_length=1)
    table_or_sidecar: str = Field(min_length=1)
    column: str = Field(min_length=1)
    commodity_axis: CommodityAxis | None = Field(default=None)
    region_axis: RegionAxis | None = Field(default=None)
    time_window: TimeWindow
    unit: str = Field(min_length=1)
    fidelity: FidelityLevel
    data_role: DataRole
    validation_fidelity: ValidationFidelity
    missing_policy: str = Field(min_length=1)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("missing_policy", mode="after")
    @classmethod
    def _missing_policy_not_zero(cls, v: str) -> str:
        """Reject '0' as missing_policy — silently filling with zero is forbidden."""
        if v == "0":
            raise ValueError(
                "missing_policy='0' is not permitted; "
                "must be one of: zero_fill | skip | interpolate | abort"
            )
        return v

    @model_validator(mode="after")
    def _empty_axis_rejected(self) -> MetricSpec:
        """Empty commodity or region list must raise, not silently pass."""
        if self.commodity_axis is not None and not self.commodity_axis.commodities:
            raise ValueError(
                f"MetricSpec {self.metric_id}: empty commodity_axis is not permitted; "
                "use BLOCKED_METRIC instead of filling with 0"
            )
        if self.region_axis is not None and not self.region_axis.regions:
            raise ValueError(
                f"MetricSpec {self.metric_id}: empty region_axis is not permitted; "
                "use BLOCKED_METRIC instead of filling with 0"
            )
        return self

    @model_validator(mode="after")
    def _illegal_parameter_path_rejected(self) -> MetricSpec:
        """Reject if metric_id looks like a direct parameter write path."""
        forbidden_prefixes = (
            "p04.",
            "p05.",
            "p06.",
            "parameter.",
            "force_",
            "write_",
        )
        for prefix in forbidden_prefixes:
            if self.metric_id.startswith(prefix):
                raise ValueError(
                    f"MetricSpec {self.metric_id}: metric_id '{prefix}...' is a "
                    "forbidden parameter-write path and must be rejected"
                )
        return self


# ---------------------------------------------------------------------------
# InterventionBinding — typed manipulation specification
# ---------------------------------------------------------------------------


class InterventionBinding(BaseModel):
    """One pre-declared policy or parameter manipulation within an experiment.

    Attributes
    ----------
    intervention_id
        Stable identifier, e.g. ``"M2.hardness_plus"``.
    parameter_path
        Dot-path to the model parameter or policy field to change.
        Must be a READABLE kernel path; invalid paths must raise before run.
    baseline_value
        The value before the intervention (for delta computation).
    intervention_value
        The value applied during the intervention arm.
    application_quarter
        Quarter when the change is applied; must be inside the open study window.
    persistence
        Whether the change is one-shot or sustained for the remainder of the run.
    applicable_scenarios
        Which scenario IDs this intervention is valid for.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    intervention_id: str = Field(min_length=1)
    parameter_path: str = Field(min_length=1)
    baseline_value: Any
    intervention_value: Any
    application_quarter: str = Field(
        pattern=r"^\d{4}Q[1-4]$",
        description="Must be 1957Q1–1985Q4; 1986Q1+ blocked",
    )
    persistence: str = Field(
        pattern=r"^(one_shot|sustained|reverted_at)$",
        min_length=1,
    )
    applicable_scenarios: Annotated[list[str], Field(min_length=1)]

    @field_validator("application_quarter", mode="after")
    @classmethod
    def _no_future_quarter(cls, v: str) -> str:
        if v >= "1986Q1":
            raise ValueError(
                f"application_quarter {v} violates reserved-window policy (1986Q1+ closed)"
            )
        return v

    @model_validator(mode="after")
    def _parameter_path_not_future(self) -> InterventionBinding:
        """Parameter path must not contain future-time references."""
        if "future" in self.parameter_path.lower():
            raise ValueError(
                f"InterventionBinding {self.intervention_id}: "
                f"parameter_path '{self.parameter_path}' may not reference future state"
            )
        return self


# ---------------------------------------------------------------------------
# ObservedState — snapshot of a run output used as input to a later experiment
# ---------------------------------------------------------------------------


class ObservedState(BaseModel):
    """A provenance-tracked snapshot of model output used as an input to a later run.

    This is NOT a raw historical target; it is model-produced output preserved
    for reproducibility and cross-phase linkage.
    """

    model_config = ConfigDict(frozen=True)

    observed_state_id: str = Field(min_length=1)
    source_run_id: str = Field(min_length=1)
    source_scenario: str = Field(min_length=1)
    source_checkpoint_quarter: str = Field(pattern=r"^\d{4}Q[1-4]$")
    source_digest: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 of the source run directory tree at capture time",
    )
    captured_at: str = Field(
        description="ISO-8601 timestamp of capture; not used for execution"
    )


# ---------------------------------------------------------------------------
# EvidenceRecord — one pre-registered experiment record
# ---------------------------------------------------------------------------


class EvidenceRecord(BaseModel):
    """One mechanism's pre-registered experiment bundle.

    This record is created at study declaration time (before any experiment
    is run). It contains typed MetricSpecs and InterventionBindings, a
    provenance DAG node, and a status field. The record does NOT contain
    raw target values or historical data beyond declared references.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str = Field(min_length=1, description="Unique, stable identifier")
    mechanism_id: str = Field(
        pattern=r"^M(?:[1-9]|1[01])$",
        description="Corresponds to config/p06/cards/M*.json",
    )
    v1_card_sha256: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 of the corresponding v1 card JSON; anchors provenance DAG",
    )
    supersedes_card_sha256: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
        description="If this is a v2 card, SHA-256 of the superseded v1 card",
    )
    hypothesis: str = Field(min_length=1)
    status: EvidenceStatus = Field(
        default=EvidenceStatus.DECLARED,
        description="Initial status; updated after experiment runs",
    )
    metric_specs: Annotated[list[MetricSpec], Field(min_length=1)]
    intervention_bindings: list[InterventionBinding] = Field(default_factory=list)
    linked_observed_states: list[ObservedState] = Field(default_factory=list)
    declared_reason: str = Field(
        min_length=1,
        description="Why this experiment is declared (or blocked) at this phase",
    )
    blocked_reason: str | None = Field(
        default=None,
        description="If status is BLOCKED, the specific blocking condition",
    )
    minimum_replicates: int = Field(ge=1, default=1)
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )
    created_by_phase: str = Field(min_length=1)

    @model_validator(mode="after")
    def _blocked_must_have_reason(self) -> EvidenceRecord:
        if self.status == EvidenceStatus.BLOCKED and not self.blocked_reason:
            raise ValueError(
                f"EvidenceRecord {self.record_id}: status=BLOCKED requires blocked_reason"
            )
        return self

    @model_validator(mode="after")
    def _declared_requires_metrics(self) -> EvidenceRecord:
        if self.status == EvidenceStatus.DECLARED and not self.metric_specs:
            raise ValueError(
                f"EvidenceRecord {self.record_id}: "
                "status=DECLARED requires at least one metric_spec"
            )
        return self


# ---------------------------------------------------------------------------
# EvidenceManifest — collection of EvidenceRecords for one phase
# ---------------------------------------------------------------------------


class EvidenceManifest(BaseModel):
    """Top-level manifest for one phase's evidence registry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_version: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    records: Annotated[list[EvidenceRecord], Field(min_length=1)]

    def get_record(self, mechanism_id: str) -> EvidenceRecord | None:
        for rec in self.records:
            if rec.mechanism_id == mechanism_id:
                return rec
        return None

    def record_ids(self) -> list[str]:
        return [rec.record_id for rec in self.records]

    def mechanism_ids(self) -> list[str]:
        return sorted({rec.mechanism_id for rec in self.records})
