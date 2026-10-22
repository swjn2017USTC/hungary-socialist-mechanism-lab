"""Validator for the HIST_VNEXT H5D labour institution/unit spec.

Pure and read-only: it never mutates the spec, the repository or engine state, and
it does not import the engine. It is the executable gate behind the spec's
"independent PASS": claims about the live contract and about the code the spec
names are re-derived here from the real files. The measured C0 block is NOT
re-derived by this gate; see evidence_scope.not_gated.

Run directly for a JSON report::

    .venv/bin/python studies/HIST_VNEXT/M03/labor_spec.py

Import for the pytest contract suite::

    spec, failures = validate_repository(REPO_ROOT)
"""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import Any

SPEC_REL = "studies/HIST_VNEXT/M03/labor_institution_spec_v1.json"

REQUIRED_TOP_KEYS = (
    "schema_version",
    "spec_id",
    "spec_semver",
    "phase_id",
    "mechanism_id",
    "study_id",
    "status",
    "implementation_status",
    "default_off",
    "wired_into_engine",
    "document",
    "authorization",
    "scope",
    "unit_contract",
    "contract_bindings",
    "state_declarations",
    "rules",
    "identities",
    "reconciliation",
    "timing",
    "call_chain",
    "derived_metrics",
    "negative_controls",
    "test_matrix",
    "historical",
    "stop_conditions",
)

TIME_AXES = (
    "h_formal",
    "h_plot",
    "h_second",
    "h_queue",
    "h_search",
    "h_leisure",
)

REQUIRED_RULES = ("establishment", "hire", "release", "absence", "effort")

REQUIRED_SYMBOLS = ("L_WE", "E_i", "H_i", "A_i", "e_i", "H_eff_i")

REQUIRED_STOP_TOKENS = (
    "full migration of legacy state versions",
    "changes any default behaviour",
    "no aggregate labour total constraint",
    "wage or arrears substitutes",
)

REQUIRED_IDENTITIES = (
    "I1a", "I1b", "I2", "I3", "I4", "I5a", "I5b", "I6", "I7", "I8",
)

REQUIRED_BINDINGS = (
    "unit_contract.hours_per_worker_quarter_formal",
    "unit_contract.hours_per_worker_quarter_endowment",
    "unit_contract.hours_per_worker_quarter_plot_cap",
    "unit_contract.hours_per_worker_quarter_second_cap",
    "unit_contract.money_per_worker_equivalent_quarter",
    "unit_contract.plot_hours_per_activity",
    "unit_contract.nominal_labor_share_of_equivalent_persons",
    "unit_contract.labor_capacity_headroom",
    "rules.establishment.target_utilization",
    "rules.effort.effort_grievance_weight",
    "rules.effort.effort_informal_hours_weight",
    "rules.effort.effort_queue_search_weight",
    "rules.effort.effort_floor",
)

REQUIRED_FORBIDDEN = (
    "asserting the gap is zero",
    "scaling organisation labour by a fitted factor",
    "changing _PHYSICAL_LABOR_SHARE",
)

REQUIRED_TIMING_MUST_NOT = (
    "rewrite any of the six household time axes",
    "write back household hours from the production side",
    "update labour inside the production phase",
)

REQUIRED_DECLARATIONS = (
    "L_WE", "E_i", "H_i", "A_i", "e_i", "H_eff_i",
    "capacity_i", "labor_per_activity_i", "activity_realized_i",
)

ALLOWED_UNITS = {
    "worker_equivalent_quarter",
    "person",
    "fraction",
    "hour/quarter",
    "money",
    "activity",
    "person/activity",
}

ALLOWED_RULE_UNITS = {
    "person",
    "person/quarter",
    "fraction",
    "hour/quarter",
}


def load_spec(repo_root: Path) -> dict[str, Any]:
    """Load the spec JSON from the repository root."""
    return json.loads((repo_root / SPEC_REL).read_text(encoding="utf-8"))


def _walk_calibrated(node: Any, trail: str = "") -> list[str]:
    """Return every path that claims calibration or historical admission."""
    hits: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{trail}.{key}" if trail else key
            if key == "calibrated" and value is True:
                hits.append(here)
            if key == "evidence_status" and isinstance(value, str) and "calibrat" in value:
                hits.append(here)
            hits.extend(_walk_calibrated(value, here))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            hits.extend(_walk_calibrated(value, f"{trail}[{index}]"))
    return hits


