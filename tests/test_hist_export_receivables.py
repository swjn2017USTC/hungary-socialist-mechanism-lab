"""H3F-D2: export receivables, terms and bad-debt reversal entries.

Every test drives the real material kernel and the real invariant gate.  The
fixture is the frozen D0 export fixture (seed 1729, one Treasury with 4 units of
domestic cash, CMEA/USD energy deliveries of 2 each at prices 1/3).  All amounts
are synthetic engineering inputs, not historical calibrations.
"""

from __future__ import annotations

import copy
import json
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import hsm_lab.institutions.export_receivables_adapter as era
from hsm_lab.contract.base import ResearchGateError
from hsm_lab.engine import accounting
from hsm_lab.engine.finance import (
    CMEA_CURRENCY,
    USD_CURRENCY,
    AccountKind,
    treasury_receivable_account_id,
    treasury_term_account_id,
)
from hsm_lab.engine.material import advance_chain, tick_material
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import MaterialHistory, capture_material_stocks
from hsm_lab.institutions.export_receivables_adapter import (
    SCHEMA_ID,
    ExportReceivableEventSpec,
    ExportReceivableFailure,
    ExportReceivablesRegime,
    _build_policy,
    execute_export_receivables_tick,
    load_export_receivables_regime,
)
from hsm_lab.storage.checkpoint import (
    checkpoint_dir,
    load_material_checkpoint,
    save_material_checkpoint,
)
from hsm_lab.storage.material_output import append_material_rows
from tests.test_checkpoint import _rehash
from tests.test_hist_export_finance import _forcing, _legacy_export_fixture
from tests.test_material import Fixture

REGIME_PATH = (
    Path(__file__).resolve().parents[1]
    / "config/trade_regimes/hist_vnext_v1/export_receivables.json"
)
USD_LOT = "d2-usd-energy@0:energy"
CMEA_LOT = "d2-cmea-energy@0:energy"


def _regime(term: int = 1) -> ExportReceivablesRegime:
    return ExportReceivablesRegime(
        schema_version="hist-export-receivables-regime-v1",
        regime_id="export_receivables",
        source_kind="synthetic",
        term_quarters=term,
        contracts=(
            {
                "contract_id": "d2-cmea-energy",
                "currency": CMEA_CURRENCY,
                "buyer_id": 9102,
                "seller_id": 0,
                "commodity_id": "energy",
            },
            {
                "contract_id": "d2-usd-energy",
                "currency": USD_CURRENCY,
                "buyer_id": 9101,
                "seller_id": 0,
                "commodity_id": "energy",
            },
        ),
    )


def _event(
    event_id: str,
    tick: int,
    kind: str,
    lot: str,
    amount: float,
    *,
    contract: str | None = None,
    currency: str | None = None,
    buyer: int | None = None,
) -> ExportReceivableEventSpec:
    is_usd = lot == USD_LOT
    return ExportReceivableEventSpec(
        event_id=event_id,
        tick=tick,
        kind=kind,
        receivable_id=lot,
        contract_id=contract or ("d2-usd-energy" if is_usd else "d2-cmea-energy"),
        currency=currency or (USD_CURRENCY if is_usd else CMEA_CURRENCY),
        buyer_id=buyer if buyer is not None else (9101 if is_usd else 9102),
        seller_id=0,
        amount=amount,
    )


def _run(
    fixture: Fixture,
    regime: ExportReceivablesRegime,
    *,
    events: tuple[ExportReceivableEventSpec, ...] = (),
    ticks: int = 5,
):
    return execute_export_receivables_tick(
        fixture.state,
        _forcing(fixture, ticks=ticks),
        fixture.parameters,
        fixture.network,
        regime=regime,
        events=events,
    )


def _assert_gate(result) -> None:
    assert result.gate.max_finance_abs_residual <= 1e-9
    assert result.gate.max_material_abs_residual <= 1e-9


def _lots(fixture: Fixture) -> dict[str, object]:
    return {lot.receivable_id: lot for lot in fixture.state.export_receivables}


# ---------------------------------------------------------------------------
# Core arithmetic: delivery -> due -> overdue -> loss -> write-off -> recovery.
# ---------------------------------------------------------------------------


def test_delivery_opens_same_currency_receivables_without_cash() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    result = _run(fixture, _regime())
    _assert_gate(result)

    lots = _lots(fixture)
    assert lots[USD_LOT].principal == pytest.approx(6.0)
    assert lots[USD_LOT].gross == pytest.approx(6.0)
    assert lots[USD_LOT].due_tick == 1
    assert lots[CMEA_LOT].principal == pytest.approx(2.0)
    assert lots[CMEA_LOT].due_tick == 1
    assert result.flows.export_receivable_opened_usd == pytest.approx(6.0)
    assert result.flows.export_receivable_opened_cmea == pytest.approx(2.0)
    assert result.flows.export_receivable_received_usd == 0.0
    assert result.flows.export_receivable_received_cmea == 0.0
    assert result.flows.export_receivable_balance_usd == pytest.approx(6.0)
    assert result.flows.export_receivable_balance_cmea == pytest.approx(2.0)
    # The Treasury paid 4 for procurement; no export cash arrived.
    assert fixture.state.treasury_deposit == pytest.approx(0.0)
    assert fixture.state.usd_reserve == 0.0
    assert fixture.state.cmea_settlement_balance == 0.0
    assert result.observation["overdue"] == []
    # Delivery journal debits the receivable, not cash.
    delivery = [
        (kind, amount, currency)
        for kind, amount, currency in zip(
            result.flows.journal_kind,
            result.flows.journal_amount,
            result.flows.journal_currency,
            strict=False,
        )
        if kind == "export_receivable_delivery"
    ]
    assert sorted(delivery) == [
        ("export_receivable_delivery", 2.0, CMEA_CURRENCY),
        ("export_receivable_delivery", 6.0, USD_CURRENCY),
    ]


def test_full_due_receipt_moves_both_currencies_to_cash() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run(fixture, _regime())
    result = _run(
        fixture,
        _regime(),
        events=(
            _event("usd-full", 1, "receipt", USD_LOT, 6.0),
            _event("cmea-full", 1, "receipt", CMEA_LOT, 2.0),
        ),
    )
    _assert_gate(result)

    assert fixture.state.usd_reserve == pytest.approx(6.0)
    assert fixture.state.cmea_settlement_balance == pytest.approx(2.0)
    assert all(lot.gross == 0.0 for lot in fixture.state.export_receivables)
    assert result.flows.export_receivable_received_usd == pytest.approx(6.0)
    assert result.flows.export_receivable_received_cmea == pytest.approx(2.0)
    assert result.observation["overdue"] == []


def test_zero_receipt_stays_due_then_overdue_without_auto_loss() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run(fixture, _regime())
    first = _run(fixture, _regime())
    _assert_gate(first)
    assert first.observation["due"] and not first.observation["overdue"]
    assert all(lot.provision == 0.0 for lot in fixture.state.export_receivables)

    second = _run(fixture, _regime())
    _assert_gate(second)
    overdue = {entry["receivable_id"]: entry for entry in second.observation["overdue"]}
    assert overdue[USD_LOT]["age"] == 1
    assert overdue[CMEA_LOT]["age"] == 1
    assert second.flows.export_receivable_overdue_usd == pytest.approx(6.0)
    assert second.flows.export_receivable_overdue_cmea == pytest.approx(2.0)
    assert second.flows.export_receivable_loss_provision_usd == 0.0
    assert second.flows.export_receivable_loss_provision_cmea == 0.0


