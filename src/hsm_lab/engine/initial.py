"""One-shot material initial conditions (P02 plan steps 1 and 3).

``build_material_initial_conditions`` performs the single initialization
draw: household sizes/weights/regions/plot cohorts once through the RNG
registry, then the complete organization list with every numeric field
final at construction time (no placeholder-then-fill).  Network and state
builders consume the frozen :class:`MaterialInitialConditions` and never
re-draw households or re-derive organization labor/cash.

Labor identities (plan step 3): the initial labor budget is the actual
represented person count, 90% distributed across physical activity
capacity and 10% evenly across traders, so each productive organization
can sustain 1.2x its physical capacity before labor binds.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from hsm_lab.contract.households import (
    compile_household_catalog,
)
from hsm_lab.contract.material import (
    COMMODITY_INDEX,
    CONSTRUCTION_CAPACITY_TOTAL,
    DEFAULT_STRATEGIC_IMPORTANCE,
    FARM_CAPACITY_TOTAL,
    INDUSTRIAL_CAPACITY_TOTALS,
    INDUSTRIAL_TECHNOLOGY_IDS,
    ORGANIZATION_PROFILES,
    ORGANIZATION_TYPE_ORDER,
    P02_COMMODITY_IDS,
    PRODUCTIVE_TYPES,
    RETAIL_HANDLING_TOTAL,
    TRADER_TYPES,
    TRANSPORT_CAPACITY_TOTAL,
    TYPE_TECHNOLOGY_IDS,
    WHOLESALE_HANDLING_TOTAL,
    ExportRole,
    MaterialInitialConditions,
    MaterialParameters,
    OrganizationSpec,
    OrganizationType,
    PrivatePlotRecipe,
    TechnologySpec,
)
from hsm_lab.contract.schemas import ConfigError, ScenarioSpec
from hsm_lab.engine.households import build_synthetic_households
from hsm_lab.engine.rng import RngRegistry

#: Fraction of represented persons assigned to physical activities.
_PHYSICAL_LABOR_SHARE = 0.9
#: Labor headroom over physical capacity each productive organization gets.
_LABOR_CAPACITY_HEADROOM = 1.2


def _organization_slots(
    profile: dict[OrganizationType, int],
) -> list[tuple[OrganizationType, str | None, float]]:
    """Canonical ``(type, technology_id, capacity)`` slots in org-id order.

    One global sequence in ``ORGANIZATION_TYPE_ORDER``; industrial slots are
    grouped by the six ``INDUSTRIAL_TECHNOLOGY_IDS`` technologies.
    """
    technology_count = len(INDUSTRIAL_TECHNOLOGY_IDS)
    farm_count = profile.get(OrganizationType.AGRICULTURAL_COOPERATIVE, 0) + profile.get(
        OrganizationType.STATE_FARM, 0
    )
    slots: list[tuple[OrganizationType, str | None, float]] = []
    for org_type in ORGANIZATION_TYPE_ORDER:
        count = int(profile.get(org_type, 0))
        if org_type is OrganizationType.INDUSTRIAL_SOE:
            if count % technology_count:
                raise ConfigError(
                    f"industrial count {count} does not split evenly across the "
                    f"{technology_count} industrial technologies"
                )
            per_technology = count // technology_count
            for index, technology_id in enumerate(INDUSTRIAL_TECHNOLOGY_IDS):
                capacity = (
                    INDUSTRIAL_CAPACITY_TOTALS[index] / per_technology if per_technology else 0.0
                )
                slots.extend([(org_type, technology_id, capacity)] * per_technology)
            continue
        if org_type in (
            OrganizationType.AGRICULTURAL_COOPERATIVE,
            OrganizationType.STATE_FARM,
        ):
            capacity = FARM_CAPACITY_TOTAL / farm_count if farm_count else 0.0
        elif org_type is OrganizationType.CONSTRUCTION:
            capacity = CONSTRUCTION_CAPACITY_TOTAL / count if count else 0.0
        elif org_type is OrganizationType.TRANSPORT:
            capacity = TRANSPORT_CAPACITY_TOTAL / count if count else 0.0
        else:
            capacity = 0.0
        slot_technology_id = (
            TYPE_TECHNOLOGY_IDS[org_type][0] if org_type in PRODUCTIVE_TYPES else None
        )
        slots.extend([(org_type, slot_technology_id, capacity)] * count)
    return slots


def _validate_references(
    organizations: tuple[OrganizationSpec, ...],
    technologies: list[TechnologySpec],
) -> None:
    """Technology and bank foreign keys over the final organization list."""
    declared = {technology.technology_id for technology in technologies}
    bank_ids = {org.organization_id for org in organizations if org.type is OrganizationType.BANK}
    for org in organizations:
        if org.type in PRODUCTIVE_TYPES:
            if org.technology_id is None:  # OrganizationSpec validation prevents this
                raise ConfigError(
                    f"productive organization {org.organization_id} lacks a technology"
                )
            if org.technology_id not in declared:
                raise ConfigError(
                    f"organization {org.organization_id} uses undeclared technology "
                    f"{org.technology_id!r}"
                )
            if org.technology_id not in TYPE_TECHNOLOGY_IDS[org.type]:
                raise ConfigError(
                    f"organization {org.organization_id} of type {org.type.value} "
                    f"cannot carry technology {org.technology_id!r}"
                )
        if org.type is not OrganizationType.BANK and (
            org.bank_id is None or org.bank_id not in bank_ids
        ):
            raise ConfigError(
                f"organization {org.organization_id} bank_id {org.bank_id} does not "
                "reference a bank organization"
            )


def _quarterly_flow_value(
    parameters: MaterialParameters,
    technologies: Sequence[TechnologySpec],
    slots: Sequence[tuple[OrganizationType, str | None, float]],
    equivalent_persons: float,
) -> float:
    """Declared quarterly goods-flow value used to size distribution capital.

    Production input value (technology coefficients x admin prices at the
    utilization target) plus the household basket value at the declared
    per-person quantities. This is an engineering conversion over synthetic
    admin prices — not a historical flow.
    """
    price_by_id = {
        commodity_id: float(parameters.prices[index])
        for commodity_id, index in COMMODITY_INDEX.items()
    }
    technology_by_id = {technology.technology_id: technology for technology in technologies}
    input_value = 0.0
    for org_type, technology_id, capacity in slots:
        if org_type not in PRODUCTIVE_TYPES or technology_id is None:
            continue
        target = min(
            float(parameters.utilization) * capacity,
            _LABOR_CAPACITY_HEADROOM * capacity,
        )
        technology = technology_by_id[technology_id]
        for row in technology.inputs:
            price = price_by_id.get(row.commodity_id)
            if price is None:
                raise ConfigError(
                    f"technology {technology_id} consumes undeclared commodity {row.commodity_id!r}"
                )
            input_value += row.coefficient * price * target
    household_value = (
        sum(
            float(parameters.prices[COMMODITY_INDEX[commodity_id]])
            for commodity_id in P02_COMMODITY_IDS
            if commodity_id in price_by_id
        )
        * equivalent_persons
    )
    return input_value + household_value


def build_material_initial_conditions(
    spec: ScenarioSpec, rng: RngRegistry
) -> MaterialInitialConditions:
    """Draw the readonly material initial conditions exactly once (plan step 1).

    Household sizes come from one ``rng.uniform`` call when stochastic;
    organization specs are built complete (region = canonical org id modulo
    the region count, capacities split per profile totals, labor/cash final)
    and then ``organization_recipe.overrides`` replace whole slots by exact
    organization id.
    """
    if spec.kind != "material":
        raise ConfigError(
            f"build_material_initial_conditions requires kind='material', got {spec.kind!r}"
        )
    parameters = spec.material_parameters
    initial_recipe = spec.material_initial
    recipe = spec.organization_recipe
    technologies = spec.technologies
    if parameters is None or initial_recipe is None or recipe is None or technologies is None:
        raise ConfigError(
            "material scenario lacks material_parameters/material_initial/"
            "organization_recipe/technologies"
        )

    # ScenarioSpec carries no plot fields; the contract default recipe is the
    # declared synthetic plot channel (grade S structural assumption).
    plot_recipe = PrivatePlotRecipe()
    households = build_synthetic_households(spec, rng)
    region_count = len(spec.region_ids)
    region_persons = np.bincount(
        np.asarray(households.region, dtype=np.int64),
        weights=(households.weight * households.size).astype(np.float64),
        minlength=region_count,
    )
    equivalent_persons = float(region_persons.sum())
    household_parameters = spec.household_parameters
    if household_parameters is None:
        raise ConfigError("material scenario must declare household_parameters")
    household_catalog = compile_household_catalog(
        household_parameters, parameters, tuple(spec.commodities)
    )

    profile = ORGANIZATION_PROFILES[recipe.profile]
    slots = _organization_slots(profile)
    organization_count = len(slots)

    physical_capacity_total = sum(
        capacity for org_type, _, capacity in slots if org_type in PRODUCTIVE_TYPES
    )  # noqa: E501
    if physical_capacity_total <= 0.0:
        raise ConfigError("organization profile declares no productive capacity")
    physical_labor_per_activity = (_PHYSICAL_LABOR_SHARE * equivalent_persons) / (
        _LABOR_CAPACITY_HEADROOM * physical_capacity_total
    )
    trader_count = sum(1 for org_type, _, _ in slots if org_type in TRADER_TYPES)
    trader_labor = (
        (1.0 - _PHYSICAL_LABOR_SHARE) * equivalent_persons / trader_count if trader_count else 0.0
    )
    wholesale_count = int(profile.get(OrganizationType.WHOLESALE_PROCURMENT, 0))
    retail_count = int(profile.get(OrganizationType.RETAIL, 0))
    bank_org_ids = [
        org_id for org_id, (org_type, _, _) in enumerate(slots) if org_type is OrganizationType.BANK
    ]
    if not bank_org_ids and organization_count > 0:
        raise ConfigError("organization profile has organizations but no bank to bind accounts to")

    wage_rate = parameters.wage_rate
    total_handling = sum(
        (
            WHOLESALE_HANDLING_TOTAL / wholesale_count
            if org_type is OrganizationType.WHOLESALE_PROCURMENT
            else RETAIL_HANDLING_TOTAL / retail_count
        )
        for org_type, _, _ in slots
        if org_type in TRADER_TYPES
    )
    quarterly_flow_value = _quarterly_flow_value(
        parameters, technologies, slots, equivalent_persons
    )
    distribution_capital_total = (
        float(initial_recipe.distribution_working_capital_quarters) * quarterly_flow_value
    )
    generated: list[OrganizationSpec] = []
    generated_working_capital: dict[int, float] = {}
    for org_id, (org_type, technology_id, capacity) in enumerate(slots):
        working_capital = 0.0
        if org_type in PRODUCTIVE_TYPES:
            # 90% of represented persons by capacity share: labor can sustain
            # 1.2x capacity (labor_available / labor_per_activity).
            labor_available = _LABOR_CAPACITY_HEADROOM * capacity * physical_labor_per_activity
            labor_per_activity: float | None = physical_labor_per_activity
            handling_capacity = 0.0
            sector_id: str | None = technology_id
            assert technology_id is not None  # productive slots always carry one
            strategic = DEFAULT_STRATEGIC_IMPORTANCE.get(technology_id)
            export_role: ExportRole = (
                "both" if org_type is OrganizationType.INDUSTRIAL_SOE else "none"
            )
        elif org_type in TRADER_TYPES:
            labor_available = trader_labor
            labor_per_activity = 1.0
            handling_capacity = (
                WHOLESALE_HANDLING_TOTAL / wholesale_count
                if org_type is OrganizationType.WHOLESALE_PROCURMENT
                else RETAIL_HANDLING_TOTAL / retail_count
            )
            working_capital = (
                distribution_capital_total * handling_capacity / total_handling
                if total_handling > 0.0
                else 0.0
            )
            generated_working_capital[org_id] = working_capital
            sector_id = "distribution"
            strategic = DEFAULT_STRATEGIC_IMPORTANCE.get(org_type.value)
            export_role = "none"
        else:  # bank: no material capacity, labor, handling or technology
            labor_available = 0.0
            labor_per_activity = None
            handling_capacity = 0.0
            sector_id = "finance"
            strategic = DEFAULT_STRATEGIC_IMPORTANCE.get("bank")
            export_role = "none"
        if strategic is None:
            raise ConfigError(f"no default strategic importance for organization {org_id}")
        bank_id = (
            None if org_type is OrganizationType.BANK else bank_org_ids[org_id % len(bank_org_ids)]
        )
        bailout_prior = (
            initial_recipe.bank_initial_bailout_prior
            if org_type is OrganizationType.BANK
            else initial_recipe.initial_bailout_prior
        )
        generated.append(
            OrganizationSpec(
                organization_id=org_id,
                type=org_type,
                region_id=spec.region_ids[org_id % region_count],
                sector_id=sector_id,
                technology_id=technology_id,
                bank_id=bank_id,
                strategic_importance=strategic,
                ministry_id=None,
                export_role=export_role,
                capacity=capacity,
                labor_available=labor_available,
                labor_per_activity=labor_per_activity,
                handling_capacity=handling_capacity,
                initial_cash=(
                    initial_recipe.organization_deposit_quarters * wage_rate * labor_available
                    + working_capital
                ),
                initial_loan_principal=0.0,
                initial_bailout_expectation=bailout_prior,
            )
        )

    # Full-spec overrides replace whole slots; no field-level merge.
    override_by_id: dict[int, OrganizationSpec] = {}
    for override in recipe.overrides:
        if override.organization_id in override_by_id:
            raise ConfigError(
                "organization_recipe overrides repeat an organization_id: "
                f"{override.organization_id}"
            )
        override_by_id[override.organization_id] = override
    unknown = sorted(set(override_by_id) - set(range(organization_count)))
    if unknown:
        raise ConfigError(f"organization_recipe overrides reference unknown id(s) {unknown}")
    organizations = tuple(
        override_by_id.get(org_id, generated[org_id]) for org_id in range(organization_count)
    )
    _validate_references(organizations, technologies)

    # Only generated (non-overridden) traders carry the working-capital line;
    # the Treasury's opening deposit is reduced by exactly this amount so the
    # money stock is unchanged (M2-neutral reallocation).
    distribution_working_capital = float(
        sum(
            value
            for org_id, value in generated_working_capital.items()
            if org_id not in override_by_id
        )
    )

    return MaterialInitialConditions(
        scenario_id=spec.scenario_id,
        region_ids=tuple(spec.region_ids),
        commodity_ids=tuple(spec.commodities),
        seed=rng.seed,
        stochastic=spec.stochastic,
        households=households,
        organizations=organizations,
        technologies=tuple(technologies),
        routes=tuple(spec.routes) if spec.routes is not None else None,
        plot_recipe=plot_recipe,
        equivalent_persons=equivalent_persons,
        region_equivalent_persons=region_persons,
        parameters=parameters,
        initial_recipe=initial_recipe,
        household_parameters=household_parameters,
        household_catalog=household_catalog,
        distribution_working_capital=distribution_working_capital,
    )


__all__ = ["build_material_initial_conditions"]
