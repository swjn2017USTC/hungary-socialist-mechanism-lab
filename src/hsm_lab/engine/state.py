"""Material runtime state, flows and declarations (P02).

Typed dataclasses over NumPy column arrays; every commodity axis is last.
The authoritative material stock is the single ``stock_value[S]`` array over
the canonical ``(owner_kind, owner_id, pool, commodity_id, stage)`` cell
catalog compiled once into :class:`MaterialNetwork`. Household cash, finance
accounts, regional dwelling/durable stocks and organization capacity/finance
live in separate typed arrays. Bank organizations hold no material cell.

Units: household cash/wage claims are per represented household; organization
and cell stocks are physical quantities. Journal amounts are represented
economy amounts (``weight *`` per-household deltas) — never double-weighted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from hsm_lab.contract.households import (
    DURABLE_IDS,
    ENTITLEMENT_IDS,
    HOUSEHOLD_GOOD_IDS,
    SUBSTITUTION_IDS,
)
from hsm_lab.contract.material import (
    ORGANIZATION_TYPE_ORDER,
    CellOwnerKind,
    MaterialInitialConditions,
    MaterialParameters,
    OrganizationSpec,
    OrganizationType,
)
from hsm_lab.contract.schemas import ResearchGateError, ScenarioSpec

if TYPE_CHECKING:  # pragma: no cover - annotation-only; avoids an import cycle
    from hsm_lab.engine.network import MaterialNetwork

MATERIAL_STATE_VERSION = "material-state-v2"

POOL_CODES: dict[str, int] = {
    "input": 0,
    "output": 1,
    "wholesale": 2,
    "retail": 3,
    "wip": 4,
    "import_pool": 5,
}

#: Fixed household subsystem axis sizes (P03).  Every multi-axis state/flow
#: array below carries one of these as its trailing dimension.
N_H = len(HOUSEHOLD_GOOD_IDS)  # 11 consumption sub-channels
N_D = len(DURABLE_IDS)  # 4 durable types
N_E = len(ENTITLEMENT_IDS)  # 7 entitlement components
N_Q = len(SUBSTITUTION_IDS)  # 5 forced-substitution pairs


def owner_kind_code(kind: CellOwnerKind) -> int:
    return {
        CellOwnerKind.ORGANIZATION: 0,
        CellOwnerKind.PLOT: 1,
        CellOwnerKind.PROJECT: 2,
        CellOwnerKind.TREASURY_IMPORT: 3,
        CellOwnerKind.SECOND_ECONOMY: 4,
    }[kind]


@dataclass
class MaterialPrices:
    """Compiled readonly price view: ``food`` raw/ready priced separately."""

    standard: np.ndarray  # float64 (G,) admin price; food slot is ready food
    food_raw: float

    def price_for(self, commodity_index: int, stage_code: int) -> float:
        if commodity_index == 2 and stage_code == 1:  # food/raw
            return self.food_raw
        return float(self.standard[commodity_index])


@dataclass
class MaterialForcing:
    """Admitted deterministic quarterly forcing for the full horizon grid.

    ``oil_price``/``global_usd_rate`` are (T,) scalars per quarter;
    ``official_fx`` has NaN where no quote exists (1985-only in P02);
    ``cmea_energy_price`` is the reconstructed contract price (NaN outside
    its registered window); ``segment`` labels the evidence segment per tick.
    """

    quarters: list[str]
    oil_price: np.ndarray  # float64 (T,)
    global_usd_rate: np.ndarray  # float64 (T,)
    official_fx: np.ndarray  # float64 (T,) NaN = no quote
    cmea_energy_price: np.ndarray  # float64 (T,) NaN = outside window
    segment: list[str]  # per-tick evidence segment label
    input_artifact_hashes: dict[str, str]


@dataclass
class MaterialState:
    """Complete mutable material-economy state at an end-of-quarter boundary."""

    schema_version: str
    completed_ticks: int
    # --- stock cells (S,) authoritative material inventory -------------
    stock_value: np.ndarray  # float64 (S,)
    # --- households (N,) -----------------------------------------------
    household_id: np.ndarray  # int64 (N,)
    household_region: np.ndarray  # int32 (N,)
    household_weight: np.ndarray  # float64 (N,)
    household_size: np.ndarray  # float64 (N,)
    household_cash: np.ndarray  # float64 (N,)
    household_deferred_receipt: np.ndarray  # float64 (N,)
    household_wage_claim: np.ndarray  # float64 (N,) unpaid wage claims
    # --- household static attributes (N,) --------------------------------
    household_urban: np.ndarray  # bool (N,)
    household_occupation: np.ndarray  # int8 (N,) occupation ordinal
    household_sector: np.ndarray  # int16 (N,) sector ordinal
    household_education: np.ndarray  # int8 (N,) education ordinal
    household_children: np.ndarray  # int16 (N,)
    household_adults: np.ndarray  # int16 (N,)
    household_elderly: np.ndarray  # int16 (N,)
    household_working_adults: np.ndarray  # float64 (N,)
    household_pay_weight: np.ndarray  # float64 (N,)
    household_plot_participating: np.ndarray  # bool (N,)
    household_second_participating: np.ndarray  # bool (N,)
    household_western_exposure: np.ndarray  # float64 (N,)
    # --- household dynamic state (N,) ------------------------------------
    household_tenure: np.ndarray  # int8 (N,) tenure ordinal
    household_informal_access: np.ndarray  # float64 (N,)
    household_dwelling_access: np.ndarray  # float64 (N,)
    household_housing_wait: np.ndarray  # int32 (N,)
    household_last_income: np.ndarray  # float64 (N,)
    household_reference_income: np.ndarray  # float64 (N,)
    household_last_price_index: np.ndarray  # float64 (N,)
    household_reserved_plot_hours: np.ndarray  # float64 (N,)
    household_reserved_second_hours: np.ndarray  # float64 (N,)
    household_formal_effort: np.ndarray  # float64 (N,)
    household_material_satisfaction: np.ndarray  # float64 (N,)
    household_political_compliance: np.ndarray  # float64 (N,)
    household_grievance: np.ndarray  # float64 (N,)
    # --- household multi-axis dynamic state (N, axis) --------------------
    household_durable_owned: np.ndarray  # float64 (N, D)
    household_durable_age: np.ndarray  # float64 (N, D)
    household_durable_backlog: np.ndarray  # float64 (N, D)
    household_durable_wait: np.ndarray  # int32 (N, D)
    household_durable_repair_credit: np.ndarray  # float64 (N, D)
    household_consumption_reference: np.ndarray  # float64 (N, H)
    household_last_consumption: np.ndarray  # float64 (N, H)
    household_last_availability_unmet: np.ndarray  # float64 (N, H)
    household_entitlement: np.ndarray  # float64 (N, E)
    household_expectation: np.ndarray  # float64 (N, E)
    household_improvement_streak: np.ndarray  # int32 (N, E)
    # --- regional household-channel stocks (R,) -------------------------
    dwelling_stock: np.ndarray  # float64 (R,) physical dwelling stock
    housing_vacant: np.ndarray  # float64 (R,) unoccupied dwelling stock
    # --- second-economy aggregate pool (R, G) ---------------------------
    second_output_stock: np.ndarray  # float64 (R, G) produced output inventory
    # --- organizations (O,) ---------------------------------------------
    organization_id: np.ndarray  # int64 (O,)
    organization_type: np.ndarray  # int8 (O,) OrganizationType ordinal
    organization_region: np.ndarray  # int32 (O,)
    organization_technology: np.ndarray  # int32 (O,) technology row or -1
    organization_activity: np.ndarray  # int32 (O,) P-axis index or -1
    organization_bank: np.ndarray  # int32 (O,) dense bank index or -1
    organization_capacity: np.ndarray  # float64 (O,)
    organization_labor_available: np.ndarray  # float64 (O,) nominal labor
    organization_labor_endowment: np.ndarray  # float64 (O,) static nominal base
    organization_effort_factor: np.ndarray  # float64 (O,) [floor, 1] effort
    organization_labor_per_activity: np.ndarray  # float64 (O,) 0 if none
    organization_cash: np.ndarray  # float64 (O,)
    organization_wage_arrears: np.ndarray  # float64 (O,)
    organization_interest_arrears: np.ndarray  # float64 (O,)
    organization_principal: np.ndarray  # float64 (O,)
    organization_shortage_expectation: np.ndarray  # float64 (O,)
    organization_bailout_expectation: np.ndarray  # float64 (O,)
    organization_project_approved: np.ndarray  # float64 (O,)
    organization_capital_wip: np.ndarray  # float64 (O,)
    organization_construction_wip: np.ndarray  # float64 (O,)
    organization_capital_age: np.ndarray  # float64 (O,)
    # --- plots (R,) ------------------------------------------------------
    plot_capacity: np.ndarray  # float64 (R,) land capacity
    plot_labor_budget: np.ndarray  # float64 (R,) spare-time labor
    plot_activity: np.ndarray  # int32 (R,) P-axis index
    # --- finance: banks (B,) ---------------------------------------------
    bank_reserves: np.ndarray  # float64 (B,)
    bank_loan_asset: np.ndarray  # float64 (B,)
    bank_deposit_liability: np.ndarray  # float64 (B,)
    bank_equity: np.ndarray  # float64 (B,)
    bank_interest_receivable: np.ndarray  # float64 (B,)
    treasury_deposit: float  # domestic fiscal account (banks with bank index 0)
    # --- foreign accounts (scalars; separate currencies) ------------------
    usd_reserve: float
    usd_principal: float
    usd_interest_arrears: float
    cmea_settlement_balance: float  # may go negative (memo credit)

    def copy_dynamic(self) -> MaterialState:
        """Deep-copy every mutable array; shares nothing the tick mutates."""
        import dataclasses

        clone = dataclasses.replace(self)
        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            if isinstance(value, np.ndarray):
                setattr(clone, f.name, value.copy())
        return clone


@dataclass
class MaterialStockSnapshot:
    """Runner-captured opening boundary (mutable arrays only)."""

    stock_value: np.ndarray  # float64 (S,)
    household_cash: np.ndarray  # float64 (N,)
    organization_cash: np.ndarray  # float64 (O,)
    dwelling_stock: np.ndarray  # float64 (R,)
    housing_vacant: np.ndarray  # float64 (R,)
    household_durable_owned: np.ndarray  # float64 (N, D)
    household_dwelling_access: np.ndarray  # float64 (N,)
    household_informal_access: np.ndarray  # float64 (N,)
    household_entitlement: np.ndarray  # float64 (N, E)
    household_expectation: np.ndarray  # float64 (N, E)
    second_output_stock: np.ndarray  # float64 (R, G)
    bank_reserves: np.ndarray  # float64 (B,)
    bank_loan_asset: np.ndarray  # float64 (B,)
    bank_deposit_liability: np.ndarray  # float64 (B,)
    bank_equity: np.ndarray  # float64 (B,)
    bank_interest_receivable: np.ndarray  # float64 (B,)
    treasury_deposit: float
    usd_reserve: float
    usd_principal: float
    usd_interest_arrears: float
    cmea_settlement_balance: float
    # organization dynamic finance/expectation fields
    organization_cash_open: np.ndarray  # alias of organization_cash above
    organization_principal: np.ndarray
    organization_wage_arrears: np.ndarray
    organization_interest_arrears: np.ndarray
    organization_shortage_expectation: np.ndarray
    organization_bailout_expectation: np.ndarray
    organization_project_approved: np.ndarray
    organization_capital_wip: np.ndarray
    organization_construction_wip: np.ndarray
    organization_capacity: np.ndarray
    household_wage_claim: np.ndarray
    household_deferred_receipt: np.ndarray
    completed_ticks: int


@dataclass
class MaterialTickFlows:
    """All material/financial flows of one completed tick.

    Demand axis D covers every order intent (production inputs K, trader
    replenishment, plot inputs, investment, housing, exports). Stock
    conservation is checked once per unique stock cell — never by summing
    overlapping demand views.
    """

    tick: int
    quarter: str
    # --- production (P activities) ---------------------------------------
    activity_target: np.ndarray  # float64 (P,)
    activity_realized: np.ndarray  # float64 (P,)
    # --- demand cells (D,) six segments + opening/closing views ----------
    desired: np.ndarray  # float64 (D,)
    ordered: np.ndarray  # float64 (D,) after funding (cash-limited)
    ordered_gross: np.ndarray  # float64 (D,) before funding/overorder scaling
    unfunded_order: np.ndarray  # float64 (D,)
    allocated: np.ndarray  # float64 (D,)
    delivered: np.ndarray  # float64 (D,)
    used: np.ndarray  # float64 (D,)
    inventory_open: np.ndarray  # float64 (D,) destination cell opening view
    inventory_close: np.ndarray  # float64 (D,) destination cell closing view
    financial_delivery_blocked: np.ndarray  # float64 (D,)
    # --- sparse route edges (M,) ------------------------------------------
    edge_delivered: np.ndarray  # float64 (M,)
    edge_allocated: np.ndarray  # float64 (M,)
    edge_service_used: np.ndarray  # float64 (M,) logistics service consumed
    edge_service_fee: np.ndarray  # float64 (M,) domestic currency fee
    # --- organizations (O,) ------------------------------------------------
    organization_target: np.ndarray  # float64 (O,) 0 for non-producers
    organization_realized: np.ndarray  # float64 (O,)
    organization_wage_due: np.ndarray  # float64 (O,)
    organization_wage_paid: np.ndarray  # float64 (O,)
    organization_interest_due: np.ndarray  # float64 (O,)
    organization_interest_paid: np.ndarray  # float64 (O,)
    organization_principal_paid: np.ndarray  # float64 (O,)
    organization_credit_requested: np.ndarray  # float64 (O,)
    organization_credit_approved: np.ndarray  # float64 (O,)
    organization_credit_drawn: np.ndarray  # float64 (O,)
    organization_investment_requested: np.ndarray  # float64 (O,)
    organization_investment_approved: np.ndarray  # float64 (O,)
    organization_investment_completed: np.ndarray  # float64 (O,)
    organization_bailout_requested: np.ndarray  # float64 (O,)
    organization_bailout_granted: np.ndarray  # float64 (O,)
    organization_sales_receipts: np.ndarray  # float64 (O,)
    organization_purchases: np.ndarray  # float64 (O,)
    # --- households (N,) -----------------------------------------------------
    household_wage_income: np.ndarray  # float64 (N,) pre-purchase wages
    household_plot_income_formal: np.ndarray  # float64 (N,)
    household_plot_income_direct: np.ndarray  # float64 (N,) late receipts
    household_late_wage: np.ndarray  # float64 (N,)
    household_desired: np.ndarray  # float64 (N, G)
    household_affordable: np.ndarray  # float64 (N, G)
    household_realized: np.ndarray  # float64 (N, G)
    household_budget_unmet: np.ndarray  # float64 (N, G)
    household_availability_unmet: np.ndarray  # float64 (N, G)
    household_spending: np.ndarray  # float64 (N,)
    household_self_use: np.ndarray  # float64 (N,) imputed value
    household_plot_input_funding: np.ndarray  # float64 (N,)
    household_budget_available: np.ndarray  # float64 (N,)
    household_forced_saving: np.ndarray  # float64 (N,)
    household_voluntary_saving: np.ndarray  # float64 (N,)
    household_cash_open: np.ndarray  # float64 (N,)
    household_cash_close: np.ndarray  # float64 (N,)
    # --- household consumption sub-channels (N, H) --------------------------
    household_desired_h: np.ndarray  # float64 (N, H)
    household_affordable_h: np.ndarray  # float64 (N, H)
    household_realized_h: np.ndarray  # float64 (N, H)
    household_budget_unmet_h: np.ndarray  # float64 (N, H)
    household_availability_unmet_h: np.ndarray  # float64 (N, H)
    household_formal_h: np.ndarray  # float64 (N, H)
    household_plot_self_h: np.ndarray  # float64 (N, H)
    household_plot_market_h: np.ndarray  # float64 (N, H)
    household_second_h: np.ndarray  # float64 (N, H)
    household_goal_credit_h: np.ndarray  # float64 (N, H)
    # --- household substitution / time / money (N, ·) -----------------------
    household_substitution: np.ndarray  # float64 (N, Q)
    household_queue_hours: np.ndarray  # float64 (N,)
    household_search_hours: np.ndarray  # float64 (N,)
    household_plot_hours: np.ndarray  # float64 (N,)
    household_second_hours: np.ndarray  # float64 (N,)
    household_leisure_hours: np.ndarray  # float64 (N,)
    household_planned_spending: np.ndarray  # float64 (N,)
    household_savings_draw: np.ndarray  # float64 (N,)
    household_second_input_funding: np.ndarray  # float64 (N,)
    household_second_income_direct: np.ndarray  # float64 (N,)
    household_substitution_loss: np.ndarray  # float64 (N,)
    household_postponement_cost: np.ndarray  # float64 (N,)
    household_welfare_net: np.ndarray  # float64 (N,)
    # --- durable / housing flows (N, ·) -------------------------------------
    durable_acquired: np.ndarray  # float64 (N, D)
    durable_retired: np.ndarray  # float64 (N, D)
    durable_repaired: np.ndarray  # float64 (N, D)
    housing_allocated: np.ndarray  # float64 (N,)
    private_completed: np.ndarray  # float64 (N,)
    household_overcrowding: np.ndarray  # float64 (N,)
    entitlement_gap: np.ndarray  # float64 (N, E)
    second_input_used: np.ndarray  # float64 (S,) second-economy input cell draw
    # --- regional retail (R, G) ----------------------------------------------
    retail_available: np.ndarray  # float64 (R, G)
    retail_sales: np.ndarray  # float64 (R, G)
    retail_unmet: np.ndarray  # float64 (R, G)
    # --- trade (G,) + channel scalars -----------------------------------------
    imports: np.ndarray  # float64 (G,) realized total
    cmea_imports: np.ndarray  # float64 (G,)
    convertible_imports: np.ndarray  # float64 (G,)
    cmea_exports: np.ndarray  # float64 (G,)
    convertible_exports: np.ndarray  # float64 (G,)
    cmea_import_payment: float
    cmea_export_receipt: float
    usd_import_payment: float
    usd_export_receipt: float
    usd_interest_paid: float
    usd_interest_accrued: float
    usd_principal_paid: float
    usd_loan_drawn: float
    official_fx_translation: float | None  # diagnostic only
    expired_services: float  # services that expired unused this tick
    # --- journal (typed columns; represented amounts) ---------------------------
    journal_kind: list[str] = field(default_factory=list)
    journal_tick: list[int] = field(default_factory=list)
    journal_debit: list[int] = field(default_factory=list)
    journal_credit: list[int] = field(default_factory=list)
    journal_currency: list[str] = field(default_factory=list)
    journal_amount: list[float] = field(default_factory=list)
    journal_org: list[int | None] = field(default_factory=list)
    journal_leg: list[int] = field(default_factory=list)

    # --- residual snapshots (filled by engine.accounting) ------------------------
    material_balance_residual: np.ndarray | None = None
    material_balance_tolerance: np.ndarray | None = None
    finance_balance_residual: np.ndarray | None = None
    finance_balance_tolerance: np.ndarray | None = None


@dataclass
class MaterialHistory:
    """Compact per-tick trajectory buffers (dict rows per table)."""

    aggregate_rows: list[dict[str, object]] = field(default_factory=list)
    stage_rows: list[dict[str, object]] = field(default_factory=list)
    national_rows: list[dict[str, object]] = field(default_factory=list)
    budget_rows: list[dict[str, object]] = field(default_factory=list)
    organization_rows: list[dict[str, object]] = field(default_factory=list)
    financial_rows: list[dict[str, object]] = field(default_factory=list)
    department_rows: list[dict[str, object]] = field(default_factory=list)
    diagnostic_rows: list[dict[str, object]] = field(default_factory=list)
    event_rows: list[dict[str, object]] = field(default_factory=list)
    digest_chain: str = ""


def material_tick_event() -> str:
    """The only per-tick event literal the material runner emits."""
    return "material_tick_completed"


def initial_conditions_scenario_guard(spec: ScenarioSpec) -> None:
    """Cheap structural assert reused by builders (kind/kind-fields coherence)."""
    if spec.kind == "material":
        if spec.material_parameters is None or spec.material_initial is None:
            raise ValueError("material scenario lacks parameters/initial recipe")


__all__ = [
    "MATERIAL_STATE_VERSION",
    "N_D",
    "N_E",
    "N_H",
    "N_Q",
    "MaterialForcing",
    "MaterialHistory",
    "MaterialPrices",
    "MaterialState",
    "MaterialStockSnapshot",
    "MaterialTickFlows",
    "POOL_CODES",
    "build_material_prices",
    "capture_material_stocks",
    "initial_conditions_scenario_guard",
    "initialize_material",
    "material_state_shapes",
    "material_tick_event",
    "owner_kind_code",
]

# ----------------------------------------------------------------------
# P02 builders (ST additions): prices, initial state and opening snapshots.
# Imports live here so the pinned declarations above stay byte-identical.


def build_material_prices(parameters: MaterialParameters) -> MaterialPrices:
    """Compile the readonly admin price view (plan step 1 price vector)."""
    standard = np.array(parameters.prices, dtype=np.float64)
    return MaterialPrices(standard=standard, food_raw=float(parameters.food_raw_price))


def _dense_bank_index(
    organizations: tuple[OrganizationSpec, ...],
) -> tuple[np.ndarray, dict[int, int]]:
    """Per-organization dense bank index (-1 for banks themselves)."""
    bank_ids = sorted(
        spec.organization_id for spec in organizations if spec.type == OrganizationType.BANK
    )
    if not bank_ids:
        raise ValueError("material scenario requires at least one bank organization")
    position = {bank_id: index for index, bank_id in enumerate(bank_ids)}
    dense = np.full(len(organizations), -1, dtype=np.int32)
    for row, spec in enumerate(organizations):
        if spec.type == OrganizationType.BANK:
            continue
        if spec.bank_id is None or spec.bank_id not in position:
            raise ValueError(
                f"organization {spec.organization_id} binds unknown bank {spec.bank_id!r}"
            )
        dense[row] = position[spec.bank_id]
    return dense, position


def _check_network_alignment(initial: MaterialInitialConditions, network: MaterialNetwork) -> None:
    """Fail closed when the compiled network disagrees with the initial draw."""
    cell_columns = (
        network.cell_owner_kind,
        network.cell_owner_id,
        network.cell_region,
        network.cell_pool,
        network.cell_commodity,
        network.cell_stage,
    )
    cell_count = int(np.asarray(cell_columns[0]).shape[0])
    if any(np.asarray(column).shape != (cell_count,) for column in cell_columns):
        raise ValueError("network cell catalog columns disagree in length")
    if tuple(network.commodity_ids) != tuple(initial.commodity_ids):
        raise ValueError("network commodity axis does not match the initial conditions")
    if tuple(network.region_ids) != tuple(initial.region_ids):
        raise ValueError("network region axis does not match the initial conditions")
    activity_count = int(np.asarray(network.activity_kind).shape[0])
    for name in ("activity_org_index", "activity_region", "activity_capacity"):
        if np.asarray(getattr(network, name)).shape != (activity_count,):
            raise ValueError(f"network {name} does not match the activity axis")
    input_count = int(np.asarray(network.input_activity).shape[0])
    if np.asarray(network.input_cell).shape != (input_count,):
        raise ValueError("network input_cell/input_activity disagree in length")
    if network.A.shape != (activity_count, input_count):
        raise ValueError("network A matrix does not match its activity/input axes")
    if network.B.shape != (activity_count, cell_count):
        raise ValueError("network B matrix does not match its activity/cell axes")


def initialize_material(
    spec: ScenarioSpec,
    initial: MaterialInitialConditions,
    network: MaterialNetwork,
) -> MaterialState:
    """Build the opening state from the single initialization draw (plan §3).

    ``initial`` is readonly — every array is copied, nothing is re-drawn.
    Org input/output cells hold ``initial_recipe`` quarters of one quarter's
    A/B target flow at ``min(utilization * capacity, labor cap)`` with
    seasonal factor 1; plot cells hold exactly one quarter of the plot
    target flow; wholesale, retail, project-WIP, import-pool and the
    non-stockable services cells open at zero. Deposit liabilities include
    weighted household cash, non-bank organization deposits and the
    Treasury fiscal account (bank dense index 0); reserves balance the
    sheet: ``reserves = deposits + equity - loans``.
    """
    initial_conditions_scenario_guard(spec)
    _check_network_alignment(initial, network)

    parameters = initial.parameters
    recipe = initial.initial_recipe
    region_ids = initial.region_ids
    commodity_ids = initial.commodity_ids
    region_count = len(region_ids)
    org_count = initial.organization_count

    # --- organizations: static identity + seeded dynamic fields ------------
    org_specs = initial.organizations
    region_index = {region: index for index, region in enumerate(region_ids)}
    technology_index = {
        tech.technology_id: index for index, tech in enumerate(initial.technologies)
    }
    for s in org_specs:
        if s.technology_id is not None and s.technology_id not in technology_index:
            raise ValueError(
                f"organization {s.organization_id} declares unknown technology {s.technology_id!r}"
            )
    organization_id = np.array([s.organization_id for s in org_specs], dtype=np.int64)
    organization_type = np.array(
        [ORGANIZATION_TYPE_ORDER.index(s.type) for s in org_specs], dtype=np.int8
    )
    organization_region = np.array([region_index[s.region_id] for s in org_specs], dtype=np.int32)
    organization_technology = np.array(
        [-1 if s.technology_id is None else technology_index[s.technology_id] for s in org_specs],
        dtype=np.int32,
    )
    organization_capacity = np.array([s.capacity for s in org_specs], dtype=np.float64)
    organization_labor_available = np.array(
        [s.labor_available for s in org_specs], dtype=np.float64
    )
    organization_labor_per_activity = np.array(
        [0.0 if s.labor_per_activity is None else s.labor_per_activity for s in org_specs],
        dtype=np.float64,
    )
    organization_cash = np.array([s.initial_cash for s in org_specs], dtype=np.float64)
    organization_principal = np.array(
        [s.initial_loan_principal for s in org_specs], dtype=np.float64
    )
    organization_bailout_expectation = np.array(
        [s.initial_bailout_expectation for s in org_specs], dtype=np.float64
    )
    organization_bank, bank_position = _dense_bank_index(org_specs)
    bank_count = len(bank_position)

    # --- activity axis: org rows from the network, one activity per org ----
    activity_kind = np.asarray(network.activity_kind)
    activity_count = int(activity_kind.shape[0])
    org_activity_mask = activity_kind == 0
    org_activity_rows = np.nonzero(org_activity_mask)[0]
    org_axis_rows = np.asarray(network.activity_org_index)[org_activity_rows]
    organization_activity = np.full(org_count, -1, dtype=np.int32)
    if org_axis_rows.size:
        if int(org_axis_rows.min()) < 0 or int(org_axis_rows.max()) >= org_count:
            raise ValueError("network org activity references an unknown organization row")
        if np.unique(org_axis_rows).size != org_axis_rows.size:
            raise ValueError("an organization row carries more than one activity")
        organization_activity[org_axis_rows] = org_activity_rows

    # --- plots: land/labor budgets derived here from the household draw ----
    households = initial.households
    household_id = np.array(households.household_id, dtype=np.int64, copy=True)
    household_region = np.array(households.region, dtype=np.int32, copy=True)
    household_weight = np.array(households.weight, dtype=np.float64, copy=True)
    household_size = np.array(households.size, dtype=np.float64, copy=True)
    household_count = int(household_id.shape[0])
    if household_region.size and (
        int(household_region.min()) < 0 or int(household_region.max()) >= region_count
    ):
        raise ValueError("household region index outside the declared region axis")
    participating = np.asarray(households.plot_participating, dtype=bool)
    participating_persons = np.bincount(
        household_region[participating],
        weights=(household_weight * household_size)[participating],
        minlength=region_count,
    ).astype(np.float64, copy=True)
    plot_recipe = initial.plot_recipe
    plot_capacity = participating_persons * plot_recipe.capacity_per_participating_person
    plot_labor_budget = participating_persons * plot_recipe.spare_time_labor_fraction
    plot_activity = np.full(region_count, -1, dtype=np.int32)
    plot_rows = np.nonzero(activity_kind == 1)[0]
    plot_row_regions = np.asarray(network.activity_region)[plot_rows]
    if (
        plot_rows.size != region_count
        or int(plot_row_regions.min()) < 0
        or int(plot_row_regions.max()) >= region_count
        or np.unique(plot_row_regions).size != region_count
    ):
        raise ValueError("network must carry exactly one plot activity per region")
    plot_activity[plot_row_regions] = plot_rows

    # --- one quarter of target flow (seasonal factor 1 at initialization) --
    utilization = float(parameters.utilization)
    target = np.zeros(activity_count, dtype=np.float64)
    if org_axis_rows.size:
        per_activity = organization_labor_per_activity[org_axis_rows]
        if np.any(per_activity <= 0.0):
            raise ValueError("productive activity lacks a positive labor_per_activity")
        target[org_activity_rows] = np.minimum(
            utilization * organization_capacity[org_axis_rows],
            organization_labor_available[org_axis_rows] / per_activity,
        )
    plot_target = np.minimum(
        utilization * plot_capacity,
        plot_labor_budget / plot_recipe.plot_labor_per_activity,
    )
    target[plot_rows] = plot_target[plot_row_regions]

    # --- authoritative stock cells ----------------------------------------
    cell_count = int(np.asarray(network.cell_owner_kind).shape[0])
    stock_value = np.zeros(cell_count, dtype=np.float64)
    input_quarters = np.where(org_activity_mask, float(recipe.input_stock_quarters), 1.0)
    output_quarters = np.where(org_activity_mask, float(recipe.output_stock_quarters), 1.0)
    a_rows = np.repeat(np.arange(activity_count), np.diff(np.asarray(network.A.indptr)))
    a_amounts = np.asarray(network.A.data) * target[a_rows] * input_quarters[a_rows]
    np.add.at(stock_value, np.asarray(network.input_cell)[np.asarray(network.A.indices)], a_amounts)
    b_rows = np.repeat(np.arange(activity_count), np.diff(np.asarray(network.B.indptr)))
    b_amounts = np.asarray(network.B.data) * target[b_rows] * output_quarters[b_rows]
    np.add.at(stock_value, np.asarray(network.B.indices), b_amounts)
    if "services_transport" in commodity_ids:  # never stockable, opens at zero
        services = commodity_ids.index("services_transport")
        stock_value[np.asarray(network.cell_commodity) == services] = 0.0
    if not np.all(np.isfinite(stock_value)):
        raise ValueError("initial material stock contains non-finite values")
    if np.any(stock_value < 0.0):
        raise ValueError("initial material stock must be non-negative")

    # --- households / regional stocks --------------------------------------
    household_cash = np.full(household_count, float(recipe.household_cash), dtype=np.float64)
    household_deferred_receipt = np.zeros(household_count, dtype=np.float64)
    household_wage_claim = np.zeros(household_count, dtype=np.float64)
    region_persons = np.array(initial.region_equivalent_persons, dtype=np.float64, copy=True)
    if region_persons.shape != (region_count,):
        raise ValueError("region_equivalent_persons must match the region axis")
    dwelling_stock = float(recipe.dwelling_per_person) * region_persons
    # Per-household dwelling access ≈ min(1, stock / represented households).
    household_total_region = np.bincount(
        household_region, weights=household_weight, minlength=region_count
    )
    access_share = np.minimum(
        1.0,
        dwelling_stock / np.maximum(household_total_region, 1e-12),
    )
    household_dwelling_access = access_share[household_region]
    housing_vacant = np.maximum(
        dwelling_stock
        - np.bincount(
            household_region,
            weights=household_weight * household_dwelling_access,
            minlength=region_count,
        ),
        0.0,
    )

    household_parameters = initial.household_parameters
    catalog = initial.household_catalog
    if household_parameters is None or catalog is None:
        raise ValueError("initial conditions must carry household parameters and catalog")

    durable_owned = np.asarray(households.durable_owned, dtype=np.float64).copy()
    household_tenure = np.asarray(households.tenure, dtype=np.int8).copy()
    household_informal_access = np.asarray(households.informal_access, dtype=np.float64).copy()

    # reference income = national nominal wage pool * pay share (must be > 0)
    pay_weight = np.asarray(households.pay_weight, dtype=np.float64)
    national_wage_pool = float(parameters.wage_rate) * float(organization_labor_available.sum())
    pay_total = float((household_weight * pay_weight).sum())
    if pay_total > 0.0:
        pay_share = pay_weight / pay_total
    else:
        # No pay weight (tiny zero-labor fixtures): fall back to a flat
        # represented-household split so the reference scale stays finite.
        weight_total = float(household_weight.sum())
        pay_share = np.where(weight_total > 0.0, household_weight / weight_total, 0.0)
    reference_income = national_wage_pool * pay_share

    initial_entitlement = np.asarray(
        household_parameters.expectations.initial_entitlement, dtype=np.float64
    )
    household_entitlement = np.tile(initial_entitlement, (household_count, 1))
    household_expectation = household_entitlement.copy()

    equivalence = (
        np.asarray(households.adults, dtype=np.float64)
        + 0.7 * np.asarray(households.children, dtype=np.float64)
        + 0.9 * np.asarray(households.elderly, dtype=np.float64)
    )
    base = np.asarray(household_parameters.demand.base_per_equivalent_person, dtype=np.float64)
    consumption_reference = base[None, :] * equivalence[:, None]
    last_price_index = np.ones(household_count, dtype=np.float64)
    compliance = np.full(
        household_count, household_parameters.welfare.compliance_baseline, dtype=np.float64
    )

    # --- finance: deposits/equity/reserves, treasury and foreign accounts --
    national_wage_bill = float(parameters.wage_rate) * float(organization_labor_available.sum())
    treasury_deposit = float(recipe.treasury_deposit_quarters) * national_wage_bill
    # M2-neutral distribution working capital: the Treasury's idle opening
    # deposit funds the wholesale/retail bridge (already included in the
    # generated organizations' initial cash), so total money is unchanged.
    treasury_deposit -= float(initial.distribution_working_capital)
    if treasury_deposit < 0.0:
        raise ResearchGateError(
            "distribution working capital exceeds the Treasury's opening deposit; "
            "reduce distribution_working_capital_quarters"
        )
    nonbank = organization_bank >= 0
    bank_deposit_liability = np.zeros(bank_count, dtype=np.float64)
    bank_deposit_liability += np.bincount(
        organization_bank[nonbank],
        weights=organization_cash[nonbank],
        minlength=bank_count,
    )
    bank_deposit_liability += np.bincount(
        household_region % bank_count,
        weights=household_weight * household_cash,
        minlength=bank_count,
    )
    bank_deposit_liability[0] += treasury_deposit  # Treasury banks at index 0
    bank_equity = np.full(
        bank_count,
        float(recipe.bank_equity_quarters) * national_wage_bill,
        dtype=np.float64,
    )
    bank_loan_asset = np.bincount(
        organization_bank[nonbank],
        weights=organization_principal[nonbank],
        minlength=bank_count,
    ).astype(np.float64, copy=True)
    bank_reserves = bank_deposit_liability + bank_equity - bank_loan_asset
    bank_interest_receivable = np.zeros(bank_count, dtype=np.float64)

    return MaterialState(
        schema_version=MATERIAL_STATE_VERSION,
        completed_ticks=0,
        stock_value=stock_value,
        household_id=household_id,
        household_region=household_region,
        household_weight=household_weight,
        household_size=household_size,
        household_cash=household_cash,
        household_deferred_receipt=household_deferred_receipt,
        household_wage_claim=household_wage_claim,
        household_urban=np.asarray(households.urban, dtype=bool).copy(),
        household_occupation=np.asarray(households.occupation, dtype=np.int8).copy(),
        household_sector=np.asarray(households.sector, dtype=np.int16).copy(),
        household_education=np.asarray(households.education, dtype=np.int8).copy(),
        household_children=np.asarray(households.children, dtype=np.int16).copy(),
        household_adults=np.asarray(households.adults, dtype=np.int16).copy(),
        household_elderly=np.asarray(households.elderly, dtype=np.int16).copy(),
        household_working_adults=np.asarray(households.working_adults, dtype=np.float64).copy(),
        household_pay_weight=pay_weight.copy(),
        household_plot_participating=participating.copy(),
        household_second_participating=np.asarray(
            households.second_participating, dtype=bool
        ).copy(),
        household_western_exposure=np.asarray(households.western_exposure, dtype=np.float64).copy(),
        household_tenure=household_tenure,
        household_informal_access=household_informal_access,
        household_dwelling_access=household_dwelling_access,
        household_housing_wait=np.zeros(household_count, dtype=np.int32),
        household_last_income=reference_income.copy(),
        household_reference_income=reference_income.copy(),
        household_last_price_index=last_price_index,
        household_reserved_plot_hours=np.zeros(household_count, dtype=np.float64),
        household_reserved_second_hours=np.zeros(household_count, dtype=np.float64),
        household_formal_effort=np.ones(household_count, dtype=np.float64),
        household_material_satisfaction=np.full(household_count, 0.5, dtype=np.float64),
        household_political_compliance=compliance,
        household_grievance=np.zeros(household_count, dtype=np.float64),
        household_durable_owned=durable_owned,
        household_durable_age=np.zeros((household_count, durable_owned.shape[1]), dtype=np.float64),
        household_durable_backlog=np.zeros(
            (household_count, durable_owned.shape[1]), dtype=np.float64
        ),
        household_durable_wait=np.zeros((household_count, durable_owned.shape[1]), dtype=np.int32),
        household_durable_repair_credit=np.zeros(
            (household_count, durable_owned.shape[1]), dtype=np.float64
        ),
        household_consumption_reference=consumption_reference,
        household_last_consumption=consumption_reference.copy(),
        household_last_availability_unmet=np.zeros(
            (household_count, len(catalog.household_good_ids)), dtype=np.float64
        ),
        household_entitlement=household_entitlement,
        household_expectation=household_expectation,
        household_improvement_streak=np.zeros(
            (household_count, household_entitlement.shape[1]), dtype=np.int32
        ),
        dwelling_stock=dwelling_stock,
        housing_vacant=housing_vacant,
        second_output_stock=np.zeros((region_count, len(commodity_ids)), dtype=np.float64),
        organization_id=organization_id,
        organization_type=organization_type,
        organization_region=organization_region,
        organization_technology=organization_technology,
        organization_activity=organization_activity,
        organization_bank=organization_bank,
        organization_capacity=organization_capacity,
        organization_labor_available=organization_labor_available,
        organization_labor_endowment=organization_labor_available.copy(),
        organization_effort_factor=np.ones(org_count, dtype=np.float64),
        organization_labor_per_activity=organization_labor_per_activity,
        organization_cash=organization_cash,
        organization_wage_arrears=np.zeros(org_count, dtype=np.float64),
        organization_interest_arrears=np.zeros(org_count, dtype=np.float64),
        organization_principal=organization_principal,
        organization_shortage_expectation=np.zeros(org_count, dtype=np.float64),
        organization_bailout_expectation=organization_bailout_expectation,
        organization_project_approved=np.zeros(org_count, dtype=np.float64),
        organization_capital_wip=np.zeros(org_count, dtype=np.float64),
        organization_construction_wip=np.zeros(org_count, dtype=np.float64),
        organization_capital_age=np.zeros(org_count, dtype=np.float64),
        plot_capacity=plot_capacity,
        plot_labor_budget=plot_labor_budget,
        plot_activity=plot_activity,
        bank_reserves=bank_reserves,
        bank_loan_asset=bank_loan_asset,
        bank_deposit_liability=bank_deposit_liability,
        bank_equity=bank_equity,
        bank_interest_receivable=bank_interest_receivable,
        treasury_deposit=treasury_deposit,
        usd_reserve=float(parameters.trade.convertible_opening_reserve),
        usd_principal=float(parameters.trade.convertible_opening_principal),
        usd_interest_arrears=0.0,
        cmea_settlement_balance=0.0,
    )


def capture_material_stocks(state: MaterialState) -> MaterialStockSnapshot:
    """Deep-copy the mutable opening boundary (arrays share no memory)."""
    return MaterialStockSnapshot(
        stock_value=state.stock_value.copy(),
        household_cash=state.household_cash.copy(),
        organization_cash=state.organization_cash.copy(),
        dwelling_stock=state.dwelling_stock.copy(),
        housing_vacant=state.housing_vacant.copy(),
        household_durable_owned=state.household_durable_owned.copy(),
        household_dwelling_access=state.household_dwelling_access.copy(),
        household_informal_access=state.household_informal_access.copy(),
        household_entitlement=state.household_entitlement.copy(),
        household_expectation=state.household_expectation.copy(),
        second_output_stock=state.second_output_stock.copy(),
        bank_reserves=state.bank_reserves.copy(),
        bank_loan_asset=state.bank_loan_asset.copy(),
        bank_deposit_liability=state.bank_deposit_liability.copy(),
        bank_equity=state.bank_equity.copy(),
        bank_interest_receivable=state.bank_interest_receivable.copy(),
        treasury_deposit=float(state.treasury_deposit),
        usd_reserve=float(state.usd_reserve),
        usd_principal=float(state.usd_principal),
        usd_interest_arrears=float(state.usd_interest_arrears),
        cmea_settlement_balance=float(state.cmea_settlement_balance),
        organization_cash_open=state.organization_cash.copy(),
        organization_principal=state.organization_principal.copy(),
        organization_wage_arrears=state.organization_wage_arrears.copy(),
        organization_interest_arrears=state.organization_interest_arrears.copy(),
        organization_shortage_expectation=state.organization_shortage_expectation.copy(),
        organization_bailout_expectation=state.organization_bailout_expectation.copy(),
        organization_project_approved=state.organization_project_approved.copy(),
        organization_capital_wip=state.organization_capital_wip.copy(),
        organization_construction_wip=state.organization_construction_wip.copy(),
        organization_capacity=state.organization_capacity.copy(),
        household_wage_claim=state.household_wage_claim.copy(),
        household_deferred_receipt=state.household_deferred_receipt.copy(),
        completed_ticks=int(state.completed_ticks),
    )


def material_state_shapes(state: MaterialState) -> dict[str, tuple[int, ...]]:
    """Shape map of every ndarray field (diagnostics/tests)."""
    import dataclasses

    shapes: dict[str, tuple[int, ...]] = {}
    for f in dataclasses.fields(state):
        value = getattr(state, f.name)
        if isinstance(value, np.ndarray):
            shapes[f.name] = tuple(int(n) for n in value.shape)
    return shapes
