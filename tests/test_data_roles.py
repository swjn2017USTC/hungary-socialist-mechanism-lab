from __future__ import annotations

import json

import pytest

from hsm_lab.contract.schemas import ConfigError, ResearchGateError
from tests.conftest import (
    REPO_ROOT,
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
    variable_spec(
        "population_anchor", "initial_anchor", "initial_state", original_frequency="dated"
    )
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
        "initial_at": "1957-01-01",
        "observation_at": observation_at,
        "anchor_ids": list(anchor_ids),
    }


def test_1960_observation_renamed_1957_grade_A_rejected(tmp_path) -> None:
    artifact = _initial_artifact(tmp_path, grade="A", evidence="observed", observation_at="1960")
    with pytest.raises(Exception, match="grade B|reconstructed|bridging"):
        make_registry(
            tmp_path, sources=[source_spec()], variables=POP_VARIABLE, artifacts=[artifact]
        )


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
        tmp_path,
        sources=[source_spec()],
        variables=POP_VARIABLE,
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
            variables=[variable_spec("gdp", "outcome", "target", aggregation="sum")],
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
            artifacts=[_parameter_artifact(tmp_path, evidence="literature_proxy", literature=[])],
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
        tmp_path,
        grade="B",
        evidence="reconstructed",
        observation_at="1960",
        anchor_ids=["census_1960"],
    )
    first["provenance"]["derived_from"] = ["initial_B_reconstructed"]
    second["provenance"]["derived_from"] = ["census_1960"]
    with pytest.raises(ConfigError, match="cycle"):
        make_registry(
            tmp_path,
            sources=[source_spec()],
            variables=POP_VARIABLE,
            artifacts=[first, second],
        )


