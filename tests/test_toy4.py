"""P01 regression: kernel accounting, rationing rules, forcing gates, runner."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.contract.schemas import (
    ConfigError,
    ResearchGateError,
    ScenarioSpec,
    Toy4Parameters,
)
from hsm_lab.engine.accounting import check_toy4_invariants, snapshot_opening_stocks
from hsm_lab.engine.state import (
    Toy4Forcing,
    Toy4State,
    produce_leontief,
    tick_toy4,
)
from tests.conftest import REPO_ROOT, load_json

COMMODITIES = ["energy", "capital_goods", "food", "consumer_goods"]
FOOD = 2


@pytest.fixture()
def contract():
    return load_research_contract(REPO_ROOT)


@pytest.fixture()
def spec(contract):
    return load_scenario(REPO_ROOT, "toy4")


@pytest.fixture()
def registry(spec):
    from hsm_lab.data.registry import DataRegistry

    return DataRegistry.load(REPO_ROOT, allowed_commodities=spec.commodities)


def base_parameters(**overrides) -> Toy4Parameters:
    spec = load_scenario(REPO_ROOT, "toy4")
    assert spec.toy4_parameters is not None
    return spec.toy4_parameters.model_copy(update=overrides)

def kernel_state(**overrides) -> Toy4State:
    """1 food-producing organization / 1 region; G stays 4, N/E overridable."""
    n = overrides.get("household_id", np.arange(2, dtype=np.int64)).shape[0]
    defaults = dict(
        schema_version="toy4-state-v1",
        completed_ticks=0,
        household_id=np.arange(n, dtype=np.int64),
        household_region=np.zeros(n, dtype=np.int32),
        household_weight=np.full(n, 5.0 / 6.0),
        household_size=np.full(n, 3.0),
        household_cash=np.zeros(n),
        organization_id=np.arange(1, dtype=np.int64),
        organization_region=np.zeros(1, dtype=np.int32),
        organization_output_sector=np.array([FOOD], dtype=np.int32),
        organization_capacity=np.array([3.0]),
        organization_labor_capacity=np.array([3.0]),
        organization_input_coefficients=np.array([[0.0, 0.0, 4.0 / 3.0, 0.0]]),
        organization_output_mix=np.array([[0.0, 0.0, 1.0, 0.0]]),
        organization_input_inventory=np.array([[0.0, 0.0, 3.0, 0.0]]),
        wholesale_inventory=np.array([0.0, 0.0, 3.0, 0.0]),
        retail_inventory=np.array([[0.0, 0.0, 4.0, 0.0]]),
        region_equivalent_persons=np.array([5.0]),
        regional_share=np.array([1.0]),
    )
    defaults.update(overrides)
    return Toy4State(**defaults)


def one_quarter_forcing(imports, exports) -> Toy4Forcing:
    return Toy4Forcing(
        quarters=["1957Q1"],
        imports=np.array([imports], dtype=np.float64),
        export_orders=np.array([exports], dtype=np.float64),
        input_artifact_hashes={},
    )


def kernel_tick(state, parameters, imports=(0, 0, 2.0, 0), exports=(0, 0, 1.0, 0)):
    return tick_toy4(state, one_quarter_forcing(imports, exports), parameters)


# ---------------------------------------------------------------------------
# Kernel reference arithmetic (plan Verification, first bullet)
def test_kernel_reference_transfers_match_plan_arithmetic() -> None:
    """Opening stock 10 + imports 2 + production 3 - input use 4 - exports 1
    - weighted consumption 5 -> closing global stock 5, per ledger."""
    parameters = base_parameters(desired_per_person=[0, 0, 1, 0], target_utilization=1.0)
    state = kernel_state()
    flows = kernel_tick(state, parameters)

    total_close = (
        state.wholesale_inventory.sum()
        + state.organization_input_inventory.sum()
        + state.retail_inventory.sum()
    )
    assert total_close == pytest.approx(5.0, abs=1e-9)
    assert flows.organization_realized[0] == pytest.approx(3.0)
    assert flows.used_input[0, FOOD] == pytest.approx(4.0)
    assert flows.retail_sales[0, FOOD] == pytest.approx(5.0)
    assert flows.export_realized[FOOD] == pytest.approx(1.0)
    # Per-ledger transfers, not just the global identity.
    assert state.organization_input_inventory[0, FOOD] == pytest.approx(0.0, abs=1e-9)
    assert state.wholesale_inventory[FOOD] == pytest.approx(0.0, abs=1e-9)
    assert state.retail_inventory[0, FOOD] == pytest.approx(5.0, abs=1e-9)
    assert flows.delivered_input[0, FOOD] == pytest.approx(1.0)
    # WafterExport(food) = (3+2-1+3) - 1 = 6 is fully released to retail.
    assert flows.retail_incoming[0, FOOD] == pytest.approx(6.0)
    # Each household: income 18, spending 2*3 = 6.
    assert flows.household_cash_close.tolist() == [12.0, 12.0]


def test_leontief_boundaries() -> None:
    y, used = produce_leontief(
        np.array([[6.0, 10.0, 0.0, 0.0]]),
        np.array([[2.0, 1.0, 0.0, 0.0]]),
        np.array([10.0]),
    )
    assert y[0] == pytest.approx(3.0)
    assert used.tolist() == [[6.0, 3.0, 0.0, 0.0]]
    # Zero coefficients never limit; all-required-zero input means y = 0.
    y_zero_coeff, _ = produce_leontief(
        np.array([[100.0, 100.0, 0.0, 0.0]]),
        np.array([[0.0, 0.0, 0.0, 0.0]]),
        np.array([10.0]),
    )
    assert y_zero_coeff[0] == pytest.approx(10.0)
    y_zero_input, _ = produce_leontief(
        np.array([[0.0, 0.0, 0.0, 0.0]]),
        np.array([[2.0, 1.0, 0.0, 0.0]]),
        np.array([10.0]),
    )
    assert y_zero_input[0] == pytest.approx(0.0)


def test_same_tick_output_cannot_feed_second_organization() -> None:
    """Org B orders energy this tick; org A's same-tick output is not in the
    pre-production wholesale pool B allocates from."""
    parameters = base_parameters()
    state = kernel_state(
        household_id=np.arange(1, dtype=np.int64),
        household_weight=np.array([1.0]),
        organization_id=np.arange(2, dtype=np.int64),
        organization_region=np.zeros(2, dtype=np.int32),
        organization_output_sector=np.array([0, 1], dtype=np.int32),
        organization_capacity=np.array([100.0, 100.0]),
        organization_labor_capacity=np.array([100.0, 100.0]),
        organization_input_coefficients=np.array(
            [[0.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]]
        ),
        organization_output_mix=np.array(
            [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]
        ),
        organization_input_inventory=np.zeros((2, 4)),
        wholesale_inventory=np.zeros(4),
        retail_inventory=np.zeros((1, 4)),
        region_equivalent_persons=np.array([3.0]),
        regional_share=np.array([1.0]),
    )
    flows = kernel_tick(state, parameters)
    # The capital-goods org ordered 0.9*100 energy but pre-production wholesale
    # was empty: it received nothing even though the energy org produced 90 of
    # energy during this very tick.
    assert flows.ordered_input[1, 0] == pytest.approx(90.0)
    assert flows.delivered_input[1, 0] == pytest.approx(0.0)
    assert flows.organization_output[0, 0] == pytest.approx(90.0)
    # A's output enters wholesale only after allocation; 20% is then released.
    assert state.wholesale_inventory[0] == pytest.approx(90.0 * (1.0 - 0.2))
    assert flows.retail_incoming[0, 0] == pytest.approx(18.0)


def test_organization_storage_order_permutation_invariance() -> None:
    """Same organization IDs and parameters in a different storage order give
    identical per-ID results up to accounting tolerance."""
    parameters = base_parameters()
    ids = np.array([5, 7], dtype=np.int64)
    shared = dict(
        household_id=np.arange(2, dtype=np.int64),
        household_region=np.array([0, 1], dtype=np.int32),
        household_weight=np.array([1.0, 1.0]),
        regional_share=np.array([0.5, 0.5]),
        region_equivalent_persons=np.array([3.0, 3.0]),
        wholesale_inventory=np.array([50.0, 50.0, 20.0, 20.0]),
        retail_inventory=np.zeros((2, 4)),
    )
    forward = kernel_state(
        organization_id=ids,
        organization_region=np.array([0, 1], dtype=np.int32),
        organization_output_sector=np.array([0, FOOD], dtype=np.int32),
        organization_capacity=np.array([10.0, 3.0]),
        organization_labor_capacity=np.array([10.0, 3.0]),
        organization_input_coefficients=np.array(
            [[0.1, 0.0, 0.0, 0.0], [0.0, 0.0, 4.0 / 3.0, 0.0]]
        ),
        organization_output_mix=np.array(
            [[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]]
        ),
        organization_input_inventory=np.array(
            [[0.5, 0.0, 0.0, 0.0], [0.0, 0.0, 3.0, 0.0]]
        ),
        **shared,
    )
    backward = kernel_state(
        organization_id=ids[::-1].copy(),
        organization_region=np.array([1, 0], dtype=np.int32),
        organization_output_sector=np.array([FOOD, 0], dtype=np.int32),
        organization_capacity=np.array([3.0, 10.0]),
        organization_labor_capacity=np.array([3.0, 10.0]),
        organization_input_coefficients=np.array(
            [[0.0, 0.0, 4.0 / 3.0, 0.0], [0.1, 0.0, 0.0, 0.0]]
        ),
        organization_output_mix=np.array(
            [[0.0, 0.0, 1.0, 0.0], [1.0, 0.0, 0.0, 0.0]]
        ),
        organization_input_inventory=np.array(
            [[0.0, 0.0, 3.0, 0.0], [0.5, 0.0, 0.0, 0.0]]
        ),
        **shared,
    )
    flows_forward = kernel_tick(forward, parameters)
    flows_backward = kernel_tick(backward, parameters)
    for index, oid in enumerate(ids.tolist()):
        row_b = int(np.flatnonzero(backward.organization_id == oid)[0])
        assert flows_forward.organization_realized[index] == pytest.approx(
            flows_backward.organization_realized[row_b], abs=1e-9
        )
        np.testing.assert_allclose(
            flows_forward.organization_output[index],
            flows_backward.organization_output[row_b],
            atol=1e-9,
        )
    np.testing.assert_allclose(
        forward.wholesale_inventory, backward.wholesale_inventory, atol=1e-9
    )
    np.testing.assert_allclose(
        forward.retail_inventory, backward.retail_inventory, atol=1e-9
    )


# ---------------------------------------------------------------------------
# Household rules (plan Verification, household bullets)
# ---------------------------------------------------------------------------


def household_state(retail_food: float, weights, desired_pp) -> Toy4State:
    n = len(weights)
    return kernel_state(
        household_id=np.arange(n, dtype=np.int64),
        household_region=np.zeros(n, dtype=np.int32),
        household_weight=np.array(weights, dtype=np.float64),
        household_size=np.full(n, 3.0),
        retail_inventory=np.array([[0.0, 0.0, retail_food, 0.0]]),
    )


def test_household_budget_scales_desired_to_income() -> None:
    parameters = base_parameters()
    state = household_state(1e4, [1.0], parameters.desired_per_person)
    flows = kernel_tick(state, parameters)
    cost = 1.2 * 1.0 + 0.0 + 2.0 * 6.0 + 3.0 * 3.0
    assert cost == pytest.approx(22.2)
    alpha = 18.0 / 22.2
    assert flows.household_affordable[0, FOOD] == pytest.approx(alpha * 6.0)
    # Only food is retailed here, so spending covers the food part of the
    # affordable basket; the full basket still costs exactly the income.
    assert flows.household_spending[0] == pytest.approx(2.0 * alpha * 6.0)
    assert (
        flows.household_affordable[0] @ np.array(parameters.prices)
        == pytest.approx(18.0)
    )
    assert flows.budget_unmet[0, FOOD] > 0
    assert flows.availability_unmet[0, FOOD] == pytest.approx(0.0, abs=1e-12)
    assert flows.household_realized[0, FOOD] == pytest.approx(alpha * 6.0)


def alpha_of(parameters) -> float:
    cost = sum(
        p * d * 3.0 for p, d in zip(parameters.prices, parameters.desired_per_person, strict=False)
    )
    return min(1.0, 18.0 / cost)


def test_zero_retail_forces_full_saving() -> None:
    parameters = base_parameters(retail_release_fraction=[0.0, 0.0, 0.0, 0.0])
    state = household_state(0.0, [1.0], parameters.desired_per_person)
    flows = kernel_tick(state, parameters)
    assert flows.household_realized[0, FOOD] == pytest.approx(0.0)
    assert flows.household_spending[0] == pytest.approx(0.0)
    assert flows.forced_saving[0] == pytest.approx(18.0)
    assert flows.availability_unmet[0, FOOD] == pytest.approx(
        alpha_of(parameters) * 6.0
    )


def test_rationing_quota_not_region_copy() -> None:
    """Weights 2/1, affordable food 4 each, region stock 6: each household gets
    beta*q = 2 (weighted sales 6), never a copy of the whole stock."""
    parameters = base_parameters(
        desired_per_person=[0, 0, 4.0 / 3.0, 0],
        retail_release_fraction=[0.0, 0.0, 0.0, 0.0],
    )
    state = household_state(6.0, [2.0, 1.0], parameters.desired_per_person)
    state.wholesale_inventory = np.array([0.0, 0.0, 0.0, 0.0])
    flows = kernel_tick(state, parameters)
    assert flows.household_affordable[:, FOOD].tolist() == [4.0, 4.0]
    assert flows.household_realized[:, FOOD].tolist() == [2.0, 2.0]
    assert flows.retail_sales[0, FOOD] == pytest.approx(6.0)
    assert state.retail_inventory[0, FOOD] == pytest.approx(0.0, abs=1e-9)


def test_regions_rationed_locally_no_national_clearing() -> None:
    """Two regions, desired food 10 each (budget-unconstrained), stocks 15/5:
    realized 10/5, closing 5/0; region 2 is not topped up nationally."""
    parameters = base_parameters(
        desired_per_person=[0, 0, 10.0 / 3.0, 0],
        income_per_person=10.0,
        retail_release_fraction=[0.0, 0.0, 0.0, 0.0],
    )
    state = kernel_state(
        household_id=np.arange(2, dtype=np.int64),
        household_region=np.array([0, 1], dtype=np.int32),
        household_weight=np.array([1.0, 1.0]),
        wholesale_inventory=np.zeros(4),
        retail_inventory=np.array(
            [[0.0, 0.0, 15.0, 0.0], [0.0, 0.0, 5.0, 0.0]]
        ),
        regional_share=np.array([0.5, 0.5]),
        region_equivalent_persons=np.array([3.0, 3.0]),
    )
    flows = kernel_tick(state, parameters)
    assert flows.household_affordable[:, FOOD].tolist() == [10.0, 10.0]
    assert flows.household_realized[:, FOOD].tolist() == [10.0, 5.0]
    assert flows.availability_unmet[:, FOOD].tolist() == [0.0, 5.0]
    assert state.retail_inventory[:, FOOD].tolist() == [5.0, 0.0]


def test_zero_demand_cell_keeps_inventory_and_zero_rate() -> None:
    parameters = base_parameters(desired_per_person=[0.0, 0.0, 0.0, 0.0])
    state = kernel_state()
    opening_retail = 4.0
    flows = kernel_tick(state, parameters)
    assert flows.retail_sales[0, FOOD] == pytest.approx(0.0)
    assert state.retail_inventory[0, FOOD] == pytest.approx(
        opening_retail + flows.retail_incoming[0, FOOD], abs=1e-9
    )
    assert flows.household_realized[0, FOOD] == 0.0


# ---------------------------------------------------------------------------
# Forcing admission gates
# ---------------------------------------------------------------------------


def toy4_fixture_rows(shock: bool = True):
    imports_rows = []
    exports_rows = []
    y, q = 1957, 1
    for _ in range(116):
        period = f"{y}Q{q}"
        shock_quarters = {"1973Q4", "1974Q1", "1974Q2", "1974Q3"}
        energy_import = 0.0 if shock and period in shock_quarters else 150.0
        for index, commodity in enumerate(COMMODITIES):
            imports_rows.append(
                {
                    "variable_id": "toy4_import_supply",
                    "period": period,
                    "region_id": None,
                    "commodity_id": commodity,
                    "value": energy_import if index == 0 else 0.0,
                    "unit": "toy4_commodity_unit",
                }
            )
            exports_rows.append(
                {
                    "variable_id": "toy4_export_orders",
                    "period": period,
                    "region_id": None,
                    "commodity_id": commodity,
                    "value": 20.0 if index == 1 else 0.0,
                    "unit": "toy4_commodity_unit",
                }
            )
        q += 1
        if q == 5:
            y, q = y + 1, 1
    return imports_rows + exports_rows


def build_fixture_registry(tmp_path: Path, mutate=None):
    import shutil

    from tests.conftest import make_registry, provenance, source_spec, variable_spec

    shutil.copy(REPO_ROOT / "BASELINE.md", tmp_path / "BASELINE.md")
    shutil.copy(REPO_ROOT / "uv.lock", tmp_path / "uv.lock")

    imports_path = tmp_path / "data" / "fixtures" / "import_supply.parquet"
    exports_path = tmp_path / "data" / "fixtures" / "export_orders.parquet"
    from tests.conftest import write_long_parquet

    imports_rows = [r for r in toy4_fixture_rows() if r["variable_id"] == "toy4_import_supply"]
    exports_rows = [r for r in toy4_fixture_rows() if r["variable_id"] == "toy4_export_orders"]
    if mutate is not None:
        imports_rows, exports_rows, meta = mutate(imports_rows, exports_rows, {})
    else:
        meta = {}
    digest_imports = write_long_parquet(imports_path, imports_rows)
    digest_exports = write_long_parquet(exports_path, exports_rows)

    rights = {
        "license_status": "verified",
        "license_name": "local fixture",
        "terms_locator": "fixture:p01-toy4",
        "evidence_quote": "local",
        "checked_at": "2026-10-07T00:00:00Z",
        "download_allowed": True,
        "redistribution_allowed": True,
        "notes": "",
    }
    source = source_spec(
        "p01_toy4_fixture",
        rights=rights,
        institution="HSM Lab local fixture",
        dataset="P01 Toy-4 deterministic forcing fixtures",
        locator="fixture:p01-toy4",
        expected_format=["PARQUET"],
        expected_roles=["exogenous_forcing", "target"],
        retrieval_method="local deterministic generation",
        access_status="public_metadata",
        audit_status="metadata_checked",
        coverage_notes="fixture",
    )
    variables = [
        variable_spec(
            "toy4_import_supply",
            "external",
            "exogenous_forcing",
            unit="toy4_commodity_unit",
            original_frequency="quarterly",
            aggregation="sum",
        ),
        variable_spec(
            "toy4_export_orders",
            "external",
            "exogenous_forcing",
            unit="toy4_commodity_unit",
            original_frequency="quarterly",
            aggregation="sum",
        ),
    ]

    def artifact(aid, vid, path, digest, role="exogenous_forcing"):
        prov = provenance(
            variable=vid,
            role=role,
            evidence_status="synthetic_fixture",
            source_id="p01_toy4_fixture",
            original_frequency="quarterly",
            method="synthetic_generation",
            locator="fixture:p01-toy4",
            rights=rights,
            artifact_sha256=digest,
            raw_sha256=digest,
        )
        entry = {
            "artifact_id": aid,
            "variable_id": vid,
            "path": str(path.relative_to(tmp_path)),
            "source_id": "p01_toy4_fixture",
            "allow_missing": False,
            "role": role,
            "provenance": prov,
        }
        period_start = meta.get("period_start", "1957Q1")
        period_end = meta.get("period_end", "1985Q4")
        if role == "exogenous_forcing":
            entry["period"] = {
                "start": period_start,
                "end": period_end,
                "frequency": "quarterly",
            }
        else:
            entry["use"] = "calibration"
            entry["observed_period"] = {
                "start": period_start,
                "end": period_end,
                "frequency": "quarterly",
            }
            entry["comparison_aggregation"] = "sum"
        return entry

    swap = meta.get("swap_variables", False)
    import_var = "toy4_export_orders" if swap else "toy4_import_supply"
    export_var = "toy4_import_supply" if swap else "toy4_export_orders"
    artifacts = [
        artifact(
            "p01_toy4_import_supply",
            import_var,
            imports_path,
            meta.get("digest_imports", digest_imports),
            role=meta.get("import_role", "exogenous_forcing"),
        ),
        artifact(
            "p01_toy4_export_orders",
            export_var,
            exports_path,
            digest_exports,
        ),
    ]
    registry = make_registry(
        tmp_path,
        sources=[source],
        variables=variables,
        artifacts=artifacts,
        allowed_commodities=COMMODITIES,
    )
    return registry


def drop_one_cell(imports_rows, exports_rows, meta):
    imports_rows = imports_rows[:-1]
    return imports_rows, exports_rows, meta


def duplicate_one_cell(imports_rows, exports_rows, meta):
    imports_rows = imports_rows + [dict(imports_rows[0])]
    return imports_rows, exports_rows, meta


def negative_value(imports_rows, exports_rows, meta):
    imports_rows[3]["value"] = -1.0
    return imports_rows, exports_rows, meta


def nan_value(imports_rows, exports_rows, meta):
    imports_rows[3]["value"] = float("nan")
    return imports_rows, exports_rows, meta


def regional_row(imports_rows, exports_rows, meta):
    imports_rows[3]["region_id"] = "budapest"
    return imports_rows, exports_rows, meta


def wrong_digest(imports_rows, exports_rows, meta):
    meta["digest_imports"] = "f" * 64
    return imports_rows, exports_rows, meta


def target_role(imports_rows, exports_rows, meta):
    meta["import_role"] = "target"
    return imports_rows, exports_rows, meta


def shortened_window(imports_rows, exports_rows, meta):
    """Drop 1985Q4 and declare both artifacts ending 1985Q3 (valid hashes)."""
    imports_rows = [r for r in imports_rows if r["period"] != "1985Q4"]
    exports_rows = [r for r in exports_rows if r["period"] != "1985Q4"]
    meta["period_end"] = "1985Q3"
    return imports_rows, exports_rows, meta


def shifted_window(imports_rows, exports_rows, meta):
    """Drop 1957Q1 and declare both artifacts starting 1957Q2 (valid hashes)."""
    imports_rows = [r for r in imports_rows if r["period"] != "1957Q1"]
    exports_rows = [r for r in exports_rows if r["period"] != "1957Q1"]
    meta["period_start"] = "1957Q2"
    return imports_rows, exports_rows, meta


def swapped_variables(imports_rows, exports_rows, meta):
    """Swap the two variables between artifacts while keeping valid hashes."""
    meta["swap_variables"] = True
    return imports_rows, exports_rows, meta


@pytest.mark.parametrize(
    "mutate,match",
    [
        (drop_one_cell, "grid mismatch"),
        (duplicate_one_cell, "duplicate"),
        (negative_value, "finite and >= 0"),
        (nan_value, "non-finite"),
        (regional_row, "national-only"),
        (wrong_digest, "digest mismatch"),
        (target_role, "exogenous forcing"),
    ],
)
def test_forcing_corruptions_rejected_before_output(tmp_path, spec, contract, mutate, match):
    from hsm_lab.engine.toy4 import run_toy4

    registry = build_fixture_registry(tmp_path, mutate=mutate)
    with pytest.raises(ResearchGateError, match=match):
        run_toy4(spec, tmp_path / "run", contract, registry)
    assert not (tmp_path / "run").exists()


def test_zero_row_does_not_substitute_missing_cell(tmp_path, spec, contract):
    """Dropping one cell while other quarters carry real zeros for the same
    commodity is still a grid mismatch, never silently filled."""
    registry = build_fixture_registry(tmp_path, mutate=drop_one_cell)
    from hsm_lab.engine.toy4 import load_toy4_forcing

    with pytest.raises(ResearchGateError, match="grid mismatch"):
        load_toy4_forcing(spec, registry)


@pytest.mark.parametrize(
    "mutate,match",
    [
        (shortened_window, "must equal the full contract core window"),
        (shifted_window, "must equal the full contract core window"),
        (swapped_variables, "must carry exactly variable"),
    ],
)
def test_self_consistent_window_and_variable_mutations_refused(
    tmp_path, spec, contract, mutate, match
):
    """Fixtures that are internally consistent (valid hashes, in-window rows)
    but shortened, shifted or variable-swapped must still be refused before any
    output directory exists."""
    from hsm_lab.engine.toy4 import load_toy4_forcing, run_toy4

    registry = build_fixture_registry(tmp_path, mutate=mutate)
    with pytest.raises(ResearchGateError, match=match):
        load_toy4_forcing(spec, registry)
    with pytest.raises(ResearchGateError, match=match):
        run_toy4(spec, tmp_path / "run", contract, registry)
    assert not (tmp_path / "run").exists()


# ---------------------------------------------------------------------------
# Invariant tampering (plan: each ledger must be named individually)
# ---------------------------------------------------------------------------


def completed_reference():
    parameters = base_parameters(desired_per_person=[0, 0, 1, 0], target_utilization=1.0)
    state = kernel_state()
    flows = kernel_tick(state, parameters)
    return state, flows, parameters


def test_tampered_retail_ledger_named() -> None:
    state, flows, parameters = completed_reference()
    opening = snapshot_opening_stocks(state, flows)
    state.retail_inventory = state.retail_inventory + 1.0
    with pytest.raises(Exception, match="retail"):
        check_toy4_invariants(opening, state, flows, parameters)


def test_tampered_wholesale_ledger_named() -> None:
    state, flows, parameters = completed_reference()
    opening = snapshot_opening_stocks(state, flows)
    state.wholesale_inventory = state.wholesale_inventory + 1.0
    with pytest.raises(Exception, match="wholesale"):
        check_toy4_invariants(opening, state, flows, parameters)


def test_tampered_organization_ledger_named() -> None:
    state, flows, parameters = completed_reference()
    opening = snapshot_opening_stocks(state, flows)
    state.organization_input_inventory = state.organization_input_inventory + 1.0
    with pytest.raises(Exception, match="org_input"):
        check_toy4_invariants(opening, state, flows, parameters)


def test_tampered_double_counted_transfer_named() -> None:
    state, flows, parameters = completed_reference()
    opening = snapshot_opening_stocks(state, flows)
    # An extra unit released to retail, consistently recorded across the retail
    # snapshots and the closing state, so only the wholesale transfer ledger
    # (which subtracts the incoming transfer) is inconsistent.
    flows.retail_planned = flows.retail_planned + 1.0
    flows.retail_incoming = flows.retail_incoming + 1.0
    flows.retail_available = flows.retail_available + 1.0
    flows.retail_close = flows.retail_close + 1.0
    state.retail_inventory = state.retail_inventory + 1.0
    with pytest.raises(Exception, match="retail_incoming|wholesale"):
        check_toy4_invariants(opening, state, flows, parameters)


def test_spending_above_income_fails() -> None:
    state, flows, parameters = completed_reference()
    opening = snapshot_opening_stocks(state, flows)
    flows.household_spending = flows.household_spending + 100.0
    with pytest.raises(Exception, match="spending"):
        check_toy4_invariants(opening, state, flows, parameters)


@pytest.mark.parametrize(
    "field",
    [
        "allocated_input",
        "ordered_input",
        "available_input",
        "input_unmet",
        "budget_unmet",
        "household_affordable",
        "household_desired",
        "voluntary_saving",
        "forced_saving",
        "retail_incoming",
        "retail_sales",
        "export_unmet",
    ],
)
def test_nan_flow_corruption_fails_closed(field) -> None:
    """A NaN anywhere in the flow record is a violation, never a silently
    comparing cell or a zero diagnostic."""
    from hsm_lab.engine.accounting import AccountingError

    state, flows, parameters = completed_reference()
    getattr(flows, field).flat[0] = float("nan")
    with pytest.raises(AccountingError):
        check_toy4_invariants(
            snapshot_opening_stocks(state, flows), state, flows, parameters
        )


def test_nan_closing_state_fails_closed() -> None:
    from hsm_lab.engine.accounting import AccountingError

    state, flows, parameters = completed_reference()
    state.retail_inventory[0, FOOD] = float("nan")
    with pytest.raises(AccountingError, match="non-finite"):
        check_toy4_invariants(
            snapshot_opening_stocks(state, flows), state, flows, parameters
        )


@pytest.mark.parametrize(
    "field",
    [
        "household_size",
        "region_equivalent_persons",
        "regional_share",
        "organization_capacity",
        "household_weight",
    ],
)
def test_nan_state_arrays_fail_closed(field) -> None:
    from hsm_lab.engine.accounting import AccountingError

    state, flows, parameters = completed_reference()
    values = getattr(state, field)
    values = values.copy()
    values.flat[0] = float("nan")
    setattr(state, field, values)
    with pytest.raises(AccountingError, match="non-finite|not finite"):
        check_toy4_invariants(
            snapshot_opening_stocks(state, flows), state, flows, parameters
        )


def test_detached_state_cash_fails_closed() -> None:
    """Closing state cash is authoritative: a divergence from the flow
    snapshot must fail even when both flow sides agree."""
    from hsm_lab.engine.accounting import AccountingError

    state, flows, parameters = completed_reference()
    opening = snapshot_opening_stocks(state, flows)
    detached = state.household_cash.copy()
    detached[0] += 100.0
    state.household_cash = detached
    with pytest.raises(AccountingError, match="cash"):
        check_toy4_invariants(opening, state, flows, parameters)


def test_detached_state_stock_fails_closed() -> None:
    from hsm_lab.engine.accounting import AccountingError

    state, flows, parameters = completed_reference()
    opening = snapshot_opening_stocks(state, flows)
    state.retail_inventory = state.retail_inventory + 5.0
    with pytest.raises(AccountingError):
        check_toy4_invariants(opening, state, flows, parameters)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda f: _bump(f, "budget_unmet", (0, FOOD), 1.0),
        lambda f: _bump(f, "total_unmet", (0, FOOD), 1.0),
        lambda f: _bump(f, "availability_unmet", (0, FOOD), 1.0),
        lambda f: _bump(f, "allocated_input", (0, FOOD), 1.0),
        lambda f: _bump(f, "organization_target", (0,), 1.0),
    ],
)
def test_finite_flow_identity_perturbations_fail_closed(mutate) -> None:
    """Finite perturbations that break a declared identity must fail, not just
    NaN/inequality violations."""
    from hsm_lab.engine.accounting import AccountingError

    state, flows, parameters = completed_reference()
    mutate(flows)
    with pytest.raises(AccountingError):
        check_toy4_invariants(
            snapshot_opening_stocks(state, flows), state, flows, parameters
        )


def test_finite_recorded_snapshot_perturbations_fail_closed() -> None:
    """Recorded residual/tolerance snapshots and outcome definitions must be
    bound to recomputation, not merely finite."""
    from hsm_lab.engine.accounting import AccountingError

    for field, index in (
        ("export_unmet", (FOOD,)),
        ("organization_output_shortfall", (0,)),
        ("material_balance_residual", (FOOD,)),
        ("cash_balance_residual", (0,)),
        ("material_balance_tolerance", (FOOD,)),
        ("cash_balance_tolerance", (0,)),
    ):
        state, flows, parameters = completed_reference()
        _bump(flows, field, index, 1.0)
        with pytest.raises(AccountingError):
            check_toy4_invariants(
                snapshot_opening_stocks(state, flows), state, flows, parameters
            )


def test_runner_post_tick_state_corruption_reports_prior_boundary(
    tmp_path, contract, registry, monkeypatch
) -> None:
    import hsm_lab.engine.toy4 as toy4_module

    original = toy4_module.tick_toy4

    def corrupting(state, forcing, parameters):
        flows = original(state, forcing, parameters)
        # Detach the authoritative closing cash after the kernel advanced.
        detached = state.household_cash.copy()
        detached[0] += 100.0
        state.household_cash = detached
        return flows

    monkeypatch.setattr(toy4_module, "tick_toy4", corrupting)
    from hsm_lab.engine.toy4 import run_toy4

    spec = load_scenario(REPO_ROOT, "toy4")
    from hsm_lab.engine.accounting import AccountingError

    with pytest.raises(AccountingError):
        run_toy4(spec, tmp_path / "corrupt", contract, registry)
    payload = load_json(tmp_path / "corrupt" / "manifest.json")
    assert payload["status"] == "failed"
    assert payload["completed_ticks"] == 0
    assert payload["last_completed_quarter"] is None
    assert payload["deterministic_replay_digest"] == ""


def test_nonzero_initial_cash_recipe_supported(tmp_path, contract, registry, spec):
    """The supported nonzero initial-cash recipe must run to completion (the
    cash identity is stated relative to the declared opening cash)."""
    from hsm_lab.engine.toy4 import run_toy4

    assert spec.toy4_initial is not None
    parameters = spec.model_copy(
        update={
            "toy4_initial": spec.toy4_initial.model_copy(
                update={"household_cash": 100.0}
            )
        }
    )
    parameters = ScenarioSpec.model_validate(parameters.model_dump())
    manifest = run_toy4(parameters, tmp_path / "cash", contract, registry)
    assert manifest.status == "completed"
    assert manifest.completed_ticks == 116


def test_runner_state_identity_corruption_fails_closed(
    tmp_path, contract, registry, monkeypatch
) -> None:
    """The runner's per-tick gate recomputes static/derived state identities,
    so a capacity or regional-persons corruption is refused at runtime."""
    import hsm_lab.engine.toy4 as toy4_module

    original = toy4_module.tick_toy4

    def corrupting(state, forcing, parameters):
        flows = original(state, forcing, parameters)
        capacity = state.organization_capacity.copy()
        capacity[0] = capacity[0] + 1000.0
        state.organization_capacity = capacity
        return flows

    monkeypatch.setattr(toy4_module, "tick_toy4", corrupting)
    from hsm_lab.engine.accounting import AccountingError
    from hsm_lab.engine.toy4 import run_toy4

    spec = load_scenario(REPO_ROOT, "toy4")
    with pytest.raises(AccountingError):
        run_toy4(spec, tmp_path / "idcorrupt", contract, registry)
    payload = load_json(tmp_path / "idcorrupt" / "manifest.json")
    assert payload["status"] == "failed"
    assert payload["completed_ticks"] == 0
    assert payload["deterministic_replay_digest"] == ""


def test_runtime_gate_rejects_off_rule_target() -> None:
    """A coherent tick executed at utilization 0.5 must be rejected when checked
    against the declared 0.9 rule, at the target-binding ledger."""
    from hsm_lab.engine.accounting import AccountingError

    declared = base_parameters(desired_per_person=[0, 0, 1, 0], target_utilization=0.9)
    off_rule = base_parameters(desired_per_person=[0, 0, 1, 0], target_utilization=0.5)
    state = kernel_state()
    flows = kernel_tick(state, off_rule)
    opening = snapshot_opening_stocks(state, flows)
    with pytest.raises(AccountingError, match="target_equals_min_util_capacity_labor"):
        check_toy4_invariants(opening, state, flows, declared)


def test_runner_rejects_off_rule_target(tmp_path, contract, registry, monkeypatch) -> None:
    """A runner executing the kernel at utilization 0.5 while the declared
    scenario says 0.9 must fail closed at the first tick."""
    import hsm_lab.engine.toy4 as toy4_module

    original = toy4_module.tick_toy4

    def off_rule(state, forcing, parameters):
        lo = parameters.model_copy(update={"target_utilization": 0.5})
        return original(state, forcing, lo)

    monkeypatch.setattr(toy4_module, "tick_toy4", off_rule)
    from hsm_lab.engine.accounting import AccountingError
    from hsm_lab.engine.toy4 import run_toy4

    spec = load_scenario(REPO_ROOT, "toy4")
    with pytest.raises(AccountingError):
        run_toy4(spec, tmp_path / "offrule", contract, registry)
    payload = load_json(tmp_path / "offrule" / "manifest.json")
    assert payload["status"] == "failed"
    assert payload["completed_ticks"] == 0
    assert payload["deterministic_replay_digest"] == ""
    assert not (tmp_path / "offrule" / "checkpoints").exists()


def test_runtime_gate_rejects_off_rule_release_fraction() -> None:
    from hsm_lab.engine.accounting import AccountingError

    declared = base_parameters(desired_per_person=[0, 0, 1, 0], target_utilization=1.0)
    off_rule = base_parameters(
        desired_per_person=[0, 0, 1, 0],
        target_utilization=1.0,
        retail_release_fraction=[0.2, 0.0, 0.5, 1.0],
    )
    state = kernel_state()
    flows = kernel_tick(state, off_rule)
    opening = snapshot_opening_stocks(state, flows)
    with pytest.raises(AccountingError, match="retail_incoming_equals_share_times_offer"):
        check_toy4_invariants(opening, state, flows, declared)


def test_runtime_gate_rejects_off_rule_production() -> None:
    """Under-production below the declared Leontief minimum must fail, not just
    production above capacity."""
    import hsm_lab.engine.state as state_module
    from hsm_lab.engine.accounting import AccountingError

    original = state_module.produce_leontief

    def half_output(available, coefficients, target):
        realized, used = original(available, coefficients, target)
        return realized * 0.5, used * 0.5

    state = kernel_state()
    parameters = base_parameters(
        desired_per_person=[0, 0, 1, 0], target_utilization=1.0
    )
    saved = state_module.produce_leontief
    state_module.produce_leontief = half_output
    try:
        from hsm_lab.engine.state import tick_toy4

        with pytest.raises(AccountingError, match="realized_equals_leontief_min"):
            tick_toy4(
                state,
                one_quarter_forcing((0, 0, 2.0, 0), (0, 0, 1.0, 0)),
                parameters,
            )
    finally:
        state_module.produce_leontief = saved


def test_runner_rejects_forcing_mismatch(tmp_path, contract, registry, monkeypatch) -> None:
    import hsm_lab.engine.toy4 as toy4_module

    original = toy4_module.tick_toy4

    def mismatched(state, forcing, parameters):
        fake = type(forcing)(
            quarters=forcing.quarters,
            imports=forcing.imports.copy(),
            export_orders=forcing.export_orders.copy(),
            input_artifact_hashes=dict(forcing.input_artifact_hashes),
        )
        fake.imports[0, 0] = 0.0  # contradict the admitted fixture's 150
        return original(state, fake, parameters)

    monkeypatch.setattr(toy4_module, "tick_toy4", mismatched)
    from hsm_lab.contract.schemas import ResearchGateError
    from hsm_lab.engine.toy4 import run_toy4

    spec = load_scenario(REPO_ROOT, "toy4")
    with pytest.raises(ResearchGateError, match="forcing"):
        run_toy4(spec, tmp_path / "forcmis", contract, registry)
    payload = load_json(tmp_path / "forcmis" / "manifest.json")
    assert payload["status"] == "failed"
    assert payload["completed_ticks"] == 0
    assert payload["deterministic_replay_digest"] == ""
    assert not (tmp_path / "forcmis" / "checkpoints").exists()


def test_runner_rejects_stale_tick_metadata(tmp_path, contract, registry, monkeypatch) -> None:
    """A tick that does not describe the next admitted quarter must be refused."""
    import hsm_lab.engine.toy4 as toy4_module

    original = toy4_module.tick_toy4

    def stale(state, forcing, parameters):
        flows = original(state, forcing, parameters)
        flows.tick = flows.tick - 1
        return flows

    monkeypatch.setattr(toy4_module, "tick_toy4", stale)
    from hsm_lab.contract.schemas import ResearchGateError
    from hsm_lab.engine.toy4 import run_toy4

    spec = load_scenario(REPO_ROOT, "toy4")
    with pytest.raises(ResearchGateError, match="next admitted quarter"):
        run_toy4(spec, tmp_path / "stale", contract, registry)
    payload = load_json(tmp_path / "stale" / "manifest.json")
    assert payload["status"] == "failed"
    assert payload["completed_ticks"] == 0


def test_runner_opening_snapshot_detects_flow_snapshot_tampering(
    tmp_path, contract, registry, monkeypatch
) -> None:
    """The runner's opening snapshot is the pre-call state, so a kernel whose
    returned opening snapshots disagree with it is refused even if the closing
    state is internally consistent."""
    import hsm_lab.engine.toy4 as toy4_module

    original = toy4_module.tick_toy4

    def tampered_snapshots(state, forcing, parameters):
        flows = original(state, forcing, parameters)
        flows.organization_input_open = flows.organization_input_open + 1.0
        flows.wholesale_open = flows.wholesale_open + 1.0
        return flows

    monkeypatch.setattr(toy4_module, "tick_toy4", tampered_snapshots)
    from hsm_lab.engine.accounting import AccountingError
    from hsm_lab.engine.toy4 import run_toy4

    spec = load_scenario(REPO_ROOT, "toy4")
    with pytest.raises(AccountingError, match="opening"):
        run_toy4(spec, tmp_path / "opensnap", contract, registry)
    payload = load_json(tmp_path / "opensnap" / "manifest.json")
    assert payload["status"] == "failed"
    assert payload["completed_ticks"] == 0


def _bump(flows, field, index, delta) -> None:
    values = getattr(flows, field).copy()
    values[index] += delta
    setattr(flows, field, values)


# ---------------------------------------------------------------------------
# Runner-level behaviour
# ---------------------------------------------------------------------------


def run_full(tmp_path: Path, contract, registry, name: str, **overrides):
    from hsm_lab.engine.toy4 import run_toy4

    spec = load_scenario(REPO_ROOT, "toy4")
    if overrides:
        spec = ScenarioSpec.model_validate(
            spec.model_copy(update=overrides).model_dump()
        )
    return run_toy4(spec, tmp_path / name, contract, registry), tmp_path / name


def test_full_run_digest_determinism_and_seed_sensitivity(tmp_path, contract, registry):
    manifest_a, dir_a = run_full(tmp_path, contract, registry, "a")
    manifest_b, dir_b = run_full(tmp_path, contract, registry, "b")
    manifest_c, _ = run_full(tmp_path, contract, registry, "c", seed=1730)
    assert manifest_a.status == "completed"
    assert manifest_a.completed_ticks == 116
    assert manifest_a.last_completed_quarter == "1985Q4"
    assert manifest_a.deterministic_replay_digest == manifest_b.deterministic_replay_digest
    assert manifest_a.deterministic_replay_digest != manifest_c.deterministic_replay_digest
    for table in ("aggregates", "national_accounts", "household_budgets", "events"):
        assert pl.read_parquet(dir_a / f"{table}.parquet").equals(
            pl.read_parquet(dir_b / f"{table}.parquet")
        )


def test_household_scaling_bounds_complete_horizon(tmp_path, contract, registry):
    for n in (1000, 2000):
        manifest, run_dir = run_full(tmp_path, contract, registry, f"n{n}", households=n)
        assert manifest.status == "completed"
        assert manifest.households == n
        assert manifest.completed_ticks == 116
        assert manifest.last_completed_quarter == "1985Q4"


def test_research_full_policy_refused(tmp_path, contract, registry, spec):
    from hsm_lab.contract.schemas import OutputPolicy
    from hsm_lab.engine.toy4 import run_toy4

    bad = spec.model_copy(update={"output_policy": OutputPolicy.RESEARCH_FULL})
    with pytest.raises(ConfigError, match="ensemble_compact"):
        run_toy4(bad, tmp_path / "run", contract, registry)
    assert not (tmp_path / "run").exists()


def test_deterministic_mode_zero_draws(tmp_path, contract, registry):
    manifest, run_dir = run_full(tmp_path, contract, registry, "det", stochastic=False)
    assert manifest.rng_draws_count == 0
    summary = load_json(run_dir / "summary.json")
    assert summary["rng_draws_count"] == 0
    assert summary["deterministic_mode"]["warning"] == "deterministic_no_replicates"
    assert summary["completed_ticks"] == 116


def test_output_table_shapes_and_duckdb_parity(tmp_path, contract, registry):
    import duckdb

    _, run_dir = run_full(tmp_path, contract, registry, "tables")
    aggregates = pl.read_parquet(run_dir / "aggregates.parquet")
    national = pl.read_parquet(run_dir / "national_accounts.parquet")
    budgets = pl.read_parquet(run_dir / "household_budgets.parquet")
    diagnostics = pl.read_parquet(run_dir / "tick_diagnostics.parquet")
    events = pl.read_parquet(run_dir / "events.parquet")
    assert aggregates.height == 116 * 20 * 4
    assert national.height == 116 * 4
    assert budgets.height == 116 * 20
    assert diagnostics.height == 116
    assert events.height == 116
    for frame, keys in (
        (aggregates, ["tick", "region_id", "commodity_id"]),
        (national, ["tick", "commodity_id"]),
        (budgets, ["tick", "region_id"]),
        (diagnostics, ["tick"]),
        (events, ["tick"]),
    ):
        assert frame.group_by(keys).len().filter(pl.col("len") > 1).height == 0
    assert set(aggregates["region_id"].unique()) == set(contract.region_ids)
    assert set(aggregates["commodity_id"].unique()) == set(COMMODITIES)
    connection = duckdb.connect(str(run_dir / "trajectory.duckdb"), read_only=True)
    try:
        for name, frame in (
            ("aggregates", aggregates),
            ("national_accounts", national),
            ("household_budgets", budgets),
            ("tick_diagnostics", diagnostics),
            ("events", events),
        ):
            from_db = pl.from_arrow(
                connection.execute(f"SELECT * FROM {name}").arrow()
            )
            assert from_db.sort([c for c in frame.columns if c in keys or c == "tick"]).equals(
                frame.sort([c for c in frame.columns if c in keys or c == "tick"])
            ), name
        views = connection.execute("SHOW TABLES").fetchall()
    finally:
        connection.close()
    assert {name for (name,) in views} == {
        "aggregates",
        "national_accounts",
        "household_budgets",
        "tick_diagnostics",
        "events",
    }
    # No micro panels anywhere.
    assert not (run_dir / "households.parquet").exists()
    assert not (run_dir / "enterprises.parquet").exists()


def test_inventory_continuity_and_shock_passthrough(tmp_path, contract, registry, spec):
    from hsm_lab.engine.toy4 import load_toy4_forcing

    _, run_dir = run_full(tmp_path, contract, registry, "cont")
    national = pl.read_parquet(run_dir / "national_accounts.parquet")
    forcing = load_toy4_forcing(spec, registry)
    imports_out = national.sort(["tick", "commodity_id"]).filter(
        pl.col("commodity_id") == "energy"
    )["imports"].to_list()
    np.testing.assert_allclose(imports_out, forcing.imports[:, 0], rtol=0, atol=0)
    # closing -> next opening continuity per commodity
    for commodity in COMMODITIES:
        rows = national.filter(pl.col("commodity_id") == commodity).sort("tick")
        wholesale_close = rows["wholesale_close"].to_list()
        wholesale_open = rows["wholesale_open"].to_list()
        for index in range(1, len(wholesale_close)):
            assert wholesale_open[index] == pytest.approx(
                wholesale_close[index - 1], abs=1e-9
            )
    # positive mechanism outputs
    summary = load_json(run_dir / "summary.json")
    assert summary["by_commodity"]["food"]["production"] > 0
    assert summary["by_commodity"]["consumer_goods"]["budget_unmet"] > 0
    assert summary["by_commodity"]["consumer_goods"]["availability_unmet"] > 0
    assert summary["household_budget"]["forced_saving"] > 0
    assert summary["invariants"]["max_material_tolerance_ratio"] <= 1.0
    assert summary["invariants"]["max_cash_tolerance_ratio"] <= 1.0


def test_summary_cumulative_matches_independent_groupby(tmp_path, contract, registry):
    _, run_dir = run_full(tmp_path, contract, registry, "agg")
    national = pl.read_parquet(run_dir / "national_accounts.parquet")
    summary = load_json(run_dir / "summary.json")
    for commodity, stats in summary["by_commodity"].items():
        rows = national.filter(pl.col("commodity_id") == commodity)
        assert stats["production"] == pytest.approx(rows["production"].sum())
        assert stats["imports"] == pytest.approx(rows["imports"].sum())
        assert stats["exports"] == pytest.approx(rows["export_realized"].sum())
        assert stats["consumption"] == pytest.approx(rows["household_consumption"].sum())


def test_final_cash_accumulates_all_regions(tmp_path, contract, registry):
    """final_cash is the final-quarter national weighted household cash stock,
    not the last region's row."""
    _, run_dir = run_full(tmp_path, contract, registry, "cash")
    budgets = pl.read_parquet(run_dir / "household_budgets.parquet")
    summary = load_json(run_dir / "summary.json")
    expected = float(
        budgets.filter(pl.col("tick") == summary["completed_ticks"] - 1)[
            "cash_close"
        ].sum()
    )
    assert summary["household_budget"]["final_cash"] == pytest.approx(expected)
    # income - spending over the whole run equals the final cash stock when the
    # initial cash is zero (this scenario's recipe).
    assert summary["household_budget"]["final_cash"] == pytest.approx(
        summary["household_budget"]["income"]
        - summary["household_budget"]["spending"]
    )


