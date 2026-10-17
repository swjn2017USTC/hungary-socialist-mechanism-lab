"""P07A1 §4: evidence manifest loader.

Loads and validates evidence manifests and records. This module does NOT
read historical target values, does NOT modify the production engine, and
does NOT access the 1986Q1–1988Q4 reserved window.

Two manifest formats are distinguished:
- EvidenceManifest / EvidenceRecord: hypothesis/metric_specs form (experiment evidence)
- StudyManifest / StudyDeclaration: intent/linked_cards form (research intent record)

The dispatch is based on the presence of the ``intent`` field in the first
record: ``intent`` => StudyManifest, ``hypothesis`` => EvidenceManifest.
Records that mix both fields, or have neither, are rejected as ambiguous.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from hsm_lab.contract.guards import sha256_file
from hsm_lab.contract.schemas import Quarter
from hsm_lab.evidence.metric_enricher import metric_table_units
from hsm_lab.evidence.provenance import (
    _TRAJECTORY_TABLES_DIRNAME,
    _resolve_output_dir,
    verify_run_identity,
)
from hsm_lab.evidence.schemas import (
    DataRole,
    EvidenceManifest,
    EvidenceRecord,
    EvidenceStatus,
    FidelityLevel,
    MetricSpec,
    MissingPolicy,
    StudyDeclaration,
    StudyManifest,
    TimeWindow,
    ValidationFidelity,
    canonical_mechanism_id,
)
from hsm_lab.evidence.table_registry import F2_REGION_IDS
from hsm_lab.provenance.manifest import MANIFEST_FILENAME

# Card locations on disk. v1 cards use study-form file names (``M1.json`` …
# ``M11.json``, no zero padding) under ``config/p06/cards``; v2 superseding
# cards, when a mechanism has one, live under ``config/mechanisms/v2``.
_V1_CARD_DIR = Path("config") / "p06" / "cards"
_V2_CARD_DIR = Path("config") / "mechanisms" / "v2"

# Study declarations live next to the manifest: ``studies/<two-digit study
# id>/study_decl.json`` (``studies/M01/study_decl.json`` …). The sidecar is the
# declaration's own card-SHA binding, so it must be read and cross-verified
# rather than trusted from the manifest alone.
_STUDIES_DIR = Path("studies")
_SIDECAR_FILENAME = "study_decl.json"

# The v1-card SHA index used to build supersedes edges in the provenance DAG.
# It names one v1 card SHA per mechanism, so it is a sidecar SHA claim that must
# be checked against the actual card bytes rather than trusted.
_SUPERSEDES_FILENAME = "supersedes.json"

_CARD_ID_PATTERN = re.compile(r"^[Mm]0?([1-9]|1[01])$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """``object_pairs_hook`` that refuses duplicate JSON keys.

    ``json.loads`` silently keeps the last value of a duplicated key, which
    would let a sidecar shadow the identity fields read here.
    """
    seen: dict[str, object] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate JSON key {key!r}")
        seen[key] = value
    return seen


def _load_json_object(path: Path, *, label: str) -> dict[str, object]:
    """Strictly read a JSON object sidecar (no duplicate keys, object root).

    Raises
    ------
    ValueError
        If the file cannot be read, is not valid JSON, contains duplicate keys,
        or does not have a JSON object at its root.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"{label}: cannot read {path}: {exc}") from exc
    try:
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except ValueError as exc:
        raise ValueError(f"{label}: {path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(
            f"{label}: {path} must be a JSON object, got {type(payload).__name__}"
        )
    return payload


def _card_filename(mechanism_id: str) -> str:
    """Map a mechanism id (``M1``…``M11`` or ``M01``…``M11``) to its card file name.

    Card files are named in study form without zero padding (``M1.json`` …),
    so both ``M1`` and ``M01`` resolve to ``M1.json``.
    """
    match = _CARD_ID_PATTERN.match(mechanism_id.strip())
    if match is None:
        raise ValueError(f"invalid mechanism_id: {mechanism_id!r}")
    return f"M{int(match.group(1))}.json"


def _verify_record_cards(root: Path, record: EvidenceRecord) -> None:
    """Verify an EvidenceRecord's declared card SHAs against the cards on disk.

    Checks ``record.v1_card_sha256`` against
    ``config/p06/cards/<mechanism>.json`` and, when a superseding v2 card hash
    is declared, ``record.supersedes_card_sha256`` against
    ``config/mechanisms/v2/<mechanism>.json``.

    Raises
    ------
    ValueError
        If a declared card is missing or its computed SHA-256 does not match
        the hash declared in the record.
    """
    v1_path = root / _V1_CARD_DIR / _card_filename(record.mechanism_id)
    if not v1_path.is_file():
        raise ValueError(
            f"EvidenceRecord {record.record_id}: v1 card not found at {v1_path}"
        )
    actual_v1_sha = sha256_file(v1_path)
    if actual_v1_sha != record.v1_card_sha256:
        raise ValueError(
            f"EvidenceRecord {record.record_id}: v1_card_sha256 mismatch for "
            f"{record.mechanism_id} — card={actual_v1_sha[:16]}... "
            f"record={record.v1_card_sha256[:16]}..."
        )

    if record.supersedes_card_sha256 is not None:
        v2_path = root / _V2_CARD_DIR / _card_filename(record.mechanism_id)
        if not v2_path.is_file():
            raise ValueError(
                f"EvidenceRecord {record.record_id}: supersedes_card_sha256 is "
                f"declared but the v2 card is missing at {v2_path}"
            )
        actual_v2_sha = sha256_file(v2_path)
        if actual_v2_sha != record.supersedes_card_sha256:
            raise ValueError(
                f"EvidenceRecord {record.record_id}: supersedes_card_sha256 "
                f"mismatch for {record.mechanism_id} — card={actual_v2_sha[:16]}... "
                f"record={record.supersedes_card_sha256[:16]}..."
            )


def _sidecar_path(root: Path, mechanism_id: str) -> Path:
    """Resolve ``studies/<two-digit study id>/study_decl.json`` for a declaration.

    The study directory key is the canonical (zero-padded) mechanism id, so
    ``M1`` and ``M01`` both resolve to ``studies/M01/study_decl.json``.
    """
    try:
        study_key = canonical_mechanism_id(mechanism_id)
    except ValueError as exc:
        raise ValueError(
            f"invalid mechanism_id in study declaration: {mechanism_id!r}"
        ) from exc
    return root / _STUDIES_DIR / study_key / _SIDECAR_FILENAME


def _read_study_sidecar(root: Path, record: StudyDeclaration) -> dict[str, object]:
    """Read a StudyDeclaration's ``study_decl.json`` sidecar.

    Raises
    ------
    ValueError
        If the sidecar is missing, is not valid JSON, is not a JSON object, or
        does not declare the keys this verification depends on: the identity
        (``mechanism_id``) and card binding (``v1_card_sha256``) plus the
        declaration content cross-checked against the manifest record
        (``intent``, ``status``, ``linked_cards``). Missing keys are errors —
        never skipped.
    """
    path = _sidecar_path(root, record.mechanism_id)
    if not path.is_file():
        raise ValueError(
            f"StudyDeclaration {record.record_id}: study sidecar not found at {path}"
        )
    payload = _load_json_object(
        path, label=f"StudyDeclaration {record.record_id}: study sidecar"
    )
    for key in ("mechanism_id", "v1_card_sha256", "intent", "status", "linked_cards"):
        if key not in payload:
            raise ValueError(
                f"StudyDeclaration {record.record_id}: sidecar {path} is missing "
                f"required key {key!r}"
            )
    return payload


def _verify_sidecar_content(
    payload: dict[str, object],
    record: StudyDeclaration,
    *,
    manifest_phase: str | None,
) -> None:
    """Verify a sidecar's declared content against its manifest record.

    The sidecar is the declaration's own file on disk; the manifest record is a
    separate copy of the same declaration. Reading only the sidecar's identity
    and card SHA would let a sidecar that describes a *different* declaration
    (different intent, status, linked cards or phase) pass verification, so the
    declaration content itself is cross-checked here. ``linked_cards`` is
    compared on canonical M01 form (``M1``/``M01`` agree); ``phase`` is compared
    when the sidecar declares one, against the record's own phase or, when the
    record declares none, the containing manifest's phase.

    Raises
    ------
    ValueError
        If any of the compared sidecar fields is malformed or differs from the
        declaration.
    """
    sidecar_intent = payload["intent"]
    if not isinstance(sidecar_intent, str) or not sidecar_intent:
        raise ValueError(
            f"StudyDeclaration {record.record_id}: sidecar intent must be a "
            f"non-empty string, got {sidecar_intent!r}"
        )
    if sidecar_intent != record.intent:
        raise ValueError(
            f"StudyDeclaration {record.record_id}: sidecar intent mismatch — "
            f"sidecar={sidecar_intent!r}, declaration={record.intent!r}"
        )

    sidecar_status = payload["status"]
    if sidecar_status not in ("declared", "blocked"):
        raise ValueError(
            f"StudyDeclaration {record.record_id}: sidecar status must be "
            f"'declared' or 'blocked', got {sidecar_status!r}"
        )
    if sidecar_status != record.status:
        raise ValueError(
            f"StudyDeclaration {record.record_id}: sidecar status mismatch — "
            f"sidecar={sidecar_status!r}, declaration={record.status!r}"
        )

    sidecar_cards = payload["linked_cards"]
    if (
        not isinstance(sidecar_cards, list)
        or not sidecar_cards
        or not all(isinstance(card, str) for card in sidecar_cards)
    ):
        raise ValueError(
            f"StudyDeclaration {record.record_id}: sidecar linked_cards must be a "
            f"non-empty list of mechanism id strings, got {sidecar_cards!r}"
        )
    try:
        sidecar_canonical_cards = [canonical_mechanism_id(card) for card in sidecar_cards]
    except ValueError as exc:
        raise ValueError(
            f"StudyDeclaration {record.record_id}: sidecar linked_cards "
            f"{sidecar_cards!r} contains an invalid mechanism id: {exc}"
        ) from exc
    declared_canonical_cards = [
        canonical_mechanism_id(card) for card in record.linked_cards
    ]
    if sidecar_canonical_cards != declared_canonical_cards:
        raise ValueError(
            f"StudyDeclaration {record.record_id}: sidecar linked_cards mismatch — "
            f"sidecar={sidecar_cards!r} ({sidecar_canonical_cards}), "
            f"declaration={record.linked_cards!r} ({declared_canonical_cards})"
        )

    sidecar_phase = payload.get("phase")
    if sidecar_phase is not None:
        if not isinstance(sidecar_phase, str) or not sidecar_phase:
            raise ValueError(
                f"StudyDeclaration {record.record_id}: sidecar phase must be a "
                f"non-empty string, got {sidecar_phase!r}"
            )
        declared_phase = record.phase if record.phase is not None else manifest_phase
        if declared_phase is not None and sidecar_phase != declared_phase:
            raise ValueError(
                f"StudyDeclaration {record.record_id}: sidecar phase mismatch — "
                f"sidecar={sidecar_phase!r}, declaration={declared_phase!r}"
            )


