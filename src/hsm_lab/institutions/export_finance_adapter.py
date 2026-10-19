"""H3F-D0: versioned legacy Treasury-prepay reference and double-book observer.

This module is a thin, explicitly opt-in adapter around the existing material
kernel.  Importing it must not register any hooks, mutate engine defaults, or
touch engine files: the legacy export finance path is byte-identical unless a
caller passes a :class:`LegacyTradeRegime` to :func:`execute_legacy_trade_tick`.

Three responsibilities are split into three pure functions:

* :func:`load_legacy_trade_regime` reads a single regime JSON file and rejects
  every other shape with ``HIST_H3F_D0``-prefixed :class:`ResearchGateError`.
* :func:`observe_legacy_trade_tick` is strictly read-only: it returns a fresh
  observation dict that mirrors the legacy export receipts, payments and
  journal legs without ever mutating the flows, state, opening snapshot,
  parameters or network.
* :func:`execute_legacy_trade_tick` is the opt-in wrapper: it validates the
  regime and the opening boundary, deep-copies the state for rollback, runs
  exactly one real ``tick_material`` plus the existing material/financial
  invariant gate, then the observer, and only then advances
  ``state.completed_ticks``.  Any failure inside that window restores every
  dataclass field of the state and raises :class:`LegacyTradeFailure`.

The adapter does not introduce loans, receivables, maturities or bad-debt
state.  Its only purpose is to register an extra observation layer that the
underlying kernel cannot see (the foreign-account journal-leg counterpart, the
Treasury goods-payment payee group, the CMEA memo-credit closing identity).
"""

from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

from hsm_lab.contract.base import ResearchGateError, StrictModel
from hsm_lab.contract.material import PURPOSE_CODES, MaterialParameters, RoutePurpose
from hsm_lab.engine import accounting
from hsm_lab.engine.accounting import InvariantSummary, tolerance_for
from hsm_lab.engine.finance import (
    CMEA_CURRENCY,
    DOMESTIC_CURRENCY,
    USD_CURRENCY,
    AccountKind,
    build_account_directory,
    foreign_account_id,
    treasury_account_id,
)
from hsm_lab.engine.material import (
    _cell_price_vector,  # read-only reuse
    tick_material,
)
from hsm_lab.engine.network import MaterialNetwork
from hsm_lab.engine.state import (
    MaterialForcing,
    MaterialState,
    MaterialStockSnapshot,
    MaterialTickFlows,
    capture_material_stocks,
)
from hsm_lab.engine.trade import channel_prices

# ---------------------------------------------------------------------------
# Schema constants (do not edit once published; D1/D2/D3 will introduce their
# own schema versions).
# ---------------------------------------------------------------------------

REGIME_SCHEMA_VERSION = "hist-trade-regime-v1"
REGIME_ID = "legacy_treasury_prepay"
REGIME_SOURCE_KIND = "synthetic"
OBSERVATION_SCHEMA_VERSION = "hist-legacy-trade-observation-v1"

GATE_PREFIX = "HIST_H3F_D0"

#: Channel index → currency code (mirrors ``network.export_demand_cell``).
CHANNEL_CURRENCIES: tuple[str, ...] = (CMEA_CURRENCY, USD_CURRENCY)
CHANNEL_LABELS: tuple[str, ...] = ("CMEA", "USD")
CMEA_CHANNEL = 0
USD_CHANNEL = 1

#: Route-purpose codes that mark a real export edge.
EXPORT_PURPOSES: tuple[int, ...] = (
    int(PURPOSE_CODES[RoutePurpose.EXPORT_CMEA]),
    int(PURPOSE_CODES[RoutePurpose.EXPORT_CONVERTIBLE]),
)
EXPORT_PURPOSE_TO_CHANNEL: dict[int, int] = {
    EXPORT_PURPOSES[0]: CMEA_CHANNEL,
    EXPORT_PURPOSES[1]: USD_CHANNEL,
}


def _reject(message: str) -> None:
    raise ResearchGateError(f"{GATE_PREFIX}: {message}")


class LegacyTradeRegime(StrictModel):
    """Frozen synthetic reference regime; D1/D2/D3 carry their own types."""

    schema_version: Literal["hist-trade-regime-v1"]
    regime_id: Literal["legacy_treasury_prepay"]
    source_kind: Literal["synthetic"]


def load_legacy_trade_regime(path: str | Path) -> LegacyTradeRegime:
    """Read a single regime JSON file and validate it as D0 legacy_treasury_prepay.

    Missing file, invalid JSON, unknown keys, wrong literal, or a path that
    claims to belong to a D1/D2/D3 regime all raise
    ``HIST_H3F_D0``-prefixed :class:`ResearchGateError`.  The loader never
    scans a tree, falls back to a default, or imports other regime files.
    """
    file_path = Path(path)
    text: str | None = None
    try:
        text = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        _reject(f"regime file not found: {file_path}")
    except OSError as exc:
        _reject(f"could not read regime file {file_path}: {exc}")
    assert text is not None  # FileNotFoundError branch above returns

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        _reject(f"invalid JSON in regime file {file_path}: {exc.msg}")
    if not isinstance(payload, dict):
        _reject(f"regime file {file_path} must decode to a JSON object")

    # Defend against extra keys before pydantic sees the payload (StrictModel
    # already enforces extra="forbid", but the explicit check gives a clearer
    # error and matches the D0 spec wording).
    expected_keys = {"schema_version", "regime_id", "source_kind"}
    extra = set(payload.keys()) - expected_keys
    if extra:
        _reject(f"regime file {file_path} has unexpected keys: {sorted(extra)}")
    if set(payload.keys()) != expected_keys:
        _reject(
            f"regime file {file_path} must carry exactly the keys "
            f"{sorted(expected_keys)}; got {sorted(payload.keys())}"
        )

    try:
        return LegacyTradeRegime.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - any pydantic rejection is a gate violation
        _reject(f"regime file {file_path} failed validation: {exc}")


# ---------------------------------------------------------------------------
# Observer: strictly read-only.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LegacyTradeResult:
    """One admitted legacy trade tick; flows/gate/observation are the kernel output."""

    flows: MaterialTickFlows
    gate: InvariantSummary
    observation: dict[str, Any]


class LegacyTradeFailure(ResearchGateError):
    """Wrapper rejected the tick (gate failure, observer failure, invalid regime)."""

    def __init__(
        self,
        *,
        phase: str,
        cause: BaseException,
        failed_flows: MaterialTickFlows | None,
        failed_state: MaterialState | None,
    ) -> None:
        super().__init__(f"{GATE_PREFIX}: {phase} failed: {cause}")
        self.phase = phase
        self.cause = cause
        self.failed_flows = failed_flows
        self.failed_state = failed_state


def _index_account_keys(
    directory: dict[tuple[str, int, str, str], int],
) -> dict[int, tuple[str, int, str, str]]:
    inverse: dict[int, tuple[str, int, str, str]] = {}
    for key, account_id in directory.items():
        if account_id in inverse:
            _fail_observer(
                f"duplicate account id {account_id} for keys {inverse[account_id]} and {key}"
            )
        inverse[account_id] = key
    return inverse


def _fail_observer(message: str) -> None:
    raise ResearchGateError(f"{GATE_PREFIX}: observer: {message}")


def _validate_flow_scalar(name: str, value: float) -> float:
    if not math.isfinite(float(value)):
        _fail_observer(f"flow scalar {name}={value!r} must be finite")
    return float(value)


def _validate_flow_axis(
    name: str,
    values: np.ndarray | list[float],
    *,
    non_negative: bool = False,
    non_negative_tol: float = 1e-12,
) -> np.ndarray:
    """Validate a 1-D float flow axis is finite (and optionally non-negative)."""
    array = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(array)):
        _fail_observer(f"flow axis {name} contains non-finite values")
    if non_negative and np.any(array < -non_negative_tol):
        _fail_observer(f"flow axis {name} contains negative values")
    return array


#: Absolute floor for journal-vs-flow sum comparisons.  1e-10 is the smallest
#: positive scalar the engine ever carries on a journal leg; anything larger
#: must be visible in the journal, anything below 1e-12 is float noise.
_JOURNAL_SUM_ABS_TOL = 1e-12