def test_runner_tick_failure_writes_failed_manifest(tmp_path, contract, registry, monkeypatch):
    import hsm_lab.engine.toy4 as toy4_module

    original = toy4_module.tick_toy4

    def exploding(state, forcing, parameters):
        if state.completed_ticks == 3:
            raise RuntimeError("kernel exploded mid-run")
        return original(state, forcing, parameters)

    monkeypatch.setattr(toy4_module, "tick_toy4", exploding)
    from hsm_lab.engine.toy4 import run_toy4

    spec = load_scenario(REPO_ROOT, "toy4")
    with pytest.raises(RuntimeError, match="kernel exploded"):
        run_toy4(spec, tmp_path / "failed", contract, registry)
    payload = load_json(tmp_path / "failed" / "manifest.json")
    assert payload["status"] == "failed"
    assert payload["completed_ticks"] == 3
    assert payload["last_completed_quarter"] == "1957Q3"
    assert payload["rng_draws_count"] == spec.households  # initialization draws are real
    assert payload["deterministic_replay_digest"] == ""
    assert not (tmp_path / "failed" / "checkpoints").exists()


def test_checkpoint_write_failure_fails_run(tmp_path, contract, registry, monkeypatch):
    import hsm_lab.storage.checkpoint as checkpoint_module

    def boom(*args, **kwargs):
        raise OSError("disk full during checkpoint")

    monkeypatch.setattr(checkpoint_module, "save_toy4_checkpoint", boom)
    from hsm_lab.engine.toy4 import run_toy4

    spec = load_scenario(REPO_ROOT, "toy4")
    with pytest.raises(OSError, match="disk full"):
        run_toy4(spec, tmp_path / "ckfail", contract, registry, checkpoint_every=2)
    payload = load_json(tmp_path / "ckfail" / "manifest.json")
    assert payload["status"] == "failed"
    assert payload["deterministic_replay_digest"] == ""


