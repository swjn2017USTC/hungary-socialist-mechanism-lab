"""H5F-F1 / M09: real forecast error and information-rule transmission.

The runner issues one-quarter-ahead forecasts from two already-published
physical-output reports, applies the same frozen procurement mapping in four
information/rule arms (delay 0/1 x persistence/linear), executes each arm
through the reviewed H2B ``commit_proposal`` bridge and scores the frozen
forecasts against the kernel's own realized output.

This is a synthetic, material-only engineering study.  It is not the blocked
M09 historical validation, does not change the M09 registration, and does not
use the legacy ``forecast_accuracy = capability`` definition as an error.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.guards import load_research_contract, load_scenario, sha256_file
from hsm_lab.contract.material import (
    PURPOSE_CODES,
    STAGE_CODES,
    RoutePurpose,
    commodity_spec,
)
from hsm_lab.contract.schemas import ScenarioSpec
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine import accounting
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.material import (
    canonical_material_bytes,
    load_material_forcing,
    tick_material,
)
from hsm_lab.engine.network import build_material_network
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import capture_material_stocks, initialize_material
from hsm_lab.institutions.authority import authority_at
from hsm_lab.institutions.decisions import (
    ActorRole,
    ProcurementChoiceKind,
    ProcurementDecision,
)
from hsm_lab.institutions.execution_adapter import (
    _base_controls,
    _with_procurement_request,
    commit_proposal,
)
from hsm_lab.institutions.forecast_error_adapter import (
    ForecastReport,
    ForecastResidual,
    IssuedForecast,
    RealizedForecast,
    issue_forecast,
    quarter_day,
    quarter_end,
    score_forecast,
)
from hsm_lab.institutions.observed import ObservationBuilder
from hsm_lab.institutions.proposal_validation import BoundedPlanning, ValidationResult
from hsm_lab.institutions.schemas import (
    AuthorityScope,
    DateInterval,
    InstitutionEvent,
    RegimeCalendar,
)
from hsm_lab.provenance.manifest import (
    canonical_digest,
    canonical_json,
    content_addressed_run_id,
)

SCHEMA_VERSION = "hist_vnext_h5f_f1_m09_v1"
DEFAULT_SPEC = Path("studies/HIST_VNEXT/M09/spec.json")
ARMS = (
    "delay0_persistence",
    "delay0_linear",
    "delay1_persistence",
    "delay1_linear",
)
ARM_DELAY = {
    "delay0_persistence": 0,
    "delay0_linear": 0,
    "delay1_persistence": 1,
    "delay1_linear": 1,
}
ARM_METHOD = {
    "delay0_persistence": "persistence",
    "delay0_linear": "linear",
    "delay1_persistence": "persistence",
    "delay1_linear": "linear",
}
ACTOR_ORGANIZATION_ID = "ORG-ENT-A"
ACTOR_SECTOR_ID = "industry"
ACTOR_GEOGRAPHIC_ID = "national"
COMMODITY_ID = "energy"
STAGE = "standard"
UNIT = "p02_energy_unit"
QUANTITY_CAP = 100.0
ZERO_TOLERANCE = 1e-6

PROTECTED_SHA256 = {
    "BASELINE.md": "1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f",
    "config/research_contract.json": (
        "6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82"
    ),
    "uv.lock": "9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9",
}
M09_CARD_SHA256 = "fa1b30703cda0009471e03cdf6b88b47d20a7ce525385adfdd554f595e55273c"
C0_EXPECTED_DIGEST = "92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d"
C0_EXPECTED_PARAMETER_HASH = (
    "e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445"
)
C1_EXPECTED_DIGEST = "c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5"
C1_EXPECTED_PARAMETER_HASH = (
    "632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90"
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _day(value: str) -> DateInterval:
    parsed = date.fromisoformat(value)
    return DateInterval(earliest=parsed, latest=parsed, precision="day")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(canonical_json(value) + b"\n")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class RunnerError(RuntimeError):
    """A hard study failure: stop, preserve evidence, never fall back."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RunnerError(message)


# ---------------------------------------------------------------------------
# Frozen spec
# ---------------------------------------------------------------------------


def _load_spec(root: Path, spec_path: Path) -> dict[str, Any]:
    path = spec_path if spec_path.is_absolute() else root / spec_path
    spec = _read_json(path)
    _require(spec.get("schema_version") == SCHEMA_VERSION, "unexpected M09 spec schema")
    _require(tuple(spec["arms"]) == ARMS, "spec arms must be the fixed 2x2 matrix")
    _require(tuple(spec["seeds"]) == (1729, 1730, 1731), "spec seeds changed")
    _require(spec["registration_status_changed"] is False, "registration flag changed")
    _require(spec["base_scenario"] == "intermediate8", "base scenario changed")
    _require(spec["scenario_id"] == "hist_vnext_h5f_f1_m09_synthetic", "scenario id changed")
    _require(int(spec["ticks"]) == 8, "spec ticks changed")
    _require(tuple(spec["issue_ticks"]) == (3, 4, 5, 6), "issue ticks changed")
    _require(tuple(spec["target_ticks"]) == (4, 5, 6, 7), "target ticks changed")
    _require(spec["forecast"]["commodity_id"] == COMMODITY_ID, "commodity changed")
    _require(spec["forecast"]["stage"] == STAGE, "stage changed")
    _require(spec["forecast"]["unit"] == UNIT, "unit changed")
    _require(float(spec["procurement"]["quantity_cap"]) == QUANTITY_CAP, "cap changed")
    return spec


def _typed_scenario(
    base: ScenarioSpec, spec: dict[str, Any], *, seed: int, ticks: int
) -> ScenarioSpec:
    updated = base.model_copy(
        update={
            "scenario_id": spec["scenario_id"],
            "ticks": ticks,
            "seed": seed,
        }
    )
    scenario = ScenarioSpec.model_validate(updated.model_dump(mode="python"))
    _require(scenario.ticks == ticks, "typed scenario ticks changed")
    _require(scenario.seed == seed, "typed scenario seed changed")
    _require(scenario.scenario_id == spec["scenario_id"], "typed scenario id changed")
    _require(scenario.politics is None, "synthetic material study must not install politics")
    return scenario


# ---------------------------------------------------------------------------
# Static topology selection (never looks at future production or outcomes)
# ---------------------------------------------------------------------------


def _select_target(network: Any) -> dict[str, Any]:
    commodity_index = tuple(network.commodity_ids).index(COMMODITY_ID)
    consumable_stage = STAGE_CODES[commodity_spec(COMMODITY_ID).consumable_stage()]
    _require(consumable_stage == STAGE_CODES[STAGE], "energy consumable stage changed")

    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    cell_stage = np.asarray(network.cell_stage, dtype=np.int64)
    procurement_purpose = PURPOSE_CODES[RoutePurpose.PROCUREMENT]

    hub_mask = (
        (demand_purpose == procurement_purpose)
        & (cell_commodity[demand_cell] == commodity_index)
        & (cell_stage[demand_cell] == consumable_stage)
        & (cell_owner_kind[demand_cell] == 0)
    )
    hubs = sorted({int(value) for value in cell_owner_id[demand_cell][hub_mask]})
    _require(bool(hubs), "no energy procurement hub exists")
    hub = hubs[0]

    hub_cell_mask = (
        (cell_owner_kind == 0)
        & (cell_owner_id == hub)
        & (cell_commodity == commodity_index)
        & (cell_stage == consumable_stage)
    )
    hub_cells = np.flatnonzero(hub_cell_mask)
    _require(hub_cells.size >= 1, "selected hub has no energy stock cell")
    hub_cell = int(hub_cells[0])

    edge_destination = np.asarray(network.edge_destination_cell, dtype=np.int64)
    edge_source = np.asarray(network.edge_source_cell, dtype=np.int64)
    edge_commodity = np.asarray(network.edge_commodity, dtype=np.int64)
    edge_stage = np.asarray(network.edge_stage, dtype=np.int64)
    edge_purpose = np.asarray(network.edge_purpose, dtype=np.int64)
    route_edges = np.flatnonzero(edge_destination == hub_cell)
    _require(route_edges.size >= 1, "hub cell has no incoming route")

    b_column = network.B.tocsc()
    activity_kind = np.asarray(network.activity_kind, dtype=np.int64)
    activity_org = np.asarray(network.activity_org_index, dtype=np.int64)
    candidates: list[tuple[int, int, int, int, float]] = []
    for edge in route_edges:
        if (
            int(edge_commodity[edge]) != commodity_index
            or int(edge_stage[edge]) != consumable_stage
            or int(edge_purpose[edge]) != procurement_purpose
        ):
            continue
        source_cell = int(edge_source[edge])
        column = b_column.getcol(source_cell).tocoo()
        for activity, coefficient in zip(column.row, column.data, strict=True):
            if int(activity_kind[activity]) != 0:
                continue
            if float(coefficient) <= 0.0:
                continue
            candidates.append(
                (
                    int(activity_org[activity]),
                    int(activity),
                    source_cell,
                    int(edge),
                    float(coefficient),
                )
            )
    _require(bool(candidates), "no routed production source for the hub cell")
    org, activity, source_cell, edge, coefficient = min(candidates)

    return {
        "hub_organization_index": hub,
        "hub_stock_cell": hub_cell,
        "source_organization_index": org,
        "source_activity_index": activity,
        "source_stock_cell": source_cell,
        "route_edge_index": edge,
        "route_edge_id": int(network.edge_id[edge]),
        "route_weight": float(network.edge_weight[edge]),
        "output_coefficient": coefficient,
        "commodity_index": commodity_index,
        "stage_index": consumable_stage,
        "legal_candidate_count": len(candidates),
        "subject_organization_id": f"ORG-SRC-{org}",
        "actor_organization_id": ACTOR_ORGANIZATION_ID,
        "crosswalk": {
            ACTOR_ORGANIZATION_ID: hub,
            f"ORG-SRC-{org}": org,
        },
    }