def test_partial_receipt_loss_writeoff_and_recovery_chain() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run(fixture, _regime())
    partial = _run(
        fixture,
        _regime(),
        events=(
            _event("usd-part", 1, "receipt", USD_LOT, 4.0),
            _event("cmea-part", 1, "receipt", CMEA_LOT, 1.0),
        ),
    )
    _assert_gate(partial)
    assert _lots(fixture)[USD_LOT].gross == pytest.approx(2.0)
    assert _lots(fixture)[CMEA_LOT].gross == pytest.approx(1.0)
    assert fixture.state.usd_reserve == pytest.approx(4.0)
    assert fixture.state.cmea_settlement_balance == pytest.approx(1.0)

    loss = _run(
        fixture,
        _regime(),
        events=(
            _event("usd-loss", 2, "loss", USD_LOT, 2.0),
            _event("cmea-loss", 2, "loss", CMEA_LOT, 1.0),
        ),
    )
    _assert_gate(loss)
    assert _lots(fixture)[USD_LOT].provision == pytest.approx(2.0)
    assert _lots(fixture)[CMEA_LOT].provision == pytest.approx(1.0)
    assert fixture.state.usd_reserve == pytest.approx(4.0)  # no loss cash

    writeoff = _run(
        fixture,
        _regime(),
        events=(
            _event("usd-wo", 3, "writeoff", USD_LOT, 2.0),
            _event("cmea-wo", 3, "writeoff", CMEA_LOT, 1.0),
        ),
    )
    _assert_gate(writeoff)
    assert _lots(fixture)[USD_LOT].gross == 0.0
    assert _lots(fixture)[USD_LOT].written_off == pytest.approx(2.0)
    assert _lots(fixture)[CMEA_LOT].written_off == pytest.approx(1.0)
    assert fixture.state.usd_reserve == pytest.approx(4.0)  # write-off is not cash

    recovery = _run(
        fixture,
        _regime(),
        events=(_event("usd-recovery", 4, "recovery", USD_LOT, 1.0),),
    )
    _assert_gate(recovery)
    usd = _lots(fixture)[USD_LOT]
    cmea = _lots(fixture)[CMEA_LOT]
    assert usd.written_off == pytest.approx(1.0)
    assert usd.received == pytest.approx(5.0)
    assert usd.recovered == pytest.approx(1.0)
    assert cmea.written_off == pytest.approx(1.0)
    assert fixture.state.usd_reserve == pytest.approx(5.0)
    assert fixture.state.cmea_settlement_balance == pytest.approx(1.0)
    assert recovery.observation["identity_residuals"] == {
        "principal_closure": 0.0,
        "provision_closure": 0.0,
        "cash_closure": 0.0,
    }
    # Original principal closes as A + R + B per lot.
    assert usd.gross + usd.received + usd.written_off == pytest.approx(usd.principal)
    assert cmea.gross + cmea.received + cmea.written_off == pytest.approx(cmea.principal)


def test_term_two_early_payment_is_not_overdue() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run(fixture, _regime(term=2))
    assert _lots(fixture)[USD_LOT].due_tick == 2
    early = _run(
        fixture,
        _regime(term=2),
        events=(_event("usd-early", 1, "receipt", USD_LOT, 1.0),),
    )
    _assert_gate(early)
    assert early.observation["overdue"] == []
    assert _lots(fixture)[USD_LOT].due_tick == 2
    final = _run(
        fixture,
        _regime(term=2),
        events=(
            _event("usd-rest", 2, "receipt", USD_LOT, 5.0),
            _event("cmea-rest", 2, "receipt", CMEA_LOT, 2.0),
        ),
    )
    _assert_gate(final)
    assert all(lot.gross == 0.0 for lot in fixture.state.export_receivables)
    assert fixture.state.usd_reserve == pytest.approx(6.0)
    assert fixture.state.cmea_settlement_balance == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Default-off and refusal behavior.
# ---------------------------------------------------------------------------


def test_legacy_path_without_policy_remains_cash_settlement() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        _forcing(fixture, ticks=1),
        fixture.parameters,
        fixture.network,
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    assert fixture.state.export_receivables == ()
    assert fixture.state.usd_reserve == pytest.approx(6.0)
    assert fixture.state.cmea_settlement_balance == pytest.approx(2.0)


def test_open_receivables_cannot_fall_back_to_legacy_cash() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run(fixture, _regime())
    before = copy.deepcopy(fixture.state)
    with pytest.raises(ValueError, match="open export receivables"):
        tick_material(
            fixture.state,
            _forcing(fixture, ticks=5),
            fixture.parameters,
            fixture.network,
        )
    assert fixture.state.completed_ticks == before.completed_ticks
    assert fixture.state.export_receivables == before.export_receivables


def test_duplicate_and_over_receipt_are_rejected_before_mutation() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run(fixture, _regime())
    before = copy.deepcopy(fixture.state)
    with pytest.raises(ExportReceivableFailure) as caught:
        _run(
            fixture,
            _regime(),
            events=(
                _event("dup", 1, "receipt", USD_LOT, 1.0),
                _event("dup", 1, "receipt", USD_LOT, 1.0),
            ),
        )
    assert caught.value.phase == "preflight"
    assert fixture.state.completed_ticks == 1
    assert fixture.state.export_receivables == before.export_receivables

    _run(fixture, _regime(), events=(_event("ok", 1, "receipt", USD_LOT, 1.0),))
    before = copy.deepcopy(fixture.state)
    with pytest.raises(ExportReceivableFailure, match="exceeds gross"):
        _run(fixture, _regime(), events=(_event("over", 2, "receipt", USD_LOT, 6.0),))
    assert fixture.state.completed_ticks == 2
    assert fixture.state.export_receivables == before.export_receivables


def test_identity_and_cross_currency_events_are_rejected() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run(fixture, _regime())
    for event in (
        _event("wrong-buyer", 1, "receipt", USD_LOT, 1.0, buyer=9999),
        _event("wrong-currency", 1, "receipt", USD_LOT, 1.0, currency=CMEA_CURRENCY),
        _event("wrong-contract", 1, "receipt", USD_LOT, 1.0, contract="other-contract"),
    ):
        with pytest.raises(ExportReceivableFailure, match="identity mismatch"):
            _run(fixture, _regime(), events=(event,))
    assert fixture.state.completed_ticks == 1


def test_loss_before_due_writeoff_without_provision_and_excess_recovery_reject() -> None:
    early = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run(early, _regime(term=2))
    with pytest.raises(ExportReceivableFailure, match="loss before due"):
        _run(early, _regime(term=2), events=(_event("early-loss", 1, "loss", USD_LOT, 1.0),))

    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run(fixture, _regime())
    with pytest.raises(ExportReceivableFailure, match="write-off exceeds"):
        _run(fixture, _regime(), events=(_event("no-provision", 1, "writeoff", USD_LOT, 1.0),))
    _run(fixture, _regime(), events=(_event("loss-ok", 1, "loss", USD_LOT, 2.0),))
    _run(fixture, _regime(), events=(_event("wo-ok", 2, "writeoff", USD_LOT, 2.0),))
    with pytest.raises(ExportReceivableFailure, match="recovery exceeds"):
        _run(fixture, _regime(), events=(_event("too-much", 3, "recovery", USD_LOT, 3.0),))
    assert fixture.state.completed_ticks == 3


def test_regime_loader_accepts_frozen_file_and_rejects_mutations(tmp_path) -> None:
    regime = load_export_receivables_regime(REGIME_PATH)
    assert regime.regime_id == "export_receivables"
    assert regime.term_quarters == 1
    assert {contract.currency for contract in regime.contracts} == {
        USD_CURRENCY,
        CMEA_CURRENCY,
    }
    payload = json.loads(REGIME_PATH.read_text(encoding="utf-8"))
    wrong_id = dict(payload, regime_id="legacy_treasury_prepay")
    extra = dict(payload, unexpected=1)
    missing = {k: v for k, v in payload.items() if k != "term_quarters"}
    bool_term = dict(payload, term_quarters=True)
    string_term = dict(payload, term_quarters="1")
    duplicate = dict(payload, contracts=payload["contracts"] + payload["contracts"][:1])
    for index, candidate in enumerate(
        (wrong_id, extra, missing, bool_term, string_term, duplicate)
    ):
        path = tmp_path / f"regime-{index}.json"
        path.write_text(json.dumps(candidate), encoding="utf-8")
        with pytest.raises(ResearchGateError, match="HIST_H3F_D2"):
            load_export_receivables_regime(path)
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(ResearchGateError, match="HIST_H3F_D2"):
        load_export_receivables_regime(bad)


def test_account_ids_do_not_shift_legacy_or_d1_ids() -> None:
    fixture = _legacy_export_fixture(treasury=1.0, stock=8.0)
    state = fixture.state
    base_term = treasury_term_account_id(state, AccountKind.LOAN_LIABILITY)
    base_receivable = base_term + 3  # D1 term block has three accounts
    assert (
        treasury_receivable_account_id(state, USD_CURRENCY, AccountKind.EXPORT_RECEIVABLE)
        == base_receivable
    )
    assert (
        treasury_receivable_account_id(state, CMEA_CURRENCY, AccountKind.EXPORT_RECEIVABLE)
        == base_receivable + 4
    )  # first currency block has four accounts


