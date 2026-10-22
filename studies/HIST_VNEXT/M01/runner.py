"""H5C M01 matched-reference-history ratchet experiment.

The experiment holds one synthetic F1/Intermediate-8 economic state fixed at a
single treatment quarter (1958Q1) and asks whether a *carried reference
history* changes the response to an identical one-quarter cut.  The only
mechanism under study is the existing
``engine.household_welfare.update_household_expectations`` ratchet; the runner
does not implement a parallel expectation system.

Modes:

* ``reproduce`` — record the counterexamples (legacy card quarters, empty C0
  political tables, forced-saving-only input) and the donor first stage.
* ``profile`` — seed 1729, the complete 26-arm matrix.
* ``study`` — all three declared seeds, 78 arms.
* ``verify`` — recompute file hashes, arm identities, tables and matching
  evidence read-only.

All generated evidence is synthetic/structural.  The historical status is
UNIDENTIFIED: no admitted D14 source identifies the empirical ratchet.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections.abc import Sequence
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

# Running this file directly puts ``studies/HIST_VNEXT/M01`` first on
# ``sys.path``.  Bind the repository root explicitly so the namespace package
# and ``hsm_lab`` both resolve.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from hsm_lab.contract.base import ConfigError  # noqa: E402
from hsm_lab.contract.guards import load_research_contract, load_scenario  # noqa: E402
from hsm_lab.contract.households import (  # noqa: E402
    ENTITLEMENT_IDS,
    INTERMEDIATE8_AXIS,
    HouseholdParameters,
)
from hsm_lab.contract.politics import (  # noqa: E402
    POLICY_COORDINATES,
    POLITICAL_FEATURE_IDS,
    InterventionSpec,
)
from hsm_lab.contract.schemas import ScenarioSpec  # noqa: E402
from hsm_lab.data.registry import DataRegistry  # noqa: E402
from hsm_lab.engine.household_welfare import update_household_expectations  # noqa: E402
from hsm_lab.engine.initial import build_material_initial_conditions  # noqa: E402
from hsm_lab.engine.network import build_material_network  # noqa: E402
from hsm_lab.engine.policy import default_initial_policy  # noqa: E402
from hsm_lab.engine.political_run import open_political_session  # noqa: E402
from hsm_lab.engine.rng import RngRegistry  # noqa: E402
from hsm_lab.engine.state import (  # noqa: E402
    capture_material_stocks,
    initialize_material,
)
from hsm_lab.provenance.manifest import (  # noqa: E402
    canonical_digest,
    compute_scenario_hash,
)

SCHEMA_VERSION = "hist_vnext_h5c_m01_v1"
PHASE_ID = "H5C"
MECHANISM_ID = "M1"
STUDY_ID = "M01"
SPEC_PATH = _HERE / "spec.json"

BASE_SCENARIO_ID = "p04_replay"
SYNTHETIC_SCENARIO_ID = "hist_vnext_h5c_m01_synthetic"
TICKS = 8
WARMUP_TICKS = 4
TREATMENT_TICK = 4
TREATMENT_QUARTER = "1958Q1"
HISTORIES = ("one_jump", "two_steps", "four_steps")
STRENGTHS = (0.1, 0.0)
CUTS = ("no_cut", "income_cut", "welfare_cut", "import_cut")
NATIVE_CUTS = ("no_cut", "income_cut")
SEEDS = (1729, 1730, 1731)
SEQUENCES = {
    "one_jump": (0.5, 0.5, 0.5, 0.9),
    "two_steps": (0.5, 0.5, 0.7, 0.9),
    "four_steps": (0.6, 0.7, 0.8, 0.9),
}
CUT_PATCH = {
    "income_cut": "wage_factor",
    "welfare_cut": "welfare_provision",
    "import_cut": "consumer_import_factor",
}
CUT_VALUE = {
    "income_cut": 0.9,
    "welfare_cut": 0.4,
    "import_cut": 0.8,
}
E_REAL_CONSUMPTION = INTERMEDIATE8_AXIS.good_ids.index("basic_food")
ENTITLEMENT_REAL_CONSUMPTION = ENTITLEMENT_IDS.index("real_consumption")
ENTITLEMENT_WELFARE = ENTITLEMENT_IDS.index("welfare")
DOMESTIC_CURRENCY = "p02_domestic_currency"
ATOL = 1e-10
RTOL = 1e-8


# ---------------------------------------------------------------------------
# Serialization / hashing helpers
# ---------------------------------------------------------------------------


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, np.ndarray):
        return _clean(value.tolist())
    if isinstance(value, np.generic):
        return _clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_clean(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_memory_payload(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(_clean(payload), separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _array_digest(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(f"{contiguous.dtype.str}|{contiguous.shape}|".encode())
    digest.update(contiguous.tobytes())
    return digest.hexdigest()


def _field_digest(value: Any) -> str:
    if isinstance(value, np.ndarray):
        return _array_digest(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return canonical_digest(value)
    if isinstance(value, tuple):
        return canonical_digest([_field_repr(item) for item in value])
    return canonical_digest(_field_repr(value))


def _field_repr(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "__dataclass_fields__"):
        return {name: _field_repr(getattr(value, name)) for name in value.__dataclass_fields__}
    if isinstance(value, tuple):
        return [_field_repr(item) for item in value]
    return repr(value)


def _state_field_digests(state: Any, *, exclude: frozenset[str] = frozenset()) -> dict[str, str]:
    out: dict[str, str] = {}
    for field in fields(state):
        if field.name in exclude:
            continue
        out[field.name] = _field_digest(getattr(state, field.name))
    return out


def _nonmemory_digest(state: Any) -> str:
    return canonical_digest(
        _state_field_digests(
            state,
            exclude=frozenset(
                {
                    "household_expectation",
                    "household_improvement_streak",
                    "household_consumption_reference",
                }
            ),
        )
    )


def _file_manifest(root: Path) -> list[dict[str, Any]]:
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if str(relative) == "manifest.json":
            continue
        entries.append(
            {
                "path": str(relative),
                "sha256": _sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return entries


# ---------------------------------------------------------------------------
# Scenario and interventions
# ---------------------------------------------------------------------------


def _study_spec(root: Path) -> dict[str, Any]:
    if not SPEC_PATH.is_file():
        raise ConfigError(f"H5C spec not found: {SPEC_PATH}")
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def _scenario_for(root: Path, seed: int, ticks: int, scenario_id: str) -> ScenarioSpec:
    base = load_scenario(root, BASE_SCENARIO_ID)
    payload = base.model_dump(mode="json")
    payload.update(
        {
            "scenario_id": scenario_id,
            "ticks": int(ticks),
            "seed": int(seed),
        }
    )
    spec = ScenarioSpec.model_validate(payload)
    contract = load_research_contract(root)
    spec.validate_for_run(contract)
    if str(spec.start) != "1957Q1":
        raise ConfigError("H5C assumes the frozen core start 1957Q1")
    return spec


def _scenario(root: Path, seed: int) -> ScenarioSpec:
    return _scenario_for(root, seed, TICKS, SYNTHETIC_SCENARIO_ID)


def _policy_interventions(
    spec: ScenarioSpec,
    cut_id: str,
    *,
    ticks: int | None = None,
    treatment_tick: int = TREATMENT_TICK,
) -> list[InterventionSpec]:
    if cut_id not in CUTS:
        raise ConfigError(f"unknown cut {cut_id!r}")
    policy = default_initial_policy(spec)
    start = spec.start
    out: list[InterventionSpec] = []
    for tick in range(int(ticks if ticks is not None else spec.ticks)):
        quarter = str(start.advance(tick))
        for coordinate in POLICY_COORDINATES:
            value = float(getattr(policy, coordinate))
            if tick == treatment_tick and coordinate == CUT_PATCH.get(cut_id, ""):
                value = CUT_VALUE[cut_id]
            out.append(
                InterventionSpec(
                    intervention_id=f"{quarter}-{coordinate}",
                    effective_quarter=quarter,
                    until_quarter=quarter,
                    target=f"policy.{coordinate}",
                    operation="set",
                    value=value,
                    provenance="H5C synthetic controlled experiment",
                )
            )
    return out


def _intervention_payload(
    spec: ScenarioSpec, interventions: Sequence[InterventionSpec]
) -> dict[str, Any]:
    records = []
    for item in interventions:
        record = item.model_dump(mode="json")
        record["effective_quarter"] = str(item.effective_quarter)
        record["until_quarter"] = None if item.until_quarter is None else str(item.until_quarter)
        records.append(record)
    warmup_quarters = {_quarter_key(tick) for tick in range(WARMUP_TICKS)}
    warmup = [item for item in records if item["effective_quarter"] in warmup_quarters]
    treatment = [item for item in records if item["effective_quarter"] == TREATMENT_QUARTER]
    return {
        "count": len(records),
        "sha256": canonical_digest(records),
        "warmup_sha256": canonical_digest(warmup),
        "treatment_sha256": canonical_digest(treatment),
        "records": records,
        "all_coordinates_each_quarter": len(records) == TICKS * len(POLICY_COORDINATES),
    }


_QUARTER_CACHE: dict[int, str] = {}


def _quarter_key(tick: int) -> str:
    if tick not in _QUARTER_CACHE:
        _QUARTER_CACHE[tick] = f"{1957 + tick // 4}Q{tick % 4 + 1}"
    return _QUARTER_CACHE[tick]


# ---------------------------------------------------------------------------
# Donor memory (synthetic controlled-state transplant input)
# ---------------------------------------------------------------------------


def _donor_state(root: Path, spec: ScenarioSpec, contract: Any) -> Any:
    initial = build_material_initial_conditions(spec, RngRegistry(spec.seed))
    network = build_material_network(spec, contract, initial)
    return initialize_material(spec, initial, network)


def donor_memory(
    *,
    root: Path,
    spec: ScenarioSpec,
    contract: Any,
    history_id: str,
    formation_ratchet_strength: float,
) -> dict[str, Any]:
    """Form the carried reference history with the existing updater only."""
    if history_id not in SEQUENCES:
        raise ConfigError(f"unknown history {history_id!r}")
    if not 0.0 <= float(formation_ratchet_strength) <= 0.3:
        raise ConfigError("formation ratchet strength outside [0, 0.3]")
    donor = _donor_state(root, spec, contract)
    reference0 = np.asarray(donor.household_consumption_reference, dtype=np.float64).copy()
    parameters = spec.household_parameters
    assert parameters is not None
    formation_payload = parameters.model_dump(mode="json")
    formation_payload["expectations"]["ratchet_strength"] = float(formation_ratchet_strength)
    formation = HouseholdParameters.model_validate(formation_payload)
    samples = []
    for index, sample in enumerate(SEQUENCES[history_id]):
        opening = capture_material_stocks(donor)
        experienced = (reference0 * (sample / (1.0 - sample))).copy()
        sample_flows = SimpleNamespace(
            household_realized_h=experienced,
            household_availability_unmet_h=np.zeros_like(reference0),
        )
        before_expectation = np.asarray(donor.household_expectation, dtype=np.float64).copy()
        before_streak = np.asarray(donor.household_improvement_streak, dtype=np.int32).copy()
        before_entitlement = np.asarray(donor.household_entitlement, dtype=np.float64).copy()
        donor.household_entitlement[:, ENTITLEMENT_REAL_CONSUMPTION] = float(sample)
        update_household_expectations(donor, sample_flows, formation, opening)
        samples.append(
            {
                "sample_index": index,
                "sample_quarter": _quarter_key(index),
                "sample_entitlement_real_consumption": float(sample),
                "experienced_acquisition_axis": "intermediate8_v1 household channel",
                "experienced_acquisition_units": {
                    channel: f"synthetic_physical_unit:{channel}"
                    for channel in INTERMEDIATE8_AXIS.good_ids
                },
                "experienced_acquisition_mean_by_channel": np.mean(experienced, axis=0).tolist(),
                "experienced_acquisition_sha256": _array_digest(experienced),
                "opening_entitlement_real_consumption": before_entitlement[
                    :, ENTITLEMENT_REAL_CONSUMPTION
                ].tolist(),
                "opening_expectation_real_consumption": before_expectation[
                    :, ENTITLEMENT_REAL_CONSUMPTION
                ].tolist(),
                "closing_expectation_real_consumption": np.asarray(
                    donor.household_expectation[:, ENTITLEMENT_REAL_CONSUMPTION]
                ).tolist(),
                "opening_streak_real_consumption": before_streak[
                    :, ENTITLEMENT_REAL_CONSUMPTION
                ].tolist(),
                "closing_streak_real_consumption": np.asarray(
                    donor.household_improvement_streak[:, ENTITLEMENT_REAL_CONSUMPTION]
                ).tolist(),
                "consumption_reference_mean_by_channel": np.mean(
                    np.asarray(donor.household_consumption_reference, dtype=np.float64), axis=0
                ).tolist(),
                "consumption_reference_sha256": _array_digest(
                    np.asarray(donor.household_consumption_reference, dtype=np.float64)
                ),
            }
        )
    expectation = np.asarray(donor.household_expectation, dtype=np.float64)[
        :, ENTITLEMENT_REAL_CONSUMPTION
    ].copy()
    streak = np.asarray(donor.household_improvement_streak, dtype=np.int32)[
        :, ENTITLEMENT_REAL_CONSUMPTION
    ].copy()
    reference = np.asarray(donor.household_consumption_reference, dtype=np.float64).copy()
    return {
        "schema_version": SCHEMA_VERSION,
        "history_id": history_id,
        "formation_ratchet_strength": float(formation_ratchet_strength),
        "sequence": list(SEQUENCES[history_id]),
        "source": "synthetic controlled-state transplant (do(memory))",
        "evidence_status": "synthetic_experience_input",
        "not_economic_output": True,
        "not_installed_in_forcing_or_actor_observation": True,
        "axis": {
            "entitlement": "real_consumption",
            "channel": list(INTERMEDIATE8_AXIS.good_ids),
        },
        "initial_reference_mean": float(np.mean(reference0)),
        "samples": samples,
        "final": {
            "expectation_real_consumption": expectation.tolist(),
            "streak_real_consumption": [int(value) for value in streak.tolist()],
            "expectation_sha256": _array_digest(expectation),
            "streak_sha256": _array_digest(streak),
            "consumption_reference": reference.tolist(),
            "consumption_reference_sha256": _array_digest(reference),
            "expectation_real_consumption_mean": float(np.mean(expectation)),
            "streak_real_consumption_max": int(np.max(streak)),
            "consumption_reference_total": float(np.sum(reference)),
            "threshold_crossed": bool(np.max(streak) >= parameters.expectations.ratchet_quarters),
        },
    }


# ---------------------------------------------------------------------------
# Matching evidence
# ---------------------------------------------------------------------------


def _matching_snapshot(session: Any, spec: ScenarioSpec) -> dict[str, Any]:
    state = session.state
    political = session.political
    rng = session.rng.snapshot()
    explicit = {
        "quarter": str(spec.start.advance(int(state.completed_ticks))),
        "completed_ticks": int(state.completed_ticks),
        "household_cash_sum": float(np.sum(state.household_cash)),
        "organization_cash_sum": float(np.sum(state.organization_cash)),
        "bank_deposit_liability_sum": float(np.sum(state.bank_deposit_liability)),
        "bank_reserves_sum": float(np.sum(state.bank_reserves)),
        "treasury_deposit": float(state.treasury_deposit),
        "usd_reserve": float(state.usd_reserve),
        "cmea_settlement_balance": float(state.cmea_settlement_balance),
        "stock_value_sum": float(np.sum(state.stock_value)),
        "second_output_stock_sum": float(np.sum(state.second_output_stock)),
        "organization_capacity_sum": float(np.sum(state.organization_capacity)),
        "policy": [float(value) for value in np.asarray(political.policy)],
        "scenario_hash": compute_scenario_hash(spec),
        "parameter_hash": session.parameter_hash,
        "initial_recipe_hash": session.initial_recipe_hash,
        "forcing_input_hashes": dict(session.forcing.input_artifact_hashes),
        "external_pack_hash": session.pack.pack_hash,
        "baseline_hash": session.baseline_hash,
        "lock_hash": session.lock_hash,
        "rng_snapshot_digest": canonical_digest(_clean(rng)),
        "rng_draws_by_module": _clean(session.rng.draws_by_module()),
        "rng_active_modules": list(session.rng.active_modules()),
    }
    payload = {
        "material": _state_field_digests(state),
        "political": _state_field_digests(political),
        "explicit": explicit,
        "nonmemory_digest": _nonmemory_digest(state),
    }
    payload["matching_digest"] = canonical_digest(payload)
    return payload


def _differing_columns(before: np.ndarray, after: np.ndarray) -> list[int]:
    if before.shape != after.shape:
        raise ConfigError(f"shape changed: {before.shape} -> {after.shape}")
    if before.ndim == 1:
        return [0] if not np.array_equal(before, after) else []
    columns = []
    for column in range(before.shape[1]):
        if not np.array_equal(before[:, column], after[:, column]):
            columns.append(column)
    return columns


SAME_POINT_KEYS = (
    "quarter",
    "completed_ticks",
    "household_cash_sum",
    "organization_cash_sum",
    "bank_deposit_liability_sum",
    "treasury_deposit",
    "usd_reserve",
    "stock_value_sum",
    "second_output_stock_sum",
    "organization_capacity_sum",
    "policy",
    "scenario_hash",
    "parameter_hash",
    "forcing_input_hashes",
    "external_pack_hash",
    "rng_snapshot_digest",
)


def assert_same_point(left: dict[str, Any], right: dict[str, Any]) -> None:
    """Reject any difference in the declared same-point matching keys."""
    l_explicit = left["explicit"] if "explicit" in left else left
    r_explicit = right["explicit"] if "explicit" in right else right
    mismatched = [key for key in SAME_POINT_KEYS if l_explicit.get(key) != r_explicit.get(key)]
    if mismatched:
        raise ConfigError(f"same-point matching failed on {mismatched}")


def require_political_measurement(tables: dict[str, Any]) -> None:
    """Empty/missing political rows are a missing measurement, never a zero."""
    pq = tables["political_quarters"]
    opp = tables["opposition_regions"]
    info = tables["information_quarters"]
    if pq.height == 0:
        raise ConfigError("political_quarters is empty; political effect is not measurable")
    if opp.height == 0:
        raise ConfigError("opposition_regions is empty; grievance is not measurable")
    gap = info.filter(info["feature_id"] == "contract_gap")
    if gap.height != TICKS:
        raise ConfigError("contract_gap rows are missing; the mediator is not measurable")
    if TREATMENT_QUARTER not in [str(value) for value in pq["quarter"].to_list()]:
        raise ConfigError("treatment quarter is absent from political_quarters")


def apply_memory_transplant(state: Any, donor: dict[str, Any]) -> dict[str, Any]:
    """Copy exactly the three whitelisted memory fields into the live state."""
    expectation = np.asarray(state.household_expectation, dtype=np.float64)
    streak = np.asarray(state.household_improvement_streak, dtype=np.int32)
    reference = np.asarray(state.household_consumption_reference, dtype=np.float64)
    final = donor["final"]
    expectation_values = np.asarray(final["expectation_real_consumption"], dtype=np.float64)
    streak_values = np.asarray(final["streak_real_consumption"], dtype=np.int32)
    reference_values = np.asarray(final["consumption_reference"], dtype=np.float64)
    if expectation_values.shape != (expectation.shape[0],):
        raise ConfigError("donor expectation axis does not match the live household axis")
    if reference_values.shape != reference.shape:
        raise ConfigError("donor consumption reference shape does not match the live state")
    before = {
        "household_expectation": expectation.copy(),
        "household_improvement_streak": streak.copy(),
        "household_consumption_reference": reference.copy(),
    }
    state.household_expectation[:, ENTITLEMENT_REAL_CONSUMPTION] = expectation_values
    state.household_improvement_streak[:, ENTITLEMENT_REAL_CONSUMPTION] = streak_values
    state.household_consumption_reference[:, :] = reference_values
    return before


def audit_transplant_delta(before: dict[str, np.ndarray], after: Any) -> dict[str, Any]:
    changed: dict[str, list[int]] = {}
    allowed = {
        "household_expectation": {ENTITLEMENT_REAL_CONSUMPTION},
        "household_improvement_streak": {ENTITLEMENT_REAL_CONSUMPTION},
        "household_consumption_reference": set(
            range(np.asarray(after.household_consumption_reference).shape[1])
        ),
    }
    for name, old in before.items():
        current = np.asarray(getattr(after, name))
        columns = _differing_columns(old, current)
        if columns:
            changed[name] = columns
        if not set(columns) <= allowed[name]:
            raise ConfigError(f"transplant changed forbidden columns of {name}: {columns}")
    material_after = _state_field_digests(after)
    return {
        "changed_fields": changed,
        "allowed_columns": {name: sorted(values) for name, values in allowed.items()},
        "whitelist_respected": True,
        "material_after": material_after,
    }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _region_weight_share(state: Any, region_count: int) -> np.ndarray:
    region = np.asarray(state.household_region, dtype=np.int64)
    weight = np.asarray(state.household_weight, dtype=np.float64)
    totals = np.bincount(region, weights=weight, minlength=region_count)
    return totals / max(float(totals.sum()), 1e-12)


def _state_metrics(
    *, session: Any, spec: ScenarioSpec, catalog: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the summary record and the full axis-typed adapter payload."""
    from studies.HIST_VNEXT.M01.expectations_adapter import read_expectations

    state = session.state
    payload = read_expectations(state, catalog)
    summary = payload["summary"]
    tick = int(state.completed_ticks) - 1
    quarter = str(spec.start.advance(tick))
    grievance = np.asarray(state.household_grievance, dtype=np.float64)
    weights = np.asarray(state.household_weight, dtype=np.float64)
    region_count = len(spec.region_ids)
    region = np.asarray(state.household_region, dtype=np.int64)
    region_grievance = np.bincount(region, weights=weights * grievance, minlength=region_count)
    region_weight = np.bincount(region, weights=weights, minlength=region_count)
    by_region = region_grievance / np.maximum(region_weight, 1e-12)
    policy = np.asarray(session.political.policy, dtype=np.float64)
    payload["tick"] = tick
    payload["quarter"] = quarter
    payload["units"] = {
        "level": "study_level",
        "expectation": "bounded_score_unit_interval",
        "entitlement": "bounded_score_unit_interval",
        "improvement_streak": "consecutive_quarter_count",
        "consumption_reference": {
            channel: f"synthetic_physical_unit:{channel}" for channel in catalog.household_good_ids
        },
        "grievance": "bounded_score_unit_interval",
        "compliance": "bounded_score_unit_interval",
    }
    payload["matching_field_sha256"] = {
        "household_expectation": _field_digest(state.household_expectation),
        "household_improvement_streak": _field_digest(state.household_improvement_streak),
        "household_consumption_reference": _field_digest(state.household_consumption_reference),
    }
    payload["array_sha256"] = {
        "expectation": _array_digest(np.asarray(payload["expectation"], dtype=np.float64)),
        "entitlement": _array_digest(np.asarray(payload["entitlement"], dtype=np.float64)),
        "improvement_streak": _array_digest(
            np.asarray(payload["improvement_streak"], dtype=np.float64)
        ),
        "consumption_reference": _array_digest(
            np.asarray(payload["consumption_reference"], dtype=np.float64)
        ),
        "grievance": _array_digest(np.asarray(payload["grievance"], dtype=np.float64)),
        "compliance": _array_digest(np.asarray(payload["compliance"], dtype=np.float64)),
    }
    record = {
        "tick": tick,
        "quarter": quarter,
        **summary,
        "expectation_real_consumption_sha256": payload["array_sha256"]["expectation"],
        "consumption_reference_sha256": payload["array_sha256"]["consumption_reference"],
        "entitlement_welfare_mean": float(
            np.mean(state.household_entitlement[:, ENTITLEMENT_WELFARE])
        ),
        "entitlement_real_consumption_mean": float(
            np.mean(state.household_entitlement[:, ENTITLEMENT_REAL_CONSUMPTION])
        ),
        "grievance_national": float(
            np.average(grievance, weights=weights) if float(weights.sum()) > 0 else 0.0
        ),
        "grievance_by_region": {
            region_id: float(by_region[index]) for index, region_id in enumerate(spec.region_ids)
        },
        "policy": {
            coordinate: float(policy[index]) for index, coordinate in enumerate(POLICY_COORDINATES)
        },
    }
    return record, payload


