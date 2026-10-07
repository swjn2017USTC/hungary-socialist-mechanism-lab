"""Toy-4 end-of-quarter checkpoints: atomic publish, strict resume gates.

Format ``toy4-checkpoint-v1``. A checkpoint is only ever written after a tick
has fully passed its accounting invariants (``completed_ticks`` boundary), and
is published atomically via a ``.tmp-<uuid>`` staging directory + ``os.replace``.
Resume verifies payload digests, versions, scenario identity, axes, RNG state
and the digest-chain boundary before any output directory is created.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

from hsm_lab.contract.guards import sha256_file
from hsm_lab.contract.schemas import (
    ResearchContract,
    ResearchGateError,
    ScenarioSpec,
)
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import (
    TOY4_STATE_VERSION,
    Toy4History,
    Toy4State,
)
from hsm_lab.storage.toy4_output import history_frames

CHECKPOINT_VERSION = "toy4-checkpoint-v1"
TOY4_ENGINE_VERSION = "toy4-engine-v1"

_STATE_ARRAY_FIELDS = (
    "household_id",
    "household_region",
    "household_weight",
    "household_size",
    "household_cash",
    "organization_id",
    "organization_region",
    "organization_output_sector",
    "organization_capacity",
    "organization_labor_capacity",
    "organization_input_coefficients",
    "organization_output_mix",
    "organization_input_inventory",
    "wholesale_inventory",
    "retail_inventory",
    "region_equivalent_persons",
    "regional_share",
)

_STATE_DTYPES: dict[str, np.dtype] = {
    "household_id": np.dtype("<i8"),
    "household_region": np.dtype("<i4"),
    "household_weight": np.dtype("<f8"),
    "household_size": np.dtype("<f8"),
    "household_cash": np.dtype("<f8"),
    "organization_id": np.dtype("<i8"),
    "organization_region": np.dtype("<i4"),
    "organization_output_sector": np.dtype("<i4"),
    "organization_capacity": np.dtype("<f8"),
    "organization_labor_capacity": np.dtype("<f8"),
    "organization_input_coefficients": np.dtype("<f8"),
    "organization_output_mix": np.dtype("<f8"),
    "organization_input_inventory": np.dtype("<f8"),
    "wholesale_inventory": np.dtype("<f8"),
    "retail_inventory": np.dtype("<f8"),
    "region_equivalent_persons": np.dtype("<f8"),
    "regional_share": np.dtype("<f8"),
}

_HISTORY_TABLES = (
    "aggregates",
    "national_accounts",
    "household_budgets",
    "tick_diagnostics",
    "events",
)


def state_arrays(state: Toy4State) -> dict[str, np.ndarray]:
    return {name: getattr(state, name) for name in _STATE_ARRAY_FIELDS}


def _state_from_arrays(
    arrays: dict[str, np.ndarray], completed_ticks: int
) -> Toy4State:
    return Toy4State(
        schema_version=TOY4_STATE_VERSION,
        completed_ticks=completed_ticks,
        **{name: arrays[name] for name in _STATE_ARRAY_FIELDS},
    )


def checkpoint_dir(run_dir: Path, completed_ticks: int) -> Path:
    return run_dir / "checkpoints" / f"tick-{completed_ticks:04d}"


def save_toy4_checkpoint(
    directory: Path,
    state: Toy4State,
    history: Toy4History,
    rng: RngRegistry,
    metadata: dict[str, object],
) -> Path:
    """Atomically publish one end-of-quarter checkpoint; refuse overwrite."""
    if directory.exists() or directory.is_symlink():
        raise ResearchGateError(
            f"checkpoint directory {directory} already exists; refusing to overwrite"
        )
    directory.parent.mkdir(parents=True, exist_ok=True)
    staging = directory.parent / f".tmp-{uuid4().hex}"
    staging.mkdir()
    try:
        arrays = state_arrays(state)
        for name, array in arrays.items():
            if array.dtype.hasobject:
                raise ResearchGateError(f"state array {name} has object dtype")
        payload_arrays: dict[str, Any] = {
            "completed_ticks": np.asarray(state.completed_ticks, dtype="<i8"),
            **{
                name: np.ascontiguousarray(array)
                for name, array in arrays.items()
            },
        }
        np.savez(staging / "state.npz", **payload_arrays)

        frames = history_frames(history)
        for name in _HISTORY_TABLES:
            frame = frames[name]
            if frame.height == 0:
                # Parquet needs an explicit empty-frame schema write.
                frame = frame.clear()
            frame.write_parquet(staging / f"{name}.parquet")
        payload: dict[str, object] = {
            "checkpoint_version": CHECKPOINT_VERSION,
            "state_version": state.schema_version,
            "engine_version": TOY4_ENGINE_VERSION,
            "completed_ticks": int(state.completed_ticks),
            "rng_snapshot": rng.snapshot(),
            "digest_chain": history.digest_chain,
            **metadata,
        }
        payload_hashes = {
            entry.name: sha256_file(entry)
            for entry in sorted(staging.iterdir())
            if entry.is_file()
        }
        payload["payload_sha256"] = payload_hashes
        (staging / "metadata.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(staging, directory)
    except BaseException:
        import shutil

        shutil.rmtree(staging, ignore_errors=True)
        raise
    return directory


def _verify_payload_hashes(directory: Path, metadata: dict[str, Any]) -> None:
    declared = metadata.get("payload_sha256")
    if not isinstance(declared, dict):
        raise ResearchGateError("checkpoint metadata lacks payload_sha256 map")
    actual_names = {
        entry.name for entry in directory.iterdir() if entry.is_file()
    } - {"metadata.json"}
    if set(declared) != actual_names:
        raise ResearchGateError(
            f"checkpoint payload file set mismatch: declared {sorted(declared)} "
            f"vs present {sorted(actual_names)}"
        )
    for name, digest in sorted(declared.items()):
        path = directory / name
        if not path.is_file():
            raise ResearchGateError(f"checkpoint payload {name} is missing")
        if sha256_file(path) != digest:
            raise ResearchGateError(f"checkpoint payload {name}: digest mismatch")


def _validate_history_consistency(
    frames: dict[str, Any],
    state: Toy4State,
    scenario: ScenarioSpec,
    completed: int,
    forcing: Any,
) -> None:
    """Cross-check the stored prefix against the retained boundary state.

    Recomputes stock continuity, the per-commodity material identity and the
    boundary stocks from the compact rows; a hash-consistent but economically
    inconsistent prefix is refused before any output exists.
    """
    import polars as pl

    national = frames["national_accounts"].sort(["commodity_id", "tick"])
    aggregates = frames["aggregates"].sort(["commodity_id", "region_id", "tick"])
    budgets = frames["household_budgets"].sort(["region_id", "tick"])
    commodities = list(scenario.commodities)
    regions = list(scenario.region_ids)
    expected_ticks = list(range(completed))
    agg_index = {
        (int(row["tick"]), row["region_id"], row["commodity_id"]): row
        for row in frames["aggregates"].iter_rows(named=True)
    }
    budget_index = {
        (int(row["tick"]), row["region_id"]): row
        for row in frames["household_budgets"].iter_rows(named=True)
    }

    def per_commodity(
        frame: Any, column: str
    ) -> dict[str, list[tuple[int, float]]]:
        return {
            commodity: sorted(
                zip(
                    frame.filter(pl.col("commodity_id") == commodity)["tick"].to_list(),
                    frame.filter(pl.col("commodity_id") == commodity)[column].to_list(),
                    strict=True,
                )
            )
            for commodity in commodities
        }

    from hsm_lab.engine.accounting import ATOL, RTOL

    def tol(lhs: float, rhs: float) -> float:
        return ATOL + RTOL * max(abs(lhs), abs(rhs))

    # Adjacent-quarter continuity (needs at least two ticks).
    if completed >= 2:
        close = per_commodity(national, "total_stock_close")
        open_ = per_commodity(national, "total_stock_open")
        for commodity in commodities:
            for index in range(1, len(close[commodity])):
                lhs = open_[commodity][index][1]
                rhs = close[commodity][index - 1][1]
                if abs(lhs - rhs) > tol(lhs, rhs):
                    raise ResearchGateError(
                        f"checkpoint history stock continuity broken for {commodity} "
                        f"at tick {open_[commodity][index][0]}"
                    )

    # Per-row identities at every positive boundary (including the first tick).
    for row in national.iter_rows(named=True):
        lhs = row["total_stock_close"] - row["total_stock_open"]
        rhs = (
            row["imports"]
            + row["production"]
            - row["used_input"]
            - row["export_realized"]
            - row["household_consumption"]
        )
        if abs(lhs - rhs) > tol(lhs, rhs):
            raise ResearchGateError(
                f"checkpoint history national row is not material-balanced at "
                f"tick {row['tick']} commodity {row['commodity_id']}"
            )
        row_tol = tol(lhs, rhs)
        if abs(row["material_balance_residual"]) > row_tol:
            raise ResearchGateError(
                f"checkpoint history stores a residual beyond tolerance at "
                f"tick {row['tick']} commodity {row['commodity_id']}"
            )
        if abs(row["material_balance_tolerance_ratio"]) > 1.0:
            raise ResearchGateError(
                f"checkpoint history stores an out-of-range material tolerance ratio "
                f"at tick {row['tick']} commodity {row['commodity_id']}"
            )
        if row["material_balance_tolerance_ratio"] < 0.0:
            raise ResearchGateError(
                f"checkpoint history stores a negative material tolerance ratio at "
                f"tick {row['tick']} commodity {row['commodity_id']}"
            )

    # Regional rows must agree with the national rows they aggregate into.
    for row in national.iter_rows(named=True):
        tick = row["tick"]
        commodity = row["commodity_id"]
        agg_rows = aggregates.filter(
            (pl.col("tick") == tick) & (pl.col("commodity_id") == commodity)
        )
        for column in (
            "production",
            "retail_close",
            "organization_input_close",
            "organization_input_open",
            "retail_open",
            "used_input",
            "household_realized",
        ):
            regional_sum = float(agg_rows[column].sum())
            if column == "household_realized":
                national_value = float(row["household_consumption"])
            else:
                national_value = float(row[column])
            if abs(regional_sum - national_value) > tol(regional_sum, national_value):
                raise ResearchGateError(
                    f"checkpoint history regional {column} disagrees with national at "
                    f"tick {tick} commodity {commodity}"
                )

    # National stock composition and export identity per row.
    for row in national.iter_rows(named=True):
        open_sum = (
            row["wholesale_open"]
            + row["organization_input_open"]
            + row["retail_open"]
        )
        close_sum = (
            row["wholesale_close"]
            + row["organization_input_close"]
            + row["retail_close"]
        )
        if abs(row["total_stock_open"] - open_sum) > tol(row["total_stock_open"], open_sum):
            raise ResearchGateError(
                f"checkpoint national total_stock_open composition broken at tick "
                f"{row['tick']} commodity {row['commodity_id']}"
            )
        if abs(row["total_stock_close"] - close_sum) > tol(row["total_stock_close"], close_sum):
            raise ResearchGateError(
                f"checkpoint national total_stock_close composition broken at tick "
                f"{row['tick']} commodity {row['commodity_id']}"
            )
        unmet = row["export_desired"] - row["export_realized"]
        if abs(row["export_unmet"] - unmet) > tol(row["export_unmet"], unmet):
            raise ResearchGateError(
                f"checkpoint national export_unmet definition broken at tick "
                f"{row['tick']} commodity {row['commodity_id']}"
            )
        tick_agg = aggregates.filter(
            (pl.col("tick") == row["tick"])
            & (pl.col("commodity_id") == row["commodity_id"])
        )
        expected_close = (
            row["wholesale_open"]
            + row["imports"]
            + row["production"]
            - float(tick_agg["delivered_input"].sum())
            - row["export_realized"]
            - float(tick_agg["retail_incoming"].sum())
        )
        if abs(row["wholesale_close"] - expected_close) > tol(
            row["wholesale_close"], expected_close
        ):
            raise ResearchGateError(
                f"checkpoint national wholesale ledger broken at tick {row['tick']} "
                f"commodity {row['commodity_id']}"
            )

    # Recompute each region's desired input from the retained static arrays.
    params = scenario.toy4_parameters
    assert params is not None
    target_scalar = np.minimum(
        float(params.target_utilization) * state.organization_capacity,
        state.organization_labor_capacity,
    )
    target = state.organization_output_mix * target_scalar[:, None]
    desired_per_org = state.organization_input_coefficients * target_scalar[:, None]
    expected_target: dict[str, list[float]] = {}
    expected_desired: dict[str, list[float]] = {}
    for region_index, region in enumerate(regions):
        mask = state.organization_region == region_index
        if mask.any():
            expected_target[region] = target[mask].sum(axis=0).tolist()
            expected_desired[region] = (
                desired_per_org[mask].sum(axis=0).tolist()
            )
        else:
            expected_target[region] = [0.0] * len(commodities)
            expected_desired[region] = [0.0] * len(commodities)

    # Historical forcing must equal the admitted fixture.
    for row in national.iter_rows(named=True):
        tick = int(row["tick"])
        commodity_index = commodities.index(row["commodity_id"])
        expected_import = float(forcing.imports[tick, commodity_index])
        expected_export = float(forcing.export_orders[tick, commodity_index])
        if abs(row["imports"] - expected_import) > tol(
            row["imports"], expected_import
        ):
            raise ResearchGateError(
                f"checkpoint history imports disagree with the admitted forcing at "
                f"tick {tick} commodity {row['commodity_id']}"
            )
        if abs(row["export_desired"] - expected_export) > tol(
            row["export_desired"], expected_export
        ):
            raise ResearchGateError(
                f"checkpoint history export_desired disagrees with the admitted "
                f"forcing at tick {tick} commodity {row['commodity_id']}"
            )

    # Recompute the household block exactly from the retained micro state, the
    # declared parameters and each tick's retail availability.
    prices = np.asarray(params.prices, dtype=np.float64)
    dpp = np.asarray(params.desired_per_person, dtype=np.float64)
    size = state.household_size
    weight = state.household_weight
    income_h = float(params.income_per_person) * size
    desired_h = size[:, None] * dpp[None, :]
    cost_h = desired_h @ prices
    alpha = np.ones(size.shape[0])
    binding = cost_h > 0
    alpha[binding] = np.minimum(1.0, income_h[binding] / cost_h[binding])
    affordable_h = desired_h * alpha[:, None]
    for tick in expected_ticks:
        for region_index, region in enumerate(regions):
            mask = state.household_region == region_index
            w = weight[mask]
            region_affordable = affordable_h[mask]
            demand = (w[:, None] * region_affordable).sum(axis=0)
            beta = np.ones(len(commodities))
            for index, commodity in enumerate(commodities):
                available = agg_index[(tick, region, commodity)]["retail_available"]
                if demand[index] > 0:
                    beta[index] = min(1.0, available / demand[index])
            realized = region_affordable * beta[None, :]
            income_r = float((w * income_h[mask]).sum())
            desired_r = (w[:, None] * desired_h[mask]).sum(axis=0)
            affordable_r = demand
            realized_r = (w[:, None] * realized).sum(axis=0)
            spending_r = float((w * (realized @ prices)).sum())
            voluntary_r = float((w * (income_h[mask] - region_affordable @ prices)).sum())
            forced_r = float((w * ((region_affordable - realized) @ prices)).sum())
            budget_row = budget_index[(tick, region)]
            for label, lhs, rhs in (
                ("budget_income", budget_row["income"], income_r),
                ("budget_spending", budget_row["spending"], spending_r),
                ("budget_voluntary_saving", budget_row["voluntary_saving"], voluntary_r),
                ("budget_forced_saving", budget_row["forced_saving"], forced_r),
            ):
                if abs(lhs - rhs) > tol(lhs, rhs):
                    raise ResearchGateError(
                        f"checkpoint {label} disagrees with recomputation at tick "
                        f"{tick} region {region}"
                    )
            for index, commodity in enumerate(commodities):
                cell = agg_index[(tick, region, commodity)]
                for label, lhs, rhs in (
                    ("household_desired", cell["household_desired"], desired_r[index]),
                    ("household_affordable", cell["household_affordable"], affordable_r[index]),
                    ("household_realized", cell["household_realized"], realized_r[index]),
                ):
                    if abs(lhs - rhs) > tol(lhs, rhs):
                        raise ResearchGateError(
                            f"checkpoint {label} disagrees with recomputation at tick "
                            f"{tick} region {region} commodity {commodity}"
                        )

    # Adjacent-quarter continuity for regional organization and retail stocks.
    if completed >= 2:
        for region in regions:
            region_agg = aggregates.filter(pl.col("region_id") == region).sort("tick")
            for commodity in commodities:
                rows = region_agg.filter(pl.col("commodity_id") == commodity).sort("tick")
                close_org = rows["organization_input_close"].to_list()
                open_org = rows["organization_input_open"].to_list()
                close_retail = rows["retail_close"].to_list()
                open_retail = rows["retail_open"].to_list()
                for step in range(1, len(close_org)):
                    if abs(open_org[step] - close_org[step - 1]) > tol(
                        open_org[step], close_org[step - 1]
                    ):
                        raise ResearchGateError(
                            f"checkpoint regional organization input continuity broken "
                            f"for {region}/{commodity} at tick {step}"
                        )
                    if abs(open_retail[step] - close_retail[step - 1]) > tol(
                        open_retail[step], close_retail[step - 1]
                    ):
                        raise ResearchGateError(
                            f"checkpoint regional retail continuity broken for "
                            f"{region}/{commodity} at tick {step}"
                        )

    # Regional rows: local stock-flow and flow-definition identities.
    for row in aggregates.iter_rows(named=True):
        checks = (
            (
                "organization_input_identity",
                row["organization_input_close"],
                row["organization_input_open"] + row["delivered_input"] - row["used_input"],
            ),
            (
                "retail_identity",
                row["retail_close"],
                row["retail_open"] + row["retail_incoming"] - row["retail_sales"],
            ),
            (
                "available_input_identity",
                row["available_input"],
                row["organization_input_open"] + row["delivered_input"],
            ),
            (
                "input_unmet_identity",
                row["input_unmet"],
                row["ordered_input"] - row["delivered_input"],
            ),
            (
                "production_shortfall_identity",
                row["production_shortfall"],
                row["production_target"] - row["production"],
            ),
            (
                "budget_unmet_identity",
                row["budget_unmet"],
                row["household_desired"] - row["household_affordable"],
            ),
            (
                "availability_unmet_identity",
                row["availability_unmet"],
                row["household_affordable"] - row["household_realized"],
            ),
            (
                "total_unmet_identity",
                row["total_unmet"],
                row["household_desired"] - row["household_realized"],
            ),
            ("retail_planned_identity", row["retail_planned"], row["retail_incoming"]),
            ("allocated_identity", row["allocated_input"], row["delivered_input"]),
            (
                "ordered_input_identity",
                row["ordered_input"],
                max(row["desired_input"] - row["organization_input_open"], 0.0),
            ),
            (
                "retail_sales_identity",
                row["retail_sales"],
                row["household_realized"],
            ),
            (
                "retail_available_identity",
                row["retail_available"],
                row["retail_open"] + row["retail_incoming"],
            ),
        )
        for label, lhs, rhs in checks:
            if abs(lhs - rhs) > tol(lhs, rhs):
                raise ResearchGateError(
                    f"checkpoint aggregate {label} broken at tick {row['tick']} "
                    f"region {row['region_id']} commodity {row['commodity_id']}"
                )
        commodity_index = commodities.index(row["commodity_id"])
        expected = expected_desired[row["region_id"]][commodity_index]
        if abs(row["desired_input"] - expected) > tol(row["desired_input"], expected):
            raise ResearchGateError(
                f"checkpoint aggregate desired_input disagrees with recomputation at "
                f"tick {row['tick']} region {row['region_id']} "
                f"commodity {row['commodity_id']}"
            )
        expected_tgt = expected_target[row["region_id"]][commodity_index]
        if abs(row["production_target"] - expected_tgt) > tol(
            row["production_target"], expected_tgt
        ):
            raise ResearchGateError(
                f"checkpoint aggregate production_target disagrees with recomputation at "
                f"tick {row['tick']} region {row['region_id']} "
                f"commodity {row['commodity_id']}"
            )
        if row["delivered_input"] > row["ordered_input"] + tol(
            row["delivered_input"], row["ordered_input"]
        ):
            raise ResearchGateError(
                f"checkpoint aggregate delivered>ordered at tick {row['tick']} "
                f"region {row['region_id']} commodity {row['commodity_id']}"
            )
        if row["used_input"] > row["available_input"] + tol(
            row["used_input"], row["available_input"]
        ):
            raise ResearchGateError(
                f"checkpoint aggregate used>available at tick {row['tick']} "
                f"region {row['region_id']} commodity {row['commodity_id']}"
            )
        if row["household_realized"] > row["household_affordable"] + tol(
            row["household_realized"], row["household_affordable"]
        ) or row["household_affordable"] > row["household_desired"] + tol(
            row["household_affordable"], row["household_desired"]
        ):
            raise ResearchGateError(
                f"checkpoint aggregate household ordering broken at tick {row['tick']} "
                f"region {row['region_id']} commodity {row['commodity_id']}"
            )
        expected_availability_rate = (
            row["availability_unmet"] / row["household_affordable"]
            if row["household_affordable"] > 0
            else 0.0
        )
        if abs(row["availability_shortage_rate"] - expected_availability_rate) > 1e-9:
            raise ResearchGateError(
                f"checkpoint aggregate availability rate disagrees at tick "
                f"{row['tick']} region {row['region_id']} commodity {row['commodity_id']}"
            )
        expected_total_rate = (
            row["total_unmet"] / row["household_desired"]
            if row["household_desired"] > 0
            else 0.0
        )
        if abs(row["total_unmet_rate"] - expected_total_rate) > 1e-9:
            raise ResearchGateError(
                f"checkpoint aggregate total unmet rate disagrees at tick "
                f"{row['tick']} region {row['region_id']} commodity {row['commodity_id']}"
            )

    # Budget rows: household count, weights and persons must match the retained
    # immutable household arrays; plus saving decomposition and cash residual.
    for row in budgets.iter_rows(named=True):
        region_index = regions.index(row["region_id"])
        mask = state.household_region == region_index
        count = int(mask.sum())
        weight_sum = float(state.household_weight[mask].sum())
        persons = float(
            (state.household_weight[mask] * state.household_size[mask]).sum()
        )
        if row["household_count"] != count:
            raise ResearchGateError(
                f"checkpoint budget household_count disagrees with state at tick "
                f"{row['tick']} region {row['region_id']}"
            )
        if abs(row["weight_sum"] - weight_sum) > tol(row["weight_sum"], weight_sum):
            raise ResearchGateError(
                f"checkpoint budget weight_sum disagrees with state at tick "
                f"{row['tick']} region {row['region_id']}"
            )
        if abs(row["equivalent_persons"] - persons) > tol(row["equivalent_persons"], persons):
            raise ResearchGateError(
                f"checkpoint budget equivalent_persons disagrees with state at tick "
                f"{row['tick']} region {row['region_id']}"
            )
        saving_sum = row["voluntary_saving"] + row["forced_saving"]
        income_spend = row["income"] - row["spending"]
        if abs(income_spend - saving_sum) > tol(income_spend, saving_sum):
            raise ResearchGateError(
                f"checkpoint budget saving decomposition broken at tick "
                f"{row['tick']} region {row['region_id']}"
            )
        cash_lhs = row["cash_close"] - row["cash_open"]
        cash_rhs = row["income"] - row["spending"]
        recomputed_residual = cash_lhs - cash_rhs
        recomputed_tolerance = tol(cash_lhs, cash_rhs)
        if abs(row["cash_balance_residual"] - recomputed_residual) > max(
            recomputed_tolerance, 1e-9
        ):
            raise ResearchGateError(
                f"checkpoint budget cash residual disagrees with recomputation at tick "
                f"{row['tick']} region {row['region_id']}"
            )
        # The ratio itself is derived from a cancellation-heavy residual; only
        # its [0, 1] bound (checked in the diagnostics scan) and the residual
        # binding above are numerically meaningful. The raw tolerance column is
        # not stored, so an exact ratio recomputation is not attempted.
        if row["cash_balance_tolerance_ratio"] < 0.0:
            raise ResearchGateError(
                f"checkpoint budget cash tolerance ratio is negative at tick "
                f"{row['tick']} region {row['region_id']}"
            )

    for row in budgets.iter_rows(named=True):
        lhs = row["cash_close"] - row["cash_open"]
        rhs = row["income"] - row["spending"]
        if abs(lhs - rhs) > tol(lhs, rhs):
            raise ResearchGateError(
                f"checkpoint history household cash identity broken at tick "
                f"{row['tick']} region {row['region_id']}"
            )
        if abs(row["cash_balance_tolerance_ratio"]) > 1.0:
            raise ResearchGateError(
                f"checkpoint history stores an out-of-range cash tolerance ratio at "
                f"tick {row['tick']} region {row['region_id']}"
            )
    if completed >= 2:
        for region in regions:
            rows = budgets.filter(pl.col("region_id") == region).sort("tick")
            cash_close = rows["cash_close"].to_list()
            cash_open = rows["cash_open"].to_list()
            for index in range(1, len(cash_close)):
                if abs(cash_open[index] - cash_close[index - 1]) > tol(
                    cash_open[index], cash_close[index - 1]
                ):
                    raise ResearchGateError(
                        f"checkpoint history household cash continuity broken for "
                        f"region {region}"
                    )

    # Boundary stocks must match the retained state.
    final_tick = completed - 1
    for index, commodity in enumerate(commodities):
        rows = national.filter(
            (pl.col("commodity_id") == commodity) & (pl.col("tick") == final_tick)
        )
        wholesale = float(rows["wholesale_close"][0])
        org_input = float(rows["organization_input_close"][0])
        retail = float(rows["retail_close"][0])
        if abs(wholesale - float(state.wholesale_inventory[index])) > 1e-9:
            raise ResearchGateError(
                f"checkpoint boundary wholesale stock disagrees with state for {commodity}"
            )
        if abs(org_input - float(state.organization_input_inventory[:, index].sum())) > 1e-9:
            raise ResearchGateError(
                f"checkpoint boundary organization input disagrees with state for {commodity}"
            )
        if abs(retail - float(state.retail_inventory[:, index].sum())) > 1e-9:
            raise ResearchGateError(
                f"checkpoint boundary retail stock disagrees with state for {commodity}"
            )
    for region_index, region in enumerate(regions):
        rows = budgets.filter(
            (pl.col("region_id") == region) & (pl.col("tick") == final_tick)
        )
        mask = state.household_region == region_index
        state_cash = float(
            np.sum(state.household_weight[mask] * state.household_cash[mask])
        )
        if abs(float(rows["cash_close"][0]) - state_cash) > 1e-6:
            raise ResearchGateError(
                f"checkpoint boundary household cash disagrees with state for {region}"
            )
    for region_index, region in enumerate(regions):
        rows = aggregates.filter(
            (pl.col("region_id") == region) & (pl.col("tick") == final_tick)
        )
        org_mask = state.organization_region == region_index
        for index, commodity in enumerate(commodities):
            cell = rows.filter(pl.col("commodity_id") == commodity)
            if cell.height != 1:
                raise ResearchGateError(
                    f"checkpoint boundary aggregates incomplete for {region}/{commodity}"
                )
            regional_org_input = float(
                state.organization_input_inventory[org_mask, index].sum()
            )
            if abs(float(cell["organization_input_close"][0]) - regional_org_input) > 1e-9:
                raise ResearchGateError(
                    f"checkpoint boundary regional organization input disagrees with "
                    f"state for {region}/{commodity}"
                )
            if (
                abs(float(cell["retail_close"][0])
                    - float(state.retail_inventory[region_index, index])) > 1e-9
            ):
                raise ResearchGateError(
                    f"checkpoint boundary regional retail disagrees with state for "
                    f"{region}/{commodity}"
                )


def load_toy4_checkpoint(
    directory: Path,
    spec: ScenarioSpec,
    contract: ResearchContract,
    registry: Any,
) -> tuple[Toy4State, Toy4History, RngRegistry, dict[str, object]]:
    """Strictly verify and restore a checkpoint; no output side effects."""
    from hsm_lab.engine.toy4 import load_toy4_forcing

    if not directory.is_dir():
        raise ResearchGateError(f"checkpoint directory not found: {directory}")
    try:
        metadata = json.loads(
            (directory / "metadata.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchGateError(f"unreadable checkpoint metadata: {exc}") from exc
    if metadata.get("checkpoint_version") != CHECKPOINT_VERSION:
        raise ResearchGateError(
            f"unsupported checkpoint version {metadata.get('checkpoint_version')!r}"
        )
    if metadata.get("state_version") != TOY4_STATE_VERSION:
        raise ResearchGateError("checkpoint state schema version mismatch")
    if metadata.get("engine_version") != TOY4_ENGINE_VERSION:
        raise ResearchGateError("checkpoint engine version mismatch")
    _verify_payload_hashes(directory, metadata)

    # --- scenario identity: template rules must be unchanged; the snapshot's
    # own runtime profile (seed/N/ticks/policy) is what gets restored.
    snapshot_scenario = ScenarioSpec.model_validate(metadata.get("scenario"))
    for field in (
        "scenario_id",
        "kind",
        "start",
        "region_ids",
        "commodities",
        "forcing_ids",
        "initial_ids",
        "parameter_ids",
        "toy4_parameters",
        "toy4_initial",
    ):
        if getattr(snapshot_scenario, field) != getattr(spec, field):
            raise ResearchGateError(
                f"checkpoint scenario {field} differs from the current template; "
                "forking a checkpoint into a modified scenario is refused"
            )
    boundary_ticks = metadata.get("completed_ticks")
    if isinstance(boundary_ticks, bool) or not isinstance(boundary_ticks, int):
        raise ResearchGateError("checkpoint metadata lacks an integer completed_ticks")
    expected_last = str(snapshot_scenario.start.advance(boundary_ticks - 1))
    if metadata.get("last_completed_quarter") != expected_last:
        raise ResearchGateError(
            f"checkpoint last_completed_quarter {metadata.get('last_completed_quarter')!r} "
            f"disagrees with the boundary {expected_last!r}"
        )
    expected_next = str(snapshot_scenario.start.advance(boundary_ticks))
    if metadata.get("next_quarter") != expected_next:
        raise ResearchGateError(
            f"checkpoint next_quarter {metadata.get('next_quarter')!r} "
            f"disagrees with the boundary {expected_next!r}"
        )
    if metadata.get("region_ids") != list(snapshot_scenario.region_ids):
        raise ResearchGateError("checkpoint region axes disagree with the scenario")
    if metadata.get("commodity_ids") != list(snapshot_scenario.commodities):
        raise ResearchGateError("checkpoint commodity axes disagree with the scenario")

    # --- environment hashes must match the current world.
    if metadata.get("baseline_hash") != contract.expected_baseline_sha256:
        raise ResearchGateError("checkpoint baseline hash differs from the pinned one")
    from hsm_lab.provenance.manifest import compute_lock_hash

    if metadata.get("lock_hash") != compute_lock_hash(registry.root):
        raise ResearchGateError("checkpoint lock hash differs from the current lock")
    forcing = load_toy4_forcing(snapshot_scenario, registry)
    if dict(forcing.input_artifact_hashes) != metadata.get("input_artifact_hashes"):
        raise ResearchGateError("checkpoint input artifact hashes differ")
    from hsm_lab.engine.toy4 import toy4_parameter_vector, toy4_recipe_hash

    if (
        metadata.get("parameter_hash")
        != _hash_vector(toy4_parameter_vector(snapshot_scenario))
    ):
        raise ResearchGateError("checkpoint parameter hash mismatch")
    if metadata.get("initial_recipe_hash") != toy4_recipe_hash(snapshot_scenario):
        raise ResearchGateError("checkpoint initial recipe hash mismatch")

    # --- state payload.
    try:
        payload = np.load(directory / "state.npz", allow_pickle=False)
    except Exception as exc:  # noqa: BLE001 - any load failure is a gate failure
        raise ResearchGateError(f"unreadable checkpoint state: {exc}") from exc
    raw_completed = np.asarray(payload["completed_ticks"])
    if raw_completed.dtype != np.dtype("<i8") or raw_completed.shape != ():
        raise ResearchGateError(
            "checkpoint completed_ticks must be a scalar int64 array "
            f"(got dtype {raw_completed.dtype}, shape {raw_completed.shape})"
        )
    completed = int(raw_completed.item())
    if completed != metadata.get("completed_ticks") or completed <= 0:
        raise ResearchGateError("checkpoint completed_ticks inconsistent")
    arrays: dict[str, np.ndarray] = {}
    for name, dtype in _STATE_DTYPES.items():
        target = np.dtype(dtype)
        try:
            raw = np.asarray(payload[name])
        except (KeyError, ValueError) as exc:
            raise ResearchGateError(f"checkpoint state array {name} invalid: {exc}") from exc
        if raw.dtype != target:
            raise ResearchGateError(
                f"checkpoint state array {name} has dtype {raw.dtype}, "
                f"expected exactly {target} (silent coercion is refused)"
            )
        arrays[name] = np.ascontiguousarray(raw)
    state = _state_from_arrays(arrays, completed)
    n = state.household_id.shape[0]
    e = state.organization_id.shape[0]
    r = state.retail_inventory.shape[0]
    g = state.wholesale_inventory.shape[0]
    expected_shapes: dict[str, tuple[int, ...]] = {
        "household_id": (n,),
        "household_region": (n,),
        "household_weight": (n,),
        "household_size": (n,),
        "household_cash": (n,),
        "organization_id": (e,),
        "organization_region": (e,),
        "organization_output_sector": (e,),
        "organization_capacity": (e,),
        "organization_labor_capacity": (e,),
        "organization_input_coefficients": (e, g),
        "organization_output_mix": (e, g),
        "organization_input_inventory": (e, g),
        "wholesale_inventory": (g,),
        "retail_inventory": (r, g),
        "region_equivalent_persons": (r,),
        "regional_share": (r,),
    }

    for name, shape in expected_shapes.items():
        if arrays[name].shape != shape:
            raise ResearchGateError(
                f"checkpoint state array {name} has shape {arrays[name].shape}, "
                f"expected {shape}"
            )
    if n != snapshot_scenario.households or e != snapshot_scenario.enterprises:
        raise ResearchGateError("checkpoint axes disagree with the snapshot scenario")
    if g != len(snapshot_scenario.commodities) or r != len(snapshot_scenario.region_ids):
        raise ResearchGateError("checkpoint axes disagree with the snapshot scenario")
    if len(set(state.household_id.tolist())) != n or len(
        set(state.organization_id.tolist())
    ) != e:
        raise ResearchGateError("checkpoint household/organization ids are not unique")
    from hsm_lab.engine.accounting import ATOL

    for name in (
        "organization_input_inventory",
        "wholesale_inventory",
        "retail_inventory",
        "household_cash",
        "household_weight",
        "household_size",
        "organization_capacity",
        "organization_labor_capacity",
        "organization_input_coefficients",
        "organization_output_mix",
        "region_equivalent_persons",
        "regional_share",
    ):
        values = arrays[name]
        if not np.all(np.isfinite(values)):
            raise ResearchGateError(f"checkpoint state array {name} is not finite")
        if float(np.min(values)) < -ATOL:
            raise ResearchGateError(f"checkpoint state array {name} is negative")
    if (
        int(state.household_region.min()) < 0
        or int(state.household_region.max()) >= r
        or int(state.organization_region.min()) < 0
        or int(state.organization_region.max()) >= r
        or int(state.organization_output_sector.min()) < 0
        or int(state.organization_output_sector.max()) >= g
    ):
        raise ResearchGateError("checkpoint index arrays fall outside the state axes")
    if (
        float(state.regional_share.min()) < 0
        or abs(float(state.regional_share.sum()) - 1.0) > 1e-9
    ):
        raise ResearchGateError(
            "checkpoint regional shares are not a valid distribution"
        )
    parameters = snapshot_scenario.toy4_parameters
    assert parameters is not None
    recipe = snapshot_scenario.toy4_initial
    assert recipe is not None
    from hsm_lab.engine.accounting import AccountingError, check_toy4_state_identities

    try:
        check_toy4_state_identities(
            state, parameters, "checkpoint", float(recipe.household_cash)
        )
    except AccountingError as exc:
        raise ResearchGateError(
            f"checkpoint state violates declared initialization identities: {exc}"
        ) from exc

    # --- history payload: exact schemas, unique full key grids, coverage and
    # a matching digest boundary.
    import polars as pl

    from hsm_lab.storage.toy4_output import (
        AGGREGATE_COLUMNS,
        BUDGET_COLUMNS,
        DIAGNOSTIC_COLUMNS,
        EVENT_COLUMNS,
        NATIONAL_COLUMNS,
    )

    expected_columns = {
        "aggregates": AGGREGATE_COLUMNS,
        "national_accounts": NATIONAL_COLUMNS,
        "household_budgets": BUDGET_COLUMNS,
        "tick_diagnostics": DIAGNOSTIC_COLUMNS,
        "events": EVENT_COLUMNS,
    }
    key_columns = {
        "aggregates": ["tick", "region_id", "commodity_id"],
        "national_accounts": ["tick", "commodity_id"],
        "household_budgets": ["tick", "region_id"],
        "tick_diagnostics": ["tick"],
        "events": ["tick"],
    }
    string_columns = {
        "aggregates": {"quarter", "region_id", "commodity_id"},
        "national_accounts": {"quarter", "commodity_id"},
        "household_budgets": {"quarter", "region_id"},
        "tick_diagnostics": {"quarter", "digest"},
        "events": {"quarter", "event_type", "details_json"},
    }
    frames: dict[str, pl.DataFrame] = {}
    for name in _HISTORY_TABLES:
        path = directory / f"{name}.parquet"
        if not path.is_file():
            raise ResearchGateError(f"checkpoint history table {name} is missing")
        frame = pl.read_parquet(path)
        if frame.columns != expected_columns[name]:
            raise ResearchGateError(
                f"checkpoint history table {name} schema differs from the writer's"
            )
        for column in expected_columns[name]:
            expected_dtype: Any
            if column in ("tick", "household_count"):
                expected_dtype = pl.Int64
            elif column in string_columns[name]:
                expected_dtype = pl.String
            else:
                expected_dtype = pl.Float64
            if frame.schema[column] != expected_dtype:
                raise ResearchGateError(
                    f"checkpoint history table {name}.{column} has dtype "
                    f"{frame.schema[column]}, expected exactly {expected_dtype}"
                )
        for column in expected_columns[name]:
            if frame[column].null_count():
                raise ResearchGateError(
                    f"checkpoint history table {name}.{column} has null values"
                )
        numeric = [
            column
            for column in expected_columns[name]
            if column not in string_columns[name]
        ]
        for column in numeric:
            series = frame[column]
            if not series.is_finite().all():
                raise ResearchGateError(
                    f"checkpoint history table {name}.{column} has non-finite values"
                )
        if frame.group_by(key_columns[name]).len().filter(pl.col("len") > 1).height:
            raise ResearchGateError(
                f"checkpoint history table {name} contains duplicate keys"
            )
        frames[name] = frame
    expected_ticks = list(range(completed))
    for name in _HISTORY_TABLES:
        bad_quarter = frames[name].filter(
            pl.col("quarter")
            != pl.col("tick").map_elements(
                lambda tick: str(snapshot_scenario.start.advance(int(tick))),
                return_dtype=pl.String,
            )
        )
        if bad_quarter.height:
            raise ResearchGateError(
                f"checkpoint history table {name} has rows whose quarter disagrees "
                "with the scenario calendar"
            )

    for name in _HISTORY_TABLES:
        observed_ticks = sorted(frames[name]["tick"].unique().to_list())
        if observed_ticks != expected_ticks:
            raise ResearchGateError(
                f"checkpoint history table {name} does not cover ticks "
                f"0..{completed - 1} exactly"
            )
    axis_checks = (
        ("aggregates", "region_id", snapshot_scenario.region_ids),
        ("aggregates", "commodity_id", snapshot_scenario.commodities),
        ("national_accounts", "commodity_id", snapshot_scenario.commodities),
        ("household_budgets", "region_id", snapshot_scenario.region_ids),
    )
    for table, column, allowed in axis_checks:
        observed = set(frames[table][column].unique().to_list())
        unknown = observed - set(allowed)
        if unknown:
            raise ResearchGateError(
                f"checkpoint history {table}.{column} references unknown "
                f"values {sorted(unknown)}"
            )
    diagnostics = frames["tick_diagnostics"]
    if diagnostics.height != completed:
        raise ResearchGateError(
            f"checkpoint diagnostics cover {diagnostics.height} ticks, "
            f"boundary claims {completed}"
        )
    if frames["aggregates"].height != completed * r * g:
        raise ResearchGateError("checkpoint aggregates prefix is incomplete")
    if frames["national_accounts"].height != completed * g:
        raise ResearchGateError("checkpoint national prefix is incomplete")
    if frames["household_budgets"].height != completed * r:
        raise ResearchGateError("checkpoint household budget prefix is incomplete")
    if frames["events"].height != completed:
        raise ResearchGateError("checkpoint events prefix is incomplete")
    for column in (
        "max_material_abs_residual",
        "max_material_tolerance_ratio",
        "max_cash_abs_residual",
        "max_cash_tolerance_ratio",
    ):
        series = diagnostics[column]
        if bool((series < 0.0).any()) or bool((series > 1.0).any()):
            raise ResearchGateError(
                f"checkpoint diagnostics {column} lies outside [0, 1]"
            )
    _validate_history_consistency(frames, state, snapshot_scenario, completed, forcing)
    chain = metadata.get("digest_chain")
    if not isinstance(chain, str) or not chain:
        raise ResearchGateError("checkpoint lacks a digest chain")

    if diagnostics.height and diagnostics["digest"][-1] != chain:
        raise ResearchGateError("checkpoint digest chain disagrees with last tick row")

    # Events must be the declared tick events and carry the same evidence as the
    # diagnostics row for their tick.
    from hsm_lab.storage.toy4_output import TOY4_TICK_EVENT

    diagnostic_by_tick = {
        int(row["tick"]): row for row in diagnostics.iter_rows(named=True)
    }
    for row in frames["events"].iter_rows(named=True):
        if row["event_type"] != TOY4_TICK_EVENT:
            raise ResearchGateError(
                f"checkpoint event type {row['event_type']!r} is not {TOY4_TICK_EVENT!r}"
            )
        try:
            details = json.loads(row["details_json"])
        except (TypeError, ValueError) as exc:
            raise ResearchGateError(
                f"checkpoint event details are not valid JSON: {exc}"
            ) from exc
        if not isinstance(details, dict):
            raise ResearchGateError("checkpoint event details must be a JSON object")
        diagnostic = diagnostic_by_tick.get(int(row["tick"]))
        if diagnostic is None:
            raise ResearchGateError(
                f"checkpoint event at tick {row['tick']} has no diagnostics row"
            )
        if details.get("digest") != diagnostic["digest"]:
            raise ResearchGateError(
                f"checkpoint event digest disagrees with diagnostics at tick "
                f"{row['tick']}"
            )
        for field in (
            "max_material_abs_residual",
            "max_material_tolerance_ratio",
            "max_cash_abs_residual",
            "max_cash_tolerance_ratio",
        ):
            if field not in details or not isinstance(details[field], (int, float)) or isinstance(
                details[field], bool
            ):
                raise ResearchGateError(
                    f"checkpoint event {field} is not a JSON number at tick "
                    f"{row['tick']}"
                )
            if not math.isfinite(float(details[field])):
                raise ResearchGateError(
                    f"checkpoint event {field} is not finite at tick {row['tick']}"
                )
            if abs(float(details[field]) - float(diagnostic[field])) > 1e-12:
                raise ResearchGateError(
                    f"checkpoint event {field} disagrees with diagnostics at tick "
                    f"{row['tick']}"
                )

    history = Toy4History(
        aggregate_rows=frames["aggregates"].to_dicts(),
        national_rows=frames["national_accounts"].to_dicts(),
        budget_rows=frames["household_budgets"].to_dicts(),
        diagnostic_rows=diagnostics.to_dicts(),
        event_rows=frames["events"].to_dicts(),
        digest_chain=chain,
    )
    rng = RngRegistry.from_snapshot(metadata.get("rng_snapshot"))
    if rng.seed != snapshot_scenario.seed:
        raise ResearchGateError(
            "checkpoint RNG seed disagrees with the snapshot scenario"
        )
    expected_rng = RngRegistry(snapshot_scenario.seed)
    if snapshot_scenario.stochastic:
        expected_rng.uniform("toy4.initial_households", snapshot_scenario.households)
    if rng.snapshot() != expected_rng.snapshot():
        raise ResearchGateError(
            "checkpoint RNG snapshot does not match the Toy-4 initialization profile "
            "(module set, draw counts or PCG64 position)"
        )
    return state, history, rng, metadata


def _hash_vector(vector: dict[str, float]) -> str:
    from hsm_lab.provenance.manifest import compute_parameter_hash

    return compute_parameter_hash(vector)


def next_quarter_of(spec: ScenarioSpec, completed_ticks: int) -> str:
    return str(spec.start.advance(completed_ticks))
