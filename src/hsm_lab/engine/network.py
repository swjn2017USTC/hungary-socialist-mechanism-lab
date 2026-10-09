"""Material network compiler (P02 plan step 2).

Compiles, exactly once and before any tick runs:

* the canonical stock-cell catalog ``(owner_kind, owner_id, region, pool,
  commodity index, stage)`` — the single authority behind ``stock_value[S]``;
* the sparse activity matrices ``A`` (inputs, CSR over ``K`` required input
  rows) and ``B`` (outputs into stock cells), with ``P =`` productive
  organizations + ``R`` private-plot activities (plots last);
* the demand-cell axis ``D`` (order intents) and the canonical route edge
  table ``M`` (default nearest graph, an explicit ``MaterialRouteSpec`` list,
  or genuinely no routes).

Everything here is a pure function of its arguments: the readonly
``MaterialInitialConditions`` is never mutated, no per-tick work happens in
this module, and building twice yields byte-identical arrays.  Banks never
receive material cells; exports and household acquisition are boundary sink
demands (``destination cell = -1``) so no export stock cell exists.

Interpretation notes (not pinned field-by-field by the interfaces file):

* plot output pools — ``raw_market`` sits in pool ``output`` (sold via formal
  procurement), ``ready_self`` in pool ``input`` (reserved for own use) and
  ``ready_market`` in pool ``retail`` (direct household market); the three
  keys therefore never collide in the catalog;
* plot self-use and the plot direct market are kernel channels over the
  pinned ``plot_ready_self_cell``/``plot_ready_market_cell`` maps, not route
  edges (household acquisition never pays transport);
* the treasury import buffer joins the nearest-hub collection for every
  hub-sold importable commodity (energy/food-ready/consumer/durable), and is
  additionally the declared second source of every importable production,
  plot-input and capital-investment demand;
* hub collection intents group their partitioned suppliers in consecutive
  canonical pairs so no demand cell ever exceeds two suppliers while every
  farm still keeps a buyer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.sparse import csr_matrix  # type: ignore[import-untyped]

if TYPE_CHECKING:  # pragma: no cover - annotation-only; avoids an import cycle
    from hsm_lab.contract.households import HouseholdCatalog, HouseholdParameters

from hsm_lab.contract.base import ConfigError, ResearchGateError
from hsm_lab.contract.material import (
    P02_COMMODITY_IDS,
    PRODUCTIVE_TYPES,
    PURPOSE_CODES,
    STAGE_CODES,
    CellOwnerKind,
    CommoditySpec,
    InputCoefficient,
    MaterialInitialConditions,
    MaterialRouteSpec,
    OrganizationType,
    OutputCoefficient,
    PrivatePlotRecipe,
    RoutePurpose,
    Stage,
    StockCellRef,
    TechnologySpec,
    catalog_for_commodities,
    commodity_spec,
    get_catalog,
    wholesale_hub_regions,
)
from hsm_lab.contract.schemas import ResearchContract, ScenarioSpec
from hsm_lab.engine.state import POOL_CODES, owner_kind_code

MATERIAL_NETWORK_VERSION = "material-network-v4"

_POOL_INPUT = POOL_CODES["input"]
_POOL_OUTPUT = POOL_CODES["output"]
_POOL_WHOLESALE = POOL_CODES["wholesale"]
_POOL_RETAIL = POOL_CODES["retail"]
_POOL_WIP = POOL_CODES["wip"]
_POOL_IMPORT = POOL_CODES["import_pool"]

_POOL_NAMES = {code: name for name, code in POOL_CODES.items()}
_STAGE_NAMES = {code: name for name, code in STAGE_CODES.items()}
_KIND_NAMES = {owner_kind_code(kind): kind.value for kind in CellOwnerKind}

# The wholesale-hub, retail and investment commodity sets are derived from the
# commodity registry in ``contract.material`` (see HUB_COMMODITY_STAGES,
# RETAIL_COMMODITY_STAGES, INVESTMENT_COMMODITY_IDS); a new commodity joins the
# distribution or investment layer by declaring the flag, not by editing engine code.
# Exports ship from the sources nearest the national origin (region 0).
EXPORT_ORIGIN_REGION = 0

_BORDER_PURPOSES: frozenset[RoutePurpose] = frozenset(
    {
        RoutePurpose.HOUSING,
        RoutePurpose.EXPORT_CMEA,
        RoutePurpose.EXPORT_CONVERTIBLE,
        RoutePurpose.HOUSEHOLD,
    }
)
_ROUTEABLE_PURPOSES: frozenset[RoutePurpose] = frozenset(
    {
        RoutePurpose.INTERMEDIATE,
        RoutePurpose.PRIVATE_PLOT,
        RoutePurpose.PROCUREMENT,
        RoutePurpose.RETAIL,
        RoutePurpose.INVESTMENT,
    }
)
_SELLING_POOLS = frozenset({_POOL_OUTPUT, _POOL_WHOLESALE, _POOL_RETAIL, _POOL_IMPORT})
_ATOL = 1e-9


@dataclass(frozen=True)
class MaterialNetwork:
    """Pinned compiled network surface (see ``.omp/p02_interfaces.md``)."""

    schema_version: str
    catalog_id: str  # frozen material ontology id (P05 §A)
    region_ids: tuple[str, ...]
    commodity_ids: tuple[str, ...]
    region_distance: np.ndarray  # float64 (R, R) declared spatial proxy
    household_parameters: HouseholdParameters
    household_catalog: HouseholdCatalog
    second_input_commodities: tuple[int, ...]  # commodity axis indices used as inputs
    second_output_commodities: tuple[int, ...]  # commodity axis indices produced
    # per parent commodity: the region retail cell index for this commodity (-1 none)
    retail_cell_by_commodity: np.ndarray  # int32 (R, G)
    # stock-cell catalog (S,) ordered by (owner_kind, owner_id, region, pool,
    # commodity index, stage)
    cell_owner_kind: np.ndarray  # int8 (S,)
    cell_owner_id: np.ndarray  # int64 (S,)
    cell_region: np.ndarray  # int32 (S,)
    cell_pool: np.ndarray  # int8 (S,)
    cell_commodity: np.ndarray  # int16 (S,)
    cell_stage: np.ndarray  # int8 (S,)
    # (kind, id, region, pool, commodity_id, stage) -> row
    cell_index: dict[tuple[str, int, int, str, str, str], int]
    # activities P = productive organizations + R plot activities (plots last)
    activity_kind: np.ndarray  # int8 (P,)
    activity_org_index: np.ndarray  # int32 (P,)
    activity_region: np.ndarray  # int32 (P,)
    activity_capacity: np.ndarray  # float64 (P,)
    activity_early_service: np.ndarray  # bool (P,) same-quarter service producer
    early_service_tiers: list[np.ndarray]  # topological tiers of early producers
    A: csr_matrix  # (P, K) inputs, positive entries only
    input_cell: np.ndarray  # int32 (K,)
    input_activity: np.ndarray  # int32 (K,)
    input_timing: np.ndarray  # int8 (K,) 0 opening / 1 same-quarter service
    B: csr_matrix  # (P, S) outputs into the owner's stock cells
    # demand cells D = K production inputs + trader/plot/investment/housing/
    # export/household intents
    demand_cell: np.ndarray  # int32 (D,)
    demand_purpose: np.ndarray  # int8 (D,)
    demand_activity: np.ndarray  # int32 (D,)
    demand_input_index: np.ndarray  # int32 (D,)
    # (D,) static share of the owning need: production/trader/household cells are
    # 1.0; a hub's collection intents each carry their group-capacity share so
    # the intents of one hub cell sum to exactly one hub need (never over-order).
    demand_share: np.ndarray  # float64 (D,)
    # routes (M,) in canonical edge_id order
    edge_source_cell: np.ndarray  # int32 (M,)
    edge_destination_cell: np.ndarray  # int32 (M,)
    edge_demand: np.ndarray  # int32 (M,)
    edge_commodity: np.ndarray  # int16 (M,)
    edge_stage: np.ndarray  # int8 (M,)
    edge_purpose: np.ndarray  # int8 (M,)
    edge_weight: np.ndarray  # float64 (M,)
    edge_transport_org: np.ndarray  # int32 (M,)
    edge_transport_per_unit: np.ndarray  # float64 (M,)
    edge_buyer_org: np.ndarray  # int32 (M,)
    edge_self_hauled: np.ndarray  # bool (M,) transported by the buyer's own fleet
    edge_is_fallback: np.ndarray  # bool (M,) draws only when declared sources are short
    edge_transport_service_cell: np.ndarray  # int32 (M,) carrier output service cell or -1
    edge_distance: np.ndarray  # float64 (M,) declared route distance
    edge_id: np.ndarray  # int64 (M,)
    # convenience maps
    org_input_cells: dict[int, list[int]]
    org_output_cell: np.ndarray  # int32 (O,)
    org_wholesale_cell: np.ndarray  # int32 (O,)
    plot_input_cells: np.ndarray  # int32 (R, 3) energy/raw/capital columns
    plot_raw_cell: np.ndarray  # int32 (R,)
    plot_ready_self_cell: np.ndarray  # int32 (R,)
    plot_ready_market_cell: np.ndarray  # int32 (R,)
    retail_cell: np.ndarray  # int32 (R, G)
    import_pool_cell: np.ndarray  # int32 (G,)
    project_capital_cell: np.ndarray  # int32 (O,)
    project_construction_cell: np.ndarray  # int32 (O,)
    export_demand_cell: np.ndarray  # int32 (2, G) cmea/convertible rows


def _cyclic_distance(a: int, b: int, period: int) -> int:
    """Ring distance between two region indices."""
    if period <= 1:
        return 0
    delta = abs(a - b) % period
    return min(delta, period - delta)


class _Compiler:
    """One-shot deterministic network builder (never reused)."""

    def __init__(
        self,
        initial: MaterialInitialConditions,
        technologies: Sequence[TechnologySpec],
        routes: Sequence[MaterialRouteSpec] | None,
        commodities: Sequence[CommoditySpec],
        region_ids: Sequence[str],
        plot_recipe: PrivatePlotRecipe,
        region_distance: np.ndarray | None = None,
    ) -> None:
        self.initial = initial
        self.technologies: tuple[TechnologySpec, ...] = tuple(technologies)
        self.routes = routes
        self.commodities: tuple[CommoditySpec, ...] = tuple(commodities)
        self.region_ids: tuple[str, ...] = tuple(region_ids)
        self.plot_recipe = plot_recipe
        self.region_distance_input = region_distance

    # ------------------------------------------------------------------
    # step 1: input coherence and organization tables
    # ------------------------------------------------------------------

    def _validate_inputs(self) -> None:
        self.region_count = len(self.region_ids)
        self.commodity_count = len(self.commodities)
        if self.region_count == 0 or self.commodity_count == 0:
            raise ConfigError("network needs at least one region and one commodity")
        if len(set(self.region_ids)) != self.region_count:
            raise ConfigError("region ids must be unique")
        commodity_ids = tuple(spec.id for spec in self.commodities)
        if len(set(commodity_ids)) != self.commodity_count:
            raise ConfigError("commodity ids must be unique")
        if commodity_ids != tuple(self.initial.commodity_ids):
            raise ConfigError("declared commodities do not match the initial conditions axis")
        if self.region_ids != tuple(self.initial.region_ids):
            raise ConfigError("declared region ids do not match the initial conditions axis")
        self.commodity_ids = commodity_ids
        self.commodity_index = {cid: index for index, cid in enumerate(commodity_ids)}
        self.catalog_id = catalog_for_commodities(commodity_ids).catalog_id
        self.material_catalog = get_catalog(self.catalog_id)
        self.catalog_index = dict(self.material_catalog.index)
        self.commodity_stockable = np.asarray(
            [bool(spec.stockable) for spec in self.commodities], dtype=bool
        )
        self.region_index = {rid: index for index, rid in enumerate(self.region_ids)}
        self._init_region_distance()

        self.tech_index: dict[str, int] = {}
        for row, technology in enumerate(self.technologies):
            if technology.technology_id in self.tech_index:
                raise ConfigError(f"duplicate technology id {technology.technology_id!r}")
            self.tech_index[technology.technology_id] = row
            coefficients: tuple[InputCoefficient | OutputCoefficient, ...] = (
                *technology.inputs,
                *technology.outputs,
            )
            for coefficient_row in coefficients:
                if coefficient_row.commodity_id not in self.commodity_index:
                    raise ConfigError(
                        f"technology {technology.technology_id} references unknown "
                        f"commodity {coefficient_row.commodity_id}"
                    )

        raw_share = self.plot_recipe.output_raw_share
        self_share = self.plot_recipe.self_use_fraction
        market_share = self.plot_recipe.direct_market_fraction
        if abs(raw_share + self_share + market_share - 1.0) > 1e-12:
            raise ConfigError(
                "plot recipe output shares must sum to 1 "
                f"(raw {raw_share} + self {self_share} + market {market_share})"
            )

        trade = self.initial.parameters.trade
        cmea_imports = np.asarray(trade.cmea_desired_imports, dtype=np.float64)
        convertible_imports = np.asarray(trade.convertible_desired_imports, dtype=np.float64)
        cmea_exports = np.asarray(trade.cmea_export_demands, dtype=np.float64)
        convertible_exports = np.asarray(trade.convertible_export_demands, dtype=np.float64)
        self.import_cap = np.zeros(self.commodity_count, dtype=np.float64)
        self.export_demand = np.zeros((2, self.commodity_count), dtype=np.float64)
        for g, spec in enumerate(self.commodities):
            axis = self.catalog_index.get(spec.id)
            if axis is None:
                continue  # extra declared commodity: never importable/exportable
            self.import_cap[g] = cmea_imports[axis] + convertible_imports[axis]
            self.export_demand[0, g] = cmea_exports[axis]
            self.export_demand[1, g] = convertible_exports[axis]
        self.importable = self.import_cap > 0.0
        self.default_transport_per_unit = float(self.initial.parameters.transport_per_unit)

        household_parameters = self.initial.household_parameters
        if household_parameters is None or self.initial.household_catalog is None:
            raise ConfigError(
                "material initial conditions must carry household_parameters and "
                "household_catalog for P03"
            )
        recipe = household_parameters.second_economy
        second_inputs: list[int] = []
        second_outputs: list[int] = []
        for axis_index, commodity_id in enumerate(P02_COMMODITY_IDS):
            net_index = self.commodity_index.get(commodity_id)
            if net_index is None:
                continue
            if recipe.input_coefficients[axis_index] > 0.0:
                second_inputs.append(net_index)
            if recipe.output_coefficients[axis_index] > 0.0:
                second_outputs.append(net_index)
        self.second_input_commodities = tuple(sorted(second_inputs))
        self.second_output_commodities = tuple(sorted(second_outputs))

    def _role_g(self, role: str) -> int | None:
        """Network commodity index of the first channel in a catalog role."""
        for commodity_id in self.material_catalog.with_role(role):
            if commodity_id in self.commodity_index:
                return self.commodity_index[commodity_id]
        return None

    def _init_region_distance(self) -> None:
        """Explicit spatial proxy (P05 §A.7): never an ordinal ring by default."""
        count = self.region_count
        supplied = self.region_distance_input
        self.explicit_distance = supplied is not None
        if supplied is None:
            # Declared S proxy: identity inside a region, unit cost across
            # regions. The legacy ring ordering is only used to break source
            # ranking ties deterministically, not as a distance claim.
            distance = np.ones((count, count), dtype=np.float64)
            np.fill_diagonal(distance, 0.0)
        else:
            distance = np.asarray(supplied, dtype=np.float64)
            if distance.shape != (count, count):
                raise ConfigError(
                    f"region distance matrix must be ({count}, {count}), got {distance.shape}"
                )
            if not np.all(np.isfinite(distance)):
                raise ConfigError("region distance matrix must be finite")
            if bool(np.any(distance < 0.0)):
                raise ConfigError("region distance matrix must be non-negative")
        self.region_distance = distance

    def _init_carrier_capacity(self) -> None:
        self.transport_capacity = np.asarray(
            [
                float(self.initial.organizations[row].capacity)
                for row in self.transport_rows
            ],
            dtype=np.float64,
        )

    def _region_distance_of(self, a: int, b: int) -> float:
        if a < 0 or b < 0:
            return float(np.max(self.region_distance)) if self.region_count else 1.0
        return float(self.region_distance[a, b])

    def _select_carrier(
        self, source_region: int, destination_region: int, reference_work: float
    ) -> int:
        """Pick a carrier by route distance, then assigned load ratio, then id."""
        if not self.transport_rows:
            return -1
        base = source_region if source_region >= 0 else destination_region
        if base < 0:
            base = 0
        carrier_region = np.asarray(
            [self.org_region[row] for row in self.transport_rows], dtype=np.int64
        )
        route_distance = self.region_distance[base, carrier_region]
        safe_capacity = np.where(self.transport_capacity > 0.0, self.transport_capacity, 1.0)
        load_ratio = self.transport_assigned / safe_capacity
        best = min(
            range(len(self.transport_rows)),
            key=lambda index: (
                float(route_distance[index]),
                float(load_ratio[index]),
                int(self.transport_rows[index]),
            ),
        )
        self.transport_assigned[best] += max(float(reference_work), 0.0)
        return int(self.transport_rows[best])

    def _build_org_tables(self) -> None:
        organizations = tuple(
            sorted(self.initial.organizations, key=lambda org: org.organization_id)
        )
        ids = [org.organization_id for org in organizations]
        if ids != list(range(len(ids))):
            raise ConfigError("organization ids must form the canonical 0..O-1 sequence")
        self.organizations = organizations
        self.org_count = len(organizations)
        self.org_type: list[OrganizationType] = []
        self.org_region: list[int] = []
        self.org_tech_row: list[int] = []
        self.productive_rows: list[int] = []
        self.wholesale_rows: list[int] = []
        self.retail_rows: list[int] = []
        self.transport_rows: list[int] = []
        for row, org in enumerate(organizations):
            region = self.region_index.get(org.region_id)
            if region is None:
                raise ConfigError(
                    f"organization {org.organization_id} references unknown region "
                    f"{org.region_id!r}"
                )
            tech_row = -1
            if org.technology_id is not None:
                tech_row = self.tech_index.get(org.technology_id, -1)
                if tech_row < 0:
                    raise ConfigError(
                        f"organization {org.organization_id} references unknown "
                        f"technology {org.technology_id!r}"
                    )
            if org.type in PRODUCTIVE_TYPES and tech_row < 0:
                raise ConfigError(
                    f"productive organization {org.organization_id} lacks a technology"
                )
            self.org_type.append(org.type)
            self.org_region.append(region)
            self.org_tech_row.append(tech_row)
            if org.type in PRODUCTIVE_TYPES:
                self.productive_rows.append(row)
                if org.type is OrganizationType.TRANSPORT:
                    self.transport_rows.append(row)
            elif org.type is OrganizationType.WHOLESALE_PROCURMENT:
                self.wholesale_rows.append(row)
            elif org.type is OrganizationType.RETAIL:
                self.retail_rows.append(row)

        # Wholesale hubs live at the pinned hub regions (not at org_id % 20).
        hub_count = len(self.wholesale_rows)
        pinned = wholesale_hub_regions(hub_count) if hub_count else ()
        self.hub_regions = [int(region % self.region_count) for region in pinned]

        # Retail service regions: position block [p*R//n, ceil((p+1)*R/n)).
        retail_count = len(self.retail_rows)
        self.retail_served: list[list[int]] = []
        self.region_retail_positions: list[list[int]] = [[] for _ in range(self.region_count)]
        for position in range(retail_count):
            start = position * self.region_count // retail_count
            end = -(-(position + 1) * self.region_count // retail_count)
            served = list(range(start, min(end, self.region_count)))
            self.retail_served.append(served)
            for region in served:
                self.region_retail_positions[region].append(position)

        self.plot_activity_base = len(self.productive_rows)
        self.transport_assigned = np.zeros(len(self.transport_rows), dtype=np.float64)
        self.transport_capacity = np.zeros(len(self.transport_rows), dtype=np.float64)
        self._init_carrier_capacity()

    # ------------------------------------------------------------------
    # step 2: stock-cell catalog
    # ------------------------------------------------------------------

    def _add_cell(self, kind: int, owner: int, region: int, pool: int, g: int, stage: int) -> int:
        self.cell_kind.append(kind)
        self.cell_owner.append(owner)
        self.cell_region_list.append(region)
        self.cell_pool.append(pool)
        self.cell_commodity_list.append(g)
        self.cell_stage.append(stage)
        return len(self.cell_kind) - 1

    def _stage_of(self, stage: str) -> int:
        return STAGE_CODES[stage]

    def _build_cells(self) -> None:
        self.cell_kind: list[int] = []
        self.cell_owner: list[int] = []
        self.cell_region_list: list[int] = []
        self.cell_pool: list[int] = []
        self.cell_commodity_list: list[int] = []
        self.cell_stage: list[int] = []

        self.k_activity: list[int] = []
        self.k_cell: list[int] = []
        self.k_coefficient: list[float] = []
        self.k_timing: list[int] = []
        self.b_activity: list[int] = []
        self.b_cell: list[int] = []
        self.b_coefficient: list[float] = []

        self.input_cell_of_org: dict[tuple[int, int, int], int] = {}
        self.org_output_records: list[tuple[int, int, int, int]] = []  # org,g,s,prov
        self.hub_cell_records: list[tuple[int, int, int, int]] = []  # pos,g,s,prov
        self.retail_cell_records: list[tuple[int, int, int, int, int]] = []
        self.project_cell_of: dict[tuple[int, int], int] = {}

        kind_org = owner_kind_code(CellOwnerKind.ORGANIZATION)
        kind_plot = owner_kind_code(CellOwnerKind.PLOT)
        kind_project = owner_kind_code(CellOwnerKind.PROJECT)
        kind_treasury = owner_kind_code(CellOwnerKind.TREASURY_IMPORT)

        org_activity = 0
        for row, org in enumerate(self.organizations):
            org_kind = self.org_type[row]
            if org_kind is OrganizationType.BANK:
                continue  # banks never hold material cells
            region = self.org_region[row]
            if org_kind is OrganizationType.WHOLESALE_PROCURMENT:
                position = self.wholesale_rows.index(row)
                hub_region = self.hub_regions[position]
                for cid, stage in self.material_catalog.hub_commodity_stages:
                    g = self.commodity_index.get(cid)
                    if g is None:
                        continue
                    stage_code = self._stage_of(stage)
                    prov = self._add_cell(
                        kind_org,
                        org.organization_id,
                        hub_region,
                        _POOL_WHOLESALE,
                        g,
                        stage_code,
                    )
                    self.hub_cell_records.append((position, g, stage_code, prov))
                continue
            if org_kind is OrganizationType.RETAIL:
                position = self.retail_rows.index(row)
                for served in self.retail_served[position]:
                    for cid, stage in self.material_catalog.retail_commodity_stages:
                        g = self.commodity_index.get(cid)
                        if g is None:
                            continue
                        prov = self._add_cell(
                            kind_org,
                            org.organization_id,
                            served,
                            _POOL_RETAIL,
                            g,
                            self._stage_of(stage),
                        )
                        self.retail_cell_records.append(
                            (position, served, g, self._stage_of(stage), prov)
                        )
                continue
            # productive organization: one activity, input and output cells
            technology = self.technologies[self.org_tech_row[row]]
            activity = org_activity
            org_activity += 1
            for coefficient in technology.inputs:
                g = self.commodity_index[coefficient.commodity_id]
                stage_code = self._stage_of(coefficient.stage)
                prov = self._add_cell(
                    kind_org, org.organization_id, region, _POOL_INPUT, g, stage_code
                )
                self.k_activity.append(activity)
                self.k_cell.append(prov)
                self.k_coefficient.append(float(coefficient.coefficient))
                self.k_timing.append(
                    1 if coefficient.resolved_input_timing == "same_quarter_service" else 0
                )
                self.input_cell_of_org[(row, g, stage_code)] = prov
            for output_coefficient in technology.outputs:
                g = self.commodity_index[output_coefficient.commodity_id]
                stage_code = self._stage_of(output_coefficient.stage)
                prov = self._add_cell(
                    kind_org, org.organization_id, region, _POOL_OUTPUT, g, stage_code
                )
                self.b_activity.append(activity)
                self.b_cell.append(prov)
                self.b_coefficient.append(float(output_coefficient.coefficient))
                self.org_output_records.append((row, g, stage_code, prov))
            for cid in self.material_catalog.investment_commodity_ids:
                g = self.commodity_index.get(cid)
                if g is None:
                    continue
                prov = self._add_cell(
                    kind_project,
                    org.organization_id,
                    region,
                    _POOL_WIP,
                    g,
                    STAGE_CODES["standard"],
                )
                self.project_cell_of[(row, g)] = prov

        # private plots: three input cells and the raw/self/market food cells
        self.plot_input_map: dict[tuple[int, int], int] = {}
        self.plot_raw_map: dict[int, int] = {}
        self.plot_ready_self_map: dict[int, int] = {}
        self.plot_ready_market_map: dict[int, int] = {}
        role_coefficients = {
            "energy": self.plot_recipe.input_energy,
            "raw": self.plot_recipe.input_raw_materials,
            "capital": self.plot_recipe.input_capital_goods,
        }
        self.plot_coefficient_by_id: dict[str, float] = {}
        for role, coefficient in role_coefficients.items():
            role_ids = self.material_catalog.with_role(role)
            if role_ids and role_ids[0] in self.commodity_index:
                self.plot_coefficient_by_id[role_ids[0]] = float(coefficient)
        food_raw_g = self._role_g("food_raw")
        food_ready_g = self._role_g("food")
        if food_raw_g is None:
            food_raw_g = food_ready_g
        if food_ready_g is None:
            food_ready_g = food_raw_g
        plot_inputs = sorted(
            self.commodity_index[cid]
            for cid in self.plot_coefficient_by_id
            if cid in self.commodity_index
        )
        self.plot_input_commodities = plot_inputs
        for region in range(self.region_count):
            for g in plot_inputs:
                prov = self._add_cell(
                    kind_plot, -1, region, _POOL_INPUT, g, STAGE_CODES["standard"]
                )
                self.plot_input_map[(region, g)] = prov
            if food_raw_g is not None:
                self.plot_raw_map[region] = self._add_cell(
                    kind_plot, -1, region, _POOL_OUTPUT, food_raw_g, STAGE_CODES["raw"]
                )
            if food_ready_g is not None:
                self.plot_ready_self_map[region] = self._add_cell(
                    kind_plot, -1, region, _POOL_INPUT, food_ready_g, STAGE_CODES["ready"]
                )
                self.plot_ready_market_map[region] = self._add_cell(
                    kind_plot, -1, region, _POOL_RETAIL, food_ready_g, STAGE_CODES["ready"]
                )

        # treasury national import pool (region -1: never folded into a region)
        self.import_cell_map: dict[int, int] = {}
        for g in range(self.commodity_count):
            if not self.importable[g]:
                continue
            self.import_cell_map[g] = self._add_cell(
                kind_treasury,
                -1,
                -1,
                _POOL_IMPORT,
                g,
                STAGE_CODES[self._consumable_stage(g)],
            )

    def _finalize_cells(self) -> None:
        kind = np.asarray(self.cell_kind, dtype=np.int8)
        owner = np.asarray(self.cell_owner, dtype=np.int64)
        region = np.asarray(self.cell_region_list, dtype=np.int32)
        pool = np.asarray(self.cell_pool, dtype=np.int8)
        commodity = np.asarray(self.cell_commodity_list, dtype=np.int16)
        stage = np.asarray(self.cell_stage, dtype=np.int8)
        order = np.lexsort((stage, commodity, pool, region, owner, kind))
        row_count = kind.size
        if row_count:
            same = (
                (kind[order][1:] == kind[order][:-1])
                & (owner[order][1:] == owner[order][:-1])
                & (region[order][1:] == region[order][:-1])
                & (pool[order][1:] == pool[order][:-1])
                & (commodity[order][1:] == commodity[order][:-1])
                & (stage[order][1:] == stage[order][:-1])
            )
            if bool(np.any(same)):
                first = int(np.flatnonzero(same)[0])
                raise ResearchGateError(
                    "duplicate stock cell catalog key "
                    f"({_KIND_NAMES[int(kind[order][first])]}, "
                    f"{int(owner[order][first])}, {int(region[order][first])}, "
                    f"{_POOL_NAMES[int(pool[order][first])]}, "
                    f"{self.commodity_ids[int(commodity[order][first])]}, "
                    f"{_STAGE_NAMES[int(stage[order][first])]})"
                )
        self.cell_kind_np = kind[order]
        self.cell_owner_np = owner[order]
        self.cell_region_np = region[order]
        self.cell_pool_np = pool[order]
        self.cell_commodity_np = commodity[order]
        self.cell_stage_np = stage[order]
        self.cell_count = row_count

        prov_final = np.empty(row_count, dtype=np.int64)
        prov_final[order] = np.arange(row_count, dtype=np.int64)
        self.prov_final = prov_final

        self.cell_index: dict[tuple[str, int, int, str, str, str], int] = {}
        for final_row in range(row_count):
            self.cell_index[
                (
                    _KIND_NAMES[int(self.cell_kind_np[final_row])],
                    int(self.cell_owner_np[final_row]),
                    int(self.cell_region_np[final_row]),
                    _POOL_NAMES[int(self.cell_pool_np[final_row])],
                    self.commodity_ids[int(self.cell_commodity_np[final_row])],
                    _STAGE_NAMES[int(self.cell_stage_np[final_row])],
                )
            ] = final_row

        # bank guard: no organization cell may belong to a bank
        kind_code_org = owner_kind_code(CellOwnerKind.ORGANIZATION)
        org_block = int(np.count_nonzero(self.cell_kind_np == kind_code_org))
        for org_row in self.cell_owner_np[:org_block].tolist():
            if self.org_type[org_row] is OrganizationType.BANK:
                raise ResearchGateError(f"bank organization {org_row} must not own material cells")

        # stage legality is read from each commodity's declared spec, not a
        # single food id: a multi-stage commodity (raw/ready food) may carry
        # non-standard cells, every other commodity must be standard.
        for g in range(self.commodity_count):
            spec = commodity_spec(self.commodity_ids[g])
            allowed = {STAGE_CODES[stage] for stage in spec.stages}
            cells = self.cell_commodity_np == g
            if not bool(np.any(cells)):
                continue
            used = set(np.unique(self.cell_stage_np[cells]).tolist())
            if not used <= allowed:
                raise ResearchGateError(
                    f"commodity {self.commodity_ids[g]!r} carries stages outside its "
                    f"declared set: {sorted(used - allowed)}"
                )

        # producer / hub / retail lookups in final rows
        self.producers: dict[tuple[int, int], list[tuple[int, int]]] = {}
        for org_row, g, stage_code, prov in self.org_output_records:
            self.producers.setdefault((g, stage_code), []).append((int(prov_final[prov]), org_row))
        for sources in self.producers.values():
            sources.sort()
        self.hub_cells: dict[tuple[int, int, int], int] = {}
        self.hub_cell_list: dict[tuple[int, int], list[tuple[int, int, int]]] = {}
        for position, g, stage_code, prov in self.hub_cell_records:
            final_row = int(prov_final[prov])
            self.hub_cells[(position, g, stage_code)] = final_row
            self.hub_cell_list.setdefault((g, stage_code), []).append(
                (final_row, position, self.hub_regions[position])
            )
        self.retail_cells: dict[tuple[int, int, int, int], int] = {}
        for position, served, g, stage_code, prov in self.retail_cell_records:
            self.retail_cells[(position, served, g, stage_code)] = int(prov_final[prov])
        self.project_cells_final = {
            key: int(prov_final[prov]) for key, prov in self.project_cell_of.items()
        }
        self.import_cells_final = {
            g: int(prov_final[prov]) for g, prov in self.import_cell_map.items()
        }
        self.plot_input_final = {
            key: int(prov_final[prov]) for key, prov in self.plot_input_map.items()
        }
        self.plot_raw_final = {r: int(prov_final[prov]) for r, prov in self.plot_raw_map.items()}
        self.plot_ready_self_final = {
            r: int(prov_final[prov]) for r, prov in self.plot_ready_self_map.items()
        }
        self.plot_ready_market_final = {
            r: int(prov_final[prov]) for r, prov in self.plot_ready_market_map.items()
        }
        self.input_cells_final = {
            key: int(prov_final[prov]) for key, prov in self.input_cell_of_org.items()
        }

    # ------------------------------------------------------------------
    # step 3: activities and the sparse A/B matrices
    # ------------------------------------------------------------------

    def _plot_land_capacity(self) -> np.ndarray:
        households = self.initial.households
        participating = np.asarray(households.plot_participating, dtype=bool)
        persons = np.asarray(households.weight, dtype=np.float64) * np.asarray(
            households.size, dtype=np.float64
        )
        selected = persons[participating]
        regions = np.asarray(households.region, dtype=np.int64)[participating]
        if selected.size:
            participating_persons = np.bincount(
                regions, weights=selected, minlength=self.region_count
            )
        else:
            participating_persons = np.zeros(self.region_count, dtype=np.float64)
        return participating_persons * self.plot_recipe.capacity_per_participating_person

    def _build_activities(self) -> None:
        org_rows = self.productive_rows
        plot_base = self.plot_activity_base
        self.activity_count = plot_base + self.region_count
        self.activity_kind_np = np.concatenate(
            [
                np.zeros(plot_base, dtype=np.int8),
                np.ones(self.region_count, dtype=np.int8),
            ]
        )
        self.activity_org_np = np.asarray([*org_rows, *([-1] * self.region_count)], dtype=np.int32)
        self.activity_region_np = np.asarray(
            [*map(self.org_region.__getitem__, org_rows), *range(self.region_count)],
            dtype=np.int32,
        )
        land = self._plot_land_capacity()
        self.activity_capacity_np = np.concatenate(
            [
                np.asarray(
                    [self.organizations[row].capacity for row in org_rows],
                    dtype=np.float64,
                ),
                land,
            ]
        )

        # plot inputs append to K in commodity-index order
        for region in range(self.region_count):
            for g in self.plot_input_commodities:
                activity = plot_base + region
                self.k_activity.append(activity)
                self.k_cell.append(self.plot_input_map[(region, g)])
                self.k_coefficient.append(self.plot_coefficient_by_id[self.commodity_ids[g]])
                self.k_timing.append(0)  # plot inputs are stockable by construction

        # plot outputs into raw/self/market cells (zero shares omitted)
        if self.plot_raw_map:
            raw_share = self.plot_recipe.output_raw_share
            self_share = self.plot_recipe.self_use_fraction
            market_share = self.plot_recipe.direct_market_fraction
            for region in range(self.region_count):
                activity = plot_base + region
                rows: list[tuple[int, float]] = [
                    (self.plot_raw_map[region], raw_share),
                    (self.plot_ready_self_map[region], self_share),
                    (self.plot_ready_market_map[region], market_share),
                ]
                for cell, share in rows:
                    if share > 0.0:
                        self.b_activity.append(activity)
                        self.b_cell.append(cell)
                        self.b_coefficient.append(float(share))

        self.k_count = len(self.k_activity)
        self.input_activity_np = np.asarray(self.k_activity, dtype=np.int32)
        self.input_cell_np = self.prov_final[np.asarray(self.k_cell, dtype=np.int64)].astype(
            np.int32
        )
        if self.k_count:
            self.A_matrix = csr_matrix(
                (
                    np.asarray(self.k_coefficient, dtype=np.float64),
                    (
                        self.input_activity_np.astype(np.int64),
                        np.arange(self.k_count, dtype=np.int64),
                    ),
                ),
                shape=(self.activity_count, self.k_count),
            )
        else:
            self.A_matrix = csr_matrix((self.activity_count, 0))
        self.B_matrix = csr_matrix(
            (
                np.asarray(self.b_coefficient, dtype=np.float64),
                (
                    np.asarray(self.b_activity, dtype=np.int64),
                    self.prov_final[np.asarray(self.b_cell, dtype=np.int64)],
                ),
            ),
            shape=(self.activity_count, self.cell_count),
        )
        if self.B_matrix.nnz != len(self.b_coefficient):
            raise ResearchGateError("duplicate B output cell per activity")
        if not np.all(np.isfinite(self.A_matrix.data)) or bool(np.any(self.A_matrix.data <= 0.0)):
            raise ResearchGateError("A coefficients must be finite and positive")
        if not np.all(np.isfinite(self.B_matrix.data)) or bool(np.any(self.B_matrix.data <= 0.0)):
            raise ResearchGateError("B coefficients must be finite and positive")

        # P05 §0.4: same-quarter service dependency DAG.  An activity may only
        # be scheduled early when it produces a non-stockable service and every
        # input is opening stock; a non-stockable producer that itself needs a
        # same-quarter service is an undeclared cycle.
        self.input_timing_np = np.asarray(self.k_timing, dtype=np.int8)
        has_same_quarter_input = np.zeros(self.activity_count, dtype=np.float64)
        if self.k_count:
            np.add.at(
                has_same_quarter_input,
                self.input_activity_np.astype(np.int64),
                self.input_timing_np.astype(np.float64),
            )
        produces_service = np.zeros(self.activity_count, dtype=bool)
        for activity, cell in zip(self.b_activity, self.b_cell, strict=True):
            g = int(self.cell_commodity_np[int(self.prov_final[cell])])
            if not bool(self.commodity_stockable[g]):
                produces_service[activity] = True
        early = produces_service  # every non-stockable producer runs early (tiered)
        self.activity_early_service_np = early
        self.early_service_tiers_np = self._early_service_tiers(early)

    def _early_service_tiers(self, early: np.ndarray) -> list[np.ndarray]:
        """Topological tiers of same-quarter service producers (P05 §0.4).

        Activity A depends on B when A consumes same-quarter a non-stockable
        commodity that B produces.  A true cycle is a ConfigError; otherwise the
        tiers give the order in which the kernel must produce them.
        """
        producers_of: dict[int, set[int]] = {}
        for activity, cell in zip(self.b_activity, self.b_cell, strict=True):
            g = int(self.cell_commodity_np[int(self.prov_final[cell])])
            if not bool(self.commodity_stockable[g]):
                producers_of.setdefault(g, set()).add(activity)
        members = [int(a) for a in np.flatnonzero(early)]
        deps: dict[int, set[int]] = {a: set() for a in members}
        for index in range(self.k_count):
            if int(self.input_timing_np[index]) != 1:
                continue
            activity = int(self.input_activity_np[index])
            if activity not in deps:
                continue
            g = int(self.cell_commodity_np[int(self.input_cell_np[index])])
            for producer in producers_of.get(g, ()):
                if producer != activity:
                    deps[activity].add(producer)
        tiers: list[np.ndarray] = []
        remaining = set(members)
        while remaining:
            ready = sorted(a for a in remaining if not (deps[a] & remaining))
            if not ready:
                raise ConfigError(
                    "same-quarter service cycle among activities "
                    f"{sorted(remaining)}"
                )
            tiers.append(np.asarray(ready, dtype=np.int64))
            remaining -= set(ready)
        return tiers

    # ------------------------------------------------------------------
    # step 4: demand cells and edges
    # ------------------------------------------------------------------

    def _add_demand(
        self,
        destination: int,
        purpose: RoutePurpose,
        activity: int,
        input_index: int,
        share: float = 1.0,
    ) -> int:
        self.demand_destination.append(destination)
        self.demand_purpose_list.append(PURPOSE_CODES[purpose])
        self.demand_activity_list.append(activity)
        self.demand_input_list.append(input_index)
        self.demand_share_list.append(float(share))
        return len(self.demand_destination) - 1

    def _add_edge(
        self,
        source: int,
        destination: int,
        demand: int,
        purpose: RoutePurpose,
        weight: float,
        buyer_org: int,
        transport_region: int,
        transport_override: int | None = None,
        fallback: bool = False,
    ) -> None:
        source_region = int(self.cell_region_np[source])
        g = int(self.cell_commodity_np[source])
        stockable = bool(self.commodity_stockable[g]) if g < self.commodity_stockable.size else True
        if not self.explicit_distance:
            # Legacy declared proxy (intermediate8): same-region edges are free
            # and the ring picks the carrier.  P05 §0.2's self-haul rule still
            # applies so a carrier's own fuel never depends on its own service
            # pool (the transport-insolvency trap).
            buyer_is_transport = buyer_org >= 0 and buyer_org in self.transport_rows
            if buyer_is_transport and stockable:
                transport_org, per_unit = -1, 0.0
            elif source_region >= 0 and source_region == transport_region:
                transport_org, per_unit = -1, 0.0
            elif not self.transport_rows:
                transport_org, per_unit = -1, self.default_transport_per_unit
            else:
                base = source_region if source_region >= 0 else transport_region
                base = base if base >= 0 else 0
                transport_org = int(self.transport_rows[base % len(self.transport_rows)])
                per_unit = self.default_transport_per_unit
            self.edge_source_list.append(source)
            self.edge_destination_list.append(destination)
            self.edge_demand_list.append(demand)
            self.edge_purpose_list.append(PURPOSE_CODES[purpose])
            self.edge_weight_list.append(float(weight))
            self.edge_transport_list.append(transport_org)
            self.edge_per_unit_list.append(per_unit)
            self.edge_buyer_list.append(buyer_org)
            self.edge_self_hauled_list.append(transport_org < 0)
            self.edge_fallback_list.append(bool(fallback))
            self.edge_distance_list.append(
                float(_cyclic_distance(source_region if source_region >= 0 else transport_region,
                                       transport_region, self.region_count))
            )
            return
        buyer_is_transport = buyer_org >= 0 and buyer_org in self.transport_rows
        # P05 §0.2: a carrier's own stockable production input is self-hauled
        # (its fleet burns its own fuel, claims no other carrier), and a
        # non-stockable service delivery never requests a second transport
        # service. Every other routed edge with logistics work selects a
        # carrier and pays a fee; no carrier means a diagnosable zero delivery.
        self_hauled = (buyer_is_transport and stockable) or (not stockable)
        if self_hauled:
            transport_org = -1
            per_unit = 0.0
        elif transport_override is not None:
            transport_org = transport_override
            per_unit = self.default_transport_per_unit
        else:
            transport_org = self._select_carrier(
                source_region,
                transport_region,
                float(weight) * float(self.default_transport_per_unit),
            )
            per_unit = self.default_transport_per_unit if transport_org >= 0 else 0.0
        self.edge_source_list.append(source)
        self.edge_destination_list.append(destination)
        self.edge_demand_list.append(demand)
        self.edge_purpose_list.append(PURPOSE_CODES[purpose])
        self.edge_weight_list.append(float(weight))
        self.edge_transport_list.append(transport_org)
        self.edge_per_unit_list.append(per_unit)
        self.edge_buyer_list.append(buyer_org)
        self.edge_self_hauled_list.append(bool(self_hauled))
        self.edge_fallback_list.append(bool(fallback))
        self.edge_distance_list.append(self._region_distance_of(source_region, transport_region))

    def _consumable_stage(self, g: int) -> Stage:
        """The stage a commodity is delivered, imported or exported in.

        Read from the registry (retail stage, else hub stage, else the first
        declared stage) so a new commodity never needs an engine change.
        """
        spec = commodity_spec(self.commodity_ids[g])
        return spec.consumable_stage()

    def _ranked_producers(
        self, g: int, stage_code: int, buyer_region: int
    ) -> list[tuple[int, int]]:
        candidates = self.producers.get((g, stage_code), [])
        return sorted(
            candidates,
            key=lambda item: (
                _cyclic_distance(
                    buyer_region, int(self.cell_region_np[item[0]]), self.region_count
                ),
                item[0],
            ),
        )

    def _standard_sources(
        self, g: int, stage_code: int, buyer_region: int
    ) -> list[tuple[int, float]]:
        """Nearest-2 domestic producers; importable demands add the buffer."""
        ranked = self._ranked_producers(g, stage_code, buyer_region)
        sources: list[int] = []
        if g in self.import_cells_final:
            sources = ([ranked[0][0]] if ranked else []) + [self.import_cells_final[g]]
        else:
            sources = [cell for cell, _ in ranked[:2]]
        if not sources:
            return []
        share = 1.0 / len(sources)
        return [(cell, share) for cell in sources]

    def _nearest_hubs(
        self, g: int, stage_code: int, buyer_region: int, count: int = 2
    ) -> list[tuple[int, float]]:
        candidates = self.hub_cell_list.get((g, stage_code), [])
        ranked = sorted(
            candidates,
            key=lambda item: (
                _cyclic_distance(buyer_region, item[2], self.region_count),
                item[0],
            ),
        )[:count]
        if not ranked:
            return []
        share = 1.0 / len(ranked)
        return [(item[0], share) for item in ranked]

    def _producer_fallback_sources(
        self, g: int, stage_code: int, buyer_region: int, declared: set[int]
    ) -> list[tuple[int, float]]:
        """P05 §0.3 fallback: every other producer of the same commodity/stage."""
        ranked = self._ranked_producers(g, stage_code, buyer_region)
        extra = [cell for cell, _row in ranked if cell not in declared]
        if not extra:
            return []
        share = 1.0 / len(extra)
        return [(cell, share) for cell in extra]

    def _hub_fallback_sources(
        self, g: int, stage_code: int, buyer_region: int, declared: set[int]
    ) -> list[tuple[int, float]]:
        """Fallback hubs beyond the declared nearest-hub set."""
        candidates = self.hub_cell_list.get((g, stage_code), [])
        ranked = sorted(
            candidates,
            key=lambda item: (
                _cyclic_distance(buyer_region, item[2], self.region_count),
                item[0],
            ),
        )
        extra = [item[0] for item in ranked if item[0] not in declared]
        if not extra:
            return []
        share = 1.0 / len(extra)
        return [(cell, share) for cell in extra]

    def _nearest_hub_position(self, region: int) -> int:
        return min(
            range(len(self.wholesale_rows)),
            key=lambda position: (
                _cyclic_distance(region, self.hub_regions[position], self.region_count),
                position,
            ),
        )

    def _construction_sources(self, buyer_region: int) -> list[tuple[int, float]]:
        g = self._role_g("construction")
        if g is None:
            return []
        return self._standard_sources(g, STAGE_CODES["standard"], buyer_region)

    def _build_demand_skeleton(self) -> None:
        """D block 1: every K row is a demand cell (plots use private_plot)."""
        self.demand_destination: list[int] = []
        self.demand_purpose_list: list[int] = []
        self.demand_activity_list: list[int] = []
        self.demand_input_list: list[int] = []
        self.demand_share_list: list[float] = []
        self.edge_source_list: list[int] = []
        self.edge_destination_list: list[int] = []
        self.edge_demand_list: list[int] = []
        self.edge_purpose_list: list[int] = []
        self.edge_weight_list: list[float] = []
        self.edge_transport_list: list[int] = []
        self.edge_per_unit_list: list[float] = []
        self.edge_buyer_list: list[int] = []
        self.edge_self_hauled_list: list[bool] = []
        self.edge_fallback_list: list[bool] = []
        self.edge_distance_list: list[float] = []
        plot_base = self.plot_activity_base
        self.k_demand = np.arange(self.k_count, dtype=np.int32)
        for k in range(self.k_count):
            activity = int(self.input_activity_np[k])
            is_plot = activity >= plot_base
            purpose = RoutePurpose.PRIVATE_PLOT if is_plot else RoutePurpose.INTERMEDIATE
            self._add_demand(int(self.input_cell_np[k]), purpose, activity, k)

        # blocks 4-6 (indices recorded; edges attach in the graph builders)
        self.investment_demand: dict[tuple[int, int], int] = {}
        for row in self.productive_rows:
            for cid in self.material_catalog.investment_commodity_ids:
                g = self.commodity_index.get(cid)
                if g is None or (row, g) not in self.project_cells_final:
                    continue
                self.investment_demand[(row, g)] = self._add_demand(
                    self.project_cells_final[(row, g)], RoutePurpose.INVESTMENT, -1, -1
                )
        self.housing_demand: list[int] = []
        for _ in range(self.region_count):
            self.housing_demand.append(self._add_demand(-1, RoutePurpose.HOUSING, -1, -1))
        self.export_demand_index = np.full((2, self.commodity_count), -1, dtype=np.int32)
        for channel, purpose in (
            (0, RoutePurpose.EXPORT_CMEA),
            (1, RoutePurpose.EXPORT_CONVERTIBLE),
        ):
            for g in range(self.commodity_count):
                if self.export_demand[channel, g] > 0.0:
                    self.export_demand_index[channel, g] = self._add_demand(-1, purpose, -1, -1)
        self.household_demand: dict[tuple[int, int], int] = {}
        household_goods = [g for g, spec in enumerate(self.commodities) if spec.household_channel]
        self.household_goods = household_goods
        for region in range(self.region_count):
            for g in household_goods:
                self.household_demand[(region, g)] = self._add_demand(
                    -1, RoutePurpose.HOUSEHOLD, -1, -1
                )

    def _trader_block_start(self) -> int:
        return len(self.demand_destination)

    def _build_default_graph(self) -> None:
        """Default nearest graph (plan step 2 '默认network固定').

        The pinned D order is [K, trader, investment, housing, export,
        household]; the skeleton already appended the post-trader blocks, so
        the trader cells are spliced in at the recorded boundary and the
        stored absolute indices shift by the trader block length.
        """
        trader_start = self._trader_block_start()
        # dest, purpose, activity, input, static share of the owner's need
        trader_rows: list[tuple[int, int, int, int, float]] = []

        def add_trader(destination: int, purpose: RoutePurpose, share: float = 1.0) -> int:
            trader_rows.append((destination, PURPOSE_CODES[purpose], -1, -1, float(share)))
            return trader_start + len(trader_rows) - 1

        # collection intents: suppliers partitioned to their nearest hub,
        # grouped in consecutive canonical pairs (<=2 sources per demand cell)
        hub_suppliers: dict[tuple[int, int, int], list[tuple[int, float]]] = {}
        if self.wholesale_rows:
            for (g, stage_code), producer_cells in sorted(self.producers.items()):
                if (
                    self.commodity_ids[g],
                    _STAGE_NAMES[stage_code],
                ) not in self.material_catalog.hub_commodity_stages:
                    continue
                for cell, org_row in producer_cells:
                    position = self._nearest_hub_position(int(self.cell_region_np[cell]))
                    hub_suppliers.setdefault((position, g, stage_code), []).append(
                        (cell, float(self.organizations[org_row].capacity))
                    )
            food_raw_g = self._role_g("food_raw")
            if food_raw_g is not None:
                raw_code = STAGE_CODES["raw"]
                for region, cell in sorted(self.plot_raw_final.items()):
                    position = self._nearest_hub_position(region)
                    hub_suppliers.setdefault((position, food_raw_g, raw_code), []).append(
                        (
                            cell,
                            float(self.activity_capacity_np[self.plot_activity_base + region]),
                        )
                    )
            for g, cell in sorted(self.import_cells_final.items()):
                stage_code = int(self.cell_stage_np[cell])
                if (
                    self.commodity_ids[g],
                    _STAGE_NAMES[stage_code],
                ) not in self.material_catalog.hub_commodity_stages:
                    continue  # raw/capital imports sell directly, not via hubs
                position = 0  # national buffer: nearest hub = lowest position
                hub_suppliers.setdefault((position, g, stage_code), []).append(
                    (cell, float(self.import_cap[g]))
                )
        for position, g, stage_code in sorted(hub_suppliers):
            suppliers = sorted(hub_suppliers[(position, g, stage_code)])
            destination = self.hub_cells[(position, g, stage_code)]
            buyer = self.wholesale_rows[position]
            destination_capacity = sum(capacity for _, capacity in suppliers)
            for start in range(0, len(suppliers), 2):
                group = suppliers[start : start + 2]
                total_capacity = sum(capacity for _, capacity in group)
                share = (
                    total_capacity / destination_capacity
                    if destination_capacity > 0.0
                    else 1.0 / ((len(suppliers) + 1) // 2)
                )
                demand = add_trader(destination, RoutePurpose.PROCUREMENT, share)
                if total_capacity > 0.0:
                    weights = [capacity / total_capacity for _, capacity in group]
                else:
                    weights = [1.0 / len(group)] * len(group)
                for (cell, _), weight in zip(group, weights, strict=True):
                    self._add_edge(
                        cell,
                        destination,
                        demand,
                        RoutePurpose.PROCUREMENT,
                        weight,
                        buyer,
                        int(self.cell_region_np[destination]),
                    )

        # retail replenishment intents (goods from hubs, services from transport)
        services_g = self._role_g("service")
        for position, org_row in enumerate(self.retail_rows):
            for served in self.retail_served[position]:
                for cid, stage in self.material_catalog.retail_commodity_stages:
                    retail_g = self.commodity_index.get(cid)
                    if retail_g is None:
                        continue
                    stage_code = self._stage_of(stage)
                    retail_cell_row = self.retail_cells.get(
                        (position, served, retail_g, stage_code)
                    )
                    if retail_cell_row is None:
                        continue
                    demand = add_trader(retail_cell_row, RoutePurpose.RETAIL)
                    if retail_g == services_g:
                        # same-tick services: two nearest transport producers
                        ranked = self._ranked_producers(retail_g, stage_code, served)[:2]
                        share = 1.0 / len(ranked) if ranked else 0.0
                        retail_sources = [(item[0], share) for item in ranked]
                    else:
                        retail_sources = self._nearest_hubs(retail_g, stage_code, served)
                        if not retail_sources and bool(
                            getattr(
                                self.initial.parameters,
                                "retail_replenishment_fallback",
                                False,
                            )
                        ):
                            # A commodity that declares retail stages but no hub
                            # stage (F2's g03 electricity and g16 public services)
                            # has no hub to collect from, so its retail cells could
                            # never be replenished and its household demand never
                            # materialised.  Fall back to the commodity's producers,
                            # the path the first service role already uses.  The
                            # nine commodities that do have hubs are untouched
                            # because the hub branch above already returned.
                            ranked = self._ranked_producers(retail_g, stage_code, served)[:2]
                            share = 1.0 / len(ranked) if ranked else 0.0
                            retail_sources = [(item[0], share) for item in ranked]
                    for source, weight in retail_sources:
                        self._add_edge(
                            source,
                            retail_cell_row,
                            demand,
                            RoutePurpose.RETAIL,
                            weight,
                            org_row,
                            served,
                        )

        # splice the trader block into the D axis after the K block
        spliced_destination = [
            *self.demand_destination[:trader_start],
            *[row[0] for row in trader_rows],
            *self.demand_destination[trader_start:],
        ]
        spliced_purpose = [
            *self.demand_purpose_list[:trader_start],
            *[row[1] for row in trader_rows],
            *self.demand_purpose_list[trader_start:],
        ]
        spliced_activity = [
            *self.demand_activity_list[:trader_start],
            *[row[2] for row in trader_rows],
            *self.demand_activity_list[trader_start:],
        ]
        spliced_input = [
            *self.demand_input_list[:trader_start],
            *[row[3] for row in trader_rows],
            *self.demand_input_list[trader_start:],
        ]
        spliced_share = [
            *self.demand_share_list[:trader_start],
            *[row[4] for row in trader_rows],
            *self.demand_share_list[trader_start:],
        ]
        shift = len(trader_rows)
        self.demand_destination = spliced_destination
        self.demand_purpose_list = spliced_purpose
        self.demand_activity_list = spliced_activity
        self.demand_input_list = spliced_input
        self.demand_share_list = spliced_share
        self.investment_demand = {
            key: demand + shift if demand >= trader_start else demand
            for key, demand in self.investment_demand.items()
        }
        self.housing_demand = [
            demand + shift if demand >= trader_start else demand for demand in self.housing_demand
        ]
        self.export_demand_index = np.where(
            self.export_demand_index >= trader_start,
            self.export_demand_index + shift,
            self.export_demand_index,
        )
        self.household_demand = {
            key: demand + shift if demand >= trader_start else demand
            for key, demand in self.household_demand.items()
        }

        # --- block 1 edges: production inputs --------------------------
        plot_base = self.plot_activity_base
        for k in range(self.k_count):
            destination = int(self.input_cell_np[k])
            activity = int(self.input_activity_np[k])
            g = int(self.cell_commodity_np[destination])
            stage_code = int(self.cell_stage_np[destination])
            buyer_region = int(self.activity_region_np[activity])
            buyer = int(self.activity_org_np[activity])
            purpose = (
                RoutePurpose.PRIVATE_PLOT if activity >= plot_base else RoutePurpose.INTERMEDIATE
            )
            spec = commodity_spec(self.commodity_ids[g])
            if len(spec.stages) > 1 and spec.stages[0] == _STAGE_NAMES[stage_code]:
                # A staged commodity is collected through the wholesale hubs in its
                # first stage (raw food); everything else comes from producers.
                input_sources = self._nearest_hubs(g, stage_code, buyer_region)
            else:
                input_sources = self._standard_sources(g, stage_code, buyer_region)
            for source, weight in input_sources:
                self._add_edge(
                    source,
                    destination,
                    int(self.k_demand[k]),
                    purpose,
                    weight,
                    buyer,
                    buyer_region,
                )
            # P05 §0.3 fallback: additional same-commodity sources used only when
            # the declared sources cannot cover the order.
            declared_cells = {cell for cell, _w in input_sources}
            if len(spec.stages) > 1 and spec.stages[0] == _STAGE_NAMES[stage_code]:
                fallback_sources = self._hub_fallback_sources(
                    g, stage_code, buyer_region, declared_cells
                )
            else:
                fallback_sources = self._producer_fallback_sources(
                    g, stage_code, buyer_region, declared_cells
                )
            for source, weight in fallback_sources:
                self._add_edge(
                    source,
                    destination,
                    int(self.k_demand[k]),
                    purpose,
                    weight,
                    buyer,
                    buyer_region,
                    fallback=True,
                )

        # --- investment / housing / export / household edges ------------
        for row in self.productive_rows:
            region = self.org_region[row]
            for cid in self.material_catalog.investment_commodity_ids:
                investment_g = self.commodity_index.get(cid)
                if investment_g is None or (row, investment_g) not in self.investment_demand:
                    continue
                destination = self.project_cells_final[(row, investment_g)]
                demand = self.investment_demand[(row, investment_g)]
                if cid == self.material_catalog.with_role("construction")[0]:
                    invest_sources = self._construction_sources(region)
                else:
                    invest_sources = self._standard_sources(
                        investment_g, STAGE_CODES["standard"], region
                    )
                for source, weight in invest_sources:
                    self._add_edge(
                        source,
                        destination,
                        demand,
                        RoutePurpose.INVESTMENT,
                        weight,
                        row,
                        region,
                    )
        construction_g = self._role_g("construction")
        for region in range(self.region_count):
            demand = self.housing_demand[region]
            housing_sources = (
                self._construction_sources(region) if construction_g is not None else []
            )
            for source, weight in housing_sources:
                self._add_edge(source, -1, demand, RoutePurpose.HOUSING, weight, -1, region)
        for channel in (0, 1):
            for g in range(self.commodity_count):
                demand = int(self.export_demand_index[channel, g])
                if demand < 0:
                    continue
                stage_code = STAGE_CODES[self._consumable_stage(g)]
                candidates: list[tuple[int, int, int]] = [
                    (cell, 0, int(self.cell_region_np[cell]))
                    for cell, _ in self.producers.get((g, stage_code), [])
                ]
                candidates += [
                    (cell, 1, hub_region)
                    for cell, _, hub_region in self.hub_cell_list.get((g, stage_code), [])
                ]
                ranked_candidates = sorted(
                    candidates,
                    key=lambda item: (
                        _cyclic_distance(EXPORT_ORIGIN_REGION, item[2], self.region_count),
                        item[0],
                    ),
                )[:2]
                purpose = (
                    RoutePurpose.EXPORT_CMEA if channel == 0 else RoutePurpose.EXPORT_CONVERTIBLE
                )
                if ranked_candidates:
                    share = 1.0 / len(ranked_candidates)
                    for cell, _, _ in ranked_candidates:
                        self._add_edge(cell, -1, demand, purpose, share, -1, -1)
        for region in range(self.region_count):
            for hh_g in self.household_goods:
                demand = self.household_demand[(region, hh_g)]
                stage_code = STAGE_CODES[self._consumable_stage(hh_g)]
                household_sources: list[int] = []
                for hh_position in self.region_retail_positions[region][:2]:
                    household_cell = self.retail_cells.get((hh_position, region, hh_g, stage_code))
                    if household_cell is not None:
                        household_sources.append(household_cell)
                if household_sources:
                    share = 1.0 / len(household_sources)
                    for cell in household_sources:
                        self._add_edge(cell, -1, demand, RoutePurpose.HOUSEHOLD, share, -1, region)

    # ------------------------------------------------------------------
    # explicit route lists
    # ------------------------------------------------------------------

    def _resolve_ref(self, ref: StockCellRef, side: str) -> int:
        kind_code = owner_kind_code(ref.owner_kind)
        pool_code = POOL_CODES.get(ref.pool)
        if pool_code is None:
            raise ConfigError(f"route {side} uses unknown pool {ref.pool!r}")
        g = self.commodity_index.get(ref.commodity_id)
        if g is None:
            raise ConfigError(f"route {side} references unknown commodity {ref.commodity_id!r}")
        stage_code = STAGE_CODES[ref.stage]
        owner = ref.organization_id if ref.organization_id is not None else None
        region = self.region_index[ref.region_id] if ref.region_id is not None else None
        matches = [
            row
            for row in range(self.cell_count)
            if int(self.cell_kind_np[row]) == kind_code
            and int(self.cell_pool_np[row]) == pool_code
            and int(self.cell_commodity_np[row]) == g
            and int(self.cell_stage_np[row]) == stage_code
            and (owner is None or int(self.cell_owner_np[row]) == owner)
            and (region is None or int(self.cell_region_np[row]) == region)
        ]
        if not matches:
            raise ConfigError(
                f"route {side} references an unknown stock cell "
                f"({ref.owner_kind.value}, org={ref.organization_id}, "
                f"region={ref.region_id}, pool={ref.pool}, "
                f"commodity={ref.commodity_id}, stage={ref.stage})"
            )
        if len(matches) > 1:
            raise ConfigError(
                f"route {side} matches {len(matches)} stock cells; add an "
                "organization_id/region_id to disambiguate"
            )
        return matches[0]

    def _apply_explicit_routes(self) -> None:
        """Explicit route list: cell-to-cell supply edges only (plan step 2).

        Boundary purposes (housing/export/household) have no destination
        stock cell and cannot be expressed as a ``MaterialRouteSpec``; they
        stay structural demand cells without edges unless the default graph
        is requested.
        """
        trader_start = self._trader_block_start()
        # source, destination, purpose, weight, transport org row (-1 auto)
        resolved: list[tuple[int, int, RoutePurpose, float, int]] = []
        trader_group_keys: set[tuple[int, int]] = set()
        seen_edges: set[tuple[int, int, int]] = set()

        k_demand_by_cell = {int(self.input_cell_np[k]): k for k in range(self.k_count)}
        plot_input_cells = set(self.plot_input_final.values())
        kind_org = owner_kind_code(CellOwnerKind.ORGANIZATION)
        kind_project = owner_kind_code(CellOwnerKind.PROJECT)

        for spec in self.routes or []:
            source = self._resolve_ref(spec.source, "source")
            destination = self._resolve_ref(spec.destination, "destination")
            purpose = spec.purpose
            if purpose in _BORDER_PURPOSES:
                raise ConfigError(
                    f"route purpose {purpose.value} is a boundary sink without a "
                    "destination stock cell; it cannot be declared as a route"
                )
            if purpose not in _ROUTEABLE_PURPOSES:  # pragma: no cover - enum closed
                raise ConfigError(f"unknown route purpose {purpose!r}")
            if int(self.cell_pool_np[source]) not in _SELLING_POOLS:
                raise ConfigError(
                    "route source must be an output/wholesale/retail/import cell, "
                    f"got pool {_POOL_NAMES[int(self.cell_pool_np[source])]}"
                )
            weight = float(spec.weight)
            if not np.isfinite(weight) or weight <= 0.0:
                raise ConfigError("route weight must be finite and positive")
            transport_override = -1
            if spec.transport_organization_id is not None:
                matches = [
                    row
                    for row in self.transport_rows
                    if self.organizations[row].organization_id == spec.transport_organization_id
                ]
                if not matches:
                    raise ConfigError(
                        f"route transport organization "
                        f"{spec.transport_organization_id} is not a transport org"
                    )
                transport_override = matches[0]

            destination_pool = int(self.cell_pool_np[destination])
            destination_kind = int(self.cell_kind_np[destination])
            if destination in k_demand_by_cell:
                expected = (
                    RoutePurpose.PRIVATE_PLOT
                    if destination in plot_input_cells
                    else RoutePurpose.INTERMEDIATE
                )
                if purpose is not expected:
                    raise ConfigError(
                        f"route purpose {purpose.value} does not match the "
                        f"destination production input cell (expected "
                        f"{expected.value})"
                    )
            elif destination_kind == kind_project:
                if purpose is not RoutePurpose.INVESTMENT:
                    raise ConfigError("routes into a project WIP cell must use purpose investment")
            elif destination_pool == _POOL_WHOLESALE:
                if purpose is not RoutePurpose.PROCUREMENT:
                    raise ConfigError("routes into a wholesale cell must use purpose procurement")
                trader_group_keys.add((destination, PURPOSE_CODES[purpose]))
            elif destination_pool == _POOL_RETAIL:
                if purpose is not RoutePurpose.RETAIL:
                    raise ConfigError("routes into a retail cell must use purpose retail")
                trader_group_keys.add((destination, PURPOSE_CODES[purpose]))
            else:
                raise ConfigError(
                    f"route purpose {purpose.value} is incompatible with the destination cell kind"
                )
            edge_key = (source, destination, PURPOSE_CODES[purpose])
            if edge_key in seen_edges:
                raise ConfigError(
                    "duplicate route edge "
                    f"(source cell {source} -> destination cell {destination}, "
                    f"purpose {purpose.value})"
                )
            seen_edges.add(edge_key)
            buyer = (
                int(self.cell_owner_np[destination])
                if destination_kind in (kind_org, kind_project)
                else -1
            )
            resolved.append((source, destination, purpose, weight, transport_override))

        # trader demand cells occupy the block after K, sorted canonically
        ordered = sorted(trader_group_keys)
        remap = {key: trader_start + index for index, key in enumerate(ordered)}
        trader_rows = [(key[0], key[1], -1, -1, 1.0) for key in ordered]
        shift = len(trader_rows)
        self.demand_destination = [
            *self.demand_destination[:trader_start],
            *[row[0] for row in trader_rows],
            *self.demand_destination[trader_start:],
        ]
        self.demand_purpose_list = [
            *self.demand_purpose_list[:trader_start],
            *[row[1] for row in trader_rows],
            *self.demand_purpose_list[trader_start:],
        ]
        self.demand_activity_list = [
            *self.demand_activity_list[:trader_start],
            *[row[2] for row in trader_rows],
            *self.demand_activity_list[trader_start:],
        ]
        self.demand_input_list = [
            *self.demand_input_list[:trader_start],
            *[row[3] for row in trader_rows],
            *self.demand_input_list[trader_start:],
        ]
        self.demand_share_list = [
            *self.demand_share_list[:trader_start],
            *[row[4] for row in trader_rows],
            *self.demand_share_list[trader_start:],
        ]
        self.investment_demand = {
            key: demand + shift for key, demand in self.investment_demand.items()
        }
        self.housing_demand = [demand + shift for demand in self.housing_demand]
        self.export_demand_index = self.export_demand_index + np.where(
            self.export_demand_index >= 0, shift, 0
        )
        self.household_demand = {
            key: demand + shift for key, demand in self.household_demand.items()
        }

        for source, destination, purpose, weight, transport_override in resolved:
            if destination in k_demand_by_cell:
                demand = int(k_demand_by_cell[destination])
            elif int(self.cell_kind_np[destination]) == kind_project:
                g = int(self.cell_commodity_np[destination])
                org_row = int(self.cell_owner_np[destination])
                demand = self.investment_demand[(org_row, g)]
            else:
                demand = remap[(destination, PURPOSE_CODES[purpose])]
            buyer = (
                int(self.cell_owner_np[destination])
                if int(self.cell_kind_np[destination]) in (kind_org, kind_project)
                else -1
            )
            transport_region = int(self.cell_region_np[destination])
            override = None if transport_override < 0 else transport_override
            self._add_edge(
                source,
                destination,
                demand,
                purpose,
                weight,
                buyer,
                transport_region,
                override,
            )

    # ------------------------------------------------------------------
    # step 5: canonical edge order + validation
    # ------------------------------------------------------------------

    def _finalize_edges(self) -> None:
        source = np.asarray(self.edge_source_list, dtype=np.int32)
        destination = np.asarray(self.edge_destination_list, dtype=np.int32)
        demand = np.asarray(self.edge_demand_list, dtype=np.int32)
        purpose = np.asarray(self.edge_purpose_list, dtype=np.int8)
        weight = np.asarray(self.edge_weight_list, dtype=np.float64)
        transport = np.asarray(self.edge_transport_list, dtype=np.int32)
        per_unit = np.asarray(self.edge_per_unit_list, dtype=np.float64)
        buyer = np.asarray(self.edge_buyer_list, dtype=np.int32)
        self_hauled = np.asarray(self.edge_self_hauled_list, dtype=bool)
        fallback = np.asarray(self.edge_fallback_list, dtype=bool)
        distance = np.asarray(self.edge_distance_list, dtype=np.float64)
        self.edge_count = source.size
        if self.edge_count:
            order = np.lexsort(
                (
                    self.cell_stage_np[source].astype(np.int8),
                    purpose,
                    demand,
                    destination,
                    source,
                )
            )
            source = source[order]
            destination = destination[order]
            demand = demand[order]
            purpose = purpose[order]
            weight = weight[order]
            transport = transport[order]
            per_unit = per_unit[order]
            buyer = buyer[order]
            self_hauled = self_hauled[order]
            fallback = fallback[order]
            distance = distance[order]
        self.edge_source_np = source
        self.edge_destination_np = destination
        self.edge_demand_np = demand
        self.edge_purpose_np = purpose
        self.edge_weight_np = weight
        self.edge_transport_np = transport
        self.edge_per_unit_np = per_unit
        self.edge_buyer_np = buyer
        self.edge_self_hauled_np = self_hauled
        self.edge_is_fallback_np = fallback
        self.edge_distance_np = distance
        self.edge_id_np = np.arange(self.edge_count, dtype=np.int64)
        self.demand_count = len(self.demand_destination)
        self.demand_cell_np = np.asarray(self.demand_destination, dtype=np.int32)
        self.demand_purpose_np = np.asarray(self.demand_purpose_list, dtype=np.int8)
        self.demand_activity_np = np.asarray(self.demand_activity_list, dtype=np.int32)
        self.demand_input_np = np.asarray(self.demand_input_list, dtype=np.int32)
        self.demand_share_np = np.asarray(self.demand_share_list, dtype=np.float64)

    def _validate_graph(self) -> None:
        demand_count = self.demand_count
        edge_demand = self.edge_demand_np
        if self.edge_count:
            if int(edge_demand.min()) < 0 or int(edge_demand.max()) >= demand_count:
                raise ResearchGateError("edge references a demand cell out of range")
            if (
                int(self.edge_source_np.min()) < 0
                or int(self.edge_source_np.max()) >= self.cell_count
            ):
                raise ResearchGateError("edge source cell out of range")
            sink_destinations = self.edge_destination_np < 0
            if bool(np.any(self.edge_destination_np[~sink_destinations] >= self.cell_count)):
                raise ResearchGateError("edge destination cell out of range")
            if not np.all(np.isfinite(self.edge_weight_np)) or bool(
                np.any(self.edge_weight_np <= 0.0)
            ):
                raise ResearchGateError("edge weights must be finite and positive")
            if not np.all(np.isfinite(self.edge_per_unit_np)) or bool(
                np.any(self.edge_per_unit_np < 0.0)
            ):
                raise ResearchGateError("transport_per_unit must be finite, >= 0")

            fallback = self.edge_is_fallback_np
            declared_edges = ~fallback
            declared_counts = np.bincount(edge_demand[declared_edges], minlength=demand_count)
            if int(declared_counts.max()) > 2:
                offender = int(np.flatnonzero(declared_counts > 2)[0])
                raise ConfigError(
                    f"demand cell {offender} declares {int(declared_counts[offender])} "
                    "suppliers; at most 2 are allowed"
                )
            sums = np.bincount(
                edge_demand[declared_edges],
                weights=self.edge_weight_np[declared_edges],
                minlength=demand_count,
            )
            served = declared_counts > 0
            if bool(np.any(np.abs(sums[served] - 1.0) > _ATOL)):
                offender = int(np.flatnonzero(served & (np.abs(sums - 1.0) > _ATOL))[0])
                raise ConfigError(
                    f"route weights of demand cell {offender} sum to {sums[offender]!r}, not 1"
                )
            if bool(np.any(fallback)):
                fb_sums = np.bincount(
                    edge_demand[fallback],
                    weights=self.edge_weight_np[fallback],
                    minlength=demand_count,
                )
                fb_served = fb_sums > 0.0
                if bool(np.any(np.abs(fb_sums[fb_served] - 1.0) > _ATOL)):
                    offender = int(np.flatnonzero(fb_served & (np.abs(fb_sums - 1.0) > _ATOL))[0])
                    raise ConfigError(
                        f"fallback weights of demand cell {offender} sum to "
                        f"{fb_sums[offender]!r}, not 1"
                    )
            share = self.demand_share_np
            if not np.all(np.isfinite(share)) or bool(np.any(share <= 0.0)):
                raise ConfigError("demand shares must be finite and positive")
            procurement_code = np.int8(PURPOSE_CODES[RoutePurpose.PROCUREMENT])
            proc = self.demand_purpose_np == procurement_code
            destinations = self.demand_cell_np[proc]
            positive = destinations >= 0
            if bool(np.any(positive)):
                by_hub = np.bincount(
                    destinations[positive],
                    weights=share[proc][positive],
                    minlength=self.cell_count,
                )
                touched = np.flatnonzero(by_hub > 0.0)
                if bool(np.any(np.abs(by_hub[touched] - 1.0) > _ATOL)):
                    offender = int(touched[np.argmax(np.abs(by_hub[touched] - 1.0))])
                    raise ConfigError(
                        f"hub cell {offender} collection intents sum to {by_hub[offender]!r}, "
                        "not one hub need (a hub must not over-order its own requirement)"
                    )

            border_codes = np.asarray(
                [PURPOSE_CODES[purpose] for purpose in _BORDER_PURPOSES], dtype=np.int8
            )
            purpose_np = self.edge_purpose_np
            is_border = np.isin(purpose_np, border_codes)
            if bool(np.any((self.edge_destination_np < 0) & ~is_border)):
                raise ConfigError(
                    "edges into a boundary sink must use a housing/export/household purpose"
                )
            if bool(np.any((self.edge_destination_np >= 0) & is_border)):
                raise ConfigError("housing/export/household purposes must target boundary sinks")
            for purpose in RoutePurpose:
                mask = purpose_np == PURPOSE_CODES[purpose]
                if not bool(np.any(mask)) or purpose in _BORDER_PURPOSES:
                    continue
                pools = self.cell_pool_np[self.edge_destination_np[mask]]
                kinds = self.cell_kind_np[self.edge_destination_np[mask]]
                source_pools = self.cell_pool_np[self.edge_source_np[mask]]
                org_cells = kinds == owner_kind_code(CellOwnerKind.ORGANIZATION)
                plot_cells = kinds == owner_kind_code(CellOwnerKind.PLOT)
                project_cells = kinds == owner_kind_code(CellOwnerKind.PROJECT)
                if purpose is RoutePurpose.INTERMEDIATE:
                    ok = org_cells & (pools == _POOL_INPUT)
                elif purpose is RoutePurpose.PRIVATE_PLOT:
                    ok = plot_cells & (pools == _POOL_INPUT)
                elif purpose is RoutePurpose.PROCUREMENT:
                    ok = org_cells & (pools == _POOL_WHOLESALE)
                elif purpose is RoutePurpose.RETAIL:
                    ok = org_cells & (pools == _POOL_RETAIL)
                elif purpose is RoutePurpose.INVESTMENT:
                    ok = project_cells & (pools == _POOL_WIP)
                else:  # pragma: no cover - border purposes handled above
                    ok = np.zeros(pools.size, dtype=bool)
                if not bool(np.all(ok)):
                    raise ConfigError(
                        f"purpose {purpose.value} is incompatible with a destination cell"
                    )
                if bool(np.any(~np.isin(source_pools, list(_SELLING_POOLS)))):
                    raise ConfigError(f"purpose {purpose.value} has a non-selling source cell")
            for channel_purpose in (RoutePurpose.EXPORT_CMEA, RoutePurpose.EXPORT_CONVERTIBLE):
                mask = purpose_np == PURPOSE_CODES[channel_purpose]
                if not bool(np.any(mask)):
                    continue
                source_pools = self.cell_pool_np[self.edge_source_np[mask]]
                if bool(np.any(~np.isin(source_pools, (_POOL_OUTPUT, _POOL_WHOLESALE)))):
                    raise ConfigError(
                        "export edges must ship out of producer output or wholesale cells"
                    )
            household_mask = purpose_np == PURPOSE_CODES[RoutePurpose.HOUSEHOLD]
            if bool(np.any(household_mask)):
                source_pools = self.cell_pool_np[self.edge_source_np[household_mask]]
                if bool(np.any(source_pools != _POOL_RETAIL)):
                    raise ConfigError("household edges must source from retail cells")
            housing_mask = purpose_np == PURPOSE_CODES[RoutePurpose.HOUSING]
            if bool(np.any(housing_mask)):
                commodities = self.cell_commodity_np[self.edge_source_np[housing_mask]]
                pools = self.cell_pool_np[self.edge_source_np[housing_mask]]
                construction_g = self._role_g("construction")
                if (
                    construction_g is None
                    or bool(np.any(commodities != construction_g))
                    or bool(np.any(pools != _POOL_OUTPUT))
                ):
                    raise ConfigError("housing edges must source construction from producer cells")

    # ------------------------------------------------------------------
    # step 6: assembly
    # ------------------------------------------------------------------

    def _assemble(self) -> MaterialNetwork:
        org_count = self.org_count
        plot_input_cells = np.full((self.region_count, 3), -1, dtype=np.int32)
        plot_role_ids = [
            ids[0]
            for role in ("energy", "raw", "capital")
            if (ids := self.material_catalog.with_role(role))
        ]
        columns = [self.commodity_index.get(cid, -1) for cid in plot_role_ids]
        for region in range(self.region_count):
            for column, g in enumerate(columns):
                if g >= 0 and (region, g) in self.plot_input_final:
                    plot_input_cells[region, column] = self.plot_input_final[(region, g)]
        plot_raw = np.asarray(
            [self.plot_raw_final.get(region, -1) for region in range(self.region_count)],
            dtype=np.int32,
        )
        plot_ready_self = np.asarray(
            [self.plot_ready_self_final.get(region, -1) for region in range(self.region_count)],
            dtype=np.int32,
        )
        plot_ready_market = np.asarray(
            [self.plot_ready_market_final.get(region, -1) for region in range(self.region_count)],
            dtype=np.int32,
        )

        retail_cell = np.full((self.region_count, self.commodity_count), -1, dtype=np.int32)
        for (_position, served, g, _stage_code), cell in sorted(
            self.retail_cells.items(), key=lambda item: item[1]
        ):
            if retail_cell[served, g] < 0:
                retail_cell[served, g] = cell

        import_pool_cell = np.full(self.commodity_count, -1, dtype=np.int32)
        for g, cell in self.import_cells_final.items():
            import_pool_cell[g] = cell

        org_input_cells: dict[int, list[int]] = {row: [] for row in range(org_count)}
        for k in range(self.k_count):
            activity = int(self.input_activity_np[k])
            org_row = int(self.activity_org_np[activity])
            if org_row >= 0:
                org_input_cells[org_row].append(int(self.input_cell_np[k]))

        org_output_cell = np.full(org_count, -1, dtype=np.int32)
        org_wholesale_cell = np.full(org_count, -1, dtype=np.int32)
        for row, org in enumerate(self.organizations):
            if org.type in PRODUCTIVE_TYPES:
                owned = [
                    int(self.prov_final[prov])
                    for org_row2, _, _, prov in self.org_output_records
                    if org_row2 == row
                ]
                if owned:
                    org_output_cell[row] = int(min(owned))
            elif org.type is OrganizationType.WHOLESALE_PROCURMENT:
                position = self.wholesale_rows.index(row)
                owned = [
                    cell for (pos, _g, _stage), cell in self.hub_cells.items() if pos == position
                ]
                if owned:
                    org_output_cell[row] = min(owned)
                    org_wholesale_cell[row] = min(owned)
            elif org.type is OrganizationType.RETAIL:
                position = self.retail_rows.index(row)
                owned = [
                    cell
                    for (pos, _served, _g, _stage), cell in self.retail_cells.items()
                    if pos == position
                ]
                if owned:
                    org_output_cell[row] = min(owned)
                    org_wholesale_cell[row] = min(owned)

        project_capital = np.full(org_count, -1, dtype=np.int32)
        project_construction = np.full(org_count, -1, dtype=np.int32)
        capital_g = self._role_g("capital")
        construction_g = self._role_g("construction")
        for (row, g), cell in self.project_cells_final.items():
            if g == capital_g:
                project_capital[row] = cell
            elif g == construction_g:
                project_construction[row] = cell

        household_parameters = self.initial.household_parameters
        household_catalog = self.initial.household_catalog
        assert household_parameters is not None and household_catalog is not None
        return MaterialNetwork(
            schema_version=MATERIAL_NETWORK_VERSION,
            catalog_id=self.catalog_id,
            region_ids=self.region_ids,
            commodity_ids=self.commodity_ids,
            region_distance=self.region_distance,
            household_parameters=household_parameters,
            household_catalog=household_catalog,
            second_input_commodities=self.second_input_commodities,
            second_output_commodities=self.second_output_commodities,
            retail_cell_by_commodity=retail_cell,
            cell_owner_kind=self.cell_kind_np,
            cell_owner_id=self.cell_owner_np,
            cell_region=self.cell_region_np,
            cell_pool=self.cell_pool_np,
            cell_commodity=self.cell_commodity_np,
            cell_stage=self.cell_stage_np,
            cell_index=self.cell_index,
            activity_kind=self.activity_kind_np,
            activity_org_index=self.activity_org_np,
            activity_region=self.activity_region_np,
            activity_capacity=self.activity_capacity_np,
            activity_early_service=self.activity_early_service_np,
            early_service_tiers=self.early_service_tiers_np,
            A=self.A_matrix,
            input_cell=self.input_cell_np,
            input_activity=self.input_activity_np,
            input_timing=self.input_timing_np,
            B=self.B_matrix,
            demand_cell=self.demand_cell_np,
            demand_purpose=self.demand_purpose_np,
            demand_activity=self.demand_activity_np,
            demand_input_index=self.demand_input_np,
            demand_share=self.demand_share_np,
            edge_source_cell=self.edge_source_np,
            edge_destination_cell=self.edge_destination_np,
            edge_demand=self.edge_demand_np,
            edge_commodity=self.cell_commodity_np[self.edge_source_np].astype(np.int16),
            edge_stage=self.cell_stage_np[self.edge_source_np].astype(np.int8),
            edge_purpose=self.edge_purpose_np,
            edge_weight=self.edge_weight_np,
            edge_transport_org=self.edge_transport_np,
            edge_transport_per_unit=self.edge_per_unit_np,
            edge_buyer_org=self.edge_buyer_np,
            edge_self_hauled=self.edge_self_hauled_np,
            edge_is_fallback=self.edge_is_fallback_np,
            edge_transport_service_cell=np.where(
                self.edge_transport_np >= 0,
                org_output_cell[np.maximum(self.edge_transport_np, 0)],
                -1,
            ).astype(np.int32),
            edge_distance=self.edge_distance_np,
            edge_id=self.edge_id_np,
            org_input_cells=org_input_cells,
            org_output_cell=org_output_cell,
            org_wholesale_cell=org_wholesale_cell,
            plot_input_cells=plot_input_cells,
            plot_raw_cell=plot_raw,
            plot_ready_self_cell=plot_ready_self,
            plot_ready_market_cell=plot_ready_market,
            retail_cell=retail_cell,
            import_pool_cell=import_pool_cell,
            project_capital_cell=project_capital,
            project_construction_cell=project_construction,
            export_demand_cell=self.export_demand_index,
        )

    def compile(self) -> MaterialNetwork:
        self._validate_inputs()
        self._build_org_tables()
        self._build_cells()
        self._finalize_cells()
        self._build_activities()
        self._build_demand_skeleton()
        if self.routes is None:
            self._build_default_graph()
        else:
            self._apply_explicit_routes()
        self._finalize_edges()
        self._validate_graph()
        return self._assemble()


def compile_material_network(
    initial: MaterialInitialConditions,
    technologies: Sequence[TechnologySpec],
    routes: Sequence[MaterialRouteSpec] | None,
    commodities: Sequence[CommoditySpec],
    region_ids: Sequence[str],
    plot_recipe: PrivatePlotRecipe,
    region_distance: np.ndarray | None = None,
) -> MaterialNetwork:
    """Compile the network from one readonly initial draw (pure function)."""
    return _Compiler(
        initial, technologies, routes, commodities, region_ids, plot_recipe, region_distance
    ).compile()


def build_material_network(
    spec: ScenarioSpec,
    contract: ResearchContract,
    initial: MaterialInitialConditions,
    region_distance: np.ndarray | None = None,
) -> MaterialNetwork:
    """Validate the scenario/contract axes, then compile from ``initial``."""
    if spec.kind != "material":
        raise ConfigError(f"build_material_network requires kind='material', got {spec.kind!r}")
    if list(spec.commodities) != list(initial.commodity_ids):
        raise ConfigError("scenario commodities do not match the initial draw")
    contract_regions = tuple(contract.region_ids)
    if tuple(initial.region_ids) != contract_regions:
        raise ConfigError("initial region ids do not match the contract order")
    if tuple(spec.region_ids) != contract_regions:
        raise ConfigError("scenario region ids do not match the contract order")
    specs: list[CommoditySpec] = []
    for commodity_id in initial.commodity_ids:
        specs.append(commodity_spec(commodity_id))
    return compile_material_network(
        initial,
        initial.technologies,
        initial.routes,
        specs,
        contract.region_ids,
        initial.plot_recipe,
        region_distance,
    )


def produce_leontief(
    available: np.ndarray,
    coefficient: np.ndarray,
    activity_index: np.ndarray,
    target: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Segmented Leontief minimum over required inputs.

    ``available``/``coefficient`` are K-length; ``activity_index`` maps each
    input row to its activity in ``[0, P)`` and ``target`` is ``(P,)``.
    Returns ``(realized (P,), used (K,))`` with ``realized = min(target,
    min_k available_k / coefficient_k)`` and ``used_k = coefficient_k *
    realized(activity_k)``.  Activities without required inputs are
    unconstrained (realized = target); zero-coefficient inputs are absent
    from ``K`` by construction.  The returned arrays never carry ±inf.
    """
    available = np.asarray(available, dtype=np.float64)
    coefficient = np.asarray(coefficient, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    indices = np.asarray(activity_index)
    if available.ndim != 1 or coefficient.ndim != 1 or target.ndim != 1:
        raise ValueError("produce_leontief inputs must be one-dimensional")
    k_count = available.size
    activity_total = target.size
    if coefficient.size != k_count or indices.size != k_count:
        raise ValueError("available/coefficient/activity_index lengths must all match")
    if not np.issubdtype(indices.dtype, np.integer):
        raise ValueError("activity_index must be an integer array")
    if k_count:
        if int(indices.min()) < 0 or int(indices.max()) >= activity_total:
            raise ValueError("activity_index values must lie in [0, P)")
    if not np.all(np.isfinite(available)) or bool(np.any(available < 0.0)):
        raise ValueError("available must be finite and non-negative")
    if not np.all(np.isfinite(target)) or bool(np.any(target < 0.0)):
        raise ValueError("target must be finite and non-negative")
    if not np.all(np.isfinite(coefficient)) or bool(np.any(coefficient <= 0.0)):
        raise ValueError("coefficient must be finite and positive")
    if k_count == 0:
        return target.copy(), np.zeros(0, dtype=np.float64)
    rows = indices.astype(np.intp)
    ratio = available / coefficient
    segment_min = np.full(activity_total, np.inf, dtype=np.float64)
    np.minimum.at(segment_min, rows, ratio)
    realized = np.minimum(target, segment_min)
    used = coefficient * realized[rows]
    return realized, used


__all__ = [
    "MATERIAL_NETWORK_VERSION",
    "MaterialNetwork",
    "build_material_network",
    "compile_material_network",
    "produce_leontief",
]
