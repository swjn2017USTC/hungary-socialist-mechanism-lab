"""Schema and strict validator for pre-registered P06 mechanism cards.

This module validates card structure only. It does not instantiate experiments
or assign any mechanism verdict.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

NonEmpty = Annotated[str, Field(min_length=1)]


class MechanismResultCategory(StrEnum):
    SUPPORTED = "SUPPORTED"
    CONDITIONAL = "CONDITIONAL"
    WEAK = "WEAK"
    REJECTED = "REJECTED"
    UNIDENTIFIED = "UNIDENTIFIED"


class MechanismCard(BaseModel):
    """One M1–M11 pre-registration, before any results are observed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mechanism_id: str = Field(pattern=r"^M(?:[1-9]|1[01])$")
    hypothesis: NonEmpty
    manipulated_variables: list[NonEmpty] = Field(min_length=1)
    controlled_variables: list[NonEmpty] = Field(min_length=1)
    metrics: list[NonEmpty] = Field(min_length=1)
    falsification_criterion: NonEmpty
    minimum_replicates: int = Field(ge=1)
    result_categories: list[MechanismResultCategory] = Field(min_length=1)
    calibrated_parameter_dependencies: list[NonEmpty]


def validate_mechanism_card(payload: object) -> MechanismCard:
    """Validate a card payload or raise Pydantic's path-specific validation error."""
    return MechanismCard.model_validate(payload)


def mechanism_card_json_schema() -> dict[str, object]:
    """Return the portable JSON Schema for storage and external review."""
    return MechanismCard.model_json_schema()


def load_mechanism_cards(root: Path) -> list[MechanismCard]:
    """Load and validate the complete, registry-resolved M1–M11 preregistration set."""
    card_dir = Path(root) / "config/p06/cards"
    paths = sorted(card_dir.glob("M*.json"))
    cards = [
        validate_mechanism_card(json.loads(path.read_text(encoding="utf-8")))
        for path in paths
    ]
    expected = {f"M{i}" for i in range(1, 12)}
    ids = [card.mechanism_id for card in cards]
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError(f"mechanism cards must contain M1–M11 exactly once; got {ids}")

    registry = (Path(root) / "config/calibration/p05_parameters.yml").read_text(encoding="utf-8")
    try:
        import yaml

        registry_payload = yaml.safe_load(registry)
    except ImportError as exc:  # pragma: no cover - dependency is in the project runtime
        raise RuntimeError("PyYAML is required to resolve mechanism-card dependencies") from exc
    artifact_ids = {item["artifact_id"] for item in registry_payload["parameters"]}
    control = json.loads((Path(root) / "config/calibration/p05.json").read_text(encoding="utf-8"))
    unidentified = {
        artifact_id
        for artifact_id, status in control["identification"].items()
        if status == "unidentified"
    }
    for card in cards:
        unknown = set(card.calibrated_parameter_dependencies) - artifact_ids
        if unknown:
            raise ValueError(
                f"{card.mechanism_id} has unknown dependency artifact_id(s): {sorted(unknown)}"
            )
        depends_on_unidentified = bool(
            set(card.calibrated_parameter_dependencies) & unidentified
        )
        supported_only = card.result_categories == [MechanismResultCategory.SUPPORTED]
        if depends_on_unidentified and supported_only:
            raise ValueError(
                f"{card.mechanism_id} depends on an unidentified block and "
                "cannot be SUPPORTED-only"
            )
    return sorted(cards, key=lambda card: int(card.mechanism_id[1:]))
