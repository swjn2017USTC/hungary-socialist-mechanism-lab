"""
H1A — source admission, shared-observation detection, and 1957 anchor crosswalk validation.

Offline evaluation only: no PDF reading, no OCR traversal, no remote uploads.

The module treats source admission as a set of falsifiable gates:

* primary institutional/observation records need a verifiable document number or
  archival reference, valid ``RightsSpec`` evidence, a bound page range, a period
  or availability date, and excerpts that are explicitly approved for that source;
* shared roots make records non-independent even when their works differ; an
  untraceable root is ``None`` (unknown), never ``True``;
* the 63-row crosswalk is a declaration-only bijection to the legacy initial-state
  artifacts, checked field by field against ``DATA_MANIFEST_v1.json``.
"""

from __future__ import annotations

import calendar
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from hsm_lab.contract.base import ConfigError
from hsm_lab.data.schemas import RightsSpec

SCHEMA_VERSION = "hist_vnext_h1a_v1"
TARGET_INITIAL_AT = "1957-01-01"
ANCHOR_CLASSIFICATIONS = {"direct", "reconstructed", "proxy", "synthetic", "blocked"}
ANCHOR_UNITS = {
    "dwelling_anchor": "dwellings",
    "household_anchor": "households",
    "population_anchor": "persons",
}
SOURCE_EVIDENCE_KINDS = {"direct", "proxy", "reconstructed", "synthetic"}
PRIMARY_SOURCE_TYPES = {"primary_institutional", "primary_observation"}
PURPOSE_ALLOWED_USES = {
    "institutional_context": {"narrow_citation", "internal_validation_background"},
    "secondary_context": {"narrow_citation", "internal_validation_background"},
    "historical_reference": {"narrow_citation"},
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ANCHOR_RE = re.compile(r"^(dwelling|household|population)_(\d{4})_orszagos_(\d{2})$")


class _StructuralError(RuntimeError):
    """A required H1A declaration is absent, malformed, or the wrong container type."""


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def evaluate_source(record: dict, *, approved_excerpts: list[dict]) -> dict:
    """
    Evaluate a single source record for admission status.

    Returns
    -------
    dict with keys:
        status : "candidate" | "admitted" | "blocked"
        reasons : list[str]   # field-level evidence gaps
    """
    if not isinstance(record, dict):
        return {"status": "blocked", "reasons": ["record is not an object"]}

    identity_reasons: list[str] = []
    if not _usable_identifier(record.get("source_id")):
        identity_reasons.append("invalid: source_id must be non-empty")
    work_id = record.get("work_id")
    if work_id is not None and not _usable_identifier(work_id):
        identity_reasons.append("invalid: work_id must be non-empty")
    if identity_reasons:
        return {"status": "blocked", "reasons": identity_reasons}

    reasons: list[str] = []
    source_type = record.get("source_type", "")

    # ── forcing/actor purpose always blocked (H1A §4) ──
    purpose = record.get("purpose", "")
    if purpose in ("forcing", "actor"):
        reasons.append(f"purpose={purpose!r}: historical target as forcing/actor not admitted")
        return {"status": "blocked", "reasons": reasons}

    # ── secondary_analysis: always candidate (contextual, not primary evidence) ──
    if source_type == "secondary_analysis":
        reasons.append("secondary_analysis: contextual only, not a primary institutional source")
        return {"status": "candidate", "reasons": reasons}

    if source_type == "catalogue":
        reasons.append("catalogue: metadata reference only")
        return {"status": "candidate", "reasons": reasons}

    if source_type not in PRIMARY_SOURCE_TYPES:
        reasons.append(f"unknown source_type: {source_type!r}")
        return {"status": "blocked", "reasons": reasons}

    # A published document number is itself a verifiable identifier; an archival
    # reference is required only when no document number is available.  Truthy
    # containers or booleans are not identifiers.
    document_number = record.get("document_number")
    archival_reference = record.get("archival_reference")
    if document_number is not None and not isinstance(document_number, str):
        reasons.append("invalid: document_number must be a string")
    if archival_reference is not None and not isinstance(archival_reference, str):
        reasons.append("invalid: archival_reference must be a string")
    usable_document = _usable_identifier(document_number)
    usable_archive = _usable_identifier(archival_reference)
    if not usable_document and not usable_archive:
        reasons.append("missing: usable document_number or archival_reference")

    rights_status, rights_reasons = _rights_reasons(record.get("rights"))
    reasons.extend(rights_reasons)
    if rights_status == "unknown":
        return {"status": "candidate", "reasons": reasons}

    if not _is_sha256(record.get("source_sha256")):
        reasons.append("missing or invalid: source_sha256")
    if not record.get("pdf_page_range"):
        reasons.append("missing: pdf_page_range")
    if not record.get("statistical_period") and not record.get("source_available_at"):
        reasons.append("missing: statistical_period or source_available_at")
    if not _usable_identifier(record.get("observable_pattern")):
        reasons.append("missing: observable_pattern (the independently observable claim)")

    selected_ids = record.get("approved_excerpt_ids") or []
    if not isinstance(selected_ids, list) or not selected_ids:
        reasons.append("no approved excerpts")
    elif not all(_usable_identifier(item) for item in selected_ids):
        reasons.append("invalid: approved_excerpt_ids must be a list of non-empty strings")
    else:
        by_id = {
            excerpt.get("excerpt_id"): excerpt
            for excerpt in approved_excerpts
            if isinstance(excerpt, dict)
        }
        for excerpt_id in selected_ids:
            excerpt = by_id.get(excerpt_id)
            if excerpt is None:
                reasons.append(f"approved excerpt not found: {excerpt_id!r}")
                continue
            reasons.extend(_excerpt_reasons(excerpt, record))

    if reasons:
        return {"status": "blocked", "reasons": reasons}
    return {"status": "admitted", "reasons": []}


def find_shared_observations(records: list[dict]) -> list[dict]:
    """
    Detect shared/cited observations across records.

    A pair is non-independent when the records share a direct root, cite a root
    that the other record carries, or belong to the same work.  A record without
    its own traceable root cannot support an independence claim: the pair is
    ``None`` (unknown), not ``True``.  Unknown cited roots are also ``None``.
    """
    if len(records) < 2:
        return []

    known_root_ids: set[str] = set()
    for record in records:
        known_root_ids.update(_string_set(record.get("observation_ids")))

    results: list[dict] = []
    for index, record in enumerate(records):
        own_obs = _string_set(record.get("observation_ids"))
        own_cited = _string_set(record.get("cited_observation_ids"))
        work_id = record.get("work_id")

        for other in records[index + 1 :]:
            other_obs = _string_set(other.get("observation_ids"))
            other_cited = _string_set(other.get("cited_observation_ids"))
            other_work = other.get("work_id")

            shared = (
                (own_obs & other_obs)
                | (own_cited & other_obs)
                | (own_obs & other_cited)
                | (own_cited & other_cited)
            )
            all_cited = own_cited | other_cited
            unknown_cited = all_cited - known_root_ids
            same_work = work_id is not None and work_id == other_work

            if same_work:
                independent: bool | None = False
            elif shared:
                independent = None if shared & unknown_cited else False
            elif not own_obs or not other_obs:
                independent = None
            elif unknown_cited:
                independent = None
            else:
                independent = True

            results.append(
                {
                    "record_ids": [record.get("source_id"), other.get("source_id")],
                    "work_ids": [work_id, other_work],
                    "shared_work_ids": [work_id, other_work] if same_work else [],
                    "shared_observation_ids": sorted(shared),
                    "independent": independent,
                }
            )

    return results


def validate_anchor_crosswalk(
    records: list[dict],
    *,
    legacy_artifacts: list[dict] | None = None,
    legacy_artifact_ids: set[str] | None = None,
) -> None:
    """
    Validate a 1957 anchor crosswalk.

    ``legacy_artifacts`` is the full ``role=initial_state`` metadata list.  When
    supplied, every legacy artifact must be covered exactly once and every
    row field must match the artifact (ID, variable, source, path, SHA, dates,
    grade, evidence status).  ``legacy_artifact_ids`` alone is rejected because
    an ID set cannot verify those fields.

    Raises ``ValueError`` on structural or semantic violations.
    """
    if legacy_artifact_ids is not None and legacy_artifacts is None:
        raise ValueError(
            "legacy_artifact_ids alone cannot validate artifact metadata; "
            "pass legacy_artifacts from DATA_MANIFEST_v1.json"
        )
    if not isinstance(records, list):
        raise ValueError("anchor crosswalk records must be a list")

    seen_ids: dict[str, int] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"anchor record at index {index} is not an object")
        anchor_id = record.get("anchor_id")
        if not isinstance(anchor_id, str) or not anchor_id:
            raise ValueError(
                f"Record at index {index} is missing anchor_id; "
                "every anchor must have a unique anchor_id"
            )
        if anchor_id in seen_ids:
            raise ValueError(
                f"Duplicate anchor_id: {anchor_id!r} (first seen at index {seen_ids[anchor_id]}, "
                f"again at index {index})"
            )
        seen_ids[anchor_id] = index
        _validate_anchor_row(record, index)

    anchor_ids = set(seen_ids)
    for record in records:
        supporting_ids = record.get("supporting_anchor_ids")
        if supporting_ids is None:
            continue
        if not isinstance(supporting_ids, list) or not all(
            isinstance(item, str) and item for item in supporting_ids
        ):
            raise ValueError(
                f"anchor {record.get('anchor_id')!r}: supporting_anchor_ids must be a list "
                "of non-empty strings"
            )
        for supporting in supporting_ids:
            if supporting == record.get("anchor_id"):
                raise ValueError(f"anchor {record.get('anchor_id')!r} supports itself")
            if supporting not in anchor_ids:
                raise ValueError(
                    f"anchor {record.get('anchor_id')!r} references unknown supporting "
                    f"anchor {supporting!r}"
                )

    if legacy_artifacts is not None:
        _validate_anchor_bijection(records, legacy_artifacts)