# ---------------------------------------------------------------------------
# Calendar, admission, decisions
# ---------------------------------------------------------------------------


def _calendar(spec: dict[str, Any]) -> RegimeCalendar:
    calendar = spec["calendar"]
    event = InstitutionEvent(
        event_id="H5F-F1-GRANT-PROCUREMENT",
        permission="procurement",
        scope=AuthorityScope(
            organization_ids=(ACTOR_ORGANIZATION_ID,),
            sector_ids=(ACTOR_SECTOR_ID,),
            geographic_ids=(ACTOR_GEOGRAPHIC_ID,),
            excluded_sector_ids=(),
        ),
        action="grant",
        revokes_event_id=None,
        proposal_date=_day("1957-01-01"),
        approval_date=_day("1957-01-01"),
        enactment_date=_day("1957-01-01"),
        effective_from=_day("1957-01-01"),
        effective_to=None,
        observed_implementation_at=None,
        source_available_at=_day("1957-01-01"),
        issuer="synthetic H5F-F1",
        legal_force="enactment",
        source_ids=("synthetic:h5f-f1-spec",),
        synthetic_flag=True,
        confidence_reason="实验权限，非历史法规",
        search_tags=(),
    )
    _require(calendar.get("event_id") == event.event_id, "calendar event id changed")
    _require(calendar.get("effective_from") == "1957-01-01", "calendar effective date changed")
    return RegimeCalendar(events=(event,))


def _admit(
    decision: ProcurementDecision,
    calendar: RegimeCalendar,
    observation: Any,
) -> tuple[ValidationResult | None, str | None]:
    legal, reason = decision.validate_legality()
    if not legal:
        return None, reason
    bounded, bounded_reason = BoundedPlanning().evaluate(decision, observation)
    if not bounded:
        return None, bounded_reason
    result = authority_at(
        calendar,
        organization_id=decision.organization_id,
        sector_id=decision.sector_id,
        geographic_id=ACTOR_GEOGRAPHIC_ID,
        permission="procurement",
        decision_at=decision.decision_at,
    )
    if result.status != "granted":
        return None, f"procurement authority is {result.status}: {result.reason}"
    digest = hashlib.sha256(decision.model_dump_json().encode("utf-8")).hexdigest()
    return (
        ValidationResult(
            decision_id=decision.decision_id,
            is_legal=True,
            authority_status="granted",
            reason="H5F-F1 admission",
            mode="admission",
            admission_eligible=True,
            decision_digest=digest,
        ),
        None,
    )


def _decision(*, run_id: str, quarter: str, quantity: float) -> ProcurementDecision:
    return ProcurementDecision(
        decision_id=f"{run_id}:{quarter}:procurement",
        actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
        organization_id=ACTOR_ORGANIZATION_ID,
        sector_id=ACTOR_SECTOR_ID,
        quarter=quarter,
        decision_at=quarter_day(quarter, 15),
        available_at=quarter_day(quarter, 10),
        kind=ProcurementChoiceKind.REQUEST,
        commodity_id=COMMODITY_ID,
        requested_quantity=float(quantity),
    )


# ---------------------------------------------------------------------------
# Physical measurement / observation construction
# ---------------------------------------------------------------------------


def _source_production(flows: Any, network: Any, source_cell: int) -> float:
    produced = np.asarray(flows.activity_realized, dtype=np.float64) @ network.B
    return float(np.asarray(produced, dtype=np.float64).reshape(-1)[source_cell])


def _publication_date(measurement_quarter: str, delay: int) -> date:
    from hsm_lab.contract.schemas import Quarter

    publication_quarter = Quarter.parse(measurement_quarter).advance(1 + delay)
    return quarter_day(str(publication_quarter), 10)


def _select_reports(
    archive: Mapping[str, dict[str, Any]],
    *,
    issued_quarter: str,
    issued_at: date,
    delay: int,
    subject: str,
    measurement_factory: ObservationBuilder,
) -> tuple[tuple[ForecastReport, ForecastReport], list[dict[str, Any]]]:
    available: list[tuple[str, dict[str, Any], date]] = []
    for measurement_quarter, entry in archive.items():
        published = _publication_date(measurement_quarter, delay)
        if published <= issued_at:
            available.append((measurement_quarter, entry, published))
    available.sort(key=lambda item: item[0])
    _require(len(available) >= 2, "fewer than two published reports at issuance")
    older, newer = available[-2], available[-1]
    reports: list[ForecastReport] = []
    metadata: list[dict[str, Any]] = []
    for measurement_quarter, entry, published in (older, newer):
        observation = measurement_factory.build(
            organization_id=ACTOR_ORGANIZATION_ID,
            sector_id=ACTOR_SECTOR_ID,
            geographic_id=ACTOR_GEOGRAPHIC_ID,
            quarter=issued_quarter,
            decision_at=issued_at,
            available_at=published,
            raw_data={
                "quarter": issued_quarter,
                "supply_quantity": float(entry["value"]),
            },
        )
        reports.append(
            ForecastReport(
                observation=observation,
                measurement_quarter=measurement_quarter,
                subject_organization_id=subject,
                commodity_id=COMMODITY_ID,
                stage=STAGE,
                unit=UNIT,
            )
        )
        metadata.append(
            {
                "measurement_quarter": measurement_quarter,
                "published_at": published.isoformat(),
                "value": float(entry["value"]),
                "flow_witness_sha256": entry["flow_witness_sha256"],
            }
        )
    return (reports[0], reports[1]), metadata


# ---------------------------------------------------------------------------
# Economics / execution evidence
# ---------------------------------------------------------------------------


def _weighted(values: np.ndarray, weights: np.ndarray, mask: np.ndarray | None = None) -> float:
    if mask is None:
        return float(np.sum(np.asarray(values, dtype=np.float64) * weights))
    return float(np.sum(np.asarray(values, dtype=np.float64)[mask] * weights[mask]))


def _economics(flows: Any, state: Any, network: Any) -> dict[str, Any]:
    weights = np.asarray(state.household_weight, dtype=np.float64)
    region = np.asarray(state.household_region, dtype=np.int64)
    region_ids = tuple(str(value) for value in network.region_ids)
    commodity_ids = tuple(str(value) for value in network.commodity_ids)
    desired = np.asarray(flows.household_desired, dtype=np.float64)
    realized = np.asarray(flows.household_realized, dtype=np.float64)
    affordable = np.asarray(flows.household_affordable, dtype=np.float64)
    unmet = np.asarray(flows.household_availability_unmet, dtype=np.float64)

    energy_index = commodity_ids.index(COMMODITY_ID)
    per_region: list[dict[str, Any]] = []
    for index, region_id in enumerate(region_ids):
        mask = region == index
        desired_value = _weighted(desired[:, energy_index], weights, mask)
        unmet_value = _weighted(unmet[:, energy_index], weights, mask)
        per_region.append(
            {
                "region_id": region_id,
                "realized": _weighted(realized[:, energy_index], weights, mask),
                "affordable": _weighted(affordable[:, energy_index], weights, mask),
                "availability_unmet": unmet_value,
                "desired": desired_value,
                "shortage_share": (
                    unmet_value / desired_value if desired_value > 0.0 else None
                ),
            }
        )
    national_desired = _weighted(desired[:, energy_index], weights)
    national_unmet = _weighted(unmet[:, energy_index], weights)
    commodities = {}
    for index, commodity_id in enumerate(commodity_ids):
        commodities[commodity_id] = {
            "unit": commodity_spec(commodity_id).unit,
            "household_realized": _weighted(realized[:, index], weights),
            "household_affordable": _weighted(affordable[:, index], weights),
            "household_availability_unmet": _weighted(unmet[:, index], weights),
            "household_desired": _weighted(desired[:, index], weights),
        }
    return {
        "unit": UNIT,
        "energy": {
            "national": {
                "realized": _weighted(realized[:, energy_index], weights),
                "affordable": _weighted(affordable[:, energy_index], weights),
                "availability_unmet": national_unmet,
                "desired": national_desired,
                "shortage_share": (
                    national_unmet / national_desired if national_desired > 0.0 else None
                ),
            },
            "per_region": per_region,
        },
        "other_commodities": commodities,
    }


def _economics_summary(
    tick_records: list[dict[str, Any]], *, target_ticks: Sequence[int]
) -> list[dict[str, Any]]:
    target_set = {int(value) for value in target_ticks}
    grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for record in tick_records:
        if record.get("arm") == "warmup" or int(record["tick"]) not in target_set:
            continue
        grouped.setdefault((int(record["seed"]), str(record["arm"])), []).append(record)

    summaries: list[dict[str, Any]] = []
    for (seed, arm), rows in sorted(grouped.items()):
        region_totals: dict[str, dict[str, float]] = {}
        commodity_totals: dict[str, dict[str, Any]] = {}
        national = {
            "realized": 0.0,
            "affordable": 0.0,
            "availability_unmet": 0.0,
            "desired": 0.0,
        }
        for row in rows:
            economics = row["economics"]
            energy = economics["energy"]
            for key in national:
                national[key] += float(energy["national"][key])
            for region in energy["per_region"]:
                bucket = region_totals.setdefault(
                    region["region_id"],
                    {"realized": 0.0, "affordable": 0.0, "availability_unmet": 0.0, "desired": 0.0},
                )
                for key in bucket:
                    bucket[key] += float(region[key])
            for commodity_id, values in economics["other_commodities"].items():
                bucket = commodity_totals.setdefault(
                    commodity_id,
                    {
                        "unit": values["unit"],
                        "household_realized": 0.0,
                        "household_affordable": 0.0,
                        "household_availability_unmet": 0.0,
                        "household_desired": 0.0,
                    },
                )
                for key in (
                    "household_realized",
                    "household_affordable",
                    "household_availability_unmet",
                    "household_desired",
                ):
                    bucket[key] += float(values[key])
        national["shortage_share"] = (
            national["availability_unmet"] / national["desired"]
            if national["desired"] > 0.0
            else None
        )
        per_region = []
        for region_id, values in sorted(region_totals.items()):
            values["region_id"] = region_id
            values["shortage_share"] = (
                values["availability_unmet"] / values["desired"]
                if values["desired"] > 0.0
                else None
            )
            per_region.append(values)
        summaries.append(
            {
                "seed": seed,
                "arm": arm,
                "target_quarters": [row["quarter"] for row in rows],
                "energy": {"unit": UNIT, "national": national, "per_region": per_region},
                "other_commodities": commodity_totals,
            }
        )
    return summaries


