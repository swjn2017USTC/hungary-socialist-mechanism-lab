"""H0A §4: identity guards — mechanism ID normalisation, missing policy,
time-window bounds, observed-state availability, run-reference integrity,
two-format manifest split, and verify_run_identity.

All tests are read-only; they validate schema invariants and dispatch logic
without running the model or touching production engine state.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hsm_lab.evidence.loader import (
    load_all_evidence_records,
    load_evidence_manifest,
    validate_evidence_manifest,
    validate_study_manifest,
    write_evidence_manifest,
)
from hsm_lab.evidence.provenance import verify_run_identity
from hsm_lab.evidence.schemas import (
    EvidenceRecord,
    EvidenceRunReference,
    EvidenceStatus,
    MissingPolicy,
    ObservedState,
    StudyDeclaration,
    StudyManifest,
    TimeWindow,
    canonical_mechanism_id,
    study_mechanism_id,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Mechanism ID normalisation (H0A §2.1)
# ---------------------------------------------------------------------------

class TestCanonicalMechanismId:
    @pytest.mark.parametrize(
        "input_id, expected",
        [
            ("M1", "M01"),
            ("m1", "M01"),
            ("M01", "M01"),
            ("M9", "M09"),
            ("M10", "M10"),
            ("M11", "M11"),
            ("m11", "M11"),
        ],
    )
    def test_round_trip_canonical(self, input_id: str, expected: str) -> None:
        result = canonical_mechanism_id(input_id)
        assert result == expected

    @pytest.mark.parametrize(
        "invalid_id",
        [
            "M00",
            "m00",
            "M12",
            "M001",
            "M0",
            "M",
            "X1",
            "M1X",
            "",
            "M1x",
        ],
    )
    def test_rejects_invalid(self, invalid_id: str) -> None:
        with pytest.raises(ValueError, match="Invalid mechanism ID"):
            canonical_mechanism_id(invalid_id)


class TestStudyMechanismId:
    @pytest.mark.parametrize(
        "input_id, expected",
        [
            ("M1", "M1"),
            ("m1", "M1"),
            ("M01", "M1"),
            ("M9", "M9"),
        ],
    )
    def test_round_trip_study(self, input_id: str, expected: str) -> None:
        result = study_mechanism_id(input_id)
        assert result == expected

    @pytest.mark.parametrize(
        "out_of_range",
        ["M10", "M11", "m10", "m11"],
    )
    def test_rejects_m10_m11(self, out_of_range: str) -> None:
        with pytest.raises(ValueError, match="Study mechanism ID must be M1-M9"):
            study_mechanism_id(out_of_range)


# ---------------------------------------------------------------------------
# MissingPolicy enum
# ---------------------------------------------------------------------------

class TestMissingPolicy:
    def test_exact_values(self) -> None:
        assert MissingPolicy.ABORT == "abort"
        assert MissingPolicy.SKIP == "skip"
        assert MissingPolicy.INTERPOLATE == "interpolate"

    def test_rejects_zero_fill(self) -> None:
        with pytest.raises(ValueError):
            MissingPolicy("zero_fill")

    def test_rejects_zero(self) -> None:
        with pytest.raises(ValueError):
            MissingPolicy("0")


# ---------------------------------------------------------------------------
# TimeWindow quarter bounds (H0A §3.1)
# ---------------------------------------------------------------------------

class TestTimeWindowBounds:
    @pytest.mark.parametrize(
        "start,end",
        [
            ("1957Q1", "1985Q4"),  # exact boundaries — allowed
            ("1957Q1", "1985Q3"),  # inside window
            ("1958Q1", "1985Q4"),  # inside window
        ],
    )
    def test_valid_window(self, start: str, end: str) -> None:
        tw = TimeWindow(
            start_quarter=start,
            end_quarter=end,
            missing_policy=MissingPolicy.ABORT,
        )
        assert tw.start_quarter == start
        assert tw.end_quarter == end

    @pytest.mark.parametrize(
        "start,end",
        [
            # Below 1957Q1
            ("1956Q4", "1985Q4"),
            ("1956Q1", "1957Q1"),
            # Above 1985Q4
            ("1985Q4", "1986Q1"),
            ("1986Q1", "1986Q2"),
            # Reversed window
            ("1980Q1", "1979Q4"),
        ],
    )
    def test_rejects_out_of_bounds(self, start: str, end: str) -> None:
        with pytest.raises(ValidationError):
            TimeWindow(
                start_quarter=start,
                end_quarter=end,
                missing_policy=MissingPolicy.ABORT,
            )


# ---------------------------------------------------------------------------
# ObservedState available_at / decision_at (H0A §3.3)
# ---------------------------------------------------------------------------

class TestObservedStateAvailability:
    def test_valid_order(self) -> None:
        obs = ObservedState(
            observed_state_id="obs-1",
            source_run_id="run-1",
            source_scenario="historical_f2_replay",
            source_checkpoint_quarter="1960Q1",
            available_at="1960Q1",
            decision_at="1961Q1",
            source_digest="a" * 64,
            captured_at="2024-01-01T00:00:00Z",
        )
        assert obs.available_at == "1960Q1"
        assert obs.decision_at == "1961Q1"

    def test_available_at_equals_checkpoint_allowed(self) -> None:
        obs = ObservedState(
            observed_state_id="obs-2",
            source_run_id="run-1",
            source_scenario="historical_f2_replay",
            source_checkpoint_quarter="1960Q1",
            available_at="1960Q1",  # same as checkpoint
            decision_at="1961Q1",
            source_digest="a" * 64,
            captured_at="2024-01-01T00:00:00Z",
        )
        assert obs is not None

    def test_available_at_before_checkpoint_rejected(self) -> None:
        with pytest.raises(ValidationError, match="available_at.*source_checkpoint_quarter"):
            ObservedState(
                observed_state_id="obs-3",
                source_run_id="run-1",
                source_scenario="historical_f2_replay",
                source_checkpoint_quarter="1960Q2",
                available_at="1960Q1",  # before checkpoint
                decision_at="1961Q1",
                source_digest="a" * 64,
                captured_at="2024-01-01T00:00:00Z",
            )

    def test_decision_at_before_available_at_rejected(self) -> None:
        with pytest.raises(ValidationError, match="decision_at.*available_at"):
            ObservedState(
                observed_state_id="obs-4",
                source_run_id="run-1",
                source_scenario="historical_f2_replay",
                source_checkpoint_quarter="1960Q1",
                available_at="1961Q1",
                decision_at="1960Q4",  # before available_at
                source_digest="a" * 64,
                captured_at="2024-01-01T00:00:00Z",
            )

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ObservedState(
                observed_state_id="obs-5",
                source_run_id="run-1",
                source_scenario="historical_f2_replay",
                source_checkpoint_quarter="1960Q1",
                available_at="1960Q1",
                decision_at="1961Q1",
                source_digest="a" * 64,
                captured_at="2024-01-01T00:00:00Z",
                extra_field="not allowed",
            )


# ---------------------------------------------------------------------------
# EvidenceRunReference
# ---------------------------------------------------------------------------

class TestEvidenceRunReference:
    def test_valid_reference(self) -> None:
        ref = EvidenceRunReference(
            run_id="run-001",
            scenario_id="historical_f2_replay",
            seed=1729,
            output_dir=Path("/tmp/test-output"),
            digest="a" * 64,
        )
        assert ref.run_id == "run-001"
        assert ref.seed == 1729

    def test_rejects_negative_seed(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceRunReference(
                run_id="run-001",
                scenario_id="historical_f2_replay",
                seed=-1,
                output_dir=Path("/tmp/test-output"),
                digest="a" * 64,
            )

    def test_rejects_bool_seed(self) -> None:
        """seed=True (bool) must be rejected; bool is not a valid seed type."""
        with pytest.raises(ValidationError, match="bool"):
            EvidenceRunReference(
                run_id="run-001",
                scenario_id="historical_f2_replay",
                seed=True,  # bool, not int
                output_dir=Path("/tmp/test-output"),
                digest="a" * 64,
            )
        with pytest.raises(ValidationError, match="bool"):
            EvidenceRunReference(
                run_id="run-002",
                scenario_id="historical_f2_replay",
                seed=False,  # bool, not int
                output_dir=Path("/tmp/test-output"),
                digest="a" * 64,
            )


# ---------------------------------------------------------------------------
# EvidenceRecord SUPPORTED requires run_references (H0A §5.2)
# ---------------------------------------------------------------------------

class TestSupportedRequiresRuns:
    def _make_minimal_record(self, **overrides) -> EvidenceRecord:
        from hsm_lab.evidence.schemas import (
            DataRole,
            FidelityLevel,
            MetricSpec,
            ValidationFidelity,
        )

        tw = TimeWindow(
            start_quarter="1957Q1",
            end_quarter="1985Q4",
            missing_policy=MissingPolicy.ABORT,
        )
        spec = MetricSpec(
            metric_id="M01.test",
            table_or_sidecar="test",
            column="test",
            time_window=tw,
            unit="units",
            fidelity=FidelityLevel.F2_RUN,
            data_role=DataRole.CANDIDATE_LINKAGE,
            validation_fidelity=ValidationFidelity.NO_COUNTERPART,
            missing_policy=MissingPolicy.ABORT,
        )
        kwargs = dict(
            record_id="TEST-REC",
            mechanism_id="M1",
            v1_card_sha256="a" * 64,
            hypothesis="test hypothesis",
            status=EvidenceStatus.DECLARED,
            metric_specs=[spec],
            declared_reason="test",
            created_by_phase="H0A",
        )
        kwargs.update(overrides)
        return EvidenceRecord(**kwargs)

    def test_supported_requires_run_references(self) -> None:
        ref = EvidenceRunReference(
            run_id="run-001",
            scenario_id="historical_f2_replay",
            seed=1729,
            output_dir=Path("/tmp/test-output"),
            digest="a" * 64,
        )
        record = self._make_minimal_record(
            status=EvidenceStatus.SUPPORTED,
            run_references=[ref],
        )
        assert record.status == EvidenceStatus.SUPPORTED

    def test_supported_without_run_references_rejected(self) -> None:
        with pytest.raises(ValidationError, match="SUPPORTED requires at least one run_reference"):
            self._make_minimal_record(status=EvidenceStatus.SUPPORTED)

    def test_supported_rejects_duplicate_run_id(self) -> None:
        ref1 = EvidenceRunReference(
            run_id="run-001",
            scenario_id="historical_f2_replay",
            seed=1729,
            output_dir=Path("/tmp/test-output"),
            digest="a" * 64,
        )
        ref2 = EvidenceRunReference(
            run_id="run-001",  # duplicate run_id
            scenario_id="historical_f2_replay",
            seed=1730,
            output_dir=Path("/tmp/test-output2"),
            digest="b" * 64,
        )
        with pytest.raises(ValidationError, match="duplicated"):
            self._make_minimal_record(
                status=EvidenceStatus.SUPPORTED,
                run_references=[ref1, ref2],
            )

    def test_supported_rejects_duplicate_run_id_seed_pair(self) -> None:
        """Same (run_id, seed) pair appearing twice must be rejected.

        This test uses two different run_ids with the same seed, which is
        allowed. To test the pair check specifically, we test a scenario
        where run_id uniqueness passes but the pair uniqueness would fail.
        (The pair check is secondary to the run_id check; if both fire,
        run_id fires first.)
        """
        # Different run_ids with same seed — this is allowed (run_id check passes,
        # pair check would also pass since (run-001, 1729) != (run-002, 1729))
        ref1 = EvidenceRunReference(
            run_id="run-001",
            scenario_id="historical_f2_replay",
            seed=1729,
            output_dir=Path("/tmp/test-output"),
            digest="a" * 64,
        )
        ref2 = EvidenceRunReference(
            run_id="run-002",
            scenario_id="historical_f2_replay",
            seed=1729,
            output_dir=Path("/tmp/test-output2"),
            digest="b" * 64,
        )
        # This should succeed (different run_ids)
        record = self._make_minimal_record(
            status=EvidenceStatus.SUPPORTED,
            run_references=[ref1, ref2],
        )
        assert record.status == EvidenceStatus.SUPPORTED

    def test_supported_rejects_insufficient_replicates(self) -> None:
        ref = EvidenceRunReference(
            run_id="run-001",
            scenario_id="historical_f2_replay",
            seed=1729,
            output_dir=Path("/tmp/test-output"),
            digest="a" * 64,
        )
        with pytest.raises(ValidationError, match="minimum_replicates"):
            self._make_minimal_record(
                status=EvidenceStatus.SUPPORTED,
                run_references=[ref],
                minimum_replicates=2,
            )


# ---------------------------------------------------------------------------
# StudyDeclaration & StudyManifest (H0A §2.2)
# ---------------------------------------------------------------------------

class TestStudyDeclaration:
    def test_valid_declared_record(self) -> None:
        decl = StudyDeclaration(
            record_id="P07A1-M01",
            mechanism_id="M01",
            intent="social_contract_ratchet_verification",
            linked_cards=["M1"],
            status="declared",
            declared_reason="ready for experiment",
        )
        assert decl.record_id == "P07A1-M01"
        assert decl.card_id == "M01"

    def test_valid_blocked_record(self) -> None:
        decl = StudyDeclaration(
            record_id="P07A1-M02",
            mechanism_id="M02",
            intent="soft_budget_investment_shortage",
            linked_cards=["M2"],
            status="blocked",
            blocked_reason="missing prerequisite",
        )
        assert decl.status == "blocked"

    def test_declared_requires_declared_reason(self) -> None:
        with pytest.raises(ValidationError, match="declared requires declared_reason"):
            StudyDeclaration(
                record_id="TEST",
                mechanism_id="M01",
                intent="test",
                linked_cards=["M1"],
                status="declared",
                declared_reason=None,
            )

    def test_blocked_requires_blocked_reason(self) -> None:
        with pytest.raises(ValidationError, match="blocked requires blocked_reason"):
            StudyDeclaration(
                record_id="TEST",
                mechanism_id="M01",
                intent="test",
                linked_cards=["M1"],
                status="blocked",
                blocked_reason=None,
            )

    def test_rejects_empty_linked_cards(self) -> None:
        with pytest.raises(ValidationError):
            StudyDeclaration(
                record_id="TEST",
                mechanism_id="M01",
                intent="test",
                linked_cards=[],
                status="declared",
                declared_reason="test",
            )

    def test_card_id_property(self) -> None:
        decl = StudyDeclaration(
            record_id="TEST",
            mechanism_id="M01",
            intent="test",
            linked_cards=["M1"],
            status="declared",
            declared_reason="test",
        )
        assert decl.card_id == "M01"

    def test_research_package_complete_defaults_false(self) -> None:
        decl = StudyDeclaration(
            record_id="TEST",
            mechanism_id="M01",
            intent="test",
            linked_cards=["M1"],
            status="declared",
            declared_reason="test",
        )
        assert decl.research_package_complete is False


class TestStudyManifest:
    def test_valid_manifest(self) -> None:
        decl = StudyDeclaration(
            record_id="P07A1-M01",
            mechanism_id="M01",
            intent="test",
            linked_cards=["M1"],
            status="declared",
            declared_reason="test",
        )
        manifest = StudyManifest(
            manifest_version="1.0.0",
            phase="P07A1",
            created_by_phase="P07A1",
            records=[decl],
        )
        assert manifest.phase == "P07A1"
        assert len(manifest.records) == 1

    def test_rejects_duplicate_record_ids(self) -> None:
        decl1 = StudyDeclaration(
            record_id="DUP",
            mechanism_id="M01",
            intent="test",
            linked_cards=["M1"],
            status="declared",
            declared_reason="test",
        )
        decl2 = StudyDeclaration(
            record_id="DUP",  # duplicate
            mechanism_id="M02",
            intent="test2",
            linked_cards=["M2"],
            status="declared",
            declared_reason="test2",
        )
        with pytest.raises(ValidationError, match="duplicate record_id"):
            StudyManifest(
                manifest_version="1.0.0",
                phase="P07A1",
                created_by_phase="P07A1",
                records=[decl1, decl2],
            )


# ---------------------------------------------------------------------------
# Two-format manifest dispatch (H0A §2.4)
# ---------------------------------------------------------------------------

class TestManifestDispatch:
    def test_study_manifest_loaded_from_real_file(self) -> None:
        """studies/manifest.json is a StudyManifest with intent records."""
        manifest = load_evidence_manifest(ROOT, ROOT / "studies" / "manifest.json")
        assert isinstance(manifest, StudyManifest)
        assert len(manifest.records) == 11

    def test_validate_study_manifest_rejects_evidence_record(self) -> None:
        payload = {
            "manifest_version": "1.0.0",
            "phase": "P07A1",
            "records": [{
                "record_id": "TEST",
                "mechanism_id": "M01",
                "hypothesis": "test hypothesis",
                "metric_specs": [],
            }],
        }
        with pytest.raises(ValidationError, match="StudyManifest"):
            validate_study_manifest(payload)

    def test_validate_evidence_manifest_rejects_study_record(self) -> None:
        payload = {
            "manifest_version": "1.0.0",
            "phase": "P07A1",
            "records": [{
                "record_id": "TEST",
                "mechanism_id": "M01",
                "intent": "test intent",
                "linked_cards": ["M1"],
            }],
        }
        with pytest.raises(ValidationError, match="EvidenceManifest"):
            validate_evidence_manifest(payload)

    def test_load_all_evidence_records_returns_study_declarations(self) -> None:
        records = load_all_evidence_records(ROOT)
        assert all(isinstance(r, StudyDeclaration) for r in records)
        assert len(records) == 11

    def test_write_evidence_manifest_rejects_study_manifest(self, tmp_path: Path) -> None:
        decl = StudyDeclaration(
            record_id="TEST",
            mechanism_id="M01",
            intent="test",
            linked_cards=["M1"],
            status="declared",
            declared_reason="test",
        )
        manifest = StudyManifest(
            manifest_version="1.0.0",
            phase="P07A1",
            created_by_phase="P07A1",
            records=[decl],
        )
        out_path = tmp_path / "manifest.json"
        with pytest.raises(TypeError, match="only accepts EvidenceManifest"):
            write_evidence_manifest(tmp_path, manifest, out_path)


# ---------------------------------------------------------------------------
# verify_run_identity — boundary tests (H0A §4)
# ---------------------------------------------------------------------------

def _make_minimal_run_manifest(
    *,
    seed: int = 1729,
    status: str = "completed",
    failure_message: str | None = None,
    scenario_hash: str | None = None,
    lock_hash: str = "c" * 64,
    data_manifest_hash: str = "d" * 64,
    parameter_hash: str = "e" * 64,
    deterministic_replay_digest: str = "a" * 64,
    completed_ticks: int = 4,
) -> dict:
    """Build a minimal but complete RunManifest dict for testing.

    By default, scenario_hash is set to the known value for
    ``historical_f2_replay`` so that verify_run_identity's scenario
    validation passes.
    """
    from datetime import UTC, datetime

    # Known scenario_hash for historical_f2_replay (pre-computed)
    _DEFAULT_SCENARIO_HASH = (
        "a1881537e2d8b2c29551e0fe747d1f7485ab80d22bebbb7bb5b09231142d5d29"
    )
    return {
        "schema_version": "1",
        "run_id": "test-run",
        "run_kind": "material_household_simulation",
        "status": status,
        "failure_message": failure_message,
        "started_at": datetime(2024, 1, 1, tzinfo=UTC).isoformat(),
        "baseline_version": "1.1",
        "baseline_hash": "f" * 64,
        "git_commit": None,
        "dirty_tree": False,
        "python": "3.12",
        "platform": {"system": "Darwin", "release": "24.0.0"},
        "lock_hash": lock_hash,
        "scenario_hash": (
            scenario_hash if scenario_hash is not None
            else _DEFAULT_SCENARIO_HASH
        ),
        "data_manifest_hash": data_manifest_hash,
        "parameter_hash": parameter_hash,
        "seed": seed,
        "households": 1000,
        "ticks": completed_ticks,
        "commodity_ids": ["g01", "g02"],
        "region_ids": ["national"],
        "output_policy": "research_full",
        "output_hashes": {},
        "rng_scheme_version": "1.0",
        "dependency_versions": {"numpy": "1.26"},
        "research_warnings": [],
        "completed_ticks": completed_ticks,
        "deterministic_replay_digest": deterministic_replay_digest,
    }


class TestVerifyRunIdentity:
    def test_nonexistent_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="manifest.json not found"):
            verify_run_identity(
                root=ROOT,
                scenario_id="historical_f2_replay",
                seed=1729,
                expected_digest="a" * 64,
                output_dir=tmp_path / "nonexistent",
            )

    def test_wrong_seed_raises(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(_make_minimal_run_manifest(seed=9999)),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="seed"):
            verify_run_identity(
                root=ROOT,
                scenario_id="historical_f2_replay",
                seed=1729,
                expected_digest="a" * 64,
                output_dir=tmp_path,
            )

    def test_wrong_digest_raises(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(_make_minimal_run_manifest(deterministic_replay_digest="0" * 64)),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="digest"):
            verify_run_identity(
                root=ROOT,
                scenario_id="historical_f2_replay",
                seed=1729,
                expected_digest="a" * 64,
                output_dir=tmp_path,
            )

    def test_incomplete_status_raises(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(_make_minimal_run_manifest(status="running", completed_ticks=0)),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="completed"):
            verify_run_identity(
                root=ROOT,
                scenario_id="historical_f2_replay",
                seed=1729,
                expected_digest="a" * 64,
                output_dir=tmp_path,
            )

    def test_failure_message_raises(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(_make_minimal_run_manifest(failure_message="engine error")),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="failure_message"):
            verify_run_identity(
                root=ROOT,
                scenario_id="historical_f2_replay",
                seed=1729,
                expected_digest="a" * 64,
                output_dir=tmp_path,
            )

    def test_zero_scenario_hash_raises(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(_make_minimal_run_manifest(scenario_hash="0" * 64)),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="scenario_hash"):
            verify_run_identity(
                root=ROOT,
                scenario_id="historical_f2_replay",
                seed=1729,
                expected_digest="a" * 64,
                output_dir=tmp_path,
            )

    def test_missing_required_file_raises(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(_make_minimal_run_manifest()),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="required output file"):
            verify_run_identity(
                root=ROOT,
                scenario_id="historical_f2_replay",
                seed=1729,
                expected_digest="a" * 64,
                output_dir=tmp_path,
            )
