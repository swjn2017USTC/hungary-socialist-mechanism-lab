"""P05 data/F2 freeze (plan section B).

``freeze_data_manifest`` role-admits the declared research selection, records
per-artifact rights/units/frequency/window/digest evidence and splits the
declared targets into the calibration and hold-out registries.  It hashes the
artifacts but never reads a sealed target value, so a freeze cannot leak the
hold-out.  Once ``DATA_MANIFEST_v1.json`` exists the freeze refuses to run
again: any hash, parser, unit, window or ontology change must produce a new
manifest version instead of editing v1.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from hsm_lab.contract.guards import sha256_file
from hsm_lab.contract.schemas import TargetUse
from hsm_lab.data.registry import DataRegistry
from hsm_lab.data.schemas import (
    ForcingArtifact,
    InitialArtifact,
    ParameterArtifact,
    TargetArtifact,
)

MANIFEST_FILENAME = "DATA_MANIFEST_v1.json"
MANIFEST_KEY = "artifacts"
_REGISTRY_FILES = ("sources.yml", "variables.yml", "artifacts.yml")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def _yaml_doc(key: str, entries: list[dict[str, Any]]) -> str:
    return yaml.safe_dump(
        {"schema_version": "1", key: entries}, sort_keys=True, allow_unicode=True
    )


def _load_control(config: Path) -> dict[str, Any]:
    if not config.is_file():
        raise FileNotFoundError(f"P05 control file not found: {config}")
    control = json.loads(config.read_text(encoding="utf-8"))
    for key in ("ontology", "windows", "registries"):
        if key not in control:
            raise ValueError(f"P05 control file is missing the {key!r} block")
    return control


def _ontology_commodities(root: Path, rel: str) -> tuple[str, list[str]]:
    payload = json.loads((root / rel).read_text(encoding="utf-8"))
    commodities = [str(entry["id"]) for entry in payload["commodities"]]
    return str(payload["ontology_id"]), commodities


def _artifact_entry(root: Path, artifact: Any) -> dict[str, Any]:
    path = root / artifact.path
    present = path.is_file()
    digest = sha256_file(path) if present else None
    declared = artifact.provenance.artifact_sha256
    entry: dict[str, Any] = {
        "artifact_id": artifact.artifact_id,
        "role": artifact.role.value,
        "source_id": artifact.source_id,
        "variable_id": artifact.variable_id,
        "path": artifact.path,
        "present": present,
        "sha256": digest,
        "declared_sha256": declared,
        "digest_matches": None if digest is None else bool(digest == declared),
        "allow_missing": bool(artifact.allow_missing),
        "evidence_status": artifact.provenance.evidence_status.value,
        "original_frequency": artifact.provenance.original_frequency.value,
        "model_frequency": artifact.provenance.model_frequency.value,
        "source_period": artifact.provenance.source_period,
        "raw_path": artifact.provenance.raw_path,
        "rights": artifact.provenance.rights.model_dump(mode="json"),
    }
    if isinstance(artifact, TargetArtifact):
        entry["use"] = artifact.use.value
        entry["comparison_aggregation"] = artifact.comparison_aggregation
        entry["observed_period"] = artifact.observed_period.model_dump(mode="json")
    if isinstance(artifact, ForcingArtifact):
        entry["period"] = artifact.period.model_dump(mode="json")
    if isinstance(artifact, InitialArtifact):
        entry["grade"] = artifact.grade.value
        entry["initial_at"] = artifact.initial_at
        entry["observation_at"] = artifact.observation_at
        entry["anchor_ids"] = list(artifact.anchor_ids)
    if isinstance(artifact, ParameterArtifact):
        entry["literature_refs"] = list(artifact.literature_refs)
    return entry


def freeze_data_manifest(root: Path, *, config: Path) -> dict[str, object]:
    """Seal ``DATA_MANIFEST_v1`` and the P05 target/hold-out/parameter registries."""
    control = _load_control(config)
    ontology_id, commodities = _ontology_commodities(root, str(control["ontology"]))
    registry = DataRegistry.load(root, allowed_commodities=commodities)
    manifests_dir = root / "data" / "manifests"
    target_path = manifests_dir / MANIFEST_FILENAME
    if target_path.exists():
        raise FileExistsError(
            f"{MANIFEST_FILENAME} already exists; a changed freeze must use a new version"
        )

    entries = [
        _artifact_entry(root, artifact) for _, artifact in sorted(registry.artifacts.items())
    ]
    by_use: dict[str, list[str]] = {use.value: [] for use in TargetUse}
    for entry in entries:
        if "use" in entry:
            by_use[str(entry["use"])].append(str(entry["artifact_id"]))
    roles = Counter(str(entry["role"]) for entry in entries)
    missing = [e["artifact_id"] for e in entries if not e["present"] and not e["allow_missing"]]

    manifest: dict[str, object] = {
        "manifest_version": "DATA_MANIFEST_v1",
        "study": "P05",
        "ontology_id": ontology_id,
        "ontology_sha256": sha256_file(root / str(control["ontology"])),
        "control_sha256": sha256_file(config),
        "registry_sha256": {
            name: sha256_file(manifests_dir / name) for name in _REGISTRY_FILES
        },
        "artifact_count": len(entries),
        "role_counts": dict(sorted(roles.items())),
        "targets_by_use": {key: sorted(value) for key, value in sorted(by_use.items())},
        "missing_required": sorted(missing),
        "windows": control["windows"],
        "commodities": commodities,
        MANIFEST_KEY: entries,
    }
    manifest_hash = sha256_text(_canonical_json(manifest))

    calibration_uses = {TargetUse.CALIBRATION.value, TargetUse.VALIDATION.value}
    holdout_uses = {TargetUse.HOLDOUT.value, TargetUse.RESERVED.value}
    calibration = [e for e in entries if e.get("use") in calibration_uses]
    holdout = [e for e in entries if e.get("use") in holdout_uses]
    sealed = [
        {
            "artifact_id": e["artifact_id"],
            "use": e["use"],
            "sha256": e["sha256"],
            "observed_period": e.get("observed_period"),
            "comparison_aggregation": e.get("comparison_aggregation"),
        }
        for e in holdout
    ]
    exposure = control.get("exposure", [])
    parameters = [
        {
            "artifact_id": e["artifact_id"],
            "variable_id": e["variable_id"],
            "literature_refs": e.get("literature_refs", []),
            "present": e["present"],
        }
        for e in entries
        if e["role"] == "latent_parameter"
    ]

    manifests_dir.mkdir(parents=True, exist_ok=True)
    (manifests_dir / MANIFEST_FILENAME).write_text(_canonical_json(manifest), encoding="utf-8")
    (manifests_dir / "p05_targets.yml").write_text(
        _yaml_doc("targets", calibration), encoding="utf-8"
    )
    (manifests_dir / "p05_holdout.yml").write_text(
        _yaml_doc("targets", sealed), encoding="utf-8"
    )
    (manifests_dir / "p05_exposure.yml").write_text(
        _yaml_doc("exposures", list(exposure)), encoding="utf-8"
    )
    parameters_path = root / str(control["registries"]["parameters"])
    parameters_path.parent.mkdir(parents=True, exist_ok=True)
    parameters_path.write_text(_yaml_doc("parameters", parameters), encoding="utf-8")

    return {
        "status": "frozen",
        "manifest": str(manifests_dir / MANIFEST_FILENAME),
        "manifest_sha256": manifest_hash,
        "artifact_count": len(entries),
        "role_counts": manifest["role_counts"],
        "missing_required": sorted(missing),
        "targets": {
            "calibration": len(calibration),
            "holdout": len(holdout),
        },
    }


def sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()
