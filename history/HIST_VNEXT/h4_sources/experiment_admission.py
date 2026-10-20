"""
H4A-1 — source-less synthetic experiment initial-state admission.

This domain is deliberately isolated from the statistical H4A-0 evaluator.  It
admits a declared *experiment assumption*, not a historical observation:

* the base scenario is the existing grade-S synthetic recipe;
* persons/households are inherited from that recipe, not re-estimated;
* the dwelling ratio is an explicit three-setting experiment design;
* an independent review plus a hash-bound approval are required before the
  declaration becomes ``EXPERIMENT_ONLY``;
* historical inputs admitted remain zero and ``runtime_connected`` stays false.

The module is offline.  It never reads a private value payload, never writes the
engine state, and never changes the base scenario.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from hsm_lab.contract.base import ConfigError, Sha256Hex, StrictModel
from hsm_lab.contract.schemas import DataRole, ScenarioSpec
from hsm_lab.provenance.manifest import canonical_json

SCHEMA_VERSION = "hist_vnext_h4a1_experiment_v1"
EXPERIMENT_ID = "h4exp_synthetic_dwelling_sensitivity_v1"
TARGET_INITIAL_AT = "1957-01-01"
TRANSFORMATION_VERSION = "inherit-synthetic-recipe-and-dwelling-ratio-v1"
BASE_SCENARIO_PATH = "config/scenarios/historical_f2_replay.json"
UPSTREAM_APPROVED_PATH = "docs/phases/HIST_VNEXT/H4A-0/APPROVED_INPUT_SET.json"
LEDGER_PATH = "docs/phases/HIST_VNEXT/H4A-1/ASSUMPTION_LEDGER.md"

RECORD_IDS = (
    "h4exp_inherited_persons",
    "h4exp_inherited_households",
    "h4exp_dwelling_ratio",
)
RECORD_SPECS = {
    "h4exp_inherited_persons": (
        "household_initial.counties[].persons_total",
        "persons",
        "inherited_baseline_synthetic",
    ),
    "h4exp_inherited_households": (
        "household_initial.counties[].household_total",
        "households",
        "inherited_baseline_synthetic",
    ),
    "h4exp_dwelling_ratio": (
        "material_initial.dwelling_per_person",
        "dwellings/person",
        "explicit_experiment_design",
    ),
}
SETTINGS = (
    ("low", 0.3),
    ("baseline", 0.4),
    ("high", 0.5),
)
REQUIRED_REVIEW_FILES = (
    "history/HIST_VNEXT/h4_sources/experiment_admission.py",
    "config/initial_state/hist_vnext_h4_v1/experiment_inputs.json",
    "tests/test_hist_experiment_initial_admission.py",
    "docs/phases/HIST_VNEXT/H4A-1/ASSUMPTION_LEDGER.md",
    "config/scenarios/historical_f2_replay.json",
    "docs/phases/HIST_VNEXT/H4A-0/APPROVED_INPUT_SET.json",
    "docs/phases/HIST_VNEXT/H4A-1/H1A_REREVIEW_ROUND14.md",
)
assert DataRole.INITIAL_STATE.value == "initial_state"


# ---------------------------------------------------------------------------
# Declaration models
# ---------------------------------------------------------------------------


class BaseScenarioBinding(StrictModel):
    path: str = Field(min_length=1)
    sha256: Sha256Hex
    household_recipe_sha256: Sha256Hex
    material_recipe_sha256: Sha256Hex

    @field_validator("path")
    @classmethod
    def _path_is_relative(cls, value: str) -> str:
        _require_repo_relative(value)
        return value


class UpstreamBinding(StrictModel):
    path: str = Field(min_length=1)
    sha256: Sha256Hex

    @field_validator("path")
    @classmethod
    def _path_is_relative(cls, value: str) -> str:
        _require_repo_relative(value)
        return value


class ExperimentRecord(StrictModel):
    assumption_id: str = Field(min_length=1)
    target_field: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    basis: str = Field(min_length=1)
    ledger_ref: str = Field(min_length=1)
    historical_support: Literal["none"]

    @model_validator(mode="after")
    def _closed_record(self) -> ExperimentRecord:
        expected = RECORD_SPECS.get(self.assumption_id)
        if expected is None:
            raise ConfigError(f"unknown experiment assumption_id {self.assumption_id!r}")
        target_field, unit, basis = expected
        if (self.target_field, self.unit, self.basis) != expected:
            raise ConfigError(
                f"{self.assumption_id}: expected target/unit/basis "
                f"{(target_field, unit, basis)!r}"
            )
        if self.ledger_ref != self.assumption_id:
            raise ConfigError(
                f"{self.assumption_id}: ledger_ref must equal the assumption_id"
            )
        return self


class Setting(StrictModel):
    setting_id: str = Field(min_length=1)
    value: float = Field(ge=0.0, allow_inf_nan=False)


class ExperimentDeclaration(StrictModel):
    schema_version: Literal[SCHEMA_VERSION]
    experiment_id: Literal[EXPERIMENT_ID]
    classification: Literal["synthetic"]
    evidence_kind: Literal["experiment_assumption"]
    data_role: Literal["initial_state"]
    purpose: Literal["initial_state"]
    target_initial_at: Literal[TARGET_INITIAL_AT]
    historical_status: Literal["NOT_ESTABLISHED"]
    runtime_connected: Literal[False]
    declared_by: str = Field(min_length=1)
    base_scenario: BaseScenarioBinding
    upstream_approved_input_set: UpstreamBinding
    records: list[ExperimentRecord] = Field(min_length=3, max_length=3)
    settings: list[Setting] = Field(min_length=3, max_length=3)
    transformation_version: Literal[TRANSFORMATION_VERSION]
    ledger_path: str = Field(min_length=1)
    ledger_sha256: Sha256Hex

    @field_validator("declared_by", "ledger_path")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ConfigError("declared_by/ledger_path must not be blank")
        return value

    @field_validator("ledger_path")
    @classmethod
    def _ledger_path_is_relative(cls, value: str) -> str:
        _require_repo_relative(value)
        return value

    @model_validator(mode="after")
    def _closed_declaration(self) -> ExperimentDeclaration:
        if tuple(record.assumption_id for record in self.records) != RECORD_IDS:
            raise ConfigError(f"records must be exactly {RECORD_IDS!r} in order")
        if self.base_scenario.path != BASE_SCENARIO_PATH:
            raise ConfigError(f"base_scenario.path must be {BASE_SCENARIO_PATH!r}")
        if self.upstream_approved_input_set.path != UPSTREAM_APPROVED_PATH:
            raise ConfigError(
                f"upstream_approved_input_set.path must be {UPSTREAM_APPROVED_PATH!r}"
            )
        if self.ledger_path != LEDGER_PATH:
            raise ConfigError(f"ledger_path must be {LEDGER_PATH!r}")
        expected_settings = [(name, value) for name, value in SETTINGS]
        actual_settings = [(setting.setting_id, setting.value) for setting in self.settings]
        if actual_settings != expected_settings:
            raise ConfigError(f"settings must be exactly {expected_settings!r}")
        return self


# ---------------------------------------------------------------------------
# Review / approval models
# ---------------------------------------------------------------------------


class ReviewBinding(StrictModel):
    path: str = Field(min_length=1)
    sha256: Sha256Hex

    @field_validator("path")
    @classmethod
    def _path_is_relative(cls, value: str) -> str:
        _require_repo_relative(value)
        return value


class ReviewRecord(StrictModel):
    schema_version: Literal[SCHEMA_VERSION]
    verdict: Literal["PASS", "PATCH", "REDESIGN"]
    reviewer_identity: str = Field(min_length=1)
    reviewer_role: Literal["@review"]
    reviewed_at: datetime
    reviewed_sha256: dict[str, Sha256Hex]
    approved_assumption_ids: list[str]
    purpose: Literal["initial_state"]
    target_initial_at: Literal[TARGET_INITIAL_AT]
    expires_at: datetime | None

    @field_validator("reviewed_at", "expires_at")
    @classmethod
    def _utc_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _require_utc(value)

    @model_validator(mode="after")
    def _review_scope(self) -> ReviewRecord:
        _require_exact_files(self.reviewed_sha256)
        if tuple(self.approved_assumption_ids) != RECORD_IDS:
            raise ConfigError(f"review must approve exactly {RECORD_IDS!r}")
        return self


class ApprovalRecord(StrictModel):
    schema_version: Literal[SCHEMA_VERSION]
    review: ReviewBinding
    reviewed_sha256: dict[str, Sha256Hex]
    approved_assumption_ids: list[str]
    purpose: Literal["initial_state"]
    target_initial_at: Literal[TARGET_INITIAL_AT]
    expires_at: datetime | None
    issued_by: str = Field(min_length=1)
    issued_at: datetime
    runtime_connected: Literal[False]

    @field_validator("issued_at", "expires_at")
    @classmethod
    def _utc_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _require_utc(value)

    @model_validator(mode="after")
    def _approval_scope(self) -> ApprovalRecord:
        _require_exact_files(self.reviewed_sha256)
        if tuple(self.approved_assumption_ids) != RECORD_IDS:
            raise ConfigError(f"approval must approve exactly {RECORD_IDS!r}")
        return self


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_experiment_declaration(root: Path, config_path: Path) -> ExperimentDeclaration:
    """Load and fully validate the declared experiment design and its bindings."""
    root = Path(root).resolve()
    config_file = _resolve(root, config_path)
    try:
        raw = _load_json(config_file, "experiment_inputs.json")
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot load experiment declaration: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("experiment declaration must be an object")
    declaration = ExperimentDeclaration.model_validate(raw)
    _validate_bindings(root, declaration)
    return declaration


def audit_experiment_admission(
    root: Path,
    *,
    config_path: Path,
    approval_path: Path | None,
    checked_at: datetime,
) -> dict[str, Any]:
    """Audit the declaration and optional independent approval."""
    checked_at = _require_utc(checked_at)
    root = Path(root).resolve()
    try:
        declaration = load_experiment_declaration(root, config_path)
    except (ConfigError, ValidationError, OSError) as exc:
        return _result(
            exit_code=2,
            structural="BLOCKED",
            admission="BLOCKED",
            derived_quantities=None,
            errors=[f"declaration: {exc}"],
        )

    derived = _derived_quantities(root, declaration)
    if derived is None:
        return _result(
            exit_code=2,
            structural="BLOCKED",
            admission="BLOCKED",
            derived_quantities=None,
            errors=["cannot derive region quantities"],
        )

    if approval_path is None:
        return _result(
            exit_code=1,
            structural="PASS",
            admission="PENDING",
            derived_quantities=derived,
            errors=["no independent approval supplied"],
        )

    try:
        approval_file = _resolve(root, approval_path)
        approval = ApprovalRecord.model_validate(
            _load_json(approval_file, "EXPERIMENT_INPUT_APPROVAL.json")
        )
    except (ConfigError, ValidationError, OSError, json.JSONDecodeError, ValueError) as exc:
        return _result(
            exit_code=2,
            structural="BLOCKED",
            admission="BLOCKED",
            derived_quantities=derived,
            errors=[f"approval: {exc}"],
        )

    try:
        review_file = _resolve(root, approval.review.path)
        review_bytes = review_file.read_bytes()
        review = ReviewRecord.model_validate(
            json.loads(review_bytes.decode("utf-8"))
        )
    except (ConfigError, ValidationError, OSError, json.JSONDecodeError, ValueError) as exc:
        return _result(
            exit_code=2,
            structural="BLOCKED",
            admission="BLOCKED",
            derived_quantities=derived,
            errors=[f"review: {exc}"],
        )

    if _sha256_bytes(review_bytes) != approval.review.sha256:
        return _result(
            exit_code=2,
            structural="BLOCKED",
            admission="BLOCKED",
            derived_quantities=derived,
            errors=["review file hash does not match approval.review.sha256"],
        )

    scope_error = _check_review_scope(root, declaration, review, approval, checked_at)
    if scope_error is not None:
        code, message = scope_error
        return _result(
            exit_code=code,
            structural="PASS" if code == 1 else "BLOCKED",
            admission="BLOCKED" if code == 1 else "BLOCKED",
            derived_quantities=derived,
            errors=[message],
        )

    approved_inputs = [record.model_dump(mode="json") for record in declaration.records]
    return _result(
        exit_code=0,
        structural="PASS",
        admission="EXPERIMENT_ONLY",
        derived_quantities=derived,
        errors=[],
        approved_inputs=approved_inputs,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument(
        "--config",
        default="config/initial_state/hist_vnext_h4_v1/experiment_inputs.json",
    )
    parser.add_argument("--approval", default=None)
    args = parser.parse_args(argv)
    result = audit_experiment_admission(
        Path(args.root),
        config_path=Path(args.config),
        approval_path=Path(args.approval) if args.approval else None,
        checked_at=datetime.now(UTC),
    )
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return int(result["exit_code"])


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_repo_relative(value: str) -> None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigError(f"path must be repository-relative and must not escape: {value!r}")


def _resolve(root: Path, value: Path) -> Path:
    path = Path(value)
    resolved = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not resolved.is_relative_to(root):
        raise ConfigError(f"path escapes repository root: {value}")
    return resolved


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ConfigError("datetime must be timezone-aware UTC")
    return value


def _require_exact_files(files: dict[str, str]) -> None:
    if set(files) != set(REQUIRED_REVIEW_FILES):
        raise ConfigError(
            "reviewed_sha256 must contain exactly the seven prerequisite files"
        )


def _load_json(path: Path, label: str) -> Any:
    with open(path) as handle:
        return json.load(handle)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_sha256(value: Any) -> str:
    return _sha256_bytes(canonical_json(value))


def _validate_bindings(root: Path, declaration: ExperimentDeclaration) -> None:
    base_path = _resolve(root, Path(declaration.base_scenario.path))
    base_bytes = base_path.read_bytes()
    if _sha256_bytes(base_bytes) != declaration.base_scenario.sha256:
        raise ConfigError("base scenario SHA256 does not match declaration")
    raw = json.loads(base_bytes.decode("utf-8"))
    if not isinstance(raw, dict):
        raise ConfigError("base scenario must be an object")
    _reject_bool_recipe_values(raw)
    spec = ScenarioSpec.model_validate(raw)
    if spec.household_initial is None or spec.material_initial is None:
        raise ConfigError("base scenario lacks household_initial/material_initial")
    if (
        spec.household_initial.grade != "S"
        or spec.household_initial.evidence_status != "structural_assumption"
        or spec.household_initial.population_kind != "synthetic"
    ):
        raise ConfigError("household_initial must be grade S / structural_assumption / synthetic")
    if (
        spec.material_initial.grade != "S"
        or spec.material_initial.evidence_status != "structural_assumption"
    ):
        raise ConfigError("material_initial must be grade S / structural_assumption")
    if declaration.base_scenario.household_recipe_sha256 != _canonical_sha256(
        spec.household_initial.model_dump(mode="json")
    ):
        raise ConfigError("household recipe SHA256 does not match declaration")
    if declaration.base_scenario.material_recipe_sha256 != _canonical_sha256(
        spec.material_initial.model_dump(mode="json")
    ):
        raise ConfigError("material recipe SHA256 does not match declaration")

    upstream_path = _resolve(root, Path(declaration.upstream_approved_input_set.path))
    upstream_bytes = upstream_path.read_bytes()
    if _sha256_bytes(upstream_bytes) != declaration.upstream_approved_input_set.sha256:
        raise ConfigError("upstream approved-input set SHA256 does not match declaration")
    upstream = json.loads(upstream_bytes.decode("utf-8"))
    if not isinstance(upstream, dict):
        raise ConfigError("upstream approved-input set must be an object")
    for key in ("initial_state_inputs", "measurement_inputs", "assumption_inputs"):
        if upstream.get(key) != []:
            raise ConfigError(f"upstream {key} must remain empty for this experiment")

    ledger_path = _resolve(root, Path(declaration.ledger_path))
    ledger_bytes = ledger_path.read_bytes()
    if not ledger_bytes:
        raise ConfigError("assumption ledger is empty")
    if _sha256_bytes(ledger_bytes) != declaration.ledger_sha256:
        raise ConfigError("assumption ledger SHA256 does not match declaration")

    counties = spec.household_initial.counties
    region_ids = list(spec.region_ids)
    county_ids = [county.county_id for county in counties]
    if set(county_ids) != set(region_ids) or len(county_ids) != len(region_ids):
        raise ConfigError("household counties must match model regions one-to-one")
    if spec.material_initial.dwelling_per_person != SETTINGS[1][1]:
        raise ConfigError("baseline setting must equal material_initial.dwelling_per_person")


def _reject_bool_recipe_values(raw: dict[str, Any]) -> None:
    household = raw.get("household_initial")
    material = raw.get("material_initial")
    if not isinstance(household, dict) or not isinstance(material, dict):
        raise ConfigError("base scenario lacks household_initial/material_initial objects")
    counties = household.get("counties")
    if not isinstance(counties, list) or not counties:
        raise ConfigError("household_initial.counties must be a non-empty list")
    for index, county in enumerate(counties):
        if not isinstance(county, dict):
            raise ConfigError(f"household_initial.counties[{index}] must be an object")
        for field in ("persons_total", "household_total"):
            value = county.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ConfigError(f"county {index} {field} must be a number, not {type(value)}")
    dwelling = material.get("dwelling_per_person")
    if isinstance(dwelling, bool) or not isinstance(dwelling, (int, float)):
        raise ConfigError("material_initial.dwelling_per_person must be a number")


def _derived_quantities(
    root: Path, declaration: ExperimentDeclaration
) -> dict[str, Any] | None:
    base_path = _resolve(root, Path(declaration.base_scenario.path))
    spec = ScenarioSpec.model_validate(json.loads(base_path.read_text()))
    if spec.household_initial is None or spec.material_initial is None:
        return None
    ratios = {setting.setting_id: float(setting.value) for setting in declaration.settings}
    by_region: dict[str, dict[str, Any]] = {}
    persons_values: list[float] = []
    household_values: list[float] = []
    dwelling_values: dict[str, list[float]] = {name: [] for name in ratios}
    for county in spec.household_initial.counties:
        persons = float(county.persons_total)
        households = float(county.household_total)
        if not math.isfinite(persons) or not math.isfinite(households):
            return None
        if persons <= 0.0 or households <= 0.0 or persons < households:
            return None
        persons_values.append(persons)
        household_values.append(households)
        dwellings: dict[str, float] = {}
        for name, ratio in ratios.items():
            value = ratio * persons
            if not math.isfinite(value):
                return None
            dwellings[name] = value
            dwelling_values[name].append(value)
        by_region[county.county_id] = {
            "persons": persons,
            "households": households,
            "dwellings": dwellings,
        }
    if not persons_values:
        return None
    national = {
        "persons": math.fsum(persons_values),
        "households": math.fsum(household_values),
        "dwellings": {
            name: math.fsum(values) for name, values in dwelling_values.items()
        },
    }
    return {
        "units": {
            "persons": "persons",
            "households": "households",
            "dwellings": "dwellings",
        },
        "by_region": by_region,
        "national": national,
    }


def _check_review_scope(
    root: Path,
    declaration: ExperimentDeclaration,
    review: ReviewRecord,
    approval: ApprovalRecord,
    checked_at: datetime,
) -> tuple[int, str] | None:
    if review.verdict != "PASS":
        return (1, f"independent review verdict is {review.verdict}, not PASS")
    if review.reviewer_identity == declaration.declared_by:
        return (2, "declared_by and reviewer_identity must differ")
    if approval.issued_by != review.reviewer_identity:
        return (2, "approval issued_by does not match reviewer_identity")
    if approval.issued_at != review.reviewed_at:
        return (2, "approval issued_at does not match reviewed_at")
    if approval.reviewed_sha256 != review.reviewed_sha256:
        return (2, "approval reviewed_sha256 does not match review")
    if approval.approved_assumption_ids != review.approved_assumption_ids:
        return (2, "approval assumption scope does not match review")
    if approval.purpose != review.purpose or approval.target_initial_at != review.target_initial_at:
        return (2, "approval purpose/target does not match review")
    if approval.expires_at != review.expires_at:
        return (2, "approval expiry does not match review")

    for relative, expected in review.reviewed_sha256.items():
        path = _resolve(root, Path(relative))
        if _sha256_file(path) != expected:
            return (2, f"stale or forged reviewed file hash: {relative}")

    if approval.issued_at > checked_at:
        return (2, "approval is issued in the future")
    if approval.expires_at is not None and checked_at >= approval.expires_at:
        return (1, "approval has expired")
    return None


def _result(
    *,
    exit_code: int,
    structural: str,
    admission: str,
    derived_quantities: dict[str, Any] | None,
    errors: list[str],
    approved_inputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "exit_code": exit_code,
        "structural": structural,
        "admission": admission,
        "historical": "NOT_ESTABLISHED",
        "runtime_connected": False,
        "historical_inputs_admitted": 0,
        "approved_inputs": approved_inputs or [],
        "derived_quantities": derived_quantities,
        "errors": errors,
    }


if __name__ == "__main__":
    raise SystemExit(main())
