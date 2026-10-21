"""H2B: bridge validated decisions to the material kernel.

Architecture
------------
Decision → H2A ``validate_proposal`` → ``ValidationResult(is_legal=True)``
                                        ↓
                              ``commit_proposal``
                                        ↓
              Existing ``TickControls`` (``central_target`` for planning,
              ``procurement_requests`` for commodity acquisition)
                                        ↓
              capture opening stocks → ``tick_material`` → invariant gate
                                        ↓
              advance one quarter only after the invariants pass

The adapter never writes stocks, accounts, deliveries or a second clock.  The
kernel owns ordering, allocation, delivery, finance and the accounting gate.
The only state mutation is the single-quarter ``completed_ticks`` advance that
the existing runner performs after a passing tick.

Procurement requests are expressed as commodity-specific demand on the
procurement hub.  The control carries ``(organization_idx, commodity_idx,
quantity)``; the kernel maps it onto that organization's procurement demand
cells for the commodity and then runs its normal order/allocation/payment
path.  If a decision cannot be expressed by an existing control (price,
investment, household need in this minimal phase), it is reported as not
committed with a static reason rather than rewriting state or inventing a
second mechanism.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

import numpy as np

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.material import (
    PURPOSE_CODES,
    STAGE_CODES,
    RoutePurpose,
    commodity_spec,
    get_catalog,
)
from hsm_lab.engine.policy import compile_price_override
from hsm_lab.institutions.authority import authority_at
from hsm_lab.institutions.decisions import (
    Decision,
    InvestmentDecision,
    PriceProposalDecision,
    ProcurementChoiceKind,
    ProcurementDecision,
)
from hsm_lab.institutions.price_regimes import PriceRegime
from hsm_lab.institutions.proposal_validation import ValidationResult

if TYPE_CHECKING:
    from hsm_lab.engine.material import MaterialTickFlows
    from hsm_lab.engine.network import MaterialNetwork
    from hsm_lab.engine.policy import TickControls
    from hsm_lab.engine.state import MaterialForcing, MaterialState


_PROCUREMENT_PURPOSE = PURPOSE_CODES[RoutePurpose.PROCUREMENT]


# ---------------------------------------------------------------------------
# Execution result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of committing one validated decision to the material kernel."""

    decision_id: str
    is_committed: bool
    flows: MaterialTickFlows | None = None
    reason: str = ""
    warnings: tuple[str, ...] = ()
    trace: tuple[tuple[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "is_committed": self.is_committed,
            "reason": self.reason,
            "warnings": list(self.warnings),
            "trace": dict(self.trace),
            "flows_summary": _flows_summary(self.flows) if self.flows else None,
        }


def _flows_summary(flows: MaterialTickFlows) -> dict[str, Any]:
    if flows is None:
        return {}
    return {
        "tick": int(flows.tick),
        "quarter": str(flows.quarter),
        "total_delivered": float(flows.delivered.sum()),
        "total_allocated": float(flows.allocated.sum()),
        "total_ordered": float(flows.ordered.sum()),
        "blocked_financial": float(flows.financial_delivery_blocked.sum()),
        "blocked_physical": float(flows.physical_delivery_blocked.sum()),
    }


# ---------------------------------------------------------------------------
# Identity resolution
# ---------------------------------------------------------------------------


def _resolve_organization_index(
    decision: Decision,
    state: MaterialState,
    organization_index: Mapping[str, int] | None,
) -> int:
    """Map the institutional organization identity to a material org index.

    The crosswalk is scenario-owned.  ``organization_index`` is the explicit
    mapping; otherwise a plain decimal organization id is accepted.  No
    implicit name matching is performed: an unresolved identity is a rejection,
    not a guess.
    """
    value = decision.organization_id
    if organization_index is None:
        raise KeyError(
            "explicit scenario organization crosswalk is required; "
            "no numeric identity fallback is used"
        )
    index = organization_index.get(value)
    if index is None:
        raise KeyError("organization identity is not in the scenario crosswalk")
    org_ids = np.asarray(state.organization_id, dtype=np.int64)
    if index < 0 or index >= len(org_ids) or int(org_ids[index]) != index:
        raise KeyError("organization index is outside the material state")
    return index


def _resolve_commodity_index(
    decision: ProcurementDecision,
    network: MaterialNetwork,
) -> int:
    commodity_ids = tuple(str(value) for value in network.commodity_ids)
    try:
        return commodity_ids.index(str(decision.commodity_id))
    except ValueError:
        raise KeyError("commodity is not in the material network") from None


# ---------------------------------------------------------------------------
# TickControls construction
# ---------------------------------------------------------------------------


def _base_controls(
    parameters: Any,
    network: MaterialNetwork,
    controls: TickControls | None,
) -> TickControls:
    from hsm_lab.engine.policy import TickControls

    if controls is not None:
        return controls
    return TickControls(
        material_parameters=parameters,
        household_parameters=network.household_parameters,
        household_catalog=network.household_catalog,
        autonomy=0.0,
        central_target=None,
        policy=None,
        procurement_requests=None,
        investment_approvals=None,
    )


def _with_procurement_request(
    controls: TickControls,
    request: tuple[int, int, float],
) -> TickControls:

    existing = controls.procurement_requests or ()
    return replace(
        controls,
        material_parameters=controls.material_parameters,
        household_parameters=controls.household_parameters,
        household_catalog=controls.household_catalog,
        autonomy=controls.autonomy,
        central_target=controls.central_target,
        policy=controls.policy,
        procurement_requests=(*existing, request),
    )


# ---------------------------------------------------------------------------
# Procurement trace
# ---------------------------------------------------------------------------


def _procurement_delivery(
    flows: MaterialTickFlows,
    network: MaterialNetwork,
    organization_index: int,
    commodity_index: int,
    parameters: Any,
) -> tuple[float, float, float]:
    """Return (delivered, commodity goods payment, organization-wide purchases).

    ``buyer_payment`` is derived from the delivered quantity and the
    commodity's administered price, not from the organization's combined
    purchases across every commodity.
    """
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)

    consumable_stage = STAGE_CODES[
        commodity_spec(network.commodity_ids[commodity_index]).consumable_stage()
    ]
    cell_stage = np.asarray(network.cell_stage, dtype=np.int64)
    mask = (
        (demand_purpose == _PROCUREMENT_PURPOSE)
        & (cell_commodity[demand_cell] == commodity_index)
        & (cell_stage[demand_cell] == consumable_stage)
    )
    owner_mask = (cell_owner_kind[demand_cell] == 0) & (
        cell_owner_id[demand_cell] == organization_index
    )
    mask = mask & owner_mask
    delivered_cells = np.asarray(flows.delivered, dtype=np.float64)[mask]
    delivered = float(delivered_cells.sum())
    from hsm_lab.engine.material import build_material_prices

    prices = build_material_prices(parameters)
    stages = cell_stage[demand_cell[mask]]
    unit_prices = np.asarray(
        [prices.price_for(commodity_index, int(stage)) for stage in stages],
        dtype=np.float64,
    )
    goods_payment = float((delivered_cells * unit_prices).sum())
    purchases = getattr(flows, "organization_purchases", None)
    organization_purchases = (
        float(np.asarray(purchases, dtype=np.float64)[organization_index])
        if purchases is not None
        else 0.0
    )
    return delivered, goods_payment, organization_purchases


