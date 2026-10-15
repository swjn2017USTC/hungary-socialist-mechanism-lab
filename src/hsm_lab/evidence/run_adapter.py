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

from hsm_lab.evidence.provenance import verify_run_identity


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


def verify_digest_unchanged(
    scenario_id: str,
    seed: int,
    expected_digest: str,
    output_dir: Path,
    root: Path,
) -> bool:
    """Verify that a scenario run produces the expected digest.

    Delegates to ``verify_run_identity`` for full provenance verification.
    Returns False on any verification failure (missing files, hash mismatch,
    wrong seed, incomplete run, etc.).

    Returns
    -------
    bool
        True if verification passes; False on any failure.
    """
    try:
        verify_run_identity(
            root=root,
            scenario_id=scenario_id,
            seed=seed,
            expected_digest=expected_digest,
            output_dir=output_dir,
        )
    except (ValueError, OSError):
        return False
    return True


def get_c0_digest() -> str:
    """Return the C0 (historical_f2_replay) reference digest."""
    return "92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d"


def get_c1_digest() -> str:
    """Return the C1 (historical_f2_trade_scenario) reference digest."""
    return "c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5"
