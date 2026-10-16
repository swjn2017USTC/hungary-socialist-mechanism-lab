"""P07A1 §5 / H0B §4: v1 card → v2 MetricSpec registry adapter.

This module reads existing v1 mechanism cards (config/p06/cards/M*.json),
verifies each card's bytes against the frozen H0B identity map, registers every
declared card metric at ``(legacy_card_id, metrics-array index, verbatim
metric string)`` granularity, and reports per-metric observability against a
real run's output tree. It does NOT run experiments, does NOT read target
values, and does NOT modify the production engine.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from hsm_lab.evidence.loader import (
    _is_missing_value,
    _is_nonfinite_value,
    _metric_artifact_path,
)
from hsm_lab.evidence.metric_enricher import (
    UNIT_CONSTRAINT_LABEL,
    MetricComponent,
    MetricEnrichment,
    enrich_metric_spec,
    get_blocked_metric,
    get_metric_enrichment,
    is_mapped_metric,
    metric_commodity_units,
)
from hsm_lab.evidence.schemas import (
    MetricSpec,
    MissingPolicy,
    canonical_mechanism_id,
)
from hsm_lab.evidence.table_registry import is_optional_sidecar


class MetricSpecRegistry(BaseModel):
    """Read-only registry of MetricSpecs derived from v1 cards.

    This registry is built at P07A1 load time. It is not an experiment
    runner and does not produce results.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    phase: str = Field(min_length=1)
    registry_version: str = Field(min_length=1)
    v1_cards_sha256: dict[str, str] = Field(
        description="mechanism_id → SHA-256 of v1 card JSON"
    )
    metric_specs: Annotated[list[MetricSpec], Field(min_length=1)]


def _compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_v1_card_sha256_map(root: Path) -> dict[str, str]:
    """Compute SHA-256 for each v1 card file.

    Returns
    -------
    dict[str, str]
        mechanism_id → SHA-256 hex string.
    """
    card_dir = root / "config" / "p06" / "cards"
    result: dict[str, str] = {}
    for card_path in sorted(card_dir.glob("M*.json")):
        mechanism_id = card_path.stem
        result[mechanism_id] = _compute_sha256(card_path)
    return result


def load_v2_card_registry(root: Path, phase: str) -> MetricSpecRegistry:
    """Build the MetricSpec registry through the verified semantic registration.

    The registry is not derived from the cards by a second, weaker path: it is
    the H0B :func:`register_legacy_cards` registration, which verifies every
    card's bytes against the frozen identity map and enriches every declared
    metric through the enricher. A placeholder spec
    (``table_or_sidecar="unknown"``, ``unit="unknown"``) is never constructed,
    and a card that was edited is refused rather than described under a frozen
    id.

    Parameters
    ----------
    root
        Repository root.
    phase
        Current phase label.

    Returns
    -------
    MetricSpecRegistry
        One verified MetricSpec per declared metric (41), each MAPPED to its
        single model counterpart or BLOCKED with its reason.
    """
    registered = register_legacy_cards(root)
    return MetricSpecRegistry(
        phase=phase,
        registry_version="1.0.0",
        v1_cards_sha256={
            card.mechanism_id: card.sha256 for card in registered.cards
        },
        metric_specs=[
            registration.spec for registration in registered.registrations
        ],
    )


# ---------------------------------------------------------------------------
# H0B §4: legacy-card semantic registration
# ---------------------------------------------------------------------------

#: SHA-256 of every legacy card, as frozen by the HIST-VNEXT identity map
#: (MECHANISM_IDENTITY_MAP.json, 02_MECHANISM_IDENTITY_RECONCILIATION.md).
#: Registration compares the bytes on disk with these digests: a card that was
#: edited is a different card, and describing it under the frozen identity
#: would attach new semantics to an old name.
FROZEN_V1_CARD_SHA256: dict[str, str] = {
    "M1": "7a3beaa4be817cfb745a163c579b0ec472fcfb3f55c8caaca7db15854c74352d",
    "M2": "0da621e51ad436103ec3c76d820701cda84e8bb0c9cb79ef0947337856990589",
    "M3": "06adefbd144800d1ff2afd10f5f73765f6e70339d1280ba002b434bb6e32f8ba",
    "M4": "c9e70e5ca07bca8e7865f274dc052cb1ed5aed795787a9a07f16ec37fb5323ac",
    "M5": "cdcbbfbd8d99b8b0d55f1afeaf564d2fac5cef3cd53d7058f75943af611bd879",
    "M6": "047db0a8473f326c8a6a2609bc18ea42c24cb979a96f0a20cf254575dde5e6c6",
    "M7": "f6383c8b16fa5f16e2517ec992da2524a2ba1eb31612ff4c542515f3d3399d90",
    "M8": "f4761f7f7b3865e61d285ccdd058c91ee0cfd463964cb2b7c4b6f03e22dd0bd1",
    "M9": "fa1b30703cda0009471e03cdf6b88b47d20a7ce525385adfdd554f595e55273c",
    "M10": "c23d545b59432e6f9412c512824aba5af40cc242daaa4c65239c6f4ae129b880",
    "M11": "c65318dc1d4c149d7d15b49db229c19768a282f5e6c59307197fe194d1c86887",
}

