"""P07A1: evidence identity schemas and provenance DAG.

This package provides typed schemas for ObservedState, MetricSpec,
InterventionBinding, and EvidenceRecord; a loader for evidence manifests;
a provenance DAG that anchors every record to a v1 card SHA-256; and
a v1 → v2 card adapter that exposes a MetricSpec registry without
modifying the production engine.

No production engine code is imported or modified here.
"""

from __future__ import annotations

from hsm_lab.evidence.adapter import (
    MetricSpecRegistry,
    card_to_metric_specs,
    load_v2_card_registry,
)
from hsm_lab.evidence.loader import (
    EvidenceManifest,
    EvidenceRecord,
    load_evidence_manifest,
    validate_evidence_manifest,
    validate_evidence_record,
)
from hsm_lab.evidence.provenance import (
    EvidenceDAGEdge,
    EvidenceDAGNode,
    build_card_provenance,
)
from hsm_lab.evidence.schemas import (
    CommodityAxis,
    DataRole,
    FidelityLevel,
    InterventionBinding,
    MetricSpec,
    ObservedState,
    RegionAxis,
    TimeWindow,
    ValidationFidelity,
)

__all__ = [
    # schemas
    "CommodityAxis",
    "DataRole",
    "FidelityLevel",
    "InterventionBinding",
    "MetricSpec",
    "ObservedState",
    "RegionAxis",
    "TimeWindow",
    "ValidationFidelity",
    # loader
    "EvidenceManifest",
    "EvidenceRecord",
    "load_evidence_manifest",
    "validate_evidence_record",
    "validate_evidence_manifest",
    # provenance
    "EvidenceDAGEdge",
    "EvidenceDAGNode",
    "build_card_provenance",
    # adapter
    "MetricSpecRegistry",
    "card_to_metric_specs",
    "load_v2_card_registry",
]
