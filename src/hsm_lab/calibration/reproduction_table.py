"""Declared, window-gated comparison of model output with admitted P05 targets."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from hsm_lab.contract.guards import load_research_contract, load_scenario, sha256_file
from hsm_lab.contract.schemas import ConfigError, TargetUse
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.material import run_material
from hsm_lab.engine.state import build_material_prices


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
    target_rows = manifest.get("targets", [])
    target_ids = {str(row["variable_id"]) for row in target_rows}
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
    supported_mappings = {
        "consumption",
        "trade_export_volume_index",
        "trade_import_volume_index",
    }
    valid_grades = {
        "mapped_like_for_like",
        "normalized_index",
        "allocation_assumed",
        "no_counterpart",
        "blocked",
    }
    for row in entries:
        status = row.get("status")
        grade = row.get("comparison_grade")
        if grade not in valid_grades:
            raise ConfigError(
                f"{row['variable_id']}: invalid or missing comparison_grade {grade!r}"
            )
        mapped_grades = valid_grades - {"no_counterpart", "blocked"}
        if grade != status and not (status == "mapped" and grade in mapped_grades):
            raise ConfigError(
                f"{row['variable_id']}: comparison_grade {grade!r} conflicts with {status!r}"
            )
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
            source = row.get("source")
            if not isinstance(source, dict) or not source:
                raise ConfigError(f"{row['variable_id']}: mapped crosswalk lacks declared source")
            source_type = source.get("type")
            if source_type not in {
                "admitted_target_artifacts",
                "scenario_declared_trade_vectors",
            }:
                raise ConfigError(f"{row['variable_id']}: unsupported mapped source type")
            if source_type == "scenario_declared_trade_vectors":
                trade_variables = {
                    "trade_export_volume_index",
                    "trade_import_volume_index",
                }
                if row["variable_id"] not in trade_variables:
                    raise ConfigError(
                        f"{row['variable_id']}: scenario-declared trade source is only "
                        "supported for the two admitted trade indices"
                    )
                scenario_id = str(source.get("scenario_id", ""))
                scenario_path = root / "config" / "scenarios" / f"{scenario_id}.json"
                if scenario_id != str(crosswalk.get("model_scenario", "")):
                    raise ConfigError(
                        f"{row['variable_id']}: trade source scenario must match model_scenario"
                    )
                if not scenario_path.is_file() or sha256_file(scenario_path) != str(
                    source.get("scenario_sha256", "")
                ):
                    raise ConfigError(
                        f"{row['variable_id']}: declared trade scenario digest is missing or stale"
                    )
                if not str(source.get("non_circularity_note", "")).strip():
                    raise ConfigError(
                        f"{row['variable_id']}: trade source lacks a non-circularity note"
                    )
            declared_artifacts = source.get("artifacts")
            if not isinstance(declared_artifacts, list) or not declared_artifacts:
                raise ConfigError(f"{row['variable_id']}: mapped source must list frozen artifacts")
            use_for_window = {
                "calibration": "calibration",
                "internal_validation": "validation",
            }
            expected_uses = {use_for_window[name] for name in row["comparison_window"]}
            expected_sources = {
                (str(item["artifact_id"]), str(item["sha256"]))
                for item in target_rows
                if item.get("variable_id") == row["variable_id"]
                and item.get("role") == "target"
                and item.get("use") in expected_uses
            }
            listed_sources = {
                (str(item.get("artifact_id", "")), str(item.get("sha256", "")))
                for item in declared_artifacts
                if isinstance(item, dict)
            }
            if listed_sources != expected_sources:
                raise ConfigError(
                    f"{row['variable_id']}: declared source artifacts do not match "
                    "its admitted comparison targets"
                )
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


def annual_price_weighted_trade_values(
    frame: pl.DataFrame, commodities: list[str], standard_prices: list[float]
) -> dict[int, dict[str, float]]:
    """Annual means of broad trade quantities valued at frozen admin prices."""
    if len(commodities) != len(standard_prices):
        raise ConfigError("declared price vector does not align with the scenario commodity axis")
    price_by_commodity = dict(zip(commodities, map(float, standard_prices), strict=True))
    required = {
        "quarter",
        "commodity_id",
        "exports",
        "imports",
        "cmea_exports",
        "convertible_exports",
        "cmea_imports",
        "convertible_imports",
    }
    if not required.issubset(frame.columns):
        raise ConfigError(
            f"national_accounts lacks trade columns {sorted(required - set(frame.columns))}"
        )
    quarter_totals: dict[str, dict[str, float]] = {}
    for item in frame.select(sorted(required)).to_dicts():
        commodity = str(item["commodity_id"])
        if commodity not in price_by_commodity:
            raise ConfigError(f"national_accounts contains undeclared commodity {commodity!r}")
        price = price_by_commodity[commodity]
        totals = quarter_totals.setdefault(str(item["quarter"]), {})
        for column in required - {"quarter", "commodity_id"}:
            totals[column] = totals.get(column, 0.0) + float(item[column]) * price
    annual: dict[int, dict[str, float]] = {}
    for quarter, totals in quarter_totals.items():
        year = int(quarter[:4])
        yearly = annual.setdefault(year, {})
        for key, value in totals.items():
            yearly[key] = yearly.get(key, 0.0) + value / 4.0
    return annual


def annual_price_weighted_trade_indices(
    frame: pl.DataFrame, commodities: list[str], standard_prices: list[float]
) -> dict[str, dict[int, dict[str, float]]]:
    """Normalize admin-price trade totals to 1960=100 with channel diagnostics.

    Channel contributions use the same total-trade 1960 denominator. They are
    diagnostics, not target series.
    """
    annual = annual_price_weighted_trade_values(frame, commodities, standard_prices)
    output: dict[str, dict[int, dict[str, float]]] = {}
    for direction, channels in {
        "exports": ("cmea_exports", "convertible_exports"),
        "imports": ("cmea_imports", "convertible_imports"),
    }.items():
        base = annual.get(1960, {}).get(direction, 0.0)
        if base == 0.0:
            raise ConfigError(f"model {direction} has no nonzero 1960 base")
        output[direction] = {
            year: {
                "total_index": totals[direction] / base * 100.0,
                "cmea_channel_index": totals[channels[0]] / base * 100.0,
                "convertible_channel_index": totals[channels[1]] / base * 100.0,
            }
            for year, totals in annual.items()
        }
    return output


def index_year_is_informative(year: int, base_year: int = 1960) -> bool:
    """The normalization base is exact by construction and carries no fit information."""
    return int(year) != int(base_year)


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
    accounts = pl.read_parquet(run_dir / "national_accounts.parquet")
    consumption_index = annual_household_consumption_index(accounts)
    if spec.material_parameters is None:
        raise ConfigError("historical material scenario has no declared material parameters")
    standard_prices = build_material_prices(spec.material_parameters).standard.tolist()
    trade_values = annual_price_weighted_trade_values(
        accounts, list(spec.commodities), standard_prices
    )
    mapped_ids = {
        str(entry["variable_id"])
        for entry in crosswalk["entries"]
        if entry["status"] == "mapped"
    }
    trade_indices: dict[str, dict[int, dict[str, float]]] = {"exports": {}, "imports": {}}
    if mapped_ids & {"trade_export_volume_index", "trade_import_volume_index"}:
        trade_indices = annual_price_weighted_trade_indices(
            accounts, list(spec.commodities), standard_prices
        )
    model_series: dict[str, dict[int, dict[str, float]]] = {
        "consumption": {
            year: {"total_index": value} for year, value in consumption_index.items()
        },
        "trade_export_volume_index": trade_indices["exports"],
        "trade_import_volume_index": trade_indices["imports"],
    }
    windows = crosswalk["comparison_windows"]
    rows: list[dict[str, Any]] = []
    variable_summaries = []
    allowed_windows = {
        "calibration": TargetUse.CALIBRATION,
        "internal_validation": TargetUse.VALIDATION,
    }
    for entry in crosswalk["entries"]:
        if entry["status"] != "mapped":
            continue
        variable_id = str(entry["variable_id"])
        if variable_id not in model_series:
            raise ConfigError(f"{variable_id}: mapped model series is not implemented")
        years_allowed: set[int] = set()
        for window_name in entry["comparison_window"]:
            bounds = windows[window_name]
            years_allowed.update(range(int(bounds["start_year"]), int(bounds["end_year"]) + 1))
        variable_rows: list[dict[str, Any]] = []
        for artifact in registry.artifacts.values():
            if artifact.variable_id != variable_id or artifact.use not in allowed_windows.values():
                continue
            window_name = next(
                name for name, use in allowed_windows.items() if use is artifact.use
            )
            if window_name not in entry["comparison_window"]:
                continue
            target = registry.load_targets(artifact, artifact.use)
            for item in target.to_dicts():
                year = int(str(item["period"])[:4])
                if year not in years_allowed:
                    raise ConfigError(
                        f"mapped target {artifact.artifact_id} includes undeclared year {year}"
                    )
                if item["region_id"] is not None or item["commodity_id"] is not None:
                    raise ConfigError(
                        f"mapped target {artifact.artifact_id} needs a declared "
                        "dimension aggregation"
                    )
                model_row = model_series[variable_id].get(year)
                if model_row is None:
                    raise ConfigError(f"model has no annual value for {variable_id} in {year}")
                target_value = float(item["value"])
                model_value = model_row["total_index"]
                residual = model_value - target_value
                tolerance = float(entry["error_tolerance"])
                row = {
                    "variable_id": variable_id,
                    "comparison_grade": entry["comparison_grade"],
                    "window": window_name,
                    "year": year,
                    "informative": index_year_is_informative(year),
                    "target_value": target_value,
                    "model_value": model_value,
                    "residual": residual,
                    "absolute_residual": abs(residual),
                    "tolerance": tolerance,
                    "verdict": (
                        "within_tolerance" if abs(residual) <= tolerance else "outside_tolerance"
                    ),
                    "diagnostic_cmea_exports_admin_price_value": trade_values[year]["cmea_exports"],
                    "diagnostic_convertible_exports_admin_price_value": trade_values[year][
                        "convertible_exports"
                    ],
                    "diagnostic_cmea_imports_admin_price_value": trade_values[year]["cmea_imports"],
                    "diagnostic_convertible_imports_admin_price_value": trade_values[year][
                        "convertible_imports"
                    ],
                }
                variable_rows.append(row)
                rows.append(row)
        if not variable_rows:
            raise ConfigError(f"mapped crosswalk {variable_id} produced no target comparison rows")
        informative_rows = [row for row in variable_rows if row["informative"]]
        outside_informative = sum(
            row["verdict"] == "outside_tolerance" for row in informative_rows
        )
        variable_summaries.append(
            {
                "variable_id": variable_id,
                "comparison_grade": entry["comparison_grade"],
                "comparison_count": len(variable_rows),
                "informative_year_count": len(informative_rows),
                "within_tolerance_count": sum(
                    row["verdict"] == "within_tolerance" for row in variable_rows
                ),
                "outside_tolerance_count": sum(
                    row["verdict"] == "outside_tolerance" for row in variable_rows
                ),
                "informative_outside_tolerance_count": outside_informative,
                "informative_outside_tolerance_statement": (
                    f"{outside_informative} of {len(informative_rows)} informative "
                    "years outside tolerance"
                ),
                "mean_absolute_residual": sum(row["absolute_residual"] for row in variable_rows)
                / len(variable_rows),
                "max_absolute_residual": max(row["absolute_residual"] for row in variable_rows),
                "overall_verdict": (
                    "within_tolerance_all"
                    if all(row["verdict"] == "within_tolerance" for row in informative_rows)
                    else "outside_tolerance"
                ),
                "interpretation": (
                    "descriptive reproduction comparison only; "
                    "not calibration or validation"
                ),
            }
        )
    if not rows:
        raise ConfigError("mapped consumption crosswalk produced no target comparison rows")
    rows.sort(key=lambda row: (row["year"], row["window"]))
    mapped = sum(row["status"] == "mapped" for row in crosswalk["entries"])
    no_counterpart = sum(row["status"] == "no_counterpart" for row in crosswalk["entries"])
    blocked = sum(row["status"] == "blocked" for row in crosswalk["entries"])
    by_grade = {
        grade: sum(row["comparison_grade"] == grade for row in crosswalk["entries"])
        for grade in (
            "mapped_like_for_like", "normalized_index", "allocation_assumed",
            "no_counterpart", "blocked",
        )
    }
    rows.sort(key=lambda row: (row["variable_id"], row["year"], row["window"]))
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
        "by_grade": by_grade,
        "variable_summaries": variable_summaries,
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
