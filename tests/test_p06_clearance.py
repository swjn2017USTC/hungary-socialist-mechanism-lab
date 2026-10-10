"""P05 to P06 clearance gates that are independent of model validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hsm_lab.contract.guards import AVAILABLE_SCENARIOS

ROOT = Path(__file__).resolve().parents[1]


def test_control_scenario_names_are_registered() -> None:
    control = json.loads((ROOT / "config/calibration/p05.json").read_text())
    assert control["scenarios"]
    assert set(control["scenarios"].values()) <= set(AVAILABLE_SCENARIOS)
    assert control["scenarios"]["historical_replay"] == "historical_f2_replay"


def test_terminal_floors_are_declared_research_thresholds() -> None:
    control = json.loads((ROOT / "config/calibration/p05.json").read_text())
    floors = control["gates"]["terminal_floor"]
    assert floors["t1_production_last_10_min"] == 35092
    assert floors["t2_household_consumption_last_10_min"] == 2085
    assert floors["t3_treasury_solvent_tick"] == 115
    assert floors["t3_rescue_grants_lookback_ticks"] == 20
    assert "Research declarations, not fitted values" in floors["note"]


def test_clearance_never_waives_silently() -> None:
    """Every declared waiver must correspond to a rendered item.

    Regression: the waivers were first written for items that did not exist in the item
    list, so the checklist reported "Waivers: None" while the scope decision claimed five
    waivers. An item is now required by default and can only disappear through a recorded
    waiver.
    """
    from hsm_lab.calibration.clearance import run_clearance

    control = json.loads((ROOT / "config/calibration/p06_clearance.json").read_text())
    report = run_clearance(ROOT, with_runs=False)
    rendered = {item.id for item in report.items}
    declared = {str(entry["id"]) for entry in control["items"]}
    assert declared == rendered
    for waiver in control["waivers"]:
        assert waiver["item"] in rendered, waiver["item"]
        assert waiver.get("reason") and waiver.get("decided_by") and waiver.get("date")
    waived = {item.id for item in report.items if item.status == "WAIVED"}
    assert waived == {str(w["item"]) for w in control["waivers"]}


def test_scope_marker_survives_markdown_line_wrapping(tmp_path) -> None:
    from hsm_lab.calibration.clearance import _check_scope_statement

    marker = "reproduction under declared behavioural assumptions"
    docs = tmp_path / "docs" / "phases"
    docs.mkdir(parents=True)
    (docs / "P05_REPORT.md").write_text(
        "The study is re-scoped to historical reproduction under declared\n"
        "behavioural assumptions.\n"
    )
    ok, evidence = _check_scope_statement(tmp_path, marker)
    assert ok, evidence


def test_unwaived_unsatisfied_item_is_open_and_not_cleared(tmp_path) -> None:
    from hsm_lab.calibration.clearance import render_markdown, run_clearance

    config = {
        "schema_version": "1",
        "scope_decision": {"decision": "test", "decided_by": "test", "date": "2026-10-10"},
        "waivers": [],
        "items": [
            {
                "id": "unsatisfied_thing",
                "kind": "unsatisfied",
                "note": "deliberately unmet",
                "description": "a required item with no waiver",
                "required": True,
            }
        ],
    }
    config_path = tmp_path / "p06_clearance.json"
    config_path.write_text(json.dumps(config))

    report = run_clearance(tmp_path, config_path=config_path, with_runs=False)

    assert not report.cleared
    assert [item.id for item in report.open_items] == ["unsatisfied_thing"]
    markdown = render_markdown(report)
    assert "**OPEN**" in markdown
    assert "deliberately unmet" in markdown


def test_waived_unsatisfied_item_clears_and_renders_the_reason(tmp_path) -> None:
    from hsm_lab.calibration.clearance import render_markdown, run_clearance

    config = {
        "schema_version": "1",
        "scope_decision": {"decision": "test", "decided_by": "user", "date": "2026-10-10"},
        "waivers": [
            {
                "item": "unsatisfied_thing",
                "reason": "decided to proceed on the reproduction scope",
                "decided_by": "user",
                "date": "2026-10-10",
            }
        ],
        "items": [
            {
                "id": "unsatisfied_thing",
                "kind": "unsatisfied",
                "note": "deliberately unmet",
                "description": "a required item with a waiver",
                "required": True,
            }
        ],
    }
    config_path = tmp_path / "p06_clearance.json"
    config_path.write_text(json.dumps(config))

    report = run_clearance(tmp_path, config_path=config_path, with_runs=False)

    assert report.cleared
    assert report.items[0].status == "WAIVED"
    markdown = render_markdown(report)
    assert "decided to proceed on the reproduction scope" in markdown


def test_p06_arm_summary_check_requires_all_completed_hash_identified_arms(tmp_path) -> None:
    from hsm_lab.calibration.clearance import _check_p06_arms_summary

    ok, evidence = _check_p06_arms_summary(tmp_path)
    assert not ok
    assert "regenerate the v4 parent" in evidence

    required = {
        "1968": ["control", "no-reform", "nem-plus", "nos-hu", "digital-nem"],
        "1973": [
            "control",
            "borrowing-smoothing",
            "consumption-restraint",
            "investment-restraint",
            "price-wage-compensation",
            "hard-budget",
        ],
        "political": [
            "control",
            "coalition-weights",
            "soviet-constraint",
            "consumer-import",
            "cultural-openness",
            "second-economy",
        ],
    }
    arms = []
    next_digest = 0
    for family, arm_ids in required.items():
        for arm_id in arm_ids:
            next_digest += 1
            digest = f"{next_digest:064x}"
            output_dir = f"outputs/p06-arms/{family}/{arm_id}"
            run_dir = tmp_path / output_dir
            run_dir.mkdir(parents=True)
            (run_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "completed_ticks": 116,
                        "last_completed_quarter": "1985Q4",
                        "parameter_hash": "b" * 64,
                        "deterministic_replay_digest": digest,
                    }
                )
            )
            arms.append(
                {
                    "family": family,
                    "arm_id": arm_id,
                    "output_dir": output_dir,
                    "status": "completed",
                    "completed_ticks": 116,
                    "last_completed_quarter": "1985Q4",
                    "parameter_hash": "b" * 64,
                    "intervention_hash": "c" * 64,
                    "replay_digest": digest,
                    "metrics": {"guardrails": {"accounting_invariants_pass": True}},
                }
            )
    summary_dir = tmp_path / "outputs" / "p06-arms"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "summary.json").write_text(json.dumps({"arms": arms}))
    ok, evidence = _check_p06_arms_summary(tmp_path)
    assert ok, evidence

    arms.pop()
    (summary_dir / "summary.json").write_text(json.dumps({"arms": arms}))
    ok, evidence = _check_p06_arms_summary(tmp_path)
    assert not ok
    assert "political arms missing" in evidence


def test_trade_transmission_clearance_reads_run_summary_without_pinning_outcome(tmp_path) -> None:
    from hsm_lab.calibration.clearance import _check_p06_trade_transmission

    run = {
        "scenario_id": "declared_scenario",
        "parameter_hash": "a" * 64,
        "seed": 1729,
        "deterministic_replay_digest": "b" * 64,
        "completed_ticks": 116,
        "last_completed_quarter": "1985Q4",
        "by_commodity": {
            "g01_solid_fuels": {
                "imports": {"cmea": 1.0, "convertible": 2.0},
                "exports": {"cmea": 3.0, "convertible": 4.0},
            }
        },
        "invariants": {
            "max_finance_abs_residual": 0.0,
            "max_material_abs_residual": 0.0,
        },
    }
    summary = {
        "schema_version": 1,
        "scenario_definition": {"scenario_sha256": "c" * 64},
        "runs": {arm_id: dict(run) for arm_id in ("C0", "C1", "C2")},
    }
    evidence_path = tmp_path / "outputs/p06-trade-transmission/summary.json"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text(json.dumps(summary))

    passed, _ = _check_p06_trade_transmission(tmp_path)
    assert passed

    summary["runs"].pop("C2")
    evidence_path.write_text(json.dumps(summary))
    passed, evidence = _check_p06_trade_transmission(tmp_path)
    assert not passed
    assert "C0, C1 and conditional C2" in evidence


def test_release_manifest_check_requires_frozen_digests_and_verbatim_waivers(tmp_path) -> None:
    from hsm_lab.calibration.clearance import _check_p06_release_manifest

    docs = tmp_path / "docs/phases"
    docs.mkdir(parents=True)
    config_dir = tmp_path / "config/calibration"
    config_dir.mkdir(parents=True)
    crosswalk = config_dir / "p06_reproduction_crosswalk.json"
    crosswalk.write_text("{}")
    reason = "the declared waiver reason"
    (config_dir / "p06_clearance.json").write_text(
        json.dumps({"waivers": [{"item": "gate", "reason": reason}]})
    )
    digest = hashlib.sha256(crosswalk.read_bytes()).hexdigest()
    release = docs / "P06_RELEASE.md"
    release.write_text(
        "92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d "
        "45999d895dac3b84bc69918273eed0c3b51489cba9ddae4fdbb2a20c54411f27 "
        f"{digest} 26 PASS / 4 WAIVED / 0 OPEN 416 passed, 0 failed calibrated = 0 "
        "no parameter is identified Reserved window 1986Q1–1988Q4 was never read "
        f"{reason}"
    )
    passed, evidence = _check_p06_release_manifest(tmp_path)
    assert passed, evidence
    release.write_text(release.read_text().replace(reason, "edited waiver"))
    passed, evidence = _check_p06_release_manifest(tmp_path)
    assert not passed
    assert "waiver reason" in evidence


def test_bundle_rebuilt_check_compares_both_recorded_digests_and_parameter_hashes(
    tmp_path,
) -> None:
    from hsm_lab.calibration.clearance import _check_p06_bundle_rebuilt

    cases = (
        ("p05-historical-replay", "replayed-p05-historical", "historical_f2_replay"),
        ("trade-scenario", "replayed-trade-c1", "historical_f2_trade_scenario"),
    )
    for bundle_name, replay_name, scenario in cases:
        bundle_dir = tmp_path / "outputs/p06-release-bundles" / bundle_name
        replay_dir = tmp_path / "outputs/p06-release-bundles" / replay_name
        bundle_dir.mkdir(parents=True)
        replay_dir.mkdir(parents=True)
        (bundle_dir / "bundle.json").write_text(
            json.dumps(
                {
                    "scenario_id": scenario,
                    "deterministic_replay_digest": "a" * 64,
                    "parameter_hash": "b" * 64,
                }
            )
        )
        (replay_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "status": "completed",
                    "deterministic_replay_digest": "a" * 64,
                    "parameter_hash": "b" * 64,
                }
            )
        )
    passed, evidence = _check_p06_bundle_rebuilt(tmp_path)
    assert passed, evidence
    replay = tmp_path / "outputs/p06-release-bundles/replayed-trade-c1/manifest.json"
    payload = json.loads(replay.read_text())
    payload["deterministic_replay_digest"] = "c" * 64
    replay.write_text(json.dumps(payload))
    passed, evidence = _check_p06_bundle_rebuilt(tmp_path)
    assert not passed
    assert "differs" in evidence
