"""P07B1 §1: minimal runner adapter — ScenarioSpec → EvidenceRecord.

This module bridges the existing `run_material()` engine entry point to the
P07 evidence registry. It validates the scenario against the MetricSpec
registry, runs the model (if explicitly requested), and produces a stub
EvidenceRecord with the run digest. It does NOT run full experiments;
negative-control runs are the only permitted execution at this phase.

No production engine code is modified; this adapter only calls existing
entry points.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from hsm_lab.evidence.adapter import MetricSpecRegistry
from hsm_lab.evidence.schemas import (
    EvidenceRecord,
    EvidenceStatus,
    MetricSpec,
)


class AdapterConfig(BaseModel):
    """Configuration for the evidence run adapter."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    # If True, actually run the model. At B1 this must be False.
    run_model: bool = Field(default=False)
    # Existing C0/C1 digests for regression comparison
    known_digest: str | None = Field(
        default=None,
        description="SHA-256 digest of a reference run for regression",
    )


def build_stub_evidence_record(
    scenario_id: str,
    phase: str,
    mechanism_ids: list[str],
    registry: MetricSpecRegistry,
    run_digest: str | None = None,
    status: EvidenceStatus = EvidenceStatus.DECLARED,
) -> EvidenceRecord:
    """Build a stub EvidenceRecord with the scenario's metric specs.

    This is a *declaration* record: it records which metrics are in scope
    for this scenario and which mechanism IDs are linked. It does NOT contain
    experiment results.

    Parameters
    ----------
    scenario_id
        e.g. "historical_f2_replay".
    phase
        Current phase, e.g. "P07B1".
    mechanism_ids
        Which M1–M11 are in scope for this scenario.
    registry
        The MetricSpecRegistry with all known metric specs.
    run_digest
        The digest of the run output (if a run has been performed).
    status
        Initial status; at B1 this is DECLARED.

    Returns
    -------
    EvidenceRecord
        Stub evidence record with metric specs from the registry.
    """
    # Collect all metric specs for the specified mechanism IDs
    all_specs: list[MetricSpec] = []
    for spec in registry.metric_specs:
        # metric_id format is "{mechanism}.{metric}" e.g. "m1.household_consumption"
        for mid in mechanism_ids:
            if spec.metric_id.startswith(f"{mid.lower()}."):
                all_specs.append(spec)
                break

    record_id = f"{phase}-{scenario_id}-stub"
    # For single-card stubs use the real ID; for multi-card use first ID
    # (the declared_reason records the full list)
    primary_mechanism = mechanism_ids[0] if mechanism_ids else "M1"

    return EvidenceRecord(
        record_id=record_id,
        mechanism_id=primary_mechanism,
        v1_card_sha256="0" * 64,  # stub; real SHA set per-card later
        hypothesis=f"Stub evidence record for scenario {scenario_id} at {phase}",
        status=status,
        metric_specs=all_specs,
        intervention_bindings=[],
        linked_observed_states=[],
        declared_reason=(
            f"B1 stub: adapter declared for scenario={scenario_id}, "
            f"mechanisms={mechanism_ids}, {len(all_specs)} metric specs in scope"
        ),
        blocked_reason=None,
        minimum_replicates=1,
        created_by_phase=phase,
    )


def verify_digest_unchanged(
    scenario_id: str,
    seed: int,
    expected_digest: str,
    output_dir: Path,
    root: Path,
) -> bool:
    """Verify that a scenario run produces the expected digest.

    This function does NOT run the model; it only checks whether a
    previously-run output directory contains the expected digest.

    Returns
    -------
    bool
        True if the output dir exists and its digest matches expected_digest.
    """
    import json

    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    digest = manifest.get("deterministic_replay_digest") or manifest.get("run_digest")
    return digest == expected_digest


def get_c0_digest() -> str:
    """Return the C0 (historical_f2_replay) reference digest."""
    return "92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d"


def get_c1_digest() -> str:
    """Return the C1 (historical_f2_trade_scenario) reference digest."""
    return "c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5"
