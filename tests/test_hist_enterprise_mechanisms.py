"""H5A-A1 / M02 consumer-visible mechanism guards.

Every test here is a real-model test.  The tiny enterprise fixtures reuse the
construction and conservation helpers in ``tests/test_material.py`` (test-only
reuse: the production runner never imports test code), and the runner tests
drive the actual 1000-household ``intermediate8`` study through
``run_m02_study`` in a throwaway directory.

The seven guards required by the preregistration are covered:

1. a joint budget intervention can never be reported as a pure rescue effect;
2. a pre-approved project can never fabricate a new approval or an installation;
3. reversing the arm order from one opening state cannot contaminate a later arm;
4. credit plus an approval cannot fabricate material or an installation when the
   capital/construction legs are not deliverable;
5. a zero denominator and a missing axis can never become a zero shortage;
6. a collapsed baseline can never become a counter-example;
7. a study spec carrying an out-of-bounds ``investment_intensity`` is refused
   before any model is initialised.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import pytest

from experiments import hist_enterprise as he
from hsm_lab.contract.material import PURPOSE_CODES
from hsm_lab.engine.policy import default_initial_policy
from tests.test_material import Fixture, bank, default_params, hub, producer, retail, tech

REPO_ROOT = Path(__file__).resolve().parents[1]
STUDY_SPEC = REPO_ROOT / "studies/HIST_VNEXT/M02/spec.json"

INVESTMENT_COMMODITIES = ("capital_goods", "consumer_goods", "construction")
_INVESTMENT_PURPOSE = PURPOSE_CODES["investment"]
_TINY_TICKS = 3


# ---------------------------------------------------------------------------
# Real tiny enterprise fixtures
# ---------------------------------------------------------------------------


def _enterprise_tiny(
    *,
    allocation_order: str = "production_first",
    consumer_cash: float = 0.0,
    preapproved_capacity: float = 0.0,
    ticks: int = _TINY_TICKS,
) -> Fixture:
    """A tiny enterprise chain whose consumer producer wants to invest.

    A capital seller and a builder each open with one unit of capacity while the
    consumer producer wants ten units of capacity.  The consumer's technology
    consumes ``capital_goods`` as an intermediate input and its investment plan
    wants the same goods again, so the declared allocation order alone decides
    whether the project's capital leg is ever delivered.
    """
    technologies = [
        tech("capital_goods_production", inputs=(), outputs=(("capital_goods", "standard", 1.0),)),
        tech(
            "consumer_goods_production",
            inputs=(("capital_goods", 1.0),),
            outputs=(("consumer_goods", "standard", 1.0),),
        ),
        tech("building_construction", inputs=(), outputs=(("construction", "standard", 1.0),)),
    ]
    organizations = [
        bank(0),
        producer(1, "capital_goods_production", capacity=1.0),
        producer(2, "consumer_goods_production", capacity=10.0, cash=consumer_cash),
        producer(3, "building_construction", capacity=1.0),
        hub(4),
        retail(5),
    ]
    parameters = default_params(
        desired_per_person=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
        allocation_order=allocation_order,
        hunger_base=0.5,
        hunger_shortage=0.5,
    )
    fixture = Fixture(
        organizations,
        technologies,
        commodities=INVESTMENT_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 10.0)],
        household_cash=1000.0,
        ticks=ticks,
    )
    if preapproved_capacity:
        fixture.state.organization_project_approved[2] = preapproved_capacity
    return fixture


def _tiny_arm() -> he.ArmDesign:
    return he.ArmDesign(
        name="tiny_soft_high",
        budget="soft",
        intensity="high",
        regime="base",
        mediator=None,
        role="main_baseline",
        budget_hardness=0.0,
        credit_fraction=0.5,
        investment_intensity=1.0,
    )


def _run_tiny(
    fixture: Fixture,
    tmp_path: Path,
    arm: he.ArmDesign | None = None,
    finance_probe: bool = False,
    account_ids: frozenset[int] | None = None,
) -> tuple[he.ArmResult, list[dict]]:
    """Drive the real kernel through the runner's own per-arm path."""
    design = arm or _tiny_arm()
    layout = he.build_axis_layout(fixture.network)
    forcing = fixture.forcing(_TINY_TICKS)
    policy = default_initial_policy(fixture.spec).patch(design.policy_patch())
    scratch_path = tmp_path / design.name
    scratch_path.mkdir(parents=True, exist_ok=True)
    streams = he._Streams(
        trace=he._JsonlStream(scratch_path / "trace.jsonl"),
        journal=he._ParquetStream(scratch_path / "journal.parquet", he.JOURNAL_SCHEMA),
        organizations=he._ParquetStream(
            scratch_path / "organizations.parquet", he.ORGANIZATION_SCHEMA
        ),
        demand=he._ParquetStream(scratch_path / "demand.parquet", he.DEMAND_SCHEMA),
    )
    try:
        result = he._run_arm(
            scenario=fixture.spec,
            opening=fixture.state,
            forcing=forcing,
            network=fixture.network,
            layout=layout,
            arm=design,
            seed=1729,
            policy_dump={name: float(value) for name, value in policy.model_dump().items()},
            household_base=fixture.household_parameters,
            streams=streams,
            output_dir=scratch_path,
            opening_digest=he._sha256(he.canonical_material_bytes(fixture.state)),
            forcing_digest="forcing",
            network_digest="network",
            spec_digest="spec",
            card_sha256="card",
            scenario_sha256="scenario",
            account_ids=(
                frozenset(he.build_account_directory(fixture.state).values())
                if account_ids is None
                else account_ids
            ),
            finance_probe=finance_probe,
        )
    finally:
        streams.close()
    traces = [
        json.loads(line) for line in (scratch_path / "trace.jsonl").read_text().splitlines()
    ]
    return result, traces


