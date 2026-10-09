"""P02 material-economy contracts: commodities, organizations, technologies.

This module freezes the Intermediate-8 ontology and the formal organization
layer before any engine module is written. All defaults are synthetic
engineering fixtures (``structural_assumption / not_calibrated /
not_assessed``); nothing here is a historical Hungarian estimate.

Stage model: ``food`` carries two legal stock stages (``raw``/``ready``);
every other commodity is ``standard`` only. A route may never change stage;
raw->ready happens only inside a declared food-processing technology.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal, Self, cast

import numpy as np
from pydantic import Field, model_validator

from hsm_lab.contract.base import ConfigError, FiniteFloat, StrictModel

if TYPE_CHECKING:  # pragma: no cover - annotation-only; avoids an import cycle
    from hsm_lab.contract.households import HouseholdCatalog, HouseholdParameters

Stage = Literal["standard", "raw", "ready"]
STAGES: tuple[Stage, ...] = ("standard", "raw", "ready")
STAGE_CODES: dict[str, int] = {"standard": 0, "raw": 1, "ready": 2}


class StockableStageError(ConfigError):
    """A stage/commodity combination that the ontology forbids."""


class CommoditySpec(StrictModel):
    """One declared material commodity.

    ``stages`` is the commodity's declared stage axis.  ``hub_stages`` /
    ``retail_stages`` mark the stages the distribution layer stocks (a commodity
    can be collected in one stage and sold in another, as food is), and
    ``investment`` marks the commodity that can be installed as project WIP.
    Adding a commodity is therefore a data change: the stage rules are read from
    here instead of being hardcoded per id.
    """

    id: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    stockable: bool = True
    household_channel: bool = False
    stages: tuple[Stage, ...] = ("standard",)
    hub_stages: tuple[Stage, ...] = ()
    retail_stages: tuple[Stage, ...] = ()
    investment: bool = False

    def stage_codes(self) -> tuple[int, ...]:
        return tuple(STAGE_CODES[stage] for stage in self.stages)

    def consumable_stage(self) -> Stage:
        """The stage a commodity is delivered, imported or exported in."""
        return (self.retail_stages or self.hub_stages or self.stages)[0]


def commodity_spec(commodity_id: str) -> CommoditySpec:
    """Declared spec for one commodity id (raises ``ConfigError`` if unknown)."""
    spec = _COMMODITY_SPEC_BY_ID.get(commodity_id)
    if spec is None:
        raise ConfigError(f"commodity {commodity_id!r} is not declared in the registry")
    return spec


def legal_stages(commodity_id: str) -> tuple[Stage, ...]:
    """The stages a commodity may legally sit in, read from the registry."""
    return commodity_spec(commodity_id).stages


P02_COMMODITY_SPECS: tuple[CommoditySpec, ...] = (
    CommoditySpec(
        id="energy",
        unit="p02_energy_unit",
        household_channel=True,
        hub_stages=("standard",),
        retail_stages=("standard",),
    ),
    CommoditySpec(
        id="capital_goods",
        unit="p02_capital_unit",
        investment=True,
    ),
    CommoditySpec(
        id="food",
        unit="p02_food_unit",
        household_channel=True,
        stages=("raw", "ready"),
        hub_stages=("raw", "ready"),
        retail_stages=("ready",),
    ),
    CommoditySpec(
        id="consumer_goods",
        unit="p02_consumer_unit",
        household_channel=True,
        hub_stages=("standard",),
        retail_stages=("standard",),
    ),
    CommoditySpec(id="raw_materials", unit="p02_raw_unit"),
    CommoditySpec(id="construction", unit="p02_construction_unit", investment=True),
    CommoditySpec(
        id="durable_goods",
        unit="p02_durable_unit",
        household_channel=True,
        hub_stages=("standard",),
        retail_stages=("standard",),
    ),
    CommoditySpec(
        id="services_transport",
        unit="p02_service_unit",
        stockable=False,
        household_channel=True,
        retail_stages=("standard",),
    ),
)

P02_COMMODITY_IDS: tuple[str, ...] = tuple(spec.id for spec in P02_COMMODITY_SPECS)
COMMODITY_INDEX: dict[str, int] = {
    spec_id: index for index, spec_id in enumerate(P02_COMMODITY_IDS)
}


def _declared_pairs(pairs: tuple[tuple[str, str], ...]) -> tuple[tuple[str, str], ...]:
    """Filter ``(commodity, stage)`` pairs to declared ones, order preserved.

    The order is part of the canonical cell ordering (and therefore of the run
    digest), so it is declared once here rather than implied by registry order.
    A new commodity joins the distribution layer by adding its pair below.
    """
    declared = {
        (spec.id, stage)
        for spec in P02_COMMODITY_SPECS
        for stage in (*spec.hub_stages, *spec.retail_stages)
    }
    return tuple(pair for pair in pairs if pair in declared)


# What the wholesale hubs stock (and therefore collect), in canonical order.
HUB_COMMODITY_STAGES: tuple[tuple[str, str], ...] = _declared_pairs(
    (
        ("food", "raw"),
        ("food", "ready"),
        ("energy", "standard"),
        ("consumer_goods", "standard"),
        ("durable_goods", "standard"),
    )
)
# What regional retail holds: services arrive same-tick into the ephemeral
# retail pool and expire at the end of the quarter.
RETAIL_COMMODITY_STAGES: tuple[tuple[str, str], ...] = _declared_pairs(
    (
        ("energy", "standard"),
        ("food", "ready"),
        ("consumer_goods", "standard"),
        ("durable_goods", "standard"),
        ("services_transport", "standard"),
    )
)
INVESTMENT_COMMODITY_IDS: tuple[str, ...] = tuple(
    spec.id for spec in P02_COMMODITY_SPECS if spec.investment
)


# ---------------------------------------------------------------------------
# P05 F2 historical ontology (BASELINE §9.2 G1; P05 §A)
#
# Frozen 16-group runtime commodity axis.  Every unit is an explicit
# "fixed-1960-composition volume unit" for that group; featured-series
# conversions (tonnes, thousand units) are declared separately in the data
# manifest and never summed across groups.  All stage/hub/retail/role
# assignments here are the declared structural freeze, not historical
# observations.
# ---------------------------------------------------------------------------

F2_COMMODITY_SPECS: tuple[CommoditySpec, ...] = (
    CommoditySpec(
        id="g01_solid_fuels",
        unit="f2_solid_fuel_1960_unit",
        household_channel=True,
        hub_stages=("standard",),
        retail_stages=("standard",),
    ),
    CommoditySpec(
        id="g02_oil_gas_fuels",
        unit="f2_liquid_fuel_1960_unit",
        household_channel=True,
        hub_stages=("standard",),
        retail_stages=("standard",),
    ),
    CommoditySpec(
        id="g03_electricity_heat",
        unit="f2_electricity_heat_1960_unit",
        stockable=False,
        household_channel=True,
        retail_stages=("standard",),
    ),
    CommoditySpec(id="g04_basic_metals_materials", unit="f2_basic_material_1960_unit"),
    CommoditySpec(id="g05_chemicals_fertilizer", unit="f2_chemical_1960_unit"),
    CommoditySpec(
        id="g06_machinery_capital",
        unit="f2_machinery_1960_unit",
        investment=True,
    ),
    CommoditySpec(
        id="g07_construction",
        unit="f2_construction_1960_unit",
        investment=True,
    ),
    CommoditySpec(
        id="g08_agricultural_raw",
        unit="f2_agri_raw_1960_unit",
        stages=("raw",),
        hub_stages=("raw",),
    ),
    CommoditySpec(
        id="g09_basic_food",
        unit="f2_basic_food_1960_unit",
        household_channel=True,
        stages=("ready",),
        hub_stages=("ready",),
        retail_stages=("ready",),
    ),
    CommoditySpec(
        id="g10_animal_food",
        unit="f2_animal_food_1960_unit",
        household_channel=True,
        stages=("ready",),
        hub_stages=("ready",),
        retail_stages=("ready",),
    ),
    CommoditySpec(
        id="g11_textiles_footwear",
        unit="f2_textile_1960_unit",
        household_channel=True,
        hub_stages=("standard",),
        retail_stages=("standard",),
    ),
    CommoditySpec(
        id="g12_household_nondurables",
        unit="f2_nondurable_1960_unit",
        household_channel=True,
        hub_stages=("standard",),
        retail_stages=("standard",),
    ),
    CommoditySpec(
        id="g13_household_durables",
        unit="f2_durable_1960_unit",
        household_channel=True,
        hub_stages=("standard",),
        retail_stages=("standard",),
    ),
    CommoditySpec(
        id="g14_vehicles_transport_equipment",
        unit="f2_vehicle_1960_unit",
        household_channel=True,
        hub_stages=("standard",),
        retail_stages=("standard",),
    ),
    CommoditySpec(
        id="g15_market_services",
        unit="f2_market_service_1960_unit",
        stockable=False,
        household_channel=True,
        retail_stages=("standard",),
    ),
    CommoditySpec(
        id="g16_housing_public_services",
        unit="f2_public_service_1960_unit",
        stockable=False,
        household_channel=True,
        retail_stages=("standard",),
    ),
)

F2_COMMODITY_IDS: tuple[str, ...] = tuple(spec.id for spec in F2_COMMODITY_SPECS)

#: Declared family roles for the F2 catalog (P05 §A.1 role column).  A role
#: names which distinguished engine behaviour a commodity carries; the mapping
#: is frozen data, never inferred from id order.
F2_COMMODITY_ROLES: dict[str, tuple[str, ...]] = {
    "g01_solid_fuels": ("energy",),
    "g02_oil_gas_fuels": ("energy",),
    "g03_electricity_heat": ("energy", "same_quarter_service"),
    "g04_basic_metals_materials": ("raw",),
    "g05_chemicals_fertilizer": ("raw",),
    "g06_machinery_capital": ("capital",),
    "g07_construction": ("construction",),
    "g08_agricultural_raw": ("agricultural_raw", "food_raw"),
    "g09_basic_food": ("food",),
    "g10_animal_food": ("food",),
    "g11_textiles_footwear": ("light",),
    "g12_household_nondurables": ("light",),
    "g13_household_durables": ("durable",),
    "g14_vehicles_transport_equipment": ("durable", "vehicle"),
    "g15_market_services": ("service", "same_quarter_service"),
    "g16_housing_public_services": ("service", "public", "same_quarter_service"),
}


@dataclass(frozen=True)
class MaterialCatalog:
    """One frozen runtime commodity axis plus its declared family roles."""

    catalog_id: str
    specs: tuple[CommoditySpec, ...]
    roles: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(spec.id for spec in self.specs)

    @property
    def index(self) -> dict[str, int]:
        return {spec.id: position for position, spec in enumerate(self.specs)}

    def spec(self, commodity_id: str) -> CommoditySpec:
        for spec in self.specs:
            if spec.id == commodity_id:
                return spec
        raise ConfigError(
            f"commodity {commodity_id!r} is not declared in catalog {self.catalog_id!r}"
        )

    def has_role(self, commodity_id: str, role: str) -> bool:
        return role in self.roles.get(commodity_id, ())

    def with_role(self, role: str) -> tuple[str, ...]:
        return tuple(cid for cid in self.ids if self.has_role(cid, role))

    @property
    def household_channel_ids(self) -> tuple[str, ...]:
        return tuple(spec.id for spec in self.specs if spec.household_channel)

    @property
    def hub_commodity_stages(self) -> tuple[tuple[str, str], ...]:
        return _declared_pairs_for(self.specs, hub=True)

    @property
    def retail_commodity_stages(self) -> tuple[tuple[str, str], ...]:
        return _declared_pairs_for(self.specs, retail=True)

    @property
    def investment_commodity_ids(self) -> tuple[str, ...]:
        return tuple(spec.id for spec in self.specs if spec.investment)


def _declared_pairs_for(
    specs: Sequence[CommoditySpec], *, hub: bool = False, retail: bool = False
) -> tuple[tuple[str, str], ...]:
    """All ``(commodity, stage)`` hub/retail pairs in declared spec order."""
    pairs: list[tuple[str, str]] = []
    for spec in specs:
        stages = spec.hub_stages if hub else (spec.retail_stages if retail else spec.stages)
        for stage in stages:
            pair = (spec.id, stage)
            if pair not in pairs:
                pairs.append(pair)
    return tuple(pairs)


INTERMEDIATE8_CATALOG = MaterialCatalog(
    catalog_id="intermediate8_v1",
    specs=P02_COMMODITY_SPECS,
    roles={
        "energy": ("energy",),
        "capital_goods": ("capital",),
        "food": ("food", "food_raw"),
        "consumer_goods": ("light",),
        "raw_materials": ("raw",),
        "construction": ("construction",),
        "durable_goods": ("durable",),
        "services_transport": ("service", "same_quarter_service"),
    },
)
F2_CATALOG = MaterialCatalog(
    catalog_id="f2_v1",
    specs=F2_COMMODITY_SPECS,
    roles=F2_COMMODITY_ROLES,
)
CATALOGS: dict[str, MaterialCatalog] = {
    INTERMEDIATE8_CATALOG.catalog_id: INTERMEDIATE8_CATALOG,
    F2_CATALOG.catalog_id: F2_CATALOG,
}
DEFAULT_CATALOG_ID = INTERMEDIATE8_CATALOG.catalog_id


def get_catalog(catalog_id: str) -> MaterialCatalog:
    catalog = CATALOGS.get(catalog_id)
    if catalog is None:
        raise ConfigError(f"unknown material catalog {catalog_id!r}")
    return catalog


def catalog_for_commodities(commodity_ids: Sequence[str]) -> MaterialCatalog:
    """Resolve the frozen catalog that declares every one of ``commodity_ids``.

    A scenario may declare a subset of a frozen catalog (the P02 fixtures omit
    the capital axis); because the frozen id sets are disjoint, a subset belongs
    to at most one catalog.  An id owned by no catalog is a ConfigError.
    """
    declared = frozenset(commodity_ids)
    matches = [
        catalog for catalog in CATALOGS.values() if declared <= frozenset(catalog.ids)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ConfigError(
            f"commodity axis does not belong to any frozen catalog: {sorted(declared)}"
        )
    raise ConfigError(f"commodity axis is ambiguous across catalogs: {sorted(declared)}")


# Union registry so ``commodity_spec`` resolves every frozen ontology id.
_COMMODITY_SPEC_BY_ID = {
    spec.id: spec for spec in (*P02_COMMODITY_SPECS, *F2_COMMODITY_SPECS)
}


class OrganizationType(StrEnum):
    """The eight P02 organization types (exact vocabulary)."""

    INDUSTRIAL_SOE = "industrial_soe"
    AGRICULTURAL_COOPERATIVE = "agricultural_cooperative"
    STATE_FARM = "state_farm"
    CONSTRUCTION = "construction"
    TRANSPORT = "transport"
    WHOLESALE_PROCURMENT = "wholesale_procurement"
    RETAIL = "retail"
    PUBLIC_SERVICE = "public_service"
    BANK = "bank"


ORGANIZATION_TYPE_ORDER: tuple[OrganizationType, ...] = (
    OrganizationType.INDUSTRIAL_SOE,
    OrganizationType.AGRICULTURAL_COOPERATIVE,
    OrganizationType.STATE_FARM,
    OrganizationType.CONSTRUCTION,
    OrganizationType.TRANSPORT,
    OrganizationType.WHOLESALE_PROCURMENT,
    OrganizationType.RETAIL,
    OrganizationType.PUBLIC_SERVICE,
    OrganizationType.BANK,
)
PRODUCTIVE_TYPES = frozenset(
    {
        OrganizationType.INDUSTRIAL_SOE,
        OrganizationType.AGRICULTURAL_COOPERATIVE,
        OrganizationType.STATE_FARM,
        OrganizationType.CONSTRUCTION,
        OrganizationType.TRANSPORT,
        OrganizationType.PUBLIC_SERVICE,
    }
)
TRADER_TYPES = frozenset({OrganizationType.WHOLESALE_PROCURMENT, OrganizationType.RETAIL})

# Industrial technologies in canonical order; capacity totals below follow it.
INDUSTRIAL_TECHNOLOGY_IDS: tuple[str, ...] = (
    "energy_generation",
    "raw_materials_production",
    "capital_goods_production",
    "food_processing",
    "consumer_goods_production",
    "durable_goods_production",
)

# Six industrial capacity totals: energy/raw/capital/food-processing/consumer/durable.
# energy 36,000 and raw_materials 34,000 are the smallest declared totals that keep
# the declared target vector input-feasible with headroom. At the 0.9 utilization
# target the whole-economy input requirement is 22,365 + 0.045 * C_energy for energy
# and 21,150 + 0.072 * C_raw for raw materials (both sectors consume themselves), so
# the earlier 30,000 / 20,000 pair demanded 22,590 raw-material units against an
# 18,000 supply (ratio 0.797) and made the synthetic fixture physically infeasible.
# The chosen pair holds supply/use ratios of ~1.35 and ~1.30 respectively.
INDUSTRIAL_CAPACITY_TOTALS: tuple[float, ...] = (
    36000.0,
    34000.0,
    8000.0,
    40000.0,
    22000.0,
    1000.0,
)
FARM_CAPACITY_TOTAL = 60000.0
CONSTRUCTION_CAPACITY_TOTAL = 8000.0
TRANSPORT_CAPACITY_TOTAL = 70000.0
WHOLESALE_HANDLING_TOTAL = 180000.0
RETAIL_HANDLING_TOTAL = 80000.0

DEFAULT_STRATEGIC_IMPORTANCE: dict[str, float] = {
    "energy_generation": 1.0,
    "capital_goods_production": 1.0,
    "raw_materials_production": 0.8,
    "food_processing": 0.8,
    "field_farming": 0.8,
    "building_construction": 0.7,
    "freight_transport": 1.0,
    "wholesale_procurement": 0.7,
    "retail": 0.7,
    "consumer_goods_production": 0.3,
    "durable_goods_production": 0.3,
    "public_service": 0.8,
    "bank": 0.0,
    # P05 F2 technologies
    "solid_fuels_production": 1.0,
    "oil_gas_production": 1.0,
    "utilities_production": 1.0,
    "basic_materials_production": 0.8,
    "chemicals_production": 0.8,
    "machinery_production": 1.0,
    "food_processing_f2": 0.8,
    "light_goods_production": 0.3,
    "durables_vehicles_production": 0.3,
    "market_services_production": 0.5,
    "field_farming_f2": 0.8,
    "building_construction_f2": 0.7,
    "freight_transport_f2": 1.0,
    "public_services": 0.8,
}

ExportRole = Literal["none", "cmea", "convertible", "both"]

FiniteFraction = Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]
NonNegativeFloat = Annotated[FiniteFloat, Field(ge=0.0)]
PositiveFloat = Annotated[FiniteFloat, Field(gt=0.0)]


class OrganizationSpec(StrictModel):
    """One declared organization (plan step 1 field contract, exact keys)."""

    organization_id: int = Field(strict=True, ge=0)
    type: OrganizationType
    region_id: str = Field(min_length=1)
    sector_id: str | None = None
    technology_id: str | None = None
    bank_id: int | None = None
    strategic_importance: FiniteFloat = Field(ge=0.0, le=1.0)
    ministry_id: str | None = None
    export_role: ExportRole = "none"
    capacity: NonNegativeFloat = 0.0
    labor_available: NonNegativeFloat = 0.0
    labor_per_activity: PositiveFloat | None = None
    handling_capacity: NonNegativeFloat = 0.0
    initial_cash: NonNegativeFloat = 0.0
    initial_loan_principal: NonNegativeFloat = 0.0
    initial_bailout_expectation: FiniteFloat = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_type_shape(self) -> Self:
        kind = self.type
        if kind is OrganizationType.BANK:
            if self.technology_id is not None:
                raise ConfigError(
                    f"bank organization {self.organization_id} must not declare a technology"
                )
            if self.capacity != 0.0:
                raise ConfigError(f"bank organization {self.organization_id} has fixed capacity 0")
            if self.handling_capacity != 0.0:
                raise ConfigError(
                    f"bank organization {self.organization_id} has fixed handling_capacity 0"
                )
            if self.labor_available != 0.0 or self.labor_per_activity is not None:
                raise ConfigError(f"bank organization {self.organization_id} has no material labor")
            if self.bank_id is not None:
                raise ConfigError(
                    f"bank organization {self.organization_id} must not carry bank_id"
                )
            if self.initial_loan_principal != 0.0:
                raise ConfigError(f"bank organization {self.organization_id} cannot borrow")
        if kind in TRADER_TYPES:
            if self.technology_id is not None:
                raise ConfigError(f"trader {self.organization_id} must not declare a technology")
            if self.capacity != 0.0:
                raise ConfigError(f"trader {self.organization_id} has fixed capacity 0")
            if self.handling_capacity <= 0.0:
                raise ConfigError(
                    f"trader {self.organization_id} requires a positive handling_capacity"
                )
            if self.labor_per_activity is not None and self.labor_available <= 0.0:
                raise ConfigError(
                    f"trader {self.organization_id} declares labor_per_activity without labor"
                )
        if kind in PRODUCTIVE_TYPES:
            if self.technology_id is None:
                raise ConfigError(
                    f"productive organization {self.organization_id} requires a technology_id"
                )
            if self.capacity <= 0.0:
                raise ConfigError(
                    f"productive organization {self.organization_id} requires capacity > 0"
                )
            if self.labor_available <= 0.0 or self.labor_per_activity is None:
                raise ConfigError(
                    f"productive organization {self.organization_id} requires labor "
                    "available and a positive labor_per_activity"
                )
            if self.handling_capacity != 0.0:
                raise ConfigError(
                    f"productive organization {self.organization_id} has fixed handling_capacity 0"
                )
        return self


class InputCoefficient(StrictModel):
    """One declared technology input row (positive only; zero cells are omitted).

    ``input_timing`` (P05 §0.4) says whether the input must be on hand as
    opening stock (``opening_stock``) or may be delivered within the same
    quarter (``same_quarter_service``).  It is derived from the commodity's
    stockability when unset: stockable -> opening stock, non-stockable ->
    same-quarter service.  An explicit value that contradicts the ontology is
    rejected rather than silently accepted.
    """

    commodity_id: str = Field(min_length=1)
    stage: Stage = "standard"
    coefficient: PositiveFloat
    input_timing: Literal["opening_stock", "same_quarter_service"] | None = None

    @model_validator(mode="after")
    def _check_timing(self) -> Self:
        if self.input_timing is not None:
            spec = commodity_spec(self.commodity_id)
            expected = "opening_stock" if spec.stockable else "same_quarter_service"
            if self.input_timing != expected:
                raise ConfigError(
                    f"input {self.commodity_id!r} is "
                    f"{'stockable' if spec.stockable else 'non-stockable'} so input_timing "
                    f"must be {expected!r}, got {self.input_timing!r}"
                )
        return self

    @property
    def resolved_input_timing(self) -> Literal["opening_stock", "same_quarter_service"]:
        """Declared timing, defaulting to the ontology's stockability rule."""
        if self.input_timing is not None:
            return self.input_timing
        return "opening_stock" if commodity_spec(self.commodity_id).stockable else (
            "same_quarter_service"
        )


