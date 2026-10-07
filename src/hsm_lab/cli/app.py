"""Typer CLI surface. Business logic lives in testable functions.

Every command supports ``--json`` and prints exactly one JSON object on
stdout (human-readable logs go to stderr). Exit codes: 0 success,
1 environment/I/O/research-gate failure, 2 input/config validation failure.

The CLI reads config only from the current working directory (the repository
root); there is no --project-root and no multi-source config precedence.
"""

from __future__ import annotations

import json
import platform
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from shutil import rmtree
from typing import Any
from uuid import uuid4

import typer

from hsm_lab.contract.guards import (
    BASELINE_FILENAME,
    load_research_contract,
    load_scenario,
    verify_baseline,
)
from hsm_lab.contract.schemas import (
    ConfigError,
    OutputPolicy,
    ResearchGateError,
    ScenarioSpec,
)

app = typer.Typer(add_completion=False, no_args_is_help=True)
baseline_app = typer.Typer(add_completion=False, no_args_is_help=True)
data_app = typer.Typer(add_completion=False, no_args_is_help=True)
benchmark_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(baseline_app, name="baseline")
app.add_typer(data_app, name="data")
app.add_typer(benchmark_app, name="benchmark")


def _emit(payload: dict[str, Any], json_mode: bool, human: list[str]) -> None:
    if json_mode:
        print(json.dumps(payload, sort_keys=True))
    else:
        for line in human:
            print(line)
        if not human:
            print(json.dumps(payload, indent=2, sort_keys=True))


def _fail(exc: Exception, json_mode: bool) -> None:
    code = 2 if isinstance(exc, ConfigError) else 1
    payload = {
        "status": "error",
        "error": str(exc),
        "error_type": type(exc).__name__,
        "exit_code": code,
    }
    if json_mode:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"error[{type(exc).__name__}]: {exc}", file=sys.stderr)
    raise typer.Exit(code) from exc


def _guard(action: Callable[[], None], json_mode: bool) -> None:
    """Run ``action``; map contract errors to exit codes 1/2."""
    try:
        action()
    except (ConfigError, ResearchGateError, OSError) as exc:
        _fail(exc, json_mode)


def _repo_root() -> Path:
    return Path.cwd()


def _fresh_output_dir(requested: Path | None, command: str) -> Path:
    if requested is None:
        return Path("outputs") / command / uuid4().hex
    if requested.exists() or requested.is_symlink():
        raise ResearchGateError(
            f"output path {requested} already exists; refusing to overwrite (no automatic "
            "deletion of previous runs)"
        )
    return requested


JsonOption = typer.Option(False, "--json", help="Print a single JSON object on stdout.")