def _verify_study_sidecar(
    root: Path,
    record: StudyDeclaration,
    *,
    manifest_phase: str | None = None,
) -> None:
    """Cross-verify one StudyDeclaration against its own ``study_decl.json`` sidecar.

    The manifest record and the sidecar are two separate artefacts of the same
    declaration; neither may be trusted on its own:

    * the sidecar's ``mechanism_id`` must name the same mechanism as the
      declaration (compared on canonical M01 form, so ``M1``/``M01`` agree),
    * its ``intent``, ``status`` and ``linked_cards`` must equal the
      declaration's (``linked_cards`` compared on canonical form, and
      ``phase`` compared when the sidecar declares one — falling back to the
      containing manifest's phase when the record declares none), so a sidecar
      left over from a different declaration cannot pass as this one's, and
    * the sidecar's ``v1_card_sha256`` must equal the SHA-256 of the actual card
      bytes on disk, which is what binds the declaration to real card content.

    A record that also declares ``v1_card_sha256`` is bound to the same card
    bytes by :func:`_verify_study_record_cards`, so the two can never disagree
    without one of those two checks firing first.

    Raises
    ------
    ValueError
        If the sidecar is missing/unreadable, its mechanism identity or
        declaration content (intent/status/linked_cards/phase) differs, or a
        declared card SHA is malformed, zero, or does not match the card.
    """
    payload = _read_study_sidecar(root, record)

    sidecar_mechanism_id = payload["mechanism_id"]
    if not isinstance(sidecar_mechanism_id, str) or not sidecar_mechanism_id:
        raise ValueError(
            f"StudyDeclaration {record.record_id}: sidecar mechanism_id must be a "
            f"non-empty string, got {sidecar_mechanism_id!r}"
        )
    try:
        sidecar_canonical = canonical_mechanism_id(sidecar_mechanism_id)
    except ValueError as exc:
        raise ValueError(
            f"StudyDeclaration {record.record_id}: sidecar mechanism_id "
            f"{sidecar_mechanism_id!r} is not a valid mechanism id: {exc}"
        ) from exc
    if sidecar_canonical != canonical_mechanism_id(record.mechanism_id):
        raise ValueError(
            f"StudyDeclaration {record.record_id}: sidecar mechanism_id mismatch — "
            f"sidecar={sidecar_mechanism_id!r} ({sidecar_canonical}), "
            f"declaration={record.mechanism_id!r} "
            f"({canonical_mechanism_id(record.mechanism_id)})"
        )

    _verify_sidecar_content(payload, record, manifest_phase=manifest_phase)

    sidecar_sha = payload["v1_card_sha256"]
    if not isinstance(sidecar_sha, str) or not _SHA256_PATTERN.match(sidecar_sha):
        raise ValueError(
            f"StudyDeclaration {record.record_id}: sidecar v1_card_sha256 must be "
            f"64 lowercase hex characters, got {sidecar_sha!r}"
        )
    if sidecar_sha == "0" * 64:
        raise ValueError(
            f"StudyDeclaration {record.record_id}: sidecar v1_card_sha256 is all "
            "zeros; the declaration is not card-bound"
        )

    v1_path = root / _V1_CARD_DIR / _card_filename(sidecar_canonical)
    if not v1_path.is_file():
        raise ValueError(
            f"StudyDeclaration {record.record_id}: v1 card not found for "
            f"{sidecar_canonical} at {v1_path} (declared by sidecar)"
        )
    actual_sha = sha256_file(v1_path)
    if actual_sha != sidecar_sha:
        raise ValueError(
            f"StudyDeclaration {record.record_id}: sidecar v1_card_sha256 mismatch "
            f"for {sidecar_canonical} — card={actual_sha[:16]}... "
            f"sidecar={sidecar_sha[:16]}..."
        )


def _verify_supersedes_index(root: Path, record: StudyDeclaration) -> None:
    """Cross-verify the v1-card SHA index against the card bytes on disk.

    ``config/mechanisms/v2/supersedes.json`` is a second sidecar SHA claim — the
    one the provenance DAG reads to link v1 cards to superseding v2 cards. Its
    entry for the declaration's mechanism must exist and must equal the SHA-256
    of the actual v1 card bytes, otherwise a supersedes edge would be built on
    an unverified hash.

    Raises
    ------
    ValueError
        If the index is missing/unreadable, has no entry for the mechanism, or
        its entry is malformed, zero, or does not match the card on disk.
    """
    index_path = root / _V2_CARD_DIR / _SUPERSEDES_FILENAME
    if not index_path.is_file():
        raise ValueError(
            f"StudyDeclaration {record.record_id}: v1 card SHA index not found at "
            f"{index_path}"
        )
    label = f"StudyDeclaration {record.record_id}: v1 card SHA index"
    index = _load_json_object(index_path, label=label)

    canonical = canonical_mechanism_id(record.mechanism_id)
    key = _card_filename(canonical).removesuffix(".json")
    if key not in index:
        raise ValueError(
            f"StudyDeclaration {record.record_id}: v1 card SHA index {index_path} "
            f"has no entry for {key!r}"
        )
    declared_sha = index[key]
    if not isinstance(declared_sha, str) or not _SHA256_PATTERN.match(declared_sha):
        raise ValueError(
            f"StudyDeclaration {record.record_id}: v1 card SHA index {index_path} "
            f"entry {key!r} must be 64 lowercase hex characters, got {declared_sha!r}"
        )
    if declared_sha == "0" * 64:
        raise ValueError(
            f"StudyDeclaration {record.record_id}: v1 card SHA index {index_path} "
            f"entry {key!r} is all zeros; it does not bind a card"
        )

    v1_path = root / _V1_CARD_DIR / _card_filename(canonical)
    if not v1_path.is_file():
        raise ValueError(
            f"StudyDeclaration {record.record_id}: v1 card not found for "
            f"{canonical} at {v1_path} (declared by the v1 card SHA index)"
        )
    actual_sha = sha256_file(v1_path)
    if actual_sha != declared_sha:
        raise ValueError(
            f"StudyDeclaration {record.record_id}: v1 card SHA index mismatch for "
            f"{canonical} — card={actual_sha[:16]}... "
            f"index={declared_sha[:16]}..."
        )


def verify_study_manifest_cards(
    root: Path,
    manifest: StudyManifest,
) -> None:
    """Verify every declared card of a StudyManifest against the cards on disk.

    For each record, every mechanism id it declares (its own ``mechanism_id``
    and each entry of ``linked_cards``) must resolve to an existing card file
    under ``config/p06/cards``. When the record declares ``v1_card_sha256``,
    the card's computed SHA-256 must equal it — the same binding
    :func:`_verify_record_cards` applies to SUPPORTED EvidenceRecords.

    Each record is additionally cross-verified against its own sidecar,
    ``studies/<two-digit study id>/study_decl.json`` (:func:`_verify_study_sidecar`):
    the sidecar must exist, must name the same mechanism, its
    ``intent``/``status``/``linked_cards``/``phase`` must match the record's,
    and its ``v1_card_sha256`` must equal the SHA-256 of the actual card bytes.
    The sidecar — not the manifest — is what card-binds the real declarations. The
    ``config/mechanisms/v2/supersedes.json`` v1-card SHA index that feeds the
    DAG's supersedes edges is cross-verified against the same card bytes
    (:func:`_verify_supersedes_index`).

    Parameters
    ----------
    root
        Repository root containing ``config/p06/cards``, ``config/mechanisms/v2``
        and ``studies``.
    manifest
        Validated StudyManifest whose records are checked.

    Raises
    ------
    ValueError
        If a declared card is missing or its computed SHA-256 does not match
        the hash declared in the record, or if a record's sidecar or the v1-card
        SHA index is missing/unreadable, names a different mechanism, or
        declares a card SHA that does not match the card on disk.
    """
    for record in manifest.records:
        _verify_study_record_cards(root, record, manifest_phase=manifest.phase)


def _verify_study_record_cards(
    root: Path,
    record: StudyDeclaration,
    *,
    manifest_phase: str | None = None,
) -> None:
    """Verify one StudyDeclaration's declared cards and sidecars against disk.

    Raises
    ------
    ValueError
        If a declared card is missing or its computed SHA-256 does not match
        the hash declared in the record, or if the record's sidecar (see
        :func:`_verify_study_sidecar`, which cross-checks the sidecar's
        ``intent``/``status``/``linked_cards``/``phase`` against the record) or
        the v1-card SHA index (see :func:`_verify_supersedes_index`) fails
        cross-verification.
    """
    # mechanism_id and every linked card must name the same mechanism (enforced
    # by the schema), so dedupe on the resolved file name.
    checked: set[str] = set()
    for mechanism_id in (record.mechanism_id, *record.linked_cards):
        filename = _card_filename(mechanism_id)
        if filename in checked:
            continue
        checked.add(filename)
        v1_path = root / _V1_CARD_DIR / filename
        if not v1_path.is_file():
            raise ValueError(
                f"StudyDeclaration {record.record_id}: v1 card not found for "
                f"{mechanism_id} at {v1_path}"
            )
        if record.v1_card_sha256 is None:
            continue
        actual_v1_sha = sha256_file(v1_path)
        if actual_v1_sha != record.v1_card_sha256:
            raise ValueError(
                f"StudyDeclaration {record.record_id}: v1_card_sha256 mismatch "
                f"for {mechanism_id} — card={actual_v1_sha[:16]}... "
                f"record={record.v1_card_sha256[:16]}..."
            )

    # The sidecar is the declaration's own card-SHA binding and must be read
    # and cross-verified, not taken on trust from the manifest record. The
    # v1-card SHA index is the second sidecar SHA claim (it feeds the DAG's
    # supersedes edges), and is cross-verified against the same card bytes.
    _verify_study_sidecar(root, record, manifest_phase=manifest_phase)
    _verify_supersedes_index(root, record)


