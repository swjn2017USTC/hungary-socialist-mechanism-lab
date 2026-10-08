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
from hsm_lab.contract.material import OrganizationProfile, OrganizationRecipe
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
            memory_bytes = __import__("os").sysconf("SC_PAGE_SIZE") * __import__("os").sysconf(
                "SC_PHYS_PAGES"
            )
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
    scenario: str = typer.Option(
        "smoke",
        "--scenario",
        help="Scenario id (smoke | intermediate8 | intermediate8_external).",
    ),
    seed: int | None = typer.Option(None, "--seed", min=0, help="RNG seed override."),
    output_policy: str | None = typer.Option(
        None,
        "--output-policy",
        help="research_full | ensemble_compact.",
    ),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Fresh output directory."),
    households: int | None = typer.Option(
        None,
        "--households",
        help="Material household count override (1000-30000).",
    ),
    organizations: int | None = typer.Option(
        None,
        "--organizations",
        help="Material organization profile size (100 | 200 | 400).",
    ),
    until: str | None = typer.Option(
        None,
        "--until",
        help="Material inclusive stop quarter YYYYQn (pauses before horizon).",
    ),
    checkpoint_every: int = typer.Option(
        0,
        "--checkpoint-every",
        min=0,
        help="Save a material checkpoint every k completed ticks.",
    ),
    resume: Path | None = typer.Option(
        None,
        "--resume",
        help="Material checkpoint directory to resume from.",
    ),
    json_mode: bool = JsonOption,
) -> None:
    """Run a scenario (smoke probe load or the Intermediate-8 material economy)."""

    def action() -> None:
        from hsm_lab.data.registry import DataRegistry

        if scenario == "toy4":
            raise ConfigError(
                "--scenario toy4 was removed with the P01 Toy-4 engine and its "
                "config; use --scenario intermediate8 (Intermediate-8 material economy)"
            )
        root = _repo_root()
        contract = load_research_contract(root)
        spec = load_scenario(root, scenario)
        if spec.kind not in ("smoke", "material"):
            raise ConfigError(
                f"scenario {scenario!r} carries kind {spec.kind!r}; only smoke and "
                "material runs exist (the toy4 economic kind was removed)"
            )
        material_only = {
            "--households": households,
            "--organizations": organizations,
            "--until": until,
            "--checkpoint-every": checkpoint_every if checkpoint_every else None,
            "--resume": resume,
        }
        if spec.kind == "smoke":
            used = [flag for flag, value in material_only.items() if value is not None]
            if used:
                raise ConfigError(
                    f"option(s) {used} only apply to --scenario intermediate8, not smoke"
                )
            target = None
        else:
            target = _prepare_material_run(
                spec=spec,
                seed=seed,
                households=households,
                organizations=organizations,
                output_policy=output_policy,
                resume=resume,
            )
            spec = target
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
            target_dir = _fresh_output_dir(output_dir, "run")
            manifest = run_smoke(spec, target_dir, contract, registry)
            payload = {
                "status": "ok",
                "command": "run",
                "run_id": manifest.run_id,
                "run_kind": manifest.run_kind,
                "output_dir": str(target_dir),
                "manifest_path": str(Path(target_dir) / "manifest.json"),
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
                f"output: {target_dir}",
                f"digest: {manifest.deterministic_replay_digest}",
                f"rng draws: {manifest.rng_draws_count} ({manifest.rng_draws_by_module})",
            ]
        else:
            from hsm_lab.engine.material import run_material

            registry = DataRegistry.load(root, allowed_commodities=spec.commodities)
            target_dir = _fresh_output_dir(output_dir, "run")
            if spec.politics is not None:
                from hsm_lab.engine.political_run import run_political

                manifest = run_political(
                    spec,
                    target_dir,
                    contract,
                    registry,
                    until=until,
                    checkpoint_every=checkpoint_every,
                    resume_from=resume,
                )
            else:
                manifest = run_material(
                    spec,
                    target_dir,
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
                "output_dir": str(target_dir),
                "manifest_path": str(Path(target_dir) / "manifest.json"),
                "seed": manifest.seed,
                "output_policy": manifest.output_policy.value,
                "ticks": manifest.ticks,
                "completed_ticks": manifest.completed_ticks,
                "last_completed_quarter": manifest.last_completed_quarter,
                "horizon_reached": manifest.completed_ticks == manifest.ticks,
                "checkpoint_paths": [
                    str(target_dir / path.rsplit("/metadata.json", 1)[0])
                    for path in sorted(manifest.output_hashes)
                    if path.startswith("checkpoints/") and path.endswith("/metadata.json")
                ],
                "rng_draws_count": manifest.rng_draws_count,
                "rng_draws_by_module": manifest.rng_draws_by_module,
                "stochastic_modules_active": manifest.stochastic_modules_active,
                "deterministic_replay_digest": manifest.deterministic_replay_digest,
                "research_warnings": manifest.research_warnings,
            }
            human = [
                f"run {manifest.run_id} {'paused' if paused else 'completed'}: {manifest.run_kind}",
                f"output: {target_dir}",
                f"completed ticks: {manifest.completed_ticks}/{manifest.ticks} "
                f"(last quarter {manifest.last_completed_quarter})",
                f"digest: {manifest.deterministic_replay_digest}",
                f"rng draws: {manifest.rng_draws_count} ({manifest.rng_draws_by_module})",
            ]
        _emit(payload, json_mode, human)

    _guard(action, json_mode)