def _has_procurement_cells(
    network: MaterialNetwork,
    organization_index: int,
    commodity_index: int,
) -> bool:
    """True iff this organization owns a procurement cell for the commodity."""
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    consumable_stage = STAGE_CODES[
        commodity_spec(network.commodity_ids[commodity_index]).consumable_stage()
    ]
    cell_stage = np.asarray(network.cell_stage, dtype=np.int64)
    return bool(
        (
            (demand_purpose == _PROCUREMENT_PURPOSE)
            & (cell_commodity[demand_cell] == commodity_index)
            & (cell_stage[demand_cell] == consumable_stage)
            & (cell_owner_kind[demand_cell] == 0)
            & (cell_owner_id[demand_cell] == organization_index)
        ).any()
    )


def _restore_state(state: MaterialState, snapshot: MaterialState) -> None:
    """Restore every mutable field from a pre-tick deep copy."""
    import copy

    for field_name in state.__dataclass_fields__:
        setattr(state, field_name, copy.deepcopy(getattr(snapshot, field_name)))


def _require_authority(
    decision: Decision,
    *,
    permission: str,
    authority_calendar: Any | None,
    geographic_id: str,
) -> str | None:
    """Return an error reason unless the declared authority grants permission."""
    if authority_calendar is None:
        return "no authority calendar supplied; the authority-bound bridge fails closed"
    result = authority_at(
        authority_calendar,
        organization_id=decision.organization_id,
        sector_id=decision.sector_id,
        geographic_id=geographic_id,
        permission=permission,
        decision_at=decision.decision_at,
    )
    if result.status != "granted":
        return f"{permission} authority is {result.status}: {result.reason}"
    return None


