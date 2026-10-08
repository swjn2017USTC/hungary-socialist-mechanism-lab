"""P04 political runner: the single admission owner for a politics-enabled run.

One admitted quarter, in the pinned order:

1. read the immutable external slice and the active events (explicit channels);
2. apply one-shot / windowed interventions to *temporary* views, select the
   lagged published observation, prepare the coalition feedback, update the
   coalition weights and form the policy (Mode A replay / Mode B broker /
   Mode C = base + declared interventions);
3. commit the coalition/policy/culture/capability transition and compile the
   effective material/household parameters (+ the central-vs-local mix);
4. run the material kernel (the only producer of realized quantities);
5. update county opposition / household culture / action, form the closing
   observation ring, the objective/prediction rings and the planner forecast;
6. run the material invariants and the P04 gates; only then advance the chain,
   append the tables and checkpoint.

Mode C is created *only* by an explicit checkpoint fork: the child restores the
parent's full state at the boundary and then diverges solely through the
declared interventions.  No LLM/decision client is involved anywhere.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import numpy as np

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.politics import (
    OPPOSITION_AXIS_IDS,
    POLICY_COORDINATES,
    POLITICAL_FEATURE_IDS,
    SIGNAL_CHANNELS,
    BroadcastEnvelope,
    BrokerParameters,
    CoalitionTransition,
    EventRegistry,
    ExternalWorldPack,
    ExternalWorldSlice,
    F,
    InformationMessage,
    InformationProgram,
    InformationState,
    InterventionOperation,
    InterventionSpec,
    J,
    PolicyDecision,
    PolicyReplayRegistry,
    PolicyVector,
    PoliticalFeedback,
    PoliticalMode,
    PoliticalRunSpec,
    PoliticalSignals,
    TruthSnapshot,
    U,
    normalize_policy_vector,
    resolve_political_parameters,
)
from hsm_lab.contract.schemas import (
    Quarter,
    ResearchContract,
    ResearchGateError,
    ScenarioSpec,
)
from hsm_lab.data.external import (
    compile_policy_schedule,
    load_event_registry,
    load_external_pack,
    load_information_program,
)
from hsm_lab.engine.accounting import check_material_invariants, finance_balance_residuals
from hsm_lab.engine.culture import classify_content, update_household_culture, visibility_multiplier
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.material import (
    MATERIAL_RUN_KIND,
    _material_residuals,
    _tick_index,
    canonical_material_bytes,
    initial_digest_chain,
    load_material_forcing,
    material_parameter_vector,
    material_recipe_hash,
    tick_material,
)
from hsm_lab.engine.network import build_material_network
from hsm_lab.engine.observation import MEASUREMENT_MODULE, form_enterprise_reports, observe_state
from hsm_lab.engine.opposition import action_propensity, update_region_capacity
from hsm_lab.engine.policy import (
    TickControls,
    compile_effective_policy,
    default_initial_policy,
)
from hsm_lab.engine.political_state import (
    POLITICAL_RING_LENGTH,
    POLITICAL_STATE_VERSION,
    PoliticalState,
    canonical_political_bytes,
    canonical_political_hash,
    initial_political_state,
    political_arrays,
    resolve_political_axes,
    state_from_political_arrays,
)
from hsm_lab.engine.politics import choose_policy, update_coalitions
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import (
    MATERIAL_STATE_VERSION,
    MaterialHistory,
    MaterialState,
    capture_material_stocks,
    initialize_material,
)
from hsm_lab.engine.technology import advance_information_capacity, information_state
from hsm_lab.provenance.manifest import (
    RunManifest,
    canonical_digest,
    compute_lock_hash,
    compute_parameter_hash,
    compute_scenario_hash,
    finalize_manifest,
    hash_output_tree,
    manifest_preamble,
    write_manifest_atomic,
)
from hsm_lab.storage.fork import ForkOrigin, build_branch_spec
from hsm_lab.storage.material_output import (
    append_material_rows,
    history_frames,
    write_material_tables,
)
from hsm_lab.storage.output import write_summary
from hsm_lab.storage.political_output import (
    information_rows,
    opposition_row,
    policy_decision_rows,
    political_event_row,
    political_quarter_row,
)

POLITICAL_RUN_KIND: Literal["p04_political_simulation"] = "p04_political_simulation"
POLITICAL_RESEARCH_WARNING = "p04_structural_politics_not_historical_fit"
POLITICAL_ENGINE_VERSION_FULL = "material-engine-v3"

_FEATURE = {name: index for index, name in enumerate(POLITICAL_FEATURE_IDS)}
_COORDINATE = {name: index for index, name in enumerate(POLICY_COORDINATES)}
_SIGNAL = {name: index for index, name in enumerate(SIGNAL_CHANNELS)}
_GROWTH = _FEATURE["growth"]
_SHORTAGE = _FEATURE["shortage"]
_DEBT = _FEATURE["debt_pressure"]
_UNREST = _FEATURE["worker_unrest"]
_CONTRACT_GAP = _FEATURE["contract_gap"]
_SOVIET = _FEATURE["soviet_constraint"]
_EXTERNAL_PRESSURE = _FEATURE["external_pressure"]
_POLICY_ERROR = _FEATURE["previous_policy_error"]
_COHESION = _FEATURE["elite_cohesion"]
_TECHNOLOGY = _FEATURE["technology_capacity"]
_REPRESSION = _COORDINATE["repression"]
_ENTERPRISE_AUTONOMY = _COORDINATE["enterprise_autonomy"]
_CULTURAL_OPENNESS = _COORDINATE["cultural_openness"]


# ---------------------------------------------------------------------------
# Interventions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompiledIntervention:
    """One intervention compiled to absolute quarter ordinals / messages."""

    spec: InterventionSpec
    start_ordinal: int
    end_ordinal: int | None
    message: InformationMessage | None

    def active(self, ordinal: int) -> bool:
        if ordinal < self.start_ordinal:
            return False
        return self.end_ordinal is None or ordinal <= self.end_ordinal

    def one_shot(self, ordinal: int) -> bool:
        return ordinal == self.start_ordinal


def compile_interventions(
    interventions: list[InterventionSpec], start_ordinal: int
) -> list[CompiledIntervention]:
    """Compile declared interventions to absolute ordinals and broadcast messages.

    ``start_ordinal`` is the scenario's first-quarter ordinal, so a broadcast's
    ``at_step`` is the global closing step (initial=0) that the information
    scheduler and the checkpoints agree on.
    """
    compiled: list[CompiledIntervention] = []
    for spec in interventions:
        start = spec.effective_quarter.to_ordinal()
        end = None if spec.until_quarter is None else spec.until_quarter.to_ordinal()
        message = None
        if spec.operation is InterventionOperation.BROADCAST:
            envelope = spec.value
            if not isinstance(envelope, BroadcastEnvelope):  # pragma: no cover - validated
                raise ConfigError("broadcast intervention lacks a typed envelope")
            audience_all = bool(envelope.audience.all)
            message = InformationMessage(
                message_id=f"cf:{spec.intervention_id}",
                at_step=start - start_ordinal + 1,
                ttl=envelope.ttl,
                audience_all=audience_all,
                region_ids=(() if audience_all else tuple(envelope.audience.region_id_in or ())),
                channel=envelope.channel,
                intensity=envelope.intensity,
                content_sensitivity=envelope.content_sensitivity,
                content=envelope.content,
                display_only=False,
            )
        compiled.append(
            CompiledIntervention(spec=spec, start_ordinal=start, end_ordinal=end, message=message)
        )
    return compiled


# ---------------------------------------------------------------------------
# Static run context
# ---------------------------------------------------------------------------


@dataclass
class PoliticalRuntime:
    spec: ScenarioSpec
    contract: ResearchContract
    registry: Any
    politics: PoliticalRunSpec
    pack: ExternalWorldPack
    events: EventRegistry
    program: InformationProgram
    replay: PolicyReplayRegistry | None
    schedule: dict[str, list[float]] | None
    forcing: Any
    interventions: list[CompiledIntervention]
    base_mode: PoliticalMode
    branch: Any = None
    root_parameter_hash: str = ""
    branch_parameter_hash: str = ""
    resuming_counterfactual: bool = False
    logical_mode: PoliticalMode | None = None


def _external_pressure(pack: ExternalWorldPack, tick: int) -> float:
    if tick <= 0:
        return 0.0
    oil = pack.values[:, pack.variable_ids.index("world_oil_price")]
    rate = pack.values[:, pack.variable_ids.index("global_usd_rate")]
    pressures = []
    for series in (oil, rate):
        previous, current = float(series[tick - 1]), float(series[tick])
        if np.isfinite(previous) and np.isfinite(current) and abs(previous) > 1e-12:
            pressures.append(abs(current / previous - 1.0))
    return float(np.clip(sum(pressures), 0.0, 1.0))


def _initial_published() -> np.ndarray:
    """Initial-prior published observation vector (declared, all-zero)."""
    return np.zeros(F, dtype=np.float64)


def _feedback(
    *,
    runtime: PoliticalRuntime,
    political: PoliticalState,
    published: np.ndarray,
    valid: np.ndarray,
    external: ExternalWorldSlice,
    tick: int,
    soviet_constraint: float,
    cohesion: float,
    capability: float,
) -> PoliticalFeedback:
    reported = np.asarray(published, dtype=np.float64).copy()
    features = reported.copy()
    features[_GROWTH] = float(np.clip(features[_GROWTH], -1.0, 1.0))
    for index in range(F):
        if index != _GROWTH:
            features[index] = float(np.clip(features[index], 0.0, 1.0))
    # A coordinate with no valid published measurement keeps the declared
    # initial prior (zero) rather than a fabricated value.
    features = np.where(np.asarray(valid, dtype=bool), features, 0.0)
    features[_SOVIET] = float(np.clip(soviet_constraint, 0.0, 1.0))
    features[_EXTERNAL_PRESSURE] = _external_pressure(runtime.pack, tick)
    features[_TECHNOLOGY] = float(np.clip(capability, 0.0, 1.0))
    features[_COHESION] = float(np.clip(cohesion, 0.0, 1.0))
    objective = np.array(
        [
            1.0 - float(features[_UNREST]),
            1.0 - float(np.clip(soviet_constraint, 0.0, 1.0)),
            1.0 - float(features[_CONTRACT_GAP]),
            float(features[_COHESION]),
            1.0 - float(features[_DEBT]),
        ],
        dtype=np.float64,
    )
    return PoliticalFeedback(
        features_raw=reported.copy(),
        features_reported=reported.copy(),
        features=features,
        valid=np.asarray(valid, dtype=bool).copy(),
        growth_undefined=not bool(valid[_GROWTH]),
        objective_vector=objective,
        policy_error=float(np.clip(political.policy_error[0], 0.0, 1.0)),
    )


def _policy_error(
    previous_policy: PolicyVector, objective: np.ndarray, a_matrix: np.ndarray
) -> tuple[float, np.ndarray]:
    """Compare the previous policy's five-objective proxy with the observed one.

    ``prediction = clip(A @ normalize(previous_policy), -1, 1)`` is the declared
    structural proxy for what the coalition expected the five objectives to be
    under the policy it just ran; the error is the mean absolute deviation from
    the same quarter's reported/clipped objective vector.
    """
    prediction = np.clip(a_matrix @ normalize_policy_vector(previous_policy.to_vector()), -1.0, 1.0)
    error = float(
        np.clip(np.mean(np.abs(prediction - np.asarray(objective, dtype=np.float64))), 0.0, 1.0)
    )
    return error, prediction


def _update_policy_error(
    *,
    runtime: PoliticalRuntime,
    political: PoliticalState,
    previous_policy: PolicyVector,
    objective: np.ndarray,
    tick: int,
) -> None:
    """Write the prediction/objective rings and the current policy error."""
    a_matrix = np.asarray(runtime.politics.parameters.broker.A, dtype=np.float64)
    error, prediction = _policy_error(previous_policy, objective, a_matrix)
    slot = int(tick) % POLITICAL_RING_LENGTH
    political.prediction_history[slot] = prediction
    political.objective_history[slot] = np.asarray(objective, dtype=np.float64)
    political.policy_error = np.array([error], dtype=np.float64)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_political(
    spec: ScenarioSpec,
    output_dir: Path,
    contract: ResearchContract,
    registry: Any,
    *,
    until: Quarter | str | None = None,
    checkpoint_every: int = 0,
    resume_from: Path | None = None,
    fork_from: ForkOrigin | None = None,
    interventions: list[InterventionSpec] | None = None,
) -> RunManifest:
    """Run (or resume/fork) a P04 politics-enabled scenario into a fresh dir."""

    if spec.kind != "material":
        raise ConfigError(f"run_political requires kind='material', got {spec.kind!r}")
    if spec.politics is None:
        raise ConfigError("run_political requires a politics block (use run_material otherwise)")
    contract_check = contract
    root = registry.root
    from hsm_lab.contract.guards import BASELINE_FILENAME, verify_baseline

    verify_baseline(root / BASELINE_FILENAME, contract_check)
    spec.validate_for_run(contract_check)
    if checkpoint_every < 0:
        raise ConfigError("checkpoint_every must be non-negative")

    if resume_from is not None:
        # The boundary tick is read from the checkpoint metadata below.
        pass

    parent_scenario = spec if fork_from is None else fork_from.parent_scenario
    effective_spec = spec
    politics = spec.politics
    assert isinstance(politics, PoliticalRunSpec)

    # Resuming a counterfactual child must restore its branch context: the root
    # base mode and every intervention already in force.  `run --resume` never
    # appends interventions (a new divergence requires a new fork).
    resuming_counterfactual = False
    compiled_interventions: list[CompiledIntervention] = []
    if resume_from is not None:
        from hsm_lab.storage.fork import (
            inherited_interventions_of,
            resolve_root_base_mode,
        )

        resume_metadata_path = Path(resume_from) / "metadata.json"
        if not resume_metadata_path.is_file():
            raise ResearchGateError(f"resume source is not a checkpoint directory: {resume_from}")
        resume_metadata = json.loads(resume_metadata_path.read_text(encoding="utf-8"))
        if resume_metadata.get("branch") is not None:
            politics = politics.model_copy(update={"mode": PoliticalMode.COUNTERFACTUAL})
            compiled_interventions = compile_interventions(
                inherited_interventions_of(resume_metadata), spec.start.to_ordinal()
            )
            resuming_counterfactual = True
            # The root base mode is authoritative over whatever the template
            # scenario declares.
            resume_base_mode = resolve_root_base_mode(resume_metadata)
        else:
            resume_base_mode = None
    else:
        resume_base_mode = None
    from hsm_lab.engine.policy import default_initial_policy as _dip

    resolved_parameters = resolve_political_parameters(politics.parameters, _dip(spec))
    politics = politics.model_copy(update={"parameters": resolved_parameters})
    if fork_from is not None:
        base_mode = fork_from.base_mode
        compiled_interventions = compile_interventions(
            [*fork_from.inherited_interventions, *fork_from.interventions],
            spec.start.to_ordinal(),
        )
    elif resume_base_mode is not None:
        base_mode = resume_base_mode
    else:
        base_mode = politics.mode
        if interventions:
            compiled_interventions = compile_interventions(interventions, spec.start.to_ordinal())

    forcing = load_material_forcing(effective_spec, registry)
    parameter_vector = {
        **material_parameter_vector(effective_spec),
        **politics.parameters.flatten(),
    }
    parameter_hash = compute_parameter_hash(parameter_vector)

    pack = load_external_pack(politics, registry)
    events = load_event_registry(root)
    program = load_information_program(root, pack.information_program_path or "")
    schedule: dict[str, list[float]] | None = None
    if (
        base_mode is PoliticalMode.HISTORICAL_REPLAY
        and politics.mode is not PoliticalMode.COUNTERFACTUAL
    ):
        all_quarters = [str(spec.start.advance(k)) for k in range(spec.ticks)]
        schedule = compile_policy_schedule(politics, registry, all_quarters)
    if (
        base_mode is PoliticalMode.HISTORICAL_REPLAY
        and politics.mode is PoliticalMode.COUNTERFACTUAL
        and politics.replay_registry
    ):
        all_quarters = [str(spec.start.advance(k)) for k in range(spec.ticks)]
        schedule = compile_policy_schedule(politics, registry, all_quarters)

    branch = None
    if fork_from is not None:
        # Branch effective-parameter hash: the base parameter hash plus the
        # declared intervention schedule.  It never masquerades as the base
        # parameter_hash.
        branch_parameter_hash = canonical_digest(
            {
                "base_parameter_hash": parameter_hash,
                "interventions": [
                    item.spec.model_dump(mode="json") for item in compiled_interventions
                ],
            }
        )
        branch = build_branch_spec(
            origin=fork_from,
            child_spec=spec,
            root_parameter_hash=parameter_hash,
            branch_parameter_hash=branch_parameter_hash,
            external_history_hash=pack.pack_hash,
            root_scenario_hash=compute_scenario_hash(parent_scenario),
        )

    runtime = PoliticalRuntime(
        spec=effective_spec,
        contract=contract_check,
        registry=registry,
        politics=politics,
        pack=pack,
        events=events,
        program=program,
        replay=None,
        schedule=schedule,
        forcing=forcing,
        interventions=compiled_interventions,
        base_mode=base_mode,
        branch=branch,
        root_parameter_hash=parameter_hash,
        branch_parameter_hash=parameter_hash,
        resuming_counterfactual=resuming_counterfactual,
    )
    return _execute(runtime, output_dir, registry, until, checkpoint_every, resume_from, fork_from)


def _objective_weights(spec: ScenarioSpec, politics: PoliticalRunSpec, registry: Any) -> np.ndarray:
    return np.ones(J, dtype=np.float64)


def _opposition_initial(
    spec: ScenarioSpec, politics: PoliticalRunSpec, registry: Any
) -> np.ndarray:
    parameters = politics.parameters.opposition
    return np.tile(
        np.asarray(parameters.initial_state, dtype=np.float64), (len(spec.region_ids), 1)
    )


def _execute(
    runtime: PoliticalRuntime,
    output_dir: Path,
    registry: Any,
    until: Quarter | str | None,
    checkpoint_every: int,
    resume_from: Path | None,
    fork_from: ForkOrigin | None,
) -> RunManifest:
    from hsm_lab.storage.checkpoint import (
        checkpoint_dir,
        load_material_checkpoint,
        save_material_checkpoint,
    )

    spec = runtime.spec
    contract = runtime.contract
    root = registry.root
    from hsm_lab.contract.guards import BASELINE_FILENAME, verify_baseline

    baseline_hash = verify_baseline(root / BASELINE_FILENAME, contract)
    forcing = runtime.forcing
    politics = runtime.politics
    parameters = politics.parameters
    parameter_vector = {
        **material_parameter_vector(spec),
        **parameters.flatten(),
    }
    parameter_hash = compute_parameter_hash(parameter_vector)
    lock_hash = compute_lock_hash(root)
    initial_recipe_hash = material_recipe_hash(spec)

    def _parse_until(value: Any) -> Quarter | None:
        if value is None:
            return None
        return Quarter.parse(value) if isinstance(value, str) else value

    until_quarter = _parse_until(until)

    # --- initial condition draw / restore --------------------------------
    rng: RngRegistry | None = None
    state: MaterialState | None = None
    political: PoliticalState | None = None
    history: MaterialHistory | None = None
    resume_boundary = 0
    parent_run_id: str | None = None
    restored_metadata: dict[str, Any] = {}
    restore_source = (
        resume_from
        if resume_from is not None
        else (None if fork_from is None else fork_from.checkpoint)
    )
    probe_rng = RngRegistry(spec.seed)
    probe_initial = build_material_initial_conditions(spec, probe_rng)
    network = build_material_network(spec, contract, probe_initial)
    axes = resolve_political_axes(
        households=spec.households,
        regions=len(spec.region_ids),
        organizations=int(spec.organizations or 0),
        commodities=len(spec.commodities),
        interventions=len(runtime.interventions),
    )
    if restore_source is not None:
        # Read the boundary first so the expected RNG profile (measurement
        # draws = boundary * F) can be checked in a single strict load.
        metadata_path = restore_source / "metadata.json"
        if not metadata_path.is_file():
            raise ResearchGateError(f"checkpoint metadata not found: {metadata_path}")
        boundary_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        resume_boundary = int(boundary_meta["completed_ticks"])
        state, history, rng, restored_metadata = load_material_checkpoint(
            restore_source,
            spec,
            contract,
            network,
            extra_rng_modules=(
                {MEASUREMENT_MODULE: resume_boundary * F} if spec.stochastic else {}
            ),
        )
        if "political" not in restored_metadata:
            raise ResearchGateError(
                "checkpoint carries no political payload; it was not written by a P04 run"
            )
        political = state_from_political_arrays(
            {name: np.asarray(value) for name, value in restored_metadata["political"].items()},
            axes,
        )
        # The branch intervention ledger is branch-defined: a child fork has its
        # own (inherited + declared) schedule, so rebuild the TTL axis to match.
        if political.intervention_ttl.shape[0] != len(runtime.interventions):
            political.intervention_ttl = np.zeros(len(runtime.interventions), dtype=np.int64)
        parent_run_id = str(restored_metadata.get("source_run_id") or "")
    else:
        rng = RngRegistry(spec.seed)
        initial = build_material_initial_conditions(spec, rng)
        network = build_material_network(spec, contract, initial)
        state = initialize_material(spec, initial, network)
        political = _initial_state(spec, politics, state, network, axes, len(runtime.interventions))
        history = MaterialHistory()
        history.digest_chain = _initial_chain(
            spec=spec,
            baseline_hash=baseline_hash,
            lock_hash=lock_hash,
            parameter_hash=parameter_hash,
            initial_recipe_hash=initial_recipe_hash,
            input_artifact_hashes=dict(forcing.input_artifact_hashes),
            initial_state=state,
            political=political,
        )
    assert state is not None and political is not None and history is not None and rng is not None

    # The observation references are the initial report normalization carried in
    # the political state (checkpointed, never updated from future outcomes).
    normalization = np.asarray(political.report_normalization, dtype=np.float64)
    parameters = politics.parameters
    observation_parameters = parameters.observation.model_copy(
        update={
            "need_reference": float(max(normalization[0], 1e-12)),
            "inventory_reference": float(max(normalization[1], 1e-12)),
            "capacity_reference": float(max(normalization[2], 1e-12)),
        }
    )
    parameters = parameters.model_copy(update={"observation": observation_parameters})
    politics = politics.model_copy(update={"parameters": parameters})
    runtime.politics = politics

    if until_quarter is not None:
        end = spec.start.advance(spec.ticks - 1)
        if (
            not spec.start.advance(resume_boundary).to_ordinal()
            <= until_quarter.to_ordinal()
            <= end.to_ordinal()
        ):
            raise ConfigError(f"--until {until_quarter} lies outside the remaining window")
        target_ticks = until_quarter.to_ordinal() - spec.start.to_ordinal() + 1
    else:
        target_ticks = spec.ticks

    if output_dir.exists() or output_dir.is_symlink():
        raise ResearchGateError(
            f"output directory {output_dir} already exists; refusing to overwrite any previous run"
        )

    run_id = uuid4().hex
    running = manifest_preamble(
        run_id=run_id,
        spec=spec,
        contract=contract,
        root=root,
        baseline_hash=baseline_hash,
        run_kind=MATERIAL_RUN_KIND,
        parameter_vector=parameter_vector,
        input_artifact_hashes=dict(forcing.input_artifact_hashes) | dict(pack_hashes(runtime.pack)),
        initial_recipe_hash=initial_recipe_hash,
        engine_version=POLITICAL_ENGINE_VERSION_FULL,
        parent_run_id=parent_run_id or None,
        resumed_from_checkpoint=str(restore_source) if restore_source is not None else None,
    )
    logical_mode = (
        PoliticalMode.COUNTERFACTUAL
        if (runtime.branch is not None or runtime.resuming_counterfactual)
        else runtime.base_mode
    )
    runtime.logical_mode = logical_mode
    running = running.model_copy(
        update={
            "run_kind": POLITICAL_RUN_KIND,
            "political_mode": logical_mode,
        }
    )
    output_dir.mkdir(parents=True)
    write_manifest_atomic(output_dir, running)

    runtime_network = dataclasses.replace(network)
    index = _tick_index(network)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    hh_region = np.asarray(state.household_region, dtype=np.int64)
    hh_weight = np.asarray(state.household_weight, dtype=np.float64)
    region_count = len(spec.region_ids)
    org_count = int(state.organization_id.shape[0])
    g_count = len(network.commodity_ids)

    # Formation inputs: static county education/sector margins via household weights.
    education = np.asarray(state.household_education, dtype=np.int64)
    sector = np.asarray(state.household_sector, dtype=np.int64)
    tertiary = (education == 2).astype(np.float64)
    industry = (sector == 0).astype(np.float64)
    intellectual_density = _county_mean(tertiary, hh_weight, hh_region, region_count)
    worker_density = _county_mean(industry, hh_weight, hh_region, region_count)
    formation_inputs = np.stack([intellectual_density, worker_density], axis=1)

    # County contact for the Western-exposure target (fixed initial margin).
    initial_exposure = np.asarray(state.household_western_exposure, dtype=np.float64).copy()
    county_contact = initial_exposure.copy()

    tallies: dict[str, Any] = {
        "max_material_abs_residual": 0.0,
        "max_material_tolerance_ratio": 0.0,
        "max_finance_abs_residual": 0.0,
        "max_finance_tolerance_ratio": 0.0,
        "soviet_violations": 0,
        "delivered_broadcasts": 0,
    }
    checkpoint_paths: list[str] = []
    saved_boundaries: set[int] = set()
    admitted_ticks = int(state.completed_ticks)
    # Rebuild the broadcast scheduler state for the restored boundary: all
    # program messages whose [at_step, at_step+ttl) covers steps 1..boundary.
    program_state = _ProgramState(runtime.program, resume_boundary)
    cf_state = _InterventionState(runtime.interventions, spec.start.to_ordinal())

    try:
        run_started = time.perf_counter()
        while state.completed_ticks < target_ticks:
            tick = int(state.completed_ticks)
            quarter = Quarter.parse(str(forcing.quarters[tick]))
            opening = capture_material_stocks(state)
            external = runtime.pack.slice(tick)

            # --- 2. signals, interventions, coalition, policy ---------------
            signals_prev = np.asarray(political.signals, dtype=np.float64)
            deliver_rows, county_signals, cf_government = _deliver_broadcasts(
                tick=tick,
                quarter=quarter,
                runtime=runtime,
                political=political,
                state=state,
                network=network,
                program_state=program_state,
                cf_state=cf_state,
                region_count=region_count,
                hh_region=hh_region,
            )
            signals = _advance_signals(signals_prev, runtime, tick, county_signals, region_count)
            government = _government_signals(signals, external, cf_government)
            political.signals = signals

            # Declared counterfactual controls resolved for this quarter: the
            # Soviet-constraint multiplier and the branch broadcast TTL ledger.
            multiplier = cf_state.soviet_multiplier(tick)
            if multiplier is None:
                multiplier = 1.0
            political.soviet_constraint_multiplier = np.array([float(multiplier)], dtype=np.float64)
            soviet_constraint = float(
                np.clip(external.get("soviet_constraint", 0.0) * float(multiplier), 0.0, 1.0)
            )
            ttl = _remaining_ttl(cf_state, tick)
            if political.intervention_ttl.shape[0] == ttl.shape[0]:
                political.intervention_ttl = ttl

            decision_policy, coalition_transition, decision = _decision_step(
                runtime=runtime,
                political=political,
                signals=signals,
                external=external,
                tick=tick,
                quarter=quarter,
                cf_state=cf_state,
                government=government,
                county_signals=county_signals,
                soviet_constraint=soviet_constraint,
            )

            # --- 3. commit transitions, compile effective policy ------------
            if coalition_transition is not None:
                political.coalition_weights = coalition_transition.new_weights
            capability_before = float(political.information_capability[0])
            info_state_before = InformationState(
                capability=capability_before,
                dimensions=np.asarray(political.information_dimensions, dtype=np.float64),
                total_lag=_total_lag(political, parameters),
            )
            political.policy = decision_policy.to_vector()
            effective = compile_effective_policy(
                spec.material_parameters,  # type: ignore[arg-type]
                spec.household_parameters,  # type: ignore[arg-type]
                decision_policy,
                external,
                tuple(network.commodity_ids),
            )
            object.__setattr__(
                runtime_network, "household_parameters", effective.household_parameters
            )
            object.__setattr__(runtime_network, "household_catalog", effective.household_catalog)
            central = _central_target(
                political=political,
                network=network,
                plan_utilization=float(decision_policy.plan_utilization),
                tick=tick,
            )
            controls = TickControls(
                material_parameters=effective.material_parameters,
                household_parameters=effective.household_parameters,
                household_catalog=effective.household_catalog,
                autonomy=float(decision_policy.enterprise_autonomy),
                central_target=central,
                policy=decision_policy,
            )

            # --- 4. material tick ------------------------------------------
            flows = tick_material(
                state,
                forcing,
                effective.material_parameters,
                runtime_network,
                controls=controls,
            )
            if flows.tick != tick:
                raise ResearchGateError("material tick does not describe the expected quarter")

            # --- 5. closing: culture, opposition, action --------------------
            household_signals = county_signals[hh_region]
            openness = float(decision_policy.cultural_openness)
            western_visible = household_signals[:, _SIGNAL["western_comparison"]]
            identification, exposure, efficacy = update_household_culture(
                np.asarray(political.household_identification, dtype=np.float64),
                np.asarray(political.household_exposure, dtype=np.float64),
                np.asarray(political.household_efficacy, dtype=np.float64),
                official_signal_visible=float(
                    np.mean(county_signals[:, _SIGNAL["official_policy"]])
                ),
                western_signal_visible=western_visible,
                region_exposure_target=np.zeros(region_count, dtype=np.float64),
                region_efficacy=np.asarray(
                    political.opposition[:, OPPOSITION_AXIS_IDS.index("perceived_efficacy")]
                ),
                household_region=hh_region,
                exposure_contact=county_contact,
                parameters=parameters.culture,
                openness=openness,
            )
            political.household_identification = identification
            political.household_exposure = exposure
            political.household_efficacy = efficacy

            opposition = update_region_capacity(
                np.asarray(political.opposition, dtype=np.float64),
                formation_inputs,
                decision_policy,
                county_signals,
                external,
                parameters.opposition,
            )
            political.opposition = opposition
            risk_signal = np.asarray(
                county_signals[:, _SIGNAL["public_action_risk"]], dtype=np.float64
            )
            risk_signal = np.clip(risk_signal, 0.0, 1.0)
            grievance = np.asarray(state.household_grievance, dtype=np.float64)
            action = action_propensity(
                grievance,
                hh_region,
                np.asarray(political.household_exposure, dtype=np.float64),
                np.asarray(political.household_efficacy, dtype=np.float64),
                opposition,
                decision_policy,
                risk_signal,
                parameters.opposition,
                region_count,
            )
            political.household_action = action

            # capability accumulation (uses the chosen policy; next-quarter effect)
            new_info = advance_information_capacity(
                info_state_before, decision_policy, external, parameters.information
            )
            if cf_capability_override := cf_state.capability_override(tick):
                new_info = information_state(cf_capability_override, parameters.information)
            political.information_capability = np.array([new_info.capability], dtype=np.float64)
            political.information_dimensions = np.asarray(new_info.dimensions, dtype=np.float64)

            # --- closing truth features + observation ring ------------------
            truth = _closing_truth(
                state=state,
                political=political,
                flows=flows,
                external=external,
                index=index,
                cell_commodity=cell_commodity,
                g_count=g_count,
                debt_reference=parameters.external_recipe.debt_reference,
                capability=new_info.capability,
                tick=tick,
                soviet_constraint=soviet_constraint,
            )
            _commit_report_ring(
                political=political,
                runtime=runtime,
                state=state,
                network=network,
                flows=flows,
                truth=truth,
                info_state=new_info,
                tick=tick,
                quarter=quarter,
                rng=rng,
                stochastic=spec.stochastic,
                index=index,
                cell_commodity=cell_commodity,
                org_count=org_count,
                g_count=g_count,
            )
            cohesion_next = _update_cohesion(
                political=political,
                parameters=parameters.broker,
                policy=decision_policy,
            )
            political.elite_cohesion = np.array([cohesion_next], dtype=np.float64)

            # --- 6. gates ---------------------------------------------------
            invariant_summary = check_material_invariants(
                opening,
                state,
                flows,
                effective.material_parameters,
                runtime_network,
                controls=controls,
            )
            residual, tolerance = _material_residuals(opening, state, flows, runtime_network)
            flows.material_balance_residual = residual
            flows.material_balance_tolerance = tolerance
            finance_residual, finance_tolerance = finance_balance_residuals(state, flows)
            flows.finance_balance_residual = finance_residual
            flows.finance_balance_tolerance = finance_tolerance
            tallies["max_material_abs_residual"] = max(
                tallies["max_material_abs_residual"],
                float(invariant_summary.max_material_abs_residual),
            )
            tallies["max_material_tolerance_ratio"] = max(
                tallies["max_material_tolerance_ratio"],
                float(invariant_summary.max_material_tolerance_ratio),
            )

            # --- commit -----------------------------------------------------
            state.completed_ticks += 1
            history.digest_chain = _advance_chain(
                previous=history.digest_chain,
                state=state,
                flows=flows,
                political=political,
                deliveries=deliver_rows,
            )
            admitted_ticks = state.completed_ticks
            invariant_dict: dict[str, Any] = {
                "max_material_abs_residual": float(invariant_summary.max_material_abs_residual),
                "max_material_tolerance_ratio": float(
                    invariant_summary.max_material_tolerance_ratio
                ),
                "max_finance_abs_residual": float(invariant_summary.max_finance_abs_residual),
                "max_finance_tolerance_ratio": float(invariant_summary.max_finance_tolerance_ratio),
                "checked_cells": int(invariant_summary.checked_cells),
                "per_ledger": dict(invariant_summary.per_ledger),
                "forcing_segment": str(forcing.segment[tick]),
                "treasury_deposit_open": float(opening.treasury_deposit),
                "bank_reserves_open": [float(v) for v in opening.bank_reserves],
                "housing_completed": float(
                    np.sum(np.asarray(state.dwelling_stock) - opening.dwelling_stock)
                ),
                "material_balance_residual": [float(v) for v in residual],
                "material_balance_tolerance": [float(v) for v in tolerance],
            }
            append_material_rows(
                history,
                state,
                flows,
                effective.material_parameters,
                runtime_network,
                region_ids=list(spec.region_ids),
                commodity_ids=list(spec.commodities),
                digest=history.digest_chain,
                invariant_summary=invariant_dict,
                opening_stock=opening.stock_value,
            )
            _append_political_rows(
                history=history,
                runtime=runtime,
                political=political,
                state=state,
                flows=flows,
                decision=decision,
                coalition_transition=coalition_transition,
                county_signals=county_signals,
                external=external,
                tick=tick,
                quarter=quarter,
                deliverables=deliver_rows,
                region_ids=list(spec.region_ids),
                governance=government,
                info_state=new_info,
                soviet_constraint=soviet_constraint,
            )

            boundary = state.completed_ticks
            paused_here = boundary == target_ticks and target_ticks < spec.ticks
            due = (
                (checkpoint_every > 0 and boundary % checkpoint_every == 0)
                or paused_here
                or (checkpoint_every > 0 and boundary == spec.ticks)
            )
            if due and boundary not in saved_boundaries:
                path = save_material_checkpoint(
                    checkpoint_dir(output_dir, boundary),
                    state,
                    network,
                    history,
                    rng,
                    {
                        "scenario": spec.model_dump(mode="json"),
                        "scenario_hash": compute_scenario_hash(spec),
                        "baseline_hash": baseline_hash,
                        "lock_hash": lock_hash,
                        "parameter_hash": parameter_hash,
                        "initial_recipe_hash": initial_recipe_hash,
                        "engine_version": POLITICAL_ENGINE_VERSION_FULL,
                        "state_version": MATERIAL_STATE_VERSION,
                        "political_state_version": POLITICAL_STATE_VERSION,
                        "political_mode": str(logical_mode),
                        "input_artifact_hashes": dict(forcing.input_artifact_hashes),
                        "region_ids": list(spec.region_ids),
                        "commodity_ids": list(spec.commodities),
                        "last_completed_quarter": str(spec.start.advance(boundary - 1)),
                        "next_quarter": str(spec.start.advance(boundary)),
                        "source_run_id": run_id,
                        "branch": None
                        if runtime.branch is None
                        else runtime.branch.model_dump(mode="json"),
                    },
                    political_arrays=political_arrays(political, axes),
                )
                saved_boundaries.add(boundary)
                checkpoint_paths.append(str(path.relative_to(output_dir)))

        # --- finalize -------------------------------------------------------
        frames = history_frames(history)
        write_material_tables(output_dir, frames)
        summary = _build_summary(
            runtime=runtime,
            run_id=run_id,
            spec=spec,
            state=state,
            political=political,
            history=history,
            frames=frames,
            rng=rng,
            parameter_hash=parameter_hash,
            initial_recipe_hash=initial_recipe_hash,
            checkpoint_paths=checkpoint_paths,
            tallies=tallies,
            logical_mode=logical_mode,
            performance={"total_wall_s": time.perf_counter() - run_started},
        )
        write_summary(summary, output_dir)
        parameters_declaration = spec.material_parameters
        assert parameters_declaration is not None
        (output_dir / "parameters.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "scenario_id": spec.scenario_id,
                    "parameter_hash": parameter_hash,
                    "declaration": parameters_declaration.model_dump(mode="json"),
                    "political_parameters": parameters.model_dump(mode="json"),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        hashes = hash_output_tree(output_dir)
        boundary = state.completed_ticks
        status: Literal["completed", "paused"] = "completed" if boundary == spec.ticks else "paused"
        final = finalize_manifest(
            running,
            status=status,
            output_hashes=hashes,
            rng_draws_count=rng.draws_count(),
            rng_draws_by_module=rng.draws_by_module(),
            stochastic_modules_active=[
                module for module, count in rng.draws_by_module().items() if count > 0
            ],
            deterministic_replay_digest=history.digest_chain,
            completed_ticks=boundary,
            last_completed_quarter=(str(spec.start.advance(boundary - 1)) if boundary else None),
        )
        write_manifest_atomic(output_dir, final)
        return final
    except Exception as exc:  # noqa: BLE001 - record evidence, then re-raise
        draws_by_module = rng.draws_by_module() if rng is not None else {}
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
            completed_ticks=admitted_ticks,
            last_completed_quarter=(
                str(spec.start.advance(admitted_ticks - 1)) if admitted_ticks else None
            ),
        )
        try:
            write_manifest_atomic(output_dir, failed)
        except OSError:  # pragma: no cover
            pass
        raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def pack_hashes(pack: ExternalWorldPack) -> dict[str, str]:
    return {"p04_external_pack": pack.pack_hash}


def _county_mean(
    values: np.ndarray, weight: np.ndarray, region: np.ndarray, region_count: int
) -> np.ndarray:
    numerator = np.bincount(region, weights=weight * values, minlength=region_count)
    denominator = np.bincount(region, weights=weight, minlength=region_count)
    return numerator / np.maximum(denominator, 1e-12)


def _region_capacity(opposition: np.ndarray) -> np.ndarray:
    network_size = opposition[:, OPPOSITION_AXIS_IDS.index("network_size")]
    worker = opposition[:, OPPOSITION_AXIS_IDS.index("worker_linkage")]
    samizdat = opposition[:, OPPOSITION_AXIS_IDS.index("samizdat_capacity")]
    efficacy = opposition[:, OPPOSITION_AXIS_IDS.index("perceived_efficacy")]
    return network_size * np.sqrt(np.maximum(worker * samizdat, 0.0)) * efficacy


def _total_lag(political: PoliticalState, parameters: Any) -> int:
    capability = float(np.clip(political.information_capability[0], 0.0, 1.0))
    info = information_state(capability, parameters.information)
    return int(info.total_lag)


def _initial_state(
    spec: ScenarioSpec,
    politics: PoliticalRunSpec,
    state: MaterialState,
    network: Any,
    axes: dict[str, int],
    intervention_count: int,
) -> PoliticalState:
    parameters = politics.parameters
    info = information_state(politics.initial.information_capability, parameters.information)
    # Report normalization references: fixed at the initial boundary from
    # positive initial magnitudes (never updated from future outcomes).
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_pool = np.asarray(network.cell_pool, dtype=np.int64)
    stock = np.asarray(state.stock_value, dtype=np.float64)
    output_total = float(stock[(cell_owner_kind == 0) & (cell_pool == 1)].sum())
    input_total = float(stock[(cell_owner_kind == 0) & (cell_pool == 0)].sum())
    capacity_total = float(np.asarray(state.organization_capacity, dtype=np.float64).sum())
    normalization = np.array(
        [
            max(input_total, 1.0),
            max(output_total, 1.0),
            max(capacity_total, 1.0),
        ],
        dtype=np.float64,
    )
    return initial_political_state(
        households=spec.households,
        regions=len(spec.region_ids),
        organizations=int(spec.organizations or 0),
        commodities=len(spec.commodities),
        interventions=int(intervention_count),
        coalition_weights=np.asarray(politics.initial.coalition_weights, dtype=np.float64),
        policy=default_initial_policy(spec),
        elite_cohesion=politics.initial.elite_cohesion,
        information_capability=politics.initial.information_capability,
        information_dimensions=info.dimensions,
        objective_weights=np.ones(J, dtype=np.float64),
        opposition_initial=_opposition_initial(spec, politics, None),
        household_initial_ideology=np.full(
            spec.households, parameters.culture.initial_ideology, dtype=np.float64
        ),
        household_initial_exposure=np.zeros(spec.households, dtype=np.float64),
        household_initial_efficacy=np.zeros(spec.households, dtype=np.float64),
        report_normalization=normalization,
    )


def _initial_chain(
    *,
    spec: ScenarioSpec,
    baseline_hash: str,
    lock_hash: str,
    parameter_hash: str,
    initial_recipe_hash: str,
    input_artifact_hashes: dict[str, str],
    initial_state: MaterialState,
    political: PoliticalState,
) -> str:
    base = initial_digest_chain(
        spec=spec,
        baseline_hash=baseline_hash,
        lock_hash=lock_hash,
        parameter_hash=parameter_hash,
        initial_recipe_hash=initial_recipe_hash,
        input_artifact_hashes=input_artifact_hashes,
        initial_state=initial_state,
    )
    digest = hashlib.sha256()
    digest.update(bytes.fromhex(base))
    digest.update(canonical_political_bytes(political))
    return digest.hexdigest()


def _advance_chain(
    *,
    previous: str,
    state: MaterialState,
    flows: Any,
    political: PoliticalState,
    deliveries: list[dict[str, Any]],
) -> str:
    digest = hashlib.sha256()
    digest.update(bytes.fromhex(previous))
    digest.update(canonical_material_bytes(state, flows))
    digest.update(canonical_political_bytes(political))
    from hsm_lab.provenance.manifest import canonical_json

    digest.update(
        canonical_json(
            [
                [
                    row["event_id"],
                    row["channel"],
                    row["message_id"],
                    row["recipient_id"],
                    row["classification"],
                    row["delivery"],
                ]
                for row in sorted(
                    deliveries,
                    key=lambda r: (
                        r["event_id"],
                        r["channel"],
                        r["message_id"],
                        r["recipient_id"],
                    ),
                )
            ]
        )
    )
    return digest.hexdigest()


class _ProgramState:
    """Deterministic broadcast scheduler (pure function of the step)."""

    def __init__(self, program: InformationProgram, boundary: int) -> None:
        self.program = program
        self.boundary = int(boundary)

    def active_at(self, tick: int) -> list[InformationMessage]:
        step = tick + 1
        return [message for message in self.program.messages if message.active_at(step)]


class _InterventionState:
    """Compiled branch interventions resolved per quarter (tick -> ordinal)."""

    def __init__(self, interventions: list[CompiledIntervention], start_ordinal: int) -> None:
        self.interventions = interventions
        self._start_ordinal = int(start_ordinal)

    def _ordinal(self, tick: int) -> int:
        return self._start_ordinal + int(tick)

    def active_messages(self, tick: int) -> list[InformationMessage]:
        messages: list[InformationMessage] = []
        step = tick + 1
        for item in self.interventions:
            if item.message is None:
                continue
            if item.message.at_step <= step < item.message.at_step + item.message.ttl:
                messages.append(item.message)
        return messages

    def coalition_override(self, tick: int) -> np.ndarray | None:
        ordinal = self._ordinal(tick)
        for item in self.interventions:
            if item.spec.target == "coalition_weights" and item.one_shot(ordinal):
                assert isinstance(item.spec.value, list)
                return np.asarray(item.spec.value, dtype=np.float64)
        return None

    def capability_override(self, tick: int) -> float | None:
        ordinal = self._ordinal(tick)
        for item in self.interventions:
            if item.spec.target == "technology.capability" and item.one_shot(ordinal):
                assert not isinstance(item.spec.value, list)
                return float(item.spec.value)
        return None

    def objective_override(self, tick: int) -> np.ndarray | None:
        ordinal = self._ordinal(tick)
        for item in self.interventions:
            if item.spec.target == "broker.objective_weights" and item.active(ordinal):
                assert isinstance(item.spec.value, list)
                return np.asarray(item.spec.value, dtype=np.float64)
        return None

    def soviet_multiplier(self, tick: int) -> float | None:
        ordinal = self._ordinal(tick)
        for item in self.interventions:
            if item.spec.target == "soviet_constraint_multiplier" and item.active(ordinal):
                assert not isinstance(item.spec.value, list)
                return float(item.spec.value)
        return None

    def policy_patches(self, tick: int) -> dict[str, float]:
        ordinal = self._ordinal(tick)
        patches: dict[str, float] = {}
        for item in self.interventions:
            if not item.spec.target.startswith("policy."):
                continue
            if not item.active(ordinal):
                continue
            coordinate = item.spec.target[len("policy.") :]
            assert not isinstance(item.spec.value, list)
            patches[coordinate] = float(item.spec.value)
        return patches


def _remaining_ttl(cf_state: _InterventionState, tick: int) -> np.ndarray:
    """Remaining TTL (in quarters) of every branch broadcast at this tick."""
    out = np.zeros(len(cf_state.interventions), dtype=np.int64)
    step = int(tick) + 1
    for index, item in enumerate(cf_state.interventions):
        message = item.message
        if message is None:
            continue
        if message.at_step <= step < message.at_step + message.ttl:
            out[index] = message.at_step + message.ttl - step
    return out


def _classification_and_multiplier(
    sensitivity: float, policy: PolicyVector, parameters: Any
) -> tuple[str, float]:
    classification = classify_content(
        sensitivity, float(policy.supported_boundary), float(policy.tolerance_boundary)
    )
    multiplier = visibility_multiplier(classification, parameters.culture)
    return classification, multiplier


_GOVERNMENT_CHANNELS = frozenset({"regime_threat", "repression_cost"})
_UNFILTERED_CHANNELS = frozenset({"public_action_risk", "regime_threat", "repression_cost"})


def _deliver_message(
    message: InformationMessage,
    *,
    policy: PolicyVector,
    parameters: Any,
    region_ids: list[str],
    county_signals: np.ndarray,
    rows: list[dict[str, Any]],
    tick: int,
    quarter: str,
    source_id: str,
    attribution: str,
) -> float:
    """Deliver one message; return its all-audience government contribution."""
    classification, multiplier = _classification_and_multiplier(
        message.content_sensitivity, policy, parameters
    )
    channel_index = SIGNAL_CHANNELS.index(message.channel)
    effective = float(message.intensity)
    if message.channel not in _UNFILTERED_CHANNELS:
        effective *= multiplier
    if message.display_only:
        effective = 0.0
    government_contribution = 0.0
    targets = (
        list(range(len(region_ids)))
        if message.audience_all
        else [region_ids.index(region) for region in message.region_ids if region in region_ids]
    )
    for region_index in targets:
        county_signals[region_index, channel_index] += effective
        rows.append(
            political_event_row(
                tick=tick,
                quarter=quarter,
                event_id=message.message_id.split(":")[0],
                channel=message.channel,
                message_id=message.message_id,
                recipient_id=region_ids[region_index],
                source_id=source_id,
                delivery="delivered" if effective != 0.0 else "blocked",
                classification=classification,
                attribution=attribution,
            )
        )
    if message.audience_all and message.channel in _GOVERNMENT_CHANNELS:
        government_contribution = effective
    return government_contribution


def _deliver_broadcasts(
    *,
    tick: int,
    quarter: Quarter,
    runtime: PoliticalRuntime,
    political: PoliticalState,
    state: MaterialState,
    network: Any,
    program_state: _ProgramState,
    cf_state: _InterventionState,
    region_count: int,
    hh_region: np.ndarray,
) -> tuple[list[dict[str, Any]], np.ndarray, float]:
    policy = PolicyVector.from_vector(np.asarray(political.policy, dtype=np.float64))
    parameters = runtime.politics.parameters
    region_ids = list(runtime.spec.region_ids)
    county_signals = np.zeros((region_count, len(SIGNAL_CHANNELS)), dtype=np.float64)
    rows: list[dict[str, Any]] = []
    for message in program_state.active_at(tick):
        _deliver_message(
            message,
            policy=policy,
            parameters=parameters,
            region_ids=region_ids,
            county_signals=county_signals,
            rows=rows,
            tick=tick,
            quarter=str(quarter),
            source_id="p04_information_program",
            attribution="historical_event",
        )
    cf_government = 0.0
    for message in cf_state.active_messages(tick):
        cf_government += _deliver_message(
            message,
            policy=policy,
            parameters=parameters,
            region_ids=region_ids,
            county_signals=county_signals,
            rows=rows,
            tick=tick,
            quarter=str(quarter),
            source_id="p04_counterfactual_program",
            attribution="counterfactual_intervention",
        )
    return rows, county_signals, cf_government


def _advance_signals(
    previous: np.ndarray,
    runtime: PoliticalRuntime,
    tick: int,
    county_signals: np.ndarray,
    region_count: int,
) -> np.ndarray:
    parameters = runtime.politics.parameters.external_recipe
    quarter = Quarter.parse(str(runtime.forcing.quarters[tick]))
    increments = np.zeros(len(SIGNAL_CHANNELS), dtype=np.float64)
    for event in runtime.events.events:
        if not event.active(quarter):
            continue
        for channel in event.signal_channels:
            increments[SIGNAL_CHANNELS.index(channel)] += float(parameters.default_loading)
    signals = float(parameters.signal_persistence) * previous + increments
    return np.clip(signals, float(parameters.signal_lower), float(parameters.signal_upper))


def _government_signals(
    signals: np.ndarray, external: ExternalWorldSlice, cf_government: float
) -> dict[str, float]:
    tension = float(external.get("geopolitical_tension", 0.0))
    regime_threat = float(
        np.clip(
            signals[SIGNAL_CHANNELS.index("regime_threat")] + 0.5 * tension + cf_government,
            0.0,
            1.0,
        )
    )
    repression_cost = float(
        np.clip(signals[SIGNAL_CHANNELS.index("repression_cost")] + cf_government, 0.0, 1.0)
    )
    return {"regime_threat": regime_threat, "repression_cost": repression_cost}


def _decision_step(
    *,
    runtime: PoliticalRuntime,
    political: PoliticalState,
    signals: np.ndarray,
    external: ExternalWorldSlice,
    tick: int,
    quarter: Quarter,
    cf_state: _InterventionState,
    government: dict[str, float],
    county_signals: np.ndarray,
    soviet_constraint: float,
) -> tuple[PolicyVector, CoalitionTransition | None, PolicyDecision | None]:
    parameters = runtime.politics.parameters
    capability = float(political.information_capability[0])
    override = cf_state.capability_override(tick)
    if override is not None:
        capability = float(override)
    information = information_state(capability, parameters.information)

    published, valid, source = _select_published(political, tick, information.total_lag)
    feedback = _feedback(
        runtime=runtime,
        political=political,
        published=published,
        valid=valid,
        external=external,
        tick=tick,
        soviet_constraint=soviet_constraint,
        cohesion=float(political.elite_cohesion[0]),
        capability=capability,
    )
    weights = np.asarray(political.coalition_weights, dtype=np.float64)
    override_weights = cf_state.coalition_override(tick)
    if override_weights is not None:
        weights = override_weights
    transition = update_coalitions(weights, feedback, external, parameters.coalition)

    signals_pack = PoliticalSignals(
        government=dict(government),
        county=np.asarray(county_signals, dtype=np.float64),
        delivered={},
    )
    previous_policy = PolicyVector.from_vector(np.asarray(political.policy, dtype=np.float64))
    broker_parameters = parameters.broker
    objective_override = cf_state.objective_override(tick)
    if objective_override is not None:
        broker_parameters = broker_parameters.model_copy(
            update={"q": [float(value) for value in objective_override]}
        )
    decision: PolicyDecision | None = None
    if runtime.base_mode is PoliticalMode.ENDOGENOUS_POLITICS:
        decision = choose_policy(
            transition.new_weights,
            previous_policy,
            feedback,
            external,
            information,
            broker_parameters,
            signals=signals_pack,
        )
        policy = PolicyVector.from_vector(decision.selected_policy)
    else:
        policy = _replay_policy(runtime, tick, previous_policy)

    patches = cf_state.policy_patches(tick)
    if patches:
        policy = policy.patch(patches)
    if runtime.base_mode is PoliticalMode.HISTORICAL_REPLAY:
        # Mode A (and A-based branches) keep the declared replay policy; the
        # Soviet feasible set is diagnostic only (recorded as a violation).
        if decision is None:
            decision = PolicyDecision(
                candidate_ids=[],
                candidate_utilities=np.zeros(0, dtype=np.float64),
                candidate_policies=np.zeros((0, U), dtype=np.float64),
                selected_index=-1,
                selected_policy=policy.to_vector(),
                binding_constraints=[],
                source="replay",
                elite_cohesion=float(political.elite_cohesion[0]),
            )
    else:
        policy = _project_soviet(policy, soviet_constraint, broker_parameters)
    _update_policy_error(
        runtime=runtime,
        political=political,
        previous_policy=previous_policy,
        objective=feedback.objective_vector,
        tick=tick,
    )
    return policy, transition, decision


def _replay_policy(runtime: PoliticalRuntime, tick: int, previous: PolicyVector) -> PolicyVector:
    if runtime.schedule is None:
        return previous
    return PolicyVector.model_validate(
        {name: float(runtime.schedule[name][tick]) for name in POLICY_COORDINATES}
    )


def _project_soviet(
    policy: PolicyVector, constraint: float, parameters: BrokerParameters
) -> PolicyVector:
    cap = 1.0 - float(np.clip(constraint, 0.0, 1.0)) * (1.0 - float(parameters.soviet_floor))
    updated = policy.model_dump()
    if updated["enterprise_autonomy"] > cap:
        updated["enterprise_autonomy"] = cap
    if updated["cultural_openness"] > cap:
        updated["cultural_openness"] = cap
    return PolicyVector.model_validate(updated)


def _select_published(
    political: PoliticalState, tick: int, total_lag: int
) -> tuple[np.ndarray, np.ndarray, int]:
    cursor = int(political.publication_cursor[0])
    source = max(tick - 1 - int(total_lag), cursor)
    if source < 0:
        return _initial_published(), np.zeros(F, dtype=bool), -1
    slot = source % POLITICAL_RING_LENGTH
    if int(political.state_report_quarters[slot]) == source and int(
        political.state_report_valid[slot]
    ):
        political.publication_cursor = np.array([source], dtype=np.int64)
        return (
            np.asarray(political.state_published[slot], dtype=np.float64).copy(),
            np.asarray(political.state_valid[slot], dtype=np.float64).astype(bool),
            source,
        )
    # No new valid published source: keep the previous published view.
    return (
        np.asarray(political.state_published[slot], dtype=np.float64).copy(),
        np.asarray(political.state_valid[slot], dtype=np.float64).astype(bool),
        source,
    )


def _central_target(
    *, political: PoliticalState, network: Any, plan_utilization: float, tick: int
) -> np.ndarray:
    activity_count = int(np.asarray(network.activity_kind).shape[0])
    season = np.ones(activity_count, dtype=np.float64)
    farm_rows = np.asarray(network.activity_kind) == 0
    season[~farm_rows] = 1.0
    forecast = np.asarray(political.planner_capacity_forecast, dtype=np.float64)
    estimate = np.asarray(political.planner_inventory_estimate, dtype=np.float64)
    activity_org = np.asarray(network.activity_org_index, dtype=np.int64)
    indptr = np.asarray(network.B.indptr)
    b_rows = np.repeat(np.arange(indptr.size - 1), np.diff(indptr))
    b_cells = np.asarray(network.B.indices, dtype=np.int64)
    b_coeff = np.asarray(network.B.data, dtype=np.float64)
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cover = np.zeros(activity_count, dtype=np.float64)
    if b_rows.size:
        org_owner = np.where(cell_owner_kind[b_cells] == 0, cell_owner_id[b_cells], -1)
        safe_org = np.maximum(org_owner, 0)
        commodity = cell_commodity[b_cells]
        inventory = estimate[safe_org, commodity]
        ratio = inventory / np.maximum(b_coeff, 1e-12)
        ratio = np.where(org_owner >= 0, ratio, 0.0)
        np.maximum.at(cover, b_rows, ratio)
    central = np.zeros(activity_count, dtype=np.float64)
    for activity in range(activity_count):
        if int(activity_org[activity]) < 0:
            central[activity] = 0.0
            continue
        base = plan_utilization * forecast[int(activity_org[activity])] * season[activity]
        central[activity] = max(base - cover[activity], 0.0) * season[activity]
    return central


def _closing_truth(
    *,
    state: MaterialState,
    political: PoliticalState,
    flows: Any,
    external: ExternalWorldSlice,
    index: Any,
    cell_commodity: np.ndarray,
    g_count: int,
    debt_reference: float,
    capability: float,
    tick: int,
    soviet_constraint: float,
) -> TruthSnapshot:
    # Gross material output index: total realized physical activity (a quantity
    # index, never GDP and never an admin-price-weighted value).
    output_value = float(np.sum(np.asarray(flows.activity_realized, dtype=np.float64)))
    last_output = float(political.last_output_value[0])
    growth = 0.0 if last_output <= 0.0 else float(output_value / last_output - 1.0)
    growth_undefined = last_output <= 0.0

    weight = np.asarray(state.household_weight, dtype=np.float64)
    affordable = np.asarray(flows.household_affordable, dtype=np.float64)
    unmet = np.asarray(flows.household_availability_unmet, dtype=np.float64)
    denominator = float(np.sum(weight[:, None] * affordable))
    numerator = float(np.sum(weight[:, None] * np.minimum(unmet, affordable)))
    if denominator <= 0.0:
        shortage = 0.0
        shortage_undefined = True
    else:
        shortage = float(np.clip(numerator / denominator, 0.0, 1.0))
        shortage_undefined = False

    debt_pressure = float(np.clip(float(state.usd_principal) / max(debt_reference, 1e-9), 0.0, 1.0))
    action = np.asarray(political.household_action, dtype=np.float64)
    sector = np.asarray(state.household_sector, dtype=np.int64)
    industry_mask = sector == 0
    numerator_unrest = float(np.sum(weight[industry_mask] * action[industry_mask]))
    denominator_unrest = float(np.sum(weight[industry_mask]))
    worker_unrest = (
        0.0
        if denominator_unrest <= 0.0
        else float(np.clip(numerator_unrest / denominator_unrest, 0.0, 1.0))
    )
    gap = np.asarray(flows.entitlement_gap, dtype=np.float64)
    positive_gap = np.maximum(gap, 0.0).mean(axis=1)
    contract_gap = float(
        np.clip(np.sum(weight * positive_gap) / max(float(weight.sum()), 1e-12), 0.0, 1.0)
    )

    features = np.zeros(F, dtype=np.float64)
    features[_GROWTH] = float(np.clip(growth, -1.0, 1.0))
    features[_SHORTAGE] = shortage
    features[_DEBT] = debt_pressure
    features[_UNREST] = worker_unrest
    features[_CONTRACT_GAP] = contract_gap
    features[_SOVIET] = float(np.clip(soviet_constraint, 0.0, 1.0))
    features[_EXTERNAL_PRESSURE] = _external_pressure_from_slice(external)
    features[_POLICY_ERROR] = float(np.clip(political.policy_error[0], 0.0, 1.0))
    features[_COHESION] = float(np.clip(political.elite_cohesion[0], 0.0, 1.0))
    features[_TECHNOLOGY] = float(np.clip(capability, 0.0, 1.0))
    political.last_output_value = np.array([output_value], dtype=np.float64)
    return TruthSnapshot(
        features=features,
        output_value=output_value,
        shortage_denominator_zero=shortage_undefined,
        growth_base_zero=growth_undefined,
    )


def _external_pressure_from_slice(external: ExternalWorldSlice) -> float:
    return float(np.clip(external.values.get("geopolitical_tension", 0.0), 0.0, 1.0))


def _enterprise_views(
    *, state: MaterialState, network: Any, flows: Any, org_count: int, g_count: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    cell_pool = np.asarray(network.cell_pool, dtype=np.int64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    stock = np.asarray(state.stock_value, dtype=np.float64)
    output_mask = (cell_owner_kind == 0) & (cell_pool == 1)
    inventory = np.zeros((org_count, g_count), dtype=np.float64)
    if output_mask.any():
        np.add.at(
            inventory,
            (cell_owner_id[output_mask], cell_commodity[output_mask]),
            stock[output_mask],
        )
    k_count = int(np.asarray(network.input_cell).shape[0])
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    desired = np.asarray(flows.desired, dtype=np.float64)
    need = np.zeros((org_count, g_count), dtype=np.float64)
    valid = demand_cell[:k_count] >= 0
    buyer = np.asarray(network.activity_org_index, dtype=np.int64)[
        np.asarray(network.input_activity, dtype=np.int64)
    ]
    for index in range(k_count):
        if not valid[index] or buyer[index] < 0:
            continue
        need[buyer[index], cell_commodity[demand_cell[index]]] += float(desired[index])
    capacity = np.asarray(state.organization_capacity, dtype=np.float64).copy()
    return need, inventory, capacity


def _commit_report_ring(
    *,
    political: PoliticalState,
    runtime: PoliticalRuntime,
    state: MaterialState,
    network: Any,
    flows: Any,
    truth: TruthSnapshot,
    info_state: InformationState,
    tick: int,
    quarter: Quarter,
    rng: RngRegistry,
    stochastic: bool,
    index: Any,
    cell_commodity: np.ndarray,
    org_count: int,
    g_count: int,
) -> None:
    parameters = runtime.politics.parameters
    need, inventory, capacity = _enterprise_views(
        state=state, network=network, flows=flows, org_count=org_count, g_count=g_count
    )
    reports = form_enterprise_reports(
        need,
        inventory,
        capacity,
        overstatement=float(parameters.observation.initial_overstatement),
        concealment=float(parameters.observation.initial_concealment),
        misstatement=float(parameters.observation.initial_misstatement),
    )
    observation = observe_state(
        truth,
        reports,
        info_state,
        rng,
        parameters.observation,
        quarter=str(quarter),
        measurement_quarter=tick,
        published_quarter=tick,
        stochastic=stochastic,
    )
    slot = tick % POLITICAL_RING_LENGTH
    political.state_truth[slot] = observation.raw_truth
    political.state_noise[slot] = observation.measurement_noise
    political.state_bias[slot] = observation.strategic_bias
    political.state_reported[slot] = observation.reported
    political.state_published[slot] = observation.published
    political.state_clip_delta[slot] = observation.clipping_delta
    political.state_valid[slot] = observation.valid.astype(np.int64)
    political.state_report_quarters[slot] = tick
    political.state_report_valid[slot] = 1
    political.enterprise_inventory_history[slot] = reports.reported_inventory
    political.enterprise_need_history[slot] = reports.reported_need
    political.enterprise_capacity_history[slot] = reports.reported_capacity
    capability = float(info_state.capability)
    political.planner_inventory_estimate = capability * reports.reported_inventory + (
        1.0 - capability
    ) * np.asarray(political.planner_inventory_estimate, dtype=np.float64)
    political.planner_capacity_forecast = capability * reports.reported_capacity + (
        1.0 - capability
    ) * np.asarray(political.planner_capacity_forecast, dtype=np.float64)


def _update_cohesion(
    *, political: PoliticalState, parameters: BrokerParameters, policy: PolicyVector
) -> float:
    from hsm_lab.contract.politics import normalize_policy_vector

    normalized = normalize_policy_vector(policy.to_vector())
    ideals = normalize_policy_vector(np.asarray(parameters.ideals, dtype=np.float64))
    weights = np.asarray(political.coalition_weights, dtype=np.float64)
    distances = np.mean((normalized[None, :] - ideals) ** 2, axis=1)
    achieved = 1.0 - float(np.sum(weights * distances))
    alpha = float(parameters.cohesion_alpha)
    old = float(political.elite_cohesion[0])
    return float(np.clip((1.0 - alpha) * old + alpha * achieved, 0.0, 1.0))


def _append_political_rows(
    *,
    history: MaterialHistory,
    runtime: PoliticalRuntime,
    political: PoliticalState,
    state: MaterialState,
    flows: Any,
    decision: PolicyDecision | None,
    coalition_transition: CoalitionTransition | None,
    county_signals: np.ndarray,
    external: ExternalWorldSlice,
    tick: int,
    quarter: Quarter,
    deliverables: list[dict[str, Any]],
    region_ids: list[str],
    governance: dict[str, float],
    info_state: InformationState,
    soviet_constraint: float,
) -> None:
    parameters = runtime.politics.parameters
    base_mode = runtime.base_mode
    policy = PolicyVector.from_vector(np.asarray(political.policy, dtype=np.float64))
    constr = float(np.clip(soviet_constraint, 0.0, 1.0))
    cap = 1.0 - constr * (1.0 - float(parameters.broker.soviet_floor))
    if base_mode is PoliticalMode.HISTORICAL_REPLAY:
        violation = max(
            0.0, float(policy.enterprise_autonomy) - cap, float(policy.cultural_openness) - cap
        )
        soviet_bound = False
    else:
        violation = 0.0
        soviet_bound = bool(
            float(policy.enterprise_autonomy) >= cap - 1e-12
            or float(policy.cultural_openness) >= cap - 1e-12
        )
    source = "replay" if base_mode is PoliticalMode.HISTORICAL_REPLAY else "broker"
    selected = "replay"
    if decision is not None and decision.candidate_ids:
        selected = decision.candidate_ids[decision.selected_index]
    history.political_quarter_rows.append(
        political_quarter_row(
            tick=tick,
            quarter=str(quarter),
            mode=str(runtime.logical_mode if runtime.logical_mode is not None else base_mode),
            policy_source=source,
            coalition_weights=np.asarray(political.coalition_weights, dtype=np.float64),
            policy=policy.to_vector(),
            elite_cohesion=float(political.elite_cohesion[0]),
            soviet_bound=soviet_bound,
            soviet_violation=violation,
            selected_candidate=selected,
            information_capability=float(info_state.capability),
            coalition_contributions=(
                None
                if coalition_transition is None
                else np.asarray(coalition_transition.contributions, dtype=np.float64)
            ),
        )
    )
    weight = np.asarray(state.household_weight, dtype=np.float64)
    region = np.asarray(state.household_region, dtype=np.int64)
    opposition = np.asarray(political.opposition, dtype=np.float64)
    capacity = _region_capacity(opposition)
    grievance = np.asarray(state.household_grievance, dtype=np.float64)
    action = np.asarray(political.household_action, dtype=np.float64)
    exposure = np.asarray(political.household_exposure, dtype=np.float64)
    risk = np.clip(
        float(policy.repression)
        + np.asarray(
            county_signals[:, SIGNAL_CHANNELS.index("public_action_risk")], dtype=np.float64
        ),
        0.0,
        1.0,
    )
    for region_index, region_id in enumerate(region_ids):
        mask = region == region_index
        total = float(weight[mask].sum())
        denominator = total if total > 0.0 else 1.0
        history.opposition_rows.append(
            opposition_row(
                tick=tick,
                quarter=str(quarter),
                region_id=region_id,
                opposition=opposition[region_index],
                capacity=float(capacity[region_index]),
                weighted_grievance=float(np.sum(weight[mask] * grievance[mask]) / denominator),
                weighted_voice=float(np.sum(weight[mask] * action[mask]) / denominator),
                weighted_risk=float(risk[region_index]),
                weighted_exposure=float(np.sum(weight[mask] * exposure[mask]) / denominator),
            )
        )
    slot = tick % POLITICAL_RING_LENGTH
    for row in information_rows(
        tick=tick,
        quarter=str(quarter),
        capability=float(info_state.capability),
        dimensions=np.asarray(political.information_dimensions, dtype=np.float64),
        total_lag=int(info_state.total_lag),
        source_quarter=int(political.publication_cursor[0]),
        truth=np.asarray(political.state_truth[slot], dtype=np.float64),
        noise=np.asarray(political.state_noise[slot], dtype=np.float64),
        bias=np.asarray(political.state_bias[slot], dtype=np.float64),
        published=np.asarray(political.state_published[slot], dtype=np.float64),
        valid=np.asarray(political.state_valid[slot], dtype=np.float64).astype(bool),
    ):
        history.information_rows.append(row)
    if decision is not None and decision.candidate_ids:
        for row in policy_decision_rows(
            tick=tick,
            quarter=str(quarter),
            candidate_ids=decision.candidate_ids,
            utilities=np.asarray(decision.candidate_utilities, dtype=np.float64),
            terms=(
                None
                if decision.candidate_terms is None
                else np.asarray(decision.candidate_terms, dtype=np.float64)
            ),
            binding_per_candidate=decision.candidate_binding,
        ):
            history.policy_decision_rows.append(row)
    for row in deliverables:
        history.political_event_rows.append(row)


def _build_summary(
    *,
    runtime: PoliticalRuntime,
    run_id: str,
    spec: ScenarioSpec,
    state: MaterialState,
    political: PoliticalState,
    history: MaterialHistory,
    frames: dict[str, Any],
    rng: RngRegistry,
    parameter_hash: str,
    initial_recipe_hash: str,
    checkpoint_paths: list[str],
    tallies: dict[str, Any],
    logical_mode: PoliticalMode,
    performance: dict[str, Any],
) -> dict[str, Any]:
    boundary = state.completed_ticks
    draws_by_module = rng.draws_by_module()
    return {
        "schema_version": "1",
        "run_id": run_id,
        "run_kind": POLITICAL_RUN_KIND,
        "engine_version": POLITICAL_ENGINE_VERSION_FULL,
        "political_mode": str(logical_mode),
        "scenario_id": spec.scenario_id,
        "study_id": runtime.politics.study_id,
        "start": str(spec.start),
        "end": str(spec.start.advance(spec.ticks - 1)),
        "planned_ticks": spec.ticks,
        "completed_ticks": boundary,
        "last_completed_quarter": str(spec.start.advance(boundary - 1)) if boundary else None,
        "horizon_reached": boundary == spec.ticks,
        "households": spec.households,
        "organizations": spec.organizations,
        "region_ids": list(spec.region_ids),
        "commodity_ids": list(spec.commodities),
        "seed": spec.seed,
        "output_policy": spec.output_policy.value,
        "parameter_hash": parameter_hash,
        "initial_recipe_hash": initial_recipe_hash,
        "external_pack_hash": runtime.pack.pack_hash,
        "information_program_hash": runtime.program.program_hash,
        "event_ids": [event.event_id for event in runtime.events.events],
        "deterministic_replay_digest": history.digest_chain,
        "political_state_hash": canonical_political_hash(political),
        "rng_draws_count": rng.draws_count(),
        "rng_draws_by_module": draws_by_module,
        "stochastic_modules_active": [
            module for module, count in draws_by_module.items() if count > 0
        ],
        "row_counts": {name: frame.height for name, frame in frames.items()},
        "coalition_weights_close": [
            float(value) for value in np.asarray(political.coalition_weights, dtype=np.float64)
        ],
        "information_capability_close": float(political.information_capability[0]),
        "policy_close": {
            name: float(value)
            for name, value in zip(
                POLICY_COORDINATES, np.asarray(political.policy, dtype=np.float64), strict=True
            )
        },
        "invariants": {
            "max_material_abs_residual": tallies["max_material_abs_residual"],
            "max_material_tolerance_ratio": tallies["max_material_tolerance_ratio"],
            "checked_ticks": boundary,
        },
        "soviet_violations": tallies,
        "checkpoint_paths": checkpoint_paths,
        "performance": performance,
        "research_warnings": list(runtime.contract.research_warnings)
        + [POLITICAL_RESEARCH_WARNING],
        "mechanism_note": (
            "P04 political/external/information quantities are structural engineering "
            "fixtures; the run is not a historical fit and carries no historical "
            "probability claim. Higher information capability changes information "
            "channels only, never physical productivity."
        ),
    }
