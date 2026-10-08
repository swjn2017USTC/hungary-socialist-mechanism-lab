"""P02 material checkpoint: publish gates, strict resume, semantic tamper.

Covers the pinned checkpoint module end to end: version/hash refusal, a real
``tick_material``+history roundtrip, payload/tamper refusal, the material
state field-spec gates, and a real ``run_material`` pause -> resume whose
final replay digest equals the uninterrupted run.  Nothing is mocked; the
runner fixtures write into ``tmp_path`` only.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from hsm_lab.contract.guards import load_scenario
from hsm_lab.contract.schemas import ConfigError, ResearchGateError
from hsm_lab.data.material import build_synthetic_material_fixtures
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine import accounting as accounting_module
from hsm_lab.engine.material import advance_chain, run_material, tick_material
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import MaterialHistory, capture_material_stocks
from hsm_lab.storage.checkpoint import (
    CHECKPOINT_VERSION,
    checkpoint_dir,
    load_material_checkpoint,
    save_material_checkpoint,
    state_arrays,
)
from hsm_lab.storage.material_output import append_material_rows, history_frames
from tests.conftest import REPO_ROOT
from tests.test_material import (
    Fixture,
    _food_chain_fixture,
    _raw_bottleneck_fixture,
    _transport_fixture,
)

TICKS = 1


def _invariant_dict(fixture: Fixture, opening, flows) -> dict[str, Any]:
    summary = accounting_module.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    return {
        "max_material_abs_residual": float(summary.max_material_abs_residual),
        "max_material_tolerance_ratio": float(summary.max_material_tolerance_ratio),
        "max_finance_abs_residual": float(summary.max_finance_abs_residual),
        "max_finance_tolerance_ratio": float(summary.max_finance_tolerance_ratio),
        "checked_cells": int(summary.checked_cells),
        "per_ledger": dict(summary.per_ledger),
        "forcing_segment": "synthetic_warmup",
        "treasury_deposit_open": float(opening.treasury_deposit),
        "bank_reserves_open": [float(v) for v in opening.bank_reserves],
        "housing_completed": float(
            np.sum(np.asarray(fixture.state.dwelling_stock) - opening.dwelling_stock)
        ),
    }


def _advance_once(fixture: Fixture) -> MaterialHistory:
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(fixture.state, fixture.forcing(1), fixture.parameters, fixture.network)
    fixture.state.completed_ticks += 1
    history = MaterialHistory()
    history.digest_chain = advance_chain("0" * 64, fixture.state, flows)
    append_material_rows(
        history,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        region_ids=list(fixture.region_ids),
        commodity_ids=list(fixture.commodities),
        digest=history.digest_chain,
        invariant_summary=_invariant_dict(fixture, opening, flows),
    )
    return history


def _publish(tmp_path: Path, fixture: Fixture, contract, name: str):
    history = _advance_once(fixture)
    rng = RngRegistry(fixture.spec.seed)
    metadata = {
        "scenario": fixture.spec.model_dump(mode="json"),
        "region_ids": list(fixture.region_ids),
        "commodity_ids": list(fixture.commodities),
        "baseline_hash": contract.expected_baseline_sha256,
        "last_completed_quarter": str(
            fixture.spec.start.advance(fixture.state.completed_ticks - 1)
        ),
        "next_quarter": str(fixture.spec.start.advance(fixture.state.completed_ticks)),
        "source_run_id": "unit",
    }
    directory = checkpoint_dir(tmp_path, fixture.state.completed_ticks)
    path = save_material_checkpoint(
        directory, fixture.state, fixture.network, history, rng, metadata
    )
    return path, history, rng


def _checkpoint_fixture() -> Fixture:
    return _transport_fixture(transport_opening=1.0)


# ---------------------------------------------------------------------------
# Version and payload-hash refusal
# ---------------------------------------------------------------------------


def _minimal_checkpoint_dir(tmp_path: Path, version: str) -> Path:
    directory = tmp_path / f"ckpt-{version}"
    directory.mkdir()
    (directory / "metadata.json").write_text(
        json.dumps({"checkpoint_version": version}, indent=2) + "\n", encoding="utf-8"
    )
    return directory


def test_toy4_checkpoint_version_is_refused(tmp_path, contract) -> None:
    directory = _minimal_checkpoint_dir(tmp_path, "toy4-checkpoint-v1")
    fixture = _checkpoint_fixture()
    with pytest.raises(ResearchGateError, match="Toy-4"):
        load_material_checkpoint(directory, fixture.spec, contract, fixture.network)


@pytest.mark.parametrize("version", ["material-checkpoint-v2", "bogus", ""])
def test_unknown_checkpoint_version_is_refused(tmp_path, contract, version) -> None:
    directory = _minimal_checkpoint_dir(tmp_path, version)
    fixture = _checkpoint_fixture()
    with pytest.raises(ResearchGateError):
        load_material_checkpoint(directory, fixture.spec, contract, fixture.network)


def test_checkpoint_metadata_hash_tamper_is_refused(tmp_path, contract) -> None:
    fixture = _checkpoint_fixture()
    path, _history, _rng = _publish(tmp_path, fixture, contract, "hash")
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    metadata["network_static_hash"] = "0" * 64
    (path / "metadata.json").write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")
    with pytest.raises(ResearchGateError):
        load_material_checkpoint(path, fixture.spec, contract, fixture.network)


def test_checkpoint_payload_digest_mismatch_is_refused(tmp_path, contract) -> None:
    fixture = _checkpoint_fixture()
    path, _history, _rng = _publish(tmp_path, fixture, contract, "payload")
    (path / "state.npz").write_bytes((path / "state.npz").read_bytes() + b"\x00")
    with pytest.raises(ResearchGateError, match="digest"):
        load_material_checkpoint(path, fixture.spec, contract, fixture.network)


def test_checkpoint_extra_payload_file_is_refused(tmp_path, contract) -> None:
    fixture = _checkpoint_fixture()
    path, _history, _rng = _publish(tmp_path, fixture, contract, "extra")
    (path / "surprise.bin").write_bytes(b"x")
    with pytest.raises(ResearchGateError):
        load_material_checkpoint(path, fixture.spec, contract, fixture.network)


def test_checkpoint_overwrite_is_refused(tmp_path, contract) -> None:
    fixture = _checkpoint_fixture()
    path, history, rng = _publish(tmp_path, fixture, contract, "overwrite")
    with pytest.raises(ResearchGateError, match="exists"):
        save_material_checkpoint(
            path,
            fixture.state,
            fixture.network,
            history,
            rng,
            {"scenario": fixture.spec.model_dump(mode="json")},
        )


# ---------------------------------------------------------------------------
# Roundtrip
# ---------------------------------------------------------------------------


def test_material_checkpoint_roundtrip_restores_state_and_history(tmp_path, contract) -> None:
    fixture = _checkpoint_fixture()
    path, history, _rng = _publish(tmp_path, fixture, contract, "roundtrip")
    state, loaded_history, rng, metadata = load_material_checkpoint(
        path, fixture.spec, contract, fixture.network
    )
    assert state.completed_ticks == fixture.state.completed_ticks
    assert metadata["checkpoint_version"] == CHECKPOINT_VERSION
    assert rng.seed == fixture.spec.seed

    expected = state_arrays(fixture.state)
    restored = state_arrays(state)
    for name, array in expected.items():
        assert np.array_equal(array, restored[name]), name
    assert state.treasury_deposit == pytest.approx(fixture.state.treasury_deposit)
    assert state.cmea_settlement_balance == pytest.approx(fixture.state.cmea_settlement_balance)

    assert loaded_history.digest_chain == history.digest_chain
    original = history_frames(history)
    restored_frames = history_frames(loaded_history)
    for table in original:
        assert original[table].equals(restored_frames[table]), table


# ---------------------------------------------------------------------------
# Semantic / field-spec tamper refusal
# ---------------------------------------------------------------------------


def _rehash(path: Path) -> None:
    import hashlib

    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    metadata["payload_sha256"] = {
        entry.name: hashlib.sha256(entry.read_bytes()).hexdigest()
        for entry in sorted(path.iterdir())
        if entry.is_file() and entry.name != "metadata.json"
    }
    (path / "metadata.json").write_text(
        json.dumps(metadata, sort_keys=True) + "\n", encoding="utf-8"
    )


def _mutate_state(path: Path, mutate: Callable[[dict], None]) -> None:
    payload = dict(np.load(path / "state.npz", allow_pickle=False))
    mutate(payload)
    np.savez(path / "state.npz", **payload)
    _rehash(path)


def test_negative_stock_is_refused_even_when_rehashed(tmp_path, contract) -> None:
    fixture = _checkpoint_fixture()
    path, _history, _rng = _publish(tmp_path, fixture, contract, "negstock")

    def mutate(payload: dict) -> None:
        payload["stock_value"] = payload["stock_value"].copy()
        payload["stock_value"][0] = -5.0

    _mutate_state(path, mutate)
    with pytest.raises(ResearchGateError, match="negative"):
        load_material_checkpoint(path, fixture.spec, contract, fixture.network)


def test_extra_state_payload_field_is_refused(tmp_path, contract) -> None:
    fixture = _checkpoint_fixture()
    path, _history, _rng = _publish(tmp_path, fixture, contract, "extrafield")

    def mutate(payload: dict) -> None:
        payload["mystery_field"] = np.zeros(1, dtype="<f8")

    _mutate_state(path, mutate)
    with pytest.raises(ResearchGateError, match="field-spec"):
        load_material_checkpoint(path, fixture.spec, contract, fixture.network)


def test_wrong_completed_ticks_dtype_is_refused(tmp_path, contract) -> None:
    fixture = _checkpoint_fixture()
    path, _history, _rng = _publish(tmp_path, fixture, contract, "dtype")

    def mutate(payload: dict) -> None:
        payload["completed_ticks"] = np.asarray(fixture.state.completed_ticks, dtype="<i4")

    _mutate_state(path, mutate)
    with pytest.raises(ResearchGateError, match="completed_ticks"):
        load_material_checkpoint(path, fixture.spec, contract, fixture.network)


def test_network_static_hash_mismatch_is_refused(tmp_path, contract) -> None:
    fixture = _checkpoint_fixture()
    path, _history, _rng = _publish(tmp_path, fixture, contract, "netmismatch")
    other = _raw_bottleneck_fixture(energy_opening=100.0)
    with pytest.raises(ResearchGateError, match="network static hash"):
        load_material_checkpoint(path, fixture.spec, contract, other.network)


def test_scenario_axis_mismatch_is_refused(tmp_path, contract) -> None:
    fixture = _checkpoint_fixture()
    path, _history, _rng = _publish(tmp_path, fixture, contract, "axismismatch")
    other = _food_chain_fixture()
    with pytest.raises(ResearchGateError, match="scenario"):
        load_material_checkpoint(path, other.spec, contract, fixture.network)


def test_checkpoint_dir_layout(tmp_path) -> None:
    assert checkpoint_dir(tmp_path / "run", 40) == tmp_path / "run" / "checkpoints" / "tick-0040"


def test_history_table_deleted_is_refused(tmp_path, contract) -> None:
    fixture = _checkpoint_fixture()
    path, _history, _rng = _publish(tmp_path, fixture, contract, "tabledelete")
    (path / "aggregates.parquet").unlink()
    with pytest.raises(ResearchGateError):
        load_material_checkpoint(path, fixture.spec, contract, fixture.network)


def test_readable_after_clean_copy(tmp_path, contract) -> None:
    fixture = _checkpoint_fixture()
    path, _history, _rng = _publish(tmp_path, fixture, contract, "copy")
    clone = tmp_path / "clone"
    shutil.copytree(path, clone)
    state, _, _, _ = load_material_checkpoint(clone, fixture.spec, contract, fixture.network)
    assert state.completed_ticks == TICKS


# ---------------------------------------------------------------------------
# Real runner pause -> resume
# ---------------------------------------------------------------------------


def _runner_repo(tmp_path: Path):
    root = tmp_path / "repo"
    (root / "config" / "scenarios").mkdir(parents=True)
    (root / "data" / "manifests").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "config" / "research_contract.json", root / "config")
    shutil.copy(REPO_ROOT / "BASELINE.md", root / "BASELINE.md")
    shutil.copy(REPO_ROOT / "uv.lock", root / "uv.lock")
    shutil.copy(
        REPO_ROOT / "config" / "scenarios" / "intermediate8.json",
        root / "config" / "scenarios",
    )
    for name in ("sources.yml", "variables.yml", "artifacts.yml"):
        shutil.copy(REPO_ROOT / "data" / "manifests" / name, root / "data" / "manifests" / name)
    build_synthetic_material_fixtures(root)
    spec = load_scenario(root, "intermediate8")
    spec = spec.model_copy(
        update={
            "households": 1000,
            "organizations": 100,
            "organization_recipe": spec.organization_recipe.model_copy(
                update={"profile": "p02_100"}
            ),
        }
    )
    registry = DataRegistry.load(root, allowed_commodities=list(spec.commodities))
    return root, spec, registry


def test_run_material_pause_then_resume_matches_uninterrupted(tmp_path, contract) -> None:
    root, spec, registry = _runner_repo(tmp_path)

    full = run_material(spec, root / "full", contract, registry, until="1957Q4")
    assert full.status == "paused"
    assert full.completed_ticks == 4

    paused = run_material(
        spec, root / "pause", contract, registry, until="1957Q1", checkpoint_every=1
    )
    assert paused.status == "paused"
    assert paused.completed_ticks == 1
    checkpoint = checkpoint_dir(root / "pause", 1)
    assert checkpoint.is_dir()

    resumed = run_material(
        spec, root / "resume", contract, registry, until="1957Q4", resume_from=checkpoint
    )
    assert resumed.status == "paused"
    assert resumed.completed_ticks == 4
    assert resumed.deterministic_replay_digest == full.deterministic_replay_digest
    assert resumed.parent_run_id == paused.run_id


def test_resume_refuses_a_terminal_checkpoint(tmp_path, contract) -> None:
    root, spec, registry = _runner_repo(tmp_path)
    # a checkpoint at the scenario horizon already ends it: the zero-tick
    # replay is refused before any output is created
    full = run_material(
        spec, root / "full", contract, registry, checkpoint_every=spec.ticks
    )
    assert full.status == "completed"
    assert full.completed_ticks == spec.ticks
    terminal = checkpoint_dir(root / "full", spec.ticks)
    assert terminal.is_dir()
    with pytest.raises(ConfigError, match="ends the scenario"):
        run_material(spec, root / "replay", contract, registry, resume_from=terminal)
    assert not (root / "replay").exists()