class OutputCoefficient(StrictModel):
    """One declared technology output row (positive only)."""

    commodity_id: str = Field(min_length=1)
    stage: Stage = "standard"
    coefficient: PositiveFloat


class TechnologySpec(StrictModel):
    """A Leontief activity: positive input/output rows over declared commodities."""

    technology_id: str = Field(min_length=1)
    inputs: list[InputCoefficient] = Field(default_factory=list)
    outputs: list[OutputCoefficient] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_keys(self) -> Self:
        for rows, name in ((self.inputs, "inputs"), (self.outputs, "outputs")):
            keys = [(row.commodity_id, row.stage) for row in rows]
            if len(set(keys)) != len(keys):
                raise ConfigError(
                    f"technology {self.technology_id}: duplicate {name} commodity/stage key"
                )
            for row in rows:
                if row.stage not in legal_stages(row.commodity_id):
                    raise ConfigError(
                        f"technology {self.technology_id}: commodity {row.commodity_id} "
                        f"cannot carry stage {row.stage!r}"
                    )
        return self


# ----------------------------------------------------------------------
# Frozen default synthetic technologies (plan section 3).
# ----------------------------------------------------------------------


def _tech(
    technology_id: str,
    inputs: tuple[tuple[str, float] | tuple[str, str, float], ...],
    outputs: tuple[tuple[str, Stage, float], ...],
) -> TechnologySpec:
    input_rows = [
        InputCoefficient(
            commodity_id=row[0],
            stage=cast("Stage", row[1]) if len(row) == 3 else "standard",
            coefficient=row[-1],
        )
        for row in inputs
    ]
    return TechnologySpec(
        technology_id=technology_id,
        inputs=input_rows,
        outputs=[OutputCoefficient(commodity_id=c, stage=s, coefficient=v) for c, s, v in outputs],
    )