# ---------------------------------------------------------------------------
# Checkpoint persistence.
# ---------------------------------------------------------------------------


def test_checkpoint_roundtrip_restores_open_book_and_event_log(tmp_path, contract) -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    # The D0 fixture zeroes the CMEA credit envelope outside pydantic
    # validation; the checkpoint reloader validates the scenario strictly, so
    # restore a legal positive envelope (it does not affect tick 0: no imports).
    fixture.parameters = fixture.parameters.model_copy(
        update={
            "trade": fixture.parameters.trade.model_copy(
                update={"cmea_credit_envelope": 1.0}
            )
        }
    )
    fixture.spec = fixture.spec.model_copy(update={"material_parameters": fixture.parameters})
    opening = capture_material_stocks(fixture.state)
    forcing = _forcing(fixture, ticks=5)
    policy = _build_policy(fixture.state, _regime(), ())
    result = _run(fixture, _regime())
    _assert_gate(result)
    history = MaterialHistory()
    flows = result.flows
    summary = accounting.check_material_invariants(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        forcing=forcing,
        export_receivable_policy=policy,
    )
    invariant_summary = {
        "max_material_abs_residual": float(summary.max_material_abs_residual),
        "max_material_tolerance_ratio": float(summary.max_material_tolerance_ratio),
        "max_finance_abs_residual": float(summary.max_finance_abs_residual),
        "max_finance_tolerance_ratio": float(summary.max_finance_tolerance_ratio),
        "checked_cells": int(summary.checked_cells),
        "per_ledger": dict(summary.per_ledger),
        "expired_leftover_by_cell": summary.expired_leftover_by_cell,
        "forcing_segment": "synthetic_warmup",
        "treasury_deposit_open": float(opening.treasury_deposit),
        "bank_reserves_open": [float(v) for v in opening.bank_reserves],
        "housing_completed": float(
            np.sum(np.asarray(fixture.state.dwelling_stock) - opening.dwelling_stock)
        ),
    }
    history.digest_chain = advance_chain("0" * 64, fixture.state, flows)
    append_material_rows(
        history,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        region_ids=list(fixture.region_ids),
        commodity_ids=list(fixture.commodities),
        digest=history.digest_chain,
        invariant_summary=invariant_summary,
    )
    metadata = {
        "scenario": fixture.spec.model_dump(mode="json"),
        "region_ids": list(fixture.region_ids),
        "commodity_ids": list(fixture.commodities),
        "baseline_hash": contract.expected_baseline_sha256,
        "last_completed_quarter": str(
            fixture.spec.start.advance(fixture.state.completed_ticks - 1)
        ),
        "next_quarter": str(fixture.spec.start.advance(fixture.state.completed_ticks)),
        "source_run_id": "unit-d2",
    }
    path = save_material_checkpoint(
        checkpoint_dir(tmp_path, fixture.state.completed_ticks),
        fixture.state,
        fixture.network,
        history,
        RngRegistry(fixture.spec.seed),
        metadata,
    )
    loaded, _history, _rng, _metadata = load_material_checkpoint(
        path, fixture.spec, contract, fixture.network
    )
    assert loaded.export_receivables == fixture.state.export_receivables
    assert loaded.export_receivable_event_ids == fixture.state.export_receivable_event_ids

    # A resumed receipt must use the persisted book and must not double count.
    resumed = execute_export_receivables_tick(
        loaded,
        _forcing(fixture, ticks=5),
        fixture.parameters,
        fixture.network,
        regime=_regime(),
        events=(
            _event("usd-resumed", 1, "receipt", USD_LOT, 6.0),
            _event("cmea-resumed", 1, "receipt", CMEA_LOT, 2.0),
        ),
    )
    _assert_gate(resumed)
    assert loaded.usd_reserve == pytest.approx(6.0)
    assert loaded.cmea_settlement_balance == pytest.approx(2.0)
    with pytest.raises(ExportReceivableFailure, match="duplicate event id"):
        execute_export_receivables_tick(
            loaded,
            _forcing(fixture, ticks=5),
            fixture.parameters,
            fixture.network,
            regime=_regime(),
            events=(_event("usd-resumed", 2, "receipt", USD_LOT, 1.0),),
        )


# ---------------------------------------------------------------------------
# Direct orchestration and gate tamper.
# ---------------------------------------------------------------------------


def test_direct_orchestration_matches_adapter_field_for_field() -> None:
    regime = _regime()
    event_plan = {
        0: (),
        1: (
            _event("usd-part", 1, "receipt", USD_LOT, 4.0),
            _event("cmea-part", 1, "receipt", CMEA_LOT, 1.0),
        ),
        2: (
            _event("usd-loss", 2, "loss", USD_LOT, 2.0),
            _event("cmea-loss", 2, "loss", CMEA_LOT, 1.0),
        ),
        3: (
            _event("usd-wo", 3, "writeoff", USD_LOT, 2.0),
            _event("cmea-wo", 3, "writeoff", CMEA_LOT, 1.0),
        ),
        4: (_event("usd-recovery", 4, "recovery", USD_LOT, 1.0),),
    }
    adapter_fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    adapter_results = []
    adapter_states = []
    for tick in range(5):
        adapter_results.append(
            _run(adapter_fixture, regime, events=event_plan[tick])
        )
        adapter_states.append(copy.deepcopy(adapter_fixture.state))

    direct_fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    direct_forcing = _forcing(direct_fixture, ticks=5)
    direct_flows = []
    direct_gates = []
    direct_states = []
    for tick in range(5):
        specs = event_plan[tick]
        policy = _build_policy(direct_fixture.state, regime, specs)
        opening = capture_material_stocks(direct_fixture.state)
        flows = tick_material(
            direct_fixture.state,
            direct_forcing,
            direct_fixture.parameters,
            direct_fixture.network,
            export_receivable_policy=policy,
        )
        direct_fixture.state.completed_ticks = tick + 1
        gate = accounting.check_material_invariants(
            opening,
            direct_fixture.state,
            flows,
            direct_fixture.parameters,
            direct_fixture.network,
            forcing=direct_forcing,
            export_receivable_policy=policy,
        )
        direct_flows.append(flows)
        direct_gates.append(gate)
        direct_states.append(copy.deepcopy(direct_fixture.state))

    for index, (adapter_result, direct_flow, direct_gate) in enumerate(
        zip(adapter_results, direct_flows, direct_gates, strict=True)
    ):
        assert set(direct_gate.per_ledger) == set(adapter_result.gate.per_ledger)
        for ledger, (residual, ratio) in adapter_result.gate.per_ledger.items():
            direct_residual, direct_ratio = direct_gate.per_ledger[ledger]
            assert direct_residual == pytest.approx(residual)
            assert direct_ratio == pytest.approx(ratio)
        _assert_state_equal(adapter_states[index], direct_states[index])
        for name in direct_flow.__dataclass_fields__:
            left = getattr(adapter_result.flows, name)
            right = getattr(direct_flow, name)
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
            "journal_event",
        ):
            assert getattr(adapter_result.flows, column) == getattr(direct_flow, column)


def test_gate_rejects_a_tampered_receivable_balance() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    opening = capture_material_stocks(fixture.state)
    forcing = _forcing(fixture, ticks=5)
    policy = _build_policy(fixture.state, _regime(), ())
    flows = tick_material(
        fixture.state,
        forcing,
        fixture.parameters,
        fixture.network,
        export_receivable_policy=policy,
    )
    fixture.state.export_receivables = tuple(
        lot.__class__(**{**lot.__dict__, "gross": lot.gross + 1.0})
        for lot in fixture.state.export_receivables
    )
    with pytest.raises(accounting.AccountingError, match="receivable"):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            forcing=forcing,
            export_receivable_policy=policy,
        )


def test_observation_schema_is_independent_and_read_only() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    result = _run(fixture, _regime())
    assert result.observation["schema_version"] == SCHEMA_ID
    assert result.observation["source_kind"] == "synthetic"
    assert result.observation["historical"] == "UNIDENTIFIED"
    assert result.observation["cash"]["usd_receipt"] == 0.0
    assert result.observation["receivable_open"] == []
    assert len(result.observation["receivable_close"]) == 2


