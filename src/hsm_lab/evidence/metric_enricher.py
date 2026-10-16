"""P07A2 §2 / H0B §4–§5: metric enricher — v1 card metrics to typed MetricSpecs.

This module maps v1 card metric names to typed MetricSpecs with a real
``table_or_sidecar``, ``column``, commodity/region axes, unit and fidelity. It
reads only declarations: it never runs experiments, never reads target values,
and never touches the production engine.

H0B semantics
-------------
* A card metric that names **one** model quantity is MAPPED to it.
* A card metric that names several quantities (a ``/``-separated pair, a
  ``vs`` comparison, a channel split, a column group) is a **composite**: it is
  BLOCKED, with each named component recorded, because binding it to its first
  component is a paraphrase, not a mapping (05 §H0B STOP condition).
* A card metric whose quantity the model does not produce at all is BLOCKED
  with the reason (an absent sidecar, a column with no producer, a missing
  denominator/selector, no pre-registered window).
* Nothing is dropped and nothing is zero-filled: an unmapped metric is
  returned as a MetricSpec carrying ``blocked_reason``.
* A physical F2 flow (consumption, production, imports, stocks) is denominated
  in the commodity's own 1960 unit read from the frozen ontology
  ``config/ontology/f2_v1.json`` (``PHYSICAL_UNIT_TOKEN``), never in model
  currency, never as a base-year index, and never as an unweighted
  cross-commodity total (see ``physical_aggregate_unit``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hsm_lab.evidence.schemas import (
    CommodityAxis,
    DataRole,
    FidelityLevel,
    MetricSpec,
    RegionAxis,
    TimeWindow,
    ValidationFidelity,
)
from hsm_lab.evidence.table_registry import (
    F2_COMMODITY_IDS,
    PHYSICAL_UNIT_TOKEN,
    f2_commodity_unit,
    f2_commodity_units_for,
    get_f2_table_registry,
    validate_physical_unit_claims,
)

# ---------------------------------------------------------------------------
# Guard: missing_policy must NEVER be silently "0"
# ---------------------------------------------------------------------------
_MISSING_POLICY_NOT_ZERO = "abort"

# Sentinel values for a metric with no model counterpart. H0B forbids dropping
# such metrics or zero-filling them: they are returned as MetricSpecs carrying
# an explicit ``blocked_reason``.
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

# All 16 commodities (the F2 commodity axis)
_ALL_COMMODITIES = tuple(F2_COMMODITY_IDS)

# Unit vocabularies. A unit is either the commodity-physical token (resolved
# per commodity through the ontology) or one scalar the model itself declares.
UNIT_MODEL_CURRENCY = "M_forint"
UNIT_COUNT = "count"
UNIT_PERSONS = "persons"
UNIT_DIMENSIONLESS_INDEX = "dimensionless_index"
UNIT_DIMENSIONLESS_RATIO = "dimensionless_ratio"
UNIT_POLICY_SCALAR = "policy_scalar"
UNIT_MODEL_UTILITY = "model_utility"
UNIT_CONSTRAINT_LABEL = "binding_constraint_label"


# ---------------------------------------------------------------------------
# Enrichment records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricComponent:
    """One quantity a composite card metric names.

    A component is evidence that the card metric was read in full, not a
    substitute for it: the composite itself stays BLOCKED.
    """

    table: str
    column: str | None
    unit: str | None
    note: str | None = None


@dataclass(frozen=True)
class MetricEnrichment:
    """The model quantity a card metric maps to."""

    table: str
    column: str
    unit: str
    fidelity: FidelityLevel = FidelityLevel.F2_RUN
    commodities: tuple[str, ...] | None = None
    regions: tuple[str, ...] | None = None
    aggregation: str | None = None
    data_role: DataRole = DataRole.CANDIDATE_LINKAGE
    validation_fidelity: ValidationFidelity = ValidationFidelity.NO_COUNTERPART
    note: str | None = None


@dataclass(frozen=True)
class BlockedMetric:
    """A card metric with no single model counterpart, and why."""

    reason: str
    components: tuple[MetricComponent, ...] = field(default_factory=tuple)
    declared_artifact: str | None = None
    """The run artefact the card names, when it names one (a sidecar no run
    produces), so a consumer can report the missing producer rather than a
    generic block."""


# ---------------------------------------------------------------------------
# Mapping: key = f"{mechanism_id}.{exact_card_metric_string}" → enrichment
# ---------------------------------------------------------------------------


def _m(mechanism_id: str, v1_metric: str) -> str:
    """Helper: build lookup key from the mechanism and the verbatim metric."""
    return f"{mechanism_id}.{v1_metric}"


_currency = UNIT_MODEL_CURRENCY
_physical = PHYSICAL_UNIT_TOKEN

#: Metric -> the one model quantity it names (H0B §4 frozen per-card semantics).
_CARD_METRIC_MAP: dict[str, MetricEnrichment] = {
    # ── M1 (M01): social-contract ratchet ────────────────────────────────
    # household_consumption is a preserved physical quantity: the commodity
    # dimension survives the region sum, so it keeps the commodity's own 1960
    # unit instead of a model-currency or own-base-year index claim.
    _m("M1", "household_consumption"): MetricEnrichment(
        table="national_accounts",
        column="household_consumption",
        unit=_physical,
        commodities=_ALL_COMMODITIES,
        data_role=DataRole.TARGET,
        validation_fidelity=ValidationFidelity.EXACT,
        note=(
            "weighted sum of flows.household_realized per commodity "
            "(engine/material.py tallies['consumption'], written by "
            "storage/material_output.py:774): a physical flow in the "
            "commodity's own ontology unit"
        ),
    ),
    _m("M1", "household_budgets.spending"): MetricEnrichment(
        table="household_budgets",
        column="spending",
        unit=_currency,
        regions=tuple(_ALL_REGIONS),
        aggregation="sum",
        data_role=DataRole.EXPOSURE,
        validation_fidelity=ValidationFidelity.PROXY,
        note="model domestic currency, never a historical million-forint claim",
    ),
    _m("M1", "opposition_regions.weighted_grievance"): MetricEnrichment(
        table="opposition_regions",
        column="weighted_grievance",
        unit=UNIT_DIMENSIONLESS_INDEX,
        regions=tuple(_ALL_REGIONS),
        aggregation="mean",
        data_role=DataRole.CANDIDATE_LINKAGE,
        validation_fidelity=ValidationFidelity.NO_COUNTERPART,
        note="0 rows in a C0-style run: the column exists but carries no data",
    ),
    _m("M1", "political_quarters.policy_welfare_provision"): MetricEnrichment(
        table="political_quarters",
        column="policy_welfare_provision",
        unit=UNIT_POLICY_SCALAR,
        data_role=DataRole.CANDIDATE_LINKAGE,
        validation_fidelity=ValidationFidelity.NO_COUNTERPART,
        note="0 rows in a C0-style run: the column exists but carries no data",
    ),
    _m("M1", "forced_saving"): MetricEnrichment(
        table="household_budgets",
        column="forced_saving",
        unit=_currency,
        regions=tuple(_ALL_REGIONS),
        aggregation="sum",
        data_role=DataRole.EXPOSURE,
        validation_fidelity=ValidationFidelity.PROXY,
    ),

    # ── M2 (M02): soft budget and investment hunger ───────────────────────
    _m("M2", "tick_diagnostics.bottleneck_demand_count"): MetricEnrichment(
        table="tick_diagnostics",
        column="bottleneck_demand_count",
        unit=UNIT_COUNT,
        data_role=DataRole.CANDIDATE_LINKAGE,
        validation_fidelity=ValidationFidelity.PROXY,
        note="count of bottlenecked demand cells; shared with M5 and M9",
    ),

    # ── M4 (M04): second economy ─────────────────────────────────────────
    # The availability gap is a quantity of goods never delivered, not a
    # monetary budget: binding it to household_budgets.budget_available would
    # replace the card's subject with a different quantity.
    _m("M4", "formal household_availability_unmet"): MetricEnrichment(
        table="aggregates",
        column="household_availability_unmet",
        unit=_physical,
        commodities=_ALL_COMMODITIES,
        data_role=DataRole.CANDIDATE_LINKAGE,
        validation_fidelity=ValidationFidelity.NO_COUNTERPART,
        note=(
            "physical unmet household demand per commodity; NOT "
            "household_budgets.budget_available (model currency)"
        ),
    ),
    # Service use is an attributed output *value*: engine/accounting.py:2230
    # sums service_use_productive + service_use_household as value, written by
    # storage/material_output.py:1233.
    _m("M4", "departments.service_use_household"): MetricEnrichment(
        table="departments",
        column="service_use_household",
        unit=_currency,
        data_role=DataRole.CANDIDATE_LINKAGE,
        validation_fidelity=ValidationFidelity.NO_COUNTERPART,
        note="service use value (M_forint) by engine/accounting.py:2230",
    ),

    # ── M5 (M05): enterprise autonomy, two outcomes ───────────────────────
    _m("M5", "tick_diagnostics.bottleneck_demand_count"): MetricEnrichment(
        table="tick_diagnostics",
        column="bottleneck_demand_count",
        unit=UNIT_COUNT,
        data_role=DataRole.CANDIDATE_LINKAGE,
        validation_fidelity=ValidationFidelity.PROXY,
        note=(
            "same counter as M2's: a shared bottleneck count is not an "
            "independent identification of either mechanism"
        ),
    ),

    # ── M6 (M06): external debt and the social contract ───────────────────
    _m("M6", "household_consumption"): MetricEnrichment(
        table="national_accounts",
        column="household_consumption",
        unit=_physical,
        commodities=_ALL_COMMODITIES,
        data_role=DataRole.TARGET,
        validation_fidelity=ValidationFidelity.EXACT,
        note="same physical quantity as M1's household_consumption",
    ),

    # ── M8 (M08): coalition paths under crisis ───────────────────────────
    _m("M8", "policy_decisions.utility"): MetricEnrichment(
        table="policy_decisions",
        column="utility",
        unit=UNIT_MODEL_UTILITY,
        data_role=DataRole.CANDIDATE_LINKAGE,
        validation_fidelity=ValidationFidelity.NO_COUNTERPART,
        note="0 rows in a C0-style run: the column exists but carries no data",
    ),

    # ── M9 (M09): information and optimization ───────────────────────────
    _m("M9", "policy_decisions.binding_constraints"): MetricEnrichment(
        table="policy_decisions",
        column="binding_constraints",
        unit=UNIT_CONSTRAINT_LABEL,
        data_role=DataRole.CANDIDATE_LINKAGE,
        validation_fidelity=ValidationFidelity.NO_COUNTERPART,
        note="string column of binding-constraint labels; 0 rows in C0",
    ),
    _m("M9", "tick_diagnostics.bottleneck_demand_count"): MetricEnrichment(
        table="tick_diagnostics",
        column="bottleneck_demand_count",
        unit=UNIT_COUNT,
        data_role=DataRole.CANDIDATE_LINKAGE,
        validation_fidelity=ValidationFidelity.PROXY,
    ),

    # ── M11 (M11): Department I / Department II composition ───────────────
    _m(
        "M11",
        "aggregate consumer-goods volume (national_accounts.household_consumption)",
    ): MetricEnrichment(
        table="national_accounts",
        column="household_consumption",
        unit=_physical,
        commodities=_ALL_COMMODITIES,
        data_role=DataRole.TARGET,
        validation_fidelity=ValidationFidelity.EXACT,
        note="physical consumption volume per commodity, not an aggregate value",
    ),
}


#: Composite / unproducible card metrics -> reason and named components.
_BLOCKED_METRICS: dict[str, BlockedMetric] = {
    # ── M2 ───────────────────────────────────────────────────────────────
    _m("M2", "aggregates.undelivered share"): BlockedMetric(
        reason=(
            "declares a share but no denominator; binding it to the delivered "
            "quantity would replace the card's ratio with a level, and no "
            "weighted denominator exists in the model"
        ),
        components=(
            MetricComponent("aggregates", "desired", _physical),
            MetricComponent("aggregates", "delivered", _physical),
        ),
    ),
    _m("M2", "organization_diagnostics.credit_drawn/shortage_expectation_mean"): BlockedMetric(
        reason=(
            "composite of two unrelated quantities (a currency stock and a "
            "dimensionless expectation) joined by '/'; until the separator is "
            "declared to mean a ratio or a joint report, neither component may "
            "stand for the whole"
        ),
        components=(
            MetricComponent(
                "organization_diagnostics", "credit_drawn", _currency,
                "credit drawn over the quarter, M_forint",
            ),
            MetricComponent(
                "organization_diagnostics", "shortage_expectation_mean",
                UNIT_DIMENSIONLESS_RATIO,
                "mean shortage expectation per organization",
            ),
        ),
    ),
    _m("M2", "commodity_circuit.stock_close"): BlockedMetric(
        reason=(
            "no F2 run writes a commodity_circuit table or sidecar, and "
            "stage_balances.closing is not the commodity circuit's stock close"
        ),
        components=(
            MetricComponent(
                "stage_balances", "closing", _physical,
                "per-stage closing stock: a different quantity from the "
                "circuit's stock close",
            ),
        ),
        declared_artifact="commodity_circuit",
    ),

    # ── M3 ───────────────────────────────────────────────────────────────
    _m("M3", "organization_diagnostics.labor_mean/wage_arrears_sum"): BlockedMetric(
        reason=(
            "composite: the card requires both the mean labour force and the "
            "wage-arrears stock; truncating it to one component loses the "
            "discipline-versus-arrears comparison the card is about, and no "
            "declared rule combines them"
        ),
        components=(
            MetricComponent(
                "organization_diagnostics", "labor_mean", UNIT_PERSONS,
                "mean available organization labour",
            ),
            MetricComponent(
                "organization_diagnostics", "wage_arrears_sum", _currency,
                "outstanding wage arrears, model currency",
            ),
        ),
    ),
    _m("M3", "national_accounts.production per worker proxy"): BlockedMetric(
        reason=(
            "per-worker productivity needs a worker denominator comparable to "
            "the physical production numerator; the card itself calls this a "
            "proxy, and no headcount is declared alongside national_accounts "
            "production"
        ),
        components=(
            MetricComponent(
                "national_accounts", "production", _physical,
                "physical production per commodity",
            ),
            MetricComponent(
                "organization_diagnostics", "labor_mean", UNIT_PERSONS,
                "labour is per region x organization type, not national",
            ),
        ),
    ),
    _m("M3", "aggregates.household_desired vs delivered"): BlockedMetric(
        reason=(
            "the comparison needs a household-specific delivered quantity, but "
            "aggregates.delivered covers every use, so pairing it with "
            "household_desired would measure non-delivery to households with "
            "deliveries to everyone else"
        ),
        components=(
            MetricComponent("aggregates", "household_desired", _physical),
            MetricComponent(
                "aggregates", "delivered", _physical,
                "all-use deliveries, not a household counterpart",
            ),
            MetricComponent(
                "aggregates", "household_availability_unmet", _physical,
                "the household-specific unmet quantity that does exist",
            ),
        ),
    ),

    # ── M4 ───────────────────────────────────────────────────────────────
    _m("M4", "aggregates.plot_self_use/plot_market_sales"): BlockedMetric(
        reason=(
            "composite of two physical plot flows joined by '/'; both are "
            "declared components and neither may stand for the pair"
        ),
        components=(
            MetricComponent("aggregates", "plot_self_use", _physical),
            MetricComponent("aggregates", "plot_market_sales", _physical),
        ),
    ),
    _m("M4", "household_budgets.plot_income_formal/plot_income_direct"): BlockedMetric(
        reason=(
            "composite of two income channels joined by '/'; both are declared "
            "components and the model has no declared routing between them"
        ),
        components=(
            MetricComponent("household_budgets", "plot_income_formal", _currency),
            MetricComponent("household_budgets", "plot_income_direct", _currency),
        ),
    ),

    # ── M5 ───────────────────────────────────────────────────────────────
    _m("M5", "organization_diagnostics.investment_approved/credit_drawn"): BlockedMetric(
        reason=(
            "composite pairing an investment approval with a credit drawdown; "
            "binding it to the credit column alone would drop the investment "
            "outcome the card's two-outcome claim needs"
        ),
        components=(
            MetricComponent(
                "organization_diagnostics", "investment_approved", _currency,
            ),
            MetricComponent(
                "organization_diagnostics", "credit_drawn", _currency,
            ),
        ),
    ),
    _m("M5", "national_accounts.production/used"): BlockedMetric(
        reason=(
            "composite of the physical production and use flows joined by '/'; "
            "both are declared components"
        ),
        components=(
            MetricComponent("national_accounts", "production", _physical),
            MetricComponent("national_accounts", "used", _physical),
        ),
    ),
    _m("M5", "money_stock.money_total_close"): BlockedMetric(
        reason=(
            "no F2 run writes money_stock.money_total_close, and summing "
            "financial_accounts.closing over every account is not the total "
            "money stock: the account set, currency and consolidation rule are "
            "undeclared"
        ),
        components=(
            MetricComponent(
                "financial_accounts", "closing", _currency,
                "per-account closing balance, not a money aggregate",
            ),
        ),
        declared_artifact="money_stock",
    ),

    # ── M6 ───────────────────────────────────────────────────────────────
    _m("M6", "national_accounts.imports by channel"): BlockedMetric(
        reason=(
            "the card demands imports decomposed by channel; one column cannot "
            "carry the CMEA/convertible split, and substituting the total would "
            "drop exactly the channel contrast the mechanism is about"
        ),
        components=(
            MetricComponent("national_accounts", "cmea_imports", _physical),
            MetricComponent("national_accounts", "convertible_imports", _physical),
            MetricComponent("national_accounts", "imports", _physical),
        ),
    ),
    _m("M6", "money_stock (credit/principal)"): BlockedMetric(
        reason=(
            "names a sidecar no F2 run writes and pairs a credit flow with a "
            "principal stock; a single credit flow cannot stand for both"
        ),
        components=(
            MetricComponent(
                "financial_accounts", "credit_drawn", _currency,
                "per-account credit flow, not a principal stock",
            ),
            MetricComponent(
                "organization_diagnostics", "principal_sum", _currency,
                "enterprise principal stock, no historical counterpart",
            ),
        ),
        declared_artifact="money_stock",
    ),
    # financial_accounts.closing is per (account_id, currency); MetricSpec has
    # no account/currency selector axis, so binding treasury_cash to it would
    # silently sum every account.
    _m("M6", "treasury_cash"): BlockedMetric(
        reason=(
            "treasury cash is one account in one currency; MetricSpec carries "
            "no account_label/currency selector, so binding it to "
            "financial_accounts.closing would sum every account and currency"
        ),
        components=(
            MetricComponent(
                "financial_accounts", "closing", _currency,
                "requires account_label + currency selectors",
            ),
        ),
    ),

    # ── M7 ───────────────────────────────────────────────────────────────
    _m("M7", "aggregates and household_budgets by region_id"): BlockedMetric(
        reason=(
            "names a region-axis read over two tables with different measures "
            "and no metric column; a national scalar is not a 20-region vector, "
            "and no shared regional measure is declared"
        ),
        components=(
            MetricComponent(
                "aggregates", None, None,
                "region_id axis only; no column named by the card",
            ),
            MetricComponent(
                "household_budgets", None, None,
                "region_id axis only; no column named by the card",
            ),
        ),
    ),
    _m("M7", "opposition_regions by region"): BlockedMetric(
        reason=(
            "names the opposition table's region axis but no metric column, and "
            "opposition_regions carries 0 rows in a C0-style run, so an empty "
            "table would be reported as a null result"
        ),
        components=(
            MetricComponent(
                "opposition_regions", None, None,
                "region_id axis only; table is empty in C0",
            ),
        ),
    ),

    # ── M8 ───────────────────────────────────────────────────────────────
    _m("M8", "political_quarters mode weights and selected_candidate"): BlockedMetric(
        reason=(
            "composite naming four coalition weights plus a selected candidate; "
            "no single column expresses which coalition won, and the table has "
            "0 rows in a C0-style run"
        ),
        components=(
            MetricComponent(
                "political_quarters", "weight_reform_technocratic",
                UNIT_POLICY_SCALAR,
            ),
            MetricComponent(
                "political_quarters", "weight_administrative_conservative",
                UNIT_POLICY_SCALAR,
            ),
            MetricComponent(
                "political_quarters", "weight_social_contract_pragmatist",
                UNIT_POLICY_SCALAR,
            ),
            MetricComponent(
                "political_quarters", "weight_sectoral_industrial",
                UNIT_POLICY_SCALAR,
            ),
            MetricComponent(
                "political_quarters", "selected_candidate",
                UNIT_CONSTRAINT_LABEL,
                "string label of the winning candidate",
            ),
        ),
    ),

    # ── M9 ───────────────────────────────────────────────────────────────
    _m(
        "M9",
        "information_quarters.data_latency/measurement_error/forecast_accuracy"
        "/optimization_capacity",
    ): BlockedMetric(
        reason=(
            "composite of four information columns, and the card's forecast "
            "measure is a definition score (capability), not a realized "
            "prediction residual; without issued/realized pairs the research "
            "question is blocked rather than answered by the fourth column"
        ),
        components=(
            MetricComponent(
                "information_quarters", "data_latency", UNIT_DIMENSIONLESS_RATIO,
            ),
            MetricComponent(
                "information_quarters", "measurement_error",
                UNIT_DIMENSIONLESS_RATIO,
            ),
            MetricComponent(
                "information_quarters", "forecast_accuracy",
                UNIT_DIMENSIONLESS_RATIO,
                "defined as capability in the engine: not a real forecast error",
            ),
            MetricComponent(
                "information_quarters", "optimization_capacity",
                UNIT_DIMENSIONLESS_RATIO,
            ),
        ),
    ),

    # ── M10 ──────────────────────────────────────────────────────────────
    _m("M10", "national_accounts.imports/exports by channel"): BlockedMetric(
        reason=(
            "names both trade directions and both channels; four columns "
            "cannot be represented by one, and dropping the channel split "
            "removes the transmission the external-shock card measures"
        ),
        components=(
            MetricComponent("national_accounts", "cmea_imports", _physical),
            MetricComponent("national_accounts", "convertible_imports", _physical),
            MetricComponent("national_accounts", "imports", _physical),
            MetricComponent("national_accounts", "cmea_exports", _physical),
            MetricComponent("national_accounts", "convertible_exports", _physical),
            MetricComponent("national_accounts", "exports", _physical),
        ),
    ),
    _m("M10", "money_stock.money_total_close"): BlockedMetric(
        reason=(
            "no F2 run writes money_stock.money_total_close; the total money "
            "stock cannot be reconstructed from financial_accounts.closing "
            "without a declared account/currency consolidation rule"
        ),
        components=(
            MetricComponent(
                "financial_accounts", "closing", _currency,
                "per-account closing balance",
            ),
        ),
        declared_artifact="money_stock",
    ),
    _m("M10", "treasury_cash"): BlockedMetric(
        reason=(
            "treasury cash is one account in one currency and MetricSpec has no "
            "account_label/currency selector; the account is unknown, so it is "
            "not guessed"
        ),
        components=(
            MetricComponent(
                "financial_accounts", "closing", _currency,
                "requires account_label + currency selectors",
            ),
        ),
    ),
    _m("M10", "later-window aggregates.household_availability_unmet"): BlockedMetric(
        reason=(
            "the card requires a later window that was never pre-registered; "
            "choosing one after seeing the outcome would be an ex-post window"
        ),
        components=(
            MetricComponent(
                "aggregates", "household_availability_unmet", _physical,
                "the quantity itself is declared; only the window is not",
            ),
        ),
    ),

    # ── M11 ──────────────────────────────────────────────────────────────
    _m(
        "M11",
        "assortment/availability (aggregates.household_availability_unmet, "
        "tick_diagnostics.bottleneck_demand_count)",
    ): BlockedMetric(
        reason=(
            "composite pairing a physical unmet quantity with a bottleneck "
            "cell count; the two have different units and no declared "
            "combination rule"
        ),
        components=(
            MetricComponent(
                "aggregates", "household_availability_unmet", _physical,
            ),
            MetricComponent(
                "tick_diagnostics", "bottleneck_demand_count", UNIT_COUNT,
            ),
        ),
    ),
    _m("M11", "regional distribution (by region_id)"): BlockedMetric(
        reason=(
            "names a region axis but no measure; a regional distribution needs "
            "a declared allocation vector, and the model exposes no regional "
            "budget or regional delivery vector to read"
        ),
        components=(
            MetricComponent(
                "aggregates", None, None,
                "region_id axis only; no measure named by the card",
            ),
        ),
    ),
    _m(
        "M11",
        "durable waiting (aggregates.household_desired vs delivered for "
        "g13_household_durables)",
    ): BlockedMetric(
        reason=(
            "durable waiting needs a household-specific delivered series for "
            "g13; aggregates.delivered covers every use, so the waiting gap "
            "would be overstated"
        ),
        components=(
            MetricComponent(
                "aggregates", "household_desired", _physical,
                "restricted to g13_household_durables",
            ),
            MetricComponent(
                "aggregates", "delivered", _physical,
                "all-use deliveries for g13, not household-specific",
            ),
        ),
    ),
    _m(
        "M11",
        "household welfare loss (household_budgets saving/substitution columns)",
    ): BlockedMetric(
        reason=(
            "names a column group ('saving/substitution') with no single "
            "column, and the model has no substitution column to read; the "
            "saving columns alone measure saving, not welfare loss"
        ),
        components=(
            MetricComponent("household_budgets", "voluntary_saving", _currency),
            MetricComponent("household_budgets", "forced_saving", _currency),
        ),
    ),
    _m("M11", "departments.actual_use_value split by department"): BlockedMetric(
        reason=(
            "requires a department split, but MetricSpec carries no department "
            "axis; one row per department cannot be bound to a single column "
            "without silently choosing a department"
        ),
        components=(
            MetricComponent(
                "departments", "actual_use_value", _currency,
                "requires a department selector",
            ),
        ),
    ),
}


#: Non-card metric ids retained from the P07A2 registry that the evidence gate
#: still binds (they name a single real column and are asserted by
#: tests/test_metric_binding_validation.py). Legacy card *aliases* that merely
#: paraphrased a different subject are gone: a metric the card never declared
#: must not look like coverage of one it did.
_P07A2_RETAINED_METRIC_MAP: dict[str, MetricEnrichment] = {
    _m("M9", "technology.forecast_accuracy"): MetricEnrichment(
        table="information_quarters",
        column="forecast_accuracy",
        unit=UNIT_DIMENSIONLESS_RATIO,
        data_role=DataRole.CANDIDATE_LINKAGE,
        validation_fidelity=ValidationFidelity.NO_COUNTERPART,
        note=(
            "retained P07A2 id; in the engine this is a capability definition, "
            "not a realized forecast error"
        ),
    ),
    _m("M10", "national_accounts.imports"): MetricEnrichment(
        table="national_accounts",
        column="imports",
        unit=_physical,
        commodities=_ALL_COMMODITIES,
        data_role=DataRole.CANDIDATE_LINKAGE,
        validation_fidelity=ValidationFidelity.PROXY,
        note="total imports; the channel split is M10's blocked card metric",
    ),
    _m("M11", "national_accounts.production"): MetricEnrichment(
        table="national_accounts",
        column="production",
        unit=_physical,
        commodities=_ALL_COMMODITIES,
        data_role=DataRole.CANDIDATE_LINKAGE,
        validation_fidelity=ValidationFidelity.PROXY,
    ),
}


_METRIC_MAP: dict[str, MetricEnrichment] = {
    **_CARD_METRIC_MAP,
    **_P07A2_RETAINED_METRIC_MAP,
}


def card_metric_map() -> dict[str, MetricEnrichment]:
    """The card-declared metric → quantity map (read-only copy)."""
    return dict(_CARD_METRIC_MAP)


def blocked_metric_map() -> dict[str, BlockedMetric]:
    """The card-declared composite/unproducible metric → reason map."""
    return dict(_BLOCKED_METRICS)


def is_card_metric(mechanism_id: str, v1_metric_name: str) -> bool:
    """True if this exact string is declared by the named legacy card."""
    return _m(mechanism_id, v1_metric_name) in _CARD_METRIC_MAP


def is_mapped_metric(mechanism_id: str, v1_metric_name: str) -> bool:
    """True if this mechanism+metric pair has a known single counterpart."""
    return _m(mechanism_id, v1_metric_name) in _METRIC_MAP


def is_physical_metric(mechanism_id: str, v1_metric_name: str) -> bool:
    """True if the metric's quantity is physical, with a per-commodity unit."""
    enrichment = _METRIC_MAP.get(_m(mechanism_id, v1_metric_name))
    return enrichment is not None and enrichment.unit == PHYSICAL_UNIT_TOKEN


