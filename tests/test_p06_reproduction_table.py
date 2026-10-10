"""P06 target comparison uses a predeclared crosswalk and annual index normalization."""

from __future__ import annotations

import json
import re
from pathlib import Path

import polars as pl
import pytest
import yaml

from hsm_lab.calibration.reproduction_table import (
    annual_household_consumption_index,
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
    assert statuses.count("mapped") == 1
    assert statuses.count("no_counterpart") == 3
    assert statuses.count("blocked") == 10
    mapped = next(entry for entry in crosswalk["entries"] if entry["status"] == "mapped")
    assert mapped["variable_id"] == "consumption"
    assert set(mapped["comparison_window"]) == {"calibration", "internal_validation"}
    assert mapped["error_tolerance"] == 0.5


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