# ---------------------------------------------------------------------------
# Review-fix: identity, journal, valuation and direct-input tamper.
# ---------------------------------------------------------------------------


def _direct_delivery(fixture: Fixture):
    forcing = _forcing(fixture, ticks=5)
    policy = _build_policy(fixture.state, _regime(), ())
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        forcing,
        fixture.parameters,
        fixture.network,
        export_receivable_policy=policy,
    )
    return opening, policy, flows, forcing


def _assert_state_equal(left, right) -> None:
    for name in left.__dataclass_fields__:
        a = getattr(left, name)
        b = getattr(right, name)
        if isinstance(a, np.ndarray):
            assert np.array_equal(a, b), name
        else:
            assert a == b, name


def test_gate_rejects_duplicate_and_mutated_closing_identities() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    opening, policy, flows, forcing = _direct_delivery(fixture)
    # The untampered tick passes.
    accounting.check_material_invariants(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        forcing=forcing,
        export_receivable_policy=policy,
    )

    fixture.state.export_receivables = fixture.state.export_receivables + (
        fixture.state.export_receivables[0],
    )
    with pytest.raises(accounting.AccountingError, match="duplicate receivable"):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            forcing=forcing,
            export_receivable_policy=policy,
        )

    for field, value, match in (
        ("buyer_id", 9999, "identity field"),
        ("currency", CMEA_CURRENCY, "identity field"),
        ("commodity_id", "not-a-good", "unknown commodity|identity field"),
        ("due_tick", 99, "identity field"),
    ):
        fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
        opening, policy, flows, forcing = _direct_delivery(fixture)
        fixture.state.export_receivables = tuple(
            replace(lot, **{field: value})
            if lot.receivable_id == USD_LOT
            else lot
            for lot in fixture.state.export_receivables
        )
        with pytest.raises(accounting.AccountingError, match=match):
            accounting.check_material_invariants(
                opening,
                fixture.state,
                flows,
                fixture.parameters,
                fixture.network,
                forcing=forcing,
                export_receivable_policy=policy,
            )

    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    opening, policy, flows, forcing = _direct_delivery(fixture)
    fixture.state.export_receivables = tuple(
        replace(lot, delivery_tick=-3, due_tick=99) if lot.receivable_id == USD_LOT else lot
        for lot in fixture.state.export_receivables
    )
    with pytest.raises(accounting.AccountingError, match="receivable"):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            forcing=forcing,
            export_receivable_policy=policy,
        )


def test_gate_rejects_split_or_reorged_delivery_journal() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    opening, policy, flows, forcing = _direct_delivery(fixture)
    index = next(
        i
        for i, kind in enumerate(flows.journal_kind)
        if kind == "export_receivable_delivery" and flows.journal_currency[i] == USD_CURRENCY
    )
    original = flows.journal_amount[index]
    flows.journal_amount[index] = original / 2.0
    flows.journal_kind.append(flows.journal_kind[index])
    flows.journal_tick.append(flows.journal_tick[index])
    flows.journal_debit.append(flows.journal_debit[index])
    flows.journal_credit.append(flows.journal_credit[index])
    flows.journal_currency.append(flows.journal_currency[index])
    flows.journal_amount.append(original / 2.0)
    flows.journal_org.append(None)
    flows.journal_leg.append(0)
    flows.journal_event.append(flows.journal_event[index])
    with pytest.raises(accounting.AccountingError, match="journal rows do not match"):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            forcing=forcing,
            export_receivable_policy=policy,
        )

    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    opening, policy, flows, forcing = _direct_delivery(fixture)
    index = next(
        i
        for i, kind in enumerate(flows.journal_kind)
        if kind == "export_receivable_delivery"
    )
    flows.journal_org[index] = 9999
    with pytest.raises(accounting.AccountingError, match="journal_org"):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            forcing=forcing,
            export_receivable_policy=policy,
        )


def test_gate_rejects_phantom_d2_activity_on_a_legacy_tick() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        _forcing(fixture, ticks=1),
        fixture.parameters,
        fixture.network,
    )
    policy = _build_policy(fixture.state, _regime(), ())
    flows.export_receivable_balance_usd = 999.0
    receivable = treasury_receivable_account_id(
        fixture.state, USD_CURRENCY, AccountKind.EXPORT_RECEIVABLE
    )
    income = treasury_receivable_account_id(
        fixture.state, USD_CURRENCY, AccountKind.EXPORT_SALES_INCOME
    )
    flows.journal_kind.append("export_receivable_delivery")
    flows.journal_tick.append(flows.tick)
    flows.journal_debit.append(receivable)
    flows.journal_credit.append(income)
    flows.journal_currency.append(USD_CURRENCY)
    flows.journal_amount.append(999.0)
    flows.journal_org.append(None)
    flows.journal_leg.append(0)
    flows.journal_event.append("phantom")
    with pytest.raises(accounting.AccountingError, match="export_receivable"):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            forcing=_forcing(fixture, ticks=1),
            export_receivable_policy=policy,
        )


def test_gate_rejects_a_coherent_valuation_double() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    opening, policy, flows, forcing = _direct_delivery(fixture)
    flows.export_receivable_events = tuple(
        replace(event, amount=event.amount * 2.0)
        for event in flows.export_receivable_events
    )
    fixture.state.export_receivables = tuple(
        replace(lot, principal=lot.principal * 2.0, gross=lot.gross * 2.0)
        for lot in fixture.state.export_receivables
    )
    cmea_prices, usd_prices = flows.export_receivable_channel_prices
    flows.export_receivable_channel_prices = (
        tuple(value * 2.0 for value in cmea_prices),
        tuple(value * 2.0 for value in usd_prices),
    )
    flows.export_receivable_opened_usd *= 2.0
    flows.export_receivable_opened_cmea *= 2.0
    flows.export_receivable_balance_usd *= 2.0
    flows.export_receivable_balance_cmea *= 2.0
    for index, kind in enumerate(flows.journal_kind):
        if kind == "export_receivable_delivery":
            flows.journal_amount[index] *= 2.0
    with pytest.raises(
        accounting.AccountingError,
        match="prices_vs_forcing|delivery_principal",
    ):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            forcing=forcing,
            export_receivable_policy=policy,
        )


def test_direct_kernel_rejects_invalid_contract_event_and_forcing() -> None:
    from hsm_lab.engine.state import (
        ExportContract,
        ExportReceivableEvent,
        ExportReceivablePolicy,
    )

    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    bad_contract = ExportContract(
        contract_id="bad",
        currency=USD_CURRENCY,
        buyer_id=-1,
        seller_id=7,
        commodity_id="energy",
    )
    with pytest.raises(ValueError, match="negative|seller"):
        tick_material(
            fixture.state,
            _forcing(fixture, ticks=1),
            fixture.parameters,
            fixture.network,
            export_receivable_policy=ExportReceivablePolicy(
                term_quarters=1, contracts=(bad_contract,)
            ),
        )

    good_contract = ExportContract(
        contract_id="d2-usd-energy",
        currency=USD_CURRENCY,
        buyer_id=9101,
        seller_id=0,
        commodity_id="energy",
    )
    bad_event = ExportReceivableEvent(
        event_id="bad",
        tick=True,
        kind="receipt",
        receivable_id=USD_LOT,
        contract_id="d2-usd-energy",
        currency=USD_CURRENCY,
        buyer_id=9101,
        seller_id=0,
        commodity_id="energy",
        delivery_tick=0.0,
        due_tick=1.0,
        amount=True,
    )
    with pytest.raises(ValueError, match="strict integer|strict number"):
        tick_material(
            fixture.state,
            _forcing(fixture, ticks=1),
            fixture.parameters,
            fixture.network,
            export_receivable_policy=ExportReceivablePolicy(
                term_quarters=1,
                contracts=(good_contract,),
                events=(bad_event,),
            ),
        )

    bad_forcing = _forcing(fixture, ticks=2)
    bad_forcing.quarters[1] = bad_forcing.quarters[0]
    with pytest.raises(ValueError, match="strictly consecutive"):
        tick_material(
            fixture.state,
            bad_forcing,
            fixture.parameters,
            fixture.network,
            export_receivable_policy=ExportReceivablePolicy(
                term_quarters=1, contracts=(good_contract,)
            ),
        )


