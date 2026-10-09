"""Declared parameter-axis sweeps for the P05 gate metrics.

The E4/E5 work needed one thing repeatedly: run the historical replay baseline
with exactly one declared input changed and read the frozen acceptance metrics
off the result.  Doing that from throwaway scripts meant the evidence could not
be re-checked, so the sweep lives here.

Two axes exist because they are the two levers the diagnosis points at:

``credit_envelope_fraction``
    the working-capital envelope the banks size for wages + input orders +
    investment; at 0.5 the producers fund only ~61% of their input orders.
``transport_capacity_scale``
    a *diagnostic* multiplier on the declared transport sector capacity
    (``F2_TRANSPORT_CAPACITY_TOTAL``).  The engine reads that constant when it
    builds the initial conditions, so the multiplier is applied as a scoped
    monkeypatch and is **not** a model parameter: adopting a value must go
    through the parameter registry, not through this tool.

Neither axis is a fix on its own — the measured results are in
``docs/phases/P05_REPORT.md`` §E6 — the tool exists so the numbers can be
reproduced.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from hsm_lab.provenance.manifest import canonical_digest

AXES = (
    "credit_envelope_fraction",
    "input_credit_earmark_fraction",
    "transport_capacity_scale",
    "interest_sink_remittance_fraction",
    "fiscal_turnover_remittance_fraction",
    "bailout_envelope_fraction",
    "wage_rate",
    "service_split.0",
    "service_split.1",
    "service_split.2",
    "handling_work_per_unit.scale",
    "trade.cmea_export_demands.scale",
    "trade.convertible_export_demands.scale",
)


@dataclass
class AxisPoint:
    """One swept value and the frozen gate metrics measured at it."""

    value: float
    status: str
    ticks: int
    liveness: float
    production_first_10: float
    production_last_10: float
    household_consumption_last_10: float
    treasury_cash_tick_115: float | None
    rescue_grants_last_20: float | None
    terminal_t1_pass: bool
    terminal_t2_pass: bool
    terminal_t3_pass: bool
    terminal_floor_pass: bool
    expired_services_tail: float
    treasury_zero_tick: int | None
    allocated_total: float
    delivered_total: float
    physical_blocked_total: float
    financial_blocked_total: float
    output_dir: str
    parameter_hash: str = ""
    seed: int = 0
    intervention_hash: str = ""
    deterministic_replay_digest: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = dict(self.__dict__)
        payload.pop("extras", None)
        return payload


@contextmanager
def _noop_context() -> Iterator[None]:
    yield None


@contextmanager
def _transport_capacity_scaled(scale: float) -> Iterator[float]:
    """Scale the declared transport capacity for the duration of the block."""
    from hsm_lab.engine import initial

    original = float(initial.F2_TRANSPORT_CAPACITY_TOTAL)
    initial.F2_TRANSPORT_CAPACITY_TOTAL = original * float(scale)
    try:
        yield original
    finally:
        initial.F2_TRANSPORT_CAPACITY_TOTAL = original


def _gate_metrics(
    output_dir: Path, terminal_floor: dict[str, Any] | None = None
) -> dict[str, Any]:
    if terminal_floor is None:
        root = Path(__file__).resolve().parents[3]
        control = json.loads((root / "config/calibration/p05.json").read_text())
        terminal_floor = control["gates"]["terminal_floor"]
    national = pl.read_parquet(output_dir / "national_accounts.parquet")
    aggregates = pl.read_parquet(output_dir / "aggregates.parquet")
    diagnostics = pl.read_parquet(output_dir / "tick_diagnostics.parquet").sort("tick")
    production = (
        national.group_by("tick")
        .agg(pl.col("production").sum())
        .sort("tick")["production"]
        .to_numpy()
        .astype(np.float64)
    )
    household = (
        national.group_by("tick")
        .agg(pl.col("household_consumption").sum())
        .sort("tick")["household_consumption"]
        .to_numpy()
        .astype(np.float64)
    )
    expired = diagnostics["expired_services"].to_numpy().astype(np.float64)
    treasury = np.zeros(0, dtype=np.float64)
    treasury_tick_115: float | None = None
    rescue_grants: float | None = None
    financial = output_dir / "financial_accounts.parquet"
    if financial.exists():
        selected = (
            pl.read_parquet(financial)
            .filter(pl.col("account_label") == "treasury_cash")
            .sort("tick")
        )
        if selected.height:
            treasury = selected["closing"].to_numpy().astype(np.float64)
            terminal_tick = int(terminal_floor["t3_treasury_solvent_tick"])
            at_terminal = selected.filter(pl.col("tick") == terminal_tick)
            if at_terminal.height:
                treasury_tick_115 = float(at_terminal["closing"][0])
            max_tick = int(selected["tick"].max())
            lookback = int(terminal_floor["t3_rescue_grants_lookback_ticks"])
            rescue_grants = float(
                selected.filter(pl.col("tick") >= max_tick - lookback + 1)["grant"]
                .fill_null(0.0)
                .abs()
                .sum()
            )
    broke = treasury.size > 0 and bool((treasury <= 1e-9).any())
    zero_tick = int(np.argmax(treasury <= 1e-9)) if broke else None
    first = float(production[:10].mean()) if production.size >= 10 else float(production.mean())
    last = float(production[-10:].mean()) if production.size >= 10 else float(production.mean())
    household_last = (
        float(household[-10:].mean()) if household.size >= 10 else float(household.mean())
    )
    t1 = last >= float(terminal_floor["t1_production_last_10_min"])
    t2 = household_last >= float(terminal_floor["t2_household_consumption_last_10_min"])
    t3 = (
        treasury_tick_115 is not None and treasury_tick_115 >= -1e-9
    ) or (rescue_grants is not None and rescue_grants <= 1e-9)
    return {
        "liveness": float(last / first) if first > 0.0 else 0.0,
        "production_first_10": first,
        "production_last_10": last,
        "household_consumption_last_10": household_last,
        "treasury_cash_tick_115": treasury_tick_115,
        "rescue_grants_last_20": rescue_grants,
        "terminal_t1_pass": t1,
        "terminal_t2_pass": t2,
        "terminal_t3_pass": t3,
        "terminal_floor_pass": bool(t1 and t2 and t3),
        "expired_services_tail": (
            float(expired[40:].mean()) if expired.size > 40 else float(expired.mean())
        ),
        "treasury_zero_tick": zero_tick,
        "allocated_total": float(aggregates["allocated"].sum()),
        "delivered_total": float(aggregates["delivered"].sum()),
        "physical_blocked_total": float(aggregates["physical_delivery_blocked"].sum()),
        "financial_blocked_total": float(aggregates["financial_delivery_blocked"].sum()),
    }


def run_axis_sweep(
    spec: Any,
    contract: Any,
    registry: Any,
    *,
    axis: str,
    points: list[float],
    output_root: Path,
    terminal_floor: dict[str, Any],
) -> list[AxisPoint]:
    """Run the scenario once per value of one declared axis."""
    if axis not in AXES:
        raise ValueError(f"unknown axis {axis!r}; expected one of {AXES}")
    from hsm_lab.engine.material import run_material

    results: list[AxisPoint] = []
    for value in points:
        label = f"{axis}-{value:g}".replace(".", "p")
        output_dir = Path(output_root) / label
        context = (
            _transport_capacity_scaled(value)
            if axis == "transport_capacity_scale"
            else _noop_context()
        )
        with context:
            scenario = spec
            if axis == "credit_envelope_fraction":
                scenario = spec.model_copy(
                    update={
                        "material_parameters": spec.material_parameters.model_copy(
                            update={"credit_envelope_fraction": float(value)}
                        )
                    }
                )
            elif axis in (
                "input_credit_earmark_fraction",
                "interest_sink_remittance_fraction",
                "fiscal_turnover_remittance_fraction",
                "bailout_envelope_fraction",
                "wage_rate",
            ):
                scenario = spec.model_copy(
                    update={
                        "material_parameters": spec.material_parameters.model_copy(
                            update={axis: float(value)}
                        )
                    }
                )
            elif axis.startswith("service_split."):
                index = int(axis.rsplit(".", 1)[1])
                split = list(spec.material_parameters.service_split)
                old_value = split[index]
                delta = float(value) - old_value
                other_indices = [i for i in range(3) if i != index]
                other_total = sum(split[i] for i in other_indices)
                if float(value) < 0.0 or delta > other_total:
                    raise ValueError(f"{axis}={value:g} cannot preserve service_split shares")
                split[index] = float(value)
                if other_total:
                    for i in other_indices:
                        split[i] -= delta * split[i] / other_total
                scenario = spec.model_copy(
                    update={
                        "material_parameters": spec.material_parameters.model_copy(
                            update={"service_split": split}
                        )
                    }
                )
            elif axis == "handling_work_per_unit.scale":
                baseline = list(spec.material_parameters.handling_work_per_unit)
                scenario = spec.model_copy(
                    update={
                        "material_parameters": spec.material_parameters.model_copy(
                            update={"handling_work_per_unit": [x * float(value) for x in baseline]}
                        )
                    }
                )
            elif axis in (
                "trade.cmea_export_demands.scale",
                "trade.convertible_export_demands.scale",
            ):
                key = axis.rsplit(".", 2)[1]
                trade = spec.material_parameters.trade.model_copy(
                    update={
                        key: [
                            x * float(value)
                            for x in getattr(spec.material_parameters.trade, key)
                        ]
                    }
                )
                scenario = spec.model_copy(
                    update={
                        "material_parameters": spec.material_parameters.model_copy(
                            update={"trade": trade}
                        )
                    }
                )
        intervention_hash = canonical_digest({"axis": axis, "value": float(value)})
        run = run_material(scenario, output_dir, contract, registry, checkpoint_every=0)
        metrics = _gate_metrics(output_dir, terminal_floor)
        results.append(
            AxisPoint(
                value=float(value),
                status=str(run.status),
                ticks=int(run.completed_ticks),
                output_dir=str(output_dir),
                parameter_hash=str(run.parameter_hash),
                seed=int(spec.seed),
                intervention_hash=intervention_hash,
                deterministic_replay_digest=str(run.deterministic_replay_digest),
                **metrics,
            )
        )
    return results
