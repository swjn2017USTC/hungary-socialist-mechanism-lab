"""Read-only P05 circuit observations; no parameters or canonical fields change.

The scoped observer calls the unmodified tick exactly once, takes deep opening
snapshots, and writes sidecars after the normal runner has finished. Deposits
already include the credit fund: money_total must not count that pool twice.
The model has no currency-in-circulation state (structural zero).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import polars as pl

from hsm_lab.calibration.axis_sweep import _gate_metrics
from hsm_lab.contract.material import ORGANIZATION_TYPE_ORDER
from hsm_lab.engine import accounting, material
from hsm_lab.engine.finance import (
    DOMESTIC_CURRENCY,
    AccountKind,
    household_account_ids,
    treasury_account_id,
)
from hsm_lab.engine.state import build_material_prices, capture_material_stocks


def money_snapshot(state: Any) -> dict[str, float]:
    """Disjoint deposit owners and their matching bank liabilities."""
    household = float(np.dot(state.household_weight, state.household_cash))
    organization = float(np.asarray(state.organization_cash)[state.organization_bank >= 0].sum())
    deposits = float(np.asarray(state.bank_deposit_liability).sum())
    treasury = float(state.treasury_deposit)
    fund = float(state.credit_fund)
    return {
        "currency_in_circulation": 0.0,
        "household_cash": household,
        "organization_cash": organization,
        "treasury_cash": treasury,
        "credit_fund": fund,
        "deposit_liabilities": deposits,
        "money_total": deposits,
        "deposit_composition_residual": deposits - household - organization - treasury - fund,
        "bank_reserves": float(np.asarray(state.bank_reserves).sum()),
        "bank_equity": float(np.asarray(state.bank_equity).sum()),
        "bank_loan_asset": float(np.asarray(state.bank_loan_asset).sum()),
        "principal": float(np.asarray(state.organization_principal).sum()),
        "wage_arrears": float(np.asarray(state.organization_wage_arrears).sum()),
    }


def money_flow_residual(
    opening: float,
    closing: float,
    drawn: float,
    repaid: float,
    interest: float,
    *,
    neutral: bool,
    remitted: float = 0.0,
) -> float:
    """Credit creates/destroys deposits only on the non-neutral branch."""
    destroyed = float(interest) - float(remitted)
    return closing - opening - (0.0 if neutral else drawn - repaid) + destroyed


class CircuitObserver:
    """Compact, detached observations of the authoritative tick state/flows."""

    def __init__(self) -> None:
        self.money: list[dict[str, Any]] = []
        self.commodities: list[dict[str, Any]] = []
        self.banks: list[dict[str, Any]] = []
        self.sectors: list[dict[str, Any]] = []
        self.services: list[dict[str, Any]] = []
        self.journal: list[dict[str, Any]] = []

    def observe(
        self,
        opening: Any,
        before: dict[str, float],
        state: Any,
        flows: Any,
        parameters: Any,
        network: Any,
    ) -> None:
        keys = {"tick": int(flows.tick), "quarter": str(flows.quarter)}
        weight = np.asarray(state.household_weight, dtype=np.float64)

        def hh(name: str) -> float:
            return float(np.dot(weight, np.asarray(getattr(flows, name), dtype=np.float64)))

        def org(name: str) -> float:
            return float(np.asarray(getattr(flows, name), dtype=np.float64).sum())

        after = money_snapshot(state)
        money: dict[str, Any] = dict(keys)
        transport_code = next(
            i for i, organization_type in enumerate(ORGANIZATION_TYPE_ORDER)
            if organization_type.value == "transport"
        )
        transport_mask = np.asarray(state.organization_type) == transport_code
        transport_realized = float(
            np.asarray(flows.organization_realized, dtype=np.float64)[transport_mask].sum()
        )
        freight_need = float(
            np.sum(
                np.asarray(flows.edge_allocated, dtype=np.float64)
                * np.asarray(network.edge_transport_per_unit, dtype=np.float64)
            )
        )
        money.update(
            {
                "transport_target": float(
                    np.asarray(flows.organization_target, dtype=np.float64)[transport_mask].sum()
                ),
                "transport_realized": transport_realized,
                "transport_logistics_pool": transport_realized
                * float(parameters.service_split[0]),
                "freight_service_need": freight_need,
                "delivered_total": float(np.asarray(flows.delivered, dtype=np.float64).sum()),
                "physical_blocked_total": float(
                    np.asarray(flows.physical_delivery_blocked, dtype=np.float64).sum()
                ),
            }
        )
        for name in before:
            money[f"{name}_open"] = before[name]
            money[f"{name}_close"] = after[name]
        drawn = org("organization_credit_drawn")
        repaid = org("organization_principal_paid")
        interest = org("organization_interest_paid")
        journal_kind = np.asarray(flows.journal_kind, dtype=object)
        journal_amount = np.asarray(flows.journal_amount, dtype=np.float64)
        journal_debit = np.asarray(flows.journal_debit, dtype=np.int64)
        household_cash_ids = household_account_ids(state, AccountKind.CASH_DEPOSIT)
        treasury_cash_id = treasury_account_id(state, AccountKind.CASH_DEPOSIT)
        recipient_accounts = np.append(household_cash_ids, treasury_cash_id)
        interest_remitted = float(
            journal_amount[
                (journal_kind == "interest_recipient_deposit")
                & np.isin(journal_debit, recipient_accounts)
            ].sum()
        )
        fiscal_remitted = float(
            journal_amount[
                (journal_kind == "fiscal_turnover_remittance")
                & (journal_debit == treasury_cash_id)
            ].sum()
        )
        money.update(
            {
                "credit_drawn": drawn,
                "principal_repaid": repaid,
                "interest_accrued": org("organization_interest_due"),
                "interest_paid": interest,
                "interest_destroyed": interest - interest_remitted,
                "interest_remitted": interest_remitted,
                "fiscal_turnover_remitted": fiscal_remitted,
                "money_flow_residual": money_flow_residual(
                    before["money_total"],
                    after["money_total"],
                    drawn,
                    repaid,
                    interest,
                    neutral=bool(parameters.m2_neutral_credit),
                    remitted=interest_remitted,
                ),
                "wages_due": org("organization_wage_due"),
                "wages_paid": org("organization_wage_paid"),
                "pre_purchase_wages": hh("household_wage_income"),
                "late_wages": hh("household_late_wage"),
                "plot_formal_income": hh("household_plot_income_formal"),
                "plot_direct_income": hh("household_plot_income_direct"),
                "second_direct_income": hh("household_second_income_direct"),
                "plot_input_funding": hh("household_plot_input_funding"),
                "second_input_funding": hh("household_second_input_funding"),
                "household_spending": hh("household_spending"),
                "household_budget": hh("household_budget_available"),
                "voluntary_saving": hh("household_voluntary_saving"),
                "forced_saving": hh("household_forced_saving"),
                "savings_draw": hh("household_savings_draw"),
                "deferred_close": float(np.dot(weight, state.household_deferred_receipt)),
                "seller_receipts": org("organization_sales_receipts"),
                "organization_purchases": org("organization_purchases"),
                "bailout_grants": org("organization_bailout_granted"),
            }
        )
        hh_expected_change = (
            money["pre_purchase_wages"]
            + money["late_wages"]
            + money["plot_formal_income"]
            + money["plot_direct_income"]
            + money["second_direct_income"]
            - money["plot_input_funding"]
            - money["second_input_funding"]
            - money["household_spending"]
        )
        money["household_cash_residual"] = (
            after["household_cash"] - before["household_cash"] - hh_expected_change
        )
        kind = np.asarray(flows.journal_kind, dtype=object)
        currency = np.asarray(flows.journal_currency, dtype=object)
        debit = np.asarray(flows.journal_debit, dtype=np.int64)
        credit = np.asarray(flows.journal_credit, dtype=np.int64)
        amount = np.asarray(flows.journal_amount, dtype=np.float64)
        treasury_id = treasury_account_id(state, AccountKind.CASH_DEPOSIT)
        goods = (kind == "goods_payment") & (currency == DOMESTIC_CURRENCY)
        treasury_in = float(amount[goods & (credit == treasury_id)].sum())
        treasury_out = float(amount[goods & (debit == treasury_id)].sum())
        money["treasury_goods_inflow"] = treasury_in
        money["treasury_goods_outflow"] = treasury_out
        money["treasury_cash_residual"] = (
            after["treasury_cash"]
            - before["treasury_cash"]
            - treasury_in
            + treasury_out
            + money["bailout_grants"]
        )
        self.money.append(money)
        # Leg totals are labelled explicitly: paired accounting legs and
        # settlement legs are not additional cash transfers.
        for label in sorted(set(flows.journal_kind)):
            selected = (kind == label) & (currency == DOMESTIC_CURRENCY)
            self.journal.append(
                {
                    **keys,
                    "kind": label,
                    "currency": DOMESTIC_CURRENCY,
                    "leg_count": int(selected.sum()),
                    "leg_amount_sum": float(amount[selected].sum()),
                }
            )

        prices = build_material_prices(parameters)
        continuity = accounting._reconstruct(opening, state, flows, network, prices, parameters)
        cell_g = np.asarray(network.cell_commodity, dtype=np.int64)
        values = {
            "stock_open": opening.stock_value,
            "production": continuity.production,
            "imports": continuity.imports_in,
            "internal_in": continuity.edge_receipts,
            "internal_out": continuity.edge_out_internal,
            "production_input_used": continuity.production_used,
            "logistics_used": continuity.logistics_used,
            "investment_installed": continuity.project_installed,
            "household_boundary": continuity.household_edges_out,
            "plot_boundary": continuity.household_channel,
            "exports": continuity.exports_out,
            "housing": continuity.housing_out,
            "second_input_used": flows.second_input_used,
            "pool_draw": flows.service_pool_draw_at_cell,
            "pool_credit": flows.service_pool_credit_at_cell,
            "expired": continuity.services_leftover,
            "stock_close": state.stock_value,
        }
        household_catalog = network.household_catalog
        parent = np.asarray(household_catalog.to_material, dtype=np.float64)
        funded = (weight @ np.asarray(flows.household_affordable_h)) @ parent
        realized = (weight @ np.asarray(flows.household_realized_h)) @ parent
        cell_prices = material._cell_price_vector(parameters, network)
        output_cells = np.asarray(network.org_output_cell, dtype=np.int64)
        output_g = np.full(output_cells.shape, -1, dtype=np.int64)
        valid_output = output_cells >= 0
        output_g[valid_output] = cell_g[output_cells[valid_output]]
        for g, commodity in enumerate(network.commodity_ids):
            mask = cell_g == g
            row = {
                **keys,
                "commodity_id": commodity,
                **{name: float(np.asarray(value)[mask].sum()) for name, value in values.items()},
                "household_funded": float(funded[g]),
                "household_realized": float(realized[g]),
            }
            row["balance_residual"] = (
                row["stock_open"]
                + row["production"]
                + row["imports"]
                + row["internal_in"]
                - row["internal_out"]
                - row["production_input_used"]
                - row["logistics_used"]
                - row["investment_installed"]
                - row["household_boundary"]
                - row["plot_boundary"]
                - row["exports"]
                - row["housing"]
                - row["second_input_used"]
                + row["pool_draw"]
                - row["pool_credit"]
                - row["expired"]
                - row["stock_close"]
            )
            row["stock_value_open"] = float(np.dot(opening.stock_value[mask], cell_prices[mask]))
            row["stock_value_close"] = float(np.dot(state.stock_value[mask], cell_prices[mask]))
            row["expired_at_producer_prices"] = float(
                np.dot(continuity.services_leftover[mask], cell_prices[mask])
            )
            self.commodities.append(row)
            if bool(continuity.services_cells[mask].any()):
                producers = output_g == g
                self.services.append(
                    {
                        **keys,
                        "commodity_id": commodity,
                        "expired": row["expired"],
                        "production": row["production"],
                        "expired_at_producer_prices": row["expired_at_producer_prices"],
                        "producer_receipts": float(
                            flows.organization_sales_receipts[producers].sum()
                        ),
                        "producer_wages_paid": float(flows.organization_wage_paid[producers].sum()),
                        "producer_cash_close": float(state.organization_cash[producers].sum()),
                    }
                )
        for bank in range(state.bank_reserves.size):
            row = {**keys, "bank": bank}
            for name in (
                "bank_reserves",
                "bank_deposit_liability",
                "bank_loan_asset",
                "bank_interest_receivable",
                "bank_equity",
            ):
                row[f"{name}_open"] = float(getattr(opening, name)[bank])
                row[f"{name}_close"] = float(getattr(state, name)[bank])
            self.banks.append(row)
        for code, organization_type in enumerate(ORGANIZATION_TYPE_ORDER):
            mask = state.organization_type == code
            row = {
                **keys,
                "organization_type": str(organization_type.value),
                "cash_open": float(opening.organization_cash[mask].sum()),
                "cash_close": float(state.organization_cash[mask].sum()),
            }
            for name in (
                "wage_due",
                "wage_paid",
                "credit_drawn",
                "principal_paid",
                "interest_paid",
                "sales_receipts",
                "purchases",
                "target",
                "realized",
            ):
                row[name] = float(np.asarray(getattr(flows, f"organization_{name}"))[mask].sum())
            self.sectors.append(row)

    def write(self, output_dir: Path) -> dict[str, str]:
        paths = {}
        for table, rows in (
            ("money_stock", self.money),
            ("commodity_circuit", self.commodities),
            ("bank_circuit", self.banks),
            ("sector_circuit", self.sectors),
            ("service_expiry", self.services),
            ("journal_totals", self.journal),
        ):
            path = output_dir / f"{table}.parquet"
            pl.DataFrame(rows).write_parquet(path)
            paths[table] = str(path)
        return paths


def run_leak_audit(
    spec: Any, contract: Any, registry: Any, *, output_dir: Path, until: str | None = None
) -> dict[str, Any]:
    """Run the unchanged material kernel with a scoped, read-only observer."""
    if spec.kind != "material" or spec.ticks > 116:
        raise ValueError("leak audit requires a material scenario of at most 116 ticks")
    observer = CircuitObserver()
    original = material.tick_material

    def observed(state: Any, forcing: Any, parameters: Any, network: Any, **kwargs: Any) -> Any:
        opening = capture_material_stocks(state)
        before = money_snapshot(state)
        flows = original(state, forcing, parameters, network, **kwargs)
        observer.observe(opening, before, state, flows, parameters, network)
        return flows

    with patch.object(material, "tick_material", observed):
        manifest = material.run_material(spec, output_dir, contract, registry, until=until)
    if manifest.status not in ("completed", "paused"):
        raise RuntimeError(f"audit run failed: {manifest.failure_message}")
    paths = observer.write(output_dir)
    money = pl.DataFrame(observer.money)
    circuit = pl.DataFrame(observer.commodities)
    diagnostic = pl.read_parquet(output_dir / "tick_diagnostics.parquet")
    expiry = circuit.group_by("tick").agg(pl.col("expired").sum()).sort("tick")
    payload = {
        "status": "measured",
        "inference_status": "NOT_RUN",
        "scenario_id": spec.scenario_id,
        "completed_ticks": manifest.completed_ticks,
        "deterministic_replay_digest": manifest.deterministic_replay_digest,
        "rng_draws_count": manifest.rng_draws_count,
        "gate_metrics": _gate_metrics(output_dir),
        "sidecars": paths,
        "max_money_flow_residual": float(money["money_flow_residual"].abs().max()),
        "max_deposit_composition_residual": float(
            money["deposit_composition_residual_close"].abs().max()
        ),
        "max_household_cash_residual": float(money["household_cash_residual"].abs().max()),
        "max_treasury_cash_residual": float(money["treasury_cash_residual"].abs().max()),
        "max_commodity_balance_residual": float(circuit["balance_residual"].abs().max()),
        "max_expiry_reconciliation_residual": float(
            (expiry["expired"] - diagnostic.sort("tick")["expired_services"]).abs().max()
        ),
        "money_definition": "currency (structural zero) + deposit liabilities; fund included",
    }
    (output_dir / "leak_audit.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload
