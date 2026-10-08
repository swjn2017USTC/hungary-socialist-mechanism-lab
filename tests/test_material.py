"""P02 material kernel behaviour: hand-computable bottleneck fixtures.

Every fixture here builds a tiny real network with
``compile_material_network`` and advances it with the real ``tick_material``
kernel (no engine mocks).  Defaults mirror the plan §8 fixture recipe:
admin price 1, ``wage_rate`` 1, ``utilization`` 1, ample cash/labor/handling,
``service_split=(1, 0, 0)`` (so with ``transport_per_unit=x`` a delivered good
draws exactly ``x`` services), no trade, no investment, no private plots, no
over-order/hoarding unless a test turns them on.

The tiny commodity axes intentionally drop ``construction`` (and sometimes
``capital_goods``) where a fixture does not need them.  Every declared
investment commodity still gets an investment demand cell for each productive
organization; a commodity with no declared supplier simply receives zero
delivery (an observable backlog), and the installation path resolves the
owning project from the demand cell's destination.  Declaring only the
commodities a fixture actually routes is the documented reduction the network
compiler supports; it is not a mocked engine.
"""

from __future__ import annotations

import numpy as np
import pytest

from hsm_lab.contract.material import (
    INTERMEDIATE8_COMMODITY_IDS,
    P02_COMMODITY_SPECS,
    PURPOSE_CODES,
    CellOwnerKind,
    CommoditySpec,
    HouseholdInitial,
    InputCoefficient,
    MaterialInitialConditions,
    MaterialInitialRecipe,
    MaterialParameters,
    MaterialRouteSpec,
    OrganizationRecipe,
    OrganizationSpec,
    OrganizationType,
    OutputCoefficient,
    PrivatePlotRecipe,
    RoutePurpose,
    StockCellRef,
    TechnologySpec,
    TradeParameters,
)
from hsm_lab.contract.schemas import OutputPolicy, ScenarioSpec
from hsm_lab.engine import accounting as accounting_module
from hsm_lab.engine.material import tick_material
from hsm_lab.engine.network import compile_material_network
from hsm_lab.engine.state import (
    MaterialForcing,
    MaterialState,
    build_material_prices,
    capture_material_stocks,
    initialize_material,
)

FIXTURE_FORCING_PACK = "data/fixtures/p02_material_synthetic_pack.json"
START = "1957Q1"

# The canonical tiny axis: Intermediate-8 minus ``construction`` (see module
# docstring).  Order matches the fixed Intermediate-8 order.
TINY_COMMODITIES = tuple(c for c in INTERMEDIATE8_COMMODITY_IDS if c != "construction")

# Fixtures with no capital-goods producer must not declare capital_goods:
# investment demand cells for a producer would then have no supplier, and the
# kernel's installation pass requires every investment demand to carry a buyer
# org.  Dropping the commodity keeps the axis honest for these fixtures.
NO_CAPITAL_COMMODITIES = tuple(c for c in TINY_COMMODITIES if c != "capital_goods")


# ---------------------------------------------------------------------------
# fixture construction helpers
# ---------------------------------------------------------------------------


def tech(
    technology_id: str,
    inputs: tuple[tuple[str, float], ...] = (),
    outputs: tuple[tuple[str, str, float], ...] = (),
) -> TechnologySpec:
    return TechnologySpec(
        technology_id=technology_id,
        inputs=[
            InputCoefficient(commodity_id=c, stage="standard", coefficient=k)
            for c, k in inputs
        ],
        outputs=[
            OutputCoefficient(commodity_id=c, stage=s, coefficient=k)
            for c, s, k in outputs
        ],
    )


def org(
    organization_id: int, org_type: OrganizationType, region: str = "R0", **kw
) -> OrganizationSpec:
    base: dict = {
        "organization_id": organization_id,
        "type": org_type,
        "region_id": region,
        "strategic_importance": kw.pop("strategic_importance", 0.5),
        "initial_bailout_expectation": kw.pop("initial_bailout_expectation", 0.0),
    }
    base.update(kw)
    return OrganizationSpec(**base)


def producer(
    organization_id: int,
    technology_id: str,
    region: str = "R0",
    capacity: float = 10.0,
    cash: float = 100000.0,
    bank_id: int = 0,
) -> OrganizationSpec:
    return org(
        organization_id,
        OrganizationType.INDUSTRIAL_SOE,
        region,
        technology_id=technology_id,
        capacity=capacity,
        labor_available=capacity,
        labor_per_activity=1.0,
        initial_cash=cash,
        bank_id=bank_id,
    )


def hub(
    organization_id: int, region: str = "R0", handling: float = 1_000_000.0
) -> OrganizationSpec:
    return org(
        organization_id,
        OrganizationType.WHOLESALE_PROCURMENT,
        region,
        handling_capacity=handling,
        initial_cash=100000.0,
        bank_id=0,
    )


def retail(
    organization_id: int, region: str = "R0", handling: float = 1_000_000.0
) -> OrganizationSpec:
    return org(
        organization_id,
        OrganizationType.RETAIL,
        region,
        handling_capacity=handling,
        initial_cash=100000.0,
        bank_id=0,
    )


def transport(organization_id: int, region: str = "R0", capacity: float = 1.0) -> OrganizationSpec:
    return org(
        organization_id,
        OrganizationType.TRANSPORT,
        region,
        technology_id="freight_transport",
        capacity=capacity,
        labor_available=capacity,
        labor_per_activity=1.0,
        initial_cash=100000.0,
        bank_id=0,
    )


def bank(organization_id: int = 0, region: str = "R0") -> OrganizationSpec:
    return org(organization_id, OrganizationType.BANK, region)


def idle_source_tech(technology_id: str, commodity: str, stage: str = "standard") -> TechnologySpec:
    """A producer that never actually produces (its only input is unsupplied).

    Used to model an opening-stock "seller": the fixture pins its output
    stock directly, and its own activity is starved because no producer of
    ``durable_goods`` exists in these tiny networks.
    """
    return tech(technology_id, inputs=(("durable_goods", 1.0),), outputs=((commodity, stage, 1.0),))


def default_params(**overrides) -> MaterialParameters:
    base: dict = {
        "prices": [1.0] * 8,
        "food_raw_price": 1.0,
        "desired_per_person": [0.0] * 8,
        "utilization": 1.0,
        "service_split": [1.0, 0.0, 0.0],
        "overorder_strength": 0.0,
        "hoarding_quarters": 0.0,
        "wage_rate": 1.0,
        "hunger_base": 0.0,
        "hunger_bailout": 0.0,
        "hunger_shortage": 0.0,
        "transport_per_unit": 0.0,
        "farm_seasonal_factors": [1.0, 1.0, 1.0, 1.0],
        "housing_request_per_person": 0.0,
        "trade": TradeParameters(
            cmea_desired_imports=[0.0] * 8,
            convertible_desired_imports=[0.0] * 8,
            cmea_export_demands=[0.0] * 8,
            convertible_export_demands=[0.0] * 8,
            convertible_opening_reserve=0.0,
            convertible_loan_limit=0.0,
        ),
    }
    base.update(overrides)
    return MaterialParameters(**base)


