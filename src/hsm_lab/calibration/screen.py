"""P05 identifiability screening (plan §D / §271).

``screen_parameters`` reads the frozen parameter registry and the frozen target
registry and classifies every declared latent parameter as identified /
weakly identified / unidentified / fixed from the *admissible numeric* targets
only.  With no admissible numeric evidence linked to a parameter it reports
``NO_IDENTIFIABLE_PARAMETERS`` instead of inventing a candidate set; that is the
honest outcome the plan requires of the real registry path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

# Parameters whose value is pinned by a literature/structural assumption rather
# than estimated from data; these are reported as ``fixed`` and never screened.
_FIXED_MARKERS = ("structural assumption", "literature", "pinned")


def _load_yaml(path: Path, key: str) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"registry not found: {path}")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = doc.get(key)
    if not isinstance(entries, list):
        raise ValueError(f"{path}: expected a top-level {key!r} list")
    return [entry for entry in entries if isinstance(entry, dict)]


def _year(value: Any) -> int | None:
    text = str(value)[:4]
    return int(text) if text.isdigit() else None


def _overlap(period: dict[str, Any] | None, start: int, end: int) -> str:
    """``inside`` / ``overlaps`` / ``outside`` of the training window."""
    if not isinstance(period, dict):
        return "outside"
    first = _year(period.get("start"))
    last = _year(period.get("end"))
    if first is None or last is None:
        return "outside"
    if first >= start and last <= end:
        return "inside"
    if last < start or first > end:
        return "outside"
    return "overlaps"


def _inside_training(period: dict[str, Any] | None, start: int, end: int) -> bool:
    if not isinstance(period, dict):
        return False
    first = _year(period.get("start"))
    last = _year(period.get("end"))
    if first is None or last is None:
        return False
    return first >= start and last <= end


def screen_parameters(root: Path, *, config: Path) -> dict[str, object]:
    """Classify the declared latent parameters from admissible target evidence."""
    control = json.loads(config.read_text(encoding="utf-8"))
    windows = control["windows"]
    training = windows["training"]
    train_start = _year(training["start"])
    train_end = _year(training["end"])
    if train_start is None or train_end is None:
        raise ValueError("control training window must carry four-digit years")

    declared_identity = {
        str(name): str(label) for name, label in (control.get("identification") or {}).items()
    }
    linkage_entries = control.get("linkage") or []
    linkage: dict[str, list[str]] = {}
    for entry in linkage_entries:
        if not isinstance(entry, dict):
            raise ValueError("control linkage entries must be mappings")
        parameter = str(entry.get("parameter"))
        targets_for = [str(v) for v in entry.get("targets", [])]
        if not parameter or not targets_for:
            raise ValueError(f"control linkage entry is incomplete: {entry!r}")
        linkage[parameter] = targets_for
    parameters = _load_yaml(root / str(control["registries"]["parameters"]), "parameters")
    targets = _load_yaml(root / str(control["registries"]["targets"]), "targets")

    admissible: list[dict[str, Any]] = []
    for target in targets:
        if not target.get("present"):
            continue
        if str(target.get("evidence_status")) != "observed":
            continue
        if not _inside_training(target.get("observed_period"), train_start, train_end):
            continue
        if target.get("digest_matches") is False:
            continue
        admissible.append(target)
    overlap_counts: dict[str, int] = {"inside": 0, "overlaps": 0, "outside": 0}
    declared: list[dict[str, Any]] = []
    for target in targets:
        status_overlap = _overlap(target.get("observed_period"), train_start, train_end)
        overlap_counts[status_overlap] += 1
        if status_overlap == "overlaps" and target.get("present"):
            declared.append(
                {
                    "artifact_id": target.get("artifact_id"),
                    "variable_id": target.get("variable_id"),
                    "observed_period": target.get("observed_period"),
                    "overlap": status_overlap,
                }
            )
    by_variable: dict[str, list[str]] = {}
    for target in admissible:
        by_variable.setdefault(str(target.get("variable_id")), []).append(
            str(target.get("artifact_id"))
        )

    rows: list[dict[str, Any]] = []
    for parameter in parameters:
        variable = str(parameter.get("variable_id"))
        refs = " ".join(str(ref).lower() for ref in parameter.get("literature_refs", []))
        declared_targets = linkage.get(str(parameter.get("artifact_id")), [])
        linked = sorted(
            {artifact for var in declared_targets for artifact in by_variable.get(var, [])}
        )
        declared_label = declared_identity.get(str(parameter.get("artifact_id")))
        if declared_label in ("fixed", "unidentified"):
            # a declared identity wins over the wording heuristic: the audit
            # decides whether a parameter is structurally determined or merely
            # prior-constrained, and that decision is auditable in the control file
            status = declared_label
        elif any(marker in refs for marker in _FIXED_MARKERS):
            status = "fixed"
        elif linked:
            status = "identified"
        else:
            status = "unidentified"
        rows.append(
            {
                "parameter": parameter.get("artifact_id"),
                "variable_id": variable,
                "status": status,
                "admissible_targets": linked,
            }
        )

    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row["status"])] = counts.get(str(row["status"]), 0) + 1
    identified = [row for row in rows if row["status"] == "identified"]
    verdict = "ok" if identified else "NO_IDENTIFIABLE_PARAMETERS"
    inference_status = "NOT_RUN" if not identified else "PENDING"
    blocking: list[str] = []
    if not identified:
        if overlap_counts["inside"] == 0 and overlap_counts["overlaps"] > 0:
            blocking.append(
                "no declared target window lies fully inside the training window "
                f"({training['start']}-{training['end']}): {overlap_counts['overlaps']} targets "
                "partially overlap and would leak the boundary year"
            )
        if all(row["status"] == "fixed" for row in rows):
            blocking.append("every declared latent parameter is a structural prior (fixed)")
        if any(row["status"] == "unidentified" for row in rows):
            blocking.append(
                f"{sum(1 for row in rows if row['status'] == 'unidentified')} parameters are "
                "declared UNIDENTIFIED: no declared observable constrains them, so they stay "
                "prior-constrained and must not be reported as estimated"
            )
        if not any(row["admissible_targets"] for row in rows):
            blocking.append(
                "no declared parameter is linked to an admissible target variable "
                "(no parameter-to-target linkage is declared in the control file)"
            )

    return {
        "status": verdict,
        "command": "calibration screen",
        "training_window": {"start": training["start"], "end": training["end"]},
        "admissible_targets": len(admissible),
        "parameters": len(rows),
        "status_counts": dict(sorted(counts.items())),
        "identified": [row["parameter"] for row in identified],
        "declared_linkage": sorted(linkage),
        "identifiable_set": [row["parameter"] for row in identified],
        "inference_status": inference_status,
        "unlinked_parameters": [
            row["parameter"] for row in rows if not linkage.get(str(row["parameter"]))
        ],
        "target_window_overlap": overlap_counts,
        "overlapping_targets": declared,
        "blocking_reasons": blocking,
        "rows": rows,
    }
