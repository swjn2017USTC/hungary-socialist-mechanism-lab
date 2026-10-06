from __future__ import annotations

import json

import pytest

from hsm_lab.contract.schemas import ConfigError
from tests.conftest import (
    VERIFIED_RIGHTS,
    base_rows,
    make_registry,
    provenance,
    sha256_file,
    source_spec,
    variable_spec,
    write_long_parquet,
)

POP_VARIABLE = [
    variable_spec("population_anchor", "initial_anchor", "initial_state",
                  original_frequency="dated")
]
PARAM_VARIABLE = [
    variable_spec("sbc_strength", "latent", "latent_parameter", original_frequency="static")
]


def _anchor_artifact(tmp_path) -> dict:
    path = tmp_path / "fixtures" / "census_1960.parquet"
    digest = write_long_parquet(
        path, base_rows(["1960-01-01"], [7.5], variable_id="population_anchor")
    )
    return {
        "artifact_id": "census_1960",
        "variable_id": "population_anchor",
        "path": "fixtures/census_1960.parquet",
        "provenance": provenance(
            variable="population_anchor",
            role="initial_state",
            evidence_status="observed",
            original_frequency="dated",
            artifact_sha256=digest,
            raw_sha256=digest,
        ),
        "source_id": "src_fixture",
        "role": "initial_state",
        "grade": "A",
        "initial_at": "1960-01-01",
        "observation_at": "1960-01-01",
        "anchor_ids": [],
    }


def _initial_artifact(tmp_path, *, grade, evidence, observation_at, anchor_ids=()) -> dict:
    name = f"initial_{grade}_{evidence}"
    path = tmp_path / "fixtures" / f"{name}.parquet"
    digest = write_long_parquet(
        path, base_rows(["1957-01-01"], [7.2], variable_id="population_anchor")
    )
    return {
        "artifact_id": name,
        "variable_id": "population_anchor",
        "path": f"fixtures/{name}.parquet",
        "provenance": provenance(
            variable="population_anchor",
            role="initial_state",
            evidence_status=evidence,
            original_frequency="dated",
            artifact_sha256=digest,
            raw_sha256=digest,
            derived_from=list(anchor_ids),
        ),
        "source_id": "src_fixture",
        "role": "initial_state",
        "grade": grade,
        "initial_at": "1957Q1",
        "observation_at": observation_at,
        "anchor_ids": list(anchor_ids),
    }


def test_1960_observation_renamed_1957_grade_A_rejected(tmp_path) -> None:
    artifact = _initial_artifact(
        tmp_path, grade="A", evidence="observed", observation_at="1960"
    )
    with pytest.raises(Exception, match="grade B|reconstructed|bridging"):
        make_registry(tmp_path, sources=[source_spec()], variables=POP_VARIABLE,
                      artifacts=[artifact])


def test_grade_B_reconstruction_with_anchor_allowed(tmp_path) -> None:
    anchor = _anchor_artifact(tmp_path)
    bridged = _initial_artifact(
        tmp_path,
        grade="B",
        evidence="reconstructed",
        observation_at="1960",
        anchor_ids=["census_1960"],
    )
    registry = make_registry(
        tmp_path, sources=[source_spec()], variables=POP_VARIABLE,
        artifacts=[anchor, bridged],
    )
    frame = registry.load_initial(registry.artifacts["initial_B_reconstructed"])
    assert frame.height == 1
    assert registry.artifacts["census_1960"].grade == "A"

def test_annual_target_claiming_quarterly_observed_rejected(tmp_path) -> None:
    path = tmp_path / "fixtures" / "gdp.parquet"
    digest = write_long_parquet(path, base_rows(["1970", "1971"], [1.0, 2.0]))
    artifact = {
        "artifact_id": "gdp_quarterly_claim",
        "variable_id": "gdp",
        "path": "fixtures/gdp.parquet",
        "provenance": provenance(
            variable="gdp",
            role="target",
            evidence_status="observed",
            original_frequency="annual",
            model_frequency="annual",
            method="identity",
            artifact_sha256=digest,
            raw_sha256=digest,
        ),
        "source_id": "src_fixture",
        "role": "target",
        "use": "calibration",
        "observed_period": {"start": "1970Q1", "end": "1971Q4", "frequency": "quarterly"},
        "comparison_aggregation": "sum",
    }
    with pytest.raises(Exception, match="annual targets cannot claim"):
        make_registry(
            tmp_path,
            sources=[source_spec()],
            variables=[variable_spec("gdp", "outcome", "target")],
            artifacts=[artifact],
        )
