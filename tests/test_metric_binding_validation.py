"""P07A2 regression tests: metric enrichment and intervention validation.

Tests the table registry, metric enricher, and InterventionBinding validator.
No production engine is modified; these tests use the canonical F2 table
registry derived from observed C0 run output.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from hsm_lab.evidence.intervention_validator import (
    InterventionValidationError,
    get_policy_column,
    is_valid_parameter_path,
    validate_intervention_binding,
    validate_intervention_bindings,
)
from hsm_lab.evidence.metric_enricher import (
    enrich_card_metrics,
    enrich_metric_spec,
    is_mapped_metric,
)
from hsm_lab.evidence.schemas import (
    DataRole,
    FidelityLevel,
    InterventionBinding,
    MetricSpec,
    TimeWindow,
    ValidationFidelity,
)
from hsm_lab.evidence.table_registry import (
    F2_COMMODITY_IDS,
    F2_REGION_IDS,
    F2_TABLE_COLUMNS,
    POLICY_PATH_TO_COLUMN,
    get_f2_table_registry,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Table registry tests
# ---------------------------------------------------------------------------

def test_f2_table_registry_has_all_known_tables() -> None:
    """Registry must contain all 14 F2 output tables."""
    registry = get_f2_table_registry()
    names = {t.table_name for t in registry.tables}
    expected = {
        "aggregates", "national_accounts", "household_budgets",
        "tick_diagnostics", "departments", "opposition_regions",
        "organization_diagnostics", "financial_accounts",
        "political_quarters", "information_quarters", "stage_balances",
        "policy_decisions", "political_events", "events",
    }
    assert names == expected, f"Missing tables: {expected - names}"


def test_f2_table_registry_columns_match_known_output() -> None:
    """Each table's columns must match the canonical F2 output columns."""
    registry = get_f2_table_registry()
    for table in registry.tables:
        canonical = F2_TABLE_COLUMNS.get(table.table_name, [])
        assert table.columns == canonical, (
            f"Table '{table.table_name}' columns differ from canonical"
        )


def test_f2_commodity_ids_16() -> None:
    """F2 must have exactly 16 commodity IDs."""
    assert len(F2_COMMODITY_IDS) == 16
    assert "g01_solid_fuels" in F2_COMMODITY_IDS
    assert "g16_housing_public_services" in F2_COMMODITY_IDS


def test_f2_region_ids_20() -> None:
    """F2 must have exactly 20 region IDs."""
    assert len(F2_REGION_IDS) == 20
    assert "budapest" in F2_REGION_IDS
    assert "csongrad" in F2_REGION_IDS


def test_commodity_axis_tables_have_commodity_ids() -> None:
    """Tables with has_commodity_axis=True must have commodity_ids populated."""
    registry = get_f2_table_registry()
    for table in registry.tables:
        if table.has_commodity_axis:
            assert table.commodity_ids is not None
            assert len(table.commodity_ids) == 16


def test_region_axis_tables_have_region_ids() -> None:
    """Tables with has_region_axis=True must have region_ids populated."""
    registry = get_f2_table_registry()
    for table in registry.tables:
        if table.has_region_axis:
            assert table.region_ids is not None
            assert len(table.region_ids) == 20


def test_national_accounts_has_household_consumption_column() -> None:
    """national_accounts must have household_consumption column."""
    registry = get_f2_table_registry()
    t = registry.get_table("national_accounts")
    assert t is not None
    assert "household_consumption" in t.columns
    assert "imports" in t.columns
    assert "exports" in t.columns


# ---------------------------------------------------------------------------
# Metric enricher tests
# ---------------------------------------------------------------------------

def test_m1_household_consumption_enriches_correctly() -> None:
    """M1.household_consumption → national_accounts.household_consumption.

    H0B: the original card metric is a preserved physical quantity, so the
    validation fidelity is EXACT, not a normalised index.
    """
    spec = enrich_metric_spec("M1", "household_consumption")
    assert spec is not None
    assert spec.table_or_sidecar == "national_accounts"
    assert spec.column == "household_consumption"
    assert spec.data_role == DataRole.TARGET
    assert spec.validation_fidelity == ValidationFidelity.EXACT
    assert spec.blocked_reason is None
    assert spec.missing_policy != "0"
    assert spec.fidelity == FidelityLevel.F2_RUN


def test_m1_forced_saving_enriches() -> None:
    """M1.forced_saving → household_budgets.forced_saving."""
    spec = enrich_metric_spec("M1", "forced_saving")
    assert spec is not None
    assert spec.table_or_sidecar == "household_budgets"
    assert spec.column == "forced_saving"
    assert spec.missing_policy != "0"


