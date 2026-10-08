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


# ---------------------------------------------------------------------------
# Session: stepwise admission (drivable by the native loop or SocioVerse2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionOutcome:
    """A computed-but-uncommitted quarter decision (no state was written)."""

    policy: PolicyVector
    transition: CoalitionTransition
    decision: PolicyDecision
    prediction: np.ndarray
    objective: np.ndarray
    policy_error: float
    capability: float
    information: InformationState
    weights_before: np.ndarray
    policy_source: str
    soviet_bound: bool
    soviet_violation: float
    publication_source: int


@dataclass(frozen=True)
class QuarterPrep:
    """The exogenous part of one quarter (external slice, events, broadcasts)."""

    tick: int
    quarter: Quarter
    external: ExternalWorldSlice
    delivery_rows: list[dict[str, Any]]
    county_signals: np.ndarray
    government: dict[str, float]
    signals: np.ndarray
    soviet_constraint: float
    multiplier: float
    ttl: np.ndarray
    cf_government: float


class PoliticalSession:
    """One admitted quarter at a time; the single owner of P04 admission.

    ``open()`` performs preflight, restore/fork and initialization exactly once;
    ``admit_quarter()`` advances exactly one quarter (external slice → signals →
    decision → material kernel → culture/opposition/observation → gates → tables
    → checkpoint); ``finish()`` writes the tables, summary and manifest.  The
    native runner and the SocioVerse2 orchestration both drive this object, so
    there is exactly one admission path.
    """

    def __init__(
        self,
        runtime: PoliticalRuntime,
        output_dir: Path,
        registry: Any,
        until: Quarter | str | None,
        checkpoint_every: int,
        resume_from: Path | None,
        fork_from: ForkOrigin | None,
    ) -> None:
        self.runtime = runtime
        self.output_dir = Path(output_dir)
        self.registry = registry
        self.until = until
        self.checkpoint_every = int(checkpoint_every)
        self.resume_from = resume_from
        self.fork_from = fork_from

        self.spec = runtime.spec
        self.contract = runtime.contract
        self.politics = runtime.politics
        self.pack = runtime.pack
        self.forcing = runtime.forcing
        self.logical_mode: PoliticalMode = runtime.base_mode
        self.opened = False
        self.finished = False
        if self.checkpoint_every < 0:
            raise ConfigError("checkpoint_every must be non-negative")

    # -- lifecycle ---------------------------------------------------------
    def open(self) -> PoliticalSession:
        from hsm_lab.contract.guards import BASELINE_FILENAME, verify_baseline
        from hsm_lab.storage.checkpoint import load_material_checkpoint

        spec = self.spec
        registry = self.registry
        root = registry.root
        if self.output_dir.exists() or self.output_dir.is_symlink():
            raise ResearchGateError(
                f"output directory {self.output_dir} already exists; refusing to "
                "overwrite any previous run"
            )
        self.baseline_hash = verify_baseline(root / BASELINE_FILENAME, self.contract)
        self.lock_hash = compute_lock_hash(root)
        self.parameter_vector = {
            **material_parameter_vector(spec),
            **self.politics.parameters.flatten(),
        }
        self.parameter_hash = compute_parameter_hash(self.parameter_vector)
        self.initial_recipe_hash = material_recipe_hash(spec)

        self.until_quarter = (
            None
            if self.until is None
            else (Quarter.parse(self.until) if isinstance(self.until, str) else self.until)
        )

        # --- initial condition draw / restore -----------------------------
        self.parent_run_id: str | None = None
        self.restored_metadata: dict[str, Any] = {}
        self.restore_source = (
            self.resume_from
            if self.resume_from is not None
            else (None if self.fork_from is None else self.fork_from.checkpoint)
        )
        self.network = build_material_network(
            spec, self.contract, build_material_initial_conditions(spec, RngRegistry(spec.seed))
        )
        self.axes = resolve_political_axes(
            households=spec.households,
            regions=len(spec.region_ids),
            organizations=int(spec.organizations or 0),
            commodities=len(spec.commodities),
            interventions=len(self.runtime.interventions),
        )
        if self.restore_source is not None:
            metadata_path = self.restore_source / "metadata.json"
            if not metadata_path.is_file():
                raise ResearchGateError(f"checkpoint metadata not found: {metadata_path}")
            boundary_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
            boundary = int(boundary_meta["completed_ticks"])
            state, history, rng, restored = load_material_checkpoint(
                self.restore_source,
                spec,
                self.contract,
                self.network,
                extra_rng_modules=({MEASUREMENT_MODULE: boundary * F} if spec.stochastic else {}),
            )
            if "political" not in restored:
                raise ResearchGateError(
                    "checkpoint carries no political payload; it was not written by a P04 run"
                )
            political = state_from_political_arrays(
                {name: np.asarray(value) for name, value in restored["political"].items()},
                self.axes,
            )
            if political.intervention_ttl.shape[0] != len(self.runtime.interventions):
                political.intervention_ttl = np.zeros(
                    len(self.runtime.interventions), dtype=np.int64
                )
            self.rng, self.state, self.political, self.history = rng, state, political, history
            self.restored_metadata = restored
            self.resume_boundary = boundary
            self.parent_run_id = str(restored.get("source_run_id") or "")
        else:
            self.rng = RngRegistry(spec.seed)
            initial = build_material_initial_conditions(spec, self.rng)
            self.network = build_material_network(spec, self.contract, initial)
            self.state = initialize_material(spec, initial, self.network)
            self.political = _initial_state(
                spec,
                self.politics,
                self.state,
                self.network,
                self.axes,
                len(self.runtime.interventions),
            )
            self.history = MaterialHistory()
            self.history.digest_chain = _initial_chain(
                spec=spec,
                baseline_hash=self.baseline_hash,
                lock_hash=self.lock_hash,
                parameter_hash=self.parameter_hash,
                initial_recipe_hash=self.initial_recipe_hash,
                input_artifact_hashes=dict(self.forcing.input_artifact_hashes),
                initial_state=self.state,
                political=self.political,
            )
            self.resume_boundary = 0

        # Observation references are the initial report normalization carried in
        # the political state (checkpointed; never updated from future outcomes).
        normalization = np.asarray(self.political.report_normalization, dtype=np.float64)
        parameters = self.politics.parameters
        parameters = parameters.model_copy(
            update={
                "observation": parameters.observation.model_copy(
                    update={
                        "need_reference": float(max(normalization[0], 1e-12)),
                        "inventory_reference": float(max(normalization[1], 1e-12)),
                        "capacity_reference": float(max(normalization[2], 1e-12)),
                    }
                )
            }
        )
        self.politics = self.politics.model_copy(update={"parameters": parameters})
        self.runtime.politics = self.politics

        if self.until_quarter is not None:
            end = spec.start.advance(spec.ticks - 1)
            if not (
                spec.start.advance(self.resume_boundary).to_ordinal()
                <= self.until_quarter.to_ordinal()
                <= end.to_ordinal()
            ):
                raise ConfigError(f"--until {self.until_quarter} lies outside the remaining window")
            self.target_ticks = self.until_quarter.to_ordinal() - spec.start.to_ordinal() + 1
        else:
            self.target_ticks = spec.ticks

        self.logical_mode = (
            PoliticalMode.COUNTERFACTUAL
            if (self.runtime.branch is not None or self.runtime.resuming_counterfactual)
            else self.runtime.base_mode
        )
        self.runtime.logical_mode = self.logical_mode

        self.run_id = uuid4().hex
        running = manifest_preamble(
            run_id=self.run_id,
            spec=spec,
            contract=self.contract,
            root=root,
            baseline_hash=self.baseline_hash,
            run_kind=MATERIAL_RUN_KIND,
            parameter_vector=self.parameter_vector,
            input_artifact_hashes=dict(self.forcing.input_artifact_hashes)
            | dict(pack_hashes(self.pack)),
            initial_recipe_hash=self.initial_recipe_hash,
            engine_version=POLITICAL_ENGINE_VERSION_FULL,
            parent_run_id=self.parent_run_id or None,
            resumed_from_checkpoint=str(self.restore_source) if self.restore_source else None,
        )
        self.manifest = running.model_copy(
            update={"run_kind": POLITICAL_RUN_KIND, "political_mode": self.logical_mode}
        )
        self.output_dir.mkdir(parents=True)
        write_manifest_atomic(self.output_dir, self.manifest)

        self._derive_runtime_indices()
        self.tallies: dict[str, Any] = {
            "max_material_abs_residual": 0.0,
            "max_material_tolerance_ratio": 0.0,
            "max_finance_abs_residual": 0.0,
            "max_finance_tolerance_ratio": 0.0,
            "soviet_violations": 0,
            "delivered_broadcasts": 0,
        }
        self.checkpoint_paths: list[str] = []
        self.saved_boundaries: set[int] = set()
        self.admitted_ticks = int(self.state.completed_ticks)
        self.program_state = _ProgramState(self.runtime.program, self.resume_boundary)
        self.cf_state = _InterventionState(self.runtime.interventions, self.spec.start.to_ordinal())
        self.run_started = time.perf_counter()
        self.last_outcome: DecisionOutcome | None = None
        self.last_quarter: str | None = None
        self.opened = True
        return self

    def _derive_runtime_indices(self) -> None:
        spec = self.spec
        state = self.state
        network = self.network
        self.runtime_network = dataclasses.replace(network)
        self.index = _tick_index(network)
        self.cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
        self.hh_region = np.asarray(state.household_region, dtype=np.int64)
        self.hh_weight = np.asarray(state.household_weight, dtype=np.float64)
        self.region_count = len(spec.region_ids)
        self.org_count = int(state.organization_id.shape[0])
        self.g_count = len(network.commodity_ids)
        education = np.asarray(state.household_education, dtype=np.int64)
        sector = np.asarray(state.household_sector, dtype=np.int64)
        intellectual_density = _county_mean(
            (education == 2).astype(np.float64), self.hh_weight, self.hh_region, self.region_count
        )
        worker_density = _county_mean(
            (sector == 0).astype(np.float64), self.hh_weight, self.hh_region, self.region_count
        )
        self.formation_inputs = np.stack([intellectual_density, worker_density], axis=1)
        self.county_contact = np.asarray(state.household_western_exposure, dtype=np.float64).copy()

    # -- read-only views ---------------------------------------------------
    @property
    def region_ids(self) -> list[str]:
        return list(self.spec.region_ids)

    @property
    def completed_ticks(self) -> int:
        return int(self.state.completed_ticks)

    @property
    def done(self) -> bool:
        return self.completed_ticks >= self.target_ticks

    @property
    def remaining_ticks(self) -> int:
        return max(0, self.target_ticks - self.completed_ticks)

    @property
    def start_tick(self) -> int:
        return int(self.state.completed_ticks) if self.opened else 0

    def quarter_of(self, tick: int) -> str:
        return str(self.spec.start.advance(tick))

    def published_view(self) -> dict[str, float]:
        """Lagged published state the decision layer may legitimately see."""
        lag = _total_lag(self.political, self.politics.parameters)
        published, valid, source = select_published(self.political, self.completed_ticks, lag)
        return {
            "source_tick": float(source),
            **{
                feature: float(published[index]) if bool(valid[index]) else float("nan")
                for index, feature in enumerate(POLITICAL_FEATURE_IDS)
            },
        }

    def audit_state(self) -> dict[str, Any]:
        """Real closing aggregates for panel/metrics only (never for decisions)."""
        return {
            "completed_ticks": self.completed_ticks,
            "quarter": self.quarter_of(self.completed_ticks - 1) if self.completed_ticks else None,
            "logical_mode": str(self.logical_mode),
            "information_capability": float(self.political.information_capability[0]),
            "elite_cohesion": float(self.political.elite_cohesion[0]),
            "coalition_weights": [
                float(value) for value in np.asarray(self.political.coalition_weights)
            ],
            "policy": {
                name: float(value)
                for name, value in zip(
                    POLICY_COORDINATES, np.asarray(self.political.policy), strict=True
                )
            },
            "opposition_capacity": [
                float(value) for value in _region_capacity(np.asarray(self.political.opposition))
            ],
            "max_material_tolerance_ratio": float(self.tallies["max_material_tolerance_ratio"]),
            "max_finance_tolerance_ratio": float(self.tallies["max_finance_tolerance_ratio"]),
        }

    def region_state(self, region_id: str) -> dict[str, Any]:
        index = self.spec.region_ids.index(region_id)
        opposition = np.asarray(self.political.opposition, dtype=np.float64)
        return {
            "region_id": region_id,
            "capacity": float(_region_capacity(opposition)[index]),
            "perceived_efficacy": float(
                opposition[index, OPPOSITION_AXIS_IDS.index("perceived_efficacy")]
            ),
            "repression_exposure": float(
                opposition[index, OPPOSITION_AXIS_IDS.index("repression_exposure")]
            ),
        }

    # -- one quarter -------------------------------------------------------
    def _prepare(self, tick: int) -> QuarterPrep:
        quarter = Quarter.parse(self.quarter_of(tick))
        external = self.pack.slice(tick)
        deliver_rows, county_signals, cf_government = _deliver_broadcasts(
            tick=tick,
            quarter=quarter,
            runtime=self.runtime,
            political=self.political,
            state=self.state,
            network=self.network,
            program_state=self.program_state,
            cf_state=self.cf_state,
            region_count=self.region_count,
            hh_region=self.hh_region,
        )
        signals = _advance_signals(
            np.asarray(self.political.signals, dtype=np.float64),
            self.runtime,
            tick,
            county_signals,
            self.region_count,
        )
        government = _government_signals(signals, external, cf_government)
        multiplier = self.cf_state.soviet_multiplier(tick)
        if multiplier is None:
            multiplier = 1.0
        soviet_constraint = float(
            np.clip(external.get("soviet_constraint", 0.0) * float(multiplier), 0.0, 1.0)
        )
        return QuarterPrep(
            tick=tick,
            quarter=quarter,
            external=external,
            delivery_rows=deliver_rows,
            county_signals=county_signals,
            government=government,
            signals=signals,
            soviet_constraint=soviet_constraint,
            multiplier=float(multiplier),
            ttl=_remaining_ttl(self.cf_state, tick),
            cf_government=float(cf_government),
        )

    def propose_decision(self) -> DecisionOutcome:
        """Compute the next quarter's decision without committing anything."""
        if not self.opened:
            raise ConfigError("session is not open")
        if self.done:
            raise ConfigError("no remaining quarter to decide")
        tick = self.completed_ticks
        prep = self._prepare(tick)
        return _decide(
            runtime=self.runtime,
            political=self.political,
            signals=prep.signals,
            external=prep.external,
            tick=tick,
            quarter=prep.quarter,
            cf_state=self.cf_state,
            government=prep.government,
            county_signals=prep.county_signals,
            soviet_constraint=prep.soviet_constraint,
        )

    def admit_quarter(self, decision: PolicyDecision | None = None) -> dict[str, Any]:
        """Advance exactly one quarter; returns a compact audit record.

        ``decision`` may be supplied by an external orchestration layer (the
        SocioVerse2 decision model); otherwise the session computes it with the
        project's own rule.  Either way this method is the only place that
        commits P04/material state for the quarter.
        """
        if not self.opened:
            raise ConfigError("session is not open")
        if self.done:
            raise ConfigError("scenario already reached its target boundary")
        tick = self.completed_ticks
        prep = self._prepare(tick)
        outcome = _decide(
            runtime=self.runtime,
            political=self.political,
            signals=prep.signals,
            external=prep.external,
            tick=tick,
            quarter=prep.quarter,
            cf_state=self.cf_state,
            government=prep.government,
            county_signals=prep.county_signals,
            soviet_constraint=prep.soviet_constraint,
        )
        if decision is not None:
            outcome = dataclasses.replace(
                outcome,
                decision=decision,
                policy=PolicyVector.from_vector(np.asarray(decision.selected_policy)),
            )
        return self._commit(prep, outcome)

    def _commit(self, prep: QuarterPrep, outcome: DecisionOutcome) -> dict[str, Any]:
        spec = self.spec
        state = self.state
        political = self.political
        parameters = self.politics.parameters
        tick = prep.tick
        quarter = prep.quarter
        opening = capture_material_stocks(state)

        # --- commit the quarter's political transition --------------------
        political.signals = prep.signals
        political.soviet_constraint_multiplier = np.array([prep.multiplier], dtype=np.float64)
        if political.intervention_ttl.shape[0] == prep.ttl.shape[0]:
            political.intervention_ttl = prep.ttl
        political.publication_cursor = np.array(
            [max(int(political.publication_cursor[0]), int(outcome.publication_source))],
            dtype=np.int64,
        )
        political.coalition_weights = outcome.transition.new_weights
        political.policy = outcome.policy.to_vector()
        slot = tick % POLITICAL_RING_LENGTH
        political.prediction_history[slot] = outcome.prediction
        political.objective_history[slot] = outcome.objective
        political.policy_error = np.array([outcome.policy_error], dtype=np.float64)
        self.last_outcome = outcome
        self.last_quarter = str(quarter)

        info_state_before = InformationState(
            capability=outcome.capability,
            dimensions=np.asarray(political.information_dimensions, dtype=np.float64),
            total_lag=_total_lag(political, parameters),
        )
        effective = compile_effective_policy(
            spec.material_parameters,  # type: ignore[arg-type]
            spec.household_parameters,  # type: ignore[arg-type]
            outcome.policy,
            prep.external,
            tuple(self.network.commodity_ids),
        )
        object.__setattr__(
            self.runtime_network, "household_parameters", effective.household_parameters
        )
        object.__setattr__(self.runtime_network, "household_catalog", effective.household_catalog)
        central = _central_target(
            political=political,
            network=self.network,
            plan_utilization=float(outcome.policy.plan_utilization),
            tick=tick,
        )
        controls = TickControls(
            material_parameters=effective.material_parameters,
            household_parameters=effective.household_parameters,
            household_catalog=effective.household_catalog,
            autonomy=float(outcome.policy.enterprise_autonomy),
            central_target=central,
            policy=outcome.policy,
        )

        # --- material kernel (the only producer of realized quantities) ----
        flows = tick_material(
            state,
            self.forcing,
            effective.material_parameters,
            self.runtime_network,
            controls=controls,
        )
        if flows.tick != tick:
            raise ResearchGateError("material tick does not describe the expected quarter")

        # --- closing: culture, opposition, action --------------------------
        household_signals = prep.county_signals[self.hh_region]
        western_visible = household_signals[:, _SIGNAL["western_comparison"]]
        identification, exposure, efficacy = update_household_culture(
            np.asarray(political.household_identification, dtype=np.float64),
            np.asarray(political.household_exposure, dtype=np.float64),
            np.asarray(political.household_efficacy, dtype=np.float64),
            official_signal_visible=float(
                np.mean(prep.county_signals[:, _SIGNAL["official_policy"]])
            ),
            western_signal_visible=western_visible,
            region_exposure_target=np.zeros(self.region_count, dtype=np.float64),
            region_efficacy=np.asarray(
                political.opposition[:, OPPOSITION_AXIS_IDS.index("perceived_efficacy")]
            ),
            household_region=self.hh_region,
            exposure_contact=self.county_contact,
            parameters=parameters.culture,
            openness=float(outcome.policy.cultural_openness),
        )
        political.household_identification = identification
        political.household_exposure = exposure
        political.household_efficacy = efficacy

        opposition = update_region_capacity(
            np.asarray(political.opposition, dtype=np.float64),
            self.formation_inputs,
            outcome.policy,
            prep.county_signals,
            prep.external,
            parameters.opposition,
        )
        political.opposition = opposition
        risk_signal = np.clip(
            np.asarray(prep.county_signals[:, _SIGNAL["public_action_risk"]], dtype=np.float64),
            0.0,
            1.0,
        )
        political.household_action = action_propensity(
            np.asarray(state.household_grievance, dtype=np.float64),
            self.hh_region,
            np.asarray(political.household_exposure, dtype=np.float64),
            np.asarray(political.household_efficacy, dtype=np.float64),
            opposition,
            outcome.policy,
            risk_signal,
            parameters.opposition,
            self.region_count,
        )

        new_info = advance_information_capacity(
            info_state_before, outcome.policy, prep.external, parameters.information
        )
        capability_override = self.cf_state.capability_override(tick)
        if capability_override:
            new_info = information_state(capability_override, parameters.information)
        political.information_capability = np.array([new_info.capability], dtype=np.float64)
        political.information_dimensions = np.asarray(new_info.dimensions, dtype=np.float64)

        truth = _closing_truth(
            state=state,
            political=political,
            flows=flows,
            external=prep.external,
            index=self.index,
            cell_commodity=self.cell_commodity,
            g_count=self.g_count,
            debt_reference=parameters.external_recipe.debt_reference,
            capability=new_info.capability,
            tick=tick,
            soviet_constraint=prep.soviet_constraint,
        )
        _commit_report_ring(
            political=political,
            runtime=self.runtime,
            state=state,
            network=self.network,
            flows=flows,
            truth=truth,
            info_state=new_info,
            tick=tick,
            quarter=quarter,
            rng=self.rng,
            stochastic=spec.stochastic,
            index=self.index,
            cell_commodity=self.cell_commodity,
            org_count=self.org_count,
            g_count=self.g_count,
        )
        political.elite_cohesion = np.array(
            [
                _update_cohesion(
                    political=political,
                    parameters=parameters.broker,
                    policy=outcome.policy,
                )
            ],
            dtype=np.float64,
        )

        # --- gates ---------------------------------------------------------
        invariant_summary = check_material_invariants(
            opening,
            state,
            flows,
            effective.material_parameters,
            self.runtime_network,
            controls=controls,
        )
        residual, tolerance = _material_residuals(opening, state, flows, self.runtime_network)
        flows.material_balance_residual = residual
        flows.material_balance_tolerance = tolerance
        finance_residual, finance_tolerance = finance_balance_residuals(state, flows)
        flows.finance_balance_residual = finance_residual
        flows.finance_balance_tolerance = finance_tolerance
        self.tallies["max_material_abs_residual"] = max(
            self.tallies["max_material_abs_residual"],
            float(invariant_summary.max_material_abs_residual),
        )
        self.tallies["max_material_tolerance_ratio"] = max(
            self.tallies["max_material_tolerance_ratio"],
            float(invariant_summary.max_material_tolerance_ratio),
        )
        self.tallies["max_finance_abs_residual"] = max(
            self.tallies["max_finance_abs_residual"],
            float(invariant_summary.max_finance_abs_residual),
        )
        self.tallies["max_finance_tolerance_ratio"] = max(
            self.tallies["max_finance_tolerance_ratio"],
            float(invariant_summary.max_finance_tolerance_ratio),
        )
        self.tallies["soviet_violations"] += int(outcome.soviet_violation > 0.0)
        self.tallies["delivered_broadcasts"] += sum(
            1 for row in prep.delivery_rows if row["delivery"] == "delivered"
        )

        # --- commit the boundary -------------------------------------------
        state.completed_ticks += 1
        self.history.digest_chain = _advance_chain(
            previous=self.history.digest_chain,
            state=state,
            flows=flows,
            political=political,
            deliveries=prep.delivery_rows,
        )
        self.admitted_ticks = state.completed_ticks
        invariant_dict: dict[str, Any] = {
            "max_material_abs_residual": float(invariant_summary.max_material_abs_residual),
            "max_material_tolerance_ratio": float(invariant_summary.max_material_tolerance_ratio),
            "max_finance_abs_residual": float(invariant_summary.max_finance_abs_residual),
            "max_finance_tolerance_ratio": float(invariant_summary.max_finance_tolerance_ratio),
            "checked_cells": int(invariant_summary.checked_cells),
            "per_ledger": dict(invariant_summary.per_ledger),
            "forcing_segment": str(self.forcing.segment[tick]),
            "treasury_deposit_open": float(opening.treasury_deposit),
            "bank_reserves_open": [float(v) for v in opening.bank_reserves],
            "housing_completed": float(
                np.sum(np.asarray(state.dwelling_stock) - opening.dwelling_stock)
            ),
            "material_balance_residual": [float(v) for v in residual],
            "material_balance_tolerance": [float(v) for v in tolerance],
        }
        append_material_rows(
            self.history,
            state,
            flows,
            effective.material_parameters,
            self.runtime_network,
            region_ids=list(spec.region_ids),
            commodity_ids=list(spec.commodities),
            digest=self.history.digest_chain,
            invariant_summary=invariant_dict,
            opening_stock=opening.stock_value,
        )
        _append_political_rows(
            history=self.history,
            runtime=self.runtime,
            political=political,
            state=state,
            flows=flows,
            decision=outcome.decision,
            coalition_transition=outcome.transition,
            county_signals=prep.county_signals,
            external=prep.external,
            tick=tick,
            quarter=quarter,
            deliverables=prep.delivery_rows,
            region_ids=list(spec.region_ids),
            governance=prep.government,
            info_state=new_info,
            soviet_constraint=prep.soviet_constraint,
        )
        self._maybe_checkpoint(state.completed_ticks)
        return {
            "tick": tick,
            "quarter": str(quarter),
            "policy_source": outcome.policy_source,
            "coalition_weights": [float(v) for v in outcome.transition.new_weights],
            "policy": [float(v) for v in outcome.policy.to_vector()],
            "information_capability": float(new_info.capability),
            "delivered_broadcasts": sum(
                1 for row in prep.delivery_rows if row["delivery"] == "delivered"
            ),
        }

    def _maybe_checkpoint(self, boundary: int) -> None:
        from hsm_lab.storage.checkpoint import checkpoint_dir, save_material_checkpoint

        paused_here = boundary == self.target_ticks and self.target_ticks < self.spec.ticks
        due = (
            (self.checkpoint_every > 0 and boundary % self.checkpoint_every == 0)
            or paused_here
            or (self.checkpoint_every > 0 and boundary == self.spec.ticks)
        )
        if not due or boundary in self.saved_boundaries:
            return
        path = save_material_checkpoint(
            checkpoint_dir(self.output_dir, boundary),
            self.state,
            self.network,
            self.history,
            self.rng,
            {
                "scenario": self.spec.model_dump(mode="json"),
                "scenario_hash": compute_scenario_hash(self.spec),
                "baseline_hash": self.baseline_hash,
                "lock_hash": self.lock_hash,
                "parameter_hash": self.parameter_hash,
                "initial_recipe_hash": self.initial_recipe_hash,
                "engine_version": POLITICAL_ENGINE_VERSION_FULL,
                "state_version": MATERIAL_STATE_VERSION,
                "political_state_version": POLITICAL_STATE_VERSION,
                "political_mode": str(self.logical_mode),
                "input_artifact_hashes": dict(self.forcing.input_artifact_hashes),
                "region_ids": list(self.spec.region_ids),
                "commodity_ids": list(self.spec.commodities),
                "last_completed_quarter": str(self.spec.start.advance(boundary - 1)),
                "next_quarter": str(self.spec.start.advance(boundary)),
                "source_run_id": self.run_id,
                "branch": None
                if self.runtime.branch is None
                else self.runtime.branch.model_dump(mode="json"),
            },
            political_arrays=political_arrays(self.political, self.axes),
        )
        self.saved_boundaries.add(boundary)
        self.checkpoint_paths.append(str(path.relative_to(self.output_dir)))

    # -- finalization ------------------------------------------------------
    def finish(self) -> RunManifest:
        if self.finished:
            raise ResearchGateError("session already finished")
        spec = self.spec
        frames = history_frames(self.history)
        write_material_tables(self.output_dir, frames)
        summary = _build_summary(
            runtime=self.runtime,
            run_id=self.run_id,
            spec=spec,
            state=self.state,
            political=self.political,
            history=self.history,
            frames=frames,
            rng=self.rng,
            parameter_hash=self.parameter_hash,
            initial_recipe_hash=self.initial_recipe_hash,
            checkpoint_paths=self.checkpoint_paths,
            tallies=self.tallies,
            logical_mode=self.logical_mode,
            performance={"total_wall_s": time.perf_counter() - self.run_started},
        )
        write_summary(summary, self.output_dir)
        parameters_declaration = spec.material_parameters
        assert parameters_declaration is not None
        (self.output_dir / "parameters.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "scenario_id": spec.scenario_id,
                    "parameter_hash": self.parameter_hash,
                    "declaration": parameters_declaration.model_dump(mode="json"),
                    "political_parameters": self.politics.parameters.model_dump(mode="json"),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        hashes = hash_output_tree(self.output_dir)
        boundary = self.state.completed_ticks
        status: Literal["completed", "paused"] = "completed" if boundary == spec.ticks else "paused"
        final = finalize_manifest(
            self.manifest,
            status=status,
            output_hashes=hashes,
            rng_draws_count=self.rng.draws_count(),
            rng_draws_by_module=self.rng.draws_by_module(),
            stochastic_modules_active=[
                module for module, count in self.rng.draws_by_module().items() if count > 0
            ],
            deterministic_replay_digest=self.history.digest_chain,
            completed_ticks=boundary,
            last_completed_quarter=(str(spec.start.advance(boundary - 1)) if boundary else None),
        )
        write_manifest_atomic(self.output_dir, final)
        self.finished = True
        return final

    def mark_failed(self, exc: BaseException) -> None:
        """Record a failed run; never silently downgrade the evidence."""
        if self.finished:
            return
        draws_by_module = self.rng.draws_by_module() if self.rng is not None else {}
        boundary = self.admitted_ticks
        failed = finalize_manifest(
            self.manifest,
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
                str(self.spec.start.advance(boundary - 1)) if boundary else None
            ),
        )
        try:
            write_manifest_atomic(self.output_dir, failed)
        except OSError:  # pragma: no cover - evidence already lost
            pass


