"""Toy-4 forcing loader, canonical digests and the end-to-end run runner.

The runner reuses the P00 lifecycle discipline (baseline-before-output,
fresh directory, running -> terminal manifest, protected fallible region)
but executes the real multi-commodity economic kernel, never ``run_smoke``.
"""

from __future__ import annotations

import hashlib
import json
import struct
import time
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import numpy as np
import polars as pl

from hsm_lab.contract.guards import BASELINE_FILENAME, verify_baseline
from hsm_lab.contract.schemas import (
    ConfigError,
    Quarter,
    ResearchContract,
    ResearchGateError,
    ScenarioSpec,
)
from hsm_lab.data.registry import DataRegistry
from hsm_lab.data.schemas import ForcingArtifact
from hsm_lab.engine.accounting import (
    capture_mutable_stocks,
    check_toy4_invariants,
    check_toy4_state_identities,
)
from hsm_lab.engine.rng import RNG_SCHEME_VERSION, RngRegistry
from hsm_lab.engine.state import (
    TOY4_STATE_VERSION,
    TickFlows,
    Toy4Forcing,
    Toy4History,
    Toy4State,
    initialize_toy4,
    tick_toy4,
)
from hsm_lab.provenance.manifest import (
    RunManifest,
    canonical_digest,
    canonical_json,
    compute_lock_hash,
    compute_parameter_hash,
    compute_scenario_hash,
    finalize_manifest,
    hash_output_tree,
    manifest_preamble,
    write_manifest_atomic,
)
from hsm_lab.storage.output import write_summary
from hsm_lab.storage.toy4_output import (
    append_compact_rows,
    history_frames,
    write_toy4_tables,
)

TOY4_ENGINE_VERSION = "toy4-engine-v1"
TOY4_FORCING_UNIT = "toy4_commodity_unit"

# Canonical per-run synthetic-parameter vector (parameters + initial recipe).
Vector = dict[str, float]


def toy4_parameter_vector(spec: ScenarioSpec) -> Vector:
    parameters = spec.toy4_parameters
    recipe = spec.toy4_initial
    if parameters is None or recipe is None:
        raise ConfigError("toy4 scenario lacks parameters/initial recipe")
    return {**parameters.flatten(), **recipe.flatten()}


def toy4_recipe_hash(spec: ScenarioSpec) -> str:
    if spec.toy4_initial is None:  # pragma: no cover - guarded earlier
        raise ConfigError("toy4 scenario lacks initial recipe")
    return canonical_digest(spec.toy4_initial.model_dump(mode="json"))


def _initial_household_cash(spec: ScenarioSpec) -> float:
    if spec.toy4_initial is None:  # pragma: no cover - guarded earlier
        raise ConfigError("toy4 scenario lacks initial recipe")
    return float(spec.toy4_initial.household_cash)


def toy4_parameter_hash(spec: ScenarioSpec) -> str:
    return compute_parameter_hash(toy4_parameter_vector(spec))


def _quarter_grid(start: str, end: str) -> list[str]:
    first = Quarter.parse(start)
    last = Quarter.parse(end)
    if last.to_ordinal() < first.to_ordinal():
        raise ResearchGateError(f"inverted forcing window {start}..{end}")
    return [str(first.advance(step)) for step in range(last.to_ordinal() - first.to_ordinal() + 1)]


