"""D5 + D6: synthetic array/aggregation invariants, storage, manifest gates."""

from __future__ import annotations

import hashlib
from pathlib import Path

import duckdb
import numpy as np
import polars as pl
import pytest

from hsm_lab.contract.schemas import ResearchGateError
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.smoke import run_smoke
from tests.conftest import REPO_ROOT, load_json, smoke_spec


@pytest.fixture()
def registry() -> DataRegistry:
    return DataRegistry.load(REPO_ROOT)


def _run(tmp_path: Path, name: str, contract, registry, **overrides):
    manifest = run_smoke(smoke_spec(contract, **overrides), tmp_path / name, contract, registry)
    return manifest, tmp_path / name


def test_aggregate_shape_and_group_invariants(contract, registry, tmp_path) -> None:
    _, run_dir = _run(tmp_path, "agg", contract, registry)
    frame = pl.read_parquet(run_dir / "aggregates.parquet")
    assert frame.height == 10 * 20 * 4 * 2  # ticks x regions x commodities x kinds
    assert frame["commodity_id"].n_unique() == 4
    household_rows = frame.filter(pl.col("actor_kind") == "households")
    assert set(household_rows["count"].to_list()) == {50}
    assert set(household_rows["weight_sum"].to_list()) == {50.0}
    enterprise_counts = set(
        frame.filter(pl.col("actor_kind") == "enterprises")["count"].to_list()
    )
    assert enterprise_counts == {2, 3}  # ids 0..49 -> regions via id % 20
    assert frame["probe_sum"].is_finite().all()
    assert (frame["probe_sum"] >= 0).all()
    # every (tick, kind, region, commodity) appears exactly once
    grouped = frame.group_by(["tick", "actor_kind", "region_id", "commodity_id"]).len()
    assert (grouped["len"] == 1).all()


def test_empty_region_mean_is_null_not_nan(contract, registry, tmp_path) -> None:
    _, run_dir = _run(tmp_path, "sparse", contract, registry, enterprises=5)
    frame = pl.read_parquet(run_dir / "aggregates.parquet")
    enterprise = frame.filter(
        (pl.col("actor_kind") == "enterprises") & (pl.col("region_id") == "zala")
    )
    assert (enterprise["count"] == 0).all()
    assert (enterprise["probe_sum"] == 0.0).all()
    assert enterprise["probe_mean"].is_null().all()
    assert not enterprise["probe_mean"].is_nan().any()


def test_deterministic_mode_values_and_zero_draws(contract, registry, tmp_path) -> None:
    manifest, run_dir = _run(
        tmp_path, "det", contract, registry, stochastic=False, seed=0
    )
    assert manifest.rng_draws_count == 0
    assert manifest.stochastic_modules_active == []
    frame = pl.read_parquet(run_dir / "aggregates.parquet")
    tick1 = frame.filter(pl.col("tick") == 1)
    assert set(tick1["probe_mean"].drop_nulls().to_list()) == {2.0}
    summary = load_json(run_dir / "summary.json")
    assert summary["deterministic_mode"]["warning"] == "deterministic_no_replicates"
    assert summary["rng"]["stochastic_replicates_valid"] is False


def test_same_seed_compact_full_agree(contract, registry, tmp_path) -> None:
    compact_manifest, compact_dir = _run(tmp_path, "c1", contract, registry)
    full_manifest, full_dir = _run(
        tmp_path, "f1", contract, registry, output_policy="research_full"
    )
    assert compact_manifest.deterministic_replay_digest == (
        full_manifest.deterministic_replay_digest
    )
    assert compact_manifest.rng_draws_count == full_manifest.rng_draws_count == 42_000
    assert full_manifest.rng_draws_by_module == {
        "smoke.enterprises": 2_000,
        "smoke.households": 40_000,
    }
    compact_frame = pl.read_parquet(compact_dir / "aggregates.parquet")
    full_frame = pl.read_parquet(full_dir / "aggregates.parquet")
    assert compact_frame.equals(full_frame)
    # compact writes no micro files and no micro views
    assert sorted(p.name for p in compact_dir.iterdir()) == [
        "aggregates.parquet",
        "manifest.json",
        "summary.json",
        "trajectory.duckdb",
    ]
    compact_db = duckdb.connect(str(compact_dir / "trajectory.duckdb"), read_only=True)
    tables = compact_db.execute(
        "SELECT table_name FROM information_schema.tables"
    ).fetchall()
    compact_db.close()
    assert {name for (name,) in tables} == {"aggregates", "events"}


