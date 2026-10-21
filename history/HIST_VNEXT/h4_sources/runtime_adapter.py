"""H4A runtime connection: consume the approved experiment inputs in a real run.

This is the missing engine consumer for the H4A-1 declaration.  It:

* re-validates the declaration and approval through ``experiment_admission``;
* applies the approved persons/households and dwelling-ratio settings to a real
  ``historical_f2_replay`` scenario copy;
* runs a 4-quarter material arm for each setting;
* writes a runtime manifest with ``runtime_connected=true`` and
  ``consumed_by_model`` listing the three approved assumption records and the
  actual run ids;
* writes model-internal measurements only.  Historical comparison remains
  ``NOT_RUN``; no historical value is admitted or compared.

The adapter never edits the committed H4A-1 declaration/approval, never opens a
private value payload, and never writes engine state directly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from history.HIST_VNEXT.h4_sources.experiment_admission import (
    audit_experiment_admission,
    load_experiment_declaration,
)
from hsm_lab.contract.base import ConfigError
from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.material import run_material

SCHEMA_VERSION = "hist_vnext_h4a_runtime_v1"
DEFAULT_CLOCK = "2020-01-01T00:00:00Z"
BASE_SCENARIO_ID = "historical_f2_replay"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(root: Path, value: Path) -> Path:
    path = Path(value)
    resolved = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ConfigError(f"path escapes the repository: {value}")
    return resolved


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _apply_setting(
    spec: Any,
    *,
    by_region: dict[str, Any],
    dwelling_per_person: float,
    ticks: int = 4,
):
    household_update = []
    for county in spec.household_initial.counties:
        derived = by_region.get(county.county_id)
        if derived is None:
            raise ConfigError(f"derived quantities missing region {county.county_id!r}")
        household_update.append(
            county.model_copy(
                update={
                    "persons_total": float(derived["persons"]),
                    "household_total": float(derived["households"]),
                }
            )
        )
    household = spec.household_initial.model_copy(update={"counties": household_update})
    material = spec.material_initial.model_copy(
        update={"dwelling_per_person": float(dwelling_per_person)}
    )
    return spec.model_copy(
        update={
            "ticks": int(ticks),
            "household_initial": household,
            "material_initial": material,
        }
    )


def _measurement(run_dir: Path, *, setting_id: str, run_id: str) -> dict[str, Any]:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    by_commodity = summary["by_commodity"]
    households = pl.read_parquet(run_dir / "household_budgets.parquet")
    diagnostics = pl.read_parquet(run_dir / "tick_diagnostics.parquet")
    metrics = {
        "production_total": float(sum(v["production"] for v in by_commodity.values())),
        "household_consumption_total": float(
            sum(v["household_consumption"] for v in by_commodity.values())
        ),
        "imports_total": float(sum(v["imports"] for v in by_commodity.values())),
        "exports_total": float(sum(v["exports"] for v in by_commodity.values())),
        "availability_unmet_total": float(
            sum(v["availability_unmet"] for v in by_commodity.values())
        ),
        "final_stock_total": float(sum(v["final_stock"] for v in by_commodity.values())),
        "household_spending_total": float(households["spending"].sum()),
        "household_cash_close_total": float(households["cash_close"].sum()),
        "max_material_abs_residual": float(diagnostics["max_material_abs_residual"].max()),
        "max_finance_abs_residual": float(diagnostics["max_finance_abs_residual"].max()),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "role": "model_measurement",
        "setting_id": setting_id,
        "run_id": run_id,
        "metrics": metrics,
        "units": {
            "production_total": "model commodity units",
            "household_consumption_total": "model commodity units",
            "imports_total": "model commodity units",
            "exports_total": "model commodity units",
            "availability_unmet_total": "model commodity units",
            "final_stock_total": "model commodity units",
            "household_spending_total": "model cash units",
            "household_cash_close_total": "model cash units",
            "max_material_abs_residual": "model units",
            "max_finance_abs_residual": "model cash units",
        },
        "aggregation": "4-quarter sum except final stock (end) and residuals (max)",
        "historical_comparison": "NOT_RUN",
        "not_measured": [
            "any comparison with a historical value",
            "any historical welfare interpretation",
            "any parameter estimated from these measurements",
        ],
    }


def run_h4a_experiment(
    root: Path,
    *,
    config_path: Path,
    approval_path: Path,
    output_dir: Path,
    setting_ids: Sequence[str] | None = None,
    clock: str = DEFAULT_CLOCK,
) -> dict[str, Any]:
    root = Path(root).resolve()
    config_file = _resolve(root, Path(config_path))
    approval_file = _resolve(root, Path(approval_path))
    output_path = Path(output_dir)
    output_dir = (
        output_path.resolve()
        if output_path.is_absolute()
        else (root / output_path).resolve()
    )
    if output_dir.exists():
        raise ConfigError(f"output directory already exists: {output_dir}")

    declaration = load_experiment_declaration(root, config_file)
    audit = audit_experiment_admission(
        root,
        config_path=config_file,
        approval_path=approval_file,
        checked_at=datetime.now(UTC),
    )
    if audit.get("exit_code") != 0 or audit.get("admission") != "EXPERIMENT_ONLY":
        raise ConfigError(f"experiment admission is not approved: {audit.get('errors')}")
    derived = audit.get("derived_quantities")
    if not isinstance(derived, dict) or "by_region" not in derived:
        raise ConfigError("experiment admission produced no derived regional quantities")

    setting_values = {setting.setting_id: float(setting.value) for setting in declaration.settings}
    selected = tuple(setting_ids) if setting_ids is not None else tuple(setting_values)
    unknown = sorted(set(selected) - set(setting_values))
    if unknown:
        raise ConfigError(f"unknown setting ids: {unknown}")

    contract = load_research_contract(root)
    base = load_scenario(root, BASE_SCENARIO_ID)
    output_dir.mkdir(parents=True)
    runs: dict[str, Any] = {}
    consumed: list[dict[str, Any]] = []
    for setting_id in selected:
        spec = _apply_setting(
            base,
            by_region=derived["by_region"],
            dwelling_per_person=setting_values[setting_id],
        )
        spec.validate_for_run(contract)
        registry = DataRegistry.load(root, allowed_commodities=list(spec.commodities))
        run_dir = output_dir / setting_id
        manifest = run_material(
            spec,
            run_dir,
            contract,
            registry,
            deterministic_identity=True,
            fixed_clock=clock,
        )
        measurement = _measurement(run_dir, setting_id=setting_id, run_id=manifest.run_id)
        (run_dir / "measurement.json").write_text(
            json.dumps(measurement, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        run_ref = _display_path(run_dir, root)
        runs[setting_id] = {
            "run_id": manifest.run_id,
            "run_dir": run_ref,
            "status": manifest.status,
            "completed_ticks": manifest.completed_ticks,
            "deterministic_replay_digest": manifest.deterministic_replay_digest,
            "measurement": f"{run_ref}/measurement.json",
        }
        for record in declaration.records:
            consumed.append(
                {
                    "assumption_id": record.assumption_id,
                    "setting_id": setting_id,
                    "run_id": manifest.run_id,
                    "target_field": record.target_field,
                    "unit": record.unit,
                    "basis": record.basis,
                }
            )

    runtime = {
        "schema_version": SCHEMA_VERSION,
        "runtime_connected": True,
        "historical_inputs_admitted": int(audit.get("historical_inputs_admitted", 0)),
        "historical_status": "NOT_ESTABLISHED",
        "experiment_id": declaration.experiment_id,
        "target_initial_at": declaration.target_initial_at,
        "declaration": {
            "path": str(config_file.relative_to(root)),
            "sha256": _sha256_file(config_file),
        },
        "approval": {
            "path": str(approval_file.relative_to(root)),
            "sha256": _sha256_file(approval_file),
        },
        "consumed_by_model": consumed,
        "runs": runs,
        "initial_state_notice": (
            "The 1957 synthetic baseline scenario is copied and the approved experiment "
            "assumptions are applied; this is not a historical 1957 initial state."
        ),
        "measurement_notice": (
            "Measurements are model-internal and have no historical comparison; "
            "historical_status remains NOT_ESTABLISHED."
        ),
    }
    (output_dir / "runtime_manifest.json").write_text(
        json.dumps(runtime, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return runtime


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--config", required=True)
    parser.add_argument("--approval", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--setting", action="append", dest="settings")
    parser.add_argument("--clock", default=DEFAULT_CLOCK)
    args = parser.parse_args(argv)
    try:
        result = run_h4a_experiment(
            Path(args.root),
            config_path=Path(args.config),
            approval_path=Path(args.approval),
            output_dir=Path(args.output_dir),
            setting_ids=args.settings,
            clock=args.clock,
        )
    except (ConfigError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
