"""External trade channels for the material economy (P02 plan section 5).

Four helpers the kernel drives in one fixed clearing order:

* ``realize_external_debt_service`` — USD interest on the OPENING principal
  first, then the payable scheduled principal, then a loan draw capped at the
  quarterly ceiling and sized only to the remaining import funding gap.  New
  draws never accrue same-quarter interest.
* ``realize_imports`` — channel-separated import clearance: the CMEA cap is
  ``cmea_credit_envelope + max(settlement balance, 0)``; USD imports come from
  the reserve remaining after debt service (plus the fresh draw).  Desired
  quantities scale proportionally within a channel; channel books are never
  netted against each other.  Realized quantities land in the treasury
  import-pool cells (food imports are ``ready`` by construction).
* ``build_export_demands`` — channel export demand vectors as demand-cell
  claims, scaled to what the Treasury can actually pay this quarter.
* ``settle_exports_and_closing`` — export receipts are booked to the CLOSING
  USD reserve / CMEA settlement balance (usable next quarter); the CMEA
  balance may go negative as memo credit without creating a loan asset.

Every function mutates the working arrays / flows the kernel passes and
appends Journal legs, but stays importable for direct fixture tests.  The
external books use one trade-settlement account per currency paired against
the treasury fiscal account (the plan's "trade bridge"): each transaction is
single-currency and balanced, no cross-currency valuation is ever booked, and
the official FX quote is a diagnostic only.  Convertible energy carries the
world oil price relative to the reference anchor; CMEA energy uses the
reconstructed contract quote when one exists for the quarter and the
structural prior otherwise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from hsm_lab.contract.material import MaterialParameters, get_catalog
from hsm_lab.engine import finance
from hsm_lab.engine.finance import (
    CMEA_CURRENCY,
    USD_CURRENCY,
    foreign_account_id,
    quarter_external_rate,
    treasury_account_id,
    treasury_receivable_account_id,
)
from hsm_lab.engine.state import (
    ExportContract,
    ExportReceivable,
    ExportReceivableEvent,
    ExportReceivablePolicy,
    MaterialState,
    MaterialTickFlows,
)

if TYPE_CHECKING:  # pragma: no cover - annotation-only; avoids an import cycle
    from hsm_lab.engine.network import MaterialNetwork

__all__ = [
    "apply_receivable_events",
    "build_export_demands",
    "channel_prices",
    "realize_external_debt_service",
    "realize_imports",
    "receivable_journal_rows",
    "resolve_export_contract",
    "settle_exports_and_closing",
    "settle_exports_on_receivables",
    "validate_export_contract",
    "validate_export_event",
    "validate_export_policy",
    "validate_receivable_book",
]


def _finite(name: str, *values: float) -> None:
    for value in values:
        if not np.isfinite(value):
            raise ValueError(f"{name} must be finite, got {value!r}")


def _fixed_axis_vector(values: list[float], network: MaterialNetwork) -> np.ndarray:
    """Map a catalog-indexed trade vector onto the network commodity axis."""
    index = get_catalog(network.catalog_id).index
    mapped = np.zeros(len(network.commodity_ids), dtype=np.float64)
    for g, commodity_id in enumerate(network.commodity_ids):
        fixed = index.get(commodity_id)
        if fixed is not None:
            mapped[g] = float(values[fixed])
    return mapped


def channel_prices(
    parameters: MaterialParameters,
    network: MaterialNetwork,
    *,
    oil_price: float,
    cmea_contract_price: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-unit channel price vectors on the network commodity axis.

    ``cmea_contract_price`` is the quarter's reconstructed contract quote for
    CMEA energy (NaN outside its registered window); the structural prior
    ``cmea_base_energy_price * cmea_uncertainty_multiplier`` applies then.
    Convertible energy is scaled by ``oil_price / world_oil_reference``.
    """
    _finite("oil_price", oil_price)
    trade = parameters.trade
    cmea = _fixed_axis_vector(trade.cmea_prices, network)
    convertible = _fixed_axis_vector(trade.convertible_prices, network)
    catalog = get_catalog(network.catalog_id)
    energy_ids = catalog.with_role("energy")
    energy_index = catalog.index[energy_ids[0]] if energy_ids else None
    for g, commodity_id in enumerate(network.commodity_ids):
        if energy_index is not None and commodity_id in energy_ids:
            cmea[g] = (
                float(cmea_contract_price)
                if np.isfinite(cmea_contract_price)
                else float(parameters.cmea_base_energy_price)
                * float(parameters.cmea_uncertainty_multiplier)
            )
            convertible[g] = (
                float(trade.convertible_prices[energy_index])
                * float(oil_price)
                / float(parameters.world_oil_reference)
            )
    return cmea, convertible


