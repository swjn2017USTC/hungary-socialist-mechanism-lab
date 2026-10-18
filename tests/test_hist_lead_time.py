"""H3D: synthetic fixed lead-time staging (P->L, P/2->L/2->P/2->L/2).

Every fixture here is the real ``_food_chain_fixture`` /
``_energy_lag_fixture`` / ``_transport_fixture`` from
``tests.test_material``.  No tick, account, stock or journal is mocked.
The tests advance the kernel via a real helper that captures opening,
calls the real ``tick_material`` (or the H3D adapter), checks the
existing invariants, and only then increments ``completed_ticks``.  The
legacy food chain path must reproduce the P02 baseline 8 / 0 / 0 / 6
quarters (with the Q3 unmet=4), and the 2-stage / 4-stage path must
improve the household food timing without widening the envelope.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.contract.material import (
    P02_COMMODITY_IDS,
    PURPOSE_CODES,
    RoutePurpose,
    TradeParameters,
)
from hsm_lab.engine import accounting
from hsm_lab.engine.material import (
    canonical_material_bytes,
    tick_material,
)
from hsm_lab.engine.state import capture_material_stocks
from hsm_lab.institutions.lead_time_adapter import (
    LeadTimeFailure,
    LeadTimeSpec,
    _verify_trace,
    execute_lead_time_tick,
    load_lead_time_spec,
)
from tests.test_material import (
    NO_CAPITAL_COMMODITIES,
    Fixture,
    _energy_lag_fixture,
    _food_chain_fixture,
    _housing_fixture,
    _investment_priority_fixture,
    _partial_project_fixture,
    _transport_fixture,
    _transport_hub_edge,
    bank,
    default_params,
    hub,
    idle_source_tech,
    producer,
    retail,
    tech,
    transport,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "institutions" / "HIST_VNEXT" / "h3d_tiny_lead_time.json"


# ---------------------------------------------------------------------------
# Real helpers — never silently swallow a failure
# ---------------------------------------------------------------------------


def _run_kernel_tick(fixture: Fixture, forcing_quarters: int = 4) -> None:
    """Run one real tick and only advance on a full invariant pass."""
    forcing = fixture.forcing(forcing_quarters)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state, forcing, fixture.parameters, fixture.network
    )
    summary = accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    assert summary.max_material_abs_residual < 1e-8
    fixture.state.completed_ticks = int(fixture.state.completed_ticks) + 1


def _run_adapter_tick(fixture: Fixture, spec: LeadTimeSpec) -> None:
    """Run one real adapter tick; advance only on a full pass."""
    forcing = fixture.forcing(4)
    result = execute_lead_time_tick(
        fixture.state,
        forcing,
        fixture.parameters,
        fixture.network,
        spec=spec,
    )
    assert result.gate.max_material_abs_residual < 1e-8


def _run_n_quarters(
    fixture: Fixture, spec: LeadTimeSpec | None, quarters: int
) -> list:
    """Run ``quarters`` real ticks; return flows; advance only on pass."""
    forcing = fixture.forcing(max(quarters + 1, 5))
    captured: list = []
    for _ in range(quarters):
        if spec is None:
            opening = capture_material_stocks(fixture.state)
            flows = tick_material(
                fixture.state,
                forcing,
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
            fixture.state.completed_ticks = int(fixture.state.completed_ticks) + 1
        else:
            result = execute_lead_time_tick(
                fixture.state,
                forcing,
                fixture.parameters,
                fixture.network,
                spec=spec,
            )
            flows = result.flows
        captured.append(flows)
    return captured


def _food_chain_canonical(fixture: Fixture) -> bytes:
    return canonical_material_bytes(fixture.state)


def _assert_pair_identity(
    arm_a_fixture: Fixture,
    arm_b_fixture: Fixture,
    *,
    label: str,
) -> None:
    """Reject a paired comparison arm whose inputs diverge from the baseline.

    The paired-arm identity helper is the only legitimate way to compare a
    ``legacy`` arm and a ``staged`` arm: every opening cash/stock, parameters,
    forcing quarter slice and network attribute must match exactly.  Tests
    that bypass this check by feeding different fixtures into the two arms
    must be rejected.
    """
    state_a = arm_a_fixture.state
    state_b = arm_b_fixture.state
    for field in (
        "organization_cash",
        "household_cash",
        "stock_value",
        "treasury_deposit",
        "bank_reserves",
        "bank_deposit_liability",
        "household_deferred_receipt",
        "household_durable_owned",
        "organization_shortage_expectation",
        "organization_capacity",
    ):
        a = np.asarray(getattr(state_a, field), dtype=np.float64)
        b = np.asarray(getattr(state_b, field), dtype=np.float64)
        if not np.array_equal(a, b):
            raise AssertionError(
                f"paired-arm identity violation on {label}: "
                f"state.{field} opening differs between arms"
            )
    if arm_a_fixture.parameters != arm_b_fixture.parameters:
        raise AssertionError(
            f"paired-arm identity violation on {label}: parameters differ"
        )
    if arm_a_fixture.network.region_ids != arm_b_fixture.network.region_ids:
        raise AssertionError(
            f"paired-arm identity violation on {label}: region_ids differ"
        )
    if list(arm_a_fixture.network.commodity_ids) != list(
        arm_b_fixture.network.commodity_ids
    ):
        raise AssertionError(
            f"paired-arm identity violation on {label}: commodity_ids differ"
        )


# ---------------------------------------------------------------------------
# Shared repair helpers
# ---------------------------------------------------------------------------


def _assert_state_fully_restored(
    state: object, before: object, *, label: str = "rollback"
) -> None:
    """Compare every dataclass field (arrays exactly) plus the clock."""
    fields = state.__dataclass_fields__  # type: ignore[attr-defined]
    assert int(state.completed_ticks) == int(before.completed_ticks)
    for field in fields:
        current = getattr(state, field)
        original = getattr(before, field)
        if isinstance(original, np.ndarray):
            assert np.array_equal(
                np.asarray(current), np.asarray(original)
            ), f"{label}: field {field} did not roll back"
        else:
            assert current == original, (
                f"{label}: field {field} did not roll back"
            )


def _assert_trace_rejected(
    fixture: Fixture,
    result: object,
    corrupted: dict,
    *,
    stage_count: int = 4,
) -> None:
    with pytest.raises(ResearchGateError, match="hist-lead-time-v1"):
        _verify_trace(
            spec=LeadTimeSpec(stage_count=stage_count),
            state=fixture.state,
            network=fixture.network,
            parameters=fixture.parameters,
            flows=result.flows,
            trace=corrupted,
            audit=_audit_from_trace(result.trace),
        )


def _export_fixture() -> Fixture:
    """One energy seller with a positive CMEA export demand and Treasury cash."""
    seller = producer(1, "energy_generation")
    axis = len(P02_COMMODITY_IDS)
    trade = TradeParameters(
        cmea_desired_imports=[0.0] * axis,
        convertible_desired_imports=[0.0] * axis,
        cmea_export_demands=[
            2.0 if commodity_id == "energy" else 0.0
            for commodity_id in P02_COMMODITY_IDS
        ],
        convertible_export_demands=[0.0] * axis,
        convertible_opening_reserve=0.0,
        convertible_loan_limit=0.0,
    )
    fixture = Fixture(
        [bank(0), seller],
        [idle_source_tech("energy_generation", "energy")],
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=default_params(trade=trade),
        households=[(0, 1.0, 1.0)],
        ticks=1,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[
        fixture.cell("organization", 1, 0, "output", "energy")
    ] = 5.0
    return fixture


def _two_bank_transport_fixture() -> Fixture:
    """Transport fixture whose cross-region seller banks at bank 1."""
    seller = producer(2, "energy_generation", region="R1", bank_id=1)
    wholesale = hub(3, region="R0")
    shop = retail(4, region="R0")
    hauler = transport(5, region="R0", capacity=1.0)
    technologies = [
        idle_source_tech("energy_generation", "energy"),
        tech(
            "freight_transport",
            inputs=(("durable_goods", 1.0),),
            outputs=(("services_transport", "standard", 1.0),),
        ),
    ]
    parameters = default_params(
        desired_per_person=[0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        transport_per_unit=0.1,
    )
    fixture = Fixture(
        [bank(0), bank(1), seller, wholesale, shop, hauler],
        technologies,
        region_ids=("R0", "R1"),
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 25.0)],
        household_cash=1000.0,
        ticks=1,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[
        fixture.cell("organization", 2, 1, "output", "energy")
    ] = 10.0
    fixture.state.stock_value[
        fixture.cell("organization", 5, 0, "input", "durable_goods")
    ] = 1.0
    return fixture


# ---------------------------------------------------------------------------
# Spec loader / spec file
# ---------------------------------------------------------------------------


def test_spec_loader_reads_default_null() -> None:
    spec = load_lead_time_spec(SPEC_PATH)
    assert spec.stage_count is None
    assert spec.schema_version == "hist-lead-time-v1"
    assert spec.source_kind == "synthetic"


def test_spec_file_default_off() -> None:
    payload = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": "hist-lead-time-v1",
        "source_kind": "synthetic",
        "stage_count": None,
    }


def test_spec_loader_rejects_unknown_keys(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "schema_version": "hist-lead-time-v1",
                "source_kind": "synthetic",
                "stage_count": None,
                "extra_key": 1,
            }
        )
    )
    with pytest.raises(ResearchGateError, match="unknown keys"):
        load_lead_time_spec(bad)


def test_spec_loader_rejects_wrong_schema(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "schema_version": "hist-lead-time-other",
                "source_kind": "synthetic",
                "stage_count": 2,
            }
        )
    )
    with pytest.raises(ResearchGateError, match="schema_version"):
        load_lead_time_spec(bad)


def test_spec_loader_rejects_non_synthetic_source(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "schema_version": "hist-lead-time-v1",
                "source_kind": "historical",
                "stage_count": 2,
            }
        )
    )
    with pytest.raises(ResearchGateError, match="source_kind"):
        load_lead_time_spec(bad)


def test_spec_loader_rejects_invalid_stage_count(tmp_path: Path) -> None:
    for value in (3, 0, 1, 2.0, 5, -2):
        bad = tmp_path / "bad.json"
        bad.write_text(
            json.dumps(
                {
                    "schema_version": "hist-lead-time-v1",
                    "source_kind": "synthetic",
                    "stage_count": value,
                }
            )
        )
        with pytest.raises(ResearchGateError):
            load_lead_time_spec(bad)


def test_spec_loader_rejects_bool_stage_count(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "schema_version": "hist-lead-time-v1",
                "source_kind": "synthetic",
                "stage_count": True,
            }
        )
    )
    with pytest.raises(ResearchGateError):
        load_lead_time_spec(bad)


def test_spec_loader_rejects_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(ResearchGateError, match="not found"):
        load_lead_time_spec(missing)


def test_spec_loader_rejects_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(ResearchGateError, match="invalid JSON"):
        load_lead_time_spec(bad)


def test_spec_loader_rejects_non_object_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2, 3]")
    with pytest.raises(ResearchGateError, match="JSON object"):
        load_lead_time_spec(bad)


# ---------------------------------------------------------------------------
# Kernel preflight rejection — every call must raise before any state change
# ---------------------------------------------------------------------------


def test_kernel_rejects_bool_count_does_not_mutate_state() -> None:
    fixture = _food_chain_fixture()
    opening_stocks = np.asarray(
        fixture.state.stock_value, dtype=np.float64
    ).copy()
    opening_cash = float(np.sum(fixture.state.organization_cash))
    with pytest.raises(ValueError, match="HIST_H3D_LEAD_TIME"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_count=True,
        )
    assert np.array_equal(
        np.asarray(fixture.state.stock_value, dtype=np.float64),
        opening_stocks,
    )
    assert float(np.sum(fixture.state.organization_cash)) == pytest.approx(
        opening_cash
    )


def test_kernel_rejects_zero_count() -> None:
    fixture = _food_chain_fixture()
    with pytest.raises(ValueError, match="HIST_H3D_LEAD_TIME"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_count=0,
        )


def test_kernel_rejects_one_count() -> None:
    fixture = _food_chain_fixture()
    with pytest.raises(ValueError, match="HIST_H3D_LEAD_TIME"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_count=1,
        )


def test_kernel_rejects_three_count() -> None:
    fixture = _food_chain_fixture()
    with pytest.raises(ValueError, match="HIST_H3D_LEAD_TIME"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_count=3,
        )


def test_kernel_rejects_float_count() -> None:
    fixture = _food_chain_fixture()
    with pytest.raises(ValueError, match="HIST_H3D_LEAD_TIME"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_count=2.0,
        )


def test_kernel_rejects_negative_count() -> None:
    fixture = _food_chain_fixture()
    with pytest.raises(ValueError, match="HIST_H3D_LEAD_TIME"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_count=-2,
        )


def test_kernel_rejects_non_dict_trace() -> None:
    fixture = _food_chain_fixture()
    with pytest.raises(ValueError, match="HIST_H3D_LEAD_TIME"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_count=2,
            micro_stage_trace=[],
        )


def test_kernel_rejects_nonempty_trace() -> None:
    fixture = _food_chain_fixture()
    with pytest.raises(ValueError, match="HIST_H3D_LEAD_TIME"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_count=2,
            micro_stage_trace={"stages": []},
        )


def test_kernel_rejects_combined_h3b_hook() -> None:
    fixture = _food_chain_fixture()
    caps = np.zeros(fixture.state.organization_id.shape[0], dtype=np.float64)
    with pytest.raises(ValueError, match="HIST_H3D_LEAD_TIME"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_count=2,
            micro_stage_trace={},
            credit_approval_caps=caps,
        )


def test_kernel_rejects_combined_h3c_hook() -> None:
    fixture = _food_chain_fixture()
    with pytest.raises(ValueError, match="HIST_H3D_LEAD_TIME"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_count=2,
            micro_stage_trace={},
            routing_trace={},
        )


def test_kernel_rejects_combined_h3c_routing_allocator() -> None:
    fixture = _food_chain_fixture()

    def _allocator(_):
        return np.zeros(0, dtype=np.float64)

    with pytest.raises(ValueError, match="HIST_H3D_LEAD_TIME"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_count=2,
            micro_stage_trace={},
            routing_allocator=_allocator,
        )


def test_legacy_path_no_state_change_on_preflight() -> None:
    fixture = _food_chain_fixture()
    before = copy.deepcopy(fixture.state)
    with pytest.raises(ValueError, match="HIST_H3D_LEAD_TIME"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_count=5,
        )
    assert int(fixture.state.completed_ticks) == int(before.completed_ticks)
    assert np.array_equal(
        np.asarray(fixture.state.stock_value, dtype=np.float64),
        np.asarray(before.stock_value, dtype=np.float64),
    )


def test_adapter_rejects_invalid_spec_type() -> None:
    fixture = _food_chain_fixture()
    with pytest.raises(ResearchGateError, match="LeadTimeSpec"):
        execute_lead_time_tick(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            spec=object(),  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Legacy food chain baseline (P02 reproduction — three real quarters)
# ---------------------------------------------------------------------------


def test_legacy_food_chain_three_real_quarters() -> None:
    fixture = _food_chain_fixture()
    food_g = fixture.g("food")
    forcing = fixture.forcing(4)
    flows_list: list = []
    for _ in range(3):
        opening = capture_material_stocks(fixture.state)
        flows = tick_material(
            fixture.state, forcing, fixture.parameters, fixture.network
        )
        accounting.check_material_invariants(
            opening, fixture.state, flows, fixture.parameters, fixture.network
        )
        fixture.state.completed_ticks = int(fixture.state.completed_ticks) + 1
        flows_list.append(flows)
    assert flows_list[0].activity_realized[0] == pytest.approx(8.0)
    assert flows_list[0].household_realized[0, food_g] == pytest.approx(0.0)
    assert flows_list[1].household_realized[0, food_g] == pytest.approx(0.0)
    assert flows_list[2].household_realized[0, food_g] == pytest.approx(6.0)
    assert flows_list[2].household_availability_unmet[0, food_g] == pytest.approx(4.0)
    assert int(fixture.state.completed_ticks) == 3


def test_legacy_kernel_canonical_bytes_match_for_none_spec() -> None:
    """``stage_count=None`` adapter must match the default kernel byte-for-byte."""
    fixture_a = _food_chain_fixture()
    for _ in range(3):
        _run_kernel_tick(fixture_a)
    fixture_b = _food_chain_fixture()
    for _ in range(3):
        _run_adapter_tick(fixture_b, LeadTimeSpec(stage_count=None))
    assert _food_chain_canonical(fixture_a) == _food_chain_canonical(fixture_b)


# ---------------------------------------------------------------------------
# 2-stage food chain: production 8, hub delivery 8, retail delivery 8,
# household 6, cumulative Q1..Q4 >= legacy, clock advances 4
# ---------------------------------------------------------------------------


def test_two_stage_food_chain_q1_production_and_hub_delivery() -> None:
    fixture = _food_chain_fixture()
    food_g = fixture.g("food")
    hub_cell = fixture.cell("organization", 2, 0, "wholesale", "food", "ready")
    flows_q1 = _run_n_quarters(fixture, LeadTimeSpec(stage_count=2), 1)[0]
    assert flows_q1.activity_realized[0] == pytest.approx(8.0)
    assert fixture.state.stock_value[hub_cell] == pytest.approx(8.0)
    assert flows_q1.household_realized[0, food_g] == pytest.approx(0.0)
    assert flows_q1.household_availability_unmet[0, food_g] == pytest.approx(10.0)


def test_two_stage_food_chain_q2_retail_delivery_and_household() -> None:
    fixture = _food_chain_fixture()
    food_g = fixture.g("food")
    hub_cell = fixture.cell("organization", 2, 0, "wholesale", "food", "ready")
    shop_cell = fixture.cell("organization", 3, 0, "retail", "food", "ready")
    flows = _run_n_quarters(fixture, LeadTimeSpec(stage_count=2), 2)
    flows_q2 = flows[1]
    raw_input_cell = fixture.cell(
        "organization", 1, 0, "input", "food", "raw"
    )
    assert float(fixture.state.stock_value[raw_input_cell]) == pytest.approx(0.0)
    assert fixture.state.stock_value[shop_cell] == pytest.approx(2.0)
    assert fixture.state.stock_value[hub_cell] == pytest.approx(0.0)
    assert flows_q2.household_realized[0, food_g] == pytest.approx(6.0)
    assert flows_q2.household_availability_unmet[0, food_g] == pytest.approx(4.0)


def test_two_stage_cumulative_no_less_than_legacy_through_q4() -> None:
    """Through Q4 the staged arm must match or exceed legacy household food."""
    legacy_food = _food_chain_fixture()
    staged_food = _food_chain_fixture()
    _assert_pair_identity(legacy_food, staged_food, label="food_chain_2stage")
    legacy_flows = _run_n_quarters(legacy_food, None, 4)
    staged_flows = _run_n_quarters(
        staged_food, LeadTimeSpec(stage_count=2), 4
    )
    assert int(legacy_food.state.completed_ticks) == 4
    assert int(staged_food.state.completed_ticks) == 4
    food_g = legacy_food.g("food")
    legacy_cum = float(
        sum(f.household_realized[0, food_g] for f in legacy_flows)
    )
    staged_cum = float(
        sum(f.household_realized[0, food_g] for f in staged_flows)
    )
    assert staged_cum + 1e-9 >= legacy_cum


def test_two_stage_food_chain_first_p_uses_only_opening_inputs() -> None:
    fixture = _food_chain_fixture()
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        micro_stage_count=2,
        micro_stage_trace={},
    )
    accounting.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    assert float(flows.activity_realized[0]) == pytest.approx(8.0)
    raw_input_cell = fixture.cell(
        "organization", 1, 0, "input", "food", "raw"
    )
    assert float(fixture.state.stock_value[raw_input_cell]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 4-stage food chain: cumulative same as 2-stage through Q4 (food chain has
# deterministic per-quarter P/L), clock 4
# ---------------------------------------------------------------------------


def test_four_stage_food_chain_q1_production_and_hub_delivery() -> None:
    fixture = _food_chain_fixture()
    food_g = fixture.g("food")
    hub_cell = fixture.cell("organization", 2, 0, "wholesale", "food", "ready")
    flows_q1 = _run_n_quarters(fixture, LeadTimeSpec(stage_count=4), 1)[0]
    assert flows_q1.activity_realized[0] == pytest.approx(8.0)
    assert fixture.state.stock_value[hub_cell] == pytest.approx(8.0)
    assert flows_q1.household_realized[0, food_g] == pytest.approx(0.0)


def test_four_stage_cumulative_no_less_than_legacy_through_q4() -> None:
    legacy_food = _food_chain_fixture()
    staged_food = _food_chain_fixture()
    _assert_pair_identity(legacy_food, staged_food, label="food_chain_4stage")
    legacy_flows = _run_n_quarters(legacy_food, None, 4)
    staged_flows = _run_n_quarters(
        staged_food, LeadTimeSpec(stage_count=4), 4
    )
    assert int(legacy_food.state.completed_ticks) == 4
    assert int(staged_food.state.completed_ticks) == 4
    food_g = legacy_food.g("food")
    legacy_cum = float(
        sum(f.household_realized[0, food_g] for f in legacy_flows)
    )
    staged_cum = float(
        sum(f.household_realized[0, food_g] for f in staged_flows)
    )
    assert staged_cum + 1e-9 >= legacy_cum


# ---------------------------------------------------------------------------
# Energy lag fixture — staging must not borrow not-yet-delivered energy
# ---------------------------------------------------------------------------


def test_two_stage_energy_lag_no_future_energy_to_first_p() -> None:
    fixture = _energy_lag_fixture(capital_buffer=0.0)
    raw_activity_row = 1
    capital_activity_row = 2
    flows_q1 = _run_n_quarters(fixture, LeadTimeSpec(stage_count=2), 1)[0]
    # First P cannot see yet-uncommitted delivery of energy.
    assert flows_q1.activity_realized[raw_activity_row] == pytest.approx(0.0)
    assert flows_q1.activity_realized[capital_activity_row] == pytest.approx(
        0.0
    )
    # The single L moves the available 3 energy into the raw producer input
    # cell so the next quarter's P can use it.  ``flows.used`` (the per-K
    # consumption vector) records zero because Q1 production itself produced
    # nothing — the energy is staged for the next quarter's input cell.
    raw_input_cell = fixture.cell(
        "organization", 2, 0, "input", "energy"
    )
    assert fixture.state.stock_value[raw_input_cell] == pytest.approx(3.0)


def test_four_stage_energy_lag_p2_uses_only_l1_delivered_energy() -> None:
    fixture = _energy_lag_fixture(capital_buffer=0.0)
    raw_demand = fixture.k_of(
        fixture.cell("organization", 3, 0, "input", "raw_materials")
    )
    energy_demand = fixture.k_of(
        fixture.cell("organization", 2, 0, "input", "energy")
    )
    capital_activity = 2
    raw_activity = 1
    # Run one quarter so the staged path executes two P/L rounds.
    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(5),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=4),
    )
    flows_q1 = result.flows
    # Q1 first P cannot run — no input has been delivered yet.
    p_stages = [s for s in result.trace["stages"] if s["kind"] == "P"]
    assert p_stages[0]["activity_realized"][raw_activity] == pytest.approx(0.0)
    assert p_stages[0]["activity_realized"][capital_activity] == pytest.approx(
        0.0
    )
    # Q1 second P can run because L1 has now moved 3 energy into the raw
    # producer's input cell.  P2 uses only the L1-delivered energy; it cannot
    # access energy produced earlier in the same stage round.
    assert p_stages[1]["activity_realized"][raw_activity] == pytest.approx(
        3.0
    )
    assert p_stages[1]["activity_realized"][capital_activity] == pytest.approx(
        0.0
    )
    # Q1 second L then moves the produced raw into the capital producer's
    # input cell — but P1 cannot have consumed that raw before L2 has
    # delivered it.  Capital producer therefore still shows zero at Q1.
    assert flows_q1.activity_realized[raw_activity] == pytest.approx(3.0)
    assert flows_q1.activity_realized[capital_activity] == pytest.approx(0.0)
    assert flows_q1.delivered[energy_demand] == pytest.approx(3.0)
    assert flows_q1.delivered[raw_demand] == pytest.approx(3.0)
    # Q2 first P now lets the capital producer consume the L2-delivered raw.
    result_q2 = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(5),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=4),
    )
    flows_q2 = result_q2.flows
    assert flows_q2.activity_realized[capital_activity] == pytest.approx(3.0)


def test_four_stage_energy_lag_pre_p_snapshot_is_not_double_counted() -> None:
    """Regression for the round-2 pre-P double count.

    L credits the delivered 3 energy into ``state.stock_value``; the pre-P
    trace must persist that genuine state availability (3.0), not
    ``stock + delivered`` (6.0).
    """
    fixture = _energy_lag_fixture(capital_buffer=0.0)
    energy_cell = fixture.cell("organization", 2, 0, "input", "energy")
    energy_k = fixture.k_of(energy_cell)
    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(5),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=4),
    )
    p_stages = [s for s in result.trace["stages"] if s["kind"] == "P"]
    assert len(p_stages) == 2
    # P1 sees no delivered energy yet.
    assert p_stages[0]["input_available_before"][energy_k] == pytest.approx(0.0)
    assert p_stages[0]["source_eligible_before"][energy_cell] == pytest.approx(
        0.0
    )
    # P2 sees exactly the L1-delivered 3 units, in both fields.
    assert p_stages[1]["source_eligible_before"][energy_cell] == pytest.approx(
        3.0
    )
    assert p_stages[1]["input_available_before"][energy_k] == pytest.approx(
        3.0
    )
    assert p_stages[1]["used"][energy_k] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Zero source stock — stockable loop must terminate in both staged paths
# ---------------------------------------------------------------------------


def test_two_stage_zero_sources_terminates() -> None:
    fixture = _food_chain_fixture()
    raw_input_cell = fixture.cell(
        "organization", 1, 0, "input", "food", "raw"
    )
    fixture.state.stock_value[raw_input_cell] = 0.0
    fixture.state.stock_value[:] = 0.0
    flows = _run_n_quarters(fixture, LeadTimeSpec(stage_count=2), 2)
    for f in flows:
        assert f.activity_realized[0] == pytest.approx(0.0)
        assert f.delivered.sum() == pytest.approx(0.0)


def test_four_stage_zero_sources_terminates() -> None:
    fixture = _food_chain_fixture()
    fixture.state.stock_value[:] = 0.0
    flows = _run_n_quarters(fixture, LeadTimeSpec(stage_count=4), 2)
    for f in flows:
        assert f.activity_realized[0] == pytest.approx(0.0)
        assert f.delivered.sum() == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Transport fixture: opening 0 delivers 0, opening 1 delivers 10 with real
# counterparties; 4-stage total service use <= 1 quarter budget
# ---------------------------------------------------------------------------


def test_transport_opening_zero_delivers_zero_legacy() -> None:
    fixture = _transport_fixture(transport_opening=0.0)
    edge = _transport_hub_edge(fixture)
    flows = _run_n_quarters(fixture, None, 1)[0]
    assert flows.edge_allocated[edge] == pytest.approx(10.0)
    assert flows.edge_delivered[edge] == pytest.approx(0.0)
    assert flows.edge_service_used[edge] == pytest.approx(0.0)
    assert flows.edge_service_fee[edge] == pytest.approx(0.0)


def test_transport_opening_one_delivers_ten_legacy() -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    edge = _transport_hub_edge(fixture)
    seller_org = 1
    hauler_org = 4
    hub_org = 2
    flows = _run_n_quarters(fixture, None, 1)[0]
    assert flows.edge_delivered[edge] == pytest.approx(10.0)
    assert flows.edge_service_used[edge] == pytest.approx(1.0)
    fee = float(flows.edge_service_fee[edge])
    assert fee > 0.0
    assert flows.organization_sales_receipts[seller_org] == pytest.approx(10.0)
    assert flows.organization_sales_receipts[hauler_org] == pytest.approx(fee)
    assert flows.organization_purchases[hub_org] == pytest.approx(10.0 + fee)


def test_transport_two_stage_cumulative_service_use_capped() -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=2),
    )
    flows = result.flows
    assert fixture.state.completed_ticks == 1
    stage_l_entries = [
        s
        for s in result.trace["stages"]
        if s["kind"] == "L"
    ]
    assert len(stage_l_entries) == 1
    total_service = float(np.sum(flows.edge_service_used))
    assert total_service <= 1.0 + 1e-9


def test_transport_four_stage_cumulative_service_use_capped() -> None:
    fixture = _transport_fixture(transport_opening=1.0)
    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=4),
    )
    assert fixture.state.completed_ticks == 1
    flows = result.flows
    total_service = float(np.sum(flows.edge_service_used))
    assert total_service <= 1.0 + 1e-9


# ---------------------------------------------------------------------------
# Rollback on adapter failure: every state field + completed_ticks restored
# ---------------------------------------------------------------------------


def test_adapter_rollback_restores_state_on_corrupted_trace() -> None:
    """Corrupt a real L-round trace after the kernel ran; the adapter must
    reject it through ``_verify_trace``, roll back every dataclass field, and
    leave the clock at its opening value."""
    fixture = _food_chain_fixture()
    before = copy.deepcopy(fixture.state)

    import hsm_lab.institutions.lead_time_adapter as adapter_mod

    original_tick = adapter_mod.tick_material

    def _corrupting_tick(*args, **kwargs):
        flows_obj = original_tick(*args, **kwargs)
        trace_d = kwargs.get("micro_stage_trace")
        for stage in trace_d["stages"]:
            if stage["kind"] == "L":
                stage["purchases"] = [
                    float(value) + 1.0e6 for value in stage["purchases"]
                ]
                break
        return flows_obj

    adapter_mod.tick_material = _corrupting_tick  # type: ignore[assignment]
    failure = None
    try:
        execute_lead_time_tick(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            spec=LeadTimeSpec(stage_count=2),
        )
    except LeadTimeFailure as exc:
        failure = exc
    finally:
        adapter_mod.tick_material = original_tick  # type: ignore[assignment]

    assert failure is not None
    assert failure.phase == "trace"
    assert failure.failed_flows is not None
    assert isinstance(failure.failed_trace, dict)
    _assert_state_fully_restored(fixture.state, before, label="trace rollback")


def test_adapter_rollback_publishes_failed_flows_and_trace() -> None:
    """A genuine corrupted-flow rejection must publish the failed flows and
    trace for review and restore every state field exactly."""
    fixture = _food_chain_fixture()
    before = copy.deepcopy(fixture.state)

    import hsm_lab.institutions.lead_time_adapter as adapter_mod

    original_tick = adapter_mod.tick_material

    def _corrupting_tick(*args, **kwargs):
        flows_obj = original_tick(*args, **kwargs)
        flows_obj.delivered = (
            np.asarray(flows_obj.delivered, dtype=np.float64) + 1.0e6
        )
        return flows_obj

    adapter_mod.tick_material = _corrupting_tick  # type: ignore[assignment]
    failure = None
    try:
        execute_lead_time_tick(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            spec=LeadTimeSpec(stage_count=2),
        )
    except LeadTimeFailure as exc:
        failure = exc
    finally:
        adapter_mod.tick_material = original_tick  # type: ignore[assignment]

    assert failure is not None
    assert failure.failed_flows is not None
    assert isinstance(failure.failed_trace, dict)
    assert "stages" in failure.failed_trace
    _assert_state_fully_restored(fixture.state, before, label="flow rollback")


# ---------------------------------------------------------------------------
# Cash / freight envelope: cumulative purchases <= frozen envelope; later L
# cannot reuse the first L's cash after seller receipts (4-stage proof)
# ---------------------------------------------------------------------------


def test_four_stage_cash_envelope_not_refilled_by_sales_receipts() -> None:
    """Cumulative org purchases across 4 L rounds must stay within the
    frozen quarterly envelope, even when the first L already credited seller
    receipts onto the orgs' deposit.  This proves a later L cannot widen the
    envelope from inter-quarter seller receipts."""
    fixture = _food_chain_fixture()
    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=4),
    )
    frozen_envelope = float(
        np.sum(result.trace["frozen_quarter_budgets"]["organization_cash"])
    )
    cumulative_purchases = float(
        sum(
            float(np.sum(stage["purchases"]))
            for stage in result.trace["stages"]
            if stage["kind"] == "L"
        )
    )
    assert cumulative_purchases <= frozen_envelope + 1e-9


def test_four_stage_trace_envelope_shrinks_after_each_l() -> None:
    fixture = _food_chain_fixture()
    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=4),
    )
    l_stages = [
        s for s in result.trace["stages"] if s["kind"] == "L"
    ]
    assert len(l_stages) == 2
    prev_cash_before = float(
        np.sum(l_stages[0]["org_cash_envelope_before"])
    )
    prev_cash_after = float(
        np.sum(l_stages[0]["org_cash_envelope_after"])
    )
    next_cash_before = float(
        np.sum(l_stages[1]["org_cash_envelope_before"])
    )
    assert prev_cash_after == pytest.approx(next_cash_before)
    assert prev_cash_after <= prev_cash_before + 1e-9


# ---------------------------------------------------------------------------
# Paired-arm identity helper rejects asymmetric inputs
# ---------------------------------------------------------------------------


def test_paired_arm_identity_helper_accepts_identical_inputs() -> None:
    a = _food_chain_fixture()
    b = _food_chain_fixture()
    _assert_pair_identity(a, b, label="identical")
    assert True


def test_paired_arm_identity_helper_rejects_opening_stock_change() -> None:
    a = _food_chain_fixture()
    b = _food_chain_fixture()
    hub_cell = b.cell("organization", 2, 0, "wholesale", "food", "ready")
    b.state.stock_value[hub_cell] = b.state.stock_value[hub_cell] + 5.0
    with pytest.raises(AssertionError, match="paired-arm identity"):
        _assert_pair_identity(a, b, label="hub-stock")


# ---------------------------------------------------------------------------
# Defect 1: investment / housing / export / capital age install runs once for
# staged too — plan §3 closing investment pass must run for both legacy and
# staged paths.  These tests confirm staged = 2/4 install the same project WIP
# as the legacy path, so the project_capital_wip_state_binding accounting gate
# admits the staged tick.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stage_count", [None, 2, 4])
def test_installation_identity_matches_completed_capacity(stage_count) -> None:
    """Install once for legacy/2/4: capacity + completed, WIP and age exact.

    ``capital_wip_close = capital_wip_open + delivered_capital -
    completed * capital_unit`` and likewise for construction.  Legacy and
    2-stage complete the same 40 units; 4-stage completes 24 and leaves the
    uninstalled construction WIP (10 -> 4).  All three are positive, exact
    identities, not non-negativity smoke checks.
    """
    fixture = _investment_priority_fixture("investment_first")
    consumer_org = 2
    capital_g = fixture.g("capital_goods")
    construction_g = fixture.g("construction")
    capital_unit = float(fixture.parameters.capacity_capital_goods_per_unit)
    construction_unit = float(
        fixture.parameters.capacity_construction_per_unit
    )
    demand_cells = np.asarray(fixture.network.demand_cell, dtype=np.int64)
    demand_commodity = np.asarray(
        fixture.network.cell_commodity, dtype=np.int64
    )
    investment_mask = np.asarray(
        fixture.network.demand_purpose, dtype=np.int64
    ) == int(PURPOSE_CODES[RoutePurpose.INVESTMENT])

    capacity_open = float(
        fixture.state.organization_capacity[consumer_org]
    )
    capital_wip_open = float(
        fixture.state.organization_capital_wip[consumer_org]
    )
    construction_wip_open = float(
        fixture.state.organization_construction_wip[consumer_org]
    )
    age_open = float(fixture.state.organization_capital_age[consumer_org])

    if stage_count is None:
        opening = capture_material_stocks(fixture.state)
        flows = tick_material(
            fixture.state,
            fixture.forcing(4),
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
    else:
        result = execute_lead_time_tick(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            spec=LeadTimeSpec(stage_count=stage_count),
        )
        flows = result.flows

    completed = float(flows.organization_investment_completed[consumer_org])
    assert completed > 0.0
    assert float(
        fixture.state.organization_capacity[consumer_org]
    ) - capacity_open == pytest.approx(completed)
    assert float(fixture.state.organization_capital_age[consumer_org]) - (
        age_open
    ) == pytest.approx(1.0)

    delivered_capital = float(
        flows.delivered[
            investment_mask
            & (demand_commodity[demand_cells] == capital_g)
        ].sum()
    )
    delivered_construction = float(
        flows.delivered[
            investment_mask
            & (demand_commodity[demand_cells] == construction_g)
        ].sum()
    )
    assert delivered_capital > 0.0
    assert float(
        fixture.state.organization_capital_wip[consumer_org]
    ) == pytest.approx(
        capital_wip_open + delivered_capital - completed * capital_unit
    )
    assert float(
        fixture.state.organization_construction_wip[consumer_org]
    ) == pytest.approx(
        construction_wip_open
        + delivered_construction
        - completed * construction_unit
    )
    # The closing installation pass records the installed units on
    # ``flows.used`` at the investment demand cells.
    used_capital = float(
        flows.used[
            investment_mask
            & (demand_commodity[demand_cells] == capital_g)
        ].sum()
    )
    used_construction = float(
        flows.used[
            investment_mask
            & (demand_commodity[demand_cells] == construction_g)
        ].sum()
    )
    assert used_capital == pytest.approx(completed * capital_unit)
    assert used_construction == pytest.approx(completed * construction_unit)


@pytest.mark.parametrize("stage_count", [2, 4])
def test_partial_project_funded_fraction_and_wip_close(stage_count) -> None:
    """A genuinely partial project: the builder can supply only .25 of the
    .5 construction per unit.  One of two approved units completes
    (funded fraction 0.5), capacity rises by exactly one, and the unmatched
    .5 capital leaves .25 capital WIP; construction WIP closes to zero."""
    fixture = _partial_project_fixture()
    consumer_org = 2
    capital_g = fixture.g("capital_goods")
    construction_g = fixture.g("construction")
    capital_unit = float(fixture.parameters.capacity_capital_goods_per_unit)
    construction_unit = float(
        fixture.parameters.capacity_construction_per_unit
    )
    # Bind construction: no opening construction output and only .25 capacity.
    fixture.state.organization_capacity[3] = 0.25
    fixture.state.organization_labor_available[3] = 0.25
    fixture.state.stock_value[
        fixture.cell("organization", 3, 0, "output", "construction")
    ] = 0.0
    fixture.state.stock_value[
        fixture.cell("organization", 1, 0, "output", "capital_goods")
    ] = 0.25

    demand_cells = np.asarray(fixture.network.demand_cell, dtype=np.int64)
    demand_commodity = np.asarray(
        fixture.network.cell_commodity, dtype=np.int64
    )
    investment_mask = np.asarray(
        fixture.network.demand_purpose, dtype=np.int64
    ) == int(PURPOSE_CODES[RoutePurpose.INVESTMENT])

    approved_open = float(
        fixture.state.organization_project_approved[consumer_org]
    )
    capacity_open = float(
        fixture.state.organization_capacity[consumer_org]
    )
    capital_wip_open = float(
        fixture.state.organization_capital_wip[consumer_org]
    )
    construction_wip_open = float(
        fixture.state.organization_construction_wip[consumer_org]
    )
    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=stage_count),
    )
    flows = result.flows
    completed = float(flows.organization_investment_completed[consumer_org])
    funded_fraction = completed / approved_open
    assert 0.0 < funded_fraction < 1.0
    assert completed == pytest.approx(1.0)
    assert float(
        fixture.state.organization_capacity[consumer_org]
    ) - capacity_open == pytest.approx(completed)

    delivered_capital = float(
        flows.delivered[
            investment_mask
            & (demand_commodity[demand_cells] == capital_g)
        ].sum()
    )
    delivered_construction = float(
        flows.delivered[
            investment_mask
            & (demand_commodity[demand_cells] == construction_g)
        ].sum()
    )
    assert float(
        fixture.state.organization_capital_wip[consumer_org]
    ) == pytest.approx(
        capital_wip_open + delivered_capital - completed * capital_unit
    )
    assert float(
        fixture.state.organization_construction_wip[consumer_org]
    ) == pytest.approx(
        construction_wip_open
        + delivered_construction
        - completed * construction_unit
    )
    assert float(fixture.state.organization_capital_wip[consumer_org]) > 0.0
    assert float(
        fixture.state.organization_construction_wip[consumer_org]
    ) == pytest.approx(0.0)


@pytest.mark.parametrize("stage_count", [2, 4])
def test_housing_completion_credits_exact_construction(stage_count) -> None:
    """The shared closing pass turns delivered housing construction into
    dwellings exactly once: dwelling_stock rises by the delivered units,
    ``flows.used`` equals ``flows.delivered`` on the housing demand rows, and
    a positive share is allocated to the waiting household."""
    fixture = _housing_fixture()
    housing_mask = np.asarray(
        fixture.network.demand_purpose, dtype=np.int64
    ) == int(PURPOSE_CODES[RoutePurpose.HOUSING])
    initial_dwellings = float(fixture.state.dwelling_stock[0])
    initial_vacant = float(fixture.state.housing_vacant[0])
    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=stage_count),
    )
    flows = result.flows
    delivered_housing = float(flows.delivered[housing_mask].sum())
    assert delivered_housing > 0.0
    assert float(fixture.state.dwelling_stock[0]) - initial_dwellings == (
        pytest.approx(delivered_housing)
    )
    assert float(flows.used[housing_mask].sum()) == pytest.approx(
        delivered_housing
    )
    np.testing.assert_allclose(
        np.asarray(flows.used[housing_mask], dtype=np.float64),
        np.asarray(flows.delivered[housing_mask], dtype=np.float64),
    )
    assert float(flows.housing_allocated.sum()) > 0.0
    assert float(fixture.state.housing_vacant[0]) >= initial_vacant


@pytest.mark.parametrize("stage_count", [2, 4])
def test_export_used_tracks_delivered(stage_count) -> None:
    """A positive CMEA export delivery reaches the demand cell and the
    closing pass sets ``flows.used[export_demand] == delivered`` exactly."""
    fixture = _export_fixture()
    export_cell = int(
        fixture.network.export_demand_cell[0, fixture.g("energy")]
    )
    assert export_cell >= 0
    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=stage_count),
    )
    flows = result.flows
    delivered = float(flows.delivered[export_cell])
    assert delivered > 0.0
    assert delivered == pytest.approx(2.0)
    assert float(flows.used[export_cell]) == pytest.approx(delivered)
    assert (
        int(fixture.state.completed_ticks) - int(flows.tick) == 1
    )


# ---------------------------------------------------------------------------
# Defect 2: per-round logistics/handling caps in 4-stage mode
# ---------------------------------------------------------------------------


def test_four_stage_transport_per_l_cap_enforced() -> None:
    """Reviewer repro: each L may not exceed initial_pool / 2."""
    fixture = _transport_fixture(transport_opening=1.0)
    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=4),
    )
    l_usage = [
        float(
            np.sum(s["logistics_pool_before"]) - np.sum(s["logistics_pool_after"])
        )
        for s in result.trace["stages"]
        if s["kind"] == "L"
    ]
    initial_pool = np.asarray(
        result.trace["frozen_quarter_budgets"]["logistics_pool_initial"],
        dtype=np.float64,
    )
    total_pool = float(np.sum(initial_pool))
    half_pool = total_pool / 2.0
    for usage in l_usage:
        assert usage <= half_pool + 1e-6
    assert sum(l_usage) <= total_pool + 1e-6
    # Per org: cap <= initial/2 and spend <= cap.
    for stage in result.trace["stages"]:
        if stage["kind"] != "L":
            continue
        caps = np.asarray(stage["logistics_round_cap"], dtype=np.float64)
        spend = np.asarray(stage["logistics_spend"], dtype=np.float64)
        np.testing.assert_array_less(
            caps - initial_pool / 2.0, np.full_like(caps, 1e-9)
        )
        np.testing.assert_array_less(
            spend - caps, np.full_like(spend, 1e-9)
        )
        assert float(np.sum(caps)) == pytest.approx(half_pool)


def test_four_stage_transport_handling_cap_recorded() -> None:
    """Each L's handling_round_cap must be the half-tranche (n=2) and never
    exceed the recorded initial handling pool, mirroring the logistics cap."""
    fixture = _transport_fixture(transport_opening=1.0)
    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=4),
    )
    initial_handling = np.asarray(
        result.trace["frozen_quarter_budgets"]["handling_capacity_initial"],
        dtype=np.float64,
    )
    for stage in result.trace["stages"]:
        if stage["kind"] == "L":
            declared = np.asarray(stage["handling_round_cap"], dtype=np.float64)
            spend = np.asarray(stage["handling_spend"], dtype=np.float64)
            np.testing.assert_allclose(declared, initial_handling / 2.0)
            np.testing.assert_array_less(
                spend - declared, np.full_like(spend, 1e-9)
            )





def test_four_stage_transport_l1_partial_l2_uses_remainder() -> None:
    """When L1 uses less than half the pool, L2 may not exceed the cumulative
    quarterly remainder."""
    fixture = _transport_fixture(transport_opening=0.5)
    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=4),
    )
    l_stages = [s for s in result.trace["stages"] if s["kind"] == "L"]
    assert len(l_stages) == 2
    l1_before = float(np.sum(l_stages[0]["logistics_pool_before"]))
    l1_after = float(np.sum(l_stages[0]["logistics_pool_after"]))
    l2_before = float(np.sum(l_stages[1]["logistics_pool_before"]))
    assert l1_after == pytest.approx(l2_before)
    # Per-round caps sum to half-pool each:
    half_pool = float(
        np.sum(result.trace["frozen_quarter_budgets"]["logistics_pool_initial"])
        / 2.0
    )
    for stage in l_stages:
        assert float(np.sum(stage["logistics_round_cap"])) == pytest.approx(half_pool)
    l1_used = l1_before - l1_after
    # The second L can never exceed the half-tranche even if L1 was cheap.
    assert l1_used <= half_pool + 1e-6
    # And the cumulative delivered never exceeds the initial pool.
    cumulative = sum(
        float(
            np.sum(s["logistics_pool_before"]) - np.sum(s["logistics_pool_after"])
        )
        for s in l_stages
    )
    assert cumulative <= float(
        np.sum(result.trace["frozen_quarter_budgets"]["logistics_pool_initial"])
    ) + 1e-6


def test_four_stage_transport_two_l_caps_consistent() -> None:
    """Round caps declared in the trace must equal min(initial_pool/n,
    logistics_pool_before) for every L."""
    fixture = _transport_fixture(transport_opening=1.0)
    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=4),
    )
    initial_pool = np.asarray(
        result.trace["frozen_quarter_budgets"]["logistics_pool_initial"],
        dtype=np.float64,
    )
    n = 2
    expected = initial_pool / float(n)
    for stage in result.trace["stages"]:
        if stage["kind"] == "L":
            declared = np.asarray(stage["logistics_round_cap"], dtype=np.float64)
            np.testing.assert_allclose(declared, expected)


# ---------------------------------------------------------------------------
# Defect 2b: unused first-tranche capacity never enlarges the second tranche
# ---------------------------------------------------------------------------


def test_four_stage_unused_l1_cap_does_not_carry_over() -> None:
    """The clean trace keeps L2's cap at the initial/2 tranche even when L1
    spends less than its half, and a fabricated zero-L1-spend trace is
    rejected because the spend is bound to real edge service use.

    The old acceptance of an internally consistent zero-spend L1 trace is
    explicitly replaced by rejection: L1's ``edge_service_used`` is positive,
    so zero ``logistics_spend`` is physically false.
    """
    fixture = _transport_fixture(transport_opening=1.0)
    result = _run_clean_four_stage(fixture)
    trace = copy.deepcopy(result.trace)
    l_stages = [s for s in trace["stages"] if s["kind"] == "L"]
    assert len(l_stages) == 2
    l1, l2 = l_stages
    initial_pool = np.asarray(
        trace["frozen_quarter_budgets"]["logistics_pool_initial"],
        dtype=np.float64,
    )
    # Clean trace: L2's cap is the half-tranche, never the full pool.
    np.testing.assert_allclose(
        np.asarray(l2["logistics_round_cap"], dtype=np.float64),
        initial_pool / 2.0,
    )
    assert float(np.sum(l1["edge_service_used"])) > 0.0
    l1["logistics_round_cap"] = [0.0] * initial_pool.size
    l1["logistics_spend"] = [0.0] * initial_pool.size
    l1["logistics_pool_after"] = list(l1["logistics_pool_before"])
    l2["logistics_pool_before"] = list(l1["logistics_pool_after"])
    l2_spend = np.asarray(l2["logistics_spend"], dtype=np.float64)
    l2["logistics_pool_after"] = (
        np.asarray(l2["logistics_pool_before"], dtype=np.float64) - l2_spend
    ).tolist()
    assert float(np.sum(l2_spend)) > 0.0
    _assert_trace_rejected(fixture, result, trace)


def test_four_stage_handling_binding_spend_within_cap(monkeypatch) -> None:
    """Reduce handling capacity so the second quarter's L rounds genuinely
    bind: spend is positive and <= the half-tranche, and the cumulative
    quarterly handling spend never exceeds the one-quarter budget."""
    import hsm_lab.engine.material as material_mod

    monkeypatch.setattr(material_mod, "WHOLESALE_HANDLING_TOTAL", 1.0)
    monkeypatch.setattr(material_mod, "RETAIL_HANDLING_TOTAL", 1.0)
    fixture = _food_chain_fixture()
    _run_n_quarters(fixture, LeadTimeSpec(stage_count=4), 1)
    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(5),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=4),
    )
    initial_handling = np.asarray(
        result.trace["frozen_quarter_budgets"]["handling_capacity_initial"],
        dtype=np.float64,
    )
    l_stages = [s for s in result.trace["stages"] if s["kind"] == "L"]
    spends = np.vstack(
        [np.asarray(s["handling_spend"], dtype=np.float64) for s in l_stages]
    )
    assert float(np.sum(spends)) > 0.0
    for stage in l_stages:
        spend = np.asarray(stage["handling_spend"], dtype=np.float64)
        cap = np.asarray(stage["handling_round_cap"], dtype=np.float64)
        np.testing.assert_array_less(
            spend - cap, np.full_like(spend, 1e-9)
        )
        np.testing.assert_array_less(
            cap - initial_handling / 2.0,
            np.full_like(cap, 1e-9),
        )
    cumulative = spends.sum(axis=0)
    np.testing.assert_array_less(
        cumulative - initial_handling, np.full_like(cumulative, 1e-9)
    )


def test_two_bank_incoming_cannot_refill_second_l() -> None:
    """A two-bank fixture: L1 pays across banks.  Adding an incoming refill to
    L2's recorded bank-outflow envelope is rejected by inter-L continuity."""
    fixture = _two_bank_transport_fixture()
    result = _run_clean_four_stage(fixture)
    l_stages = [s for s in result.trace["stages"] if s["kind"] == "L"]
    assert len(l_stages) == 2
    assert float(np.sum(l_stages[0]["bank_outflow_spend"])) > 0.0
    corrupted = copy.deepcopy(result.trace)
    corrupted_l2 = [
        s for s in corrupted["stages"] if s["kind"] == "L"
    ][1]
    inflow = np.asarray(corrupted_l2["bank_outflow_before"], dtype=np.float64)
    inflow[0] += 1.0
    corrupted_l2["bank_outflow_before"] = inflow.tolist()
    _assert_trace_rejected(fixture, result, corrupted)


