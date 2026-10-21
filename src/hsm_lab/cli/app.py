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

from hsm_lab.calibration.closure import audit_material_closure
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
calibration_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(baseline_app, name="baseline")
app.add_typer(data_app, name="data")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(calibration_app, name="calibration")


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


def _region_distance_for(spec: ScenarioSpec, root: Path) -> Any:
    """Explicit F2 distance matrix when the scenario uses the F2 catalog."""
    from hsm_lab.contract.material import F2_CATALOG, catalog_for_commodities

    catalog = catalog_for_commodities(spec.commodities)
    if catalog.catalog_id != F2_CATALOG.catalog_id:
        return None
    path = root / "config" / "ontology" / "f2_regions_v1.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    if tuple(payload["region_ids"]) != tuple(spec.region_ids):
        raise ConfigError("f2_regions_v1.json region ids do not match the scenario")
    import numpy as np

    return np.asarray(payload["distance_matrix"], dtype=np.float64)


@calibration_app.command("screen")
def calibration_screen(
    config: Path = typer.Option(
        Path("config/calibration/p05.json"),
        "--config",
        help="P05 research control file (windows and registry references).",
    ),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Fresh output directory."),
    json_mode: bool = JsonOption,
) -> None:
    """Classify the declared latent parameters from admissible target evidence."""

    def action() -> None:
        import json as _json

        from hsm_lab.calibration.screen import screen_parameters

        root = _repo_root()
        target = _fresh_output_dir(output_dir, "p05-screen")
        payload = screen_parameters(root, config=config)
        target.mkdir(parents=True, exist_ok=False)
        (target / "screen.json").write_text(
            _json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _emit(
            {**payload, "output_dir": str(target)},
            json_mode,
            [
                f"screen {payload['status']}: {payload['parameters']} parameters, "
                f"{payload['admissible_targets']} admissible targets "
                f"{payload['status_counts']}"
            ],
        )
        if payload["status"] == "NO_IDENTIFIABLE_PARAMETERS":
            raise typer.Exit(0)

    _guard(action, json_mode)


@calibration_app.command("fidelity")
def calibration_fidelity(
    config: Path = typer.Option(
        Path("config/calibration/p05.json"),
        "--config",
        help="P05 research control file (seed banks, tolerances, registries).",
    ),
    stage: str = typer.Option("prior", "--stage", help="prior | posterior."),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Fresh output directory."),
    json_mode: bool = JsonOption,
) -> None:
    """Report the F1 paired-fidelity preconditions for the declared control file."""

    def action() -> None:
        import json as _json

        from hsm_lab.calibration.fidelity import prior_fidelity

        root = _repo_root()
        target = _fresh_output_dir(output_dir, "p05-fidelity")
        payload = prior_fidelity(root, config=config, stage=stage)
        target.mkdir(parents=True, exist_ok=False)
        (target / "fidelity.json").write_text(
            _json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _emit(
            {**payload, "output_dir": str(target)},
            json_mode,
            [
                f"fidelity {payload['status']} (stage {payload['stage']}): "
                f"candidates {len(payload.get('candidates', []))}"
            ],
        )

    _guard(action, json_mode)


@calibration_app.command("abc-smoke")
def calibration_abc_smoke(
    config: Path = typer.Option(
        Path("config/calibration/p05.json"), "--config", help="P05 research control file."
    ),
    particles: int = typer.Option(16, "--particles", min=1, help="ABC particles per population."),
    populations: int = typer.Option(2, "--populations", min=1, help="ABC populations."),
    ticks: int = typer.Option(4, "--ticks", min=1, help="Kernel ticks per evaluation."),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Fresh output directory."),
    json_mode: bool = JsonOption,
) -> None:
    """Prove the ABC API on a synthetic target and that the real registry has no candidates."""

    def action() -> None:
        import json as _json

        from hsm_lab.calibration.abc_smoke import abc_registry_path, abc_synthetic_recovery

        root = _repo_root()
        target = _fresh_output_dir(output_dir, "p05-abc-smoke")
        payload = {
            "command": "calibration abc-smoke",
            "synthetic_recovery": abc_synthetic_recovery(
                root, config=config, particles=particles, populations=populations, ticks=ticks
            ),
            "real_registry_path": abc_registry_path(root, config=config),
        }
        target.mkdir(parents=True, exist_ok=False)
        (target / "abc_smoke.json").write_text(
            _json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        recovery = payload["synthetic_recovery"]
        registry = payload["real_registry_path"]
        _emit(
            {**payload, "output_dir": str(target)},
            json_mode,
            [
                f"abc smoke: {recovery['status']} "
                f"({recovery['particles']} particles x {recovery['populations_completed']} "
                f"populations, posterior mean {recovery['posterior_mean']:.4f} "
                f"vs truth {recovery['truth']})",
                f"real registry path: {registry['status']} "
                f"(candidates {len(registry['identifiable_set'])})",
            ],
        )

    _guard(action, json_mode)


@calibration_app.command("audit-closure")
def calibration_audit_closure(
    scenario: str = typer.Option(
        "intermediate8",
        "--scenario",
        help="Material catalog scenario whose kernel must close.",
    ),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Fresh output directory."),
    diagnostic_ticks: int = typer.Option(
        232, "--diagnostic-ticks", min=8, help="H0 diagnostic ticks (P05 default 232)."
    ),
    seed: int | None = typer.Option(None, "--seed", min=0, help="Initial-state seed override."),
    json_mode: bool = JsonOption,
) -> None:
    """Run the offline material/service/money closure certificate (P05 §0.7)."""

    def action() -> None:
        root = _repo_root()
        contract = load_research_contract(root)
        spec = load_scenario(root, scenario)
        target = _fresh_output_dir(output_dir, f"p05-closure-{scenario}")
        certificate = audit_material_closure(
            spec,
            contract,
            output_dir=target,
            diagnostic_ticks=diagnostic_ticks,
            seed=seed,
            region_distance=_region_distance_for(spec, root),
        )
        _emit(
            {
                "status": certificate.status,
                "command": "calibration audit-closure",
                "scenario_id": certificate.scenario_id,
                "catalog_id": certificate.catalog_id,
                "engine_version": certificate.engine_version,
                "diagnostic_ticks": certificate.diagnostic_ticks,
                "passed": certificate.passed,
                "max_periodic_residual": certificate.max_periodic_residual,
                "periodic_residuals": certificate.periodic_residuals,
                "periodic_tolerance": certificate.periodic_tolerance,
                "stock_output_ratio_residual": certificate.stock_output_ratio_residual,
                "stock_output_ratio_tolerance": certificate.stock_output_ratio_tolerance,
                "stock_output_ratio_annual_drift": certificate.stock_output_ratio_annual_drift,
                "lambda_common": certificate.lambda_common,
                "output_liveness": certificate.output_liveness,
                "credit_debt_growth": certificate.credit_debt_growth,
                "debt_to_output": certificate.debt_to_output,
                "sbc_transfer_ratio": certificate.sbc_transfer_ratio,
                "forced_saving_ratio": certificate.forced_saving_ratio,
                "dead_commodities": certificate.dead_commodities,
                "max_material_tolerance_ratio": certificate.max_material_tolerance_ratio,
                "max_finance_tolerance_ratio": certificate.max_finance_tolerance_ratio,
                "certificate_path": str(target / "certificate.json"),
            },
            json_mode,
            [
                f"closure {certificate.status}: output/cash residual "
                f"{max(certificate.periodic_residuals.get('output', 0.0), certificate.periodic_residuals.get('cash', 0.0)):.3e} "  # noqa: E501
                f"(tol {certificate.periodic_tolerance:g}); stock/output ratio residual "
                f"{certificate.stock_output_ratio_residual:.3e} "
                f"(tol {certificate.stock_output_ratio_tolerance:g}, drift "
                f"{certificate.stock_output_ratio_annual_drift:+.3f}/yr)"
            ],
        )
        if not certificate.passed:
            raise typer.Exit(1)

    _guard(action, json_mode)


@calibration_app.command("forcing-ladder")
def calibration_forcing_ladder(
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Fresh output directory."),
    diagnostic_ticks: int | None = typer.Option(
        None, "--diagnostic-ticks", min=8, help="Defaults to the configured 232 synthetic ticks."
    ),
    seed: int | None = typer.Option(None, "--seed", min=0, help="Defaults to the configured seed."),
    json_mode: bool = JsonOption,
) -> None:
    """Run the configured H0-H4 diagnostic ladder on intermediate8 only."""

    def action() -> None:
        from hsm_lab.calibration.forcing_ladder import run_forcing_ladder

        root = _repo_root()
        target = _fresh_output_dir(output_dir, "p06-forcing-ladder-intermediate8")
        payload = run_forcing_ladder(root, target, diagnostic_ticks=diagnostic_ticks, seed=seed)
        payload["output_dir"] = str(target)
        _emit(
            payload,
            json_mode,
            [
                f"{rung['rung_id']}: {rung['status']} liveness {rung['output_liveness']:.4f}"
                for rung in payload["rungs"]
            ],
        )

    _guard(action, json_mode)


@calibration_app.command("interest-fiscal-arms")
def calibration_interest_fiscal_arms(
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Fresh experiment directory."
    ),
    json_mode: bool = JsonOption,
) -> None:
    """Run the registered P05 B0/I1-I3/F1/C1/N1 transfer arms through 1985Q4."""

    def action() -> None:
        from hsm_lab.calibration.interest_fiscal_experiment import run_interest_fiscal_arms

        root = _repo_root()
        target = (
            output_dir
            if output_dir is not None and output_dir.exists()
            else _fresh_output_dir(output_dir, "p05-interest-fiscal-arms")
        )
        payload = run_interest_fiscal_arms(root, target)
        _emit(
            payload,
            json_mode,
            [
                (
                    f"{arm['arm']}: REJECTED at tick {arm['completed_ticks']} "
                    f"({arm['failure_message']})"
                    if arm.get("status") == "rejected_accounting_residual"
                    else (
                        f"{arm['arm']}: gates={'PASS' if arm['frozen_gates_pass'] else 'BLOCKED'} "
                        f"T1={arm['terminal_T1_pass']} T2={arm['terminal_T2_pass']} "
                        f"T3={arm['terminal_T3_pass']} liveness={arm['liveness']:.4f}"
                    )
                )
                for arm in payload["arms"]
            ],
        )

    _guard(action, json_mode)


@calibration_app.command("axis-sweep")
def calibration_axis_sweep(
    axis: str = typer.Option(
        ...,
        "--axis",
        help=(
            "credit_envelope_fraction, input_credit_earmark_fraction, transport_capacity_scale, "
            "interest_sink_remittance_fraction, or fiscal_turnover_remittance_fraction."
        ),
    ),
    points: str = typer.Option(
        ..., "--points", help="Comma-separated axis values, e.g. 0.5,0.75,1.0."
    ),
    scenario: str = typer.Option(
        "historical_f2_replay", "--scenario", help="Material scenario to sweep."
    ),
    seed: int | None = typer.Option(None, "--seed", min=0, help="Override the model seed."),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Fresh output directory."),
    json_mode: bool = JsonOption,
) -> None:
    """Run the gate metrics once per value of one declared axis (P05 §E6)."""

    def action() -> None:
        from hsm_lab.calibration.axis_sweep import AXES, run_axis_sweep
        from hsm_lab.data.registry import DataRegistry

        if axis not in AXES:
            raise typer.BadParameter(f"unknown axis {axis!r}; expected one of {AXES}")
        values = [float(part) for part in points.split(",") if part.strip()]
        if not values:
            raise typer.BadParameter("--points must list at least one value")
        root = _repo_root()
        contract = load_research_contract(root)
        spec = load_scenario(root, scenario)
        registry = DataRegistry.load(root, allowed_commodities=spec.commodities)
        target = _fresh_output_dir(output_dir, f"p05-axis-{axis}")
        control = json.loads((root / "config/calibration/p05.json").read_text())
        results = run_axis_sweep(
            spec,
            contract,
            registry,
            axis=axis,
            points=values,
            output_root=target,
            terminal_floor=control["gates"]["terminal_floor"],
            seed=seed,
        )
        _emit(
            {
                "status": "measured",
                "command": "calibration axis-sweep",
                "axis": axis,
                "scenario_id": spec.scenario_id,
                "points": [point.as_dict() for point in results],
                "output_dir": str(target),
            },
            json_mode,
            [
                f"{point.value:g}: liveness {point.liveness:.4f} "
                f"expired tail {point.expired_services_tail:,.0f} "
                f"treasury zero {point.treasury_zero_tick}"
                for point in results
            ],
        )

    _guard(action, json_mode)


@calibration_app.command("morris-screen")
def calibration_morris_screen(
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Fresh evidence directory."),
    trajectories: int = typer.Option(2, "--trajectories", min=1),
    levels: int = typer.Option(4, "--levels", min=3),
    seed: int = typer.Option(1729, "--seed", min=0),
    model_seed: int | None = typer.Option(None, "--model-seed", min=0),
    json_mode: bool = JsonOption,
) -> None:
    """Screen declared structural inputs with Morris elementary effects."""

    def action() -> None:
        from hsm_lab.calibration.morris import run_structural_morris

        root = _repo_root()
        target = _fresh_output_dir(output_dir, "p06-morris")
        payload = run_structural_morris(
            root,
            target,
            trajectories=trajectories,
            levels=levels,
            seed=seed,
            model_seed=model_seed,
        )
        _emit(
            payload,
            json_mode,
            [
                f"{effect['name']}: mu*={effect['mu_star']:.6g} sigma={effect['sigma']:.6g}"
                for effect in payload["effects"]
            ],
        )

    _guard(action, json_mode)


@calibration_app.command("bundle")
def calibration_bundle(
    run_dir: Path = typer.Option(..., "--run-dir", help="Completed material run directory."),
    bundle_dir: Path = typer.Option(..., "--bundle-dir", help="New bundle destination."),
    json_mode: bool = JsonOption,
) -> None:
    """Assemble the reproducibility bundle for a recorded material run."""

    def action() -> None:
        from hsm_lab.calibration.reproducibility_bundle import assemble_reproducibility_bundle

        root = _repo_root()
        source = run_dir if run_dir.is_absolute() else root / run_dir
        target = bundle_dir if bundle_dir.is_absolute() else root / bundle_dir
        target = _fresh_output_dir(target, "p06-bundle")
        payload = assemble_reproducibility_bundle(root, source, target)
        payload["status"] = "assembled"
        payload["bundle_dir"] = str(target)
        _emit(payload, json_mode, [f"bundle: {target}"])

    _guard(action, json_mode)


@calibration_app.command("bundle-verify")
def calibration_bundle_verify(
    bundle_dir: Path = typer.Option(..., "--bundle-dir", help="Captured bundle directory."),
    replay_dir: Path = typer.Option(..., "--replay-dir", help="New replay output directory."),
    json_mode: bool = JsonOption,
) -> None:
    """Rebuild a recorded digest from a captured reproducibility bundle."""

    def action() -> None:
        from hsm_lab.calibration.reproducibility_bundle import verify_reproducibility_bundle

        root = _repo_root()
        bundle = bundle_dir if bundle_dir.is_absolute() else root / bundle_dir
        replay = replay_dir if replay_dir.is_absolute() else root / replay_dir
        replay = _fresh_output_dir(replay, "p06-bundle-replay")
        payload = verify_reproducibility_bundle(root, bundle, replay)
        _emit(payload, json_mode, [f"bundle replay: {payload['status']}"])

    _guard(action, json_mode)


@calibration_app.command("reproduction-table")
def calibration_reproduction_table(
    output_dir: Path = typer.Option(
        ..., "--output-dir", help="New reproduction-table output directory."
    ),
    json_mode: bool = JsonOption,
) -> None:
    """Compare only mapped P05 targets in the open calibration/validation windows."""

    def action() -> None:
        from hsm_lab.calibration.reproduction_table import run_reproduction_table

        root = _repo_root()
        target = _fresh_output_dir(output_dir, "p06-reproduction-table")
        payload = run_reproduction_table(root, target)
        _emit(
            payload,
            json_mode,
            [
                "crosswalk counts: "
                + ", ".join(f"{key}={value}" for key, value in payload["crosswalk_counts"].items()),
                "; ".join(
                    f"{item['variable_id']}: {item['overall_verdict']}"
                    for item in payload["variable_summaries"]
                ),
            ],
        )

    _guard(action, json_mode)


@calibration_app.command("audit-leak")
def calibration_audit_leak(
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Fresh output directory."),
    until: str | None = typer.Option(None, "--until", help="Inclusive stop quarter YYYYQn."),
    json_mode: bool = JsonOption,
) -> None:
    """Observe the unchanged P05 baseline's money and commodity circuits."""

    def action() -> None:
        from hsm_lab.calibration.leak_audit import run_leak_audit
        from hsm_lab.data.registry import DataRegistry

        root = _repo_root()
        contract = load_research_contract(root)
        spec = load_scenario(root, "historical_f2_replay")
        registry = DataRegistry.load(root, allowed_commodities=spec.commodities)
        target = _fresh_output_dir(output_dir, "p05-leak-audit")
        payload = run_leak_audit(spec, contract, registry, output_dir=target, until=until)
        _emit(payload, json_mode, [f"Circuit observations: {target}"])

    _guard(action, json_mode)


@calibration_app.command("p06-clearance")
def calibration_p06_clearance(
    output: Path = typer.Option(
        Path("docs/phases/P06_CLEARANCE.md"), "--output", help="Checklist document to write."
    ),
    with_runs: bool = typer.Option(
        False, "--with-runs", help="Also reproduce the legacy digest (adds one 116-tick run)."
    ),
    json_mode: bool = JsonOption,
) -> None:
    """Evaluate the declared P06 clearance checklist and write the document."""

    def action() -> None:
        from hsm_lab.calibration.clearance import render_markdown, run_clearance

        root = _repo_root()
        report = run_clearance(root, with_runs=with_runs)
        target = Path(output)
        if not target.is_absolute():
            target = root / target
        target.write_text(render_markdown(report))
        payload = report.as_dict()
        payload["checklist_path"] = str(target)
        _emit(
            payload,
            json_mode,
            [
                f"{item.id}: {item.status} - {item.evidence}"
                for item in report.items
            ]
            + [f"cleared: {report.cleared}"],
        )
        if report.open_items:
            raise typer.Exit(1)

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
    deterministic_identity: bool = typer.Option(
        False,
        "--deterministic-identity",
        help="Content-addressed run id, fixed clock and byte-stable trajectory tables.",
    ),
    fixed_clock: str | None = typer.Option(
        None,
        "--fixed-clock",
        help="ISO-8601 clock for deterministic identity (default 1970-01-01T00:00:00Z).",
    ),
    socioverse: bool = typer.Option(
        False,
        "--socioverse",
        help="Drive a P04 run through the real SocioVerse2 longitudinal simulator.",
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
            "--deterministic-identity": deterministic_identity if deterministic_identity else None,
            "--fixed-clock": fixed_clock,
            "--socioverse": socioverse if socioverse else None,
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
                if deterministic_identity or fixed_clock is not None:
                    raise ConfigError(
                        "--deterministic-identity/--fixed-clock currently apply only to "
                        "material runs without the political layer"
                    )
                if socioverse:
                    from hsm_lab.integrations.socioverse import run_political_socioverse

                    manifest = run_political_socioverse(
                        spec,
                        target_dir,
                        contract,
                        registry,
                        until=until,
                        checkpoint_every=checkpoint_every,
                        resume_from=resume,
                    )
                else:
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
                    deterministic_identity=deterministic_identity,
                    fixed_clock=fixed_clock,
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
        # The profile family is fixed by the scenario's own recipe (P02 material
        # catalogs use p02_*, the F2 historical catalog uses p05_*); a count-only
        # switch must stay inside that family or the organization set silently
        # stops matching the catalog the run declares.
        family_sizes: dict[str, tuple[int, ...]] = {"p02": (100, 200, 400), "p05": (300, 400, 450)}
        recipe_for_family = spec.organization_recipe
        family = (
            recipe_for_family.profile.rsplit("_", 1)[0]
            if recipe_for_family is not None and "_" in recipe_for_family.profile
            else "p02"
        )
        sizes = family_sizes.get(family)
        if sizes is None:
            raise ConfigError(
                f"scenario organization profile {recipe_for_family.profile!r} has no "
                "count switch family; switch the profile in the config instead"
            )
        profiles: dict[int, OrganizationProfile] = {n: f"{family}_{n}" for n in sizes}
        profile = profiles.get(organizations)
        if profile is None:
            raise ConfigError(
                f"--organizations must be one of {'/'.join(str(n) for n in sizes)} for the "
                f"{family} profile family, got {organizations}"
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
        if manifest.run_kind not in ("material_household_simulation", "p04_political_simulation"):
            raise ResearchGateError(
                "summary reads material_household_simulation and p04_political_simulation "
                f"runs, got {manifest.run_kind!r}"
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


@data_app.command("reconstruct-p05")
def data_reconstruct_p05(
    config: Path = typer.Option(
        Path("config/calibration/p05.json"),
        "--config",
        help="P05 research control file (windows and registry references).",
    ),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Fresh output directory."),
    json_mode: bool = JsonOption,
) -> None:
    """Audit the mandatory 1957 initial anchors declared by the frozen manifest."""

    def action() -> None:
        import json as _json

        from hsm_lab.data.reconstruct import reconstruct_p05

        root = _repo_root()
        target = _fresh_output_dir(output_dir, "p05-reconstruct")
        payload = reconstruct_p05(root, config=config)
        target.mkdir(parents=True, exist_ok=False)
        (target / "reconstruct.json").write_text(
            _json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _emit(
            {**payload, "output_dir": str(target)},
            json_mode,
            [
                f"reconstruct {payload['status']}: {payload['declared_anchors']} anchors "
                f"declared, missing {payload['missing_mandatory']}"
            ],
        )

    _guard(action, json_mode)


@data_app.command("freeze-p05")
def data_freeze_p05(
    config: Path = typer.Option(
        Path("config/calibration/p05.json"),
        "--config",
        help="P05 research control file (windows, tolerances, registry references).",
    ),
    json_mode: bool = JsonOption,
) -> None:
    """Seal DATA_MANIFEST_v1 and the P05 target/hold-out/parameter registries."""

    def action() -> None:
        from hsm_lab.data.history import freeze_data_manifest

        root = _repo_root()
        payload = freeze_data_manifest(root, config=config)
        _emit(
            {"command": "data freeze-p05", **payload},
            json_mode,
            [
                f"frozen {payload['artifact_count']} artifacts "
                f"({payload['targets']['calibration']} calibration, "
                f"{payload['targets']['holdout']} hold-out); "
                f"missing required {len(payload['missing_required'])}"
            ],
        )

    _guard(action, json_mode)


@data_app.command("ingest")
def data_ingest(
    source: str = typer.Option(
        ..., "--source", help="One ingestion source id from the fixed allowlist."
    ),
    start: str | None = typer.Option(
        None, "--start", help="Inclusive start year (YYYY) overriding the default window."
    ),
    end: str | None = typer.Option(
        None, "--end", help="Inclusive end year (YYYY) overriding the default window."
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
        default_start, default_end = INGEST_DEFAULT_WINDOWS[source]
        window_start = default_start if start is None else start
        window_end = default_end if end is None else end
        for flag, value in (("--start", start), ("--end", end)):
            if value is not None and (len(value) != 4 or not value.isdigit()):
                raise ConfigError(f"{flag} must be a four-digit year, got {value!r}")
        if window_start > window_end:
            raise ConfigError(f"ingestion window start {window_start} is after end {window_end}")
        root = _repo_root()
        report = ingest_source(
            root,
            IngestionRequest(
                source_id=source,
                start=window_start,
                end=window_end,
                offline=offline,
                refresh=refresh,
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
        from hsm_lab.data.registry import DataRegistry
        from hsm_lab.engine.political_run import run_political
        from hsm_lab.storage.fork import load_counterfactual_origin

        root = _repo_root()
        contract = load_research_contract(root)
        metadata_path = checkpoint / "metadata.json"
        if not metadata_path.is_file():
            raise ResearchGateError(f"fork source is not a checkpoint directory: {checkpoint}")
        from hsm_lab.storage.fork import (
            inherited_interventions_of,
            parse_parent_scenario,
            resolve_root_base_mode,
        )

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        parent = parse_parent_scenario(metadata)
        root_base_mode = resolve_root_base_mode(metadata)
        already_in_force = inherited_interventions_of(metadata)
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
        origin = load_counterfactual_origin(
            checkpoint,
            child,
            contract,
            interventions=specs,
            inherited_interventions=already_in_force,
            root_base_mode=root_base_mode,
        )
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


@benchmark_app.command("f2")
def benchmark_f2(
    config: Path = typer.Option(
        Path("config/benchmarks/f2.json"),
        "--config",
        help="F2 benchmark config (16-commodity historical catalog).",
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Fresh directory for the benchmark report."
    ),
    json_mode: bool = JsonOption,
) -> None:
    """F2 historical-model benchmark (16-commodity catalog, P05 §G)."""
    del config  # the harness resolves config/benchmarks/f2.json from the repo root
    _run_benchmark("f2", output_dir, json_mode)


def main() -> None:  # console entry: hsm = hsm_lab.cli.app:main
    app()


if __name__ == "__main__":
    main()