def _verify_supported_metric_fidelity(record: EvidenceRecord) -> None:
    """Reject a SUPPORTED record whose metrics have no model counterpart.

    ``ValidationFidelity.NO_COUNTERPART`` means the metric has no counterpart in
    the model at any fidelity, so no run can produce a column to validate it
    against. A record that rests on such a metric therefore cannot be validated
    and must not be published as SUPPORTED.

    Raises
    ------
    ValueError
        If any metric spec of the record declares ``no_counterpart`` fidelity.
        The message lists every offending metric id.
    """
    offenders = sorted(
        spec.metric_id
        for spec in record.metric_specs
        if spec.validation_fidelity == ValidationFidelity.NO_COUNTERPART
    )
    if offenders:
        raise ValueError(
            f"EvidenceRecord {record.record_id}: status=SUPPORTED but "
            f"metric_specs with validation_fidelity="
            f"{ValidationFidelity.NO_COUNTERPART.value} cannot be validated by "
            f"any run: {offenders}"
        )


# ---------------------------------------------------------------------------
# SUPPORTED metric content binding (H0A P0-2)
# ---------------------------------------------------------------------------

# A MetricSpec's ``table_or_sidecar`` names an artefact inside the run output:
# the run's compact Parquet table (at the run root or under
# ``trajectory_tables/``), a file with that exact name, or a JSON sidecar of
# that name.

# The metric enricher's alias for "every region in the F2 registry".
_ALL_REGIONS_ALIAS = "all_20_regions"

# A TARGET or CANDIDATE_LINKAGE metric must carry actual data: a table column
# that is entirely null (or NaN) is a placeholder, not a measurement, so it
# cannot support a SUPPORTED record.
_DATA_ROLES_REQUIRING_DATA = (DataRole.TARGET, DataRole.CANDIDATE_LINKAGE)

# The model layer a run's manifest declares, and the metric fidelities that
# layer can produce. An F2 run's tables are F2 output, so a metric declared at
# F1_intermediate_8 cannot have been measured in it (and an F1 run cannot
# produce an F2 quantity); a synthetic/analytical probe is not a run layer at
# all, so no run can support it.
_RUN_LAYER_METRIC_FIDELITIES: dict[str, frozenset[FidelityLevel]] = {
    "f1": frozenset({FidelityLevel.F1_INTERMEDIATE}),
    "f2": frozenset({FidelityLevel.F2_RUN, FidelityLevel.F2_DIAGNOSTIC}),
}


def _is_missing_value(value: object) -> bool:
    """True for a null/NaN cell — empty data rather than a measurement."""
    if value is None:
        return True
    return isinstance(value, float) and math.isnan(value)


# Declared categorical units.  Everything else is a quantitative measurement:
# physical, monetary, count or probability quantities must carry numbers, and
# an arbitrary string cannot become an observable value.
_CATEGORICAL_UNITS = frozenset({"binding_constraint_label"})

# JSON sidecars must declare a typed binding for every metric they supply.
_SIDECAR_BINDINGS_KEY = "__metric_bindings__"
_SIDECAR_BINDING_KEYS = frozenset({
    "unit", "value_type", "temporal", "selectors",
})


def _is_numeric_measurement(value: object) -> bool:
    """True for an exact int/float measurement (booleans excluded)."""
    actual = type(value)
    return actual is int or actual is float


def _is_nonfinite_value(value: object) -> bool:
    """True for an infinite cell — nonsense rather than a measurement.

    ``inf``/``-inf`` propagate through every aggregation, so a column that
    holds one does not carry usable data even though it is not null.
    """
    return (
        isinstance(value, float)
        and not math.isnan(value)
        and not math.isfinite(value)
    )


def _run_has_stochastic_activity(manifest: object) -> bool:
    """Return True only for a manifest with consistent, nonzero RNG activity.

    A distinct seed or output directory is not, by itself, an independent
    stochastic replicate: a deterministic run reports zero draws and no active
    modules.  The manifest's RNG fields must also agree with each other.
    """
    count = getattr(manifest, "rng_draws_count", None)
    by_module = getattr(manifest, "rng_draws_by_module", None)
    active = getattr(manifest, "stochastic_modules_active", None)
    if type(count) is not int or count < 0:
        raise ValueError(
            "verified run manifest declares an invalid rng_draws_count"
        )
    if type(by_module) is not dict:
        raise ValueError(
            "verified run manifest declares an invalid rng_draws_by_module"
        )
    total = 0
    for key, value in by_module.items():
        if type(key) is not str or type(value) is not int or value < 0:
            raise ValueError(
                "verified run manifest declares an invalid rng module draw count"
            )
        total += value
    if total != count:
        raise ValueError(
            "verified run manifest rng_draws_by_module does not sum to "
            "rng_draws_count"
        )
    if type(active) is not list:
        raise ValueError(
            "verified run manifest declares an invalid "
            "stochastic_modules_active"
        )
    for module in active:
        if type(module) is not str:
            raise ValueError(
                "verified run manifest declares a non-string active module"
            )
    positive_modules = {
        key for key, value in by_module.items() if value > 0
    }
    if set(active) != positive_modules:
        raise ValueError(
            "verified run manifest stochastic_modules_active does not match "
            "the modules with positive rng_draws_by_module counts"
        )
    if count > 0 and not active:
        raise ValueError(
            "verified run manifest reports RNG draws but no active "
            "stochastic module"
        )
    return count > 0