# ---------------------------------------------------------------------------
# Defect 3: real stage-budget/aggregate verification
# ---------------------------------------------------------------------------


def _run_clean_four_stage(fixture: Fixture) -> object:
    return execute_lead_time_tick(
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=4),
    )


def _corrupt_trace(result) -> dict:
    """Return a deep copy of ``result.trace`` with reviewer-style corruption."""
    import copy as _copy

    corrupted = _copy.deepcopy(result.trace)
    return corrupted


def _audit_from_trace(trace: dict) -> dict:
    """Genuine kernel-audit equivalent for direct ``_verify_trace`` tests.

    The adapter keeps the real kernel audit internal, so unit tests that
    corrupt an unrelated trace field reconstruct the audit walk from the
    *genuine* trace (the L bank delta is the exact snapshot difference).  The
    coherent +100 stock corruption test does NOT use this helper: it goes
    through the adapter and the kernel's real audit.
    """
    audit: dict = {
        "stage_count": trace["stage_count"],
        "n": trace["n"],
        "prelude_stock": np.asarray(
            trace["prelude_stock"], dtype=np.float64
        ).copy(),
        "stages": [],
    }
    previous_bank = np.asarray(
        trace["frozen_quarter_budgets"]["bank_reserves"], dtype=np.float64
    ).copy()
    for stage in trace["stages"]:
        entry: dict = {
            "index": stage["index"],
            "kind": stage["kind"],
        }
        for name in (
            "stock_before",
            "stock_after",
            "state_cash_after",
            "state_bank_reserves_after",
        ):
            entry[name] = np.asarray(stage[name], dtype=np.float64).copy()
        if stage["kind"] == "L":
            bank_after = entry["state_bank_reserves_after"]
            entry["bank_delta"] = bank_after - previous_bank
            previous_bank = bank_after
        audit["stages"].append(entry)
    return audit


