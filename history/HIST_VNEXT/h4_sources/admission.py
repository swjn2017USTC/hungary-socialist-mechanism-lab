"""
H4A-0 — statistical-publication admission, 63-anchor audit, and D08–D10 crosswalk.

The module is deliberately offline and metadata-first:

* ``evaluate_statistical_candidate`` judges one declared table/value candidate.
* ``validate_h4_crosswalk`` checks the 63 legacy anchors, the new anchor
  crosswalk, and the measurement crosswalk without touching runtime state.
* ``audit_h4a0`` reads the declared H4A-0 package and reports structural,
  admission, and historical verdicts separately.

It does not read PDF page images, run OCR, upload files, or write to the source
packages.  ``--verify-files`` only streams bytes for SHA-256 checks against the
declared source/transcript paths.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from hsm_lab.data.schemas import RightsSpec
from hsm_lab.evidence.schemas import DataRole

SCHEMA_VERSION = "hist_vnext_h4a0_v1"
TARGET_INITIAL_AT = "1957-01-01"

CLASSIFICATIONS = {"direct", "reconstructed", "proxy", "synthetic", "blocked"}
ADMISSION_STATUSES = {"candidate", "admitted", "blocked"}
EVIDENCE_KINDS = {
    "statistical_observation",
    "reconstruction",
    "experiment_assumption",
    "secondary_context",
}
MEASUREMENT_STATUSES = {"exact", "proxy", "no_counterpart", "blocked"}
DATE_PRECISIONS = {"day", "month", "year", "unknown"}
PUBLICATION_BASES = {
    "table_header",
    "table_footnote",
    "explicit_reconstruction",
}
DATA_ROLE_PURPOSE = {
    DataRole.RECONSTRUCTED_INITIAL.value: {"initial_state"},
    DataRole.TARGET.value: {"measurement"},
    DataRole.CANDIDATE_LINKAGE.value: {
        "definition_review",
        "secondary_context",
        "internal_validation_background",
    },
}
SOURCE_TYPES = {
    "historical_official_statistics_scan_user_supplied",
    "secondary_analysis",
}

REQUIRED_CANDIDATE_FIELDS = (
    "candidate_id",
    "source_id",
    "source_sha256",
    "source_path",
    "pdf_page",
    "printed_page",
    "printed_page_status",
    "table",
    "row",
    "column",
    "source_variable",
    "unit",
    "reference_date",
    "reference_period",
    "date_precision",
    "reference_date_basis",
    "publication_at",
    "publication_precision",
    "available_at",
    "edition",
    "geographic_scope",
    "source_regions",
    "model_regions",
    "boundary_mapping",
    "coverage",
    "price_basis",
    "population_basis",
    "sector_scope",
    "import_scope",
    "aggregation",
    "footnotes",
    "uncertainty",
    "classification",
    "admission_status",
    "runtime_connected",
    "evidence_kind",
    "data_role",
    "allowed_uses",
    "rights",
    "rights_evidence_ref",
    "access_approval_ref",
    "work_id",
    "observation_ids",
    "cited_observation_ids",
    "verified_by",
    "verification_record_ref",
    "evidence_grade",
    "missing_fields",
    "block_reasons",
)

# Fields that may legitimately be null/empty for a metadata-only candidate.
NULLABLE_CANDIDATE_FIELDS = {
    "printed_page",
    "reference_date",
    "reference_period",
    "available_at",
    "model_regions",
    "source_regions",
    "boundary_mapping",
    "population_basis",
    "price_basis",
    "sector_scope",
    "import_scope",
    "value_ref",
    "verification_record_ref",
    "uncertainty",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _index_sources(evidence_index: dict) -> dict[str, dict]:
    sources = evidence_index.get("sources", {})
    if isinstance(sources, list):
        return {item["source_id"]: item for item in sources}
    if isinstance(sources, dict):
        return sources
    raise ValueError("evidence_index.sources must be a list or mapping")


def _page_is_hold(source: dict, page: int) -> bool:
    return page in set(source.get("hold_pages", []))


def _reference_years(record: dict) -> set[str]:
    years: set[str] = set()
    reference_date = record.get("reference_date")
    if reference_date:
        years.add(str(reference_date)[:4])
    period = record.get("reference_period")
    if isinstance(period, dict):
        start = str(period.get("start", ""))[:4]
        end = str(period.get("end", ""))[:4]
        if start.isdigit() and end.isdigit() and int(start) <= int(end):
            years.update(str(year) for year in range(int(start), int(end) + 1))
        else:
            for key in ("start", "end"):
                value = period.get(key)
                if value:
                    years.add(str(value)[:4])
    return years


def _reference_endpoint_years(record: dict) -> set[str]:
    years: set[str] = set()
    reference_date = record.get("reference_date")
    if reference_date:
        years.add(str(reference_date)[:4])
    period = record.get("reference_period")
    if isinstance(period, dict):
        for key in ("start", "end"):
            value = period.get(key)
            if value:
                years.add(str(value)[:4])
    return years


def _approved_hold(record: dict, access: dict | None, source: dict) -> bool:
    """A HOLD approval must match source, SHA, page, purpose, use and scope."""
    if access is None:
        return False
    approvals = access.get("hold_approvals", [])
    required = (
        "approver",
        "approved_at",
        "approval_ref",
        "allowed_purpose",
        "allowed_years",
        "allowed_uses",
        "allowed_table",
    )
    for approval in approvals:
        if not isinstance(approval, dict) or any(not approval.get(key) for key in required):
            continue
        if approval.get("source_sha256") != record.get("source_sha256"):
            continue
        if approval.get("source_sha256") != source.get("source_sha256"):
            continue
        if approval.get("source_id") != record.get("source_id"):
            continue
        if approval.get("pdf_page") != record.get("pdf_page"):
            continue
        if approval.get("allowed_purpose") != record.get("purpose"):
            continue
        if str(record.get("access_approval_ref")) != str(approval.get("approval_ref")):
            continue
        years = {str(year) for year in approval.get("allowed_years", [])}
        if not _reference_years(record).issubset(years):
            continue
        approved_uses = set(approval.get("allowed_uses", []))
        if not set(record.get("allowed_uses", [])).issubset(approved_uses):
            continue
        if approval.get("allowed_table") != record.get("table"):
            continue
        allowed_rows = set(approval.get("allowed_rows", []))
        allowed_columns = set(approval.get("allowed_columns", []))
        if not allowed_rows and not allowed_columns:
            continue
        if allowed_rows and record.get("row") not in allowed_rows:
            continue
        if allowed_columns and record.get("column") not in allowed_columns:
            continue
        return True
    return False


def _check_rights(record: dict, access: dict | None, reasons: list[str]) -> None:
    try:
        rights = RightsSpec.model_validate(record.get("rights"))
    except Exception as error:  # pydantic ConfigError is not a ValueError subclass
        reasons.append(f"invalid rights: {error}")
        return
    if rights.license_status == "unknown":
        reasons.append("rights license_status=unknown: no value-use admission")
    if access is None:
        reasons.append("no access-register entry")
        return
    value_use = access.get("value_use", {})
    if not value_use.get("allowed", False):
        reasons.append("access register does not approve numerical value use")
    approved_uses = set(value_use.get("allowed_uses", []))
    requested = set(record.get("allowed_uses", []))
    missing = sorted(requested - approved_uses)
    if missing:
        reasons.append(f"access register does not approve uses {missing}")
    if not record.get("rights_evidence_ref"):
        reasons.append("missing rights_evidence_ref")
    if not record.get("access_approval_ref"):
        reasons.append("missing access_approval_ref")


def _check_date_fields(record: dict, reasons: list[str]) -> None:
    reference_date = record.get("reference_date")
    reference_period = record.get("reference_period")
    if reference_date and reference_period:
        reasons.append("both reference_date and reference_period set")
    if not reference_date and not reference_period:
        reasons.append("missing reference_date/reference_period")
    if reference_date:
        try:
            date.fromisoformat(reference_date)
        except (TypeError, ValueError):
            reasons.append(f"invalid reference_date: {reference_date!r}")
    if reference_period:
        if not isinstance(reference_period, dict):
            reasons.append("reference_period must be an object")
        else:
            start = reference_period.get("start")
            end = reference_period.get("end")
            try:
                date.fromisoformat(start)
                date.fromisoformat(end)
            except (TypeError, ValueError):
                reasons.append("reference_period start/end must be ISO dates")
    basis = record.get("reference_date_basis")
    if basis not in PUBLICATION_BASES:
        reasons.append(f"reference_date_basis must be one of {sorted(PUBLICATION_BASES)}")
    publication = str(record.get("publication_at") or "")
    if publication and publication in str(reference_date or ""):
        reasons.append("publication_at used as reference_date")
    precision = record.get("date_precision")
    if precision not in DATE_PRECISIONS:
        reasons.append(f"date_precision must be one of {sorted(DATE_PRECISIONS)}")


def _check_role(record: dict, reasons: list[str]) -> None:
    role = record.get("data_role")
    purpose = record.get("purpose")
    if role not in DATA_ROLE_PURPOSE:
        reasons.append(f"data_role not allowed in H4A-0: {role!r}")
        return
    if purpose not in DATA_ROLE_PURPOSE[role]:
        reasons.append(f"purpose {purpose!r} not allowed for data_role {role!r}")
    uses = set(record.get("allowed_uses", []))
    allowed_uses = set(DATA_ROLE_PURPOSE[role])
    if not uses.issubset(allowed_uses):
        reasons.append(f"allowed_uses {sorted(uses - allowed_uses)} are not permitted for {role!r}")
    if role == DataRole.TARGET.value and {"forcing", "actor"} & uses:
        reasons.append("target data_role cannot be used as forcing/actor")
    if purpose in {"forcing", "actor"}:
        reasons.append("purpose forcing/actor is forbidden for H4A-0")


def _check_evidence_semantics(record: dict, source: dict, reasons: list[str]) -> None:
    kind = record.get("evidence_kind")
    if kind not in EVIDENCE_KINDS:
        reasons.append(f"evidence_kind not allowed: {kind!r}")
    if kind == "secondary_context" and source.get("source_type") != "secondary_analysis":
        reasons.append("secondary_context requires a secondary_analysis source")
    if kind == "reconstruction" and record.get("classification") not in {"reconstructed", "proxy"}:
        reasons.append("evidence_kind=reconstruction requires reconstructed/proxy classification")
    if kind == "experiment_assumption":
        if record.get("classification") != "synthetic":
            reasons.append("experiment_assumption requires synthetic classification")
        if record.get("source_id") is not None:
            reasons.append("experiment_assumption cannot claim a real source_id")
    if record.get("historical_authority_status") != "not_verified_by_this_record":
        reasons.append("historical_authority_status must be not_verified_by_this_record")
    if record.get("model_rule_status") != "not_defined_in_h4a0":
        reasons.append("model_rule_status must be not_defined_in_h4a0")
    if record.get("runtime_connected") is not False:
        reasons.append("runtime_connected must be false")


def _check_anti_shortcuts(record: dict, reasons: list[str]) -> None:
    text = " ".join(
        str(record.get(key, ""))
        for key in ("source_variable", "unit", "coverage", "population_basis")
    ).lower()
    if (
        "sample" in text
        and ("household" in text or "háztartás" in text)
        and record.get("geographic_scope") == "national"
    ):
        reasons.append("sample household count cannot stand in for a national household total")
    classification = record.get("classification")
    if classification == "direct":
        period = record.get("reference_period")
        period_start = period.get("start", "") if isinstance(period, dict) else ""
        reference = record.get("reference_date") or period_start
        year = str(reference)[:4]
        if record.get("data_role") == DataRole.RECONSTRUCTED_INITIAL.value and year in {
            "1960",
            "1972",
        }:
            reasons.append(f"{year} observation cannot be direct for the 1957 initial state")
    if classification == "direct" and "flow" in str(record.get("aggregation", "")).lower():
        if record.get("data_role") == DataRole.RECONSTRUCTED_INITIAL.value:
            reasons.append("annual flow cannot be a direct initial stock")


def evaluate_statistical_candidate(
    record: dict,
    *,
    evidence_index: dict,
    access_register: dict,
) -> dict:
    """Evaluate one statistical candidate.

    Returns ``{"status", "reasons", "structural_errors"}``.  ``structural_errors``
    are contradictions that make the declaration itself invalid (exit 2);
    ``reasons`` are evidence/authorisation gaps (exit 1).
    """
    reasons: list[str] = []
    errors: list[str] = []
    hold_blocked = False

    for field in REQUIRED_CANDIDATE_FIELDS:
        if field not in record:
            errors.append(f"missing required field: {field}")

    candidate_id = record.get("candidate_id")
    source_id = record.get("source_id")
    sources = _index_sources(evidence_index)
    source = sources.get(source_id)
    if source is None:
        errors.append(f"unknown source_id: {source_id!r}")
        source = {}

    if record.get("source_sha256") != source.get("source_sha256"):
        errors.append("candidate source_sha256 does not match the source register")
    if record.get("source_path") != source.get("local_path"):
        errors.append("candidate source_path does not match the source register")
    if source.get("source_type") not in SOURCE_TYPES:
        errors.append(f"source_type not registered for H4A-0: {source.get('source_type')!r}")

    page = record.get("pdf_page")
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        errors.append(f"pdf_page must be a positive integer, got {page!r}")
    else:
        pdf_pages = source.get("pdf_pages")
        if isinstance(pdf_pages, int) and page > pdf_pages:
            errors.append(f"pdf_page {page} outside registered range 1-{pdf_pages}")
        page_index = set(source.get("page_index", []))
        if page_index and page not in page_index:
            errors.append(f"pdf_page {page} not present in the registered page index")
        if _page_is_hold(source, page):
            access = (access_register.get("sources") or {}).get(source_id)
            if not _approved_hold(record, access, source):
                hold_blocked = True
                reasons.append(f"pdf_page {page} is HOLD and has no matching narrow approval")

    printed_status = record.get("printed_page_status")
    if printed_status not in {"verified", "unknown"}:
        errors.append("printed_page_status must be 'verified' or 'unknown'")
    elif printed_status == "verified" and not record.get("printed_page"):
        errors.append("printed_page_status=verified requires printed_page")

    classification = record.get("classification")
    if classification not in CLASSIFICATIONS:
        errors.append(f"invalid classification: {classification!r}")
    declared = record.get("admission_status")
    if declared not in ADMISSION_STATUSES:
        errors.append(f"invalid admission_status: {declared!r}")

    _check_date_fields(record, reasons)
    _check_role(record, reasons)
    _check_evidence_semantics(record, source, reasons)
    _check_anti_shortcuts(record, reasons)
    _check_rights(record, (access_register.get("sources") or {}).get(source_id), reasons)

    if source.get("source_type") == "secondary_analysis":
        if (
            record.get("data_role") != DataRole.CANDIDATE_LINKAGE.value
            or record.get("purpose") != "secondary_context"
            or record.get("evidence_kind") != "secondary_context"
        ):
            reasons.append("secondary_analysis is contextual only and cannot be a numerical input")
        else:
            reasons.append("secondary_analysis: contextual only, not a primary statistical source")

    # Missing evidence fields are gaps, not silent zeros.
    for field in (
        "unit",
        "reference_date",
        "reference_period",
        "date_precision",
        "geographic_scope",
    ):
        if record.get(field) in (None, "", [], {}):
            if field in NULLABLE_CANDIDATE_FIELDS and record.get(field) is None:
                continue
            reasons.append(f"missing evidence: {field}")
    if (
        record.get("geographic_scope") == "national"
        and not record.get("population_basis")
        and "population" in str(record.get("source_variable", "")).lower()
    ):
        reasons.append("national population candidate lacks population_basis")
    if record.get("geographic_scope") and record.get("geographic_scope") != "national":
        boundary = str(record.get("boundary_mapping") or "")
        if not record.get("model_regions"):
            reasons.append("regional candidate has no model_regions")
        if (
            not boundary
            or boundary in {"unknown", "none"}
            or boundary.startswith("not_established")
        ):
            reasons.append("regional candidate has no verified boundary mapping")

    source_years = {str(year) for year in record.get("source_year_columns", [])}
    if source_years:
        reference_years = _reference_endpoint_years(record)
        outside = reference_years - source_years
        if outside:
            reasons.append(f"reference years {sorted(outside)} are outside source_year_columns")

    # A 1957 initial state accepts 1957 observations, or an explicitly justified
    # end-1956 stock carried across the calendar boundary.  Later years are never
    # direct 1957 observations.
    if (
        record.get("data_role") == DataRole.RECONSTRUCTED_INITIAL.value
        and record.get("purpose") == "initial_state"
    ):
        reference_date = record.get("reference_date")
        aggregation = str(record.get("aggregation") or "")
        transformation = str(record.get("transformation") or "")
        if record.get("classification") == "direct":
            if reference_date != TARGET_INITIAL_AT:
                reasons.append("direct initial state must be observed at 1957-01-01")
            if "flow" in aggregation:
                reasons.append("annual flow cannot be a direct initial stock")
        elif record.get("classification") == "reconstructed":
            if aggregation != "end_of_period_stock":
                reasons.append("reconstructed initial state must be an end-of-period stock")
            if reference_date == "1956-12-31":
                if "carried_to_1957-01-01" not in transformation:
                    reasons.append("end-1956 stock needs an explicit 1957 opening-boundary carry")
            elif reference_date != TARGET_INITIAL_AT:
                reasons.append("reconstructed initial state must target 1957-01-01")
        else:
            reasons.append("initial-state classification must be direct or reconstructed")

    role = record.get("data_role")
    purpose = record.get("purpose")
    numerical_role = role in {DataRole.RECONSTRUCTED_INITIAL.value, DataRole.TARGET.value} and (
        purpose in {"initial_state", "measurement"}
    )
    definition_only = role == DataRole.CANDIDATE_LINKAGE.value
    value_ref = record.get("value_ref")
    if value_ref is not None and not isinstance(value_ref, dict):
        errors.append("value_ref must be an object")
        value_ref = None
    if numerical_role:
        for field in ("table", "row", "column"):
            if not record.get(field):
                reasons.append(f"numerical candidate missing source locator: {field}")
        if value_ref is None:
            reasons.append("numerical candidate has no value_ref")
        else:
            for key in ("path", "sha256", "field_locator"):
                if not value_ref.get(key):
                    errors.append(f"value_ref missing {key}")
                elif not isinstance(value_ref.get(key), str):
                    errors.append(f"value_ref.{key} must be a string")
            if isinstance(value_ref.get("sha256"), str) and len(value_ref["sha256"]) != 64:
                errors.append("value_ref.sha256 must be 64 hex characters")
        if not record.get("verified_by") or not record.get("verification_record_ref"):
            reasons.append("numerical candidate lacks a verification record")
    elif definition_only and value_ref is not None:
        reasons.append("definition-only candidate cannot carry a numerical value_ref")

    missing_fields = record.get("missing_fields")
    block_reasons = record.get("block_reasons")
    if missing_fields and not isinstance(missing_fields, list):
        errors.append("missing_fields must be a list")
    elif missing_fields:
        reasons.append(f"unresolved missing fields: {missing_fields}")
    if block_reasons and not isinstance(block_reasons, list):
        errors.append("block_reasons must be a list")
    elif block_reasons:
        reasons.append(f"unresolved block reasons: {block_reasons}")

    if declared == "admitted" and (errors or reasons):
        errors.append("declared admitted but admission gates do not pass")
    if record.get("runtime_connected") is not False:
        errors.append("runtime_connected must be false")

    if errors:
        status = "blocked"
    elif classification == "blocked":
        status = "blocked"
    elif hold_blocked:
        status = "blocked"
    elif reasons:
        status = "candidate"
    else:
        status = "admitted"

    return {
        "candidate_id": candidate_id,
        "status": status,
        "reasons": reasons,
        "structural_errors": errors,
    }


def _shared_pairs(records: list[dict]) -> list[dict]:
    """Pairwise root detection, including direct observation-ID intersection."""
    known_roots: set[str] = set()
    for record in records:
        known_roots.update(record.get("observation_ids", []))
    results: list[dict] = []
    for index, left in enumerate(records):
        for right in records[index + 1 :]:
            left_obs = set(left.get("observation_ids", []))
            right_obs = set(right.get("observation_ids", []))
            left_cited = set(left.get("cited_observation_ids", []))
            right_cited = set(right.get("cited_observation_ids", []))
            shared = (left_obs & right_obs) | (left_cited & right_obs)
            shared |= (left_obs & right_cited) | (left_cited & right_cited)
            cited = left_cited | right_cited
            unknown_cited = cited - known_roots
            same_work = bool(left.get("work_id")) and left.get("work_id") == right.get("work_id")
            if shared:
                if shared & unknown_cited or shared - known_roots:
                    independent: bool | None = None
                else:
                    independent = False
            elif same_work:
                independent = False
            elif not (left_obs or left_cited) or not (right_obs or right_cited):
                independent = None
            elif unknown_cited or not known_roots:
                independent = None
            else:
                independent = True
            results.append(
                {
                    "record_ids": [left.get("candidate_id"), right.get("candidate_id")],
                    "work_ids": [left.get("work_id"), right.get("work_id")],
                    "shared_work_ids": ([left.get("work_id")] if same_work else []),
                    "shared_observation_ids": sorted(shared),
                    "unknown_observation_ids": sorted(unknown_cited),
                    "independent": independent,
                }
            )
    return results


def validate_shared_observations(
    shared_records: list[dict],
    *,
    candidates: list[dict] | None = None,
    observation_groups: list[dict] | None = None,
) -> None:
    """Reject false independence and incomplete shared-root declarations."""
    candidate_by_id = {item.get("candidate_id"): item for item in (candidates or [])}
    for entry in shared_records:
        shared = set(entry.get("shared_observation_ids", []))
        unknown = set(entry.get("unknown_observation_ids", []))
        same_work = bool(entry.get("shared_work_ids"))
        if entry.get("independent") is True and (shared or same_work or unknown):
            raise ValueError(
                "shared observation declared independent: "
                f"{entry.get('record_ids')} roots={sorted(shared | unknown)}"
            )

    if candidates is not None:
        declared = {frozenset(entry.get("record_ids", [])): entry for entry in shared_records}
        for computed in _shared_pairs(candidates):
            key = frozenset(computed["record_ids"])
            if computed["independent"] is False:
                entry = declared.get(key)
                if entry is None or entry.get("independent") is not False:
                    raise ValueError(f"undeclared shared root for candidate pair {sorted(key)}")
            if computed["independent"] is None:
                entry = declared.get(key)
                if entry is not None and entry.get("independent") is True:
                    raise ValueError(f"unknown root declared independent for {sorted(key)}")

    for group in observation_groups or []:
        if not isinstance(group, dict):
            raise ValueError("observation group must be an object")
        group_candidates = group.get("candidate_ids", [])
        if not isinstance(group_candidates, list):
            raise ValueError("observation group candidate_ids must be a list")
        roots = set(group.get("observation_ids", []))
        for candidate_id in group_candidates:
            candidate = candidate_by_id.get(candidate_id)
            if candidate is None:
                raise ValueError(f"observation group references unknown candidate {candidate_id!r}")
            if not roots.intersection(
                set(candidate.get("observation_ids", []))
                | set(candidate.get("cited_observation_ids", []))
            ):
                raise ValueError(f"observation group root not carried by {candidate_id!r}")
        if len(group_candidates) > 1 and group.get("independent_observations") != 1:
            raise ValueError(
                f"observation group {group.get('group_id')!r} "
                "must declare one independent observation"
            )


def validate_h4_crosswalk(
    records: list[dict],
    *,
    legacy_records: list[dict],
    candidates: list[dict],
) -> None:
    """Validate exact 63-anchor coverage and candidate-role boundaries."""
    legacy_ids = [item.get("anchor_id") for item in legacy_records]
    if len(legacy_ids) != 63:
        raise ValueError(f"legacy crosswalk must contain 63 anchors, got {len(legacy_ids)}")
    if len(set(legacy_ids)) != len(legacy_ids):
        raise ValueError("legacy crosswalk contains duplicate anchor_id values")
    authoritative = {item.get("anchor_id"): item for item in legacy_records}

    candidate_ids = [item.get("candidate_id") for item in candidates]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("duplicate candidate_id in candidate overlay")
    candidate_by_id = {item.get("candidate_id"): item for item in candidates}

    seen: set[str] = set()
    for index, record in enumerate(records):
        anchor_id = record.get("anchor_id")
        if not anchor_id:
            raise ValueError(f"anchor record at index {index} has no anchor_id")
        if anchor_id in seen:
            raise ValueError(f"duplicate anchor_id: {anchor_id!r}")
        seen.add(anchor_id)
        legacy = record.get("legacy_record") or {}
        if legacy.get("anchor_id") != anchor_id:
            raise ValueError(f"{anchor_id}: legacy_record.anchor_id does not match")
        if legacy != authoritative.get(anchor_id):
            raise ValueError(f"{anchor_id}: legacy_record is not the authoritative snapshot")
        if record.get("verified_source_sha256") != authoritative[anchor_id].get("source_sha256"):
            raise ValueError(f"{anchor_id}: verified_source_sha256 is not the legacy source hash")
        if record.get("h4_classification") not in CLASSIFICATIONS:
            raise ValueError(f"{anchor_id}: invalid h4_classification")
        if record.get("admission_status") not in ADMISSION_STATUSES:
            raise ValueError(f"{anchor_id}: invalid admission_status")
        if record.get("runtime_connected") is not False:
            raise ValueError(f"{anchor_id}: runtime_connected must be false")
        linked = record.get("candidate_ids", [])
        if not isinstance(linked, list):
            raise ValueError(f"{anchor_id}: candidate_ids must be a list")
        for candidate_id in linked:
            if candidate_id not in candidate_ids:
                raise ValueError(f"{anchor_id}: unknown candidate_id {candidate_id!r}")
        if (
            legacy.get("classification") == "blocked"
            and record.get("h4_classification") == "direct"
            and not record.get("candidate_ids")
        ):
            raise ValueError(
                f"{anchor_id}: legacy blocked anchor cannot become direct without a candidate"
            )
        if (
            record.get("h4_classification") == "direct"
            or record.get("admission_status") == "admitted"
        ):
            eligible = [
                candidate_by_id[candidate_id]
                for candidate_id in record.get("candidate_ids", [])
                if candidate_by_id[candidate_id].get("data_role")
                == DataRole.RECONSTRUCTED_INITIAL.value
                and candidate_by_id[candidate_id].get("purpose") == "initial_state"
                and candidate_by_id[candidate_id].get("admission_status") == "admitted"
                and candidate_by_id[candidate_id].get("classification")
                in {"direct", "reconstructed"}
            ]
            if not eligible:
                raise ValueError(
                    f"{anchor_id}: admitted/direct anchor needs an admitted initial-state candidate"
                )
        if legacy.get("source_sha256") and record.get("verified_source_sha256") not in (
            None,
            legacy.get("source_sha256"),
        ):
            raise ValueError(f"{anchor_id}: source hash differs from the legacy snapshot")

    if seen != set(legacy_ids):
        missing = sorted(set(legacy_ids) - seen)
        extra = sorted(seen - set(legacy_ids))
        raise ValueError(f"anchor coverage mismatch; missing={missing} extra={extra}")


def validate_measurement_crosswalk(records: list[dict], *, candidate_ids: set[str]) -> None:
    ids: set[str] = set()
    for record in records:
        mapping_id = record.get("mapping_id")
        if not mapping_id:
            raise ValueError("measurement record missing mapping_id")
        if mapping_id in ids:
            raise ValueError(f"duplicate mapping_id: {mapping_id!r}")
        ids.add(mapping_id)
        if record.get("mapping_status") not in MEASUREMENT_STATUSES:
            raise ValueError(f"{mapping_id}: invalid mapping_status")
        if record.get("runtime_connected") is not False:
            raise ValueError(f"{mapping_id}: runtime_connected must be false")
        if record.get("model_metric") is None and record.get("mapping_status") != "no_counterpart":
            raise ValueError(f"{mapping_id}: null model_metric requires no_counterpart")
        linked = record.get("candidate_ids", [])
        if not isinstance(linked, list):
            raise ValueError(f"{mapping_id}: candidate_ids must be a list")
        for candidate_id in linked:
            if candidate_id not in candidate_ids:
                raise ValueError(f"{mapping_id}: unknown candidate_id {candidate_id!r}")
        role = record.get("data_role")
        if role not in DATA_ROLE_PURPOSE:
            raise ValueError(f"{mapping_id}: data_role not allowed: {role!r}")
        if role == DataRole.TARGET.value and record.get("purpose") != "measurement":
            raise ValueError(f"{mapping_id}: target role requires measurement purpose")
        if (
            role == DataRole.TARGET.value
            and record.get("allowed_uses")
            and set(record["allowed_uses"]) & {"forcing", "actor"}
        ):
            raise ValueError(f"{mapping_id}: target cannot be forcing/actor")


def _load_package(root: Path) -> dict:
    base = root / "history/HIST_VNEXT/h4_sources"
    return {
        "sources": _load_json(base / "sources.json"),
        "access": _load_json(base / "access_register.json"),
        "shared": _load_json(base / "shared_observations.json"),
        "candidates": _load_json(
            root / "config/initial_state/hist_vnext_h4_v1/candidate_overlay.json"
        ),
        "anchors": _load_json(root / "config/initial_state/hist_vnext_h4_v1/anchor_crosswalk.json"),
        "measurement": _load_json(
            root / "config/initial_state/hist_vnext_h4_v1/measurement_crosswalk.json"
        ),
        "approved": _load_json(root / "docs/phases/HIST_VNEXT/H4A-0/APPROVED_INPUT_SET.json"),
        "legacy_anchors": _load_json(
            root / "config/initial_state/hist_vnext_v1/anchor_crosswalk.json"
        ),
    }


def _record_list(payload: Any, key: str, label: str, errors: list[str]) -> list[dict]:
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return []
    value = payload.get(key, [])
    if not isinstance(value, list):
        errors.append(f"{label}.{key} must be a list")
        return []
    records = [item for item in value if isinstance(item, dict)]
    if len(records) != len(value):
        errors.append(f"{label}.{key} contains non-object entries")
    return records


def _validate_source_register(root: Path, sources: list[dict], errors: list[str]) -> None:
    """Bind the declared sources to the intake manifests and page index."""
    seen: set[str] = set()
    for source in sources:
        source_id = source.get("source_id")
        if not source_id or source_id in seen:
            errors.append(f"invalid or duplicate source_id: {source_id!r}")
            continue
        seen.add(source_id)
        if source.get("source_type") not in SOURCE_TYPES:
            errors.append(f"source {source_id}: invalid source_type")
        digest = str(source.get("source_sha256", ""))
        if len(digest) != 64:
            errors.append(f"source {source_id}: source_sha256 must be 64 hex characters")

    matched: set[str] = set()
    has_secondary = any(item.get("source_type") == "secondary_analysis" for item in sources)
    has_statistics = any(
        item.get("source_type") == "historical_official_statistics_scan_user_supplied"
        for item in sources
    )

    batch1 = root / "data/private/hist_vnext_sources/batch01_20261016/manifest.json"
    if has_secondary and not batch1.is_file():
        errors.append("batch01 manifest is required for secondary_analysis sources")
    if batch1.is_file():
        manifest = json.loads(batch1.read_text(encoding="utf-8"))
        by_sha = {doc.get("sha256"): doc for doc in manifest.get("documents", [])}
        candidate_path = root / "history/HIST_VNEXT/sources/batch01_candidates.json"
        candidate_ids: dict[str, str] = {}
        if candidate_path.is_file():
            payload = json.loads(candidate_path.read_text(encoding="utf-8"))
            candidate_ids = {
                item.get("source_sha256"): item.get("source_id")
                for item in payload.get("records", [])
            }
        for source in sources:
            doc = by_sha.get(source.get("source_sha256"))
            if doc is None:
                continue
            matched.add(source.get("source_id"))
            if candidate_ids.get(source.get("source_sha256")) != source.get("source_id"):
                errors.append(
                    f"source {source.get('source_id')}: source_id not bound to batch01 candidates"
                )
            if doc.get("pdf_pages") != source.get("pdf_pages"):
                errors.append(
                    f"source {source.get('source_id')}: pdf_pages differs from batch01 manifest"
                )
            expected_path = "data/private/hist_vnext_sources/batch01_20261016/" + str(
                doc.get("original_relative_path", "")
            )
            if source.get("local_path") != expected_path:
                errors.append(
                    f"source {source.get('source_id')}: path is not the canonical batch01 path"
                )
            if source.get("source_type") != "secondary_analysis":
                errors.append(
                    f"source {source.get('source_id')}: "
                    "batch01 source_type must be secondary_analysis"
                )

    batch2 = root / "data/private/hist_vnext_sources/batch02_20261020/manifest.json"
    page_index = root / "data/private/hist_vnext_sources/batch02_20261020/page_index.csv"
    if has_statistics and not batch2.is_file():
        errors.append("batch02 manifest is required for statistical yearbook sources")
    if has_statistics and not page_index.is_file():
        errors.append("batch02 page_index.csv is required for statistical yearbook sources")
    if batch2.is_file():
        manifest = json.loads(batch2.read_text(encoding="utf-8"))
        by_sha = {book.get("sha256"): book for book in manifest.get("books", [])}
        page_rows: list[dict] = []
        if page_index.is_file():
            import csv

            with page_index.open(encoding="utf-8", newline="") as handle:
                page_rows = list(csv.DictReader(handle))
        rows_by_year: dict[str, list[dict]] = {}
        for row in page_rows:
            rows_by_year.setdefault(str(row.get("yearbook")), []).append(row)
        for source in sources:
            book = by_sha.get(source.get("source_sha256"))
            if book is None:
                continue
            matched.add(source.get("source_id"))
            if book.get("source_id") != source.get("source_id"):
                errors.append(
                    f"source {source.get('source_id')}: source_id differs from batch02 manifest"
                )
            if book.get("pdf_pages") != source.get("pdf_pages"):
                errors.append(
                    f"source {source.get('source_id')}: pdf_pages differs from batch02 manifest"
                )
            expected_path = "data/private/hist_vnext_sources/batch02_20261020/" + str(
                book.get("original_relative_path", "")
            )
            if source.get("local_path") != expected_path:
                errors.append(
                    f"source {source.get('source_id')}: path is not the canonical batch02 path"
                )
            if source.get("source_type") != "historical_official_statistics_scan_user_supplied":
                errors.append(
                    f"source {source.get('source_id')}: batch02 source_type differs from manifest"
                )
            year = str(book.get("year_label"))
            expected_pages = {int(row["pdf_page"]) for row in rows_by_year.get(year, [])}
            expected_holds = {
                int(row["pdf_page"])
                for row in rows_by_year.get(year, [])
                if row.get("routing_status") == "YEAR_HINT_HOLD_NO_DEFAULT_READ"
            }
            if set(source.get("page_index", [])) != expected_pages:
                errors.append(
                    f"source {source.get('source_id')}: page_index differs from page_index.csv"
                )
            if set(source.get("hold_pages", [])) != expected_holds:
                errors.append(
                    f"source {source.get('source_id')}: hold_pages differs from page_index.csv"
                )

    for source in sources:
        if source.get("source_id") not in matched:
            errors.append(
                f"source {source.get('source_id')}: not present in an authoritative intake manifest"
            )


def _validate_anchor_manifests(root: Path, legacy_records: list[dict], errors: list[str]) -> None:
    manifests: dict[str, dict] = {}
    for name in ("DATA_MANIFEST_v1.json", "DATA_MANIFEST_v2.json"):
        path = root / "data/manifests" / name
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        by_path = {
            item.get("path"): item
            for item in payload.get("artifacts", [])
            if item.get("role") == "initial_state"
        }
        manifests[name] = by_path
    for legacy in legacy_records:
        path = legacy.get("path")
        for name, by_path in manifests.items():
            artifact = by_path.get(path)
            if artifact is None:
                errors.append(f"{legacy.get('anchor_id')}: path absent from {name}")
                continue
            if artifact.get("declared_sha256") != legacy.get("source_sha256"):
                errors.append(f"{legacy.get('anchor_id')}: hash differs from {name}")
            if artifact.get("observation_at") != legacy.get("observation_at"):
                errors.append(f"{legacy.get('anchor_id')}: observation_at differs from {name}")


def audit_h4a0(root: Path, *, verify_files: bool = False) -> dict:
    """Audit the declared H4A-0 package.

    Exit codes:
      0 — structure valid and every declared candidate passed its gate;
      1 — structure valid but candidates/blocked items remain;
      2 — structural contradiction, identity/hash error, or forged admission.
    """
    root = Path(root)
    details: list[str] = []
    errors: list[str] = []

    try:
        package = _load_package(root)
    except (OSError, json.JSONDecodeError) as error:
        return {
            "exit_code": 2,
            "structural": "BLOCKED",
            "historical": "UNIDENTIFIED",
            "summary": {},
            "details": [f"package load error: {error}"],
        }

    source_payload = package["sources"]
    sources = _record_list(source_payload, "sources", "sources.json", errors)
    source_by_id = {item.get("source_id"): item for item in sources}
    if len(source_by_id) != len(sources):
        errors.append("duplicate source_id in sources.json")
    if not isinstance(source_payload, dict) or source_payload.get("declaration_only") is not True:
        errors.append("sources.json declaration_only must be true")
    if not isinstance(source_payload, dict) or source_payload.get("runtime_connected") is not False:
        errors.append("sources.json runtime_connected must be false")

    _validate_source_register(root, sources, errors)

    access = package["access"]
    access_by_id = access.get("sources", {}) if isinstance(access, dict) else {}
    if not isinstance(access, dict) or not isinstance(access_by_id, dict):
        errors.append("access_register.json.sources must be an object")
        access_by_id = {}
    for source_id in source_by_id:
        if source_id not in access_by_id:
            errors.append(f"source {source_id} has no access-register entry")

    candidate_payload = package["candidates"]
    candidates = _record_list(candidate_payload, "records", "candidate_overlay.json", errors)
    if (
        not isinstance(candidate_payload, dict)
        or candidate_payload.get("declaration_only") is not True
    ):
        errors.append("candidate_overlay.json declaration_only must be true")
    if (
        not isinstance(candidate_payload, dict)
        or candidate_payload.get("runtime_connected") is not False
    ):
        errors.append("candidate_overlay.json runtime_connected must be false")
    if (
        not isinstance(candidate_payload, dict)
        or candidate_payload.get("target_initial_at") != TARGET_INITIAL_AT
    ):
        errors.append(f"target_initial_at must be {TARGET_INITIAL_AT}")

    evidence_index = {"sources": source_by_id}
    results: dict[str, dict] = {}
    for record in candidates:
        result = evaluate_statistical_candidate(
            record, evidence_index=evidence_index, access_register=access
        )
        results[result["candidate_id"]] = result
        errors.extend(result["structural_errors"])
        details.append(
            f"[{result['candidate_id']}] {result['status']}"
            + (f" reasons={result['reasons']}" if result["reasons"] else "")
            + (f" errors={result['structural_errors']}" if result["structural_errors"] else "")
        )

    # A declared value input must actually be admitted and match its set/role.
    approved = package["approved"]
    if not isinstance(approved, dict) or approved.get("schema_version") != SCHEMA_VERSION:
        errors.append("APPROVED_INPUT_SET.json schema_version mismatch")
    candidate_by_id = {item.get("candidate_id"): item for item in candidates}
    approved_ids: set[str] = set()
    approved_sets: dict[str, str] = {}
    set_role = {
        "initial_state_inputs": (DataRole.RECONSTRUCTED_INITIAL.value, "initial_state"),
        "measurement_inputs": (DataRole.TARGET.value, "measurement"),
    }
    if isinstance(approved, dict):
        for key in ("initial_state_inputs", "measurement_inputs", "assumption_inputs"):
            entries = approved.get(key, [])
            if not isinstance(entries, list):
                errors.append(f"APPROVED_INPUT_SET.{key} must be a list")
                continue
            for index, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    errors.append(f"APPROVED_INPUT_SET.{key}[{index}] must be an object")
                    continue
                candidate_id = entry.get("candidate_id")
                if not candidate_id:
                    errors.append(f"APPROVED_INPUT_SET.{key}[{index}] has no candidate_id")
                    continue
                if candidate_id in approved_ids:
                    errors.append(f"approved candidate {candidate_id!r} appears in multiple sets")
                    continue
                approved_ids.add(candidate_id)
                approved_sets[candidate_id] = key
                if candidate_id not in results or results[candidate_id]["status"] != "admitted":
                    errors.append(f"approved input {candidate_id!r} is not an admitted candidate")
                    continue
                candidate = candidate_by_id.get(candidate_id, {})
                role = entry.get("role")
                purpose = entry.get("purpose")
                for field in (
                    "source_id",
                    "source_sha256",
                    "pdf_page",
                    "verification_record_ref",
                    "rights_evidence_ref",
                    "access_approval_ref",
                ):
                    if entry.get(field) != candidate.get(field):
                        errors.append(
                            f"approved input {candidate_id!r} {field} does not match its candidate"
                        )
                approved_value_ref = entry.get("value_ref")
                candidate_value_ref = candidate.get("value_ref")
                if not isinstance(approved_value_ref, dict) or not isinstance(
                    candidate_value_ref, dict
                ):
                    errors.append(f"approved input {candidate_id!r} has no usable value_ref")
                else:
                    for field in ("path", "sha256", "field_locator"):
                        if approved_value_ref.get(field) != candidate_value_ref.get(field):
                            errors.append(
                                f"approved input {candidate_id!r} value_ref.{field} "
                                "does not match its candidate"
                            )
                if role != candidate.get("data_role"):
                    errors.append(
                        f"approved input {candidate_id!r} role does not match its candidate"
                    )
                if purpose != candidate.get("purpose"):
                    errors.append(
                        f"approved input {candidate_id!r} purpose does not match its candidate"
                    )
                if key in set_role and (role, purpose) != set_role[key]:
                    errors.append(f"approved input {candidate_id!r} has the wrong role for {key}")
                if key in {"initial_state_inputs", "measurement_inputs"} and not candidate.get(
                    "value_ref"
                ):
                    errors.append(f"approved numerical input {candidate_id!r} has no value_ref")
                if key == "assumption_inputs":
                    if candidate.get("evidence_kind") != "experiment_assumption":
                        errors.append(
                            f"assumption input {candidate_id!r} is not an experiment assumption"
                        )
                    if role != DataRole.CANDIDATE_LINKAGE.value:
                        errors.append(
                            f"assumption input {candidate_id!r} must be candidate_linkage"
                        )

    # Candidates that declare admitted must be in the matching approved set.
    for candidate_id, candidate in candidate_by_id.items():
        if candidate.get("admission_status") != "admitted":
            continue
        key = approved_sets.get(candidate_id)
        expected_key = (
            "initial_state_inputs"
            if candidate.get("data_role") == DataRole.RECONSTRUCTED_INITIAL.value
            else "measurement_inputs"
            if candidate.get("data_role") == DataRole.TARGET.value
            else None
        )
        if key is None:
            errors.append(
                f"candidate {candidate_id!r} declares admitted "
                "but is absent from APPROVED_INPUT_SET"
            )
        elif expected_key and key != expected_key:
            errors.append(f"candidate {candidate_id!r} is approved in the wrong input set")

    legacy_records = _record_list(
        package["legacy_anchors"], "records", "legacy anchor_crosswalk.json", errors
    )
    anchor_records = _record_list(
        package["anchors"], "records", "H4A-0 anchor_crosswalk.json", errors
    )
    measurement_records = _record_list(
        package["measurement"], "records", "measurement_crosswalk.json", errors
    )
    shared_payload = package["shared"]
    shared_records = _record_list(shared_payload, "records", "shared_observations.json", errors)
    observation_groups = (
        shared_payload.get("observation_groups", []) if isinstance(shared_payload, dict) else []
    )
    if not isinstance(observation_groups, list):
        errors.append("shared_observations.json.observation_groups must be a list")
        observation_groups = []

    try:
        validate_h4_crosswalk(
            anchor_records,
            legacy_records=legacy_records,
            candidates=candidates,
        )
    except ValueError as error:
        errors.append(f"anchor crosswalk: {error}")

    try:
        _validate_anchor_manifests(root, legacy_records, errors)
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"artifact manifest load error: {error}")

    try:
        validate_measurement_crosswalk(measurement_records, candidate_ids=set(results))
    except ValueError as error:
        errors.append(f"measurement crosswalk: {error}")

    try:
        validate_shared_observations(
            shared_records,
            candidates=candidates,
            observation_groups=observation_groups,
        )
    except ValueError as error:
        errors.append(f"shared observations: {error}")

    computed_shared = _shared_pairs(candidates)
    non_independent = sum(1 for item in computed_shared if item["independent"] is False)
    details.append(
        "shared-observation pairs from candidates: "
        f"{len(computed_shared)}, non-independent: {non_independent}"
    )

    if verify_files:
        for source_id, source in source_by_id.items():
            relative = source.get("local_path")
            if not isinstance(relative, str) or not relative:
                errors.append(f"source local_path is not a path string: {source_id}")
                continue
            path = root / relative
            if not path.is_file():
                errors.append(f"source file missing: {source_id} {path}")
                continue
            digest = _sha256_file(path)
            if digest != source.get("source_sha256"):
                errors.append(f"source hash mismatch: {source_id} {digest}")
        for record in candidates:
            value_ref = record.get("value_ref")
            if not isinstance(value_ref, dict):
                if value_ref is not None:
                    errors.append(f"value_ref is not an object: {record.get('candidate_id')}")
                continue
            relative = value_ref.get("path")
            if not isinstance(relative, str) or not relative:
                errors.append(f"value_ref.path is not a path string: {record.get('candidate_id')}")
                continue
            path = root / relative
            if not path.is_file():
                errors.append(f"value_ref missing file: {record.get('candidate_id')} {path}")
                continue
            digest = _sha256_file(path)
            if digest != value_ref.get("sha256"):
                errors.append(f"value_ref hash mismatch: {record.get('candidate_id')} {digest}")
        for legacy in legacy_records:
            if not legacy.get("path"):
                continue
            path = root / str(legacy.get("path", ""))
            if not path.is_file():
                errors.append(f"anchor file missing: {legacy.get('anchor_id')} {path}")
                continue
            digest = _sha256_file(path)
            if digest != legacy.get("source_sha256"):
                errors.append(f"anchor hash mismatch: {legacy.get('anchor_id')} {digest}")

    statuses = {
        status: sum(1 for result in results.values() if result["status"] == status)
        for status in ("admitted", "candidate", "blocked")
    }
    summary = {
        "sources": len(sources),
        "candidates": len(candidates),
        "candidate_status": statuses,
        "anchor_records": len(anchor_records),
        "measurement_records": len(measurement_records),
        "approved_inputs": len(approved_ids),
        "shared_non_independent_pairs": non_independent,
    }

    if errors:
        exit_code = 2
        structural = "BLOCKED"
    elif statuses["admitted"] != len(candidates):
        exit_code = 1
        structural = "PASS"
    else:
        exit_code = 0
        structural = "PASS"

    historical = "UNIDENTIFIED" if exit_code != 0 else "NOT_ESTABLISHED"
    if errors:
        details = errors + details

    return {
        "exit_code": exit_code,
        "structural": structural,
        "historical": historical,
        "summary": summary,
        "details": details,
    }


if __name__ == "__main__":
    repo_root = Path(".")
    if "--root" in sys.argv:
        index = sys.argv.index("--root")
        if index + 1 < len(sys.argv):
            repo_root = Path(sys.argv[index + 1])
    result = audit_h4a0(repo_root, verify_files="--verify-files" in sys.argv)
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.exit(result["exit_code"])
