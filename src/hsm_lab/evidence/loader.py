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
from pathlib import Path

from pydantic import ValidationError

from hsm_lab.evidence.schemas import (
    EvidenceManifest,
    EvidenceRecord,
    StudyDeclaration,
    StudyManifest,
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
) -> EvidenceManifest | StudyManifest:
    """Load and validate an evidence manifest from disk.

    Dispatches to the appropriate schema based on the first record's fields:
    - ``intent`` in first record => StudyManifest
    - ``hypothesis`` in first record => EvidenceManifest

    Parameters
    ----------
    root
        Repository root (used only for context in error messages).
    manifest_path
        Path to the manifest JSON file.

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
                return validate_study_manifest(payload)
            elif "hypothesis" in first:
                return validate_evidence_manifest(payload)

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

    Parameters
    ----------
    root
        Repository root.
    manifest
        Validated manifest to write.
    manifest_path
        Explicit output path (no default override).

    Raises
    ------
    TypeError
        If manifest is a StudyManifest (only EvidenceManifest is accepted).
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
