"""H0B: 11 legacy cards, 41 real metrics, physical units and research status.

These tests cover the H0B contract (05 §H0B):

* all 11 legacy cards are registered from their real files with their frozen
  SHA-256 and their exact original metric strings, in declaration order;
* every one of the 41 declared metrics ends MAPPED or BLOCKED with a reason --
  none is dropped, paraphrased into its first component, or zero-filled;
* a physical F2 flow carries the commodity-specific ontology unit, and a
  different commodity's unit is refused;
* a metric's run observability distinguishes a missing file, a missing column,
  an empty table, an unmatched selector, an absent sidecar and a genuine zero;
* the M7--M11 negative cases keep their identity and their blocking;
* the hypothesis diffs and new-id applications stay candidate-only, and no
  record claims prior identification or research completion.

The registry checks are Git-only. The observability checks that read a real
``outputs/`` run skip (with the reason) when that run is not in the checkout.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from hsm_lab.evidence.adapter import (
    FROZEN_V1_CARD_SHA256,
    LEGACY_CARD_IDS,
    LegacyCardIdentityError,
    ObservationStatus,
    load_legacy_cards,
    observation_counts,
    observe_metric,
    observe_registry,
    register_legacy_cards,
    resolve_run_artifact,
    study_id_for,
)
from hsm_lab.evidence.metric_enricher import (
    PHYSICAL_UNIT_TOKEN,
    UNIT_MODEL_CURRENCY,
    blocked_metric_map,
    card_metric_map,
    enrich_card_metrics,
    enrich_metric_spec,
    get_blocked_metric,
    is_mapped_metric,
    is_physical_metric,
    metric_commodity_units,
    metric_components,
    metric_table_units,
    physical_aggregate_unit,
)
from hsm_lab.evidence.schemas import DataRole, ValidationFidelity
from hsm_lab.evidence.table_registry import (
    F2_COMMODITY_IDS,
    F2_COMMODITY_UNITS,
    F2_OPTIONAL_SIDECARS,
    F2_TABLE_COLUMNS,
    P07A2_HISTORICAL_PAIR_UNITS,
    f2_commodity_unit,
    f2_commodity_units_for,
    is_monetary_or_share_unit,
    validate_commodity_units,
    validate_physical_unit_claims,
)

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_RUN = ROOT / "outputs" / "hist-vnext-audit-20261015" / "C0-r1"

#: Declared metric count per legacy card, as frozen by 02/05.
CARD_METRIC_COUNTS = {
    "M1": 5, "M2": 4, "M3": 3, "M4": 4, "M5": 4, "M6": 4,
    "M7": 2, "M8": 2, "M9": 3, "M10": 4, "M11": 6,
}
#: The 17 metrics the pre-H0B map left unmapped. They may stay blocked, but
#: none may disappear and none may be renumbered onto another subject.
PRE_H0B_UNMAPPED = {
    "M7#0", "M7#1", "M8#0", "M8#1", "M9#0", "M9#1", "M9#2",
    "M10#0", "M10#1", "M10#2", "M10#3",
    "M11#0", "M11#1", "M11#2", "M11#3", "M11#4", "M11#5",
}


@pytest.fixture(scope="module")
def registry():
    return register_legacy_cards(ROOT)


def _card_payload(mechanism_id: str) -> dict:
    return json.loads(
        (ROOT / "config" / "p06" / "cards" / f"{mechanism_id}.json").read_text(
            encoding="utf-8"
        )
    )


def _write_parquet(path: Path, columns: dict[str, list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tables = {name: pa.array(values) for name, values in columns.items()}
    pq.write_table(pa.table(tables), path)


def _household_consumption_run(
    tmp_path: Path,
    *,
    values: list[float],
    commodities: list[str] | None = None,
) -> Path:
    """A minimal run tree carrying national_accounts.household_consumption."""
    run_dir = tmp_path / "run"
    goods = commodities if commodities is not None else list(F2_COMMODITY_IDS)
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_parquet(
        run_dir / "national_accounts.parquet",
        {
            "tick": list(range(len(goods))),
            "quarter": ["1957Q1"] * len(goods),
            "commodity_id": goods,
            "household_consumption": values,
        },
    )
    return run_dir


def _m1_consumption_registration(registry):
    return registry.for_card("M1")[0]


# ---------------------------------------------------------------------------
# Table registry: the model's own output schema
# ---------------------------------------------------------------------------


class TestTableRegistryMatchesModelSchema:
    """`F2_TABLE_COLUMNS` must be the schema the model actually writes."""

    def test_every_table_matches_the_writers_column_list(self) -> None:
        from hsm_lab.storage import material_output as mo
        from hsm_lab.storage import political_output as po

        expected = {
            "aggregates": mo.AGGREGATE_COLUMNS,
            "stage_balances": mo.STAGE_COLUMNS,
            "national_accounts": mo.NATIONAL_COLUMNS,
            "household_budgets": mo.BUDGET_COLUMNS,
            "organization_diagnostics": mo.ORGANIZATION_COLUMNS,
            "financial_accounts": mo.FINANCIAL_COLUMNS,
            "departments": mo.DEPARTMENT_COLUMNS,
            "tick_diagnostics": mo.DIAGNOSTIC_COLUMNS,
            "events": mo.EVENT_COLUMNS,
            "political_quarters": po.POLITICAL_QUARTER_COLUMNS,
            "opposition_regions": po.OPPOSITION_COLUMNS,
            "information_quarters": po.INFORMATION_COLUMNS,
            "policy_decisions": po.POLICY_DECISION_COLUMNS,
            "political_events": po.POLITICAL_EVENT_COLUMNS,
        }
        assert set(expected) == set(F2_TABLE_COLUMNS)
        for table, columns in expected.items():
            assert F2_TABLE_COLUMNS[table] == list(columns), (
                f"{table} registry columns differ from the writer's own list"
            )

    def test_material_balance_columns_the_registry_used_to_omit(self) -> None:
        aggregates = F2_TABLE_COLUMNS["aggregates"]
        for column in (
            "wholesale_open", "wholesale_close", "retail_open", "retail_close",
            "household_desired", "household_budget_unmet",
            "household_availability_unmet", "plot_self_use", "plot_market_sales",
        ):
            assert column in aggregates, f"aggregates.{column} is missing"
        national = F2_TABLE_COLUMNS["national_accounts"]
        for column in (
            "plot_open", "plot_close", "project_wip_open", "project_wip_close",
            "import_pool_open", "import_pool_close", "total_stock_open",
            "total_stock_close", "material_balance_residual",
            "material_balance_tolerance_ratio",
        ):
            assert column in national, f"national_accounts.{column} is missing"
        organization = F2_TABLE_COLUMNS["organization_diagnostics"]
        for column in (
            "bailout_requested", "bailout_granted", "principal_sum",
            "wage_arrears_sum", "interest_arrears_sum", "cash_sum",
            "shortage_expectation_mean", "bailout_expectation_mean",
        ):
            assert column in organization, (
                f"organization_diagnostics.{column} is missing"
            )

    def test_fictional_columns_are_gone(self) -> None:
        assert "soviet_relation_quality" not in F2_TABLE_COLUMNS["political_quarters"]
        events = F2_TABLE_COLUMNS["events"]
        for column in ("entity_id", "entity_type", "payload"):
            assert column not in events, f"events.{column} does not exist"
        assert "details_json" in events
        for column in ("soviet_bound", "soviet_violation"):
            assert column in F2_TABLE_COLUMNS["political_quarters"]

    def test_registry_matches_a_real_run_schema_if_present(self) -> None:
        if not REFERENCE_RUN.is_dir():
            pytest.skip(f"reference run {REFERENCE_RUN} is not in this checkout")
        for table, columns in F2_TABLE_COLUMNS.items():
            artifact = resolve_run_artifact(REFERENCE_RUN, table)
            assert artifact is not None, f"reference run holds no {table}"
            observed = pq.read_table(artifact).schema.names
            assert list(observed) == columns, f"{table} schema differs from registry"


# ---------------------------------------------------------------------------
# Card identity and the 41 registrations
# ---------------------------------------------------------------------------


class TestLegacyCardIdentity:
    """The registration describes these cards, byte for byte."""

    def test_eleven_cards_with_frozen_sha_and_study_map(self, registry) -> None:
        assert len(registry.cards) == 11
        assert registry.identity_map() == {
            f"M{i}": f"M{i:02d}" for i in range(1, 12)
        }
        for card in registry.cards:
            expected = FROZEN_V1_CARD_SHA256[card.mechanism_id]
            assert card.sha256 == expected
            assert hashlib.sha256(
                (ROOT / card.relative_path).read_bytes()
            ).hexdigest() == expected
        assert study_id_for("M1") == "M01"
        assert study_id_for("M10") == "M10"
        with pytest.raises(LegacyCardIdentityError):
            study_id_for("M12")

    def test_41_metrics_verbatim_and_in_declaration_order(self, registry) -> None:
        assert registry.counts()["metrics"] == 41
        for card in registry.cards:
            payload = _card_payload(card.mechanism_id)
            declared = payload["metrics"]
            registrations = registry.for_card(card.mechanism_id)
            assert len(declared) == CARD_METRIC_COUNTS[card.mechanism_id]
            assert [r.metric_index for r in registrations] == list(range(len(declared)))
            assert [r.exact_original_metric for r in registrations] == declared

    def test_the_17_pre_h0b_gaps_are_still_registered(self, registry) -> None:
        registered = {r.key for r in registry.registrations}
        assert PRE_H0B_UNMAPPED <= registered
        # each gap is either mapped or blocked, and never dropped
        for registration in registry.registrations:
            assert registration.status in {"mapped", "blocked"}
            if registration.is_blocked:
                assert registration.blocked_reason
                assert registration.spec.column == registration.exact_original_metric
                assert registration.spec.table_or_sidecar == "BLOCKED_METRIC"
                assert (
                    registration.spec.validation_fidelity
                    == ValidationFidelity.NO_COUNTERPART
                )

    def test_an_edited_metric_string_is_refused(self, tmp_path: Path) -> None:
        cards = tmp_path / "config" / "p06" / "cards"
        cards.mkdir(parents=True)
        for mechanism_id in LEGACY_CARD_IDS:
            source = ROOT / "config" / "p06" / "cards" / f"{mechanism_id}.json"
            (cards / source.name).write_bytes(source.read_bytes())
        target = cards / "M1.json"
        payload = json.loads(target.read_text(encoding="utf-8"))
        payload["metrics"][0] = "household_consumption_index"
        target.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(LegacyCardIdentityError, match="refusing to register"):
            register_legacy_cards(tmp_path)

    def test_an_unknown_card_file_is_refused(self, tmp_path: Path) -> None:
        cards = tmp_path / "config" / "p06" / "cards"
        cards.mkdir(parents=True)
        for mechanism_id in LEGACY_CARD_IDS:
            source = ROOT / "config" / "p06" / "cards" / f"{mechanism_id}.json"
            (cards / source.name).write_bytes(source.read_bytes())
        (cards / "M12.json").write_text('{"mechanism_id": "M12", "metrics": ["x"]}')
        with pytest.raises(LegacyCardIdentityError, match="does not know"):
            load_legacy_cards(tmp_path)

    def test_metric_ids_are_unique_and_never_a_parameter_path(self, registry) -> None:
        ids = [r.spec.metric_id for r in registry.registrations]
        assert len(ids) == len(set(ids))
        for metric_id in ids:
            for prefix in ("p04.", "p05.", "p06.", "parameter.", "force_", "write_"):
                assert not metric_id.startswith(prefix)

    def test_public_registry_is_the_verified_registration(self, registry) -> None:
        """``load_v2_card_registry`` is the verified registration, not a copy.

        The public entry point must not build a second, weaker registry with
        placeholder specs (``table_or_sidecar="unknown"``): it returns the same
        verified specs the H0B registration produced.
        """
        from hsm_lab.evidence.adapter import load_v2_card_registry

        public = load_v2_card_registry(ROOT, "H0B")
        assert public.v1_cards_sha256 == registry.identity_map_sha256()
        assert [spec.metric_id for spec in public.metric_specs] == [
            registration.spec.metric_id for registration in registry.registrations
        ]
        for spec in public.metric_specs:
            assert spec.table_or_sidecar != "unknown"
            assert spec.unit != "unknown"

    def test_enrich_card_metrics_keeps_one_spec_per_declared_metric(
        self, registry
    ) -> None:
        for card in registry.cards:
            payload = _card_payload(card.mechanism_id)
            specs = enrich_card_metrics(card.mechanism_id, payload["metrics"])
            assert len(specs) == len(payload["metrics"]) == CARD_METRIC_COUNTS[
                card.mechanism_id
            ]
            for spec, metric in zip(specs, payload["metrics"], strict=True):
                assert spec.missing_policy != "0"
                if spec.blocked_reason is None:
                    assert is_mapped_metric(card.mechanism_id, metric)
                else:
                    assert spec.column == metric


# ---------------------------------------------------------------------------
# Physical quantities carry the commodity's own unit
# ---------------------------------------------------------------------------


class TestPhysicalCommodityUnits:
    """A physical flow is denominated in its commodity's 1960 unit."""

    def test_m1_consumption_units_equal_the_ontology_per_commodity(
        self, registry
    ) -> None:
        units = metric_commodity_units("M1", "household_consumption")
        assert units is not None
        assert len(units) == 16
        assert units == F2_COMMODITY_UNITS
        assert units["g01_solid_fuels"] == "f2_solid_fuel_1960_unit"
        assert units["g09_basic_food"] == "f2_basic_food_1960_unit"
        assert units["g16_housing_public_services"] == "f2_public_service_1960_unit"
        registration = _m1_consumption_registration(registry)
        assert registration.commodity_units() == units

    def test_m1_consumption_is_not_denominated_in_currency(self) -> None:
        spec = enrich_metric_spec("M1", "household_consumption")
        assert spec.unit == PHYSICAL_UNIT_TOKEN
        assert spec.unit != UNIT_MODEL_CURRENCY
        assert spec.commodity_axis is not None
        assert len(spec.commodity_axis.commodities) == 16
        assert spec.data_role == DataRole.TARGET
        assert spec.validation_fidelity == ValidationFidelity.EXACT
        assert is_physical_metric("M1", "household_consumption")

    def test_m11_consumption_and_production_are_physical(self) -> None:
        volume = enrich_metric_spec(
            "M11",
            "aggregate consumer-goods volume "
            "(national_accounts.household_consumption)",
        )
        assert volume.unit == PHYSICAL_UNIT_TOKEN
        assert volume.blocked_reason is None
        production = enrich_metric_spec("M11", "national_accounts.production")
        assert production.unit == PHYSICAL_UNIT_TOKEN
        assert production.commodity_axis is not None
        assert len(production.commodity_axis.commodities) == 16
        assert production.unit != UNIT_MODEL_CURRENCY

    def test_every_physical_metric_resolves_all_commodity_units(
        self, registry
    ) -> None:
        physical = [
            r
            for r in registry.mapped()
            if r.spec.unit == PHYSICAL_UNIT_TOKEN
        ]
        assert physical, "no physical metric registered"
        for registration in physical:
            units = registration.commodity_units()
            assert units is not None
            assert set(units) == set(F2_COMMODITY_IDS)
            assert all(units.values())

    def test_non_physical_metrics_have_no_commodity_unit_map(self) -> None:
        assert metric_commodity_units("M1", "forced_saving") is None
        assert metric_commodity_units("M2", "tick_diagnostics.bottleneck_demand_count") is None
        assert not is_physical_metric("M1", "forced_saving")

    def test_a_swapped_commodity_unit_is_refused(self) -> None:
        swapped = dict(F2_COMMODITY_UNITS)
        swapped["g09_basic_food"] = F2_COMMODITY_UNITS["g01_solid_fuels"]
        with pytest.raises(ValueError, match="different quantity"):
            validate_commodity_units(swapped)
        validate_commodity_units(dict(F2_COMMODITY_UNITS))
        assert f2_commodity_unit("g09_basic_food") == "f2_basic_food_1960_unit"

    def test_an_unknown_commodity_unit_is_refused(self) -> None:
        with pytest.raises(KeyError):
            f2_commodity_units_for(["g99_unknown_commodity"])
        with pytest.raises(ValueError):
            validate_commodity_units({"g99_unknown_commodity": "whatever"})

    def test_unweighted_cross_commodity_total_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unweighted cross-commodity"):
            physical_aggregate_unit(list(F2_COMMODITY_IDS))
        assert physical_aggregate_unit(["g09_basic_food"]) == (
            f2_commodity_unit("g09_basic_food")
        )


