"""H5B M4 second-economy F2 adapter (named commodity recipe, structural assumption).

This module owns the *only* hook that runs F2 second-economy execution outside
the pinned 8-commodity ``SecondEconomyRecipe``.  It exposes a frozen recipe, a
frozen derived ``F2SecondEconomyNetwork`` view, and the four tick functions
planner/settle/expiry/invariant-check that swap in when the F2 recipe is
attached via ``attach_f2_second_economy``.  The recipe and its execution
constants are explicitly *not* calibrated; meta fields declare
``role="latent_parameter"`` / ``evidence_status="structural_assumption"`` /
``calibration_status="not_calibrated"``.

Design boundary:
    * The legacy ``engine.second_economy.settle_second_economy`` P03 path
      keeps running unchanged when no F2 recipe is attached.  Only the F2
      adapter handles named F2 commodity axes.
    * All stock sources are organisation-owned selling cells (output/wholesale/
      retail).  Plot ready-market, Treasury import pool, regular input/WIP and
      plot self-use are never second-economy source cells.
    * Household funding equals represented-cash share: no double-weighting.
    * Inputs and outputs are bounded by real available stock; per-region
      funding is computed before any state mutation, then atomic.
    * F2 expiry uses the declared ``stockable`` attribute on commodity specs,
      not legacy string heuristics.
    * Trace is sidecar-only: ``tick_material`` passes a fresh dict per tick
      when opt-in; ``None`` (default) keeps the kernel allocation-free.

Mutability is locked: every dataclass is frozen; arrays are copies; no global
state is touched.  Pre-mutation precomputation guards cash debit, stock draw,
output write, payer/receiver settlement and bank reserve balance.  Accounting
errors are surfaced as ``AccountingError``; configuration and validation
issues as ``ConfigError``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import Any

import numpy as np

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.households import HouseholdParameters
from hsm_lab.contract.material import CommoditySpec
from hsm_lab.engine.accounting import AccountingError, tolerance_for
from hsm_lab.engine.network import MaterialNetwork
from hsm_lab.engine.state import POOL_CODES, MaterialState, MaterialStockSnapshot, MaterialTickFlows
from hsm_lab.provenance.manifest import canonical_digest

# F2-specific marker constants — declared once, never inferred.
SCHEMA_VERSION = "hist_vnext_second_economy_f2_v1"
SPEC_SCHEMA_VERSION = "hist_vnext_h5b_m04_v1"
_RECIPE_ID_DEFAULT = "hist-vnext-m04-nonplot-v1"
_F2_NETWORK_MARKER = "hist_vnext_f2_second_economy_v1"
_F2_DOMAIN_PREFIX = "f2_second_economy"

# Selling pool codes used by the F2 input draw (organisational output/wholesale/
# retail).  Plot ready-market (retail owned by a plot cell with owner_kind==1
# is filtered later via the cell_owner_kind check) is also excluded.
_SELLING_POOLS = frozenset(
    {POOL_CODES["output"], POOL_CODES["wholesale"], POOL_CODES["retail"]}
)

# Owner-kind codes that pass the source filter.  0 = organization; 1 = plot,
# 2 = project, 3 = treasury_import, 4 = second_economy pool.  Only 0 sells.
_ORG_OWNER_KIND = 0


# ---------------------------------------------------------------------------
# Recipe
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class F2SecondEconomyRecipe:
    """Frozen F2 second-economy recipe: named commodity axes, hours, capacity.

    The metadata role/evidence/calibration are required to declare this as a
    structural assumption, never a calibrated historical estimate.  Inputs and
    outputs are stored as ``(commodity_id, coefficient)`` pairs in declared
    order — duplicates and unknown commodity ids are rejected.  Zero
    coefficients are not stored.
    """

    recipe_id: str
    input_coefficients: tuple[tuple[str, float], ...]
    output_coefficients: tuple[tuple[str, float], ...]
    hours_per_activity: float
    capacity_per_participating_worker: float
    role: str = "latent_parameter"
    evidence_status: str = "structural_assumption"
    calibration_status: str = "not_calibrated"
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def default_nonplot_v1(
        cls, *,
        recipe_id: str = _RECIPE_ID_DEFAULT,
    ) -> F2SecondEconomyRecipe:
        """The pre-registered H5B non-plot F2 recipe (synthetic struct.)."""
        return cls(
            recipe_id=recipe_id,
            input_coefficients=(
                ("g02_oil_gas_fuels", 0.02),
                ("g04_basic_metals_materials", 0.03),
            ),
            output_coefficients=(
                ("g11_textiles_footwear", 0.10),
                ("g15_market_services", 0.25),
            ),
            hours_per_activity=4.0,
            capacity_per_participating_worker=10.0,
        )

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> F2SecondEconomyRecipe:
        """Build from a JSON-friendly mapping; raises ``ConfigError`` on shape."""
        if not isinstance(payload, dict):
            raise ConfigError("F2 recipe payload must be a mapping")
        try:
            inputs = [
                (str(name), float(coefficient))
                for name, coefficient in payload.get("input_coefficients", ())
            ]
            outputs = [
                (str(name), float(coefficient))
                for name, coefficient in payload.get("output_coefficients", ())
            ]
            return cls(
                recipe_id=str(payload.get("recipe_id", _RECIPE_ID_DEFAULT)),
                input_coefficients=tuple(inputs),
                output_coefficients=tuple(outputs),
                hours_per_activity=float(payload.get("hours_per_activity", 4.0)),
                capacity_per_participating_worker=float(
                    payload.get("capacity_per_participating_worker", 10.0)
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"invalid F2 recipe payload: {exc}") from exc

    def to_mapping(self) -> dict[str, Any]:
        """Return the canonical mapping used for hashing."""
        return {
            "schema_version": self.schema_version,
            "recipe_id": self.recipe_id,
            "input_coefficients": [list(pair) for pair in self.input_coefficients],
            "output_coefficients": [list(pair) for pair in self.output_coefficients],
            "hours_per_activity": float(self.hours_per_activity),
            "capacity_per_participating_worker": float(
                self.capacity_per_participating_worker
            ),
            "role": self.role,
            "evidence_status": self.evidence_status,
            "calibration_status": self.calibration_status,
        }

    @property
    def recipe_hash(self) -> str:
        """Stable SHA-256 derived from the canonical payload (never trust input)."""
        return canonical_digest(self.to_mapping())


def _validate_recipe(
    recipe: F2SecondEconomyRecipe,
    *,
    commodity_ids: tuple[str, ...],
    allowed_outputs: set[str] | None = None,
) -> None:
    """Run all declared checks against an attached commodity axis."""
    seen_inputs: set[str] = set()
    for name, coefficient in recipe.input_coefficients:
        if name in seen_inputs:
            raise ConfigError(
                f"F2 recipe {recipe.recipe_id!r} repeats input commodity {name!r}"
            )
        seen_inputs.add(name)
        if name not in commodity_ids:
            raise ConfigError(
                f"F2 recipe input {name!r} is not on the network commodity axis"
            )
        if not math.isfinite(coefficient) or coefficient <= 0.0:
            raise ConfigError(
                f"F2 recipe input coefficient for {name!r} must be finite and > 0"
            )
    seen_outputs: set[str] = set()
    for name, coefficient in recipe.output_coefficients:
        if name in seen_outputs:
            raise ConfigError(
                f"F2 recipe {recipe.recipe_id!r} repeats output commodity {name!r}"
            )
        seen_outputs.add(name)
        if name not in commodity_ids:
            raise ConfigError(
                f"F2 recipe output {name!r} is not on the network commodity axis"
            )
        if allowed_outputs is not None and name not in allowed_outputs:
            raise ConfigError(
                f"F2 recipe output {name!r} is not a declared household channel parent"
            )
        if not math.isfinite(coefficient) or coefficient <= 0.0:
            raise ConfigError(
                f"F2 recipe output coefficient for {name!r} must be finite and > 0"
            )
    if not math.isfinite(recipe.hours_per_activity) or recipe.hours_per_activity <= 0.0:
        raise ConfigError("F2 hours_per_activity must be finite and > 0")
    if not math.isfinite(recipe.capacity_per_participating_worker) or not (
        0.0 <= recipe.capacity_per_participating_worker <= 20.0
    ):
        raise ConfigError(
            "F2 capacity_per_participating_worker must be finite and lie in [0, 20]"
        )
    if not recipe.input_coefficients or not recipe.output_coefficients:
        raise ConfigError("F2 recipe must declare at least one input and one output")


# ---------------------------------------------------------------------------
# F2 network view
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class F2SecondEconomyNetwork(MaterialNetwork):
    """Derived ``MaterialNetwork`` view carrying one F2 recipe.

    All other fields are copied from the underlying ``MaterialNetwork``; the
    arrays are shared, not copied, and the original dataclass field table is
    never modified.  The marker attribute lets callers detect opt-in without
    holding a reference to the recipe.
    """

    second_economy_f2_recipe: F2SecondEconomyRecipe
    f2_marker: str = _F2_NETWORK_MARKER


def _as_f2_view(network: Any) -> F2SecondEconomyNetwork | None:
    """Return the F2 view if ``network`` carries the marker, else ``None``."""
    if getattr(network, "f2_marker", None) == _F2_NETWORK_MARKER:
        return network  # type: ignore[return-value]
    return None


def _f2_recipe(network: Any) -> F2SecondEconomyRecipe | None:
    view = _as_f2_view(network)
    return None if view is None else view.second_economy_f2_recipe


def attach_f2_second_economy(
    network: Any, recipe: F2SecondEconomyRecipe
) -> F2SecondEconomyNetwork:
    """Return a frozen F2 view of ``network`` carrying ``recipe``.

    The function never mutates ``network`` and never modifies
    ``MaterialNetwork``'s declared field table (a frozen dataclass).  It
    re-emits the original ``second_input_commodities`` /
    ``second_output_commodities`` tuples ordered by the recipe's commodity
    names as they appear on the network commodity axis.
    """
    if not isinstance(network, MaterialNetwork):
        raise ConfigError(
            f"attach_f2_second_economy requires MaterialNetwork, got {type(network).__name__}"
        )
    if getattr(network, "f2_marker", None) == _F2_NETWORK_MARKER:
        raise ConfigError("network already carries an F2 recipe; refusing duplicate attach")
    commodity_ids = tuple(network.commodity_ids)
    parent_index = np.asarray(
        network.household_catalog.parent_material_index, dtype=np.int64
    )
    allowed_outputs = {
        commodity_ids[int(index)] for index in parent_index if int(index) >= 0
    }
    _validate_recipe(
        recipe,
        commodity_ids=commodity_ids,
        allowed_outputs=allowed_outputs,
    )
    commodity_index = {cid: index for index, cid in enumerate(commodity_ids)}
    inputs_sorted = tuple(
        sorted(recipe.input_coefficients, key=lambda pair: commodity_index[pair[0]])
    )
    outputs_sorted = tuple(
        sorted(recipe.output_coefficients, key=lambda pair: commodity_index[pair[0]])
    )
    payload = {field.name: getattr(network, field.name) for field in fields(network)}
    payload["second_input_commodities"] = tuple(
        commodity_index[name] for name, _ in inputs_sorted
    )
    payload["second_output_commodities"] = tuple(
        commodity_index[name] for name, _ in outputs_sorted
    )
    payload["second_economy_f2_recipe"] = recipe
    payload["f2_marker"] = _F2_NETWORK_MARKER
    return F2SecondEconomyNetwork(**payload)


# ---------------------------------------------------------------------------
# Planning: F2 household-time reservation
# ---------------------------------------------------------------------------


def plan_f2_household_time(
    state: MaterialState,
    parameters: HouseholdParameters,
    *,
    tolerance: float,
) -> None:
    """Reserve plot/second hours with F2-named tolerance and cohort rule.

    ``tolerance`` is the raw ``second_economy_tolerance`` (may be 0).  The
    planner:
        * Reads working_adults and ``household_second_participating`` only;
          no other cohort is treated as a participant.
        * Reduces requested second hours by ``tolerance`` (clamped to >= 0).
        * Preserves the formal hours baseline (no formal feedback).
        * Compresses plot+second joint requests against remaining time; the
          shortage and grievance intensity formulae stay unchanged.
        * Rejects ``formal > endowment`` before mutating any array.
        * Leaves queue/search/leisure intake untouched (the allocator computes
          those downstream, bounded to the remaining time).
    """
    raw_tolerance = float(tolerance)
    if not math.isfinite(raw_tolerance) or raw_tolerance < 0.0:
        raise ConfigError(
            f"F2 tolerance must be finite and non-negative, got {raw_tolerance!r}"
        )
    time = parameters.time
    working = np.asarray(state.household_working_adults, dtype=np.float64)
    second = np.asarray(state.household_second_participating, dtype=bool)
    grievance = np.asarray(state.household_grievance, dtype=np.float64)
    last_unmet = np.asarray(state.household_last_availability_unmet, dtype=np.float64)
    desired_ref = np.asarray(state.household_consumption_reference, dtype=np.float64)
    eps = float(parameters.eps)
    shortage = np.where(
        desired_ref.sum(axis=1) > 0.0,
        last_unmet.sum(axis=1) / np.maximum(desired_ref.sum(axis=1), eps),
        0.0,
    )
    shortage = np.clip(shortage, 0.0, 1.0)

    # Plot hours are computed from scratch each tick (mirrors legacy F1):
    # ``participating & working > 0`` is the cohort.  Treat the F2 view as
    # ``hours_cap_per_worker * working`` for every participating household;
    # the joint compression below scales these against remaining time.
    plot_participating = np.asarray(
        state.household_plot_participating, dtype=bool
    ) & (working > 0.0)
    plot_hours = np.where(
        plot_participating, time.plot_hours_cap_per_worker * working, 0.0
    )
    # Cohort rule: zero working adults yields zero second hours; raw tolerance
    # multiplies the requested second hours directly (no clamp on hours/intensity).
    intensity = np.clip(
        time.second_hours_base
        + time.second_shortage_weight * shortage
        + time.second_grievance_weight * grievance,
        0.0,
        1.0,
    )
    requested_second = np.where(
        second, time.second_hours_cap_per_worker * working * intensity, 0.0
    )
    second_hours = requested_second * max(raw_tolerance, 0.0)
    # Plot request is supplied by the caller-allocated hours; F2 only enforces
    # that the joint requests compress against remaining time together with second.
    formal_hours = time.formal_hours_per_worker * working
    endowment = time.time_endowment_hours * working
    # Endow < formal => refuse before mutation.  Endow == formal leaves zero
    # remaining time, so the joint compression scales plot and second hours to
    # zero; that is the PLAN's tight-time counterexample.
    if np.any(formal_hours > endowment + eps):
        bad = int(np.flatnonzero(formal_hours > endowment + eps)[0])
        raise ConfigError(
            f"F2 time planner: household {bad} has formal hours {float(formal_hours[bad])} "
            f"exceeding endowment {float(endowment[bad])} (mutation rejected)"
        )
    plot_requested = plot_hours
    second_requested = second_hours
    joint_request = plot_requested + second_requested
    remaining = np.maximum(endowment - formal_hours, 0.0)
    scale = np.where(
        joint_request > 0.0,
        np.minimum(1.0, remaining / np.maximum(joint_request, eps)),
        1.0,
    )
    plot_hours = plot_requested * scale
    second_hours = second_requested * scale

    state.household_reserved_plot_hours = plot_hours
    state.household_reserved_second_hours = second_hours


# ---------------------------------------------------------------------------
# Settle: F2 production, funding, journal and bank-reserve migration
# ---------------------------------------------------------------------------


def settle_f2_second_economy(
    state: MaterialState,
    flows: MaterialTickFlows,
    network: Any,
    parameters: HouseholdParameters,
    price_net: np.ndarray,
    *,
    trace: dict[str, Any] | None = None,
) -> None:
    """Inputs, outputs, payments and journal legs for F2 second economy.

    Per region, activity is the minimum of:
        1. capacity = cohort_weighted_workers * recipe.capacity_per_worker;
        2. reserved labor = sum(weight * reserved_hours) / hours_per_activity;
        3. per-input physical stock (real seller cells, organisation output /
           wholesale / retail only) divided by the input coefficient;
        4. cohort cash / ``sum(coefficient * price_net)`` (cash before stock).

    No retail cell is the source of two competing withdrawals in one tick; the
    F2 draw runs after the formal production step so it inherits residual
    stock.  Funding is computed regionally, debited per-household against
    opening cash, and credited to the source cell's organisation (organisa-
    tions only); plot ready-market and Treasury import cells are *never*
    credited here.
    """
    recipe = _f2_recipe(network)
    if recipe is None:
        # Defensive: the dispatcher should never call us without opt-in.
        return

    region = np.asarray(state.household_region, dtype=np.int64)
    weight = np.asarray(state.household_weight, dtype=np.float64)
    working = np.asarray(state.household_working_adults, dtype=np.float64)
    hours = np.asarray(state.household_reserved_second_hours, dtype=np.float64)
    participant = np.asarray(state.household_second_participating, dtype=bool)
    household_cash = np.asarray(state.household_cash, dtype=np.float64)
    if household_cash.size == 0:
        return
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    commodity_ids = tuple(network.commodity_ids)
    commodity_index = {cid: index for index, cid in enumerate(commodity_ids)}
    g_count = len(commodity_ids)

    # Mirror the legacy flows.household_second_hours write.
    flows.household_second_hours = np.asarray(
        state.household_reserved_second_hours, dtype=np.float64
    ).copy()

    # Cohort mask: participants with positive working adults.
    cohort_mask = participant & (working > 0.0)
    if not bool(np.any(cohort_mask)):
        _record_zero_trace(trace, network, state, tick=int(flows.tick))
        return

    weighted_workers_per_region = np.zeros(region_count, dtype=np.float64)
    weighted_hours_per_region = np.zeros(region_count, dtype=np.float64)
    weighted_cash_per_region = np.zeros(region_count, dtype=np.float64)
    np.add.at(
        weighted_workers_per_region,
        region[cohort_mask],
        (weight * working)[cohort_mask],
    )
    np.add.at(
        weighted_hours_per_region,
        region[cohort_mask],
        (weight * hours)[cohort_mask],
    )
    np.add.at(
        weighted_cash_per_region,
        region[cohort_mask],
        (weight * np.maximum(household_cash, 0.0))[cohort_mask],
    )
    hours_per_activity = max(float(recipe.hours_per_activity), 1e-12)

    activity_capacity = weighted_workers_per_region * float(
        recipe.capacity_per_participating_worker
    )
    activity_labor = weighted_hours_per_region / hours_per_activity
    target = np.maximum(np.minimum(activity_capacity, activity_labor), 0.0)

    if not np.any(target > 0.0):
        _record_zero_trace(trace, network, state, tick=int(flows.tick))
        return

    cell_region = np.asarray(network.cell_region, dtype=np.int64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_pool = np.asarray(network.cell_pool, dtype=np.int64)
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    stock = np.asarray(state.stock_value, dtype=np.float64).copy()

    selling = (
        np.isin(cell_pool, list(_SELLING_POOLS))
        & (cell_owner_kind == _ORG_OWNER_KIND)
    )
    availability = np.zeros((region_count, g_count), dtype=np.float64)
    for r in range(region_count):
        mask = selling & (cell_region == r)
        if not mask.any():
            continue
        availability[r] = np.bincount(
            cell_commodity[mask], weights=stock[mask], minlength=g_count
        )

    # Cash-side activity cap from input costs at the live admin price.
    inputs_sorted = sorted(
        recipe.input_coefficients, key=lambda pair: commodity_index[pair[0]]
    )
    if not inputs_sorted:
        _record_zero_trace(trace, network, state, tick=int(flows.tick))
        return
    input_coefficient_array = np.array(
        [coefficient for _, coefficient in inputs_sorted], dtype=np.float64
    )
    input_price_array = np.array(
        [float(price_net[commodity_index[name]]) for name, _ in inputs_sorted],
        dtype=np.float64,
    )
    cost_per_activity = float(np.sum(input_coefficient_array * input_price_array))
    if cost_per_activity <= 0.0 or not np.isfinite(cost_per_activity):
        _record_zero_trace(trace, network, state, tick=int(flows.tick))
        return

    cash_capped = np.divide(
        weighted_cash_per_region,
        cost_per_activity,
        out=np.zeros(region_count, dtype=np.float64),
        where=(target > 0.0),
    )
    target = np.minimum(target, np.maximum(cash_capped, 0.0))

    # Per-input stock caps.
    realized = target.copy()
    for name, coefficient in inputs_sorted:
        g = commodity_index[name]
        if coefficient <= 0.0:
            continue
        limit = availability[:, g] / coefficient
        realized = np.minimum(realized, limit)
    realized = np.maximum(realized, 0.0)
    if not np.any(realized > 0.0):
        _record_zero_trace(trace, network, state, tick=int(flows.tick))
        return

    # Funding: cohort cash, distributed per represented cash share.
    funded_region = np.zeros(region_count, dtype=np.float64)
    payment_region = realized * cost_per_activity
    region_cash = np.bincount(
        region[cohort_mask],
        weights=(weight * np.maximum(household_cash, 0.0))[cohort_mask],
        minlength=region_count,
    )
    allowed_share = np.divide(
        np.maximum(region_cash, 0.0),
        payment_region,
        out=np.zeros(region_count, dtype=np.float64),
        where=payment_region > 0.0,
    )
    allowed_share = np.minimum(allowed_share, 1.0)
    funded_region = payment_region * allowed_share
    realized = realized * allowed_share

    # Aggregate per-household funding (no double weight): per PLAN §A.6,
    # ``fund_i = funded_region * cash_i / sum_cohort(weight*cash)`` so the
    # weighted cohort sum equals ``funded_region`` exactly, irrespective of
    # household weights.  ``cohort_cash_total`` is the *weighted* cohort cash.
    input_funding = np.zeros(weight.size, dtype=np.float64)
    cohort_cash_total = np.zeros(region_count, dtype=np.float64)
    cash_pos = np.maximum(household_cash, 0.0)
    np.add.at(cohort_cash_total, region[cohort_mask], (weight * cash_pos)[cohort_mask])
    for r in range(region_count):
        if funded_region[r] <= 0.0 or cohort_cash_total[r] <= 0.0:
            continue
        region_mask = region == r
        in_cohort = region_mask & cohort_mask
        if not in_cohort.any():
            continue
        shares = cash_pos[in_cohort] / max(cohort_cash_total[r], 1e-12)
        shares = np.clip(shares, 0.0, 1.0)
        input_funding[in_cohort] = funded_region[r] * shares
    # Cap per-household debit to their own cash.  If anyone under-budgets,
    # rescale ``realized`` so ``sum(weight*input_funding) == sum(input_funding)``
    # is preserved at the cohort level (the bank delta stays closed).
    input_funding = np.minimum(input_funding, np.maximum(household_cash, 0.0))
    region_paid = np.zeros(region_count, dtype=np.float64)
    np.add.at(
        region_paid,
        region[cohort_mask],
        (weight * input_funding)[cohort_mask],
    )
    target_paid = np.minimum(funded_region, region_cash)
    cap = np.divide(
        target_paid,
        region_paid,
        out=np.ones(region_count, dtype=np.float64),
        where=region_paid > 0.0,
    )
    realized = realized * np.minimum(cap, 1.0)
    realized = np.maximum(realized, 0.0)
    if not np.any(realized > 0.0):
        _record_zero_trace(trace, network, state, tick=int(flows.tick))
        return
    funded_region = realized * cost_per_activity
    # Recompute per-household funding on the reconciled slice.
    input_funding = np.zeros(weight.size, dtype=np.float64)
    for r in range(region_count):
        if funded_region[r] <= 0.0 or cohort_cash_total[r] <= 0.0:
            continue
        region_mask = region == r
        in_cohort = region_mask & cohort_mask
        if not in_cohort.any():
            continue
        shares = cash_pos[in_cohort] / max(cohort_cash_total[r], 1e-12)
        shares = np.clip(shares, 0.0, 1.0)
        input_funding[in_cohort] = funded_region[r] * shares
    input_funding = np.minimum(input_funding, np.maximum(household_cash, 0.0))

    # Pre-mutation prechecks.
    if float(np.any(np.asarray(state.bank_reserves, dtype=np.float64) < -1e-9)):
        raise AccountingError("F2 settle: bank reserves negative before mutation")
    if not bool(np.all(np.isfinite(input_funding))):
        raise AccountingError("F2 settle: input funding contains non-finite entries")

    org_count = int(state.organization_id.shape[0])
    bank_count = int(np.asarray(state.bank_reserves).shape[0])
    seller_credit = np.zeros(org_count, dtype=np.float64)
    # Region -> per-commodity -> cell index, in deterministic (ascending) order.
    new_input_used = np.zeros_like(stock)

    for name, coefficient in inputs_sorted:
        g = commodity_index[name]
        price = float(input_price_array[list(inputs_sorted).index((name, coefficient))])
        take_per_region = realized * coefficient
        for r in range(region_count):
            quantity_r = float(take_per_region[r])
            if quantity_r <= 1e-12:
                continue
            mask = selling & (cell_region == r) & (cell_commodity == g)
            if not mask.any():
                continue
            cells = np.flatnonzero(mask)
            cell_stock = stock[cells]
            total = float(cell_stock.sum())
            if total <= 0.0:
                continue
            take = min(quantity_r, total)
            share = cell_stock / total
            amount_per_cell = take * share
            stock[cells] -= amount_per_cell
            new_input_used[cells] += amount_per_cell
            value = amount_per_cell * price
            owners = cell_owner_id[cells]
            np.add.at(seller_credit, owners, value)
    total_input_paid = float(seller_credit.sum())
    total_input_funded = float((weight * input_funding).sum())
    if total_input_paid + 1e-6 < total_input_funded:
        raise AccountingError(
            f"F2 settle: cell credits {total_input_paid:.9f} fall short of cohort "
            f"funding {total_input_funded:.9f} (mutation rejected)"
        )

    # Mutate state atomically from this point.
    state.stock_value = stock
    state.household_cash = household_cash - input_funding
    flows.second_input_used = np.asarray(flows.second_input_used, dtype=np.float64) + new_input_used
    flows.household_second_input_funding = (
        np.asarray(flows.household_second_input_funding, dtype=np.float64) + input_funding
    )
    if np.any(seller_credit > 0.0):
        state.organization_cash = (
            np.asarray(state.organization_cash, dtype=np.float64) + seller_credit
        )
        flows.organization_sales_receipts = (
            np.asarray(flows.organization_sales_receipts, dtype=np.float64)
            + seller_credit
        )

    # Output writes — second-output pool is the only F2 destination.
    pool = np.asarray(state.second_output_stock, dtype=np.float64).copy()
    for name, coefficient in recipe.output_coefficients:
        g = commodity_index[name]
        pool[:, g] = pool[:, g] + realized * float(coefficient)
    state.second_output_stock = pool

    # Bank-sheet migration: household cash debit per bank, organisation credit per bank.
    org_bank = np.asarray(state.organization_bank, dtype=np.int64)
    bank_delta = np.zeros(bank_count, dtype=np.float64)
    safe_bank = np.where(org_bank >= 0, org_bank, 0)
    paying_org = seller_credit > 0.0
    bank_delta += np.bincount(
        safe_bank[paying_org], weights=seller_credit[paying_org], minlength=bank_count
    )
    paying_hh = input_funding > 0.0
    hh_bank = region % max(bank_count, 1)
    bank_delta -= np.bincount(
        hh_bank[paying_hh],
        weights=(weight * input_funding)[paying_hh],
        minlength=bank_count,
    )
    if bool(np.any(bank_delta != 0.0)):
        state.bank_deposit_liability = (
            np.asarray(state.bank_deposit_liability, dtype=np.float64) + bank_delta
        )
        state.bank_reserves = np.asarray(state.bank_reserves, dtype=np.float64) + bank_delta
        from hsm_lab.engine import finance

        finance._append_interbank_legs(
            state, flows, kind="hist_second_input_payment", delta=bank_delta, leg_offset=0
        )

    # Post-mutation gates (defensive).
    if bool(np.any(np.asarray(state.bank_reserves, dtype=np.float64) < -1e-6)):
        raise AccountingError("F2 settle: bank reserves went negative")
    if bool(np.any(np.asarray(state.organization_cash, dtype=np.float64) < -1e-6)):
        raise AccountingError("F2 settle: organisation cash went negative")
    if bool(np.any(np.asarray(state.household_cash, dtype=np.float64) < -1e-6)):
        raise AccountingError("F2 settle: household cash went negative")
    if bool(np.any(np.asarray(state.stock_value, dtype=np.float64) < -1e-6)):
        raise AccountingError("F2 settle: stock value went negative")

    # Record trace if requested.
    if trace is not None:
        _record_settle_trace(
            trace,
            state=state,
            network=network,
            tick=int(flows.tick),
            realized=realized,
            new_input_used=new_input_used,
            funding=input_funding,
            seller_credit=seller_credit,
            weighted_workers=weighted_workers_per_region,
            weighted_hours=weighted_hours_per_region,
            weighted_cash=weighted_cash_per_region,
            capacity=activity_capacity,
            labor=activity_labor,
            cash_cap=cash_capped,
            availability=availability,
            commodity_index=commodity_index,
        )


# ---------------------------------------------------------------------------
# Expire: F2 stockable-aware expiry
# ---------------------------------------------------------------------------


def expire_f2_second_economy(
    state: MaterialState,
    network: Any,
    *,
    trace: dict[str, Any] | None = None,
) -> None:
    """Drop non-stockable F2 services from the second-output pool.

    Stockability comes from the declared commodity spec, not from
    legacy string heuristics.  We persist the trait on a per-commodity basis
    so this remains deterministic.
    """
    recipe = _f2_recipe(network)
    if recipe is None:
        return
    commodity_ids = list(network.commodity_ids)
    pool = np.asarray(state.second_output_stock, dtype=np.float64).copy()
    # Stockability by commodity spec: services_transport-like declared
    # ``stockable=False`` outputs zero; everything else stays.
    specs: list[CommoditySpec | None] = [
        _try_commodity_spec(name) for name in commodity_ids
    ]
    for g, name in enumerate(commodity_ids):
        spec = specs[g]
        stockable = bool(getattr(spec, "stockable", True)) if spec is not None else True
        if stockable:
            continue
        expired_quantity = pool[:, g].copy()
        pool[:, g] = 0.0
        if trace is not None:
            expired = np.asarray(
                trace.get(
                    "expired",
                    np.zeros(
                        (int(np.asarray(state.dwelling_stock).shape[0]), len(commodity_ids)),
                        dtype=np.float64,
                    ),
                ),
                dtype=np.float64,
            ).copy()
            if expired.shape[0] != expired_quantity.shape[0]:
                expired = np.zeros(
                    (expired_quantity.shape[0], len(commodity_ids)), dtype=np.float64
                )
            expired[:, g] = expired[:, g] + expired_quantity
            trace["expired"] = expired
            trace.setdefault("expired_regions", {})
            trace["expired_regions"][name] = expired_quantity
    state.second_output_stock = pool


def _try_commodity_spec(commodity_id: str) -> CommoditySpec | None:
    try:
        from hsm_lab.contract.material import commodity_spec

        return commodity_spec(commodity_id)
    except Exception:  # pragma: no cover - defensive only; spec must exist for F2 axes
        return None


# ---------------------------------------------------------------------------
# Invariant check: F2 pool + ledger reconciliation
# ---------------------------------------------------------------------------


def check_f2_second_economy(
    opening: MaterialStockSnapshot | None,
    state: MaterialState,
    flows: MaterialTickFlows,
    network: Any,
    trace: dict[str, Any] | None,
) -> dict[str, float]:
    """Validate F2 pool continuity and journal-counterparty ledger closure.

    Every identity is checked per (region, commodity) or per household; a
    national netting that hides offsetting regional errors is never accepted.
    The trace must be bound to this tick and this recipe hash.
    """
    recipe = _f2_recipe(network)
    if recipe is None:
        return {"f2_checked": 0.0, "f2_pool_residual": 0.0, "f2_input_residual": 0.0}
    if trace is None:
        raise AccountingError("F2 invariant requires a populated trace dict")
    if trace.get("tick") != int(flows.tick):
        raise AccountingError(
            f"F2 trace tick {trace.get('tick')!r} does not match flow tick {int(flows.tick)!r}"
        )
    if trace.get("recipe_hash") != recipe.recipe_hash:
        raise AccountingError(
            f"F2 trace recipe hash {trace.get('recipe_hash')!r} != "
            f"expected {recipe.recipe_hash!r}"
        )

    commodity_ids = list(network.commodity_ids)
    commodity_index = {cid: index for index, cid in enumerate(commodity_ids)}
    g_count = len(commodity_ids)
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    weight = np.asarray(state.household_weight, dtype=np.float64)
    region = np.asarray(state.household_region, dtype=np.int64)
    catalog_to_material = _catalog_to_material(network)
    opening_pool = (
        np.asarray(opening.second_output_stock, dtype=np.float64)
        if opening is not None
        else np.zeros((region_count, g_count), dtype=np.float64)
    )
    closing_pool = np.asarray(state.second_output_stock, dtype=np.float64)
    produced = _f2_trace_array(
        trace, "produced", shape=(region_count, g_count), dtype=np.float64
    )
    expired = _f2_trace_array(
        trace, "expired", shape=(region_count, g_count), dtype=np.float64
    )
    activity = _f2_trace_array(trace, "activity", shape=(region_count,), dtype=np.float64)
    if not (
        np.all(np.isfinite(opening_pool))
        and np.all(np.isfinite(closing_pool))
        and np.all(np.isfinite(produced))
        and np.all(np.isfinite(expired))
        and np.all(np.isfinite(activity))
    ):
        raise AccountingError(f"F2 trace for tick {int(flows.tick)} contains non-finite values")
    if np.any(produced < 0.0) or np.any(expired < 0.0) or np.any(activity < 0.0):
        raise AccountingError(f"F2 trace for tick {int(flows.tick)} has negative quantities")

    # The trace is evidence, not authority: production is re-derived from the
    # recorded activity and the frozen recipe coefficients, per (region,
    # commodity).  A trace whose produced block was edited cannot survive.
    expected_produced = np.zeros((region_count, g_count), dtype=np.float64)
    for name, coefficient in recipe.output_coefficients:
        g = commodity_index[name]
        expected_produced[:, g] = expected_produced[:, g] + activity * float(coefficient)
    produced_gap = np.abs(expected_produced - produced)
    if bool(np.any(produced_gap > tolerance_for(expected_produced, produced))):
        bad = np.unravel_index(int(np.argmax(produced_gap)), produced_gap.shape)
        raise AccountingError(
            f"F2 produced quantity for {commodity_ids[bad[1]]} in region {bad[0]} is "
            f"{produced[bad]:.9f} but activity {float(activity[bad[0]]):.9f} x recipe "
            f"coefficient gives {expected_produced[bad]:.9f} (tick {int(flows.tick)})"
        )

    # Household second acquisition (normal + second substitution) is already
    # in ``flows.household_second_h``; project it to the parent commodity axis
    # once and aggregate by region.
    second_h = np.asarray(flows.household_second_h, dtype=np.float64)
    if catalog_to_material is None:
        raise AccountingError("F2 invariant requires the compiled household catalog")
    if second_h.shape != (weight.size, catalog_to_material.shape[0]):
        raise AccountingError(
            f"F2 household_second_h shape {second_h.shape} does not match the catalog"
        )
    weighted_g = np.einsum("nh,hg->ng", np.maximum(second_h, 0.0), catalog_to_material)
    consumed_g_region = np.zeros((region_count, g_count), dtype=np.float64)
    for g in range(g_count):
        consumed_g_region[:, g] = np.bincount(
            region, weights=weight * weighted_g[:, g], minlength=region_count
        )

    # Pool identity: opening + produced - expired - consumed == closing,
    # checked per (region, commodity).
    expected_close = opening_pool + produced - expired - consumed_g_region
    tolerance = tolerance_for(expected_close, closing_pool)
    pool_gap = np.abs(expected_close - closing_pool)
    if bool(np.any(pool_gap > tolerance)):
        bad = np.unravel_index(int(np.argmax(pool_gap)), pool_gap.shape)
        raise AccountingError(
            f"F2 pool continuity broken at region {bad[0]}, "
            f"{commodity_ids[bad[1]]}: expected {expected_close[bad]:.9f}, "
            f"got {closing_pool[bad]:.9f} (tick {int(flows.tick)})"
        )

    # Expiry is re-derived from the real commodity spec's ``stockable`` trait,
    # not from the trace and not from a legacy string heuristic:
    #   * non-stockable output must not survive the tick, and what left the pool
    #     is exactly opening + produced - consumed;
    #   * stockable output must never be written off as expired.
    specs = [_try_commodity_spec(name) for name in commodity_ids]
    for name, _coefficient in recipe.output_coefficients:
        g = commodity_index[name]
        spec = specs[g]
        stockable = bool(getattr(spec, "stockable", True)) if spec is not None else True
        if stockable:
            leaked = np.abs(expired[:, g])
            if bool(np.any(leaked > tolerance_for(0.0, expired[:, g]))):
                bad = int(np.argmax(leaked))
                raise AccountingError(
                    f"F2 trace expires {float(expired[bad, g]):.9f} of stockable "
                    f"{name!r} in region {bad} (tick {int(flows.tick)})"
                )
            continue
        retained = np.abs(closing_pool[:, g])
        if bool(np.any(retained > tolerance_for(0.0, closing_pool[:, g]))):
            bad = int(np.argmax(retained))
            raise AccountingError(
                f"F2 non-stockable {name!r} keeps {float(closing_pool[bad, g]):.9f} "
                f"in the second-output pool at region {bad} (tick {int(flows.tick)})"
            )
        expected_expiry = opening_pool[:, g] + produced[:, g] - consumed_g_region[:, g]
        expiry_gap = np.abs(expected_expiry - expired[:, g])
        if bool(np.any(expiry_gap > tolerance_for(expected_expiry, expired[:, g]))):
            bad = int(np.argmax(expiry_gap))
            raise AccountingError(
                f"F2 expiry for non-stockable {name!r} broken at region {bad}: "
                f"opening+produced-consumed = {expected_expiry[bad]:.9f}, "
                f"trace records {expired[bad, g]:.9f} (tick {int(flows.tick)})"
            )

    # Input continuity per (region, input commodity).
    input_used = np.asarray(flows.second_input_used, dtype=np.float64)
    cell_region = np.asarray(network.cell_region, dtype=np.int64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    input_residual = 0.0
    for name, coefficient in recipe.input_coefficients:
        g = commodity_index[name]
        mask = cell_commodity == g
        used_by_region = np.bincount(
            cell_region[mask],
            weights=input_used[mask],
            minlength=region_count,
        )
        expected = activity * float(coefficient)
        gap = np.abs(used_by_region - expected)
        tol = tolerance_for(expected, used_by_region)
        input_residual = max(input_residual, float(np.max(gap)))
        if bool(np.any(gap > tol)):
            bad = int(np.argmax(gap))
            raise AccountingError(
                f"F2 input continuity for {name!r} broken at region {bad}: "
                f"expected {expected[bad]:.9f}, got {used_by_region[bad]:.9f}"
            )

    # Production hours <= reserved cohort hours, per region.
    hours = np.asarray(state.household_reserved_second_hours, dtype=np.float64)
    region_hours = np.zeros(region_count, dtype=np.float64)
    cohort = np.asarray(state.household_second_participating, dtype=bool) & (
        np.asarray(state.household_working_adults, dtype=np.float64) > 0.0
    )
    np.add.at(region_hours, region[cohort], (weight * hours)[cohort])
    used_hours = activity * float(recipe.hours_per_activity)
    overrun = used_hours - region_hours
    if bool(np.any(overrun > 1e-6 + 1e-9 * np.maximum(region_hours, 1.0))):
        bad = int(np.argmax(overrun))
        raise AccountingError(
            f"F2 production exceeds reserved hours in region {bad}: "
            f"{float(used_hours[bad]):.6f} > {float(region_hours[bad]):.6f}"
        )

    # Funding closure: weighted household funding == seller cell credits.
    funding = np.asarray(
        trace.get("funding", np.zeros(0, dtype=np.float64)), dtype=np.float64
    )
    seller_credit = np.asarray(
        trace.get("seller_credit", np.zeros(0, dtype=np.float64)), dtype=np.float64
    )
    flow_funding = np.asarray(flows.household_second_input_funding, dtype=np.float64)
    if funding.shape != flow_funding.shape:
        raise AccountingError(
            f"F2 funding trace shape {funding.shape} does not match the flow "
            f"{flow_funding.shape}"
        )
    funding_gap = np.abs(funding - flow_funding)
    if bool(np.any(funding_gap > tolerance_for(funding, flow_funding))):
        bad = int(np.argmax(funding_gap))
        raise AccountingError(
            f"F2 funding trace for household {bad} is {funding[bad]:.9f}, the "
            f"settlement flow records {flow_funding[bad]:.9f}"
        )
    paid_by_household = float((weight * funding).sum()) if funding.size else 0.0
    paid_to_sellers = float(seller_credit.sum()) if seller_credit.size else 0.0
    if abs(paid_by_household - paid_to_sellers) > tolerance_for(
        paid_by_household, paid_to_sellers
    ):
        raise AccountingError(
            f"F2 funding closure broken: cohort paid {paid_by_household:.9f}, "
            f"sellers received {paid_to_sellers:.9f}"
        )

    # Direct-sale revenue belongs to the same participating cohort and equals
    # the priced second-economy basket (normal + second substitution).
    catalog = network.household_catalog
    price_h = np.asarray(catalog.price_h, dtype=np.float64)
    second_spend = np.asarray(second_h, dtype=np.float64) @ price_h
    actual_receipt_array = np.asarray(
        flows.household_second_income_direct, dtype=np.float64
    )
    if actual_receipt_array.shape != (weight.size,):
        raise AccountingError(
            f"F2 household_second_income_direct shape {actual_receipt_array.shape} "
            f"does not match the household axis"
        )
    actual_receipts = float((weight * actual_receipt_array).sum())

    # Per-household receipts, not the national net: the regional sale is
    # ``sum(weight * second_spend)`` and each participating household with
    # working adults takes ``working_i / sum_cohort(weight*working)`` of it.  An
    # offset between two participants leaves the weighted total intact and is
    # therefore invisible to the aggregate identity above.
    working = np.asarray(state.household_working_adults, dtype=np.float64)
    sale_by_region = np.bincount(
        region, weights=weight * second_spend, minlength=region_count
    )
    cohort_workers = np.bincount(
        region[cohort], weights=(weight * working)[cohort], minlength=region_count
    )
    expected_receipt = np.zeros(weight.size, dtype=np.float64)
    for r in range(region_count):
        if sale_by_region[r] <= 0.0 or cohort_workers[r] <= 0.0:
            continue
        mask = (region == r) & cohort
        if bool(np.any(mask)):
            expected_receipt[mask] = sale_by_region[r] * working[mask] / cohort_workers[r]
    receipt_gap = np.abs(expected_receipt - actual_receipt_array)
    if bool(np.any(receipt_gap > tolerance_for(expected_receipt, actual_receipt_array))):
        bad = int(np.argmax(receipt_gap))
        raise AccountingError(
            f"F2 direct-sale receipt for household {bad} (region {int(region[bad])}) is "
            f"{actual_receipt_array[bad]:.9f}, working share of the regional sale gives "
            f"{expected_receipt[bad]:.9f} (tick {int(flows.tick)})"
        )

    # Journal counterparty check: the deterministic two-pointer buyer/seller
    # matching is recomputed here and compared leg by leg (account, currency,
    # amount), so a swapped debit/credit, a shifted amount, a foreign currency
    # or a non-household cash account cannot hide behind an equal total.
    from hsm_lab.engine import finance

    kind = np.asarray(flows.journal_kind, dtype=object)
    debit = np.asarray(flows.journal_debit, dtype=np.int64)
    credit = np.asarray(flows.journal_credit, dtype=np.int64)
    amount = np.asarray(flows.journal_amount, dtype=np.float64)
    currency = np.asarray(flows.journal_currency, dtype=object)
    cash_accounts = set(
        finance.household_account_ids(state, "cash_deposit").tolist()
    )
    sale_legs = kind == "hist_second_direct_sale"
    expected_leg_debit, expected_leg_credit, expected_leg_amount = (
        _expected_direct_sale_legs(
            region=region,
            weight=weight,
            buyer_amount=second_spend,
            seller_amount=expected_receipt,
            household_cash_account=finance.household_account_ids(state, "cash_deposit"),
        )
    )
    recorded_count = int(np.count_nonzero(sale_legs))
    if recorded_count != int(expected_leg_amount.size):
        raise AccountingError(
            f"F2 direct-sale journal carries {recorded_count} legs, the recomputed "
            f"buyer/seller matching needs {int(expected_leg_amount.size)} "
            f"(tick {int(flows.tick)})"
        )
    if recorded_count:
        if not (
            all(int(v) in cash_accounts for v in debit[sale_legs])
            and all(int(v) in cash_accounts for v in credit[sale_legs])
        ):
            raise AccountingError("F2 direct-sale journal names a non-household-cash account")
        if not bool(np.all(currency[sale_legs] == finance.DOMESTIC_CURRENCY)):
            raise AccountingError("F2 direct-sale journal leg is not in the domestic currency")
        leg_positions = np.flatnonzero(sale_legs)
        for index, position in enumerate(leg_positions):
            expected_amount = float(expected_leg_amount[index])
            recorded_amount = float(amount[position])
            if (
                int(debit[position]) == int(expected_leg_debit[index])
                and int(credit[position]) == int(expected_leg_credit[index])
                and abs(recorded_amount - expected_amount)
                <= tolerance_for(expected_amount, recorded_amount)
            ):
                continue
            raise AccountingError(
                f"F2 direct-sale journal leg {index} is debit {int(debit[position])} / "
                f"credit {int(credit[position])} / {recorded_amount:.9f}; the recomputed "
                f"matching requires debit {int(expected_leg_debit[index])} / credit "
                f"{int(expected_leg_credit[index])} / {expected_amount:.9f} "
                f"(tick {int(flows.tick)})"
            )
        if abs(float(amount[sale_legs].sum()) - actual_receipts) > tolerance_for(
            float(amount[sale_legs].sum()), actual_receipts
        ):
            raise AccountingError(
                "F2 direct-sale journal amount does not match household receipts"
            )
    elif actual_receipts > tolerance_for(actual_receipts, 0.0):
        raise AccountingError("F2 direct-sale receipts have no journal legs")

    input_legs = kind == "hist_second_input_payment"
    bank_count = int(np.asarray(state.bank_reserves).shape[0])
    hh_bank = region % max(bank_count, 1)
    expected_delta = -np.bincount(
        hh_bank, weights=weight * funding, minlength=bank_count
    )
    org_bank = np.asarray(state.organization_bank, dtype=np.int64)
    safe_org_bank = np.where(org_bank >= 0, org_bank, 0)
    expected_delta += np.bincount(
        safe_org_bank, weights=seller_credit, minlength=bank_count
    )
    deposit_liability = finance.bank_account_ids(
        state, finance.AccountKind.DEPOSIT_LIABILITY
    )
    reserves = finance.bank_account_ids(state, finance.AccountKind.RESERVES)
    expected_debit, expected_credit, expected_amount = _expected_interbank_legs(
        delta=expected_delta,
        deposit_liability=deposit_liability,
        reserves=reserves,
    )
    recorded_input = int(np.count_nonzero(input_legs))
    if recorded_input != int(expected_amount.size):
        raise AccountingError(
            f"F2 input-payment journal carries {recorded_input} legs, the "
            f"recomputed bank settlement needs {int(expected_amount.size)}"
        )
    if recorded_input:
        if not bool(np.all(currency[input_legs] == finance.DOMESTIC_CURRENCY)):
            raise AccountingError(
                "F2 input-payment journal leg is not in the domestic currency"
            )
        positions = np.flatnonzero(input_legs)
        for index, position in enumerate(positions):
            expected_amt = float(expected_amount[index])
            recorded_amt = float(amount[position])
            if (
                int(debit[position]) == int(expected_debit[index])
                and int(credit[position]) == int(expected_credit[index])
                and abs(recorded_amt - expected_amt)
                <= tolerance_for(expected_amt, recorded_amt)
            ):
                continue
            raise AccountingError(
                f"F2 input-payment journal leg {index} is debit {int(debit[position])} / "
                f"credit {int(credit[position])} / {recorded_amt:.9f}; the recomputed "
                f"bank settlement requires debit {int(expected_debit[index])} / credit "
                f"{int(expected_credit[index])} / {expected_amt:.9f}"
            )

    return {
        "f2_checked": 1.0,
        "f2_pool_residual": float(np.max(pool_gap)),
        "f2_input_residual": float(input_residual),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _expected_direct_sale_legs(
    *,
    region: np.ndarray,
    weight: np.ndarray,
    buyer_amount: np.ndarray,
    seller_amount: np.ndarray,
    household_cash_account: np.ndarray,
    tolerance: float = 1e-9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Recompute the direct-sale buyer/seller matching as journal legs.

    Independent re-derivation of what ``append_f2_direct_sale_journal`` must
    write: ascending region, then ascending household id, two-pointer on the
    represented amounts ``weight * amount``.  Returns parallel
    ``(debit_account, credit_account, amount)`` arrays in leg order.
    """
    region = np.asarray(region, dtype=np.int64)
    weight = np.asarray(weight, dtype=np.float64)
    buyer_amount = np.asarray(buyer_amount, dtype=np.float64)
    seller_amount = np.asarray(seller_amount, dtype=np.float64)
    debits: list[int] = []
    credits: list[int] = []
    amounts: list[float] = []
    for r in np.unique(region):
        buyers = np.flatnonzero((region == r) & (weight * buyer_amount > tolerance))
        sellers = np.flatnonzero((region == r) & (weight * seller_amount > tolerance))
        if buyers.size == 0 or sellers.size == 0:
            continue
        buyer_left = weight[buyers] * buyer_amount[buyers]
        seller_left = weight[sellers] * seller_amount[sellers]
        i = 0
        j = 0
        while i < buyers.size and j < sellers.size:
            matched = float(min(buyer_left[i], seller_left[j]))
            if matched > tolerance:
                debits.append(int(household_cash_account[buyers[i]]))
                credits.append(int(household_cash_account[sellers[j]]))
                amounts.append(matched)
            buyer_left[i] -= matched
            seller_left[j] -= matched
            if buyer_left[i] <= tolerance:
                i += 1
            if seller_left[j] <= tolerance:
                j += 1
    return (
        np.asarray(debits, dtype=np.int64),
        np.asarray(credits, dtype=np.int64),
        np.asarray(amounts, dtype=np.float64),
    )


