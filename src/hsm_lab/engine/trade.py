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
)
from hsm_lab.engine.state import MaterialState, MaterialTickFlows

if TYPE_CHECKING:  # pragma: no cover - annotation-only; avoids an import cycle
    from hsm_lab.engine.network import MaterialNetwork

__all__ = [
    "build_export_demands",
    "channel_prices",
    "realize_external_debt_service",
    "realize_imports",
    "settle_exports_and_closing",
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