def open_political_session(
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
) -> PoliticalSession:
    """Build the run context and open a session (preflight + restore/init)."""
    runtime = _build_runtime(
        spec,
        contract,
        registry,
        until=until,
        resume_from=resume_from,
        fork_from=fork_from,
        interventions=interventions,
    )
    return PoliticalSession(
        runtime, output_dir, registry, until, checkpoint_every, resume_from, fork_from
    ).open()


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
    session = open_political_session(
        spec,
        output_dir,
        contract,
        registry,
        until=until,
        checkpoint_every=checkpoint_every,
        resume_from=resume_from,
        fork_from=fork_from,
        interventions=interventions,
    )
    try:
        while not session.done:
            session.admit_quarter()
        return session.finish()
    except Exception as exc:  # noqa: BLE001 - record evidence, then re-raise
        session.mark_failed(exc)
        raise


def _build_runtime(
    spec: ScenarioSpec,
    contract: ResearchContract,
    registry: Any,
    *,
    until: Quarter | str | None,
    resume_from: Path | None,
    fork_from: ForkOrigin | None,
    interventions: list[InterventionSpec] | None,
) -> PoliticalRuntime:
    """Assemble the immutable per-run context (external pack, events, schedule)."""
    if spec.kind != "material":
        raise ConfigError(f"run_political requires kind='material', got {spec.kind!r}")
    if spec.politics is None:
        raise ConfigError("run_political requires a politics block (use run_material otherwise)")
    root = registry.root
    from hsm_lab.contract.guards import BASELINE_FILENAME, verify_baseline

    verify_baseline(root / BASELINE_FILENAME, contract)
    spec.validate_for_run(contract)

    parent_scenario = spec if fork_from is None else fork_from.parent_scenario
    politics = spec.politics
    assert isinstance(politics, PoliticalRunSpec)

    resuming_counterfactual = False
    compiled_interventions: list[CompiledIntervention] = []
    resume_base_mode: PoliticalMode | None = None
    if resume_from is not None:
        from hsm_lab.storage.fork import inherited_interventions_of, resolve_root_base_mode

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
            resume_base_mode = resolve_root_base_mode(resume_metadata)

    from hsm_lab.engine.policy import default_initial_policy as _dip

    politics = politics.model_copy(
        update={"parameters": resolve_political_parameters(politics.parameters, _dip(spec))}
    )
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

    forcing = load_material_forcing(spec, registry)
    parameter_vector = {**material_parameter_vector(spec), **politics.parameters.flatten()}
    parameter_hash = compute_parameter_hash(parameter_vector)
    pack = load_external_pack(politics, registry)
    events = load_event_registry(root)
    program = load_information_program(root, pack.information_program_path or "")

    schedule: dict[str, list[float]] | None = None
    if base_mode is PoliticalMode.HISTORICAL_REPLAY and (
        politics.mode is not PoliticalMode.COUNTERFACTUAL or politics.replay_registry
    ):
        all_quarters = [str(spec.start.advance(k)) for k in range(spec.ticks)]
        schedule = compile_policy_schedule(politics, registry, all_quarters)

    branch = None
    if fork_from is not None:
        branch = build_branch_spec(
            origin=fork_from,
            child_spec=spec,
            root_parameter_hash=parameter_hash,
            branch_parameter_hash=canonical_digest(
                {
                    "base_parameter_hash": parameter_hash,
                    "interventions": [
                        item.spec.model_dump(mode="json") for item in compiled_interventions
                    ],
                }
            ),
            external_history_hash=pack.pack_hash,
            root_scenario_hash=compute_scenario_hash(parent_scenario),
        )
    return PoliticalRuntime(
        spec=spec,
        contract=contract,
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


def _objective_weights(spec: ScenarioSpec, politics: PoliticalRunSpec, registry: Any) -> np.ndarray:
    return np.ones(J, dtype=np.float64)


def _opposition_initial(
    spec: ScenarioSpec, politics: PoliticalRunSpec, registry: Any
) -> np.ndarray:
    parameters = politics.parameters.opposition
    return np.tile(
        np.asarray(parameters.initial_state, dtype=np.float64), (len(spec.region_ids), 1)
    )


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


def _decide(
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
) -> DecisionOutcome:
    """Compute (without committing) the coalition transition and policy for one quarter.

    This is the single decision rule shared by the native runner and the
    SocioVerse2 `DecisionModel` adapter; it reads state and writes nothing, so it
    can be proposed first and committed later.
    """
    parameters = runtime.politics.parameters
    capability = float(political.information_capability[0])
    override = cf_state.capability_override(tick)
    if override is not None:
        capability = float(override)
    information = information_state(capability, parameters.information)

    published, valid, source = select_published(political, tick, information.total_lag)
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
    decision: PolicyDecision
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

    patches = cf_state.policy_patches(tick)
    if patches:
        policy = policy.patch(patches)
        decision = dataclasses.replace(decision, selected_policy=policy.to_vector())

    constraint = float(np.clip(soviet_constraint, 0.0, 1.0))
    cap = 1.0 - constraint * (1.0 - float(broker_parameters.soviet_floor))
    if runtime.base_mode is PoliticalMode.HISTORICAL_REPLAY:
        # Mode A (and A-based branches) keep the declared replay policy; the
        # Soviet feasible set is diagnostic only (recorded as a violation).
        violation = max(
            0.0,
            float(policy.enterprise_autonomy) - cap,
            float(policy.cultural_openness) - cap,
        )
        soviet_bound = False
    else:
        policy = _project_soviet(policy, constraint, broker_parameters)
        violation = 0.0
        soviet_bound = bool(
            float(policy.enterprise_autonomy) >= cap - 1e-12
            or float(policy.cultural_openness) >= cap - 1e-12
        )

    a_matrix = np.asarray(broker_parameters.A, dtype=np.float64)
    error, prediction = _policy_error(previous_policy, feedback.objective_vector, a_matrix)
    return DecisionOutcome(
        policy=policy,
        transition=transition,
        decision=decision,
        prediction=prediction,
        objective=np.asarray(feedback.objective_vector, dtype=np.float64),
        policy_error=error,
        capability=capability,
        information=information,
        weights_before=weights,
        policy_source=(
            "replay" if runtime.base_mode is PoliticalMode.HISTORICAL_REPLAY else "broker"
        ),
        soviet_bound=soviet_bound,
        soviet_violation=violation,
        publication_source=int(source),
    )


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


def select_published(
    political: PoliticalState, tick: int, total_lag: int
) -> tuple[np.ndarray, np.ndarray, int]:
    """Pick the lagged published state view for a decision (read-only).

    The publication cursor is *not* advanced here: it is committed by the
    session when the quarter is admitted, so a decision proposal never mutates
    causal state.
    """
    cursor = int(political.publication_cursor[0])
    source = max(tick - 1 - int(total_lag), cursor)
    if source < 0:
        return _initial_published(), np.zeros(F, dtype=bool), -1
    slot = source % POLITICAL_RING_LENGTH
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
