"""H5A-A1 / M02 enterprise-chain experiment runner.

One entry point, ``run_m02_study``, drives the *existing* material chain
(``build_material_initial_conditions`` -> ``build_material_network`` ->
``initialize_material`` -> ``load_material_forcing`` -> ``tick_material``)
over the read-only ``intermediate8`` branch.  It is not a second engine: it
adds no cash, no goods, no settlement rule, no approval cap and no policy
pathway.  Every quarter is advanced by exactly one ``tick_material`` call
under ``controls=effective.controls`` and is gated by
``check_material_invariants`` against its own opening snapshot.

Rules this module enforces mechanically rather than by convention:

* Rejection happens before the output directory exists and before any model is
  initialised: unknown/empty/duplicate seed or arm, a non-preregistered
  window, a drifted source or card hash, an existing output directory, an
  out-of-bounds policy coordinate.
* Every policy coordinate goes through ``default_initial_policy(...).patch``
  and Pydantic validation; ``model_copy`` is never used to write one.
* ``investment_approvals`` is never passed and ``central_target`` is ``None``,
  so the engine's request is the *unconstrained* request.  That quantity is
  additionally recomputed here from the opening state and the effective
  parameters and compared tick by tick.
* Shortage is grouped by commodity + stage + purpose.  A zero denominator is
  ``value=null, status="ZERO_DENOMINATOR"``; a declared axis the run never
  routed is ``BLOCKED_METRIC``.  Neither is zero-filled and neither is dropped.
* Per-arm digests separate the *scientific* content (inputs, controls,
  effective parameters, numeric trace, final state) from the *comparison*
  content (state, real flows, ledger only).  Arm labels, paths, wall clock,
  RSS, command lines and HEAD enter neither, so a placebo arm running the
  identical treatment reproduces the identical comparison digest.
* Every journal leg is checked against the account directory built by
  ``engine.finance.build_account_directory``; an account id the directory does
  not own halts the run instead of being exported as a real counterparty.
* The preregistered study passes **no** credit approval cap, so the engine
  keeps its legacy Treasury-credit journal path and every per-arm comparison,
  final-state and journal digest is reproducible against an earlier run.
  ``finance_probe=True`` is an explicitly opt-in diagnostic that switches to
  the engine's H3B bank-lender journal path purely to read the pre-scaling
  cash and procurement intermediates; it is never used for a study run.

The study is explicitly synthetic.  It exercises the real Intermediate-8
enterprise chain; it cannot promote any historical status.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import json
import math
import platform
import resource
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel
from scipy.sparse import spmatrix

from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.contract.material import ORGANIZATION_TYPE_ORDER, PURPOSE_CODES, OrganizationType
from hsm_lab.contract.politics import ExternalWorldSlice
from hsm_lab.contract.schemas import ScenarioSpec
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.accounting import check_material_invariants
from hsm_lab.engine.finance import build_account_directory
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.material import (
    canonical_material_bytes,
    load_material_forcing,
    tick_material,
)
from hsm_lab.engine.network import build_material_network
from hsm_lab.engine.policy import compile_effective_policy, default_initial_policy
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import capture_material_stocks, initialize_material
from hsm_lab.provenance.manifest import canonical_json

__all__ = [
    "PREREGISTERED_ARMS",
    "PREREGISTERED_HOUSEHOLDS",
    "PREREGISTERED_SEEDS",
    "PREREGISTERED_SPEC_SCHEMA",
    "PREREGISTERED_TICKS",
    "PREREGISTERED_WINDOW",
    "ArmDesign",
    "SpecRejection",
    "axis_gap_rows",
    "baseline_collapse_reason",
    "build_account_directory",
    "run_m02_study",
    "unconstrained_investment_request",
]

# ---------------------------------------------------------------------------
# Frozen design constants: the preregistration, not defaults.
# ---------------------------------------------------------------------------

PREREGISTERED_SPEC_SCHEMA = "hist_vnext_h5a_a1_m02_v1"
PREREGISTERED_PHASE_ID = "H5A-A1"
PREREGISTERED_MECHANISM_ID = "M2"
PREREGISTERED_STUDY_ID = "M02"
PREREGISTERED_HOUSEHOLDS = 1000
PREREGISTERED_TICKS = 4
PREREGISTERED_WINDOW = ("1957Q1", "1957Q2", "1957Q3", "1957Q4")
PREREGISTERED_SEEDS = (1729, 1730, 1731)
PREREGISTERED_ARMS = (
    "soft_low_base",
    "hard_low_base",
    "soft_high_base",
    "hard_high_base",
    "soft_low_reduced",
    "hard_low_reduced",
    "soft_high_reduced",
    "hard_high_reduced",
    "credit_cut_high_base",
    "rescue_cut_high_base",
    "credit_cut_high_reduced",
    "rescue_cut_high_reduced",
    "placebo_soft_low_base",
)
PREREGISTERED_REGIMES = ("base", "reduced")
PREREGISTERED_LEVELS = ("low", "high")
DEFAULT_SPEC_PATH = Path("studies/HIST_VNEXT/M02/spec.json")

_PURPOSE_BY_NAME = {name: code for name, code in PURPOSE_CODES.items()}
_NAME_BY_PURPOSE = {code: name for name, code in PURPOSE_CODES.items()}
_STAGE_BY_CODE = {0: "standard", 1: "raw", 2: "ready"}
_INVESTMENT_PURPOSE = _PURPOSE_BY_NAME["investment"]
_BANK_TYPE_CODE = ORGANIZATION_TYPE_ORDER.index(OrganizationType.BANK)

# Large enough that no request can reach it, small enough that downstream
# arithmetic on the cap vector cannot overflow.
_NON_BINDING_CREDIT_CAP = 1e15

# Relative equality used only for "did this quantity move at all" first-stage
# questions.  Conservation always uses the engine's own <= 1 tolerance ratios.
_FIRST_STAGE_RTOL = 1e-9
_FIRST_STAGE_ATOL = 1e-12


class SpecRejection(ValueError):
    """A study design was refused before any output or model was created."""


class RunHalted(RuntimeError):
    """A conservation failure or a baseline collapse stopped the run."""


# ---------------------------------------------------------------------------
# JSON and digest helpers
# ---------------------------------------------------------------------------


def _clean(value: Any) -> Any:
    """Strict-JSON-safe copy: no NaN, no numpy, no tuples."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, np.ndarray):
        return [_clean(item) for item in value.tolist()]
    if isinstance(value, BaseModel):
        return _clean(value.model_dump())
    if isinstance(value, Mapping):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return [_clean(item) for item in sorted(value, key=repr)]
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    raise TypeError(f"value of type {type(value)!r} is not JSON-serialisable")


def _canonical(value: Any) -> bytes:
    return canonical_json(_clean(value))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _digest_form(value: Any) -> Any:
    """Exact structural digest form for arrays, sparse matrices and containers.

    A silent ``repr`` fallback would embed memory addresses and silently
    destroy reproducibility, so an unknown type raises instead.
    """
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return number if math.isfinite(number) else "NaN"
    if isinstance(value, np.ndarray):
        contiguous = np.ascontiguousarray(value)
        return {
            "ndarray": {
                "dtype": str(contiguous.dtype),
                "shape": list(contiguous.shape),
                "sha256": _sha256(contiguous.tobytes()),
            }
        }
    if isinstance(value, spmatrix):
        return {
            "sparse": {
                "format": value.format,
                "shape": list(value.shape),
                "indptr": _sha256(np.ascontiguousarray(value.indptr).tobytes()),
                "indices": _sha256(np.ascontiguousarray(value.indices).tobytes()),
                "data": _sha256(np.ascontiguousarray(value.data).tobytes()),
            }
        }
    if isinstance(value, BaseModel):
        return {
            "model": value.__class__.__name__,
            "fields": _digest_form(value.model_dump()),
        }
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            "dataclass": type(value).__name__,
            "fields": _digest_form(
                {field.name: getattr(value, field.name) for field in dataclasses.fields(value)}
            ),
        }
    if isinstance(value, Mapping):
        return {
            "map": [
                [_digest_form(key), _digest_form(item)]
                for key, item in sorted(value.items(), key=lambda pair: repr(pair[0]))
            ]
        }
    if isinstance(value, tuple):
        return {"tuple": [_digest_form(item) for item in value]}
    if isinstance(value, list):
        return [_digest_form(item) for item in value]
    raise TypeError(f"cannot build a reproducible digest for {type(value)!r}")


def _digest(value: Any) -> str:
    return _sha256(_canonical(_digest_form(value)))


# ---------------------------------------------------------------------------
# Spec loading and pre-flight validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArmDesign:
    """One preregistered arm resolved to concrete policy coordinates."""

    name: str
    budget: str
    intensity: str
    regime: str
    mediator: str | None
    role: str
    budget_hardness: float
    credit_fraction: float
    investment_intensity: float

    def policy_patch(self) -> dict[str, float]:
        return {
            "budget_hardness": self.budget_hardness,
            "credit_fraction": self.credit_fraction,
            "investment_intensity": self.investment_intensity,
        }


@dataclass(frozen=True)
class StudySpec:
    raw: dict[str, Any]
    path: Path
    digest: str
    arms: tuple[ArmDesign, ...]
    scenario_id: str
    scenario_sha256: str
    card_sha256: str
    seeds: tuple[int, ...]
    households: int
    ticks: int
    window: tuple[str, ...]

    @property
    def arm_names(self) -> tuple[str, ...]:
        return tuple(arm.name for arm in self.arms)

    def placebo_targets(self) -> tuple[tuple[str, str], ...]:
        rows = self.raw["arms"]
        pairs = []
        for index, arm in enumerate(self.arms):
            if arm.role != "placebo_negative_control":
                continue
            target = str(rows[index].get("placebo_of", ""))
            pairs.append((arm.name, target))
        return tuple(pairs)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SpecRejection(message)