LEGACY_CARD_IDS: tuple[str, ...] = tuple(FROZEN_V1_CARD_SHA256)


class LegacyCardIdentityError(ValueError):
    """A legacy card's bytes, id, or metric list contradict the frozen map."""


def card_relative_path(mechanism_id: str) -> str:
    """The repository-relative path of one legacy card."""
    if mechanism_id not in FROZEN_V1_CARD_SHA256:
        raise LegacyCardIdentityError(
            f"{mechanism_id!r} is not one of the legacy cards "
            f"{list(LEGACY_CARD_IDS)}"
        )
    return f"config/p06/cards/{mechanism_id}.json"


def study_id_for(mechanism_id: str) -> str:
    """The study id of a legacy card: ``M1`` → ``M01`` … ``M11`` → ``M11``.

    This is the explicit one-to-one identity map frozen by
    02_MECHANISM_IDENTITY_RECONCILIATION.md, resolved through H0A's
    :func:`hsm_lab.evidence.schemas.canonical_mechanism_id` so the canonical
    check is the one H0A already performs. It is deliberately *not*
    :func:`hsm_lab.evidence.schemas.study_mechanism_id`, which rejects M10/M11.
    """
    if mechanism_id not in FROZEN_V1_CARD_SHA256:
        raise LegacyCardIdentityError(f"unknown legacy card id {mechanism_id!r}")
    return canonical_mechanism_id(mechanism_id)


@dataclass(frozen=True)
class LegacyCard:
    """One legacy card as it exists on disk, with its frozen identity."""

    mechanism_id: str
    study_id: str
    relative_path: str
    sha256: str
    metrics: tuple[str, ...]


@dataclass(frozen=True)
class RegisteredMetric:
    """One declared card metric at H0B registration granularity.

    The granularity is ``(legacy_card_id, metrics-array index, verbatim
    metric string)``: no metric is stripped, reworded, deduplicated or
    expanded into its components, so the 41 declared items stay 41 items.
    """

    mechanism_id: str
    study_id: str
    card_sha256: str
    metric_index: int
    exact_original_metric: str
    status: str
    spec: MetricSpec
    enrichment: MetricEnrichment | None
    blocked_reason: str | None
    components: tuple[MetricComponent, ...]

    @property
    def key(self) -> str:
        """``(card, index)`` as a stable string, e.g. ``"M1#0"``."""
        return f"{self.mechanism_id}#{self.metric_index}"

    @property
    def is_blocked(self) -> bool:
        return self.status == "blocked"

    def commodity_units(self) -> dict[str, str] | None:
        """Ontology units per commodity for a physical metric, else None."""
        return metric_commodity_units(self.mechanism_id, self.exact_original_metric)


@dataclass(frozen=True)
class LegacySemanticRegistry:
    """The H0B registration of all 11 legacy cards (read-only)."""

    cards: tuple[LegacyCard, ...]
    registrations: tuple[RegisteredMetric, ...]

    def for_card(self, mechanism_id: str) -> tuple[RegisteredMetric, ...]:
        """The registrations of one card, in declaration order."""
        return tuple(
            r for r in self.registrations if r.mechanism_id == mechanism_id
        )

    def mapped(self) -> tuple[RegisteredMetric, ...]:
        return tuple(r for r in self.registrations if not r.is_blocked)

    def blocked(self) -> tuple[RegisteredMetric, ...]:
        return tuple(r for r in self.registrations if r.is_blocked)

    def counts(self) -> dict[str, int]:
        """``{"cards", "metrics", "mapped", "blocked"}``."""
        return {
            "cards": len(self.cards),
            "metrics": len(self.registrations),
            "mapped": len(self.mapped()),
            "blocked": len(self.blocked()),
        }

    def identity_map(self) -> dict[str, str]:
        """legacy card id → study id, for the cards actually registered."""
        return {card.mechanism_id: card.study_id for card in self.cards}

    def identity_map_sha256(self) -> dict[str, str]:
        """legacy card id → verified SHA-256, for the cards registered."""
        return {card.mechanism_id: card.sha256 for card in self.cards}