def _hashed_output_paths(run_dir: Path) -> set[str]:
    """Paths covered by a verified run's own output-hash map."""
    payload = json.loads((run_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    hashes = payload.get("output_hashes")
    if not isinstance(hashes, dict):
        raise ValueError(
            f"run {run_dir} has no output_hashes to bind metric artefacts"
        )
    return {str(key) for key in hashes}


def _metric_label(record: EvidenceRecord, spec: MetricSpec) -> str:
    """The record/metric/artefact label every metric-content error carries."""
    return (
        f"EvidenceRecord {record.record_id}: metric {spec.metric_id} "
        f"(table_or_sidecar={spec.table_or_sidecar!r})"
    )


def _run_declared_layer(run_dir: Path) -> str:
    """The model layer (``"f1"``/``"f2"``) a run's own manifest declares.

    The manifest records ``fidelity`` directly, and the ontology it names
    implies the layer when the field is absent (the same rule
    ``hsm_lab.provenance.manifest.p05_manifest_fields`` applies). A run whose
    manifest declares neither cannot have its metric bindings checked, so it is
    refused rather than assumed.

    Raises
    ------
    ValueError
        If the run has no readable manifest, or its manifest declares neither a
        model fidelity nor an ontology id.
    """
    manifest_path = run_dir / MANIFEST_FILENAME
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            "verify_supported_record_runs: run "
            f"{run_dir} has no readable {MANIFEST_FILENAME} to establish the "
            f"model layer its metrics were produced at: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(
            "verify_supported_record_runs: run "
            f"{run_dir} {MANIFEST_FILENAME} is not a JSON object"
        )
    fidelity = payload.get("fidelity")
    if fidelity in _RUN_LAYER_METRIC_FIDELITIES:
        return str(fidelity)
    ontology_id = payload.get("ontology_id")
    if isinstance(ontology_id, str) and ontology_id:
        return "f2" if ontology_id.startswith("f2") else "f1"
    raise ValueError(
        "verify_supported_record_runs: run "
        f"{run_dir} declares neither a model 'fidelity' nor an 'ontology_id' "
        "in its manifest, so the layer its metrics were produced at cannot be "
        "verified"
    )


def _verify_metric_layer_binding(
    *,
    spec: MetricSpec,
    run_dir: Path,
    run_layer: str,
    label: str,
) -> None:
    """Require the metric's declared layer to be one the run produced.

    A metric's ``fidelity`` names the model layer the quantity exists at; a run
    executes exactly one layer. Declaring an F1 quantity against an F2 run (or
    an F2 quantity against an F1 run) means the run cannot have produced the
    column, however plausible its name is.

    Raises
    ------
    ValueError
        If the metric's fidelity is not a layer the run's manifest declares.
    """
    allowed = _RUN_LAYER_METRIC_FIDELITIES[run_layer]
    if spec.fidelity in allowed:
        return
    raise ValueError(
        f"{label}: metric declares fidelity={spec.fidelity.value} but run "
        f"{run_dir} is an {run_layer.upper()} run (its manifest declares "
        f"fidelity={run_layer!r}); a run at that layer cannot have produced a "
        f"{spec.fidelity.value} quantity"
    )


def _canonical_table_name(artifact: Path) -> str | None:
    """The canonical table identity a resolved artefact path carries.

    Units are declared per ``(table, column)`` pair, keyed by the *table* the
    quantity lives in (``aggregates``, ``national_accounts``) rather than by the
    spelling a record used to name it. The resolved artefact is therefore
    reduced to its file stem, so every alias that resolves to the same Parquet
    table (``national_accounts.parquet``, ``trajectory_tables/national_accounts``)
    binds to the same declared units and cannot dodge the unit gate by spelling.
    A JSON sidecar is not a model table, so it has no canonical table identity.
    """
    if artifact.suffix != ".parquet":
        return None
    return artifact.stem


def _verify_metric_unit_binding(
    *,
    spec: MetricSpec,
    run_dir: Path,
    artifact: Path,
    label: str,
    table_units: dict[tuple[str, str], frozenset[str]],
) -> None:
    """Require a physical-quantity metric's unit to be the table's unit.

    A physical quantity is only the quantity it claims to be at the unit the
    model declares for the ``(table, column)`` pair it is read from: the same
    column is ``M_forint`` in one table and a ``count`` in another, and a
    record declaring the wrong unit would otherwise compare unlike quantities.

    The pair is looked up by the *resolved* artefact's canonical table identity,
    not by the ``table_or_sidecar`` spelling: a record naming the very same
    table as ``national_accounts.parquet`` or
    ``trajectory_tables/national_accounts`` must bind to the units the model
    declares for ``national_accounts``, or an aliased declaration would never be
    checked at all. A JSON sidecar is not a model table and has no declared
    unit, so it is left to the content checks; a Parquet table whose column the
    model declares no unit for cannot have the declared unit established, so it
    is refused rather than trusted.

    Raises
    ------
    ValueError
        If the pair's unit is declared and the metric's unit is not it, or a
        Parquet table's column carries no declared unit to bind the metric to.
    """
    canonical_table = _canonical_table_name(artifact)
    if canonical_table is None:
        return
    declared_units = table_units.get((canonical_table, spec.column))
    if declared_units is None:
        unit_bearing_columns = sorted(
            column
            for table_name, column in table_units
            if table_name == canonical_table
        )
        raise ValueError(
            f"{label}: metric declares unit {spec.unit!r} for column "
            f"{spec.column!r} of Parquet table {canonical_table!r} in run "
            f"{run_dir}, but the model declares no unit for that column "
            f"(columns with a declared unit: {unit_bearing_columns}); the "
            "declared unit cannot be established"
        )
    if spec.unit in declared_units:
        return
    raise ValueError(
        f"{label}: metric declares unit {spec.unit!r} but "
        f"{artifact.name} in run {run_dir} carries column {spec.column!r} in "
        f"unit(s) {sorted(declared_units)}; the declared unit does not match "
        "the quantity the table holds"
    )


def _metric_artifact_path(run_dir: Path, table_or_sidecar: str) -> Path | None:
    """Locate the run artefact a MetricSpec's ``table_or_sidecar`` names.

    Candidates, in order: the compact Parquet table (``<name>.parquet`` at the
    run root or under ``trajectory_tables/``), the file ``<name>``, and the
    sidecar ``<name>.json``. Only paths inside the run directory are
    considered, so a declared sidecar cannot resolve outside the run it claims
    to have been measured in.

    Parameters
    ----------
    run_dir
        The referenced run's resolved output directory.
    table_or_sidecar
        The MetricSpec's declared table or sidecar name.

    Returns
    -------
    Path | None
        The resolved artefact path, or None when the run holds no such
        artefact.
    """
    name = table_or_sidecar.strip()
    if not name:
        return None
    try:
        run_root = run_dir.resolve()
    except OSError:
        return None
    candidates = (
        run_dir / f"{name}.parquet",
        run_dir / _TRAJECTORY_TABLES_DIRNAME / f"{name}.parquet",
        run_dir / name,
        run_dir / f"{name}.json",
    )
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if not resolved.is_relative_to(run_root):
            continue
        if resolved.is_file():
            return resolved
    return None


def _window_quarter_labels(window: TimeWindow) -> list[str]:
    """Enumerate the ``YYYYQn`` labels of a declared time window, inclusive."""
    first = Quarter.parse(window.start_quarter).to_ordinal()
    last = Quarter.parse(window.end_quarter).to_ordinal()
    return [str(Quarter.from_ordinal(ordinal)) for ordinal in range(first, last + 1)]


def _resolved_axis_values(values: list[str]) -> list[str]:
    """Expand the registry-wide region alias the metric enricher emits."""
    if list(values) == [_ALL_REGIONS_ALIAS]:
        return list(F2_REGION_IDS)
    return list(values)


def _read_column_values(artifact: Path, column: str) -> list[object]:
    """Read one column's values out of a Parquet artefact.

    ``column`` must exist in the schema (callers check that first).
    """
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    try:
        values: list[object] = pq.read_table(artifact, columns=[column]).column(
            column
        ).to_pylist()
    except Exception as exc:
        raise ValueError(
            "verify_supported_record_runs: cannot read column "
            f"{column!r} from {artifact.name}: {exc}"
        ) from exc
    return values


def _verify_metric_parquet_content(
    *,
    record: EvidenceRecord,
    run_dir: Path,
    artifact: Path,
    specs: list[MetricSpec],
) -> None:
    """Verify metrics bound to one Parquet table against that table's content.

    Raises
    ------
    ValueError
        If a declared column is absent, the table has no rows, the table has
        no ``quarter`` column, the declared time window has no rows, a
        declared commodity/region selector value is not covered, a declared
        quarter × selector combination has no rows, or a
        TARGET/CANDIDATE_LINKAGE metric carries no usable data in that
        window/selector intersection (all null/NaN there, a missing value
        under ``missing_policy=abort``, or an infinite value).
    """
    import pyarrow.parquet as pq

    try:
        parquet_file = pq.ParquetFile(artifact)
    except Exception as exc:
        raise ValueError(
            "verify_supported_record_runs: "
            f"{artifact.name} in run {run_dir} is not a readable Parquet "
            f"table: {exc}"
        ) from exc
    schema_names = set(parquet_file.schema_arrow.names)
    num_rows = parquet_file.metadata.num_rows

    for spec in specs:
        label = _metric_label(record, spec)
        if spec.column not in schema_names:
            raise ValueError(
                f"{label}: column {spec.column!r} does not exist in "
                f"{artifact.name} of run {run_dir} "
                f"(columns: {sorted(schema_names)})"
            )
        if num_rows == 0:
            raise ValueError(
                f"{label}: {artifact.name} has no rows in run {run_dir}, so "
                "the metric has no data to be supported by"
            )
        if "quarter" not in schema_names:
            raise ValueError(
                f"{label}: {artifact.name} in run {run_dir} has no 'quarter' "
                "column, so the declared time window cannot be verified"
            )
        present_quarters = {
            str(quarter)
            for quarter in _read_column_values(artifact, "quarter")
            if quarter is not None
        }
        missing_quarters = [
            quarter
            for quarter in _window_quarter_labels(spec.time_window)
            if quarter not in present_quarters
        ]
        if missing_quarters:
            raise ValueError(
                f"{label}: run {run_dir} has no rows for the declared time "
                f"window {spec.time_window.start_quarter}.."
                f"{spec.time_window.end_quarter} (missing e.g. "
                f"{missing_quarters[:5]}); the metric is not measured over its "
                f"declared window (missing_policy="
                f"{spec.missing_policy.value})"
            )

        axis_selectors = (
            (
                "commodity_id",
                "commodity",
                spec.commodity_axis.commodities if spec.commodity_axis else None,
            ),
            (
                "region_id",
                "region",
                spec.region_axis.regions if spec.region_axis else None,
            ),
        )
        declared_commodities: list[str] | None = None
        declared_regions: list[str] | None = None
        for axis_column, axis_kind, declared_values in axis_selectors:
            if declared_values is None:
                continue
            declared = _resolved_axis_values(declared_values)
            if axis_column not in schema_names:
                raise ValueError(
                    f"{label}: declares a {axis_kind} selector but "
                    f"{artifact.name} in run {run_dir} has no "
                    f"{axis_column!r} column"
                )
            present_values = {
                value
                for value in _read_column_values(artifact, axis_column)
                if value is not None
            }
            missing_values = [
                value for value in declared if value not in present_values
            ]
            if missing_values:
                raise ValueError(
                    f"{label}: declared {axis_kind}(s) "
                    f"{missing_values[:5]} are absent from {artifact.name} in "
                    f"run {run_dir}; the declared selector is not covered"
                )
            if axis_column == "commodity_id":
                declared_commodities = declared
            else:
                declared_regions = declared

        # Covering the window and covering each selector separately is not
        # covering their intersection: a table can carry every declared quarter
        # and every declared commodity while never carrying, say,
        # ``g09_basic_food`` in ``1957Q1``. The metric is only measured over the
        # declared window if every declared quarter has rows for every declared
        # commodity/region combination.
        _verify_joint_coverage(
            label=label,
            run_dir=run_dir,
            artifact=artifact,
            window=spec.time_window,
            declared_commodities=declared_commodities,
            declared_regions=declared_regions,
        )

        # The metric is measured over the intersection just verified, so that
        # intersection — not the whole column — is what must carry data: a
        # column that is null throughout the declared window while other
        # quarters or selectors hold values supports nothing.
        # Data semantics do not depend on the role label: changing a metric
        # from TARGET to FORCING must not bypass missing/nonfinite/datatype
        # checks.  The metric's own missing_policy governs tolerance.
        _verify_metric_window_data(
            spec=spec,
            run_dir=run_dir,
            artifact=artifact,
            label=label,
            declared_commodities=declared_commodities,
            declared_regions=declared_regions,
        )


def _verify_joint_coverage(
    *,
    label: str,
    run_dir: Path,
    artifact: Path,
    window: TimeWindow,
    declared_commodities: list[str] | None,
    declared_regions: list[str] | None,
) -> None:
    """Require rows for every declared quarter × selector combination.

    Quarter coverage and selector coverage are checked independently above, but
    the metric is measured over the *intersection*: a table carrying every
    declared quarter and every declared commodity can still have no row for
    ``g09_basic_food`` in ``1957Q1``. With an axis declared, each of its values
    must appear in *every* declared quarter (and, when both axes are declared,
    in combination).

    Raises
    ------
    ValueError
        If any declared quarter × commodity × region combination has no row.
    """
    if declared_commodities is None and declared_regions is None:
        return

    import pyarrow.parquet as pq

    columns = ["quarter"]
    if declared_commodities is not None:
        columns.append("commodity_id")
    if declared_regions is not None:
        columns.append("region_id")
    try:
        table = pq.read_table(artifact, columns=columns)
    except Exception as exc:
        raise ValueError(
            "verify_supported_record_runs: cannot read columns "
            f"{columns} from {artifact.name}: {exc}"
        ) from exc

    present: set[tuple[str, ...]] = set()
    for row in zip(
        *(table.column(name).to_pylist() for name in columns), strict=True
    ):
        if any(value is None for value in row):
            continue
        present.add(tuple(str(value) for value in row))

    commodities: list[str | None] = (
        list(declared_commodities) if declared_commodities is not None else [None]
    )
    regions: list[str | None] = (
        list(declared_regions) if declared_regions is not None else [None]
    )
    missing: list[str] = []
    for quarter in _window_quarter_labels(window):
        for commodity in commodities:
            for region in regions:
                combination = tuple(
                    str(value)
                    for value in (quarter, commodity, region)
                    if value is not None
                )
                if combination not in present:
                    missing.append(" × ".join(combination))
                    if len(missing) >= 5:
                        break
            if len(missing) >= 5:
                break
        if len(missing) >= 5:
            break
    if missing:
        raise ValueError(
            f"{label}: run {run_dir} has no rows for the declared "
            f"quarter × selector combination(s) {missing} in {artifact.name}; "
            "every declared quarter must carry data for every declared "
            "commodity/region selector (missing_policy="
            f"{window.missing_policy.value})"
        )


def _read_window_intersection_values(
    *,
    artifact: Path,
    column: str,
    window_quarters: set[str],
    commodities: list[str] | None,
    regions: list[str] | None,
) -> list[object]:
    """Read one metric column's values over the declared window × selector rows.

    Only rows inside the declared time window — and, where an axis is
    declared, only rows carrying one of the declared commodity/region values —
    are read: those are the rows the metric is actually measured over.
    """
    import pyarrow.parquet as pq

    columns = ["quarter", column]
    if commodities is not None:
        columns.append("commodity_id")
    if regions is not None:
        columns.append("region_id")
    columns = list(dict.fromkeys(columns))
    try:
        table = pq.read_table(artifact, columns=columns)
    except Exception as exc:
        raise ValueError(
            "verify_supported_record_runs: cannot read columns "
            f"{columns} from {artifact.name}: {exc}"
        ) from exc

    commodity_set = set(commodities) if commodities is not None else None
    region_set = set(regions) if regions is not None else None
    values: list[object] = []
    for row in zip(
        *(table.column(name).to_pylist() for name in columns), strict=True
    ):
        cells = dict(zip(columns, row, strict=True))
        quarter = cells["quarter"]
        if quarter is None or str(quarter) not in window_quarters:
            continue
        if commodity_set is not None:
            commodity = cells["commodity_id"]
            if commodity is None or str(commodity) not in commodity_set:
                continue
        if region_set is not None:
            region = cells["region_id"]
            if region is None or str(region) not in region_set:
                continue
        values.append(cells[column])
    return values


def _verify_metric_window_data(
    *,
    spec: MetricSpec,
    run_dir: Path,
    artifact: Path,
    label: str,
    declared_commodities: list[str] | None,
    declared_regions: list[str] | None,
) -> None:
    """Require usable data inside the metric's declared window/selector rows.

    A TARGET/CANDIDATE_LINKAGE metric is measured over the intersection of its
    declared time window and its declared commodity/region selectors, so that
    intersection is what must carry data. Judging the column across every row
    instead lets a table pass on data the metric never covers: the declared
    window can be null throughout while other quarters — or other selectors —
    hold values, and the whole-column check sees only the latter.

    The metric's own ``missing_policy`` applies to that intersection too:
    ``abort`` refuses a null/NaN anywhere in it, while ``skip``/``interpolate``
    tolerate missing cells as long as some value survives to be used. A value
    that is infinite is never a measurement, whatever the policy.

    Raises
    ------
    ValueError
        If no value in the declared intersection is a measurement (all
        null/NaN), the declared ``missing_policy`` is ``abort`` and any value
        there is null/NaN, or a value there is infinite.
    """
    values = _read_window_intersection_values(
        artifact=artifact,
        column=spec.column,
        window_quarters=set(_window_quarter_labels(spec.time_window)),
        commodities=declared_commodities,
        regions=declared_regions,
    )
    window = (
        f"{spec.time_window.start_quarter}..{spec.time_window.end_quarter}"
    )
    if not values:
        # ``_verify_joint_coverage`` guarantees a row for every declared
        # quarter × selector, so this is defensive only.
        raise ValueError(
            f"{label}: {artifact.name} in run {run_dir} has no row carrying "
            f"column {spec.column!r} in the declared window {window} for the "
            f"declared selectors, so the metric has no data over its declared "
            f"window (missing_policy={spec.missing_policy.value})"
        )
    missing_values = [value for value in values if _is_missing_value(value)]
    if len(missing_values) == len(values):
        # "Exists in the schema" is not "has data": a column that is null (or
        # NaN) throughout the declared intersection is a placeholder for a
        # measurement, however much data it carries elsewhere.
        raise ValueError(
            f"{label}: column {spec.column!r} in {artifact.name} of run "
            f"{run_dir} has no values in the declared window {window} (all "
            f"{len(values)} row(s) there are null or NaN); a "
            f"{spec.data_role.value} metric must carry actual data"
        )
    if missing_values and spec.missing_policy == MissingPolicy.ABORT:
        raise ValueError(
            f"{label}: column {spec.column!r} in {artifact.name} of run "
            f"{run_dir} is null or NaN in {len(missing_values)} of "
            f"{len(values)} row(s) of the declared window {window}, but the "
            "metric declares missing_policy=abort, so the value it would rest "
            "on is not measured"
        )
    # Nor is a value that is not a number: ``inf``/``-inf`` propagate through
    # every aggregation, so a window holding one measures nothing. Checked per
    # value, so one infinite cell cannot ride along behind finite ones.
    nonfinite_values = [
        value for value in values if _is_nonfinite_value(value)
    ]
    if nonfinite_values:
        raise ValueError(
            f"{label}: column {spec.column!r} in {artifact.name} of run "
            f"{run_dir} carries {len(nonfinite_values)} non-finite value(s) "
            f"(inf/-inf, e.g. {nonfinite_values[0]!r}) among {len(values)} "
            f"row(s) of the declared window {window}; an infinite value is not "
            f"a measurement, so a {spec.data_role.value} metric must not rest "
            "on it"
        )
    if spec.unit in _CATEGORICAL_UNITS:
        malformed = [
            value
            for value in values
            if not _is_missing_value(value) and type(value) is not str
        ]
        if malformed:
            raise ValueError(
                f"{label}: column {spec.column!r} in {artifact.name} of run "
                f"{run_dir} declares categorical unit {spec.unit!r} but carries "
                f"{len(malformed)} non-string value(s) (e.g. "
                f"{malformed[0]!r}) among {len(values)} row(s) of the declared "
                f"window {window}"
            )
    else:
        # Physical, monetary, count and probability metrics are quantitative:
        # a string cell is not a number and cannot support the declaration.
        nonnumeric = [
            value
            for value in values
            if not _is_missing_value(value)
            and not _is_numeric_measurement(value)
        ]
        if nonnumeric:
            raise ValueError(
                f"{label}: column {spec.column!r} in {artifact.name} of run "
                f"{run_dir} declares quantitative unit {spec.unit!r} but "
                f"carries {len(nonnumeric)} non-numeric value(s) (e.g. "
                f"{nonnumeric[0]!r}) among {len(values)} row(s) of the "
                f"declared window {window}"
            )


def _verify_metric_sidecar_content(
    *,
    record: EvidenceRecord,
    run_dir: Path,
    artifact: Path,
    specs: list[MetricSpec],
) -> None:
    """Verify metrics bound to one JSON sidecar against that sidecar's content.

    Raises
    ------
    ValueError
        If the sidecar is empty, not a JSON object, or does not declare a
        finite, non-null value for a bound metric's column.
    """
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            "verify_supported_record_runs: sidecar "
            f"{artifact.name} in run {run_dir} is not readable JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict) or not payload:
        raise ValueError(
            "verify_supported_record_runs: sidecar "
            f"{artifact.name} in run {run_dir} must be a non-empty JSON object"
        )

    # A JSON sidecar must declare the semantics of every metric it supplies.
    # Without an explicit unit, value type, temporal extent and selector
    # declaration, a dictionary entry cannot be shown to be the quantity the
    # metric claims, so unknown semantics block promotion.
    bindings = payload.get(_SIDECAR_BINDINGS_KEY)
    if not isinstance(bindings, dict) or not bindings:
        first_spec = specs[0]
        raise ValueError(
            f"{_metric_label(record, first_spec)}: JSON sidecar "
            f"{artifact.name!r} in run {run_dir} has no typed "
            f"{_SIDECAR_BINDINGS_KEY!r} declaration; an unbound sidecar "
            "cannot support a SUPPORTED record"
        )
    for spec in specs:
        label = _metric_label(record, spec)
        if spec.column not in payload:
            raise ValueError(
                f"{label}: column {spec.column!r} is not declared in sidecar "
                f"{artifact.name} of run {run_dir}"
            )
        binding = bindings.get(spec.column)
        if not isinstance(binding, dict):
            raise ValueError(
                f"{label}: sidecar {artifact.name} of run {run_dir} declares "
                f"no established typed binding for column {spec.column!r}"
            )
        if set(binding) != _SIDECAR_BINDING_KEYS:
            raise ValueError(
                f"{label}: sidecar binding for {spec.column!r} must declare "
                "exactly unit, value_type, temporal and selectors"
            )
        if binding["unit"] != spec.unit:
            raise ValueError(
                f"{label}: declared unit {spec.unit!r} does not match the "
                f"sidecar binding unit {binding['unit']!r}"
            )
        temporal = binding["temporal"]
        if (
            not isinstance(temporal, dict)
            or set(temporal) != {"start_quarter", "end_quarter"}
        ):
            raise ValueError(
                f"{label}: sidecar binding temporal extent must declare "
                "exactly start_quarter and end_quarter"
            )
        if (
            temporal["start_quarter"] != spec.time_window.start_quarter
            or temporal["end_quarter"] != spec.time_window.end_quarter
        ):
            raise ValueError(
                f"{label}: sidecar binding temporal extent "
                f"{temporal['start_quarter']}..{temporal['end_quarter']} does "
                f"not match the metric window "
                f"{spec.time_window.start_quarter}..{spec.time_window.end_quarter}"
            )
        selectors = binding["selectors"]
        if type(selectors) is not list or selectors:
            raise ValueError(
                f"{label}: sidecar binding must declare an empty selector list; "
                "sidecar scalars cannot support commodity/region selectors"
            )
        if spec.commodity_axis is not None or spec.region_axis is not None:
            raise ValueError(
                f"{label}: sidecar scalar binding cannot satisfy a declared "
                "commodity/region selector"
            )
        value = payload[spec.column]
        if _is_missing_value(value):
            raise ValueError(
                f"{label}: sidecar {artifact.name} of run {run_dir} declares "
                f"{spec.column!r} as null or NaN, so the metric has no value"
            )
        if _is_nonfinite_value(value):
            raise ValueError(
                f"{label}: sidecar {artifact.name} of run {run_dir} declares "
                f"{spec.column!r} as a non-finite value ({value!r}); inf/-inf "
                "propagates through every aggregation, so the metric has no "
                "value"
            )
        value_type = binding["value_type"]
        if value_type not in ("number", "string"):
            raise ValueError(
                f"{label}: sidecar binding value_type must be 'number' or "
                "'string'"
            )
        # The declared datatype must agree with the unit's semantics: a
        # quantitative unit is a number and a categorical unit is a string.
        if spec.unit in _CATEGORICAL_UNITS:
            if value_type != "string":
                raise ValueError(
                    f"{label}: categorical unit {spec.unit!r} requires "
                    "value_type='string'"
                )
        elif value_type != "number":
            raise ValueError(
                f"{label}: quantitative unit {spec.unit!r} requires "
                "value_type='number'"
            )
        if value_type == "number":
            if not _is_numeric_measurement(value):
                raise ValueError(
                    f"{label}: sidecar binding declares value_type='number' "
                    f"but {spec.column!r} is {type(value).__name__}"
                )
        elif type(value) is not str:
            raise ValueError(
                f"{label}: sidecar binding declares value_type='string' "
                f"but {spec.column!r} is {type(value).__name__}"
            )


def _verify_metric_artifact_content(
    *,
    record: EvidenceRecord,
    run_dir: Path,
    artifact: Path,
    specs: list[MetricSpec],
) -> None:
    """Dispatch metric-content verification by artefact type."""
    if artifact.suffix == ".parquet":
        _verify_metric_parquet_content(
            record=record, run_dir=run_dir, artifact=artifact, specs=specs
        )
    else:
        _verify_metric_sidecar_content(
            record=record, run_dir=run_dir, artifact=artifact, specs=specs
        )


def verify_supported_metric_content(root: Path, record: EvidenceRecord) -> None:
    """Root-back verify that every declared metric exists in the backing runs.

    A run reference proves that a *run* happened; it says nothing about
    whether the metrics the record rests on were actually produced by it. A
    record could therefore declare plausible-looking metrics
    (``table_or_sidecar``/``column``) that no run ever wrote. This gate closes
    that gap for SUPPORTED records: every metric of the record is checked
    against the output of every run it references —

    * the declared ``fidelity`` must be a model layer that run actually ran:
      an F1 quantity cannot be validated against an F2 run (nor an F2 quantity
      against an F1 run), and a synthetic/analytical probe is no run layer at
      all (see :func:`_verify_metric_layer_binding`);
    * the declared ``unit`` must be the unit the model declares for the
      resolved artefact's canonical ``(table, column)`` pair, so a physical
      quantity is not compared in the unit of a different quantity and an
      aliased ``table_or_sidecar`` spelling cannot dodge the check (see
      :func:`_verify_metric_unit_binding`);
    * the declared ``table_or_sidecar`` must exist in the run output (a
      compact Parquet table, or a sidecar file);
    * the declared ``column`` must exist there (Parquet schema, or sidecar
      key with a finite, non-null value), and for a TARGET/CANDIDATE_LINKAGE
      metric the column must carry actual values throughout the declared
      window/selector intersection rather than being null, NaN or infinite
      there;
    * the declared ``time_window`` must be covered by the table's
      ``quarter`` column, so a metric declared over quarters the run never
      produced is rejected rather than supported by unrelated rows;
    * a declared ``commodity_axis`` / ``region_axis`` selector must be
      covered by the table's ``commodity_id`` / ``region_id`` column; and
    * the intersection of the two must be covered: every declared quarter
      must carry rows for every declared commodity/region selector, so a
      metric cannot be supported by a table that measures the declared
      commodity only in other quarters.

    Parameters
    ----------
    root
        Repository root (used to resolve relative run output directories).
    record
        The SUPPORTED record whose metrics are verified.

    Raises
    ------
    ValueError
        If a referenced run's manifest declares no model layer, a metric's
        declared fidelity is not that layer, a metric's declared unit is not
        the unit of the column it reads (or no unit is declared for that
        column), a metric's table/sidecar is missing from a referenced run,
        its column is absent, the declared window has no rows, a declared
        selector value is not covered by the table, or a
        TARGET/CANDIDATE_LINKAGE metric carries no usable data in the
        declared window/selector intersection.
    """
    table_units = metric_table_units()
    for ref in record.run_references:
        run_dir = _resolve_output_dir(ref.output_dir, root)
        run_layer = _run_declared_layer(run_dir)
        by_artifact: dict[str, list[MetricSpec]] = {}
        for spec in record.metric_specs:
            # The layer is a property of the record's metrics against this run,
            # so it is checked before the run's artefacts are searched: a run
            # cannot hold the column of a quantity it never ran.
            _verify_metric_layer_binding(
                spec=spec,
                run_dir=run_dir,
                run_layer=run_layer,
                label=_metric_label(record, spec),
            )
            by_artifact.setdefault(spec.table_or_sidecar, []).append(spec)
        for table_or_sidecar, specs in by_artifact.items():
            artifact = _metric_artifact_path(run_dir, table_or_sidecar)
            if artifact is None:
                metric_ids = sorted(spec.metric_id for spec in specs)
                raise ValueError(
                    f"EvidenceRecord {record.record_id}: metric_specs "
                    f"{metric_ids} declare "
                    f"table_or_sidecar={table_or_sidecar!r}, but run "
                    f"{ref.run_id!r} ({run_dir}) holds no such table or sidecar"
                )
            # A metric may only rest on bytes the verified run hashed.  A
            # staging path (``.tmp-*``) or any other unhashed file could change
            # after verification without invalidating the run digest.
            hashed_paths = _hashed_output_paths(run_dir)
            try:
                relative_artifact = (
                    artifact.resolve()
                    .relative_to(run_dir.resolve())
                    .as_posix()
                )
            except ValueError:
                relative_artifact = None
            if (
                relative_artifact is None
                or any(
                    part.startswith(".tmp-")
                    for part in Path(relative_artifact).parts
                )
                or relative_artifact not in hashed_paths
            ):
                raise ValueError(
                    f"EvidenceRecord {record.record_id}: metric artefact "
                    f"{table_or_sidecar!r} in run {ref.run_id!r} is not "
                    "covered by the run's verified output hashes"
                )
            _verify_metric_artifact_content(
                record=record, run_dir=run_dir, artifact=artifact, specs=specs
            )
            # Unit binding is checked last so that a record is never rejected
            # on its unit claim for an artefact that was never there: every
            # artifact-level check above reports first.
            for spec in specs:
                _verify_metric_unit_binding(
                    spec=spec,
                    run_dir=run_dir,
                    artifact=artifact,
                    label=_metric_label(record, spec),
                    table_units=table_units,
                )


@dataclass(frozen=True)
class _VerifiedRun:
    """One run reference that passed ``verify_run_identity``.

    Only runs that survived the root-backed gate are collected, so a linked
    observed state that names one of these run ids is bound to a run the
    repository actually holds.
    """

    run_id: str
    scenario_id: str
    digest: str
    output_dir: Path


def _run_output_quarter_labels(run_dir: Path) -> set[str]:
    """Collect the ``quarter`` labels a verified run's own output carries.

    The material runner writes every table declared in ``summary.json``'s
    ``row_counts`` as a tick-grain Parquet table with a ``quarter`` column
    (``verify_run_identity`` refuses a table without one), so the union of
    those columns is the run's actual quarter coverage.
    """
    summary_path = run_dir / "summary.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"verify_supported_record_runs: run {run_dir} has no readable "
            f"summary.json to establish its quarter coverage: {exc}"
        ) from exc
    row_counts = summary.get("row_counts") if isinstance(summary, dict) else None
    if not isinstance(row_counts, dict) or not row_counts:
        raise ValueError(
            f"verify_supported_record_runs: run {run_dir} declares no "
            "summary.json 'row_counts', so its quarter coverage is unknown"
        )

    quarters: set[str] = set()
    for table_name in row_counts:
        if not isinstance(table_name, str) or not table_name:
            raise ValueError(
                f"verify_supported_record_runs: run {run_dir} declares a "
                f"non-string trajectory table name: {table_name!r}"
            )
        table_path = _metric_artifact_path(run_dir, table_name)
        if table_path is None or table_path.suffix != ".parquet":
            raise ValueError(
                f"verify_supported_record_runs: run {run_dir} declares "
                f"trajectory table {table_name!r} but it is not readable as "
                "a Parquet table"
            )
        try:
            values = _read_column_values(table_path, "quarter")
        except ValueError as exc:
            raise ValueError(
                f"verify_supported_record_runs: run {run_dir} trajectory "
                f"table {table_name!r} carries no readable 'quarter' column: "
                f"{exc}"
            ) from exc
        quarters.update(
            str(value) for value in values if value is not None
        )
    return quarters