def _strict_sum_tolerance(expected: float) -> float:
    """Tightest tolerance that still tolerates 1 ULP of float noise.

    The D0 plan requires the journal sum to equal the flow scalar exactly so
    that a strict positive (including ``1e-10``) cannot be hidden by an
    overly-loose ATOL; ``1e-12`` keeps this guarantee while tolerating the
    last-bit rounding noise of a single multiplication/add.
    """
    return max(_JOURNAL_SUM_ABS_TOL, abs(float(expected)) * 1e-15)


def _axis_or_zero(values: np.ndarray, axis: int) -> np.ndarray:
    """Return ``values[axis]`` converted to ``list[float]``."""
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.shape[0] <= axis:
        _fail_observer(f"axis {axis} missing from a 1-D flow vector")
    return array


def _channel_axis(
    cell_index: int,
    *,
    currency: str,
    flows: MaterialTickFlows,
    channel: int,
    g: int,
) -> tuple[float, float, float, float, float, str]:
    """Resolve (desired, ordered, allocated, delivered, used, demand_status) for one cell.

    Returns ``(desired, ordered, allocated, delivered, used, status)``.  When the
    demand cell is absent (``-1``) every quantity is zero and the status is
    ``NO_DEMAND_CELL``.  When the cell exists but the demand is zero (within
    tolerance) the status is ``ZERO_DEMAND``.  Otherwise ``ACTIVE``.
    """
    if cell_index < 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0, "NO_DEMAND_CELL"
    if cell_index >= int(flows.desired.shape[0]):
        _fail_observer(
            f"channel {channel}/{currency} demand cell {cell_index} "
            f"lies outside the flows demand axis ({flows.desired.shape[0]})"
        )
    desired = float(flows.desired[cell_index])
    ordered = float(flows.ordered[cell_index])
    allocated = float(flows.allocated[cell_index])
    delivered = float(flows.delivered[cell_index])
    used = float(flows.used[cell_index])
    tol = float(tolerance_for(desired, 0.0))
    status = "ZERO_DEMAND" if abs(desired) <= tol else "ACTIVE"
    return desired, ordered, allocated, delivered, used, status


def _commodity_axis_safe(network: MaterialNetwork | None) -> tuple[str, ...]:
    if network is None:
        return ()
    return tuple(network.commodity_ids)


def _network_export_demand_cell(
    network: MaterialNetwork, channel: int, g: int
) -> int:
    cells = np.asarray(network.export_demand_cell, dtype=np.int64)
    if cells.ndim != 2 or cells.shape[0] <= channel or cells.shape[1] <= g:
        _fail_observer(
            f"export_demand_cell shape {cells.shape} cannot address channel={channel} g={g}"
        )
    return int(cells[channel, g])


def _channel_prices_axis(
    *,
    parameters: MaterialParameters,
    network: MaterialNetwork,
    oil_price: float,
    cmea_contract_price: float,
) -> tuple[np.ndarray, np.ndarray]:
    if not math.isfinite(oil_price):
        _fail_observer(f"oil_price={oil_price!r} must be finite")
    if not (math.isfinite(cmea_contract_price) or math.isnan(cmea_contract_price)):
        _fail_observer(
            f"cmea_contract_price={cmea_contract_price!r} must be finite or NaN"
        )
    cmea, convertible = channel_prices(
        parameters,
        network,
        oil_price=float(oil_price),
        cmea_contract_price=float(cmea_contract_price),
    )
    return cmea, convertible


def _channel_axis_view(
    *,
    flows: MaterialTickFlows,
    network: MaterialNetwork,
    channel: int,
    currency: str,
    parameters: MaterialParameters,
    oil_price: float,
    cmea_contract_price: float,
) -> dict[str, Any]:
    g_count = len(network.commodity_ids)
    desired_axis: list[float] = []
    ordered_axis: list[float] = []
    allocated_axis: list[float] = []
    delivered_axis: list[float] = []
    used_axis: list[float] = []
    demand_status: list[str] = []
    for g in range(g_count):
        cell_index = _network_export_demand_cell(network, channel, g)
        desired, ordered, allocated, delivered, used, status = _channel_axis(
            cell_index,
            currency=currency,
            flows=flows,
            channel=channel,
            g=g,
        )
        for axis_name, axis_value in (
            ("desired", desired),
            ("ordered", ordered),
            ("allocated", allocated),
            ("delivered", delivered),
            ("used", used),
        ):
            if not math.isfinite(float(axis_value)):
                _fail_observer(
                    f"channel {channel}/{currency} demand axis "
                    f"{axis_name}[{g}]={axis_value!r} must be finite"
                )
            if float(axis_value) < -float(tolerance_for(axis_value, 0.0)):
                _fail_observer(
                    f"channel {channel}/{currency} demand axis "
                    f"{axis_name}[{g}]={axis_value!r} must be non-negative"
                )
        desired_axis.append(desired)
        ordered_axis.append(ordered)
        allocated_axis.append(allocated)
        delivered_axis.append(delivered)
        used_axis.append(used)
        demand_status.append(status)

    # Channel imports/exports are already axis-aligned on the commodity axis.
    if channel == CMEA_CHANNEL:
        exports_axis = np.asarray(flows.cmea_exports, dtype=np.float64)
        imports_axis = np.asarray(flows.cmea_imports, dtype=np.float64)
        export_receipt = _validate_flow_scalar("cmea_export_receipt", flows.cmea_export_receipt)
        import_payment = _validate_flow_scalar("cmea_import_payment", flows.cmea_import_payment)
        balance_open = 0.0  # opening balance lives outside flows; we use state scalars
    else:
        exports_axis = np.asarray(flows.convertible_exports, dtype=np.float64)
        imports_axis = np.asarray(flows.convertible_imports, dtype=np.float64)
        export_receipt = _validate_flow_scalar("usd_export_receipt", flows.usd_export_receipt)
        import_payment = _validate_flow_scalar("usd_import_payment", flows.usd_import_payment)
        balance_open = 0.0

    cmea_prices, convertible_prices = _channel_prices_axis(
        parameters=parameters,
        network=network,
        oil_price=oil_price,
        cmea_contract_price=cmea_contract_price,
    )
    expected_receipt = float(
        np.dot(
            exports_axis,
            convertible_prices if channel == USD_CHANNEL else cmea_prices,
        )
    )

    # Strict no-delivery/no-receipt rule: a strictly positive receipt requires
    # at least one strictly positive delivered export quantity.  This must be
    # enforced BEFORE the ordinary accounting tolerance so a 1e-10 receipt
    # against a zero delivered-axis cannot hide inside the tolerance.  Use the
    # *actual* demand-cell ``delivered_axis`` (not the channel ``exports_axis``
    # the kernel copies it to), and compare against exact zero so a legitimate
    # tiny positive delivery (e.g. 3.33e-14) is not erased by a quantity
    # cutoff (the prior 1e-12 cutoff silently turned a matching positive
    # delivery into zero and rejected the tick).
    if export_receipt > 0.0:
        has_positive_delivery = False
        for g in range(g_count):
            cell_index = _network_export_demand_cell(network, channel, g)
            if cell_index < 0:
                continue
            if float(delivered_axis[g]) > 0.0:
                has_positive_delivery = True
                break
        if not has_positive_delivery:
            _fail_observer(
                f"channel {channel}/{currency} export_receipt={export_receipt!r} "
                f"is positive while every actual delivered export quantity is "
                f"exactly zero"
            )

    # Strict axis correspondence: ``exports_axis`` must equal the boundary
    # ``delivered`` values across all cells (no ACTIVE row may diverge).  The
    # kernel copies one to the other so exact equality is expected; reject any
    # strictly-positive-vs-exact-zero mismatch without letting the accounting
    # ATOL erase it.
    for g in range(g_count):
        cell_index = _network_export_demand_cell(network, channel, g)
        if cell_index < 0:
            if not math.isclose(
                float(exports_axis[g]),
                0.0,
                abs_tol=float(tolerance_for(float(exports_axis[g]), 0.0)),
            ):
                _fail_observer(
                    f"channel {channel}/{currency} exports[{g}]={exports_axis[g]!r} "
                    f"non-zero for NO_DEMAND_CELL"
                )
            continue
        if demand_status[g] == "NO_DEMAND_CELL":
            continue
        delivered_v = float(delivered_axis[g])
        exports_v = float(exports_axis[g])
        # Reject a positive-vs-zero mismatch BEFORE the accounting ATOL: the
        # tolerance formula gives ~1e-9 for a zero-vs-tiny-positive pair, which
        # would otherwise hide the bypass.
        if delivered_v > 0.0 and exports_v == 0.0:
            _fail_observer(
                f"channel {channel}/{currency} delivered[{g}]={delivered_v!r} "
                f"is strictly positive while exports[{g}]={exports_v!r} is "
                f"exactly zero"
            )
        if delivered_v == 0.0 and exports_v > 0.0:
            _fail_observer(
                f"channel {channel}/{currency} exports[{g}]={exports_v!r} "
                f"is strictly positive while delivered[{g}]={delivered_v!r} "
                f"is exactly zero"
            )
        tol = float(tolerance_for(delivered_v, exports_v))
        if abs(delivered_v - exports_v) > tol:
            _fail_observer(
                f"channel {channel}/{currency} exports[{g}]={exports_v!r} "
                f"diverges from delivered={delivered_v!r} beyond tolerance {tol!r}"
            )

    tol_receipt = float(tolerance_for(export_receipt, expected_receipt))
    if abs(export_receipt - expected_receipt) > tol_receipt:
        _fail_observer(
            f"channel {channel}/{currency} export_receipt={export_receipt!r} "
            f"diverges from dot(exports, prices)={expected_receipt!r} beyond tolerance "
            f"{tol_receipt!r}"
        )

    view: dict[str, Any] = {
        "currency": currency,
        "desired": desired_axis,
        "ordered": ordered_axis,
        "allocated": allocated_axis,
        "delivered": delivered_axis,
        "used": used_axis,
        "imports": imports_axis.tolist(),
        "exports": exports_axis.tolist(),
        "demand_status": demand_status,
        "import_payment": import_payment,
        "export_receipt": export_receipt,
        "expected_receipt": float(expected_receipt),
        "balance_open": balance_open,  # overwritten by caller once opening is known
        "balance_close": 0.0,  # ditto
    }
    return view


