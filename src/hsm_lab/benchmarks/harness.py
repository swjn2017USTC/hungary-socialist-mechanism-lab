"""Benchmark harness: isolated subprocess workers, RSS/wall/CPU evidence.

This module's import surface is stdlib-only so that worker processes can pin
BLAS/Polars thread counts *before* numpy/polars load. P00 workers run the
same ``run_smoke`` synthetic workload as the CLI; the P02 ``material`` kind
runs the real Intermediate-8 economic path (plan section 9 cases). Parent
runs workers sequentially (workers=1), no thread pools.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Literal

THREAD_ENV_KEYS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "POLARS_MAX_THREADS",
)
NORMAL_PEAK_RSS_BYTES = 16_000_000_000
HARD_PEAK_RSS_BYTES = 22_000_000_000
WORKER_TIMEOUT_S = 1200.0
MATERIAL_WALL_GATE_S = 30.0
MATERIAL_CHECKPOINT_WALL_GATE_S = 45.0
MATERIAL_MAX_SCALING_RATIO = 3.5
# The F1 acceptance case: 5000 households / 200 organizations / 116 ticks,
# no checkpoints (plan section 9).
F1_CASE = (5000, 200, 116)

SCALING_CASES: tuple[tuple[int, int], ...] = (
    (1000, 50),
    (5000, 100),
    (10000, 200),
    (20000, 300),
    (30000, 300),
    (50000, 500),
)
SCALING_TICKS = (10, 116)

_BENCHMARK_NOTES = (
    "workload=synthetic_array_rng_aggregation_storage: probe arrays, RNG draws, "
    "region x commodity aggregation and Parquet/DuckDB output only",
    "not an F2 historical-model benchmark; no economic mechanism executes here",
    "repeats are timing repetitions of one fixed seed, not stochastic replicates",
    "peak RSS is the worker process high-water mark (includes imports), not the "
    "parent's RSS and not an end-of-run snapshot",
)

_ORGANIZATION_PROFILES: dict[int, Literal["p02_100", "p02_200", "p02_400"]] = {
    100: "p02_100",
    200: "p02_200",
    400: "p02_400",
}
_F2_ORGANIZATION_PROFILES: dict[int, str] = {
    300: "p05_300",
    400: "p05_400",
    450: "p05_450",
}


def _load_config(root: Path, kind: str) -> dict[str, Any]:
    name = {"material": "material", "f2": "f2"}.get(kind, "p00")
    path = root / "config" / "benchmarks" / f"{name}.json"
    if not path.is_file():
        raise RuntimeError(f"benchmark config not found: {path}")
    config: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "1":
        raise ValueError("benchmark config schema_version must be '1'")
    if config.get("workers") != 1:
        raise ValueError("benchmark runs one worker; workers must be 1")
    if config.get("regions") != 20:
        raise ValueError("benchmark config regions must be 20")
    if kind == "material":
        if len(config.get("commodities", [])) != 8:
            raise ValueError(
                "material benchmark config must carry the eight Intermediate-8 "
                "commodity ids"
            )
        cases = config.get("cases")
        if not isinstance(cases, list) or not cases:
            raise ValueError("material benchmark config must carry a cases list")
        for case in cases:
            for key in ("households", "organizations", "ticks"):
                if not isinstance(case.get(key), int) or case[key] <= 0:
                    raise ValueError(f"material case missing integer {key}: {case}")
            if case["organizations"] not in _ORGANIZATION_PROFILES:
                raise ValueError(
                    f"material case organizations must be 100/200/400: {case}"
                )
    elif kind == "f2":
        if len(config.get("commodities", [])) != 16:
            raise ValueError("f2 benchmark config must carry the sixteen F2 commodity ids")
        cases = config.get("cases")
        if not isinstance(cases, list) or not cases:
            raise ValueError("f2 benchmark config must carry a cases list")
        for case in cases:
            for key in ("households", "organizations", "ticks"):
                if not isinstance(case.get(key), int) or case[key] <= 0:
                    raise ValueError(f"f2 case missing integer {key}: {case}")
            if case["organizations"] not in _F2_ORGANIZATION_PROFILES:
                raise ValueError(
                    f"f2 case organizations must be 300/400/450: {case}"
                )
    else:
        if len(config.get("commodities", [])) != 4:
            raise ValueError("benchmark config must carry the four Toy-4 commodity ids")
    if not isinstance(config.get("seed"), int) or config["seed"] < 0:
        raise ValueError("benchmark seed must be a non-negative integer")
    return config


def _case_definitions(kind: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    seed = config["seed"]
    cases: list[dict[str, Any]] = []
    if kind == "smoke":
        for policy in ("ensemble_compact", "research_full"):
            cases.append(
                {
                    "case_id": f"smoke_{policy}",
                    "kind": "smoke",
                    "policy": policy,
                    "households": 1000,
                    "enterprises": 50,
                    "ticks": 10,
                    "seed": seed,
                }
            )
    elif kind == "material":
        for case in config["cases"]:
            households = int(case["households"])
            organizations = int(case["organizations"])
            ticks = int(case["ticks"])
            checkpoint_every = int(case.get("checkpoint_every", 0))
            case_id = f"material_n{households}_o{organizations}_t{ticks}"
            if checkpoint_every:
                case_id += f"_ckpt{checkpoint_every}"
            cases.append(
                {
                    "case_id": case_id,
                    "kind": "material",
                    "policy": "ensemble_compact",
                    "households": households,
                    "organizations": organizations,
                    "ticks": ticks,
                    "seed": seed,
                    "checkpoint_every": checkpoint_every,
                }
            )
    elif kind == "f2":
        for case in config["cases"]:
            households = int(case["households"])
            organizations = int(case["organizations"])
            ticks = int(case["ticks"])
            checkpoint_every = int(case.get("checkpoint_every", 0))
            retention = str(case.get("retention", "trajectory"))
            policy = str(case.get("output_policy", "ensemble_compact"))
            case_id = f"f2_n{households}_o{organizations}_t{ticks}_{retention}"
            if checkpoint_every:
                case_id += f"_ckpt{checkpoint_every}"
            cases.append(
                {
                    "case_id": case_id,
                    "kind": "f2",
                    "policy": policy,
                    "retention": retention,
                    "households": households,
                    "organizations": organizations,
                    "ticks": ticks,
                    "seed": seed,
                    "checkpoint_every": checkpoint_every,
                }
            )
    else:
        for households, enterprises in SCALING_CASES:
            for ticks in SCALING_TICKS:
                cases.append(
                    {
                        "case_id": f"scale_n{households}_t{ticks}",
                        "kind": "scaling",
                        "policy": "ensemble_compact",
                        "households": households,
                        "enterprises": enterprises,
                        "ticks": ticks,
                        "seed": seed,
                    }
                )
    return cases


def _worker_main(case_path: Path, output_dir: Path) -> int:
    for key in THREAD_ENV_KEYS:
        os.environ[key] = "1"
    import resource

    case = json.loads(case_path.read_text(encoding="utf-8"))
    from hsm_lab.cli.app import _repo_root  # noqa: PLC2701 - worker shares CLI root rules
    from hsm_lab.contract.guards import load_research_contract, load_scenario
    from hsm_lab.contract.material import OrganizationRecipe
    from hsm_lab.contract.schemas import OutputPolicy, ScenarioSpec
    from hsm_lab.data.registry import DataRegistry

    root = _repo_root()
    contract = load_research_contract(root)
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    if case.get("kind") in ("material", "f2"):
        from hsm_lab.engine.material import run_material

        scenario_id = "historical_f2_replay" if case["kind"] == "f2" else "intermediate8"
        base = load_scenario(root, scenario_id)
        if base.organization_recipe is None or base.organization_recipe.overrides:
            raise RuntimeError(
                "material benchmark requires the stock organization profile "
                "(no overrides) so the count switch is exact"
            )
        profiles = (
            _F2_ORGANIZATION_PROFILES
            if case["kind"] == "f2"
            else _ORGANIZATION_PROFILES
        )
        profile = profiles[int(case["organizations"])]
        spec = ScenarioSpec.model_validate(
            base.model_copy(
                update={
                    "households": case["households"],
                    "organizations": case["organizations"],
                    "organization_recipe": OrganizationRecipe(
                        profile=profile, overrides=[]
                    ),
                    "ticks": case["ticks"],
                    "seed": case["seed"],
                    "output_policy": OutputPolicy(case["policy"]),
                }
            )
            .model_dump()
        )
        registry = DataRegistry.load(root, allowed_commodities=spec.commodities)
        manifest = run_material(
            spec,
            output_dir,
            contract,
            registry,
            checkpoint_every=int(case.get("checkpoint_every", 0)),
        )
    else:
        from hsm_lab.engine.smoke import run_smoke

        spec = load_scenario(root, "smoke").model_copy(
            update={
                "households": case["households"],
                "enterprises": case["enterprises"],
                "ticks": case["ticks"],
                "seed": case["seed"],
                "output_policy": OutputPolicy(case["policy"]),
            }
        )
        registry = DataRegistry.load(root)
        manifest = run_smoke(spec, output_dir, contract, registry)
    wall_s = time.perf_counter() - started_wall
    cpu_s = time.process_time() - started_cpu
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_bytes = rss if sys.platform == "darwin" else rss * 1024
    sizes = {
        entry.relative_to(output_dir).as_posix(): entry.stat().st_size
        for entry in sorted(output_dir.rglob("*"))
        if entry.is_file()
    }
    checkpoint_bytes = sum(
        size for name, size in sizes.items() if name.startswith("checkpoints/")
    )
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    result = {
        "status": "ok",
        "case_id": case["case_id"],
        "wall_s": wall_s,
        "cpu_s": cpu_s,
        "peak_rss_bytes": peak_rss_bytes,
        "rss_source": "resource.getrusage(RUSAGE_SELF).ru_maxrss",
        "rss_units": "bytes (darwin native; linux x1024)",
        "pid": os.getpid(),
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "machine": os.uname().machine,
        "thread_env": {key: os.environ[key] for key in THREAD_ENV_KEYS},
        "duckdb_threads": 1,
        "output_file_sizes": sizes,
        "duckdb_bytes": sizes.get("trajectory.duckdb", 0),
        "parquet_bytes": sum(size for name, size in sizes.items() if name.endswith(".parquet")),
        "checkpoint_bytes": checkpoint_bytes,
        "total_output_bytes": sum(sizes.values()),
        "manifest": {
            "run_id": manifest.run_id,
            "status": manifest.status,
            "rng_draws_count": manifest.rng_draws_count,
            "deterministic_replay_digest": manifest.deterministic_replay_digest,
            "output_hashes": manifest.output_hashes,
        },
        "performance": summary["performance"],
        "row_counts": summary["row_counts"],
        "events_written": summary["row_counts"]["events"],
    }
    if case.get("kind") == "material":
        result["invariants"] = summary.get("invariants", {})
        result["dimensions"] = summary.get("dimensions", {})
        result["phase_times"] = {
            key: value
            for key, value in (summary.get("performance") or {}).items()
            if key.endswith("_wall_s")
        }
    print(json.dumps(result, sort_keys=True))
    return 0


def _run_measurement(
    case: dict[str, Any], root: Path, run_dir: Path, case_path: Path
) -> dict[str, Any]:
    env = {**os.environ, **{key: "1" for key in THREAD_ENV_KEYS}}
    started = time.perf_counter()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "hsm_lab.benchmarks.harness",
            "--worker",
            str(case_path),
            "--output-dir",
            str(run_dir),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=WORKER_TIMEOUT_S,
    )
    elapsed = time.perf_counter() - started
    if proc.returncode != 0:
        return {
            "status": "error",
            "case_id": case["case_id"],
            "returncode": proc.returncode,
            "stderr_tail": proc.stderr[-2000:],
            "worker_elapsed_s": elapsed,
        }
    lines = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    result: dict[str, Any] = json.loads(lines[-1])
    result["worker_elapsed_s"] = elapsed
    return result


def _case_report(case: dict[str, Any], measurements: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [m for m in measurements if m.get("status") == "ok"]
    walls = [m["wall_s"] for m in ok]
    cpus = [m["cpu_s"] for m in ok]
    peaks = [m["peak_rss_bytes"] for m in ok]
    peak = max(peaks) if peaks else 0
    performance_keys = ("compute_wall_s", "aggregate_wall_s")
    compute_agg = [
        sum(float(m["performance"].get(key, 0.0)) for key in performance_keys)
        for m in ok
    ]
    ticks = case["ticks"]
    median_wall = statistics.median(walls) if walls else None
    report: dict[str, Any] = {
        "case_id": case["case_id"],
        "output_policy": case["policy"],
        "ticks": ticks,
        "seed": case["seed"],
        "workers": 1,
        "repeats": measurements,
        "repeat_count": len(measurements),
        "failed_repeats": len(measurements) - len(ok),
        "median_wall_s": median_wall,
        "median_cpu_s": statistics.median(cpus) if cpus else None,
        "median_worker_elapsed_s": (
            statistics.median([m["worker_elapsed_s"] for m in ok]) if ok else None
        ),
        "max_peak_rss_bytes": peak,
        "peak_rss_gb": peak / 1e9,
        "peak_rss_gib": peak / (1024**3),
        "events_written": ticks,
        "events_per_second": (ticks / median_wall if median_wall and median_wall > 0 else None),
        "compute_aggregate_median_s": statistics.median(compute_agg) if compute_agg else None,
        "duckdb_bytes": max((m["duckdb_bytes"] for m in ok), default=0),
        "parquet_bytes": max((m["parquet_bytes"] for m in ok), default=0),
        "checkpoint_bytes": max((m.get("checkpoint_bytes", 0) for m in ok), default=0),
        "checkpoint_wall_s": (
            statistics.median(
                [float(m["performance"].get("checkpoint_wall_s", 0.0)) for m in ok]
            )
            if ok
            else None
        ),
        "total_output_bytes": max((m["total_output_bytes"] for m in ok), default=0),
        "rng_draws_count": ok[0]["manifest"]["rng_draws_count"] if ok else None,
        "deterministic_replay_digest": (
            ok[0]["manifest"]["deterministic_replay_digest"] if ok else None
        ),
        "output_hashes": ok[0]["manifest"]["output_hashes"] if ok else {},
        "gates": {
            "peak_rss_ok": peak <= HARD_PEAK_RSS_BYTES,
            "peak_rss_warning": peak > NORMAL_PEAK_RSS_BYTES,
            "all_repeats_ok": len(ok) == len(measurements),
            "measurement_too_short": bool(
                compute_agg and statistics.median(compute_agg) < 0.05
            ),
        },
    }
    if case.get("kind") == "smoke":
        report["households"] = case["households"]
        report["enterprises"] = case["enterprises"]
        scalar_updates = (case["households"] + case["enterprises"]) * 4 * ticks
        report["scalar_updates"] = scalar_updates
        report["updates_per_second"] = (
            scalar_updates / median_wall if median_wall and median_wall > 0 else None
        )
    elif case.get("kind") in ("material", "f2"):
        report["households"] = case["households"]
        report["organizations"] = case["organizations"]
        dimensions = ok[0].get("dimensions") if ok else {}
        report["dimensions"] = dimensions or None
        report["phase_times"] = ok[0].get("phase_times") if ok else None
        if dimensions:
            n = case["households"]
            report["effective_scalar_updates"] = ticks * (
                8 * n
                + int(dimensions.get("K", 0))
                + int(dimensions.get("D", 0))
                + int(dimensions.get("M", 0))
                + int(dimensions.get("S", 0))
            )
            report["updates_per_second"] = (
                report["effective_scalar_updates"] / median_wall
                if median_wall and median_wall > 0
                else None
            )
        else:
            report["effective_scalar_updates"] = None
            report["updates_per_second"] = None
        digests = {m["manifest"]["deterministic_replay_digest"] for m in ok}
        report["gates"]["digest_stable"] = len(digests) == 1
        invariants = ok[0].get("invariants") if ok else None
        if invariants:
            ratios = [
                max(
                    float(m.get("invariants", {}).get("max_material_tolerance_ratio", 0.0)),
                    float(m.get("invariants", {}).get("max_finance_tolerance_ratio", 0.0)),
                )
                for m in ok
            ]
            max_ratio = max(ratios) if ratios else None
            report["invariant_max_tolerance_ratio"] = max_ratio
            report["gates"]["invariants_ok"] = max_ratio is not None and max_ratio <= 1.0
        else:
            report["gates"]["invariants_ok"] = None
        if not case.get("checkpoint_every") and ticks == F1_CASE[2]:
            report["gates"]["wall_s_ok"] = bool(
                median_wall is not None and median_wall <= MATERIAL_WALL_GATE_S
            )
        if case.get("checkpoint_every"):
            report["gates"]["checkpoint_wall_s_ok"] = bool(
                median_wall is not None
                and median_wall <= MATERIAL_CHECKPOINT_WALL_GATE_S
            )
    else:
        report["households"] = case["households"]
        report["enterprises"] = case["enterprises"]
        scalar_updates = (case["households"] + case["enterprises"]) * 4 * ticks
        report["scalar_updates"] = scalar_updates
        report["updates_per_second"] = (
            scalar_updates / median_wall if median_wall and median_wall > 0 else None
        )
    required = ["peak_rss_ok", "all_repeats_ok"]
    if case.get("kind") in ("material", "f2"):
        required.append("digest_stable")
        if ok and ok[0].get("invariants"):
            required.append("invariants_ok")
        f1_match = (case["households"], case["organizations"], case["ticks"]) == F1_CASE
        if case.get("kind") == "f2":
            f1_match = case["households"] == F1_CASE[0] and case["ticks"] == F1_CASE[2]
        if not case.get("checkpoint_every") and f1_match:
            required.append("wall_s_ok")
        if case.get("checkpoint_every"):
            required.append("checkpoint_wall_s_ok")
    report["status"] = "pass" if all(report["gates"][key] for key in required) else "fail"
    return report


def _scaling_ratio(
    case_reports: list[dict[str, Any]],
    ticks: int,
    small_n: int = 10000,
    large_n: int = 20000,
) -> dict[str, Any] | None:
    def find(households: int) -> dict[str, Any] | None:
        for report in case_reports:
            if (
                report["households"] == households
                and report["ticks"] == ticks
                and report["compute_aggregate_median_s"]
            ):
                return report
        return None

    small, large = find(small_n), find(large_n)
    if small is None or large is None:
        return None
    ratio = large["compute_aggregate_median_s"] / small["compute_aggregate_median_s"]
    return {
        "base": f"n{small_n}_vs_n{large_n}",
        "ticks": ticks,
        "compute_aggregate_ratio": ratio,
        "needs_profile": ratio >= 3.5,
        "threshold": 3.5,
        "unavailable": False,
    }


def _material_axis_ratio(
    case_reports: list[dict[str, Any]],
    *,
    axis: str,
    small: dict[str, int],
    large: dict[str, int],
    threshold: float,
) -> dict[str, Any] | None:
    """Median wall-clock doubling ratio on one axis (plan section 9)."""

    def find(selection: dict[str, int]) -> dict[str, Any] | None:
        for report in case_reports:
            if report.get("ticks") != 116 or report.get("checkpoint_bytes"):
                continue
            if all(report.get(key) == value for key, value in selection.items()):
                return report
        return None

    low, high = find(small), find(large)
    if low is None or high is None:
        return None
    if not low.get("median_wall_s") or not high.get("median_wall_s"):
        return {
            "axis": axis,
            "small": small,
            "large": large,
            "median_wall_ratio": None,
            "unavailable": True,
            "threshold": threshold,
        }
    ratio = high["median_wall_s"] / low["median_wall_s"]
    return {
        "axis": axis,
        "small": small,
        "large": large,
        "median_wall_ratio": ratio,
        "unavailable": False,
        "threshold": threshold,
        "needs_profile": ratio > threshold,
    }


def run_benchmark(kind: str, root: Path, output_root: Path) -> dict[str, Any]:
    """Run all cases of ``kind``; write benchmark.json + summary.md; return report."""
    if kind not in ("smoke", "scaling", "material", "f2"):
        raise ValueError(f"unknown benchmark kind {kind!r}")
    config = _load_config(root, kind)
    cases = _case_definitions(kind, config)
    output_root.mkdir(parents=True)
    case_dir = output_root / "cases"
    case_dir.mkdir()
    warmups = config.get("warmups", 1)
    repeats = config.get("repeats", 3)

    case_reports: list[dict[str, Any]] = []
    for case in cases:
        case_path = case_dir / f"{case['case_id']}.json"
        case_path.write_text(json.dumps(case, sort_keys=True) + "\n", encoding="utf-8")
        measurements: list[dict[str, Any]] = []
        runs_root = output_root / "runs" / case["case_id"]
        runs_root.mkdir(parents=True)
        for index in range(warmups):
            measurements.append(
                {
                    "excluded": True,
                    "label": f"warmup-{index}",
                    **_run_measurement(
                        case, root, runs_root / f"warmup-{index}", case_path
                    ),
                }
            )
        for index in range(repeats):
            measurements.append(
                {
                    "excluded": False,
                    "label": f"repeat-{index}",
                    **_run_measurement(case, root, runs_root / f"repeat-{index}", case_path),
                }
            )
        case_reports.append(
            _case_report(case, [m for m in measurements if not m["excluded"]])
        )
        case_reports[-1]["warmups"] = [m for m in measurements if m["excluded"]]

    workload = {
        "material": "intermediate8_material_economy_kernel_storage",
        "f2": "f2_historical_material_economy_kernel_storage",
    }.get(kind, "synthetic_array_rng_aggregation_storage")
    base_notes = (
        list(_BENCHMARK_NOTES)
        if kind != "material"
        else [
            "repeats are timing repetitions of one fixed seed, not stochastic replicates",
            "peak RSS is the worker process high-water mark (includes imports), not the "
            "parent's RSS and not an end-of-run snapshot",
        ]
    )
    report: dict[str, Any] = {
        "schema_version": "1",
        "benchmark_kind": kind,
        "workload": workload,
        "config": config,
        "thread_policy": {key: "1" for key in THREAD_ENV_KEYS} | {"duckdb_threads": 1},
        "resource_gates": {
            "normal_peak_rss_bytes": NORMAL_PEAK_RSS_BYTES,
            "hard_peak_rss_bytes": HARD_PEAK_RSS_BYTES,
            "note": "decimal GB gates; report shows bytes, GB and GiB",
        },
        "cases": case_reports,
        "notes": base_notes,
    }
    if kind in ("material", "f2"):
        report["notes"] = report["notes"] + [
            "material workload executes the real Intermediate-8 economic path: "
            "preflight, kernel ticks, gates, digest and compact storage",
            "effective scalar updates = T*(8N+K+D+M+S) (households x 8 commodities "
            "plus network cell/edge/demand dimensions), an engineering throughput "
            "measure, not an instruction count",
            "pause/resume replay evidence lives in the acceptance verification "
            "driver, not in this timing benchmark",
        ]
        household_axis = config.get("scaling_household_axis")
        org_axis = config.get("scaling_organization_axis")
        threshold = float(config.get("max_scaling_ratio", MATERIAL_MAX_SCALING_RATIO))
        ratios: list[dict[str, Any]] = []
        if isinstance(household_axis, list) and len(household_axis) == 2:
            ns, org = household_axis
            for small_n, large_n in zip(ns, ns[1:], strict=False):
                ratio = _material_axis_ratio(
                    case_reports,
                    axis=f"households_{small_n}_to_{large_n}_org{org}",
                    small={"households": small_n, "organizations": org},
                    large={"households": large_n, "organizations": org},
                    threshold=threshold,
                )
                if ratio is not None:
                    ratios.append(ratio)
        if isinstance(org_axis, list) and len(org_axis) == 2:
            n, orgs = org_axis
            for small_o, large_o in zip(orgs, orgs[1:], strict=False):
                ratio = _material_axis_ratio(
                    case_reports,
                    axis=f"organizations_{small_o}_to_{large_o}_n{n}",
                    small={"households": n, "organizations": small_o},
                    large={"households": n, "organizations": large_o},
                    threshold=threshold,
                )
                if ratio is not None:
                    ratios.append(ratio)
        report["scaling_ratios"] = ratios
        report["scaling_ratio_gate_s"] = config.get("wall_gate_s", MATERIAL_WALL_GATE_S)
        ckpt = next(
            (case for case in case_reports if case.get("checkpoint_bytes")), None
        )
        base = next(
            (
                case
                for case in case_reports
                if (
                    case.get("households"),
                    case.get("organizations"),
                    case.get("ticks"),
                )
                == F1_CASE
                and not case.get("checkpoint_bytes")
            ),
            None,
        )
        if ckpt is not None and base is not None and base["median_wall_s"]:
            report["checkpoint_overhead"] = {
                "wall_ratio_vs_f1": ckpt["median_wall_s"] / base["median_wall_s"],
                "checkpoint_bytes": ckpt["checkpoint_bytes"],
                "total_output_bytes": ckpt["total_output_bytes"],
                "max_peak_rss_bytes": ckpt["max_peak_rss_bytes"],
            }
    elif kind == "scaling":
        ratios = [
            ratio
            for ticks in SCALING_TICKS
            if (ratio := _scaling_ratio(case_reports, ticks)) is not None
        ]
        report["scaling_ratios"] = ratios
        if any(ratio["needs_profile"] for ratio in ratios):
            report["notes"] = report["notes"] + [
                "needs_profile: 10k->20k compute+aggregate ratio >= 3.5; profile before "
                "trusting linearity"
            ]
    report["overall_gate"] = (
        "pass" if all(case["status"] == "pass" for case in case_reports) else "fail"
    )
    if kind in ("material", "f2"):
        bad = [
            ratio
            for ratio in report["scaling_ratios"]
            if not ratio.get("unavailable")
            and ratio.get("median_wall_ratio") is not None
            and ratio["median_wall_ratio"] > ratio["threshold"]
        ]
        if bad:
            report["overall_gate"] = "fail"
            report["notes"] = report["notes"] + [
                "needs_profile: a doubling ratio exceeded "
                f"{bad[0]['threshold']}; profile the kernel hotspots before "
                "accepting P02"
            ]
    (output_root / "benchmark.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    title = {
        "material": "P02 material benchmark",
        "f2": "P05 F2 historical benchmark",
    }.get(kind, f"P00 benchmark: {kind}")
    workload_note = (
        "real economic loop (kernel + gates + compact storage)"
        if kind in ("material", "f2")
        else "synthetic probe load, not a historical model"
    )
    lines = [
        f"# {title}",
        "",
        f"- workload: {report['workload']} ({workload_note})",
        f"- overall gate: {report['overall_gate']}",
        "",
        "| case | policy | N | O | T | median wall s | median cpu s | peak RSS GiB | "
        "updates/s | events/s | status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    def format_measurement(value: Any, digits: int) -> str:
        return f"{value:.{digits}f}" if isinstance(value, (int, float)) else "unavailable"

    for case in case_reports:
        if kind in ("material", "f2"):
            scale = f"{case['households']} | {case['organizations']}"
        else:
            scale = f"{case['households']} | {case.get('enterprises', 0)}"
        lines.append(
            f"| {case['case_id']} | {case['output_policy']} | {scale} | "
            f"{case['ticks']} | "
            f"{format_measurement(case['median_wall_s'], 3)} | "
            f"{format_measurement(case['median_cpu_s'], 3)} | "
            f"{format_measurement(case['peak_rss_gib'], 3)} | "
            f"{case['updates_per_second'] or 0:,.0f} | "
            f"{case['events_per_second'] or 0:,.1f} | {case['status']} |"
        )
    (output_root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hsm_lab.benchmarks.harness")
    parser.add_argument("--worker", type=Path, help="worker mode: path to case JSON")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.worker is None:
        parser.error("direct invocation requires --worker (use the hsm CLI for benchmarks)")
    if args.output_dir is None:
        parser.error("--output-dir is required in worker mode")
    return _worker_main(args.worker, args.output_dir)


if __name__ == "__main__":
    sys.exit(main())