def test_derived_from_unknown_id_rejected(tmp_path) -> None:
    artifact = _initial_artifact(
        tmp_path,
        grade="B",
        evidence="reconstructed",
        observation_at="1960",
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
            variable="gdp",
            role="target",
            evidence_status="observed",
            artifact_sha256=digest,
            raw_sha256=digest,
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
        variables=POP_VARIABLE + [variable_spec("gdp", "outcome", "target", aggregation="sum")],
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
        RightsSpec.model_validate(
            {
                "license_status": "verified",
                "license_name": None,
                "terms_locator": None,
                "evidence_quote": None,
                "checked_at": None,
                "download_allowed": True,
                "redistribution_allowed": True,
                "notes": "missing evidence",
            }
        )


# ----------------------------------------------------------------------
# Review round 1: anchor lineage and payload/declaration agreement.
# ----------------------------------------------------------------------
def test_self_anchor_rejected(tmp_path) -> None:
    artifact = _initial_artifact(
        tmp_path,
        grade="B",
        evidence="reconstructed",
        observation_at="1960",
        anchor_ids=["initial_B_reconstructed"],
    )
    with pytest.raises(ConfigError, match="cycle"):
        make_registry(
            tmp_path, sources=[source_spec()], variables=POP_VARIABLE, artifacts=[artifact]
        )


def test_anchor_cycle_rejected(tmp_path) -> None:
    first = _initial_artifact(
        tmp_path,
        grade="B",
        evidence="reconstructed",
        observation_at="1960",
        anchor_ids=["initial_B_reconstructed__2"],
    )
    first["artifact_id"] = "initial_B_reconstructed__1"
    first["path"] = "fixtures/initial_B_reconstructed__1.parquet"
    second = _initial_artifact(
        tmp_path,
        grade="B",
        evidence="reconstructed",
        observation_at="1960",
        anchor_ids=["initial_B_reconstructed__1"],
    )
    second["artifact_id"] = "initial_B_reconstructed__2"
    second["path"] = "fixtures/initial_B_reconstructed__2.parquet"
    with pytest.raises(ConfigError, match="cycle"):
        make_registry(
            tmp_path,
            sources=[source_spec()],
            variables=POP_VARIABLE,
            artifacts=[first, second],
        )


def test_structural_assumption_anchor_rejected(tmp_path) -> None:
    assumption = _initial_artifact(
        tmp_path, grade="S", evidence="structural_assumption", observation_at="1957-01-01"
    )
    assumption["artifact_id"] = "assumption_anchor"
    assumption["path"] = "fixtures/assumption_anchor.parquet"
    bridged = _initial_artifact(
        tmp_path,
        grade="B",
        evidence="reconstructed",
        observation_at="1960",
        anchor_ids=["assumption_anchor"],
    )
    with pytest.raises(ConfigError, match="grade A or B"):
        make_registry(
            tmp_path,
            sources=[source_spec()],
            variables=POP_VARIABLE,
            artifacts=[assumption, bridged],
        )


def test_grade_a_payload_must_sit_at_observation_date(tmp_path) -> None:
    """File at 1960-01-01 declared as a 1957 observed state is refused."""
    from hsm_lab.contract.schemas import ResearchGateError

    lying = _anchor_artifact(tmp_path)
    lying["initial_at"] = "1957-01-01"
    lying["observation_at"] = "1957-01-01"
    registry = make_registry(
        tmp_path, sources=[source_spec()], variables=POP_VARIABLE, artifacts=[lying]
    )
    with pytest.raises(ResearchGateError, match="does not match the declared observation_at"):
        registry.load_initial(registry.artifacts["census_1960"])


def test_prior_file_field_disagreements_rejected(tmp_path) -> None:
    from hsm_lab.contract.schemas import ResearchGateError

    base = _parameter_artifact(tmp_path, evidence="literature_proxy")
    registry = make_registry(
        tmp_path, sources=[source_spec()], variables=PARAM_VARIABLE, artifacts=[base]
    )
    assert (
        registry.validate_parameter(registry.artifacts["param_sbc"])["calibration_status"]
        == "not_calibrated"
    )

    payload = json.loads((tmp_path / "fixtures" / "prior.json").read_text(encoding="utf-8"))
    payload["bounds"] = {"lower": 20.0, "upper": 30.0}
    (tmp_path / "fixtures" / "prior.json").write_text(json.dumps(payload), encoding="utf-8")
    digest = sha256_file(tmp_path / "fixtures" / "prior.json")
    drifted = {**base}
    drifted["provenance"] = {**base["provenance"], "artifact_sha256": digest, "raw_sha256": digest}
    registry2 = make_registry(
        tmp_path, sources=[source_spec()], variables=PARAM_VARIABLE, artifacts=[drifted]
    )
    with pytest.raises(ResearchGateError, match="bounds.lower"):
        registry2.validate_parameter(registry2.artifacts["param_sbc"])

    payload["bounds"] = {"lower": 0.0, "upper": 1.0}
    payload["literature_refs"] = ["Not Actually Cited (1999)"]
    (tmp_path / "fixtures" / "prior.json").write_text(json.dumps(payload), encoding="utf-8")
    digest3 = sha256_file(tmp_path / "fixtures" / "prior.json")
    drifted3 = {
        **base,
        "provenance": {**base["provenance"], "artifact_sha256": digest3, "raw_sha256": digest3},
    }
    registry3 = make_registry(
        tmp_path, sources=[source_spec()], variables=PARAM_VARIABLE, artifacts=[drifted3]
    )
    with pytest.raises(ResearchGateError, match="literature_refs"):
        registry3.validate_parameter(registry3.artifacts["param_sbc"])


def test_within_month_later_observation_requires_grade_B(tmp_path) -> None:
    """1960-01-31 observed data may not pose as a 1960-01-01 observed state."""
    from hsm_lab.contract.schemas import ConfigError as ContractConfigError

    near = _anchor_artifact(tmp_path)
    near["initial_at"] = "1960-01-01"
    near["observation_at"] = "1960-01-31"
    with pytest.raises(ContractConfigError, match="grade B"):
        make_registry(tmp_path, sources=[source_spec()], variables=POP_VARIABLE, artifacts=[near])


# ----------------------------------------------------------------------
# Review round 3 (N1/N2): transitive anchor admission and grade-A chronology.
# ----------------------------------------------------------------------
def _chain_fixture(tmp_path):
    """grade-A census 1960 <- grade-B 1958 bridge <- grade-B 1957 reconstruction."""
    anchor = _anchor_artifact(tmp_path)
    bridge = _initial_artifact(
        tmp_path,
        grade="B",
        evidence="reconstructed",
        observation_at="1960-01-01",
        anchor_ids=["census_1960"],
    )
    bridge["artifact_id"] = "bridge_1958"
    bridge["path"] = "fixtures/bridge_1958.parquet"
    bridge["initial_at"] = "1958-01-01"
    bridge_file = tmp_path / "fixtures" / "bridge_1958.parquet"
    digest = write_long_parquet(
        bridge_file, base_rows(["1958-01-01"], [7.3], variable_id="population_anchor")
    )
    bridge["provenance"]["artifact_sha256"] = digest
    bridge["provenance"]["raw_sha256"] = digest
    top = _initial_artifact(
        tmp_path,
        grade="B",
        evidence="reconstructed",
        observation_at="1958-01-01",
        anchor_ids=["bridge_1958"],
    )
    top["artifact_id"] = "top_1957"
    top["path"] = "fixtures/top_1957.parquet"
    top_file = tmp_path / "fixtures" / "top_1957.parquet"
    digest2 = write_long_parquet(
        top_file, base_rows(["1957-01-01"], [7.25], variable_id="population_anchor")
    )
    top["provenance"]["artifact_sha256"] = digest2
    top["provenance"]["raw_sha256"] = digest2
    return anchor, bridge, top


def test_valid_multilevel_reconstruction_chain_loads(tmp_path) -> None:
    anchor, bridge, top = _chain_fixture(tmp_path)
    registry = make_registry(
        tmp_path,
        sources=[source_spec()],
        variables=POP_VARIABLE,
        artifacts=[anchor, bridge, top],
    )
    frame = registry.load_initial(registry.artifacts["top_1957"])
    assert frame.height == 1


def test_descendant_refused_when_anchor_file_missing(tmp_path) -> None:
    anchor, bridge, top = _chain_fixture(tmp_path)
    (tmp_path / "fixtures" / "census_1960.parquet").unlink()
    registry = make_registry(
        tmp_path,
        sources=[source_spec()],
        variables=POP_VARIABLE,
        artifacts=[anchor, bridge, top],
    )
    with pytest.raises(ResearchGateError, match="file not found"):
        registry.load_initial(registry.artifacts["top_1957"])


def test_descendant_refused_when_anchor_rights_denied(tmp_path) -> None:
    anchor, bridge, top = _chain_fixture(tmp_path)
    denied = {**VERIFIED_RIGHTS, "download_allowed": False}
    # the anchor chain hangs off a denied source; the descendant itself is fine
    for artifact in (anchor, bridge):
        artifact["source_id"] = "src_denied"
        artifact["provenance"]["source_id"] = "src_denied"
        artifact["provenance"]["rights"] = denied
    registry = make_registry(
        tmp_path,
        sources=[source_spec(), source_spec(source_id="src_denied", rights=denied)],
        variables=POP_VARIABLE,
        artifacts=[anchor, bridge, top],
    )
    with pytest.raises(ResearchGateError, match="download permission"):
        registry.load_initial(registry.artifacts["top_1957"])


def test_descendant_refused_when_anchor_payload_corrupted(tmp_path) -> None:
    anchor, bridge, top = _chain_fixture(tmp_path)
    (tmp_path / "fixtures" / "bridge_1958.parquet").write_bytes(b"tampered")
    registry = make_registry(
        tmp_path,
        sources=[source_spec()],
        variables=POP_VARIABLE,
        artifacts=[anchor, bridge, top],
    )
    with pytest.raises(ResearchGateError, match="digest mismatch"):
        registry.load_initial(registry.artifacts["top_1957"])


def test_ancient_observation_cannot_be_grade_a(tmp_path) -> None:
    stale = _anchor_artifact(tmp_path)
    stale["initial_at"] = "1957-01-01"
    stale["observation_at"] = "1900-01-01"
    stale_file = tmp_path / "fixtures" / "census_1960.parquet"
    digest = write_long_parquet(
        stale_file, base_rows(["1900-01-01"], [7.5], variable_id="population_anchor")
    )
    stale["provenance"]["artifact_sha256"] = digest
    stale["provenance"]["raw_sha256"] = digest
    with pytest.raises(Exception, match="coincide exactly with initial_at"):
        make_registry(tmp_path, sources=[source_spec()], variables=POP_VARIABLE, artifacts=[stale])


def test_mixed_precision_grade_a_rejected(tmp_path) -> None:
    mixed = _anchor_artifact(tmp_path)
    mixed["initial_at"] = "1960-03-01"
    mixed["observation_at"] = "1960Q1"  # quarter end = 1960-03-31, not equal
    with pytest.raises(Exception, match="coincide exactly"):
        make_registry(tmp_path, sources=[source_spec()], variables=POP_VARIABLE, artifacts=[mixed])


def test_impossible_calendar_date_rejected(tmp_path) -> None:
    bad = _anchor_artifact(tmp_path)
    bad["initial_at"] = "1960-02-31"
    bad["observation_at"] = "1960-02-31"
    with pytest.raises(Exception, match="invalid anchor date"):
        make_registry(tmp_path, sources=[source_spec()], variables=POP_VARIABLE, artifacts=[bad])


def test_policy_input_channel_is_separate_from_external_forcing() -> None:
    """Mode A policy replay is its own input channel, never external forcing."""
    import pytest

    from hsm_lab.data.registry import DataRegistry

    registry = DataRegistry.load(REPO_ROOT)
    policy_artifact = registry.artifacts["p04_policy_enterprise_autonomy"]
    frame = registry.load_policy_input(policy_artifact)
    assert frame.height == 116
    with pytest.raises(Exception, match="policy_input"):
        registry.load_forcing(policy_artifact)

    external_artifact = registry.artifacts["p02_material_world_oil_quarterly"]
    with pytest.raises(Exception, match="external"):
        registry.load_policy_input(external_artifact)
