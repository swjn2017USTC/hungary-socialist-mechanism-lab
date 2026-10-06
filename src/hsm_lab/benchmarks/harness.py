"""P00 benchmark harness: isolated subprocess workers, RSS/wall/CPU evidence.

This module's import surface is stdlib-only so that worker processes can pin
BLAS/Polars thread counts *before* numpy/polars load. Workers run the same
``run_smoke`` synthetic workload as the CLI; the benchmark measures an
engineering load (arrays + RNG + aggregation + storage), never a historical
F2 model. Parent runs workers sequentially (workers=1), no thread pools.
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
from typing import Any

THREAD_ENV_KEYS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "POLARS_MAX_THREADS",
)
NORMAL_PEAK_RSS_BYTES = 16_000_000_000
HARD_PEAK_RSS_BYTES = 22_000_000_000
WORKER_TIMEOUT_S = 1200.0

SCALING_CASES: tuple[tuple[int, int], ...] = (
    (1000, 50),
    (5000, 100),
    (10000, 200),
    (20000, 300),
    (30000, 300),
    (50000, 500),
)
SMOKE_TICKS = (10,)
SCALING_TICKS = (10, 116)

_BENCHMARK_NOTES = (
    "workload=synthetic_array_rng_aggregation_storage: probe arrays, RNG draws, "
    "region x commodity aggregation and Parquet/DuckDB output only",
    "not an F2 historical-model benchmark; no economic mechanism executes here",
    "repeats are timing repetitions of one fixed seed, not stochastic replicates",
    "peak RSS is the worker process high-water mark (includes imports), not the "
    "parent's RSS and not an end-of-run snapshot",
)


def _load_config(root: Path) -> dict[str, Any]:
    path = root / "config" / "benchmarks" / "p00.json"
    if not path.is_file():
        raise RuntimeError(f"benchmark config not found: {path}")
    config: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "1":
        raise ValueError("benchmark config schema_version must be '1'")
    if config.get("workers") != 1:
        raise ValueError("P00 benchmark runs one worker; workers must be 1")
    if config.get("regions") != 20:
        raise ValueError("benchmark config regions must be 20")
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
                    "policy": policy,
                    "households": 1000,
                    "enterprises": 50,
                    "ticks": 10,
                    "seed": seed,
                }
            )
    else:
        for households, enterprises in SCALING_CASES:
            for ticks in SCALING_TICKS:
                cases.append(
                    {
                        "case_id": f"scale_n{households}_t{ticks}",
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
    from hsm_lab.contract.schemas import OutputPolicy
    from hsm_lab.data.registry import DataRegistry
    from hsm_lab.engine.smoke import run_smoke

    root = _repo_root()
    contract = load_research_contract(root)
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
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    manifest = run_smoke(spec, output_dir, contract, registry)
    wall_s = time.perf_counter() - started_wall
    cpu_s = time.process_time() - started_cpu
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_bytes = rss if sys.platform == "darwin" else rss * 1024
    sizes = {
        entry.name: entry.stat().st_size for entry in sorted(output_dir.iterdir())
    }
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
    compute_agg = [
        m["performance"]["compute_wall_s"] + m["performance"]["aggregate_wall_s"] for m in ok
    ]
    households, enterprises, ticks = case["households"], case["enterprises"], case["ticks"]
    scalar_updates = (households + enterprises) * 4 * ticks
    median_wall = statistics.median(walls) if walls else None
    report: dict[str, Any] = {
        "case_id": case["case_id"],
        "output_policy": case["policy"],
        "households": households,
        "enterprises": enterprises,
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
        "scalar_updates": scalar_updates,
        "updates_per_second": (
            scalar_updates / median_wall if median_wall and median_wall > 0 else None
        ),
        "events_written": ticks,
        "events_per_second": (ticks / median_wall if median_wall and median_wall > 0 else None),
        "compute_aggregate_median_s": statistics.median(compute_agg) if compute_agg else None,
        "duckdb_bytes": max((m["duckdb_bytes"] for m in ok), default=0),
        "parquet_bytes": max((m["parquet_bytes"] for m in ok), default=0),
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
                compute_agg and statistics.median(compute_agg) < 0.1
            ),
        },
    }
    report["status"] = (
        "pass"
        if report["gates"]["peak_rss_ok"] and report["gates"]["all_repeats_ok"]
        else "fail"
    )
    return report


def _scaling_ratio(case_reports: list[dict[str, Any]], ticks: int) -> dict[str, Any] | None:
    def find(households: int) -> dict[str, Any] | None:
        for report in case_reports:
            if (
                report["households"] == households
                and report["ticks"] == ticks
                and report["compute_aggregate_median_s"]
            ):
                return report
        return None

    small, large = find(10000), find(20000)
    if small is None or large is None:
        return None
    ratio = large["compute_aggregate_median_s"] / small["compute_aggregate_median_s"]
    return {
        "base": "n10000_vs_n20000",
        "ticks": ticks,
        "compute_aggregate_ratio": ratio,
        "needs_profile": ratio >= 3.5,
        "threshold": 3.5,
    }


def run_benchmark(kind: str, root: Path, output_root: Path) -> dict[str, Any]:
    """Run all cases of ``kind``; write benchmark.json + summary.md; return report."""
    if kind not in ("smoke", "scaling"):
        raise ValueError(f"unknown benchmark kind {kind!r}")
    config = _load_config(root)
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

    report: dict[str, Any] = {
        "schema_version": "1",
        "benchmark_kind": kind,
        "workload": "synthetic_array_rng_aggregation_storage",
        "config": config,
        "thread_policy": {key: "1" for key in THREAD_ENV_KEYS} | {"duckdb_threads": 1},
        "resource_gates": {
            "normal_peak_rss_bytes": NORMAL_PEAK_RSS_BYTES,
            "hard_peak_rss_bytes": HARD_PEAK_RSS_BYTES,
            "note": "decimal GB gates; report shows bytes, GB and GiB",
        },
        "cases": case_reports,
        "notes": list(_BENCHMARK_NOTES),
    }
    if kind == "scaling":
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
    (output_root / "benchmark.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        f"# P00 benchmark: {kind}",
        "",
        f"- workload: {report['workload']} (synthetic probe load, not a historical model)",
        f"- overall gate: {report['overall_gate']}",
        "",
        "| case | policy | N | E | T | median wall s | median cpu s | peak RSS GiB | "
        "updates/s | events/s | status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for case in case_reports:
        lines.append(
            f"| {case['case_id']} | {case['output_policy']} | {case['households']} | "
            f"{case['enterprises']} | {case['ticks']} | "
            f"{case['median_wall_s']:.3f} | {case['median_cpu_s']:.3f} | "
            f"{case['peak_rss_gib']:.3f} | "
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
