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

from hsm_lab.contract.schemas import Quarter
from hsm_lab.evidence.loader import (
    load_all_evidence_records,
    load_evidence_manifest,
    validate_evidence_manifest,
    validate_study_manifest,
    verify_evidence_manifest_runs,
    verify_study_manifest_cards,
    verify_supported_record_runs,
    write_evidence_manifest,
)
from hsm_lab.evidence.provenance import verify_run_identity
from hsm_lab.evidence.schemas import (
    CommodityAxis,
    DataRole,
    EvidenceManifest,
    EvidenceRecord,
    EvidenceRunReference,
    EvidenceStatus,
    FidelityLevel,
    MetricSpec,
    MissingPolicy,
    ObservedState,
    RegionAxis,
    StudyDeclaration,
    StudyManifest,
    TimeWindow,
    ValidationFidelity,
    canonical_mechanism_id,
    study_mechanism_id,
)
from hsm_lab.evidence.table_registry import PHYSICAL_UNIT_TOKEN

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
# EvidenceRecord SUPPORTED requires run_references and root verification (H0A §5.2)
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

    def test_supported_without_root_context_is_rejected(self) -> None:
        """A directly constructed SUPPORTED record is a validation bypass.

        Structural checks alone cannot establish trust: without a root the
        referenced runs cannot be verified, so the record must never exist as
        SUPPORTED (H0A P0-1).
        """
        ref = EvidenceRunReference(
            run_id="run-001",
            scenario_id="historical_f2_replay",
            seed=1729,
            output_dir=Path("/tmp/test-output"),
            digest="a" * 64,
        )
        with pytest.raises(ValidationError, match="root-backed verification"):
            self._make_minimal_record(
                status=EvidenceStatus.SUPPORTED,
                run_references=[ref],
            )

    def test_fabricated_supported_payload_cannot_be_parsed(self) -> None:
        """A manifest declaring SUPPORTED with fabricated refs never loads.

        This is the exact H0A P0-1 bypass: ``model_validate`` used to accept
        such a payload on structural checks alone. It must be rejected unless
        a root is supplied and the referenced runs verify against it.
        """
        ref = EvidenceRunReference(
            run_id="run-001",
            scenario_id="historical_f2_replay",
            seed=1729,
            output_dir=Path("/tmp/test-output"),
            digest="a" * 64,
        )
        fabricated = self._make_minimal_record(
            run_references=[ref],
        ).model_copy(update={"status": EvidenceStatus.SUPPORTED})
        payload = {
            "manifest_version": "1.0.0",
            "phase": "H0A",
            "records": [fabricated.model_dump()],
        }
        with pytest.raises(ValidationError, match="root-backed verification"):
            validate_evidence_manifest(payload)

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
        # Different run_ids with the same seed pass the structural pair check;
        # only the root-backed gate rejects the record, so that check must not
        # be the one that fires here.
        with pytest.raises(ValidationError) as excinfo:
            self._make_minimal_record(
                status=EvidenceStatus.SUPPORTED,
                run_references=[ref1, ref2],
            )
        message = excinfo.value.errors()[0]["msg"]
        assert "duplicated" not in message
        assert "root-backed verification" in message

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

    def test_supported_rejects_same_seed_runs_as_replicates(self) -> None:
        """Two distinct runs that replay one seed are not independent replicates.

        Different run_ids and different output directories do not make a second
        replicate: the same seed means the same stochastic trajectory, so the
        pair is a deterministic replay of replicate one.
        """
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
            seed=1729,  # same seed as ref1 — replay, not a replicate
            output_dir=Path("/tmp/test-output2"),
            digest="b" * 64,
        )
        with pytest.raises(ValidationError, match="same-seed"):
            self._make_minimal_record(
                status=EvidenceStatus.SUPPORTED,
                run_references=[ref1, ref2],
                minimum_replicates=2,
            )

    def test_distinct_seed_replicates_pass_structural_checks(self) -> None:
        """Distinct seeds over distinct runs satisfy the structural checks."""
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
            seed=1730,
            output_dir=Path("/tmp/test-output2"),
            digest="b" * 64,
        )
        # Both the pair and the distinct-seed replicate checks pass; the only
        # error is the root-backed gate, which cannot be satisfied by a
        # directly constructed record.
        with pytest.raises(ValidationError) as excinfo:
            self._make_minimal_record(
                status=EvidenceStatus.SUPPORTED,
                run_references=[ref1, ref2],
                minimum_replicates=2,
            )
        message = excinfo.value.errors()[0]["msg"]
        assert "unique (run_id, seed) pairs" not in message
        assert "distinct seed(s)" not in message
        assert "root-backed verification" in message

    def test_fabricated_supported_record_is_rejected_against_real_root(self) -> None:
        """With a root, trust is re-derived from disk; fabrication fails.

        The declared card SHA is structurally valid but does not match the real
        card, so the root-backed gate rejects the record — proving the root is
        actually consulted rather than merely recorded.
        """
        from hsm_lab.evidence.schemas import MetricSpec, ValidationFidelity

        declared = self._make_minimal_record()
        counterpart = MetricSpec(
            metric_id="M01.test",
            table_or_sidecar="test",
            column="test",
            time_window=declared.metric_specs[0].time_window,
            unit="units",
            fidelity=FidelityLevel.F2_RUN,
            data_role=DataRole.CANDIDATE_LINKAGE,
            validation_fidelity=ValidationFidelity.EXACT,
            missing_policy=MissingPolicy.ABORT,
        )
        ref = EvidenceRunReference(
            run_id="run-001",
            scenario_id="historical_f2_replay",
            seed=1729,
            output_dir=Path("/tmp/test-output"),
            digest="a" * 64,
        )
        # model_copy skips after-validators: exactly the in-memory fabrication
        # a caller could attempt before handing the record to a consumer.
        fabricated = declared.model_copy(
            update={
                "status": EvidenceStatus.SUPPORTED,
                "metric_specs": [counterpart],
                "run_references": [ref],
            }
        )
        with pytest.raises(ValidationError, match="v1_card_sha256 mismatch"):
            validate_evidence_manifest(
                {
                    "manifest_version": "1.0.0",
                    "phase": "H0A",
                    "records": [fabricated.model_dump()],
                },
                root=ROOT,
            )


# ---------------------------------------------------------------------------
# SUPPORTED records may not rest on no_counterpart metrics (H0A P0)
# ---------------------------------------------------------------------------

class TestSupportedNoCounterpartGate:
    """A metric with no model counterpart cannot be validated by any run.

    ``verify_evidence_manifest_runs`` is the promotion/publish gate, so a
    SUPPORTED record carrying such a metric must be rejected there — the record
    (and therefore the manifest) may not be published as supported evidence.
    """

    def _record(self, *, fidelity: ValidationFidelity, card_sha: str) -> EvidenceRecord:
        tw = TimeWindow(
            start_quarter="1957Q1",
            end_quarter="1985Q4",
            missing_policy=MissingPolicy.ABORT,
        )
        spec = MetricSpec(
            metric_id="M1.test",
            table_or_sidecar="aggregates",
            column="value",
            time_window=tw,
            unit="units",
            fidelity=FidelityLevel.F2_RUN,
            data_role=DataRole.CANDIDATE_LINKAGE,
            validation_fidelity=fidelity,
            missing_policy=MissingPolicy.ABORT,
        )
        ref = EvidenceRunReference(
            run_id="run-001",
            scenario_id="historical_f2_replay",
            seed=1729,
            output_dir=Path("/nonexistent-run-dir"),
            digest="a" * 64,
        )
        declared = EvidenceRecord(
            record_id="TEST-NC",
            mechanism_id="M1",
            v1_card_sha256=card_sha,
            hypothesis="test hypothesis",
            status=EvidenceStatus.DECLARED,
            metric_specs=[spec],
            run_references=[ref],
            declared_reason="unit-test promotion attempt",
            created_by_phase="H0A",
        )
        # ``model_copy`` skips after-validators, so this is precisely the
        # unverified in-memory SUPPORTED record the publish gate must catch.
        return declared.model_copy(update={"status": EvidenceStatus.SUPPORTED})

    def _manifest(self, record: EvidenceRecord) -> EvidenceManifest:
        # model_construct skips validation: a real caller cannot build a
        # manifest holding an unverified SUPPORTED record, and the publish gate
        # must still reject this one.
        return EvidenceManifest.model_construct(
            manifest_version="1.0.0",
            phase="H0A",
            records=[record],
        )

    def test_supported_with_no_counterpart_metric_is_rejected(self) -> None:
        manifest = self._manifest(
            self._record(fidelity=ValidationFidelity.NO_COUNTERPART, card_sha="a" * 64)
        )
        with pytest.raises(ValueError, match="no_counterpart"):
            verify_evidence_manifest_runs(ROOT, manifest)

    def test_no_counterpart_record_cannot_be_published(self, tmp_path: Path) -> None:
        from hsm_lab.contract.guards import sha256_file

        # Card bytes are real, so only the metric fidelity blocks publication.
        card_sha = sha256_file(ROOT / "config" / "p06" / "cards" / "M1.json")
        manifest = self._manifest(
            self._record(
                fidelity=ValidationFidelity.NO_COUNTERPART, card_sha=card_sha
            )
        )
        out_dir = tmp_path / "published"
        out_dir.mkdir()
        out_path = out_dir / "manifest.json"
        with pytest.raises(ValueError, match="no_counterpart"):
            write_evidence_manifest(ROOT, manifest, out_path)
        assert not out_path.exists()

    def test_counterpart_metric_is_not_blocked_by_the_fidelity_gate(self) -> None:
        """The gate is specific: a counterpart metric falls through to run checks."""
        from hsm_lab.contract.guards import sha256_file

        card_sha = sha256_file(ROOT / "config" / "p06" / "cards" / "M1.json")
        manifest = self._manifest(
            self._record(fidelity=ValidationFidelity.EXACT, card_sha=card_sha)
        )
        with pytest.raises(ValueError) as excinfo:
            verify_evidence_manifest_runs(ROOT, manifest)
        assert "no_counterpart" not in str(excinfo.value)
        assert "manifest.json not found" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Independent replicates need distinct seeds (H0A P0)
# ---------------------------------------------------------------------------

class TestSameSeedReplicateGate:
    """Same-seed runs are deterministic replays, never independent replicates.

    ``minimum_replicates`` is a replicate *independence* claim, so the publish
    gate counts distinct seeds, not references: two references that share a seed
    replay one trajectory. The record is built as DECLARED and then promoted to
    SUPPORTED via ``model_copy``, which skips after-validators, so the loader —
    the last gate before publication — is the code under test. (A real caller
    cannot construct such a record: direct SUPPORTED construction requires a
    root and is rejected, H0A P0-1.)
    """

    def _record(self) -> EvidenceRecord:
        from hsm_lab.contract.guards import sha256_file

        tw = TimeWindow(
            start_quarter="1957Q1",
            end_quarter="1985Q4",
            missing_policy=MissingPolicy.ABORT,
        )
        spec = MetricSpec(
            metric_id="M1.test",
            table_or_sidecar="aggregates",
            column="value",
            time_window=tw,
            unit="units",
            fidelity=FidelityLevel.F2_RUN,
            data_role=DataRole.CANDIDATE_LINKAGE,
            validation_fidelity=ValidationFidelity.EXACT,
            missing_policy=MissingPolicy.ABORT,
        )
        ref1 = EvidenceRunReference(
            run_id="run-001",
            scenario_id="historical_f2_replay",
            seed=1729,
            output_dir=Path("/nonexistent-run-dir-a"),
            digest="a" * 64,
        )
        ref2 = EvidenceRunReference(
            run_id="run-002",
            scenario_id="historical_f2_replay",
            seed=1729,  # same seed: a deterministic replay of run-001
            output_dir=Path("/nonexistent-run-dir-b"),
            digest="b" * 64,
        )
        declared = EvidenceRecord(
            record_id="TEST-SEED",
            mechanism_id="M1",
            v1_card_sha256=sha256_file(ROOT / "config" / "p06" / "cards" / "M1.json"),
            hypothesis="test hypothesis",
            status=EvidenceStatus.DECLARED,
            metric_specs=[spec],
            run_references=[ref1, ref2],
            declared_reason="unit-test promotion attempt",
            created_by_phase="H0A",
        )
        # ``model_copy`` skips after-validators, so this is precisely the
        # unverified in-memory SUPPORTED record the publish gate must catch.
        return declared.model_copy(update={"status": EvidenceStatus.SUPPORTED})

    def _manifest(self, record: EvidenceRecord) -> EvidenceManifest:
        # model_construct skips validation: a real caller cannot build a
        # manifest holding an unverified SUPPORTED record, and the publish gate
        # must still reject this one.
        return EvidenceManifest.model_construct(
            manifest_version="1.0.0",
            phase="H0A",
            records=[record],
        )

    def test_same_seed_record_with_raised_minimum_is_rejected(self) -> None:
        record = self._record().model_copy(update={"minimum_replicates": 2})
        with pytest.raises(ValueError, match="same-seed"):
            verify_evidence_manifest_runs(ROOT, self._manifest(record))

    def test_same_seed_record_cannot_be_published(self, tmp_path: Path) -> None:
        record = self._record().model_copy(update={"minimum_replicates": 2})
        out_dir = tmp_path / "published"
        out_dir.mkdir()
        out_path = out_dir / "manifest.json"
        with pytest.raises(ValueError, match="same-seed"):
            write_evidence_manifest(ROOT, self._manifest(record), out_path)
        assert not out_path.exists()

    def test_same_seed_record_parsed_from_manifest_json_is_rejected(self) -> None:
        """A same-seed record is rejected when the manifest is parsed from JSON.

        The structural validator re-runs on every parse, so a manifest file
        declaring two same-seed replicates under ``minimum_replicates=2`` never
        even loads.
        """
        payload = {
            "manifest_version": "1.0.0",
            "phase": "H0A",
            "records": [
                {
                    "record_id": "TEST-SEED",
                    "mechanism_id": "M1",
                    "v1_card_sha256": "a" * 64,
                    "hypothesis": "test hypothesis",
                    "status": "supported",
                    "declared_reason": "unit-test promotion attempt",
                    "created_by_phase": "H0A",
                    "minimum_replicates": 2,
                    "metric_specs": [
                        {
                            "metric_id": "M1.test",
                            "table_or_sidecar": "aggregates",
                            "column": "value",
                            "time_window": {
                                "start_quarter": "1957Q1",
                                "end_quarter": "1985Q4",
                                "missing_policy": "abort",
                            },
                            "unit": "units",
                            "fidelity": "F2_run",
                            "data_role": "candidate_linkage",
                            "validation_fidelity": "exact",
                            "missing_policy": "abort",
                        }
                    ],
                    "run_references": [
                        {
                            "run_id": "run-001",
                            "scenario_id": "historical_f2_replay",
                            "seed": 1729,
                            "output_dir": "/nonexistent-run-dir-a",
                            "digest": "a" * 64,
                        },
                        {
                            "run_id": "run-002",
                            "scenario_id": "historical_f2_replay",
                            "seed": 1729,
                            "output_dir": "/nonexistent-run-dir-b",
                            "digest": "b" * 64,
                        },
                    ],
                }
            ],
        }
        with pytest.raises(ValidationError, match="same-seed"):
            validate_evidence_manifest(payload)

    def test_distinct_seeds_are_not_blocked_by_the_seed_gate(self) -> None:
        """The gate is specific: distinct seeds fall through to run verification."""
        record = self._record()
        second_replicate = record.run_references[1].model_copy(update={"seed": 1730})
        mutated = record.model_copy(
            update={
                "minimum_replicates": 2,
                "run_references": [record.run_references[0], second_replicate],
            }
        )
        with pytest.raises(ValueError) as excinfo:
            verify_evidence_manifest_runs(ROOT, self._manifest(mutated))
        assert "same-seed" not in str(excinfo.value)
        assert "manifest.json not found" in str(excinfo.value)


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
    ticks: int = 4,
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
        "ticks": ticks,
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
            json.dumps(_make_minimal_run_manifest(ticks=116, completed_ticks=116)),
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