def _validate_journal_columns(flows: MaterialTickFlows) -> tuple[np.ndarray, ...]:
    if flows.journal_kind is None or len(flows.journal_kind) == 0:
        return (
            np.empty(0, dtype=object),
            np.empty(0, dtype=np.int64),
            np.empty(0, dtype=np.int64),
            np.empty(0, dtype=np.float64),
            np.empty(0, dtype=object),
            np.empty(0, dtype=object),
            np.empty(0, dtype=object),
            np.empty(0, dtype=np.int64),
        )
    count = len(flows.journal_kind)
    columns = (
        flows.journal_kind,
        flows.journal_tick,
        flows.journal_debit,
        flows.journal_credit,
        flows.journal_currency,
        flows.journal_amount,
        flows.journal_org,
        flows.journal_leg,
    )
    lengths = {len(col) for col in columns}
    if len(lengths) != 1:
        _fail_observer(f"journal column lengths differ: {sorted(lengths)}")
    if count != next(iter(lengths)):
        _fail_observer(f"journal row count mismatch: {count}")
    kind = np.asarray(flows.journal_kind, dtype=object)
    tick = np.asarray(flows.journal_tick, dtype=np.int64)
    debit = np.asarray(flows.journal_debit, dtype=np.int64)
    credit = np.asarray(flows.journal_credit, dtype=np.int64)
    amount = np.asarray(flows.journal_amount, dtype=np.float64)
    currency = np.asarray(flows.journal_currency, dtype=object)
    org = np.asarray(flows.journal_org, dtype=object)
    leg = np.asarray(flows.journal_leg, dtype=np.int64)
    if not np.all(np.isfinite(amount)) or np.any(amount <= 0.0):
        _fail_observer("journal amounts must be finite and strictly positive")
    if not np.all(tick == flows.tick):
        _fail_observer("journal legs must all carry the flow tick")
    if int(leg[0]) != 0:
        _fail_observer("first journal leg must start at index 0")
    if count > 1:
        restart = leg[1:] == 0
        sequential = np.diff(leg) == 1
        if not bool(np.all(restart | sequential)):
            _fail_observer(
                "journal leg indices must restart at 0 and increment by 1 per transaction"
            )
    starts = np.nonzero(leg == 0)[0]
    run_id = np.cumsum(leg == 0) - 1
    if not bool(np.all(currency == currency[starts][run_id])):
        _fail_observer("a journal transaction mixes currencies")
    return kind, tick, debit, credit, amount, currency, org, leg