def audit_h1a(root: Path) -> dict:
    """
    Run the full H1A audit on the repository at *root*.

    Returns a dict with ``exit_code`` (0 pass, 1 historical blocked, 2 structural
    block), ``structural``, ``historical``, ``summary``, and ``details``.  Any
    missing/malformed declaration or wrong container type is a structural exit 2;
    an empty authority/event package can never produce a historical PASS.
    """
    details: list[str] = []
    root = Path(root)

    candidates_path = root / "history/HIST_VNEXT/sources/batch01_candidates.json"
    authority_path = root / "history/HIST_VNEXT/sources/authority_coverage.json"
    events_path = root / "history/HIST_VNEXT/event_candidates/events.json"
    access_path = root / "history/HIST_VNEXT/exposure/access_register.json"
    review_req_path = root / "history/HIST_VNEXT/exposure/review_requests.json"
    crosswalk_path = root / "config/initial_state/hist_vnext_v1/anchor_crosswalk.json"
    manifest_path = root / "data/manifests/DATA_MANIFEST_v1.json"

    required_paths = [
        (candidates_path, "batch01_candidates.json"),
        (authority_path, "authority_coverage.json"),
        (events_path, "events.json"),
        (access_path, "access_register.json"),
        (review_req_path, "review_requests.json"),
        (crosswalk_path, "anchor_crosswalk.json"),
        (manifest_path, "DATA_MANIFEST_v1.json"),
    ]
    missing = [label for path, label in required_paths if not path.exists()]
    if missing:
        details.append(f"Missing required files: {', '.join(missing)}")
        return _structural_result(details)

    try:
        candidates_data = _load_json(candidates_path, "batch01_candidates.json")
        access_data = _load_json(access_path, "access_register.json")
        authority_data = _load_json(authority_path, "authority_coverage.json")
        events_data = _load_json(events_path, "events.json")
        review_data = _load_json(review_req_path, "review_requests.json")
        crosswalk_data = _load_json(crosswalk_path, "anchor_crosswalk.json")
        manifest_data = _load_json(manifest_path, "DATA_MANIFEST_v1.json")

        records = _records(candidates_data, "records", "batch01_candidates.json")
        approved_excerpts = _records(access_data, "approved_excerpts", "access_register.json")
        authorities = _authorities(authority_data)
        events = _records(events_data, "events", "events.json")
        requests = _records(review_data, "requests", "review_requests.json")
        anchor_records = _records(crosswalk_data, "records", "anchor_crosswalk.json")
        artifacts = _records(manifest_data, "artifacts", "DATA_MANIFEST_v1.json")
        _validate_candidate_records(records)
        _validate_approved_excerpt_records(approved_excerpts)
        _validate_authority_records(authorities)
        _validate_event_records(events)
        _validate_initial_state_artifacts(artifacts)
    except _StructuralError as exc:
        details.append(str(exc))
        return _structural_result(details)

    legacy_artifacts = [
        artifact
        for artifact in artifacts
        if artifact.get("role") == "initial_state" and artifact.get("artifact_id")
    ]
    if len(anchor_records) != 63:
        details.append(f"anchor_crosswalk.json: expected 63 records, got {len(anchor_records)}")
        return _structural_result(details, historical="BLOCKED")
    if len(legacy_artifacts) != 63:
        details.append(
            "DATA_MANIFEST_v1.json: expected 63 role=initial_state artifacts, "
            f"got {len(legacy_artifacts)}"
        )
        return _structural_result(details, historical="BLOCKED")

    try:
        _validate_crosswalk_header(crosswalk_data)
        validate_anchor_crosswalk(anchor_records, legacy_artifacts=legacy_artifacts)
    except ValueError as exc:
        details.append(f"anchor_crosswalk validation error: {exc}")
        return _structural_result(details, historical="BLOCKED")

    admitted_count = 0
    candidate_count = 0
    blocked_count = 0
    work_ids: set[str] = set()
    admitted_by_id: dict[str, dict] = {}
    admitted_records: list[dict] = []
    for record in records:
        result = evaluate_source(record, approved_excerpts=approved_excerpts)
        if result["status"] == "admitted":
            admitted_count += 1
            admitted_by_id[record["source_id"]] = record
            admitted_records.append(record)
        elif result["status"] == "candidate":
            candidate_count += 1
        else:
            blocked_count += 1
        work_id = record.get("work_id")
        if work_id:
            work_ids.add(work_id)
        for reason in result["reasons"]:
            details.append(f"  [{record.get('source_id')}] {reason}")

    approved_evidence_by_source: dict[str, list[dict]] = {}
    excerpt_by_id = {
        excerpt.get("excerpt_id"): excerpt
        for excerpt in approved_excerpts
        if isinstance(excerpt.get("excerpt_id"), str)
    }
    for record in admitted_records:
        selected = set(record.get("approved_excerpt_ids") or [])
        evidence: list[dict] = []
        for excerpt_id in selected:
            excerpt = excerpt_by_id.get(excerpt_id)
            if excerpt is None or excerpt.get("source_id") != record["source_id"]:
                continue
            pages = {
                page
                for page in excerpt.get("pdf_pages", [])
                if isinstance(page, int) and not isinstance(page, bool)
            }
            window = _date_bounds(excerpt.get("allowed_window"))
            if pages and window is not None:
                evidence.append({"pages": pages, "window": window})
        approved_evidence_by_source[record["source_id"]] = evidence

    shared = find_shared_observations(records)
    admitted_shared = find_shared_observations(admitted_records)
    non_independent = sum(1 for pair in shared if pair["independent"] is False)
    independent_pairs = sum(1 for pair in admitted_shared if pair["independent"] is True)
    details.append(
        f"  Shared-observation pairs: {len(shared)}, non-independent: {non_independent}, "
        f"admitted independent pairs: {independent_pairs}"
    )

    auth_blocked = sum(1 for authority in authorities if authority.get("status") == "blocked")
    event_candidates = sum(1 for event in events if event.get("status") == "candidate")
    review_required = sum(1 for request in requests if request.get("status") == "REVIEW_REQUIRED")
    details.append(f"  Authority entries: {len(authorities)}, blocked: {auth_blocked}")
    details.append(f"  Event candidates: {len(events)}, candidate: {event_candidates}")
    details.append(f"  Review requests: {len(requests)}, REVIEW_REQUIRED: {review_required}")

    classifications: dict[str, int] = {}
    for anchor in anchor_records:
        classification = anchor.get("classification", "unknown")
        classifications[classification] = classifications.get(classification, 0) + 1
    for classification, count in sorted(classifications.items()):
        details.append(f"  Anchor classification {classification}: {count}")
    blocked_anchors = classifications.get("blocked", 0)

    coverage_ok, coverage_reasons = _coverage_ok(
        authorities,
        events,
        admitted_by_id,
        approved_evidence_by_source,
    )
    events_ok, event_reasons = _events_ok(
        events,
        admitted_by_id,
        approved_evidence_by_source,
    )
    patterns_ok = len(admitted_records) >= 2 and all(
        _usable_identifier(record.get("observable_pattern"))
        for record in admitted_records
    )
    independent_ok = independent_pairs >= 1 and patterns_ok
    historical_reasons: list[str] = []
    if admitted_count < 2:
        historical_reasons.append("fewer than two admitted observable patterns")
    if not patterns_ok:
        historical_reasons.append("admitted records lack an observable_pattern")
    if not coverage_ok:
        historical_reasons.extend(coverage_reasons)
    if not events_ok:
        historical_reasons.extend(event_reasons)
    if not independent_ok:
        historical_reasons.append("no independent admitted observable pair with traceable roots")
    if blocked_anchors:
        historical_reasons.append(f"{blocked_anchors} anchor(s) remain blocked for 1957")
    for reason in historical_reasons:
        details.append(f"  historical gate: {reason}")

    historical_pass = not historical_reasons
    exit_code = 0 if historical_pass else 1
    return {
        "exit_code": exit_code,
        "structural": "PASS",
        "historical": "PASS" if historical_pass else "BLOCKED",
        "summary": {
            "total_candidates": candidate_count,
            "total_admitted": admitted_count,
            "total_blocked_sources": blocked_count,
            "total_blocked_anchors": blocked_anchors,
            "total_sources": len(records),
            "total_works": len(work_ids),
            "anchor_classifications": classifications,
            "authority_blocked": auth_blocked,
            "event_candidates": event_candidates,
            "review_requests_required": review_required,
            "independent_pairs": independent_pairs,
            "non_independent_pairs": non_independent,
        },
        "details": details,
    }


