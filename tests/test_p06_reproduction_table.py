"""P06 target comparison uses a predeclared crosswalk and annual index normalization."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import polars as pl
import pytest
import yaml

from hsm_lab.calibration.reproduction_table import (
    annual_household_consumption_index,
    annual_price_weighted_trade_indices,
    annual_price_weighted_trade_values,
    index_year_is_informative,
    load_reproduction_crosswalk,
)
from hsm_lab.contract.schemas import ConfigError

ROOT = Path(__file__).resolve().parents[1]


def _unlisted_inert_arms(arms: list[dict], declared: set[str]) -> set[str]:
    control = next(
        arm for arm in arms if arm["family"] == "political" and arm["arm_id"] == "control"
    )
    return {
        arm["arm_id"]
        for arm in arms
        if arm["family"] == "political"
        and arm["arm_id"] != "control"
        and arm["metrics"] == control["metrics"]
        and arm["arm_id"] not in declared
    }


def test_political_arms_matching_every_reported_metric_are_declared_inert() -> None:
    report = (ROOT / "docs/phases/P06_POLITICAL_COUNTERFACTUAL.md").read_text()
    front_matter = re.match(r"^---\n(.*?)\n---\n", report, re.DOTALL)
    assert front_matter is not None
    declaration = yaml.safe_load(front_matter.group(1))
    inert_arms = set(declaration["inert_arms"])
    summary_path = ROOT / "outputs/p06-arms/summary.json"
    if not summary_path.exists():
        pytest.skip("local P06 arm summary is not present in this checkout")
    arms = json.loads(summary_path.read_text())["arms"]
    assert not _unlisted_inert_arms(arms, inert_arms)


def test_reproduction_crosswalk_covers_exactly_the_admitted_target_variables() -> None:
    crosswalk = load_reproduction_crosswalk(ROOT)
    statuses = [entry["status"] for entry in crosswalk["entries"]]
    assert len(crosswalk["entries"]) == 14
    assert set(statuses) <= {"mapped", "no_counterpart", "blocked"}
    for entry in crosswalk["entries"]:
        if entry["status"] == "mapped":
            assert str(entry.get("comparison_grade", "")).strip()
            assert entry.get("source") not in (None, "", [], {})
            assert entry.get("comparison_window") not in (None, "", [], {})
            assert str(entry.get("error_tolerance", "")).strip()
        if entry.get("allocation_assumed") or entry.get("comparison_grade") == "allocation_assumed":
            artifacts = entry.get("source", {}).get("artifacts", [])
            assert artifacts
            assert all(str(artifact.get("sha256", "")).strip() for artifact in artifacts)
    for variable_id in ("trade_export_volume_index", "trade_import_volume_index"):
        trade_entry = next(
            entry for entry in crosswalk["entries"] if entry["variable_id"] == variable_id
        )
        assert trade_entry["status"] in {"mapped", "no_counterpart", "blocked"}
        assert "build_material_prices(parameters).standard" in trade_entry[
            "candidate_model_quantity"
        ]
        assert "CMEA versus convertible composition is not inferred" in trade_entry[
            "methodological_difference"
        ]


def test_trade_index_uses_standard_admin_prices_and_reports_channel_contributions() -> None:
    rows = []
    for year, export_energy, export_food, import_energy, import_food in (
        (1960, 1.0, 2.0, 2.0, 1.0),
        (1961, 2.0, 2.0, 1.0, 3.0),
    ):
        for quarter in range(1, 5):
            rows.extend(
                [
                    {
                        "quarter": f"{year}Q{quarter}", "commodity_id": "energy",
                        "exports": export_energy, "imports": import_energy,
                        "cmea_exports": export_energy, "convertible_exports": 0.0,
                        "cmea_imports": import_energy, "convertible_imports": 0.0,
                    },
                    {
                        "quarter": f"{year}Q{quarter}", "commodity_id": "food",
                        "exports": export_food, "imports": import_food,
                        "cmea_exports": 0.0, "convertible_exports": export_food,
                        "cmea_imports": 0.0, "convertible_imports": import_food,
                    },
                ]
            )
    indices = annual_price_weighted_trade_indices(
        pl.DataFrame(rows), ["energy", "food"], [2.0, 3.0]
    )
    values = annual_price_weighted_trade_values(
        pl.DataFrame(rows), ["energy", "food"], [2.0, 3.0]
    )
    assert indices["exports"][1960]["total_index"] == pytest.approx(100.0)
    assert indices["exports"][1961]["total_index"] == pytest.approx(125.0)
    assert indices["exports"][1960]["cmea_channel_index"] == pytest.approx(25.0)
    assert indices["exports"][1960]["convertible_channel_index"] == pytest.approx(75.0)
    assert indices["imports"][1961]["total_index"] == pytest.approx(11.0 / 7.0 * 100.0)
    assert values[1960]["cmea_exports"] == pytest.approx(2.0)
    assert values[1960]["convertible_exports"] == pytest.approx(6.0)


def test_model_consumption_index_uses_its_own_1960_base_and_quarter_mean() -> None:
    rows = []
    for year, quarterly in ((1960, [10.0, 20.0, 30.0, 40.0]), (1961, [20.0] * 4)):
        for q, total in enumerate(quarterly, start=1):
            for commodity, share in (("food", 0.25), ("energy", 0.75)):
                rows.append(
                    {
                        "quarter": f"{year}Q{q}",
                        "commodity_id": commodity,
                        "household_consumption": total * share,
                    }
                )
    result = annual_household_consumption_index(pl.DataFrame(rows))
    assert result[1960] == pytest.approx(100.0)
    assert result[1961] == pytest.approx(80.0)


def test_index_normalization_base_year_is_uninformative() -> None:
    assert not index_year_is_informative(1960)
    assert index_year_is_informative(1961)


def test_mapped_crosswalk_cannot_authorize_holdout_or_reserved(tmp_path: Path) -> None:
    import json
    (tmp_path / "config/calibration").mkdir(parents=True)
    (tmp_path / "data/manifests").mkdir(parents=True)
    p05 = {"reproduction_crosswalk": "config/calibration/crosswalk.json"}
    (tmp_path / "config/calibration/p05.json").write_text(json.dumps(p05))
    (tmp_path / "data/manifests/p05_targets.yml").write_text(
        yaml.safe_dump({"targets": [{"variable_id": "x"}]})
    )
    entry = {
        "variable_id": "x",
        "status": "mapped",
        "comparison_grade": "normalized_index",
        "target_unit": "index_1960_100",
        "model_unit": "index_1960_100",
        "model_quantity": "test quantity",
        "comparison_rule": "index_1960_100",
        "annual_aggregation": "mean",
        "comparison_window": ["holdout"],
        "error_tolerance": 0.5,
        "precision_basis": "fixed published precision",
    }
    (tmp_path / "config/calibration/crosswalk.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "source_manifest": "data/manifests/p05_targets.yml",
                "entries": [entry],
            }
        )
    )
    with pytest.raises(ConfigError, match="hold-out/reserved"):
        load_reproduction_crosswalk(tmp_path)


def test_mapped_crosswalk_without_a_declared_source_is_refused(tmp_path: Path) -> None:
    (tmp_path / "config/calibration").mkdir(parents=True)
    (tmp_path / "data/manifests").mkdir(parents=True)
    (tmp_path / "config/calibration/p05.json").write_text(
        '{"reproduction_crosswalk":"config/calibration/crosswalk.json"}'
    )
    (tmp_path / "data/manifests/p05_targets.yml").write_text(
        yaml.safe_dump(
            {
                "targets": [
                    {
                        "variable_id": "x", "artifact_id": "x-cal", "sha256": "abc",
                        "role": "target", "use": "calibration",
                    }
                ]
            }
        )
    )
    entry = {
        "variable_id": "x", "status": "mapped", "comparison_grade": "normalized_index",
        "target_unit": "index_1960_100", "model_unit": "index_1960_100",
        "model_quantity": "test quantity", "comparison_rule": "index_1960_100",
        "annual_aggregation": "mean", "comparison_window": ["calibration"],
        "error_tolerance": 0.5, "precision_basis": "fixed published precision",
    }
    (tmp_path / "config/calibration/crosswalk.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "source_manifest": "data/manifests/p05_targets.yml",
                "entries": [entry],
            }
        )
    )
    with pytest.raises(ConfigError, match="lacks declared source"):
        load_reproduction_crosswalk(tmp_path)


def test_trade_scenario_source_is_digest_pinned_and_limited_to_trade_indices(
    tmp_path: Path,
) -> None:
    scenario_id = "historical_f2_trade_scenario"
    scenario_path = tmp_path / "config/scenarios" / f"{scenario_id}.json"
    scenario_path.parent.mkdir(parents=True)
    scenario_path.write_text('{"scenario_id":"historical_f2_trade_scenario"}\n')
    digest = hashlib.sha256(scenario_path.read_bytes()).hexdigest()
    (tmp_path / "config/calibration").mkdir(parents=True)
    (tmp_path / "data/manifests").mkdir(parents=True)
    (tmp_path / "config/calibration/p05.json").write_text(
        '{"reproduction_crosswalk":"config/calibration/crosswalk.json"}'
    )
    target = {
        "variable_id": "trade_import_volume_index",
        "artifact_id": "trade-import-calibration",
        "sha256": "a" * 64,
        "role": "target",
        "use": "calibration",
    }
    (tmp_path / "data/manifests/p05_targets.yml").write_text(
        yaml.safe_dump({"targets": [target]})
    )
    entry = {
        "variable_id": target["variable_id"],
        "status": "mapped",
        "comparison_grade": "normalized_index",
        "target_unit": "index_1960_100",
        "model_unit": "index_1960_100",
        "model_quantity": "total import quantity",
        "comparison_rule": "index_1960_100",
        "annual_aggregation": "mean",
        "comparison_window": ["calibration"],
        "error_tolerance": 0.5,
        "precision_basis": "fixed published rounding precision",
        "source": {
            "type": "scenario_declared_trade_vectors",
            "scenario_id": scenario_id,
            "scenario_sha256": digest,
            "non_circularity_note": "No target series is used as a demand vector.",
            "artifacts": [
                {"artifact_id": target["artifact_id"], "sha256": target["sha256"]}
            ],
        },
    }
    crosswalk = {
        "schema_version": "1",
        "source_manifest": "data/manifests/p05_targets.yml",
        "model_scenario": scenario_id,
        "entries": [entry],
    }
    crosswalk_path = tmp_path / "config/calibration/crosswalk.json"
    crosswalk_path.write_text(json.dumps(crosswalk))
    loaded = load_reproduction_crosswalk(tmp_path)
    assert loaded["entries"][0]["source"]["scenario_sha256"] == digest

    entry["source"]["scenario_sha256"] = "b" * 64
    crosswalk_path.write_text(json.dumps(crosswalk))
    with pytest.raises(ConfigError, match="scenario digest"):
        load_reproduction_crosswalk(tmp_path)

    target["variable_id"] = "consumption"
    entry["variable_id"] = "consumption"
    entry["source"]["scenario_sha256"] = digest
    (tmp_path / "data/manifests/p05_targets.yml").write_text(
        yaml.safe_dump({"targets": [target]})
    )
    crosswalk_path.write_text(json.dumps(crosswalk))
    with pytest.raises(ConfigError, match="only supported for the two admitted trade indices"):
        load_reproduction_crosswalk(tmp_path)
