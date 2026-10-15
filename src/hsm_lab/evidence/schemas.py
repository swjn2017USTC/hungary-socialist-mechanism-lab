"""P07A1 §2: typed evidence schemas.

MetricSpec, InterventionBinding, ObservedState, EvidenceRecord.

These schemas validate the shape of declared metrics and interventions.
They do NOT run experiments, read target values, or modify the production engine.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hsm_lab.contract.schemas import Quarter

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


class MissingPolicy(StrEnum):
    """Strict missing-data policy; no zero_fill variants or aliases accepted."""

    ABORT = "abort"
    SKIP = "skip"
    INTERPOLATE = "interpolate"


# ---------------------------------------------------------------------------
# Mechanism ID normalisation (H0A §2.1)
# ---------------------------------------------------------------------------


def canonical_mechanism_id(value: str) -> str:
    """Convert M1-M11 or M01-M09 to canonical M01-M11 form.

    Examples
    --------
    >>> canonical_mechanism_id("M1")   # "M01"
    >>> canonical_mechanism_id("m01") # "M01"
    >>> canonical_mechanism_id("M10")  # "M10"
    """
    v = value.strip()
    m = re.match(r"^M0?([1-9]|1[01])$", v, re.IGNORECASE)
    if not m:
        raise ValueError(f"Invalid mechanism ID: {value!r}")
    n = int(m.group(1))
    return f"M{n:02d}"


def study_mechanism_id(value: str) -> str:
    """Convert M01-M11 or M1-M11 to study form M1-M9 (no leading zero).

    Raises ValueError for M10, M11, M00, M12, M001, or any unrecognised form.
    """
    v = value.strip()
    m = re.match(r"^M0?([1-9]|1[01])$", v, re.IGNORECASE)
    if not m:
        raise ValueError(f"Invalid mechanism ID: {value!r}")
    n = int(m.group(1))
    if n > 9:
        raise ValueError(f"Study mechanism ID must be M1-M9; got {value!r}")
    return f"M{n}"


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
    missing_policy: MissingPolicy

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

    @model_validator(mode="after")
    def _study_window(self) -> TimeWindow:
        """Enforce 1957Q1 <= start <= end <= 1985Q4 using ordinal arithmetic."""
        start_q = Quarter.parse(self.start_quarter)
        end_q = Quarter.parse(self.end_quarter)
        min_ordinal = Quarter.parse("1957Q1").to_ordinal()
        max_ordinal = Quarter.parse("1985Q4").to_ordinal()
        if start_q.to_ordinal() < min_ordinal:
            raise ValueError(
                f"TimeWindow start {self.start_quarter} is before 1957Q1 (study window)"
            )
        if end_q.to_ordinal() > max_ordinal:
            raise ValueError(
                f"TimeWindow end {self.end_quarter} is after 1985Q4 (study window)"
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
    missing_policy: MissingPolicy
    description: str | None = Field(default=None, max_length=500)

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
    def _application_quarter_bounds(cls, v: str) -> str:
        """Enforce 1957Q1 <= application_quarter <= 1985Q4 using ordinal arithmetic."""
        q = Quarter.parse(v)
        min_ord = Quarter.parse("1957Q1").to_ordinal()
        max_ord = Quarter.parse("1985Q4").to_ordinal()
        ord_ = q.to_ordinal()
        if ord_ < min_ord:
            raise ValueError(
                f"application_quarter {v} is before 1957Q1 (study window)"
            )
        if ord_ > max_ord:
            raise ValueError(
                f"application_quarter {v} is after 1985Q4 (study window)"
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

    model_config = ConfigDict(frozen=True, extra="forbid")

    observed_state_id: str = Field(min_length=1)
    source_run_id: str = Field(min_length=1)
    source_scenario: str = Field(min_length=1)
    source_checkpoint_quarter: str = Field(pattern=r"^\d{4}Q[1-4]$")
    source_digest: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 of the source run directory tree at capture time",
    )

    @field_validator("source_digest", mode="after")
    @classmethod
    def _source_digest_not_zero(cls, v: str) -> str:
        """Reject all-zero SHA-256 digests."""
        if v == "0" * 64:
            raise ValueError("source_digest must not be all zeros")
        return v

    captured_at: str = Field(
        description="ISO-8601 timestamp of capture; not used for execution",
    )
    available_at: str = Field(
        pattern=r"^\d{4}Q[1-4]$",
        description=(
            "First quarter this snapshot is admissible as input; "
            "source_checkpoint_quarter <= available_at"
        ),
    )
    decision_at: str = Field(
        pattern=r"^\d{4}Q[1-4]$",
        description=(
            "Quarter of the decision that consumes this snapshot; "
            "available_at <= decision_at"
        ),
    )

    @model_validator(mode="after")
    def _availability_order(self) -> ObservedState:
        """Enforce source_checkpoint_quarter <= available_at <= decision_at,
        and all three are within the open study window [1957Q1, 1985Q4].
        """
        # Study window boundaries
        WINDOW_START = Quarter.parse("1957Q1")
        WINDOW_END = Quarter.parse("1985Q4")

        cp = Quarter.parse(self.source_checkpoint_quarter)
        av = Quarter.parse(self.available_at)
        dc = Quarter.parse(self.decision_at)

        # Check absolute window boundaries
        if cp.to_ordinal() < WINDOW_START.to_ordinal():
            raise ValueError(
                f"ObservedState {self.observed_state_id}: "
                f"source_checkpoint_quarter {self.source_checkpoint_quarter} is before "
                f"study window start {WINDOW_START}"
            )
        if cp.to_ordinal() > WINDOW_END.to_ordinal():
            raise ValueError(
                f"ObservedState {self.observed_state_id}: "
                f"source_checkpoint_quarter {self.source_checkpoint_quarter} is after "
                f"study window end {WINDOW_END}"
            )
        if av.to_ordinal() < WINDOW_START.to_ordinal():
            raise ValueError(
                f"ObservedState {self.observed_state_id}: "
                f"available_at {self.available_at} is before study window start"
            )
        if av.to_ordinal() > WINDOW_END.to_ordinal():
            raise ValueError(
                f"ObservedState {self.observed_state_id}: "
                f"available_at {self.available_at} is after study window end"
            )
        if dc.to_ordinal() < WINDOW_START.to_ordinal():
            raise ValueError(
                f"ObservedState {self.observed_state_id}: "
                f"decision_at {self.decision_at} is before study window start"
            )
        if dc.to_ordinal() > WINDOW_END.to_ordinal():
            raise ValueError(
                f"ObservedState {self.observed_state_id}: "
                f"decision_at {self.decision_at} is after study window end"
            )

        # Check relative ordering
        if av.to_ordinal() < cp.to_ordinal():
            raise ValueError(
                f"ObservedState {self.observed_state_id}: "
                f"available_at {self.available_at} < "
                f"source_checkpoint_quarter {self.source_checkpoint_quarter}"
            )
        if dc.to_ordinal() < av.to_ordinal():
            raise ValueError(
                f"ObservedState {self.observed_state_id}: "
                f"decision_at {self.decision_at} < available_at {self.available_at}"
            )
        return self


# ---------------------------------------------------------------------------
# EvidenceRunReference — provenance handle to an actual run (H0A §5.1)
# ---------------------------------------------------------------------------


class EvidenceRunReference(BaseModel):
    """A strict handle to an actual scenario run on disk.

    This is NOT a trusted verification result; it is a locating pointer.
    The referenced run must pass verify_run_identity before the containing
    EvidenceRecord may be promoted to SUPPORTED.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(
        min_length=1,
        description="Unique run identifier from RunManifest.run_id",
    )
    scenario_id: str = Field(
        min_length=1,
        description="Scenario identifier, e.g. historical_f2_replay",
    )
    seed: int = Field(
        ge=0,
        description="Non-negative integer seed used for this run",
    )
    output_dir: Path = Field(
        description="Absolute or root-relative path to the run output directory",
    )

    @field_validator("seed", mode="before")
    @classmethod
    def _seed_not_bool(cls, v: object) -> int:
        """Reject bool before coercion; Pydantic coerces str/float in non-strict mode."""
        if isinstance(v, bool):
            raise ValueError("seed must be a strict integer; bool is not allowed")
        return v

    digest: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 digest of the full output tree at run completion",
    )

    @field_validator("digest", mode="after")
    @classmethod
    def _digest_not_zero(cls, v: str) -> str:
        """Reject all-zero SHA-256 digests."""
        if v == "0" * 64:
            raise ValueError("digest must not be all zeros")
        return v


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

    @field_validator("v1_card_sha256", mode="after")
    @classmethod
    def _v1_card_sha256_not_zero(cls, v: str) -> str:
        """Reject all-zero SHA-256 digests."""
        if v == "0" * 64:
            raise ValueError("v1_card_sha256 must not be all zeros")
        return v

    @field_validator("supersedes_card_sha256", mode="after")
    @classmethod
    def _supersedes_card_sha256_not_zero(cls, v: str | None) -> str | None:
        """Reject all-zero SHA-256 digests for v2 cards."""
        if v is not None and v == "0" * 64:
            raise ValueError("supersedes_card_sha256 must not be all zeros")
        return v

    hypothesis: str = Field(min_length=1)
    status: EvidenceStatus = Field(
        default=EvidenceStatus.DECLARED,
        description="Initial status; updated after experiment runs",
    )
    metric_specs: Annotated[list[MetricSpec], Field(min_length=1)]
    intervention_bindings: list[InterventionBinding] = Field(default_factory=list)
    linked_observed_states: list[ObservedState] = Field(default_factory=list)
    run_references: list[EvidenceRunReference] = Field(default_factory=list)
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

    @model_validator(mode="after")
    def _supported_requires_runs(self) -> EvidenceRecord:
        """SUPPORTED status requires verified run references.

        Run-time verify_run_identity is performed by the loader (which has
        access to root, scenario_id, seed, and expected_digest). Here we
        enforce the structural pre-conditions: non-empty run_references,
        unique run_ids, and sufficient replicate count.
        """
        if self.status != EvidenceStatus.SUPPORTED:
            return self
        if not self.run_references:
            raise ValueError(
                f"EvidenceRecord {self.record_id}: "
                "status=SUPPORTED requires at least one run_reference"
            )
        # run_id uniqueness
        seen_ids: set[str] = set()
        for ref in self.run_references:
            if ref.run_id in seen_ids:
                raise ValueError(
                    f"EvidenceRecord {self.record_id}: run_id {ref.run_id!r} "
                    "is duplicated in run_references"
                )
            seen_ids.add(ref.run_id)
        # Minimum replicates: unique (run_id, seed) pairs must meet minimum_replicates
        seen_pairs: set[tuple[str, int]] = set()
        for ref in self.run_references:
            pair = (ref.run_id, ref.seed)
            if pair in seen_pairs:
                raise ValueError(
                    f"EvidenceRecord {self.record_id}: (run_id, seed) pair "
                    f"{pair} is duplicated; minimum_replicates={self.minimum_replicates} "
                    "requires unique pairs"
                )
            seen_pairs.add(pair)
        if len(seen_pairs) < self.minimum_replicates:
            raise ValueError(
                f"EvidenceRecord {self.record_id}: "
                f"run_references has {len(seen_pairs)} unique (run_id, seed) pairs, "
                f"but minimum_replicates={self.minimum_replicates}"
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


# ---------------------------------------------------------------------------
# StudyDeclaration & StudyManifest — intent/linked_cards records (H0A §2.2)
# ---------------------------------------------------------------------------


class StudyDeclaration(BaseModel):
    """A study-intent record (intent/linked_cards form), NOT an EvidenceRecord.

    This corresponds to the real records in studies/manifest.json. It is
    distinct from EvidenceRecord which uses hypothesis/metric_specs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    linked_cards: Annotated[list[str], Field(min_length=1)]
    status: Literal["declared", "blocked"]
    declared_reason: str | None = Field(default=None)
    blocked_reason: str | None = Field(default=None)
    v1_card_sha256: str | None = Field(default=None)
    phase: str | None = Field(default=None)
    research_package_complete: Literal[False] = Field(default=False)
    note: str | None = Field(default=None)

    @property
    def card_id(self) -> str:
        """Return canonical M1-M11 key for the primary linked card (first entry)."""
        return canonical_mechanism_id(self.linked_cards[0])

    @model_validator(mode="after")
    def _status_reason_consistency(self) -> StudyDeclaration:
        if self.status == "declared" and not self.declared_reason:
            raise ValueError(
                f"StudyDeclaration {self.record_id}: status=declared requires declared_reason"
            )
        if self.status == "blocked" and not self.blocked_reason:
            raise ValueError(
                f"StudyDeclaration {self.record_id}: status=blocked requires blocked_reason"
            )
        return self

    @model_validator(mode="after")
    def _linked_cards_identity(self) -> StudyDeclaration:
        """Each linked card's canonical identity must belong to the same mechanism;
        cross-card borrowing (e.g. linking M2 when mechanism_id is M01) is not allowed.
        """
        # Canonical form of the declaration's own mechanism_id
        self_canonical = canonical_mechanism_id(self.mechanism_id)
        for card in self.linked_cards:
            try:
                card_canonical = canonical_mechanism_id(card)
                # Cross-card borrowing: linked card maps to a different mechanism
                if card_canonical != self_canonical:
                    raise ValueError(
                        f"StudyDeclaration {self.record_id}: "
                        f"linked_card {card!r} maps to canonical {card_canonical}, "
                        f"which differs from declaration's mechanism {self_canonical} — "
                        "cross-card borrowing is not allowed"
                    )
            except ValueError as exc:
                raise ValueError(
                    f"StudyDeclaration {self.record_id}: linked_card {card!r} is not a valid "
                    f"mechanism ID (M1–M11): {exc}"
                ) from exc
        return self


class StudyManifest(BaseModel):
    """Top-level manifest for study-intent records (intent/linked_cards form)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_version: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    description: str | None = Field(default=None)
    created_by_phase: str = Field(min_length=1)
    records: Annotated[list[StudyDeclaration], Field(min_length=1)]

    @model_validator(mode="after")
    def _no_duplicate_record_ids(self) -> StudyManifest:
        seen: set[str] = set()
        for rec in self.records:
            if rec.record_id in seen:
                raise ValueError(
                    f"StudyManifest: duplicate record_id {rec.record_id!r}"
                )
            seen.add(rec.record_id)
        return self
