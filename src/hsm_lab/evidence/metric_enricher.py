"""P07A2 §2: metric enricher — maps v1 card metric names to typed MetricSpecs.

This module reads v1 card metric declarations and produces enriched MetricSpec
objects with real table_or_sidecar, column, commodity/region axes, unit, and
fidelity. It does NOT run experiments, does NOT read target values, and does
NOT modify the production engine.
"""

from __future__ import annotations

from hsm_lab.evidence.schemas import (
    CommodityAxis,
    DataRole,
    FidelityLevel,
    MetricSpec,
    RegionAxis,
    TimeWindow,
    ValidationFidelity,
)
from hsm_lab.evidence.table_registry import F2_COMMODITY_IDS, get_f2_table_registry

# ---------------------------------------------------------------------------
# Guard: missing_policy must NEVER be silently "0"
# ---------------------------------------------------------------------------
_MISSING_POLICY_NOT_ZERO = "abort"

# Sentinel values for a metric with no known model counterpart. H0B forbids
# dropping such metrics or zero-filling them: they are returned as MetricSpecs
# carrying an explicit ``blocked_reason``.
_BLOCKED_TABLE = "BLOCKED_METRIC"
_BLOCKED_UNIT = "unmapped"

# Default time window
_DEFAULT_WINDOW = TimeWindow(
    start_quarter="1957Q1",
    end_quarter="1985Q4",
    missing_policy=_MISSING_POLICY_NOT_ZERO,
)

# All 20 regions (for region-axis aggregation)
_ALL_REGIONS = [
    "budapest", "pest", "borsod_abauj_zemplen", "heves", "nograd",
    "fejer", "komarom", "veszprem", "gyor_sopron", "vas", "zala",
    "baranya", "somogy", "tolna", "hajdu_bihar", "szabolcs_szatmar",
    "szolnok", "bacs_kiskun", "bekes", "csongrad",
]


# ---------------------------------------------------------------------------
# Mapping: key = f"{mechanism_id}.{v1_metric_name}" → enrichment spec
# ---------------------------------------------------------------------------


def _m(mechanism_id: str, v1_metric: str) -> str:
    """Helper: build lookup key."""
    return f"{mechanism_id}.{v1_metric}"


# EnrichmentTuple: (table, column, unit, fidelity, has_comm, commodities,
# has_region, regions, aggregation, data_role, validation_fidelity)
_EnrichmentTuple = tuple[
    str,  # table
    str,  # column
    str,  # unit
    FidelityLevel,
    bool,  # has_comm
    list[str] | None,  # commodities
    bool,  # has_region
    list[str] | None,  # regions
    str | None,  # aggregation
    DataRole,
    ValidationFidelity,
]