# ---------------------------------------------------------------------------
# Review-fix: rollback, timing, checkpoint semantics, observation read-only.
# ---------------------------------------------------------------------------


def test_failure_after_settlement_rolls_back_and_retry_succeeds(monkeypatch) -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    before = copy.deepcopy(fixture.state)

    def boom(*_args, **_kwargs):
        raise RuntimeError("injected gate failure")

    monkeypatch.setattr(era.accounting, "check_material_invariants", boom)
    with pytest.raises(ExportReceivableFailure) as caught:
        _run(fixture, _regime())
    assert caught.value.phase == "invariants"
    assert caught.value.failed_flows is not None
    assert caught.value.failed_state is not None
    assert fixture.state.completed_ticks == 0
    _assert_state_equal(fixture.state, before)

    monkeypatch.undo()
    result = _run(fixture, _regime())
    _assert_gate(result)
    assert fixture.state.completed_ticks == 1


def test_observation_failure_rolls_back(monkeypatch) -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    before = copy.deepcopy(fixture.state)

    def boom(*_args, **_kwargs):
        raise RuntimeError("injected observation failure")

    monkeypatch.setattr(era, "_build_observation", boom)
    with pytest.raises(ExportReceivableFailure) as caught:
        _run(fixture, _regime())
    assert caught.value.phase == "observation"
    assert fixture.state.completed_ticks == 0
    _assert_state_equal(fixture.state, before)


def test_receipt_is_not_spendable_until_the_next_quarter() -> None:
    fixture = _legacy_export_fixture(
        treasury=4.0, stock=8.0, usd_import_quantity=2.0
    )
    first = _run(fixture, _regime())
    _assert_gate(first)
    assert first.flows.usd_import_payment == 0.0
    assert fixture.state.usd_reserve == 0.0

    second = _run(
        fixture,
        _regime(),
        events=(_event("usd-full", 1, "receipt", USD_LOT, 6.0),),
    )
    _assert_gate(second)
    assert second.flows.usd_import_payment == 0.0  # opening cash was 0
    assert fixture.state.usd_reserve == pytest.approx(6.0)

    third = _run(fixture, _regime())
    _assert_gate(third)
    assert third.flows.usd_import_payment == pytest.approx(2.0)
    assert fixture.state.usd_reserve == pytest.approx(4.0)


def test_zero_stock_and_zero_funding_create_no_receivable() -> None:
    for kwargs in ({"treasury": 0.0, "stock": 8.0}, {"treasury": 4.0, "stock": 0.0}):
        fixture = _legacy_export_fixture(**kwargs)
        result = _run(fixture, _regime())
        _assert_gate(result)
        assert fixture.state.export_receivables == ()
        assert result.observation["receivable_close"] == []
        assert result.flows.export_receivable_opened_usd == 0.0
        assert result.flows.export_receivable_opened_cmea == 0.0


def test_end_window_debt_is_censored_and_next_tick_is_refused() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=1)
    result = execute_export_receivables_tick(
        fixture.state,
        forcing,
        fixture.parameters,
        fixture.network,
        regime=_regime(),
    )
    _assert_gate(result)
    assert len(fixture.state.export_receivables) == 2
    with pytest.raises(ExportReceivableFailure) as caught:
        execute_export_receivables_tick(
            fixture.state,
            forcing,
            fixture.parameters,
            fixture.network,
            regime=_regime(),
        )
    assert caught.value.phase == "forcing"