def _prepare_material_run(
    *,
    spec: ScenarioSpec,
    seed: int | None,
    households: int | None,
    organizations: int | None,
    output_policy: str | None,
    resume: Path | None,
) -> ScenarioSpec:
    """Validate material-only options and apply them to the scenario copy."""
    if resume is not None:
        conflicts = [
            flag
            for flag, value in (
                ("--seed", seed),
                ("--households", households),
                ("--organizations", organizations),
                ("--output-policy", output_policy),
            )
            if value is not None
        ]
        if conflicts:
            raise ConfigError(
                f"option(s) {conflicts} are refused together with --resume: "
                "seed/households/organizations/policy come from the checkpoint scenario"
            )
        return spec
    if spec.politics is not None:
        conflicts = [
            flag
            for flag, value in (
                ("--seed", seed),
                ("--households", households),
                ("--organizations", organizations),
                ("--output-policy", output_policy),
            )
            if value is not None
        ]
        if conflicts:
            raise ConfigError(
                f"option(s) {conflicts} are refused for a P04 politics scenario: the "
                "recipe is pinned by the scenario config (fork a checkpoint to change "
                "policy/coalition/technology instead)"
            )
        return spec
    overrides: dict[str, Any] = {}
    if households is not None:
        if not 1000 <= households <= 30000:
            raise ConfigError(f"--households must lie in [1000, 30000], got {households}")
        overrides["households"] = households
    if organizations is not None:
        profiles: dict[int, OrganizationProfile] = {
            100: "p02_100",
            200: "p02_200",
            400: "p02_400",
        }
        profile = profiles.get(organizations)
        if profile is None:
            raise ConfigError(
                f"--organizations must be one of 100/200/400 (defined profiles), "
                f"got {organizations}"
            )
        recipe = spec.organization_recipe
        if recipe is not None and recipe.overrides:
            raise ConfigError(
                "--organizations cannot switch the organization profile: the "
                "scenario carries explicit organization_recipe overrides that a "
                "count-only switch would silently drop; provide a config with a "
                "consistent recipe"
            )
        overrides["organizations"] = organizations
        if recipe is not None:
            overrides["organization_recipe"] = OrganizationRecipe(profile=profile, overrides=[])
    if seed is not None:
        overrides["seed"] = seed
    if output_policy is not None:
        try:
            overrides["output_policy"] = OutputPolicy(output_policy)
        except ValueError as exc:
            raise ConfigError(
                f"unknown output policy {output_policy!r}: use research_full or ensemble_compact"
            ) from exc
    if overrides:
        return _revalidated_copy(spec, overrides)
    return spec


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
    run_dir: Path = typer.Option(
        ..., "--run-dir", help="Completed or paused material run directory."
    ),
    json_mode: bool = JsonOption,
) -> None:
    """Read back a finished/paused material run summary (never starts a simulation)."""

    def action() -> None:
        from hsm_lab.provenance.manifest import RunManifest
        from hsm_lab.storage.checkpoint import ENGINE_VERSION

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
        if manifest.run_kind != "intermediate8_household_simulation":
            raise ResearchGateError(
                "summary only reads intermediate8_household_simulation runs, got "
                f"{manifest.run_kind!r}"
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
            raise ResearchGateError("summary completed_ticks disagrees with the manifest boundary")
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
            _summary_human(payload, manifest.engine_version or ENGINE_VERSION),
        )

    _guard(action, json_mode)


