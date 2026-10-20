"""
H1A source admission — behavioral contracts and negative examples.

The suite separates software contracts from historical claims.  The positive
fixtures are explicitly labelled software fixtures; they do not assert that a
real document exists or that a historical value was verified.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from hsm_lab.evidence.schemas import DataRole

REPO_ROOT = Path(__file__).resolve().parents[1]
PRIMARY_SHA = "f" * 64
EXCERPT_HASH = "ab" * 32
RIGHTS_VERIFIED = {
    "license_status": "verified",
    "license_name": "test licence",
    "terms_locator": "https://example.invalid/terms",
    "evidence_quote": "software fixture only",
    "checked_at": "2026-10-15T00:00:00Z",
    "download_allowed": True,
    "redistribution_allowed": False,
    "notes": "software fixture; not a real rights determination",
}


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _run_cli(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "history.HIST_VNEXT.sources.admission",
            "--root",
            str(root),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _manifest_artifact(family: str, index: int) -> dict:
    region = f"{index:02d}"
    suffix = "_orszagos" if index == 0 else f"_region{index}"
    return {
        "artifact_id": f"p05_census2011_{family}_{region}{suffix}",
        "role": "initial_state",
        "source_id": "ksh_census_2011_retrospective",
        "sha256": "e" * 64,
        "declared_sha256": "e" * 64,
        "grade": "C",
        "evidence_status": "literature_proxy",
        "observation_at": "1960-01-01",
        "initial_at": "1960-01-01",
        "path": f"data/raw/ksh_census_2011/{region}_1_3_1_1.xls",
        "variable_id": f"{family}_anchor",
    }


def _anchor(family: str, index: int, *, classification: str = "blocked") -> dict:
    artifact = _manifest_artifact(family, index)
    units = {"dwelling": "dwellings", "household": "households", "population": "persons"}
    missing = {
        "dwelling": "no 1957 regional housing stock",
        "household": "no 1957 household count or definition",
        "population": "no direct 1957 regional observation",
    }[family]
    return {
        "anchor_id": f"{family}_1960_orszagos_{index:02d}",
        "legacy_artifact_id": artifact["artifact_id"],
        "variable_id": artifact["variable_id"],
        "source_id": artifact["source_id"],
        "source_sha256": artifact["sha256"],
        "legacy_grade": artifact["grade"],
        "legacy_evidence_status": artifact["evidence_status"],
        "observation_at": artifact["observation_at"],
        "legacy_initial_at": artifact["initial_at"],
        "unit": units[family],
        "geographic_scope": "national" if index == 0 else f"region_{index:02d}",
        "source_boundary_basis": (
            "1960 census counts published in 2011 retrospective tables using 2011 "
            "fixed boundaries; not the 1957 boundary"
        ),
        "desired_boundary_basis": "1957 administrative/legal boundary (unresolved)",
        "source_evidence_kind": "proxy",
        "classification": classification,
        "transformation": "documented_proxy_identity" if classification != "blocked" else None,
        "supporting_anchor_ids": [],
        "uncertainty": "high",
        "missing_evidence": "" if classification != "blocked" else missing,
        "runtime_connected": False,
        "path": artifact["path"],
    }


def _candidate(source_id: str, work_id: str) -> dict:
    return {
        "source_id": source_id,
        "work_id": work_id,
        "title": source_id,
        "authors": ["fixture"],
        "publication_date": "1982",
        "publication_precision": "year",
        "document_number": "SWP506",
        "archival_reference": None,
        "source_type": "secondary_analysis",
        "purpose": "secondary_context",
        "local_path": f"data/private/{source_id}.pdf",
        "source_sha256": "a" * 64,
        "pdf_pages": 43,
        "pdf_page_range": "1-43",
        "printed_page_range": None,
        "statistical_period": None,
        "source_available_at": None,
        "source_available_precision": "unknown",
        "rights": {"license_status": "unknown"},
        "remote_model_upload_allowed": False,
        "data_role": DataRole.NOT_ADMITTED,
        "admission_status": "candidate",
        "observation_ids": [],
        "cited_observation_ids": [],
        "approved_excerpt_ids": [],
        "missing_fields": ["archival_reference", "usage_rights"],
    }


def _primary_record(
    source_id: str = "decree_1966_41",
    *,
    work_id: str = "gov_decree_1966",
    root: str = "root_a",
    excerpt_id: str = "excerpt_001",
    source_sha256: str = PRIMARY_SHA,
) -> dict:
    return {
        "source_id": source_id,
        "work_id": work_id,
        "title": source_id,
        "authors": ["Hungarian Government"],
        "publication_date": "1966-07-01",
        "publication_precision": "day",
        "document_number": "41/1966",
        "archival_reference": "MOL XIX-A-1-a-41-1966",
        "source_type": "primary_institutional",
        "purpose": "institutional_context",
        "local_path": f"data/private/primary/{source_id}.pdf",
        "source_sha256": source_sha256,
        "pdf_pages": 12,
        "pdf_page_range": "1-12",
        "printed_page_range": "1-12",
        "statistical_period": None,
        "source_available_at": "1966-07-01",
        "source_available_precision": "day",
        "rights": dict(RIGHTS_VERIFIED),
        "remote_model_upload_allowed": False,
        "data_role": DataRole.NOT_ADMITTED,
        "admission_status": "candidate",
        "observation_ids": [root],
        "cited_observation_ids": [root],
        "observable_pattern": f"observable pattern for {root}",
        "approved_excerpt_ids": [excerpt_id],
        "missing_fields": [],
    }


def _excerpt(**overrides: object) -> dict:
    value = {
        "excerpt_id": "excerpt_001",
        "source_id": "decree_1966_41",
        "source_sha256": PRIMARY_SHA,
        "content_hash": EXCERPT_HASH,
        "approved_by": "reviewer",
        "approved_at": "2026-10-16",
        "allowed_use": "narrow_citation",
        "allowed_window": "1966-01-01/1967-12-31",
        "pdf_pages": [3],
    }
    value.update(overrides)
    value.setdefault(
        "handoff",
        {
            "content_sha256": value["content_hash"],
            "source_sha256": value["source_sha256"],
            "approved_by": value["approved_by"],
            "approved_at": value["approved_at"],
        },
    )
    return value


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    records = [
        _candidate("balassa_1982_swp506", "balassa_1982_swp506"),
        _candidate("kenen_1990_wp9079", "kenen_1990_wp9079"),
        _candidate("boote_somogyi_1991_ch02", "boote_somogyi_1991_op83"),
        _candidate("boote_somogyi_1991_ch05", "boote_somogyi_1991_op83"),
    ]
    _write_json(
        root / "history/HIST_VNEXT/sources/batch01_candidates.json",
        {"schema_version": "hist_vnext_h1a_v1", "records": records},
    )
    _write_json(
        root / "history/HIST_VNEXT/sources/authority_coverage.json",
        {
            "authorities": [
                {
                    "authority": "1965 preparation / 1966 approval",
                    "period": "1965/1966",
                    "required_primary_ids": ["E01"],
                    "implementation_evidence_ids": [],
                    "status": "blocked",
                    "missing_evidence": "primary decree or government protocol",
                }
            ]
        },
    )
    _write_json(
        root / "history/HIST_VNEXT/event_candidates/events.json",
        {
            "events": [
                {
                    "event_id": "E01",
                    "description": "fixture candidate",
                    "date": None,
                    "date_precision": "unknown",
                    "status": "candidate",
                    "missing_fields": ["date"],
                }
            ]
        },
    )
    _write_json(
        root / "history/HIST_VNEXT/exposure/access_register.json",
        {"schema_version": "hist_vnext_h1a_v1", "approved_excerpts": [], "access_log": []},
    )
    _write_json(
        root / "history/HIST_VNEXT/exposure/review_requests.json",
        {
            "schema_version": "hist_vnext_h1a_v1",
            "requests": [
                {
                    "request_id": "RR-001",
                    "source_id": "balassa_1982_swp506",
                    "page_range": "10-18",
                    "reason": "fixture",
                    "status": "REVIEW_REQUIRED",
                }
            ],
        },
    )
    artifacts = [
        _manifest_artifact(family, index)
        for family in ("dwelling", "household", "population")
        for index in range(21)
    ]
    _write_json(
        root / "data/manifests/DATA_MANIFEST_v1.json",
        {"schema_version": "v1", "artifacts": artifacts},
    )
    records = [
        _anchor(family, index)
        for family in ("dwelling", "household", "population")
        for index in range(21)
    ]
    _write_json(
        root / "config/initial_state/hist_vnext_v1/anchor_crosswalk.json",
        {
            "schema_version": "hist_vnext_h1a_v1",
            "declaration_only": True,
            "runtime_connected": False,
            "target_initial_at": "1957-01-01",
            "records": records,
        },
    )
    return root


@pytest.fixture
def positive_repo(repo_root: Path) -> Path:
    """Software-only gate fixture: not evidence of a real historical package."""
    second_sha = "1" * 64
    second = _primary_record(
        "decree_1967_42",
        work_id="gov_decree_1967",
        root="root_b",
        excerpt_id="excerpt_002",
        source_sha256=second_sha,
    )
    _write_json(
        repo_root / "history/HIST_VNEXT/sources/batch01_candidates.json",
        {"schema_version": "hist_vnext_h1a_v1", "records": [_primary_record(), second]},
    )
    _write_json(
        repo_root / "history/HIST_VNEXT/exposure/access_register.json",
        {
            "schema_version": "hist_vnext_h1a_v1",
            "approved_excerpts": [
                _excerpt(),
                _excerpt(
                    excerpt_id="excerpt_002",
                    source_id="decree_1967_42",
                    source_sha256=second_sha,
                ),
            ],
            "access_log": [],
        },
    )
    _write_json(
        repo_root / "history/HIST_VNEXT/sources/authority_coverage.json",
        {
            "authorities": [
                {
                    "authority": "software fixture authority",
                    "period": "1966",
                    "required_primary_ids": ["E01"],
                    "implementation_evidence_ids": ["E02"],
                    "status": "covered",
                }
            ]
        },
    )
    _write_json(
        repo_root / "history/HIST_VNEXT/event_candidates/events.json",
        {
            "events": [
                {
                    "event_id": "E01",
                    "description": "software fixture authority event",
                    "date": "1966-07-01",
                    "date_precision": "day",
                    "document_number": "41/1966",
                    "archival_reference": "MOL XIX-A-1-a-41-1966",
                    "rights": dict(RIGHTS_VERIFIED),
                    "source_id": "decree_1966_41",
                    "source_sha256": PRIMARY_SHA,
                    "pdf_page": 3,
                    "issuer": "software fixture government",
                    "legal_force": "software fixture decree",
                    "reviewer": "software fixture reviewer",
                    "authority_granted": ["software fixture procurement right"],
                    "implementation_evidence_id": "E02",
                    "observed_implementation_at": "1966-07-15",
                    "status": "verified",
                },
                {
                    "event_id": "E02",
                    "description": "software fixture implementation event",
                    "date": "1967-01-01",
                    "date_precision": "day",
                    "document_number": "42/1967",
                    "archival_reference": "MOL XIX-A-1-a-42-1967",
                    "rights": dict(RIGHTS_VERIFIED),
                    "source_id": "decree_1967_42",
                    "source_sha256": second_sha,
                    "pdf_page": 3,
                    "issuer": "software fixture ministry",
                    "legal_force": "software fixture implementation order",
                    "reviewer": "software fixture reviewer",
                    "authority_granted": ["software fixture procurement right"],
                    "implementation_evidence_id": "E01",
                    "observed_implementation_at": "1967-01-15",
                    "status": "verified",
                },
            ]
        },
    )
    crosswalk_path = repo_root / "config/initial_state/hist_vnext_v1/anchor_crosswalk.json"
    crosswalk = json.loads(crosswalk_path.read_text())
    for record in crosswalk["records"]:
        record["classification"] = "proxy"
        record["source_evidence_kind"] = "proxy"
        record["transformation"] = "documented_proxy_identity"
        record["missing_evidence"] = ""
    _write_json(crosswalk_path, crosswalk)
    return repo_root


# --------------------------------------------------------------------------- #
# Admission evaluation
# --------------------------------------------------------------------------- #


class TestAdmission:
    def test_secondary_sources_stay_candidate(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = json.loads(
            (repo_root / "history/HIST_VNEXT/sources/batch01_candidates.json").read_text()
        )["records"][0]
        result = evaluate_source(record, approved_excerpts=[])
        assert result["status"] == "candidate"
        assert any("secondary_analysis" in reason for reason in result["reasons"])

    @pytest.mark.parametrize("purpose", ["forcing", "actor"])
    def test_target_purpose_is_blocked(self, purpose: str):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record["purpose"] = purpose
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "blocked"
        assert any(purpose in reason for reason in result["reasons"])

    def test_complete_primary_is_admitted(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        result = evaluate_source(_primary_record(), approved_excerpts=[_excerpt()])
        assert result == {"status": "admitted", "reasons": []}

    def test_published_document_number_without_archival_reference_is_admitted(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record["archival_reference"] = None
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "admitted"

    @pytest.mark.parametrize("field", ["document_number", "archival_reference"])
    @pytest.mark.parametrize("bad", [["x"], {"x": "y"}, True])
    def test_malformed_identifier_blocks_even_with_alternative(
        self, field: str, bad: object
    ):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record[field] = bad
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "blocked"
        assert any(f"invalid: {field}" in reason for reason in result["reasons"])

    @pytest.mark.parametrize("field", ["document_number", "archival_reference"])
    def test_whitespace_identifier_is_not_usable(self, field: str):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record[field] = " \t\n"
        record["archival_reference" if field == "document_number" else "document_number"] = None
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "blocked"
        assert any("usable document_number" in reason for reason in result["reasons"])

    def test_missing_document_and_archival_reference_is_blocked(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record["document_number"] = None
        record["archival_reference"] = None
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "blocked"
        assert any(
            "document_number or archival_reference" in reason
            for reason in result["reasons"]
        )

    def test_blank_work_identity_blocks(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record["work_id"] = " \t\n"
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "blocked"
        assert any("work_id" in reason for reason in result["reasons"])

    def test_blank_matching_source_identity_blocks(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        excerpt = _excerpt()
        record["source_id"] = " \t\n"
        excerpt["source_id"] = " \t\n"
        result = evaluate_source(record, approved_excerpts=[excerpt])
        assert result["status"] == "blocked"
        assert any("source_id" in reason for reason in result["reasons"])

    def test_blank_selected_excerpt_identity_blocks(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        excerpt = _excerpt()
        record["approved_excerpt_ids"] = [" \t\n"]
        excerpt["excerpt_id"] = " \t\n"
        result = evaluate_source(record, approved_excerpts=[excerpt])
        assert result["status"] == "blocked"
        assert any("approved_excerpt_ids" in reason for reason in result["reasons"])

    def test_blank_matching_approval_identity_blocks(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        excerpt = _excerpt()
        excerpt["approved_by"] = " \t\n"
        excerpt["handoff"]["approved_by"] = " \t\n"
        result = evaluate_source(_primary_record(), approved_excerpts=[excerpt])
        assert result["status"] == "blocked"
        assert any("approved_by" in reason for reason in result["reasons"])

    def test_whitespace_rights_evidence_is_blocked(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        rights = dict(RIGHTS_VERIFIED)
        rights["evidence_quote"] = " \t\n"
        record["rights"] = rights
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "blocked"
        assert any("invalid rights" in reason for reason in result["reasons"])

    def test_verified_rights_require_evidence(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record["rights"] = {"license_status": "verified"}
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "blocked"
        assert any("invalid rights" in reason for reason in result["reasons"])

    def test_invented_rights_status_is_blocked(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record["rights"] = {"license_status": "invented"}
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "blocked"
        assert any("invalid rights" in reason for reason in result["reasons"])

    def test_unknown_rights_is_candidate(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record["rights"] = {"license_status": "unknown"}
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "candidate"
        assert any("unknown rights" in reason for reason in result["reasons"])

    def test_excerpt_source_id_mismatch_blocks(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        result = evaluate_source(
            _primary_record(), approved_excerpts=[_excerpt(source_id="WRONG")]
        )
        assert result["status"] == "blocked"
        assert any("source_id mismatch" in reason for reason in result["reasons"])

    def test_excerpt_parent_hash_mismatch_blocks(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        result = evaluate_source(
            _primary_record(),
            approved_excerpts=[_excerpt(source_sha256="c" * 64)],
        )
        assert result["status"] == "blocked"
        assert any("does not match parent" in reason for reason in result["reasons"])

    def test_excerpt_page_outside_range_blocks(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        result = evaluate_source(
            _primary_record(), approved_excerpts=[_excerpt(pdf_pages=[99])]
        )
        assert result["status"] == "blocked"
        assert any("outside" in reason for reason in result["reasons"])

    def test_excerpt_allowed_window_outside_source_blocks(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        result = evaluate_source(
            _primary_record(),
            approved_excerpts=[_excerpt(allowed_window="1986-01-01/1988-12-31")],
        )
        assert result["status"] == "blocked"
        assert any("does not cover" in reason for reason in result["reasons"])

    def test_excerpt_allowed_use_must_match_purpose(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        result = evaluate_source(
            _primary_record(), approved_excerpts=[_excerpt(allowed_use="none")]
        )
        assert result["status"] == "blocked"
        assert any("allowed_use" in reason for reason in result["reasons"])

    def test_multi_source_excerpt_register_is_filtered(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        other = _excerpt(
            excerpt_id="excerpt_002",
            source_id="other_source",
            source_sha256="d" * 64,
        )
        result = evaluate_source(
            _primary_record(), approved_excerpts=[_excerpt(), other]
        )
        assert result["status"] == "admitted"

    def test_whitespace_observable_pattern_is_not_admitted(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record["observable_pattern"] = " \t\n"
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "blocked"
        assert any("observable_pattern" in reason for reason in result["reasons"])

    def test_unselected_excerpt_is_not_admitted(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record["approved_excerpt_ids"] = []
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "blocked"
        assert any("no approved excerpts" in reason for reason in result["reasons"])

    def test_restricted_rights_need_use_evidence(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record["rights"] = {"license_status": "restricted"}
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "blocked"
        assert any("invalid rights" in reason for reason in result["reasons"])

    @pytest.mark.parametrize(
        "value",
        ["1966-1988/1967", "1966/1967-1988", "1966-1988/1967-1968"],
    )
    def test_composite_interval_endpoints_are_blocked(self, value: str):
        from history.HIST_VNEXT.sources.admission import _date_bounds, evaluate_source

        assert _date_bounds(value) is None
        record = _primary_record()
        record["statistical_period"] = value
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "blocked"
        window_result = evaluate_source(
            _primary_record(), approved_excerpts=[_excerpt(allowed_window=value)]
        )
        assert window_result["status"] == "blocked"

    @pytest.mark.parametrize(
        "window",
        ["1966/1967/1988", "1967-12-31/1966-01-01"],
    )
    def test_malformed_excerpt_window_is_blocked(self, window: str):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        result = evaluate_source(
            _primary_record(), approved_excerpts=[_excerpt(allowed_window=window)]
        )
        assert result["status"] == "blocked"
        assert any("allowed_window" in reason for reason in result["reasons"])

    def test_partial_period_authorization_is_blocked(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record["source_available_at"] = None
        record["statistical_period"] = "1966/1988"
        result = evaluate_source(
            record, approved_excerpts=[_excerpt(allowed_window="1966")]
        )
        assert result["status"] == "blocked"
        assert any("does not cover" in reason for reason in result["reasons"])

    def test_full_period_is_checked_even_with_availability(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record["source_available_at"] = "1966-07-01"
        record["statistical_period"] = "1966/1988"
        result = evaluate_source(
            record, approved_excerpts=[_excerpt(allowed_window="1966")]
        )
        assert result["status"] == "blocked"
        assert any("statistical_period" in reason for reason in result["reasons"])

    def test_missing_page_count_is_blocked(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record["pdf_pages"] = None
        record["pdf_page_range"] = "1-999"
        result = evaluate_source(record, approved_excerpts=[_excerpt(pdf_pages=[999])])
        assert result["status"] == "blocked"
        assert any("pdf_pages must be a positive integer" in reason for reason in result["reasons"])

    def test_changed_content_hash_must_match_handoff(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        excerpt = _excerpt(content_hash="cd" * 32)
        excerpt["handoff"]["content_sha256"] = EXCERPT_HASH
        result = evaluate_source(_primary_record(), approved_excerpts=[excerpt])
        assert result["status"] == "blocked"
        assert any("handoff content_sha256 mismatch" in reason for reason in result["reasons"])

    def test_invalid_approved_excerpt_ids_do_not_raise(self):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = _primary_record()
        record["approved_excerpt_ids"] = [{}]
        result = evaluate_source(record, approved_excerpts=[_excerpt()])
        assert result["status"] == "blocked"
        assert any("approved_excerpt_ids" in reason for reason in result["reasons"])


# --------------------------------------------------------------------------- #
# Shared observations
# --------------------------------------------------------------------------- #


class TestSharedObservations:
    def test_same_work_is_not_independent(self):
        from history.HIST_VNEXT.sources.admission import find_shared_observations

        records = [
            {
                "source_id": "a",
                "work_id": "same",
                "observation_ids": ["obs_A"],
                "cited_observation_ids": ["obs_A"],
            },
            {
                "source_id": "b",
                "work_id": "same",
                "observation_ids": ["obs_B"],
                "cited_observation_ids": ["obs_B"],
            },
        ]
        pair = find_shared_observations(records)[0]
        assert pair["independent"] is False

    def test_different_works_with_distinct_traceable_roots_are_independent(self):
        from history.HIST_VNEXT.sources.admission import find_shared_observations

        records = [
            {
                "source_id": "a",
                "work_id": "work_a",
                "observation_ids": ["obs_X"],
                "cited_observation_ids": ["obs_X"],
            },
            {
                "source_id": "b",
                "work_id": "work_b",
                "observation_ids": ["obs_Y"],
                "cited_observation_ids": ["obs_Y"],
            },
        ]
        pair = find_shared_observations(records)[0]
        assert pair["independent"] is True

    def test_direct_root_overlap_is_not_independent(self):
        from history.HIST_VNEXT.sources.admission import find_shared_observations

        records = [
            {
                "source_id": "a",
                "work_id": "work_a",
                "observation_ids": ["root"],
                "cited_observation_ids": [],
            },
            {
                "source_id": "b",
                "work_id": "work_b",
                "observation_ids": ["root"],
                "cited_observation_ids": [],
            },
        ]
        pair = find_shared_observations(records)[0]
        assert pair["independent"] is False
        assert pair["shared_observation_ids"] == ["root"]

    def test_unrooted_record_cannot_be_independent(self):
        from history.HIST_VNEXT.sources.admission import find_shared_observations

        records = [
            {
                "source_id": "a",
                "work_id": "work_a",
                "observation_ids": [],
                "cited_observation_ids": [],
            },
            {
                "source_id": "b",
                "work_id": "work_b",
                "observation_ids": ["obs_X"],
                "cited_observation_ids": ["obs_X"],
            },
        ]
        pair = find_shared_observations(records)[0]
        assert pair["independent"] is None

    def test_unknown_shared_root_returns_none(self):
        from history.HIST_VNEXT.sources.admission import find_shared_observations

        records = [
            {
                "source_id": "a",
                "work_id": "work_a",
                "observation_ids": [],
                "cited_observation_ids": ["obs_unknown_root"],
            },
            {
                "source_id": "b",
                "work_id": "work_b",
                "observation_ids": [],
                "cited_observation_ids": ["obs_unknown_root"],
            },
        ]
        pair = find_shared_observations(records)[0]
        assert pair["independent"] is None


# --------------------------------------------------------------------------- #
# Anchor crosswalk
# --------------------------------------------------------------------------- #


def _crosswalk(root: Path) -> list[dict]:
    return json.loads(
        (root / "config/initial_state/hist_vnext_v1/anchor_crosswalk.json").read_text()
    )["records"]


def _artifacts(root: Path) -> list[dict]:
    artifacts = json.loads(
        (root / "data/manifests/DATA_MANIFEST_v1.json").read_text()
    )["artifacts"]
    return [artifact for artifact in artifacts if artifact.get("role") == "initial_state"]


class TestAnchorCrosswalk:
    def test_real_crosswalk_is_a_full_bijection(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    def test_legacy_artifact_ids_alone_are_rejected(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        ids = {artifact["artifact_id"] for artifact in _artifacts(REPO_ROOT)}
        with pytest.raises(ValueError, match="legacy_artifact_ids alone"):
            validate_anchor_crosswalk(records, legacy_artifact_ids=ids)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("variable_id", "NOT_A_REGISTERED_VARIABLE"),
            ("anchor_id", "invented_1960_orszagos_00"),
            ("classification", "invented"),
            ("path", "data/raw/does-not-exist.xls"),
            ("runtime_connected", True),
        ],
    )
    def test_forged_row_fields_are_rejected(self, field: str, value: object):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        records[0][field] = value
        with pytest.raises(ValueError):
            validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    def test_swapped_anchor_geography_is_rejected(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        records[0]["anchor_id"], records[1]["anchor_id"] = (
            records[1]["anchor_id"],
            records[0]["anchor_id"],
        )
        records[0]["geographic_scope"], records[1]["geographic_scope"] = (
            records[1]["geographic_scope"],
            records[0]["geographic_scope"],
        )
        with pytest.raises(ValueError, match="does not match legacy artifact identity"):
            validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    def test_whitespace_blocked_evidence_is_rejected(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        records[0]["missing_evidence"] = " \t\n"
        with pytest.raises(ValueError, match="missing_evidence"):
            validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    def test_actual_unresolved_rows_cannot_be_relabelled_proxy(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        for record in records:
            record["classification"] = "proxy"
        with pytest.raises(ValueError, match="missing_evidence|transformation"):
            validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    def test_actual_rows_cannot_be_relabelled_synthetic(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        for record in records:
            record["classification"] = "synthetic"
        with pytest.raises(ValueError, match="classification|source_evidence_kind"):
            validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    def test_proxy_requires_transformation_and_supporting_evidence(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        records[0].update(
            classification="proxy",
            source_evidence_kind="proxy",
            transformation=None,
            missing_evidence="unresolved boundary",
        )
        with pytest.raises(ValueError, match="transformation"):
            validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    @pytest.mark.parametrize(
        "field", ["variable_id", "classification", "source_evidence_kind"]
    )
    def test_anchor_scalar_containers_are_exit_2(self, positive_repo: Path, field: str):
        path = positive_repo / "config/initial_state/hist_vnext_v1/anchor_crosswalk.json"
        data = json.loads(path.read_text())
        data["records"][0][field] = ["x"]
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 2
        assert "Traceback" not in completed.stderr
        assert json.loads(completed.stdout)["structural"] == "BLOCKED"

    def test_source_evidence_kind_is_derived_from_manifest(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        records[0]["source_evidence_kind"] = "direct"
        with pytest.raises(ValueError, match="source_evidence_kind"):
            validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    def test_supporting_anchor_container_is_validated(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        records[0]["supporting_anchor_ids"] = 1
        with pytest.raises(ValueError, match="supporting_anchor_ids"):
            validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    def test_reconstructed_without_support_is_rejected(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        records[0]["classification"] = "reconstructed"
        records[0]["source_evidence_kind"] = "reconstructed"
        with pytest.raises(ValueError, match="transformation|supporting"):
            validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    def test_1960_proxy_cannot_be_direct(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        records[0]["classification"] = "direct"
        with pytest.raises(ValueError, match="contradicts|cannot be classified"):
            validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    def test_missing_legacy_artifact_id_is_rejected(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        del records[0]["legacy_artifact_id"]
        with pytest.raises(ValueError, match="missing legacy_artifact_id"):
            validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    def test_duplicate_legacy_artifact_id_is_rejected(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        records[1]["legacy_artifact_id"] = records[0]["legacy_artifact_id"]
        with pytest.raises(ValueError, match="covered by both"):
            validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    def test_missing_legacy_artifact_is_rejected(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)[:-1]
        with pytest.raises(ValueError, match="does not cover"):
            validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    def test_unknown_legacy_artifact_id_is_rejected(self):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        records = _crosswalk(REPO_ROOT)
        records[0]["legacy_artifact_id"] = "not_a_legacy_artifact"
        with pytest.raises(ValueError, match="not a role=initial_state artifact"):
            validate_anchor_crosswalk(records, legacy_artifacts=_artifacts(REPO_ROOT))

    def test_header_contract_is_rejected(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = repo_root / "config/initial_state/hist_vnext_v1/anchor_crosswalk.json"
        data = json.loads(path.read_text())
        data["declaration_only"] = False
        _write_json(path, data)
        result = audit_h1a(repo_root)
        assert result["exit_code"] == 2
        assert result["structural"] == "BLOCKED"


# --------------------------------------------------------------------------- #
# Audit structural and historical gates
# --------------------------------------------------------------------------- #


class TestAudit:
    def test_current_fixture_is_structural_pass_historical_blocked(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        result = audit_h1a(repo_root)
        assert result["exit_code"] == 1
        assert result["structural"] == "PASS"
        assert result["historical"] == "BLOCKED"
        assert result["summary"]["total_candidates"] == 4
        assert result["summary"]["total_admitted"] == 0
        assert result["summary"]["total_blocked_anchors"] == 63

    def test_malformed_manifest_is_exit_2(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        (repo_root / "data/manifests/DATA_MANIFEST_v1.json").write_text("{")
        result = audit_h1a(repo_root)
        assert result["exit_code"] == 2
        assert result["structural"] == "BLOCKED"

    def test_malformed_candidate_container_is_exit_2(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        (repo_root / "history/HIST_VNEXT/sources/batch01_candidates.json").write_text("[]")
        result = audit_h1a(repo_root)
        assert result["exit_code"] == 2

    def test_malformed_nested_candidate_is_exit_2(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = repo_root / "history/HIST_VNEXT/sources/batch01_candidates.json"
        _write_json(path, {"records": [1]})
        result = audit_h1a(repo_root)
        assert result["exit_code"] == 2

    def test_empty_coverage_cannot_pass(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        _write_json(
            positive_repo / "history/HIST_VNEXT/sources/authority_coverage.json",
            {"authorities": []},
        )
        _write_json(
            positive_repo / "history/HIST_VNEXT/event_candidates/events.json",
            {"events": []},
        )
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"
        assert any("authority coverage is empty" in detail for detail in result["details"])

    def test_unverified_event_cannot_pass(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/event_candidates/events.json"
        data = json.loads(path.read_text())
        data["events"][0]["status"] = "candidate"
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    def test_positive_software_fixture_reaches_exit_0(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 0
        assert result["structural"] == "PASS"
        assert result["historical"] == "PASS"
        assert result["summary"]["total_admitted"] == 2
        assert result["summary"]["total_blocked_anchors"] == 0
        assert result["summary"]["independent_pairs"] >= 1

    def test_nested_candidate_container_is_exit_2(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = repo_root / "history/HIST_VNEXT/sources/batch01_candidates.json"
        data = json.loads(path.read_text())
        data["records"][0]["approved_excerpt_ids"] = [{}]
        _write_json(path, data)
        result = audit_h1a(repo_root)
        assert result["exit_code"] == 2
        assert result["structural"] == "BLOCKED"

    def test_nested_authority_container_is_exit_2(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = repo_root / "history/HIST_VNEXT/sources/authority_coverage.json"
        data = json.loads(path.read_text())
        data["authorities"][0]["implementation_evidence_ids"] = 1
        _write_json(path, data)
        result = audit_h1a(repo_root)
        assert result["exit_code"] == 2
        assert result["structural"] == "BLOCKED"

    def test_subprocess_nested_error_returns_exit_2(self, repo_root: Path):
        path = repo_root / "history/HIST_VNEXT/sources/batch01_candidates.json"
        data = json.loads(path.read_text())
        data["records"][0]["approved_excerpt_ids"] = [{}]
        _write_json(path, data)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "history.HIST_VNEXT.sources.admission",
                "--root",
                str(repo_root),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 2
        assert "Traceback" not in completed.stderr
        assert json.loads(completed.stdout)["structural"] == "BLOCKED"

    def test_event_source_must_be_admitted(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/event_candidates/events.json"
        data = json.loads(path.read_text())
        data["events"][0]["source_id"] = "ABSENT"
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    def test_event_rights_date_and_page_are_validated(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/event_candidates/events.json"
        data = json.loads(path.read_text())
        data["events"][0].update(
            rights={"license_status": "invented"},
            date="NOT_A_DATE",
            pdf_page=999,
        )
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    @pytest.mark.parametrize("field", ["authority", "period"])
    @pytest.mark.parametrize("blank", ["", " \t\n", "\u00a0"])
    def test_blank_authority_metadata_blocks(
        self, positive_repo: Path, field: str, blank: str
    ):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/sources/authority_coverage.json"
        data = json.loads(path.read_text())
        data["authorities"][0][field] = blank
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"
        completed = _run_cli(positive_repo)
        assert completed.returncode == 1
        assert "Traceback" not in completed.stderr
        assert json.loads(completed.stdout)["historical"] == "BLOCKED"

    @pytest.mark.parametrize(
        "period",
        [
            "1966/1967/1968",
            "1967-12-31/1966-01-01",
            "1966-1988/1967",
            "1966/1967-1988",
            "1966-1988/1967-1968",
        ],
    )
    def test_malformed_authority_period_blocks(self, positive_repo: Path, period: str):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/sources/authority_coverage.json"
        data = json.loads(path.read_text())
        data["authorities"][0]["period"] = period
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"
        completed = _run_cli(positive_repo)
        assert completed.returncode == 1
        assert "Traceback" not in completed.stderr

    @pytest.mark.parametrize(
        "window",
        [
            "1966/1967/1988",
            "1967-12-31/1966-01-01",
            "1966-1988/1967",
            "1966/1967-1988",
            "1966-1988/1967-1968",
        ],
    )
    def test_malformed_excerpt_window_blocks_cli(self, positive_repo: Path, window: str):
        path = positive_repo / "history/HIST_VNEXT/exposure/access_register.json"
        data = json.loads(path.read_text())
        data["approved_excerpts"][0]["allowed_window"] = window
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 1
        assert "Traceback" not in completed.stderr
        assert json.loads(completed.stdout)["historical"] == "BLOCKED"

    def test_authority_period_must_be_parseable(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/sources/authority_coverage.json"
        data = json.loads(path.read_text())
        data["authorities"][0]["period"] = "not-a-period"
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    def test_authority_status_must_be_verified(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/sources/authority_coverage.json"
        data = json.loads(path.read_text())
        data["authorities"][0]["status"] = "candidate"
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    def test_second_pattern_must_be_admitted(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/sources/batch01_candidates.json"
        data = json.loads(path.read_text())
        data["records"][1]["source_type"] = "secondary_analysis"
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    def test_whitespace_observable_pattern_blocks_cli(self, positive_repo: Path):
        path = positive_repo / "history/HIST_VNEXT/sources/batch01_candidates.json"
        data = json.loads(path.read_text())
        data["records"][0]["observable_pattern"] = " \t\n"
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 1
        assert json.loads(completed.stdout)["historical"] == "BLOCKED"

    def test_observable_pattern_is_required(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/sources/batch01_candidates.json"
        data = json.loads(path.read_text())
        data["records"][0]["observable_pattern"] = None
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    def test_duplicate_source_identity_is_exit_2(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/sources/batch01_candidates.json"
        data = json.loads(path.read_text())
        duplicate = copy.deepcopy(data["records"][0])
        duplicate["work_id"] = "different_label"
        duplicate["observation_ids"] = ["invented_root"]
        duplicate["cited_observation_ids"] = ["invented_root"]
        data["records"][1] = duplicate
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 2
        assert result["structural"] == "BLOCKED"

    def test_event_page_must_be_approved(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/event_candidates/events.json"
        data = json.loads(path.read_text())
        data["events"][0]["pdf_page"] = 4
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    def test_observed_implementation_must_fit_authorized_window(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/event_candidates/events.json"
        data = json.loads(path.read_text())
        data["events"][0]["observed_implementation_at"] = "1988-02-01"
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    def test_page_and_window_must_come_from_same_excerpt(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        candidates_path = positive_repo / "history/HIST_VNEXT/sources/batch01_candidates.json"
        candidates = json.loads(candidates_path.read_text())
        candidates["records"][0]["approved_excerpt_ids"].append("late_page4")
        _write_json(candidates_path, candidates)

        access_path = positive_repo / "history/HIST_VNEXT/exposure/access_register.json"
        access = json.loads(access_path.read_text())
        late = copy.deepcopy(access["approved_excerpts"][0])
        late.update(
            excerpt_id="late_page4",
            pdf_pages=[4],
            allowed_window="1966-01-01/1988-12-31",
        )
        access["approved_excerpts"].append(late)
        _write_json(access_path, access)

        events_path = positive_repo / "history/HIST_VNEXT/event_candidates/events.json"
        events = json.loads(events_path.read_text())
        events["events"][0]["observed_implementation_at"] = "1988-02-01"
        _write_json(events_path, events)

        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    def test_manifest_evidence_status_container_is_exit_2(self, positive_repo: Path):
        path = positive_repo / "data/manifests/DATA_MANIFEST_v1.json"
        data = json.loads(path.read_text())
        data["artifacts"][0]["evidence_status"] = ["literature_proxy"]
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 2
        assert "Traceback" not in completed.stderr
        assert json.loads(completed.stdout)["structural"] == "BLOCKED"

    def test_whitespace_event_evidence_blocks(self, positive_repo: Path):
        path = positive_repo / "history/HIST_VNEXT/event_candidates/events.json"
        data = json.loads(path.read_text())
        data["events"][0]["issuer"] = " \t\n"
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 1
        assert json.loads(completed.stdout)["historical"] == "BLOCKED"

    def test_event_institutional_fields_are_required(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/event_candidates/events.json"
        data = json.loads(path.read_text())
        data["events"][0].update(
            issuer=None,
            legal_force=None,
            reviewer=None,
            authority_granted=[],
            implementation_evidence_id=None,
            observed_implementation_at=None,
        )
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    def test_implementation_evidence_must_be_distinct(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/sources/authority_coverage.json"
        data = json.loads(path.read_text())
        data["authorities"][0]["implementation_evidence_ids"] = ["E01"]
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    def test_partial_authority_evidence_overlap_is_blocked(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/sources/authority_coverage.json"
        data = json.loads(path.read_text())
        data["authorities"][0]["implementation_evidence_ids"] = ["E01", "E02"]
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    def test_duplicate_event_id_is_exit_2(self, positive_repo: Path):
        path = positive_repo / "history/HIST_VNEXT/event_candidates/events.json"
        data = json.loads(path.read_text())
        duplicate = copy.deepcopy(data["events"][0])
        duplicate["issuer"] = "contradictory issuer"
        duplicate["document_number"] = "CONFLICTING/1966"
        data["events"].append(duplicate)
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 2
        assert "Traceback" not in completed.stderr
        assert json.loads(completed.stdout)["structural"] == "BLOCKED"

    def test_duplicate_excerpt_id_is_exit_2(self, positive_repo: Path):
        path = positive_repo / "history/HIST_VNEXT/exposure/access_register.json"
        data = json.loads(path.read_text())
        duplicate = copy.deepcopy(data["approved_excerpts"][0])
        duplicate["allowed_use"] = "none"
        duplicate["pdf_pages"] = [4]
        data["approved_excerpts"].insert(0, duplicate)
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 2
        assert "Traceback" not in completed.stderr
        assert json.loads(completed.stdout)["structural"] == "BLOCKED"

    @pytest.mark.parametrize(
        "mutation",
        [
            {"document_number": ["41/1966"], "archival_reference": None},
            {"document_number": None, "archival_reference": {"archive": "A"}},
            {"document_number": True, "archival_reference": None},
        ],
    )
    def test_malformed_source_identifiers_are_exit_2(
        self, positive_repo: Path, mutation: dict
    ):
        path = positive_repo / "history/HIST_VNEXT/sources/batch01_candidates.json"
        data = json.loads(path.read_text())
        data["records"][0].update(mutation)
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 2
        assert "Traceback" not in completed.stderr
        assert json.loads(completed.stdout)["structural"] == "BLOCKED"

    @pytest.mark.parametrize(
        "mutation",
        [
            {"document_number": " \t\n", "archival_reference": None},
            {"document_number": None, "archival_reference": " \t\n"},
        ],
    )
    def test_whitespace_source_identifier_blocks(self, positive_repo: Path, mutation: dict):
        path = positive_repo / "history/HIST_VNEXT/sources/batch01_candidates.json"
        data = json.loads(path.read_text())
        data["records"][0].update(mutation)
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 1
        assert json.loads(completed.stdout)["historical"] == "BLOCKED"

    def test_whitespace_event_identifier_blocks(self, positive_repo: Path):
        path = positive_repo / "history/HIST_VNEXT/event_candidates/events.json"
        data = json.loads(path.read_text())
        data["events"][0].update(document_number=" \t", archival_reference=None)
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 1
        assert json.loads(completed.stdout)["historical"] == "BLOCKED"

    @pytest.mark.parametrize(
        ("relative", "container", "selector", "field"),
        [
            (
                "history/HIST_VNEXT/sources/batch01_candidates.json",
                "records",
                0,
                "source_id",
            ),
            (
                "history/HIST_VNEXT/sources/batch01_candidates.json",
                "records",
                0,
                "work_id",
            ),
            (
                "history/HIST_VNEXT/event_candidates/events.json",
                "events",
                0,
                "event_id",
            ),
        ],
    )
    def test_whitespace_identity_is_exit_2(
        self,
        positive_repo: Path,
        relative: str,
        container: str,
        selector: int,
        field: str,
    ):
        path = positive_repo / relative
        data = json.loads(path.read_text())
        data[container][selector][field] = " \t\n"
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 2
        assert "Traceback" not in completed.stderr
        assert json.loads(completed.stdout)["structural"] == "BLOCKED"

    @pytest.mark.parametrize("field", ["source_type", "purpose"])
    def test_source_scalar_containers_are_exit_2(
        self, positive_repo: Path, field: str
    ):
        path = positive_repo / "history/HIST_VNEXT/sources/batch01_candidates.json"
        data = json.loads(path.read_text())
        data["records"][0][field] = ["x"]
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 2
        assert "Traceback" not in completed.stderr
        assert json.loads(completed.stdout)["structural"] == "BLOCKED"

    def test_date_precision_must_match_representation(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/event_candidates/events.json"
        data = json.loads(path.read_text())
        data["events"][0].update(date="1966", date_precision="day")
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    @pytest.mark.parametrize("identifier", ["document_number", "archival_reference"])
    def test_event_identification_alternative(
        self, positive_repo: Path, identifier: str
    ):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/event_candidates/events.json"
        data = json.loads(path.read_text())
        data["events"][0][identifier] = None
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 0
        assert result["historical"] == "PASS"

    def test_event_requires_at_least_one_identifier(self, positive_repo: Path):
        from history.HIST_VNEXT.sources.admission import audit_h1a

        path = positive_repo / "history/HIST_VNEXT/event_candidates/events.json"
        data = json.loads(path.read_text())
        data["events"][0]["document_number"] = None
        data["events"][0]["archival_reference"] = None
        _write_json(path, data)
        result = audit_h1a(positive_repo)
        assert result["exit_code"] == 1
        assert result["historical"] == "BLOCKED"

    def test_null_implementation_evidence_is_structured(self, positive_repo: Path):
        path = positive_repo / "history/HIST_VNEXT/sources/authority_coverage.json"
        data = json.loads(path.read_text())
        data["authorities"][0]["implementation_evidence_ids"] = None
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 1
        assert "Traceback" not in completed.stderr
        result = json.loads(completed.stdout)
        assert result["structural"] == "PASS"
        assert result["historical"] == "BLOCKED"

    def test_list_allowed_use_is_exit_2(self, positive_repo: Path):
        path = positive_repo / "history/HIST_VNEXT/exposure/access_register.json"
        data = json.loads(path.read_text())
        data["approved_excerpts"][0]["allowed_use"] = ["narrow_citation"]
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 2
        assert "Traceback" not in completed.stderr
        assert json.loads(completed.stdout)["structural"] == "BLOCKED"

    def test_list_work_id_is_exit_2(self, positive_repo: Path):
        path = positive_repo / "history/HIST_VNEXT/sources/batch01_candidates.json"
        data = json.loads(path.read_text())
        data["records"][0]["work_id"] = ["x"]
        _write_json(path, data)
        completed = _run_cli(positive_repo)
        assert completed.returncode == 2
        assert "Traceback" not in completed.stderr
        assert json.loads(completed.stdout)["structural"] == "BLOCKED"


# --------------------------------------------------------------------------- #
# Metadata precision and schema
# --------------------------------------------------------------------------- #


class TestMetadataPrecision:
    def test_candidate_publication_precision_is_preserved(self):
        records = json.loads(
            (REPO_ROOT / "history/HIST_VNEXT/sources/batch01_candidates.json").read_text()
        )["records"]
        by_id = {record["source_id"]: record for record in records}
        assert by_id["balassa_1982_swp506"]["publication_date"] == "1982"
        assert by_id["balassa_1982_swp506"]["publication_precision"] == "year"
        assert by_id["kenen_1990_wp9079"]["publication_date"] == "1990-09"
        assert by_id["kenen_1990_wp9079"]["publication_precision"] == "month"
        for record in records:
            assert record["source_available_at"] is None
            assert record["source_available_precision"] == "unknown"

    def test_events_keep_precision_and_unknown_dates(self):
        events = json.loads(
            (REPO_ROOT / "history/HIST_VNEXT/event_candidates/events.json").read_text()
        )["events"]
        by_id = {event["event_id"]: event for event in events}
        assert by_id["E03"]["date"] == "1968-01-01"
        assert by_id["E03"]["date_precision"] == "day"
        assert by_id["E04"]["date"] == "1972-11"
        assert by_id["E04"]["date_precision"] == "month"
        assert by_id["E05"]["date"] == "1973"
        assert by_id["E05"]["date_precision"] == "year"
        assert by_id["E06"]["date"] == "1975"
        assert by_id["E06"]["date_precision"] == "year"
        for event in events:
            assert "date_precision" in event
            assert "enacted_at" in event
            assert "effective_at" in event
            assert "effective_to" in event
            assert "available_at" in event
            assert "observed_implementation_at" in event
            assert "information_rights" in event
            assert "authority_granted" in event
            assert "authority_removed" in event

    def test_crosswalk_records_keep_legacy_id_and_boundary_caveat(self):
        records = _crosswalk(REPO_ROOT)
        for record in records:
            assert record["legacy_artifact_id"]
            assert "2011" in record["source_boundary_basis"]
            assert "autonomy law" not in record["desired_boundary_basis"]
