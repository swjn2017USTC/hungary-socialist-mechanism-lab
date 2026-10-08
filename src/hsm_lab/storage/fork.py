"""P04 counterfactual fork: load an immutable parent boundary and diverge.

A fork never re-executes the parent prefix and never mutates the parent's
output.  It restores the parent checkpoint *strictly* (the same loader, the
same gates), records the branch identity (source checkpoint hash, base mode,
declared interventions, inherited interventions) and then continues the suffix
with the child's effective politics mode ``counterfactual``.

The child boundary checkpoint is re-published atomically into the child output
directory with child ownership; the parent's files and hashes are untouched.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.politics import (
    BranchSpec,
    InterventionSpec,
    PoliticalMode,
    PoliticalRunSpec,
)
from hsm_lab.contract.schemas import ResearchContract, ResearchGateError, ScenarioSpec
from hsm_lab.provenance.manifest import canonical_digest


@dataclass(frozen=True)
class ForkOrigin:
    """Everything a counterfactual child needs from its parent boundary."""

    checkpoint: Path
    boundary_tick: int
    base_mode: PoliticalMode
    interventions: list[InterventionSpec]
    inherited_interventions: list[InterventionSpec]
    source_checkpoint_hash: str
    parent_scenario: ScenarioSpec


def checkpoint_identity_hash(checkpoint: Path) -> str:
    """Stable identity of a checkpoint payload (its declared digest map)."""
    metadata_path = checkpoint / "metadata.json"
    if not metadata_path.is_file():
        raise ResearchGateError(f"checkpoint metadata not found: {metadata_path}")
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    digests = payload.get("payload_sha256")
    if not isinstance(digests, dict) or not digests:
        raise ResearchGateError("checkpoint lacks a payload digest map")
    return canonical_digest(
        {
            "payload_sha256": digests,
            "completed_ticks": payload.get("completed_ticks"),
            "digest_chain": payload.get("digest_chain"),
        }
    )


def load_counterfactual_origin(
    checkpoint: Path,
    child_spec: ScenarioSpec,
    contract: ResearchContract,
    *,
    interventions: list[InterventionSpec],
    inherited_interventions: list[InterventionSpec] | None = None,
) -> ForkOrigin:
    """Validate a parent boundary and the declared child interventions."""
    checkpoint = Path(checkpoint)
    metadata_path = checkpoint / "metadata.json"
    if not metadata_path.is_file():
        raise ResearchGateError(f"fork source is not a checkpoint directory: {checkpoint}")
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    boundary = payload.get("completed_ticks")
    if isinstance(boundary, bool) or not isinstance(boundary, int) or boundary <= 0:
        raise ResearchGateError("fork source checkpoint has no positive boundary")
    parent_scenario = ScenarioSpec.model_validate(payload.get("scenario"))
    if parent_scenario.politics is None:
        raise ResearchGateError("fork source checkpoint was not written by a politics-enabled run")
    if not isinstance(parent_scenario.politics, PoliticalRunSpec):  # pragma: no cover
        raise ConfigError("parent scenario politics block is not a PoliticalRunSpec")
    base_mode = parent_scenario.politics.mode
    if base_mode is PoliticalMode.COUNTERFACTUAL:
        # A branch of a branch inherits its root base mode and prior schedule.
        base_mode = parent_scenario.politics.mode
    if (
        child_spec.start.advance(boundary).to_ordinal()
        > child_spec.start.advance(child_spec.ticks - 1).to_ordinal()
    ):
        raise ConfigError(
            f"fork boundary {child_spec.start.advance(boundary)} already ends the scenario; "
            "a fork must have at least one future tick"
        )
    next_quarter = child_spec.start.advance(boundary).to_ordinal()
    for spec in interventions:
        if spec.effective_quarter.to_ordinal() < next_quarter:
            raise ConfigError(
                f"intervention {spec.intervention_id} starts before the fork boundary "
                f"{child_spec.start.advance(boundary)}"
            )
    inherited = list(inherited_interventions or [])
    declared_ids = {spec.target for spec in interventions}
    for spec in inherited:
        if spec.target in declared_ids:
            raise ConfigError(
                f"intervention target {spec.target!r} conflicts with an inherited "
                "intervention schedule"
            )
    return ForkOrigin(
        checkpoint=checkpoint,
        boundary_tick=boundary,
        base_mode=base_mode,
        interventions=list(interventions),
        inherited_interventions=inherited,
        source_checkpoint_hash=checkpoint_identity_hash(checkpoint),
        parent_scenario=parent_scenario,
    )


def build_branch_spec(
    *,
    origin: ForkOrigin,
    child_spec: ScenarioSpec,
    root_parameter_hash: str,
    branch_parameter_hash: str,
    external_history_hash: str,
    root_scenario_hash: str,
    parent_run_id: str | None = None,
    parent_version_id: str | None = None,
) -> BranchSpec:
    """Assemble the recorded branch identity for a Mode C run."""
    return BranchSpec(
        branch_id=f"branch-{origin.source_checkpoint_hash[:12]}",
        source_checkpoint=str(origin.checkpoint),
        source_checkpoint_hash=origin.source_checkpoint_hash,
        parent_run_id=parent_run_id,
        parent_version_id=parent_version_id,
        base_mode=origin.base_mode,
        boundary_tick=origin.boundary_tick,
        external_history_hash=external_history_hash,
        interventions=list(origin.interventions),
        intervention_hash=canonical_digest(
            [spec.model_dump(mode="json") for spec in origin.interventions]
        ),
        inherited_interventions=list(origin.inherited_interventions),
        root_scenario_hash=root_scenario_hash,
        root_parameter_hash=root_parameter_hash,
        branch_parameter_hash=branch_parameter_hash,
    )


__all__ = [
    "ForkOrigin",
    "build_branch_spec",
    "checkpoint_identity_hash",
    "load_counterfactual_origin",
]