def test_m2_bottleneck_demand_count_enriches() -> None:
    """M2.tick_diagnostics.bottleneck_demand_count → tick_diagnostics.bottleneck_demand_count."""
    spec = enrich_metric_spec("M2", "tick_diagnostics.bottleneck_demand_count")
    assert spec is not None
    assert spec.table_or_sidecar == "tick_diagnostics"
    assert spec.column == "bottleneck_demand_count"
    assert spec.data_role == DataRole.CANDIDATE_LINKAGE


def test_m5_and_m2_same_metric_name_both_mapped() -> None:
    """Same metric name in different cards must both enrich correctly (unique keys)."""
    spec_m2 = enrich_metric_spec("M2", "tick_diagnostics.bottleneck_demand_count")
    spec_m5 = enrich_metric_spec("M5", "tick_diagnostics.bottleneck_demand_count")
    assert spec_m2 is not None
    assert spec_m5 is not None
    assert spec_m2.metric_id != spec_m5.metric_id
    # metric_id uses lowercase mechanism prefix: "m2.tick_...", "m5.tick_..."
    assert "m2" in spec_m2.metric_id
    assert "m5" in spec_m5.metric_id


def test_m9_forecast_accuracy_enriches() -> None:
    """M9.technology.forecast_accuracy → information_quarters.forecast_accuracy."""
    spec = enrich_metric_spec("M9", "technology.forecast_accuracy")
    assert spec is not None
    assert spec.table_or_sidecar == "information_quarters"
    assert spec.column == "forecast_accuracy"
    assert spec.data_role == DataRole.CANDIDATE_LINKAGE


def test_unmapped_metric_returns_blocked_spec() -> None:
    """A metric with no known counterpart must return a blocked MetricSpec.

    H0B: the declared metric is preserved with an explicit blocked_reason
    instead of being dropped as None.
    """
    spec = enrich_metric_spec("M2", "nonexistent_metric_xyz")
    assert spec is not None
    assert spec.blocked_reason is not None
    assert "nonexistent_metric_xyz" in spec.blocked_reason
    assert spec.column == "nonexistent_metric_xyz"
    assert spec.metric_id == "m2.nonexistent_metric_xyz"
    assert spec.validation_fidelity == ValidationFidelity.NO_COUNTERPART
    assert spec.missing_policy != "0"
    assert is_mapped_metric("M2", "nonexistent_metric_xyz") is False


def test_enrich_card_metrics_returns_list() -> None:
    """enrich_card_metrics must return one spec per declared metric.

    H0B: unmapped metrics are returned as blocked MetricSpecs, so the batch
    keeps all 4 declarations (3 mapped + 1 blocked).
    """
    metrics = enrich_card_metrics("M1", [
        "household_consumption",
        "household_budgets.spending",
        "forced_saving",
        "nonexistent_metric",
    ])
    assert isinstance(metrics, list)
    assert len(metrics) == 4
    # declaration order is preserved (one metric_id per declared metric)
    assert [spec.metric_id for spec in metrics] == [
        "m1.household_consumption",
        "m1.household_budgets_spending",
        "m1.forced_saving",
        "m1.nonexistent_metric",
    ]
    mapped = [spec for spec in metrics if spec.blocked_reason is None]
    blocked = [spec for spec in metrics if spec.blocked_reason is not None]
    assert len(mapped) == 3
    assert len(blocked) == 1
    # the blocked spec keeps the original card metric string verbatim
    assert blocked[0].column == "nonexistent_metric"
    assert blocked[0].validation_fidelity == ValidationFidelity.NO_COUNTERPART


def test_missing_policy_not_zero() -> None:
    """All enriched MetricSpecs (mapped and blocked) must have missing_policy != '0'."""
    test_cases = [
        ("M1", "household_consumption"),
        ("M2", "tick_diagnostics.bottleneck_demand_count"),
        ("M5", "tick_diagnostics.bottleneck_demand_count"),
        ("M9", "technology.forecast_accuracy"),
        ("M11", "national_accounts.production"),
        # blocked spec: the missing-data guard applies there too
        ("M1", "nonexistent_metric"),
    ]
    for mechanism_id, metric in test_cases:
        spec = enrich_metric_spec(mechanism_id, metric)
        assert spec.missing_policy != "0", (
            f"{mechanism_id}.{metric} has missing_policy='0'"
        )
        if spec.blocked_reason is not None:
            assert spec.validation_fidelity == ValidationFidelity.NO_COUNTERPART


