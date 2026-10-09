"""P03 synthetic household population generator and quarterly demand (plan B/C).

Everything here is vectorized over the household axis: the generator runs once
at initialization and never again; ``form_household_demand`` is a pure array
kernel called once per tick from ``tick_material``.  No per-household Python
object, dict or history exists anywhere in this module.

Synthetic provenance: the county recipe is a declared grade-S engineering
fixture.  Changing the household *sample* size ``N`` never changes the weighted
county household/person/urban/occupation margins; only the resolution of the
synthetic attributes improves.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # pragma: no cover - annotation-only; avoids an import cycle
    from hsm_lab.engine.state import MaterialState

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.households import (
    EDUCATION_PAY_MULTIPLIER,
    HOUSEHOLD_EDUCATION_IDS,
    HOUSEHOLD_OCCUPATION_IDS,
    HOUSEHOLD_TENURE_IDS,
    OCCUPATION_SECTOR,
    CountyHouseholdSpec,
    HouseholdCatalog,
    HouseholdParameters,
)
from hsm_lab.contract.material import HouseholdInitial
from hsm_lab.contract.schemas import ScenarioSpec
from hsm_lab.engine.rng import RngRegistry

ATTRIBUTE_MODULE = "household.initial_attributes"
#: Number of independent uniform draws per household at initialization.
_ATTR_DRAWS = 5


def _size_distribution(base: np.ndarray, mean: float) -> tuple[np.ndarray, np.ndarray]:
    """Maximum-entropy size distribution matching ``mean`` by exponential tilt.

    ``p_s ∝ base_s exp(λ s)`` found by bisection on λ (no clipping of the
    declared anchor).  Extends the support with a geometric tail when
    ``mean > 6``.  Raises when the anchor is infeasible.
    """
    probs = np.asarray(base, dtype=np.float64)
    probs = probs / probs.sum()
    if mean < 0.999999:
        raise ConfigError("household mean size must be >= 1")
    if abs(mean - 1.0) < 1e-9:
        out = np.zeros_like(probs)
        out[0] = 1.0
        return np.arange(1, probs.size + 1, dtype=np.float64), out
    sizes = np.arange(1, probs.size + 1, dtype=np.float64)
    if abs(mean - 6.0) < 1e-9:
        out = np.zeros_like(probs)
        out[-1] = 1.0
        return sizes, out
    if mean > 6.0:
        extra = int(np.ceil(mean) + 2) - probs.size
        if extra > 0:
            tail = np.array([probs[-1] * 2.0 ** (-(s - probs.size)) for s in range(1, extra + 1)])
            probs = np.concatenate([probs, tail])
            probs = probs / probs.sum()
            sizes = np.arange(1, probs.size + 1, dtype=np.float64)
    lo, hi = -60.0, 60.0
    for _ in range(128):
        mid = 0.5 * (lo + hi)
        tilted = probs * np.exp(np.clip(mid * sizes, -700.0, 700.0))
        total = tilted.sum()
        if total <= 0.0:
            hi = mid
            continue
        tilted = np.asarray(tilted / total, dtype=np.float64)
        current = float(np.dot(tilted, sizes))
        if abs(current - mean) <= 1e-10:
            return np.asarray(sizes, dtype=np.float64), tilted
        if current < mean:
            lo = mid
        else:
            hi = mid
    raise ConfigError(f"size-distribution tilt failed to match mean {mean!r}")


def _largest_remainder(total: int, weights: np.ndarray, tie_order: np.ndarray) -> np.ndarray:
    """Hamilton largest-remainder integer apportionment with a deterministic tie key."""
    weights = np.asarray(weights, dtype=np.float64)
    safe = weights.sum()
    if safe <= 0.0:
        raise ConfigError("household cell masses must be positive")
    quotas = total * weights / safe
    floors = np.floor(quotas).astype(np.int64)
    remainder = int(total - floors.sum())
    if remainder > 0:
        frac = quotas - floors
        order = np.lexsort((tie_order, -frac))
        floors[order[:remainder]] += 1
    return np.asarray(floors, dtype=np.int64)


def _cells_for_county(
    county: CountyHouseholdSpec, region_ordinal: int
) -> tuple[list[tuple[int, float, int, int]], list[float]]:
    mean = county.persons_total / county.household_total
    sizes, p = _size_distribution(np.asarray(county.size_probabilities), mean)
    cells: list[tuple[int, float, int, int]] = []
    masses: list[float] = []
    for si, size in enumerate(sizes):
        for urban in (0, 1):
            p_urban = county.urban_share if urban else 1.0 - county.urban_share
            if p_urban <= 1e-12:
                continue
            for occupation in range(len(HOUSEHOLD_OCCUPATION_IDS)):
                p_occ = county.occupation_shares[occupation]
                if p_occ <= 1e-12:
                    continue
                cells.append((region_ordinal, float(size), urban, occupation))
                masses.append(county.household_total * float(p[si]) * p_urban * p_occ)
    return cells, masses


def build_synthetic_households(spec: ScenarioSpec, rng: RngRegistry) -> HouseholdInitial:
    """Draw the county-conditioned weighted synthetic household population (B)."""
    recipe = spec.household_initial
    if recipe is None:
        raise ConfigError("material scenario must declare household_initial")
    region_ids = tuple(spec.region_ids)
    if len(recipe.counties) != len(region_ids):
        raise ConfigError(
            "household_initial must declare exactly one CountyHouseholdSpec per region"
        )
    for ordinal, county in enumerate(recipe.counties):
        if county.county_id != region_ids[ordinal]:
            raise ConfigError(
                f"household_initial county {county.county_id!r} does not match region "
                f"{region_ids[ordinal]!r} at ordinal {ordinal}"
            )

    cell_keys: list[tuple[int, float, int, int]] = []
    cell_masses: list[float] = []
    for ordinal, county in enumerate(recipe.counties):
        county_cells, county_masses = _cells_for_county(county, ordinal)
        cell_keys.extend(county_cells)
        cell_masses.extend(county_masses)
    cell_count = len(cell_keys)
    sample = int(spec.households)
    if sample < cell_count:
        raise ConfigError(
            "household sample cannot cover positive county strata: "
            f"N={sample} < {cell_count} positive cells"
        )
    masses = np.asarray(cell_masses, dtype=np.float64)
    tie = np.asarray(
        [
            ((region * 7 + int(size) - 1) * 2 + urban) * 4 + occupation
            for region, size, urban, occupation in cell_keys
        ],
        dtype=np.int64,
    )
    # every positive cell gets at least one representative household; the rest
    # are apportioned by Hamilton on the cell mass, so sum(weight) == sum(mass)
    # exactly and the weighted county margins are invariant to the sample size.
    counts = np.ones(cell_count, dtype=np.int64)
    remaining = sample - cell_count
    if remaining > 0:
        counts = counts + _largest_remainder(remaining, masses, tie)
    weights = masses / counts

    def _expand(values: object) -> np.ndarray:
        return np.repeat(np.asarray(values), counts)

    region = _expand([key[0] for key in cell_keys]).astype(np.int32)
    size = _expand([key[1] for key in cell_keys]).astype(np.float64)
    urban = _expand([key[2] for key in cell_keys]).astype(bool)
    occupation = _expand([key[3] for key in cell_keys]).astype(np.int8)
    weight = _expand(weights).astype(np.float64)
    household_id = np.arange(weight.size, dtype=np.int64)

    # per-household cell ordinal for the attribute CDFs
    cell_ordinal = np.repeat(np.arange(cell_count, dtype=np.int64), counts)
    # ordinal within cell (j-th representative of its cell)
    cell_start = np.repeat(np.concatenate(([0], np.cumsum(counts)[:-1])), counts)
    within = np.arange(weight.size, dtype=np.int64) - cell_start

    children = np.empty(weight.size, dtype=np.int16)
    elderly = np.empty(weight.size, dtype=np.int16)
    adults = np.empty(weight.size, dtype=np.int16)
    education = np.empty(weight.size, dtype=np.int8)
    tenure = np.empty(weight.size, dtype=np.int8)
    plot = np.empty(weight.size, dtype=bool)
    second = np.empty(weight.size, dtype=bool)
    access = np.empty(weight.size, dtype=np.float64)
    western = np.empty(weight.size, dtype=np.float64)

    if spec.stochastic:
        draws = np.asarray(rng.uniform(ATTRIBUTE_MODULE, weight.size * _ATTR_DRAWS)).reshape(
            weight.size, _ATTR_DRAWS
        )
    else:
        draws = None

    edu_cdf: list[np.ndarray] = []
    tenure_cdf: list[np.ndarray] = []
    for county in recipe.counties:
        edu_cdf.append(np.cumsum(np.asarray(county.education_shares, dtype=np.float64)))
        tenure_cdf.append(np.cumsum(np.asarray(county.tenure_shares, dtype=np.float64)))

    for cell_index, (region_ordinal, size_value, _urban, _occ) in enumerate(cell_keys):
        county = recipe.counties[region_ordinal]
        mask = cell_ordinal == cell_index
        n_cell = int(mask.sum())
        if n_cell == 0:
            continue
        children[mask] = min(
            int(size_value) - 1, int(np.floor(size_value * county.child_share + 0.5))
        )
        elderly[mask] = min(
            int(size_value) - 1 - int(children[mask][0]),
            int(np.floor(size_value * county.elderly_share + 0.5)),
        )
        adults[mask] = int(size_value) - int(children[mask][0]) - int(elderly[mask][0])
        if draws is None:
            u = (within[mask] + 0.5) / n_cell
            u0 = u1 = u2 = u3 = u4 = u
        else:
            u0 = draws[mask, 0]
            u1 = draws[mask, 1]
            u2 = draws[mask, 2]
            u3 = draws[mask, 3]
            u4 = draws[mask, 4]
        education[mask] = np.searchsorted(edu_cdf[region_ordinal], u0, side="right").astype(np.int8)
        tenure[mask] = np.searchsorted(tenure_cdf[region_ordinal], u1, side="right").astype(np.int8)
        plot[mask] = u2 < county.plot_share
        second[mask] = u3 < county.second_share
        access[mask] = np.clip(county.informal_access + 0.2 * (u4 - 0.5), 0.0, 1.0)
        western[mask] = county.western_exposure

    education = np.minimum(education, len(HOUSEHOLD_EDUCATION_IDS) - 1)
    tenure = np.minimum(tenure, len(HOUSEHOLD_TENURE_IDS) - 1)
    working_adults = adults.astype(np.float64)
    pay_weight = working_adults * np.asarray(EDUCATION_PAY_MULTIPLIER, dtype=np.float64)[education]
    sector = np.asarray(OCCUPATION_SECTOR, dtype=np.int16)[occupation]

    durable_owned = np.zeros((weight.size, 4), dtype=np.float64)
    for ordinal, county in enumerate(recipe.counties):
        row = region == ordinal
        durable_owned[row] = np.asarray(county.durable_ownership, dtype=np.float64)

    county_household_total = sum(c.household_total for c in recipe.counties)
    county_persons_total = sum(c.persons_total for c in recipe.counties)
    achieved = {
        "household_total": float(weight.sum()),
        "persons_total": float((weight * size).sum()),
        "urban_share": float((weight * urban).sum() / weight.sum()),
    }
    digest = hashlib.sha256(
        b"".join(
            [
                np.ascontiguousarray(region).tobytes(),
                np.ascontiguousarray(size).tobytes(),
                np.ascontiguousarray(urban).tobytes(),
                np.ascontiguousarray(occupation).tobytes(),
                np.ascontiguousarray(weight).tobytes(),
            ]
        )
    ).hexdigest()

    return HouseholdInitial(
        household_id=household_id,
        region=region,
        weight=weight,
        size=size,
        plot_participating=plot,
        urban=urban,
        occupation=occupation,
        sector=sector,
        education=education,
        children=children,
        adults=adults,
        elderly=elderly,
        working_adults=working_adults,
        pay_weight=pay_weight,
        second_participating=second,
        western_exposure=western,
        informal_access=access,
        tenure=tenure,
        durable_owned=durable_owned,
        people_total=county_persons_total,
        household_total=county_household_total,
        achieved_margins=achieved,
        static_hash=digest,
    )


def household_equivalence(state: MaterialState) -> np.ndarray:
    """Household equivalent-adult scale ``e = adults + .7 children + .9 elderly``."""
    return (
        np.asarray(state.household_adults, dtype=np.float64)
        + 0.7 * np.asarray(state.household_children, dtype=np.float64)
        + 0.9 * np.asarray(state.household_elderly, dtype=np.float64)
    )


def form_household_demand(
    state: MaterialState,
    parameters: HouseholdParameters,
    catalog: HouseholdCatalog,
) -> np.ndarray:
    """Quarterly desired consumption per household and sub-channel (C1/C3).

    Pure array kernel over frozen opening state.  Returns ``(N, H)`` desired
    quantities in household-channel units.  Durable ``H`` channels carry zero
    here: durable aspirations live in the stock module (E).
    """
    demand = parameters.demand
    equivalent = household_equivalence(state)
    last_income = np.asarray(state.household_last_income, dtype=np.float64)
    reference = np.asarray(state.household_reference_income, dtype=np.float64)
    eps = parameters.eps
    z = np.maximum(np.log(np.maximum(last_income, eps) / np.maximum(reference, eps)), 0.0)

    region = np.asarray(state.household_region, dtype=np.int64)
    weight = np.asarray(state.household_weight, dtype=np.float64)
    urban = np.asarray(state.household_urban, dtype=bool)
    occupation = np.asarray(state.household_occupation, dtype=np.int64)
    education = np.asarray(state.household_education, dtype=np.int64)
    western = np.asarray(state.household_western_exposure, dtype=np.float64)

    occ_mult = np.asarray(demand.occupation_multipliers, dtype=np.float64)[occupation]
    edu_mult = np.asarray(demand.education_multipliers, dtype=np.float64)[education]
    lux_mult = occ_mult * edu_mult

    expectation_real = np.asarray(state.household_expectation, dtype=np.float64)[
        :, catalog.entitlement_ids.index("real_consumption")
    ]

    # Peer light-goods uplift from the previous quarter's realised basket.
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    light_channels = catalog.channels("light")
    last_light = np.asarray(state.household_last_consumption, dtype=np.float64)[
        :, list(light_channels)
    ].sum(axis=1)
    peer_num = np.bincount(region, weights=weight * last_light, minlength=region_count)
    peer_den = np.bincount(region, weights=weight * equivalent, minlength=region_count)
    peer_uplift = np.zeros(weight.size, dtype=np.float64)
    national_peer = float(peer_num.sum() / max(peer_den.sum(), eps))
    if national_peer > eps:
        peer_uplift = np.maximum(
            peer_num[region] / np.maximum(peer_den[region], eps) / national_peer - 1.0, 0.0
        )

    base = np.asarray(demand.base_per_equivalent_person, dtype=np.float64)
    energy_multiplier = np.where(
        urban, demand.urban_energy_multiplier, demand.rural_energy_multiplier
    )
    desired = np.zeros((weight.size, len(catalog.household_good_ids)), dtype=np.float64)
    for channel in catalog.channels("energy"):
        desired[:, channel] = base[channel] * equivalent * energy_multiplier
    for channel in catalog.channels("basic_food"):
        desired[:, channel] = base[channel] * equivalent
    higher_factor = (
        1.0
        + demand.higher_income_elasticity * z
        + demand.higher_expectation_weight * expectation_real
    )
    for channel in catalog.channels("higher_food"):
        desired[:, channel] = base[channel] * equivalent * higher_factor * lux_mult
    light_factor = (
        1.0
        + demand.light_income_elasticity * z
        + demand.light_peer_weight * peer_uplift
        + demand.light_western_weight * western
    )
    for channel in light_channels:
        desired[:, channel] = base[channel] * equivalent * light_factor * lux_mult
    personal_factor = 1.0 + demand.personal_income_elasticity * z
    for channel in catalog.channels("personal"):
        desired[:, channel] = base[channel] * equivalent * personal_factor
    # Public services get the declared flat per-equivalent-person base, like
    # basic food: they are an entitlement rather than a luxury channel.  Without
    # this branch the channel carried zero demand for every household, so the
    # whole g16 pipeline (desired -> ordered -> allocated -> delivered) stayed at
    # zero while producers still produced against capacity.
    if "public" in catalog.role_channels:
        for channel in catalog.channels("public"):
            desired[:, channel] = base[channel] * equivalent * lux_mult
    # durable channels carry a flat declared base (aspiration demand is added by
    # the stock module); protected minima never multiply the luxury channels.
    for durable_channel in catalog.durable_h_index:
        if durable_channel >= 0:
            desired[:, int(durable_channel)] = base[int(durable_channel)] * equivalent
    if not np.all(np.isfinite(desired)):
        raise ValueError("household demand carries non-finite values")
    return np.maximum(desired, 0.0)


__all__ = [
    "ATTRIBUTE_MODULE",
    "build_synthetic_households",
    "form_household_demand",
    "household_equivalence",
]