def _hub_blocked(flows: Any, network: Any, hub: int, commodity_index: int) -> tuple[float, float]:
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    demand_purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_owner_kind = np.asarray(network.cell_owner_kind, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    cell_stage = np.asarray(network.cell_stage, dtype=np.int64)
    mask = (
        (demand_purpose == PURPOSE_CODES[RoutePurpose.PROCUREMENT])
        & (cell_commodity[demand_cell] == commodity_index)
        & (cell_stage[demand_cell] == STAGE_CODES[STAGE])
        & (cell_owner_kind[demand_cell] == 0)
        & (cell_owner_id[demand_cell] == hub)
    )
    rows = demand_cell[mask]
    financial = float(np.asarray(flows.financial_delivery_blocked, dtype=np.float64)[rows].sum())
    physical = float(np.asarray(flows.physical_delivery_blocked, dtype=np.float64)[rows].sum())
    return financial, physical


def _execution_evidence(
    result: Any,
    flows: Any,
    network: Any,
    target: dict[str, Any],
) -> dict[str, Any]:
    trace = dict(result.trace)
    hub = int(target["hub_organization_index"])
    commodity_index = int(target["commodity_index"])
    financial, physical = _hub_blocked(flows, network, hub, commodity_index)
    requested = float(trace.get("requested_quantity", 0.0))
    if not result.is_committed:
        classification = "rejected"
    elif requested <= 0.0:
        classification = "zero"
    elif trace.get("binding_status") == "satisfied":
        classification = "satisfied"
    elif financial + physical > 0.0:
        classification = "resource_blocked"
    else:
        classification = "binding"
    return {
        "committed": bool(result.is_committed),
        "reason": str(result.reason),
        "classification": classification,
        "requested_quantity": requested,
        "baseline_delivered_quantity": float(
            trace.get("baseline_delivered_quantity", 0.0)
        ),
        "delivered_quantity": float(trace.get("delivered_quantity", 0.0)),
        "incremental_delivered_quantity": float(
            trace.get("incremental_delivered_quantity", 0.0)
        ),
        "baseline_buyer_payment": float(trace.get("baseline_buyer_payment", 0.0)),
        "buyer_payment": float(trace.get("buyer_payment", 0.0)),
        "incremental_buyer_payment": float(
            trace.get("incremental_buyer_payment", 0.0)
        ),
        "plan_actual_gap": float(trace.get("plan_actual_gap", 0.0)),
        "binding_status": str(trace.get("binding_status", "")),
        "financial_delivery_blocked": financial,
        "physical_delivery_blocked": physical,
    }


def _accounting_evidence(flows: Any, summary: Any) -> dict[str, Any]:
    def maximum(values: Any) -> float:
        if values is None:
            return 0.0
        array = np.asarray(values, dtype=np.float64)
        if array.size == 0:
            return 0.0
        return float(np.max(np.abs(array)))

    journal = {
        "kind": list(getattr(flows, "journal_kind", ())),
        "tick": list(getattr(flows, "journal_tick", ())),
        "debit": list(getattr(flows, "journal_debit", ())),
        "credit": list(getattr(flows, "journal_credit", ())),
        "currency": list(getattr(flows, "journal_currency", ())),
        "amount": list(getattr(flows, "journal_amount", ())),
        "org": list(getattr(flows, "journal_org", ())),
        "leg": list(getattr(flows, "journal_leg", ())),
        "event": list(getattr(flows, "journal_event", ())),
    }
    lengths = {len(value) for value in journal.values()}
    amounts = (
        np.asarray(journal["amount"], dtype=np.float64)
        if journal["amount"]
        else np.zeros(0)
    )
    journal_rows = len(journal["kind"])
    journal_intact = (
        len(lengths) == 1
        and bool(np.all(np.isfinite(amounts)))
        and all(type(value) is int and value >= 0 for value in journal["debit"])
        and all(type(value) is int and value >= 0 for value in journal["credit"])
    )
    return {
        "gate_max_material_abs_residual": float(summary.max_material_abs_residual),
        "gate_max_material_tolerance_ratio": float(
            summary.max_material_tolerance_ratio
        ),
        "gate_max_finance_abs_residual": float(summary.max_finance_abs_residual),
        "gate_max_finance_tolerance_ratio": float(
            summary.max_finance_tolerance_ratio
        ),
        "gate_checked_cells": int(summary.checked_cells),
        "gate_threshold": ZERO_TOLERANCE,
        "invariant_gate": "passed",
        "continuity_snapshot_max_abs_residual": maximum(
            getattr(flows, "material_balance_residual", None)
        ),
        "continuity_snapshot_note": (
            "diagnostic snapshot over every stock cell, including non-gate "
            "service/retail cells; the gate maxima above are authoritative"
        ),
        "journal_entries": journal_rows,
        "journal_columns_present": bool(journal_rows == len(journal["amount"])),
        "journal_rows_intact": journal_intact,
        "journal_sha256": canonical_digest(journal),
    }


# ---------------------------------------------------------------------------
# Incremental evidence writer (issue before kernel, flushed per line)
# ---------------------------------------------------------------------------


class _EvidenceWriter:
    def __init__(self, output: Path) -> None:
        self.output = output
        self._handles = {
            name: (output / f"{name}.jsonl").open("w", encoding="utf-8")
            for name in ("issued", "realized", "residuals", "ticks")
        }
        self._seq: dict[tuple[int, str], int] = {}

    def close(self) -> None:
        for handle in self._handles.values():
            if handle.closed:
                continue
            handle.flush()
            handle.close()

    def next_seq(self, seed: int, arm: str) -> int:
        key = (seed, arm)
        value = self._seq.get(key, 0)
        self._seq[key] = value + 1
        return value

    def emit(self, name: str, content: dict[str, Any]) -> int:
        payload = {"content": content, "content_sha256": canonical_digest(content)}
        self._handles[name].write(json.dumps(payload, sort_keys=True) + "\n")
        self._handles[name].flush()
        return int(content["seq"])


# ---------------------------------------------------------------------------
# State hashing
# ---------------------------------------------------------------------------


def _hash_state(state: Any) -> str:
    return _sha256_bytes(canonical_material_bytes(state))


def _hash_state_and_flows(state: Any, flows: Any) -> str:
    return _sha256_bytes(canonical_material_bytes(state, flows))


def _baseline_step(
    state: Any,
    forcing: Any,
    parameters: Any,
    network: Any,
) -> tuple[Any, dict[str, Any]]:
    opening = capture_material_stocks(state)
    before = int(state.completed_ticks)
    opening_hash = _hash_state(state)
    flows = tick_material(state, forcing, parameters, network)
    summary = accounting.check_material_invariants(
        opening, state, flows, parameters, network
    )
    _require(
        summary.max_material_abs_residual < ZERO_TOLERANCE
        and summary.max_finance_abs_residual < ZERO_TOLERANCE,
        "warm-up tick failed the invariant gate",
    )
    state.completed_ticks += 1
    return flows, {
        "tick_before": before,
        "tick_after": int(state.completed_ticks),
        "opening_state_sha256": opening_hash,
        "closing_state_sha256": _hash_state(state),
        "flow_witness_sha256": _hash_state_and_flows(state, flows),
        "material_max_abs_residual": float(summary.max_material_abs_residual),
        "finance_max_abs_residual": float(summary.max_finance_abs_residual),
    }


# ---------------------------------------------------------------------------
# One experiment run
# ---------------------------------------------------------------------------


def _source_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    paths = [
        root / "src/hsm_lab/institutions/forecast_error_adapter.py",
        Path(__file__).resolve(),
    ]
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _scenario_hash(scenario: ScenarioSpec) -> str:
    return canonical_digest(scenario.model_dump(mode="json"))


def _run_id(
    *,
    scenario_hash: str,
    spec_sha256: str,
    source_sha256: str,
    seed: int,
    arm_id: str,
) -> str:
    return content_addressed_run_id(
        {
            "schema_version": SCHEMA_VERSION,
            "scenario_hash": scenario_hash,
            "spec_sha256": spec_sha256,
            "source_sha256": source_sha256,
            "seed": seed,
            "arm_id": arm_id,
        }
    )


def _load_world(
    root: Path,
    scenario: ScenarioSpec,
) -> tuple[Any, Any, Any, Any, Any, Any]:
    contract = load_research_contract(root)
    registry = DataRegistry.load(root, allowed_commodities=list(scenario.commodities))
    forcing = load_material_forcing(scenario, registry)
    _require(
        len(forcing.quarters) >= scenario.ticks,
        "forcing pack does not cover the synthetic window",
    )
    initial = build_material_initial_conditions(scenario, RngRegistry(int(scenario.seed)))
    network = build_material_network(scenario, contract, initial)
    state = initialize_material(scenario, initial, network)
    parameters = scenario.material_parameters
    _require(parameters is not None, "scenario has no material parameters")
    return registry, forcing, initial, network, state, parameters


def _descriptive_mean(
    per_seed: Mapping[str, dict[str, Any]]
) -> dict[str, Any]:
    values = list(per_seed.values())
    count = len(values)
    _require(count > 0, "no per-seed matrix to describe")
    result: dict[str, Any] = {}
    for field in ("mae", "signed_bias", "delay_effect", "method_effect"):
        keys = list(values[0][field])
        result[field] = {
            key: float(np.mean([value[field][key] for value in values]))
            for key in keys
        }
    result["interaction"] = float(
        np.mean([value["interaction"] for value in values])
    )
    return result


def _matrix_entry(
    records: list[dict[str, Any]], *, expected_per_arm: int = 4
) -> dict[str, Any]:
    by_arm: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    for record in records:
        by_arm[record["arm"]].append(record)
    mae: dict[str, float] = {}
    bias: dict[str, float] = {}
    for arm in ARMS:
        rows = by_arm[arm]
        _require(
            len(rows) == expected_per_arm,
            f"arm {arm} does not have {expected_per_arm} completed targets",
        )
        mae[arm] = float(np.mean([row["absolute_error"] for row in rows]))
        bias[arm] = float(np.mean([row["residual"] for row in rows]))
    return {
        "mae": mae,
        "signed_bias": bias,
        "delay_effect": {
            method: mae[f"delay0_{method}"] - mae[f"delay1_{method}"]
            for method in ("persistence", "linear")
        },
        "method_effect": {
            delay: mae[f"{delay}_linear"] - mae[f"{delay}_persistence"]
            for delay in ("delay0", "delay1")
        },
        "interaction": (
            (mae["delay0_linear"] - mae["delay0_persistence"])
            - (mae["delay1_linear"] - mae["delay1_persistence"])
        ),
    }


def run_experiment(
    root: Path,
    *,
    spec_path: Path,
    output_dir: Path,
    mode: str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    output = (
        Path(output_dir).resolve()
        if Path(output_dir).is_absolute()
        else (root / output_dir).resolve()
    )
    if output.exists() or output.is_symlink():
        raise RunnerError(f"output directory already exists: {output}")
    spec_file = spec_path if spec_path.is_absolute() else root / spec_path
    spec = _load_spec(root, spec_file)
    spec_sha256 = sha256_file(spec_file)
    source_sha256 = _source_sha256(root)

    if mode == "smoke":
        seeds = (1729,)
        ticks = 5
        issue_ticks = (3,)
        target_ticks = (4,)
    elif mode in ("profile", "study"):
        seeds = (1729,) if mode == "profile" else (1729, 1730, 1731)
        ticks = 8
        issue_ticks = (3, 4, 5, 6)
        target_ticks = (4, 5, 6, 7)
    else:
        raise RunnerError(f"unknown experiment mode {mode!r}")

    output.mkdir(parents=True)
    writer = _EvidenceWriter(output)
    started = time.time()
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))
    records: list[dict[str, Any]] = []
    tick_records: list[dict[str, Any]] = []
    first_stage: list[dict[str, Any]] = []
    seed_records: list[dict[str, Any]] = []
    run_identities: list[dict[str, Any]] = []
    failed_seeds: list[dict[str, Any]] = []
    crosswalks: dict[str, Any] = {}

    try:
        for seed in seeds:
            try:
                scenario = _typed_scenario(
                    load_scenario(root, spec["base_scenario"]),
                    spec,
                    seed=seed,
                    ticks=ticks,
                )
                scenario_hash = _scenario_hash(scenario)
                _registry, forcing, _initial, network, state, parameters = _load_world(
                    root, scenario
                )
                target = _select_target(network)
                crosswalks[str(seed)] = target
                calendar = _calendar(spec)
                calendar_sha256 = canonical_digest(calendar.model_dump(mode="json"))
                crosswalk_sha256 = canonical_digest(target["crosswalk"])
                builder = ObservationBuilder("procurement_organization")

                archive: dict[str, dict[str, Any]] = {}
                warmup_ticks: list[dict[str, Any]] = []
                for tick in range(3):
                    flows, witness = _baseline_step(state, forcing, parameters, network)
                    quarter = str(forcing.quarters[tick])
                    production = _source_production(
                        flows, network, int(target["source_stock_cell"])
                    )
                    archive[quarter] = {
                        "value": production,
                        "flow_witness_sha256": witness["flow_witness_sha256"],
                        "tick": tick,
                    }
                    warmup_ticks.append(
                        {
                            "tick": tick,
                            "quarter": quarter,
                            "source_production": production,
                            **witness,
                        }
                    )
                branch_state = copy.deepcopy(state)
                branch_sha = _hash_state(branch_state)
                _require(
                    branch_state.completed_ticks == 3,
                    "warm-up clock did not reach tick 3",
                )

                seed_records.append(
                    {
                        "seed": seed,
                        "scenario_hash": scenario_hash,
                        "branch_state_sha256": branch_sha,
                        "warmup_ticks": warmup_ticks,
                        "archive_after_warmup": {
                            key: value["value"] for key, value in archive.items()
                        },
                    }
                )
                for warmup in warmup_ticks:
                    tick_records.append({"seed": seed, "arm": "warmup", **warmup})

                for arm in ARMS:
                    delay = ARM_DELAY[arm]
                    method = ARM_METHOD[arm]
                    run_id = _run_id(
                        scenario_hash=scenario_hash,
                        spec_sha256=spec_sha256,
                        source_sha256=source_sha256,
                        seed=seed,
                        arm_id=arm,
                    )
                    arm_state = copy.deepcopy(branch_state)
                    arm_archive = copy.deepcopy(archive)
                    issued_by_id: dict[str, IssuedForecast] = {}
                    realized_by_id: dict[str, RealizedForecast] = {}
                    residual_by_id: dict[str, ForecastResidual] = {}
                    pending: dict[str, IssuedForecast] = {}
                    pending_sequences: dict[str, int] = {}
                    run_identities.append(
                        {
                            "seed": seed,
                            "arm": arm,
                            "run_id": run_id,
                            "scenario_hash": scenario_hash,
                            "spec_sha256": spec_sha256,
                            "source_sha256": source_sha256,
                            "calendar_sha256": calendar_sha256,
                            "crosswalk_sha256": crosswalk_sha256,
                        }
                    )
                    _require(
                        _hash_state(arm_state) == branch_sha,
                        "arm start state differs from the common branch",
                    )

                    for tick in range(3, ticks):
                        quarter = str(forcing.quarters[tick])
                        issued: IssuedForecast | None = None
                        issued_seq: int | None = None
                        reports_metadata: list[dict[str, Any]] = []
                        if tick in issue_ticks:
                            target_quarter = str(forcing.quarters[tick + 1])
                            issued_at = quarter_day(quarter, 15)
                            reports, reports_metadata = _select_reports(
                                arm_archive,
                                issued_quarter=quarter,
                                issued_at=issued_at,
                                delay=delay,
                                subject=str(target["subject_organization_id"]),
                                measurement_factory=builder,
                            )
                            issued = issue_forecast(
                                reports,
                                forecast_id=(
                                    f"{run_id}:{quarter}:{target_quarter}:"
                                    f"{COMMODITY_ID}:{STAGE}:"
                                    f"{target['subject_organization_id']}"
                                ),
                                run_id=run_id,
                                seed=seed,
                                arm_id=arm,
                                issued_quarter=quarter,
                                issued_at=issued_at,
                                target_quarter=target_quarter,
                                method=method,
                            )
                            issued_by_id[issued.forecast_id] = issued
                            pending[issued.target_quarter] = issued
                            issued_seq = writer.next_seq(seed, arm)
                            pending_sequences[issued.target_quarter] = issued_seq
                            writer.emit(
                                "issued",
                                {
                                    **issued.model_dump(mode="json"),
                                    "seq": issued_seq,
                                    "seed": seed,
                                    "arm": arm,
                                    "reports": reports_metadata,
                                },
                            )
                            first_stage.append(
                                {
                                    "seed": seed,
                                    "arm": arm,
                                    "mode": mode,
                                    "delay": delay,
                                    "method": method,
                                    "issued_quarter": quarter,
                                    "issued_at": issued_at.isoformat(),
                                    "target_quarter": target_quarter,
                                    "reports": reports_metadata,
                                    "available_at": issued.available_at.isoformat(),
                                    "input_observation_sha256": issued.input_observation_sha256,
                                }
                            )
                            quantity = min(
                                QUANTITY_CAP, max(0.0, float(issued.prediction))
                            )
                            observation_for_decision = reports[1].observation
                        else:
                            quantity = float(spec["procurement"]["terminal_quantity"])
                            observation_for_decision = None

                        decision = _decision(
                            run_id=run_id, quarter=quarter, quantity=quantity
                        )
                        if observation_for_decision is None:
                            observation_for_decision = builder.build(
                                organization_id=ACTOR_ORGANIZATION_ID,
                                sector_id=ACTOR_SECTOR_ID,
                                geographic_id=ACTOR_GEOGRAPHIC_ID,
                                quarter=quarter,
                                decision_at=decision.decision_at,
                                available_at=decision.available_at,
                                raw_data={"quarter": quarter},
                            )
                        validation, error = _admit(
                            decision, calendar, observation_for_decision
                        )
                        if error is not None or validation is None:
                            failed_seeds.append(
                                {
                                    "seed": seed,
                                    "arm": arm,
                                    "tick": tick,
                                    "error": f"admission rejected: {error}",
                                }
                            )
                            raise RunnerError(
                                f"seed {seed} arm {arm} tick {tick}: {error}"
                            )
                        _require(
                            int(arm_state.completed_ticks) == tick,
                            "decision tick and material clock disagree",
                        )
                        _require(
                            decision.quarter == quarter,
                            "decision quarter and forcing quarter disagree",
                        )

                        kernel_start_seq = writer.next_seq(seed, arm)
                        writer.emit(
                            "ticks",
                            {
                                "seq": kernel_start_seq,
                                "kind": "kernel_start",
                                "seed": seed,
                                "arm": arm,
                                "tick": tick,
                                "quarter": quarter,
                                "completed_ticks_before": int(arm_state.completed_ticks),
                                "issued_forecast_id": (
                                    issued.forecast_id if issued is not None else None
                                ),
                            },
                        )
                        opening_hash = _hash_state(arm_state)
                        opening_snapshot = capture_material_stocks(arm_state)
                        result = commit_proposal(
                            decision,
                            validation,
                            arm_state,
                            forcing,
                            parameters,
                            network,
                            organization_index=target["crosswalk"],
                        )
                        kernel_end_seq = writer.next_seq(seed, arm)
                        if not result.is_committed or result.flows is None:
                            failed_seeds.append(
                                {
                                    "seed": seed,
                                    "arm": arm,
                                    "tick": tick,
                                    "error": f"commit rejected: {result.reason}",
                                }
                            )
                            raise RunnerError(
                                f"seed {seed} arm {arm} tick {tick} commit rejected: "
                                f"{result.reason}"
                            )
                        flows = result.flows
                        applied_controls = _with_procurement_request(
                            _base_controls(parameters, network, None),
                            (
                                int(target["hub_organization_index"]),
                                int(target["commodity_index"]),
                                (
                                    0.0
                                    if decision.kind == ProcurementChoiceKind.CANCEL
                                    else float(decision.requested_quantity)
                                ),
                            ),
                        )
                        gate_summary = accounting.check_material_invariants(
                            opening_snapshot,
                            arm_state,
                            flows,
                            parameters,
                            network,
                            controls=applied_controls,
                        )
                        _require(
                            gate_summary.max_material_abs_residual < ZERO_TOLERANCE
                            and gate_summary.max_finance_abs_residual < ZERO_TOLERANCE,
                            "reconstructed gate disagrees with the committed tick",
                        )
                        production = _source_production(
                            flows, network, int(target["source_stock_cell"])
                        )
                        closing_hash = _hash_state(arm_state)
                        flow_witness = _hash_state_and_flows(arm_state, flows)
                        writer.emit(
                            "ticks",
                            {
                                "seq": kernel_end_seq,
                                "kind": "kernel_end",
                                "seed": seed,
                                "arm": arm,
                                "tick": tick,
                                "quarter": quarter,
                                "completed_ticks_after": int(arm_state.completed_ticks),
                                "opening_state_sha256": opening_hash,
                                "closing_state_sha256": closing_hash,
                                "flow_witness_sha256": flow_witness,
                                "source_production": production,
                            },
                        )
                        _require(
                            int(arm_state.completed_ticks) == tick + 1,
                            "kernel did not advance exactly one quarter",
                        )

                        realization: RealizedForecast | None = None
                        residual: ForecastResidual | None = None
                        if quarter in pending:
                            pending_forecast = pending.pop(quarter)
                            realized_issue_seq = pending_sequences.pop(quarter)
                            realization = RealizedForecast(
                                forecast_id=pending_forecast.forecast_id,
                                run_id=run_id,
                                seed=seed,
                                arm_id=arm,
                                subject_organization_id=pending_forecast.subject_organization_id,
                                commodity_id=COMMODITY_ID,
                                stage=STAGE,
                                unit=UNIT,
                                target_quarter=quarter,
                                measurement_quarter=quarter,
                                realized_at=quarter_end(quarter),
                                realized_value=production,
                                kernel_tick=tick,
                                kernel_quarter=quarter,
                                witness_sha256=flow_witness,
                            )
                            residual = score_forecast(pending_forecast, realization)
                            _require(
                                pending_forecast.forecast_id not in realized_by_id,
                                "duplicate realization for one forecast",
                            )
                            realized_by_id[realization.forecast_id] = realization
                            residual_by_id[residual.forecast_id] = residual
                            realization_seq = writer.next_seq(seed, arm)
                            writer.emit(
                                "realized",
                                {
                                    **realization.model_dump(mode="json"),
                                    "seq": realization_seq,
                                    "seed": seed,
                                    "arm": arm,
                                },
                            )
                            writer.emit(
                                "residuals",
                                {
                                    **residual.model_dump(mode="json"),
                                    "seq": realization_seq,
                                    "seed": seed,
                                    "arm": arm,
                                },
                            )
                            _require(
                                realized_issue_seq < kernel_start_seq
                                and kernel_start_seq < kernel_end_seq
                                and kernel_end_seq < realization_seq,
                                "forecast/realization chronology is not monotone",
                            )

                        arm_archive[quarter] = {
                            "value": production,
                            "flow_witness_sha256": flow_witness,
                            "tick": tick,
                        }
                        execution = _execution_evidence(result, flows, network, target)
                        tick_record = {
                            "seed": seed,
                            "arm": arm,
                            "tick": tick,
                            "quarter": quarter,
                            "opening_state_sha256": opening_hash,
                            "closing_state_sha256": closing_hash,
                            "flow_witness_sha256": flow_witness,
                            "completed_ticks_before": tick,
                            "completed_ticks_after": int(arm_state.completed_ticks),
                            "source_production": production,
                            "issued_forecast_id": (
                                issued.forecast_id if issued is not None else None
                            ),
                            "realized_forecast_id": (
                                realization.forecast_id if realization is not None else None
                            ),
                            "residual": (
                                residual.model_dump(mode="json")
                                if residual is not None
                                else None
                            ),
                            "execution": execution,
                            "accounting": _accounting_evidence(flows, gate_summary),
                            "economics": _economics(flows, arm_state, network),
                            "seq": {
                                "issue": issued_seq,
                                "kernel_start": kernel_start_seq,
                                "kernel_end": kernel_end_seq,
                                "realization": (
                                    realization_seq if realization is not None else None
                                ),
                            },
                        }
                        tick_records.append(tick_record)

                    _require(not pending, "issued forecasts remain unrealized")
                    for forecast_id in issued_by_id:
                        _require(
                            forecast_id in realized_by_id,
                            "issued forecast has no realization",
                        )
                        residual_record = residual_by_id[forecast_id]
                        records.append(
                            {
                                "seed": seed,
                                "arm": arm,
                                "method": method,
                                "delay": delay,
                                "issued_quarter": residual_record.issued_quarter,
                                "target_quarter": residual_record.target_quarter,
                                "forecast_id": forecast_id,
                                "prediction": residual_record.prediction,
                                "realized_value": residual_record.realized_value,
                                "residual": residual_record.residual,
                                "absolute_error": residual_record.absolute_error,
                            }
                        )
            except Exception as exc:  # noqa: BLE001 - preserve and stop
                failed_seeds.append({"seed": seed, "error": str(exc)})
                writer.close()
                _write_json(
                    output / "FAILED_SEEDS.json",
                    {
                        "schema_version": SCHEMA_VERSION,
                        "mode": mode,
                        "status": "FAILED",
                        "failed_seeds": failed_seeds,
                    },
                )
                _write_json(
                    output / "BLOCKER_CERTIFICATE.json",
                    {
                        "schema_version": SCHEMA_VERSION,
                        "phase_id": "H5F-F1",
                        "study_id": "M09",
                        "mode": mode,
                        "status": "BLOCKED",
                        "error": str(exc),
                        "failed_seeds": failed_seeds,
                        "attempted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "fallback_used": False,
                    },
                )
                raise
    finally:
        writer.close()

    expected_per_arm = len(seeds) * (1 if mode == "smoke" else 4)
    try:
        matrix = _matrix_entry(records, expected_per_arm=expected_per_arm)
        per_seed_matrices = {}
        for seed in seeds:
            seed_records_rows = [row for row in records if row["seed"] == seed]
            per_seed_matrices[str(seed)] = _matrix_entry(
                seed_records_rows,
                expected_per_arm=1 if mode == "smoke" else 4,
            )
        first_stage_check = _verify_first_stage(first_stage)
        economics = _economics_summary(tick_records, target_ticks=target_ticks)
    except Exception as exc:  # noqa: BLE001 - post-loop failure must be sealed
        failed_seeds.append({"phase": "aggregation", "error": str(exc)})
        _write_json(
            output / "FAILED_SEEDS.json",
            {
                "schema_version": SCHEMA_VERSION,
                "mode": mode,
                "status": "FAILED",
                "failed_seeds": failed_seeds,
            },
        )
        _write_json(
            output / "BLOCKER_CERTIFICATE.json",
            {
                "schema_version": SCHEMA_VERSION,
                "phase_id": "H5F-F1",
                "study_id": "M09",
                "mode": mode,
                "status": "BLOCKED",
                "error": str(exc),
                "failed_seeds": failed_seeds,
                "attempted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "fallback_used": False,
            },
        )
        raise

    science = {
        "schema_version": SCHEMA_VERSION,
        "phase_id": "H5F-F1",
        "study_id": "M09",
        "mechanism_id": "M9",
        "registration_status_changed": False,
        "material_only": True,
        "mode": mode,
        "spec_sha256": spec_sha256,
        "source_sha256": source_sha256,
        "scenario": {
            "base": spec["base_scenario"],
            "id": spec["scenario_id"],
            "hashes": {
                str(seed): rec["scenario_hash"]
                for seed, rec in zip(seeds, seed_records, strict=True)
            },
            "ticks": ticks,
            "seeds": list(seeds),
        },
        "arms": list(ARMS),
        "issue_ticks": list(issue_ticks),
        "target_ticks": list(target_ticks),
        "quarters": {
            "issued": [str(forcing.quarters[tick]) for tick in issue_ticks],
            "targets": [str(forcing.quarters[tick]) for tick in target_ticks],
        },
        "targets": crosswalks,
        "run_identities": run_identities,
        "seed_records": seed_records,
        "first_stage": first_stage,
        "first_stage_check": first_stage_check,
        "records": records,
        "matrix": {
            "pooled": matrix,
            "per_seed": per_seed_matrices,
            "descriptive_mean": _descriptive_mean(per_seed_matrices),
        },
        "economics": economics,
        "ticks": tick_records,
        "failed_seeds": [],
        "historical_status": "NOT_RUN",
        "structural_status": "SYNTHETIC_ENGINEERING_PROFILE",
        "notes": spec.get("notes", []),
    }
    science_digest = canonical_digest(science)
    _write_json(output / "science.json", science)

    sidecar_hashes = {
        name: sha256_file(output / f"{name}.jsonl")
        for name in ("issued", "realized", "residuals", "ticks")
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "phase_id": "H5F-F1",
        "study_id": "M09",
        "mechanism_id": "M9",
        "mode": mode,
        "status": "COMPLETED",
        "material_only": True,
        "politics_installed": False,
        "registration_status_changed": False,
        "historical_status": "NOT_RUN",
        "science_digest": science_digest,
        "sidecar_sha256": sidecar_hashes,
        "spec_sha256": spec_sha256,
        "source_sha256": source_sha256,
        "plan_sha256": sha256_file(root / "studies/HIST_VNEXT/M09/PLAN.md"),
        "test_sha256": sha256_file(root / "tests/test_hist_information_politics.py"),
        "spec_path": str(spec_file.relative_to(root)),
        "seeds": list(seeds),
        "arms": list(ARMS),
        "ticks": ticks,
        "target_count": len(records),
        "started_at": started_at,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "output_dir": (
            str(output.relative_to(root)) if output.is_relative_to(root) else str(output)
        ),
        "wall_seconds": round(time.time() - started, 3),
        "failed_seeds": failed_seeds,
    }
    _write_json(output / "manifest.json", manifest)
    _write_json(output / "ledger.json", {
        "schema_version": SCHEMA_VERSION,
        "status": "COMPLETED",
        "record_count": len(records),
        "expected_record_count": len(seeds) * len(ARMS) * len(target_ticks),
        "matrix": matrix,
        "failed_seeds": failed_seeds,
    })
    _write_json(output / "FAILED_SEEDS.json", {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "status": "COMPLETED",
        "failed_seeds": [],
        "checked_pairs": len(records),
    })
    return manifest