def _read_legacy_card(root: Path, mechanism_id: str) -> LegacyCard:
    """Read and verify one legacy card against the frozen identity map.

    Raises
    ------
    LegacyCardIdentityError
        If the file is missing, its SHA-256 is not the frozen digest, its
        declared ``mechanism_id`` is not the file's id, or its ``metrics``
        array is missing/empty/non-string.
    """
    relative = card_relative_path(mechanism_id)
    path = root / relative
    try:
        payload_bytes = path.read_bytes()
    except OSError as error:
        raise LegacyCardIdentityError(f"legacy card {relative} is unreadable: {error}") from error
    digest = hashlib.sha256(payload_bytes).hexdigest()
    expected = FROZEN_V1_CARD_SHA256[mechanism_id]
    if digest != expected:
        raise LegacyCardIdentityError(
            f"legacy card {relative} has SHA-256 {digest}, not the frozen "
            f"{expected}; refusing to register an edited card under a frozen id"
        )
    payload = json.loads(payload_bytes.decode("utf-8"))
    declared_id = payload.get("mechanism_id")
    if declared_id != mechanism_id:
        raise LegacyCardIdentityError(
            f"legacy card {relative} declares mechanism_id {declared_id!r}, "
            f"not {mechanism_id!r}"
        )
    metrics = payload.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise LegacyCardIdentityError(
            f"legacy card {relative} declares no metrics array"
        )
    for index, metric in enumerate(metrics):
        if not isinstance(metric, str) or not metric:
            raise LegacyCardIdentityError(
                f"legacy card {relative} metric[{index}] is not a non-empty "
                f"string: {metric!r}"
            )
    return LegacyCard(
        mechanism_id=mechanism_id,
        study_id=study_id_for(mechanism_id),
        relative_path=relative,
        sha256=digest,
        metrics=tuple(metrics),
    )


def load_legacy_cards(root: Path) -> tuple[LegacyCard, ...]:
    """Read all 11 legacy cards, verifying each against the frozen map.

    Raises
    ------
    LegacyCardIdentityError
        If a card is missing, edited, or if the card directory holds a card
        the frozen identity map does not know (a new card must be registered
        deliberately, not absorbed into H0B's 11).
    """
    card_dir = root / "config" / "p06" / "cards"
    known = {f"{mechanism_id}.json" for mechanism_id in LEGACY_CARD_IDS}
    present = {path.name for path in card_dir.glob("M*.json")}
    unexpected = sorted(present - known)
    if unexpected:
        raise LegacyCardIdentityError(
            f"legacy card directory holds cards the frozen identity map does "
            f"not know: {unexpected}"
        )
    return tuple(_read_legacy_card(root, mechanism_id) for mechanism_id in LEGACY_CARD_IDS)


def register_legacy_card(root: Path, mechanism_id: str) -> tuple[RegisteredMetric, ...]:
    """Register every metric one legacy card declares, in declaration order."""
    card = _read_legacy_card(root, mechanism_id)
    registrations: list[RegisteredMetric] = []
    for index, metric in enumerate(card.metrics):
        blocked = get_blocked_metric(card.mechanism_id, metric)
        mapped = is_mapped_metric(card.mechanism_id, metric)
        spec = enrich_metric_spec(card.mechanism_id, metric)
        registrations.append(
            RegisteredMetric(
                mechanism_id=card.mechanism_id,
                study_id=card.study_id,
                card_sha256=card.sha256,
                metric_index=index,
                exact_original_metric=metric,
                status="mapped" if mapped else "blocked",
                spec=spec,
                enrichment=get_metric_enrichment(card.mechanism_id, metric),
                blocked_reason=None if mapped else spec.blocked_reason,
                components=blocked.components if blocked is not None else (),
            )
        )
    return tuple(registrations)