# ---------------------------------------------------------------------------
# Observability: empty is not zero
# ---------------------------------------------------------------------------


class TestRunObservability:
    """A miss has a diagnosable reason, and none of them is a zero."""

    def test_an_empty_table_is_not_a_zero(self, tmp_path: Path, registry) -> None:
        run_dir = _household_consumption_run(tmp_path, values=[0.0] * 16)
        # keep the real schema but drop every row
        table = pq.read_table(run_dir / "national_accounts.parquet")
        pq.write_table(table.slice(0, 0), run_dir / "national_accounts.parquet")
        observation = observe_metric(run_dir, _m1_consumption_registration(registry))
        assert observation.status == ObservationStatus.TABLE_EMPTY
        assert observation.rows == 0
        assert not observation.observable
        assert observation.values is None

    def test_a_true_zero_column_is_observable_as_zero(
        self, tmp_path: Path, registry
    ) -> None:
        run_dir = _household_consumption_run(tmp_path, values=[0.0] * 16)
        observation = observe_metric(run_dir, _m1_consumption_registration(registry))
        assert observation.status == ObservationStatus.OBSERVABLE_ZERO
        assert observation.observable
        assert observation.values == (0.0,)
        assert observation.window_rows == 16

    def test_a_nonzero_column_is_observable(self, tmp_path: Path, registry) -> None:
        run_dir = _household_consumption_run(tmp_path, values=[1.5] * 16)
        observation = observe_metric(run_dir, _m1_consumption_registration(registry))
        assert observation.status == ObservationStatus.OBSERVABLE
        assert observation.values == (1.5,)

    def test_a_missing_artifact_is_reported_as_absent(
        self, tmp_path: Path, registry
    ) -> None:
        run_dir = tmp_path / "empty-run"
        run_dir.mkdir()
        observation = observe_metric(run_dir, _m1_consumption_registration(registry))
        assert observation.status == ObservationStatus.ARTIFACT_ABSENT
        assert observation.rows is None

    def test_a_missing_column_is_distinct_from_a_missing_artifact(
        self, tmp_path: Path, registry
    ) -> None:
        run_dir = tmp_path / "run"
        _write_parquet(
            run_dir / "national_accounts.parquet",
            {"tick": [0], "quarter": ["1957Q1"], "commodity_id": ["g01_solid_fuels"]},
        )
        observation = observe_metric(run_dir, _m1_consumption_registration(registry))
        assert observation.status == ObservationStatus.COLUMN_ABSENT
        assert observation.rows == 1

    def test_an_unmatched_selector_is_reported(
        self, tmp_path: Path, registry
    ) -> None:
        run_dir = _household_consumption_run(
            tmp_path, values=[1.0], commodities=["g01_solid_fuels"]
        )
        observation = observe_metric(run_dir, _m1_consumption_registration(registry))
        assert observation.status == ObservationStatus.SELECTOR_UNMATCHED
        assert "commodity_id" in observation.detail

    def test_an_absent_sidecar_is_distinct_from_a_semantic_block(
        self, tmp_path: Path, registry
    ) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        money_stock = next(
            r
            for r in registry.for_card("M5")
            if r.exact_original_metric == "money_stock.money_total_close"
        )
        assert (
            observe_metric(run_dir, money_stock).status
            == ObservationStatus.SIDECAR_ABSENT
        )
        semantic = registry.for_card("M7")[0]
        assert (
            observe_metric(run_dir, semantic).status
            == ObservationStatus.SEMANTICS_BLOCKED
        )

    def test_nonfinite_values_are_not_measurements(
        self, tmp_path: Path, registry
    ) -> None:
        run_dir = _household_consumption_run(
            tmp_path, values=[float("inf")] + [1.0] * 15
        )
        observation = observe_metric(run_dir, _m1_consumption_registration(registry))
        assert observation.status == ObservationStatus.NONFINITE_VALUES

    def test_a_null_inside_the_declared_window_is_not_a_measured_zero(
        self, tmp_path: Path, registry
    ) -> None:
        """``missing_policy=abort`` refuses a null in the declared window.

        A zero value and a missing value are different observations: a column
        that is 0 in 15 rows and null in one is not a measured zero, and the
        metric's own ``missing_policy=abort`` refuses it rather than letting the
        null ride along behind the finite values.
        """
        run_dir = _household_consumption_run(
            tmp_path, values=[0.0] * 15 + [None]
        )
        observation = observe_metric(run_dir, _m1_consumption_registration(registry))
        assert observation.status == ObservationStatus.NULL_VALUES
        assert observation.values is None
        assert not observation.observable

    def test_an_all_null_window_is_not_a_measured_zero(
        self, tmp_path: Path, registry
    ) -> None:
        run_dir = _household_consumption_run(tmp_path, values=[None] * 16)
        observation = observe_metric(run_dir, _m1_consumption_registration(registry))
        assert observation.status == ObservationStatus.NULL_VALUES
        assert observation.values is None
        assert not observation.observable

    def test_a_categorical_column_is_observed_without_float_coercion(
        self, tmp_path: Path, registry
    ) -> None:
        """A label column is observed as labels, never coerced to a number.

        ``policy_decisions.binding_constraints`` is a string column; forcing it
        through ``float`` would crash or invent a number, so its distinct labels
        are reported and ``values`` stays ``None``.
        """
        registration = next(
            r
            for r in registry.for_card("M9")
            if r.exact_original_metric == "policy_decisions.binding_constraints"
        )
        run_dir = tmp_path / "run"
        _write_parquet(
            run_dir / "policy_decisions.parquet",
            {
                "tick": [0, 1, 2],
                "quarter": ["1957Q1", "1957Q1", "1957Q1"],
                "binding_constraints": ["supply", "labour", "supply"],
            },
        )
        observation = observe_metric(run_dir, registration)
        assert observation.status == ObservationStatus.OBSERVABLE
        assert observation.labels == ("labour", "supply")
        assert observation.values is None
        assert observation.observable

    def test_a_categorical_null_in_the_window_is_not_measured(
        self, tmp_path: Path, registry
    ) -> None:
        registration = next(
            r
            for r in registry.for_card("M9")
            if r.exact_original_metric == "policy_decisions.binding_constraints"
        )
        run_dir = tmp_path / "run"
        _write_parquet(
            run_dir / "policy_decisions.parquet",
            {
                "tick": [0, 1],
                "quarter": ["1957Q1", "1957Q1"],
                "binding_constraints": ["supply", None],
            },
        )
        observation = observe_metric(run_dir, registration)
        assert observation.status == ObservationStatus.NULL_VALUES
        assert observation.labels is None
        assert not observation.observable

    def test_artifact_resolution_is_the_gates_own_resolver(
        self, tmp_path: Path
    ) -> None:
        from hsm_lab.evidence.loader import _metric_artifact_path

        run_dir = tmp_path / "run"
        (run_dir / "trajectory_tables").mkdir(parents=True)
        _write_parquet(run_dir / "trajectory_tables" / "aggregates.parquet", {"tick": [0]})
        _write_parquet(run_dir / "national_accounts.parquet", {"tick": [0]})
        (run_dir / "run_metrics.json").write_text('{"delivered_total": 1.0}')
        assert resolve_run_artifact(run_dir, "aggregates") == (
            _metric_artifact_path(run_dir, "aggregates")
        )
        assert resolve_run_artifact(run_dir, "national_accounts") == (
            _metric_artifact_path(run_dir, "national_accounts")
        )
        assert resolve_run_artifact(run_dir, "run_metrics") == (
            _metric_artifact_path(run_dir, "run_metrics")
        )
        assert resolve_run_artifact(run_dir, "never_written") is None
        assert resolve_run_artifact(run_dir, "  national_accounts  ") == (
            _metric_artifact_path(run_dir, "national_accounts")
        )

    def test_reference_run_observations_are_diagnosable(self, registry) -> None:
        if not REFERENCE_RUN.is_dir():
            pytest.skip(f"reference run {REFERENCE_RUN} is not in this checkout")
        observations = observe_registry(REFERENCE_RUN, registry)
        assert len(observations) == 41
        counts = observation_counts(observations)
        for status in observations:
            assert status.status in set(ObservationStatus)
        assert counts.get("observable", 0) + counts.get("observable_zero", 0) == 10
        assert counts.get("table_empty", 0) == 4
        assert counts.get("sidecar_absent", 0) == 4
        assert counts.get("semantics_blocked", 0) == 23
        empty = [o for o in observations if o.status == ObservationStatus.TABLE_EMPTY]
        assert all(o.values is None and not o.observable for o in empty)
        assert all("0 rows" in o.detail for o in empty)


