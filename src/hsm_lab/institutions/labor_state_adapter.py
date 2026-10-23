"""H5D M3 labour institution adapter (default off).

The adapter implements the accepted ``hist-vnext-labor-institution-v1``
contract as an *external* sidecar:

* ``LaborRecipe`` maps only the frozen spec fields, with no new economic
  defaults of its own.
* ``LaborSidecar`` carries establishment, headcount, absence, effort, the
  previous-quarter signals and the spec/rules identity.  It never enters
  ``MaterialState`` or ``MaterialTickFlows``, so the legacy array field set,
  canonical bytes and checkpoint versions are untouched.
* ``LaborTickPlan`` is prepared before ``tick_material`` and consumed inside
  the tick (before ``plan_household_time``) and by the invariant gate.
* ``LaborDiagnostics`` holds the reported counts/shares; undefined ratios are
  reported as ``None`` (JSON ``null``), never as NaN, 1 or 0.

Every array is copied and made read-only on construction.  No global state is
touched.  Configuration and shape/axis problems raise ``ConfigError``; a
runtime labour-ledger violation raises ``AccountingError``; nothing falls back
to a disabled state.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from hsm_lab.contract.base import ConfigError, ResearchGateError
from hsm_lab.engine.accounting import AccountingError, tolerance_for
from hsm_lab.engine.state import MaterialState, MaterialTickFlows
from hsm_lab.provenance.manifest import canonical_digest

SIDECAR_SCHEMA_VERSION = "hist_vnext_h5d_labor_sidecar_v1"
BUNDLE_SCHEMA_VERSION = "hist_vnext_h5d_labor_bundle_v1"
ADAPTER_SCHEMA_VERSION = "hist_vnext_h5d_labor_adapter_v1"



# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _readonly(array: np.ndarray, dtype: Any) -> np.ndarray:
    result = np.array(array, dtype=dtype, copy=True, order="C")
    result.setflags(write=False)
    return result


def _as_float_array(value: Any, name: str, ndim: int) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != ndim:
        raise ConfigError(f"{name} must be {ndim}-dimensional, got shape {array.shape}")
    if not bool(np.all(np.isfinite(array))):
        raise ConfigError(f"{name} must be finite")
    return _readonly(array, np.float64)


def _as_id_array(value: Any, name: str) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim != 1:
        raise ConfigError(f"{name} must be one-dimensional, got shape {array.shape}")
    if not np.issubdtype(array.dtype, np.integer):
        raise ConfigError(f"{name} must carry integer ids, got dtype {array.dtype}")
    if np.any(array < 0):
        raise ConfigError(f"{name} must carry non-negative ids")
    return _readonly(array, np.int64)


def _finite_scalar(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ConfigError(f"{name} must be a finite number, got a bool")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} must be a finite number, got {value!r}") from exc
    if not math.isfinite(result):
        raise ConfigError(f"{name} must be finite, got {value!r}")
    return result


def _fraction(value: Any, name: str) -> float:
    result = _finite_scalar(value, name)
    if not 0.0 <= result <= 1.0:
        raise ConfigError(f"{name} must lie in [0, 1], got {result!r}")
    return result


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ConfigError(f"{name} must be a 64-character sha256 hex string")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ConfigError(f"{name} must be hexadecimal") from exc
    return value.lower()


def _shape(array: np.ndarray, length: int, name: str) -> None:
    if array.shape != (length,):
        raise ConfigError(f"{name} must have shape ({length},), got {array.shape}")


def _nonnegative(array: np.ndarray, name: str) -> None:
    if bool(np.any(array < 0.0)):
        raise ConfigError(f"{name} must be non-negative")


def _unit_interval(array: np.ndarray, name: str) -> None:
    if bool(np.any(array < 0.0)) or bool(np.any(array > 1.0)):
        raise ConfigError(f"{name} must lie in [0, 1]")


# ---------------------------------------------------------------------------
# recipe
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LaborRecipe:
    """Frozen mapping of the accepted spec; no economic default is invented."""

    spec_sha256: str
    rules_sha256: str
    hours_per_we: float
    endowment_hours: float
    target_utilization: float
    hire_capacity_share: float
    max_release_fraction: float
    absence_default: float
    absence_upper_bound: float
    effort_grievance_weight: float
    effort_informal_hours_weight: float
    effort_queue_search_weight: float
    effort_floor: float

    def __post_init__(self) -> None:
        _sha(self.spec_sha256, "recipe.spec_sha256")
        _sha(self.rules_sha256, "recipe.rules_sha256")
        for name in (
            "hours_per_we",
            "endowment_hours",
            "target_utilization",
            "hire_capacity_share",
            "max_release_fraction",
            "absence_default",
            "absence_upper_bound",
            "effort_grievance_weight",
            "effort_informal_hours_weight",
            "effort_queue_search_weight",
            "effort_floor",
        ):
            object.__setattr__(self, name, _finite_scalar(getattr(self, name), f"recipe.{name}"))
        if self.hours_per_we <= 0.0 or self.endowment_hours <= 0.0:
            raise ConfigError("recipe hours constants must be positive")
        if not 0.0 < self.target_utilization <= 1.0:
            raise ConfigError("recipe.target_utilization must lie in (0, 1]")
        if not 0.0 < self.hire_capacity_share <= 1.0:
            raise ConfigError("recipe.hire_capacity_share must lie in (0, 1]")
        if not 0.0 <= self.max_release_fraction <= 1.0:
            raise ConfigError("recipe.max_release_fraction must lie in [0, 1]")
        if not 0.0 <= self.absence_default <= self.absence_upper_bound <= 1.0:
            raise ConfigError("recipe absence bounds must satisfy 0 <= default <= bound <= 1")
        for name in (
            "effort_grievance_weight",
            "effort_informal_hours_weight",
            "effort_queue_search_weight",
            "effort_floor",
        ):
            _fraction(getattr(self, name), f"recipe.{name}")

    @classmethod
    def from_spec(cls, spec: Mapping[str, Any], *, spec_sha256: str) -> LaborRecipe:
        """Map the accepted spec keys; reject anything structurally missing."""
        if spec.get("schema_version") != "hist_vnext_labor_institution_spec_v1":
            raise ConfigError("labor recipe requires the accepted spec schema")
        units = spec.get("unit_contract")
        rules = spec.get("rules")
        if not isinstance(units, Mapping) or not isinstance(rules, Mapping):
            raise ConfigError("labor spec lacks unit_contract/rules")
        try:
            establishment = rules["establishment"]
            hire = rules["hire"]
            release = rules["release"]
            absence = rules["absence"]
            effort = rules["effort"]
            values = {
                "hours_per_we": units["hours_per_worker_equivalent_quarter"],
                "endowment_hours": units["hours_per_worker_quarter_endowment"],
                "target_utilization": establishment["target_utilization"],
                "hire_capacity_share": hire["hire_capacity_share_per_quarter"],
                "max_release_fraction": release["max_release_fraction_per_quarter"],
                "absence_default": absence["absence_default"],
                "absence_upper_bound": absence["absence_upper_bound"],
                "effort_grievance_weight": effort["effort_grievance_weight"],
                "effort_informal_hours_weight": effort["effort_informal_hours_weight"],
                "effort_queue_search_weight": effort["effort_queue_search_weight"],
                "effort_floor": effort["effort_floor"],
            }
        except (KeyError, TypeError) as exc:
            raise ConfigError(f"labor spec rule key missing: {exc}") from exc
        return cls(
            spec_sha256=spec_sha256,
            rules_sha256=canonical_digest(spec["rules"]),
            **values,
        )

    def identity(self) -> dict[str, Any]:
        return {
            "spec_sha256": self.spec_sha256,
            "rules_sha256": self.rules_sha256,
            "hours_per_we": self.hours_per_we,
            "endowment_hours": self.endowment_hours,
            "target_utilization": self.target_utilization,
            "hire_capacity_share": self.hire_capacity_share,
            "max_release_fraction": self.max_release_fraction,
            "absence_default": self.absence_default,
            "absence_upper_bound": self.absence_upper_bound,
            "effort_grievance_weight": self.effort_grievance_weight,
            "effort_informal_hours_weight": self.effort_informal_hours_weight,
            "effort_queue_search_weight": self.effort_queue_search_weight,
            "effort_floor": self.effort_floor,
        }


# ---------------------------------------------------------------------------
# sidecar
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LaborSidecar:
    schema_version: str
    completed_ticks: int
    signal_tick: int | None
    organization_ids: np.ndarray
    region_ids: np.ndarray
    establishment: np.ndarray
    headcount: np.ndarray
    absence_rate: np.ndarray
    effort: np.ndarray
    effective_hours: np.ndarray
    lag_grievance: np.ndarray
    lag_informal_share: np.ndarray
    lag_queue_search_share: np.ndarray
    spec_sha256: str
    rules_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != SIDECAR_SCHEMA_VERSION:
            raise ConfigError(
                f"labor sidecar schema must be {SIDECAR_SCHEMA_VERSION!r}, "
                f"got {self.schema_version!r}"
            )
        if isinstance(self.completed_ticks, bool) or not isinstance(
            self.completed_ticks, (int, np.integer)
        ):
            raise ConfigError("sidecar.completed_ticks must be an integer")
        if int(self.completed_ticks) < 0:
            raise ConfigError("sidecar.completed_ticks must be non-negative")
        object.__setattr__(self, "completed_ticks", int(self.completed_ticks))
        if self.signal_tick is None and self.completed_ticks > 0:
            raise ConfigError(
                "sidecar.signal_tick must be present once a quarter has completed"
            )
        if self.signal_tick is not None:
            if isinstance(self.signal_tick, bool) or not isinstance(
                self.signal_tick, (int, np.integer)
            ):
                raise ConfigError("sidecar.signal_tick must be an integer or None")
            if int(self.signal_tick) != self.completed_ticks - 1:
                raise ConfigError(
                    "sidecar.signal_tick must equal completed_ticks - 1 "
                    "(no quarter may be skipped)"
                )
            object.__setattr__(self, "signal_tick", int(self.signal_tick))
        object.__setattr__(
            self, "organization_ids", _as_id_array(self.organization_ids, "organization_ids")
        )
        object.__setattr__(self, "region_ids", _as_id_array(self.region_ids, "region_ids"))
        org_count = self.organization_ids.shape[0]
        region_count = self.region_ids.shape[0]
        for name in (
            "establishment",
            "headcount",
            "absence_rate",
            "effort",
            "effective_hours",
        ):
            array = _as_float_array(getattr(self, name), f"sidecar.{name}", 1)
            _shape(array, org_count, f"sidecar.{name}")
            _nonnegative(array, f"sidecar.{name}")
            object.__setattr__(self, name, array)
        for name in ("lag_grievance", "lag_informal_share", "lag_queue_search_share"):
            array = _as_float_array(getattr(self, name), f"sidecar.{name}", 1)
            _shape(array, region_count, f"sidecar.{name}")
            object.__setattr__(self, name, array)
        _unit_interval(self.absence_rate, "sidecar.absence_rate")
        _unit_interval(self.effort, "sidecar.effort")
        _sha(self.spec_sha256, "sidecar.spec_sha256")
        _sha(self.rules_sha256, "sidecar.rules_sha256")
        object.__setattr__(self, "spec_sha256", self.spec_sha256.lower())
        object.__setattr__(self, "rules_sha256", self.rules_sha256.lower())


@dataclass(frozen=True)
class LaborTickPlan:
    recipe: LaborRecipe
    tick: int
    previous: LaborSidecar | None
    organization_ids: np.ndarray
    region_ids: np.ndarray
    capacity_open: np.ndarray
    labor_per_activity: np.ndarray
    working_population: float
    establishment_raw: np.ndarray
    establishment: np.ndarray
    headcount: np.ndarray
    absence_rate: np.ndarray
    absence_adjustment: np.ndarray
    effort: np.ndarray
    effective_hours: np.ndarray
    release: np.ndarray
    hire_raw: np.ndarray
    hire: np.ndarray
    available_workers: float
    hire_scale: float

    def __post_init__(self) -> None:
        if not isinstance(self.recipe, LaborRecipe):
            raise ConfigError("plan.recipe must be a LaborRecipe")
        if isinstance(self.tick, bool) or not isinstance(self.tick, (int, np.integer)):
            raise ConfigError("plan.tick must be an integer")
        if int(self.tick) < 0:
            raise ConfigError("plan.tick must be non-negative")
        object.__setattr__(self, "tick", int(self.tick))
        if self.previous is not None and not isinstance(self.previous, LaborSidecar):
            raise ConfigError("plan.previous must be a LaborSidecar or None")
        object.__setattr__(
            self, "organization_ids", _as_id_array(self.organization_ids, "organization_ids")
        )
        object.__setattr__(self, "region_ids", _as_id_array(self.region_ids, "region_ids"))
        org_count = self.organization_ids.shape[0]
        for name in (
            "capacity_open",
            "labor_per_activity",
            "establishment_raw",
            "establishment",
            "headcount",
            "absence_rate",
            "absence_adjustment",
            "effort",
            "effective_hours",
            "release",
            "hire_raw",
            "hire",
        ):
            array = _as_float_array(getattr(self, name), f"plan.{name}", 1)
            _shape(array, org_count, f"plan.{name}")
            object.__setattr__(self, name, array)
        for name in ("capacity_open", "labor_per_activity"):
            _nonnegative(getattr(self, name), f"plan.{name}")
        for name in ("establishment_raw", "establishment", "headcount", "effective_hours"):
            _nonnegative(getattr(self, name), f"plan.{name}")
        for name in ("release", "hire_raw", "hire"):
            _nonnegative(getattr(self, name), f"plan.{name}")
        _unit_interval(self.absence_rate, "plan.absence_rate")
        _unit_interval(self.effort, "plan.effort")
        object.__setattr__(
            self,
            "working_population",
            _finite_scalar(self.working_population, "plan.working_population"),
        )
        object.__setattr__(
            self,
            "available_workers",
            _finite_scalar(self.available_workers, "plan.available_workers"),
        )
        object.__setattr__(
            self, "hire_scale", _finite_scalar(self.hire_scale, "plan.hire_scale")
        )
        if self.working_population < 0.0 or self.available_workers < 0.0:
            raise ConfigError("plan supply quantities must be non-negative")
        if self.hire_scale < 0.0 or self.hire_scale > 1.0:
            raise ConfigError("plan.hire_scale must lie in [0, 1]")


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LaborDiagnostics:
    tick: int
    quarter: str
    signal_tick: int | None
    n_working: float
    n_working_weighted: float
    weight_gap_persons: float
    hours_used: float
    hours_supplied_establishment: float
    hours_supplied_effective: float
    establishment_unused_share: float | None
    underutilization_share: float | None
    activity_per_effective_hour: np.ndarray
    organization_hours_used: np.ndarray
    organization_realized: np.ndarray
    organization_labor_per_activity: np.ndarray
    u_labor: float
    g_labor: float
    n_gap: float
    distribution_uncovered_we: float
    productive_nominal_effective_gap_we: float
    no_working_adults_regions: tuple[int, ...] = field(default=())
    no_household_support_regions: tuple[int, ...] = field(default=())
    labor_mode: str = "ENABLED"
    core_chain: str | None = None
    labor_chain: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "n_working",
            "n_working_weighted",
            "weight_gap_persons",
            "hours_used",
            "hours_supplied_establishment",
            "hours_supplied_effective",
            "u_labor",
            "g_labor",
            "n_gap",
            "distribution_uncovered_we",
            "productive_nominal_effective_gap_we",
        ):
            object.__setattr__(
                self, name, _finite_scalar(getattr(self, name), f"diagnostics.{name}")
            )
        for name in (
            "activity_per_effective_hour",
            "organization_hours_used",
            "organization_realized",
            "organization_labor_per_activity",
        ):
            array = np.asarray(getattr(self, name), dtype=np.float64)
            if array.ndim != 1:
                raise ConfigError(f"diagnostics.{name} must be one-dimensional")
            object.__setattr__(self, name, _readonly(array, np.float64))
        object.__setattr__(self, "tick", int(self.tick))
        object.__setattr__(self, "quarter", str(self.quarter))
        object.__setattr__(self, "labor_mode", str(self.labor_mode))


# ---------------------------------------------------------------------------
# canonical payloads
# ---------------------------------------------------------------------------


def _array_payload(array: np.ndarray) -> list[float] | list[int]:
    return [float(value) for value in np.asarray(array).tolist()]


def sidecar_payload(sidecar: LaborSidecar) -> dict[str, Any]:
    return {
        "schema_version": sidecar.schema_version,
        "completed_ticks": sidecar.completed_ticks,
        "signal_tick": sidecar.signal_tick,
        "organization_ids": [int(v) for v in sidecar.organization_ids.tolist()],
        "region_ids": [int(v) for v in sidecar.region_ids.tolist()],
        "establishment": _array_payload(sidecar.establishment),
        "headcount": _array_payload(sidecar.headcount),
        "absence_rate": _array_payload(sidecar.absence_rate),
        "effort": _array_payload(sidecar.effort),
        "effective_hours": _array_payload(sidecar.effective_hours),
        "lag_grievance": _array_payload(sidecar.lag_grievance),
        "lag_informal_share": _array_payload(sidecar.lag_informal_share),
        "lag_queue_search_share": _array_payload(sidecar.lag_queue_search_share),
        "spec_sha256": sidecar.spec_sha256,
        "rules_sha256": sidecar.rules_sha256,
    }


def sidecar_from_payload(payload: Mapping[str, Any]) -> LaborSidecar:
    expected = {
        "schema_version",
        "completed_ticks",
        "signal_tick",
        "organization_ids",
        "region_ids",
        "establishment",
        "headcount",
        "absence_rate",
        "effort",
        "effective_hours",
        "lag_grievance",
        "lag_informal_share",
        "lag_queue_search_share",
        "spec_sha256",
        "rules_sha256",
    }
    if set(payload) != expected:
        raise ResearchGateError(
            f"labor sidecar field set mismatch: missing {sorted(expected - set(payload))}, "
            f"unexpected {sorted(set(payload) - expected)}"
        )
    return LaborSidecar(**{key: payload[key] for key in expected})


def plan_payload(plan: LaborTickPlan) -> dict[str, Any]:
    return {
        "recipe": plan.recipe.identity(),
        "tick": plan.tick,
        "previous": None if plan.previous is None else sidecar_payload(plan.previous),
        "organization_ids": [int(v) for v in plan.organization_ids.tolist()],
        "region_ids": [int(v) for v in plan.region_ids.tolist()],
        "capacity_open": _array_payload(plan.capacity_open),
        "labor_per_activity": _array_payload(plan.labor_per_activity),
        "working_population": plan.working_population,
        "establishment_raw": _array_payload(plan.establishment_raw),
        "establishment": _array_payload(plan.establishment),
        "headcount": _array_payload(plan.headcount),
        "absence_rate": _array_payload(plan.absence_rate),
        "absence_adjustment": _array_payload(plan.absence_adjustment),
        "effort": _array_payload(plan.effort),
        "effective_hours": _array_payload(plan.effective_hours),
        "release": _array_payload(plan.release),
        "hire_raw": _array_payload(plan.hire_raw),
        "hire": _array_payload(plan.hire),
        "available_workers": plan.available_workers,
        "hire_scale": plan.hire_scale,
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, np.floating):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def diagnostics_payload(diagnostics: LaborDiagnostics) -> dict[str, Any]:
    return {
        "tick": diagnostics.tick,
        "quarter": diagnostics.quarter,
        "signal_tick": diagnostics.signal_tick,
        "labor_mode": diagnostics.labor_mode,
        "n_working": diagnostics.n_working,
        "n_working_weighted": diagnostics.n_working_weighted,
        "weight_gap_persons": diagnostics.weight_gap_persons,
        "hours_used": diagnostics.hours_used,
        "hours_supplied_establishment": diagnostics.hours_supplied_establishment,
        "hours_supplied_effective": diagnostics.hours_supplied_effective,
        "establishment_unused_share": diagnostics.establishment_unused_share,
        "underutilization_share": diagnostics.underutilization_share,
        "activity_per_effective_hour": _json_safe(diagnostics.activity_per_effective_hour),
        "organization_hours_used": _array_payload(diagnostics.organization_hours_used),
        "organization_realized": _array_payload(diagnostics.organization_realized),
        "organization_labor_per_activity": _array_payload(
            diagnostics.organization_labor_per_activity
        ),
        "u_labor": diagnostics.u_labor,
        "g_labor": diagnostics.g_labor,
        "n_gap": diagnostics.n_gap,
        "distribution_uncovered_we": diagnostics.distribution_uncovered_we,
        "productive_nominal_effective_gap_we": (
            diagnostics.productive_nominal_effective_gap_we
        ),
        "no_working_adults_regions": list(diagnostics.no_working_adults_regions),
        "no_household_support_regions": list(diagnostics.no_household_support_regions),
        "core_chain": diagnostics.core_chain,
        "labor_chain": diagnostics.labor_chain,
    }


# ---------------------------------------------------------------------------
# rule functions
# ---------------------------------------------------------------------------


def _validate_state_axes(state: MaterialState) -> tuple[np.ndarray, np.ndarray]:
    organization_ids = np.asarray(state.organization_id, dtype=np.int64)
    region_count = int(np.asarray(state.dwelling_stock).shape[0])
    region_ids = np.arange(region_count, dtype=np.int64)
    organization_region = np.asarray(state.organization_region, dtype=np.int64)
    if organization_region.shape != organization_ids.shape:
        raise ConfigError("state.organization_region must match the organization axis")
    if organization_region.size and (
        int(organization_region.min()) < 0 or int(organization_region.max()) >= region_count
    ):
        raise ConfigError("state.organization_region lies outside the region axis")
    return organization_ids, region_ids


def transition_headcount(
    previous_establishment: np.ndarray,
    previous_headcount: np.ndarray,
    establishment: np.ndarray,
    working_population: float,
    *,
    hire_capacity_share: float,
    max_release_fraction: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    """Release, then one order-free hire allocation from the shared pool."""
    e_prev = _as_float_array(previous_establishment, "previous_establishment", 1)
    h_prev = _as_float_array(previous_headcount, "previous_headcount", 1)
    e_cur = _as_float_array(establishment, "establishment", 1)
    n_working = _finite_scalar(working_population, "working_population")
    if e_prev.shape != h_prev.shape or e_prev.shape != e_cur.shape:
        raise ConfigError("headcount transition arrays must share one shape")
    _nonnegative(e_prev, "previous_establishment")
    _nonnegative(h_prev, "previous_headcount")
    _nonnegative(e_cur, "establishment")
    if n_working < 0.0:
        raise ConfigError("working_population must be non-negative")
    _field = _fraction(hire_capacity_share, "hire_capacity_share")
    _release_cap = _fraction(max_release_fraction, "max_release_fraction")

    release = np.clip(h_prev - e_cur, 0.0, _release_cap * h_prev)
    retained = h_prev - release
    if float(retained.sum()) > n_working + float(tolerance_for(float(retained.sum()), n_working)):
        raise ConfigError(
            "previous headcount exceeds the working population even after the "
            "capped release; refusing the quarter instead of scaling existing headcount"
        )
    hire_capacity = _field * e_prev
    hire_raw = np.clip(e_cur - retained, 0.0, hire_capacity)
    available = max(0.0, n_working - float(retained.sum()))
    raw_total = float(hire_raw.sum())
    if raw_total > available:
        scale = available / raw_total if raw_total > 0.0 else 1.0
    else:
        scale = 1.0
    hire = hire_raw * scale
    headcount = retained + hire
    if float(headcount.sum()) > n_working + float(
        tolerance_for(float(headcount.sum()), n_working)
    ):
        raise ConfigError("headcount transition violates the working-population ceiling")
    return (
        _readonly(headcount, np.float64),
        _readonly(release, np.float64),
        _readonly(hire_raw, np.float64),
        _readonly(hire, np.float64),
        float(scale),
    )


def _establishment(
    capacity: np.ndarray,
    labor_per_activity: np.ndarray,
    target_utilization: float,
    working_population: float,
) -> tuple[np.ndarray, np.ndarray]:
    productive = capacity > 0.0
    if bool(np.any(labor_per_activity[productive] <= 0.0)):
        raise ConfigError("productive organizations require a positive labor_per_activity")
    raw = np.zeros(capacity.shape[0], dtype=np.float64)
    raw[productive] = (
        capacity[productive] * labor_per_activity[productive] * float(target_utilization)
    )
    total = float(raw.sum())
    if total > 0.0:
        scale = min(1.0, float(working_population) / total)
    else:
        scale = 1.0
    establishment = raw * scale
    return _readonly(raw, np.float64), _readonly(establishment, np.float64)


def prepare_labor_tick(
    state: MaterialState,
    recipe: LaborRecipe,
    previous: LaborSidecar | None,
    *,
    initial_headcount: np.ndarray | None = None,
    absence_adjustment: np.ndarray | None = None,
) -> LaborTickPlan:
    """Build the quarter's labour plan from the live opening state."""
    organization_ids, region_ids = _validate_state_axes(state)
    org_count = int(organization_ids.shape[0])
    capacity = _as_float_array(state.organization_capacity, "state.organization_capacity", 1)
    labor_per_activity = _as_float_array(
        state.organization_labor_per_activity, "state.organization_labor_per_activity", 1
    )
    _shape(capacity, org_count, "state.organization_capacity")
    _shape(labor_per_activity, org_count, "state.organization_labor_per_activity")
    _nonnegative(capacity, "state.organization_capacity")
    _nonnegative(labor_per_activity, "state.organization_labor_per_activity")
    working_adults = _as_float_array(
        state.household_working_adults, "state.household_working_adults", 1
    )
    _nonnegative(working_adults, "state.household_working_adults")
    working_population = float(working_adults.sum())
    if working_population < 0.0:
        raise ConfigError("working population must be non-negative")
    tick = int(state.completed_ticks)

    if absence_adjustment is None:
        adjustment = np.zeros(org_count, dtype=np.float64)
    else:
        adjustment = _as_float_array(absence_adjustment, "absence_adjustment", 1)
        _shape(adjustment, org_count, "absence_adjustment")

    establishment_raw, establishment = _establishment(
        capacity,
        labor_per_activity,
        recipe.target_utilization,
        working_population,
    )
    if float(establishment.sum()) > working_population + float(
        tolerance_for(float(establishment.sum()), working_population)
    ):
        raise ConfigError("establishment exceeds the working population")

    if previous is None:
        if tick != 0:
            raise ConfigError(
                "a labor plan without a previous sidecar is only valid at tick 0; "
                "an enabled continuation requires the persisted sidecar"
            )
        if initial_headcount is None:
            headcount = np.array(establishment, dtype=np.float64, copy=True)
        else:
            headcount = _as_float_array(initial_headcount, "initial_headcount", 1)
            _shape(headcount, org_count, "initial_headcount")
            _nonnegative(headcount, "initial_headcount")
            if float(headcount.sum()) > working_population + float(
                tolerance_for(float(headcount.sum()), working_population)
            ):
                raise ConfigError("initial headcount exceeds the working population")
        release = np.zeros(org_count, dtype=np.float64)
        hire_raw = np.zeros(org_count, dtype=np.float64)
        hire = np.zeros(org_count, dtype=np.float64)
        hire_scale = 1.0
        available_workers = working_population - float(headcount.sum())
        absence_prev = np.full(org_count, float(recipe.absence_default), dtype=np.float64)
        grievance_lag = np.zeros(int(region_ids.shape[0]), dtype=np.float64)
        informal_lag = np.zeros(int(region_ids.shape[0]), dtype=np.float64)
        queue_lag = np.zeros(int(region_ids.shape[0]), dtype=np.float64)
    else:
        if previous.spec_sha256 != recipe.spec_sha256:
            raise ConfigError("sidecar spec hash does not match the active recipe")
        if previous.rules_sha256 != recipe.rules_sha256:
            raise ConfigError("sidecar rules hash does not match the active recipe")
        if previous.completed_ticks != tick:
            raise ConfigError(
                f"sidecar completed_ticks {previous.completed_ticks} does not match "
                f"the opening tick {tick}"
            )
        if previous.signal_tick != tick - 1:
            raise ConfigError("sidecar signal_tick is not the previous quarter")
        if not np.array_equal(previous.organization_ids, organization_ids):
            raise ConfigError("sidecar organization axis drifted")
        if not np.array_equal(previous.region_ids, region_ids):
            raise ConfigError("sidecar region axis drifted")
        prev_headcount = np.asarray(previous.headcount, dtype=np.float64)
        if float(prev_headcount.sum()) > working_population + float(
            tolerance_for(float(prev_headcount.sum()), working_population)
        ):
            raise ConfigError(
                "previous headcount already exceeds the working population; "
                "refusing the quarter instead of force-releasing workers"
            )
        headcount, release, hire_raw, hire, hire_scale = transition_headcount(
            previous.establishment,
            prev_headcount,
            establishment,
            working_population,
            hire_capacity_share=recipe.hire_capacity_share,
            max_release_fraction=recipe.max_release_fraction,
        )
        available_workers = working_population - float(
            (prev_headcount - release).sum()
        )
        absence_prev = np.asarray(previous.absence_rate, dtype=np.float64)
        grievance_lag = np.asarray(previous.lag_grievance, dtype=np.float64)
        informal_lag = np.asarray(previous.lag_informal_share, dtype=np.float64)
        queue_lag = np.asarray(previous.lag_queue_search_share, dtype=np.float64)
        expected_effective = (
            prev_headcount
            * recipe.hours_per_we
            * (1.0 - absence_prev)
            * np.asarray(previous.effort, dtype=np.float64)
        )
        if not np.allclose(
            np.asarray(previous.effective_hours, dtype=np.float64),
            expected_effective,
            rtol=1e-12,
            atol=1e-12,
        ):
            raise ConfigError("sidecar effective hours violate identity I2")

    absence_rate = np.clip(
        absence_prev + adjustment, 0.0, recipe.absence_upper_bound
    )
    effort = np.clip(
        1.0
        - recipe.effort_grievance_weight * grievance_lag
        - recipe.effort_informal_hours_weight * informal_lag
        - recipe.effort_queue_search_weight * queue_lag,
        recipe.effort_floor,
        1.0,
    )
    # Effort is a regional quantity; expand it to the organization axis.
    org_region = np.asarray(state.organization_region, dtype=np.int64)
    org_effort = effort[org_region]
    effective_hours = headcount * recipe.hours_per_we * (1.0 - absence_rate) * org_effort
    _nonnegative(effective_hours, "effective_hours")

    return LaborTickPlan(
        recipe=recipe,
        tick=tick,
        previous=previous,
        organization_ids=organization_ids,
        region_ids=region_ids,
        capacity_open=capacity,
        labor_per_activity=labor_per_activity,
        working_population=working_population,
        establishment_raw=establishment_raw,
        establishment=establishment,
        headcount=headcount,
        absence_rate=absence_rate,
        absence_adjustment=adjustment,
        effort=org_effort,
        effective_hours=effective_hours,
        release=release,
        hire_raw=hire_raw,
        hire=hire,
        available_workers=available_workers,
        hire_scale=hire_scale,
    )


