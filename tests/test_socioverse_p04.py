"""P04 SocioVerse2 orchestration tests: the real longitudinal simulator loop."""

from __future__ import annotations

import json

import polars as pl
import pytest

from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.contract.politics import InterventionSpec, PoliticalMode
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.political_run import open_political_session, run_political
from hsm_lab.storage.fork import load_counterfactual_origin
from tests.conftest import REPO_ROOT

socioverse = pytest.importorskip("socioverse")


@pytest.fixture(scope="module")
def contract():
    return load_research_contract(REPO_ROOT)


@pytest.fixture(scope="module")
def registry():
    return DataRegistry.load(REPO_ROOT)


def _broadcast(region_id: str) -> InterventionSpec:
    return InterventionSpec.model_validate(
        {
            "intervention_id": "sv-broadcast",
            "effective_quarter": "1958Q1",
            "operation": "broadcast",
            "target": "information.broadcast",
            "value": {
                "content": "cf",
                "channel": "western_comparison",
                "intensity": 0.2,
                "content_sensitivity": 0.5,
                "audience": {"all": None, "region_id_in": [region_id]},
                "ttl": 2,
            },
            "provenance": "test",
        }
    )


def _fork_session(spec, contract, registry, tmp_path, region_id: str = "pest"):
    origin_dir = tmp_path / "origin"
    run_political(spec, origin_dir, contract, registry, until="1957Q4", checkpoint_every=4)
    checkpoint = origin_dir / "checkpoints" / "tick-0004"
    child = spec.model_copy(
        update={"politics": spec.politics.model_copy(update={"mode": PoliticalMode.COUNTERFACTUAL})}
    )
    origin = load_counterfactual_origin(
        checkpoint, child, contract, interventions=[_broadcast(region_id)]
    )
    session = open_political_session(
        child, tmp_path / "child", contract, registry, until="1958Q2", fork_from=origin
    )
    return session


def test_institutional_population_is_26_persistent_ids(contract, registry) -> None:
    from hsm_lab.integrations.socioverse import InstitutionalPopulation

    spec = load_scenario(REPO_ROOT, "p04_endogenous")
    population = InstitutionalPopulation("study", list(spec.region_ids))
    personas = population.build(seed=1)
    ids = [persona.agent_id for persona in personas]
    assert len(ids) == 26
    assert len(set(ids)) == 26
    assert "leadership:broker" in ids
    assert "state:planner" in ids
    assert {
        f"coalition:{name}"
        for name in __import__(
            "hsm_lab.contract.politics", fromlist=["COALITION_IDS"]
        ).COALITION_IDS
    } <= set(ids)
    assert sum(1 for value in ids if value.startswith("region:")) == 20


def test_real_longitudinal_loop_drives_the_native_session(tmp_path, contract, registry) -> None:
    from hsm_lab.integrations.socioverse import run_political_socioverse

    spec = load_scenario(REPO_ROOT, "p04_endogenous")
    manifest = run_political_socioverse(
        spec, tmp_path / "run", contract, registry, until="1957Q3", checkpoint_every=2
    )
    assert manifest.status == "paused"
    assert manifest.completed_ticks == 3
    assert manifest.political_mode is PoliticalMode.ENDOGENOUS_POLITICS

    panel = pl.read_parquet(tmp_path / "run" / "socioverse" / "panel.parquet")
    assert panel.height == 26 * 4  # t=0 boundary + 3 steps
    assert sorted(panel["step"].unique().to_list()) == [0, 1, 2, 3]
    assert panel["agent_id"].n_unique() == 26

    broker = panel.filter(pl.col("agent_id") == "leadership:broker")
    assert set(broker["action_kind"].drop_nulls().to_list()) == {"policy_choice"}
    payload = json.loads(broker.filter(pl.col("step") == 1)["action_payload"][0])
    assert payload["source"] == "broker"
    assert payload["selected_policy"]
    # Every non-broker institutional actor stays action-free (no fabricated panels).
    others = panel.filter(pl.col("agent_id") != "leadership:broker")
    assert others["action_kind"].drop_nulls().len() == 0

    metrics = pl.read_parquet(tmp_path / "run" / "socioverse" / "metrics.parquet")
    assert metrics.height == 4
    quarters = pl.read_parquet(tmp_path / "run" / "political_quarters.parquet")
    assert quarters.height == 3
    joined = metrics.join(
        quarters.with_columns(pl.col("tick") + 1), left_on="step", right_on="tick"
    )
    assert joined.height == 3

    # DuckDB and Parquet carry the same panel content.
    import duckdb

    connection = duckdb.connect(
        str(tmp_path / "run" / "socioverse" / "study.duckdb"), read_only=True
    )
    try:
        db_rows = connection.execute("SELECT COUNT(*) FROM panel").fetchone()[0]
        db_steps = connection.execute("SELECT DISTINCT step FROM panel ORDER BY step").fetchall()
    finally:
        connection.close()
    assert db_rows == panel.height
    assert [row[0] for row in db_steps] == [0, 1, 2, 3]


