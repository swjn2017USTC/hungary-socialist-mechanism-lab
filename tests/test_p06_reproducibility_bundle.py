from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

from hsm_lab.calibration.reproducibility_bundle import (
    assemble_reproducibility_bundle,
    verify_reproducibility_bundle,
)
from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.contract.schemas import ResearchGateError, ScenarioSpec
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.material import run_material

ROOT = Path(__file__).resolve().parents[1]


def _one_tick_run(destination: Path):
    spec = load_scenario(ROOT, "intermediate8")
    spec = ScenarioSpec.model_validate(spec.model_copy(update={"ticks": 1}).model_dump())
    return run_material(
        spec,
        destination,
        load_research_contract(ROOT),
        DataRegistry.load(ROOT, allowed_commodities=spec.commodities),
    )


def test_bundle_replays_a_recorded_run_digest_from_scratch(tmp_path: Path) -> None:
    run_id = uuid.uuid4().hex
    run_dir = tmp_path / f"source-{run_id}"
    replay_dir = tmp_path / f"replay-{run_id}"
    try:
        _one_tick_run(run_dir)
        bundle = tmp_path / "bundle"
        record = assemble_reproducibility_bundle(ROOT, run_dir, bundle)
        assert record["no_manual_steps"]["passed"] is True
        assert record["holdout_values_read"] is False
        assert record["reserved_values_read"] is False

        verification = verify_reproducibility_bundle(ROOT, bundle, replay_dir)
        assert verification["status"] == "verified"
        assert verification["digest_matches"] is True
        assert verification["parameter_hash_matches"] is True
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
        shutil.rmtree(replay_dir, ignore_errors=True)


def test_bundle_refuses_changed_captured_inputs(tmp_path: Path) -> None:
    run_id = uuid.uuid4().hex
    run_dir = tmp_path / f"tamper-{run_id}"
    try:
        _one_tick_run(run_dir)
        bundle = tmp_path / "bundle"
        assemble_reproducibility_bundle(ROOT, run_dir, bundle)
        scenario = next((bundle / "config/scenarios").glob("*.json"))
        scenario.write_text(scenario.read_text(encoding="utf-8") + " ", encoding="utf-8")

        with pytest.raises(ResearchGateError, match="captured file missing or changed"):
            verify_reproducibility_bundle(ROOT, bundle, tmp_path / "replay")
    finally:
        pass