def _summary_human(payload: dict[str, Any], engine_version: str) -> list[str]:
    lines = [
        f"material summary ({engine_version}): scenario {payload.get('scenario_id')} "
        f"seed {payload.get('seed')}",
        f"quarters: {payload.get('completed_ticks')}/{payload.get('planned_ticks')} "
        f"completed (last {payload.get('last_completed_quarter')}, "
        f"horizon_reached={payload.get('horizon_reached')})",
        f"digest: {payload.get('deterministic_replay_digest')}",
    ]
    for commodity, stats in sorted((payload.get("by_commodity") or {}).items()):
        if not isinstance(stats, dict):
            continue
        lines.append(
            f"  {commodity}: production {stats.get('production', 0.0):.1f}, imports "
            f"{stats.get('imports', 0.0):.1f}, used {stats.get('used_input', 0.0):.1f}, "
            f"exports {stats.get('exports', 0.0):.1f}, consumption "
            f"{stats.get('consumption', 0.0):.1f}"
        )
        lines.append(
            f"    unmet budget {stats.get('budget_unmet', 0.0):.1f} / availability "
            f"{stats.get('availability_unmet', 0.0):.1f} / total "
            f"{stats.get('total_unmet', 0.0):.1f} "
            f"(availability rate {stats.get('cumulative_availability_shortage_rate', 0.0):.3f})"
        )
    invariants = payload.get("invariants") or {}
    lines.append(
        f"  invariants: max material residual "
        f"{invariants.get('max_material_abs_residual')}, ratio "
        f"{invariants.get('max_material_tolerance_ratio')}; max finance residual "
        f"{invariants.get('max_finance_abs_residual')}, ratio "
        f"{invariants.get('max_finance_tolerance_ratio')}"
    )
    return lines


INGEST_DEFAULT_WINDOWS: dict[str, tuple[str, str]] = {
    "ksh_gdp": ("1960", "1985"),
    "ksh_industry": ("1960", "1985"),
    "ksh_agriculture_b": ("1960", "1985"),
    "ksh_trade": ("1960", "1985"),
    "worldbank_pink_sheet": ("1960-01", "1985-12"),
    "federalreserve_h15": ("1957-01", "1985-12"),
    "fred_fedfunds": ("1957-01", "1985-12"),
    "mnb_official_fx": ("1985-01-01", "1985-12-31"),
}


