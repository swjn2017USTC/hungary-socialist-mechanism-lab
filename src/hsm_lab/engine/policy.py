"""P04 policy bridge: compile a declared PolicyVector into runtime parameters.

The bridge is the single place where political policy touches the material
economy.  It maps the 19 declared coordinates onto *relative* multipliers over
the immutable base ``MaterialParameters`` / ``HouseholdParameters`` (never
per-quarter compounding), recompiles the household price catalog when prices
actually move, and carries the central-vs-local planning mix through
:class:`TickControls`.

Political state never gets a handle that writes stock/cash/debt/production:
every realized quantity is still produced by the material kernel and the
finance journal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.households import (
    HouseholdCatalog,
    HouseholdParameters,
    compile_household_catalog,
)
from hsm_lab.contract.material import (
    MaterialParameters,
)
from hsm_lab.contract.politics import ExternalWorldSlice, PolicyVector

__all__ = ["EffectivePolicy", "TickControls", "compile_effective_policy"]


@dataclass(frozen=True)
class TickControls:
    """Runtime controls handed to one material tick (never a state writer)."""

    material_parameters: MaterialParameters
    household_parameters: HouseholdParameters
    household_catalog: HouseholdCatalog
    autonomy: float
    central_target: np.ndarray | None = None  # float64 (P,) or None for the local rule
    policy: PolicyVector | None = None


@dataclass(frozen=True)
class EffectivePolicy:
    """Compiled runtime parameters for one admitted quarter."""

    policy: PolicyVector
    material_parameters: MaterialParameters
    household_parameters: HouseholdParameters
    household_catalog: HouseholdCatalog
    controls: TickControls
    price_changed: bool


def _household_parent_channels(
    material: MaterialParameters, household: HouseholdParameters
) -> np.ndarray:
    """Boolean (G,) mask of commodities feeding the household channel."""
    ids = household.allocation.parent_commodity_ids
    mask = np.zeros(len(material.prices), dtype=bool)
    from hsm_lab.contract.material import COMMODITY_INDEX

    for commodity_id in ids:
        if commodity_id in COMMODITY_INDEX:
            mask[COMMODITY_INDEX[commodity_id]] = True
    return mask


def compile_effective_policy(
    base_material: MaterialParameters,
    base_household: HouseholdParameters,
    policy: PolicyVector,
    external: ExternalWorldSlice,
    commodity_ids: tuple[str, ...],
) -> EffectivePolicy:
    """Map a policy vector onto runtime material/household parameters."""
    material_update = base_material.model_dump()
    material_update["utilization"] = float(policy.plan_utilization)
    material_update["prices"] = [
        float(p) * float(policy.admin_price_factor) for p in base_material.prices
    ]
    material_update["food_raw_price"] = float(base_material.food_raw_price) * float(
        policy.admin_price_factor
    )
    material_update["wage_rate"] = float(base_material.wage_rate) * float(policy.wage_factor)
    material_update["credit_envelope_fraction"] = float(policy.credit_fraction)
    material_update["bailout_envelope_fraction"] = float(
        base_material.bailout_envelope_fraction
    ) * (1.0 - float(policy.budget_hardness))
    material_update["hunger_base"] = float(base_material.hunger_base) * float(
        policy.investment_intensity
    )
    material_update["allocation_order"] = (
        "investment_first" if float(policy.industrial_priority) > 0.5 else "production_first"
    )
    trade = dict(material_update["trade"])
    credit_availability = external.get("international_credit_availability", 1.0)
    trade["convertible_loan_limit"] = (
        float(base_material.trade.convertible_loan_limit)
        * float(policy.borrowing_factor)
        * float(credit_availability)
    )
    household_mask = _household_parent_channels(base_material, base_household)
    desired = list(trade["convertible_desired_imports"])
    for g, _commodity_id in enumerate(commodity_ids):
        if household_mask[g]:
            desired[g] = float(desired[g]) * float(policy.consumer_import_factor)
    trade["convertible_desired_imports"] = desired
    # External demand / energy quota channels: the declared multipliers scale
    # the base desired flows; no event adds a second shock.
    western_demand = external.get("western_demand", 1.0)
    cmea_demand = external.get("cmea_demand", 1.0)
    quota = external.get("soviet_energy_availability", 1.0)
    trade["convertible_export_demands"] = [
        float(v) * float(western_demand) for v in trade["convertible_export_demands"]
    ]
    trade["cmea_export_demands"] = [
        float(v) * float(cmea_demand) for v in trade["cmea_export_demands"]
    ]
    if "energy" in commodity_ids:
        energy_index = commodity_ids.index("energy")
        cmea_imports = list(trade["cmea_desired_imports"])
        cmea_imports[energy_index] = min(
            float(cmea_imports[energy_index]), float(quota) * float(cmea_imports[energy_index])
        )
        trade["cmea_desired_imports"] = cmea_imports
    material_update["trade"] = trade
    material = MaterialParameters.model_validate(material_update)

    household_update = base_household.model_dump()
    household_update["welfare"]["welfare_provision"] = float(policy.welfare_provision)
    household_update["welfare"]["private_autonomy"] = float(policy.private_autonomy)
    household_update["welfare"]["cultural_openness"] = float(policy.cultural_openness)
    household_update["housing"]["housing_construction_cap_per_person"] = float(
        base_household.housing.housing_construction_cap_per_person
    ) * float(policy.housing_factor)
    household_update["time"]["second_hours_cap_per_worker"] = max(
        1e-6,
        float(base_household.time.second_hours_cap_per_worker)
        * float(policy.second_economy_tolerance),
    )
    household = HouseholdParameters.model_validate(household_update)

    price_changed = bool(
        any(abs(a - b) > 1e-12 for a, b in zip(material.prices, base_material.prices, strict=True))
        or abs(material.food_raw_price - base_material.food_raw_price) > 1e-12
    )
    catalog = compile_household_catalog(household, material, tuple(commodity_ids))
    controls = TickControls(
        material_parameters=material,
        household_parameters=household,
        household_catalog=catalog,
        autonomy=float(policy.enterprise_autonomy),
        central_target=None,
        policy=policy,
    )
    return EffectivePolicy(
        policy=policy,
        material_parameters=material,
        household_parameters=household,
        household_catalog=catalog,
        controls=controls,
        price_changed=price_changed,
    )


def central_activity_target(
    *,
    plan_utilization: float,
    reported_capacity_forecast: np.ndarray,
    inventory_estimate: np.ndarray,
    activity_org: np.ndarray,
    output_coefficient: np.ndarray,
    season: np.ndarray,
) -> np.ndarray:
    """Form the lagged central target per productive activity (plan step 3).

    ``central = max(plan_utilization*reported_capacity_forecast*season
    - inventory_estimate/of_output / max(output_coefficient, eps), 0)``; for
    multi-output technologies the minimum over outputs is taken.  The estimate
    is a *published/forecast* view, never the true stock.
    """
    activity_count = int(np.asarray(season).shape[0])
    eps = 1e-12
    target = np.full(activity_count, np.inf, dtype=np.float64)
    for activity in range(activity_count):
        org = int(activity_org[activity])
        if org < 0:
            target[activity] = 0.0
            continue
        coefficient = float(output_coefficient[activity])
        if coefficient <= 0.0:
            target[activity] = 0.0
            continue
        stock_cover = float(inventory_estimate[activity]) / max(coefficient, eps)
        value = (
            float(plan_utilization)
            * float(reported_capacity_forecast[activity])
            * float(season[activity])
            - stock_cover
        )
        target[activity] = max(value, 0.0)
    return target


def default_initial_policy(spec: Any) -> PolicyVector:
    """The declared grade-S initial policy vector for a material scenario.

    Literal values: base utilization; autonomy 0.1; neutral price/wage/housing/
    borrowing/import factors; credit fraction from the base parameters; no budget
    hardness; full second-economy tolerance; base household welfare/private/
    culture; supported=0.3, tolerance=0.7, repression=0.3; no information effort.
    """
    from hsm_lab.contract.politics import PolicyVector as _PV

    parameters = spec.material_parameters
    household = spec.household_parameters
    if parameters is None or household is None:
        raise ConfigError("default_initial_policy requires a material scenario recipe")
    return _PV(
        plan_utilization=float(parameters.utilization),
        enterprise_autonomy=0.1,
        investment_intensity=1.0,
        industrial_priority=0.0 if parameters.allocation_order == "production_first" else 1.0,
        admin_price_factor=1.0,
        wage_factor=1.0,
        credit_fraction=float(parameters.credit_envelope_fraction),
        budget_hardness=0.0,
        housing_factor=1.0,
        borrowing_factor=1.0,
        consumer_import_factor=1.0,
        second_economy_tolerance=1.0,
        welfare_provision=float(household.welfare.welfare_provision),
        private_autonomy=float(household.welfare.private_autonomy),
        cultural_openness=float(household.welfare.cultural_openness),
        supported_boundary=0.3,
        tolerance_boundary=0.7,
        repression=0.3,
        information_investment=0.0,
    )