def validate_labor_plan(state: MaterialState, plan: LaborTickPlan) -> None:
    """Pre-mutation plan gate used by the kernel before any state write."""
    if not isinstance(plan, LaborTickPlan):
        raise ConfigError("labor_plan must be a LaborTickPlan or None")
    if int(plan.tick) != int(state.completed_ticks):
        raise ConfigError(
            f"labor plan tick {plan.tick} does not match the opening tick "
            f"{state.completed_ticks}"
        )
    organization_ids, region_ids = _validate_state_axes(state)
    if not np.array_equal(plan.organization_ids, organization_ids):
        raise ConfigError("labor plan organization axis does not match the state")
    if not np.array_equal(plan.region_ids, region_ids):
        raise ConfigError("labor plan region axis does not match the state")
    if not np.array_equal(
        np.asarray(plan.capacity_open, dtype=np.float64),
        np.asarray(state.organization_capacity, dtype=np.float64),
    ):
        raise ConfigError("labor plan opening capacity does not match the live state")
    if not np.array_equal(
        np.asarray(plan.labor_per_activity, dtype=np.float64),
        np.asarray(state.organization_labor_per_activity, dtype=np.float64),
    ):
        raise ConfigError("labor plan labor_per_activity does not match the live state")

    recipe = plan.recipe
    org_count = int(organization_ids.shape[0])
    working = np.asarray(state.household_working_adults, dtype=np.float64)
    n_working = float(working.sum())
    if abs(float(plan.working_population) - n_working) > float(
        tolerance_for(n_working, plan.working_population)
    ):
        raise ConfigError("labor plan working population does not match the state")
    capacity = np.asarray(plan.capacity_open, dtype=np.float64)
    lpa = np.asarray(plan.labor_per_activity, dtype=np.float64)
    productive = capacity > 0.0
    if bool(np.any(lpa[productive] <= 0.0)):
        raise ConfigError("productive organizations require a positive labor_per_activity")

    establishment_raw = np.zeros(org_count, dtype=np.float64)
    establishment_raw[productive] = (
        capacity[productive] * lpa[productive] * float(recipe.target_utilization)
    )
    raw_total = float(establishment_raw.sum())
    scale = min(1.0, n_working / raw_total) if raw_total > 0.0 else 1.0
    _require_close(plan.establishment_raw, establishment_raw, "establishment_raw")
    _require_close(plan.establishment, establishment_raw * scale, "establishment")
    if float(np.asarray(plan.establishment).sum()) > n_working + float(
        tolerance_for(float(np.asarray(plan.establishment).sum()), n_working)
    ):
        raise ConfigError("labor plan establishment exceeds the working population")
    headcount = np.asarray(plan.headcount, dtype=np.float64)
    if float(headcount.sum()) > n_working + float(
        tolerance_for(float(headcount.sum()), n_working)
    ):
        raise ConfigError("labor plan headcount exceeds the working population")
    _unit_interval(np.asarray(plan.absence_rate), "plan.absence_rate")
    if bool(np.any(np.asarray(plan.absence_rate) > recipe.absence_upper_bound + 1e-12)):
        raise ConfigError("labor plan absence exceeds the recipe upper bound")
    effort = np.asarray(plan.effort, dtype=np.float64)
    if bool(np.any(effort < recipe.effort_floor - 1e-12)) or bool(np.any(effort > 1.0)):
        raise ConfigError("labor plan effort lies outside the recipe bounds")
    _require_close(
        plan.effective_hours,
        headcount
        * float(recipe.hours_per_we)
        * (1.0 - np.asarray(plan.absence_rate))
        * effort,
        "effective_hours",
    )

    if plan.previous is None:
        zeros = np.zeros(org_count, dtype=np.float64)
        _require_close(plan.release, zeros, "initial release")
        _require_close(plan.hire_raw, zeros, "initial hire_raw")
        _require_close(plan.hire, zeros, "initial hire")
        _require_close(
            np.asarray([plan.hire_scale]), np.asarray([1.0]), "initial hire_scale"
        )
        expected_absence = np.clip(
            float(recipe.absence_default) + np.asarray(plan.absence_adjustment),
            0.0,
            recipe.absence_upper_bound,
        )
        _require_close(plan.absence_rate, expected_absence, "initial absence")
        _require_close(effort, np.ones(org_count), "initial effort")
    else:
        previous = plan.previous
        if previous.spec_sha256 != recipe.spec_sha256:
            raise ConfigError("labor plan previous spec hash does not match the recipe")
        if previous.rules_sha256 != recipe.rules_sha256:
            raise ConfigError("labor plan previous rules hash does not match the recipe")
        if previous.completed_ticks != plan.tick or previous.signal_tick != plan.tick - 1:
            raise ConfigError("labor plan previous sidecar stamps do not match the tick")
        if not np.array_equal(previous.organization_ids, organization_ids) or not (
            np.array_equal(previous.region_ids, region_ids)
        ):
            raise ConfigError("labor plan previous sidecar axis does not match the state")
        previous_headcount = np.asarray(previous.headcount, dtype=np.float64)
        previous_establishment = np.asarray(previous.establishment, dtype=np.float64)
        if float(previous_headcount.sum()) > n_working + float(
            tolerance_for(float(previous_headcount.sum()), n_working)
        ):
            raise ConfigError("labor plan previous headcount exceeds the supply")
        _require_close(
            previous.effective_hours,
            previous_headcount
            * float(recipe.hours_per_we)
            * (1.0 - np.asarray(previous.absence_rate))
            * np.asarray(previous.effort),
            "previous effective_hours",
        )
        release = np.clip(
            previous_headcount - np.asarray(plan.establishment),
            0.0,
            float(recipe.max_release_fraction) * previous_headcount,
        )
        _require_close(plan.release, release, "release")
        retained = previous_headcount - release
        hire_raw = np.clip(
            np.asarray(plan.establishment) - retained,
            0.0,
            float(recipe.hire_capacity_share) * previous_establishment,
        )
        _require_close(plan.hire_raw, hire_raw, "hire_raw")
        available = n_working - float(retained.sum())
        _require_close(
            np.asarray([plan.available_workers]),
            np.asarray([available]),
            "available_workers",
        )
        raw_sum = float(hire_raw.sum())
        expected_scale = available / raw_sum if raw_sum > available else 1.0
        _require_close(
            np.asarray([plan.hire_scale]), np.asarray([expected_scale]), "hire_scale"
        )
        _require_close(plan.hire, expected_scale * hire_raw, "hire")
        _require_close(
            headcount, retained + expected_scale * hire_raw, "headcount evolution"
        )
        absent_prev = np.asarray(previous.absence_rate, dtype=np.float64)
        _require_close(
            plan.absence_rate,
            np.clip(
                absent_prev + np.asarray(plan.absence_adjustment),
                0.0,
                recipe.absence_upper_bound,
            ),
            "absence path",
        )
        expected_effort = np.clip(
            1.0
            - float(recipe.effort_grievance_weight)
            * np.asarray(previous.lag_grievance, dtype=np.float64)
            - float(recipe.effort_informal_hours_weight)
            * np.asarray(previous.lag_informal_share, dtype=np.float64)
            - float(recipe.effort_queue_search_weight)
            * np.asarray(previous.lag_queue_search_share, dtype=np.float64),
            float(recipe.effort_floor),
            1.0,
        )[np.asarray(state.organization_region, dtype=np.int64)]
        _require_close(effort, expected_effort, "effort rule")