def default_technologies() -> list[TechnologySpec]:
    """The frozen synthetic technology set (agriculture is an endogenous chain)."""
    return [
        _tech(
            "energy_generation",
            (("energy", 0.05), ("raw_materials", 0.05), ("capital_goods", 0.005)),
            (("energy", "standard", 1.0),),
        ),
        _tech(
            "raw_materials_production",
            (("energy", 0.30), ("raw_materials", 0.08), ("capital_goods", 0.005)),
            (("raw_materials", "standard", 1.0),),
        ),
        _tech(
            "capital_goods_production",
            (("energy", 0.25), ("raw_materials", 0.50), ("services_transport", 0.02)),
            (("capital_goods", "standard", 1.0),),
        ),
        _tech(
            "food_processing",
            (
                ("food", "raw", 1.25),
                ("energy", 0.15),
                ("raw_materials", 0.10),
                ("capital_goods", 0.005),
            ),
            (("food", "ready", 1.0),),
        ),
        _tech(
            "consumer_goods_production",
            (
                ("energy", 0.15),
                ("raw_materials", 0.30),
                ("capital_goods", 0.005),
                ("services_transport", 0.02),
            ),
            (("consumer_goods", "standard", 1.0),),
        ),
        _tech(
            "durable_goods_production",
            (
                ("energy", 0.25),
                ("raw_materials", 0.80),
                ("capital_goods", 0.01),
                ("services_transport", 0.03),
            ),
            (("durable_goods", "standard", 1.0),),
        ),
        _tech(
            "building_construction",
            (
                ("energy", 0.10),
                ("raw_materials", 0.60),
                ("capital_goods", 0.01),
                ("services_transport", 0.02),
            ),
            (("construction", "standard", 1.0),),
        ),
        _tech(
            "freight_transport",
            (("energy", 0.05), ("capital_goods", 0.002)),
            (("services_transport", "standard", 1.0),),
        ),
        _tech(
            "field_farming",
            (("energy", 0.05), ("raw_materials", 0.03), ("capital_goods", 0.002)),
            (("food", "raw", 1.0),),
        ),
    ]


