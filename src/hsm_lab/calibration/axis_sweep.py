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

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

AXES = (
    "credit_envelope_fraction",
    "input_credit_earmark_fraction",
    "transport_capacity_scale",
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
    expired_services_tail: float
    treasury_zero_tick: int | None
    allocated_total: float
    delivered_total: float
    physical_blocked_total: float
    financial_blocked_total: float
    output_dir: str
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


def _gate_metrics(output_dir: Path) -> dict[str, Any]:
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
    expired = diagnostics["expired_services"].to_numpy().astype(np.float64)
    treasury = np.zeros(0, dtype=np.float64)
    financial = output_dir / "financial_accounts.parquet"
    if financial.exists():
        selected = (
            pl.read_parquet(financial)
            .filter(pl.col("account_label") == "treasury_cash")
            .sort("tick")
        )
        if selected.height:
            treasury = selected["closing"].to_numpy().astype(np.float64)
    broke = treasury.size > 0 and bool((treasury <= 1e-9).any())
    zero_tick = int(np.argmax(treasury <= 1e-9)) if broke else None
    first = float(production[:10].mean()) if production.size >= 10 else float(production.mean())
    last = float(production[-10:].mean()) if production.size >= 10 else float(production.mean())
    return {
        "liveness": float(last / first) if first > 0.0 else 0.0,
        "production_first_10": first,
        "production_last_10": last,
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
            elif axis == "input_credit_earmark_fraction":
                scenario = spec.model_copy(
                    update={
                        "material_parameters": spec.material_parameters.model_copy(
                            update={"input_credit_earmark_fraction": float(value)}
                        )
                    }
                )
            run = run_material(scenario, output_dir, contract, registry, checkpoint_every=0)
        metrics = _gate_metrics(output_dir)
        results.append(
            AxisPoint(
                value=float(value),
                status=str(run.status),
                ticks=int(run.completed_ticks),
                output_dir=str(output_dir),
                **metrics,
            )
        )
    return results
