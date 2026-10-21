"""H4B execution bridge: price-category and investment-approval decisions."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.contract.material import commodity_spec
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.material import load_material_forcing
from hsm_lab.engine.network import build_material_network
from hsm_lab.engine.policy import compile_price_override
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import build_material_prices, initialize_material
from hsm_lab.institutions.decisions import (
    ActorRole,
    InvestmentDecision,
    PriceProposalDecision,
    PriceProposalKind,
)
from hsm_lab.institutions.execution_adapter import commit_proposal
from hsm_lab.institutions.price_regimes import PriceCategoryRule, PriceRegime
from hsm_lab.institutions.schemas import (
    AuthorityScope,
    DateInterval,
    InstitutionEvent,
    RegimeCalendar,
)
from tests.test_hist_tiny_execution import _validation, make_tiny
from tests.test_material import _partial_project_fixture

REPO_ROOT = Path(__file__).resolve().parents[1]


def _day(year: int, month: int) -> DateInterval:
    return DateInterval(
        earliest=date(year, month, 1),
        latest=date(year, month, 1),
        precision="day",
    )


def _calendar(inv_org: str = "1") -> RegimeCalendar:
    def grant(event_id: str, permission: str, org: str = "") -> InstitutionEvent:
        return InstitutionEvent(
            event_id=event_id,
            permission=permission,
            scope=AuthorityScope(
                organization_ids=(org,) if org else (),
                sector_ids=("industry",),
                excluded_sector_ids=(),
                geographic_ids=(),
            ),
            action="grant",
            proposal_date=_day(1955, 1),
            approval_date=_day(1955, 6),
            enactment_date=_day(1956, 1),
            effective_from=_day(1956, 1),
            effective_to=None,
            observed_implementation_at=None,
            source_available_at=_day(1955, 1),
            issuer="synthetic",
            legal_force="enactment",
            source_ids=("synthetic:h4b-bridge-test",),
            synthetic_flag=True,
            confidence_reason="synthetic test",
            search_tags=(),
        )

    return RegimeCalendar(
        events=(
            grant("PRICE-GRANT", "price_setting"),
            grant("INVEST-GRANT", "investment_approval", org=inv_org),
        )
    )


def _regime() -> PriceRegime:
    return PriceRegime(
        categories=[
            PriceCategoryRule(
                category_id="energy",
                commodity_ids=["energy"],
                regime="authorized_adjustment",
            ),
            PriceCategoryRule(
                category_id="food-fixed",
                commodity_ids=["food"],
                regime="fixed",
            ),
        ]
    )


def test_declared_price_regime_covers_all_f2_commodities() -> None:
    from hsm_lab.contract.guards import load_scenario

    spec = load_scenario(REPO_ROOT, "historical_f2_replay")
    regime = PriceRegime.model_validate_json(
        (REPO_ROOT / "config/price_regimes/hist_vnext_h4b_v1.json").read_text()
    )
    regime.validate_commodities(tuple(spec.commodities))
    assert regime.rule_for("g03_electricity_heat").regime == "fixed"
    assert (
        regime.rule_for("g06_machinery_capital").regime == "authorized_adjustment"
    )


def _f2_fixture():
    spec = load_scenario(REPO_ROOT, "historical_f2_replay")
    contract = load_research_contract(REPO_ROOT)
    registry = DataRegistry.load(REPO_ROOT, allowed_commodities=list(spec.commodities))
    initial = build_material_initial_conditions(spec, RngRegistry(spec.seed))
    network = build_material_network(spec, contract, initial)
    state = initialize_material(spec, initial, network)
    forcing = load_material_forcing(spec, registry)
    return state, forcing, spec, network


def test_price_bridge_executes_on_real_f2_scenario() -> None:
    state, forcing, spec, network = _f2_fixture()
    decision = _price(commodity_id="g06_machinery_capital", price=99.0)
    regime = PriceRegime.model_validate_json(
        (REPO_ROOT / "config/price_regimes/hist_vnext_h4b_v1.json").read_text()
    )
    target_index = tuple(spec.commodities).index("g06_machinery_capital")
    overridden, _catalog = compile_price_override(
        spec.material_parameters,
        spec.household_parameters,
        commodity_index=target_index,
        price=99.0,
        commodity_ids=tuple(spec.commodities),
    )
    for index, (old, new) in enumerate(
        zip(spec.material_parameters.prices, overridden.prices, strict=True)
    ):
        if index != target_index:
            assert new == old

    result = commit_proposal(
        decision,
        _validation(decision),
        state,
        forcing,
        spec.material_parameters,
        network,
        authority_calendar=_calendar(),
        price_regime=regime,
    )
    assert result.is_committed, result.reason
    trace = dict(result.trace)
    assert trace["new_price"] == 99.0
    assert trace["old_price"] != 99.0
    assert state.completed_ticks == 1


def test_raw_food_override_changes_the_effective_raw_price() -> None:
    _state, _forcing, spec, _network = _f2_fixture()
    commodity_ids = tuple(spec.commodities)
    index = commodity_ids.index("g08_agricultural_raw")
    material, _catalog = compile_price_override(
        spec.material_parameters,
        spec.household_parameters,
        commodity_index=index,
        price=99.0,
        commodity_ids=commodity_ids,
    )
    assert material.food_raw_price == 99.0
    assert build_material_prices(material).food_raw == 99.0
    stage = commodity_spec("g08_agricultural_raw").consumable_stage()
    assert build_material_prices(material).price_for(index, stage) == 99.0


def _price(
    *,
    commodity_id: str = "energy",
    price: float = 20.0,
    decision_id: str = "price-1",
) -> PriceProposalDecision:
    return PriceProposalDecision(
        decision_id=decision_id,
        actor_role=ActorRole.APPROVER,
        organization_id="3",
        sector_id="industry",
        quarter="1957Q1",
        decision_at=date(1957, 1, 15),
        available_at=date(1957, 1, 10),
        kind=PriceProposalKind.SET,
        commodity_id=commodity_id,
        proposed_price=price,
    )


def _investment(
    *,
    organization_id: str = "1",
    amount: float = 50.0,
    decision_id: str = "inv-1",
) -> InvestmentDecision:
    return InvestmentDecision(
        decision_id=decision_id,
        actor_role=ActorRole.INVESTMENT_ORGANIZATION,
        organization_id=organization_id,
        sector_id="industry",
        quarter="1957Q1",
        decision_at=date(1957, 1, 15),
        available_at=date(1957, 1, 10),
        kind="request",
        project_id="P1",
        requested_amount=amount,
    )


def test_price_decision_changes_only_the_target_price() -> None:
    tiny = make_tiny()
    decision = _price()
    result = commit_proposal(
        decision,
        _validation(decision),
        tiny.state,
        tiny.forcing(4),
        tiny.parameters,
        tiny.network,
        authority_calendar=_calendar(),
        price_regime=_regime(),
    )
    assert result.is_committed, result.reason
    trace = dict(result.trace)
    assert trace["control"] == "price_override"
    assert trace["category_id"] == "energy"
    assert trace["new_price"] == 20.0
    assert trace["old_price"] != trace["new_price"]
    assert trace["binding_status"] == "changed"
    assert tiny.state.completed_ticks == 1


def test_fixed_price_category_rejects_the_proposal() -> None:
    tiny = make_tiny()
    decision = _price(commodity_id="food", decision_id="price-fixed")
    result = commit_proposal(
        decision,
        _validation(decision),
        tiny.state,
        tiny.forcing(4),
        tiny.parameters,
        tiny.network,
        authority_calendar=_calendar(),
        price_regime=_regime(),
    )
    assert not result.is_committed
    assert "fixed" in result.reason
    assert tiny.state.completed_ticks == 0


def test_price_bridge_fails_closed_without_authority_or_regime() -> None:
    tiny = make_tiny()
    decision = _price(decision_id="price-no-auth")
    no_auth = commit_proposal(
        decision,
        _validation(decision),
        tiny.state,
        tiny.forcing(4),
        tiny.parameters,
        tiny.network,
        price_regime=_regime(),
    )
    assert not no_auth.is_committed
    assert "authority calendar" in no_auth.reason

    no_regime = commit_proposal(
        decision,
        _validation(decision),
        tiny.state,
        tiny.forcing(4),
        tiny.parameters,
        tiny.network,
        authority_calendar=_calendar(),
    )
    assert not no_regime.is_committed
    assert "price regime" in no_regime.reason
    assert tiny.state.completed_ticks == 0


def test_investment_approval_caps_new_capacity_and_is_auditable() -> None:
    fixture = _partial_project_fixture()
    # Positive hunger makes the unconstrained request large, so the cap binds.
    parameters = fixture.parameters.model_copy(
        update={"capital_depreciation_rate": 10.0}
    )
    decision = _investment(organization_id="2", amount=1.0)
    result = commit_proposal(
        decision,
        _validation(decision),
        fixture.state,
        fixture.forcing(2),
        parameters,
        fixture.network,
        organization_index={"2": 2},
        authority_calendar=_calendar(inv_org="2"),
    )
    assert result.is_committed, result.reason
    trace = dict(result.trace)
    assert trace["control"] == "investment_approvals"
    assert trace["approved_capacity"] > 0.0
    assert trace["unit_cost"] > 0.0
    assert trace["approved_capacity"] <= 2.0 + 1e-9
    assert trace["investment_requested"] <= 2.0 + 1e-9
    assert trace["investment_approved"] <= 2.0 + 1e-9
    assert trace["baseline_investment_requested"] > trace["investment_requested"]
    assert result.flows.organization_investment_requested[2] <= 2.0 + 1e-9
    assert fixture.state.completed_ticks == 1


def test_investment_approval_rejects_unauthorized_organization() -> None:
    fixture = _partial_project_fixture()
    decision = _investment(organization_id="3", decision_id="inv-unauth")
    result = commit_proposal(
        decision,
        _validation(decision),
        fixture.state,
        fixture.forcing(2),
        fixture.parameters,
        fixture.network,
        organization_index={"3": 3},
        authority_calendar=_calendar(inv_org="2"),
    )
    assert not result.is_committed
    assert "investment_approval authority" in result.reason
    assert fixture.state.completed_ticks == 0


def test_investment_bridge_requires_authority_calendar() -> None:
    fixture = _partial_project_fixture()
    decision = _investment(organization_id="2", decision_id="inv-no-cal")
    result = commit_proposal(
        decision,
        _validation(decision),
        fixture.state,
        fixture.forcing(2),
        fixture.parameters,
        fixture.network,
        organization_index={"2": 2},
    )
    assert not result.is_committed
    assert "authority calendar" in result.reason
    assert fixture.state.completed_ticks == 0