# ---------------------------------------------------------------------------
# First-stage derivation check
# ---------------------------------------------------------------------------


def _verify_first_stage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_key: dict[tuple[Any, ...], set[tuple[str, ...]]] = {}
    for row in rows:
        key = (
            row["seed"],
            row["issued_quarter"],
            row["method"],
        )
        by_key.setdefault(key, set()).add(
            tuple(item["measurement_quarter"] for item in row["reports"])
        )
    changed = 0
    unchanged = 0
    details = []
    for (seed, quarter, method), sets in sorted(by_key.items()):
        if len(sets) == 2:
            changed += 1
            details.append(
                {
                    "seed": seed,
                    "issued_quarter": quarter,
                    "method": method,
                    "status": "DELAY_CHANGED_REPORT_SET",
                }
            )
        else:
            unchanged += 1
            details.append(
                {
                    "seed": seed,
                    "issued_quarter": quarter,
                    "method": method,
                    "status": "DELAY_DID_NOT_CHANGE_REPORT_SET",
                }
            )
    return {
        "changed_sets": changed,
        "unchanged_sets": unchanged,
        "details": details,
        "status": (
            "ESTABLISHED" if changed > 0 and unchanged == 0 else "NOT_ESTABLISHED"
        ),
    }


# ---------------------------------------------------------------------------
# Read-only verification
# ---------------------------------------------------------------------------


