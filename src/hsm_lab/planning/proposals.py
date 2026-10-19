"""H3E: frozen information-bound planning inputs and proposal containers.

The module is deliberately data-only.  It never reads ``MaterialState``,
``MaterialForcing``, a session, a target or the filesystem.  A caller supplies
already-available :class:`~hsm_lab.institutions.observed.ActorObservation`
records plus a frozen synthetic technology declaration; the builder validates
information cutoffs, required values, units, currencies and identity, then
produces immutable arrays that a solver may read.

The four-quarter horizon is a planning horizon, not an experiment length.  All
future values are explicit ``last_available_constant`` forecasts.  No future
kernel state or forcing array can enter through this module.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

import numpy as np

from hsm_lab.contract.base import ResearchGateError
from hsm_lab.engine.accounting import ATOL
from hsm_lab.institutions.observed import (
    ActorObservation,
    verify_observation_invariants,
)

SCHEMA_VERSION = "hist-bounded-planning-v1"
HORIZON_QUARTERS = 4
SOURCE_KIND = "synthetic"
FORECAST_METHOD = "last_available_constant"
GATE_PREFIX = "HIST_H3E_PLANNING"
ARMS: tuple[str, ...] = (
    "historical_rule_based",
    "bounded_planning",
    "full_information_upper_bound",
)
PRIORITY: tuple[str, ...] = (
    "minimize_normalized_household_final_shortfall",
    "minimize_normalized_other_shortfall",
    "minimize_purchase_and_freight_cost",
    "minimize_canonical_edge_tiebreak",
)

BUDGET_PAYER_KINDS = ("funding_group", "bank_prepayment")


def _reject(message: str) -> None:
    raise ResearchGateError(f"{GATE_PREFIX}: {message}")


def _exact_str(value: Any, name: str) -> str:
    if type(value) is not str or not value:
        _reject(f"{name} must be a non-empty exact string")
    return value


def _exact_int(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        _reject(f"{name} must be a non-negative exact integer")
    return int(value)


def _exact_date(value: Any, name: str) -> date:
    if type(value) is not date:
        _reject(f"{name} must be a plain date")
    return value


def _frozen(
    value: Any,
    shape: tuple[int, ...],
    name: str,
    *,
    non_negative: bool = True,
) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != shape:
        _reject(f"{name} shape {array.shape} does not match {shape}")
    if not bool(np.all(np.isfinite(array))):
        _reject(f"{name} contains a non-finite value")
    if non_negative and bool(np.any(array < -ATOL)):
        bad = int(np.argmin(array))
        _reject(f"{name}[{bad}]={float(array.ravel()[bad])!r} is negative")
    array = np.ascontiguousarray(array, dtype=np.float64)
    return np.frombuffer(array.tobytes(), dtype=np.float64).reshape(shape)


def _frozen_int(value: Any, shape: tuple[int, ...], name: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.int64)
    if array.shape != shape:
        _reject(f"{name} shape {array.shape} does not match {shape}")
    array = np.ascontiguousarray(array, dtype=np.int64)
    return np.frombuffer(array.tobytes(), dtype=np.int64).reshape(shape)


def _frozen_bool(value: Any, shape: tuple[int, ...], name: str) -> np.ndarray:
    array = np.asarray(value, dtype=bool)
    if array.shape != shape:
        _reject(f"{name} shape {array.shape} does not match {shape}")
    array = np.ascontiguousarray(array, dtype=bool)
    return np.frombuffer(array.tobytes(), dtype=bool).reshape(shape)


def _array_digest(array: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode("ascii"))
    digest.update(repr(tuple(array.shape)).encode("ascii"))
    digest.update(np.ascontiguousarray(array).tobytes())
    return digest.hexdigest()


def _hash_arrays(arrays: dict[str, np.ndarray], scalars: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for key in sorted(arrays):
        digest.update(key.encode("utf-8"))
        digest.update(_array_digest(arrays[key]).encode("ascii"))
    for key in sorted(scalars):
        digest.update(key.encode("utf-8"))
        digest.update(repr(scalars[key]).encode("utf-8"))
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Frozen synthetic declarations
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanningDeclarations:
    """A frozen, source-labelled synthetic planning world.

    Goods are addressed by ``"commodity|stage"``.  Service goods are never
    traded on an edge and never carry across quarters.  Recipes are Leontief:
    one unit of activity consumes every listed input coefficient and produces
    ``recipe_output_coeff`` units of one output good.
    """

    source_kind: str
    quarters: tuple[str, ...]
    terminal_mask: tuple[bool, ...]
    currency: str
    bank_count: int
    organization_ids: tuple[str, ...]
    organization_bank: np.ndarray
    organization_cash_opening: np.ndarray
    goods_id: tuple[str, ...]
    goods_is_service: np.ndarray
    prices: np.ndarray
    inventory_opening: np.ndarray
    wage: np.ndarray
    funding_capacity: np.ndarray
    service_capacity: np.ndarray
    handling_capacity: np.ndarray
    bank_reserves: np.ndarray
    edge_id: np.ndarray
    edge_seller: np.ndarray
    edge_buyer: np.ndarray
    edge_good: np.ndarray
    edge_unit_price: np.ndarray
    edge_transport_org: np.ndarray
    edge_freight_per_unit: np.ndarray
    edge_handling_per_unit: np.ndarray
    edge_capacity: np.ndarray
    demand_id: tuple[str, ...]
    demand_buyer: np.ndarray
    demand_good: np.ndarray
    demand_final: np.ndarray
    demand_ordered: np.ndarray
    demand_gross: np.ndarray
    recipe_id: tuple[str, ...]
    recipe_org: np.ndarray
    recipe_output_good: np.ndarray
    recipe_output_coeff: np.ndarray
    recipe_input_ptr: np.ndarray
    recipe_input_good: np.ndarray
    recipe_input_coeff: np.ndarray
    recipe_capacity: np.ndarray
    edge_baseline: np.ndarray | None = None
    organization_funding_group: np.ndarray | None = None
    funding_group_capacity: np.ndarray | None = None
    organization_currency: tuple[str, ...] | None = None
    organization_interest: np.ndarray | None = None
    organization_order_financing: np.ndarray | None = None
    edge_service_good: np.ndarray | None = None
    organization_service_good: np.ndarray | None = None
    baseline_procurement: np.ndarray | None = None
    edge_freight_price: np.ndarray | None = None
    recipe_tier: np.ndarray | None = None
    service_split: tuple[float, float, float] = (1.0, 0.0, 0.0)
    decision_organization_ids: tuple[str, ...] | None = None
    required_reports: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if type(self.source_kind) is not str or self.source_kind != SOURCE_KIND:
            _reject("declarations.source_kind must be 'synthetic'")
        if (
            type(self.quarters) is not tuple
            or len(self.quarters) != HORIZON_QUARTERS
            or any(type(q) is not str or not q for q in self.quarters)
        ):
            _reject("declarations.quarters must be four non-empty strings")
        if len(set(self.quarters)) != HORIZON_QUARTERS:
            _reject("declarations.quarters must be unique")
        _exact_str(self.currency, "declarations.currency")
        if type(self.terminal_mask) is not tuple or len(self.terminal_mask) != HORIZON_QUARTERS:
            _reject("declarations.terminal_mask must be a four-element tuple")
        if any(type(v) is not bool for v in self.terminal_mask):
            _reject("declarations.terminal_mask must be exact bools")
        active = list(self.terminal_mask)
        if not active[0]:
            _reject("declarations.terminal_mask must start active")
        seen_inactive = False
        for value in active:
            if value:
                if seen_inactive:
                    _reject("declarations.terminal_mask must be an active prefix")
            else:
                seen_inactive = True

        org_ids = tuple(_exact_str(v, "organization_ids") for v in self.organization_ids)
        if not org_ids or len(set(org_ids)) != len(org_ids):
            _reject("organization_ids must be non-empty and unique")
        object.__setattr__(self, "organization_ids", org_ids)
        org_count = len(org_ids)

        goods_ids = tuple(_exact_str(v, "goods_id") for v in self.goods_id)
        if not goods_ids or len(set(goods_ids)) != len(goods_ids):
            _reject("goods_id must be non-empty and unique")
        object.__setattr__(self, "goods_id", goods_ids)
        good_count = len(goods_ids)

        _exact_int(self.bank_count, "declarations.bank_count")
        if self.bank_count <= 0:
            _reject("bank_count must be positive")

        shape_o = (org_count,)
        shape_g = (good_count,)
        shape_og = (org_count, good_count)
        shape_4o = (HORIZON_QUARTERS, org_count)
        shape_4g = (HORIZON_QUARTERS, good_count)
        shape_4b = (HORIZON_QUARTERS, int(self.bank_count))

        object.__setattr__(
            self,
            "organization_bank",
            _frozen_int(self.organization_bank, shape_o, "organization_bank"),
        )
        if bool(np.any(self.organization_bank >= int(self.bank_count))):
            _reject("organization_bank is outside the bank axis")
        object.__setattr__(
            self,
            "organization_cash_opening",
            _frozen(self.organization_cash_opening, shape_o, "organization_cash_opening"),
        )
        object.__setattr__(
            self,
            "goods_is_service",
            _frozen_bool(self.goods_is_service, shape_g, "goods_is_service"),
        )
        object.__setattr__(self, "prices", _frozen(self.prices, shape_4g, "prices"))
        object.__setattr__(
            self,
            "inventory_opening",
            _frozen(self.inventory_opening, shape_og, "inventory_opening"),
        )
        object.__setattr__(self, "wage", _frozen(self.wage, shape_4o, "wage"))
        object.__setattr__(
            self, "funding_capacity", _frozen(self.funding_capacity, shape_4o, "funding_capacity")
        )
        object.__setattr__(
            self, "service_capacity", _frozen(self.service_capacity, shape_4o, "service_capacity")
        )
        object.__setattr__(
            self,
            "handling_capacity",
            _frozen(self.handling_capacity, shape_4o, "handling_capacity"),
        )
        object.__setattr__(
            self, "bank_reserves", _frozen(self.bank_reserves, shape_4b, "bank_reserves")
        )

        edge_count = int(np.asarray(self.edge_id).shape[0])
        shape_e = (edge_count,)
        object.__setattr__(self, "edge_id", _frozen_int(self.edge_id, shape_e, "edge_id"))
        if int(np.unique(self.edge_id).size) != edge_count:
            _reject("edge_id must be unique")
        for name in ("edge_seller", "edge_buyer", "edge_good", "edge_transport_org"):
            object.__setattr__(self, name, _frozen_int(getattr(self, name), shape_e, name))
        if bool(np.any((self.edge_seller < 0) | (self.edge_seller >= org_count))):
            _reject("edge_seller is outside the organization axis")
        if bool(np.any((self.edge_buyer < 0) | (self.edge_buyer >= org_count))):
            _reject("edge_buyer is outside the organization axis")
        if bool(np.any((self.edge_good < 0) | (self.edge_good >= good_count))):
            _reject("edge_good is outside the goods axis")
        if bool(np.any((self.edge_transport_org < -1) | (self.edge_transport_org >= org_count))):
            _reject("edge_transport_org is outside the organization axis")
        if bool(np.any(self.edge_seller == self.edge_buyer)):
            _reject("self edges are not admissible")
        for name in (
            "edge_unit_price",
            "edge_freight_per_unit",
            "edge_handling_per_unit",
        ):
            object.__setattr__(self, name, _frozen(getattr(self, name), shape_e, name))
        if self.edge_freight_price is None:
            freight_price = np.array(self.edge_freight_per_unit, dtype=np.float64, copy=True)
        else:
            freight_price = _frozen(self.edge_freight_price, shape_e, "edge_freight_price")
        object.__setattr__(self, "edge_freight_price", freight_price)
        object.__setattr__(
            self,
            "edge_capacity",
            _frozen(self.edge_capacity, (HORIZON_QUARTERS, edge_count), "edge_capacity"),
        )
        if self.edge_baseline is None:
            edge_baseline = np.zeros((HORIZON_QUARTERS, edge_count), dtype=np.float64)
        else:
            edge_baseline = _frozen(
                self.edge_baseline,
                (HORIZON_QUARTERS, edge_count),
                "edge_baseline",
            )
        if bool(np.any(edge_baseline < 0.0)):
            _reject("edge_baseline must be non-negative")
        object.__setattr__(self, "edge_baseline", edge_baseline)

        demand_count = int(np.asarray(self.demand_id).shape[0])
        shape_d = (demand_count,)
        demand_ids = tuple(_exact_str(v, "demand_id") for v in self.demand_id)
        if len(set(demand_ids)) != demand_count:
            _reject("demand_id must be unique")
        object.__setattr__(self, "demand_id", demand_ids)
        for name in ("demand_buyer", "demand_good"):
            object.__setattr__(self, name, _frozen_int(getattr(self, name), shape_d, name))
        if bool(np.any((self.demand_buyer < 0) | (self.demand_buyer >= org_count))):
            _reject("demand_buyer is outside the organization axis")
        if bool(np.any((self.demand_good < 0) | (self.demand_good >= good_count))):
            _reject("demand_good is outside the goods axis")
        object.__setattr__(
            self, "demand_final", _frozen_bool(self.demand_final, shape_d, "demand_final")
        )
        object.__setattr__(
            self,
            "demand_ordered",
            _frozen(self.demand_ordered, (HORIZON_QUARTERS, demand_count), "demand_ordered"),
        )
        object.__setattr__(
            self,
            "demand_gross",
            _frozen(self.demand_gross, (HORIZON_QUARTERS, demand_count), "demand_gross"),
        )
        if bool(np.any(self.demand_ordered > self.demand_gross + 1e-9)):
            _reject("demand_ordered cannot exceed demand_gross")

        recipe_count = int(np.asarray(self.recipe_id).shape[0])
        recipe_ids = tuple(_exact_str(v, "recipe_id") for v in self.recipe_id)
        if len(set(recipe_ids)) != recipe_count:
            _reject("recipe_id must be unique")
        object.__setattr__(self, "recipe_id", recipe_ids)
        shape_r = (recipe_count,)
        for name in ("recipe_org", "recipe_output_good"):
            object.__setattr__(self, name, _frozen_int(getattr(self, name), shape_r, name))
        object.__setattr__(
            self,
            "recipe_output_coeff",
            _frozen(self.recipe_output_coeff, shape_r, "recipe_output_coeff"),
        )
        if bool(np.any((self.recipe_org < 0) | (self.recipe_org >= org_count))):
            _reject("recipe_org is outside the organization axis")
        if bool(np.any((self.recipe_output_good < 0) | (self.recipe_output_good >= good_count))):
            _reject("recipe_output_good is outside the goods axis")
        input_ptr = np.asarray(self.recipe_input_ptr, dtype=np.int64)
        if input_ptr.shape != (recipe_count + 1,):
            _reject("recipe_input_ptr must have recipe_count + 1 entries")
        if input_ptr[0] != 0 or bool(np.any(np.diff(input_ptr) < 0)):
            _reject("recipe_input_ptr must start at zero and be non-decreasing")
        input_count = int(input_ptr[-1])
        if int(np.asarray(self.recipe_input_good).shape[0]) != input_count:
            _reject("recipe_input_good does not match recipe_input_ptr")
        if int(np.asarray(self.recipe_input_coeff).shape[0]) != input_count:
            _reject("recipe_input_coeff does not match recipe_input_ptr")
        object.__setattr__(self, "recipe_input_ptr", input_ptr.copy())
        object.__setattr__(
            self,
            "recipe_input_good",
            _frozen_int(self.recipe_input_good, (input_count,), "recipe_input_good"),
        )
        object.__setattr__(
            self,
            "recipe_input_coeff",
            _frozen(self.recipe_input_coeff, (input_count,), "recipe_input_coeff"),
        )
        if bool(np.any((self.recipe_input_good < 0) | (self.recipe_input_good >= good_count))):
            _reject("recipe_input_good is outside the goods axis")
        object.__setattr__(
            self,
            "recipe_capacity",
            _frozen(self.recipe_capacity, (HORIZON_QUARTERS, recipe_count), "recipe_capacity"),
        )

        if self.organization_funding_group is None:
            funding_group = np.arange(org_count, dtype=np.int64)
        else:
            funding_group = _frozen_int(
                self.organization_funding_group,
                (org_count,),
                "organization_funding_group",
            )
        if funding_group.size and int(funding_group.max()) >= org_count:
            _reject("organization_funding_group is outside the group axis")
        group_count = int(funding_group.max()) + 1 if funding_group.size else 0
        if self.funding_group_capacity is None:
            if group_count != org_count:
                _reject("funding_group_capacity is required for shared funding groups")
            group_capacity = _frozen(
                self.funding_capacity,
                (HORIZON_QUARTERS, group_count),
                "funding_group_capacity",
            )
        else:
            group_capacity = _frozen(
                self.funding_group_capacity,
                (HORIZON_QUARTERS, group_count),
                "funding_group_capacity",
            )
        object.__setattr__(self, "organization_funding_group", funding_group)
        object.__setattr__(self, "funding_group_capacity", group_capacity)

        if self.organization_currency is None:
            organization_currency = (self.currency,) * org_count
        else:
            organization_currency = tuple(
                _exact_str(value, "organization_currency") for value in self.organization_currency
            )
            if len(organization_currency) != org_count:
                _reject("organization_currency must align with organizations")
        object.__setattr__(self, "organization_currency", organization_currency)
        for edge in range(edge_count):
            seller_currency = organization_currency[int(self.edge_seller[edge])]
            buyer_currency = organization_currency[int(self.edge_buyer[edge])]
            if seller_currency != buyer_currency:
                _reject("cross-currency edges require an explicit settlement model")
            carrier = int(self.edge_transport_org[edge])
            if carrier >= 0 and organization_currency[carrier] != buyer_currency:
                _reject("cross-currency freight requires an explicit settlement model")

        if self.organization_interest is None:
            interest = np.zeros((HORIZON_QUARTERS, org_count), dtype=np.float64)
        else:
            interest = _frozen(
                self.organization_interest,
                (HORIZON_QUARTERS, org_count),
                "organization_interest",
            )
        object.__setattr__(self, "organization_interest", interest)
        if self.organization_order_financing is None:
            order_financing = np.array(self.funding_capacity, dtype=np.float64, copy=True)
        else:
            order_financing = _frozen(
                self.organization_order_financing,
                (HORIZON_QUARTERS, org_count),
                "organization_order_financing",
            )
        object.__setattr__(self, "organization_order_financing", order_financing)

        if self.edge_service_good is None:
            edge_service_good = np.full(edge_count, -1, dtype=np.int64)
            if self.organization_service_good is None:
                service_goods = np.flatnonzero(self.goods_is_service)
                default_service = int(service_goods[0]) if service_goods.size else -1
                org_service = np.full(org_count, default_service, dtype=np.int64)
            else:
                org_service = np.asarray(self.organization_service_good, dtype=np.int64)
            for edge in range(edge_count):
                carrier = int(self.edge_transport_org[edge])
                if carrier >= 0:
                    edge_service_good[edge] = int(org_service[carrier])
        else:
            edge_service_good = _frozen_int(
                self.edge_service_good, (edge_count,), "edge_service_good"
            )
        if bool(np.any((edge_service_good < -1) | (edge_service_good >= good_count))):
            _reject("edge_service_good is outside the goods axis")
        for edge in range(edge_count):
            good = int(edge_service_good[edge])
            if good >= 0 and not bool(self.goods_is_service[good]):
                _reject("edge_service_good must name a service good")
            if float(self.edge_freight_per_unit[edge]) > ATOL and good < 0:
                _reject("a freight-using edge must name a service good")
        object.__setattr__(self, "edge_service_good", edge_service_good)

        if self.organization_service_good is None:
            service_goods = np.flatnonzero(self.goods_is_service)
            service_default = int(service_goods[0]) if service_goods.size else -1
            organization_service_good = np.full(org_count, service_default, dtype=np.int64)
        else:
            organization_service_good = _frozen_int(
                self.organization_service_good,
                (org_count,),
                "organization_service_good",
            )
        if bool(
            np.any((organization_service_good < -1) | (organization_service_good >= good_count))
        ):
            _reject("organization_service_good is outside the goods axis")
        for org in range(org_count):
            good = int(organization_service_good[org])
            if good >= 0 and not bool(self.goods_is_service[good]):
                _reject("organization_service_good must name a service good")
        object.__setattr__(self, "organization_service_good", organization_service_good)

        if self.recipe_tier is None:
            recipe_tier = np.zeros(recipe_count, dtype=np.int64)
        else:
            recipe_tier = _frozen_int(self.recipe_tier, (recipe_count,), "recipe_tier")
        object.__setattr__(self, "recipe_tier", recipe_tier)

        if self.baseline_procurement is None:
            baseline = np.zeros((HORIZON_QUARTERS, org_count, good_count), dtype=np.float64)
        else:
            baseline = _frozen(
                self.baseline_procurement,
                (HORIZON_QUARTERS, org_count, good_count),
                "baseline_procurement",
            )
        object.__setattr__(self, "baseline_procurement", baseline)

        if type(self.service_split) is not tuple or len(self.service_split) != 3:
            _reject("service_split must be a three-element tuple")
        split = tuple(float(value) for value in self.service_split)
        if any(not math.isfinite(value) or value < 0.0 for value in split):
            _reject("service_split must be finite and non-negative")
        if abs(sum(split) - 1.0) > 1e-9:
            _reject("service_split must sum to one")
        object.__setattr__(self, "service_split", split)
        object.__setattr__(
            self,
            "recipe_input_ptr",
            np.frombuffer(
                np.ascontiguousarray(input_ptr, dtype=np.int64).tobytes(),
                dtype=np.int64,
            ).reshape(input_ptr.shape),
        )

        if self.decision_organization_ids is None:
            decision_organizations = org_ids
        else:
            decision_organizations = tuple(
                _exact_str(value, "decision_organization_ids")
                for value in self.decision_organization_ids
            )
            if any(value not in org_ids for value in decision_organizations):
                _reject("decision_organization_ids names an unknown organization")
        object.__setattr__(self, "decision_organization_ids", decision_organizations)

        required = tuple(self.required_reports)
        for item in required:
            if type(item) is not tuple or len(item) != 2:
                _reject("required_reports elements must be (organization_id, goods_id)")
            org_id, good_id = item
            if org_id not in org_ids or good_id not in goods_ids:
                _reject(f"required report {item!r} names an unknown organization/good")
        object.__setattr__(self, "required_reports", required)
        if type(self.notes) is not tuple or any(type(n) is not str for n in self.notes):
            _reject("notes must be a tuple of strings")

    def digest(self) -> str:
        arrays = {
            "organization_bank": self.organization_bank,
            "organization_cash_opening": self.organization_cash_opening,
            "goods_is_service": self.goods_is_service.astype(np.float64),
            "prices": self.prices,
            "inventory_opening": self.inventory_opening,
            "wage": self.wage,
            "funding_capacity": self.funding_capacity,
            "service_capacity": self.service_capacity,
            "handling_capacity": self.handling_capacity,
            "bank_reserves": self.bank_reserves,
            "edge_id": self.edge_id,
            "edge_seller": self.edge_seller,
            "edge_buyer": self.edge_buyer,
            "edge_good": self.edge_good,
            "edge_unit_price": self.edge_unit_price,
            "edge_transport_org": self.edge_transport_org,
            "edge_freight_per_unit": self.edge_freight_per_unit,
            "edge_freight_price": self.edge_freight_price,
            "edge_handling_per_unit": self.edge_handling_per_unit,
            "edge_capacity": self.edge_capacity,
            "edge_baseline": self.edge_baseline,
            "demand_buyer": self.demand_buyer,
            "demand_good": self.demand_good,
            "demand_final": self.demand_final.astype(np.float64),
            "demand_ordered": self.demand_ordered,
            "demand_gross": self.demand_gross,
            "recipe_org": self.recipe_org,
            "recipe_output_good": self.recipe_output_good,
            "recipe_output_coeff": self.recipe_output_coeff,
            "recipe_input_ptr": self.recipe_input_ptr,
            "recipe_input_good": self.recipe_input_good,
            "recipe_input_coeff": self.recipe_input_coeff,
            "recipe_capacity": self.recipe_capacity,
            "organization_funding_group": self.organization_funding_group,
            "funding_group_capacity": self.funding_group_capacity,
            "organization_interest": self.organization_interest,
            "organization_order_financing": self.organization_order_financing,
            "edge_service_good": self.edge_service_good,
            "organization_service_good": self.organization_service_good,
            "baseline_procurement": self.baseline_procurement,
        }
        scalars = {
            "source_kind": self.source_kind,
            "quarters": self.quarters,
            "terminal_mask": self.terminal_mask,
            "currency": self.currency,
            "bank_count": self.bank_count,
            "organization_ids": self.organization_ids,
            "goods_id": self.goods_id,
            "demand_id": self.demand_id,
            "recipe_id": self.recipe_id,
            "organization_currency": self.organization_currency,
            "service_split": self.service_split,
            "decision_organization_ids": self.decision_organization_ids,
            "required_reports": self.required_reports,
        }
        return _hash_arrays(arrays, scalars)


# ---------------------------------------------------------------------------
# Observation bindings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanningObservation:
    """One actor observation explicitly bound to an organization and good."""

    organization_id: str
    commodity_id: str
    stage: str
    observation: ActorObservation

    def __post_init__(self) -> None:
        _exact_str(self.organization_id, "observation.organization_id")
        _exact_str(self.commodity_id, "observation.commodity_id")
        _exact_str(self.stage, "observation.stage")
        if type(self.observation) is not ActorObservation:
            _reject("observation must be a concrete ActorObservation")
        if self.observation.actor_role != "procurement_organization":
            _reject("planning reports require actor_role='procurement_organization'")
        if self.observation.organization_id != self.organization_id:
            _reject("observation organization_id does not match its binding")
        violations = verify_observation_invariants(self.observation)
        if violations:
            _reject(f"observation invariant violation: {violations[0]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "commodity_id": self.commodity_id,
            "stage": self.stage,
            "observation": self.observation.to_dict(),
        }


@dataclass(frozen=True)
class PlanningBudgetObservation:
    """A published approver budget bound to a payer channel and currency."""

    organization_id: str
    payer_kind: str
    payer_id: int
    currency: str
    observation: ActorObservation

    def __post_init__(self) -> None:
        _exact_str(self.organization_id, "budget.organization_id")
        if self.payer_kind not in BUDGET_PAYER_KINDS:
            _reject(f"budget.payer_kind must be one of {BUDGET_PAYER_KINDS}")
        _exact_int(self.payer_id, "budget.payer_id")
        _exact_str(self.currency, "budget.currency")
        if type(self.observation) is not ActorObservation:
            _reject("budget observation must be a concrete ActorObservation")
        if self.observation.actor_role != "approver":
            _reject("budget report requires actor_role='approver'")
        violations = verify_observation_invariants(self.observation)
        if violations:
            _reject(f"budget observation invariant violation: {violations[0]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "payer_kind": self.payer_kind,
            "payer_id": self.payer_id,
            "currency": self.currency,
            "observation": self.observation.to_dict(),
        }


def _report_values(observation: ActorObservation) -> dict[str, float]:
    required = (
        "supply_quantity",
        "demand_quantity",
        "administered_price",
        "inventory_level",
        "capacity_utilization",
        "shortage_indicator",
    )
    values: dict[str, float] = {}
    for name in required:
        if not observation.has_field(name):
            _reject(f"observation is missing required field {name!r}")
        raw = observation.get_field(name)
        if type(raw) not in (int, float) or type(raw) is bool:
            _reject(f"observation field {name!r} must be a finite number")
        value = float(raw)
        if not math.isfinite(value) or value < 0.0:
            _reject(f"observation field {name!r} must be finite and non-negative")
        values[name] = value
    return values


def _budget_value(observation: ActorObservation) -> float:
    if not observation.has_field("budget_available"):
        _reject("budget observation is missing budget_available")
    raw = observation.get_field("budget_available")
    if type(raw) not in (int, float) or type(raw) is bool:
        _reject("budget_available must be a finite number")
    value = float(raw)
    if not math.isfinite(value) or value < 0.0:
        _reject("budget_available must be finite and non-negative")
    return value


# ---------------------------------------------------------------------------
# Planning inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanningInputs:
    """The complete immutable input to one four-quarter planning decision."""

    schema_version: str
    decision_at: date
    quarter: str
    horizon_quarters: int
    quarters: tuple[str, ...]
    terminal_mask: tuple[bool, ...]
    source_kind: str
    information_mode: str
    forecast_method: str
    priority: tuple[str, ...]
    priority_hash: str
    declarations: PlanningDeclarations
    observations: tuple[PlanningObservation, ...]
    budget_observations: tuple[PlanningBudgetObservation, ...]
    goods_id: tuple[str, ...]
    goods_is_service: np.ndarray
    organization_ids: tuple[str, ...]
    organization_bank: np.ndarray
    inventory_initial: np.ndarray
    cash_initial: np.ndarray
    prices: np.ndarray
    demand_ordered: np.ndarray
    demand_gross: np.ndarray
    recipe_capacity: np.ndarray
    funding_capacity: np.ndarray
    service_capacity: np.ndarray
    handling_capacity: np.ndarray
    edge_capacity: np.ndarray
    bank_reserves: np.ndarray
    wage: np.ndarray
    organization_funding_group: np.ndarray
    funding_group_capacity: np.ndarray
    organization_currency: tuple[str, ...]
    interest: np.ndarray
    order_financing: np.ndarray
    edge_service_good: np.ndarray
    edge_freight_price: np.ndarray
    recipe_tier: np.ndarray
    organization_service_good: np.ndarray
    baseline_procurement: np.ndarray
    service_split: tuple[float, ...]
    observation_hash: str
    forecast_hash: str
    input_hash: str
    nested_bounded: bool
    nested_reason: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            _reject("unsupported planning input schema")
        _exact_date(self.decision_at, "decision_at")
        _exact_str(self.quarter, "quarter")
        if self.horizon_quarters != HORIZON_QUARTERS:
            _reject("horizon_quarters must be four")
        if self.information_mode not in ("bounded_planning", "full_information_upper_bound"):
            _reject("information_mode is not registered")
        if self.forecast_method != FORECAST_METHOD:
            _reject("forecast_method is not registered")
        if type(self.terminal_mask) is not tuple or len(self.terminal_mask) != HORIZON_QUARTERS:
            _reject("terminal_mask must have four entries")
        if self.priority != PRIORITY:
            _reject("priority order is not the frozen H3E order")
        if type(self.nested_bounded) is not bool:
            _reject("nested_bounded must be exact bool")
        _exact_str(self.nested_reason, "nested_reason")
        org_count = len(self.organization_ids)
        good_count = len(self.goods_id)
        if self.terminal_mask[0] is not True:
            _reject("the decision quarter must be active")
        for _, name, shape in (
            (self.organization_bank, "organization_bank", (org_count,)),
            (self.inventory_initial, "inventory_initial", (org_count, good_count)),
            (self.cash_initial, "cash_initial", (org_count,)),
            (self.prices, "prices", (HORIZON_QUARTERS, good_count)),
            (
                self.demand_ordered,
                "demand_ordered",
                (HORIZON_QUARTERS, int(self.declarations.demand_buyer.shape[0])),
            ),
            (
                self.demand_gross,
                "demand_gross",
                (HORIZON_QUARTERS, int(self.declarations.demand_buyer.shape[0])),
            ),
            (
                self.recipe_capacity,
                "recipe_capacity",
                (HORIZON_QUARTERS, int(self.declarations.recipe_org.shape[0])),
            ),
            (self.funding_capacity, "funding_capacity", (HORIZON_QUARTERS, org_count)),
            (self.service_capacity, "service_capacity", (HORIZON_QUARTERS, org_count)),
            (self.handling_capacity, "handling_capacity", (HORIZON_QUARTERS, org_count)),
            (
                self.edge_capacity,
                "edge_capacity",
                (HORIZON_QUARTERS, int(self.declarations.edge_id.shape[0])),
            ),
            (
                self.bank_reserves,
                "bank_reserves",
                (HORIZON_QUARTERS, int(self.declarations.bank_count)),
            ),
            (self.wage, "wage", (HORIZON_QUARTERS, org_count)),
            (
                self.organization_funding_group,
                "organization_funding_group",
                (org_count,),
            ),
            (
                self.funding_group_capacity,
                "funding_group_capacity",
                (HORIZON_QUARTERS, int(self.organization_funding_group.max()) + 1),
            ),
            (self.interest, "interest", (HORIZON_QUARTERS, org_count)),
            (self.order_financing, "order_financing", (HORIZON_QUARTERS, org_count)),
            (
                self.edge_service_good,
                "edge_service_good",
                (int(self.declarations.edge_id.shape[0]),),
            ),
            (
                self.edge_freight_price,
                "edge_freight_price",
                (int(self.declarations.edge_id.shape[0]),),
            ),
            (
                self.recipe_tier,
                "recipe_tier",
                (int(self.declarations.recipe_org.shape[0]),),
            ),
            (
                self.organization_service_good,
                "organization_service_good",
                (org_count,),
            ),
            (
                self.baseline_procurement,
                "baseline_procurement",
                (HORIZON_QUARTERS, org_count, good_count),
            ),
        ):
            if getattr(self, name).shape != shape:
                _reject(f"{name} shape does not match the planning axes")
            if not bool(np.all(np.isfinite(getattr(self, name)))):
                _reject(f"{name} contains a non-finite value")
            if name in ("edge_service_good", "organization_service_good"):
                if bool(np.any((getattr(self, name) < -1) | (getattr(self, name) >= good_count))):
                    _reject(f"{name} is outside the goods axis")
            elif name != "inventory_initial" and bool(np.any(getattr(self, name) < -ATOL)):
                _reject(f"{name} contains a negative value")
        if not bool(np.all(self.goods_is_service == self.declarations.goods_is_service)):
            _reject("goods_is_service does not match the declarations")
        if (
            type(self.organization_currency) is not tuple
            or len(self.organization_currency) != org_count
        ):
            _reject("organization_currency must align with organizations")
        if any(type(value) is not str or not value for value in self.organization_currency):
            _reject("organization_currency entries must be non-empty strings")
        if type(self.service_split) is not tuple or len(self.service_split) != 3:
            _reject("service_split must have three entries")
        split = tuple(float(value) for value in self.service_split)
        if any(not math.isfinite(value) or value < 0.0 for value in split):
            _reject("service_split must be finite and non-negative")
        if abs(sum(split) - 1.0) > 1e-9:
            _reject("service_split must sum to one")
        for name in (
            "goods_is_service",
            "organization_bank",
            "inventory_initial",
            "cash_initial",
            "prices",
            "demand_ordered",
            "demand_gross",
            "recipe_capacity",
            "funding_capacity",
            "service_capacity",
            "handling_capacity",
            "edge_capacity",
            "bank_reserves",
            "wage",
            "organization_funding_group",
            "funding_group_capacity",
            "interest",
            "order_financing",
            "edge_service_good",
            "edge_freight_price",
            "recipe_tier",
            "organization_service_good",
            "baseline_procurement",
        ):
            array = np.ascontiguousarray(getattr(self, name))
            object.__setattr__(
                self,
                name,
                np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape),
            )

    def digest(self) -> str:
        arrays = {
            "goods_is_service": self.goods_is_service.astype(np.float64),
            "organization_bank": self.organization_bank,
            "inventory_initial": self.inventory_initial,
            "cash_initial": self.cash_initial,
            "prices": self.prices,
            "demand_ordered": self.demand_ordered,
            "demand_gross": self.demand_gross,
            "recipe_capacity": self.recipe_capacity,
            "funding_capacity": self.funding_capacity,
            "service_capacity": self.service_capacity,
            "handling_capacity": self.handling_capacity,
            "edge_capacity": self.edge_capacity,
            "bank_reserves": self.bank_reserves,
            "wage": self.wage,
            "organization_funding_group": self.organization_funding_group,
            "funding_group_capacity": self.funding_group_capacity,
            "interest": self.interest,
            "order_financing": self.order_financing,
            "edge_service_good": self.edge_service_good,
            "edge_freight_price": self.edge_freight_price,
            "recipe_tier": self.recipe_tier,
            "organization_service_good": self.organization_service_good,
            "baseline_procurement": self.baseline_procurement,
        }
        scalars = {
            "schema_version": self.schema_version,
            "decision_at": self.decision_at.isoformat(),
            "quarter": self.quarter,
            "horizon_quarters": self.horizon_quarters,
            "quarters": self.quarters,
            "terminal_mask": self.terminal_mask,
            "source_kind": self.source_kind,
            "information_mode": self.information_mode,
            "forecast_method": self.forecast_method,
            "priority_hash": self.priority_hash,
            "declarations_hash": self.declarations.digest(),
            "organization_currency": self.organization_currency,
            "service_split": self.service_split,
            "observation_hash": self.observation_hash,
            "forecast_hash": self.forecast_hash,
            "nested_bounded": self.nested_bounded,
        }
        return _hash_arrays(arrays, scalars)


def _observation_digest(
    observations: tuple[PlanningObservation, ...],
    budget_observations: tuple[PlanningBudgetObservation, ...],
    quarter: str,
) -> str:
    digest = hashlib.sha256()
    digest.update(quarter.encode("utf-8"))
    for item in sorted(
        observations, key=lambda value: (value.organization_id, value.commodity_id, value.stage)
    ):
        values = _report_values(item.observation)
        digest.update(item.organization_id.encode("utf-8"))
        digest.update(item.commodity_id.encode("utf-8"))
        digest.update(item.stage.encode("utf-8"))
        digest.update(item.observation.available_at.isoformat().encode("ascii"))
        for name in sorted(values):
            digest.update(name.encode("ascii"))
            digest.update(repr(values[name]).encode("ascii"))
    for item in sorted(
        budget_observations,
        key=lambda value: (value.organization_id, value.payer_kind, value.payer_id, value.currency),
    ):
        digest.update(b"budget")
        digest.update(item.organization_id.encode("utf-8"))
        digest.update(item.payer_kind.encode("utf-8"))
        digest.update(str(item.payer_id).encode("ascii"))
        digest.update(item.currency.encode("utf-8"))
        digest.update(item.observation.available_at.isoformat().encode("ascii"))
        digest.update(repr(_budget_value(item.observation)).encode("ascii"))
    return digest.hexdigest()


def observation_digest(
    observations: tuple[PlanningObservation, ...],
    budget_observations: tuple[PlanningBudgetObservation, ...],
    *,
    quarter: str,
) -> str:
    """Public execution-side recomputation of the bound observation hash."""
    if type(observations) is not tuple or type(budget_observations) is not tuple:
        _reject("observations and budget_observations must be tuples")
    return _observation_digest(observations, budget_observations, quarter)


def _quarter_ordinal(label: str) -> int:
    _exact_str(label, "quarter label")
    if len(label) < 6 or label[-2] != "Q" or not label[:-2].isdigit():
        _reject(f"invalid quarter label {label!r}")
    quarter = int(label[-1])
    if quarter < 1 or quarter > 4:
        _reject(f"invalid quarter number in {label!r}")
    return int(label[:-2]) * 4 + quarter - 1


def _date_quarter_ordinal(value: date) -> int:
    return value.year * 4 + (value.month - 1) // 3


def _flatten_future(array: np.ndarray) -> np.ndarray:
    """Copy the first active quarter to every later quarter."""
    frozen = np.asarray(array, dtype=np.float64).copy()
    for offset in range(1, HORIZON_QUARTERS):
        frozen[offset] = frozen[0]
    return frozen


def build_planning_inputs(
    *,
    observations: tuple[PlanningObservation, ...],
    declarations: PlanningDeclarations,
    decision_at: date,
    quarter: str,
    budget_observations: tuple[PlanningBudgetObservation, ...] = (),
    information_mode: Literal[
        "bounded_planning", "full_information_upper_bound"
    ] = "bounded_planning",
) -> PlanningInputs:
    """Validate and freeze one information-bound planning problem.

    Every required report must exist and be published no later than
    ``decision_at``.  A missing quantity is a gate failure, never a zero fill
    and never an automatic switch to full information.
    """
    if type(declarations) is not PlanningDeclarations:
        _reject("declarations must be a concrete PlanningDeclarations")
    _exact_date(decision_at, "decision_at")
    _exact_str(quarter, "quarter")
    if type(observations) is not tuple or any(
        type(item) is not PlanningObservation for item in observations
    ):
        _reject("observations must be a tuple of PlanningObservation")
    if type(budget_observations) is not tuple or any(
        type(item) is not PlanningBudgetObservation for item in budget_observations
    ):
        _reject("budget_observations must be a tuple of PlanningBudgetObservation")
    if information_mode not in ("bounded_planning", "full_information_upper_bound"):
        _reject("information_mode is not registered")
    if declarations.quarters[0] != quarter:
        _reject("quarter does not match the declarations' first quarter")
    if _date_quarter_ordinal(decision_at) != _quarter_ordinal(quarter):
        _reject("decision_at does not fall in the planning quarter")
    ordinals = tuple(_quarter_ordinal(label) for label in declarations.quarters)
    if any(ordinals[index + 1] != ordinals[index] + 1 for index in range(HORIZON_QUARTERS - 1)):
        _reject("declarations.quarters must be consecutive real quarters")
    core_end = 1985 * 4 + 3  # 1985Q4
    if ordinals[0] > core_end:
        _reject("planning decision lies in the reserved validation window")
    for offset, ordinal in enumerate(ordinals):
        if ordinal > core_end and declarations.terminal_mask[offset]:
            _reject("quarters beyond the 1985Q4 historical core must be inactive")

    org_index = {name: index for index, name in enumerate(declarations.organization_ids)}
    good_index = {name: index for index, name in enumerate(declarations.goods_id)}
    org_count = len(declarations.organization_ids)
    good_count = len(declarations.goods_id)

    seen: dict[tuple[str, str, str], tuple[float, ...]] = {}
    observed_inventory = np.zeros((org_count, good_count), dtype=np.float64)
    observed_report: dict[tuple[int, int], dict[str, float]] = {}
    observed_prices: dict[int, float] = {}
    for item in observations:
        if item.organization_id not in org_index:
            _reject(f"observation organization {item.organization_id!r} is not declared")
        goods_key = f"{item.commodity_id}|{item.stage}"
        if goods_key not in good_index:
            _reject(f"observation good {goods_key!r} is not declared")
        if item.observation.quarter != quarter:
            _reject("observation quarter does not match the decision quarter")
        if item.observation.decision_at != decision_at:
            _reject("observation decision_at does not match the planning decision date")
        if item.observation.available_at > decision_at:
            _reject("observation was not available at the decision date")
        values = _report_values(item.observation)
        key = (item.organization_id, item.commodity_id, item.stage)
        packed = tuple(values[name] for name in sorted(values))
        if key in seen:
            if seen[key] != packed:
                _reject(f"conflicting duplicate reports for {key!r}")
            _reject(f"duplicate reports for {key!r}")
        seen[key] = packed
        o = org_index[item.organization_id]
        g = good_index[goods_key]
        observed_inventory[o, g] = values["inventory_level"]
        observed_report[(o, g)] = values
        price = values["administered_price"]
        if g in observed_prices and observed_prices[g] != price:
            _reject(f"conflicting published prices for good {declarations.goods_id[g]!r}")
        observed_prices[g] = price

    required = set(declarations.required_reports)
    for edge in range(int(declarations.edge_id.shape[0])):
        good_id = declarations.goods_id[int(declarations.edge_good[edge])]
        required.add((declarations.organization_ids[int(declarations.edge_seller[edge])], good_id))
        required.add((declarations.organization_ids[int(declarations.edge_buyer[edge])], good_id))
        carrier = int(declarations.edge_transport_org[edge])
        service_good = int(declarations.edge_service_good[edge])
        if carrier >= 0 and service_good >= 0:
            required.add(
                (
                    declarations.organization_ids[carrier],
                    declarations.goods_id[service_good],
                )
            )
    for demand in range(int(declarations.demand_buyer.shape[0])):
        good = int(declarations.demand_good[demand])
        required.add(
            (
                declarations.organization_ids[int(declarations.demand_buyer[demand])],
                declarations.goods_id[good],
            )
        )
    for recipe in range(int(declarations.recipe_org.shape[0])):
        good = int(declarations.recipe_output_good[recipe])
        required.add(
            (
                declarations.organization_ids[int(declarations.recipe_org[recipe])],
                declarations.goods_id[good],
            )
        )
        start = int(declarations.recipe_input_ptr[recipe])
        end = int(declarations.recipe_input_ptr[recipe + 1])
        for position in range(start, end):
            input_good = int(declarations.recipe_input_good[position])
            required.add(
                (
                    declarations.organization_ids[int(declarations.recipe_org[recipe])],
                    declarations.goods_id[input_good],
                )
            )
    for org in range(org_count):
        for good in range(good_count):
            capacity = 0.0
            for recipe in range(int(declarations.recipe_org.shape[0])):
                if (
                    int(declarations.recipe_org[recipe]) == org
                    and int(declarations.recipe_output_good[recipe]) == good
                ):
                    capacity += float(declarations.recipe_capacity[0, recipe])
            if float(declarations.inventory_opening[org, good]) > ATOL or capacity > ATOL:
                required.add((declarations.organization_ids[org], declarations.goods_id[good]))
    for org_id, good_id in sorted(required):
        commodity_id, stage = good_id.split("|", 1)
        key = (org_id, commodity_id, stage)
        if key not in seen:
            _reject(f"required report is missing for {key!r}")

    funding_group_reports: dict[int, float] = {}
    bank_reports: dict[int, float] = {}
    budget_seen: set[tuple[int, str, int, str]] = set()
    for item in budget_observations:
        if item.organization_id not in org_index:
            _reject("budget target organization is not declared")
        o = org_index[item.organization_id]
        if item.currency != declarations.currency:
            _reject("budget currency does not match the declared currency")
        if item.currency != declarations.organization_currency[o]:
            _reject("budget currency does not match the organization currency")
        if item.observation.quarter != quarter:
            _reject("budget observation quarter does not match the decision quarter")
        if item.observation.decision_at != decision_at:
            _reject("budget observation decision_at does not match the decision date")
        if item.observation.available_at > decision_at:
            _reject("budget observation was not available at the decision date")
        key = (o, item.payer_kind, item.payer_id, item.currency)
        if key in budget_seen:
            _reject("duplicate budget report for one payer channel")
        budget_seen.add(key)
        value = _budget_value(item.observation)
        if item.payer_kind == "funding_group":
            group = int(declarations.organization_funding_group[o])
            if item.payer_id != group:
                _reject("funding-group report does not name the organization's group")
            if group in funding_group_reports and funding_group_reports[group] != value:
                _reject("conflicting funding-group reports")
            funding_group_reports[group] = value
        else:
            if item.payer_id >= int(declarations.bank_count):
                _reject("bank-prepayment report names an unknown bank")
            if item.payer_id in bank_reports and bank_reports[item.payer_id] != value:
                _reject("conflicting bank-prepayment reports")
            bank_reports[item.payer_id] = value

    buyer_orgs = set(int(v) for v in declarations.edge_buyer)
    buyer_orgs |= set(int(v) for v in declarations.demand_buyer)
    buyer_orgs |= set(int(v) for v in declarations.recipe_org)
    required_groups = {int(declarations.organization_funding_group[o]) for o in buyer_orgs}
    for group in sorted(required_groups):
        if group not in funding_group_reports:
            _reject(f"required funding-group report is missing for group {group}")
    cross_bank = (
        declarations.organization_bank[declarations.edge_buyer]
        != declarations.organization_bank[declarations.edge_seller]
    )
    required_banks = set(
        int(value) for value in declarations.organization_bank[declarations.edge_buyer][cross_bank]
    )
    freight_cross = (declarations.edge_transport_org >= 0) & (
        declarations.organization_bank[declarations.edge_buyer]
        != declarations.organization_bank[np.maximum(declarations.edge_transport_org, 0)]
    )
    required_banks |= set(
        int(value)
        for value in declarations.organization_bank[declarations.edge_buyer][freight_cross]
    )
    for bank in sorted(required_banks):
        if bank not in bank_reports:
            _reject(f"required bank-prepayment report is missing for bank {bank}")

    group_capacity = np.zeros(
        (HORIZON_QUARTERS, int(declarations.funding_group_capacity.shape[1])),
        dtype=np.float64,
    )
    bank_reserves_effective = np.zeros(
        (HORIZON_QUARTERS, int(declarations.bank_count)), dtype=np.float64
    )
    if information_mode == "bounded_planning":
        # Bounded actors start from published reports only.  Unreported
        # balances are not silently filled from the true synthetic ledger.
        inventory_initial = np.zeros((org_count, good_count), dtype=np.float64)
        cash_initial = np.array(declarations.organization_cash_opening, dtype=np.float64, copy=True)
        for (o, g), values in observed_report.items():
            inventory_initial[o, g] = values["inventory_level"]
        for group, value in funding_group_reports.items():
            group_capacity[:, group] = value
        for bank, value in bank_reports.items():
            bank_reserves_effective[:, bank] = value
    else:
        inventory_initial = np.array(declarations.inventory_opening, dtype=np.float64, copy=True)
        cash_initial = np.array(declarations.organization_cash_opening, dtype=np.float64, copy=True)
        group_capacity = np.array(declarations.funding_group_capacity, dtype=np.float64, copy=True)
        bank_reserves_effective = np.array(declarations.bank_reserves, dtype=np.float64, copy=True)

    prices = np.array(declarations.prices, dtype=np.float64, copy=True)
    demand_ordered = np.array(declarations.demand_ordered, dtype=np.float64, copy=True)
    demand_gross = np.array(declarations.demand_gross, dtype=np.float64, copy=True)
    recipe_capacity = np.array(declarations.recipe_capacity, dtype=np.float64, copy=True)

    # Current-quarter observations override the declarations; later quarters
    # are explicit constant forecasts, never future forcing values.
    for good, price in observed_prices.items():
        prices[0, good] = price
    for (o, g), values in observed_report.items():
        demand_total = float(
            np.sum(
                declarations.demand_ordered[
                    0, (declarations.demand_buyer == o) & (declarations.demand_good == g)
                ]
            )
        )
        mask = (declarations.demand_buyer == o) & (declarations.demand_good == g)
        if bool(np.any(mask)):
            if demand_total > ATOL:
                demand_ordered[0, mask] = (
                    declarations.demand_ordered[0, mask] / demand_total * values["demand_quantity"]
                )
            else:
                first = int(np.flatnonzero(mask)[0])
                demand_ordered[0, first] = values["demand_quantity"]
            demand_gross[0, mask] = np.maximum(demand_gross[0, mask], demand_ordered[0, mask])
        recipe_mask = (declarations.recipe_output_good == g) & (declarations.recipe_org == o)
        if bool(np.any(recipe_mask)):
            supply = values["supply_quantity"] * values["capacity_utilization"]
            recipe_capacity[0, recipe_mask] = np.minimum(
                declarations.recipe_capacity[0, recipe_mask], supply
            )
    funding_capacity = np.zeros((HORIZON_QUARTERS, org_count), dtype=np.float64)
    for org in range(org_count):
        group = int(declarations.organization_funding_group[org])
        funding_capacity[:, org] = group_capacity[:, group]
    order_financing = np.array(
        declarations.organization_order_financing, dtype=np.float64, copy=True
    )
    for org in range(org_count):
        group = int(declarations.organization_funding_group[org])
        order_financing[:, org] = np.minimum(order_financing[:, org], group_capacity[:, group])

    prices = _flatten_future(prices)
    demand_ordered = _flatten_future(demand_ordered)
    demand_gross = _flatten_future(demand_gross)
    recipe_capacity = _flatten_future(recipe_capacity)
    funding_capacity = _flatten_future(funding_capacity)
    group_capacity = _flatten_future(group_capacity)
    order_financing = _flatten_future(order_financing)
    interest = _flatten_future(declarations.organization_interest)
    baseline_procurement = _flatten_future(declarations.baseline_procurement)
    service_capacity = _flatten_future(declarations.service_capacity)
    handling_capacity = _flatten_future(declarations.handling_capacity)
    edge_capacity = _flatten_future(declarations.edge_capacity)
    bank_reserves = _flatten_future(bank_reserves_effective)
    wage = _flatten_future(declarations.wage)

    observation_hash = _observation_digest(observations, budget_observations, quarter)
    priority_hash = hashlib.sha256(repr(PRIORITY).encode("utf-8")).hexdigest()
    forecast_hash = _hash_arrays(
        {
            "prices": prices,
            "demand_ordered": demand_ordered,
            "demand_gross": demand_gross,
            "recipe_capacity": recipe_capacity,
            "funding_capacity": funding_capacity,
            "service_capacity": service_capacity,
            "handling_capacity": handling_capacity,
            "edge_capacity": edge_capacity,
            "bank_reserves": bank_reserves,
            "wage": wage,
            "funding_group_capacity": group_capacity,
            "interest": interest,
            "order_financing": order_financing,
            "baseline_procurement": baseline_procurement,
        },
        {"forecast_method": FORECAST_METHOD, "quarters": declarations.quarters},
    )

    nested = True
    nested_reason = "bounded arm: nesting is assessed by the full-information arm"
    if information_mode == "full_information_upper_bound":
        reasons: list[str] = []
        for (o, g), values in observed_report.items():
            if values["inventory_level"] > float(declarations.inventory_opening[o, g]) + ATOL:
                reasons.append(
                    f"reported inventory exceeds true inventory for "
                    f"{declarations.organization_ids[o]}/{declarations.goods_id[g]}"
                )
        for group, value in funding_group_reports.items():
            true_value = float(declarations.funding_group_capacity[0, group])
            if value > true_value + ATOL:
                reasons.append(f"approved funding group {group} exceeds the true envelope")
        for bank, value in bank_reports.items():
            true_value = float(declarations.bank_reserves[0, bank])
            if value > true_value + ATOL:
                reasons.append(f"reported bank reserve {bank} exceeds the true reserve")
        if reasons:
            nested = False
            nested_reason = "NOT_COMPARABLE: " + "; ".join(reasons)
        else:
            nested_reason = (
                "bounded observations dominate no more resource than the "
                "full-information current state"
            )

    # A bounded planner must not be able to read the true opening inventory or
    # cash out of the declarations container.  The full-information arm keeps
    # them because that is its registered extra information.
    effective_declarations = declarations
    if information_mode == "bounded_planning":
        effective_declarations = replace(
            declarations,
            inventory_opening=np.array(inventory_initial, dtype=np.float64, copy=True),
            organization_cash_opening=np.array(cash_initial, dtype=np.float64, copy=True),
            funding_group_capacity=np.array(group_capacity, dtype=np.float64, copy=True),
            bank_reserves=np.array(bank_reserves, dtype=np.float64, copy=True),
        )
    inputs = PlanningInputs(
        schema_version=SCHEMA_VERSION,
        decision_at=decision_at,
        quarter=quarter,
        horizon_quarters=HORIZON_QUARTERS,
        quarters=declarations.quarters,
        terminal_mask=declarations.terminal_mask,
        source_kind=declarations.source_kind,
        information_mode=information_mode,
        forecast_method=FORECAST_METHOD,
        priority=PRIORITY,
        priority_hash=priority_hash,
        declarations=effective_declarations,
        observations=observations,
        budget_observations=budget_observations,
        goods_id=declarations.goods_id,
        goods_is_service=np.array(declarations.goods_is_service, dtype=bool, copy=True),
        organization_ids=declarations.organization_ids,
        organization_bank=np.array(declarations.organization_bank, dtype=np.int64, copy=True),
        inventory_initial=inventory_initial,
        cash_initial=cash_initial,
        prices=prices,
        demand_ordered=demand_ordered,
        demand_gross=demand_gross,
        recipe_capacity=recipe_capacity,
        funding_capacity=funding_capacity,
        service_capacity=service_capacity,
        handling_capacity=handling_capacity,
        edge_capacity=edge_capacity,
        bank_reserves=bank_reserves,
        wage=wage,
        organization_funding_group=np.array(
            declarations.organization_funding_group, dtype=np.int64, copy=True
        ),
        funding_group_capacity=group_capacity,
        organization_currency=declarations.organization_currency,
        interest=interest,
        order_financing=order_financing,
        edge_service_good=np.array(declarations.edge_service_good, dtype=np.int64, copy=True),
        edge_freight_price=np.array(declarations.edge_freight_price, dtype=np.float64, copy=True),
        recipe_tier=np.array(declarations.recipe_tier, dtype=np.int64, copy=True),
        organization_service_good=np.array(
            declarations.organization_service_good, dtype=np.int64, copy=True
        ),
        baseline_procurement=baseline_procurement,
        service_split=declarations.service_split,
        observation_hash=observation_hash,
        forecast_hash=forecast_hash,
        input_hash="",
        nested_bounded=nested,
        nested_reason=nested_reason,
    )
    object.__setattr__(inputs, "input_hash", inputs.digest())
    for name in (
        "goods_is_service",
        "organization_bank",
        "inventory_initial",
        "cash_initial",
        "prices",
        "demand_ordered",
        "demand_gross",
        "recipe_capacity",
        "funding_capacity",
        "service_capacity",
        "handling_capacity",
        "edge_capacity",
        "bank_reserves",
        "wage",
        "organization_funding_group",
        "funding_group_capacity",
        "interest",
        "order_financing",
        "edge_service_good",
        "baseline_procurement",
    ):
        getattr(inputs, name).setflags(write=False)
    return inputs


__all__ = [
    "ARMS",
    "BUDGET_PAYER_KINDS",
    "FORECAST_METHOD",
    "HORIZON_QUARTERS",
    "PRIORITY",
    "PlanningBudgetObservation",
    "PlanningDeclarations",
    "PlanningInputs",
    "PlanningObservation",
    "SCHEMA_VERSION",
    "SOURCE_KIND",
    "build_planning_inputs",
    "observation_digest",
]