def _build_metric_map() -> dict[str, _EnrichmentTuple]:
    """Build the metric enrichment map.

    Returns
    -------
    dict[str, tuple]
        key = "M{n}.{metric_name}" → (table, column, unit, fidelity,
        has_comm, commodities_or_None, has_region, regions_or_None,
        aggregation_or_None, data_role, validation_fidelity)
    """
    m = _m  # local alias

    return {
        # ── M1 metrics ──────────────────────────────────────────────
        # H0B: household_consumption is a preserved physical quantity
        # (flows.household_realized aggregated over regions keeps the
        # commodity dimension), not an own-base-year normalised index.
        m("M1", "household_consumption"): (
            "national_accounts", "household_consumption",
            "M_forint (model currency)", FidelityLevel.F2_RUN,
            False, None, False, None, None,
            DataRole.TARGET, ValidationFidelity.EXACT,
        ),
        m("M1", "household_budgets.spending"): (
            "household_budgets", "spending",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, True, ["all_20_regions"], "sum",
            DataRole.EXPOSURE, ValidationFidelity.PROXY,
        ),
        m("M1", "opposition_regions.weighted_grievance"): (
            "opposition_regions", "weighted_grievance",
            "dimensionless_index", FidelityLevel.F2_RUN,
            False, None, True, ["all_20_regions"], "mean",
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),
        m("M1", "political_quarters.policy_welfare_provision"): (
            "political_quarters", "policy_welfare_provision",
            "policy_scalar", FidelityLevel.F2_RUN,
            False, None, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),
        m("M1", "forced_saving"): (
            "household_budgets", "forced_saving",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, True, ["all_20_regions"], "sum",
            DataRole.EXPOSURE, ValidationFidelity.PROXY,
        ),

        # ── M2 metrics ──────────────────────────────────────────────
        m("M2", "tick_diagnostics.bottleneck_demand_count"): (
            "tick_diagnostics", "bottleneck_demand_count",
            "count", FidelityLevel.F2_RUN,
            False, None, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.PROXY,
        ),
        m("M2", "aggregates.undelivered share"): (
            "aggregates", "delivered",
            "share (0-1)", FidelityLevel.F2_RUN,
            True, F2_COMMODITY_IDS, True, ["all_20_regions"], "sum",
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),
        m("M2", "organization_diagnostics.credit_drawn/shortage_expectation_mean"): (
            "organization_diagnostics", "credit_drawn",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, True, ["all_20_regions"], "sum",
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.PROXY,
        ),
        m("M2", "commodity_circuit.stock_close"): (
            "stage_balances", "closing",
            "M_forint", FidelityLevel.F2_RUN,
            True, F2_COMMODITY_IDS, True, ["all_20_regions"], "sum",
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),

        # ── M3 metrics ──────────────────────────────────────────────
        m("M3", "organization_diagnostics.labor_mean/wage_arrears_sum"): (
            "organization_diagnostics", "labor_mean",
            "workers", FidelityLevel.F2_RUN,
            False, None, True, ["all_20_regions"], "mean",
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),
        m("M3", "national_accounts.production per worker proxy"): (
            "national_accounts", "production",
            "M_forint", FidelityLevel.F2_RUN,
            True, F2_COMMODITY_IDS, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),
        m("M3", "aggregates.household_desired vs delivered"): (
            "aggregates", "delivered",
            "M_forint", FidelityLevel.F2_RUN,
            True, F2_COMMODITY_IDS, True, ["all_20_regions"], "sum",
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),

        # ── M4 metrics ──────────────────────────────────────────────
        m("M4", "aggregates.plot_self_use/plot_market_sales"): (
            "household_budgets", "self_use_imputed",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, True, ["all_20_regions"], "sum",
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),
        m("M4", "household_budgets.plot_income_formal/plot_income_direct"): (
            "household_budgets", "plot_income_formal",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, True, ["all_20_regions"], "sum",
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),
        m("M4", "formal household_availability_unmet"): (
            "household_budgets", "budget_available",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, True, ["all_20_regions"], "sum",
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),
        m("M4", "departments.service_use_household"): (
            "departments", "service_use_household",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),

        # ── M5 metrics ──────────────────────────────────────────────
        m("M5", "organization_diagnostics.investment_approved/credit_drawn"): (
            "organization_diagnostics", "investment_approved",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, True, ["all_20_regions"], "sum",
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.PROXY,
        ),
        m("M5", "national_accounts.production/used"): (
            "national_accounts", "production",
            "M_forint", FidelityLevel.F2_RUN,
            True, F2_COMMODITY_IDS, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.PROXY,
        ),
        m("M5", "tick_diagnostics.bottleneck_demand_count"): (
            "tick_diagnostics", "bottleneck_demand_count",
            "count", FidelityLevel.F2_RUN,
            False, None, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.PROXY,
        ),
        m("M5", "money_stock.money_total_close"): (
            "financial_accounts", "closing",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),

        # ── M6 metrics ──────────────────────────────────────────────
        m("M6", "national_accounts.imports by channel"): (
            "national_accounts", "imports",
            "M_forint (admin price)", FidelityLevel.F2_RUN,
            True, F2_COMMODITY_IDS, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.PROXY,
        ),
        m("M6", "money_stock (credit/principal)"): (
            "financial_accounts", "credit_drawn",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),
        m("M6", "household_consumption"): (
            "national_accounts", "household_consumption",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, False, None, None,
            DataRole.TARGET, ValidationFidelity.NORMALIZED_INDEX,
        ),
        m("M6", "treasury_cash"): (
            "financial_accounts", "closing",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.PROXY,
        ),

        # ── M7 metrics ──────────────────────────────────────────────
        m("M7", "regional investment_intensity"): (
            "organization_diagnostics", "investment_approved",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, True, _ALL_REGIONS, "sum",
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),
        m("M7", "regional housing_factor"): (
            "household_budgets", "spending",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, True, _ALL_REGIONS, "sum",
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),

        # ── M8 metrics ──────────────────────────────────────────────
        m("M8", "political_quarters.policy_welfare_provision"): (
            "political_quarters", "policy_welfare_provision",
            "policy_scalar", FidelityLevel.F2_RUN,
            False, None, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),
        m("M8", "opposition_regions.weighted_grievance"): (
            "opposition_regions", "weighted_grievance",
            "dimensionless_index", FidelityLevel.F2_RUN,
            False, None, True, ["all_20_regions"], "mean",
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),

        # ── M9 metrics ──────────────────────────────────────────────
        m("M9", "technology.forecast_accuracy"): (
            "information_quarters", "forecast_accuracy",
            "dimensionless_ratio", FidelityLevel.F2_RUN,
            False, None, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),
        m("M9", "technology.optimization_capacity"): (
            "information_quarters", "optimization_capacity",
            "dimensionless_ratio", FidelityLevel.F2_RUN,
            False, None, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),

        # ── M10 metrics ──────────────────────────────────────────────
        m("M10", "national_accounts.imports"): (
            "national_accounts", "imports",
            "M_forint (admin price)", FidelityLevel.F2_RUN,
            True, F2_COMMODITY_IDS, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.PROXY,
        ),
        m("M10", "national_accounts.exports"): (
            "national_accounts", "exports",
            "M_forint (admin price)", FidelityLevel.F2_RUN,
            True, F2_COMMODITY_IDS, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.PROXY,
        ),

        # ── M11 metrics ──────────────────────────────────────────────
        m("M11", "departments.service_use_household"): (
            "departments", "service_use_household",
            "M_forint", FidelityLevel.F2_RUN,
            False, None, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),
        m("M11", "national_accounts.production"): (
            "national_accounts", "production",
            "M_forint", FidelityLevel.F2_RUN,
            True, F2_COMMODITY_IDS, False, None, None,
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.PROXY,
        ),
        m("M11", "aggregates.undelivered_share"): (
            "aggregates", "delivered",
            "M_forint", FidelityLevel.F2_RUN,
            True, F2_COMMODITY_IDS, True, ["all_20_regions"], "sum",
            DataRole.CANDIDATE_LINKAGE, ValidationFidelity.NO_COUNTERPART,
        ),
    }


