"""Declared, window-gated comparison of model output with admitted P05 targets."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.contract.schemas import ConfigError, TargetUse
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.material import run_material


def load_reproduction_crosswalk(root: Path) -> dict[str, Any]:
    """Load and validate the frozen crosswalk against the P05 target manifest."""
    control = json.loads((root / "config/calibration/p05.json").read_text())
    path = str(control.get("reproduction_crosswalk", ""))
    if not path:
        raise ConfigError("p05.json does not reference reproduction_crosswalk")
    crosswalk = json.loads((root / path).read_text())
    if crosswalk.get("schema_version") != "1":
        raise ConfigError("reproduction crosswalk schema_version must be '1'")
    manifest_path = str(crosswalk.get("source_manifest", ""))
    manifest = yaml.safe_load((root / manifest_path).read_text())
    target_ids = {str(row["variable_id"]) for row in manifest.get("targets", [])}
    entries = crosswalk.get("entries")
    if not isinstance(entries, list):
        raise ConfigError("crosswalk entries must be a list")
    entry_ids = [str(row.get("variable_id", "")) for row in entries]
    if len(entry_ids) != len(set(entry_ids)) or set(entry_ids) != target_ids:
        raise ConfigError(
            f"crosswalk must declare each admitted variable exactly once; "
            f"missing={sorted(target_ids - set(entry_ids))}, "
            f"extra={sorted(set(entry_ids) - target_ids)}"
        )
    allowed = {"mapped", "no_counterpart", "blocked"}
    supported_mappings = {"consumption"}
    for row in entries:
        status = row.get("status")
        if status not in allowed:
            raise ConfigError(f"{row['variable_id']}: invalid crosswalk status {status!r}")
        if status == "mapped":
            required = (
                "target_unit",
                "model_unit",
                "model_quantity",
                "comparison_rule",
                "annual_aggregation",
                "comparison_window",
                "error_tolerance",
                "precision_basis",
            )
            missing = [key for key in required if key not in row]
            if missing:
                raise ConfigError(f"{row['variable_id']}: mapped crosswalk lacks {missing}")
            if row["comparison_rule"] != "index_1960_100":
                raise ConfigError(
                    f"{row['variable_id']}: only index_1960_100 comparison is implemented"
                )
            if row["annual_aggregation"] != "mean":
                raise ConfigError(
                    f"{row['variable_id']}: model quantity supports only declared annual mean"
                )
            if set(row["comparison_window"]) - {"calibration", "internal_validation"}:
                raise ConfigError(f"{row['variable_id']}: hold-out/reserved window is prohibited")
            if row.get("variable_id") not in supported_mappings:
                raise ConfigError(
                    f"{row['variable_id']}: mapped model extractor is not implemented"
                )
            if float(row["error_tolerance"]) <= 0:
                raise ConfigError(f"{row['variable_id']}: tolerance must be positive")
        elif not str(row.get("reason", "")).strip():
            raise ConfigError(f"{row['variable_id']}: {status} requires a reason")
    return crosswalk


def annual_household_consumption_index(frame: pl.DataFrame) -> dict[int, float]:
    """Mean quarterly household-consumption totals, indexed to the model's own 1960."""
    annual = (
        frame.with_columns(pl.col("quarter").str.slice(0, 4).cast(pl.Int32).alias("year"))
        .group_by(["year", "quarter"])
        .agg(pl.col("household_consumption").sum().alias("quarter_total"))
        .group_by("year")
        .agg(pl.col("quarter_total").mean().alias("annual_mean"))
        .sort("year")
    )
    by_year = {int(row["year"]): float(row["annual_mean"]) for row in annual.to_dicts()}
    base = by_year.get(1960)
    if base is None or base == 0:
        raise ConfigError("model household consumption has no nonzero 1960 base")
    return {year: value / base * 100.0 for year, value in by_year.items()}