@data_app.command("ingest")
def data_ingest(
    source: str = typer.Option(
        ..., "--source", help="One ingestion source id from the fixed allowlist."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use the hash-verified cache only; miss exits 1."
    ),
    refresh: bool = typer.Option(False, "--refresh", help="Download a new vintage even if cached."),
    json_mode: bool = JsonOption,
) -> None:
    """Download, cache, parse and register one whitelisted data source."""

    def action() -> None:
        from hsm_lab.data.ingestion import IngestionRequest, ingest_source

        if source not in INGEST_DEFAULT_WINDOWS:
            known = ", ".join(sorted(INGEST_DEFAULT_WINDOWS))
            raise ConfigError(f"unknown ingestion source {source!r}; allowlist: {known}")
        start, end = INGEST_DEFAULT_WINDOWS[source]
        root = _repo_root()
        report = ingest_source(
            root,
            IngestionRequest(
                source_id=source, start=start, end=end, offline=offline, refresh=refresh
            ),
        )
        payload = {
            "status": "ok",
            "command": "data ingest",
            "source": report.source_id,
            "window": {"start": report.request.start, "end": report.request.end},
            "offline": bool(offline),
            "refresh": bool(refresh),
            "cache_hit": report.cache_hit,
            "downloaded": report.downloaded,
            "raw_sha256": report.raw_sha256,
            "raw_path": str(report.raw_path),
            "retrieval_url": report.retrieval_url,
            "variable_ids": list(report.variable_ids),
            "artifact_ids": list(report.artifact_ids),
        }
        human = [
            f"ingested {report.source_id}: {len(report.artifact_ids)} artifacts "
            f"({'cache' if report.cache_hit else 'download'})",
            f"raw sha256: {report.raw_sha256}",
        ]
        _emit(payload, json_mode, human)

    _guard(action, json_mode)


@data_app.command("build-material-forcing")
def data_build_material_forcing(
    profile: str = typer.Option(
        ..., "--profile", help="synthetic (local fixture) | external (admitted data)."
    ),
    json_mode: bool = JsonOption,
) -> None:
    """Build the material forcing pack (never runs during a simulation)."""

    def action() -> None:
        if profile not in ("synthetic", "external"):
            raise ConfigError(f"unknown profile {profile!r}: use synthetic or external")
        root = _repo_root()
        if profile == "synthetic":
            from hsm_lab.data.material import (
                MATERIAL_SYNTHETIC_PACK_PATH,
                build_synthetic_material_fixtures,
            )

            report = build_synthetic_material_fixtures(root)
            payload: dict[str, Any] = {
                "status": "ok",
                "command": "data build-material-forcing",
                "profile": "synthetic",
                "pack_path": str(root / MATERIAL_SYNTHETIC_PACK_PATH),
                "artifact_ids": list(report.artifact_ids),
                "variable_ids": list(report.variable_ids),
                "raw_sha256": report.raw_sha256,
            }
            human = [
                f"synthetic material fixtures built: {len(report.artifact_ids)} artifacts",
                f"pack: {root / MATERIAL_SYNTHETIC_PACK_PATH}",
            ]
        else:
            from hsm_lab.data.material import (
                MATERIAL_EXTERNAL_PACK_PATH,
                build_external_material_pack,
            )

            pack = build_external_material_pack(root, {})
            payload = {
                "status": "ok",
                "command": "data build-material-forcing",
                "profile": "external",
                "pack_path": str(root / MATERIAL_EXTERNAL_PACK_PATH),
                **{key: value for key, value in pack.items() if key != "bindings"},
                "binding_count": len(pack.get("bindings", [])),
            }
            human = [
                "external material pack built from admitted artifacts",
                f"pack: {root / MATERIAL_EXTERNAL_PACK_PATH}",
            ]
        _emit(payload, json_mode, human)

    _guard(action, json_mode)


@data_app.command("build-p04-inputs")
def data_build_p04_inputs(
    profile: str = typer.Option(
        ..., "--profile", help="synthetic (local fixture) | external (admitted data)."
    ),
    json_mode: bool = JsonOption,
) -> None:
    """Build the P04 external pack / event registry / policy replay / broadcasts."""

    def action() -> None:
        from hsm_lab.data.external import build_p04_inputs

        if profile not in ("synthetic", "external"):
            raise ConfigError(f"unknown profile {profile!r}: use synthetic or external")
        report = build_p04_inputs(_repo_root(), profile)
        _emit(
            {"status": "ok", "command": "data build-p04-inputs", **report},
            json_mode,
            [
                f"P04 {profile} inputs built: {len(report['files'])} files",
                f"pack: {report['pack_path']}",
            ],
        )

    _guard(action, json_mode)


