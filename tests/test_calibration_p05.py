"""P05 identifiability screening: real registry verdict and synthetic linkage."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from hsm_lab.calibration.fidelity import prior_fidelity
from hsm_lab.calibration.screen import screen_parameters

ROOT = Path(__file__).resolve().parents[1]


def test_real_registry_reports_no_identifiable_parameters() -> None:
    payload = screen_parameters(ROOT, config=ROOT / "config" / "calibration" / "p05.json")
    assert payload["status"] == "NO_IDENTIFIABLE_PARAMETERS"
    assert payload["identified"] == []
    assert payload["parameters"] >= 1
    # every declared parameter is accounted for as fixed or unidentified
    assert sum(payload["status_counts"].values()) == payload["parameters"]
    # the declared calibration windows now sit inside the aligned training window
    assert payload["target_window_overlap"]["inside"] == 14
    assert payload["target_window_overlap"]["overlaps"] == 0
    assert payload["admissible_targets"] == 14
    # the remaining blocker is the undeclared parameter-to-target linkage
    assert payload["declared_linkage"] == []
    assert payload["identifiable_set"] == []
    assert payload["inference_status"] == "NOT_RUN"
    # the declared identity split now includes the structural input-credit rule
    assert payload["status_counts"] == {"fixed": 9, "unidentified": 6}
    assert any("linkage" in reason for reason in payload["blocking_reasons"])
    assert any("UNIDENTIFIED" in reason for reason in payload["blocking_reasons"])


def _write_registries(root: Path, *, linked: bool) -> Path:
    (root / "config" / "calibration").mkdir(parents=True)
    (root / "data" / "manifests").mkdir(parents=True)
    control = {
        "ontology": "config/ontology/f2_v1.json",
        "windows": {
            "training": {"start": "1961Q1", "end": "1969Q4"},
        },
        "registries": {
            "parameters": "config/calibration/p05_parameters.yml",
            "targets": "data/manifests/p05_targets.yml",
            "holdout": "data/manifests/p05_holdout.yml",
            "exposure": "data/manifests/p05_exposure.yml",
        },
        "linkage": [{"parameter": "p_target", "targets": ["v_target"]}],
    }
    config = root / "config" / "calibration" / "p05.json"
    config.write_text(json.dumps(control), encoding="utf-8")
    (config.parent / "p05_parameters.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1",
                "parameters": [
                    {
                        "artifact_id": "p_target",
                        "variable_id": "v_target",
                        "literature_refs": ["estimated from the wage series"],
                        "present": True,
                    },
                    {
                        "artifact_id": "p_fixed",
                        "variable_id": "v_fixed",
                        "literature_refs": ["structural assumption: constant price"],
                        "present": True,
                    },
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    targets = [
        {
            "artifact_id": "t_v_target",
            "variable_id": "v_target",
            "use": "calibration",
            "present": True,
            "evidence_status": "observed",
            "digest_matches": True,
            "observed_period": {"start": "1962", "end": "1968", "frequency": "annual"},
        }
    ]
    if not linked:
        targets[0]["observed_period"] = {"start": "1975", "end": "1980", "frequency": "annual"}
    (root / "data" / "manifests" / "p05_targets.yml").write_text(
        yaml.safe_dump({"schema_version": "1", "targets": targets}, sort_keys=True),
        encoding="utf-8",
    )
    return config


def test_admissible_training_target_identifies_and_structural_prior_stays_fixed(
    tmp_path: Path,
) -> None:
    config = _write_registries(tmp_path, linked=True)
    payload = screen_parameters(tmp_path, config=config)
    assert payload["status"] == "ok"
    assert payload["identified"] == ["p_target"]
    statuses = {row["parameter"]: row["status"] for row in payload["rows"]}
    assert statuses["p_fixed"] == "fixed"
    assert statuses["p_target"] == "identified"


def test_target_outside_training_window_is_not_admissible(tmp_path: Path) -> None:
    config = _write_registries(tmp_path, linked=False)
    payload = screen_parameters(tmp_path, config=config)
    assert payload["admissible_targets"] == 0
    assert payload["status"] == "NO_IDENTIFIABLE_PARAMETERS"
    assert payload["target_window_overlap"]["outside"] == 1


def test_fidelity_short_circuits_without_a_candidate_set() -> None:
    payload = prior_fidelity(ROOT, config=ROOT / "config" / "calibration" / "p05.json")
    assert payload["status"] == "NO_IDENTIFIABLE_PARAMETERS"
    assert payload["stage"] == "prior"
    assert payload["paired_study"] is None
    assert payload["inference_status"] == "NOT_RUN"
    assert payload["blocking_reasons"]


def test_fidelity_reports_the_unimplemented_paired_study_for_a_candidate_set(
    tmp_path: Path,
) -> None:
    config = _write_registries(tmp_path, linked=True)
    payload = prior_fidelity(tmp_path, config=config, stage="prior")
    # a candidate exists, so the stage must not pretend the study ran
    assert payload["status"] == "PAIRED_STUDY_NOT_IMPLEMENTED"
    assert payload["candidates"] == ["p_target"]
    assert payload["paired_study"] is None
    assert "prior_vectors" in payload["required_inputs"]
    assert "paired_median_bias_scale" in payload["required_inputs"]


def test_fidelity_rejects_unknown_stage() -> None:
    import pytest

    with pytest.raises(ValueError, match="unknown fidelity stage"):
        prior_fidelity(ROOT, config=ROOT / "config" / "calibration" / "p05.json", stage="nope")


def test_abc_smoke_proves_the_api_and_the_empty_registry_path(tmp_path: Path) -> None:
    pytest = __import__("pytest")
    pytest.importorskip("pyabc")
    from hsm_lab.calibration.abc_smoke import abc_registry_path, abc_synthetic_recovery

    registry = abc_registry_path(ROOT, config=ROOT / "config" / "calibration" / "p05.json")
    assert registry["status"] == "NO_IDENTIFIABLE_PARAMETERS"
    assert registry["identifiable_set"] == []
    assert registry["inference_status"] == "NOT_RUN"

    # a tiny declared budget: the smoke proves the API path, not throughput
    recovery = abc_synthetic_recovery(
        ROOT,
        config=ROOT / "config" / "calibration" / "p05.json",
        particles=3,
        populations=1,
        ticks=2,
    )
    assert recovery["status"] == "ok"
    assert recovery["checkpoint_used"] is False
    assert recovery["populations_completed"] == 1
    assert recovery["posterior_particles"] == 3
    assert recovery["observed_summary"] > 0.0