def test_full_micro_matches_aggregates(contract, registry, tmp_path) -> None:
    _, full_dir = _run(tmp_path, "full", contract, registry, output_policy="research_full")
    assert (full_dir / "households.parquet").stat().st_size > 0
    connection = duckdb.connect(str(full_dir / "trajectory.duckdb"), read_only=True)
    micro = connection.execute(
        """
        SELECT region_id, commodity_id, count(*) AS n, sum(probe_value) AS s
        FROM households_micro WHERE tick = 9 GROUP BY 1, 2 ORDER BY 1, 2
        """
    ).fetchall()
    compact = connection.execute(
        """
        SELECT region_id, commodity_id, probe_sum FROM aggregates
        WHERE actor_kind = 'households' AND tick = 9
        """
    ).fetchall()
    connection.close()
    assert len(micro) == 80
    for (_region, _commodity, count, total), (_, _, expected) in zip(
        micro, sorted(compact), strict=True
    ):
        assert count == 50
        assert total == pytest.approx(expected, rel=1e-12, abs=1e-12)
    household_micro = pl.read_parquet(full_dir / "households.parquet")
    assert household_micro.height == 40_000
    assert set(household_micro.columns) == {
        "tick", "quarter", "actor_id", "region_id", "commodity_id", "weight", "probe_value"
    }


def test_manifest_hashes_recompute(contract, registry, tmp_path) -> None:
    manifest, run_dir = _run(tmp_path, "m", contract, registry)
    payload = load_json(run_dir / "manifest.json")
    for name, expected in manifest.output_hashes.items():
        actual = hashlib.sha256((run_dir / name).read_bytes()).hexdigest()
        assert actual == expected, name
    assert "manifest.json" not in manifest.output_hashes
    from hsm_lab.provenance.manifest import (
        canonical_digest,
        compute_data_manifest_hash,
        compute_lock_hash,
        compute_scenario_hash,
    )

    assert payload["lock_hash"] == compute_lock_hash(REPO_ROOT)
    assert payload["data_manifest_hash"] == compute_data_manifest_hash(REPO_ROOT)
    assert payload["scenario_hash"] == compute_scenario_hash(smoke_spec(contract))
    assert payload["parameter_hash"] == canonical_digest({})
    assert payload["baseline_hash"] == contract.expected_baseline_sha256
    assert payload["run_kind"] == "synthetic_engine_smoke"
    assert payload["political_mode"] is None
    assert payload["research_warnings"] == contract.research_warnings
    assert payload["status"] == "completed"
    assert payload["finished_at"] >= payload["started_at"]


def test_preexisting_output_dir_rejected_and_untouched(
    contract, registry, tmp_path
) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "previous.txt").write_text("keep me", encoding="utf-8")
    with pytest.raises(ResearchGateError, match="already exists"):
        run_smoke(smoke_spec(contract), existing, contract, registry)
    assert (existing / "previous.txt").read_text(encoding="utf-8") == "keep me"
    assert sorted(p.name for p in existing.iterdir()) == ["previous.txt"]


def test_io_failure_writes_failed_manifest(contract, registry, tmp_path, monkeypatch) -> None:
    import hsm_lab.engine.smoke as smoke_module

    def boom(*args, **kwargs):
        raise OSError("disk exploded during duckdb write")

    monkeypatch.setattr(smoke_module, "write_duckdb", boom)
    with pytest.raises(OSError, match="disk exploded"):
        run_smoke(smoke_spec(contract), tmp_path / "failed", contract, registry)
    payload = load_json(tmp_path / "failed" / "manifest.json")
    assert payload["status"] == "failed"
    assert "disk exploded" in payload["failure_message"]
    assert payload["output_hashes"] == {}


def test_events_table_counts_ticks(contract, registry, tmp_path) -> None:
    _, run_dir = _run(tmp_path, "ev", contract, registry)
    connection = duckdb.connect(str(run_dir / "trajectory.duckdb"), read_only=True)
    events = connection.execute("SELECT tick, event FROM events ORDER BY tick").fetchall()
    quarters = connection.execute(
        "SELECT DISTINCT quarter FROM aggregates ORDER BY quarter"
    ).fetchall()
    connection.close()
    assert events == [(tick, "synthetic_tick_completed") for tick in range(10)]
    assert [q for (q,) in quarters] == [
        "1957Q1", "1957Q2", "1957Q3", "1957Q4",
        "1958Q1", "1958Q2", "1958Q3", "1958Q4",
        "1959Q1", "1959Q2",
    ]


def test_weights_conserved_every_tick(contract, registry, tmp_path) -> None:
    _, run_dir = _run(tmp_path, "w", contract, registry)
    frame = pl.read_parquet(run_dir / "aggregates.parquet")
    per_tick = frame.group_by(["tick", "actor_kind"]).agg(
        pl.col("weight_sum").sum().alias("total_weight"),
        pl.col("count").sum().alias("total_count"),
    )
    household_totals = per_tick.filter(pl.col("actor_kind") == "households")
    # rows are region x commodity: each household is weighted once per commodity
    assert set(household_totals["total_weight"].to_list()) == {4000.0}
    assert set(household_totals["total_count"].to_list()) == {4000}
    assert (frame["weight_sum"] == frame["count"].cast(pl.Float64)).all()
    enterprise_totals = per_tick.filter(pl.col("actor_kind") == "enterprises")
    assert set(enterprise_totals["total_weight"].to_list()) == {200.0}


