"""P07A1 §4: evidence manifest loader.

Loads and validates evidence manifests and records. This module does NOT
read historical target values, does NOT modify the production engine, and
does NOT access the 1986Q1–1988Q4 reserved window.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from hsm_lab.evidence.schemas import EvidenceManifest, EvidenceRecord


def validate_evidence_record(payload: object) -> EvidenceRecord:
    """Validate a single EvidenceRecord payload, raising Pydantic validation errors."""
    return EvidenceRecord.model_validate(payload)


def validate_evidence_manifest(payload: object) -> EvidenceManifest:
    """Validate a top-level evidence manifest, raising on structural failure."""
    return EvidenceManifest.model_validate(payload)


def load_evidence_manifest(root: Path, manifest_path: Path) -> EvidenceManifest:
    """Load and validate an evidence manifest from disk.

    Parameters
    ----------
    root
        Repository root (used only for context in error messages).
    manifest_path
        Path to the manifest JSON file.

    Returns
    -------
    EvidenceManifest
        Validated manifest object.

    Raises
    ------
    FileNotFoundError
        If the manifest file does not exist.
    ValidationError
        If the manifest JSON does not conform to the EvidenceManifest schema.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Evidence manifest not found: {manifest_path} "
            f"(relative to root {root})"
        )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    try:
        return validate_evidence_manifest(payload)
    except ValidationError as exc:
        raise ValidationError.from_exception_data(
            title="EvidenceManifest",
            line_errors=exc.errors(),
        ) from exc


def load_all_evidence_records(root: Path) -> list[EvidenceRecord]:
    """Load all evidence records from the phase manifest.

    At P07A1 the manifest is at ``studies/manifest.json``.

    Returns
    -------
    list[EvidenceRecord]
        One record per M1–M11 mechanism, each with v1 SHA-256 anchored.
    """
    manifest_path = root / "studies" / "manifest.json"
    manifest = load_evidence_manifest(root, manifest_path)
    return manifest.records


def write_evidence_manifest(
    root: Path,
    manifest: EvidenceManifest,
    manifest_path: Path | None = None,
) -> None:
    """Write an evidence manifest to disk as JSON.

    Parameters
    ----------
    root
        Repository root.
    manifest
        Validated EvidenceManifest to write.
    manifest_path
        Output path; defaults to ``studies/manifest.json``.
    """
    if manifest_path is None:
        manifest_path = root / "studies" / "manifest.json"
    # Atomic write: write to temp file then rename
    temp_path = manifest_path.with_suffix(".tmp")
    temp_path.write_text(
        manifest.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )
    temp_path.rename(manifest_path)