# ---------------------------------------------------------------------------
# Selector application order and declared-datatype binding
# ---------------------------------------------------------------------------


class TestSelectorAndDatatypeBinding:
    """Selectors are applied before values; datatypes follow declared semantics."""

    def test_a_single_axis_selector_excludes_undeclared_rows(
        self, tmp_path: Path, registry
    ) -> None:
        """The one-axis case filters exactly like a joint one.

        ``M1#1 household_budgets.spending`` declares a single region axis. A
        row for a region the spec does not declare is not an observation of
        this metric: with the 20 declared regions at 0.0 and an undeclared
        region at 999.0, the declared window is a measured zero, not an
        observation carrying 999.0.
        """
        registration = registry.for_card("M1")[1]
        declared = list(registration.spec.region_axis.regions)
        run_dir = tmp_path / "run"
        _write_parquet(
            run_dir / "household_budgets.parquet",
            {
                "tick": list(range(len(declared) + 1)),
                "quarter": ["1957Q1"] * (len(declared) + 1),
                "region_id": declared + ["atlantis"],
                "spending": [0.0] * len(declared) + [999.0],
            },
        )
        observation = observe_metric(run_dir, registration)
        assert observation.status == ObservationStatus.OBSERVABLE_ZERO
        assert observation.values == (0.0,)

    def test_an_undeclared_null_cannot_unmeasure_the_declared_window(
        self, tmp_path: Path, registry
    ) -> None:
        """A null in an *unselected* row is not a null in the declared window.

        ``missing_policy=abort`` refuses a null in the declared window; a row
        the selector already excluded is not in that window, so it must not
        turn a measured zero into an unmeasured one.
        """
        registration = registry.for_card("M1")[1]
        declared = list(registration.spec.region_axis.regions)
        run_dir = tmp_path / "run"
        _write_parquet(
            run_dir / "household_budgets.parquet",
            {
                "tick": list(range(len(declared) + 1)),
                "quarter": ["1957Q1"] * (len(declared) + 1),
                "region_id": declared + ["atlantis"],
                "spending": [0.0] * len(declared) + [None],
            },
        )
        observation = observe_metric(run_dir, registration)
        assert observation.status == ObservationStatus.OBSERVABLE_ZERO
        assert observation.values == (0.0,)

    def test_a_numeric_metric_rejects_a_non_numeric_column(
        self, tmp_path: Path, registry
    ) -> None:
        """A declared quantity is not a category.

        ``M1#0 household_consumption`` declares the commodity's physical unit,
        so its column must carry quantities. A string column under it is not a
        categorical measurement of this metric: reading it as labels would
        report an unmeasured quantity as an observable one.
        """
        run_dir = _household_consumption_run(
            tmp_path, values=["not_a_quantity"] * 16
        )
        observation = observe_metric(run_dir, _m1_consumption_registration(registry))
        assert observation.status == ObservationStatus.DATATYPE_MISMATCH
        assert observation.values is None
        assert observation.labels is None
        assert not observation.observable

    def test_a_label_metric_with_a_numeric_column_is_still_read_as_labels(
        self, tmp_path: Path, registry
    ) -> None:
        """A declared label metric is never a quantity, whatever the dtype.

        The declared semantics decide: M9's binding-constraint metric keeps
        its categories even if a producer wrote codes instead of strings, and
        it is never coerced to ``float``.
        """
        registration = next(
            r
            for r in registry.for_card("M9")
            if r.exact_original_metric == "policy_decisions.binding_constraints"
        )
        run_dir = tmp_path / "run"
        _write_parquet(
            run_dir / "policy_decisions.parquet",
            {
                "tick": [0, 1, 2],
                "quarter": ["1957Q1", "1957Q1", "1957Q1"],
                "binding_constraints": [1, 2, 1],
            },
        )
        observation = observe_metric(run_dir, registration)
        assert observation.status == ObservationStatus.OBSERVABLE
        assert observation.values is None
        assert observation.labels == ("1", "2")