def _verify_linked_observed_states(
    root: Path,
    record: EvidenceRecord,
    verified_runs: list[_VerifiedRun],
) -> None:
    """Root-back verify the observed states a SUPPORTED record links.

    ``run_references`` prove which runs happened; ``linked_observed_states``
    claim which captured snapshots the record's reasoning rests on. Those
    snapshots are model output of a *specific* run at a *specific* quarter, so
    each one is bound to a run the gate above verified:

    * a SUPPORTED record must link at least one observed state — a historical
      linkage with no snapshot is not traceable to any model output;
    * ``source_run_id`` must name one of the record's verified runs (a
      fabricated run id names no verified run and is rejected);
    * ``source_scenario`` must be the scenario of that run, and
      ``source_digest`` must be the digest that run verified with, so a
      snapshot cannot be attributed to a run with different content;
    * ``source_checkpoint_quarter`` must appear in that run's own output, so a
      snapshot cannot claim a quarter the source run never produced.

    Parameters
    ----------
    root
        Repository root (used to resolve relative run output directories).
    record
        The SUPPORTED record whose linked observed states are verified.
    verified_runs
        The run references that already passed ``verify_run_identity``.

    Raises
    ------
    ValueError
        If the record links no observed state, or a linked state does not name
        a verified run, contradicts its scenario/digest, or claims a checkpoint
        quarter the source run's output does not contain.
    """
    if not record.linked_observed_states:
        raise ValueError(
            f"EvidenceRecord {record.record_id}: status=SUPPORTED but has no "
            "linked_observed_states; a supported record must link the observed "
            "snapshot(s) it is traceable to"
        )

    by_run_id: dict[str, _VerifiedRun] = {}
    for run in verified_runs:
        by_run_id.setdefault(run.run_id, run)
    quarters_by_run_id: dict[str, set[str]] = {}

    for state in record.linked_observed_states:
        label = (
            f"EvidenceRecord {record.record_id}: observed_state "
            f"{state.observed_state_id}"
        )
        source_run = by_run_id.get(state.source_run_id)
        if source_run is None:
            raise ValueError(
                f"{label}: source_run_id {state.source_run_id!r} matches no "
                "verified run_reference of this record (verified runs: "
                f"{sorted(by_run_id)}); a snapshot of an unverified run is not "
                "evidence"
            )
        if state.source_scenario != source_run.scenario_id:
            raise ValueError(
                f"{label}: source_scenario {state.source_scenario!r} does not "
                f"match the verified run's scenario "
                f"{source_run.scenario_id!r}"
            )
        if state.source_digest != source_run.digest:
            raise ValueError(
                f"{label}: source_digest {state.source_digest[:16]}... does "
                f"not match the digest verified for run "
                f"{source_run.run_id!r} ({source_run.digest[:16]}...)"
            )
        run_dir = _resolve_output_dir(source_run.output_dir, root)
        present = quarters_by_run_id.get(source_run.run_id)
        if present is None:
            present = _run_output_quarter_labels(run_dir)
            quarters_by_run_id[source_run.run_id] = present
        if state.source_checkpoint_quarter not in present:
            raise ValueError(
                f"{label}: source_checkpoint_quarter "
                f"{state.source_checkpoint_quarter} is not in the output of "
                f"run {source_run.run_id!r} ({run_dir}); the snapshot claims a "
                "quarter its source run never produced"
            )