def _parameter_artifact(tmp_path, *, evidence: str, literature=None, bounds=None) -> dict:
    path = tmp_path / "fixtures" / "prior.json"
    payload = {
        "schema_version": "1",
        "variable_id": "sbc_strength",
        "literature_refs": literature if literature is not None else ["Kornai (1980)"],
        "prior_description": "Beta(2, 2) prior on SBC strength",
        "bounds": bounds or {"lower": 0.0, "upper": 1.0},
        "calibration_status": "not_calibrated",
        "sensitivity_status": "not_assessed",
        "uncertainty_notes": "wide prior; no posterior exists yet",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    digest = sha256_file(path)
    return {
        "artifact_id": "param_sbc",
        "variable_id": "sbc_strength",
        "path": "fixtures/prior.json",
        "provenance": provenance(
            variable="sbc_strength",
            role="latent_parameter",
            evidence_status=evidence,
            original_frequency="static",
            artifact_sha256=digest,
            raw_sha256=digest,
        ),
        "source_id": "src_fixture",
        "role": "latent_parameter",
        "literature_refs": literature if literature is not None else ["Kornai (1980)"],
        "prior_description": "Beta(2, 2) prior on SBC strength",
        "bounds": bounds or {"lower": 0.0, "upper": 1.0},
        "calibration_status": "not_calibrated",
        "sensitivity_status": "not_assessed",
        "uncertainty_notes": "wide prior; no posterior exists yet",
    }


def test_latent_parameter_with_observed_evidence_rejected(tmp_path) -> None:
    with pytest.raises(Exception, match="observed evidence"):
        make_registry(
            tmp_path,
            sources=[source_spec()],
            variables=PARAM_VARIABLE,
            artifacts=[_parameter_artifact(tmp_path, evidence="observed")],
        )


def test_latent_parameter_requires_literature(tmp_path) -> None:
    with pytest.raises(Exception, match="min_length|literature"):
        make_registry(
            tmp_path,
            sources=[source_spec()],
            variables=PARAM_VARIABLE,
            artifacts=[_parameter_artifact(tmp_path, evidence="literature_proxy",
                                            literature=[])],
        )


def test_latent_parameter_inverted_bounds_rejected(tmp_path) -> None:
    with pytest.raises(Exception, match="inverted"):
        make_registry(
            tmp_path,
            sources=[source_spec()],
            variables=PARAM_VARIABLE,
            artifacts=[
                _parameter_artifact(
                    tmp_path, evidence="literature_proxy", bounds={"lower": 1.0, "upper": 0.0}
                )
            ],
        )


def test_latent_parameter_prior_file_validates(tmp_path) -> None:
    registry = make_registry(
        tmp_path,
        sources=[source_spec()],
        variables=PARAM_VARIABLE,
        artifacts=[_parameter_artifact(tmp_path, evidence="literature_proxy")],
    )
    payload = registry.validate_parameter(registry.artifacts["param_sbc"])
    assert payload["calibration_status"] == "not_calibrated"



def test_derived_from_cycle_rejected(tmp_path) -> None:
    first = _anchor_artifact(tmp_path)
    second = _initial_artifact(
        tmp_path, grade="B", evidence="reconstructed", observation_at="1960",
        anchor_ids=["census_1960"],
    )
    first["provenance"]["derived_from"] = ["initial_B_reconstructed"]
    second["provenance"]["derived_from"] = ["census_1960"]
    with pytest.raises(ConfigError, match="cycle"):
        make_registry(
            tmp_path, sources=[source_spec()], variables=POP_VARIABLE,
            artifacts=[first, second],
        )


def test_derived_from_unknown_id_rejected(tmp_path) -> None:
    artifact = _initial_artifact(
        tmp_path, grade="B", evidence="reconstructed", observation_at="1960",
        anchor_ids=["ghost_anchor"],
    )
    with pytest.raises(ConfigError, match="unknown artifact"):
        make_registry(
            tmp_path, sources=[source_spec()], variables=POP_VARIABLE, artifacts=[artifact]
        )


def test_same_source_different_roles_allowed(tmp_path) -> None:
    anchor = _anchor_artifact(tmp_path)
    gdp_path = tmp_path / "fixtures" / "gdp2.parquet"
    digest = write_long_parquet(gdp_path, base_rows(["1970", "1971"], [1.0, 2.0]))
    target = {
        "artifact_id": "gdp_target",
        "variable_id": "gdp",
        "path": "fixtures/gdp2.parquet",
        "provenance": provenance(
            variable="gdp", role="target", evidence_status="observed",
            artifact_sha256=digest, raw_sha256=digest,
        ),
        "source_id": "src_fixture",
        "role": "target",
        "use": "calibration",
        "observed_period": {"start": "1970", "end": "1971", "frequency": "annual"},
        "comparison_aggregation": "sum",
    }
    registry = make_registry(
        tmp_path,
        sources=[source_spec(expected_roles=["initial_state", "target"])],
        variables=POP_VARIABLE + [variable_spec("gdp", "outcome", "target")],
        artifacts=[anchor, target],
    )
    assert set(registry.artifacts) == {"census_1960", "gdp_target"}


def test_variable_role_semantic_mismatch_rejected(tmp_path) -> None:
    with pytest.raises(Exception, match="semantic_kind"):
        make_registry(
            tmp_path,
            sources=[source_spec()],
            variables=[variable_spec("gdp", "outcome", "exogenous_forcing")],
            artifacts=[],
        )


def test_unknown_rights_cannot_grant_downloads() -> None:
    from hsm_lab.data.schemas import RightsSpec

    # pydantic wraps ValueError subclasses into ValidationError at this layer;
    # the registry loader later re-raises them as ConfigError.
    with pytest.raises(ValueError, match="unknown rights cannot grant"):
        RightsSpec.model_validate({**VERIFIED_RIGHTS, "license_status": "unknown"})
    with pytest.raises(ValueError, match="verified rights require"):
        RightsSpec.model_validate({
            "license_status": "verified",
            "license_name": None,
            "terms_locator": None,
            "evidence_quote": None,
            "checked_at": None,
            "download_allowed": True,
            "redistribution_allowed": True,
            "notes": "missing evidence",
        })