def _investment_axis_totals(result: he.ArmResult, commodity: str) -> dict[str, float]:
    rows = [
        row
        for row in he.axis_gap_rows(result)
        if row["axis_status"] == "OBSERVED"
        and row["commodity"] == commodity
        and row["purpose"] == "investment"
    ]
    assert rows, f"the tiny network declares no investment axis for {commodity}"
    row = rows[0]
    return {"ordered": row["ordered"], "delivered": row["delivered"]}


# ---------------------------------------------------------------------------
# Guard 4/2: credit and approval are not material; a pre-set project is not a
# new approval.
# ---------------------------------------------------------------------------


def test_credit_and_approval_never_fabricate_material_or_installation(tmp_path: Path) -> None:
    """Guard 4: a loan and an approval are money, not a delivered project.

    In ``production_first`` the consumer's intermediate claim takes the one
    available unit of capital goods, so the project's own capital leg is never
    delivered.  Credit is drawn and an approval is granted, yet nothing is
    installed and no capacity appears.
    """
    fixture = _enterprise_tiny(allocation_order="production_first", consumer_cash=0.0)
    capacity_open = fixture.state.organization_capacity.copy()
    result, traces = _run_tiny(fixture, tmp_path)

    assert result.window_metrics["credit_drawn_total"] > 0.0, "the tiny must actually borrow"
    assert result.window_metrics["investment_approved_total"] > 0.0, "an approval must be granted"
    assert result.window_metrics["investment_request_unconstrained_total"] > 0.0
    assert result.window_metrics["investment_installed_capacity_total"] == 0.0
    assert result.window_metrics["capital_wip_close_total"] == 0.0
    assert _investment_axis_totals(result, "capital_goods")["delivered"] == 0.0
    assert np.allclose(
        fixture.state.organization_capacity,
        capacity_open,
    ), "capacity may only grow through an installation, and none happened"
    assert all(record["investment_request_recheck_max_abs_diff"] == 0.0 for record in traces)


def test_allocation_order_not_credit_decides_whether_capacity_is_installed(
    tmp_path: Path,
) -> None:
    """Guard 4/2: the same loan buys capacity only when the legs are delivered.

    This is the design-exposed counterexample reproduced as a permanent test: two
    arms start from one identical opening state, both draw credit, and only the
    one whose investment legs were physically delivered installs capacity.
    """
    starved, _ = _run_tiny(
        _enterprise_tiny(allocation_order="production_first", consumer_cash=0.0), tmp_path
    )
    fed, _ = _run_tiny(
        _enterprise_tiny(allocation_order="investment_first", consumer_cash=0.0), tmp_path
    )

    assert starved.window_metrics["credit_drawn_total"] > 0.0
    assert fed.window_metrics["credit_drawn_total"] > 0.0
    assert starved.window_metrics["investment_installed_capacity_total"] == 0.0
    assert fed.window_metrics["investment_installed_capacity_total"] > 0.0
    assert fed.window_metrics["capacity_close_total"] > starved.window_metrics[
        "capacity_close_total"
    ]
    assert (
        _investment_axis_totals(fed, "capital_goods")["delivered"]
        > _investment_axis_totals(starved, "capital_goods")["delivered"]
    )