def _load_json(path: Path, label: str) -> dict[str, Any]:
    _require(path.is_file(), f"{label} is not a file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SpecRejection(f"{label} is not valid JSON: {path}: {exc}") from exc
    _require(isinstance(payload, dict), f"{label} must be a JSON object: {path}")
    return payload


def _resolve_under_root(root: Path, relative: str, label: str) -> Path:
    candidate = Path(relative)
    _require(
        bool(relative) and not candidate.is_absolute(),
        f"{label} must be a repo-relative path",
    )
    resolved = (root / candidate).resolve()
    _require(
        resolved.is_relative_to(root),
        f"{label} escapes the repository root: {relative}",
    )
    return resolved


def _select_subset(
    requested: Sequence[Any] | None, registered: Sequence[Any], label: str, kind: type
) -> tuple[Any, ...]:
    """Validate a caller-supplied subset of a preregistered sequence."""
    values = tuple(registered if requested is None else requested)
    _require(len(values) > 0, f"{label} must not be empty")
    _require(
        all(type(value) is kind for value in values),
        f"{label} must be a sequence of {kind.__name__} values",
    )
    _require(len(set(values)) == len(values), f"{label} contains duplicates: {list(values)}")
    unknown = [value for value in values if value not in set(registered)]
    _require(not unknown, f"{label} are not preregistered in the study spec: {unknown}")
    return values


def load_study_spec(root: Path, spec_path: Path) -> StudySpec:
    """Load and fully validate the study spec; raises ``SpecRejection``."""
    root = root.resolve()
    payload = _load_json(spec_path, "study spec")
    _require(
        payload.get("schema_version") == PREREGISTERED_SPEC_SCHEMA,
        f"spec schema_version must be {PREREGISTERED_SPEC_SCHEMA!r}",
    )
    for key, expected in (
        ("phase_id", PREREGISTERED_PHASE_ID),
        ("mechanism_id", PREREGISTERED_MECHANISM_ID),
        ("study_id", PREREGISTERED_STUDY_ID),
    ):
        _require(payload.get(key) == expected, f"spec {key} must be {expected!r}")

    legacy = payload.get("legacy_card")
    _require(isinstance(legacy, dict), "spec legacy_card must be an object")
    card_path = _resolve_under_root(root, str(legacy.get("path", "")), "legacy_card.path")
    card_sha256 = str(legacy.get("sha256", ""))
    actual_card = _sha256_file(card_path)
    _require(
        actual_card == card_sha256,
        f"legacy card hash drifted: declared {card_sha256}, actual {actual_card}",
    )
    card = json.loads(card_path.read_text(encoding="utf-8"))
    _require(
        legacy.get("hypothesis") == card.get("hypothesis"),
        "spec must reproduce the legacy card hypothesis verbatim",
    )
    _require(
        legacy.get("falsification_criterion") == card.get("falsification_criterion"),
        "spec must reproduce the legacy card falsification criterion verbatim",
    )
    _require(
        list(legacy.get("metrics", [])) == list(card.get("metrics", [])),
        "spec must reproduce the legacy card metrics verbatim",
    )

    source = payload.get("source")
    _require(isinstance(source, dict), "spec source must be an object")
    scenario_id = str(source.get("scenario_id", ""))
    scenario_path = _resolve_under_root(root, str(source.get("path", "")), "source.path")
    scenario_sha256 = str(source.get("sha256", ""))
    actual_scenario = _sha256_file(scenario_path)
    _require(
        actual_scenario == scenario_sha256,
        f"source scenario hash drifted: declared {scenario_sha256}, actual {actual_scenario}",
    )

    run = payload.get("run")
    _require(isinstance(run, dict), "spec run must be an object")
    _require(
        int(run.get("households", 0)) == PREREGISTERED_HOUSEHOLDS,
        f"spec households must be the preregistered {PREREGISTERED_HOUSEHOLDS}",
    )
    _require(
        int(run.get("ticks", 0)) == PREREGISTERED_TICKS,
        f"spec ticks must be the preregistered {PREREGISTERED_TICKS}",
    )
    window = run.get("window")
    _require(isinstance(window, dict), "spec run.window must be an object")
    quarters = tuple(str(quarter) for quarter in window.get("quarters", ()))
    _require(
        quarters == PREREGISTERED_WINDOW,
        f"spec window {list(quarters)} is not the preregistered window "
        f"{list(PREREGISTERED_WINDOW)}",
    )
    _require(
        str(window.get("start")) == PREREGISTERED_WINDOW[0]
        and str(window.get("end")) == PREREGISTERED_WINDOW[-1],
        "spec window start/end do not match the preregistered window",
    )
    _require(
        int(run.get("warmup_quarters", -1)) == 0,
        "this study preregisters no warmup quarters",
    )
    _require(
        run.get("auto_extension") is False,
        "this study preregisters no automatic window extension",
    )

    seeds_raw = run.get("seeds")
    _require(isinstance(seeds_raw, list) and seeds_raw, "spec run.seeds must be a non-empty list")
    _require(
        all(type(value) is int for value in seeds_raw),
        "spec run.seeds must be integers",
    )
    seeds = tuple(int(value) for value in seeds_raw)
    _require(len(set(seeds)) == len(seeds), "spec run.seeds contains duplicates")

    policy = payload.get("policy")
    _require(isinstance(policy, dict), "spec policy must be an object")
    budget_block = policy.get("budget")
    _require(isinstance(budget_block, dict), "spec policy.budget must be an object")
    intensity_block = policy.get("investment_intensity")
    _require(
        isinstance(intensity_block, dict),
        "spec policy.investment_intensity must be an object",
    )
    fixed = policy.get("fixed")
    _require(isinstance(fixed, dict), "spec policy.fixed must be an object")
    _require(fixed.get("central_target") is None, "central_target must stay null in this study")
    _require(
        fixed.get("investment_approvals") is None,
        "investment_approvals must stay null so the engine request stays unconstrained",
    )

    arm_rows = payload.get("arms")
    _require(isinstance(arm_rows, list) and arm_rows, "spec arms must be a non-empty list")
    _require(
        all(isinstance(row, Mapping) and "name" in row for row in arm_rows),
        "every spec arm needs a name",
    )
    declared_names = tuple(str(row["name"]) for row in arm_rows)
    _require(
        declared_names == PREREGISTERED_ARMS,
        "spec arms must be exactly the preregistered 13 arms in order: "
        f"{list(PREREGISTERED_ARMS)}",
    )

    arms: list[ArmDesign] = []
    for row in arm_rows:
        name = str(row["name"])
        budget_key = str(row.get("budget", ""))
        intensity_key = str(row.get("intensity", ""))
        regime = str(row.get("regime", ""))
        _require(
            budget_key in budget_block,
            f"arm {name!r} names an undeclared budget coordinate {budget_key!r}",
        )
        _require(
            intensity_key in intensity_block,
            f"arm {name!r} names an undeclared investment level {intensity_key!r}",
        )
        _require(
            regime in PREREGISTERED_REGIMES,
            f"arm {name!r} names an undeclared demand regime {regime!r}",
        )
        coordinates = budget_block[budget_key]
        _require(
            isinstance(coordinates, dict)
            and {"budget_hardness", "credit_fraction"} <= set(coordinates),
            f"budget coordinate {budget_key!r} must declare budget_hardness and credit_fraction",
        )
        arms.append(
            ArmDesign(
                name=name,
                budget=budget_key,
                intensity=intensity_key,
                regime=regime,
                mediator=None if row.get("mediator") is None else str(row["mediator"]),
                role=str(row.get("role", "main")),
                budget_hardness=float(coordinates["budget_hardness"]),
                credit_fraction=float(coordinates["credit_fraction"]),
                investment_intensity=float(intensity_block[intensity_key]),
            )
        )

    regimes = payload.get("demand_regimes")
    _require(isinstance(regimes, dict), "spec demand_regimes must be an object")
    _require(
        set(regimes) >= set(PREREGISTERED_REGIMES),
        f"spec must declare both demand regimes: {list(PREREGISTERED_REGIMES)}",
    )

    return StudySpec(
        raw=payload,
        path=spec_path,
        digest=_sha256(spec_path.read_bytes()),
        arms=tuple(arms),
        scenario_id=scenario_id,
        scenario_sha256=scenario_sha256,
        card_sha256=card_sha256,
        seeds=seeds,
        households=PREREGISTERED_HOUSEHOLDS,
        ticks=PREREGISTERED_TICKS,
        window=quarters,
    )


def resolve_arm_policies(spec: StudySpec, root: Path) -> dict[str, dict[str, float]]:
    """Compile every arm's policy vector, refusing out-of-bounds coordinates.

    This reads the *configuration* only: no initial conditions, no network, no
    state.  An out-of-bounds coordinate is refused here, which is why the
    runner can claim it rejected a study before initialising any model.
    """
    scenario = load_scenario(root, spec.scenario_id)
    resolved: dict[str, dict[str, float]] = {}
    for arm in spec.arms:
        try:
            policy = default_initial_policy(scenario).patch(arm.policy_patch())
        except Exception as exc:
            raise SpecRejection(
                f"arm {arm.name!r} declares an invalid policy coordinate "
                f"{arm.policy_patch()}: {exc}"
            ) from exc
        resolved[arm.name] = {name: float(value) for name, value in policy.model_dump().items()}
    return resolved


# ---------------------------------------------------------------------------
# Streaming evidence writers
# ---------------------------------------------------------------------------


class _JsonlStream:
    """One JSON object per row, flushed on every write."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle = path.open("w", encoding="utf-8")
        self.rows = 0

    def write(self, record: Mapping[str, Any]) -> None:
        self._handle.write(_canonical(record).decode("utf-8") + "\n")
        self._handle.flush()
        self.rows += 1

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.flush()
            self._handle.close()


class _ParquetStream:
    """Append-only PyArrow ParquetWriter: one row group per flushed tick."""

    def __init__(self, path: Path, schema: pa.Schema) -> None:
        self.path = path
        self.rows = 0
        self._schema = schema
        self._writer: pq.ParquetWriter | None = None

    def write(self, columns: Mapping[str, Sequence[Any]]) -> None:
        table = pa.Table.from_pydict(
            {field.name: list(columns[field.name]) for field in self._schema},
            schema=self._schema,
        )
        if self._writer is None:
            self._writer = pq.ParquetWriter(self.path, self._schema)
        self._writer.write_table(table)
        self.rows += table.num_rows

    def close(self) -> None:
        if self._writer is None:
            pq.write_table(
                pa.Table.from_pydict(
                    {field.name: [] for field in self._schema}, schema=self._schema
                ),
                self.path,
            )
            return
        self._writer.close()


JOURNAL_SCHEMA = pa.schema(
    [
        ("seed", pa.int32()),
        ("arm", pa.string()),
        ("tick", pa.int32()),
        ("quarter", pa.string()),
        ("kind", pa.string()),
        ("debit", pa.int32()),
        ("credit", pa.int32()),
        ("currency", pa.string()),
        ("amount", pa.float64()),
        ("org", pa.int32()),
        ("leg", pa.int32()),
        ("event_id", pa.string()),
    ]
)

ORGANIZATION_SCHEMA = pa.schema(
    [
        ("seed", pa.int32()),
        ("arm", pa.string()),
        ("tick", pa.int32()),
        ("quarter", pa.string()),
        ("org", pa.int32()),
        ("investment_request_unconstrained", pa.float64()),
        ("investment_requested_flows", pa.float64()),
        ("investment_approved", pa.float64()),
        ("investment_installed_capacity", pa.float64()),
        ("credit_requested", pa.float64()),
        ("credit_approved", pa.float64()),
        ("credit_drawn", pa.float64()),
        ("bailout_requested", pa.float64()),
        ("bailout_granted", pa.float64()),
        ("shortage_expectation_open", pa.float64()),
        ("shortage_expectation_close", pa.float64()),
        ("bailout_expectation_open", pa.float64()),
        ("bailout_expectation_close", pa.float64()),
        ("capital_wip_open", pa.float64()),
        ("capital_wip_close", pa.float64()),
        ("construction_wip_open", pa.float64()),
        ("construction_wip_close", pa.float64()),
        ("project_approved_open", pa.float64()),
        ("project_approved_close", pa.float64()),
        ("capacity_open", pa.float64()),
        ("capacity_close", pa.float64()),
        ("activity_realized", pa.float64()),
        ("organization_purchases", pa.float64()),
        ("organization_sales_receipts", pa.float64()),
        # Pre-scaling finance intermediates.  These are the real kernel values,
        # read through ``procurement_trace``; they explain *why* an order was
        # funded and are never reconstructed in the runner.
        ("cash_available_for_goods", pa.float64()),
        ("credit_approval_caps", pa.float64()),
        ("input_order_cost", pa.float64()),
        ("old_project_cost", pa.float64()),
        ("new_investment_request_cost", pa.float64()),
        ("input_credit_earmarked", pa.float64()),
    ]
)

DEMAND_SCHEMA = pa.schema(
    [
        ("seed", pa.int32()),
        ("arm", pa.string()),
        ("tick", pa.int32()),
        ("quarter", pa.string()),
        ("commodity", pa.string()),
        ("stage", pa.string()),
        ("purpose", pa.string()),
        ("axis_status", pa.string()),
        ("demand_rows", pa.int32()),
        ("desired", pa.float64()),
        ("ordered_gross", pa.float64()),
        ("unfunded_order", pa.float64()),
        ("ordered", pa.float64()),
        ("allocated", pa.float64()),
        ("delivered", pa.float64()),
        ("used", pa.float64()),
        ("financial_delivery_blocked", pa.float64()),
        ("physical_delivery_blocked", pa.float64()),
        ("bottleneck_demand_count", pa.int32()),
    ]
)


# ---------------------------------------------------------------------------
# Commodity + stage + purpose demand axis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AxisLayout:
    """Demand rows mapped onto the full declared commodity/stage/purpose axis."""

    commodity_ids: tuple[str, ...]
    axes: tuple[tuple[str, str, str], ...]
    observed: tuple[bool, ...]
    row_axis: np.ndarray
    axis_count: int
    investment_rows: np.ndarray

    def rows(self) -> list[tuple[str, str, str, bool]]:
        return [
            (commodity, stage, purpose, observed)
            for (commodity, stage, purpose), observed in zip(self.axes, self.observed, strict=True)
        ]


def build_axis_layout(network: Any) -> AxisLayout:
    """Group every demand row by commodity + stage + route purpose.

    The axis is the full cross product of the run's commodities, cell stages
    and route purposes.  Axes the network never routes stay in the export and
    are reported ``BLOCKED_METRIC`` instead of being dropped or zero-filled.
    """
    commodity_ids = tuple(network.commodity_ids)
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    purpose = np.asarray(network.demand_purpose, dtype=np.int64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_stage = np.asarray(network.cell_stage, dtype=np.int64)

    def axis_of(cell: int, code: int) -> tuple[str, str, str]:
        stage = int(cell_stage[cell])
        return (
            commodity_ids[int(cell_commodity[cell])],
            _STAGE_BY_CODE.get(stage, f"stage{stage}"),
            _NAME_BY_PURPOSE.get(int(code), f"purpose{code}"),
        )

    stages = tuple(sorted({int(value) for value in np.unique(cell_stage)}))
    purposes = tuple(sorted({int(value) for value in np.unique(purpose)}))
    axes = tuple(
        (
            commodity_ids[commodity],
            _STAGE_BY_CODE.get(stage, f"stage{stage}"),
            _NAME_BY_PURPOSE[purpose],
        )
        for commodity in range(len(commodity_ids))
        for stage in stages
        for purpose in purposes
    )
    position = {axis: index for index, axis in enumerate(axes)}
    row_axes = np.asarray(
        [position[axis_of(cell, code)] for cell, code in zip(demand_cell, purpose, strict=True)],
        dtype=np.int64,
    )
    observed_flags = [False] * len(axes)
    for index in row_axes.tolist():
        observed_flags[index] = True
    return AxisLayout(
        commodity_ids=commodity_ids,
        axes=axes,
        observed=tuple(observed_flags),
        row_axis=row_axes,
        axis_count=len(axes),
        investment_rows=(purpose == _INVESTMENT_PURPOSE),
    )


# ---------------------------------------------------------------------------
# Kernel quantities recomputed independently of the flows record
# ---------------------------------------------------------------------------


def unconstrained_investment_request(state: Any, parameters: Any, network: Any) -> np.ndarray:
    """Recompute the engine's uncapped investment request from the opening state.

    Capacity times investment hunger, rebuilt here from the *opening* state and
    the *effective* parameters so it never inherits a cap, a rounding step or a
    flows alias.  With ``investment_approvals`` unset the engine must reproduce
    this vector exactly; the runner compares them tick by tick.
    """
    org_activity = np.asarray(state.organization_activity, dtype=np.int64)
    with_activity = org_activity >= 0
    org_count = int(with_activity.size)
    activity_org = np.asarray(network.activity_org_index, dtype=np.int64)
    input_activity = np.asarray(network.input_activity, dtype=np.int64)
    k_buyer = activity_org[input_activity]
    org_k = k_buyer >= 0
    has_k_cells = (
        np.bincount(
            np.where(org_k, k_buyer, 0), weights=org_k.astype(np.float64), minlength=org_count
        )
        > 0
    )
    hunger = (
        float(parameters.hunger_base)
        + float(parameters.hunger_bailout)
        * np.asarray(state.organization_bailout_expectation, dtype=np.float64)
        + float(parameters.hunger_shortage)
        * np.where(
            has_k_cells, np.asarray(state.organization_shortage_expectation, dtype=np.float64), 0.0
        )
        + float(getattr(parameters, "capital_depreciation_rate", 0.0))
    )
    return np.where(
        with_activity, np.asarray(state.organization_capacity, dtype=np.float64) * hunger, 0.0
    )


def _non_binding_credit_caps(state: Any) -> np.ndarray:
    """A cap vector that cannot bind, for the opt-in finance probe only.

    The kernel requires a cap vector before it will fill ``procurement_trace``.
    This is that vector: a real borrower's cap is set far above any request the
    kernel can form, and a non-borrower or bank row carries the exact zero the
    validator demands, so the trace is readable without rationing anything.
    """
    org_bank = np.asarray(state.organization_bank, dtype=np.int64)
    bank_rows = np.asarray(state.organization_type, dtype=np.int64) == _BANK_TYPE_CODE
    return np.where((org_bank >= 0) & ~bank_rows, _NON_BINDING_CREDIT_CAP, 0.0)


def reduced_demand_household_parameters(base: Any) -> Any:
    """Halve every household-good channel base, floored at its declared minimum.

    This is the preregistered ``reduced`` demand regime: a declared design
    setting, not a historical estimate, and it leaves every minimum and every
    other demand parameter untouched.
    """
    payload = base.model_dump()
    demand = payload["demand"]
    demand["base_per_equivalent_person"] = [
        max(float(minimum), 0.5 * float(base_value))
        for base_value, minimum in zip(
            demand["base_per_equivalent_person"],
            demand["minimum_per_equivalent_person"],
            strict=True,
        )
    ]
    return type(base).model_validate(payload)


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------


def _sum(value: Any) -> float:
    if value is None:
        return 0.0
    array = np.asarray(value, dtype=np.float64)
    if array.size == 0:
        return 0.0
    total = float(array.sum())
    return total if math.isfinite(total) else 0.0


def _mean(value: Any) -> float:
    array = np.asarray(value, dtype=np.float64)
    if array.size == 0:
        return 0.0
    return float(array.mean())


def _weighted(weight: np.ndarray, values: Any) -> float:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim == 1:
        return float(np.sum(np.asarray(weight, dtype=np.float64) * array))
    return float(np.sum(np.asarray(weight, dtype=np.float64)[:, None] * array))


def _stage_name(code: int) -> str:
    return _STAGE_BY_CODE.get(int(code), f"stage{int(code)}")


# ---------------------------------------------------------------------------
# Per-arm execution
# ---------------------------------------------------------------------------

_AXIS_FLOW_FIELDS = (
    "desired",
    "ordered_gross",
    "unfunded_order",
    "ordered",
    "allocated",
    "delivered",
    "used",
    "financial_delivery_blocked",
    "physical_delivery_blocked",
)


@dataclass
class _Streams:
    trace: _JsonlStream
    journal: _ParquetStream
    organizations: _ParquetStream
    demand: _ParquetStream

    def close(self) -> None:
        self.trace.close()
        self.journal.close()
        self.organizations.close()
        self.demand.close()


@dataclass
class ArmResult:
    arm: str
    seed: int
    quarters: list[str] = field(default_factory=list)
    opening_state_digest: str = ""
    comparison_digest: str = ""
    scientific_digest: str = ""
    final_state_digest: str = ""
    journal_digest: str = ""
    window_metrics: dict[str, float] = field(default_factory=dict)
    final_quarter_metrics: dict[str, Any] = field(default_factory=dict)
    axis_totals: dict[tuple[str, str, str], dict[str, float]] = field(default_factory=dict)
    axis_observed: dict[tuple[str, str, str], bool] = field(default_factory=dict)
    collapsed_chains: list[str] = field(default_factory=list)


def _trace_array(
    trace: Mapping[str, Any] | None, name: str, org_count: int
) -> list[float | None]:
    """One per-organization finance intermediate, or nulls when not measured.

    The kernel only fills ``procurement_trace`` on its H3B bank-lender path, so
    an unprobed run exports *null*, never a zero: an unmeasured intermediate and
    a measured zero are different facts.
    """
    if trace is None or name not in trace:
        return [None] * org_count
    values = np.asarray(trace[name], dtype=np.float64)
    if int(values.size) != org_count:
        raise RunHalted(
            f"finance trace {name!r} has length {values.size}, expected {org_count}"
        )
    return [float(value) for value in values]


_FINANCE_TRACE_TOTALS = (
    "credit_approval_caps",
    "cash_available_for_goods",
    "input_order_cost",
    "old_project_cost",
    "new_investment_request_cost",
    "input_credit_earmarked",
)


def _finance_trace_record(trace: Mapping[str, Any] | None) -> dict[str, Any]:
    """Per-tick finance intermediates with a per-array digest, or NOT_RUN."""
    if trace is None:
        return {
            "status": "NOT_RUN",
            "reason": (
                "the engine fills procurement_trace only on its H3B bank-lender path; "
                "the preregistered study keeps the legacy Treasury-credit journal so "
                "its comparison, final-state and journal digests stay reproducible"
            ),
            "totals": {name: None for name in _FINANCE_TRACE_TOTALS},
            "digests": {},
        }
    return {
        "status": "MEASURED",
        "totals": {name: _sum(trace[name]) for name in _FINANCE_TRACE_TOTALS},
        "digests": {name: _digest(trace[name]) for name in _FINANCE_TRACE_TOTALS},
    }


def _procurement_view(flows: Any) -> dict[str, float]:
    return {name: _sum(getattr(flows, name)) for name in _AXIS_FLOW_FIELDS}


def _household_view(
    weight: np.ndarray,
    flows: Any,
    commodity_ids: Sequence[str],
    channel_ids: Sequence[str],
) -> dict[str, dict[str, dict[str, float]]]:
    """Per-commodity and per-household-good-channel household outcomes.

    Every series carries the real household weight and stays on its own axis;
    heterogeneous physical quantities are never pooled into one welfare total.
    """
    return {
        "commodity": {
            commodity_id: {
                "desired": _weighted(weight, flows.household_desired[:, index]),
                "budget_unmet": _weighted(weight, flows.household_budget_unmet[:, index]),
                "availability_unmet": _weighted(
                    weight, flows.household_availability_unmet[:, index]
                ),
                "realized": _weighted(weight, flows.household_realized[:, index]),
            }
            for index, commodity_id in enumerate(commodity_ids)
        },
        "channel": {
            channel_id: {
                "desired": _weighted(weight, flows.household_desired_h[:, index]),
                "budget_unmet": _weighted(weight, flows.household_budget_unmet_h[:, index]),
                "availability_unmet": _weighted(
                    weight, flows.household_availability_unmet_h[:, index]
                ),
                "realized": _weighted(weight, flows.household_realized_h[:, index]),
            }
            for index, channel_id in enumerate(channel_ids)
        },
    }


def _halt(
    *,
    streams: _Streams,
    output_dir: Path,
    boundary: Any,
    state: Any,
    seed: int,
    arm: ArmDesign,
    tick: int,
    quarter: str,
    policy: Any,
    effective: Any,
    forcing: Any,
    network: Any,
    scenario: ScenarioSpec,
    reason: str,
    exception_type: str,
) -> None:
    """Restore the pre-tick boundary, persist the evidence and stop the run.

    The failed state is hashed *before* the restore so the two are distinct
    facts: what the kernel had actually written, and the boundary the run is
    returned to.  Every mutable field is copied back field by field, and the
    restored state is hashed again and asserted equal to the boundary, so a
    partial restore can never pass silently.
    """
    state_at_failure_digest = _sha256(canonical_material_bytes(state))
    boundary_digest = _sha256(canonical_material_bytes(boundary))
    failed_completed_ticks = int(state.completed_ticks)
    for field_name in state.__dataclass_fields__:
        setattr(state, field_name, copy.deepcopy(getattr(boundary, field_name)))
    restored_digest = _sha256(canonical_material_bytes(state))
    if restored_digest != boundary_digest:
        raise RunHalted(
            f"failure boundary restore did not reproduce the pre-tick state at tick "
            f"{tick}: restored {restored_digest}, boundary {boundary_digest}"
        )
    material_parameters = effective.material_parameters
    evidence = {
        "status": "HALTED",
        "reason": reason,
        "exception_type": exception_type,
        "seed": int(seed),
        "arm": arm.name,
        "tick": int(tick),
        "quarter": quarter,
        "completed_ticks": failed_completed_ticks,
        "state_at_failure_sha256": state_at_failure_digest,
        "boundary_pre_tick_state_sha256": boundary_digest,
        "restored_pre_tick_state_sha256": restored_digest,
        "restored_equals_boundary": True,
        "forcing_quarters": [str(value) for value in forcing.quarters],
        "effective_material_parameters": {
            "hunger_base": float(material_parameters.hunger_base),
            "credit_envelope_fraction": float(material_parameters.credit_envelope_fraction),
            "bailout_envelope_fraction": float(material_parameters.bailout_envelope_fraction),
        },
        "policy_vector": _clean(policy.model_dump()),
        "effective_material_parameters_sha256": _digest(effective.material_parameters),
        "effective_household_parameters_sha256": _digest(effective.household_parameters),
        "scenario_id": scenario.scenario_id,
        "network_sha256": _digest(network),
        "forcing_sha256": _digest(forcing),
        "artifact_rows": {
            "trace": streams.trace.rows,
            "journal": streams.journal.rows,
            "organization": streams.organizations.rows,
            "demand": streams.demand.rows,
        },
    }
    (output_dir / "failure.json").write_text(
        _canonical(evidence).decode("utf-8") + "\n", encoding="utf-8"
    )
    streams.close()
    raise RunHalted(reason)


# A main baseline that never delivered one of these three goods produced no
# capital/construction/consumer chain at all, whatever its other totals say.
_COLLAPSE_COMMODITIES = ("capital_goods", "construction", "consumer_goods")


def _collapsed_chains(window: Mapping[str, float]) -> list[str]:
    """Key productive chains a main baseline left at exactly zero all window.

    Installed capacity and realized activity are not enough: a baseline can
    keep producing while never delivering a capital, construction or consumer
    good, and it can satisfy household demand on paper while realising none of
    it.  Both are silent non-results, so both collapse the arm.
    """
    chains = {
        "installed_capacity": "investment_installed_capacity_total",
        "activity_realized": "activity_realized_total",
        "organization_realized": "organization_realized_total",
    }
    collapsed = [name for name, key in chains.items() if float(window.get(key, 0.0)) == 0.0]
    collapsed.extend(
        f"{commodity}_delivered"
        for commodity in _COLLAPSE_COMMODITIES
        if float(window.get(f"commodity_delivered:{commodity}", 0.0)) == 0.0
    )
    desired = float(window.get("household_desired_commodity:consumer_goods", 0.0))
    realized = float(window.get("household_realized_commodity:consumer_goods", 0.0))
    if desired > 0.0 and realized == 0.0:
        collapsed.append("household_consumer_goods_desired_but_unrealized")
    return collapsed


def baseline_collapse_reason(result: ArmResult, arm: ArmDesign) -> str | None:
    """Refuse to read a collapsed main baseline as a mechanism counter-example.

    A baseline whose key capital/construction/consumer chain produced nothing
    at all over the whole window carries no information about the mechanism, so
    it must halt the study rather than be compared against.
    """
    if arm.role != "main_baseline":
        return None
    if not result.collapsed_chains:
        return None
    return (
        "BLOCKED_BASELINE_COLLAPSE: the main baseline "
        f"{arm.name!r} (seed {result.seed}) left {result.collapsed_chains} at exactly "
        "zero for the whole window; no mechanism comparison may read it as a "
        "historical counter-example"
    )


def _run_arm(
    *,
    scenario: ScenarioSpec,
    opening: Any,
    forcing: Any,
    network: Any,
    layout: AxisLayout,
    arm: ArmDesign,
    seed: int,
    policy_dump: Mapping[str, float],
    household_base: Any,
    streams: _Streams,
    output_dir: Path,
    opening_digest: str,
    forcing_digest: str,
    network_digest: str,
    spec_digest: str,
    card_sha256: str,
    scenario_sha256: str,
    account_ids: frozenset[int],
    finance_probe: bool = False,
) -> ArmResult:
    """Run one arm over the preregistered window under real conservation gates.

    ``account_ids`` is the account directory's id set; every journal leg is
    checked against it.  ``finance_probe`` is an explicitly opt-in diagnostic
    that reads the pre-scaling cash intermediates through the engine's own
    ``procurement_trace``; it switches the kernel to the H3B bank-lender journal
    path and is therefore never used for a preregistered study run, whose
    comparison, final-state and journal digests must stay reproducible.
    """
    state = copy.deepcopy(opening)
    policy = default_initial_policy(scenario).patch(arm.policy_patch())
    result = ArmResult(arm=arm.name, seed=int(seed), opening_state_digest=opening_digest)
    weight = np.asarray(state.household_weight, dtype=np.float64)
    commodity_ids = tuple(network.commodity_ids)
    channel_ids = tuple(network.household_catalog.household_good_ids)
    org_count = int(np.asarray(state.organization_capacity).size)
    demand_commodity = np.asarray(
        network.cell_commodity, dtype=np.int64
    )[np.asarray(network.demand_cell, dtype=np.int64)]

    comparison_quarters: list[dict[str, Any]] = []
    scientific_quarters: list[dict[str, Any]] = []
    window_sums: dict[str, float] = {}
    axis_totals: dict[tuple[str, str, str], dict[str, float]] = {
        axis: dict.fromkeys((*_AXIS_FLOW_FIELDS, "demand_rows", "bottleneck_demand_count"), 0.0)
        for axis in layout.axes
    }
    journal_chain: list[str] = []

    for tick, quarter in enumerate(forcing.quarters):
        external = ExternalWorldSlice(
            quarter=str(quarter), values={}, origins={}, evidence_status={}
        )
        effective = compile_effective_policy(
            scenario.material_parameters,
            household_base,
            policy,
            external,
            commodity_ids,
        )
        controls = effective.controls
        parameters = effective.material_parameters
        _require(
            controls.central_target is None and controls.investment_approvals is None,
            "the study pins central_target=None and investment_approvals=None",
        )

        boundary = copy.deepcopy(state)
        opening_state_digest = _sha256(canonical_material_bytes(state))
        opening_snapshot = capture_material_stocks(state)
        completed_before = int(state.completed_ticks)
        request_unconstrained = unconstrained_investment_request(state, parameters, network)
        credit_approval_caps = (
            _non_binding_credit_caps(state) if finance_probe else None
        )
        procurement_trace: dict[str, np.ndarray] | None = {} if finance_probe else None

        try:
            flows = tick_material(
                state,
                forcing,
                parameters,
                network,
                controls=controls,
                credit_approval_caps=credit_approval_caps,
                procurement_trace=procurement_trace,
            )
            summary = check_material_invariants(
                opening_snapshot,
                state,
                flows,
                parameters,
                network,
                controls=controls,
                forcing=forcing,
            )
            material_ratio = float(summary.max_material_tolerance_ratio)
            finance_ratio = float(summary.max_finance_tolerance_ratio)
            if not (material_ratio <= 1.0 and finance_ratio <= 1.0):
                raise RunHalted(
                    f"conservation gate breached at tick {tick}: material ratio "
                    f"{material_ratio}, finance ratio {finance_ratio}"
                )
            if int(state.completed_ticks) != completed_before:
                raise RunHalted(
                    f"tick_material moved the admitted clock to {int(state.completed_ticks)} "
                    f"before the gate passed (expected {completed_before})"
                )
            # The engine contract: completed_ticks advances only once the
            # quarter's conservation gate has passed.
            state.completed_ticks = completed_before + 1
            if not bool(np.all(np.isfinite(np.asarray(state.stock_value, dtype=np.float64)))):
                raise RunHalted(f"non-finite closing stock at tick {tick}")
        except RunHalted as exc:
            _halt(
                streams=streams,
                output_dir=output_dir,
                boundary=boundary,
                state=state,
                seed=seed,
                arm=arm,
                tick=tick,
                quarter=str(quarter),
                policy=policy,
                effective=effective,
                forcing=forcing,
                network=network,
                scenario=scenario,
                reason=str(exc),
                exception_type=type(exc).__name__,
            )
        except Exception as exc:
            _halt(
                streams=streams,
                output_dir=output_dir,
                boundary=boundary,
                state=state,
                seed=seed,
                arm=arm,
                tick=tick,
                quarter=str(quarter),
                policy=policy,
                effective=effective,
                forcing=forcing,
                network=network,
                scenario=scenario,
                reason=f"{type(exc).__name__}: {exc}",
                exception_type=type(exc).__name__,
            )

        closing_state_digest = _sha256(canonical_material_bytes(state))

        # --- axis-scoped procurement --------------------------------------
        ordered = np.asarray(flows.ordered, dtype=np.float64)
        delivered = np.asarray(flows.delivered, dtype=np.float64)
        bottleneck_mask = (ordered > 0.0) & (delivered <= 0.0)
        axis_columns = {
            name: np.bincount(
                layout.row_axis,
                weights=np.asarray(getattr(flows, name), dtype=np.float64),
                minlength=layout.axis_count,
            )
            for name in _AXIS_FLOW_FIELDS
        }
        axis_rows = np.bincount(layout.row_axis, minlength=layout.axis_count)
        axis_bottleneck = np.bincount(
            layout.row_axis[bottleneck_mask], minlength=layout.axis_count
        )
        axis_rows_table: dict[str, list[Any]] = {
            "seed": [int(seed)] * layout.axis_count,
            "arm": [arm.name] * layout.axis_count,
            "tick": [int(tick)] * layout.axis_count,
            "quarter": [str(quarter)] * layout.axis_count,
            "commodity": [axis[0] for axis in layout.axes],
            "stage": [axis[1] for axis in layout.axes],
            "purpose": [axis[2] for axis in layout.axes],
            "axis_status": ["OBSERVED" if flag else "BLOCKED_METRIC" for flag in layout.observed],
            "demand_rows": axis_rows.astype(np.int32).tolist(),
            "bottleneck_demand_count": axis_bottleneck.astype(np.int32).tolist(),
        }
        for name, column in axis_columns.items():
            axis_rows_table[name] = column.tolist()
        streams.demand.write(axis_rows_table)

        for index, axis in enumerate(layout.axes):
            bucket = axis_totals[axis]
            bucket["demand_rows"] += float(axis_rows[index])
            bucket["bottleneck_demand_count"] += float(axis_bottleneck[index])
            for name in _AXIS_FLOW_FIELDS:
                bucket[name] += float(axis_columns[name][index])

        investment_procurement = {
            name: _sum(np.asarray(getattr(flows, name), dtype=np.float64)[layout.investment_rows])
            for name in _AXIS_FLOW_FIELDS
        }

        # --- per-organization investment / credit / WIP -------------------
        streams.organizations.write(
            {
                "seed": [int(seed)] * org_count,
                "arm": [arm.name] * org_count,
                "tick": [int(tick)] * org_count,
                "quarter": [str(quarter)] * org_count,
                "org": list(range(org_count)),
                "investment_request_unconstrained": request_unconstrained.tolist(),
                "investment_requested_flows": np.asarray(
                    flows.organization_investment_requested, dtype=np.float64
                ).tolist(),
                "investment_approved": np.asarray(
                    flows.organization_investment_approved, dtype=np.float64
                ).tolist(),
                "investment_installed_capacity": np.asarray(
                    flows.organization_investment_completed, dtype=np.float64
                ).tolist(),
                "credit_requested": np.asarray(
                    flows.organization_credit_requested, dtype=np.float64
                ).tolist(),
                "credit_approved": np.asarray(
                    flows.organization_credit_approved, dtype=np.float64
                ).tolist(),
                "credit_drawn": np.asarray(
                    flows.organization_credit_drawn, dtype=np.float64
                ).tolist(),
                "bailout_requested": np.asarray(
                    flows.organization_bailout_requested, dtype=np.float64
                ).tolist(),
                "bailout_granted": np.asarray(
                    flows.organization_bailout_granted, dtype=np.float64
                ).tolist(),
                "shortage_expectation_open": np.asarray(
                    opening_snapshot.organization_shortage_expectation, dtype=np.float64
                ).tolist(),
                "shortage_expectation_close": np.asarray(
                    state.organization_shortage_expectation, dtype=np.float64
                ).tolist(),
                "bailout_expectation_open": np.asarray(
                    opening_snapshot.organization_bailout_expectation, dtype=np.float64
                ).tolist(),
                "bailout_expectation_close": np.asarray(
                    state.organization_bailout_expectation, dtype=np.float64
                ).tolist(),
                "capital_wip_open": np.asarray(
                    opening_snapshot.organization_capital_wip, dtype=np.float64
                ).tolist(),
                "capital_wip_close": np.asarray(
                    state.organization_capital_wip, dtype=np.float64
                ).tolist(),
                "construction_wip_open": np.asarray(
                    opening_snapshot.organization_construction_wip, dtype=np.float64
                ).tolist(),
                "construction_wip_close": np.asarray(
                    state.organization_construction_wip, dtype=np.float64
                ).tolist(),
                "project_approved_open": np.asarray(
                    opening_snapshot.organization_project_approved, dtype=np.float64
                ).tolist(),
                "project_approved_close": np.asarray(
                    state.organization_project_approved, dtype=np.float64
                ).tolist(),
                "capacity_open": np.asarray(
                    opening_snapshot.organization_capacity, dtype=np.float64
                ).tolist(),
                "capacity_close": np.asarray(
                    state.organization_capacity, dtype=np.float64
                ).tolist(),
                "activity_realized": np.asarray(
                    flows.organization_realized, dtype=np.float64
                ).tolist(),
                "organization_purchases": np.asarray(
                    flows.organization_purchases, dtype=np.float64
                ).tolist(),
                "organization_sales_receipts": np.asarray(
                    flows.organization_sales_receipts, dtype=np.float64
                ).tolist(),
                "cash_available_for_goods": _trace_array(
                    procurement_trace, "cash_available_for_goods", org_count
                ),
                "credit_approval_caps": _trace_array(
                    procurement_trace, "credit_approval_caps", org_count
                ),
                "input_order_cost": _trace_array(procurement_trace, "input_order_cost", org_count),
                "old_project_cost": _trace_array(procurement_trace, "old_project_cost", org_count),
                "new_investment_request_cost": _trace_array(
                    procurement_trace, "new_investment_request_cost", org_count
                ),
                "input_credit_earmarked": _trace_array(
                    procurement_trace, "input_credit_earmarked", org_count
                ),
            }
        )

        # --- journal ------------------------------------------------------
        legs = len(flows.journal_kind)
        journal_columns = {
            "seed": [int(seed)] * legs,
            "arm": [arm.name] * legs,
            "tick": [int(value) for value in flows.journal_tick],
            "quarter": [str(quarter)] * legs,
            "kind": [str(value) for value in flows.journal_kind],
            "debit": [int(value) for value in flows.journal_debit],
            "credit": [int(value) for value in flows.journal_credit],
            "currency": [str(value) for value in flows.journal_currency],
            "amount": [float(value) for value in flows.journal_amount],
            "org": [-1 if value is None else int(value) for value in flows.journal_org],
            "leg": [int(value) for value in flows.journal_leg],
            "event_id": [None if value is None else str(value) for value in flows.journal_event],
        }
        # A journal leg is only evidence if both of its accounts exist in the
        # directory; an unknown id is an illegal counterparty, not a new one.
        touched = set(journal_columns["debit"]) | set(journal_columns["credit"])
        invalid_accounts = sorted(touched - account_ids)
        journal_account_check = {
            "checked": legs,
            "accounts_touched": len(touched),
            "invalid": len(invalid_accounts),
            "invalid_account_ids": invalid_accounts[:8],
            "status": "OK" if not invalid_accounts else "INVALID_COUNTERPARTY",
        }
        if invalid_accounts:
            _halt(
                streams=streams,
                output_dir=output_dir,
                boundary=boundary,
                state=state,
                seed=seed,
                arm=arm,
                tick=tick,
                quarter=str(quarter),
                policy=policy,
                effective=effective,
                forcing=forcing,
                network=network,
                scenario=scenario,
                reason=(
                    f"journal leg references {len(invalid_accounts)} account ids outside "
                    f"the account directory at tick {tick}: {invalid_accounts[:8]}"
                ),
                exception_type="JournalAccountError",
            )
        if legs:
            streams.journal.write(journal_columns)
        journal_digest = _digest(
            {
                "kind": journal_columns["kind"],
                "debit": journal_columns["debit"],
                "credit": journal_columns["credit"],
                "currency": journal_columns["currency"],
                "amount": journal_columns["amount"],
                "org": journal_columns["org"],
                "leg": journal_columns["leg"],
                "event_id": journal_columns["event_id"],
            }
        )
        journal_chain.append(journal_digest)

        # --- trace --------------------------------------------------------
        household = _household_view(weight, flows, commodity_ids, channel_ids)
        tick_metrics = {
            "investment_request_unconstrained_total": _sum(request_unconstrained),
            "investment_requested_flows_total": _sum(flows.organization_investment_requested),
            "investment_approved_total": _sum(flows.organization_investment_approved),
            "investment_installed_capacity_total": _sum(flows.organization_investment_completed),
            "credit_requested_total": _sum(flows.organization_credit_requested),
            "credit_approved_total": _sum(flows.organization_credit_approved),
            "credit_drawn_total": _sum(flows.organization_credit_drawn),
            "bailout_requested_total": _sum(flows.organization_bailout_requested),
            "bailout_granted_total": _sum(flows.organization_bailout_granted),
            "activity_target_total": _sum(flows.activity_target),
            "activity_realized_total": _sum(flows.activity_realized),
            "organization_realized_total": _sum(flows.organization_realized),
            "organization_purchases_total": _sum(flows.organization_purchases),
            "organization_sales_receipts_total": _sum(flows.organization_sales_receipts),
            "shortage_expectation_mean": _mean(state.organization_shortage_expectation),
            "bailout_expectation_mean": _mean(state.organization_bailout_expectation),
            "capacity_close_total": _sum(state.organization_capacity),
            "capital_wip_close_total": _sum(state.organization_capital_wip),
            "construction_wip_close_total": _sum(state.organization_construction_wip),
            "project_approved_close_total": _sum(state.organization_project_approved),
            "procurement": _procurement_view(flows),
            "investment_purpose_procurement": investment_procurement,
            "bottleneck_demand_count": int(bottleneck_mask.sum()),
        }
        for name, value in tick_metrics.items():
            if isinstance(value, (int, float)):
                window_sums[name] = window_sums.get(name, 0.0) + float(value)
        for channel_id, values in household["channel"].items():
            for series, value in values.items():
                window_sums[f"household_{series}_channel:{channel_id}"] = (
                    window_sums.get(f"household_{series}_channel:{channel_id}", 0.0) + float(value)
                )
        for commodity_id, values in household["commodity"].items():
            for series, value in values.items():
                key = f"household_{series}_commodity:{commodity_id}"
                window_sums[key] = window_sums.get(key, 0.0) + float(value)
        delivered_by_commodity = np.bincount(
            demand_commodity, weights=delivered, minlength=len(commodity_ids)
        )
        for index, commodity_id in enumerate(commodity_ids):
            key = f"commodity_delivered:{commodity_id}"
            window_sums[key] = window_sums.get(key, 0.0) + float(delivered_by_commodity[index])

        request_diff = float(
            np.max(
                np.abs(
                    request_unconstrained
                    - np.asarray(flows.organization_investment_requested, dtype=np.float64)
                )
            )
        )
        # Closing stock is a level, not a flow: it is exported per quarter with
        # its own source named, never summed across quarters.
        stock_close = _stock_close_by_axis(state, network)
        streams.trace.write(
            {
                "seed": int(seed),
                "arm": arm.name,
                "tick": int(tick),
                "quarter": str(quarter),
                "budget": arm.budget,
                "intensity": arm.intensity,
                "regime": arm.regime,
                "mediator": arm.mediator,
                "role": arm.role,
                "policy_vector": dict(policy_dump),
                "effective_material_parameters_sha256": _digest(effective.material_parameters),
                "effective_household_parameters_sha256": _digest(effective.household_parameters),
                "effective_household_catalog_sha256": _digest(effective.household_catalog),
                "controls_binding": {
                    "central_target": None,
                    "investment_approvals": None,
                    "procurement_requests": None,
                    "autonomy": float(controls.autonomy),
                    "price_changed": bool(effective.price_changed),
                },
                "opening_state_sha256": opening_state_digest,
                "closing_state_sha256": closing_state_digest,
                "investment_request_recheck_max_abs_diff": request_diff,
                "metrics": tick_metrics,
                "household": household,
                "conservation": {
                    "max_material_tolerance_ratio": material_ratio,
                    "max_finance_tolerance_ratio": finance_ratio,
                    "checked_cells": int(summary.checked_cells),
                    "per_ledger": {
                        ledger: {"residual": float(pair[0]), "ratio": float(pair[1])}
                        for ledger, pair in sorted(summary.per_ledger.items())
                    },
                },
                "journal_sha256": journal_digest,
                "journal_legs": legs,
                "journal_account_check": journal_account_check,
                "finance_trace": _finance_trace_record(procurement_trace),
                "stock_close": stock_close,
            }
        )

        comparison_quarters.append(
            {
                "closing_state_sha256": closing_state_digest,
                "metrics": tick_metrics,
                "journal_sha256": journal_digest,
                "stock_close_by_commodity_stage": _stock_close_digest_rows(stock_close),
            }
        )
        scientific_quarters.append(
            {
                "tick": int(tick),
                "quarter": str(quarter),
                "policy_vector": dict(policy_dump),
                "effective_material_parameters_sha256": _digest(effective.material_parameters),
                "effective_household_parameters_sha256": _digest(effective.household_parameters),
                "metrics": tick_metrics,
                "household": household,
                "closing_state_sha256": closing_state_digest,
                "stock_close": stock_close,
            }
        )
        result.quarters.append(str(quarter))

    final_state_digest = _sha256(canonical_material_bytes(state))
    comparison_digest = _digest(
        {
            "opening_state_sha256": opening_digest,
            "quarters": comparison_quarters,
            "final_state_sha256": final_state_digest,
        }
    )
    result.comparison_digest = comparison_digest
    result.final_state_digest = final_state_digest
    result.journal_digest = _digest(journal_chain)
    result.scientific_digest = _digest(
        {
            "schema_version": PREREGISTERED_SPEC_SCHEMA,
            "phase_id": PREREGISTERED_PHASE_ID,
            "mechanism_id": PREREGISTERED_MECHANISM_ID,
            "study_id": PREREGISTERED_STUDY_ID,
            "spec_sha256": spec_digest,
            "legacy_card_sha256": card_sha256,
            "scenario_sha256": scenario_sha256,
            "seed": int(seed),
            "window": [str(quarter) for quarter in forcing.quarters],
            "opening_state_sha256": opening_digest,
            "network_sha256": network_digest,
            "forcing_sha256": forcing_digest,
            "household_base_sha256": _digest(household_base),
            "quarters": scientific_quarters,
            "final_state_sha256": final_state_digest,
            "comparison_digest": comparison_digest,
        }
    )
    result.window_metrics = window_sums
    result.axis_totals = axis_totals
    result.axis_observed = {
        axis: flag for axis, flag in zip(layout.axes, layout.observed, strict=True)
    }
    if comparison_quarters:
        result.final_quarter_metrics = dict(comparison_quarters[-1]["metrics"])
    result.collapsed_chains = _collapsed_chains(window_sums)
    return result


def _stock_close_by_axis(state: Any, network: Any) -> list[dict[str, Any]]:
    """Closing stock per (commodity, stage), summed from the real state cells.

    This replaces the blocked ``commodity_circuit.stock_close``: it names its
    own source instead of inventing a circuit quantity that does not exist.
    Each row states how many cells it summed, so a reader never has to guess
    what the number covers.
    """
    stock = np.asarray(state.stock_value, dtype=np.float64)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    cell_stage = np.asarray(network.cell_stage, dtype=np.int64)
    totals: dict[tuple[str, str], list[float]] = {}
    for cell in range(stock.size):
        key = (network.commodity_ids[int(cell_commodity[cell])], _stage_name(int(cell_stage[cell])))
        bucket = totals.setdefault(key, [0.0, 0.0])
        bucket[0] += float(stock[cell])
        bucket[1] += 1.0
    return [
        {
            "commodity": commodity,
            "stage": stage,
            "stock_close": float(total),
            "cells": int(cells),
            "source": "sum of state.stock_value over its cells",
        }
        for (commodity, stage), (total, cells) in sorted(totals.items())
    ]


def _stock_close_digest_rows(rows: Sequence[Mapping[str, Any]]) -> list[list[Any]]:
    """The canonical digest form of the stock rows.

    The exported rows name their fields; the comparison digest keeps the flat
    form it was defined with, so renaming an export column never silently
    re-baselines an arm's comparison digest.
    """
    return [
        [
            str(row["commodity"]),
            str(row["stage"]),
            float(row["stock_close"]),
            int(row["cells"]),
            str(row["source"]),
        ]
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Gap ratios, first stages, contrasts, verdicts
# ---------------------------------------------------------------------------


def _blocked_gap() -> dict[str, Any]:
    return {
        "value": None,
        "numerator": None,
        "denominator": None,
        "status": "BLOCKED_METRIC",
    }


def _gap(numerator: float, denominator: float) -> dict[str, Any]:
    if denominator == 0.0:
        return {
            "value": None,
            "numerator": float(numerator),
            "denominator": 0.0,
            "status": "ZERO_DENOMINATOR",
        }
    return {
        "value": float(numerator) / float(denominator),
        "numerator": float(numerator),
        "denominator": float(denominator),
        "status": "OK",
    }


def axis_gap_rows(result: ArmResult) -> list[dict[str, Any]]:
    """Per-axis gross and funded gap ratios for one arm/seed window.

    ``gross gap`` counts unfunded demand too; ``funded gap`` only counts demand
    that got money.  Numerator, denominator and unit travel with every value,
    and a zero denominator is never turned into a zero.
    """
    rows: list[dict[str, Any]] = []
    for axis, totals in result.axis_totals.items():
        base = {
            "arm": result.arm,
            "seed": result.seed,
            "commodity": axis[0],
            "stage": axis[1],
            "purpose": axis[2],
            "unit": "ratio_of_physical_units_on_this_axis",
            "demand_rows": int(totals["demand_rows"]),
            "ordered_gross": totals["ordered_gross"],
            "ordered": totals["ordered"],
            "delivered": totals["delivered"],
            "bottleneck_demand_count": int(totals["bottleneck_demand_count"]),
        }
        if not result.axis_observed.get(axis, False):
            base.update(
                {
                    "axis_status": "BLOCKED_METRIC",
                    "ordered_gross": None,
                    "ordered": None,
                    "delivered": None,
                    "bottleneck_demand_count": None,
                    "gross_gap": _blocked_gap(),
                    "funded_gap": _blocked_gap(),
                }
            )
        else:
            base.update(
                {
                    "axis_status": "OBSERVED",
                    "gross_gap": _gap(
                        totals["ordered_gross"] - totals["delivered"], totals["ordered_gross"]
                    ),
                    "funded_gap": _gap(totals["ordered"] - totals["delivered"], totals["ordered"]),
                }
            )
        rows.append(base)
    return rows


def _moved(left: float, right: float) -> bool:
    return abs(left - right) > _FIRST_STAGE_ATOL + _FIRST_STAGE_RTOL * max(abs(left), abs(right))


def _first_stage(
    results: Mapping[tuple[int, str], ArmResult],
    seeds: Sequence[int],
    gap_rows: Mapping[tuple[int, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    """Adjudicate the budget, investment and demand-regime stages separately.

    A stage is only ``BINDING`` when a real quantity moved.  A parameter value
    is never used in place of an effect, and a non-binding leg carries an
    explicit null reason.
    """

    def window(seed: int, arm: str, key: str) -> float | None:
        found = results.get((seed, arm))
        return None if found is None else float(found.window_metrics.get(key, 0.0))

    budget: list[dict[str, Any]] = []
    investment: list[dict[str, Any]] = []
    demand: list[dict[str, Any]] = []

    for seed in seeds:
        for regime in PREREGISTERED_REGIMES:
            for level in PREREGISTERED_LEVELS:
                soft, hard = f"soft_{level}_{regime}", f"hard_{level}_{regime}"
                if (seed, soft) not in results or (seed, hard) not in results:
                    continue
                soft_credit = float(window(seed, soft, "credit_drawn_total"))
                hard_credit = float(window(seed, hard, "credit_drawn_total"))
                soft_rescue = float(window(seed, soft, "bailout_granted_total"))
                hard_rescue = float(window(seed, hard, "bailout_granted_total"))
                credit_cut = f"credit_cut_high_{regime}"
                rescue_cut = f"rescue_cut_high_{regime}"
                # The mediator arms exist only at high investment.  At low
                # investment there is no cut arm to compare against, so the
                # decomposition reports null there instead of borrowing the
                # high-level arm and mislabelling it.
                cut_credit = (
                    window(seed, credit_cut, "credit_drawn_total") if level == "high" else None
                )
                cut_rescue = (
                    window(seed, rescue_cut, "bailout_granted_total") if level == "high" else None
                )
                credit_cut_rescue = (
                    window(seed, credit_cut, "bailout_granted_total") if level == "high" else None
                )
                credit_binding = _moved(soft_credit, hard_credit)
                rescue_binding = _moved(soft_rescue, hard_rescue) or (
                    cut_rescue is not None and _moved(soft_rescue, float(cut_rescue))
                )
                budget.append(
                    {
                        "seed": int(seed),
                        "regime": regime,
                        "intensity": level,
                        "credit_leg": {
                            "soft_credit_drawn": soft_credit,
                            "hard_credit_drawn": hard_credit,
                            "credit_cut_credit_drawn": cut_credit,
                            "difference": soft_credit - hard_credit,
                            "status": "BINDING" if credit_binding else "NONBINDING",
                            "reason": None
                            if credit_binding
                            else (
                                "NO_FUNDS"
                                if soft_credit == 0.0 and hard_credit == 0.0
                                else "ZERO_OUTPUT"
                            ),
                        },
                        "rescue_leg": {
                            "soft_bailout_granted": soft_rescue,
                            "hard_bailout_granted": hard_rescue,
                            "rescue_cut_bailout_granted": cut_rescue,
                            "credit_cut_bailout_granted": credit_cut_rescue,
                            "hardness_only_note": (
                                "rescue_cut isolates budget_hardness at fixed "
                                "credit_fraction=0.5; credit_cut isolates "
                                "credit_fraction=0 at fixed budget_hardness=0. The "
                                "hardness coordinate can only bind where a bailout is "
                                "actually granted somewhere in the comparison."
                            ),
                            "status": "BINDING" if rescue_binding else "NONBINDING",
                            "reason": None
                            if rescue_binding
                            else (
                                "ZERO_OUTPUT"
                                if soft_rescue == 0.0 and hard_rescue == 0.0
                                else "NOT_APPLICABLE"
                            ),
                        },
                        "joint_budget_leg": {
                            "status": (
                                "BINDING"
                                if (credit_binding or rescue_binding)
                                else "NONBINDING"
                            ),
                            "note": (
                                "soft/hard is a JOINT credit + hardness intervention; "
                                "neither leg alone may be called the budget effect."
                            ),
                        },
                        "axis_comparison": {
                            "comparable_axes": len(
                                {
                                    key
                                    for key in {
                                        (row["commodity"], row["stage"], row["purpose"])
                                        for row in gap_rows.get((seed, soft), [])
                                        if row["axis_status"] == "OBSERVED"
                                    }
                                    & {
                                        (row["commodity"], row["stage"], row["purpose"])
                                        for row in gap_rows.get((seed, hard), [])
                                        if row["axis_status"] == "OBSERVED"
                                    }
                                }
                            ),
                        },
                    }
                )

            for level_budget in ("soft", "hard"):
                low, high = f"{level_budget}_low_{regime}", f"{level_budget}_high_{regime}"
                if (seed, low) not in results or (seed, high) not in results:
                    continue
                keys = (
                    "investment_request_unconstrained_total",
                    "investment_approved_total",
                    "investment_installed_capacity_total",
                    "credit_drawn_total",
                    "bailout_granted_total",
                    "activity_realized_total",
                )
                differences = {
                    key: float(window(seed, high, key)) - float(window(seed, low, key))
                    for key in keys
                }
                request_moved = _moved(
                    differences["investment_request_unconstrained_total"], 0.0
                )
                binding = request_moved and any(
                    _moved(differences[key], 0.0)
                    for key in (
                        "investment_approved_total",
                        "investment_installed_capacity_total",
                        "credit_drawn_total",
                        "bailout_granted_total",
                    )
                )
                investment.append(
                    {
                        "seed": int(seed),
                        "budget": level_budget,
                        "regime": regime,
                        "low": low,
                        "high": high,
                        "differences": differences,
                        "status": "BINDING" if binding else "NONBINDING",
                        "reason": None if binding else "ZERO_OUTPUT",
                    }
                )

        for level_budget in ("soft", "hard", "credit_cut", "rescue_cut"):
            for level in PREREGISTERED_LEVELS:
                if level_budget in ("credit_cut", "rescue_cut") and level != "high":
                    continue
                base_arm = f"{level_budget}_{level}_base"
                reduced_arm = f"{level_budget}_{level}_reduced"
                if (seed, base_arm) not in results or (seed, reduced_arm) not in results:
                    continue
                base_metrics = results[(seed, base_arm)].window_metrics
                reduced_metrics = results[(seed, reduced_arm)].window_metrics
                differing = sorted(
                    key.split(":", 1)[1]
                    for key, value in base_metrics.items()
                    if key.startswith("household_desired_channel:")
                    and _moved(float(value), float(reduced_metrics.get(key, 0.0)))
                )
                demand.append(
                    {
                        "seed": int(seed),
                        "budget": level_budget,
                        "intensity": level,
                        "base_arm": base_arm,
                        "reduced_arm": reduced_arm,
                        "differing_household_desired_channels": differing,
                        "status": "BINDING" if differing else "NONBINDING",
                        "reason": None if differing else "ZERO_OUTPUT",
                    }
                )

    return {
        "budget": budget,
        "investment": investment,
        "demand_regime": demand,
        "note": (
            "Each stage is adjudicated on its own. A non-binding leg is reported "
            "NONBINDING with an explicit null reason; no parameter value substitutes "
            "for an effect."
        ),
    }


_CONTRAST_KEYS = (
    "credit_drawn_total",
    "bailout_requested_total",
    "bailout_granted_total",
    "investment_request_unconstrained_total",
    "investment_requested_flows_total",
    "investment_approved_total",
    "investment_installed_capacity_total",
    "activity_realized_total",
    "organization_realized_total",
    "capital_wip_close_total",
    "construction_wip_close_total",
    "project_approved_close_total",
)


def _gap_index(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    return {(row["commodity"], row["stage"], row["purpose"]): row for row in rows}


def _contrasts(
    results: Mapping[tuple[int, str], ArmResult],
    seeds: Sequence[int],
    gap_rows: Mapping[tuple[int, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    """Per seed and per regime: budget contrast, investment contrast, DiD.

    The two regimes are never pooled.  Only metrics with the same definition on
    both sides are subtracted, and gap ratios are only compared on axes both
    arms actually observed.
    """

    def window(seed: int, arm: str, key: str) -> float | None:
        found = results.get((seed, arm))
        return None if found is None else float(found.window_metrics.get(key, 0.0))

    rows: list[dict[str, Any]] = []
    for seed in seeds:
        for regime in PREREGISTERED_REGIMES:
            needed = [
                f"{budget}_{level}_{regime}"
                for budget in ("soft", "hard")
                for level in PREREGISTERED_LEVELS
            ]
            if any((seed, arm) not in results for arm in needed):
                continue
            budget_contrast: dict[str, Any] = {}
            for level in PREREGISTERED_LEVELS:
                soft, hard = f"soft_{level}_{regime}", f"hard_{level}_{regime}"
                for key in _CONTRAST_KEYS:
                    left, right = window(seed, soft, key), window(seed, hard, key)
                    if left is None or right is None:
                        continue
                    budget_contrast[f"{key}|intensity={level}"] = {
                        "metric": key,
                        "soft": left,
                        "hard": right,
                        "contrast": left - right,
                    }
            investment_contrast: dict[str, Any] = {}
            for level_budget in ("soft", "hard"):
                low, high = f"{level_budget}_low_{regime}", f"{level_budget}_high_{regime}"
                for key in _CONTRAST_KEYS:
                    left, right = window(seed, high, key), window(seed, low, key)
                    if left is None or right is None:
                        continue
                    investment_contrast[f"{key}|budget={level_budget}"] = {
                        "metric": key,
                        "high": left,
                        "low": right,
                        "contrast": left - right,
                    }
            difference_in_differences: dict[str, Any] = {}
            for key in _CONTRAST_KEYS:
                high = budget_contrast.get(f"{key}|intensity=high")
                low = budget_contrast.get(f"{key}|intensity=low")
                if high is None or low is None:
                    continue
                difference_in_differences[key] = {
                    "budget_contrast_high": high["contrast"],
                    "budget_contrast_low": low["contrast"],
                    "difference_in_differences": high["contrast"] - low["contrast"],
                }

            axis_contrast_by_level: dict[str, dict[str, Any]] = {}
            for level in PREREGISTERED_LEVELS:
                left_index = _gap_index(gap_rows.get((seed, f"soft_{level}_{regime}"), []))
                right_index = _gap_index(gap_rows.get((seed, f"hard_{level}_{regime}"), []))
                axis_contrast: dict[str, Any] = {}
                for key in sorted(set(left_index) & set(right_index)):
                    for metric_name in ("gross_gap", "funded_gap"):
                        left = left_index[key][metric_name]
                        right = right_index[key][metric_name]
                        label = f"{'|'.join(key)}|{metric_name}"
                        if left["status"] != "OK" or right["status"] != "OK":
                            status = (
                                "BLOCKED_METRIC"
                                if "BLOCKED_METRIC" in (left["status"], right["status"])
                                else "ZERO_DENOMINATOR"
                            )
                            axis_contrast[label] = {
                                "axis": "|".join(key),
                                "metric": metric_name,
                                "soft": left,
                                "hard": right,
                                "contrast": None,
                                "status": status,
                            }
                            continue
                        axis_contrast[label] = {
                            "axis": "|".join(key),
                            "metric": metric_name,
                            "soft": left,
                            "hard": right,
                            "contrast": float(left["value"]) - float(right["value"]),
                            "status": "OK",
                        }
                axis_contrast_by_level[level] = axis_contrast

            rows.append(
                {
                    "seed": int(seed),
                    "regime": regime,
                    "budget_contrast": budget_contrast,
                    "investment_contrast": investment_contrast,
                    "difference_in_differences": difference_in_differences,
                    "axis_scoped_budget_contrast": axis_contrast_by_level,
                }
            )

    triple: dict[str, Any] = {}
    by_pair = {(row["seed"], row["regime"]): row for row in rows}
    for seed in seeds:
        if (seed, "base") not in by_pair or (seed, "reduced") not in by_pair:
            continue
        base_row = by_pair[(seed, "base")]["budget_contrast"]
        reduced_row = by_pair[(seed, "reduced")]["budget_contrast"]
        per_seed: dict[str, Any] = {}
        for key in sorted(set(base_row) & set(reduced_row)):
            metric_name = key.split("|intensity=", 1)[0]
            high_key, low_key = f"{metric_name}|intensity=high", f"{metric_name}|intensity=low"
            present = all(
                key in index for key in (high_key, low_key) for index in (base_row, reduced_row)
            )
            if present:
                base_high = base_row[high_key]["contrast"]
                base_low = base_row[low_key]["contrast"]
                reduced_high = reduced_row[high_key]["contrast"]
                reduced_low = reduced_row[low_key]["contrast"]
                per_seed[metric_name] = {
                    "budget_contrast_base_high": base_high,
                    "budget_contrast_base_low": base_low,
                    "budget_contrast_reduced_high": reduced_high,
                    "budget_contrast_reduced_low": reduced_low,
                    "regime_interaction": (base_high - reduced_high),
                    "triple_difference": (base_high - base_low) - (reduced_high - reduced_low),
                }
        triple[str(seed)] = per_seed

    return {
        "by_seed_and_regime": rows,
        "regime_interaction_and_triple_difference": triple,
        "pooling_note": (
            "Regimes are never pooled into one series. Every contrast is reported per "
            "seed with its own values; repeated trajectories do not create confidence "
            "intervals."
        ),
        "gap_note": (
            "Gap ratios are compared only on commonly observed commodity+stage+purpose "
            "axes. Heterogeneous physical units are never summed across commodities."
        ),
        "household_note": (
            "Household quantities stay per household-good channel and per commodity; "
            "no cross-commodity welfare total is computed."
        ),
    }


def _verdicts(
    results: Mapping[tuple[int, str], ArmResult],
    first_stage: Mapping[str, Any],
    contrasts: Mapping[str, Any],
    seeds: Sequence[int],
    arms: Sequence[str],
) -> dict[str, Any]:
    """Technical, structural and historical verdicts, kept strictly apart."""
    complete = all((seed, arm) in results for seed in seeds for arm in arms)
    technical = {
        "verdict": "PASS" if complete else "INCOMPLETE",
        "level": "VERIFIED_BY_RUN",
        "basis": (
            "every executed tick passed the engine's own material and finance tolerance "
            "gate (<=1) and advanced the material clock by exactly one quarter"
        ),
    }

    structural: dict[str, Any] = {}
    for regime in PREREGISTERED_REGIMES:
        bound = [
            row
            for row in first_stage["budget"]
            if row["regime"] == regime and row["joint_budget_leg"]["status"] == "BINDING"
        ]
        if not bound:
            structural[regime] = {
                "verdict": "UNIDENTIFIED",
                "level": "VERIFIED_BY_RUN",
                "reason": (
                    "the preregistered budget first stage never bound in this window, "
                    "so the card's falsification criterion cannot be read"
                ),
            }
            continue
        non_falling: list[dict[str, Any]] = []
        readable = 0
        readable_by_level = {level: 0 for level in PREREGISTERED_LEVELS}
        # The card's criterion is judged at both preregistered investment
        # levels.  Reading only the high level would let a low-level
        # counter-example pass unnoticed, so both vectors are kept.
        for contrast in contrasts["by_seed_and_regime"]:
            if contrast["regime"] != regime:
                continue
            for level, axes_by_label in contrast["axis_scoped_budget_contrast"].items():
                axis_entries = [
                    (label, entry)
                    for label, entry in axes_by_label.items()
                    if entry["status"] == "OK"
                ]
                if not axis_entries:
                    continue
                readable += 1
                readable_by_level[level] += 1
                # The card's criterion reads "the shortage metrics do not fall",
                # so a strictly positive soft-minus-hard contrast is a fall and
                # a non-positive one is a metric that did not fall.  The whole
                # axis vector is kept: no favourable column is selected after
                # the fact.
                stuck = [
                    {"axis": label, "contrast": float(entry["contrast"])}
                    for label, entry in axis_entries
                    if float(entry["contrast"]) <= 0.0
                ]
                if stuck:
                    non_falling.append(
                        {"seed": contrast["seed"], "intensity": level, "axes": stuck}
                    )
        if readable == 0:
            structural[regime] = {
                "verdict": "UNIDENTIFIED",
                "level": "VERIFIED_BY_RUN",
                "reason": (
                    "no commonly observed shortage axis had a nonzero denominator in "
                    "either compared arm"
                ),
            }
        elif non_falling:
            structural[regime] = {
                "verdict": "REJECTED",
                "level": "VERIFIED_BY_RUN",
                "reason": (
                    "the card's own falsification criterion is met in this model and "
                    "window: on at least one preregistered shortage axis, at one or "
                    "both investment levels, the gap does not fall when hardness rises "
                    "and credit is cut"
                ),
                "readable_contrasts": readable,
                "readable_contrasts_by_level": readable_by_level,
                "levels_adjudicated": list(PREREGISTERED_LEVELS),
                "seeds_with_non_falling_shortage_axis": non_falling,
            }
        else:
            structural[regime] = {
                "verdict": "CONDITIONAL",
                "level": "VERIFIED_BY_RUN",
                "reason": (
                    "every readable axis falls at both investment levels, but a "
                    "four-quarter synthetic window cannot establish the card's "
                    "regime-independent sufficiency claim, so SUPPORTED is never "
                    "produced here"
                ),
                "readable_contrasts": readable,
                "readable_contrasts_by_level": readable_by_level,
                "levels_adjudicated": list(PREREGISTERED_LEVELS),
            }

    return {
        "technical": technical,
        "structural": {
            "by_regime": structural,
            "supported_claim": None,
            "supported_note": (
                "SUPPORTED is not reachable from a four-quarter synthetic window; the "
                "card's sufficiency claim is about sustained, regime-independent shortage."
            ),
            "rescue_leg_nonbinding_records": sum(
                1 for row in first_stage["budget"] if row["rescue_leg"]["status"] == "NONBINDING"
            ),
            "credit_leg_nonbinding_records": sum(
                1 for row in first_stage["budget"] if row["credit_leg"]["status"] == "NONBINDING"
            ),
            "arms_with_zero_bailout_grant": sorted(
                {
                    arm
                    for (_seed, arm), result in results.items()
                    if result.window_metrics.get("bailout_granted_total", 0.0) == 0.0
                }
            ),
            "level": "VERIFIED_BY_RUN",
        },
        "historical": {
            "identification_status": "UNIDENTIFIED",
            "historical_support": "NOT_ESTABLISHED",
            "level": "NOT_RUN",
            "reason": (
                "no admitted enterprise archive or independent shortage observation was "
                "used; a synthetic structural run cannot promote the historical verdict"
            ),
        },
        "f2_generalisation": {
            "status": "NOT_RUN",
            "level": "NOT_RUN",
            "reason": "this study deliberately leaves the F2 investment price axis untouched",
        },
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(_canonical(payload).decode("utf-8") + "\n", encoding="utf-8")


def _artifact_list(output_dir: Path) -> list[dict[str, str]]:
    return [
        {
            "path": str(path.relative_to(output_dir)),
            "sha256": _sha256_file(path),
            "bytes": str(path.stat().st_size),
        }
        for path in sorted(output_dir.rglob("*"))
        if path.is_file()
    ]


def run_m02_study(
    root: Path,
    *,
    output_dir: Path,
    spec_path: Path = DEFAULT_SPEC_PATH,
    seeds: Sequence[int] | None = None,
    arm_names: Sequence[str] | None = None,
    finance_probe: bool = False,
) -> dict[str, Any]:
    """Run the preregistered M02 enterprise-chain study.

    Everything is refused before the output directory exists and before any
    model is initialised.  Only the full 3-seed x 13-arm design is
    ``COMPLETED``; any subset is ``PARTIAL``.

    ``arm_names`` is both the filter and the execution order.

    ``output_dir`` must be a path that does not exist yet.  The CLI restricts
    it further to a fresh directory under ``<root>/outputs``; this Python entry
    point also accepts a fresh directory outside the repository so pytest can
    isolate a run in ``tmp_path``.  Neither form may write anywhere else.

    ``finance_probe`` is a diagnostic only: it reads the kernel's pre-scaling
    cash intermediates through ``procurement_trace``, which switches the engine
    to its H3B bank-lender journal path.  It is off by default because that
    path changes the journal bytes a preregistered run must reproduce.
    """
    root = Path(root).resolve()
    output_dir = Path(output_dir)
    spec_path = Path(spec_path)
    if not spec_path.is_absolute():
        spec_path = (root / spec_path).resolve()

    started = time.monotonic()
    spec = load_study_spec(root, spec_path)
    selected_seeds = _select_subset(seeds, spec.seeds, "seeds", int)
    selected_arms = _select_subset(arm_names, spec.arm_names, "arm_names", str)
    policies = resolve_arm_policies(spec, root)
    _require(
        not output_dir.exists(),
        f"output directory already exists: {output_dir}",
    )
    output_dir.mkdir(parents=True)
    contract = load_research_contract(root)
    base_scenario = load_scenario(root, spec.scenario_id)

    streams = _Streams(
        trace=_JsonlStream(output_dir / "trace.jsonl"),
        journal=_ParquetStream(output_dir / "journal.parquet", JOURNAL_SCHEMA),
        organizations=_ParquetStream(
            output_dir / "organization_investment_credit_wip.parquet", ORGANIZATION_SCHEMA
        ),
        demand=_ParquetStream(output_dir / "demand_by_axis.parquet", DEMAND_SCHEMA),
    )
    (output_dir / "spec.json").write_bytes(spec.path.read_bytes())

    results: dict[tuple[int, str], ArmResult] = {}
    input_identity: list[dict[str, Any]] = []
    account_directories: dict[int, list[list[Any]]] = {}
    failure: dict[str, Any] | None = None
    baseline_collapse: list[dict[str, Any]] = []

    try:
        for seed in selected_seeds:
            payload = base_scenario.model_dump()
            payload["households"] = spec.households
            payload["ticks"] = spec.ticks
            payload["seed"] = int(seed)
            scenario = ScenarioSpec.model_validate(payload)
            scenario.validate_for_run(contract)

            initial = build_material_initial_conditions(scenario, RngRegistry(scenario.seed))
            network = build_material_network(scenario, contract, initial)
            opening = initialize_material(scenario, initial, network)
            registry = DataRegistry.load(root, allowed_commodities=list(scenario.commodities))
            forcing = load_material_forcing(scenario, registry)
            quarters = tuple(str(quarter) for quarter in forcing.quarters)
            if quarters != spec.window:
                raise SpecRejection(
                    f"forcing window {list(quarters)} does not match the preregistered "
                    f"window {list(spec.window)}"
                )
            layout = build_axis_layout(network)
            opening_digest = _sha256(canonical_material_bytes(opening))
            network_digest = _digest(network)
            forcing_digest = _digest(forcing)
            account_directory = build_account_directory(opening)
            account_entries = sorted(
                [str(key[0]), int(key[1]), str(key[2]), str(key[3])]
                for key in account_directory
            )
            account_ids = frozenset(int(value) for value in account_directory.values())
            account_directory_sha256 = _digest(account_entries)
            account_directories[int(seed)] = account_entries
            input_identity.append(
                {
                    "seed": int(seed),
                    "opening_state_sha256": opening_digest,
                    "network_sha256": network_digest,
                    "forcing_sha256": forcing_digest,
                    "account_directory_sha256": account_directory_sha256,
                    "account_count": len(account_entries),
                    "quarters": list(quarters),
                    "households": int(spec.households),
                    "scenario_sha256": spec.scenario_sha256,
                    "card_sha256": spec.card_sha256,
                }
            )
            household_bases = {
                "base": scenario.household_parameters,
                "reduced": reduced_demand_household_parameters(scenario.household_parameters),
            }
            # Execute in exactly the order the caller asked for, resolved
            # against the preregistered designs.  A full run requests the spec
            # order and is therefore unchanged; a subset run executes the arms
            # it was actually given, in the sequence it named them.
            arm_designs = {arm.name: arm for arm in spec.arms}
            for arm_name in selected_arms:
                arm = arm_designs[arm_name]
                result = _run_arm(
                    scenario=scenario,
                    opening=opening,
                    forcing=forcing,
                    network=network,
                    layout=layout,
                    arm=arm,
                    seed=int(seed),
                    policy_dump=policies[arm.name],
                    household_base=household_bases[arm.regime],
                    streams=streams,
                    output_dir=output_dir,
                    opening_digest=opening_digest,
                    forcing_digest=forcing_digest,
                    network_digest=network_digest,
                    spec_digest=spec.digest,
                    card_sha256=spec.card_sha256,
                    scenario_sha256=spec.scenario_sha256,
                    account_ids=account_ids,
                    finance_probe=finance_probe,
                )
                if result.opening_state_digest != opening_digest:
                    raise SpecRejection(
                        f"arm {arm.name!r} entered from a different opening state than "
                        "its seed baseline"
                    )
                results[(int(seed), arm.name)] = result
                collapse = baseline_collapse_reason(result, arm)
                if collapse is not None:
                    baseline_collapse.append(
                        {
                            "seed": int(seed),
                            "arm": arm.name,
                            "regime": arm.regime,
                            "collapsed_chains": result.collapsed_chains,
                        }
                    )
                    raise RunHalted(collapse)
    except RunHalted as exc:
        failure = {
            "status": "BLOCKED_BASELINE_COLLAPSE" if baseline_collapse else "FAILED",
            "reason": str(exc),
            "baseline_collapse": baseline_collapse,
        }
    finally:
        streams.close()

    gap_rows = {key: axis_gap_rows(result) for key, result in results.items()}
    first_stage = _first_stage(results, selected_seeds, gap_rows)
    contrasts = _contrasts(results, selected_seeds, gap_rows)
    verdicts = _verdicts(results, first_stage, contrasts, selected_seeds, selected_arms)

    per_arm = {
        f"{seed}|{arm}": {
            "seed": seed,
            "arm": arm,
            "quarters": result.quarters,
            "opening_state_digest": result.opening_state_digest,
            "comparison_digest": result.comparison_digest,
            "scientific_digest": result.scientific_digest,
            "final_state_digest": result.final_state_digest,
            "journal_digest": result.journal_digest,
            "window_metrics": result.window_metrics,
            "final_quarter_metrics": result.final_quarter_metrics,
        }
        for (seed, arm), result in sorted(results.items())
    }

    placebo_checks: list[dict[str, Any]] = []
    for placebo, target in spec.placebo_targets():
        for seed in selected_seeds:
            found = results.get((seed, placebo))
            reference = results.get((seed, target))
            if found is None or reference is None:
                placebo_checks.append(
                    {"seed": int(seed), "placebo": placebo, "target": target, "status": "NOT_RUN"}
                )
                continue
            placebo_checks.append(
                {
                    "seed": int(seed),
                    "placebo": placebo,
                    "target": target,
                    "status": "COMPARED",
                    "comparison_digest_equal": (
                        found.comparison_digest == reference.comparison_digest
                    ),
                    "scientific_digest_equal": (
                        found.scientific_digest == reference.scientific_digest
                    ),
                    "final_state_digest_equal": (
                        found.final_state_digest == reference.final_state_digest
                    ),
                    "journal_digest_equal": found.journal_digest == reference.journal_digest,
                    "placebo_comparison_digest": found.comparison_digest,
                    "target_comparison_digest": reference.comparison_digest,
                }
            )

    if failure is not None:
        status = failure["status"]
    elif (
        tuple(selected_seeds) == PREREGISTERED_SEEDS
        and tuple(selected_arms) == PREREGISTERED_ARMS
    ):
        status = "COMPLETED"
    else:
        status = "PARTIAL"

    resources = {
        "wall_seconds": round(time.monotonic() - started, 3),
        "max_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "python": sys.version,
        "platform": platform.platform(),
        "model_usage": "NOT_MEASURED",
        "model_usage_note": (
            "This runner makes no model calls. Token and cost accounting belongs to the "
            "calling orchestration session, not to the simulation."
        ),
        "rows": {
            "trace": streams.trace.rows,
            "journal": streams.journal.rows,
            "organization": streams.organizations.rows,
            "demand": streams.demand.rows,
        },
    }

    summary: dict[str, Any] = {
        "schema_version": PREREGISTERED_SPEC_SCHEMA,
        "phase_id": PREREGISTERED_PHASE_ID,
        "mechanism_id": PREREGISTERED_MECHANISM_ID,
        "study_id": PREREGISTERED_STUDY_ID,
        "status": status,
        "status_reason": failure["reason"]
        if failure
        else (
            "full preregistered design executed"
            if status == "COMPLETED"
            else "seed or arm subset; COMPLETED is reserved for the full 3 seeds x 13 arms"
        ),
        "spec": {
            "path": (
                str(spec_path.relative_to(root))
                if spec_path.is_relative_to(root)
                else str(spec_path)
            ),
            "sha256": spec.digest,
            "card_sha256": spec.card_sha256,
            "scenario_sha256": spec.scenario_sha256,
            "households": spec.households,
            "ticks": spec.ticks,
            "window": list(spec.window),
        },
        "selected": {
            "seeds": [int(value) for value in selected_seeds],
            "arms": list(selected_arms),
        },
        "ticks_executed": sum(len(result.quarters) for result in results.values()),
        "input_identity": input_identity,
        "per_arm": per_arm,
        "first_stage": first_stage,
        "contrasts": contrasts,
        "placebo_checks": placebo_checks,
        "verdicts": verdicts,
        "failure": failure,
        "resources": resources,
    }
    _write_json(output_dir / "results.json", summary)
    gap_axis_keys = {
        (row["commodity"], row["stage"], row["purpose"])
        for rows in gap_rows.values()
        for row in rows
    }
    _write_json(
        output_dir / "gap_summary.json",
        {
            "axes": [list(axis) for axis in sorted(gap_axis_keys)],
            "rows": [row for key in sorted(gap_rows) for row in gap_rows[key]],
        },
    )
    _write_json(output_dir / "input_identity.json", input_identity)
    _write_json(output_dir / "resources.json", resources)
    _write_json(
        output_dir / "account_directory.json",
        {
            "source": "hsm_lab.engine.finance.build_account_directory(opening_state)",
            "entry_fields": ["owner_kind", "owner_id", "currency", "account_kind"],
            "per_seed": [
                {
                    "seed": int(entry["seed"]),
                    "account_count": int(entry["account_count"]),
                    "sha256": str(entry["account_directory_sha256"]),
                    "entries": account_directories.get(int(entry["seed"]), []),
                }
                for entry in input_identity
            ],
        },
    )
    summary["artifacts"] = _artifact_list(output_dir)
    _write_json(output_dir / "manifest.json", {"artifacts": summary["artifacts"], "status": status})
    return summary


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="experiments.hist_enterprise")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC_PATH)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seeds", type=str, default=None)
    parser.add_argument("--arms", type=str, default=None)
    parser.add_argument(
        "--finance-probe",
        action="store_true",
        help=(
            "diagnostic: read the kernel's pre-scaling cash intermediates; this "
            "switches the engine to its H3B bank-lender journal path and changes "
            "the journal digest, so it is never used for a preregistered run"
        ),
    )
    return parser.parse_args(argv)


def _public_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": summary["status"],
        "status_reason": summary["status_reason"],
        "ticks_executed": summary["ticks_executed"],
        "selected": summary["selected"],
        "placebo_checks": summary["placebo_checks"],
        "verdicts": summary["verdicts"],
        "failure": summary["failure"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    seeds = (
        None
        if args.seeds is None
        else tuple(int(value) for value in args.seeds.split(",") if value.strip())
    )
    arms = (
        None
        if args.arms is None
        else tuple(value.strip() for value in args.arms.split(",") if value.strip())
    )
    root = args.root.resolve()
    outputs_root = (root / "outputs").resolve()
    target = args.output_dir if args.output_dir.is_absolute() else (Path.cwd() / args.output_dir)
    if not target.resolve().is_relative_to(outputs_root):
        print(
            _canonical(
                {
                    "status": "REJECTED",
                    "error": f"CLI output directory must be a fresh path under {outputs_root}",
                }
            ).decode("utf-8")
        )
        return 2
    try:
        summary = run_m02_study(
            root,
            output_dir=args.output_dir,
            spec_path=args.spec,
            seeds=seeds,
            arm_names=arms,
            finance_probe=bool(args.finance_probe),
        )
    except SpecRejection as exc:
        print(_canonical({"status": "REJECTED", "error": str(exc)}).decode("utf-8"))
        return 2
    except RunHalted as exc:
        print(_canonical({"status": "HALTED", "error": str(exc)}).decode("utf-8"))
        return 1
    print(_canonical(_public_summary(summary)).decode("utf-8"))
    return 0 if summary["status"] not in ("FAILED", "BLOCKED_BASELINE_COLLAPSE") else 1


if __name__ == "__main__":
    raise SystemExit(main())