_METRIC_MAP: dict[str, tuple[
    str, str, str, FidelityLevel,
    bool, list[str] | None,
    bool, list[str] | None, str | None,
    DataRole, ValidationFidelity,
]] = _build_metric_map()


def is_mapped_metric(mechanism_id: str, v1_metric_name: str) -> bool:
    """True if this mechanism+metric pair has a known enrichment."""
    return _m(mechanism_id, v1_metric_name) in _METRIC_MAP


def get_metric_enrichment(
    mechanism_id: str,
    v1_metric_name: str,
) -> _EnrichmentTuple | None:
    """Return the enrichment tuple for a mechanism+metric, or None."""
    return _METRIC_MAP.get(_m(mechanism_id, v1_metric_name))


def metric_table_units() -> dict[tuple[str, str], frozenset[str]]:
    """The unit(s) the model declares for each ``(table, column)`` pair.

    A MetricSpec's ``unit`` describes the quantity its ``table``/``column``
    pair carries, so the pairs the enrichment map binds are exactly the pairs
    whose unit the model declares. Consumers use this to check that a declared
    metric unit matches the quantity the table holds; a pair the map does not
    bind (a sidecar, or a column no mapped metric reads) has no declared unit.

    Returns
    -------
    dict[tuple[str, str], frozenset[str]]
        ``(table, column)`` → the units the mapped metrics declare for it.
    """
    units: dict[tuple[str, str], set[str]] = {}
    for table, column, unit, *_rest in _METRIC_MAP.values():
        units.setdefault((table, column), set()).add(unit)
    return {pair: frozenset(values) for pair, values in units.items()}


def _build_metric_id(mechanism_id: str, v1_metric_name: str) -> str:
    """Build a stable metric_id from mechanism + normalized metric name."""
    return (
        f"{mechanism_id.lower()}."
        f"{v1_metric_name.replace(' ', '_').replace('.', '_').replace('/', '_')}"
    )


