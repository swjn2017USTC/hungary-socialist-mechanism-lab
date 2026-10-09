"""P06 mechanism-card schema refuses incomplete or post hoc cards."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hsm_lab.calibration.mechanism_cards import (
    MechanismCard,
    MechanismResultCategory,
    load_mechanism_cards,
    mechanism_card_json_schema,
    validate_mechanism_card,
)

ROOT = Path(__file__).resolve().parents[1]


def test_incomplete_mechanism_card_is_refused() -> None:
    with pytest.raises(ValidationError):
        validate_mechanism_card({"mechanism_id": "M1", "hypothesis": "test"})


def test_schema_has_omp_plan_fields_and_only_five_result_categories() -> None:
    schema = json.loads((ROOT / "config/p06/mechanism_card.schema.json").read_text())
    assert schema == mechanism_card_json_schema()
    assert set(schema["properties"]) == {
        "mechanism_id",
        "hypothesis",
        "manipulated_variables",
        "controlled_variables",
        "metrics",
        "falsification_criterion",
        "minimum_replicates",
        "result_categories",
        "calibrated_parameter_dependencies",
    }
    assert {category.value for category in MechanismResultCategory} == {
        "SUPPORTED",
        "CONDITIONAL",
        "WEAK",
        "REJECTED",
        "UNIDENTIFIED",
    }
    assert MechanismCard.model_fields["mechanism_id"].is_required()


def test_card_validator_accepts_a_pre_registration_without_a_verdict() -> None:
    card = validate_mechanism_card(
        {
            "mechanism_id": "M1",
            "hypothesis": "A declared mechanism changes the registered outcome.",
            "manipulated_variables": ["parameter_x"],
            "controlled_variables": ["seed", "scenario"],
            "metrics": ["terminal_output"],
            "falsification_criterion": "The metric does not cross its threshold.",
            "minimum_replicates": 3,
            "result_categories": [item.value for item in MechanismResultCategory],
            "calibrated_parameter_dependencies": [],
        }
    )
    assert card.mechanism_id == "M1"
    assert "verdict" not in MechanismCard.model_fields


def test_repository_cards_are_complete_and_resolve_registry_dependencies() -> None:
    cards = load_mechanism_cards(ROOT)
    assert len(cards) == 11
    assert {card.mechanism_id for card in cards} == {f"M{i}" for i in range(1, 12)}
    all_categories = {category.value for category in MechanismResultCategory}
    for card in cards:
        assert {category.value for category in card.result_categories} == all_categories
        assert card.minimum_replicates == 3
    m1 = next(card for card in cards if card.mechanism_id == "M1")
    assert "p04_coalition_prior" in m1.calibrated_parameter_dependencies


def test_unknown_registry_dependency_is_rejected(tmp_path: Path) -> None:
    import shutil

    shutil.copytree(ROOT / "config", tmp_path / "config")
    cards_dir = tmp_path / "config/p06/cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "config/p06/cards").glob("*.json"):
        shutil.copy2(path, cards_dir / path.name)
    card_path = cards_dir / "M1.json"
    payload = json.loads(card_path.read_text())
    payload["calibrated_parameter_dependencies"].append("unknown_parameter")
    card_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="unknown dependency artifact_id"):
        load_mechanism_cards(tmp_path)


def test_unidentified_dependency_cannot_be_supported_only(tmp_path: Path) -> None:
    import shutil

    shutil.copytree(ROOT / "config", tmp_path / "config")
    cards_dir = tmp_path / "config/p06/cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "config/p06/cards").glob("*.json"):
        shutil.copy2(path, cards_dir / path.name)
    card_path = cards_dir / "M1.json"
    payload = json.loads(card_path.read_text())
    payload["result_categories"] = ["SUPPORTED"]
    card_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="cannot be SUPPORTED-only"):
        load_mechanism_cards(tmp_path)