def load_toy4_forcing(spec: ScenarioSpec, registry: DataRegistry) -> Toy4Forcing:
    """Admit both forcing fixtures and pivot them to (T, G) float64 arrays.

    Admission (role/rights/digest/unit/period) happens inside the registry;
    this loader additionally pins the declared coverage to the contract's core
    window and the artifact identity to its exact variable, enforces the
    complete quarter x commodity grid aligned to the scenario start, and
    checks non-negative finite values and national-only rows - all before any
    output directory exists. Shortened or shifted self-consistent fixtures
    with valid hashes are refused, not silently sliced.
    """
    if spec.forcing_ids != [
        "p01_toy4_import_supply",
        "p01_toy4_export_orders",
    ]:
        raise ConfigError(f"unexpected toy4 forcing_ids {spec.forcing_ids}")
    artifact_variables = {
        "p01_toy4_import_supply": "toy4_import_supply",
        "p01_toy4_export_orders": "toy4_export_orders",
    }
    core_start = str(registry.contract.core_start)
    core_end = str(registry.contract.core_end)
    if str(spec.start) != core_start:
        raise ConfigError(
            f"toy4 forcing is aligned to the core window start {core_start}, "
            f"not {spec.start}"
        )
    tables: dict[str, Any] = {}
    hashes: dict[str, str] = {}
    for artifact_id in spec.forcing_ids:
        artifact = registry.artifacts.get(artifact_id)
        if artifact is None:
            raise ResearchGateError(f"forcing artifact {artifact_id} is not registered")
        if not isinstance(artifact, ForcingArtifact):
            raise ResearchGateError(
                f"forcing artifact {artifact_id} has role {artifact.role.value}; "
                "only exogenous forcing may enter the Toy-4 runtime"
            )
        if artifact.variable_id != artifact_variables[artifact_id]:
            raise ResearchGateError(
                f"forcing artifact {artifact_id} must carry exactly variable "
                f"{artifact_variables[artifact_id]!r}, got {artifact.variable_id!r}"
            )
        if (artifact.period.start, artifact.period.end) != (core_start, core_end):
            raise ResearchGateError(
                f"forcing artifact {artifact_id}: declared coverage "
                f"{artifact.period.start}..{artifact.period.end} must equal the full "
                f"contract core window {core_start}..{core_end}"
            )
        frame = registry.load_forcing(artifact)
        tables[artifact_id] = frame
        digest = artifact.provenance.artifact_sha256
        assert digest is not None  # admission already enforced a real digest
        hashes[artifact_id] = digest
    quarters = _quarter_grid(core_start, core_end)
    commodities = list(spec.commodities)
    expected = {(period, commodity) for period in quarters for commodity in commodities}
    pivoted: dict[str, np.ndarray] = {}
    for artifact_id, frame in tables.items():
        units = frame["unit"].unique().to_list()
        if units != [TOY4_FORCING_UNIT]:
            raise ResearchGateError(
                f"forcing artifact {artifact_id}: unit must be {TOY4_FORCING_UNIT!r}, "
                f"got {units}"
            )
        if frame["region_id"].null_count() != frame.height:
            raise ResearchGateError(
                f"forcing artifact {artifact_id}: Toy-4 forcing is national-only "
                "(region_id must be null on every row)"
            )
        if frame["value"].null_count():
            raise ResearchGateError(
                f"forcing artifact {artifact_id}: missing values are never filled"
            )
        values = frame["value"].to_numpy()
        if not np.all(np.isfinite(values)) or float(np.min(values)) < 0:
            raise ResearchGateError(
                f"forcing artifact {artifact_id}: values must be finite and >= 0"
            )
        keys = set(zip(frame["period"].to_list(), frame["commodity_id"].to_list(), strict=True))
        if keys != expected:
            missing = sorted(expected - keys)[:4]
            extra = sorted(keys - expected)[:4]
            raise ResearchGateError(
                f"forcing artifact {artifact_id}: grid mismatch - missing {missing}, "
                f"unexpected {extra} (a real zero row never substitutes a missing cell)"
            )
        matrix = np.zeros((len(quarters), len(commodities)), dtype=np.float64)
        period_index = {period: index for index, period in enumerate(quarters)}
        commodity_index = {name: index for index, name in enumerate(commodities)}
        for period, commodity, value in zip(
            frame["period"].to_list(),
            frame["commodity_id"].to_list(),
            frame["value"].to_list(),
            strict=True,
        ):
            matrix[period_index[period], commodity_index[commodity]] = float(value)
        pivoted[artifact_id] = np.ascontiguousarray(matrix)
    horizon = quarters[: spec.ticks]
    return Toy4Forcing(
        quarters=horizon,
        imports=pivoted["p01_toy4_import_supply"][: spec.ticks].copy(),
        export_orders=pivoted["p01_toy4_export_orders"][: spec.ticks].copy(),
        input_artifact_hashes=hashes,
    )