TECHNOLOGY_BY_ID = {t.technology_id: t for t in default_technologies()}

# Technology each productive organization type carries by default.
TYPE_TECHNOLOGY_IDS: dict[OrganizationType, tuple[str, ...]] = {
    OrganizationType.INDUSTRIAL_SOE: INDUSTRIAL_TECHNOLOGY_IDS,
    OrganizationType.AGRICULTURAL_COOPERATIVE: ("field_farming",),
    OrganizationType.STATE_FARM: ("field_farming",),
    OrganizationType.CONSTRUCTION: ("building_construction",),
    OrganizationType.TRANSPORT: ("freight_transport",),
    OrganizationType.PUBLIC_SERVICE: ("public_services",),
}


# ----------------------------------------------------------------------
# P05 F2 (16-commodity) technologies, capacity totals and profiles
# ----------------------------------------------------------------------

#: Industrial technologies in canonical order for the F2 catalog (10 sectors);
#: agriculture runs as coop/farm, construction and transport keep their own
#: organization types, and public services carry ``public_services``.
F2_INDUSTRIAL_TECHNOLOGY_IDS: tuple[str, ...] = (
    "solid_fuels_production",
    "oil_gas_production",
    "utilities_production",
    "basic_materials_production",
    "chemicals_production",
    "machinery_production",
    "food_processing_f2",
    "light_goods_production",
    "durables_vehicles_production",
    "market_services_production",
)

F2_INDUSTRIAL_CAPACITY_TOTALS: tuple[float, ...] = (
    40000.0,
    22000.0,
    30000.0,
    34000.0,
    20000.0,
    12000.0,
    26000.0,
    24000.0,
    14000.0,
    18000.0,
)
F2_FARM_CAPACITY_TOTAL = 60000.0
F2_CONSTRUCTION_CAPACITY_TOTAL = 10000.0
F2_TRANSPORT_CAPACITY_TOTAL = 60000.0
F2_PUBLIC_CAPACITY_TOTAL = 20000.0