def _write_state_payload(state, directory: Path) -> None:
    from hsm_lab.storage.checkpoint import (
        RECEIVABLE_PAYLOAD,
        _receivable_payload,
    )

    (directory / RECEIVABLE_PAYLOAD).write_text(
        json.dumps(_receivable_payload(state), sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_checkpoint_payload_roundtrips_after_recovery(tmp_path) -> None:
    from hsm_lab.storage.checkpoint import _parse_receivable_payload

    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run(fixture, _regime())
    _run(
        fixture,
        _regime(),
        events=(
            _event("usd-part", 1, "receipt", USD_LOT, 4.0),
            _event("cmea-part", 1, "receipt", CMEA_LOT, 1.0),
        ),
    )
    _run(
        fixture,
        _regime(),
        events=(
            _event("usd-loss", 2, "loss", USD_LOT, 2.0),
            _event("cmea-loss", 2, "loss", CMEA_LOT, 1.0),
        ),
    )
    _run(
        fixture,
        _regime(),
        events=(
            _event("usd-wo", 3, "writeoff", USD_LOT, 2.0),
            _event("cmea-wo", 3, "writeoff", CMEA_LOT, 1.0),
        ),
    )
    _run(
        fixture,
        _regime(),
        events=(_event("usd-recovery", 4, "recovery", USD_LOT, 1.0),),
    )
    _write_state_payload(fixture.state, tmp_path)
    book, log = _parse_receivable_payload(tmp_path)
    assert book == fixture.state.export_receivables
    assert log == fixture.state.export_receivable_event_ids

    resumed = copy.deepcopy(fixture.state)
    resumed.export_receivables = book
    resumed.export_receivable_event_ids = log
    result = execute_export_receivables_tick(
        resumed,
        _forcing(fixture, ticks=6),
        fixture.parameters,
        fixture.network,
        regime=_regime(),
        events=(_event("usd-final", 5, "recovery", USD_LOT, 1.0),),
    )
    _assert_gate(result)
    assert resumed.usd_reserve == pytest.approx(6.0)
    assert _lots(fixture)[USD_LOT].written_off == pytest.approx(1.0)


def test_checkpoint_loader_rejects_malformed_receivable_semantics(
    tmp_path, contract
) -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    fixture.parameters = fixture.parameters.model_copy(
        update={
            "trade": fixture.parameters.trade.model_copy(
                update={"cmea_credit_envelope": 1.0}
            )
        }
    )
    fixture.spec = fixture.spec.model_copy(update={"material_parameters": fixture.parameters})
    opening = capture_material_stocks(fixture.state)
    forcing = _forcing(fixture, ticks=5)
    policy = _build_policy(fixture.state, _regime(), ())
    result = _run(fixture, _regime())
    _assert_gate(result)
    history = MaterialHistory()
    flows = result.flows
    summary = accounting.check_material_invariants(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        forcing=forcing,
        export_receivable_policy=policy,
    )
    invariant_summary = {
        "max_material_abs_residual": float(summary.max_material_abs_residual),
        "max_material_tolerance_ratio": float(summary.max_material_tolerance_ratio),
        "max_finance_abs_residual": float(summary.max_finance_abs_residual),
        "max_finance_tolerance_ratio": float(summary.max_finance_tolerance_ratio),
        "checked_cells": int(summary.checked_cells),
        "per_ledger": dict(summary.per_ledger),
        "expired_leftover_by_cell": summary.expired_leftover_by_cell,
        "forcing_segment": "synthetic_warmup",
        "treasury_deposit_open": float(opening.treasury_deposit),
        "bank_reserves_open": [float(v) for v in opening.bank_reserves],
        "housing_completed": float(
            np.sum(np.asarray(fixture.state.dwelling_stock) - opening.dwelling_stock)
        ),
    }
    history.digest_chain = advance_chain("0" * 64, fixture.state, flows)
    append_material_rows(
        history,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        region_ids=list(fixture.region_ids),
        commodity_ids=list(fixture.commodities),
        digest=history.digest_chain,
        invariant_summary=invariant_summary,
    )
    metadata = {
        "scenario": fixture.spec.model_dump(mode="json"),
        "region_ids": list(fixture.region_ids),
        "commodity_ids": list(fixture.commodities),
        "baseline_hash": contract.expected_baseline_sha256,
        "last_completed_quarter": str(
            fixture.spec.start.advance(fixture.state.completed_ticks - 1)
        ),
        "next_quarter": str(fixture.spec.start.advance(fixture.state.completed_ticks)),
        "source_run_id": "unit-d2-malformed",
    }
    path = save_material_checkpoint(
        checkpoint_dir(tmp_path, fixture.state.completed_ticks),
        fixture.state,
        fixture.network,
        history,
        RngRegistry(fixture.spec.seed),
        metadata,
    )
    mutations = (
        ("currency", "bogus"),
        ("seller_id", 7),
        ("buyer_id", -1),
        ("commodity_id", "not-a-good"),
        ("delivery_tick", -5),
        ("due_tick", -4),
        ("recovered", 999.0),
    )
    for index, (field, value) in enumerate(mutations):
        bad = tmp_path / f"bad-{index}"
        shutil.copytree(path, bad)
        payload = json.loads((bad / "receivables.json").read_text(encoding="utf-8"))
        payload["receivables"][0][field] = value
        (bad / "receivables.json").write_text(json.dumps(payload), encoding="utf-8")
        _rehash(bad)
        with pytest.raises(ResearchGateError, match="receivable"):
            load_material_checkpoint(bad, fixture.spec, contract, fixture.network)

    # Equation-preserving but temporally impossible: collection, provision,
    # write-off and recovery all inside the delivery tick.
    bad = tmp_path / "bad-time"
    shutil.copytree(path, bad)
    payload = json.loads((bad / "receivables.json").read_text(encoding="utf-8"))
    usd = next(
        entry for entry in payload["receivables"] if entry["principal"] == pytest.approx(6.0)
    )
    usd.update(
        {
            "gross": 5.0,
            "received": 1.0,
            "recovered": 1.0,
            "writeoffs": 1.0,
            "written_off": 0.0,
            "provision": 0.0,
            "provision_expense": 2.0,
            "provision_released": 1.0,
        }
    )
    (bad / "receivables.json").write_text(json.dumps(payload), encoding="utf-8")
    _rehash(bad)
    with pytest.raises(ResearchGateError, match="receivable"):
        load_material_checkpoint(bad, fixture.spec, contract, fixture.network)

    bad = tmp_path / "bad-log"
    shutil.copytree(path, bad)
    payload = json.loads((bad / "receivables.json").read_text(encoding="utf-8"))
    payload["event_ids"] = []
    (bad / "receivables.json").write_text(json.dumps(payload), encoding="utf-8")
    _rehash(bad)
    with pytest.raises(ResearchGateError, match="receivable"):
        load_material_checkpoint(bad, fixture.spec, contract, fixture.network)

    bad = tmp_path / "bad-reserved"
    shutil.copytree(path, bad)
    payload = json.loads((bad / "receivables.json").read_text(encoding="utf-8"))
    payload["event_ids"].append("delivery:d2-usd-energy@1:energy")
    (bad / "receivables.json").write_text(json.dumps(payload), encoding="utf-8")
    _rehash(bad)
    with pytest.raises(ResearchGateError, match="receivable"):
        load_material_checkpoint(bad, fixture.spec, contract, fixture.network)


def test_observation_builder_is_read_only() -> None:
    from hsm_lab.institutions.export_receivables_adapter import _build_observation

    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    forcing = _forcing(fixture, ticks=5)
    policy = _build_policy(fixture.state, _regime(), ())
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        forcing,
        fixture.parameters,
        fixture.network,
        export_receivable_policy=policy,
    )
    state_before = copy.deepcopy(fixture.state)
    flows_before = copy.deepcopy(flows)
    observation = _build_observation(
        state=fixture.state,
        opening=opening,
        flows=flows,
        regime=_regime(),
    )
    assert observation["schema_version"] == SCHEMA_ID
    _assert_state_equal(fixture.state, state_before)
    _assert_state_equal(flows, flows_before)


def test_old_future_and_same_tick_collection_are_rejected() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run(fixture, _regime())
    for spec in (
        _event("old", 0, "receipt", USD_LOT, 1.0),
        _event("future", 2, "receipt", USD_LOT, 1.0),
    ):
        with pytest.raises(ExportReceivableFailure) as caught:
            _run(fixture, _regime(), events=(spec,))
        assert caught.value.phase == "preflight"
    assert fixture.state.completed_ticks == 1

    from hsm_lab.engine.state import ExportReceivableEvent
    from hsm_lab.engine.trade import apply_receivable_events

    delivery = ExportReceivableEvent(
        event_id="delivery:same",
        tick=1,
        kind="delivery",
        receivable_id="same",
        contract_id="d2-usd-energy",
        currency=USD_CURRENCY,
        buyer_id=9101,
        seller_id=0,
        commodity_id="energy",
        delivery_tick=1,
        due_tick=2,
        amount=6.0,
    )
    receipt = ExportReceivableEvent(
        event_id="same-receipt",
        tick=1,
        kind="receipt",
        receivable_id="same",
        contract_id="d2-usd-energy",
        currency=USD_CURRENCY,
        buyer_id=9101,
        seller_id=0,
        commodity_id="energy",
        delivery_tick=1,
        due_tick=2,
        amount=6.0,
    )
    with pytest.raises(ValueError, match="delivery tick"):
        apply_receivable_events((), (), (delivery, receipt), current_tick=1)


def test_gate_binds_caller_events_to_the_admitted_policy() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run(fixture, _regime())
    forcing = _forcing(fixture, ticks=5)
    events = (_event("usd-part", 1, "receipt", USD_LOT, 4.0),)
    policy = _build_policy(fixture.state, _regime(), events)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        forcing,
        fixture.parameters,
        fixture.network,
        export_receivable_policy=policy,
    )
    fixture.state.completed_ticks = 2
    with pytest.raises(accounting.AccountingError, match="admitted policy events"):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            forcing=forcing,
            export_receivable_policy=replace(policy, events=()),
        )


def test_each_d2_artifact_alone_activates_the_default_off_gate() -> None:
    from hsm_lab.engine.finance import append_transaction

    receivable = treasury_receivable_account_id
    cases = ("account", "kind", "scalar", "event")
    for case in cases:
        fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
        opening = capture_material_stocks(fixture.state)
        flows = tick_material(
            fixture.state,
            _forcing(fixture, ticks=1),
            fixture.parameters,
            fixture.network,
        )
        if case == "account":
            append_transaction(
                flows,
                transaction_id=0,
                kind="phantom_unrecognized",
                legs=[
                    (
                        int(
                            receivable(
                                fixture.state,
                                USD_CURRENCY,
                                AccountKind.EXPORT_RECEIVABLE,
                            )
                        ),
                        int(
                            receivable(
                                fixture.state,
                                USD_CURRENCY,
                                AccountKind.EXPORT_SALES_INCOME,
                            )
                        ),
                        USD_CURRENCY,
                        1.0,
                    )
                ],
            )
        elif case == "kind":
            append_transaction(
                flows,
                transaction_id=0,
                kind="export_receivable_delivery",
                legs=[
                    (
                        int(
                            receivable(
                                fixture.state,
                                USD_CURRENCY,
                                AccountKind.EXPORT_RECEIVABLE,
                            )
                        ),
                        int(
                            receivable(
                                fixture.state,
                                USD_CURRENCY,
                                AccountKind.EXPORT_SALES_INCOME,
                            )
                        ),
                        USD_CURRENCY,
                        1.0,
                    )
                ],
            )
            flows.journal_event[-1] = None
        elif case == "scalar":
            flows.export_receivable_balance_usd = 1.0
        else:
            flows.journal_event[-1] = "phantom-event"
        with pytest.raises(accounting.AccountingError, match="D2 activity requires"):
            accounting.check_material_invariants(
                opening,
                fixture.state,
                flows,
                fixture.parameters,
                fixture.network,
            )


def test_gate_rejects_a_merged_event_transaction_leg() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run(fixture, _regime())
    forcing = _forcing(fixture, ticks=5)
    events = (
        _event("pay1", 1, "receipt", USD_LOT, 1.0),
        _event("pay2", 1, "receipt", USD_LOT, 1.0),
    )
    policy = _build_policy(fixture.state, _regime(), events)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        forcing,
        fixture.parameters,
        fixture.network,
        export_receivable_policy=policy,
    )
    fixture.state.completed_ticks = 2
    indices = [
        index
        for index, event_id in enumerate(flows.journal_event)
        if event_id == "pay2"
    ]
    assert len(indices) == 1
    flows.journal_leg[indices[0]] = 1
    with pytest.raises(
        accounting.AccountingError, match="one-leg transaction|does not end"
    ):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            forcing=forcing,
            export_receivable_policy=policy,
        )