def test_verify_trace_rejects_missing_frozen_budgets() -> None:
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    corrupted["frozen_quarter_budgets"] = {}
    from hsm_lab.institutions.lead_time_adapter import _verify_trace

    with pytest.raises(ResearchGateError, match="hist-lead-time-v1"):
        _verify_trace(
            spec=LeadTimeSpec(stage_count=4),
            state=fixture.state,
            network=fixture.network,
            parameters=fixture.parameters,
            flows=result.flows,
            trace=corrupted,
            audit=_audit_from_trace(result.trace),
        )


def test_verify_trace_rejects_negative_l_cash_closing() -> None:
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    # Spike a negative closing balance on the first L's cash envelope.
    for stage in corrupted["stages"]:
        if stage["kind"] == "L":
            stage["org_cash_envelope_after"] = (
                np.asarray(stage["org_cash_envelope_after"]) - 5.0
            ).tolist()
            break
    from hsm_lab.institutions.lead_time_adapter import _verify_trace

    with pytest.raises(ResearchGateError, match="hist-lead-time-v1"):
        _verify_trace(
            spec=LeadTimeSpec(stage_count=4),
            state=fixture.state,
            network=fixture.network,
            parameters=fixture.parameters,
            flows=result.flows,
            trace=corrupted,
            audit=_audit_from_trace(result.trace),
        )