@app.command()
def doctor(
    json_mode: bool = JsonOption,
    socioverse_smoke: bool = typer.Option(
        False, "--socioverse-smoke", help="Run the real SocioVerse2 store smoke in a temp dir."
    ),
) -> None:
    """Environment, dependency, contract-hash and lock checks."""

    def action() -> None:
        checks: list[dict[str, Any]] = []

        def record(name: str, ok: bool, detail: str, warn_only: bool = False) -> bool:
            status = "pass" if ok else ("warn" if warn_only else "fail")
            checks.append({"check": name, "status": status, "detail": detail})
            return ok or warn_only

        python_ok = sys.version_info[:2] == (3, 12)
        record("python_3_12", python_ok, sys.version.split()[0])
        machine = platform.machine()
        arm64 = sys.platform == "darwin" and machine == "arm64"
        record("arm64_macos", arm64, f"{sys.platform}/{machine}", warn_only=True)
        try:
            memory_bytes = __import__("os").sysconf("SC_PAGE_SIZE") * __import__(
                "os"
            ).sysconf("SC_PHYS_PAGES")
        except (OSError, ValueError, AttributeError):
            memory_bytes = None
        record(
            "physical_memory",
            memory_bytes is not None,
            f"{memory_bytes} bytes" if memory_bytes is not None else "unavailable",
            warn_only=True,
        )

        import importlib

        from hsm_lab.provenance.manifest import TRACKED_DEPENDENCIES

        for dependency in TRACKED_DEPENDENCIES:
            module_name = {"PyYAML": "yaml", "socioverse2": "socioverse"}.get(
                dependency, dependency
            )
            try:
                module = importlib.import_module(module_name)
                record(
                    f"import_{module_name}",
                    True,
                    getattr(module, "__version__", package_version_safe(dependency)),
                )
            except Exception as exc:  # noqa: BLE001
                record(f"import_{module_name}", False, f"{type(exc).__name__}: {exc}")

        root = _repo_root()
        try:
            contract = load_research_contract(root)
            digest = verify_baseline(root / BASELINE_FILENAME, contract)
            record("baseline_hash", True, digest)
        except (ConfigError, ResearchGateError) as exc:
            record("baseline_hash", False, str(exc))
            contract = None
        record("uv_lock", (root / "uv.lock").is_file(), str(root / "uv.lock"))

        socioverse_evidence: dict[str, Any] | None = None
        if socioverse_smoke:
            from hsm_lab.integrations.socioverse import smoke_socioverse

            temp = Path(tempfile.mkdtemp(prefix="hsm-socioverse-smoke."))
            try:
                socioverse_evidence = smoke_socioverse(temp / "store")
                record("socioverse_store_smoke", True, json.dumps(socioverse_evidence))
            except Exception as exc:  # noqa: BLE001
                record("socioverse_store_smoke", False, f"{type(exc).__name__}: {exc}")
            finally:
                rmtree(temp, ignore_errors=True)

        failed = [check for check in checks if check["status"] == "fail"]
        payload: dict[str, Any] = {
            "status": "ok" if not failed else "fail",
            "command": "doctor",
            "checks": checks,
            "failed_checks": [check["check"] for check in failed],
        }
        if socioverse_evidence is not None:
            payload["socioverse_smoke"] = socioverse_evidence
        if contract is not None:
            payload["contract"] = {
                "baseline_version": contract.baseline_version,
                "expected_baseline_sha256": contract.expected_baseline_sha256,
                "core": f"{contract.core_start}..{contract.core_end}",
                "reserved": f"{contract.reserved_start}..{contract.reserved_end}",
            }
        _emit(payload, json_mode, [f"{c['check']}: {c['status']} ({c['detail']})" for c in checks])
        if failed:
            raise typer.Exit(1)

    _guard(action, json_mode)


def package_version_safe(name: str) -> str:
    try:
        from importlib.metadata import version

        return version(name)
    except Exception:  # noqa: BLE001  # pragma: no cover
        return "<unknown>"


@baseline_app.command("verify")
def baseline_verify(
    path: Path | None = typer.Option(None, "--path", help="Baseline file to verify."),
    json_mode: bool = JsonOption,
) -> None:
    """Compare BASELINE.md bytes against the pinned contract hash."""

    def action() -> None:
        root = _repo_root()
        contract = load_research_contract(root)
        target = path if path is not None else root / BASELINE_FILENAME
        digest = verify_baseline(target, contract)
        _emit(
            {
                "status": "ok",
                "command": "baseline verify",
                "path": str(target),
                "baseline_version": contract.baseline_version,
                "sha256": digest,
                "expected_sha256": contract.expected_baseline_sha256,
            },
            json_mode,
            [f"baseline OK: {digest} ({contract.baseline_version})"],
        )

    _guard(action, json_mode)


@data_app.command("audit")
def data_audit(
    online: bool = typer.Option(False, "--online", help="HEAD-check metadata locators."),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Fresh directory for the audit report."
    ),
    json_mode: bool = JsonOption,
) -> None:
    """Audit the data registry (metadata only; never downloads raw data)."""

    def action() -> None:
        from hsm_lab.data.audit import audit_registry, write_audit_report
        from hsm_lab.data.registry import DataRegistry

        root = _repo_root()
        registry = DataRegistry.load(root)
        report = audit_registry(registry, online=online)
        report_path = write_audit_report(report, _fresh_output_dir(output_dir, "data_audit"))
        payload = {
            "status": "ok",
            "command": "data audit",
            "report_path": report_path,
            "registry_valid": report["registry_valid"],
            "sources_ready": report["sources_ready"],
            "sources_total": report["sources_total"],
            "artifacts_registered": report["artifacts_registered"],
            "blocked_or_unverified": [
                entry["source_id"] for entry in report["blocked_or_unverified"]
            ],
        }
        human = [
            f"registry_valid: {report['registry_valid']}",
            f"sources_ready: {report['sources_ready']} "
            f"({report['sources_total']} sources, {len(report['blocked_or_unverified'])} "
            "blocked/unverified)",
            f"artifacts_registered: {report['artifacts_registered']}",
            f"report: {report_path}",
        ]
        _emit(payload, json_mode, human)

    _guard(action, json_mode)