# --------------------------------------------------------------------------- #
# Structural helpers
# --------------------------------------------------------------------------- #


def _load_json(path: Path, label: str) -> Any:
    try:
        with open(path) as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise _StructuralError(f"JSON parse error in {label}: {exc}") from exc
    except OSError as exc:
        raise _StructuralError(f"OS error loading {label}: {exc}") from exc


def _records(data: Any, key: str, label: str) -> list[dict]:
    if not isinstance(data, dict):
        raise _StructuralError(f"{label}: top-level JSON must be an object")
    value = data.get(key)
    if not isinstance(value, list):
        raise _StructuralError(f"{label}: {key!r} must be a list")
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise _StructuralError(f"{label}: {key}[{index}] must be an object")
    return value


def _authorities(data: Any) -> list[dict]:
    if isinstance(data, list):
        value = data
    elif isinstance(data, dict):
        value = data.get("authorities")
    else:
        raise _StructuralError("authority_coverage.json: top-level JSON must be an object or list")
    if not isinstance(value, list):
        raise _StructuralError("authority_coverage.json: 'authorities' must be a list")
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise _StructuralError(
                f"authority_coverage.json: authorities[{index}] must be an object"
            )
    return value


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(
        _usable_identifier(item) for item in value
    ):
        raise _StructuralError(f"{label} must be a list of non-empty strings")
    return value


