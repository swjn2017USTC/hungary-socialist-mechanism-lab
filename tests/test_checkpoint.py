"""P01 regression: checkpoint save/resume equivalence and refusal gates."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.contract.schemas import ConfigError, ResearchGateError, ScenarioSpec
from tests.conftest import REPO_ROOT, load_json

TABLES = (
    "aggregates",
    "national_accounts",
    "household_budgets",
    "tick_diagnostics",
    "events",
)


@pytest.fixture()
def contract():
    return load_research_contract(REPO_ROOT)


@pytest.fixture()
def spec(contract):
    return load_scenario(REPO_ROOT, "toy4")


@pytest.fixture()
def registry(spec):
    from hsm_lab.data.registry import DataRegistry

    return DataRegistry.load(REPO_ROOT, allowed_commodities=spec.commodities)


def run_toy4(tmp_path: Path, contract, registry, name: str, **kwargs):
    from hsm_lab.engine.toy4 import run_toy4

    spec = load_scenario(REPO_ROOT, "toy4")
    if "overrides" in kwargs:
        spec = ScenarioSpec.model_validate(
            spec.model_copy(update=kwargs.pop("overrides")).model_dump()
        )
    return run_toy4(spec, tmp_path / name, contract, registry, **kwargs)


def paused_run(tmp_path: Path, contract, registry, name: str, boundary: int, **kwargs):
    until = str(spec_start().advance(boundary - 1))
    return run_toy4(tmp_path, contract, registry, name, until=until, **kwargs)


def spec_start():
    return load_scenario(REPO_ROOT, "toy4").start


def final_state_arrays(run_dir: Path, boundary: int) -> dict:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    ckpt = checkpoint_dir(run_dir, boundary)
    payload = np.load(ckpt / "state.npz", allow_pickle=False)
    return {name: payload[name] for name in payload.files}


def assert_runs_equivalent(full_dir: Path, resumed_dir: Path, full_boundary: int) -> None:
    full_summary = load_json(full_dir / "summary.json")
    resumed_summary = load_json(resumed_dir / "summary.json")
    assert full_summary["deterministic_replay_digest"] == (
        resumed_summary["deterministic_replay_digest"]
    )
    assert resumed_summary["completed_ticks"] == full_boundary
    for table in TABLES:
        assert pl.read_parquet(full_dir / f"{table}.parquet").equals(
            pl.read_parquet(resumed_dir / f"{table}.parquet")
        ), table
    assert full_summary["household_budget"] == resumed_summary["household_budget"]


@pytest.mark.parametrize("boundary", [1, 40, 115])
def test_checkpoint_resume_matches_uninterrupted(
    tmp_path, contract, registry, boundary
) -> None:
    run_toy4(tmp_path, contract, registry, f"full-{boundary}")
    paused = paused_run(
        tmp_path, contract, registry, f"paused-{boundary}", boundary
    )
    assert paused.status == "paused"
    from hsm_lab.storage.checkpoint import checkpoint_dir

    ckpt = checkpoint_dir(tmp_path / f"paused-{boundary}", boundary)
    resumed = run_toy4(
        tmp_path,
        contract,
        registry,
        f"resumed-{boundary}",
        resume_from=ckpt,
    )
    assert resumed.status == "completed"
    assert resumed.completed_ticks == 116
    assert_runs_equivalent(tmp_path / f"full-{boundary}", tmp_path / f"resumed-{boundary}", 116)


def test_terminal_checkpoint_state_and_rng_match_uninterrupted(
    tmp_path, contract, registry
) -> None:
    """Both the reference and the resumed run save a terminal checkpoint; the
    final state arrays, RNG snapshot and digest chain must be identical."""
    from hsm_lab.storage.checkpoint import (
        checkpoint_dir,
    )

    reference = run_toy4(
        tmp_path, contract, registry, "ref-term", checkpoint_every=116
    )
    paused_run(tmp_path, contract, registry, "p-term", 58)
    resumed = run_toy4(
        tmp_path,
        contract,
        registry,
        "r-term",
        resume_from=checkpoint_dir(tmp_path / "p-term", 58),
        checkpoint_every=116,
    )
    assert reference.completed_ticks == resumed.completed_ticks == 116
    ref_state = np.load(
        checkpoint_dir(tmp_path / "ref-term", 116) / "state.npz", allow_pickle=False
    )
    res_state = np.load(
        checkpoint_dir(tmp_path / "r-term", 116) / "state.npz", allow_pickle=False
    )
    assert sorted(ref_state.files) == sorted(res_state.files)
    for name in ref_state.files:
        np.testing.assert_array_equal(ref_state[name], res_state[name])
    ref_meta = json.loads(
        (checkpoint_dir(tmp_path / "ref-term", 116) / "metadata.json").read_text()
    )
    res_meta = json.loads(
        (checkpoint_dir(tmp_path / "r-term", 116) / "metadata.json").read_text()
    )
    assert ref_meta["rng_snapshot"] == res_meta["rng_snapshot"]
    assert ref_meta["digest_chain"] == res_meta["digest_chain"]
    # The restored RNG continues identically from both terminal snapshots.
    from hsm_lab.engine.rng import RngRegistry

    left = RngRegistry.from_snapshot(ref_meta["rng_snapshot"])
    right = RngRegistry.from_snapshot(res_meta["rng_snapshot"])
    np.testing.assert_array_equal(
        left.uniform("suffix", 8), right.uniform("suffix", 8)
    )


def _tamper_metadata(ckpt: Path, **updates) -> None:
    path = ckpt / "metadata.json"
    payload = json.loads(path.read_text())
    payload.update(updates)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _rewrite_state_and_rehash(ckpt: Path, mutate) -> None:
    """Rewrite state.npz through mutate(dict) and update its payload hash."""
    from hsm_lab.contract.guards import sha256_file

    state_path = ckpt / "state.npz"
    arrays = dict(np.load(state_path, allow_pickle=False))
    mutate(arrays)
    np.savez(state_path, **arrays)
    metadata_path = ckpt / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["payload_sha256"]["state.npz"] = sha256_file(state_path)
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("region_ids", ["bogus_region"] * 20, "region axes"),
        ("commodity_ids", ["a", "b", "c", "d"], "commodity axes"),
        ("next_quarter", "1900Q1", "next_quarter"),
        ("last_completed_quarter", "1900Q1", "last_completed_quarter"),
    ],
)
def test_tampered_checkpoint_metadata_refused(
    tmp_path, contract, registry, field, value, match
) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, f"tm-{field}", 10)
    ckpt = checkpoint_dir(tmp_path / f"tm-{field}", 10)
    _tamper_metadata(ckpt, **{field: value})
    with pytest.raises(ResearchGateError, match=match):
        run_toy4(tmp_path, contract, registry, f"rm-{field}", resume_from=ckpt)
    assert not (tmp_path / f"rm-{field}").exists()


def test_tampered_checkpoint_rng_seed_refused(tmp_path, contract, registry) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "rs", 10)
    ckpt = checkpoint_dir(tmp_path / "rs", 10)
    metadata = json.loads((ckpt / "metadata.json").read_text())
    snapshot = metadata["rng_snapshot"]
    snapshot["seed"] = snapshot["seed"] + 1
    _tamper_metadata(ckpt, rng_snapshot=snapshot)
    with pytest.raises(ResearchGateError, match="RNG seed"):
        run_toy4(tmp_path, contract, registry, "rs-out", resume_from=ckpt)
    assert not (tmp_path / "rs-out").exists()


def test_checkpoint_non_integer_region_axis_refused(tmp_path, contract, registry) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "fz", 10)
    ckpt = checkpoint_dir(tmp_path / "fz", 10)

    def to_float(arrays):
        arrays["household_region"] = arrays["household_region"].astype(np.float64) + 0.5

    _rewrite_state_and_rehash(ckpt, to_float)
    with pytest.raises(ResearchGateError, match="dtype"):
        run_toy4(tmp_path, contract, registry, "fz-out", resume_from=ckpt)
    assert not (tmp_path / "fz-out").exists()


def test_checkpoint_nan_capacity_refused(tmp_path, contract, registry) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "nc", 10)
    ckpt = checkpoint_dir(tmp_path / "nc", 10)

    def poison(arrays):
        arrays["organization_capacity"] = arrays["organization_capacity"].copy()
        arrays["organization_capacity"][0] = float("nan")

    _rewrite_state_and_rehash(ckpt, poison)
    with pytest.raises(ResearchGateError, match="not finite"):
        run_toy4(tmp_path, contract, registry, "nc-out", resume_from=ckpt)
    assert not (tmp_path / "nc-out").exists()


def test_checkpoint_duplicate_history_key_refused(tmp_path, contract, registry) -> None:
    from hsm_lab.contract.guards import sha256_file
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "dh", 10)
    ckpt = checkpoint_dir(tmp_path / "dh", 10)
    aggregates_path = ckpt / "aggregates.parquet"
    frame = pl.read_parquet(aggregates_path)
    rows = frame.to_dicts()
    rows[1] = dict(rows[0])  # duplicate the first key, keeping row count
    pl.DataFrame(rows, schema=frame.schema).write_parquet(aggregates_path)
    metadata_path = ckpt / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["payload_sha256"]["aggregates.parquet"] = sha256_file(aggregates_path)
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    with pytest.raises(ResearchGateError, match="duplicate keys"):
        run_toy4(tmp_path, contract, registry, "dh-out", resume_from=ckpt)
    assert not (tmp_path / "dh-out").exists()


def _rewrite_table_and_rehash(ckpt: Path, table: str, mutate) -> None:
    from hsm_lab.contract.guards import sha256_file

    path = ckpt / f"{table}.parquet"
    frame = pl.read_parquet(path)
    mutate(frame, path)
    metadata_path = ckpt / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["payload_sha256"][f"{table}.parquet"] = sha256_file(path)
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")


def test_checkpoint_history_unknown_budget_region_refused(tmp_path, contract, registry) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "hb", 10)
    ckpt = checkpoint_dir(tmp_path / "hb", 10)

    def mutate(frame, path):
        victim = frame["region_id"][0]
        frame = frame.with_columns(
            pl.when((pl.col("tick") == 0) & (pl.col("region_id") == victim))
            .then(pl.lit("bogus_region"))
            .otherwise(pl.col("region_id"))
            .alias("region_id")
        )
        frame.write_parquet(path)

    _rewrite_table_and_rehash(ckpt, "household_budgets", mutate)
    with pytest.raises(ResearchGateError, match="unknown"):
        run_toy4(tmp_path, contract, registry, "hb-out", resume_from=ckpt)
    assert not (tmp_path / "hb-out").exists()


def test_checkpoint_history_unknown_national_commodity_refused(
    tmp_path, contract, registry
) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "hn", 10)
    ckpt = checkpoint_dir(tmp_path / "hn", 10)

    def mutate(frame, path):
        victim = frame["commodity_id"][0]
        frame = frame.with_columns(
            pl.when((pl.col("tick") == 0) & (pl.col("commodity_id") == victim))
            .then(pl.lit("bogus_commodity"))
            .otherwise(pl.col("commodity_id"))
            .alias("commodity_id")
        )
        frame.write_parquet(path)

    _rewrite_table_and_rehash(ckpt, "national_accounts", mutate)
    with pytest.raises(ResearchGateError, match="unknown"):
        run_toy4(tmp_path, contract, registry, "hn-out", resume_from=ckpt)
    assert not (tmp_path / "hn-out").exists()


def test_checkpoint_history_float_tick_refused(tmp_path, contract, registry) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "ht", 10)
    ckpt = checkpoint_dir(tmp_path / "ht", 10)

    def mutate(frame, path):
        frame.with_columns(pl.col("tick").cast(pl.Float64)).write_parquet(path)

    _rewrite_table_and_rehash(ckpt, "aggregates", mutate)
    with pytest.raises(ResearchGateError, match="dtype"):
        run_toy4(tmp_path, contract, registry, "ht-out", resume_from=ckpt)
    assert not (tmp_path / "ht-out").exists()


def test_checkpoint_history_hidden_quarter_refused(tmp_path, contract, registry) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "hq", 10)
    ckpt = checkpoint_dir(tmp_path / "hq", 10)

    def mutate(frame, path):
        frame = frame.with_columns(
            pl.when(
                (pl.col("tick") == 0)
                & (pl.col("region_id") == frame["region_id"][0])
                & (pl.col("commodity_id") == frame["commodity_id"][0])
            )
            .then(pl.lit("1900Q1"))
            .otherwise(pl.col("quarter"))
            .alias("quarter")
        )
        frame.write_parquet(path)

    _rewrite_table_and_rehash(ckpt, "aggregates", mutate)
    with pytest.raises(ResearchGateError, match="calendar"):
        run_toy4(tmp_path, contract, registry, "hq-out", resume_from=ckpt)
    assert not (tmp_path / "hq-out").exists()


def test_checkpoint_history_unbalanced_production_refused(
    tmp_path, contract, registry
) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "hprod", 10)
    ckpt = checkpoint_dir(tmp_path / "hprod", 10)

    def mutate(frame, path):
        frame = frame.with_columns(
            (pl.col("production") + 1000.0).alias("production")
        )
        frame.write_parquet(path)

    _rewrite_table_and_rehash(ckpt, "national_accounts", mutate)
    with pytest.raises(ResearchGateError, match="material|boundary"):
        run_toy4(tmp_path, contract, registry, "hprod-out", resume_from=ckpt)
    assert not (tmp_path / "hprod-out").exists()


def test_checkpoint_history_nan_diagnostic_refused(tmp_path, contract, registry) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "hd", 10)
    ckpt = checkpoint_dir(tmp_path / "hd", 10)

    def mutate(frame, path):
        frame = frame.with_columns(
            pl.when(pl.col("tick") == 0)
            .then(float("nan"))
            .otherwise(pl.col("max_material_tolerance_ratio"))
            .alias("max_material_tolerance_ratio")
        )
        frame.write_parquet(path)

    _rewrite_table_and_rehash(ckpt, "tick_diagnostics", mutate)
    with pytest.raises(ResearchGateError, match="non-finite|outside"):
        run_toy4(tmp_path, contract, registry, "hd-out", resume_from=ckpt)
    assert not (tmp_path / "hd-out").exists()


def test_checkpoint_first_tick_production_corruption_refused(
    tmp_path, contract, registry
) -> None:
    """The per-row material identity applies at completed_ticks == 1 too."""
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "f1", 1)
    ckpt = checkpoint_dir(tmp_path / "f1", 1)

    def mutate(frame, path):
        frame.with_columns((pl.col("production") + 1000.0).alias("production")).write_parquet(
            path
        )

    _rewrite_table_and_rehash(ckpt, "national_accounts", mutate)
    with pytest.raises(ResearchGateError, match="material|regional"):
        run_toy4(tmp_path, contract, registry, "f1-out", resume_from=ckpt)
    assert not (tmp_path / "f1-out").exists()


def test_checkpoint_regional_national_disagreement_refused(
    tmp_path, contract, registry
) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "rn", 10)
    ckpt = checkpoint_dir(tmp_path / "rn", 10)

    def mutate(frame, path):
        frame.with_columns(
            pl.when((pl.col("tick") == 0) & (pl.col("commodity_id") == frame["commodity_id"][0]))
            .then(pl.col("production") + 1000.0)
            .otherwise(pl.col("production"))
            .alias("production")
        ).write_parquet(path)

    _rewrite_table_and_rehash(ckpt, "aggregates", mutate)
    with pytest.raises(ResearchGateError, match="regional|disagree|material"):
        run_toy4(tmp_path, contract, registry, "rn-out", resume_from=ckpt)
    assert not (tmp_path / "rn-out").exists()


def test_checkpoint_budget_income_corruption_refused(tmp_path, contract, registry) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "bi", 10)
    ckpt = checkpoint_dir(tmp_path / "bi", 10)

    def mutate(frame, path):
        frame.with_columns(
            pl.when(pl.col("tick") == 0)
            .then(pl.col("income") + 1000.0)
            .otherwise(pl.col("income"))
            .alias("income")
        ).write_parquet(path)

    _rewrite_table_and_rehash(ckpt, "household_budgets", mutate)
    with pytest.raises(
        ResearchGateError, match="income|saving|cash|identity|decomposition"
    ):
        run_toy4(tmp_path, contract, registry, "bi-out", resume_from=ckpt)
    assert not (tmp_path / "bi-out").exists()


@pytest.mark.parametrize(
    "table,mutate",
    [
        (
            "aggregates",
            lambda frame, path: frame.with_columns(
                pl.when(pl.col("tick") == 0)
                .then(None)
                .otherwise(pl.col("quarter"))
                .alias("quarter")
            ).write_parquet(path),
        ),
        (
            "tick_diagnostics",
            lambda frame, path: frame.with_columns(
                pl.when(pl.col("tick") == 0)
                .then(None)
                .otherwise(pl.col("max_material_tolerance_ratio"))
                .alias("max_material_tolerance_ratio")
            ).write_parquet(path),
        ),
    ],
)
def test_checkpoint_history_null_values_refused(
    tmp_path, contract, registry, table, mutate
) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, f"nl-{table}", 10)
    ckpt = checkpoint_dir(tmp_path / f"nl-{table}", 10)
    _rewrite_table_and_rehash(ckpt, table, mutate)
    with pytest.raises(ResearchGateError, match="null"):
        run_toy4(tmp_path, contract, registry, f"nl-{table}-out", resume_from=ckpt)
    assert not (tmp_path / f"nl-{table}-out").exists()


@pytest.mark.parametrize(
    "table,column,match",
    [
        ("aggregates", "used_input", "identity|regional|disagree"),
        ("aggregates", "retail_open", "identity|regional|disagree"),
        ("aggregates", "budget_unmet", "identity"),
        ("aggregates", "total_unmet", "identity"),
        ("aggregates", "production_shortfall", "identity"),
        ("aggregates", "availability_shortage_rate", "rate"),
        ("aggregates", "input_unmet", "identity"),
        ("national_accounts", "export_unmet", "export_unmet"),
        ("national_accounts", "wholesale_open", "composition"),
        ("national_accounts", "retail_close", "regional|composition"),
    ],
)
def test_checkpoint_single_cell_identity_rewrites_refused(
    tmp_path, contract, registry, table, column, match
) -> None:
    """Isolated one-cell rewrites (with the payload hash updated) that break a
    directly recomputable identity must be refused before output."""
    from hsm_lab.storage.checkpoint import checkpoint_dir

    name = f"r4-{table}-{column}"
    paused_run(tmp_path, contract, registry, name, 40)
    ckpt = checkpoint_dir(tmp_path / name, 40)

    def mutate(frame, path, column=column):
        frame.with_columns(
            pl.when(pl.col("tick") == 0)
            .then(pl.col(column) + 1000.0)
            .otherwise(pl.col(column))
            .alias(column)
        ).write_parquet(path)

    _rewrite_table_and_rehash(ckpt, table, mutate)
    with pytest.raises(ResearchGateError, match=match):
        run_toy4(tmp_path, contract, registry, f"{name}-out", resume_from=ckpt)
    assert not (tmp_path / f"{name}-out").exists()


@pytest.mark.parametrize(
    "column,match", [("cash_balance_residual", "residual"), ("forced_saving", "saving")]
)
def test_checkpoint_budget_snapshot_rewrites_refused(
    tmp_path, contract, registry, column, match
) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    name = f"r4b-{column}"
    paused_run(tmp_path, contract, registry, name, 40)
    ckpt = checkpoint_dir(tmp_path / name, 40)

    def mutate(frame, path, column=column):
        frame.with_columns(
            pl.when(pl.col("tick") == 0)
            .then(pl.col(column) + 1000.0)
            .otherwise(pl.col(column))
            .alias(column)
        ).write_parquet(path)

    _rewrite_table_and_rehash(ckpt, "household_budgets", mutate)
    with pytest.raises(ResearchGateError, match=match):
        run_toy4(tmp_path, contract, registry, f"{name}-out", resume_from=ckpt)
    assert not (tmp_path / f"{name}-out").exists()


@pytest.mark.parametrize(
    "array,match",
    [("organization_capacity", "identit"), ("region_equivalent_persons", "identit")],
)
def test_checkpoint_state_identity_rewrites_refused(
    tmp_path, contract, registry, array, match
) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    name = f"r4s-{array}"
    paused_run(tmp_path, contract, registry, name, 40)
    ckpt = checkpoint_dir(tmp_path / name, 40)

    def mutate(arrays, array=array):
        values = np.asarray(arrays[array]).copy()
        values.flat[0] = float(values.flat[0]) + 1000.0
        arrays[array] = values

    _rewrite_state_and_rehash(ckpt, mutate)
    with pytest.raises(ResearchGateError, match=match):
        run_toy4(tmp_path, contract, registry, f"{name}-out", resume_from=ckpt)
    assert not (tmp_path / f"{name}-out").exists()



    """tick-0115 resume executes exactly 1985Q4; a tick-0116 resume is a no-op."""
    paused_run(tmp_path, contract, registry, "p115", 115)
    from hsm_lab.storage.checkpoint import checkpoint_dir, load_toy4_checkpoint

    spec = load_scenario(REPO_ROOT, "toy4")
    state, _history, _rng, metadata = load_toy4_checkpoint(
        checkpoint_dir(tmp_path / "p115", 115), spec, contract, registry
    )
    assert metadata["next_quarter"] == "1985Q4"
    resumed = run_toy4(
        tmp_path, contract, registry, "r115", resume_from=checkpoint_dir(
            tmp_path / "p115", 115
        )
    )
    assert resumed.completed_ticks == 116
    assert resumed.last_completed_quarter == "1985Q4"

    terminal = run_toy4(
        tmp_path, contract, registry, "p116", until="1985Q4", checkpoint_every=1
    )
    assert terminal.status == "completed"
    with pytest.raises(ConfigError, match="zero-tick replay"):
        run_toy4(
            tmp_path,
            contract,
            registry,
            "r116",
            resume_from=checkpoint_dir(tmp_path / "p116", 116),
        )
    assert not (tmp_path / "r116").exists()


def test_checkpoint_cross_organization_inventory_move_refused(
    tmp_path, contract, registry
) -> None:
    """Moving inventory between organizations while preserving the national
    total still breaks the per-region boundary rows."""
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "orgmove", 40)
    ckpt = checkpoint_dir(tmp_path / "orgmove", 40)

    def mutate(arrays):
        org_inv = np.asarray(arrays["organization_input_inventory"]).copy()
        org_inv[3, 0] += 1.0
        org_inv[7, 0] -= 1.0
        arrays["organization_input_inventory"] = org_inv

    _rewrite_state_and_rehash(ckpt, mutate)
    with pytest.raises(ResearchGateError, match="organization input|disagree|identities"):
        run_toy4(tmp_path, contract, registry, "orgmove-out", resume_from=ckpt)
    assert not (tmp_path / "orgmove-out").exists()


@pytest.mark.parametrize(
    "array,index,value",
    [
        ("organization_region", 0, 1),
        ("organization_output_sector", 0, 1),
        ("organization_id", 0, 999),
        ("household_region", 0, 5),
        ("household_id", 0, 10000),
    ],
)
def test_checkpoint_id_mapping_corruption_refused(
    tmp_path, contract, registry, array, index, value
) -> None:
    """Immutable id/region/sector mappings from the initializer must be
    enforced at admission."""
    from hsm_lab.storage.checkpoint import checkpoint_dir

    name = f"idmap-{array}-{index}"
    paused_run(tmp_path, contract, registry, name, 10)
    ckpt = checkpoint_dir(tmp_path / name, 10)

    def mutate(arrays, array=array, index=index, value=value):
        values = np.asarray(arrays[array]).copy()
        values[index] = value
        arrays[array] = values

    _rewrite_state_and_rehash(ckpt, mutate)
    with pytest.raises(ResearchGateError):
        run_toy4(tmp_path, contract, registry, f"{name}-out", resume_from=ckpt)
    assert not (tmp_path / f"{name}-out").exists()


def test_checkpoint_within_region_cash_redistribution_refused(
    tmp_path, contract, registry
) -> None:
    """Redistributing cash between households of one region (weighted total
    unchanged) breaks the size-proportionality identity of the fixed kernel."""
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "cashredist", 40)
    ckpt = checkpoint_dir(tmp_path / "cashredist", 40)

    def mutate(arrays):
        cash = np.asarray(arrays["household_cash"]).copy()
        cash[0] += 1.0
        cash[20] -= 1.0
        arrays["household_cash"] = cash

    _rewrite_state_and_rehash(ckpt, mutate)
    with pytest.raises(ResearchGateError, match="identities|proportional"):
        run_toy4(tmp_path, contract, registry, "cashredist-out", resume_from=ckpt)
    assert not (tmp_path / "cashredist-out").exists()


@pytest.mark.parametrize(
    "table,column,match",
    [
        ("aggregates", "desired_input", "desired_input|ordered_input"),
        ("aggregates", "allocated_input", "allocated_identity"),
        ("aggregates", "retail_available", "retail_available_identity|recomputation"),
        ("household_budgets", "household_count", "household_count"),
        ("household_budgets", "weight_sum", "weight_sum"),
        ("household_budgets", "equivalent_persons", "equivalent_persons"),
    ],
)
def test_checkpoint_compact_cell_identity_rewrites_refused(
    tmp_path, contract, registry, table, column, match
) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    name = f"c6-{table}-{column}"
    paused_run(tmp_path, contract, registry, name, 40)
    ckpt = checkpoint_dir(tmp_path / name, 40)

    def mutate(frame, path, column=column):
        frame.with_columns(
            pl.when(pl.col("tick") == 0)
            .then(pl.col(column) + 1000.0)
            .otherwise(pl.col(column))
            .alias(column)
        ).write_parquet(path)

    _rewrite_table_and_rehash(ckpt, table, mutate)
    with pytest.raises(ResearchGateError, match=match):
        run_toy4(tmp_path, contract, registry, f"{name}-out", resume_from=ckpt)
    assert not (tmp_path / f"{name}-out").exists()


@pytest.mark.parametrize(
    "table,column,match",
    [
        ("aggregates", "production_target", "production_target|production_shortfall"),
        ("aggregates", "production_shortfall", "production_shortfall"),
        ("national_accounts", "export_desired", "export_unmet|forcing"),
        ("national_accounts", "imports", "material|forcing"),
        ("national_accounts", "material_balance_tolerance_ratio", "negative"),
        ("events", "event_type", "event type"),
        ("events", "details_json", "event"),
        ("tick_diagnostics", "max_material_tolerance_ratio", "event"),
    ],
)
def test_checkpoint_round7_identity_rewrites_refused(
    tmp_path, contract, registry, table, column, match
) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    name = f"c7-{table}-{column}"
    paused_run(tmp_path, contract, registry, name, 40)
    ckpt = checkpoint_dir(tmp_path / name, 40)

    def mutate(frame, path, column=column, table=table):
        if table == "events" and column == "event_type":
            replacement = pl.lit("forged_completed")
        elif table == "events" and column == "details_json":
            replacement = pl.lit("{}")
        elif table == "national_accounts" and column == "material_balance_tolerance_ratio":
            replacement = pl.lit(-0.5)
        elif table == "tick_diagnostics" and column == "max_material_tolerance_ratio":
            replacement = pl.lit(0.5)
        else:
            replacement = pl.col(column) + 1000.0
        frame.with_columns(
            pl.when(pl.col("tick") == 0).then(replacement).otherwise(pl.col(column)).alias(column)
        ).write_parquet(path)

    _rewrite_table_and_rehash(ckpt, table, mutate)
    with pytest.raises(ResearchGateError, match=match):
        run_toy4(tmp_path, contract, registry, f"{name}-out", resume_from=ckpt)
    assert not (tmp_path / f"{name}-out").exists()


def test_checkpoint_unfunded_retail_transfer_refused(tmp_path, contract, registry) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "unfunded", 40)
    ckpt = checkpoint_dir(tmp_path / "unfunded", 40)

    def mutate(frame, path):
        frame.with_columns(
            [
                pl.when(pl.col("tick") == 0)
                .then(pl.col(column) + 1000.0)
                .otherwise(pl.col(column))
                .alias(column)
                for column in (
                    "retail_planned",
                    "retail_incoming",
                    "retail_available",
                    "retail_sales",
                )
            ]
        ).write_parquet(path)

    _rewrite_table_and_rehash(ckpt, "aggregates", mutate)
    with pytest.raises(ResearchGateError):
        run_toy4(tmp_path, contract, registry, "unfunded-out", resume_from=ckpt)
    assert not (tmp_path / "unfunded-out").exists()


def test_checkpoint_paired_budget_and_demand_mutations_refused(
    tmp_path, contract, registry
) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    # income and spending both +1000 keeps the cash identity but not the
    # recomputed household income.
    paused_run(tmp_path, contract, registry, "pairinc", 40)
    ckpt = checkpoint_dir(tmp_path / "pairinc", 40)

    def mutate_income(frame, path):
        frame.with_columns(
            [
                pl.when(pl.col("tick") == 0)
                .then(pl.col(column) + 1000.0)
                .otherwise(pl.col(column))
                .alias(column)
                for column in ("income", "spending")
            ]
        ).write_parquet(path)

    _rewrite_table_and_rehash(ckpt, "household_budgets", mutate_income)
    with pytest.raises(ResearchGateError, match="recomputation"):
        run_toy4(tmp_path, contract, registry, "pairinc-out", resume_from=ckpt)
    assert not (tmp_path / "pairinc-out").exists()

    # demand trio +1000 keeps the difference identities but not the recomputed
    # baskets.
    paused_run(tmp_path, contract, registry, "pairdem", 40)
    ckpt2 = checkpoint_dir(tmp_path / "pairdem", 40)

    def mutate_demand(frame, path):
        new_desired = pl.col("household_desired") + 1000.0
        new_total = pl.col("total_unmet") + 1000.0
        frame.with_columns(
            [
                pl.when(pl.col("tick") == 0)
                .then(new_desired)
                .otherwise(pl.col("household_desired"))
                .alias("household_desired"),
                pl.when(pl.col("tick") == 0)
                .then(pl.col("budget_unmet") + 1000.0)
                .otherwise(pl.col("budget_unmet"))
                .alias("budget_unmet"),
                pl.when(pl.col("tick") == 0)
                .then(new_total)
                .otherwise(pl.col("total_unmet"))
                .alias("total_unmet"),
                pl.when(pl.col("tick") == 0)
                .then(new_total / new_desired)
                .otherwise(pl.col("total_unmet_rate"))
                .alias("total_unmet_rate"),
            ]
        ).write_parquet(path)

    _rewrite_table_and_rehash(ckpt2, "aggregates", mutate_demand)
    with pytest.raises(ResearchGateError):
        run_toy4(tmp_path, contract, registry, "pairdem-out", resume_from=ckpt2)
    assert not (tmp_path / "pairdem-out").exists()


@pytest.mark.parametrize(
    "bad_value",
    ['"NaN"', "NaN", "[]", "true", "null", "1e999"],
)
def test_checkpoint_event_details_type_and_finiteness_refused(
    tmp_path, contract, registry, bad_value
) -> None:
    """Preserve the genuine digest and unaffected details; only the diagnostic
    field under test is replaced with a non-number / non-finite value."""
    import json as _json

    from hsm_lab.storage.checkpoint import checkpoint_dir

    name = f"ev-{abs(hash(bad_value)) % 10000}"
    paused_run(tmp_path, contract, registry, name, 10)
    ckpt = checkpoint_dir(tmp_path / name, 10)

    def mutate(frame, path):
        rows = []
        for row in frame.iter_rows(named=True):
            details = _json.loads(row["details_json"])
            if int(row["tick"]) == 0:
                details["max_material_abs_residual"] = _json.loads(bad_value)
            row = dict(row)
            row["details_json"] = _json.dumps(details, sort_keys=True, separators=(",", ":"))
            rows.append(row)
        pl.DataFrame(rows, schema=frame.schema).write_parquet(path)

    _rewrite_table_and_rehash(ckpt, "events", mutate)
    with pytest.raises(ResearchGateError):
        run_toy4(tmp_path, contract, registry, f"{name}-out", resume_from=ckpt)
    assert not (tmp_path / f"{name}-out").exists()


def test_checkpoint_order_identity_refused(tmp_path, contract, registry) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "order", 40)
    ckpt = checkpoint_dir(tmp_path / "order", 40)

    def mutate(frame, path):
        frame.with_columns(
            [
                pl.when(pl.col("tick") == 0)
                .then(pl.col("ordered_input") + 1.0)
                .otherwise(pl.col("ordered_input"))
                .alias("ordered_input"),
                pl.when(pl.col("tick") == 0)
                .then(pl.col("input_unmet") + 1.0)
                .otherwise(pl.col("input_unmet"))
                .alias("input_unmet"),
            ]
        ).write_parquet(path)

    _rewrite_table_and_rehash(ckpt, "aggregates", mutate)
    with pytest.raises(ResearchGateError):
        run_toy4(tmp_path, contract, registry, "order-out", resume_from=ckpt)
    assert not (tmp_path / "order-out").exists()


def test_checkpoint_regional_stock_continuity_refused(
    tmp_path, contract, registry
) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "rcont", 40)
    ckpt = checkpoint_dir(tmp_path / "rcont", 40)

    def mutate(frame, path):
        regions = sorted(frame["region_id"].unique().to_list())
        first, second = regions[0], regions[1]
        columns = (
            "organization_input_open",
            "organization_input_close",
            "available_input",
        )
        exprs = []
        for column in columns:
            plus = (
                pl.when(
                    (pl.col("tick") == 10)
                    & (pl.col("region_id") == first)
                    & (pl.col("commodity_id") == "energy")
                )
                .then(pl.col(column) + 1.0)
                .when(
                    (pl.col("tick") == 10)
                    & (pl.col("region_id") == second)
                    & (pl.col("commodity_id") == "energy")
                )
                .then(pl.col(column) - 1.0)
                .otherwise(pl.col(column))
                .alias(column)
            )
            exprs.append(plus)
        frame.with_columns(exprs).write_parquet(path)

    _rewrite_table_and_rehash(ckpt, "aggregates", mutate)
    with pytest.raises(ResearchGateError, match="continuity|disagree|regional"):
        run_toy4(tmp_path, contract, registry, "rcont-out", resume_from=ckpt)
    assert not (tmp_path / "rcont-out").exists()


@pytest.mark.parametrize("mutate_kind", ["float", "nonscalar"])
def test_checkpoint_completed_ticks_dtype_shape_refused(
    tmp_path, contract, registry, mutate_kind
) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    name = f"bt-{mutate_kind}"
    paused_run(tmp_path, contract, registry, name, 10)
    ckpt = checkpoint_dir(tmp_path / name, 10)

    def mutate(arrays):
        if mutate_kind == "float":
            arrays["completed_ticks"] = np.asarray(40.9, dtype=np.float64)
        else:
            arrays["completed_ticks"] = np.asarray([10, 10], dtype=np.int64)

    _rewrite_state_and_rehash(ckpt, mutate)
    with pytest.raises(ResearchGateError, match="completed_ticks"):
        run_toy4(tmp_path, contract, registry, f"{name}-out", resume_from=ckpt)
    assert not (tmp_path / f"{name}-out").exists()


def test_checkpoint_rng_profile_binding_refused(tmp_path, contract, registry) -> None:
    """Rewriting the RNG snapshot to a valid-but-wrong PCG64 position or draw
    count (same seed) must be refused."""
    from hsm_lab.storage.checkpoint import checkpoint_dir

    paused_run(tmp_path, contract, registry, "rngprof", 10)
    ckpt = checkpoint_dir(tmp_path / "rngprof", 10)
    metadata_path = ckpt / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    snapshot = metadata["rng_snapshot"]
    # Advance the stream by one extra draw beyond the initialization profile.
    from hsm_lab.engine.rng import RngRegistry

    extra = RngRegistry.from_snapshot(snapshot)
    extra.uniform("toy4.initial_households", 1)
    metadata["rng_snapshot"] = extra.snapshot()
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    with pytest.raises(ResearchGateError, match="RNG snapshot"):
        run_toy4(tmp_path, contract, registry, "rngprof-out", resume_from=ckpt)
    assert not (tmp_path / "rngprof-out").exists()


def test_runtime_gate_rejects_fabricated_order() -> None:
    """The runtime invariant gate enforces the ordering identity, not only the
    checkpoint validator."""
    from hsm_lab.engine.accounting import (
        AccountingError,
        check_toy4_invariants,
        snapshot_opening_stocks,
    )
    from tests.test_toy4 import completed_reference

    state, flows, parameters = completed_reference()
    # Move ordered_input and input_unmet together so only the ordering identity
    # (not the input_unmet decomposition) is violated.
    flows.ordered_input = flows.ordered_input + 1.0
    flows.input_unmet = flows.input_unmet + 1.0
    with pytest.raises(AccountingError, match="ordered_input"):
        check_toy4_invariants(
            snapshot_opening_stocks(state, flows), state, flows, parameters
        )


def test_resume_restores_overridden_profile_not_template_defaults(
    tmp_path, contract, registry
) -> None:
    """N1000/seed1730 checkpoint resumes without re-passing overrides and is
    not silently overwritten by the N1600/seed1729 template."""
    run_toy4(
        tmp_path, contract, registry, "ref", overrides={"households": 1000, "seed": 1730}
    )
    paused = run_toy4(
        tmp_path,
        contract,
        registry,
        "p",
        until="1970Q1",
        overrides={"households": 1000, "seed": 1730},
        checkpoint_every=1,
    )
    assert paused.status == "paused"
    from hsm_lab.storage.checkpoint import checkpoint_dir

    boundary = paused.completed_ticks
    resumed = run_toy4(
        tmp_path, contract, registry, "r", resume_from=checkpoint_dir(
            tmp_path / "p", boundary
        )
    )
    assert resumed.households == 1000
    assert resumed.seed == 1730
    assert_runs_equivalent(tmp_path / "ref", tmp_path / "r", 116)


def test_resume_output_is_prefix_plus_suffix(tmp_path, contract, registry) -> None:
    paused_run(tmp_path, contract, registry, "p40", 40)
    from hsm_lab.storage.checkpoint import checkpoint_dir

    run_toy4(
        tmp_path, contract, registry, "r40", resume_from=checkpoint_dir(
            tmp_path / "p40", 40
        )
    )
    aggregates = pl.read_parquet(tmp_path / "r40" / "aggregates.parquet")
    assert aggregates.height == 116 * 20 * 4
    ticks = sorted(aggregates["tick"].unique().to_list())
    assert ticks == list(range(116))
    # prefix rows are byte-identical to the paused run's rows
    paused_rows = pl.read_parquet(tmp_path / "p40" / "aggregates.parquet")
    assert aggregates.head(paused_rows.height).equals(paused_rows)


def test_corrupt_checkpoint_payload_refused(tmp_path, contract, registry) -> None:
    paused_run(tmp_path, contract, registry, "pc", 10)
    from hsm_lab.storage.checkpoint import checkpoint_dir

    ckpt = checkpoint_dir(tmp_path / "pc", 10)
    target = ckpt / "aggregates.parquet"
    raw = bytearray(target.read_bytes())
    raw[-1] ^= 0xFF
    target.write_bytes(bytes(raw))
    with pytest.raises(ResearchGateError, match="digest mismatch"):
        run_toy4(tmp_path, contract, registry, "rc", resume_from=ckpt)
    assert not (tmp_path / "rc").exists()


def test_missing_checkpoint_directory_refused(tmp_path, contract, registry) -> None:
    with pytest.raises(ResearchGateError, match="not found"):
        run_toy4(
            tmp_path, contract, registry, "rx", resume_from=tmp_path / "nope"
        )
    assert not (tmp_path / "rx").exists()



def test_parameter_mismatch_refused(tmp_path, contract, registry, spec) -> None:
    paused_run(tmp_path, contract, registry, "pm", 10)
    from hsm_lab.storage.checkpoint import checkpoint_dir

    tampered = ScenarioSpec.model_validate(
        spec.model_copy(
            update={
                "toy4_parameters": spec.toy4_parameters.model_copy(
                    update={"income_per_person": 7.0}
                )
            }
        ).model_dump()
    )
    from hsm_lab.engine.toy4 import run_toy4

    with pytest.raises(ResearchGateError, match="differs from the current template"):
        run_toy4(
            tampered,
            tmp_path / "rm",
            contract,
            registry,
            resume_from=checkpoint_dir(tmp_path / "pm", 10),
        )


def test_axes_mismatch_refused(tmp_path, contract, registry, spec) -> None:
    paused_run(tmp_path, contract, registry, "am", 10)
    from hsm_lab.storage.checkpoint import checkpoint_dir

    tampered = spec.model_copy(
        update={"commodities": ["a", "b", "c", "d"], "forcing_ids": []}
    )
    from hsm_lab.engine.toy4 import run_toy4

    with pytest.raises((ConfigError, ResearchGateError)):
        run_toy4(
            tampered,
            tmp_path / "rm2",
            contract,
            registry,
            resume_from=checkpoint_dir(tmp_path / "am", 10),
        )


def test_checkpoint_refuses_overwrite_and_uses_staging(tmp_path, contract, registry) -> None:
    manifest = run_toy4(tmp_path, contract, registry, "ow", until="1958Q1")
    boundary = manifest.completed_ticks
    run_dir = tmp_path / "ow"
    from hsm_lab.storage.checkpoint import checkpoint_dir, save_toy4_checkpoint

    ckpt = checkpoint_dir(run_dir, boundary)
    assert ckpt.is_dir()
    # No staging leftovers were published as partial checkpoints.
    leftovers = [p for p in (run_dir / "checkpoints").iterdir() if p.name.startswith(".tmp-")]
    assert leftovers == []
    # Saving the same boundary again is refused.
    state = np.load(ckpt / "state.npz", allow_pickle=False)
    from hsm_lab.engine.rng import RngRegistry
    from hsm_lab.engine.state import Toy4History

    with pytest.raises(ResearchGateError, match="refusing to overwrite"):
        save_toy4_checkpoint(
            ckpt,
            _state_from_npz(state, boundary),
            Toy4History(digest_chain="x" * 64),
            RngRegistry(1729),
            {"scenario": load_scenario(REPO_ROOT, "toy4").model_dump(mode="json")},
        )


def _state_from_npz(payload, completed: int):
    from hsm_lab.storage.checkpoint import _STATE_DTYPES, _state_from_arrays

    arrays = {name: np.ascontiguousarray(payload[name], dtype=dtype)
              for name, dtype in _STATE_DTYPES.items()}
    return _state_from_arrays(arrays, completed)


def test_checkpoint_metadata_records_lineage(tmp_path, contract, registry) -> None:
    from hsm_lab.storage.checkpoint import checkpoint_dir

    manifest = run_toy4(tmp_path, contract, registry, "lin", until="1959Q1")
    boundary = manifest.completed_ticks
    metadata = load_json(checkpoint_dir(tmp_path / "lin", boundary) / "metadata.json")
    assert metadata["checkpoint_version"] == "toy4-checkpoint-v1"
    assert metadata["state_version"] == "toy4-state-v1"
    assert metadata["engine_version"] == "toy4-engine-v1"
    assert metadata["completed_ticks"] == boundary
    assert metadata["last_completed_quarter"] == "1959Q1"
    assert metadata["next_quarter"] == "1959Q2"
    assert metadata["source_run_id"] == manifest.run_id
    assert set(metadata["payload_sha256"]) == {
        "state.npz",
        "aggregates.parquet",
        "national_accounts.parquet",
        "household_budgets.parquet",
        "tick_diagnostics.parquet",
        "events.parquet",
    }
    scenario = ScenarioSpec.model_validate(metadata["scenario"])
    assert scenario.kind == "toy4"
    diagnostics = pl.read_parquet(
        checkpoint_dir(tmp_path / "lin", boundary) / "tick_diagnostics.parquet"
    )
    assert diagnostics["digest"][-1] == metadata["digest_chain"]


def test_manifest_hashes_nested_checkpoints(tmp_path, contract, registry) -> None:
    from hsm_lab.contract.guards import sha256_file

    manifest = run_toy4(tmp_path, contract, registry, "hashes", checkpoint_every=40)
    hashes = manifest.output_hashes
    nested = [name for name in hashes if name.startswith("checkpoints/")]
    assert nested, "nested checkpoint payload files must be hashed individually"
    for name in nested:
        assert hashes[name] == sha256_file(tmp_path / "hashes" / name)
    assert "manifest.json" not in hashes