def _blocked_metric_spec(
    mechanism_id: str,
    v1_metric_name: str,
) -> MetricSpec:
    """Build an explicitly blocked MetricSpec for a metric without counterpart.

    H0B: an unmapped metric MUST NOT be returned as ``None``, dropped from the
    batch, or silently filled with 0. It is returned as a MetricSpec whose
    ``blocked_reason`` records the gap and whose ``validation_fidelity`` is
    NO_COUNTERPART; the original card metric string is preserved verbatim in
    ``column``.
    """
    return MetricSpec(
        metric_id=_build_metric_id(mechanism_id, v1_metric_name),
        table_or_sidecar=_BLOCKED_TABLE,
        column=v1_metric_name,
        commodity_axis=None,
        region_axis=None,
        time_window=_DEFAULT_WINDOW,
        unit=_BLOCKED_UNIT,
        fidelity=FidelityLevel.F2_RUN,
        data_role=DataRole.CANDIDATE_LINKAGE,
        validation_fidelity=ValidationFidelity.NO_COUNTERPART,
        missing_policy=_MISSING_POLICY_NOT_ZERO,
        blocked_reason=(
            f"No known F2 model counterpart for "
            f"'{mechanism_id}.{v1_metric_name}'"
        ),
        description=(
            f"BLOCKED: v1 card metric '{v1_metric_name}' ({mechanism_id}) "
            "has no known model counterpart"
        ),
    )


def enrich_metric_spec(
    mechanism_id: str,
    v1_metric_name: str,
) -> MetricSpec:
    """Enrich one v1 card metric into a typed MetricSpec.

    A metric with no known model counterpart is returned as a blocked
    MetricSpec (``blocked_reason`` set, ``validation_fidelity`` NO_COUNTERPART)
    rather than ``None``; callers never lose the declared metric.
    Raises ValueError if the mapped table/column is invalid.
    Raises ValueError if the resulting metric_id is a forbidden parameter path.
    """
    enrichment = get_metric_enrichment(mechanism_id, v1_metric_name)
    if enrichment is None:
        return _blocked_metric_spec(mechanism_id, v1_metric_name)

    (
        table, column, unit, fidelity,
        has_comm, commodities,
        has_region, regions, aggregation,
        data_role, validation_fidelity,
    ) = enrichment

    registry = get_f2_table_registry()
    table_spec = registry.get_table(table)
    if table_spec is None:
        raise ValueError(
            f"Table '{table}' for metric '{v1_metric_name}' "
            "is not in the F2 table registry"
        )
    if column not in table_spec.columns:
        raise ValueError(
            f"Column '{column}' is not in table '{table}'. "
            f"Available: {table_spec.columns}"
        )

    # Commodity axis
    commodity_axis: CommodityAxis | None = None
    if has_comm and commodities:
        commodity_axis = CommodityAxis(
            commodities=commodities,
            unit=unit,
            source_recipe=None,
        )

    # Region axis
    region_axis: RegionAxis | None = None
    if has_region and regions:
        resolved_regions = _ALL_REGIONS if regions == ["all_20_regions"] else regions
        region_axis = RegionAxis(
            regions=resolved_regions,
            unit=unit,
            aggregation=aggregation or "sum",
        )

    # Build stable metric_id from mechanism + normalized metric name
    metric_id = _build_metric_id(mechanism_id, v1_metric_name)

    # Forbidden path check
    forbidden_prefixes = ("p04.", "p05.", "p06.", "parameter.", "force_", "write_")
    for prefix in forbidden_prefixes:
        if metric_id.startswith(prefix):
            raise ValueError(
                f"Enriched metric_id '{metric_id}' starts with forbidden prefix "
                f"'{prefix}'"
            )

    return MetricSpec(
        metric_id=metric_id,
        table_or_sidecar=table,
        column=column,
        commodity_axis=commodity_axis,
        region_axis=region_axis,
        time_window=_DEFAULT_WINDOW,
        unit=unit,
        fidelity=fidelity,
        data_role=data_role,
        validation_fidelity=validation_fidelity,
        missing_policy=_MISSING_POLICY_NOT_ZERO,
        description=f"Enriched from v1 card metric '{v1_metric_name}' via P07A2 enricher",
    )


def enrich_card_metrics(
    mechanism_id: str,
    v1_card_metrics: list[str],
) -> list[MetricSpec]:
    """Enrich all v1 card metrics for one mechanism.

    One MetricSpec is returned per declared metric, in declaration order:
    mapped metrics are enriched from the F2 registry, unmapped metrics are
    returned as blocked MetricSpecs (``blocked_reason`` set). Nothing is
    silently dropped.
    """
    return [
        enrich_metric_spec(mechanism_id, metric_name)
        for metric_name in v1_card_metrics
    ]
