"""Material end-of-quarter checkpoints: atomic publish, strict resume gates.

Format ``material-checkpoint-v4``. A checkpoint is only ever written after a
tick has fully passed its accounting invariants (``completed_ticks``
boundary) and is published atomically via a ``.tmp-<uuid>`` staging
directory + ``os.replace``. Resume verifies payload digests, versions,
scenario identity, axes, the compiled-network static hash, the state
field-spec (shape/dtype/finite/range), RNG state and the history/digest
boundary before the caller creates any output directory.

Toy-4 checkpoints are refused explicitly ("version unsupported") before any
output creation; there is no migration and no prefix re-execution.

Environment hashes that need the repository (lock hash, consumed-input
artifact hashes) are re-verified by the runner's own preflight — this module
has no registry parameter by the pinned signature and never guesses.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import numpy as np

from hsm_lab.contract.guards import sha256_file
from hsm_lab.contract.material import ORGANIZATION_TYPE_ORDER, legal_stages
from hsm_lab.contract.schemas import (
    ResearchContract,
    ResearchGateError,
    ScenarioSpec,
)
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import (
    MATERIAL_STATE_VERSION,
    N_D,
    N_E,
    N_H,
    N_Q,
    ExportReceivable,
    MaterialHistory,
    MaterialState,
)
from hsm_lab.engine.trade import validate_receivable_book
from hsm_lab.storage.material_output import (
    AGGREGATE_COLUMNS,
    BUDGET_COLUMNS,
    DEPARTMENT_COLUMNS,
    DIAGNOSTIC_COLUMNS,
    EVENT_COLUMNS,
    FINANCIAL_COLUMNS,
    MATERIAL_TICK_EVENT,
    NATIONAL_COLUMNS,
    ORGANIZATION_COLUMNS,
    STAGE_COLUMNS,
    TABLES,
)
from hsm_lab.storage.political_output import (
    INFORMATION_QUARTERS,
    OPPOSITION_REGIONS,
    POLICY_DECISIONS,
    POLITICAL_COLUMNS,
    POLITICAL_EVENTS,
    POLITICAL_INT_COLUMNS,
    POLITICAL_KEYS,
    POLITICAL_QUARTERS,
    POLITICAL_STRING_COLUMNS,
    POLITICAL_TABLES,
)

# v6 adds the H3F-D2 export-receivable book/event log (a JSON sidecar in the
# same hashed payload).  v5 added the H3F-D1 Treasury term-loan scalars.  The
# material state version string stays v4 because replay digests over the array
# field set must remain byte-identical for C0/C1; old checkpoints are refused
# explicitly by this version gate rather than silently misread.
CHECKPOINT_VERSION = "material-checkpoint-v6"
STATE_VERSION = MATERIAL_STATE_VERSION  # "material-state-v4"
ENGINE_VERSION = "material-engine-v4"

_TOY4_CHECKPOINT_VERSIONS = ("toy4-checkpoint-v1",)

# ---------------------------------------------------------------------------
# Shared state field-spec: the single authority for serialization and
# validation. Save walks the dataclass and refuses any drift from this spec,
# so a new MaterialState ndarray field can never silently escape a payload.
# ---------------------------------------------------------------------------

_STATE_ARRAY_SPEC: tuple[tuple[str, np.dtype, str], ...] = (
    ("stock_value", np.dtype("<f8"), "S"),
    ("household_id", np.dtype("<i8"), "N"),
    ("household_region", np.dtype("<i4"), "N"),
    ("household_weight", np.dtype("<f8"), "N"),
    ("household_size", np.dtype("<f8"), "N"),
    ("household_cash", np.dtype("<f8"), "N"),
    ("household_deferred_receipt", np.dtype("<f8"), "N"),
    ("household_wage_claim", np.dtype("<f8"), "N"),
    ("household_urban", np.dtype("?"), "N"),
    ("household_occupation", np.dtype("i1"), "N"),
    ("household_sector", np.dtype("<i2"), "N"),
    ("household_education", np.dtype("i1"), "N"),
    ("household_children", np.dtype("<i2"), "N"),
    ("household_adults", np.dtype("<i2"), "N"),
    ("household_elderly", np.dtype("<i2"), "N"),
    ("household_working_adults", np.dtype("<f8"), "N"),
    ("household_pay_weight", np.dtype("<f8"), "N"),
    ("household_plot_participating", np.dtype("?"), "N"),
    ("household_second_participating", np.dtype("?"), "N"),
    ("household_western_exposure", np.dtype("<f8"), "N"),
    ("household_tenure", np.dtype("i1"), "N"),
    ("household_informal_access", np.dtype("<f8"), "N"),
    ("household_dwelling_access", np.dtype("<f8"), "N"),
    ("household_housing_wait", np.dtype("<i4"), "N"),
    ("household_last_income", np.dtype("<f8"), "N"),
    ("household_reference_income", np.dtype("<f8"), "N"),
    ("household_last_price_index", np.dtype("<f8"), "N"),
    ("household_initial_service_value", np.dtype("<f8"), "N"),
    ("household_reserved_plot_hours", np.dtype("<f8"), "N"),
    ("household_reserved_second_hours", np.dtype("<f8"), "N"),
    ("household_formal_effort", np.dtype("<f8"), "N"),
    ("household_material_satisfaction", np.dtype("<f8"), "N"),
    ("household_political_compliance", np.dtype("<f8"), "N"),
    ("household_grievance", np.dtype("<f8"), "N"),
    ("household_durable_owned", np.dtype("<f8"), "N"),
    ("household_durable_age", np.dtype("<f8"), "N"),
    ("household_durable_backlog", np.dtype("<f8"), "N"),
    ("household_durable_wait", np.dtype("<i4"), "N"),
    ("household_durable_repair_credit", np.dtype("<f8"), "N"),
    ("household_consumption_reference", np.dtype("<f8"), "N"),
    ("household_last_consumption", np.dtype("<f8"), "N"),
    ("household_last_availability_unmet", np.dtype("<f8"), "N"),
    ("household_entitlement", np.dtype("<f8"), "N"),
    ("household_expectation", np.dtype("<f8"), "N"),
    ("household_improvement_streak", np.dtype("<i4"), "N"),
    ("dwelling_stock", np.dtype("<f8"), "R"),
    ("housing_vacant", np.dtype("<f8"), "R"),
    ("second_output_stock", np.dtype("<f8"), "R"),
    ("organization_id", np.dtype("<i8"), "O"),
    ("organization_type", np.dtype("i1"), "O"),
    ("organization_region", np.dtype("<i4"), "O"),
    ("organization_technology", np.dtype("<i4"), "O"),
    ("organization_activity", np.dtype("<i4"), "O"),
    ("organization_bank", np.dtype("<i4"), "O"),
    ("organization_capacity", np.dtype("<f8"), "O"),
    ("organization_labor_available", np.dtype("<f8"), "O"),
    ("organization_labor_endowment", np.dtype("<f8"), "O"),
    ("organization_effort_factor", np.dtype("<f8"), "O"),
    ("organization_labor_per_activity", np.dtype("<f8"), "O"),
    ("organization_cash", np.dtype("<f8"), "O"),
    ("organization_wage_arrears", np.dtype("<f8"), "O"),
    ("organization_interest_arrears", np.dtype("<f8"), "O"),
    ("organization_principal", np.dtype("<f8"), "O"),
    ("organization_shortage_expectation", np.dtype("<f8"), "O"),
    ("organization_demand_signal", np.dtype("<f8"), "O"),
    ("organization_bailout_expectation", np.dtype("<f8"), "O"),
    ("organization_project_approved", np.dtype("<f8"), "O"),
    ("organization_capital_wip", np.dtype("<f8"), "O"),
    ("organization_construction_wip", np.dtype("<f8"), "O"),
    ("organization_capital_age", np.dtype("<f8"), "O"),
    ("plot_capacity", np.dtype("<f8"), "R"),
    ("plot_labor_budget", np.dtype("<f8"), "R"),
    ("plot_activity", np.dtype("<i4"), "R"),
    ("bank_reserves", np.dtype("<f8"), "B"),
    ("bank_loan_asset", np.dtype("<f8"), "B"),
    ("bank_deposit_liability", np.dtype("<f8"), "B"),
    ("bank_equity", np.dtype("<f8"), "B"),
    ("bank_interest_receivable", np.dtype("<f8"), "B"),
)

#: Fields whose trailing dimension is a fixed household axis (H/D/E/Q) or the
#: commodity axis (G).  ``_TRAILING_SIZES`` fixes the household axes; the
#: commodity axis is validated from the payload length when available.
_STATE_TRAILING: dict[str, str] = {
    "household_durable_owned": "D",
    "household_durable_age": "D",
    "household_durable_backlog": "D",
    "household_durable_wait": "D",
    "household_durable_repair_credit": "D",
    "household_consumption_reference": "H",
    "household_last_consumption": "H",
    "household_last_availability_unmet": "H",
    "household_entitlement": "E",
    "household_expectation": "E",
    "household_improvement_streak": "E",
    "second_output_stock": "G",
}
_TRAILING_SIZES: dict[str, int] = {"D": N_D, "E": N_E, "H": N_H, "Q": N_Q}

_STATE_SCALAR_SPEC: tuple[tuple[str, np.dtype], ...] = (
    ("treasury_deposit", np.dtype("<f8")),
    ("treasury_loan_asset", np.dtype("<f8")),
    ("credit_fund", np.dtype("<f8")),
    ("usd_reserve", np.dtype("<f8")),
    ("usd_principal", np.dtype("<f8")),
    ("usd_interest_arrears", np.dtype("<f8")),
    ("cmea_settlement_balance", np.dtype("<f8")),
    ("treasury_loan_principal", np.dtype("<f8")),
    ("treasury_interest_arrears", np.dtype("<f8")),
    ("treasury_loan_maturity_tick", np.dtype("<f8")),
    ("treasury_loan_rate", np.dtype("<f8")),
)

# Non-negative state fields (cmea settlement may go negative as memo credit;
# capital_age is monotone). ATOL slack mirrors the accounting gates.
_STATE_NON_NEGATIVE = (
    "stock_value",
    "household_weight",
    "household_size",
    "household_cash",
    "household_deferred_receipt",
    "household_wage_claim",
    "household_working_adults",
    "household_children",
    "household_adults",
    "household_elderly",
    "household_pay_weight",
    "household_western_exposure",
    "household_dwelling_access",
    "household_housing_wait",
    "household_last_income",
    "household_reference_income",
    "household_last_price_index",
    "household_initial_service_value",
    "household_reserved_plot_hours",
    "household_reserved_second_hours",
    "household_formal_effort",
    "household_durable_owned",
    "household_durable_age",
    "household_durable_backlog",
    "household_durable_repair_credit",
    "household_consumption_reference",
    "household_last_consumption",
    "household_last_availability_unmet",
    "dwelling_stock",
    "housing_vacant",
    "second_output_stock",
    "organization_capacity",
    "organization_labor_available",
    "organization_labor_per_activity",
    "organization_cash",
    "organization_principal",
    "organization_project_approved",
    "organization_capital_wip",
    "organization_construction_wip",
    "organization_capital_age",
    "plot_capacity",
    "plot_labor_budget",
    "bank_reserves",
    "bank_loan_asset",
    "bank_deposit_liability",
    "bank_equity",
    "bank_interest_receivable",
    "treasury_deposit",
    "usd_reserve",
    "usd_principal",
    "usd_interest_arrears",
    "treasury_loan_principal",
    "treasury_interest_arrears",
    "treasury_loan_rate",
)

_STATE_UNIT_RANGE = (
    "organization_shortage_expectation",
    "organization_bailout_expectation",
    "household_informal_access",
    "household_material_satisfaction",
    "household_political_compliance",
    "household_grievance",
    "household_entitlement",
    "household_expectation",
)

_NETWORK_ARRAY_SPEC: tuple[tuple[str, np.dtype], ...] = (
    ("cell_owner_kind", np.dtype("i1")),
    ("cell_owner_id", np.dtype("<i8")),
    ("cell_region", np.dtype("<i4")),
    ("cell_pool", np.dtype("i1")),
    ("cell_commodity", np.dtype("i2")),
    ("cell_stage", np.dtype("i1")),
    ("activity_kind", np.dtype("i1")),
    ("activity_org_index", np.dtype("<i4")),
    ("activity_region", np.dtype("<i4")),
    ("activity_capacity", np.dtype("<f8")),
    ("activity_early_service", np.dtype("?")),
    ("input_cell", np.dtype("<i4")),
    ("input_activity", np.dtype("<i4")),
    ("input_timing", np.dtype("i1")),
    ("demand_cell", np.dtype("<i4")),
    ("demand_purpose", np.dtype("i1")),
    ("demand_activity", np.dtype("<i4")),
    ("demand_input_index", np.dtype("<i4")),
    ("demand_share", np.dtype("<f8")),
    ("edge_source_cell", np.dtype("<i4")),
    ("edge_destination_cell", np.dtype("<i4")),
    ("edge_demand", np.dtype("<i4")),
    ("edge_commodity", np.dtype("i2")),
    ("edge_stage", np.dtype("i1")),
    ("edge_purpose", np.dtype("i1")),
    ("edge_weight", np.dtype("<f8")),
    ("edge_transport_org", np.dtype("<i4")),
    ("edge_transport_per_unit", np.dtype("<f8")),
    ("edge_buyer_org", np.dtype("<i4")),
    ("edge_self_hauled", np.dtype("?")),
    ("edge_is_fallback", np.dtype("?")),
    ("edge_transport_service_cell", np.dtype("<i4")),
    ("edge_distance", np.dtype("<f8")),
    ("region_distance", np.dtype("<f8")),
    ("edge_id", np.dtype("<i8")),
    ("org_output_cell", np.dtype("<i4")),
    ("org_wholesale_cell", np.dtype("<i4")),
    ("plot_input_cells", np.dtype("<i4")),
    ("plot_raw_cell", np.dtype("<i4")),
    ("plot_ready_self_cell", np.dtype("<i4")),
    ("plot_ready_market_cell", np.dtype("<i4")),
    ("retail_cell", np.dtype("<i4")),
    ("retail_cell_by_commodity", np.dtype("<i4")),
    ("import_pool_cell", np.dtype("<i4")),
    ("project_capital_cell", np.dtype("<i4")),
    ("project_construction_cell", np.dtype("<i4")),
    ("export_demand_cell", np.dtype("<i4")),
)

_HISTORY_COLUMNS = {
    "aggregates": AGGREGATE_COLUMNS,
    "stage_balances": STAGE_COLUMNS,
    "national_accounts": NATIONAL_COLUMNS,
    "household_budgets": BUDGET_COLUMNS,
    "organization_diagnostics": ORGANIZATION_COLUMNS,
    "financial_accounts": FINANCIAL_COLUMNS,
    "departments": DEPARTMENT_COLUMNS,
    "tick_diagnostics": DIAGNOSTIC_COLUMNS,
    "events": EVENT_COLUMNS,
    **POLITICAL_COLUMNS,
}

_HISTORY_KEYS = {
    "aggregates": ["tick", "region_id", "commodity_id"],
    "stage_balances": ["tick", "region_id", "commodity_id", "stage"],
    "national_accounts": ["tick", "commodity_id"],
    "household_budgets": ["tick", "region_id"],
    "organization_diagnostics": ["tick", "region_id", "organization_type"],
    "financial_accounts": ["tick", "account_id", "currency"],
    "departments": ["tick", "department"],
    "tick_diagnostics": ["tick"],
    "events": ["tick"],
    **POLITICAL_KEYS,
}

_HISTORY_INT_COLUMNS = {
    "aggregates": {"tick"},
    "stage_balances": {"tick"},
    "national_accounts": {"tick"},
    "household_budgets": {"tick"},
    "organization_diagnostics": {"tick", "organization_count"},
    "financial_accounts": {"tick", "account_id"},
    "departments": {"tick"},
    "tick_diagnostics": {"tick", "checked_cells", "bottleneck_demand_count"},
    "events": {"tick"},
    **POLITICAL_INT_COLUMNS,
}

_HISTORY_STRING_COLUMNS = {
    "aggregates": {"quarter", "region_id", "commodity_id"},
    "stage_balances": {"quarter", "region_id", "commodity_id", "stage"},
    "national_accounts": {"quarter", "commodity_id"},
    "household_budgets": {"quarter", "region_id"},
    "organization_diagnostics": {"quarter", "region_id", "organization_type"},
    "financial_accounts": {"quarter", "currency", "account_label"},
    "departments": {"quarter", "department"},
    "tick_diagnostics": {"quarter", "digest", "forcing_segment"},
    "events": {"quarter", "event_type", "details_json"},
    **POLITICAL_STRING_COLUMNS,
}

# Nullable-by-design columns (unavailable boundary values; never 0-faked).
_HISTORY_NULLABLE = {
    "organization_diagnostics": {
        "capacity_mean",
        "labor_mean",
        "shortage_expectation_mean",
        "bailout_expectation_mean",
        "input_bottleneck_share",
    },
    "financial_accounts": {"opening", "residual"},
}


def _spec_drift(walked: set[str], expected: set[str], label: str) -> None:
    if walked != expected:
        raise ResearchGateError(
            f"material {label} field-spec drift: payload fields "
            f"{sorted(walked ^ expected)} differ from the checkpoint spec; "
            "update the shared spec deliberately (no silent state escape)"
        )


def state_arrays(state: MaterialState) -> dict[str, np.ndarray]:
    """Every ndarray field of the state, in shared-spec order."""
    import dataclasses

    arrays = {
        name: np.ascontiguousarray(getattr(state, name))
        for name, _dtype, _axis in _STATE_ARRAY_SPEC
    }
    walked = {
        f.name for f in dataclasses.fields(state) if isinstance(getattr(state, f.name), np.ndarray)
    }
    _spec_drift(walked, {name for name, _d, _a in _STATE_ARRAY_SPEC}, "state")
    return arrays


def network_arrays(network: Any) -> dict[str, np.ndarray]:
    """Every ndarray field of the compiled network, in shared-spec order."""
    import dataclasses

    arrays = {
        name: np.ascontiguousarray(getattr(network, name)) for name, _dtype in _NETWORK_ARRAY_SPEC
    }
    walked = {
        f.name
        for f in dataclasses.fields(network)
        if isinstance(getattr(network, f.name), np.ndarray)
    }
    _spec_drift(walked, {name for name, _d in _NETWORK_ARRAY_SPEC}, "network")
    return arrays


def canonical_array_bytes(entries: dict[str, np.ndarray]) -> bytes:
    """Deterministic little-endian bytes over spec-named arrays."""
    import struct

    chunks: list[bytes] = []
    for name in sorted(entries):
        array = np.ascontiguousarray(entries[name])
        little = np.dtype(array.dtype.newbyteorder("<"))
        contiguous = np.ascontiguousarray(array.astype(little, copy=False))
        header = (
            struct.pack("<Q", len(name))
            + name.encode("utf-8")
            + struct.pack("<Q", contiguous.ndim)
            + struct.pack(f"<{contiguous.ndim}Q", *contiguous.shape)
            + struct.pack("<Q", len(little.str))
            + little.str.encode("ascii")
        )
        chunks.append(struct.pack("<Q", len(header)) + header + contiguous.tobytes())
    return b"".join(chunks)


def canonical_array_hash(entries: dict[str, np.ndarray]) -> str:
    """SHA-256 over :func:`canonical_array_bytes` of the given arrays."""
    import hashlib

    return hashlib.sha256(canonical_array_bytes(entries)).hexdigest()


def network_static_hash(network: Any) -> str:
    """Static hash over the stored network payload (cell/activity/route axes).

    The household catalog is a pure function of the scenario parameters and is
    rebuilt from the spec on resume, so it is not duplicated into the checkpoint
    payload; its own hash is carried in the run manifest instead.
    """
    return canonical_array_hash(network_arrays(network))


def checkpoint_dir(run_dir: Path, completed_ticks: int) -> Path:
    return run_dir / "checkpoints" / f"tick-{completed_ticks:04d}"


RECEIVABLE_PAYLOAD = "receivables.json"


def _receivable_payload(state: MaterialState) -> dict[str, object]:
    import dataclasses

    return {
        "receivables": [
            dataclasses.asdict(lot) for lot in state.export_receivables
        ],
        "event_ids": list(state.export_receivable_event_ids),
    }


def _parse_receivable_payload(
    directory: Path,
) -> tuple[tuple[ExportReceivable, ...], tuple[str, ...]]:
    path = directory / RECEIVABLE_PAYLOAD
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchGateError(f"unreadable checkpoint receivable payload: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != {"receivables", "event_ids"}:
        raise ResearchGateError(
            "checkpoint receivable payload must carry exactly receivables/event_ids"
        )
    raw_lots = payload["receivables"]
    raw_ids = payload["event_ids"]
    if not isinstance(raw_lots, list) or not isinstance(raw_ids, list):
        raise ResearchGateError("checkpoint receivable payload has non-list entries")
    expected = {
        "receivable_id",
        "contract_id",
        "currency",
        "buyer_id",
        "seller_id",
        "commodity_id",
        "delivery_tick",
        "due_tick",
        "principal",
        "gross",
        "provision",
        "written_off",
        "received",
        "recovered",
        "writeoffs",
        "provision_expense",
        "provision_released",
    }
    def _text(entry: dict[str, object], name: str, index: int) -> str:
        value = entry[name]
        if not isinstance(value, str) or not value:
            raise ResearchGateError(
                f"checkpoint receivable {index} {name} must be a non-empty string"
            )
        return value

    def _integer(entry: dict[str, object], name: str, index: int) -> int:
        value = entry[name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ResearchGateError(
                f"checkpoint receivable {index} {name} must be a strict integer"
            )
        return int(value)

    def _amount(entry: dict[str, object], name: str, index: int) -> float:
        value = entry[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ResearchGateError(
                f"checkpoint receivable {index} {name} must be a strict number"
            )
        number = float(value)
        if not np.isfinite(number):
            raise ResearchGateError(
                f"checkpoint receivable {index} {name} must be finite"
            )
        return number

    lots: list[ExportReceivable] = []
    for index, entry in enumerate(raw_lots):
        if not isinstance(entry, dict) or set(entry) != expected:
            raise ResearchGateError(
                f"checkpoint receivable {index} must carry exactly the lot fields"
            )
        lot = ExportReceivable(
            receivable_id=_text(entry, "receivable_id", index),
            contract_id=_text(entry, "contract_id", index),
            currency=_text(entry, "currency", index),
            buyer_id=_integer(entry, "buyer_id", index),
            seller_id=_integer(entry, "seller_id", index),
            commodity_id=_text(entry, "commodity_id", index),
            delivery_tick=_integer(entry, "delivery_tick", index),
            due_tick=_integer(entry, "due_tick", index),
            principal=_amount(entry, "principal", index),
            gross=_amount(entry, "gross", index),
            provision=_amount(entry, "provision", index),
            written_off=_amount(entry, "written_off", index),
            received=_amount(entry, "received", index),
            recovered=_amount(entry, "recovered", index),
            writeoffs=_amount(entry, "writeoffs", index),
            provision_expense=_amount(entry, "provision_expense", index),
            provision_released=_amount(entry, "provision_released", index),
        )
        lots.append(lot)
    event_ids: list[str] = []
    for index, value in enumerate(raw_ids):
        if not isinstance(value, str) or not value:
            raise ResearchGateError(
                f"checkpoint receivable event id {index} must be a non-empty string"
            )
        event_ids.append(value)
    return tuple(lots), tuple(event_ids)


def save_material_checkpoint(
    directory: Path,
    state: MaterialState,
    network: Any,
    history: MaterialHistory,
    rng: RngRegistry,
    metadata: dict[str, object],
    *,
    political_arrays: dict[str, np.ndarray] | None = None,
) -> Path:
    """Atomically publish one end-of-quarter checkpoint; refuse overwrite.

    ``political_arrays`` (when the P04 layer is enabled) are written into the
    same checkpoint directory as ``political.npz`` and are covered by the same
    payload digest map, so a P04 boundary is one immutable, self-describing
    artifact - not a sidecar.
    """
    if directory.exists() or directory.is_symlink():
        raise ResearchGateError(
            f"checkpoint directory {directory} already exists; refusing to overwrite"
        )
    directory.parent.mkdir(parents=True, exist_ok=True)
    staging = directory.parent / f".tmp-{uuid4().hex}"
    staging.mkdir()
    try:
        arrays = state_arrays(state)
        for name, array in arrays.items():
            if array.dtype.hasobject:
                raise ResearchGateError(f"state array {name} has object dtype")
        payload_arrays: dict[str, Any] = {
            "completed_ticks": np.asarray(state.completed_ticks, dtype="<i8"),
            **arrays,
            **{
                name: np.asarray(getattr(state, name), dtype="<f8")
                for name, _dtype in _STATE_SCALAR_SPEC
            },
        }
        np.savez(staging / "state.npz", **payload_arrays)

        network_payload: dict[str, Any] = {
            "schema_version": np.asarray(network.schema_version),
            **network_arrays(network),
        }
        np.savez(staging / "network.npz", **network_payload)
        (staging / RECEIVABLE_PAYLOAD).write_text(
            json.dumps(
                _receivable_payload(state),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )

        from hsm_lab.storage.material_output import history_frames

        frames = history_frames(history)
        for name in TABLES:
            frame = frames[name]
            if frame.height == 0:
                frame = frame.clear()
            frame.write_parquet(staging / f"{name}.parquet")
        payload: dict[str, object] = {
            "checkpoint_version": CHECKPOINT_VERSION,
            "state_version": state.schema_version,
            "engine_version": ENGINE_VERSION,
            "completed_ticks": int(state.completed_ticks),
            "rng_snapshot": rng.snapshot(),
            "digest_chain": history.digest_chain,
            "network_static_hash": network_static_hash(network),
            **metadata,
        }
        if political_arrays:
            np.savez(
                staging / "political.npz",
                **{name: np.ascontiguousarray(array) for name, array in political_arrays.items()},
            )
            payload["political_arrays"] = sorted(political_arrays)
        payload_hashes = {
            entry.name: sha256_file(entry) for entry in sorted(staging.iterdir()) if entry.is_file()
        }
        payload["payload_sha256"] = payload_hashes
        (staging / "metadata.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(staging, directory)
    except BaseException:
        import shutil

        shutil.rmtree(staging, ignore_errors=True)
        raise
    return directory


def _verify_payload_hashes(directory: Path, metadata: dict[str, Any]) -> None:
    declared = metadata.get("payload_sha256")
    if not isinstance(declared, dict):
        raise ResearchGateError("checkpoint metadata lacks payload_sha256 map")
    actual_names = {entry.name for entry in directory.iterdir() if entry.is_file()} - {
        "metadata.json"
    }
    if set(declared) != actual_names:
        raise ResearchGateError(
            f"checkpoint payload file set mismatch: declared {sorted(declared)} "
            f"vs present {sorted(actual_names)}"
        )
    for name, digest in sorted(declared.items()):
        path = directory / name
        if not path.is_file():
            raise ResearchGateError(f"checkpoint payload {name} is missing")
        if sha256_file(path) != digest:
            raise ResearchGateError(f"checkpoint payload {name}: digest mismatch")


def _load_metadata(directory: Path) -> dict[str, Any]:
    if not directory.is_dir():
        raise ResearchGateError(f"checkpoint directory not found: {directory}")
    try:
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchGateError(f"unreadable checkpoint metadata: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ResearchGateError("checkpoint metadata must be a JSON object")
    return metadata


def _gate_versions(metadata: dict[str, Any]) -> None:
    version = metadata.get("checkpoint_version")
    if version != CHECKPOINT_VERSION:
        if version in _TOY4_CHECKPOINT_VERSIONS or str(version).startswith("toy4"):
            raise ResearchGateError(
                f"unsupported checkpoint version {version!r}: Toy-4 checkpoints are "
                "refused (version unsupported); the Toy-4 engine was removed and "
                "there is no migration path"
            )
        raise ResearchGateError(f"unsupported checkpoint version {version!r}")
    if metadata.get("state_version") != STATE_VERSION:
        raise ResearchGateError("checkpoint state schema version mismatch")
    if metadata.get("engine_version") != ENGINE_VERSION:
        raise ResearchGateError("checkpoint engine version mismatch")


def _state_from_payload(
    payload: Any,
    completed: int,
    *,
    catalog: Any = None,
    receivables: tuple[ExportReceivable, ...] = (),
    receivable_event_ids: tuple[str, ...] = (),
) -> tuple[MaterialState, dict[str, np.ndarray]]:
    raw_completed = np.asarray(payload["completed_ticks"])
    if raw_completed.dtype != np.dtype("<i8") or raw_completed.shape != ():
        raise ResearchGateError(
            "checkpoint completed_ticks must be a scalar int64 array "
            f"(got dtype {raw_completed.dtype}, shape {raw_completed.shape})"
        )
    present = set(payload.files) - {"completed_ticks"}
    expected = {name for name, _d, _a in _STATE_ARRAY_SPEC} | {
        name for name, _d in _STATE_SCALAR_SPEC
    }
    _spec_drift(set(present), expected, "state payload")
    trailing_sizes = dict(_TRAILING_SIZES)
    if catalog is not None:
        trailing_sizes["H"] = len(catalog.household_good_ids)
        trailing_sizes["D"] = len(catalog.durable_ids)
        trailing_sizes["Q"] = len(catalog.substitution_ids)
    axes: dict[str, int] = {}
    for _name, _dtype, axis in _STATE_ARRAY_SPEC:
        if axis in axes:
            continue
        first = next(n for n, d, a in _STATE_ARRAY_SPEC if a == axis)
        axes[axis] = int(np.asarray(payload[first]).shape[0])
    arrays: dict[str, np.ndarray] = {}
    for name, dtype, axis in _STATE_ARRAY_SPEC:
        target = np.dtype(dtype)
        raw = np.asarray(payload[name])
        if raw.dtype != target:
            raise ResearchGateError(
                f"checkpoint state array {name} has dtype {raw.dtype}, "
                f"expected exactly {target} (silent coercion is refused)"
            )
        trailing = _STATE_TRAILING.get(name)
        if trailing is None:
            if raw.ndim != 1 or raw.shape[0] != axes[axis]:
                raise ResearchGateError(
                    f"checkpoint state array {name} has shape {raw.shape}, expected ({axes[axis]},)"
                )
        else:
            expected_trailing = trailing_sizes.get(trailing)
            if (
                raw.ndim != 2
                or raw.shape[0] != axes[axis]
                or (expected_trailing is not None and raw.shape[1] != expected_trailing)
            ):
                raise ResearchGateError(
                    f"checkpoint state array {name} has shape {raw.shape}, "
                    f"expected a 2-D ({axes[axis]}, {trailing}) array"
                )
        arrays[name] = np.ascontiguousarray(raw)
    scalars: dict[str, float] = {}
    for name, dtype in _STATE_SCALAR_SPEC:
        raw = np.asarray(payload[name])
        if raw.dtype != np.dtype(dtype) or raw.shape != ():
            raise ResearchGateError(
                f"checkpoint state scalar {name} must be a 0-d {dtype} array "
                f"(got dtype {raw.dtype}, shape {raw.shape})"
            )
        scalars[name] = float(raw.item())
    state = MaterialState(
        schema_version=STATE_VERSION,
        completed_ticks=completed,
        export_receivables=receivables,
        export_receivable_event_ids=receivable_event_ids,
        **cast("dict[str, Any]", arrays),
        **cast("dict[str, Any]", scalars),
    )
    return state, arrays


def _validate_state(
    state: MaterialState,
    arrays: dict[str, np.ndarray],
    snapshot: ScenarioSpec,
    network: Any,
) -> None:
    from hsm_lab.engine.accounting import ATOL

    regions = len(snapshot.region_ids)
    households = int(snapshot.households)
    org_count = arrays["organization_id"].shape[0]
    bank_count = arrays["bank_reserves"].shape[0]
    activity_count = int(np.asarray(network.activity_kind).shape[0])
    if arrays["household_id"].shape[0] != households:
        raise ResearchGateError("checkpoint household axis disagrees with the scenario")
    if snapshot.organizations is not None and org_count != int(snapshot.organizations):
        raise ResearchGateError("checkpoint organization axis disagrees with the scenario")
    if arrays["dwelling_stock"].shape[0] != regions:
        raise ResearchGateError("checkpoint region axis disagrees with the scenario")
    if len(set(state.household_id.tolist())) != households:
        raise ResearchGateError("checkpoint household ids are not unique")
    if len(set(state.organization_id.tolist())) != org_count:
        raise ResearchGateError("checkpoint organization ids are not unique")
    for name in (name for name, _d, _a in _STATE_ARRAY_SPEC):
        values = arrays[name]
        if not np.all(np.isfinite(values)):
            raise ResearchGateError(f"checkpoint state array {name} is not finite")
    for name in _STATE_NON_NEGATIVE:
        field_values = arrays.get(name)
        if field_values is None:
            field_values = np.asarray(getattr(state, name))
        if float(np.min(field_values)) < -ATOL:
            raise ResearchGateError(f"checkpoint state field {name} is negative")
    for name in _STATE_UNIT_RANGE:
        values = arrays[name]
        if float(np.min(values)) < -ATOL or float(np.max(values)) > 1.0 + ATOL:
            raise ResearchGateError(f"checkpoint state field {name} lies outside [0, 1]")
    if (
        state.treasury_deposit < -ATOL
        or state.usd_reserve < -ATOL
        or state.treasury_loan_principal < -ATOL
        or state.treasury_interest_arrears < -ATOL
        or state.treasury_loan_rate < -ATOL
        or state.treasury_loan_maturity_tick < -1.0 - ATOL
    ):
        raise ResearchGateError("checkpoint treasury/usd/loan accounts are negative")
    try:
        validate_receivable_book(
            tuple(state.export_receivables),
            tuple(state.export_receivable_event_ids),
            completed_ticks=int(state.completed_ticks),
            commodity_ids=tuple(network.commodity_ids),
        )
    except ValueError as exc:
        raise ResearchGateError(f"checkpoint receivable semantics rejected: {exc}") from exc
    index_checks = (
        ("household_region", arrays["household_region"], regions),
        ("organization_region", arrays["organization_region"], regions),
        (
            "organization_technology",
            arrays["organization_technology"],
            len(snapshot.technologies or []),
        ),
        ("organization_activity", arrays["organization_activity"], activity_count),
        ("organization_bank", arrays["organization_bank"], bank_count),
        ("plot_activity", arrays["plot_activity"], activity_count),
    )
    for name, values, bound in index_checks:
        if values.size and (int(values.min()) < -1 or int(values.max()) >= max(bound, 1)):
            raise ResearchGateError(f"checkpoint index array {name} falls outside its axis")


def _validate_political_history_table(
    name: str,
    frame: Any,
    snapshot: ScenarioSpec,
    completed: int,
) -> None:
    """Validate one P04 table (typed empty when politics is disabled)."""
    import polars as pl

    from hsm_lab.contract.politics import POLITICAL_FEATURE_IDS

    columns = _HISTORY_COLUMNS[name]
    if frame.columns != columns:
        raise ResearchGateError(
            f"checkpoint political table {name} schema differs from the writer's"
        )
    for column in columns:
        if column in _HISTORY_INT_COLUMNS[name]:
            expected: Any = pl.Int64
        elif column in _HISTORY_STRING_COLUMNS[name]:
            expected = pl.String
        else:
            expected = pl.Float64
        if frame.schema[column] != expected:
            raise ResearchGateError(
                f"checkpoint political table {name}.{column} has dtype "
                f"{frame.schema[column]}, expected exactly {expected}"
            )
    numeric = [column for column in columns if column not in _HISTORY_STRING_COLUMNS[name]]
    for column in numeric:
        series = frame[column].drop_nulls()
        if series.len() and not series.is_finite().all():
            raise ResearchGateError(
                f"checkpoint political table {name}.{column} has non-finite values"
            )
    if frame.height and frame.group_by(_HISTORY_KEYS[name]).len().filter(pl.col("len") > 1).height:
        raise ResearchGateError(f"checkpoint political table {name} contains duplicate keys")
    if frame.height:
        bad_quarter = frame.filter(
            pl.col("quarter")
            != pl.col("tick").map_elements(
                lambda tick: str(snapshot.start.advance(int(tick))),
                return_dtype=pl.String,
            )
        )
        if bad_quarter.height:
            raise ResearchGateError(
                f"checkpoint political table {name} has rows whose quarter disagrees "
                "with the scenario calendar"
            )
    enabled = snapshot.politics is not None
    if not enabled:
        if frame.height:
            raise ResearchGateError(
                f"checkpoint political table {name} must be empty when politics is None"
            )
        return
    observed_ticks = sorted(frame["tick"].unique().to_list()) if frame.height else []
    if set(observed_ticks) - set(range(completed)):
        raise ResearchGateError(
            f"checkpoint political table {name} references ticks beyond the boundary"
        )
    regions = list(snapshot.region_ids)
    if name == POLITICAL_QUARTERS:
        if observed_ticks != list(range(completed)) or frame.height != completed:
            raise ResearchGateError(
                f"checkpoint political_quarters must cover ticks 0..{completed - 1} exactly"
            )
    elif name == OPPOSITION_REGIONS:
        if observed_ticks != list(range(completed)) or frame.height != completed * len(regions):
            raise ResearchGateError(
                "checkpoint opposition_regions must cover every region on every tick"
            )
        unknown = set(frame["region_id"].unique().to_list()) - set(regions)
        if unknown:
            raise ResearchGateError(
                f"checkpoint opposition_regions references unknown regions {sorted(unknown)}"
            )
    elif name == INFORMATION_QUARTERS:
        if observed_ticks != list(range(completed)) or frame.height != completed * len(
            POLITICAL_FEATURE_IDS
        ):
            raise ResearchGateError(
                "checkpoint information_quarters must cover every feature on every tick"
            )
        unknown = set(frame["feature_id"].unique().to_list()) - set(POLITICAL_FEATURE_IDS)
        if unknown:
            raise ResearchGateError(
                f"checkpoint information_quarters references unknown features {sorted(unknown)}"
            )
    # policy_decisions / political_events may be empty (Mode A / no events) and
    # carry no fixed per-tick height.


_POLITICAL_TABLE_SET = frozenset(POLITICAL_TABLES)


def _validate_history_frames(
    frames: dict[str, Any],
    state: MaterialState,
    snapshot: ScenarioSpec,
    completed: int,
) -> None:
    import polars as pl

    regions = list(snapshot.region_ids)
    commodities = list(snapshot.commodities)
    stage_cells = sum(len(legal_stages(c)) for c in commodities)
    bank_count = int(state.bank_reserves.shape[0])
    expected_heights = {
        "aggregates": completed * len(regions) * len(commodities),
        "stage_balances": completed * (len(regions) + 1) * stage_cells,
        "national_accounts": completed * len(commodities),
        "household_budgets": completed * len(regions),
        "organization_diagnostics": completed * len(regions) * len(ORGANIZATION_TYPE_ORDER),
        "financial_accounts": completed * (bank_count + 3),
        "departments": completed * 5,
        "tick_diagnostics": completed,
        "events": completed,
    }
    for name in TABLES:
        frame = frames[name]
        if name in _POLITICAL_TABLE_SET:
            _validate_political_history_table(name, frame, snapshot, completed)
            continue
        if frame.columns != _HISTORY_COLUMNS[name]:
            raise ResearchGateError(
                f"checkpoint history table {name} schema differs from the writer's"
            )
        expected_dtype: Any
        for column in _HISTORY_COLUMNS[name]:
            if column in _HISTORY_INT_COLUMNS[name]:
                expected_dtype = pl.Int64
            elif column in _HISTORY_STRING_COLUMNS[name]:
                expected_dtype = pl.String
            else:
                expected_dtype = pl.Float64
            if frame.schema[column] != expected_dtype:
                raise ResearchGateError(
                    f"checkpoint history table {name}.{column} has dtype "
                    f"{frame.schema[column]}, expected exactly {expected_dtype}"
                )
        nullable = set(_HISTORY_NULLABLE.get(name, set()))
        if name == "stage_balances":
            nullable.add("region_id")  # exactly one national-owner row per tick
        for column in _HISTORY_COLUMNS[name]:
            if column in nullable:
                continue
            if frame[column].null_count():
                raise ResearchGateError(f"checkpoint history table {name}.{column} has null values")
        if name == "stage_balances":
            national_ticks = frame.filter(pl.col("region_id").is_null())["tick"]
            if national_ticks.n_unique() != completed or national_ticks.len() != (
                completed * sum(len(legal_stages(c)) for c in snapshot.commodities)
            ):
                raise ResearchGateError(
                    "checkpoint stage_balances must carry exactly one complete "
                    "national-owner row grid per tick"
                )
        numeric = [
            column
            for column in _HISTORY_COLUMNS[name]
            if column not in _HISTORY_STRING_COLUMNS[name]
        ]
        for column in numeric:
            series = frame[column].drop_nulls()
            if series.len() and not series.is_finite().all():
                raise ResearchGateError(
                    f"checkpoint history table {name}.{column} has non-finite values"
                )
        if frame.group_by(_HISTORY_KEYS[name]).len().filter(pl.col("len") > 1).height:
            raise ResearchGateError(f"checkpoint history table {name} contains duplicate keys")
        observed_ticks = sorted(frame["tick"].unique().to_list())
        if observed_ticks != list(range(completed)):
            raise ResearchGateError(
                f"checkpoint history table {name} does not cover ticks 0..{completed - 1} exactly"
            )
        if frame.height != expected_heights[name]:
            raise ResearchGateError(
                f"checkpoint history table {name} has {frame.height} rows, "
                f"expected {expected_heights[name]} for the declared axes"
            )
        bad_quarter = frame.filter(
            pl.col("quarter")
            != pl.col("tick").map_elements(
                lambda tick: str(snapshot.start.advance(int(tick))),
                return_dtype=pl.String,
            )
        )
        if bad_quarter.height:
            raise ResearchGateError(
                f"checkpoint history table {name} has rows whose quarter disagrees "
                "with the scenario calendar"
            )

    axis_checks = (
        ("aggregates", "region_id", regions),
        ("aggregates", "commodity_id", commodities),
        (
            "stage_balances",
            "region_id",
            [*regions, None],
        ),
        ("stage_balances", "commodity_id", commodities),
        ("national_accounts", "commodity_id", commodities),
        ("household_budgets", "region_id", regions),
        (
            "organization_diagnostics",
            "organization_type",
            [t.value for t in ORGANIZATION_TYPE_ORDER],
        ),
    )
    for table, column, allowed in axis_checks:
        observed = set(frames[table][column].unique().to_list())
        unknown = observed - set(allowed)
        if unknown:
            raise ResearchGateError(
                f"checkpoint history {table}.{column} references unknown "
                f"values {sorted(unknown, key=str)}"
            )


def _validate_history_consistency(
    frames: dict[str, Any],
    state: MaterialState,
    snapshot: ScenarioSpec,
    completed: int,
    network: Any,
) -> None:
    import polars as pl

    from hsm_lab.engine.accounting import ATOL, RTOL

    def tol(lhs: float, rhs: float) -> float:
        return ATOL + RTOL * max(abs(lhs), abs(rhs))

    diagnostics = frames["tick_diagnostics"]
    for column in (
        "max_material_abs_residual",
        "max_material_tolerance_ratio",
        "max_finance_abs_residual",
        "max_finance_tolerance_ratio",
    ):
        series = diagnostics[column].drop_nulls()
        if series.len() and (bool((series < 0.0).any()) or bool((series > 1.0).any())):
            raise ResearchGateError(f"checkpoint diagnostics {column} lies outside [0, 1]")

    # adjacent-quarter continuity + per-row ledger identity on the full grid
    stage = frames["stage_balances"].sort(["region_id", "commodity_id", "stage", "tick"])
    previous_close: dict[tuple[str | None, str, str], float] = {}
    for row in stage.iter_rows(named=True):
        key = (row["region_id"], row["commodity_id"], row["stage"])
        if row["tick"] > 0:
            expected_open = previous_close.get(key)
            if expected_open is None or abs(row["opening"] - expected_open) > tol(
                row["opening"], expected_open
            ):
                raise ResearchGateError(
                    f"checkpoint stage-balance continuity broken at tick {row['tick']} for {key}"
                )
        previous_close[key] = row["closing"]
        scale = max(
            abs(row["opening"]),
            abs(row["closing"]),
            abs(row["production"]),
            abs(row["receipts"]),
        )
        if abs(row["residual"]) > 1e-6 + 1e-9 * scale:
            raise ResearchGateError(
                f"checkpoint stage_balances stores a residual beyond tolerance at "
                f"tick {row['tick']} for {key}"
            )

    final_tick = completed - 1
    national = frames["national_accounts"].filter(pl.col("tick") == final_tick)
    closing_by_commodity = dict(
        zip(
            national["commodity_id"].to_list(),
            national["total_stock_close"].to_list(),
            strict=True,
        )
    )
    cell_commodity = np.asarray(network.cell_commodity)
    actual_by_commodity = np.bincount(
        cell_commodity,
        weights=np.asarray(state.stock_value),
        minlength=len(snapshot.commodities),
    )
    for index, commodity in enumerate(snapshot.commodities):
        stored = float(closing_by_commodity[commodity])
        actual = float(actual_by_commodity[index])
        if abs(stored - actual) > max(1e-6, tol(stored, actual)):
            raise ResearchGateError(
                f"checkpoint boundary total stock disagrees with the state for {commodity}"
            )

    budgets = frames["household_budgets"].filter(pl.col("tick") == final_tick)
    budget_cash = dict(
        zip(
            budgets["region_id"].to_list(),
            budgets["cash_close"].to_list(),
            strict=True,
        )
    )
    weight = state.household_weight
    for region_index, region in enumerate(snapshot.region_ids):
        mask = state.household_region == region_index
        state_cash = float(np.sum(weight[mask] * state.household_cash[mask]))
        if abs(float(budget_cash[region]) - state_cash) > 1e-6:
            raise ResearchGateError(
                f"checkpoint boundary household cash disagrees with the state for {region}"
            )

    financial = frames["financial_accounts"].filter(pl.col("tick") == final_tick)
    boundary_scalars = (
        ("treasury_cash", float(state.treasury_deposit)),
        ("foreign_usd_reserve", float(state.usd_reserve)),
        ("foreign_cmea_settlement", float(state.cmea_settlement_balance)),
    )
    for label, expected in boundary_scalars:
        rows = financial.filter(pl.col("account_label") == label)
        if rows.height != 1:
            raise ResearchGateError(
                f"checkpoint financial boundary row {label!r} missing at the final tick"
            )
        if abs(float(rows["closing"][0]) - expected) > 1e-9:
            raise ResearchGateError(
                f"checkpoint financial boundary {label} disagrees with the state"
            )

    org_final = frames["organization_diagnostics"].filter(pl.col("tick") == final_tick)
    if int(org_final["organization_count"].sum()) != int(state.organization_id.shape[0]):
        raise ResearchGateError(
            "checkpoint organization diagnostics count disagrees with the state axis"
        )

    chain_row = diagnostics.filter(pl.col("tick") == final_tick)
    if not chain_row.height or chain_row["digest"][0] == "":
        raise ResearchGateError("checkpoint diagnostics lack the final digest")

    diagnostic_by_tick = {int(row["tick"]): row for row in diagnostics.iter_rows(named=True)}
    for row in frames["events"].iter_rows(named=True):
        if row["event_type"] != MATERIAL_TICK_EVENT:
            raise ResearchGateError(
                f"checkpoint event type {row['event_type']!r} is not {MATERIAL_TICK_EVENT!r}"
            )
        try:
            details = json.loads(row["details_json"])
        except (TypeError, ValueError) as exc:
            raise ResearchGateError(f"checkpoint event details are not valid JSON: {exc}") from exc
        if not isinstance(details, dict):
            raise ResearchGateError("checkpoint event details must be a JSON object")
        diagnostic = diagnostic_by_tick.get(int(row["tick"]))
        if diagnostic is None:
            raise ResearchGateError(
                f"checkpoint event at tick {row['tick']} has no diagnostics row"
            )
        if details.get("digest") != diagnostic["digest"]:
            raise ResearchGateError(
                f"checkpoint event digest disagrees with diagnostics at tick {row['tick']}"
            )
        for field in (
            "max_material_abs_residual",
            "max_material_tolerance_ratio",
            "max_finance_abs_residual",
            "max_finance_tolerance_ratio",
            "bottleneck_demand_count",
            "financial_blocked_total",
        ):
            if (
                field not in details
                or not isinstance(details[field], (int, float))
                or (isinstance(details[field], bool))
            ):
                raise ResearchGateError(
                    f"checkpoint event {field} is not a JSON number at tick {row['tick']}"
                )
            if abs(float(details[field]) - float(diagnostic[field])) > 1e-9:
                raise ResearchGateError(
                    f"checkpoint event {field} disagrees with diagnostics at tick {row['tick']}"
                )


def load_material_checkpoint(
    directory: Path,
    spec: ScenarioSpec,
    contract: ResearchContract,
    network: Any,
    *,
    extra_rng_modules: dict[str, int] | None = None,
) -> tuple[MaterialState, MaterialHistory, RngRegistry, dict[str, object]]:
    """Strictly verify and restore a checkpoint; no output side effects.

    ``extra_rng_modules`` declares the additional deterministic draw counts a
    P04-enabled run consumes (e.g. ``{"p04_observation.measurement": L*F}``), so
    the restored PCG64 state is checked against the full profile.
    """
    from hsm_lab.storage.fork import parse_parent_scenario

    metadata = _load_metadata(directory)
    _gate_versions(metadata)
    _verify_payload_hashes(directory, metadata)
    receivables, receivable_event_ids = _parse_receivable_payload(directory)

    snapshot = parse_parent_scenario(metadata)
    for field in (
        "scenario_id",
        "kind",
        "start",
        "region_ids",
        "commodities",
        "stochastic",
        "material_parameters",
        "material_initial",
        "organization_recipe",
        "technologies",
        "routes",
        "forcing_pack",
        "forcing_bindings",
    ):
        if getattr(snapshot, field) != getattr(spec, field):
            raise ResearchGateError(
                f"checkpoint scenario {field} differs from the current template; "
                "forking a checkpoint into a modified scenario is refused"
            )
    boundary_ticks = metadata.get("completed_ticks")
    if isinstance(boundary_ticks, bool) or not isinstance(boundary_ticks, int):
        raise ResearchGateError("checkpoint metadata lacks an integer completed_ticks")
    if boundary_ticks <= 0:
        raise ResearchGateError(
            "checkpoint boundary must be a positive completed-ticks count; "
            "a zero-tick replay is refused"
        )
    expected_last = str(snapshot.start.advance(boundary_ticks - 1))
    if metadata.get("last_completed_quarter") != expected_last:
        raise ResearchGateError(
            f"checkpoint last_completed_quarter "
            f"{metadata.get('last_completed_quarter')!r} disagrees with the "
            f"boundary {expected_last!r}"
        )
    expected_next = str(snapshot.start.advance(boundary_ticks))
    if metadata.get("next_quarter") != expected_next:
        raise ResearchGateError(
            f"checkpoint next_quarter {metadata.get('next_quarter')!r} disagrees "
            f"with the boundary {expected_next!r}"
        )
    if metadata.get("region_ids") != list(snapshot.region_ids):
        raise ResearchGateError("checkpoint region axes disagree with the scenario")
    if metadata.get("commodity_ids") != list(snapshot.commodities):
        raise ResearchGateError("checkpoint commodity axes disagree with the scenario")
    if metadata.get("baseline_hash") != contract.expected_baseline_sha256:
        raise ResearchGateError("checkpoint baseline hash differs from the pinned one")

    # --- network static hash: stored payload vs the passed compiled network
    try:
        network_payload = np.load(directory / "network.npz", allow_pickle=False)
    except Exception as exc:  # noqa: BLE001 - any load failure is a gate failure
        raise ResearchGateError(f"unreadable checkpoint network: {exc}") from exc
    stored_fields = set(network_payload.files) - {"schema_version"}
    _spec_drift(
        stored_fields,
        {name for name, _d in _NETWORK_ARRAY_SPEC},
        "network payload",
    )
    marker = str(np.asarray(network_payload["schema_version"]).item())
    if marker != getattr(network, "schema_version", None):
        raise ResearchGateError("checkpoint network schema marker mismatch")
    stored_hash = metadata.get("network_static_hash")
    recomputed_stored = canonical_array_hash(
        {name: np.asarray(network_payload[name]) for name in stored_fields}
    )

    if stored_hash is not None and stored_hash != recomputed_stored:
        raise ResearchGateError("checkpoint network payload hash mismatch")
    passed_hash = network_static_hash(network)
    if stored_hash is None or passed_hash != stored_hash:
        raise ResearchGateError(
            "checkpoint network static hash mismatch: the compiled network "
            "differs from the one the checkpoint was written with"
        )

    # --- state payload
    try:
        payload = np.load(directory / "state.npz", allow_pickle=False)
    except Exception as exc:  # noqa: BLE001 - any load failure is a gate failure
        raise ResearchGateError(f"unreadable checkpoint state: {exc}") from exc
    completed = int(np.asarray(payload["completed_ticks"]).item())
    if completed != boundary_ticks:
        raise ResearchGateError("checkpoint completed_ticks inconsistent")
    state, arrays = _state_from_payload(
        payload,
        completed,
        catalog=network.household_catalog,
        receivables=receivables,
        receivable_event_ids=receivable_event_ids,
    )
    _validate_state(state, arrays, snapshot, network)

    # --- parameter/initial-recipe identity (kernel module owns the vectors)
    from hsm_lab.engine.material import (
        material_recipe_hash,
    )
    from hsm_lab.provenance.manifest import compute_parameter_hash

    if metadata.get("parameter_hash") is not None and metadata.get(
        "parameter_hash"
    ) != compute_parameter_hash(_parameter_vector_with_politics(snapshot)):
        raise ResearchGateError("checkpoint parameter hash mismatch")
    if metadata.get("initial_recipe_hash") is not None and metadata.get(
        "initial_recipe_hash"
    ) != material_recipe_hash(snapshot):
        raise ResearchGateError("checkpoint initial recipe hash mismatch")

    # --- history payload
    import polars as pl

    frames: dict[str, Any] = {}
    for name in TABLES:
        path = directory / f"{name}.parquet"
        if not path.is_file():
            raise ResearchGateError(f"checkpoint history table {name} is missing")
        frames[name] = pl.read_parquet(path)
    _validate_history_frames(frames, state, snapshot, completed)

    chain = metadata.get("digest_chain")
    if not isinstance(chain, str) or not chain:
        raise ResearchGateError("checkpoint lacks a digest chain")
    diagnostics = frames["tick_diagnostics"]
    if diagnostics.height and diagnostics["digest"][-1] != chain:
        raise ResearchGateError("checkpoint digest chain disagrees with last tick row")
    _validate_history_consistency(frames, state, snapshot, completed, network)

    history = MaterialHistory(
        aggregate_rows=frames["aggregates"].to_dicts(),
        stage_rows=frames["stage_balances"].to_dicts(),
        national_rows=frames["national_accounts"].to_dicts(),
        budget_rows=frames["household_budgets"].to_dicts(),
        organization_rows=frames["organization_diagnostics"].to_dicts(),
        financial_rows=frames["financial_accounts"].to_dicts(),
        department_rows=frames["departments"].to_dicts(),
        diagnostic_rows=diagnostics.to_dicts(),
        event_rows=frames["events"].to_dicts(),
        political_quarter_rows=frames[POLITICAL_QUARTERS].to_dicts(),
        opposition_rows=frames[OPPOSITION_REGIONS].to_dicts(),
        information_rows=frames[INFORMATION_QUARTERS].to_dicts(),
        policy_decision_rows=frames[POLICY_DECISIONS].to_dicts(),
        political_event_rows=frames[POLITICAL_EVENTS].to_dicts(),
        digest_chain=chain,
    )
    rng = RngRegistry.from_snapshot(cast("dict[str, object]", metadata.get("rng_snapshot")))
    if rng.seed != snapshot.seed:
        raise ResearchGateError("checkpoint RNG seed disagrees with the snapshot scenario")
    expected_rng = RngRegistry(snapshot.seed)
    if snapshot.stochastic:
        from hsm_lab.engine.households import _ATTR_DRAWS, ATTRIBUTE_MODULE

        expected_rng.uniform(ATTRIBUTE_MODULE, snapshot.households * _ATTR_DRAWS)
        for module, count in (extra_rng_modules or {}).items():
            if count:
                expected_rng.uniform(module, int(count))
    if rng.snapshot() != expected_rng.snapshot():
        raise ResearchGateError(
            "checkpoint RNG snapshot does not match the material initialization "
            "profile (module set, draw counts or PCG64 position)"
        )
    declared_political = metadata.get("political_arrays")
    if declared_political:
        try:
            payload_political = np.load(directory / "political.npz", allow_pickle=False)
        except Exception as exc:  # noqa: BLE001 - any load failure is a gate failure
            raise ResearchGateError(f"unreadable checkpoint political payload: {exc}") from exc
        if sorted(payload_political.files) != sorted(declared_political):
            raise ResearchGateError(
                "checkpoint political payload field set disagrees with its declaration"
            )
        metadata["political"] = {
            name: np.asarray(payload_political[name]) for name in declared_political
        }
    return state, history, rng, metadata


def _parameter_vector_with_politics(snapshot: ScenarioSpec) -> dict[str, float]:
    """Material parameter vector merged with the resolved P04 political parameters."""
    from hsm_lab.engine.material import material_parameter_vector

    vector = material_parameter_vector(snapshot)
    if snapshot.politics is not None:
        from hsm_lab.contract.politics import PoliticalRunSpec, resolve_political_parameters
        from hsm_lab.engine.policy import default_initial_policy

        politics = (
            snapshot.politics
            if isinstance(snapshot.politics, PoliticalRunSpec)
            else PoliticalRunSpec.model_validate(snapshot.politics)
        )
        resolved = resolve_political_parameters(
            politics.parameters, default_initial_policy(snapshot)
        )
        vector = {**vector, **resolved.flatten()}
    return vector


def next_quarter_of(spec: ScenarioSpec, completed_ticks: int) -> str:
    return str(spec.start.advance(completed_ticks))