def f2_default_technologies() -> list[TechnologySpec]:
    """Declared F2 Leontief technology set (grade-S structural fixture)."""
    return [
        _tech(
            "solid_fuels_production",
            (("g06_machinery_capital", 0.01), ("g05_chemicals_fertilizer", 0.005)),
            (("g01_solid_fuels", "standard", 1.0),),
        ),
        _tech(
            "oil_gas_production",
            (("g01_solid_fuels", 0.02), ("g06_machinery_capital", 0.01)),
            (("g02_oil_gas_fuels", "standard", 1.0),),
        ),
        _tech(
            "utilities_production",
            (
                ("g01_solid_fuels", 0.15),
                ("g02_oil_gas_fuels", 0.05),
                ("g06_machinery_capital", 0.01),
            ),
            (("g03_electricity_heat", "standard", 1.0),),
        ),
        _tech(
            "basic_materials_production",
            (
                ("g01_solid_fuels", 0.20),
                ("g02_oil_gas_fuels", 0.05),
                ("g03_electricity_heat", 0.05),
                ("g05_chemicals_fertilizer", 0.05),
                ("g06_machinery_capital", 0.02),
            ),
            (("g04_basic_metals_materials", "standard", 1.0),),
        ),
        _tech(
            "chemicals_production",
            (
                ("g01_solid_fuels", 0.10),
                ("g02_oil_gas_fuels", 0.15),
                ("g03_electricity_heat", 0.05),
                ("g04_basic_metals_materials", 0.05),
                ("g06_machinery_capital", 0.02),
            ),
            (("g05_chemicals_fertilizer", "standard", 1.0),),
        ),
        _tech(
            "machinery_production",
            (
                ("g03_electricity_heat", 0.05),
                ("g04_basic_metals_materials", 0.30),
                ("g05_chemicals_fertilizer", 0.05),
                ("g06_machinery_capital", 0.02),
            ),
            (("g06_machinery_capital", "standard", 1.0),),
        ),
        _tech(
            "food_processing_f2",
            (
                ("g03_electricity_heat", 0.02),
                ("g06_machinery_capital", 0.005),
                ("g08_agricultural_raw", "raw", 0.80),
            ),
            (
                ("g09_basic_food", "ready", 0.60),
                ("g10_animal_food", "ready", 0.40),
            ),
        ),
        _tech(
            "light_goods_production",
            (
                ("g03_electricity_heat", 0.03),
                ("g04_basic_metals_materials", 0.02),
                ("g05_chemicals_fertilizer", 0.05),
                ("g06_machinery_capital", 0.01),
            ),
            (
                ("g11_textiles_footwear", "standard", 0.50),
                ("g12_household_nondurables", "standard", 0.50),
            ),
        ),
        _tech(
            "durables_vehicles_production",
            (
                ("g03_electricity_heat", 0.03),
                ("g04_basic_metals_materials", 0.20),
                ("g05_chemicals_fertilizer", 0.05),
                ("g06_machinery_capital", 0.05),
            ),
            (
                ("g13_household_durables", "standard", 0.60),
                ("g14_vehicles_transport_equipment", "standard", 0.40),
            ),
        ),
        _tech(
            "market_services_production",
            (("g03_electricity_heat", 0.05), ("g06_machinery_capital", 0.01)),
            (
                ("g15_market_services", "standard", 0.70),
                ("g16_housing_public_services", "standard", 0.30),
            ),
        ),
        _tech(
            "field_farming_f2",
            (
                ("g02_oil_gas_fuels", 0.03),
                ("g05_chemicals_fertilizer", 0.05),
                ("g06_machinery_capital", 0.005),
            ),
            (("g08_agricultural_raw", "raw", 1.0),),
        ),
        _tech(
            "building_construction_f2",
            (
                ("g03_electricity_heat", 0.02),
                ("g04_basic_metals_materials", 0.30),
                ("g05_chemicals_fertilizer", 0.05),
                ("g06_machinery_capital", 0.02),
                ("g07_construction", 0.10),
            ),
            (("g07_construction", "standard", 1.0),),
        ),
        _tech(
            "freight_transport_f2",
            (("g02_oil_gas_fuels", 0.05), ("g06_machinery_capital", 0.002)),
            (("g15_market_services", "standard", 1.0),),
        ),
        _tech(
            "public_services",
            (("g03_electricity_heat", 0.03), ("g06_machinery_capital", 0.01)),
            (("g16_housing_public_services", "standard", 1.0),),
        ),
    ]


F2_TYPE_TECHNOLOGY_IDS: dict[OrganizationType, tuple[str, ...]] = {
    OrganizationType.INDUSTRIAL_SOE: F2_INDUSTRIAL_TECHNOLOGY_IDS,
    OrganizationType.AGRICULTURAL_COOPERATIVE: ("field_farming_f2",),
    OrganizationType.STATE_FARM: ("field_farming_f2",),
    OrganizationType.CONSTRUCTION: ("building_construction_f2",),
    OrganizationType.TRANSPORT: ("freight_transport_f2",),
    OrganizationType.PUBLIC_SERVICE: ("public_services",),
}


F2_ORGANIZATION_PROFILES: dict[str, dict[OrganizationType, int]] = {
    "p05_300": {
        OrganizationType.INDUSTRIAL_SOE: 200,
        OrganizationType.AGRICULTURAL_COOPERATIVE: 45,
        OrganizationType.STATE_FARM: 15,
        OrganizationType.CONSTRUCTION: 4,
        OrganizationType.TRANSPORT: 4,
        OrganizationType.WHOLESALE_PROCURMENT: 2,
        OrganizationType.RETAIL: 20,
        OrganizationType.PUBLIC_SERVICE: 5,
        OrganizationType.BANK: 5,
    },
    "p05_400": {
        OrganizationType.INDUSTRIAL_SOE: 250,
        OrganizationType.AGRICULTURAL_COOPERATIVE: 60,
        OrganizationType.STATE_FARM: 20,
        OrganizationType.CONSTRUCTION: 8,
        OrganizationType.TRANSPORT: 8,
        OrganizationType.WHOLESALE_PROCURMENT: 4,
        OrganizationType.RETAIL: 20,
        OrganizationType.PUBLIC_SERVICE: 20,
        OrganizationType.BANK: 10,
    },
    "p05_450": {
        OrganizationType.INDUSTRIAL_SOE: 280,
        OrganizationType.AGRICULTURAL_COOPERATIVE: 75,
        OrganizationType.STATE_FARM: 25,
        OrganizationType.CONSTRUCTION: 8,
        OrganizationType.TRANSPORT: 8,
        OrganizationType.WHOLESALE_PROCURMENT: 4,
        OrganizationType.RETAIL: 20,
        OrganizationType.PUBLIC_SERVICE: 20,
        OrganizationType.BANK: 10,
    },
}


# ----------------------------------------------------------------------
# Private plots (plan section 3): fixed coefficients, recipe-carried split.
# ----------------------------------------------------------------------


class ForcingBinding(StrictModel):
    """Scenario-side declaration that one external variable feeds the runtime.

    Only EXOGENOUS_FORCING artifacts may bind; targets/initials/parameters
    can never enter ``initialize_material``/``tick_material`` through this.
    """

    variable_id: str = Field(min_length=1)
    artifact_id: str | None = None
    required_period_start: str = Field(min_length=1)
    required_period_end: str = Field(min_length=1)


MATERIAL_FORCING_VARIABLE_IDS = frozenset(
    {
        "world_oil_price",
        "global_usd_rate",
        "official_fx",
        "cmea_energy_price",
    }
)


class PrivatePlotRecipe(StrictModel):
    """Declared private-plot channel (grade S structural assumption)."""

    role: Literal["initial_state"] = "initial_state"
    evidence_status: Literal["structural_assumption"] = "structural_assumption"
    calibration_status: Literal["not_calibrated"] = "not_calibrated"
    participation_fraction: FiniteFraction = 0.2
    capacity_per_participating_person: PositiveFloat = 0.15
    self_use_fraction: Annotated[FiniteFloat, Field(ge=0.0, le=0.75)] = 0.5
    spare_time_labor_fraction: PositiveFloat = 0.05
    plot_labor_per_activity: PositiveFloat = 0.2
    input_energy: PositiveFloat = 0.02
    input_raw_materials: PositiveFloat = 0.01
    input_capital_goods: PositiveFloat = 0.001
    output_raw_share: PositiveFloat = 0.25

    @property
    def direct_market_fraction(self) -> float:
        return 0.75 - self.self_use_fraction


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


class CellOwnerKind(StrEnum):
    """Owner kinds that may hold a material stock cell (banks never do)."""

    ORGANIZATION = "organization"
    PLOT = "plot"
    PROJECT = "project"
    TREASURY_IMPORT = "treasury_import"
    SECOND_ECONOMY = "second_economy"


class StockCellRef(StrictModel):
    """Config-level addressing of one stock cell (resolved at compile time)."""

    owner_kind: CellOwnerKind
    organization_id: int | None = None
    region_id: str | None = None
    pool: Literal["input", "output", "wholesale", "retail", "wip", "import_pool"] = "output"
    commodity_id: str = Field(min_length=1)
    stage: Stage = "standard"

    @model_validator(mode="after")
    def _check_shape(self) -> Self:
        if self.owner_kind is CellOwnerKind.ORGANIZATION and self.organization_id is None:
            raise ConfigError("organization stock cell requires organization_id")
        if self.owner_kind in (CellOwnerKind.PLOT, CellOwnerKind.PROJECT) and (
            self.region_id is None
        ):
            raise ConfigError(f"{self.owner_kind.value} stock cell requires region_id")
        if self.owner_kind is CellOwnerKind.TREASURY_IMPORT and self.region_id is not None:
            raise ConfigError("national import pool cell must not carry a region")
        if self.stage not in legal_stages(self.commodity_id):
            raise ConfigError(f"commodity {self.commodity_id} cannot carry stage {self.stage!r}")
        return self