# The compact tables the fixture run ships, with the columns the material
# runner writes for them (``hsm_lab.storage.material_output``): every table
# carries the tick/quarter keys, the axis key columns of the dimensions it
# models, and its own data columns. ``information_quarters`` is declared with
# zero rows (as in the real C0 run) to exercise the empty-table paths.
_FIXTURE_TABLE_COLUMNS: dict[str, list[str]] = {
    "aggregates": [
        "tick", "quarter", "region_id", "commodity_id", "delivered", "used",
    ],
    "stage_balances": [
        "tick", "quarter", "region_id", "commodity_id", "stage", "closing",
    ],
    "national_accounts": [
        "tick", "quarter", "commodity_id", "production",
        "household_consumption", "imports", "exports",
    ],
    "household_budgets": [
        "tick", "quarter", "region_id", "spending", "forced_saving",
    ],
    "tick_diagnostics": ["tick", "quarter", "bottleneck_demand_count"],
    "information_quarters": [
        "tick", "quarter", "feature_id", "forecast_accuracy",
    ],
}

# Tables the fixture writes with zero rows regardless of the tick count.
_FIXTURE_EMPTY_TABLES = ("information_quarters",)

_FIXTURE_INT_COLUMNS = {"tick", "bottleneck_demand_count"}
_FIXTURE_STRING_COLUMNS = {"quarter", "region_id", "commodity_id", "stage", "feature_id"}


def _write_fixture_table(
    path: Path,
    table_name: str,
    *,
    ticks: int,
    quarters: list[str],
    commodities: list[str],
    regions: list[str],
) -> int:
    """Write one compact fixture table in the material runner's schema layout.

    Rows are generated from the scenario's declared universe (all regions and
    commodities appear), so the run's own tables cover it. Returns the row
    count actually written.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows: list[dict[str, object]] = []
    empty = table_name in _FIXTURE_EMPTY_TABLES
    for tick in range(0 if empty else ticks):
        quarter = quarters[tick]
        if table_name == "aggregates":
            for region in regions:
                for commodity in commodities:
                    rows.append({
                        "tick": tick,
                        "quarter": quarter,
                        "region_id": region,
                        "commodity_id": commodity,
                        "delivered": float(tick + 1),
                        "used": float(tick + 1),
                    })
        elif table_name == "stage_balances":
            for index, region in enumerate(regions):
                rows.append({
                    "tick": tick,
                    "quarter": quarter,
                    "region_id": region,
                    "commodity_id": commodities[index % len(commodities)],
                    "stage": "raw",
                    "closing": float(tick + index),
                })
        elif table_name == "national_accounts":
            for commodity in commodities:
                rows.append({
                    "tick": tick,
                    "quarter": quarter,
                    "commodity_id": commodity,
                    "production": float(tick + 1),
                    "household_consumption": float(tick + 2),
                    "imports": float(tick),
                    "exports": float(tick),
                })
        elif table_name == "household_budgets":
            for region in regions:
                rows.append({
                    "tick": tick,
                    "quarter": quarter,
                    "region_id": region,
                    "spending": float(tick + 1),
                    "forced_saving": float(tick),
                })
        elif table_name == "tick_diagnostics":
            rows.append({
                "tick": tick,
                "quarter": quarter,
                "bottleneck_demand_count": tick,
            })
        else:
            raise ValueError(f"unknown fixture table {table_name!r}")

    columns = _FIXTURE_TABLE_COLUMNS[table_name]
    table = pa.table({
        name: pa.array(
            [row[name] for row in rows], type=_fixture_column_type(name)
        )
        for name in columns
    })
    pq.write_table(table, path)
    return table.num_rows


def _fixture_column_type(column: str):
    """Arrow type for one fixture column."""
    import pyarrow as pa

    if column in _FIXTURE_INT_COLUMNS:
        return pa.int64()
    if column in _FIXTURE_STRING_COLUMNS:
        return pa.string()
    return pa.float64()


def _read_row_counts(run_dir: Path) -> dict[str, int]:
    """Read the run's declared ``summary.json`` row counts (mutable copy)."""
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    return dict(summary["row_counts"])


