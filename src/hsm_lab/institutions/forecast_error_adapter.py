"""H5F-F1: issued -> realized forecast residual adapter (M9).

This module is deliberately narrow.  It turns two already-published, closed
actor observations into one issued prediction, and later scores that frozen
prediction against one realized physical quantity.  It never reads the engine,
state, forcing, files, callbacks or the future: every input is a scalar,
tuple, plain ``date`` or a certified :class:`ActorObservation`.

The legacy ``forecast_accuracy`` entry in ``engine.technology`` is a
capability-derived definition, not an error measurement.  These objects are the
measurement counterpart and do not reuse that number.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Literal

from hsm_lab.contract.base import ConfigError, StrictModel
from hsm_lab.contract.schemas import Quarter
from hsm_lab.institutions.observed import ActorObservation, verify_observation_invariants
from hsm_lab.provenance.manifest import canonical_digest

SCHEMA_VERSION = "hist_vnext_h5f_f1_forecast_v1"
METHODS = ("persistence", "linear")
_COMMODITY_ID = "energy"
_STAGE = "standard"
_UNIT = "p02_energy_unit"
_ACTOR_ROLE = "procurement_organization"


# ---------------------------------------------------------------------------
# Quarter / date helpers (pure calendar arithmetic, no engine state)
# ---------------------------------------------------------------------------


def quarter_end(value: str) -> date:
    """Return the last calendar day of a ``YYYYQ[1-4]`` quarter."""
    quarter = Quarter.parse(value)
    if quarter.quarter == 1:
        return date(quarter.year, 3, 31)
    if quarter.quarter == 2:
        return date(quarter.year, 6, 30)
    if quarter.quarter == 3:
        return date(quarter.year, 9, 30)
    return date(quarter.year, 12, 31)


def quarter_day(value: str, day: int) -> date:
    """Return ``day`` in the first month of a quarter (synthetic issue dates)."""
    quarter = Quarter.parse(value)
    month = {1: 1, 2: 4, 3: 7, 4: 10}[quarter.quarter]
    return date(quarter.year, month, day)


def _ordinal(value: str) -> int:
    return Quarter.parse(value).to_ordinal()


def _is_hex64(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


# ---------------------------------------------------------------------------
# Model storage custody (model_construct / shadowed field rejection)
# ---------------------------------------------------------------------------


def _model_storage_violation(obj: Any, cls: type[Any]) -> str | None:
    """Reject non-exact instances and model-construct/shadowed storage."""
    if type(obj) is not cls:
        return f"expected an exact {cls.__name__}"
    declared = set(cls.model_fields.keys())
    try:
        extra = object.__getattribute__(obj, "__pydantic_extra__")
        private = object.__getattribute__(obj, "__pydantic_private__")
        fields_set = object.__getattribute__(obj, "__pydantic_fields_set__")
        instance = object.__getattribute__(obj, "__dict__")
    except AttributeError:
        return f"{cls.__name__} storage is unavailable"
    if extra is not None:
        return f"{cls.__name__} __pydantic_extra__ must be empty"
    if private is not None:
        return f"{cls.__name__} __pydantic_private__ must be empty"
    if type(fields_set) is not set:
        return f"{cls.__name__} metadata is malformed"
    for name in fields_set:
        if type(name) is not str or name not in declared:
            return f"{cls.__name__} metadata contains an unvalidated field name"
    if type(instance) is not dict:
        return f"{cls.__name__} storage is malformed"
    if len(instance) != len(declared):
        return f"{cls.__name__} storage is missing declared fields"
    for key in instance:
        if type(key) is not str or key not in declared:
            return f"{cls.__name__} storage contains an undeclared field"
    return None


def _exact_str(value: Any, name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be exactly str")
    if not value:
        raise ValueError(f"{name} must be non-empty")
    return value


def _exact_date(value: Any, name: str) -> date:
    if type(value) is not date:
        raise TypeError(f"{name} must be a plain date")
    return value


def _finite_nonnegative(value: Any, name: str) -> float:
    if type(value) not in (int, float):
        raise TypeError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if result < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return result


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class ForecastReport(StrictModel):
    """One closed, published observation of a quarter's physical output.

    ``observation`` is the actor's certified view at the decision point:
    ``observation.quarter`` is the decision quarter and ``observation.available_at``
    is the publication date.  The measured quarter is carried separately so a
    stale measurement is never relabelled as the current quarter.
    """

    observation: ActorObservation
    measurement_quarter: str
    subject_organization_id: str
    commodity_id: str
    stage: str
    unit: str


def _report_violation(report: Any) -> str | None:
    violation = _model_storage_violation(report, ForecastReport)
    if violation is not None:
        return violation
    observation = object.__getattribute__(report, "observation")
    try:
        observation_violations = verify_observation_invariants(observation)
    except Exception as exc:  # noqa: BLE001 - boundary: refuse, do not execute payloads
        return f"observation invariant verification failed: {exc}"
    if observation_violations:
        return "observation invariant violation: " + "; ".join(observation_violations)
    if object.__getattribute__(observation, "actor_role") != _ACTOR_ROLE:
        return "forecast report observation must use the procurement organization role"
    fields = {
        name: object.__getattribute__(report, name)
        for name in (
            "measurement_quarter",
            "subject_organization_id",
            "commodity_id",
            "stage",
            "unit",
        )
    }
    for name, value in fields.items():
        if type(value) is not str or not value:
            return f"report {name} must be a non-empty exact str"
    try:
        Quarter.parse(fields["measurement_quarter"])
        issued_quarter = object.__getattribute__(observation, "quarter")
        Quarter.parse(issued_quarter)
        supply = observation.get_field("supply_quantity")
    except (ConfigError, KeyError, TypeError, ValueError) as exc:
        return f"forecast report is malformed: {exc}"
    if type(supply) not in (int, float) or not math.isfinite(supply) or supply < 0.0:
        return "report supply_quantity must be a finite non-negative number"
    if _ordinal(fields["measurement_quarter"]) >= _ordinal(issued_quarter):
        return "report measurement quarter must precede the observation quarter"
    if object.__getattribute__(observation, "available_at") < quarter_end(
        fields["measurement_quarter"]
    ):
        return "report cannot be published before its measurement quarter closes"
    return None


def _report_supply(report: ForecastReport) -> float:
    return float(object.__getattribute__(report, "observation").get_field("supply_quantity"))


# ---------------------------------------------------------------------------
# Issued / realized / residual records
# ---------------------------------------------------------------------------


class IssuedForecast(StrictModel):
    """A frozen prediction made from exactly two published reports."""

    schema_version: Literal["hist_vnext_h5f_f1_forecast_v1"] = SCHEMA_VERSION
    forecast_id: str
    run_id: str
    seed: int
    arm_id: str
    method: str
    actor_organization_id: str
    actor_sector_id: str
    actor_geographic_id: str
    subject_organization_id: str
    commodity_id: str
    stage: str
    unit: str
    issued_quarter: str
    issued_at: date
    older_measurement_quarter: str
    newer_measurement_quarter: str
    older_available_at: date
    newer_available_at: date
    available_at: date
    target_quarter: str
    horizon_quarters: int = 1
    older_value: float
    newer_value: float
    prediction: float
    raw_prediction: float
    clipping_delta: float
    input_observation_sha256: str


class RealizedForecast(StrictModel):
    """One physical realization for a previously issued target quarter."""

    schema_version: Literal["hist_vnext_h5f_f1_forecast_v1"] = SCHEMA_VERSION
    forecast_id: str
    run_id: str
    seed: int
    arm_id: str
    subject_organization_id: str
    commodity_id: str
    stage: str
    unit: str
    target_quarter: str
    measurement_quarter: str
    realized_at: date
    realized_value: float
    kernel_tick: int
    kernel_quarter: str
    witness_sha256: str


class ForecastResidual(StrictModel):
    """Signed forecast error; MAE is computed only over a complete target set."""

    schema_version: Literal["hist_vnext_h5f_f1_forecast_v1"] = SCHEMA_VERSION
    forecast_id: str
    run_id: str
    seed: int
    arm_id: str
    method: str
    subject_organization_id: str
    commodity_id: str
    stage: str
    unit: str
    issued_quarter: str
    target_quarter: str
    prediction: float
    realized_value: float
    residual: float
    absolute_error: float


# ---------------------------------------------------------------------------
# Issuance
# ---------------------------------------------------------------------------


def _observation_hash(reports: tuple[ForecastReport, ForecastReport]) -> str:
    payload = [
        {
            "measurement_quarter": str(report.measurement_quarter),
            "observation": report.observation.to_dict(),
        }
        for report in reports
    ]
    return canonical_digest(payload)


def issue_forecast(
    reports: tuple[ForecastReport, ...],
    *,
    forecast_id: str,
    run_id: str,
    seed: int,
    arm_id: str,
    issued_quarter: str,
    issued_at: date,
    target_quarter: str,
    method: str,
) -> IssuedForecast:
    """Issue one prediction from two consecutive published reports.

    The prediction is a pure function of the reported physical quantities.
    ``persistence`` copies the newer report; ``linear`` performs one
    two-point O(1) extrapolation on quarter ordinals, then clips at zero.
    """
    if type(reports) is not tuple:
        raise TypeError("reports must be exactly tuple")
    if len(reports) != 2:
        raise ValueError("exactly two published reports are required")
    for report in reports:
        violation = _report_violation(report)
        if violation is not None:
            raise ValueError(f"invalid forecast report: {violation}")

    forecast_id = _exact_str(forecast_id, "forecast_id")
    run_id = _exact_str(run_id, "run_id")
    arm_id = _exact_str(arm_id, "arm_id")
    issued_quarter = _exact_str(issued_quarter, "issued_quarter")
    target_quarter = _exact_str(target_quarter, "target_quarter")
    method = _exact_str(method, "method")
    issued_at = _exact_date(issued_at, "issued_at")
    if type(seed) is not int or seed < 0:
        raise TypeError("seed must be a non-negative exact int")
    if method not in METHODS:
        raise ValueError(f"unknown forecast method {method!r}")

    try:
        issued_ordinal = _ordinal(issued_quarter)
        target_ordinal = _ordinal(target_quarter)
        report_ordinals = [
            _ordinal(str(object.__getattribute__(report, "measurement_quarter")))
            for report in reports
        ]
    except ConfigError as exc:
        raise ValueError(f"invalid quarter: {exc}") from exc
    if target_ordinal - issued_ordinal != 1:
        raise ValueError("target quarter must be exactly one quarter after issuance")
    if any(ordinal >= issued_ordinal for ordinal in report_ordinals):
        raise ValueError("a report cannot be measured in the issue quarter or later")
    if sorted(report_ordinals) != list(
        range(min(report_ordinals), min(report_ordinals) + 2)
    ):
        raise ValueError("the two reports must be consecutive quarters")
    if len(set(report_ordinals)) != 2:
        raise ValueError("the two reports must be distinct quarters")

    ordered = sorted(reports, key=lambda value: _ordinal(value.measurement_quarter))
    older, newer = ordered

    for name in (
        "subject_organization_id",
        "commodity_id",
        "stage",
        "unit",
    ):
        if object.__getattribute__(older, name) != object.__getattribute__(
            newer, name
        ):
            raise ValueError(f"reports mix {name}")
    subject = object.__getattribute__(newer, "subject_organization_id")
    commodity_id = object.__getattribute__(newer, "commodity_id")
    stage = object.__getattribute__(newer, "stage")
    unit = object.__getattribute__(newer, "unit")
    if (commodity_id, stage, unit) != (_COMMODITY_ID, _STAGE, _UNIT):
        raise ValueError("this phase measures energy/standard in p02_energy_unit")

    actor_organization_id = object.__getattribute__(newer.observation, "organization_id")
    actor_sector_id = object.__getattribute__(newer.observation, "sector_id")
    actor_geographic_id = object.__getattribute__(newer.observation, "geographic_id")
    for report in reports:
        observation = report.observation
        if object.__getattribute__(observation, "quarter") != issued_quarter:
            raise ValueError("report observation is not made in the issue quarter")
        if object.__getattribute__(observation, "decision_at") != issued_at:
            raise ValueError("report observation decision date does not match issuance")
        if object.__getattribute__(observation, "available_at") > issued_at:
            raise ValueError("report is not published by the issue date")
        if (
            object.__getattribute__(observation, "organization_id"),
            object.__getattribute__(observation, "sector_id"),
            object.__getattribute__(observation, "geographic_id"),
        ) != (
            actor_organization_id,
            actor_sector_id,
            actor_geographic_id,
        ):
            raise ValueError("reports mix the observing actor identity")

    older_value = _report_supply(older)
    newer_value = _report_supply(newer)
    older_ordinal = _ordinal(str(older.measurement_quarter))
    newer_ordinal = _ordinal(str(newer.measurement_quarter))

    if method == "persistence":
        raw_prediction = newer_value
    else:
        raw_prediction = newer_value + (target_ordinal - newer_ordinal) * (
            (newer_value - older_value) / (newer_ordinal - older_ordinal)
        )
    prediction = max(0.0, float(raw_prediction))
    clipping_delta = prediction - float(raw_prediction)

    older_available = object.__getattribute__(older.observation, "available_at")
    newer_available = object.__getattribute__(newer.observation, "available_at")
    available_at = max(older_available, newer_available)
    if available_at > issued_at:
        raise ValueError("inputs are not available by the issue date")

    expected_id = (
        f"{run_id}:{issued_quarter}:{target_quarter}:{commodity_id}:{stage}:{subject}"
    )
    if forecast_id != expected_id:
        raise ValueError("forecast_id does not match the declared identity")

    return IssuedForecast(
        forecast_id=forecast_id,
        run_id=run_id,
        seed=seed,
        arm_id=arm_id,
        method=method,
        actor_organization_id=actor_organization_id,
        actor_sector_id=actor_sector_id,
        actor_geographic_id=actor_geographic_id,
        subject_organization_id=subject,
        commodity_id=commodity_id,
        stage=stage,
        unit=unit,
        issued_quarter=issued_quarter,
        issued_at=issued_at,
        older_measurement_quarter=str(older.measurement_quarter),
        newer_measurement_quarter=str(newer.measurement_quarter),
        older_available_at=older_available,
        newer_available_at=newer_available,
        available_at=available_at,
        target_quarter=target_quarter,
        horizon_quarters=target_ordinal - issued_ordinal,
        older_value=older_value,
        newer_value=newer_value,
        prediction=prediction,
        raw_prediction=float(raw_prediction),
        clipping_delta=clipping_delta,
        input_observation_sha256=_observation_hash((older, newer)),
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _issued_violation(issued: Any) -> str | None:
    violation = _model_storage_violation(issued, IssuedForecast)
    if violation is not None:
        return violation
    for name in (
        "forecast_id",
        "run_id",
        "arm_id",
        "method",
        "actor_organization_id",
        "actor_sector_id",
        "actor_geographic_id",
        "subject_organization_id",
        "commodity_id",
        "stage",
        "unit",
        "issued_quarter",
        "target_quarter",
    ):
        if type(object.__getattribute__(issued, name)) is not str:
            return f"issued {name} must be exactly str"
    for name in (
        "issued_at",
        "older_available_at",
        "newer_available_at",
        "available_at",
    ):
        if type(object.__getattribute__(issued, name)) is not date:
            return f"issued {name} must be a plain date"
    if type(object.__getattribute__(issued, "seed")) is not int:
        return "issued seed must be exactly int"
    if object.__getattribute__(issued, "method") not in METHODS:
        return "issued method is not recognized"
    if (
        issued.commodity_id,
        issued.stage,
        issued.unit,
    ) != (_COMMODITY_ID, _STAGE, _UNIT):
        return "issued forecast is not energy/standard/p02_energy_unit"
    try:
        issued_ordinal = _ordinal(issued.issued_quarter)
        target_ordinal = _ordinal(issued.target_quarter)
        older_ordinal = _ordinal(issued.older_measurement_quarter)
        newer_ordinal = _ordinal(issued.newer_measurement_quarter)
    except (ConfigError, TypeError, ValueError) as exc:
        return f"issued quarter is malformed: {exc}"
    if target_ordinal - issued_ordinal != 1:
        return "issued target is not exactly one quarter ahead"
    if object.__getattribute__(issued, "horizon_quarters") != 1:
        return "issued horizon must be one quarter"
    if newer_ordinal - older_ordinal != 1 or newer_ordinal >= issued_ordinal:
        return "issued reports are not two consecutive closed quarters"
    if issued.older_available_at < quarter_end(issued.older_measurement_quarter):
        return "older report was published before its measurement quarter closed"
    if issued.newer_available_at < quarter_end(issued.newer_measurement_quarter):
        return "newer report was published before its measurement quarter closed"
    if issued.available_at > issued.issued_at:
        return "issued forecast uses information after its decision date"
    if issued.available_at != max(issued.older_available_at, issued.newer_available_at):
        return "issued available_at is inconsistent"
    for name in (
        "older_value",
        "newer_value",
        "prediction",
        "raw_prediction",
        "clipping_delta",
    ):
        value = object.__getattribute__(issued, name)
        if type(value) is not float or not math.isfinite(value):
            return f"issued {name} must be a finite float"
    if issued.prediction != max(0.0, issued.raw_prediction):
        return "issued prediction is not the clipped raw prediction"
    if issued.clipping_delta != issued.prediction - issued.raw_prediction:
        return "issued clipping delta is inconsistent"
    if issued.older_value < 0.0 or issued.newer_value < 0.0:
        return "issued report values must be non-negative"
    if issued.method == "persistence":
        expected_raw = issued.newer_value
    else:
        expected_raw = issued.newer_value + (target_ordinal - newer_ordinal) * (
            (issued.newer_value - issued.older_value)
            / (newer_ordinal - older_ordinal)
        )
    if abs(issued.raw_prediction - expected_raw) > 1e-9:
        return "issued raw prediction does not recompute from the reports"
    if abs(issued.prediction - max(0.0, expected_raw)) > 1e-9:
        return "issued prediction does not recompute from the reports"
    if not _is_hex64(object.__getattribute__(issued, "input_observation_sha256")):
        return "issued input hash is malformed"
    expected_id = (
        f"{issued.run_id}:{issued.issued_quarter}:{issued.target_quarter}:"
        f"{issued.commodity_id}:{issued.stage}:{issued.subject_organization_id}"
    )
    if issued.forecast_id != expected_id:
        return "issued forecast_id does not match its identity"
    return None


def _realized_violation(realized: Any) -> str | None:
    violation = _model_storage_violation(realized, RealizedForecast)
    if violation is not None:
        return violation
    for name in (
        "forecast_id",
        "run_id",
        "arm_id",
        "subject_organization_id",
        "commodity_id",
        "stage",
        "unit",
        "target_quarter",
        "measurement_quarter",
        "kernel_quarter",
    ):
        if type(object.__getattribute__(realized, name)) is not str:
            return f"realized {name} must be exactly str"
    if type(object.__getattribute__(realized, "seed")) is not int:
        return "realized seed must be exactly int"
    if type(object.__getattribute__(realized, "kernel_tick")) is not int:
        return "realized kernel_tick must be exactly int"
    if type(object.__getattribute__(realized, "realized_at")) is not date:
        return "realized_at must be a plain date"
    value = object.__getattribute__(realized, "realized_value")
    if type(value) is not float or not math.isfinite(value) or value < 0.0:
        return "realized_value must be a finite non-negative float"
    if not _is_hex64(object.__getattribute__(realized, "witness_sha256")):
        return "realized witness hash is malformed"
    if (
        realized.commodity_id,
        realized.stage,
        realized.unit,
    ) != (_COMMODITY_ID, _STAGE, _UNIT):
        return "realized forecast is not energy/standard/p02_energy_unit"
    if realized.kernel_tick < 0:
        return "realized kernel tick must be non-negative"
    try:
        _ordinal(realized.target_quarter)
    except (ConfigError, TypeError, ValueError) as exc:
        return f"realized target quarter is malformed: {exc}"
    if realized.measurement_quarter != realized.target_quarter:
        return "realized measurement quarter must equal the target quarter"
    if realized.kernel_quarter != realized.target_quarter:
        return "realized kernel quarter must equal the target quarter"
    return None


def score_forecast(issued: IssuedForecast, realized: RealizedForecast) -> ForecastResidual:
    """Pair a frozen forecast with its realization and return signed error.

    The scorer is stateless: duplicate/conflict rejection belongs to the
    runner ledger.  A missing realization stays pending and is never imputed.
    """
    issued_violation = _issued_violation(issued)
    if issued_violation is not None:
        raise ValueError(f"invalid issued forecast: {issued_violation}")
    realized_violation = _realized_violation(realized)
    if realized_violation is not None:
        raise ValueError(f"invalid realization: {realized_violation}")

    join_fields = (
        "forecast_id",
        "run_id",
        "arm_id",
        "subject_organization_id",
        "commodity_id",
        "stage",
        "unit",
        "target_quarter",
    )
    for name in join_fields:
        if object.__getattribute__(issued, name) != object.__getattribute__(
            realized, name
        ):
            raise ValueError(f"issued and realized forecasts do not share {name}")
    if issued.seed != realized.seed:
        raise ValueError("issued and realized forecasts do not share the seed")
    if realized.realized_at < quarter_end(issued.target_quarter):
        raise ValueError("realization cannot precede the target quarter close")

    residual = float(realized.realized_value) - float(issued.prediction)
    return ForecastResidual(
        forecast_id=issued.forecast_id,
        run_id=issued.run_id,
        seed=issued.seed,
        arm_id=issued.arm_id,
        method=issued.method,
        subject_organization_id=issued.subject_organization_id,
        commodity_id=issued.commodity_id,
        stage=issued.stage,
        unit=issued.unit,
        issued_quarter=issued.issued_quarter,
        target_quarter=issued.target_quarter,
        prediction=issued.prediction,
        realized_value=realized.realized_value,
        residual=residual,
        absolute_error=abs(residual),
    )


__all__ = [
    "ForecastReport",
    "ForecastResidual",
    "IssuedForecast",
    "METHODS",
    "RealizedForecast",
    "SCHEMA_VERSION",
    "issue_forecast",
    "quarter_day",
    "quarter_end",
    "score_forecast",
]