def _validate_candidate_records(records: list[dict]) -> None:
    seen_source_ids: set[str] = set()
    for index, record in enumerate(records):
        label = f"batch01_candidates.json: records[{index}]"
        source_id = record.get("source_id")
        if not _usable_identifier(source_id):
            raise _StructuralError(f"{label}.source_id must be a non-empty string")
        if source_id in seen_source_ids:
            raise _StructuralError(f"{label}.source_id duplicates {source_id!r}")
        seen_source_ids.add(source_id)
        work_id = record.get("work_id")
        if work_id is not None and not _usable_identifier(work_id):
            raise _StructuralError(f"{label}.work_id must be a non-empty string or null")
        for field in (
            "source_type",
            "purpose",
            "document_number",
            "archival_reference",
            "source_sha256",
            "pdf_page_range",
            "statistical_period",
            "source_available_at",
            "publication_date",
            "local_path",
        ):
            value = record.get(field)
            if value is not None and not isinstance(value, str):
                raise _StructuralError(f"{label}.{field} must be a string or null")
        rights = record.get("rights")
        if rights is not None and not isinstance(rights, dict):
            raise _StructuralError(f"{label}.rights must be an object or null")
        for field in ("approved_excerpt_ids", "observation_ids", "cited_observation_ids"):
            value = record.get(field)
            if value is not None:
                _string_list(value, f"{label}.{field}")
        if "pdf_pages" in record and record["pdf_pages"] is not None:
            page_count = record["pdf_pages"]
            if isinstance(page_count, bool) or not isinstance(page_count, int) or page_count < 1:
                raise _StructuralError(f"{label}.pdf_pages must be a positive integer")
        pattern = record.get("observable_pattern")
        if pattern is not None and not isinstance(pattern, str):
            raise _StructuralError(f"{label}.observable_pattern must be a string")


def _validate_approved_excerpt_records(excerpts: list[dict]) -> None:
    seen_excerpt_ids: set[str] = set()
    for index, excerpt in enumerate(excerpts):
        label = f"access_register.json: approved_excerpts[{index}]"
        excerpt_id = excerpt.get("excerpt_id")
        if isinstance(excerpt_id, str) and excerpt_id:
            if excerpt_id in seen_excerpt_ids:
                raise _StructuralError(f"{label}.excerpt_id duplicates {excerpt_id!r}")
            seen_excerpt_ids.add(excerpt_id)
        for field in (
            "excerpt_id",
            "source_id",
            "source_sha256",
            "content_hash",
            "approved_by",
            "approved_at",
            "allowed_use",
            "allowed_window",
        ):
            if not _usable_identifier(excerpt.get(field)):
                raise _StructuralError(f"{label}.{field} must be a non-empty string")
        pages = excerpt.get("pdf_pages")
        if not isinstance(pages, list) or not pages:
            raise _StructuralError(f"{label}.pdf_pages must be a non-empty list")
        if not all(
            isinstance(page, int) and not isinstance(page, bool) and page >= 1
            for page in pages
        ):
            raise _StructuralError(f"{label}.pdf_pages must contain positive integers")
        handoff = excerpt.get("handoff")
        if not isinstance(handoff, dict):
            raise _StructuralError(f"{label}.handoff must be an object")
        for field in ("content_sha256", "source_sha256", "approved_by", "approved_at"):
            if not _usable_identifier(handoff.get(field)):
                raise _StructuralError(f"{label}.handoff.{field} must be a non-empty string")


def _validate_authority_records(authorities: list[dict]) -> None:
    for index, authority in enumerate(authorities):
        label = f"authority_coverage.json: authorities[{index}]"
        for field in ("required_primary_ids", "implementation_evidence_ids"):
            value = authority.get(field)
            if value is not None:
                _string_list(value, f"{label}.{field}")
        if not isinstance(authority.get("status"), str) or not authority["status"]:
            raise _StructuralError(f"{label}.status must be a non-empty string")


def _validate_event_records(events: list[dict]) -> None:
    seen_event_ids: set[str] = set()
    for index, event in enumerate(events):
        label = f"events.json: events[{index}]"
        if not _usable_identifier(event.get("event_id")):
            raise _StructuralError(f"{label}.event_id must be a non-empty string")
        if event["event_id"] in seen_event_ids:
            raise _StructuralError(f"{label}.event_id duplicates {event['event_id']!r}")
        seen_event_ids.add(event["event_id"])
        if not isinstance(event.get("status"), str) or not event["status"]:
            raise _StructuralError(f"{label}.status must be a non-empty string")
        for field in ("authority_granted", "authority_removed"):
            value = event.get(field)
            if value is not None:
                _string_list(value, f"{label}.{field}")
        for field in (
            "date",
            "date_precision",
            "document_number",
            "archival_reference",
            "source_id",
            "source_sha256",
            "issuer",
            "legal_force",
            "reviewer",
            "implementation_evidence_id",
            "observed_implementation_at",
        ):
            value = event.get(field)
            if value is not None and not isinstance(value, str):
                raise _StructuralError(f"{label}.{field} must be a string or null")
        if "pdf_page" in event and event["pdf_page"] is not None:
            page = event["pdf_page"]
            if isinstance(page, bool) or not isinstance(page, int) or page < 1:
                raise _StructuralError(f"{label}.pdf_page must be a positive integer")
        if "rights" in event and event["rights"] is not None:
            if not isinstance(event["rights"], dict):
                raise _StructuralError(f"{label}.rights must be an object or null")


def _validate_initial_state_artifacts(artifacts: list[dict]) -> None:
    for index, artifact in enumerate(artifacts):
        if artifact.get("role") != "initial_state":
            continue
        label = f"DATA_MANIFEST_v1.json: artifacts[{index}]"
        for field in (
            "artifact_id",
            "variable_id",
            "source_id",
            "sha256",
            "path",
            "grade",
            "evidence_status",
            "observation_at",
            "initial_at",
        ):
            if not _usable_identifier(artifact.get(field)):
                raise _StructuralError(f"{label}.{field} must be a non-empty string")


def _structural_result(details: list[str], *, historical: str = "UNIDENTIFIED") -> dict:
    return {
        "exit_code": 2,
        "structural": "BLOCKED",
        "historical": historical,
        "summary": {},
        "details": details,
    }