def register_legacy_cards(root: Path) -> LegacySemanticRegistry:
    """Register all 11 legacy cards end to end.

    Every declared metric ends MAPPED (one model counterpart) or BLOCKED (with
    its reason); none is dropped or zero-filled.

    Raises
    ------
    LegacyCardIdentityError
        If any card's bytes or declarations contradict the frozen identity map.
    """
    cards = load_legacy_cards(root)
    registrations = tuple(
        registration
        for card in cards
        for registration in register_legacy_card(root, card.mechanism_id)
    )
    return LegacySemanticRegistry(cards=cards, registrations=registrations)


# ---------------------------------------------------------------------------
# H0B §4: per-run observability of a registered metric
# ---------------------------------------------------------------------------


class ObservationStatus(StrEnum):
    """Why a registered metric can or cannot be read from one run.

    The statuses are deliberately distinct. A missing file, a missing column,
    a wrongly typed column, an empty table, a window with no rows, an
    unmatched selector, an absent sidecar and a genuine zero are different
    observations, and only the last one is a measurement: an empty table or an
    absent artifact MUST NOT be reported as zero, and a column whose datatype
    contradicts the metric's declared semantics MUST NOT be read as data.
    """

    SEMANTICS_BLOCKED = "semantics_blocked"
    SIDECAR_ABSENT = "sidecar_absent"
    ARTIFACT_ABSENT = "artifact_absent"
    TABLE_EMPTY = "table_empty"
    COLUMN_ABSENT = "column_absent"
    DATATYPE_MISMATCH = "datatype_mismatch"
    WINDOW_EMPTY = "window_empty"
    SELECTOR_UNMATCHED = "selector_unmatched"
    NULL_VALUES = "null_values"
    NONFINITE_VALUES = "nonfinite_values"
    OBSERVABLE_ZERO = "observable_zero"
    OBSERVABLE = "observable"


#: How many distinct finite values an observation keeps (a report, not a dump).
_MAX_REPORTED_VALUES = 8

#: Units whose declared values are categories, not quantities. A metric that
#: declares one of these is observed as the labels it declares; every other
#: declared unit (physical, monetary, count, index, scalar, utility) is a
#: quantity, so a non-numeric column under it is a datatype mismatch rather
#: than a categorical measurement.
CATEGORICAL_UNITS: frozenset[str] = frozenset({UNIT_CONSTRAINT_LABEL})


@dataclass(frozen=True)
class MetricObservation:
    """What one registered metric looks like in one run output tree."""

    key: str
    mechanism_id: str
    metric_index: int
    metric_id: str
    exact_original_metric: str
    status: ObservationStatus
    detail: str
    artifact: str | None = None
    rows: int | None = None
    window_rows: int | None = None
    values: tuple[float, ...] | None = None
    labels: tuple[str, ...] | None = None
    """Distinct categorical values, for a metric that declares a label unit.

    A label metric (e.g. M9's ``policy_decisions.binding_constraints``, which
    declares the ``binding_constraint_label`` unit) carries categories, not
    quantities: coercing a category to ``float`` would either crash or invent
    a number, so the categorical values are reported as the strings they are
    and ``values`` stays ``None``. A metric that declares a quantity unit is
    never observed this way -- a non-numeric column under it is a datatype
    mismatch, not a category.
    """

    @property
    def observable(self) -> bool:
        """True only when the run really carries the quantity."""
        return self.status in (
            ObservationStatus.OBSERVABLE,
            ObservationStatus.OBSERVABLE_ZERO,
        )


def _observation(
    registration: RegisteredMetric,
    status: ObservationStatus,
    detail: str,
    *,
    artifact: Path | None = None,
    rows: int | None = None,
    window_rows: int | None = None,
    values: tuple[float, ...] | None = None,
    labels: tuple[str, ...] | None = None,
) -> MetricObservation:
    return MetricObservation(
        key=registration.key,
        mechanism_id=registration.mechanism_id,
        metric_index=registration.metric_index,
        metric_id=registration.spec.metric_id,
        exact_original_metric=registration.exact_original_metric,
        status=status,
        detail=detail,
        artifact=None if artifact is None else str(artifact),
        rows=rows,
        window_rows=window_rows,
        values=values,
        labels=labels,
    )