class Fixture:
    """A compiled tiny material economy plus its immutable scenario."""

    def __init__(
        self,
        orgs: list[OrganizationSpec],
        technologies: list[TechnologySpec],
        *,
        region_ids: tuple[str, ...] = ("R0",),
        commodities: tuple[str, ...] = TINY_COMMODITIES,
        parameters: MaterialParameters | None = None,
        households: list[tuple[int, float, float]] | None = None,
        household_cash: float = 0.0,
        ticks: int = 3,
        routes: list[MaterialRouteSpec] | None = None,
        plot_participating: np.ndarray | None = None,
    ) -> None:
        self.parameters = parameters if parameters is not None else default_params()
        self.commodities = tuple(commodities)
        self.region_ids = tuple(region_ids)
        self.routes = tuple(routes) if routes is not None else None
        specs = [s for s in P02_COMMODITY_SPECS if s.id in self.commodities]
        self._commodity_specs: tuple[CommoditySpec, ...] = tuple(specs)
        household_rows = households or [(0, 1.0, 1.0)]
        weight = np.array([row[1] for row in household_rows], dtype=np.float64)
        size = np.array([row[2] for row in household_rows], dtype=np.float64)
        region = np.array([row[0] for row in household_rows], dtype=np.int32)
        region_persons = np.zeros(len(region_ids), dtype=np.float64)
        for r, w, s in household_rows:
            region_persons[r] += w * s
        self.recipe = MaterialInitialRecipe(household_cash=household_cash)
        self.initial = MaterialInitialConditions(
            scenario_id="p02_tiny",
            region_ids=self.region_ids,
            commodity_ids=self.commodities,
            seed=1729,
            stochastic=False,
            households=HouseholdInitial(
                household_id=np.arange(weight.size, dtype=np.int64),
                region=region,
                weight=weight,
                size=size,
                plot_participating=(
                    np.zeros(weight.size, dtype=bool)
                    if plot_participating is None
                    else np.asarray(plot_participating, dtype=bool)
                ),
            ),
            organizations=tuple(orgs),
            technologies=tuple(technologies),
            routes=self.routes,
            plot_recipe=PrivatePlotRecipe(),
            equivalent_persons=float(region_persons.sum()),
            region_equivalent_persons=region_persons,
            parameters=self.parameters,
            initial_recipe=self.recipe,
        )
        self.network = compile_material_network(
            self.initial,
            self.initial.technologies,
            self.routes,
            self._commodity_specs,
            self.region_ids,
            self.initial.plot_recipe,
        )
        self.spec = ScenarioSpec(
            scenario_id="p02_tiny",
            start=START,
            ticks=ticks,
            households=int(weight.size),
            region_ids=list(self.region_ids),
            commodities=list(self.commodities),
            seed=1729,
            stochastic=False,
            output_policy=OutputPolicy.ENSEMBLE_COMPACT,
            forcing_ids=[],
            initial_ids=[],
            parameter_ids=[],
            kind="material",
            material_parameters=self.parameters,
            material_initial=self.recipe,
            organization_recipe=OrganizationRecipe(profile="p02_100"),
            technologies=list(technologies),
            routes=list(routes) if routes is not None else None,
            forcing_pack=FIXTURE_FORCING_PACK,
        )
        self.state: MaterialState = initialize_material(self.spec, self.initial, self.network)
        self.prices = build_material_prices(self.parameters)

    # -- addressing -----------------------------------------------------
    def cell(
        self,
        kind: str,
        owner_id: int,
        region: int,
        pool: str,
        commodity: str,
        stage: str = "standard",
    ) -> int:
        return self.network.cell_index[(kind, owner_id, region, pool, commodity, stage)]

    def g(self, commodity: str) -> int:
        return self.network.commodity_ids.index(commodity)

    def k_of(self, cell_row: int) -> int:
        match = np.flatnonzero(np.asarray(self.network.input_cell) == cell_row)
        assert match.size == 1, f"input cell {cell_row} is not a single K row"
        return int(match[0])

    def edge(self, source: int, destination: int) -> int:
        src = np.asarray(self.network.edge_source_cell)
        dst = np.asarray(self.network.edge_destination_cell)
        match = np.flatnonzero((src == source) & (dst == destination))
        assert match.size >= 1, f"no edge {source}->{destination}"
        return int(match[0])

    # -- ticking --------------------------------------------------------
    def forcing(
        self,
        ticks: int,
        *,
        global_usd_rate: float = 0.0,
        official_fx: float | None = None,
        cmea_energy_price: float | None = None,
    ) -> MaterialForcing:
        from hsm_lab.contract.schemas import Quarter

        start = Quarter.parse(START)
        return MaterialForcing(
            quarters=[str(start.advance(i)) for i in range(ticks)],
            oil_price=np.full(ticks, self.parameters.world_oil_reference),
            global_usd_rate=np.full(ticks, global_usd_rate),
            official_fx=np.full(ticks, np.nan if official_fx is None else official_fx),
            cmea_energy_price=np.full(
                ticks, np.nan if cmea_energy_price is None else cmea_energy_price
            ),
            segment=["synthetic_warmup"] * ticks,
            input_artifact_hashes={},
        )

    def tick(self, ticks: int = 3) -> list:
        forcing = self.forcing(ticks)
        output = []
        for _ in range(ticks):
            output.append(tick_material(self.state, forcing, self.parameters, self.network))
        return output

    def check(self, opening, flows) -> object:
        return accounting_module.check_material_invariants(
            opening, self.state, flows, self.parameters, self.network
        )


# ---------------------------------------------------------------------------
# Bottleneck fixture 1: energy lag propagates through opening stocks
# ---------------------------------------------------------------------------


def _energy_lag_fixture(*, capital_buffer: float = 0.0) -> Fixture:
    energy = producer(1, "energy_generation", capacity=8.0)
    rawp = producer(2, "raw_materials_production", capacity=8.0)
    capp = producer(3, "capital_goods_production", capacity=8.0)
    technologies = [
        tech(
            "energy_generation",
            inputs=(("capital_goods", 0.01),),
            outputs=(("energy", "standard", 1.0),),
        ),
        tech(
            "raw_materials_production",
            inputs=(("energy", 1.0),),
            outputs=(("raw_materials", "standard", 1.0),),
        ),
        tech(
            "capital_goods_production",
            inputs=(("raw_materials", 1.0),),
            outputs=(("capital_goods", "standard", 1.0),),
        ),
    ]
    fixture = Fixture([bank(0), energy, rawp, capp], technologies)
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "output", "energy")] = 3.0
    if capital_buffer:
        fixture.state.stock_value[
            fixture.cell("organization", 3, 0, "input", "raw_materials")
        ] = capital_buffer
    return fixture


def test_energy_bottleneck_propagates_with_opening_stock_lag() -> None:
    fixture = _energy_lag_fixture()
    flows = fixture.tick(2)

    energy_demand = fixture.k_of(fixture.cell("organization", 2, 0, "input", "energy"))
    raw_demand = fixture.k_of(fixture.cell("organization", 3, 0, "input", "raw_materials"))

    # t0: the raw producer orders 8 energy, only 3 exist, so only 3 is used.
    assert flows[0].desired[energy_demand] == pytest.approx(8.0)
    assert flows[0].ordered[energy_demand] == pytest.approx(8.0)
    assert flows[0].allocated[energy_demand] == pytest.approx(3.0)
    assert flows[0].delivered[energy_demand] == pytest.approx(3.0)
    assert flows[0].used[energy_demand] == pytest.approx(3.0)
    assert flows[0].desired[energy_demand] - flows[0].delivered[energy_demand] == pytest.approx(5.0)
    # the energy seller's opening stock is fully drained
    assert fixture.state.stock_value[
        fixture.cell("organization", 1, 0, "output", "energy")
    ] == pytest.approx(0.0)
    assert flows[0].activity_realized[1] == pytest.approx(3.0)  # raw
    assert flows[0].activity_realized[2] == pytest.approx(0.0)  # capital

    # t1: last quarter's raw output is the only source the capital producer
    # sees; this quarter's new energy cannot be used before production runs.
    assert flows[1].activity_realized[2] == pytest.approx(3.0)
    assert flows[1].delivered[raw_demand] == pytest.approx(3.0)

    # a 2-unit opening buffer lets capital produce immediately at t0
    buffered = _energy_lag_fixture(capital_buffer=2.0)
    buffered_flows = buffered.tick(1)
    raw_demand_b = buffered.k_of(buffered.cell("organization", 3, 0, "input", "raw_materials"))
    assert buffered_flows[0].activity_realized[2] == pytest.approx(2.0)
    assert buffered_flows[0].delivered[raw_demand_b] == pytest.approx(0.0)
    assert buffered_flows[0].used[raw_demand_b] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Bottleneck fixture 2: raw shortage is independent of abundant energy
# ---------------------------------------------------------------------------


