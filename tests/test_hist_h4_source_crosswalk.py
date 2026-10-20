"""H4A-0 statistical admission and crosswalk behavioral contracts.

The tests exercise admission, boundary, and role invariants.  The fixture is a
software contract example, not a historical claim.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

import history.HIST_VNEXT.h4_sources.admission as h4_admission
from history.HIST_VNEXT.h4_sources.admission import (
    SCHEMA_VERSION,
    audit_h4a0,
    evaluate_statistical_candidate,
    validate_h4_crosswalk,
    validate_measurement_crosswalk,
    validate_shared_observations,
)

SHA = "a" * 64


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _minimal_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 200] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode())
    payload.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(payload)


def _base_source() -> dict:
    return {
        "source_id": "FIXTURE_STAT",
        "work_id": "FIXTURE_STAT",
        "source_type": "historical_official_statistics_scan_user_supplied",
        "local_path": "data/private/fixture/source.pdf",
        "source_sha256": SHA,
        "pdf_pages": 10,
        "page_index": list(range(1, 11)),
        "hold_pages": [5],
    }


def _base_candidate() -> dict:
    return {
        "candidate_id": "fixture_candidate",
        "source_id": "FIXTURE_STAT",
        "source_sha256": SHA,
        "source_path": "data/private/fixture/source.pdf",
        "pdf_page": 1,
        "printed_page": "1",
        "printed_page_status": "verified",
        "table": "fixture table",
        "row": "total",
        "column": "1957",
        "source_variable": "population",
        "unit": "persons",
        "reference_date": "1957-01-01",
        "reference_period": None,
        "date_precision": "day",
        "reference_date_basis": "table_header",
        "publication_at": "1958",
        "publication_precision": "year",
        "available_at": None,
        "edition": "fixture",
        "geographic_scope": "national",
        "source_regions": ["fixture"],
        "model_regions": ["national"],
        "boundary_mapping": "national_total_matches_model_national",
        "coverage": "fixture population",
        "price_basis": None,
        "population_basis": "de facto present population",
        "sector_scope": None,
        "import_scope": None,
        "aggregation": "point_in_time",
        "footnotes": [],
        "uncertainty": "fixture",
        "classification": "direct",
        "admission_status": "candidate",
        "runtime_connected": False,
        "evidence_kind": "statistical_observation",
        "data_role": "reconstructed_initial",
        "purpose": "initial_state",
        "allowed_uses": ["initial_state"],
        "rights": {
            "license_status": "verified",
            "license_name": "fixture licence",
            "terms_locator": "fixture://terms",
            "evidence_quote": "fixture only",
            "checked_at": "2026-10-20T00:00:00Z",
            "download_allowed": True,
            "redistribution_allowed": False,
        },
        "rights_evidence_ref": "fixture://rights",
        "access_approval_ref": "fixture://access",
        "work_id": "FIXTURE_STAT",
        "observation_ids": ["obs_fixture"],
        "cited_observation_ids": [],
        "verified_by": "fixture reviewer",
        "verification_record_ref": "fixture://review",
        "evidence_grade": "C",
        "missing_fields": [],
        "block_reasons": [],
        "historical_authority_status": "not_verified_by_this_record",
        "model_rule_status": "not_defined_in_h4a0",
        "value_ref": {
            "path": "data/private/fixture/value.md",
            "sha256": "b" * 64,
            "field_locator": "table=fixture table; row=total; column=1957",
        },
        "transformation": None,
        "source_year_columns": [1957],
    }


def _access(value_use: bool = True, hold_approval: dict | None = None) -> dict:
    entry = {
        "local_review": {"allowed": True},
        "value_use": {
            "allowed": value_use,
            "allowed_uses": ["initial_state"] if value_use else [],
        },
        "hold_approvals": [hold_approval] if hold_approval else [],
    }
    return {"sources": {"FIXTURE_STAT": entry}}


def _evidence(source: dict | None = None) -> dict:
    return {"sources": {((source or _base_source())["source_id"]): (source or _base_source())}}


def _evaluate(candidate: dict, *, access: dict | None = None, source: dict | None = None) -> dict:
    return evaluate_statistical_candidate(
        candidate,
        evidence_index=_evidence(source),
        access_register=access or _access(),
    )


def _write_goal_package(
    root: Path,
    *,
    candidate: dict,
    access: dict | None = None,
    approved_entries: list[dict] | None = None,
    source: dict | None = None,
) -> None:
    source = source or _base_source()
    source["local_path"] = (
        "data/private/hist_vnext_sources/batch02_20261020/yearbooks/1956/original/source.pdf"
    )
    source["pdf_pages"] = 1
    source["page_index"] = [1]
    source["hold_pages"] = []
    candidate["source_path"] = source["local_path"]
    candidate["pdf_page"] = 1
    source_file = root / source["local_path"]
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_bytes(_minimal_pdf("fixture table row total column 1957 value 42"))
    source_sha = hashlib.sha256(source_file.read_bytes()).hexdigest()
    source["source_sha256"] = source_sha
    candidate["source_sha256"] = source_sha
    manifest_dir = root / "data/private/hist_vnext_sources/batch02_20261020"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "manifest.json").write_text(
        json.dumps(
            {
                "books": [
                    {
                        "source_id": "FIXTURE_STAT",
                        "sha256": source_sha,
                        "pdf_pages": 1,
                        "year_label": 1956,
                        "original_relative_path": "yearbooks/1956/original/source.pdf",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (manifest_dir / "page_index.csv").write_text(
        "yearbook,pdf_page,routing_status\n1956,1,REVIEW_REQUIRED_NOT_ADMITTED\n",
        encoding="utf-8",
    )
    value_file = root / "data/private/fixture/value.md"
    value_file.parent.mkdir(parents=True, exist_ok=True)
    value_file.write_text(
        "# Synthetic software fixture\ntable=fixture table\nrow=total\ncolumn=1957\nvalue=42\n",
        encoding="utf-8",
    )
    if isinstance(candidate.get("value_ref"), dict):
        candidate["value_ref"]["sha256"] = hashlib.sha256(value_file.read_bytes()).hexdigest()
        for entry in approved_entries or []:
            if not isinstance(entry, dict) or entry.get("candidate_id") != candidate.get(
                "candidate_id"
            ):
                continue
            for field in (
                "source_id",
                "source_sha256",
                "pdf_page",
                "verification_record_ref",
                "rights_evidence_ref",
                "access_approval_ref",
            ):
                entry.setdefault(field, candidate.get(field))
            entry.setdefault("value_ref", dict(candidate["value_ref"]))

    legacy = [
        {
            "anchor_id": f"fixture_anchor_{index:02d}",
            "source_sha256": SHA,
            "classification": "blocked",
        }
        for index in range(63)
    ]
    legacy_payload = {"records": legacy}
    _write(root / "config/initial_state/hist_vnext_v1/anchor_crosswalk.json", legacy_payload)

    anchors = [
        {
            "anchor_id": item["anchor_id"],
            "legacy_record": item,
            "h4_classification": "blocked",
            "admission_status": "blocked",
            "runtime_connected": False,
            "candidate_ids": [],
            "verified_source_sha256": SHA,
        }
        for item in legacy
    ]
    _write(
        root / "config/initial_state/hist_vnext_h4_v1/anchor_crosswalk.json",
        {"records": anchors},
    )
    _write(
        root / "config/initial_state/hist_vnext_h4_v1/measurement_crosswalk.json",
        {"records": []},
    )
    _write(
        root / "config/initial_state/hist_vnext_h4_v1/candidate_overlay.json",
        {
            "schema_version": SCHEMA_VERSION,
            "declaration_only": True,
            "runtime_connected": False,
            "target_initial_at": "1957-01-01",
            "records": [candidate],
        },
    )
    _write(
        root / "history/HIST_VNEXT/h4_sources/sources.json",
        {
            "schema_version": SCHEMA_VERSION,
            "declaration_only": True,
            "runtime_connected": False,
            "sources": [source],
        },
    )
    _write(
        root / "history/HIST_VNEXT/h4_sources/access_register.json",
        access or _access(),
    )
    _write(
        root / "history/HIST_VNEXT/h4_sources/shared_observations.json",
        {"records": []},
    )
    _write(
        root / "docs/phases/HIST_VNEXT/H4A-0/APPROVED_INPUT_SET.json",
        {
            "schema_version": SCHEMA_VERSION,
            "initial_state_inputs": approved_entries or [],
            "measurement_inputs": [],
            "assumption_inputs": [],
        },
    )


# ---------------------------------------------------------------------------
# evaluate_statistical_candidate
# ---------------------------------------------------------------------------


def test_complete_statistical_candidate_is_admitted() -> None:
    result = _evaluate(_base_candidate())
    assert result["status"] == "admitted"
    assert result["reasons"] == []
    assert result["structural_errors"] == []


@pytest.mark.parametrize(
    "missing", ["unit", "reference_date", "date_precision", "geographic_scope"]
)
def test_missing_evidence_keeps_candidate_out_of_approved_set(missing: str) -> None:
    candidate = _base_candidate()
    candidate[missing] = None
    result = _evaluate(candidate)
    assert result["status"] != "admitted"


def test_unknown_rights_never_admits_even_if_access_register_allows() -> None:
    candidate = _base_candidate()
    candidate["rights"] = {"license_status": "unknown", "license_name": None}
    result = _evaluate(candidate)
    assert result["status"] == "candidate"
    assert any("unknown" in reason for reason in result["reasons"])


def test_hash_page_and_index_identity_errors_are_structural() -> None:
    candidate = _base_candidate()
    candidate["source_sha256"] = "b" * 64
    result = _evaluate(candidate)
    assert any("source_sha256" in error for error in result["structural_errors"])

    candidate = _base_candidate()
    candidate["pdf_page"] = 11
    result = _evaluate(candidate)
    assert any("outside registered range" in error for error in result["structural_errors"])

    candidate = _base_candidate()
    candidate["pdf_page"] = 0
    result = _evaluate(candidate)
    assert any("positive integer" in error for error in result["structural_errors"])

    source = _base_source()
    source["page_index"] = [2, 3]
    candidate = _base_candidate()
    result = _evaluate(candidate, source=source)
    assert any(
        "not present in the registered page index" in error for error in result["structural_errors"]
    )


def test_hold_page_without_matching_approval_is_blocked() -> None:
    candidate = _base_candidate()
    candidate["pdf_page"] = 5
    result = _evaluate(candidate)
    assert result["status"] == "blocked"
    assert any("HOLD" in reason for reason in result["reasons"])


def test_hold_page_with_matching_narrow_approval_can_pass() -> None:
    candidate = _base_candidate()
    candidate["pdf_page"] = 5
    approval = {
        "source_id": "FIXTURE_STAT",
        "source_sha256": SHA,
        "pdf_page": 5,
        "allowed_purpose": "initial_state",
        "allowed_uses": ["initial_state"],
        "allowed_years": [1957],
        "allowed_table": "fixture table",
        "allowed_rows": ["total"],
        "allowed_columns": ["1957"],
        "approver": "isolated reviewer",
        "approved_at": "2026-10-20",
        "approval_ref": "fixture://hold-approval",
    }
    candidate["access_approval_ref"] = "fixture://hold-approval"
    result = _evaluate(candidate, access=_access(hold_approval=approval))
    assert result["status"] == "admitted"


def test_sample_household_cannot_be_national_household_total() -> None:
    candidate = _base_candidate()
    candidate["source_variable"] = "sample household count"
    candidate["unit"] = "sample households"
    result = _evaluate(candidate)
    assert any("sample household" in reason for reason in result["reasons"])


@pytest.mark.parametrize("year", ["1960", "1972"])
def test_later_observation_cannot_be_direct_1957_initial(year: str) -> None:
    candidate = _base_candidate()
    candidate["reference_date"] = f"{year}-01-01"
    result = _evaluate(candidate)
    assert any("cannot be direct" in reason for reason in result["reasons"])


def test_target_cannot_be_forcing_or_actor() -> None:
    candidate = _base_candidate()
    candidate["data_role"] = "target"
    candidate["purpose"] = "measurement"
    candidate["allowed_uses"] = ["forcing"]
    result = _evaluate(candidate)
    assert any("forcing" in reason for reason in result["reasons"])


def test_publication_date_cannot_stand_in_for_reference_date() -> None:
    candidate = _base_candidate()
    candidate["reference_date"] = "1958-01-01"
    candidate["publication_at"] = "1958"
    result = _evaluate(candidate)
    assert any("publication_at" in reason for reason in result["reasons"])


def test_declared_admitted_with_a_gap_is_structural_error() -> None:
    candidate = _base_candidate()
    candidate["admission_status"] = "admitted"
    candidate["unit"] = None
    result = _evaluate(candidate)
    assert result["status"] == "blocked"
    assert any("declared admitted" in error for error in result["structural_errors"])


def test_runtime_connection_is_rejected() -> None:
    candidate = _base_candidate()
    candidate["runtime_connected"] = True
    result = _evaluate(candidate)
    assert any("runtime_connected" in error for error in result["structural_errors"])


def test_malformed_value_ref_is_structural_error() -> None:
    candidate = _base_candidate()
    candidate["value_ref"] = {"path": "x", "sha256": "short", "field_locator": "row 1"}
    result = _evaluate(candidate)
    assert any("value_ref.sha256" in error for error in result["structural_errors"])


@pytest.mark.parametrize(
    "field", ["value_ref", "verified_by", "verification_record_ref", "table", "row", "column"]
)
def test_numerical_candidate_needs_value_provenance_and_locators(field: str) -> None:
    candidate = _base_candidate()
    candidate[field] = None
    result = _evaluate(candidate)
    assert result["status"] != "admitted"
    assert any(
        "value_ref" in reason or "verification" in reason or field in reason
        for reason in result["reasons"]
    )


def test_declared_gaps_prevent_admission() -> None:
    candidate = _base_candidate()
    candidate["missing_fields"] = ["second_independent_transcription"]
    result = _evaluate(candidate)
    assert result["status"] != "admitted"

    candidate = _base_candidate()
    candidate["block_reasons"] = ["not verified"]
    result = _evaluate(candidate)
    assert result["status"] != "admitted"


def test_definition_only_candidate_cannot_carry_a_value_ref() -> None:
    candidate = _base_candidate()
    candidate["data_role"] = "candidate_linkage"
    candidate["purpose"] = "definition_review"
    candidate["allowed_uses"] = ["definition_review"]
    result = _evaluate(candidate)
    assert result["status"] != "admitted"
    assert any("definition-only" in reason for reason in result["reasons"])


@pytest.mark.parametrize("year", ["1959", "1987"])
def test_only_1957_or_justified_end_1956_initial_state_is_allowed(year: str) -> None:
    candidate = _base_candidate()
    candidate["reference_date"] = f"{year}-01-01"
    candidate["source_year_columns"] = [int(year)]
    result = _evaluate(candidate)
    assert any("direct initial state" in reason for reason in result["reasons"])


def test_regional_candidate_needs_evidence_not_only_model_region_names() -> None:
    candidate = _base_candidate()
    candidate["geographic_scope"] = "region_01"
    candidate["model_regions"] = ["region_01"]
    candidate["boundary_mapping"] = None
    result = _evaluate(candidate)
    assert any("boundary mapping" in reason for reason in result["reasons"])


def test_role_uses_must_be_subset_of_the_role() -> None:
    candidate = _base_candidate()
    candidate["allowed_uses"] = ["initial_state", "measurement", "forcing"]
    result = _evaluate(candidate)
    assert any("not permitted" in reason or "forcing" in reason for reason in result["reasons"])


def test_source_year_columns_must_contain_reference_year() -> None:
    candidate = _base_candidate()
    candidate["source_year_columns"] = [1960, 1966, 1967]
    result = _evaluate(candidate)
    assert any("outside source_year_columns" in reason for reason in result["reasons"])


def test_secondary_analysis_cannot_be_a_numerical_input() -> None:
    source = _base_source()
    source["source_type"] = "secondary_analysis"
    candidate = _base_candidate()
    result = _evaluate(candidate, source=source)
    assert result["status"] != "admitted"
    assert any("secondary_analysis" in reason for reason in result["reasons"])


def test_hold_page_without_approval_is_blocked_not_candidate() -> None:
    candidate = _base_candidate()
    candidate["pdf_page"] = 5
    result = _evaluate(candidate)
    assert result["status"] == "blocked"


def test_hold_approval_must_match_purpose_table_row_and_column() -> None:
    candidate = _base_candidate()
    candidate["pdf_page"] = 5
    candidate["access_approval_ref"] = "fixture://hold-approval"
    approval = {
        "source_id": "FIXTURE_STAT",
        "source_sha256": SHA,
        "pdf_page": 5,
        "allowed_purpose": "secondary_context",
        "allowed_uses": ["initial_state"],
        "allowed_years": [1957],
        "allowed_table": "fixture table",
        "allowed_rows": ["total"],
        "allowed_columns": ["1957"],
        "approver": "isolated reviewer",
        "approved_at": "2026-10-20",
        "approval_ref": "fixture://hold-approval",
    }
    result = _evaluate(candidate, access=_access(hold_approval=approval))
    assert result["status"] == "blocked"


def test_hold_approval_must_cover_the_whole_period() -> None:
    candidate = _base_candidate()
    candidate["pdf_page"] = 5
    candidate["access_approval_ref"] = "fixture://hold-approval"
    candidate["data_role"] = "candidate_linkage"
    candidate["purpose"] = "definition_review"
    candidate["allowed_uses"] = ["definition_review"]
    candidate["classification"] = "direct"
    candidate["value_ref"] = None
    candidate["verified_by"] = "fixture reviewer"
    candidate["verification_record_ref"] = "fixture://review"
    candidate["reference_date"] = None
    candidate["reference_period"] = {"start": "1957-01-01", "end": "1988-12-31"}
    candidate["source_year_columns"] = [1957, 1988]
    approval = {
        "source_id": "FIXTURE_STAT",
        "source_sha256": SHA,
        "pdf_page": 5,
        "allowed_purpose": "definition_review",
        "allowed_uses": ["definition_review"],
        "allowed_years": [1957],
        "allowed_table": "fixture table",
        "allowed_rows": ["total"],
        "allowed_columns": ["1957"],
        "approver": "isolated reviewer",
        "approved_at": "2026-10-20",
        "approval_ref": "fixture://hold-approval",
    }
    result = _evaluate(candidate, access=_access(hold_approval=approval))
    assert result["status"] == "blocked"


def test_initial_state_opening_boundary_is_exact() -> None:
    candidate = _base_candidate()
    candidate["reference_date"] = "1956-01-01"
    candidate["source_year_columns"] = [1956]
    candidate["transformation"] = "mentions 1957-01-01 but is not an end-1956 stock"
    result = _evaluate(candidate)
    assert any("direct initial state" in reason for reason in result["reasons"])

    candidate = _base_candidate()
    candidate["reference_date"] = "1957-12-31"
    result = _evaluate(candidate)
    assert any("direct initial state" in reason for reason in result["reasons"])

    candidate = _base_candidate()
    candidate["classification"] = "reconstructed"
    candidate["reference_date"] = None
    candidate["reference_period"] = {"start": "1957-01-01", "end": "1957-12-31"}
    candidate["aggregation"] = "annual_flow"
    result = _evaluate(candidate)
    assert any("end-of-period stock" in reason for reason in result["reasons"])


def test_commit_bound_candidate_text_has_no_thousands_separated_cell_values() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (root / "config/initial_state/hist_vnext_h4_v1/candidate_overlay.json").read_text()
    )

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)

    # Years, page numbers and hyphenated dates are allowed; grouped cell values are not.
    assert not any(re.search(r"\b\d{1,3}(?:[ ,]\d{3})+\b", item) for item in strings(payload))
    # Footnotes must be independently worded summaries, not verbatim Hungarian excerpts.
    hungarian = re.compile(r"[áéíóöőúüűÁÉÍÓÖŐÚÜŰ]")
    for candidate in payload["records"]:
        for footnote in candidate.get("footnotes", []):
            assert not hungarian.search(footnote)
    commit_bound = [
        *sorted((root / "docs/phases/HIST_VNEXT/H4A-0").glob("*.md")),
        *sorted((root / "config/initial_state/hist_vnext_h4_v1").glob("*.json")),
        *sorted((root / "history/HIST_VNEXT/h4_sources").glob("*.json")),
    ]
    for path in commit_bound:
        text = path.read_text()
        assert not re.search(r"Pécs\s+\d", text), path
        assert not re.search(r"value=\d", text), path


# ---------------------------------------------------------------------------
# Crosswalk and shared-observation invariants
# ---------------------------------------------------------------------------


def _legacy_anchors(count: int = 63) -> list[dict]:
    return [
        {"anchor_id": f"a_{index:02d}", "source_sha256": SHA, "classification": "blocked"}
        for index in range(count)
    ]


def _new_anchors(legacy: list[dict]) -> list[dict]:
    return [
        {
            "anchor_id": item["anchor_id"],
            "legacy_record": item,
            "h4_classification": "blocked",
            "admission_status": "blocked",
            "runtime_connected": False,
            "candidate_ids": [],
            "verified_source_sha256": SHA,
        }
        for item in legacy
    ]


def test_crosswalk_requires_exact_63_anchor_coverage() -> None:
    legacy = _legacy_anchors()
    records = _new_anchors(legacy)
    validate_h4_crosswalk(records, legacy_records=legacy, candidates=[])

    with pytest.raises(ValueError, match="coverage mismatch"):
        validate_h4_crosswalk(records[:-1], legacy_records=legacy, candidates=[])


def test_crosswalk_rejects_duplicate_and_unknown_candidate() -> None:
    legacy = _legacy_anchors()
    records = _new_anchors(legacy)
    records[1]["anchor_id"] = records[0]["anchor_id"]
    with pytest.raises(ValueError, match="duplicate anchor_id"):
        validate_h4_crosswalk(records, legacy_records=legacy, candidates=[])

    records = _new_anchors(legacy)
    records[0]["candidate_ids"] = ["forged"]
    with pytest.raises(ValueError, match="unknown candidate_id"):
        validate_h4_crosswalk(records, legacy_records=legacy, candidates=[])


def test_legacy_blocked_anchor_cannot_become_direct_without_candidate() -> None:
    legacy = _legacy_anchors()
    records = _new_anchors(legacy)
    records[0]["h4_classification"] = "direct"
    with pytest.raises(ValueError, match="cannot become direct"):
        validate_h4_crosswalk(records, legacy_records=legacy, candidates=[])


def test_anchor_promotion_requires_an_admitted_initial_candidate() -> None:
    legacy = _legacy_anchors()
    records = _new_anchors(legacy)
    records[0]["h4_classification"] = "direct"
    records[0]["admission_status"] = "admitted"
    records[0]["candidate_ids"] = ["blocked_target"]
    candidates = [
        {
            "candidate_id": "blocked_target",
            "data_role": "target",
            "purpose": "measurement",
            "admission_status": "blocked",
            "classification": "direct",
        }
    ]
    with pytest.raises(ValueError, match="admitted initial-state candidate"):
        validate_h4_crosswalk(records, legacy_records=legacy, candidates=candidates)


def test_forged_legacy_snapshot_and_hash_are_rejected() -> None:
    legacy = _legacy_anchors()
    records = _new_anchors(legacy)
    records[0]["legacy_record"] = dict(records[0]["legacy_record"], observation_at="1957-01-01")
    with pytest.raises(ValueError, match="authoritative snapshot"):
        validate_h4_crosswalk(records, legacy_records=legacy, candidates=[])

    records = _new_anchors(legacy)
    records[0]["verified_source_sha256"] = "forged"
    with pytest.raises(ValueError, match="verified_source_sha256"):
        validate_h4_crosswalk(records, legacy_records=legacy, candidates=[])


def test_direct_observation_intersection_is_not_independent() -> None:
    candidates = [
        {"candidate_id": "a", "observation_ids": ["root"], "cited_observation_ids": []},
        {"candidate_id": "b", "observation_ids": ["root"], "cited_observation_ids": []},
    ]
    with pytest.raises(ValueError, match="undeclared shared root"):
        validate_shared_observations([], candidates=candidates)
    validate_shared_observations(
        [
            {
                "record_ids": ["a", "b"],
                "shared_observation_ids": ["root"],
                "independent": False,
            }
        ],
        candidates=candidates,
    )


def test_same_work_with_distinct_observations_is_not_independent() -> None:
    candidates = [
        {"candidate_id": "a", "work_id": "W", "observation_ids": ["r1"]},
        {"candidate_id": "b", "work_id": "W", "observation_ids": ["r2"]},
    ]
    with pytest.raises(ValueError, match="undeclared shared root"):
        validate_shared_observations([], candidates=candidates)
    validate_shared_observations(
        [
            {
                "record_ids": ["a", "b"],
                "work_ids": ["W", "W"],
                "shared_work_ids": ["W"],
                "shared_observation_ids": [],
                "independent": False,
            }
        ],
        candidates=candidates,
    )


def test_unrooted_candidate_is_not_declared_independent() -> None:
    candidates = [
        {"candidate_id": "a", "work_id": "A", "observation_ids": ["r1"]},
        {"candidate_id": "b", "work_id": "B", "observation_ids": []},
    ]
    with pytest.raises(ValueError, match="declared independent"):
        validate_shared_observations(
            [{"record_ids": ["a", "b"], "shared_observation_ids": [], "independent": True}],
            candidates=candidates,
        )


def test_unknown_root_cannot_be_declared_independent() -> None:
    with pytest.raises(ValueError, match="declared independent"):
        validate_shared_observations(
            [
                {
                    "record_ids": ["a", "b"],
                    "shared_observation_ids": ["unknown-root"],
                    "unknown_observation_ids": ["unknown-root"],
                    "independent": True,
                }
            ]
        )


def test_measurement_mapping_requires_no_counterpart_for_null_metric() -> None:
    record = {
        "mapping_id": "m1",
        "mapping_status": "exact",
        "model_metric": None,
        "runtime_connected": False,
        "data_role": "candidate_linkage",
        "purpose": "definition_review",
    }
    with pytest.raises(ValueError, match="null model_metric"):
        validate_measurement_crosswalk([record], candidate_ids=set())


def test_measurement_target_cannot_be_forcing() -> None:
    record = {
        "mapping_id": "m1",
        "mapping_status": "exact",
        "model_metric": "x",
        "runtime_connected": False,
        "data_role": "target",
        "purpose": "measurement",
        "allowed_uses": ["forcing"],
    }
    with pytest.raises(ValueError, match="forcing"):
        validate_measurement_crosswalk([record], candidate_ids=set())


def test_known_shared_root_cannot_be_declared_independent() -> None:
    with pytest.raises(ValueError, match="declared independent"):
        validate_shared_observations(
            [
                {
                    "record_ids": ["a", "b"],
                    "shared_observation_ids": ["root"],
                    "independent": True,
                }
            ]
        )
    validate_shared_observations(
        [
            {
                "record_ids": ["a", "b"],
                "shared_observation_ids": ["root"],
                "independent": False,
            }
        ]
    )


# ---------------------------------------------------------------------------
# audit_h4a0 package behavior
# ---------------------------------------------------------------------------


def test_audit_accepts_complete_package_and_the_single_approved_input(tmp_path: Path) -> None:
    candidate = _base_candidate()
    candidate["admission_status"] = "admitted"
    _write_goal_package(
        tmp_path,
        candidate=candidate,
        approved_entries=[
            {
                "candidate_id": "fixture_candidate",
                "role": "reconstructed_initial",
                "purpose": "initial_state",
            }
        ],
    )
    result = audit_h4a0(tmp_path, verify_files=True)
    assert result["exit_code"] == 0
    assert result["structural"] == "PASS"


def test_audit_rejects_approved_but_not_admitted_candidate(tmp_path: Path) -> None:
    candidate = _base_candidate()
    candidate["unit"] = None
    _write_goal_package(
        tmp_path,
        candidate=candidate,
        approved_entries=[
            {
                "candidate_id": "fixture_candidate",
                "role": "reconstructed_initial",
                "purpose": "initial_state",
            }
        ],
    )
    result = audit_h4a0(tmp_path)
    assert result["exit_code"] == 2
    assert any("not an admitted candidate" in detail for detail in result["details"])


def test_audit_rejects_forged_admitted_declaration(tmp_path: Path) -> None:
    candidate = _base_candidate()
    candidate["admission_status"] = "admitted"
    candidate["unit"] = None
    _write_goal_package(tmp_path, candidate=candidate, approved_entries=[])
    result = audit_h4a0(tmp_path)
    assert result["exit_code"] == 2


def test_audit_verify_files_detects_source_hash_mismatch(tmp_path: Path) -> None:
    candidate = _base_candidate()
    candidate["admission_status"] = "admitted"
    _write_goal_package(
        tmp_path,
        candidate=candidate,
        approved_entries=[
            {
                "candidate_id": "fixture_candidate",
                "role": "reconstructed_initial",
                "purpose": "initial_state",
            }
        ],
    )
    (
        tmp_path
        / "data/private/hist_vnext_sources/batch02_20261020/yearbooks/1956/original/source.pdf"
    ).write_bytes(b"tampered")
    result = audit_h4a0(tmp_path, verify_files=True)
    assert result["exit_code"] == 2
    assert any("source hash mismatch" in detail for detail in result["details"])


def test_audit_rejects_cross_role_approved_entry(tmp_path: Path) -> None:
    candidate = _base_candidate()
    candidate["admission_status"] = "admitted"
    _write_goal_package(
        tmp_path,
        candidate=candidate,
        approved_entries=[
            {
                "candidate_id": "fixture_candidate",
                "role": "target",
                "purpose": "forcing",
            }
        ],
    )
    result = audit_h4a0(tmp_path)
    assert result["exit_code"] == 2


def test_audit_rejects_contradictory_approved_provenance(tmp_path: Path) -> None:
    candidate = _base_candidate()
    candidate["admission_status"] = "admitted"
    _write_goal_package(
        tmp_path,
        candidate=candidate,
        approved_entries=[
            {
                "candidate_id": "fixture_candidate",
                "role": "reconstructed_initial",
                "purpose": "initial_state",
                "source_id": "WRONG_SOURCE",
                "source_sha256": "0" * 64,
                "pdf_page": 999,
                "value_ref": {"path": "wrong", "sha256": "0" * 64, "field_locator": "wrong"},
            }
        ],
    )
    result = audit_h4a0(tmp_path)
    assert result["exit_code"] == 2
    assert any("does not match its candidate" in detail for detail in result["details"])


def test_audit_returns_structured_error_for_list_valued_value_path(tmp_path: Path) -> None:
    candidate = _base_candidate()
    candidate["value_ref"]["path"] = []
    _write_goal_package(tmp_path, candidate=candidate, approved_entries=[])
    result = audit_h4a0(tmp_path, verify_files=True)
    assert result["exit_code"] == 2
    assert result["structural"] == "BLOCKED"


def test_audit_returns_structured_error_for_null_measurement_candidate_ids(
    tmp_path: Path,
) -> None:
    candidate = _base_candidate()
    _write_goal_package(tmp_path, candidate=candidate, approved_entries=[])
    measurement_path = tmp_path / "config/initial_state/hist_vnext_h4_v1/measurement_crosswalk.json"
    measurement_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "mapping_id": "m1",
                        "mapping_status": "no_counterpart",
                        "model_metric": None,
                        "runtime_connected": False,
                        "data_role": "candidate_linkage",
                        "purpose": "definition_review",
                        "candidate_ids": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = audit_h4a0(tmp_path)
    assert result["exit_code"] == 2
    assert result["structural"] == "BLOCKED"


def test_audit_requires_intake_manifest_and_page_index(tmp_path: Path) -> None:
    candidate = _base_candidate()
    _write_goal_package(tmp_path, candidate=candidate, approved_entries=[])
    manifest_dir = tmp_path / "data/private/hist_vnext_sources/batch02_20261020"
    (manifest_dir / "manifest.json").unlink()
    (manifest_dir / "page_index.csv").unlink()
    result = audit_h4a0(tmp_path)
    assert result["exit_code"] == 2
    assert any("batch02 manifest is required" in detail for detail in result["details"])


def test_source_register_rejects_forged_batch01_id_and_noncanonical_path(
    tmp_path: Path,
) -> None:
    manifest_dir = tmp_path / "data/private/hist_vnext_sources/batch01_20261016"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "manifest.json").write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "sha256": "c" * 64,
                        "pdf_pages": 2,
                        "original_relative_path": "D01/original/source.pdf",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    candidates_path = tmp_path / "history/HIST_VNEXT/sources/batch01_candidates.json"
    candidates_path.parent.mkdir(parents=True)
    candidates_path.write_text(
        json.dumps({"records": [{"source_id": "REAL", "source_sha256": "c" * 64}]}),
        encoding="utf-8",
    )
    sources = [
        {
            "source_id": "FORGED_BATCH01",
            "source_sha256": "c" * 64,
            "pdf_pages": 2,
            "local_path": "elsewhere/D01/original/source.pdf",
            "source_type": "secondary_analysis",
        }
    ]
    errors: list[str] = []
    h4_admission._validate_source_register(tmp_path, sources, errors)
    assert any("source_id not bound" in error for error in errors)
    assert any("not the canonical batch01 path" in error for error in errors)


def test_audit_returns_structured_error_for_malformed_measurement_payload(tmp_path: Path) -> None:
    candidate = _base_candidate()
    _write_goal_package(tmp_path, candidate=candidate, approved_entries=[])
    (tmp_path / "config/initial_state/hist_vnext_h4_v1/measurement_crosswalk.json").write_text(
        "[]", encoding="utf-8"
    )
    result = audit_h4a0(tmp_path)
    assert result["exit_code"] == 2
    assert result["structural"] == "BLOCKED"


def test_audit_returns_structured_error_for_malformed_value_ref(tmp_path: Path) -> None:
    candidate = _base_candidate()
    candidate["value_ref"] = "malformed"
    _write_goal_package(tmp_path, candidate=candidate, approved_entries=[])
    result = audit_h4a0(tmp_path, verify_files=True)
    assert result["exit_code"] == 2
    assert result["structural"] == "BLOCKED"


def test_audit_rejects_source_substitution_against_the_manifest(tmp_path: Path) -> None:
    candidate = _base_candidate()
    _write_goal_package(tmp_path, candidate=candidate, approved_entries=[])
    sources_path = tmp_path / "history/HIST_VNEXT/h4_sources/sources.json"
    original_source = json.loads(sources_path.read_text())["sources"][0]
    manifest = {
        "books": [
            {
                "source_id": "FIXTURE_STAT",
                "sha256": original_source["source_sha256"],
                "pdf_pages": 10,
                "year_label": 1956,
                "original_relative_path": "yearbooks/1956/original/source.pdf",
            }
        ]
    }
    manifest_path = tmp_path / "data/private/hist_vnext_sources/batch02_20261020/manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    baselined = tmp_path / "BASELINE.md"
    baselined.write_text("substituted\n", encoding="utf-8")
    substituted_sha = hashlib.sha256(baselined.read_bytes()).hexdigest()
    sources = json.loads(sources_path.read_text())
    sources["sources"][0]["local_path"] = "BASELINE.md"
    sources["sources"][0]["source_sha256"] = substituted_sha
    sources_path.write_text(json.dumps(sources), encoding="utf-8")
    result = audit_h4a0(tmp_path, verify_files=True)
    assert result["exit_code"] == 2
    assert any(
        "not present in an authoritative intake manifest" in detail for detail in result["details"]
    )


def test_audit_returns_structured_error_for_malformed_approved_entry(tmp_path: Path) -> None:
    candidate = _base_candidate()
    _write_goal_package(tmp_path, candidate=candidate, approved_entries=[None])
    result = audit_h4a0(tmp_path)
    assert result["exit_code"] == 2
    assert result["structural"] == "BLOCKED"
    assert any("must be an object" in detail for detail in result["details"])


def test_real_repository_audit_is_structural_pass_with_gaps() -> None:
    root = Path(__file__).resolve().parents[1]
    result = audit_h4a0(root)
    assert result["structural"] == "PASS"
    assert result["exit_code"] == 1
    assert result["summary"]["anchor_records"] == 63
    assert result["summary"]["approved_inputs"] == 0