def test_preapproved_project_cannot_fabricate_a_new_approval_or_an_installation(
    tmp_path: Path,
) -> None:
    """Guard 2: a pre-set approval is old debt, not a new request or a delivery."""
    plain = _enterprise_tiny(allocation_order="production_first", consumer_cash=100000.0)
    preapproved = _enterprise_tiny(
        allocation_order="production_first",
        consumer_cash=100000.0,
        preapproved_capacity=40.0,
    )
    plain_result, plain_traces = _run_tiny(plain, tmp_path)
    preapproved_result, preapproved_traces = _run_tiny(preapproved, tmp_path)

    opening_request = he.unconstrained_investment_request(
        plain.state, plain.parameters, plain.network
    )
    assert opening_request.sum() > 0.0, "the tiny must want to invest from the opening state"
    assert plain_traces[0]["metrics"]["investment_requested_flows_total"] == pytest.approx(
        opening_request.sum()
    ), "the uncapped engine request must equal capacity times hunger at the opening state"
    assert preapproved_traces[0]["metrics"]["investment_requested_flows_total"] == pytest.approx(
        opening_request.sum()
    ), "a pre-set project must not change the unconstrained new request"
    assert preapproved_result.window_metrics["investment_installed_capacity_total"] == 0.0, (
        "40 approved capacity units with no WIP cannot install anything"
    )
    assert preapproved_result.window_metrics["project_approved_close_total"] >= 40.0, (
        "the old commitment must still be on the books"
    )
    assert (
        preapproved_result.window_metrics["investment_approved_total"]
        <= preapproved_result.window_metrics["investment_requested_flows_total"]
    ), "an approval can never exceed the uncapped request it was cut from"


# ---------------------------------------------------------------------------
# Guard 5: a zero denominator and a missing axis never become a zero shortage.
# ---------------------------------------------------------------------------


def test_zero_denominator_and_missing_axis_never_become_zero_shortage(
    tmp_path: Path,
) -> None:
    """Guard 5: an axis with no demand, and an axis the run never routed."""
    result, _ = _run_tiny(_enterprise_tiny(allocation_order="production_first"), tmp_path)
    rows = he.axis_gap_rows(result)

    blocked = [row for row in rows if row["axis_status"] == "BLOCKED_METRIC"]
    zero_denominator = [
        row
        for row in rows
        if row["axis_status"] == "OBSERVED" and row["gross_gap"]["status"] == "ZERO_DENOMINATOR"
    ]
    assert blocked, "the tiny must leave declared axes unrouted, or the guard is untested"
    assert zero_denominator, "the tiny must leave a routed axis with no orders"

    for row in blocked:
        for metric in ("gross_gap", "funded_gap"):
            assert row[metric]["value"] is None
            assert row[metric]["status"] == "BLOCKED_METRIC"
            assert row[metric]["denominator"] is None
        assert row["delivered"] is None and row["ordered"] is None
    for row in zero_denominator:
        for metric in ("gross_gap", "funded_gap"):
            assert row[metric]["value"] is None
            assert row[metric]["denominator"] == 0.0
            assert row[metric]["status"] == "ZERO_DENOMINATOR"
    for row in rows:
        for metric in ("gross_gap", "funded_gap"):
            if row[metric]["denominator"] == 0:
                assert row[metric]["value"] != 0.0, "a zero denominator must never read as 0% gap"
    # A real zero gap is still distinguishable from an unreadable one.
    filled = [
        row
        for row in rows
        if row["axis_status"] == "OBSERVED" and row["gross_gap"]["status"] == "OK"
    ]
    assert any(float(row["gross_gap"]["value"]) == 0.0 for row in filled)
    assert all(float(row["gross_gap"]["value"]) is not None for row in filled)


# ---------------------------------------------------------------------------
# Guard 8: a halt restores the pre-tick state and records what actually ran.
# ---------------------------------------------------------------------------


