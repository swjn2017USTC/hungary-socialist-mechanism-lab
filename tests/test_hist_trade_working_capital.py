"""H3F-D1: limited-term Treasury trade working-capital loan.

Every test drives the real material kernel and the real invariant gate.  The
fixture is the frozen D0 export fixture (seed 1729, one bank, one energy
seller, CMEA/USD demand 2 each at admin price 1).  Amounts are synthetic
engineering inputs, not historical calibrations.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.engine import accounting, finance
from hsm_lab.engine.finance import (
    CMEA_CURRENCY,
    DOMESTIC_CURRENCY,
    USD_CURRENCY,
    AccountKind,
    bank_account_ids,
    foreign_account_id,
    plot_clearing_account_ids,
    treasury_account_id,
    treasury_term_account_id,
)
from hsm_lab.engine.material import tick_material
from hsm_lab.engine.state import MaterialTickFlows, capture_material_stocks
from hsm_lab.institutions.trade_working_capital_adapter import (
    SCHEMA_ID,
    TradeWorkingCapitalBook,
    TradeWorkingCapitalFailure,
    TradeWorkingCapitalRegime,
    WorkingCapitalBatch,
    execute_trade_working_capital_tick,
    load_trade_working_capital_regime,
)
from tests.test_hist_export_finance import _forcing, _legacy_export_fixture
from tests.test_material import Fixture

REGIME_PATH = (
    Path(__file__).resolve().parents[1]
    / "config/trade_regimes/hist_vnext_v1/limited_trade_working_capital.json"
)


def _regime(
    *,
    limit: float = 4.0,
    bank: int = 0,
    rate: float = 0.04,
    term: int = 1,
    start: int = 0,
    end: int = 0,
) -> TradeWorkingCapitalRegime:
    return TradeWorkingCapitalRegime(
        schema_version="hist-trade-working-capital-regime-v1",
        regime_id="limited_trade_working_capital",
        source_kind="synthetic",
        bank_index=bank,
        credit_limit=limit,
        annual_rate=rate,
        term_quarters=term,
        draw_tick_start=start,
        draw_tick_end=end,
    )


def _run(
    fixture: Fixture,
    regime: TradeWorkingCapitalRegime,
    *,
    book: TradeWorkingCapitalBook | None = None,
    ticks: int = 2,
):
    return execute_trade_working_capital_tick(
        fixture.state,
        _forcing(fixture, ticks=ticks),
        fixture.parameters,
        fixture.network,
        regime=regime,
        book=book,
    )


def _assert_gate(result) -> None:
    assert result.gate.max_finance_abs_residual <= 1e-9
    assert result.gate.max_material_abs_residual <= 1e-9


def _fund_next_tick(state, cash: float) -> None:
    """Inject a declared pre-existing domestic deposit backed by reserves."""
    state.treasury_deposit = float(cash)
    state.bank_deposit_liability[0] += float(cash)
    state.bank_reserves[0] += float(cash)


# ---------------------------------------------------------------------------
# Core housing/loan arithmetic.
# ---------------------------------------------------------------------------


def test_full_draw_pays_real_exports_and_books_a_real_bank_asset() -> None:
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    result = _run(fixture, _regime(limit=4.0))
    _assert_gate(result)
    state = fixture.state
    flows = result.flows

    assert result.observation["schema_version"] == SCHEMA_ID
    assert flows.treasury_loan_drawn == pytest.approx(4.0)
    assert flows.treasury_export_outlay == pytest.approx(4.0)
    assert flows.treasury_principal_paid == 0.0
    assert flows.treasury_interest_due == 0.0  # new draw never accrues same tick
    assert state.treasury_deposit == pytest.approx(0.0)
    assert state.treasury_loan_principal == pytest.approx(4.0)
    assert state.treasury_interest_arrears == 0.0
    assert result.book.principal == pytest.approx(4.0)
    assert [(b.draw_tick, b.maturity_tick) for b in result.book.batches] == [(0, 1)]

    # The bank created a real asset and a matching deposit; reserves unchanged.
    assert state.bank_loan_asset[0] == pytest.approx(4.0)
    assert state.bank_deposit_liability[0] == pytest.approx(4.0)
    assert state.bank_reserves[0] == pytest.approx(20.0)
    assert state.bank_equity[0] == pytest.approx(20.0)
    # The seller was paid and the stock left the real cell.
    assert state.organization_cash[1] == pytest.approx(4.0)
    assert np.sum(flows.cmea_exports) == pytest.approx(2.0)
    assert np.sum(flows.convertible_exports) == pytest.approx(2.0)
    assert flows.cmea_export_receipt == pytest.approx(2.0)
    assert flows.usd_export_receipt == pytest.approx(6.0)
    cell = fixture.cell("organization", 1, 0, "output", "energy")
    assert state.stock_value[cell] == pytest.approx(4.0)
    # Maturity is never silently rolled into a fresh term.
    assert result.book.batches[0].maturity_tick == 1


def test_maturity_accrues_interest_pays_principal_and_clears_the_bank_asset() -> None:
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    first = _run(fixture, _regime(limit=4.0))
    _fund_next_tick(fixture.state, 4.04)
    second = _run(fixture, _regime(limit=4.0), book=first.book)
    _assert_gate(second)

    flows = second.flows
    assert flows.treasury_interest_due == pytest.approx(0.04)
    assert flows.treasury_interest_paid == pytest.approx(0.04)
    assert flows.treasury_principal_paid == pytest.approx(4.0)
    assert flows.treasury_loan_drawn == 0.0  # draw window closed at tick 1
    assert fixture.state.treasury_deposit == pytest.approx(0.0)
    assert fixture.state.treasury_loan_principal == pytest.approx(0.0)
    assert fixture.state.treasury_interest_arrears == pytest.approx(0.0)
    assert second.book.principal == pytest.approx(0.0)
    assert second.book.batches == ()
    assert fixture.state.bank_loan_asset[0] == pytest.approx(0.0)
    assert fixture.state.bank_deposit_liability[0] == pytest.approx(4.0)  # seller cash
    assert fixture.state.bank_equity[0] == pytest.approx(20.04)
    assert fixture.state.bank_interest_receivable[0] == pytest.approx(0.0)


def test_partial_maturity_keeps_principal_with_the_same_bank() -> None:
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    first = _run(fixture, _regime(limit=4.0))
    _fund_next_tick(fixture.state, 2.0)
    second = _run(fixture, _regime(limit=4.0), book=first.book)
    _assert_gate(second)

    assert second.flows.treasury_interest_paid == pytest.approx(0.04)
    assert second.flows.treasury_principal_paid == pytest.approx(1.96)
    assert second.flows.treasury_principal_paid < 4.0
    assert fixture.state.treasury_loan_principal == pytest.approx(2.04)
    assert second.book.principal == pytest.approx(2.04)
    assert second.book.batches[0].maturity_tick == 1  # overdue, not reset
    assert fixture.state.bank_loan_asset[0] == pytest.approx(2.04)


def test_unpaid_interest_and_principal_remain_as_arrears() -> None:
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    first = _run(fixture, _regime(limit=4.0))
    second = _run(fixture, _regime(limit=4.0), book=first.book)  # no cash at tick 1
    _assert_gate(second)

    assert second.flows.treasury_interest_due == pytest.approx(0.04)
    assert second.flows.treasury_interest_paid == 0.0
    assert second.flows.treasury_principal_paid == 0.0
    assert fixture.state.treasury_interest_arrears == pytest.approx(0.04)
    assert fixture.state.treasury_loan_principal == pytest.approx(4.0)
    assert second.book.interest_arrears == pytest.approx(0.04)
    assert second.book.batches[0].maturity_tick == 1


# ---------------------------------------------------------------------------
# Nonbinding / zero / no-gap / limit-bound sizing.
# ---------------------------------------------------------------------------


def test_existing_cash_and_nonbinding_limit_do_not_create_a_loan() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    result = _run(fixture, _regime(limit=8.0))
    _assert_gate(result)
    assert result.flows.treasury_loan_drawn == 0.0
    assert result.book.principal == 0.0
    assert fixture.state.treasury_loan_principal == 0.0
    assert result.flows.treasury_export_outlay == pytest.approx(4.0)
    assert result.observation["draw_sizing"]["outlay_without_loan"] == pytest.approx(4.0)
    assert result.observation["draw_sizing"]["outlay_at_limit"] == pytest.approx(4.0)


def test_zero_limit_and_no_stock_never_draw() -> None:
    zero_limit = _legacy_export_fixture(treasury=0.0, stock=8.0)
    result = _run(zero_limit, _regime(limit=0.0))
    _assert_gate(result)
    assert result.flows.treasury_loan_drawn == 0.0
    assert zero_limit.state.treasury_loan_principal == 0.0

    no_stock = _legacy_export_fixture(treasury=0.0, stock=0.0)
    result = _run(no_stock, _regime(limit=4.0))
    _assert_gate(result)
    assert result.flows.treasury_loan_drawn == 0.0
    assert result.flows.treasury_export_outlay == 0.0
    assert no_stock.state.treasury_loan_principal == 0.0


def test_draw_is_capped_by_the_limit_and_scales_real_delivery() -> None:
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    result = _run(fixture, _regime(limit=2.0))
    _assert_gate(result)
    assert result.flows.treasury_loan_drawn == pytest.approx(2.0)
    assert result.flows.treasury_export_outlay == pytest.approx(2.0)
    assert np.sum(result.flows.cmea_exports) == pytest.approx(1.0)
    assert np.sum(result.flows.convertible_exports) == pytest.approx(1.0)
    assert result.flows.cmea_export_receipt == pytest.approx(1.0)
    assert result.flows.usd_export_receipt == pytest.approx(3.0)
    assert result.observation["limit_remaining"] == pytest.approx(0.0)
    assert result.observation["draw_sizing"]["limit_remaining"] == pytest.approx(2.0)


def test_no_export_demand_means_no_loan() -> None:
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    trade = fixture.parameters.trade.model_copy(
        update={
            "cmea_export_demands": [0.0] * 8,
            "convertible_export_demands": [0.0] * 8,
        }
    )
    fixture.parameters = fixture.parameters.model_copy(update={"trade": trade})
    result = _run(fixture, _regime(limit=4.0))
    _assert_gate(result)
    assert result.flows.treasury_loan_drawn == 0.0
    assert fixture.state.treasury_loan_principal == 0.0


def test_draw_window_is_enforced() -> None:
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    result = _run(fixture, _regime(limit=4.0, start=1, end=1))
    _assert_gate(result)
    assert result.flows.treasury_loan_drawn == 0.0
    assert fixture.state.treasury_loan_principal == 0.0


# ---------------------------------------------------------------------------
# Refusals: regime, book, bank, rollback.
# ---------------------------------------------------------------------------


def test_regime_loader_accepts_the_frozen_file_and_rejects_mutations(tmp_path) -> None:
    regime = load_trade_working_capital_regime(REGIME_PATH)
    assert regime.regime_id == "limited_trade_working_capital"
    assert regime.source_kind == "synthetic"
    assert regime.credit_limit == 4.0
    assert regime.annual_rate == 0.04

    payload = json.loads(REGIME_PATH.read_text(encoding="utf-8"))
    wrong_id = dict(payload, regime_id="legacy_treasury_prepay")
    extra = dict(payload, unexpected=1)
    missing = {k: v for k, v in payload.items() if k != "annual_rate"}
    for index, candidate in enumerate((wrong_id, extra, missing)):
        path = tmp_path / f"regime-{index}.json"
        path.write_text(json.dumps(candidate), encoding="utf-8")
        with pytest.raises(ResearchGateError, match="HIST_H3F_D1"):
            load_trade_working_capital_regime(path)
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(ResearchGateError, match="HIST_H3F_D1"):
        load_trade_working_capital_regime(bad)


def test_invalid_bank_and_book_mismatch_reject_before_mutation() -> None:
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    before = copy.deepcopy(fixture.state)
    with pytest.raises(TradeWorkingCapitalFailure) as caught:
        _run(fixture, _regime(limit=4.0, bank=5))
    assert caught.value.phase == "preflight"
    assert fixture.state.completed_ticks == 0
    for name in before.__dataclass_fields__:
        left = getattr(fixture.state, name)
        right = getattr(before, name)
        if isinstance(left, np.ndarray):
            assert np.array_equal(left, right)
        else:
            assert left == right

    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    _run(fixture, _regime(limit=4.0))
    with pytest.raises(TradeWorkingCapitalFailure, match="disagrees with state"):
        _run(fixture, _regime(limit=4.0), book=TradeWorkingCapitalBook(bank_index=0))


def test_m2_neutral_is_incompatible_and_rolls_back() -> None:
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    fixture.parameters = fixture.parameters.model_copy(update={"m2_neutral_credit": True})
    with pytest.raises(TradeWorkingCapitalFailure, match="m2_neutral_credit"):
        _run(fixture, _regime(limit=4.0))
    assert fixture.state.completed_ticks == 0
    assert fixture.state.treasury_loan_principal == 0.0


def test_strict_numeric_regime_fields_reject_booleans_and_strings(tmp_path) -> None:
    payload = json.loads(REGIME_PATH.read_text(encoding="utf-8"))
    for index, (field, value) in enumerate(
        (
            ("credit_limit", True),
            ("annual_rate", True),
            ("annual_rate", "0.04"),
            ("credit_limit", "4.0"),
        )
    ):
        candidate = dict(payload, **{field: value})
        path = tmp_path / f"coerced-{index}.json"
        path.write_text(json.dumps(candidate), encoding="utf-8")
        with pytest.raises(ResearchGateError, match="HIST_H3F_D1"):
            load_trade_working_capital_regime(path)


def test_over_limit_opening_principal_is_rejected_before_mutation() -> None:
    fixture = _legacy_export_fixture(treasury=8.04, stock=8.0)
    state = fixture.state
    state.completed_ticks = 1
    state.treasury_loan_principal = 8.0
    state.treasury_loan_maturity_tick = 1.0
    state.treasury_loan_rate = 0.04
    state.bank_loan_asset[0] = 8.0
    book = TradeWorkingCapitalBook(
        bank_index=0,
        batches=(
            # draw_tick 0, maturity 1, principal 8 -> over the 4 limit.
            WorkingCapitalBatch(
                draw_tick=0, maturity_tick=1, principal=8.0, annual_rate=0.04
            ),
        ),
    )
    with pytest.raises(TradeWorkingCapitalFailure, match="exceeds the credit_limit"):
        _run(fixture, _regime(limit=4.0, start=0, end=1), book=book, ticks=2)
    assert fixture.state.completed_ticks == 1
    assert fixture.state.treasury_loan_principal == pytest.approx(8.0)


def test_future_dated_batch_is_rejected_before_mutation() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    state = fixture.state
    state.treasury_loan_principal = 4.0
    state.treasury_loan_maturity_tick = 6.0
    state.treasury_loan_rate = 0.04
    book = TradeWorkingCapitalBook(
        bank_index=0,
        batches=(
            WorkingCapitalBatch(
                draw_tick=5, maturity_tick=6, principal=4.0, annual_rate=0.04
            ),
        ),
    )
    with pytest.raises(TradeWorkingCapitalFailure, match="not before the current tick"):
        _run(fixture, _regime(limit=4.0, start=0, end=5), book=book, ticks=2)
    assert fixture.state.completed_ticks == 0
    assert fixture.state.treasury_loan_principal == pytest.approx(4.0)


def test_maturity_tick_cannot_draw_a_replacement_facility() -> None:
    regime = _regime(limit=4.0, start=0, end=1, term=1)
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    first = _run(fixture, regime)
    assert first.flows.treasury_loan_drawn == pytest.approx(4.0)
    _fund_next_tick(fixture.state, 4.04)
    second = _run(fixture, regime, book=first.book)
    _assert_gate(second)
    assert second.observation["draw_sizing"]["rollover_blocked"] == 1.0
    assert second.flows.treasury_loan_drawn == 0.0
    assert second.flows.treasury_principal_paid == pytest.approx(4.0)
    assert fixture.state.treasury_loan_principal == 0.0
    assert fixture.state.treasury_loan_maturity_tick == -1.0


def test_checkpointed_schedule_scalars_reconstruct_the_book() -> None:
    regime = _regime(limit=4.0, start=0, end=0, term=1)
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    _run(fixture, regime)
    assert fixture.state.treasury_loan_maturity_tick == 1.0
    assert fixture.state.treasury_loan_rate == pytest.approx(0.04)
    _fund_next_tick(fixture.state, 4.04)
    restored = _run(fixture, regime, book=None)  # no in-memory book
    _assert_gate(restored)
    assert restored.flows.treasury_interest_due == pytest.approx(0.04)
    assert restored.flows.treasury_principal_paid == pytest.approx(4.0)
    assert fixture.state.treasury_loan_principal == 0.0
    assert fixture.state.treasury_loan_maturity_tick == -1.0
    assert restored.book.batches == ()


def test_term_account_ids_do_not_shift_legacy_ids() -> None:
    fixture = _legacy_export_fixture(treasury=1.0, stock=8.0)
    state = fixture.state
    n_banks = int(state.bank_reserves.shape[0])
    n_orgs = int(state.organization_id.shape[0])
    n_households = int(state.household_id.shape[0])
    n_regions = int(state.dwelling_stock.shape[0])
    from hsm_lab.engine.finance import (
        BANK_ACCOUNT_KINDS,
        HOUSEHOLD_ACCOUNT_KINDS,
        ORGANIZATION_ACCOUNT_KINDS,
        TREASURY_ACCOUNT_KINDS,
    )

    base_foreign = (
        len(HOUSEHOLD_ACCOUNT_KINDS) * n_households
        + len(ORGANIZATION_ACCOUNT_KINDS) * n_orgs
        + len(BANK_ACCOUNT_KINDS) * n_banks
        + len(TREASURY_ACCOUNT_KINDS)
    )
    assert foreign_account_id(state, USD_CURRENCY) == base_foreign
    assert foreign_account_id(state, CMEA_CURRENCY) == base_foreign + 1
    assert int(plot_clearing_account_ids(state)[0]) == base_foreign + 2
    assert treasury_term_account_id(state, AccountKind.LOAN_LIABILITY) == (
        base_foreign + 2 + n_regions
    )
    directory = finance.build_account_directory(state)
    assert ("treasury", 0, DOMESTIC_CURRENCY, AccountKind.LOAN_LIABILITY) in directory


# ---------------------------------------------------------------------------
# Direct orchestration vs adapter.
# ---------------------------------------------------------------------------


def _direct_tick(
    fixture: Fixture,
    *,
    draw: float,
    cash_housing_cap: float,
) -> tuple[MaterialTickFlows, object]:
    """Test-local independent orchestration of exactly one D1 draw tick."""
    state = fixture.state
    opening = capture_material_stocks(state)
    bank = 0
    state.treasury_deposit = float(state.treasury_deposit) + draw
    state.treasury_loan_principal = float(state.treasury_loan_principal) + draw
    state.treasury_loan_maturity_tick = 1.0
    state.treasury_loan_rate = 0.04
    state.bank_loan_asset[bank] += draw
    state.bank_deposit_liability[bank] += draw
    flows = tick_material(
        state,
        _forcing(fixture, ticks=2),
        fixture.parameters,
        fixture.network,
        treasury_housing_payable=cash_housing_cap,
    )
    flows.treasury_loan_drawn = float(draw)
    legs = [
        (
            treasury_account_id(state, AccountKind.CASH_DEPOSIT),
            bank_account_ids(state, AccountKind.DEPOSIT_LIABILITY)[bank],
            DOMESTIC_CURRENCY,
            draw,
        )
    ]
    finance.append_transaction(
        flows, transaction_id=0, kind="treasury_working_capital_draw", legs=legs
    )
    legs = [
        (
            bank_account_ids(state, AccountKind.LOAN_ASSET)[bank],
            treasury_term_account_id(state, AccountKind.LOAN_LIABILITY),
            DOMESTIC_CURRENCY,
            draw,
        )
    ]
    finance.append_transaction(
        flows, transaction_id=0, kind="treasury_working_capital_draw", legs=legs
    )
    state.completed_ticks = int(state.completed_ticks) + 1
    gate = accounting.check_material_invariants(
        opening, state, flows, fixture.parameters, fixture.network
    )
    return flows, gate


def _direct_service_tick(fixture: Fixture) -> tuple[MaterialTickFlows, object]:
    """Test-local maturity tick: accrual, interest, principal, journal, gate."""
    state = fixture.state
    opening = capture_material_stocks(state)
    bank = 0
    interest_due = 0.04
    interest_paid = min(float(state.treasury_deposit), interest_due)
    state.treasury_deposit -= interest_paid
    state.bank_interest_receivable[bank] += interest_due - interest_paid
    state.bank_equity[bank] += interest_due
    state.bank_deposit_liability[bank] -= interest_paid
    state.treasury_interest_arrears = interest_due - interest_paid
    principal_paid = min(float(state.treasury_deposit), 4.0)
    state.treasury_deposit -= principal_paid
    state.bank_deposit_liability[bank] -= principal_paid
    state.bank_loan_asset[bank] -= principal_paid
    state.treasury_loan_principal -= principal_paid
    if float(state.treasury_loan_principal) > 1e-9:
        state.treasury_loan_maturity_tick = 1.0
        state.treasury_loan_rate = 0.04
    else:
        state.treasury_loan_maturity_tick = -1.0
        state.treasury_loan_rate = 0.0
    flows = tick_material(
        state,
        _forcing(fixture, ticks=2),
        fixture.parameters,
        fixture.network,
        treasury_housing_payable=float(state.treasury_deposit),
    )
    flows.treasury_interest_due = interest_due
    flows.treasury_interest_paid = interest_paid
    flows.treasury_principal_paid = principal_paid
    bank_interest = bank_account_ids(state, AccountKind.INTEREST_RECEIVABLE)[bank]
    bank_equity = bank_account_ids(state, AccountKind.EQUITY)[bank]
    bank_deposit = bank_account_ids(state, AccountKind.DEPOSIT_LIABILITY)[bank]
    bank_loan = bank_account_ids(state, AccountKind.LOAN_ASSET)[bank]
    finance.append_transaction(
        flows,
        transaction_id=0,
        kind="treasury_working_capital_interest_accrual",
        legs=[
            (
                bank_interest,
                bank_equity,
                DOMESTIC_CURRENCY,
                interest_due,
            )
        ],
    )
    finance.append_transaction(
        flows,
        transaction_id=0,
        kind="treasury_working_capital_interest_accrual",
        legs=[
            (
                treasury_term_account_id(state, AccountKind.INTEREST_EXPENSE),
                treasury_term_account_id(state, AccountKind.INTEREST_PAYABLE),
                DOMESTIC_CURRENCY,
                interest_due,
            )
        ],
    )
    if interest_paid > 0.0:
        finance.append_transaction(
            flows,
            transaction_id=0,
            kind="treasury_working_capital_interest_payment",
            legs=[
                (
                    treasury_term_account_id(state, AccountKind.INTEREST_PAYABLE),
                    treasury_account_id(state, AccountKind.CASH_DEPOSIT),
                    DOMESTIC_CURRENCY,
                    interest_paid,
                )
            ],
        )
        finance.append_transaction(
            flows,
            transaction_id=0,
            kind="treasury_working_capital_interest_payment",
            legs=[
                (bank_deposit, bank_interest, DOMESTIC_CURRENCY, interest_paid)
            ],
        )
    if principal_paid > 0.0:
        finance.append_transaction(
            flows,
            transaction_id=0,
            kind="treasury_working_capital_principal",
            legs=[
                (
                    treasury_term_account_id(state, AccountKind.LOAN_LIABILITY),
                    treasury_account_id(state, AccountKind.CASH_DEPOSIT),
                    DOMESTIC_CURRENCY,
                    principal_paid,
                )
            ],
        )
        finance.append_transaction(
            flows,
            transaction_id=0,
            kind="treasury_working_capital_principal",
            legs=[(bank_deposit, bank_loan, DOMESTIC_CURRENCY, principal_paid)],
        )
    state.completed_ticks = int(state.completed_ticks) + 1
    gate = accounting.check_material_invariants(
        opening, state, flows, fixture.parameters, fixture.network
    )
    return flows, gate


def test_direct_orchestration_matches_adapter_field_for_field() -> None:
    regime = _regime(limit=4.0)
    adapter_fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    draw_result = _run(adapter_fixture, regime)
    _assert_gate(draw_result)
    _fund_next_tick(adapter_fixture.state, 4.04)
    service_result = _run(adapter_fixture, regime, book=draw_result.book)
    _assert_gate(service_result)
    assert service_result.observation["legacy_trade_observation"]["schema_version"] == (
        "hist-legacy-trade-observation-v1"
    )

    direct_fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    _direct_tick(
        direct_fixture,
        draw=float(draw_result.observation["draw"]),
        cash_housing_cap=0.0,
    )
    _fund_next_tick(direct_fixture.state, 4.04)
    direct_flows, direct_gate = _direct_service_tick(direct_fixture)

    assert set(direct_gate.per_ledger) == set(service_result.gate.per_ledger)
    for ledger, (residual, ratio) in service_result.gate.per_ledger.items():
        direct_residual, direct_ratio = direct_gate.per_ledger[ledger]
        assert direct_residual == pytest.approx(residual)
        assert direct_ratio == pytest.approx(ratio)
    for name in adapter_fixture.state.__dataclass_fields__:
        left = getattr(adapter_fixture.state, name)
        right = getattr(direct_fixture.state, name)
        if isinstance(left, np.ndarray):
            assert np.array_equal(left, right)
        else:
            assert left == right
    for name in direct_flows.__dataclass_fields__:
        left = getattr(service_result.flows, name)
        right = getattr(direct_flows, name)
        if isinstance(left, np.ndarray):
            assert np.array_equal(left, right)
        else:
            assert left == right
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
        assert getattr(service_result.flows, column) == getattr(direct_flows, column)


def test_admission_gate_rejects_a_fabricated_treasury_loan_flow() -> None:
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        _forcing(fixture, ticks=2),
        fixture.parameters,
        fixture.network,
    )
    flows.treasury_loan_drawn = 1.0  # no journal entry, no state change
    with pytest.raises(accounting.AccountingError, match="treasury_deposit_continuity"):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
        )

    # A real draw tick with its bank-side journal removed must also fail: the
    # bank-loan continuity and D1 journal-vs-flow ledgers reconstruct the bank
    # row from the journal, never from a scalar hint.
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    result = _run(fixture, _regime(limit=4.0))
    flows = result.flows
    keep = [
        index
        for index, kind in enumerate(flows.journal_kind)
        if kind != "treasury_working_capital_draw"
    ]
    for column in (
        "journal_kind",
        "journal_tick",
        "journal_debit",
        "journal_credit",
        "journal_currency",
        "journal_amount",
        "journal_org",
    ):
        setattr(flows, column, [getattr(flows, column)[index] for index in keep])
    flows.journal_leg = [int(flows.journal_leg[index]) for index in keep]
    opening = capture_material_stocks(fixture.state)
    with pytest.raises(accounting.AccountingError):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
        )