def _validate_crosswalk_header(data: Any) -> None:
    if not isinstance(data, dict):
        raise ValueError("anchor_crosswalk.json: top-level JSON must be an object")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"anchor_crosswalk.json: schema_version must be {SCHEMA_VERSION!r}, "
            f"got {data.get('schema_version')!r}"
        )
    if data.get("declaration_only") is not True:
        raise ValueError("anchor_crosswalk.json: declaration_only must be true")
    if data.get("runtime_connected") is not False:
        raise ValueError("anchor_crosswalk.json: runtime_connected must be false")
    if data.get("target_initial_at") != TARGET_INITIAL_AT:
        raise ValueError(
            f"anchor_crosswalk.json: target_initial_at must be {TARGET_INITIAL_AT!r}"
        )


# --------------------------------------------------------------------------- #
# Admission helpers
# --------------------------------------------------------------------------- #


def _rights_reasons(rights: Any) -> tuple[str | None, list[str]]:
    if not isinstance(rights, dict):
        return None, ["missing: rights"]
    try:
        spec = RightsSpec.model_validate(rights)
    except (ValidationError, ConfigError, ValueError) as exc:
        return None, [f"invalid rights: {exc}"]
    if spec.license_status == "unknown":
        return "unknown", ["unknown rights: rights"]

    # A non-unknown label is not permission by itself.  Both verified and
    # restricted material need a named licence, a terms locator, a quoted
    # evidence statement, a check date, and permission to hold a local copy.
    missing = [
        name
        for name, value in (
            ("license_name", spec.license_name),
            ("terms_locator", spec.terms_locator),
            ("evidence_quote", spec.evidence_quote),
            ("checked_at", spec.checked_at),
        )
        if not (value.strip() if isinstance(value, str) else value)
    ]
    if missing:
        return None, [f"invalid rights: non-unknown status lacks {missing}"]
    if spec.download_allowed is not True:
        return None, ["invalid rights: download_allowed is not true for the requested use"]
    return spec.license_status, []


def _excerpt_reasons(excerpt: dict, record: dict) -> list[str]:
    excerpt_id = excerpt.get("excerpt_id", "unknown")
    reasons: list[str] = []
    required = (
        "excerpt_id",
        "source_id",
        "source_sha256",
        "content_hash",
        "approved_by",
        "approved_at",
        "allowed_use",
        "allowed_window",
        "pdf_pages",
        "handoff",
    )
    for field in required:
        if not excerpt.get(field):
            reasons.append(f"invalid excerpt {excerpt_id!r}: missing {field}")
    if reasons:
        return reasons

    if not _usable_identifier(excerpt["excerpt_id"]):
        reasons.append(f"invalid excerpt {excerpt_id!r}: excerpt_id is blank")
    if not _usable_identifier(excerpt["source_id"]):
        reasons.append(f"invalid excerpt {excerpt_id!r}: source_id is blank")
    if excerpt["source_id"] != record.get("source_id"):
        reasons.append(
            f"excerpt source_id mismatch: expected {record.get('source_id')!r}, "
            f"got {excerpt['source_id']!r}"
        )
    if not _is_sha256(excerpt["source_sha256"]):
        reasons.append(f"invalid excerpt {excerpt_id!r}: source_sha256 is not SHA256")
    elif excerpt["source_sha256"] != record.get("source_sha256"):
        reasons.append(f"invalid excerpt {excerpt_id!r}: source_sha256 does not match parent")
    if not _is_sha256(excerpt["content_hash"]):
        reasons.append(f"invalid excerpt {excerpt_id!r}: content_hash is not SHA256")
    reasons.extend(_handoff_reasons(excerpt))
    if not _is_iso_instant(excerpt["approved_at"]):
        reasons.append(f"invalid excerpt {excerpt_id!r}: approved_at is not an ISO date")
    if not _usable_identifier(excerpt["approved_by"]):
        reasons.append(f"invalid excerpt {excerpt_id!r}: approved_by is empty")

    allowed_uses = PURPOSE_ALLOWED_USES.get(record.get("purpose"), set())
    allowed_use = excerpt["allowed_use"]
    if not isinstance(allowed_use, str) or allowed_use not in allowed_uses:
        reasons.append(
            f"invalid excerpt {excerpt_id!r}: allowed_use {allowed_use!r} "
            f"is not permitted for purpose {record.get('purpose')!r}"
        )

    page_count = record.get("pdf_pages")
    page_bounds = _page_range(record.get("pdf_page_range"))
    pages = excerpt["pdf_pages"]
    if not isinstance(page_count, int) or isinstance(page_count, bool) or page_count < 1:
        reasons.append("invalid parent record: pdf_pages must be a positive integer")
    if not isinstance(pages, list) or not pages:
        reasons.append(f"invalid excerpt {excerpt_id!r}: pdf_pages must be a non-empty list")
    elif page_bounds is None:
        reasons.append("invalid parent record: pdf_page_range is not a valid page range")
    else:
        for page in pages:
            if isinstance(page, bool) or not isinstance(page, int) or page < 1:
                reasons.append(f"invalid excerpt {excerpt_id!r}: pdf_pages must be integers")
                break
            if not page_bounds[0] <= page <= page_bounds[1]:
                reasons.append(
                    f"invalid excerpt {excerpt_id!r}: page {page} is outside "
                    f"{record.get('pdf_page_range')!r}"
                )
                break
            if isinstance(page_count, int) and page > page_count:
                reasons.append(
                    f"invalid excerpt {excerpt_id!r}: page {page} exceeds pdf_pages={page_count}"
                )
                break

    window = _date_bounds(excerpt["allowed_window"])
    if window is None:
        reasons.append(f"invalid excerpt {excerpt_id!r}: allowed_window is not a date range")
    else:
        source_period = record.get("statistical_period")
        available_at = record.get("source_available_at")
        if not source_period and not available_at:
            reasons.append(
                f"invalid excerpt {excerpt_id!r}: parent record has no period or availability"
            )
        if available_at:
            bounds = _date_bounds(available_at)
            if bounds is None or not (window[0] <= bounds[0] and window[1] >= bounds[1]):
                reasons.append(
                    f"invalid excerpt {excerpt_id!r}: allowed_window does not cover "
                    f"source_available_at={available_at!r}"
                )
        if source_period:
            bounds = _date_bounds(source_period)
            if bounds is None or not (window[0] <= bounds[0] and window[1] >= bounds[1]):
                reasons.append(
                    f"invalid excerpt {excerpt_id!r}: allowed_window does not cover "
                    f"statistical_period={source_period!r}"
                )
    return reasons