# ----------------------------------------------------------------------
# Canonical digests
# ----------------------------------------------------------------------

_STATE_DTYPE_ORDER = sorted(_STATE_DTYPE_NAMES := {
    "household_id": "<i8",
    "household_region": "<i4",
    "household_weight": "<f8",
    "household_size": "<f8",
    "household_cash": "<f8",
    "organization_id": "<i8",
    "organization_region": "<i4",
    "organization_output_sector": "<i4",
    "organization_capacity": "<f8",
    "organization_labor_capacity": "<f8",
    "organization_input_coefficients": "<f8",
    "organization_output_mix": "<f8",
    "organization_input_inventory": "<f8",
    "wholesale_inventory": "<f8",
    "retail_inventory": "<f8",
    "region_equivalent_persons": "<f8",
    "regional_share": "<f8",
})


def _block(field: str, array: np.ndarray) -> bytes:
    dtype = np.dtype(array.dtype.newbyteorder("<"))
    contiguous = np.ascontiguousarray(array, dtype=dtype)
    header = canonical_json(
        {
            "field": field,
            "shape": list(contiguous.shape),
            "dtype": contiguous.dtype.str,
            "byte_length": int(contiguous.nbytes),
        }
    )
    return struct.pack("<Q", len(header)) + header + contiguous.tobytes()


def canonical_toy4_bytes(state: Toy4State, flows: TickFlows | None = None) -> bytes:
    """Deterministic bytes over the canonical state (+ optional flow) arrays.

    JSON headers carry field/shape/little-endian dtype/byte_length and are
    separated from their payload by an 8-byte little-endian length prefix.
    Timers, UUIDs, paths and writer objects never enter the digest.
    """
    header = canonical_json(
        {
            "state_version": state.schema_version,
            "completed_ticks": state.completed_ticks,
            "flows": None
            if flows is None
            else {"tick": flows.tick, "quarter": flows.quarter},
        }
    )
    chunks = [struct.pack("<Q", len(header)) + header]
    for name in _STATE_DTYPE_ORDER:
        chunks.append(_block(name, getattr(state, name)))
    if flows is not None:
        from dataclasses import fields

        flow_arrays = sorted(
            (
                f.name,
                getattr(flows, f.name),
            )
            for f in fields(TickFlows)
            if isinstance(getattr(flows, f.name), np.ndarray)
        )
        for name, array in flow_arrays:
            chunks.append(_block(name, array))
    return b"".join(chunks)


def initial_digest_chain(
    *,
    spec: ScenarioSpec,
    baseline_hash: str,
    lock_hash: str,
    parameter_hash: str,
    initial_recipe_hash: str,
    input_artifact_hashes: dict[str, str],
    initial_state: Toy4State,
) -> str:
    initial_state_hash = hashlib.sha256(canonical_toy4_bytes(initial_state)).hexdigest()
    return canonical_digest(
        {
            "engine_version": TOY4_ENGINE_VERSION,
            "state_version": TOY4_STATE_VERSION,
            "baseline_hash": baseline_hash,
            "lock_hash": lock_hash,
            "seed": spec.seed,
            "stochastic": spec.stochastic,
            "households": spec.households,
            "enterprises": spec.enterprises,
            "region_ids": list(spec.region_ids),
            "commodity_ids": list(spec.commodities),
            "initial_recipe_hash": initial_recipe_hash,
            "parameter_hash": parameter_hash,
            "input_artifact_hashes": dict(input_artifact_hashes),
            "initial_state_hash": initial_state_hash,
        }
    )


def advance_chain(previous: str, state: Toy4State, flows: TickFlows) -> str:
    digest = hashlib.sha256()
    digest.update(bytes.fromhex(previous))
    digest.update(canonical_toy4_bytes(state, flows))
    return digest.hexdigest()


# ----------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------


def _parse_until(until: Quarter | str | None) -> Quarter | None:
    if until is None:
        return None
    if isinstance(until, str):
        return Quarter.parse(until)
    return until