def _require_close(lhs: Any, rhs: Any, label: str) -> None:
    left = np.asarray(lhs, dtype=np.float64)
    right = np.asarray(rhs, dtype=np.float64)
    if left.shape != right.shape:
        raise ConfigError(f"labor plan {label} shape mismatch {left.shape} vs {right.shape}")
    if not np.allclose(left, right, rtol=1e-12, atol=1e-12):
        raise ConfigError(f"labor plan {label} does not satisfy its declared identity")


def apply_labor_plan(state: MaterialState, plan: LaborTickPlan) -> None:
    """Write the plan's effort into the existing carrier; never advance H."""
    validate_labor_plan(state, plan)
    state.organization_effort_factor = np.array(plan.effort, dtype=np.float64, copy=True)


def _region_grievance(
    region: np.ndarray,
    weight: np.ndarray,
    grievance: np.ndarray,
    region_count: int,
) -> tuple[np.ndarray, tuple[int, ...]]:
    weighted = np.bincount(region, weights=weight * grievance, minlength=region_count)
    support = np.bincount(region, weights=weight, minlength=region_count)
    mean = np.zeros(region_count, dtype=np.float64)
    missing = np.flatnonzero(support <= 0.0)
    valid = support > 0.0
    mean[valid] = weighted[valid] / support[valid]
    return mean, tuple(int(index) for index in missing)