def _raw_bottleneck_fixture(*, energy_opening: float) -> Fixture:
    energy = producer(1, "energy_generation")
    raw = producer(2, "raw_materials_production")
    consumer = producer(3, "consumer_goods_production")
    technologies = [
        idle_source_tech("energy_generation", "energy"),
        idle_source_tech("raw_materials_production", "raw_materials"),
        tech(
            "consumer_goods_production",
            inputs=(("energy", 0.2), ("raw_materials", 0.5)),
            outputs=(("consumer_goods", "standard", 1.0),),
        ),
    ]
    fixture = Fixture(
        [bank(0), energy, raw, consumer], technologies, commodities=NO_CAPITAL_COMMODITIES
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[
        fixture.cell("organization", 1, 0, "output", "energy")
    ] = energy_opening
    fixture.state.stock_value[fixture.cell("organization", 2, 0, "output", "raw_materials")] = 2.0
    return fixture


def test_raw_material_bottleneck_is_independent_of_energy() -> None:
    fixture = _raw_bottleneck_fixture(energy_opening=100.0)
    flows = fixture.tick(1)[0]
    energy_cell = fixture.cell("organization", 3, 0, "input", "energy")
    raw_cell = fixture.cell("organization", 3, 0, "input", "raw_materials")
    energy_k = fixture.k_of(energy_cell)
    raw_k = fixture.k_of(raw_cell)

    assert flows.activity_realized[2] == pytest.approx(4.0)
    assert flows.used[energy_k] == pytest.approx(0.8)
    assert flows.used[raw_k] == pytest.approx(2.0)
    assert flows.delivered[energy_k] == pytest.approx(2.0)
    assert fixture.state.stock_value[energy_cell] == pytest.approx(1.2)
    # The source keeps everything it did not ship: 100 - 2 delivered = 98.
    assert fixture.state.stock_value[
        fixture.cell("organization", 1, 0, "output", "energy")
    ] == pytest.approx(98.0)
    # 100 available - 0.8 used = 99.2 unused; raw is exhausted, shortfall 6.
    assert 100.0 - flows.used[energy_k] == pytest.approx(99.2)
    assert flows.desired[raw_k] - flows.delivered[raw_k] == pytest.approx(3.0)
    assert flows.activity_target[2] * 1.0 - flows.activity_realized[2] == pytest.approx(6.0)

    # With no energy the activity cannot run, and the delivered raw is never
    # consumed (it stays in the buyer's input cell).
    starved = _raw_bottleneck_fixture(energy_opening=0.0)
    starved_flows = starved.tick(1)[0]
    raw_cell_s = starved.cell("organization", 3, 0, "input", "raw_materials")
    assert starved_flows.activity_realized[2] == pytest.approx(0.0)
    assert starved_flows.used[starved.k_of(raw_cell_s)] == pytest.approx(0.0)
    assert starved.state.stock_value[raw_cell_s] == pytest.approx(2.0)
    assert starved.state.stock_value[
        starved.cell("organization", 2, 0, "output", "raw_materials")
    ] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Bottleneck fixture 3: food processing + distribution delay
# ---------------------------------------------------------------------------


def route(
    source_org: int,
    source_pool: str,
    source_commodity: str,
    source_stage: str,
    dest_org: int,
    dest_pool: str,
    dest_commodity: str,
    dest_stage: str,
    purpose: RoutePurpose,
    weight: float = 1.0,
) -> MaterialRouteSpec:
    return MaterialRouteSpec(
        source=StockCellRef(
            owner_kind=CellOwnerKind.ORGANIZATION,
            organization_id=source_org,
            pool=source_pool,  # type: ignore[arg-type]
            commodity_id=source_commodity,
            stage=source_stage,  # type: ignore[arg-type]
        ),
        destination=StockCellRef(
            owner_kind=CellOwnerKind.ORGANIZATION,
            organization_id=dest_org,
            pool=dest_pool,  # type: ignore[arg-type]
            commodity_id=dest_commodity,
            stage=dest_stage,  # type: ignore[arg-type]
        ),
        purpose=purpose,
        weight=weight,
    )


def _food_chain_fixture(*, processor_capacity: float = 10.0) -> Fixture:
    processor = producer(1, "food_processing", capacity=processor_capacity)
    wholesale = hub(2)
    shop = retail(3)
    technologies = [
        TechnologySpec(
            technology_id="food_processing",
            inputs=[InputCoefficient(commodity_id="food", stage="raw", coefficient=1.25)],
            outputs=[OutputCoefficient(commodity_id="food", stage="ready", coefficient=1.0)],
        ),
    ]
    parameters = default_params(desired_per_person=[0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    # The default nearest-hub graph builds the processor -> hub -> retail chain
    # and the retail -> household edges; households are funded by real wages.
    fixture = Fixture(
        [bank(0), processor, wholesale, shop],
        technologies,
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 10.0)],
        household_cash=1000.0,
        ticks=3,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[
        fixture.cell("organization", 1, 0, "input", "food", "raw")
    ] = 10.0
    return fixture


def test_food_processing_and_distribution_delay() -> None:
    fixture = _food_chain_fixture()
    flows = fixture.tick(3)
    food_g = fixture.g("food")
    processor_cell = fixture.cell("organization", 1, 0, "output", "food", "ready")
    hub_cell = fixture.cell("organization", 2, 0, "wholesale", "food", "ready")
    shop_cell = fixture.cell("organization", 3, 0, "retail", "food", "ready")
    to_hub = fixture.edge(processor_cell, hub_cell)
    to_shop = fixture.edge(hub_cell, shop_cell)

    # t0: the processor turns its 10 opening raw into 8 ready food; the chain
    # has not moved it yet (production lands after this quarter's allocation).
    assert flows[0].activity_realized[0] == pytest.approx(8.0)
    assert flows[0].edge_delivered[to_hub] == pytest.approx(0.0)
    assert flows[0].household_realized[0, food_g] == pytest.approx(0.0)
    assert fixture.state.stock_value[
        fixture.cell("organization", 1, 0, "input", "food", "raw")
    ] == pytest.approx(0.0)

    # t1: the hub collects the 8; retail is still empty and households wait.
    assert flows[1].edge_delivered[to_hub] == pytest.approx(8.0)
    assert flows[1].edge_delivered[to_shop] == pytest.approx(0.0)
    assert flows[1].household_realized[0, food_g] == pytest.approx(0.0)

    # t2: retail finally receives it; households get 8 of their desired 10.
    assert flows[2].edge_delivered[to_shop] == pytest.approx(8.0)
    assert flows[2].household_realized[0, food_g] == pytest.approx(8.0)
    assert flows[2].household_availability_unmet[0, food_g] == pytest.approx(2.0)


def test_zero_processing_capacity_blocks_ready_food() -> None:
    fixture = _food_chain_fixture()
    # A capacity/labor wipe-out (structural control): the activity cannot run
    # even with 10 raw food on hand, and no downstream stock appears.
    fixture.state.organization_capacity[1] = 0.0
    fixture.state.organization_labor_available[1] = 0.0
    flows = fixture.tick(2)
    raw_cell = fixture.cell("organization", 1, 0, "input", "food", "raw")
    hub_cell = fixture.cell("organization", 2, 0, "wholesale", "food", "ready")
    assert flows[0].activity_realized[0] == pytest.approx(0.0)
    assert fixture.state.stock_value[raw_cell] == pytest.approx(10.0)
    assert fixture.state.stock_value[hub_cell] == pytest.approx(0.0)
    assert flows[1].edge_delivered[
        fixture.edge(fixture.cell("organization", 1, 0, "output", "food", "ready"), hub_cell)
    ] == pytest.approx(0.0)
    assert flows[1].household_realized[0, fixture.g("food")] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Bottleneck fixture 4: transport reservation never delivers or charges
# ---------------------------------------------------------------------------


def _transport_fixture(*, transport_opening: float) -> Fixture:
    seller = producer(1, "energy_generation", region="R1")  # cross-region seller
    wholesale = hub(2, region="R0")  # pinned hub region
    shop = retail(3, region="R0")
    hauler = transport(4, region="R0", capacity=1.0)
    technologies = [
        idle_source_tech("energy_generation", "energy"),
        tech(
            "freight_transport",
            inputs=(("durable_goods", 1.0),),
            outputs=(("services_transport", "standard", 1.0),),
        ),
    ]
    parameters = default_params(
        desired_per_person=[0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        transport_per_unit=0.1,
    )
    fixture = Fixture(
        [bank(0), seller, wholesale, shop, hauler],
        technologies,
        region_ids=("R0", "R1"),
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 25.0)],
        household_cash=1000.0,
        ticks=1,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 1, "output", "energy")] = 10.0
    if transport_opening:
        fixture.state.stock_value[
            fixture.cell("organization", 4, 0, "input", "durable_goods")
        ] = transport_opening
    return fixture


def _transport_hub_edge(fixture: Fixture) -> int:
    seller_cell = fixture.cell("organization", 1, 1, "output", "energy")
    hub_cell = fixture.cell("organization", 2, 0, "wholesale", "energy")
    return fixture.edge(seller_cell, hub_cell)


def test_transport_reservations_do_not_deliver_or_charge() -> None:
    frozen = _transport_fixture(transport_opening=0.0)
    edge = _transport_hub_edge(frozen)
    seller_cell = frozen.cell("organization", 1, 1, "output", "energy")
    hub_cell = frozen.cell("organization", 2, 0, "wholesale", "energy")
    hub_cash_open = float(frozen.state.organization_cash[2])
    flows = frozen.tick(1)[0]

    assert flows.edge_allocated[edge] == pytest.approx(10.0)
    assert flows.edge_delivered[edge] == pytest.approx(0.0)
    assert flows.edge_service_used[edge] == pytest.approx(0.0)
    assert flows.edge_service_fee[edge] == pytest.approx(0.0)
    assert frozen.state.stock_value[seller_cell] == pytest.approx(10.0)
    assert frozen.state.stock_value[hub_cell] == pytest.approx(0.0)
    # wages move cash, but no goods/freight leg is charged for a reservation
    assert float(frozen.state.organization_cash[2]) == pytest.approx(hub_cash_open - 0.0)

    moving = _transport_fixture(transport_opening=1.0)
    edge = _transport_hub_edge(moving)
    seller_cell = moving.cell("organization", 1, 1, "output", "energy")
    hub_cell = moving.cell("organization", 2, 0, "wholesale", "energy")
    wage = float(moving.parameters.wage_rate)
    seller_wage = wage * float(moving.state.organization_labor_available[1])
    hauler_wage = wage * float(moving.state.organization_labor_available[4])
    hauler_cash_open = float(moving.state.organization_cash[4])
    seller_cash_open = float(moving.state.organization_cash[1])
    hub_cash_open = float(moving.state.organization_cash[2])
    flows = moving.tick(1)[0]

    assert flows.edge_allocated[edge] == pytest.approx(10.0)
    assert flows.edge_delivered[edge] == pytest.approx(10.0)
    assert flows.edge_service_used[edge] == pytest.approx(1.0)
    assert flows.edge_service_fee[edge] == pytest.approx(1.0)
    assert moving.state.stock_value[seller_cell] == pytest.approx(0.0)
    # the trader buyer keeps the 10 goods it does not consume this quarter
    assert moving.state.stock_value[hub_cell] == pytest.approx(10.0)
    # seller is paid 10 for the goods, transport is paid the 1 fee
    assert flows.organization_sales_receipts[1] == pytest.approx(10.0)
    assert flows.organization_sales_receipts[4] == pytest.approx(1.0)
    assert flows.organization_purchases[2] == pytest.approx(11.0)
    assert float(moving.state.organization_cash[1]) - seller_cash_open == pytest.approx(
        10.0 - seller_wage
    )
    assert float(moving.state.organization_cash[4]) - hauler_cash_open == pytest.approx(
        1.0 - hauler_wage
    )
    assert float(moving.state.organization_cash[2]) - hub_cash_open == pytest.approx(-11.0)