def get_metric_enrichment(
    mechanism_id: str,
    v1_metric_name: str,
) -> MetricEnrichment | None:
    """Return the enrichment for a mechanism+metric, or None."""
    return _METRIC_MAP.get(_m(mechanism_id, v1_metric_name))


def get_blocked_metric(
    mechanism_id: str,
    v1_metric_name: str,
) -> BlockedMetric | None:
    """Return the blocking reason and components for a card metric, or None."""
    return _BLOCKED_METRICS.get(_m(mechanism_id, v1_metric_name))


def metric_components(
    mechanism_id: str,
    v1_metric_name: str,
) -> tuple[MetricComponent, ...]:
    """The components a blocked card metric names (empty for mapped metrics)."""
    blocked = get_blocked_metric(mechanism_id, v1_metric_name)
    return blocked.components if blocked is not None else ()


def metric_commodity_units(
    mechanism_id: str,
    v1_metric_name: str,
) -> dict[str, str] | None:
    """Per-commodity ontology units for a physical metric, else None.

    The unit of a physical F2 flow is the *commodity's own* 1960 unit, so a
    physical metric has one unit per commodity rather than a scalar. Returns
    None for a metric that is not physical (or has no counterpart).
    """
    enrichment = _METRIC_MAP.get(_m(mechanism_id, v1_metric_name))
    if enrichment is None or enrichment.unit != PHYSICAL_UNIT_TOKEN:
        return None
    commodities = enrichment.commodities or _ALL_COMMODITIES
    # Resolving through the ontology (and validating the result) is what keeps
    # a physical metric from being denominated in another commodity's unit.
    return f2_commodity_units_for(list(commodities))


