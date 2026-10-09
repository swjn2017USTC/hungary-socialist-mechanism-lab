"""P05 1957 reconstruction audit (plan §B.8 / §150).

``reconstruct_p05`` audits whether the frozen DATA_MANIFEST_v1 carries the
mandatory 1957 initial anchors (20-county population, household totals, the
dwelling base) and reports their A/B/C/S provenance level.  When a mandatory
family is absent the data/F2 initialization gate *fails* — the rest of the
audit is still completed, and a uniform synthetic population is never passed
off as an admitted reconstruction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANDATORY_ANCHOR_FAMILIES: tuple[str, ...] = ("population", "household", "dwelling")
_ANCHOR_ROLES = ("initial_state", "initial", "initial_conditions", "anchor")


def _is_anchor(artifact: dict[str, Any]) -> bool:
    return str(artifact.get("role")) in _ANCHOR_ROLES


def reconstruct_p05(root: Path, *, config: Path) -> dict[str, object]:
    """Audit the 1957 initial anchors declared by the frozen data manifest."""
    control = json.loads(config.read_text(encoding="utf-8"))
    manifest_filename = str(control.get("data_manifest") or "DATA_MANIFEST_v1.json")
    manifest_path = root / "data" / "manifests" / manifest_filename
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"{manifest_filename} is not frozen yet; run `hsm data freeze-p05` first"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = [entry for entry in manifest.get("artifacts", []) if isinstance(entry, dict)]
    anchors = [entry for entry in artifacts if _is_anchor(entry)]

    families: dict[str, list[dict[str, Any]]] = {family: [] for family in MANDATORY_ANCHOR_FAMILIES}
    for anchor in anchors:
        variable = str(anchor.get("variable_id", "")).lower()
        for family in MANDATORY_ANCHOR_FAMILIES:
            if family in variable:
                families[family].append(anchor)

    summary: list[dict[str, Any]] = []
    missing: list[str] = []
    for family in MANDATORY_ANCHOR_FAMILIES:
        admitted = [entry for entry in families[family] if entry.get("present")]
        if not admitted:
            missing.append(family)
        summary.append(
            {
                "family": family,
                "declared": len(families[family]),
                "admitted": len(admitted),
                "artifact_ids": [entry.get("artifact_id") for entry in admitted],
                "provenance": sorted({str(entry.get("evidence_status")) for entry in admitted}),
                "grades": sorted({str(entry.get("grade")) for entry in admitted}),
                "periods": [entry.get("anchor_period") for entry in admitted],
            }
        )

    periodic = sorted(
        {
            str(entry.get("evidence_status"))
            for entry in artifacts
            if entry.get("evidence_status") is not None
        }
    )
    wired = control.get("anchor_initialization") or {}
    wired_status = str(wired.get("status", "unknown"))
    verdict = "ok" if not missing else "MISSING_MANDATORY_ANCHORS"
    return {
        "status": verdict,
        "command": "data reconstruct-p05",
        "manifest": str(manifest_path.relative_to(root)),
        "manifest_sha256": _sha256(manifest_path),
        "ontology_id": manifest.get("ontology_id"),
        "windows": control.get("windows", {}),
        "declared_artifacts": len(artifacts),
        "declared_anchors": len(anchors),
        "initialization_wired": wired_status == "wired",
        "identification_wiring": {"status": wired_status, "note": wired.get("note")},
        "mandatory": summary,
        "missing_mandatory": missing,
        "evidence_levels_present": periodic,
        "caveats": [
            "anchors are KSH Nepszamlalas 2011 retrospective tables: official values "
            "on 2011 boundaries/definitions",
            "grade C fixed-space proxy; the 1957 historical county boundary is NOT "
            "observed here",
            "1957 itself must be a grade-S derivation (1949/1960 comparable re-coded "
            "pair plus the official national 1957-01-01 total)",
        ],
        "note": (
            "uniform synthetic population is never admitted as a 1957 reconstruction"
            if missing
            else (
                "mandatory 1957 initial anchors are admitted, but no code path consumes "
                "them yet: the gate is admission-only and the initial state is still synthetic"
                if wired_status != "wired"
                else "mandatory 1957 initial anchors are present and wired into initialization"
            )
        ),
    }


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
