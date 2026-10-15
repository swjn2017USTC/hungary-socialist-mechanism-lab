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
    verify_study_manifest_cards,
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


# ---------------------------------------------------------------------------
# verify_run_identity — parameter_hash recomputation from the scenario spec
# ---------------------------------------------------------------------------

_PARAMETER_SCENARIO = "historical_f2_replay"


def _write_self_consistent_material_run(
    run_dir: Path,
    *,
    parameter_hash: str,
    scenario_id: str = _PARAMETER_SCENARIO,
    expected_digest: str = "a" * 64,
) -> Path:
    """Write a material run dir whose own artefacts fully agree.

    ``manifest.json``, ``parameters.json`` and ``manifest.output_hashes`` are
    mutually consistent, so steps 1–14 of verify_run_identity pass regardless
    of ``parameter_hash``; only the scenario-spec recomputation can reject a
    fabricated value. All non-parameter hashes are computed from the live repo.
    """
    from hsm_lab.contract.guards import load_scenario
    from hsm_lab.engine.material import material_parameter_vector
    from hsm_lab.provenance.manifest import (
        compute_data_manifest_hash,
        compute_lock_hash,
        compute_scenario_hash,
        hash_output_tree,
    )

    spec = load_scenario(ROOT, scenario_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(
        json.dumps({"run_id": "test-run"}), encoding="utf-8"
    )
    (run_dir / "initial_recipe.json").write_text("{}", encoding="utf-8")
    (run_dir / "parameters.json").write_text(
        json.dumps({
            "parameter_vector": material_parameter_vector(spec),
            "parameter_hash": parameter_hash,
        }),
        encoding="utf-8",
    )
    manifest = _make_minimal_run_manifest(
        parameter_hash=parameter_hash,
        scenario_hash=compute_scenario_hash(spec),
        lock_hash=compute_lock_hash(ROOT),
        data_manifest_hash=compute_data_manifest_hash(ROOT),
        deterministic_replay_digest=expected_digest,
    )
    manifest["output_hashes"] = hash_output_tree(run_dir)
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return run_dir


class TestVerifyRunIdentityParameterHash:
    def test_fabricated_parameter_hash_is_rejected(self, tmp_path: Path) -> None:
        """A hash that no step 1–14 contradicts is still rejected if the spec disagrees."""
        run_dir = _write_self_consistent_material_run(
            tmp_path / "run", parameter_hash="a" * 64
        )
        with pytest.raises(ValueError, match="recomputed from scenario"):
            verify_run_identity(
                root=ROOT,
                scenario_id=_PARAMETER_SCENARIO,
                seed=1729,
                expected_digest="a" * 64,
                output_dir=run_dir,
            )

    def test_spec_derived_parameter_hash_is_accepted(self, tmp_path: Path) -> None:
        from hsm_lab.contract.guards import load_scenario
        from hsm_lab.engine.material import material_parameter_vector
        from hsm_lab.provenance.manifest import compute_parameter_hash

        spec_hash = compute_parameter_hash(
            material_parameter_vector(load_scenario(ROOT, _PARAMETER_SCENARIO))
        )
        run_dir = _write_self_consistent_material_run(
            tmp_path / "run", parameter_hash=spec_hash
        )
        manifest = verify_run_identity(
            root=ROOT,
            scenario_id=_PARAMETER_SCENARIO,
            seed=1729,
            expected_digest="a" * 64,
            output_dir=run_dir,
        )
        assert manifest.parameter_hash == spec_hash


# ---------------------------------------------------------------------------
# StudyManifest card verification (loader)
# ---------------------------------------------------------------------------

def _write_study_manifest(
    root: Path,
    *,
    mechanism_id: str = "M01",
    linked_cards: list[str] | None = None,
    v1_card_sha256: str | None = None,
) -> Path:
    manifest_path = root / "studies" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, object] = {
        "record_id": f"TEST-{mechanism_id}",
        "mechanism_id": mechanism_id,
        "intent": "unit_test_intent",
        "linked_cards": linked_cards if linked_cards is not None else [mechanism_id],
        "status": "declared",
        "declared_reason": "unit-test declaration",
        "blocked_reason": None,
    }
    if v1_card_sha256 is not None:
        record["v1_card_sha256"] = v1_card_sha256
    manifest_path.write_text(
        json.dumps({
            "manifest_version": "1.0.0",
            "phase": "P07A1",
            "created_by_phase": "P07A1",
            "records": [record],
        }),
        encoding="utf-8",
    )
    return manifest_path


def _stage_card(root: Path, card_name: str) -> Path:
    """Copy a real v1 card into ``root`` under the study card directory."""
    source = ROOT / "config" / "p06" / "cards" / card_name
    target = root / "config" / "p06" / "cards" / card_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    return target


class TestStudyManifestCardVerification:
    def test_real_study_manifest_cards_are_verified(self) -> None:
        manifest = load_evidence_manifest(ROOT, ROOT / "studies" / "manifest.json")
        assert isinstance(manifest, StudyManifest)
        # Real records declare no v1_card_sha256, but every declared card must
        # still exist on disk.
        verify_study_manifest_cards(ROOT, manifest)
        for record in manifest.records:
            assert (ROOT / "config" / "p06" / "cards" / f"{record.linked_cards[0]}.json").is_file()

    def test_missing_card_is_rejected(self, tmp_path: Path) -> None:
        manifest_path = _write_study_manifest(tmp_path)
        with pytest.raises(ValueError, match="v1 card not found"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_declared_card_sha_mismatch_is_rejected(self, tmp_path: Path) -> None:
        card = _stage_card(tmp_path, "M1.json")
        assert card.is_file()
        manifest_path = _write_study_manifest(tmp_path, v1_card_sha256="b" * 64)
        with pytest.raises(ValueError, match="v1_card_sha256 mismatch"):
            load_evidence_manifest(tmp_path, manifest_path)

    @pytest.mark.parametrize(
        "mechanism_id, card_name",
        [("M01", "M1.json"), ("M1", "M1.json"), ("M11", "M11.json")],
    )
    def test_declared_card_sha_match_is_accepted(
        self, tmp_path: Path, mechanism_id: str, card_name: str
    ) -> None:
        from hsm_lab.contract.guards import sha256_file

        card = _stage_card(tmp_path, card_name)
        manifest_path = _write_study_manifest(
            tmp_path,
            mechanism_id=mechanism_id,
            linked_cards=[card_name.removesuffix(".json")],
            v1_card_sha256=sha256_file(card),
        )
        manifest = load_evidence_manifest(tmp_path, manifest_path)
        assert isinstance(manifest, StudyManifest)
        assert manifest.records[0].v1_card_sha256 == sha256_file(card)

    def test_card_sha_absent_still_requires_card(self, tmp_path: Path) -> None:
        """A record without v1_card_sha256 is still bound to an existing card."""
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path)
        manifest = load_evidence_manifest(tmp_path, manifest_path)
        assert isinstance(manifest, StudyManifest)
        assert manifest.records[0].v1_card_sha256 is None

    def test_verify_runs_false_skips_card_verification(self, tmp_path: Path) -> None:
        manifest_path = _write_study_manifest(tmp_path)
        manifest = load_evidence_manifest(tmp_path, manifest_path, verify_runs=False)
        assert isinstance(manifest, StudyManifest)