# ---------------------------------------------------------------------------
# M7--M11 negative cases
# ---------------------------------------------------------------------------


class TestCardNegativeCases:
    """A card's identity and its blocking survive; nothing is promoted."""

    @pytest.mark.parametrize("mechanism_id", ["M7", "M10"])
    def test_cards_with_no_mapped_metric_keep_every_original(
        self, registry, mechanism_id: str
    ) -> None:
        registrations = registry.for_card(mechanism_id)
        assert all(r.is_blocked for r in registrations)
        payload = _card_payload(mechanism_id)
        assert [r.exact_original_metric for r in registrations] == payload["metrics"]
        for registration in registrations:
            assert registration.blocked_reason
            assert registration.spec.table_or_sidecar == "BLOCKED_METRIC"

    def test_m7_refuses_a_national_scalar_as_a_region_vector(self, registry) -> None:
        reason = registry.for_card("M7")[0].blocked_reason
        assert "region" in reason
        assert "scalar" in reason
        assert registry.for_card("M7")[1].blocked_reason
        assert not any(
            r.enrichment is not None and r.enrichment.regions for r in registry.for_card("M7")
        )

    def test_m9_composite_names_the_definition_score(self, registry) -> None:
        composite = next(
            r
            for r in registry.for_card("M9")
            if r.exact_original_metric.startswith("information_quarters.data_latency")
        )
        assert composite.is_blocked
        assert "capability" in composite.blocked_reason
        components = metric_components("M9", composite.exact_original_metric)
        assert len(components) == 4
        assert any(
            c.column == "forecast_accuracy" and "not a real forecast error" in (c.note or "")
            for c in components
        )

    def test_m11_does_not_read_a_stage_table_as_a_department_split(
        self, registry
    ) -> None:
        department_item = next(
            r
            for r in registry.for_card("M11")
            if r.exact_original_metric.startswith("departments.actual_use_value")
        )
        assert department_item.is_blocked
        assert "department axis" in department_item.blocked_reason
        for registration in registry.registrations:
            enrichment = registration.enrichment
            if enrichment is not None:
                assert enrichment.table != "stage_balances"
        assert "stage" in F2_TABLE_COLUMNS["stage_balances"]

    def test_m8_mode_weight_composite_lists_every_component(self, registry) -> None:
        composite = registry.for_card("M8")[0]
        assert composite.is_blocked
        columns = {c.column for c in composite.components}
        assert {
            "weight_reform_technocratic",
            "weight_administrative_conservative",
            "weight_social_contract_pragmatist",
            "weight_sectoral_industrial",
            "selected_candidate",
        } <= columns

    def test_blocked_metrics_are_not_zero_filled(self, registry) -> None:
        for registration in registry.blocked():
            spec = registration.spec
            assert spec.blocked_reason
            assert spec.unit == "unmapped"
            assert spec.missing_policy != "0"
            assert (
                spec.validation_fidelity == ValidationFidelity.NO_COUNTERPART
            )
            assert spec.commodity_axis is None
            assert spec.region_axis is None
            assert spec.column == registration.exact_original_metric

    def test_a_c0_style_empty_political_table_is_reported_empty(
        self, registry
    ) -> None:
        if not REFERENCE_RUN.is_dir():
            pytest.skip(f"reference run {REFERENCE_RUN} is not in this checkout")
        for registration in registry.mapped():
            enrichment = registration.enrichment
            if enrichment is None or enrichment.table not in {
                "political_quarters", "information_quarters", "policy_decisions",
                "opposition_regions",
            }:
                continue
            observation = observe_metric(REFERENCE_RUN, registration)
            assert observation.status == ObservationStatus.TABLE_EMPTY
            assert observation.rows == 0