def _region_hours_share(
    region: np.ndarray,
    hours: np.ndarray,
    working: np.ndarray,
    endowment_hours: float,
    region_count: int,
) -> tuple[np.ndarray, tuple[int, ...]]:
    numerator = np.bincount(region, weights=hours, minlength=region_count)
    working_region = np.bincount(region, weights=working, minlength=region_count)
    denominator = endowment_hours * working_region
    share = np.zeros(region_count, dtype=np.float64)
    missing = np.flatnonzero(denominator <= 0.0)
    valid = denominator > 0.0
    share[valid] = numerator[valid] / denominator[valid]
    return share, tuple(int(index) for index in missing)


def close_labor_tick(
    state: MaterialState,
    flows: MaterialTickFlows,
    plan: LaborTickPlan,
) -> tuple[LaborSidecar, LaborDiagnostics]:
    """Verify the labour ledger and publish next quarter's sidecar."""
    if not isinstance(plan, LaborTickPlan):
        raise ConfigError("labor_plan must be a LaborTickPlan")
    organization_ids, region_ids = _validate_state_axes(state)
    org_count = int(organization_ids.shape[0])
    region_count = int(region_ids.shape[0])
    # Closing capacity may have grown when investment completed inside the
    # tick, so only the identity axes and the plan's own tick are re-checked
    # here; the opening-quote check happened in ``apply_labor_plan``.
    if int(plan.tick) != int(state.completed_ticks):
        raise ConfigError(
            f"labor plan tick {plan.tick} does not match the closing tick "
            f"{state.completed_ticks}"
        )
    if not np.array_equal(plan.organization_ids, organization_ids):
        raise ConfigError("labor plan organization axis does not match the state")
    if not np.array_equal(plan.region_ids, region_ids):
        raise ConfigError("labor plan region axis does not match the state")
    if int(flows.tick) != plan.tick:
        raise AccountingError(
            f"flows tick {flows.tick} does not match the labor plan tick {plan.tick}"
        )
    realized = np.asarray(flows.organization_realized, dtype=np.float64)
    _shape(realized, org_count, "flows.organization_realized")
    if not bool(np.all(np.isfinite(realized))) or bool(np.any(realized < 0.0)):
        raise AccountingError("organization_realized must be finite and non-negative")

    hours_used_i = plan.recipe.hours_per_we * plan.labor_per_activity * realized
    tolerance = np.asarray(tolerance_for(hours_used_i, plan.effective_hours), dtype=np.float64)
    over = hours_used_i - plan.effective_hours
    if bool(np.any(over > tolerance)):
        index = int(np.argmax(over - tolerance))
        raise AccountingError(
            "accounting violation in "
            f"{flows.quarter} ledger=labor_effective_hours_used "
            f"key=organization[{int(organization_ids[index])}] "
            f"lhs={float(hours_used_i[index])!r} rhs={float(plan.effective_hours[index])!r}"
        )

    hours_used = float(hours_used_i.sum())
    hours_establishment = float(plan.recipe.hours_per_we * plan.establishment.sum())
    hours_effective = float(plan.effective_hours.sum())
    establishment_share = (
        1.0 - hours_used / hours_establishment if hours_establishment > 0.0 else None
    )
    effective_share = 1.0 - hours_used / hours_effective if hours_effective > 0.0 else None
    if effective_share is not None and (
        effective_share < -float(tolerance_for(1.0, 1.0)) or effective_share > 1.0 + 1e-12
    ):
        raise AccountingError(
            f"effective-hour share {effective_share!r} lies outside [0, 1] after I4"
        )
    activity_per_hour = np.full(org_count, np.nan, dtype=np.float64)
    positive = plan.effective_hours > 0.0
    activity_per_hour[positive] = realized[positive] / plan.effective_hours[positive]

    working_adults = np.asarray(state.household_working_adults, dtype=np.float64)
    weights = np.asarray(state.household_weight, dtype=np.float64)
    n_working = float(working_adults.sum())
    n_weighted = float((weights * working_adults).sum())
    nominal_all = float(np.asarray(state.organization_labor_available, dtype=np.float64).sum())
    productive = plan.capacity_open > 0.0
    nominal_productive = float(
        np.asarray(state.organization_labor_available, dtype=np.float64)[productive].sum()
    )
    effective_we = hours_effective / plan.recipe.hours_per_we
    g_labor = nominal_all - n_working
    n_gap = nominal_all - effective_we
    distribution_uncovered = nominal_all - nominal_productive
    productive_gap = nominal_productive - effective_we

    household_region = np.asarray(state.household_region, dtype=np.int64)
    remaining = int(household_region.shape[0])
    if remaining:
        if int(household_region.min()) < 0 or int(household_region.max()) >= region_count:
            raise AccountingError("household_region lies outside the region axis")
        grievance_mean, no_support = _region_grievance(
            household_region,
            weights,
            np.asarray(state.household_grievance, dtype=np.float64),
            region_count,
        )
        plot_share, no_plot_workers = _region_hours_share(
            household_region,
            np.asarray(state.household_reserved_plot_hours, dtype=np.float64),
            working_adults,
            plan.recipe.endowment_hours,
            region_count,
        )
        second_share, no_second_workers = _region_hours_share(
            household_region,
            np.asarray(state.household_reserved_second_hours, dtype=np.float64),
            working_adults,
            plan.recipe.endowment_hours,
            region_count,
        )
        queue_share, no_queue_workers = _region_hours_share(
            household_region,
            np.asarray(flows.household_queue_hours, dtype=np.float64),
            working_adults,
            plan.recipe.endowment_hours,
            region_count,
        )
        search_share, no_search_workers = _region_hours_share(
            household_region,
            np.asarray(flows.household_search_hours, dtype=np.float64),
            working_adults,
            plan.recipe.endowment_hours,
            region_count,
        )
        no_working = tuple(
            sorted(set(no_plot_workers) | set(no_second_workers) | set(no_queue_workers)
                   | set(no_search_workers))
        )
    else:
        grievance_mean = np.zeros(region_count, dtype=np.float64)
        plot_share = np.zeros(region_count, dtype=np.float64)
        second_share = np.zeros(region_count, dtype=np.float64)
        queue_share = np.zeros(region_count, dtype=np.float64)
        search_share = np.zeros(region_count, dtype=np.float64)
        no_support = tuple()
        no_working = tuple()
    informal_share = plot_share + second_share
    queue_search_share = queue_share + search_share
    if not (
        np.all(np.isfinite(informal_share))
        and np.all(np.isfinite(queue_search_share))
        and np.all(np.isfinite(grievance_mean))
    ):
        raise AccountingError("next-quarter labour signals must be finite")

    sidecar = LaborSidecar(
        schema_version=SIDECAR_SCHEMA_VERSION,
        completed_ticks=plan.tick + 1,
        signal_tick=plan.tick,
        organization_ids=organization_ids,
        region_ids=region_ids,
        establishment=plan.establishment,
        headcount=plan.headcount,
        absence_rate=plan.absence_rate,
        effort=plan.effort,
        effective_hours=plan.effective_hours,
        lag_grievance=grievance_mean,
        lag_informal_share=informal_share,
        lag_queue_search_share=queue_search_share,
        spec_sha256=plan.recipe.spec_sha256,
        rules_sha256=plan.recipe.rules_sha256,
    )
    diagnostics = LaborDiagnostics(
        tick=plan.tick,
        quarter=str(flows.quarter),
        signal_tick=plan.previous.signal_tick if plan.previous is not None else None,
        n_working=n_working,
        n_working_weighted=n_weighted,
        weight_gap_persons=n_weighted - n_working,
        hours_used=hours_used,
        hours_supplied_establishment=hours_establishment,
        hours_supplied_effective=hours_effective,
        establishment_unused_share=establishment_share,
        underutilization_share=effective_share,
        activity_per_effective_hour=activity_per_hour,
        organization_hours_used=hours_used_i,
        organization_realized=realized,
        organization_labor_per_activity=plan.labor_per_activity,
        u_labor=n_working - float(plan.headcount.sum()),
        g_labor=g_labor,
        n_gap=n_gap,
        distribution_uncovered_we=distribution_uncovered,
        productive_nominal_effective_gap_we=productive_gap,
        no_working_adults_regions=no_working,
        no_household_support_regions=no_support,
    )
    return sidecar, diagnostics