def _read_sidecar(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        content = payload.get("content")
        digest = payload.get("content_sha256")
        if not isinstance(content, dict):
            raise RunnerError(f"{path.name}: sidecar content is not an object")
        if canonical_digest(content) != digest:
            raise RunnerError(f"{path.name}: sidecar content hash mismatch")
        rows.append(content)
    return rows


def _verify_package(output: Path, *, expected_mode: str | None = None) -> dict[str, Any]:
    output = Path(output)
    if not output.is_dir():
        raise RunnerError(f"output directory does not exist: {output}")
    science = _read_json(output / "science.json")
    manifest = _read_json(output / "manifest.json")
    if expected_mode is not None and science.get("mode") != expected_mode:
        raise RunnerError(
            f"expected mode {expected_mode!r}, found {science.get('mode')!r}"
        )
    if canonical_digest(science) != manifest.get("science_digest"):
        raise RunnerError("science digest does not match the manifest")
    if manifest.get("status") != "COMPLETED":
        raise RunnerError("manifest status is not COMPLETED")
    if manifest.get("failed_seeds"):
        raise RunnerError("manifest declares failed seeds")
    if science.get("failed_seeds"):
        raise RunnerError("science payload declares failed seeds")

    for name in ("issued", "realized", "residuals", "ticks"):
        digest = sha256_file(output / f"{name}.jsonl")
        if digest != manifest["sidecar_sha256"].get(name):
            raise RunnerError(f"{name}.jsonl hash does not match the manifest")

    issued_rows = _read_sidecar(output / "issued.jsonl")
    realized_rows = _read_sidecar(output / "realized.jsonl")
    residual_rows = _read_sidecar(output / "residuals.jsonl")
    tick_rows = _read_sidecar(output / "ticks.jsonl")

    issued: dict[str, IssuedForecast] = {}
    for row in issued_rows:
        forecast = IssuedForecast.model_validate(
            {
                key: value
                for key, value in row.items()
                if key not in ("seq", "arm", "reports")
            }
        )
        if forecast.forecast_id in issued:
            raise RunnerError("duplicate issued forecast id")
        if forecast.seed != row.get("seed") or forecast.arm_id != row.get("arm"):
            raise RunnerError("issued sidecar identity mismatch")
        issued[forecast.forecast_id] = forecast
        expected = (
            f"{forecast.run_id}:{forecast.issued_quarter}:{forecast.target_quarter}:"
            f"{forecast.commodity_id}:{forecast.stage}:{forecast.subject_organization_id}"
        )
        if forecast.forecast_id != expected:
            raise RunnerError("issued forecast id is not canonical")
        reports = row.get("reports")
        if not isinstance(reports, list) or len(reports) != 2:
            raise RunnerError("issued sidecar does not carry two reports")
        if forecast.arm_id not in ARMS:
            raise RunnerError("issued forecast arm is not in the frozen matrix")
        delay = ARM_DELAY[forecast.arm_id]
        if forecast.method != ARM_METHOD[forecast.arm_id]:
            raise RunnerError("issued method does not match its arm")
        from hsm_lab.contract.schemas import Quarter

        issued_ordinal = Quarter.parse(forecast.issued_quarter).to_ordinal()
        expected_newer = issued_ordinal - 1 - delay
        expected_older = expected_newer - 1

        expected_quarters = (
            str(Quarter.from_ordinal(expected_older)),
            str(Quarter.from_ordinal(expected_newer)),
        )
        if (
            forecast.older_measurement_quarter,
            forecast.newer_measurement_quarter,
        ) != expected_quarters:
            raise RunnerError("issued reports do not follow the arm delay schedule")
        for report in reports:
            expected_publication = _publication_date(
                report["measurement_quarter"], delay
            ).isoformat()
            if report["published_at"] != expected_publication:
                raise RunnerError("report publication date does not follow the delay")
            if date.fromisoformat(report["published_at"]) < quarter_end(
                report["measurement_quarter"]
            ):
                raise RunnerError("report was published before its quarter closed")
        payload = [
            {
                "measurement_quarter": report["measurement_quarter"],
                "observation": {
                    "actor_role": "procurement_organization",
                    "organization_id": ACTOR_ORGANIZATION_ID,
                    "sector_id": ACTOR_SECTOR_ID,
                    "geographic_id": ACTOR_GEOGRAPHIC_ID,
                    "quarter": forecast.issued_quarter,
                    "decision_at": forecast.issued_at.isoformat(),
                    "available_at": report["published_at"],
                    "observed_fields": {
                        "quarter": forecast.issued_quarter,
                        "supply_quantity": report["value"],
                    },
                },
            }
            for report in reports
        ]
        if canonical_digest(payload) != forecast.input_observation_sha256:
            raise RunnerError("issued input observation hash does not recompute")
        if tuple(sorted(report["measurement_quarter"] for report in reports)) != (
            forecast.older_measurement_quarter,
            forecast.newer_measurement_quarter,
        ):
            raise RunnerError("issued measurement-quarter ordering is inconsistent")
        ordered_reports = sorted(
            reports,
            key=lambda report: Quarter.parse(
                report["measurement_quarter"]
            ).to_ordinal(),
        )
        older_report, newer_report = ordered_reports
        older_value = float(older_report["value"])
        newer_value = float(newer_report["value"])
        if forecast.older_value != older_value or forecast.newer_value != newer_value:
            raise RunnerError("issued report values do not match the input reports")
        if forecast.older_available_at != date.fromisoformat(
            older_report["published_at"]
        ):
            raise RunnerError("issued older availability does not match the report")
        if forecast.newer_available_at != date.fromisoformat(
            newer_report["published_at"]
        ):
            raise RunnerError("issued newer availability does not match the report")
        if forecast.issued_at != quarter_day(forecast.issued_quarter, 15):
            raise RunnerError("issued decision date is not the declared day 15")
        target_ordinal = Quarter.parse(forecast.target_quarter).to_ordinal()
        older_ordinal = Quarter.parse(forecast.older_measurement_quarter).to_ordinal()
        newer_ordinal = Quarter.parse(forecast.newer_measurement_quarter).to_ordinal()
        if forecast.method == "persistence":
            expected_raw = newer_value
        else:
            expected_raw = newer_value + (target_ordinal - newer_ordinal) * (
                (newer_value - older_value) / (newer_ordinal - older_ordinal)
            )
        if abs(forecast.raw_prediction - expected_raw) > 1e-9:
            raise RunnerError("issued raw prediction does not recompute")
        if abs(forecast.prediction - max(0.0, expected_raw)) > 1e-9:
            raise RunnerError("issued prediction does not recompute")
        if abs(forecast.clipping_delta - (max(0.0, expected_raw) - expected_raw)) > 1e-9:
            raise RunnerError("issued clipping delta does not recompute")
        if forecast.available_at != max(
            forecast.older_available_at, forecast.newer_available_at
        ):
            raise RunnerError("issued available_at is inconsistent")
        if forecast.available_at > forecast.issued_at:
            raise RunnerError("issued forecast uses an unpublished report")

    realized: dict[str, RealizedForecast] = {}
    for row in realized_rows:
        forecast = RealizedForecast.model_validate(
            {key: value for key, value in row.items() if key not in ("seq", "arm")}
        )
        if forecast.forecast_id in realized:
            raise RunnerError("duplicate realization")
        if forecast.forecast_id not in issued:
            raise RunnerError("realization has no issued forecast")
        if forecast.seed != row.get("seed") or forecast.arm_id != row.get("arm"):
            raise RunnerError("realization sidecar identity mismatch")
        realized[forecast.forecast_id] = forecast

    tick_by_forecast = {
        row["realized_forecast_id"]: row
        for row in science["ticks"]
        if row.get("realized_forecast_id")
    }
    if set(tick_by_forecast) != set(realized):
        raise RunnerError("realization witness rows do not cover the forecast set")
    for forecast_id, forecast in realized.items():
        tick_row = tick_by_forecast[forecast_id]
        if forecast.witness_sha256 != tick_row["flow_witness_sha256"]:
            raise RunnerError("realized witness does not match the kernel tick")
        if forecast.kernel_tick != tick_row["tick"]:
            raise RunnerError("realized kernel tick does not match the tick record")
        if forecast.kernel_quarter != tick_row["quarter"]:
            raise RunnerError("realized kernel quarter does not match the tick record")
        if forecast.realized_value != tick_row["source_production"]:
            raise RunnerError("realized value does not match the measured output")

    residual_sidecar: dict[str, ForecastResidual] = {}
    for row in residual_rows:
        forecast = ForecastResidual.model_validate(
            {key: value for key, value in row.items() if key not in ("seq", "arm")}
        )
        if forecast.forecast_id in residual_sidecar:
            raise RunnerError("duplicate residual")
        residual_sidecar[forecast.forecast_id] = forecast

    expected_ids = set(issued)
    if set(realized) != expected_ids:
        raise RunnerError("issued and realized forecast sets differ")
    if set(residual_sidecar) != expected_ids:
        raise RunnerError("issued and residual forecast sets differ")

    recomputed: dict[str, ForecastResidual] = {}
    for forecast_id, issued_record in issued.items():
        residual = score_forecast(issued_record, realized[forecast_id])
        recomputed[forecast_id] = residual
        recorded = residual_sidecar[forecast_id]
        if residual.model_dump(mode="json") != recorded.model_dump(mode="json"):
            raise RunnerError("residual sidecar does not recompute")

    records = science["records"]
    if len(records) != len(expected_ids):
        raise RunnerError("science records do not cover every forecast")
    for record in records:
        forecast_id = record["forecast_id"]
        if forecast_id not in recomputed:
            raise RunnerError("science record has no issued forecast")
        residual = recomputed[forecast_id]
        for name in (
            "prediction",
            "realized_value",
            "residual",
            "absolute_error",
            "issued_quarter",
            "target_quarter",
        ):
            if record.get(name) != getattr(residual, name):
                raise RunnerError(f"science record {name} does not recompute")

    per_seed_expected = 1 if science["mode"] == "smoke" else 4
    expected_per_arm = len(science["scenario"]["seeds"]) * per_seed_expected
    matrix = _matrix_entry(records, expected_per_arm=expected_per_arm)
    if matrix != science["matrix"]["pooled"]:
        raise RunnerError("pooled forecast matrix does not recompute")
    for seed in science["scenario"]["seeds"]:
        rows = [row for row in records if row["seed"] == seed]
        if _matrix_entry(rows, expected_per_arm=per_seed_expected) != science["matrix"][
            "per_seed"
        ][str(seed)]:
            raise RunnerError(f"seed {seed} forecast matrix does not recompute")
    if _descriptive_mean(science["matrix"]["per_seed"]) != science["matrix"][
        "descriptive_mean"
    ]:
        raise RunnerError("descriptive mean matrix does not recompute")
    if _economics_summary(
        science["ticks"], target_ticks=science["target_ticks"]
    ) != science["economics"]:
        raise RunnerError("aggregated economics do not recompute")
    for seed in science["scenario"]["seeds"]:
        seed_identities = [
            identity
            for identity in science["run_identities"]
            if identity["seed"] == seed
        ]
        if len({row["calendar_sha256"] for row in seed_identities}) != 1:
            raise RunnerError("arms do not share one authority calendar")
        if len({row["crosswalk_sha256"] for row in seed_identities}) != 1:
            raise RunnerError("arms do not share one organization crosswalk")
    repo_root = Path(__file__).resolve().parents[3]
    if science["spec_sha256"] != sha256_file(
        repo_root / "studies/HIST_VNEXT/M09/spec.json"
    ):
        raise RunnerError("science payload is not bound to the current spec")
    if science["source_sha256"] != _source_sha256(repo_root):
        raise RunnerError("science payload is not bound to the current source")
    expected_targets = len(science["scenario"]["seeds"]) * len(ARMS) * 4
    if science["mode"] == "smoke":
        expected_targets = len(science["scenario"]["seeds"]) * len(ARMS)
    if len(records) != expected_targets:
        raise RunnerError("completed record count does not match the declared design")

    # Run identity recomputation (no wall clock, output directory or mode).
    identities = {
        (row["seed"], row["arm"]): row for row in science["run_identities"]
    }
    if len(identities) != len(science["run_identities"]):
        raise RunnerError("duplicate run identity")
    scenario_hashes = science["scenario"]["hashes"]
    for (seed, arm), identity in identities.items():
        expected = _run_id(
            scenario_hash=scenario_hashes[str(seed)],
            spec_sha256=science["spec_sha256"],
            source_sha256=science["source_sha256"],
            seed=seed,
            arm_id=arm,
        )
        if expected != identity["run_id"]:
            raise RunnerError("run id does not recompute")

    # Chronology, flushed-event and state-chain verification.
    events_by_seq = {
        (row.get("seed"), row.get("arm"), row.get("seq")): row for row in tick_rows
    }
    if not events_by_seq:
        raise RunnerError("no kernel events were recorded")
    seed_lookup = {row["seed"]: row for row in science["seed_records"]}
    for (seed, arm), _identity in identities.items():
        arm_rows = [
            row
            for row in science["ticks"]
            if row.get("seed") == seed and row.get("arm") == arm
        ]
        if not arm_rows:
            raise RunnerError(f"no tick records for seed {seed} arm {arm}")
        tick_rows_sorted = sorted(arm_rows, key=lambda row: row["tick"])
        if [row["tick"] for row in tick_rows_sorted] != list(
            range(3, 3 + len(tick_rows_sorted))
        ):
            raise RunnerError("arm ticks are not contiguous")
        previous_closing = seed_lookup[seed]["branch_state_sha256"]
        for row in tick_rows_sorted:
            if row["opening_state_sha256"] != previous_closing:
                raise RunnerError("state hash chain is broken")
            if row["completed_ticks_after"] != row["completed_ticks_before"] + 1:
                raise RunnerError("material clock did not advance exactly once")
            previous_closing = row["closing_state_sha256"]
            sequence = row["seq"]
            start_event = events_by_seq.get((seed, arm, sequence["kernel_start"]))
            end_event = events_by_seq.get((seed, arm, sequence["kernel_end"]))
            if start_event is None or start_event.get("kind") != "kernel_start":
                raise RunnerError("kernel start event is missing")
            if end_event is None or end_event.get("kind") != "kernel_end":
                raise RunnerError("kernel end event is missing")
            if end_event.get("opening_state_sha256") != row["opening_state_sha256"]:
                raise RunnerError("kernel event opening hash differs from the tick")
            if end_event.get("closing_state_sha256") != row["closing_state_sha256"]:
                raise RunnerError("kernel event closing hash differs from the tick")
            if end_event.get("flow_witness_sha256") != row["flow_witness_sha256"]:
                raise RunnerError("kernel event flow witness differs from the tick")
            if sequence["issue"] is not None:
                if not (
                    sequence["issue"] < sequence["kernel_start"] < sequence["kernel_end"]
                ):
                    raise RunnerError("forecast was not issued before the kernel call")
                issued_record = issued[row["issued_forecast_id"]]
                if issued_record.issued_quarter != row["quarter"]:
                    raise RunnerError("issued forecast quarter is inconsistent")
            if sequence["realization"] is not None:
                if sequence["realization"] <= sequence["kernel_end"]:
                    raise RunnerError("realization preceded the kernel completion")
            residual = row.get("residual")
            if residual is not None:
                if residual["forecast_id"] != row["realized_forecast_id"]:
                    raise RunnerError("tick residual identity mismatch")
                if residual["residual"] != recomputed[residual["forecast_id"]].residual:
                    raise RunnerError("tick residual does not recompute")

    # First-stage: the delay must change the available report set.
    if science["first_stage_check"]["status"] != "ESTABLISHED":
        raise RunnerError("delay did not change the available report set")
    for row in science["first_stage"]:
        if row["input_observation_sha256"] not in {
            forecast.input_observation_sha256 for forecast in issued.values()
        }:
            raise RunnerError("first-stage input hash has no issued forecast")

    return {
        "status": "PASS",
        "mode": science["mode"],
        "science_digest": manifest["science_digest"],
        "records": len(records),
        "seeds": science["scenario"]["seeds"],
        "arms": list(ARMS),
        "first_stage": science["first_stage_check"]["status"],
        "matrix": science["matrix"]["pooled"],
    }


# ---------------------------------------------------------------------------
# Reproduce (legacy definition counterexample)
# ---------------------------------------------------------------------------


def run_reproduce(root: Path, *, output_dir: Path) -> dict[str, Any]:
    from hsm_lab.contract.politics import INFORMATION_DIMENSION_IDS
    from hsm_lab.engine.technology import InformationParameters, information_dimensions

    root = Path(root).resolve()
    output = (
        Path(output_dir).resolve()
        if Path(output_dir).is_absolute()
        else (root / output_dir).resolve()
    )
    if output.exists() or output.is_symlink():
        raise RunnerError(f"output directory already exists: {output}")
    output.mkdir(parents=True)
    parameters = InformationParameters()
    rows = []
    for capability in (0.0, 0.25, 0.5, 0.75, 1.0):
        dimensions = information_dimensions(capability, parameters)
        rows.append(
            {
                "capability": capability,
                **{
                    key: float(dimensions[index])
                    for index, key in enumerate(INFORMATION_DIMENSION_IDS)
                },
            }
        )
    declaration = _read_json(root / "studies/M09/study_decl.json")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "probe": "legacy_forecast_accuracy_definition",
        "function": "hsm_lab.engine.technology.information_dimensions",
        "capability_sweep": rows,
        "observation": (
            "forecast_accuracy equals the clipped capability input at every "
            "capability and the function accepts no issued forecast, realized "
            "value, or residual."
        ),
        "legacy_study_decl": {
            "path": "studies/M09/study_decl.json",
            "sha256": sha256_file(root / "studies/M09/study_decl.json"),
            "status": declaration.get("status"),
            "blocked_reason": declaration.get("blocked_reason"),
            "v1_card_sha256": declaration.get("v1_card_sha256"),
        },
        "scientific_status": "DEFINITION_SCORE_NOT_AN_ERROR_MEASUREMENT",
        "existing_forecast_mae": "NOT_RUN",
        "historical_validation": "NOT_RUN",
    }
    _write_json(output / "legacy-definition.json", payload)
    return payload


