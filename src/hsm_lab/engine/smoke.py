"""The P00 synthetic smoke workload. NOT an economic engine.

``run_smoke`` drives an O(NG + EG) array/RNG/aggregation/storage load: probe
arrays per actor kind, one uniform draw per module per tick, vectorized
region x commodity aggregation, and Parquet/DuckDB output under a run
manifest. Every value is a ``probe_value`` - never income, output, inventory
or satisfaction. No historical mechanism is simulated here.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import polars as pl

from hsm_lab.contract.guards import BASELINE_FILENAME, verify_baseline
from hsm_lab.contract.schemas import (
    OutputPolicy,
    ResearchContract,
    ResearchGateError,
    ScenarioSpec,
)
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.rng import RNG_SCHEME_VERSION, RngRegistry
from hsm_lab.provenance.manifest import (
    RunManifest,
    finalize_manifest,
    hash_output_tree,
    manifest_preamble,
    write_manifest_atomic,
)
from hsm_lab.storage.output import (
    AGGREGATE_COLUMNS,
    MicroWriter,
    write_aggregates,
    write_duckdb,
    write_summary,
)

HOUSEHOLD_MODULE = "smoke.households"
ENTERPRISE_MODULE = "smoke.enterprises"
TICK_EVENT = "synthetic_tick_completed"


def replay_digest(
    spec: ScenarioSpec,
    household_probes: np.ndarray,
    enterprise_probes: np.ndarray,
    quarters: list[str],
    rng_scheme_version: str,
) -> str:
    """Digest over fixed dtype/byte-order/shape probe results + tick sequence.

    Excludes run_id, timestamps, output paths, performance numbers, git state
    and Parquet/DuckDB bytes: identical seed + config in one locked
    environment must reproduce it bit-for-bit (no cross-platform claim).
    """
    from hsm_lab.provenance.manifest import canonical_json

    header = {
        "array_dtype": "float64",
        "byte_order": "little",
        "memory_order": "C",
        "commodity_ids": list(spec.commodities),
        "households_shape": [int(dim) for dim in household_probes.shape],
        "enterprises_shape": [int(dim) for dim in enterprise_probes.shape],
        "quarters": quarters,
        "rng_scheme": rng_scheme_version,
        "seed": spec.seed,
        "stochastic": spec.stochastic,
    }
    digest = hashlib.sha256()
    digest.update(canonical_json(header))
    digest.update(np.ascontiguousarray(household_probes, dtype="<f8").tobytes(order="C"))
    digest.update(np.ascontiguousarray(enterprise_probes, dtype="<f8").tobytes(order="C"))
    return digest.hexdigest()


def _aggregate_tick(
    actor_kind: str,
    tick: int,
    quarter: str,
    region_index: np.ndarray,
    weights: np.ndarray,
    probes: np.ndarray,
    region_ids: list[str],
    commodity_ids: list[str],
) -> list[dict[str, Any]]:
    n_regions = len(region_ids)
    counts = np.bincount(region_index, minlength=n_regions)
    weight_sums = np.bincount(region_index, weights=weights, minlength=n_regions)
    rows: list[dict[str, Any]] = []
    for commodity_index, commodity_id in enumerate(commodity_ids):
        probe_sums = np.bincount(
            region_index, weights=probes[:, commodity_index], minlength=n_regions
        )
        for region_index_value in range(n_regions):
            count = int(counts[region_index_value])
            rows.append(
                {
                    "tick": tick,
                    "quarter": quarter,
                    "actor_kind": actor_kind,
                    "region_id": region_ids[region_index_value],
                    "commodity_id": commodity_id,
                    "count": count,
                    "weight_sum": float(weight_sums[region_index_value]),
                    "probe_sum": float(probe_sums[region_index_value]),
                    "probe_mean": (
                        float(probe_sums[region_index_value] / count) if count else None
                    ),
                }
            )
    return rows


def _probe_stats(probes: np.ndarray) -> dict[str, float]:
    return {
        "min": float(probes.min()),
        "max": float(probes.max()),
        "mean": float(probes.mean()),
        "std": float(probes.std()),
    }


def run_smoke(
    spec: ScenarioSpec,
    output_dir: Path,
    contract: ResearchContract,
    registry: DataRegistry,
) -> RunManifest:
    """Run the synthetic smoke workload into a fresh ``output_dir``."""
    root = registry.root
    baseline_hash = verify_baseline(root / BASELINE_FILENAME, contract)
    spec.validate_for_run(contract)
    if output_dir.exists() or output_dir.is_symlink():
        raise ResearchGateError(
            f"output directory {output_dir} already exists; refusing to overwrite any "
            "previous run"
        )

    run_id = uuid4().hex
    running = manifest_preamble(
        run_id=run_id,
        spec=spec,
        contract=contract,
        root=root,
        baseline_hash=baseline_hash,
    )
    output_dir.mkdir(parents=True)
    write_manifest_atomic(output_dir, running)

    rng = RngRegistry(spec.seed) if spec.stochastic else None
    n_regions = len(spec.region_ids)
    n_commodities = len(spec.commodities)
    household_ids = np.arange(spec.households, dtype=np.int64)
    enterprise_ids = np.arange(spec.enterprises, dtype=np.int64)
    household_region = household_ids % n_regions
    enterprise_region = enterprise_ids % n_regions
    household_weights = np.ones(spec.households, dtype=np.float64)
    enterprise_weights = np.ones(spec.enterprises, dtype=np.float64)
    household_probes = np.zeros((spec.households, n_commodities), dtype=np.float64)
    enterprise_probes = np.zeros((spec.enterprises, n_commodities), dtype=np.float64)

    aggregate_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    compute_s = 0.0
    aggregate_s = 0.0
    household_writer = (
        MicroWriter(output_dir / "households.parquet")
        if spec.output_policy is OutputPolicy.RESEARCH_FULL
        else None
    )
    enterprise_writer = (
        MicroWriter(output_dir / "enterprises.parquet")
        if spec.output_policy is OutputPolicy.RESEARCH_FULL
        else None
    )

    try:
        for tick in range(spec.ticks):
            quarter = spec.start.advance(tick)
            started = time.perf_counter()
            if rng is not None:
                household_probes += rng.uniform(
                    HOUSEHOLD_MODULE, (spec.households, n_commodities)
                )
                enterprise_probes += rng.uniform(
                    ENTERPRISE_MODULE, (spec.enterprises, n_commodities)
                )
            else:
                household_probes += 1.0
                enterprise_probes += 1.0
            compute_s += time.perf_counter() - started

            started = time.perf_counter()
            aggregate_rows.extend(
                _aggregate_tick(
                    "households",
                    tick,
                    str(quarter),
                    household_region,
                    household_weights,
                    household_probes,
                    spec.region_ids,
                    spec.commodities,
                )
            )
            aggregate_rows.extend(
                _aggregate_tick(
                    "enterprises",
                    tick,
                    str(quarter),
                    enterprise_region,
                    enterprise_weights,
                    enterprise_probes,
                    spec.region_ids,
                    spec.commodities,
                )
            )
            aggregate_s += time.perf_counter() - started
            event_rows.append(
                {"tick": tick, "quarter": str(quarter), "event": TICK_EVENT}
            )
            if household_writer is not None and enterprise_writer is not None:
                household_writer.write_tick(
                    tick,
                    str(quarter),
                    household_ids,
                    household_region,
                    spec.region_ids,
                    spec.commodities,
                    household_weights,
                    household_probes,
                )
                enterprise_writer.write_tick(
                    tick,
                    str(quarter),
                    enterprise_ids,
                    enterprise_region,
                    spec.region_ids,
                    spec.commodities,
                    enterprise_weights,
                    enterprise_probes,
                )

        io_started = time.perf_counter()
        if household_writer is not None:
            household_writer.close()
        if enterprise_writer is not None:
            enterprise_writer.close()
        aggregates_frame = pl.DataFrame(aggregate_rows).cast(
            {"tick": pl.Int64, "count": pl.Int64}
        )
        aggregates_frame = aggregates_frame.select(AGGREGATE_COLUMNS)
        events_frame = pl.DataFrame(event_rows).cast({"tick": pl.Int64})
        write_aggregates(aggregates_frame, output_dir)
        micro_paths: dict[str, Path] = {}
        if spec.output_policy is OutputPolicy.RESEARCH_FULL:
            micro_paths = {
                "households_micro": output_dir / "households.parquet",
                "enterprises_micro": output_dir / "enterprises.parquet",
            }
        write_duckdb(output_dir, aggregates_frame, events_frame, micro_paths)

        quarters = [str(spec.start.advance(tick)) for tick in range(spec.ticks)]
        digest = replay_digest(
            spec,
            household_probes,
            enterprise_probes,
            quarters,
            RNG_SCHEME_VERSION,
        )
        draws_by_module = rng.draws_by_module() if rng is not None else {}
        draws_count = sum(draws_by_module.values())
        modules_active = [m for m, c in draws_by_module.items() if c > 0]
        stochastic_replicates_valid = bool(spec.stochastic and draws_count > 0)
        summary: dict[str, Any] = {
            "schema_version": "1",
            "run_id": run_id,
            "run_kind": "synthetic_engine_smoke",
            "political_mode": None,
            "scenario_id": spec.scenario_id,
            "seed": spec.seed,
            "stochastic": spec.stochastic,
            "output_policy": spec.output_policy.value,
            "start_quarter": quarters[0],
            "end_quarter": quarters[-1],
            "ticks": spec.ticks,
            "households": spec.households,
            "enterprises": spec.enterprises,
            "commodity_ids": list(spec.commodities),
            "region_ids": list(spec.region_ids),
            "parameter_vector": {},
            "rng": {
                "scheme_version": RNG_SCHEME_VERSION,
                "draws_count": draws_count,
                "draws_by_module": draws_by_module,
                "modules_active": modules_active,
                "stochastic_replicates_valid": stochastic_replicates_valid,
            },
            "deterministic_replay_digest": digest,
            "global_probe_stats": {
                "households": _probe_stats(household_probes),
                "enterprises": _probe_stats(enterprise_probes),
            },
            "final_tick_aggregates": [
                row for row in aggregate_rows if row["tick"] == spec.ticks - 1
            ],
            "row_counts": {
                "aggregates": aggregates_frame.height,
                "events": events_frame.height,
                "households_micro": (
                    spec.households * n_commodities * spec.ticks
                    if household_writer is not None
                    else None
                ),
                "enterprises_micro": (
                    spec.enterprises * n_commodities * spec.ticks
                    if enterprise_writer is not None
                    else None
                ),
            },
            "weights": {
                "household_weights_all_one": bool(
                    np.array_equal(household_weights, np.ones_like(household_weights))
                ),
                "enterprise_weights_all_one": bool(
                    np.array_equal(enterprise_weights, np.ones_like(enterprise_weights))
                ),
            },
            "mechanism_diagnostics": {},
            "mechanism_note": (
                "P00 runs no economic, political or household mechanisms; probe values "
                "are synthetic workload quantities, not historical magnitudes."
            ),
            "research_warnings": list(contract.research_warnings),
            "performance": {
                "compute_wall_s": compute_s,
                "aggregate_wall_s": aggregate_s,
                "io_wall_s": time.perf_counter() - io_started,
            },
        }
        if not spec.stochastic:
            summary["deterministic_mode"] = {
                "warning": "deterministic_no_replicates",
                "note": "zero RNG draws: this run is not a stochastic replicate",
            }
        write_summary(summary, output_dir)
        hashes = hash_output_tree(output_dir)
        final = finalize_manifest(
            running,
            status="completed",
            output_hashes=hashes,
            rng_draws_count=draws_count,
            rng_draws_by_module=draws_by_module,
            stochastic_modules_active=modules_active,
            deterministic_replay_digest=digest,
        )
        write_manifest_atomic(output_dir, final)
        return final
    except Exception as exc:  # noqa: BLE001 - record evidence, then re-raise
        for writer in (household_writer, enterprise_writer):
            if writer is not None:
                try:
                    writer.close()
                except Exception:  # noqa: BLE001  # pragma: no cover - best effort
                    pass
        # Report the RNG state actually reached before the failure - never a
        # fabricated zero - and leave the replay digest absent rather than
        # inventing a completed result.
        draws_by_module = rng.draws_by_module() if rng is not None else {}
        failed = finalize_manifest(
            running,
            status="failed",
            output_hashes={},
            rng_draws_count=sum(draws_by_module.values()),
            rng_draws_by_module=draws_by_module,
            stochastic_modules_active=[
                module for module, count in draws_by_module.items() if count > 0
            ],
            deterministic_replay_digest="",
            failure_message=f"{type(exc).__name__}: {exc}",
        )
        try:
            write_manifest_atomic(output_dir, failed)
        except OSError:  # pragma: no cover - evidence already lost
            pass
        raise