@app.command()
def fork(
    checkpoint: Path = typer.Option(
        ..., "--checkpoint", help="Parent P04 checkpoint directory to fork from."
    ),
    intervention: Path = typer.Option(
        ..., "--intervention", help="Intervention JSON list (may be an empty list)."
    ),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Fresh output directory."),
    until: str | None = typer.Option(None, "--until", help="Inclusive stop quarter YYYYQn."),
    checkpoint_every: int = typer.Option(
        0, "--checkpoint-every", min=0, help="Save a checkpoint every k completed ticks."
    ),
    json_mode: bool = JsonOption,
) -> None:
    """Fork a P04 checkpoint into a Mode C counterfactual branch."""

    def action() -> None:
        from hsm_lab.contract.guards import load_research_contract
        from hsm_lab.contract.politics import InterventionSpec, PoliticalMode
        from hsm_lab.contract.schemas import ScenarioSpec
        from hsm_lab.data.registry import DataRegistry
        from hsm_lab.engine.political_run import run_political
        from hsm_lab.storage.fork import load_counterfactual_origin

        root = _repo_root()
        contract = load_research_contract(root)
        metadata_path = checkpoint / "metadata.json"
        if not metadata_path.is_file():
            raise ResearchGateError(f"fork source is not a checkpoint directory: {checkpoint}")
        parent = ScenarioSpec.model_validate(
            json.loads(metadata_path.read_text(encoding="utf-8"))["scenario"]
        )
        if parent.politics is None:
            raise ConfigError("fork requires a politics-enabled checkpoint")
        if not intervention.is_file():
            raise ConfigError(f"intervention file not found: {intervention}")
        raw = json.loads(intervention.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ConfigError("intervention file must contain a JSON list of intervention specs")
        specs = [InterventionSpec.model_validate(entry) for entry in raw]
        child = parent.model_copy(
            update={
                "politics": parent.politics.model_copy(
                    update={"mode": PoliticalMode.COUNTERFACTUAL}
                ),
            }
        )
        registry = DataRegistry.load(root, allowed_commodities=child.commodities)
        origin = load_counterfactual_origin(checkpoint, child, contract, interventions=specs)
        target_dir = _fresh_output_dir(output_dir, "fork")
        manifest = run_political(
            child,
            target_dir,
            contract,
            registry,
            until=until,
            checkpoint_every=checkpoint_every,
            fork_from=origin,
        )
        _emit(
            {
                "status": "ok" if manifest.status != "paused" else "paused",
                "command": "fork",
                "run_id": manifest.run_id,
                "run_kind": manifest.run_kind,
                "political_mode": str(manifest.political_mode),
                "source_checkpoint": str(checkpoint),
                "output_dir": str(target_dir),
                "completed_ticks": manifest.completed_ticks,
                "last_completed_quarter": manifest.last_completed_quarter,
                "deterministic_replay_digest": manifest.deterministic_replay_digest,
                "intervention_count": len(specs),
            },
            json_mode,
            [
                f"fork {manifest.run_id}: {manifest.completed_ticks} ticks "
                f"(last {manifest.last_completed_quarter})",
                f"output: {target_dir}",
            ],
        )

    _guard(action, json_mode)


@benchmark_app.command("material")
def benchmark_material(
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Fresh directory for the benchmark report."
    ),
    json_mode: bool = JsonOption,
) -> None:
    """Intermediate-8 material-path benchmark (plan section 9 exact cases)."""
    _run_benchmark("material", output_dir, json_mode)


def main() -> None:  # console entry: hsm = hsm_lab.cli.app:main
    app()


if __name__ == "__main__":
    main()
