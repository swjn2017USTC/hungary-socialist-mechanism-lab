"""P07B1 regression tests: evidence run adapter.

Tests the adapter config, digest constants, and the verify_digest_unchanged
provenance helper. No production engine is modified.
"""

from __future__ import annotations

import json
from pathlib import Path

from hsm_lab.evidence.run_adapter import (
    AdapterConfig,
    get_c0_digest,
    get_c1_digest,
    verify_digest_unchanged,
)

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
# verify_digest_unchanged — boundary tests (H0A §5)
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
    # Valid manifest format but wrong digest
    manifest.write_text(
        json.dumps({
            "schema_version": "1",
            "run_id": "test-run",
            "run_kind": "material_household_simulation",
            "status": "completed",
            "seed": 1729,
            "deterministic_replay_digest": "0" * 64,  # wrong digest
            "scenario_hash": "a" * 64,
            "lock_hash": "b" * 64,
            "data_manifest_hash": "c" * 64,
            "parameter_hash": "d" * 64,
            "output_hashes": {},
            "failure_message": None,
            "completed_ticks": 4,
        }),
        encoding="utf-8",
    )
    result = verify_digest_unchanged(
        scenario_id="historical_f2_replay",
        seed=1729,
        expected_digest=get_c0_digest(),
        output_dir=tmp_path,
        root=ROOT,
    )
    assert result is False


def test_verify_digest_unchanged_returns_false_for_wrong_seed(tmp_path: Path) -> None:
    """verify_digest_unchanged must return False when seed differs."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({
            "schema_version": "1",
            "run_id": "test-run",
            "run_kind": "material_household_simulation",
            "status": "completed",
            "seed": 9999,  # wrong seed
            "deterministic_replay_digest": get_c0_digest(),
            "scenario_hash": "a" * 64,
            "lock_hash": "b" * 64,
            "data_manifest_hash": "c" * 64,
            "parameter_hash": "d" * 64,
            "output_hashes": {},
            "failure_message": None,
            "completed_ticks": 4,
        }),
        encoding="utf-8",
    )
    result = verify_digest_unchanged(
        scenario_id="historical_f2_replay",
        seed=1729,  # correct seed
        expected_digest=get_c0_digest(),
        output_dir=tmp_path,
        root=ROOT,
    )
    assert result is False


def test_verify_digest_unchanged_returns_false_for_incomplete_run(tmp_path: Path) -> None:
    """verify_digest_unchanged must return False when run status is not completed."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({
            "schema_version": "1",
            "run_id": "test-run",
            "run_kind": "material_household_simulation",
            "status": "running",  # not completed
            "seed": 1729,
            "deterministic_replay_digest": get_c0_digest(),
            "scenario_hash": "a" * 64,
            "lock_hash": "b" * 64,
            "data_manifest_hash": "c" * 64,
            "parameter_hash": "d" * 64,
            "output_hashes": {},
            "failure_message": None,
            "completed_ticks": 0,
        }),
        encoding="utf-8",
    )
    result = verify_digest_unchanged(
        scenario_id="historical_f2_replay",
        seed=1729,
        expected_digest=get_c0_digest(),
        output_dir=tmp_path,
        root=ROOT,
    )
    assert result is False


def test_verify_digest_unchanged_returns_false_for_failed_run(tmp_path: Path) -> None:
    """verify_digest_unchanged must return False when run has failure_message."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({
            "schema_version": "1",
            "run_id": "test-run",
            "run_kind": "material_household_simulation",
            "status": "completed",
            "seed": 1729,
            "deterministic_replay_digest": get_c0_digest(),
            "scenario_hash": "a" * 64,
            "lock_hash": "b" * 64,
            "data_manifest_hash": "c" * 64,
            "parameter_hash": "d" * 64,
            "output_hashes": {},
            "failure_message": "something went wrong",
            "completed_ticks": 4,
        }),
        encoding="utf-8",
    )
    result = verify_digest_unchanged(
        scenario_id="historical_f2_replay",
        seed=1729,
        expected_digest=get_c0_digest(),
        output_dir=tmp_path,
        root=ROOT,
    )
    assert result is False


def test_verify_digest_unchanged_returns_false_for_zero_hash(tmp_path: Path) -> None:
    """verify_digest_unchanged must return False when manifest has zero SHA hashes."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({
            "schema_version": "1",
            "run_id": "test-run",
            "run_kind": "material_household_simulation",
            "status": "completed",
            "seed": 1729,
            "deterministic_replay_digest": get_c0_digest(),
            "scenario_hash": "0" * 64,  # zero hash
            "lock_hash": "b" * 64,
            "data_manifest_hash": "c" * 64,
            "parameter_hash": "d" * 64,
            "output_hashes": {},
            "failure_message": None,
            "completed_ticks": 4,
        }),
        encoding="utf-8",
    )
    result = verify_digest_unchanged(
        scenario_id="historical_f2_replay",
        seed=1729,
        expected_digest=get_c0_digest(),
        output_dir=tmp_path,
        root=ROOT,
    )
    assert result is False


def test_verify_digest_unchanged_returns_false_for_missing_required_files(tmp_path: Path) -> None:
    """verify_digest_unchanged must return False when required output files are missing."""
    # Write only manifest.json, no summary.json or parameters.json
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({
            "schema_version": "1",
            "run_id": "test-run",
            "run_kind": "material_household_simulation",
            "status": "completed",
            "seed": 1729,
            "deterministic_replay_digest": get_c0_digest(),
            "scenario_hash": "a" * 64,
            "lock_hash": "b" * 64,
            "data_manifest_hash": "c" * 64,
            "parameter_hash": "d" * 64,
            "output_hashes": {},
            "failure_message": None,
            "completed_ticks": 4,
        }),
        encoding="utf-8",
    )
    result = verify_digest_unchanged(
        scenario_id="historical_f2_replay",
        seed=1729,
        expected_digest=get_c0_digest(),
        output_dir=tmp_path,
        root=ROOT,
    )
    assert result is False


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
# Negative-control: C0/C1 from real audit run directories (if present)
# ---------------------------------------------------------------------------

def test_negative_control_c0_digest_matches_audit() -> None:
    """The C0 digest from the audit run directory must match the frozen reference."""
    c0_dir = ROOT / "outputs" / "codex-audit-vnext-20261011" / "C0"
    if not c0_dir.exists():
        # Real audit run output not present; skip
        return
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
    if not c1_dir.exists():
        # Real audit run output not present; skip
        return
    result = verify_digest_unchanged(
        scenario_id="historical_f2_trade_scenario",
        seed=1729,
        expected_digest=get_c1_digest(),
        output_dir=c1_dir,
        root=ROOT,
    )
    assert result is True
