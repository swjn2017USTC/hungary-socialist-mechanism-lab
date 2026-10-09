"""P05 Gate 1 freeze checks: F2 ontology and region proxy (P05 §A).

These tests assert the *frozen* artifacts a historical F2 run must compile
against, not any historical magnitude.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl

from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.contract.material import (
    F2_CATALOG,
    F2_COMMODITY_ROLES,
    F2_COMMODITY_SPECS,
    OrganizationType,
    catalog_for_commodities,
    get_catalog,
)

ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict:
    return json.loads(path.read_text())


def test_f2_ontology_freeze_matches_python_catalog() -> None:
    frozen = _read(ROOT / "config" / "ontology" / "f2_v1.json")
    assert frozen["ontology_id"] == F2_CATALOG.catalog_id
    assert frozen["commodity_count"] == 16
    assert len(F2_COMMODITY_SPECS) == 16
    by_id = {row["id"]: row for row in frozen["commodities"]}
    assert tuple(by_id) == F2_CATALOG.ids
    for spec in F2_COMMODITY_SPECS:
        row = by_id[spec.id]
        assert row["unit"] == spec.unit
        assert row["stockable"] == spec.stockable
        assert row["household_channel"] == spec.household_channel
        assert row["stages"] == list(spec.stages)
        assert row["hub_stages"] == list(spec.hub_stages)
        assert row["retail_stages"] == list(spec.retail_stages)
        assert row["investment"] == spec.investment
        assert row["roles"] == list(F2_COMMODITY_ROLES[spec.id])


def test_f2_axis_roles_are_complete_and_typed() -> None:
    # every non-stockable commodity is a same-quarter service
    for spec in F2_COMMODITY_SPECS:
        if not spec.stockable:
            assert F2_CATALOG.has_role(spec.id, "same_quarter_service")
    # featured goods keep their roles so the engine never guesses by index
    assert F2_CATALOG.with_role("capital") == ("g06_machinery_capital",)
    assert F2_CATALOG.with_role("construction") == ("g07_construction",)
    assert F2_CATALOG.with_role("food_raw") == ("g08_agricultural_raw",)
    assert F2_CATALOG.with_role("vehicle") == ("g14_vehicles_transport_equipment",)
    assert F2_CATALOG.with_role("public") == ("g16_housing_public_services",)


def test_f2_technologies_cover_the_axis() -> None:
    from hsm_lab.contract.material import F2_COMMODITY_IDS, f2_default_technologies

    f2_ids = set(F2_COMMODITY_IDS)
    technologies = f2_default_technologies()
    produced: set[str] = set()
    for technology in technologies:
        for row in technology.inputs:
            assert row.commodity_id in f2_ids
        for row in technology.outputs:
            assert row.commodity_id in f2_ids
            produced.add(row.commodity_id)
    # every runtime commodity is producible by some declared technology
    assert produced == f2_ids


def test_f2_profiles_split_evenly_and_sum() -> None:
    from hsm_lab.contract.material import (
        F2_INDUSTRIAL_TECHNOLOGY_IDS,
        F2_ORGANIZATION_PROFILES,
        ORGANIZATION_PROFILES,
    )

    count = len(F2_INDUSTRIAL_TECHNOLOGY_IDS)
    for profile_id, profile in F2_ORGANIZATION_PROFILES.items():
        assert ORGANIZATION_PROFILES[profile_id] is profile
        assert profile[OrganizationType.INDUSTRIAL_SOE] % count == 0
        assert sum(profile.values()) in (300, 400, 450)


def test_f2_household_axis_is_well_formed() -> None:
    from hsm_lab.contract.households import F2_AXIS
    from hsm_lab.contract.material import F2_COMMODITY_IDS

    assert F2_AXIS.axis_id == "f2_v1"
    assert len(F2_AXIS.good_ids) == 15
    assert len(F2_AXIS.parent_commodity_ids) == 15
    assert set(F2_AXIS.parent_commodity_ids) <= set(F2_COMMODITY_IDS)
    assert F2_AXIS.channels_for("energy") == (0, 1, 2)
    assert F2_AXIS.channels_for("light") == (5, 6)
    assert len(F2_AXIS.role_channels["durable"]) == 4
    groups: dict[str, float] = {}
    for parent, quota in zip(F2_AXIS.parent_commodity_ids, F2_AXIS.quota_share, strict=True):
        groups[parent] = groups.get(parent, 0.0) + quota
    assert all(abs(total - 1.0) < 1e-9 for total in groups.values())


def test_f2_scenario_and_benchmark_config_are_registered() -> None:
    import json

    from hsm_lab.benchmarks.harness import _case_definitions, _load_config

    spec = load_scenario(ROOT, "historical_f2_replay")
    contract = load_research_contract(ROOT)
    spec.validate_for_run(contract)
    assert len(spec.commodities) == 16
    config = _load_config(ROOT, "f2")
    cases = _case_definitions("f2", config)
    assert cases and all(case["kind"] == "f2" for case in cases)
    raw = json.loads((ROOT / "config" / "benchmarks" / "f2.json").read_text())
    assert len(raw["commodities"]) == 16


def test_catalog_resolution_is_by_id_set_not_order() -> None:
    reordered = tuple(reversed(F2_CATALOG.ids))
    assert catalog_for_commodities(reordered).catalog_id == "f2_v1"
    assert get_catalog("intermediate8_v1").ids[0] == "energy"


def test_f2_regions_freeze_uses_contract_nodes() -> None:
    contract = load_research_contract(ROOT)
    frozen = _read(ROOT / "config" / "ontology" / "f2_regions_v1.json")
    assert tuple(frozen["region_ids"]) == tuple(contract.region_ids)
    matrix = frozen["distance_matrix"]
    assert len(matrix) == len(contract.region_ids)
    for i, row in enumerate(matrix):
        assert row[i] == 0.0
        for j, value in enumerate(row):
            assert value == (0.0 if i == j else 1.0)


def test_input_timing_derives_from_stockability() -> None:
    from hsm_lab.contract.material import InputCoefficient

    stockable = InputCoefficient(commodity_id="energy", coefficient=1.0)
    assert stockable.resolved_input_timing == "opening_stock"
    service = InputCoefficient(commodity_id="services_transport", coefficient=1.0)
    assert service.resolved_input_timing == "same_quarter_service"


def test_input_timing_rejects_contradictory_declaration() -> None:
    import pytest
    from pydantic import ValidationError

    from hsm_lab.contract.material import InputCoefficient

    with pytest.raises(ValidationError):
        InputCoefficient(
            commodity_id="energy", coefficient=1.0, input_timing="same_quarter_service"
        )
    with pytest.raises(ValidationError):
        InputCoefficient(
            commodity_id="services_transport", coefficient=1.0, input_timing="opening_stock"
        )


def test_f2_non_stockable_inputs_are_same_quarter() -> None:
    from hsm_lab.contract.material import F2_COMMODITY_SPECS, InputCoefficient

    for spec in F2_COMMODITY_SPECS:
        timing = InputCoefficient(commodity_id=spec.id, coefficient=1.0).resolved_input_timing
        expected = "opening_stock" if spec.stockable else "same_quarter_service"
        assert timing == expected



def test_reconstruction_admits_the_mandatory_anchors_as_grade_c_proxies() -> None:
    from hsm_lab.data.reconstruct import reconstruct_p05

    payload = reconstruct_p05(ROOT, config=ROOT / "config" / "calibration" / "p05.json")
    assert payload["status"] == "ok"
    assert payload["missing_mandatory"] == []
    assert payload["declared_anchors"] == 63
    # the anchors exist but only as 2011 fixed-space proxies: never reported as A/B
    for family in payload["mandatory"]:
        assert family["admitted"] == 21
        assert family["grades"] == ["C"]
        assert family["provenance"] == ["literature_proxy"]
    assert any("fixed-space proxy" in caveat for caveat in payload["caveats"])


def test_reconstruction_fails_without_mandatory_anchors(tmp_path) -> None:
    import json

    from hsm_lab.data.reconstruct import reconstruct_p05

    (tmp_path / "data" / "manifests").mkdir(parents=True)
    control = json.loads((ROOT / "config" / "calibration" / "p05.json").read_text())
    name = control.get("data_manifest", "DATA_MANIFEST_v1.json")
    (tmp_path / "data" / "manifests" / name).write_text(
        json.dumps({"artifacts": [], "ontology_id": "f2_v1"}), encoding="utf-8"
    )
    payload = reconstruct_p05(tmp_path, config=ROOT / "config" / "calibration" / "p05.json")
    assert payload["status"] == "MISSING_MANDATORY_ANCHORS"
    assert payload["declared_anchors"] == 0


def test_f2_published_expiry_is_the_kernel_sink(tmp_path) -> None:
    """The published per-commodity expiry is the kernel's own expiry sink.

    Regression: the publisher resolved stockability from the P02-only commodity
    registry and defaulted every unknown id to stockable, so all three F2 service
    commodities reported zero expiry (2.8 M units hidden) and the frozen expiry
    gate could not be evaluated from the published artifacts at all.
    """

    from hsm_lab.data.registry import DataRegistry
    from hsm_lab.engine.material import run_material

    spec = load_scenario(ROOT, "historical_f2_replay")
    contract = load_research_contract(ROOT)
    registry = DataRegistry.load(ROOT, allowed_commodities=spec.commodities)
    run_material(spec, tmp_path / "run", contract, registry, until="1958Q4")

    national = pl.read_parquet(tmp_path / "run" / "national_accounts.parquet")
    services = {"g03_electricity_heat", "g15_market_services", "g16_housing_public_services"}
    assert set(national.filter(pl.col("expiry") > 0)["commodity_id"].unique().to_list()) == services

    diagnostics = pl.read_parquet(tmp_path / "run" / "tick_diagnostics.parquet").sort("tick")
    per_tick = (
        national.group_by("tick").agg(pl.col("expiry").sum()).sort("tick")["expiry"].to_numpy()
    )
    assert np.allclose(per_tick, diagnostics["expired_services"].to_numpy(), atol=1e-6)

    # The stage grid carries a ledger-consistent reconstruction with its own
    # residual identity, so it is not asserted equal to the kernel sink; it must
    # nevertheless report the same three commodities instead of a structural zero.
    stage = pl.read_parquet(tmp_path / "run" / "stage_balances.parquet")
    assert set(stage.filter(pl.col("expiry") > 0)["commodity_id"].unique().to_list()) == services
