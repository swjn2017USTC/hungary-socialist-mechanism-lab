"""Compact Toy-4 output tables: region/national aggregates, budgets, events.

Five tables only (aggregates, national_accounts, household_budgets,
tick_diagnostics, events), all Parquet + DuckDB. No household or organization
per-tick micro panel is ever written - the O(T*R*G) compact rows are the whole
trajectory record.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

from hsm_lab.contract.schemas import Toy4Parameters
from hsm_lab.engine.state import TickFlows, Toy4History, Toy4State
from hsm_lab.provenance.manifest import canonical_json
from hsm_lab.storage.output import write_duckdb

AGGREGATE_COLUMNS = [
    "tick",
    "quarter",
    "region_id",
    "commodity_id",
    "production_target",
    "production",
    "production_shortfall",
    "desired_input",
    "ordered_input",
    "allocated_input",
    "delivered_input",
    "available_input",
    "used_input",
    "input_unmet",
    "organization_input_open",
    "organization_input_close",
    "retail_open",
    "retail_planned",
    "retail_incoming",
    "retail_available",
    "retail_sales",
    "retail_close",
    "household_desired",
    "household_affordable",
    "household_realized",
    "budget_unmet",
    "availability_unmet",
    "total_unmet",
    "availability_shortage_rate",
    "total_unmet_rate",
]

NATIONAL_COLUMNS = [
    "tick",
    "quarter",
    "commodity_id",
    "imports",
    "export_desired",
    "export_realized",
    "export_unmet",
    "production",
    "used_input",
    "household_consumption",
    "wholesale_open",
    "wholesale_close",
    "organization_input_open",
    "organization_input_close",
    "retail_open",
    "retail_close",
    "total_stock_open",
    "total_stock_close",
    "material_balance_residual",
    "material_balance_tolerance_ratio",
]

BUDGET_COLUMNS = [
    "tick",
    "quarter",
    "region_id",
    "household_count",
    "weight_sum",
    "equivalent_persons",
    "income",
    "spending",
    "voluntary_saving",
    "forced_saving",
    "cash_open",
    "cash_close",
    "cash_balance_residual",
    "cash_balance_tolerance_ratio",
]


def _org_region_sums(state: Toy4State, values: np.ndarray) -> np.ndarray:
    regions = state.retail_inventory.shape[0]
    commodities = values.shape[1]
    out = np.zeros((regions, commodities))
    for commodity in range(commodities):
        out[:, commodity] = np.bincount(
            state.organization_region,
            weights=values[:, commodity],
            minlength=regions,
        )
    return out


def _household_region_sums(state: Toy4State, values: np.ndarray) -> np.ndarray:
    regions = state.retail_inventory.shape[0]
    commodities = values.shape[1]
    out = np.zeros((regions, commodities))
    for commodity in range(commodities):
        out[:, commodity] = np.bincount(
            state.household_region,
            weights=state.household_weight * values[:, commodity],
            minlength=regions,
        )
    return out

DIAGNOSTIC_COLUMNS = [
    "tick",
    "quarter",
    "digest",
    "max_material_abs_residual",
    "max_material_tolerance_ratio",
    "max_cash_abs_residual",
    "max_cash_tolerance_ratio",
]

EVENT_COLUMNS = ["tick", "quarter", "event_type", "details_json"]

TOY4_TICK_EVENT = "toy4_tick_completed"


def _rate(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator > 0 else 0.0



def append_compact_rows(
    history: Toy4History,
    state: Toy4State,
    flows: TickFlows,
    parameters: Toy4Parameters,
    *,
    region_ids: list[str],
    commodity_ids: list[str],
    digest: str,
    invariant_summary: dict[str, float],
) -> None:
    """Append one completed tick's compact rows to the history buffers."""
    regions = len(region_ids)
    commodities = len(commodity_ids)

    target_by_commodity = state.organization_output_mix * flows.organization_target[:, None]
    shortfall_by_commodity = (
        state.organization_output_mix * flows.organization_output_shortfall[:, None]
    )
    org_sums = {
        "production_target": _org_region_sums(state, target_by_commodity),
        "production": _org_region_sums(state, flows.organization_output),
        "production_shortfall": _org_region_sums(state, shortfall_by_commodity),
        "desired_input": _org_region_sums(state, flows.desired_input),
        "ordered_input": _org_region_sums(state, flows.ordered_input),
        "allocated_input": _org_region_sums(state, flows.allocated_input),
        "delivered_input": _org_region_sums(state, flows.delivered_input),
        "available_input": _org_region_sums(state, flows.available_input),
        "used_input": _org_region_sums(state, flows.used_input),
        "input_unmet": _org_region_sums(state, flows.input_unmet),
        "organization_input_open": _org_region_sums(state, flows.organization_input_open),
        "organization_input_close": _org_region_sums(state, flows.organization_input_close),
    }
    hh_sums = {
        "household_desired": _household_region_sums(state, flows.household_desired),
        "household_affordable": _household_region_sums(state, flows.household_affordable),
        "household_realized": _household_region_sums(state, flows.household_realized),
        "budget_unmet": _household_region_sums(state, flows.budget_unmet),
        "availability_unmet": _household_region_sums(state, flows.availability_unmet),
        "total_unmet": _household_region_sums(state, flows.total_unmet),
    }

    for region in range(regions):
        for commodity in range(commodities):
            affordable = hh_sums["household_affordable"][region, commodity]
            desired = hh_sums["household_desired"][region, commodity]
            history.aggregate_rows.append(
                {
                    "tick": flows.tick,
                    "quarter": flows.quarter,
                    "region_id": region_ids[region],
                    "commodity_id": commodity_ids[commodity],
                    **{
                        name: float(table[region, commodity])
                        for name, table in org_sums.items()
                    },
                    "retail_open": float(flows.retail_open[region, commodity]),
                    "retail_planned": float(flows.retail_planned[region, commodity]),
                    "retail_incoming": float(flows.retail_incoming[region, commodity]),
                    "retail_available": float(flows.retail_available[region, commodity]),
                    "retail_sales": float(flows.retail_sales[region, commodity]),
                    "retail_close": float(flows.retail_close[region, commodity]),
                    **{
                        name: float(table[region, commodity])
                        for name, table in hh_sums.items()
                    },
                    "availability_shortage_rate": float(
                        _rate(
                            hh_sums["availability_unmet"][region, commodity], affordable
                        )
                    ),
                    "total_unmet_rate": float(_rate(
                        hh_sums["total_unmet"][region, commodity], desired
                    )),
                }
            )

    total_stock_open = (
        flows.wholesale_open
        + flows.organization_input_open.sum(axis=0)
        + flows.retail_open.sum(axis=0)
    )
    total_stock_close = (
        flows.wholesale_close
        + flows.organization_input_close.sum(axis=0)
        + flows.retail_close.sum(axis=0)
    )
    for commodity in range(commodities):
        tolerance = float(flows.material_balance_tolerance[commodity])
        residual = float(flows.material_balance_residual[commodity])
        history.national_rows.append(
            {
                "tick": flows.tick,
                "quarter": flows.quarter,
                "commodity_id": commodity_ids[commodity],
                "imports": float(flows.imports[commodity]),
                "export_desired": float(flows.export_desired[commodity]),
                "export_realized": float(flows.export_realized[commodity]),
                "export_unmet": float(flows.export_unmet[commodity]),
                "production": float(flows.organization_output[:, commodity].sum()),
                "used_input": float(flows.used_input[:, commodity].sum()),
                "household_consumption": float(flows.retail_sales[:, commodity].sum()),
                "wholesale_open": float(flows.wholesale_open[commodity]),
                "wholesale_close": float(flows.wholesale_close[commodity]),
                "organization_input_open": float(
                    flows.organization_input_open[:, commodity].sum()
                ),
                "organization_input_close": float(
                    flows.organization_input_close[:, commodity].sum()
                ),
                "retail_open": float(flows.retail_open[:, commodity].sum()),
                "retail_close": float(flows.retail_close[:, commodity].sum()),
                "total_stock_open": float(total_stock_open[commodity]),
                "total_stock_close": float(total_stock_close[commodity]),
                "material_balance_residual": residual,
                "material_balance_tolerance_ratio": float(
                    abs(residual) / tolerance if tolerance > 0 else 0.0
                ),
            }
        )

    weight = state.household_weight
    for region in range(regions):
        mask = state.household_region == region
        w = weight[mask]
        tolerance = float(flows.cash_balance_tolerance[region])
        residual = float(flows.cash_balance_residual[region])
        history.budget_rows.append(
            {
                "tick": flows.tick,
                "quarter": flows.quarter,
                "region_id": region_ids[region],
                "household_count": int(mask.sum()),
                "weight_sum": float(w.sum()),
                "equivalent_persons": float(
                    (w * state.household_size[mask]).sum()
                ),
                "income": float((w * flows.household_income[mask]).sum()),
                "spending": float((w * flows.household_spending[mask]).sum()),
                "voluntary_saving": float((w * flows.voluntary_saving[mask]).sum()),
                "forced_saving": float((w * flows.forced_saving[mask]).sum()),
                "cash_open": float((w * flows.household_cash_open[mask]).sum()),
                "cash_close": float((w * flows.household_cash_close[mask]).sum()),
                "cash_balance_residual": residual,
                "cash_balance_tolerance_ratio": float(
                    abs(residual) / tolerance if tolerance > 0 else 0.0
                ),
            }
        )

    history.diagnostic_rows.append(
        {
            "tick": flows.tick,
            "quarter": flows.quarter,
            "digest": digest,
            **{name: float(value) for name, value in invariant_summary.items()},
        }
    )
    details = {
        "digest": digest,
        **{name: float(value) for name, value in invariant_summary.items()},
    }
    history.event_rows.append(
        {
            "tick": flows.tick,
            "quarter": flows.quarter,
            "event_type": TOY4_TICK_EVENT,
            "details_json": canonical_json(details).decode("utf-8"),
        }
    )