def test_verify_trace_rejects_p1_produced_inflation() -> None:
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    for stage in corrupted["stages"]:
        if stage["kind"] == "P":
            inflated = [999999.0] * len(stage["produced"])
            stage["produced"] = inflated
            break
    from hsm_lab.institutions.lead_time_adapter import _verify_trace

    with pytest.raises(ResearchGateError, match="hist-lead-time-v1"):
        _verify_trace(
            spec=LeadTimeSpec(stage_count=4),
            state=fixture.state,
            network=fixture.network,
            parameters=fixture.parameters,
            flows=result.flows,
            trace=corrupted,
            audit=_audit_from_trace(result.trace),
        )


def test_verify_trace_rejects_missing_stage() -> None:
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    # Drop the last stage.
    corrupted["stages"] = corrupted["stages"][:-1]
    from hsm_lab.institutions.lead_time_adapter import _verify_trace

    with pytest.raises(ResearchGateError, match="hist-lead-time-v1"):
        _verify_trace(
            spec=LeadTimeSpec(stage_count=4),
            state=fixture.state,
            network=fixture.network,
            parameters=fixture.parameters,
            flows=result.flows,
            trace=corrupted,
            audit=_audit_from_trace(result.trace),
        )


def test_verify_trace_rejects_wrong_shape() -> None:
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    for stage in corrupted["stages"]:
        if stage["kind"] == "L":
            # Truncate allocated to a smaller shape - should trigger the
            # shape check.
            stage["allocated"] = stage["allocated"][:1]
            break
    from hsm_lab.institutions.lead_time_adapter import _verify_trace

    with pytest.raises(ResearchGateError, match="hist-lead-time-v1"):
        _verify_trace(
            spec=LeadTimeSpec(stage_count=4),
            state=fixture.state,
            network=fixture.network,
            parameters=fixture.parameters,
            flows=result.flows,
            trace=corrupted,
            audit=_audit_from_trace(result.trace),
        )