def realize_external_debt_service(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    *,
    global_rate_percent: float,
    desired_usd_outlay: float = 0.0,
    transaction_base: int = 0,
) -> dict[str, float]:
    """USD clearing on the OPENING principal: interest, principal, then draw.

    Interest for the quarter is ``global_rate_percent / 400 +
    hungary_spread_annual / 4`` on the opening principal; unpaid interest
    accrues into ``usd_interest_arrears`` (never capitalized).  The scheduled
    principal is ``principal_repayment_fraction`` of the opening principal and
    is paid only from the remaining reserve; unpaid principal keeps its
    original balance.  The draw is capped at ``convertible_loan_limit`` and
    sized to the import funding gap only, so loans are never drawn without a
    spending need.  Returns the realized amounts for diagnostics.
    """
    _finite("global_rate_percent", global_rate_percent, desired_usd_outlay)
    if state.usd_reserve < -1e-12 or state.usd_principal < -1e-12:
        raise ValueError("external accounts must open non-negative")
    treasury_fiscal = treasury_account_id(state, finance.AccountKind.FISCAL_EXPENSE)
    usd_account = foreign_account_id(state, USD_CURRENCY)
    transaction_id = int(transaction_base)

    opening_principal = float(state.usd_principal)
    rate = quarter_external_rate(global_rate_percent, parameters)
    interest_due = opening_principal * rate
    interest_paid = min(interest_due, float(state.usd_reserve))
    interest_arrears = interest_due - interest_paid
    state.usd_reserve -= interest_paid
    state.usd_interest_arrears = float(state.usd_interest_arrears) + interest_arrears

    scheduled = opening_principal * float(parameters.principal_repayment_fraction)
    principal_paid = min(scheduled, float(state.usd_reserve))
    state.usd_reserve -= principal_paid
    state.usd_principal = opening_principal - principal_paid

    draw = min(
        float(parameters.trade.convertible_loan_limit),
        max(0.0, float(desired_usd_outlay) - float(state.usd_reserve)),
    )
    state.usd_reserve += draw
    state.usd_principal += draw

    flows.usd_interest_accrued = interest_due
    flows.usd_interest_paid = interest_paid
    flows.usd_principal_paid = principal_paid
    flows.usd_loan_drawn = draw

    if interest_paid > 0.0:
        finance.append_transaction(
            flows,
            transaction_id=transaction_id,
            kind="interest_payment",
            legs=[(treasury_fiscal, usd_account, USD_CURRENCY, interest_paid)],
        )
        transaction_id += 1
    if principal_paid > 0.0:
        finance.append_transaction(
            flows,
            transaction_id=transaction_id,
            kind="principal_repayment",
            legs=[(treasury_fiscal, usd_account, USD_CURRENCY, principal_paid)],
        )
        transaction_id += 1
    if draw > 0.0:
        finance.append_transaction(
            flows,
            transaction_id=transaction_id,
            kind="loan_drawdown",
            legs=[(usd_account, treasury_fiscal, USD_CURRENCY, draw)],
        )
    return {
        "interest_due": interest_due,
        "interest_paid": interest_paid,
        "interest_arrears": interest_arrears,
        "principal_scheduled": scheduled,
        "principal_paid": principal_paid,
        "loan_drawn": draw,
    }


