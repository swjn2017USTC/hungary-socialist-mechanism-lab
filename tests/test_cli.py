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
            [str(console_script), "--help"], cwd=REPO_ROOT, env=_env(),
            capture_output=True, text=True, timeout=60,
        )
        assert script.returncode == 0
        assert "doctor" in script.stdout
    assert "doctor" in module.stdout
    assert "run" in module.stdout
    assert "benchmark" in module.stdout


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
        proc = hsm("run", "--scenario", "smoke", *args,
                   "--output-dir", str(tmp_path / name), "--json")
        assert proc.returncode == 0, proc.stderr
        results[name] = json.loads(proc.stdout)
    assert results["a"]["deterministic_replay_digest"] == results["full"][
        "deterministic_replay_digest"
    ]
    assert results["a"]["deterministic_replay_digest"] != results["c"][
        "deterministic_replay_digest"
    ]
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
    assert payload["artifacts_registered"] == 0
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
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0
