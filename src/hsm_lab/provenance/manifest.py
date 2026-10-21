"""Run manifests and canonical digests (BASELINE §35).

Every formal run writes a ``status=running`` manifest immediately after its
output directory exists, and rewrites it atomically (temp file + os.replace)
as ``completed`` or ``failed`` once evidence exists. Input validation failures
happen *before* any directory is created, so no fake completed run can appear.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal

from hsm_lab.contract.guards import sha256_file
from hsm_lab.contract.schemas import (
    OutputPolicy,
    PoliticalMode,
    ResearchContract,
    ScenarioSpec,
    StrictModel,
)

MANIFEST_FILENAME = "manifest.json"
TRACKED_DEPENDENCIES = (
    "numpy",
    "scipy",
    "polars",
    "duckdb",
    "pyarrow",
    "pydantic",
    "PyYAML",
    "socioverse2",
    "networkx",
    "SALib",
    "pyabc",
    "typer",
)

_CANONICAL_KW: dict[str, Any] = {
    "sort_keys": True,
    "separators": (",", ":"),
    "ensure_ascii": False,
    "allow_nan": False,
}


def canonical_json(value: Any) -> bytes:
    """Deterministic UTF-8 JSON bytes used for every digest in this project."""
    return json.dumps(value, **_CANONICAL_KW).encode("utf-8")


def canonical_digest(value: Any) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(value)).hexdigest()


def content_addressed_run_id(payload: dict[str, Any]) -> str:
    """Return a deterministic 32-hex run id from declared run identity.

    The id intentionally excludes wall-clock time, output directory, and process
    ids.  It is opt-in: the default runner still uses a random uuid so legacy
    provenance semantics are unchanged.
    """
    return canonical_digest(payload)[:32]


def capture_environment() -> dict[str, Any]:
    dependency_versions = {}
    for name in TRACKED_DEPENDENCIES:
        try:
            dependency_versions[name] = version(name)
        except PackageNotFoundError:  # pragma: no cover - frozen env always has them
            dependency_versions[name] = "<missing>"
    machine = platform.machine()
    memory_bytes: int | None = None
    try:
        memory_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):  # pragma: no cover - non-POSIX
        memory_bytes = None
    return {
        "python": sys.version,
        "python_version": ".".join(str(part) for part in sys.version_info[:3]),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": machine,
            "arm64": machine == "arm64",
            "memory_bytes": memory_bytes,
        },
        "dependency_versions": dependency_versions,
    }


def capture_git(root: Path) -> dict[str, Any]:
    note: str | None = None
    commit: str | None = None
    try:
        commit_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        commit = commit_proc.stdout.strip()
        status_proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        dirty = bool(status_proc.stdout.strip())
    except (OSError, subprocess.SubprocessError) as exc:
        commit = None
        dirty = False
        note = f"git unavailable: {exc}"
    return {"git_commit": commit, "dirty_tree": dirty, "git_note": note}


def compute_lock_hash(root: Path) -> str:
    lock = root / "uv.lock"
    if not lock.is_file():
        raise RuntimeError(f"uv.lock not found at {lock}: formal runs require a frozen lock")
    return sha256_file(lock)


def compute_scenario_hash(spec: ScenarioSpec) -> str:
    return canonical_digest(spec.model_dump(mode="json"))


def compute_data_manifest_hash(root: Path) -> str:
    manifests = root / "data" / "manifests"
    payload = {}
    for name in ("sources.yml", "variables.yml", "artifacts.yml"):
        path = manifests / name
        if not path.is_file():
            raise RuntimeError(f"data manifest missing: {path}")
        payload[name] = sha256_file(path)
    return canonical_digest(payload)


def compute_parameter_hash(parameter_vector: dict[str, float]) -> str:
    return canonical_digest(parameter_vector)


def hash_output_tree(run_dir: Path) -> dict[str, str]:
    """SHA-256 per output file (recursive); root manifest and staging excluded.

    Keys are repo-relative POSIX paths, so nested checkpoint payload files are
    hashed individually. Directory inodes and half-written ``.tmp-*`` staging
    directories never enter the map.
    """
    hashes: dict[str, str] = {}
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        if path == run_dir / MANIFEST_FILENAME:
            continue
        if any(part.startswith(".tmp-") for part in path.relative_to(run_dir).parts):
            continue
        key = path.relative_to(run_dir).as_posix()
        hashes[key] = sha256_file(path)
    return hashes


class RunManifest(StrictModel):
    """BASELINE §35 fields plus P00/P01 extensions."""

    schema_version: Literal["1"] = "1"
    run_id: str
    run_kind: Literal[
        "synthetic_engine_smoke",
        "toy4_f0_simulation",
        "material_household_simulation",
        "p04_political_simulation",
    ] = "synthetic_engine_smoke"
    political_mode: PoliticalMode | None = None
    # P05 §195: ontology/fidelity/retention and the calibration snapshots are
    # kept separate from the input/provenance hashes and from the replay
    # behaviour digest; the output policy never enters the behaviour digest.
    ontology_id: str | None = None
    fidelity: Literal["f1", "f2"] | None = None
    retention: str | None = None
    initial_ensemble_hash: str | None = None
    inference_snapshot_hash: str | None = None
    target_split_hash: str | None = None
    parent_version_id: str | None = None
    version_id: str | None = None
    study_id: str | None = None
    counterfactual_base: str | None = None
    step_offset: int = 0
    socioverse_version: str | None = None
    status: Literal["running", "completed", "paused", "failed"]
    failure_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    baseline_version: str
    baseline_hash: str
    git_commit: str | None
    dirty_tree: bool
    git_note: str | None = None
    python: str
    platform: dict[str, Any]
    lock_hash: str
    scenario_hash: str
    data_manifest_hash: str
    parameter_hash: str
    seed: int
    households: int
    enterprises: int | None = None
    organizations: int | None = None
    ticks: int
    commodity_ids: list[str]
    region_ids: list[str]
    output_policy: OutputPolicy
    output_hashes: dict[str, str] = {}
    rng_scheme_version: str
    rng_draws_count: int = 0
    rng_draws_by_module: dict[str, int] = {}
    stochastic_modules_active: list[str] = []
    deterministic_replay_digest: str = ""
    dependency_versions: dict[str, str]
    research_warnings: list[str]
    engine_version: str | None = None
    completed_ticks: int = 0
    last_completed_quarter: str | None = None
    input_artifact_hashes: dict[str, str] = {}
    initial_recipe_hash: str | None = None
    parent_run_id: str | None = None
    resumed_from_checkpoint: str | None = None


def write_manifest_atomic(run_dir: Path, manifest: RunManifest) -> Path:
    """Write the manifest via temp file + atomic replace (no half-written file)."""
    target = run_dir / MANIFEST_FILENAME
    temp = run_dir / f"{MANIFEST_FILENAME}.tmp"
    payload = json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    temp.write_text(payload, encoding="utf-8")
    os.replace(temp, target)
    return target


def p05_manifest_fields(root: Path, spec: Any) -> dict[str, Any]:
    """P05 §195 ontology/fidelity/retention/target-split decorations.

    Kept out of the replay behaviour digest: the output policy never changes the
    seed draw, and these fields only label which ontology/fidelity a run belongs
    to and which sealed target split it was admitted against.
    """
    from hsm_lab.contract.guards import sha256_bytes
    from hsm_lab.contract.material import catalog_for_commodities

    catalog = catalog_for_commodities(list(spec.commodities))
    ontology_id = catalog.catalog_id
    split_paths = (
        root / "data" / "manifests" / "p05_targets.yml",
        root / "data" / "manifests" / "p05_holdout.yml",
    )
    return {
        "ontology_id": ontology_id,
        "fidelity": "f2" if ontology_id.startswith("f2") else "f1",
        "retention": spec.output_policy.value,
        "target_split_hash": (
            sha256_bytes(b"".join(path.read_bytes() for path in split_paths))
            if all(path.is_file() for path in split_paths)
            else None
        ),
    }


def manifest_preamble(
    *,
    run_id: str,
    spec: ScenarioSpec,
    contract: ResearchContract,
    root: Path,
    baseline_hash: str,
    run_kind: Literal[
        "synthetic_engine_smoke",
        "toy4_f0_simulation",
        "material_household_simulation",
        "p04_political_simulation",
    ] = "synthetic_engine_smoke",
    parameter_vector: dict[str, float] | None = None,
    input_artifact_hashes: dict[str, str] | None = None,
    initial_recipe_hash: str | None = None,
    engine_version: str | None = None,
    parent_run_id: str | None = None,
    resumed_from_checkpoint: str | None = None,
    ontology_id: str | None = None,
    fidelity: Literal["f1", "f2"] | None = None,
    retention: str | None = None,
    initial_ensemble_hash: str | None = None,
    inference_snapshot_hash: str | None = None,
    target_split_hash: str | None = None,
    started_at: datetime | None = None,
) -> RunManifest:
    """Assemble the status=running manifest right after the run directory exists.

    ``started_at`` is injectable so a deterministic-identity run can use a fixed
    clock.  ``None`` preserves the legacy wall-clock behavior.
    """
    env = capture_environment()
    git = capture_git(root)
    return RunManifest(
        run_id=run_id,
        run_kind=run_kind,
        ontology_id=ontology_id,
        fidelity=fidelity,
        retention=retention,
        initial_ensemble_hash=initial_ensemble_hash,
        inference_snapshot_hash=inference_snapshot_hash,
        target_split_hash=target_split_hash,
        status="running",
        started_at=started_at if started_at is not None else datetime.now(UTC),
        baseline_version=contract.baseline_version,
        baseline_hash=baseline_hash,
        git_commit=git["git_commit"],
        dirty_tree=git["dirty_tree"],
        git_note=git["git_note"],
        python=env["python"],
        platform=env["platform"],
        lock_hash=compute_lock_hash(root),
        scenario_hash=compute_scenario_hash(spec),
        data_manifest_hash=compute_data_manifest_hash(root),
        parameter_hash=compute_parameter_hash(parameter_vector or {}),
        seed=spec.seed,
        households=spec.households,
        enterprises=spec.enterprises,
        organizations=spec.organizations,
        ticks=spec.ticks,
        commodity_ids=list(spec.commodities),
        region_ids=list(spec.region_ids),
        output_policy=spec.output_policy,
        rng_scheme_version="pcg64-sha256-module-v1",
        dependency_versions=env["dependency_versions"],
        research_warnings=list(contract.research_warnings),
        engine_version=engine_version,
        input_artifact_hashes=dict(input_artifact_hashes or {}),
        initial_recipe_hash=initial_recipe_hash,
        parent_run_id=parent_run_id,
        resumed_from_checkpoint=resumed_from_checkpoint,
    )


def finalize_manifest(
    running: RunManifest,
    *,
    status: Literal["completed", "paused", "failed"],
    output_hashes: dict[str, str],
    rng_draws_count: int,
    rng_draws_by_module: dict[str, int],
    stochastic_modules_active: list[str],
    deterministic_replay_digest: str,
    failure_message: str | None = None,
    completed_ticks: int | None = None,
    last_completed_quarter: str | None = None,
    finished_at: datetime | None = None,
) -> RunManifest:
    """Return the terminal manifest with evidence fields filled in.

    ``paused`` may carry a valid prefix digest; ``failed`` always carries an
    empty terminal digest. A paused run is never relabelled completed.
    """
    if completed_ticks is None and status == "completed":
        completed_ticks = running.ticks
    return running.model_copy(
        update={
            "status": status,
            "finished_at": finished_at if finished_at is not None else datetime.now(UTC),
            "failure_message": failure_message,
            "output_hashes": dict(output_hashes),
            "rng_draws_count": rng_draws_count,
            "rng_draws_by_module": dict(rng_draws_by_module),
            "stochastic_modules_active": list(stochastic_modules_active),
            "deterministic_replay_digest": (
                deterministic_replay_digest if status != "failed" else ""
            ),
            "completed_ticks": completed_ticks if completed_ticks is not None else 0,
            "last_completed_quarter": last_completed_quarter,
        }
    )
