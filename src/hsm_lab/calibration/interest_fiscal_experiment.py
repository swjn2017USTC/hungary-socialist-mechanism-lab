"""Reproduce the pre-registered P05 interest/fiscal arms and compact metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from hsm_lab.calibration.leak_audit import run_leak_audit
from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.data.registry import DataRegistry

ARMS: dict[str, dict[str, float | str]] = {
    "B0": {},
    "I1": {"interest_sink_remittance_fraction": 0.5},
    "I2": {"interest_sink_remittance_fraction": 1.0},
    "I3": {
        "interest_sink_remittance_fraction": 1.0,
        "interest_sink_recipient": "households",
    },
    "F1": {"fiscal_turnover_remittance_fraction": 0.02},
    "C1": {
        "interest_sink_remittance_fraction": 1.0,
        "interest_sink_recipient": "treasury",
        "fiscal_turnover_remittance_fraction": 0.02,
    },
    "N1": {"credit_envelope_fraction": 1.0},
}
SERVICE_IDS = {
    "g03": "g03_electricity_heat",
    "g15": "g15_market_services",
    "g16": "g16_housing_public_services",
}


def _sum_at(frame: pl.DataFrame, column: str, tick: int) -> float:
    selected = frame.filter(pl.col("tick") == tick)
    return float(selected[column].sum()) if selected.height else 0.0


def summarize_arm(
    output_dir: Path, audit: dict[str, Any], *, baseline_consumption: float | None = None
) -> dict[str, Any]:
    """Read one run and its circuit sidecars into the registered gate/metric row."""
    national = pl.read_parquet(output_dir / "national_accounts.parquet")
    aggregates = pl.read_parquet(output_dir / "aggregates.parquet")
    diagnostics = pl.read_parquet(output_dir / "tick_diagnostics.parquet")
    financial = pl.read_parquet(output_dir / "financial_accounts.parquet")
    organizations = pl.read_parquet(output_dir / "organization_diagnostics.parquet")
    circuit = pl.read_parquet(output_dir / "commodity_circuit.parquet")
    money = pl.read_parquet(output_dir / "money_stock.parquet").sort("tick")
    sector = pl.read_parquet(output_dir / "sector_circuit.parquet")

    per_tick = national.group_by("tick").agg(pl.col("production").sum()).sort("tick")
    production = per_tick["production"].to_numpy().astype(np.float64)
    first10 = float(production[:10].mean()) if production.size >= 10 else 0.0
    last10 = float(production[-10:].mean()) if production.size >= 10 else 0.0
    liveness = last10 / first10 if first10 > 0.0 else 0.0
    household = (
        national.group_by("tick")
        .agg(pl.col("household_consumption").sum())
        .sort("tick")["household_consumption"]
        .to_numpy()
        .astype(np.float64)
    )
    household_last = float(household[-10:].mean()) if household.size >= 10 else 0.0

    service_ratios: dict[str, float | None] = {}
    expiry_ratios: dict[str, float | None] = {}
    for short, commodity in SERVICE_IDS.items():
        rows = circuit.filter(pl.col("commodity_id") == commodity)
        funded = float(rows["household_funded"].sum())
        realized = float(rows["household_realized"].sum())
        service_ratios[short] = realized / funded if funded > 0.0 else None
        denominator = float(rows["stock_open"].sum() + rows["production"].sum())
        expiry_ratios[short] = (
            float(rows["expired"].sum() / denominator) if denominator > 0 else None
        )

    treasury = financial.filter(pl.col("account_label") == "treasury_cash").sort("tick")
    zero_rows = treasury.filter(pl.col("closing") <= 1e-9)
    zero_tick = int(zero_rows["tick"][0]) if zero_rows.height else None
    treasury_tick115 = _sum_at(treasury, "closing", 115)
    treasury_solvent_115 = treasury_tick115 >= -1e-9
    rescue_grants_last20 = float(
        treasury.filter(pl.col("tick") >= 96)["grant"].fill_null(0.0).abs().sum()
    )
    terminal_t3 = treasury_solvent_115 or rescue_grants_last20 <= 1e-9
    max_expiry = max((v for v in expiry_ratios.values() if v is not None), default=None)
    service_gate = all(v is not None and v >= 0.9 for v in service_ratios.values())
    accounting_pass = (
        audit["completed_ticks"] == 116
        and float(diagnostics["max_finance_tolerance_ratio"].max()) <= 1.0
        and float(diagnostics["max_material_tolerance_ratio"].max()) <= 1.0
        and float(audit["max_money_flow_residual"]) < 1e-6
    )
    frozen_gates = {
        "liveness": liveness >= 0.8,
        "service_delivery_funded": service_gate,
        "treasury_self_financing": zero_tick is None,
        "per_commodity_expiry": max_expiry is not None and max_expiry <= 0.20,
        "accounting_invariants": accounting_pass,
    }

    total_allocated = float(aggregates["allocated"].sum())
    physical_blocked = float(aggregates["physical_delivery_blocked"].sum())
    money_final = money.filter(pl.col("tick") == 115)
    sector_transport = sector.filter(pl.col("organization_type") == "transport")
    transport_target = float(sector_transport["target"].sum())
    transport_realized = float(sector_transport["realized"].sum())
    freight_need = float(money["freight_service_need"].sum())
    logistics_pool = float(money["transport_logistics_pool"].sum())
    wage_final = organizations.filter(pl.col("tick") == 115)
    guardrails = {
        "terminal_consumption_not_below_B0": (
            None
            if baseline_consumption is None
            else household_last >= baseline_consumption - 1e-9
        ),
        "household_availability_unmet_not_above_B0": None,
    }
    availability_unmet = float(aggregates["household_availability_unmet"].sum())
    return {
        "status": "measured",
        "arm": output_dir.name,
        "parameter_overrides": ARMS.get(output_dir.name, {}),
        "ticks": int(audit["completed_ticks"]),
        "deterministic_replay_digest": audit["deterministic_replay_digest"],
        "parameter_hash": json.loads((output_dir / "manifest.json").read_text())["parameter_hash"],
        "frozen_gates": frozen_gates,
        "frozen_gates_pass": all(frozen_gates.values()),
        "liveness": liveness,
        "production_first_10": first10,
        "production_last_10": last10,
        "household_consumption_last_10": household_last,
        "service_realized_funded": service_ratios,
        "treasury_zero_tick": zero_tick,
        "treasury_cash_tick_115": treasury_tick115,
        "rescue_grants_total": float(money["bailout_grants"].sum()),
        "rescue_grants_last_20": rescue_grants_last20,
        "expiry_fraction": expiry_ratios,
        "expiry_fraction_max": max_expiry,
        "physical_blocked_share": physical_blocked / total_allocated if total_allocated else 0.0,
        "accounting_max_finance_tolerance_ratio": float(
            diagnostics["max_finance_tolerance_ratio"].max()
        ),
        "accounting_max_material_tolerance_ratio": float(
            diagnostics["max_material_tolerance_ratio"].max()
        ),
        "max_money_flow_residual": float(audit["max_money_flow_residual"]),
        "treasury_solvent_tick115": treasury_solvent_115,
        "terminal_T1_pass": last10 >= 35092.0,
        "terminal_T2_pass": household_last >= 2085.0,
        "terminal_T3_pass": terminal_t3,
        "terminal_floor_pass": last10 >= 35092.0 and household_last >= 2085.0 and terminal_t3,
        "interest_paid": float(money["interest_paid"].sum()),
        "interest_destroyed": float(money["interest_destroyed"].sum()),
        "interest_remitted": float(money["interest_remitted"].sum()),
        "fiscal_turnover_remitted": float(money["fiscal_turnover_remitted"].sum()),
        "money_stock_open": float(money["money_total_open"][0]),
        "money_stock_close": float(money["money_total_close"][money.height - 1]),
        "household_cash_close": float(money_final["household_cash_close"].sum()),
        "bank_equity_close": float(money_final["bank_equity_close"].sum()),
        "wage_arrears_final": float(wage_final["wage_arrears_sum"].sum()),
        "interest_arrears_final": float(wage_final["interest_arrears_sum"].sum()),
        "household_spending": float(money["household_spending"].sum()),
        "household_availability_unmet": availability_unmet,
        "transport_target": transport_target,
        "transport_realized": transport_realized,
        "delivered_total": float(aggregates["delivered"].sum()),
        "freight_service_need": freight_need,
        "transport_logistics_pool": logistics_pool,
        "transport_pool_to_freight_need": logistics_pool / freight_need if freight_need else None,
        "guardrails": guardrails,
        "output_dir": str(output_dir),
    }


def run_interest_fiscal_arms(root: Path, output_root: Path) -> dict[str, Any]:
    """Run B0/I1-I3/F1/C1/N1 once each, bounded to the frozen 116-tick horizon."""
    root = root.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        allowed = set(ARMS) | {"arm_metrics.json"}
        unexpected = {path.name for path in output_root.iterdir()} - allowed
        if unexpected:
            raise FileExistsError(
                "refusing to reuse experiment directory with unrecognized entries: "
                f"{sorted(unexpected)}"
            )
    else:
        output_root.mkdir(parents=True)
    contract = load_research_contract(root)
    baseline = load_scenario(root, "historical_f2_replay")
    registry = DataRegistry.load(root, allowed_commodities=baseline.commodities)
    preliminary: list[tuple[str, dict[str, Any]]] = []
    rejected: list[dict[str, Any]] = []
    for arm, overrides in ARMS.items():
        target = output_root / arm
        if target.exists():
            manifest_path = target / "manifest.json"
            if not manifest_path.exists():
                raise FileExistsError(f"incomplete unrecognized arm directory: {target}")
            manifest = json.loads(manifest_path.read_text())
            audit_path = target / "leak_audit.json"
            if manifest.get("status") == "completed" and audit_path.exists():
                preliminary.append((arm, json.loads(audit_path.read_text())))
                continue
            rejected.append(
                {
                    "status": "rejected_accounting_residual",
                    "arm": arm,
                    "parameter_overrides": overrides,
                    "completed_ticks": int(manifest.get("completed_ticks", 0)),
                    "last_completed_quarter": manifest.get("last_completed_quarter"),
                    "deterministic_replay_digest": manifest.get("deterministic_replay_digest"),
                    "failure_message": manifest.get("failure_message"),
                    "output_dir": str(target),
                }
            )
            continue
        scenario = baseline.model_copy(
            update={
                "material_parameters": baseline.material_parameters.model_copy(
                    update=overrides
                )
            }
        )
        try:
            audit = run_leak_audit(scenario, contract, registry, output_dir=target)
        except (RuntimeError, ValueError) as exc:
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
            rejected.append(
                {
                    "status": "rejected_accounting_residual",
                    "arm": arm,
                    "parameter_overrides": overrides,
                    "completed_ticks": int(manifest.get("completed_ticks", 0)),
                    "last_completed_quarter": manifest.get("last_completed_quarter"),
                    "deterministic_replay_digest": manifest.get("deterministic_replay_digest"),
                    "failure_message": str(exc),
                    "output_dir": str(target),
                }
            )
            continue
        if audit["completed_ticks"] != 116:
            raise RuntimeError(f"{arm} stopped at {audit['completed_ticks']} ticks, expected 116")
        preliminary.append((arm, audit))

    if not any(arm == "B0" for arm, _ in preliminary):
        raise RuntimeError("the B0 control failed; no arm results can be compared")
    b0 = output_root / "B0"
    b0_national = pl.read_parquet(b0 / "national_accounts.parquet")
    b0_household = (
        b0_national.group_by("tick")
        .agg(pl.col("household_consumption").sum())
        .sort("tick")["household_consumption"]
        .to_numpy()
    )
    baseline_consumption = float(b0_household[-10:].mean())
    b0_unmet = float(
        pl.read_parquet(b0 / "aggregates.parquet")["household_availability_unmet"].sum()
    )
    arms = list(rejected)
    for arm, audit in preliminary:
        row = summarize_arm(
            output_root / arm,
            audit,
            baseline_consumption=baseline_consumption,
        )
        row["guardrails"]["household_availability_unmet_not_above_B0"] = (
            row["household_availability_unmet"] <= b0_unmet + 1e-9
        )
        arms.append(row)
    payload = {
        "status": "measured",
        "inference_status": "NOT_RUN",
        "scenario_id": baseline.scenario_id,
        "completed_ticks": 116,
        "last_completed_quarter": "1985Q4",
        "arms": arms,
        "output_root": str(output_root),
        "note": "synthetic model experiment only; no calibration or validation claim",
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    (output_root / "arm_metrics.json").write_text(serialized)
    return payload
