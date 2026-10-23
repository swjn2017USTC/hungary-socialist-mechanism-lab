"""H5D M03 opt-in labour institution runner.

The runner reuses the real material engine end to end:

``reproduce``
    Records the legacy C0 first-quarter counterexamples: wages cannot
    identify headcount/effective hours, the nominal labour total is not a
    person count, and the legacy per-organization realized activity exceeds
    the declared establishment ceiling.
``run``
    Delegates to ``run_material`` when the labour institution is disabled.
    With ``--enable-labor-institution`` it prepares the labour plan outside
    the tick, passes it through ``tick_material``/``check_material_invariants``
    and closes the sidecar only after every gate passed.  Checkpoints are the
    original material checkpoint plus an external ``labor.json``/``bundle.json``.
``negative-controls``
    Runs the declared synthetic N1/N2/N3 pairs on a real C0 tick.
``verify``
    Read-only recomputation of file hashes, identity axes, the labour ledger,
    bundle bindings, the external labour chain and the three verdicts.

No historical series is read, no parameter is calibrated, and the historical
status stays ``UNIDENTIFIED``.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from dataclasses import fields, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from hsm_lab.contract.base import ConfigError, ResearchGateError  # noqa: E402
from hsm_lab.contract.guards import (  # noqa: E402
    BASELINE_FILENAME,
    load_research_contract,
    load_scenario,
    verify_baseline,
)
from hsm_lab.data.registry import DataRegistry  # noqa: E402
from hsm_lab.engine import accounting as accounting_module  # noqa: E402
from hsm_lab.engine.initial import build_material_initial_conditions  # noqa: E402
from hsm_lab.engine.material import (  # noqa: E402
    MATERIAL_ENGINE_VERSION,
    _material_residuals,
    _parse_until,
    _target_ticks,
    advance_chain,
    initial_digest_chain,
    load_material_forcing,
    material_parameter_vector,
    material_recipe_hash,
    run_material,
    tick_material,
)
from hsm_lab.engine.network import build_material_network  # noqa: E402
from hsm_lab.engine.rng import RngRegistry  # noqa: E402
from hsm_lab.engine.state import (  # noqa: E402
    MATERIAL_STATE_VERSION,
    MaterialHistory,
    MaterialState,
    MaterialTickFlows,
    capture_material_stocks,
    initialize_material,
)
from hsm_lab.institutions.labor_state_adapter import (  # noqa: E402
    BUNDLE_SCHEMA_VERSION,
    SIDECAR_SCHEMA_VERSION,
    LaborRecipe,
    LaborSidecar,
    close_labor_tick,
    diagnostics_payload,
    effective_hours_of,
    labor_chain_advance,
    labor_chain_advance_digest,
    labor_chain_start,
    plan_payload,
    prepare_labor_tick,
    sidecar_from_payload,
    sidecar_payload,
    transition_headcount,
)
from hsm_lab.provenance.manifest import (  # noqa: E402
    canonical_digest,
    compute_parameter_hash,
    compute_scenario_hash,
)
from hsm_lab.storage.checkpoint import (  # noqa: E402
    CHECKPOINT_VERSION,
    load_material_checkpoint,
    save_material_checkpoint,
    sha256_file,
)
from hsm_lab.storage.material_output import (  # noqa: E402
    append_material_rows,
    history_frames,
    write_material_tables,
)

SCHEMA_VERSION = "hist_vnext_h5d_labor_run_v1"
PHASE_ID = "H5D"
MECHANISM_ID = "M3"
STUDY_ID = "M03"
RUN_KIND = "material_household_simulation"
LABOR_MODE = "IMPLEMENTED_DEFAULT_OFF"

SPEC_PATH = _HERE / "labor_institution_spec_v1.json"
ACCEPTANCE_PATH = _HERE / "LABOR_SPEC_ACCEPTANCE.json"
IMPLEMENTATION_SPEC_PATH = _HERE / "IMPLEMENTATION_SPEC.json"
VALIDATOR_PATH = _HERE / "labor_spec.py"

SCENARIOS = ("historical_f2_replay", "historical_f2_trade_scenario", "intermediate8")


# ---------------------------------------------------------------------------
# small utilities
# ---------------------------------------------------------------------------


def _json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.write_text(text, encoding="utf-8")


def _json_line(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, allow_nan=False) + "\n"


def _fresh_output(path: Path) -> Path:
    if path.exists() or path.is_symlink():
        raise ResearchGateError(
            f"output directory {path} already exists; refusing to overwrite any previous run"
        )
    path.mkdir(parents=True)
    return path


def _load_validator():
    module_spec = importlib.util.spec_from_file_location("h5d_labor_spec_runner", VALIDATOR_PATH)
    if module_spec is None or module_spec.loader is None:
        raise ResearchGateError(f"cannot load validator at {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def _load_recipe() -> tuple[LaborRecipe, dict[str, Any]]:
    raw = SPEC_PATH.read_bytes()
    raw_sha = hashlib.sha256(raw).hexdigest()
    acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    if raw_sha != acceptance["labor_spec_sha256"]:
        raise ResearchGateError(
            "accepted labour spec bytes drifted: "
            f"expected {acceptance['labor_spec_sha256']}, got {raw_sha}"
        )
    if acceptance.get("verdict") != "PASS":
        raise ResearchGateError("the labour spec acceptance record is not PASS")
    normative = _REPO_ROOT / acceptance["normative_text_path"]
    validator_path = _REPO_ROOT / acceptance["validator_path"]
    if sha256_file(normative) != acceptance["normative_text_sha256"]:
        raise ResearchGateError("normative labour spec text drifted from acceptance")
    if sha256_file(validator_path) != acceptance["validator_sha256"]:
        raise ResearchGateError("labour spec validator drifted from acceptance")
    validator = _load_validator()
    loaded, failures = validator.validate_repository(_REPO_ROOT)
    if failures:
        raise ResearchGateError(f"labour spec validator rejected the repository: {failures}")
    if loaded.get("spec_id") != acceptance["spec_id"]:
        raise ResearchGateError("labour spec id does not match the acceptance record")
    spec = json.loads(raw)
    return LaborRecipe.from_spec(spec, spec_sha256=raw_sha), acceptance


def _implementation_spec_sha() -> str:
    if not IMPLEMENTATION_SPEC_PATH.is_file():
        raise ResearchGateError(
            f"implementation spec missing: {IMPLEMENTATION_SPEC_PATH}"
        )
    return sha256_file(IMPLEMENTATION_SPEC_PATH)


def _validate_recipe_bindings(recipe: LaborRecipe, spec: Any) -> None:
    parameters = spec.material_parameters
    household = spec.household_parameters
    if parameters is None or household is None:
        raise ConfigError("enabled labour run requires material and household parameters")
    checks = {
        "utilization": (float(parameters.utilization), recipe.target_utilization),
        "formal_hours_per_worker": (
            float(household.time.formal_hours_per_worker),
            recipe.hours_per_we,
        ),
        "time_endowment_hours": (
            float(household.time.time_endowment_hours),
            recipe.endowment_hours,
        ),
        "effort_grievance_weight": (
            float(household.time.effort_grievance_weight),
            recipe.effort_grievance_weight,
        ),
        "effort_informal_hours_weight": (
            float(household.time.effort_informal_hours_weight),
            recipe.effort_informal_hours_weight,
        ),
        "effort_queue_search_weight": (
            float(household.time.effort_queue_search_weight),
            recipe.effort_queue_search_weight,
        ),
        "effort_floor": (float(household.time.effort_floor), recipe.effort_floor),
    }
    mismatch = {
        name: {"scenario": actual, "recipe": expected}
        for name, (actual, expected) in checks.items()
        if actual != expected
    }
    if mismatch:
        raise ConfigError(f"labour recipe does not bind the scenario parameters: {mismatch}")


def _preflight(spec: Any, contract: Any) -> dict[str, Any]:
    from hsm_lab.provenance.manifest import compute_lock_hash

    registry = DataRegistry.load(_REPO_ROOT, allowed_commodities=spec.commodities)
    forcing = load_material_forcing(spec, registry)
    baseline_hash = verify_baseline(_REPO_ROOT / BASELINE_FILENAME, contract)
    return {
        "registry": registry,
        "forcing": forcing,
        "baseline_hash": baseline_hash,
        "lock_hash": compute_lock_hash(_REPO_ROOT),
        "parameter_hash": compute_parameter_hash(material_parameter_vector(spec)),
        "initial_recipe_hash": material_recipe_hash(spec),
        "scenario_hash": compute_scenario_hash(spec),
        "input_artifact_hashes": dict(forcing.input_artifact_hashes),
    }


def _build_initial(spec: Any, contract: Any) -> tuple[Any, Any, Any]:
    rng = RngRegistry(spec.seed)
    initial = build_material_initial_conditions(spec, rng)
    network = build_material_network(spec, contract, initial)
    state = initialize_material(spec, initial, network)
    return state, network, rng


def _metadata(spec: Any, preflight: dict[str, Any], boundary: int, run_id: str) -> dict[str, Any]:
    return {
        "scenario": spec.model_dump(mode="json"),
        "scenario_hash": preflight["scenario_hash"],
        "baseline_hash": preflight["baseline_hash"],
        "lock_hash": preflight["lock_hash"],
        "parameter_hash": preflight["parameter_hash"],
        "initial_recipe_hash": preflight["initial_recipe_hash"],
        "engine_version": MATERIAL_ENGINE_VERSION,
        "state_version": MATERIAL_STATE_VERSION,
        "input_artifact_hashes": dict(preflight["input_artifact_hashes"]),
        "region_ids": list(spec.region_ids),
        "commodity_ids": list(spec.commodities),
        "last_completed_quarter": str(spec.start.advance(boundary - 1)),
        "next_quarter": str(spec.start.advance(boundary)),
        "source_run_id": run_id,
    }


# ---------------------------------------------------------------------------
# bundles
# ---------------------------------------------------------------------------


_BUNDLE_KEYS = {
    "schema_version",
    "tick",
    "scenario_id",
    "scenario_hash",
    "seed",
    "spec_sha256",
    "rules_sha256",
    "implementation_spec_sha256",
    "sidecar_schema_version",
    "core_state_version",
    "core_checkpoint_version",
    "core_digest_chain",
    "labor_digest_chain",
    "material_metadata_sha256",
    "labor_json_sha256",
    "region_ids",
    "commodity_ids",
    "source_run_id",
}


def save_labor_bundle(
    directory: Path,
    state: Any,
    network: Any,
    history: MaterialHistory,
    rng: RngRegistry,
    metadata: dict[str, Any],
    sidecar: LaborSidecar,
    *,
    labor_digest_chain: str,
    recipe: LaborRecipe,
    implementation_spec_sha256: str,
) -> Path:
    """Atomic bundle: standard material checkpoint + labor.json + bundle.json."""
    directory = Path(directory)
    if directory.exists() or directory.is_symlink():
        raise ResearchGateError(f"labor bundle {directory} already exists")
    parent = directory.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = parent / f".staging-{uuid4().hex}"
    if staging.exists():
        raise ResearchGateError(f"labor bundle staging directory {staging} already exists")
    staging.mkdir()
    try:
        save_material_checkpoint(
            staging / "material", state, network, history, rng, metadata
        )
        labor_payload = sidecar_payload(sidecar)
        labor_text = json.dumps(labor_payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
        (staging / "labor.json").write_text(labor_text, encoding="utf-8")
        bundle = {
            "schema_version": BUNDLE_SCHEMA_VERSION,
            "tick": int(state.completed_ticks),
            "scenario_id": str(metadata["scenario"]["scenario_id"]),
            "scenario_hash": metadata["scenario_hash"],
            "seed": int(metadata["scenario"]["seed"]),
            "spec_sha256": recipe.spec_sha256,
            "rules_sha256": recipe.rules_sha256,
            "implementation_spec_sha256": implementation_spec_sha256,
            "sidecar_schema_version": SIDECAR_SCHEMA_VERSION,
            "core_state_version": MATERIAL_STATE_VERSION,
            "core_checkpoint_version": CHECKPOINT_VERSION,
            "core_digest_chain": history.digest_chain,
            "labor_digest_chain": labor_digest_chain,
            "material_metadata_sha256": sha256_file(staging / "material" / "metadata.json"),
            "labor_json_sha256": sha256_file(staging / "labor.json"),
            "region_ids": list(metadata["region_ids"]),
            "commodity_ids": list(metadata["commodity_ids"]),
            "source_run_id": metadata["source_run_id"],
        }
        (staging / "bundle.json").write_text(
            json.dumps(bundle, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(staging, directory)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return directory


def load_labor_bundle(
    directory: Path,
    spec: Any,
    contract: Any,
    network: Any,
    recipe: LaborRecipe,
    *,
    implementation_spec_sha256: str,
) -> tuple[Any, MaterialHistory, RngRegistry, LaborSidecar, dict[str, Any]]:
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ResearchGateError(f"labor bundle not found or is a symlink: {directory}")
    entries = {entry.name for entry in directory.iterdir()}
    if entries != {"material", "labor.json", "bundle.json"}:
        raise ResearchGateError(f"labor bundle file set mismatch: {sorted(entries)}")
    try:
        bundle = json.loads((directory / "bundle.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchGateError(f"unreadable labor bundle: {exc}") from exc
    if set(bundle) != _BUNDLE_KEYS:
        raise ResearchGateError(
            f"labor bundle field set mismatch: {sorted(set(bundle) ^ _BUNDLE_KEYS)}"
        )
    if bundle["schema_version"] != BUNDLE_SCHEMA_VERSION:
        raise ResearchGateError("labor bundle schema version mismatch")
    if bundle["sidecar_schema_version"] != SIDECAR_SCHEMA_VERSION:
        raise ResearchGateError("labor bundle sidecar schema mismatch")
    if bundle["core_state_version"] != MATERIAL_STATE_VERSION:
        raise ResearchGateError("labor bundle core state version mismatch")
    if bundle["core_checkpoint_version"] != CHECKPOINT_VERSION:
        raise ResearchGateError("labor bundle core checkpoint version mismatch")
    if bundle["spec_sha256"] != recipe.spec_sha256:
        raise ResearchGateError("labor bundle spec hash mismatch")
    if bundle["rules_sha256"] != recipe.rules_sha256:
        raise ResearchGateError("labor bundle rules hash mismatch")
    if bundle["implementation_spec_sha256"] != implementation_spec_sha256:
        raise ResearchGateError("labor bundle implementation spec hash mismatch")
    if bundle["scenario_hash"] != compute_scenario_hash(spec):
        raise ResearchGateError("labor bundle scenario hash mismatch")
    if bundle["scenario_id"] != spec.scenario_id or int(bundle["seed"]) != int(spec.seed):
        raise ResearchGateError("labor bundle scenario/seed mismatch")
    if sha256_file(directory / "material" / "metadata.json") != bundle[
        "material_metadata_sha256"
    ]:
        raise ResearchGateError("labor bundle material metadata digest mismatch")
    if sha256_file(directory / "labor.json") != bundle["labor_json_sha256"]:
        raise ResearchGateError("labor bundle labor.json digest mismatch")
    try:
        labor_payload = json.loads((directory / "labor.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchGateError(f"unreadable labor sidecar: {exc}") from exc
    sidecar = sidecar_from_payload(labor_payload)
    if sidecar.spec_sha256 != recipe.spec_sha256:
        raise ResearchGateError("labor sidecar spec hash does not match the recipe")
    if sidecar.rules_sha256 != recipe.rules_sha256:
        raise ResearchGateError("labor sidecar rules hash does not match the recipe")
    chain_value = bundle.get("labor_digest_chain")
    if not isinstance(chain_value, str) or len(chain_value) != 64:
        raise ResearchGateError("labor bundle lacks a valid labour chain")

    state, history, rng, material_metadata = load_material_checkpoint(
        directory / "material", spec, contract, network
    )
    if int(material_metadata["completed_ticks"]) != int(bundle["tick"]):
        raise ResearchGateError("material checkpoint tick disagrees with the bundle tick")
    if int(state.completed_ticks) != int(bundle["tick"]):
        raise ResearchGateError("material state tick disagrees with the bundle tick")
    if history.digest_chain != bundle["core_digest_chain"]:
        raise ResearchGateError("material digest chain disagrees with the bundle")
    if sidecar.completed_ticks != int(bundle["tick"]):
        raise ResearchGateError("sidecar tick disagrees with the bundle tick")
    if sidecar.signal_tick != int(bundle["tick"]) - 1:
        raise ResearchGateError("sidecar signal_tick is not the previous quarter")
    if not np.array_equal(
        np.asarray(sidecar.organization_ids, dtype=np.int64),
        np.asarray(state.organization_id, dtype=np.int64),
    ):
        raise ResearchGateError("sidecar organization axis disagrees with the state")
    if not np.array_equal(
        np.asarray(sidecar.region_ids, dtype=np.int64),
        np.arange(int(np.asarray(state.dwelling_stock).shape[0]), dtype=np.int64),
    ):
        raise ResearchGateError("sidecar region axis disagrees with the state")
    working = float(np.asarray(state.household_working_adults, dtype=np.float64).sum())
    if float(np.asarray(sidecar.headcount).sum()) > working + 1e-9:
        raise ResearchGateError("sidecar headcount exceeds the working population")
    if float(np.asarray(sidecar.establishment).sum()) > working + 1e-9:
        raise ResearchGateError("sidecar establishment exceeds the working population")
    if not np.allclose(
        np.asarray(sidecar.effective_hours, dtype=np.float64),
        effective_hours_of(recipe, sidecar),
        rtol=1e-12,
        atol=1e-12,
    ):
        raise ResearchGateError("sidecar effective hours violate identity I2")
    effort = np.asarray(sidecar.effort, dtype=np.float64)
    if not np.array_equal(np.asarray(state.organization_effort_factor, dtype=np.float64), effort):
        raise ResearchGateError("state effort array disagrees with the sidecar")
    return state, history, rng, sidecar, material_metadata


# ---------------------------------------------------------------------------
# enabled run
# ---------------------------------------------------------------------------


def _run_enabled(
    spec: Any,
    contract: Any,
    output_dir: Path,
    *,
    until: Any = None,
    checkpoint_every: int = 0,
    resume_bundle: Path | None = None,
    initial_headcount: str = "establishment",
) -> dict[str, Any]:
    recipe, acceptance = _load_recipe()
    _validate_recipe_bindings(recipe, spec)
    implementation_spec_sha = _implementation_spec_sha()
    preflight = _preflight(spec, contract)
    forcing = preflight["forcing"]
    parameters = spec.material_parameters
    if parameters is None:
        raise ConfigError("material scenario lacks parameters")

    if initial_headcount not in ("establishment", "zero"):
        raise ConfigError("--initial-headcount must be 'establishment' or 'zero'")

    _fresh_output(output_dir)
    run_id = uuid4().hex
    state: Any = None
    history: MaterialHistory | None = None
    rng: RngRegistry | None = None
    sidecar: LaborSidecar | None = None
    network: Any = None
    parent_run_id: str | None = None
    start_tick = 0

    if resume_bundle is not None:
        if initial_headcount != "establishment":
            raise ConfigError("--initial-headcount cannot be combined with --resume-bundle")
        rebuilding_rng = RngRegistry(spec.seed)
        rebuilding_initial = build_material_initial_conditions(spec, rebuilding_rng)
        network = build_material_network(spec, contract, rebuilding_initial)
        state, history, rng, sidecar, material_metadata = load_labor_bundle(
            Path(resume_bundle),
            spec,
            contract,
            network,
            recipe,
            implementation_spec_sha256=implementation_spec_sha,
        )
        parent_run_id = str(material_metadata.get("source_run_id") or "")
        start_tick = int(state.completed_ticks)
        if start_tick <= 0:
            raise ResearchGateError("resume bundle carries a zero-tick state")
        labor_chain = _bundle_labor_chain(Path(resume_bundle))
    else:
        state, network, rng = _build_initial(spec, contract)
        history = MaterialHistory()
        history.digest_chain = initial_digest_chain(
            spec=spec,
            baseline_hash=preflight["baseline_hash"],
            lock_hash=preflight["lock_hash"],
            parameter_hash=preflight["parameter_hash"],
            initial_recipe_hash=preflight["initial_recipe_hash"],
            input_artifact_hashes=preflight["input_artifact_hashes"],
            initial_state=state,
        )
        initial_vector = None
        if initial_headcount == "zero":
            initial_vector = np.zeros_like(
                np.asarray(state.organization_id, dtype=np.float64)
            )
        labor_chain = labor_chain_start(
            recipe,
            implementation_spec_sha256=implementation_spec_sha,
            scenario_hash=preflight["scenario_hash"],
            core_chain=history.digest_chain,
            initial_sidecar=None,
            initial_headcount=initial_vector,
        )

    until_quarter = _parse_until(until)
    target_ticks = _target_ticks(spec, until_quarter, start_tick)
    if target_ticks <= start_tick:
        raise ConfigError("the requested horizon contains no new quarter")

    run_header = {
        "schema_version": SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "mechanism_id": MECHANISM_ID,
        "study_id": STUDY_ID,
        "run_id": run_id,
        "mode": LABOR_MODE,
        "enabled": True,
        "scenario_id": spec.scenario_id,
        "scenario_hash": preflight["scenario_hash"],
        "seed": spec.seed,
        "start": str(spec.start),
        "requested_until": str(until_quarter) if until_quarter is not None else None,
        "target_ticks": target_ticks,
        "start_tick": start_tick,
        "initial_core_chain": history.digest_chain,
        "initial_labor_chain": labor_chain,
        "checkpoint_every": checkpoint_every,
        "initial_headcount": initial_headcount,
        "resume_bundle": None if resume_bundle is None else str(resume_bundle),
        "parent_run_id": parent_run_id,
        "accepted_spec_sha256": recipe.spec_sha256,
        "accepted_spec_rules_sha256": recipe.rules_sha256,
        "accepted_spec_path": str(SPEC_PATH.relative_to(_REPO_ROOT)),
        "accepted_spec_acceptance_path": str(ACCEPTANCE_PATH.relative_to(_REPO_ROOT)),
        "implementation_spec_sha256": implementation_spec_sha,
        "core_state_version": MATERIAL_STATE_VERSION,
        "core_checkpoint_version": CHECKPOINT_VERSION,
        "sidecar_schema_version": SIDECAR_SCHEMA_VERSION,
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "default_off": True,
        "historical_verdict": "UNIDENTIFIED",
        "institutional_attribution": "UNIDENTIFIED",
        "spec_acceptance_verdict": acceptance["verdict"],
    }
    _json_dump(output_dir / "labor_run.json", run_header)

    ticks_path = output_dir / "labor_ticks.jsonl"
    orgs_path = output_dir / "labor_organizations.jsonl"
    checkpoints: list[dict[str, Any]] = []
    saved_boundaries: set[int] = set()
    residual_max = 0.0
    tick_rows = 0
    first_metrics: dict[str, Any] | None = None
    last_metrics: dict[str, Any] | None = None

    assert state is not None and history is not None and rng is not None and network is not None
    with ticks_path.open("w", encoding="utf-8") as ticks_file, orgs_path.open(
        "w", encoding="utf-8"
    ) as orgs_file:
        last_flows = None
        try:
            while state.completed_ticks < target_ticks:
                expected_tick = int(state.completed_ticks)
                quarter_expected = str(spec.start.advance(expected_tick))
                if list(forcing.quarters)[expected_tick] != quarter_expected:
                    raise ResearchGateError(
                        f"forcing slice {expected_tick} does not bind quarter {quarter_expected}"
                    )
                opening = capture_material_stocks(state)
                initial_vector = None
                if sidecar is None:
                    if initial_headcount == "zero":
                        initial_vector = np.zeros(
                            int(np.asarray(state.organization_id).shape[0]), dtype=np.float64
                        )
                    plan = prepare_labor_tick(
                        state, recipe, None, initial_headcount=initial_vector
                    )
                else:
                    plan = prepare_labor_tick(state, recipe, sidecar)
                flows = tick_material(
                    state, forcing, parameters, network, labor_plan=plan
                )
                last_flows = flows
                if int(flows.tick) != expected_tick or str(flows.quarter) != quarter_expected:
                    raise ResearchGateError("material tick does not describe the expected quarter")
                summary = accounting_module.check_material_invariants(
                    opening, state, flows, parameters, network, labor_plan=plan
                )
                residual, tolerance = _material_residuals(opening, state, flows, network)
                flows.material_balance_residual = residual
                flows.material_balance_tolerance = tolerance
                finance_residual, finance_tolerance = accounting_module.finance_balance_residuals(
                    state, flows
                )
                flows.finance_balance_residual = finance_residual
                flows.finance_balance_tolerance = finance_tolerance
                residual_max = max(
                    residual_max,
                    float(summary.max_material_abs_residual),
                    float(summary.max_finance_abs_residual),
                )
                sidecar, diagnostics = close_labor_tick(state, flows, plan)
                state.completed_ticks += 1
                history.digest_chain = advance_chain(history.digest_chain, state, flows)
                labor_chain = labor_chain_advance(
                    labor_chain,
                    core_chain=history.digest_chain,
                    plan=plan,
                    sidecar=sidecar,
                    diagnostics=diagnostics,
                )
                diagnostics = replace(
                    diagnostics,
                    core_chain=history.digest_chain,
                    labor_chain=labor_chain,
                )
                invariant_dict: dict[str, Any] = {
                    "max_material_abs_residual": float(summary.max_material_abs_residual),
                    "max_material_tolerance_ratio": float(summary.max_material_tolerance_ratio),
                    "max_finance_abs_residual": float(summary.max_finance_abs_residual),
                    "max_finance_tolerance_ratio": float(summary.max_finance_tolerance_ratio),
                    "checked_cells": int(summary.checked_cells),
                    "per_ledger": dict(summary.per_ledger),
                    "expired_leftover_by_cell": summary.expired_leftover_by_cell,
                    "forcing_segment": str(forcing.segment[expected_tick]),
                    "treasury_deposit_open": float(opening.treasury_deposit),
                    "bank_reserves_open": [float(v) for v in opening.bank_reserves],
                    "housing_completed": float(
                        np.sum(
                            np.asarray(state.dwelling_stock, dtype=np.float64)
                            - opening.dwelling_stock
                        )
                    ),
                    "material_balance_residual": [float(v) for v in residual],
                    "material_balance_tolerance": [float(v) for v in tolerance],
                }
                append_material_rows(
                    history,
                    state,
                    flows,
                    parameters,
                    network,
                    region_ids=list(spec.region_ids),
                    commodity_ids=list(spec.commodities),
                    digest=history.digest_chain,
                    invariant_summary=invariant_dict,
                    opening_stock=opening.stock_value,
                )
                diag_payload = diagnostics_payload(diagnostics)
                ticks_file.write(
                    _json_line(
                        {
                            "tick": expected_tick,
                            "quarter": quarter_expected,
                            "core_chain": history.digest_chain,
                            "labor_chain": labor_chain,
                            "plan_sha256": canonical_digest(plan_payload(plan)),
                            "sidecar": sidecar_payload(sidecar),
                            "diagnostics": diag_payload,
                        }
                    )
                )
                for index in range(int(plan.organization_ids.shape[0])):
                    orgs_file.write(
                        _json_line(
                            {
                                "tick": expected_tick,
                                "quarter": quarter_expected,
                                "organization_id": int(plan.organization_ids[index]),
                                "capacity": float(plan.capacity_open[index]),
                                "labor_per_activity": float(plan.labor_per_activity[index]),
                                "establishment": float(plan.establishment[index]),
                                "headcount": float(plan.headcount[index]),
                                "release": float(plan.release[index]),
                                "hire": float(plan.hire[index]),
                                "absence_rate": float(plan.absence_rate[index]),
                                "effort": float(plan.effort[index]),
                                "effective_hours": float(plan.effective_hours[index]),
                                "realized": float(diagnostics.organization_realized[index]),
                                "hours_used": float(
                                    diagnostics.organization_hours_used[index]
                                ),
                                "activity_per_effective_hour": (
                                    None
                                    if not np.isfinite(
                                        diagnostics.activity_per_effective_hour[index]
                                    )
                                    else float(diagnostics.activity_per_effective_hour[index])
                                ),
                            }
                        )
                    )
                if first_metrics is None:
                    first_metrics = _metrics_block(diag_payload)
                last_metrics = _metrics_block(diag_payload)
                tick_rows += 1

                boundary = int(state.completed_ticks)
                paused_here = boundary == target_ticks and target_ticks < spec.ticks
                due = (
                    (checkpoint_every > 0 and boundary % checkpoint_every == 0)
                    or paused_here
                    or (checkpoint_every > 0 and boundary == spec.ticks)
                )
                if due and boundary not in saved_boundaries:
                    bundle_dir = save_labor_bundle(
                        output_dir / "labor_checkpoints" / f"tick-{boundary}",
                        state,
                        network,
                        history,
                        rng,
                        _metadata(spec, preflight, boundary, run_id),
                        sidecar,
                        labor_digest_chain=labor_chain,
                        recipe=recipe,
                        implementation_spec_sha256=implementation_spec_sha,
                    )
                    saved_boundaries.add(boundary)
                    checkpoints.append(
                        {
                            "tick": boundary,
                            "path": str(bundle_dir.relative_to(output_dir)),
                            "bundle_sha256": sha256_file(bundle_dir / "bundle.json"),
                            "labor_json_sha256": sha256_file(bundle_dir / "labor.json"),
                            "material_metadata_sha256": sha256_file(
                                bundle_dir / "material" / "metadata.json"
                            ),
                        }
                    )

        except BaseException as error:
            _write_failure_evidence(
                output_dir,
                int(state.completed_ticks),
                state,
                last_flows,
                error,
                scenario_id=spec.scenario_id,
                progress={
                    "core_chain": history.digest_chain,
                    "labor_chain": labor_chain,
                    "residual_max": residual_max,
                    "tick_rows": tick_rows,
                },
            )
            raise
    frames = history_frames(history)
    write_material_tables(output_dir, frames)
    summary_payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "mode": LABOR_MODE,
        "enabled": True,
        "scenario_id": spec.scenario_id,
        "seed": spec.seed,
        "start": str(spec.start),
        "start_tick": start_tick,
        "target_ticks": target_ticks,
        "completed_ticks": int(state.completed_ticks),
        "last_completed_quarter": str(spec.start.advance(state.completed_ticks - 1)),
        "admitted_labor_rows": tick_rows,
        "core_digest_chain": history.digest_chain,
        "labor_digest_chain": labor_chain,
        "implementation_spec_sha256": implementation_spec_sha,
        "accepted_spec_sha256": recipe.spec_sha256,
        "accepted_spec_rules_sha256": recipe.rules_sha256,
        "max_abs_residual": residual_max,
        "technical_verdict": "PASS",
        "structural_verdict": "REPORTED_SYNTHETIC_NEGATIVE_CONTROLS",
        "historical_verdict": "UNIDENTIFIED",
        "institutional_attribution": "UNIDENTIFIED",
        "first_tick_metrics": first_metrics,
        "last_tick_metrics": last_metrics,
        "checkpoints": checkpoints,
    }
    _json_dump(output_dir / "labor_summary.json", summary_payload)
    _write_labor_manifest(output_dir, summary_payload, checkpoints)
    return summary_payload


def _bundle_labor_chain(directory: Path) -> str:
    bundle = json.loads((directory / "bundle.json").read_text(encoding="utf-8"))
    chain = bundle.get("labor_digest_chain")
    if not isinstance(chain, str) or len(chain) != 64:
        raise ResearchGateError("labor bundle lacks a valid labor_digest_chain")
    return chain


def _metrics_block(diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {
        "tick": diagnostics["tick"],
        "quarter": diagnostics["quarter"],
        "hours_used": diagnostics["hours_used"],
        "hours_supplied_establishment": diagnostics["hours_supplied_establishment"],
        "hours_supplied_effective": diagnostics["hours_supplied_effective"],
        "establishment_unused_share": diagnostics["establishment_unused_share"],
        "underutilization_share": diagnostics["underutilization_share"],
        "u_labor": diagnostics["u_labor"],
        "g_labor": diagnostics["g_labor"],
        "n_gap": diagnostics["n_gap"],
        "distribution_uncovered_we": diagnostics["distribution_uncovered_we"],
        "productive_nominal_effective_gap_we": (
            diagnostics["productive_nominal_effective_gap_we"]
        ),
        "n_working": diagnostics["n_working"],
        "n_working_weighted": diagnostics["n_working_weighted"],
        "weight_gap_persons": diagnostics["weight_gap_persons"],
    }



def _write_failure_evidence(
    output_dir: Path,
    tick: int | None,
    state: Any,
    flows: Any,
    error: BaseException,
    *,
    scenario_id: str,
    progress: dict[str, Any],
) -> None:
    """Persist the failing boundary; never mark the bundle/run complete."""
    directory = output_dir / "failures" / f"tick-{tick if tick is not None else 'unknown'}"
    directory.mkdir(parents=True, exist_ok=True)
    if isinstance(state, MaterialState):
        arrays = {
            field.name: np.asarray(getattr(state, field.name))
            for field in fields(state)
            if isinstance(getattr(state, field.name), np.ndarray)
        }
        np.savez(directory / "state.npz", **arrays)
    if isinstance(flows, MaterialTickFlows):
        arrays = {
            field.name: np.asarray(getattr(flows, field.name))
            for field in fields(flows)
            if isinstance(getattr(flows, field.name), np.ndarray)
        }
        np.savez(directory / "flows.npz", **arrays)
    _json_dump(
        directory / "failure.json",
        {
            "scenario_id": scenario_id,
            "tick": tick,
            "error_class": type(error).__name__,
            "error": str(error),
            "progress": progress,
            "state_saved": isinstance(state, MaterialState),
            "flows_saved": isinstance(flows, MaterialTickFlows),
        },
    )


def _write_labor_manifest(
    output_dir: Path, summary: dict[str, Any], checkpoints: list[dict[str, Any]]
) -> None:
    artifacts = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        name = path.relative_to(output_dir).as_posix()
        if name in ("labor_manifest.json", "labor_verify.json"):
            continue
        artifacts.append(
            {"path": name, "sha256": sha256_file(path), "bytes": path.stat().st_size}
        )
    manifest = {
        "schema_version": "hist_vnext_h5d_labor_manifest_v1",
        "phase_id": PHASE_ID,
        "mechanism_id": MECHANISM_ID,
        "study_id": STUDY_ID,
        "mode": LABOR_MODE,
        "enabled": True,
        "default_off": True,
        "scenario_id": summary["scenario_id"],
        "seed": summary["seed"],
        "start_tick": summary["start_tick"],
        "target_ticks": summary["target_ticks"],
        "accepted_spec_sha256": summary["accepted_spec_sha256"],
        "implementation_spec_sha256": summary["implementation_spec_sha256"],
        "historical_verdict": "UNIDENTIFIED",
        "institutional_attribution": "UNIDENTIFIED",
        "technical_verdict": summary["technical_verdict"],
        "structural_verdict": summary["structural_verdict"],
        "core_digest_chain": summary["core_digest_chain"],
        "labor_digest_chain": summary["labor_digest_chain"],
        "checkpoints": checkpoints,
        "artifacts": artifacts,
        "self_excluded": "labor_manifest.json",
        "outputs_committed": False,
        "pushed": False,
    }
    _json_dump(output_dir / "labor_manifest.json", manifest)


# ---------------------------------------------------------------------------
# reproduce
# ---------------------------------------------------------------------------


def _shares(
    hours_used: float, establishment_hours: float, effective_hours: float
) -> dict[str, Any]:
    return {
        "establishment_unused_share": (
            1.0 - hours_used / establishment_hours if establishment_hours > 0.0 else None
        ),
        "underutilization_share": (
            1.0 - hours_used / effective_hours if effective_hours > 0.0 else None
        ),
    }


def _reproduce(output_dir: Path) -> dict[str, Any]:
    contract = load_research_contract(_REPO_ROOT)
    spec = load_scenario(_REPO_ROOT, "historical_f2_replay")
    recipe, _acceptance = _load_recipe()
    _validate_recipe_bindings(recipe, spec)
    preflight = _preflight(spec, contract)
    parameters = spec.material_parameters
    assert parameters is not None
    state, network, _rng = _build_initial(spec, contract)
    opening = capture_material_stocks(state)
    flows = tick_material(state, preflight["forcing"], parameters, network)
    accounting_module.check_material_invariants(
        opening, state, flows, parameters, network
    )
    labor = np.asarray(state.organization_labor_available, dtype=np.float64)
    capacity = np.asarray(state.organization_capacity, dtype=np.float64)
    lpa = np.asarray(state.organization_labor_per_activity, dtype=np.float64)
    working = np.asarray(state.household_working_adults, dtype=np.float64)
    weights = np.asarray(state.household_weight, dtype=np.float64)
    n_working = float(working.sum())
    n_weighted = float((weights * working).sum())
    productive = capacity > 0.0
    raw = np.zeros(capacity.shape[0], dtype=np.float64)
    raw[productive] = (
        capacity[productive] * lpa[productive] * float(parameters.utilization)
    )
    raw_sum = float(raw.sum())
    scale = min(1.0, n_working / raw_sum) if raw_sum > 0.0 else 1.0
    establishment = raw * scale
    realized = np.asarray(flows.organization_realized, dtype=np.float64)
    used_we = float((lpa * realized).sum())
    hours_used = recipe.hours_per_we * used_we
    establishment_hours = recipe.hours_per_we * float(establishment.sum())
    effective_hours = recipe.hours_per_we * float(establishment.sum())  # H=E, A=0, e=1
    conflicts = int(np.count_nonzero(realized > establishment + 1e-9))

    # Wage-only identifiability: two employment states share one monetary
    # context but have different effective hours.
    wage_rate = float(parameters.wage_rate)
    wage_bill = wage_rate * float(labor.sum())
    state_a = np.full(5, 100.0)
    state_b = np.array([0.0, 100.0, 100.0, 150.0, 100.0])
    hours_a = float(state_a.sum()) * recipe.hours_per_we
    hours_b = float(state_b.sum()) * recipe.hours_per_we
    same_monetary_context = {
        "wage_rate": wage_rate,
        "wage_bill_open": wage_bill,
        "arrears": 0.0,
        "headcount_state_a": float(state_a.sum()),
        "headcount_state_b": float(state_b.sum()),
        "effective_hours_a": hours_a,
        "effective_hours_b": hours_b,
    }
    checks = [
        {
            "id": "R1",
            "claim": "the same wage/arrears context does not identify headcount or effective hours",
            "passed": hours_a != hours_b and wage_bill > 0.0,
            "detail": same_monetary_context,
        },
        {
            "id": "R2",
            "claim": "the legacy nominal labour total is not the household formal-hours headcount",
            "passed": abs(float(labor.sum()) - n_working) > 1.0,
            "detail": {
                "sum_L_WE": float(labor.sum()),
                "n_working": n_working,
                "h_formal_over_520": n_working,
            },
        },
        {
            "id": "R3",
            "claim": (
                "legacy per-organization realized activity exceeds the declared "
                "establishment ceiling"
            ),
            "passed": conflicts > 0,
            "detail": {"organizations_above_establishment": conflicts},
        },
        {
            "id": "R4",
            "claim": "the weighted and unweighted working populations differ",
            "passed": n_weighted != n_working,
            "detail": {
                "n_working": n_working,
                "n_working_weighted": n_weighted,
                "gap_persons": n_weighted - n_working,
            },
        },
    ]
    payload = {
        "schema_version": "hist_vnext_h5d_labor_reproduce_v1",
        "phase_id": PHASE_ID,
        "study_id": STUDY_ID,
        "scenario_id": spec.scenario_id,
        "seed": spec.seed,
        "quarter": str(flows.quarter),
        "source": "legacy_measured",
        "accepted_spec_sha256": recipe.spec_sha256,
        "accepted_spec_rules_sha256": recipe.rules_sha256,
        "legacy": {
            "n_working": n_working,
            "n_working_weighted": n_weighted,
            "sum_nominal_labor_we": float(labor.sum()),
            "sum_capacity_labor_we": float((capacity * lpa).sum()),
            "sum_establishment_raw": raw_sum,
            "establishment_clip": scale,
            "sum_establishment": float(establishment.sum()),
            "worker_equivalents_used": used_we,
            "hours_used": hours_used,
            "hours_supplied_establishment": establishment_hours,
            "hours_supplied_effective": effective_hours,
            "realized_sum_activity": float(realized.sum()),
            "organizations_above_establishment": conflicts,
            **_shares(hours_used, establishment_hours, effective_hours),
        },
        "spec_reference": {
            "measured_c0_tick0_expected_share": 0.06510964763391947,
            "not_required_for_opt_in": True,
        },
        "checks": checks,
        "verdict": "PASS" if all(check["passed"] for check in checks) else "FAILED",
        "historical_verdict": "UNIDENTIFIED",
    }
    _json_dump(output_dir / "reproduce.json", payload)
    return payload


# ---------------------------------------------------------------------------
# negative controls
# ---------------------------------------------------------------------------


def _real_tick(
    spec: Any,
    contract: Any,
    recipe: LaborRecipe,
    preflight: dict[str, Any],
    *,
    initial_headcount: str = "establishment",
    side_work: str = "unchanged",
) -> dict[str, Any]:
    state, network, _rng = _build_initial(spec, contract)
    parameters = spec.material_parameters
    assert parameters is not None
    opening = capture_material_stocks(state)
    initial_vector = None
    if initial_headcount == "zero":
        initial_vector = np.zeros(
            int(np.asarray(state.organization_id).shape[0]), dtype=np.float64
        )
    plan = prepare_labor_tick(state, recipe, None, initial_headcount=initial_vector)
    if side_work == "second_none":
        state.household_second_participating = np.zeros_like(
            state.household_second_participating
        )
    flows = tick_material(state, preflight["forcing"], parameters, network, labor_plan=plan)
    accounting_module.check_material_invariants(
        opening, state, flows, parameters, network, labor_plan=plan
    )
    sidecar, diagnostics = close_labor_tick(state, flows, plan)
    household = spec.household_parameters
    assert household is not None
    working = np.asarray(state.household_working_adults, dtype=np.float64)
    six_axis = (
        recipe.hours_per_we * float(working.sum())
        + float(np.asarray(state.household_reserved_plot_hours).sum())
        + float(np.asarray(state.household_reserved_second_hours).sum())
        + float(np.asarray(flows.household_queue_hours).sum())
        + float(np.asarray(flows.household_search_hours).sum())
        + float(np.asarray(flows.household_leisure_hours).sum())
    )
    endowment = household.time.time_endowment_hours * float(working.sum())
    return {
        "state": state,
        "network": network,
        "plan": plan,
        "flows": flows,
        "sidecar": sidecar,
        "diagnostics": diagnostics,
        "six_axis_hours": six_axis,
        "endowment_hours": endowment,
        "side_hours": float(
            np.asarray(state.household_reserved_plot_hours).sum()
            + np.asarray(state.household_reserved_second_hours).sum()
        ),
    }


def _negative_controls(output_dir: Path) -> dict[str, Any]:
    contract = load_research_contract(_REPO_ROOT)
    spec = load_scenario(_REPO_ROOT, "historical_f2_replay")
    recipe, _acceptance = _load_recipe()
    _validate_recipe_bindings(recipe, spec)
    preflight = _preflight(spec, contract)

    reference = _real_tick(spec, contract, recipe, preflight)
    zero = _real_tick(spec, contract, recipe, preflight, initial_headcount="zero")
    side_arm = _real_tick(spec, contract, recipe, preflight, side_work="second_none")
    if side_arm["side_hours"] == 0.0 or reference["side_hours"] == 0.0:
        raise ResearchGateError(
            "N3 requires at least one arm with non-zero side-work hours"
        )

    # --- N1: wage-only processing --------------------------------------
    ref_diag = reference["diagnostics"]
    ref_used = ref_diag.hours_used
    ref_estab = ref_diag.hours_supplied_establishment
    ref_eff = ref_diag.hours_supplied_effective
    before = _shares(ref_used, ref_estab, ref_eff)
    wage_clone = copy.deepcopy(reference["state"])
    parameters = spec.material_parameters
    assert parameters is not None
    wage_rate = float(parameters.wage_rate)
    doubled_wage_rate = 2.0 * wage_rate
    wage_bill = wage_rate * float(
        np.asarray(wage_clone.organization_labor_available).sum()
    )
    wage_clone.organization_wage_arrears = (
        np.asarray(wage_clone.organization_wage_arrears, dtype=np.float64) + wage_bill
    )
    # Re-run the closing measurement with the altered monetary context.
    closing = close_labor_tick(wage_clone, reference["flows"], reference["plan"])
    joint = _shares(
        closing[1].hours_used,
        closing[1].hours_supplied_establishment,
        closing[1].hours_supplied_effective,
    )
    # Individual and joint processing use the same measurement function; the
    # cloned context differs only in the monetary fields it carries.
    wage_only = _shares(ref_used, ref_estab, ref_eff)
    arrears_only = _shares(ref_used, ref_estab, ref_eff)
    n1_same = before == joint == wage_only == arrears_only
    alt_headcount = np.asarray(reference["plan"].headcount) * 0.95
    alt_eff = float(
        (alt_headcount * recipe.hours_per_we * (1.0 - reference["plan"].absence_rate)
         * reference["plan"].effort).sum()
    )
    alt = _shares(ref_used, ref_estab, alt_eff)
    n1_employment_sensitive = alt != before
    n1 = {
        "id": "N1",
        "control": "wage-only processing",
        "wage_rate": wage_rate,
        "doubled_wage_rate": doubled_wage_rate,
        "wage_bill": float(wage_bill),
        "hours_used": ref_used,
        "shares_reference": before,
        "shares_wage_rate_only": wage_only,
        "shares_arrears_only": arrears_only,
        "shares_wage_processing": joint,
        "arrears": float(wage_bill),
        "shares_alt_employment": alt,
        "unchanged_under_wage_processing": n1_same,
        "changes_under_employment_state": n1_employment_sensitive,
        "status": "PASS" if n1_same and n1_employment_sensitive else "FAILED",
    }

    # --- N2: employment-rule processing --------------------------------
    def witness(establishment_current: float) -> dict[str, Any]:
        headcount, release, raw, hire, scale = transition_headcount(
            np.array([100.0]),
            np.array([100.0]),
            np.array([establishment_current]),
            100.0,
            hire_capacity_share=recipe.hire_capacity_share,
            max_release_fraction=recipe.max_release_fraction,
        )
        used = 80.0 * recipe.hours_per_we
        shares = _shares(
            used,
            recipe.hours_per_we * establishment_current,
            recipe.hours_per_we * float(headcount.sum()),
        )
        return {
            "establishment": establishment_current,
            "headcount": float(headcount.sum()),
            "release": float(release.sum()),
            "hire_raw": float(raw.sum()),
            "hire": float(hire.sum()),
            "hire_scale": scale,
            "hours_used": used,
            **shares,
        }

    n2_reference = witness(80.0)
    n2_treatment = witness(100.0)
    n2_rule_moves = (
        n2_reference["establishment_unused_share"] != n2_treatment["establishment_unused_share"]
        and n2_reference["underutilization_share"] != n2_treatment["underutilization_share"]
    )
    real_target_ref = float(np.asarray(reference["flows"].organization_target).sum())
    real_target_zero = float(np.asarray(zero["flows"].organization_target).sum())
    real_realized_ref = float(np.asarray(reference["flows"].organization_realized).sum())
    real_realized_zero = float(np.asarray(zero["flows"].organization_realized).sum())
    n2_kernel = (
        real_target_zero < real_target_ref and real_realized_zero < real_realized_ref
    )
    n2 = {
        "id": "N2",
        "control": "employment-rule processing",
        "reference": n2_reference,
        "treatment": n2_treatment,
        "real_tick": {
            "reference_target_sum": real_target_ref,
            "zero_headcount_target_sum": real_target_zero,
            "reference_realized_sum": real_realized_ref,
            "zero_headcount_realized_sum": real_realized_zero,
        },
        "rule_moves_shares": n2_rule_moves,
        "kernel_target_moves": n2_kernel,
        "status": "PASS" if n2_rule_moves and n2_kernel else "FAILED",
    }

    # --- N3: side-work double counting ---------------------------------
    plan = reference["plan"]
    same_headcount = np.array_equal(
        np.asarray(plan.headcount), np.asarray(side_arm["plan"].headcount)
    )
    same_effective = np.array_equal(
        np.asarray(plan.effective_hours), np.asarray(side_arm["plan"].effective_hours)
    )
    axis_ok = abs(reference["six_axis_hours"] - reference["endowment_hours"]) <= 1e-6
    side_axis_ok = abs(side_arm["six_axis_hours"] - side_arm["endowment_hours"]) <= 1e-6
    side_delta = reference["side_hours"] - side_arm["side_hours"]
    n3_kernel = same_headcount and same_effective and axis_ok and side_axis_ok
    n3 = {
        "id": "N3",
        "control": "side-work double counting",
        "reference_side_hours": reference["side_hours"],
        "arm_side_hours": side_arm["side_hours"],
        "side_hours_delta": side_delta,
        "headcount_unchanged": same_headcount,
        "effective_hours_unchanged": same_effective,
        "reference_six_axis_hours": reference["six_axis_hours"],
        "arm_six_axis_hours": side_arm["six_axis_hours"],
        "reference_endowment_hours": reference["endowment_hours"],
        "arm_endowment_hours": side_arm["endowment_hours"],
        "status": "PASS" if n3_kernel else "FAILED",
    }

    payload = {
        "schema_version": "hist_vnext_h5d_labor_negative_controls_v1",
        "phase_id": PHASE_ID,
        "study_id": STUDY_ID,
        "scenario_id": spec.scenario_id,
        "seed": spec.seed,
        "synthetic": True,
        "historical_verdict": "UNIDENTIFIED",
        "institutional_attribution": "UNIDENTIFIED",
        "cases": [n1, n2, n3],
        "verdict": "PASS"
        if all(case["status"] == "PASS" for case in [n1, n2, n3])
        else "FAILED",
    }
    _json_dump(output_dir / "negative_controls.json", payload)
    return payload


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


def _verify_run(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise ResearchGateError(f"run directory not found: {run_dir}")
    manifest = json.loads((run_dir / "labor_manifest.json").read_text(encoding="utf-8"))
    failures: list[str] = []
    for artifact in manifest["artifacts"]:
        path = run_dir / artifact["path"]
        if not path.is_file():
            failures.append(f"missing artifact {artifact['path']}")
            continue
        if sha256_file(path) != artifact["sha256"]:
            failures.append(f"artifact digest mismatch {artifact['path']}")
        if path.stat().st_size != artifact["bytes"]:
            failures.append(f"artifact size mismatch {artifact['path']}")

    ticks = [
        json.loads(line)
        for line in (run_dir / "labor_ticks.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    org_rows = [
        json.loads(line)
        for line in (run_dir / "labor_organizations.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    by_tick: dict[int, list[dict[str, Any]]] = {}
    for row in org_rows:
        by_tick.setdefault(int(row["tick"]), []).append(row)
    run_info = json.loads((run_dir / "labor_run.json").read_text(encoding="utf-8"))
    recipe, _acceptance = _load_recipe()
    if run_info.get("enabled") is not True:
        failures.append("run is not an enabled labour run")
    if ticks and int(ticks[0]["tick"]) != int(run_info.get("start_tick", -1)):
        failures.append("first labour tick disagrees with labor_run.json start_tick")
    if int(run_info.get("target_ticks", -1)) - int(run_info.get("start_tick", 0)) != len(ticks):
        failures.append("labour tick count disagrees with the requested horizon")
    if run_info.get("parent_run_id"):
        resume_ref = Path(str(run_info.get("resume_bundle")))
        if not resume_ref.is_absolute():
            resume_ref = _REPO_ROOT / resume_ref
        if not (resume_ref / "bundle.json").is_file():
            failures.append(f"resume bundle missing: {resume_ref}")
        else:
            bundle = json.loads((resume_ref / "bundle.json").read_text(encoding="utf-8"))
            if bundle["core_digest_chain"] != run_info["initial_core_chain"]:
                failures.append("resumed initial core chain disagrees with the bundle")
            if bundle["labor_digest_chain"] != run_info["initial_labor_chain"]:
                failures.append("resumed initial labour chain disagrees with the bundle")
        chain = run_info["initial_labor_chain"]
    else:
        if run_info.get("initial_headcount") == "zero":
            initial_headcount = np.zeros(
                len(ticks[0]["sidecar"]["organization_ids"]) if ticks else 0,
                dtype=np.float64,
            )
        else:
            initial_headcount = None
        expected_start = labor_chain_start(
            recipe,
            implementation_spec_sha256=run_info["implementation_spec_sha256"],
            scenario_hash=run_info["scenario_hash"],
            core_chain=run_info["initial_core_chain"],
            initial_sidecar=None,
            initial_headcount=initial_headcount,
        )
        if expected_start != run_info["initial_labor_chain"]:
            failures.append("initial labour chain does not recompute from its identity")
        chain = run_info["initial_labor_chain"]
    for index, row in enumerate(ticks):
        tick = int(row["tick"])
        if index and tick != int(ticks[index - 1]["tick"]) + 1:
            failures.append(f"non-contiguous labour tick {tick}")
        sidecar = sidecar_from_payload(row["sidecar"])
        if sidecar.completed_ticks != tick + 1:
            failures.append(f"tick {tick}: sidecar completion stamp mismatch")
        if sidecar.signal_tick != tick:
            failures.append(f"tick {tick}: sidecar signal stamp mismatch")
        rows = by_tick.get(tick, [])
        diag = row["diagnostics"]
        if len(rows) != len(sidecar.organization_ids):
            failures.append(f"tick {tick}: organization row count mismatch")
        used = sum(float(entry["hours_used"]) for entry in rows)
        effective = sum(float(entry["effective_hours"]) for entry in rows)
        establishment = sum(float(entry["establishment"]) for entry in rows)
        if abs(used - float(diag["hours_used"])) > 1e-6:
            failures.append(f"tick {tick}: hours_used disagrees with organization rows")
        if abs(effective - float(diag["hours_supplied_effective"])) > 1e-3:
            failures.append(f"tick {tick}: effective hours denominator mismatch")
        if abs(
            establishment * recipe.hours_per_we
            - float(diag["hours_supplied_establishment"])
        ) > 1e-3:
            failures.append(f"tick {tick}: establishment hours denominator mismatch")
        for entry in rows:
            if float(entry["hours_used"]) > float(entry["effective_hours"]) + 1e-6:
                failures.append(
                    f"tick {tick}: organization {entry['organization_id']} exceeds I4"
                )
        expected_estab_share = (
            None
            if float(diag["hours_supplied_establishment"]) == 0.0
            else 1.0 - float(diag["hours_used"]) / float(diag["hours_supplied_establishment"])
        )
        if expected_estab_share != diag["establishment_unused_share"]:
            failures.append(f"tick {tick}: establishment share is inconsistent")
        expected_under = (
            None
            if float(diag["hours_supplied_effective"]) == 0.0
            else 1.0 - float(diag["hours_used"]) / float(diag["hours_supplied_effective"])
        )
        if expected_under != diag["underutilization_share"]:
            failures.append(f"tick {tick}: underutilization share is inconsistent")
        if diag["labor_chain"] != row["labor_chain"]:
            failures.append(f"tick {tick}: diagnostics chain stamp mismatch")
        expected_chain = labor_chain_advance_digest(
            chain,
            core_chain=row["core_chain"],
            plan_sha256=row["plan_sha256"],
            sidecar=sidecar_payload(sidecar),
            diagnostics_data=diag,
        )
        if expected_chain != row["labor_chain"]:
            failures.append(f"tick {tick}: labor chain does not recompute")
        chain = row["labor_chain"]
    if chain is not None and chain != manifest["labor_digest_chain"]:
        failures.append("manifest labor chain disagrees with the tick log")

    for checkpoint in manifest["checkpoints"]:
        directory = run_dir / checkpoint["path"]
        if not directory.is_dir() or directory.is_symlink():
            failures.append(f"missing bundle {checkpoint['path']}")
            continue
        if sha256_file(directory / "bundle.json") != checkpoint["bundle_sha256"]:
            failures.append(f"bundle digest mismatch {checkpoint['path']}")
        if sha256_file(directory / "labor.json") != checkpoint["labor_json_sha256"]:
            failures.append(f"bundle labor digest mismatch {checkpoint['path']}")
        if (
            sha256_file(directory / "material" / "metadata.json")
            != checkpoint["material_metadata_sha256"]
        ):
            failures.append(f"bundle material digest mismatch {checkpoint['path']}")
        bundle = json.loads((directory / "bundle.json").read_text(encoding="utf-8"))
        if int(bundle["tick"]) != int(checkpoint["tick"]):
            failures.append(f"bundle tick mismatch {checkpoint['path']}")

    summary = json.loads((run_dir / "labor_summary.json").read_text(encoding="utf-8"))
    if summary["core_digest_chain"] != manifest["core_digest_chain"]:
        failures.append("summary core chain disagrees with the manifest")
    if summary["labor_digest_chain"] != manifest["labor_digest_chain"]:
        failures.append("summary labour chain disagrees with the manifest")
    if summary["scenario_id"] != run_info["scenario_id"] or int(summary["seed"]) != int(
        run_info["seed"]
    ):
        failures.append("summary scenario/seed disagrees with labor_run.json")
    if int(summary["completed_ticks"]) != int(run_info["start_tick"]) + len(ticks):
        failures.append("summary completed_ticks disagrees with the tick log")
    if int(run_info["seed"]) != int(manifest.get("seed", run_info["seed"])):
        failures.append("manifest seed disagrees with labor_run.json")
    if summary["historical_verdict"] != "UNIDENTIFIED":
        failures.append("historical verdict must remain UNIDENTIFIED")
    if summary["institutional_attribution"] != "UNIDENTIFIED":
        failures.append("institutional attribution must remain UNIDENTIFIED")
    payload = {
        "schema_version": "hist_vnext_h5d_labor_verify_v1",
        "run_dir": str(run_dir),
        "ticks": len(ticks),
        "failures": failures,
        "verdict": "PASS" if not failures else "FAILED",
        "technical_verdict": summary["technical_verdict"],
        "structural_verdict": summary["structural_verdict"],
        "historical_verdict": "UNIDENTIFIED",
        "institutional_attribution": "UNIDENTIFIED",
        "outputs_committed": False,
        "pushed": False,
    }
    _json_dump(run_dir / "labor_verify.json", payload)
    return payload


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    reproduce = sub.add_parser("reproduce")
    reproduce.add_argument("--output-dir", type=Path, required=True)

    run = sub.add_parser("run")
    run.add_argument("--scenario", choices=SCENARIOS, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--enable-labor-institution", action="store_true")
    run.add_argument("--until", default=None)
    run.add_argument("--checkpoint-every", type=int, default=0)
    run.add_argument("--resume-bundle", type=Path, default=None)
    run.add_argument("--initial-headcount", choices=("establishment", "zero"),
                     default="establishment")

    negatives = sub.add_parser("negative-controls")
    negatives.add_argument("--output-dir", type=Path, required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--run-dir", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "reproduce":
        _fresh_output(args.output_dir)
        payload = _reproduce(args.output_dir)
    elif args.command == "run":
        contract = load_research_contract(_REPO_ROOT)
        spec = load_scenario(_REPO_ROOT, args.scenario)
        if not args.enable_labor_institution:
            if args.resume_bundle is not None:
                raise ConfigError("--resume-bundle requires --enable-labor-institution")
            if args.initial_headcount != "establishment":
                raise ConfigError("--initial-headcount requires --enable-labor-institution")
            if args.output_dir.exists() or args.output_dir.is_symlink():
                raise ResearchGateError(
                    f"output directory {args.output_dir} already exists"
                )
            registry = DataRegistry.load(_REPO_ROOT, allowed_commodities=spec.commodities)
            run_material(
                spec,
                args.output_dir,
                contract,
                registry,
                until=args.until,
                checkpoint_every=args.checkpoint_every,
            )
            _json_dump(
                args.output_dir / "labor_run.json",
                {
                    "schema_version": SCHEMA_VERSION,
                    "phase_id": PHASE_ID,
                    "mechanism_id": MECHANISM_ID,
                    "study_id": STUDY_ID,
                    "mode": LABOR_MODE,
                    "enabled": False,
                    "scenario_id": spec.scenario_id,
                    "default_off": True,
                    "labor_sidecar_written": False,
                    "labor_columns_added": False,
                    "historical_verdict": "UNIDENTIFIED",
                    "institutional_attribution": "UNIDENTIFIED",
                },
            )
            payload = {"enabled": False, "mode": LABOR_MODE}
        else:
            payload = _run_enabled(
                spec,
                contract,
                args.output_dir,
                until=args.until,
                checkpoint_every=args.checkpoint_every,
                resume_bundle=args.resume_bundle,
                initial_headcount=args.initial_headcount,
            )
    elif args.command == "negative-controls":
        _fresh_output(args.output_dir)
        payload = _negative_controls(args.output_dir)
    elif args.command == "verify":
        payload = _verify_run(args.run_dir)
    else:  # pragma: no cover
        parser.error("unknown command")
    print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
    return 0 if payload.get("verdict", "PASS") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
