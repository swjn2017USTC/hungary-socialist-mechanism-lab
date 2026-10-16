"""P07A2 §1 / H0B §5: canonical table and column registry for F2 run output.

This module maps table names to their columns, commodity axes, region axes,
and quarter ranges, and resolves the commodity-specific physical unit the
model declares for each commodity from the read-only ontology
``config/ontology/f2_v1.json``.

H0B: ``F2_TABLE_COLUMNS`` mirrors the schema the model itself declares for
its output tables -- the ``*_COLUMNS`` lists in ``hsm_lab.storage.
material_output`` / ``hsm_lab.storage.political_output`` that the writer uses
to emit the Parquet files -- and was cross-checked against the Parquet schema
of a real run. Columns a legacy card expected but the model never writes
(``political_quarters.soviet_relation_quality``, ``events.entity_id`` /
``entity_type`` / ``payload``) are gone; columns the model does write and the
registry omitted (aggregates household/plot/retail/wholesale stocks,
national_accounts inventory/residual, organization_diagnostics arrears and
expectations) are present.

The evidence package stays decoupled from the production engine: this module
reads the frozen ontology JSON, never ``hsm_lab.storage`` or the engine.
``tests/test_hist_semantic_registry.py`` is what binds the two by comparing
these lists with the writer's own column constants.

This module is read-only: it does not read run output, run the model, or
access historical targets.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Commodity and region axis descriptors for each table
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TableAxis:
    """Describes whether a table has commodity and/or region dimensions."""

    has_commodity_axis: bool = False
    has_region_axis: bool = False
    # For stage_balances: production-stage dimension
    has_stage_axis: bool = False


# ---------------------------------------------------------------------------
# Canonical F2 table registry
# ---------------------------------------------------------------------------

# All tables produced by a historical_f2_replay run with output_policy=ensemble_compact.
# Tables with 0 rows (opposition_regions, political_quarters, policy_decisions, etc.)
# are included because they may become non-empty under different scenarios.

F2_TABLES: dict[str, TableAxis] = {
    # (tick, quarter, region, commodity) tables
    "aggregates": TableAxis(has_commodity_axis=True, has_region_axis=True),
    "national_accounts": TableAxis(has_commodity_axis=True, has_region_axis=False),
    "household_budgets": TableAxis(has_commodity_axis=False, has_region_axis=True),
    "stage_balances": TableAxis(has_commodity_axis=True, has_region_axis=True, has_stage_axis=True),
    "organization_diagnostics": TableAxis(has_commodity_axis=False, has_region_axis=True),
    # (tick, quarter) tables
    "tick_diagnostics": TableAxis(has_commodity_axis=False, has_region_axis=False),
    # departments has department string axis (neither commodity nor region)
    "departments": TableAxis(has_commodity_axis=False, has_region_axis=False),
    # opposition has region axis
    "opposition_regions": TableAxis(has_commodity_axis=False, has_region_axis=True),
    # financial accounts has account_id axis
    "financial_accounts": TableAxis(has_commodity_axis=False, has_region_axis=False),
    # political (0-row in baseline)
    "political_quarters": TableAxis(has_commodity_axis=False, has_region_axis=False),
    "political_events": TableAxis(has_commodity_axis=False, has_region_axis=False),
    "information_quarters": TableAxis(has_commodity_axis=False, has_region_axis=False),
    "policy_decisions": TableAxis(has_commodity_axis=False, has_region_axis=False),
    # events
    "events": TableAxis(has_commodity_axis=False, has_region_axis=False),
}


# ---------------------------------------------------------------------------
# Known commodity IDs in F2 (from C0 manifest)
# ---------------------------------------------------------------------------

F2_COMMODITY_IDS: list[str] = [
    "g01_solid_fuels",
    "g02_oil_gas_fuels",
    "g03_electricity_heat",
    "g04_basic_metals_materials",
    "g05_chemicals_fertilizer",
    "g06_machinery_capital",
    "g07_construction",
    "g08_agricultural_raw",
    "g09_basic_food",
    "g10_animal_food",
    "g11_textiles_footwear",
    "g12_household_nondurables",
    "g13_household_durables",
    "g14_vehicles_transport_equipment",
    "g15_market_services",
    "g16_housing_public_services",
]


# ---------------------------------------------------------------------------
# Known region IDs in F2 (from C0 manifest)
# ---------------------------------------------------------------------------

F2_REGION_IDS: list[str] = [
    "budapest",
    "pest",
    "borsod_abauj_zemplen",
    "heves",
    "nograd",
    "fejer",
    "komarom",
    "veszprem",
    "gyor_sopron",
    "vas",
    "zala",
    "baranya",
    "somogy",
    "tolna",
    "hajdu_bihar",
    "szabolcs_szatmar",
    "szolnok",
    "bacs_kiskun",
    "bekes",
    "csongrad",
]


# ---------------------------------------------------------------------------
# Canonical columns per table (verified from C0 parquet inspection)
# ---------------------------------------------------------------------------

F2_TABLE_COLUMNS: dict[str, list[str]] = {
    "aggregates": [
        "tick", "quarter", "region_id", "commodity_id",
        "desired", "ordered", "ordered_gross", "unfunded",
        "allocated", "delivered", "used",
        "financial_delivery_blocked", "physical_delivery_blocked",
        "production", "production_raw", "production_ready",
        "input_open", "input_close", "output_open", "output_close",
        "wholesale_open", "wholesale_close", "retail_open", "retail_close",
        "household_desired", "household_budget_unmet",
        "household_availability_unmet",
        "plot_self_use", "plot_market_sales",
    ],
    "national_accounts": [
        "tick", "quarter", "commodity_id",
        "cmea_imports", "convertible_imports", "imports",
        "cmea_exports", "convertible_exports", "exports",
        "production", "production_raw", "production_ready", "used",
        "household_consumption", "expiry",
        "organization_input_open", "organization_input_close",
        "organization_output_open", "organization_output_close",
        "wholesale_open", "wholesale_close", "retail_open", "retail_close",
        "plot_open", "plot_close",
        "project_wip_open", "project_wip_close",
        "import_pool_open", "import_pool_close",
        "total_stock_open", "total_stock_close",
        "material_balance_residual", "material_balance_tolerance_ratio",
    ],
    "household_budgets": [
        "tick", "quarter", "region_id",
        "cash_open", "cash_close", "pre_purchase_wages",
        "plot_income_formal", "plot_income_direct", "late_wage_payment",
        "spending", "self_use_imputed", "plot_input_funding",
        "budget_available", "voluntary_saving", "forced_saving",
        "deferred_open", "deferred_close",
    ],
    "tick_diagnostics": [
        "tick", "quarter", "digest",
        "max_material_abs_residual", "max_material_tolerance_ratio",
        "max_finance_abs_residual", "max_finance_tolerance_ratio",
        "checked_cells", "bottleneck_demand_count",
        "financial_blocked_total", "forcing_segment", "expired_services",
    ],
    "departments": [
        "tick", "quarter", "department",
        "actual_use_value", "attributed_output_value",
        "service_use_productive", "service_use_household",
    ],
    "opposition_regions": [
        "tick", "quarter", "region_id",
        "network_size", "intellectual_density", "worker_linkage",
        "samizdat_capacity", "foreign_linkage", "repression_exposure",
        "perceived_efficacy", "capacity",
        "weighted_grievance", "weighted_voice", "weighted_risk",
        "weighted_exposure",
    ],
    "organization_diagnostics": [
        "tick", "quarter", "region_id", "organization_type",
        "organization_count", "capacity_sum", "capacity_mean",
        "labor_sum", "labor_mean", "target_sum", "realized_sum",
        "ordered_sum", "delivered_sum", "input_bottleneck_share",
        "credit_requested", "credit_approved", "credit_drawn",
        "investment_requested", "investment_approved", "investment_completed",
        "bailout_requested", "bailout_granted", "principal_sum",
        "wage_arrears_sum", "interest_arrears_sum", "cash_sum",
        "shortage_expectation_mean", "bailout_expectation_mean",
    ],
    "financial_accounts": [
        "tick", "quarter", "account_id", "currency", "account_label",
        "opening", "closing", "credit_drawn", "grant",
        "interest_accrued", "interest_paid", "principal_repaid", "residual",
    ],
    "political_quarters": [
        "tick", "quarter", "mode", "policy_source",
        "weight_reform_technocratic", "weight_administrative_conservative",
        "weight_social_contract_pragmatist", "weight_sectoral_industrial",
        "policy_plan_utilization", "policy_enterprise_autonomy",
        "policy_investment_intensity", "policy_industrial_priority",
        "policy_admin_price_factor", "policy_wage_factor",
        "policy_credit_fraction", "policy_budget_hardness",
        "policy_housing_factor", "policy_borrowing_factor",
        "policy_consumer_import_factor", "policy_second_economy_tolerance",
        "policy_welfare_provision", "policy_private_autonomy",
        "policy_cultural_openness", "policy_supported_boundary",
        "policy_tolerance_boundary", "policy_repression",
        "policy_information_investment",
        "elite_cohesion", "soviet_bound", "soviet_violation",
        "selected_candidate", "information_capability",
        "coalition_contributions_json",
    ],
    "information_quarters": [
        "tick", "quarter", "feature_id", "capability", "data_latency",
        "measurement_error", "forecast_accuracy", "optimization_capacity",
        "inventory_visibility", "reporting_speed", "computational_cost",
        "total_lag", "source_quarter", "truth", "noise", "bias",
        "published", "valid",
    ],
    "stage_balances": [
        "tick", "quarter", "region_id", "commodity_id", "stage",
        "opening", "closing", "receipts", "production", "used",
        "delivered_out", "expiry", "residual",
    ],
    "policy_decisions": [
        "tick", "quarter", "candidate_id", "utility",
        "binding_constraints", "contributions_json",
    ],
    "political_events": [
        "tick", "quarter", "event_id", "channel", "message_id",
        "recipient_id", "source_id", "delivery", "classification",
        "attribution",
    ],
    "events": [
        "tick", "quarter", "event_type", "details_json",
    ],
}


# ---------------------------------------------------------------------------
# Optional sidecars named by legacy cards, produced by no F2 run
# ---------------------------------------------------------------------------

# The v1 cards name these sidecars as the home of quantities they measure. No
# F2 run writes them: a run output tree holds the 14 Parquet tables above and
# nothing else. A metric bound to one of them is BLOCKED rather than read from
# a stand-in table, because summing ``financial_accounts.closing`` over every
# account is not ``money_stock.money_total_close``, and
# ``stage_balances.closing`` is not ``commodity_circuit.stock_close``.
F2_OPTIONAL_SIDECARS: dict[str, str] = {
    "money_stock": (
        "no F2 run writes a money_stock table or sidecar, so money_total_close "
        "has no producer to read"
    ),
    "commodity_circuit": (
        "no F2 run writes a commodity_circuit table or sidecar, so stock_close "
        "has no producer to read"
    ),
}


def is_optional_sidecar(name: str) -> bool:
    """True if ``name`` is a card-named sidecar that no F2 run produces."""
    return name in F2_OPTIONAL_SIDECARS


# ---------------------------------------------------------------------------
# Commodity-specific physical units (read-only ontology)
# ---------------------------------------------------------------------------

# An F2 physical quantity is denominated in the commodity's own 1960 unit, not
# in model currency and not in a base-year index. The units live in the frozen
# ontology; they are read here, never invented, so a commodity whose unit the
# ontology does not declare cannot be silently priced, normalised or summed
# with another commodity.
_ONTOLOGY_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "ontology" / "f2_v1.json"
)

# The token a MetricSpec declares when its quantity is a physical flow whose
# unit is the commodity-specific ontology unit rather than a single scalar.
# ``metric_commodity_units`` resolves it to one unit per commodity.
PHYSICAL_UNIT_TOKEN = "f2_v1_commodity_physical_unit"


@lru_cache(maxsize=1)
def load_f2_commodity_units() -> dict[str, str]:
    """Read commodity_id → physical unit from ``config/ontology/f2_v1.json``.

    Returns
    -------
    dict[str, str]
        One 1960 unit per F2 commodity, as declared by the ontology.

    Raises
    ------
    RuntimeError
        If the ontology is missing or does not declare a non-empty unit for
        every F2 commodity. The gate fails closed: a commodity without a
        declared unit must not be measured, priced or summarised.
    """
    try:
        payload = json.loads(_ONTOLOGY_PATH.read_text(encoding="utf-8"))
    except OSError as error:  # pragma: no cover - frozen repository file
        raise RuntimeError(
            f"F2 ontology {_ONTOLOGY_PATH} is unreadable: {error}"
        ) from error
    units = {
        str(entry["id"]): str(entry["unit"])
        for entry in payload.get("commodities", [])
        if entry.get("id") and entry.get("unit")
    }
    missing = [c for c in F2_COMMODITY_IDS if c not in units]
    if missing:
        raise RuntimeError(
            f"F2 ontology {_ONTOLOGY_PATH} declares no unit for {missing}"
        )
    unknown = sorted(set(units) - set(F2_COMMODITY_IDS))
    if unknown:
        raise RuntimeError(
            f"F2 ontology {_ONTOLOGY_PATH} declares commodities the F2 axis "
            f"does not hold: {unknown}"
        )
    return units


F2_COMMODITY_UNITS: dict[str, str] = load_f2_commodity_units()


def f2_commodity_unit(commodity_id: str) -> str:
    """The ontology-declared physical unit of one F2 commodity.

    Raises
    ------
    KeyError
        If the ontology declares no unit for ``commodity_id``.
    """
    try:
        return F2_COMMODITY_UNITS[commodity_id]
    except KeyError as error:
        raise KeyError(
            f"the F2 ontology declares no physical unit for commodity "
            f"{commodity_id!r}; the quantity cannot be denominated"
        ) from error


def f2_commodity_units_for(commodity_ids: list[str]) -> dict[str, str]:
    """Resolve one ontology unit per commodity, refusing unknown commodities.

    Raises
    ------
    KeyError
        If any requested commodity has no ontology-declared unit.
    """
    resolved = {commodity: f2_commodity_unit(commodity) for commodity in commodity_ids}
    validate_commodity_units(resolved)
    return resolved


def validate_commodity_units(claims: Mapping[str, str]) -> None:
    """Refuse any commodity→unit claim the ontology does not make.

    A unit claim is the one place a physical quantity can silently become a
    different one: a food quantity denominated in solid-fuel units is not the
    quantity the table holds, even though both columns are physical. Every
    producer of such a claim is checked here rather than trusted.

    Raises
    ------
    ValueError
        If a claimed commodity is unknown, or its claimed unit is not the
        ontology-declared unit for that commodity.
    """
    for commodity, claimed in claims.items():
        try:
            declared = f2_commodity_unit(commodity)
        except KeyError as error:
            raise ValueError(str(error)) from error
        if claimed != declared:
            raise ValueError(
                f"commodity {commodity!r} is declared in unit {declared!r} by the "
                f"F2 ontology, not {claimed!r}: the claimed unit belongs to a "
                "different quantity"
            )


# ---------------------------------------------------------------------------
# Pre-H0B unit declarations: revoked, kept only as a record
# ---------------------------------------------------------------------------

# H0B re-declares the unit of a physical F2 quantity as the commodity-specific
# ontology unit (05 §H0B), and a physical quantity is never denominated in
# model currency or a share. A few ``(table, column)`` pairs carried a monetary
# or share declaration in the pre-H0B P07A2 registry; those declarations were
# wrong about the quantity the model holds, so H0B **revokes** them.
#
# 05 §1.1 forbids silently rewriting past declarations, so the revoked claims
# stay on disk here as a record of what was asserted -- but they are NOT part
# of the live accepted-unit set. ``metric_enricher.metric_table_units`` builds
# that set from the model's own declarations only, so a monetary or share unit
# for one of these physical pairs is refused rather than accepted.
P07A2_HISTORICAL_PAIR_UNITS: dict[tuple[str, str], tuple[str, ...]] = {
    ("aggregates", "delivered"): ("M_forint", "share (0-1)"),
    ("national_accounts", "household_consumption"): (
        "M_forint",
        "M_forint (model currency)",
    ),
    ("financial_accounts", "closing"): ("M_forint",),
}
"""Pre-H0B unit claims, revoked. Kept as evidence, never merged into the live set."""


#: Tokens that mark a unit as a value denomination rather than a physical
#: quantity: a physical flow cannot be denominated in model currency, in a
#: share of something else, or in a dimensionless index/ratio of itself.
_MONETARY_OR_SHARE_UNIT_TOKENS: tuple[str, ...] = (
    "forint",
    "currency",
    "share",
    "index",
    "ratio",
)


def is_monetary_or_share_unit(unit: str) -> bool:
    """True for a unit token that denominates a value, not a physical quantity.

    A physical F2 quantity carries the commodity-specific ontology unit (the
    token :data:`PHYSICAL_UNIT_TOKEN`, resolved per commodity). A monetary,
    share or index/ratio token is a different quantity's unit; treating it as
    the physical pair's unit silently restates the quantity.
    """
    normalized = unit.casefold()
    return any(token in normalized for token in _MONETARY_OR_SHARE_UNIT_TOKENS)


def validate_physical_unit_claims(
    units: Mapping[tuple[str, str], frozenset[str] | set[str]],
) -> None:
    """Refuse a physical pair that also accepts a monetary or share unit.

    The accepted-unit set of a physical ``(table, column)`` pair must be
    exactly the physical token: if the pair claims the physical unit and a
    monetary/share unit at once, the model would accept a value denomination
    for a physical quantity, and the union is a silent unit bypass. Fails
    closed rather than trusting any producer of such a set.

    Raises
    ------
    ValueError
        If a pair declares :data:`PHYSICAL_UNIT_TOKEN` together with a
        monetary/share unit.
    """
    for (table, column), declared in units.items():
        if PHYSICAL_UNIT_TOKEN not in declared:
            continue
        conflicting = sorted(
            unit
            for unit in declared
            if unit != PHYSICAL_UNIT_TOKEN and is_monetary_or_share_unit(unit)
        )
        if conflicting:
            raise ValueError(
                f"physical pair {table}.{column} declares both "
                f"{PHYSICAL_UNIT_TOKEN!r} and the monetary/share unit(s) "
                f"{conflicting}: a physical quantity cannot be denominated in "
                "model currency, a share or an index"
            )


# ---------------------------------------------------------------------------
# InterventionBinding parameter paths that map to real policy columns
# ---------------------------------------------------------------------------

# These are the policy fields that appear as columns in political_quarters.parquet.
# The InterventionBinding.parameter_path uses dot notation (policy.budget_hardness)
# which maps to the policy_ column name.
POLICY_PATH_TO_COLUMN: dict[str, str] = {
    "policy.plan_utilization": "policy_plan_utilization",
    "policy.enterprise_autonomy": "policy_enterprise_autonomy",
    "policy.investment_intensity": "policy_investment_intensity",
    "policy.industrial_priority": "policy_industrial_priority",
    "policy.admin_price_factor": "policy_admin_price_factor",
    "policy.wage_factor": "policy_wage_factor",
    "policy.credit_fraction": "policy_credit_fraction",
    "policy.budget_hardness": "policy_budget_hardness",
    "policy.housing_factor": "policy_housing_factor",
    "policy.borrowing_factor": "policy_borrowing_factor",
    "policy.consumer_import_factor": "policy_consumer_import_factor",
    "policy.second_economy_tolerance": "policy_second_economy_tolerance",
    "policy.welfare_provision": "policy_welfare_provision",
    "policy.private_autonomy": "policy_private_autonomy",
    "policy.cultural_openness": "policy_cultural_openness",
    "policy.supported_boundary": "policy_supported_boundary",
    "policy.tolerance_boundary": "policy_tolerance_boundary",
    "policy.repression": "policy_repression",
    "policy.information_investment": "policy_information_investment",
}

VALID_PARAMETER_PATHS: set[str] = set(POLICY_PATH_TO_COLUMN.keys())


# ---------------------------------------------------------------------------
# Pydantic models for registry output
# ---------------------------------------------------------------------------


class TableSpec(BaseModel):
    """Canonical specification for one F2 output table."""

    model_config = ConfigDict(frozen=True)

    table_name: str = Field(min_length=1)
    has_commodity_axis: bool = False
    has_region_axis: bool = False
    has_stage_axis: bool = False
    columns: Annotated[list[str], Field(min_length=1)]
    commodity_ids: list[str] | None = Field(
        default=None,
        description="Populated if has_commodity_axis=True",
    )
    region_ids: list[str] | None = Field(
        default=None,
        description="Populated if has_region_axis=True",
    )


class TableRegistry(BaseModel):
    """Complete registry of F2 run output tables."""

    model_config = ConfigDict(frozen=True)

    tables: Annotated[list[TableSpec], Field(min_length=1)]

    def get_table(self, table_name: str) -> TableSpec | None:
        for t in self.tables:
            if t.table_name == table_name:
                return t
        return None

    def column_exists(self, table_name: str, column: str) -> bool:
        t = self.get_table(table_name)
        if t is None:
            return False
        return column in t.columns


def build_f2_table_registry() -> TableRegistry:
    """Build the canonical F2 table registry from known output tables.

    Returns
    -------
    TableRegistry
        All F2 tables with their columns and axis information.
    """
    tables: list[TableSpec] = []

    for table_name, axes in F2_TABLES.items():
        cols = F2_TABLE_COLUMNS.get(table_name, [])
        tables.append(
            TableSpec(
                table_name=table_name,
                has_commodity_axis=axes.has_commodity_axis,
                has_region_axis=axes.has_region_axis,
                has_stage_axis=axes.has_stage_axis,
                columns=cols,
                commodity_ids=F2_COMMODITY_IDS if axes.has_commodity_axis else None,
                region_ids=F2_REGION_IDS if axes.has_region_axis else None,
            )
        )

    return TableRegistry(tables=tables)


# Singleton
_F2_TABLE_REGISTRY: TableRegistry | None = None


def get_f2_table_registry() -> TableRegistry:
    """Return the singleton F2 table registry."""
    global _F2_TABLE_REGISTRY
    if _F2_TABLE_REGISTRY is None:
        _F2_TABLE_REGISTRY = build_f2_table_registry()
    return _F2_TABLE_REGISTRY