def _target_ticks(spec: ScenarioSpec, until: Quarter | None, start_tick: int) -> int:
    if until is None:
        return spec.ticks
    end = spec.start.advance(spec.ticks - 1)
    first = spec.start.advance(start_tick)
    if until.to_ordinal() < first.to_ordinal():
        raise ConfigError(
            f"--until {until} precedes the first executed quarter {first}"
        )
    if until.to_ordinal() > end.to_ordinal():
        raise ConfigError(f"--until {until} lies beyond the scenario end {end}")
    return until.to_ordinal() - spec.start.to_ordinal() + 1


def _by_commodity_summary(
    frames: dict[str, Any], commodity_ids: list[str]
) -> dict[str, dict[str, float]]:
    national = frames["national_accounts"]
    aggregates = frames["aggregates"]
    out: dict[str, dict[str, float]] = {}
    for commodity in commodity_ids:
        rows = national.filter(pl.col("commodity_id") == commodity)
        agg = aggregates.filter(pl.col("commodity_id") == commodity)
        final = rows.row(-1, named=True) if rows.height else {}
        affordable_total = float(agg["household_affordable"].sum())
        desired_total = float(agg["household_desired"].sum())
        availability_unmet = float(agg["availability_unmet"].sum())
        total_unmet = float(agg["total_unmet"].sum())
        out[commodity] = {
            "production": float(rows["production"].sum()),
            "imports": float(rows["imports"].sum()),
            "used_input": float(rows["used_input"].sum()),
            "exports": float(rows["export_realized"].sum()),
            "consumption": float(rows["household_consumption"].sum()),
            "budget_unmet": float(agg["budget_unmet"].sum()),
            "availability_unmet": availability_unmet,
            "total_unmet": total_unmet,
            "final_wholesale_inventory": float(final.get("wholesale_close", 0.0)),
            "final_organization_input_inventory": float(
                final.get("organization_input_close", 0.0)
            ),
            "final_retail_inventory": float(final.get("retail_close", 0.0)),
            "cumulative_availability_shortage_rate": (
                availability_unmet / affordable_total if affordable_total > 0 else 0.0
            ),
            "cumulative_total_unmet_rate": (
                total_unmet / desired_total if desired_total > 0 else 0.0
            ),
        }
    return out


def _build_summary(
    *,
    run_id: str,
    spec: ScenarioSpec,
    state: Toy4State,
    history: Toy4History,
    frames: dict[str, Any],
    rng: RngRegistry,
    parameter_hash: str,
    initial_recipe_hash: str,
    input_artifact_hashes: dict[str, str],
    performance: dict[str, float],
    checkpoint_paths: list[str],
    research_warnings: list[str],
) -> dict[str, Any]:
    budgets = frames["household_budgets"]
    diagnostics = frames["tick_diagnostics"]
    commodity_ids = list(spec.commodities)
    draws_by_module = rng.draws_by_module()
    draws_count = sum(draws_by_module.values())
    boundary = state.completed_ticks
    summary: dict[str, Any] = {
        "schema_version": "1",
        "run_id": run_id,
        "run_kind": "toy4_f0_simulation",
        "engine_version": TOY4_ENGINE_VERSION,
        "political_mode": None,
        "scenario_id": spec.scenario_id,
        "start": str(spec.start),
        "end": str(spec.start.advance(spec.ticks - 1)),
        "last_completed_quarter": (
            str(spec.start.advance(boundary - 1)) if boundary else None
        ),
        "planned_ticks": spec.ticks,
        "completed_ticks": boundary,
        "horizon_reached": boundary == spec.ticks,
        "households": spec.households,
        "organizations": spec.enterprises,
        "region_ids": list(spec.region_ids),
        "commodity_ids": commodity_ids,
        "seed": spec.seed,
        "output_policy": spec.output_policy.value,
        "parameter_hash": parameter_hash,
        "initial_recipe_hash": initial_recipe_hash,
        "input_artifact_hashes": dict(input_artifact_hashes),
        "deterministic_replay_digest": history.digest_chain,
        "rng_scheme_version": RNG_SCHEME_VERSION,
        "rng_draws_count": draws_count,
        "rng_draws_by_module": draws_by_module,
        "stochastic_modules_active": [
            module for module, count in draws_by_module.items() if count > 0
        ],
        "row_counts": {name: frame.height for name, frame in frames.items()},
        "by_commodity": _by_commodity_summary(frames, commodity_ids),
        "household_budget": {
            "income": float(budgets["income"].sum()),
            "spending": float(budgets["spending"].sum()),
            "voluntary_saving": float(budgets["voluntary_saving"].sum()),
            "forced_saving": float(budgets["forced_saving"].sum()),
            "final_cash": (
                float(
                    budgets.filter(pl.col("tick") == boundary - 1)["cash_close"].sum()
                )
                if boundary
                else 0.0
            ),
        },
        "invariants": {
            "max_material_abs_residual": float(
                diagnostics["max_material_abs_residual"].max()
            )
            if diagnostics.height
            else 0.0,
            "max_material_tolerance_ratio": float(
                diagnostics["max_material_tolerance_ratio"].max()
            )
            if diagnostics.height
            else 0.0,
            "max_cash_abs_residual": float(diagnostics["max_cash_abs_residual"].max())
            if diagnostics.height
            else 0.0,
            "max_cash_tolerance_ratio": float(
                diagnostics["max_cash_tolerance_ratio"].max()
            )
            if diagnostics.height
            else 0.0,
            "checked_ticks": diagnostics.height,
        },
        "performance": performance,
        "checkpoint_paths": list(checkpoint_paths),
        "research_warnings": research_warnings + [
            "toy4_synthetic_fixture_not_historical_fit"
        ],
        "mechanism_diagnostics": {},
        "mechanism_note": (
            "Toy-4 economic quantities are synthetic engineering fixture values, "
            "not historical Hungarian magnitudes."
        ),
    }
    if not spec.stochastic:
        summary["deterministic_mode"] = {
            "warning": "deterministic_no_replicates",
            "note": "zero RNG draws: this run is not a stochastic replicate",
        }
    return summary


