"""Shared fixtures: repo-root contract loading and synthetic registry factories.

All fixtures are small, explicitly synthetic, and live in tmp directories.
No test touches the network, real hold-out data, or the user's BASELINE.md.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import polars as pl
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

LONG_SCHEMA: dict[str, pl.DataType] = {
    "variable_id": pl.String,
    "period": pl.String,
    "region_id": pl.String,
    "commodity_id": pl.String,
    "value": pl.Float64,
    "unit": pl.String,
}


@pytest.fixture()
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture()
def contract(repo_root: Path):
    from hsm_lab.contract.guards import load_research_contract

    return load_research_contract(repo_root)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


VERIFIED_RIGHTS: dict[str, Any] = {
    "license_status": "verified",
    "license_name": "CC BY 4.0",
    "terms_locator": "https://example.org/terms",
    "evidence_quote": "may be copied, reproduced and redistributed",
    "checked_at": "2026-10-07T00:00:00Z",
    "download_allowed": True,
    "redistribution_allowed": True,
    "notes": "synthetic fixture rights block",
}

UNKNOWN_RIGHTS: dict[str, Any] = {
    "license_status": "unknown",
    "license_name": None,
    "terms_locator": None,
    "evidence_quote": None,
    "checked_at": None,
    "download_allowed": None,
    "redistribution_allowed": None,
    "notes": "synthetic fixture: rights unknown",
}


def source_spec(source_id: str = "src_fixture", rights: dict | None = None, **overrides) -> dict:
    spec: dict[str, Any] = {
        "source_id": source_id,
        "institution": "Fixture Institute",
        "dataset": "fixture-table",
        "locator": "https://example.org/fixture",
        "expected_format": ["XLSX"],
        "expected_roles": ["exogenous_forcing", "initial_state", "target", "latent_parameter"],
        "retrieval_method": "synthetic fixture generation",
        "access_status": "public_metadata",
        "audit_status": "metadata_checked",
        "rights": rights if rights is not None else VERIFIED_RIGHTS,
        "coverage_notes": "synthetic fixture coverage",
        "notes": "",
    }
    spec.update(overrides)
    return spec


def variable_spec(variable_id: str, semantic_kind: str, allowed_role: str, **overrides) -> dict:
    spec: dict[str, Any] = {
        "variable_id": variable_id,
        "semantic_kind": semantic_kind,
        "allowed_roles": [allowed_role],
        "unit": "fixture-unit",
        "original_frequency": "annual",
        "aggregation": None,
        "notes": f"synthetic fixture variable {variable_id}",
    }
    spec.update(overrides)
    return spec


def provenance(
    *,
    variable: str,
    role: str,
    evidence_status: str,
    source_id: str = "src_fixture",
    original_frequency: str = "annual",
    model_frequency: str | None = None,
    method: str = "identity",
    aggregation: str | None = None,
    artifact_sha256: str | None = None,
    raw_sha256: str | None = None,
    raw_path: str | None = None,
    derived_from: list[str] | None = None,
    locator: str = "https://example.org/fixture",
    rights: dict | None = None,
) -> dict:
    return {
        "variable": variable,
        "role": role,
        "source_institution": "Fixture Institute",
        "dataset": "fixture-table",
        "locator": locator,
        "retrieved_at": "2026-10-07T00:00:00Z",
        "raw_sha256": raw_sha256,
        "original_frequency": original_frequency,
        "model_frequency": model_frequency or original_frequency,
        "transformation": {
            "method": method,
            "source_frequency": original_frequency,
            "result_frequency": model_frequency or original_frequency,
            "aggregation": aggregation,
            "description": "synthetic fixture transformation",
        },
        "evidence_status": evidence_status,
        "rights": rights if rights is not None else VERIFIED_RIGHTS,
        "notes": "synthetic fixture provenance",
        "source_id": source_id,
        "source_period": None,
        "raw_path": raw_path,
        "derived_from": derived_from or [],
        "artifact_sha256": artifact_sha256,
    }


def make_registry(
    root: Path,
    *,
    sources: list[dict],
    variables: list[dict],
    artifacts: list[dict],
    allowed_commodities: list[str] | None = None,
) -> Any:
    """Materialize a complete fixture registry under ``root`` and load it."""
    (root / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy(
        REPO_ROOT / "config" / "research_contract.json",
        root / "config" / "research_contract.json",
    )
    (root / "data" / "manifests").mkdir(parents=True, exist_ok=True)
    (root / "fixtures").mkdir(parents=True, exist_ok=True)
    (root / "data" / "manifests" / "sources.yml").write_text(
        yaml.safe_dump({"schema_version": "1", "sources": sources}, sort_keys=False),
        encoding="utf-8",
    )
    (root / "data" / "manifests" / "variables.yml").write_text(
        yaml.safe_dump({"schema_version": "1", "variables": variables}, sort_keys=False),
        encoding="utf-8",
    )
    (root / "data" / "manifests" / "artifacts.yml").write_text(
        yaml.safe_dump({"schema_version": "1", "artifacts": artifacts}, sort_keys=False),
        encoding="utf-8",
    )
    from hsm_lab.data.registry import DataRegistry

    return DataRegistry.load(
        root,
        extra_roots=(root / "fixtures",),
        allowed_commodities=allowed_commodities,
    )


def write_long_parquet(path: Path, rows: list[dict[str, Any]]) -> str:
    """Write a synthetic long-form table; return its real SHA-256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(rows, schema=LONG_SCHEMA)
    frame.write_parquet(path)
    return sha256_file(path)


def base_rows(
    periods: list[str], values: list[float], variable_id: str = "gdp", unit: str = "fixture-unit"
) -> list[dict[str, Any]]:
    return [
        {
            "variable_id": variable_id,
            "period": period,
            "region_id": None,
            "commodity_id": None,
            "value": value,
            "unit": unit,
        }
        for period, value in zip(periods, values, strict=True)
    ]


def smoke_spec(contract, **overrides):
    """The canonical smoke scenario, with overrides applied."""
    from hsm_lab.contract.guards import load_scenario
    from hsm_lab.contract.schemas import OutputPolicy

    spec = load_scenario(REPO_ROOT, "smoke")
    if "output_policy" in overrides:
        overrides = {**overrides, "output_policy": OutputPolicy(overrides["output_policy"])}
    if contract.region_ids != spec.region_ids:
        spec = spec.model_copy(update={"region_ids": contract.region_ids})
    if overrides:
        spec = spec.model_copy(update=overrides)
    return spec


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