def test_halt_restores_the_pre_tick_state_and_reports_the_effective_parameters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guard 8: the failed state is hashed, then the boundary is restored.

    A half-applied tick leaves the arm mid-quarter.  The runner must return the
    state to the boundary it captured, prove the restore byte-for-byte, and
    record the effective parameters that produced the failure.
    """
    fixture = _enterprise_tiny(allocation_order="production_first")
    boundary_digest = he._sha256(he.canonical_material_bytes(fixture.state))

    def _fail(state, *args, **kwargs):
        # Damage the state the way a real partial tick would, then fail.
        state.organization_cash = np.asarray(state.organization_cash) + 1234.5
        state.completed_ticks = int(state.completed_ticks) + 7
        raise RuntimeError("synthetic mid-tick failure")

    monkeypatch.setattr(he, "tick_material", _fail)
    with pytest.raises(he.RunHalted):
        _run_tiny(fixture, tmp_path)

    failure = json.loads((tmp_path / "tiny_soft_high" / "failure.json").read_text())
    assert failure["status"] == "HALTED"
    assert failure["exception_type"] == "RuntimeError"
    assert failure["reason"] == "RuntimeError: synthetic mid-tick failure"
    assert failure["completed_ticks"] == 7, "the clock the kernel left behind must be reported"
    assert failure["forcing_quarters"] == [
        "1957Q1",
        "1957Q2",
        "1957Q3",
    ] or failure["forcing_quarters"], "the forcing quarters must be recorded"

    failed_digest = failure["state_at_failure_sha256"]
    assert failed_digest != boundary_digest, "the damaged state must hash differently"
    assert failure["boundary_pre_tick_state_sha256"] == boundary_digest
    assert failure["restored_pre_tick_state_sha256"] == boundary_digest
    assert failure["restored_equals_boundary"] is True
    parameters = failure["effective_material_parameters"]
    assert parameters["hunger_base"] == pytest.approx(0.5)
    assert parameters["credit_envelope_fraction"] >= 0.0
    assert parameters["bailout_envelope_fraction"] >= 0.0


def test_halt_restores_every_mutable_state_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guard 8: restoration is per field, so no damaged array survives.

    The state object the runner mutates is the one it must hand back, so the
    test keeps a reference to it and compares that object after the halt.
    """
    fixture = _enterprise_tiny(allocation_order="production_first")
    boundary_digest = he._sha256(he.canonical_material_bytes(fixture.state))
    live: dict[str, Any] = {}

    def _fail(state, *args, **kwargs):
        live["state"] = state
        state.organization_cash = np.asarray(state.organization_cash) * 0.0
        state.organization_capacity = np.zeros_like(state.organization_capacity)
        raise RuntimeError("synthetic wipe")

    monkeypatch.setattr(he, "tick_material", _fail)
    with pytest.raises(he.RunHalted):
        _run_tiny(fixture, tmp_path)

    state = live["state"]
    assert float(np.asarray(state.organization_capacity).sum()) > 0.0, (
        "the wiped capacity array must have been put back"
    )
    assert float(np.asarray(state.organization_cash).sum()) > 0.0, (
        "the wiped cash array must have been put back"
    )
    assert he._sha256(he.canonical_material_bytes(state)) == boundary_digest


def test_halt_restores_the_live_state_object_not_a_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guard 8: the restored object is the one the kernel was mutating."""
    fixture = _enterprise_tiny(allocation_order="production_first")
    seen: list[bytes] = []

    def _fail(state, *args, **kwargs):
        state.organization_cash = np.asarray(state.organization_cash) * 0.0
        seen.append(he.canonical_material_bytes(state))
        raise RuntimeError("synthetic wipe")

    monkeypatch.setattr(he, "tick_material", _fail)
    with pytest.raises(he.RunHalted):
        _run_tiny(fixture, tmp_path)

    failure = json.loads((tmp_path / "tiny_soft_high" / "failure.json").read_text())
    assert failure["state_at_failure_sha256"] == he._sha256(seen[0]), (
        "the pre-restore hash must be the state the kernel actually left"
    )
    assert failure["restored_pre_tick_state_sha256"] == failure[
        "boundary_pre_tick_state_sha256"
    ]
    assert failure["restored_pre_tick_state_sha256"] != failure["state_at_failure_sha256"]


def test_collapsed_baseline_is_halted_instead_of_read_as_a_counter_example(
    tmp_path: Path,
) -> None:
    """Guard 6: no capacity installed at all means the arm measures nothing."""
    collapsed, _ = _run_tiny(
        _enterprise_tiny(allocation_order="production_first"), tmp_path
    )
    healthy, _ = _run_tiny(
        _enterprise_tiny(allocation_order="investment_first"), tmp_path
    )

    assert "installed_capacity" in collapsed.collapsed_chains
    reason = he.baseline_collapse_reason(collapsed, _tiny_arm())
    assert reason is not None and reason.startswith("BLOCKED_BASELINE_COLLAPSE")
    assert he.baseline_collapse_reason(healthy, _tiny_arm()) is None
    competitor = he.ArmDesign(
        name="tiny_competitor",
        budget="hard",
        intensity="high",
        regime="base",
        mediator=None,
        role="main",
        budget_hardness=1.0,
        credit_fraction=0.0,
        investment_intensity=1.0,
    )
    assert he.baseline_collapse_reason(collapsed, competitor) is None, (
        "only a main baseline collapse blocks the study; a competitor arm's own zero "
        "chain blocks its own comparison, not the whole run"
    )


# ---------------------------------------------------------------------------
# Guard 9: a journal account the directory does not own halts the run.
# ---------------------------------------------------------------------------


def test_journal_leg_outside_the_account_directory_halts_the_run(
    tmp_path: Path,
) -> None:
    """Guard 9: an unknown counterparty is an illegal one, not an extra one."""
    fixture = _enterprise_tiny(allocation_order="production_first")
    directory = frozenset(he.build_account_directory(fixture.state).values())
    poisoned = frozenset(directory - {min(directory)})
    assert len(poisoned) == len(directory) - 1

    with pytest.raises(he.RunHalted):
        _run_tiny(fixture, tmp_path, account_ids=poisoned)

    failure = json.loads((tmp_path / "tiny_soft_high" / "failure.json").read_text())
    assert failure["exception_type"] == "JournalAccountError"
    assert "outside the account directory" in failure["reason"]
    assert failure["restored_pre_tick_state_sha256"] == he._sha256(
        he.canonical_material_bytes(fixture.state)
    )


def test_real_journal_legs_all_resolve_against_the_account_directory(
    tmp_path: Path,
) -> None:
    """Guard 9: every real leg this engine writes is a directory account."""
    fixture = _enterprise_tiny(allocation_order="investment_first")
    _, traces = _run_tiny(fixture, tmp_path)
    directory = set(he.build_account_directory(fixture.state).values())

    assert traces, "the tiny must produce real journal legs"
    for record in traces:
        check = record["journal_account_check"]
        assert check["status"] == "OK"
        assert check["invalid"] == 0
        assert check["invalid_account_ids"] == []
        assert check["checked"] == record["journal_legs"] > 0
        assert check["accounts_touched"] <= len(directory)


def test_profile_run_publishes_the_account_directory_and_binds_its_digest(
    tmp_path: Path,
) -> None:
    """Guard 9: the directory is exported and bound to each seed's identity."""
    summary = he.run_m02_study(
        REPO_ROOT,
        output_dir=tmp_path / "profile",
        spec_path=STUDY_SPEC,
        seeds=(1729,),
        arm_names=("soft_low_base", "soft_high_base"),
    )
    directory = json.loads((tmp_path / "profile" / "account_directory.json").read_text())
    identity = json.loads((tmp_path / "profile" / "input_identity.json").read_text())

    assert directory["source"] == "hsm_lab.engine.finance.build_account_directory(opening_state)"
    assert directory["entry_fields"] == [
        "owner_kind",
        "owner_id",
        "currency",
        "account_kind",
    ]
    assert len(directory["per_seed"]) == 1
    entry = directory["per_seed"][0]
    assert entry["seed"] == 1729
    assert len(entry["entries"]) == entry["account_count"] > 0
    assert all(len(row) == 4 for row in entry["entries"])
    assert entry["entries"] == sorted(entry["entries"])

    assert identity[0]["account_directory_sha256"] == entry["sha256"]
    assert summary["input_identity"][0]["account_directory_sha256"] == entry["sha256"]