def _run_controls_tick(
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: Any,
    network: MaterialNetwork,
    controls: Any,
    opening: Any,
    before: MaterialState,
) -> tuple[MaterialTickFlows | None, str | None]:
    """Run one tick under controls and enforce the invariant gate with rollback."""
    from hsm_lab.engine import accounting
    from hsm_lab.engine.material import tick_material

    try:
        flows = tick_material(state, forcing, parameters, network, controls=controls)
        summary = accounting.check_material_invariants(
            opening, state, flows, parameters, network, controls=controls
        )
    except Exception as exc:  # noqa: BLE001 - failure must roll back the state
        _restore_state(state, before)
        return None, f"tick or invariant gate failed: {exc}"
    if (
        summary.max_material_abs_residual >= 1e-6
        or summary.max_finance_abs_residual >= 1e-6
    ):
        _restore_state(state, before)
        return None, "material/financial invariant gate rejected the quarter"
    return flows, None


def _baseline_flows(
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: Any,
    network: MaterialNetwork,
    controls: Any,
) -> MaterialTickFlows | None:
    import copy

    from hsm_lab.engine.material import tick_material

    try:
        return tick_material(
            copy.deepcopy(state), forcing, parameters, network, controls=controls
        )
    except Exception:  # noqa: BLE001 - a failed baseline is reported as no baseline
        return None


def _commit_price(
    decision: PriceProposalDecision,
    *,
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: Any,
    network: MaterialNetwork,
    controls: Any,
    tick: int,
    quarter: str,
    authority_calendar: Any | None,
    price_regime: PriceRegime | None,
    geographic_id: str,
) -> ExecutionResult:
    import copy

    from hsm_lab.engine.state import capture_material_stocks

    if price_regime is None:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason="no declared price regime supplied; price bridge fails closed",
        )
    try:
        rule = price_regime.rule_for(decision.commodity_id)
    except ConfigError as exc:
        return ExecutionResult(
            decision_id=decision.decision_id, is_committed=False, reason=str(exc)
        )
    authority_error = _require_authority(
        decision,
        permission="price_setting",
        authority_calendar=authority_calendar,
        geographic_id=geographic_id,
    )
    if authority_error is not None:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason=authority_error,
        )
    if rule.regime == "fixed":
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason=(
                f"price category {rule.category_id!r} is fixed; "
                "no proposal is admissible"
            ),
        )
    commodity_ids = tuple(str(value) for value in network.commodity_ids)
    try:
        commodity_index = commodity_ids.index(decision.commodity_id)
    except ValueError:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason="commodity is not in the material network",
        )
    old_price = float(parameters.prices[commodity_index])
    try:
        new_material, catalog = compile_price_override(
            parameters,
            network.household_parameters,
            commodity_index=commodity_index,
            price=float(decision.proposed_price),
            commodity_ids=commodity_ids,
        )
    except ConfigError as exc:
        return ExecutionResult(
            decision_id=decision.decision_id, is_committed=False, reason=str(exc)
        )
    new_controls = replace(
        controls,
        material_parameters=new_material,
        household_catalog=catalog,
    )
    baseline_flows = _baseline_flows(state, forcing, parameters, network, controls)
    before = copy.deepcopy(state)
    opening = capture_material_stocks(state)
    flows, error = _run_controls_tick(
        state, forcing, new_material, network, new_controls, opening, before
    )
    if error is not None or flows is None:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason=error or "price tick produced no flows",
            trace=(
                ("tick", tick),
                ("quarter", quarter),
                ("commodity_id", decision.commodity_id),
                ("control", "price_override"),
                ("binding_status", "rejected"),
            ),
        )
    state.completed_ticks += 1
    new_price = float(new_material.prices[commodity_index])
    baseline_delivered = float(baseline_flows.delivered.sum()) if baseline_flows else 0.0
    return ExecutionResult(
        decision_id=decision.decision_id,
        is_committed=True,
        flows=flows,
        trace=(
            ("tick", tick),
            ("quarter", quarter),
            ("control", "price_override"),
            ("control_applied", True),
            ("category_id", rule.category_id),
            ("regime", rule.regime),
            ("commodity_id", decision.commodity_id),
            ("commodity_index", commodity_index),
            ("old_price", old_price),
            ("new_price", new_price),
            ("price_ratio", (new_price / old_price) if old_price > 0.0 else None),
            ("baseline_delivered", baseline_delivered),
            ("decision_delivered", float(flows.delivered.sum())),
            ("binding_status", "changed" if new_price != old_price else "nonbinding"),
        ),
    )


