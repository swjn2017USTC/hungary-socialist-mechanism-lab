"""P05 §0 closure-audit tests: aggregate LP certificate and kernel diagnostic."""

from __future__ import annotations

from pathlib import Path

from hsm_lab.calibration.closure import (
    PERIODIC_TOLERANCE,
    ClosureCertificate,
    diagnose_kernel_closure,
    physical_feasibility_lambda,
)
from hsm_lab.contract.guards import load_research_contract, load_scenario

ROOT = Path(__file__).resolve().parents[1]


def test_aggregate_lp_is_feasible_for_the_declared_capacity() -> None:
    contract = load_research_contract(ROOT)
    spec = load_scenario(ROOT, "intermediate8")
    result = physical_feasibility_lambda(spec, contract)
    assert result["status"] == "ok"
    # the declared capacity/labor can meet the whole declared basket periodically
    assert result["lambda_common"] >= 0.5
    assert result["lambda_ok"] is True


def test_kernel_diagnostic_reports_a_periodicity_verdict() -> None:
    contract = load_research_contract(ROOT)
    spec = load_scenario(ROOT, "intermediate8")
    certificate = diagnose_kernel_closure(spec, contract, diagnostic_ticks=8)
    assert isinstance(certificate, ClosureCertificate)
    assert certificate.diagnostic_ticks == 8
    assert certificate.periodic_tolerance == PERIODIC_TOLERANCE
    assert set(certificate.periodic_residuals) == {"output", "stock", "cash"}
    assert certificate.max_periodic_residual >= 0.0
    assert 0.0 <= certificate.output_liveness <= 1.0
    assert all(row["tick"] < 8 for row in certificate.diagnostic_rows)


def test_fallback_edges_exist_and_keep_declared_suppliers_at_two() -> None:
    import numpy as np

    from hsm_lab.engine.initial import build_material_initial_conditions
    from hsm_lab.engine.network import build_material_network
    from hsm_lab.engine.rng import RngRegistry

    contract = load_research_contract(ROOT)
    spec = load_scenario(ROOT, "intermediate8")
    initial = build_material_initial_conditions(spec, RngRegistry(spec.seed))
    network = build_material_network(spec, contract, initial)
    fallback = np.asarray(network.edge_is_fallback, dtype=bool)
    assert bool(fallback.any())
    demand = np.asarray(network.edge_demand, dtype=np.int64)
    declared = ~fallback
    counts = np.bincount(demand[declared], minlength=int(demand.max()) + 1)
    assert int(counts.max()) <= 2
    # every demand with fallback edges still weights them to one
    fb_sums = np.bincount(
        demand[fallback], weights=np.asarray(network.edge_weight)[fallback]
    )
    served = fb_sums > 0.0
    assert bool(np.all(np.abs(fb_sums[served] - 1.0) <= 1e-9))


def test_certified_price_diagnostic_runs_without_cash_overdraft() -> None:
    contract = load_research_contract(ROOT)
    spec = load_scenario(ROOT, "intermediate8")
    # Exercises the household budget bound and the per-household second-economy
    # funding cap: under cost-recovery prices the raw channels would overrun
    # household cash and fail the accounting gate.
    certificate = diagnose_kernel_closure(
        spec, contract, diagnostic_ticks=16, use_certified_prices=True
    )
    assert certificate.certified_prices is not None
    assert certificate.max_periodic_residual >= 0.0


def test_certified_cost_recovery_prices_are_finite_and_positive() -> None:
    from hsm_lab.calibration.closure import certified_cost_recovery_prices
    from hsm_lab.engine.initial import build_material_initial_conditions
    from hsm_lab.engine.network import build_material_network
    from hsm_lab.engine.rng import RngRegistry
    from hsm_lab.engine.state import initialize_material

    contract = load_research_contract(ROOT)
    spec = load_scenario(ROOT, "intermediate8")
    initial = build_material_initial_conditions(spec, RngRegistry(spec.seed))
    network = build_material_network(spec, contract, initial)
    state = initialize_material(spec, initial, network)
    prices = certified_cost_recovery_prices(spec, network, state)
    assert prices is not None
    assert len(prices) == len(network.commodity_ids)
    assert all(value > 0.0 for value in prices)