# ---------------------------------------------------------------------------
# Bottleneck fixture 5: regional distribution shortage with national surplus
# ---------------------------------------------------------------------------


def test_regional_distribution_shortage_with_national_surplus() -> None:
    parameters = default_params(desired_per_person=[0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    # A real wage-paying actor funds household budgets (no invented income).
    worker = producer(2, "energy_generation", capacity=10.0)
    fixture = Fixture(
        [bank(0), retail(1, region="R0"), worker],
        [idle_source_tech("energy_generation", "energy")],
        region_ids=("R0", "R1"),
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 5.0), (1, 1.0, 5.0)],
        household_cash=1000.0,
        ticks=1,
    )
    food_g = fixture.g("food")
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "retail", "food", "ready")] = 10.0
    flows = fixture.tick(1)[0]

    assert flows.household_realized[0, food_g] == pytest.approx(5.0)
    assert flows.household_realized[1, food_g] == pytest.approx(0.0)
    assert flows.household_availability_unmet[1, food_g] == pytest.approx(5.0)
    assert fixture.state.stock_value[
        fixture.cell("organization", 1, 0, "retail", "food", "ready")
    ] == pytest.approx(5.0)
    assert fixture.state.stock_value[
        fixture.cell("organization", 1, 1, "retail", "food", "ready")
    ] == pytest.approx(0.0)
    # national availability (10) equals national desired (10): no regional
    # averaging, no raw food substitution.
    total_desired = flows.household_desired[0, food_g] + flows.household_desired[1, food_g]
    assert total_desired == pytest.approx(10.0)


def test_household_retail_rationing_matches_availability() -> None:
    parameters = default_params(desired_per_person=[0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    worker = producer(2, "energy_generation", capacity=10.0)
    fixture = Fixture(
        [bank(0), retail(1, region="R0"), worker],
        [idle_source_tech("energy_generation", "energy")],
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 10.0)],
        household_cash=1000.0,
        ticks=1,
    )
    food_g = fixture.g("food")
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "retail", "food", "ready")] = 8.0
    flows = fixture.tick(1)[0]

    assert flows.household_desired[0, food_g] == pytest.approx(10.0)
    assert flows.household_realized[0, food_g] == pytest.approx(8.0)
    assert flows.household_availability_unmet[0, food_g] == pytest.approx(2.0)
    assert flows.retail_sales[0, food_g] == pytest.approx(8.0)
    assert flows.retail_unmet[0, food_g] == pytest.approx(2.0)
    assert fixture.state.stock_value[
        fixture.cell("organization", 1, 0, "retail", "food", "ready")
    ] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Shortage toggles: over-order crowds out, hoarding does not unconditionally
# add orders, and both are real request/competition changes
# ---------------------------------------------------------------------------


def _shared_source_fixture(
    *, overorder: float, hoarding: float, a_expectation: float, a_opening: float = 0.0
) -> Fixture:
    source = producer(1, "energy_generation", capacity=1.0)
    a = producer(2, "consumer_goods_production", capacity=4.0)
    b = producer(3, "consumer_goods_production", capacity=8.0)
    technologies = [
        idle_source_tech("energy_generation", "energy"),
        tech(
            "consumer_goods_production",
            inputs=(("energy", 1.0),),
            outputs=(("consumer_goods", "standard", 1.0),),
        ),
    ]
    parameters = default_params(overorder_strength=overorder, hoarding_quarters=hoarding)
    fixture = Fixture(
        [bank(0), source, a, b],
        technologies,
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "output", "energy")] = 12.0
    if a_opening:
        fixture.state.stock_value[fixture.cell("organization", 2, 0, "input", "energy")] = a_opening
    fixture.state.organization_shortage_expectation[2] = a_expectation
    return fixture


def test_overordering_crowds_out_and_accumulates_inventory() -> None:
    baseline = _shared_source_fixture(overorder=0.0, hoarding=0.0, a_expectation=0.0)
    flows = baseline.tick(1)[0]
    a_k = baseline.k_of(baseline.cell("organization", 2, 0, "input", "energy"))
    b_k = baseline.k_of(baseline.cell("organization", 3, 0, "input", "energy"))
    assert flows.delivered[a_k] == pytest.approx(4.0)
    assert flows.delivered[b_k] == pytest.approx(8.0)
    assert flows.used[a_k] == pytest.approx(4.0)
    assert baseline.state.stock_value[
        baseline.cell("organization", 2, 0, "input", "energy")
    ] == pytest.approx(0.0)
    assert flows.activity_realized[2] == pytest.approx(8.0)

    crowded = _shared_source_fixture(overorder=1.0, hoarding=0.0, a_expectation=1.0)
    flows = crowded.tick(1)[0]
    a_k = crowded.k_of(crowded.cell("organization", 2, 0, "input", "energy"))
    b_k = crowded.k_of(crowded.cell("organization", 3, 0, "input", "energy"))
    assert flows.desired[a_k] == pytest.approx(4.0)  # real need unchanged
    assert flows.ordered[a_k] == pytest.approx(8.0)  # expectation inflates the order
    assert flows.delivered[a_k] == pytest.approx(6.0)  # shared 12 split 8:8
    assert flows.delivered[b_k] == pytest.approx(6.0)
    assert flows.used[a_k] == pytest.approx(4.0)
    assert crowded.state.stock_value[
        crowded.cell("organization", 2, 0, "input", "energy")
    ] == pytest.approx(2.0)
    assert flows.activity_realized[2] == pytest.approx(6.0)  # B is crowded out

    # hoarding does not add an order when stock already covers desired+hoard
    covered = _shared_source_fixture(overorder=0.0, hoarding=0.5, a_expectation=0.0, a_opening=6.0)
    flows = covered.tick(1)[0]
    a_k = covered.k_of(covered.cell("organization", 2, 0, "input", "energy"))
    assert flows.ordered[a_k] == pytest.approx(0.0)
    assert flows.delivered[a_k] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Bottleneck fixture 7: allocation priority squeezes consumer production
# ---------------------------------------------------------------------------

INVESTMENT_PRIORITY_COMMODITIES = ("capital_goods", "consumer_goods", "construction")
_INVESTMENT_PURPOSE = PURPOSE_CODES[RoutePurpose.INVESTMENT]
_HOUSING_PURPOSE = PURPOSE_CODES[RoutePurpose.HOUSING]


def _org_activity(fixture: Fixture, org_row: int) -> int:
    match = np.flatnonzero(np.asarray(fixture.network.activity_org_index) == org_row)
    assert match.size == 1, f"organization row {org_row} is not one activity"
    return int(match[0])


def _investment_demand(fixture: Fixture, org_id: int, commodity: str) -> int:
    purpose = np.asarray(fixture.network.demand_purpose)
    destination = np.asarray(fixture.network.demand_cell)
    owner = np.asarray(fixture.network.cell_owner_id)
    cell_commodity = np.asarray(fixture.network.cell_commodity)
    g = fixture.g(commodity)
    match = [
        int(demand)
        for demand in np.flatnonzero(purpose == _INVESTMENT_PURPOSE)
        if int(cell_commodity[destination[demand]]) == g
        and int(owner[destination[demand]]) == org_id
    ]
    assert len(match) == 1, f"expected one {commodity} investment demand for org {org_id}"
    return match[0]


def _housing_demand(fixture: Fixture, region: int = 0) -> int:
    purpose = np.asarray(fixture.network.demand_purpose)
    match = np.flatnonzero(purpose == _HOUSING_PURPOSE)
    assert match.size > region, "no housing demand for that region"
    return int(match[region])


def _weighted(fixture: Fixture, values: np.ndarray) -> float:
    return float(np.sum(np.asarray(fixture.state.household_weight) * np.asarray(values)))


def _assert_gate(fixture: Fixture, opening, flows) -> None:
    """The same material/finance gate the runner applies after every tick."""
    summary = fixture.check(opening, flows)
    assert summary.max_material_tolerance_ratio <= 1.0
    assert summary.max_finance_tolerance_ratio <= 1.0


def _tick_with_gate(fixture: Fixture, ticks: int) -> list:
    """Advance one quarter at a time, gating each against its own opening.

    The gate compares the captured opening with the CLOSING state, so it cannot
    be deferred across several ticks.
    """
    flows = []
    forcing = fixture.forcing(ticks)
    for _ in range(ticks):
        opening = capture_material_stocks(fixture.state)
        flow = tick_material(fixture.state, forcing, fixture.parameters, fixture.network)
        _assert_gate(fixture, opening, flow)
        flows.append(flow)
    return flows