def test_verify_trace_rejects_nan_in_p_used() -> None:
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    for stage in corrupted["stages"]:
        if stage["kind"] == "P":
            used = list(stage["used"])
            used[0] = float("nan")
            stage["used"] = used
            break
    from hsm_lab.institutions.lead_time_adapter import _verify_trace

    with pytest.raises(ResearchGateError, match="hist-lead-time-v1"):
        _verify_trace(
            spec=LeadTimeSpec(stage_count=4),
            state=fixture.state,
            network=fixture.network,
            parameters=fixture.parameters,
            flows=result.flows,
            trace=corrupted,
            audit=_audit_from_trace(result.trace),
        )


@pytest.mark.parametrize("field", ("state_cash_after", "state_bank_reserves_after"))
@pytest.mark.parametrize("value", (float("nan"), float("inf")))
def test_verify_trace_rejects_nonfinite_p_snapshots(field: str, value: float) -> None:
    """A NaN/inf P cash or bank snapshot cannot equal the genuine audit."""
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = copy.deepcopy(result.trace)
    p_stage = next(stage for stage in corrupted["stages"] if stage["kind"] == "P")
    values = np.asarray(p_stage[field], dtype=np.float64).copy()
    values[0] = value
    p_stage[field] = values.tolist()
    _assert_trace_rejected(fixture, result, corrupted)


@pytest.mark.parametrize("field", ("state_cash_after", "state_bank_reserves_after"))
def test_adapter_rolls_back_nonfinite_p_snapshot(field: str) -> None:
    """The adapter must reject a non-finite trace snapshot and roll back."""
    fixture = _food_chain_fixture()
    before = copy.deepcopy(fixture.state)

    import hsm_lab.institutions.lead_time_adapter as adapter_mod

    original_tick = adapter_mod.tick_material

    def _nonfinite_tick(*args, **kwargs):
        flows_obj = original_tick(*args, **kwargs)
        trace_d = kwargs.get("micro_stage_trace")
        if trace_d:
            p_stage = next(
                stage for stage in trace_d["stages"] if stage["kind"] == "P"
            )
            values = np.asarray(p_stage[field], dtype=np.float64).copy()
            values[0] = float("nan")
            p_stage[field] = values.tolist()
        return flows_obj

    adapter_mod.tick_material = _nonfinite_tick  # type: ignore[assignment]
    failure = None
    try:
        execute_lead_time_tick(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            spec=LeadTimeSpec(stage_count=4),
        )
    except LeadTimeFailure as exc:
        failure = exc
    finally:
        adapter_mod.tick_material = original_tick  # type: ignore[assignment]

    assert failure is not None
    assert failure.phase == "trace"
    assert "non-finite" in str(failure.cause)
    _assert_state_fully_restored(
        fixture.state, before, label=f"non-finite {field}"
    )