def run_reproduction_table(root: Path, output_dir: Path) -> dict[str, Any]:
    """Run one replay, read only mapped training/internal-validation targets, and compare."""
    root = Path(root)
    output_dir = Path(output_dir)
    if output_dir.exists() or output_dir.is_symlink():
        raise ConfigError(f"output directory already exists: {output_dir}")
    crosswalk = load_reproduction_crosswalk(root)
    spec = load_scenario(root, str(crosswalk["model_scenario"]))
    contract = load_research_contract(root)
    registry = DataRegistry.load(root, allowed_commodities=spec.commodities)
    output_dir.mkdir(parents=True)
    run_dir = output_dir / "replay"
    run_manifest = run_material(
        spec,
        run_dir,
        contract,
        registry,
        until=str(crosswalk["simulation_until"]),
        checkpoint_every=0,
    )
    model_index = annual_household_consumption_index(
        pl.read_parquet(run_dir / "national_accounts.parquet")
    )
    windows = crosswalk["comparison_windows"]
    entry = next(row for row in crosswalk["entries"] if row["variable_id"] == "consumption")
    rows: list[dict[str, Any]] = []
    years_allowed: set[int] = set()
    for window_name in entry["comparison_window"]:
        bounds = windows[window_name]
        years_allowed.update(range(int(bounds["start_year"]), int(bounds["end_year"]) + 1))
    for artifact in registry.artifacts.values():
        if artifact.variable_id != entry["variable_id"]:
            continue
        if artifact.use not in (TargetUse.CALIBRATION, TargetUse.VALIDATION):
            continue
        expected_use = artifact.use
        window_name = (
            "calibration"
            if expected_use is TargetUse.CALIBRATION
            else "internal_validation"
        )
        target = registry.load_targets(artifact, expected_use)
        for item in target.to_dicts():
            year = int(str(item["period"])[:4])
            if year not in years_allowed:
                raise ConfigError(
                    f"mapped target {artifact.artifact_id} includes undeclared year {year}"
                )
            if item["region_id"] is not None or item["commodity_id"] is not None:
                raise ConfigError(
                    f"mapped target {artifact.artifact_id} needs a declared dimension aggregation"
                )
            target_value = float(item["value"])
            model_value = model_index.get(year)
            if model_value is None:
                raise ConfigError(f"model has no annual value for target year {year}")
            residual = model_value - target_value
            tolerance = float(entry["error_tolerance"])
            rows.append(
                {
                    "variable_id": entry["variable_id"],
                    "window": window_name,
                    "year": year,
                    "target_value": target_value,
                    "model_value": model_value,
                    "residual": residual,
                    "absolute_residual": abs(residual),
                    "tolerance": tolerance,
                    "verdict": (
                        "within_tolerance" if abs(residual) <= tolerance else "outside_tolerance"
                    ),
                }
            )
    if not rows:
        raise ConfigError("mapped consumption crosswalk produced no target comparison rows")
    rows.sort(key=lambda row: (row["year"], row["window"]))
    mapped = sum(row["status"] == "mapped" for row in crosswalk["entries"])
    no_counterpart = sum(row["status"] == "no_counterpart" for row in crosswalk["entries"])
    blocked = sum(row["status"] == "blocked" for row in crosswalk["entries"])
    variable_summary = {
        "variable_id": "consumption",
        "comparison_count": len(rows),
        "within_tolerance_count": sum(row["verdict"] == "within_tolerance" for row in rows),
        "outside_tolerance_count": sum(row["verdict"] == "outside_tolerance" for row in rows),
        "mean_absolute_residual": sum(row["absolute_residual"] for row in rows) / len(rows),
        "max_absolute_residual": max(row["absolute_residual"] for row in rows),
        "overall_verdict": (
            "within_tolerance_all"
            if all(row["verdict"] == "within_tolerance" for row in rows)
            else "outside_tolerance"
        ),
        "interpretation": "descriptive reproduction comparison only; not calibration or validation",
    }
    payload = {
        "schema_version": 1,
        "status": "computed",
        "scope": crosswalk["scope"],
        "scenario_id": spec.scenario_id,
        "simulation_until": str(crosswalk["simulation_until"]),
        "run_dir": str(run_dir),
        "replay_digest": run_manifest.deterministic_replay_digest,
        "crosswalk_counts": {
            "mapped": mapped,
            "no_counterpart": no_counterpart,
            "blocked": blocked,
        },
        "variable_summaries": [variable_summary],
        "rows": rows,
        "excluded_variables_have_no_rows": True,
        "holdout_values_read": False,
        "reserved_values_read": False,
    }
    (output_dir / "reproduction_table.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    with (output_dir / "reproduction_table.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return payload