def _investment_priority_fixture(order: str) -> Fixture:
    """Plan §8 case 7.

    A capital seller opens with 10 units.  One consumer producer wants them
    twice: as the production input of a target-10 activity (``a_capital = 1``)
    and as the capital leg of an already-approved 40-unit project
    (``capacity_capital_goods_per_unit = .25``, 10 construction units staged
    as WIP).  The allocation tier order alone decides who gets the 10 units.

    The construction producer keeps the project's construction leg supplied;
    a declared investment commodity may also be left unsupplied (see the
    disconnected-investment regression below), in which case delivery is zero
    while the project owner is still resolved from the demand cell.
    """
    capital_source = producer(1, "capital_goods_production", capacity=1.0)
    consumer = producer(2, "consumer_goods_production", capacity=10.0)
    builder = producer(3, "building_construction", capacity=1.0)
    wholesale = hub(4)
    shop = retail(5)
    technologies = [
        tech(
            "capital_goods_production",
            inputs=(),
            outputs=(("capital_goods", "standard", 1.0),),
        ),
        tech(
            "consumer_goods_production",
            inputs=(("capital_goods", 1.0),),
            outputs=(("consumer_goods", "standard", 1.0),),
        ),
        tech(
            "building_construction",
            inputs=(),
            outputs=(("construction", "standard", 1.0),),
        ),
    ]
    parameters = default_params(
        desired_per_person=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
        allocation_order=order,
    )
    fixture = Fixture(
        [bank(0), capital_source, consumer, builder, wholesale, shop],
        technologies,
        commodities=INVESTMENT_PRIORITY_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 10.0)],
        household_cash=1000.0,
        ticks=3,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[
        fixture.cell("organization", 1, 0, "output", "capital_goods")
    ] = 10.0
    fixture.state.organization_project_approved[2] = 40.0
    fixture.state.organization_construction_wip[2] = 10.0
    fixture.state.stock_value[fixture.cell("project", 2, 0, "wip", "construction")] = 10.0
    return fixture


def test_investment_priority_squeezes_consumer_production() -> None:
    production = _investment_priority_fixture("production_first")
    consumer_org = 2
    consumer_activity = _org_activity(production, consumer_org)
    consumer_g = production.g("consumer_goods")
    inter = production.k_of(
        production.cell("organization", consumer_org, 0, "input", "capital_goods")
    )
    investment_capital = _investment_demand(production, consumer_org, "capital_goods")
    flows = _tick_with_gate(production, 3)

    # production_first: the intermediate input clears first, the project waits.
    assert flows[0].delivered[inter] == pytest.approx(10.0)
    assert flows[0].activity_realized[consumer_activity] == pytest.approx(10.0)
    assert flows[0].delivered[investment_capital] == pytest.approx(0.0)
    assert flows[0].organization_investment_completed[consumer_org] == pytest.approx(0.0)
    assert production.state.organization_capacity[consumer_org] == pytest.approx(10.0)
    assert production.state.organization_capital_wip[consumer_org] == pytest.approx(0.0)
    assert production.state.organization_construction_wip[consumer_org] == pytest.approx(10.0)
    assert production.state.organization_project_approved[consumer_org] == pytest.approx(40.0)
    # the ten consumer goods reach households only through the two-quarter
    # producer -> wholesale -> retail chain
    assert [
        _weighted(production, flow.household_realized[:, consumer_g]) for flow in flows
    ] == [pytest.approx(0.0), pytest.approx(0.0), pytest.approx(10.0)]

    investment = _investment_priority_fixture("investment_first")
    inv_activity = _org_activity(investment, consumer_org)
    inv_inter = investment.k_of(
        investment.cell("organization", consumer_org, 0, "input", "capital_goods")
    )
    inv_capital = _investment_demand(investment, consumer_org, "capital_goods")
    inv_construction = _investment_demand(investment, consumer_org, "construction")
    inv_flows = _tick_with_gate(investment, 3)

    # investment_first: the project takes all 10, the activity starves, and
    # the completed project raises capacity by exactly 40 with both WIP at 0.
    assert inv_flows[0].delivered[inv_inter] == pytest.approx(0.0)
    assert inv_flows[0].activity_realized[inv_activity] == pytest.approx(0.0)
    assert inv_flows[0].delivered[inv_capital] == pytest.approx(10.0)
    assert inv_flows[0].used[inv_capital] == pytest.approx(10.0)
    assert inv_flows[0].used[inv_construction] == pytest.approx(10.0)
    assert inv_flows[0].organization_investment_completed[consumer_org] == pytest.approx(40.0)
    assert investment.state.organization_capacity[consumer_org] == pytest.approx(50.0)
    assert investment.state.organization_capital_wip[consumer_org] == pytest.approx(0.0)
    assert investment.state.organization_construction_wip[consumer_org] == pytest.approx(0.0)
    assert investment.state.organization_project_approved[consumer_org] == pytest.approx(0.0)
    assert [
        _weighted(investment, flow.household_realized[:, consumer_g]) for flow in inv_flows
    ] == [pytest.approx(0.0), pytest.approx(0.0), pytest.approx(0.0)]


def test_investment_material_use_is_valued_in_department_i() -> None:
    """Plan §8 case 7: the project's ACTUAL material use belongs to Department I.

    Department I values the physical units installed this tick (from the
    investment demand cells' ``used``), not capacity units times the per-unit
    coefficient: a 40-unit capacity completion needs exactly 10 capital goods
    and 10 construction units at ``capacity_*_per_unit`` = 0.25.
    """
    investment = _investment_priority_fixture("investment_first")
    consumer_org = 2
    flows = _tick_with_gate(investment, 1)[0]
    inv_capital = _investment_demand(investment, consumer_org, "capital_goods")
    inv_construction = _investment_demand(investment, consumer_org, "construction")

    # the material actually installed this tick (admin price 1 per unit)
    assert flows.used[inv_capital] == pytest.approx(10.0)
    assert flows.used[inv_construction] == pytest.approx(10.0)
    summary = accounting_module.derive_departments(
        flows,
        build_material_prices(investment.parameters),
        investment.network,
        state=investment.state,
        housing_completed=0.0,
    )
    assert summary.commodity_use_quantities["capital_goods"]["department_I"] == pytest.approx(10.0)
    assert summary.commodity_use_quantities["construction"]["department_I"] == pytest.approx(10.0)
    assert summary.department_I_realized_use_value == pytest.approx(20.0)


def test_disconnected_investment_commodity_backlogs_without_crashing() -> None:
    """A declared investment commodity with no supplier is an observable backlog.

    The project owner is resolved from the demand cell's destination even when
    the cell has no route supplier (``demand_buyer == -1``), so the tick stays
    valid: nothing is delivered/installed, capacity is unchanged, and the
    unimplemented request remains approved.
    """
    capital_source = producer(1, "capital_goods_production", capacity=1.0)
    consumer = producer(2, "consumer_goods_production", capacity=10.0)
    wholesale = hub(3)
    shop = retail(4)
    technologies = [
        tech(
            "capital_goods_production",
            inputs=(),
            outputs=(("capital_goods", "standard", 1.0),),
        ),
        tech(
            "consumer_goods_production",
            inputs=(("capital_goods", 1.0),),
            outputs=(("consumer_goods", "standard", 1.0),),
        ),
    ]
    parameters = default_params(desired_per_person=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0])
    fixture = Fixture(
        [bank(0), capital_source, consumer, wholesale, shop],
        technologies,
        commodities=("capital_goods", "consumer_goods"),
        parameters=parameters,
        households=[(0, 1.0, 10.0)],
        household_cash=1000.0,
        ticks=2,
    )
    fixture.state.stock_value[:] = 0.0
    # No capital-goods WIP is staged, so the whole approved project is backlog.
    fixture.state.organization_project_approved[2] = 4.0

    flows = _tick_with_gate(fixture, 2)
    investment_capital = _investment_demand(fixture, 2, "capital_goods")
    for flow in flows:
        assert flow.delivered[investment_capital] == pytest.approx(0.0)
        assert flow.used[investment_capital] == pytest.approx(0.0)
        assert flow.organization_investment_completed[2] == pytest.approx(0.0)
    assert fixture.state.organization_capacity[2] == pytest.approx(10.0)
    assert fixture.state.organization_project_approved[2] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# Bottleneck fixture 10: plot stages, own use and late receipts
# ---------------------------------------------------------------------------


