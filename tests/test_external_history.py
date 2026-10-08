"""P04 external-history tests: explicit channels, pack integrity, replay isolation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hsm_lab.contract.politics import (
    EXTERNAL_VARIABLE_IDS,
    SIGNAL_CHANNELS,
    PolicyReplayRegistry,
    PoliticalRunSpec,
    resolve_political_parameters,
)
from hsm_lab.data.external import (
    P04_SYNTHETIC_PACK_PATH,
    load_event_registry,
    load_external_pack,
    load_policy_replay,
)
from hsm_lab.data.registry import DataRegistry
from tests.conftest import REPO_ROOT


def test_event_registry_has_explicit_channels_and_provenance() -> None:
    registry = load_event_registry(REPO_ROOT)
    assert len(registry.events) == 16
    expected = {
        "post1956_stabilization",
        "soviet_energy_network",
        "prague_spring",
        "warsaw_pact_invasion",
        "detente_ostpolitik",
        "cmea_programme",
        "oil_shock_1",
        "western_stagflation",
        "helsinki",
        "cmea_price_rule_change",
        "charter77",
        "oil_shock_2",
        "volcker_credit_squeeze",
        "solidarity",
        "polish_martial_law",
        "gorbachev_signal",
    }
    assert {event.event_id for event in registry.events} == expected
    for event in registry.events:
        assert event.signal_channels, event.event_id
        assert set(event.signal_channels) <= set(SIGNAL_CHANNELS)
        assert event.date_evidence, event.event_id
        assert set(event.economic_series_refs) <= set(EXTERNAL_VARIABLE_IDS)
        assert event.mapping_parameter_paths, event.event_id


def test_replay_schedule_carries_initial_then_1968_step() -> None:
    registry = load_policy_replay(REPO_ROOT, "data/manifests/policy_replay.yml")
    assert isinstance(registry, PolicyReplayRegistry)
    quarters = ["1957Q1", "1967Q4", "1968Q1", "1968Q2"]
    schedule = registry.compiled_schedule(tuple(quarters))
    assert schedule["enterprise_autonomy"][0] == 0.1
    assert schedule["enterprise_autonomy"][1] == 0.1
    assert schedule["enterprise_autonomy"][2] == 0.7
    assert schedule["enterprise_autonomy"][3] == 0.7
    # A coordinate with no change-point carries the declared initial value.
    assert schedule["repression"] == [0.3, 0.3, 0.3, 0.3]


def test_replay_rejects_out_of_bounds_patch() -> None:
    registry = PolicyReplayRegistry.model_validate(
        {
            "initial_policy": _initial_policy_payload(),
            "records": [
                {
                    "record_id": "bad",
                    "effective_quarter": "1968Q1",
                    "patch": {"repression": 5.0},
                    "date_precision": "exact_quarter",
                    "date_evidence": ["test"],
                    "magnitude_evidence_status": "structural_assumption",
                    "notes": "test",
                }
            ],
            "coverage_note": "test",
        }
    )
    # The out-of-bounds patch is refused when the piecewise schedule is compiled.
    with pytest.raises(Exception, match="bounds"):
        registry.compiled_schedule(("1957Q1", "1968Q1"))


def test_external_pack_tamper_gate(tmp_path: Path) -> None:
    from tests.conftest import make_registry, source_spec

    make_registry(
        tmp_path,
        sources=[source_spec("p04_fixture")],
        variables=[],
        artifacts=[],
    )
    pack_path = REPO_ROOT / P04_SYNTHETIC_PACK_PATH
    tampered = json.loads(pack_path.read_text())
    tampered["variables"]["technology_access"]["values"][0] = 0.99
    scratch = tmp_path / "fixtures"
    scratch.mkdir(parents=True, exist_ok=True)
    (scratch / "p04_external_synthetic_pack.json").write_text(json.dumps(tampered))

    registry = DataRegistry.load(tmp_path, extra_roots=(scratch,))
    politics = PoliticalRunSpec(
        mode="historical_replay",
        external_pack="fixtures/p04_external_synthetic_pack.json",
        event_registry="data/manifests/external_events.yml",
        replay_registry="data/manifests/policy_replay.yml",
        study_id="test",
    )
    with pytest.raises(Exception, match="pack_sha256"):
        load_external_pack(politics, registry)


def test_default_parameters_are_resolved_from_the_initial_policy() -> None:
    from hsm_lab.contract.guards import load_scenario
    from hsm_lab.contract.politics import PoliticalParameters
    from hsm_lab.engine.policy import default_initial_policy

    spec = load_scenario(REPO_ROOT, "p04_endogenous")
    raw = PoliticalParameters()
    assert not any(any(row) for row in raw.broker.A)
    resolved = resolve_political_parameters(raw, default_initial_policy(spec))
    assert any(any(row) for row in resolved.broker.A)
    assert any(any(row) for row in resolved.coalition.beta)
    assert any(any(row) for row in resolved.observation.feature_bias_loading)


def _initial_policy_payload() -> dict[str, float]:
    return {
        "plan_utilization": 0.9,
        "enterprise_autonomy": 0.1,
        "investment_intensity": 1.0,
        "industrial_priority": 0.0,
        "admin_price_factor": 1.0,
        "wage_factor": 1.0,
        "credit_fraction": 0.5,
        "budget_hardness": 0.0,
        "housing_factor": 1.0,
        "borrowing_factor": 1.0,
        "consumer_import_factor": 1.0,
        "second_economy_tolerance": 1.0,
        "welfare_provision": 0.5,
        "private_autonomy": 0.5,
        "cultural_openness": 0.5,
        "supported_boundary": 0.3,
        "tolerance_boundary": 0.7,
        "repression": 0.3,
        "information_investment": 0.0,
    }