def resolve_run_artifact(run_dir: Path, name: str) -> Path | None:
    """Locate a run artefact by name, using the evidence gate's own resolver.

    This is the promotion gate's :func:`hsm_lab.evidence.loader.
    _metric_artifact_path`, not a second copy of its candidate order: a report
    about where a metric lives must never disagree with the path the gate would
    actually read. Candidates are ``<name>.parquet`` at the run root, then
    under ``trajectory_tables/``, then the file ``<name>``, then the sidecar
    ``<name>.json``, and only inside the run directory.
    """
    return _metric_artifact_path(run_dir, name)


def _selector_columns(spec: MetricSpec) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """The ``(axis column, declared values)`` pairs a spec declares."""
    pairs: list[tuple[str, tuple[str, ...]]] = []
    if spec.commodity_axis is not None:
        pairs.append(("commodity_id", tuple(spec.commodity_axis.commodities)))
    if spec.region_axis is not None:
        pairs.append(("region_id", tuple(spec.region_axis.regions)))
    return tuple(pairs)


def _observe_parquet(
    registration: RegisteredMetric,
    artifact: Path,
) -> MetricObservation:
    import pyarrow as pa  # type: ignore[import-untyped]
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    spec = registration.spec
    table = pq.read_table(artifact)
    rows = table.num_rows
    if rows == 0:
        return _observation(
            registration,
            ObservationStatus.TABLE_EMPTY,
            "the table exists with 0 rows: an empty table is not a measured zero",
            artifact=artifact,
            rows=0,
        )
    columns = table.schema.names
    if spec.column not in columns:
        return _observation(
            registration,
            ObservationStatus.COLUMN_ABSENT,
            f"column '{spec.column}' is not in {artifact.name} "
            f"({len(columns)} columns)",
            artifact=artifact,
            rows=rows,
        )
    window = spec.time_window
    if "quarter" not in columns:
        return _observation(
            registration,
            ObservationStatus.WINDOW_EMPTY,
            f"{artifact.name} carries no 'quarter' column, so the declared "
            f"window {window.start_quarter}–{window.end_quarter} cannot be read",
            artifact=artifact,
            rows=rows,
        )
    quarters = table.column("quarter").to_pylist()
    in_window = [
        index
        for index, quarter in enumerate(quarters)
        if quarter is not None
        and window.start_quarter <= str(quarter) <= window.end_quarter
    ]
    if not in_window:
        return _observation(
            registration,
            ObservationStatus.WINDOW_EMPTY,
            f"no rows in the declared window {window.start_quarter}–"
            f"{window.end_quarter} ({rows} rows outside it)",
            artifact=artifact,
            rows=rows,
            window_rows=0,
        )
    window_rows = len(in_window)
    axes: list[tuple[list[object], frozenset[str]]] = []
    for axis_column, declared in _selector_columns(spec):
        if axis_column not in columns:
            return _observation(
                registration,
                ObservationStatus.SELECTOR_UNMATCHED,
                f"declares a '{axis_column}' selector but {artifact.name} has no "
                f"'{axis_column}' column",
                artifact=artifact,
                rows=rows,
                window_rows=window_rows,
            )
        axis_values = table.column(axis_column).to_pylist()
        observed = {str(axis_values[index]) for index in in_window}
        missing = [value for value in declared if value not in observed]
        if missing:
            return _observation(
                registration,
                ObservationStatus.SELECTOR_UNMATCHED,
                f"declared {axis_column} values {missing} have no rows in the "
                f"declared window",
                artifact=artifact,
                rows=rows,
                window_rows=window_rows,
            )
        axes.append((axis_values, frozenset(declared)))
    # Every declared selector is applied to the row set before a single value
    # is read -- a one-axis metric exactly as a joint one. A row whose axis
    # value the spec does not declare is not an observation of this metric,
    # so letting it through would let an out-of-scope row change how the
    # declared rows are classified (an unselected region's 999.0, or its
    # null, is not part of the declared window).
    selected = [
        index
        for index in in_window
        if all(str(axis_values[index]) in allowed for axis_values, allowed in axes)
    ]
    raw = table.column(spec.column).to_pylist()
    values = [raw[index] for index in selected]
    column_type = table.schema.field(spec.column).type
    if spec.unit in CATEGORICAL_UNITS:
        # A metric that declares a label unit (e.g. M9's binding-constraint
        # column) carries categories, not quantities: coercing a category with
        # ``float`` would crash or invent a number, so its values are observed
        # as the labels they are.
        return _observe_categorical(
            registration,
            artifact=artifact,
            values=values,
            rows=rows,
            window_rows=window_rows,
        )
    if not (pa.types.is_integer(column_type) or pa.types.is_floating(column_type)):
        # The metric declares a physical, monetary or count unit, so its
        # column must carry quantities. A column that holds non-quantitative
        # values is not this metric's data: reading it as a category would
        # report an unmeasured quantity as an observable one. A column that
        # holds no value at all (every entry null) carries no category either,
        # so it falls through to the missing-data classification below and is
        # reported as NULL_VALUES, never as a mismatch or a zero.
        if not all(_is_missing_value(value) for value in values):
            return _observation(
                registration,
                ObservationStatus.DATATYPE_MISMATCH,
                f"metric declares the numeric unit '{spec.unit}' but column "
                f"'{spec.column}' is {column_type}: a declared quantity is not "
                "a category",
                artifact=artifact,
                rows=rows,
                window_rows=window_rows,
            )
    finite: list[float] = []
    missing = 0
    nonfinite = 0
    for value in values:
        if _is_missing_value(value):
            missing += 1
            continue
        number = float(value)
        if _is_nonfinite_value(number):
            nonfinite += 1
            continue
        finite.append(number)
    abort = spec.missing_policy == MissingPolicy.ABORT
    if missing == len(values):
        return _observation(
            registration,
            ObservationStatus.NULL_VALUES,
            f"all {len(values)} values in the declared window are null or NaN: "
            "a placeholder is not a measurement",
            artifact=artifact,
            rows=rows,
            window_rows=window_rows,
        )
    if missing and abort:
        # The metric's own missing_policy applies to the declared window: an
        # ``abort`` metric whose window is null in even one row is not
        # measured there, however many values its column carries elsewhere.
        return _observation(
            registration,
            ObservationStatus.NULL_VALUES,
            f"{missing} of {len(values)} values in the declared window are null "
            f"or NaN and the metric declares missing_policy="
            f"{spec.missing_policy.value}, so the value it would rest on is not "
            "measured",
            artifact=artifact,
            rows=rows,
            window_rows=window_rows,
        )
    if nonfinite:
        return _observation(
            registration,
            ObservationStatus.NONFINITE_VALUES,
            f"{nonfinite} of {len(values)} values in the declared window are "
            "non-finite",
            artifact=artifact,
            rows=rows,
            window_rows=window_rows,
        )
    distinct = tuple(sorted(set(finite))[:_MAX_REPORTED_VALUES])
    if all(value == 0.0 for value in finite):
        return _observation(
            registration,
            ObservationStatus.OBSERVABLE_ZERO,
            f"{len(finite)} finite values in the declared window, every one of "
            f"them exactly 0 ({missing} missing)",
            artifact=artifact,
            rows=rows,
            window_rows=window_rows,
            values=(0.0,),
        )
    return _observation(
        registration,
        ObservationStatus.OBSERVABLE,
        f"{len(finite)} finite values in the declared window "
        f"({len(distinct)} distinct, {missing} missing)",
        artifact=artifact,
        rows=rows,
        window_rows=window_rows,
        values=distinct,
    )


