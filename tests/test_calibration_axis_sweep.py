"""Tests for the declared axis-sweep tool."""

from __future__ import annotations

from types import SimpleNamespace

import polars as pl
import pytest

from hsm_lab.calibration import axis_sweep
from hsm_lab.calibration.axis_sweep import _gate_metrics, run_axis_sweep


def _write_run(root, *, production: list[float], treasury: list[float]) -> None:
    ticks = list(range(len(production)))
    pl.DataFrame(
        {
            "tick": ticks,
            "production": production,
            "household_consumption": [20.0] * len(ticks),
        }
    ).write_parquet(
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
            "grant": [0.0] * len(ticks),
        }
    ).write_parquet(root / "financial_accounts.parquet")


def test_gate_metrics_reads_the_frozen_series(tmp_path) -> None:
    production = [100.0] * 10 + [50.0] * 10
    treasury = [5.0, 5.0, 0.0] + [5.0] * 17
    _write_run(tmp_path, production=production, treasury=treasury)

    floors = {
        "t1_production_last_10_min": 50,
        "t2_household_consumption_last_10_min": 20,
        "t3_treasury_solvent_tick": 19,
        "t3_rescue_grants_lookback_ticks": 20,
    }
    metrics = _gate_metrics(tmp_path, floors)

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

    floors = {
        "t1_production_last_10_min": 50,
        "t2_household_consumption_last_10_min": 20,
        "t3_treasury_solvent_tick": 19,
        "t3_rescue_grants_lookback_ticks": 20,
    }
    metrics = _gate_metrics(tmp_path, floors)

    assert metrics["treasury_zero_tick"] is None
    assert metrics["liveness"] == pytest.approx(1.0)


def test_unknown_axis_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="unknown axis"):
        run_axis_sweep(
            None,
            None,
            None,
            axis="not_an_axis",
            points=[1.0],
            output_root=tmp_path,
            terminal_floor={},
        )


def test_input_credit_earmark_axis_updates_the_declared_parameter(tmp_path, monkeypatch) -> None:
    parameters = SimpleNamespace(input_credit_earmark_fraction=0.0)
    spec = SimpleNamespace(
        material_parameters=parameters,
        seed=0,
        model_copy=lambda *, update: SimpleNamespace(
            material_parameters=update["material_parameters"]
        ),
    )
    parameters.model_copy = lambda *, update: SimpleNamespace(**update)
    observed = []

    def fake_run(scenario, output_dir, contract, registry, *, checkpoint_every):
        observed.append(scenario.material_parameters.input_credit_earmark_fraction)
        return SimpleNamespace(
            status="completed",
            completed_ticks=116,
            parameter_hash="parameter-hash",
            deterministic_replay_digest="replay-digest",
        )

    monkeypatch.setattr(
        axis_sweep,
        "_gate_metrics",
        lambda _output_dir, _terminal_floor: {
            "liveness": 0.1,
            "production_first_10": 1.0,
            "production_last_10": 0.1,
            "household_consumption_last_10": 0.1,
            "treasury_cash_tick_115": None,
            "rescue_grants_last_20": None,
            "terminal_t1_pass": False,
            "terminal_t2_pass": False,
            "terminal_t3_pass": False,
            "terminal_floor_pass": False,
            "expired_services_tail": 0.0,
            "treasury_zero_tick": 1,
            "allocated_total": 1.0,
            "delivered_total": 0.5,
            "physical_blocked_total": 0.5,
            "financial_blocked_total": 0.0,
        },
    )
    monkeypatch.setattr("hsm_lab.engine.material.run_material", fake_run)

    points = run_axis_sweep(
        spec, None, None, axis="input_credit_earmark_fraction", points=[0.25], output_root=tmp_path,
        terminal_floor={
            "t1_production_last_10_min": 35092,
            "t2_household_consumption_last_10_min": 2085,
            "t3_treasury_solvent_tick": 115,
            "t3_rescue_grants_lookback_ticks": 20,
        },
    )

    assert observed == [0.25]
    assert points[0].ticks == 116
    assert points[0].parameter_hash == "parameter-hash"
    assert points[0].seed == 0
    assert points[0].intervention_hash
    assert points[0].deterministic_replay_digest == "replay-digest"


@pytest.mark.parametrize(
    "axis",
    [
        "bailout_envelope_fraction",
        "wage_rate",
        "service_split.0",
        "service_split.1",
        "service_split.2",
        "handling_work_per_unit.scale",
        "trade.cmea_export_demands.scale",
        "trade.convertible_export_demands.scale",
    ],
)
def test_declared_structural_axes_are_registered(axis) -> None:
    assert axis in axis_sweep.AXES
