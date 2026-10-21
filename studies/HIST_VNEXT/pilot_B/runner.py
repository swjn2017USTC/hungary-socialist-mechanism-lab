"""H4C Pilot B: conditional transmission of four institutional settings.

The study runs two independent, model-generated branch states produced by the
approved H4A initial-state settings and the admitted external forcing pack.
Each branch is deep-copied once per arm; every arm receives the same branch
state, network, forcing and seed.  The only differences are the frozen arm
settings declared in ``spec.json``.

The runner composes the already-reviewed execution bridges:

* D0: ``execute_legacy_trade_tick`` (legacy Treasury prepay reference);
* D1: ``execute_trade_working_capital_tick`` (limited term Treasury loan);
* D2: ``execute_export_receivables_tick`` (contract receivables);
* D3: ``execute_cmea_clearing_tick`` (bilateral CMEA clearing).

It never mutates a source scenario, approval, regime or artifact.  The branch
state is **not** a historical state.  No target or sealed-window value is read.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import platform
import resource
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

# Running this file as a script puts ``studies/HIST_VNEXT/pilot_B`` first on
# sys.path.  The two H4A helpers live under the repository's ``history``
# package, so bind the repository root explicitly before importing them.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from history.HIST_VNEXT.h4_sources.experiment_admission import (
    audit_experiment_admission,
)
from history.HIST_VNEXT.h4_sources.runtime_adapter import _apply_setting
from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.contract.material import MaterialParameters
from hsm_lab.contract.schemas import Quarter
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
from hsm_lab.engine.state import (
    MaterialForcing,
    MaterialState,
    MaterialTickFlows,
    capture_material_stocks,
    initialize_material,
)
from hsm_lab.institutions.cmea_clearing_adapter import (
    CmeaClearingEventSpec,
    CmeaClearingRegime,
    execute_cmea_clearing_tick,
)
from hsm_lab.institutions.export_finance_adapter import (
    execute_legacy_trade_tick,
    load_legacy_trade_regime,
)
from hsm_lab.institutions.export_receivables_adapter import (
    ExportReceivableEventSpec,
    ExportReceivablesRegime,
    execute_export_receivables_tick,
)
from hsm_lab.institutions.trade_working_capital_adapter import (
    TradeWorkingCapitalBook,
    TradeWorkingCapitalRegime,
    execute_trade_working_capital_tick,
)
from hsm_lab.provenance.manifest import canonical_digest

SCHEMA_VERSION = "hist_vnext_h4c_pilot_b_v1"
DEFAULT_SPEC = Path("studies/HIST_VNEXT/pilot_B/spec.json")
PRICE_INDEX_VERSION = "h4c-price-index-v1"
GATE_TOLERANCE = 1e-6
_EPS = 1e-9

_ARMS = (
    "base",
    "s",
    "w",
    "sw",
    "r",
    "sr",
    "c",
    "sc",
    "placebo",
    "usd_limit_probe",
    "s_envelope50",
    "w_term2",
    "r_term2",
    "r_receipt_delay2",
    "c_quota20",
    "c_price_half",
    "c_price_high",
    "c_term2",
    "p_fixed",
    "p_spot",
)

_NOT_RUN = (
    {
        "id": "D1+D2",
        "status": "REDESIGN",
        "reason": "tick_material rejects D1 and D2 in one active tick",
    },
    {
        "id": "D1+D3",
        "status": "REDESIGN",
        "reason": "D1 and D3 adapters each require the other to be switched off",
    },
    {
        "id": "D2+D3",
        "status": "REDESIGN",
        "reason": "tick_material rejects D2 and D3 in one active tick",
    },
    {
        "id": "all_four_active",
        "status": "REDESIGN",
        "reason": "no supported joint execution interface exists",
    },
    {
        "id": "d3_dynamic_contract_repricing",
        "status": "NOT_IMPLEMENTED",
        "reason": "D3 contract price is frozen in the persisted regime",
    },
    {
        "id": "d2_import_obligation_extinguishment",
        "status": "NOT_IMPLEMENTED",
        "reason": "D3 exposes settle_export only; import obligations are retained",
    },
    {
        "id": "formal_rollover",
        "status": "NOT_IMPLEMENTED",
        "reason": "D1 blocks replacement draws on a maturity tick",
    },
    {
        "id": "f2_new_usd_external_financing",
        "status": "REDESIGN",
        "reason": "COMMODITY_INDEX misses every g01..g16 id, so desired_usd_outlay is 0",
    },
    {
        "id": "price_subsidy_for_imports",
        "status": "NOT_RUN",
        "reason": "S is a Treasury bailout of existing arrears, not an import price subsidy",
    },
    {
        "id": "per_contract_heterogeneous_terms",
        "status": "NOT_RUN",
        "reason": "one frozen term per D2/D3 regime and one D1 facility",
    },
    {
        "id": "1977_1978_execution",
        "status": "NOT_RUN",
        "reason": "the study window ends at 1976Q4",
    },
)


class PilotTickFailure(RuntimeError):
    """A post-mutation pilot failure; the runner stops instead of falling back."""

    def __init__(self, message: str, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.detail = dict(detail or {})


# ---------------------------------------------------------------------------
# Small deterministic helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_array(array: np.ndarray) -> str:
    value = np.asarray(array, dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(str(value.shape).encode("ascii"))
    digest.update(np.nan_to_num(value, nan=0.0).tobytes())
    digest.update(np.isnan(value).tobytes())
    return digest.hexdigest()


def _clean(value: Any) -> Any:
    """Make a value strict-JSON representable (NaN/Inf -> null)."""
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, np.ndarray):
        return _clean(value.tolist())
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _json_default(value: Any) -> Any:
    return _clean(value)


def _dump_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(_clean(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _resolve_inside(root: Path, value: Path, *, label: str) -> Path:
    path = Path(value)
    resolved = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not resolved.is_relative_to(root):
        raise ConfigError(f"{label} escapes the repository: {value}")
    return resolved


def _resolve_output(root: Path, value: Path) -> Path:
    path = Path(value)
    resolved = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not resolved.is_relative_to(root):
        raise ConfigError(f"output directory escapes the repository: {value}")
    if resolved.exists():
        raise ConfigError(f"output directory already exists: {resolved}")
    return resolved


def _quarter_ordinal(value: str) -> int:
    return Quarter.parse(value).to_ordinal()


def _require_consecutive(labels: Sequence[str], *, label: str) -> None:
    for left, right in zip(labels, labels[1:], strict=False):
        if _quarter_ordinal(right) != _quarter_ordinal(left) + 1:
            raise ConfigError(f"{label} is not a strictly adjacent quarter grid at {left}->{right}")


# ---------------------------------------------------------------------------
# Spec and arm definitions
# ---------------------------------------------------------------------------


def _expected_arms() -> list[dict[str, Any]]:
    return [
        {
            "name": "base",
            "mechanism": "D0",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "research",
            "price_level": None,
            "term_quarters": None,
            "credit_limit": None,
            "quota": None,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "s",
            "mechanism": "D0",
            "bailout_envelope_fraction": 0.25,
            "price_rule": "research",
            "price_level": None,
            "term_quarters": None,
            "credit_limit": None,
            "quota": None,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "w",
            "mechanism": "D1",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "research",
            "price_level": None,
            "term_quarters": 1,
            "credit_limit": 4.0,
            "quota": None,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "sw",
            "mechanism": "D1",
            "bailout_envelope_fraction": 0.25,
            "price_rule": "research",
            "price_level": None,
            "term_quarters": 1,
            "credit_limit": 4.0,
            "quota": None,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "r",
            "mechanism": "D2",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "research",
            "price_level": None,
            "term_quarters": 1,
            "credit_limit": None,
            "quota": None,
            "receipt_delay_quarters": 0,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "sr",
            "mechanism": "D2",
            "bailout_envelope_fraction": 0.25,
            "price_rule": "research",
            "price_level": None,
            "term_quarters": 1,
            "credit_limit": None,
            "quota": None,
            "receipt_delay_quarters": 0,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "c",
            "mechanism": "D3",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "research",
            "price_level": 1.0,
            "term_quarters": 1,
            "credit_limit": None,
            "quota": 10.0,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "sc",
            "mechanism": "D3",
            "bailout_envelope_fraction": 0.25,
            "price_rule": "research",
            "price_level": 1.0,
            "term_quarters": 1,
            "credit_limit": None,
            "quota": 10.0,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "placebo",
            "mechanism": "D0",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "research",
            "price_level": None,
            "term_quarters": None,
            "credit_limit": None,
            "quota": None,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "usd_limit_probe",
            "mechanism": "D0",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "research",
            "price_level": None,
            "term_quarters": None,
            "credit_limit": None,
            "quota": None,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 4.0,
        },
        {
            "name": "s_envelope50",
            "mechanism": "D0",
            "bailout_envelope_fraction": 0.5,
            "price_rule": "research",
            "price_level": None,
            "term_quarters": None,
            "credit_limit": None,
            "quota": None,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "w_term2",
            "mechanism": "D1",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "research",
            "price_level": None,
            "term_quarters": 2,
            "credit_limit": 4.0,
            "quota": None,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "r_term2",
            "mechanism": "D2",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "research",
            "price_level": None,
            "term_quarters": 2,
            "credit_limit": None,
            "quota": None,
            "receipt_delay_quarters": 0,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "r_receipt_delay2",
            "mechanism": "D2",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "research",
            "price_level": None,
            "term_quarters": 1,
            "credit_limit": None,
            "quota": None,
            "receipt_delay_quarters": 2,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "c_quota20",
            "mechanism": "D3",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "research",
            "price_level": 1.0,
            "term_quarters": 1,
            "credit_limit": None,
            "quota": 20.0,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "c_price_half",
            "mechanism": "D3",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "research",
            "price_level": 0.5,
            "term_quarters": 1,
            "credit_limit": None,
            "quota": 10.0,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "c_price_high",
            "mechanism": "D3",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "research",
            "price_level": 1.5,
            "term_quarters": 1,
            "credit_limit": None,
            "quota": 10.0,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "c_term2",
            "mechanism": "D3",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "research",
            "price_level": 1.0,
            "term_quarters": 2,
            "credit_limit": None,
            "quota": 10.0,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "p_fixed",
            "mechanism": "D0",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "fixed",
            "price_level": 1.0,
            "term_quarters": None,
            "credit_limit": None,
            "quota": None,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
        {
            "name": "p_spot",
            "mechanism": "D0",
            "bailout_envelope_fraction": 0.0,
            "price_rule": "spot",
            "price_level": None,
            "term_quarters": None,
            "credit_limit": None,
            "quota": None,
            "receipt_delay_quarters": None,
            "convertible_loan_limit": 0.0,
        },
    ]


def _load_spec(root: Path, spec_path: Path) -> tuple[dict[str, Any], Path]:
    spec_file = _resolve_inside(root, spec_path, label="spec")
    try:
        config = json.loads(spec_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"spec is unreadable: {exc}") from exc
    if not isinstance(config, dict):
        raise ConfigError("spec must decode to a JSON object")
    if config.get("schema_version") != SCHEMA_VERSION:
        raise ConfigError(f"spec schema_version must be {SCHEMA_VERSION!r}")
    if config.get("arms") != _expected_arms():
        raise ConfigError("spec arms do not match the frozen H4C arm definitions")
    if tuple(config.get("arms_declared", ())) != _ARMS:
        raise ConfigError(f"spec arms_declared must be exactly {list(_ARMS)!r}")
    episodes = config.get("episodes")
    if not isinstance(episodes, list) or len(episodes) != 2:
        raise ConfigError("spec must declare exactly two episodes")
    expected_episodes = (
        ("pre75", 64, "1973Q1", "1974Q4"),
        ("post75", 72, "1975Q1", "1976Q4"),
    )
    for episode, expected in zip(episodes, expected_episodes, strict=True):
        if not isinstance(episode, dict):
            raise ConfigError("each episode must be an object")
        if (
            episode.get("episode_id"),
            episode.get("warmup_ticks"),
            episode.get("start_quarter"),
            episode.get("end_quarter"),
        ) != expected:
            raise ConfigError(f"episode declaration does not match {expected!r}")
    if int(config.get("ticks", 0)) != 80:
        raise ConfigError("spec ticks must be 80 (1957Q1..1976Q4)")
    if str(config.get("commodity_id")) != "g02_oil_gas_fuels":
        raise ConfigError("spec commodity_id must be g02_oil_gas_fuels")
    if float(config.get("quarterly_trade_request", 0.0)) != 2.0:
        raise ConfigError("spec quarterly_trade_request must be 2")
    if float(config.get("cmea_credit_envelope", 0.0)) != 10.0:
        raise ConfigError("spec cmea_credit_envelope must be 10")
    return config, spec_file


# ---------------------------------------------------------------------------
# Parameters and forcing
# ---------------------------------------------------------------------------


def _g02_index(network: Any) -> int:
    try:
        return tuple(network.commodity_ids).index("g02_oil_gas_fuels")
    except ValueError as exc:  # pragma: no cover - scenario gate
        raise ConfigError("network has no g02_oil_gas_fuels") from exc


def _parameters(
    scenario: Any,
    *,
    commodity_ids: Sequence[str],
    bailout_envelope_fraction: float,
    convertible_loan_limit: float,
    trade_requests: bool,
) -> MaterialParameters:
    parameters = scenario.material_parameters
    if parameters is None:  # pragma: no cover - scenario gate
        raise ConfigError("scenario has no material parameters")
    payload = parameters.model_dump(mode="python")
    trade = payload["trade"]
    vector_names = (
        "cmea_desired_imports",
        "convertible_desired_imports",
        "cmea_export_demands",
        "convertible_export_demands",
    )
    size = len(commodity_ids)
    for name in vector_names:
        trade[name] = [0.0] * size
    if trade_requests:
        try:
            index = tuple(commodity_ids).index("g02_oil_gas_fuels")
        except ValueError as exc:  # pragma: no cover - scenario gate
            raise ConfigError("commodity axis has no g02_oil_gas_fuels") from exc
        for name in vector_names:
            trade[name][index] = 2.0
    trade["cmea_credit_envelope"] = 10.0
    trade["convertible_loan_limit"] = float(convertible_loan_limit)
    payload["bailout_envelope_fraction"] = float(bailout_envelope_fraction)
    return MaterialParameters.model_validate(payload)


def _anchor_tick(forcing: MaterialForcing) -> int:
    try:
        return list(forcing.quarters).index("1975Q1")
    except ValueError as exc:
        raise ConfigError("forcing has no 1975Q1 anchor") from exc


def _validate_forcing_window(
    forcing: MaterialForcing,
    *,
    start_tick: int,
    window_ticks: int,
    anchor_tick: int,
) -> None:
    stop = start_tick + window_ticks
    if stop > len(forcing.quarters):
        raise ConfigError("episode window exceeds the forcing horizon")
    labels = forcing.quarters[start_tick:stop]
    _require_consecutive(labels, label="episode forcing window")
    if not np.isfinite(forcing.oil_price[start_tick:stop]).all():
        raise ConfigError("episode window has a non-finite oil price")
    if not np.isfinite(forcing.global_usd_rate[start_tick:stop]).all():
        raise ConfigError("episode window has a non-finite USD rate")
    raw = np.asarray(forcing.cmea_energy_price, dtype=np.float64)
    if not np.isnan(raw[:anchor_tick]).all():
        raise ConfigError("raw CMEA quotes before 1975Q1 must be NaN")
    if raw[anchor_tick] <= 0.0 or not np.isfinite(raw[anchor_tick]):
        raise ConfigError("the 1975Q1 CMEA anchor must be finite and positive")
    if start_tick < anchor_tick:
        if not np.isnan(raw[start_tick:stop]).all():
            raise ConfigError("pre-1975 episode window must carry no reconstructed CMEA quote")
    elif not np.isfinite(raw[start_tick:stop]).all():
        raise ConfigError("post-1975 episode window has a missing CMEA quote")


def _model_forcing(
    raw: MaterialForcing,
    *,
    arm: dict[str, Any],
    world_oil_reference: float,
    anchor_tick: int,
) -> MaterialForcing:
    rule = str(arm["price_rule"])
    values = np.full_like(raw.cmea_energy_price, np.nan, dtype=np.float64)
    if rule == "research":
        anchor_value = float(raw.cmea_energy_price[anchor_tick])
        if not math.isfinite(anchor_value) or anchor_value <= 0.0:
            raise ConfigError("CMEA research-price anchor is not positive")
        values[anchor_tick:] = (
            np.asarray(raw.cmea_energy_price[anchor_tick:], dtype=np.float64) / anchor_value
        )
    elif rule == "fixed":
        level = arm.get("price_level")
        if level is None:
            raise ConfigError(f"arm {arm['name']!r} lacks a fixed price level")
        values[:] = float(level)
    elif rule == "spot":
        values = np.asarray(raw.oil_price, dtype=np.float64) / float(world_oil_reference)
    else:  # pragma: no cover - spec gate
        raise ConfigError(f"unknown price rule {rule!r}")
    if not np.isfinite(values).all() and rule != "research":
        raise ConfigError(f"price rule {rule!r} produced a non-finite CMEA series")
    return MaterialForcing(
        quarters=list(raw.quarters),
        oil_price=np.asarray(raw.oil_price, dtype=np.float64),
        global_usd_rate=np.asarray(raw.global_usd_rate, dtype=np.float64),
        official_fx=np.asarray(raw.official_fx, dtype=np.float64),
        cmea_energy_price=values,
        segment=list(raw.segment),
        input_artifact_hashes=dict(raw.input_artifact_hashes),
    )


# ---------------------------------------------------------------------------
# Regimes and events
# ---------------------------------------------------------------------------


def _d1_regime(arm: dict[str, Any], *, start_tick: int) -> TradeWorkingCapitalRegime:
    return TradeWorkingCapitalRegime(
        schema_version="hist-trade-working-capital-regime-v1",
        regime_id="limited_trade_working_capital",
        source_kind="synthetic",
        bank_index=0,
        credit_limit=float(arm["credit_limit"] or 0.0),
        annual_rate=0.04,
        term_quarters=int(arm["term_quarters"] or 1),
        draw_tick_start=int(start_tick),
        draw_tick_end=int(start_tick),
    )


def _d2_regime(arm: dict[str, Any]) -> ExportReceivablesRegime:
    return ExportReceivablesRegime(
        schema_version="hist-export-receivables-regime-v1",
        regime_id="export_receivables",
        source_kind="synthetic",
        term_quarters=int(arm["term_quarters"] or 1),
        contracts=(
            {
                "contract_id": "h4c-usd-fuel",
                "currency": "USD",
                "buyer_id": 9101,
                "seller_id": 0,
                "commodity_id": "g02_oil_gas_fuels",
            },
            {
                "contract_id": "h4c-cmea-fuel",
                "currency": "cmea_settlement_unit",
                "buyer_id": 9102,
                "seller_id": 0,
                "commodity_id": "g02_oil_gas_fuels",
            },
        ),
    )


def _d3_regime(arm: dict[str, Any]) -> CmeaClearingRegime:
    level = float(arm["price_level"] or 1.0)
    return CmeaClearingRegime(
        schema_version="hist-cmea-clearing-regime-v1",
        regime_id="cmea_clearing",
        source_kind="synthetic",
        term_quarters=int(arm["term_quarters"] or 1),
        clearing_group=(9201,),
        counterparties=({"counterparty_id": 9201, "credit_limit": float(arm["quota"] or 0.0)},),
        contracts=(
            {
                "contract_id": "h4c-cmea-import",
                "counterparty_id": 9201,
                "direction": "import",
                "commodity_id": "g02_oil_gas_fuels",
                "price": level,
            },
            {
                "contract_id": "h4c-cmea-export",
                "counterparty_id": 9201,
                "direction": "export",
                "commodity_id": "g02_oil_gas_fuels",
                "price": level,
            },
        ),
    )


def _d2_events(
    state: MaterialState,
    *,
    episode_id: str,
    arm_name: str,
    receipt_delay_quarters: int,
) -> tuple[ExportReceivableEventSpec, ...]:
    tick = int(state.completed_ticks)
    events: list[ExportReceivableEventSpec] = []
    for lot in sorted(state.export_receivables, key=lambda item: item.receivable_id):
        if float(lot.gross) <= _EPS:
            continue
        if tick < int(lot.due_tick) + int(receipt_delay_quarters):
            continue
        events.append(
            ExportReceivableEventSpec(
                event_id=f"h4c:{episode_id}:{arm_name}:receipt:{lot.receivable_id}:{tick}",
                tick=tick,
                kind="receipt",
                receivable_id=lot.receivable_id,
                contract_id=lot.contract_id,
                currency=lot.currency,
                buyer_id=int(lot.buyer_id),
                seller_id=int(lot.seller_id),
                amount=float(lot.gross),
            )
        )
    return tuple(events)


def _d3_events(
    state: MaterialState,
    *,
    episode_id: str,
    arm_name: str,
) -> tuple[CmeaClearingEventSpec, ...]:
    tick = int(state.completed_ticks)
    events: list[CmeaClearingEventSpec] = []
    for entry in sorted(state.cmea_clearing_entries, key=lambda item: item.entry_id):
        if entry.direction != "export":
            continue
        outstanding = float(entry.amount) - float(entry.settled)
        if outstanding <= _EPS:
            continue
        if tick < int(entry.due_tick):
            continue
        events.append(
            CmeaClearingEventSpec(
                event_id=f"h4c:{episode_id}:{arm_name}:settle_export:{entry.entry_id}:{tick}",
                tick=tick,
                kind="settle_export",
                entry_id=entry.entry_id,
                amount=outstanding,
            )
        )
    return tuple(events)


# ---------------------------------------------------------------------------
# Execution and trace
# ---------------------------------------------------------------------------


def _restore_state(state: MaterialState, snapshot: MaterialState) -> None:
    for field_name in state.__dataclass_fields__:
        setattr(state, field_name, copy.deepcopy(getattr(snapshot, field_name)))


def _require_gate(gate: Any, *, phase: str) -> None:
    if (
        float(gate.max_material_abs_residual) >= GATE_TOLERANCE
        or float(gate.max_finance_abs_residual) >= GATE_TOLERANCE
    ):
        raise PilotTickFailure(
            f"{phase} failed the invariant gate",
            detail={
                "max_material_abs_residual": float(gate.max_material_abs_residual),
                "max_finance_abs_residual": float(gate.max_finance_abs_residual),
            },
        )


def _execute_arm_tick(
    *,
    arm: dict[str, Any],
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: MaterialParameters,
    network: Any,
    book: TradeWorkingCapitalBook | None,
    episode_id: str,
    d0_regime: Any,
    d1_regime: TradeWorkingCapitalRegime | None,
    d2_regime: ExportReceivablesRegime | None,
    d3_regime: CmeaClearingRegime | None,
) -> tuple[MaterialTickFlows, Any, TradeWorkingCapitalBook | None, dict[str, Any]]:
    mechanism = str(arm["mechanism"])
    name = str(arm["name"])
    if mechanism == "D0":
        result = execute_legacy_trade_tick(
            state, forcing, parameters, network, regime=d0_regime
        )
        return result.flows, result.gate, book, result.observation
    if mechanism == "D1":
        assert d1_regime is not None
        result = execute_trade_working_capital_tick(
            state,
            forcing,
            parameters,
            network,
            regime=d1_regime,
            book=book,
        )
        return result.flows, result.gate, result.book, result.observation
    if mechanism == "D2":
        assert d2_regime is not None
        events = _d2_events(
            state,
            episode_id=episode_id,
            arm_name=name,
            receipt_delay_quarters=int(arm["receipt_delay_quarters"] or 0),
        )
        result = execute_export_receivables_tick(
            state,
            forcing,
            parameters,
            network,
            regime=d2_regime,
            events=events,
        )
        return result.flows, result.gate, book, result.observation
    if mechanism == "D3":
        assert d3_regime is not None
        events = _d3_events(state, episode_id=episode_id, arm_name=name)
        result = execute_cmea_clearing_tick(
            state,
            forcing,
            parameters,
            network,
            regime=d3_regime,
            events=events,
        )
        return result.flows, result.gate, book, result.observation
    raise ConfigError(f"unknown mechanism {mechanism!r}")


def _observation_subset(mechanism: str, observation: dict[str, Any]) -> dict[str, Any]:
    if mechanism == "D0":
        return {
            "identity_residuals": observation.get("identity_residuals"),
            "official_fx_translation": observation.get("official_fx_translation"),
        }
    if mechanism == "D1":
        return {
            key: observation.get(key)
            for key in (
                "draw",
                "draw_sizing",
                "service",
                "scheduled_batches",
                "matured_this_tick",
                "export_outlay",
                "identity_residuals",
                "limit_remaining",
                "loan_principal_open",
                "loan_principal_close",
                "interest_arrears_open",
                "interest_arrears_close",
                "account_ids",
            )
        }
    if mechanism == "D2":
        return {
            key: observation.get(key)
            for key in (
                "events",
                "due",
                "overdue",
                "flow_scalars",
                "identity_residuals",
                "account_ids",
            )
        }
    return {
        key: observation.get(key)
        for key in (
            "events",
            "due",
            "overdue",
            "positions",
            "flow_scalars",
            "account_ids",
        )
    }


def _journal_summary(flows: MaterialTickFlows) -> dict[str, Any]:
    kind_counts = Counter(str(kind) for kind in flows.journal_kind)
    currency_totals: dict[str, dict[str, float]] = {}
    for kind, currency, amount in zip(
        flows.journal_kind,
        flows.journal_currency,
        flows.journal_amount,
        strict=True,
    ):
        bucket = currency_totals.setdefault(str(kind), {})
        bucket[str(currency)] = bucket.get(str(currency), 0.0) + float(amount)
    rows = [
        [
            str(flows.journal_kind[index]),
            int(flows.journal_tick[index]),
            int(flows.journal_debit[index]),
            int(flows.journal_credit[index]),
            str(flows.journal_currency[index]),
            float(flows.journal_amount[index]),
            None if flows.journal_org[index] is None else int(flows.journal_org[index]),
            int(flows.journal_leg[index]),
            flows.journal_event[index],
        ]
        for index in range(len(flows.journal_kind))
    ]
    digest = hashlib.sha256(
        json.dumps(rows, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return {
        "rows": len(rows),
        "sha256": digest,
        "kind_counts": dict(sorted(kind_counts.items())),
        "kind_currency_totals": {
            kind: dict(sorted(bucket.items()))
            for kind, bucket in sorted(currency_totals.items())
        },
    }


def _commodity_outcomes(
    state: MaterialState,
    flows: MaterialTickFlows,
    network: Any,
) -> dict[str, dict[str, float]]:
    commodity_ids = tuple(str(value) for value in network.commodity_ids)
    g_count = len(commodity_ids)
    cell_commodity = np.asarray(network.cell_commodity, dtype=np.int64)
    demand_cell = np.asarray(network.demand_cell, dtype=np.int64)
    output_by_cell = np.asarray(network.B.transpose().dot(flows.activity_realized)).ravel()
    production = np.bincount(
        cell_commodity, weights=np.maximum(output_by_cell, 0.0), minlength=g_count
    )
    stock_close = np.bincount(
        cell_commodity,
        weights=np.maximum(np.asarray(state.stock_value, dtype=np.float64), 0.0),
        minlength=g_count,
    )
    household_realized = np.asarray(flows.household_realized, dtype=np.float64).sum(axis=0)
    availability_unmet = np.asarray(
        flows.household_availability_unmet, dtype=np.float64
    ).sum(axis=0)
    budget_unmet = np.asarray(flows.household_budget_unmet, dtype=np.float64).sum(axis=0)
    cmea_imports = np.asarray(flows.cmea_imports, dtype=np.float64)
    convertible_imports = np.asarray(flows.convertible_imports, dtype=np.float64)
    cmea_exports = np.asarray(flows.cmea_exports, dtype=np.float64)
    convertible_exports = np.asarray(flows.convertible_exports, dtype=np.float64)

    # Demand cells with a real destination group by the destination's
    # commodity.  Export demand cells have destination -1, so map each of the
    # two export channels explicitly instead of indexing the last stock cell.
    export_map: dict[int, int] = {}
    export_cells = np.asarray(network.export_demand_cell, dtype=np.int64)
    for channel in range(export_cells.shape[0]):
        for g, cell in enumerate(export_cells[channel]):
            if int(cell) >= 0:
                export_map[int(cell)] = g

    def demand_by_commodity(values: Any) -> np.ndarray:
        array = np.asarray(values, dtype=np.float64)
        grouped = np.zeros(g_count, dtype=np.float64)
        valid = demand_cell >= 0
        np.add.at(grouped, cell_commodity[demand_cell[valid]], array[valid])
        for cell, g in export_map.items():
            grouped[g] += float(array[cell])
        return grouped

    desired = demand_by_commodity(flows.desired)
    ordered = demand_by_commodity(flows.ordered)
    delivered = demand_by_commodity(flows.delivered)
    used = demand_by_commodity(flows.used)
    physical_blocked = demand_by_commodity(flows.physical_delivery_blocked)
    financial_blocked = demand_by_commodity(flows.financial_delivery_blocked)

    result: dict[str, dict[str, float]] = {}
    for index, commodity_id in enumerate(commodity_ids):
        result[commodity_id] = {
            "production": float(production[index]),
            "desired": float(desired[index]),
            "ordered": float(ordered[index]),
            "delivered": float(delivered[index]),
            "used": float(used[index]),
            "physical_delivery_blocked": float(physical_blocked[index]),
            "financial_delivery_blocked": float(financial_blocked[index]),
            "imports": float(cmea_imports[index] + convertible_imports[index]),
            "cmea_imports": float(cmea_imports[index]),
            "convertible_imports": float(convertible_imports[index]),
            "exports": float(cmea_exports[index] + convertible_exports[index]),
            "cmea_exports": float(cmea_exports[index]),
            "convertible_exports": float(convertible_exports[index]),
            "household_realized": float(household_realized[index]),
            "household_availability_unmet": float(availability_unmet[index]),
            "household_budget_unmet": float(budget_unmet[index]),
            "stock_close": float(stock_close[index]),
        }
    return result


def _household_by_region(
    state: MaterialState,
    flows: MaterialTickFlows,
    network: Any,
) -> dict[str, dict[str, list[float]]]:
    regions = tuple(str(value) for value in network.region_ids)
    region_axis = np.asarray(state.household_region, dtype=np.int64)
    realized = np.asarray(flows.household_realized, dtype=np.float64)
    availability = np.asarray(flows.household_availability_unmet, dtype=np.float64)
    budget = np.asarray(flows.household_budget_unmet, dtype=np.float64)
    commodity_ids = tuple(str(value) for value in network.commodity_ids)
    result: dict[str, dict[str, list[float]]] = {}
    for index, region in enumerate(regions):
        result[region] = {}
        for g, commodity_id in enumerate(commodity_ids):
            result[region][commodity_id] = [
                float(np.sum(realized[region_axis == index, g])),
                float(np.sum(availability[region_axis == index, g])),
                float(np.sum(budget[region_axis == index, g])),
            ]
    return result


def _book_summary(book: TradeWorkingCapitalBook | None) -> dict[str, Any] | None:
    if book is None:
        return None
    return {
        "bank_index": int(book.bank_index),
        "principal": float(book.principal),
        "interest_arrears": float(book.interest_arrears),
        "batches": [
            {
                "draw_tick": int(batch.draw_tick),
                "maturity_tick": int(batch.maturity_tick),
                "principal": float(batch.principal),
                "annual_rate": float(batch.annual_rate),
            }
            for batch in book.batches
        ],
    }


def _state_summary(
    state: MaterialState,
    *,
    book: TradeWorkingCapitalBook | None,
) -> dict[str, Any]:
    return {
        "completed_ticks": int(state.completed_ticks),
        "treasury_deposit": float(state.treasury_deposit),
        "treasury_loan_asset": float(state.treasury_loan_asset),
        "credit_fund": float(state.credit_fund),
        "usd_reserve": float(state.usd_reserve),
        "usd_principal": float(state.usd_principal),
        "usd_interest_arrears": float(state.usd_interest_arrears),
        "cmea_settlement_balance": float(state.cmea_settlement_balance),
        "treasury_loan_principal": float(state.treasury_loan_principal),
        "treasury_interest_arrears": float(state.treasury_interest_arrears),
        "treasury_loan_maturity_tick": float(state.treasury_loan_maturity_tick),
        "treasury_loan_rate": float(state.treasury_loan_rate),
        "bank_reserves": np.asarray(state.bank_reserves, dtype=np.float64).tolist(),
        "bank_loan_asset": np.asarray(state.bank_loan_asset, dtype=np.float64).tolist(),
        "bank_deposit_liability": np.asarray(
            state.bank_deposit_liability, dtype=np.float64
        ).tolist(),
        "bank_equity": np.asarray(state.bank_equity, dtype=np.float64).tolist(),
        "bank_interest_receivable": np.asarray(
            state.bank_interest_receivable, dtype=np.float64
        ).tolist(),
        "organization_cash_total": float(
            np.asarray(state.organization_cash, dtype=np.float64).sum()
        ),
        "organization_wage_arrears_total": float(
            np.asarray(state.organization_wage_arrears, dtype=np.float64).sum()
        ),
        "organization_interest_arrears_total": float(
            np.asarray(state.organization_interest_arrears, dtype=np.float64).sum()
        ),
        "organization_principal_total": float(
            np.asarray(state.organization_principal, dtype=np.float64).sum()
        ),
        "household_cash_total": float(
            np.asarray(state.household_cash, dtype=np.float64).sum()
        ),
        "household_wage_claim_total": float(
            np.asarray(state.household_wage_claim, dtype=np.float64).sum()
        ),
        "d1_book": _book_summary(book),
        "d2_lots": [
            {
                "receivable_id": lot.receivable_id,
                "contract_id": lot.contract_id,
                "currency": lot.currency,
                "buyer_id": int(lot.buyer_id),
                "seller_id": int(lot.seller_id),
                "commodity_id": lot.commodity_id,
                "delivery_tick": int(lot.delivery_tick),
                "due_tick": int(lot.due_tick),
                "gross": float(lot.gross),
                "received": float(lot.received),
                "written_off": float(lot.written_off),
                "outstanding": float(lot.gross),
            }
            for lot in state.export_receivables
        ],
        "d3_accounts": [
            {
                "counterparty_id": int(account.counterparty_id),
                "credit_limit": float(account.credit_limit),
                "balance": float(account.balance),
                "quota_remaining": float(account.credit_limit) + float(account.balance),
            }
            for account in state.cmea_clearing_accounts
        ],
        "d3_entries": [
            {
                "entry_id": entry.entry_id,
                "contract_id": entry.contract_id,
                "counterparty_id": int(entry.counterparty_id),
                "direction": entry.direction,
                "commodity_id": entry.commodity_id,
                "entry_tick": int(entry.entry_tick),
                "due_tick": int(entry.due_tick),
                "quantity": float(entry.quantity),
                "amount": float(entry.amount),
                "settled": float(entry.settled),
                "outstanding": float(entry.amount) - float(entry.settled),
            }
            for entry in state.cmea_clearing_entries
        ],
        "d3_settlements": [
            {
                "event_id": item.event_id,
                "tick": int(item.tick),
                "entry_id": item.entry_id,
                "amount": float(item.amount),
            }
            for item in state.cmea_clearing_settlements
        ],
    }


def _desired_trade(
    parameters: MaterialParameters, network: Any
) -> dict[str, float]:
    index = _g02_index(network)
    trade = parameters.trade
    return {
        "cmea_desired_imports": float(trade.cmea_desired_imports[index]),
        "convertible_desired_imports": float(trade.convertible_desired_imports[index]),
        "cmea_export_demands": float(trade.cmea_export_demands[index]),
        "convertible_export_demands": float(trade.convertible_export_demands[index]),
        "cmea_credit_envelope": float(trade.cmea_credit_envelope),
        "convertible_loan_limit": float(trade.convertible_loan_limit),
    }


def _flow_scalars(flows: MaterialTickFlows) -> dict[str, float]:
    names = (
        "cmea_import_payment",
        "cmea_export_receipt",
        "usd_import_payment",
        "usd_export_receipt",
        "usd_interest_paid",
        "usd_interest_accrued",
        "usd_principal_paid",
        "usd_loan_drawn",
        "treasury_loan_drawn",
        "treasury_principal_paid",
        "treasury_interest_due",
        "treasury_interest_paid",
        "treasury_export_outlay",
        "expired_services",
        "export_receivable_opened_usd",
        "export_receivable_opened_cmea",
        "export_receivable_received_usd",
        "export_receivable_received_cmea",
        "export_receivable_balance_usd",
        "export_receivable_balance_cmea",
        "export_receivable_overdue_usd",
        "export_receivable_overdue_cmea",
        "cmea_clearing_import_payment",
        "cmea_clearing_export_pending",
        "cmea_clearing_export_settled",
    )
    return {name: float(getattr(flows, name)) for name in names}


def _trade_channel_trace(
    flows: MaterialTickFlows, network: Any
) -> dict[str, Any]:
    """The exact g02 demand cells and import channels used by the trade pre-pass."""
    g = _g02_index(network)
    result: dict[str, Any] = {}
    for name, channel in (("cmea_export", 0), ("convertible_export", 1)):
        cell = int(np.asarray(network.export_demand_cell, dtype=np.int64)[channel, g])
        if cell < 0:
            result[name] = {"status": "NO_DEMAND_CELL"}
            continue
        result[name] = {
            "status": "DEMAND_CELL",
            "demand_cell": cell,
            "desired": float(flows.desired[cell]),
            "ordered": float(flows.ordered[cell]),
            "allocated": float(flows.allocated[cell]),
            "delivered": float(flows.delivered[cell]),
            "physical_delivery_blocked": float(
                flows.physical_delivery_blocked[cell]
            ),
            "financial_delivery_blocked": float(
                flows.financial_delivery_blocked[cell]
            ),
        }
    result["cmea_import"] = {
        "quantity": float(flows.cmea_imports[g]),
        "payment": float(flows.cmea_import_payment),
    }
    result["convertible_import"] = {
        "quantity": float(flows.convertible_imports[g]),
        "payment": float(flows.usd_import_payment),
    }
    return result


def _build_trace(
    *,
    episode_id: str,
    arm: dict[str, Any],
    state: MaterialState,
    flows: MaterialTickFlows,
    gate: Any,
    observation: dict[str, Any],
    book: TradeWorkingCapitalBook | None,
    network: Any,
    parameters: MaterialParameters,
    raw_forcing: MaterialForcing,
    model_forcing: MaterialForcing,
) -> dict[str, Any]:
    tick = int(flows.tick)
    return {
        "episode_id": episode_id,
        "arm": str(arm["name"]),
        "mechanism": str(arm["mechanism"]),
        "price_rule": str(arm["price_rule"]),
        "tick": tick,
        "quarter": str(flows.quarter),
        "forcing": {
            "oil_price": float(raw_forcing.oil_price[tick]),
            "global_usd_rate": float(raw_forcing.global_usd_rate[tick]),
            "raw_cmea_quote": float(raw_forcing.cmea_energy_price[tick]),
            "model_cmea_price": float(model_forcing.cmea_energy_price[tick]),
            "segment": str(raw_forcing.segment[tick]),
            "price_index_version": PRICE_INDEX_VERSION,
        },
        "desired_trade": _desired_trade(parameters, network),
        "trade_channels": _trade_channel_trace(flows, network),
        "scalars": _flow_scalars(flows),
        "bailout": {
            "requested": float(
                np.asarray(flows.organization_bailout_requested, dtype=np.float64).sum()
            ),
            "granted": float(
                np.asarray(flows.organization_bailout_granted, dtype=np.float64).sum()
            ),
            "granted_by_organization": {
                str(int(index)): float(value)
                for index, value in enumerate(flows.organization_bailout_granted)
                if float(value) > 0.0
            },
        },
        "outcomes": _commodity_outcomes(state, flows, network),
        "household_by_region": _household_by_region(state, flows, network),
        "journal": _journal_summary(flows),
        "observation": _observation_subset(str(arm["mechanism"]), observation),
        "state": _state_summary(state, book=book),
        "gate": {
            "max_material_abs_residual": float(gate.max_material_abs_residual),
            "max_finance_abs_residual": float(gate.max_finance_abs_residual),
        },
    }


# ---------------------------------------------------------------------------
# Journal parquet
# ---------------------------------------------------------------------------


class _JournalWriter:
    def __init__(self, path: Path) -> None:
        import pyarrow as pa

        self._pa = pa
        self._path = path
        self._schema = pa.schema(
            [
                ("episode_id", pa.string()),
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
        self._writer: Any = None
        self.rows = 0

    def write(
        self,
        flows: MaterialTickFlows,
        *,
        episode_id: str,
        arm: str,
    ) -> None:
        import pyarrow.parquet as pq

        count = len(flows.journal_kind)
        if count == 0:
            return
        if self._writer is None:
            self._writer = pq.ParquetWriter(self._path, self._schema)
        pa = self._pa
        table = pa.Table.from_arrays(
            [
                pa.array([episode_id] * count, type=pa.string()),
                pa.array([arm] * count, type=pa.string()),
                pa.array(flows.journal_tick, type=pa.int32()),
                pa.array([str(flows.quarter)] * count, type=pa.string()),
                pa.array(flows.journal_kind, type=pa.string()),
                pa.array(flows.journal_debit, type=pa.int32()),
                pa.array(flows.journal_credit, type=pa.int32()),
                pa.array(flows.journal_currency, type=pa.string()),
                pa.array(flows.journal_amount, type=pa.float64()),
                pa.array(flows.journal_org, type=pa.int32()),
                pa.array(flows.journal_leg, type=pa.int32()),
                pa.array(flows.journal_event, type=pa.string()),
            ],
            schema=self._schema,
        )
        self._writer.write_table(table)
        self.rows += count

    def close(self) -> None:
        import pyarrow.parquet as pq

        if self._writer is None:
            table = self._pa.Table.from_arrays(
                [self._pa.array([], type=field.type) for field in self._schema],
                schema=self._schema,
            )
            pq.write_table(table, self._path)
            return
        self._writer.close()


# ---------------------------------------------------------------------------
# Window summaries and episode execution
# ---------------------------------------------------------------------------


def _sum_window(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"status": "NOT_RUN", "ticks": 0}
    commodity_ids = tuple(rows[0]["outcomes"].keys())
    scalar_names = tuple(rows[0]["scalars"].keys())
    commodity_totals: dict[str, dict[str, float]] = {
        commodity_id: {} for commodity_id in commodity_ids
    }
    for commodity_id in commodity_ids:
        fields = tuple(rows[0]["outcomes"][commodity_id].keys())
        commodity_totals[commodity_id] = {
            field: (
                float(rows[-1]["outcomes"][commodity_id][field])
                if field == "stock_close"
                else sum(float(row["outcomes"][commodity_id][field]) for row in rows)
            )
            for field in fields
        }
    scalars = {
        name: sum(float(row["scalars"][name]) for row in rows) for name in scalar_names
    }
    bailout_requested = sum(float(row["bailout"]["requested"]) for row in rows)
    bailout_granted = sum(float(row["bailout"]["granted"]) for row in rows)
    d1_draw = sum(float(row["scalars"]["treasury_loan_drawn"]) for row in rows)
    d1_outlay = sum(float(row["scalars"]["treasury_export_outlay"]) for row in rows)
    d2_opened_usd = sum(float(row["scalars"]["export_receivable_opened_usd"]) for row in rows)
    d2_opened_cmea = sum(float(row["scalars"]["export_receivable_opened_cmea"]) for row in rows)
    d2_received_usd = sum(
        float(row["scalars"]["export_receivable_received_usd"]) for row in rows
    )
    d2_received_cmea = sum(
        float(row["scalars"]["export_receivable_received_cmea"]) for row in rows
    )
    d2_overdue_usd = sum(
        float(row["scalars"]["export_receivable_overdue_usd"]) for row in rows
    )
    d2_overdue_cmea = sum(
        float(row["scalars"]["export_receivable_overdue_cmea"]) for row in rows
    )
    c_import_payment = sum(
        float(row["scalars"]["cmea_clearing_import_payment"]) for row in rows
    )
    c_export_pending = sum(
        float(row["scalars"]["cmea_clearing_export_pending"]) for row in rows
    )
    c_export_settled = sum(
        float(row["scalars"]["cmea_clearing_export_settled"]) for row in rows
    )
    c_imports_g02 = float(
        commodity_totals.get("g02_oil_gas_fuels", {}).get("cmea_imports", 0.0)
    )
    final_state = rows[-1]["state"]
    d3_accounts = final_state.get("d3_accounts", [])
    c_quota_remaining = sum(float(item["quota_remaining"]) for item in d3_accounts)
    c_quota_used = sum(
        float(item["credit_limit"]) - float(item["quota_remaining"])
        for item in d3_accounts
    )
    return {
        "status": "EXECUTED",
        "ticks": len(rows),
        "first_tick": int(rows[0]["tick"]),
        "last_tick": int(rows[-1]["tick"]),
        "first_quarter": rows[0]["quarter"],
        "last_quarter": rows[-1]["quarter"],
        "scalars": scalars,
        "by_commodity": commodity_totals,
        "first_stage": {
            "S_bailout_requested": bailout_requested,
            "S_bailout_granted": bailout_granted,
            "W_treasury_loan_drawn": d1_draw,
            "W_treasury_export_outlay": d1_outlay,
            "R_opened_usd": d2_opened_usd,
            "R_opened_cmea": d2_opened_cmea,
            "R_received_usd": d2_received_usd,
            "R_received_cmea": d2_received_cmea,
            "R_overdue_usd": d2_overdue_usd,
            "R_overdue_cmea": d2_overdue_cmea,
            "C_import_payment": c_import_payment,
            "C_import_quantity_g02": c_imports_g02,
            "C_import_quantity_by_commodity": {
                commodity_id: float(value["cmea_imports"])
                for commodity_id, value in commodity_totals.items()
            },
            "C_quota_remaining": c_quota_remaining,
            "C_quota_used": c_quota_used,
            "C_export_pending": c_export_pending,
            "C_export_settled": c_export_settled,
            "USD_loan_drawn": scalars["usd_loan_drawn"],
            "USD_import_payment": scalars["usd_import_payment"],
        },
        "final_state": final_state,
    }


def _first_stage_nonzero(summary: dict[str, Any], mechanism: str) -> bool:
    if summary.get("status") != "EXECUTED":
        return False
    stage = summary["first_stage"]
    names = {
        "D0": ("C_import_quantity_g02", "USD_import_payment"),
        "D1": ("W_treasury_loan_drawn", "W_treasury_export_outlay"),
        "D2": (
            "R_opened_usd",
            "R_opened_cmea",
            "R_received_usd",
            "R_received_cmea",
        ),
        "D3": (
            "C_import_payment",
            "C_import_quantity_g02",
            "C_export_pending",
            "C_export_settled",
        ),
    }[mechanism]
    return any(abs(float(stage[name])) > _EPS for name in names)


def _arm_summary(
    *,
    arm: dict[str, Any],
    rows: Sequence[dict[str, Any]],
    window_ticks: int,
    final_state_sha256: str,
    book: TradeWorkingCapitalBook | None,
    model_forcing_sha256: str,
) -> dict[str, Any]:
    mechanism = str(arm["mechanism"])
    short_rows = list(rows[:4])
    later_rows = list(rows[4:]) if window_ticks == 8 else []
    short = _sum_window(short_rows)
    later = _sum_window(later_rows)
    with_s = float(arm["bailout_envelope_fraction"]) > 0.0
    s_first_stage = with_s and (
        float(short.get("first_stage", {}).get("S_bailout_granted", 0.0)) > _EPS
        or float(later.get("first_stage", {}).get("S_bailout_granted", 0.0)) > _EPS
    )
    mechanism_first_stage = _first_stage_nonzero(
        short, mechanism
    ) or _first_stage_nonzero(later, mechanism)
    structural_status = (
        "FIRST_STAGE_OBSERVED"
        if mechanism_first_stage or s_first_stage
        else "NULL_FIRST_STAGE"
    )
    trace_digest = hashlib.sha256(
        json.dumps(_clean(list(rows)), separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    comparable_rows = [
        {key: value for key, value in row.items() if key != "arm"} for row in rows
    ]
    comparable_digest = hashlib.sha256(
        json.dumps(
            _clean(comparable_rows), separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    ledger = canonical_digest(
        {
            "state_sha256": final_state_sha256,
            "d1_book": _book_summary(book),
            "d2_event_log": rows[-1]["state"]["d2_lots"],
            "d3_entries": rows[-1]["state"]["d3_entries"],
        }
    )
    return {
        "status": "EXECUTED",
        "mechanism": mechanism,
        "price_rule": str(arm["price_rule"]),
        "model_forcing_sha256": model_forcing_sha256,
        "ticks": len(rows),
        "short_window": short,
        "later_window": later,
        "first_stage_observed": mechanism_first_stage or s_first_stage,
        "mechanism_first_stage_observed": mechanism_first_stage,
        "s_first_stage_observed": s_first_stage,
        "structural_status": structural_status,
        "trace_sha256": trace_digest,
        "comparison_trace_sha256": comparable_digest,
        "final_state_sha256": final_state_sha256,
        "final_ledger_sha256": ledger,
        "tables": {
            "short": short.get("by_commodity"),
            "later": later.get("by_commodity"),
        },
        "final_state": rows[-1]["state"],
    }


def _warm_up(
    *,
    scenario: Any,
    initial: Any,
    network: Any,
    forcing: MaterialForcing,
    parameters: MaterialParameters,
    ticks: int,
) -> MaterialState:
    state = initialize_material(scenario, initial, network)
    for _ in range(int(ticks)):
        opening = capture_material_stocks(state)
        flows = tick_material(state, forcing, parameters, network)
        summary = accounting.check_material_invariants(
            opening, state, flows, parameters, network
        )
        _require_gate(summary, phase="warm-up")
        state.completed_ticks += 1
    if int(state.completed_ticks) != int(ticks):
        raise PilotTickFailure("warm-up did not reach the declared tick")
    return state


def _run_episode(
    *,
    root: Path,
    episode: dict[str, Any],
    scenario: Any,
    network: Any,
    raw_forcing: MaterialForcing,
    base_parameters: MaterialParameters,
    d0_regime: Any,
    anchor_tick: int,
    window_ticks: int,
    arm_names: Sequence[str],
    arm_definitions: dict[str, dict[str, Any]],
    trace_handle: Any,
    journal: _JournalWriter,
    progress: dict[str, Any],
) -> dict[str, Any]:
    episode_id = str(episode["episode_id"])
    start_tick = int(episode["warmup_ticks"])
    initial = build_material_initial_conditions(scenario, RngRegistry(int(scenario.seed)))
    branch = _warm_up(
        scenario=scenario,
        initial=initial,
        network=network,
        forcing=raw_forcing,
        parameters=base_parameters,
        ticks=start_tick,
    )
    branch_sha = hashlib.sha256(canonical_material_bytes(branch)).hexdigest()
    _validate_forcing_window(
        raw_forcing,
        start_tick=start_tick,
        window_ticks=window_ticks,
        anchor_tick=anchor_tick,
    )
    records: dict[str, Any] = {}
    for arm_name in arm_names:
        arm = arm_definitions[arm_name]
        model_forcing = _model_forcing(
            raw_forcing,
            arm=arm,
            world_oil_reference=float(scenario.material_parameters.world_oil_reference),
            anchor_tick=anchor_tick,
        )
        parameters = _parameters(
            scenario,
            commodity_ids=tuple(network.commodity_ids),
            bailout_envelope_fraction=float(arm["bailout_envelope_fraction"]),
            convertible_loan_limit=float(arm["convertible_loan_limit"]),
            trade_requests=True,
        )
        d1_regime = (
            _d1_regime(arm, start_tick=start_tick)
            if arm["mechanism"] == "D1"
            else None
        )
        d2_regime = _d2_regime(arm) if arm["mechanism"] == "D2" else None
        d3_regime = _d3_regime(arm) if arm["mechanism"] == "D3" else None
        state = copy.deepcopy(branch)
        book: TradeWorkingCapitalBook | None = None
        rows: list[dict[str, Any]] = []
        for _ in range(window_ticks):
            progress.update(
                {
                    "episode_id": episode_id,
                    "arm": arm_name,
                    "tick": int(state.completed_ticks),
                }
            )
            quarter = str(raw_forcing.quarters[int(state.completed_ticks)])
            before_state = copy.deepcopy(state)
            before_book = book
            try:
                flows, gate, book_after, observation = _execute_arm_tick(
                    arm=arm,
                    state=state,
                    forcing=model_forcing,
                    parameters=parameters,
                    network=network,
                    book=book,
                    episode_id=episode_id,
                    d0_regime=d0_regime,
                    d1_regime=d1_regime,
                    d2_regime=d2_regime,
                    d3_regime=d3_regime,
                )
                _require_gate(gate, phase=f"{episode_id}/{arm_name}/{quarter}")
                if int(state.completed_ticks) != int(before_state.completed_ticks) + 1:
                    raise PilotTickFailure("executor clock did not advance exactly once")
                trace = _build_trace(
                    episode_id=episode_id,
                    arm=arm,
                    state=state,
                    flows=flows,
                    gate=gate,
                    observation=observation,
                    book=book_after,
                    network=network,
                    parameters=parameters,
                    raw_forcing=raw_forcing,
                    model_forcing=model_forcing,
                )
                journal.write(flows, episode_id=episode_id, arm=arm_name)
            except Exception as exc:  # noqa: BLE001 - restore then stop
                _restore_state(state, before_state)
                book = before_book
                detail = {
                    "episode_id": episode_id,
                    "arm": arm_name,
                    "tick": int(before_state.completed_ticks),
                    "quarter": quarter,
                    "phase": getattr(exc, "phase", None),
                }
                raise PilotTickFailure(
                    f"{episode_id}/{arm_name}/{quarter} failed: {exc}", detail=detail
                ) from exc
            book = book_after
            rows.append(trace)
            trace_handle.write(
                json.dumps(_clean(trace), separators=(",", ":"), ensure_ascii=False)
                + "\n"
            )
            trace_handle.flush()
        final_state_sha = hashlib.sha256(canonical_material_bytes(state)).hexdigest()
        records[arm_name] = _arm_summary(
            arm=arm,
            rows=rows,
            window_ticks=window_ticks,
            final_state_sha256=final_state_sha,
            book=book,
            model_forcing_sha256=_sha256_array(model_forcing.cmea_energy_price),
        )
    placebo = records.get("placebo")
    base = records.get("base")
    if placebo is not None and base is not None:
        if placebo["comparison_trace_sha256"] != base["comparison_trace_sha256"]:
            raise PilotTickFailure(
                f"{episode_id}: placebo trace differs from base",
                detail={"episode_id": episode_id},
            )
        if placebo["final_ledger_sha256"] != base["final_ledger_sha256"]:
            raise PilotTickFailure(
                f"{episode_id}: placebo ledger differs from base",
                detail={"episode_id": episode_id},
            )
    return {
        "episode_id": episode_id,
        "start_tick": start_tick,
        "start_quarter": str(raw_forcing.quarters[start_tick]),
        "end_quarter": str(raw_forcing.quarters[start_tick + window_ticks - 1]),
        "branch_state_sha256": branch_sha,
        "historical_status": "NOT_ESTABLISHED",
        "arms": records,
    }


# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------


def _code_bindings(root: Path, spec_file: Path, forcing_pack: Path) -> dict[str, str]:
    paths = (
        Path(__file__).resolve(),
        spec_file,
        forcing_pack,
        root / "config/scenarios/historical_f2_replay.json",
        root / "config/initial_state/hist_vnext_h4_v1/experiment_inputs.json",
        root / "docs/phases/HIST_VNEXT/H4A-1/EXPERIMENT_INPUT_APPROVAL.json",
        root / "src/hsm_lab/engine/material.py",
        root / "src/hsm_lab/engine/finance.py",
        root / "src/hsm_lab/engine/accounting.py",
        root / "src/hsm_lab/institutions/trade_working_capital_adapter.py",
        root / "src/hsm_lab/institutions/export_receivables_adapter.py",
        root / "src/hsm_lab/institutions/cmea_clearing_adapter.py",
        root / "src/hsm_lab/institutions/export_finance_adapter.py",
        root / "history/HIST_VNEXT/h4_sources/experiment_admission.py",
        root / "history/HIST_VNEXT/h4_sources/runtime_adapter.py",
    )
    return {
        path.relative_to(root).as_posix(): _sha256_file(path)
        for path in paths
    }


def _git_state(root: Path) -> dict[str, Any]:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return {"head": "NOT_MEASURED", "dirty_entries": "NOT_MEASURED"}
    return {"head": head, "dirty_entries": dirty}


def _write_failure_certificate(
    output: Path,
    *,
    exc: BaseException,
    progress: dict[str, Any],
    started_at: str,
) -> None:
    certificate = {
        "schema_version": f"{SCHEMA_VERSION}_failure_certificate",
        "status": "FAILED",
        "started_at": started_at,
        "failed_at": datetime.now(UTC).isoformat(),
        "error_type": type(exc).__name__,
        "error": str(exc),
        "progress": _clean(progress),
        "resources": {
            "max_rss": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            "platform": platform.platform(),
        },
        "note": "partial traces/journal may remain; never reuse this output directory",
    }
    _dump_json(output / "FAILURE_CERTIFICATE.json", certificate)


def run_pilot(
    root: Path,
    *,
    spec_path: Path = DEFAULT_SPEC,
    output_dir: Path,
    window_ticks: int = 4,
    arms_override: Sequence[str] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    started_at = datetime.now(UTC).isoformat()
    config, spec_file = _load_spec(root, Path(spec_path))
    if int(window_ticks) not in (4, 8):
        raise ConfigError("window_ticks must be 4 or 8")
    if arms_override is not None:
        selected = list(arms_override)
        if not selected:
            raise ConfigError("arm selection is empty")
        if len(selected) != len(set(selected)):
            raise ConfigError("arm selection contains duplicates")
        unknown = sorted(set(selected) - set(_ARMS))
        if unknown:
            raise ConfigError(f"unknown pilot arm(s): {unknown}")
        arm_names = selected
    else:
        arm_names = list(_ARMS)
    output = _resolve_output(root, Path(output_dir))

    scenario = load_scenario(root, str(config["source_scenario"]))
    audit = audit_experiment_admission(
        root,
        config_path=Path("config/initial_state/hist_vnext_h4_v1/experiment_inputs.json"),
        approval_path=Path("docs/phases/HIST_VNEXT/H4A-1/EXPERIMENT_INPUT_APPROVAL.json"),
        checked_at=datetime.now(UTC),
    )
    if audit.get("exit_code") != 0 or audit.get("admission") != "EXPERIMENT_ONLY":
        raise ConfigError(f"experiment admission is not approved: {audit.get('errors')}")
    derived = audit.get("derived_quantities")
    if not isinstance(derived, dict) or "by_region" not in derived:
        raise ConfigError("experiment admission produced no derived regional quantities")
    scenario = _apply_setting(
        scenario,
        by_region=derived["by_region"],
        dwelling_per_person=float(config["dwelling_per_person"]),
        ticks=int(config["ticks"]),
    )
    scenario = scenario.model_copy(update={"forcing_pack": str(config["forcing_pack"])})
    # The network compiler creates import/export cells only for commodities
    # with a positive declared trade request.  Declare the study's g02 request
    # on the scenario copy used to compile the network; the warm-up still runs
    # with a zero-request parameter copy, so the branch opening is unchanged.
    study_scenario = scenario.model_copy(
        update={
            "material_parameters": _parameters(
                scenario,
                commodity_ids=tuple(scenario.commodities),
                bailout_envelope_fraction=0.0,
                convertible_loan_limit=0.0,
                trade_requests=True,
            )
        }
    )

    pilot_dir = (root / "studies/HIST_VNEXT/pilot_B").resolve()
    registry = DataRegistry.load(
        root,
        allowed_commodities=list(study_scenario.commodities),
        extra_roots=(pilot_dir,),
    )
    raw_forcing = load_material_forcing(study_scenario, registry)
    if not np.isnan(np.asarray(raw_forcing.official_fx, dtype=np.float64)).all():
        raise ConfigError("study forcing must not consume official FX")
    anchor_tick = _anchor_tick(raw_forcing)
    contract = load_research_contract(root)
    initial = build_material_initial_conditions(
        study_scenario, RngRegistry(int(config["seed"]))
    )
    network = build_material_network(study_scenario, contract, initial)
    base_parameters = _parameters(
        study_scenario,
        commodity_ids=tuple(study_scenario.commodities),
        bailout_envelope_fraction=0.0,
        convertible_loan_limit=0.0,
        trade_requests=False,
    )
    d0_regime = load_legacy_trade_regime(
        root / "config/trade_regimes/hist_vnext_v1/legacy_treasury_prepay.json"
    )
    arm_definitions = {str(arm["name"]): arm for arm in config["arms"]}
    forcing_pack = _resolve_inside(
        root, Path(str(config["forcing_pack"])), label="forcing pack"
    )

    output.mkdir(parents=True)
    progress: dict[str, Any] = {}
    trace_handle = (output / "trace.jsonl").open("w", encoding="utf-8")
    journal = _JournalWriter(output / "journal.parquet")
    phase_times: dict[str, float] = {}
    run_started_perf = time.perf_counter()
    try:
        episodes: dict[str, Any] = {}
        for episode in config["episodes"]:
            phase_start = time.perf_counter()
            record = _run_episode(
                root=root,
                episode=episode,
                scenario=study_scenario,
                network=network,
                raw_forcing=raw_forcing,
                base_parameters=base_parameters,
                d0_regime=d0_regime,
                anchor_tick=anchor_tick,
                window_ticks=int(window_ticks),
                arm_names=arm_names,
                arm_definitions=arm_definitions,
                trace_handle=trace_handle,
                journal=journal,
                progress=progress,
            )
            episodes[str(record["episode_id"])] = record
            phase_times[f"episode:{record['episode_id']}"] = (
                time.perf_counter() - phase_start
            )
        trace_handle.close()
        journal.close()
        all_arms = {
            episode_id: record["arms"] for episode_id, record in episodes.items()
        }
        structural = {
            episode_id: {
                arm: summary["structural_status"]
                for arm, summary in arms.items()
            }
            for episode_id, arms in all_arms.items()
        }
        usd_probe: dict[str, dict[str, float]] = {}
        for episode_id, arms in all_arms.items():
            probe = arms.get("usd_limit_probe")
            if probe is None:
                continue
            draws = [float(probe["short_window"]["first_stage"]["USD_loan_drawn"])]
            payments = [float(probe["short_window"]["first_stage"]["USD_import_payment"])]
            if probe["later_window"].get("status") == "EXECUTED":
                draws.append(float(probe["later_window"]["first_stage"]["USD_loan_drawn"]))
                payments.append(
                    float(probe["later_window"]["first_stage"]["USD_import_payment"])
                )
            usd_probe[episode_id] = {
                "usd_loan_drawn": float(sum(draws)),
                "usd_import_payment": float(sum(payments)),
                "positive_desired_convertible_imports": 2.0,
            }
        if any(entry["usd_loan_drawn"] > _EPS for entry in usd_probe.values()):
            raise PilotTickFailure(
                "usd_limit_probe drew a new USD loan despite the F2 COMMODITY_INDEX gap",
                detail={"usd_limit_probe": usd_probe},
            )
        scientific = {
            "schema_version": SCHEMA_VERSION,
            "status": "COMPLETED" if set(arm_names) == set(_ARMS) else "PARTIAL",
            "seed": int(config["seed"]),
            "source_scenario": str(config["source_scenario"]),
            "window_ticks": int(window_ticks),
            "arms_declared": list(_ARMS),
            "arms_executed": arm_names,
            "episodes": episodes,
            "admission": {
                "exit_code": int(audit["exit_code"]),
                "structural": str(audit["structural"]),
                "admission": str(audit["admission"]),
            },
            "forcing": {
                "pack_path": str(config["forcing_pack"]),
                "pack_sha256": _sha256_file(forcing_pack),
                "binding_hash": json.loads(forcing_pack.read_text(encoding="utf-8"))[
                    "binding_hash"
                ],
                "artifact_hashes": dict(raw_forcing.input_artifact_hashes),
                "anchor_quarter": "1975Q1",
                "anchor_value": float(raw_forcing.cmea_energy_price[anchor_tick]),
                "price_index_version": PRICE_INDEX_VERSION,
                "raw_cmea_sha256": _sha256_array(raw_forcing.cmea_energy_price),
                "official_fx": "NOT_LOADED",
                "note": (
                    "collective-farm/official FX excluded; CMEA contract price is a "
                    "model index, not a historical conversion"
                ),
            },
            "code": _code_bindings(root, spec_file, forcing_pack),
            "usd_limit_probe": {
                "status": "PASS_ZERO_DRAW" if usd_probe else "NOT_RUN",
                "episodes": usd_probe,
                "boundary": "material.py desired_usd_outlay uses P02 COMMODITY_INDEX",
            },
            "verdicts": {
                "technical": "PASS",
                "structural": structural,
                "historical": "NOT_ESTABLISHED",
            },
            "not_run": list(_NOT_RUN),
            "notes": [
                "Branch states are model-generated, not historical initial states.",
                "1977-1978 were not run; long-run historical cost is NOT_OBSERVED.",
                "No welfare interpretation is attached to cross-episode differences.",
                (
                    "S is a Treasury bailout of existing wage/interest arrears, "
                    "not an import price subsidy."
                ),
            ],
        }
        scientific_digest = canonical_digest(scientific)
        pilot_id = scientific_digest[:32]
        resources = {
            "wall_seconds": time.perf_counter() - run_started_perf,
            "phase_seconds": phase_times,
            "max_rss": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            "max_rss_unit": "bytes on darwin, KiB on linux",
            "platform": platform.platform(),
            "generated_at": datetime.now(UTC).isoformat(),
            "started_at": started_at,
            "journal_rows": journal.rows,
            "trace_rows": len(episodes) * len(arm_names) * int(window_ticks),
            "git": _git_state(root),
        }
        manifest = {
            **scientific,
            "pilot_id": pilot_id,
            "scientific_digest": scientific_digest,
            "runtime": resources,
        }
        _dump_json(output / "manifest.json", manifest)
        _dump_json(
            output / "arm_summary.json",
            {
                "schema_version": SCHEMA_VERSION,
                "pilot_id": pilot_id,
                "arms": {
                    episode_id: {
                        arm: {
                            key: value
                            for key, value in summary.items()
                            if key not in {"final_state", "tables"}
                        }
                        for arm, summary in record["arms"].items()
                    }
                    for episode_id, record in episodes.items()
                },
            },
        )
        _dump_json(output / "resources.json", resources)
        return manifest
    except Exception as exc:
        trace_handle.close()
        try:
            journal.close()
        finally:
            _write_failure_certificate(
                output, exc=exc, progress=progress, started_at=started_at
            )
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--spec", default=str(DEFAULT_SPEC))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--window-ticks", type=int, choices=(4, 8), default=4)
    parser.add_argument("--arm", action="append", dest="arms")
    args = parser.parse_args(argv)
    try:
        result = run_pilot(
            Path(args.root),
            spec_path=Path(args.spec),
            output_dir=Path(args.output_dir),
            window_ticks=int(args.window_ticks),
            arms_override=args.arms,
        )
    except (ConfigError, OSError, ValueError, PilotTickFailure) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 2
    print(
        json.dumps(
            {"status": result["status"], "pilot_id": result["pilot_id"]}, indent=2
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