def run_toy4(
    spec: ScenarioSpec,
    output_dir: Path,
    contract: ResearchContract,
    registry: DataRegistry,
    *,
    until: Quarter | str | None = None,
    checkpoint_every: int = 0,
    resume_from: Path | None = None,
) -> RunManifest:
    """Run the Toy-4 economic simulation into a fresh ``output_dir``."""
    from hsm_lab.storage.checkpoint import (
        checkpoint_dir,
        load_toy4_checkpoint,
        save_toy4_checkpoint,
    )

    root = registry.root
    baseline_hash = verify_baseline(root / BASELINE_FILENAME, contract)
    spec.validate_for_run(contract)
    if checkpoint_every < 0:
        raise ConfigError("checkpoint_every must be non-negative")

    # ---------------- preflight (before any output exists) ----------------
    forcing = load_toy4_forcing(spec, registry)
    lock_hash = compute_lock_hash(root)
    parameter_hash = toy4_parameter_hash(spec)
    initial_recipe_hash = toy4_recipe_hash(spec)

    parent_run_id: str | None = None
    if resume_from is not None:
        _resume_state, _resume_history, _resume_rng, metadata = load_toy4_checkpoint(
            resume_from, spec, contract, registry
        )
        restored = ScenarioSpec.model_validate(metadata["scenario"])
        restored.validate_for_run(contract)
        if compute_scenario_hash(restored) != metadata.get("scenario_hash"):
            raise ResearchGateError("restored scenario hash mismatch")
        if _resume_state.household_id.shape[0] != restored.households:
            raise ResearchGateError("checkpoint household count disagrees")
        spec = restored
        forcing = load_toy4_forcing(spec, registry)
        parent_run_id = str(metadata.get("source_run_id") or "")
        next_quarter = spec.start.advance(_resume_state.completed_ticks)
        if next_quarter.to_ordinal() > spec.start.advance(spec.ticks - 1).to_ordinal():
            raise ConfigError(
                f"checkpoint boundary {next_quarter} already ends the scenario; "
                "a zero-tick replay is refused"
            )
    until_quarter = _parse_until(until)
    start_tick = _resume_state.completed_ticks if resume_from is not None else 0
    target_ticks = _target_ticks(spec, until_quarter, start_tick)

    if output_dir.exists() or output_dir.is_symlink():
        raise ResearchGateError(
            f"output directory {output_dir} already exists; refusing to overwrite any "
            "previous run"
        )

    run_id = uuid4().hex
    running = manifest_preamble(
        run_id=run_id,
        spec=spec,
        contract=contract,
        root=root,
        baseline_hash=baseline_hash,
        run_kind="toy4_f0_simulation",
        parameter_vector=toy4_parameter_vector(spec),
        input_artifact_hashes=forcing.input_artifact_hashes,
        initial_recipe_hash=initial_recipe_hash,
        engine_version=TOY4_ENGINE_VERSION,
        parent_run_id=parent_run_id or None,
        resumed_from_checkpoint=str(resume_from) if resume_from is not None else None,
    )
    output_dir.mkdir(parents=True)
    write_manifest_atomic(output_dir, running)

    state: Toy4State | None = None
    history: Toy4History | None = None
    rng: RngRegistry | None = None
    checkpoint_paths: list[str] = []
    saved_boundaries: set[int] = set()
    admitted_ticks = 0
    if resume_from is not None:
        state, history, rng = _resume_state, _resume_history, _resume_rng
        admitted_ticks = _resume_state.completed_ticks
    try:
        if resume_from is None:
            rng = RngRegistry(spec.seed)
            state = initialize_toy4(spec, rng)
            history = Toy4History()
            history.digest_chain = initial_digest_chain(
                spec=spec,
                baseline_hash=baseline_hash,
                lock_hash=lock_hash,
                parameter_hash=parameter_hash,
                initial_recipe_hash=initial_recipe_hash,
                input_artifact_hashes=forcing.input_artifact_hashes,
                initial_state=state,
            )
        assert state is not None and history is not None and rng is not None
        parameters = spec.toy4_parameters
        assert parameters is not None
        compute_s = 0.0
        aggregate_s = 0.0
        checkpoint_s = 0.0
        run_started = time.perf_counter()
        cpu_started = time.process_time()

        admitted_ticks = state.completed_ticks
        while state.completed_ticks < target_ticks:
            started = time.perf_counter()
            expected_tick = state.completed_ticks
            opening = capture_mutable_stocks(state)
            flows = tick_toy4(state, forcing, parameters)
            if flows.tick != expected_tick or state.completed_ticks != expected_tick + 1:
                raise ResearchGateError(
                    f"tick {flows.tick} does not describe the next admitted quarter "
                    f"{expected_tick}"
                )
            # The runner binds the returned external flows to the admitted
            # forcing before any digest advance or checkpoint publication.
            if not np.array_equal(flows.imports, forcing.imports[flows.tick]) or not np.array_equal(
                flows.export_desired, forcing.export_orders[flows.tick]
            ):
                raise ResearchGateError(
                    f"tick {flows.tick} external flows do not match the admitted forcing"
                )
            invariant_summary = check_toy4_invariants(
                opening, state, flows, parameters
            )
            check_toy4_state_identities(
                state, parameters, flows.quarter, _initial_household_cash(spec)
            )
            # The digest chain advances only for a tick that passed the outer
            # gate, so a rejected quarter never enters the replay record.
            history.digest_chain = advance_chain(history.digest_chain, state, flows)
            admitted_ticks = state.completed_ticks
            compute_s += time.perf_counter() - started

            started = time.perf_counter()
            append_compact_rows(
                history,
                state,
                flows,
                parameters,
                region_ids=list(spec.region_ids),
                commodity_ids=list(spec.commodities),
                digest=history.digest_chain,
                invariant_summary=invariant_summary,
            )
            aggregate_s += time.perf_counter() - started

            boundary = state.completed_ticks
            paused_here = boundary == target_ticks and target_ticks < spec.ticks
            due = (
                (checkpoint_every > 0 and boundary % checkpoint_every == 0)
                or paused_here
                or (checkpoint_every > 0 and boundary == spec.ticks)
            )
            if due and boundary not in saved_boundaries:
                started = time.perf_counter()
                path = save_toy4_checkpoint(
                    checkpoint_dir(output_dir, boundary),
                    state,
                    history,
                    rng,
                    {
                        "scenario": spec.model_dump(mode="json"),
                        "scenario_hash": compute_scenario_hash(spec),
                        "baseline_hash": baseline_hash,
                        "lock_hash": lock_hash,
                        "parameter_hash": parameter_hash,
                        "initial_recipe_hash": initial_recipe_hash,
                        "input_artifact_hashes": dict(
                            forcing.input_artifact_hashes
                        ),
                        "region_ids": list(spec.region_ids),
                        "commodity_ids": list(spec.commodities),
                        "last_completed_quarter": str(spec.start.advance(boundary - 1)),
                        "next_quarter": str(spec.start.advance(boundary)),
                        "source_run_id": run_id,
                    },
                )
                checkpoint_s += time.perf_counter() - started
                saved_boundaries.add(boundary)
                checkpoint_paths.append(str(path.relative_to(output_dir)))

        write_started = time.perf_counter()
        frames = history_frames(history)
        write_toy4_tables(output_dir, frames)
        performance = {
            "compute_wall_s": compute_s,
            "aggregate_wall_s": aggregate_s,
            "checkpoint_wall_s": checkpoint_s,
            "total_wall_s": time.perf_counter() - run_started,
            "cpu_s": time.process_time() - cpu_started,
        }
        summary = _build_summary(
            run_id=run_id,
            spec=spec,
            state=state,
            history=history,
            frames=frames,
            rng=rng,
            parameter_hash=parameter_hash,
            initial_recipe_hash=initial_recipe_hash,
            input_artifact_hashes=dict(forcing.input_artifact_hashes),
            performance={
                **performance,
                "write_wall_s": time.perf_counter() - write_started,
            },
            checkpoint_paths=checkpoint_paths,
            research_warnings=list(contract.research_warnings),
        )
        write_summary(summary, output_dir)
        parameters_declaration = spec.toy4_parameters
        recipe_declaration = spec.toy4_initial
        assert parameters_declaration is not None and recipe_declaration is not None
        (output_dir / "parameters.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "scenario_id": spec.scenario_id,
                    "parameter_hash": parameter_hash,
                    "declaration": parameters_declaration.model_dump(mode="json"),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (output_dir / "initial_recipe.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "scenario_id": spec.scenario_id,
                    "initial_recipe_hash": initial_recipe_hash,
                    "declaration": recipe_declaration.model_dump(mode="json"),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        hashes = hash_output_tree(output_dir)
        boundary = state.completed_ticks
        status: Literal["completed", "paused"] = (
            "completed" if boundary == spec.ticks else "paused"
        )
        final = finalize_manifest(
            running,
            status=status,
            output_hashes=hashes,
            rng_draws_count=rng.draws_count(),
            rng_draws_by_module=rng.draws_by_module(),
            stochastic_modules_active=[
                module
                for module, count in rng.draws_by_module().items()
                if count > 0
            ],
            deterministic_replay_digest=history.digest_chain,
            completed_ticks=boundary,
            last_completed_quarter=(
                str(spec.start.advance(boundary - 1)) if boundary else None
            ),
        )
        write_manifest_atomic(output_dir, final)
        return final
    except Exception as exc:  # noqa: BLE001 - record evidence, then re-raise
        draws_by_module = rng.draws_by_module() if rng is not None else {}
        boundary = admitted_ticks
        failed = finalize_manifest(
            running,
            status="failed",
            output_hashes={},
            rng_draws_count=sum(draws_by_module.values()),
            rng_draws_by_module=draws_by_module,
            stochastic_modules_active=[
                module for module, count in draws_by_module.items() if count > 0
            ],
            deterministic_replay_digest="",
            failure_message=f"{type(exc).__name__}: {exc}",
            completed_ticks=boundary,
            last_completed_quarter=(
                str(spec.start.advance(boundary - 1)) if boundary else None
            ),
        )
        try:
            write_manifest_atomic(output_dir, failed)
        except OSError:  # pragma: no cover - evidence already lost
            pass
        raise