def test_adapter_rollback_on_real_flow_corruption() -> None:
    """Replace the forced _verify_trace monkeypatch with a genuine flow
    corruption: inflate ``flows.delivered`` after the staged kernel ran but
    before the gate runs.  Adapter must roll back ALL dataclass fields,
    publish failed flows/trace, and leave ``completed_ticks`` untouched."""
    fixture = _food_chain_fixture()
    before = copy.deepcopy(fixture.state)

    import hsm_lab.institutions.lead_time_adapter as adapter_mod

    original_tick = adapter_mod.tick_material

    def _corrupting_tick(*args, **kwargs):
        result_flows = original_tick(*args, **kwargs)
        # Inflate flows.delivered on the demand axis beyond what could have
        # been allocated/delivered; this is the kind of inconsistency that
        # the gate must catch.
        result_flows.delivered = (
            np.asarray(result_flows.delivered, dtype=np.float64) + 1e6
        )
        return result_flows

    adapter_mod.tick_material = _corrupting_tick  # type: ignore[assignment]
    failure = None
    try:
        execute_lead_time_tick(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            spec=LeadTimeSpec(stage_count=4),
        )
    except LeadTimeFailure as exc:
        failure = exc
    finally:
        adapter_mod.tick_material = original_tick  # type: ignore[assignment]

    assert failure is not None
    assert failure.failed_flows is not None
    assert isinstance(failure.failed_trace, dict)
    assert "stages" in failure.failed_trace
    # Every dataclass field + completed_ticks restored.
    assert int(fixture.state.completed_ticks) == int(before.completed_ticks)
    for field in (
        "stock_value",
        "organization_cash",
        "household_cash",
        "treasury_deposit",
        "bank_reserves",
        "bank_deposit_liability",
        "household_deferred_receipt",
        "organization_capacity",
        "organization_capital_wip",
        "organization_construction_wip",
        "organization_project_approved",
        "organization_capital_age",
        "organization_shortage_expectation",
        "dwelling_stock",
        "housing_vacant",
    ):
        assert np.array_equal(
            np.asarray(getattr(fixture.state, field), dtype=np.float64),
            np.asarray(getattr(before, field), dtype=np.float64),
        ), f"field {field} did not roll back"


def test_adapter_rollback_on_real_trace_corruption() -> None:
    """Corrupt the trace after the staged kernel ran but before _verify_trace
    by routing tick_material through a wrapper that injects a malformed
    trace stage.  Adapter must roll back state and surface LeadTimeFailure."""
    fixture = _transport_fixture(transport_opening=1.0)
    before = copy.deepcopy(fixture.state)

    import hsm_lab.institutions.lead_time_adapter as adapter_mod

    original_tick = adapter_mod.tick_material

    def _trace_corrupting_tick(*args, **kwargs):
        flows_obj = original_tick(*args, **kwargs)
        trace_d = kwargs.get("micro_stage_trace")
        if trace_d and trace_d.get("stages"):
            # Inflate the first L's logistics_spend above the frozen pool
            # by a factor of 1000; the per-L reconciliation must reject.
            for stage in trace_d["stages"]:
                if stage.get("kind") == "L":
                    spend = list(stage.get("logistics_spend", []))
                    spend[0] = 1.0e6
                    stage["logistics_spend"] = spend
                    break
        return flows_obj

    adapter_mod.tick_material = _trace_corrupting_tick  # type: ignore[assignment]
    failure = None
    try:
        execute_lead_time_tick(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            spec=LeadTimeSpec(stage_count=4),
        )
    except LeadTimeFailure as exc:
        failure = exc
    finally:
        adapter_mod.tick_material = original_tick  # type: ignore[assignment]

    assert failure is not None
    assert failure.failed_trace is not None
    assert int(fixture.state.completed_ticks) == int(before.completed_ticks)
    assert np.array_equal(
        np.asarray(fixture.state.stock_value, dtype=np.float64),
        np.asarray(before.stock_value, dtype=np.float64),
    )


def test_verify_trace_rejects_negative_l1_cash_envelope() -> None:
    """Reviewer corruption 1: subtract 1e9 from L1 opening and closing cash."""
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    for stage in corrupted["stages"]:
        if stage["kind"] == "L":
            stage["org_cash_envelope_before"] = (
                np.asarray(stage["org_cash_envelope_before"]) - 1.0e9
            ).tolist()
            stage["org_cash_envelope_after"] = (
                np.asarray(stage["org_cash_envelope_after"]) - 1.0e9
            ).tolist()
            break
    _assert_trace_rejected(fixture, result, corrupted)


def test_verify_trace_rejects_refilled_second_l_cash_envelope() -> None:
    """Reviewer corruption 2: add 100 to both L2 opening and closing (an
    unearned inter-stage refill with an unchanged before-after gap)."""
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    l_stages = [s for s in corrupted["stages"] if s["kind"] == "L"]
    assert len(l_stages) == 2
    for name in ("org_cash_envelope_before", "org_cash_envelope_after"):
        refilled = np.asarray(l_stages[1][name], dtype=np.float64).copy()
        refilled[0] += 100.0
        l_stages[1][name] = refilled.tolist()
    _assert_trace_rejected(fixture, result, corrupted)


def test_verify_trace_rejects_reversed_stage_order() -> None:
    """Reviewer corruption 3: reverse the stages list."""
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    corrupted["stages"].reverse()
    _assert_trace_rejected(fixture, result, corrupted)


def test_verify_trace_rejects_per_stage_recipe_substitution() -> None:
    """Reviewer corruption 4: P1 used 6.25 -> 7.25 and P2 3.75 -> 2.75
    (same quarterly total, wrong per-stage Leontief recipe)."""
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    p_stages = [s for s in corrupted["stages"] if s["kind"] == "P"]
    assert p_stages[0]["used"][0] == pytest.approx(6.25)
    assert p_stages[1]["used"][0] == pytest.approx(3.75)
    p_stages[0]["used"][0] = 7.25
    p_stages[1]["used"][0] = 2.75
    _assert_trace_rejected(fixture, result, corrupted)


def test_verify_trace_rejects_zero_cap_with_positive_spend() -> None:
    """Reviewer corruption 5: L1 logistics cap 0 while spend is 0.5."""
    fixture = _transport_fixture(transport_opening=1.0)
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    hauler_org = 4
    for stage in corrupted["stages"]:
        if stage["kind"] == "L":
            caps = np.asarray(stage["logistics_round_cap"], dtype=np.float64)
            assert float(np.asarray(stage["logistics_spend"])[hauler_org]) > 0.0
            caps[hauler_org] = 0.0
            stage["logistics_round_cap"] = caps.tolist()
            break
    _assert_trace_rejected(fixture, result, corrupted)


def test_verify_trace_rejects_full_pool_cap_in_four_stage() -> None:
    """Reviewer corruption 6: L1 logistics cap is the full quarterly pool
    instead of the half-tranche."""
    fixture = _transport_fixture(transport_opening=1.0)
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    hauler_org = 4
    for stage in corrupted["stages"]:
        if stage["kind"] == "L":
            caps = np.asarray(stage["logistics_round_cap"], dtype=np.float64)
            caps[hauler_org] = 1.0
            stage["logistics_round_cap"] = caps.tolist()
            break
    _assert_trace_rejected(fixture, result, corrupted)


def test_verify_trace_rejects_zeroed_frozen_cash_budgets() -> None:
    """Reviewer corruption 7: zero every frozen organization-cash budget
    while the quarterly purchases are positive."""
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    budgets = corrupted["frozen_quarter_budgets"]["organization_cash"]
    corrupted["frozen_quarter_budgets"]["organization_cash"] = [
        0.0 for _ in budgets
    ]
    assert any(
        float(np.sum(stage["purchases"])) > 0.0
        for stage in corrupted["stages"]
        if stage["kind"] == "L"
    )
    _assert_trace_rejected(fixture, result, corrupted)


def test_verify_trace_rejects_non_retail_destination_credit() -> None:
    """Only retail-owned destination cells may credit an L source pool."""
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    non_retail_cell = fixture.cell(
        "organization", 1, 0, "output", "food", "ready"
    )
    for stage in corrupted["stages"]:
        if stage["kind"] == "L":
            credit = np.asarray(
                stage["destination_credit"], dtype=np.float64
            ).copy()
            after = np.asarray(
                stage["source_eligible_after"], dtype=np.float64
            ).copy()
            credit[non_retail_cell] += 10.0
            after[non_retail_cell] += 10.0
            stage["destination_credit"] = credit.tolist()
            stage["source_eligible_after"] = after.tolist()
            break
    _assert_trace_rejected(fixture, result, corrupted)


def test_verify_trace_rejects_zero_logistics_spend_with_service_use() -> None:
    """Reviewer repro 1: both L stages report zero logistics spend and an
    unchanged pool while ``flows.edge_service_used`` is really 1.0.

    The trace is internally consistent (before == after, zero spend), so only
    the new per-edge binding to delivered service use can reject it.
    """
    fixture = _transport_fixture(transport_opening=1.0)
    result = _run_clean_four_stage(fixture)
    assert float(np.sum(result.flows.edge_service_used)) == pytest.approx(1.0)
    corrupted = _corrupt_trace(result)
    initial_pool = np.asarray(
        corrupted["frozen_quarter_budgets"]["logistics_pool_initial"],
        dtype=np.float64,
    )
    l_stages = [s for s in corrupted["stages"] if s["kind"] == "L"]
    assert len(l_stages) == 2
    for stage in l_stages:
        assert float(np.sum(stage["edge_service_used"])) > 0.0
        stage["logistics_spend"] = [0.0] * int(initial_pool.size)
        stage["logistics_pool_before"] = initial_pool.tolist()
        stage["logistics_pool_after"] = initial_pool.tolist()
    _assert_trace_rejected(fixture, result, corrupted)


def test_verify_trace_rejects_zero_source_destination_with_deliveries() -> None:
    """Reviewer repro 2: both L stages report zero source outflow and zero
    destination credit while the real edge deliveries total 8.0 and the
    genuine per-L source outflows are [5.0, 3.0].

    ``source_eligible_after`` is set equal to ``source_eligible_before`` so
    the old identity passes; the per-edge bincount binding must reject.
    """
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    assert float(np.sum(result.flows.edge_delivered)) == pytest.approx(8.0)
    corrupted = _corrupt_trace(result)
    cell_count = int(np.asarray(fixture.network.cell_commodity).shape[0])
    l_stages = [s for s in corrupted["stages"] if s["kind"] == "L"]
    assert len(l_stages) == 2
    genuine_outflows = [
        float(np.sum(stage["source_outflow"])) for stage in l_stages
    ]
    np.testing.assert_allclose(genuine_outflows, [5.0, 3.0])
    for stage in l_stages:
        stage["source_outflow"] = [0.0] * cell_count
        stage["destination_credit"] = [0.0] * cell_count
        stage["source_eligible_after"] = list(stage["source_eligible_before"])
    _assert_trace_rejected(fixture, result, corrupted)


def test_envelope_binding_cash_limit_blocks_second_l_refill() -> None:
    """Build a binding cash-limited buyer case to prove receipts do not
    refill the cumulative quarterly envelope.  ``_transport_fixture`` with
    a tiny logistics transport_opening already exhausts a small pool; the
    second L's receipt cannot replenish the first L's quota."""
    fixture = _transport_fixture(transport_opening=1.0)
    # Tighten the carrier's org_cash so receipt/incoming cannot widen the
    # first L's envelope.  Adjust the bank's deposit liability downward by
    # exactly the same amount so the deposit-cover gate stays valid.
    hauler_index = 4
    hub_index = 2
    org_cash = np.asarray(
        fixture.state.organization_cash, dtype=np.float64
    ).copy()
    bank_reserves = np.asarray(
        fixture.state.bank_reserves, dtype=np.float64
    ).copy()
    bank_dep = np.asarray(
        fixture.state.bank_deposit_liability, dtype=np.float64
    ).copy()
    bank_equity = np.asarray(
        fixture.state.bank_equity, dtype=np.float64
    ).copy()
    bank_loans = np.asarray(
        fixture.state.bank_loan_asset, dtype=np.float64
    ).copy()
    bank_interest = np.asarray(
        fixture.state.bank_interest_receivable, dtype=np.float64
    ).copy()
    cash_diff = float(org_cash[hauler_index] - 1.0)
    org_cash[hauler_index] = 1.0
    # Reduce deposit liability by the same amount as the cash we extracted,
    # so the cover identity remains balanced at opening.
    bank_reserves[0] = bank_reserves[0] - cash_diff
    bank_dep[0] = bank_dep[0] - cash_diff
    # bank_loan_asset stays - asset drop matches liability drop.
    fixture.state.organization_cash = org_cash
    fixture.state.bank_reserves = bank_reserves
    fixture.state.bank_deposit_liability = bank_dep
    fixture.state.bank_equity = bank_equity
    fixture.state.bank_loan_asset = bank_loans
    fixture.state.bank_interest_receivable = bank_interest

    result = execute_lead_time_tick(
        fixture.state,
        fixture.forcing(4),
        fixture.parameters,
        fixture.network,
        spec=LeadTimeSpec(stage_count=4),
    )
    flows = result.flows
    # Cumulative envelope: each L's after <= before, and the cumulative
    # hub/buyer purchase total stays bounded by the trace-recorded summed
    # per-L ``purchases``.
    l_stages = [s for s in result.trace["stages"] if s["kind"] == "L"]
    assert len(l_stages) == 2
    sum_purchases_hub = sum(
        float(s["purchases"][hub_index]) for s in l_stages
    )
    assert float(l_stages[0]["purchases"][hub_index]) > 0.0
    assert sum_purchases_hub > 0.0
    # ``flows.organization_purchases`` must equal the sum of L-round
    # purchases (no widening between rounds).
    assert float(flows.organization_purchases[hub_index]) == pytest.approx(
        sum_purchases_hub, abs=1e-6
    )
    # Per-org inter-L continuity: L2 starts exactly where L1 stopped, so the
    # first L's spend cannot be funded a second time.
    np.testing.assert_allclose(
        np.asarray(l_stages[1]["org_cash_envelope_before"], dtype=np.float64),
        np.asarray(l_stages[0]["org_cash_envelope_after"], dtype=np.float64),
    )
    second_before = np.asarray(
        l_stages[1]["org_cash_envelope_before"], dtype=np.float64
    )
    second_purchases = np.asarray(
        l_stages[1]["purchases"], dtype=np.float64
    )
    assert float(second_before[hub_index]) > 0.0
    assert float(second_purchases[hub_index]) <= float(
        second_before[hub_index]
    ) + 1e-9
    frozen_cash = float(
        np.sum(
            result.trace["frozen_quarter_budgets"]["organization_cash"]
        )
    )
    assert sum_purchases_hub <= frozen_cash + 1e-9
    assert float(np.sum(second_purchases)) <= float(
        np.sum(second_before)
    ) + 1e-9
    del hauler_index