# ---------------------------------------------------------------------------
# Declared units, and the retentions H0B had to keep
# ---------------------------------------------------------------------------


class TestDeclaredUnits:
    def test_declared_units_cover_every_pair_the_metrics_bind(self) -> None:
        declared = metric_table_units()
        for key, enrichment in card_metric_map().items():
            pair = (enrichment.table, enrichment.column)
            assert declared[pair] >= {enrichment.unit}, key
        for blocked in blocked_metric_map().values():
            for component in blocked.components:
                if component.unit is None:
                    continue
                assert declared[(component.table, component.column)] >= {
                    component.unit
                }

    def test_an_undeclared_pair_stays_undeclared(self) -> None:
        # the H0A gate fails closed where the model declares no unit
        assert ("aggregates", "used") not in metric_table_units()

    def test_pre_h0b_unit_claims_are_revoked_not_live(self) -> None:
        """The pre-H0B monetary/share claims are recorded, never live.

        They stay on disk as the revoked record (05 §1.1: past declarations are
        not silently rewritten), but a physical pair's accepted-unit set must
        not contain them, or the pair would silently accept a monetary/share
        unit for a physical quantity.
        """
        assert P07A2_HISTORICAL_PAIR_UNITS, "the revoked record must stay on disk"
        declared = metric_table_units()
        for pair, units in P07A2_HISTORICAL_PAIR_UNITS.items():
            live = declared.get(pair, frozenset())
            if PHYSICAL_UNIT_TOKEN not in live:
                # Not a physical pair here (financial_accounts.closing really
                # is a currency column); nothing to revoke.
                continue
            for unit in units:
                assert unit not in live, (
                    f"physical pair {pair} still accepts the revoked unit "
                    f"{unit!r}"
                )
        assert declared[("national_accounts", "household_consumption")] == frozenset(
            {PHYSICAL_UNIT_TOKEN}
        )
        assert declared[("aggregates", "delivered")] == frozenset(
            {PHYSICAL_UNIT_TOKEN}
        )

    def test_a_physical_pair_rejects_a_monetary_or_share_unit(self) -> None:
        """A physical pair may not also accept a monetary/share unit."""
        assert is_monetary_or_share_unit("M_forint")
        assert is_monetary_or_share_unit("M_forint (model currency)")
        assert is_monetary_or_share_unit("share (0-1)")
        assert not is_monetary_or_share_unit(PHYSICAL_UNIT_TOKEN)
        with pytest.raises(ValueError, match="physical pair"):
            validate_physical_unit_claims(
                {
                    ("national_accounts", "household_consumption"): frozenset(
                        {PHYSICAL_UNIT_TOKEN, "M_forint"}
                    )
                }
            )
        # A pair that carries only the physical token is fine.
        validate_physical_unit_claims(
            {
                ("national_accounts", "household_consumption"): frozenset(
                    {PHYSICAL_UNIT_TOKEN}
                )
            }
        )

    def test_a_sidecar_metric_has_no_declared_readable_pair(self) -> None:
        declared = metric_table_units()
        sidecar_metrics = [
            ("commodity_circuit", get_blocked_metric("M2", "commodity_circuit.stock_close")),
            ("money_stock", get_blocked_metric("M5", "money_stock.money_total_close")),
            ("money_stock", get_blocked_metric("M6", "money_stock (credit/principal)")),
            ("money_stock", get_blocked_metric("M10", "money_stock.money_total_close")),
        ]
        for artifact, blocked in sidecar_metrics:
            assert blocked is not None
            assert blocked.declared_artifact == artifact
            assert artifact in F2_OPTIONAL_SIDECARS
            assert all(pair[0] != artifact for pair in declared), (
                f"a metric declares a unit for sidecar '{artifact}', which no run writes"
            )