@app.command()
def run(
    scenario: str = typer.Option("smoke", "--scenario", help="Scenario id (smoke | toy4)."),
    seed: int | None = typer.Option(None, "--seed", min=0, help="RNG seed override."),
    output_policy: str | None = typer.Option(
        None, "--output-policy", help="research_full | ensemble_compact."
    ),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Fresh output directory."),
    households: int | None = typer.Option(
        None, "--households", help="Toy-4 household count override (1000-2000)."
    ),
    until: str | None = typer.Option(
        None, "--until", help="Toy-4 inclusive stop quarter YYYYQn (pauses before horizon)."
    ),
    checkpoint_every: int = typer.Option(
        0, "--checkpoint-every", min=0, help="Save a Toy-4 checkpoint every k completed ticks."
    ),
    resume: Path | None = typer.Option(
        None, "--resume", help="Toy-4 checkpoint directory to resume from."
    ),
    json_mode: bool = JsonOption,
) -> None:
    """Run a scenario (smoke probe load or the Toy-4 economic slice)."""

    def action() -> None:
        from hsm_lab.data.registry import DataRegistry

        root = _repo_root()
        contract = load_research_contract(root)
        spec = load_scenario(root, scenario)
        toy4_only = {
            "--households": households,
            "--until": until,
            "--checkpoint-every": checkpoint_every if checkpoint_every else None,
            "--resume": resume,
        }
        if spec.kind == "smoke":
            used = [flag for flag, value in toy4_only.items() if value is not None]
            if used:
                raise ConfigError(
                    f"option(s) {used} only apply to --scenario toy4, not smoke"
                )
        target = None
        if spec.kind == "smoke":
            from hsm_lab.engine.smoke import run_smoke

            overrides: dict[str, Any] = {}
            if seed is not None:
                overrides["seed"] = seed
            if output_policy is not None:
                try:
                    overrides["output_policy"] = OutputPolicy(output_policy)
                except ValueError as exc:
                    raise ConfigError(
                        f"unknown output policy {output_policy!r}: use research_full or "
                        "ensemble_compact"
                    ) from exc
            if overrides:
                spec = _revalidated_copy(spec, overrides)
            registry = DataRegistry.load(root)
            target = _fresh_output_dir(output_dir, "run")
            manifest = run_smoke(spec, target, contract, registry)
            payload = {
                "status": "ok",
                "command": "run",
                "run_id": manifest.run_id,
                "run_kind": manifest.run_kind,
                "output_dir": str(target),
                "manifest_path": str(Path(target) / "manifest.json"),
                "seed": manifest.seed,
                "output_policy": manifest.output_policy.value,
                "ticks": manifest.ticks,
                "completed_ticks": manifest.completed_ticks,
                "last_completed_quarter": manifest.last_completed_quarter,
                "horizon_reached": True,
                "checkpoint_paths": [],
                "rng_draws_count": manifest.rng_draws_count,
                "rng_draws_by_module": manifest.rng_draws_by_module,
                "stochastic_modules_active": manifest.stochastic_modules_active,
                "deterministic_replay_digest": manifest.deterministic_replay_digest,
                "research_warnings": manifest.research_warnings,
            }
            human = [
                f"run {manifest.run_id} completed: {manifest.run_kind}",
                f"output: {target}",
                f"digest: {manifest.deterministic_replay_digest}",
                f"rng draws: {manifest.rng_draws_count} "
                f"({manifest.rng_draws_by_module})",
            ]
        else:
            from hsm_lab.engine.toy4 import run_toy4

            if resume is not None:
                if scenario != "toy4":
                    raise ConfigError("--resume requires --scenario toy4")
                conflicts = [
                    flag
                    for flag, value in (
                        ("--seed", seed),
                        ("--households", households),
                        ("--output-policy", output_policy),
                    )
                    if value is not None
                ]
                if conflicts:
                    raise ConfigError(
                        f"option(s) {conflicts} are refused together with --resume: "
                        "seed/households/policy come from the checkpoint scenario"
                    )
            toy4_overrides: dict[str, Any] = {}
            if households is not None:
                if not 1000 <= households <= 2000:
                    raise ConfigError(
                        f"--households must lie in [1000, 2000], got {households}"
                    )
                toy4_overrides["households"] = households
            if seed is not None:
                toy4_overrides["seed"] = seed
            if output_policy is not None:
                try:
                    toy4_overrides["output_policy"] = OutputPolicy(output_policy)
                except ValueError as exc:
                    raise ConfigError(
                        f"unknown output policy {output_policy!r}: use research_full or "
                        "ensemble_compact"
                    ) from exc
            if toy4_overrides:
                spec = _revalidated_copy(spec, toy4_overrides)
            registry = DataRegistry.load(root, allowed_commodities=spec.commodities)
            target = _fresh_output_dir(output_dir, "run")
            manifest = run_toy4(
                spec,
                target,
                contract,
                registry,
                until=until,
                checkpoint_every=checkpoint_every,
                resume_from=resume,
            )
            paused = manifest.status == "paused"
            payload = {
                "status": "paused" if paused else "ok",
                "command": "run",
                "run_id": manifest.run_id,
                "run_kind": manifest.run_kind,
                "output_dir": str(target),
                "manifest_path": str(Path(target) / "manifest.json"),
                "seed": manifest.seed,
                "output_policy": manifest.output_policy.value,
                "ticks": manifest.ticks,
                "completed_ticks": manifest.completed_ticks,
                "last_completed_quarter": manifest.last_completed_quarter,
                "horizon_reached": manifest.completed_ticks == manifest.ticks,
                "checkpoint_paths": [
                    str(target / path.rsplit("/metadata.json", 1)[0])
                    for path in sorted(manifest.output_hashes)
                    if path.startswith("checkpoints/")
                    and path.endswith("/metadata.json")
                ],
                "rng_draws_count": manifest.rng_draws_count,
                "rng_draws_by_module": manifest.rng_draws_by_module,
                "stochastic_modules_active": manifest.stochastic_modules_active,
                "deterministic_replay_digest": manifest.deterministic_replay_digest,
                "research_warnings": manifest.research_warnings,
            }
            human = [
                f"run {manifest.run_id} {'paused' if paused else 'completed'}: "
                f"{manifest.run_kind}",
                f"output: {target}",
                f"completed ticks: {manifest.completed_ticks}/{manifest.ticks} "
                f"(last quarter {manifest.last_completed_quarter})",
                f"digest: {manifest.deterministic_replay_digest}",
                f"rng draws: {manifest.rng_draws_count} "
                f"({manifest.rng_draws_by_module})",
            ]
        _emit(payload, json_mode, human)

    _guard(action, json_mode)