def verify_supported_record_runs(root: Path, record: EvidenceRecord) -> None:
    """Root-back verify the run references of one SUPPORTED EvidenceRecord.

    This is the single root-backed gate for SUPPORTED records. It is called by
    ``verify_evidence_manifest_runs`` (the loader publish/load path) and,
    through the ``_supported_requires_runs`` Pydantic validator, by every
    construction/parse that supplies a root validation context — so a record
    cannot become SUPPORTED without passing exactly these checks.

    It ensures that:
    1. No metric of the record has ``validation_fidelity=no_counterpart``:
       such a metric has no model counterpart at any fidelity, so it cannot
       have been validated against a run and cannot carry a SUPPORTED record.
    2. The declared v1 card SHA-256 matches ``config/p06/cards/<mechanism>.json``
       and any declared superseding v2 card SHA-256 matches
       ``config/mechanisms/v2/<mechanism>.json``
    3. Run outputs exist on disk and have the expected digests
    4. The run_id in the reference matches the actual run_id in the manifest
    5. Each distinct actual run (by resolved output_dir + digest) is counted
       only once toward minimum_replicates
    6. Only runs with DISTINCT seeds count as independent replicates: same-seed
       references are deterministic replays of one stochastic trajectory, so a
       record whose references cover fewer distinct seeds than its declared
       ``minimum_replicates`` is rejected
    7. Every declared metric is backed by the referenced runs' output: its
       ``table_or_sidecar`` and ``column`` exist there, the declared
       ``time_window`` is covered by real rows, and a declared
       commodity/region selector is covered by the table's axis column — for
       every declared quarter, not just for the table as a whole (see
       :func:`verify_supported_metric_content`)
    8. The record links at least one observed state, and each linked state
       names a *verified* run: its ``source_run_id``, ``source_scenario`` and
       ``source_digest`` must agree with that run, and its
       ``source_checkpoint_quarter`` must be a quarter the source run's output
       actually contains (see :func:`_verify_linked_observed_states`)

    Raises
    ------
    ValueError
        If the record has no run_references, if any metric has
        ``validation_fidelity`` ``no_counterpart``, if any declared card SHA
        does not match the card on disk, or if any run reference fails
        verification, including missing output directory, digest mismatch,
        invalid manifest fields, run_id mismatch, duplicate run references, too
        few distinct seeds/actual runs to satisfy the declared
        ``minimum_replicates``, a metric whose table/column/window/selector is
        absent from a referenced run's output, or a missing/mis-attributed
        linked_observed_state.
    """
    if not record.run_references:
        raise ValueError(
            f"EvidenceRecord {record.record_id}: "
            f"status=SUPPORTED but has no run_references"
        )

    # A metric with no model counterpart cannot be validated by any run, so
    # a record resting on one can never be SUPPORTED. Checked before the run
    # verification: the record is rejected on its own declared content.
    _verify_supported_metric_fidelity(record)

    # Card provenance: the declared card SHAs must match the cards on disk.
    _verify_record_cards(root, record)

    # Independent replicates need distinct seeds: same-seed references are
    # deterministic replays of one and the same stochastic trajectory, so
    # they cannot count as independent replicates even when they point at
    # distinct actual runs in distinct output directories. This is a
    # property of the declared references, so it is checked before any run
    # output is touched.
    distinct_seeds = {ref.seed for ref in record.run_references}
    if len(distinct_seeds) < record.minimum_replicates:
        raise ValueError(
            f"EvidenceRecord {record.record_id}: run_references declare only "
            f"{len(distinct_seeds)} distinct seed(s) "
            f"{sorted(distinct_seeds)}, but "
            f"minimum_replicates={record.minimum_replicates}; runs sharing a "
            "seed are deterministic replays, not independent stochastic "
            "replicates, so same-seed runs cannot count as independent "
            "replicates"
        )

    # Track distinct actual runs by (resolved_output_dir, digest)
    seen_actual_runs: set[tuple[Path, str]] = set()
    # Only runs with consistent, nonzero RNG activity can be independent
    # stochastic replicates.
    stochastic_seeds: set[int] = set()
    # Verified runs, for binding the record's linked observed states to them.
    verified_runs: list[_VerifiedRun] = []

    for ref in record.run_references:
        # verify_run_identity will raise ValueError if verification fails
        # It returns the verified RunManifest
        actual_manifest = verify_run_identity(
            root=root,
            output_dir=ref.output_dir,
            scenario_id=ref.scenario_id,
            seed=ref.seed,
            expected_digest=ref.digest,
        )

        # CRITICAL: The run_id in the reference must match the actual run_id
        # in the manifest. Fabricated run_ids that don't match the manifest
        # are rejected.
        if actual_manifest.run_id != ref.run_id:
            raise ValueError(
                f"EvidenceRecord {record.record_id}: run_reference.run_id "
                f"{ref.run_id!r} does not match actual run_id "
                f"{actual_manifest.run_id!r} in manifest"
            )
        verified_runs.append(
            _VerifiedRun(
                run_id=actual_manifest.run_id,
                scenario_id=ref.scenario_id,
                digest=ref.digest,
                output_dir=ref.output_dir,
            )
        )

        # Track distinct actual runs for replicate counting
        # Resolve output_dir relative to root to get the actual path
        resolved_path = _resolve_output_dir(ref.output_dir, root)
        actual_run_key = (resolved_path, ref.digest)
        if actual_run_key in seen_actual_runs:
            raise ValueError(
                f"EvidenceRecord {record.record_id}: run_reference for "
                f"{ref.output_dir} (run_id={ref.run_id!r}) is a duplicate "
                f"of an already-verified run; each distinct actual run "
                f"can only be counted once toward minimum_replicates"
            )
        seen_actual_runs.add(actual_run_key)
        if _run_has_stochastic_activity(actual_manifest):
            stochastic_seeds.add(ref.seed)

    # Verify we have enough distinct actual runs
    if len(seen_actual_runs) < record.minimum_replicates:
        raise ValueError(
            f"EvidenceRecord {record.record_id}: only "
            f"{len(seen_actual_runs)} distinct actual runs verified, "
            f"but minimum_replicates={record.minimum_replicates}"
        )
    # The runs are real; the snapshots the record links must be theirs. A
    # linked observed state claims a specific model-output snapshot of a
    # specific run at a specific quarter, so it is bound to the verified run
    # (id/scenario/digest) and to that run's actual quarter coverage.
    _verify_linked_observed_states(root, record, verified_runs)

    # The referenced runs are real; now prove the record's metrics are theirs.
    # A verified run says nothing about whether the declared table/column/
    # window/selector exists in its output, so each metric is checked against
    # every referenced run's artefacts (H0A P0-2).
    verify_supported_metric_content(root, record)

    # Independent stochastic replicates require actual RNG activity.  A
    # minimum_replicates=1 record makes no replication claim and may rest on a
    # deterministic run; two or more require that many stochastic runs.
    if (
        record.minimum_replicates > 1
        and len(stochastic_seeds) < record.minimum_replicates
    ):
        raise ValueError(
            f"EvidenceRecord {record.record_id}: only "
            f"{len(stochastic_seeds)} distinct seed(s) among verified runs "
            f"report stochastic RNG activity, but "
            f"minimum_replicates={record.minimum_replicates}; distinct seeds "
            "over deterministic zero-draw runs (or duplicate seeds among "
            "active runs) are not independent stochastic replicates"
        )


