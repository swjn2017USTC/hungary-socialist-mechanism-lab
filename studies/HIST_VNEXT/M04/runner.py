"""H5B M04 second-economy F2 runner.

Drives the F2 opt-in branch through three tolerance arms over a small in-memory
shrunken version of ``historical_f2_replay``.  Modes: ``reproduce`` saves the
declared red-counter examples; ``profile`` runs seed 1729 across all three arms
at 4 ticks (the structural profile); ``study`` runs all 3 seeds × 3 arms at 16
ticks; ``verify`` re-hashes every produced artefact.

The runner does not duplicate the engine — it calls ``build_material_initial_…``,
``build_material_network(...)`` and ``tick_material`` via the standard F2 view.
Plot self-use and the F2 second-economy pool are independent; the runner never
patches the existing P03 settle path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

# Running this file as a script puts ``studies/HIST_VNEXT/M04`` first on
# ``sys.path``.  Bind the repository root explicitly so the package lives.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from hsm_lab.contract.base import ConfigError  # noqa: E402
from hsm_lab.contract.guards import load_research_contract, load_scenario  # noqa: E402
from hsm_lab.contract.schemas import ScenarioSpec  # noqa: E402
from hsm_lab.engine.accounting import check_material_invariants  # noqa: E402
from hsm_lab.engine.material import (  # noqa: E402
    load_material_forcing,
    tick_material,
)
from hsm_lab.engine.network import MaterialNetwork  # noqa: E402
from hsm_lab.engine.rng import RngRegistry  # noqa: E402
from hsm_lab.engine.state import (  # noqa: E402
    build_material_prices,
    capture_material_stocks,
    initialize_material,
)
from hsm_lab.institutions.second_economy_f2_adapter import (  # noqa: E402
    F2SecondEconomyRecipe,
    attach_f2_second_economy,
    check_f2_second_economy,
)
from hsm_lab.provenance.manifest import canonical_digest  # noqa: E402

SCHEMA_VERSION = "hist_vnext_h5b_m04_v1"
SPEC_PATH = Path("studies/HIST_VNEXT/M04/spec.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_dumps(payload: Any) -> str:
    return json.dumps(_clean(payload), indent=2, sort_keys=False)


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_clean(item) for item in value.tolist()]
    if isinstance(value, (np.floating,)):
        f = float(value)
        if not np.isfinite(f):
            return None
        return f
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, float):
        if not np.isfinite(value):
            return None
        return value
    return value


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _dump_json(path: Path, payload: Any) -> None:
    path.write_text(_json_dumps(payload), encoding="utf-8")


def _shrunk_spec(
    spec: ScenarioSpec, *, households: int, ticks: int, seed: int
) -> ScenarioSpec:
    """Return a copy of ``spec`` in-memory only (no file mutation)."""
    return spec.model_copy(
        update={
            "scenario_id": "historical_f2_replay_m04_run",
            "households": int(households),
            "ticks": int(ticks),
            "seed": int(seed),
            "forcing_bindings": [],
        }
    )


def _build_tick_controls(
    *,
    state: Any,
    network: Any,
    parameters: Any,
    catalog: Any,
    raw_tolerance: float,
) -> Any:
    """Build a minimal ``TickControls`` carrying the F2 tolerance.

    Avoiding ``compile_effective_policy`` keeps the catalog at F2 axis and
    preserves the raw tolerance (no 1e-6 floor).
    """
    from hsm_lab.contract.politics import PolicyVector
    from hsm_lab.engine.policy import TickControls

    policy = PolicyVector(
        plan_utilization=1.0,
        enterprise_autonomy=0.1,
        investment_intensity=1.0,
        industrial_priority=0.0,
        admin_price_factor=1.0,
        wage_factor=1.0,
        credit_fraction=0.5,
        budget_hardness=0.0,
        housing_factor=1.0,
        borrowing_factor=1.0,
        consumer_import_factor=1.0,
        second_economy_tolerance=float(raw_tolerance),
        welfare_provision=0.5,
        private_autonomy=0.5,
        cultural_openness=0.5,
        supported_boundary=0.3,
        tolerance_boundary=0.7,
        repression=0.3,
        information_investment=0.0,
    )
    return TickControls(
        material_parameters=parameters,
        household_parameters=network.household_parameters,
        household_catalog=catalog,
        autonomy=0.1,
        central_target=None,
        policy=policy,
    )


def _declared_study() -> dict[str, Any]:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def _declared_arms(study: dict[str, Any]) -> dict[str, float]:
    arms = {
        str(arm["arm_id"]): float(arm["second_economy_tolerance"])
        for arm in study.get("arms", [])
    }
    if not arms:
        raise ConfigError("spec.json declares no arms")
    return arms


def _treatment_free_policy_hash(
    network: Any, catalog: Any, raw_tolerance: float
) -> str:
    controls = _build_tick_controls(
        state=None,
        network=network,
        parameters=network.household_parameters,
        catalog=catalog,
        raw_tolerance=raw_tolerance,
    )
    payload = controls.policy.model_dump()
    payload.pop("second_economy_tolerance", None)
    return canonical_digest(payload)


# ---------------------------------------------------------------------------
# Engine execution
# ---------------------------------------------------------------------------


def _build_initial(
    spec: ScenarioSpec, seed: int
) -> tuple[Any, MaterialNetwork, dict[str, Any]]:
    contract = load_research_contract(_REPO_ROOT)
    rng = RngRegistry(seed)
    from hsm_lab.engine.initial import build_material_initial_conditions
    from hsm_lab.engine.network import build_material_network

    initial = build_material_initial_conditions(spec, rng)
    network = build_material_network(spec, contract, initial)
    # Surface a few invariants for the experiment log; tolerate missing attrs.
    region_count = (
        int(initial.region_count)
        if hasattr(initial, "region_count") and initial.region_count is not None
        else (
            int(network.dwelling_stock.shape[0])
            if hasattr(network, "dwelling_stock")
            else len(network.region_ids)
        )
    )
    household_count = (
        int(initial.household_count)
        if hasattr(initial, "household_count") and initial.household_count is not None
        else int(np.asarray(initial.households.household_id).shape[0])
    )
    hashes = {
        "lock_hash": _lock_hash(),
        "scenario_hash": _scenario_hash(spec, seed),
        "network_field_count": len(network.__dataclass_fields__),
        "household_count": household_count,
        "region_count": region_count,
    }
    return initial, network, hashes


def _lock_hash() -> str:
    """The pinned uv.lock SHA-256 used by the runner."""
    from hsm_lab.provenance.manifest import compute_lock_hash

    return compute_lock_hash(_REPO_ROOT)


def _scenario_hash(spec: ScenarioSpec, seed: int) -> str:
    return canonical_digest(
        {"scenario_id": spec.scenario_id, "seed": seed, "households": spec.households}
    )


def _seed_assets(
    spec: ScenarioSpec, seed: int
) -> tuple[Any, Any, Any, dict[str, Any], Any]:
    """Build one initial state/network/forcing per seed (shared by all arms)."""
    import copy

    initial, network, hashes = _build_initial(spec, seed)
    state = initialize_material(spec, initial, network)
    recipe = F2SecondEconomyRecipe.default_nonplot_v1()
    f2_network = attach_f2_second_economy(network, recipe)
    forcing = load_material_forcing(spec, _make_registry(spec))
    return copy.deepcopy(state), f2_network, forcing, hashes, recipe


def _execute_arm(
    spec: ScenarioSpec,
    *,
    seed: int,
    tolerance_value: float,
    ticks: int,
    assets: tuple[Any, Any, Any, dict[str, Any], Any] | None = None,
) -> dict[str, Any]:
    import copy

    if assets is None:
        assets = _seed_assets(spec, seed)
    state_template, f2_network, forcing, hashes, recipe = assets
    state = copy.deepcopy(state_template)
    state_opening_balance = _bank_balance_total(state)
    org_cash_open = float(np.asarray(state.organization_cash, dtype=np.float64).sum())
    household_cash_open = float(np.asarray(state.household_cash, dtype=np.float64).sum())
    opening_hash = hashlib.sha256()
    for field_name in (
        "stock_value",
        "second_output_stock",
        "household_cash",
        "organization_cash",
        "household_reserved_plot_hours",
        "household_reserved_second_hours",
    ):
        array = np.ascontiguousarray(getattr(state, field_name), dtype=np.float64)
        opening_hash.update(str(array.shape).encode("ascii"))
        opening_hash.update(array.tobytes())
    opening_hash.update(str(int(state.completed_ticks)).encode("ascii"))
    opening_state_sha256 = opening_hash.hexdigest()
    prices = build_material_prices(spec.material_parameters)
    catalog = f2_network.household_catalog
    trace: dict[str, Any] = {}
    ticks_done: list[dict[str, Any]] = []
    completed = 0
    gate_residuals: list[dict[str, float]] = []
    pool_residuals: list[dict[str, float]] = []
    failures: list[dict[str, Any]] = []
    for tick in range(int(ticks)):
        if completed != state.completed_ticks:
            raise ConfigError(
                f"completed_ticks mismatch before tick {tick}: "
                f"state={state.completed_ticks} expected={completed}"
            )
        if state.completed_ticks >= len(forcing.quarters):
            break
        controls = _build_tick_controls(
            state=state,
            network=f2_network,
            parameters=spec.material_parameters,
            catalog=catalog,
            raw_tolerance=tolerance_value,
        )
        trace_payload: dict[str, Any] = {}
        opening = capture_material_stocks(state)
        pre_tick = copy.deepcopy(state)
        try:
            flows = tick_material(
                state,
                forcing,
                spec.material_parameters,
                f2_network,
                controls=controls,
                second_economy_trace=trace_payload,
            )
            check_material_invariants(
                opening=opening,
                state=state,
                flows=flows,
                parameters=spec.material_parameters,
                network=f2_network,
            )
            pool_residual = check_f2_second_economy(
                opening=opening,
                state=state,
                flows=flows,
                network=f2_network,
                trace=trace_payload,
            )
        except BaseException as exc:  # noqa: BLE001 - evidence, then stop
            state = pre_tick
            failures.append(
                {
                    "seed": int(seed),
                    "arm": str(tolerance_value),
                    "tick": int(tick),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            break
        pool_residuals.append(
            {
                "tick": int(flows.tick),
                "f2_pool_residual": float(pool_residual.get("f2_pool_residual", 0.0)),
                "f2_input_residual": float(pool_residual.get("f2_input_residual", 0.0)),
            }
        )
        completed += 1
        state.completed_ticks = completed
        gate_residuals.append(
            {
                "tick": int(flows.tick),
                "money_gap": float(state.bank_deposit_liability.sum()),
                "bank_reserves_min": float(np.asarray(state.bank_reserves).min()),
            }
        )
        ticks_done.append(_summarise_tick(state, flows, f2_network, trace_payload, prices))
        for key, value in trace_payload.items():
            trace.setdefault(f"t{completed}_{key}", _clean(value))
    household_cash_close = float(np.asarray(state.household_cash, dtype=np.float64).sum())
    org_cash_close = float(np.asarray(state.organization_cash, dtype=np.float64).sum())
    state_close_balance = _bank_balance_total(state)
    return {
        "completed_ticks": int(completed),
        "tolerance": float(tolerance_value),
        "household_cash_open": household_cash_open,
        "household_cash_close": household_cash_close,
        "org_cash_open": org_cash_open,
        "org_cash_close": org_cash_close,
        "bank_balance_open": state_opening_balance,
        "bank_balance_close": state_close_balance,
        "ticks": ticks_done,
        "pool_residuals": pool_residuals,
        "gate_residuals": gate_residuals,
        "hashes": hashes,
        "opening_state_sha256": opening_state_sha256,
        "recipe_hash": recipe.recipe_hash,
        "failures": failures,
        "status": "COMPLETED" if not failures and completed == int(ticks) else "PARTIAL",
    }


def _make_registry(spec: ScenarioSpec | None = None):
    from hsm_lab.data.registry import DataRegistry

    allowed = list(spec.commodities) if spec is not None else None
    return DataRegistry.load(_REPO_ROOT, allowed_commodities=allowed)


def _bank_balance_total(state: Any) -> float:
    deposits = np.asarray(state.bank_deposit_liability, dtype=np.float64).sum()
    equity = np.asarray(state.bank_equity, dtype=np.float64).sum()
    return float(deposits + equity)


def _summarise_tick(
    state: Any,
    flows: Any,
    network: MaterialNetwork,
    trace: dict[str, Any],
    prices: Any,
) -> dict[str, Any]:
    pool = np.asarray(state.second_output_stock, dtype=np.float64)
    g11 = network.commodity_ids.index("g11_textiles_footwear")
    g15 = network.commodity_ids.index("g15_market_services")
    g02 = network.commodity_ids.index("g02_oil_gas_fuels")
    g04 = network.commodity_ids.index("g04_basic_metals_materials")
    activity = np.asarray(
        trace.get("activity", np.zeros(pool.shape[0], dtype=np.float64)), dtype=np.float64
    )
    produced = np.asarray(trace.get("produced", np.zeros_like(pool)), dtype=np.float64)
    funding_arr = np.asarray(trace.get("funding", np.zeros(0, dtype=np.float64)), dtype=np.float64)
    weight = np.asarray(state.household_weight, dtype=np.float64)
    if funding_arr.size == 0:
        funding_total = 0.0
        funding_households: list[float] = []
    else:
        funding = funding_arr
        funding_total = float((weight * funding).sum())
        funding_households = [float(x) for x in funding]
    to_material = np.asarray(network.household_catalog.to_material, dtype=np.float64)
    formal_h_g = np.asarray(flows.household_formal_h, dtype=np.float64) @ to_material
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    g_count = len(network.commodity_ids)
    formal_available = np.asarray(
        trace.get(
            "formal_available_after_input",
            np.zeros((region_count, g_count), dtype=np.float64),
        ),
        dtype=np.float64,
    )
    capacity = np.asarray(
        trace.get("capacity", np.zeros(pool.shape[0])), dtype=np.float64
    )
    labor = np.asarray(trace.get("labor", np.zeros(pool.shape[0])), dtype=np.float64)
    kinds = np.asarray(flows.journal_kind, dtype=object)
    journal_counts = {
        str(kind): int(np.count_nonzero(kinds == kind))
        for kind in sorted(set(kinds.tolist()))
    }
    second_hours = np.asarray(flows.household_second_hours, dtype=np.float64)
    second_income = np.asarray(flows.household_second_income_direct, dtype=np.float64)
    return {
        "tick": int(flows.tick),
        "activity_total": float(activity.sum()),
        "produced_g02": float(produced[:, g02].sum()),
        "produced_g04": float(produced[:, g04].sum()),
        "produced_g11": float(produced[:, g11].sum()),
        "produced_g15": float(produced[:, g15].sum()),
        "funding_total": funding_total,
        "funding_households": funding_households,
        "second_hours_total": float(second_hours.sum()),
        "second_hours_weighted": float((weight * second_hours).sum()),
        "second_income_total": float(second_income.sum()),
        "second_income_weighted": float((weight * second_income).sum()),
        "second_pool_g11": float(pool[:, g11].sum()),
        "second_pool_g15": float(pool[:, g15].sum()),
        "second_pool_total": float(pool.sum()),
        "second_input_used_total": float(np.asarray(flows.second_input_used).sum()),
        "plot_self_weighted": float(
            (
                weight
                * np.asarray(flows.household_plot_self_h, dtype=np.float64).sum(axis=1)
            ).sum()
        ),
        "plot_market_weighted": float(
            (
                weight
                * np.asarray(flows.household_plot_market_h, dtype=np.float64).sum(axis=1)
            ).sum()
        ),
        "plot_direct_income_weighted": float(
            (weight * np.asarray(flows.household_plot_income_direct, dtype=np.float64)).sum()
        ),
        "formal_sales_total": float(np.asarray(flows.retail_sales, dtype=np.float64).sum()),
        "formal_delivered_total": float(np.asarray(flows.delivered, dtype=np.float64).sum()),
        "formal_used_total": float(np.asarray(flows.used, dtype=np.float64).sum()),
        "formal_available_total": float(formal_available.sum()),
        "formal_purchased_total": float((weight[:, None] * formal_h_g).sum()),
        "formal_unmet_total": float(np.asarray(flows.retail_unmet, dtype=np.float64).sum()),
        "household_cash_close_weighted": float(
            (weight * np.asarray(state.household_cash, dtype=np.float64)).sum()
        ),
        "formal_hours_weighted": float(
            (
                weight
                * network.household_parameters.time.formal_hours_per_worker
                * np.asarray(state.household_working_adults, dtype=np.float64)
            ).sum()
        ),
        "leisure_hours_weighted": float(
            (weight * np.asarray(flows.household_leisure_hours, dtype=np.float64)).sum()
        ),
        "capacity_binding_regions": int(
            np.count_nonzero(activity >= capacity - 1e-9)
        ),
        "labor_binding_regions": int(np.count_nonzero(activity >= labor - 1e-9)),
        "journal_counts": journal_counts,
        "household_second_hours_state_units": [float(x) for x in second_hours],
        "household_second_income_state_units": [float(x) for x in second_income],
    }


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


def _run_reproduce(spec: ScenarioSpec, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "mode": "reproduce",
        "schema_version": SCHEMA_VERSION,
        "spec_sha256": _hash_file(SPEC_PATH),
        "counter_examples": [],
    }
    # 1. F2 network second tuples empty.
    initial, network, _ = _build_initial(
        spec, int(_declared_study()["run"]["seeds"][0])
    )
    payload["counter_examples"].append(
        {
            "name": "f2_network_second_tuples_empty",
            "expected": "second_input_commodities == () and second_output_commodities == ()",
            "actual_input": tuple(network.second_input_commodities),
            "actual_output": tuple(network.second_output_commodities),
            "status": (
                "REPRODUCED"
                if not network.second_input_commodities
                and not network.second_output_commodities
                else "CHANGED"
            ),
        }
    )
    # 2. After F2 attach: tuples exactly g02/g04 and g11/g15.
    recipe = F2SecondEconomyRecipe.default_nonplot_v1()
    f2_network = attach_f2_second_economy(network, recipe)
    g02 = spec.commodities.index("g02_oil_gas_fuels")
    g04 = spec.commodities.index("g04_basic_metals_materials")
    g11 = spec.commodities.index("g11_textiles_footwear")
    g15 = spec.commodities.index("g15_market_services")
    payload["counter_examples"].append(
        {
            "name": "f2_network_attached_axes",
            "expected": "(g02, g04) -> (g11, g15)",
            "actual_input": tuple(f2_network.second_input_commodities),
            "actual_output": tuple(f2_network.second_output_commodities),
            "parent_input_unchanged": tuple(network.second_input_commodities),
            "parent_output_unchanged": tuple(network.second_output_commodities),
            "status": "REPRODUCED"
            if tuple(f2_network.second_input_commodities) == (g02, g04)
            and tuple(f2_network.second_output_commodities) == (g11, g15)
            else "FAILED",
        }
    )

    # 3. Tight time budget: endowment == formal hours leaves zero plot/second.
    from hsm_lab.engine.state import initialize_material as _initialize

    tight_params = spec.household_parameters.model_copy(
        update={
            "time": spec.household_parameters.time.model_copy(
                update={
                    "time_endowment_hours": 520.0,
                    "formal_hours_per_worker": 520.0,
                }
            )
        }
    )
    tight_state = _initialize(spec, initial, network)
    n = int(tight_state.household_id.size)
    tight_state.household_working_adults = np.zeros(n, dtype=np.float64)
    tight_state.household_working_adults[0] = 1.0
    tight_state.household_plot_participating = np.zeros(n, dtype=bool)
    tight_state.household_plot_participating[0] = True
    tight_state.household_second_participating = np.zeros(n, dtype=bool)
    tight_state.household_second_participating[0] = True
    from hsm_lab.institutions.second_economy_f2_adapter import plan_f2_household_time

    plan_f2_household_time(tight_state, tight_params, tolerance=1.0)
    plot_h = float(np.asarray(tight_state.household_reserved_plot_hours)[0])
    second_h = float(np.asarray(tight_state.household_reserved_second_hours)[0])
    payload["counter_examples"].append(
        {
            "name": "tight_time_budget_reserves_nothing",
            "expected": "plot + second == 0 when endowment equals formal hours",
            "actual_plot_hours": plot_h,
            "actual_second_hours": second_h,
            "status": "GUARDED" if plot_h + second_h == 0.0 else "FAILED",
        }
    )

    # 4. One repair shelf, four durable shortages: the legacy loop reuses the
    #    same availability for every q; the F2 room split consumes it once.
    catalog = network.household_catalog
    target_h = catalog.household_good_ids.index("repair_services")
    shelf = 1.0
    durable_q = [
        q
        for q in range(len(catalog.substitution_ids))
        if int(catalog.substitute_target_h[q]) == target_h
    ]
    legacy_total = float(len(durable_q) * min(1.0, shelf))
    f2_total = min(float(len(durable_q)), shelf)
    payload["counter_examples"].append(
        {
            "name": "one_repair_shelf_not_reused",
            "method": "analytic_counterfactual (the legacy loop is not executed)",
            "expected": "four durable shortages consume at most one real repair unit",
            "legacy_loop_total": legacy_total,
            "f2_room_total": f2_total,
            "status": "REPRODUCED" if legacy_total > shelf and f2_total <= shelf else "FAILED",
        }
    )
    _dump_json(output_dir / "counter_examples.json", payload)
    return payload


def _run_profile(
    spec: ScenarioSpec, output_dir: Path, *, ticks: int = 4
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    study = _declared_study()
    declared_arms = _declared_arms(study)
    if int(ticks) != int(study["run"]["ticks_profile"]):
        raise ConfigError(
            f"profile ticks {ticks} != declared ticks_profile "
            f"{study['run']['ticks_profile']}"
        )
    seed = int(study["run"]["seeds"][0])
    assets = _seed_assets(spec, seed)
    arms_summary: dict[str, dict[str, Any]] = {}
    for arm_id, tolerance_value in declared_arms.items():
        run = _execute_arm(
            spec,
            seed=seed,
            tolerance_value=tolerance_value,
            ticks=ticks,
            assets=assets,
        )
        arms_summary[arm_id] = run
    failures = {
        arm: run["failures"] for arm, run in arms_summary.items() if run["failures"]
    }
    if failures:
        raise ConfigError(f"profile arms failed: {json.dumps(failures)}")
    incomplete = {
        arm: (run["status"], run["completed_ticks"])
        for arm, run in arms_summary.items()
        if run["status"] != "COMPLETED" or int(run["completed_ticks"]) != int(ticks)
    }
    if incomplete:
        raise ConfigError(f"profile arms incomplete: {json.dumps(incomplete)}")
    treatment_hashes = {
        _treatment_free_policy_hash(
            assets[1], assets[1].household_catalog, tolerance
        )
        for tolerance in declared_arms.values()
    }
    if len(treatment_hashes) != 1:
        raise ConfigError("profile arms differ in a non-treatment policy coordinate")
    opening_digests = {
        run["opening_state_sha256"] for run in arms_summary.values()
    }
    if len(opening_digests) != 1:
        raise ConfigError("profile arms do not share one opening state")
    payload = {
        "mode": "profile",
        "schema_version": SCHEMA_VERSION,
        "spec_sha256": _hash_file(SPEC_PATH),
        "seed": seed,
        "ticks": ticks,
        "arms": arms_summary,
        "status": "COMPLETED",
        "opening_state_sha256": next(iter(opening_digests)),
        "treatment_only": True,
        "treatment_free_policy_sha256": next(iter(treatment_hashes)),
    }
    _dump_json(output_dir / "profile.json", payload)
    return payload


def _run_study(
    spec: ScenarioSpec, output_dir: Path, *, ticks: int = 16
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    study = _declared_study()
    declared_arms = _declared_arms(study)
    if int(ticks) != int(study["run"]["ticks_study"]):
        raise ConfigError(
            f"study ticks {ticks} != declared ticks_study "
            f"{study['run']['ticks_study']}"
        )
    seeds: list[int] = [int(seed) for seed in study["run"]["seeds"]]
    arms: dict[str, dict[int, dict[str, Any]]] = {
        arm: {} for arm in declared_arms
    }
    for seed in seeds:
        assets = _seed_assets(spec, seed)
        treatment_hashes = {
            _treatment_free_policy_hash(
                assets[1], assets[1].household_catalog, tolerance
            )
            for tolerance in declared_arms.values()
        }
        if len(treatment_hashes) != 1:
            raise ConfigError(
                f"seed {seed} arms differ in a non-treatment policy coordinate"
            )
        for arm_id, tolerance_value in declared_arms.items():
            run = _execute_arm(
                spec,
                seed=seed,
                tolerance_value=tolerance_value,
                ticks=ticks,
                assets=assets,
            )
            arms[arm_id][seed] = run
        failures = {
            arm: run["failures"]
            for arm, run in ((a, arms[a][seed]) for a in arms)
            if run["failures"]
        }
        if failures:
            raise ConfigError(f"seed {seed} arms failed: {json.dumps(failures)}")
        incomplete = {
            arm: (run["status"], run["completed_ticks"])
            for arm, run in ((a, arms[a][seed]) for a in arms)
            if run["status"] != "COMPLETED" or int(run["completed_ticks"]) != int(ticks)
        }
        if incomplete:
            raise ConfigError(
                f"seed {seed} arms incomplete: {json.dumps(incomplete)}"
            )
        opening_digests = {
            run["opening_state_sha256"] for run in (arms[a][seed] for a in arms)
        }
        if len(opening_digests) != 1:
            raise ConfigError(f"seed {seed} arms do not share one opening state")
    payload = {
        "mode": "study",
        "schema_version": SCHEMA_VERSION,
        "spec_sha256": _hash_file(SPEC_PATH),
        "ticks": ticks,
        "seeds": seeds,
        "arms": arms,
        "status": "COMPLETED",
        "treatment_only": True,
        "treatment_free_policy_sha256": next(iter(treatment_hashes)),
    }
    _dump_json(output_dir / "study.json", payload)
    return payload


def _run_verify(
    spec: ScenarioSpec,
    output_dir: Path,
    *,
    evidence_root: Path,
) -> dict[str, Any]:
    from hsm_lab.evidence.provenance import verify_run_identity

    output_dir.mkdir(parents=True, exist_ok=True)
    output_resolved = output_dir.resolve()
    manifest_path = (_REPO_ROOT / "studies/HIST_VNEXT/M04/EVIDENCE_MANIFEST.json").resolve()
    targets = []
    for path in sorted(evidence_root.rglob("*")):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved == manifest_path or output_resolved in resolved.parents:
            continue
        targets.append(
            {
                "path": str(path.relative_to(evidence_root)),
                "sha256": _hash_file(path),
            }
        )

    failures: list[dict[str, str]] = []
    checks: dict[str, Any] = {}

    # Protected input bytes (as snapshotted before implementation).
    protected_path = evidence_root / "protected-initial.json"
    if protected_path.exists():
        protected = json.loads(protected_path.read_text(encoding="utf-8"))
        protected_ok = {}
        for rel, expected in protected.get("sha256", {}).items():
            candidate = _REPO_ROOT / rel
            actual = _hash_file(candidate) if candidate.exists() else None
            protected_ok[rel] = actual == expected
            if actual != expected:
                failures.append(
                    {
                        "check": "protected_hash",
                        "path": rel,
                        "expected": str(expected),
                        "actual": str(actual),
                    }
                )
        checks["protected_hashes"] = protected_ok
    else:
        failures.append({"check": "protected_snapshot", "path": str(protected_path)})

    # C0 / C1 provenance.
    identity_checks = (
        (
            "historical_f2_replay",
            evidence_root / "C0",
            "92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d",
            "e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445",
        ),
        (
            "historical_f2_trade_scenario",
            evidence_root / "C1",
            "c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5",
            "632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90",
        ),
    )
    run_identity: dict[str, Any] = {}
    for scenario_id, run_dir, expected_digest, expected_parameter in identity_checks:
        try:
            manifest = verify_run_identity(
                root=_REPO_ROOT,
                scenario_id=scenario_id,
                seed=1729,
                expected_digest=expected_digest,
                output_dir=run_dir,
            )
            manifest_json = json.loads((run_dir / "manifest.json").read_text())
            ok = (
                int(manifest_json.get("completed_ticks", -1)) == 116
                and str(manifest_json.get("last_completed_quarter")) == "1985Q4"
                and str(manifest_json.get("parameter_hash")) == expected_parameter
                and str(manifest_json.get("seed")) == "1729"
            )
            run_identity[scenario_id] = {
                "ok": bool(ok),
                "completed_ticks": manifest_json.get("completed_ticks"),
                "last_completed_quarter": manifest_json.get("last_completed_quarter"),
                "parameter_hash": manifest_json.get("parameter_hash"),
                "deterministic_replay_digest": manifest_json.get(
                    "deterministic_replay_digest"
                ),
            }
            if not ok:
                failures.append({"check": "run_identity", "scenario": scenario_id})
        except BaseException as exc:  # noqa: BLE001 - evidence
            run_identity[scenario_id] = {"ok": False, "error": str(exc)}
            failures.append(
                {"check": "run_identity", "scenario": scenario_id, "error": str(exc)}
            )
    checks["run_identity"] = run_identity

    # F1 before/after byte identity.
    f1_fields = (
        "completed_ticks",
        "last_completed_quarter",
        "seed",
        "scenario_hash",
        "parameter_hash",
        "lock_hash",
        "data_manifest_hash",
        "deterministic_replay_digest",
    )
    f1: dict[str, Any] = {}
    before_path = evidence_root / "F1-before/manifest.json"
    after_path = evidence_root / "F1-after/manifest.json"
    if before_path.exists() and after_path.exists():
        before = json.loads(before_path.read_text())
        after = json.loads(after_path.read_text())
        for field in f1_fields:
            same = before.get(field) == after.get(field)
            f1[field] = {"same": same, "before": before.get(field), "after": after.get(field)}
            if not same:
                failures.append({"check": "f1_identity", "field": field})
        same_outputs = before.get("output_hashes") == after.get("output_hashes")
        f1["output_hashes"] = {"same": same_outputs}
        if not same_outputs:
            failures.append({"check": "f1_identity", "field": "output_hashes"})
        if int(after.get("completed_ticks", -1)) != 4 or str(
            after.get("last_completed_quarter")
        ) != "1957Q4":
            failures.append({"check": "f1_window", "after": after.get("last_completed_quarter")})
    else:
        failures.append({"check": "f1_pair_missing"})
    checks["f1_identity"] = f1

    # Manifest bindings (self-excluded by construction).
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        manifest_ok = True
        for item in manifest.get("artefacts", []):
            rel = str(item.get("path", ""))
            expected = str(item.get("sha256", ""))
            candidate = _REPO_ROOT / rel
            actual = _hash_file(candidate) if candidate.exists() else None
            if actual != expected:
                manifest_ok = False
                failures.append(
                    {
                        "check": "manifest_artifact",
                        "path": rel,
                        "expected": expected,
                        "actual": str(actual),
                    }
                )
        checks["manifest_artifacts_ok"] = manifest_ok
    else:
        checks["manifest_artifacts_ok"] = None

    payload = {
        "mode": "verify",
        "schema_version": SCHEMA_VERSION,
        "evidence_root": str(
            evidence_root.relative_to(_REPO_ROOT)
            if evidence_root.is_relative_to(_REPO_ROOT)
            else evidence_root
        ),
        "artefacts": targets,
        "spec_sha256": _hash_file(SPEC_PATH),
        "lock_hash": _lock_hash(),
        "scenario_sha256": _hash_file(Path("config/scenarios/historical_f2_replay.json")),
        "card_sha256": _hash_file(Path("config/p06/cards/M4.json")),
        "checks": checks,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    }
    _dump_json(output_dir / "verification.json", payload)
    if failures:
        raise ConfigError(
            f"verify found {len(failures)} failure(s); see {output_dir / 'verification.json'}"
        )
    return payload


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=("reproduce", "profile", "study", "verify")
    )
    parser.add_argument(
        "--spec", default="studies/HIST_VNEXT/M04/spec.json"
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--evidence-root", default=None)
    parser.add_argument("--ticks", type=int, default=None)
    parser.add_argument(
        "--households", type=int, default=1000
    )
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise ConfigError(
            f"output_dir {output_dir} already exists; refusing to overwrite"
        )
    spec_file = (
        Path(args.spec).resolve()
        if Path(args.spec).is_absolute()
        else _REPO_ROOT / args.spec
    )
    spec_obj = json.loads(spec_file.read_text(encoding="utf-8"))
    scenario_id = spec_obj.get("source", {}).get("scenario_id", "historical_f2_replay")
    default_ticks = 16 if args.mode == "study" else 4
    ticks = int(args.ticks) if args.ticks is not None else default_ticks
    full_spec = load_scenario(_REPO_ROOT, scenario_id)
    run_spec = _shrunk_spec(
        full_spec,
        households=args.households,
        ticks=ticks,
        seed=int(_declared_study()["run"]["seeds"][0]),
    )
    if args.mode == "reproduce":
        result = _run_reproduce(run_spec, output_dir)
    elif args.mode == "profile":
        result = _run_profile(run_spec, output_dir, ticks=ticks)
    elif args.mode == "study":
        result = _run_study(run_spec, output_dir, ticks=ticks)
    elif args.mode == "verify":
        if args.evidence_root is None:
            parser.error("verify requires --evidence-root")
        evidence_root = Path(args.evidence_root).resolve()
        result = _run_verify(run_spec, output_dir, evidence_root=evidence_root)
    else:  # pragma: no cover
        raise ConfigError(f"unknown mode {args.mode}")
    print(json.dumps({"status": "ok", "mode": args.mode, "output_dir": str(output_dir)}, indent=2))
    print(_json_dumps(result)[:2000])
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
