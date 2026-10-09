"""Schema and strict validator for pre-registered P06 mechanism cards.

This module validates card structure only. It does not instantiate experiments
or assign any mechanism verdict.
"""

from __future__ import annotations

from enum import StrEnum
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