# ---------------------------------------------------------------------------
# Hypothesis diffs, new-id applications and the research-status overlay
# ---------------------------------------------------------------------------


class TestH0BOverlays:
    def test_ontology_document_registers_every_metric_and_the_old_status(self) -> None:
        path = ROOT / "docs" / "upgrade_review" / "HIST_VNEXT" / "H0B_SEMANTIC_ONTOLOGY.md"
        document = path.read_text(encoding="utf-8")
        block = document.split("```json", 1)[1].split("```", 1)[0]
        status = json.loads(block)
        assert status["ontology_version"] == "hist_vnext_h0b_v1"
        assert status["registered_metrics"] == 41
        assert status["registered_legacy_cards"] == 11
        superseded = status["supersedes"]
        assert superseded["path"] == (
            "docs/upgrade_review/evidence/P08_DIAGNOSTIC_ONTOLOGY.md"
        )
        assert superseded["status"] == [
            "historical_draft",
            "NOT_ACCEPTED_AS_CANONICAL",
        ]
        old = ROOT / superseded["path"]
        assert hashlib.sha256(old.read_bytes()).hexdigest() == superseded["sha256"]
        for card in LEGACY_CARD_IDS:
            for index, metric in enumerate(_card_payload(card)["metrics"]):
                assert f"| {index} | `{metric}` |" in document, (
                    f"{card}#{index} '{metric}' is missing from the ontology document"
                )

    def test_hypothesis_diffs_keep_the_original_sentence_verbatim(self) -> None:
        path = ROOT / "config" / "mechanisms" / "hist_vnext_v1" / "hypothesis_diffs.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        assert len(document["cards"]) == 11
        for entry in document["cards"]:
            payload = _card_payload(entry["legacy_card_id"])
            assert entry["original_hypothesis"] == payload["hypothesis"]
            expected_sha = hashlib.sha256(
                (ROOT / entry["legacy_card_path"]).read_bytes()
            ).hexdigest()
            assert entry["legacy_card_sha256"] == expected_sha
            assert entry["p07_ontology_drift"]
            assert entry["reconciliation_decision"]
            assert entry["h0b_revision"]
            assert entry["original_number_reused_for_new_subject"] is False
            assert entry["original_manipulated_variables"] == payload[
                "manipulated_variables"
            ]
            assert entry["original_controlled_variables"] == payload[
                "controlled_variables"
            ]
            assert entry["original_falsification_criterion"] == payload[
                "falsification_criterion"
            ]
            assert entry["original_result_categories"] == payload["result_categories"]
            assert entry["original_minimum_replicates"] == payload["minimum_replicates"]
            assert entry["original_calibrated_parameter_dependencies"] == payload[
                "calibrated_parameter_dependencies"
            ]

    def test_new_id_applications_are_candidates_only(self) -> None:
        path = ROOT / "config" / "mechanisms" / "hist_vnext_v1" / "new_id_applications.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        applications = document["applications"]
        assert len(applications) == 11
        assert {a["proposed_id"] for a in applications} == {
            "M1-S1", "M2-S1", "X03", "X04", "M5-S1", "X06",
            "M4-S1", "X08", "M9-S1", "X10", "X11",
        }
        for application in applications:
            assert application["status"] == "candidate"
            assert application["creates_formal_card"] is False
            assert application["reuses_legacy_number"] is False
            assert application["parent_legacy_card_id"] in LEGACY_CARD_IDS
            assert application["change_reason"]
            assert application["preregistered_at"]
            assert application["schema_version"] == "hist_vnext_v1"

    def _overlay(self) -> dict:
        path = (
            ROOT / "studies" / "HIST_VNEXT" / "declarations"
            / "research_status_overlay.json"
        )
        return json.loads(path.read_text(encoding="utf-8"))

    def test_overlay_never_claims_completion_or_identification(self) -> None:
        overlay = self._overlay()
        assert len(overlay["records"]) == 11
        assert overlay["summary"]["research_package_complete_true"] == 0
        assert overlay["summary"]["historical_supported"] == 0
        assert overlay["summary"]["historical_identification_identified"] == 0
        assert overlay["policy"]["threshold_promotes_historical_status"] is False
        for record in overlay["records"]:
            assert record["research_package_complete"] is False
            assert record["historical_supported"] is False
            assert record["historical_identification_status"] == "UNIDENTIFIED"
            assert record["prior_identified_claim_present"] is False
            assert record["structural_result"]["status"] == "NOT_RUN"
            assert record["promotion_rules_applied"] == []

    def test_overlay_keeps_every_intent_and_source_hash(self) -> None:
        overlay = self._overlay()
        for record in overlay["records"]:
            declaration = ROOT / record["source_declaration"]["path"]
            payload = json.loads(declaration.read_text(encoding="utf-8"))
            assert record["intent"] == payload["intent"]
            assert record["source_declaration"]["sha256"] == hashlib.sha256(
                declaration.read_bytes()
            ).hexdigest()
            card = ROOT / record["source_v1_card"]["path"]
            assert record["source_v1_card"]["sha256"] == hashlib.sha256(
                card.read_bytes()
            ).hexdigest()
            assert record["source_v1_card"]["frozen_identity_map_sha256_matches"] is True

    def test_overlay_observability_frequencies_equal_the_reference_run(
        self, registry
    ) -> None:
        """Each recorded frequency is the reference run's own observation.

        The overlay's per-record ``observability_in_reference_run`` is the
        genuine frequency of ``observe_registry`` over the reference run
        (counted per legacy card), not a partial tally: the per-card
        frequencies sum to ``metrics_total``, the summary and the
        ``reference_run`` tally equal ``observation_counts``, and the run the
        frequencies were counted against is the identified artefact.
        """
        if not REFERENCE_RUN.is_dir():
            pytest.skip(f"reference run {REFERENCE_RUN} is not in this checkout")
        overlay = self._overlay()
        observations = observe_registry(REFERENCE_RUN, registry)
        per_card: dict[str, dict[str, int]] = {}
        for observation in observations:
            counts = per_card.setdefault(observation.mechanism_id, {})
            status = str(observation.status)
            counts[status] = counts.get(status, 0) + 1
        total = observation_counts(observations)
        reference = overlay["reference_run"]
        assert reference["path"] == str(REFERENCE_RUN.relative_to(ROOT))
        manifest = json.loads(
            (REFERENCE_RUN / "manifest.json").read_text(encoding="utf-8")
        )
        assert reference["run_id"] == manifest["run_id"]
        assert reference["seed"] == manifest["seed"]
        assert reference["ticks"] == manifest["ticks"]
        assert (
            reference["deterministic_replay_digest"]
            == manifest["deterministic_replay_digest"]
        )
        assert reference["registered_metrics"] == len(observations) == 41
        assert reference["observability"] == total
        assert overlay["summary"]["observability_in_reference_run"] == total
        for record in overlay["records"]:
            registration = record["technical_registration"]
            frequencies = registration["observability_in_reference_run"]
            assert frequencies == per_card[record["legacy_card_id"]], (
                f"{record['mechanism_id']} observation frequencies disagree "
                "with the reference run"
            )
            assert sum(frequencies.values()) == registration["metrics_total"]
        assert sum(
            sum(record["technical_registration"]["observability_in_reference_run"].values())
            for record in overlay["records"]
        ) == len(observations)

    def test_m01_and_m05_prior_identified_claims_are_revoked(self) -> None:
        overlay = self._overlay()
        revoked = {
            record["mechanism_id"]: record.get("revoked_claims", [])
            for record in overlay["records"]
        }
        assert set(revoked) == {f"M{i:02d}" for i in range(1, 12)}
        assert len(revoked["M01"]) == 1
        assert len(revoked["M05"]) == 1
        for study, legacy in (("M01", "M1"), ("M05", "M5")):
            claim = revoked[study][0]
            declaration = json.loads(
                (ROOT / "studies" / study / "study_decl.json").read_text(
                    encoding="utf-8"
                )
            )
            assert claim["verbatim_claim"] == declaration["declared_reason"]
            assert "identified" in claim["verbatim_claim"]
            assert claim["revoked_by_phase"] == "H0B"
            assert (
                claim["replacement_status"]["historical_identification_status"]
                == "UNIDENTIFIED"
            )
            assert claim["replacement_status"]["structural_result"] == "NOT_RUN"
            assert claim["replacement_status"]["declaration"] == "declared"
            assert legacy

    def test_revoked_prior_claims_survive_only_as_quotations(self) -> None:
        """The referenced priors are UNIDENTIFIED; 'identified' is quoted only.

        ``config/calibration/p05.json`` records the P04 behavioural priors as
        UNIDENTIFIED and prior-constrained, so the overlay's own reasoning may
        not reassert them as identified: the "identified" sentence survives
        only inside the revoked ``verbatim_claim``.
        """
        overlay = self._overlay()
        note = overlay["policy"]["prior_identification_note"]
        assert "UNIDENTIFIED" in note
        assert "prior-constrained" in note
        with_priors = {
            record["mechanism_id"]: record["prior_identification"]
            for record in overlay["records"]
            if "prior_identification" in record
        }
        assert set(with_priors) == {"M01", "M05"}
        for study, prior in with_priors.items():
            assert prior["status"] == "UNIDENTIFIED"
            assert prior["referenced_priors"]
            assert "UNIDENTIFIED" in prior["basis"]
            record = next(
                r for r in overlay["records"] if r["mechanism_id"] == study
            )
            assert "UNIDENTIFIED" in record["historical_support"]["reason"]
        for record in overlay["records"]:
            for claim in record.get("revoked_claims", []):
                # The original sentence is preserved as the quotation ...
                assert "identified" in claim["verbatim_claim"]
                # ... never restated by the revocation's own reasoning.
                assert "are identified *model* parameters" not in claim["reason"]
                assert "UNIDENTIFIED" in claim["reason"]

    def test_blocked_reason_diffs_keep_the_previous_wording(self) -> None:
        overlay = self._overlay()
        for record in overlay["records"]:
            diff = record.get("blocked_reason_diff")
            if diff is None:
                continue
            declaration = json.loads(
                (
                    ROOT / "studies" / record["mechanism_id"] / "study_decl.json"
                ).read_text(encoding="utf-8")
            )
            assert diff["verbatim_previous_reason"] == declaration["blocked_reason"]
            assert diff["h0b_reason"]