def _read_tables(output_dir: Path) -> dict[str, Any]:
    import polars as pl

    def read(name: str) -> Any:
        path = output_dir / f"{name}.parquet"
        if not path.is_file():
            raise ConfigError(f"required output table missing: {path}")
        return pl.read_parquet(path)

    return {
        "political_quarters": read("political_quarters"),
        "opposition_regions": read("opposition_regions"),
        "information_quarters": read("information_quarters"),
        "household_budgets": read("household_budgets"),
        "national_accounts": read("national_accounts"),
        "organization_diagnostics": read("organization_diagnostics"),
        "tick_diagnostics": read("tick_diagnostics"),
    }


def _table_metrics(
    tables: dict[str, Any], spec: ScenarioSpec, weights: np.ndarray
) -> dict[str, Any]:
    pq = tables["political_quarters"].sort("tick")
    opp = tables["opposition_regions"].sort(["tick", "region_id"])
    budgets = tables["household_budgets"].sort(["tick", "region_id"])
    national = tables["national_accounts"].sort(["tick", "commodity_id"])
    orgs = tables["organization_diagnostics"].sort(["tick", "region_id"])
    info = tables["information_quarters"].sort(["tick", "feature_id"])
    out: dict[str, Any] = {}
    for row in pq.iter_rows(named=True):
        tick = int(row["tick"])
        quarter = str(row["quarter"])
        opp_rows = opp.filter(opp["tick"] == tick)
        grievance_weighted = 0.0
        grievance_regions: dict[str, float] = {}
        for item in opp_rows.iter_rows(named=True):
            value = float(item["weighted_grievance"])
            grievance_regions[str(item["region_id"])] = value
            index = spec.region_ids.index(str(item["region_id"]))
            grievance_weighted += value * float(weights[index])
        budget_rows = budgets.filter(budgets["tick"] == tick)
        national_rows = national.filter(national["tick"] == tick)
        org_rows = orgs.filter(orgs["tick"] == tick)
        info_rows = info.filter((info["tick"] == tick) & (info["feature_id"] == "contract_gap"))
        out[quarter] = {
            "tick": tick,
            "quarter": quarter,
            "policy": {
                coordinate: float(row[f"policy_{coordinate}"]) for coordinate in POLICY_COORDINATES
            },
            "mode": str(row["mode"]),
            "policy_source": str(row["policy_source"]),
            "grievance_national_from_table": grievance_weighted,
            "grievance_by_region": grievance_regions,
            "spending_total": float(budget_rows["spending"].sum()),
            "forced_saving_total": float(budget_rows["forced_saving"].sum()),
            "budget_available_total": float(budget_rows["budget_available"].sum()),
            "pre_purchase_wages_total": float(budget_rows["pre_purchase_wages"].sum()),
            "late_wage_payment_total": float(budget_rows["late_wage_payment"].sum()),
            "voluntary_saving_total": float(budget_rows["voluntary_saving"].sum()),
            "cash_open_total": float(budget_rows["cash_open"].sum()),
            "cash_close_total": float(budget_rows["cash_close"].sum()),
            "wage_arrears_sum": float(org_rows["wage_arrears_sum"].sum()),
            "household_consumption_by_commodity": {
                str(item["commodity_id"]): float(item["household_consumption"])
                for item in national_rows.iter_rows(named=True)
            },
            "imports_by_commodity": {
                str(item["commodity_id"]): float(item["imports"])
                for item in national_rows.iter_rows(named=True)
            },
            "convertible_imports_by_commodity": {
                str(item["commodity_id"]): float(item["convertible_imports"])
                for item in national_rows.iter_rows(named=True)
            },
            "production_by_commodity": {
                str(item["commodity_id"]): float(item["production"])
                for item in national_rows.iter_rows(named=True)
            },
            "contract_gap_truth": (float(info_rows["truth"][0]) if info_rows.height else None),
            "contract_gap_published": (
                float(info_rows["published"][0]) if info_rows.height else None
            ),
            "contract_gap_valid": (bool(info_rows["valid"][0]) if info_rows.height else None),
        }
    return out