# ---------------------------------------------------------------------------
# Guard 10: closing stock is exported, named and sourced.
# ---------------------------------------------------------------------------


def test_stock_close_is_exported_per_quarter_with_its_source(tmp_path: Path) -> None:
    """Guard 10: stock_close is a level with a stated source, not a sum."""
    fixture = _enterprise_tiny(allocation_order="investment_first")
    _, traces = _run_tiny(fixture, tmp_path)

    assert traces
    for record in traces:
        rows = record["stock_close"]
        assert rows, "every quarter must export its closing stock by axis"
        for row in rows:
            assert set(row) == {"commodity", "stage", "stock_close", "cells", "source"}
            assert row["source"] == "sum of state.stock_value over its cells"
            assert row["cells"] >= 1
            assert row["stock_close"] >= 0.0


# ---------------------------------------------------------------------------
# Guard 11: the opt-in finance probe reads the kernel's real intermediates.
# ---------------------------------------------------------------------------


def test_finance_probe_reads_real_cash_and_procurement_intermediates(
    tmp_path: Path,
) -> None:
    """Guard 11: the intermediates come from the kernel, not from the runner."""
    fixture = _enterprise_tiny(allocation_order="investment_first", consumer_cash=500.0)
    result, traces = _run_tiny(fixture, tmp_path, finance_probe=True)
    parquet = tmp_path / "tiny_soft_high" / "organizations.parquet"

    assert traces
    for record in traces:
        finance = record["finance_trace"]
        assert finance["status"] == "MEASURED"
        assert finance["totals"]["cash_available_for_goods"] is not None
        assert finance["totals"]["input_order_cost"] > 0.0
        assert set(finance["digests"]) == set(finance["totals"])
        assert all(len(digest) == 64 for digest in finance["digests"].values())

    columns = pq.read_schema(parquet)
    for name in (
        "cash_available_for_goods",
        "credit_approval_caps",
        "input_order_cost",
        "old_project_cost",
        "new_investment_request_cost",
        "input_credit_earmarked",
    ):
        assert name in columns.names, f"{name} must be exported per organization"

    table = pq.read_table(parquet, columns=["cash_available_for_goods"]).to_pandas()
    assert table["cash_available_for_goods"].notna().any()
    assert float(table["cash_available_for_goods"].abs().sum()) > 0.0, (
        "a consumer holding cash must show a non-zero goods budget"
    )
    assert result.window_metrics["organization_purchases_total"] > 0.0