def test_metric_id_not_forbidden_path() -> None:
    """Metric IDs must not start with forbidden parameter-write prefixes."""
    # Mix of mapped and unmapped card metrics — none may produce a forbidden ID
    for mechanism_id in [f"M{i}" for i in range(1, 12)]:
        for metric in [
            "household_consumption", "tick_diagnostics.bottleneck_demand_count",
            "technology.forecast_accuracy",
        ]:
            spec = enrich_metric_spec(mechanism_id, metric)
            forbidden = ("p04.", "p05.", "p06.", "parameter.", "force_", "write_")
            for prefix in forbidden:
                assert not spec.metric_id.startswith(prefix), (
                    f"metric_id '{spec.metric_id}' starts with forbidden '{prefix}'"
                )


def test_commodity_axis_populated_for_commodity_tables() -> None:
    """Enriched specs for commodity-axis tables must have commodity_axis set."""
    test_cases = [
        ("M10", "national_accounts.imports"),
        ("M11", "national_accounts.production"),
    ]
    for mechanism_id, metric in test_cases:
        spec = enrich_metric_spec(mechanism_id, metric)
        assert spec is not None
        assert spec.commodity_axis is not None
        assert len(spec.commodity_axis.commodities) == 16


def test_region_axis_populated_for_regional_tables() -> None:
    """Enriched specs for regional tables must have region_axis set."""
    spec = enrich_metric_spec("M1", "household_budgets.spending")
    assert spec is not None
    assert spec.region_axis is not None
    assert len(spec.region_axis.regions) == 20


def test_time_window_reserved_window_blocked() -> None:
    """All enriched specs must use 1957Q1–1985Q4 window."""
    spec = enrich_metric_spec("M1", "household_consumption")
    assert spec is not None
    assert spec.time_window.start_quarter == "1957Q1"
    assert spec.time_window.end_quarter == "1985Q4"
    assert spec.time_window.start_quarter < "1986Q1"


# ---------------------------------------------------------------------------
# InterventionBinding validator tests
# ---------------------------------------------------------------------------

def test_valid_intervention_binding_passes() -> None:
    """A correctly formed InterventionBinding must pass validation."""
    binding = InterventionBinding(
        intervention_id="M1.hardness_plus",
        parameter_path="policy.budget_hardness",
        baseline_value=1.0,
        intervention_value=0.5,
        application_quarter="1961Q1",
        persistence="one_shot",
        applicable_scenarios=["historical_f2_replay"],
    )
    validate_intervention_binding(binding)  # must not raise


def test_reserved_window_application_quarter_rejected() -> None:
    """application_quarter in 1986Q1+ must raise ValidationError."""
    # Pydantic's @field_validator on application_quarter fires before our
    # InterventionValidationError, so we catch ValidationError.
    with pytest.raises(ValidationError) as exc_info:
        InterventionBinding(
            intervention_id="M2.late_intervention",
            parameter_path="policy.budget_hardness",
            baseline_value=1.0,
            intervention_value=0.5,
            application_quarter="1986Q3",
            persistence="one_shot",
            applicable_scenarios=["historical_f2_replay"],
        )
    assert "1986" in str(exc_info.value)


def test_future_parameter_path_rejected() -> None:
    """parameter_path containing 'future' must raise ValidationError."""
    # Pydantic's _parameter_path_not_future validator fires first.
    with pytest.raises(ValidationError) as exc_info:
        InterventionBinding(
            intervention_id="M9.future_path",
            parameter_path="policy.future_budget",
            baseline_value=1.0,
            intervention_value=0.5,
            application_quarter="1961Q1",
            persistence="one_shot",
            applicable_scenarios=["historical_f2_replay"],
        )
    assert "future" in str(exc_info.value).lower()


def test_unknown_parameter_path_rejected() -> None:
    """parameter_path not in the known policy set must raise."""
    binding = InterventionBinding(
        intervention_id="M2.unknown_path",
        parameter_path="policy.unknown_parameter_xyz",
        baseline_value=1.0,
        intervention_value=0.5,
        application_quarter="1961Q1",
        persistence="one_shot",
        applicable_scenarios=["historical_f2_replay"],
    )
    with pytest.raises(InterventionValidationError) as exc_info:
        validate_intervention_binding(binding)
    assert "not a known policy path" in str(exc_info.value)


def test_valid_parameter_paths_all_recognized() -> None:
    """All 20 policy paths in POLICY_PATH_TO_COLUMN must be valid."""
    for path in POLICY_PATH_TO_COLUMN:
        assert is_valid_parameter_path(path)
        col = get_policy_column(path)
        assert col is not None
        assert isinstance(col, str)


