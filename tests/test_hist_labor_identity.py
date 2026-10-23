"""H5D labour identity contract tests.

This file is the H5D whitelisted test path. It currently gates the *declared*
labour institution/unit spec: units, aggregate labour totals, employment rules,
absence/effort separation and exclusivity with the H5B household time budget.
The adapter's behavioural identity tests land in the same file when H5D
implementation is separately authorized; until then ``implementation_status`` is
``NOT_RUN`` and there is nothing behavioural to assert.

Every mutation test proves the gate is load-bearing: it deep-copies the spec,
breaks one declared invariant and requires the validator to reject it.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from hsm_lab.contract.base import ConfigError, ResearchGateError
from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine import accounting as accounting_module
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.material import (
    canonical_material_bytes,
    load_material_forcing,
    tick_material,
)
from hsm_lab.engine.network import build_material_network
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import capture_material_stocks, initialize_material
from hsm_lab.institutions import labor_state_adapter as labor
from hsm_lab.storage.checkpoint import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = REPO_ROOT / "studies/HIST_VNEXT/M03/labor_institution_spec_v1.json"
MODULE_PATH = REPO_ROOT / "studies/HIST_VNEXT/M03/labor_spec.py"
RUNNER_PATH = REPO_ROOT / "studies/HIST_VNEXT/M03/labor_runner.py"


def _load_validator():
    module_spec = importlib.util.spec_from_file_location("h5d_labor_spec", MODULE_PATH)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


labor_spec = _load_validator()


@pytest.fixture()
def spec() -> dict[str, Any]:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def _failures(spec: dict[str, Any]) -> list[str]:
    return labor_spec.validate_spec(spec, REPO_ROOT)


def test_spec_file_passes_every_declared_invariant() -> None:
    """S1-S10 together: the repository spec is internally consistent."""
    loaded, failures = labor_spec.validate_repository(REPO_ROOT)
    assert loaded["spec_id"] == "hist-vnext-labor-institution-v1"
    assert failures == []


def test_spec_is_declared_and_not_wired(spec: dict[str, Any]) -> None:
    """S1: the spec is a declaration, not an implementation."""
    assert spec["status"] == "DECLARED_NOT_IMPLEMENTED"
    assert spec["implementation_status"] == "NOT_RUN"
    assert spec["default_off"] is True
    assert spec["wired_into_engine"] is False
    mutated = copy.deepcopy(spec)
    mutated["status"] = "IMPLEMENTED"
    assert any(f.startswith("S1 status") for f in _failures(mutated))


def test_time_endowment_decomposition(spec: dict[str, Any]) -> None:
    """S2: 1040 = 520 + 52 + 130 + 338 must hold exactly."""
    units = spec["unit_contract"]
    assert units["hours_per_worker_quarter_endowment"] == 1040.0
    assert units["hours_per_worker_quarter_formal"] == 520.0
    assert units["hours_per_worker_quarter_plot_cap"] == 52.0
    assert units["hours_per_worker_quarter_second_cap"] == 130.0
    assert units["hours_headroom_for_queue_search_leisure"] == 338.0
    assert (
        units["hours_per_worker_quarter_formal"]
        + units["hours_per_worker_quarter_plot_cap"]
        + units["hours_per_worker_quarter_second_cap"]
        + units["hours_headroom_for_queue_search_leisure"]
        == units["hours_per_worker_quarter_endowment"]
    )

    mutated = copy.deepcopy(spec)
    mutated["unit_contract"]["hours_headroom_for_queue_search_leisure"] = 300.0
    assert any(f.startswith("S2 decomposition") for f in _failures(mutated))


def test_contract_bindings_match_live_defaults(spec: dict[str, Any]) -> None:
    """S3: every spec constant equals the contract default it claims to bind."""
    assert len(spec["contract_bindings"]) == 13
    assert _failures(spec) == []

    mutated = copy.deepcopy(spec)
    mutated["unit_contract"]["hours_per_worker_quarter_formal"] = 519.0
    failures = _failures(mutated)
    assert any("S3 unit_contract.hours_per_worker_quarter_formal" in f for f in failures)


def test_call_chain_anchors_still_exist(spec: dict[str, Any]) -> None:
    """S4: a mutated anchor must still be rejected by the frozen validator."""
    assert len(spec["call_chain"]) == 12
    mutated = copy.deepcopy(spec)
    mutated["call_chain"][3]["anchor"] = "labor_arr = np.asarray(state.labor_that_does_not_exist"
    assert any("S4 anchor not found" in f for f in _failures(mutated))


def test_household_time_axes_are_exclusive_and_exhaustive(spec: dict[str, Any]) -> None:
    """S5: exactly six disjoint axes close the endowment every quarter."""
    identity = next(i for i in spec["identities"] if i["id"] == "I1b")
    assert list(identity["axes"]) == [
        "h_formal",
        "h_plot",
        "h_second",
        "h_queue",
        "h_search",
        "h_leisure",
    ]
    assert identity["exclusive"] is True
    assert identity["exhaustive"] is True
    assert "household_time_endowment" in identity["enforced_by"]

    mutated = copy.deepcopy(spec)
    mutated["identities"] = [i for i in mutated["identities"] if i["id"] != "I1b"]
    assert any("S5 exclusivity identity" in f for f in _failures(mutated))


def test_no_historical_or_calibrated_claim(spec: dict[str, Any]) -> None:
    """S6: the spec admits no series and calibrates nothing."""
    assert spec["historical"]["status"] == "UNIDENTIFIED"
    assert spec["historical"]["admitted_series"] == []
    assert spec["historical"]["employed_for_parameters"] == []

    mutated = copy.deepcopy(spec)
    mutated["rules"]["release"]["calibrated"] = True
    assert any("S6 calibrated" in f for f in _failures(mutated))


def test_hoarding_index_excludes_wages(spec: dict[str, Any]) -> None:
    """S7: a wage-only rule must not be able to move the hoarding index."""
    hoarding = spec["derived_metrics"]["unused_labour_share"]
    assert hoarding["computable"] is False
    excluded = " ".join(hoarding["excluded_inputs"])
    assert "organization_wage_arrears" in excluded
    assert "wage_rate" in excluded
    assert "wage" not in hoarding["hours_supplied_establishment"]
    assert "wage" not in hoarding["hours_supplied_effective"]
    assert "wage" not in hoarding["hours_used"]

    mutated = copy.deepcopy(spec)
    mutated["derived_metrics"]["unused_labour_share"]["hours_used"] = (
        "wage_rate * activity_realized"
    )
    assert any("S7 wage terms" in f for f in _failures(mutated))


def test_labour_totals_are_declared_unreconciled(spec: dict[str, Any]) -> None:
    """S8: the two totals are different quantities; the gap is explicit."""
    reconciliation = spec["reconciliation"]
    assert reconciliation["status"] == "UNRECONCILED_DECLARED"
    assert reconciliation["same_quantity"] is False
    assert "1.0 * N_equivalent_persons" in reconciliation["organization_side"]
    assert "0.9 productive + 0.1 distribution" in reconciliation["organization_side"]
    assert "N_working" in reconciliation["household_side"]
    assert reconciliation["gap_quantity"]["unit"] == "worker_equivalent_quarter"
    assert "L_WE" in reconciliation["gap_quantity"]["definition"]
    assert reconciliation["unallocated_labor"]["computable_today"] is False
    assert reconciliation["forbidden"]

    mutated = copy.deepcopy(spec)
    mutated["reconciliation"]["same_quantity"] = True
    failures = _failures(mutated)
    assert any("S8 same_quantity" in f for f in failures)


def test_stop_conditions_cover_the_contract(spec: dict[str, Any]) -> None:
    """S9: the mandated STOPs are all present."""
    stops = " ".join(spec["stop_conditions"])
    for token in (
        "full migration of legacy state versions",
        "changes any default behaviour",
        "no aggregate labour total constraint",
        "wage or arrears substitutes",
        "asserted to be equal without an explicit slack",
    ):
        assert token in stops

    mutated = copy.deepcopy(spec)
    mutated["stop_conditions"] = ["no aggregate labour total constraint"]
    assert any("S9 STOP condition missing" in f for f in _failures(mutated))


def test_employment_state_is_decomposed(spec: dict[str, Any]) -> None:
    """S10: establishment, headcount, absence, effective hours and release differ."""
    assert set(spec["rules"]) == {
        "establishment",
        "hire",
        "release",
        "absence",
        "effort",
    }
    units = {entry["symbol"]: entry["unit"] for entry in spec["state_declarations"]}
    assert units["L_WE"] == "worker_equivalent_quarter"
    assert units["E_i"] == "person"
    assert units["H_i"] == "person"
    assert units["A_i"] == "fraction"
    assert units["e_i"] == "fraction"
    assert units["H_eff_i"] == "hour/quarter"
    assert spec["rules"]["establishment"]["unit"] == "person"
    assert spec["rules"]["release"]["unit"] == "person/quarter"

    mutated = copy.deepcopy(spec)
    mutated["state_declarations"] = [
        entry for entry in mutated["state_declarations"] if entry["symbol"] != "H_eff_i"
    ]
    assert any("S10 state declaration missing: H_eff_i" in f for f in _failures(mutated))


def test_effective_hours_identity_keeps_absence_and_effort_separate(
    spec: dict[str, Any],
) -> None:
    """I2: H_eff is bound by the spec, consumed by I4, and evaluated with its factors."""
    i2 = next(i for i in spec["identities"] if i["id"] == "I2")
    assert "(1 - A_i)" in i2["statement"]
    assert "e_i" in i2["statement"]
    assert "I4" in i2["consumed_by"]
    i4 = next(i for i in spec["identities"] if i["id"] == "I4")
    assert "H_eff_i" in i4["statement"]

    hours = spec["unit_contract"]["hours_per_worker_equivalent_quarter"]
    headcount, absence, effort = 10.0, 0.1, 0.8
    effective = headcount * hours * (1.0 - absence) * effort
    assert effective == pytest.approx(3744.0)
    # Effective hours are the production input; nominal labour is only the stock.
    assert effective < headcount * hours

    stripped = copy.deepcopy(spec)
    stripped["identities"] = [
        i for i in stripped["identities"] if i["id"] != "I4"
    ]
    assert any("S11 identity missing: I4" in f for f in _failures(stripped))


def test_measured_block_is_arithmetically_consistent(spec: dict[str, Any]) -> None:
    """S17: the C0 evidence block cannot be fabricated or left pre-clip."""
    measured = spec["derived_metrics"]["unused_labour_share"]["measured_c0_tick0"]
    # The engine's formal-hours identity uses unweighted working adults (11 330),
    # not the weighted count (11 250); the spec records both and adopts the former.
    assert measured["n_working"] == 11330.0
    assert measured["n_working_weighted"] == 11250.0
    assert measured["sum_capacity_labour_we"] == 12750.0
    assert measured["sum_e_raw"] == pytest.approx(11475.0)
    assert measured["pro_rata_factor"] == pytest.approx(11330.0 / 11475.0)
    assert measured["net_establishment_factor"] == pytest.approx(0.9 * 11330.0 / 11475.0)
    assert measured["sum_e_after_clip"] == pytest.approx(11330.0)
    assert measured["hours_supplied"] == pytest.approx(5891600.0)
    assert measured["hours_used"] == pytest.approx(520.0 * measured["worker_equivalents_used"])
    assert measured["establishment_unused_share"] == pytest.approx(
        1.0 - measured["hours_used"] / measured["hours_supplied"]
    )
    assert measured["capacity_denominator_index"] == pytest.approx(
        1.0 - measured["worker_equivalents_used"] / measured["sum_capacity_labour_we"]
    )
    assert measured["unused_we_vs_establishment"] == pytest.approx(
        measured["sum_e_after_clip"] - measured["worker_equivalents_used"]
    )
    assert measured["hours_used"] < measured["hours_supplied"]

    pre_clip = copy.deepcopy(spec)
    pre_clip["derived_metrics"]["unused_labour_share"]["measured_c0_tick0"][
        "hours_supplied"
    ] = 6630000.0
    assert any("S17 hours_supplied" in f for f in _failures(pre_clip))

    fabricated = copy.deepcopy(spec)
    fabricated["derived_metrics"]["unused_labour_share"]["measured_c0_tick0"][
        "establishment_unused_share"
    ] = 0.1692
    assert any("S17 establishment_unused_share" in f for f in _failures(fabricated))

    gap_faked = copy.deepcopy(spec)
    gap_faked["reconciliation"]["nominal_effective_gap"]["measured_c0_tick0"] = 9999.0
    assert any("S17b nominal_effective_gap" in f for f in _failures(gap_faked))

    no_eff = copy.deepcopy(spec)
    for i in no_eff["identities"]:
        if i["id"] == "I4":
            i["statement"] = "activity_target_i <= L_WE_i / labor_per_activity_i"
    assert any("S17 I4 must bound" in f for f in _failures(no_eff))


def test_aggregate_formulas_cannot_regress(spec: dict[str, Any]) -> None:
    """S18: the 0.9/1.0 split, the I2 factors and the no-year rule survive edits."""
    i5b = next(i for i in spec["identities"] if i["id"] == "I5b")
    assert "1.0 * N_equivalent_persons" in i5b["statement"]
    assert "1.0 * N_equivalent_persons" in spec["reconciliation"]["organization_side"]

    reverted = copy.deepcopy(spec)
    reverted["identities"] = [
        {**i, "statement": "sum_{all_organizations} L_WE_i = 0.9 * N_equivalent_persons"}
        if i["id"] == "I5b"
        else i
        for i in reverted["identities"]
    ]
    assert any("S18 I5b" in f for f in _failures(reverted))

    side_reverted = copy.deepcopy(spec)
    side_reverted["reconciliation"]["organization_side"] = (
        "sum_i L_WE_i = 0.9 * N_equivalent_persons"
    )
    assert any("S18 organization_side" in f for f in _failures(side_reverted))

    historical_prose = copy.deepcopy(spec)
    historical_prose["rules"]["absence"]["absence_adjustment_i"] = (
        "declared path matching 0.072 absence recorded in 1975"
    )
    assert any("S18 calendar year" in f for f in _failures(historical_prose))

    document_prose = copy.deepcopy(spec)
    document_prose["document"] += " Calibrated to 1975 CSO reports."
    assert any("S18 calendar year" in f for f in _failures(document_prose))

    identity_prose = copy.deepcopy(spec)
    identity_prose["identities"][0]["note"] = "matched 1975 observations"
    assert any("S18 calendar year" in f for f in _failures(identity_prose))

    quarter_prose = copy.deepcopy(spec)
    quarter_prose["rules"]["absence"]["absence_adjustment_i"] = "fitted in 1957Q1"
    assert any("S18 calendar year" in f for f in _failures(quarter_prose))

    side_merged = copy.deepcopy(spec)
    side_merged["reconciliation"]["household_side"] = (
        "h_formal / 520 = 1.0 * N_equivalent_persons"
    )
    assert any("S18 household_side" in f for f in _failures(side_merged))


def test_every_identity_is_declared(spec: dict[str, Any]) -> None:
    """S11: the aggregate labour identity is split, not silently merged."""
    ids = [entry["id"] for entry in spec["identities"]]
    assert ids == ["I1a", "I1b", "I2", "I3", "I4", "I5a", "I5b", "I6", "I7", "I8"]
    i5a = next(i for i in spec["identities"] if i["id"] == "I5a")
    i5b = next(i for i in spec["identities"] if i["id"] == "I5b")
    assert "sum_{productive}" in i5a["statement"]
    assert "0.9" in i5a["statement"]
    assert "sum_{all_organizations}" in i5b["statement"]
    assert "1.0" in i5b["statement"]
    # The distribution branch is a real 10% of nominal labour, not zero.
    assert i5b["measured_c0_tick0"]["all"] == 17000.0
    assert i5b["measured_c0_tick0"]["productive"] == 15300.0

    mutated = copy.deepcopy(spec)
    mutated["identities"] = [i for i in mutated["identities"] if i["id"] != "I5b"]
    assert any("S11 identity missing: I5b" in f for f in _failures(mutated))


def test_hoarding_metric_carries_the_hour_conversion(spec: dict[str, Any]) -> None:
    """S12: labour_per_activity is persons/activity, so the metric needs x520."""
    hoarding = spec["derived_metrics"]["unused_labour_share"]
    assert hoarding["hours_used"].startswith("520 *")
    assert hoarding["unit_of_labor_per_activity"] == "person per activity unit"
    assert "MaterialTickFlows.organization_realized" in hoarding["unit_of_activity_realized"]
    assert hoarding["computable"] is False

    mutated = copy.deepcopy(spec)
    mutated["derived_metrics"]["unused_labour_share"]["hours_used"] = (
        "sum_i (labor_per_activity_i * activity_realized_i)"
    )
    assert any("S12 hours_used" in f for f in _failures(mutated))


def test_establishment_bridges_units_and_is_not_output_anchored(
    spec: dict[str, Any],
) -> None:
    """S13: capacity is in activity units; release must actually be consumed."""
    establishment = spec["rules"]["establishment"]
    assert "labor_per_activity_i" in establishment["target_rule"]
    assert "min(1, N_working / sum_j E_j_raw)" in establishment["target_rule"]
    assert "realized" not in establishment["target_rule"].lower()
    assert "scale(t) * H_i_hire_raw(t)" in spec["rules"]["hire"]["rule"]
    assert "applied before hiring" in spec["rules"]["release"]["rule"]

    output_anchored = copy.deepcopy(spec)
    output_anchored["rules"]["establishment"]["target_rule"] = (
        "E_i = realized_output_i / 520"
    )
    assert any("S13 establishment must not anchor" in f for f in _failures(output_anchored))

    inert_release = copy.deepcopy(spec)
    inert_release["rules"]["hire"]["rule"] = "H_i(t) = H_i(t-1) + H_i_hire(t)"
    assert any("S13 hire must subtract" in f for f in _failures(inert_release))


def test_gate_retains_its_structural_guards(spec: dict[str, Any]) -> None:
    """S14: bindings, forbidden shortcuts, timing bans and metric exclusions."""
    fields = {entry["spec_field"] for entry in spec["contract_bindings"]}
    assert "rules.effort.effort_floor" in fields
    assert "rules.effort.effort_grievance_weight" in fields
    assert len(spec["negative_controls"]) == 3
    assert {c["status"] for c in spec["negative_controls"]} == {"NOT_RUN"}
    assert "any price index" in " ".join(
        spec["derived_metrics"]["unused_labour_share"]["excluded_inputs"]
    )

    dropped = copy.deepcopy(spec)
    dropped["contract_bindings"] = [
        b for b in dropped["contract_bindings"] if b["spec_field"] != "rules.effort.effort_floor"
    ]
    assert any("S14 contract binding missing" in f for f in _failures(dropped))

    weakened = copy.deepcopy(spec)
    weakened["reconciliation"]["forbidden"] = ["nothing"]
    assert any("S14 forbidden shortcut missing" in f for f in _failures(weakened))

    emptied = copy.deepcopy(spec)
    emptied["timing"]["must_not"] = []
    assert any("S14 timing.must_not missing" in f for f in _failures(emptied))

    advanced = copy.deepcopy(spec)
    advanced["negative_controls"][0]["status"] = "RUN"
    assert any("S14 negative control N1" in f for f in _failures(advanced))


def test_slack_quantities_are_dimensionally_named(spec: dict[str, Any]) -> None:
    """S15: unemployment is persons; the WE gap is a separate reported quantity."""
    reconciliation = spec["reconciliation"]
    assert reconciliation["unallocated_labor"]["unit"] == "person"
    assert reconciliation["gap_quantity"]["unit"] == "worker_equivalent_quarter"
    assert reconciliation["gap_quantity"]["computable_today"] is True
    assert reconciliation["unallocated_labor"]["computable_today"] is False

    mutated = copy.deepcopy(spec)
    mutated["reconciliation"]["unallocated_labor"]["unit"] = "worker_equivalent_quarter"
    assert any("S15 unallocated_labor" in f for f in _failures(mutated))


def test_rule_numbers_are_bound_or_declared(spec: dict[str, Any]) -> None:
    """S16: no rule number may appear without a binding or a declaration."""
    names = {entry["name"] for entry in spec["declared_parameters"]}
    assert "rules.release.max_release_fraction_per_quarter" in names
    assert "rules.hire.hire_capacity_share_per_quarter" in names
    assert all(entry["calibrated"] is False for entry in spec["declared_parameters"])

    undeclared = copy.deepcopy(spec)
    undeclared["rules"]["establishment"]["target_utilization"] = 0.85
    assert any("S16 rule number" in f for f in _failures(undeclared))

    fabricated = copy.deepcopy(spec)
    fabricated["rules"]["absence"]["mean_absence_rate_1975"] = 0.074
    assert any("S16 rule number" in f for f in _failures(fabricated))

    relabelled = copy.deepcopy(spec)
    relabelled["declared_parameters"][0]["calibrated"] = True
    assert any("S16 declared parameter" in f for f in _failures(relabelled))


def test_reconciliation_rule_keeps_the_ban(spec: dict[str, Any]) -> None:
    """S16: the gap may not be reconciled through wages."""
    rule = spec["reconciliation"]["required_adapter_rule"]
    assert "unallocated_labor" in rule
    assert "never absorb" in rule

    mutated = copy.deepcopy(spec)
    mutated["reconciliation"]["required_adapter_rule"] = "reconcile the gap through wages"
    assert any("S16 required_adapter_rule" in f for f in _failures(mutated))


def test_metric_is_labelled_technical_not_institutional(spec: dict[str, Any]) -> None:
    """S17: the raw share includes utilization and seasonality; it is not hoarding."""
    hoarding = spec["derived_metrics"]["unused_labour_share"]
    assert hoarding["name"] == "labour_underutilization"
    assert hoarding["underutilization_share"]["range"] == [0.0, 1.0]
    assert "H_eff" in hoarding["underutilization_share"]["definition"]
    assert hoarding["establishment_unused_share"]["range"] == "unrestricted"
    assert hoarding["institutional_attribution"]["status"] == "UNIDENTIFIED"
    assert hoarding["institutional_attribution"]["status"] == "UNIDENTIFIED"
    assert hoarding["underutilization_share"]["computable"] is False
    assert "after the adapter" in hoarding["activity_realized_bound"]
    slack = hoarding["technical_slack"]
    assert slack["utilization_slack_we"] + slack["seasonal_slack_we"] == pytest.approx(
        slack["total_unused_we"]
    )
    assert slack["total_unused_we"] == pytest.approx(
        slack["capacity_labour_we"] - slack["realized_we"]
    )
    # 0.1692 is the capacity-denominator variant, not the reported metric.
    assert hoarding["capacity_denominator_variant"]["value"] == pytest.approx(0.16923076923076907)
    assert spec["rules"]["establishment"]["coverage"] == (
        "see scope.coverage_boundary (single source of truth)"
    )
    assert spec["evidence_scope"]["calendar_year_scan"]

    mislabelled = copy.deepcopy(spec)
    mislabelled["derived_metrics"]["unused_labour_share"]["institutional_attribution"][
        "status"
    ] = "IDENTIFIED"
    assert any("S17 institutional attribution" in f for f in _failures(mislabelled))


def test_coverage_boundary_is_declared(spec: dict[str, Any]) -> None:
    """S19: the capacity-less distribution branch is declared, not dropped."""
    boundary = spec["scope"]["coverage_boundary"]
    assert "productive branch" in boundary["establishment_covered"]
    assert len(boundary["not_covered"]) == 2
    assert "1700" in boundary["consequence"]
    split = spec["reconciliation"]["nominal_effective_gap"]["split"]
    assert split["distribution_uncovered_we"] == 1700.0
    assert split["productive_nominal_effective_gap_we"] == 3970.0
    assert split["distribution_uncovered_we"] + split[
        "productive_nominal_effective_gap_we"
    ] == pytest.approx(spec["reconciliation"]["nominal_effective_gap"]["measured_c0_tick0"])

    dropped = copy.deepcopy(spec)
    dropped["scope"]["coverage_boundary"]["not_covered"] = []
    assert any("S19 coverage_boundary" in f for f in _failures(dropped))


def test_metric_name_has_no_stale_alias(spec: dict[str, Any]) -> None:
    """S20: the rename is enforced; no hoarding_index key or prose survives."""
    reverted = copy.deepcopy(spec)
    reverted["derived_metrics"]["labor_hoarding_index"] = reverted["derived_metrics"].pop(
        "unused_labour_share"
    )
    assert any("S20 stale hoarding_index key" in f for f in _failures(reverted))

    prose = copy.deepcopy(spec)
    prose["negative_controls"][0]["requirement"] = "wage must not move hoarding_index"
    assert any("S20 stale hoarding_index reference" in f for f in _failures(prose))

    legacy_metric = copy.deepcopy(spec)
    legacy_metric["derived_metrics"]["unused_labour_share"][
        "institutional_hoarding_index"
    ] = {"computable": False}
    assert any("S20 stale hoarding_index key" in f for f in _failures(legacy_metric))


def test_coverage_text_is_a_single_source(spec: dict[str, Any]) -> None:
    """S21: the establishment rule cannot restate the boundary in free text."""
    doubled = copy.deepcopy(spec)
    doubled["rules"]["establishment"]["coverage"] = (
        "wholesale and retail also receive establishments"
    )
    assert any("S21 establishment.coverage" in f for f in _failures(doubled))

    unscoped = copy.deepcopy(spec)
    del unscoped["evidence_scope"]["measured_block"]
    assert any("S22 evidence_scope" in f for f in _failures(unscoped))


def test_money_never_becomes_hours(spec: dict[str, Any]) -> None:
    """S23: money is confined to I6 and to prohibition prose; no conversion anywhere."""
    i6 = next(i for i in spec["identities"] if i["id"] == "I6")
    assert i6["statement"] == "wage_bill_open_i = 6.0 * L_WE_i (money/quarter)"
    assert "never" in i6["note"].lower()
    assert "520" not in i6["note"]

    inverted = copy.deepcopy(spec)
    for identity in inverted["identities"]:
        if identity["id"] == "I2":
            identity["statement"] = "H_eff_i = wage_bill_open_i / 6.0 * 520"
    assert any("S23 money-to-hours conversion" in f for f in _failures(inverted))

    smuggled_note = copy.deepcopy(spec)
    smuggled_note["identities"][7]["note"] += (
        " never inferred, except that H_eff_i = wage_bill_open_i / 6.0 * 520 is the definition"
    )
    assert any("S23" in f for f in _failures(smuggled_note))

    declaration = copy.deepcopy(spec)
    for entry in declaration["state_declarations"]:
        if entry["symbol"] == "H_eff_i":
            entry["producer_required"] = "H_eff_i = wage_bill_open_i / 6.0 * 520"
    assert any("S23 money-to-hours conversion" in f for f in _failures(declaration))

    metric = copy.deepcopy(spec)
    metric["derived_metrics"]["unused_labour_share"]["underutilization_share"][
        "definition"
    ] = "1 - hours_used / H_eff_i with H_eff_i = wage_bill_open_i / 6.0 * 520"
    assert any("S23 money-to-hours conversion" in f for f in _failures(metric))

    ruled = copy.deepcopy(spec)
    ruled["rules"]["release"]["rule"] = "release scaled by wage_bill_open"
    assert any("S23 unqualified money term at rules.release.rule" in f for f in _failures(ruled))

    unit_contract = copy.deepcopy(spec)
    unit_contract["unit_contract"]["hours_per_wage_bill_unit"] = (
        "520 hours per wage_bill; H_eff_i = wage_bill_open_i / 6.0 * 520"
    )
    assert any("S23 money-to-hours conversion" in f for f in _failures(unit_contract))

    matrix = copy.deepcopy(spec)
    matrix["test_matrix"].append(
        {"id": "S30", "kind": "spec", "assertion": "H_eff_i = wage_bill_open_i / 6.0 * 520"}
    )
    assert any("S23 money-to-hours conversion" in f for f in _failures(matrix))

    control = copy.deepcopy(spec)
    control["negative_controls"][1]["requirement"] = (
        "measured as 1 - hours_used / (wage_bill_open_i / 6.0 * 520)"
    )
    assert any("S23 money-to-hours conversion" in f for f in _failures(control))

    payroll = copy.deepcopy(spec)
    payroll["state_declarations"][5]["producer_required"] = (
        "H_eff_i = payroll_open_i / 6.0 * 520"
    )
    assert any("S23 money-to-hours conversion" in f for f in _failures(payroll))

    sibling = copy.deepcopy(spec)
    sibling["derived_metrics"]["unused_labour_share"]["excluded_inputs_extra"] = (
        "H_eff_i = wage_bill_open_i / 6.0 * 520"
    )
    assert any("S23 money-to-hours conversion" in f for f in _failures(sibling))

    phrase_hidden = copy.deepcopy(spec)
    phrase_hidden["document"] += " no money term; H_eff_i = wage_bill_open_i / 6.0 * 520"
    assert any("S23 money-to-hours conversion" in f for f in _failures(phrase_hidden))

    currency = copy.deepcopy(spec)
    currency["state_declarations"][5]["producer_required"] = "Ft_open_i / 6.0 * 520"
    assert any("S23 money-to-hours conversion" in f for f in _failures(currency))

    salary = copy.deepcopy(spec)
    salary["state_declarations"][5]["producer_required"] = "salary_open_i / 6.0 * 520"
    assert any("S23 money-to-hours conversion" in f for f in _failures(salary))

    i6_check = copy.deepcopy(spec)
    for identity in i6_check["identities"]:
        if identity["id"] == "I6":
            identity["check"] = "H_eff_i = wage_bill_open_i / 6.0 * 520"
    assert any("S23 money-to-hours conversion" in f for f in _failures(i6_check))

    symbolic = copy.deepcopy(spec)
    for identity in symbolic["identities"]:
        if identity["id"] == "I6":
            identity["check"] = (
                "H_eff_i = wage_bill_open_i / wage_rate "
                "* hours_per_worker_equivalent_quarter"
            )
    assert any("S23 money-to-hours conversion" in f for f in _failures(symbolic))

    nested = copy.deepcopy(spec)
    for identity in nested["identities"]:
        if identity["id"] == "I6":
            identity["extra"] = {
                "note": [
                    "never infer hours except H_eff_i = wage_bill_open_i / wage_rate "
                    "* hours_per_worker_equivalent_quarter"
                ]
            }
    assert any("S23 money-to-hours conversion" in f for f in _failures(nested))

    # A legitimate prohibition sentence must still pass.
    banning = copy.deepcopy(spec)
    banning["rules"]["establishment"]["note"] = (
        "it must never be inferred from wage_bill_open"
    )
    assert _failures(banning) == []


def test_establishment_rule_is_the_canonical_text(spec: dict[str, Any]) -> None:
    """S23: inert or reordered multipliers are rejected, not substring-matched."""
    canonical = (
        "E_i_raw = capacity_i * labor_per_activity_i * target_utilization_i; "
        "E_i = E_i_raw * min(1, N_working / sum_j E_j_raw)"
    )
    assert spec["rules"]["establishment"]["target_rule"] == canonical

    bare = copy.deepcopy(spec)
    bare["rules"]["establishment"]["target_rule"] = (
        "E_i = capacity_i * labor_per_activity_i * min(1, N_working / sum_j E_j_raw)"
    )
    assert any("S23 establishment target_rule" in f for f in _failures(bare))

    inert = copy.deepcopy(spec)
    inert["rules"]["establishment"]["target_rule"] = (
        "E_i_raw = capacity_i * labor_per_activity_i; "
        "E_i = E_i_raw * 1.0 * target_utilization_i; "
        "E_i = E_i_raw * min(1, N_working / sum_j E_j_raw)"
    )
    assert any("S23 establishment target_rule" in f for f in _failures(inert))

    reordered = copy.deepcopy(spec)
    reordered["rules"]["establishment"]["target_rule"] = (
        "E_i_raw = capacity_i * labor_per_activity_i; "
        "E_i = E_i_raw * min(1, N_working / sum_j E_j_raw) * target_utilization_i"
    )
    assert any("S23 establishment target_rule" in f for f in _failures(reordered))


def test_unit_contract_key_set_is_closed(spec: dict[str, Any]) -> None:
    """S23: a numeric money->hours factor cannot be smuggled into the unit contract."""
    allowed = {
        "nominal_labor_symbol",
        "nominal_labor_unit",
        "nominal_labor_dimension",
        "hours_per_worker_equivalent_quarter",
        "hours_per_worker_quarter_endowment",
        "hours_per_worker_quarter_formal",
        "hours_per_worker_quarter_plot_cap",
        "hours_per_worker_quarter_second_cap",
        "hours_headroom_for_queue_search_leisure",
        "plot_hours_per_activity",
        "money_per_worker_equivalent_quarter",
        "nominal_labor_share_of_equivalent_persons",
        "labor_capacity_headroom",
        "conversion_rule",
        "why_520",
    }
    assert set(spec["unit_contract"]) == allowed

    for key, value in (
        ("money_to_hour_factor", 86.6666667),
        ("ft_per_hour", 86.6666667),
        ("conversion", {"per_money_unit": 0.0115}),
    ):
        mutated = copy.deepcopy(spec)
        mutated["unit_contract"][key] = value
        assert any("S23 unit_contract has undeclared keys" in f for f in _failures(mutated))


def test_provenance_lists_cannot_park_a_year(spec: dict[str, Any]) -> None:
    """S18: the slack provenance list is scanned like any other text."""
    planted = copy.deepcopy(spec)
    planted["derived_metrics"]["unused_labour_share"]["technical_slack"]["sources"].append(
        "mean absence 1975 = 0.074 (yearbook)"
    )
    assert any("S18 calendar year" in f for f in _failures(planted))


def test_transition_preserves_labour_supply(spec: dict[str, Any]) -> None:
    """I8: hires draw from one shared pool; the round-9 witness cannot overshoot."""
    hire = spec["rules"]["hire"]
    assert "avail(t) = N_working - sum_i H1_i" == hire["supply_pool"]
    assert "sum_i H_i(t) <= N_working" in hire["invariant"]
    i8 = next(i for i in spec["identities"] if i["id"] == "I8")

    n_working = 100.0
    e_prev = [10.0, 90.0]
    h_prev = [10.0, 90.0]
    e_cur = [1.0, 99.0]
    cap = [0.25 * e for e in e_prev]
    release = [min(max(h - e, 0.0), 0.1 * h) for h, e in zip(h_prev, e_cur, strict=True)]
    h1 = [h - r for h, r in zip(h_prev, release, strict=True)]
    raw = [min(max(e - h1_i, 0.0), c) for e, h1_i, c in zip(e_cur, h1, cap, strict=True)]
    avail = n_working - sum(h1)
    scale = min(1.0, avail / sum(raw)) if sum(raw) > avail else 1.0
    h_cur = [h1_i + scale * r for h1_i, r in zip(h1, raw, strict=True)]
    assert release == [1.0, 0.0]
    assert raw == [0.0, 9.0]
    assert scale == 1.0 / 9.0
    assert sum(h_cur) == 100.0
    assert "sum 100" in i8["witness"]
    assert "sum H = 108" in i8["note"]

    unscaled = copy.deepcopy(spec)
    unscaled["rules"]["hire"].pop("supply_scale")
    assert any("S24 hire supply_scale" in f for f in _failures(unscaled))

    unscaled_rule = copy.deepcopy(spec)
    unscaled_rule["rules"]["hire"]["rule"] = (
        "H1_i = H_i(t-1) - H_i_release(t); H_i(t) = H1_i + H_i_hire_raw(t)"
    )
    assert any("S24 hire rule is not the canonical" in f for f in _failures(unscaled_rule))

    inert_scale = copy.deepcopy(spec)
    inert_scale["rules"]["hire"]["supply_scale"] = "scale(t) = 1"
    assert any("S24 hire supply_scale" in f for f in _failures(inert_scale))

    current_quarter = copy.deepcopy(spec)
    current_quarter["timing"]["effort_inputs_timing"]["queue_search_share_i"] = (
        "(h_queue + h_search)/(1040*N_working) at t"
    )
    assert any("S24 effort input queue_search_share_i" in f for f in _failures(current_quarter))


def test_metric_bound_uses_effective_hours(spec: dict[str, Any]) -> None:
    """The establishment-denominator share is unrestricted; only the H_eff share is bounded."""
    hoarding = spec["derived_metrics"]["unused_labour_share"]
    diagnostic = hoarding["establishment_unused_share"]
    bounded = hoarding["underutilization_share"]
    assert diagnostic["range"] == "unrestricted"
    assert bounded["range"] == [0.0, 1.0]
    assert "H_eff" in bounded["definition"]
    assert hoarding["institutional_attribution"]["status"] == "UNIDENTIFIED"

    # The round-9 witness: retained above-establishment workers can drive the
    # establishment-denominator share negative; the bounded share cannot.
    e_cur = [40.0, 40.0]
    hours_supplied = 520.0 * sum(e_cur)
    hours_used = 520.0 * sum([45.0, 45.0])
    assert 1.0 - hours_used / hours_supplied == pytest.approx(-0.125)
    effective_hours = 520.0 * sum([45.0, 45.0])
    assert 1.0 - hours_used / effective_hours == pytest.approx(0.0)
    assert "-0.125" in diagnostic["witness"]

    promoted = copy.deepcopy(spec)
    promoted["derived_metrics"]["unused_labour_share"]["establishment_unused_share"][
        "range"
    ] = [0.0, 1.0]
    assert any("S17 the establishment-denominator" in f for f in _failures(promoted))


def test_six_axis_timing_is_single_valued(spec: dict[str, Any]) -> None:
    """S24: the adapter runs before planning, and effort inputs are lagged."""
    order = spec["timing"]["quarter_boundary_order"]
    assert order[0].lower().startswith("adapter")
    assert "plan_household_time" in order[1]
    assert spec["timing"]["adapter_position"].startswith("before plan_household_time")
    effort = spec["timing"]["effort_inputs_timing"]
    assert effort["initial_values"].startswith("zero at t=0")
    assert "t-1" in effort["queue_search_share_i"]
    assert "t-1" in effort["informal_hours_share_i"]

    reordered = copy.deepcopy(spec)
    reordered["timing"]["quarter_boundary_order"] = list(reversed(order))
    assert any("S24 the adapter must run first" in f for f in _failures(reordered))


def test_bounded_metric_declares_zero_denominator(spec: dict[str, Any]) -> None:
    """A feasible start with H(0)=0 leaves the effective-hours share undefined."""
    bounded = spec["derived_metrics"]["unused_labour_share"]["underutilization_share"]
    assert "> 0" in bounded["domain"]
    assert "UNDEFINED" in bounded["zero_denominator"]
    assert bounded["on_zero"] == "null"

    # I7 permits H(0)=0 while E(0)>0, so the zero case is admissible.
    headcount, effort_hours = 0.0, 0.0
    assert headcount * 520.0 == effort_hours

    mutated = copy.deepcopy(spec)
    mutated["derived_metrics"]["unused_labour_share"]["underutilization_share"][
        "zero_denominator"
    ] = "0"
    assert any("S17 zero effective hours" in f for f in _failures(mutated))


def test_release_notice_is_an_initiation_lag(spec: dict[str, Any]) -> None:
    """A1: recovery is capped; notice is not a completion guarantee."""
    row = next(r for r in spec["test_matrix"] if r["id"] == "A1")
    assert "at most max_release_fraction_per_quarter" in row["assertion"]
    assert "several quarters" in row["assertion"]

    h_prev, e_cur = 100.0, 80.0
    release = min(max(h_prev - e_cur, 0.0), 0.1 * h_prev)
    assert release == 10.0
    assert h_prev - release == 90.0 != e_cur


def test_capacity_is_mutable_after_investment(spec: dict[str, Any]) -> None:
    """The binding-side argument is scoped to initialization, not permanent."""
    capacity = next(d for d in spec["state_declarations"] if d["symbol"] == "capacity_i")
    assert capacity["mutable_today"] is True
    assert "investment" in capacity["producer_today"]
    i4 = next(i for i in spec["identities"] if i["id"] == "I4")
    assert "re-evaluated" in i4["binding_side"]


# ---------------------------------------------------------------------------
# H5D implementation behaviour (adapter + opt-in kernel binding)
# ---------------------------------------------------------------------------


def _load_runner():
    module_spec = importlib.util.spec_from_file_location("h5d_labor_runner", RUNNER_PATH)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


labor_runner = _load_runner()


@pytest.fixture(scope="module")
def recipe() -> labor.LaborRecipe:
    raw = SPEC_PATH.read_bytes()
    return labor.LaborRecipe.from_spec(
        json.loads(raw), spec_sha256=hashlib.sha256(raw).hexdigest()
    )


@pytest.fixture(scope="module")
def c0():
    contract = load_research_contract(REPO_ROOT)
    spec = load_scenario(REPO_ROOT, "historical_f2_replay")
    registry = DataRegistry.load(REPO_ROOT, allowed_commodities=spec.commodities)
    forcing = load_material_forcing(spec, registry)
    rng = RngRegistry(spec.seed)
    initial = build_material_initial_conditions(spec, rng)
    network = build_material_network(spec, contract, initial)
    state = initialize_material(spec, initial, network)
    return SimpleNamespace(
        contract=contract,
        spec=spec,
        registry=registry,
        forcing=forcing,
        network=network,
        state=state,
    )


def _tick(
    c0, recipe, *, sidecar=None, initial_headcount=None, side_second_off=False, state=None
):
    state = copy.deepcopy(c0.state if state is None else state)
    opening = capture_material_stocks(state)
    plan = labor.prepare_labor_tick(
        state, recipe, sidecar, initial_headcount=initial_headcount
    )
    if side_second_off:
        state.household_second_participating = np.zeros_like(
            state.household_second_participating
        )
    flows = tick_material(
        state, c0.forcing, c0.spec.material_parameters, c0.network, labor_plan=plan
    )
    summary = accounting_module.check_material_invariants(
        opening,
        state,
        flows,
        c0.spec.material_parameters,
        c0.network,
        labor_plan=plan,
    )
    next_sidecar, diagnostics = labor.close_labor_tick(state, flows, plan)
    closing_state = copy.deepcopy(state)
    state.completed_ticks += 1
    return SimpleNamespace(
        state=state,
        closing_state=closing_state,
        opening=opening,
        plan=plan,
        flows=flows,
        summary=summary,
        sidecar=next_sidecar,
        diagnostics=diagnostics,
    )


def test_establishment_bridge_and_supply_clip(c0, recipe) -> None:
    """The capacity->person bridge uses lpa and clips pro rata to N_working."""
    state = copy.deepcopy(c0.state)
    plan = labor.prepare_labor_tick(state, recipe, None)
    capacity = np.asarray(state.organization_capacity, dtype=np.float64)
    lpa = np.asarray(state.organization_labor_per_activity, dtype=np.float64)
    productive = capacity > 0.0
    assert plan.establishment_raw[productive] == pytest.approx(
        capacity[productive] * lpa[productive] * recipe.target_utilization
    )
    assert float(plan.establishment_raw.sum()) == pytest.approx(11475.0)
    assert float(plan.establishment.sum()) == pytest.approx(11330.0)
    assert float(plan.headcount.sum()) == pytest.approx(11330.0)
    assert float(plan.effective_hours.sum()) == pytest.approx(5891600.0)
    assert np.all(plan.effort == 1.0)
    # The clip cannot be replaced by dropping lpa or utilization.
    without_lpa = capacity[productive].sum() * recipe.target_utilization
    without_utilization = (capacity[productive] * lpa[productive]).sum()
    assert without_lpa != pytest.approx(11475.0)
    assert without_utilization != pytest.approx(11475.0)


def test_headcount_transition_witness_and_shared_pool() -> None:
    """I7/I8: release first, then one order-free hire allocation."""
    headcount, release, raw, hire, scale = labor.transition_headcount(
        np.array([10.0, 90.0]),
        np.array([10.0, 90.0]),
        np.array([1.0, 99.0]),
        100.0,
        hire_capacity_share=0.25,
        max_release_fraction=0.1,
    )
    assert release == pytest.approx([1.0, 0.0])
    assert raw == pytest.approx([0.0, 9.0])
    assert scale == pytest.approx(1.0 / 9.0)
    assert headcount == pytest.approx([9.0, 91.0])
    assert float(headcount.sum()) == pytest.approx(100.0)

    swapped = labor.transition_headcount(
        np.array([90.0, 10.0]),
        np.array([90.0, 10.0]),
        np.array([99.0, 1.0]),
        100.0,
        hire_capacity_share=0.25,
        max_release_fraction=0.1,
    )
    assert swapped[0] == pytest.approx([91.0, 9.0])

    # Release cap applies per quarter and never closes the gap at once.
    capped, release_capped, _, _, _ = labor.transition_headcount(
        np.array([100.0]),
        np.array([100.0]),
        np.array([80.0]),
        100.0,
        hire_capacity_share=0.25,
        max_release_fraction=0.1,
    )
    assert release_capped == pytest.approx([10.0])
    assert capped == pytest.approx([90.0])

    with pytest.raises(ConfigError):
        labor.transition_headcount(
            np.array([200.0]),
            np.array([200.0]),
            np.array([200.0]),
            100.0,
            hire_capacity_share=0.25,
            max_release_fraction=0.1,
        )


def test_absence_effort_and_lag_timing(c0, recipe) -> None:
    """I2 keeps absence and effort separate; t=0 uses zero lagged signals."""
    state = copy.deepcopy(c0.state)
    plan0 = labor.prepare_labor_tick(state, recipe, None)
    org_count = int(plan0.organization_ids.shape[0])
    region_count = int(plan0.region_ids.shape[0])
    previous = labor.LaborSidecar(
        schema_version=labor.SIDECAR_SCHEMA_VERSION,
        completed_ticks=1,
        signal_tick=0,
        organization_ids=plan0.organization_ids,
        region_ids=plan0.region_ids,
        establishment=plan0.establishment,
        headcount=plan0.headcount,
        absence_rate=np.zeros(org_count),
        effort=plan0.effort,
        effective_hours=plan0.effective_hours,
        lag_grievance=np.ones(region_count),
        lag_informal_share=np.full(region_count, 0.25),
        lag_queue_search_share=np.full(region_count, 0.5),
        spec_sha256=recipe.spec_sha256,
        rules_sha256=recipe.rules_sha256,
    )
    state.completed_ticks = 1
    plan1 = labor.prepare_labor_tick(
        state,
        recipe,
        previous,
        absence_adjustment=np.full(org_count, 0.1),
    )
    assert np.allclose(plan1.effort, 0.425)  # 1 - .4 - .3*.25 - .2*.5
    assert np.allclose(plan1.absence_rate, 0.1)
    assert plan1.effective_hours == pytest.approx(
        plan1.headcount * 520.0 * 0.9 * 0.425
    )

    state_signal = copy.deepcopy(c0.state)
    state_signal.household_grievance[:] = 1.0
    plan_signal = labor.prepare_labor_tick(state_signal, recipe, None)
    assert np.all(plan_signal.effort == 1.0)


def test_real_tick_binds_effective_hours_and_rejects_forgery(c0, recipe) -> None:
    result = _tick(c0, recipe)
    hours_used = np.asarray(result.diagnostics.organization_hours_used)
    effective = np.asarray(result.plan.effective_hours)
    assert np.all(hours_used <= effective + 1e-6)
    assert result.diagnostics.establishment_unused_share == pytest.approx(
        0.07593862448231381
    )
    assert result.diagnostics.underutilization_share == pytest.approx(
        0.07593862448231381
    )
    assert result.summary.max_material_abs_residual < 1e-6

    forged = copy.deepcopy(result.flows)
    forged.organization_realized = np.asarray(forged.organization_realized) * 2.0
    with pytest.raises(accounting_module.AccountingError):
        labor.close_labor_tick(result.closing_state, forged, result.plan)


def test_zero_headcount_quarter_and_capped_hiring(c0, recipe) -> None:
    state = copy.deepcopy(c0.state)
    zeros = np.zeros(int(state.organization_id.shape[0]), dtype=np.float64)
    result = _tick(c0, recipe, initial_headcount=zeros)
    assert result.diagnostics.hours_used == 0.0
    assert result.diagnostics.underutilization_share is None
    assert result.diagnostics.establishment_unused_share == pytest.approx(1.0)
    assert float(result.flows.organization_target.sum()) == 0.0
    assert float(result.flows.organization_realized.sum()) == 0.0

    next_plan = labor.prepare_labor_tick(result.state, recipe, result.sidecar)
    establishment_total = float(next_plan.establishment.sum())
    assert 0.0 < float(next_plan.headcount.sum())
    assert float(next_plan.headcount.sum()) <= 0.25 * establishment_total + 1e-9


def test_headcount_may_exceed_establishment_bounds(recipe) -> None:
    """Retained workers can push the establishment share negative; H is not clipped."""
    headcount, release, _, _, _ = labor.transition_headcount(
        np.array([50.0, 50.0]),
        np.array([50.0, 50.0]),
        np.array([40.0, 40.0]),
        100.0,
        hire_capacity_share=0.25,
        max_release_fraction=0.1,
    )
    assert headcount == pytest.approx([45.0, 45.0])
    assert np.all(headcount > np.array([40.0, 40.0]))
    hours_used = 90.0 * recipe.hours_per_we
    establishment_hours = 80.0 * recipe.hours_per_we
    effective_hours = float(headcount.sum()) * recipe.hours_per_we
    assert 1.0 - hours_used / establishment_hours == pytest.approx(-0.125)
    assert 1.0 - hours_used / effective_hours == pytest.approx(0.0)


def test_totals_coverage_and_gap_split(c0, recipe) -> None:
    result = _tick(c0, recipe)
    diagnostics = result.diagnostics
    state = result.state
    nominal = np.asarray(state.organization_labor_available, dtype=np.float64)
    productive = np.asarray(result.plan.capacity_open) > 0.0
    assert diagnostics.n_working == pytest.approx(11330.0)
    assert diagnostics.n_working_weighted == pytest.approx(11250.0)
    assert diagnostics.weight_gap_persons == pytest.approx(-80.0)
    assert float(nominal[~productive].sum()) == pytest.approx(1700.0)
    assert diagnostics.u_labor == pytest.approx(0.0)
    assert diagnostics.g_labor == pytest.approx(5670.0)
    assert diagnostics.n_gap == pytest.approx(5670.0)
    assert diagnostics.distribution_uncovered_we == pytest.approx(1700.0)
    assert diagnostics.productive_nominal_effective_gap_we == pytest.approx(3970.0)
    assert (
        diagnostics.distribution_uncovered_we
        + diagnostics.productive_nominal_effective_gap_we
    ) == pytest.approx(diagnostics.n_gap)
    # Lower effort raises N_gap; U is unaffected (the gaps are WE quantities).
    lower_effective = float(result.plan.effective_hours.sum()) * 0.9
    lower_gap = float(nominal.sum()) - lower_effective / recipe.hours_per_we
    assert lower_gap > diagnostics.n_gap
    assert diagnostics.u_labor == pytest.approx(
        diagnostics.n_working - float(result.plan.headcount.sum())
    )


def test_default_off_is_byte_identical(c0) -> None:
    state_a = copy.deepcopy(c0.state)
    state_b = copy.deepcopy(c0.state)
    flows_a = tick_material(state_a, c0.forcing, c0.spec.material_parameters, c0.network)
    flows_b = tick_material(
        state_b, c0.forcing, c0.spec.material_parameters, c0.network, labor_plan=None
    )
    assert canonical_material_bytes(state_a, flows_a) == canonical_material_bytes(
        state_b, flows_b
    )
    assert np.all(state_a.organization_effort_factor == 1.0)


def test_invalid_plan_is_rejected_before_mutation(c0, recipe) -> None:
    state = copy.deepcopy(c0.state)
    plan = labor.prepare_labor_tick(state, recipe, None)
    before = canonical_material_bytes(state)
    wrong_tick = replace(plan, tick=1)
    with pytest.raises(ConfigError):
        tick_material(
            state,
            c0.forcing,
            c0.spec.material_parameters,
            c0.network,
            labor_plan=wrong_tick,
        )
    assert canonical_material_bytes(state) == before

    wrong_axis = replace(plan, organization_ids=plan.organization_ids + 1000)
    with pytest.raises(ConfigError):
        tick_material(
            state,
            c0.forcing,
            c0.spec.material_parameters,
            c0.network,
            labor_plan=wrong_axis,
        )
    assert canonical_material_bytes(state) == before


def test_negative_control_semantics(c0, recipe) -> None:
    """N1 shares do not read wages; N2 rules move both shares; N3 does not double count."""
    reference = _tick(c0, recipe)
    used = reference.diagnostics.hours_used
    establishment_hours = reference.diagnostics.hours_supplied_establishment
    effective_hours = reference.diagnostics.hours_supplied_effective
    shares = (1.0 - used / establishment_hours, 1.0 - used / effective_hours)
    assert shares == pytest.approx((0.07593862448231381, 0.07593862448231381))

    # N1 through the real closing function: adding a wage bill to arrears cannot
    # move a measurement that never reads monetary fields.
    wage_clone = copy.deepcopy(reference.closing_state)
    wage_bill = recipe.hours_per_we * float(
        np.asarray(wage_clone.organization_labor_available).sum()
    )
    wage_clone.organization_wage_arrears = (
        np.asarray(wage_clone.organization_wage_arrears, dtype=np.float64) + wage_bill
    )
    _, wage_diag = labor.close_labor_tick(wage_clone, reference.flows, reference.plan)
    assert labor.diagnostics_payload(wage_diag) == labor.diagnostics_payload(reference.diagnostics)

    # N2 through the real transition function: the same 80 WE of work.
    def shares_for(establishment_current: float):
        headcount, _, _, _, _ = labor.transition_headcount(
            np.array([100.0]),
            np.array([100.0]),
            np.array([establishment_current]),
            100.0,
            hire_capacity_share=recipe.hire_capacity_share,
            max_release_fraction=recipe.max_release_fraction,
        )
        hours_used = 80.0 * recipe.hours_per_we
        return (
            1.0 - hours_used / (recipe.hours_per_we * establishment_current),
            1.0 - hours_used / (recipe.hours_per_we * float(headcount.sum())),
        )

    ref_shares = shares_for(80.0)
    treat_shares = shares_for(100.0)
    assert ref_shares[0] != treat_shares[0]
    assert ref_shares[1] != treat_shares[1]

    # N3: removing second-economy participation changes side hours and the six-axis
    # split, never the organization's effective hours.
    side_arm = _tick(c0, recipe, side_second_off=True)
    assert np.array_equal(
        np.asarray(reference.plan.effective_hours),
        np.asarray(side_arm.plan.effective_hours),
    )
    assert np.array_equal(
        np.asarray(reference.plan.headcount), np.asarray(side_arm.plan.headcount)
    )
    for result in (reference, side_arm):
        working = float(np.asarray(result.state.household_working_adults).sum())
        six_axis = (
            recipe.hours_per_we * working
            + float(np.asarray(result.state.household_reserved_plot_hours).sum())
            + float(np.asarray(result.state.household_reserved_second_hours).sum())
            + float(np.asarray(result.flows.household_queue_hours).sum())
            + float(np.asarray(result.flows.household_search_hours).sum())
            + float(np.asarray(result.flows.household_leisure_hours).sum())
        )
        assert six_axis == pytest.approx(recipe.endowment_hours * working)
    reference_side = float(
        np.asarray(reference.state.household_reserved_plot_hours).sum()
        + np.asarray(reference.state.household_reserved_second_hours).sum()
    )
    arm_side = float(
        np.asarray(side_arm.state.household_reserved_plot_hours).sum()
        + np.asarray(side_arm.state.household_reserved_second_hours).sum()
    )
    assert reference_side > 0.0 and arm_side > 0.0
    assert reference_side > arm_side


def test_bundle_resume_and_tamper_rejection(tmp_path, recipe) -> None:
    contract = load_research_contract(REPO_ROOT)
    spec = load_scenario(REPO_ROOT, "intermediate8")
    prefix = tmp_path / "prefix"
    continuous = tmp_path / "continuous"
    straight = tmp_path / "straight"
    labor_runner._run_enabled(
        spec, contract, prefix, until="1957Q2", checkpoint_every=2
    )
    labor_runner._run_enabled(
        spec,
        contract,
        continuous,
        until="1957Q4",
        resume_bundle=prefix / "labor_checkpoints/tick-2",
    )
    labor_runner._run_enabled(spec, contract, straight, until="1957Q4")
    resumed = json.loads((continuous / "labor_summary.json").read_text())
    reference = json.loads((straight / "labor_summary.json").read_text())
    assert resumed["core_digest_chain"] == reference["core_digest_chain"]
    assert resumed["labor_digest_chain"] == reference["labor_digest_chain"]
    assert resumed["last_tick_metrics"] == reference["last_tick_metrics"]
    assert labor_runner._verify_run(continuous)["verdict"] == "PASS"

    # The stage-balance identity is still an authoritative gate: planting a
    # residual (and rehashing the payload around it) must fail the loader.
    import polars as pl

    residual_bundle = tmp_path / "planted-residual"
    shutil.copytree(prefix / "labor_checkpoints/tick-2", residual_bundle)
    stage_path = residual_bundle / "material" / "stage_balances.parquet"
    frame = pl.read_parquet(stage_path).with_row_index("_row")
    frame = frame.with_columns(
        pl.when(pl.col("_row") == 0)
        .then(pl.col("residual") + 1.0)
        .otherwise(pl.col("residual"))
        .alias("residual")
    ).drop("_row")
    frame.write_parquet(stage_path)
    metadata_path = residual_bundle / "material" / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["payload_sha256"]["stage_balances.parquet"] = sha256_file(stage_path)
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    bundle_path = residual_bundle / "bundle.json"
    bundle = json.loads(bundle_path.read_text())
    bundle["material_metadata_sha256"] = sha256_file(metadata_path)
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
    network = build_material_network(
        spec, contract, build_material_initial_conditions(spec, RngRegistry(spec.seed))
    )
    with pytest.raises(ResearchGateError):
        labor_runner.load_labor_bundle(
            residual_bundle,
            spec,
            contract,
            network,
            recipe,
            implementation_spec_sha256=labor_runner._implementation_spec_sha(),
        )

    # A tampered lag fails the bundle SHA binding.
    tampered = tmp_path / "tampered"
    shutil.copytree(continuous / "labor_checkpoints/tick-4", tampered)
    payload = json.loads((tampered / "labor.json").read_text())
    payload["lag_grievance"][0] = float(payload["lag_grievance"][0]) + 0.01
    (tampered / "labor.json").write_text(json.dumps(payload), encoding="utf-8")
    rng = RngRegistry(spec.seed)
    initial = build_material_initial_conditions(spec, rng)
    network = build_material_network(spec, contract, initial)
    with pytest.raises(ResearchGateError):
        labor_runner.load_labor_bundle(
            tampered,
            spec,
            contract,
            network,
            recipe,
            implementation_spec_sha256=labor_runner._implementation_spec_sha(),
        )

    # A coherent rehash that only corrupts the state effort carrier is caught by
    # the sidecar identity check.
    effort_tamper = tmp_path / "effort-tamper"
    shutil.copytree(continuous / "labor_checkpoints/tick-4", effort_tamper)
    state_path = effort_tamper / "material" / "state.npz"
    arrays = dict(np.load(state_path))
    arrays["organization_effort_factor"] = np.full(
        arrays["organization_effort_factor"].shape, 0.5
    )
    np.savez(state_path, **arrays)
    metadata_path = effort_tamper / "material" / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["payload_sha256"]["state.npz"] = sha256_file(state_path)
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    bundle_path = effort_tamper / "bundle.json"
    bundle = json.loads(bundle_path.read_text())
    bundle["material_metadata_sha256"] = sha256_file(metadata_path)
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
    with pytest.raises(ResearchGateError):
        labor_runner.load_labor_bundle(
            effort_tamper,
            spec,
            contract,
            network,
            recipe,
            implementation_spec_sha256=labor_runner._implementation_spec_sha(),
        )

    # Missing sidecar, a changed rules identity and a foreign scenario are all
    # refused before any state is restored.
    missing = tmp_path / "missing"
    shutil.copytree(continuous / "labor_checkpoints/tick-4", missing)
    (missing / "labor.json").unlink()
    with pytest.raises(ResearchGateError):
        labor_runner.load_labor_bundle(
            missing,
            spec,
            contract,
            network,
            recipe,
            implementation_spec_sha256=labor_runner._implementation_spec_sha(),
        )

    rules_tamper = tmp_path / "rules-tamper"
    shutil.copytree(continuous / "labor_checkpoints/tick-4", rules_tamper)
    rules_bundle = json.loads((rules_tamper / "bundle.json").read_text())
    rules_bundle["rules_sha256"] = "0" * 64
    (rules_tamper / "bundle.json").write_text(json.dumps(rules_bundle))
    with pytest.raises(ResearchGateError):
        labor_runner.load_labor_bundle(
            rules_tamper,
            spec,
            contract,
            network,
            recipe,
            implementation_spec_sha256=labor_runner._implementation_spec_sha(),
        )

    other_spec = load_scenario(REPO_ROOT, "historical_f2_replay")
    other_rng = RngRegistry(other_spec.seed)
    other_initial = build_material_initial_conditions(other_spec, other_rng)
    other_network = build_material_network(other_spec, contract, other_initial)
    with pytest.raises(ResearchGateError):
        labor_runner.load_labor_bundle(
            continuous / "labor_checkpoints/tick-4",
            other_spec,
            contract,
            other_network,
            recipe,
            implementation_spec_sha256=labor_runner._implementation_spec_sha(),
        )

    # A value edit without updating the manifest digest fails verification.
    tampered_run = tmp_path / "verify-tamper"
    shutil.copytree(continuous, tampered_run)
    lines = (tampered_run / "labor_ticks.jsonl").read_text().splitlines()
    first = json.loads(lines[0])
    first["diagnostics"]["hours_used"] = float(first["diagnostics"]["hours_used"]) + 1.0
    lines[0] = json.dumps(first, sort_keys=True)
    (tampered_run / "labor_ticks.jsonl").write_text("\n".join(lines) + "\n")
    assert labor_runner._verify_run(tampered_run)["verdict"] == "FAILED"


def test_live_capacity_after_real_investment_install(c0, recipe) -> None:
    """Next-quarter establishment reads the capacity installed by the real tick."""
    first = _tick(c0, recipe)
    capacity_before = np.asarray(first.state.organization_capacity, dtype=np.float64).copy()
    second = _tick(c0, recipe, sidecar=first.sidecar, state=first.state)
    completed = float(np.asarray(second.flows.organization_investment_completed).sum())
    capacity_after = np.asarray(second.state.organization_capacity, dtype=np.float64)
    assert completed > 0.0
    assert float((capacity_after - capacity_before).sum()) > 0.0
    # The install quarter froze E at the opening capacity.
    assert np.array_equal(
        np.asarray(second.plan.capacity_open), capacity_before
    )
    next_plan = labor.prepare_labor_tick(second.state, recipe, second.sidecar)
    assert np.array_equal(np.asarray(next_plan.capacity_open), capacity_after)
    productive = capacity_after > 0.0
    lpa = np.asarray(second.state.organization_labor_per_activity, dtype=np.float64)
    assert next_plan.establishment_raw[productive] == pytest.approx(
        capacity_after[productive] * lpa[productive] * recipe.target_utilization
    )


def test_establishment_is_order_free(c0, recipe) -> None:
    state = copy.deepcopy(c0.state)
    capacity = np.asarray(state.organization_capacity, dtype=np.float64)
    lpa = np.asarray(state.organization_labor_per_activity, dtype=np.float64)
    permutation = np.random.default_rng(7).permutation(capacity.shape[0])
    base_raw, base = labor._establishment(
        capacity, lpa, recipe.target_utilization, 11330.0
    )
    perm_raw, perm = labor._establishment(
        capacity[permutation], lpa[permutation], recipe.target_utilization, 11330.0
    )
    assert perm_raw == pytest.approx(base_raw[permutation])
    assert perm == pytest.approx(base[permutation])


def test_zero_establishment_and_headcount(c0, recipe) -> None:
    """E=H=0 is admissible: both shares are undefined, raw counts are reported."""
    state = copy.deepcopy(c0.state)
    state.organization_capacity = np.zeros_like(state.organization_capacity)
    plan = labor.prepare_labor_tick(state, recipe, None)
    assert np.all(np.asarray(plan.establishment) == 0.0)
    assert np.all(np.asarray(plan.headcount) == 0.0)
    opening = capture_material_stocks(state)
    flows = tick_material(
        state, c0.forcing, c0.spec.material_parameters, c0.network, labor_plan=plan
    )
    accounting_module.check_material_invariants(
        opening, state, flows, c0.spec.material_parameters, c0.network, labor_plan=plan
    )
    _, diagnostics = labor.close_labor_tick(state, flows, plan)
    assert diagnostics.hours_used == 0.0
    assert diagnostics.establishment_unused_share is None
    assert diagnostics.underutilization_share is None
    assert diagnostics.hours_supplied_establishment == 0.0
    assert diagnostics.hours_supplied_effective == 0.0


def test_forged_plan_fields_are_rejected(c0, recipe) -> None:
    state = copy.deepcopy(c0.state)
    plan = labor.prepare_labor_tick(state, recipe, None)
    n_working = float(np.asarray(state.household_working_adults).sum())
    org_count = int(np.asarray(state.organization_id).shape[0])
    with pytest.raises(ConfigError):
        labor.validate_labor_plan(
            state, replace(plan, headcount=np.full(org_count, n_working))
        )
    with pytest.raises(ConfigError):
        labor.validate_labor_plan(state, replace(plan, hire_scale=0.5))
    with pytest.raises(ConfigError):
        labor.validate_labor_plan(
            state,
            replace(plan, effective_hours=np.asarray(plan.effective_hours) * 0.5),
        )
    # A forged plan is rejected by the kernel before any mutation as well.
    before = canonical_material_bytes(state)
    with pytest.raises(ConfigError):
        tick_material(
            state,
            c0.forcing,
            c0.spec.material_parameters,
            c0.network,
            labor_plan=replace(plan, establishment=np.asarray(plan.establishment) * 0.5),
        )
    assert canonical_material_bytes(state) == before


def test_c0_bundle_resume_matches_continuous_run(tmp_path, recipe) -> None:
    """The corrected plot outflow must let an F2 bundle resume bit-identically."""
    contract = load_research_contract(REPO_ROOT)
    spec = load_scenario(REPO_ROOT, "historical_f2_replay")
    prefix = tmp_path / "c0-prefix"
    continuous = tmp_path / "c0-continuous"
    straight = tmp_path / "c0-straight"
    labor_runner._run_enabled(
        spec, contract, prefix, until="1957Q2", checkpoint_every=2
    )
    labor_runner._run_enabled(
        spec,
        contract,
        continuous,
        until="1957Q4",
        resume_bundle=prefix / "labor_checkpoints/tick-2",
    )
    labor_runner._run_enabled(spec, contract, straight, until="1957Q4")
    resumed = json.loads((continuous / "labor_summary.json").read_text())
    reference = json.loads((straight / "labor_summary.json").read_text())
    assert resumed["core_digest_chain"] == reference["core_digest_chain"]
    assert resumed["labor_digest_chain"] == reference["labor_digest_chain"]
    assert resumed["last_tick_metrics"] == reference["last_tick_metrics"]
    assert labor_runner._verify_run(continuous)["verdict"] == "PASS"

    # The stage-balance identity is still an authoritative gate: planting a
    # residual (and rehashing the payload around it) must fail the loader.
    import polars as pl

    residual_bundle = tmp_path / "planted-residual"
    shutil.copytree(prefix / "labor_checkpoints/tick-2", residual_bundle)
    stage_path = residual_bundle / "material" / "stage_balances.parquet"
    frame = pl.read_parquet(stage_path).with_row_index("_row")
    frame = frame.with_columns(
        pl.when(pl.col("_row") == 0)
        .then(pl.col("residual") + 1.0)
        .otherwise(pl.col("residual"))
        .alias("residual")
    ).drop("_row")
    frame.write_parquet(stage_path)
    metadata_path = residual_bundle / "material" / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["payload_sha256"]["stage_balances.parquet"] = sha256_file(stage_path)
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    bundle_path = residual_bundle / "bundle.json"
    bundle = json.loads(bundle_path.read_text())
    bundle["material_metadata_sha256"] = sha256_file(metadata_path)
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
    network = build_material_network(
        spec, contract, build_material_initial_conditions(spec, RngRegistry(spec.seed))
    )
    with pytest.raises(ResearchGateError):
        labor_runner.load_labor_bundle(
            residual_bundle,
            spec,
            contract,
            network,
            recipe,
            implementation_spec_sha256=labor_runner._implementation_spec_sha(),
        )
