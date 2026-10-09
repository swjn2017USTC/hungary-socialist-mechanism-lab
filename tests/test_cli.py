"""D7: real CLI subprocess behaviour (exit codes, JSON, seeds, refusals)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import REPO_ROOT

STRIPPED_ENV_KEYS = ("OPENAI_API_KEY", "SV_LLM_API_KEY", "SV_EVENT_API_KEY", "SV_EVENT_API_URL")


def _env() -> dict[str, str]:
    env = dict(os.environ)
    for key in STRIPPED_ENV_KEYS:
        env.pop(key, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def hsm(*args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "hsm_lab", *args],
        cwd=cwd,
        env=_env(),
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_help_both_entrypoints() -> None:
    module = hsm("--help")
    assert module.returncode == 0
    console_script = Path(sys.executable).with_name("hsm")
    if console_script.is_file():
        script = subprocess.run(
            [str(console_script), "--help"],
            cwd=REPO_ROOT,
            env=_env(),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert script.returncode == 0
        assert "doctor" in script.stdout
    assert "doctor" in module.stdout
    assert "run" in module.stdout
    assert "benchmark" in module.stdout


def test_morris_screen_is_registered_as_a_calibration_command() -> None:
    proc = hsm("calibration", "--help")
    assert proc.returncode == 0, proc.stderr
    assert "morris-screen" in proc.stdout


def test_baseline_verify_json() -> None:
    proc = hsm("baseline", "verify", "--json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["status"] == "ok"
    assert payload["sha256"] == payload["expected_sha256"]


def test_baseline_verify_corrupted_copy(tmp_path) -> None:
    bad = tmp_path / "BASELINE.md"
    bad.write_text("drifted", encoding="utf-8")
    proc = hsm("baseline", "verify", "--path", str(bad), "--json")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "error"
    assert "hash drift" in payload["error"]


def test_doctor_json() -> None:
    proc = hsm("doctor", "--json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "ok"
    assert payload["failed_checks"] == []
    assert len(payload["checks"]) >= 15


def test_run_two_seeds_and_policies(tmp_path) -> None:
    results = {}
    for name, args in {
        "a": ["--seed", "1729"],
        "c": ["--seed", "1730"],
        "full": ["--seed", "1729", "--output-policy", "research_full"],
    }.items():
        proc = hsm(
            "run", "--scenario", "smoke", *args, "--output-dir", str(tmp_path / name), "--json"
        )
        assert proc.returncode == 0, proc.stderr
        results[name] = json.loads(proc.stdout)
    assert (
        results["a"]["deterministic_replay_digest"]
        == results["full"]["deterministic_replay_digest"]
    )
    assert (
        results["a"]["deterministic_replay_digest"] != results["c"]["deterministic_replay_digest"]
    )
    assert results["a"]["rng_draws_count"] == 42_000
    for name in results:
        assert results[name]["run_kind"] == "synthetic_engine_smoke"
        assert results[name]["status"] == "ok"
        assert (tmp_path / name / "manifest.json").is_file()


def test_unsupported_scenario_rejected(tmp_path) -> None:
    proc = hsm("run", "--scenario", "historical", "--output-dir", str(tmp_path / "h"), "--json")
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert "unsupported scenario" in payload["error"]
    assert not (tmp_path / "h").exists()


def test_existing_output_dir_rejected(tmp_path) -> None:
    target = tmp_path / "exists"
    target.mkdir()
    (target / "sentinel.txt").write_text("x", encoding="utf-8")
    proc = hsm("run", "--scenario", "smoke", "--output-dir", str(target), "--json")
    assert proc.returncode == 1
    assert "already exists" in json.loads(proc.stdout)["error"]
    assert (target / "sentinel.txt").read_text(encoding="utf-8") == "x"


def test_data_audit_offline() -> None:
    proc = hsm("data", "audit", "--json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["registry_valid"] is True
    assert payload["sources_ready"] is False
    assert "fred_fedfunds" in payload["blocked_or_unverified"]
    report = json.loads(Path(payload["report_path"]).read_text(encoding="utf-8"))
    assert report["gaps"][0]["status"] == "not_audited"


def test_missing_config_dir_is_error(tmp_path) -> None:
    proc = hsm("baseline", "verify", "--json", cwd=tmp_path)
    assert proc.returncode == 1
    assert "repository root" in json.loads(proc.stdout)["error"]


def test_cli_needs_no_api_keys(tmp_path) -> None:
    env = _env()
    assert not any(key in env for key in STRIPPED_ENV_KEYS)
    proc = subprocess.run(
        [sys.executable, "-m", "hsm_lab", "doctor", "--json"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0


def test_toy4_scenario_refused(tmp_path) -> None:
    """The deleted Toy-4 scenario exits 2 with one JSON object, before any run."""
    proc = hsm(
        "run",
        "--scenario",
        "toy4",
        "--output-dir",
        str(tmp_path / "n"),
        "--json",
    )
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["status"] == "error"
    assert payload["exit_code"] == 2
    assert "toy4" in payload["error"] and "intermediate8" in payload["error"]
    assert not (tmp_path / "n").exists()


def test_material_json_error_surface_for_bad_option(tmp_path) -> None:
    """Invalid option ranges must still emit one JSON object on stdout (exit 2),
    never a bare human Typer error."""
    proc = hsm(
        "run",
        "--scenario",
        "intermediate8",
        "--households",
        "999",
        "--output-dir",
        str(tmp_path / "n"),
        "--json",
    )
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["status"] == "error"
    assert payload["exit_code"] == 2
    assert "households" in payload["error"]
    assert not (tmp_path / "n").exists()


def test_material_organizations_only_defined_profiles(tmp_path) -> None:
    proc = hsm(
        "run",
        "--scenario",
        "intermediate8",
        "--organizations",
        "300",
        "--output-dir",
        str(tmp_path / "o"),
        "--json",
    )
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert "100/200/400" in payload["error"]
    assert not (tmp_path / "o").exists()


def test_material_resume_with_override_refused(tmp_path, monkeypatch) -> None:
    """--resume refuses seed/households/organizations/policy overrides before
    the engine module is ever imported."""
    from typer.testing import CliRunner

    from hsm_lab.cli.app import app

    monkeypatch.chdir(REPO_ROOT)
    runner = CliRunner()
    conflict = runner.invoke(
        app,
        [
            "run",
            "--scenario",
            "intermediate8",
            "--resume",
            str(tmp_path / "missing-ckpt"),
            "--seed",
            "9",
            "--output-dir",
            str(tmp_path / "r"),
            "--json",
        ],
    )
    assert conflict.exit_code == 2
    assert "--resume" in json.loads(conflict.stdout)["error"]
    assert not (tmp_path / "r").exists()


def _fake_material_run_dir(tmp_path: Path, *, tamper: bool = False) -> Path:
    """A syntactically valid finished material run directory."""
    import hashlib

    from hsm_lab.provenance.manifest import RunManifest

    run_dir = tmp_path / "material-run"
    run_dir.mkdir()
    summary = {
        "schema_version": "1",
        "run_id": "run0001",
        "run_kind": "material_household_simulation",
        "scenario_id": "intermediate8",
        "planned_ticks": 2,
        "completed_ticks": 2,
        "horizon_reached": True,
        "seed": 1729,
        "deterministic_replay_digest": "digest-abc",
        "by_commodity": {"food": {"production": 10.0}},
        "invariants": {"max_material_abs_residual": 0.0},
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    manifest = RunManifest.model_validate(
        {
            "run_id": "run0001",
            "run_kind": "material_household_simulation",
            "status": "completed",
            "started_at": "2026-01-01T00:00:00Z",
            "finished_at": "2026-01-01T00:00:01Z",
            "baseline_version": "v1",
            "baseline_hash": "0" * 64,
            "git_commit": None,
            "dirty_tree": False,
            "python": "3.12",
            "platform": {},
            "lock_hash": "0" * 64,
            "scenario_hash": "0" * 64,
            "data_manifest_hash": "0" * 64,
            "parameter_hash": "0" * 64,
            "seed": 1729,
            "households": 5000,
            "organizations": 200,
            "ticks": 2,
            "commodity_ids": ["energy"],
            "region_ids": ["r0"],
            "output_policy": "ensemble_compact",
            "rng_scheme_version": "pcg64-sha256-module-v1",
            "dependency_versions": {},
            "research_warnings": [],
            "engine_version": "material-engine-v2",
            "completed_ticks": 2,
            "deterministic_replay_digest": "digest-abc",
            "output_hashes": {
                "summary.json": hashlib.sha256(summary_path.read_bytes()).hexdigest()
            },
        }
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    if tamper:
        # rewrite economic bytes AFTER the manifest recorded the authentic hash
        tampered = json.loads(summary_path.read_text())
        tampered["by_commodity"]["food"]["production"] = 123456789.0
        summary_path.write_text(json.dumps(tampered, indent=2, sort_keys=True) + "\n")
    return run_dir


def test_summary_refuses_toy4_run_kind(tmp_path) -> None:
    run_dir = _fake_material_run_dir(tmp_path)
    manifest = json.loads((run_dir / "manifest.json").read_text())
    manifest["run_kind"] = "toy4_f0_simulation"
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    proc = hsm("summary", "--run-dir", str(run_dir), "--json")
    assert proc.returncode == 1
    assert "material_household_simulation" in json.loads(proc.stdout)["error"]


def test_summary_refuses_tampered_economic_field(tmp_path) -> None:
    run_dir = _fake_material_run_dir(tmp_path, tamper=True)
    proc = hsm("summary", "--run-dir", str(run_dir), "--json")
    assert proc.returncode == 1
    assert "recorded output hash" in json.loads(proc.stdout)["error"]


def test_summary_reads_authentic_material_run(tmp_path) -> None:
    run_dir = _fake_material_run_dir(tmp_path)
    proc = hsm("summary", "--run-dir", str(run_dir), "--json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["run_kind"] == "material_household_simulation"
    assert payload["completed_ticks"] == 2
    human = hsm("summary", "--run-dir", str(run_dir))
    assert human.returncode == 0
    assert "material summary" in human.stdout and "food" in human.stdout


def test_data_ingest_fred_rights_blocked_zero_network(tmp_path) -> None:
    proc = hsm("data", "ingest", "--source", "fred_fedfunds", "--json")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "error"
    assert "rights-blocked" in payload["error"]
    assert "no network call" in payload["error"]


def test_data_ingest_rejects_unknown_source_and_flag_conflict() -> None:
    unknown = hsm("data", "ingest", "--source", "not_a_source", "--json")
    assert unknown.returncode == 2
    assert "allowlist" in json.loads(unknown.stdout)["error"]
    conflict = hsm("data", "ingest", "--source", "ksh_gdp", "--offline", "--refresh", "--json")
    assert conflict.returncode == 2
    assert "mutually exclusive" in json.loads(conflict.stdout)["error"]


def test_help_lists_new_material_commands() -> None:
    data_help = hsm("data", "--help")
    assert data_help.returncode == 0
    assert "ingest" in data_help.stdout
    assert "build-material-forcing" in data_help.stdout
    benchmark_help = hsm("benchmark", "--help")
    assert benchmark_help.returncode == 0
    assert "material" in benchmark_help.stdout
    assert "toy4" not in benchmark_help.stdout
