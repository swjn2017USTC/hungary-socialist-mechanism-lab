"""Declared price-category regimes for the H2B execution bridge.

The model has an administered price vector, not a historical price-category
institution.  This module only carries a *declared research setting*: each
commodity belongs to exactly one category, and each category is either
``fixed`` or ``authorized_adjustment``.  Missing or duplicate coverage fails
closed; the bridge never guesses a default regime.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from hsm_lab.contract.base import ConfigError, StrictModel


class PriceCategoryRule(StrictModel):
    category_id: str = Field(min_length=1)
    commodity_ids: list[str] = Field(min_length=1)
    regime: Literal["fixed", "authorized_adjustment"]


class PriceRegime(StrictModel):
    """Declared commodity -> category -> regime book."""

    schema_version: Literal["1"] = "1"
    categories: list[PriceCategoryRule] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_coverage(self) -> PriceRegime:
        category_ids = [rule.category_id for rule in self.categories]
        if len(set(category_ids)) != len(category_ids):
            raise ConfigError("price regime category ids must be unique")
        commodity_ids = [cid for rule in self.categories for cid in rule.commodity_ids]
        if len(set(commodity_ids)) != len(commodity_ids):
            raise ConfigError("a commodity may appear in only one price category")
        return self

    def rule_for(self, commodity_id: str) -> PriceCategoryRule:
        for rule in self.categories:
            if commodity_id in rule.commodity_ids:
                return rule
        raise ConfigError(
            f"commodity {commodity_id!r} has no declared price category; "
            "the price bridge fails closed"
        )

    def validate_commodities(self, commodity_ids: tuple[str, ...]) -> None:
        missing = sorted(
            set(commodity_ids)
            - {cid for rule in self.categories for cid in rule.commodity_ids}
        )
        if missing:
            raise ConfigError(
                "price regime does not cover model commodities: " + ", ".join(missing)
            )