def _observe_categorical(
    registration: RegisteredMetric,
    *,
    artifact: Path,
    values: list[object],
    rows: int,
    window_rows: int,
) -> MetricObservation:
    """Observe a label metric's values in the declared window, without coercion.

    A metric that declares a label unit is measurable as its distinct labels;
    it is never a quantity, so it is never coerced to ``float`` and never
    reported as zero. The metric's ``missing_policy`` still applies: under
    ``abort`` a null label in the declared window means the metric is not
    measured there.
    """
    labels = [str(value) for value in values if value is not None]
    missing = len(values) - len(labels)
    if not labels:
        return _observation(
            registration,
            ObservationStatus.NULL_VALUES,
            f"all {len(values)} labels in the declared window are null: a "
            "placeholder is not a measurement",
            artifact=artifact,
            rows=rows,
            window_rows=window_rows,
        )
    if missing and registration.spec.missing_policy == MissingPolicy.ABORT:
        return _observation(
            registration,
            ObservationStatus.NULL_VALUES,
            f"{missing} of {len(values)} labels in the declared window are null "
            f"and the metric declares missing_policy="
            f"{registration.spec.missing_policy.value}",
            artifact=artifact,
            rows=rows,
            window_rows=window_rows,
        )
    distinct = tuple(sorted(set(labels))[:_MAX_REPORTED_VALUES])
    return _observation(
        registration,
        ObservationStatus.OBSERVABLE,
        f"{len(labels)} categorical value(s) in the declared window "
        f"({len(distinct)} distinct, {missing} missing)",
        artifact=artifact,
        rows=rows,
        window_rows=window_rows,
        labels=distinct,
    )