def _handoff_reasons(excerpt: dict) -> list[str]:
    """Compare an excerpt with its separately declared administrator handoff."""
    excerpt_id = excerpt.get("excerpt_id", "unknown")
    handoff = excerpt.get("handoff")
    if not isinstance(handoff, dict):
        return [f"invalid excerpt {excerpt_id!r}: handoff must be an object"]
    reasons: list[str] = []
    for field in ("content_sha256", "source_sha256", "approved_by", "approved_at"):
        if not _usable_identifier(handoff.get(field)):
            reasons.append(f"invalid excerpt {excerpt_id!r}: handoff missing {field}")
    if reasons:
        return reasons
    if handoff["content_sha256"] != excerpt.get("content_hash"):
        reasons.append(f"invalid excerpt {excerpt_id!r}: handoff content_sha256 mismatch")
    if handoff["source_sha256"] != excerpt.get("source_sha256"):
        reasons.append(f"invalid excerpt {excerpt_id!r}: handoff source_sha256 mismatch")
    if handoff["approved_by"] != excerpt.get("approved_by"):
        reasons.append(f"invalid excerpt {excerpt_id!r}: handoff approved_by mismatch")
    if handoff["approved_at"] != excerpt.get("approved_at"):
        reasons.append(f"invalid excerpt {excerpt_id!r}: handoff approved_at mismatch")
    if not _is_sha256(handoff["content_sha256"]):
        reasons.append(f"invalid excerpt {excerpt_id!r}: handoff content_sha256 is not SHA256")
    if not _is_sha256(handoff["source_sha256"]):
        reasons.append(f"invalid excerpt {excerpt_id!r}: handoff source_sha256 is not SHA256")
    return reasons


