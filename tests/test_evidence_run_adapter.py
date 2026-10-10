"""P07B1 regression tests: evidence run adapter and negative-control fixture.

Tests the adapter from ScenarioSpec to EvidenceRecord, the digest-regression
helper, and the negative-control fixture. No production engine is modified.
"""

from __future__ import annotations

from pathlib import Path

from hsm_lab.evidence.adapter import load_v2_card_registry
from hsm_lab.evidence.run_adapter import (
    AdapterConfig,
    build_stub_evidence_record,
    get_c0_digest,
    get_c1_digest,
    verify_digest_unchanged,
)
from hsm_lab.evidence.schemas import EvidenceStatus

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Reference digest constants
# ---------------------------------------------------------------------------

def test_c0_digest_constant() -> None:
    """C0 reference digest must be the frozen audit value."""
    digest = get_c0_digest()
    assert digest == "92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d"
    assert len(digest) == 64


def test_c1_digest_constant() -> None:
    """C1 reference digest must be the frozen audit value."""
    digest = get_c1_digest()
    assert digest == "c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5"
    assert len(digest) == 64


# ---------------------------------------------------------------------------
# AdapterConfig
# ---------------------------------------------------------------------------

def test_adapter_config_defaults() -> None:
    """AdapterConfig must default run_model=False (no experiment execution at B1)."""
    cfg = AdapterConfig(scenario_id="historical_f2_replay", phase="P07B1")
    assert cfg.run_model is False
    assert cfg.known_digest is None


def test_adapter_config_with_known_digest() -> None:
    """AdapterConfig accepts a known_digest for regression comparison."""
    cfg = AdapterConfig(
        scenario_id="historical_f2_replay",
        phase="P07B1",
        known_digest=get_c0_digest(),
    )
    assert cfg.known_digest == get_c0_digest()


# ---------------------------------------------------------------------------
# build_stub_evidence_record
# ---------------------------------------------------------------------------

def test_stub_record_has_no_experiment_results() -> None:
    """Stub record must have status=DECLARED and empty linked_observed_states."""
    registry = load_v2_card_registry(ROOT, "P07B1")
    record = build_stub_evidence_record(
        scenario_id="historical_f2_replay",
        phase="P07B1",
        mechanism_ids=["M1"],
        registry=registry,
        run_digest=None,
        status=EvidenceStatus.DECLARED,
    )
    assert record.status == EvidenceStatus.DECLARED
    assert record.linked_observed_states == []
    assert len(record.metric_specs) >= 1


def test_stub_record_contains_m1_metrics() -> None:
    """Stub record for M1 must include at least household_consumption metrics."""
    registry = load_v2_card_registry(ROOT, "P07B1")
    record = build_stub_evidence_record(
        scenario_id="historical_f2_replay",
        phase="P07B1",
        mechanism_ids=["M1"],
        registry=registry,
    )
    metric_ids = {spec.metric_id for spec in record.metric_specs}
    # At least household_consumption should be present
    m1_ids = {mid for mid in metric_ids if mid.startswith("m1.")}
    assert len(m1_ids) >= 1


def test_stub_record_multi_mechanism() -> None:
    """Stub record for multiple mechanisms includes specs from all."""
    registry = load_v2_card_registry(ROOT, "P07B1")
    record = build_stub_evidence_record(
        scenario_id="historical_f2_replay",
        phase="P07B1",
        mechanism_ids=["M1", "M5"],
        registry=registry,
    )
    metric_ids = {spec.metric_id for spec in record.metric_specs}
    m1_ids = {mid for mid in metric_ids if mid.startswith("m1.")}
    m5_ids = {mid for mid in metric_ids if mid.startswith("m5.")}
    assert len(m1_ids) >= 1
    assert len(m5_ids) >= 1


def test_stub_record_record_id_contains_phase_and_scenario() -> None:
    """Stub record ID must encode phase and scenario for traceability."""
    registry = load_v2_card_registry(ROOT, "P07B1")
    record = build_stub_evidence_record(
        scenario_id="historical_f2_replay",
        phase="P07B1",
        mechanism_ids=["M1"],
        registry=registry,
    )
    assert "P07B1" in record.record_id
    assert "historical_f2_replay" in record.record_id


# ---------------------------------------------------------------------------
# verify_digest_unchanged — negative-control fixture
# ---------------------------------------------------------------------------

def test_verify_digest_unchanged_returns_false_for_nonexistent_dir(tmp_path: Path) -> None:
    """verify_digest_unchanged must return False when output dir does not exist."""
    result = verify_digest_unchanged(
        scenario_id="historical_f2_replay",
        seed=1729,
        expected_digest=get_c0_digest(),
        output_dir=tmp_path / "nonexistent",
        root=ROOT,
    )
    assert result is False


def test_verify_digest_unchanged_returns_false_for_wrong_digest(tmp_path: Path) -> None:
    """verify_digest_unchanged must return False when digest differs."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"deterministic_replay_digest": "wrong_digest_value"}', encoding="utf-8")
    result = verify_digest_unchanged(
        scenario_id="historical_f2_replay",
        seed=1729,
        expected_digest=get_c0_digest(),
        output_dir=tmp_path,
        root=ROOT,
    )
    assert result is False


def test_verify_digest_unchanged_returns_true_for_matching_digest(tmp_path: Path) -> None:
    """verify_digest_unchanged must return True when digest matches."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"deterministic_replay_digest": "' + get_c0_digest() + '"}',
        encoding="utf-8",
    )
    result = verify_digest_unchanged(
        scenario_id="historical_f2_replay",
        seed=1729,
        expected_digest=get_c0_digest(),
        output_dir=tmp_path,
        root=ROOT,
    )
    assert result is True


def test_verify_digest_unchanged_uses_run_digest_fallback(tmp_path: Path) -> None:
    """verify_digest_unchanged falls back to run_digest if deterministic_replay_digest absent."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"run_digest": "' + get_c0_digest() + '"}',
        encoding="utf-8",
    )
    result = verify_digest_unchanged(
        scenario_id="historical_f2_replay",
        seed=1729,
        expected_digest=get_c0_digest(),
        output_dir=tmp_path,
        root=ROOT,
    )
    assert result is True


def test_verify_digest_unchanged_invalid_json(tmp_path: Path) -> None:
    """verify_digest_unchanged returns False on malformed manifest."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text("not valid json {{{", encoding="utf-8")
    result = verify_digest_unchanged(
        scenario_id="historical_f2_replay",
        seed=1729,
        expected_digest=get_c0_digest(),
        output_dir=tmp_path,
        root=ROOT,
    )
    assert result is False


# ---------------------------------------------------------------------------
# Negative-control fixture: C0 digest from audit run directory
# ---------------------------------------------------------------------------

def test_negative_control_c0_digest_matches_audit() -> None:
    """The C0 digest from the audit run directory must match the frozen reference."""
    c0_dir = ROOT / "outputs" / "codex-audit-vnext-20261011" / "C0"
    result = verify_digest_unchanged(
        scenario_id="historical_f2_replay",
        seed=1729,
        expected_digest=get_c0_digest(),
        output_dir=c0_dir,
        root=ROOT,
    )
    assert result is True


def test_negative_control_c1_digest_matches_audit() -> None:
    """The C1 digest from the audit run directory must match the frozen reference."""
    c1_dir = ROOT / "outputs" / "codex-audit-vnext-20261011" / "C1"
    result = verify_digest_unchanged(
        scenario_id="historical_f2_trade_scenario",
        seed=1729,
        expected_digest=get_c1_digest(),
        output_dir=c1_dir,
        root=ROOT,
    )
    assert result is True