def physical_aggregate_unit(commodity_ids: list[str]) -> str:
    """The single unit a same-unit cross-commodity total may be denominated in.

    Raises
    ------
    ValueError
        If the commodities do not share one ontology unit. A cross-commodity
        total without weights would add solid fuel to housing services, so it
        is refused rather than reported as a quantity.
    """
    units = {f2_commodity_unit(commodity) for commodity in commodity_ids}
    if len(units) != 1:
        raise ValueError(
            f"commodities {list(commodity_ids)} carry {len(units)} different "
            f"physical units ({sorted(units)}); an unweighted cross-commodity "
            "total is not a quantity"
        )
    return units.pop()


def metric_table_units() -> dict[tuple[str, str], frozenset[str]]:
    """The unit(s) the model declares for each ``(table, column)`` pair.

    A MetricSpec's ``unit`` describes the quantity its ``table``/``column``
    pair carries, so the pairs the enrichment map binds are exactly the pairs
    whose unit the model declares: every mapped metric's own pair and every
    component a blocked composite names. Those are the model's *live*
    declarations.

    The pre-H0B declarations in
    :data:`hsm_lab.evidence.table_registry.P07A2_HISTORICAL_PAIR_UNITS` are
    **not** merged in: they claimed model currency or a share for physical
    quantities, and are revoked (kept only as a record). Merging them would
    let a physical pair accept a monetary unit, which the guard
    :func:`hsm_lab.evidence.table_registry.validate_physical_unit_claims`
    refuses.

    A pair nothing declares (``aggregates.used``, or a sidecar) has no declared
    unit, and a consumer must refuse a unit claim about it rather than trust it.

    Returns
    -------
    dict[tuple[str, str], frozenset[str]]
        ``(table, column)`` → the units the model declares for it.

    Raises
    ------
    ValueError
        If a physical pair would also accept a monetary or share unit, i.e. the
        live declarations contradict the model's own quantity.
    """
    units: dict[tuple[str, str], set[str]] = {}
    for enrichment in _METRIC_MAP.values():
        units.setdefault((enrichment.table, enrichment.column), set()).add(
            enrichment.unit
        )
    for blocked in _BLOCKED_METRICS.values():
        for component in blocked.components:
            # An axis-only component names no column, so it declares no pair unit.
            if component.unit is None or component.column is None:
                continue
            units.setdefault((component.table, component.column), set()).add(
                component.unit
            )
    declared = {pair: frozenset(values) for pair, values in units.items()}
    validate_physical_unit_claims(declared)
    return declared


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
    ``blocked_reason`` records the gap -- the card's own reason where the
    registered semantics know it -- and whose ``validation_fidelity`` is
    NO_COUNTERPART; the original card metric string is preserved verbatim in
    ``column``.
    """
    registered = get_blocked_metric(mechanism_id, v1_metric_name)
    if registered is None:
        reason = f"No known F2 model counterpart for '{mechanism_id}.{v1_metric_name}'"
        components: tuple[MetricComponent, ...] = ()
    else:
        reason = registered.reason
        components = registered.components
    description = (
        f"BLOCKED: v1 card metric '{v1_metric_name}' ({mechanism_id}): {reason}"
    )
    if components:
        declared = "; ".join(
            f"{component.table}.{component.column}"
            + (f" [{component.unit}]" if component.unit else "")
            + (f" ({component.note})" if component.note else "")
            for component in components
        )
        description = f"{description} | declared components: {declared}"
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
        blocked_reason=reason,
        description=description[:500],
    )


def enrich_metric_spec(
    mechanism_id: str,
    v1_metric_name: str,
) -> MetricSpec:
    """Enrich one v1 card metric into a typed MetricSpec.

    A metric with no known single model counterpart -- whether it is a
    registered composite, names an absent sidecar, or is simply unknown -- is
    returned as a blocked MetricSpec (``blocked_reason`` set,
    ``validation_fidelity`` NO_COUNTERPART) rather than ``None``; callers never
    lose the declared metric.

    Raises
    ------
    ValueError
        If a mapped table/column is not in the F2 registry, or the resulting
        metric_id is a forbidden parameter path.
    """
    enrichment = get_metric_enrichment(mechanism_id, v1_metric_name)
    if enrichment is None:
        return _blocked_metric_spec(mechanism_id, v1_metric_name)

    registry = get_f2_table_registry()
    table_spec = registry.get_table(enrichment.table)
    if table_spec is None:
        raise ValueError(
            f"Table '{enrichment.table}' for metric '{v1_metric_name}' "
            "is not in the F2 table registry"
        )
    if enrichment.column not in table_spec.columns:
        raise ValueError(
            f"Column '{enrichment.column}' is not in table '{enrichment.table}'. "
            f"Available: {table_spec.columns}"
        )

    # Commodity axis: the unit is the commodity-specific ontology unit, so the
    # axis declares the token and metric_commodity_units resolves it per good.
    commodity_axis: CommodityAxis | None = None
    if enrichment.commodities:
        commodity_axis = CommodityAxis(
            commodities=list(enrichment.commodities),
            unit=enrichment.unit,
            source_recipe=None,
        )

    # Region axis
    region_axis: RegionAxis | None = None
    if enrichment.regions:
        region_axis = RegionAxis(
            regions=list(enrichment.regions),
            unit=enrichment.unit,
            aggregation=enrichment.aggregation or "sum",
        )

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
        table_or_sidecar=enrichment.table,
        column=enrichment.column,
        commodity_axis=commodity_axis,
        region_axis=region_axis,
        time_window=_DEFAULT_WINDOW,
        unit=enrichment.unit,
        fidelity=enrichment.fidelity,
        data_role=enrichment.data_role,
        validation_fidelity=enrichment.validation_fidelity,
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