class RoutePurpose(StrEnum):
    """Exact route purpose vocabulary (plan step 2)."""

    INTERMEDIATE = "intermediate"
    INVESTMENT = "investment"
    HOUSING = "housing"
    PROCUREMENT = "procurement"
    RETAIL = "retail"
    PRIVATE_PLOT = "private_plot"
    EXPORT_CMEA = "export_cmea"
    EXPORT_CONVERTIBLE = "export_convertible"
    HOUSEHOLD = "household"
    SECOND_ECONOMY = "second_economy"


PURPOSE_CODES: dict[RoutePurpose, int] = {
    purpose: index for index, purpose in enumerate(RoutePurpose)
}


class MaterialRouteSpec(StrictModel):
    """One declared supply edge: source cell -> destination cell for a purpose."""

    source: StockCellRef
    destination: StockCellRef
    purpose: RoutePurpose
    weight: PositiveFloat
    transport_organization_id: int | None = None

    @model_validator(mode="after")
    def _check_stage(self) -> Self:
        if self.source.commodity_id != self.destination.commodity_id:
            raise ConfigError(
                f"route {self.source.commodity_id}->{self.destination.commodity_id} "
                "must keep one commodity; stage conversion is a technology, not a route"
            )
        if self.source.stage != self.destination.stage:
            raise ConfigError(
                f"route {self.source.commodity_id} changes stage "
                f"{self.source.stage}->{self.destination.stage}: transfers never convert stage"
            )
        return self


# ----------------------------------------------------------------------
# Organization recipe profiles
# ----------------------------------------------------------------------

ORGANIZATION_PROFILES: dict[str, dict[OrganizationType, int]] = {
    "p02_100": {
        OrganizationType.INDUSTRIAL_SOE: 60,
        OrganizationType.AGRICULTURAL_COOPERATIVE: 15,
        OrganizationType.STATE_FARM: 5,
        OrganizationType.CONSTRUCTION: 4,
        OrganizationType.TRANSPORT: 4,
        OrganizationType.WHOLESALE_PROCURMENT: 1,
        OrganizationType.RETAIL: 10,
        OrganizationType.BANK: 1,
    },
    "p02_200": {
        OrganizationType.INDUSTRIAL_SOE: 120,
        OrganizationType.AGRICULTURAL_COOPERATIVE: 30,
        OrganizationType.STATE_FARM: 10,
        OrganizationType.CONSTRUCTION: 8,
        OrganizationType.TRANSPORT: 8,
        OrganizationType.WHOLESALE_PROCURMENT: 3,
        OrganizationType.RETAIL: 20,
        OrganizationType.BANK: 1,
    },
    "p02_400": {
        OrganizationType.INDUSTRIAL_SOE: 240,
        OrganizationType.AGRICULTURAL_COOPERATIVE: 60,
        OrganizationType.STATE_FARM: 20,
        OrganizationType.CONSTRUCTION: 16,
        OrganizationType.TRANSPORT: 16,
        OrganizationType.WHOLESALE_PROCURMENT: 6,
        OrganizationType.RETAIL: 40,
        OrganizationType.BANK: 2,
    },
}
ORGANIZATION_PROFILES.update(F2_ORGANIZATION_PROFILES)


OrganizationProfile = Literal[
    "p02_100", "p02_200", "p02_400", "p05_300", "p05_400", "p05_450"
]
"""Frozen organization profile sizes (count switch targets)."""