# ---------------------------------------------------------------------------
# Round 4: physical stock path, omitted trace, effective handling and
# real cash/bank evidence
# ---------------------------------------------------------------------------


def _run_staged_kernel(
    fixture: Fixture,
    stage_count: int,
    trace: dict | None,
):
    """Run one real staged kernel tick with an optional trace argument."""
    forcing = fixture.forcing(4)
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(
        fixture.state,
        forcing,
        fixture.parameters,
        fixture.network,
        micro_stage_count=stage_count,
        micro_stage_trace=trace,
    )
    summary = accounting.check_material_invariants(
        opening,
        fixture.state,
        flows,
        fixture.parameters,
        fixture.network,
    )
    assert summary.max_material_abs_residual < 1e-8
    fixture.state.completed_ticks = int(fixture.state.completed_ticks) + 1
    return flows


@pytest.mark.parametrize("stage_count", [2, 4])
def test_staged_kernel_omitted_trace_is_accepted_and_identical(
    stage_count: int,
) -> None:
    """A valid 2/4-stage tick must run with ``micro_stage_trace=None`` and
    produce exactly the same canonical state/flows as a traced tick."""
    traced = _food_chain_fixture()
    untraced = _food_chain_fixture()
    trace: dict = {}
    traced_flows = _run_staged_kernel(traced, stage_count, trace)
    untraced_flows = _run_staged_kernel(untraced, stage_count, None)
    assert trace["stage_count"] == stage_count
    assert len(trace["stages"]) == stage_count
    assert "prelude_stock" in trace
    assert canonical_material_bytes(
        traced.state, traced_flows
    ) == canonical_material_bytes(untraced.state, untraced_flows)


@pytest.mark.parametrize("stage_count", [2, 4])
def test_zero_handling_coefficients_clean_trace_passes(
    stage_count: int,
) -> None:
    """All-zero handling coefficients are normalized to 1.0 by the kernel;
    the verifier must use the same effective coefficient and accept the
    clean trace (Q2 delivers through the wholesale/retail chain)."""
    fixture = _food_chain_fixture()
    fixture.parameters = fixture.parameters.model_copy(
        update={
            "handling_work_per_unit": [
                0.0
                for _ in fixture.parameters.handling_work_per_unit
            ]
        }
    )
    spends = []
    for _ in range(2):
        result = execute_lead_time_tick(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            spec=LeadTimeSpec(stage_count=stage_count),
        )
        spends.extend(
            float(np.sum(stage["handling_spend"]))
            for stage in result.trace["stages"]
            if stage["kind"] == "L"
        )
    assert max(spends) > 0.0


def test_verify_trace_rejects_p1_p2_payload_swap() -> None:
    """Swapping the P1/P2 payloads (keeping index/kind) preserves the
    quarterly totals but breaks the real stock path: P1 would open at the
    post-L1 stock instead of the recorded prelude stock."""
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    p_stages = [s for s in corrupted["stages"] if s["kind"] == "P"]
    assert len(p_stages) == 2
    payload_keys = [
        key for key in p_stages[0] if key not in ("index", "kind")
    ]
    for key in payload_keys:
        p_stages[0][key], p_stages[1][key] = (
            p_stages[1][key],
            p_stages[0][key],
        )
    _assert_trace_rejected(fixture, result, corrupted)


def test_verify_trace_rejects_missing_prelude_stock() -> None:
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    corrupted.pop("prelude_stock")
    _assert_trace_rejected(fixture, result, corrupted)


def test_verify_trace_rejects_prelude_stock_shift() -> None:
    fixture = _food_chain_fixture()
    result = _run_clean_four_stage(fixture)
    corrupted = _corrupt_trace(result)
    prelude = np.asarray(corrupted["prelude_stock"], dtype=np.float64)
    shifted = prelude.copy()
    shifted[int(np.flatnonzero(prelude > 0.0)[0])] += 1.0
    corrupted["prelude_stock"] = shifted.tolist()
    _assert_trace_rejected(fixture, result, corrupted)


def test_adapter_rollback_on_p_payload_swap() -> None:
    """A swapped P payload injected after the real tick must be rejected by
    the trace gate and roll back every MaterialState field and the clock."""
    fixture = _food_chain_fixture()
    before = copy.deepcopy(fixture.state)

    import hsm_lab.institutions.lead_time_adapter as adapter_mod

    original_tick = adapter_mod.tick_material

    def _swap_p_payloads(*args, **kwargs):
        flows_obj = original_tick(*args, **kwargs)
        trace_d = kwargs.get("micro_stage_trace")
        if trace_d:
            p_stages = [
                stage
                for stage in trace_d["stages"]
                if stage["kind"] == "P"
            ]
            if len(p_stages) == 2:
                payload_keys = [
                    key
                    for key in p_stages[0]
                    if key not in ("index", "kind")
                ]
                for key in payload_keys:
                    p_stages[0][key], p_stages[1][key] = (
                        p_stages[1][key],
                        p_stages[0][key],
                    )
        return flows_obj

    adapter_mod.tick_material = _swap_p_payloads  # type: ignore[assignment]
    failure = None
    try:
        execute_lead_time_tick(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            spec=LeadTimeSpec(stage_count=4),
        )
    except LeadTimeFailure as exc:
        failure = exc
    finally:
        adapter_mod.tick_material = original_tick  # type: ignore[assignment]

    assert failure is not None
    assert failure.phase == "trace"
    _assert_state_fully_restored(fixture.state, before, label="p swap")


def test_constrained_hub_cash_receipts_do_not_refill_envelope() -> None:
    """A hub with only 8 units of cash and opening stock sells 5 in L1 while
    buying its own inputs.  Its real cash therefore rises, but the frozen
    quarterly envelope keeps falling: L2 starts from L1's envelope closing
    value, never from the receipts."""
    fixture = _food_chain_fixture()
    hub_index = 2
    hub_stock_cell = fixture.cell(
        "organization", hub_index, 0, "wholesale", "food", "ready"
    )
    fixture.state.stock_value[hub_stock_cell] = 5.0
    cash = np.asarray(
        fixture.state.organization_cash, dtype=np.float64
    ).copy()
    constrained_cash = 8.0
    delta = float(cash[hub_index] - constrained_cash)
    cash[hub_index] = constrained_cash
    fixture.state.organization_cash = cash
    reserves = np.asarray(
        fixture.state.bank_reserves, dtype=np.float64
    ).copy()
    deposits = np.asarray(
        fixture.state.bank_deposit_liability, dtype=np.float64
    ).copy()
    reserves[0] -= delta
    deposits[0] -= delta
    fixture.state.bank_reserves = reserves
    fixture.state.bank_deposit_liability = deposits
    fixture.state.credit_fund = 0.0
    fixture.parameters = fixture.parameters.model_copy(
        update={
            "credit_envelope_fraction": 0.0,
            "input_credit_earmark_fraction": 0.0,
        }
    )

    result = _run_clean_four_stage(fixture)
    l_stages = [s for s in result.trace["stages"] if s["kind"] == "L"]
    assert len(l_stages) == 2
    l1, l2 = l_stages
    frozen_hub = float(
        result.trace["frozen_quarter_budgets"]["organization_cash"][
            hub_index
        ]
    )
    assert frozen_hub == pytest.approx(constrained_cash)
    assert float(l1["purchases"][hub_index]) > 0.0
    assert float(l2["purchases"][hub_index]) > 0.0
    assert float(l1["sales"][hub_index]) > 0.0
    np.testing.assert_allclose(
        np.asarray(l2["org_cash_envelope_before"], dtype=np.float64),
        np.asarray(l1["org_cash_envelope_after"], dtype=np.float64),
    )
    total_hub_purchases = float(
        l1["purchases"][hub_index]
    ) + float(l2["purchases"][hub_index])
    assert total_hub_purchases <= frozen_hub + 1e-9
    # Real state cash at the L2 boundary is the L1 state cash after; it is
    # strictly above the frozen envelope because the L1 sale receipts arrived.
    l1_state_cash = float(l1["state_cash_after"][hub_index])
    l2_envelope_before = float(l2["org_cash_envelope_before"][hub_index])
    assert l1_state_cash > l2_envelope_before + 1e-9
    assert l1_state_cash == pytest.approx(
        constrained_cash
        + float(l1["sales"][hub_index])
        - float(l1["purchases"][hub_index])
    )


def _two_bank_receipt_fixture() -> Fixture:
    """Two banks with the hub at bank 1 and its seller/retail buyer at bank 0.

    L1 pays the cross-bank seller from bank 1; L2 receives the cross-bank
    retail sale into bank 1, so real reserves rise while its frozen outflow
    envelope cannot.
    """
    seller = producer(2, "energy_generation", region="R1", bank_id=0)
    wholesale = hub(3, region="R0").model_copy(update={"bank_id": 1})
    shop = retail(4, region="R0")
    hauler = transport(5, region="R0", capacity=1.0)
    technologies = [
        idle_source_tech("energy_generation", "energy"),
        tech(
            "freight_transport",
            inputs=(("durable_goods", 1.0),),
            outputs=(("services_transport", "standard", 1.0),),
        ),
    ]
    parameters = default_params(
        desired_per_person=[0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        transport_per_unit=0.1,
    )
    fixture = Fixture(
        [bank(0), bank(1), seller, wholesale, shop, hauler],
        technologies,
        region_ids=("R0", "R1"),
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 25.0)],
        household_cash=1000.0,
        ticks=1,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[
        fixture.cell("organization", 2, 1, "output", "energy")
    ] = 10.0
    fixture.state.stock_value[
        fixture.cell("organization", 5, 0, "input", "durable_goods")
    ] = 1.0
    fixture.state.stock_value[
        fixture.cell("organization", 3, 0, "wholesale", "energy")
    ] = 5.0
    return fixture