def _usable_identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _is_iso_instant(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        try:
            date.fromisoformat(value)
            return True
        except ValueError:
            return False


def _atomic_date_bounds(value: Any) -> tuple[date, date] | None:
    """Parse one atomic year, month, or day representation (no range)."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or "/" in text:
        return None
    match = re.fullmatch(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", text)
    if match is None:
        return None
    year = int(match.group(1))
    month = int(match.group(2) or 1)
    day = int(match.group(3) or 1)
    try:
        start = date(year, month, day)
    except ValueError:
        return None
    if match.group(3):
        return (start, start)
    if match.group(2):
        last_day = calendar.monthrange(year, month)[1]
        return (start, date(year, month, last_day))
    return (date(year, 1, 1), date(year, 12, 31))


def _standalone_date_bounds(value: Any) -> tuple[date, date] | None:
    """Parse one atomic date or one standalone ordered year range."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or "/" in text:
        return None
    year_range = re.fullmatch(r"(\d{4})-(\d{4})", text)
    if year_range is not None:
        start_year = int(year_range.group(1))
        end_year = int(year_range.group(2))
        if start_year > end_year:
            return None
        try:
            return (date(start_year, 1, 1), date(end_year, 12, 31))
        except ValueError:
            return None
    return _atomic_date_bounds(text)


def _date_bounds(value: Any) -> tuple[date, date] | None:
    """Parse one standalone date/range or exactly two ordered atomic endpoints."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    parts = text.split("/")
    if len(parts) == 1:
        return _standalone_date_bounds(parts[0])
    if len(parts) != 2:
        return None
    left = _atomic_date_bounds(parts[0])
    right = _atomic_date_bounds(parts[1])
    if left is None or right is None:
        return None
    if left[0] > right[0]:
        return None
    return (left[0], right[1])


def _date_matches_precision(value: Any, precision: Any) -> bool:
    if not isinstance(value, str):
        return False
    if precision == "day":
        pattern = r"\d{4}-\d{2}-\d{2}"
    elif precision == "month":
        pattern = r"\d{4}-\d{2}"
    elif precision == "year":
        pattern = r"\d{4}"
    else:
        return False
    return re.fullmatch(pattern, value) is not None and _date_bounds(value) is not None


def _page_range(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(\d+)\s*[-–]\s*(\d+)\s*", value)
    if match is None:
        return None
    first, last = int(match.group(1)), int(match.group(2))
    if first < 1 or last < first:
        return None
    return (first, last)


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str) and item}


# --------------------------------------------------------------------------- #
# Crosswalk helpers
# --------------------------------------------------------------------------- #


def _validate_anchor_row(record: dict, index: int) -> None:
    anchor_id = str(record.get("anchor_id"))
    match = _ANCHOR_RE.fullmatch(anchor_id)
    if match is None:
        raise ValueError(
            f"anchor_id {anchor_id!r} at index {index} does not match "
            "<dwelling|household|population>_<year>_orszagos_<NN>"
        )
    family, year_text, suffix_text = match.groups()
    if year_text != "1960":
        raise ValueError(f"anchor_id {anchor_id!r}: legacy initial year must be 1960")
    suffix = int(suffix_text)
    if not 0 <= suffix <= 20:
        raise ValueError(f"anchor_id {anchor_id!r}: region suffix must be 00..20")

    variable_id = record.get("variable_id")
    if not isinstance(variable_id, str) or variable_id not in ANCHOR_UNITS:
        raise ValueError(
            f"anchor_id {anchor_id!r}: unknown variable_id {variable_id!r}; "
            f"expected one of {sorted(ANCHOR_UNITS)}"
        )
    if variable_id != f"{family}_anchor":
        raise ValueError(
            f"anchor_id {anchor_id!r}: family {family!r} contradicts variable_id {variable_id!r}"
        )

    classification = record.get("classification")
    if not isinstance(classification, str) or classification not in ANCHOR_CLASSIFICATIONS:
        raise ValueError(
            f"anchor_id {anchor_id!r} at index {index} has invalid classification "
            f"{classification!r}; expected one of {sorted(ANCHOR_CLASSIFICATIONS)}"
        )

    if not isinstance(record.get("path"), str) or not record["path"]:
        raise ValueError(
            f"anchor_id {anchor_id!r} at index {index} is missing path; "
            "per-row path must be preserved per plan §5"
        )
    if record.get("runtime_connected") is not False:
        raise ValueError(
            f"anchor_id {anchor_id!r}: runtime_connected must be false in a declaration-only "
            "crosswalk"
        )

    unit = record.get("unit")
    expected_unit = ANCHOR_UNITS[variable_id]
    if unit != expected_unit:
        raise ValueError(
            f"anchor_id {anchor_id!r}: unit {unit!r} does not match {expected_unit!r}"
        )
    source_kind = record.get("source_evidence_kind")
    if not isinstance(source_kind, str) or source_kind not in SOURCE_EVIDENCE_KINDS:
        raise ValueError(
            f"anchor_id {anchor_id!r}: invalid source_evidence_kind {source_kind!r}"
        )
    for field in ("source_boundary_basis", "desired_boundary_basis"):
        if not _usable_identifier(record.get(field)):
            raise ValueError(f"anchor_id {anchor_id!r}: missing {field}")

    if classification != "blocked" and classification != source_kind:
        raise ValueError(
            f"anchor_id {anchor_id!r}: classification {classification!r} contradicts "
            f"source_evidence_kind {source_kind!r}"
        )

    missing_evidence = record.get("missing_evidence")
    if classification == "blocked":
        if not _usable_identifier(missing_evidence):
            raise ValueError(
                f"anchor_id {anchor_id!r}: blocked rows must state missing_evidence"
            )
    elif classification in {"proxy", "synthetic"}:
        transformation = record.get("transformation")
        if not _usable_identifier(transformation):
            raise ValueError(
                f"anchor_id {anchor_id!r}: {classification} rows need a transformation"
            )
        if _usable_identifier(missing_evidence):
            raise ValueError(
                f"anchor_id {anchor_id!r}: {classification} rows cannot retain unresolved "
                "missing_evidence"
            )
        if "1957" not in record["source_boundary_basis"]:
            raise ValueError(
                f"anchor_id {anchor_id!r}: {classification} rows must state the 1957 "
                "limitation in source_boundary_basis"
            )
    elif classification == "reconstructed":
        transformation = record.get("transformation")
        if not _usable_identifier(transformation):
            raise ValueError(
                f"anchor_id {anchor_id!r}: reconstructed rows need a transformation"
            )
        if not record.get("supporting_anchor_ids"):
            raise ValueError(
                f"anchor_id {anchor_id!r}: reconstructed rows need supporting_anchor_ids"
            )
        if _usable_identifier(missing_evidence):
            raise ValueError(
                f"anchor_id {anchor_id!r}: reconstructed rows cannot retain unresolved "
                "missing_evidence"
            )
    elif classification == "direct":
        if _usable_identifier(missing_evidence):
            raise ValueError(
                f"anchor_id {anchor_id!r}: direct rows cannot retain missing_evidence"
            )

    observation_at = record.get("observation_at")
    if source_kind == "proxy" and observation_at == "1960-01-01" and classification == "direct":
        raise ValueError(
            f"anchor_id {anchor_id!r}: legacy_initial_at=1960-01-01 "
            "with source_evidence_kind=proxy cannot be classified as direct for 1957 target"
        )

    geographic = record.get("geographic_scope")
    if suffix == 0:
        if geographic != "national":
            raise ValueError(
                f"anchor_id {anchor_id!r} is the national (00) entry but "
                f"geographic_scope={geographic!r}; must be 'national'"
            )
    elif geographic != f"region_{suffix:02d}":
        raise ValueError(
            f"anchor_id {anchor_id!r}: geographic_scope must be 'region_{suffix:02d}', "
            f"got {geographic!r}"
        )


def _validate_anchor_bijection(records: list[dict], legacy_artifacts: list[dict]) -> None:
    by_id: dict[str, dict] = {}
    for artifact in legacy_artifacts:
        artifact_id = artifact.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ValueError("legacy artifact is missing artifact_id")
        if artifact_id in by_id:
            raise ValueError(f"legacy manifest repeats artifact_id {artifact_id!r}")
        by_id[artifact_id] = artifact

    covered: dict[str, str] = {}
    for record in records:
        anchor_id = str(record.get("anchor_id"))
        artifact_id = record.get("legacy_artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ValueError(
                f"anchor_id {anchor_id!r}: missing legacy_artifact_id; the crosswalk must "
                "state the legacy artifact it covers"
            )
        if artifact_id in covered:
            raise ValueError(
                f"legacy_artifact_id {artifact_id!r} is covered by both "
                f"{covered[artifact_id]!r} and {anchor_id!r}"
            )
        artifact = by_id.get(artifact_id)
        if artifact is None:
            raise ValueError(
                f"anchor_id {anchor_id!r}: legacy_artifact_id {artifact_id!r} "
                "is not a role=initial_state artifact"
            )
        covered[artifact_id] = anchor_id
        _check_artifact_match(record, artifact)

    missing = sorted(set(by_id) - set(covered))
    if missing:
        raise ValueError(f"crosswalk does not cover legacy artifacts: {missing}")


def _check_artifact_match(record: dict, artifact: dict) -> None:
    anchor_id = str(record.get("anchor_id"))
    if artifact.get("role") != "initial_state":
        raise ValueError(f"artifact {artifact.get('artifact_id')!r} is not role=initial_state")

    artifact_id = str(artifact.get("artifact_id", ""))
    match = re.fullmatch(
        r"p05_census2011_(dwelling|household|population)_(\d{2})(?:_(.+))?", artifact_id
    )
    if match is None:
        raise ValueError(f"legacy artifact_id {artifact_id!r} has an unknown identity shape")
    family, suffix_text, region = match.groups()
    suffix = int(suffix_text)
    if artifact.get("variable_id") != f"{family}_anchor":
        raise ValueError(
            f"legacy artifact {artifact_id!r} variable_id does not match its family"
        )

    expected_anchor_id = f"{family}_1960_orszagos_{suffix:02d}"
    expected_scope = "national" if suffix == 0 else f"region_{suffix:02d}"
    if record.get("anchor_id") != expected_anchor_id:
        raise ValueError(
            f"anchor_id {anchor_id!r} does not match legacy artifact identity "
            f"{expected_anchor_id!r}"
        )
    if record.get("geographic_scope") != expected_scope:
        raise ValueError(
            f"anchor_id {anchor_id!r}: geographic_scope {record.get('geographic_scope')!r} "
            f"does not match legacy artifact identity {expected_scope!r}"
        )
    if suffix == 0 and region != "orszagos":
        raise ValueError(f"legacy artifact {artifact_id!r}: national artifact must be orszagos")
    if suffix != 0 and not region:
        raise ValueError(f"legacy artifact {artifact_id!r}: regional artifact lacks a region")

    evidence_status = artifact.get("evidence_status")
    if not isinstance(evidence_status, str):
        raise ValueError(
            f"legacy artifact {artifact_id!r}: evidence_status must be a string"
        )
    expected_kind = {
        "literature_proxy": "proxy",
        "proxy": "proxy",
        "direct": "direct",
        "reconstructed": "reconstructed",
        "synthetic": "synthetic",
    }.get(evidence_status)
    if expected_kind is None:
        raise ValueError(
            f"legacy artifact {artifact_id!r}: unsupported evidence_status {evidence_status!r}"
        )
    if record.get("source_evidence_kind") != expected_kind:
        raise ValueError(
            f"anchor_id {anchor_id!r}: source_evidence_kind {record.get('source_evidence_kind')!r} "
            f"does not match legacy evidence_status {evidence_status!r} ({expected_kind!r})"
        )

    checks = {
        "variable_id": artifact.get("variable_id"),
        "source_id": artifact.get("source_id"),
        "source_sha256": artifact.get("sha256"),
        "path": artifact.get("path"),
        "legacy_grade": artifact.get("grade"),
        "legacy_evidence_status": evidence_status,
        "observation_at": artifact.get("observation_at"),
        "legacy_initial_at": artifact.get("initial_at"),
    }
    for field, expected in checks.items():
        if record.get(field) != expected:
            raise ValueError(
                f"anchor_id {anchor_id!r}: {field} {record.get(field)!r} does not match "
                f"legacy artifact value {expected!r}"
            )

    if record.get("classification") == "direct":
        if (
            artifact.get("observation_at") != TARGET_INITIAL_AT
            or artifact.get("initial_at") != TARGET_INITIAL_AT
        ):
            raise ValueError(
                f"anchor_id {anchor_id!r}: direct classification requires a 1957-01-01 "
                "observation and initial date"
            )
        if expected_kind != "direct":
            raise ValueError(
                f"anchor_id {anchor_id!r}: direct classification contradicts "
                f"evidence_status {evidence_status!r}"
            )


def _coverage_ok(
    authorities: list[dict],
    events: list[dict],
    admitted_by_id: dict[str, dict],
    approved_evidence_by_source: dict[str, list[dict]],
) -> tuple[bool, list[str]]:
    if not authorities:
        return False, ["authority coverage is empty"]
    events_by_id = {
        event.get("event_id"): event
        for event in events
        if isinstance(event.get("event_id"), str) and event.get("event_id")
    }
    reasons: list[str] = []
    for index, authority in enumerate(authorities):
        label = authority.get("authority", f"authority[{index}]")
        if not _usable_identifier(authority.get("authority")):
            reasons.append(f"authority[{index}] has no named institution/authority")
        period = authority.get("period")
        if not _usable_identifier(period):
            reasons.append(f"authority[{index}] has no institutional period")
        elif _date_bounds(period) is None:
            reasons.append(f"authority[{index}] period is not a recognized date or range")
        if authority.get("status") not in {"covered", "verified"}:
            reasons.append(f"authority {label!r} has unverified status")
        required = authority.get("required_primary_ids")
        implementation = authority.get("implementation_evidence_ids")
        if not isinstance(required, list) or not required:
            reasons.append(f"authority {label!r} has no required_primary_ids")
            continue
        if not isinstance(implementation, list) or not implementation:
            reasons.append(f"authority {label!r} has no implementation_evidence_ids")
            implementation = []
        if not set(implementation).isdisjoint(set(required)):
            reasons.append(
                f"authority {label!r} overlaps primary and implementation evidence"
            )
        for event_id in set(required) | set(implementation):
            event = events_by_id.get(event_id)
            if event is None:
                reasons.append(f"authority {label!r} references unknown event {event_id!r}")
            elif not _event_ready(
                event,
                admitted_by_id,
                approved_evidence_by_source,
                events_by_id,
            ):
                reasons.append(f"authority {label!r} event {event_id!r} is not verified")
    return not reasons, reasons


def _events_ok(
    events: list[dict],
    admitted_by_id: dict[str, dict],
    approved_evidence_by_source: dict[str, list[dict]],
) -> tuple[bool, list[str]]:
    if not events:
        return False, ["event candidates are empty"]
    events_by_id = {
        event.get("event_id"): event
        for event in events
        if isinstance(event.get("event_id"), str) and event.get("event_id")
    }
    reasons = [
        f"event {event.get('event_id')!r} is not verified"
        for event in events
        if not _event_ready(
            event,
            admitted_by_id,
            approved_evidence_by_source,
            events_by_id,
        )
    ]
    return not reasons, reasons


def _event_ready(
    event: dict,
    admitted_by_id: dict[str, dict],
    approved_evidence_by_source: dict[str, list[dict]],
    events_by_id: dict[str, dict],
) -> bool:
    if event.get("status") != "verified":
        return False
    if not _date_matches_precision(event.get("date"), event.get("date_precision")):
        return False
    if not _usable_identifier(event.get("document_number")) and not _usable_identifier(
        event.get("archival_reference")
    ):
        return False
    for field in ("issuer", "legal_force", "reviewer", "source_id", "source_sha256"):
        if not _usable_identifier(event.get(field)):
            return False
    granted = event.get("authority_granted")
    if not isinstance(granted, list) or not granted:
        return False
    if not all(_usable_identifier(item) for item in granted):
        return False
    implementation_id = event.get("implementation_evidence_id")
    if not _usable_identifier(implementation_id):
        return False
    if implementation_id == event.get("event_id") or implementation_id not in events_by_id:
        return False
    observed = _date_bounds(event.get("observed_implementation_at"))
    if observed is None:
        return False

    rights_status, rights_reasons = _rights_reasons(event.get("rights"))
    if rights_status not in {"verified", "restricted"} or rights_reasons:
        return False

    source = admitted_by_id.get(event.get("source_id"))
    if source is None:
        return False
    if event.get("source_sha256") != source.get("source_sha256"):
        return False
    page = event.get("pdf_page")
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        return False
    page_count = source.get("pdf_pages")
    if not isinstance(page_count, int) or page > page_count:
        return False
    bounds = _page_range(source.get("pdf_page_range"))
    if bounds is None or not bounds[0] <= page <= bounds[1]:
        return False

    evidence = approved_evidence_by_source.get(event["source_id"], [])
    return any(
        page in item["pages"]
        and item["window"][0] <= observed[0]
        and observed[1] <= item["window"][1]
        for item in evidence
    )


# --------------------------------------------------------------------------- #
# CLI entry point
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    repo_root = Path(".")
    if "--root" in sys.argv:
        index = sys.argv.index("--root")
        if index + 1 < len(sys.argv):
            repo_root = Path(sys.argv[index + 1])

    result = audit_h1a(repo_root)
    json.dump(result, sys.stdout, indent=2)
    sys.exit(result["exit_code"])