class OrganizationRecipe(StrictModel):
    """Profile selection plus optional full-spec overrides (same ids only)."""

    profile: OrganizationProfile = "p02_200"
    overrides: list[OrganizationSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_overrides(self) -> Self:
        ids = [o.organization_id for o in self.overrides]
        if len(set(ids)) != len(ids):
            raise ConfigError("organization_recipe overrides repeat an organization_id")
        return self


# ----------------------------------------------------------------------
# Parameters
# ----------------------------------------------------------------------


def _fixed_vector(name: str, length: int) -> object:
    return Annotated[list[FiniteFloat], Field(min_length=length, max_length=length)]


class TradeParameters(StrictModel):
    """Channel x commodity trade vectors (plan section 5, exact defaults)."""

    cmea_prices: list[FiniteFloat] = Field(
        default=[1.0, 4.0, 2.0, 3.0, 1.5, 5.0, 12.0, 1.0], min_length=1
    )
    convertible_prices: list[FiniteFloat] = Field(
        default=[1.0, 4.0, 2.0, 3.0, 1.5, 5.0, 12.0, 1.0], min_length=1
    )
    cmea_desired_imports: list[FiniteFloat] = Field(
        default=[3000.0, 500.0, 0.0, 0.0, 5000.0, 0.0, 0.0, 0.0], min_length=1
    )
    convertible_desired_imports: list[FiniteFloat] = Field(
        default=[500.0, 1000.0, 100.0, 200.0, 1000.0, 0.0, 50.0, 0.0],
        min_length=1,
    )
    cmea_export_demands: list[FiniteFloat] = Field(
        default=[0.0, 100.0, 100.0, 0.0, 0.0, 0.0, 0.0, 0.0], min_length=1
    )
    convertible_export_demands: list[FiniteFloat] = Field(
        default=[0.0, 100.0, 0.0, 100.0, 0.0, 0.0, 0.0, 0.0], min_length=1
    )
    cmea_credit_envelope: PositiveFloat = 10000.0
    convertible_opening_reserve: NonNegativeFloat = 20000.0
    convertible_loan_limit: NonNegativeFloat = 5000.0
    convertible_opening_principal: NonNegativeFloat = 0.0

    def flatten(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for name in (
            "cmea_prices",
            "convertible_prices",
            "cmea_desired_imports",
            "convertible_desired_imports",
            "cmea_export_demands",
            "convertible_export_demands",
        ):
            for index, value in enumerate(getattr(self, name)):
                out[f"{name}.{index}"] = value
        for name in (
            "cmea_credit_envelope",
            "convertible_opening_reserve",
            "convertible_loan_limit",
            "convertible_opening_principal",
        ):
            out[name] = getattr(self, name)
        return out

    @model_validator(mode="after")
    def _check_vectors(self) -> Self:
        for name in (
            "cmea_prices",
            "convertible_prices",
            "cmea_desired_imports",
            "convertible_desired_imports",
            "cmea_export_demands",
            "convertible_export_demands",
        ):
            vector = getattr(self, name)
            if any(not math.isfinite(v) or v < 0 for v in vector):
                raise ConfigError(f"trade.{name} must be finite and non-negative")
        for name in ("cmea_prices", "convertible_prices"):
            if any(v <= 0 for v in getattr(self, name)):
                raise ConfigError(f"trade.{name} must be strictly positive")
        return self

    def check_axis(self, commodity_ids: Sequence[str]) -> None:
        """Validate the six commodity-indexed trade vectors against a declared axis."""
        size = len(commodity_ids)
        for name in (
            "cmea_prices",
            "convertible_prices",
            "cmea_desired_imports",
            "convertible_desired_imports",
            "cmea_export_demands",
            "convertible_export_demands",
        ):
            if len(getattr(self, name)) != size:
                raise ConfigError(
                    f"trade.{name} must have one entry per declared commodity "
                    f"({size}), got {len(getattr(self, name))}"
                )


class MaterialParameters(StrictModel):
    """Intermediate-8 model constants (plan step 1 load-bearing literal keys)."""

    role: Literal["latent_parameter"] = "latent_parameter"
    evidence_status: Literal["structural_assumption"] = "structural_assumption"
    calibration_status: Literal["not_calibrated"] = "not_calibrated"
    sensitivity_status: Literal["not_assessed"] = "not_assessed"
    notes: str = (
        "Synthetic Intermediate-8 engineering constants; not historical Hungarian "
        "magnitudes and not calibrated against any observed series."
    )
    # Admin prices (standard food slot represents ready food).
    prices: list[FiniteFloat] = Field(
        default=[1.0, 4.0, 2.0, 3.0, 1.5, 5.0, 12.0, 1.0], min_length=1
    )
    food_raw_price: PositiveFloat = 0.8
    utilization: Annotated[FiniteFloat, Field(gt=0.0, le=1.0)] = 0.9
    # Same-tick service split: logistics / productive / household, sums to 1.
    service_split: list[FiniteFloat] = Field(default=[0.7, 0.2, 0.1], min_length=3, max_length=3)
    # Shortage mechanism toggles (default OFF so the mechanism is opt-in).
    overorder_strength: NonNegativeFloat = 0.0
    hoarding_quarters: NonNegativeFloat = 0.0
    shortage_alpha: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.25
    # Labor and finance.
    wage_rate: PositiveFloat = 6.0
    credit_envelope_fraction: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.5
    # P05 §0.6: cap on standing principal as a multiple of an organization's
    # quarterly wage bill (0 = unlimited). A positive cap makes the money stock
    # stationary in the closure control instead of growing with every drawdown.
    credit_stock_cap_quarters: NonNegativeFloat = 0.0
    #: A commodity that declares retail stages but no hub stage (F2's g03
    #: electricity and g16 public services) otherwise has no replenishment route
    #: at all, so its household demand can never materialise.  Off by default:
    #: only catalogs that declare such commodities may opt in.
    retail_replenishment_fallback: bool = False
    # P05 §0.5: apply the wholesale/retail distribution margin to trader sales
    # (off by default until the treasury border continuity is margin-aware).
    distribution_margins_enabled: bool = True
    # P05 §0.6: fund working capital from a fixed M2-neutral credit fund deposit
    # instead of the banks creating new deposits (off = legacy creation).
    m2_neutral_credit: bool = False
    # P05 §0.6: keep loss-makers solvent by an M2-neutral surplus->deficit transfer.
    sbc_redistribution: bool = False
    # P05 §0.6: cap production by output-cell cover so no inventory accumulates.
    demand_limited_targets: bool = False
    # P05 §0.6: production cover multiple of realized consumption.
    demand_cover: float = 1.0
    # P05 §0.6: share of exogenous household demand kept as a production floor.
    demand_floor: float = 0.0
    # P05 §0.6: relative slack on the bank-deposit coverage identity (float64
    # accumulation only; 0 keeps the legacy absolute-only tolerance).
    money_tolerance_rel: float = 0.0
    # P05 §0.6: production target rule. ``leontief_upper_bound`` caps each
    # commodity's gross output at (I - M)^-1 d, damped by ``leontief_damping``
    # and floored at ``leontief_floor`` x the capacity target.  Measured
    # (P05 kernel diagnostic): with d = declared household basket only it still
    # drains to the zero fixed point because the H0 control declares no
    # investment/housing/export final demand, so the capital/construction
    # activities are capped to zero and the wage base collapses with them.
    production_target_rule: Literal["legacy", "leontief_upper_bound", "lean_plan"] = "legacy"
    leontief_damping: float = 1.0
    leontief_floor: float = 0.0
    # P05 §0.6: pure replacement investment — each productive organization
    # orders ``rate x capacity`` of new capacity per quarter (funded cash-first
    # through the existing investment pipeline).  0 disables it.
    capital_depreciation_rate: float = 0.0
    bailout_envelope_fraction: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.25
    bailout_alpha: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.25
    domestic_credit_rate_annual: Annotated[FiniteFloat, Field(ge=0.0)] = 0.04
    hungary_spread_annual: NonNegativeFloat = 0.02
    principal_repayment_fraction: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.05
    hunger_base: NonNegativeFloat = 0.02
    hunger_bailout: NonNegativeFloat = 0.05
    hunger_shortage: NonNegativeFloat = 0.05
    # Transport and handling.
    transport_per_unit: NonNegativeFloat = 0.05
    handling_work_per_unit: list[FiniteFloat] = Field(default=[1.0] * 8, min_length=1)
    # External anchors.
    world_oil_reference: PositiveFloat = 1.63
    oil_warmup_price: PositiveFloat = 1.6
    cmea_base_energy_price: PositiveFloat = 1.0
    cmea_uncertainty_multiplier: PositiveFloat = 1.0
    allocation_order: Literal["production_first", "investment_first"] = "production_first"
    farm_seasonal_factors: list[FiniteFloat] = Field(
        default=[0.5, 0.8, 1.8, 0.9], min_length=4, max_length=4
    )
    capacity_capital_goods_per_unit: PositiveFloat = 0.25
    capacity_construction_per_unit: PositiveFloat = 0.25
    trade: TradeParameters = Field(default_factory=TradeParameters)

    @model_validator(mode="after")
    def _check_vectors(self) -> Self:
        for name in ("prices", "handling_work_per_unit"):
            vector = getattr(self, name)
            if any(not math.isfinite(v) or v < 0 for v in vector):
                raise ConfigError(f"{name} must be finite and non-negative")
        if any(v <= 0 for v in self.prices):
            raise ConfigError("prices must be strictly positive")
        if sum(self.service_split) != 1.0 or any(v < 0 for v in self.service_split):
            raise ConfigError("service_split must be non-negative and sum to exactly 1")
        if any(not math.isfinite(v) or v < 0 for v in self.farm_seasonal_factors):
            raise ConfigError("farm_seasonal_factors must be finite and non-negative")
        return self

    def check_axis(self, commodity_ids: Sequence[str]) -> None:
        """Validate every commodity-indexed vector against a declared axis.

        Called by the scenario/registry gate once the commodity axis is known, so
        the parameter set itself carries no fixed commodity count.
        """
        size = len(commodity_ids)
        for name in (
            "prices",
            "handling_work_per_unit",
        ):
            if len(getattr(self, name)) != size:
                raise ConfigError(
                    f"{name} must have one entry per declared commodity "
                    f"({size}), got {len(getattr(self, name))}"
                )
        self.trade.check_axis(commodity_ids)

    def flatten(self) -> dict[str, float]:
        """Field/index-path flattening for the run's parameter hash."""
        vector: dict[str, float] = {
            "food_raw_price": self.food_raw_price,
            "utilization": self.utilization,
            "overorder_strength": self.overorder_strength,
            "hoarding_quarters": self.hoarding_quarters,
            "shortage_alpha": self.shortage_alpha,
            "wage_rate": self.wage_rate,
            "credit_envelope_fraction": self.credit_envelope_fraction,
            "credit_stock_cap_quarters": self.credit_stock_cap_quarters,
            "distribution_margins_enabled": (
                1.0 if self.distribution_margins_enabled else 0.0
            ),
            "m2_neutral_credit": 1.0 if self.m2_neutral_credit else 0.0,
            "sbc_redistribution": 1.0 if self.sbc_redistribution else 0.0,
            "demand_limited_targets": 1.0 if self.demand_limited_targets else 0.0,
            "demand_cover": float(self.demand_cover),
            "demand_floor": float(self.demand_floor),
            "money_tolerance_rel": float(self.money_tolerance_rel),
            "production_target_rule.leontief_upper_bound": (
                1.0 if self.production_target_rule == "leontief_upper_bound" else 0.0
            ),
            "production_target_rule.lean_plan": (
                1.0 if self.production_target_rule == "lean_plan" else 0.0
            ),
            "leontief_damping": float(self.leontief_damping),
            "leontief_floor": float(self.leontief_floor),
            "capital_depreciation_rate": float(self.capital_depreciation_rate),
            "bailout_envelope_fraction": self.bailout_envelope_fraction,
            "bailout_alpha": self.bailout_alpha,
            "domestic_credit_rate_annual": self.domestic_credit_rate_annual,
            "hungary_spread_annual": self.hungary_spread_annual,
            "principal_repayment_fraction": self.principal_repayment_fraction,
            "hunger_base": self.hunger_base,
            "hunger_bailout": self.hunger_bailout,
            "hunger_shortage": self.hunger_shortage,
            "transport_per_unit": self.transport_per_unit,
            "world_oil_reference": self.world_oil_reference,
            "oil_warmup_price": self.oil_warmup_price,
            "cmea_base_energy_price": self.cmea_base_energy_price,
            "cmea_uncertainty_multiplier": self.cmea_uncertainty_multiplier,
            "capacity_capital_goods_per_unit": self.capacity_capital_goods_per_unit,
            "capacity_construction_per_unit": self.capacity_construction_per_unit,
            "allocation_order.production_first": (
                1.0 if self.allocation_order == "production_first" else 0.0
            ),
        }
        for name in (
            "prices",
            "service_split",
            "handling_work_per_unit",
            "farm_seasonal_factors",
        ):
            for index, value in enumerate(getattr(self, name)):
                vector[f"{name}.{index}"] = value
        for name, value in self.trade.flatten().items():
            vector[f"trade.{name}"] = value
        return vector


class MaterialInitialRecipe(StrictModel):
    """Declared synthetic initial state (grade S; every identity is hash-bound)."""

    role: Literal["initial_state"] = "initial_state"
    grade: Literal["S"] = "S"
    evidence_status: Literal["structural_assumption"] = "structural_assumption"
    observation_at: None = None
    input_stock_quarters: PositiveFloat = 1.0
    output_stock_quarters: PositiveFloat = 1.0
    dwelling_per_person: NonNegativeFloat = 0.4
    household_cash: NonNegativeFloat = 0.0
    organization_deposit_quarters: PositiveFloat = 2.0
    treasury_deposit_quarters: PositiveFloat = 10.0
    bank_equity_quarters: PositiveFloat = 1.0
    initial_bailout_prior: FiniteFraction = 0.5
    bank_initial_bailout_prior: FiniteFraction = 0.0
    # Working capital for the distribution layer (wholesale + retail), expressed
    # as quarters of the declared national quarterly goods-flow value and funded
    # M2-neutrally by reducing the Treasury's opening deposit. Without it the
    # only bridge between producers and households is structurally insolvent.
    distribution_working_capital_quarters: NonNegativeFloat = 1.0
    #: Quarters of national wage bill held as the M2-neutral credit fund deposit.
    credit_fund_quarters: NonNegativeFloat = 0.0

    def flatten(self) -> dict[str, float]:
        return {
            "input_stock_quarters": self.input_stock_quarters,
            "output_stock_quarters": self.output_stock_quarters,
            "dwelling_per_person": self.dwelling_per_person,
            "household_cash": self.household_cash,
            "organization_deposit_quarters": self.organization_deposit_quarters,
            "treasury_deposit_quarters": self.treasury_deposit_quarters,
            "bank_equity_quarters": self.bank_equity_quarters,
            "initial_bailout_prior": self.initial_bailout_prior,
            "bank_initial_bailout_prior": self.bank_initial_bailout_prior,
            "distribution_working_capital_quarters": (self.distribution_working_capital_quarters),
            "credit_fund_quarters": self.credit_fund_quarters,
        }


# ----------------------------------------------------------------------
# Initial conditions (drawn once, shared by network + state builders)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class HouseholdInitial:
    """Per-represented-household initial arrays (canonical id order 0..N-1)."""

    household_id: np.ndarray  # int64 (N,)
    region: np.ndarray  # int32 (N,)
    weight: np.ndarray  # float64 (N,)
    size: np.ndarray  # float64 (N,)
    plot_participating: np.ndarray  # bool (N,)
    # --- P03 static attributes (all canonical id order) ------------------
    urban: np.ndarray  # bool (N,)
    occupation: np.ndarray  # int8 (N,) occupation ordinal
    sector: np.ndarray  # int16 (N,) sector ordinal
    education: np.ndarray  # int8 (N,) education ordinal
    children: np.ndarray  # int16 (N,)
    adults: np.ndarray  # int16 (N,)
    elderly: np.ndarray  # int16 (N,)
    working_adults: np.ndarray  # float64 (N,)
    pay_weight: np.ndarray  # float64 (N,)
    second_participating: np.ndarray  # bool (N,)
    western_exposure: np.ndarray  # float64 (N,)
    informal_access: np.ndarray  # float64 (N,)
    tenure: np.ndarray  # int8 (N,) initial tenure ordinal
    durable_owned: np.ndarray  # float64 (N, D) initial ownership rate
    people_total: float = 0.0
    household_total: float = 0.0
    achieved_margins: dict[str, float] = field(default_factory=dict)
    static_hash: str = ""


@dataclass(frozen=True)
class MaterialInitialConditions:
    """Readonly bridge between the single initialization draw and the engine.

    ``network``/``state`` builders consume this; nobody re-draws household
    sizes or re-derives organization capacities with placeholder labor.
    """

    scenario_id: str
    region_ids: tuple[str, ...]
    commodity_ids: tuple[str, ...]
    seed: int
    stochastic: bool
    households: HouseholdInitial
    organizations: tuple[OrganizationSpec, ...]
    technologies: tuple[TechnologySpec, ...]
    routes: tuple[MaterialRouteSpec, ...] | None
    plot_recipe: PrivatePlotRecipe
    equivalent_persons: float
    region_equivalent_persons: np.ndarray  # float64 (R,)
    parameters: MaterialParameters
    initial_recipe: MaterialInitialRecipe
    household_parameters: HouseholdParameters | None = None
    household_catalog: HouseholdCatalog | None = None
    distribution_working_capital: float = 0.0

    @property
    def organization_count(self) -> int:
        return len(self.organizations)


def wholesale_hub_regions(count: int) -> tuple[int, ...]:
    """Deterministic wholesale hub region indices (200-profile pins 0/7/14)."""
    if count == 1:
        return (0,)
    if count == 3:
        return (0, 7, 14)
    return tuple(index * 20 // count for index in range(count))


__all__ = [
    "CATALOGS",
    "COMMODITY_INDEX",
    "CONSTRUCTION_CAPACITY_TOTAL",
    "CellOwnerKind",
    "DEFAULT_CATALOG_ID",
    "F2_CATALOG",
    "F2_COMMODITY_IDS",
    "F2_COMMODITY_ROLES",
    "F2_COMMODITY_SPECS",
    "FARM_CAPACITY_TOTAL",
    "HouseholdInitial",
    "INDUSTRIAL_CAPACITY_TOTALS",
    "INDUSTRIAL_TECHNOLOGY_IDS",
    "INTERMEDIATE8_CATALOG",
    "MaterialCatalog",
    "P02_COMMODITY_IDS",
    "InputCoefficient",
    "MaterialInitialConditions",
    "MaterialInitialRecipe",
    "MaterialParameters",
    "MaterialRouteSpec",
    "ORGANIZATION_TYPE_ORDER",
    "OrganizationRecipe",
    "OrganizationSpec",
    "OrganizationType",
    "P02_COMMODITY_SPECS",
    "PrivatePlotRecipe",
    "PURPOSE_CODES",
    "RETAIL_HANDLING_TOTAL",
    "RoutePurpose",
    "STAGES",
    "STAGE_CODES",
    "StockableStageError",
    "StockCellRef",
    "TECHNOLOGY_BY_ID",
    "TRANSPORT_CAPACITY_TOTAL",
    "TYPE_TECHNOLOGY_IDS",
    "TradeParameters",
    "WHOLESALE_HANDLING_TOTAL",
    "catalog_for_commodities",
    "commodity_spec",
    "get_catalog",
    "HUB_COMMODITY_STAGES",
    "RETAIL_COMMODITY_STAGES",
    "INVESTMENT_COMMODITY_IDS",
    "legal_stages",
    "default_technologies",
    "wholesale_hub_regions",
]
