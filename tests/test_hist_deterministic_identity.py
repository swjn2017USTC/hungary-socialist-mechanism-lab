"""Deterministic identity: content-addressed run id, fixed clock, byte-stable tree."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.material import _parse_fixed_clock, run_material
from hsm_lab.provenance.manifest import content_addressed_run_id

REPO_ROOT = Path(__file__).resolve().parents[1]


def _payload(**overrides):
    base = {
        "scheme": "material-deterministic-identity-v1",
        "run_kind": "material_household_simulation",
        "engine_version": "material-engine-v4",
        "scenario_hash": "a" * 64,
        "parameter_hash": "b" * 64,
        "initial_recipe_hash": "c" * 64,
        "input_artifact_hashes": {"x": "d" * 64},
        "baseline_hash": "e" * 64,
        "lock_hash": "f" * 64,
        "seed": 1729,
        "households": 5000,
        "enterprises": None,
        "organizations": 400,
        "ticks": 116,
        "commodity_ids": ["g01", "g02"],
        "region_ids": ["r1"],
        "output_policy": "ensemble_compact",
        "parent_run_id": None,
        "resume_completed_ticks": 0,
    }
    base.update(overrides)
    return base


def test_content_addressed_run_id_is_stable_and_sensitive() -> None:
    first = content_addressed_run_id(_payload())
    assert first == content_addressed_run_id(_payload())
    assert len(first) == 32
    assert first != content_addressed_run_id(_payload(seed=1730))
    assert first != content_addressed_run_id(_payload(scenario_hash="0" * 64))
    assert first != content_addressed_run_id(_payload(resume_completed_ticks=4))


def test_fixed_clock_default_and_validation() -> None:
    assert _parse_fixed_clock(None) == datetime(1970, 1, 1, tzinfo=UTC)
    assert _parse_fixed_clock("2020-01-01T00:00:00Z") == datetime(2020, 1, 1, tzinfo=UTC)
    with pytest.raises(ConfigError, match="timezone"):
        _parse_fixed_clock("2020-01-01T00:00:00")
    with pytest.raises(ConfigError, match="ISO-8601"):
        _parse_fixed_clock("not-a-date")


def test_fixed_clock_requires_deterministic_identity(tmp_path: Path) -> None:
    contract = load_research_contract(REPO_ROOT)
    spec = load_scenario(REPO_ROOT, "historical_f2_replay")
    registry = DataRegistry.load(REPO_ROOT, allowed_commodities=list(spec.commodities))
    target = tmp_path / "run"
    with pytest.raises(ConfigError, match="requires --deterministic-identity"):
        run_material(
            spec,
            target,
            contract,
            registry,
            until="1957Q2",
            fixed_clock="2020-01-01T00:00:00Z",
        )
    assert not target.exists()


def test_cli_rejects_deterministic_identity_for_smoke(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from hsm_lab.cli.app import app

    result = CliRunner().invoke(
        app,
        [
            "run",
            "--scenario",
            "smoke",
            "--deterministic-identity",
            "--output-dir",
            str(tmp_path / "smoke"),
        ],
    )
    assert result.exit_code != 0
    assert "--deterministic-identity" in result.output
    assert not (tmp_path / "smoke").exists()


def test_run_id_binds_boundary_and_clock(tmp_path: Path) -> None:
    contract = load_research_contract(REPO_ROOT)
    spec = load_scenario(REPO_ROOT, "historical_f2_replay")
    registry = DataRegistry.load(REPO_ROOT, allowed_commodities=list(spec.commodities))

    def run(name: str, *, clock: str = "2020-01-01T00:00:00Z", **kwargs):
        return run_material(
            spec,
            tmp_path / name,
            contract,
            registry,
            deterministic_identity=True,
            fixed_clock=clock,
            **kwargs,
        )

    one = run("one", until="1957Q1")
    two = run("two", until="1957Q2")
    shifted = run("shifted", until="1957Q1", clock="2021-01-01T00:00:00Z")
    checkpointed = run("checkpointed", until="1957Q1", checkpoint_every=1)

    assert len({one.run_id, two.run_id, shifted.run_id, checkpointed.run_id}) == 4


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_two_deterministic_runs_are_byte_identical(tmp_path: Path) -> None:
    contract = load_research_contract(REPO_ROOT)
    spec = load_scenario(REPO_ROOT, "historical_f2_replay")
    registry = DataRegistry.load(REPO_ROOT, allowed_commodities=list(spec.commodities))

    left = run_material(
        spec,
        tmp_path / "left",
        contract,
        registry,
        until="1957Q2",
        deterministic_identity=True,
        fixed_clock="2020-01-01T00:00:00Z",
    )
    right = run_material(
        spec,
        tmp_path / "right",
        contract,
        registry,
        until="1957Q2",
        deterministic_identity=True,
        fixed_clock="2020-01-01T00:00:00Z",
    )

    assert left.run_id == right.run_id
    assert left.started_at == right.started_at == datetime(2020, 1, 1, tzinfo=UTC)
    assert left.finished_at == right.finished_at == datetime(2020, 1, 1, tzinfo=UTC)

    left_dir = tmp_path / "left"
    right_dir = tmp_path / "right"
    assert (left_dir / "trajectory_tables").is_dir()
    assert not (left_dir / "trajectory.duckdb").exists()
    assert _tree_bytes(left_dir) == _tree_bytes(right_dir)

    # The default path is untouched: a legacy run still writes DuckDB.
    legacy = run_material(spec, tmp_path / "legacy", contract, registry, until="1957Q2")
    assert (tmp_path / "legacy" / "trajectory.duckdb").is_file()
    assert legacy.run_id != left.run_id