def test_direct_preflight_rejects_missing_contract_before_mutation() -> None:
    from hsm_lab.engine.state import ExportContract, ExportReceivablePolicy

    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    before = copy.deepcopy(fixture.state)
    cmea_only = ExportReceivablePolicy(
        term_quarters=1,
        contracts=(
            ExportContract(
                contract_id="d2-cmea-energy",
                currency=CMEA_CURRENCY,
                buyer_id=9102,
                seller_id=0,
                commodity_id="energy",
            ),
        ),
    )
    with pytest.raises(ValueError, match="exactly one contract"):
        tick_material(
            fixture.state,
            _forcing(fixture, ticks=1),
            fixture.parameters,
            fixture.network,
            export_receivable_policy=cmea_only,
        )
    _assert_state_equal(fixture.state, before)


def test_direct_preflight_rejects_non_integer_clock_before_mutation() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    policy = _build_policy(fixture.state, _regime(), ())
    for bad in (True, 0.5):
        before = copy.deepcopy(fixture.state)
        fixture.state.completed_ticks = bad
        with pytest.raises(ValueError, match="integer"):
            tick_material(
                fixture.state,
                _forcing(fixture, ticks=1),
                fixture.parameters,
                fixture.network,
                export_receivable_policy=policy,
            )
        fixture.state.completed_ticks = before.completed_ticks
        _assert_state_equal(fixture.state, before)

    # Adapter rejection/rollback parity for the same clock input.
    before = copy.deepcopy(fixture.state)
    fixture.state.completed_ticks = True
    with pytest.raises(ExportReceivableFailure) as caught:
        _run(fixture, _regime())
    assert caught.value.phase == "preflight"
    fixture.state.completed_ticks = before.completed_ticks
    _assert_state_equal(fixture.state, before)


def test_direct_preflight_rejects_nonpositive_admitted_prices_before_mutation() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    policy = _build_policy(fixture.state, _regime(), ())
    cases = []
    zero = _forcing(fixture, ticks=1)
    zero.cmea_energy_price[0] = 0.0
    cases.append(zero)
    negative = _forcing(fixture, ticks=1)
    negative.cmea_energy_price[0] = -1.0
    cases.append(negative)
    negative_oil = _forcing(fixture, ticks=1)
    negative_oil.oil_price[0] = -1.0
    cases.append(negative_oil)
    for forcing in cases:
        before = copy.deepcopy(fixture.state)
        with pytest.raises(ValueError, match="finite and positive"):
            tick_material(
                fixture.state,
                forcing,
                fixture.parameters,
                fixture.network,
                export_receivable_policy=policy,
            )
        _assert_state_equal(fixture.state, before)

    # Adapter restores the same rejection.
    before = copy.deepcopy(fixture.state)
    with pytest.raises(ExportReceivableFailure) as caught:
        execute_export_receivables_tick(
            fixture.state,
            cases[0],
            fixture.parameters,
            fixture.network,
            regime=_regime(),
        )
    assert caught.value.phase in {"preflight", "tick_material"}
    _assert_state_equal(fixture.state, before)


def test_gate_rejects_fractional_or_boolean_d2_journal_values() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    opening, policy, flows, forcing = _direct_delivery(fixture)
    cases = (
        ("journal_leg", 0.5, "journal|strict integer"),
        ("journal_tick", 0.5, "journal|strict integer"),
        ("journal_debit", 38.5, "journal|strict integer"),
        ("journal_leg", True, "journal|strict integer"),
        ("journal_debit", True, "journal|strict integer"),
    )
    for field, value, match in cases:
        original = getattr(flows, field)
        index = next(
            i
            for i, event_id in enumerate(flows.journal_event)
            if event_id is not None
        )
        mutated = list(original)
        mutated[index] = value
        setattr(flows, field, mutated)
        with pytest.raises(accounting.AccountingError, match=match):
            accounting.check_material_invariants(
                opening,
                fixture.state,
                flows,
                fixture.parameters,
                fixture.network,
                forcing=forcing,
                export_receivable_policy=policy,
            )
        setattr(flows, field, original)


def test_checkpoint_rejects_provision_release_without_recovery(tmp_path, contract) -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    fixture.parameters = fixture.parameters.model_copy(
        update={
            "trade": fixture.parameters.trade.model_copy(
                update={"cmea_credit_envelope": 1.0}
            )
        }
    )
    fixture.spec = fixture.spec.model_copy(update={"material_parameters": fixture.parameters})
    _run(fixture, _regime())
    forcing = _forcing(fixture, ticks=5)
    policy = _build_policy(
        fixture.state, _regime(), (_event("usd-part", 1, "receipt", USD_LOT, 4.0),)
    )
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        forcing,
        fixture.parameters,
        fixture.network,
        export_receivable_policy=policy,
    )
    fixture.state.completed_ticks = 2
    summary = accounting.check_material_invariants(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        forcing=forcing,
        export_receivable_policy=policy,
    )
    history = MaterialHistory()
    invariant_summary = {
        "max_material_abs_residual": float(summary.max_material_abs_residual),
        "max_material_tolerance_ratio": float(summary.max_material_tolerance_ratio),
        "max_finance_abs_residual": float(summary.max_finance_abs_residual),
        "max_finance_tolerance_ratio": float(summary.max_finance_tolerance_ratio),
        "checked_cells": int(summary.checked_cells),
        "per_ledger": dict(summary.per_ledger),
        "expired_leftover_by_cell": summary.expired_leftover_by_cell,
        "forcing_segment": "synthetic_warmup",
        "treasury_deposit_open": float(opening.treasury_deposit),
        "bank_reserves_open": [float(v) for v in opening.bank_reserves],
        "housing_completed": float(
            np.sum(np.asarray(fixture.state.dwelling_stock) - opening.dwelling_stock)
        ),
    }
    # History needs both ticks; rebuild from a fresh fixture for completeness.
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    fixture.parameters = fixture.parameters.model_copy(
        update={
            "trade": fixture.parameters.trade.model_copy(
                update={"cmea_credit_envelope": 1.0}
            )
        }
    )
    fixture.spec = fixture.spec.model_copy(update={"material_parameters": fixture.parameters})
    history = MaterialHistory()
    chain = "0" * 64
    for tick in range(2):
        tick_policy = _build_policy(
            fixture.state,
            _regime(),
            () if tick == 0 else (_event("usd-part", 1, "receipt", USD_LOT, 4.0),),
        )
        tick_opening = capture_material_stocks(fixture.state)
        tick_flows = tick_material(
            fixture.state,
            forcing,
            fixture.parameters,
            fixture.network,
            export_receivable_policy=tick_policy,
        )
        fixture.state.completed_ticks = tick + 1
        tick_summary = accounting.check_material_invariants(
            tick_opening,
            fixture.state,
            tick_flows,
            fixture.parameters,
            fixture.network,
            forcing=forcing,
            export_receivable_policy=tick_policy,
        )
        invariant_summary = {
            "max_material_abs_residual": float(tick_summary.max_material_abs_residual),
            "max_material_tolerance_ratio": float(tick_summary.max_material_tolerance_ratio),
            "max_finance_abs_residual": float(tick_summary.max_finance_abs_residual),
            "max_finance_tolerance_ratio": float(tick_summary.max_finance_tolerance_ratio),
            "checked_cells": int(tick_summary.checked_cells),
            "per_ledger": dict(tick_summary.per_ledger),
            "expired_leftover_by_cell": tick_summary.expired_leftover_by_cell,
            "forcing_segment": "synthetic_warmup",
            "treasury_deposit_open": float(tick_opening.treasury_deposit),
            "bank_reserves_open": [float(v) for v in tick_opening.bank_reserves],
            "housing_completed": float(
                np.sum(np.asarray(fixture.state.dwelling_stock) - tick_opening.dwelling_stock)
            ),
        }
        chain = advance_chain(chain, fixture.state, tick_flows)
        append_material_rows(
            history,
            fixture.state,
            tick_flows,
            fixture.parameters,
            fixture.network,
            region_ids=list(fixture.region_ids),
            commodity_ids=list(fixture.commodities),
            digest=chain,
            invariant_summary=invariant_summary,
        )
    history.digest_chain = chain
    metadata = {
        "scenario": fixture.spec.model_dump(mode="json"),
        "region_ids": list(fixture.region_ids),
        "commodity_ids": list(fixture.commodities),
        "baseline_hash": contract.expected_baseline_sha256,
        "last_completed_quarter": str(
            fixture.spec.start.advance(fixture.state.completed_ticks - 1)
        ),
        "next_quarter": str(fixture.spec.start.advance(fixture.state.completed_ticks)),
        "source_run_id": "unit-d2-release",
    }
    path = save_material_checkpoint(
        checkpoint_dir(tmp_path, fixture.state.completed_ticks),
        fixture.state,
        fixture.network,
        history,
        RngRegistry(fixture.spec.seed),
        metadata,
    )
    payload = json.loads((path / "receivables.json").read_text(encoding="utf-8"))
    usd = next(
        entry for entry in payload["receivables"] if entry["principal"] == pytest.approx(6.0)
    )
    usd["provision_expense"] = 100.0
    usd["provision_released"] = 100.0
    (path / "receivables.json").write_text(json.dumps(payload), encoding="utf-8")
    _rehash(path)
    with pytest.raises(ResearchGateError, match="receivable"):
        load_material_checkpoint(path, fixture.spec, contract, fixture.network)


