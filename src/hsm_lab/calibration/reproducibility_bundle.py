"""Build and replay a self-contained, hash-checked P05 run bundle.

Only material runs ending by 1985Q4 are admitted. The bundle records model
inputs and the supplied report, but never reads target artifacts (including
hold-out or reserved targets). Verification reruns the recorded scenario from
its captured configuration and parameters in a fresh output directory.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from hsm_lab.contract.guards import AVAILABLE_SCENARIOS, load_research_contract, sha256_file
from hsm_lab.contract.material import MaterialParameters
from hsm_lab.contract.schemas import ResearchGateError, ScenarioSpec
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.material import run_material
from hsm_lab.provenance.manifest import RunManifest, canonical_json

_REQUIRED_RUN_FILES = ("manifest.json", "parameters.json", "initial_recipe.json", "summary.json")
_REGISTRY_FILES = (
    "data/manifests/artifacts.yml",
    "data/manifests/sources.yml",
    "data/manifests/variables.yml",
)
_SECRET_MARKERS = (".env", "secret", "credential", "token", "private_key", "id_rsa")


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchGateError(f"cannot load bundle input {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ResearchGateError(f"expected a JSON object in {path}")
    return payload


def _safe_repo_file(root: Path, rel: str) -> Path:
    candidate = (root / rel).resolve()
    if root.resolve() not in candidate.parents:
        raise ResearchGateError(f"bundle input escapes repository: {rel!r}")
    if any(marker in part.lower() for part in Path(rel).parts for marker in _SECRET_MARKERS):
        raise ResearchGateError(f"refusing to bundle a secret-like path: {rel!r}")
    if not candidate.is_file():
        raise ResearchGateError(f"required bundle input is missing: {rel}")
    return candidate


def _last_quarter(start: str, ticks: int) -> tuple[int, int]:
    year, quarter = int(start[:4]), int(start[-1])
    total = year * 4 + quarter - 1 + ticks - 1
    return total // 4, total % 4 + 1


def _recorded_files(root: Path, run_dir: Path, manifest: RunManifest) -> dict[str, Path]:
    if manifest.run_kind != "material_household_simulation":
        raise ResearchGateError("D5 currently supports material_household_simulation runs only")
    if manifest.status != "completed":
        raise ResearchGateError("only completed runs can be bundled")
    summary = _json(run_dir / "summary.json")
    scenario_id = summary.get("scenario_id")
    if scenario_id not in AVAILABLE_SCENARIOS:
        raise ResearchGateError(f"unregistered run scenario: {scenario_id!r}")
    if not manifest.last_completed_quarter or manifest.last_completed_quarter > "1985Q4":
        raise ResearchGateError("run extends beyond the closed 1985Q4 boundary")

    files: dict[str, Path] = {}
    scenario_rel = f"config/scenarios/{scenario_id}.json"
    files[scenario_rel] = _safe_repo_file(root, scenario_rel)
    config_files = [
        "config/research_contract.json",
        "config/calibration/p05.json",
        "config/calibration/p05_parameters.yml",
        "BASELINE.md",
        *_REGISTRY_FILES,
    ]
    if manifest.ontology_id:
        ontology_rel = f"config/ontology/{manifest.ontology_id}.json"
        if (root / ontology_rel).is_file():
            config_files.append(ontology_rel)
    for rel in config_files:
        files[rel] = _safe_repo_file(root, rel)

    scenario = _json(files[scenario_rel])
    if scenario.get("forcing_pack"):
        rel = str(scenario["forcing_pack"])
        files[rel] = _safe_repo_file(root, rel)

    # Include only artifacts declared as run inputs, and admit only forcing or
    # initial-state roles. Target artifacts are never opened or copied here.
    if manifest.input_artifact_hashes:
        registry = DataRegistry.load(root, allowed_commodities=scenario.get("commodities", []))
        for artifact_id, expected_hash in sorted(manifest.input_artifact_hashes.items()):
            artifact = registry.artifacts.get(artifact_id)
            if artifact is None or artifact.role.value not in (
                "exogenous_forcing",
                "initial_state",
            ):
                raise ResearchGateError(
                    f"run input {artifact_id!r} is not a forcing/initial artifact"
                )
            path = registry.resolve_path(artifact.path)
            if sha256_file(path) != expected_hash:
                raise ResearchGateError(f"run input hash mismatch for {artifact_id!r}")
            files[artifact.path] = path

    for name in _REQUIRED_RUN_FILES:
        path = run_dir / name
        if not path.is_file():
            raise ResearchGateError(f"run evidence is missing {name}")
        files[f"run/{name}"] = path
    report_path = _safe_repo_file(root, "docs/phases/P05_REPORT.md")
    if not report_path.is_file():
        raise ResearchGateError(f"report file is missing: {report_path}")
    files[f"report/{report_path.name}"] = report_path
    return files


def assemble_reproducibility_bundle(
    root: Path, run_dir: Path, bundle_dir: Path
) -> dict[str, object]:
    """Capture declared run inputs, report, hashes, parameters and digest."""
    root, run_dir = root.resolve(), run_dir.resolve()
    manifest_path = run_dir / "manifest.json"
    manifest = RunManifest.model_validate(_json(manifest_path))
    files = _recorded_files(root, run_dir, manifest)
    scenario_id = _json(run_dir / "summary.json")["scenario_id"]
    params = _json(run_dir / "parameters.json")
    if params.get("parameter_hash") != manifest.parameter_hash:
        raise ResearchGateError("parameters.json hash does not match the run manifest")
    if manifest.deterministic_replay_digest is None:
        raise ResearchGateError("run manifest has no deterministic replay digest")

    if bundle_dir.exists() and any(bundle_dir.iterdir()):
        raise ResearchGateError(f"bundle destination is not empty: {bundle_dir}")
    bundle_dir.mkdir(parents=True, exist_ok=True)
    file_records: dict[str, str] = {}
    for bundle_rel, source in sorted(files.items()):
        target = bundle_dir / bundle_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        file_records[bundle_rel] = sha256_file(target)

    payload: dict[str, object] = {
        "schema_version": 1,
        "run_id": manifest.run_id,
        "scenario_id": scenario_id,
        "parameter_hash": manifest.parameter_hash,
        "parameter_declaration_sha256": hashlib.sha256(
            canonical_json(params["declaration"])
        ).hexdigest(),
        "deterministic_replay_digest": manifest.deterministic_replay_digest,
        "run_manifest": manifest.model_dump(mode="json"),
        "captured_files": file_records,
        "no_manual_steps": {
            "passed": True,
            "selection": "manifest, scenario, declared configs, and standard P05 report",
        },
        "holdout_values_read": False,
        "reserved_values_read": False,
    }
    payload["bundle_sha256"] = hashlib.sha256(canonical_json(payload)).hexdigest()
    (bundle_dir / "bundle.json").write_bytes(canonical_json(payload) + b"\n")
    return payload


def verify_reproducibility_bundle(
    root: Path, bundle_dir: Path, replay_dir: Path
) -> dict[str, object]:
    """Check captured bytes and rerun the recorded model to reproduce its digest."""
    root, bundle_dir = root.resolve(), bundle_dir.resolve()
    payload = _json(bundle_dir / "bundle.json")
    expected_bundle_hash = payload.pop("bundle_sha256", None)
    actual_bundle_hash = hashlib.sha256(canonical_json(payload)).hexdigest()
    if actual_bundle_hash != expected_bundle_hash:
        raise ResearchGateError("bundle metadata digest mismatch")
    captured = payload.get("captured_files")
    if not isinstance(captured, dict) or not captured:
        raise ResearchGateError("bundle has no captured file inventory")
    for rel, expected in captured.items():
        path = (bundle_dir / rel).resolve()
        if bundle_dir not in path.parents or not path.is_file() or sha256_file(path) != expected:
            raise ResearchGateError(f"captured file missing or changed: {rel}")

    manifest = RunManifest.model_validate(payload["run_manifest"])
    scenario_id = payload.get("scenario_id")
    if scenario_id not in AVAILABLE_SCENARIOS:
        raise ResearchGateError(f"unregistered bundled scenario: {scenario_id!r}")
    scenario_path = bundle_dir / f"config/scenarios/{scenario_id}.json"
    spec_doc = _json(scenario_path)
    parameters = _json(bundle_dir / "run/parameters.json")
    declared = parameters.get("declaration")
    if not isinstance(declared, dict):
        raise ResearchGateError("captured parameters have no declaration")
    allowed = set(MaterialParameters.model_fields)
    spec_doc["material_parameters"] = {
        key: value for key, value in declared.items() if key in allowed
    }
    spec_doc.update(
        seed=manifest.seed,
        ticks=manifest.ticks,
        households=manifest.households,
        organizations=manifest.organizations,
        output_policy=manifest.output_policy,
    )
    spec = ScenarioSpec.model_validate(spec_doc)
    if _last_quarter(str(spec.start), spec.ticks) > (1985, 4):
        raise ResearchGateError("replay would enter the closed post-1985 period")
    if replay_dir.exists() and any(replay_dir.iterdir()):
        raise ResearchGateError(f"replay destination is not empty: {replay_dir}")
    contract = load_research_contract(root)
    registry = DataRegistry.load(root, allowed_commodities=spec.commodities)
    rebuilt = run_material(spec, replay_dir, contract, registry)
    digest_matches = rebuilt.deterministic_replay_digest == payload["deterministic_replay_digest"]
    parameter_matches = rebuilt.parameter_hash == payload["parameter_hash"]
    return {
        "status": "verified" if digest_matches and parameter_matches else "mismatch",
        "recorded_digest": payload["deterministic_replay_digest"],
        "rebuilt_digest": rebuilt.deterministic_replay_digest,
        "digest_matches": digest_matches,
        "parameter_hash_matches": parameter_matches,
        "run_id": manifest.run_id,
    }