def _plot_ready_fixture(
    *, self_ready: float = 2.0, market_ready: float = 2.0, raw_ready: float = 0.0
) -> Fixture:
    """Plan §8 case 10.

    Five represented households in R0: household 4 is the region's plot
    participant (ordinal 4 hits the recipe's 20% participation step).  The
    participation mask is passed explicitly so the initial draw, the plot
    land/labor budget and the kernel's own cohort derivation agree; household
    0 carries 1000 spendable cash, households 1-3 have no persons.  Household 4
    starts with no cash, so its budget is zero and it can only self-use; the
    direct-plot purchases are funded by household 0's real wage income.
    """
    worker = producer(1, "energy_generation", capacity=4.0)
    fixture = Fixture(
        [bank(0), worker],
        [idle_source_tech("energy_generation", "energy")],
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=default_params(
            desired_per_person=[0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        ),
        households=[
            (0, 1.0, 2.0),
            (0, 1.0, 0.0),
            (0, 1.0, 0.0),
            (0, 1.0, 0.0),
            (0, 1.0, 2.0),
        ],
        household_cash=0.0,
        plot_participating=np.array([False, False, False, False, True]),
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.network.plot_ready_self_cell[0]] = self_ready
    fixture.state.stock_value[fixture.network.plot_ready_market_cell[0]] = market_ready
    fixture.state.stock_value[fixture.network.plot_raw_cell[0]] = raw_ready
    fixture.state.household_cash[0] = 1000.0
    fixture.state.bank_deposit_liability[0] += 1000.0
    fixture.state.bank_reserves[0] += 1000.0
    return fixture


def test_plot_stage_own_use_and_payment_are_not_double_counted() -> None:
    fixture = _plot_ready_fixture()
    food_g = fixture.g("food")
    self_cell = int(fixture.network.plot_ready_self_cell[0])
    market_cell = int(fixture.network.plot_ready_market_cell[0])
    opening = capture_material_stocks(fixture.state)
    flows = fixture.tick(1)[0]
    _assert_gate(fixture, opening, flows)

    # household 4 self-uses 2 ready units, household 0 buys the 2 market units
    # with its real wage income: region food use is exactly 4 units.
    assert flows.household_self_use[4] == pytest.approx(2.0)
    assert flows.household_realized[4, food_g] == pytest.approx(2.0)
    assert flows.household_realized[0, food_g] == pytest.approx(2.0)
    assert _weighted(fixture, flows.household_realized[:, food_g]) == pytest.approx(4.0)
    # only household 0 spends: own use is imputed, never a market purchase
    assert _weighted(fixture, flows.household_spending) == pytest.approx(2.0)
    assert flows.household_spending[4] == pytest.approx(0.0)
    # both ready pools close at zero: the same 4 units are never counted twice
    assert fixture.state.stock_value[self_cell] == pytest.approx(0.0)
    assert fixture.state.stock_value[market_cell] == pytest.approx(0.0)
    # the plot produced nothing because its input cells were empty, so the
    # closing pools show exactly the consumed opening stock
    assert flows.activity_target[-1] == pytest.approx(0.3)  # 0.15 * 2 persons
    assert flows.activity_realized[-1] == pytest.approx(0.0)
    # household 4 receives the late sale receipt (2) exactly once and cannot
    # spend it in the quarter it arrives: it is next quarter's receipt.
    assert flows.household_plot_income_direct[4] == pytest.approx(2.0)
    assert _weighted(fixture, flows.household_plot_income_direct) == pytest.approx(2.0)
    assert fixture.state.household_deferred_receipt[4] == pytest.approx(2.0)
    assert fixture.state.household_cash[4] == pytest.approx(4.0)  # 2 wage + 2 late
    assert fixture.state.household_cash[0] == pytest.approx(1000.0)

    # plot raw stock is not household-ready food: 4 raw units stay unsold and
    # no household can acquire them through the private-plot channel.
    raw = _plot_ready_fixture(self_ready=0.0, market_ready=0.0, raw_ready=4.0)
    raw_opening = capture_material_stocks(raw.state)
    raw_flows = raw.tick(1)[0]
    _assert_gate(raw, raw_opening, raw_flows)
    raw_cell = int(raw.network.plot_raw_cell[0])
    assert raw_flows.household_realized[:, raw.g("food")] == pytest.approx(0.0)
    assert raw_flows.household_self_use == pytest.approx(0.0)
    assert _weighted(raw, raw_flows.household_spending) == pytest.approx(0.0)
    assert raw.state.stock_value[raw_cell] == pytest.approx(4.0)


def _formal_farm_fixture() -> Fixture:
    """Control for plan §8 case 10: no plot participant.

    Four households whose ordinals never hit the recipe's participation step
    plus a functioning state farm fed by a domestic energy producer.  With the
    plot channel genuinely off there is no own use and no plot transaction,
    while the formal farm still produces.
    """
    feed = producer(1, "energy_generation", capacity=4.0)
    farm = org(
        2,
        OrganizationType.STATE_FARM,
        "R0",
        technology_id="field_farming",
        capacity=4.0,
        labor_available=4.0,
        labor_per_activity=1.0,
        initial_cash=100000.0,
        bank_id=0,
    )
    fixture = Fixture(
        [bank(0), feed, farm],
        [
            tech("energy_generation", inputs=(), outputs=(("energy", "standard", 1.0),)),
            tech(
                "field_farming",
                inputs=(("energy", 1.0),),
                outputs=(("food", "raw", 1.0),),
            ),
        ],
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=default_params(
            desired_per_person=[0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        ),
        households=[(0, 1.0, 2.0), (0, 1.0, 1.0), (0, 1.0, 1.0), (0, 1.0, 1.0)],
        household_cash=1000.0,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "output", "energy")] = 4.0
    return fixture


def test_plot_channels_are_off_without_participation_but_farm_stands() -> None:
    fixture = _formal_farm_fixture()
    farm_activity = _org_activity(fixture, 2)
    opening = capture_material_stocks(fixture.state)
    flows = fixture.tick(1)[0]
    _assert_gate(fixture, opening, flows)

    assert flows.household_self_use == pytest.approx(0.0)
    assert flows.household_plot_income_direct == pytest.approx(0.0)
    assert flows.household_realized[:, fixture.g("food")] == pytest.approx(0.0)
    assert fixture.state.stock_value[fixture.network.plot_ready_self_cell[0]] == pytest.approx(0.0)
    assert fixture.state.stock_value[
        fixture.network.plot_ready_market_cell[0]
    ] == pytest.approx(0.0)
    # the formal farm still exists and produces raw food for the formal chain
    assert fixture.initial.organizations[2].type is OrganizationType.STATE_FARM
    assert flows.activity_realized[farm_activity] == pytest.approx(4.0)
    assert fixture.state.stock_value[
        fixture.cell("organization", 2, 0, "output", "food", "raw")
    ] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# Bottleneck fixture 11: foreign channels, rates and official FX stay separate
# ---------------------------------------------------------------------------


def _energy_only(energy: float) -> list[float]:
    return [energy] + [0.0] * 7


def _trade_channel_fixture(
    *,
    reserve: float = 100.0,
    loan_limit: float = 0.0,
    principal: float = 0.0,
    domestic_borrower: bool = False,
) -> Fixture:
    """Plan §8 case 11: 100 units of energy demand on each channel.

    CMEA energy costs 1/unit and convertible energy 2/unit (oil price equals
    the forcing reference, so no oil scaling); the CMEA envelope and the USD
    reserve are 100 each.
    """
    trade = TradeParameters(
        cmea_prices=[1.0] * 8,
        convertible_prices=[2.0] + [1.0] * 7,
        cmea_desired_imports=_energy_only(100.0),
        convertible_desired_imports=_energy_only(100.0),
        cmea_export_demands=[0.0] * 8,
        convertible_export_demands=[0.0] * 8,
        cmea_credit_envelope=100.0,
        convertible_opening_reserve=reserve,
        convertible_loan_limit=loan_limit,
        convertible_opening_principal=principal,
    )
    borrower = org(
        1,
        OrganizationType.INDUSTRIAL_SOE,
        "R0",
        technology_id="energy_generation",
        capacity=10.0,
        labor_available=10.0,
        labor_per_activity=1.0,
        initial_cash=1000.0,
        bank_id=0,
        initial_loan_principal=10.0 if domestic_borrower else 0.0,
    )
    fixture = Fixture(
        [bank(0), borrower],
        [idle_source_tech("energy_generation", "energy")],
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=default_params(trade=trade),
    )
    fixture.state.stock_value[:] = 0.0
    return fixture


def _trade_flows(fixture: Fixture, *, global_usd_rate: float = 0.0, official_fx=None) -> object:
    return tick_material(
        fixture.state,
        fixture.forcing(1, global_usd_rate=global_usd_rate, official_fx=official_fx),
        fixture.parameters,
        fixture.network,
    )


def test_foreign_channels_rates_and_official_fx_are_separate() -> None:
    fixture = _trade_channel_fixture()
    energy_g = fixture.g("energy")
    opening = capture_material_stocks(fixture.state)
    flows = _trade_flows(fixture)
    _assert_gate(fixture, opening, flows)

    # 100 CMEA units at price 1 and 50 convertible units at price 2: each
    # channel is scaled by its own budget, never averaged together.
    assert flows.cmea_imports[energy_g] == pytest.approx(100.0)
    assert flows.convertible_imports[energy_g] == pytest.approx(50.0)
    assert flows.cmea_import_payment == pytest.approx(100.0)
    assert flows.usd_import_payment == pytest.approx(100.0)
    assert fixture.state.cmea_settlement_balance == pytest.approx(-100.0)
    assert fixture.state.usd_reserve == pytest.approx(0.0)
    assert fixture.state.stock_value[
        fixture.network.import_pool_cell[energy_g]
    ] == pytest.approx(150.0)

    # The official FX quote is a diagnostic only: it never rescales quantities,
    # channel prices, payments or settlement balances.
    low = _trade_channel_fixture()
    low_flows = _trade_flows(low, official_fx=50.0)
    high = _trade_channel_fixture()
    high_flows = _trade_flows(high, official_fx=100.0)
    assert flows.official_fx_translation is None  # no quote in the forcing
    assert low_flows.official_fx_translation == pytest.approx(50.0)
    assert high_flows.official_fx_translation == pytest.approx(100.0)
    for other, other_flows in ((low, low_flows), (high, high_flows)):
        assert other_flows.cmea_imports[energy_g] == pytest.approx(100.0)
        assert other_flows.convertible_imports[energy_g] == pytest.approx(50.0)
        assert other_flows.cmea_import_payment == pytest.approx(100.0)
        assert other_flows.usd_import_payment == pytest.approx(100.0)
        assert other.state.cmea_settlement_balance == pytest.approx(-100.0)
        assert other.state.stock_value[
            other.network.import_pool_cell[energy_g]
        ] == pytest.approx(150.0)

    # External interest is the global rate plus the Hungary spread: 4%/400 +
    # 2%/400 = .015 on 100, 8%/400 + .005 = .025.  The domestic quarterly rate
    # stays .04/4 in both runs.
    four = _trade_channel_fixture(principal=100.0, domestic_borrower=True)
    four_flows = _trade_flows(four, global_usd_rate=4.0)
    eight = _trade_channel_fixture(principal=100.0, domestic_borrower=True)
    eight_flows = _trade_flows(eight, global_usd_rate=8.0)
    assert four_flows.usd_interest_accrued == pytest.approx(1.5)
    assert four_flows.usd_interest_paid == pytest.approx(1.5)
    assert four.state.usd_interest_arrears == pytest.approx(0.0)
    assert eight_flows.usd_interest_accrued == pytest.approx(2.5)
    assert four_flows.organization_interest_due[1] == pytest.approx(0.1)
    assert eight_flows.organization_interest_due[1] == pytest.approx(0.1)
    assert four.state.usd_principal == pytest.approx(95.0)  # 5% scheduled repayment

    # Zero USD balance and zero loan limit: USD imports are zero and the CMEA
    # channel is untouched.  Unpaid USD interest accrues as its own claim
    # instead of silently consuming the two isolated import budgets.
    starved = _trade_channel_fixture(reserve=0.0, loan_limit=0.0, principal=100.0)
    starved_flows = _trade_flows(starved, global_usd_rate=4.0)
    assert starved_flows.convertible_imports[energy_g] == pytest.approx(0.0)
    assert starved_flows.usd_import_payment == pytest.approx(0.0)
    assert starved_flows.cmea_imports[energy_g] == pytest.approx(100.0)
    assert starved_flows.cmea_import_payment == pytest.approx(100.0)
    assert starved_flows.usd_interest_accrued == pytest.approx(1.5)
    assert starved_flows.usd_interest_paid == pytest.approx(0.0)
    assert starved.state.usd_interest_arrears == pytest.approx(1.5)
    assert starved.state.usd_principal == pytest.approx(100.0)
    assert starved.state.cmea_settlement_balance == pytest.approx(-100.0)


# ---------------------------------------------------------------------------
# Bottleneck fixture 12: services expire, completed stocks stay put
# ---------------------------------------------------------------------------


def _services_fixture() -> Fixture:
    """Plan §8 case 12 (services): the hauler's 5 same-tick services pay for a
    10-unit cross-region delivery (3 service units) and 2 expire unused."""
    seller = producer(1, "energy_generation", region="R1", capacity=1.0)
    wholesale = hub(2, region="R0")
    shop = retail(3, region="R0")
    hauler = transport(4, region="R0", capacity=5.0)
    technologies = [
        idle_source_tech("energy_generation", "energy"),
        tech(
            "freight_transport",
            inputs=(("durable_goods", 1.0),),
            outputs=(("services_transport", "standard", 1.0),),
        ),
    ]
    parameters = default_params(
        desired_per_person=[0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        transport_per_unit=0.3,
    )
    fixture = Fixture(
        [bank(0), seller, wholesale, shop, hauler],
        technologies,
        region_ids=("R0", "R1"),
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=parameters,
        households=[(0, 1.0, 25.0)],
        household_cash=1000.0,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 1, "output", "energy")] = 10.0
    fixture.state.stock_value[fixture.cell("organization", 4, 0, "input", "durable_goods")] = 5.0
    return fixture


def test_services_expire_and_completed_stocks_do_not_become_food() -> None:
    fixture = _services_fixture()
    hauler_activity = _org_activity(fixture, 4)
    services_g = fixture.g("services_transport")
    seller_cell = fixture.cell("organization", 1, 1, "output", "energy")
    hub_cell = fixture.cell("organization", 2, 0, "wholesale", "energy")
    edge = fixture.edge(seller_cell, hub_cell)
    opening = capture_material_stocks(fixture.state)
    flows = fixture.tick(1)[0]
    _assert_gate(fixture, opening, flows)

    # produced 5, used 3, expired 2, close 0: nothing is carried or stocked
    assert flows.activity_realized[hauler_activity] == pytest.approx(5.0)
    assert flows.edge_delivered[edge] == pytest.approx(10.0)
    assert flows.edge_service_used[edge] == pytest.approx(3.0)
    assert flows.expired_services == pytest.approx(2.0)
    services_cells = np.flatnonzero(np.asarray(fixture.network.cell_commodity) == services_g)
    assert fixture.state.stock_value[services_cells] == pytest.approx(0.0)

    # construction delivered to housing becomes dwelling stock only, never
    # food or durable goods, and never factory capacity.
    housing = _housing_fixture()
    builder_capacity = float(housing.state.organization_capacity[2])
    dwelling_open = float(housing.state.dwelling_stock[0])
    housing_opening = capture_material_stocks(housing.state)
    housing_flows = housing.tick(1)[0]
    _assert_gate(housing, housing_opening, housing_flows)
    demand = _housing_demand(housing)
    assert housing_flows.used[demand] == pytest.approx(2.0)
    assert float(housing.state.dwelling_stock[0]) - dwelling_open == pytest.approx(2.0)
    assert housing.state.organization_capacity[2] == pytest.approx(builder_capacity)
    assert housing_flows.organization_investment_completed[2] == pytest.approx(0.0)
    assert housing_flows.household_realized[:, housing.g("food")] == pytest.approx(0.0)
    assert housing.state.durable_stock[0] == pytest.approx(0.0)

    # durable purchases add regional durable stock (not another consumption
    # good and not housing).
    durable = _durable_sales_fixture()
    durable_g = durable.g("durable_goods")
    durable_opening = capture_material_stocks(durable.state)
    durable_flows = durable.tick(1)[0]
    _assert_gate(durable, durable_opening, durable_flows)
    assert durable_flows.retail_sales[0, durable_g] == pytest.approx(3.0)
    assert durable.state.durable_stock[0] == pytest.approx(3.0)
    assert durable.state.dwelling_stock[0] == pytest.approx(0.4 * 3.0)
    assert durable_flows.expired_services == pytest.approx(0.0)

    # the bank owns no material cell and produces no physical output.
    bank_row = 0
    assert fixture.initial.organizations[bank_row].type is OrganizationType.BANK
    assert int(fixture.network.org_output_cell[bank_row]) == -1
    assert int(fixture.network.org_wholesale_cell[bank_row]) == -1
    assert int(fixture.network.project_capital_cell[bank_row]) == -1
    assert int(fixture.network.project_construction_cell[bank_row]) == -1
    assert not np.any(
        (np.asarray(fixture.network.cell_owner_kind) == 0)
        & (np.asarray(fixture.network.cell_owner_id) == 0)
    )
    assert bank_row not in np.asarray(fixture.network.activity_org_index)
    assert flows.organization_realized[bank_row] == pytest.approx(0.0)


def _housing_fixture() -> Fixture:
    """Plan §8 case 12 (housing): region persons 2 request 2 construction units
    and the Treasury pays for exactly 2 delivered units."""
    energy = producer(1, "energy_generation", capacity=5.0)
    builder = producer(2, "building_construction", capacity=5.0)
    technologies = [
        idle_source_tech("energy_generation", "energy"),
        tech(
            "building_construction",
            inputs=(("energy", 1.0),),
            outputs=(("construction", "standard", 1.0),),
        ),
    ]
    fixture = Fixture(
        [bank(0), energy, builder],
        technologies,
        commodities=("energy", "food", "consumer_goods", "construction", "durable_goods"),
        parameters=default_params(housing_request_per_person=1.0),
        households=[(0, 2.0, 1.0)],
        ticks=1,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "output", "energy")] = 5.0
    fixture.state.stock_value[fixture.cell("organization", 2, 0, "output", "construction")] = 2.0
    return fixture