def _revalidated_copy(spec: ScenarioSpec, overrides: dict[str, Any]) -> ScenarioSpec:
    """Apply overrides and re-run full model validation (never widen quietly)."""
    return ScenarioSpec.model_validate(spec.model_copy(update=overrides).model_dump())


def _run_benchmark(kind: str, output_dir: Path | None, json_mode: bool) -> None:
    def action() -> None:
        from hsm_lab.benchmarks.harness import run_benchmark

        target = _fresh_output_dir(output_dir, f"benchmark_{kind}")
        report = run_benchmark(kind, _repo_root(), target)
        payload = dict(report)
        payload["status"] = "ok" if report["overall_gate"] == "pass" else "fail"
        payload["command"] = f"benchmark {kind}"
        payload["output_dir"] = str(target)
        _emit(
            payload,
            json_mode,
            [
                f"benchmark {kind}: gate={report['overall_gate']}",
                f"output: {target}",
            ],
        )
        if report["overall_gate"] != "pass":
            raise typer.Exit(1)

    _guard(action, json_mode)


@benchmark_app.command("smoke")
def benchmark_smoke(
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    json_mode: bool = JsonOption,
) -> None:
    """Isolated P00 smoke benchmark (N=1000, E=50, T=10; compact and full)."""
    _run_benchmark("smoke", output_dir, json_mode)


@benchmark_app.command("scaling")
def benchmark_scaling(
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    json_mode: bool = JsonOption,
) -> None:
    """Six-scale x {10,116} ticks scaling benchmark (compact policy)."""
    _run_benchmark("scaling", output_dir, json_mode)


