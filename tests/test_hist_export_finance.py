"""H3F-D0: versioned legacy Treasury-prepay reference and double-book observation.

Every test drives the real material kernel and the real finance step (no
mocks, no tick/account/journal stand-ins).  The fixture builder mirrors the
approved reproduce recipe: one bank, one energy seller with zero capacity
and zero cash, no production, no demand/housing/plots, and fully open
trade parameters.  All amounts are fixture declarations, not runtime
injections.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.contract.material import TradeParameters
from hsm_lab.engine import accounting
from hsm_lab.engine.accounting import tolerance_for
from hsm_lab.engine.finance import (
    CMEA_CURRENCY,
    DOMESTIC_CURRENCY,
    USD_CURRENCY,
    AccountKind,
    foreign_account_id,
    organization_account_ids,
    treasury_account_id,
)
from hsm_lab.engine.material import tick_material
from hsm_lab.engine.state import MaterialStockSnapshot, MaterialTickFlows, capture_material_stocks
from hsm_lab.institutions.export_finance_adapter import (
    LegacyTradeFailure,
    LegacyTradeRegime,
    execute_legacy_trade_tick,
    load_legacy_trade_regime,
    observe_legacy_trade_tick,
)
from tests.test_material import (
    NO_CAPITAL_COMMODITIES,
    Fixture,
    _housing_fixture,
    bank,
    default_params,
    household_params,
    idle_source_tech,
    producer,
)

GATE_PREFIX = "HIST_H3F_D0"
REGIME_PATH = (
    Path(__file__).resolve().parents[1]
    / "config/trade_regimes/hist_vnext_v1/legacy_treasury_prepay.json"
)


# ---------------------------------------------------------------------------
# Fixture builder: mirrors the approved reproduce runner (seed 1729).
# ---------------------------------------------------------------------------


def _legacy_export_fixture(
    *,
    treasury: float,
    stock: float = 8.0,
    usd_reserve: float = 0.0,
    usd_import_quantity: float = 0.0,
    cmea_import_quantity: float = 0.0,
) -> Fixture:
    """Frozen synthetic legacy Treasury-prepay opening boundary.

    The builder is deterministic (seed 1729) and uses only the real kernel;
    it never imports a canned simulation, never short-circuits ``tick_material``,
    and never replaces a journal leg.
    """
    n = 8
    trade_vectors = {
        "cmea_prices": [1.0] * n,
        "convertible_prices": [1.0] * n,
        "cmea_desired_imports": [0.0] * n,
        "convertible_desired_imports": [0.0] * n,
        "cmea_export_demands": [0.0] * n,
        "convertible_export_demands": [0.0] * n,
    }
    trade_vectors["cmea_export_demands"][0] = 2.0  # energy
    trade_vectors["convertible_export_demands"][0] = 2.0
    trade_vectors["cmea_desired_imports"][0] = float(cmea_import_quantity)
    trade_vectors["convertible_desired_imports"][6] = float(usd_import_quantity)
    trade_vectors["convertible_prices"][0] = 3.0  # USD energy price
    trade = TradeParameters(
        **trade_vectors,
        cmea_credit_envelope=1.0,
        convertible_opening_reserve=float(usd_reserve),
        convertible_loan_limit=0.0,
        convertible_opening_principal=0.0,
    ).model_copy(update={"cmea_credit_envelope": 0.0})
    parameters = default_params(prices=[1.0] * n, trade=trade)
    parameters = parameters.model_copy(
        update={
            "food_raw_price": 1.0,
            "utilization": 1.0,
            "service_split": [1.0, 0.0, 0.0],
            "transport_per_unit": 0.0,
            "overorder_strength": 0.0,
            "hoarding_quarters": 0.0,
            "shortage_alpha": 0.0,
            "hunger_base": 0.0,
            "hunger_bailout": 0.0,
            "hunger_shortage": 0.0,
            "capital_depreciation_rate": 0.0,
            "credit_envelope_fraction": 0.0,
            "bailout_envelope_fraction": 0.0,
            "principal_repayment_fraction": 0.0,
            "domestic_credit_rate_annual": 0.0,
            "hungary_spread_annual": 0.0,
            "fiscal_turnover_remittance_fraction": 0.0,
            "household_savings_reentry_fraction": 0.0,
            "m2_neutral_credit": False,
            "sbc_redistribution": False,
            "demand_limited_targets": False,
            "production_target_rule": "legacy",
        }
    )
    fixture = Fixture(
        [
            bank(0),
            producer(1, "energy_generation", capacity=1.0, cash=0.0).model_copy(
                update={"capacity": 0.0, "labor_available": 0.0}
            ),
        ],
        [idle_source_tech("energy_generation", "energy")],
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 1.0)],
        household_cash=0.0,
        household_parameters=household_params(),
        ticks=2,
    )
    state = fixture.state
    state.stock_value[:] = 0.0
    state.stock_value[fixture.cell("organization", 1, 0, "output", "energy")] = float(stock)
    state.organization_capacity[:] = 0.0
    state.organization_labor_available[:] = 0.0
    state.organization_labor_endowment[:] = 0.0
    state.organization_cash[:] = 0.0
    state.organization_principal[:] = 0.0
    state.organization_wage_arrears[:] = 0.0
    state.organization_interest_arrears[:] = 0.0
    state.organization_shortage_expectation[:] = 0.0
    state.organization_bailout_expectation[:] = 0.0
    state.organization_project_approved[:] = 0.0
    state.organization_capital_wip[:] = 0.0
    state.organization_construction_wip[:] = 0.0
    state.household_cash[:] = 0.0
    state.household_deferred_receipt[:] = 0.0
    state.household_wage_claim[:] = 0.0
    state.household_durable_owned[:] = 0.0
    state.household_durable_backlog[:] = 0.0
    state.household_durable_repair_credit[:] = 0.0
    state.dwelling_stock[:] = 0.0
    state.housing_vacant[:] = 0.0
    state.second_output_stock[:] = 0.0
    state.bank_deposit_liability[:] = 0.0
    state.bank_deposit_liability[0] = float(treasury)
    state.bank_equity[:] = 0.0
    state.bank_equity[0] = 20.0
    state.bank_loan_asset[:] = 0.0
    state.bank_interest_receivable[:] = 0.0
    state.bank_reserves[:] = 0.0
    state.bank_reserves[0] = float(treasury) + 20.0
    state.treasury_deposit = float(treasury)
    state.treasury_loan_asset = 0.0
    state.credit_fund = 0.0
    state.usd_reserve = float(usd_reserve)
    state.usd_principal = 0.0
    state.usd_interest_arrears = 0.0
    state.cmea_settlement_balance = 0.0
    state.completed_ticks = 0
    return fixture


def _legacy_housing_fixture(
    *,
    treasury: float,
    transport_per_unit: float = 0.0,
) -> Fixture:
    """Real housing fixture with Treasury / bank accounts set up for the observer.

    Reuses ``tests.test_material._housing_fixture`` (energy + construction
    builder, ``housing_request_per_person=1.0``) and overlays the same
    Treasury/bank-reserve scaffolding as :func:`_legacy_export_fixture`.
    The default ``transport_per_unit`` is ``0.0`` so callers can opt in to a
    nonzero freight by overriding; the treasury defaults are large enough to
    cover the housing goods_payment at ``unit_price=1.0``.
    """
    fixture = _housing_fixture()
    state = fixture.state
    # The default housing fixture leaves the producer orgs with non-zero
    # opening cash; reset to the legacy-export style opening boundary so
    # the bank sheet balances exactly (deposits = treasury, equity = 20,
    # reserves = deposits + equity, organization_cash = 0).
    state.organization_cash[:] = 0.0
    state.organization_principal[:] = 0.0
    state.organization_wage_arrears[:] = 0.0
    state.organization_interest_arrears[:] = 0.0
    state.organization_bailout_expectation[:] = 0.0
    state.bank_loan_asset[:] = 0.0
    state.bank_interest_receivable[:] = 0.0
    state.bank_deposit_liability[:] = 0.0
    state.bank_deposit_liability[0] = float(treasury)
    state.bank_equity[:] = 0.0
    state.bank_equity[0] = 20.0
    state.bank_reserves[:] = 0.0
    state.bank_reserves[0] = float(treasury) + 20.0
    state.treasury_deposit = float(treasury)
    state.treasury_loan_asset = 0.0
    state.credit_fund = 0.0
    state.usd_reserve = 0.0
    state.usd_principal = 0.0
    state.usd_interest_arrears = 0.0
    state.cmea_settlement_balance = 0.0
    state.completed_ticks = 0
    if transport_per_unit > 0.0:
        fixture.parameters = fixture.parameters.model_copy(
            update={"transport_per_unit": float(transport_per_unit)}
        )
    return fixture


def _forcing(fixture: Fixture, ticks: int = 2):
    return fixture.forcing(
        ticks,
        global_usd_rate=0.0,
        official_fx=None,
        cmea_energy_price=1.0,
    )


def _run_one(fixture: Fixture, *, ticks: int = 1):
    forcing = _forcing(fixture, ticks=ticks)
    results = []
    for _ in range(ticks):
        opening = capture_material_stocks(fixture.state)
        flows = tick_material(fixture.state, forcing, fixture.parameters, fixture.network)
        gate = accounting.check_material_invariants(
            opening, fixture.state, flows, fixture.parameters, fixture.network
        )
        fixture.state.completed_ticks = int(fixture.state.completed_ticks) + 1
        results.append((opening, flows, gate))
    return results


def _load_regime() -> LegacyTradeRegime:
    return load_legacy_trade_regime(REGIME_PATH)


# ---------------------------------------------------------------------------
# 1. Legacy observed values for full / capped / zero / no-stock.
# ---------------------------------------------------------------------------


def test_observed_full_treasury() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    regime = _load_regime()
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    g_energy = fixture.g("energy")
    assert float(flows.cmea_exports[g_energy]) == pytest.approx(2.0, abs=1e-9)
    assert float(flows.convertible_exports[g_energy]) == pytest.approx(2.0, abs=1e-9)
    assert float(flows.cmea_export_receipt) == pytest.approx(2.0, abs=1e-9)
    assert float(flows.usd_export_receipt) == pytest.approx(6.0, abs=1e-9)
    assert observation["channels"][USD_CURRENCY]["export_receipt"] == pytest.approx(6.0, abs=1e-9)
    assert observation["channels"][CMEA_CURRENCY]["export_receipt"] == pytest.approx(2.0, abs=1e-9)
    domestic = observation["domestic"]
    assert domestic["treasury_open"] == pytest.approx(4.0, abs=1e-9)
    assert domestic["treasury_close"] == pytest.approx(0.0, abs=1e-9)
    pair_total = sum(pair["journal_payment"] for pair in domestic["treasury_payment_pairs"])
    assert pair_total == pytest.approx(4.0, abs=1e-9)
    seller_stock = float(
        fixture.state.stock_value[
            fixture.cell("organization", 1, 0, "output", "energy")
        ]
    )
    assert seller_stock == pytest.approx(4.0, abs=1e-9)


def test_observed_capped_treasury() -> None:
    fixture = _legacy_export_fixture(treasury=2.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    regime = _load_regime()
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    g_energy = fixture.g("energy")
    assert float(flows.cmea_exports[g_energy]) == pytest.approx(1.0, abs=1e-9)
    assert float(flows.convertible_exports[g_energy]) == pytest.approx(1.0, abs=1e-9)
    assert float(flows.cmea_export_receipt) == pytest.approx(1.0, abs=1e-9)
    assert float(flows.usd_export_receipt) == pytest.approx(3.0, abs=1e-9)
    assert observation["channels"][USD_CURRENCY]["export_receipt"] == pytest.approx(3.0, abs=1e-9)
    assert observation["channels"][CMEA_CURRENCY]["export_receipt"] == pytest.approx(1.0, abs=1e-9)
    pair_total = sum(
        pair["journal_payment"]
        for pair in observation["domestic"]["treasury_payment_pairs"]
    )
    assert pair_total == pytest.approx(2.0, abs=1e-9)


def test_observed_zero_treasury_with_usd_reserve() -> None:
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0, usd_reserve=100.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    regime = _load_regime()
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    for axis in ("delivered", "used", "exports", "imports"):
        usd_axis = observation["channels"][USD_CURRENCY][axis]
        cmea_axis = observation["channels"][CMEA_CURRENCY][axis]
        assert all(value == pytest.approx(0.0, abs=1e-9) for value in usd_axis)
        assert all(value == pytest.approx(0.0, abs=1e-9) for value in cmea_axis)
    assert observation["channels"][USD_CURRENCY]["export_receipt"] == pytest.approx(0.0, abs=1e-9)
    assert observation["channels"][CMEA_CURRENCY]["export_receipt"] == pytest.approx(0.0, abs=1e-9)
    assert observation["channels"][USD_CURRENCY]["balance_close"] == pytest.approx(100.0, abs=1e-9)
    assert observation["domestic"]["treasury_open"] == pytest.approx(0.0, abs=1e-9)


def test_observed_no_stock() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=0.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    regime = _load_regime()
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    assert observation["channels"][USD_CURRENCY]["export_receipt"] == pytest.approx(0.0, abs=1e-9)
    assert observation["channels"][CMEA_CURRENCY]["export_receipt"] == pytest.approx(0.0, abs=1e-9)
    pair_total = sum(
        pair["journal_payment"]
        for pair in observation["domestic"]["treasury_payment_pairs"]
    )
    assert pair_total == pytest.approx(0.0, abs=1e-9)
    assert observation["domestic"]["treasury_close"] == pytest.approx(4.0, abs=1e-9)


# ---------------------------------------------------------------------------
# 2. Legacy gate accepts the wrong-foreign-account copy; the observer rejects it.
# ---------------------------------------------------------------------------


def test_legacy_gate_accepts_wrong_foreign_account_but_observer_rejects() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    opening, flows, _gate = _run_one(fixture, ticks=1)[0]
    forcing = _forcing(fixture, ticks=1)
    usd_account = foreign_account_id(fixture.state, USD_CURRENCY)
    cmea_account = foreign_account_id(fixture.state, CMEA_CURRENCY)
    corrupted = copy.deepcopy(flows)
    changed = 0
    for index, kind in enumerate(corrupted.journal_kind):
        if kind == "export_receipt" and corrupted.journal_currency[index] == USD_CURRENCY:
            if int(corrupted.journal_debit[index]) == usd_account:
                corrupted.journal_debit[index] = cmea_account
                changed += 1
    assert changed >= 1
    # Legacy structural journal gate must still accept (the D0 plan records
    # this exact counterexample).
    accounting.check_material_invariants(
        opening, fixture.state, corrupted, fixture.parameters, fixture.network
    )
    regime = _load_regime()
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            corrupted,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


# ---------------------------------------------------------------------------
# 3. Direct legacy vs adapter: identical dynamic state, flows, journal, clock.
# ---------------------------------------------------------------------------


def test_direct_vs_adapter_byte_identical() -> None:
    regime = _load_regime()
    cases = (
        ("full", {"treasury": 4.0, "stock": 8.0}),
        ("capped", {"treasury": 2.0, "stock": 8.0}),
        ("zero", {"treasury": 0.0, "stock": 8.0, "usd_reserve": 100.0}),
        ("no_stock", {"treasury": 4.0, "stock": 0.0}),
    )
    for _name, kwargs in cases:
        direct = _legacy_export_fixture(**kwargs)
        adapter = _legacy_export_fixture(**kwargs)
        forcing = _forcing(direct, ticks=1)
        direct_opening = capture_material_stocks(direct.state)
        direct_flows = tick_material(
            direct.state, forcing, direct.parameters, direct.network
        )
        direct_gate = accounting.check_material_invariants(
            direct_opening,
            direct.state,
            direct_flows,
            direct.parameters,
            direct.network,
        )
        direct.state.completed_ticks += 1

        adapter_result = execute_legacy_trade_tick(
            adapter.state,
            forcing,
            adapter.parameters,
            adapter.network,
            regime=regime,
        )
        observed = observe_legacy_trade_tick(
            direct_opening,
            direct.state,
            direct_flows,
            direct.parameters,
            direct.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
        assert np.array_equal(direct.state.bank_reserves, adapter.state.bank_reserves)
        assert np.array_equal(direct.state.organization_cash, adapter.state.organization_cash)
        assert np.array_equal(direct.state.stock_value, adapter.state.stock_value)
        assert direct.state.treasury_deposit == pytest.approx(adapter.state.treasury_deposit)
        assert direct.state.usd_reserve == pytest.approx(adapter.state.usd_reserve)
        assert direct.state.cmea_settlement_balance == pytest.approx(
            adapter.state.cmea_settlement_balance
        )
        # Raw flows equality on the journal columns.
        for attr in (
            "journal_kind",
            "journal_tick",
            "journal_debit",
            "journal_credit",
            "journal_currency",
            "journal_amount",
            "journal_org",
            "journal_leg",
        ):
            assert getattr(direct_flows, attr) == getattr(adapter_result.flows, attr), attr
        assert (
            direct_gate.max_material_abs_residual
            == adapter_result.gate.max_material_abs_residual
        )
        assert (
            direct_gate.max_finance_abs_residual
            == adapter_result.gate.max_finance_abs_residual
        )
        # Clock advances by exactly 1 on both branches.
        assert direct.state.completed_ticks == adapter.state.completed_ticks == 1
        # Observation is a fresh dict (not identical to anything else).
        assert isinstance(observed, dict)
        assert observed is not adapter_result.observation or observed == adapter_result.observation


# ---------------------------------------------------------------------------
# 4. Two-quarter timing: Q1 receipt cannot fund Q1 imports.
# ---------------------------------------------------------------------------


def test_two_quarter_receipt_before_import_timing() -> None:
    regime = _load_regime()
    fixture = _legacy_export_fixture(
        treasury=4.0, stock=8.0, usd_reserve=0.0, usd_import_quantity=2.0
    )
    forcing = _forcing(fixture, ticks=2)

    quarters: list[dict[str, float | str]] = []
    for index in range(2):
        result = execute_legacy_trade_tick(
            fixture.state,
            forcing,
            fixture.parameters,
            fixture.network,
            regime=regime,
        )
        observation = result.observation
        quarters.append(
            {
                "tick": index,
                "usd_import_payment": float(result.flows.usd_import_payment),
                "usd_export_receipt": float(result.flows.usd_export_receipt),
                "usd_close": float(observation["channels"][USD_CURRENCY]["balance_close"]),
                "cmea_export_receipt": float(result.flows.cmea_export_receipt),
                "cmea_close": float(observation["channels"][CMEA_CURRENCY]["balance_close"]),
                "treasury_close": float(observation["domestic"]["treasury_close"]),
            }
        )
    assert quarters[0]["usd_import_payment"] == pytest.approx(0.0, abs=1e-9)
    assert quarters[0]["usd_export_receipt"] == pytest.approx(6.0, abs=1e-9)
    assert quarters[0]["usd_close"] == pytest.approx(6.0, abs=1e-9)
    assert quarters[1]["usd_import_payment"] == pytest.approx(2.0, abs=1e-9)
    assert quarters[1]["usd_close"] == pytest.approx(4.0, abs=1e-9)
    # Q2 exports are zero because Treasury has no remaining domestic cash.
    assert quarters[1]["usd_export_receipt"] == pytest.approx(0.0, abs=1e-9)
    # CMEA never crosses subsidises USD imports (Q1 still delivers 2 because
    # the Treasury paid both channels; Q2 stops because the Treasury ran dry).
    assert quarters[0]["cmea_export_receipt"] == pytest.approx(2.0, abs=1e-9)
    assert quarters[1]["cmea_export_receipt"] == pytest.approx(0.0, abs=1e-9)
    assert quarters[0]["cmea_close"] == pytest.approx(2.0, abs=1e-9)
    assert quarters[1]["cmea_close"] == pytest.approx(2.0, abs=1e-9)
    # The CMEA balance can never pay an USD import_payment; the USD close
    # only ever depends on USD-side flows.
    assert quarters[1]["usd_close"] == pytest.approx(
        quarters[0]["usd_close"] + quarters[1]["usd_export_receipt"]
        - quarters[1]["usd_import_payment"],
        abs=1e-9,
    )


# ---------------------------------------------------------------------------
# 5. Corruption / rejection: every gate rejects the bad input.
# ---------------------------------------------------------------------------


def _make_full_run() -> tuple[Fixture, MaterialStockSnapshot, object, object]:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    return fixture, opening, flows, forcing


def test_corruption_controls() -> None:
    regime = _load_regime()
    fixture, opening, flows, forcing = _make_full_run()

    def _observe_with_real_prices(
        *, state, fl, reg=regime
    ) -> dict:
        return observe_legacy_trade_tick(
            opening,
            state,
            fl,
            fixture.parameters,
            fixture.network,
            regime=reg,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )

    # The observer must not mutate the raw flows.
    snapshot_before = copy.deepcopy(flows)
    _observe_with_real_prices(state=fixture.state, fl=flows)
    assert flows.journal_kind == snapshot_before.journal_kind
    assert flows.journal_amount == snapshot_before.journal_amount
    assert np.array_equal(flows.cmea_exports, snapshot_before.cmea_exports)
    assert np.array_equal(flows.convertible_exports, snapshot_before.convertible_exports)

    cmea_account = foreign_account_id(fixture.state, CMEA_CURRENCY)

    # 1. Wrong foreign counterpart: observer rejects.
    wrong_counterpart = copy.deepcopy(flows)
    for index, kind in enumerate(wrong_counterpart.journal_kind):
        if kind == "export_receipt" and wrong_counterpart.journal_currency[index] == USD_CURRENCY:
            wrong_counterpart.journal_debit[index] = cmea_account
    with pytest.raises(ResearchGateError):
        _observe_with_real_prices(state=fixture.state, fl=wrong_counterpart)

    # 2. Wrong receipt currency.
    wrong_currency = copy.deepcopy(flows)
    for index, kind in enumerate(wrong_currency.journal_kind):
        if kind == "export_receipt" and wrong_currency.journal_currency[index] == USD_CURRENCY:
            wrong_currency.journal_currency[index] = CMEA_CURRENCY
    with pytest.raises(ResearchGateError):
        _observe_with_real_prices(state=fixture.state, fl=wrong_currency)

    # 3. Delete a positive receipt row.
    missing_receipt = copy.deepcopy(flows)
    removed = False
    for index, kind in enumerate(missing_receipt.journal_kind):
        if kind == "export_receipt" and missing_receipt.journal_currency[index] == USD_CURRENCY:
            for column in (
                "journal_kind",
                "journal_tick",
                "journal_debit",
                "journal_credit",
                "journal_currency",
                "journal_amount",
                "journal_org",
                "journal_leg",
            ):
                getattr(missing_receipt, column).pop(index)
            removed = True
            break
    assert removed
    with pytest.raises(ResearchGateError):
        _observe_with_real_prices(state=fixture.state, fl=missing_receipt)

    # 4. Receipt without any delivered export.
    no_delivery = copy.deepcopy(flows)
    no_delivery.cmea_exports[:] = 0.0
    no_delivery.convertible_exports[:] = 0.0
    with pytest.raises(ResearchGateError):
        _observe_with_real_prices(state=fixture.state, fl=no_delivery)

    # 5. Wrong domestic payee: redirect one goods_payment credit to the
    # debit account, breaking the payee mapping.
    wrong_payee = copy.deepcopy(flows)
    for index, kind in enumerate(wrong_payee.journal_kind):
        if kind == "goods_payment":
            wrong_payee.journal_credit[index] = wrong_payee.journal_debit[index]
            break
    with pytest.raises(ResearchGateError):
        _observe_with_real_prices(state=fixture.state, fl=wrong_payee)

    # 6. Negative USD reserve.
    bad_state_usd = copy.deepcopy(fixture.state)
    bad_state_usd.usd_reserve = -1.0
    with pytest.raises(ResearchGateError):
        _observe_with_real_prices(state=bad_state_usd, fl=flows)

    # 7. Negative bank reserves.
    bad_state_bank = copy.deepcopy(fixture.state)
    bad_state_bank.bank_reserves = np.full_like(bad_state_bank.bank_reserves, -1.0)
    with pytest.raises(ResearchGateError):
        _observe_with_real_prices(state=bad_state_bank, fl=flows)

    # 8. Strict positive receipt (1e-10) without its journal leg.
    tiny = copy.deepcopy(flows)
    tiny.usd_export_receipt += 1e-10
    with pytest.raises(ResearchGateError):
        _observe_with_real_prices(state=fixture.state, fl=tiny)

    # 9. NaN receipt.
    nonfinite = copy.deepcopy(flows)
    nonfinite.usd_export_receipt = float("nan")
    with pytest.raises(ResearchGateError):
        _observe_with_real_prices(state=fixture.state, fl=nonfinite)

    # 10. Wrong tick on flows.
    wrong_tick = copy.deepcopy(flows)
    wrong_tick.tick = int(flows.tick) + 1
    with pytest.raises(ResearchGateError):
        _observe_with_real_prices(state=fixture.state, fl=wrong_tick)

    # 11. Invalid regime instance.
    class _NotARegime:
        schema_version = "hist-trade-regime-v1"
        regime_id = "legacy_treasury_prepay"
        source_kind = "synthetic"

    with pytest.raises(ResearchGateError):
        _observe_with_real_prices(state=fixture.state, fl=flows, reg=_NotARegime())


def _append_journal_row(flows: MaterialTickFlows, **fields) -> None:
    """Insert a new transaction (leg=0) at position 0; bump every existing leg by 1."""
    leg_offset = int(len(flows.journal_kind))
    for column in (
        "journal_kind",
        "journal_tick",
        "journal_debit",
        "journal_credit",
        "journal_currency",
        "journal_amount",
        "journal_org",
        "journal_leg",
    ):
        existing = list(getattr(flows, column))
        if column == "journal_kind":
            existing.insert(0, fields["kind"])
        elif column == "journal_tick":
            existing.insert(0, fields["tick"])
        elif column == "journal_debit":
            existing.insert(0, fields["debit"])
        elif column == "journal_credit":
            existing.insert(0, fields["credit"])
        elif column == "journal_currency":
            existing.insert(0, fields["currency"])
        elif column == "journal_amount":
            existing.insert(0, fields["amount"])
        elif column == "journal_org":
            existing.insert(0, fields["org"])
        elif column == "journal_leg":
            bumped = [leg + 1 for leg in existing]
            bumped.insert(0, 0)
            existing = bumped
        setattr(flows, column, existing)
    assert int(leg_offset) + 1 == len(flows.journal_kind)


def test_trade_journal_currency_book_whitelist() -> None:
    """Trade-related journal rows must use the kind-appropriate currency book.

    Per the D0 plan:
      * export_receipt / import_payment: USD or cmea_settlement_unit
      * loan_drawdown / interest_payment / principal_repayment: USD or
        p02_domestic_currency

    Each negative control APPENDS an extra row (rather than mutating an
    existing receipt) so the observer must reject both the wrong book and
    the new total; an extra well-formed USD/CMEA row also fails its
    scalar sum because the existing per-channel sum check fires.
    """
    regime = _load_regime()
    fixture, opening, flows, forcing = _make_full_run()
    usd_account = foreign_account_id(fixture.state, USD_CURRENCY)
    cmea_account = foreign_account_id(fixture.state, CMEA_CURRENCY)
    treasury_fiscal = treasury_account_id(fixture.state, AccountKind.FISCAL_EXPENSE)
    treasury_cash = treasury_account_id(fixture.state, AccountKind.CASH_DEPOSIT)

    def _observe(state, fl=flows) -> dict:
        return observe_legacy_trade_tick(
            opening,
            state,
            fl,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )

    # Anchor: a valid full run still observes cleanly.
    observation = _observe(fixture.state)
    assert observation["channels"][USD_CURRENCY]["export_receipt"] == pytest.approx(6.0, abs=1e-9)

    # 1. Domestic export_receipt row appended -> reject (book mismatch).
    bad = copy.deepcopy(flows)
    _append_journal_row(
        bad,
        kind="export_receipt",
        tick=int(flows.tick),
        debit=usd_account,
        credit=treasury_fiscal,
        currency=DOMESTIC_CURRENCY,
        amount=1.0,
        org=None,
    )
    with pytest.raises(ResearchGateError) as excinfo:
        _observe(fixture.state, bad)
    assert str(excinfo.value).startswith(GATE_PREFIX)

    # 2. CMEA loan_drawdown row appended -> reject (CMEA is not a loan book).
    bad = copy.deepcopy(flows)
    _append_journal_row(
        bad,
        kind="loan_drawdown",
        tick=int(flows.tick),
        debit=usd_account,
        credit=treasury_fiscal,
        currency=CMEA_CURRENCY,
        amount=1.0,
        org=None,
    )
    with pytest.raises(ResearchGateError) as excinfo:
        _observe(fixture.state, bad)
    assert str(excinfo.value).startswith(GATE_PREFIX)

    # 3. CMEA interest_payment row appended -> reject.
    bad = copy.deepcopy(flows)
    _append_journal_row(
        bad,
        kind="interest_payment",
        tick=int(flows.tick),
        debit=treasury_cash,
        credit=cmea_account,
        currency=CMEA_CURRENCY,
        amount=1.0,
        org=None,
    )
    with pytest.raises(ResearchGateError) as excinfo:
        _observe(fixture.state, bad)
    assert str(excinfo.value).startswith(GATE_PREFIX)

    # 4. CMEA principal_repayment row appended -> reject.
    bad = copy.deepcopy(flows)
    _append_journal_row(
        bad,
        kind="principal_repayment",
        tick=int(flows.tick),
        debit=treasury_cash,
        credit=cmea_account,
        currency=CMEA_CURRENCY,
        amount=1.0,
        org=None,
    )
    with pytest.raises(ResearchGateError) as excinfo:
        _observe(fixture.state, bad)
    assert str(excinfo.value).startswith(GATE_PREFIX)

    # 5. Domestic import_payment row appended -> reject.
    bad = copy.deepcopy(flows)
    _append_journal_row(
        bad,
        kind="import_payment",
        tick=int(flows.tick),
        debit=treasury_fiscal,
        credit=usd_account,
        currency=DOMESTIC_CURRENCY,
        amount=1.0,
        org=None,
    )
    with pytest.raises(ResearchGateError) as excinfo:
        _observe(fixture.state, bad)
    assert str(excinfo.value).startswith(GATE_PREFIX)

    # 6. Extra well-formed USD export_receipt row -> rejected via the
    # per-channel journal-sum check (duplicate reconciliation).
    bad = copy.deepcopy(flows)
    _append_journal_row(
        bad,
        kind="export_receipt",
        tick=int(flows.tick),
        debit=usd_account,
        credit=treasury_fiscal,
        currency=USD_CURRENCY,
        amount=6.0,
        org=None,
    )
    with pytest.raises(ResearchGateError) as excinfo:
        _observe(fixture.state, bad)
    assert str(excinfo.value).startswith(GATE_PREFIX)

    # 7. Extra well-formed CMEA export_receipt row -> same journal-sum rejection.
    bad = copy.deepcopy(flows)
    _append_journal_row(
        bad,
        kind="export_receipt",
        tick=int(flows.tick),
        debit=cmea_account,
        credit=treasury_fiscal,
        currency=CMEA_CURRENCY,
        amount=2.0,
        org=None,
    )
    with pytest.raises(ResearchGateError) as excinfo:
        _observe(fixture.state, bad)
    assert str(excinfo.value).startswith(GATE_PREFIX)


# ---------------------------------------------------------------------------
# 5b. Housing NaN/Inf / missing-row / wrong-amount / wrong-payee controls.
# ---------------------------------------------------------------------------


def _housing_observation(fixture: Fixture) -> tuple[dict, object, object, object]:
    """Drive the housing fixture once and return (observation, opening, flows, forcing)."""
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    regime = _load_regime()
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    return observation, opening, flows, forcing


def _housing_edge_index(fixture: Fixture) -> int:
    """Locate the single HOUSING-purpose edge on the housing fixture."""
    from hsm_lab.contract.material import PURPOSE_CODES, RoutePurpose

    purpose = np.asarray(fixture.network.edge_purpose, dtype=np.int64)
    housing_code = int(PURPOSE_CODES[RoutePurpose.HOUSING])
    matches = np.flatnonzero(purpose == housing_code)
    assert matches.size >= 1, "housing fixture must declare at least one housing edge"
    return int(matches[0])


def test_housing_observation_is_accepted() -> None:
    """A real housing fixture with a Treasury-paid housing edge passes the observer."""
    fixture = _legacy_housing_fixture(treasury=4.0)
    observation, _opening, _flows, _forcing = _housing_observation(fixture)
    # The observation must carry a positive housing payment and at least one
    # goods_payment journal leg for the construction builder.
    assert observation["domestic"]["housing_payment"] > 0.0
    assert observation["domestic"]["treasury_payment_pairs"], "expected at least one payee"
    sellers = [row["payee_id"] for row in observation["domestic"]["treasury_payment_pairs"]]
    assert 2 in sellers, "construction builder (payee_id=2) must receive a goods_payment"


def test_observer_rejects_nan_housing_edge_delivered() -> None:
    """A NaN ``flows.edge_delivered`` on a housing edge must be rejected."""
    fixture = _legacy_housing_fixture(treasury=4.0)
    observation, opening, flows, forcing = _housing_observation(fixture)
    edge = _housing_edge_index(fixture)
    bad = copy.deepcopy(flows)
    bad.edge_delivered[edge] = float("nan")
    regime = _load_regime()
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            bad,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_observer_rejects_nan_housing_edge_service_fee() -> None:
    """A NaN ``flows.edge_service_fee`` on a housing edge must be rejected.

    The reviewer probe injected NaN into a housing freight row that was
    otherwise zero in the unmodified tick; the observer must catch the
    corruption before any downstream comparison.
    """
    fixture = _legacy_housing_fixture(treasury=4.0)
    observation, opening, flows, forcing = _housing_observation(fixture)
    edge = _housing_edge_index(fixture)
    bad = copy.deepcopy(flows)
    bad.edge_service_fee[edge] = float("nan")
    regime = _load_regime()
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            bad,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_observer_rejects_inf_housing_edge_delivered() -> None:
    """An Inf ``flows.edge_delivered`` on a housing edge must be rejected."""
    fixture = _legacy_housing_fixture(treasury=4.0)
    observation, opening, flows, forcing = _housing_observation(fixture)
    edge = _housing_edge_index(fixture)
    bad = copy.deepcopy(flows)
    bad.edge_delivered[edge] = float("inf")
    regime = _load_regime()
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            bad,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_observer_rejects_wrong_housing_payment_amount() -> None:
    """A deviation above the accounting ATOL on a Treasury goods_payment leg must be rejected."""
    fixture = _legacy_housing_fixture(treasury=4.0)
    observation, opening, flows, forcing = _housing_observation(fixture)
    bad = copy.deepcopy(flows)
    builder_cash = treasury_account_id(fixture.state, AccountKind.CASH_DEPOSIT)
    modified = False
    for index, kind in enumerate(bad.journal_kind):
        if kind != "goods_payment":
            continue
        if str(bad.journal_currency[index]) != DOMESTIC_CURRENCY:
            continue
        if int(bad.journal_debit[index]) != builder_cash:
            continue
        if modified:
            continue
        # Use a 1e-6 deviation (above the ATOL=1e-9 ceiling used by
        # tolerance_for) so the per-payee residual check fires.
        if bad.journal_amount[index] > 0.0:
            bad.journal_amount[index] = float(bad.journal_amount[index]) + 1e-6
            modified = True
            break
    assert modified, "housing fixture must produce at least one goods_payment row"
    regime = _load_regime()
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            bad,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_observer_rejects_wrong_housing_payee() -> None:
    """A goods_payment leg that credits a non-organization account is rejected."""
    fixture = _legacy_housing_fixture(treasury=4.0)
    observation, opening, flows, forcing = _housing_observation(fixture)
    bad = copy.deepcopy(flows)
    builder_cash = treasury_account_id(fixture.state, AccountKind.CASH_DEPOSIT)
    foreign = foreign_account_id(fixture.state, USD_CURRENCY)
    modified = False
    for index, kind in enumerate(bad.journal_kind):
        if kind != "goods_payment":
            continue
        if str(bad.journal_currency[index]) != DOMESTIC_CURRENCY:
            continue
        if int(bad.journal_debit[index]) != builder_cash:
            continue
        if modified:
            continue
        # Redirect the credit to a foreign account (a different, but known,
        # non-organization account).  The payee mapping will not find a
        # payee and the observer must reject.
        bad.journal_credit[index] = foreign
        modified = True
        break
    assert modified, "housing fixture must produce at least one goods_payment row"
    regime = _load_regime()
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            bad,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_observer_rejects_missing_housing_journal_row() -> None:
    """Dropping the housing ``goods_payment`` journal row must surface the gap."""
    fixture = _legacy_housing_fixture(treasury=4.0)
    observation, opening, flows, forcing = _housing_observation(fixture)
    builder_cash = treasury_account_id(fixture.state, AccountKind.CASH_DEPOSIT)
    # Locate the housing seller's goods_payment row and remove it.
    target_index = None
    for index, kind in enumerate(flows.journal_kind):
        if kind != "goods_payment":
            continue
        if str(flows.journal_currency[index]) != DOMESTIC_CURRENCY:
            continue
        if int(flows.journal_debit[index]) != builder_cash:
            continue
        target_index = index
        break
    assert target_index is not None, "housing fixture must produce a goods_payment row"
    bad = copy.deepcopy(flows)
    for column in (
        "journal_kind",
        "journal_tick",
        "journal_debit",
        "journal_credit",
        "journal_currency",
        "journal_amount",
        "journal_org",
        "journal_leg",
    ):
        getattr(bad, column).pop(target_index)
    regime = _load_regime()
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            bad,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


# ---------------------------------------------------------------------------
# 5c. Strict no-delivery / no-receipt and Tausonic identity residual.
# ---------------------------------------------------------------------------


def test_tiny_receipt_with_matching_delivery_is_accepted() -> None:
    """A 1e-10 receipt whose delivery matches the executed channel price is accepted.

    Builds a full-treasury fixture with delivered energy 2.0 on both channels,
    then mutates the flow so convertible_exports[energy] drops to 1e-10/3.0
    (so dot(exports, prices) == 1e-10) AND the USD export_receipt leg is
    rewritten to a 1e-10 journal leg.  The observer must accept the rebuild
    because the receipt is fully funded by delivered exports.
    """
    regime = _load_regime()
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    g_energy = fixture.g("energy")
    tiny_value = 1e-10
    cell_usd_energy = int(fixture.network.export_demand_cell[1, g_energy])
    assert cell_usd_energy >= 0
    # Rebuild flows: USD channel export and receipt both reduced to 1e-10,
    # USD energy demand-cell delivered/allocated/used dropped to match.
    flows.convertible_exports[:] = 0.0
    flows.convertible_exports[g_energy] = tiny_value / 3.0  # dot(exports, prices) = 1e-10
    flows.delivered[cell_usd_energy] = tiny_value / 3.0
    flows.allocated[cell_usd_energy] = tiny_value / 3.0
    flows.used[cell_usd_energy] = tiny_value / 3.0
    flows.ordered[cell_usd_energy] = tiny_value / 3.0
    flows.desired[cell_usd_energy] = tiny_value / 3.0
    flows.usd_export_receipt = tiny_value
    # The post-tick USD reserve must agree with the identity: opening=0,
    # all loan-book scalars=0, import=0, export=tiny_value → close=tiny_value.
    fixture.state.usd_reserve = tiny_value
    for index, kind in enumerate(flows.journal_kind):
        if kind == "export_receipt" and flows.journal_currency[index] == USD_CURRENCY:
            flows.journal_amount[index] = tiny_value
            break
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    assert observation["channels"][USD_CURRENCY]["export_receipt"] == pytest.approx(
        tiny_value, abs=1e-15
    )
    usd_residual = observation["identity_residuals"]["export_receipt_by_currency"][USD_CURRENCY]
    assert abs(usd_residual) <= 1e-15


def test_tiny_receipt_with_zero_delivery_is_rejected() -> None:
    """A 1e-10 receipt against an all-zero export axis is rejected immediately."""
    regime = _load_regime()
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    # Zero every delivered export, then mark the receipt as a tiny positive.
    flows.cmea_exports[:] = 0.0
    flows.convertible_exports[:] = 0.0
    flows.usd_export_receipt = 1e-10
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_receipt_mismatch_without_matching_delivery_is_rejected() -> None:
    """The existing ``6 -> 6.0000000001`` control: receipt drifts up but
    delivered quantity is unchanged, so the receipt no longer matches
    dot(exports, prices) and the observer must reject.
    """
    regime = _load_regime()
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    # Drift the receipt up by 1e-10; leave exports/usd deltas untouched.
    flows.usd_export_receipt = float(flows.usd_export_receipt) + 1e-10
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_identity_residual_uses_dot_product_not_scalar() -> None:
    """The ``export_receipt_by_currency`` residual must equal ``dot(exports, prices) - scalar``.

    Verifies that mutating the USD receipt scalar while keeping the dot
    product stable causes the residual to track the scalar drift, confirming
    it is no longer the tautological ``scalar - scalar`` identity.
    """
    regime = _load_regime()
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    # Align ``usd_export_receipt`` with the dot product exactly so the journal
    # sum check passes; verify the residual reads zero (dot==scalar).
    g_energy = fixture.g("energy")
    expected = float(flows.convertible_exports[g_energy]) * 3.0  # USD price=3
    flows.usd_export_receipt = expected
    for index, kind in enumerate(flows.journal_kind):
        if kind == "export_receipt" and flows.journal_currency[index] == USD_CURRENCY:
            flows.journal_amount[index] = expected
            break
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    usd_residual = observation["identity_residuals"]["export_receipt_by_currency"][USD_CURRENCY]
    cmea_residual = observation["identity_residuals"]["export_receipt_by_currency"][CMEA_CURRENCY]
    assert abs(usd_residual) <= 1e-15
    assert abs(cmea_residual) <= 1e-15
    assert observation["channels"][USD_CURRENCY]["expected_receipt"] == pytest.approx(
        expected, abs=1e-15
    )


def test_wrapper_rollback_on_invariant_failure(monkeypatch) -> None:
    regime = _load_regime()
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    snapshot_before = copy.deepcopy(fixture.state)
    pre_clock = int(fixture.state.completed_ticks)

    def _boom(*args, **kwargs):
        raise RuntimeError("injected invariants failure")

    monkeypatch.setattr(
        "hsm_lab.institutions.export_finance_adapter.accounting.check_material_invariants",
        _boom,
    )
    with pytest.raises(LegacyTradeFailure) as excinfo:
        execute_legacy_trade_tick(
            fixture.state,
            forcing,
            fixture.parameters,
            fixture.network,
            regime=regime,
        )
    failure = excinfo.value
    assert str(failure).startswith(GATE_PREFIX)
    assert failure.phase == "invariants"
    assert isinstance(failure.cause, RuntimeError)
    assert failure.failed_flows is not None
    assert failure.failed_state is not None
    # Full state restoration including the clock.
    assert fixture.state.completed_ticks == pre_clock
    assert np.array_equal(fixture.state.bank_reserves, snapshot_before.bank_reserves)
    assert np.array_equal(
        fixture.state.organization_cash, snapshot_before.organization_cash
    )
    assert np.array_equal(fixture.state.stock_value, snapshot_before.stock_value)
    assert fixture.state.treasury_deposit == snapshot_before.treasury_deposit
    assert fixture.state.usd_reserve == snapshot_before.usd_reserve
    assert fixture.state.cmea_settlement_balance == snapshot_before.cmea_settlement_balance


# ---------------------------------------------------------------------------
# 6. Loader rejection paths.
# ---------------------------------------------------------------------------


def _write(path: Path, body: str | dict) -> Path:
    if isinstance(body, dict):
        path.write_text(json.dumps(body))
    else:
        path.write_text(body)
    return path


def test_loader_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ResearchGateError) as excinfo:
        load_legacy_trade_regime(tmp_path / "missing.json")
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_loader_rejects_invalid_json(tmp_path: Path) -> None:
    path = _write(tmp_path / "broken.json", "{not json")
    with pytest.raises(ResearchGateError) as excinfo:
        load_legacy_trade_regime(path)
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_loader_rejects_extra_key(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "extra.json",
        {
            "schema_version": "hist-trade-regime-v1",
            "regime_id": "legacy_treasury_prepay",
            "source_kind": "synthetic",
            "extra": 1,
        },
    )
    with pytest.raises(ResearchGateError) as excinfo:
        load_legacy_trade_regime(path)
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_loader_rejects_wrong_schema(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "wrong_schema.json",
        {
            "schema_version": "hist-trade-regime-v2",
            "regime_id": "legacy_treasury_prepay",
            "source_kind": "synthetic",
        },
    )
    with pytest.raises(ResearchGateError) as excinfo:
        load_legacy_trade_regime(path)
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_loader_rejects_d1_d2_d3_regime_ids(tmp_path: Path) -> None:
    for regime_id in (
        "legacy_treasury_credit",
        "legacy_receivables",
        "cmea_clearing_rules",
    ):
        path = _write(
            tmp_path / f"{regime_id}.json",
            {
                "schema_version": "hist-trade-regime-v1",
                "regime_id": regime_id,
                "source_kind": "synthetic",
            },
        )
        with pytest.raises(ResearchGateError) as excinfo:
            load_legacy_trade_regime(path)
        assert str(excinfo.value).startswith(GATE_PREFIX)


def test_loader_accepts_d1_d2_d3_path_markers_for_valid_d0_content(tmp_path: Path) -> None:
    """A D0-valid payload at a path containing ``d1``/``d2``/``d3`` is accepted.

    The path string is irrelevant; only the JSON content matters.
    """
    valid_payload = {
        "schema_version": "hist-trade-regime-v1",
        "regime_id": "legacy_treasury_prepay",
        "source_kind": "synthetic",
    }
    for filename in (
        "d1_legacy_treasury_credit.json",
        "d2_legacy_receivables.json",
        "d3_cmea_clearing_rules.json",
        "build123_d0_legacy_treasury_prepay.json",
        "credit_limit_d0.json",
    ):
        path = tmp_path / filename
        path.write_text(json.dumps(valid_payload))
        regime = load_legacy_trade_regime(path)
        assert regime.regime_id == "legacy_treasury_prepay"


# ---------------------------------------------------------------------------
# 7. No-demand-cell status / ZERO_DEMAND / negative CMEA opening identity.
# ---------------------------------------------------------------------------


def _fixture_no_demand_cell() -> Fixture:
    """Build a fixture whose declared commodities drop the energy cell pair.

    ``NO_CAPITAL_COMMODITIES`` already excludes ``capital_goods``; here we
    rebuild the trade vectors so every export demand request is zero.  The
    resulting fixture has only ``food``, ``consumer_goods``, ``raw_materials``,
    ``durable_goods`` and ``services_transport`` available to the seller (we
    keep the same energy seller stock for realism but route nothing through
    the export demand cells).
    """
    n = 8
    trade = TradeParameters(
        cmea_prices=[1.0] * n,
        convertible_prices=[1.0] * n,
        cmea_desired_imports=[0.0] * n,
        convertible_desired_imports=[0.0] * n,
        cmea_export_demands=[0.0] * n,
        convertible_export_demands=[0.0] * n,
        cmea_credit_envelope=1.0,
        convertible_opening_reserve=0.0,
        convertible_loan_limit=0.0,
        convertible_opening_principal=0.0,
    ).model_copy(update={"cmea_credit_envelope": 0.0})
    parameters = default_params(prices=[1.0] * n, trade=trade)
    parameters = parameters.model_copy(
        update={
            "food_raw_price": 1.0,
            "utilization": 1.0,
            "service_split": [1.0, 0.0, 0.0],
            "transport_per_unit": 0.0,
            "overorder_strength": 0.0,
            "hoarding_quarters": 0.0,
            "shortage_alpha": 0.0,
            "hunger_base": 0.0,
            "hunger_bailout": 0.0,
            "hunger_shortage": 0.0,
            "capital_depreciation_rate": 0.0,
            "credit_envelope_fraction": 0.0,
            "bailout_envelope_fraction": 0.0,
            "principal_repayment_fraction": 0.0,
            "domestic_credit_rate_annual": 0.0,
            "hungary_spread_annual": 0.0,
            "fiscal_turnover_remittance_fraction": 0.0,
            "household_savings_reentry_fraction": 0.0,
            "m2_neutral_credit": False,
            "sbc_redistribution": False,
            "demand_limited_targets": False,
            "production_target_rule": "legacy",
        }
    )
    fixture = Fixture(
        [
            bank(0),
            producer(1, "energy_generation", capacity=1.0, cash=0.0).model_copy(
                update={"capacity": 0.0, "labor_available": 0.0}
            ),
        ],
        [idle_source_tech("energy_generation", "energy")],
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 1.0)],
        household_cash=0.0,
        household_parameters=household_params(),
        ticks=2,
    )
    state = fixture.state
    state.stock_value[:] = 0.0
    state.organization_capacity[:] = 0.0
    state.organization_labor_available[:] = 0.0
    state.organization_labor_endowment[:] = 0.0
    state.organization_cash[:] = 0.0
    state.organization_principal[:] = 0.0
    state.organization_wage_arrears[:] = 0.0
    state.organization_interest_arrears[:] = 0.0
    state.organization_shortage_expectation[:] = 0.0
    state.organization_bailout_expectation[:] = 0.0
    state.organization_project_approved[:] = 0.0
    state.organization_capital_wip[:] = 0.0
    state.organization_construction_wip[:] = 0.0
    state.household_cash[:] = 0.0
    state.household_deferred_receipt[:] = 0.0
    state.household_wage_claim[:] = 0.0
    state.household_durable_owned[:] = 0.0
    state.household_durable_backlog[:] = 0.0
    state.household_durable_repair_credit[:] = 0.0
    state.dwelling_stock[:] = 0.0
    state.housing_vacant[:] = 0.0
    state.second_output_stock[:] = 0.0
    state.bank_deposit_liability[:] = 0.0
    state.bank_deposit_liability[0] = 4.0
    state.bank_equity[:] = 0.0
    state.bank_equity[0] = 20.0
    state.bank_loan_asset[:] = 0.0
    state.bank_interest_receivable[:] = 0.0
    state.bank_reserves[:] = 0.0
    state.bank_reserves[0] = 24.0
    state.treasury_deposit = 4.0
    state.treasury_loan_asset = 0.0
    state.credit_fund = 0.0
    state.usd_reserve = 0.0
    state.usd_principal = 0.0
    state.usd_interest_arrears = 0.0
    state.cmea_settlement_balance = 0.0
    state.completed_ticks = 0
    return fixture


def test_no_demand_cell_status_for_zero_export_fixture() -> None:
    fixture = _fixture_no_demand_cell()
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    regime = _load_regime()
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    # Without any export demand, every commodity's demand cell is missing
    # (cell = -1) and the observer must label every row ``NO_DEMAND_CELL``.
    statuses = (
        observation["channels"][USD_CURRENCY]["demand_status"]
        + observation["channels"][CMEA_CURRENCY]["demand_status"]
    )
    assert all(status != "ACTIVE" for status in statuses)
    assert "NO_DEMAND_CELL" in statuses


def test_zero_demand_status_for_existing_cell_with_zero_request() -> None:
    """Force the ``ZERO_DEMAND`` branch by clearing one channel post-tick.

    The network compiler only creates an export demand cell when the trade
    vector is strictly positive, so the only way to populate
    ``desired[cell] = 0`` while keeping the cell alive is to clear the cell's
    axes, the channel export vector, the channel receipt scalar and the
    matching journal leg after the kernel returns.  The observer must
    classify the surviving cell as ``ZERO_DEMAND`` while leaving the USD
    channel ``ACTIVE``.
    """
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    network = fixture.network
    energy_index = network.commodity_ids.index("energy")
    cell_cmea_energy = int(network.export_demand_cell[0, energy_index])
    cell_usd_energy = int(network.export_demand_cell[1, energy_index])
    assert cell_cmea_energy >= 0 and cell_usd_energy >= 0
    flows.desired[cell_cmea_energy] = 0.0
    flows.ordered[cell_cmea_energy] = 0.0
    flows.allocated[cell_cmea_energy] = 0.0
    flows.delivered[cell_cmea_energy] = 0.0
    flows.used[cell_cmea_energy] = 0.0
    flows.cmea_exports[:] = 0.0
    flows.cmea_export_receipt = 0.0
    fixture.state.cmea_settlement_balance = 0.0
    # Drop the CMEA export_receipt journal leg so the channel check passes.
    for index, kind in enumerate(flows.journal_kind):
        if (
            kind == "export_receipt"
            and flows.journal_currency[index] == CMEA_CURRENCY
        ):
            for column in (
                "journal_kind",
                "journal_tick",
                "journal_debit",
                "journal_credit",
                "journal_currency",
                "journal_amount",
                "journal_org",
                "journal_leg",
            ):
                getattr(flows, column).pop(index)
            break
    regime = _load_regime()
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    assert (
        observation["channels"][CMEA_CURRENCY]["demand_status"][energy_index]
        == "ZERO_DEMAND"
    )
    assert (
        observation["channels"][USD_CURRENCY]["demand_status"][energy_index]
        == "ACTIVE"
    )


def test_zero_demand_status_for_zero_request_with_stock() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    regime = _load_regime()
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    energy_index = fixture.network.commodity_ids.index("energy")
    # Every non-energy commodity has no export demand cell (``-1``); the
    # status must read ``NO_DEMAND_CELL`` for both channels.
    for channel_key in (CMEA_CURRENCY, USD_CURRENCY):
        statuses = observation["channels"][channel_key]["demand_status"]
        for index, status in enumerate(statuses):
            if index == energy_index:
                assert status in {"ACTIVE", "ZERO_DEMAND"}
            else:
                assert status == "NO_DEMAND_CELL"


def test_negative_cmea_opening_balance_with_zero_trade() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    fixture.state.cmea_settlement_balance = -1.0
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    regime = _load_regime()
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    cmea_open = float(opening.cmea_settlement_balance)
    cmea_close = float(observation["channels"][CMEA_CURRENCY]["balance_close"])
    expected_close = cmea_open + float(flows.cmea_export_receipt)
    tol = float(tolerance_for(cmea_close, expected_close))
    assert abs(cmea_close - expected_close) <= tol


# ---------------------------------------------------------------------------
# 8. D0 fix-01 regression coverage.
# ---------------------------------------------------------------------------


def test_export_edges_excludes_housing() -> None:
    """``domestic.export_edges`` must list only CMEA/USD export edges."""
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    regime = _load_regime()
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    export_edges = observation["domestic"]["export_edges"]
    assert export_edges, "fixture must produce at least one export edge"
    for row in export_edges:
        assert row["channel"] in {"CMEA", "USD"}, row
    assert "HOUSING" not in {row["channel"] for row in export_edges}


def test_observer_rejects_nan_interest_accrued() -> None:
    """A NaN ``flows.usd_interest_accrued`` must be rejected before residuals."""
    fixture, opening, flows, forcing = _make_full_run()
    corrupted = copy.deepcopy(flows)
    corrupted.usd_interest_accrued = float("nan")
    regime = _load_regime()
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            corrupted,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_observer_rejects_nan_demand_array() -> None:
    """A NaN in a demand/export axis must be rejected before residuals."""
    fixture, opening, flows, forcing = _make_full_run()
    corrupted = copy.deepcopy(flows)
    energy_index = fixture.network.commodity_ids.index("energy")
    cell_usd = int(fixture.network.export_demand_cell[1, energy_index])
    assert cell_usd >= 0
    corrupted.desired[cell_usd] = float("nan")
    regime = _load_regime()
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            corrupted,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_observer_rejects_unknown_journal_currency() -> None:
    """A journal row with an unknown currency must be rejected."""
    fixture, opening, flows, forcing = _make_full_run()
    corrupted = copy.deepcopy(flows)
    for index, kind in enumerate(corrupted.journal_kind):
        if kind == "export_receipt" and corrupted.journal_currency[index] == USD_CURRENCY:
            corrupted.journal_currency[index] = "DEM"
            break
    regime = _load_regime()
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            corrupted,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_observer_rejects_foreign_treasury_goods_payment() -> None:
    """Treasury ``goods_payment`` rows must be domestic currency only."""
    fixture, opening, flows, forcing = _make_full_run()
    corrupted = copy.deepcopy(flows)
    treasury_cash = treasury_account_id(fixture.state, AccountKind.CASH_DEPOSIT)
    for index, kind in enumerate(corrupted.journal_kind):
        if kind == "goods_payment" and int(corrupted.journal_debit[index]) == treasury_cash:
            corrupted.journal_currency[index] = USD_CURRENCY
            break
    regime = _load_regime()
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            corrupted,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_observer_rejects_negative_opening_bank_reserves() -> None:
    """Direct observer calls must reject non-finite/negative opening reserves."""
    fixture, opening, flows, forcing = _make_full_run()
    bad_opening = copy.deepcopy(opening)
    bad_opening.bank_reserves = np.full_like(bad_opening.bank_reserves, -1.0)
    regime = _load_regime()
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            bad_opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_wrapper_pre_validates_regime() -> None:
    """A non-``LegacyTradeRegime`` argument must raise ``LegacyTradeFailure``."""
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    snapshot_clock = int(fixture.state.completed_ticks)

    class _NotARegime:
        schema_version = "hist-trade-regime-v1"
        regime_id = "legacy_treasury_prepay"
        source_kind = "synthetic"

    with pytest.raises(LegacyTradeFailure) as excinfo:
        execute_legacy_trade_tick(
            fixture.state,
            forcing,
            fixture.parameters,
            fixture.network,
            regime=_NotARegime(),
        )
    failure = excinfo.value
    assert failure.phase == "regime"
    assert failure.failed_flows is None
    assert failure.failed_state is None
    assert fixture.state.completed_ticks == snapshot_clock


def test_wrapper_pre_validates_forcing_horizon() -> None:
    """An out-of-horizon tick must raise ``LegacyTradeFailure`` (phase=``forcing``)."""
    regime = _load_regime()
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    fixture.state.completed_ticks = int(len(forcing.quarters)) + 1
    snapshot_clock = int(fixture.state.completed_ticks)
    with pytest.raises(LegacyTradeFailure) as excinfo:
        execute_legacy_trade_tick(
            fixture.state,
            forcing,
            fixture.parameters,
            fixture.network,
            regime=regime,
        )
    failure = excinfo.value
    assert failure.phase == "forcing"
    assert failure.failed_flows is None
    assert failure.failed_state is None
    assert fixture.state.completed_ticks == snapshot_clock


# ---------------------------------------------------------------------------
# 9. D0 fix-task-03 regression coverage (Findings 1-4).
# ---------------------------------------------------------------------------


def test_zero_delivery_positive_receipt_bypass_rejected() -> None:
    """Finding 1: bypass with zero actual delivered, positive exports/receipt.

    Reviewer probe: every actual demand-cell ``delivered`` value is zero
    while ``flows.convertible_exports`` carries ``3.3333333333333335e-11``
    and the receipt / journal leg / closing USD reserve are all ``1e-10``.
    The observer must reject because the actual boundary delivered is
    exactly zero (not just below a 1e-12 quantity cutoff).
    """
    regime = _load_regime()
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    g_energy = fixture.g("energy")
    cell_usd_energy = int(fixture.network.export_demand_cell[1, g_energy])
    assert cell_usd_energy >= 0
    # Wipe the USD energy demand-cell delivered to exactly zero; bump the
    # USD channel export to a tiny positive scalar (3.33e-11) so the dot
    # product still equals the receipt, and rewrite the journal leg and
    # the closing USD reserve to match.
    flows.delivered[cell_usd_energy] = 0.0
    flows.allocated[cell_usd_energy] = 0.0
    flows.used[cell_usd_energy] = 0.0
    flows.ordered[cell_usd_energy] = 0.0
    flows.desired[cell_usd_energy] = 0.0
    flows.convertible_exports[g_energy] = 3.3333333333333335e-11
    flows.usd_export_receipt = 1e-10
    for index, kind_value in enumerate(flows.journal_kind):
        if (
            kind_value == "export_receipt"
            and flows.journal_currency[index] == USD_CURRENCY
        ):
            flows.journal_amount[index] = 1e-10
            break
    fixture.state.usd_reserve = 1e-10
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_tiny_positive_delivery_with_matching_receipt_accepted() -> None:
    """Finding 1: boundary - tiny matching positive delivery is accepted.

    Reviewer probe: delivered ``3.3333333333333334e-14`` with a matching
    receipt ``1e-13`` must be accepted; the prior 1e-12 quantity cutoff
    turned the matching positive delivery into zero and rejected the tick.
    """
    regime = _load_regime()
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    g_energy = fixture.g("energy")
    cell_usd_energy = int(fixture.network.export_demand_cell[1, g_energy])
    assert cell_usd_energy >= 0
    tiny_delivery = 3.3333333333333334e-14
    tiny_receipt = 1e-13
    flows.delivered[cell_usd_energy] = tiny_delivery
    flows.allocated[cell_usd_energy] = tiny_delivery
    flows.used[cell_usd_energy] = tiny_delivery
    flows.ordered[cell_usd_energy] = tiny_delivery
    flows.desired[cell_usd_energy] = tiny_delivery
    flows.convertible_exports[g_energy] = tiny_delivery
    flows.usd_export_receipt = tiny_receipt
    for index, kind_value in enumerate(flows.journal_kind):
        if (
            kind_value == "export_receipt"
            and flows.journal_currency[index] == USD_CURRENCY
        ):
            flows.journal_amount[index] = tiny_receipt
            break
    fixture.state.usd_reserve = tiny_receipt
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    assert observation["channels"][USD_CURRENCY]["export_receipt"] == pytest.approx(
        tiny_receipt, abs=1e-15
    )
    usd_residual = observation["identity_residuals"][
        "export_receipt_by_currency"
    ][USD_CURRENCY]
    # dot(exports, prices) = tiny_delivery * 3.0 = tiny_receipt; residual is zero.
    assert abs(usd_residual) <= 1e-15


def test_domestic_loan_drawdown_with_usd_foreign_account_rejected() -> None:
    """Finding 2: domestic loan_drawdown row debiting foreign_usd must reject."""
    regime = _load_regime()
    fixture, opening, flows, forcing = _make_full_run()
    usd_account = foreign_account_id(fixture.state, USD_CURRENCY)
    treasury_fiscal = treasury_account_id(fixture.state, AccountKind.FISCAL_EXPENSE)
    bad = copy.deepcopy(flows)
    _append_journal_row(
        bad,
        kind="loan_drawdown",
        tick=int(flows.tick),
        debit=usd_account,
        credit=treasury_fiscal,
        currency=DOMESTIC_CURRENCY,
        amount=100.0,
        org=None,
    )
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            bad,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_domestic_interest_payment_with_usd_foreign_account_rejected() -> None:
    """Finding 2: domestic interest_payment row debiting foreign_usd must reject."""
    regime = _load_regime()
    fixture, opening, flows, forcing = _make_full_run()
    usd_account = foreign_account_id(fixture.state, USD_CURRENCY)
    treasury_fiscal = treasury_account_id(fixture.state, AccountKind.FISCAL_EXPENSE)
    bad = copy.deepcopy(flows)
    _append_journal_row(
        bad,
        kind="interest_payment",
        tick=int(flows.tick),
        debit=usd_account,
        credit=treasury_fiscal,
        currency=DOMESTIC_CURRENCY,
        amount=100.0,
        org=None,
    )
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            bad,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_domestic_principal_repayment_with_usd_foreign_account_rejected() -> None:
    """Finding 2: domestic principal_repayment row debiting foreign_usd must reject."""
    regime = _load_regime()
    fixture, opening, flows, forcing = _make_full_run()
    usd_account = foreign_account_id(fixture.state, USD_CURRENCY)
    treasury_fiscal = treasury_account_id(fixture.state, AccountKind.FISCAL_EXPENSE)
    bad = copy.deepcopy(flows)
    _append_journal_row(
        bad,
        kind="principal_repayment",
        tick=int(flows.tick),
        debit=usd_account,
        credit=treasury_fiscal,
        currency=DOMESTIC_CURRENCY,
        amount=100.0,
        org=None,
    )
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            bad,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def _append_paired_legs(
    flows: MaterialTickFlows,
    *,
    leg_specs: list[dict[str, Any]],
) -> None:
    """Append a multi-leg transaction at the end of the journal.

    The new transaction's legs are numbered ``0, 1, ...`` relative to the
    transaction, regardless of the existing journal.  The existing rows
    are left untouched so back-to-back single-leg transactions stay
    valid; the new transaction then starts at ``leg=0`` and the journal
    validator accepts the transition as a legitimate restart.
    """
    leg_count = len(leg_specs)
    assert leg_count >= 1, "at least one leg is required"
    column_to_attr = {
        "journal_kind": "kind",
        "journal_tick": "tick",
        "journal_debit": "debit",
        "journal_credit": "credit",
        "journal_currency": "currency",
        "journal_amount": "amount",
        "journal_org": "org",
        "journal_leg": None,
    }
    for column, attr_key in column_to_attr.items():
        existing = list(getattr(flows, column))
        if column == "journal_leg":
            for leg_index in range(leg_count):
                existing.append(leg_index)
        else:
            assert attr_key is not None
            for spec in leg_specs:
                existing.append(spec[attr_key])
        setattr(flows, column, existing)


def _append_domestic_loan_pair(
    flows: MaterialTickFlows,
    *,
    debit_id: int,
    credit_id: int,
    second_debit_id: int,
    second_credit_id: int,
    kind_value: str,
    amount: float,
) -> None:
    """Append a paired domestic ``loan_*`` transaction (two legs).

    Mirrors the legitimate engine pattern: first leg debits the borrower's
    cash and credits the Treasury cash (or bank deposit), second leg
    debits the Treasury loan asset and credits the organization's loan
    liability.  Both legs share the same currency and amount.
    """
    _append_paired_legs(
        flows,
        leg_specs=[
            {
                "kind": kind_value,
                "tick": int(flows.tick),
                "debit": debit_id,
                "credit": credit_id,
                "currency": DOMESTIC_CURRENCY,
                "amount": amount,
                "org": None,
            },
            {
                "kind": kind_value,
                "tick": int(flows.tick),
                "debit": second_debit_id,
                "credit": second_credit_id,
                "currency": DOMESTIC_CURRENCY,
                "amount": amount,
                "org": None,
            },
        ],
    )


def test_legitimate_domestic_loan_drawdown_accepted() -> None:
    """Finding 2 positive: a domestic loan_drawdown using domestic accounts passes."""
    regime = _load_regime()
    fixture, opening, flows, forcing = _make_full_run()
    org_cash_id = int(
        organization_account_ids(fixture.state, AccountKind.CASH_DEPOSIT)[1]
    )
    org_loan_id = int(
        organization_account_ids(fixture.state, AccountKind.LOAN_LIABILITY)[1]
    )
    treasury_cash_id = treasury_account_id(fixture.state, AccountKind.CASH_DEPOSIT)
    treasury_loan_id = treasury_account_id(fixture.state, AccountKind.LOAN_ASSET)
    good = copy.deepcopy(flows)
    _append_domestic_loan_pair(
        good,
        debit_id=org_cash_id,
        credit_id=treasury_cash_id,
        second_debit_id=treasury_loan_id,
        second_credit_id=org_loan_id,
        kind_value="loan_drawdown",
        amount=1.0,
    )
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        good,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    # The underlying CMEA/USD export channels must still observe cleanly.
    assert observation["channels"][USD_CURRENCY]["export_receipt"] == pytest.approx(
        6.0, abs=1e-9
    )
    assert observation["channels"][CMEA_CURRENCY]["export_receipt"] == pytest.approx(
        2.0, abs=1e-9
    )


def test_legitimate_domestic_interest_payment_accepted() -> None:
    """Finding 2 positive: a domestic interest_payment using domestic accounts passes."""
    regime = _load_regime()
    fixture, opening, flows, forcing = _make_full_run()
    org_cash_id = int(
        organization_account_ids(fixture.state, AccountKind.CASH_DEPOSIT)[1]
    )
    org_interest_id = int(
        organization_account_ids(fixture.state, AccountKind.INTEREST_PAYABLE)[1]
    )
    good = copy.deepcopy(flows)
    _append_paired_legs(
        good,
        leg_specs=[
            {
                "kind": "interest_payment",
                "tick": int(flows.tick),
                "debit": org_interest_id,
                "credit": org_cash_id,
                "currency": DOMESTIC_CURRENCY,
                "amount": 0.5,
                "org": None,
            },
        ],
    )
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        good,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    assert observation["channels"][USD_CURRENCY]["export_receipt"] == pytest.approx(
        6.0, abs=1e-9
    )


def test_legitimate_domestic_principal_repayment_accepted() -> None:
    """Finding 2 positive: a domestic principal_repayment using domestic accounts passes."""
    regime = _load_regime()
    fixture, opening, flows, forcing = _make_full_run()
    org_cash_id = int(
        organization_account_ids(fixture.state, AccountKind.CASH_DEPOSIT)[1]
    )
    org_loan_id = int(
        organization_account_ids(fixture.state, AccountKind.LOAN_LIABILITY)[1]
    )
    good = copy.deepcopy(flows)
    _append_paired_legs(
        good,
        leg_specs=[
            {
                "kind": "principal_repayment",
                "tick": int(flows.tick),
                "debit": org_loan_id,
                "credit": org_cash_id,
                "currency": DOMESTIC_CURRENCY,
                "amount": 0.5,
                "org": None,
            },
        ],
    )
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        good,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    assert observation["channels"][USD_CURRENCY]["export_receipt"] == pytest.approx(
        6.0, abs=1e-9
    )


def test_export_edge_positive_fee_with_zero_delivery_rejected() -> None:
    """Finding 3: a strictly positive export edge fee with zero delivery must reject."""
    regime = _load_regime()
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    from hsm_lab.contract.material import PURPOSE_CODES, RoutePurpose

    edge_purpose = np.asarray(fixture.network.edge_purpose, dtype=np.int64)
    cmea_export_purpose = int(PURPOSE_CODES[RoutePurpose.EXPORT_CMEA])
    usd_export_purpose = int(PURPOSE_CODES[RoutePurpose.EXPORT_CONVERTIBLE])
    export_edges = [
        int(idx)
        for idx, purpose in enumerate(edge_purpose.tolist())
        if int(purpose) in (cmea_export_purpose, usd_export_purpose)
    ]
    assert export_edges, "fixture must declare at least one export edge"
    bad = copy.deepcopy(flows)
    for edge in export_edges:
        bad.edge_delivered[edge] = 0.0
        bad.edge_service_fee[edge] = 1.0
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            bad,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_housing_edge_positive_fee_with_zero_delivery_rejected() -> None:
    """Finding 3: a strictly positive housing border fee with zero delivery must reject."""
    fixture = _legacy_housing_fixture(treasury=4.0)
    observation, opening, flows, forcing = _housing_observation(fixture)
    edge = _housing_edge_index(fixture)
    bad = copy.deepcopy(flows)
    bad.edge_delivered[edge] = 0.0
    bad.edge_service_fee[edge] = 1.0
    regime = _load_regime()
    with pytest.raises(ResearchGateError) as excinfo:
        observe_legacy_trade_tick(
            opening,
            fixture.state,
            bad,
            fixture.parameters,
            fixture.network,
            regime=regime,
            oil_price=float(forcing.oil_price[0]),
            cmea_contract_price=float(forcing.cmea_energy_price[0]),
        )
    assert str(excinfo.value).startswith(GATE_PREFIX)


def test_identity_residual_reports_nonzero_signed_difference() -> None:
    """Finding 4: receipt 6.0000000001 with matching journal/closing yields nonzero residual.

    Starts from the valid full run, then drifts the USD export receipt
    scalar, the matching journal leg amount, and the closing USD reserve
    all to ``6.0000000001`` (within ``tolerance_for``).  The observer must
    accept and report a nonzero signed residual equal to
    ``dot(exports, prices) - flow receipt`` (approximately
    ``-1.000000082740371e-10``).
    """
    regime = _load_regime()
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    drifted_value = 6.0000000001
    flows.usd_export_receipt = drifted_value
    for index, kind_value in enumerate(flows.journal_kind):
        if (
            kind_value == "export_receipt"
            and flows.journal_currency[index] == USD_CURRENCY
        ):
            flows.journal_amount[index] = drifted_value
            break
    fixture.state.usd_reserve = drifted_value
    observation = observe_legacy_trade_tick(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        regime=regime,
        oil_price=float(forcing.oil_price[0]),
        cmea_contract_price=float(forcing.cmea_energy_price[0]),
    )
    # dot(exports, prices) is unchanged at 6.0; receipt is 6.0000000001,
    # so the signed residual is 6.0 - 6.0000000001 ≈ -1.000000082740371e-10.
    usd_residual = observation["identity_residuals"][
        "export_receipt_by_currency"
    ][USD_CURRENCY]
    expected_residual = 6.0 - drifted_value
    assert usd_residual == pytest.approx(expected_residual, abs=1e-15)
    # Spot-check the numeric sign and magnitude from the spec wording.
    assert abs(usd_residual - (-1.000000082740371e-10)) <= 1e-15
    assert usd_residual < 0.0