def verify_evidence_manifest_runs(
    root: Path,
    manifest: EvidenceManifest,
) -> EvidenceManifest:
    """Verify all run references for SUPPORTED records in an EvidenceManifest.

    Every SUPPORTED record is passed through :func:`verify_supported_record_runs`
    (see it for the full list of checks). On success the returned manifest
    holds a root-verified copy of each SUPPORTED record — same field values,
    with the private ``_verified`` marker set — which is what may be published
    or consumed. Non-SUPPORTED records are returned unchanged.

    Because ``_verified`` is a private marker that is neither serialized nor
    accepted as input, it can never be self-reported by a manifest; the loader
    re-derives trust by re-running these checks against disk on every load and
    every write.

    Raises
    ------
    ValueError
        If any SUPPORTED record fails :func:`verify_supported_record_runs`.
    """
    verified_records: list[EvidenceRecord] = []
    for record in manifest.records:
        if record.status != EvidenceStatus.SUPPORTED:
            verified_records.append(record)
            continue
        verify_supported_record_runs(root, record)
        # ``model_copy`` skips validators, so re-verification cannot be short
        # circuited here; the marker records the outcome of the check above.
        verified = record.model_copy()
        verified._verified = True
        verified_records.append(verified)
    return manifest.model_copy(update={"records": verified_records})


