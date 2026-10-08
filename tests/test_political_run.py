"""P04 end-to-end runner tests: mode A/B/C, resume, no-op fork equivalence."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
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
    # Forked/resumed outputs carry the shared prefix plus their own suffix.
    forked_quarters = pl.read_parquet(tmp_path / "forked" / "political_quarters.parquet")
    assert forked_quarters.height == 6
    assert sorted(forked_quarters["tick"].to_list()) == [0, 1, 2, 3, 4, 5]


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
    suffix = quarters.filter(pl.col("tick") >= 4)
    assert suffix["policy_enterprise_autonomy"].to_list() == [0.05, 0.05]
    # The prefix is the shared parent trajectory, byte-identical to the origin run.
    origin = pl.read_parquet(tmp_path / "origin3" / "political_quarters.parquet")
    prefix = quarters.filter(pl.col("tick") < 4).select(
        ["tick", "policy_enterprise_autonomy", "weight_reform_technocratic"]
    )
    shared = origin.select(
        ["tick", "policy_enterprise_autonomy", "weight_reform_technocratic"]
    ).filter(pl.col("tick") < 4)
    assert prefix.equals(shared)


def _intervention(target: str, value, quarter: str, operation: str = "set"):
    from hsm_lab.contract.politics import InterventionSpec

    return InterventionSpec.model_validate(
        {
            "intervention_id": f"test-{target.replace('.', '-')}",
            "effective_quarter": quarter,
            "operation": operation,
            "target": target,
            "value": value,
            "provenance": "test",
        }
    )


def _fork_child(spec, checkpoint, contract, interventions, output_dir, **kwargs):
    child = spec.model_copy(
        update={"politics": spec.politics.model_copy(update={"mode": PoliticalMode.COUNTERFACTUAL})}
    )
    origin = load_counterfactual_origin(checkpoint, child, contract, interventions=interventions)
    manifest = _run(child, output_dir, contract, kwargs.pop("registry"), fork_from=origin, **kwargs)
    return child, manifest


def test_soviet_multiplier_intervention_changes_behaviour(tmp_path, contract, registry) -> None:
    """A declared Soviet-constraint multiplier must actually bind the broker."""
    spec = load_scenario(REPO_ROOT, "p04_endogenous")
    _run(spec, tmp_path / "origin", contract, registry, until="1957Q4", checkpoint_every=4)
    checkpoint = tmp_path / "origin" / "checkpoints" / "tick-0004"

    _, plain = _fork_child(
        spec, checkpoint, contract, [], tmp_path / "plain", registry=registry, until="1958Q1"
    )
    _, tightened = _fork_child(
        spec,
        checkpoint,
        contract,
        [_intervention("soviet_constraint_multiplier", 2.0, "1958Q1")],
        tmp_path / "tight",
        registry=registry,
        until="1958Q1",
    )
    assert plain.deterministic_replay_digest != tightened.deterministic_replay_digest
    tight_policy = pl.read_parquet(tmp_path / "tight" / "political_quarters.parquet").filter(
        pl.col("quarter") == "1958Q1"
    )
    plain_policy = pl.read_parquet(tmp_path / "plain" / "political_quarters.parquet").filter(
        pl.col("quarter") == "1958Q1"
    )
    assert (
        tight_policy["policy_enterprise_autonomy"][0]
        < plain_policy["policy_enterprise_autonomy"][0]
    )


def test_chained_fork_inherits_root_base_and_interventions(tmp_path, contract, registry) -> None:
    spec = load_scenario(REPO_ROOT, "p04_endogenous")
    _run(spec, tmp_path / "origin", contract, registry, until="1957Q4", checkpoint_every=4)
    broadcast = _intervention(
        "information.broadcast",
        {
            "content": "cf",
            "channel": "western_comparison",
            "intensity": 0.2,
            "content_sensitivity": 0.5,
            "audience": {"all": None, "region_id_in": ["pest"]},
            "ttl": 3,
        },
        "1958Q1",
        operation="broadcast",
    )
    child, _ = _fork_child(
        spec,
        tmp_path / "origin" / "checkpoints" / "tick-0004",
        contract,
        [broadcast],
        tmp_path / "child",
        registry=registry,
        until="1958Q2",
        checkpoint_every=2,
    )
    child_checkpoint = tmp_path / "child" / "checkpoints" / "tick-0006"
    # A branch of a branch must load (the embedded scenario declares counterfactual).
    from hsm_lab.storage.fork import resolve_root_base_mode

    payload = json.loads((child_checkpoint / "metadata.json").read_text())
    assert resolve_root_base_mode(payload) is PoliticalMode.ENDOGENOUS_POLITICS
    grandchild, _ = _fork_child(
        spec,
        child_checkpoint,
        contract,
        [_intervention("soviet_constraint_multiplier", 2.0, "1958Q3")],
        tmp_path / "grandchild",
        registry=registry,
        until="1958Q4",
    )
    grand_metadata = json.loads(
        ((tmp_path / "grandchild") / "checkpoints" / "tick-0008" / "metadata.json").read_text()
    )
    branch = grand_metadata["branch"]
    assert branch["base_mode"] == "endogenous_politics"
    assert [item["intervention_id"] for item in branch["inherited_interventions"]] == [
        "test-information-broadcast"
    ]
    assert [item["intervention_id"] for item in branch["interventions"]] == [
        "test-soviet_constraint_multiplier"
    ]
    # The branch ledger axis is rebuilt for the child's own schedule.
    arrays = np.load((tmp_path / "child") / "checkpoints" / "tick-0006" / "political.npz")
    assert arrays["intervention_ttl"].shape == (1,)


def test_resume_counterfactual_child_keeps_inherited_interventions(
    tmp_path, contract, registry
) -> None:
    spec = load_scenario(REPO_ROOT, "p04_endogenous")
    _run(spec, tmp_path / "origin", contract, registry, until="1957Q4", checkpoint_every=4)
    broadcast = _intervention(
        "information.broadcast",
        {
            "content": "cf",
            "channel": "western_comparison",
            "intensity": 0.2,
            "content_sensitivity": 0.5,
            "audience": {"all": None, "region_id_in": ["pest"]},
            "ttl": 3,
        },
        "1958Q1",
        operation="broadcast",
    )
    _fork_child(
        spec,
        tmp_path / "origin" / "checkpoints" / "tick-0004",
        contract,
        [broadcast],
        tmp_path / "child",
        registry=registry,
        until="1958Q2",
        checkpoint_every=2,
    )
    manifest = _run(
        spec,
        tmp_path / "resumed",
        contract,
        registry,
        until="1958Q4",
        resume_from=tmp_path / "child" / "checkpoints" / "tick-0006",
    )
    assert manifest.political_mode is PoliticalMode.COUNTERFACTUAL
    events = pl.read_parquet(tmp_path / "resumed" / "political_events.parquet")
    inherited = events.filter(pl.col("message_id") == "cf:test-information-broadcast")
    assert inherited.height > 0
    assert set(inherited["recipient_id"].to_list()) == {"pest"}


def test_decision_and_coalition_contributions_rebuild_from_output(
    tmp_path, contract, registry
) -> None:
    spec = load_scenario(REPO_ROOT, "p04_endogenous")
    _run(spec, tmp_path / "run", contract, registry, until="1957Q3")
    decisions = pl.read_parquet(tmp_path / "run" / "policy_decisions.parquet")
    assert decisions.height > 0
    for row in decisions.iter_rows(named=True):
        terms = json.loads(row["contributions_json"])
        assert abs(sum(terms.values()) - row["utility"]) < 1e-9
    quarters = pl.read_parquet(tmp_path / "run" / "political_quarters.parquet")
    contributions = np.array(json.loads(quarters["coalition_contributions_json"][0]))
    # W coalitions x (F features + intercept) -> the row sum rebuilds the score.
    assert contributions.shape == (4, 11)
    assert np.all(np.isfinite(contributions))
