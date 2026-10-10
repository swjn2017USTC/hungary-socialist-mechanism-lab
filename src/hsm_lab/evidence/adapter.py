"""P07A1 §5: v1 card → v2 MetricSpec registry adapter.

This module reads existing v1 mechanism cards (config/p06/cards/M*.json)
and exposes a read-only MetricSpec registry derived from their declared
metrics. It does NOT run experiments, does NOT read target values, and
does NOT modify the production engine.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from hsm_lab.evidence.schemas import (
    DataRole,
    FidelityLevel,
    MetricSpec,
    TimeWindow,
    ValidationFidelity,
)


class MetricSpecRegistry(BaseModel):
    """Read-only registry of MetricSpecs derived from v1 cards.

    This registry is built at P07A1 load time. It is not an experiment
    runner and does not produce results.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    phase: str = Field(min_length=1)
    registry_version: str = Field(min_length=1)
    v1_cards_sha256: dict[str, str] = Field(
        description="mechanism_id → SHA-256 of v1 card JSON"
    )
    metric_specs: Annotated[list[MetricSpec], Field(min_length=1)]


def _compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_v1_card_sha256_map(root: Path) -> dict[str, str]:
    """Compute SHA-256 for each v1 card file.

    Returns
    -------
    dict[str, str]
        mechanism_id → SHA-256 hex string.
    """
    card_dir = root / "config" / "p06" / "cards"
    result: dict[str, str] = {}
    for card_path in sorted(card_dir.glob("M*.json")):
        mechanism_id = card_path.stem
        result[mechanism_id] = _compute_sha256(card_path)
    return result


def _normalize_metric_name(metric: str) -> str:
    """Convert a v1 card metric string to a stable metric_id.

    v1 card metrics are free-text strings like "household_consumption" or
    "tick_diagnostics.bottleneck_demand_count". We map them directly to
    metric_ids, replacing spaces with underscores.
    """
    return metric.strip().replace(" ", "_")


def card_to_metric_specs(
    mechanism_id: str,
    v1_card_path: Path,
    phase: str,
) -> list[MetricSpec]:
    """Derive typed MetricSpecs from a v1 mechanism card.

    This function is read-only: it only reads the v1 card JSON.

    Parameters
    ----------
    mechanism_id
        M1–M11.
    v1_card_path
        Path to the v1 card JSON file.
    phase
        Current phase label.

    Returns
    -------
    list[MetricSpec]
        One MetricSpec per metric declared in the card. Commodity and
        region axes are set to ``None`` (pending v2 card enrichment);
        time windows are set to the full open study window.
    """
    payload = json.loads(v1_card_path.read_text(encoding="utf-8"))
    metrics: list[str] = payload.get("metrics", [])
    specs: list[MetricSpec] = []

    # Default time window: full open study window (1957Q1–1985Q4)
    default_window = TimeWindow(
        start_quarter="1957Q1",
        end_quarter="1985Q4",
        missing_policy="abort",
    )

    for metric_str in metrics:
        metric_id = _normalize_metric_name(metric_str)

        # Determine fidelity from the card's location (v1 = F2_run by convention)
        fidelity = FidelityLevel.F2_RUN

        # Data role: metrics from v1 cards are declared at experiment level,
        # not yet mapped to historical targets (pending v2 card enrichment)
        data_role = DataRole.CANDIDATE_LINKAGE

        spec = MetricSpec(
            metric_id=f"{mechanism_id.lower()}.{metric_id}",
            table_or_sidecar="unknown",       # pending v2 enrichment
            column=metric_id,
            commodity_axis=None,
            region_axis=None,
            time_window=default_window,
            unit="unknown",                   # pending v2 enrichment
            fidelity=fidelity,
            data_role=data_role,
            validation_fidelity=ValidationFidelity.NO_COUNTERPART,
            missing_policy="abort",
            description=f"Derived from v1 card metric: {metric_str}",
        )
        specs.append(spec)

    return specs


def load_v2_card_registry(root: Path, phase: str) -> MetricSpecRegistry:
    """Build the MetricSpec registry from all v1 cards (read-only adapter).

    Parameters
    ----------
    root
        Repository root.
    phase
        Current phase label.

    Returns
    -------
    MetricSpecRegistry
        Registry containing all metric specs derived from v1 cards.
        All specs have status CANDIDATE_LINKAGE (not yet confirmed as
        having a model counterpart or a historical target mapping).
    """
    card_dir = root / "config" / "p06" / "cards"
    sha_map = load_v1_card_sha256_map(root)
    all_specs: list[MetricSpec] = []

    for mechanism_id in sorted(sha_map.keys()):
        card_path = card_dir / f"{mechanism_id}.json"
        specs = card_to_metric_specs(mechanism_id, card_path, phase)
        all_specs.extend(specs)

    return MetricSpecRegistry(
        phase=phase,
        registry_version="1.0.0",
        v1_cards_sha256=sha_map,
        metric_specs=all_specs,
    )