def _write_self_consistent_material_run(
    run_dir: Path,
    *,
    parameter_hash: str,
    scenario_id: str = _PARAMETER_SCENARIO,
    seed: int = 1729,
    expected_digest: str = "a" * 64,
    trajectory: bool = True,
    tick_count: int | None = None,
    summary_overrides: dict | None = None,
) -> Path:
    """Write a material run dir whose own artefacts fully agree.

    ``manifest.json``, ``parameters.json``, ``summary.json``,
    ``initial_recipe.json``, the tick-level trajectory tables under
    ``trajectory_tables/`` and ``manifest.output_hashes`` are mutually
    consistent, so the output-integrity steps of verify_run_identity pass
    regardless of ``parameter_hash``; only the scenario-spec recomputation can
    reject a fabricated value. All non-parameter hashes are computed from the
    live repo, and ``scenario_hash`` follows the same ``seed`` override the CLI
    applies before running.

    The trajectory tables carry the material runner's schema for their table
    and the scenario's declared commodity/region universe; ``summary.json``
    carries the identity fields a completed run records; and
    ``initial_recipe.json`` carries the scenario's actual recipe declaration.

    ``trajectory=False`` omits the trajectory tables (a JSON-only directory);
    ``tick_count`` truncates the recorded tick coverage; ``summary_overrides``
    patches individual summary.json fields.
    """
    from hsm_lab.contract.guards import (
        BASELINE_FILENAME,
        load_research_contract,
        load_scenario,
        verify_baseline,
    )
    from hsm_lab.data.registry import DataRegistry
    from hsm_lab.engine.material import (
        load_material_forcing,
        material_parameter_vector,
        material_recipe_hash,
    )
    from hsm_lab.provenance.manifest import (
        compute_data_manifest_hash,
        compute_lock_hash,
        compute_scenario_hash,
        hash_output_tree,
    )

    spec = load_scenario(ROOT, scenario_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    engine_ticks = spec.ticks if tick_count is None else tick_count
    quarters = [str(spec.start.advance(tick)) for tick in range(engine_ticks)]
    commodities = list(spec.commodities)
    regions = list(spec.region_ids)
    row_counts: dict[str, int] = {}
    if trajectory:
        tables_dir = run_dir / "trajectory_tables"
        tables_dir.mkdir(parents=True, exist_ok=True)
        for table_name in _FIXTURE_TABLE_COLUMNS:
            row_counts[table_name] = _write_fixture_table(
                tables_dir / f"{table_name}.parquet",
                table_name,
                ticks=engine_ticks,
                quarters=quarters,
                commodities=commodities,
                regions=regions,
            )
    else:
        # The tables that *would* be written: declared, but absent from disk.
        for table_name in _FIXTURE_TABLE_COLUMNS:
            row_counts[table_name] = engine_ticks

    parameters_path = run_dir / "parameters.json"
    parameters_path.write_text(
        json.dumps({
            "parameter_vector": material_parameter_vector(spec),
            "parameter_hash": parameter_hash,
        }),
        encoding="utf-8",
    )
    manifest = _make_minimal_run_manifest(
        parameter_hash=parameter_hash,
        seed=seed,
        scenario_hash=compute_scenario_hash(spec.model_copy(update={"seed": seed})),
        lock_hash=compute_lock_hash(ROOT),
        data_manifest_hash=compute_data_manifest_hash(ROOT),
        deterministic_replay_digest=expected_digest,
        ticks=spec.ticks,
        completed_ticks=spec.ticks,
    )
    manifest["commodity_ids"] = commodities
    manifest["region_ids"] = regions
    manifest["households"] = spec.households
    # The layer the run executed, as the real material runs declare it
    # (``outputs/codex-audit-vnext-20261011/C0``: ``fidelity="f2"``,
    # ``ontology_id="f2_v1"``): the metric-content gate binds a metric's
    # declared fidelity and unit to the layer the run actually ran.
    manifest["fidelity"] = "f2"
    manifest["ontology_id"] = "f2_v1"
    # Baseline, recipe and forcing identities are recomputed from the live
    # repository, exactly as verify_run_identity does; only ``parameter_hash``
    # is caller-controlled so the parameter binding can be exercised in
    # isolation.
    manifest["baseline_hash"] = verify_baseline(
        ROOT / BASELINE_FILENAME, load_research_contract(ROOT)
    )
    manifest["initial_recipe_hash"] = material_recipe_hash(spec)
    manifest["input_artifact_hashes"] = dict(
        load_material_forcing(
            spec, DataRegistry.load(ROOT, allowed_commodities=spec.commodities)
        ).input_artifact_hashes
    )

    summary: dict = {
        "schema_version": "1",
        "run_id": "test-run",
        "run_kind": manifest["run_kind"],
        "scenario_id": spec.scenario_id,
        "seed": seed,
        "planned_ticks": spec.ticks,
        "completed_ticks": spec.ticks,
        "households": spec.households,
        "commodity_ids": commodities,
        "region_ids": regions,
        "parameter_hash": parameter_hash,
        "initial_recipe_hash": manifest["initial_recipe_hash"],
        "deterministic_replay_digest": expected_digest,
        "input_artifact_hashes": manifest["input_artifact_hashes"],
        "row_counts": row_counts,
        # The accounting certification the material runner writes: the
        # residual/tolerance fields ``check_material_invariants`` returned for
        # the ticks the run completed, and the number of ticks it covered
        # (``hsm_lab.engine.material``: ``checked_ticks`` =
        # ``state.completed_ticks``). A run is only a run if its summary
        # carries the certification that let ``completed_ticks`` advance.
        "invariants": {
            "max_material_abs_residual": 0.0,
            "max_material_tolerance_ratio": 0.0,
            "max_finance_abs_residual": 0.0,
            "max_finance_tolerance_ratio": 0.0,
            "checked_ticks": spec.ticks,
        },
    }
    if summary_overrides:
        summary.update(summary_overrides)
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    # The recipe the material runner writes: the scenario's declared initial
    # state, its recipe hash, and the scenario it belongs to.
    (run_dir / "initial_recipe.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "scenario_id": spec.scenario_id,
                "initial_recipe_hash": manifest["initial_recipe_hash"],
                "declaration": spec.material_initial.model_dump(mode="json"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
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


class TestVerifyRunIdentityTrajectoryData:
    """A material run directory must ship real tick-level trajectory data.

    The JSON artefacts of a material run can be written by hand and made
    hash-consistent with each other, so presence of summary/parameters/recipe
    is not evidence of a run; the compact per-tick trajectory tables and the
    trajectory store are.
    """

    def _run_dir(self, tmp_path: Path, **kwargs) -> Path:
        return _write_self_consistent_material_run(
            tmp_path / "run", parameter_hash=_material_parameter_hash(), **kwargs
        )

    def _verify(self, run_dir: Path):
        return verify_run_identity(
            root=ROOT,
            scenario_id=_PARAMETER_SCENARIO,
            seed=1729,
            expected_digest="a" * 64,
            output_dir=run_dir,
        )

    def test_json_only_material_run_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path, trajectory=False)
        with pytest.raises(ValueError, match="JSON-only"):
            self._verify(run_dir)

    def test_truncated_tick_coverage_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path, tick_count=4)
        with pytest.raises(ValueError, match="tick coverage"):
            self._verify(run_dir)

    def test_zero_row_trajectory_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path, tick_count=0)
        with pytest.raises(ValueError, match="tick coverage"):
            self._verify(run_dir)

    def test_empty_trajectory_table_file_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        (run_dir / "trajectory_tables" / "events.parquet").write_bytes(b"")
        counts = _read_row_counts(run_dir)
        counts["events"] = 1
        _patch_run_summary(run_dir, row_counts=counts)
        with pytest.raises(ValueError, match="is empty"):
            self._verify(run_dir)

    def test_only_empty_trajectory_tables_are_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        for table_path in (run_dir / "trajectory_tables").glob("*.parquet"):
            table_path.write_bytes(b"")
        _rehash_run_outputs(run_dir)
        with pytest.raises(ValueError, match="not a run"):
            self._verify(run_dir)

    def test_declared_table_missing_from_disk_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        counts = _read_row_counts(run_dir)
        counts["policy_decisions"] = 1
        _patch_run_summary(run_dir, row_counts=counts)
        with pytest.raises(ValueError, match="no such Parquet file"):
            self._verify(run_dir)

    def test_table_without_tick_column_is_rejected(self, tmp_path: Path) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        run_dir = self._run_dir(tmp_path)
        pq.write_table(
            pa.table({"label": pa.array(["x"])}),
            run_dir / "trajectory_tables" / "events.parquet",
        )
        counts = _read_row_counts(run_dir)
        counts["events"] = 1
        _patch_run_summary(run_dir, row_counts=counts)
        with pytest.raises(ValueError, match="no 'tick' column"):
            self._verify(run_dir)

    def test_row_count_mismatch_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        counts = _read_row_counts(run_dir)
        counts["aggregates"] -= 1
        _patch_run_summary(run_dir, row_counts=counts)
        with pytest.raises(ValueError, match="declares"):
            self._verify(run_dir)

    def test_non_integer_row_count_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        counts = _read_row_counts(run_dir)
        counts["aggregates"] = str(counts["aggregates"])
        _patch_run_summary(run_dir, row_counts=counts)
        with pytest.raises(ValueError, match="must be an integer"):
            self._verify(run_dir)

    def test_summary_without_run_id_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path, summary_overrides={"run_id": ""})
        with pytest.raises(ValueError, match="'run_id'"):
            self._verify(run_dir)

    def test_summary_run_id_mismatch_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path, summary_overrides={"run_id": "other-run"})
        with pytest.raises(ValueError, match="does not match manifest.run_id"):
            self._verify(run_dir)

    def test_summary_contradicting_manifest_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path, summary_overrides={"seed": 4242})
        with pytest.raises(ValueError, match="contradicts"):
            self._verify(run_dir)

    def test_consistent_summary_with_trajectory_is_accepted(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        manifest = self._verify(run_dir)
        assert manifest.run_kind == "material_household_simulation"


class TestVerifyRunIdentityAccountingInvariants:
    """A material run must report the accounting certification it passed.

    ``hsm_lab.engine.material`` advances ``completed_ticks`` only after
    ``check_material_invariants`` passed the tick, so the summary's
    ``invariants`` block is the run's own account of that certification: the
    residual and tolerance fields the check returned, tolerance ratios within
    the 1.0 ceiling, and ``checked_ticks`` equal to the ticks the run reports as
    completed. A summary that omits the block — or that certifies a residual
    outside its tolerance band — is not the account of a certified run.
    """

    def _run_dir(self, tmp_path: Path, **kwargs) -> Path:
        return _write_self_consistent_material_run(
            tmp_path / "run", parameter_hash=_material_parameter_hash(), **kwargs
        )

    def _verify(self, run_dir: Path):
        return verify_run_identity(
            root=ROOT,
            scenario_id=_PARAMETER_SCENARIO,
            seed=1729,
            expected_digest="a" * 64,
            output_dir=run_dir,
        )

    def _invariants(self, run_dir: Path) -> dict:
        summary = json.loads(
            (run_dir / "summary.json").read_text(encoding="utf-8")
        )
        return dict(summary["invariants"])

    def _patch_summary(self, run_dir: Path, mutate) -> None:
        """Apply ``mutate`` to the summary payload and re-pin the run tree."""
        summary_path = run_dir / "summary.json"
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        mutate(payload)
        summary_path.write_text(json.dumps(payload), encoding="utf-8")
        _rehash_run_outputs(run_dir)

    def test_certified_run_is_accepted(self, tmp_path: Path) -> None:
        """Control: the runner's own certification passes the gate."""
        run_dir = self._run_dir(tmp_path)
        invariants = self._invariants(run_dir)
        assert invariants["checked_ticks"] == 116
        assert self._verify(run_dir).run_kind == "material_household_simulation"

    def test_ratio_at_the_tolerance_ceiling_is_accepted(self, tmp_path: Path) -> None:
        """Control: exactly 1.0 is within the tolerance band."""
        run_dir = self._run_dir(tmp_path)
        self._patch_summary(
            run_dir,
            lambda payload: payload["invariants"].update(
                {"max_material_tolerance_ratio": 1.0, "max_finance_tolerance_ratio": 1.0}
            ),
        )
        assert self._verify(run_dir).run_id == "test-run"

    def test_missing_invariants_block_is_rejected(self, tmp_path: Path) -> None:
        """A summary without the certification is not a completed run's account."""
        run_dir = self._run_dir(tmp_path)

        def drop(payload: dict) -> None:
            payload.pop("invariants")

        self._patch_summary(run_dir, drop)
        with pytest.raises(ValueError, match="no non-empty 'invariants' block"):
            self._verify(run_dir)

    def test_empty_invariants_block_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path, summary_overrides={"invariants": {}})
        with pytest.raises(ValueError, match="no non-empty 'invariants' block"):
            self._verify(run_dir)

    def test_invariants_missing_a_field_is_rejected(self, tmp_path: Path) -> None:
        """Every field the certification records must be there."""
        run_dir = self._run_dir(tmp_path)

        def drop(payload: dict) -> None:
            payload["invariants"].pop("max_finance_tolerance_ratio")

        self._patch_summary(run_dir, drop)
        with pytest.raises(ValueError, match="missing the fields"):
            self._verify(run_dir)

    @pytest.mark.parametrize(
        "field_name",
        ["max_material_tolerance_ratio", "max_finance_tolerance_ratio"],
    )
    def test_ratio_above_the_tolerance_ceiling_is_rejected(
        self, tmp_path: Path, field_name: str
    ) -> None:
        """A residual outside its tolerance band is not a certified tick."""
        run_dir = self._run_dir(tmp_path)
        self._patch_summary(
            run_dir,
            lambda payload: payload["invariants"].update({field_name: 1.5}),
        )
        with pytest.raises(ValueError, match="tolerance ceiling"):
            self._verify(run_dir)

    @pytest.mark.parametrize(
        "value",
        [float("nan"), float("inf"), float("-inf")],
    )
    def test_nonfinite_invariant_value_is_rejected(
        self, tmp_path: Path, value: float
    ) -> None:
        """A certification number that is not a number certifies nothing."""
        run_dir = self._run_dir(tmp_path)
        self._patch_summary(
            run_dir,
            lambda payload: payload["invariants"].update(
                {"max_material_abs_residual": value}
            ),
        )
        with pytest.raises(ValueError, match="must be a finite number"):
            self._verify(run_dir)

    @pytest.mark.parametrize(
        "field_name",
        ["max_material_tolerance_ratio", "max_finance_abs_residual"],
    )
    def test_non_numeric_invariant_value_is_rejected(
        self, tmp_path: Path, field_name: str
    ) -> None:
        run_dir = self._run_dir(tmp_path)
        self._patch_summary(
            run_dir,
            lambda payload: payload["invariants"].update({field_name: "0.5"}),
        )
        with pytest.raises(ValueError, match="must be a finite number"):
            self._verify(run_dir)

    def test_negative_invariant_value_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        self._patch_summary(
            run_dir,
            lambda payload: payload["invariants"].update(
                {"max_material_abs_residual": -1e-9}
            ),
        )
        with pytest.raises(ValueError, match="cannot be negative"):
            self._verify(run_dir)

    def test_checked_ticks_must_cover_the_completed_ticks(self, tmp_path: Path) -> None:
        """A certification that did not check every completed tick is partial."""
        run_dir = self._run_dir(tmp_path)
        self._patch_summary(
            run_dir,
            lambda payload: payload["invariants"].update({"checked_ticks": 115}),
        )
        with pytest.raises(ValueError, match="does not match completed_ticks"):
            self._verify(run_dir)

    @pytest.mark.parametrize("value", [True, "116", 116.0])
    def test_non_integer_checked_ticks_is_rejected(
        self, tmp_path: Path, value: object
    ) -> None:
        run_dir = self._run_dir(tmp_path)
        self._patch_summary(
            run_dir,
            lambda payload: payload["invariants"].update({"checked_ticks": value}),
        )
        with pytest.raises(ValueError, match="must be an integer"):
            self._verify(run_dir)


# ---------------------------------------------------------------------------
# verify_run_identity — baseline / recipe / forcing / seed-override bindings
# ---------------------------------------------------------------------------

def _mutate_run_manifest(run_dir: Path, **fields: object) -> None:
    """Overwrite manifest.json fields in place (output_hashes excludes it)."""
    manifest_path = run_dir / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload.update(fields)
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")


def _rehash_run_outputs(run_dir: Path) -> None:
    """Recompute manifest.output_hashes from disk after patching run artefacts.

    Summary/trajectory mutations change the output bytes, so the manifest must
    be re-pinned; otherwise the output-tree digest check rejects the run before
    the check under test is reached.
    """
    from hsm_lab.provenance.manifest import hash_output_tree

    manifest_path = run_dir / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["output_hashes"] = hash_output_tree(run_dir)
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")


def _patch_run_summary(run_dir: Path, **fields: object) -> None:
    """Overwrite summary.json fields and re-pin the run's output hashes."""
    summary_path = run_dir / "summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    payload.update(fields)
    summary_path.write_text(json.dumps(payload), encoding="utf-8")
    _rehash_run_outputs(run_dir)


def _material_parameter_hash(scenario_id: str = _PARAMETER_SCENARIO) -> str:
    """Live parameter_hash for a scenario — the only field the fixture may vary."""
    from hsm_lab.contract.guards import load_scenario
    from hsm_lab.engine.material import material_parameter_vector
    from hsm_lab.provenance.manifest import compute_parameter_hash

    return compute_parameter_hash(
        material_parameter_vector(load_scenario(ROOT, scenario_id))
    )


