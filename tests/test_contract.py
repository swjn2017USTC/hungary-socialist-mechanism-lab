"""D1: contract, time windows, and role gates at the admission boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from hsm_lab.contract.guards import load_scenario, verify_baseline
from hsm_lab.contract.schemas import (
    ConfigError,
    Quarter,
    ResearchGateError,
    ScenarioSpec,
    TargetUse,
)
from tests.conftest import (
    REPO_ROOT,
    base_rows,
    make_registry,
    provenance,
    smoke_spec,
    source_spec,
    variable_spec,
    write_long_parquet,
)


def test_baseline_digest_matches_pinned_hash(contract) -> None:
    assert (
        verify_baseline(REPO_ROOT / "BASELINE.md", contract)
        == "1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f"
    )


def test_baseline_drift_rejects_run_before_any_output(contract, tmp_path) -> None:
    drifted = contract.model_copy(
        update={"expected_baseline_sha256": "0" * 63 + "1"}
    )
    from hsm_lab.data.registry import DataRegistry

    registry = DataRegistry.load(REPO_ROOT)
    with pytest.raises(ResearchGateError, match="hash drift"):
        smoke_run(tmp_path / "run", drifted, registry)
    assert not (tmp_path / "run").exists()


def smoke_run(output_dir: Path, contract, registry) -> None:
    from hsm_lab.engine.smoke import run_smoke

    run_smoke(smoke_spec(contract), output_dir, contract, registry)


def test_core_window_is_116_quarters(contract) -> None:
    assert Quarter.parse("1957Q1").advance(115) == Quarter.parse("1985Q4")
    assert contract.core_ticks == 116
    assert contract.in_reserved(Quarter.parse("1986Q1"))
    assert not contract.in_reserved(Quarter.parse("1985Q4"))


@pytest.mark.parametrize("bad", ["1957Q0", "1957Q5", "1957Q", "57Q1", "1957-Q1", 1957])
def test_quarter_format_rejected(bad) -> None:
    with pytest.raises(ConfigError):
        Quarter.parse(bad)


def test_scenario_region_mismatch_rejected(contract) -> None:
    spec = smoke_spec(contract, region_ids=contract.region_ids[:-1])
    with pytest.raises(ConfigError, match="region_ids"):
        spec.validate_for_run(contract)


def test_scenario_window_leaving_core_rejected(contract) -> None:
    with pytest.raises(ConfigError, match="core window"):
        smoke_spec(contract, ticks=117).validate_for_run(contract)


def test_scenario_inputs_must_stay_empty(contract) -> None:
    with pytest.raises(ConfigError, match="must be empty"):
        smoke_spec(contract, forcing_ids=["anything"]).validate_for_run(contract)


def test_single_goods_commodity_rejected() -> None:
    base = {
        "schema_version": "1",
        "scenario_id": "x",
        "kind": "smoke",
        "start": "1957Q1",
        "ticks": 1,
        "households": 1,
        "enterprises": 1,
        "region_ids": ["budapest"],
        "commodities": ["a", "b"],
        "seed": 0,
        "stochastic": False,
        "output_policy": "ensemble_compact",
        "forcing_ids": [],
        "initial_ids": [],
        "parameter_ids": [],
    }
    with pytest.raises(ValueError, match="forbidden commodity"):
        ScenarioSpec.model_validate({**base, "commodities": ["goods", "other"]})
        ScenarioSpec.model_validate({**base, "commodities": ["goods", "goods"]})
    with pytest.raises(ValueError):
        ScenarioSpec.model_validate({**base, "commodities": ["a", "a"]})
    with pytest.raises(ValueError):
        ScenarioSpec.model_validate({**base, "households": True})  # bool is not an int


def _target_artifact(tmp_path: Path, *, use: str, periods: list[str], values: list[float]) -> dict:
    path = tmp_path / "fixtures" / f"target_{use}.parquet"
    digest = write_long_parquet(path, base_rows(periods, values))
    return {
        "artifact_id": f"art_target_{use}",
        "variable_id": "gdp",
        "path": f"fixtures/target_{use}.parquet",
        "provenance": provenance(
            variable="gdp",
            role="target",
            evidence_status="observed",
            artifact_sha256=digest,
            raw_sha256=digest,
        ),
        "source_id": "src_fixture",
        "role": "target",
        "use": use,
        "observed_period": {"start": periods[0], "end": periods[-1], "frequency": "annual"},
        "comparison_aggregation": "sum",
    }


GDP_VARIABLES = [variable_spec("gdp", "outcome", "target")]
GDP_SOURCE = [source_spec()]


def test_reserved_target_metadata_ok_numeric_load_rejected(tmp_path) -> None:
    artifact = _target_artifact(
        tmp_path, use="reserved", periods=["1986", "1987"], values=[1.0, 2.0]
    )
    registry = make_registry(
        tmp_path, sources=GDP_SOURCE, variables=GDP_VARIABLES, artifacts=[artifact]
    )
    assert "art_target_reserved" in registry.artifacts  # metadata registration is legal
    with pytest.raises(ResearchGateError, match="reserved"):
        registry.load_targets(registry.artifacts["art_target_reserved"], TargetUse.RESERVED)


def test_core_window_target_touching_reserved_rejected(tmp_path) -> None:
    artifact = _target_artifact(
        tmp_path, use="calibration", periods=["1984", "1986"], values=[1.0, 2.0]
    )
    registry = make_registry(
        tmp_path, sources=GDP_SOURCE, variables=GDP_VARIABLES, artifacts=[artifact]
    )
    with pytest.raises(ResearchGateError, match="reserved window"):
        registry.load_targets(registry.artifacts["art_target_calibration"], TargetUse.CALIBRATION)


def test_calibration_cannot_consume_validation_target(tmp_path) -> None:
    artifact = _target_artifact(
        tmp_path, use="validation", periods=["1970", "1975"], values=[1.0, 2.0]
    )
    registry = make_registry(
        tmp_path, sources=GDP_SOURCE, variables=GDP_VARIABLES, artifacts=[artifact]
    )
    with pytest.raises(ResearchGateError, match="calibration may not consume"):
        registry.load_targets(registry.artifacts["art_target_validation"], TargetUse.CALIBRATION)
    frame = registry.load_targets(
        registry.artifacts["art_target_validation"], TargetUse.VALIDATION
    )
    assert frame.height == 2


def test_target_relabeled_forcing_rejected_before_file_read(tmp_path) -> None:
    # GDP is an outcome variable; a forcing-role artifact for it must fail on
    # the semantic gate *before* any file is touched - the file does not exist.
    artifact = {
        "artifact_id": "art_gdp_as_forcing",
        "variable_id": "gdp",
        "path": "fixtures/never_written.parquet",
        "provenance": provenance(
            variable="gdp",
            role="exogenous_forcing",
            evidence_status="observed",
            artifact_sha256="a" * 64,
        ),
        "source_id": "src_fixture",
        "role": "exogenous_forcing",
        "period": {"start": "1970", "end": "1975", "frequency": "annual"},
    }
    registry = make_registry(
        tmp_path, sources=GDP_SOURCE, variables=GDP_VARIABLES, artifacts=[artifact]
    )
    from hsm_lab.data.schemas import ForcingArtifact

    forcing = registry.artifacts["art_gdp_as_forcing"]
    assert isinstance(forcing, ForcingArtifact)
    with pytest.raises(ResearchGateError, match="semantic_kind"):
        registry.load_forcing(forcing)


def _good_forcing_fixture(tmp_path: Path, *, rights=None) -> dict:
    rows = [
        {
            "variable_id": "world_oil_price",
            "period": period,
            "region_id": None,
            "commodity_id": None,
            "value": value,
            "unit": "fixture-unit",
        }
        for period, value in [("1970-01", 1.0), ("1970-02", 2.0), ("1970-03", 3.0)]
    ]
    path = tmp_path / "fixtures" / "forcing.parquet"
    digest = write_long_parquet(path, rows)
    return {
        "artifact_id": "art_forcing",
        "variable_id": "world_oil_price",
        "path": "fixtures/forcing.parquet",
        "provenance": provenance(
            variable="world_oil_price",
            role="exogenous_forcing",
            evidence_status="observed",
            original_frequency="monthly",
            model_frequency="monthly",
            artifact_sha256=digest,
            raw_sha256=digest,
            rights=rights,
        ),
        "source_id": "src_fixture",
        "role": "exogenous_forcing",
        "period": {"start": "1970-01", "end": "1970-03", "frequency": "monthly"},
    }


FORCING_VARIABLES = [
    variable_spec("world_oil_price", "external", "exogenous_forcing",
                  original_frequency="monthly")
]


def test_unknown_rights_block_real_data_admission(tmp_path) -> None:
    unknown_rights = {
        "license_status": "unknown",
        "license_name": None,
        "terms_locator": None,
        "evidence_quote": None,
        "checked_at": None,
        "download_allowed": None,
        "redistribution_allowed": None,
        "notes": "unknown fixture rights",
    }
    artifact = _good_forcing_fixture(tmp_path, rights=unknown_rights)
    registry = make_registry(
        tmp_path,
        sources=[source_spec(rights=unknown_rights)],
        variables=FORCING_VARIABLES,
        artifacts=[artifact],
    )
    with pytest.raises(ResearchGateError, match="download permission"):
        registry.load_forcing(registry.artifacts["art_forcing"])


def test_verified_forcing_loads(tmp_path) -> None:
    artifact = _good_forcing_fixture(tmp_path)
    registry = make_registry(
        tmp_path, sources=GDP_SOURCE, variables=FORCING_VARIABLES, artifacts=[artifact]
    )
    frame = registry.load_forcing(registry.artifacts["art_forcing"])
    assert frame.height == 3


def test_digest_mismatch_rejected(tmp_path) -> None:
    artifact = _good_forcing_fixture(tmp_path)
    (tmp_path / "fixtures" / "forcing.parquet").write_bytes(b"tampered")
    registry = make_registry(
        tmp_path, sources=GDP_SOURCE, variables=FORCING_VARIABLES, artifacts=[artifact]
    )
    with pytest.raises(ResearchGateError, match="digest mismatch"):
        registry.load_forcing(registry.artifacts["art_forcing"])


def test_missing_file_rejected(tmp_path) -> None:
    artifact = _good_forcing_fixture(tmp_path)
    (tmp_path / "fixtures" / "forcing.parquet").unlink()
    registry = make_registry(
        tmp_path, sources=GDP_SOURCE, variables=FORCING_VARIABLES, artifacts=[artifact]
    )
    with pytest.raises(ResearchGateError, match="file not found"):
        registry.load_forcing(registry.artifacts["art_forcing"])


def test_unknown_source_rejected(tmp_path) -> None:
    artifact = _good_forcing_fixture(tmp_path)
    artifact["source_id"] = "src_missing"
    artifact["provenance"]["source_id"] = "src_missing"
    with pytest.raises(Exception, match="unknown source"):
        make_registry(
            tmp_path, sources=GDP_SOURCE, variables=FORCING_VARIABLES, artifacts=[artifact]
        )


def test_scenario_loader_rejects_unknown_scenario(repo_root) -> None:
    with pytest.raises(ConfigError, match="unsupported scenario"):
        load_scenario(repo_root, "historical")
    with pytest.raises(ConfigError, match="unsupported scenario"):
        load_scenario(repo_root, "counterfactual_1973")