# ---------------------------------------------------------------------------
# digest chain (external; never the legacy core chain)
# ---------------------------------------------------------------------------


def labor_chain_start(
    recipe: LaborRecipe,
    *,
    implementation_spec_sha256: str,
    scenario_hash: str,
    core_chain: str,
    initial_sidecar: LaborSidecar | None,
    initial_headcount: np.ndarray | None,
) -> str:
    return canonical_digest(
        {
            "schema": "hist_vnext_h5d_labor_chain_v1",
            "adapter": ADAPTER_SCHEMA_VERSION,
            "spec_sha256": recipe.spec_sha256,
            "rules_sha256": recipe.rules_sha256,
            "implementation_spec_sha256": _sha(
                implementation_spec_sha256, "implementation_spec_sha256"
            ),
            "scenario_hash": _sha(scenario_hash, "scenario_hash"),
            "core_chain": _sha(core_chain, "core_chain"),
            "initial_sidecar": None if initial_sidecar is None
            else sidecar_payload(initial_sidecar),
            "initial_headcount": None
            if initial_headcount is None
            else _array_payload(np.asarray(initial_headcount, dtype=np.float64)),
        }
    )


def _diagnostics_chain_payload(diagnostics: LaborDiagnostics) -> dict[str, Any]:
    payload = diagnostics_payload(diagnostics)
    payload.pop("core_chain", None)
    payload.pop("labor_chain", None)
    return payload