def _expected_interbank_legs(
    *,
    delta: np.ndarray,
    deposit_liability: np.ndarray,
    reserves: np.ndarray,
    tolerance: float = 1e-9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Recompute ``finance._append_interbank_legs`` output for a bank delta."""
    remaining = np.asarray(delta, dtype=np.float64).copy()
    debits: list[int] = []
    credits: list[int] = []
    amounts: list[float] = []
    while True:
        gainers = np.flatnonzero(remaining > tolerance)
        losers = np.flatnonzero(remaining < -tolerance)
        if gainers.size == 0 or losers.size == 0:
            break
        gainer = int(gainers[0])
        loser = int(losers[0])
        matched = float(min(remaining[gainer], -remaining[loser]))
        debits.extend(
            [int(deposit_liability[gainer]), int(reserves[gainer])]
        )
        credits.extend(
            [int(deposit_liability[loser]), int(reserves[loser])]
        )
        amounts.extend([matched, matched])
        remaining[gainer] -= matched
        remaining[loser] += matched
    return (
        np.asarray(debits, dtype=np.int64),
        np.asarray(credits, dtype=np.int64),
        np.asarray(amounts, dtype=np.float64),
    )


def _f2_trace_array(
    trace: dict[str, Any], key: str, *, shape: tuple[int, ...], dtype: Any
) -> np.ndarray:
    """Return a typed trace array, raising when the trace is malformed."""
    if trace is None:
        raise AccountingError("F2 trace missing array access")
    if key not in trace:
        raise AccountingError(f"F2 trace missing key {key!r}")
    value = np.asarray(trace[key], dtype=dtype)
    if value.shape != shape:
        raise AccountingError(
            f"F2 trace {key!r} shape {value.shape} != expected {shape}"
        )
    return value


def _catalog_to_material(network: Any) -> np.ndarray | None:
    catalog = getattr(network, "household_catalog", None)
    if catalog is None:
        return None
    return np.asarray(getattr(catalog, "to_material", np.zeros((0, 0))))


def _record_zero_trace(
    trace: dict[str, Any] | None,
    network: Any,
    state: MaterialState,
    *,
    tick: int,
) -> None:
    if trace is None:
        return
    commodity_ids = tuple(network.commodity_ids)
    g_count = len(commodity_ids)
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    recipe = getattr(network, "second_economy_f2_recipe", None)
    recipe_hash = recipe.recipe_hash if recipe is not None else ""
    trace["tick"] = int(tick)
    trace["recipe_hash"] = recipe_hash
    trace["produced"] = np.zeros((region_count, g_count), dtype=np.float64)
    trace["expired"] = np.zeros((region_count, g_count), dtype=np.float64)
    trace["activity"] = np.zeros(region_count, dtype=np.float64)
    trace["funding"] = np.zeros(
        int(np.asarray(state.household_id).shape[0]), dtype=np.float64
    )
    trace["seller_credit"] = np.zeros(
        int(np.asarray(state.organization_id).shape[0]), dtype=np.float64
    )
    retail_cell = np.asarray(network.retail_cell_by_commodity, dtype=np.int64)
    stock = np.asarray(state.stock_value, dtype=np.float64)
    formal_available = np.zeros((region_count, g_count), dtype=np.float64)
    for r in range(region_count):
        for g in range(g_count):
            cell = int(retail_cell[r, g])
            if cell >= 0:
                formal_available[r, g] = max(float(stock[cell]), 0.0)
    trace["formal_available_after_input"] = formal_available


def _record_settle_trace(
    trace: dict[str, Any],
    *,
    state: MaterialState,
    network: Any,
    tick: int,
    realized: np.ndarray,
    new_input_used: np.ndarray,
    funding: np.ndarray,
    seller_credit: np.ndarray,
    weighted_workers: np.ndarray,
    weighted_hours: np.ndarray,
    weighted_cash: np.ndarray,
    capacity: np.ndarray,
    labor: np.ndarray,
    cash_cap: np.ndarray,
    availability: np.ndarray,
    commodity_index: dict[str, int],
) -> None:
    recipe = getattr(network, "second_economy_f2_recipe", None)
    if recipe is None:
        return
    commodity_ids = tuple(network.commodity_ids)
    g_count = len(commodity_ids)
    region_count = realized.shape[0]
    produced = np.zeros((region_count, g_count), dtype=np.float64)
    for name, coefficient in recipe.output_coefficients:
        g = commodity_index[name]
        produced[:, g] = produced[:, g] + realized * float(coefficient)
    # Capture post-second formal availability from real retail cells.
    retail_cell = np.asarray(network.retail_cell_by_commodity, dtype=np.int64)
    stock = np.asarray(state.stock_value, dtype=np.float64)
    formal_available = np.zeros((region_count, g_count), dtype=np.float64)
    for r in range(region_count):
        for g in range(g_count):
            cell = int(retail_cell[r, g])
            if cell >= 0:
                formal_available[r, g] = max(float(stock[cell]), 0.0)
    expired_regions = {}
    trace["tick"] = int(tick)
    trace["recipe_hash"] = recipe.recipe_hash
    trace["produced"] = produced
    trace["expired"] = np.zeros((region_count, g_count), dtype=np.float64)
    trace["activity"] = realized.copy()
    trace["funding"] = funding.copy()
    trace["seller_credit"] = seller_credit.copy()
    trace["capacity"] = capacity.copy()
    trace["labor"] = labor.copy()
    trace["cash_cap"] = cash_cap.copy()
    trace["availability"] = availability.copy()
    trace["weighted_workers"] = weighted_workers.copy()
    trace["weighted_hours"] = weighted_hours.copy()
    trace["weighted_cash"] = weighted_cash.copy()
    trace["formal_available_after_input"] = formal_available
    trace["expired_regions"] = expired_regions
    trace.setdefault("new_input_used", new_input_used.copy())


def append_f2_direct_sale_journal(
    state: MaterialState,
    flows: MaterialTickFlows,
    *,
    region: np.ndarray,
    weight: np.ndarray,
    buyer_amount: np.ndarray,
    seller_amount: np.ndarray,
) -> None:
    """Append one ``hist_second_direct_sale`` leg per matched buyer/seller pair.

    ``buyer_amount`` and ``seller_amount`` are state-unit amounts (already
    priced).  Within each region both sides are consumed in ascending
    household-id order by a two-pointer sweep, so the journal names the real
    counterparties without constructing a dense household-by-seller matrix.
    The cash/bank movement itself is settled once by the allocator's ledger.
    """
    from hsm_lab.engine import finance

    buyer_amount = np.asarray(buyer_amount, dtype=np.float64)
    seller_amount = np.asarray(seller_amount, dtype=np.float64)
    weight = np.asarray(weight, dtype=np.float64)
    region = np.asarray(region, dtype=np.int64)
    hh_cash = finance.household_account_ids(state, "cash_deposit")
    tolerance = 1e-9
    leg_offset = 0
    for r in np.unique(region):
        buyers = np.flatnonzero(
            (region == r) & (weight * buyer_amount > tolerance)
        )
        sellers = np.flatnonzero(
            (region == r) & (weight * seller_amount > tolerance)
        )
        if buyers.size == 0 or sellers.size == 0:
            continue
        buyer_left = weight[buyers] * buyer_amount[buyers]
        seller_left = weight[sellers] * seller_amount[sellers]
        i = 0
        j = 0
        while i < buyers.size and j < sellers.size:
            amount = float(min(buyer_left[i], seller_left[j]))
            if amount > tolerance:
                finance._append_legs(
                    flows,
                    kind="hist_second_direct_sale",
                    currency=finance.DOMESTIC_CURRENCY,
                    debit=np.array([hh_cash[buyers[i]]], dtype=np.int64),
                    credit=np.array([hh_cash[sellers[j]]], dtype=np.int64),
                    amount=np.array([amount], dtype=np.float64),
                    leg_offset=leg_offset,
                )
                leg_offset += 1
            buyer_left[i] -= amount
            seller_left[j] -= amount
            if buyer_left[i] <= tolerance:
                i += 1
            if seller_left[j] <= tolerance:
                j += 1


__all__ = [
    "F2SecondEconomyRecipe",
    "F2SecondEconomyNetwork",
    "append_f2_direct_sale_journal",
    "attach_f2_second_economy",
    "plan_f2_household_time",
    "settle_f2_second_economy",
    "expire_f2_second_economy",
    "check_f2_second_economy",
]