def _cast_frame(rows: list[dict[str, object]], columns: list[str]) -> pl.DataFrame:
    frame = pl.DataFrame(rows)
    return frame.select(columns).cast(
        {
            name: pl.Int64
            for name in columns
            if name in ("tick", "household_count")
        }
    )


def history_frames(history: Toy4History) -> dict[str, pl.DataFrame]:
    """Build the five compact frames from the accumulated history rows."""
    return {
        "aggregates": _cast_frame(history.aggregate_rows, AGGREGATE_COLUMNS),
        "national_accounts": _cast_frame(history.national_rows, NATIONAL_COLUMNS),
        "household_budgets": _cast_frame(history.budget_rows, BUDGET_COLUMNS),
        "tick_diagnostics": _cast_frame(history.diagnostic_rows, DIAGNOSTIC_COLUMNS),
        "events": _cast_frame(history.event_rows, EVENT_COLUMNS),
    }


def write_toy4_tables(
    output_dir: Path, frames: dict[str, pl.DataFrame]
) -> dict[str, Path]:
    """Write all compact Parquet files and the DuckDB trajectory file."""
    paths: dict[str, Path] = {}
    for name, frame in frames.items():
        path = output_dir / f"{name}.parquet"
        frame.write_parquet(path)
        paths[name] = path
    write_duckdb(output_dir, frames)
    return paths