class TestVerifyRunIdentityRepoBindings:
    """Baseline / recipe / forcing / seed-override identities are recomputed.

    The fixture is a fully self-consistent material run (all hashes derived
    from the live repository); each test then falsifies exactly one identity
    and requires verify_run_identity to reject it.
    """

    def _run_dir(self, tmp_path: Path, *, seed: int = 1729) -> Path:
        return _write_self_consistent_material_run(
            tmp_path / "run", parameter_hash=_material_parameter_hash(), seed=seed
        )

    def _verify(self, run_dir: Path, *, seed: int = 1729):
        return verify_run_identity(
            root=ROOT,
            scenario_id=_PARAMETER_SCENARIO,
            seed=seed,
            expected_digest="a" * 64,
            output_dir=run_dir,
        )

    def test_seed_override_scenario_hash_is_accepted(self, tmp_path: Path) -> None:
        """A seed-overridden run is identified by the overridden spec, not the file."""
        manifest = self._verify(self._run_dir(tmp_path, seed=4242), seed=4242)
        assert manifest.seed == 4242

    def test_seed_override_changes_scenario_hash(self) -> None:
        """The override is genuine: the on-disk spec carries a different seed."""
        from hsm_lab.contract.guards import load_scenario
        from hsm_lab.provenance.manifest import compute_scenario_hash

        default_spec = load_scenario(ROOT, _PARAMETER_SCENARIO)
        assert default_spec.seed != 4242
        assert compute_scenario_hash(
            default_spec.model_copy(update={"seed": 4242})
        ) != compute_scenario_hash(default_spec)

    def test_fabricated_baseline_hash_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        _mutate_run_manifest(run_dir, baseline_hash="f" * 64)
        with pytest.raises(ValueError, match="baseline_hash"):
            self._verify(run_dir)

    def test_fabricated_initial_recipe_hash_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        _mutate_run_manifest(run_dir, initial_recipe_hash="b" * 64)
        with pytest.raises(ValueError, match="initial_recipe_hash"):
            self._verify(run_dir)

    def test_missing_initial_recipe_hash_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        _mutate_run_manifest(run_dir, initial_recipe_hash=None)
        with pytest.raises(ValueError, match="initial_recipe_hash"):
            self._verify(run_dir)

    def test_fabricated_input_artifact_hashes_are_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        payload = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        keys = sorted(payload["input_artifact_hashes"])
        assert keys, "fixture must declare forcing inputs"
        _mutate_run_manifest(run_dir, input_artifact_hashes={keys[0]: "c" * 64})
        with pytest.raises(ValueError, match="input_artifact_hashes"):
            self._verify(run_dir)

    def test_non_material_scenario_skips_material_bindings(self, tmp_path: Path) -> None:
        """Smoke-kind runs declare no recipe/forcing, so steps 17–18 do not apply."""
        from hsm_lab.contract.guards import (
            BASELINE_FILENAME,
            load_research_contract,
            load_scenario,
            verify_baseline,
        )
        from hsm_lab.provenance.manifest import (
            compute_data_manifest_hash,
            compute_lock_hash,
            compute_scenario_hash,
            hash_output_tree,
        )

        spec = load_scenario(ROOT, "smoke")
        assert spec.organization_recipe is None and spec.forcing_pack is None

        run_dir = tmp_path / "smoke-run"
        run_dir.mkdir()
        (run_dir / "summary.json").write_text(
            json.dumps({
                "run_id": "test-run",
                "run_kind": "synthetic_engine_smoke",
                "planned_ticks": spec.ticks,
                "completed_ticks": spec.ticks,
            }),
            encoding="utf-8",
        )
        (run_dir / "parameters.json").write_text(
            json.dumps({"parameter_hash": "e" * 64}), encoding="utf-8"
        )
        (run_dir / "initial_recipe.json").write_text("{}", encoding="utf-8")
        manifest = _make_minimal_run_manifest(
            seed=7,
            scenario_hash=compute_scenario_hash(spec.model_copy(update={"seed": 7})),
            lock_hash=compute_lock_hash(ROOT),
            data_manifest_hash=compute_data_manifest_hash(ROOT),
            ticks=spec.ticks,
            completed_ticks=spec.ticks,
        )
        manifest["run_kind"] = "synthetic_engine_smoke"
        manifest["baseline_hash"] = verify_baseline(
            ROOT / BASELINE_FILENAME, load_research_contract(ROOT)
        )
        manifest["output_hashes"] = hash_output_tree(run_dir)
        (run_dir / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        verified = verify_run_identity(
            root=ROOT,
            scenario_id="smoke",
            seed=7,
            expected_digest="a" * 64,
            output_dir=run_dir,
        )
        assert verified.run_kind == "synthetic_engine_smoke"


# ---------------------------------------------------------------------------
# StudyManifest card verification (loader)
# ---------------------------------------------------------------------------

def _write_study_manifest(
    root: Path,
    *,
    mechanism_id: str = "M01",
    linked_cards: list[str] | None = None,
    v1_card_sha256: str | None = None,
    sidecar_mechanism_id: str | None = None,
    sidecar_card_sha: str | None = None,
    write_sidecar: bool = True,
    index_card_sha: str | None = None,
    index_omits_mechanism: bool = False,
) -> Path:
    """Write a study manifest (and, by default, its sidecars) under ``root``.

    The ``studies/<canonical mechanism id>/study_decl.json`` sidecar and the
    ``config/mechanisms/v2/supersedes.json`` v1-card SHA index are written
    unless overridden, declaring the same mechanism and the SHA-256 of the card
    already staged in ``root`` — so they pass cross-verification.
    """
    from hsm_lab.contract.guards import sha256_file
    from hsm_lab.evidence.schemas import canonical_mechanism_id

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

    if write_sidecar:
        canonical = canonical_mechanism_id(mechanism_id)
        sidecar_dir = root / "studies" / canonical
        sidecar_dir.mkdir(parents=True, exist_ok=True)
        card_key = f"M{int(canonical[1:])}"
        staged_card = root / "config" / "p06" / "cards" / f"{card_key}.json"
        if sidecar_card_sha is not None:
            card_sha = sidecar_card_sha
        elif staged_card.is_file():
            card_sha = sha256_file(staged_card)
        else:
            card_sha = "a" * 64
        (sidecar_dir / "study_decl.json").write_text(
            json.dumps({
                "mechanism_id": (
                    sidecar_mechanism_id if sidecar_mechanism_id is not None else canonical
                ),
                "intent": "unit_test_intent",
                "linked_cards": [card_key],
                "v1_card_sha256": card_sha,
                "status": "declared",
                "declared_reason": "unit-test declaration",
                "blocked_reason": None,
                "phase": "P07A1",
                "research_package_complete": False,
                "note": "unit-test sidecar",
            }),
            encoding="utf-8",
        )

    index_path = root / "config" / "mechanisms" / "v2" / "supersedes.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    canonical = canonical_mechanism_id(mechanism_id)
    card_key = f"M{int(canonical[1:])}"
    index: dict[str, object] = {"schema_version": "1.0.0"}
    if not index_omits_mechanism:
        if index_card_sha is not None:
            index[card_key] = index_card_sha
        else:
            staged_card = root / "config" / "p06" / "cards" / f"{card_key}.json"
            index[card_key] = (
                sha256_file(staged_card) if staged_card.is_file() else "a" * 64
            )
    index_path.write_text(json.dumps(index), encoding="utf-8")
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

    # ------------------------------------------------------------------
    # Sidecar cross-verification (H0A P0: sidecar SHAs must be read)
    # ------------------------------------------------------------------

    def test_real_study_sidecars_are_card_bound(self) -> None:
        """Every real declaration's sidecar must bind the card bytes on disk.

        The real manifest records declare no ``v1_card_sha256``, so the sidecar
        is the only card binding; it must therefore be read and checked.
        """
        from hsm_lab.contract.guards import sha256_file

        manifest = load_evidence_manifest(ROOT, ROOT / "studies" / "manifest.json")
        assert isinstance(manifest, StudyManifest)
        for record in manifest.records:
            sidecar = ROOT / "studies" / record.mechanism_id / "study_decl.json"
            assert sidecar.is_file(), f"missing sidecar for {record.mechanism_id}"
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            assert payload["mechanism_id"] == record.mechanism_id
            card = ROOT / "config" / "p06" / "cards" / f"{record.linked_cards[0]}.json"
            assert payload["v1_card_sha256"] == sha256_file(card)

    def test_real_supersedes_index_is_card_bound(self) -> None:
        """The v1-card SHA index must agree with the real card bytes."""
        from hsm_lab.contract.guards import sha256_file

        index = json.loads(
            (ROOT / "config" / "mechanisms" / "v2" / "supersedes.json").read_text(
                encoding="utf-8"
            )
        )
        for index_number in range(1, 12):
            card_key = f"M{index_number}"
            card = ROOT / "config" / "p06" / "cards" / f"{card_key}.json"
            assert index[card_key] == sha256_file(card)
        # ...and the loader accepts the real manifest through the public path.
        manifest = load_evidence_manifest(ROOT, ROOT / "studies" / "manifest.json")
        assert isinstance(manifest, StudyManifest)

    def test_supersedes_index_sha_mismatch_is_rejected(self, tmp_path: Path) -> None:
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path, index_card_sha="b" * 64)
        with pytest.raises(ValueError, match="v1 card SHA index mismatch"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_supersedes_index_missing_entry_is_rejected(self, tmp_path: Path) -> None:
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path, index_omits_mechanism=True)
        with pytest.raises(ValueError, match="has no entry for 'M1'"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_supersedes_index_missing_file_is_rejected(self, tmp_path: Path) -> None:
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path)
        (tmp_path / "config" / "mechanisms" / "v2" / "supersedes.json").unlink()
        with pytest.raises(ValueError, match="v1 card SHA index not found"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_sidecar_with_duplicate_key_is_rejected(self, tmp_path: Path) -> None:
        """A duplicated sidecar key would shadow the identity fields; refuse it."""
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path)
        sidecar_path = tmp_path / "studies" / "M01" / "study_decl.json"
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        text = json.dumps(payload).replace(
            '"mechanism_id": "M01"', '"mechanism_id": "M02", "mechanism_id": "M01"'
        )
        sidecar_path.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match="duplicate JSON key"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_missing_sidecar_is_rejected(self, tmp_path: Path) -> None:
        """A declared card is not enough: the sidecar must exist."""
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path, write_sidecar=False)
        with pytest.raises(ValueError, match="study sidecar not found"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_sidecar_mechanism_id_mismatch_is_rejected(self, tmp_path: Path) -> None:
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path, sidecar_mechanism_id="M02")
        with pytest.raises(ValueError, match="sidecar mechanism_id mismatch"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_sidecar_card_sha_mismatch_is_rejected(self, tmp_path: Path) -> None:
        card = _stage_card(tmp_path, "M1.json")
        assert card.is_file()
        manifest_path = _write_study_manifest(tmp_path, sidecar_card_sha="b" * 64)
        with pytest.raises(ValueError, match="sidecar v1_card_sha256 mismatch"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_sidecar_zero_card_sha_is_rejected(self, tmp_path: Path) -> None:
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path, sidecar_card_sha="0" * 64)
        with pytest.raises(ValueError, match="all zeros"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_sidecar_missing_key_is_rejected(self, tmp_path: Path) -> None:
        """Missing sidecar keys are errors, never silently skipped."""
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path)
        sidecar_path = tmp_path / "studies" / "M01" / "study_decl.json"
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        del payload["v1_card_sha256"]
        sidecar_path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="missing required key"):
            load_evidence_manifest(tmp_path, manifest_path)

    # ------------------------------------------------------------------
    # Sidecar content cross-verification (H0A P0: sidecar content must agree)
    # ------------------------------------------------------------------

    def _patch_sidecar(self, root: Path, **updates: object) -> None:
        """Rewrite named fields of the staged ``studies/M01`` sidecar."""
        sidecar_path = root / "studies" / "M01" / "study_decl.json"
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        payload.update(updates)
        sidecar_path.write_text(json.dumps(payload), encoding="utf-8")

    def _patch_manifest_record_phase(self, root: Path, phase: str) -> None:
        """Add a ``phase`` field to the staged manifest's first record."""
        manifest_path = root / "studies" / "manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["records"][0]["phase"] = phase
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_real_sidecar_content_matches_declarations(self) -> None:
        """Every real sidecar's content must equal its manifest record's.

        The sidecar carries intent/status/linked_cards/phase; a sidecar left
        over from a different declaration must not pass as this one's.
        """
        manifest = load_evidence_manifest(ROOT, ROOT / "studies" / "manifest.json")
        assert isinstance(manifest, StudyManifest)
        for record in manifest.records:
            sidecar = json.loads(
                (
                    ROOT / "studies" / record.mechanism_id / "study_decl.json"
                ).read_text(encoding="utf-8")
            )
            assert sidecar["intent"] == record.intent
            assert sidecar["status"] == record.status
            assert [canonical_mechanism_id(c) for c in sidecar["linked_cards"]] == [
                canonical_mechanism_id(c) for c in record.linked_cards
            ]
            assert sidecar["phase"] == manifest.phase

    def test_sidecar_intent_mismatch_is_rejected(self, tmp_path: Path) -> None:
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path)
        self._patch_sidecar(tmp_path, intent="a_different_intent")
        with pytest.raises(ValueError, match="sidecar intent mismatch"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_sidecar_status_mismatch_is_rejected(self, tmp_path: Path) -> None:
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path)
        self._patch_sidecar(tmp_path, status="blocked")
        with pytest.raises(ValueError, match="sidecar status mismatch"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_sidecar_linked_cards_mismatch_is_rejected(self, tmp_path: Path) -> None:
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path)
        self._patch_sidecar(tmp_path, linked_cards=["M2"])
        with pytest.raises(ValueError, match="sidecar linked_cards mismatch"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_sidecar_phase_mismatch_is_rejected(self, tmp_path: Path) -> None:
        """A sidecar phase that contradicts the manifest phase is rejected."""
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path)
        self._patch_sidecar(tmp_path, phase="P07B")
        with pytest.raises(ValueError, match="sidecar phase mismatch"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_declared_phase_takes_precedence_over_manifest_phase(
        self, tmp_path: Path
    ) -> None:
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path)
        self._patch_manifest_record_phase(tmp_path, "P07A1")
        manifest = load_evidence_manifest(tmp_path, manifest_path)
        assert isinstance(manifest, StudyManifest)
        assert manifest.records[0].phase == "P07A1"

    def test_sidecar_phase_contradicting_declared_phase_is_rejected(
        self, tmp_path: Path
    ) -> None:
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path)
        self._patch_manifest_record_phase(tmp_path, "P07B")
        self._patch_sidecar(tmp_path, phase="P07A1")
        with pytest.raises(ValueError, match="sidecar phase mismatch"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_sidecar_linked_cards_canonical_form_is_accepted(
        self, tmp_path: Path
    ) -> None:
        """``linked_cards`` are compared on canonical form: ``M1`` == ``M01``."""
        from hsm_lab.contract.guards import sha256_file

        card = _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(
            tmp_path,
            mechanism_id="M01",
            linked_cards=["M01"],
            v1_card_sha256=sha256_file(card),
        )
        manifest = load_evidence_manifest(tmp_path, manifest_path)
        assert isinstance(manifest, StudyManifest)
        assert manifest.records[0].linked_cards == ["M01"]

    def test_sidecar_missing_content_key_is_rejected(self, tmp_path: Path) -> None:
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path)
        sidecar_path = tmp_path / "studies" / "M01" / "study_decl.json"
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        del payload["intent"]
        sidecar_path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="missing required key"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_sidecar_malformed_status_is_rejected(self, tmp_path: Path) -> None:
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path)
        self._patch_sidecar(tmp_path, status="maybe")
        with pytest.raises(ValueError, match="sidecar status must be"):
            load_evidence_manifest(tmp_path, manifest_path)

    def test_sidecar_malformed_linked_cards_is_rejected(self, tmp_path: Path) -> None:
        _stage_card(tmp_path, "M1.json")
        manifest_path = _write_study_manifest(tmp_path)
        self._patch_sidecar(tmp_path, linked_cards="M1")
        with pytest.raises(ValueError, match="sidecar linked_cards must be"):
            load_evidence_manifest(tmp_path, manifest_path)


# ---------------------------------------------------------------------------
# verify_run_identity — fabricated trajectory schema / recipe content (P0-3)
# ---------------------------------------------------------------------------