def validate_evidence_record(payload: object, *, root: Path | None = None) -> EvidenceRecord:
    """Validate a single EvidenceRecord payload, raising Pydantic validation errors.

    ``root`` is threaded into the Pydantic validation context. A payload whose
    ``status`` is SUPPORTED is accepted only when a root is supplied and its run
    references verify against that root; a SUPPORTED payload without a root is
    rejected, so this function never yields an unverified SUPPORTED record.
    """
    return EvidenceRecord.model_validate(
        payload,
        context={"root": root} if root is not None else None,
    )


def validate_evidence_manifest(payload: object, *, root: Path | None = None) -> EvidenceManifest:
    """Validate a top-level evidence manifest as EvidenceManifest.

    ``root`` is threaded into the Pydantic validation context so that any
    SUPPORTED record is root-backed verified as part of validation. A manifest
    carrying a SUPPORTED record is therefore rejected unless a valid ``root`` is
    supplied — schema validation alone can never produce a trusted SUPPORTED
    record.

    Raises
    ------
    ValidationError
        If the payload does not conform to the EvidenceManifest schema, if any
        record has an ``intent`` field (indicating a StudyManifest), or if a
        SUPPORTED record cannot be root-backed verified.
    """
    # Guard against StudyManifest payload being passed as EvidenceManifest
    if isinstance(payload, dict):
        records = payload.get("records", [])
        if records and isinstance(records, list):
            first = records[0]
            if isinstance(first, dict) and "intent" in first:
                raise ValidationError.from_exception_data(
                    title="EvidenceManifest",
                    line_errors=[{
                        "type": "missing",
                        "loc": ("records",),
                        "msg": (
                            "Record has 'intent' field indicating StudyManifest; "
                            "use validate_study_manifest() instead"
                        ),
                        "input": first,
                    }],
                )
    return EvidenceManifest.model_validate(
        payload,
        context={"root": root} if root is not None else None,
    )


def validate_study_manifest(payload: object) -> StudyManifest:
    """Validate a top-level evidence manifest as StudyManifest.

    Raises
    ------
    ValidationError
        If the payload does not conform to the StudyManifest schema, or
        if any record has a ``hypothesis`` field (indicating an EvidenceManifest).
    """
    if isinstance(payload, dict):
        records = payload.get("records", [])
        if records and isinstance(records, list):
            first = records[0]
            if isinstance(first, dict) and "hypothesis" in first:
                raise ValidationError.from_exception_data(
                    title="StudyManifest",
                    line_errors=[{
                        "type": "missing",
                        "loc": ("records",),
                        "msg": (
                            "Record has 'hypothesis' field indicating EvidenceManifest; "
                            "use validate_evidence_manifest() instead"
                        ),
                        "input": first,
                    }],
                )
    return StudyManifest.model_validate(payload)


def load_evidence_manifest(
    root: Path,
    manifest_path: Path,
    *,
    verify_runs: bool = True,
) -> EvidenceManifest | StudyManifest:
    """Load and validate an evidence manifest from disk.

    Dispatches to the appropriate schema based on the first record's fields:
    - ``intent`` in first record => StudyManifest
    - ``hypothesis`` in first record => EvidenceManifest

    Parameters
    ----------
    root
        Repository root (used to locate cards, study sidecars, run outputs).
    manifest_path
        Path to the manifest JSON file.
    verify_runs
        If True (default), verify the artefacts a manifest references:
        for EvidenceManifest, all run references in SUPPORTED records via
        verify_run_identity plus the no-counterpart metric gate; for
        StudyManifest, every declared card and each record's
        ``studies/<study id>/study_decl.json`` sidecar via
        verify_study_manifest_cards. Set to False only for read-only schema
        validation without file access: an EvidenceManifest declaring a
        SUPPORTED record is then rejected, because a SUPPORTED record cannot
        exist without root-backed verification.

    Returns
    -------
    EvidenceManifest | StudyManifest
        Validated manifest object.

    Raises
    ------
    FileNotFoundError
        If the manifest file does not exist.
    ValidationError
        If the manifest JSON does not conform to either schema, or is ambiguous.
    ValueError
        If verify_runs=True and any SUPPORTED record's run references
        fail verify_run_identity, or any StudyDeclaration's declared card is
        missing or has a mismatching ``v1_card_sha256``.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Evidence manifest not found: {manifest_path} "
            f"(relative to root {root})"
        )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Dispatch based on first record's discriminating field
    records = payload.get("records", [])
    if records and isinstance(records, list):
        first = records[0] if records else {}
        if isinstance(first, dict):
            if "intent" in first:
                study_manifest = validate_study_manifest(payload)
                # Verify declared cards for every record
                if verify_runs:
                    verify_study_manifest_cards(root, study_manifest)
                return study_manifest
            elif "hypothesis" in first:
                # Thread the root through validation. A SUPPORTED record can
                # only be admitted when its run references verify against disk,
                # so verify_runs decides whether a root is supplied — and thus
                # whether SUPPORTED records can be loaded at all. There is no
                # separate post-hoc verification step to bypass.
                manifest = validate_evidence_manifest(
                    payload,
                    root=root if verify_runs else None,
                )
                return manifest

    # Ambiguous: raise with clear message
    raise ValidationError.from_exception_data(
        title="EvidenceManifest | StudyManifest",
        line_errors=[{
            "type": "missing",
            "loc": ("records",),
            "msg": (
                "Cannot determine manifest type: records have neither 'intent' "
                "nor 'hypothesis' field"
            ),
            "input": payload,
        }],
    )


def load_all_evidence_records(
    root: Path,
) -> list[StudyDeclaration | EvidenceRecord]:
    """Load all records from the phase manifest.

    Returns a typed list of StudyDeclaration (intent/linked_cards form) or
    EvidenceRecord (hypothesis/metric_specs form). The list is NOT homogeneous;
    consumers must narrow via ``isinstance`` before accessing type-specific fields.

    At P07A1 the manifest is ``studies/manifest.json`` and contains
    StudyDeclaration records.
    """
    manifest_path = root / "studies" / "manifest.json"
    manifest = load_evidence_manifest(root, manifest_path)
    return manifest.records  # type: ignore[return-value] — union is intentional


def write_evidence_manifest(
    root: Path,
    manifest: EvidenceManifest | StudyManifest,
    manifest_path: Path,
) -> None:
    """Write an evidence manifest to disk as JSON.

    Only EvidenceManifest is accepted; StudyManifest payloads are rejected.
    The manifest is serialized and then re-validated from those exact bytes
    with ``root`` in the validation context, so every SUPPORTED record is
    root-backed verified against disk immediately before the file is created.
    No file is created if that verification fails.

    Parameters
    ----------
    root
        Repository root (used for run reference verification).
    manifest
        Validated manifest to write.
    manifest_path
        Explicit output path (no default override).

    Raises
    ------
    TypeError
        If manifest is a StudyManifest (only EvidenceManifest is accepted).
    ValueError
        If manifest is EvidenceManifest with SUPPORTED records and any
        run reference fails verify_run_identity.
    FileExistsError
        If the target path already exists (prevents accidental overwrite).
    OSError
        If the parent directory does not exist or writing fails.
    """
    # Reject StudyManifest — only EvidenceManifest may be written via this path
    if isinstance(manifest, StudyManifest):
        raise TypeError(
            "write_evidence_manifest only accepts EvidenceManifest; "
            "StudyManifest must not be written through the evidence export path"
        )

    # Serialize to JSON bytes
    json_bytes = manifest.model_dump_json(indent=2, exclude_none=True)

    # CRITICAL: Re-validate the serialized bytes before writing, with the root
    # in the validation context. This catches any mutation that bypassed model
    # validators (e.g., model_copy with update={...} or model_construct that
    # skipped after-validators) AND re-derives SUPPORTED trust from disk: the
    # root-backed gate re-runs here, so a stale in-memory "verified" flag can
    # never substitute for verification. No file is created before this passes.
    try:
        EvidenceManifest.model_validate_json(json_bytes, context={"root": root})
    except Exception as exc:
        raise ValueError(
            "write_evidence_manifest: re-validation of serialized manifest "
            f"failed before writing: {exc}"
        ) from exc

    parent = manifest_path.parent
    if not parent.exists():
        raise OSError(f"Parent directory does not exist: {parent}")

    # No-clobber write: use os.open with O_EXCL to atomically fail if the
    # destination already exists.  This prevents the race between exists()
    # check and rename that os.replace() would silently resolve by overwriting.
    import os
    try:
        fd = os.open(
            str(manifest_path),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o644,
        )
    except FileExistsError:
        raise FileExistsError(
            f"Will not overwrite existing manifest: {manifest_path}"
        ) from None
    except OSError as exc:
        raise OSError(
            f"write_evidence_manifest: failed to open {manifest_path}: {exc}"
        ) from exc
    try:
        os.write(fd, json_bytes.encode("utf-8"))
    finally:
        os.close(fd)
