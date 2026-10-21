"""H4B Pilot A runner: 1968Q1 branch state and paired permission arms.

The branch is a model-generated 1968Q1 state produced by a deterministic warm-up
of the synthetic ``historical_f2_replay`` scenario.  It is **not** a historical
1968 initial state.  Each arm receives an independent deep copy of that state,
the same forcing, seed 1729 and four 1968 quarters.

The runner composes the already-reviewed execution bridges:

* procurement through ``commit_proposal`` (H2B admission);
* price through ``commit_proposal`` (category + authority gated);
* investment through ``commit_proposal`` (organization-level approval cap);
* the combined arm applies all three controls to one tick in the runner.

No target value, sealed window, private payload, or original source is read.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.contract.material import PURPOSE_CODES, RoutePurpose, get_catalog
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine import accounting
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.material import (
    canonical_material_bytes,
    load_material_forcing,
    tick_material,
)
from hsm_lab.engine.network import build_material_network
from hsm_lab.engine.policy import TickControls, compile_price_override
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import capture_material_stocks, initialize_material
from hsm_lab.institutions.authority import authority_at
from hsm_lab.institutions.decisions import (
    ActorRole,
    InvestmentDecision,
    PriceProposalDecision,
    PriceProposalKind,
    ProcurementChoiceKind,
    ProcurementDecision,
)
from hsm_lab.institutions.execution_adapter import _procurement_delivery, commit_proposal
from hsm_lab.institutions.price_regimes import PriceRegime
from hsm_lab.institutions.proposal_validation import ValidationResult
from hsm_lab.institutions.schemas import (
    AuthorityScope,
    DateInterval,
    InstitutionEvent,
    RegimeCalendar,
)
from hsm_lab.provenance.manifest import canonical_digest

SCHEMA_VERSION = "hist_vnext_h4b_pilot_a_v1"


class PilotTickFailure(RuntimeError):
    """A post-mutation pilot failure; the runner must stop, not fall back."""
_PROCUREMENT_PURPOSE = PURPOSE_CODES[RoutePurpose.PROCUREMENT]
DEFAULT_SPEC = Path("studies/HIST_VNEXT/pilot_A/spec.json")
PRICE_REGIME = Path("config/price_regimes/hist_vnext_h4b_v1.json")


def _day(value: str) -> DateInterval:
    parsed = date.fromisoformat(value)
    return DateInterval(earliest=parsed, latest=parsed, precision="day")


def _event(
    event_id: str,
    *,
    permission: str,
    action: str = "grant",
    organization_ids: tuple[str, ...] = (),
    effective_from: str = "1967-12-01",
    revokes_event_id: str | None = None,
) -> InstitutionEvent:
    return InstitutionEvent(
        event_id=event_id,
        permission=permission,
        scope=AuthorityScope(
            organization_ids=organization_ids,
            sector_ids=("industry",),
            excluded_sector_ids=(),
            geographic_ids=(),
        ),
        action=action,
        revokes_event_id=revokes_event_id,
        proposal_date=_day("1967-09-01"),
        approval_date=_day("1967-10-01"),
        enactment_date=_day("1967-11-01"),
        effective_from=_day(effective_from),
        effective_to=None,
        observed_implementation_at=None,
        source_available_at=_day("1967-09-01"),
        issuer="synthetic pilot calendar",
        legal_force="enactment",
        source_ids=("synthetic:h4b-pilot-a",),
        synthetic_flag=True,
        confidence_reason="declared experiment calendar; not a historical legal record",
        search_tags=("pilot-A",),
    )


def _calendar(*, revoke_procurement_for: str | None = None, no_procurement: bool = False,
              no_investment: bool = False) -> RegimeCalendar:
    events: list[InstitutionEvent] = []
    if not no_procurement:
        events.append(_event("PILOT-GRANT-PROCUREMENT", permission="procurement"))
        if revoke_procurement_for is not None:
            events.append(
                _event(
                    "PILOT-REVOKE-PROCUREMENT",
                    permission="procurement",
                    action="revoke",
                    organization_ids=(revoke_procurement_for,),
                    effective_from="1967-12-15",
                    revokes_event_id="PILOT-GRANT-PROCUREMENT",
                )
            )
    events.append(_event("PILOT-GRANT-PRICE", permission="price_setting"))
    if not no_investment:
        events.append(_event("PILOT-GRANT-INVESTMENT", permission="investment_approval"))
    return RegimeCalendar(events=tuple(events))


def _admit(decision: Any, calendar: RegimeCalendar, permission: str):
    """Pilot admission: explicit authority + payload digest.

    The H2A fixture role registry is keyed to ``ORG-ENT-A/B`` and is not the
    material organization crosswalk.  The pilot therefore performs the
    authority check explicitly and binds the decision payload digest; the
    adapter still enforces the exact payload, tick, and invariant contract.
    """
    result = authority_at(
        calendar,
        organization_id=decision.organization_id,
        sector_id=decision.sector_id,
        geographic_id="national",
        permission=permission,
        decision_at=decision.decision_at,
    )
    if result.status != "granted":
        return None, f"{permission} authority is {result.status}: {result.reason}"
    digest = hashlib.sha256(decision.model_dump_json().encode("utf-8")).hexdigest()
    return (
        ValidationResult(
            decision_id=decision.decision_id,
            is_legal=True,
            authority_status="granted",
            reason="pilot admission",
            mode="admission",
            admission_eligible=True,
            decision_digest=digest,
        ),
        None,
    )


def _quarter_date(quarter: str, day: int = 15) -> date:
    year = int(quarter[:4])
    month = {1: 1, 2: 4, 3: 7, 4: 10}[int(quarter[-1])]
    return date(year, month, day)


def _procurement_org(network: Any, commodity_id: str) -> int:
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    commodity_index = tuple(network.commodity_ids).index(commodity_id)
    mask = (
        (demand_purpose == _PROCUREMENT_PURPOSE)
        & (cell_commodity[demand_cell] == commodity_index)
        & (cell_owner_kind[demand_cell] == 0)
    )
    owners = sorted({int(value) for value in cell_owner_id[demand_cell][mask]})
    if not owners:
        raise ConfigError(f"no procurement organization for {commodity_id}")
    return owners[0]


def _productive_org(state: Any) -> int:
    candidates = np.flatnonzero(np.asarray(state.organization_capacity) > 0.0)
    if candidates.size == 0:
        raise ConfigError("no productive organization in the branch state")
    return int(candidates[0])


def _baseline_tick(state: Any, forcing: Any, parameters: Any, network: Any) -> Any:
    opening = capture_material_stocks(state)
    flows = tick_material(state, forcing, parameters, network)
    summary = accounting.check_material_invariants(
        opening, state, flows, parameters, network
    )
    if summary.max_material_abs_residual >= 1e-6 or summary.max_finance_abs_residual >= 1e-6:
        raise ConfigError("baseline tick failed the invariant gate")
    state.completed_ticks += 1
    return flows


def _metrics(flows: Any) -> dict[str, float]:
    return {
        "delivered": float(flows.delivered.sum()),
        "household_realized": float(flows.household_realized.sum()),
        "household_availability_unmet": float(flows.household_availability_unmet.sum()),
        "household_spending": float(flows.household_spending.sum()),
        "financial_blocked": float(flows.financial_delivery_blocked.sum()),
        "physical_blocked": float(flows.physical_delivery_blocked.sum()),
    }


def _decisions(
    *,
    quarter: str,
    procurement_org: int,
    investment_org: int,
    parameters: Any,
    network: Any,
    design: dict[str, Any],
) -> dict[str, Any]:
    decision_at = _quarter_date(quarter)
    available_at = _quarter_date(quarter, 10)
    procurement = ProcurementDecision(
        decision_id=f"pilot-proc-{quarter}",
        actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
        organization_id="ORG-ENT-A",
        sector_id="industry",
        quarter=quarter,
        decision_at=decision_at,
        available_at=available_at,
        kind=ProcurementChoiceKind.REQUEST,
        commodity_id=design["procurement"]["commodity_id"],
        requested_quantity=float(design["procurement"]["quantity"]),
    )
    price_commodity = design["price"]["commodity_id"]
    price_index = tuple(network.commodity_ids).index(price_commodity)
    price = PriceProposalDecision(
        decision_id=f"pilot-price-{quarter}",
        actor_role=ActorRole.APPROVER,
        organization_id="ORG-GOV",
        sector_id="industry",
        quarter=quarter,
        decision_at=decision_at,
        available_at=available_at,
        kind=PriceProposalKind.ADJUST,
        commodity_id=price_commodity,
        proposed_price=float(parameters.prices[price_index])
        * float(design["price"]["factor"]),
    )
    fixed_price = price.model_copy(
        update={
            "decision_id": f"pilot-price-fixed-{quarter}",
            "commodity_id": design["price"]["fixed_category_commodity_id"],
            "proposed_price": float(parameters.prices[
                tuple(network.commodity_ids).index(
                    design["price"]["fixed_category_commodity_id"]
                )
            ])
            * 1.1,
        }
    )
    investment = InvestmentDecision(
        decision_id=f"pilot-inv-{quarter}",
        actor_role=ActorRole.INVESTMENT_ORGANIZATION,
        organization_id="ORG-ENT-B",
        sector_id="industry",
        quarter=quarter,
        decision_at=decision_at,
        available_at=available_at,
        kind="request",
        project_id=design["investment"]["project_id"],
        requested_amount=float(design["investment"]["requested_amount"]),
    )
    return {
        "procurement": procurement,
        "price": price,
        "price_fixed": fixed_price,
        "investment": investment,
    }


def _authority_granted(decision: Any, calendar: RegimeCalendar, permission: str) -> bool:
    result = authority_at(
        calendar,
        organization_id=decision.organization_id,
        sector_id=decision.sector_id,
        geographic_id="national",
        permission=permission,
        decision_at=decision.decision_at,
    )
    return result.status == "granted"


def _restore_state(state: Any, snapshot: Any) -> None:
    import copy

    for field_name in state.__dataclass_fields__:
        setattr(state, field_name, copy.deepcopy(getattr(snapshot, field_name)))


def _combined_tick(
    *,
    state: Any,
    forcing: Any,
    parameters: Any,
    network: Any,
    calendar: RegimeCalendar,
    regime: PriceRegime,
    decisions: dict[str, Any],
    procurement_org: int,
    investment_org: int,
    spec: Any,
) -> tuple[Any, dict[str, Any]]:
    procurement = decisions["procurement"]
    price = decisions["price"]
    investment = decisions["investment"]
    validation, error = _admit(procurement, calendar, "procurement")
    if error is not None:
        raise ConfigError(f"combined procurement rejected: {error}")
    if not validation.is_legal:
        raise ConfigError(f"combined procurement rejected: {validation.reason}")
    if not _authority_granted(price, calendar, "price_setting"):
        raise ConfigError("combined price authority is not granted")
    if not _authority_granted(investment, calendar, "investment_approval"):
        raise ConfigError("combined investment authority is not granted")
    rule = regime.rule_for(price.commodity_id)
    if rule.regime != "authorized_adjustment":
        raise ConfigError("combined price category is fixed")

    commodity_index = tuple(network.commodity_ids).index(price.commodity_id)
    material, catalog = compile_price_override(
        parameters,
        network.household_parameters,
        commodity_index=commodity_index,
        price=float(price.proposed_price),
        commodity_ids=tuple(network.commodity_ids),
    )
    capital_index = _role_index(network, "capital")
    construction_index = _role_index(network, "construction")
    unit_cost = 0.0
    if capital_index >= 0:
        unit_cost += float(parameters.capacity_capital_goods_per_unit) * float(
            parameters.prices[capital_index]
        )
    if construction_index >= 0:
        unit_cost += float(parameters.capacity_construction_per_unit) * float(
            parameters.prices[construction_index]
        )
    if unit_cost <= 0.0:
        raise ConfigError("combined investment unit cost is not positive")
    approved_capacity = float(investment.requested_amount) / unit_cost
    controls = TickControls(
        material_parameters=material,
        household_parameters=network.household_parameters,
        household_catalog=catalog,
        autonomy=0.0,
        central_target=None,
        policy=None,
        procurement_requests=(
            (
                procurement_org,
                tuple(network.commodity_ids).index(procurement.commodity_id),
                float(procurement.requested_quantity),
            ),
        ),
        investment_approvals=((investment_org, approved_capacity),),
    )
    import copy

    baseline_flows = tick_material(
        copy.deepcopy(state), forcing, parameters, network, controls=None
    )
    baseline_requested = float(
        baseline_flows.organization_investment_requested[investment_org]
    )
    before = copy.deepcopy(state)
    opening = capture_material_stocks(state)
    try:
        flows = tick_material(state, forcing, material, network, controls=controls)
        summary = accounting.check_material_invariants(
            opening, state, flows, material, network, controls=controls
        )
        if (
            summary.max_material_abs_residual >= 1e-6
            or summary.max_finance_abs_residual >= 1e-6
        ):
            raise PilotTickFailure("combined tick failed the invariant gate")
        old_price = float(parameters.prices[commodity_index])
        delivered, _payment, _purchases = _procurement_delivery(
            flows,
            network,
            procurement_org,
            commodity_index,
            material,
        )
        investment_requested = float(
            flows.organization_investment_requested[investment_org]
        )
        trace = {
            "control": "combined",
            "price_commodity_id": price.commodity_id,
            "old_price": old_price,
            "new_price": float(material.prices[commodity_index]),
            "procurement_quantity": float(procurement.requested_quantity),
            "procurement_delivered": delivered,
            "approved_capacity": approved_capacity,
            "baseline_investment_requested": baseline_requested,
            "investment_requested": investment_requested,
            "investment_approved": float(
                flows.organization_investment_approved[investment_org]
            ),
            "investment_cap_binding": baseline_requested > approved_capacity + 1e-9,
        }
    except PilotTickFailure:
        _restore_state(state, before)
        raise
    except Exception as exc:  # noqa: BLE001 - restore then stop
        _restore_state(state, before)
        raise PilotTickFailure(f"combined tick failed: {exc}") from exc
    state.completed_ticks += 1
    return flows, trace


def _role_index(network: Any, role: str) -> int:
    catalog = get_catalog(str(network.catalog_id))
    for commodity_id in catalog.with_role(role):
        if commodity_id in network.commodity_ids:
            return tuple(network.commodity_ids).index(commodity_id)
    return -1


_ARM_PERMISSION = {
    "procurement_granted": "procurement",
    "procurement_revoked": "procurement",
    "procurement_unknown": "procurement",
    "price_fixed": "price_setting",
    "price_authorized": "price_setting",
    "investment_delegated": "investment_approval",
    "investment_ungranted": "investment_approval",
}


def _arm_tick(
    *,
    arm: str,
    state: Any,
    forcing: Any,
    parameters: Any,
    network: Any,
    calendar: RegimeCalendar,
    regime: PriceRegime,
    decisions: dict[str, Any],
    procurement_org: int,
    investment_org: int,
    organization_index: dict[str, int],
    spec: Any,
) -> tuple[Any, dict[str, Any], bool]:
    """Run one arm tick; return flows, trace, and whether a decision committed."""
    if arm == "negative_control":
        return _baseline_tick(state, forcing, parameters, network), {"control": "none"}, False

    if arm.startswith("procurement_"):
        decision = decisions["procurement"]
        validation, error = _admit(decision, calendar, _ARM_PERMISSION[arm])
        if error is not None:
            return (
                _baseline_tick(state, forcing, parameters, network),
                {"control": "procurement_requests", "validation": error,
                 "committed": False},
                False,
            )
        result = commit_proposal(
            decision,
            validation,
            state,
            forcing,
            parameters,
            network,
            organization_index=organization_index,
        )
        if not result.is_committed:
            return (
                _baseline_tick(state, forcing, parameters, network),
                {"control": "procurement_requests", "reason": result.reason,
                 "committed": False},
                False,
            )
        return result.flows, {**dict(result.trace), "committed": True}, True

    if arm == "price_fixed":
        decision = decisions["price_fixed"]
        validation, error = _admit(decision, calendar, _ARM_PERMISSION[arm])
        if error is not None:
            return (
                _baseline_tick(state, forcing, parameters, network),
                {"control": "price_override", "validation": error,
                 "committed": False},
                False,
            )
        result = commit_proposal(
            decision,
            validation,
            state,
            forcing,
            parameters,
            network,
            authority_calendar=calendar,
            price_regime=regime,
        )
        if not result.is_committed:
            return (
                _baseline_tick(state, forcing, parameters, network),
                {"control": "price_override", "reason": result.reason, "committed": False},
                False,
            )
        return result.flows, {**dict(result.trace), "committed": True}, True

    if arm == "price_authorized":
        decision = decisions["price"]
        validation, error = _admit(decision, calendar, _ARM_PERMISSION[arm])
        if error is not None:
            return (
                _baseline_tick(state, forcing, parameters, network),
                {"control": "price_override", "validation": error,
                 "committed": False},
                False,
            )
        result = commit_proposal(
            decision,
            validation,
            state,
            forcing,
            parameters,
            network,
            authority_calendar=calendar,
            price_regime=regime,
        )
        if not result.is_committed:
            return (
                _baseline_tick(state, forcing, parameters, network),
                {"control": "price_override", "reason": result.reason, "committed": False},
                False,
            )
        return result.flows, {**dict(result.trace), "committed": True}, True

    if arm == "investment_delegated":
        decision = decisions["investment"]
        validation, error = _admit(decision, calendar, _ARM_PERMISSION[arm])
        if error is not None:
            return (
                _baseline_tick(state, forcing, parameters, network),
                {"control": "investment_approvals", "validation": error,
                 "committed": False},
                False,
            )
        result = commit_proposal(
            decision,
            validation,
            state,
            forcing,
            parameters,
            network,
            organization_index=organization_index,
            authority_calendar=calendar,
        )
        if not result.is_committed:
            return (
                _baseline_tick(state, forcing, parameters, network),
                {"control": "investment_approvals", "reason": result.reason,
                 "committed": False},
                False,
            )
        return result.flows, {**dict(result.trace), "committed": True}, True

    if arm == "investment_ungranted":
        decision = decisions["investment"]
        validation, error = _admit(decision, calendar, _ARM_PERMISSION[arm])
        if error is not None:
            return (
                _baseline_tick(state, forcing, parameters, network),
                {"control": "investment_approvals", "validation": error, "committed": False},
                False,
            )
        result = commit_proposal(
            decision,
            validation,
            state,
            forcing,
            parameters,
            network,
            organization_index=organization_index,
            authority_calendar=calendar,
        )
        if not result.is_committed:
            return (
                _baseline_tick(state, forcing, parameters, network),
                {"control": "investment_approvals", "reason": result.reason,
                 "committed": False},
                False,
            )
        return result.flows, {**dict(result.trace), "committed": True}, True

    if arm == "combined":
        try:
            flows, trace = _combined_tick(
                state=state,
                forcing=forcing,
                parameters=parameters,
                network=network,
                calendar=calendar,
                regime=regime,
                decisions=decisions,
                procurement_org=procurement_org,
                investment_org=investment_org,
                spec=spec,
            )
        except ConfigError as exc:
            return (
                _baseline_tick(state, forcing, parameters, network),
                {"control": "combined", "reason": str(exc), "committed": False},
                False,
            )
        return flows, {**trace, "committed": True}, True

    raise ConfigError(f"unknown arm {arm!r}")


def run_pilot(
    root: Path,
    *,
    spec_path: Path = DEFAULT_SPEC,
    output_dir: Path,
    arms_override: Sequence[str] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    spec_file = (root / spec_path).resolve()
    output = Path(output_dir)
    output = output.resolve() if output.is_absolute() else (root / output).resolve()
    if output.exists():
        raise ConfigError(f"output directory already exists: {output}")
    config = json.loads(spec_file.read_text(encoding="utf-8"))
    if config.get("schema_version") != SCHEMA_VERSION:
        raise ConfigError("unexpected pilot spec schema")
    scenario_id = config["source_scenario"]
    scenario = load_scenario(root, scenario_id)
    contract = load_research_contract(root)
    registry = DataRegistry.load(root, allowed_commodities=list(scenario.commodities))
    forcing = load_material_forcing(scenario, registry)
    initial = build_material_initial_conditions(scenario, RngRegistry(int(config["seed"])))
    network = build_material_network(scenario, contract, initial)
    state = initialize_material(scenario, initial, network)
    parameters = scenario.material_parameters
    assert parameters is not None

    branch_quarter = str(config["branch_quarter"])
    try:
        branch_index = list(forcing.quarters).index(branch_quarter)
    except ValueError as exc:
        raise ConfigError(f"forcing has no quarter {branch_quarter}") from exc
    for _ in range(branch_index):
        _baseline_tick(state, forcing, parameters, network)
    if state.completed_ticks != branch_index:
        raise ConfigError("warm-up did not reach the declared branch tick")
    branch_state = copy.deepcopy(state)
    branch_sha = hashlib.sha256(canonical_material_bytes(branch_state)).hexdigest()

    design = config["declared_design"]
    procurement_org = _procurement_org(network, design["procurement"]["commodity_id"])
    investment_org = _productive_org(state)
    organization_index = {
        "ORG-ENT-A": procurement_org,
        "ORG-ENT-B": investment_org,
    }
    regime = PriceRegime.model_validate_json((root / PRICE_REGIME).read_text())

    declared_arms = list(config["arms"])
    arm_names = list(arms_override) if arms_override is not None else list(declared_arms)
    unknown_arms = sorted(set(arm_names) - set(declared_arms))
    if unknown_arms:
        raise ConfigError(f"unknown pilot arm(s): {unknown_arms}")
    arms: dict[str, Any] = {}
    for arm in arm_names:
        if arm == "negative_control":
            calendar = _calendar()
        elif arm == "procurement_revoked":
            calendar = _calendar(revoke_procurement_for="ORG-ENT-A")
        elif arm == "procurement_unknown":
            calendar = _calendar(no_procurement=True)
        elif arm == "investment_ungranted":
            calendar = _calendar(no_investment=True)
        else:
            calendar = _calendar()

        arm_state = copy.deepcopy(branch_state)
        traces: list[dict[str, Any]] = []
        totals = {
            "delivered": 0.0,
            "household_realized": 0.0,
            "household_availability_unmet": 0.0,
            "household_spending": 0.0,
            "financial_blocked": 0.0,
            "physical_blocked": 0.0,
        }
        committed = 0
        for _ in range(int(config["window_ticks"])):
            quarter = str(forcing.quarters[arm_state.completed_ticks])
            decisions = _decisions(
                quarter=quarter,
                procurement_org=procurement_org,
                investment_org=investment_org,
                parameters=parameters,
                network=network,
                design=design,
            )
            flows, trace, did_commit = _arm_tick(
                arm=arm,
                state=arm_state,
                forcing=forcing,
                parameters=parameters,
                network=network,
                calendar=calendar,
                regime=regime,
                decisions=decisions,
                procurement_org=procurement_org,
                investment_org=investment_org,
                organization_index=organization_index,
                spec=scenario,
            )
            trace["quarter"] = quarter
            traces.append(trace)
            committed += int(did_commit)
            for key, value in _metrics(flows).items():
                totals[key] += value
        arms[arm] = {
            "status": "EXECUTED",
            "decision_commits": committed,
            "totals": totals,
            "trace": traces,
            "final_state_sha256": hashlib.sha256(
                canonical_material_bytes(arm_state)
            ).hexdigest(),
        }

    negative = arms.get("negative_control", {}).get("totals")
    if negative is not None:
        for _arm, record in arms.items():
            record["delta_vs_negative_control"] = {
                key: record["totals"][key] - negative[key] for key in negative
            }

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "pilot_id": canonical_digest(
            {
                "spec": config,
                "branch_state_sha256": branch_sha,
                "arms": sorted(arm_names),
            }
        )[:32],
        "status": ("COMPLETED" if set(arm_names) == set(declared_arms) else "PARTIAL"),
        "seed": int(config["seed"]),
        "source_scenario": scenario_id,
        "branch": {
            "warmup_until": config["warmup_until"],
            "branch_quarter": branch_quarter,
            "branch_completed_ticks": branch_index,
            "branch_state_sha256": branch_sha,
            "historical_status": "NOT_ESTABLISHED",
            "notice": "model-generated 1968Q1 branch; not a historical initial state",
        },
        "window_ticks": int(config["window_ticks"]),
        "declared_design": design,
        "arms_declared": declared_arms,
        "arms_executed": arm_names,
        "price_regime": {
            "path": str(PRICE_REGIME),
            "sha256": hashlib.sha256((root / PRICE_REGIME).read_bytes()).hexdigest(),
        },
        "authority_calendar": {
            "synthetic": True,
            "grant_effective_from": "1967-12-01",
            "procurement_revoke_effective_from": "1967-12-15",
        },
        "selected_organizations": {
            "procurement_org_index": procurement_org,
            "investment_org_index": investment_org,
        },
        "arms": arms,
        "negative_control": "negative_control" if "negative_control" in arms else None,
        "historical_status": "NOT_ESTABLISHED",
        "notes": config.get("notes", []),
    }
    output.mkdir(parents=True)
    (output / "pilot_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "arm_metrics.json").write_text(
        json.dumps(
            {
                arm: {
                    "status": record["status"],
                    "decision_commits": record["decision_commits"],
                    "totals": record["totals"],
                    "delta_vs_negative_control": record.get(
                        "delta_vs_negative_control"
                    ),
                }
                for arm, record in arms.items()
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest



def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--spec", default=str(DEFAULT_SPEC))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--arm", action="append", dest="arms")
    args = parser.parse_args(argv)
    try:
        result = run_pilot(
            Path(args.root),
            spec_path=Path(args.spec),
            output_dir=Path(args.output_dir),
            arms_override=args.arms,
        )
    except (ConfigError, OSError, ValueError, PilotTickFailure) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps({"status": "ok", "pilot_id": result["pilot_id"]}, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
