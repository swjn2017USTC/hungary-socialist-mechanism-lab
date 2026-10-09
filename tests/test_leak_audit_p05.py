"""Circuit observations must close and preserve the authoritative replay."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import polars as pl
import pytest

from hsm_lab.calibration.leak_audit import (
    money_flow_residual,
    money_snapshot,
    run_leak_audit,
)
from hsm_lab.contract.guards import load_research_contract, load_scenario, sha256_file
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine import material

ROOT = Path(__file__).resolve().parents[1]


def test_money_definition_counts_the_fund_only_once() -> None:
    state = SimpleNamespace(
        household_weight=np.array([2.0]),
        household_cash=np.array([10.0]),
        organization_cash=np.array([30.0, 0.0]),
        organization_bank=np.array([0, -1]),
        treasury_deposit=40.0,
        credit_fund=50.0,
        bank_deposit_liability=np.array([140.0]),
        bank_reserves=np.array([140.0]),
        bank_equity=np.array([0.0]),
        bank_loan_asset=np.array([0.0]),
        organization_principal=np.array([0.0]),
        organization_wage_arrears=np.array([0.0]),
    )
    observed = money_snapshot(state)
    assert observed["money_total"] == 140.0
    assert observed["deposit_composition_residual"] == 0.0


def test_money_identity_distinguishes_neutral_credit_and_interest_sink() -> None:
    assert money_flow_residual(100, 127, 40, 10, 3, neutral=False) == 0.0
    assert money_flow_residual(100, 97, 40, 10, 3, neutral=True) == 0.0
    assert money_flow_residual(100, 130, 40, 10, 3, neutral=False, remitted=3) == 0.0


def test_observer_preserves_eight_tick_replay_and_closes_every_circuit(tmp_path) -> None:
    spec = load_scenario(ROOT, "historical_f2_replay")
    contract = load_research_contract(ROOT)
    registry = DataRegistry.load(ROOT, allowed_commodities=spec.commodities)
    original_tick = material.tick_material
    baseline = material.run_material(
        spec, tmp_path / "baseline", contract, registry, until="1958Q4"
    )
    observed = run_leak_audit(
        spec, contract, registry, output_dir=tmp_path / "audit", until="1958Q4"
    )
    assert material.tick_material is original_tick
    assert observed["completed_ticks"] == 8
    assert observed["deterministic_replay_digest"] == baseline.deterministic_replay_digest
    assert observed["rng_draws_count"] == baseline.rng_draws_count
    for name in baseline.output_hashes:
        if name.endswith(".parquet"):
            assert sha256_file(tmp_path / "baseline" / name) == sha256_file(
                tmp_path / "audit" / name
            )
    for name in (
        "max_money_flow_residual",
        "max_deposit_composition_residual",
        "max_household_cash_residual",
        "max_treasury_cash_residual",
        "max_commodity_balance_residual",
        "max_expiry_reconciliation_residual",
    ):
        assert observed[name] < 1e-6
    expiry = pl.read_parquet(tmp_path / "audit" / "service_expiry.parquet")
    assert set(expiry["commodity_id"]) == {
        "g03_electricity_heat",
        "g15_market_services",
        "g16_housing_public_services",
    }


def test_observer_restores_the_tick_hook_when_runner_raises(tmp_path, monkeypatch) -> None:
    spec = load_scenario(ROOT, "historical_f2_replay")
    original_tick = material.tick_material

    def fail(*args, **kwargs):
        raise RuntimeError("deliberate preflight failure")

    monkeypatch.setattr(material, "run_material", fail)
    with pytest.raises(RuntimeError, match="deliberate preflight"):
        run_leak_audit(spec, None, None, output_dir=tmp_path / "audit")
    assert material.tick_material is original_tick