def test_policy_column_exists_in_registry() -> None:
    """Each mapped policy column must exist in political_quarters."""
    registry = get_f2_table_registry()
    t = registry.get_table("political_quarters")
    assert t is not None
    for path, col in POLICY_PATH_TO_COLUMN.items():
        assert col in t.columns, (
            f"Column '{col}' from path '{path}' not in political_quarters"
        )


def test_all_v1_card_intervention_paths_are_valid() -> None:
    """All intervention paths declared in v1 cards must be valid policy paths.

    Note: bailout_envelope_fraction and credit_envelope_fraction are in the v1
    M2 card but are NOT columns in political_quarters; they are BLOCKED
    interventions that require separate engine parameterisation.
    """
    # From v1 cards: M1 uses welfare_provision and consumer_import_factor
    # M2 uses budget_hardness, credit_fraction (bailout/credit_envelope BLOCKED)
    # M3 uses wage_factor, plan_utilization
    # M5 uses enterprise_autonomy, budget_hardness
    # etc.
    v1_card_intervention_paths = [
        "policy.welfare_provision",
        "policy.consumer_import_factor",
        "policy.budget_hardness",
        "policy.credit_fraction",
        # "policy.bailout_envelope_fraction",  # BLOCKED — not in political_quarters
        # "policy.credit_envelope_fraction",   # BLOCKED — not in political_quarters
        "policy.wage_factor",
        "policy.plan_utilization",
        "policy.enterprise_autonomy",
        "policy.borrowing_factor",
        "policy.second_economy_tolerance",
        "policy.private_autonomy",
    ]
    for path in v1_card_intervention_paths:
        assert is_valid_parameter_path(path), (
            f"v1 card intervention path '{path}' is not a valid policy path"
        )


def test_validate_intervention_bindings_all_pass() -> None:
    """A list of valid bindings must all pass."""
    bindings = [
        InterventionBinding(
            intervention_id="M1.cut_1961",
            parameter_path="policy.welfare_provision",
            baseline_value=1.0,
            intervention_value=0.8,
            application_quarter="1961Q1",
            persistence="one_shot",
            applicable_scenarios=["historical_f2_replay"],
        ),
        InterventionBinding(
            intervention_id="M1.cut_1967",
            parameter_path="policy.welfare_provision",
            baseline_value=1.0,
            intervention_value=0.8,
            application_quarter="1967Q1",
            persistence="one_shot",
            applicable_scenarios=["historical_f2_replay"],
        ),
    ]
    result = validate_intervention_bindings(bindings)
    assert result == bindings


def test_validate_intervention_bindings_stops_on_first_error() -> None:
    """If any binding fails, the first error must be raised."""
    bindings = [
        InterventionBinding(
            intervention_id="M1.cut_1961",
            parameter_path="policy.welfare_provision",
            baseline_value=1.0,
            intervention_value=0.8,
            application_quarter="1961Q1",
            persistence="one_shot",
            applicable_scenarios=["historical_f2_replay"],
        ),
        InterventionBinding(
            intervention_id="M2.bad_intervention",
            parameter_path="policy.unknown",
            baseline_value=1.0,
            intervention_value=0.5,
            application_quarter="1961Q1",
            persistence="one_shot",
            applicable_scenarios=["historical_f2_replay"],
        ),
    ]
    with pytest.raises(InterventionValidationError) as exc_info:
        validate_intervention_bindings(bindings)
    assert "unknown" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Guard: missing_policy != "0"
# ---------------------------------------------------------------------------

def test_missing_policy_zero_rejected_in_schema() -> None:
    """MetricSpec with missing_policy='0' must raise via Pydantic validator."""
    # The schema itself uses Field(min_length=1) for missing_policy,
    # but we additionally verify it cannot be "0" (silently filling zeros is
    # forbidden by the design). We test that the schema rejects empty/zero.
    with pytest.raises(ValidationError):
        MetricSpec(
            metric_id="M1.test_zero_policy",
            table_or_sidecar="national_accounts",
            column="household_consumption",
            time_window=TimeWindow(
                start_quarter="1957Q1",
                end_quarter="1985Q4",
                missing_policy="0",
            ),
            unit="M_forint",
            fidelity=FidelityLevel.F2_RUN,
            data_role=DataRole.CANDIDATE_LINKAGE,
            validation_fidelity=ValidationFidelity.NORMALIZED_INDEX,
            missing_policy="0",  # Must not be silently填0
        )