def _units(spec: ScenarioSpec) -> dict[str, Any]:
    return {
        "level": "study_level",
        "consumption": {
            commodity: f"synthetic_physical_unit:{commodity}" for commodity in spec.commodities
        },
        "currency": DOMESTIC_CURRENCY,
        "grievance": "bounded_score_unit_interval",
        "expectation": "bounded_score_unit_interval",
        "not_h0b_f2": True,
    }


def _read_arm_native_manifest(output_dir: Path) -> dict[str, Any]:
    return json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))


def _arm_directory_name(seed: int, history_id: str, strength: float | None, cut_id: str) -> str:
    label = "native" if strength is None else f"{float(strength):.1f}"
    return f"{seed}-{history_id}-{label}-{cut_id}"


def _validate_arm_request(
    *, seed: int, history_id: str, formation_ratchet_strength: float | None, cut_id: str
) -> None:
    if seed not in SEEDS:
        raise ConfigError(f"seed {seed} is outside the frozen seed bank {SEEDS}")
    if history_id == "native":
        if formation_ratchet_strength is not None:
            raise ConfigError("native memory cannot carry a formation ratchet strength")
        if cut_id not in NATIVE_CUTS:
            raise ConfigError(f"native budget-only controls allow only {NATIVE_CUTS}")
        return
    if history_id not in HISTORIES:
        raise ConfigError(f"history {history_id!r} is outside {HISTORIES}")
    if formation_ratchet_strength is None or float(formation_ratchet_strength) not in STRENGTHS:
        raise ConfigError(f"formation ratchet strength must be one of {STRENGTHS}")
    if cut_id not in CUTS:
        raise ConfigError(f"cut {cut_id!r} is outside {CUTS}")


# ---------------------------------------------------------------------------
# One arm
# ---------------------------------------------------------------------------


