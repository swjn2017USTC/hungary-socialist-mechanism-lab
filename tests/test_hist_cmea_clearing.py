"""H3F-D3: independent CMEA clearing, quotas, contract prices and settlement.

Every test drives the real material kernel and the real invariant gate.  The
fixture is the frozen D0 export boundary plus an explicit CMEA import demand so
the network compiles a real import-pool cell.  All amounts are synthetic
engineering inputs, not historical calibrations.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.engine import accounting
from hsm_lab.engine.finance import (
    CMEA_CURRENCY,
    AccountKind,
    build_account_directory,
    cmea_clearing_position_account_id,
    treasury_account_id,
)
from hsm_lab.engine.material import (
    advance_chain,
    canonical_material_bytes,
    tick_material,
)
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import (
    CmeaClearingAccount,
    CmeaClearingContract,
    CmeaClearingCounterparty,
    CmeaClearingEntry,
    CmeaClearingEvent,
    CmeaClearingPolicy,
    CmeaClearingSettlement,
    CmeaClearingTransfer,
    MaterialForcing,
    MaterialHistory,
    capture_material_stocks,
)
from hsm_lab.engine.trade import (
    validate_clearing_book,
    validate_clearing_policy,
)
from hsm_lab.institutions.cmea_clearing_adapter import (
    CmeaClearingEventSpec,
    CmeaClearingFailure,
    CmeaClearingRegime,
    CmeaContractSpec,
    CmeaCounterpartySpec,
    execute_cmea_clearing_tick,
    load_cmea_clearing_regime,
)
from hsm_lab.storage.checkpoint import (
    CLEARING_PAYLOAD,
    checkpoint_dir,
    load_material_checkpoint,
    save_material_checkpoint,
)
from hsm_lab.storage.material_output import append_material_rows
from tests.test_checkpoint import _rehash
from tests.test_hist_export_finance import _forcing, _legacy_export_fixture

REGIME_PATH = (
    Path(__file__).resolve().parents[1]
    / "config/trade_regimes/hist_vnext_v1/cmea_clearing.json"
)
IMPORT_CONTRACT = "d3-imp"
EXPORT_CONTRACT = "d3-exp"


def _counterparties(import_limit: float = 10.0, export_limit: float = 6.0):
    return (
        CmeaClearingCounterparty(counterparty_id=9201, credit_limit=import_limit),
        CmeaClearingCounterparty(counterparty_id=9202, credit_limit=export_limit),
    )


def _contracts(
    *,
    import_price: float = 2.0,
    export_price: float = 2.0,
    import_cp: int = 9201,
    export_cp: int = 9202,
    include_import: bool = True,
    include_export: bool = True,
) -> tuple[CmeaClearingContract, ...]:
    contracts: list[CmeaClearingContract] = []
    if include_import:
        contracts.append(
            CmeaClearingContract(
                contract_id=IMPORT_CONTRACT,
                counterparty_id=import_cp,
                direction="import",
                commodity_id="energy",
                price=import_price,
            )
        )
    if include_export:
        contracts.append(
            CmeaClearingContract(
                contract_id=EXPORT_CONTRACT,
                counterparty_id=export_cp,
                direction="export",
                commodity_id="energy",
                price=export_price,
            )
        )
    return tuple(contracts)


def _policy(
    *,
    import_limit: float = 10.0,
    export_limit: float = 6.0,
    import_price: float = 2.0,
    export_price: float = 2.0,
    import_cp: int = 9201,
    export_cp: int = 9202,
    include_import: bool = True,
    include_export: bool = True,
    events: tuple[CmeaClearingEvent, ...] = (),
    clearing_group: tuple[int, ...] = (9201, 9202),
) -> CmeaClearingPolicy:
    return CmeaClearingPolicy(
        term_quarters=1,
        counterparties=_counterparties(import_limit, export_limit),
        contracts=_contracts(
            import_price=import_price,
            export_price=export_price,
            import_cp=import_cp,
            export_cp=export_cp,
            include_import=include_import,
            include_export=include_export,
        ),
        events=events,
        clearing_group=clearing_group,
    )


def _fixture(*, import_quantity: float = 8.0, stock: float = 8.0):
    return _legacy_export_fixture(
        treasury=4.0, stock=stock, cmea_import_quantity=import_quantity
    )


def _run(fixture, policy: CmeaClearingPolicy, *, ticks: int = 5):
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        _forcing(fixture, ticks=ticks),
        fixture.parameters,
        fixture.network,
        cmea_clearing_policy=policy,
    )
    gate = accounting.check_material_invariants(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
        forcing=_forcing(fixture, ticks=ticks),
        cmea_clearing_policy=policy,
    )
    return opening, flows, gate


def _assert_gate(gate) -> None:
    assert gate.max_finance_abs_residual <= 1e-9
    assert gate.max_material_abs_residual <= 1e-9


def _positions(fixture) -> dict[int, float]:
    return {
        int(account.counterparty_id): float(account.balance)
        for account in fixture.state.cmea_clearing_accounts
    }


def _entries(fixture, direction: str | None = None):
    return [
        entry
        for entry in fixture.state.cmea_clearing_entries
        if direction is None or entry.direction == direction
    ]


def _settle(event_id: str, tick: int, entry_id: str, amount: float) -> CmeaClearingEvent:
    return CmeaClearingEvent(
        event_id=event_id,
        tick=tick,
        kind="settle_export",
        entry_id=entry_id,
        source_counterparty_id=None,
        target_counterparty_id=None,
        amount=amount,
    )


def _transfer(
    event_id: str, tick: int, source: int, target: int, amount: float
) -> CmeaClearingEvent:
    return CmeaClearingEvent(
        event_id=event_id,
        tick=tick,
        kind="transfer",
        entry_id=None,
        source_counterparty_id=source,
        target_counterparty_id=target,
        amount=amount,
    )


# ---------------------------------------------------------------------------
# Cumulative quotas and frozen contract prices.
# ---------------------------------------------------------------------------


def test_import_cap_is_cumulative_and_not_a_per_call_envelope() -> None:
    fixture = _fixture()
    policy = _policy(import_limit=10.0, export_cp=9201)
    _opening, first, gate = _run(fixture, policy)
    _assert_gate(gate)
    # 8 desired units at the frozen price 2: the cumulative limit buys 5.
    assert first.cmea_imports[fixture.g("energy")] == pytest.approx(5.0)
    assert first.cmea_clearing_import_payment == pytest.approx(10.0)
    assert _positions(fixture)[9201] == pytest.approx(-10.0)
    assert len(_entries(fixture, "import")) == 1

    fixture.state.completed_ticks = 1
    _opening, second, gate = _run(fixture, policy)
    _assert_gate(gate)
    # The exhausted cumulative boundary cannot be re-used for another call.
    assert second.cmea_imports[fixture.g("energy")] == pytest.approx(0.0)
    assert _positions(fixture)[9201] == pytest.approx(-10.0)
    assert len(_entries(fixture, "import")) == 1


def test_zero_quota_never_borrows_from_usd_or_domestic() -> None:
    fixture = _fixture()
    _opening, flows, gate = _run(fixture, _policy(import_limit=0.0))
    _assert_gate(gate)
    assert flows.cmea_imports[fixture.g("energy")] == 0.0
    assert flows.usd_import_payment == 0.0
    assert fixture.state.cmea_settlement_balance == 0.0
    assert _entries(fixture, "import") == []


def test_non_binding_limit_leaves_quota_unused_without_creating_income() -> None:
    fixture = _fixture()
    _opening, flows, gate = _run(fixture, _policy(import_limit=30.0))
    _assert_gate(gate)
    assert flows.cmea_imports[fixture.g("energy")] == pytest.approx(8.0)
    assert flows.cmea_clearing_import_payment == pytest.approx(16.0)
    assert _positions(fixture)[9201] == pytest.approx(-16.0)
    # The remaining 14 of the same cumulative limit funds 7 more units; a
    # further call is then exhausted.  No call creates income or a new limit.
    fixture.state.completed_ticks = 1
    _opening, again, gate = _run(fixture, _policy(import_limit=30.0))
    _assert_gate(gate)
    assert again.cmea_imports[fixture.g("energy")] == pytest.approx(7.0)
    assert again.cmea_clearing_import_payment == pytest.approx(14.0)
    assert _positions(fixture)[9201] == pytest.approx(-30.0)
    fixture.state.completed_ticks = 2
    _opening, exhausted, gate = _run(fixture, _policy(import_limit=30.0))
    _assert_gate(gate)
    assert exhausted.cmea_imports[fixture.g("energy")] == 0.0
    assert exhausted.cmea_clearing_import_payment == 0.0


def test_positive_claim_is_spendable_once_and_not_a_loan_asset() -> None:
    fixture = _fixture()
    base = _policy(import_limit=0.0, export_limit=0.0, import_cp=9202)
    _opening, first, gate = _run(fixture, base)
    _assert_gate(gate)
    assert _positions(fixture)[9202] == pytest.approx(0.0)
    assert first.cmea_clearing_export_pending == pytest.approx(4.0)

    fixture.state.completed_ticks = 1
    entry_id = "export:d3-exp@0:energy"
    settle = _settle("settle-0", 1, entry_id, 4.0)
    _opening, second, gate = _run(
        fixture,
        replace(base, events=(settle,)),
    )
    _assert_gate(gate)
    assert _positions(fixture)[9202] == pytest.approx(4.0)

    # Reduce the desired import to 3 units (amount 6 > claim 4).
    fixture.parameters = fixture.parameters.model_copy(
        update={
            "trade": fixture.parameters.trade.model_copy(
                update={"cmea_desired_imports": [3.0] + [0.0] * 7}
            )
        }
    )
    fixture.state.completed_ticks = 2
    _opening, third, gate = _run(fixture, replace(base, events=()))
    _assert_gate(gate)
    assert third.cmea_imports[fixture.g("energy")] == pytest.approx(2.0)
    assert third.cmea_clearing_import_payment == pytest.approx(4.0)
    assert _positions(fixture)[9202] == pytest.approx(0.0)


def test_frozen_contract_price_ignores_forcing_quote() -> None:
    fixture = _fixture()
    # The forcing CMEA quote is 1.0; the contract freezes 2.0.
    _opening, flows, gate = _run(
        fixture, _policy(import_price=2.0, export_price=2.0)
    )
    _assert_gate(gate)
    assert flows.cmea_clearing_import_payment == pytest.approx(10.0)
    assert flows.cmea_clearing_export_pending == pytest.approx(4.0)

    other = _fixture()
    _opening, priced, gate = _run(
        other, _policy(import_price=3.0, export_price=5.0)
    )
    _assert_gate(gate)
    assert priced.cmea_imports[other.g("energy")] == pytest.approx(10.0 / 3.0)
    assert priced.cmea_clearing_import_payment == pytest.approx(10.0)
    assert priced.cmea_clearing_export_pending == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Settlement timing, quota restoration and overdue identity.
# ---------------------------------------------------------------------------


def test_export_pending_releases_quota_only_at_explicit_settlement() -> None:
    fixture = _fixture()
    policy = _policy(import_limit=10.0, export_cp=9201)
    _opening, first, gate = _run(fixture, policy)
    _assert_gate(gate)
    assert _positions(fixture)[9201] == pytest.approx(-10.0)
    assert first.cmea_clearing_export_pending == pytest.approx(4.0)

    # Tick 1: no settlement yet; the delivered export is still pending and the
    # exhausted quota cannot fund a new import.
    fixture.state.completed_ticks = 1
    _opening, second, gate = _run(fixture, policy)
    _assert_gate(gate)
    assert second.cmea_imports[fixture.g("energy")] == 0.0
    assert _positions(fixture)[9201] == pytest.approx(-10.0)

    # Tick 2: settle the tick-0 claim (due tick 1).  The settlement releases 4.
    fixture.state.completed_ticks = 2
    settle = _settle("settle-t0", 2, "export:d3-exp@0:energy", 4.0)
    _opening, third, gate = _run(fixture, replace(policy, events=(settle,)))
    _assert_gate(gate)
    assert third.cmea_clearing_export_settled == pytest.approx(4.0)
    assert _positions(fixture)[9201] == pytest.approx(-6.0)

    # Tick 3: the released 4 funds exactly 2 units at price 2.
    fixture.state.completed_ticks = 3
    _opening, fourth, gate = _run(fixture, policy)
    _assert_gate(gate)
    assert fourth.cmea_imports[fixture.g("energy")] == pytest.approx(2.0)
    assert fourth.cmea_clearing_import_payment == pytest.approx(4.0)
    assert _positions(fixture)[9201] == pytest.approx(-10.0)


def test_settlement_before_due_or_above_outstanding_is_rejected() -> None:
    fixture = _fixture()
    policy = _policy()
    _run(fixture, policy)
    # Tick 0 is the delivery tick; its due tick is 1.
    # A term-2 delivery is not settleable one tick before its due tick.
    term_two = CmeaClearingPolicy(
        term_quarters=2,
        counterparties=policy.counterparties,
        contracts=policy.contracts,
        clearing_group=policy.clearing_group,
    )
    fixture_two = _fixture()
    _run(fixture_two, term_two)
    fixture_two.state.completed_ticks = 1
    early = _settle("early", 1, "export:d3-exp@0:energy", 1.0)
    with pytest.raises(ValueError, match="before its due tick"):
        _run(fixture_two, replace(term_two, events=(early,)))

    fixture.state.completed_ticks = 1
    too_much = _settle("too-much", 1, "export:d3-exp@0:energy", 5.0)
    with pytest.raises(ValueError, match="exceeds the outstanding"):
        _run(fixture, replace(policy, events=(too_much,)))


def test_overdue_import_identity_is_retained_without_writeoff() -> None:
    fixture = _fixture()
    policy = _policy()
    _run(fixture, policy)
    fixture.state.completed_ticks = 1
    _run(fixture, policy)
    fixture.state.completed_ticks = 2
    _opening, flows, gate = _run(fixture, policy)
    _assert_gate(gate)
    overdue = dict(flows.cmea_clearing_overdue)
    assert overdue[9201] == pytest.approx(10.0)
    assert any(
        entry.direction == "import" and entry.settled == 0.0
        for entry in fixture.state.cmea_clearing_entries
    )
    # Another tick keeps the same gross obligation and does not invent a loss.
    fixture.state.completed_ticks = 3
    _opening, later, gate = _run(fixture, policy)
    _assert_gate(gate)
    assert dict(later.cmea_clearing_overdue)[9201] == pytest.approx(10.0)
    assert _positions(fixture)[9201] == pytest.approx(-10.0)


# ---------------------------------------------------------------------------
# Counterparty isolation and authorised transfers.
# ---------------------------------------------------------------------------


def test_bilateral_balances_are_never_netted_across_counterparties() -> None:
    fixture = _fixture()
    policy = _policy(import_limit=10.0, export_limit=6.0)
    _run(fixture, policy)
    fixture.state.completed_ticks = 1
    settle = _settle("settle-a", 1, "export:d3-exp@0:energy", 4.0)
    _opening, flows, gate = _run(fixture, replace(policy, events=(settle,)))
    _assert_gate(gate)
    positions = dict(flows.cmea_clearing_positions)
    assert positions[9201] == pytest.approx(-10.0)
    assert positions[9202] == pytest.approx(4.0)
    # The aggregate -6 is not a legal substitute for the two identities.
    assert sum(positions.values()) == pytest.approx(-6.0)


def test_transfer_requires_group_and_preserves_the_path() -> None:
    fixture = _fixture()
    policy = _policy()
    _run(fixture, policy)
    fixture.state.completed_ticks = 1
    settle = _settle("settle-b", 1, "export:d3-exp@0:energy", 4.0)
    _opening, _flows, gate = _run(fixture, replace(policy, events=(settle,)))
    _assert_gate(gate)
    assert _positions(fixture)[9202] == pytest.approx(4.0)

    fixture.state.completed_ticks = 2
    transfer = _transfer("transfer-1", 2, 9202, 9201, 4.0)
    _opening, flows, gate = _run(fixture, replace(policy, events=(transfer,)))
    _assert_gate(gate)
    assert _positions(fixture)[9202] == pytest.approx(0.0)
    assert _positions(fixture)[9201] == pytest.approx(-6.0)
    assert [item.event_id for item in fixture.state.cmea_clearing_transfers] == [
        "transfer-1"
    ]
    assert "transfer-1" in fixture.state.cmea_clearing_event_ids

    # Without the group, the same transfer is refused before mutation.
    fixture.state.completed_ticks = 2
    with pytest.raises(ValueError, match="not authorised"):
        _run(fixture, replace(policy, events=(transfer,), clearing_group=()))


def test_transfer_cannot_spend_more_than_the_confirmed_claim() -> None:
    fixture = _fixture()
    policy = _policy()
    _run(fixture, policy)
    fixture.state.completed_ticks = 1
    settle = _settle("settle-c", 1, "export:d3-exp@0:energy", 4.0)
    _run(fixture, replace(policy, events=(settle,)))
    fixture.state.completed_ticks = 2
    with pytest.raises(ValueError, match="exceeds counterparty 9202"):
        _run(
            fixture,
            replace(policy, events=(_transfer("bad", 2, 9202, 9201, 5.0),)),
        )


# ---------------------------------------------------------------------------
# Identity, event and journal gates.
# ---------------------------------------------------------------------------


def test_wrong_direction_contract_and_currency_are_rejected() -> None:
    fixture = _fixture()
    policy = _policy()
    _run(fixture, policy)
    fixture.state.completed_ticks = 1
    # Settling an import entry is not an export finality event.
    with pytest.raises(ValueError, match="non-export entry"):
        _run(
            fixture,
            replace(policy, events=(_settle("bad", 1, "import:d3-imp@0", 1.0),)),
        )

    with pytest.raises(ValueError, match="undeclared counterparty"):
        validate_clearing_policy(
            CmeaClearingPolicy(
                term_quarters=1,
                counterparties=_counterparties(),
                contracts=(
                    CmeaClearingContract(
                        "bad", 9999, "import", "energy", 1.0
                    ),
                ),
            )
        )
    with pytest.raises(ValueError, match="duplicate contract key"):
        validate_clearing_policy(
            CmeaClearingPolicy(
                term_quarters=1,
                counterparties=_counterparties(),
                contracts=(
                    CmeaClearingContract("a", 9201, "import", "energy", 1.0),
                    CmeaClearingContract("b", 9202, "import", "energy", 2.0),
                ),
            )
        )


def test_missing_export_contract_is_a_preflight_gate() -> None:
    fixture = _fixture()
    policy = _policy(include_export=False)
    with pytest.raises(ValueError, match="export demand for 'energy' has no contract"):
        _run(fixture, policy)


def test_duplicate_future_past_and_reserved_events_are_rejected() -> None:
    fixture = _fixture()
    base = _policy()
    with pytest.raises(ValueError, match="duplicate event id"):
        validate_clearing_policy(
            replace(
                base,
                events=(
                    _settle("dup", 1, "export:d3-exp@0:energy", 1.0),
                    _settle("dup", 1, "export:d3-exp@0:energy", 1.0),
                ),
            )
        )
    future = _settle("future", 3, "export:d3-exp@0:energy", 1.0)
    with pytest.raises(ValueError, match="carries tick 3"):
        _run(fixture, replace(base, events=(future,)))
    with pytest.raises(ValueError, match="reserved entry namespace"):
        validate_clearing_policy(
            replace(
                base,
                events=(_settle("import:bad", 1, "export:d3-exp@0:energy", 1.0),),
            )
        )
    fixture.state.completed_ticks = 1
    with pytest.raises(ValueError, match="unknown entry"):
        _run(
            fixture,
            replace(base, events=(_settle("missing", 1, "export:nope@0:energy", 1.0),)),
        )


def test_d3_journals_are_exact_and_cmea_only() -> None:
    fixture = _fixture()
    _opening, flows, gate = _run(fixture, _policy())
    _assert_gate(gate)
    rows = [
        (kind, flows.journal_currency[index], flows.journal_amount[index])
        for index, kind in enumerate(flows.journal_kind)
        if kind.startswith("cmea_clearing_")
    ]
    assert sorted(rows) == [
        ("cmea_clearing_export", CMEA_CURRENCY, 4.0),
        ("cmea_clearing_import", CMEA_CURRENCY, 10.0),
    ]
    # No USD or domestic leg may carry a D3 account.
    for index, kind in enumerate(flows.journal_kind):
        if kind.startswith("cmea_clearing_"):
            assert flows.journal_currency[index] == CMEA_CURRENCY


def test_journal_tamper_is_rejected() -> None:
    fixture = _fixture()
    opening = capture_material_stocks(fixture.state)
    policy = _policy()
    flows = tick_material(
        fixture.state,
        _forcing(fixture, ticks=5),
        fixture.parameters,
        fixture.network,
        cmea_clearing_policy=policy,
    )
    for index, kind in enumerate(flows.journal_kind):
        if kind == "cmea_clearing_import":
            flows.journal_amount[index] += 1.0
            break
    with pytest.raises(accounting.AccountingError, match="D3 journal rows"):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
            forcing=_forcing(fixture, ticks=5),
            cmea_clearing_policy=policy,
        )


# ---------------------------------------------------------------------------
# No goods, overflow rollback and default-off identity.
# ---------------------------------------------------------------------------


def test_no_stock_creates_no_export_credit() -> None:
    fixture = _fixture(import_quantity=0.0, stock=0.0)
    _opening, flows, gate = _run(
        fixture,
        _policy(include_import=False, include_export=True),
    )
    _assert_gate(gate)
    assert flows.cmea_clearing_export_pending == 0.0
    assert _entries(fixture, "export") == []
    assert all(account.balance == 0.0 for account in fixture.state.cmea_clearing_accounts)


def test_overflow_rolls_back_the_public_kernel_and_adapter() -> None:
    fixture = _fixture()
    policy = _policy(export_price=1e308)
    before = copy.deepcopy(fixture.state)
    with pytest.raises(ValueError):
        tick_material(
            fixture.state,
            _forcing(fixture, ticks=5),
            fixture.parameters,
            fixture.network,
            cmea_clearing_policy=policy,
        )
    for field_name in fixture.state.__dataclass_fields__:
        left = getattr(fixture.state, field_name)
        right = getattr(before, field_name)
        if isinstance(left, np.ndarray):
            assert np.array_equal(left, right)
        else:
            assert left == right

    regime = CmeaClearingRegime(
        schema_version="hist-cmea-clearing-regime-v1",
        regime_id="cmea_clearing",
        source_kind="synthetic",
        term_quarters=1,
        clearing_group=(9201, 9202),
        counterparties=(
            CmeaCounterpartySpec(counterparty_id=9201, credit_limit=10.0),
            CmeaCounterpartySpec(counterparty_id=9202, credit_limit=6.0),
        ),
        contracts=(
            CmeaContractSpec(
                contract_id=IMPORT_CONTRACT,
                counterparty_id=9201,
                direction="import",
                commodity_id="energy",
                price=2.0,
            ),
            CmeaContractSpec(
                contract_id=EXPORT_CONTRACT,
                counterparty_id=9202,
                direction="export",
                commodity_id="energy",
                price=1e308,
            ),
        ),
    )
    with pytest.raises(CmeaClearingFailure):
        execute_cmea_clearing_tick(
            fixture.state,
            _forcing(fixture, ticks=5),
            fixture.parameters,
            fixture.network,
            regime=regime,
        )
    for field_name in fixture.state.__dataclass_fields__:
        left = getattr(fixture.state, field_name)
        right = getattr(before, field_name)
        if isinstance(left, np.ndarray):
            assert np.array_equal(left, right)
        else:
            assert left == right


def test_default_off_has_no_clearing_artifacts() -> None:
    fixture = _fixture()
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        _forcing(fixture, ticks=5),
        fixture.parameters,
        fixture.network,
    )
    accounting.check_material_invariants(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
    )
    assert fixture.state.cmea_clearing_accounts == ()
    assert fixture.state.cmea_clearing_entries == ()
    assert fixture.state.cmea_clearing_transfers == ()
    assert fixture.state.cmea_clearing_event_ids == ()
    assert not any(kind.startswith("cmea_clearing_") for kind in flows.journal_kind)
    assert not any(event is not None for event in flows.journal_event)
    # The legacy scalar and the USD channel keep their original behaviour.
    assert flows.cmea_import_payment == pytest.approx(0.0)
    assert flows.cmea_export_receipt == pytest.approx(2.0)
    assert flows.usd_export_receipt == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# Regime loader and checkpoint.
# ---------------------------------------------------------------------------


def test_regime_loader_is_strict() -> None:
    regime = load_cmea_clearing_regime(REGIME_PATH)
    assert regime.regime_id == "cmea_clearing"
    assert regime.term_quarters == 1
    assert len(regime.counterparties) == 2
    bad = json.loads(REGIME_PATH.read_text(encoding="utf-8"))
    bad["unexpected"] = 1
    path = REGIME_PATH.parent / "_bad_d3_regime.json"
    try:
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ResearchGateError, match="unexpected keys"):
            load_cmea_clearing_regime(path)
    finally:
        path.unlink(missing_ok=True)


def _checkpoint_metadata(fixture, contract, opening, flows, summary) -> dict:
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
    history = MaterialHistory()
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
    return {
        "scenario": fixture.spec.model_dump(mode="json"),
        "region_ids": list(fixture.region_ids),
        "commodity_ids": list(fixture.commodities),
        "baseline_hash": contract.expected_baseline_sha256,
        "last_completed_quarter": str(
            fixture.spec.start.advance(fixture.state.completed_ticks - 1)
        ),
        "next_quarter": str(fixture.spec.start.advance(fixture.state.completed_ticks)),
        "source_run_id": "unit-d3",
    }, history


def test_checkpoint_roundtrip_resume_and_tamper(tmp_path, contract) -> None:
    fixture = _fixture()
    fixture.parameters = fixture.parameters.model_copy(
        update={
            "trade": fixture.parameters.trade.model_copy(
                update={"cmea_credit_envelope": 1.0}
            )
        }
    )
    fixture.spec = fixture.spec.model_copy(update={"material_parameters": fixture.parameters})
    policy = _policy()
    opening, flows, gate = _run(fixture, policy)
    _assert_gate(gate)
    fixture.state.completed_ticks = 1
    metadata, history = _checkpoint_metadata(fixture, contract, opening, flows, gate)
    path = save_material_checkpoint(
        checkpoint_dir(tmp_path, fixture.state.completed_ticks),
        fixture.state,
        fixture.network,
        history,
        RngRegistry(fixture.spec.seed),
        metadata,
    )
    assert (path / CLEARING_PAYLOAD).is_file()
    loaded, _history, _rng, _metadata = load_material_checkpoint(
        path, fixture.spec, contract, fixture.network
    )
    assert loaded.cmea_clearing_accounts == fixture.state.cmea_clearing_accounts
    assert loaded.cmea_clearing_entries == fixture.state.cmea_clearing_entries
    assert loaded.cmea_clearing_transfers == fixture.state.cmea_clearing_transfers
    assert loaded.cmea_clearing_event_ids == fixture.state.cmea_clearing_event_ids

    # Resume: settlement at tick 1 must use the restored book.
    resumed = execute_cmea_clearing_tick(
        loaded,
        _forcing(fixture, ticks=5),
        fixture.parameters,
        fixture.network,
        regime=CmeaClearingRegime(
            schema_version="hist-cmea-clearing-regime-v1",
            regime_id="cmea_clearing",
            source_kind="synthetic",
            term_quarters=1,
            clearing_group=(9201, 9202),
            counterparties=(
                CmeaCounterpartySpec(counterparty_id=9201, credit_limit=10.0),
                CmeaCounterpartySpec(counterparty_id=9202, credit_limit=6.0),
            ),
            contracts=(
                CmeaContractSpec(
                    contract_id=IMPORT_CONTRACT,
                    counterparty_id=9201,
                    direction="import",
                    commodity_id="energy",
                    price=2.0,
                ),
                CmeaContractSpec(
                    contract_id=EXPORT_CONTRACT,
                    counterparty_id=9202,
                    direction="export",
                    commodity_id="energy",
                    price=2.0,
                ),
            ),
        ),
        events=(
            CmeaClearingEventSpec(
                event_id="resume-settle",
                tick=1,
                kind="settle_export",
                entry_id="export:d3-exp@0:energy",
                amount=4.0,
            ),
        ),
    )
    _assert_gate(resumed.gate)
    assert dict(resumed.observation["positions"])[9202] == pytest.approx(4.0)

    # Tamper the cleared amount and rehash; semantic validation must reject.
    tampered = tmp_path / "tampered"
    import shutil

    shutil.copytree(path, tampered)
    payload = json.loads((tampered / CLEARING_PAYLOAD).read_text(encoding="utf-8"))
    payload["entries"][0]["settled"] = payload["entries"][0]["amount"] + 1.0
    (tampered / CLEARING_PAYLOAD).write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    _rehash(tampered)
    with pytest.raises(ResearchGateError, match="clearing semantics rejected"):
        load_material_checkpoint(tampered, fixture.spec, contract, fixture.network)


def test_default_off_checkpoint_has_no_clearing_sidecar(tmp_path, contract) -> None:
    fixture = _fixture()
    fixture.parameters = fixture.parameters.model_copy(
        update={
            "trade": fixture.parameters.trade.model_copy(
                update={"cmea_credit_envelope": 1.0}
            )
        }
    )
    fixture.spec = fixture.spec.model_copy(update={"material_parameters": fixture.parameters})
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        _forcing(fixture, ticks=5),
        fixture.parameters,
        fixture.network,
    )
    summary = accounting.check_material_invariants(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
    )
    fixture.state.completed_ticks = 1
    metadata, history = _checkpoint_metadata(fixture, contract, opening, flows, summary)
    path = save_material_checkpoint(
        checkpoint_dir(tmp_path, fixture.state.completed_ticks),
        fixture.state,
        fixture.network,
        history,
        RngRegistry(fixture.spec.seed),
        metadata,
    )
    assert not (path / CLEARING_PAYLOAD).exists()


def test_1975_boundary_does_not_rewrite_confirmed_contract_amounts() -> None:
    """A 1974Q4 delivery keeps its frozen price across the 1975Q1 rule boundary."""
    fixture = _legacy_export_fixture(
        treasury=8.0, stock=8.0, cmea_import_quantity=8.0
    )
    policy = _policy()
    forcing = MaterialForcing(
        quarters=["1974Q4", "1975Q1"],
        oil_price=np.array([fixture.parameters.world_oil_reference] * 2),
        global_usd_rate=np.zeros(2),
        official_fx=np.array([np.nan, np.nan]),
        cmea_energy_price=np.array([1.0, 9.0]),
        segment=["synthetic"] * 2,
        input_artifact_hashes={},
    )
    opening = capture_material_stocks(fixture.state)
    first = tick_material(
        fixture.state,
        forcing,
        fixture.parameters,
        fixture.network,
        cmea_clearing_policy=policy,
    )
    accounting.check_material_invariants(
        opening,
        fixture.state,
        first,
        fixture.parameters,
        fixture.network,
        forcing=forcing,
        cmea_clearing_policy=policy,
    )
    old_import = next(
        entry for entry in fixture.state.cmea_clearing_entries if entry.direction == "import"
    )
    old_export = next(
        entry for entry in fixture.state.cmea_clearing_entries if entry.direction == "export"
    )
    assert old_import.amount == pytest.approx(10.0)
    assert old_export.amount == pytest.approx(4.0)

    fixture.state.completed_ticks = 1
    opening = capture_material_stocks(fixture.state)
    second = tick_material(
        fixture.state,
        forcing,
        fixture.parameters,
        fixture.network,
        cmea_clearing_policy=policy,
    )
    accounting.check_material_invariants(
        opening,
        fixture.state,
        second,
        fixture.parameters,
        fixture.network,
        forcing=forcing,
        cmea_clearing_policy=policy,
    )
    # The 1975 quote is 9.0, but both the old and the new contract amounts stay
    # at the frozen price 2.0; no prior amount is rewritten by the new window.
    assert next(
        entry for entry in fixture.state.cmea_clearing_entries
        if entry.entry_id == old_import.entry_id
    ).amount == pytest.approx(10.0)
    assert next(
        entry for entry in fixture.state.cmea_clearing_entries
        if entry.entry_id == old_export.entry_id
    ).amount == pytest.approx(4.0)
    assert second.cmea_clearing_export_pending == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# P1/P2 negative gates: default-off traces, exact books and checkpoint loss.
# ---------------------------------------------------------------------------


def _regime_from_policy(policy: CmeaClearingPolicy) -> CmeaClearingRegime:
    return CmeaClearingRegime(
        schema_version="hist-cmea-clearing-regime-v1",
        regime_id="cmea_clearing",
        source_kind="synthetic",
        term_quarters=int(policy.term_quarters),
        clearing_group=tuple(int(cid) for cid in policy.clearing_group),
        counterparties=tuple(
            CmeaCounterpartySpec(
                counterparty_id=int(item.counterparty_id),
                credit_limit=float(item.credit_limit),
            )
            for item in policy.counterparties
        ),
        contracts=tuple(
            CmeaContractSpec(
                contract_id=item.contract_id,
                counterparty_id=int(item.counterparty_id),
                direction=item.direction,
                commodity_id=item.commodity_id,
                price=float(item.price),
            )
            for item in policy.contracts
        ),
    )


def test_forged_d3_position_account_without_policy_is_rejected() -> None:
    fixture = _fixture()
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        _forcing(fixture, ticks=5),
        fixture.parameters,
        fixture.network,
    )
    forged = cmea_clearing_position_account_id(fixture.state, 9999)
    fiscal = treasury_account_id(fixture.state, AccountKind.FISCAL_EXPENSE)
    flows.journal_kind.append("forged_d3_position")
    flows.journal_tick.append(int(flows.tick))
    flows.journal_debit.append(forged)
    flows.journal_credit.append(fiscal)
    flows.journal_currency.append(CMEA_CURRENCY)
    flows.journal_amount.append(1.0)
    flows.journal_org.append(None)
    flows.journal_leg.append(0)
    flows.journal_event.append(None)
    with pytest.raises(accounting.AccountingError, match="D3 clearing activity"):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
        )


def test_contract_price_only_trace_without_policy_is_rejected() -> None:
    fixture = _fixture()
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        _forcing(fixture, ticks=5),
        fixture.parameters,
        fixture.network,
    )
    flows.cmea_clearing_contract_prices = (("ghost", 1.0),)
    with pytest.raises(accounting.AccountingError, match="D3 clearing activity"):
        accounting.check_material_invariants(
            opening,
            fixture.state,
            flows,
            fixture.parameters,
            fixture.network,
        )


def _save_d3_checkpoint(fixture, contract, tmp_path, opening, flows, summary):
    metadata, history = _checkpoint_metadata(fixture, contract, opening, flows, summary)
    return save_material_checkpoint(
        checkpoint_dir(tmp_path, fixture.state.completed_ticks),
        fixture.state,
        fixture.network,
        history,
        RngRegistry(fixture.spec.seed),
        metadata,
    )


def _prepare_checkpoint_fixture(fixture):
    fixture.parameters = fixture.parameters.model_copy(
        update={
            "trade": fixture.parameters.trade.model_copy(
                update={"cmea_credit_envelope": 1.0}
            )
        }
    )
    fixture.spec = fixture.spec.model_copy(
        update={"material_parameters": fixture.parameters}
    )
    return fixture


def test_checkpoint_rejects_empty_clearing_sidecar(tmp_path, contract) -> None:
    fixture = _prepare_checkpoint_fixture(_fixture())
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        _forcing(fixture, ticks=5),
        fixture.parameters,
        fixture.network,
    )
    summary = accounting.check_material_invariants(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
    )
    fixture.state.completed_ticks = 1
    path = _save_d3_checkpoint(
        fixture, contract, tmp_path, opening, flows, summary
    )
    (path / CLEARING_PAYLOAD).write_text(
        json.dumps(
            {
                "regime": None,
                "accounts": [],
                "entries": [],
                "transfers": [],
                "settlements": [],
                "event_ids": [],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    _rehash(path)
    with pytest.raises(ResearchGateError, match="all-empty"):
        load_material_checkpoint(path, fixture.spec, contract, fixture.network)


def test_checkpoint_rejects_declared_zero_account_deletion(
    tmp_path, contract
) -> None:
    fixture = _prepare_checkpoint_fixture(_fixture())
    policy = CmeaClearingPolicy(
        term_quarters=1,
        counterparties=(
            CmeaClearingCounterparty(9201, 10.0),
            CmeaClearingCounterparty(9202, 6.0),
            CmeaClearingCounterparty(9203, 0.0),
        ),
        contracts=_contracts(),
        clearing_group=(9201, 9202),
    )
    result = execute_cmea_clearing_tick(
        fixture.state,
        _forcing(fixture, ticks=5),
        fixture.parameters,
        fixture.network,
        regime=_regime_from_policy(policy),
    )
    fixture.state.completed_ticks = 1
    path = save_material_checkpoint(
        checkpoint_dir(tmp_path, fixture.state.completed_ticks),
        fixture.state,
        fixture.network,
        MaterialHistory(),
        RngRegistry(fixture.spec.seed),
        {
            "scenario": fixture.spec.model_dump(mode="json"),
            "region_ids": list(fixture.region_ids),
            "commodity_ids": list(fixture.commodities),
            "baseline_hash": contract.expected_baseline_sha256,
            "last_completed_quarter": str(
                fixture.spec.start.advance(fixture.state.completed_ticks - 1)
            ),
            "next_quarter": str(
                fixture.spec.start.advance(fixture.state.completed_ticks)
            ),
            "source_run_id": "unit-d3",
        },
    )
    payload = json.loads((path / CLEARING_PAYLOAD).read_text(encoding="utf-8"))
    payload["accounts"] = [
        item for item in payload["accounts"] if item["counterparty_id"] != 9203
    ]
    (path / CLEARING_PAYLOAD).write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    _rehash(path)
    with pytest.raises(ResearchGateError, match="declared counterparties are missing"):
        load_material_checkpoint(path, fixture.spec, contract, fixture.network)
    assert result.gate.max_finance_abs_residual <= 1e-9


def test_checkpoint_rejects_deleted_settlement_event(tmp_path, contract) -> None:
    fixture = _prepare_checkpoint_fixture(_fixture())
    policy = _policy()
    first = execute_cmea_clearing_tick(
        fixture.state,
        _forcing(fixture, ticks=5),
        fixture.parameters,
        fixture.network,
        regime=_regime_from_policy(policy),
    )
    settle = CmeaClearingEventSpec(
        event_id="settle-persisted",
        tick=1,
        kind="settle_export",
        entry_id="export:d3-exp@0:energy",
        amount=4.0,
    )
    result = execute_cmea_clearing_tick(
        fixture.state,
        _forcing(fixture, ticks=5),
        fixture.parameters,
        fixture.network,
        regime=_regime_from_policy(policy),
        events=(settle,),
    )
    assert first.flows.cmea_clearing_export_pending == pytest.approx(4.0)
    assert result.observation["flow_scalars"]["export_settled"] == pytest.approx(4.0)
    path = save_material_checkpoint(
        checkpoint_dir(tmp_path, fixture.state.completed_ticks),
        fixture.state,
        fixture.network,
        MaterialHistory(),
        RngRegistry(fixture.spec.seed),
        {
            "scenario": fixture.spec.model_dump(mode="json"),
            "region_ids": list(fixture.region_ids),
            "commodity_ids": list(fixture.commodities),
            "baseline_hash": contract.expected_baseline_sha256,
            "last_completed_quarter": str(
                fixture.spec.start.advance(fixture.state.completed_ticks - 1)
            ),
            "next_quarter": str(
                fixture.spec.start.advance(fixture.state.completed_ticks)
            ),
            "source_run_id": "unit-d3",
        },
    )
    payload = json.loads((path / CLEARING_PAYLOAD).read_text(encoding="utf-8"))
    payload["event_ids"] = [
        item for item in payload["event_ids"] if item != "settle-persisted"
    ]
    (path / CLEARING_PAYLOAD).write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    _rehash(path)
    with pytest.raises(ResearchGateError, match="event log differs"):
        load_material_checkpoint(path, fixture.spec, contract, fixture.network)


def test_checkpoint_rejects_due_tick_and_amount_rewrite(
    tmp_path, contract
) -> None:
    fixture = _prepare_checkpoint_fixture(_fixture())
    policy = _policy()
    execute_cmea_clearing_tick(
        fixture.state,
        _forcing(fixture, ticks=5),
        fixture.parameters,
        fixture.network,
        regime=_regime_from_policy(policy),
    )
    path = save_material_checkpoint(
        checkpoint_dir(tmp_path, fixture.state.completed_ticks),
        fixture.state,
        fixture.network,
        MaterialHistory(),
        RngRegistry(fixture.spec.seed),
        {
            "scenario": fixture.spec.model_dump(mode="json"),
            "region_ids": list(fixture.region_ids),
            "commodity_ids": list(fixture.commodities),
            "baseline_hash": contract.expected_baseline_sha256,
            "last_completed_quarter": str(
                fixture.spec.start.advance(fixture.state.completed_ticks - 1)
            ),
            "next_quarter": str(
                fixture.spec.start.advance(fixture.state.completed_ticks)
            ),
            "source_run_id": "unit-d3",
        },
    )
    original = json.loads((path / CLEARING_PAYLOAD).read_text(encoding="utf-8"))
    payload = copy.deepcopy(original)
    for entry in payload["entries"]:
        if entry["direction"] == "import":
            entry["due_tick"] += 1
    (path / CLEARING_PAYLOAD).write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    _rehash(path)
    with pytest.raises(ResearchGateError, match="term disagrees"):
        load_material_checkpoint(path, fixture.spec, contract, fixture.network)

    payload = copy.deepcopy(original)
    for entry in payload["entries"]:
        if entry["direction"] == "import":
            entry["amount"] = 8.0
    for account in payload["accounts"]:
        if account["counterparty_id"] == 9201:
            account["balance"] = -8.0
    (path / CLEARING_PAYLOAD).write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    _rehash(path)
    with pytest.raises(ResearchGateError, match="quantity x"):
        load_material_checkpoint(path, fixture.spec, contract, fixture.network)


def test_direct_and_adapter_paired_success_match_exactly() -> None:
    direct_fixture = _fixture()
    adapter_fixture = _fixture()
    policy = _policy()
    opening = capture_material_stocks(direct_fixture.state)
    direct_flows = tick_material(
        direct_fixture.state,
        _forcing(direct_fixture, ticks=5),
        direct_fixture.parameters,
        direct_fixture.network,
        cmea_clearing_policy=policy,
    )
    accounting.check_material_invariants(
        opening,
        direct_fixture.state,
        direct_flows,
        direct_fixture.parameters,
        direct_fixture.network,
        forcing=_forcing(direct_fixture, ticks=5),
        cmea_clearing_policy=policy,
    )
    result = execute_cmea_clearing_tick(
        adapter_fixture.state,
        _forcing(adapter_fixture, ticks=5),
        adapter_fixture.parameters,
        adapter_fixture.network,
        regime=_regime_from_policy(policy),
    )
    assert result.gate.max_finance_abs_residual <= 1e-9
    assert result.gate.max_material_abs_residual <= 1e-9
    assert result.flows.journal_kind == direct_flows.journal_kind
    assert result.flows.journal_debit == direct_flows.journal_debit
    assert result.flows.journal_credit == direct_flows.journal_credit
    assert result.flows.journal_amount == pytest.approx(direct_flows.journal_amount)
    assert result.flows.journal_event == direct_flows.journal_event
    adapter_state = adapter_fixture.state
    direct_state = direct_fixture.state
    assert adapter_state.cmea_clearing_accounts == direct_state.cmea_clearing_accounts
    assert adapter_state.cmea_clearing_entries == direct_state.cmea_clearing_entries
    assert adapter_state.cmea_clearing_transfers == direct_state.cmea_clearing_transfers
    assert (
        adapter_state.cmea_clearing_settlements
        == direct_state.cmea_clearing_settlements
    )
    assert adapter_state.cmea_clearing_event_ids == direct_state.cmea_clearing_event_ids
    assert adapter_state.cmea_clearing_regime == direct_state.cmea_clearing_regime
    assert build_account_directory(adapter_fixture.state) == build_account_directory(
        direct_fixture.state
    )
    direct_fixture.state.completed_ticks = 1
    assert canonical_material_bytes(
        adapter_fixture.state, result.flows
    ) == canonical_material_bytes(direct_fixture.state, direct_flows)


# ---------------------------------------------------------------------------
# Causal replay: intermediate quota, transfer causality and global event ids.
# ---------------------------------------------------------------------------


def _causal_policy() -> CmeaClearingPolicy:
    return CmeaClearingPolicy(
        term_quarters=1,
        counterparties=(
            CmeaClearingCounterparty(9201, 10.0),
            CmeaClearingCounterparty(9202, 6.0),
        ),
        contracts=(
            CmeaClearingContract("d3-imp", 9201, "import", "energy", 1.0),
            CmeaClearingContract("d3-exp", 9202, "export", "energy", 1.0),
        ),
        clearing_group=(9201, 9202),
    )


def test_replay_rejects_intermediate_quota_breach() -> None:
    policy = _causal_policy()
    entries = (
        CmeaClearingEntry(
            "import:d3-imp@0", "d3-imp", 9201, "import", "energy", 0, 1, 10.0, 10.0, 0.0
        ),
        CmeaClearingEntry(
            "import:d3-imp@1", "d3-imp", 9201, "import", "energy", 1, 2, 10.0, 10.0, 0.0
        ),
        CmeaClearingEntry(
            "export:d3-exp@0:energy",
            "d3-exp",
            9202,
            "export",
            "energy",
            0,
            1,
            10.0,
            10.0,
            10.0,
        ),
    )
    accounts = (
        CmeaClearingAccount(9201, 10.0, -10.0),
        CmeaClearingAccount(9202, 6.0, 10.0),
    )
    settlement = CmeaClearingSettlement("settle-10", 3, "export:d3-exp@0:energy", 10.0)
    event_ids = (
        "import:d3-imp@0",
        "import:d3-imp@1",
        "export:d3-exp@0:energy",
        "settle-10",
    )
    with pytest.raises(ValueError, match="cumulative credit limit"):
        validate_clearing_book(
            accounts,
            entries,
            (),
            event_ids,
            settlements=(settlement,),
            completed_ticks=4,
            policy=policy,
        )
    # Final-balance arithmetic alone would have accepted: -10 is legal.
    assert accounts[0].balance == -10.0


def test_replay_rejects_transfer_before_confirmed_settlement() -> None:
    policy = _causal_policy()
    entries = (
        CmeaClearingEntry(
            "export:d3-exp@0:energy",
            "d3-exp",
            9202,
            "export",
            "energy",
            0,
            1,
            4.0,
            4.0,
            4.0,
        ),
    )
    accounts = (
        CmeaClearingAccount(9201, 10.0, 4.0),
        CmeaClearingAccount(9202, 6.0, 0.0),
    )
    transfer = CmeaClearingTransfer("transfer-early", 0, 9202, 9201, 4.0)
    settlement = CmeaClearingSettlement("settle-late", 1, "export:d3-exp@0:energy", 4.0)
    event_ids = ("export:d3-exp@0:energy", "transfer-early", "settle-late")
    with pytest.raises(ValueError, match="unconfirmed claim"):
        validate_clearing_book(
            accounts,
            entries,
            (transfer,),
            event_ids,
            settlements=(settlement,),
            completed_ticks=3,
            policy=policy,
        )


def test_replay_rejects_cross_log_duplicate_event_id() -> None:
    policy = _causal_policy()
    entries = (
        CmeaClearingEntry(
            "export:d3-exp@0:energy",
            "d3-exp",
            9202,
            "export",
            "energy",
            0,
            1,
            4.0,
            4.0,
            4.0,
        ),
    )
    accounts = (
        CmeaClearingAccount(9201, 10.0, 4.0),
        CmeaClearingAccount(9202, 6.0, 0.0),
    )
    duplicate = "shared-id"
    transfer = CmeaClearingTransfer(duplicate, 1, 9202, 9201, 4.0)
    settlement = CmeaClearingSettlement(duplicate, 1, "export:d3-exp@0:energy", 4.0)
    event_ids = ("export:d3-exp@0:energy", duplicate)
    with pytest.raises(ValueError, match="globally unique"):
        validate_clearing_book(
            accounts,
            entries,
            (transfer,),
            event_ids,
            settlements=(settlement,),
            completed_ticks=3,
            policy=policy,
        )


def test_replay_enforces_canonical_same_tick_order() -> None:
    policy = CmeaClearingPolicy(
        term_quarters=1,
        counterparties=(CmeaClearingCounterparty(9201, 10.0),),
        contracts=(
            CmeaClearingContract("d3-imp", 9201, "import", "energy", 1.0),
            CmeaClearingContract("d3-exp", 9201, "export", "energy", 1.0),
        ),
    )
    entry = CmeaClearingEntry(
        "export:d3-exp@0:energy",
        "d3-exp",
        9201,
        "export",
        "energy",
        0,
        1,
        10.0,
        10.0,
        10.0,
    )
    settlement = CmeaClearingSettlement(
        "settle-10", 1, "export:d3-exp@0:energy", 10.0
    )
    canonical_import = CmeaClearingEntry(
        "import:d3-imp@1",
        "d3-imp",
        9201,
        "import",
        "energy",
        1,
        2,
        10.0,
        10.0,
        0.0,
    )
    accounts = (CmeaClearingAccount(9201, 10.0, 0.0),)
    # Canonical live order: import first at tick 1, then settlement.
    validate_clearing_book(
        accounts,
        (entry, canonical_import),
        (),
        ("export:d3-exp@0:energy", "import:d3-imp@1", "settle-10"),
        settlements=(settlement,),
        completed_ticks=3,
        policy=policy,
    )

    # A reordered sidecar lets the same-tick settlement fund the import.
    over_quota = CmeaClearingEntry(
        "import:d3-imp@1",
        "d3-imp",
        9201,
        "import",
        "energy",
        1,
        2,
        20.0,
        20.0,
        0.0,
    )
    reordered_accounts = (CmeaClearingAccount(9201, 10.0, -10.0),)
    with pytest.raises(ValueError, match="canonical same-tick order"):
        validate_clearing_book(
            reordered_accounts,
            (entry, over_quota),
            (),
            ("export:d3-exp@0:energy", "settle-10", "import:d3-imp@1"),
            settlements=(settlement,),
            completed_ticks=3,
            policy=policy,
        )
