"""P04 end-to-end runner tests: mode A/B/C, resume, no-op fork equivalence."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.contract.politics import PoliticalMode
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.political_run import run_political
from hsm_lab.storage.fork import load_counterfactual_origin
from tests.conftest import REPO_ROOT


@pytest.fixture(scope="module")
def contract():
    return load_research_contract(REPO_ROOT)


@pytest.fixture(scope="module")
def registry():
    return DataRegistry.load(REPO_ROOT)


def _run(spec, output_dir: Path, contract, registry, **kwargs):
    return run_political(spec, output_dir, contract, registry, **kwargs)


def test_mode_a_replay_policy_source(tmp_path: Path, contract, registry) -> None:
    spec = load_scenario(REPO_ROOT, "p04_replay")
    manifest = _run(spec, tmp_path / "a", contract, registry, until="1957Q2")
    quarters = pl.read_parquet(tmp_path / "a" / "political_quarters.parquet")
    assert set(quarters["policy_source"].unique().to_list()) == {"replay"}
    assert set(quarters["mode"].unique().to_list()) == {"historical_replay"}
    assert quarters["policy_enterprise_autonomy"].to_list() == [0.1, 0.1]
    assert manifest.political_mode == PoliticalMode.HISTORICAL_REPLAY


def test_mode_b_broker_decisions_recorded(tmp_path: Path, contract, registry) -> None:
    spec = load_scenario(REPO_ROOT, "p04_endogenous")
    _run(spec, tmp_path / "b", contract, registry, until="1957Q3")
    quarters = pl.read_parquet(tmp_path / "b" / "political_quarters.parquet")
    assert set(quarters["policy_source"].unique().to_list()) == {"broker"}
    decisions = pl.read_parquet(tmp_path / "b" / "policy_decisions.parquet")
    assert decisions.height > 0
    first_tick = decisions.filter(pl.col("tick") == 0)
    assert first_tick.height >= 2
    assert "previous" in first_tick["candidate_id"].to_list()


def test_noop_fork_matches_plain_continuation(tmp_path: Path, contract, registry) -> None:
    spec = load_scenario(REPO_ROOT, "p04_replay")
    _run(spec, tmp_path / "origin", contract, registry, until="1957Q4", checkpoint_every=4)
    checkpoint = tmp_path / "origin" / "checkpoints" / "tick-0004"

    resumed = _run(
        spec,
        tmp_path / "resumed",
        contract,
        registry,
        until="1958Q2",
        resume_from=checkpoint,
    )
    child = spec.model_copy(
        update={"politics": spec.politics.model_copy(update={"mode": PoliticalMode.COUNTERFACTUAL})}
    )
    origin = load_counterfactual_origin(checkpoint, child, contract, interventions=[])
    forked = _run(child, tmp_path / "forked", contract, registry, until="1958Q2", fork_from=origin)
    assert forked.deterministic_replay_digest == resumed.deterministic_replay_digest
    # A resumed/forked run writes only its own suffix rows.
    assert pl.read_parquet(tmp_path / "forked" / "political_quarters.parquet").height == 2


def test_fork_refuses_pre_boundary_intervention(tmp_path: Path, contract, registry) -> None:
    from hsm_lab.contract.politics import InterventionSpec

    spec = load_scenario(REPO_ROOT, "p04_replay")
    _run(spec, tmp_path / "origin2", contract, registry, until="1957Q4", checkpoint_every=4)
    checkpoint = tmp_path / "origin2" / "checkpoints" / "tick-0004"
    child = spec.model_copy(
        update={"politics": spec.politics.model_copy(update={"mode": PoliticalMode.COUNTERFACTUAL})}
    )
    early = InterventionSpec.model_validate(
        {
            "intervention_id": "early",
            "effective_quarter": "1957Q1",
            "operation": "set",
            "target": "policy.enterprise_autonomy",
            "value": 0.2,
            "provenance": "test",
        }
    )
    with pytest.raises(Exception, match="before the fork boundary"):
        load_counterfactual_origin(checkpoint, child, contract, interventions=[early])


def test_counterfactual_intervention_changes_policy(tmp_path: Path, contract, registry) -> None:
    from hsm_lab.contract.politics import InterventionSpec

    spec = load_scenario(REPO_ROOT, "p04_endogenous")
    _run(spec, tmp_path / "origin3", contract, registry, until="1957Q4", checkpoint_every=4)
    checkpoint = tmp_path / "origin3" / "checkpoints" / "tick-0004"
    child = spec.model_copy(
        update={"politics": spec.politics.model_copy(update={"mode": PoliticalMode.COUNTERFACTUAL})}
    )
    intervention = InterventionSpec.model_validate(
        {
            "intervention_id": "no-reform",
            "effective_quarter": "1958Q1",
            "until_quarter": None,
            "operation": "set",
            "target": "policy.enterprise_autonomy",
            "value": 0.05,
            "provenance": "test",
        }
    )
    origin = load_counterfactual_origin(checkpoint, child, contract, interventions=[intervention])
    _run(child, tmp_path / "cf", contract, registry, until="1958Q2", fork_from=origin)
    quarters = pl.read_parquet(tmp_path / "cf" / "political_quarters.parquet")
    assert quarters.height == 2  # suffix only (ticks 4 and 5)
    assert quarters["policy_enterprise_autonomy"].to_list() == [0.05, 0.05]