def _resolve_leg_currency_groups(
    *,
    currency: np.ndarray,
    leg: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    starts = np.nonzero(leg == 0)[0]
    run_id = np.cumsum(leg == 0) - 1
    leg_currency = currency[starts][run_id]
    return leg_currency, starts


def _sum_journal_legs(
    *,
    amount: np.ndarray,
    debit: np.ndarray,
    credit: np.ndarray,
    mask: np.ndarray,
) -> tuple[float, float]:
    if mask.sum() == 0:
        return 0.0, 0.0
    debit_total = float(np.sum(amount[mask] * (debit[mask] >= 0).astype(np.float64)))
    credit_total = float(np.sum(amount[mask] * (credit[mask] >= 0).astype(np.float64)))
    return debit_total, credit_total


def _channel_journal_rows(
    *,
    flows: MaterialTickFlows,
    state: MaterialState,
    opening: MaterialStockSnapshot,
    channel: int,
    currency: str,
    export_receipt: float,
    import_payment: float,
    columns: tuple[np.ndarray, ...],
) -> tuple[float, float, float]:
    """Validate the per-channel journal legs and return observed receipt/payment/balance residuals.

    Returns ``(observed_receipt, observed_payment, balance_close_residual)``.
    """
    kind, _tick, debit, credit, amount, _currency, _org, _leg = columns
    foreign = foreign_account_id(state, currency)
    treasury_fiscal = treasury_account_id(state, AccountKind.FISCAL_EXPENSE)

    journal_currency_array = np.asarray(flows.journal_currency, dtype=object)
    receipt_mask = (kind == "export_receipt") & (journal_currency_array == currency)
    payment_mask = (kind == "import_payment") & (journal_currency_array == currency)
    loan_drawdown_mask = (kind == "loan_drawdown") & (journal_currency_array == currency)
    interest_payment_mask = (kind == "interest_payment") & (journal_currency_array == currency)
    principal_repayment_mask = (
        (kind == "principal_repayment") & (journal_currency_array == currency)
    )

    observed_receipt, _ = _sum_journal_legs(
        amount=amount, debit=debit, credit=credit, mask=receipt_mask
    )
    observed_payment, _ = _sum_journal_legs(
        amount=amount, debit=debit, credit=credit, mask=payment_mask
    )
    observed_draw, _ = _sum_journal_legs(
        amount=amount, debit=debit, credit=credit, mask=loan_drawdown_mask
    )
    observed_interest, _ = _sum_journal_legs(
        amount=amount, debit=debit, credit=credit, mask=interest_payment_mask
    )
    observed_principal, _ = _sum_journal_legs(
        amount=amount, debit=debit, credit=credit, mask=principal_repayment_mask
    )

    if export_receipt > 0.0:
        if receipt_mask.sum() == 0:
            _fail_observer(
                f"positive {currency} export_receipt={export_receipt!r} carries no journal leg"
            )
        for index in np.flatnonzero(receipt_mask):
            if int(debit[index]) != foreign:
                _fail_observer(
                    f"{currency} export_receipt leg {int(index)} "
                    f"debits {int(debit[index])}, expected foreign {foreign}"
                )
            if int(credit[index]) != treasury_fiscal:
                _fail_observer(
                    f"{currency} export_receipt leg {int(index)} "
                    f"credits {int(credit[index])}, expected treasury FISCAL_EXPENSE "
                    f"{treasury_fiscal}"
                )
    tol_receipt = _strict_sum_tolerance(export_receipt)
    if abs(observed_receipt - export_receipt) > tol_receipt:
        _fail_observer(
            f"{currency} export_receipt journal sum {observed_receipt!r} "
            f"diverges from flow scalar {export_receipt!r} beyond {tol_receipt!r}"
        )

    if import_payment > 0.0:
        if payment_mask.sum() == 0:
            _fail_observer(
                f"positive {currency} import_payment={import_payment!r} carries no journal leg"
            )
        for index in np.flatnonzero(payment_mask):
            if int(debit[index]) != treasury_fiscal:
                _fail_observer(
                    f"{currency} import_payment leg {int(index)} "
                    f"debits {int(debit[index])}, expected treasury FISCAL_EXPENSE "
                    f"{treasury_fiscal}"
                )
            if int(credit[index]) != foreign:
                _fail_observer(
                    f"{currency} import_payment leg {int(index)} "
                    f"credits {int(credit[index])}, expected foreign {foreign}"
                )
    tol_payment = _strict_sum_tolerance(import_payment)
    if abs(observed_payment - import_payment) > tol_payment:
        _fail_observer(
            f"{currency} import_payment journal sum {observed_payment!r} "
            f"diverges from flow scalar {import_payment!r} beyond {tol_payment!r}"
        )

    if channel == USD_CHANNEL:
        loan_drawn = float(flows.usd_loan_drawn)
        interest_paid = float(flows.usd_interest_paid)
        principal_paid = float(flows.usd_principal_paid)
        if loan_drawn > 0.0:
            if loan_drawdown_mask.sum() == 0:
                _fail_observer(
                    f"positive USD loan_drawn={loan_drawn!r} carries no journal leg"
                )
            for index in np.flatnonzero(loan_drawdown_mask):
                if int(debit[index]) != foreign:
                    _fail_observer(
                        f"USD loan_drawdown leg {int(index)} debits {int(debit[index])}, "
                        f"expected foreign {foreign}"
                    )
                if int(credit[index]) != treasury_fiscal:
                    _fail_observer(
                        f"USD loan_drawdown leg {int(index)} credits {int(credit[index])}, "
                        f"expected treasury FISCAL_EXPENSE {treasury_fiscal}"
                    )
        if interest_paid > 0.0:
            if interest_payment_mask.sum() == 0:
                _fail_observer(
                    f"positive USD interest_paid={interest_paid!r} carries no journal leg"
                )
            for index in np.flatnonzero(interest_payment_mask):
                if int(debit[index]) != treasury_fiscal:
                    _fail_observer(
                        f"USD interest_payment leg {int(index)} debits {int(debit[index])}, "
                        f"expected treasury FISCAL_EXPENSE {treasury_fiscal}"
                    )
                if int(credit[index]) != foreign:
                    _fail_observer(
                        f"USD interest_payment leg {int(index)} credits {int(credit[index])}, "
                        f"expected foreign {foreign}"
                    )
        if principal_paid > 0.0:
            if principal_repayment_mask.sum() == 0:
                _fail_observer(
                    f"positive USD principal_paid={principal_paid!r} carries no journal leg"
                )
            for index in np.flatnonzero(principal_repayment_mask):
                if int(debit[index]) != treasury_fiscal:
                    _fail_observer(
                        f"USD principal_repayment leg {int(index)} debits {int(debit[index])}, "
                        f"expected treasury FISCAL_EXPENSE {treasury_fiscal}"
                    )
                if int(credit[index]) != foreign:
                    _fail_observer(
                        f"USD principal_repayment leg {int(index)} credits {int(credit[index])}, "
                        f"expected foreign {foreign}"
                    )
        tol_draw = _strict_sum_tolerance(loan_drawn)
        if abs(observed_draw - loan_drawn) > tol_draw:
            _fail_observer(
                f"USD loan_drawdown journal sum {observed_draw!r} diverges from "
                f"flow {loan_drawn!r} beyond {tol_draw!r}"
            )
        tol_interest = _strict_sum_tolerance(interest_paid)
        if abs(observed_interest - interest_paid) > tol_interest:
            _fail_observer(
                f"USD interest_payment journal sum {observed_interest!r} diverges from "
                f"flow {interest_paid!r} beyond {tol_interest!r}"
            )
        tol_principal = _strict_sum_tolerance(principal_paid)
        if abs(observed_principal - principal_paid) > tol_principal:
            _fail_observer(
                f"USD principal_repayment journal sum {observed_principal!r} diverges from "
                f"flow {principal_paid!r} beyond {tol_principal!r}"
            )
        # USD principal and interest-arrears identity checks.
        opening_principal = float(opening.usd_principal)
        closing_principal = float(state.usd_principal)
        expected_principal = opening_principal + loan_drawn - principal_paid
        tol_p = float(tolerance_for(closing_principal, expected_principal))
        if abs(closing_principal - expected_principal) > tol_p:
            _fail_observer(
                f"USD principal identity violated: opening={opening_principal!r} "
                f"drawn={loan_drawn!r} paid={principal_paid!r} "
                f"closing={closing_principal!r} expected={expected_principal!r} "
                f"tol={tol_p!r}"
            )

    # Closing identities are checked by the caller after this returns; here
    # we simply report the observed scalars and let the wrapper compare them.
    return observed_receipt, observed_payment, observed_principal


def _export_demand_axis(
    *,
    network: MaterialNetwork,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    oil_price: float,
    cmea_contract_price: float,
) -> dict[str, Any]:
    cmea_view = _channel_axis_view(
        flows=flows,
        network=network,
        channel=CMEA_CHANNEL,
        currency=CMEA_CURRENCY,
        parameters=parameters,
        oil_price=oil_price,
        cmea_contract_price=cmea_contract_price,
    )
    usd_view = _channel_axis_view(
        flows=flows,
        network=network,
        channel=USD_CHANNEL,
        currency=USD_CURRENCY,
        parameters=parameters,
        oil_price=oil_price,
        cmea_contract_price=cmea_contract_price,
    )
    return {CMEA_CURRENCY: cmea_view, USD_CURRENCY: usd_view}


def _build_journal_rows(
    flows: MaterialTickFlows,
    state: MaterialState,
    *,
    directory: dict[int, tuple[str, int, str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    starts = np.nonzero(np.asarray(flows.journal_leg, dtype=np.int64) == 0)[0]
    starts_list = starts.tolist()
    for index in range(len(flows.journal_kind)):
        ordinal = int(np.searchsorted(starts_list, index, side="right") - 1)
        debit_id = int(flows.journal_debit[index])
        credit_id = int(flows.journal_credit[index])
        debit_key = directory.get(debit_id)
        credit_key = directory.get(credit_id)
        if debit_key is None:
            _fail_observer(f"journal row {index} debits unknown account {debit_id}")
        if credit_key is None:
            _fail_observer(f"journal row {index} credits unknown account {credit_id}")
        rows.append(
            {
                "row_index": int(index),
                "transaction_ordinal": int(ordinal),
                "kind": str(flows.journal_kind[index]),
                "tick": int(flows.journal_tick[index]),
                "debit": debit_id,
                "credit": credit_id,
                "debit_key": list(debit_key),
                "credit_key": list(credit_key),
                "currency": str(flows.journal_currency[index]),
                "amount": float(flows.journal_amount[index]),
                "org": None if flows.journal_org[index] is None else int(flows.journal_org[index]),
                "leg": int(flows.journal_leg[index]),
            }
        )
    return rows


def observe_legacy_trade_tick(
    opening: MaterialStockSnapshot,
    state: MaterialState,
    flows: MaterialTickFlows,
    parameters: MaterialParameters,
    network: MaterialNetwork,
    *,
    regime: LegacyTradeRegime,
    oil_price: float,
    cmea_contract_price: float,
) -> dict[str, Any]:
    """Build the double-book observation; never mutates the inputs."""
    if not isinstance(regime, LegacyTradeRegime):
        _fail_observer("regime is not a LegacyTradeRegime instance")
    if int(opening.completed_ticks) != int(flows.tick):
        _fail_observer(
            f"opening.completed_ticks={opening.completed_ticks} != flows.tick={flows.tick}"
        )
    if not math.isfinite(float(oil_price)):
        _fail_observer(f"oil_price={oil_price!r} must be finite")
    if not (math.isfinite(float(cmea_contract_price)) or math.isnan(float(cmea_contract_price))):
        _fail_observer(
            f"cmea_contract_price={cmea_contract_price!r} must be finite or NaN"
        )

    # ----------------------------------------------------------------
    # Pre-flight finiteness / sign checks.  These run BEFORE any residual
    # comparison because ``abs(nan) > tol`` is false, which would let a
    # NaN slip through the identity comparisons below as a silent miss.
    # CMEA ``cmea_settlement_balance`` may legitimately carry negative
    # legacy memo credit, but it must always be finite.
    # ----------------------------------------------------------------
    opening_scalar_names = (
        ("usd_reserve", opening.usd_reserve),
        ("usd_principal", opening.usd_principal),
        ("usd_interest_arrears", opening.usd_interest_arrears),
        ("cmea_settlement_balance", opening.cmea_settlement_balance),
        ("treasury_deposit", opening.treasury_deposit),
    )
    for scalar_name, scalar_value in opening_scalar_names:
        _validate_flow_scalar(f"opening.{scalar_name}", float(scalar_value))

    closing_scalar_names = (
        ("usd_reserve", state.usd_reserve),
        ("usd_principal", state.usd_principal),
        ("usd_interest_arrears", state.usd_interest_arrears),
        ("cmea_settlement_balance", state.cmea_settlement_balance),
        ("treasury_deposit", state.treasury_deposit),
    )
    for scalar_name, scalar_value in closing_scalar_names:
        _validate_flow_scalar(f"closing.{scalar_name}", float(scalar_value))

    _validate_flow_axis(
        "opening.bank_reserves", opening.bank_reserves, non_negative=True
    )
    _validate_flow_axis(
        "closing.bank_reserves", state.bank_reserves, non_negative=True
    )

    flow_scalar_names = (
        ("usd_interest_accrued", flows.usd_interest_accrued),
        ("usd_loan_drawn", flows.usd_loan_drawn),
        ("usd_interest_paid", flows.usd_interest_paid),
        ("usd_principal_paid", flows.usd_principal_paid),
        ("usd_import_payment", flows.usd_import_payment),
        ("usd_export_receipt", flows.usd_export_receipt),
        ("cmea_import_payment", flows.cmea_import_payment),
        ("cmea_export_receipt", flows.cmea_export_receipt),
    )
    for scalar_name, scalar_value in flow_scalar_names:
        _validate_flow_scalar(f"flows.{scalar_name}", float(scalar_value))
    if flows.official_fx_translation is not None and not math.isfinite(
        float(flows.official_fx_translation)
    ):
        _fail_observer(
            f"flows.official_fx_translation={flows.official_fx_translation!r} "
            "must be finite"
        )

    _validate_flow_axis("flows.cmea_imports", flows.cmea_imports, non_negative=True)
    _validate_flow_axis(
        "flows.convertible_imports", flows.convertible_imports, non_negative=True
    )
    _validate_flow_axis("flows.cmea_exports", flows.cmea_exports, non_negative=True)
    _validate_flow_axis(
        "flows.convertible_exports", flows.convertible_exports, non_negative=True
    )

    # Border (export + housing) edges: ``edge_delivered`` and
    # ``edge_service_fee`` must both be finite and non-negative.  Border
    # edges are every edge used in Treasury reconciliation: the export
    # edges (CMEA / USD) and the housing edges (purpose HOUSING).
    edge_purpose_pre = np.asarray(network.edge_purpose, dtype=np.int64)
    housing_purpose_code_pre = int(PURPOSE_CODES[RoutePurpose.HOUSING])
    border_edge_mask = np.isin(
        edge_purpose_pre, list(EXPORT_PURPOSES) + [housing_purpose_code_pre]
    )
    if border_edge_mask.any():
        _validate_flow_axis(
            "flows.edge_delivered[border]",
            np.asarray(flows.edge_delivered, dtype=np.float64)[border_edge_mask],
            non_negative=True,
        )
        _validate_flow_axis(
            "flows.edge_service_fee[border]",
            np.asarray(flows.edge_service_fee, dtype=np.float64)[border_edge_mask],
            non_negative=True,
        )

    # Journal row currency whitelist: every currency must be one of the
    # three books (domestic / USD / CMEA settlement).  Treasury
    # ``goods_payment`` rows debiting the Treasury CASH_DEPOSIT account must
    # be domestic; foreign-currency Treasury goods rows are invalid.
    treasury_cash_pre = treasury_account_id(state, AccountKind.CASH_DEPOSIT)
    treasury_fiscal_pre = treasury_account_id(state, AccountKind.FISCAL_EXPENSE)
    allowed_currencies = frozenset(
        {DOMESTIC_CURRENCY, USD_CURRENCY, CMEA_CURRENCY}
    )
    trade_kinds_pre = frozenset({
        "export_receipt",
        "import_payment",
        "loan_drawdown",
        "interest_payment",
        "principal_repayment",
    })
    for row_index, kind_value in enumerate(flows.journal_kind):
        currency_value = str(flows.journal_currency[row_index])
        if currency_value not in allowed_currencies:
            _fail_observer(
                f"journal row {row_index} kind={kind_value!r} carries unknown "
                f"currency {currency_value!r} (allowed: {sorted(allowed_currencies)})"
            )
        if kind_value == "goods_payment":
            if int(flows.journal_debit[row_index]) == treasury_cash_pre:
                if currency_value != DOMESTIC_CURRENCY:
                    _fail_observer(
                        f"journal row {row_index} is a foreign-currency Treasury "
                        f"goods_payment (currency={currency_value!r}); only domestic "
                        f"currency {DOMESTIC_CURRENCY!r} is allowed"
                    )
        # Trade-related kinds must use the kind-appropriate currency book.
        # The Treasury fiscal account exception (USD/CMEA export_receipt /
        # import_payment legs debiting the Treasury FISCAL_EXPENSE account)
        # does NOT extend to the foreign account; an ``export_receipt`` row
        # in the wrong book (e.g. domestic) or a ``loan_drawdown`` row in
        # the wrong book (e.g. CMEA) is rejected outright.
        if kind_value in ("export_receipt", "import_payment"):
            if currency_value not in (USD_CURRENCY, CMEA_CURRENCY):
                _fail_observer(
                    f"journal row {row_index} kind={kind_value!r} currency="
                    f"{currency_value!r}; only {USD_CURRENCY!r} or "
                    f"{CMEA_CURRENCY!r} is permitted for trade settlement"
                )
        elif kind_value in ("loan_drawdown", "interest_payment", "principal_repayment"):
            if currency_value not in (USD_CURRENCY, DOMESTIC_CURRENCY):
                _fail_observer(
                    f"journal row {row_index} kind={kind_value!r} currency="
                    f"{currency_value!r}; only {USD_CURRENCY!r} or "
                    f"{DOMESTIC_CURRENCY!r} is permitted (CMEA is not a "
                    "loan book)"
                )

    # Per-row account-currency compatibility.  Build the canonical account
    # directory (account id -> (owner_kind, owner_id, currency, account_kind))
    # and enforce:
    #   * the foreign trade-settlement accounts (foreign_usd, foreign_cmea)
    #     only appear in journal rows whose currency equals their directory
    #     currency (USD or CMEA respectively);
    #   * every non-fiscal account (organization / household / bank /
    #     Treasury cash / Treasury loan asset / plot clearing) must have its
    #     directory currency equal to the journal currency;
    #   * the documented Treasury fiscal bridge is the only exception:
    #     the Treasury ``FISCAL_EXPENSE`` account (domestic directory) may
    #     appear in USD or CMEA trade rows
    #     (``export_receipt``/``import_payment``/``loan_drawdown``/
    #     ``interest_payment``/``principal_repayment``) when the other side
    #     is the matching foreign account.  Outside trade rows or with a
    #     non-matching foreign counterparty the FISCAL_EXPENSE account must
    #     be domestic.
    account_directory_pre = build_account_directory(state)
    account_by_id_pre: dict[int, tuple[str, int, str, str]] = {}
    for key, account_id in account_directory_pre.items():
        if account_id in account_by_id_pre:
            _fail_observer(
                f"duplicate account id {account_id} in build_account_directory(state)"
            )
        account_by_id_pre[account_id] = key

    for row_index, kind_value in enumerate(flows.journal_kind):
        currency_value = str(flows.journal_currency[row_index])
        debit_id = int(flows.journal_debit[row_index])
        credit_id = int(flows.journal_credit[row_index])
        debit_key = account_by_id_pre.get(debit_id)
        credit_key = account_by_id_pre.get(credit_id)
        if debit_key is None:
            _fail_observer(
                f"journal row {row_index} debits unknown account {debit_id}"
            )
        if credit_key is None:
            _fail_observer(
                f"journal row {row_index} credits unknown account {credit_id}"
            )
        debit_owner, _, debit_dir_currency, _ = debit_key
        credit_owner, _, credit_dir_currency, _ = credit_key
        # Foreign trade-settlement accounts must match the journal currency.
        for side, owner, account_id in (
            ("debit", debit_owner, debit_id),
            ("credit", credit_owner, credit_id),
        ):
            if owner == "foreign_usd" and currency_value != USD_CURRENCY:
                _fail_observer(
                    f"journal row {row_index} kind={kind_value!r} {side} account "
                    f"{account_id} is foreign_usd but journal currency is "
                    f"{currency_value!r} (only {USD_CURRENCY!r} is permitted)"
                )
            if owner == "foreign_cmea" and currency_value != CMEA_CURRENCY:
                _fail_observer(
                    f"journal row {row_index} kind={kind_value!r} {side} account "
                    f"{account_id} is foreign_cmea but journal currency is "
                    f"{currency_value!r} (only {CMEA_CURRENCY!r} is permitted)"
                )
        # Treasury FISCAL_EXPENSE bridge exception.
        is_trade_row = kind_value in trade_kinds_pre
        if debit_id == treasury_fiscal_pre or credit_id == treasury_fiscal_pre:
            other_owner = credit_owner if debit_id == treasury_fiscal_pre else debit_owner
            if is_trade_row:
                if currency_value == USD_CURRENCY and other_owner == "foreign_usd":
                    pass
                elif currency_value == CMEA_CURRENCY and other_owner == "foreign_cmea":
                    pass
                else:
                    _fail_observer(
                        f"journal row {row_index} kind={kind_value!r} involves "
                        f"Treasury FISCAL_EXPENSE in {currency_value!r} trade row "
                        f"without the matching foreign counterparty "
                        f"(other owner={other_owner!r})"
                    )
            else:
                if currency_value != DOMESTIC_CURRENCY:
                    _fail_observer(
                        f"journal row {row_index} kind={kind_value!r} involves "
                        f"Treasury FISCAL_EXPENSE in non-trade row with "
                        f"currency={currency_value!r}; only domestic "
                        f"{DOMESTIC_CURRENCY!r} is permitted"
                    )
        # For non-fiscal accounts, directory currency must equal journal
        # currency.
        if debit_id != treasury_fiscal_pre and debit_owner not in (
            "foreign_usd",
            "foreign_cmea",
        ):
            if debit_dir_currency != currency_value:
                _fail_observer(
                    f"journal row {row_index} kind={kind_value!r} debits account "
                    f"{debit_id} (owner={debit_owner!r}, directory "
                    f"currency={debit_dir_currency!r}); journal currency "
                    f"{currency_value!r} does not match"
                )
        if credit_id != treasury_fiscal_pre and credit_owner not in (
            "foreign_usd",
            "foreign_cmea",
        ):
            if credit_dir_currency != currency_value:
                _fail_observer(
                    f"journal row {row_index} kind={kind_value!r} credits "
                    f"account {credit_id} (owner={credit_owner!r}, directory "
                    f"currency={credit_dir_currency!r}); journal currency "
                    f"{currency_value!r} does not match"
                )

    channel_views = _export_demand_axis(
        network=network,
        flows=flows,
        parameters=parameters,
        oil_price=oil_price,
        cmea_contract_price=cmea_contract_price,
    )

    # Treasury deposit (cash) account is the debit side of every
    # ``goods_payment`` journal row; the foreign-account and fiscal-account
    # bookkeeping is enforced inside the channel reconciliation helpers.
    treasury_cash = treasury_account_id(state, AccountKind.CASH_DEPOSIT)

    columns = _validate_journal_columns(flows)
    kind, tick_col, debit_col, credit_col, amount_col, currency_col, org_col, leg_col = columns

    # Per-channel journal reconciliation.
    _channel_journal_rows(
        flows=flows,
        state=state,
        opening=opening,
        channel=CMEA_CHANNEL,
        currency=CMEA_CURRENCY,
        export_receipt=float(flows.cmea_export_receipt),
        import_payment=float(flows.cmea_import_payment),
        columns=columns,
    )
    _channel_journal_rows(
        flows=flows,
        state=state,
        opening=opening,
        channel=USD_CHANNEL,
        currency=USD_CURRENCY,
        export_receipt=float(flows.usd_export_receipt),
        import_payment=float(flows.usd_import_payment),
        columns=columns,
    )

    # CMEA may legitimately carry no journal rows when both receipts and
    # payments are zero (legacy CMEA memo credit is in ``state.cmea_settlement_balance``,
    # not in the journal).  Empty journal is only allowed when every positive
    # settlement scalar is zero.
    positive_scalars = (
        float(flows.cmea_export_receipt),
        float(flows.usd_export_receipt),
        float(flows.cmea_import_payment),
        float(flows.usd_import_payment),
        float(flows.usd_loan_drawn),
        float(flows.usd_interest_paid),
        float(flows.usd_principal_paid),
    )
    if len(flows.journal_kind) == 0:
        if any(abs(value) > _strict_sum_tolerance(value) for value in positive_scalars):
            _fail_observer("empty journal with positive settlement scalars")

    # ---------------- domestic edges & Treasury payment pairs ----------------
    edge_purpose = np.asarray(network.edge_purpose, dtype=np.int64)
    edge_source = np.asarray(network.edge_source_cell, dtype=np.int64)
    edge_transport_org = np.asarray(network.edge_transport_org, dtype=np.int64)
    cell_owner_id = np.asarray(network.cell_owner_id, dtype=np.int64)
    cell_price = _cell_price_vector(parameters, network)

    organization_id_array = np.asarray(state.organization_id, dtype=np.int64)

    treasury_open = float(opening.treasury_deposit)
    treasury_close = float(state.treasury_deposit)

    export_edge_rows: list[dict[str, Any]] = []
    expected_payments: dict[int, float] = {}
    expected_freight_payments: dict[int, float] = {}
    housing_goods_total = 0.0
    housing_freight_total = 0.0

    for edge, purpose in enumerate(edge_purpose.tolist()):
        delivered = float(flows.edge_delivered[edge])
        fee = float(flows.edge_service_fee[edge])
        if delivered == 0.0:
            # Reject any strictly positive border fee (goods_payment is
            # delivered*price which is zero here, so the only remaining
            # payment on this edge is the freight).  Without this check the
            # fee disappears from payment expectations silently.
            if fee > 0.0:
                _fail_observer(
                    f"edge {edge} purpose={int(purpose)} carries strictly "
                    f"positive edge_service_fee={fee!r} while "
                    f"edge_delivered={delivered!r} is exactly zero"
                )
            continue
        source_cell = int(edge_source[edge])
        commodity_id = str(network.commodity_ids[int(network.cell_commodity[source_cell])])
        seller_id = int(cell_owner_id[source_cell])
        unit_price = float(cell_price[source_cell])
        goods_payment = delivered * unit_price
        if not math.isfinite(goods_payment):
            _fail_observer(
                f"edge {edge} goods_payment={goods_payment!r} is non-finite "
                f"(delivered={delivered!r}, unit_price={unit_price!r})"
            )
        transport_org = int(edge_transport_org[edge])
        carrier_id: int | None
        if transport_org >= 0:
            if transport_org >= int(organization_id_array.shape[0]):
                _fail_observer(
                    f"edge {edge} names transport org row {transport_org} "
                    "outside the organization axis"
                )
            carrier_id = int(organization_id_array[transport_org])
        else:
            carrier_id = None
        freight_payment = fee
        if not math.isfinite(freight_payment):
            _fail_observer(
                f"edge {edge} freight_payment={freight_payment!r} is non-finite"
            )

        if purpose == EXPORT_PURPOSES[0]:  # CMEA export
            channel_label = "CMEA"
        elif purpose == EXPORT_PURPOSES[1]:  # USD convertible export
            channel_label = "USD"
        else:
            continue  # domestic edges handled below via housing path

        export_edge_rows.append(
            {
                "edge_id": int(edge),
                "channel": channel_label,
                "commodity_id": commodity_id,
                "seller_id": seller_id,
                "carrier_id": carrier_id,
                "delivered": delivered,
                "goods_payment": goods_payment,
                "freight_payment": freight_payment,
            }
        )
        expected_payments[seller_id] = expected_payments.get(seller_id, 0.0) + goods_payment
        if carrier_id is not None:
            expected_freight_payments[carrier_id] = (
                expected_freight_payments.get(carrier_id, 0.0) + freight_payment
            )

    # Housing edges: declared via PURPOSE_HOUSING.  These pay from the same
    # Treasury deposit and must be folded into the per-payee expectation so
    # the raw goods_payment comparison is whole-economy accurate.
    housing_purpose_code = int(PURPOSE_CODES[RoutePurpose.HOUSING])
    for edge, purpose in enumerate(edge_purpose.tolist()):
        if purpose != housing_purpose_code:
            continue
        delivered = float(flows.edge_delivered[edge])
        fee = float(flows.edge_service_fee[edge])
        if delivered == 0.0:
            # Reject any strictly positive housing border fee when delivery
            # is exactly zero (goods_payment is delivered*price which is
            # zero here, so the fee would otherwise disappear silently).
            if fee > 0.0:
                _fail_observer(
                    f"housing edge {edge} carries strictly positive "
                    f"edge_service_fee={fee!r} while edge_delivered="
                    f"{delivered!r} is exactly zero"
                )
            continue
        source_cell = int(edge_source[edge])
        seller_id = int(cell_owner_id[source_cell])
        unit_price = float(cell_price[source_cell])
        goods_payment = delivered * unit_price
        if not math.isfinite(goods_payment):
            _fail_observer(
                f"housing edge {edge} goods_payment={goods_payment!r} is non-finite "
                f"(delivered={delivered!r}, unit_price={unit_price!r})"
            )
        transport_org = int(edge_transport_org[edge])
        carrier_id: int | None
        if transport_org >= 0:
            carrier_id = int(organization_id_array[transport_org])
        else:
            carrier_id = None
        freight_payment = fee
        if not math.isfinite(freight_payment):
            _fail_observer(
                f"housing edge {edge} freight_payment={freight_payment!r} is non-finite"
            )
        housing_goods_total += goods_payment
        housing_freight_total += freight_payment
        if not (math.isfinite(housing_goods_total) and math.isfinite(housing_freight_total)):
            _fail_observer(
                f"housing running totals are non-finite "
                f"(goods={housing_goods_total!r}, freight={housing_freight_total!r})"
            )
        expected_payments[seller_id] = expected_payments.get(seller_id, 0.0) + goods_payment
        if carrier_id is not None:
            expected_freight_payments[carrier_id] = (
                expected_freight_payments.get(carrier_id, 0.0) + freight_payment
            )

    # Aggregate journal Treasury cash_deposit credits by payee.
    goods_credits_by_payee: dict[int, float] = {}
    for index, kind_value in enumerate(flows.journal_kind):
        if kind_value != "goods_payment":
            continue
        if str(flows.journal_currency[index]) != DOMESTIC_CURRENCY:
            continue
        if int(flows.journal_debit[index]) != treasury_cash:
            continue
        credit_account = int(flows.journal_credit[index])
        amount = float(flows.journal_amount[index])
        existing = goods_credits_by_payee.get(credit_account, 0.0)
        goods_credits_by_payee[credit_account] = existing + amount

    # Map credit accounts back to canonical payee ids (an organization).
    account_directory = build_account_directory(state)
    payee_by_account: dict[int, int] = {}
    for key, account_id in account_directory.items():
        owner_kind, owner_id, _currency, account_kind = key
        if owner_kind == "organization" and account_kind == AccountKind.CASH_DEPOSIT:
            payee_by_account[account_id] = int(owner_id)

    observed_payment_by_payee: dict[int, float] = {}
    for credit_account, amount in goods_credits_by_payee.items():
        payee = payee_by_account.get(credit_account)
        if payee is None:
            _fail_observer(
                f"goods_payment journal credits unknown payee account {credit_account}"
            )
        observed_payment_by_payee[payee] = observed_payment_by_payee.get(payee, 0.0) + amount

    # All expected payees plus every observed Treasury credit payee must be in
    # the report (positive residual when observed > expected is also illegal).
    payee_ids = set(expected_payments) | set(observed_payment_by_payee) | set(
        expected_freight_payments
    )
    treasury_payment_pairs: list[dict[str, Any]] = []
    residuals_by_payee: dict[str, float] = {}
    for payee_id in sorted(payee_ids):
        expected = float(expected_payments.get(payee_id, 0.0)) + float(
            expected_freight_payments.get(payee_id, 0.0)
        )
        observed = float(observed_payment_by_payee.get(payee_id, 0.0))
        if not math.isfinite(expected):
            _fail_observer(
                f"payee {payee_id} expected payment total {expected!r} is non-finite"
            )
        if not math.isfinite(observed):
            _fail_observer(
                f"payee {payee_id} observed (journal) payment total {observed!r} is "
                "non-finite"
            )
        residual = observed - expected
        if not math.isfinite(residual):
            _fail_observer(
                f"payee {payee_id} residual {residual!r} is non-finite "
                f"(observed={observed!r}, expected={expected!r})"
            )
        tol = float(tolerance_for(observed, expected))
        if abs(residual) > tol:
            _fail_observer(
                f"Treasury payment residual for payee {payee_id}: "
                f"observed={observed!r} expected={expected!r} residual={residual!r} "
                f"tol={tol!r}"
            )
        treasury_payment_pairs.append(
            {
                "payee_id": int(payee_id),
                "expected_payment": expected,
                "journal_payment": observed,
                "residual": float(residual),
            }
        )
        residuals_by_payee[str(int(payee_id))] = float(residual)

    housing_payment_total = housing_goods_total + housing_freight_total
    if not math.isfinite(housing_payment_total):
        _fail_observer(
            f"housing_payment total {housing_payment_total!r} is non-finite "
            f"(goods={housing_goods_total!r}, freight={housing_freight_total!r})"
        )

    # ---------------- channel scalars: opening / closing / USD loan book ----
    usd_reserve_open = float(opening.usd_reserve)
    usd_reserve_close = float(state.usd_reserve)
    cmea_open = float(opening.cmea_settlement_balance)
    cmea_close = float(state.cmea_settlement_balance)

    if usd_reserve_open < 0.0 - float(tolerance_for(usd_reserve_open, 0.0)):
        _fail_observer(f"opening USD reserve {usd_reserve_open!r} is negative")
    if usd_reserve_close < 0.0 - float(tolerance_for(usd_reserve_close, 0.0)):
        _fail_observer(f"closing USD reserve {usd_reserve_close!r} is negative")

    usd_identity = (
        usd_reserve_open
        + float(flows.usd_loan_drawn)
        - float(flows.usd_interest_paid)
        - float(flows.usd_principal_paid)
        - float(flows.usd_import_payment)
        + float(flows.usd_export_receipt)
    )
    usd_residual = float(usd_reserve_close - usd_identity)
    if not math.isfinite(usd_residual):
        _fail_observer(
            f"USD reserve residual {usd_residual!r} is non-finite "
            f"(close={usd_reserve_close!r}, identity={usd_identity!r})"
        )
    tol_usd = float(tolerance_for(usd_reserve_close, usd_identity))
    if abs(usd_reserve_close - usd_identity) > tol_usd:
        _fail_observer(
            f"USD reserve identity violated: open={usd_reserve_open!r} "
            f"drawn={flows.usd_loan_drawn!r} interest={flows.usd_interest_paid!r} "
            f"principal={flows.usd_principal_paid!r} import={flows.usd_import_payment!r} "
            f"export={flows.usd_export_receipt!r} close={usd_reserve_close!r} "
            f"expected={usd_identity!r} tol={tol_usd!r}"
        )

    cmea_identity = cmea_open - float(flows.cmea_import_payment) + float(flows.cmea_export_receipt)
    cmea_residual = float(cmea_close - cmea_identity)
    if not math.isfinite(cmea_residual):
        _fail_observer(
            f"CMEA settlement residual {cmea_residual!r} is non-finite "
            f"(close={cmea_close!r}, identity={cmea_identity!r})"
        )
    tol_cmea = float(tolerance_for(cmea_close, cmea_identity))
    if abs(cmea_close - cmea_identity) > tol_cmea:
        _fail_observer(
            f"CMEA settlement identity violated: open={cmea_open!r} "
            f"import={flows.cmea_import_payment!r} export={flows.cmea_export_receipt!r} "
            f"close={cmea_close!r} expected={cmea_identity!r} tol={tol_cmea!r}"
        )

    usd_principal_open = float(opening.usd_principal)
    usd_principal_close = float(state.usd_principal)
    expected_usd_principal = (
        usd_principal_open
        + float(flows.usd_loan_drawn)
        - float(flows.usd_principal_paid)
    )
    usd_principal_residual = float(usd_principal_close - expected_usd_principal)
    if not math.isfinite(usd_principal_residual):
        _fail_observer(
            f"USD principal residual {usd_principal_residual!r} is non-finite"
        )
    tol_up = float(tolerance_for(usd_principal_close, expected_usd_principal))
    if abs(usd_principal_close - expected_usd_principal) > tol_up:
        _fail_observer(
            f"USD principal identity violated: open={usd_principal_open!r} "
            f"drawn={flows.usd_loan_drawn!r} paid={flows.usd_principal_paid!r} "
            f"close={usd_principal_close!r} expected={expected_usd_principal!r} "
            f"tol={tol_up!r}"
        )

    usd_arrears_open = float(opening.usd_interest_arrears)
    usd_arrears_close = float(state.usd_interest_arrears)
    expected_usd_arrears = (
        usd_arrears_open + float(flows.usd_interest_accrued) - float(flows.usd_interest_paid)
    )
    usd_arrears_residual = float(usd_arrears_close - expected_usd_arrears)
    if not math.isfinite(usd_arrears_residual):
        _fail_observer(
            f"USD interest-arrears residual {usd_arrears_residual!r} is non-finite"
        )
    tol_ua = float(tolerance_for(usd_arrears_close, expected_usd_arrears))
    if abs(usd_arrears_close - expected_usd_arrears) > tol_ua:
        _fail_observer(
            f"USD interest-arrears identity violated: open={usd_arrears_open!r} "
            f"accrued={flows.usd_interest_accrued!r} paid={flows.usd_interest_paid!r} "
            f"close={usd_arrears_close!r} expected={expected_usd_arrears!r} tol={tol_ua!r}"
        )

    channel_views[CMEA_CURRENCY]["balance_open"] = cmea_open
    channel_views[CMEA_CURRENCY]["balance_close"] = cmea_close
    channel_views[USD_CURRENCY]["balance_open"] = usd_reserve_open
    channel_views[USD_CURRENCY]["balance_close"] = usd_reserve_close
    channel_views[USD_CURRENCY]["principal_open"] = usd_principal_open
    channel_views[USD_CURRENCY]["principal_close"] = usd_principal_close
    channel_views[USD_CURRENCY]["loan_drawn"] = float(flows.usd_loan_drawn)
    channel_views[USD_CURRENCY]["principal_paid"] = float(flows.usd_principal_paid)
    channel_views[USD_CURRENCY]["interest_accrued"] = float(flows.usd_interest_accrued)
    channel_views[USD_CURRENCY]["interest_paid"] = float(flows.usd_interest_paid)
    channel_views[USD_CURRENCY]["interest_arrears_open"] = usd_arrears_open
    channel_views[USD_CURRENCY]["interest_arrears_close"] = usd_arrears_close
    channel_views[CMEA_CURRENCY]["balance_kind"] = "legacy_memo_credit"

    # ---------------- journal rows + identity residuals ---------------------
    directory_by_id = _index_account_keys(account_directory)
    journal_rows = _build_journal_rows(flows, state, directory=directory_by_id)

    identity_residuals: dict[str, Any] = {
        "usd_reserve": float(usd_residual),
        "usd_principal": float(usd_principal_residual),
        "usd_interest_arrears": float(usd_arrears_residual),
        "cmea_settlement": float(cmea_residual),
        # Use the channel axis view's ``expected_receipt`` (which is the
        # quantity-prices dot product, computed from the actual delivered
        # exports and the executed channel prices) rather than the flow
        # scalar itself; comparing the flow scalar against itself is
        # tautological and would always read zero.
        "export_receipt_by_currency": {
            USD_CURRENCY: float(channel_views[USD_CURRENCY]["expected_receipt"])
            - float(flows.usd_export_receipt),
            CMEA_CURRENCY: float(channel_views[CMEA_CURRENCY]["expected_receipt"])
            - float(flows.cmea_export_receipt),
        },
        "treasury_payment_by_payee": residuals_by_payee,
    }

    observation: dict[str, Any] = {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "regime_id": regime.regime_id,
        "source_kind": regime.source_kind,
        "tick": int(flows.tick),
        "quarter": str(flows.quarter),
        "commodity_ids": list(network.commodity_ids),
        "domestic": {
            "currency": DOMESTIC_CURRENCY,
            "treasury_open": treasury_open,
            "treasury_close": treasury_close,
            "export_edges": export_edge_rows,
            "housing_payment": float(housing_payment_total),
            "treasury_payment_pairs": treasury_payment_pairs,
        },
        "channels": channel_views,
        "journal": journal_rows,
        "identity_residuals": identity_residuals,
        "official_fx_translation": flows.official_fx_translation,
    }
    return observation


# ---------------------------------------------------------------------------
# Wrapper: opt-in entry point.
# ---------------------------------------------------------------------------


def _validate_opening_state(state: MaterialState) -> None:
    scalars = (
        ("usd_reserve", state.usd_reserve),
        ("usd_principal", state.usd_principal),
        ("usd_interest_arrears", state.usd_interest_arrears),
    )
    for name, value in scalars:
        v = float(value)
        if not math.isfinite(v):
            _reject(f"opening state {name}={v!r} must be finite")
        if v < 0.0 - float(tolerance_for(v, 0.0)):
            _reject(f"opening state {name}={v!r} must be non-negative")
    bank_reserves = np.asarray(state.bank_reserves, dtype=np.float64)
    if not np.all(np.isfinite(bank_reserves)):
        _reject("opening bank_reserves must be finite")
    tol = float(tolerance_for(0.0, 0.0))
    if np.any(bank_reserves < -tol):
        _reject("opening bank_reserves must be non-negative")


def _restore_state(state: MaterialState, snapshot: MaterialState) -> None:
    """Restore every MaterialState dataclass field from a pre-tick deep copy."""
    for field_name in state.__dataclass_fields__:
        setattr(state, field_name, copy.deepcopy(getattr(snapshot, field_name)))


def execute_legacy_trade_tick(
    state: MaterialState,
    forcing: MaterialForcing,
    parameters: MaterialParameters,
    network: MaterialNetwork,
    *,
    regime: LegacyTradeRegime,
) -> LegacyTradeResult:
    """Run one H3F-D0 legacy trade tick and advance only on a full pass.

    Validation happens before any state mutation.  The single real tick is
    admitted only if the existing material/financial gate and the new
    observer both pass.  On any later failure, the failed flows/state are
    copied for diagnosis, every mutable state field is restored, the clock is
    not advanced, and :class:`LegacyTradeFailure` is raised.
    """
    if not isinstance(regime, LegacyTradeRegime):
        raise LegacyTradeFailure(
            phase="regime",
            cause=ResearchGateError(
                f"{GATE_PREFIX}: regime is not a LegacyTradeRegime instance"
            ),
            failed_flows=None,
            failed_state=None,
        )
    tick = int(state.completed_ticks)
    quarters = list(forcing.quarters)
    if not (0 <= tick < len(quarters)):
        raise LegacyTradeFailure(
            phase="forcing",
            cause=ResearchGateError(
                f"{GATE_PREFIX}: tick {tick} lies outside the forcing horizon "
                f"({len(quarters)} quarters)"
            ),
            failed_flows=None,
            failed_state=None,
        )

    try:
        _validate_opening_state(state)
    except ResearchGateError as exc:
        raise LegacyTradeFailure(
            phase="opening_state",
            cause=exc,
            failed_flows=None,
            failed_state=None,
        ) from exc

    before = copy.deepcopy(state)
    opening = capture_material_stocks(state)
    flows: MaterialTickFlows | None = None
    phase = "tick_material"
    try:
        flows = tick_material(state, forcing, parameters, network)
        phase = "invariants"
        summary = accounting.check_material_invariants(
            opening, state, flows, parameters, network
        )
        phase = "observer"
        observation = observe_legacy_trade_tick(
            opening,
            state,
            flows,
            parameters,
            network,
            regime=regime,
            oil_price=float(forcing.oil_price[tick]),
            cmea_contract_price=float(forcing.cmea_energy_price[tick]),
        )
    except Exception as exc:  # noqa: BLE001 - every failure must roll back
        failed_flows = copy.deepcopy(flows) if flows is not None else None
        failed_state = copy.deepcopy(state)
        _restore_state(state, before)
        raise LegacyTradeFailure(
            phase=phase,
            cause=exc,
            failed_flows=failed_flows,
            failed_state=failed_state,
        ) from exc

    state.completed_ticks = int(before.completed_ticks) + 1
    return LegacyTradeResult(
        flows=flows,
        gate=summary,
        observation=observation,
    )


# Avoid an unused-import warning: the Symbol export list documents the
# canonical public surface (loader, observer, wrapper, result, failure).
__all__ = [
    "LegacyTradeFailure",
    "LegacyTradeRegime",
    "LegacyTradeResult",
    "execute_legacy_trade_tick",
    "load_legacy_trade_regime",
    "observe_legacy_trade_tick",
]