# ---------------------------------------------------------------------------
# Acceptance (read-only root check)
# ---------------------------------------------------------------------------


def _protected_snapshot(root: Path) -> dict[str, Any]:
    snapshot = {
        "protected": {
            path: sha256_file(root / path) for path in PROTECTED_SHA256
        },
        "m09_card_sha256": _read_json(root / "studies/M09/study_decl.json").get(
            "v1_card_sha256"
        ),
        "study_decl_sha256": sha256_file(root / "studies/M09/study_decl.json"),
        "user_files": {
            path: sha256_file(root / path)
            for path in (
                ".omp/config.yml",
                "docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md",
                "docs/upgrade_review/HIST_VNEXT/06_OMP_MINIMAX_HANDOFF.md",
            )
        },
    }
    return snapshot


def run_acceptance(root: Path, *, output_dir: Path) -> dict[str, Any]:
    from hsm_lab.evidence.provenance import verify_run_identity

    root = Path(root).resolve()
    output = (
        Path(output_dir).resolve()
        if Path(output_dir).is_absolute()
        else (root / output_dir).resolve()
    )
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "phase_id": "H5F-F1",
        "status": "PASS",
        "technical": {},
        "structural": {},
        "historical": "NOT_RUN",
        "failures": [],
    }

    def fail(section: str, message: str) -> None:
        result["status"] = "FAIL"
        result["failures"].append({"section": section, "error": message})

    snapshot_path = output / "protected_snapshot.json"
    if snapshot_path.exists():
        snapshot = _read_json(snapshot_path)
    else:
        snapshot = _protected_snapshot(root)
        fail("protected", "protected_snapshot.json is missing")
    current = _protected_snapshot(root)
    for path, expected in PROTECTED_SHA256.items():
        actual = current["protected"].get(path)
        if actual != expected:
            fail("protected", f"{path} SHA changed: {actual} != {expected}")
        if snapshot.get("protected", {}).get(path) != actual:
            fail("protected", f"{path} differs from the protected snapshot")
    if current["m09_card_sha256"] != M09_CARD_SHA256:
        fail("protected", "M09 card SHA changed")
    if snapshot.get("study_decl_sha256") != current["study_decl_sha256"]:
        fail("protected", "studies/M09/study_decl.json changed during the run")
    for path, expected in current["user_files"].items():
        if snapshot.get("user_files", {}).get(path) != expected:
            fail("user-files", f"{path} was modified during the study")

    packages: dict[str, dict[str, Any]] = {}
    current_source_sha256 = _source_sha256(root)
    current_spec_sha256 = sha256_file(root / "studies/HIST_VNEXT/M09/spec.json")
    for name, mode in (
        ("study", "study"),
        ("profile", "profile"),
        ("repeat", "profile"),
        ("smoke", "smoke"),
    ):
        path = output / name
        if not path.is_dir():
            fail("packages", f"{name} package is missing")
            continue
        try:
            packages[name] = _verify_package(path, expected_mode=mode)
            science = _read_json(path / "science.json")
            if science.get("source_sha256") != current_source_sha256:
                fail("packages", f"{name} is not bound to the final source SHA")
            if science.get("spec_sha256") != current_spec_sha256:
                fail("packages", f"{name} is not bound to the final spec SHA")
        except Exception as exc:  # noqa: BLE001 - acceptance reports, never mutates
            fail("packages", f"{name}: {exc}")
    if "profile" in packages and "repeat" in packages:
        if packages["profile"]["science_digest"] != packages["repeat"]["science_digest"]:
            fail("repeat", "profile and repeat science digests differ")
        else:
            result["technical"]["profile_repeat_identical"] = True
    if "study" in packages:
        if packages["study"]["records"] != 48:
            fail("study", "study does not contain exactly 48 paired targets")
        if packages["study"]["first_stage"] != "ESTABLISHED":
            fail("study", "first-stage delay change is not established")
    if "smoke" in packages:
        if packages["smoke"]["records"] != 4:
            fail("smoke", "smoke does not contain exactly 4 paired targets")

    regression_path = output / "regression.json"
    if not regression_path.exists():
        fail("regression", "regression.json is missing")
    else:
        regression = _read_json(regression_path)
        if regression.get("exit_code") != 0:
            fail("regression", "final regression did not exit 0")
        result["technical"]["regression"] = regression

    c0_path = output / "C0"
    c1_path = output / "C1"
    for name, scenario_id, expected_digest, expected_parameter_hash, path in (
        (
            "C0",
            "historical_f2_replay",
            C0_EXPECTED_DIGEST,
            C0_EXPECTED_PARAMETER_HASH,
            c0_path,
        ),
        (
            "C1",
            "historical_f2_trade_scenario",
            C1_EXPECTED_DIGEST,
            C1_EXPECTED_PARAMETER_HASH,
            c1_path,
        ),
    ):
        if not path.is_dir():
            fail("baseline", f"{name} output is missing")
            continue
        try:
            manifest = verify_run_identity(
                root=root,
                scenario_id=scenario_id,
                seed=1729,
                expected_digest=expected_digest,
                output_dir=path,
            )
            parameters = _read_json(path / "parameters.json")
            parameter_hash = parameters.get("parameter_hash")
            if parameter_hash != expected_parameter_hash:
                fail(
                    "baseline",
                    f"{name} parameter_hash {parameter_hash} != {expected_parameter_hash}",
                )
            result["technical"][name] = {
                "run_id": manifest.run_id,
                "completed_ticks": manifest.completed_ticks,
                "deterministic_replay_digest": manifest.deterministic_replay_digest,
                "parameter_hash": parameter_hash,
            }
        except Exception as exc:  # noqa: BLE001 - report only
            fail("baseline", f"{name}: {exc}")

    result["structural"] = {
        "m09_registration": "blocked (unchanged)",
        "historical_plan_implementation_sources": "MISSING",
        "historical_validation": "NOT_RUN",
        "synthetic_profile_only": True,
    }
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=("reproduce", "smoke", "profile", "study", "verify", "acceptance"),
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--spec", default=str(DEFAULT_SPEC))
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    root = Path(args.root)
    output = Path(args.output_dir)
    try:
        if args.mode == "reproduce":
            run_reproduce(root, output_dir=output)
            print(json.dumps({"status": "ok", "mode": "reproduce"}, indent=2))
            return 0
        if args.mode == "verify":
            result = _verify_package(output)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.mode == "acceptance":
            result = run_acceptance(root, output_dir=output)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["status"] == "PASS" else 1
        manifest = run_experiment(
            root,
            spec_path=Path(args.spec),
            output_dir=output,
            mode=args.mode,
        )
        print(json.dumps({"status": "ok", "manifest": manifest}, indent=2))
        return 0
    except (RunnerError, ConfigError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
