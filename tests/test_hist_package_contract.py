"""Consumer-level contract tests for the H6B package audit/export.

The real-repository test runs in ``git-only`` mode and therefore never opens an
ignored output.  The complete/missing-evidence tests use an explicitly
synthetic fixture under ``tmp_path``; they do not depend on historical outputs
or on a prior run of the real studies.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

import hsm_lab.evidence.package_export as package_export
from hsm_lab.contract.guards import sha256_file
from hsm_lab.evidence.package_export import (
    CHECK_NAMES,
    PackageExportError,
    audit_package,
    export_package,
    main,
    verify_export,
)

REPO = Path(__file__).resolve().parents[1]
CARD_IDS = tuple(f"M{i:02d}" for i in range(1, 12))
CHECK_SET = set(CHECK_NAMES)


# ---------------------------------------------------------------------------
# Fixture repository
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _reference_card_sha(root: Path) -> str:
    return sha256_file(root / "config/p06/cards/M1.json")


def _fixture_study(card_sha: str) -> dict[str, Any]:
    seeds = [1729, 1730]
    arms = ["control", "treatment"]
    paired = [
        {
            "seed": seed,
            "arm": arm,
            "opening_digest": f"opening-{seed}",
            "rng_digest": f"rng-{seed}",
        }
        for seed in seeds
        for arm in arms
    ]
    first_stage = [
        {
            "seed": seed,
            "arm": arm,
            "applied": True,
            "effective": True,
            "binding": True,
            "flow": 1.0,
        }
        for seed in seeds
        for arm in arms
    ]
    ticks = [
        {
            "seed": seed,
            "arm": arm,
            "tick": tick,
            "material_residual": 1e-12,
            "finance_residual": 1e-12,
        }
        for seed in seeds
        for arm in arms
        for tick in range(4)
    ]
    return {
        "schema_version": "fixture_h6b_study_v1",
        "study_id": "M01",
        "seeds": seeds,
        "arms": arms,
        "paired": paired,
        "first_stage": first_stage,
        "accounting": {"gate": 1e-6, "ticks_per_arm": 4, "ticks": ticks},
        "negative_control": {"arm": "control", "metric": 0.0},
        "metrics": {
            "effect": {"value": 0.125, "selector": "treatment_vs_control", "unit": "ratio"},
            "unmet": {"value": 0.0, "selector": "national", "unit": "physical"},
        },
        "sensitivity": [{"parameter": "tolerance", "value": 0.5}],
        "historical_status": "UNIDENTIFIED",
        "counterevidence": [{"result": "structural_null", "reason": "fixture counterexample"}],
        "failed_seeds": [],
        "card_sha": card_sha,
    }


def _not_started_definition(card_id: str) -> package_export.CardDefinition:
    legacy = f"M{int(card_id[1:])}"
    return package_export.CardDefinition(
        study_id=card_id,
        legacy_card_id=legacy,
        kind="not_started",
        phase="FIXTURE",
        card_path=f"config/p06/cards/{legacy}.json",
        declaration_path=f"studies/{card_id}/study_decl.json",
    )


def _build_fixture(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    root = tmp_path / "repo"
    (root / "config/p06/cards").mkdir(parents=True)
    (root / "config/mechanisms/v2").mkdir(parents=True)
    (root / "studies").mkdir(parents=True)
    for source in sorted((REPO / "config/p06/cards").glob("M*.json")):
        shutil.copyfile(source, root / "config/p06/cards" / source.name)
    shutil.copyfile(
        REPO / "config/mechanisms/v2/supersedes.json",
        root / "config/mechanisms/v2/supersedes.json",
    )
    shutil.copyfile(REPO / "studies/manifest.json", root / "studies/manifest.json")
    for card_id in CARD_IDS:
        sidecar = REPO / "studies" / card_id / "study_decl.json"
        target = root / "studies" / card_id / "study_decl.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sidecar, target)

    card_sha = _reference_card_sha(root)
    m01 = root / "studies/HIST_VNEXT/M01"
    m01.mkdir(parents=True)
    _write_json(
        m01 / "spec.json",
        {
            "schema_version": "fixture_h6b_spec_v1",
            "study_id": "M01",
            "mechanism_id": "M1",
            "legacy_card": {"path": "config/p06/cards/M1.json", "sha256": card_sha},
            "seeds": [1729, 1730],
            "arms": ["control", "treatment"],
            "window": {"start": "1957Q1", "end": "1957Q4"},
            "falsification_criterion": "fixture criterion",
            "required_metrics": ["effect", "unmet"],
        },
    )
    (m01 / "EVIDENCE_MANIFEST.json").write_text("{}\n", encoding="utf-8")
    (m01 / "REPORT.md").write_text("# fixture report\n", encoding="utf-8")
    (m01 / "REVIEW.md").write_text("# fixture review\n", encoding="utf-8")

    study = _fixture_study(card_sha)
    for name in ("existing", "fresh", "repeat"):
        _write_json(root / "outputs" / name / "study.json", study)

    index = {
        "schema_version": "hist_vnext_h6b_evidence_index_v1",
        "cards": {
            card_id: {
                "existing_root": "outputs/existing" if card_id == "M01" else None,
                "fresh_root": "outputs/fresh" if card_id == "M01" else None,
                "repeat_root": "outputs/repeat" if card_id == "M01" else None,
            }
            for card_id in CARD_IDS
        },
    }
    _write_json(root / "studies/HIST_VNEXT/packages/H6B/evidence_index.json", index)

    definitions = {card_id: _not_started_definition(card_id) for card_id in CARD_IDS}
    definitions["M01"] = package_export.CardDefinition(
        study_id="M01",
        legacy_card_id="M1",
        kind="experiment",
        phase="FIXTURE",
        card_path="config/p06/cards/M1.json",
        spec_path="studies/HIST_VNEXT/M01/spec.json",
        manifest_path="studies/HIST_VNEXT/M01/EVIDENCE_MANIFEST.json",
        report_path="studies/HIST_VNEXT/M01/REPORT.md",
        review_path="studies/HIST_VNEXT/M01/REVIEW.md",
        fixture=True,
    )
    return root, definitions


def _audit(
    root: Path, definitions: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> dict[str, Any]:
    monkeypatch.setattr(package_export, "CARD_DEFINITIONS", definitions)
    return audit_package(
        root,
        mode="local-data",
        evidence_index=Path("studies/HIST_VNEXT/packages/H6B/evidence_index.json"),
    )


def _mutate_study(root: Path, mutate) -> None:
    path = root / "outputs/existing/study.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    _write_json(path, payload)


# ---------------------------------------------------------------------------
# Real repository, git-only
# ---------------------------------------------------------------------------


def test_real_git_only_audit_preserves_eleven_card_identity(repo_root: Path) -> None:
    package = audit_package(
        repo_root,
        mode="git-only",
        evidence_index=Path("studies/HIST_VNEXT/packages/H6B/evidence_index.json"),
    )
    assert package["mode"] == "git-only"
    assert set(package["cards"]) == set(CARD_IDS)
    assert package["card_registry"]["counts"] == {
        "cards": 11,
        "metrics": 41,
        "mapped": 14,
        "blocked": 27,
    }
    assert package["summary"]["legacy_metrics"] == 41
    assert package["summary"]["complete"] == 0
    for card_id, card in package["cards"].items():
        assert set(card["checks"]) == CHECK_SET
        assert card["research_package_complete"] is False
        assert card["package_status"] == "blocked"
        assert len(card["legacy_metrics"]) >= 2
        assert card_id == card["study_id"]
    # Run-backed experiment checks are explicitly blocked in git-only mode.
    for card_id in ("M01", "M02", "M04", "M09"):
        assert package["cards"][card_id]["checks"]["paired_control"]["status"] == "BLOCKED"
        assert package["cards"][card_id]["checks"]["reproduction_bundle"]["status"] == "BLOCKED"
    # M03 reads its later implementation package, not the old blocker.
    m03 = package["cards"]["M03"]
    assert m03["checks"]["negative_control"]["status"] == "PASS"
    assert m03["prior_review"]["path"] == "studies/HIST_VNEXT/M03/IMPLEMENTATION_REVIEW.md"
    # M04 uses the phase review path, not a local copied review.
    assert package["cards"]["M04"]["prior_review"]["path"] == "docs/phases/HIST_VNEXT/H5B/REVIEW.md"
    # The four dedicated-directory-missing cards stay NOT_STARTED.
    for card_id in ("M05", "M08", "M10", "M11"):
        assert package["cards"][card_id]["experiment_status"] == "NOT_STARTED"
        assert package["cards"][card_id]["checks"]["experiment_declared"]["status"] == "NOT_RUN"
    # Blocker-only cards retain their blocker identity.
    assert package["cards"]["M06"]["blockers"] == ["MISSING_EXTERNAL_DEBT_CONTRACT_ADMISSION"]
    assert package["cards"]["M07"]["blockers"] == ["MISSING_REGIONAL_CROSSWALK_PASS"]
    assert "source_rights" in package
    assert package["source_rights"]["redistribution_allowed_any"] is False


# ---------------------------------------------------------------------------
# Complete synthetic fixture and the six required evidence classes
# ---------------------------------------------------------------------------


def test_complete_fixture_can_be_complete_with_unidentified_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, definitions = _build_fixture(tmp_path)
    package = _audit(root, definitions, monkeypatch)
    m01 = package["cards"]["M01"]
    assert m01["research_package_complete"] is True
    assert m01["package_status"] == "complete"
    assert m01["verdicts"]["historical"]["status"] == "UNIDENTIFIED"
    assert all(check["status"] == "PASS" for check in m01["checks"].values())
    assert package["summary"]["complete"] == 1


@pytest.mark.parametrize(
    ("name", "mutate", "expected_block"),
    [
        ("paired", lambda p: p["paired"].pop(), "paired_control"),
        ("first_stage", lambda p: p["first_stage"][0].update(binding=False), "first_stage_checked"),
        (
            "ledger",
            lambda p: p["accounting"]["ticks"][0].update(material_residual=1.0),
            "accounting_checked",
        ),
        (
            "negative_control",
            lambda p: p["negative_control"].pop("metric"),
            "negative_control",
        ),
        ("metrics", lambda p: p["metrics"].pop("effect"), "metrics_generated"),
        ("sensitivity", lambda p: p.pop("sensitivity"), "sensitivity_or_reason_not_run"),
        ("replay", lambda p: p["paired"].extend(p["paired"][:1]), "reproduction_bundle"),
    ],
)
def test_missing_required_evidence_blocks_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    mutate,
    expected_block: str,
) -> None:
    root, definitions = _build_fixture(tmp_path)
    if name == "replay":
        shutil.rmtree(root / "outputs/fresh")
    else:
        _mutate_study(root, mutate)
    package = _audit(root, definitions, monkeypatch)
    m01 = package["cards"]["M01"]
    assert m01["research_package_complete"] is False
    assert m01["checks"][expected_block]["status"] != "PASS"
    assert m01["package_status"] == "blocked"


def test_empty_or_null_metric_is_not_counted_as_measured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, definitions = _build_fixture(tmp_path)

    def null_metric(payload: dict[str, Any]) -> None:
        payload["metrics"]["unmet"]["value"] = None

    _mutate_study(root, null_metric)
    package = _audit(root, definitions, monkeypatch)
    assert package["cards"]["M01"]["checks"]["metrics_generated"]["status"] != "PASS"


def test_duplicate_seed_label_cannot_fake_a_paired_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, definitions = _build_fixture(tmp_path)

    def duplicate(payload: dict[str, Any]) -> None:
        payload["paired"][2]["seed"] = payload["paired"][0]["seed"]

    _mutate_study(root, duplicate)
    package = _audit(root, definitions, monkeypatch)
    assert package["cards"]["M01"]["checks"]["paired_control"]["status"] != "PASS"


def test_tampered_replay_digest_blocks_reproduction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, definitions = _build_fixture(tmp_path)
    path = root / "outputs/fresh/study.json"
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    package = _audit(root, definitions, monkeypatch)
    check = package["cards"]["M01"]["checks"]["reproduction_bundle"]
    assert check["status"] == "BLOCKED"
    assert "digest" in check["reason"] or "reproduce" in check["reason"]


def test_wrong_card_sha_is_a_hard_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, definitions = _build_fixture(tmp_path)
    card = root / "config/p06/cards/M1.json"
    card.write_text(card.read_text(encoding="utf-8").replace('"M1"', '"M1 "', 1), encoding="utf-8")
    with pytest.raises(PackageExportError, match="card SHA|registry"):
        _audit(root, definitions, monkeypatch)


def test_restricted_path_is_rejected_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, definitions = _build_fixture(tmp_path)
    sentinel = root / "data/private" / "sentinel.txt"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("TOP-SECRET-SENTINEL", encoding="utf-8")
    index_path = root / "studies/HIST_VNEXT/packages/H6B/evidence_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["cards"]["M01"]["existing_root"] = "data/private/sentinel.txt"
    _write_json(index_path, index)
    monkeypatch.setattr(package_export, "CARD_DEFINITIONS", definitions)
    with pytest.raises(PackageExportError, match="restricted path"):
        audit_package(
            root,
            mode="local-data",
            evidence_index=Path("studies/HIST_VNEXT/packages/H6B/evidence_index.json"),
        )


# ---------------------------------------------------------------------------
# Export reproducibility, tamper detection and CLI exit codes
# ---------------------------------------------------------------------------


def test_export_is_byte_identical_and_verify_rejects_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, definitions = _build_fixture(tmp_path)
    package_one = _audit(root, definitions, monkeypatch)
    package_two = _audit(root, definitions, monkeypatch)
    assert package_one["package_digest"] == package_two["package_digest"]

    first = tmp_path / "export-one"
    second = tmp_path / "export-two"
    export_package(package_one, first)
    export_package(package_two, second)
    first_files = sorted(path.relative_to(first) for path in first.rglob("*") if path.is_file())
    second_files = sorted(path.relative_to(second) for path in second.rglob("*") if path.is_file())
    assert first_files == second_files
    for relative in first_files:
        assert (first / relative).read_bytes() == (second / relative).read_bytes()
    assert verify_export(first)["status"] == "verified"

    tampered = first / "cards/M01.json"
    tampered.write_text(tampered.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(PackageExportError, match="changed"):
        verify_export(first)

    extra = tmp_path / "export-extra"
    export_package(package_one, extra)
    (extra / "unlisted.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(PackageExportError, match="file set mismatch"):
        verify_export(extra)


def test_cli_build_and_verify_exit_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root, definitions = _build_fixture(tmp_path)
    monkeypatch.setattr(package_export, "CARD_DEFINITIONS", definitions)
    output = tmp_path / "cli-export"
    assert (
        main(
            [
                "build",
                "--root",
                str(root),
                "--mode",
                "local-data",
                "--evidence-index",
                "studies/HIST_VNEXT/packages/H6B/evidence_index.json",
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )
    assert (output / "MANIFEST.json").is_file()
    assert main(["verify", "--package-dir", str(output)]) == 0
    # Refuse to overwrite an existing package.
    assert (
        main(["build", "--root", str(root), "--mode", "git-only", "--output-dir", str(output)]) == 2
    )
    # Tampered package is exit 2.
    (output / "package.json").write_text("{}\n", encoding="utf-8")
    assert main(["verify", "--package-dir", str(output)]) == 2
    capsys.readouterr()


def test_export_contains_no_restricted_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, definitions = _build_fixture(tmp_path)
    package = _audit(root, definitions, monkeypatch)
    exported = tmp_path / "public"
    export_package(package, exported)
    text = "".join(
        path.read_text(encoding="utf-8") for path in exported.rglob("*") if path.is_file()
    )
    for forbidden in ("original_excerpt", "ocr_text", "translation", "local_path", "TOP-SECRET"):
        assert forbidden not in text
    assert "/Users/" not in text


# ---------------------------------------------------------------------------
# Real-adapter gate helpers: artifact-derived, not asserted
# ---------------------------------------------------------------------------


def _m01_gate_study() -> dict[str, Any]:
    seeds = ["1", "2", "3"]
    levers = ("import_cut", "income_cut", "welfare_cut")
    return {
        "seeds": [1, 2, 3],
        "reference_first_stage": {
            "status": "PASS",
            "by_seed": {seed: {"status": "PASS"} for seed in seeds},
        },
        "cut_first_stage": {
            "status": "PASS",
            "by_seed": {
                seed: {
                    lever: {
                        "status": "BINDING",
                        "applied": True,
                        "effective": True,
                        "binding": True,
                        "first_stage": {"metric": "flow"},
                    }
                    for lever in levers
                }
                for seed in seeds
            },
        },
        "verdict": {
            "levers": {
                lever: {
                    "D_four_minus_one_grievance_by_seed": {seed: 1.0 for seed in seeds},
                    "D_four_minus_one_spending_by_seed": {seed: -1.0 for seed in seeds},
                }
                for lever in levers
            }
        },
        "statistics": {
            "ablation": [
                {
                    "N_status": {"spending_total": "NEGATIVE"},
                    "N_cumulative": {
                        "grievance_national_from_table": 1.0,
                        "spending_total": -1.0,
                        "expectation_real_consumption_mean": 1.0,
                    },
                }
            ],
            "missing": [],
        },
    }


def test_m01_real_gate_helpers_reject_null_and_degraded_artifacts() -> None:
    study = _m01_gate_study()
    assert package_export._m01_first_stage_ok(study)[0] is True
    assert package_export._m01_metrics_ok(study)[0] is True
    study["verdict"]["levers"]["import_cut"]["D_four_minus_one_grievance_by_seed"]["1"] = None
    assert package_export._m01_metrics_ok(study)[0] is False
    study = _m01_gate_study()
    study["cut_first_stage"]["by_seed"]["3"]["import_cut"]["binding"] = False
    assert package_export._m01_first_stage_ok(study)[0] is False


def _m02_gate_results() -> dict[str, Any]:
    seeds = [1, 2, 3]
    budget = [
        {
            "seed": seed,
            "joint_budget_leg": {"status": "BINDING"},
            "credit_leg": {"status": "BINDING"},
        }
        for seed in seeds
        for _ in range(4)
    ]
    investment = [
        {"seed": seed, "status": "BINDING", "differences": {"x": 1.0}}
        for seed in seeds
        for _ in range(4)
    ]
    demand = [
        {"seed": seed, "status": "BINDING", "differing_household_desired_channels": ["energy"]}
        for seed in seeds
        for _ in range(6)
    ]
    per_arm = {
        f"{seed}|{arm}": {
            "final_quarter_metrics": {
                "shortage_expectation_mean": 0.0,
                "credit_drawn_total": 1.0,
                "investment_approved_total": 1.0,
                "activity_realized_total": 1.0,
            }
        }
        for seed in seeds
        for arm in range(13)
    }
    return {
        "first_stage": {"budget": budget, "investment": investment, "demand_regime": demand},
        "per_arm": per_arm,
        "contrasts": {"by_seed_and_regime": [{"seed": 1}]},
        "verdicts": {
            "historical": {
                "identification_status": "UNIDENTIFIED",
                "historical_support": "NOT_ESTABLISHED",
            }
        },
    }


def test_m02_real_gate_helpers_reject_null_metric_and_nonbinding_first_stage() -> None:
    results = _m02_gate_results()
    assert package_export._m02_first_stage_ok(results)[0] is True
    assert package_export._m02_metrics_ok(results)[0] is True
    assert package_export._m02_historical_ok(results)[0] is True
    results["per_arm"]["1|0"]["final_quarter_metrics"]["shortage_expectation_mean"] = None
    assert package_export._m02_metrics_ok(results)[0] is False
    results = _m02_gate_results()
    for row in results["first_stage"]["budget"]:
        row["joint_budget_leg"]["status"] = "NONBINDING"
        row["credit_leg"]["status"] = "NONBINDING"
    assert package_export._m02_first_stage_ok(results)[0] is False
    results = _m02_gate_results()
    results["verdicts"]["historical"]["identification_status"] = "SUPPORTED"
    assert package_export._m02_historical_ok(results)[0] is False


def _m04_gate_study() -> dict[str, Any]:
    seeds = ["1", "2", "3"]
    required = (
        "second_hours_total",
        "formal_unmet_total",
        "formal_sales_total",
        "funding_total",
        "plot_self_weighted",
        "plot_market_weighted",
    )
    arms: dict[str, Any] = {}
    for index, arm in enumerate(("tolerance_0", "tolerance_05", "tolerance_1")):
        arms[arm] = {
            seed: {
                "tolerance": (0.0, 0.5, 1.0)[index],
                "completed_ticks": 16,
                "ticks": [
                    {metric: (0.0 if index == 0 else float(index)) for metric in required}
                    for _ in range(16)
                ],
            }
            for seed in seeds
        }
    return {"seeds": [1, 2, 3], "arms": arms, "treatment_only": True}


def test_m04_real_gate_helpers_reject_null_metric_and_broken_first_stage() -> None:
    study = _m04_gate_study()
    assert package_export._m04_first_stage_ok(study)[0] is True
    assert package_export._m04_metrics_ok(study)[0] is True
    study["arms"]["tolerance_0"]["1"]["ticks"][0]["formal_unmet_total"] = None
    assert package_export._m04_metrics_ok(study)[0] is False
    study = _m04_gate_study()
    for tick in study["arms"]["tolerance_1"]["1"]["ticks"]:
        tick["second_hours_total"] = 0.0
    assert package_export._m04_first_stage_ok(study)[0] is False


def test_restricted_symlink_is_rejected_before_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, definitions = _build_fixture(tmp_path)
    private = root / "data/private"
    private.mkdir(parents=True)
    (private / "study.json").write_text("TOP-SECRET", encoding="utf-8")
    link = root / "studies/HIST_VNEXT/packages/H6B/privlink"
    link.symlink_to(private, target_is_directory=True)
    index_path = root / "studies/HIST_VNEXT/packages/H6B/evidence_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["cards"]["M01"]["existing_root"] = link.relative_to(root).as_posix()
    _write_json(index_path, index)
    monkeypatch.setattr(package_export, "CARD_DEFINITIONS", definitions)
    with pytest.raises(PackageExportError, match="symlink|restricted"):
        audit_package(
            root,
            mode="local-data",
            evidence_index=Path("studies/HIST_VNEXT/packages/H6B/evidence_index.json"),
        )


def test_audit_manifest_is_root_bound_not_cwd_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, definitions = _build_fixture(tmp_path)
    foreign = tmp_path / "foreign"
    (foreign / "studies").mkdir(parents=True)
    (foreign / "studies/manifest.json").write_text("{not valid json", encoding="utf-8")
    monkeypatch.chdir(foreign)
    package = _audit(root, definitions, monkeypatch)
    assert package["cards"]["M01"]["research_package_complete"] is True


def test_m01_counterevidence_helper_rejects_supported_welfare() -> None:
    study = _m01_gate_study()
    study["verdict"]["levers"]["welfare_cut"]["status"] = "UNIDENTIFIED"
    study["false_zero_policy"] = "missing is not zero"
    assert package_export._m01_counterevidence_ok(study)[0] is True
    study["verdict"]["levers"]["welfare_cut"]["status"] = "SUPPORTED"
    assert package_export._m01_counterevidence_ok(study)[0] is False


def test_m02_sensitivity_and_counterevidence_helpers() -> None:
    results = _m02_gate_results()
    results["contrasts"] = {
        "by_seed_and_regime": [
            {
                "regime": regime,
                "budget_contrast": {},
                "investment_contrast": {},
                "difference_in_differences": {},
            }
            for regime in ("base", "reduced")
            for _ in range(3)
        ]
    }
    results["verdicts"]["structural"] = {
        "by_regime": {
            "base": {
                "reason": "falsification criterion met",
                "seeds_with_non_falling_shortage_axis": [
                    {"axes": [{"axis": "x", "contrast": 0.0}]}
                ],
            }
        }
    }
    results["verdicts"]["f2_generalisation"] = {"status": "NOT_RUN"}
    assert package_export._m02_sensitivity_ok(results)[0] is True
    assert package_export._m02_counterevidence_ok(results)[0] is True
    results["verdicts"]["structural"]["by_regime"]["base"][
        "seeds_with_non_falling_shortage_axis"
    ] = [{"axes": [{"axis": "x", "contrast": -1.0}]}]
    assert package_export._m02_counterevidence_ok(results)[0] is False
    results["contrasts"]["by_seed_and_regime"] = results["contrasts"]["by_seed_and_regime"][:3]
    assert package_export._m02_sensitivity_ok(results)[0] is False


def test_m04_sensitivity_and_counterevidence_helpers() -> None:
    study = _m04_gate_study()
    assert package_export._m04_sensitivity_ok(study)[0] is True
    manifest = {
        "statistical_summary": {"first_stage": "full arm saturates the ceiling"},
        "process_failures": [{"stage": "first"}],
    }
    assert package_export._m04_counterevidence_ok(manifest, study)[0] is True
    manifest["process_failures"] = []
    assert package_export._m04_counterevidence_ok(manifest, study)[0] is False
    study["arms"]["tolerance_1"]["1"]["tolerance"] = 9.0
    assert package_export._m04_sensitivity_ok(study)[0] is False