def _binding_value(repo_root: Path, binding: dict[str, Any]) -> Any:
    """Read the live value a spec field claims to bind to."""
    module = importlib.import_module(binding["module"])
    klass = binding.get("class")
    field = binding["field"]
    if klass:
        model = getattr(module, klass)
        return model.model_fields[field].default
    return getattr(module, field)


def _resolve_spec_field(spec: dict[str, Any], dotted: str) -> Any:
    """Resolve a dotted path; a missing segment raises KeyError for the caller to report."""
    node: Any = spec
    for part in dotted.split("."):
        node = node[part]
    return node


def validate_spec(spec: dict[str, Any], repo_root: Path) -> list[str]:
    """Return every failed invariant. Empty list means the spec passes."""
    failures: list[str] = []

    # S1 — schema and declared-not-implemented status.
    for key in REQUIRED_TOP_KEYS:
        if key not in spec:
            failures.append(f"S1 missing top-level key {key!r}")
    if spec.get("status") != "DECLARED_NOT_IMPLEMENTED":
        failures.append(f"S1 status is {spec.get('status')!r}")
    if spec.get("implementation_status") != "NOT_RUN":
        failures.append("S1 implementation_status must be NOT_RUN")
    if spec.get("default_off") is not True:
        failures.append("S1 default_off must be true")
    if spec.get("wired_into_engine") is not False:
        failures.append("S1 wired_into_engine must be false")

    units = spec.get("unit_contract", {})
    # S2 — parameter algebra of the per-worker time endowment.
    endowment = units.get("hours_per_worker_quarter_endowment")
    formal = units.get("hours_per_worker_quarter_formal")
    plot_cap = units.get("hours_per_worker_quarter_plot_cap")
    second_cap = units.get("hours_per_worker_quarter_second_cap")
    headroom = units.get("hours_headroom_for_queue_search_leisure")
    if None in (endowment, formal, plot_cap, second_cap, headroom):
        failures.append("S2 a time parameter is missing from unit_contract")
    else:
        if formal + plot_cap + second_cap + headroom != endowment:
            failures.append(
                "S2 decomposition fails: "
                f"{formal}+{plot_cap}+{second_cap}+{headroom} != {endowment}"
            )
        if headroom < 0:
            failures.append("S2 headroom must be non-negative")
        if units.get("hours_per_worker_equivalent_quarter") != formal:
            failures.append("S2 a worker-equivalent quarter must equal formal hours per worker")

    # S3 — every declared binding equals the live contract default.
    for binding in spec.get("contract_bindings", []):
        try:
            live = _binding_value(repo_root, binding)
        except (ImportError, AttributeError, KeyError, TypeError) as error:
            # A missing binding field must be reported, never raised.
            failures.append(f"S3 cannot read binding {binding.get('field')!r}: {error}")
            continue
        try:
            declared = _resolve_spec_field(spec, binding["spec_field"])
        except (KeyError, TypeError):
            failures.append(f"S3 bound field missing from the spec: {binding['spec_field']}")
            continue
        if declared != live:
            failures.append(
                f"S3 {binding['spec_field']} declares {declared!r} but contract has {live!r}"
            )

    # S4 — every code anchor still exists in the file it names.
    for entry in spec.get("call_chain", []):
        path = repo_root / entry["file"]
        if not path.is_file():
            failures.append(f"S4 anchor file missing: {entry['file']}")
            continue
        if entry["anchor"] not in path.read_text(encoding="utf-8"):
            failures.append(f"S4 anchor not found in {entry['file']}: {entry['anchor']!r}")
    chain_by_id = {entry["id"]: entry for entry in spec.get("call_chain", [])}
    for identity in spec.get("identities", []):
        anchor = identity.get("anchor")
        if anchor:
            owner = next(
                (e["file"] for e in spec["call_chain"] if e["anchor"] == anchor), None
            )
            if owner is None:
                failures.append(f"S4 identity {identity['id']} anchor is not in call_chain")
            elif anchor not in (repo_root / owner).read_text(encoding="utf-8"):
                failures.append(f"S4 identity {identity['id']} anchor missing in {owner}")
        reference = identity.get("anchor_ref")
        if reference:
            entry = chain_by_id.get(reference)
            if entry is None:
                failures.append(f"S4 identity {identity['id']} references unknown {reference}")
            elif entry["anchor"] not in (repo_root / entry["file"]).read_text(encoding="utf-8"):
                failures.append(f"S4 identity {identity['id']} reference {reference} is stale")

    # S5 — the exclusivity identity carries exactly the six time axes.
    exclusivity = next(
        (i for i in spec.get("identities", []) if i.get("id") == "I1b"), None
    )
    if exclusivity is None:
        failures.append("S5 exclusivity identity I1b missing")
    else:
        if tuple(exclusivity.get("axes", ())) != TIME_AXES:
            failures.append(f"S5 axes are {exclusivity.get('axes')!r}, expected {TIME_AXES}")
        if exclusivity.get("exclusive") is not True or exclusivity.get("exhaustive") is not True:
            failures.append("S5 exclusivity identity must be exclusive and exhaustive")

    # S6 — no historical or calibrated claim anywhere.
    historical = spec.get("historical", {})
    if historical.get("status") != "UNIDENTIFIED":
        failures.append("S6 historical status must be UNIDENTIFIED")
    if historical.get("admitted_series") != []:
        failures.append("S6 admitted_series must be empty")
    calibrated = _walk_calibrated(spec)
    if calibrated:
        failures.append(f"S6 calibrated/historical claims present: {calibrated}")

    # S7 — the hoarding index excludes wage inputs and is not computable today.
    hoarding = spec.get("derived_metrics", {}).get("unused_labour_share", {})
    excluded = " ".join(hoarding.get("excluded_inputs", []))
    for token in ("organization_wage_arrears", "wage_rate"):
        if token not in excluded:
            failures.append(f"S7 hoarding index must exclude {token}")
    if hoarding.get("computable") is not False:
        failures.append("S7 hoarding index must be computable=false before the adapter exists")
    if "wage" in hoarding.get("hours_supplied", "") or "wage" in hoarding.get("hours_used", ""):
        failures.append("S7 wage terms must not appear in hours_supplied/hours_used")

    # S8 — the two labour totals are declared unreconciled with an explicit slack.
    reconciliation = spec.get("reconciliation", {})
    if reconciliation.get("status") != "UNRECONCILED_DECLARED":
        failures.append("S8 reconciliation status must be UNRECONCILED_DECLARED")
    if reconciliation.get("same_quantity") is not False:
        failures.append("S8 same_quantity must be false")
    if not reconciliation.get("organization_side") or not reconciliation.get("household_side"):
        failures.append("S8 both labour sides must be written out")
    if not reconciliation.get("forbidden"):
        failures.append("S8 forbidden shortcuts must be listed")
    if reconciliation.get("unallocated_labor", {}).get("computable_today") is not False:
        failures.append("S8 unallocated_labor must be declared non-computable today")

    # S9 — the mandated STOP conditions are present.
    stops = " ".join(spec.get("stop_conditions", []))
    for token in REQUIRED_STOP_TOKENS:
        if token not in stops:
            failures.append(f"S9 STOP condition missing: {token!r}")

    # S10 — employment, headcount, absence, effective hours and release are separate.
    for key in REQUIRED_RULES:
        if key not in spec.get("rules", {}):
            failures.append(f"S10 rule missing: {key}")
    for rule in spec.get("rules", {}).values():
        if rule.get("unit") not in ALLOWED_RULE_UNITS:
            failures.append(f"S10 rule has undeclared unit {rule.get('unit')!r}")
    symbols = {entry["symbol"] for entry in spec.get("state_declarations", [])}
    for symbol in REQUIRED_SYMBOLS:
        if symbol not in symbols:
            failures.append(f"S10 state declaration missing: {symbol}")
    for entry in spec.get("state_declarations", []):
        if entry.get("unit") not in ALLOWED_UNITS:
            failures.append(
                f"S10 {entry['symbol']} has undeclared unit {entry.get('unit')!r}"
            )

    # S11 — every declared identity is present, with its summation qualifier.
    identity_ids = {entry.get("id") for entry in spec.get("identities", [])}
    for identity_id in REQUIRED_IDENTITIES:
        if identity_id not in identity_ids:
            failures.append(f"S11 identity missing: {identity_id}")
    by_id = {entry.get("id"): entry for entry in spec.get("identities", [])}
    for identity_id in ("I5a", "I5b"):
        entry = by_id.get(identity_id, {})
        if "sum_" not in entry.get("statement", ""):
            failures.append(f"S11 {identity_id} must state its summation qualifier")
    if "H_i_release" not in by_id.get("I7", {}).get("statement", ""):
        failures.append("S11 I7 must subtract H_i_release")

    # S12 — the hoarding metric carries its own unit conversion.
    hoarding_used = hoarding.get("hours_used", "")
    if "520" not in hoarding_used:
        failures.append("S12 hours_used must multiply worker-equivalents by 520")
    if "price" in hoarding_used or "price" in hoarding.get("hours_supplied", ""):
        failures.append("S12 price terms must not appear in the hoarding metric")

    # S13 — the institution rules are dimensionally bridged and not output-anchored.
    establishment = spec.get("rules", {}).get("establishment", {})
    if "labor_per_activity" not in establishment.get("target_rule", ""):
        failures.append("S13 establishment must convert capacity units by labor_per_activity")
    for token in ("realized", "output"):
        if token in establishment.get("target_rule", "").lower():
            failures.append(f"S13 establishment must not anchor on {token}")
    if "H_i_release" not in spec.get("rules", {}).get("hire", {}).get("rule", ""):
        failures.append("S13 hire must subtract H_i_release, or release is inert")

    # S14 — declared bindings are complete and the forbidden shortcuts survive.
    binding_fields = {entry.get("spec_field") for entry in spec.get("contract_bindings", [])}
    if len(spec.get("contract_bindings", [])) < len(REQUIRED_BINDINGS):
        failures.append("S14 too few contract bindings")
    for field in REQUIRED_BINDINGS:
        if field not in binding_fields:
            failures.append(f"S14 contract binding missing: {field}")
    forbidden = " ".join(spec.get("reconciliation", {}).get("forbidden", []))
    for token in REQUIRED_FORBIDDEN:
        if token not in forbidden:
            failures.append(f"S14 forbidden shortcut missing: {token!r}")
    must_not = " ".join(spec.get("timing", {}).get("must_not", []))
    for token in REQUIRED_TIMING_MUST_NOT:
        if token not in must_not:
            failures.append(f"S14 timing.must_not missing: {token!r}")
    if len(spec.get("test_matrix", [])) < 10:
        failures.append("S14 test_matrix must keep at least ten rows")
    for control in spec.get("negative_controls", []):
        if control.get("status") != "NOT_RUN":
            failures.append(f"S14 negative control {control.get('id')} must stay NOT_RUN")
    excluded = " ".join(hoarding.get("excluded_inputs", []))
    if "any price index" not in excluded:
        failures.append("S14 excluded_inputs must retain the price-index exclusion")

    # S15 — slack quantities are dimensionally named.
    slack = spec.get("reconciliation", {}).get("unallocated_labor", {})
    if slack.get("unit") != "person":
        failures.append("S15 unallocated_labor must be a person count")
    gap = spec.get("reconciliation", {}).get("gap_quantity", {})
    if gap.get("unit") != "worker_equivalent_quarter":
        failures.append("S15 gap_quantity must be declared in worker-equivalent-quarter")
    if "L_WE" not in gap.get("definition", ""):
        failures.append("S15 gap_quantity must carry the L_WE side")
    declared = {entry["symbol"] for entry in spec.get("state_declarations", [])}
    for symbol in REQUIRED_DECLARATIONS:
        if symbol not in declared:
            failures.append(f"S15 state declaration missing: {symbol}")

    # S16 — every numeric rule parameter is bound or explicitly declared.
    bound_values: dict[str, Any] = {}
    for binding in spec.get("contract_bindings", []):
        try:
            bound_values[binding["spec_field"]] = _binding_value(repo_root, binding)
        except (ImportError, AttributeError, KeyError, TypeError):
            continue
    declared = {entry["name"]: entry for entry in spec.get("declared_parameters", [])}
    for entry in spec.get("declared_parameters", []):
        if entry.get("calibrated") is not False:
            failures.append(f"S16 declared parameter {entry['name']} must be uncalibrated")
        if entry.get("evidence_status") != "structural_assumption":
            failures.append(
                f"S16 declared parameter {entry['name']} is not a structural assumption"
            )
    for rule_name, rule in spec.get("rules", {}).items():
        for key, value in rule.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            path = f"rules.{rule_name}.{key}"
            if path in bound_values and bound_values[path] == value:
                continue
            registered = declared.get(path)
            if registered is None:
                failures.append(f"S16 rule number {path} is neither bound nor declared")
            elif registered["value"] != value:
                failures.append(f"S16 rule number {path} differs from its declaration")
    rule_text = spec.get("reconciliation", {}).get("required_adapter_rule", "")
    if "unallocated_labor" not in rule_text or "never absorb" not in rule_text:
        failures.append("S16 required_adapter_rule must keep the explicit slack and the ban")

    # S17 — effective hours bind production, and the measured block adds up.
    by_id = {entry.get("id"): entry for entry in spec.get("identities", [])}
    i4 = by_id.get("I4", {})
    if "H_eff_i" not in i4.get("statement", ""):
        failures.append("S17 I4 must bound activity by effective hours")
    if "H_eff" not in hoarding.get("activity_realized_bound", ""):
        failures.append("S17 the realized-activity bound must reference H_eff")
    if "after the adapter" not in hoarding.get("activity_realized_bound", ""):
        failures.append("S17 the realized-activity bound must be declared conditional")
    if hoarding.get("institutional_attribution", {}).get("status") != "UNIDENTIFIED":
        failures.append("S17 institutional attribution must stay UNIDENTIFIED")
    bounded = hoarding.get("underutilization_share", {})
    if bounded.get("range") != [0.0, 1.0]:
        failures.append("S17 the bounded share must declare range [0,1]")
    if "H_eff" not in bounded.get("definition", ""):
        failures.append("S17 the bounded share must use effective hours as its denominator")
    if bounded.get("computable") is not False:
        failures.append("S17 the bounded share must be non-computable before the adapter")
    if "> 0" not in bounded.get("domain", ""):
        failures.append("S17 the bounded share must declare a positive-denominator domain")
    if "UNDEFINED" not in bounded.get("zero_denominator", ""):
        failures.append("S17 zero effective hours must be declared undefined")
    diagnostic = hoarding.get("establishment_unused_share", {})
    if diagnostic.get("range") != "unrestricted":
        failures.append(
            "S17 the establishment-denominator share must declare an unrestricted range"
        )
    measured = hoarding.get("measured_c0_tick0", {})
    required_measured = (
        "n_working", "n_working_weighted", "sum_capacity_labour_we", "sum_e_raw",
        "pro_rata_factor", "net_establishment_factor", "sum_e_after_clip",
        "worker_equivalents_used", "hours_used", "hours_supplied",
        "establishment_unused_share", "capacity_denominator_index",
        "unused_we_vs_establishment",
    )
    missing = [key for key in required_measured if key not in measured]
    if missing:
        failures.append(f"S17 measured block missing {missing}")
    else:
        expected_establishment = min(measured["n_working"], measured["sum_e_raw"])
        checks = (
            ("sum_e_raw", measured["sum_e_raw"],
             measured["sum_capacity_labour_we"]
             * float(spec.get("rules", {}).get("establishment", {}).get(
                 "target_utilization", 0.0)), 1e-6),
            ("pro_rata_factor", measured["pro_rata_factor"],
             min(1.0, measured["n_working"] / measured["sum_e_raw"]), 1e-12),
            ("net_establishment_factor", measured["net_establishment_factor"],
             float(spec.get("rules", {}).get("establishment", {}).get(
                 "target_utilization", 0.0)) * measured["pro_rata_factor"], 1e-12),
            ("sum_e_after_clip", measured["sum_e_after_clip"], expected_establishment, 1e-6),
            ("hours_used", measured["hours_used"],
             520.0 * measured["worker_equivalents_used"], 1e-6),
            ("hours_supplied", measured["hours_supplied"], 520.0 * expected_establishment, 1e-6),
            ("establishment_unused_share", measured["establishment_unused_share"],
             1.0 - measured["hours_used"] / measured["hours_supplied"], 1e-9),
            ("capacity_denominator_index", measured["capacity_denominator_index"],
             1.0 - measured["worker_equivalents_used"] / measured["sum_capacity_labour_we"],
             1e-9),
            ("unused_we_vs_establishment", measured["unused_we_vs_establishment"],
             expected_establishment - measured["worker_equivalents_used"], 1e-6),
            ("weight_convention_gap", measured["n_working"] - measured["n_working_weighted"],
             80.0, 1e-9),
        )
        for label, actual, expected, tolerance in checks:
            if abs(actual - expected) > tolerance:
                failures.append(f"S17 {label} is inconsistent: {actual!r} != {expected!r}")
        if measured["hours_used"] > measured["hours_supplied"]:
            failures.append("S17 hours_used must not exceed hours_supplied")
    slack = hoarding.get("technical_slack", {})
    if slack:
        total = slack.get("utilization_slack_we", 0.0) + slack.get("seasonal_slack_we", 0.0)
        if abs(total - slack.get("total_unused_we", -1.0)) > 1e-6:
            failures.append("S17 technical slack decomposition does not add up")
        if abs(
            slack.get("capacity_labour_we", 0.0) - slack.get("realized_we", 0.0)
            - slack.get("total_unused_we", 0.0)
        ) > 1e-6:
            failures.append("S17 technical slack does not equal capacity labour minus realized")

    # S17b — the reconciliation gap must equal the measured sides.
    gap = spec.get("reconciliation", {}).get("nominal_effective_gap", {})
    if gap.get("unit") != "worker_equivalent_quarter":
        failures.append("S17b nominal_effective_gap must be declared in WE-q")
    if "H_eff" not in gap.get("definition", ""):
        failures.append("S17b nominal_effective_gap must carry the effective-hours side")
    if not missing:
        all_labour = by_id.get("I5b", {}).get("measured_c0_tick0", {}).get("all")
        expected_gap = None
        if isinstance(all_labour, (int, float)):
            expected_gap = all_labour - min(measured["n_working"], measured["sum_e_raw"])
        stated_gap = gap.get("measured_c0_tick0", -1.0)
        if expected_gap is not None and abs(stated_gap - expected_gap) > 1e-6:
            failures.append("S17b nominal_effective_gap value disagrees with the measured block")
        split = gap.get("split", {})
        parts = split.get("distribution_uncovered_we", 0.0) + split.get(
            "productive_nominal_effective_gap_we", 0.0
        )
        if abs(parts - gap.get("measured_c0_tick0", -1.0)) > 1e-6:
            failures.append("S17b nominal_effective_gap split does not sum to the gap")

    # S18 — the aggregate formulas and the separation of absence/effort survive edits.
    i5a = by_id.get("I5a", {})
    i5b = by_id.get("I5b", {})
    if "0.9 * N_equivalent_persons" not in i5a.get("statement", ""):
        failures.append("S18 I5a must keep the 0.9 productive share")
    if "1.0 * N_equivalent_persons" not in i5b.get("statement", ""):
        failures.append("S18 I5b must keep the 1.0 all-organization share")
    if "1.0 * N_equivalent_persons" not in reconciliation.get("organization_side", ""):
        failures.append("S18 organization_side must state the 1.0 all-organization share")
    i2 = by_id.get("I2", {})
    for token in ("(1 - A_i)", "e_i"):
        if token not in i2.get("statement", ""):
            failures.append(f"S18 I2 must keep {token}")
    if "clip" not in spec.get("rules", {}).get("release", {}).get("rule", ""):
        failures.append("S18 release rule must keep its clip")
    if "effort_floor" not in spec.get("rules", {}).get("effort", {}).get("rule", ""):
        failures.append("S18 effort rule must keep effort_floor")
    year_like = re.compile(r"\b(?:19|20)\d{2}\b|\b\d{4}Q[1-4]\b")

    def scan_years(node: Any, trail: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if trail == "authorization" and key == "date":
                    continue

                scan_years(value, f"{trail}.{key}" if trail else key)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                scan_years(value, f"{trail}[{index}]")
        elif isinstance(node, str) and year_like.search(node):
            failures.append(f"S18 calendar year in {trail}")

    scan_years(spec, "")
    if "N_working" not in reconciliation.get("household_side", ""):
        failures.append("S18 household_side must be stated on N_working")
    if "N_equivalent_persons" in reconciliation.get("household_side", ""):
        failures.append("S18 household_side must not be stated on the equivalent-person count")

    # S19 — the coverage boundary is declared, not silently dropped.
    boundary = spec.get("scope", {}).get("coverage_boundary", {})
    if not boundary.get("establishment_covered"):
        failures.append("S19 coverage_boundary must name the covered organizations")
    if len(boundary.get("not_covered", [])) != 2:
        failures.append("S19 coverage_boundary must name the non-covered branches")
    if "1700" not in boundary.get("consequence", ""):
        failures.append("S19 coverage_boundary must state the uncovered 1700 WE-q")
    declared_symbols = {entry["symbol"] for entry in spec.get("state_declarations", [])}
    for symbol in ("N_working", "N_equivalent_persons"):
        if symbol not in declared_symbols:
            failures.append(f"S19 state declaration missing: {symbol}")
    split = spec.get("reconciliation", {}).get("nominal_effective_gap", {}).get("split", {})
    if split.get("distribution_uncovered_we") != 1700.0:
        failures.append("S19 distribution_uncovered_we must be declared as 1700")

    # S23 — money never converts to hours, and the rule of record uses its bound factor.
    canonical_rule = (
        "E_i_raw = capacity_i * labor_per_activity_i * target_utilization_i; "
        "E_i = E_i_raw * min(1, N_working / sum_j E_j_raw)"
    )
    if establishment.get("target_rule") != canonical_rule:
        failures.append("S23 establishment target_rule is not the canonical rule of record")
    if "target_utilization" in hoarding.get("hours_used", ""):
        failures.append("S23 target_utilization must not appear in hours_used")

    i6 = by_id.get("I6", {})
    if i6.get("statement") != "wage_bill_open_i = 6.0 * L_WE_i (money/quarter)":
        failures.append("S23 I6 must keep the exact wage-bill definition")
    if "never" not in i6.get("note", "").lower():
        failures.append("S23 I6 must keep the ban on inferring hours from money")
    for field in ("statement", "note"):
        if "520" in str(i6.get(field, "")):
            failures.append("S23 I6 must not contain an hours conversion")

    # S23 — money never converts into hours; only the WE->hours rule is legal.
    allowed_unit_keys = {
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
    extra_unit_keys = set(units) - allowed_unit_keys
    if extra_unit_keys:
        failures.append(f"S23 unit_contract has undeclared keys: {sorted(extra_unit_keys)}")
    if units.get("conversion_rule") != (
        "L_hours = L_WE * hours_per_worker_equivalent_quarter"
    ):
        failures.append("S23 unit_contract.conversion_rule must be the only hours conversion")

    money_pattern = re.compile(
        r"\b(?:wage|wages|arrears|payroll|money|monetary|price|prices|ft|forint|huf|"
        r"salary|salaries|earnings|income|remuneration|bonus|pension|payment|payments)"
        r"[a-z0-9_]*",
        re.IGNORECASE,
    )
    normative = {"rules", "identities", "state_declarations", "document", "unit_contract"}
    prohibition = ("never", "must not", "must leave", "forbidden", "excluded",
                   "not be", "without", "unchanged", "no money")
    structural_keys = {"spec_field", "field", "file", "module", "path"}

    def is_conversion(text: str) -> bool:
        lowered = text.lower()
        if not money_pattern.search(text):
            return False
        if "520" in lowered:
            return True
        if "hours_per_worker" in lowered:
            return True
        return bool(re.search(r"(?:/|\*)\s*\d", lowered))

    def money_scan(node: Any, trail: str, key: str = "") -> None:
        if isinstance(node, dict):
            is_i6 = node.get("id") == "I6"
            for name, value in node.items():
                child = f"{trail}.{name}" if trail else name
                if is_i6:
                    # I6 may name money; no field of it may convert money to hours.
                    if isinstance(value, str):
                        if is_conversion(value):
                            failures.append(f"S23 money-to-hours conversion at {child}")
                    else:
                        money_scan(value, child, name)
                    continue
                money_scan(value, child, name)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                money_scan(value, f"{trail}[{index}]", key)
        elif isinstance(node, str):
            if key in structural_keys:
                return
            if is_conversion(node):
                failures.append(f"S23 money-to-hours conversion at {trail}")
                return
            section = trail.split(".")[0].split("[")[0]
            if section in normative and money_pattern.search(node):
                lowered = node.lower()
                if not any(marker in lowered for marker in prohibition):
                    failures.append(f"S23 unqualified money term at {trail}")

    money_scan(spec, "")

    # S24 — the transition preserves supply and the timing order is single-valued.
    hire_rule = spec.get("rules", {}).get("hire", {})
    canonical_transition = (
        "H1_i = H_i(t-1) - H_i_release(t); "
        "H_i(t) = H1_i + scale(t) * H_i_hire_raw(t)"
    )
    if hire_rule.get("rule") != canonical_transition:
        failures.append("S24 hire rule is not the canonical scaled transition")
    if hire_rule.get("supply_scale") != (
        "scale(t) = min(1, avail(t) / sum_i H_i_hire_raw(t)) when the raw sum exceeds "
        "avail(t), else 1"
    ):
        failures.append("S24 hire supply_scale is not the canonical allocation")
    if hire_rule.get("supply_pool") != "avail(t) = N_working - sum_i H1_i":
        failures.append("S24 hire supply_pool is not the canonical pool")
    if "sum_i H_i(t) <= N_working" not in hire_rule.get("invariant", ""):
        failures.append("S24 hire rule must state the supply invariant")
    order = spec.get("timing", {}).get("quarter_boundary_order", [])
    if not order or "adapter" not in str(order[0]).lower():
        failures.append("S24 the adapter must run first in the quarter order")
    if len(order) < 2 or "plan_household_time" not in str(order[1]):
        failures.append("S24 plan_household_time must follow the adapter")
    effort_timing = spec.get("timing", {}).get("effort_inputs_timing", {})
    for key in ("grievance_i", "informal_hours_share_i", "queue_search_share_i"):
        if "t-1" not in str(effort_timing.get(key, "")):
            failures.append(f"S24 effort input {key} must be timestamped at t-1")

    # S20 — the metric rename is complete.
    def scan_hoarding(node: Any, trail: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                here = f"{trail}.{key}" if trail else key
                if isinstance(key, str) and "hoarding_index" in key:
                    failures.append(f"S20 stale hoarding_index key at {here}")
                scan_hoarding(value, here)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                scan_hoarding(value, f"{trail}[{index}]")
        elif isinstance(node, str) and "hoarding_index" in node:
            failures.append(f"S20 stale hoarding_index reference at {trail}")

    scan_hoarding(spec, "")

    # S21 — the coverage text is a reference, not a second prose copy.
    coverage = spec.get("rules", {}).get("establishment", {}).get("coverage", "")
    if "scope.coverage_boundary" not in coverage:
        failures.append("S21 establishment.coverage must reference scope.coverage_boundary")

    # S22 — the measured block names its own scope and provenance.
    scope = spec.get("evidence_scope", {})
    for key in ("measured_block", "pro_forma", "not_gated", "calendar_year_scan"):
        if key not in scope:
            failures.append(f"S22 evidence_scope missing {key}")
    if not hoarding.get("measured_c0_tick0", {}).get("derivation", "").strip():
        failures.append("S22 the measured block must carry a non-empty derivation")
    if "no gate" not in scope.get("not_gated", "").lower():
        failures.append("S22 evidence_scope.not_gated must state that no gate re-derives it")
    if "not an observed" not in scope.get("pro_forma", "").lower():
        failures.append("S22 evidence_scope.pro_forma must state the numbers are declared")

    # Scope discipline: the spec must not claim to cover implementation or history.
    covers = " ".join(spec.get("scope", {}).get("covers", []))
    if "implementation" in covers:
        failures.append("scope.covers must not include implementation")

    return failures


def validate_repository(repo_root: Path) -> tuple[dict[str, Any], list[str]]:
    """Load the repository spec and validate it. Returns (spec, failures)."""
    spec = load_spec(repo_root)
    return spec, validate_spec(spec, repo_root)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    spec, failures = validate_repository(repo_root)
    report = {
        "spec": SPEC_REL,
        "spec_id": spec.get("spec_id"),
        "spec_semver": spec.get("spec_semver"),
        "status": spec.get("status"),
        "checks": 24,
        "ok": not failures,
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