def test_until_pauses_and_writes_boundary_checkpoint(tmp_path, contract, registry):
    from hsm_lab.engine.toy4 import run_toy4

    spec = load_scenario(REPO_ROOT, "toy4")
    manifest = run_toy4(
        spec, tmp_path / "paused", contract, registry, until="1966Q4"
    )
    assert manifest.status == "paused"
    assert manifest.completed_ticks == 40
    assert manifest.last_completed_quarter == "1966Q4"
    summary = load_json(tmp_path / "paused" / "summary.json")
    assert summary["horizon_reached"] is False
    assert (tmp_path / "paused" / "checkpoints" / "tick-0040" / "metadata.json").is_file()


def test_until_bounds_validated(tmp_path, contract, registry, spec):
    from hsm_lab.engine.toy4 import run_toy4

    with pytest.raises(ConfigError, match="beyond the scenario end"):
        run_toy4(spec, tmp_path / "x1", contract, registry, until="1986Q1")
    assert not (tmp_path / "x1").exists()
    with pytest.raises(ConfigError, match="precedes"):
        run_toy4(spec, tmp_path / "x2", contract, registry, until="1956Q4")
    assert not (tmp_path / "x2").exists()


def test_scenario_validation_gates(tmp_path, contract, spec):
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="goods"):
        ScenarioSpec.model_validate(
            spec.model_copy(update={"commodities": ["goods", "a", "b", "c"]}).model_dump()
        )
    with pytest.raises(ConfigError, match="households"):
        spec.model_copy(update={"households": 500}).validate_for_run(contract)
    with pytest.raises(ConfigError, match="enterprises"):
        spec.model_copy(update={"enterprises": 10}).validate_for_run(contract)
    with pytest.raises(ConfigError, match="forcing_ids"):
        spec.model_copy(update={"forcing_ids": []}).validate_for_run(contract)
    with pytest.raises(ConfigError, match="toy4 commodity"):
        spec.model_copy(update={"commodities": ["a", "b", "c", "d"]}).validate_for_run(
            contract
        )


def test_smoke_cannot_carry_toy4_configs(spec):
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="smoke scenarios must not"):
        ScenarioSpec.model_validate(
            spec.model_copy(
                update={"kind": "smoke", "scenario_id": "s"}
            ).model_dump()
        )
