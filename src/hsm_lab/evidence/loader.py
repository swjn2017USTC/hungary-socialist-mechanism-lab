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
import re
from pathlib import Path

from pydantic import ValidationError

from hsm_lab.contract.guards import sha256_file
from hsm_lab.evidence.provenance import verify_run_identity
from hsm_lab.evidence.schemas import (
    EvidenceManifest,
    EvidenceRecord,
    EvidenceStatus,
    StudyDeclaration,
    StudyManifest,
)

# Card locations on disk. v1 cards use study-form file names (``M1.json`` …
# ``M11.json``, no zero padding) under ``config/p06/cards``; v2 superseding
# cards, when a mechanism has one, live under ``config/mechanisms/v2``.
_V1_CARD_DIR = Path("config") / "p06" / "cards"
_V2_CARD_DIR = Path("config") / "mechanisms" / "v2"

_CARD_ID_PATTERN = re.compile(r"^[Mm]0?([1-9]|1[01])$")


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

    Parameters
    ----------
    root
        Repository root containing ``config/p06/cards``.
    manifest
        Validated StudyManifest whose records are checked.

    Raises
    ------
    ValueError
        If a declared card is missing or its computed SHA-256 does not match
        the hash declared in the record.
    """
    for record in manifest.records:
        _verify_study_record_cards(root, record)


def _verify_study_record_cards(root: Path, record: StudyDeclaration) -> None:
    """Verify one StudyDeclaration's declared cards against the cards on disk.

    Raises
    ------
    ValueError
        If a declared card is missing or its computed SHA-256 does not match
        the hash declared in the record.
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


def verify_evidence_manifest_runs(
    root: Path,
    manifest: EvidenceManifest,
) -> None:
    """Verify all run references for SUPPORTED records in an EvidenceManifest.

    This function performs actual run identity verification by calling
    verify_run_identity for each run reference in SUPPORTED records. This
    ensures that:
    1. The declared v1 card SHA-256 matches ``config/p06/cards/<mechanism>.json``
       and any declared superseding v2 card SHA-256 matches
       ``config/mechanisms/v2/<mechanism>.json``
    2. Run outputs exist on disk and have the expected digests
    3. The run_id in the reference matches the actual run_id in the manifest
    4. Each distinct actual run (by resolved output_dir + digest) is counted only once
       toward minimum_replicates

    Raises
    ------
    ValueError
        If any declared card SHA in a SUPPORTED record does not match the card
        on disk, or any run reference in a SUPPORTED record fails verification,
        including missing output directory, digest mismatch, invalid manifest
        fields, run_id mismatch, or duplicate run references.
    """
    for record in manifest.records:
        if record.status != EvidenceStatus.SUPPORTED:
            continue
        if not record.run_references:
            raise ValueError(
                f"EvidenceRecord {record.record_id}: "
                f"status=SUPPORTED but has no run_references"
            )

        # Card provenance: the declared card SHAs must match the cards on disk.
        _verify_record_cards(root, record)

        # Track distinct actual runs by (resolved_output_dir, digest)
        seen_actual_runs: set[tuple[Path, str]] = set()

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

            # Track distinct actual runs for replicate counting
            # Resolve output_dir relative to root to get the actual path
            from hsm_lab.evidence.provenance import _resolve_output_dir
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

        # Verify we have enough distinct actual runs
        if len(seen_actual_runs) < record.minimum_replicates:
            raise ValueError(
                f"EvidenceRecord {record.record_id}: only "
                f"{len(seen_actual_runs)} distinct actual runs verified, "
                f"but minimum_replicates={record.minimum_replicates}"
            )


def validate_evidence_record(payload: object) -> EvidenceRecord:
    """Validate a single EvidenceRecord payload, raising Pydantic validation errors."""
    return EvidenceRecord.model_validate(payload)


def validate_evidence_manifest(payload: object) -> EvidenceManifest:
    """Validate a top-level evidence manifest as EvidenceManifest.

    Raises
    ------
    ValidationError
        If the payload does not conform to the EvidenceManifest schema, or
        if any record has an ``intent`` field (indicating a StudyManifest).
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
    return EvidenceManifest.model_validate(payload)


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
        Repository root (used to locate cards and run outputs).
    manifest_path
        Path to the manifest JSON file.
    verify_runs
        If True (default), verify the artefacts a manifest references:
        for EvidenceManifest, all run references in SUPPORTED records via
        verify_run_identity; for StudyManifest, every declared card via
        verify_study_manifest_cards. Set to False only for read-only schema
        validation without file access.

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
                manifest = validate_evidence_manifest(payload)
                # Verify run references for SUPPORTED records
                if verify_runs:
                    verify_evidence_manifest_runs(root, manifest)
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
    The manifest is validated before writing (re-validates from disk bytes).
    For EvidenceManifest with SUPPORTED records, run references are verified
    via verify_run_identity before writing.

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

    # Verify run references for SUPPORTED records before writing
    verify_evidence_manifest_runs(root, manifest)

    # Serialize to JSON bytes
    json_bytes = manifest.model_dump_json(indent=2, exclude_none=True)

    # CRITICAL: Re-validate the serialized bytes before writing.
    # This catches any mutation that bypassed model validators
    # (e.g., model_copy with update={...} that skipped after-validators).
    # model_validate_json re-runs ALL validators including _supported_requires_runs.
    try:
        EvidenceManifest.model_validate_json(json_bytes)
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