def _role_index(network: MaterialNetwork, role: str) -> int:
    catalog = get_catalog(str(network.catalog_id))
    commodity_ids = tuple(str(value) for value in network.commodity_ids)
    for commodity_id in catalog.with_role(role):
        if commodity_id in commodity_ids:
            return commodity_ids.index(commodity_id)
    return -1


def _commit_investment(
    decision: InvestmentDecision,
    *,
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: Any,
    network: MaterialNetwork,
    controls: Any,
    tick: int,
    quarter: str,
    organization_index: Mapping[str, int] | None,
    authority_calendar: Any | None,
    geographic_id: str,
) -> ExecutionResult:
    import copy

    from hsm_lab.engine.state import capture_material_stocks

    authority_error = _require_authority(
        decision,
        permission="investment_approval",
        authority_calendar=authority_calendar,
        geographic_id=geographic_id,
    )
    if authority_error is not None:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason=authority_error,
        )
    try:
        organization_index_value = _resolve_organization_index(
            decision, state, organization_index
        )
    except KeyError as exc:
        return ExecutionResult(
            decision_id=decision.decision_id, is_committed=False, reason=str(exc)
        )
    capital_index = _role_index(network, "capital")
    construction_index = _role_index(network, "construction")
    capital_unit = float(parameters.capacity_capital_goods_per_unit)
    construction_unit = float(parameters.capacity_construction_per_unit)
    if capital_unit > 0.0 and capital_index < 0:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason="network has no capital commodity for investment pricing",
        )
    if construction_unit > 0.0 and construction_index < 0:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason="network has no construction commodity for investment pricing",
        )
    unit_cost = 0.0
    if capital_index >= 0:
        unit_cost += capital_unit * float(parameters.prices[capital_index])
    if construction_index >= 0:
        unit_cost += construction_unit * float(parameters.prices[construction_index])
    if unit_cost <= 0.0:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason="investment unit cost is not positive; approval cannot be sized",
        )
    requested_amount = 0.0 if decision.kind == "withdraw" else float(
        decision.requested_amount
    )
    approved_capacity = requested_amount / unit_cost
    new_controls = replace(
        controls,
        investment_approvals=((organization_index_value, approved_capacity),),
    )
    baseline_flows = _baseline_flows(state, forcing, parameters, network, controls)
    before = copy.deepcopy(state)
    approved_before = float(state.organization_project_approved[organization_index_value])
    capacity_before = float(state.organization_capacity[organization_index_value])
    opening = capture_material_stocks(state)
    flows, error = _run_controls_tick(
        state, forcing, parameters, network, new_controls, opening, before
    )
    if error is not None or flows is None:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason=error or "investment tick produced no flows",
            trace=(
                ("tick", tick),
                ("quarter", quarter),
                ("organization_id", decision.organization_id),
                ("control", "investment_approvals"),
                ("binding_status", "rejected"),
            ),
        )
    state.completed_ticks += 1
    approved_after = float(state.organization_project_approved[organization_index_value])
    capacity_after = float(state.organization_capacity[organization_index_value])
    return ExecutionResult(
        decision_id=decision.decision_id,
        is_committed=True,
        flows=flows,
        trace=(
            ("tick", tick),
            ("quarter", quarter),
            ("control", "investment_approvals"),
            ("control_applied", True),
            ("organization_id", decision.organization_id),
            ("organization_index", organization_index_value),
            ("project_id", decision.project_id),
            ("requested_amount", requested_amount),
            ("unit_cost", unit_cost),
            ("approved_capacity", approved_capacity),
            ("approved_open_before", approved_before),
            ("approved_open_after", approved_after),
            ("capacity_before", capacity_before),
            ("capacity_after", capacity_after),
            (
                "baseline_delivered",
                float(baseline_flows.delivered.sum()) if baseline_flows else 0.0,
            ),
            ("decision_delivered", float(flows.delivered.sum())),
            (
                "baseline_investment_requested",
                float(
                    baseline_flows.organization_investment_requested[organization_index_value]
                )
                if baseline_flows is not None
                else 0.0,
            ),
            (
                "baseline_investment_approved",
                float(
                    baseline_flows.organization_investment_approved[organization_index_value]
                )
                if baseline_flows is not None
                else 0.0,
            ),
            (
                "investment_requested",
                float(flows.organization_investment_requested[organization_index_value]),
            ),
            (
                "investment_approved",
                float(flows.organization_investment_approved[organization_index_value]),
            ),
            ("binding_status", "approved" if approved_capacity > 0.0 else "withdrawn"),
        ),
    )