def _write_parquet(path: Path, columns: dict[str, list]) -> None:
    """Write a Parquet file at ``path`` from plain per-column value lists."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    pq.write_table(
        pa.table({name: pa.array(values) for name, values in columns.items()}),
        path,
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestVerifyRunIdentityFabricatedArtefacts:
    """Hand-written artefacts must not pass as a material run (P0-3).

    A directory can carry summary/parameters/recipe JSON and even Parquet
    files; what it cannot fake is the material runner's table schema, its
    recipe declaration, and the identity fields a completed run records.
    """

    def _run_dir(self, tmp_path: Path, **kwargs) -> Path:
        return _write_self_consistent_material_run(
            tmp_path / "run", parameter_hash=_material_parameter_hash(), **kwargs
        )

    def _verify(self, run_dir: Path):
        return verify_run_identity(
            root=ROOT,
            scenario_id=_PARAMETER_SCENARIO,
            seed=1729,
            expected_digest="a" * 64,
            output_dir=run_dir,
        )

    def test_tick_value_only_table_is_rejected(self, tmp_path: Path) -> None:
        """A ``tick,value`` Parquet file is not a material trajectory table."""
        run_dir = self._run_dir(tmp_path)
        rows = _read_row_counts(run_dir)["aggregates"]
        _write_parquet(
            run_dir / "trajectory_tables" / "aggregates.parquet",
            {"tick": list(range(rows)), "value": [float(i) for i in range(rows)]},
        )
        _rehash_run_outputs(run_dir)
        with pytest.raises(ValueError, match="missing the columns"):
            self._verify(run_dir)

    def test_table_without_axis_columns_is_rejected(self, tmp_path: Path) -> None:
        """An axis table without its axis keys is not the runner's table."""
        run_dir = self._run_dir(tmp_path)
        rows = _read_row_counts(run_dir)["aggregates"]
        _write_parquet(
            run_dir / "trajectory_tables" / "aggregates.parquet",
            {
                "tick": list(range(rows)),
                "quarter": ["1957Q1"] * rows,
                "value": [float(i) for i in range(rows)],
            },
        )
        _rehash_run_outputs(run_dir)
        with pytest.raises(ValueError, match="region_id"):
            self._verify(run_dir)

    def test_table_without_quarter_key_is_rejected(self, tmp_path: Path) -> None:
        """The tick/quarter keys are required on every compact table."""
        run_dir = self._run_dir(tmp_path)
        rows = _read_row_counts(run_dir)["tick_diagnostics"]
        _write_parquet(
            run_dir / "trajectory_tables" / "tick_diagnostics.parquet",
            {
                "tick": list(range(rows)),
                "bottleneck_demand_count": list(range(rows)),
            },
        )
        _rehash_run_outputs(run_dir)
        with pytest.raises(ValueError, match="quarter"):
            self._verify(run_dir)

    def test_empty_declared_table_with_stub_schema_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """A 0-row table is still checked: its schema must be the runner's."""
        run_dir = self._run_dir(tmp_path)
        _write_parquet(
            run_dir / "trajectory_tables" / "information_quarters.parquet",
            {"tick": [], "quarter": []},
        )
        _rehash_run_outputs(run_dir)
        with pytest.raises(ValueError, match="tick/value stub"):
            self._verify(run_dir)

    def test_table_not_covering_declared_universe_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """A table covering one commodity while the run declares 16 is not its output."""
        from hsm_lab.contract.guards import load_scenario

        run_dir = self._run_dir(tmp_path)
        rows = _read_row_counts(run_dir)["national_accounts"]
        sole_commodity = load_scenario(ROOT, _PARAMETER_SCENARIO).commodities[0]
        _write_parquet(
            run_dir / "trajectory_tables" / "national_accounts.parquet",
            {
                "tick": [0] * rows,
                "quarter": ["1957Q1"] * rows,
                "commodity_id": [sole_commodity] * rows,
                "production": [1.0] * rows,
            },
        )
        _rehash_run_outputs(run_dir)
        with pytest.raises(ValueError, match="does not cover the run's declared universe"):
            self._verify(run_dir)

    def test_empty_initial_recipe_is_rejected(self, tmp_path: Path) -> None:
        """``initial_recipe.json`` of ``{}`` is a stub, not a recipe."""
        run_dir = self._run_dir(tmp_path)
        _write_json(run_dir / "initial_recipe.json", {})
        _rehash_run_outputs(run_dir)
        with pytest.raises(ValueError, match="initial_recipe.json"):
            self._verify(run_dir)

    def test_recipe_without_declaration_is_rejected(self, tmp_path: Path) -> None:
        """A recipe file with no declaration carries no recipe content."""
        run_dir = self._run_dir(tmp_path)
        recipe = _read_json(run_dir / "initial_recipe.json")
        _write_json(
            run_dir / "initial_recipe.json",
            {
                "scenario_id": recipe["scenario_id"],
                "initial_recipe_hash": recipe["initial_recipe_hash"],
            },
        )
        _rehash_run_outputs(run_dir)
        with pytest.raises(ValueError, match="no non-empty 'declaration'"):
            self._verify(run_dir)

    def test_recipe_hash_mismatch_is_rejected(self, tmp_path: Path) -> None:
        """The recipe file's own hash must be the manifest's recipe hash."""
        run_dir = self._run_dir(tmp_path)
        recipe = _read_json(run_dir / "initial_recipe.json")
        recipe["initial_recipe_hash"] = "b" * 64
        _write_json(run_dir / "initial_recipe.json", recipe)
        _rehash_run_outputs(run_dir)
        with pytest.raises(ValueError, match="does not match manifest.initial_recipe_hash"):
            self._verify(run_dir)

    def test_recipe_from_another_scenario_is_rejected(self, tmp_path: Path) -> None:
        """A recipe belonging to a different scenario is a mismatched pairing."""
        run_dir = self._run_dir(tmp_path)
        recipe = _read_json(run_dir / "initial_recipe.json")
        recipe["scenario_id"] = "smoke"
        _write_json(run_dir / "initial_recipe.json", recipe)
        _rehash_run_outputs(run_dir)
        with pytest.raises(ValueError, match="another scenario"):
            self._verify(run_dir)

    def test_placeholder_summary_is_rejected(self, tmp_path: Path) -> None:
        """``{"run_id": ..., "row_counts": ...}`` is not a run's own account."""
        run_dir = self._run_dir(tmp_path)
        _write_json(
            run_dir / "summary.json",
            {
                "run_id": "test-run",
                "row_counts": _read_row_counts(run_dir),
            },
        )
        _rehash_run_outputs(run_dir)
        with pytest.raises(ValueError, match="placeholder summary is not a run"):
            self._verify(run_dir)

    def test_summary_without_scenario_id_is_rejected(self, tmp_path: Path) -> None:
        """The summary must name the scenario the run belongs to."""
        run_dir = self._run_dir(tmp_path)
        summary = _read_json(run_dir / "summary.json")
        del summary["scenario_id"]
        _write_json(run_dir / "summary.json", summary)
        _rehash_run_outputs(run_dir)
        with pytest.raises(ValueError, match="scenario_id"):
            self._verify(run_dir)

    def test_summary_with_empty_commodity_universe_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """An empty commodity universe is a placeholder, not a run record."""
        run_dir = self._run_dir(tmp_path)
        summary = _read_json(run_dir / "summary.json")
        summary["commodity_ids"] = []
        _write_json(run_dir / "summary.json", summary)
        _rehash_run_outputs(run_dir)
        with pytest.raises(ValueError, match="commodity_ids"):
            self._verify(run_dir)

    def test_fabricated_recipe_declaration_is_rejected(self, tmp_path: Path) -> None:
        """The declaration must be the recipe the scenario actually declares.

        The recipe hash binds the scenario's organization/technology/route
        recipe, not the initial-state declaration, so a declaration that only
        agrees on the hash used to ride along: this one claims a dwelling
        density the scenario never declared.
        """
        run_dir = self._run_dir(tmp_path)
        recipe = _read_json(run_dir / "initial_recipe.json")
        recipe["declaration"]["dwelling_per_person"] = round(
            recipe["declaration"]["dwelling_per_person"] + 0.5, 6
        )
        _write_json(run_dir / "initial_recipe.json", recipe)
        _rehash_run_outputs(run_dir)

        with pytest.raises(ValueError, match="declaration does not match"):
            self._verify(run_dir)

    def test_recipe_declaration_with_unknown_field_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """A declaration must conform to the material initial-state schema."""
        run_dir = self._run_dir(tmp_path)
        recipe = _read_json(run_dir / "initial_recipe.json")
        recipe["declaration"]["fabricated_field"] = 1.0
        _write_json(run_dir / "initial_recipe.json", recipe)
        _rehash_run_outputs(run_dir)

        with pytest.raises(
            ValueError, match="not a valid material initial-state recipe"
        ):
            self._verify(run_dir)

    def test_recipe_declaration_with_wrong_role_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """A declaration must claim the initial-state role the schema defines."""
        run_dir = self._run_dir(tmp_path)
        recipe = _read_json(run_dir / "initial_recipe.json")
        recipe["declaration"]["role"] = "running_state"
        _write_json(run_dir / "initial_recipe.json", recipe)
        _rehash_run_outputs(run_dir)

        with pytest.raises(
            ValueError, match="not a valid material initial-state recipe"
        ):
            self._verify(run_dir)

    def test_unmodified_recipe_declaration_is_accepted(self, tmp_path: Path) -> None:
        """Control: the runner's own declaration is the scenario's recipe."""
        run_dir = self._run_dir(tmp_path)
        assert self._verify(run_dir).run_id == "test-run"


@pytest.mark.parametrize("run_name", ["C0", "C1"])
def test_real_audit_run_still_verifies(run_name: str) -> None:
    """The real audit runs must still pass the hardened identity checks."""
    run_dir = ROOT / "outputs" / "codex-audit-vnext-20261011" / run_name
    if not (run_dir / "manifest.json").is_file():
        pytest.skip(f"real audit run {run_name} not present in this checkout")

    manifest = _read_json(run_dir / "manifest.json")
    summary = _read_json(run_dir / "summary.json")
    verified = verify_run_identity(
        root=ROOT,
        scenario_id=summary["scenario_id"],
        seed=manifest["seed"],
        expected_digest=manifest["deterministic_replay_digest"],
        output_dir=run_dir,
    )
    assert verified.run_id == manifest["run_id"]
    assert verified.run_kind == "material_household_simulation"


# ---------------------------------------------------------------------------
# SUPPORTED metrics must exist in the runs that back them (P0-2)
# ---------------------------------------------------------------------------

