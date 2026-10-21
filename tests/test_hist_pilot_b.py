"""H4C Pilot B: runner gates and real D1/D2/D3 tiny boundaries."""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from hsm_lab.contract.base import ConfigError, ResearchGateError
from hsm_lab.institutions.cmea_clearing_adapter import (
    CmeaClearingEventSpec,
    CmeaClearingRegime,
    execute_cmea_clearing_tick,
)
from hsm_lab.institutions.export_receivables_adapter import (
    ExportReceivableEventSpec,
    ExportReceivableFailure,
    ExportReceivablesRegime,
    execute_export_receivables_tick,
)
from hsm_lab.institutions.trade_working_capital_adapter import (
    TradeWorkingCapitalBook,
    TradeWorkingCapitalRegime,
    execute_trade_working_capital_tick,
)
from tests.test_hist_export_finance import _forcing, _legacy_export_fixture
from tests.test_material import Fixture

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "studies/HIST_VNEXT/pilot_B/runner.py"
SPEC_PATH = ROOT / "studies/HIST_VNEXT/pilot_B/spec.json"


def _load_runner():
    spec = importlib.util.spec_from_file_location("h4c_pilot_b_runner", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


def _repo_output(label: str) -> Path:
    base = ROOT / "outputs"
    base.mkdir(exist_ok=True)
    return base / f"pytest-h4c-{label}-{uuid.uuid4().hex}"


def _d1_regime(
    *,
    limit: float = 4.0,
    term: int = 1,
    start: int = 0,
    end: int = 0,
    bank: int = 0,
) -> TradeWorkingCapitalRegime:
    return TradeWorkingCapitalRegime(
        schema_version="hist-trade-working-capital-regime-v1",
        regime_id="limited_trade_working_capital",
        source_kind="synthetic",
        bank_index=bank,
        credit_limit=limit,
        annual_rate=0.04,
        term_quarters=term,
        draw_tick_start=start,
        draw_tick_end=end,
    )


def _d2_regime(term: int = 1) -> ExportReceivablesRegime:
    return ExportReceivablesRegime(
        schema_version="hist-export-receivables-regime-v1",
        regime_id="export_receivables",
        source_kind="synthetic",
        term_quarters=term,
        contracts=(
            {
                "contract_id": "h4c-usd-energy",
                "currency": "USD",
                "buyer_id": 9101,
                "seller_id": 0,
                "commodity_id": "energy",
            },
            {
                "contract_id": "h4c-cmea-energy",
                "currency": "cmea_settlement_unit",
                "buyer_id": 9102,
                "seller_id": 0,
                "commodity_id": "energy",
            },
        ),
    )


def _d3_regime(*, quota: float = 10.0, term: int = 1, price: float = 1.0):
    return CmeaClearingRegime(
        schema_version="hist-cmea-clearing-regime-v1",
        regime_id="cmea_clearing",
        source_kind="synthetic",
        term_quarters=term,
        clearing_group=(9201,),
        counterparties=({"counterparty_id": 9201, "credit_limit": quota},),
        contracts=(
            {
                "contract_id": "h4c-cmea-import",
                "counterparty_id": 9201,
                "direction": "import",
                "commodity_id": "energy",
                "price": price,
            },
            {
                "contract_id": "h4c-cmea-export",
                "counterparty_id": 9201,
                "direction": "export",
                "commodity_id": "energy",
                "price": price,
            },
        ),
    )


def _run_d1(
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


def _run_d2(
    fixture: Fixture,
    regime: ExportReceivablesRegime,
    *,
    events: tuple[ExportReceivableEventSpec, ...] = (),
    ticks: int = 8,
):
    return execute_export_receivables_tick(
        fixture.state,
        _forcing(fixture, ticks=ticks),
        fixture.parameters,
        fixture.network,
        regime=regime,
        events=events,
    )


def _run_d3(
    fixture: Fixture,
    regime: CmeaClearingRegime,
    *,
    events: tuple[CmeaClearingEventSpec, ...] = (),
    ticks: int = 8,
):
    return execute_cmea_clearing_tick(
        fixture.state,
        _forcing(fixture, ticks=ticks),
        fixture.parameters,
        fixture.network,
        regime=regime,
        events=events,
    )


def _assert_gate(result) -> None:
    assert result.gate.max_material_abs_residual <= 1e-9
    assert result.gate.max_finance_abs_residual <= 1e-9


# ---------------------------------------------------------------------------
# tiny4q: real D1 interface witness (P02 fixture, not an F2 pilot result)
# ---------------------------------------------------------------------------


def test_tiny4q_d1_lends_only_against_real_export_outlay() -> None:
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    result = _run_d1(fixture, _d1_regime(limit=4.0))
    _assert_gate(result)

    assert result.flows.treasury_loan_drawn == pytest.approx(4.0)
    assert result.flows.treasury_export_outlay == pytest.approx(4.0)
    assert result.book.principal == pytest.approx(4.0)
    assert [(batch.draw_tick, batch.maturity_tick) for batch in result.book.batches] == [
        (0, 1)
    ]
    assert result.flows.cmea_exports.sum() == pytest.approx(2.0)
    assert result.flows.convertible_exports.sum() == pytest.approx(2.0)

    zero_limit = _legacy_export_fixture(treasury=0.0, stock=8.0)
    no_draw = _run_d1(zero_limit, _d1_regime(limit=0.0))
    _assert_gate(no_draw)
    assert no_draw.flows.treasury_loan_drawn == 0.0

    no_stock = _legacy_export_fixture(treasury=0.0, stock=0.0)
    no_material = _run_d1(no_stock, _d1_regime(limit=4.0))
    _assert_gate(no_material)
    assert no_material.flows.treasury_loan_drawn == 0.0
    assert no_material.flows.treasury_export_outlay == 0.0

    no_demand = _legacy_export_fixture(treasury=0.0, stock=8.0)
    trade = no_demand.parameters.trade.model_copy(
        update={
            "cmea_export_demands": [0.0] * 8,
            "convertible_export_demands": [0.0] * 8,
        }
    )
    no_demand.parameters = no_demand.parameters.model_copy(update={"trade": trade})
    no_loan = _run_d1(no_demand, _d1_regime(limit=4.0))
    _assert_gate(no_loan)
    assert no_loan.flows.treasury_loan_drawn == 0.0


def test_tiny4q_d1_draw_is_the_funding_gap_and_is_capped() -> None:
    fixture = _legacy_export_fixture(treasury=2.0, stock=8.0)
    result = _run_d1(fixture, _d1_regime(limit=4.0))
    _assert_gate(result)
    assert result.flows.treasury_loan_drawn == pytest.approx(2.0)
    assert result.flows.treasury_export_outlay == pytest.approx(4.0)

    capped = _legacy_export_fixture(treasury=0.0, stock=8.0)
    limited = _run_d1(capped, _d1_regime(limit=1.0))
    _assert_gate(limited)
    assert limited.flows.treasury_loan_drawn == pytest.approx(1.0)
    assert limited.observation["draw_sizing"]["limit_remaining"] == pytest.approx(1.0)

    window = _legacy_export_fixture(treasury=0.0, stock=8.0)
    closed = _run_d1(window, _d1_regime(limit=4.0, start=1, end=1))
    _assert_gate(closed)
    assert closed.flows.treasury_loan_drawn == 0.0


def test_tiny4q_zero_usd_financing_and_no_reserve_imports_nothing() -> None:
    fixture = _legacy_export_fixture(
        treasury=4.0, stock=8.0, usd_reserve=0.0, usd_import_quantity=5.0
    )
    result = _run_d1(fixture, _d1_regime(limit=0.0))
    _assert_gate(result)
    assert result.flows.usd_loan_drawn == 0.0
    assert result.flows.usd_import_payment == 0.0
    assert result.flows.convertible_imports.sum() == 0.0


def test_tiny4q_usd_draw_equals_the_import_gap_under_the_limit() -> None:
    fixture = _legacy_export_fixture(
        treasury=4.0, stock=8.0, usd_reserve=0.0, usd_import_quantity=5.0
    )
    trade = fixture.parameters.trade.model_copy(
        update={"convertible_loan_limit": 10.0}
    )
    fixture.parameters = fixture.parameters.model_copy(update={"trade": trade})
    result = _run_d1(fixture, _d1_regime(limit=0.0))
    _assert_gate(result)
    # One unit per model unit, desired 5, reserve 0: the draw is the full gap.
    assert result.flows.usd_loan_drawn == pytest.approx(5.0)
    assert result.flows.usd_import_payment == pytest.approx(5.0)

    no_request = _legacy_export_fixture(
        treasury=4.0, stock=8.0, usd_reserve=0.0, usd_import_quantity=0.0
    )
    trade = no_request.parameters.trade.model_copy(
        update={"convertible_loan_limit": 10.0}
    )
    no_request.parameters = no_request.parameters.model_copy(update={"trade": trade})
    quiet = _run_d1(no_request, _d1_regime(limit=0.0))
    _assert_gate(quiet)
    assert quiet.flows.usd_loan_drawn == 0.0


def test_tiny4q_trace_used_excludes_unmapped_household_cells() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    result = _run_d1(fixture, _d1_regime(limit=0.0))
    _assert_gate(result)
    outcomes = runner._commodity_outcomes(
        fixture.state, result.flows, fixture.network
    )
    g = fixture.g("energy")
    demand = fixture.network.demand_cell
    cell_commodity = fixture.network.cell_commodity
    valid = demand >= 0
    expected = float(
        result.flows.used[valid & (cell_commodity[demand] == g)].sum()
    )
    for channel in range(2):
        cell = int(fixture.network.export_demand_cell[channel, g])
        if cell >= 0:
            expected += float(result.flows.used[cell])
    assert outcomes["energy"]["used"] == pytest.approx(expected)
    # A naive bincount includes demand cells with destination -1 and would
    # silently assign household rows to the last commodity cell.
    naive = float(result.flows.used[cell_commodity[demand] == g].sum())
    assert naive != pytest.approx(expected)


def test_tiny4q_adapter_failure_restores_state_and_clock() -> None:
    fixture = _legacy_export_fixture(treasury=0.0, stock=8.0)
    before = copy.deepcopy(fixture.state)
    with pytest.raises(ResearchGateError, match="bank_index"):
        _run_d1(fixture, _d1_regime(limit=4.0, bank=1))
    assert fixture.state.completed_ticks == before.completed_ticks
    assert fixture.state.treasury_deposit == before.treasury_deposit
    assert fixture.state.stock_value.tolist() == before.stock_value.tolist()


# ---------------------------------------------------------------------------
# tiny4q: real D2 receivables and the study's receipt-arrival rule
# ---------------------------------------------------------------------------


def test_tiny4q_d2_delivery_opens_receivables_and_delay_creates_overdue() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    first = _run_d2(fixture, _d2_regime(term=1))
    _assert_gate(first)
    assert first.flows.export_receivable_opened_usd == pytest.approx(6.0)
    assert first.flows.export_receivable_opened_cmea == pytest.approx(2.0)
    assert fixture.state.usd_reserve == 0.0

    # Study rule: receipt arrives at due_tick + 2, never before due_tick.
    events_tick1 = runner._d2_events(
        fixture.state, episode_id="pre75", arm_name="r_receipt_delay2",
        receipt_delay_quarters=2,
    )
    assert events_tick1 == ()
    second = _run_d2(fixture, _d2_regime(term=1), events=events_tick1)
    _assert_gate(second)
    assert second.flows.export_receivable_overdue_usd == 0.0
    assert second.flows.export_receivable_overdue_cmea == 0.0
    assert fixture.state.usd_reserve == 0.0

    events_tick2 = runner._d2_events(
        fixture.state, episode_id="pre75", arm_name="r_receipt_delay2",
        receipt_delay_quarters=2,
    )
    assert events_tick2 == ()
    third = _run_d2(fixture, _d2_regime(term=1), events=events_tick2)
    _assert_gate(third)
    assert third.flows.export_receivable_received_usd == 0.0
    assert third.flows.export_receivable_overdue_usd == pytest.approx(6.0)
    assert third.flows.export_receivable_overdue_cmea == pytest.approx(2.0)

    events_tick3 = runner._d2_events(
        fixture.state, episode_id="pre75", arm_name="r_receipt_delay2",
        receipt_delay_quarters=2,
    )
    assert {event.receivable_id for event in events_tick3}
    fourth = _run_d2(fixture, _d2_regime(term=1), events=events_tick3)
    _assert_gate(fourth)
    assert fourth.flows.export_receivable_received_usd == pytest.approx(6.0)
    assert fourth.flows.export_receivable_received_cmea == pytest.approx(2.0)
    assert fixture.state.usd_reserve == pytest.approx(6.0)
    assert fixture.state.cmea_settlement_balance == pytest.approx(2.0)
    assert fourth.observation["identity_residuals"] == {
        "principal_closure": 0.0,
        "provision_closure": 0.0,
        "cash_closure": 0.0,
    }
    for lot in fixture.state.export_receivables:
        assert lot.gross == 0.0
        assert lot.gross + lot.received + lot.written_off == pytest.approx(lot.principal)
    # gross is the engine's outstanding principal, so the plan's gross rule
    # does not create a second receipt for an already-collected lot.
    assert runner._d2_events(
        fixture.state,
        episode_id="pre75",
        arm_name="r_receipt_delay2",
        receipt_delay_quarters=2,
    ) == ()
    summary = runner._state_summary(fixture.state, book=None)
    assert summary["d2_lots"]
    assert all(item["outstanding"] == 0.0 for item in summary["d2_lots"])


def test_tiny4q_d2_term_zero_is_rejected_by_the_schema() -> None:
    with pytest.raises(ValidationError):
        _d2_regime(term=0)


def test_tiny4q_d2_early_receipt_is_permitted_by_the_interface_only() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run_d2(fixture, _d2_regime(term=2))
    early = ExportReceivableEventSpec(
        event_id="early",
        tick=1,
        kind="receipt",
        receivable_id="h4c-usd-energy@0:energy",
        contract_id="h4c-usd-energy",
        currency="USD",
        buyer_id=9101,
        seller_id=0,
        amount=6.0,
    )
    result = _run_d2(fixture, _d2_regime(term=2), events=(early,))
    _assert_gate(result)
    assert result.flows.export_receivable_received_usd == pytest.approx(6.0)
    # The study rule would not emit this event before due_tick; the adapter
    # itself permits a legal early payment and is not misreported as stricter.
    assert result.observation["overdue"] == []


def test_tiny4q_d2_failure_restores_state() -> None:
    fixture = _legacy_export_fixture(treasury=4.0, stock=8.0)
    _run_d2(fixture, _d2_regime(term=1))
    before = copy.deepcopy(fixture.state)
    with pytest.raises(ExportReceivableFailure):
        _run_d2(
            fixture,
            _d2_regime(term=1),
            events=(
                ExportReceivableEventSpec(
                    event_id="too-much",
                    tick=1,
                    kind="receipt",
                    receivable_id="h4c-usd-energy@0:energy",
                    contract_id="h4c-usd-energy",
                    currency="USD",
                    buyer_id=9101,
                    seller_id=0,
                    amount=99.0,
                ),
            ),
        )
    assert fixture.state.completed_ticks == before.completed_ticks
    assert fixture.state.export_receivables == before.export_receivables


# ---------------------------------------------------------------------------
# tiny4q: real D3 cumulative quota and settlement timing
# ---------------------------------------------------------------------------


def test_tiny4q_d3_quota_is_cumulative_and_exhausts_on_the_sixth_call() -> None:
    fixture = _legacy_export_fixture(
        treasury=4.0, stock=8.0, cmea_import_quantity=2.0
    )
    regime = _d3_regime(quota=10.0, term=1, price=1.0)
    for _ in range(5):
        result = _run_d3(fixture, regime)
        _assert_gate(result)
        assert result.flows.cmea_imports[fixture.g("energy")] == pytest.approx(2.0)
    assert fixture.state.cmea_clearing_accounts[0].balance == pytest.approx(-10.0)
    assert fixture.state.cmea_clearing_accounts[0].credit_limit == pytest.approx(10.0)

    exhausted = _run_d3(fixture, regime)
    _assert_gate(exhausted)
    assert exhausted.flows.cmea_imports[fixture.g("energy")] == 0.0
    assert exhausted.flows.cmea_clearing_import_payment == 0.0
    assert len(
        [entry for entry in fixture.state.cmea_clearing_entries if entry.direction == "import"]
    ) == 5


def test_tiny4q_d3_zero_quota_never_imports_or_borrows_elsewhere() -> None:
    fixture = _legacy_export_fixture(
        treasury=4.0, stock=8.0, cmea_import_quantity=2.0
    )
    result = _run_d3(fixture, _d3_regime(quota=0.0))
    _assert_gate(result)
    assert result.flows.cmea_imports[fixture.g("energy")] == 0.0
    assert result.flows.usd_import_payment == 0.0
    assert result.flows.cmea_clearing_import_payment == 0.0


def test_tiny4q_d3_frozen_price_and_same_tick_settlement_limits() -> None:
    fixture = _legacy_export_fixture(
        treasury=4.0, stock=8.0, cmea_import_quantity=2.0
    )
    result = _run_d3(fixture, _d3_regime(quota=10.0, term=2, price=1.0))
    _assert_gate(result)
    assert result.flows.cmea_clearing_import_payment == pytest.approx(2.0)
    assert result.flows.cmea_clearing_export_pending > 0.0
    assert fixture.state.cmea_settlement_balance == 0.0

    export_entry = next(
        entry
        for entry in fixture.state.cmea_clearing_entries
        if entry.direction == "export"
    )
    assert export_entry.due_tick == 2
    before = copy.deepcopy(fixture.state)
    with pytest.raises(ResearchGateError, match="before its due tick"):
        _run_d3(
            fixture,
            _d3_regime(quota=10.0, term=2, price=1.0),
            events=(
                CmeaClearingEventSpec(
                    event_id="early-settle",
                    tick=1,
                    kind="settle_export",
                    entry_id=export_entry.entry_id,
                    amount=float(export_entry.amount),
                ),
            ),
        )
    assert fixture.state.completed_ticks == before.completed_ticks
    assert fixture.state.cmea_clearing_entries == before.cmea_clearing_entries


def test_tiny4q_d3_event_ids_use_the_plan_kind() -> None:
    fixture = _legacy_export_fixture(
        treasury=4.0, stock=8.0, cmea_import_quantity=2.0
    )
    regime = _d3_regime(quota=10.0, term=1, price=1.0)
    _run_d3(fixture, regime)  # tick 0 delivery; export due tick 1
    _run_d3(fixture, regime)  # tick 1: due, no event yet
    events = runner._d3_events(
        fixture.state, episode_id="pre75", arm_name="c"
    )
    assert len(events) == 1
    event = events[0]
    assert event.kind == "settle_export"
    assert ":settle_export:" in event.event_id
    assert event.entry_id is not None
    result = _run_d3(fixture, regime, events=events)
    _assert_gate(result)
    assert result.flows.cmea_clearing_events[0].event_id == event.event_id


def test_tiny4q_d3_import_obligation_is_not_extinguished_by_export_settlement() -> None:
    fixture = _legacy_export_fixture(
        treasury=4.0, stock=8.0, cmea_import_quantity=2.0
    )
    _run_d3(fixture, _d3_regime(quota=10.0, price=1.0))
    imports = [
        entry for entry in fixture.state.cmea_clearing_entries if entry.direction == "import"
    ]
    assert imports and all(entry.settled == 0.0 for entry in imports)
    # The adapter has no import-obligation extinguishment; the study must keep
    # this row as NOT_IMPLEMENTED rather than call an export settlement payment.
    row = next(
        item
        for item in runner._NOT_RUN
        if item["id"] == "d2_import_obligation_extinguishment"
    )
    assert row["status"] == "NOT_IMPLEMENTED"


# ---------------------------------------------------------------------------
# Runner gates and the full paired design
# ---------------------------------------------------------------------------


def _assert_rejected(*args: str) -> None:
    output = _repo_output("rejected")
    try:
        code = runner.main(
            [
                "--root",
                str(ROOT),
                "--spec",
                str(SPEC_PATH),
                "--output-dir",
                str(output),
                *args,
            ]
        )
        assert code == 2
        assert not output.exists()
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_runner_rejects_invalid_windows_arms_and_existing_output() -> None:
    window_output = _repo_output("bad-window")
    try:
        with pytest.raises(SystemExit) as caught:
            runner.main(
                [
                    "--root",
                    str(ROOT),
                    "--spec",
                    str(SPEC_PATH),
                    "--output-dir",
                    str(window_output),
                    "--window-ticks",
                    "5",
                ]
            )
        assert caught.value.code == 2
        assert not window_output.exists()
    finally:
        shutil.rmtree(window_output, ignore_errors=True)

    _assert_rejected("--arm", "unknown")
    _assert_rejected("--arm", "base", "--arm", "base")

    output = _repo_output("exists")
    output.mkdir()
    try:
        code = runner.main(
            [
                "--root",
                str(ROOT),
                "--spec",
                str(SPEC_PATH),
                "--output-dir",
                str(output),
            ]
        )
        assert code == 2
    finally:
        shutil.rmtree(output, ignore_errors=True)

    with pytest.raises(ConfigError):
        runner.run_pilot(
            ROOT,
            spec_path=SPEC_PATH,
            output_dir=Path("../escape"),
            window_ticks=4,
        )

    empty_output = _repo_output("empty-selection")
    try:
        with pytest.raises(ConfigError, match="empty"):
            runner.run_pilot(
                ROOT,
                spec_path=SPEC_PATH,
                output_dir=empty_output,
                window_ticks=4,
                arms_override=[],
            )
        assert not empty_output.exists()
    finally:
        shutil.rmtree(empty_output, ignore_errors=True)


@pytest.fixture(scope="module")
def full_run():
    base = Path(tempfile.mkdtemp(dir=ROOT / "outputs", prefix="pytest-h4c-full-"))
    output = base / "pilot"
    try:
        manifest = runner.run_pilot(
            ROOT, spec_path=SPEC_PATH, output_dir=output, window_ticks=4
        )
        yield {"output": output, "manifest": manifest}
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_full_4q_declares_all_arms_and_episodes(full_run) -> None:
    manifest = full_run["manifest"]
    assert manifest["status"] == "COMPLETED"
    assert manifest["window_ticks"] == 4
    assert manifest["arms_executed"] == list(runner._ARMS)
    assert set(manifest["episodes"]) == {"pre75", "post75"}
    assert manifest["episodes"]["pre75"]["start_quarter"] == "1973Q1"
    assert manifest["episodes"]["pre75"]["end_quarter"] == "1973Q4"
    assert manifest["episodes"]["post75"]["start_quarter"] == "1975Q1"
    assert manifest["episodes"]["post75"]["end_quarter"] == "1975Q4"
    assert manifest["runtime"]["trace_rows"] == 160
    assert manifest["verdicts"]["historical"] == "NOT_ESTABLISHED"
    assert manifest["usd_limit_probe"]["status"] == "PASS_ZERO_DRAW"


def test_full_4q_placebo_matches_base_and_branch_is_shared(full_run) -> None:
    manifest = full_run["manifest"]
    rows = [
        json.loads(line)
        for line in (full_run["output"] / "trace.jsonl").read_text().splitlines()
    ]
    for episode_id, episode in manifest["episodes"].items():
        base = episode["arms"]["base"]
        placebo = episode["arms"]["placebo"]
        assert placebo["comparison_trace_sha256"] == base["comparison_trace_sha256"]
        assert placebo["final_ledger_sha256"] == base["final_ledger_sha256"]
        first_by_arm = {}
        for row in rows:
            if row["episode_id"] != episode_id:
                continue
            first_by_arm.setdefault(row["arm"], row)
        assert len(first_by_arm) == len(runner._ARMS)
        first = next(iter(first_by_arm.values()))
        common = (
            "oil_price",
            "global_usd_rate",
            "raw_cmea_quote",
            "segment",
            "price_index_version",
        )
        for row in first_by_arm.values():
            assert {key: row["forcing"][key] for key in common} == {
                key: first["forcing"][key] for key in common
            }
            assert row["tick"] == first["tick"]
        for row in rows:
            if row["episode_id"] != episode_id or row["arm"] != "base":
                continue
            for channel in ("cmea_export", "convertible_export"):
                channel_row = row["trade_channels"][channel]
                assert channel_row["status"] == "DEMAND_CELL"
                assert channel_row["desired"] == pytest.approx(2.0)
                assert channel_row["ordered"] == pytest.approx(2.0)
                assert channel_row["delivered"] == pytest.approx(0.0)
                assert channel_row["physical_delivery_blocked"] == pytest.approx(2.0)


def test_full_4q_reports_real_first_stage_and_household_null(full_run) -> None:
    manifest = full_run["manifest"]
    for episode in manifest["episodes"].values():
        for arm_name in ("w", "w_term2"):
            stage = episode["arms"][arm_name]["short_window"]["first_stage"]
            assert stage["W_treasury_loan_drawn"] == 0.0
            assert stage["W_treasury_export_outlay"] == 0.0
        for arm_name in ("r", "r_term2", "r_receipt_delay2"):
            stage = episode["arms"][arm_name]["short_window"]["first_stage"]
            assert stage["R_opened_usd"] == 0.0
            assert stage["R_opened_cmea"] == 0.0
        c_stage = episode["arms"]["c"]["short_window"]["first_stage"]
        assert c_stage["C_import_quantity_g02"] > 0
        assert c_stage["C_quota_remaining"] == pytest.approx(2.0)
        assert c_stage["C_quota_used"] == pytest.approx(8.0)
        assert episode["arms"]["s"]["short_window"]["first_stage"]["S_bailout_granted"] > 0
        for arm in episode["arms"].values():
            g02 = arm["short_window"]["by_commodity"]["g02_oil_gas_fuels"]
            assert set(g02) == {
                "production",
                "desired",
                "ordered",
                "delivered",
                "used",
                "physical_delivery_blocked",
                "financial_delivery_blocked",
                "imports",
                "cmea_imports",
                "convertible_imports",
                "exports",
                "cmea_exports",
                "convertible_exports",
                "household_realized",
                "household_availability_unmet",
                "household_budget_unmet",
                "stock_close",
            }
            assert all(math.isfinite(value) for value in g02.values())


def test_full_4q_stock_is_end_of_window_not_a_sum(full_run) -> None:
    manifest = full_run["manifest"]
    rows = [
        json.loads(line)
        for line in (full_run["output"] / "trace.jsonl").read_text().splitlines()
    ]
    for episode_id, episode in manifest["episodes"].items():
        start = int(episode["start_tick"])
        for arm in ("base", "c", "s"):
            short = [
                row
                for row in rows
                if row["episode_id"] == episode_id
                and row["arm"] == arm
                and start <= row["tick"] < start + 4
            ]
            assert len(short) == 4
            summary_stock = episode["arms"][arm]["short_window"]["by_commodity"][
                "g02_oil_gas_fuels"
            ]["stock_close"]
            assert summary_stock == short[-1]["outcomes"]["g02_oil_gas_fuels"]["stock_close"]
            assert summary_stock != sum(
                row["outcomes"]["g02_oil_gas_fuels"]["stock_close"] for row in short
            )


def test_full_4q_repeat_reverse_and_single_arm_are_identical(full_run) -> None:
    full = full_run["manifest"]
    subset = ["base", "placebo", "c"]
    outputs = {}
    try:
        for label, arms in (
            ("repeat", subset),
            ("reverse", list(reversed(subset))),
            ("single", ["c"]),
        ):
            output = _repo_output(label)
            manifest = runner.run_pilot(
                ROOT,
                spec_path=SPEC_PATH,
                output_dir=output,
                window_ticks=4,
                arms_override=arms,
            )
            outputs[label] = (output, manifest)
            assert manifest["status"] == "PARTIAL"

        for episode_id in ("pre75", "post75"):
            for arm in subset:
                expected = full["episodes"][episode_id]["arms"][arm]
                for label in ("repeat", "reverse"):
                    actual = outputs[label][1]["episodes"][episode_id]["arms"][arm]
                    assert actual["trace_sha256"] == expected["trace_sha256"]
                    assert actual["final_ledger_sha256"] == expected["final_ledger_sha256"]
            single = outputs["single"][1]["episodes"][episode_id]["arms"]["c"]
            expected_c = full["episodes"][episode_id]["arms"]["c"]
            assert single["trace_sha256"] == expected_c["trace_sha256"]
            assert single["final_ledger_sha256"] == expected_c["final_ledger_sha256"]

        repeat_trace = (outputs["repeat"][0] / "trace.jsonl").read_text()
        full_trace = (full_run["output"] / "trace.jsonl").read_text()
        def keyed(text: str) -> list[tuple[tuple[str, str, int], str]]:
            rows = []
            for line in text.splitlines():
                payload = json.loads(line)
                if payload["arm"] not in subset:
                    continue
                key = (payload["episode_id"], payload["arm"], payload["tick"])
                rows.append((key, line))
            return sorted(rows)

        assert keyed(repeat_trace) == keyed(full_trace)
    finally:
        for output, _manifest in outputs.values():
            shutil.rmtree(output, ignore_errors=True)