def _observe_sidecar(
    registration: RegisteredMetric,
    artifact: Path,
) -> MetricObservation:
    spec = registration.spec
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return _observation(
            registration,
            ObservationStatus.ARTIFACT_ABSENT,
            f"sidecar {artifact.name} is unreadable: {error}",
            artifact=artifact,
        )
    if not isinstance(payload, dict):
        return _observation(
            registration,
            ObservationStatus.COLUMN_ABSENT,
            f"sidecar {artifact.name} is not a key/value object",
            artifact=artifact,
        )
    if spec.column not in payload:
        return _observation(
            registration,
            ObservationStatus.COLUMN_ABSENT,
            f"sidecar {artifact.name} has no '{spec.column}' key",
            artifact=artifact,
            rows=len(payload),
        )
    value = payload[spec.column]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return _observation(
            registration,
            ObservationStatus.NULL_VALUES,
            f"sidecar key '{spec.column}' is not a number",
            artifact=artifact,
            rows=len(payload),
        )
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        return _observation(
            registration,
            ObservationStatus.NONFINITE_VALUES,
            f"sidecar key '{spec.column}' is null or non-finite",
            artifact=artifact,
            rows=len(payload),
        )
    if number == 0.0:
        return _observation(
            registration,
            ObservationStatus.OBSERVABLE_ZERO,
            f"sidecar key '{spec.column}' is exactly 0 (a sidecar carries no "
            "window, so the declared window is not applied)",
            artifact=artifact,
            rows=len(payload),
            values=(0.0,),
        )
    return _observation(
        registration,
        ObservationStatus.OBSERVABLE,
        f"sidecar key '{spec.column}' = {number!r}",
        artifact=artifact,
        rows=len(payload),
        values=(number,),
    )


def observe_metric(
    run_dir: Path,
    registration: RegisteredMetric,
) -> MetricObservation:
    """Report whether one registered metric is readable from one run.

    A blocked registration reports its blocking status; a mapped registration
    is looked up in the run tree and reported with a distinct status per
    failure mode. Nothing is ever filled with 0 on a miss.
    """
    if registration.is_blocked:
        blocked = get_blocked_metric(
            registration.mechanism_id, registration.exact_original_metric
        )
        declared = None if blocked is None else blocked.declared_artifact
        if declared is not None and is_optional_sidecar(declared):
            return _observation(
                registration,
                ObservationStatus.SIDECAR_ABSENT,
                f"the card names sidecar '{declared}', which no F2 run writes",
            )
        return _observation(
            registration,
            ObservationStatus.SEMANTICS_BLOCKED,
            registration.blocked_reason or "no model counterpart",
        )
    artifact = resolve_run_artifact(run_dir, registration.spec.table_or_sidecar)
    if artifact is None:
        return _observation(
            registration,
            ObservationStatus.ARTIFACT_ABSENT,
            f"run {run_dir} holds no table or sidecar named "
            f"'{registration.spec.table_or_sidecar}'",
        )
    if artifact.suffix == ".parquet":
        return _observe_parquet(registration, artifact)
    return _observe_sidecar(registration, artifact)


def observe_registry(
    run_dir: Path,
    registry: LegacySemanticRegistry,
) -> tuple[MetricObservation, ...]:
    """Observe every registered metric against one run output tree."""
    return tuple(
        observe_metric(run_dir, registration)
        for registration in registry.registrations
    )


def observation_counts(
    observations: tuple[MetricObservation, ...],
) -> dict[str, int]:
    """Count observations per status, including every status present."""
    counts: dict[str, int] = {}
    for observation in observations:
        counts[str(observation.status)] = counts.get(str(observation.status), 0) + 1
    return dict(sorted(counts.items()))