# ---------------------------------------------------------------------------
# Main commit function
# ---------------------------------------------------------------------------


def commit_proposal(
    decision: Decision,
    validation_result: ValidationResult,
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: Any,
    network: MaterialNetwork,
    controls: TickControls | None = None,
    *,
    organization_index: Mapping[str, int] | None = None,
    authority_calendar: Any | None = None,
    price_regime: PriceRegime | None = None,
    geographic_id: str = "",
) -> ExecutionResult:
    """Commit one validated decision through ``TickControls`` and one tick.

    Steps (H2B admission lifecycle):
    1. reject non-legal or unbound validation;
    2. bind decision id, quarter and identity to the kernel context;
    3. translate the decision into an existing ``TickControls`` field;
    4. capture opening stocks;
    5. run exactly one ``tick_material``;
    6. run the material/financial invariant gate with the same controls;
    7. advance ``completed_ticks`` only after the gate passes;
    8. return the kernel flows and a decision→control→delivery trace.
    """
    from hsm_lab.institutions.proposal_validation import (
        _decision_storage_violation,
    )

    # No attribute access before the exact-type/storage boundary: a str
    # subclass or shadowed field can execute a callback during comparison.
    storage_violation = _decision_storage_violation(decision)
    if storage_violation is not None:
        return ExecutionResult(
            decision_id="<invalid>",
            is_committed=False,
            reason=f"decision payload is malformed: {storage_violation}",
        )

    if not validation_result.is_legal:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason=f"Decision not committed: {validation_result.reason}",
        )
    if decision.decision_id != validation_result.decision_id:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason="decision_id does not match the validated decision",
        )
    if validation_result.mode != "admission":
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason="validated decision is not admission-eligible",
        )
    if validation_result.admission_eligible is not True:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason="validated decision is not admission-eligible",
        )
    import hashlib

    expected_digest = hashlib.sha256(
        decision.model_dump_json().encode("utf-8")
    ).hexdigest()
    if not validation_result.decision_digest:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason="validation result is not bound to a decision payload",
        )
    if validation_result.decision_digest != expected_digest:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason="decision payload does not match the validated payload",
        )
    tick = int(state.completed_ticks)
    quarters = list(forcing.quarters)
    if tick < 0 or tick >= len(quarters):
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason="decision tick lies outside the forcing horizon",
        )
    expected_quarter = str(quarters[tick])
    if decision.quarter != expected_quarter:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason=(
                f"decision quarter {decision.quarter!r} does not match the "
                f"kernel quarter {expected_quarter!r}"
            ),
        )

    base = _base_controls(parameters, network, controls)
    if type(decision) is PriceProposalDecision:
        return _commit_price(
            decision,
            state=state,
            forcing=forcing,
            parameters=parameters,
            network=network,
            controls=base,
            tick=tick,
            quarter=expected_quarter,
            authority_calendar=authority_calendar,
            price_regime=price_regime,
            geographic_id=geographic_id,
        )
    if type(decision) is InvestmentDecision:
        return _commit_investment(
            decision,
            state=state,
            forcing=forcing,
            parameters=parameters,
            network=network,
            controls=base,
            tick=tick,
            quarter=expected_quarter,
            organization_index=organization_index,
            authority_calendar=authority_calendar,
            geographic_id=geographic_id,
        )
    if type(decision) is not ProcurementDecision:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason="no TickControls mapping for this decision type",
        )

    try:
        organization_index_value = _resolve_organization_index(
            decision, state, organization_index
        )
        commodity_index = _resolve_commodity_index(decision, network)
    except KeyError as exc:
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason=str(exc),
        )

    if not _has_procurement_cells(
        network, organization_index_value, commodity_index
    ):
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason=(
                "organization has no procurement destination for the "
                "requested commodity; the control is unwired"
            ),
        )

    quantity = (
        0.0
        if decision.kind == ProcurementChoiceKind.CANCEL
        else float(decision.requested_quantity)
    )
    request = (organization_index_value, commodity_index, quantity)
    base = _base_controls(parameters, network, controls)
    new_controls = _with_procurement_request(base, request)

    import copy

    from hsm_lab.engine.material import tick_material
    from hsm_lab.engine.state import capture_material_stocks

    # The same quarter without the decision gives the baseline activity, so
    # the trace reports the request's incremental delivery rather than all
    # background procurement.
    baseline_state = copy.deepcopy(state)
    baseline_flows = tick_material(
        baseline_state, forcing, parameters, network, controls=base
    )
    (
        baseline_delivered,
        baseline_payment,
        baseline_organization_purchases,
    ) = _procurement_delivery(
        baseline_flows,
        network,
        organization_index_value,
        commodity_index,
        parameters,
    )

    before = copy.deepcopy(state)
    opening = capture_material_stocks(state)
    try:
        flows = tick_material(
            state,
            forcing,
            parameters,
            network,
            controls=new_controls,
        )
        from hsm_lab.engine import accounting

        summary = accounting.check_material_invariants(
            opening, state, flows, parameters, network, controls=new_controls
        )
    except Exception as exc:  # noqa: BLE001 - failure must roll back the state
        _restore_state(state, before)
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason=f"tick or invariant gate failed: {exc}",
            trace=(
                ("tick", tick),
                ("quarter", expected_quarter),
                ("organization_id", decision.organization_id),
                ("binding_status", "failed_rolled_back"),
            ),
        )
    if (
        summary.max_material_abs_residual >= 1e-6
        or summary.max_finance_abs_residual >= 1e-6
    ):
        _restore_state(state, before)
        return ExecutionResult(
            decision_id=decision.decision_id,
            is_committed=False,
            reason="material/financial invariant gate rejected the quarter",
            trace=(
                ("tick", tick),
                ("quarter", expected_quarter),
                ("organization_id", decision.organization_id),
                ("organization_index", organization_index_value),
                ("commodity_id", decision.commodity_id),
                ("commodity_index", commodity_index),
                ("requested_quantity", quantity),
                ("control_applied", True),
                ("control", "procurement_requests"),
                ("binding_status", "rejected_invariant"),
            ),
        )

    state.completed_ticks += 1
    (
        delivered,
        payment,
        organization_purchases,
    ) = _procurement_delivery(
        flows,
        network,
        organization_index_value,
        commodity_index,
        parameters,
    )
    incremental_delivered = delivered - baseline_delivered
    incremental_payment = payment - baseline_payment
    incremental_organization_purchases = (
        organization_purchases - baseline_organization_purchases
    )
    if quantity <= 0.0:
        binding_status = "nonbinding"
    elif incremental_delivered + 1e-9 < quantity:
        binding_status = "binding"
    else:
        binding_status = "satisfied"

    trace = (
        ("tick", tick),
        ("quarter", expected_quarter),
        ("organization_id", decision.organization_id),
        ("organization_index", organization_index_value),
        ("commodity_id", decision.commodity_id),
        ("commodity_index", commodity_index),
        ("requested_quantity", quantity),
        ("control_applied", quantity > 0.0),
        ("control", "procurement_requests"),
        ("baseline_delivered_quantity", baseline_delivered),
        ("delivered_quantity", delivered),
        ("incremental_delivered_quantity", incremental_delivered),
        ("baseline_buyer_payment", baseline_payment),
        ("buyer_payment", payment),
        ("incremental_buyer_payment", incremental_payment),
        (
            "baseline_organization_purchases",
            baseline_organization_purchases,
        ),
        ("organization_purchases", organization_purchases),
        (
            "incremental_organization_purchases",
            incremental_organization_purchases,
        ),
        ("plan_actual_gap", quantity - incremental_delivered),
        ("binding_status", binding_status),
        ("autonomy", float(new_controls.autonomy)),
        (
            "central_target_preserved",
            controls is not None
            and controls.central_target is new_controls.central_target,
        ),
        ("completed_ticks_after", int(state.completed_ticks)),
        ("deterministic_replay_tick", int(flows.tick)),
    )
    return ExecutionResult(
        decision_id=decision.decision_id,
        is_committed=True,
        flows=flows,
        reason="committed through TickControls",
        trace=trace,
    )
