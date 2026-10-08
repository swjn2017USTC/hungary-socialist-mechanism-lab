"""SocioVerse2 minimal real-store smoke (pinned ``socioverse2==0.2.0``).

This exercises the real DuckDB/Parquet trajectory store and its actual API -
no mocks, no LLM, no external event client, no economic computation. The
integration imports lazily: ``socioverse`` never enters the probe runtime.

Pinned-0.2.0 API notes (verified against the installed wheel):
- ``TrajectoryRecord`` has NO ``action_source`` field (main branch added it
  later); only agent_id/step/state/action_kind/action_payload are used.
- ``DuckDbTrajectoryStore.open()`` unlinks an existing DB, so the caller must
  pass a fresh directory.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from hsm_lab.contract.politics import COALITION_IDS, PoliticalMode
from hsm_lab.contract.schemas import ResearchGateError

STUDY_ID = "p00-smoke"


def smoke_socioverse(directory: Path) -> dict[str, Any]:
    """Write/read a real 2-agent, 2-step trajectory store in ``directory``.

    ``directory`` must be fresh (the upstream store unlinks existing DBs).
    Returns SQL/parquet evidence; raises with the real traceback on failure.
    """
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ResearchGateError(f"socioverse smoke directory not fresh: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    db_path = directory / "study.duckdb"

    trajectory = import_module("socioverse.schemas.trajectory")
    duckdb_store = import_module("socioverse.io.duckdb_store")

    TrajectoryRecord = trajectory.TrajectoryRecord
    DuckDbTrajectoryStore = duckdb_store.DuckDbTrajectoryStore
    open_readonly = duckdb_store.open_readonly

    store = DuckDbTrajectoryStore(db_path, study_id=STUDY_ID, export_parquet=True)
    store.open()
    for step in (0, 1):
        store.record(
            [
                TrajectoryRecord(
                    agent_id=f"probe-{agent}",
                    step=step,
                    state={"probe_value": step, "synthetic": True},
                    action_kind=None,
                    action_payload={},
                )
                for agent in (0, 1)
            ]
        )
        store.record_metrics({"step": step, "probe_total": 2 * step})
        if step == 1:
            store.record_events(step, ["p00-synthetic-event"])
    store.finalize()

    evidence: dict[str, Any] = {"study_id": STUDY_ID, "db_path": db_path.name}
    connection = open_readonly(db_path)
    try:
        panel_rows = connection.execute(
            "SELECT agent_id, step, CAST(state AS VARCHAR) AS state, action_kind, "
            "CAST(action_payload AS VARCHAR) AS action_payload "
            "FROM panel ORDER BY agent_id, step"
        ).fetchall()
        evidence["panel_rows"] = len(panel_rows)
        evidence["panel_primary_keys_unique"] = len(
            {(agent, step) for agent, step, *_ in panel_rows}
        ) == len(panel_rows)
        evidence["state_probe_values"] = {
            f"step{step}": sorted(
                int(row[0])
                for row in connection.execute(
                    f"SELECT json_extract(state, '$.probe_value') FROM panel WHERE step = {step}"
                ).fetchall()
            )
            for step in (0, 1)
        }
        metrics_rows = connection.execute(
            "SELECT step, probe_total FROM metrics ORDER BY step"
        ).fetchall()
        evidence["metrics"] = [list(row) for row in metrics_rows]
        events_rows = connection.execute("SELECT step, note FROM events ORDER BY step").fetchall()
        evidence["events"] = [list(row) for row in events_rows]
    finally:
        connection.close()

    import polars as pl

    # Content-level round-trip equality: compare every field, semantically
    # for JSON columns; disagreement fails the smoke instead of flagging.
    def _json_or_none(text: object) -> object:
        import json as _json

        return _json.loads(str(text)) if text is not None else None

    panel_parquet = pl.read_parquet(directory / "panel.parquet")
    metrics_parquet = pl.read_parquet(directory / "metrics.parquet")
    panel_from_parquet = sorted(
        (
            row[0],
            row[1],
            _json_or_none(row[2]),
            row[3],
            _json_or_none(row[4]),
        )
        for row in panel_parquet.iter_rows()
    )
    panel_from_db = sorted(
        (row[0], row[1], _json_or_none(row[2]), row[3], _json_or_none(row[4])) for row in panel_rows
    )
    metrics_from_parquet = sorted((row[0], row[1]) for row in metrics_parquet.iter_rows())
    metrics_from_db = sorted((row[0], row[1]) for row in metrics_rows)
    if panel_from_parquet != panel_from_db:
        raise ResearchGateError(
            "socioverse smoke: panel.parquet content disagrees with the DuckDB panel:\n"
            f"  parquet: {panel_from_parquet}\n  db:      {panel_from_db}"
        )
    if metrics_from_parquet != metrics_from_db:
        raise ResearchGateError(
            "socioverse smoke: metrics.parquet content disagrees with the DuckDB "
            f"metrics:\n  parquet: {metrics_from_parquet}\n  db:      {metrics_from_db}"
        )
    evidence["panel_parquet_rows"] = panel_parquet.height
    evidence["metrics_parquet_rows"] = metrics_parquet.height
    evidence["panel_parquet_matches_db"] = True  # enforced above, else raised
    evidence["metrics_parquet_matches_db"] = True
    return evidence


# ---------------------------------------------------------------------------
# P04 longitudinal orchestration (real SocioVerse2 loop over the native session)
# ---------------------------------------------------------------------------
#
# Division of labour: SocioVerse2 owns the longitudinal step loop, the persistent
# institutional IDs, the environment projection, information routing and the
# small panel/metrics store.  The project's own ``PoliticalSession`` owns the
# causal engine (external slice, signals, coalition/broker rule, material
# kernel, culture/opposition/observation, invariants, checkpoints).  The
# decision model is a *rule* (no LLM, no decision client); branching is the
# project's checkpoint/replay, not the framework's action replay.

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from hsm_lab.engine.political_run import PoliticalSession

try:  # pragma: no cover - exercised through the integration tests
    from socioverse.abc.decision import DecisionModel as _DecisionModelBase
    from socioverse.abc.environment import EnvironmentProvider as _EnvironmentProviderBase
    from socioverse.abc.population import PopulationProvider as _PopulationProviderBase
    from socioverse.abc.trajectory import MetricCollector as _MetricCollectorBase
    from socioverse.abc.trajectory import TrajectoryStore as _TrajectoryStoreBase
    from socioverse.engine.loop import LongitudinalSimulator as _LongitudinalSimulator
    from socioverse.env_layers.information import InformationEnvironment as _InformationEnvironment
    from socioverse.io.duckdb_store import DuckDbTrajectoryStore as _DuckDbTrajectoryStore
    from socioverse.schemas.environment import (
        Broadcast as _Broadcast,
    )
    from socioverse.schemas.environment import (
        EnvironmentBundle as _EnvironmentBundle,
    )
    from socioverse.schemas.environment import (
        EnvironmentLayer as _EnvironmentLayer,
    )
    from socioverse.schemas.environment import (
        InformationProgram as _SvInformationProgram,
    )
    from socioverse.schemas.population import (
        InteractionStructure as _InteractionStructure,
    )
    from socioverse.schemas.population import (
        Persona as _Persona,
    )
    from socioverse.schemas.population import (
        PopulationBundle as _PopulationBundle,
    )
    from socioverse.schemas.runtime import Action as _Action
    from socioverse.schemas.runtime import Observation as _Observation
    from socioverse.schemas.trajectory import TrajectoryRecord as _TrajectoryRecord

    SOCIOVERSE_IMPORT_ERROR: Exception | None = None
except Exception as _exc:  # noqa: BLE001 - reported, never silently ignored
    SOCIOVERSE_IMPORT_ERROR = _exc

COALITION_AGENT_PREFIX = "coalition:"
BROKER_AGENT_ID = "leadership:broker"
PLANNER_AGENT_ID = "state:planner"
REGION_AGENT_PREFIX = "region:"


def _require_socioverse() -> None:
    if SOCIOVERSE_IMPORT_ERROR is not None:
        raise ResearchGateError(
            f"SocioVerse2 is unavailable ({SOCIOVERSE_IMPORT_ERROR}); the longitudinal "
            "orchestration requires the pinned socioverse2==0.2.0 install"
        )


def institutional_agent_ids(region_ids: list[str]) -> list[str]:
    """The 26 persistent institutional/aggregate ids (never household personas)."""
    return [
        *[f"{COALITION_AGENT_PREFIX}{name}" for name in COALITION_IDS],
        BROKER_AGENT_ID,
        PLANNER_AGENT_ID,
        *[f"{REGION_AGENT_PREFIX}{region}" for region in region_ids],
    ]


def _decision_payload(outcome: Any) -> dict[str, Any]:
    """JSON-serializable summary of one broker decision (panel + Action payload)."""
    decision = outcome.decision
    return {
        "selected_index": int(decision.selected_index),
        "selected_policy": [float(value) for value in decision.selected_policy],
        "candidate_ids": list(decision.candidate_ids),
        "candidate_utilities": [
            float(value) for value in np.asarray(decision.candidate_utilities, dtype=np.float64)
        ],
        "candidate_terms": [
            [float(value) for value in row]
            for row in np.asarray(
                decision.candidate_terms
                if decision.candidate_terms is not None
                else np.zeros((0, 4)),
                dtype=np.float64,
            )
        ],
        "binding_constraints": list(decision.binding_constraints),
        "candidate_binding": [list(items) for items in (decision.candidate_binding or [])],
        "coalition_weights": [float(value) for value in outcome.transition.new_weights],
        "policy_error": float(outcome.policy_error),
        "source": decision.source,
    }


def _decision_from_payload(payload: dict[str, Any]) -> Any:
    """Rebuild the typed ``PolicyDecision`` handed back by the decision model."""
    from hsm_lab.contract.politics import PolicyDecision, U

    candidate_ids = [str(value) for value in payload.get("candidate_ids", [])]
    utilities = np.asarray(payload.get("candidate_utilities", []), dtype=np.float64)
    terms = np.asarray(payload.get("candidate_terms", []), dtype=np.float64)
    selected_policy = np.asarray(payload["selected_policy"], dtype=np.float64)
    if selected_policy.shape != (U,):
        raise ResearchGateError(
            f"broker action selected_policy has shape {selected_policy.shape}, expected ({U},)"
        )
    if utilities.shape != (len(candidate_ids),):
        raise ResearchGateError("broker action candidate_utilities do not align with candidate_ids")
    if terms.size and terms.shape != (len(candidate_ids), 4):
        raise ResearchGateError("broker action candidate_terms must be (C, 4)")
    return PolicyDecision(
        candidate_ids=candidate_ids,
        candidate_utilities=utilities,
        candidate_policies=np.zeros((len(candidate_ids), U), dtype=np.float64),
        selected_index=int(payload.get("selected_index", -1)),
        selected_policy=selected_policy,
        binding_constraints=[str(v) for v in payload.get("binding_constraints", [])],
        source=str(payload.get("source", "broker")),
        elite_cohesion=0.0,
        candidate_terms=terms if terms.size else None,
        candidate_binding=[
            [str(v) for v in items] for items in payload.get("candidate_binding", [])
        ]
        or None,
    )


class InstitutionalPopulation(_PopulationProviderBase):  # type: ignore[misc]
    """26 persistent institutional actors; no household/persona attributes."""

    def __init__(self, study_id: str, region_ids: list[str]) -> None:
        _require_socioverse()
        self.region_ids = list(region_ids)
        self.agent_ids = institutional_agent_ids(self.region_ids)
        self.bundle = _PopulationBundle(
            study_id=study_id,
            provider_ref="hsm_lab.integrations.socioverse:InstitutionalPopulation",
            interaction=_InteractionStructure(kind="none"),
            materialized_count=len(self.agent_ids),
        )

    def build(self, seed: int) -> list[Any]:  # noqa: ARG002 - deterministic roster
        personas: list[Any] = []
        for agent_id in self.agent_ids:
            if agent_id.startswith(REGION_AGENT_PREFIX):
                region_id = agent_id[len(REGION_AGENT_PREFIX) :]
                attributes = {"role": "region", "region_id": region_id}
            elif agent_id == BROKER_AGENT_ID:
                attributes = {"role": "broker"}
            elif agent_id == PLANNER_AGENT_ID:
                attributes = {"role": "planner"}
            else:
                attributes = {
                    "role": "coalition",
                    "coalition": agent_id[len(COALITION_AGENT_PREFIX) :],
                }
            personas.append(
                _Persona(agent_id=agent_id, attributes=attributes, group_key="institution")
            )
        return personas


class PoliticalEnvironment(_EnvironmentProviderBase):  # type: ignore[misc]
    """Environment E over the native session; E advances exactly via ``apply``."""

    def __init__(self, session: PoliticalSession, information_environment: Any) -> None:
        _require_socioverse()
        self.session = session
        self.information = information_environment
        self.region_ids = list(session.spec.region_ids)
        self.offset = session.start_tick
        self.bundle = _EnvironmentBundle(
            study_id=session.runtime.politics.study_id,
            layers=[
                _EnvironmentLayer(
                    name="macro_physical",
                    modality="physical",
                    scope="macro",
                    description="lagged published macro state (never current truth)",
                ),
                _EnvironmentLayer(
                    name="region_physical",
                    modality="physical",
                    scope="local",
                    description="county opposition/capacity aggregate",
                ),
                _EnvironmentLayer(
                    name="state_information",
                    modality="information",
                    scope="macro",
                    description="scheduled event broadcasts (display + provenance)",
                ),
                _EnvironmentLayer(
                    name="region_information",
                    modality="information",
                    scope="local",
                    description="audience-scoped broadcasts",
                ),
            ],
            provider_ref="hsm_lab.integrations.socioverse:PoliticalEnvironment",
        )

    # -- ABC ---------------------------------------------------------------
    def reset(self, seed: int) -> None:  # noqa: ARG002 - session owns the state
        self.information.reset()
        self._reset_steps = 0

    def advance_to(self, t: int) -> list[Any]:
        # Broadcasts carry GLOBAL closing steps; the framework's step counter is
        # local to this child run, so offset it back to the global step.
        self.information.advance_to(self.offset + int(t))
        return []

    def observe_batch(self, agent_ids: list[str], t: int, round_idx: int = 0) -> list[Any]:
        published = self.session.published_view()
        macro_information = self.information.macro()
        observations: list[Any] = []
        for agent_id in agent_ids:
            context: dict[str, Any] = {}
            local_physical: dict[str, Any] = {}
            if agent_id.startswith(REGION_AGENT_PREFIX):
                region_id = agent_id[len(REGION_AGENT_PREFIX) :]
                context = {"region_id": region_id}
                local_physical = self.session.region_state(region_id)
            observations.append(
                _Observation(
                    agent_id=agent_id,
                    step=t,
                    macro_physical=dict(published),
                    local_physical=local_physical,
                    macro_information=dict(macro_information),
                    local_information=dict(self.information.local_for(context)),
                )
            )
        return observations

    def apply(self, actions: list[Any]) -> None:
        if self.session.done:
            raise ResearchGateError(
                "the session already reached its target boundary; refusing to admit another quarter"
            )
        broker_actions = [action for action in actions if action.agent_id == BROKER_AGENT_ID]
        replay_mode = self.session.runtime.base_mode is PoliticalMode.HISTORICAL_REPLAY
        if replay_mode:
            if broker_actions:
                raise ResearchGateError(
                    "a Mode A (historical replay) run must not receive a broker policy action"
                )
            self.session.admit_quarter()
            return
        if len(broker_actions) != 1:
            raise ResearchGateError(
                f"exactly one broker policy_choice action is required, got {len(broker_actions)}"
            )
        action = broker_actions[0]
        if action.kind != "policy_choice" or action.source != "rule":
            raise ResearchGateError(
                f"broker action must be kind='policy_choice' with source='rule', got "
                f"{action.kind!r}/{action.source!r}"
            )
        self.session.admit_quarter(decision=_decision_from_payload(action.payload))

    def agent_state(self, agent_id: str) -> dict[str, Any]:
        audit = self.session.audit_state()
        if agent_id == BROKER_AGENT_ID:
            return {
                "role": "broker",
                "quarter": audit["quarter"],
                "completed_ticks": audit["completed_ticks"],
                "policy": audit["policy"],
                "elite_cohesion": audit["elite_cohesion"],
                "information_capability": audit["information_capability"],
            }
        if agent_id == PLANNER_AGENT_ID:
            return {
                "role": "planner",
                "quarter": audit["quarter"],
                "information_capability": audit["information_capability"],
                "max_material_tolerance_ratio": audit["max_material_tolerance_ratio"],
            }
        if agent_id.startswith(COALITION_AGENT_PREFIX):
            name = agent_id[len(COALITION_AGENT_PREFIX) :]
            index = COALITION_IDS.index(name)
            return {
                "role": "coalition",
                "coalition": name,
                "weight": audit["coalition_weights"][index],
                "elite_cohesion": audit["elite_cohesion"],
            }
        if agent_id.startswith(REGION_AGENT_PREFIX):
            return {
                "role": "region",
                **self.session.region_state(agent_id[len(REGION_AGENT_PREFIX) :]),
            }
        raise ResearchGateError(f"unknown institutional agent id {agent_id!r}")

    def snapshot(self) -> dict[str, Any]:
        return self.session.audit_state()


class PoliticalRuleDecision(_DecisionModelBase):  # type: ignore[misc]
    """Rule-based decision model: only the broker acts, and only through the rule."""

    def __init__(self, session: PoliticalSession) -> None:
        _require_socioverse()
        self.session = session
        self.replay_mode = session.runtime.base_mode is PoliticalMode.HISTORICAL_REPLAY

    def decide_batch(self, obs: list[Any], memories: dict[str, Any]) -> list[Any]:  # noqa: ARG002
        if self.replay_mode:
            # Mode A replays the declared policy: no broker decision is made.
            return []
        broker = [observation for observation in obs if observation.agent_id == BROKER_AGENT_ID]
        if len(broker) != 1:
            raise ResearchGateError(f"expected exactly one broker observation, got {len(broker)}")
        observation = broker[0]
        outcome = self.session.propose_decision()
        return [
            _Action(
                agent_id=BROKER_AGENT_ID,
                step=observation.step,
                kind="policy_choice",
                payload=_decision_payload(outcome),
                rationale=[
                    "rule: coalition multinomial-logit update + broker candidate utility argmax"
                ],
                source="rule",
            )
        ]


class PoliticalMetricCollector(_MetricCollectorBase):  # type: ignore[misc]
    """Per-step metrics from the admitted session boundary (audit aggregates only)."""

    def __init__(self, session: PoliticalSession) -> None:
        _require_socioverse()
        self.session = session

    def columns(self) -> list[str]:
        return [
            "step",
            "completed_ticks",
            "quarter",
            "information_capability",
            "elite_cohesion",
            "weight_reform_technocratic",
            "weight_administrative_conservative",
            "weight_social_contract_pragmatist",
            "weight_sectoral_industrial",
            "max_material_tolerance_ratio",
        ]

    def collect(self, env: Any, actions: list[Any], t: int) -> dict[str, Any]:  # noqa: ARG002
        audit = self.session.audit_state()
        weights = audit["coalition_weights"]
        return {
            "step": t,
            "completed_ticks": audit["completed_ticks"],
            "quarter": audit["quarter"],
            "information_capability": audit["information_capability"],
            "elite_cohesion": audit["elite_cohesion"],
            "weight_reform_technocratic": weights[0],
            "weight_administrative_conservative": weights[1],
            "weight_social_contract_pragmatist": weights[2],
            "weight_sectoral_industrial": weights[3],
            "max_material_tolerance_ratio": audit["max_material_tolerance_ratio"],
        }


class OffsetTrajectoryStore(_TrajectoryStoreBase):  # type: ignore[misc]
    """Thin store wrapper that maps local steps onto global (restored) steps."""

    def __init__(self, inner: Any, offset: int) -> None:
        _require_socioverse()
        self.inner = inner
        self.offset = int(offset)
        self.db_path = getattr(inner, "db_path", None)

    def open(self) -> None:
        self.inner.open()

    def _shifted(self, records: list[Any]) -> list[Any]:
        if self.offset == 0:
            return list(records)
        return [
            _TrajectoryRecord(
                agent_id=record.agent_id,
                step=int(record.step) + self.offset,
                state=record.state,
                action_kind=record.action_kind,
                action_payload=record.action_payload,
            )
            for record in records
        ]

    def record(self, records: list[Any]) -> None:
        self.inner.record(self._shifted(records))

    def record_metrics(self, row: dict[str, Any]) -> None:
        shifted = dict(row)
        shifted["step"] = int(row.get("step", 0)) + self.offset
        self.inner.record_metrics(shifted)

    def record_events(self, step: int, notes: list[str]) -> None:
        self.inner.record_events(int(step) + self.offset, notes)

    def record_messages(self, messages: list[dict[str, Any]]) -> None:
        self.inner.record_messages(messages)

    def finalize(self) -> None:
        self.inner.finalize()


def _to_broadcast(message: Any, source: str) -> Any:
    audience: Any = "all" if message.audience_all else {"region_id_in": list(message.region_ids)}
    return _Broadcast(
        message_id=message.message_id,
        content=message.content,
        channel=message.channel,
        at_step=message.at_step,
        ttl=message.ttl,
        audience=audience,
        note=(
            f"hsm p04 {source} broadcast (display/provenance only; the causal "
            "intensity lives in the session's typed signals)"
        ),
    )


def _broadcast_program(session: PoliticalSession) -> Any:
    """Bridge the project's information program into a SocioVerse2 program.

    Both the scheduled historical-event broadcasts and the branch's declared
    counterfactual broadcasts are routed, so the framework's information
    environment reproduces the same delivery (audience/TTL) the causal layer
    applies.  Text is never parsed for numeric effects.
    """
    broadcasts = [_to_broadcast(message, "event") for message in session.runtime.program.messages]
    for item in session.runtime.interventions:
        if item.message is not None:
            broadcasts.append(_to_broadcast(item.message, "counterfactual"))
    broadcasts.sort(key=lambda item: (item.at_step, item.message_id))
    return _SvInformationProgram(broadcasts=broadcasts)


def run_political_socioverse(
    spec: Any,
    output_dir: Path,
    contract: Any,
    registry: Any,
    *,
    until: Any = None,
    checkpoint_every: int = 0,
    resume_from: Path | None = None,
    fork_from: Any = None,
    interventions: list[Any] | None = None,
    interaction_rounds: int = 1,
) -> Any:
    """Run a P04 scenario through the real SocioVerse2 longitudinal simulator.

    The framework drives the step loop, the 26 institutional panel and the
    information routing; the project's `PoliticalSession` remains the causal
    engine and the only admission owner.
    """
    _require_socioverse()
    from hsm_lab.engine.political_run import open_political_session

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
    n_steps = session.remaining_ticks
    if n_steps == 0:
        return session.finish()

    store_dir = session.output_dir / "socioverse"
    if store_dir.exists() and any(store_dir.iterdir()):
        session.mark_failed(ResearchGateError(f"socioverse store dir not fresh: {store_dir}"))
        raise ResearchGateError(
            f"socioverse store directory {store_dir} is not fresh; each run owns its store"
        )
    store = OffsetTrajectoryStore(
        _DuckDbTrajectoryStore(
            store_dir / "study.duckdb", study_id=session.runtime.politics.study_id
        ),
        offset=session.start_tick,
    )
    environment = PoliticalEnvironment(
        session, _InformationEnvironment(program=_broadcast_program(session))
    )
    population = InstitutionalPopulation(session.runtime.politics.study_id, session.region_ids)
    collector = PoliticalMetricCollector(session)
    simulator = _LongitudinalSimulator(
        env=environment,
        population=population,
        decision=PoliticalRuleDecision(session),
        store=store,
        collector=collector,
        n_steps=n_steps,
        seed=spec.seed,
        interaction_rounds=max(1, int(interaction_rounds)),
        memory_window=1,
        metric_columns=collector.columns(),
        study_id=session.runtime.politics.study_id,
    )
    try:
        simulator.run()
    except Exception as exc:  # noqa: BLE001 - record evidence, then re-raise
        session.mark_failed(exc)
        raise
    return session.finish()