def _durable_sales_fixture() -> Fixture:
    """Plan §8 case 12 (durable): one household of 3 persons buys 3 durable
    goods from a regional retail cell with real wage income."""
    worker = producer(1, "energy_generation", capacity=3.0)
    shop = retail(2)
    fixture = Fixture(
        [bank(0), worker, shop],
        [idle_source_tech("energy_generation", "energy")],
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=default_params(
            desired_per_person=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ),
        households=[(0, 1.0, 3.0)],
        household_cash=1000.0,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 2, 0, "retail", "durable_goods")] = 3.0
    return fixture


def _partial_project_fixture() -> Fixture:
    """Plan §8 case 12 (partial project): approved 2 capacity units need .5
    capital + .5 construction; the first quarter delivers .5 capital but only
    .25 construction, so 1 unit completes and the project keeps WIP."""
    capital = producer(1, "capital_goods_production", capacity=1.0)
    consumer = producer(2, "consumer_goods_production", capacity=10.0)
    builder = producer(3, "building_construction", capacity=1.0)
    technologies = [
        tech(
            "capital_goods_production",
            inputs=(),
            outputs=(("capital_goods", "standard", 1.0),),
        ),
        tech(
            "consumer_goods_production",
            inputs=(),
            outputs=(("consumer_goods", "standard", 1.0),),
        ),
        tech(
            "building_construction",
            inputs=(),
            outputs=(("construction", "standard", 1.0),),
        ),
    ]
    fixture = Fixture(
        [bank(0), capital, consumer, builder],
        technologies,
        commodities=INVESTMENT_PRIORITY_COMMODITIES,
        parameters=default_params(),
        household_cash=1000.0,
        ticks=2,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "output", "capital_goods")] = 0.5
    fixture.state.stock_value[fixture.cell("organization", 3, 0, "output", "construction")] = 0.25
    fixture.state.organization_project_approved[2] = 2.0
    return fixture