def labor_chain_advance_digest(
    previous: str,
    *,
    core_chain: str,
    plan_sha256: str,
    sidecar: dict[str, Any],
    diagnostics_data: dict[str, Any],
) -> str:
    """Recompute the external chain from canonical digests (verify path)."""
    digest = hashlib.sha256()
    digest.update(bytes.fromhex(_sha(previous, "previous labor chain")))
    clean = {
        key: value
        for key, value in diagnostics_data.items()
        if key not in ("core_chain", "labor_chain")
    }
    digest.update(
        canonical_digest(
            {
                "core_chain": _sha(core_chain, "core_chain"),
                "plan_sha256": _sha(plan_sha256, "plan_sha256"),
                "sidecar": sidecar,
                "diagnostics": clean,
            }
        ).encode("ascii")
    )
    return digest.hexdigest()


def labor_chain_advance(
    previous: str,
    *,
    core_chain: str,
    plan: LaborTickPlan,
    sidecar: LaborSidecar,
    diagnostics: LaborDiagnostics,
) -> str:
    return labor_chain_advance_digest(
        previous,
        core_chain=core_chain,
        plan_sha256=canonical_digest(plan_payload(plan)),
        sidecar=sidecar_payload(sidecar),
        diagnostics_data=_diagnostics_chain_payload(diagnostics),
    )


# ---------------------------------------------------------------------------
# snapshot helpers used by the runner / tests
# ---------------------------------------------------------------------------


def effective_hours_of(recipe: LaborRecipe, sidecar: LaborSidecar) -> np.ndarray:
    """Recompute I2 from the sidecar's own carriers (recovery gate)."""
    return (
        np.asarray(sidecar.headcount)
        * recipe.hours_per_we
        * (1.0 - np.asarray(sidecar.absence_rate))
        * np.asarray(sidecar.effort)
    )


__all__ = [
    "ADAPTER_SCHEMA_VERSION",
    "BUNDLE_SCHEMA_VERSION",
    "SIDECAR_SCHEMA_VERSION",
    "LaborDiagnostics",
    "LaborRecipe",
    "LaborSidecar",
    "LaborTickPlan",
    "apply_labor_plan",
    "close_labor_tick",
    "diagnostics_payload",
    "effective_hours_of",
    "labor_chain_advance",
    "labor_chain_advance_digest",
    "labor_chain_start",
    "plan_payload",
    "prepare_labor_tick",
    "sidecar_from_payload",
    "sidecar_payload",
    "transition_headcount",
    "validate_labor_plan",
]