def realize_imports(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    network: MaterialNetwork,
    *,
    oil_price: float,
    cmea_contract_price: float,
    transaction_base: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Clear both import channels and land quantities in the import-pool cells.

    The CMEA quarterly cost cap is ``cmea_credit_envelope +
    max(settlement balance, 0)``; the USD budget is the reserve remaining
    after external debt service.  Desired vectors scale by one uniform factor
    per channel; commodities without an import-pool cell import zero.  The
    channel payments hit the CMEA settlement balance (may go negative) and
    the USD reserve respectively and are journaled in their own currency —
    never netted.  Returns ``(cmea_imports, convertible_imports)`` (G,).
    """
    _finite("oil_price", oil_price)
    trade = parameters.trade
    cmea_prices, convertible_prices = channel_prices(
        parameters,
        network,
        oil_price=oil_price,
        cmea_contract_price=cmea_contract_price,
    )
    cmea_desired = _fixed_axis_vector(trade.cmea_desired_imports, network)
    convertible_desired = _fixed_axis_vector(trade.convertible_desired_imports, network)

    import_cell = np.asarray(network.import_pool_cell, dtype=np.int64)
    has_cell = import_cell >= 0
    cmea_desired = np.where(has_cell, cmea_desired, 0.0)
    convertible_desired = np.where(has_cell, convertible_desired, 0.0)

    cmea_cap = float(trade.cmea_credit_envelope) + max(
        float(state.cmea_settlement_balance), 0.0
    )
    cmea_cost = float(np.dot(cmea_desired, cmea_prices))
    cmea_scale = min(1.0, cmea_cap / cmea_cost) if cmea_cost > 0.0 else 0.0
    cmea_imports = cmea_desired * cmea_scale
    cmea_payment = float(np.dot(cmea_imports, cmea_prices))

    usd_budget = float(state.usd_reserve)
    usd_cost = float(np.dot(convertible_desired, convertible_prices))
    usd_scale = min(1.0, usd_budget / usd_cost) if usd_cost > 0.0 else 0.0
    convertible_imports = convertible_desired * usd_scale
    usd_payment = float(np.dot(convertible_imports, convertible_prices))

    landed = cmea_imports + convertible_imports
    cells = import_cell[has_cell]
    if cells.size:
        state.stock_value[cells] += landed[has_cell]

    state.cmea_settlement_balance = float(state.cmea_settlement_balance) - cmea_payment
    state.usd_reserve = float(state.usd_reserve) - usd_payment

    flows.cmea_imports = cmea_imports.copy()
    flows.convertible_imports = convertible_imports.copy()
    flows.imports = landed.copy()
    flows.cmea_import_payment = cmea_payment
    flows.usd_import_payment = usd_payment

    treasury_fiscal = treasury_account_id(state, finance.AccountKind.FISCAL_EXPENSE)
    transaction_id = int(transaction_base)
    if cmea_payment > 0.0:
        finance.append_transaction(
            flows,
            transaction_id=transaction_id,
            kind="import_payment",
            legs=[
                (
                    treasury_fiscal,
                    foreign_account_id(state, CMEA_CURRENCY),
                    CMEA_CURRENCY,
                    cmea_payment,
                )
            ],
        )
        transaction_id += 1
    if usd_payment > 0.0:
        finance.append_transaction(
            flows,
            transaction_id=transaction_id,
            kind="import_payment",
            legs=[
                (
                    treasury_fiscal,
                    foreign_account_id(state, USD_CURRENCY),
                    USD_CURRENCY,
                    usd_payment,
                )
            ],
        )
    return cmea_imports, convertible_imports


def build_export_demands(
    parameters: MaterialParameters,
    network: MaterialNetwork,
    *,
    treasury_payable: float,
    admin_price: np.ndarray,
    freight_per_unit: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Channel export demand vectors scaled to the Treasury's domestic cash.

    Returns ``(desired, ordered)`` as ``(2, G)`` arrays (channel 0 = CMEA,
    1 = convertible).  The Treasury cannot lift domestic stock without paying
    the admin price plus the freight estimate, so the combined claim is scaled
    by one uniform factor when the payable cash falls short; physical
    availability is reserved later by the tier-2 allocation.
    """
    _finite("treasury_payable", treasury_payable)
    trade = parameters.trade
    desired = np.vstack(
        [
            _fixed_axis_vector(trade.cmea_export_demands, network),
            _fixed_axis_vector(trade.convertible_export_demands, network),
        ]
    )
    unit_cost = np.vstack([admin_price, admin_price]) + np.asarray(
        freight_per_unit, dtype=np.float64
    )
    total_cost = float(np.sum(desired * unit_cost))
    scale = min(1.0, float(treasury_payable) / total_cost) if total_cost > 0.0 else 0.0
    ordered = desired * scale
    return desired, ordered


def settle_exports_and_closing(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    network: MaterialNetwork,
    *,
    cmea_export_delivered: np.ndarray,
    convertible_export_delivered: np.ndarray,
    oil_price: float,
    cmea_contract_price: float,
    official_fx_quote: float,
    transaction_base: int = 0,
) -> None:
    """Book export receipts to the CLOSING external accounts (plan section 5).

    Receipts are computed from DELIVERED quantities only, at the channel
    prices, and land on the closing USD reserve / CMEA settlement balance —
    they become spendable next quarter.  The CMEA balance may close negative
    (memo credit; no loan asset is created to double-count it).  The official
    FX quote is recorded as ``official_fx_translation`` when — and only when —
    a forcing quote exists for the quarter; it never touches quantities,
    admin prices or settlement.
    """
    _finite("oil_price", oil_price)
    cmea_prices, convertible_prices = channel_prices(
        parameters,
        network,
        oil_price=oil_price,
        cmea_contract_price=cmea_contract_price,
    )
    cmea_delivered = np.asarray(cmea_export_delivered, dtype=np.float64)
    convertible_delivered = np.asarray(convertible_export_delivered, dtype=np.float64)
    if not (
        np.all(np.isfinite(cmea_delivered))
        and np.all(np.isfinite(convertible_delivered))
        and np.all(cmea_delivered >= 0.0)
        and np.all(convertible_delivered >= 0.0)
    ):
        raise ValueError("delivered export quantities must be finite and non-negative")

    cmea_receipt = float(np.dot(cmea_delivered, cmea_prices))
    usd_receipt = float(np.dot(convertible_delivered, convertible_prices))
    state.cmea_settlement_balance = float(state.cmea_settlement_balance) + cmea_receipt
    state.usd_reserve = float(state.usd_reserve) + usd_receipt

    flows.cmea_exports = cmea_delivered.copy()
    flows.convertible_exports = convertible_delivered.copy()
    flows.cmea_export_receipt = cmea_receipt
    flows.usd_export_receipt = usd_receipt
    flows.official_fx_translation = (
        float(official_fx_quote) if np.isfinite(official_fx_quote) else None
    )

    treasury_fiscal = treasury_account_id(state, finance.AccountKind.FISCAL_EXPENSE)
    transaction_id = int(transaction_base)
    if cmea_receipt > 0.0:
        finance.append_transaction(
            flows,
            transaction_id=transaction_id,
            kind="export_receipt",
            legs=[
                (
                    foreign_account_id(state, CMEA_CURRENCY),
                    treasury_fiscal,
                    CMEA_CURRENCY,
                    cmea_receipt,
                )
            ],
        )
        transaction_id += 1
    if usd_receipt > 0.0:
        finance.append_transaction(
            flows,
            transaction_id=transaction_id,
            kind="export_receipt",
            legs=[
                (
                    foreign_account_id(state, USD_CURRENCY),
                    treasury_fiscal,
                    USD_CURRENCY,
                    usd_receipt,
                )
            ],
        )


# ---------------------------------------------------------------------------
# H3F-D2: export receivables on contract terms
# ---------------------------------------------------------------------------

RECEIVABLE_KINDS = frozenset({"delivery", "receipt", "loss", "writeoff", "recovery"})
_RECEIVABLE_TOL = 1e-9


def _receivable_reject(message: str) -> None:
    raise ValueError(f"export receivables: {message}")


def _contract_for(
    contracts: tuple[ExportContract, ...], currency: str, commodity_id: str
) -> ExportContract:
    matches = [
        contract
        for contract in contracts
        if contract.currency == currency
        and (contract.commodity_id is None or contract.commodity_id == commodity_id)
    ]
    if len(matches) != 1:
        _receivable_reject(
            f"expected exactly one contract for ({currency!r}, {commodity_id!r}); "
            f"found {len(matches)}"
        )
    return matches[0]


def _strict_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        _receivable_reject(f"{name} must be a strict integer")
    return int(value)


def _strict_amount(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(
        value, (int, float, np.integer, np.floating)
    ):
        _receivable_reject(f"{name} must be a strict number")
    amount = float(value)
    if not np.isfinite(amount):
        _receivable_reject(f"{name} must be finite")
    return amount


def _strict_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        _receivable_reject(f"{name} must be a non-empty string")
    return value


def validate_export_contract(contract: ExportContract) -> None:
    if not isinstance(contract, ExportContract):
        _receivable_reject("contracts must be ExportContract instances")
    _strict_text(contract.contract_id, "contract.contract_id")
    if contract.currency not in (USD_CURRENCY, CMEA_CURRENCY):
        _receivable_reject(f"contract {contract.contract_id!r} has unknown currency")
    buyer = _strict_int(contract.buyer_id, "contract.buyer_id")
    seller = _strict_int(contract.seller_id, "contract.seller_id")
    if buyer < 0 or seller < 0:
        _receivable_reject(f"contract {contract.contract_id!r} has negative ids")
    if seller != 0:
        _receivable_reject("the synthetic export seller is Treasury id 0")
    if contract.commodity_id is not None:
        _strict_text(contract.commodity_id, "contract.commodity_id")


def validate_export_event(event: ExportReceivableEvent) -> None:
    if not isinstance(event, ExportReceivableEvent):
        _receivable_reject("events must be ExportReceivableEvent instances")
    _strict_text(event.event_id, "event.event_id")
    _strict_text(event.receivable_id, "event.receivable_id")
    _strict_text(event.contract_id, "event.contract_id")
    _strict_text(event.commodity_id, "event.commodity_id")
    if event.kind not in RECEIVABLE_KINDS:
        _receivable_reject(f"unknown event kind {event.kind!r}")
    if event.currency not in (USD_CURRENCY, CMEA_CURRENCY):
        _receivable_reject(f"event {event.event_id!r} has unknown currency")
    tick = _strict_int(event.tick, "event.tick")
    delivery_tick = _strict_int(event.delivery_tick, "event.delivery_tick")
    due_tick = _strict_int(event.due_tick, "event.due_tick")
    buyer = _strict_int(event.buyer_id, "event.buyer_id")
    seller = _strict_int(event.seller_id, "event.seller_id")
    if tick < 0 or delivery_tick < 0 or due_tick < 0:
        _receivable_reject(f"event {event.event_id!r} has a negative tick")
    if buyer < 0 or seller < 0:
        _receivable_reject(f"event {event.event_id!r} has negative ids")
    if seller != 0:
        _receivable_reject("the synthetic export seller is Treasury id 0")
    if due_tick <= delivery_tick:
        _receivable_reject(f"event {event.event_id!r} has a non-positive term")
    if delivery_tick > tick:
        _receivable_reject(f"event {event.event_id!r} is future-dated")
    _strict_amount(event.amount, f"event {event.event_id!r} amount")
    if float(event.amount) <= 0.0:
        _receivable_reject(f"event {event.event_id!r} amount must be positive")


def validate_export_policy(policy: ExportReceivablePolicy) -> None:
    if not isinstance(policy, ExportReceivablePolicy):
        _receivable_reject("policy must be an ExportReceivablePolicy")
    term = _strict_int(policy.term_quarters, "policy.term_quarters")
    if term < 1:
        _receivable_reject("policy.term_quarters must be >= 1")
    if not isinstance(policy.contracts, tuple) or not policy.contracts:
        _receivable_reject("policy.contracts must be a non-empty tuple")
    ids: set[str] = set()
    keys: set[tuple[str, str | None]] = set()
    wildcards: dict[str, int] = {}
    for contract in policy.contracts:
        validate_export_contract(contract)
        if contract.contract_id in ids:
            _receivable_reject(f"duplicate contract id {contract.contract_id!r}")
        ids.add(contract.contract_id)
        key = (contract.currency, contract.commodity_id)
        if key in keys:
            _receivable_reject(f"duplicate contract key {key!r}")
        keys.add(key)
        if contract.commodity_id is None:
            wildcards[contract.currency] = wildcards.get(contract.currency, 0) + 1
    if any(count > 1 for count in wildcards.values()):
        _receivable_reject("at most one wildcard contract per currency")
    seen: set[str] = set()
    for event in policy.events:
        validate_export_event(event)
        if event.kind == "delivery":
            _receivable_reject("delivery events are generated by the kernel")
        if event.event_id.startswith("delivery:"):
            _receivable_reject(
                f"caller event id {event.event_id!r} uses the reserved delivery namespace"
            )
        if event.event_id in seen:
            _receivable_reject(f"duplicate event id {event.event_id!r}")
        seen.add(event.event_id)


def validate_receivable_book(
    book: tuple[ExportReceivable, ...],
    event_ids: tuple[str, ...],
    *,
    completed_ticks: int | None = None,
    commodity_ids: tuple[str, ...] | None = None,
) -> None:
    """Validate a whole book/log boundary; shared by gate, adapter and checkpoint."""
    if not isinstance(book, tuple):
        _receivable_reject("receivable book must be a tuple")
    if not isinstance(event_ids, tuple):
        _receivable_reject("receivable event ids must be a tuple")
    if completed_ticks is not None:
        boundary = _strict_int(completed_ticks, "completed_ticks")
        if boundary < 0:
            _receivable_reject("completed_ticks must be non-negative")
        last_tick = boundary - 1
    else:
        last_tick = None
    commodity_set = set(commodity_ids) if commodity_ids is not None else None
    ids: set[str] = set()
    for lot in book:
        if not isinstance(lot, ExportReceivable):
            _receivable_reject("book entries must be ExportReceivable instances")
        _strict_text(lot.receivable_id, "receivable.receivable_id")
        _strict_text(lot.contract_id, "receivable.contract_id")
        _strict_text(lot.commodity_id, "receivable.commodity_id")
        if commodity_set is not None and lot.commodity_id not in commodity_set:
            _receivable_reject(
                f"receivable {lot.receivable_id!r} names unknown commodity "
                f"{lot.commodity_id!r}"
            )
        if lot.currency not in (USD_CURRENCY, CMEA_CURRENCY):
            _receivable_reject(f"receivable {lot.receivable_id!r} has unknown currency")
        buyer = _strict_int(lot.buyer_id, "receivable.buyer_id")
        seller = _strict_int(lot.seller_id, "receivable.seller_id")
        delivery_tick = _strict_int(lot.delivery_tick, "receivable.delivery_tick")
        due_tick = _strict_int(lot.due_tick, "receivable.due_tick")
        expected_id = f"{lot.contract_id}@{delivery_tick}:{lot.commodity_id}"
        if lot.receivable_id != expected_id:
            _receivable_reject(
                f"receivable id {lot.receivable_id!r} is not the canonical "
                f"contract@tick:commodity identity {expected_id!r}"
            )
        if buyer < 0 or seller < 0:
            _receivable_reject(f"receivable {lot.receivable_id!r} has negative ids")
        if seller != 0:
            _receivable_reject("the synthetic export seller is Treasury id 0")
        if delivery_tick < 0 or due_tick <= delivery_tick:
            _receivable_reject(f"receivable {lot.receivable_id!r} has an invalid term")
        if last_tick is not None:
            if delivery_tick > last_tick:
                _receivable_reject(
                    f"receivable {lot.receivable_id!r} delivery tick is not before "
                    "the boundary"
                )
            if lot.received > _RECEIVABLE_TOL and delivery_tick >= last_tick:
                _receivable_reject(
                    f"receivable {lot.receivable_id!r} records collection without "
                    "a completed post-delivery tick"
                )
            if (
                lot.provision_expense > _RECEIVABLE_TOL
                or lot.writeoffs > _RECEIVABLE_TOL
                or lot.recovered > _RECEIVABLE_TOL
            ) and due_tick > last_tick:
                _receivable_reject(
                    f"receivable {lot.receivable_id!r} records loss/write-off/recovery "
                    "before its due tick has completed"
                )
        if lot.receivable_id in ids:
            _receivable_reject(f"duplicate receivable id {lot.receivable_id!r}")
        ids.add(lot.receivable_id)
        principal = _strict_amount(lot.principal, "receivable.principal")
        if principal <= 0.0:
            _receivable_reject(f"receivable {lot.receivable_id!r} principal must be positive")
        _check_lot(lot)
        if abs(lot.written_off - (lot.writeoffs - lot.recovered)) > _RECEIVABLE_TOL:
            _receivable_reject(
                f"receivable {lot.receivable_id!r} written-off balance is not "
                "cumulative write-offs minus recoveries"
            )
        if lot.recovered > lot.received + _RECEIVABLE_TOL:
            _receivable_reject(
                f"receivable {lot.receivable_id!r} recovered more than collected"
            )
        if abs(lot.provision_released - lot.recovered) > _RECEIVABLE_TOL:
            _receivable_reject(
                f"receivable {lot.receivable_id!r} provision releases differ from "
                "cumulative recoveries"
            )
        if lot.writeoffs > lot.principal + _RECEIVABLE_TOL:
            _receivable_reject(f"receivable {lot.receivable_id!r} write-offs exceed principal")
    seen: set[str] = set()
    for event_id in event_ids:
        _strict_text(event_id, "event id")
        if event_id in seen:
            _receivable_reject(f"duplicate event id {event_id!r}")
        seen.add(event_id)
    expected_delivery_ids = {f"delivery:{lot.receivable_id}" for lot in book}
    actual_delivery_ids = {
        event_id for event_id in seen if event_id.startswith("delivery:")
    }
    if actual_delivery_ids != expected_delivery_ids:
        extra = sorted(actual_delivery_ids - expected_delivery_ids)
        missing = sorted(expected_delivery_ids - actual_delivery_ids)
        _receivable_reject(
            "receivable delivery log does not match retained lots: "
            f"extra={extra} missing={missing}"
        )


def resolve_export_contract(
    contracts: tuple[ExportContract, ...], currency: str, commodity_id: str
) -> ExportContract:
    """Resolve exactly one declared contract for a real delivery."""
    for contract in contracts:
        validate_export_contract(contract)
    return _contract_for(contracts, currency, commodity_id)


def _validate_receivable_event(event: ExportReceivableEvent, current_tick: int) -> None:
    validate_export_event(event)
    if event.tick != current_tick:
        _receivable_reject(
            f"event {event.event_id!r} carries tick {event.tick}, expected {current_tick}"
        )


def _match_identity(lot: ExportReceivable, event: ExportReceivableEvent) -> None:
    mismatched = [
        name
        for name, left, right in (
            ("contract_id", lot.contract_id, event.contract_id),
            ("currency", lot.currency, event.currency),
            ("buyer_id", lot.buyer_id, event.buyer_id),
            ("seller_id", lot.seller_id, event.seller_id),
            ("commodity_id", lot.commodity_id, event.commodity_id),
            ("delivery_tick", lot.delivery_tick, event.delivery_tick),
            ("due_tick", lot.due_tick, event.due_tick),
        )
        if left != right
    ]
    if mismatched:
        _receivable_reject(
            f"event {event.event_id!r} identity mismatch on {mismatched}"
        )


def apply_receivable_events(
    book: tuple[ExportReceivable, ...],
    event_ids: tuple[str, ...],
    events: tuple[ExportReceivableEvent, ...],
    *,
    current_tick: int,
) -> tuple[tuple[ExportReceivable, ...], tuple[str, ...]]:
    """Apply one tick's receivable events to an opening book, purely.

    The function is shared by the settlement step and the independent
    accounting gate; it never mutates its inputs.  Delivery is the only event
    that opens a lot; receipts and loss events target existing lots, and a new
    delivery can never be collected in its own tick.
    """
    validate_receivable_book(book, event_ids)
    lots = {lot.receivable_id: lot for lot in book}
    seen = set(event_ids)
    applied_ids = list(event_ids)
    for event in events:
        _validate_receivable_event(event, current_tick)
        if event.event_id in seen:
            _receivable_reject(f"duplicate event id {event.event_id!r}")
        seen.add(event.event_id)
        applied_ids.append(event.event_id)

        if event.kind == "delivery":
            if event.delivery_tick != current_tick:
                _receivable_reject("delivery events must be dated in the current tick")
            if event.receivable_id in lots:
                _receivable_reject(f"duplicate receivable id {event.receivable_id!r}")
            lots[event.receivable_id] = ExportReceivable(
                receivable_id=event.receivable_id,
                contract_id=event.contract_id,
                currency=event.currency,
                buyer_id=event.buyer_id,
                seller_id=event.seller_id,
                commodity_id=event.commodity_id,
                delivery_tick=event.delivery_tick,
                due_tick=event.due_tick,
                principal=float(event.amount),
                gross=float(event.amount),
                provision=0.0,
                written_off=0.0,
                received=0.0,
                recovered=0.0,
                writeoffs=0.0,
                provision_expense=0.0,
                provision_released=0.0,
            )
            continue

        lot = lots.get(event.receivable_id)
        if lot is None:
            _receivable_reject(f"unknown receivable {event.receivable_id!r}")
        _match_identity(lot, event)
        if lot.delivery_tick >= current_tick:
            _receivable_reject(
                f"receivable {event.receivable_id!r} cannot be collected in its delivery tick"
            )

        amount = float(event.amount)
        if event.kind == "receipt":
            if amount > lot.gross + _RECEIVABLE_TOL:
                _receivable_reject(f"receipt exceeds gross receivable for {event.event_id!r}")
            lot = _replace_lot(lot, gross=lot.gross - amount, received=lot.received + amount)
        elif event.kind == "loss":
            if current_tick < lot.due_tick:
                _receivable_reject(f"loss before due tick for {event.event_id!r}")
            if amount > lot.gross - lot.provision + _RECEIVABLE_TOL:
                _receivable_reject(
                    f"loss provision exceeds gross receivable for {event.event_id!r}"
                )
            lot = _replace_lot(
                lot,
                provision=lot.provision + amount,
                provision_expense=lot.provision_expense + amount,
            )
        elif event.kind == "writeoff":
            if current_tick < lot.due_tick:
                _receivable_reject(f"write-off before due tick for {event.event_id!r}")
            if amount > lot.gross + _RECEIVABLE_TOL or amount > lot.provision + _RECEIVABLE_TOL:
                _receivable_reject(f"write-off exceeds gross/provision for {event.event_id!r}")
            lot = _replace_lot(
                lot,
                gross=lot.gross - amount,
                provision=lot.provision - amount,
                written_off=lot.written_off + amount,
                writeoffs=lot.writeoffs + amount,
            )
        elif event.kind == "recovery":
            if amount > lot.written_off + _RECEIVABLE_TOL:
                _receivable_reject(f"recovery exceeds written-off balance for {event.event_id!r}")
            # Restore the claim and its provision, collect it, then release
            # the rebuilt provision.  The cash receipt is the same amount.
            lot = _replace_lot(
                lot,
                gross=lot.gross,  # restore + collect net to the same gross
                provision=lot.provision,
                written_off=lot.written_off - amount,
                received=lot.received + amount,
                recovered=lot.recovered + amount,
                provision_expense=lot.provision_expense + amount,
                provision_released=lot.provision_released + amount,
            )
        _check_lot(lot)
        lots[event.receivable_id] = lot

    final_book = tuple(lots[key] for key in sorted(lots))
    final_ids = tuple(applied_ids)
    validate_receivable_book(final_book, final_ids)
    return final_book, final_ids


def _replace_lot(lot: ExportReceivable, **changes: float) -> ExportReceivable:
    import dataclasses

    return dataclasses.replace(lot, **changes)


def _check_lot(lot: ExportReceivable) -> None:
    for name in (
        "principal",
        "gross",
        "provision",
        "written_off",
        "received",
        "recovered",
        "writeoffs",
        "provision_expense",
        "provision_released",
    ):
        value = float(getattr(lot, name))
        if not np.isfinite(value) or value < -_RECEIVABLE_TOL:
            _receivable_reject(f"receivable {lot.receivable_id!r} {name} is invalid")
    if lot.provision > lot.gross + _RECEIVABLE_TOL:
        _receivable_reject(f"receivable {lot.receivable_id!r} provision exceeds gross")
    if lot.written_off < -_RECEIVABLE_TOL:
        _receivable_reject(f"receivable {lot.receivable_id!r} written-off balance is negative")
    closure = lot.gross + lot.received + lot.written_off
    if abs(closure - lot.principal) > max(_RECEIVABLE_TOL, 1e-12 * lot.principal):
        _receivable_reject(
            f"receivable {lot.receivable_id!r} principal closure failed: "
            f"gross+received+written_off={closure!r} principal={lot.principal!r}"
        )
    provision_closure = lot.provision_expense - lot.writeoffs - lot.provision_released
    if abs(provision_closure - lot.provision) > max(
        _RECEIVABLE_TOL, 1e-12 * max(1.0, lot.provision_expense)
    ):
        _receivable_reject(
            f"receivable {lot.receivable_id!r} provision closure failed: "
            f"Q-W-V={provision_closure!r} L={lot.provision!r}"
        )


def _receivable_journal_legs(
    state: MaterialState, event: ExportReceivableEvent
) -> list[tuple[str, list[tuple[int, int, str, float]]]]:
    currency = event.currency
    foreign = foreign_account_id(state, currency)
    receivable = treasury_receivable_account_id(
        state, currency, finance.AccountKind.EXPORT_RECEIVABLE
    )
    allowance = treasury_receivable_account_id(
        state, currency, finance.AccountKind.BAD_DEBT_ALLOWANCE
    )
    expense = treasury_receivable_account_id(
        state, currency, finance.AccountKind.BAD_DEBT_EXPENSE
    )
    income = treasury_receivable_account_id(
        state, currency, finance.AccountKind.EXPORT_SALES_INCOME
    )
    amount = float(event.amount)
    if event.kind == "delivery":
        return [
            (
                "export_receivable_delivery",
                [(receivable, income, currency, amount)],
            )
        ]
    if event.kind == "receipt":
        return [
            (
                "export_receivable_receipt",
                [(foreign, receivable, currency, amount)],
            )
        ]
    if event.kind == "loss":
        return [
            (
                "export_receivable_loss",
                [(expense, allowance, currency, amount)],
            )
        ]
    if event.kind == "writeoff":
        return [
            (
                "export_receivable_writeoff",
                [(allowance, receivable, currency, amount)],
            )
        ]
    if event.kind == "recovery":
        return [
            (
                "export_receivable_recovery_restore",
                [(receivable, allowance, currency, amount)],
            ),
            (
                "export_receivable_recovery_receipt",
                [(foreign, receivable, currency, amount)],
            ),
            (
                "export_receivable_recovery_release",
                [(allowance, expense, currency, amount)],
            ),
        ]
    _receivable_reject(f"unknown event kind {event.kind!r}")


def receivable_journal_rows(
    state: MaterialState, event: ExportReceivableEvent
) -> list[tuple[str, int, int, str, float, str]]:
    """Exact ``(kind, debit, credit, currency, amount, event_id)`` rows."""
    rows: list[tuple[str, int, int, str, float, str]] = []
    for kind, legs in _receivable_journal_legs(state, event):
        for debit, credit, currency, amount in legs:
            rows.append(
                (kind, int(debit), int(credit), currency, float(amount), event.event_id)
            )
    return rows


def settle_exports_on_receivables(
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    network: MaterialNetwork,
    *,
    cmea_export_delivered: np.ndarray,
    convertible_export_delivered: np.ndarray,
    oil_price: float,
    cmea_contract_price: float,
    official_fx_quote: float,
    policy: ExportReceivablePolicy,
    transaction_base: int = 0,
) -> None:
    """Book real deliveries as term receivables, then apply this tick's events.

    Only an actual receipt or recovery increases the foreign settlement
    balance.  A delivery increases the same-currency receivable and export
    sales income, never cash.  Every applied event is recorded on the flows so
    the accounting gate can independently replay it from the opening book.
    """
    _finite("oil_price", oil_price)
    validate_export_policy(policy)
    current_tick = int(flows.tick)
    cmea_prices, convertible_prices = channel_prices(
        parameters,
        network,
        oil_price=oil_price,
        cmea_contract_price=cmea_contract_price,
    )
    deliveries = (
        (
            CMEA_CURRENCY,
            np.asarray(cmea_export_delivered, dtype=np.float64),
            cmea_prices,
        ),
        (
            USD_CURRENCY,
            np.asarray(convertible_export_delivered, dtype=np.float64),
            convertible_prices,
        ),
    )
    delivery_events: list[ExportReceivableEvent] = []
    for currency, delivered, prices in deliveries:
        if delivered.shape != prices.shape:
            _receivable_reject("delivered quantity and price axes disagree")
        if not np.all(np.isfinite(delivered)) or np.any(delivered < 0.0):
            _receivable_reject("delivered export quantities must be finite and non-negative")
        for g in np.nonzero(delivered > 0.0)[0]:
            commodity_id = str(network.commodity_ids[int(g)])
            contract = _contract_for(policy.contracts, currency, commodity_id)
            receivable_id = f"{contract.contract_id}@{current_tick}:{commodity_id}"
            due_tick = current_tick + int(policy.term_quarters)
            delivery_events.append(
                ExportReceivableEvent(
                    event_id=f"delivery:{receivable_id}",
                    tick=current_tick,
                    kind="delivery",
                    receivable_id=receivable_id,
                    contract_id=contract.contract_id,
                    currency=currency,
                    buyer_id=int(contract.buyer_id),
                    seller_id=int(contract.seller_id),
                    commodity_id=commodity_id,
                    delivery_tick=current_tick,
                    due_tick=due_tick,
                    amount=float(delivered[int(g)] * prices[int(g)]),
                )
            )

    applied = tuple(delivery_events) + tuple(policy.events)
    book, event_ids = apply_receivable_events(
        tuple(state.export_receivables),
        tuple(state.export_receivable_event_ids),
        applied,
        current_tick=current_tick,
    )
    state.export_receivables = book
    state.export_receivable_event_ids = event_ids

    cmea_receipt = float(
        sum(
            event.amount
            for event in policy.events
            if event.currency == CMEA_CURRENCY and event.kind in ("receipt", "recovery")
        )
    )
    usd_receipt = float(
        sum(
            event.amount
            for event in policy.events
            if event.currency == USD_CURRENCY and event.kind in ("receipt", "recovery")
        )
    )
    state.cmea_settlement_balance = float(state.cmea_settlement_balance) + cmea_receipt
    state.usd_reserve = float(state.usd_reserve) + usd_receipt

    flows.cmea_exports = np.asarray(cmea_export_delivered, dtype=np.float64).copy()
    flows.convertible_exports = np.asarray(
        convertible_export_delivered, dtype=np.float64
    ).copy()
    flows.cmea_export_receipt = cmea_receipt
    flows.usd_export_receipt = usd_receipt
    flows.official_fx_translation = (
        float(official_fx_quote) if np.isfinite(official_fx_quote) else None
    )
    flows.export_receivable_events = applied
    flows.export_receivable_channel_prices = (
        tuple(float(value) for value in cmea_prices.tolist()),
        tuple(float(value) for value in convertible_prices.tolist()),
    )
    def event_total(kinds: tuple[str, ...], currency: str) -> float:
        return float(
            sum(
                event.amount
                for event in applied
                if event.kind in kinds and event.currency == currency
            )
        )

    for currency, suffix in ((USD_CURRENCY, "usd"), (CMEA_CURRENCY, "cmea")):
        setattr(
            flows,
            f"export_receivable_opened_{suffix}",
            event_total(("delivery",), currency),
        )
        setattr(
            flows,
            f"export_receivable_received_{suffix}",
            event_total(("receipt", "recovery"), currency),
        )
        setattr(
            flows,
            f"export_receivable_recovered_{suffix}",
            event_total(("recovery",), currency),
        )
        setattr(
            flows,
            f"export_receivable_written_off_{suffix}",
            event_total(("writeoff",), currency),
        )
        setattr(
            flows,
            f"export_receivable_loss_provision_{suffix}",
            event_total(("loss",), currency),
        )
        setattr(
            flows,
            f"export_receivable_provision_released_{suffix}",
            event_total(("recovery",), currency),
        )
        setattr(
            flows,
            f"export_receivable_balance_{suffix}",
            float(sum(lot.gross for lot in book if lot.currency == currency)),
        )
        setattr(
            flows,
            f"export_receivable_overdue_{suffix}",
            float(
                sum(
                    lot.gross
                    for lot in book
                    if lot.currency == currency and lot.due_tick < current_tick
                )
            ),
        )

    transaction_id = int(transaction_base)
    for event in applied:
        for kind, legs in _receivable_journal_legs(state, event):
            finance.append_transaction(
                flows,
                transaction_id=transaction_id,
                kind=kind,
                legs=legs,
                event_id=event.event_id,
            )
            transaction_id += 1