def test_two_bank_receipts_do_not_refill_bank_envelope() -> None:
    """Bank 1 pays the cross-bank L1 purchase, then receives the cross-bank
    L2 retail sale.  Its real reserves exceed the frozen outflow envelope,
    but the envelope never refills and cumulative outgoing stays bounded."""
    fixture = _two_bank_receipt_fixture()
    assert int(fixture.state.organization_bank[3]) == 1
    assert int(fixture.state.organization_bank[2]) == 0
    result = _run_clean_four_stage(fixture)
    l_stages = [s for s in result.trace["stages"] if s["kind"] == "L"]
    assert len(l_stages) == 2
    l1, l2 = l_stages
    frozen = np.asarray(
        result.trace["frozen_quarter_budgets"]["bank_reserves"],
        dtype=np.float64,
    )
    np.testing.assert_allclose(
        np.asarray(l1["bank_outflow_before"], dtype=np.float64), frozen
    )
    np.testing.assert_allclose(
        np.asarray(l2["bank_outflow_before"], dtype=np.float64),
        np.asarray(l1["bank_outflow_after"], dtype=np.float64),
    )
    cumulative_spend = np.asarray(
        l1["bank_outflow_spend"], dtype=np.float64
    ) + np.asarray(l2["bank_outflow_spend"], dtype=np.float64)
    assert bool(np.all(cumulative_spend <= frozen + 1e-9))
    bank = 1
    assert float(l1["bank_outflow_spend"][bank]) > 0.0
    # The L1 sale into bank 1 raises real reserves above the frozen outflow
    # envelope; L2's envelope nevertheless starts at L1's closing envelope.
    assert float(l1["state_bank_reserves_after"][bank]) > float(
        l1["bank_outflow_after"][bank]
    ) + 1e-9
    assert float(l2["state_bank_reserves_after"][bank]) > float(
        l2["bank_outflow_after"][bank]
    ) + 1e-9
    assert float(l2["bank_outflow_after"][bank]) <= float(
        l2["bank_outflow_before"][bank]
    ) + 1e-9


# ---------------------------------------------------------------------------
# Round-5: independent kernel audit and genuinely binding envelope helpers
# ---------------------------------------------------------------------------


def _cash_binding_hub_fixture() -> Fixture:
    """Balanced hub: it buys 11 units over two L rounds and sells 10.

    Cash is frozen at 5.0, so L1 consumes part of the envelope and L2's real
    cash (after L1 sale receipts) exceeds the remaining envelope.  L2 demand
    is larger than the remainder, so the envelope binds exactly.
    """
    fixture = _transport_fixture(transport_opening=1.0)
    hub_index = 2
    fixture.state.stock_value[
        fixture.cell("organization", hub_index, 0, "wholesale", "energy")
    ] = 10.0
    cash = np.asarray(fixture.state.organization_cash, dtype=np.float64).copy()
    constrained_cash = 5.0
    delta = float(cash[hub_index] - constrained_cash)
    cash[hub_index] = constrained_cash
    fixture.state.organization_cash = cash
    reserves = np.asarray(
        fixture.state.bank_reserves, dtype=np.float64
    ).copy()
    deposits = np.asarray(
        fixture.state.bank_deposit_liability, dtype=np.float64
    ).copy()
    reserves[0] -= delta
    deposits[0] -= delta
    fixture.state.bank_reserves = reserves
    fixture.state.bank_deposit_liability = deposits
    fixture.state.credit_fund = 0.0
    fixture.parameters = fixture.parameters.model_copy(
        update={
            "credit_envelope_fraction": 0.0,
            "input_credit_earmark_fraction": 0.0,
        }
    )
    return fixture


def _bank_binding_two_bank_fixture() -> Fixture:
    """Two-bank fixture whose bank-1 reserves are small but backed by loans.

    Bank 1 must fund an L1 cross-bank purchase, then receives a cross-bank
    sale; its L2 outgoing demand exceeds the remaining frozen outflow
    envelope while real reserves are above it.
    """
    fixture = _two_bank_receipt_fixture()
    reserves = np.asarray(
        fixture.state.bank_reserves, dtype=np.float64
    ).copy()
    loans = np.asarray(
        fixture.state.bank_loan_asset, dtype=np.float64
    ).copy()
    constrained_reserves = 10.0
    delta = float(reserves[1] - constrained_reserves)
    reserves[1] = constrained_reserves
    loans[1] += delta
    fixture.state.bank_reserves = reserves
    fixture.state.bank_loan_asset = loans
    fixture.state.credit_fund = 0.0
    fixture.parameters = fixture.parameters.model_copy(
        update={
            "credit_envelope_fraction": 0.0,
            "input_credit_earmark_fraction": 0.0,
        }
    )
    return fixture


def test_envelope_helper_removal_increases_constrained_hub_purchases(
    monkeypatch,
) -> None:
    """The cash-envelope helper is genuinely binding, not recorded arithmetic.

    The clean run spends only the cumulative quarterly remainder in L2 even
    though real organization cash (L1 sale receipts) is higher.  Replacing
    ``_frozen_envelope_capacity`` with one that ignores ``remaining`` lets L2
    attempt more purchases and breaks the recorded before-after identity; the
    adapter rejects that result.
    """
    import hsm_lab.engine.material as material_mod

    hub_index = 2
    clean_fixture = _cash_binding_hub_fixture()
    clean = _run_clean_four_stage(clean_fixture)
    l_stages = [s for s in clean.trace["stages"] if s["kind"] == "L"]
    assert len(l_stages) == 2
    l1, l2 = l_stages
    frozen = float(
        clean.trace["frozen_quarter_budgets"]["organization_cash"][hub_index]
    )
    assert frozen == pytest.approx(5.0)
    l1_purchases = float(l1["purchases"][hub_index])
    l2_purchases = float(l2["purchases"][hub_index])
    assert l1_purchases > 0.0
    assert l2_purchases > 0.0
    np.testing.assert_allclose(
        np.asarray(l2["org_cash_envelope_before"], dtype=np.float64),
        np.asarray(l1["org_cash_envelope_after"], dtype=np.float64),
    )
    l1_state_cash = float(l1["state_cash_after"][hub_index])
    l2_envelope_before = float(l2["org_cash_envelope_before"][hub_index])
    assert l1_state_cash > l2_envelope_before + 1e-9
    assert l1_purchases + l2_purchases <= frozen + 1e-9

    patched_fixture = _cash_binding_hub_fixture()
    trace: dict = {}
    audit: dict = {}
    with monkeypatch.context() as patcher:
        patcher.setattr(
            material_mod,
            "_frozen_envelope_capacity",
            lambda actual, remaining: np.asarray(actual, dtype=np.float64),
        )
        tick_material(
            patched_fixture.state,
            patched_fixture.forcing(4),
            patched_fixture.parameters,
            patched_fixture.network,
            micro_stage_count=4,
            micro_stage_trace=trace,
            micro_stage_audit=audit,
        )
        with pytest.raises(LeadTimeFailure):
            execute_lead_time_tick(
                _cash_binding_hub_fixture().state,
                patched_fixture.forcing(4),
                patched_fixture.parameters,
                patched_fixture.network,
                spec=LeadTimeSpec(stage_count=4),
            )

    patched_l = [s for s in trace["stages"] if s["kind"] == "L"]
    assert len(patched_l) == 2
    patched_l2_purchases = float(patched_l[1]["purchases"][hub_index])
    assert patched_l2_purchases > l2_purchases + 1e-6
    # The unconstrained round over-spends the frozen remainder, so the
    # recorded before-after gap can no longer equal its purchases.
    patched_before = float(
        patched_l[1]["org_cash_envelope_before"][hub_index]
    )
    patched_after = float(
        patched_l[1]["org_cash_envelope_after"][hub_index]
    )
    assert abs((patched_before - patched_after) - patched_l2_purchases) > 1e-6


def test_envelope_helper_removal_increases_two_bank_outgoing(monkeypatch) -> None:
    """The bank-envelope helper is genuinely binding for cross-bank outgoing.

    Bank 1's real reserves after L1 (including the cross-bank sale receipt)
    exceed the frozen L2 outflow remainder, yet the clean run spends only the
    remainder.  Ignoring ``remaining`` raises L2 outgoing above the frozen
    envelope and breaks the before-after identity; the adapter rejects it.
    """
    import hsm_lab.engine.material as material_mod

    bank_index = 1
    clean = _run_clean_four_stage(_bank_binding_two_bank_fixture())
    l_stages = [s for s in clean.trace["stages"] if s["kind"] == "L"]
    assert len(l_stages) == 2
    l1, l2 = l_stages
    frozen = np.asarray(
        clean.trace["frozen_quarter_budgets"]["bank_reserves"],
        dtype=np.float64,
    )
    l1_spend = float(l1["bank_outflow_spend"][bank_index])
    l2_spend = float(l2["bank_outflow_spend"][bank_index])
    assert l1_spend > 0.0
    assert l2_spend > 0.0
    np.testing.assert_allclose(
        np.asarray(l2["bank_outflow_before"], dtype=np.float64),
        np.asarray(l1["bank_outflow_after"], dtype=np.float64),
    )
    cumulative = np.asarray(
        l1["bank_outflow_spend"], dtype=np.float64
    ) + np.asarray(l2["bank_outflow_spend"], dtype=np.float64)
    assert bool(np.all(cumulative <= frozen + 1e-9))
    assert float(l1["state_bank_reserves_after"][bank_index]) > float(
        l2["bank_outflow_before"][bank_index]
    ) + 1e-9

    patched_fixture = _bank_binding_two_bank_fixture()
    trace: dict = {}
    audit: dict = {}
    with monkeypatch.context() as patcher:
        patcher.setattr(
            material_mod,
            "_frozen_bank_capacity",
            lambda actual, remaining: np.asarray(actual, dtype=np.float64),
        )
        tick_material(
            patched_fixture.state,
            patched_fixture.forcing(4),
            patched_fixture.parameters,
            patched_fixture.network,
            micro_stage_count=4,
            micro_stage_trace=trace,
            micro_stage_audit=audit,
        )
        adapter_fixture = _bank_binding_two_bank_fixture()
        with pytest.raises(LeadTimeFailure):
            execute_lead_time_tick(
                adapter_fixture.state,
                adapter_fixture.forcing(4),
                adapter_fixture.parameters,
                adapter_fixture.network,
                spec=LeadTimeSpec(stage_count=4),
            )

    patched_l = [s for s in trace["stages"] if s["kind"] == "L"]
    patched_l2_spend = float(patched_l[1]["bank_outflow_spend"][bank_index])
    assert patched_l2_spend > l2_spend + 1e-6
    patched_before = float(patched_l[1]["bank_outflow_before"][bank_index])
    patched_after = float(patched_l[1]["bank_outflow_after"][bank_index])
    assert abs((patched_before - patched_after) - patched_l2_spend) > 1e-6


def test_adapter_rejects_coherent_plus100_stock_corruption() -> None:
    """Reviewer round-5 repro: add 100 to the prelude and every stage stock.

    The trace alone is internally coherent after that edit, so the kernel's
    independent audit snapshot must reject it at ``prelude_stock``.  The
    adapter rolls back every dataclass field and leaves the clock untouched.
    """
    fixture = _food_chain_fixture()
    before = copy.deepcopy(fixture.state)

    import hsm_lab.institutions.lead_time_adapter as adapter_mod

    original_tick = adapter_mod.tick_material

    def _plus100_tick(*args, **kwargs):
        flows_obj = original_tick(*args, **kwargs)
        trace_d = kwargs.get("micro_stage_trace")
        if trace_d:
            trace_d["prelude_stock"] = (
                np.asarray(trace_d["prelude_stock"], dtype=np.float64) + 100.0
            ).tolist()
            for stage in trace_d.get("stages", []):
                for name in ("stock_before", "stock_after"):
                    stage[name] = (
                        np.asarray(stage[name], dtype=np.float64) + 100.0
                    ).tolist()
        return flows_obj

    adapter_mod.tick_material = _plus100_tick  # type: ignore[assignment]
    failure = None
    try:
        execute_lead_time_tick(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            spec=LeadTimeSpec(stage_count=4),
        )
    except LeadTimeFailure as exc:
        failure = exc
    finally:
        adapter_mod.tick_material = original_tick  # type: ignore[assignment]

    assert failure is not None
    assert failure.phase == "trace"
    assert "prelude_stock" in str(failure.cause)
    _assert_state_fully_restored(
        fixture.state, before, label="coherent +100 stock corruption"
    )


def test_kernel_audit_preflight_rejects_bad_containers() -> None:
    fixture = _food_chain_fixture()
    with pytest.raises(ValueError, match="micro_stage_audit"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_count=4,
            micro_stage_audit=[],  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="micro_stage_audit"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_count=4,
            micro_stage_audit={"stale": True},
        )
    with pytest.raises(ValueError, match="micro_stage_audit"):
        tick_material(
            fixture.state,
            fixture.forcing(4),
            fixture.parameters,
            fixture.network,
            micro_stage_audit={},
        )
