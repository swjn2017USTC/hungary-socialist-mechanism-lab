"""Machine-checkable P06 clearance checklist (plan section 10).

The checklist is declarative: ``config/calibration/p06_clearance.json`` carries the item
list, the scope decision and the waivers, and this module only evaluates them.  A missing
artifact fails loudly (status OPEN) unless the item is explicitly waived with a reason,
a decider and a date — a waiver can never be silent.

Statuses: ``PASS`` (checked and true), ``WAIVED`` (explicitly not required, with reason),
``OPEN`` (checked and false, or not yet run).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class ClearanceItem:
    id: str
    status: str
    description: str
    evidence: str = ""
    waiver: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "description": self.description,
            "evidence": self.evidence,
            "waiver": self.waiver,
        }


@dataclass
class ClearanceReport:
    scope_decision: dict[str, Any]
    items: list[ClearanceItem] = field(default_factory=list)

    @property
    def open_items(self) -> list[ClearanceItem]:
        return [item for item in self.items if item.status == "OPEN"]

    @property
    def cleared(self) -> bool:
        return not self.open_items

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope_decision": self.scope_decision,
            "cleared": self.cleared,
            "counts": {
                status: sum(1 for item in self.items if item.status == status)
                for status in ("PASS", "WAIVED", "OPEN")
            },
            "items": [item.as_dict() for item in self.items],
        }


def _waiver_for(config: dict[str, Any], item_id: str) -> dict[str, Any] | None:
    for waiver in config.get("waivers", []):
        if str(waiver.get("item")) == item_id:
            return waiver
    return None


def _check_local_checks(root: Path, item: dict[str, Any]) -> tuple[bool, str]:
    lint = subprocess.run(
        [".venv/bin/ruff", "check", "src", "tests"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if lint.returncode != 0:
        return False, f"ruff exit {lint.returncode}: {lint.stdout.strip()[:200]}"
    evidence = root / str(item.get("pytest_evidence", ""))
    if not evidence.exists():
        return False, (
            f"pytest evidence missing at {item.get('pytest_evidence')}; regenerate with "
            ".venv/bin/python -m pytest -q -p no:cacheprovider and record passed/failed "
            "in that JSON (run outputs are local by policy)"
        )
    payload = json.loads(evidence.read_text())
    failed = int(payload.get("failed", -1))
    passed = int(payload.get("passed", 0))
    if failed != 0 or passed <= 0:
        return False, f"recorded pytest evidence: {passed} passed, {failed} failed"
    return True, f"ruff clean; pytest evidence {passed} passed, 0 failed"


def _check_digest(root: Path, item: dict[str, Any], *, with_runs: bool) -> tuple[bool, str]:
    if not with_runs:
        return False, "not run (pass --with-runs to reproduce the digest)"
    from hsm_lab.contract.guards import load_research_contract, load_scenario
    from hsm_lab.data.registry import DataRegistry
    from hsm_lab.engine.material import run_material

    scenario = str(item.get("scenario", "historical_f2_replay"))
    spec = load_scenario(root, scenario)
    contract = load_research_contract(root)
    registry = DataRegistry.load(root, allowed_commodities=spec.commodities)
    output = root / "outputs" / f"p06-clearance-digest-{uuid4().hex}"
    run = run_material(spec, output, contract, registry, checkpoint_every=0)
    expected = str(item["expected"])
    digest = str(run.deterministic_replay_digest)
    return digest == expected, f"{scenario} digest {digest[:16]}... (expected {expected[:16]}...)"


def _check_registry_consistency(root: Path) -> tuple[bool, str]:
    from hsm_lab.contract.guards import AVAILABLE_SCENARIOS

    control = json.loads((root / "config" / "calibration" / "p05.json").read_text())
    declared = sorted(set(str(v) for v in (control.get("scenarios") or {}).values()))
    unknown = [name for name in declared if name not in AVAILABLE_SCENARIOS]
    if unknown:
        return False, f"control-file scenario names not registered: {unknown}"
    return True, f"all {len(declared)} control-file scenario names are registered"


def _check_control_structure(root: Path) -> tuple[bool, str]:
    control = json.loads((root / "config" / "calibration" / "p05.json").read_text())
    floors = (control.get("gates") or {}).get("terminal_floor")
    if not floors:
        return False, "gates.terminal_floor is not declared"
    identity = control.get("identification") or {}
    counts: dict[str, int] = {}
    for label in identity.values():
        counts[str(label)] = counts.get(str(label), 0) + 1
    if counts.get("fixed", 0) != 9 or counts.get("unidentified", 0) != 6:
        return False, f"identification counts changed: {counts}"
    if control.get("linkage") != []:
        return False, f"linkage is not empty under the reproduction scope: {control.get('linkage')}"
    return True, (
        f"terminal floors declared; linkage empty; identification {counts}"
    )


def _normalize_whitespace(text: str) -> str:
    """Collapse whitespace so a markdown line wrap cannot break a content check."""
    return " ".join(text.split())


def _check_scope_statement(root: Path, marker: str) -> tuple[bool, str]:
    report = root / "docs" / "phases" / "P05_REPORT.md"
    if not report.exists():
        return False, "P05_REPORT.md missing"
    text = _normalize_whitespace(report.read_text())
    if _normalize_whitespace(marker) not in text:
        return False, f"scope statement marker absent from P05_REPORT.md: {marker!r}"
    return True, "P05_REPORT.md records the reproduction-scope decision"


def _check_reserved_window(root: Path) -> tuple[bool, str]:
    offenders: list[str] = []
    checked = 0
    for manifest in sorted(root.glob("outputs/*/manifest.json")):
        try:
            payload = json.loads(manifest.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        quarter = payload.get("last_completed_quarter")
        if not quarter:
            continue
        checked += 1
        try:
            year = int(str(quarter)[:4])
        except ValueError:
            offenders.append(f"{manifest.parent.name}: unparseable {quarter!r}")
            continue
        if year >= 1986:
            offenders.append(f"{manifest.parent.name} ends {quarter}")
    if offenders:
        return False, "runs reaching the reserved window: " + "; ".join(offenders[:5])
    return True, f"{checked} recorded runs end at or before 1985Q4"


def _check_json_field(root: Path, item: dict[str, Any]) -> tuple[bool, str]:
    path = root / str(item["path"])
    if not path.exists():
        return False, f"missing artifact {item['path']}"
    payload = json.loads(path.read_text())
    actual = payload.get(str(item["field"]))
    expected = item["equals"]
    if actual != expected:
        return False, f"{item['path']}[{item['field']}] = {actual!r}, expected {expected!r}"
    return True, f"{item['path']}[{item['field']}] = {actual!r}"


def _check_files_exist(root: Path, item: dict[str, Any]) -> tuple[bool, str]:
    missing = [str(p) for p in item.get("paths", []) if not (root / str(p)).exists()]
    if missing:
        return False, "missing: " + ", ".join(missing)
    return True, f"{len(item.get('paths', []))} artifacts present"


def _check_p06_arms_summary(root: Path) -> tuple[bool, str]:
    """Require complete, successful W5-W7 fork evidence in the local run summary."""
    path = root / "outputs" / "p06-arms" / "summary.json"
    if not path.exists():
        return False, (
            "outputs/p06-arms/summary.json missing; regenerate the v4 parent and W5-W7 "
            "forks using docs/phases/P06_UNBLOCK_AND_CROSSWALK_PROMPT.md"
        )
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"invalid outputs/p06-arms/summary.json: {exc}"

    required = {
        "1968": {"control", "no-reform", "nem-plus", "nos-hu", "digital-nem"},
        "1973": {
            "control",
            "borrowing-smoothing",
            "consumption-restraint",
            "investment-restraint",
            "price-wage-compensation",
            "hard-budget",
        },
        "political": {
            "control",
            "coalition-weights",
            "soviet-constraint",
            "consumer-import",
            "cultural-openness",
            "second-economy",
        },
    }
    arms = payload.get("arms")
    if not isinstance(arms, list):
        return False, "outputs/p06-arms/summary.json has no arms list"
    index: dict[str, dict[str, dict[str, Any]]] = {family: {} for family in required}
    for arm in arms:
        if not isinstance(arm, dict) or arm.get("family") not in index:
            continue
        arm_id = str(arm.get("arm_id", ""))
        if arm_id in index[arm["family"]]:
            return False, f"duplicate {arm['family']} arm {arm_id!r}"
        index[arm["family"]][arm_id] = arm

    for family, expected_ids in required.items():
        missing = expected_ids - set(index[family])
        if missing:
            return False, f"{family} arms missing: {sorted(missing)}"
        family_digests: set[str] = set()
        for arm_id in sorted(expected_ids):
            arm = index[family][arm_id]
            if arm.get("status") != "completed":
                return False, f"{family}/{arm_id} status is {arm.get('status')!r}"
            if arm.get("completed_ticks") != 116 or arm.get("last_completed_quarter") != "1985Q4":
                return False, f"{family}/{arm_id} did not complete through 1985Q4"
            for key in ("parameter_hash", "intervention_hash", "replay_digest"):
                value = arm.get(key)
                if not isinstance(value, str) or len(value) != 64:
                    return False, f"{family}/{arm_id} lacks a SHA-256 {key}"
            if arm["replay_digest"] in family_digests:
                return False, f"{family} arms have duplicate replay digest at {arm_id}"
            family_digests.add(arm["replay_digest"])
            metrics = arm.get("metrics")
            if not isinstance(metrics, dict) or (
                metrics.get("guardrails", {}).get("accounting_invariants_pass") is not True
            ):
                return False, f"{family}/{arm_id} accounting metrics missing or failed"
            run_manifest_path = root / str(arm.get("output_dir", "")) / "manifest.json"
            if not run_manifest_path.is_file():
                return False, f"{family}/{arm_id} run manifest is missing"
            try:
                run_manifest = json.loads(run_manifest_path.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                return False, f"{family}/{arm_id} run manifest is invalid: {exc}"
            for key in ("completed_ticks", "last_completed_quarter", "parameter_hash"):
                if run_manifest.get(key) != arm.get(key):
                    return False, f"{family}/{arm_id} summary disagrees with run manifest {key}"
            if (
                run_manifest.get("status") != "completed"
                or run_manifest.get("deterministic_replay_digest") != arm.get("replay_digest")
            ):
                return False, f"{family}/{arm_id} is not backed by its completed replay manifest"
    return True, (
        "all 17 required W5-W7 arms completed 116 ticks through 1985Q4 with hashes and metrics"
    )


def _check_p06_reproduction_table(root: Path) -> tuple[bool, str]:
    """Verify the declared crosswalk counts and bounded numeric-table artifact."""
    try:
        from hsm_lab.calibration.reproduction_table import load_reproduction_crosswalk

        crosswalk = load_reproduction_crosswalk(root)
    except (OSError, ValueError, KeyError) as exc:
        return False, f"crosswalk invalid or missing: {exc}"
    counts = {
        status: sum(row.get("status") == status for row in crosswalk["entries"])
        for status in ("mapped", "no_counterpart", "blocked")
    }
    by_grade = {
        grade: sum(row.get("comparison_grade") == grade for row in crosswalk["entries"])
        for grade in (
            "mapped_like_for_like",
            "normalized_index",
            "allocation_assumed",
            "no_counterpart",
            "blocked",
        )
    }
    path = root / "outputs/p06-reproduction-table-widened-final2/reproduction_table.json"
    if not path.exists():
        return False, (
            "outputs/p06-reproduction-table-widened-final2/reproduction_table.json missing; "
            "run hsm calibration reproduction-table --output-dir "
            "outputs/p06-reproduction-table-widened-final2"
        )
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"invalid reproduction table JSON: {exc}"
    if payload.get("crosswalk_counts") != counts:
        return False, (
            f"table crosswalk counts {payload.get('crosswalk_counts')} do not match {counts}"
        )
    if payload.get("by_grade") != by_grade:
        return False, (
            f"table grade counts {payload.get('by_grade')} do not match {by_grade}"
        )
    if (
        payload.get("holdout_values_read") is not False
        or payload.get("reserved_values_read") is not False
    ):
        return False, "table reports a protected-window numeric read"
    mapped = {row["variable_id"] for row in crosswalk["entries"] if row["status"] == "mapped"}
    years = {
        year
        for window in crosswalk["comparison_windows"].values()
        for year in range(int(window["start_year"]), int(window["end_year"]) + 1)
    }
    for row in payload.get("rows", []):
        if row.get("variable_id") not in mapped or int(row.get("year", -1)) not in years:
            return False, "table contains an unmapped variable or out-of-scope year"
    if any(
        row.get("year") == 1960 and row.get("informative") is not False
        for row in payload.get("rows", [])
    ):
        return False, "table treats an index normalization base year as informative"
    return True, (
        f"crosswalk {counts}; {len(payload.get('rows', []))} numeric rows "
        "limited to mapped open windows"
    )


def _check_p06_trade_transmission(root: Path) -> tuple[bool, str]:
    """Check that the C0/C1/C2 transmission evidence is recorded completely."""
    path = root / "outputs/p06-trade-transmission/summary.json"
    if not path.is_file():
        return False, "outputs/p06-trade-transmission/summary.json is missing"
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"invalid trade transmission summary: {exc}"
    if payload.get("schema_version") != 1:
        return False, "trade transmission summary schema_version must be 1"
    runs = payload.get("runs")
    if not isinstance(runs, dict) or not {"C0", "C1", "C2"} <= set(runs):
        return False, "trade transmission summary must record C0, C1 and conditional C2 runs"
    for arm_id in ("C0", "C1", "C2"):
        run = runs[arm_id]
        required = (
            "scenario_id",
            "parameter_hash",
            "seed",
            "deterministic_replay_digest",
            "completed_ticks",
            "last_completed_quarter",
            "by_commodity",
            "invariants",
        )
        missing = [key for key in required if key not in run]
        if missing:
            return False, f"{arm_id} trade summary is missing {missing}"
        if (
            len(str(run["parameter_hash"])) != 64
            or len(str(run["deterministic_replay_digest"])) != 64
            or int(run["completed_ticks"]) != 116
            or str(run["last_completed_quarter"]) != "1985Q4"
        ):
            return False, f"{arm_id} trade summary has incomplete run identity"
        by_commodity = run["by_commodity"]
        if not isinstance(by_commodity, dict) or not by_commodity:
            return False, f"{arm_id} trade summary has no per-commodity channels"
        for commodity, metrics in by_commodity.items():
            for direction in ("imports", "exports"):
                channels = metrics.get(direction)
                if not isinstance(channels, dict) or not {
                    "cmea",
                    "convertible",
                } <= set(channels):
                    return False, f"{arm_id}/{commodity} lacks {direction} channel volumes"
        invariants = run["invariants"]
        if not {
            "max_finance_abs_residual",
            "max_material_abs_residual",
        } <= set(invariants):
            return False, f"{arm_id} trade summary lacks accounting residual evidence"
    scenario = payload.get("scenario_definition")
    if not isinstance(scenario, dict) or not scenario.get("scenario_sha256"):
        return False, "trade transmission summary lacks scenario provenance"
    return True, (
        "C0/C1/C2 identities, 116-tick windows, per-commodity channels "
        "and residual evidence recorded"
    )


def run_clearance(
    root: Path,
    *,
    config_path: Path | None = None,
    with_runs: bool = False,
    scope_marker: str = "reproduction under declared behavioural assumptions",
) -> ClearanceReport:
    """Evaluate every declared clearance item against the repository state."""
    root = Path(root)
    config_file = config_path or root / "config" / "calibration" / "p06_clearance.json"
    config = json.loads(Path(config_file).read_text())
    report = ClearanceReport(scope_decision=dict(config.get("scope_decision") or {}))

    for item in config.get("items", []):
        item_id = str(item["id"])
        kind = str(item["kind"])
        if kind == "local_checks":
            passed, evidence = _check_local_checks(root, item)
        elif kind == "digest_reproduces":
            passed, evidence = _check_digest(root, item, with_runs=with_runs)
        elif kind == "json_field":
            passed, evidence = _check_json_field(root, item)
        elif kind == "unsatisfied":
            # An item that is required by default and can only disappear through an
            # explicit, recorded waiver: without one it is OPEN, never silently absent.
            passed, evidence = False, f"not satisfied: {item.get('note', 'no note')}"
        elif kind == "file_exists":
            passed, evidence = _check_files_exist(root, item)
        elif kind == "internal":
            check = str(item.get("check"))
            if check == "registry_consistency":
                passed, evidence = _check_registry_consistency(root)
            elif check == "control_structure":
                passed, evidence = _check_control_structure(root)
            elif check == "scope_statement":
                passed, evidence = _check_scope_statement(root, scope_marker)
            elif check == "reserved_window":
                passed, evidence = _check_reserved_window(root)
            elif check == "p06_arms_summary":
                passed, evidence = _check_p06_arms_summary(root)
            elif check == "p06_reproduction_table":
                passed, evidence = _check_p06_reproduction_table(root)
            elif check == "p06_trade_transmission":
                passed, evidence = _check_p06_trade_transmission(root)
            else:
                passed, evidence = False, f"unknown internal check {check!r}"
        else:
            passed, evidence = False, f"unknown item kind {kind!r}"

        waiver = _waiver_for(config, item_id)
        if passed:
            status = "PASS"
        elif waiver is not None:
            status = "WAIVED"
        else:
            status = "OPEN"
        report.items.append(
            ClearanceItem(
                id=item_id,
                status=status,
                description=str(item.get("description", "")),
                evidence=evidence,
                waiver=waiver,
            )
        )
    return report


def render_markdown(report: ClearanceReport) -> str:
    """Render the checklist as the committed clearance document."""
    decision = report.scope_decision
    lines = [
        "# P06 clearance checklist",
        "",
        "Generated by `hsm calibration p06-clearance`. Statuses: PASS (checked true), "
        "WAIVED (explicitly not required, with a recorded reason), OPEN (checked false or "
        "not yet run — the command exits non-zero while any OPEN item remains).",
        "",
        f"- Scope decision: `{decision.get('decision', 'undecided')}` "
        f"(decided by {decision.get('decided_by', '?')} on {decision.get('date', '?')})",
        f"- Statement: {decision.get('statement', '')}",
        "",
        "## Items",
        "",
        "| id | status | evidence |",
        "|---|---|---|",
    ]
    for item in report.items:
        lines.append(f"| `{item.id}` | **{item.status}** | {item.evidence} |")
    lines += ["", "## Waivers", ""]
    waiver_rows = [item for item in report.items if item.waiver is not None]
    if waiver_rows:
        lines += ["| id | reason | decided by | date |", "|---|---|---|---|"]
        for item in waiver_rows:
            waiver = item.waiver or {}
            reason = str(waiver.get("reason", "")).replace("|", "/")
            lines.append(
                f"| `{item.id}` | {reason} | {waiver.get('decided_by', '?')} | "
                f"{waiver.get('date', '?')} |"
            )
    else:
        lines.append("None.")
    lines += ["", "## Consequences recorded with the decision", ""]
    for consequence in decision.get("consequences", []):
        lines.append(f"- {consequence}")
    lines += [
        "",
        f"**Cleared:** {'yes' if report.cleared else 'no'} "
        f"({len(report.open_items)} open item(s) not waived).",
        "",
    ]
    if report.open_items:
        lines.append("Open items:")
        for item in report.open_items:
            lines.append(f"- `{item.id}`: {item.evidence}")
        lines.append("")
    return "\n".join(lines)
