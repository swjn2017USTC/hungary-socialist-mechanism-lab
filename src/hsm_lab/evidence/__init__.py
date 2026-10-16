"""P07A1–P07A2: evidence identity, schemas, and metric/intervention validation.

This package provides typed schemas for ObservedState, MetricSpec,
InterventionBinding, and EvidenceRecord; a loader for evidence manifests;
a provenance DAG that anchors every record to a v1 card SHA-256; a v1 → v2
card adapter; a canonical F2 table registry; a metric enricher that maps
v1 card metric names to typed MetricSpecs with real table/column axes; and
an InterventionBinding validator for policy parameter paths.

No production engine code is imported or modified here.
"""

from __future__ import annotations

from hsm_lab.evidence.adapter import (
    MetricSpecRegistry,
    load_v2_card_registry,
)
from hsm_lab.evidence.intervention_validator import (
    InterventionValidationError,
    get_policy_column,
    is_valid_parameter_path,
    validate_intervention_binding,
    validate_intervention_bindings,
)
from hsm_lab.evidence.loader import (
    EvidenceManifest,
    EvidenceRecord,
    load_evidence_manifest,
    validate_evidence_manifest,
    validate_evidence_record,
)
from hsm_lab.evidence.metric_enricher import (
    enrich_card_metrics,
    enrich_metric_spec,
    get_metric_enrichment,
    is_mapped_metric,
    metric_table_units,
)
from hsm_lab.evidence.provenance import (
    EvidenceDAGEdge,
    EvidenceDAGNode,
    build_card_provenance,
)
from hsm_lab.evidence.schemas import (
    CommodityAxis,
    DataRole,
    EvidenceStatus,
    FidelityLevel,
    InterventionBinding,
    MetricSpec,
    ObservedState,
    RegionAxis,
    TimeWindow,
    ValidationFidelity,
)
from hsm_lab.evidence.table_registry import (
    F2_COMMODITY_IDS,
    F2_REGION_IDS,
    F2_TABLE_COLUMNS,
    F2_TABLES,
    TableAxis,
    TableRegistry,
    TableSpec,
    build_f2_table_registry,
    get_f2_table_registry,
)

__all__ = [
    # schemas
    "CommodityAxis",
    "DataRole",
    "EvidenceStatus",
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
    "load_v2_card_registry",
    # metric enricher (P07A2)
    "enrich_card_metrics",
    "enrich_metric_spec",
    "get_metric_enrichment",
    "is_mapped_metric",
    "metric_table_units",
    # intervention validator (P07A2)
    "InterventionValidationError",
    "get_policy_column",
    "is_valid_parameter_path",
    "validate_intervention_binding",
    "validate_intervention_bindings",
    # table registry (P07A2)
    "F2_COMMODITY_IDS",
    "F2_REGION_IDS",
    "F2_TABLE_COLUMNS",
    "F2_TABLES",
    "TableAxis",
    "TableRegistry",
    "TableSpec",
    "build_f2_table_registry",
    "get_f2_table_registry",
]