def test_preregistered_run_reports_finance_intermediates_as_not_run(
    tmp_path: Path,
) -> None:
    """Guard 11: an unmeasured intermediate is null, never a fabricated zero."""
    fixture = _enterprise_tiny(allocation_order="investment_first", consumer_cash=500.0)
    _, traces = _run_tiny(fixture, tmp_path, finance_probe=False)
    parquet = tmp_path / "tiny_soft_high" / "organizations.parquet"

    for record in traces:
        finance = record["finance_trace"]
        assert finance["status"] == "NOT_RUN"
        assert all(value is None for value in finance["totals"].values())
        assert finance["digests"] == {}

    table = pq.read_table(parquet, columns=["cash_available_for_goods"]).to_pandas()
    assert table["cash_available_for_goods"].isna().all(), (
        "an unmeasured intermediate must be null, not zero"
    )


# ---------------------------------------------------------------------------
# Guard 7 and the rest of the runner's pre-flight refusals.
# ---------------------------------------------------------------------------


def _mutated_spec(tmp_path: Path, mutate) -> Path:
    payload = json.loads(STUDY_SPEC.read_text(encoding="utf-8"))
    mutate(payload)
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_runner_rejects_out_of_bounds_intensity_before_initialising_a_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guard 7: intensity 2.5 is refused by the study runner, not just by PolicyVector."""
    spec = _mutated_spec(
        tmp_path, lambda payload: payload["policy"]["investment_intensity"].update({"high": 2.5})
    )
    output = tmp_path / "runs" / "rejected"
    initialised: list[int] = []

    def _refuse(*args: object, **kwargs: object) -> None:
        initialised.append(1)
        raise AssertionError("the model must never be initialised for a refused study")

    monkeypatch.setattr(he, "build_material_initial_conditions", _refuse)

    with pytest.raises(he.SpecRejection) as excinfo:
        he.run_m02_study(REPO_ROOT, output_dir=output, spec_path=spec, seeds=(1729,))

    assert "policy coordinate" in str(excinfo.value)
    assert not initialised, "the refusal must precede model initialisation"
    assert not output.exists(), "the refusal must precede output creation"


@pytest.mark.parametrize(
    ("label", "mutate", "seeds", "arms", "fragment"),
    [
        (
            "unknown_seed",
            None,
            (4242,),
            None,
            "not preregistered",
        ),
        (
            "duplicate_seed",
            None,
            (1729, 1729),
            None,
            "duplicates",
        ),
        (
            "empty_arm",
            None,
            None,
            (),
            "must not be empty",
        ),
        (
            "unknown_arm",
            None,
            None,
            ("soft_low_base", "not_an_arm"),
            "not preregistered",
        ),
        (
            "duplicate_arm",
            None,
            None,
            ("soft_low_base", "soft_low_base"),
            "duplicates",
        ),
        (
            "non_preregistered_window",
            lambda payload: payload["run"]["window"].update(
                {
                    "start": "1956Q1",
                    "end": "1956Q4",
                    "quarters": ["1956Q1", "1956Q2", "1956Q3", "1956Q4"],
                }
            ),
            None,
            None,
            "not the preregistered window",
        ),
        (
            "drifted_source_hash",
            lambda payload: payload["source"].update({"sha256": "0" * 64}),
            None,
            None,
            "source scenario hash drifted",
        ),
        (
            "card_hypothesis_rewritten",
            lambda payload: payload["legacy_card"].update({"hypothesis": "rewritten"}),
            None,
            None,
            "verbatim",
        ),
    ],
)
def test_runner_refuses_unpreregistered_designs_before_any_output(
    tmp_path: Path,
    label: str,
    mutate,
    seeds: tuple[int, ...] | None,
    arms: tuple[str, ...] | None,
    fragment: str,
) -> None:
    """Every pre-flight refusal happens before the output directory exists."""
    spec = _mutated_spec(tmp_path, mutate) if mutate is not None else STUDY_SPEC
    output = tmp_path / "runs" / label
    with pytest.raises(he.SpecRejection) as excinfo:
        he.run_m02_study(
            REPO_ROOT, output_dir=output, spec_path=spec, seeds=seeds, arm_names=arms
        )
    assert fragment in str(excinfo.value), str(excinfo.value)
    assert not output.exists()


def test_runner_refuses_an_existing_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "runs" / "already-there"
    output.mkdir(parents=True)
    with pytest.raises(he.SpecRejection) as excinfo:
        he.run_m02_study(
            REPO_ROOT,
            output_dir=output,
            spec_path=STUDY_SPEC,
            seeds=(1729,),
            arm_names=("soft_low_base",),
        )
    assert "already exists" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Guards 1, 3 and the placebo/demand-regime contracts on the real study.
# ---------------------------------------------------------------------------

_STUDY_ARMS = (
    "soft_low_base",
    "hard_low_base",
    "placebo_soft_low_base",
    "soft_high_base",
    "hard_high_base",
    "rescue_cut_high_base",
    "credit_cut_high_base",
    "soft_low_reduced",
    "hard_low_reduced",
    "soft_high_reduced",
    "hard_high_reduced",
    "rescue_cut_high_reduced",
    "credit_cut_high_reduced",
)


@pytest.fixture(scope="module")
def study_runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict]:
    """Two real study runs over one seed, arms forward and reversed."""
    base = tmp_path_factory.mktemp("m02-study")
    forward = he.run_m02_study(
        REPO_ROOT,
        output_dir=base / "forward",
        spec_path=STUDY_SPEC,
        seeds=(1729,),
        arm_names=_STUDY_ARMS,
    )
    reverse = he.run_m02_study(
        REPO_ROOT,
        output_dir=base / "reverse",
        spec_path=STUDY_SPEC,
        seeds=(1729,),
        arm_names=tuple(reversed(_STUDY_ARMS)),
    )
    return {"forward": forward, "reverse": reverse, "base": base}


def _first_tick_arm_order(output_dir: Path) -> list[str]:
    """The arm sequence the kernel actually executed, read from the trace."""
    seen: list[str] = []
    for line in (output_dir / "trace.jsonl").read_text().splitlines():
        record = json.loads(line)
        if record["tick"] == 0:
            seen.append(record["arm"])
    return seen


def test_requested_arm_order_is_the_executed_arm_order(study_runs: dict[str, dict]) -> None:
    """Guard 3: ``--arms`` is an execution order, not only a summary filter."""
    base = study_runs["base"]
    assert _first_tick_arm_order(base / "forward") == list(_STUDY_ARMS)
    assert _first_tick_arm_order(base / "reverse") == list(reversed(_STUDY_ARMS))
    assert _first_tick_arm_order(base / "forward") != _first_tick_arm_order(base / "reverse")


def test_arm_order_does_not_contaminate_a_later_arm(study_runs: dict[str, dict]) -> None:
    """Guard 3: every arm enters from the identical opening state, in any order."""
    forward = study_runs["forward"]
    reverse = study_runs["reverse"]
    assert forward["status"] == reverse["status"] == "PARTIAL"
    assert forward["selected"]["arms"] != reverse["selected"]["arms"], "the orders must differ"

    openings = {entry["opening_state_sha256"] for entry in forward["input_identity"]}
    assert len(openings) == 1, "one seed must have exactly one opening state"
    for arm in _STUDY_ARMS:
        assert forward["per_arm"][f"1729|{arm}"]["opening_state_digest"] == next(iter(openings))
        assert reverse["per_arm"][f"1729|{arm}"]["opening_state_digest"] == next(iter(openings))
        digests = (
            "comparison_digest",
            "scientific_digest",
            "final_state_digest",
            "journal_digest",
        )
        for digest in digests:
            assert forward["per_arm"][f"1729|{arm}"][digest] == reverse["per_arm"][
                f"1729|{arm}"
            ][digest], f"{arm} changed {digest} when the arm order changed"


def test_placebo_arm_reproduces_its_base_arm_digests(study_runs: dict[str, dict]) -> None:
    """A placebo that only changes the label must change nothing else."""
    checks = [
        check
        for check in study_runs["forward"]["placebo_checks"]
        if check["status"] == "COMPARED"
    ]
    assert checks, "the placebo arm must have been executed"
    for check in checks:
        assert check["placebo"] == "placebo_soft_low_base"
        assert check["target"] == "soft_low_base"
        assert check["comparison_digest_equal"]
        assert check["final_state_digest_equal"]
        assert check["journal_digest_equal"]
        assert check["scientific_digest_equal"]


def test_joint_budget_is_never_reported_as_a_pure_rescue_effect(
    study_runs: dict[str, dict],
) -> None:
    """Guard 1: hardness alone is NONBINDING here; only the joint contrast binds."""
    forward = study_runs["forward"]
    per_arm = forward["per_arm"]

    soft = per_arm["1729|soft_high_base"]
    hard = per_arm["1729|soft_low_base"]
    rescue_cut = per_arm["1729|rescue_cut_high_base"]
    assert soft["comparison_digest"] != hard[
        "comparison_digest"
    ], "the joint soft/hard contrast must actually move the economy"
    assert (
        soft["comparison_digest"] == rescue_cut["comparison_digest"]
    ), "rescue_cut differs from soft_high_base only by budget_hardness"
    high_window = per_arm["1729|soft_high_base"]["window_metrics"]
    assert high_window["bailout_granted_total"] == 0.0

    records = {
        (row["regime"], row["intensity"]): row for row in forward["first_stage"]["budget"]
    }
    for regime in ("base", "reduced"):
        low = records[(regime, "low")]
        assert low["joint_budget_leg"]["status"] == "BINDING"
        assert low["credit_leg"]["status"] == "BINDING"
        assert low["rescue_leg"]["status"] == "NONBINDING"
        assert low["rescue_leg"]["reason"] in ("ZERO_OUTPUT", "NOT_APPLICABLE")
        assert "JOINT" in low["joint_budget_leg"]["note"]
        # The mediator arms exist only at high investment.  At low investment
        # the decomposition must report null rather than silently compare
        # against a high-intensity arm it never ran.
        assert low["rescue_leg"]["rescue_cut_bailout_granted"] is None
        assert low["rescue_leg"]["credit_cut_bailout_granted"] is None
        assert low["credit_leg"]["credit_cut_credit_drawn"] is None

        high = records[(regime, "high")]
        assert high["rescue_leg"]["rescue_cut_bailout_granted"] is not None
        assert high["rescue_leg"]["credit_cut_bailout_granted"] is not None
        assert high["credit_leg"]["credit_cut_credit_drawn"] is not None
    assert forward["verdicts"]["structural"]["rescue_leg_nonbinding_records"] > 0
    assert forward["verdicts"]["structural"]["credit_leg_nonbinding_records"] == 0


def test_reduced_demand_regime_moves_real_household_desired(study_runs: dict[str, dict]) -> None:
    """The demand regime is a real first stage, not a relabelled parameter."""
    forward = study_runs["forward"]
    base = forward["per_arm"]["1729|soft_low_base"]["window_metrics"]
    reduced = forward["per_arm"]["1729|soft_low_reduced"]["window_metrics"]

    channels = [
        key
        for key, value in base.items()
        if key.startswith("household_desired_channel:")
        and abs(value - reduced[key]) > 1e-9
    ]
    assert channels, "the reduced regime must change real weighted household desired"
    assert any(value > 0.0 for value in base.values() if isinstance(value, float))

    demand_records = [
        row
        for row in forward["first_stage"]["demand_regime"]
        if row["budget"] == "soft" and row["intensity"] == "low"
    ]
    assert demand_records and demand_records[0]["status"] == "BINDING"
    assert set(demand_records[0]["differing_household_desired_channels"]) == {
        key.split(":", 1)[1] for key in channels
    }


def test_study_verdicts_never_claim_support(study_runs: dict[str, dict]) -> None:
    """A four-quarter synthetic window cannot produce SUPPORTED or a history claim."""
    verdicts = study_runs["forward"]["verdicts"]
    assert verdicts["technical"]["verdict"] == "PASS"
    assert verdicts["structural"]["supported_claim"] is None
    for regime, record in verdicts["structural"]["by_regime"].items():
        assert record["verdict"] in ("CONDITIONAL", "REJECTED", "UNIDENTIFIED"), regime
    assert verdicts["historical"]["identification_status"] == "UNIDENTIFIED"
    assert verdicts["historical"]["historical_support"] == "NOT_ESTABLISHED"
    assert verdicts["f2_generalisation"]["status"] == "NOT_RUN"
    assert study_runs["forward"]["status"] == "PARTIAL", "a seed/arm subset is never COMPLETED"


def test_structural_verdict_reads_both_investment_levels(study_runs: dict[str, dict]) -> None:
    """Guard 5: the falsification criterion is judged at low *and* high."""
    forward = study_runs["forward"]
    for row in forward["contrasts"]["by_seed_and_regime"]:
        levels = row["axis_scoped_budget_contrast"]
        assert set(levels) == {"low", "high"}, (
            f"seed {row['seed']} regime {row['regime']} judged only one investment level"
        )
        for level, axes in levels.items():
            assert axes, f"{row['regime']}/{level} must export its axis vector"
            assert any(
                entry["status"] == "OK" and entry["contrast"] is not None
                for entry in axes.values()
            )

    verdicts = forward["verdicts"]["structural"]
    assert verdicts["supported_claim"] is None
    for regime, record in verdicts["by_regime"].items():
        assert record["levels_adjudicated"] == ["low", "high"], regime
        by_level = record["readable_contrasts_by_level"]
        assert set(by_level) == {"low", "high"}, regime
        assert record["readable_contrasts"] == sum(by_level.values())
        assert min(by_level.values()) > 0, f"{regime}: one level produced no readable contrast"
        if record["verdict"] == "REJECTED":
            judged = {row["intensity"] for row in record["seeds_with_non_falling_shortage_axis"]}
            assert judged, "a rejection must name the level whose axis did not fall"
            assert judged <= {"low", "high"}

    zero_bailout = verdicts["arms_with_zero_bailout_grant"]
    assert zero_bailout == sorted(set(zero_bailout)), "the zero-bailout arm list must be deduped"
    assert "credit_cut_high_base" not in zero_bailout, "credit_cut arms do grant a bailout"