def test_summary_carries_warnings_and_no_mechanisms(contract, registry, tmp_path) -> None:
    _, run_dir = _run(tmp_path, "s", contract, registry)
    summary = load_json(run_dir / "summary.json")
    assert summary["mechanism_diagnostics"] == {}
    assert len(summary["research_warnings"]) == 2
    assert summary["parameter_vector"] == {}
    assert summary["rng"]["draws_count"] == 42_000
    assert summary["row_counts"]["aggregates"] == 1600


def test_numpy_digest_stability(contract, registry, tmp_path) -> None:
    """Same seed + arrays -> identical digest bytes via the documented recipe."""
    from hsm_lab.engine.smoke import replay_digest

    spec = smoke_spec(contract)
    a = np.arange(8, dtype=np.float64).reshape(4, 2) / 7.0
    b = np.ones((2, 2), dtype=np.float64)
    first = replay_digest(spec, a, b, ["1957Q1", "1957Q2"], "pcg64-sha256-module-v1")
    second = replay_digest(spec, a.copy(), b.copy(), ["1957Q1", "1957Q2"],
                           "pcg64-sha256-module-v1")
    assert first == second
    other = replay_digest(spec, a + 1e-9, b, ["1957Q1", "1957Q2"],
                          "pcg64-sha256-module-v1")
    assert other != first



def test_io_failure_manifest_records_real_draws(contract, registry, tmp_path, monkeypatch) -> None:
    """A late failure must not fabricate zero RNG usage (review P5)."""
    import hsm_lab.engine.smoke as smoke_module
    from hsm_lab.engine import rng as rng_module

    actual = {"draws": 0}
    original_uniform = rng_module.RngRegistry.uniform

    def counting(self, module, size):  # noqa: ANN001, ANN202
        draws = original_uniform(self, module, size)
        actual["draws"] += draws.size
        return draws

    def boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise OSError("disk exploded during duckdb write")

    monkeypatch.setattr(rng_module.RngRegistry, "uniform", counting)
    monkeypatch.setattr(smoke_module, "write_duckdb", boom)
    with pytest.raises(OSError, match="disk exploded"):
        run_smoke(smoke_spec(contract), tmp_path / "late-fail", contract, registry)
    payload = load_json(tmp_path / "late-fail" / "manifest.json")
    assert payload["status"] == "failed"
    assert actual["draws"] == 42_000
    assert payload["rng_draws_count"] == 42_000, "failed manifest must report real draws"
    assert set(payload["stochastic_modules_active"]) == {
        "smoke.households",
        "smoke.enterprises",
    }
    assert payload["rng_draws_by_module"]["smoke.households"] == 40_000
    assert payload["deterministic_replay_digest"] == ""


def test_setup_failure_writes_failed_manifest(contract, registry, tmp_path, monkeypatch) -> None:
    """Failures before the first tick must still convert 'running' -> 'failed'."""
    import hsm_lab.engine.smoke as smoke_module

    def no_allocate(*args, **kwargs):  # noqa: ANN002, ANN003
        raise MemoryError("review allocation failure")

    monkeypatch.setattr(smoke_module.np, "zeros", no_allocate)
    with pytest.raises(MemoryError):
        run_smoke(smoke_spec(contract), tmp_path / "setup-fail", contract, registry)
    payload = load_json(tmp_path / "setup-fail" / "manifest.json")
    assert payload["status"] == "failed"
    assert "MemoryError" in payload["failure_message"]
    assert payload["rng_draws_count"] == 0  # genuinely zero: no draw happened
    assert payload["deterministic_replay_digest"] == ""


def test_second_writer_failure_writes_failed_manifest(
    contract, registry, tmp_path, monkeypatch
) -> None:
    """A full-policy run failing while opening the second micro writer fails closed."""
    import hsm_lab.engine.smoke as smoke_module
    from hsm_lab.storage.output import MicroWriter

    real_writer = MicroWriter
    calls = {"n": 0}

    def flaky_second(path):  # noqa: ANN001
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("second writer could not open")
        return real_writer(path)

    monkeypatch.setattr(smoke_module, "MicroWriter", flaky_second)
    with pytest.raises(OSError, match="second writer"):
        run_smoke(
            smoke_spec(contract, output_policy="research_full"),
            tmp_path / "writer-fail",
            contract,
            registry,
        )
    payload = load_json(tmp_path / "writer-fail" / "manifest.json")
    assert payload["status"] == "failed"
    assert "second writer" in payload["failure_message"]
    assert payload["rng_draws_count"] == 0
