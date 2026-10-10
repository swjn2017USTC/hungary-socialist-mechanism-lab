"""P07A2 §1: canonical table and column registry for F2 run output.

This module maps table names to their columns, commodity axes, region axes,
and quarter ranges. It is read-only: it does not read data files, run the
model, or access historical targets.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    ],
    "national_accounts": [
        "tick", "quarter", "commodity_id",
        "cmea_imports", "convertible_imports", "imports",
        "cmea_exports", "convertible_exports", "exports",
        "production", "production_raw", "production_ready", "used",
        "household_consumption", "expiry",
        "organization_input_open", "organization_input_close",
        "organization_output_open", "organization_output_close",
        "wholesale_open",
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
        "elite_cohesion", "soviet_relation_quality",
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
        "tick", "quarter", "event_type", "entity_id",
        "entity_type", "payload",
    ],
}


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