@app.command()
def summary(
    run_dir: Path = typer.Option(..., "--run-dir", help="Completed or paused Toy-4 run directory."),
    json_mode: bool = JsonOption,
) -> None:
    """Read back a finished/paused Toy-4 run summary (never starts a simulation)."""

    def action() -> None:
        from hsm_lab.engine.toy4 import TOY4_ENGINE_VERSION
        from hsm_lab.provenance.manifest import RunManifest

        manifest_path = run_dir / "manifest.json"
        summary_path = run_dir / "summary.json"
        if not manifest_path.is_file() or not summary_path.is_file():
            raise ResearchGateError(
                f"no manifest.json/summary.json under {run_dir}: not a finished run"
            )
        try:
            manifest = RunManifest.model_validate(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ResearchGateError(f"unreadable run outputs under {run_dir}: {exc}") from exc
        if manifest.run_kind != "toy4_f0_simulation":
            raise ResearchGateError(
                f"summary only reads toy4_f0_simulation runs, got {manifest.run_kind!r}"
            )
        if manifest.status not in ("completed", "paused"):
            raise ResearchGateError(
                f"run {manifest.run_id} has status {manifest.status!r}; only completed "
                "or paused runs can be summarized"
            )
        if payload.get("run_id") != manifest.run_id:
            raise ResearchGateError(
                "summary run_id does not match the manifest: refusing divergent records"
            )
        if payload.get("deterministic_replay_digest") != manifest.deterministic_replay_digest:
            raise ResearchGateError(
                "summary digest disagrees with the manifest: refusing divergent records"
            )
        if payload.get("completed_ticks") != manifest.completed_ticks:
            raise ResearchGateError(
                "summary completed_ticks disagrees with the manifest boundary"
            )
        import hashlib

        recorded = manifest.output_hashes.get("summary.json")
        actual = hashlib.sha256(summary_path.read_bytes()).hexdigest()
        if recorded is None or recorded != actual:
            raise ResearchGateError(
                "summary.json bytes do not match the manifest's recorded output hash: "
                "refusing to read back tampered summaries"
            )
        _emit(
            payload,
            json_mode,
            _summary_human(payload, manifest.engine_version or TOY4_ENGINE_VERSION),
        )

    _guard(action, json_mode)


def _summary_human(payload: dict[str, Any], engine_version: str) -> list[str]:
    lines = [
        f"toy4 summary ({engine_version}): scenario {payload.get('scenario_id')} "
        f"seed {payload.get('seed')}",
        f"quarters: {payload.get('completed_ticks')}/{payload.get('planned_ticks')} "
        f"completed (last {payload.get('last_completed_quarter')}, "
        f"horizon_reached={payload.get('horizon_reached')})",
        f"digest: {payload.get('deterministic_replay_digest')}",
    ]
    for commodity, stats in sorted((payload.get("by_commodity") or {}).items()):
        lines.append(
            f"  {commodity}: production {stats['production']:.1f}, imports "
            f"{stats['imports']:.1f}, used {stats['used_input']:.1f}, exports "
            f"{stats['exports']:.1f}, consumption {stats['consumption']:.1f}"
        )
        lines.append(
            f"    unmet budget {stats['budget_unmet']:.1f} / availability "
            f"{stats['availability_unmet']:.1f} / total {stats['total_unmet']:.1f} "
            f"(availability rate {stats['cumulative_availability_shortage_rate']:.3f})"
        )
        lines.append(
            f"    closing stocks: wholesale {stats['final_wholesale_inventory']:.1f}, "
            f"organization input {stats['final_organization_input_inventory']:.1f}, "
            f"retail {stats['final_retail_inventory']:.1f}"
        )
    invariants = payload.get("invariants") or {}
    lines.append(
        f"  invariants ({invariants.get('checked_ticks')} ticks): max material "
        f"residual {invariants.get('max_material_abs_residual')}, ratio "
        f"{invariants.get('max_material_tolerance_ratio')}; max cash residual "
        f"{invariants.get('max_cash_abs_residual')}, ratio "
        f"{invariants.get('max_cash_tolerance_ratio')}"
    )
    return lines


@benchmark_app.command("toy4")
def benchmark_toy4(
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Fresh directory for the benchmark report."
    ),
    json_mode: bool = JsonOption,
) -> None:
    """Toy-4 economic-loop scaling benchmark (N in {1000,1600,2000} x {10,116})."""
    _run_benchmark("toy4", output_dir, json_mode)


def main() -> None:  # console entry: hsm = hsm_lab.cli.app:main
    app()


if __name__ == "__main__":
    main()