def test_partial_project_wip_installs_next_quarter() -> None:
    fixture = _partial_project_fixture()
    org = 2
    capital_activity = _org_activity(fixture, 1)
    first_opening = capture_material_stocks(fixture.state)
    first = fixture.tick(1)[0]
    _assert_gate(fixture, first_opening, first)

    # t0: .5 capital and .25 construction are installed as 1 capacity unit;
    # the unmatched .25 capital stays in WIP for next quarter.
    assert first.organization_investment_completed[org] == pytest.approx(1.0)
    assert fixture.state.organization_capital_wip[org] == pytest.approx(0.25)
    assert fixture.state.organization_construction_wip[org] == pytest.approx(0.0)
    assert fixture.state.organization_capacity[org] == pytest.approx(11.0)
    assert fixture.state.organization_project_approved[org] == pytest.approx(1.0)
    inv_capital = _investment_demand(fixture, org, "capital_goods")
    inv_construction = _investment_demand(fixture, org, "construction")
    assert first.used[inv_capital] == pytest.approx(0.25)
    assert first.used[inv_construction] == pytest.approx(0.25)
    # the capital producer runs at its own capacity of 1 unit per quarter; the
    # project only takes the .5 units its approved WIP still needs
    assert first.activity_realized[capital_activity] == pytest.approx(1.0)
    assert first.delivered[inv_capital] == pytest.approx(0.5)
    assert first.delivered[inv_construction] == pytest.approx(0.25)

    # t1: another .25 of each arrives; the carried WIP completes the second
    # unit with no new approval and no negative stock.
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "output", "capital_goods")] = 0.25
    fixture.state.stock_value[fixture.cell("organization", 3, 0, "output", "construction")] = 0.25
    second_opening = capture_material_stocks(fixture.state)
    second = fixture.tick(1)[0]
    _assert_gate(fixture, second_opening, second)
    assert second.organization_investment_completed[org] == pytest.approx(1.0)
    assert fixture.state.organization_capital_wip[org] == pytest.approx(0.0)
    assert fixture.state.organization_construction_wip[org] == pytest.approx(0.0)
    assert fixture.state.organization_capacity[org] == pytest.approx(12.0)
    assert fixture.state.organization_project_approved[org] == pytest.approx(0.0)


def _mixed_energy_fixture() -> Fixture:
    """Plan §8 case 12 (departments): 6 energy units used as an intermediate
    input, 4 bought by households through retail, 100 energy units imported."""
    energy = producer(1, "energy_generation", capacity=10.0)
    consumer = producer(2, "consumer_goods_production", capacity=6.0)
    shop = retail(3)
    technologies = [
        tech("energy_generation", inputs=(), outputs=(("energy", "standard", 1.0),)),
        tech(
            "consumer_goods_production",
            inputs=(("energy", 1.0),),
            outputs=(("consumer_goods", "standard", 1.0),),
        ),
    ]
    trade = TradeParameters(
        cmea_desired_imports=_energy_only(100.0),
        convertible_desired_imports=[0.0] * 8,
        cmea_export_demands=[0.0] * 8,
        convertible_export_demands=[0.0] * 8,
        cmea_credit_envelope=1000.0,
        convertible_opening_reserve=1000.0,
        convertible_loan_limit=0.0,
    )
    fixture = Fixture(
        [bank(0), energy, consumer, shop],
        technologies,
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=default_params(
            desired_per_person=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            trade=trade,
        ),
        households=[(0, 1.0, 4.0)],
        household_cash=1000.0,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 0, "output", "energy")] = 6.0
    fixture.state.stock_value[fixture.cell("organization", 3, 0, "retail", "energy")] = 4.0
    return fixture


def _blocked_input_fixture() -> Fixture:
    """Plan §8 case 12 (reservation): the same intermediate energy demand, but
    the hauler has no fuel, so the allocation is reserved and never delivered."""
    seller = producer(1, "energy_generation", region="R1", capacity=10.0)
    buyer = producer(2, "consumer_goods_production", region="R0", capacity=6.0)
    hauler = transport(3, region="R0", capacity=1.0)
    technologies = [
        tech("energy_generation", inputs=(), outputs=(("energy", "standard", 1.0),)),
        tech(
            "consumer_goods_production",
            inputs=(("energy", 1.0),),
            outputs=(("consumer_goods", "standard", 1.0),),
        ),
        tech(
            "freight_transport",
            inputs=(("durable_goods", 1.0),),
            outputs=(("services_transport", "standard", 1.0),),
        ),
    ]
    fixture = Fixture(
        [bank(0), seller, buyer, hauler],
        technologies,
        region_ids=("R0", "R1"),
        commodities=NO_CAPITAL_COMMODITIES,
        parameters=default_params(transport_per_unit=0.1),
        household_cash=1000.0,
    )
    fixture.state.stock_value[:] = 0.0
    fixture.state.stock_value[fixture.cell("organization", 1, 1, "output", "energy")] = 10.0
    return fixture


def test_mixed_energy_departments_exclude_reservations_and_imports() -> None:
    fixture = _mixed_energy_fixture()
    energy_g = fixture.g("energy")
    intermediate = fixture.k_of(
        fixture.cell("organization", 2, 0, "input", "energy")
    )
    opening = capture_material_stocks(fixture.state)
    flows = fixture.tick(1)[0]
    _assert_gate(fixture, opening, flows)

    # 6 intermediate units + 4 household units at admin price 1: the same
    # commodity lands in Department I and II by use, not by commodity label.
    assert flows.used[intermediate] == pytest.approx(6.0)
    assert flows.household_realized[0, energy_g] == pytest.approx(4.0)
    summary = accounting_module.derive_departments(
        flows,
        build_material_prices(fixture.parameters),
        fixture.network,
        state=fixture.state,
        housing_completed=0.0,
    )
    assert summary.department_I_realized_use_value == pytest.approx(6.0)
    assert summary.department_II_realized_use_value == pytest.approx(4.0)
    assert summary.commodity_use_quantities["energy"]["department_I"] == pytest.approx(6.0)
    assert summary.commodity_use_quantities["energy"]["department_II"] == pytest.approx(4.0)
    # imports are not domestic production: 100 landed units stay out of gross
    # domestic output (10 energy + 6 consumer goods produced at price 1).
    assert flows.imports[energy_g] == pytest.approx(100.0)
    assert summary.gross_domestic_output_value == pytest.approx(16.0)

    # a reservation that never delivers is not output: the blocked intermediate
    # demand is allocated, undelivered, unused, and attributed to no department.
    blocked = _blocked_input_fixture()
    blocked_intermediate = blocked.k_of(blocked.cell("organization", 2, 0, "input", "energy"))
    blocked_opening = capture_material_stocks(blocked.state)
    blocked_flows = blocked.tick(1)[0]
    _assert_gate(blocked, blocked_opening, blocked_flows)
    assert blocked_flows.allocated[blocked_intermediate] == pytest.approx(6.0)
    assert blocked_flows.delivered[blocked_intermediate] == pytest.approx(0.0)
    assert blocked_flows.used[blocked_intermediate] == pytest.approx(0.0)
    blocked_summary = accounting_module.derive_departments(
        blocked_flows,
        build_material_prices(blocked.parameters),
        blocked.network,
        state=blocked.state,
        housing_completed=0.0,
    )
    assert blocked_summary.department_I_realized_use_value == pytest.approx(0.0)
    assert blocked_summary.department_I_attributed_output_value == pytest.approx(0.0)
    assert blocked_summary.unclassified_output_value == pytest.approx(
        blocked_summary.gross_domestic_output_value
    )


# ---------------------------------------------------------------------------
# Every fixture must satisfy the material/finance accounting gates (the same
# gate the runner applies after each admitted tick).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "factory",
    [
        lambda: _energy_lag_fixture(),
        lambda: _raw_bottleneck_fixture(energy_opening=100.0),
        lambda: _food_chain_fixture(),
        lambda: _transport_fixture(transport_opening=1.0),
        lambda: _shared_source_fixture(overorder=1.0, hoarding=0.0, a_expectation=1.0),
    ],
)
def test_fixtures_satisfy_material_invariants(factory) -> None:
    fixture = factory()
    opening = capture_material_stocks(fixture.state)
    flows = tick_material(fixture.state, fixture.forcing(1), fixture.parameters, fixture.network)
    summary = accounting_module.check_material_invariants(
        opening, fixture.state, flows, fixture.parameters, fixture.network
    )
    assert summary.max_material_tolerance_ratio <= 1.0
    assert summary.max_finance_tolerance_ratio <= 1.0