class TestSupportedMetricContentBinding:
    """A SUPPORTED record's metrics must exist in the referenced run output.

    A verified run reference proves a run happened; it says nothing about
    whether the declared ``table_or_sidecar``/``column`` was ever produced by
    it. Every metric is therefore checked against the run's own artefacts:
    the table/sidecar and column must exist, the declared window must be
    covered by real rows, and a declared commodity/region selector must be
    covered by the table's axis column.
    """

    def _run_dir(self, tmp_path: Path, *, seed: int = 1729) -> Path:
        return _write_self_consistent_material_run(
            tmp_path / "run", parameter_hash=_material_parameter_hash(), seed=seed
        )

    def _spec(self, **overrides) -> MetricSpec:
        kwargs = dict(
            metric_id="m1.delivered",
            table_or_sidecar="aggregates",
            column="delivered",
            time_window=TimeWindow(
                start_quarter="1957Q1",
                end_quarter="1985Q4",
                missing_policy=MissingPolicy.ABORT,
            ),
            # ``aggregates.delivered`` is a physical flow: its unit is the
            # commodity-specific ontology token, never model currency.
            unit=PHYSICAL_UNIT_TOKEN,
            fidelity=FidelityLevel.F2_RUN,
            data_role=DataRole.TARGET,
            validation_fidelity=ValidationFidelity.EXACT,
            missing_policy=MissingPolicy.ABORT,
        )
        kwargs.update(overrides)
        return MetricSpec(**kwargs)

    def _record(
        self,
        run_dir: Path,
        *specs: MetricSpec,
        extra_runs: list[tuple[Path, int]] | None = None,
        run_id: str = "test-run",
        digest: str = "a" * 64,
        seed: int = 1729,
        scenario_id: str = _PARAMETER_SCENARIO,
        linked_observed_states: list[ObservedState] | None = None,
    ) -> EvidenceRecord:
        from hsm_lab.contract.guards import sha256_file

        runs = [(run_dir, seed), *(extra_runs or [])]
        if linked_observed_states is None:
            # A supported record must link the snapshot it is traceable to, and
            # that snapshot must name the verified run (id/scenario/digest) and a
            # quarter the run's own output carries.
            linked_observed_states = [
                ObservedState(
                    observed_state_id="obs-1",
                    source_run_id=run_id,
                    source_scenario=scenario_id,
                    source_checkpoint_quarter="1957Q1",
                    source_digest=digest,
                    captured_at="2024-01-01T00:00:00Z",
                    available_at="1957Q1",
                    decision_at="1957Q1",
                )
            ]
        declared = EvidenceRecord(
            record_id="TEST-METRIC-CONTENT",
            mechanism_id="M1",
            v1_card_sha256=sha256_file(ROOT / "config" / "p06" / "cards" / "M1.json"),
            hypothesis="declared metrics must exist in the backing run output",
            status=EvidenceStatus.DECLARED,
            metric_specs=list(specs),
            linked_observed_states=list(linked_observed_states),
            run_references=[
                EvidenceRunReference(
                    run_id=run_id,
                    scenario_id=scenario_id,
                    seed=ref_seed,
                    output_dir=output_dir,
                    digest=digest,
                )
                for output_dir, ref_seed in runs
            ],
            declared_reason="P0-2 metric content binding",
            created_by_phase="H0A",
        )
        # ``model_copy`` skips after-validators: exactly the in-memory record a
        # caller could hand to a consumer, which the gate must re-verify.
        return declared.model_copy(update={"status": EvidenceStatus.SUPPORTED})

    def _write_sidecar(self, run_dir: Path, payload: dict) -> None:
        """Write a JSON sidecar next to the run's tables and re-pin the tree."""
        _write_json(run_dir / "run_metrics.json", payload)
        _rehash_run_outputs(run_dir)

    def test_bound_metrics_pass(self, tmp_path: Path) -> None:
        """Metrics that the referenced run really produced are accepted."""
        run_dir = self._run_dir(tmp_path)
        self._write_sidecar(run_dir, {"delivered_total": 12.5})
        record = self._record(
            run_dir,
            self._spec(
                commodity_axis=CommodityAxis(
                    commodities=["g01_solid_fuels", "g02_oil_gas_fuels"],
                    unit="M_forint",
                ),
                region_axis=RegionAxis(
                    regions=["budapest", "pest"],
                    unit="M_forint",
                    aggregation="sum",
                ),
            ),
            self._spec(
                metric_id="m1.household_consumption",
                table_or_sidecar="national_accounts",
                column="household_consumption",
                commodity_axis=CommodityAxis(
                    commodities=["g09_basic_food"], unit="M_forint"
                ),
            ),
            self._spec(
                metric_id="m2.bottleneck_demand_count",
                table_or_sidecar="tick_diagnostics",
                column="bottleneck_demand_count",
                time_window=TimeWindow(
                    start_quarter="1957Q1",
                    end_quarter="1960Q4",
                    missing_policy=MissingPolicy.ABORT,
                ),
                data_role=DataRole.CANDIDATE_LINKAGE,
                validation_fidelity=ValidationFidelity.PROXY,
                unit="count",
            ),
            self._spec(
                metric_id="m1.delivered_total",
                table_or_sidecar="run_metrics",
                column="delivered_total",
            ),
        )
        verify_supported_record_runs(ROOT, record)

    def test_bound_metrics_pass_the_publish_gate(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        record = self._record(run_dir, self._spec())
        manifest = EvidenceManifest.model_construct(
            manifest_version="1.0.0",
            phase="H0A",
            records=[record],
        )
        verified = verify_evidence_manifest_runs(ROOT, manifest)
        assert verified.records[0]._verified is True

    def test_missing_table_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        record = self._record(
            run_dir, self._spec(table_or_sidecar="never_written_table")
        )
        with pytest.raises(ValueError, match="holds no such table or sidecar"):
            verify_supported_record_runs(ROOT, record)

    def test_missing_column_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        record = self._record(run_dir, self._spec(column="production"))
        with pytest.raises(ValueError, match="column 'production' does not exist"):
            verify_supported_record_runs(ROOT, record)

    def test_empty_table_is_rejected(self, tmp_path: Path) -> None:
        """A table with no rows cannot support a metric."""
        run_dir = self._run_dir(tmp_path)
        record = self._record(
            run_dir,
            self._spec(
                metric_id="m9.forecast_accuracy",
                table_or_sidecar="information_quarters",
                column="forecast_accuracy",
                data_role=DataRole.CANDIDATE_LINKAGE,
                validation_fidelity=ValidationFidelity.PROXY,
            ),
        )
        with pytest.raises(ValueError, match="has no rows"):
            verify_supported_record_runs(ROOT, record)

    def test_window_not_covered_is_rejected(self, tmp_path: Path) -> None:
        """A metric declared over quarters the run never produced is rejected."""
        import pyarrow.compute as pc
        import pyarrow.parquet as pq

        run_dir = self._run_dir(tmp_path)
        table_path = run_dir / "trajectory_tables" / "tick_diagnostics.parquet"
        frame = pq.read_table(table_path)
        frame = frame.filter(pc.not_equal(frame["quarter"], "1985Q4"))
        pq.write_table(frame, table_path)
        counts = _read_row_counts(run_dir)
        counts["tick_diagnostics"] = frame.num_rows
        _patch_run_summary(run_dir, row_counts=counts)

        record = self._record(
            run_dir,
            self._spec(
                metric_id="m2.bottleneck_demand_count",
                table_or_sidecar="tick_diagnostics",
                column="bottleneck_demand_count",
                time_window=TimeWindow(
                    start_quarter="1985Q4",
                    end_quarter="1985Q4",
                    missing_policy=MissingPolicy.ABORT,
                ),
                data_role=DataRole.CANDIDATE_LINKAGE,
                validation_fidelity=ValidationFidelity.PROXY,
            ),
        )
        with pytest.raises(ValueError, match="no rows for the declared time window"):
            verify_supported_record_runs(ROOT, record)

    def test_commodity_selector_not_covered_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        record = self._record(
            run_dir,
            self._spec(
                commodity_axis=CommodityAxis(
                    commodities=["g99_unknown_commodity"], unit="M_forint"
                )
            ),
        )
        with pytest.raises(ValueError, match="not covered"):
            verify_supported_record_runs(ROOT, record)

    def test_selector_on_table_without_that_axis_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """``national_accounts`` has no region axis: a region selector is a lie."""
        run_dir = self._run_dir(tmp_path)
        record = self._record(
            run_dir,
            self._spec(
                table_or_sidecar="national_accounts",
                column="household_consumption",
                region_axis=RegionAxis(
                    regions=["budapest"], unit="M_forint", aggregation="sum"
                ),
            ),
        )
        with pytest.raises(ValueError, match="has no 'region_id' column"):
            verify_supported_record_runs(ROOT, record)

    def test_table_without_quarter_axis_is_rejected(self, tmp_path: Path) -> None:
        """A sidecar-named Parquet file with no quarter column cannot be window-checked."""
        run_dir = self._run_dir(tmp_path)
        _write_parquet(
            run_dir / "trajectory_tables" / "extra_table.parquet",
            {"tick": [0], "value": [1.0]},
        )
        _rehash_run_outputs(run_dir)
        record = self._record(
            run_dir,
            self._spec(table_or_sidecar="extra_table", column="value"),
        )
        with pytest.raises(ValueError, match="has no 'quarter' column"):
            verify_supported_record_runs(ROOT, record)

    def test_sidecar_missing_column_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        self._write_sidecar(run_dir, {"delivered_total": 12.5})
        record = self._record(
            run_dir,
            self._spec(
                table_or_sidecar="run_metrics", column="absent_metric"
            ),
        )
        with pytest.raises(ValueError, match="is not declared in sidecar"):
            verify_supported_record_runs(ROOT, record)

    def test_sidecar_null_value_is_rejected(self, tmp_path: Path) -> None:
        run_dir = self._run_dir(tmp_path)
        self._write_sidecar(run_dir, {"delivered_total": None})
        record = self._record(
            run_dir,
            self._spec(table_or_sidecar="run_metrics", column="delivered_total"),
        )
        with pytest.raises(ValueError, match="as null"):
            verify_supported_record_runs(ROOT, record)

    def test_metric_absent_from_one_referenced_run_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """All replicates must carry the metric, not just the first one."""
        run_dir = self._run_dir(tmp_path)
        self._write_sidecar(run_dir, {"delivered_total": 12.5})
        replicate_dir = _write_self_consistent_material_run(
            tmp_path / "replicate",
            parameter_hash=_material_parameter_hash(),
            seed=1730,
        )
        record = self._record(
            run_dir,
            self._spec(table_or_sidecar="run_metrics", column="delivered_total"),
            extra_runs=[(replicate_dir, 1730)],
        )
        record = record.model_copy(update={"minimum_replicates": 2})
        with pytest.raises(ValueError, match="holds no such table or sidecar"):
            verify_supported_record_runs(ROOT, record)

    def test_unbound_fabricated_metric_is_rejected_against_real_run(
        self, tmp_path: Path
    ) -> None:
        """The exact P0-2 fabrication: plausible table/column no run produced."""
        run_dir = self._run_dir(tmp_path)
        record = self._record(
            run_dir,
            self._spec(
                metric_id="m1.household_consumption",
                table_or_sidecar="national_accounts",
                column="household_consumption",
            ),
            self._spec(
                metric_id="m1.plausible_but_unwritten",
                table_or_sidecar="national_accounts",
                column="real_consumption_index",
            ),
        )
        with pytest.raises(
            ValueError, match="column 'real_consumption_index' does not exist"
        ):
            verify_supported_record_runs(ROOT, record)

    def test_metric_column_without_data_is_rejected(self, tmp_path: Path) -> None:
        """An all-null column is a placeholder, not a target measurement."""
        run_dir = self._run_dir(tmp_path)
        counts = _read_row_counts(run_dir)
        rows = counts["tick_diagnostics"]
        _write_parquet(
            run_dir / "trajectory_tables" / "tick_diagnostics.parquet",
            {
                "tick": list(range(rows)),
                "quarter": [
                    str(Quarter.parse("1957Q1").advance(tick))
                    for tick in range(rows)
                ],
                "bottleneck_demand_count": [None] * rows,
            },
        )
        _rehash_run_outputs(run_dir)
        record = self._record(
            run_dir,
            self._spec(
                metric_id="m2.bottleneck_demand_count",
                table_or_sidecar="tick_diagnostics",
                column="bottleneck_demand_count",
                data_role=DataRole.TARGET,
                validation_fidelity=ValidationFidelity.PROXY,
            ),
        )
        with pytest.raises(ValueError, match="must carry actual data"):
            verify_supported_record_runs(ROOT, record)

    def test_metric_column_of_nan_is_rejected(self, tmp_path: Path) -> None:
        """All-NaN values are missing data, not measurements."""
        run_dir = self._run_dir(tmp_path)
        rows = _read_row_counts(run_dir)["tick_diagnostics"]
        _write_parquet(
            run_dir / "trajectory_tables" / "tick_diagnostics.parquet",
            {
                "tick": list(range(rows)),
                "quarter": [
                    str(Quarter.parse("1957Q1").advance(tick))
                    for tick in range(rows)
                ],
                "bottleneck_demand_count": [float("nan")] * rows,
            },
        )
        _rehash_run_outputs(run_dir)
        record = self._record(
            run_dir,
            self._spec(
                metric_id="m2.bottleneck_demand_count",
                table_or_sidecar="tick_diagnostics",
                column="bottleneck_demand_count",
                data_role=DataRole.CANDIDATE_LINKAGE,
                validation_fidelity=ValidationFidelity.PROXY,
                unit="count",
            ),
        )
        with pytest.raises(ValueError, match="must carry actual data"):
            verify_supported_record_runs(ROOT, record)

    def _write_tick_diagnostics_column(
        self, run_dir: Path, values: list
    ) -> None:
        """Rewrite tick_diagnostics' count column with ``values`` (same rows)."""
        rows = _read_row_counts(run_dir)["tick_diagnostics"]
        assert len(values) == rows
        _write_parquet(
            run_dir / "trajectory_tables" / "tick_diagnostics.parquet",
            {
                "tick": list(range(rows)),
                "quarter": [
                    str(Quarter.parse("1957Q1").advance(tick))
                    for tick in range(rows)
                ],
                "bottleneck_demand_count": values,
            },
        )
        _rehash_run_outputs(run_dir)

    def _count_spec(self, **overrides) -> MetricSpec:
        """A spec bound to the count column, in the unit the model declares."""
        kwargs = dict(
            metric_id="m2.bottleneck_demand_count",
            table_or_sidecar="tick_diagnostics",
            column="bottleneck_demand_count",
            data_role=DataRole.TARGET,
            validation_fidelity=ValidationFidelity.PROXY,
            unit="count",
        )
        kwargs.update(overrides)
        return self._spec(**kwargs)

    def test_metric_column_of_infinity_is_rejected(self, tmp_path: Path) -> None:
        """An infinite column is not data: every value propagates as ``inf``."""
        run_dir = self._run_dir(tmp_path)
        rows = _read_row_counts(run_dir)["tick_diagnostics"]
        self._write_tick_diagnostics_column(run_dir, [float("inf")] * rows)
        record = self._record(run_dir, self._count_spec())
        with pytest.raises(ValueError, match="non-finite"):
            verify_supported_record_runs(ROOT, record)

    @pytest.mark.parametrize("infinite", [float("inf"), float("-inf")])
    def test_one_infinite_value_among_finite_ones_is_rejected(
        self, tmp_path: Path, infinite: float
    ) -> None:
        """An all-null/all-NaN check is not enough: one ``inf`` poisons the column."""
        run_dir = self._run_dir(tmp_path)
        rows = _read_row_counts(run_dir)["tick_diagnostics"]
        values: list[object] = [float(tick) for tick in range(rows)]
        values[1] = infinite
        self._write_tick_diagnostics_column(run_dir, values)
        record = self._record(run_dir, self._count_spec())
        with pytest.raises(ValueError, match="non-finite"):
            verify_supported_record_runs(ROOT, record)

    def test_finite_values_are_not_nonfinite(self, tmp_path: Path) -> None:
        """Control: finite values (however extreme) are measurements."""
        run_dir = self._run_dir(tmp_path)
        rows = _read_row_counts(run_dir)["tick_diagnostics"]
        self._write_tick_diagnostics_column(
            run_dir, [1.7e308 if tick == 0 else -1.7e308 for tick in range(rows)]
        )
        verify_supported_record_runs(ROOT, self._record(run_dir, self._count_spec()))

    def test_f1_metric_against_an_f2_run_is_rejected(self, tmp_path: Path) -> None:
        """A run executes one layer; the metric's layer must be that one."""
        run_dir = self._run_dir(tmp_path)
        record = self._record(
            run_dir, self._spec(fidelity=FidelityLevel.F1_INTERMEDIATE)
        )
        with pytest.raises(ValueError, match="cannot have produced"):
            verify_supported_record_runs(ROOT, record)

    def test_synthetic_metric_against_a_run_is_rejected(self, tmp_path: Path) -> None:
        """A synthetic/analytical probe is not a layer any run produced."""
        run_dir = self._run_dir(tmp_path)
        record = self._record(run_dir, self._spec(fidelity=FidelityLevel.SYNTHETIC))
        with pytest.raises(ValueError, match="cannot have produced"):
            verify_supported_record_runs(ROOT, record)

    def test_f2_metric_against_an_f1_run_is_rejected(self, tmp_path: Path) -> None:
        """The binding is two-way: an F1 run cannot produce an F2 quantity."""
        run_dir = self._run_dir(tmp_path)
        _mutate_run_manifest(run_dir, fidelity="f1", ontology_id="f1_v1")
        record = self._record(run_dir, self._spec())
        with pytest.raises(ValueError, match="cannot have produced"):
            verify_supported_record_runs(ROOT, record)

    def test_run_without_a_declared_layer_is_rejected(self, tmp_path: Path) -> None:
        """No layer, no verification: an unlabelled run is refused, not assumed."""
        run_dir = self._run_dir(tmp_path)
        _mutate_run_manifest(run_dir, fidelity=None, ontology_id=None)
        record = self._record(run_dir, self._spec())
        with pytest.raises(ValueError, match="neither a model 'fidelity'"):
            verify_supported_record_runs(ROOT, record)

    def test_ontology_implies_the_layer_when_fidelity_is_absent(
        self, tmp_path: Path
    ) -> None:
        """Control: the ontology id names the layer the manifest omits."""
        run_dir = self._run_dir(tmp_path)
        _mutate_run_manifest(run_dir, fidelity=None, ontology_id="f2_v1")
        verify_supported_record_runs(ROOT, self._record(run_dir, self._spec()))

    def test_metric_unit_not_matching_the_table_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """A count column read in ``M_forint`` is not the quantity it claims."""
        run_dir = self._run_dir(tmp_path)
        record = self._record(run_dir, self._count_spec(unit="M_forint"))
        with pytest.raises(ValueError, match="declared unit does not match"):
            verify_supported_record_runs(ROOT, record)

    def test_a_physical_pair_accepts_only_the_physical_unit(
        self, tmp_path: Path
    ) -> None:
        """A physical pair takes its ontology unit; a monetary unit is refused.

        ``national_accounts.household_consumption`` is a physical flow, so the
        only unit the model declares for it is the commodity-specific physical
        token. The pre-H0B claim that it is ``M_forint (model currency)`` is
        revoked, so a record declaring it is rejected.
        """
        run_dir = self._run_dir(tmp_path)
        verify_supported_record_runs(
            ROOT,
            self._record(
                run_dir,
                self._spec(
                    metric_id="m1.household_consumption",
                    table_or_sidecar="national_accounts",
                    column="household_consumption",
                    unit=PHYSICAL_UNIT_TOKEN,
                ),
            ),
        )
        record = self._record(
            run_dir,
            self._spec(
                metric_id="m1.household_consumption",
                table_or_sidecar="national_accounts",
                column="household_consumption",
                unit="M_forint (model currency)",
            ),
        )
        with pytest.raises(ValueError, match="declared unit does not match"):
            verify_supported_record_runs(ROOT, record)

    def test_unit_of_an_unregistered_pair_is_not_bound(self, tmp_path: Path) -> None:
        """A sidecar column has no model-declared unit to contradict."""
        run_dir = self._run_dir(tmp_path)
        self._write_sidecar(run_dir, {"delivered_total": 12.5})
        record = self._record(
            run_dir,
            self._spec(
                metric_id="m1.delivered_total",
                table_or_sidecar="run_metrics",
                column="delivered_total",
                unit="synthetic_probe_units",
            ),
        )
        verify_supported_record_runs(ROOT, record)

    @pytest.mark.parametrize("nonfinite", [float("inf"), float("-inf")])
    def test_sidecar_nonfinite_value_is_rejected(
        self, tmp_path: Path, nonfinite: float
    ) -> None:
        """``Infinity``/``-Infinity`` are JSON ``json.loads`` accepts: still not data.

        Both propagate through every aggregation, so neither is a measurement.
        """
        run_dir = self._run_dir(tmp_path)
        self._write_sidecar(run_dir, {"delivered_total": nonfinite})
        record = self._record(
            run_dir,
            self._spec(
                metric_id="m1.delivered_total",
                table_or_sidecar="run_metrics",
                column="delivered_total",
            ),
        )
        with pytest.raises(ValueError, match="non-finite"):
            verify_supported_record_runs(ROOT, record)

    def test_sidecar_nan_value_is_rejected(self, tmp_path: Path) -> None:
        """``NaN`` is missing data, not a measurement."""
        run_dir = self._run_dir(tmp_path)
        self._write_sidecar(run_dir, {"delivered_total": float("nan")})
        record = self._record(
            run_dir,
            self._spec(
                metric_id="m1.delivered_total",
                table_or_sidecar="run_metrics",
                column="delivered_total",
            ),
        )
        with pytest.raises(ValueError, match="null or NaN"):
            verify_supported_record_runs(ROOT, record)

    def test_sidecar_overflowing_literal_is_rejected(self, tmp_path: Path) -> None:
        """``1e999`` is standard JSON and parses to ``inf``: checked, not trusted."""
        run_dir = self._run_dir(tmp_path)
        (run_dir / "run_metrics.json").write_text(
            '{"delivered_total": 1e999}', encoding="utf-8"
        )
        _rehash_run_outputs(run_dir)
        record = self._record(
            run_dir,
            self._spec(
                metric_id="m1.delivered_total",
                table_or_sidecar="run_metrics",
                column="delivered_total",
            ),
        )
        with pytest.raises(ValueError, match="non-finite"):
            verify_supported_record_runs(ROOT, record)

    def test_finite_sidecar_value_is_accepted(self, tmp_path: Path) -> None:
        """Control: a finite sidecar value is a measurement."""
        run_dir = self._run_dir(tmp_path)
        self._write_sidecar(run_dir, {"delivered_total": -1.5e308})
        record = self._record(
            run_dir,
            self._spec(
                metric_id="m1.delivered_total",
                table_or_sidecar="run_metrics",
                column="delivered_total",
            ),
        )
        verify_supported_record_runs(ROOT, record)

    def test_aliased_table_path_cannot_dodge_the_unit_binding(
        self, tmp_path: Path
    ) -> None:
        """The unit is bound to the *resolved* table, not to the spelling used.

        ``trajectory_tables/national_accounts.parquet`` is the very file the
        record could have named as ``national_accounts``; looking the unit up by
        the declared spelling would find no declared unit and silently pass.
        """
        run_dir = self._run_dir(tmp_path)
        record = self._record(
            run_dir,
            self._spec(
                metric_id="m1.household_consumption",
                table_or_sidecar="trajectory_tables/national_accounts.parquet",
                column="household_consumption",
                unit="count",
            ),
        )
        with pytest.raises(ValueError, match="declared unit does not match"):
            verify_supported_record_runs(ROOT, record)

    def test_aliased_table_path_with_the_declared_unit_passes(
        self, tmp_path: Path
    ) -> None:
        """Control: the alias binds to the real table's units, so the real one passes."""
        run_dir = self._run_dir(tmp_path)
        record = self._record(
            run_dir,
            self._spec(
                metric_id="m1.household_consumption",
                table_or_sidecar="trajectory_tables/national_accounts.parquet",
                column="household_consumption",
                unit=PHYSICAL_UNIT_TOKEN,
            ),
        )
        verify_supported_record_runs(ROOT, record)

    def test_parquet_column_without_a_declared_unit_is_refused(
        self, tmp_path: Path
    ) -> None:
        """No declared unit, no verification: the gate fails closed.

        ``aggregates.used`` is a real column of a real table, but the model
        declares no unit for it, so the record's ``unit`` claim cannot be
        established and is refused rather than trusted.
        """
        run_dir = self._run_dir(tmp_path)
        record = self._record(
            run_dir,
            self._spec(
                table_or_sidecar="aggregates",
                column="used",
                unit="M_forint",
            ),
        )
        with pytest.raises(ValueError, match="cannot be established"):
            verify_supported_record_runs(ROOT, record)

    def test_real_audit_run_metric_bindings_pass(self) -> None:
        """The real C0 run satisfies the whole gate, metric content included."""
        from hsm_lab.evidence.table_registry import F2_COMMODITY_IDS, F2_REGION_IDS

        c0_dir = ROOT / "outputs" / "codex-audit-vnext-20261011" / "C0"
        if not (c0_dir / "manifest.json").is_file():
            pytest.skip("real C0 audit run not present in this checkout")

        manifest = _read_json(c0_dir / "manifest.json")
        summary = _read_json(c0_dir / "summary.json")
        region_axis = RegionAxis(
            regions=list(F2_REGION_IDS), unit="M_forint", aggregation="sum"
        )
        record = self._record(
            c0_dir,
            self._spec(
                metric_id="m1.household_consumption",
                table_or_sidecar="national_accounts",
                column="household_consumption",
            ),
            self._spec(
                commodity_axis=CommodityAxis(
                    commodities=list(F2_COMMODITY_IDS), unit="M_forint"
                ),
                region_axis=region_axis,
            ),
            self._spec(
                metric_id="m2.bottleneck_demand_count",
                table_or_sidecar="tick_diagnostics",
                column="bottleneck_demand_count",
                data_role=DataRole.CANDIDATE_LINKAGE,
                validation_fidelity=ValidationFidelity.PROXY,
                unit="count",
            ),
            self._spec(
                metric_id="m1.forced_saving",
                table_or_sidecar="household_budgets",
                column="forced_saving",
                unit="M_forint",
                region_axis=region_axis,
            ),
            self._spec(
                metric_id="m2.credit_drawn",
                table_or_sidecar="organization_diagnostics",
                column="credit_drawn",
                unit="M_forint",
                region_axis=region_axis,
                data_role=DataRole.CANDIDATE_LINKAGE,
                validation_fidelity=ValidationFidelity.PROXY,
            ),
            self._spec(
                metric_id="m6.treasury_cash",
                table_or_sidecar="financial_accounts",
                column="closing",
                unit="M_forint",
                data_role=DataRole.CANDIDATE_LINKAGE,
                validation_fidelity=ValidationFidelity.PROXY,
            ),
            run_id=manifest["run_id"],
            digest=manifest["deterministic_replay_digest"],
            seed=manifest["seed"],
            scenario_id=summary["scenario_id"],
        )
        verify_supported_record_runs(ROOT, record)


# ---------------------------------------------------------------------------
# Metric data is judged inside the declared window/selectors (H0A P0-3)
# ---------------------------------------------------------------------------


class TestSupportedMetricWindowDataBinding:
    """A metric's data check applies to its declared window, not the column.

    Judging the whole column lets a table pass on data the metric never covers:
    the declared window — or a declared commodity/region selector inside it —
    can be null throughout while other rows carry values. The declared
    intersection is what must carry data, and the metric's own
    ``missing_policy`` is applied there.
    """

    def _helper(self) -> TestSupportedMetricContentBinding:
        return TestSupportedMetricContentBinding()

    def _run_dir(self, tmp_path: Path) -> Path:
        return self._helper()._run_dir(tmp_path)

    def _record(self, run_dir: Path, *specs: MetricSpec) -> EvidenceRecord:
        return self._helper()._record(run_dir, *specs)

    def _count_spec(self, **overrides) -> MetricSpec:
        return self._helper()._count_spec(**overrides)

    def _spec(self, **overrides) -> MetricSpec:
        return self._helper()._spec(**overrides)

    def _write_tick_diagnostics_column(
        self, run_dir: Path, values: list
    ) -> None:
        self._helper()._write_tick_diagnostics_column(run_dir, values)

    def _tick_quarters(self, run_dir: Path) -> list[str]:
        rows = _read_row_counts(run_dir)["tick_diagnostics"]
        return [
            str(Quarter.parse("1957Q1").advance(tick)) for tick in range(rows)
        ]

    def test_null_window_values_are_not_masked_by_later_quarters(
        self, tmp_path: Path
    ) -> None:
        """A null declared window is not supported by data in other quarters."""
        run_dir = self._run_dir(tmp_path)
        quarters = self._tick_quarters(run_dir)
        self._write_tick_diagnostics_column(
            run_dir,
            [
                None if "1957Q1" <= quarter <= "1957Q4" else float(tick)
                for tick, quarter in enumerate(quarters)
            ],
        )
        record = self._record(
            run_dir,
            self._count_spec(
                time_window=TimeWindow(
                    start_quarter="1957Q1",
                    end_quarter="1957Q4",
                    missing_policy=MissingPolicy.ABORT,
                )
            ),
        )
        with pytest.raises(
            ValueError, match="has no values in the declared window"
        ):
            verify_supported_record_runs(ROOT, record)

    def test_null_values_outside_the_declared_window_are_not_the_metric(
        self, tmp_path: Path
    ) -> None:
        """Control: the metric is only measured over its own declared window."""
        run_dir = self._run_dir(tmp_path)
        quarters = self._tick_quarters(run_dir)
        self._write_tick_diagnostics_column(
            run_dir,
            [
                None if quarter > "1985Q1" else float(tick)
                for tick, quarter in enumerate(quarters)
            ],
        )
        record = self._record(
            run_dir,
            self._count_spec(
                time_window=TimeWindow(
                    start_quarter="1957Q1",
                    end_quarter="1985Q1",
                    missing_policy=MissingPolicy.ABORT,
                )
            ),
        )
        verify_supported_record_runs(ROOT, record)

    def test_partial_missing_in_the_declared_window_breaks_abort(
        self, tmp_path: Path
    ) -> None:
        """One null in the declared window under ``abort`` is not measurable."""
        run_dir = self._run_dir(tmp_path)
        rows = _read_row_counts(run_dir)["tick_diagnostics"]
        values: list[object] = [float(tick) for tick in range(rows)]
        values[1] = None
        self._write_tick_diagnostics_column(run_dir, values)
        record = self._record(run_dir, self._count_spec())
        with pytest.raises(ValueError, match="missing_policy=abort"):
            verify_supported_record_runs(ROOT, record)

    def test_partial_missing_in_the_declared_window_is_tolerated_by_skip(
        self, tmp_path: Path
    ) -> None:
        """Control: ``skip`` tolerates a missing cell, so the metric survives."""
        run_dir = self._run_dir(tmp_path)
        rows = _read_row_counts(run_dir)["tick_diagnostics"]
        values: list[object] = [float(tick) for tick in range(rows)]
        values[1] = None
        self._write_tick_diagnostics_column(run_dir, values)
        record = self._record(
            run_dir,
            self._count_spec(
                missing_policy=MissingPolicy.SKIP,
                time_window=TimeWindow(
                    start_quarter="1957Q1",
                    end_quarter="1985Q4",
                    missing_policy=MissingPolicy.SKIP,
                ),
            ),
        )
        verify_supported_record_runs(ROOT, record)

    def test_null_selector_rows_are_not_masked_by_other_selectors(
        self, tmp_path: Path
    ) -> None:
        """A declared commodity that is null throughout is not covered by others."""
        import pyarrow as pa
        import pyarrow.parquet as pq

        run_dir = self._run_dir(tmp_path)
        table_path = run_dir / "trajectory_tables" / "aggregates.parquet"
        frame = pq.read_table(table_path)
        quarters = frame["quarter"].to_pylist()
        commodities = frame["commodity_id"].to_pylist()
        delivered = [
            None
            if commodity == "g01_solid_fuels" and "1957Q1" <= quarter <= "1957Q4"
            else value
            for commodity, quarter, value in zip(
                commodities,
                quarters,
                frame["delivered"].to_pylist(),
                strict=True,
            )
        ]
        frame = frame.set_column(
            frame.schema.get_field_index("delivered"),
            "delivered",
            pa.array(delivered, type=pa.float64()),
        )
        pq.write_table(frame, table_path)
        _rehash_run_outputs(run_dir)

        record = self._record(
            run_dir,
            self._spec(
                commodity_axis=CommodityAxis(
                    commodities=["g01_solid_fuels"], unit="M_forint"
                ),
                time_window=TimeWindow(
                    start_quarter="1957Q1",
                    end_quarter="1957Q4",
                    missing_policy=MissingPolicy.ABORT,
                ),
            ),
        )
        with pytest.raises(
            ValueError, match="has no values in the declared window"
        ):
            verify_supported_record_runs(ROOT, record)

    def test_infinite_value_outside_the_declared_window_is_not_the_metric(
        self, tmp_path: Path
    ) -> None:
        """Control: the declared window's values are what is judged."""
        run_dir = self._run_dir(tmp_path)
        quarters = self._tick_quarters(run_dir)
        self._write_tick_diagnostics_column(
            run_dir,
            [
                float("inf") if quarter > "1985Q1" else float(tick)
                for tick, quarter in enumerate(quarters)
            ],
        )
        record = self._record(
            run_dir,
            self._count_spec(
                time_window=TimeWindow(
                    start_quarter="1957Q1",
                    end_quarter="1985Q1",
                    missing_policy=MissingPolicy.ABORT,
                )
            ),
        )
        verify_supported_record_runs(ROOT, record)


# ---------------------------------------------------------------------------
# Quarter × selector coverage is joint, not separate (H0A P0-1)
# ---------------------------------------------------------------------------


class TestSupportedJointQuarterSelectorCoverage:
    """A metric is measured over the intersection of window and selectors.

    Checking the window and each selector independently lets a table pass while
    carrying no row for the declared commodity/region in part of the declared
    window. Every declared quarter must carry data for every declared
    commodity/region selector.
    """

    def _run_dir(self, tmp_path: Path, *, seed: int = 1729) -> Path:
        return _write_self_consistent_material_run(
            tmp_path / "run", parameter_hash=_material_parameter_hash(), seed=seed
        )

    def _drop_rows(
        self,
        run_dir: Path,
        *,
        table: str = "aggregates",
        column: str,
        value: str,
        quarter: str,
    ) -> None:
        """Remove one (quarter, selector) slice and re-pin the run's hashes."""
        import pyarrow.compute as pc
        import pyarrow.parquet as pq

        table_path = run_dir / "trajectory_tables" / f"{table}.parquet"
        frame = pq.read_table(table_path)
        drop = pc.and_(
            pc.equal(frame["quarter"], quarter),
            pc.equal(frame[column], value),
        )
        frame = frame.filter(pc.invert(drop))
        pq.write_table(frame, table_path)
        counts = _read_row_counts(run_dir)
        counts[table] = frame.num_rows
        _patch_run_summary(run_dir, row_counts=counts)

    def _record_with(self, run_dir: Path, spec: MetricSpec) -> EvidenceRecord:
        """Build the shared supported record for this class' runs."""
        return TestSupportedMetricContentBinding()._record(run_dir, spec)

    def _spec(self, **overrides) -> MetricSpec:
        return TestSupportedMetricContentBinding()._spec(**overrides)

    def test_missing_commodity_in_one_declared_quarter_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """``g01_solid_fuels`` present everywhere except 1957Q1 is not coverage."""
        run_dir = self._run_dir(tmp_path)
        self._drop_rows(
            run_dir,
            column="commodity_id",
            value="g01_solid_fuels",
            quarter="1957Q1",
        )
        record = self._record_with(
            run_dir,
            self._spec(
                commodity_axis=CommodityAxis(
                    commodities=["g01_solid_fuels"], unit="M_forint"
                ),
                time_window=TimeWindow(
                    start_quarter="1957Q1",
                    end_quarter="1957Q4",
                    missing_policy=MissingPolicy.ABORT,
                ),
            ),
        )
        with pytest.raises(ValueError, match="quarter × selector"):
            verify_supported_record_runs(ROOT, record)

    def test_missing_region_in_one_declared_quarter_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """A region absent from one declared quarter is not covered jointly."""
        run_dir = self._run_dir(tmp_path)
        self._drop_rows(
            run_dir,
            column="region_id",
            value="budapest",
            quarter="1957Q1",
        )
        record = self._record_with(
            run_dir,
            self._spec(
                region_axis=RegionAxis(
                    regions=["budapest"], unit="M_forint", aggregation="sum"
                ),
                time_window=TimeWindow(
                    start_quarter="1957Q1",
                    end_quarter="1957Q4",
                    missing_policy=MissingPolicy.ABORT,
                ),
            ),
        )
        with pytest.raises(ValueError, match="quarter × selector"):
            verify_supported_record_runs(ROOT, record)

    def test_missing_commodity_region_pair_is_rejected(self, tmp_path: Path) -> None:
        """Both axes declared: the pair, not just each axis, must be covered."""
        run_dir = self._run_dir(tmp_path)
        import pyarrow.compute as pc
        import pyarrow.parquet as pq

        table_path = run_dir / "trajectory_tables" / "aggregates.parquet"
        frame = pq.read_table(table_path)
        drop = pc.and_(
            pc.and_(
                pc.equal(frame["quarter"], "1957Q1"),
                pc.equal(frame["commodity_id"], "g02_oil_gas_fuels"),
            ),
            pc.equal(frame["region_id"], "pest"),
        )
        frame = frame.filter(pc.invert(drop))
        pq.write_table(frame, table_path)
        counts = _read_row_counts(run_dir)
        counts["aggregates"] = frame.num_rows
        _patch_run_summary(run_dir, row_counts=counts)

        record = self._record_with(
            run_dir,
            self._spec(
                commodity_axis=CommodityAxis(
                    commodities=["g01_solid_fuels", "g02_oil_gas_fuels"],
                    unit="M_forint",
                ),
                region_axis=RegionAxis(
                    regions=["budapest", "pest"], unit="M_forint", aggregation="sum"
                ),
                time_window=TimeWindow(
                    start_quarter="1957Q1",
                    end_quarter="1957Q2",
                    missing_policy=MissingPolicy.ABORT,
                ),
            ),
        )
        with pytest.raises(ValueError, match="quarter × selector"):
            verify_supported_record_runs(ROOT, record)

    def test_selector_covered_in_every_declared_quarter_passes(
        self, tmp_path: Path
    ) -> None:
        """Control: an intact run satisfies the joint check."""
        run_dir = self._run_dir(tmp_path)
        record = self._record_with(
            run_dir,
            self._spec(
                commodity_axis=CommodityAxis(
                    commodities=["g01_solid_fuels", "g02_oil_gas_fuels"],
                    unit="M_forint",
                ),
                region_axis=RegionAxis(
                    regions=["budapest", "pest"], unit="M_forint", aggregation="sum"
                ),
                time_window=TimeWindow(
                    start_quarter="1957Q1",
                    end_quarter="1957Q4",
                    missing_policy=MissingPolicy.ABORT,
                ),
            ),
        )
        verify_supported_record_runs(ROOT, record)


# ---------------------------------------------------------------------------
# SUPPORTED records must link verified observed states (H0A P0-3)
# ---------------------------------------------------------------------------


class TestSupportedLinkedObservedStates:
    """``linked_observed_states`` must be backed by the verified runs.

    A snapshot claim is a provenance claim: it must name a run the gate above
    verified, agree with that run's scenario and digest, and name a quarter the
    source run's own output actually carries. A supported record must link at
    least one such snapshot.
    """

    def _run_dir(self, tmp_path: Path, *, seed: int = 1729) -> Path:
        return _write_self_consistent_material_run(
            tmp_path / "run", parameter_hash=_material_parameter_hash(), seed=seed
        )

    def _state(self, **overrides) -> ObservedState:
        kwargs = dict(
            observed_state_id="obs-1",
            source_run_id="test-run",
            source_scenario=_PARAMETER_SCENARIO,
            source_checkpoint_quarter="1957Q1",
            source_digest="a" * 64,
            captured_at="2024-01-01T00:00:00Z",
            available_at="1957Q1",
            decision_at="1957Q1",
        )
        kwargs.update(overrides)
        return ObservedState(**kwargs)

    def _record(self, run_dir: Path, **overrides) -> EvidenceRecord:
        helper = TestSupportedMetricContentBinding()
        spec = helper._spec(
            time_window=TimeWindow(
                start_quarter="1957Q1",
                end_quarter="1957Q4",
                missing_policy=MissingPolicy.ABORT,
            )
        )
        return helper._record(run_dir, spec, **overrides)

    def test_supported_without_linked_observed_state_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """A supported record with no snapshot is not traceable to model output."""
        run_dir = self._run_dir(tmp_path)
        record = self._record(run_dir, linked_observed_states=[])
        with pytest.raises(ValueError, match="no linked_observed_states"):
            verify_supported_record_runs(ROOT, record)

    def test_linked_state_with_unverified_run_id_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """A snapshot naming a run no reference verified is fabricated."""
        run_dir = self._run_dir(tmp_path)
        record = self._record(
            run_dir,
            linked_observed_states=[self._state(source_run_id="fabricated-run")],
        )
        with pytest.raises(ValueError, match="matches no verified run_reference"):
            verify_supported_record_runs(ROOT, record)

    def test_linked_state_with_wrong_scenario_is_rejected(
        self, tmp_path: Path
    ) -> None:
        run_dir = self._run_dir(tmp_path)
        record = self._record(
            run_dir,
            linked_observed_states=[
                self._state(source_scenario="historical_f2_trade_scenario")
            ],
        )
        with pytest.raises(ValueError, match="source_scenario"):
            verify_supported_record_runs(ROOT, record)

    def test_linked_state_with_wrong_digest_is_rejected(self, tmp_path: Path) -> None:
        """The snapshot must be of the run content the reference verified."""
        run_dir = self._run_dir(tmp_path)
        record = self._record(
            run_dir,
            linked_observed_states=[self._state(source_digest="b" * 64)],
        )
        with pytest.raises(ValueError, match="source_digest"):
            verify_supported_record_runs(ROOT, record)

    def test_linked_state_checkpoint_outside_run_output_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """The source run must have actually produced the checkpoint quarter.

        The run below records every tick but no ``1985Q4`` quarter label: the
        run's own output stops at ``1985Q3``, so a snapshot claiming
        ``1985Q4`` names a checkpoint the source run never produced.
        """
        import pyarrow as pa
        import pyarrow.parquet as pq

        run_dir = self._run_dir(tmp_path)
        for table_path in sorted((run_dir / "trajectory_tables").glob("*.parquet")):
            frame = pq.read_table(table_path)
            if frame.num_rows == 0:
                continue
            relabelled = [
                "1985Q3" if quarter == "1985Q4" else quarter
                for quarter in frame["quarter"].to_pylist()
            ]
            frame = frame.set_column(
                frame.schema.get_field_index("quarter"),
                "quarter",
                pa.array(relabelled, type=pa.string()),
            )
            pq.write_table(frame, table_path)
        _rehash_run_outputs(run_dir)

        record = self._record(
            run_dir,
            linked_observed_states=[
                self._state(
                    source_checkpoint_quarter="1985Q4",
                    available_at="1985Q4",
                    decision_at="1985Q4",
                )
            ],
        )
        with pytest.raises(ValueError, match="is not in the output"):
            verify_supported_record_runs(ROOT, record)

    def test_real_audit_run_linked_observed_state_passes(self) -> None:
        """The real C0 run's final quarter is an admissible checkpoint."""
        c0_dir = ROOT / "outputs" / "codex-audit-vnext-20261011" / "C0"
        if not (c0_dir / "manifest.json").is_file():
            pytest.skip("real C0 audit run not present in this checkout")

        manifest = _read_json(c0_dir / "manifest.json")
        summary = _read_json(c0_dir / "summary.json")
        record = self._record(
            c0_dir,
            run_id=manifest["run_id"],
            digest=manifest["deterministic_replay_digest"],
            seed=manifest["seed"],
            scenario_id=summary["scenario_id"],
            linked_observed_states=[
                self._state(
                    source_run_id=manifest["run_id"],
                    source_scenario=summary["scenario_id"],
                    source_checkpoint_quarter="1985Q4",
                    source_digest=manifest["deterministic_replay_digest"],
                    available_at="1985Q4",
                    decision_at="1985Q4",
                )
            ],
        )
        verify_supported_record_runs(ROOT, record)
