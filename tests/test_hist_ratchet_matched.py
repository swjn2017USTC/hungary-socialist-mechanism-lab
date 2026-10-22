"""H5C M01 matched-reference-history ratchet tests.

The tests exercise the consumer-visible invariants of the experiment: the
read-only adapter, the existing updater's first stage, same-point matching,
the whitelisted memory transplant, one-quarter policy recovery, the budget-only
negative control, real political/physical producers, and verify's tamper
rejection.  They never pin an incidental hard-coded output or a source string.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.guards import load_research_contract
from hsm_lab.contract.households import compile_household_catalog
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.network import build_material_network
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import initialize_material
from studies.HIST_VNEXT.M01 import runner
from studies.HIST_VNEXT.M01.expectations_adapter import read_expectations

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED = 1729


def _state() -> tuple[object, object, object]:
    spec = runner._scenario(REPO_ROOT, SEED)
    contract = load_research_contract(REPO_ROOT)
    initial = build_material_initial_conditions(spec, RngRegistry(spec.seed))
    network = build_material_network(spec, contract, initial)
    state = initialize_material(spec, initial, network)
    catalog = compile_household_catalog(
        spec.household_parameters,
        spec.material_parameters,
        tuple(spec.commodities),
    )
    return spec, state, catalog


@pytest.fixture(scope="module")
def arm_set(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict]:
    base = tmp_path_factory.mktemp("h5c-arms")
    common = {
        "root": REPO_ROOT,
        "seed": SEED,
        "history_id": "four_steps",
        "formation_ratchet_strength": 0.1,
    }
    income = runner.run_arm(output_dir=base / "income", cut_id="income_cut", **common)
    control = runner.run_arm(output_dir=base / "control", cut_id="no_cut", **common)
    native_cut = runner.run_arm(
        root=REPO_ROOT,
        output_dir=base / "native-cut",
        seed=SEED,
        history_id="native",
        formation_ratchet_strength=None,
        cut_id="income_cut",
    )
    native_control = runner.run_arm(
        root=REPO_ROOT,
        output_dir=base / "native-control",
        seed=SEED,
        history_id="native",
        formation_ratchet_strength=None,
        cut_id="no_cut",
    )
    return {
        "base": base,
        "income": income,
        "control": control,
        "native_cut": native_cut,
        "native_control": native_control,
    }


def test_adapter_returns_independent_axis_typed_copies() -> None:
    _spec, state, catalog = _state()
    payload = read_expectations(state, catalog)
    assert payload["axes"]["entitlement"] == list(catalog.entitlement_ids)
    assert payload["axes"]["channel"] == list(catalog.household_good_ids)
    assert len(payload["axes"]["household"]) == state.household_expectation.shape[0]
    assert len(payload["expectation"]) == len(payload["axes"]["household"])
    before = np.asarray(state.household_expectation, dtype=np.float64).copy()
    payload["expectation"][0][0] = 999.0
    payload["grievance"][0] = -10.0
    assert np.array_equal(before, np.asarray(state.household_expectation, dtype=np.float64))


def test_adapter_rejects_wrong_shape_negative_streak_and_nonfinite() -> None:
    _spec, state, catalog = _state()
    state.household_expectation = np.zeros(
        (state.household_expectation.shape[0], 2), dtype=np.float64
    )
    with pytest.raises(ConfigError):
        read_expectations(state, catalog)
    _spec, state, catalog = _state()
    state.household_improvement_streak[0, 0] = -1
    with pytest.raises(ConfigError):
        read_expectations(state, catalog)
    _spec, state, catalog = _state()
    state.household_consumption_reference[0, 0] = np.nan
    with pytest.raises(ConfigError):
        read_expectations(state, catalog)


def test_donor_first_stage_and_threshold_ablation() -> None:
    spec = runner._scenario(REPO_ROOT, SEED)
    contract = load_research_contract(REPO_ROOT)
    expected = {
        "one_jump": (0.6, 1, False),
        "two_steps": (0.6375000000000001, 2, False),
        "four_steps": (0.704921875, 4, True),
    }
    for history, (expectation, streak, crossed) in expected.items():
        high = runner.donor_memory(
            root=REPO_ROOT,
            spec=spec,
            contract=contract,
            history_id=history,
            formation_ratchet_strength=0.1,
        )
        low = runner.donor_memory(
            root=REPO_ROOT,
            spec=spec,
            contract=contract,
            history_id=history,
            formation_ratchet_strength=0.0,
        )
        assert high["final"]["expectation_real_consumption_mean"] == pytest.approx(expectation)
        assert high["final"]["streak_real_consumption_max"] == streak
        assert high["final"]["threshold_crossed"] is crossed
        equal = (
            high["final"]["expectation_real_consumption_mean"]
            == low["final"]["expectation_real_consumption_mean"]
        )
        assert equal is (history != "four_steps")
        assert high["not_economic_output"] is True
        assert high["evidence_status"] == "synthetic_experience_input"


def test_transplant_changes_only_whitelisted_memory() -> None:
    spec = runner._scenario(REPO_ROOT, SEED)
    contract = load_research_contract(REPO_ROOT)
    _spec, state, _catalog = _state()
    donor = runner.donor_memory(
        root=REPO_ROOT,
        spec=spec,
        contract=contract,
        history_id="four_steps",
        formation_ratchet_strength=0.1,
    )
    before_state = copy.deepcopy(state)
    before = runner.apply_memory_transplant(state, donor)
    audit = runner.audit_transplant_delta(before, state)
    assert audit["whitelist_respected"] is True
    assert set(audit["changed_fields"]) == {
        "household_expectation",
        "household_improvement_streak",
        "household_consumption_reference",
    }
    assert audit["changed_fields"]["household_expectation"] == [1]
    assert audit["changed_fields"]["household_improvement_streak"] == [1]
    for name in (
        "household_cash",
        "household_grievance",
        "household_entitlement",
        "household_durable_owned",
        "stock_value",
        "bank_deposit_liability",
        "treasury_deposit",
    ):
        assert np.array_equal(
            np.asarray(getattr(before_state, name)), np.asarray(getattr(state, name))
        )


def test_same_point_matching_rejects_cash_supply_quarter_and_policy() -> None:
    left = {
        "quarter": "1958Q1",
        "completed_ticks": 4,
        "household_cash_sum": 1.0,
        "organization_cash_sum": 2.0,
        "bank_deposit_liability_sum": 3.0,
        "treasury_deposit": 4.0,
        "usd_reserve": 5.0,
        "stock_value_sum": 6.0,
        "second_output_stock_sum": 7.0,
        "organization_capacity_sum": 8.0,
        "policy": [0.5] * 19,
        "scenario_hash": "s",
        "parameter_hash": "p",
        "forcing_input_hashes": {"f": "h"},
        "external_pack_hash": "e",
        "rng_snapshot_digest": "r",
    }
    runner.assert_same_point(left, copy.deepcopy(left))
    for key, value in (
        ("quarter", "1959Q1"),
        ("household_cash_sum", 1.1),
        ("stock_value_sum", 6.1),
        ("policy", [0.4] * 19),
        ("rng_snapshot_digest", "other"),
    ):
        changed = copy.deepcopy(left)
        changed[key] = value
        with pytest.raises(ConfigError):
            runner.assert_same_point(left, changed)


def test_matched_arm_produces_real_policy_politics_consumption_and_gate(
    arm_set: dict[str, dict],
) -> None:
    income = arm_set["income"]
    control = arm_set["control"]
    runner.assert_same_point(income["opening"], control["opening"])
    assert income["opening"]["nonmemory_digest"] == control["opening"]["nonmemory_digest"]
    assert income["tables"]["rows"] == {
        "political_quarters": 8,
        "opposition_regions": 160,
        "information_quarters": 80,
        "household_budgets": 160,
        "national_accounts": 64,
    }
    tick = income["tables"]["metrics_by_quarter"]["1958Q1"]
    assert tick["policy"]["wage_factor"] == pytest.approx(0.9)
    assert tick["grievance_national_from_table"] == pytest.approx(tick["grievance_national_state"])
    control_tick = control["tables"]["metrics_by_quarter"]["1958Q1"]
    assert tick["grievance_national_from_table"] != control_tick["grievance_national_from_table"]
    assert tick["household_consumption_by_commodity"]["food"] > 0.0
    assert tick["household_consumption_by_commodity"]["consumer_goods"] > 0.0
    assert tick["spending_total"] != control_tick["spending_total"]
    assert income["gates"]["max_material_tolerance_ratio"] < 1.0
    assert income["gates"]["max_finance_tolerance_ratio"] < 1.0
    assert income["matching_sha256"]


def test_budget_only_arm_keeps_native_memory_and_recovers_after_one_quarter(
    arm_set: dict[str, dict],
) -> None:
    cut = arm_set["native_cut"]
    control = arm_set["native_control"]
    matching = json.loads((Path(cut["output_dir"]) / "matching.json").read_text(encoding="utf-8"))
    assert matching["delta"] is None
    assert cut["opening"]["memory"] == cut["opening"]["memory_pre_transplant"]
    assert cut["opening"]["matching_digest"] == control["opening"]["matching_digest"]
    assert cut["opening"]["nonmemory_digest"] == control["opening"]["nonmemory_digest"]
    metrics = cut["tables"]["metrics_by_quarter"]
    assert metrics["1958Q1"]["policy"]["wage_factor"] == pytest.approx(0.9)
    for quarter in ("1958Q2", "1958Q3", "1958Q4"):
        assert metrics[quarter]["policy"]["wage_factor"] == pytest.approx(1.0)


def test_empty_political_measurement_is_rejected_not_zero() -> None:
    empty = pl.DataFrame({"tick": [], "quarter": [], "feature_id": []})
    tables = {
        "political_quarters": pl.DataFrame({"tick": [], "quarter": []}),
        "opposition_regions": empty,
        "information_quarters": empty,
    }
    with pytest.raises(ConfigError):
        runner.require_political_measurement(tables)
    tables["political_quarters"] = pl.DataFrame({"tick": [4], "quarter": ["1958Q1"]})
    with pytest.raises(ConfigError):
        runner.require_political_measurement(tables)


def test_verify_rejects_seed_metric_and_missing_table_tampering(
    arm_set: dict[str, dict], tmp_path: Path
) -> None:
    original = Path(arm_set["base"]) / "income"
    canonical = "1729-four_steps-0.1-income_cut"

    def tampered(name: str) -> Path:
        parent = tmp_path / name
        parent.mkdir()
        target = parent / canonical
        shutil.copytree(original, target)
        return target

    clean_dir = tampered("clean")
    runner._verify_arm(clean_dir)

    seed_dir = tampered("seed")
    result_path = seed_dir / "result.json"
    payload = json.loads(result_path.read_text())
    payload["seed"] = 1730
    result_path.write_text(json.dumps(payload))
    with pytest.raises(runner.VerificationError):
        runner._verify_arm(seed_dir)

    metric_dir = tampered("metric")
    result_path = metric_dir / "result.json"
    payload = json.loads(result_path.read_text())
    payload["tables"]["metrics_by_quarter"]["1958Q1"]["grievance_national_from_table"] += 0.01
    result_path.write_text(json.dumps(payload))
    with pytest.raises(runner.VerificationError):
        runner._verify_arm(metric_dir)

    gap_dir = tampered("gap")
    result_path = gap_dir / "result.json"
    payload = json.loads(result_path.read_text())
    payload["tables"]["metrics_by_quarter"]["1958Q1"]["contract_gap_truth"] += 999.0
    result_path.write_text(json.dumps(payload))
    with pytest.raises(runner.VerificationError):
        runner._verify_arm(gap_dir)

    memory_dir = tampered("memory")
    memory_path = memory_dir / "memory/post-1958Q1.json"
    memory_payload = json.loads(memory_path.read_text())
    memory_payload["expectation"][0][0] += 1.0
    memory_path.write_text(json.dumps(memory_payload))
    result_path = memory_dir / "result.json"
    payload = json.loads(result_path.read_text())
    payload["memory_files"]["memory/post-1958Q1.json"] = hashlib.sha256(
        memory_path.read_bytes()
    ).hexdigest()
    result_path.write_text(json.dumps(payload))
    with pytest.raises(runner.VerificationError):
        runner._verify_arm(memory_dir)

    nan_dir = tampered("nan")
    result_path = nan_dir / "result.json"
    payload = json.loads(result_path.read_text())
    payload["tables"]["metrics_by_quarter"]["1958Q1"]["contract_gap_truth"] = float("nan")
    result_path.write_text(json.dumps(payload))
    with pytest.raises(runner.VerificationError):
        runner._verify_arm(nan_dir)

    illegal_memory = tampered("illegal-memory")
    memory_path = illegal_memory / "memory/opening-1957Q4.json"
    memory_payload = json.loads(memory_path.read_text())
    memory_payload["expectation"][0][0] += 0.1
    expectation = np.asarray(memory_payload["expectation"], dtype=np.float64)
    memory_payload["array_sha256"]["expectation"] = runner._array_digest(expectation)
    memory_path.write_text(json.dumps(memory_payload))
    result_path = illegal_memory / "result.json"
    payload = json.loads(result_path.read_text())
    payload["memory_files"]["memory/opening-1957Q4.json"] = hashlib.sha256(
        memory_path.read_bytes()
    ).hexdigest()
    result_path.write_text(json.dumps(payload))
    with pytest.raises(runner.VerificationError):
        runner._verify_arm(illegal_memory)

    both_memory = tampered("both-memory")
    result_path = both_memory / "result.json"
    payload = json.loads(result_path.read_text())
    for relative in ("memory/pre-transplant-1957Q4.json", "memory/opening-1957Q4.json"):
        memory_path = both_memory / relative
        memory_payload = json.loads(memory_path.read_text())
        memory_payload["expectation"][0][0] += 0.1
        expectation = np.asarray(memory_payload["expectation"], dtype=np.float64)
        memory_payload["array_sha256"]["expectation"] = runner._array_digest(expectation)
        memory_path.write_text(json.dumps(memory_payload))
        payload["memory_files"][relative] = hashlib.sha256(memory_path.read_bytes()).hexdigest()
    result_path.write_text(json.dumps(payload))
    with pytest.raises(runner.VerificationError):
        runner._verify_arm(both_memory)

    summary_only = tampered("summary-only")
    memory_path = summary_only / "memory/post-1958Q1.json"
    memory_payload = json.loads(memory_path.read_text())
    memory_payload["summary"]["expectation_real_consumption_mean"] += 123.0
    memory_payload["summary"]["compliance_weighted_mean"] += 123.0
    memory_path.write_text(json.dumps(memory_payload))
    result_path = summary_only / "result.json"
    payload = json.loads(result_path.read_text())
    payload["memory_files"]["memory/post-1958Q1.json"] = hashlib.sha256(
        memory_path.read_bytes()
    ).hexdigest()
    result_path.write_text(json.dumps(payload))
    with pytest.raises(runner.VerificationError):
        runner._verify_arm(summary_only)

    forged_summary = tampered("summary")
    memory_path = forged_summary / "memory/post-1958Q1.json"
    memory_payload = json.loads(memory_path.read_text())
    memory_payload["summary"]["expectation_real_consumption_mean"] += 0.2
    memory_path.write_text(json.dumps(memory_payload))
    result_path = forged_summary / "result.json"
    payload = json.loads(result_path.read_text())
    payload["memory_files"]["memory/post-1958Q1.json"] = hashlib.sha256(
        memory_path.read_bytes()
    ).hexdigest()
    payload["tables"]["metrics_by_quarter"]["1958Q1"]["expectation_real_consumption_mean"] += 0.2
    result_path.write_text(json.dumps(payload))
    with pytest.raises(runner.VerificationError):
        runner._verify_arm(forged_summary)

    table_dir = tampered("table")
    (table_dir / "political_quarters.parquet").unlink()
    with pytest.raises(runner.VerificationError):
        runner._verify_arm(table_dir)
