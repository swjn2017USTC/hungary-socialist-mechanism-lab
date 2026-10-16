"""
H1A source admission — behavioral contracts and negative examples.

Verifies:
- Secondary-analysis sources (Balassa, Kenen, Boote-Somogyi) are `candidate`, never `admitted`.
- A primary institutional document with all required fields (document_number,
  archival_reference, usage_rights, period, statistical/制度 period,
  publication_date, source_available_at, approved_excerpt_ids) becomes `admitted`.
- Removing any critical evidence field demotes `admitted` → `candidate` or `blocked`.
- A direct 1960/C/2011 anchor claiming 1957 `direct` is rejected; the same anchor
  correctly classified as 1957 `blocked` passes validation.
- `find_shared_observations` returns `independent=false` when two papers share a root
  observation under the same work_id; `independent=true` when they do not.
- `validate_anchor_crosswalk` raises ValueError on duplicate anchor_id, missing anchor_id,
  national aggregate marked as regional, and any anchor without a classification.
- Historical target used as forcing/actor is rejected.
- `audit_h1a` on the current repo (with no admitted excerpts, no primary documents,
  all four candidates in `batch01_candidates.json`) returns exit 1 with candidate status.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# The module does not exist yet; imports fail until admission.py is written.
from hsm_lab.evidence.schemas import DataRole

# --------------------------------------------------------------------------- #
# Constants matching H1A artifact structure
# --------------------------------------------------------------------------- #

_WORK_ID_BALASSA = "balassa_1982_swp506"
_WORK_ID_IMF91 = "imf_boote_somogyi_1991_op83"
_WORK_ID_IMF90 = "kenen_1990_wp9079"
_WORK_ID_IMF91_CH2 = "imf_boote_somogyi_1991_op83"  # same work as ch1

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """Minimal repo skeleton needed by audit_h1a."""
    root = tmp_path / "repo"
    root.mkdir()

    # batch01_candidates.json
    candidates = {
        "schema_version": "hist_vnext_h1a_v1",
        "records": [
            {
                "source_id": "balassa_1982_swp506",
                "work_id": _WORK_ID_BALASSA,
                "title": "Hungary: Economic Planning and Reform",
                "authors": ["Balassa, Bela"],
                "publication_date": "1982-01-01",
                "document_number": "SWP506",
                "archival_reference": None,
                "source_type": "secondary_analysis",
                "purpose": "secondary_context",
                "local_path": "data/private/hist_vnext_sources/batch01_20261016/Balassa_1982.pdf",
                "source_sha256": "a" * 64,
                "pdf_pages": 43,
                "pdf_page_range": "1-43",
                "printed_page_range": None,
                "statistical_period": None,
                "source_available_at": "1982-01-01",
                "rights": {"license": "unknown", "source": "unknown"},
                "remote_model_upload_allowed": False,
                "data_role": DataRole.NOT_ADMITTED,
                "admission_status": "candidate",
                "observation_ids": [],
                "cited_observation_ids": [],
                "approved_excerpt_ids": [],
                "missing_fields": ["archival_reference", "usage_rights"],
            },
            {
                "source_id": "kenen_1990_wp9079",
                "work_id": _WORK_ID_IMF90,
                "title": "Hungary: Structural Reform",
                "authors": ["Kenen, Peter"],
                "publication_date": "1990-01-01",
                "document_number": "WP/90/79",
                "archival_reference": None,
                "source_type": "secondary_analysis",
                "purpose": "secondary_context",
                "local_path": "data/private/hist_vnext_sources/batch01_20261016/Kenen_1990.pdf",
                "source_sha256": "b" * 64,
                "pdf_pages": 40,
                "pdf_page_range": "1-40",
                "printed_page_range": None,
                "statistical_period": None,
                "source_available_at": "1990-01-01",
                "rights": {"license": "unknown", "source": "unknown"},
                "remote_model_upload_allowed": False,
                "data_role": DataRole.NOT_ADMITTED,
                "admission_status": "candidate",
                "observation_ids": [],
                "cited_observation_ids": [],
                "approved_excerpt_ids": [],
                "missing_fields": ["archival_reference", "usage_rights"],
            },
            {
                "source_id": "boote_somogyi_1991_ch1",
                "work_id": _WORK_ID_IMF91,
                "title": "IMF Economic Review: Hungary 1991 — Chapter 1",
                "authors": ["Boote, Anthony", "Somogyi, Robert"],
                "publication_date": "1991-01-01",
                "document_number": "OP/83",
                "archival_reference": None,
                "source_type": "secondary_analysis",
                "purpose": "secondary_context",
                "local_path": "data/private/hist_vnext_sources/batch01_20261016/IMF_1991_ch1.pdf",
                "source_sha256": "c" * 64,
                "pdf_pages": 2,
                "pdf_page_range": "1-2",
                "printed_page_range": None,
                "statistical_period": None,
                "source_available_at": "1991-01-01",
                "rights": {"license": "unknown", "source": "unknown"},
                "remote_model_upload_allowed": False,
                "data_role": DataRole.NOT_ADMITTED,
                "admission_status": "candidate",
                "observation_ids": [],
                "cited_observation_ids": [],
                "approved_excerpt_ids": [],
                "missing_fields": ["archival_reference", "usage_rights"],
            },
            {
                "source_id": "boote_somogyi_1991_ch2",
                "work_id": _WORK_ID_IMF91_CH2,
                "title": "IMF Economic Review: Hungary 1991 — Chapter 2",
                "authors": ["Boote, Anthony", "Somogyi, Robert"],
                "publication_date": "1991-01-01",
                "document_number": "OP/83",
                "archival_reference": None,
                "source_type": "secondary_analysis",
                "purpose": "secondary_context",
                "local_path": "data/private/hist_vnext_sources/batch01_20261016/IMF_1991_ch2.pdf",
                "source_sha256": "d" * 64,
                "pdf_pages": 4,
                "pdf_page_range": "1-4",
                "printed_page_range": None,
                "statistical_period": None,
                "source_available_at": "1991-01-01",
                "rights": {"license": "unknown", "source": "unknown"},
                "remote_model_upload_allowed": False,
                "data_role": DataRole.NOT_ADMITTED,
                "admission_status": "candidate",
                "observation_ids": [],
                "cited_observation_ids": [],
                "approved_excerpt_ids": [],
                "missing_fields": ["archival_reference", "usage_rights"],
            },
        ],
    }
    (root / "history" / "HIST_VNEXT" / "sources").mkdir(parents=True, exist_ok=True)
    with open(root / "history/HIST_VNEXT/sources/batch01_candidates.json", "w") as f:
        json.dump(candidates, f)

    # authority_coverage.json (all missing evidence → all blocked)
    authority = [
        {
            "authority": "1965 preparation / 1966 approval of economic mechanism",
            "period": "1965/1966",
            "required_primary_ids": [],
            "implementation_evidence_ids": [],
            "status": "blocked",
            "missing_evidence": "primary decree or government protocol",
        },
    ]
    with open(root / "history/HIST_VNEXT/sources/authority_coverage.json", "w") as f:
        json.dump(authority, f)

    # event_candidates/events.json
    events = {
        "events": [
            {
                "event_id": "E01",
                "description": "Mechanism design and approval process",
                "date": None,
                "document_number": None,
                "archival_reference": None,
                "rights": None,
                "status": "candidate",
                "missing_fields": [
                    "date",
                    "document_number",
                    "archival_reference",
                    "rights",
                ],
            },
        ],
    }
    (root / "history/HIST_VNEXT/event_candidates").mkdir(parents=True, exist_ok=True)
    with open(root / "history/HIST_VNEXT/event_candidates/events.json", "w") as f:
        json.dump(events, f)

    # exposure/access_register.json
    exposure = {
        "schema_version": "hist_vnext_h1a_v1",
        "approved_excerpts": [],
        "access_log": [],
    }
    (root / "history/HIST_VNEXT/exposure").mkdir(parents=True, exist_ok=True)
    with open(root / "history/HIST_VNEXT/exposure/access_register.json", "w") as f:
        json.dump(exposure, f)

    # review_requests.json
    review_requests = {
        "schema_version": "hist_vnext_h1a_v1",
        "requests": [
            {
                "request_id": "RR-001",
                "source_id": "balassa_1982_swp506",
                "page_range": "10-18",
                "reason": "price/investment/1972 adjustment clues",
                "status": "REVIEW_REQUIRED",
            },
        ],
    }
    with open(root / "history/HIST_VNEXT/exposure/review_requests.json", "w") as f:
        json.dump(review_requests, f)

    # DATA_MANIFEST_v1.json (required by audit_h1a)
    (root / "data/manifests").mkdir(parents=True, exist_ok=True)
    def _make_artifact_entry(family, i):
        region = f"{i:02d}"
        is_national = i == 0
        suffix = "_orszagos" if is_national else ""
        artifact_id = f"p05_census2011_{family}_{region}{suffix}"
        return {
            "artifact_id": artifact_id,
            "role": "initial_state",
            "source_id": "ksh_census_2011_retrospective",
            "declared_sha256": "e" * 64,
            "grade": "C",
            "evidence_status": "literature_proxy",
            "observation_at": "1960-01-01",
            "initial_at": "1960-01-01",
            "path": f"data/raw/ksh_census_2011/{region}_1_3_1_1.xls",
        }

    manifest = {
        "schema_version": "v1",
        "artifacts": (
            [_make_artifact_entry("dwelling", i) for i in range(21)]
            + [_make_artifact_entry("household", i) for i in range(21)]
            + [_make_artifact_entry("population", i) for i in range(21)]
        ),
    }
    with open(root / "data/manifests/DATA_MANIFEST_v1.json", "w") as f:
        json.dump(manifest, f)

    # initial_state anchor_crosswalk.json (63 items, all blocked)
    # Each record includes path and runtime_connected per R2 requirement
    def _make_anchor(family, i):
        region = f"{i:02d}"
        is_national = i == 0
        suffix = "_orszagos" if is_national else ""
        family_unit = {
            "dwelling": "dwellings",
            "household": "households",
            "population": "persons",
        }[family]
        missing_ev = {
            "dwelling": "1957 boundary map and autonomy law jurisdiction",
            "household": "1957 boundary map and household definition",
            "population": "1957 population count and boundary",
        }[family]
        return {
            "anchor_id": f"{family}_1960_orszagos_{region}",
            "variable_id": f"p05_census2011_{family}_{region}{suffix}",
            "source_id": "ksh_census_2011_retrospective",
            "source_sha256": "e" * 64,
            "legacy_grade": "C",
            "legacy_evidence_status": "2011_boundary",
            "observation_at": "1960-01-01",
            "legacy_initial_at": "1960-01-01",
            "unit": family_unit,
            "geographic_scope": "national" if is_national else f"region_{region}",
            "source_boundary_basis": "1960 census proxy",
            "desired_boundary_basis": "1957 autonomy law jurisdiction",
            "source_evidence_kind": "proxy",
            "classification": "blocked",
            "transformation": None,
            "supporting_anchor_ids": [],
            "uncertainty": "high",
            "missing_evidence": missing_ev,
            "runtime_connected": False,
            "path": f"data/raw/ksh_census_2011/{region}_1_3_1_1.xls",
        }

    anchors = {
        "schema_version": "hist_vnext_h1a_v1",
        "declaration_only": True,
        "runtime_connected": False,
        "target_initial_at": "1957-01-01",
        "records": (
            [_make_anchor("dwelling", i) for i in range(21)]
            + [_make_anchor("household", i) for i in range(21)]
            + [_make_anchor("population", i) for i in range(21)]
        ),
    }
    (root / "config" / "initial_state" / "hist_vnext_v1").mkdir(parents=True, exist_ok=True)
    with open(root / "config/initial_state/hist_vnext_v1/anchor_crosswalk.json", "w") as f:
        json.dump(anchors, f)

    return root


# --------------------------------------------------------------------------- #
# Tests — admission evaluation
# --------------------------------------------------------------------------- #

class TestSecondarySourcesStayCandidate:
    """All four batch-01 secondary sources must remain candidate, never admitted."""

    def test_balassa_is_candidate(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        with open(repo_root / "history/HIST_VNEXT/sources/batch01_candidates.json") as f:
            candidates = json.load(f)["records"]

        balassa = next(r for r in candidates if r["source_id"] == "balassa_1982_swp506")
        result = evaluate_source(balassa, approved_excerpts=[])
        assert result["status"] == "candidate"
        assert any("secondary_analysis" in r for r in result["reasons"])

    def test_forcing_purpose_blocked(self, repo_root: Path):
        """H1A §4: historical target as forcing/actor is rejected."""
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = {
            "source_id": "decree_1966_41",
            "work_id": "gov_decree_1966",
            "title": "Government Decree 41/1966",
            "authors": ["Hungarian Government"],
            "publication_date": "1966-07-01",
            "document_number": "41/1966",
            "archival_reference": "MOL XIX-A-1-a-41-1966",
            "source_type": "primary_institutional",
            "purpose": "forcing",  # explicitly for forcing
            "local_path": "test.pdf",
            "source_sha256": "f" * 64,
            "pdf_pages": 12,
            "pdf_page_range": "1-12",
            "printed_page_range": None,
            "statistical_period": "1966/1967",
            "source_available_at": "1966-07-01",
            "rights": {"license": "public_domain"},
            "remote_model_upload_allowed": False,
            "data_role": "not_admitted",
            "admission_status": "candidate",
            "observation_ids": [],
            "cited_observation_ids": [],
            "approved_excerpt_ids": [],
            "missing_fields": [],
        }
        excerpt = {
            "excerpt_id": "excerpt_001",
            "source_id": "decree_1966_41",
            "content_hash": "ab" * 32,
            "approved_by": "admin",
            "approved_at": "2026-10-16",
            "allowed_window": "1966-01-01/1967-12-31",
        }
        result = evaluate_source(record, approved_excerpts=[excerpt])
        assert result["status"] == "blocked"
        assert any("forcing" in r for r in result["reasons"])

    def test_actor_purpose_blocked(self, repo_root: Path):
        """H1A §4: historical target as actor information is rejected."""
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = {
            "source_id": "decree_1966_41",
            "work_id": "gov_decree_1966",
            "title": "Government Decree 41/1966",
            "authors": ["Hungarian Government"],
            "publication_date": "1966-07-01",
            "document_number": "41/1966",
            "archival_reference": "MOL XIX-A-1-a-41-1966",
            "source_type": "primary_institutional",
            "purpose": "actor",
            "local_path": "test.pdf",
            "source_sha256": "f" * 64,
            "pdf_pages": 12,
            "pdf_page_range": "1-12",
            "printed_page_range": None,
            "statistical_period": "1966/1967",
            "source_available_at": "1966-07-01",
            "rights": {"license": "public_domain"},
            "remote_model_upload_allowed": False,
            "data_role": "not_admitted",
            "admission_status": "candidate",
            "observation_ids": [],
            "cited_observation_ids": [],
            "approved_excerpt_ids": [],
            "missing_fields": [],
        }
        excerpt = {
            "excerpt_id": "excerpt_001",
            "source_id": "decree_1966_41",
            "content_hash": "ab" * 32,
            "approved_by": "admin",
            "approved_at": "2026-10-16",
            "allowed_window": "1966-01-01/1967-12-31",
        }
        result = evaluate_source(record, approved_excerpts=[excerpt])
        assert result["status"] == "blocked"
        assert any("actor" in r for r in result["reasons"])

    def test_excerpt_source_id_mismatch_blocks(self, repo_root: Path):
        """Excerpt source_id must match parent record."""
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = {
            "source_id": "decree_1966_41",
            "work_id": "gov_decree_1966",
            "title": "Government Decree 41/1966",
            "authors": ["Hungarian Government"],
            "publication_date": "1966-07-01",
            "document_number": "41/1966",
            "archival_reference": "MOL XIX-A-1-a-41-1966",
            "source_type": "primary_institutional",
            "purpose": "institutional_context",
            "local_path": "test.pdf",
            "source_sha256": "f" * 64,
            "pdf_pages": 12,
            "pdf_page_range": "1-12",
            "printed_page_range": None,
            "statistical_period": "1966/1967",
            "source_available_at": "1966-07-01",
            "rights": {"license": "public_domain"},
            "remote_model_upload_allowed": False,
            "data_role": "not_admitted",
            "admission_status": "candidate",
            "observation_ids": [],
            "cited_observation_ids": [],
            "approved_excerpt_ids": [],
            "missing_fields": [],
        }
        excerpt = {
            "excerpt_id": "excerpt_001",
            "source_id": "WRONG_SOURCE_ID",  # mismatched!
            "content_hash": "ab" * 32,
            "approved_by": "admin",
            "approved_at": "2026-10-16",
            "allowed_window": "1966-01-01/1967-12-31",
        }
        result = evaluate_source(record, approved_excerpts=[excerpt])
        assert result["status"] == "blocked"
        assert any("source_id mismatch" in r for r in result["reasons"])

    def test_imf_1991_two_chapters_share_work(self, repo_root: Path):
        """The two IMF 1991 chapters share work_id → same work, not independent sources."""
        from history.HIST_VNEXT.sources.admission import evaluate_source

        with open(repo_root / "history/HIST_VNEXT/sources/batch01_candidates.json") as f:
            candidates = json.load(f)["records"]

        ch1 = next(r for r in candidates if r["source_id"] == "boote_somogyi_1991_ch1")
        ch2 = next(r for r in candidates if r["source_id"] == "boote_somogyi_1991_ch2")

        result1 = evaluate_source(ch1, approved_excerpts=[])
        result2 = evaluate_source(ch2, approved_excerpts=[])

        # Same work_id: both still candidate (secondary)
        assert result1["status"] == "candidate"
        assert result2["status"] == "candidate"
        # Secondary sources are candidate due to source_type, not archival_reference
        assert any("secondary_analysis" in r for r in result1["reasons"])
        assert any("secondary_analysis" in r for r in result2["reasons"])


class TestPrimaryInstitutionalAdmission:
    """A primary institutional document with all fields becomes admitted."""

    def test_complete_primary_institutional_is_admitted(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        primary_record = {
            "source_id": "decree_1966_41",
            "work_id": "gov_decree_1966",
            "title": "Government Decree 41/1966 on the New Economic Mechanism",
            "authors": ["Hungarian Government"],
            "publication_date": "1966-07-01",
            "document_number": "41/1966",
            "archival_reference": "MOL XIX-A-1-a-41-1966",
            "source_type": "primary_institutional",
            "purpose": "institutional_context",
            "local_path": "data/private/hist_vnext_sources/primary/decree_41_1966.pdf",
            "source_sha256": "f" * 64,
            "pdf_pages": 12,
            "pdf_page_range": "1-12",
            "printed_page_range": "1-12",
            "statistical_period": None,
            "source_available_at": "1966-07-01",
            "rights": {"license": "public_domain", "source": "archival"},
            "remote_model_upload_allowed": False,
            "data_role": DataRole.NOT_ADMITTED,
            "admission_status": "candidate",
            "observation_ids": [],
            "cited_observation_ids": [],
            "approved_excerpt_ids": ["excerpt_001"],
            "missing_fields": [],
        }
        excerpt = {
            "excerpt_id": "excerpt_001",
            "source_id": "decree_1966_41",
            "pdf_pages": [3],
            "printed_pages": [3],
            "content_hash": "ab" * 32,
            "approved_by": "admin",
            "approved_at": "2026-10-16",
            "allowed_window": "1966-01-01/1967-12-31",
            "allowed_use": "narrow_citation",
        }
        result = evaluate_source(primary_record, approved_excerpts=[excerpt])
        assert result["status"] == "admitted"
        assert result["reasons"] == []

    def test_missing_archival_reference_blocks_admission(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = {
            "source_id": "decree_1966_41",
            "work_id": "gov_decree_1966",
            "title": "Government Decree 41/1966",
            "authors": ["Hungarian Government"],
            "publication_date": "1966-07-01",
            "document_number": "41/1966",
            "archival_reference": None,  # missing
            "source_type": "primary_institutional",
            "purpose": "institutional_context",
            "local_path": "data/private/hist_vnext_sources/primary/decree_41_1966.pdf",
            "source_sha256": "f" * 64,
            "pdf_pages": 12,
            "pdf_page_range": "1-12",
            "printed_page_range": None,
            "statistical_period": None,
            "source_available_at": "1966-07-01",
            "rights": {"license": "public_domain", "source": "archival"},
            "remote_model_upload_allowed": False,
            "data_role": DataRole.NOT_ADMITTED,
            "admission_status": "candidate",
            "observation_ids": [],
            "cited_observation_ids": [],
            "approved_excerpt_ids": ["excerpt_001"],
            "missing_fields": [],
        }
        excerpt = {
            "excerpt_id": "excerpt_001",
            "source_id": "decree_1966_41",
            "pdf_pages": [3],
            "printed_pages": [3],
            "content_hash": "ab" * 32,
            "approved_by": "admin",
            "approved_at": "2026-10-16",
            "allowed_window": "1966-01-01/1967-12-31",
            "allowed_use": "narrow_citation",
        }
        result = evaluate_source(record, approved_excerpts=[excerpt])
        assert result["status"] == "blocked"
        assert any("archival_reference" in r for r in result["reasons"])

    def test_missing_usage_rights_blocks_admission(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import evaluate_source

        record = {
            "source_id": "decree_1966_41",
            "work_id": "gov_decree_1966",
            "title": "Government Decree 41/1966",
            "authors": ["Hungarian Government"],
            "publication_date": "1966-07-01",
            "document_number": "41/1966",
            "archival_reference": "MOL XIX-A-1-a-41-1966",
            "source_type": "primary_institutional",
            "purpose": "institutional_context",
            "local_path": "data/private/hist_vnext_sources/primary/decree_41_1966.pdf",
            "source_sha256": "f" * 64,
            "pdf_pages": 12,
            "pdf_page_range": "1-12",
            "printed_page_range": None,
            "statistical_period": None,
            "source_available_at": "1966-07-01",
            "rights": {"license": "unknown", "source": "unknown"},  # unknown rights
            "remote_model_upload_allowed": False,
            "data_role": DataRole.NOT_ADMITTED,
            "admission_status": "candidate",
            "observation_ids": [],
            "cited_observation_ids": [],
            "approved_excerpt_ids": [],
            "missing_fields": [],
        }
        result = evaluate_source(record, approved_excerpts=[])
        assert result["status"] == "candidate"  # rights unknown → not admitted
        assert any("rights" in r.lower() or "unknown" in r.lower() for r in result["reasons"])


# --------------------------------------------------------------------------- #
# Tests — shared observations
# --------------------------------------------------------------------------- #

class TestSharedObservations:
    def test_two_sources_same_work_not_independent(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import find_shared_observations

        records = [
            {
                "source_id": "boote_somogyi_1991_ch1",
                "work_id": _WORK_ID_IMF91,
                "observation_ids": ["obs_A", "obs_B"],
                "cited_observation_ids": ["obs_A"],
            },
            {
                "source_id": "boote_somogyi_1991_ch2",
                "work_id": _WORK_ID_IMF91_CH2,  # same work_id
                "observation_ids": ["obs_A", "obs_C"],
                "cited_observation_ids": ["obs_A"],
            },
        ]
        result = find_shared_observations(records)
        assert len(result) == 1
        assert result[0]["independent"] is False
        assert "obs_A" in result[0]["shared_observation_ids"]

    def test_two_sources_different_work_may_be_independent(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import find_shared_observations

        records = [
            {
                "source_id": "balassa_1982_swp506",
                "work_id": _WORK_ID_BALASSA,
                "observation_ids": ["obs_X"],
                "cited_observation_ids": ["obs_X"],
            },
            {
                "source_id": "kenen_1990_wp9079",
                "work_id": _WORK_ID_IMF90,
                "observation_ids": ["obs_Y"],
                "cited_observation_ids": ["obs_Y"],
            },
        ]
        result = find_shared_observations(records)
        assert len(result) == 1
        assert result[0]["independent"] is True

    def test_unknown_shared_root_returns_none(self, repo_root: Path):
        """Shared root that is unknown → independent=None (R4)."""
        from history.HIST_VNEXT.sources.admission import find_shared_observations

        records = [
            {
                "source_id": "balassa_1982_swp506",
                "work_id": _WORK_ID_BALASSA,
                "observation_ids": [],  # no known root observations
                "cited_observation_ids": ["obs_unknown_root"],
            },
            {
                "source_id": "kenen_1990_wp9079",
                "work_id": _WORK_ID_IMF90,
                "observation_ids": [],  # no known root observations
                "cited_observation_ids": ["obs_unknown_root"],  # same unknown root
            },
        ]
        result = find_shared_observations(records)
        assert len(result) == 1
        assert result[0]["independent"] is None

    def test_cited_root_observation_unknown_returns_null(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import find_shared_observations

        records = [
            {
                "source_id": "balassa_1982_swp506",
                "work_id": _WORK_ID_BALASSA,
                "observation_ids": [],
                "cited_observation_ids": ["obs_unknown"],
            },
            {
                "source_id": "kenen_1990_wp9079",
                "work_id": _WORK_ID_IMF90,
                "observation_ids": ["obs_X"],
                "cited_observation_ids": ["obs_X"],
            },
        ]
        result = find_shared_observations(records)
        # ch1 cited obs_unknown which is not in ch2's observations → independent = None
        assert len(result) == 1
        assert result[0]["independent"] is None


# --------------------------------------------------------------------------- #
# Tests — anchor crosswalk validation
# --------------------------------------------------------------------------- #

class TestAnchorCrosswalkValidation:
    def test_duplicate_anchor_id_raises(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        anchors = [
            {
                "anchor_id": "dwelling_1960_orszagos_01",
                "variable_id": "p05_census2011_dwelling_01",
                "classification": "blocked",
                "runtime_connected": False,
                "path": "data/raw/ksh_census_2011/01_1_3_1_1.xls",
            },
            {
                "anchor_id": "dwelling_1960_orszagos_01",  # duplicate
                "variable_id": "p05_census2011_dwelling_02",
                "classification": "blocked",
                "runtime_connected": False,
                "path": "data/raw/ksh_census_2011/02_1_3_1_1.xls",
            },
        ]
        with pytest.raises(ValueError, match="(?i)duplicate anchor_id"):
            validate_anchor_crosswalk(anchors)

    def test_missing_anchor_id_raises(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        anchors = [
            {
                "anchor_id": "dwelling_1960_orszagos_01",
                "variable_id": "p05_census2011_dwelling_01",
                "classification": "blocked",
                "runtime_connected": False,
                "path": "data/raw/ksh_census_2011/01_1_3_1_1.xls",
            },
            {
                # anchor_id missing
                "variable_id": "p05_census2011_dwelling_02",
                "classification": "blocked",
                "runtime_connected": False,
                "path": "data/raw/ksh_census_2011/02_1_3_1_1.xls",
            },
        ]
        with pytest.raises(ValueError, match="missing anchor_id"):
            validate_anchor_crosswalk(anchors)

    def test_national_anchor_marked_as_regional_raises(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        anchors = [
            {
                "anchor_id": "dwelling_1960_orszagos_00",
                "variable_id": "p05_census2011_dwelling_00_orszagos",
                "classification": "blocked",
                "geographic_scope": "national",
                "runtime_connected": False,
                "path": "data/raw/ksh_census_2011/00_1_3_1_1.xls",
            },
            {
                # national marked as a region
                "anchor_id": "dwelling_1960_orszagos_01",
                "variable_id": "p05_census2011_dwelling_01",
                "classification": "blocked",
                "geographic_scope": "national",  # should be regional
                "runtime_connected": False,
                "path": "data/raw/ksh_census_2011/01_1_3_1_1.xls",
            },
        ]
        # dwelling_1960_orszagos_01 is in the 1..20 regional range → must not be national
        with pytest.raises(ValueError, match="geographic_scope"):
            validate_anchor_crosswalk(anchors)

    def test_missing_classification_raises(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        anchors = [
            {
                "anchor_id": "dwelling_1960_orszagos_01",
                "variable_id": "p05_census2011_dwelling_01",
                # classification missing
                "runtime_connected": False,
                "path": "data/raw/ksh_census_2011/01_1_3_1_1.xls",
            },
        ]
        with pytest.raises(ValueError, match="classification"):
            validate_anchor_crosswalk(anchors)

    def test_1960_proxy_declared_as_1957_direct_raises(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        anchors = [
            {
                "anchor_id": "dwelling_1960_orszagos_01",
                "variable_id": "p05_census2011_dwelling_01",
                "legacy_initial_at": "1960-01-01",
                "observation_at": "1960-01-01",
                "source_evidence_kind": "proxy",
                "classification": "direct",  # wrong: 1960 proxy cannot be 1957 direct
                "runtime_connected": False,
                "path": "data/raw/ksh_census_2011/01_1_3_1_1.xls",
            },
        ]
        with pytest.raises(ValueError, match="(?i)cannot be classified as.*direct"):
            validate_anchor_crosswalk(anchors)

    def test_all_63_anchors_validated_successfully(self, repo_root: Path):
        from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

        with open(repo_root / "config/initial_state/hist_vnext_v1/anchor_crosswalk.json") as f:
            anchors = json.load(f)["records"]

        assert len(anchors) == 63
        # All correctly classified as blocked (1960 proxy → 1957 blocked)
        # legacy_artifact_ids=None because fixture anchors have matching artifact_id==variable_id
        validate_anchor_crosswalk(anchors, legacy_artifact_ids=None)  # must not raise


# --------------------------------------------------------------------------- #
# Tests — audit_h1a smoke
# --------------------------------------------------------------------------- #

class TestAuditH1A:
    def test_audit_h1a_returns_candidate_exit_1(self, repo_root: Path):
        """With no admitted excerpts and all secondary candidates, audit exits 1 (blocked)."""
        from history.HIST_VNEXT.sources.admission import audit_h1a

        result = audit_h1a(repo_root)

        assert result["exit_code"] == 1
        assert result["structural"] == "PASS"
        assert result["historical"] == "BLOCKED"
        # All 4 candidates, 0 admitted, 63 blocked anchors
        assert result["summary"]["total_candidates"] == 4
        assert result["summary"]["total_admitted"] == 0
        assert result["summary"]["total_blocked_anchors"] == 63

    def test_audit_h1a_illegal_anchor_returns_structural_blocked(self, repo_root: Path):
        """audit_h1a returns exit 2 when anchor_crosswalk.json has an invalid classification."""
        from history.HIST_VNEXT.sources.admission import audit_h1a

        # Corrupt one anchor: 1960 proxy marked as 1957 direct
        with open(repo_root / "config/initial_state/hist_vnext_v1/anchor_crosswalk.json") as f:
            data = json.load(f)

        data["records"][0]["classification"] = "direct"  # 1960 proxy cannot be direct
        with open(repo_root / "config/initial_state/hist_vnext_v1/anchor_crosswalk.json", "w") as f:
            json.dump(data, f)

        result = audit_h1a(repo_root)
        # audit_h1a catches ValueError from validate_anchor_crosswalk and returns exit 2
        assert result["exit_code"] == 2
        assert result["structural"] == "BLOCKED"