def test_caller_delivery_namespace_collision_rejects_before_mutation() -> None:
    from hsm_lab.engine.state import (
        ExportReceivableEvent,
        ExportReceivablePolicy,
    )

    fixture = _legacy_export_fixture(treasury=8.0, stock=16.0)
    _run(fixture, _regime())
    assert fixture.state.completed_ticks == 1
    lot = _lots(fixture)[USD_LOT]
    collision = ExportReceivableEvent(
        event_id="delivery:d2-usd-energy@1:energy",
        tick=1,
        kind="receipt",
        receivable_id=USD_LOT,
        contract_id=lot.contract_id,
        currency=USD_CURRENCY,
        buyer_id=lot.buyer_id,
        seller_id=lot.seller_id,
        commodity_id=lot.commodity_id,
        delivery_tick=lot.delivery_tick,
        due_tick=lot.due_tick,
        amount=1.0,
    )
    before = copy.deepcopy(fixture.state)
    with pytest.raises(ValueError, match="reserved delivery namespace"):
        tick_material(
            fixture.state,
            _forcing(fixture, ticks=5),
            fixture.parameters,
            fixture.network,
            export_receivable_policy=ExportReceivablePolicy(
                term_quarters=1,
                contracts=_build_policy(fixture.state, _regime(), ()).contracts,
                events=(collision,),
            ),
        )
    _assert_state_equal(fixture.state, before)

    with pytest.raises(ExportReceivableFailure) as caught:
        _run(
            fixture,
            _regime(),
            events=(
                _event(
                    "delivery:d2-usd-energy@1:energy",
                    1,
                    "receipt",
                    USD_LOT,
                    1.0,
                ),
            ),
        )
    assert caught.value.phase == "preflight"
    _assert_state_equal(fixture.state, before)


def test_simultaneous_new_delivery_and_old_receipt_is_allowed() -> None:
    fixture = _legacy_export_fixture(treasury=8.0, stock=16.0)
    _run(fixture, _regime())
    result = _run(
        fixture,
        _regime(),
        events=(_event("pay-old-usd", 1, "receipt", USD_LOT, 1.0),),
    )
    _assert_gate(result)
    assert fixture.state.usd_reserve == pytest.approx(1.0)
    assert any(lot.delivery_tick == 1 for lot in fixture.state.export_receivables)


def test_gate_rejects_non_d2_row_merged_into_d2_transaction() -> None:
    fixture = _legacy_export_fixture(
        treasury=4.0,
        stock=8.0,
        usd_reserve=10.0,
        usd_import_quantity=2.0,
    )
    opening, policy, flows, forcing = _direct_delivery(fixture)
    # The untampered gate passes.
    accounting.check_material_invariants(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        forcing=forcing,
        export_receivable_policy=policy,
    )
    import_index = next(
        index
        for index, kind in enumerate(flows.journal_kind)
        if kind == "import_payment" and flows.journal_currency[index] == USD_CURRENCY
    )
    last_d2 = max(
        index
        for index, kind in enumerate(flows.journal_kind)
        if kind in accounting._D2_JOURNAL_KINDS
    )
    columns = (
        "journal_kind",
        "journal_tick",
        "journal_debit",
        "journal_credit",
        "journal_currency",
        "journal_amount",
        "journal_org",
        "journal_leg",
        "journal_event",
    )
    values = {name: getattr(flows, name).pop(import_index) for name in columns}
    insert_at = last_d2 if import_index > last_d2 else last_d2
    for name in columns:
        getattr(flows, name).insert(insert_at, values[name])
    flows.journal_leg[insert_at] = 1
    with pytest.raises(accounting.AccountingError, match="does not end its transaction"):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            forcing=forcing,
            export_receivable_policy=policy,
        )


def test_reserved_delivery_log_poisoning_rejects_before_mutation() -> None:
    fixture = _legacy_export_fixture(treasury=8.0, stock=16.0)
    _run(fixture, _regime())
    assert fixture.state.completed_ticks == 1
    policy = _build_policy(fixture.state, _regime(), ())
    fixture.state.export_receivable_event_ids = (
        *fixture.state.export_receivable_event_ids,
        "delivery:d2-usd-energy@1:energy",
    )
    before = copy.deepcopy(fixture.state)
    with pytest.raises(ValueError, match="delivery log does not match"):
        tick_material(
            fixture.state,
            _forcing(fixture, ticks=5),
            fixture.parameters,
            fixture.network,
            export_receivable_policy=policy,
        )
    _assert_state_equal(fixture.state, before)

    with pytest.raises(ExportReceivableFailure) as caught:
        _run(fixture, _regime())
    assert caught.value.phase == "preflight"
    _assert_state_equal(fixture.state, before)


def test_non_reserved_delivery_like_ids_are_still_accepted() -> None:
    from hsm_lab.engine.state import ExportReceivableEvent

    fixture = _legacy_export_fixture(treasury=8.0, stock=16.0)
    _run(fixture, _regime())
    lot = _lots(fixture)[USD_LOT]
    events = tuple(
        ExportReceivableEvent(
            event_id=event_id,
            tick=1,
            kind="receipt",
            receivable_id=USD_LOT,
            contract_id=lot.contract_id,
            currency=USD_CURRENCY,
            buyer_id=lot.buyer_id,
            seller_id=lot.seller_id,
            commodity_id=lot.commodity_id,
            delivery_tick=lot.delivery_tick,
            due_tick=lot.due_tick,
            amount=0.25,
        )
        for event_id in (
            "delivery",
            "Delivery:pay-old",
            "redelivery:pay-old",
            "delivery-pay-old",
            "receipt:delivery:old",
        )
    )
    result = execute_export_receivables_tick(
        fixture.state,
        _forcing(fixture, ticks=5),
        fixture.parameters,
        fixture.network,
        regime=_regime(),
        events=tuple(
            _event(
                event.event_id,
                1,
                "receipt",
                USD_LOT,
                0.25,
            )
            for event in events
        ),
    )
    _assert_gate(result)
    assert fixture.state.usd_reserve == pytest.approx(1.25)


def test_direct_kernel_restores_state_on_unrepresentable_delivery_principal() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    prices = list(fixture.parameters.trade.convertible_prices)
    prices[0] = 1e308
    trade = fixture.parameters.trade.model_copy(
        update={"convertible_prices": prices, "cmea_credit_envelope": 1.0}
    )
    fixture.parameters = fixture.parameters.model_copy(update={"trade": trade})
    policy = _build_policy(fixture.state, _regime(), ())
    before = copy.deepcopy(fixture.state)
    with np.errstate(over="ignore"):
        with pytest.raises(ValueError, match="finite"):
            tick_material(
                fixture.state,
                _forcing(fixture, ticks=1),
                fixture.parameters,
                fixture.network,
                export_receivable_policy=policy,
            )
    _assert_state_equal(fixture.state, before)
    assert fixture.state.treasury_deposit == 4.0
    assert float(np.sum(fixture.state.stock_value)) == 8.0

    before = copy.deepcopy(fixture.state)
    with np.errstate(over="ignore"):
        with pytest.raises(ExportReceivableFailure):
            execute_export_receivables_tick(
                fixture.state,
                _forcing(fixture, ticks=1),
                fixture.parameters,
                fixture.network,
                regime=_regime(),
            )
    _assert_state_equal(fixture.state, before)