def run_arm(
    *,
    root: Path,
    output_dir: Path,
    seed: int,
    history_id: str,
    formation_ratchet_strength: float | None,
    cut_id: str,
) -> dict[str, Any]:
    """Run exactly one frozen arm of the H5C matrix into a fresh directory."""
    root = Path(root).resolve()
    output_dir = Path(output_dir)
    if output_dir.exists() or output_dir.is_symlink():
        raise ConfigError(f"output directory {output_dir} already exists; refusing to reuse")
    _validate_arm_request(
        seed=seed,
        history_id=history_id,
        formation_ratchet_strength=formation_ratchet_strength,
        cut_id=cut_id,
    )
    spec = _scenario(root, seed)
    contract = load_research_contract(root)
    registry = DataRegistry.load(root, allowed_commodities=spec.commodities)
    interventions = _policy_interventions(spec, cut_id)
    intervention_payload = _intervention_payload(spec, interventions)
    if not intervention_payload["all_coordinates_each_quarter"]:
        raise ConfigError("intervention matrix does not cover all coordinates each quarter")

    session = None
    try:
        session = open_political_session(
            spec,
            output_dir,
            contract,
            registry,
            interventions=interventions,
        )
        for _ in range(WARMUP_TICKS):
            session.admit_quarter()
        if int(session.state.completed_ticks) != WARMUP_TICKS:
            raise ConfigError("warm-up did not stop at the declared treatment boundary")
        opening_matching = _matching_snapshot(session, spec)
        opening_memory, opening_payload = _state_metrics(
            session=session, spec=spec, catalog=session.runtime_network.household_catalog
        )
        memory_dir = output_dir / "memory"
        memory_dir.mkdir()
        _write_memory_payload(
            memory_dir / f"pre-transplant-{opening_memory['quarter']}.json",
            opening_payload,
        )

        donor = None
        delta = None
        if history_id != "native":
            assert formation_ratchet_strength is not None
            donor = donor_memory(
                root=root,
                spec=spec,
                contract=contract,
                history_id=history_id,
                formation_ratchet_strength=formation_ratchet_strength,
            )
            before = apply_memory_transplant(session.state, donor)
            delta = audit_transplant_delta(before, session.state)
        after_matching = _matching_snapshot(session, spec)
        transplanted_memory, transplanted_payload = _state_metrics(
            session=session,
            spec=spec,
            catalog=session.runtime_network.household_catalog,
        )
        _write_memory_payload(
            memory_dir / f"opening-{transplanted_memory['quarter']}.json",
            transplanted_payload,
        )
        if after_matching["nonmemory_digest"] != opening_matching["nonmemory_digest"]:
            raise ConfigError("memory transplant changed non-memory state")
        if (
            history_id == "native"
            and after_matching["matching_digest"] != opening_matching["matching_digest"]
        ):
            raise ConfigError("native budget-only arm changed opening memory")

        post_records: list[dict[str, Any]] = []
        state_grievance_by_tick: dict[int, float] = {}
        for _ in range(TICKS - WARMUP_TICKS):
            session.admit_quarter()
            record, payload = _state_metrics(
                session=session,
                spec=spec,
                catalog=session.runtime_network.household_catalog,
            )
            _write_memory_payload(
                memory_dir / f"post-{record['quarter']}.json",
                payload,
            )
            post_records.append(record)
            state_grievance_by_tick[int(record["tick"])] = float(record["grievance_national"])

        tallies = copy.deepcopy(session.tallies)
        finished = session.finish()
        tables = _read_tables(output_dir)
        require_political_measurement(tables)
        weights = _region_weight_share(session.state, len(spec.region_ids))
        table_metrics = _table_metrics(tables, spec, weights)
        for record in post_records:
            table_metrics[str(record["quarter"])].update(
                {
                    "expectation_real_consumption_mean": float(
                        record["expectation_real_consumption_mean"]
                    ),
                    "expectation_real_consumption_sha256": record[
                        "expectation_real_consumption_sha256"
                    ],
                    "consumption_reference_total": float(record["consumption_reference_total"]),
                    "consumption_reference_sha256": record["consumption_reference_sha256"],
                    "improvement_streak_real_consumption_max": int(
                        record["improvement_streak_real_consumption_max"]
                    ),
                    "entitlement_welfare_mean": float(record["entitlement_welfare_mean"]),
                    "entitlement_real_consumption_mean": float(
                        record["entitlement_real_consumption_mean"]
                    ),
                    "grievance_national_state": float(record["grievance_national"]),
                }
            )

        crosschecks = []
        for record in post_records:
            tick = int(record["tick"])
            quarter = str(record["quarter"])
            table_value = table_metrics[quarter]["grievance_national_from_table"]
            state_value = state_grievance_by_tick[tick]
            if abs(table_value - state_value) > 1e-10 + 1e-8 * max(
                abs(table_value), abs(state_value)
            ):
                raise ConfigError(
                    f"grievance cross-check failed at {quarter}: "
                    f"state {state_value} vs table {table_value}"
                )
            if record["policy"] != table_metrics[quarter]["policy"]:
                raise ConfigError(f"policy table does not match the committed policy at {quarter}")
            crosschecks.append(
                {
                    "tick": tick,
                    "quarter": quarter,
                    "state_grievance_national": state_value,
                    "table_grievance_national": table_value,
                    "policy_equal": True,
                }
            )

        rows = {
            "political_quarters": int(tables["political_quarters"].height),
            "opposition_regions": int(tables["opposition_regions"].height),
            "information_quarters": int(tables["information_quarters"].height),
            "household_budgets": int(tables["household_budgets"].height),
            "national_accounts": int(tables["national_accounts"].height),
        }
        expected_rows = {
            "political_quarters": TICKS,
            "opposition_regions": TICKS * len(spec.region_ids),
            "information_quarters": TICKS * len(POLITICAL_FEATURE_IDS),
            "household_budgets": TICKS * len(spec.region_ids),
            "national_accounts": TICKS * len(spec.commodities),
        }
        if rows != expected_rows:
            raise ConfigError(f"table row counts {rows} != expected {expected_rows}")
        if TREATMENT_QUARTER not in table_metrics:
            raise ConfigError("treatment quarter is missing from the political table")

        matching = {
            "schema_version": SCHEMA_VERSION,
            "seed": seed,
            "history_id": history_id,
            "formation_ratchet_strength": formation_ratchet_strength,
            "cut_id": cut_id,
            "pre": opening_matching,
            "post": after_matching,
            "delta": delta,
            "crosschecks": crosschecks,
            "native_memory": history_id == "native",
            "transplant_whitelist": [
                "household_expectation[:, real_consumption]",
                "household_improvement_streak[:, real_consumption]",
                "household_consumption_reference[:, :]",
            ],
        }
        _dump_json(output_dir / "matching.json", matching)
        if donor is not None:
            _dump_json(output_dir / "memory_trace.json", donor)
        else:
            _dump_json(
                output_dir / "memory_trace.json",
                {
                    "schema_version": SCHEMA_VERSION,
                    "history_id": "native",
                    "transplant": "none",
                    "note": "budget-only negative control keeps the native warm-up memory",
                },
            )
        _dump_json(output_dir / "interventions.json", intervention_payload)

        manifest = _read_arm_native_manifest(output_dir)
        result = {
            "schema_version": SCHEMA_VERSION,
            "phase_id": PHASE_ID,
            "mechanism_id": MECHANISM_ID,
            "study_id": STUDY_ID,
            "arm_id": _arm_directory_name(seed, history_id, formation_ratchet_strength, cut_id),
            "output_dir": str(output_dir),
            "seed": seed,
            "history_id": history_id,
            "formation_ratchet_strength": formation_ratchet_strength,
            "cut_id": cut_id,
            "native_memory": history_id == "native",
            "synthetic_experience": history_id != "native",
            "scenario_id": spec.scenario_id,
            "spec_sha256": _sha256_file(SPEC_PATH),
            "run_id": manifest["run_id"],
            "run_manifest_sha256": _sha256_file(output_dir / "manifest.json"),
            "deterministic_replay_digest": finished.deterministic_replay_digest,
            "completed_ticks": int(finished.completed_ticks),
            "status": str(finished.status),
            "opening": {
                "quarter": opening_matching["explicit"]["quarter"],
                "matching_digest": opening_matching["matching_digest"],
                "nonmemory_digest": opening_matching["nonmemory_digest"],
                "memory_pre_transplant": opening_memory,
                "memory": transplanted_memory,
            },
            "donor": (
                {
                    "history_id": donor["history_id"],
                    "formation_ratchet_strength": donor["formation_ratchet_strength"],
                    "final_expectation_real_consumption_mean": donor["final"][
                        "expectation_real_consumption_mean"
                    ],
                    "final_streak_real_consumption_max": donor["final"][
                        "streak_real_consumption_max"
                    ],
                    "final_consumption_reference_total": donor["final"][
                        "consumption_reference_total"
                    ],
                    "threshold_crossed": donor["final"]["threshold_crossed"],
                    "trace_sha256": _sha256_file(output_dir / "memory_trace.json"),
                }
                if donor is not None
                else None
            ),
            "post_records": post_records,
            "tables": {
                "rows": rows,
                "expected_rows": expected_rows,
                "metrics_by_quarter": table_metrics,
            },
            "units": _units(spec),
            "gates": {
                "max_material_abs_residual": float(tallies["max_material_abs_residual"]),
                "max_material_tolerance_ratio": float(tallies["max_material_tolerance_ratio"]),
                "max_finance_abs_residual": float(tallies["max_finance_abs_residual"]),
                "max_finance_tolerance_ratio": float(tallies["max_finance_tolerance_ratio"]),
                "soviet_violations": int(tallies["soviet_violations"]),
            },
            "matching_sha256": _sha256_file(output_dir / "matching.json"),
            "interventions_sha256": _sha256_file(output_dir / "interventions.json"),
            "memory_files": {
                str(path.relative_to(output_dir)): _sha256_file(path)
                for path in sorted(memory_dir.rglob("*.json"))
            },
            "table_hashes": {
                name: _sha256_file(output_dir / f"{name}.parquet")
                for name in (
                    "political_quarters",
                    "opposition_regions",
                    "information_quarters",
                    "household_budgets",
                    "national_accounts",
                    "organization_diagnostics",
                )
            },
        }
        if result["gates"]["max_material_tolerance_ratio"] > 1.0:
            raise ConfigError("material invariant gate failed")
        if result["gates"]["max_finance_tolerance_ratio"] > 1.0:
            raise ConfigError("finance invariant gate failed")
        _dump_json(output_dir / "result.json", result)
        return result
    except Exception as exc:  # noqa: BLE001 - preserve the failing evidence
        if output_dir.is_dir():
            _dump_json(
                output_dir / "failure.json",
                {
                    "seed": seed,
                    "history_id": history_id,
                    "formation_ratchet_strength": formation_ratchet_strength,
                    "cut_id": cut_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
        if session is not None and not session.finished:
            try:
                session.mark_failed(exc)
            except Exception:  # noqa: BLE001 - failure evidence is best effort
                pass
        raise


# ---------------------------------------------------------------------------
# Reference first stage and cut first stage
# ---------------------------------------------------------------------------


def _reference_first_stage(arms: list[dict[str, Any]]) -> dict[str, Any]:
    seeds = sorted({int(arm["seed"]) for arm in arms})
    by_key = {
        (
            arm["seed"],
            arm["history_id"],
            arm["formation_ratchet_strength"],
            arm["cut_id"],
        ): arm
        for arm in arms
    }
    expected = {
        "one_jump": {"streak": 1, "ablation": True},
        "two_steps": {"streak": 2, "ablation": True},
        "four_steps": {"streak": 4, "ablation": False},
    }
    by_seed: dict[str, Any] = {}
    overall = bool(seeds)
    for seed in seeds:
        ok = True
        histories: dict[str, Any] = {}
        for history in HISTORIES:
            rows = {}
            for strength in STRENGTHS:
                arm = by_key.get((seed, history, strength, "no_cut"))
                if arm is None:
                    ok = False
                    rows[f"{strength}"] = {"status": "MISSING"}
                    continue
                memory = arm["opening"]["memory"]
                rows[f"{strength}"] = {
                    "opening_expectation_real_consumption_mean": memory[
                        "expectation_real_consumption_mean"
                    ],
                    "opening_streak_real_consumption_max": memory[
                        "improvement_streak_real_consumption_max"
                    ],
                    "opening_consumption_reference_total": memory["consumption_reference_total"],
                    "donor_threshold_crossed": arm["donor"]["threshold_crossed"],
                }
            hi, lo = rows["0.1"], rows["0.0"]
            if (
                "opening_expectation_real_consumption_mean" in hi
                and "opening_expectation_real_consumption_mean" in lo
            ):
                rows["ablation_expectation_equal"] = (
                    hi["opening_expectation_real_consumption_mean"]
                    == lo["opening_expectation_real_consumption_mean"]
                )
            else:
                rows["ablation_expectation_equal"] = None
                ok = False
            histories[history] = rows
        for history, rule in expected.items():
            row = histories[history]
            if row["0.1"].get("opening_streak_real_consumption_max") != rule["streak"]:
                ok = False
            if row["ablation_expectation_equal"] != rule["ablation"]:
                ok = False
            if history == "four_steps" and not row["0.1"].get("donor_threshold_crossed"):
                ok = False
        by_seed[str(seed)] = {"status": "PASS" if ok else "BLOCKED", "histories": histories}
        overall = overall and ok
    return {
        "status": "PASS" if overall else "BLOCKED",
        "by_seed": by_seed,
        "expectation": {
            "one_jump": 0.6,
            "two_steps": 0.6375,
            "four_steps": 0.704921875,
        },
        "rule": (
            "every declared seed must pass; four_steps must cross the existing ratchet "
            "threshold and differ between ratchet_strength 0.1 and 0.0; one/two-step "
            "paths must not."
        ),
    }


def _cut_first_stage(arms: list[dict[str, Any]]) -> dict[str, Any]:
    seeds = sorted({int(arm["seed"]) for arm in arms})
    by_key = {
        (
            arm["seed"],
            arm["history_id"],
            arm["formation_ratchet_strength"],
            arm["cut_id"],
        ): arm
        for arm in arms
    }
    by_seed: dict[str, Any] = {}
    overall = bool(seeds)
    for seed in seeds:
        control = by_key.get((seed, "four_steps", 0.1, "no_cut"))
        if control is None:
            by_seed[str(seed)] = {"status": "BLOCKED", "reason": "missing control"}
            overall = False
            continue
        control_tick = control["tables"]["metrics_by_quarter"][TREATMENT_QUARTER]
        out: dict[str, Any] = {}
        for cut in ("income_cut", "welfare_cut", "import_cut"):
            arm = by_key.get((seed, "four_steps", 0.1, cut))
            if arm is None:
                out[cut] = {"status": "MISSING", "binding": False}
                overall = False
                continue
            tick = arm["tables"]["metrics_by_quarter"][TREATMENT_QUARTER]
            policy = tick["policy"]
            applied = abs(float(policy[CUT_PATCH[cut]]) - CUT_VALUE[cut]) <= 1e-12
            recovered = all(
                abs(
                    float(
                        arm["tables"]["metrics_by_quarter"][_quarter_key(k)]["policy"][
                            CUT_PATCH[cut]
                        ]
                    )
                    - float(
                        control["tables"]["metrics_by_quarter"][_quarter_key(k)]["policy"][
                            CUT_PATCH[cut]
                        ]
                    )
                )
                <= 1e-12
                for k in range(TREATMENT_TICK + 1, TICKS)
            )
            flow: dict[str, Any]
            if cut == "income_cut":
                flow_control = control_tick["pre_purchase_wages_total"]
                flow_cut = tick["pre_purchase_wages_total"]
                binding = flow_cut != flow_control
                flow = {
                    "metric": "household_budgets.pre_purchase_wages (region sum)",
                    "control": flow_control,
                    "cut": flow_cut,
                    "difference": flow_cut - flow_control,
                }
            elif cut == "welfare_cut":
                binding = (
                    abs(float(tick["entitlement_welfare_mean"]) - CUT_VALUE[cut]) <= 1e-12
                    and abs(float(control_tick["entitlement_welfare_mean"]) - 0.5) <= 1e-12
                )
                flow = {
                    "metric": "household_entitlement[:, welfare] mean",
                    "control": control_tick["entitlement_welfare_mean"],
                    "cut": tick["entitlement_welfare_mean"],
                }
            else:
                control_imports = control_tick["convertible_imports_by_commodity"]
                cut_imports = tick["convertible_imports_by_commodity"]
                changed = {
                    key: cut_imports[key] - control_imports[key]
                    for key in control_imports
                    if abs(cut_imports[key] - control_imports[key]) > 1e-12
                }
                binding = bool(changed)
                flow = {
                    "metric": "national_accounts.convertible_imports by commodity",
                    "control": control_imports,
                    "cut": cut_imports,
                    "changed_commodities": changed,
                }
            out[cut] = {
                "applied": bool(applied),
                "effective": bool(applied),
                "binding": bool(binding),
                "recovered_after_one_quarter": bool(recovered),
                "status": "BINDING" if binding else "NONBINDING",
                "first_stage": {
                    "policy_coordinate": CUT_PATCH[cut],
                    "target_value": CUT_VALUE[cut],
                    "flow": flow,
                },
            }
            overall = overall and applied and recovered
        by_seed[str(seed)] = out
    summary: dict[str, Any] = {}
    for cut in ("income_cut", "welfare_cut", "import_cut"):
        rows = [
            seed_map[cut]
            for seed_map in by_seed.values()
            if isinstance(seed_map, dict) and cut in seed_map
        ]
        summary[cut] = {
            "applied": bool(rows) and all(bool(row["applied"]) for row in rows),
            "effective": bool(rows) and all(bool(row["effective"]) for row in rows),
            "binding": bool(rows) and all(bool(row["binding"]) for row in rows),
            "recovered_after_one_quarter": bool(rows)
            and all(bool(row["recovered_after_one_quarter"]) for row in rows),
            "status": (
                "BINDING"
                if rows and all(bool(row["binding"]) for row in rows)
                else ("MIXED" if any(bool(row["binding"]) for row in rows) else "NONBINDING")
            ),
            "by_seed": {
                seed: seed_map[cut]
                for seed, seed_map in by_seed.items()
                if isinstance(seed_map, dict) and cut in seed_map
            },
        }
    return {"status": "PASS" if overall else "BLOCKED", "levers": summary, "by_seed": by_seed}


SCALAR_METRICS = (
    "grievance_national_from_table",
    "spending_total",
    "forced_saving_total",
    "budget_available_total",
    "pre_purchase_wages_total",
    "late_wage_payment_total",
    "wage_arrears_sum",
    "contract_gap_truth",
)
VECTOR_METRICS = ("household_consumption_by_commodity",)


def _metric_values(record: dict[str, Any]) -> dict[str, Any]:
    out = {key: record.get(key) for key in SCALAR_METRICS}
    out["expectation_real_consumption_mean"] = record.get("expectation_real_consumption_mean")
    return out


def _diff(cut: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in SCALAR_METRICS:
        a, b = cut.get(key), control.get(key)
        out[key] = None if a is None or b is None else float(a) - float(b)
    out["expectation_real_consumption_mean"] = float(
        cut["expectation_real_consumption_mean"]
    ) - float(control["expectation_real_consumption_mean"])
    for key in VECTOR_METRICS:
        out[key] = {
            commodity: float(cut[key][commodity]) - float(control[key][commodity])
            for commodity in cut[key]
        }
    return out


def _zeros(like: dict[str, Any]) -> dict[str, Any]:
    out = {key: 0.0 for key in SCALAR_METRICS}
    out["expectation_real_consumption_mean"] = 0.0
    for key in VECTOR_METRICS:
        out[key] = {commodity: 0.0 for commodity in like[key]}
    return out


def _add(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in a.items():
        if isinstance(value, dict):
            out[key] = {item: float(value[item]) + float(b[key][item]) for item in value}
        else:
            out[key] = float(value) + float(b[key])
    return out


def _sub(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in a.items():
        if isinstance(value, dict):
            out[key] = {item: float(value[item]) - float(b[key][item]) for item in value}
        else:
            out[key] = float(value) - float(b[key])
    return out


def _sum_quarters(values: list[dict[str, Any]]) -> dict[str, Any]:
    total = _zeros(values[0])
    for value in values:
        total = _add(total, value)
    return total


def _is_nonzero(value: float, reference: float) -> bool:
    return abs(value) > ATOL + RTOL * max(abs(reference), abs(value))


def _effect_status(values: list[float], reference: float) -> str:
    signs = []
    for value in values:
        if not _is_nonzero(value, reference):
            signs.append(0)
        else:
            signs.append(1 if value > 0 else -1)
    if all(sign == 0 for sign in signs):
        return "NUMERIC_ZERO"
    if all(sign > 0 for sign in signs):
        return "POSITIVE"
    if all(sign < 0 for sign in signs):
        return "NEGATIVE"
    return "MIXED"


def _windows(values: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Summarise one arm's per-quarter cut-minus-control series."""
    first = values[_quarter_key(TREATMENT_TICK)]
    second = values[_quarter_key(TREATMENT_TICK + 1)]
    cumulative = _sum_quarters(
        [values[_quarter_key(tick)] for tick in range(TREATMENT_TICK, TICKS)]
    )
    rest = _sum_quarters([values[_quarter_key(tick)] for tick in range(TREATMENT_TICK + 1, TICKS)])
    return {
        "per_quarter": values,
        "first": first,
        "second": second,
        "cumulative": cumulative,
        "rest": rest,
    }


def _control_scale(control_by_quarter: dict[str, Any]) -> dict[str, Any]:
    scale = {
        key: float(
            np.mean(
                [
                    control_by_quarter[_quarter_key(tick)][key]
                    for tick in range(TREATMENT_TICK, TICKS)
                ]
            )
        )
        for key in SCALAR_METRICS
    }
    scale["expectation_real_consumption_mean"] = float(
        np.mean(
            [
                control_by_quarter[_quarter_key(tick)]["expectation_real_consumption_mean"]
                for tick in range(TREATMENT_TICK, TICKS)
            ]
        )
    )
    scale["household_consumption_by_commodity"] = {
        commodity: float(
            np.mean(
                [
                    control_by_quarter[_quarter_key(tick)]["household_consumption_by_commodity"][
                        commodity
                    ]
                    for tick in range(TREATMENT_TICK, TICKS)
                ]
            )
        )
        for commodity in control_by_quarter[_quarter_key(TREATMENT_TICK)][
            "household_consumption_by_commodity"
        ]
    }
    return scale


def _compute_stats(arms: list[dict[str, Any]], seeds: Sequence[int]) -> dict[str, Any]:
    index = {
        (arm["seed"], arm["history_id"], arm["formation_ratchet_strength"], arm["cut_id"]): arm
        for arm in arms
    }
    effects: list[dict[str, Any]] = []
    missing: list[str] = []
    for seed in seeds:
        for strength in STRENGTHS:
            history_windows: dict[str, dict[str, Any]] = {}
            history_scale: dict[str, dict[str, Any]] = {}
            for history in HISTORIES:
                control = index.get((seed, history, strength, "no_cut"))
                if control is None:
                    missing.append(f"{seed}/{history}/{strength}/no_cut")
                    continue
                control_by_quarter = control["tables"]["metrics_by_quarter"]
                history_scale[history] = _control_scale(control_by_quarter)
                for cut in ("income_cut", "welfare_cut", "import_cut"):
                    arm = index.get((seed, history, strength, cut))
                    if arm is None:
                        missing.append(f"{seed}/{history}/{strength}/{cut}")
                        continue
                    values = {
                        _quarter_key(tick): _diff(
                            arm["tables"]["metrics_by_quarter"][_quarter_key(tick)],
                            control_by_quarter[_quarter_key(tick)],
                        )
                        for tick in range(TREATMENT_TICK, TICKS)
                    }
                    history_windows.setdefault(cut, {})[history] = _windows(values)
            for cut in ("income_cut", "welfare_cut", "import_cut"):
                if cut not in history_windows or len(history_windows[cut]) != len(HISTORIES):
                    continue
                r_four = history_windows[cut]["four_steps"]
                r_two = history_windows[cut]["two_steps"]
                r_one = history_windows[cut]["one_jump"]
                d_cumulative = _sub(r_four["cumulative"], r_one["cumulative"])
                d_first = _sub(r_four["first"], r_one["first"])
                d_per_quarter = {
                    quarter: _sub(r_four["per_quarter"][quarter], r_one["per_quarter"][quarter])
                    for quarter in r_four["per_quarter"]
                }
                effects.append(
                    {
                        "seed": seed,
                        "formation_ratchet_strength": strength,
                        "cut_id": cut,
                        "R_by_history": history_windows[cut],
                        "D_four_minus_one_cumulative": d_cumulative,
                        "D_four_minus_one_first_quarter": d_first,
                        "D_four_minus_one_per_quarter": d_per_quarter,
                        "descriptive_slope_two_minus_one_cumulative": _sub(
                            r_two["cumulative"], r_one["cumulative"]
                        ),
                        "descriptive_slope_four_minus_two_half_cumulative": {
                            key: (
                                {
                                    item: 0.5
                                    * (
                                        float(r_four["cumulative"][key][item])
                                        - float(r_two["cumulative"][key][item])
                                    )
                                    for item in r_four["cumulative"][key]
                                }
                                if isinstance(r_four["cumulative"][key], dict)
                                else 0.5
                                * (
                                    float(r_four["cumulative"][key])
                                    - float(r_two["cumulative"][key])
                                )
                            )
                            for key in r_four["cumulative"]
                        },
                        "control_scale_by_history": history_scale,
                    }
                )
        native_control = index.get((seed, "native", None, "no_cut"))
        native_cut = index.get((seed, "native", None, "income_cut"))
        if native_control is None or native_cut is None:
            missing.append(f"{seed}/native/budget-only")
        else:
            control_by_quarter = native_control["tables"]["metrics_by_quarter"]
            values = {
                _quarter_key(tick): _diff(
                    native_cut["tables"]["metrics_by_quarter"][_quarter_key(tick)],
                    control_by_quarter[_quarter_key(tick)],
                )
                for tick in range(TREATMENT_TICK, TICKS)
            }
            effects.append(
                {
                    "seed": seed,
                    "formation_ratchet_strength": None,
                    "cut_id": "income_cut",
                    "history_id": "native",
                    "budget_only_control": True,
                    "R_native": _windows(values),
                }
            )
    # N = D(ratchet_strength=0.1) - D(ratchet_strength=0.0)
    ablation: list[dict[str, Any]] = []
    by_key = {
        (row["seed"], row["formation_ratchet_strength"], row["cut_id"]): row
        for row in effects
        if not row.get("budget_only_control")
    }
    for seed in seeds:
        for cut in ("income_cut", "welfare_cut", "import_cut"):
            high = by_key.get((seed, 0.1, cut))
            low = by_key.get((seed, 0.0, cut))
            if high is None or low is None:
                missing.append(f"{seed}/{cut}/ablation")
                continue
            n_cumulative = _sub(
                high["D_four_minus_one_cumulative"], low["D_four_minus_one_cumulative"]
            )
            n_first = _sub(
                high["D_four_minus_one_first_quarter"], low["D_four_minus_one_first_quarter"]
            )
            reference = high["control_scale_by_history"]["four_steps"]
            ablation.append(
                {
                    "seed": seed,
                    "cut_id": cut,
                    "N_cumulative": n_cumulative,
                    "N_first_quarter": n_first,
                    "N_status": {
                        key: _effect_status(
                            [float(n_cumulative[key])],
                            float(reference.get(key, 0.0) or 0.0),
                        )
                        for key in (*SCALAR_METRICS, "expectation_real_consumption_mean")
                    },
                    "expected": (
                        "zero for one/two because no threshold crossing; the four-minus-one "
                        "contrast may carry the formation ratchet only through four_steps"
                    ),
                }
            )
    return {"effects": effects, "ablation": ablation, "missing": missing}


def _verdict(
    stats: dict[str, Any],
    first_stage: dict[str, Any],
    cuts: dict[str, Any],
    political_ok: bool,
) -> dict[str, Any]:
    levers: dict[str, Any] = {}
    for cut in ("income_cut", "welfare_cut", "import_cut"):
        binding = cuts.get(cut, {}).get("binding")
        all_rows = [
            row
            for row in stats["effects"]
            if row["cut_id"] == cut and not row.get("budget_only_control")
        ]
        rows = [row for row in all_rows if row["formation_ratchet_strength"] == 0.1]
        ablation_rows = [row for row in all_rows if row["formation_ratchet_strength"] == 0.0]
        grievance_d = {
            str(row["seed"]): float(
                row["D_four_minus_one_cumulative"]["grievance_national_from_table"]
            )
            for row in rows
        }
        spending_d = {
            str(row["seed"]): float(row["D_four_minus_one_cumulative"]["spending_total"])
            for row in rows
        }
        consumption_d = {
            commodity: {
                str(row["seed"]): float(
                    row["D_four_minus_one_cumulative"]["household_consumption_by_commodity"][
                        commodity
                    ]
                )
                for row in rows
            }
            for commodity in (
                rows[0]["D_four_minus_one_cumulative"]["household_consumption_by_commodity"]
                if rows
                else {}
            )
        }
        if binding is False:
            status = "NONBINDING"
        elif not rows:
            status = "UNIDENTIFIED"
        else:
            grievance_status = _effect_status(list(grievance_d.values()), 0.03)
            spending_status = _effect_status(list(spending_d.values()), 1.0)
            if grievance_status == "NUMERIC_ZERO" and spending_status == "NUMERIC_ZERO":
                status = "ZERO_EFFECT"
            elif grievance_status in ("POSITIVE", "NEGATIVE") or spending_status in (
                "POSITIVE",
                "NEGATIVE",
            ):
                status = "CONDITIONAL_CARRIED_REFERENCE_EFFECT"
            else:
                status = "UNIDENTIFIED"
        n_rows = [row for row in stats["ablation"] if row["cut_id"] == cut]
        n_grievance = [
            float(row["N_cumulative"]["grievance_national_from_table"]) for row in n_rows
        ]
        n_spending = [float(row["N_cumulative"]["spending_total"]) for row in n_rows]
        levers[cut] = {
            "binding": binding,
            "status": status,
            "D_four_minus_one_grievance_by_seed": grievance_d,
            "D_four_minus_one_spending_by_seed": spending_d,
            "main_strength": 0.1,
            "D_four_minus_one_grievance_by_seed_strength_zero": {
                str(row["seed"]): float(
                    row["D_four_minus_one_cumulative"]["grievance_national_from_table"]
                )
                for row in ablation_rows
            },
            "D_four_minus_one_spending_by_seed_strength_zero": {
                str(row["seed"]): float(row["D_four_minus_one_cumulative"]["spending_total"])
                for row in ablation_rows
            },
            "D_four_minus_one_consumption_status_by_commodity": {
                commodity: _effect_status(
                    list(values.values()),
                    float(
                        rows[0]["control_scale_by_history"]["four_steps"][
                            "household_consumption_by_commodity"
                        ][commodity]
                    )
                    if rows
                    else 0.0,
                )
                for commodity, values in consumption_d.items()
            },
            "ratchet_ablation_N_grievance_by_seed": {
                str(row["seed"]): float(row["N_cumulative"]["grievance_national_from_table"])
                for row in n_rows
            },
            "ratchet_ablation_N_spending_by_seed": {
                str(row["seed"]): float(row["N_cumulative"]["spending_total"]) for row in n_rows
            },
            "ratchet_ablation_status": {
                "grievance": _effect_status(n_grievance, 0.03),
                "spending": _effect_status(n_spending, 1.0),
            },
            "note": (
                "the history contrast is conditional on the synthetic carried reference; "
                "it is not a pure streak-duration curvature and not a historical estimate"
            ),
        }
    return {
        "reference_first_stage": first_stage["status"],
        "political_measurability": "PASS" if political_ok else "BLOCKED",
        "levers": levers,
        "historical_status": "UNIDENTIFIED",
        "historical_reason": (
            "no admitted D14 series identifies improvement expectations, equal cuts and "
            "same-period household/local responses"
        ),
        "economic_margin": "UNIDENTIFIED",
    }


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


def _fresh_dir(path: Path) -> Path:
    if path.exists() or path.is_symlink():
        raise ConfigError(f"output directory {path} already exists; refusing to reuse")
    path.mkdir(parents=True)
    return path


def _run_matrix(root: Path, output_dir: Path, seeds: Sequence[int]) -> dict[str, Any]:
    arms_dir = _fresh_dir(output_dir) / "arms"
    arms_dir.mkdir()
    arms: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for seed in seeds:
        for history in HISTORIES:
            for strength in STRENGTHS:
                for cut in CUTS:
                    arm_dir = arms_dir / _arm_directory_name(seed, history, strength, cut)
                    try:
                        arms.append(
                            run_arm(
                                root=root,
                                output_dir=arm_dir,
                                seed=seed,
                                history_id=history,
                                formation_ratchet_strength=strength,
                                cut_id=cut,
                            )
                        )
                    except Exception as exc:  # noqa: BLE001 - record, do not relabel
                        failures.append(
                            {
                                "seed": seed,
                                "history_id": history,
                                "formation_ratchet_strength": strength,
                                "cut_id": cut,
                                "arm_id": _arm_directory_name(seed, history, strength, cut),
                                "error_type": type(exc).__name__,
                                "error": str(exc),
                            }
                        )
        for cut in NATIVE_CUTS:
            arm_dir = arms_dir / _arm_directory_name(seed, "native", None, cut)
            try:
                arms.append(
                    run_arm(
                        root=root,
                        output_dir=arm_dir,
                        seed=seed,
                        history_id="native",
                        formation_ratchet_strength=None,
                        cut_id=cut,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "seed": seed,
                        "history_id": "native",
                        "formation_ratchet_strength": None,
                        "cut_id": cut,
                        "arm_id": _arm_directory_name(seed, "native", None, cut),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )

    group_checks: dict[str, Any] = {}
    for seed in seeds:
        selected = [arm for arm in arms if arm["seed"] == seed]
        if not selected:
            continue
        pre_digests = {arm["opening"]["matching_digest"] for arm in selected}
        nonmemory = {arm["opening"]["nonmemory_digest"] for arm in selected}
        warmup = {
            json.loads(
                (arms_dir / arm["arm_id"] / "interventions.json").read_text(encoding="utf-8")
            )["warmup_sha256"]
            for arm in selected
        }
        group_checks[str(seed)] = {
            "arms": len(selected),
            "pre_matching_digest_unique": sorted(pre_digests),
            "pre_matching_equal": len(pre_digests) == 1,
            "opening_nonmemory_equal": len(nonmemory) == 1,
            "warmup_interventions_equal": len(warmup) == 1,
            "budget_only_opening_memory_equals_transplant_pre": all(
                arm["opening"]["matching_digest"] in pre_digests for arm in selected
            ),
        }
        try:
            for arm in selected[1:]:
                assert_same_point(selected[0]["opening"], arm["opening"])
        except ConfigError as exc:
            failures.append({"seed": seed, "error_type": "MatchingError", "error": str(exc)})
        if not (
            group_checks[str(seed)]["pre_matching_equal"]
            and group_checks[str(seed)]["opening_nonmemory_equal"]
            and group_checks[str(seed)]["warmup_interventions_equal"]
        ):
            failures.append(
                {"seed": seed, "error_type": "MatchingError", "error": "group mismatch"}
            )

    stats = _compute_stats(arms, seeds)
    if stats["missing"]:
        failures.append(
            {"error_type": "MatrixError", "error": "missing arms", "missing": stats["missing"]}
        )
    first_stage = _reference_first_stage(arms)
    cuts = _cut_first_stage(arms) if arms else {"status": "BLOCKED"}
    political_ok = all(
        arm["tables"]["rows"]["opposition_regions"] > 0
        and arm["tables"]["rows"]["information_quarters"] > 0
        and TREATMENT_QUARTER in arm["tables"]["metrics_by_quarter"]
        for arm in arms
    )
    verdict = _verdict(stats, first_stage, cuts.get("levers", cuts), political_ok)
    technical = (
        not failures
        and first_stage["status"] == "PASS"
        and cuts["status"] == "PASS"
        and all(check["pre_matching_equal"] for check in group_checks.values())
        and all(
            check["opening_nonmemory_equal"] and check["warmup_interventions_equal"]
            for check in group_checks.values()
        )
    )
    study = {
        "schema_version": SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "mechanism_id": MECHANISM_ID,
        "study_id": STUDY_ID,
        "seeds": list(seeds),
        "matrix": {
            "expected_arms": len(seeds) * 26,
            "completed_arms": len(arms),
            "tick_count": TICKS,
            "treatment_tick": TREATMENT_TICK,
            "treatment_quarter": TREATMENT_QUARTER,
            "histories": list(HISTORIES),
            "strengths": list(STRENGTHS),
            "cuts": list(CUTS),
            "native_cuts": list(NATIVE_CUTS),
        },
        "technical_status": "PASS" if technical else "BLOCKED",
        "reference_first_stage": first_stage,
        "cut_first_stage": cuts,
        "group_checks": group_checks,
        "statistics": stats,
        "verdict": verdict,
        "failures": failures,
        "false_zero_policy": (
            "missing/empty tables are failures, not zero effects; a numeric zero is "
            "only reported when the real producer emitted finite rows"
        ),
        "rng_note": (
            "3 paired seeds are an engineering bank, not a power calculation; no "
            "p-value or arbitrary percentage threshold promotes a historical claim"
        ),
        "historical_status": "UNIDENTIFIED",
    }
    _dump_json(output_dir / "study.json", study)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "study_id": STUDY_ID,
        "spec_sha256": _sha256_file(SPEC_PATH),
        "files": _file_manifest(output_dir),
    }
    _dump_json(output_dir / "manifest.json", manifest)
    return study


def _welfare_not_cash_probe(root: Path, target: Path) -> dict[str, Any]:
    """Run two real 1-tick sessions: welfare 0.5 vs 0.4 with identical cash."""
    spec = _scenario_for(root, 1729, 1, "hist_vnext_h5c_m01_welfare_probe")
    contract = load_research_contract(root)
    registry = DataRegistry.load(root, allowed_commodities=spec.commodities)
    rows: dict[str, Any] = {}
    for label, cut_id in (("welfare_050", "no_cut"), ("welfare_040", "welfare_cut")):
        arm_dir = target / label
        session = open_political_session(
            spec,
            arm_dir,
            contract,
            registry,
            interventions=_policy_interventions(spec, cut_id, ticks=1, treatment_tick=0),
        )
        opening_cash = float(np.sum(session.state.household_cash))
        opening_org = float(np.sum(session.state.organization_cash))
        opening_treasury = float(session.state.treasury_deposit)
        session.admit_quarter()
        closing_cash = float(np.sum(session.state.household_cash))
        session.finish()
        rows[label] = {
            "household_cash_open_sum": opening_cash,
            "household_cash_close_sum": closing_cash,
            "organization_cash_open_sum": opening_org,
            "treasury_open": opening_treasury,
            "entitlement_welfare_mean": float(
                np.mean(session.state.household_entitlement[:, ENTITLEMENT_WELFARE])
            ),
            "entitlement_real_consumption_mean": float(
                np.mean(session.state.household_entitlement[:, ENTITLEMENT_REAL_CONSUMPTION])
            ),
            "grievance_mean": float(np.mean(session.state.household_grievance)),
            "policy_welfare_provision": float(session.political.policy[12]),
        }
    return {
        "probe": "welfare provision 0.5 -> 0.4 in a real 1-tick session",
        "arms": rows,
        "cash_books_identical": all(
            rows["welfare_050"][key] == rows["welfare_040"][key]
            for key in (
                "household_cash_open_sum",
                "household_cash_close_sum",
                "organization_cash_open_sum",
                "treasury_open",
            )
        ),
        "welfare_entitlement_moved": (
            rows["welfare_050"]["entitlement_welfare_mean"]
            != rows["welfare_040"]["entitlement_welfare_mean"]
        ),
        "note": (
            "welfare_provision moves an entitlement component, never a cash "
            "transfer; household cash and the Treasury opening are unchanged."
        ),
    }


def _run_reproduce(root: Path, output_dir: Path, c0_dir: Path | None) -> dict[str, Any]:
    target = _fresh_dir(output_dir)
    spec = _scenario(root, 1729)
    contract = load_research_contract(root)
    card_path = root / "config/p06/cards/M1.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    intervals = ["1961Q1", "1967Q1"]
    card_counterexample = {
        "card_path": "config/p06/cards/M1.json",
        "card_sha256": _sha256_file(card_path),
        "manipulated_variables": card["manipulated_variables"],
        "quarters": intervals,
        "matched_pair_possible": False,
        "reason": (
            "1961Q1 and 1967Q1 are different calendar points and different macro "
            "conditions; no same-quarter control can be formed."
        ),
        "metrics": card["metrics"],
        "minimum_replicates": card["minimum_replicates"],
        "forced_saving_only": False,
        "forced_saving_note": (
            "forced_saving is one of five declared metrics; it cannot stand in for "
            "grievance, consumption, policy or expectations."
        ),
    }
    c0 = {"status": "NOT_RUN", "reason": "no --c0-dir supplied"}
    if c0_dir is not None:
        import polars as pl

        tables = {}
        for name in ("political_quarters", "opposition_regions", "information_quarters"):
            path = c0_dir / f"{name}.parquet"
            if not path.is_file():
                tables[name] = {"status": "table_empty", "rows": None}
            else:
                tables[name] = {"status": "present", "rows": int(pl.read_parquet(path).height)}
        c0 = {
            "status": "MEASURED",
            "c0_dir": str(c0_dir),
            "tables": tables,
            "zero_rows_is_missing_measurement": True,
            "note": (
                "the C0 political tables are empty; an empty table cannot adjudicate a "
                "zero political response."
            ),
        }
    donor_checks = {}
    for history in HISTORIES:
        high = donor_memory(
            root=root,
            spec=spec,
            contract=contract,
            history_id=history,
            formation_ratchet_strength=0.1,
        )
        zero = donor_memory(
            root=root,
            spec=spec,
            contract=contract,
            history_id=history,
            formation_ratchet_strength=0.0,
        )
        donor_checks[history] = {
            "final_expectation_0.1": high["final"]["expectation_real_consumption_mean"],
            "final_expectation_0.0": zero["final"]["expectation_real_consumption_mean"],
            "final_streak_0.1": high["final"]["streak_real_consumption_max"],
            "final_streak_0.0": zero["final"]["streak_real_consumption_max"],
            "threshold_crossed": high["final"]["threshold_crossed"],
            "ablation_expectation_equal": (
                high["final"]["expectation_real_consumption_mean"]
                == zero["final"]["expectation_real_consumption_mean"]
            ),
        }
    welfare_probe = _welfare_not_cash_probe(root, target)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "study_id": STUDY_ID,
        "card_counterexample": card_counterexample,
        "welfare_probe": welfare_probe,
        "c0_counterexample": c0,
        "donor_first_stage": donor_checks,
        "planning_probe_failures": {
            "source": "PLAN.md verified facts (not reproduced in this session)",
            "failures": [
                "ExternalWorldSlice required origins/evidence_status",
                "diagnostic read a nonexistent treasury_cash field",
            ],
            "classification": "probe construction errors, not model accounting failures",
        },
        "design_consequence": [
            "same-quarter, same-cash, same-supply matched arms replace the 1961/1967 comparison",
            "political rows must be non-empty and include 1958Q1",
            "forced_saving alone is not promoted to the M1 verdict",
        ],
    }
    _dump_json(target / "counterexamples.json", payload)
    _dump_json(
        target / "manifest.json",
        {
            "schema_version": SCHEMA_VERSION,
            "spec_sha256": _sha256_file(SPEC_PATH),
            "files": _file_manifest(target),
        },
    )
    return payload


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------


class VerificationError(RuntimeError):
    pass


def _load_manifest(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "manifest.json"
    if not path.is_file():
        raise VerificationError(f"missing manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_files(output_dir: Path, manifest: dict[str, Any]) -> None:
    root = output_dir.resolve()
    recorded = {entry["path"]: entry for entry in manifest["files"]}
    actual = {entry["path"]: entry for entry in _file_manifest(output_dir)}
    if set(recorded) != set(actual):
        missing = sorted(set(recorded) - set(actual))
        extra = sorted(set(actual) - set(recorded))
        raise VerificationError(f"file set changed; missing={missing} extra={extra}")
    for relative, entry in recorded.items():
        path = (root / relative).resolve()
        if not str(path).startswith(str(root) + "/") and path != root:
            raise VerificationError(f"path escapes the evidence root: {relative}")
        if _sha256_file(path) != entry["sha256"]:
            raise VerificationError(f"sha mismatch: {relative}")
        if path.stat().st_size != int(entry["bytes"]):
            raise VerificationError(f"size mismatch: {relative}")


def _load_memory_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    axes = payload.get("axes", {})
    households = axes.get("household")
    entitlements = axes.get("entitlement")
    channels = axes.get("channel")
    if entitlements != list(ENTITLEMENT_IDS):
        raise VerificationError(f"memory entitlement axis changed: {path}")
    if channels != list(INTERMEDIATE8_AXIS.good_ids):
        raise VerificationError(f"memory channel axis changed: {path}")
    if not isinstance(households, list) or not households:
        raise VerificationError(f"memory household axis missing: {path}")
    n, e, h = len(households), len(entitlements), len(channels)
    shapes = {
        "expectation": (n, e),
        "entitlement": (n, e),
        "improvement_streak": (n, e),
        "consumption_reference": (n, h),
        "grievance": (n,),
        "compliance": (n,),
    }
    for name, shape in shapes.items():
        array = np.asarray(payload.get(name), dtype=np.float64)
        if array.shape != shape:
            raise VerificationError(f"memory {name} shape {array.shape} != {shape}")
        if not np.all(np.isfinite(array)):
            raise VerificationError(f"memory {name} is non-finite")
        if _array_digest(array) != payload.get("array_sha256", {}).get(name):
            raise VerificationError(f"memory {name} digest mismatch: {path}")
    streak = np.asarray(payload["improvement_streak"], dtype=np.float64)
    if np.any(streak < 0.0) or not np.all(streak == np.floor(streak)):
        raise VerificationError(f"memory streak is not a non-negative integer: {path}")
    for key in ("tick", "quarter", "summary", "units"):
        if key not in payload:
            raise VerificationError(f"memory payload missing {key}: {path}")
    return payload


def _memory_field_digest(name: str, payload: dict[str, Any]) -> str:
    if name == "household_expectation":
        array = np.asarray(payload["expectation"], dtype=np.float64)
    elif name == "household_improvement_streak":
        array = np.asarray(payload["improvement_streak"], dtype=np.int32)
    elif name == "household_consumption_reference":
        array = np.asarray(payload["consumption_reference"], dtype=np.float64)
    else:
        raise ConfigError(f"unknown memory field {name}")
    return _array_digest(array)


def _recompute_memory_summary(
    payload: dict[str, Any], household_weight: np.ndarray
) -> dict[str, Any]:
    expectation = np.asarray(payload["expectation"], dtype=np.float64)
    streak = np.asarray(payload["improvement_streak"], dtype=np.int32)
    reference = np.asarray(payload["consumption_reference"], dtype=np.float64)
    grievance = np.asarray(payload["grievance"], dtype=np.float64)
    compliance = np.asarray(payload["compliance"], dtype=np.float64)
    weights = np.asarray(household_weight, dtype=np.float64)
    if weights.shape != (expectation.shape[0],):
        raise VerificationError("household weights do not match the memory axis")
    return {
        "expectation_real_consumption_mean": float(
            np.mean(expectation[:, ENTITLEMENT_REAL_CONSUMPTION])
        ),
        "improvement_streak_real_consumption_max": int(
            np.max(streak[:, ENTITLEMENT_REAL_CONSUMPTION])
        ),
        "consumption_reference_total": float(np.sum(reference)),
        "grievance_weighted_mean": float(np.average(grievance, weights=weights)),
        "compliance_weighted_mean": float(np.average(compliance, weights=weights)),
    }


def _memory_metrics(payload: dict[str, Any], household_weight: np.ndarray) -> dict[str, Any]:
    summary = _recompute_memory_summary(payload, household_weight)
    entitlement = np.asarray(payload["entitlement"], dtype=np.float64)
    return {
        "expectation_real_consumption_mean": summary["expectation_real_consumption_mean"],
        "improvement_streak_real_consumption_max": summary[
            "improvement_streak_real_consumption_max"
        ],
        "consumption_reference_total": summary["consumption_reference_total"],
        "expectation_real_consumption_sha256": _memory_field_digest(
            "household_expectation", payload
        ),
        "consumption_reference_sha256": _memory_field_digest(
            "household_consumption_reference", payload
        ),
        "entitlement_welfare_mean": float(np.mean(entitlement[:, ENTITLEMENT_WELFARE])),
        "entitlement_real_consumption_mean": float(
            np.mean(entitlement[:, ENTITLEMENT_REAL_CONSUMPTION])
        ),
        "grievance_national_state": summary["grievance_weighted_mean"],
    }


def _post_memory_metrics(payload: dict[str, Any], household_weight: np.ndarray) -> dict[str, Any]:
    return _memory_metrics(payload, household_weight)


def _compare_nested(recorded: Any, fresh: Any, path: str) -> None:
    if isinstance(recorded, dict) and isinstance(fresh, dict):
        if set(recorded) != set(fresh):
            raise VerificationError(f"{path} key set changed")
        for key in recorded:
            _compare_nested(recorded[key], fresh[key], f"{path}.{key}")
        return
    if isinstance(recorded, bool) or isinstance(fresh, bool):
        if recorded != fresh:
            raise VerificationError(f"{path} changed")
        return
    if isinstance(recorded, (int, float)) and isinstance(fresh, (int, float)):
        if not np.isfinite(float(recorded)) or not np.isfinite(float(fresh)):
            raise VerificationError(f"{path} is non-finite")
        if abs(float(recorded) - float(fresh)) > ATOL + RTOL * max(
            abs(float(recorded)), abs(float(fresh))
        ):
            raise VerificationError(f"{path} was altered")
        return
    if recorded != fresh:
        raise VerificationError(f"{path} was altered")


def _verify_arm(arm_dir: Path) -> dict[str, Any]:
    import polars as pl

    result = json.loads((arm_dir / "result.json").read_text(encoding="utf-8"))
    matching = json.loads((arm_dir / "matching.json").read_text(encoding="utf-8"))
    native = json.loads((arm_dir / "manifest.json").read_text(encoding="utf-8"))
    interventions = json.loads((arm_dir / "interventions.json").read_text(encoding="utf-8"))
    expected_name = _arm_directory_name(
        result["seed"], result["history_id"], result["formation_ratchet_strength"], result["cut_id"]
    )
    if arm_dir.name != expected_name:
        raise VerificationError(f"arm directory {arm_dir.name} != {expected_name}")
    row_spec = _scenario(_REPO_ROOT, int(result["seed"]))
    if native["scenario_hash"] != compute_scenario_hash(row_spec):
        raise VerificationError("native manifest scenario hash changed")
    if int(native["seed"]) != int(result["seed"]):
        raise VerificationError("native manifest seed changed")
    if int(native["ticks"]) != TICKS or int(native["completed_ticks"]) != TICKS:
        raise VerificationError("native manifest tick coverage changed")
    if native["status"] != "completed":
        raise VerificationError("native manifest is not completed")
    if native["deterministic_replay_digest"] != result["deterministic_replay_digest"]:
        raise VerificationError("digest mismatch")
    if result["matching_sha256"] != _sha256_file(arm_dir / "matching.json"):
        raise VerificationError("matching sidecar hash mismatch")
    if result["interventions_sha256"] != _sha256_file(arm_dir / "interventions.json"):
        raise VerificationError("interventions sidecar hash mismatch")
    if interventions["count"] != TICKS * len(POLICY_COORDINATES):
        raise VerificationError("intervention count changed")
    if matching["pre"]["matching_digest"] != result["opening"]["matching_digest"]:
        raise VerificationError("opening matching digest changed")
    if not matching.get("delta") and result["history_id"] != "native":
        raise VerificationError("transplant arm has no delta audit")
    pre_matching = matching["pre"]
    post_matching = matching["post"]
    for block in (pre_matching, post_matching):
        expected_digest = canonical_digest(
            {
                "material": block["material"],
                "political": block["political"],
                "explicit": block["explicit"],
                "nonmemory_digest": block["nonmemory_digest"],
            }
        )
        if expected_digest != block["matching_digest"]:
            raise VerificationError("matching digest does not recompute")
    if post_matching["nonmemory_digest"] != pre_matching["nonmemory_digest"]:
        raise VerificationError("transplant changed non-memory digest")
    for key in SAME_POINT_KEYS:
        if post_matching["explicit"].get(key) != pre_matching["explicit"].get(key):
            raise VerificationError(f"post-transplant explicit {key} changed")
    changed_names = set(matching["delta"]["changed_fields"]) if matching.get("delta") else set()
    for name, digest in pre_matching["political"].items():
        if post_matching["political"].get(name) != digest:
            raise VerificationError(f"political field {name} changed at transplant")
    for name, digest in pre_matching["material"].items():
        if name in changed_names:
            continue
        if post_matching["material"].get(name) != digest:
            raise VerificationError(f"material field {name} changed at transplant")
    if result["opening"]["nonmemory_digest"] != pre_matching["nonmemory_digest"]:
        raise VerificationError("result opening non-memory digest changed")
    if matching.get("delta"):
        allowed = matching["delta"]["allowed_columns"]
        for name, columns in matching["delta"]["changed_fields"].items():
            if not set(columns) <= set(allowed[name]):
                raise VerificationError("delta whitelist violated")

    for table in (
        "political_quarters",
        "opposition_regions",
        "information_quarters",
        "household_budgets",
        "national_accounts",
        "organization_diagnostics",
    ):
        if not (arm_dir / f"{table}.parquet").is_file():
            raise VerificationError(f"required table missing: {table}.parquet")
    pq = pl.read_parquet(arm_dir / "political_quarters.parquet")
    opp = pl.read_parquet(arm_dir / "opposition_regions.parquet")
    info = pl.read_parquet(arm_dir / "information_quarters.parquet")
    budgets = pl.read_parquet(arm_dir / "household_budgets.parquet")
    national = pl.read_parquet(arm_dir / "national_accounts.parquet")
    expected = {
        "political_quarters": TICKS,
        "opposition_regions": TICKS * len(native["region_ids"]),
        "information_quarters": TICKS * len(POLITICAL_FEATURE_IDS),
        "household_budgets": TICKS * len(native["region_ids"]),
        "national_accounts": TICKS * len(native["commodity_ids"]),
    }
    measured = {
        "political_quarters": pq.height,
        "opposition_regions": opp.height,
        "information_quarters": info.height,
        "household_budgets": budgets.height,
        "national_accounts": national.height,
    }
    if measured != expected:
        raise VerificationError(f"table rows {measured} != {expected}")
    quarters = [str(value) for value in pq["quarter"].to_list()]
    if quarters != [_quarter_key(tick) for tick in range(TICKS)]:
        raise VerificationError("political quarter coverage changed")
    if TREATMENT_QUARTER not in quarters:
        raise VerificationError("treatment quarter is missing")
    cut_id = result["cut_id"]
    expected_policy = default_initial_policy(row_spec)
    for row in pq.iter_rows(named=True):
        tick = int(row["tick"])
        for coordinate in POLICY_COORDINATES:
            value = float(getattr(expected_policy, coordinate))
            if tick == TREATMENT_TICK and coordinate == CUT_PATCH.get(cut_id, ""):
                value = CUT_VALUE[cut_id]
            if abs(float(row[f"policy_{coordinate}"]) - value) > 1e-12:
                raise VerificationError(
                    f"policy {coordinate} at {row['quarter']} != declared SET value"
                )
    if not np.all(np.isfinite(np.asarray(opp["weighted_grievance"], dtype=np.float64))):
        raise VerificationError("non-finite grievance in the real table")
    gap = info.filter(info["feature_id"] == "contract_gap")
    if gap.height != TICKS:
        raise VerificationError("contract_gap rows missing")
    if not np.all(np.isfinite(np.asarray(gap["truth"], dtype=np.float64))):
        raise VerificationError("non-finite contract_gap truth")
    # Recompute the primary table metrics from actual rows.
    spec = _scenario(_REPO_ROOT, int(result["seed"]))
    initial = build_material_initial_conditions(spec, RngRegistry(spec.seed))
    network = build_material_network(spec, load_research_contract(_REPO_ROOT), initial)
    base_state = initialize_material(spec, initial, network)
    weights = _region_weight_share(base_state, len(spec.region_ids))
    household_weight = np.asarray(base_state.household_weight, dtype=np.float64)
    tables = {
        "political_quarters": pq,
        "opposition_regions": opp,
        "information_quarters": info,
        "household_budgets": budgets,
        "national_accounts": national,
        "organization_diagnostics": pl.read_parquet(arm_dir / "organization_diagnostics.parquet"),
        "tick_diagnostics": pl.read_parquet(arm_dir / "tick_diagnostics.parquet"),
    }
    recomputed = _table_metrics(tables, spec, weights)

    memory_files = result.get("memory_files")
    if not isinstance(memory_files, dict):
        raise VerificationError("memory file manifest missing")
    memory_root = arm_dir / "memory"
    actual_memory = {
        str(path.relative_to(arm_dir)): _sha256_file(path)
        for path in sorted(memory_root.rglob("*.json"))
    }
    if actual_memory != memory_files:
        raise VerificationError("memory file set or hashes changed")
    opening_name = f"memory/opening-{_quarter_key(WARMUP_TICKS - 1)}.json"
    pre_name = f"memory/pre-transplant-{_quarter_key(WARMUP_TICKS - 1)}.json"
    expected_memory = {
        opening_name,
        pre_name,
        *[f"memory/post-{_quarter_key(tick)}.json" for tick in range(TREATMENT_TICK, TICKS)],
    }
    if set(actual_memory) != expected_memory:
        raise VerificationError("memory quarter coverage changed")
    payloads = {relative: _load_memory_payload(arm_dir / relative) for relative in actual_memory}
    for relative, payload in payloads.items():
        _compare_nested(
            payload["summary"],
            _recompute_memory_summary(payload, household_weight),
            f"{relative}.summary",
        )
    opening_payload = payloads[opening_name]
    pre_payload = payloads[pre_name]
    allowed_columns = {
        "household_expectation": {ENTITLEMENT_REAL_CONSUMPTION},
        "household_improvement_streak": {ENTITLEMENT_REAL_CONSUMPTION},
        "household_consumption_reference": set(range(len(opening_payload["axes"]["channel"]))),
    }
    array_keys = {
        "household_expectation": "expectation",
        "household_improvement_streak": "improvement_streak",
        "household_consumption_reference": "consumption_reference",
    }
    actual_changed: dict[str, list[int]] = {}
    for name, key in array_keys.items():
        before = np.asarray(pre_payload[key], dtype=np.float64)
        after = np.asarray(opening_payload[key], dtype=np.float64)
        columns = _differing_columns(before, after)
        if columns:
            actual_changed[name] = columns
        if not set(columns) <= allowed_columns[name]:
            raise VerificationError(f"forbidden memory column changed: {name}")
        if _memory_field_digest(name, pre_payload) != matching["pre"]["material"].get(name):
            raise VerificationError(f"pre-transplant actual array is not bound to matching: {name}")
        if _memory_field_digest(name, opening_payload) != matching["post"]["material"].get(name):
            raise VerificationError(f"opening actual array is not bound to matching: {name}")
    declared_changed = matching["delta"]["changed_fields"] if matching.get("delta") else {}
    if actual_changed != declared_changed:
        raise VerificationError("transplant delta does not match the actual arrays")
    if result["history_id"] == "native" and actual_changed:
        raise VerificationError("native budget-only arm changed memory arrays")
    for label, payload, recorded_memory in (
        ("pre", pre_payload, result["opening"]["memory_pre_transplant"]),
        ("opening", opening_payload, result["opening"]["memory"]),
    ):
        _compare_nested(
            payload["summary"],
            _recompute_memory_summary(payload, household_weight),
            f"memory.{label}.summary",
        )
        for key, value in _memory_metrics(payload, household_weight).items():
            recorded_key = "grievance_national" if key == "grievance_national_state" else key
            _compare_nested(
                recorded_memory[recorded_key],
                value,
                f"opening.memory{'_pre_transplant' if label == 'pre' else ''}.{key}",
            )
    trace = json.loads((arm_dir / "memory_trace.json").read_text(encoding="utf-8"))
    if result["history_id"] == "native":
        if matching.get("delta") is not None:
            raise VerificationError("native budget-only arm carries a transplant delta")
        if trace.get("transplant") != "none":
            raise VerificationError("native memory trace claims a transplant")
    else:
        if matching.get("delta") is None or not trace.get("final"):
            raise VerificationError("transplant evidence missing")
        final = trace["final"]
        expectation = np.asarray(opening_payload["expectation"], dtype=np.float64)
        streak = np.asarray(opening_payload["improvement_streak"], dtype=np.float64)
        reference = np.asarray(opening_payload["consumption_reference"], dtype=np.float64)
        if not np.array_equal(
            expectation[:, ENTITLEMENT_REAL_CONSUMPTION],
            np.asarray(final["expectation_real_consumption"], dtype=np.float64),
        ):
            raise VerificationError("opening expectation does not match the donor trace")
        if not np.array_equal(
            streak[:, ENTITLEMENT_REAL_CONSUMPTION],
            np.asarray(final["streak_real_consumption"], dtype=np.float64),
        ):
            raise VerificationError("opening streak does not match the donor trace")
        if not np.array_equal(
            reference, np.asarray(final["consumption_reference"], dtype=np.float64)
        ):
            raise VerificationError("opening consumption reference does not match the donor trace")
    for relative, payload in payloads.items():
        if not relative.startswith("memory/post-"):
            continue
        quarter = payload["quarter"]
        if quarter not in recomputed:
            raise VerificationError(f"memory payload quarter {quarter} has no table row")
        recomputed[quarter].update(_post_memory_metrics(payload, household_weight))

    recorded = result["tables"]["metrics_by_quarter"]
    if set(recomputed) != set(recorded):
        raise VerificationError("recorded metric quarters changed")
    for quarter, record in recorded.items():
        _compare_nested(record, recomputed[quarter], f"metrics.{quarter}")
    return {
        **result,
        "tables": {**result["tables"], "metrics_by_quarter": recomputed},
    }


def _verify_cross_arms(root: Path, study: dict[str, Any]) -> None:
    arms_dir = root / "arms"
    arm_dirs = sorted(path for path in arms_dir.iterdir() if path.is_dir())
    results = []
    for path in arm_dirs:
        if not (path / "result.json").is_file():
            raise VerificationError(f"arm has no result: {path.name}")
        results.append(_verify_arm(path))
    seeds = [int(seed) for seed in study["seeds"]]
    expected_matrix = {
        "expected_arms": len(seeds) * 26,
        "completed_arms": len(results),
        "tick_count": TICKS,
        "treatment_tick": TREATMENT_TICK,
        "treatment_quarter": TREATMENT_QUARTER,
        "histories": list(HISTORIES),
        "strengths": list(STRENGTHS),
        "cuts": list(CUTS),
        "native_cuts": list(NATIVE_CUTS),
    }
    if study["matrix"] != expected_matrix:
        raise VerificationError("study matrix changed")
    if len(results) != expected_matrix["expected_arms"]:
        raise VerificationError("completed arm count changed")
    if len({result["arm_id"] for result in results}) != len(results):
        raise VerificationError("duplicate arm ids")
    group_checks: dict[str, Any] = {}
    for seed in seeds:
        selected = [item for item in results if int(item["seed"]) == seed]
        if len(selected) != 26:
            raise VerificationError(f"seed {seed} does not have 26 arms")
        pre = {item["opening"]["matching_digest"] for item in selected}
        nonmemory = {item["opening"]["nonmemory_digest"] for item in selected}
        warmup = {
            json.loads(
                (root / "arms" / item["arm_id"] / "interventions.json").read_text(encoding="utf-8")
            )["warmup_sha256"]
            for item in selected
        }
        group_checks[str(seed)] = {
            "arms": len(selected),
            "pre_matching_digest_unique": sorted(pre),
            "pre_matching_equal": len(pre) == 1,
            "opening_nonmemory_equal": len(nonmemory) == 1,
            "warmup_interventions_equal": len(warmup) == 1,
            "budget_only_opening_memory_equals_transplant_pre": all(
                item["opening"]["matching_digest"] in pre for item in selected
            ),
        }
        if not (
            group_checks[str(seed)]["pre_matching_equal"]
            and group_checks[str(seed)]["opening_nonmemory_equal"]
            and group_checks[str(seed)]["warmup_interventions_equal"]
        ):
            raise VerificationError(f"seed {seed} is not a matched same-point group")
        for item in selected[1:]:
            assert_same_point(selected[0]["opening"], item["opening"])
    if canonical_digest(group_checks) != canonical_digest(study["group_checks"]):
        raise VerificationError("group matching evidence changed")
    stats = _compute_stats(results, seeds)
    if canonical_digest(stats) != canonical_digest(study["statistics"]):
        raise VerificationError("recomputed statistics do not match study.json")
    first_stage = _reference_first_stage(results)
    if canonical_digest(first_stage) != canonical_digest(study["reference_first_stage"]):
        raise VerificationError("reference first stage changed")
    cuts = _cut_first_stage(results)
    if canonical_digest(cuts) != canonical_digest(study["cut_first_stage"]):
        raise VerificationError("cut first stage changed")
    political_ok = all(
        item["tables"]["rows"]["opposition_regions"] > 0
        and item["tables"]["rows"]["information_quarters"] > 0
        and TREATMENT_QUARTER in item["tables"]["metrics_by_quarter"]
        for item in results
    )
    verdict = _verdict(stats, first_stage, cuts["levers"], political_ok)
    if canonical_digest(verdict) != canonical_digest(study["verdict"]):
        raise VerificationError("verdict changed")
    if study["historical_status"] != "UNIDENTIFIED":
        raise VerificationError("historical status was promoted")
    technical = (
        first_stage["status"] == "PASS"
        and cuts["status"] == "PASS"
        and not study["failures"]
        and all(check["pre_matching_equal"] for check in group_checks.values())
    )
    if study["technical_status"] != ("PASS" if technical else "BLOCKED"):
        raise VerificationError("technical status changed")


def _run_verify(output_dir: Path) -> dict[str, Any]:
    if not output_dir.is_dir():
        raise VerificationError(f"evidence directory does not exist: {output_dir}")
    manifest = _load_manifest(output_dir)
    _verify_files(output_dir, manifest)
    study = json.loads((output_dir / "study.json").read_text(encoding="utf-8"))
    _verify_cross_arms(output_dir, study)
    payload = {
        "status": "PASS",
        "output_dir": str(output_dir),
        "files_verified": len(manifest["files"]),
        "arms_verified": int(study["matrix"]["completed_arms"]),
        "technical_status": study["technical_status"],
        "reference_first_stage": study["reference_first_stage"]["status"],
        "historical_status": study["historical_status"],
    }
    return payload


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("reproduce", "profile", "study", "verify"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--c0-dir", type=Path, default=None)
    parser.add_argument("--root", type=Path, default=_REPO_ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.mode == "reproduce":
            payload = _run_reproduce(root, args.output_dir, args.c0_dir)
            print(json.dumps(_clean(payload), indent=2, sort_keys=True))
            return 0
        if args.mode == "profile":
            payload = _run_matrix(root, args.output_dir, (1729,))
            print(
                json.dumps(
                    _clean(
                        {
                            "status": payload["technical_status"],
                            "arms": payload["matrix"]["completed_arms"],
                            "reference_first_stage": payload["reference_first_stage"]["status"],
                            "failures": payload["failures"],
                        }
                    ),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0 if payload["technical_status"] == "PASS" else 2
        if args.mode == "study":
            payload = _run_matrix(root, args.output_dir, SEEDS)
            print(
                json.dumps(
                    _clean(
                        {
                            "status": payload["technical_status"],
                            "arms": payload["matrix"]["completed_arms"],
                            "reference_first_stage": payload["reference_first_stage"]["status"],
                            "verdict": payload["verdict"],
                            "failures": payload["failures"],
                        }
                    ),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0 if payload["technical_status"] == "PASS" else 2
        payload = _run_verify(args.output_dir)
        print(json.dumps(_clean(payload), indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI must report, not only traceback
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "mode": args.mode,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
