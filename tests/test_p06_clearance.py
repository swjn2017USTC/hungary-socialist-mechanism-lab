"""P05 to P06 clearance gates that are independent of model validation."""

from __future__ import annotations

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