def test_replay_mode_has_no_broker_action(tmp_path, contract, registry) -> None:
    from hsm_lab.integrations.socioverse import run_political_socioverse

    spec = load_scenario(REPO_ROOT, "p04_replay")
    manifest = run_political_socioverse(
        spec, tmp_path / "replay", contract, registry, until="1957Q2"
    )
    assert manifest.political_mode is PoliticalMode.HISTORICAL_REPLAY
    panel = pl.read_parquet(tmp_path / "replay" / "socioverse" / "panel.parquet")
    assert panel["action_kind"].drop_nulls().len() == 0
    quarters = pl.read_parquet(tmp_path / "replay" / "political_quarters.parquet")
    assert set(quarters["policy_source"].unique().to_list()) == {"replay"}


def test_broadcast_audience_routed_by_information_environment(tmp_path, contract, registry) -> None:
    from socioverse.env_layers.information import InformationEnvironment

    from hsm_lab.integrations.socioverse import (
        PoliticalEnvironment,
        _broadcast_program,
    )

    spec = load_scenario(REPO_ROOT, "p04_endogenous")
    session = _fork_session(spec, contract, registry, tmp_path, region_id="pest")
    environment = PoliticalEnvironment(
        session, InformationEnvironment(program=_broadcast_program(session))
    )
    environment.reset(seed=1)
    other_region = next(region for region in spec.region_ids if region != "pest")
    # local step 1 -> global step 5 == the broadcast's closing step.
    environment.advance_to(1)
    observations = {
        observation.agent_id: observation
        for observation in environment.observe_batch(["region:pest", f"region:{other_region}"], 1)
    }
    assert observations["region:pest"].local_information
    assert not observations[f"region:{other_region}"].local_information
    # The macro quadrant carries the lagged published view, never current truth.
    macro = observations["region:pest"].macro_physical
    assert "source_tick" in macro
    assert (
        len(macro)
        == len(
            __import__(
                "hsm_lab.contract.politics", fromlist=["POLITICAL_FEATURE_IDS"]
            ).POLITICAL_FEATURE_IDS
        )
        + 1
    )


def test_fork_offset_maps_local_steps_to_global(tmp_path, contract, registry) -> None:
    from hsm_lab.integrations.socioverse import run_political_socioverse

    spec = load_scenario(REPO_ROOT, "p04_endogenous")
    origin_dir = tmp_path / "origin"
    run_political(spec, origin_dir, contract, registry, until="1957Q4", checkpoint_every=4)
    child = spec.model_copy(
        update={"politics": spec.politics.model_copy(update={"mode": PoliticalMode.COUNTERFACTUAL})}
    )
    origin = load_counterfactual_origin(
        origin_dir / "checkpoints" / "tick-0004", child, contract, interventions=[]
    )
    manifest = run_political_socioverse(
        child, tmp_path / "fork", contract, registry, until="1958Q2", fork_from=origin
    )
    assert manifest.political_mode is PoliticalMode.COUNTERFACTUAL
    assert manifest.completed_ticks == 6
    panel = pl.read_parquet(tmp_path / "fork" / "socioverse" / "panel.parquet")
    # local steps 0..2 are mapped onto global steps 4..6 (the restored boundary).
    assert sorted(panel["step"].unique().to_list()) == [4, 5, 6]
    assert panel.height == 26 * 3


def test_orchestration_is_behaviourally_identical_to_the_native_runner(
    tmp_path, contract, registry
) -> None:
    """The framework must not change any causal result: same digest, same tables."""
    from hsm_lab.integrations.socioverse import run_political_socioverse

    spec = load_scenario(REPO_ROOT, "p04_endogenous")
    native = run_political(spec, tmp_path / "native", contract, registry, until="1957Q3")
    socioverse_run = run_political_socioverse(
        spec, tmp_path / "sv", contract, registry, until="1957Q3"
    )
    assert socioverse_run.deterministic_replay_digest == native.deterministic_replay_digest
    for table in ("political_quarters", "opposition_regions", "information_quarters"):
        assert pl.read_parquet(tmp_path / "native" / f"{table}.parquet").equals(
            pl.read_parquet(tmp_path / "sv" / f"{table}.parquet")
        )
