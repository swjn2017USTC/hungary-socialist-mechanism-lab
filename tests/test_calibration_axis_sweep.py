"""Tests for the declared axis-sweep tool."""

from __future__ import annotations

import polars as pl
import pytest

from hsm_lab.calibration.axis_sweep import _gate_metrics, run_axis_sweep


def _write_run(root, *, production: list[float], treasury: list[float]) -> None:
    ticks = list(range(len(production)))
    pl.DataFrame({"tick": ticks, "production": production}).write_parquet(
        root / "national_accounts.parquet"
    )
    pl.DataFrame(
        {
            "allocated": [10.0] * len(ticks),
            "delivered": [6.0] * len(ticks),
            "physical_delivery_blocked": [3.5] * len(ticks),
            "financial_delivery_blocked": [0.5] * len(ticks),
        }
    ).write_parquet(root / "aggregates.parquet")
    pl.DataFrame({"tick": ticks, "expired_services": [4.0] * len(ticks)}).write_parquet(
        root / "tick_diagnostics.parquet"
    )
    pl.DataFrame(
        {
            "tick": ticks,
            "account_label": ["treasury_cash"] * len(ticks),
            "closing": treasury,
        }
    ).write_parquet(root / "financial_accounts.parquet")


def test_gate_metrics_reads_the_frozen_series(tmp_path) -> None:
    production = [100.0] * 10 + [50.0] * 10
    treasury = [5.0, 5.0, 0.0] + [5.0] * 17
    _write_run(tmp_path, production=production, treasury=treasury)

    metrics = _gate_metrics(tmp_path)

    assert metrics["liveness"] == pytest.approx(0.5)
    assert metrics["production_first_10"] == pytest.approx(100.0)
    assert metrics["production_last_10"] == pytest.approx(50.0)
    assert metrics["treasury_zero_tick"] == 2
    assert metrics["allocated_total"] == pytest.approx(200.0)
    assert metrics["delivered_total"] == pytest.approx(120.0)
    assert metrics["physical_blocked_total"] == pytest.approx(70.0)
    assert metrics["financial_blocked_total"] == pytest.approx(10.0)


def test_gate_metrics_reports_no_treasury_zero_when_solvent(tmp_path) -> None:
    _write_run(tmp_path, production=[10.0] * 20, treasury=[1.0] * 20)

    metrics = _gate_metrics(tmp_path)

    assert metrics["treasury_zero_tick"] is None
    assert metrics["liveness"] == pytest.approx(1.0)


def test_unknown_axis_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="unknown axis"):
        run_axis_sweep(
            None, None, None, axis="not_an_axis", points=[1.0], output_root=tmp_path
        )
