"""Material forcing packs, synthetic fixtures and the isolated target interface.

Responsibilities (MATERIAL_ECONOMY_EXPANSION_PLAN.md section 6):

1. ``build_synthetic_material_fixtures`` - deterministic local fixtures (no
   RNG, no wall clock): monthly/quarterly synthetic oil + USD-rate long
   tables, three structural latent priors and the synthetic forcing pack.
   Everything is byte-reproducible; conflicting existing content is refused
   instead of overwritten.
2. ``build_external_material_pack`` - compose the external forcing pack from
   *admitted* ingestion artifacts (World Bank oil + Federal Reserve rate
   mandatory, MNB official FX optional).  Derives the quarterly forcing
   tables and the five-year-rule CMEA reconstructed artifact, registers them
   through the normal manifest admission, and writes the pack JSON with
   artifact bindings, digests and the reconstruction-parameter hash.
3. ``load_material_forcing`` - the only way a material run consumes external
   data: pack + artifact digests re-verified, role gates enforced, window
   coverage exact (no gaps/overlaps), scenario bindings checked as subsets.
4. ``load_material_targets``/``compare_annual`` - the isolated TARGET
   interface; targets never enter the runtime as forcing and reserved-window
   access fails closed.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import polars as pl
import yaml

from hsm_lab.contract.guards import load_research_contract, load_scenario, sha256_file
from hsm_lab.contract.material import MATERIAL_FORCING_VARIABLE_IDS
from hsm_lab.contract.schemas import (
    ConfigError,
    DataRole,
    EvidenceStatus,
    Frequency,
    Quarter,
    ResearchGateError,
    ScenarioSpec,
    TargetUse,
)
from hsm_lab.data.frequency import (
    Aggregation,
    dated_to_quarterly,
    monthly_to_quarterly,
    quarterly_to_annual,
)
from hsm_lab.data.ingestion import (
    IngestionReport,
    IngestionRequest,
    _append_artifact_manifest,
)
from hsm_lab.data.registry import DataRegistry
from hsm_lab.data.schemas import (
    Bounds,
    ForcingArtifact,
    ParameterArtifact,
    ParameterPriorFile,
    PeriodRange,
    Provenance,
    RightsSpec,
    TargetArtifact,
    Transformation,
)
from hsm_lab.engine.state import MaterialForcing
from hsm_lab.provenance.manifest import canonical_digest

__all__ = [
    "MATERIAL_EXTERNAL_PACK_PATH",
    "MATERIAL_SYNTHETIC_PACK_PATH",
    "TargetDataset",
    "build_external_material_pack",
    "build_synthetic_material_fixtures",
    "compare_annual",
    "load_material_forcing",
    "load_material_targets",
]


MATERIAL_SYNTHETIC_PACK_PATH = "data/fixtures/p02_material_synthetic_pack.json"
MATERIAL_EXTERNAL_PACK_PATH = "data/observed/p02_material_external_pack.json"

FIXTURE_SOURCE_ID = "p02_material_fixture"
FIXTURE_LOCATOR = "fixture:p02-material"
FIXTURE_DATASET = "P02 material synthetic forcing fixtures and structural priors"
# Stable constant (never the wall clock): packs and fixtures must be
# byte-reproducible, so every timestamp field derives from this anchor.
FIXTURE_GENERATED_AT = "2026-10-07T00:00:00Z"
_FIXTURE_GENERATED_AT_DT = datetime.fromisoformat("2026-10-07T00:00:00+00:00")

SYNTHETIC_WARNING = "material_synthetic_fixture_not_historical_fit"
EXTERNAL_WARNING = "material_external_pack_requires_admitted_artifacts"

SYNTHETIC_MONTHLY_WINDOW = ("1957-01", "1985-12")
SYNTHETIC_QUARTERLY_WINDOW = ("1957Q1", "1985Q4")
SYNTHETIC_OIL_VALUE = 1.63  # USD_per_barrel, matches world_oil_reference
SYNTHETIC_RATE_VALUE = 4.0  # percent_per_year

WARMUP_WINDOW = ("1957Q1", "1959Q4")
CMEA_WINDOW = ("1975Q1", "1985Q4")
CMEA_RULE_VERSION = "cmea-five-year-contract-v1"
_QUARTER_LABEL_RE = re.compile(r"\d{4}Q[1-4]")

_LONG_COLUMNS = ("variable_id", "period", "region_id", "commodity_id", "value", "unit")


# ----------------------------------------------------------------------
# Small deterministic helpers
# ----------------------------------------------------------------------


def _month_range(start: str, end: str) -> list[str]:
    year, month = int(start[:4]), int(start[5:7])
    last = (int(end[:4]), int(end[5:7]))
    out: list[str] = []
    while (year, month) <= last:
        out.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return out


def _quarter_range(start: str, end: str) -> list[str]:
    first = Quarter.parse(start)
    last = Quarter.parse(end)
    if first.to_ordinal() > last.to_ordinal():
        raise ConfigError(f"inverted quarter range {start}..{end}")
    return [str(first.advance(k)) for k in range(last.to_ordinal() - first.to_ordinal() + 1)]


def _long_frame(
    variable_id: str, periods: list[str], values: list[float], unit: str
) -> pl.DataFrame:
    frame = pl.DataFrame(
        {
            "variable_id": pl.Series([variable_id] * len(periods), dtype=pl.String),
            "period": pl.Series(periods, dtype=pl.String),
            "region_id": pl.Series([None] * len(periods), dtype=pl.String),
            "commodity_id": pl.Series([None] * len(periods), dtype=pl.String),
            "value": pl.Series(values, dtype=pl.Float64),
            "unit": pl.Series([unit] * len(periods), dtype=pl.String),
        }
    )
    return frame.sort("period")


def _canonical_long(frame: pl.DataFrame) -> pl.DataFrame:
    """Reorder/validate a derived frame into the canonical 6-column table."""
    if frame.columns != list(_LONG_COLUMNS):
        frame = frame.select(
            [
                pl.col("variable_id"),
                pl.col("period"),
                pl.col("region_id"),
                pl.col("commodity_id"),
                pl.col("value"),
                pl.col("unit"),
            ]
        )
    return frame.sort("period")


def _parquet_bytes(frame: pl.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.write_parquet(buffer)
    return buffer.getvalue()


def _json_bytes(payload: Any) -> bytes:
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return text.encode("utf-8")


def _stage_bytes(path: Path, data: bytes) -> tuple[str, bool]:
    """Write immutable content; return (sha256, reused_existing).

    An existing file with identical content is reused byte-for-byte; a
    different content at the same path is a conflicting drift and fails
    closed.  Nothing is ever silently overwritten.
    """
    digest = hashlib.sha256(data).hexdigest()
    if path.is_file():
        existing = sha256_file(path)
        if existing == digest:
            return digest, True
        raise ResearchGateError(
            f"{path}: existing file content (sha256 {existing}) differs from the "
            f"deterministic generated content (sha256 {digest}); generated data "
            "files are immutable - investigate the drift instead of overwriting"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return digest, False


def _fixture_rights() -> RightsSpec:
    return RightsSpec(
        license_status="verified",
        license_name="Locally generated synthetic fixture (no third-party rights)",
        terms_locator=FIXTURE_LOCATOR,
        evidence_quote="generated locally by this repository; contains no third-party data",
        checked_at=_FIXTURE_GENERATED_AT_DT,
        download_allowed=True,
        redistribution_allowed=True,
        notes="synthetic fixture rights block; no external dataset involved",
    )


_FIXTURE_SOURCE_ENTRY: dict[str, Any] = {
    "source_id": FIXTURE_SOURCE_ID,
    "institution": "HSM Lab local fixture",
    "dataset": FIXTURE_DATASET,
    "locator": FIXTURE_LOCATOR,
    "expected_format": ["PARQUET", "JSON"],
    "expected_roles": ["exogenous_forcing", "latent_parameter", "initial_state"],
    "retrieval_method": "local deterministic generation inside this repository",
    "access_status": "public_metadata",
    "audit_status": "metadata_checked",
    "rights": _fixture_rights().model_dump(mode="json"),
    "coverage_notes": (
        "Deterministic synthetic monthly/quarterly forcing 1957-01..1985-12 and "
        "structural latent priors; locally generated, no historical observations."
    ),
    "notes": (
        "Local synthetic/prior/grade-S recipe source mirroring the P01 fixture "
        "rights mode; real sources never inherit these rights."
    ),
}

# Latent parameter variables required by the three structural priors.  The
# ingestion wave did not declare them; the builder appends them idempotently
# (documented deviation - without them the priors cannot be admitted).
_LATENT_VARIABLE_ENTRIES: list[dict[str, Any]] = [
    {
        "variable_id": "oil_warmup_price",
        "semantic_kind": "latent",
        "allowed_roles": ["latent_parameter"],
        "unit": "USD_per_barrel",
        "original_frequency": "static",
        "aggregation": None,
        "notes": (
            "Structural warm-up oil price for 1957Q1-1959Q4 (no observed World "
            "Bank oil before 1960-01; observations are never backfilled). "
            "Selected value 1.6 with engineering bounds [1, 3]; not calibrated."
        ),
    },
    {
        "variable_id": "cmea_base_energy_price",
        "semantic_kind": "latent",
        "allowed_roles": ["latent_parameter"],
        "unit": "cmea_settlement_unit_per_p02_energy_unit",
        "original_frequency": "static",
        "aggregation": None,
        "notes": (
            "Early CMEA base contract price prior covering 1957-1974, before the "
            "five-year reconstruction window starts 1975Q1. Bounds [0.5, 1.5]; "
            "not a calibrated estimate."
        ),
    },
    {
        "variable_id": "cmea_uncertainty_multiplier",
        "semantic_kind": "latent",
        "allowed_roles": ["latent_parameter"],
        "unit": "ratio",
        "original_frequency": "static",
        "aggregation": None,
        "notes": (
            "Multiplier scaling the five-year-rule CMEA contract price "
            "reconstruction; selected value 1.0 with engineering bounds "
            "[0.5, 1.5]; not calibrated."
        ),
    },
]

# Structural prior declarations (registry declaration + on-disk JSON file
# must agree field-by-field; DataRegistry.validate_parameter enforces it).
_PRIOR_DECLARATIONS: list[dict[str, Any]] = [
    {
        "artifact_id": "p02_material_oil_warmup_prior",
        "variable_id": "oil_warmup_price",
        "file": "p02_material_oil_warmup_prior.json",
        "literature_refs": [
            "structural assumption: fixed warm-up oil price for pre-1960 window"
        ],
        "prior_description": (
            "Fixed nominal USD oil price used as the explicit structural warm-up "
            "forcing for 1957Q1-1959Q4; the World Bank monthly series starts "
            "1960-01 and observed values are never backfilled into the warm-up."
        ),
        "bounds": {"lower": 1.0, "upper": 3.0},
        "uncertainty_notes": (
            "Engineering prior range only; no calibration and no sensitivity "
            "assessment were performed, and the selected value is not a "
            "historical estimate."
        ),
    },
    {
        "artifact_id": "p02_material_cmea_contract_prior",
        "variable_id": "cmea_base_energy_price",
        "file": "p02_material_cmea_contract_prior.json",
        "literature_refs": [
            "structural assumption: constant early CMEA base contract price "
            "before the five-year reconstruction window"
        ],
        "prior_description": (
            "Constant base CMEA energy contract price for 1957-1974; the "
            "reconstructed cmea_energy_price series only starts 1975Q1 where "
            "five complete prior years of World Bank oil exist."
        ),
        "bounds": {"lower": 0.5, "upper": 1.5},
        "uncertainty_notes": (
            "Engineering prior range only; no calibration and no sensitivity "
            "assessment were performed, and the selected value is not a "
            "historical estimate."
        ),
    },
    {
        "artifact_id": "p02_material_cmea_uncertainty_prior",
        "variable_id": "cmea_uncertainty_multiplier",
        "file": "p02_material_cmea_uncertainty_prior.json",
        "literature_refs": [
            "structural assumption: neutral CMEA reconstruction multiplier"
        ],
        "prior_description": (
            "Unit multiplier scaling the five-year-rule CMEA contract price "
            "reconstruction; the selected value 1.0 leaves the base price and "
            "the world-oil ratio unchanged."
        ),
        "bounds": {"lower": 0.5, "upper": 1.5},
        "uncertainty_notes": (
            "Engineering prior range only; no calibration and no sensitivity "
            "assessment were performed, and the selected value is not a "
            "historical estimate."
        ),
    },
]


def _ensure_manifest_entries(
    root: Path, filename: str, list_key: str, id_field: str, entries: list[dict[str, Any]]
) -> None:
    """Append missing manifest entries idempotently; never touch present ones."""
    path = root / "data" / "manifests" / filename
    if not path.is_file():
        raise ResearchGateError(f"data manifest not found: {path}")
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema_version") != "1":
        raise ConfigError(f"{path}: expected top-level schema_version '1'")
    current = doc.get(list_key)
    if not isinstance(current, list):
        raise ConfigError(f"{path}: expected a top-level '{list_key}' list")
    known = {item.get(id_field) for item in current if isinstance(item, dict)}
    changed = False
    for entry in entries:
        if entry[id_field] in known:
            continue
        current.append(deepcopy(entry))
        known.add(entry[id_field])
        changed = True
    if changed:
        payload = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)


# ----------------------------------------------------------------------
# 1. Synthetic fixtures
# ----------------------------------------------------------------------


def build_synthetic_material_fixtures(root: Path) -> IngestionReport:
    """Generate/register the deterministic synthetic material fixtures.

    Idempotent: identical reruns reuse the same files (same bytes, same
    sha256, same artifact ids); conflicting content at any target path is a
    ``ResearchGateError``.  The generated pack is byte-reproducible - every
    timestamp field uses the stable ``FIXTURE_GENERATED_AT`` anchor.
    """
    root = Path(root)

    # Manifest prerequisites: the fixture source and the three latent
    # variables (appended idempotently; existing entries are never rewritten).
    _ensure_manifest_entries(
        root, "sources.yml", "sources", "source_id", [_FIXTURE_SOURCE_ENTRY]
    )
    _ensure_manifest_entries(
        root, "variables.yml", "variables", "variable_id", _LATENT_VARIABLE_ENTRIES
    )

    registry = DataRegistry.load(root)
    source = registry.sources[FIXTURE_SOURCE_ID]
    rights = _fixture_rights()

    files: list[tuple[str, str]] = []  # (rel path, sha256)
    reused_flags: list[bool] = []

    def stage(rel: str, data: bytes) -> str:
        digest, reused = _stage_bytes(root / rel, data)
        files.append((rel, digest))
        reused_flags.append(reused)
        return digest

    # --- monthly / quarterly forcing tables -----------------------------
    oil_periods = _month_range(*SYNTHETIC_MONTHLY_WINDOW)
    rate_periods = _month_range(*SYNTHETIC_MONTHLY_WINDOW)
    oil_monthly = _long_frame(
        "world_oil_price", oil_periods, [SYNTHETIC_OIL_VALUE] * len(oil_periods), "USD_per_barrel"
    )
    rate_monthly = _long_frame(
        "global_usd_rate",
        rate_periods,
        [SYNTHETIC_RATE_VALUE] * len(rate_periods),
        "percent_per_year",
    )
    oil_quarterly = _canonical_long(monthly_to_quarterly(oil_monthly, "mean"))
    rate_quarterly = _canonical_long(monthly_to_quarterly(rate_monthly, "mean"))
    for frame, name in (
        (oil_monthly, "p02_material_world_oil_monthly.parquet"),
        (oil_quarterly, "p02_material_world_oil_quarterly.parquet"),
        (rate_monthly, "p02_material_global_usd_rate_monthly.parquet"),
        (rate_quarterly, "p02_material_global_usd_rate_quarterly.parquet"),
    ):
        stage(f"data/fixtures/{name}", _parquet_bytes(frame))

    forcing_specs: list[ForcingArtifact] = []
    for variable_id, stem, monthly in (
        ("world_oil_price", "p02_material_world_oil", True),
        ("global_usd_rate", "p02_material_global_usd_rate", True),
        ("world_oil_price", "p02_material_world_oil", False),
        ("global_usd_rate", "p02_material_global_usd_rate", False),
    ):
        rel = f"data/fixtures/{stem}_{'monthly' if monthly else 'quarterly'}.parquet"
        digest = dict(files)[rel]
        if monthly:
            transformation = Transformation(
                method="synthetic_generation",
                source_frequency=Frequency.MONTHLY,
                result_frequency=Frequency.MONTHLY,
                aggregation=None,
                description=(
                    "Local deterministic synthetic fixture generation; constant "
                    "value, no historical observations"
                ),
            )
            original = Frequency.MONTHLY
            period = PeriodRange(
                start=SYNTHETIC_MONTHLY_WINDOW[0],
                end=SYNTHETIC_MONTHLY_WINDOW[1],
                frequency=Frequency.MONTHLY,
            )
        else:
            transformation = Transformation(
                method="monthly_to_quarterly",
                source_frequency=Frequency.MONTHLY,
                result_frequency=Frequency.QUARTERLY,
                aggregation="mean",
                description=(
                    "Mean of the three synthetic monthly values per quarter "
                    "(complete-month rule; local fixture, no observations)"
                ),
            )
            original = Frequency.MONTHLY
            period = PeriodRange(
                start=SYNTHETIC_QUARTERLY_WINDOW[0],
                end=SYNTHETIC_QUARTERLY_WINDOW[1],
                frequency=Frequency.QUARTERLY,
            )
        provenance = Provenance(
            variable=variable_id,
            role=DataRole.EXOGENOUS_FORCING,
            source_institution=source.institution,
            dataset=source.dataset,
            locator=source.locator,
            retrieved_at=_FIXTURE_GENERATED_AT_DT,
            raw_sha256=digest,
            original_frequency=original,
            model_frequency=transformation.result_frequency,
            transformation=transformation,
            evidence_status=EvidenceStatus.SYNTHETIC_FIXTURE,
            rights=rights,
            notes=(
                "Deterministic synthetic material forcing; "
                "material_synthetic_fixture_not_historical_fit."
            ),
            source_id=FIXTURE_SOURCE_ID,
            source_period=None,
            raw_path=None,
            derived_from=[],
            artifact_sha256=digest,
        )
        forcing_specs.append(
            ForcingArtifact(
                artifact_id=stem + ("_monthly" if monthly else "_quarterly"),
                variable_id=variable_id,
                path=rel,
                provenance=provenance,
                source_id=FIXTURE_SOURCE_ID,
                period=period,
            )
        )

    # --- structural latent priors ---------------------------------------
    prior_specs: list[ParameterArtifact] = []
    for decl in _PRIOR_DECLARATIONS:
        rel = f"data/fixtures/{decl['file']}"
        prior_payload = {
            "schema_version": "1",
            "variable_id": decl["variable_id"],
            "literature_refs": list(decl["literature_refs"]),
            "prior_description": decl["prior_description"],
            "bounds": dict(decl["bounds"]),
            "calibration_status": "not_calibrated",
            "sensitivity_status": "not_assessed",
            "uncertainty_notes": decl["uncertainty_notes"],
        }
        ParameterPriorFile.model_validate(prior_payload)  # fail fast on shape
        digest = stage(rel, _json_bytes(prior_payload))
        provenance = Provenance(
            variable=decl["variable_id"],
            role=DataRole.LATENT_PARAMETER,
            source_institution=source.institution,
            dataset=source.dataset,
            locator=source.locator,
            retrieved_at=_FIXTURE_GENERATED_AT_DT,
            raw_sha256=digest,
            original_frequency=Frequency.STATIC,
            model_frequency=Frequency.STATIC,
            transformation=Transformation(
                method="literature_prior",
                source_frequency=Frequency.STATIC,
                result_frequency=Frequency.STATIC,
                aggregation=None,
                description=(
                    "Structural assumption prior declared locally; never an "
                    "observed or calibrated value"
                ),
            ),
            evidence_status=EvidenceStatus.STRUCTURAL_ASSUMPTION,
            rights=rights,
            notes=(
                "Structural latent parameter prior (not_calibrated/not_assessed); "
                "validated through DataRegistry.validate_parameter."
            ),
            source_id=FIXTURE_SOURCE_ID,
            source_period=None,
            raw_path=None,
            derived_from=[],
            artifact_sha256=digest,
        )
        prior_specs.append(
            ParameterArtifact(
                artifact_id=decl["artifact_id"],
                variable_id=decl["variable_id"],
                path=rel,
                provenance=provenance,
                source_id=FIXTURE_SOURCE_ID,
                literature_refs=list(decl["literature_refs"]),
                prior_description=decl["prior_description"],
                bounds=Bounds(**decl["bounds"]),
                calibration_status="not_calibrated",
                sensitivity_status="not_assessed",
                uncertainty_notes=decl["uncertainty_notes"],
            )
        )

    # --- register artifacts exactly like ingestion does ------------------
    all_specs: list[ForcingArtifact | ParameterArtifact] = [*forcing_specs, *prior_specs]
    _append_artifact_manifest(root, all_specs)

    # --- synthetic pack manifest -----------------------------------------
    def segment_spec(spec: ForcingArtifact) -> dict[str, Any]:
        return {
            "variable_id": spec.variable_id,
            "artifact_id": spec.artifact_id,
            "path": spec.path,
            "sha256": spec.provenance.artifact_sha256,
            "period": {
                "start": spec.period.start,
                "end": spec.period.end,
                "frequency": spec.period.frequency.value,
            },
            "evidence": "synthetic_fixture",
        }

    segments = {
        "world_oil_price": segment_spec(
            next(
                s
                for s in forcing_specs
                if s.variable_id == "world_oil_price"
                and s.period.frequency is Frequency.QUARTERLY
            )
        ),
        "global_usd_rate": segment_spec(
            next(
                s
                for s in forcing_specs
                if s.variable_id == "global_usd_rate"
                and s.period.frequency is Frequency.QUARTERLY
            )
        ),
    }
    pack: dict[str, Any] = {
        "schema_version": "1",
        "profile": "synthetic",
        "source_id": FIXTURE_SOURCE_ID,
        "locator": FIXTURE_LOCATOR,
        "warning": SYNTHETIC_WARNING,
        "generated_at": FIXTURE_GENERATED_AT,
        "period": {
            "start": SYNTHETIC_QUARTERLY_WINDOW[0],
            "end": SYNTHETIC_QUARTERLY_WINDOW[1],
            "frequency": "quarterly",
        },
        "segments": segments,
        "reconstruction_params": None,
        "reconstruction_params_hash": None,
        "binding_hash": canonical_digest({"profile": "synthetic", "segments": segments}),
    }
    pack_sha = stage(MATERIAL_SYNTHETIC_PACK_PATH, _json_bytes(pack))

    # --- read-back validation through the real registry gates ------------
    reloaded = DataRegistry.load(root)
    for spec in forcing_specs:
        admitted = reloaded.artifacts.get(spec.artifact_id)
        if admitted is None:
            raise ResearchGateError(
                f"fixture artifact {spec.artifact_id} missing from reloaded registry"
            )
        reloaded.load_forcing(cast(ForcingArtifact, admitted))
    for prior_spec in prior_specs:
        admitted_prior = reloaded.artifacts.get(prior_spec.artifact_id)
        if admitted_prior is None:
            raise ResearchGateError(
                f"prior artifact {prior_spec.artifact_id} missing from reloaded registry"
            )
        reloaded.validate_parameter(cast(ParameterArtifact, admitted_prior))

    return IngestionReport(
        source_id=FIXTURE_SOURCE_ID,
        request=IngestionRequest(
            source_id=FIXTURE_SOURCE_ID,
            start=SYNTHETIC_MONTHLY_WINDOW[0],
            end=SYNTHETIC_MONTHLY_WINDOW[1],
        ),
        request_hash=canonical_digest(
            {"builder": "build_synthetic_material_fixtures", "profile": "synthetic"}
        ),
        cache_hit=all(reused_flags),
        downloaded=False,
        raw_sha256=pack_sha,
        raw_path=root / MATERIAL_SYNTHETIC_PACK_PATH,
        retrieval_url=FIXTURE_LOCATOR,
        retrieved_at=_FIXTURE_GENERATED_AT_DT,
        response_metadata={
            "generator": "hsm_lab.data.material.build_synthetic_material_fixtures",
            "profile": "synthetic",
            "warning": SYNTHETIC_WARNING,
            "binding_hash": pack["binding_hash"],
            "files": [{"path": rel, "sha256": digest} for rel, digest in files],
        },
        variable_ids=(
            "world_oil_price",
            "global_usd_rate",
            "oil_warmup_price",
            "cmea_base_energy_price",
            "cmea_uncertainty_multiplier",
        ),
        artifact_ids=tuple(spec.artifact_id for spec in all_specs),
        artifact_paths=tuple(spec.path for spec in all_specs),
        artifacts=tuple(spec.model_dump(mode="json") for spec in all_specs),
    )


# ----------------------------------------------------------------------
# 2. External pack builder
# ----------------------------------------------------------------------


def _report_artifacts(report: object, source_id: str) -> list[dict[str, Any]]:
    artifacts = getattr(report, "artifacts", None)
    if artifacts is None and isinstance(report, dict):
        artifacts = report.get("artifacts")
    if not artifacts:
        raise ResearchGateError(
            f"ingestion report for source {source_id} carries no artifact records"
        )
    return [dict(item) for item in artifacts]


def _require_report(source_reports: dict[str, object], source_id: str) -> object:
    report = source_reports.get(source_id)
    if report is None:
        raise ResearchGateError(
            f"external material pack requires admitted {source_id} artifacts; "
            f"run 'hsm data ingest --source {source_id}' first (missing source: "
            f"{source_id})"
        )
    return report


def _admitted_artifact_id(
    artifacts: list[dict[str, Any]],
    variable_id: str,
    source_id: str,
    frequency: str,
) -> str:
    hits = [
        item
        for item in artifacts
        if item.get("variable_id") == variable_id
        and item.get("role") == DataRole.EXOGENOUS_FORCING.value
        and (item.get("period") or {}).get("frequency") == frequency
    ]
    if len(hits) != 1:
        raise ResearchGateError(
            f"expected exactly one admitted {frequency} exogenous_forcing artifact for "
            f"{variable_id} from source {source_id}, found {len(hits)}"
        )
    return str(hits[0]["artifact_id"])


def _load_admitted_forcing(
    registry: DataRegistry, artifact_id: str, source_id: str
) -> tuple[ForcingArtifact, pl.DataFrame]:
    artifact = registry.artifacts.get(artifact_id)
    if artifact is None:
        raise ResearchGateError(
            f"artifact {artifact_id} (source {source_id}) is not registered in "
            "data/manifests/artifacts.yml; ingest the source before building the pack"
        )
    if not isinstance(artifact, ForcingArtifact):
        raise ResearchGateError(
            f"artifact {artifact_id} has role {artifact.role.value}; the external "
            "pack consumes exogenous_forcing artifacts only"
        )
    return artifact, registry.load_forcing(artifact)


def _external_reconstruction_params(root: Path) -> dict[str, float]:
    """Selected CMEA reconstruction values from the external scenario config.

    The pinned builder signature carries no parameter arguments, so the
    selected values are read from ``config/scenarios/intermediate8_external.json``
    (the only declared consumer of the external pack).
    """
    spec = load_scenario(root, "intermediate8_external")
    if spec.material_parameters is None:  # pragma: no cover - config validates this
        raise ResearchGateError("external scenario lacks material_parameters")
    params = spec.material_parameters
    return {
        "cmea_base_energy_price": float(params.cmea_base_energy_price),
        "cmea_uncertainty_multiplier": float(params.cmea_uncertainty_multiplier),
        "world_oil_reference": float(params.world_oil_reference),
    }


def _derive_quarterly(
    parent: ForcingArtifact, frame: pl.DataFrame, registry: DataRegistry
) -> ForcingArtifact:
    """Register the monthly->quarterly (mean) derived forcing artifact."""
    variable = registry.variables[parent.variable_id]
    if variable.aggregation not in ("sum", "mean", "end_of_period"):
        raise ResearchGateError(
            f"variable {parent.variable_id} declares aggregation "
            f"{variable.aggregation!r}; monthly_to_quarterly needs a flow rule"
        )
    quarterly = _canonical_long(
        monthly_to_quarterly(frame, cast(Aggregation, variable.aggregation))
    )
    periods = quarterly["period"].to_list()
    transformation = Transformation(
        method="monthly_to_quarterly",
        source_frequency=Frequency.MONTHLY,
        result_frequency=Frequency.QUARTERLY,
        aggregation=variable.aggregation,
        description=(
            f"{variable.aggregation} of the admitted monthly observations per "
            f"complete quarter; derived from {parent.artifact_id}"
        ),
    )
    transform_hash = canonical_digest(
        {
            "deriver": "hsm_lab.data.material",
            "transformation": transformation.model_dump(mode="json"),
        }
    )
    parent_rel_dir = str(Path(parent.path).parent)
    rel_path = (
        f"{parent_rel_dir}/{parent.variable_id}_quarterly_{periods[0]}_{periods[-1]}"
        f"_{transform_hash}.parquet"
    )
    digest, _ = _stage_bytes(Path(registry.root) / rel_path, _parquet_bytes(quarterly))
    provenance = Provenance(
        variable=parent.variable_id,
        role=DataRole.EXOGENOUS_FORCING,
        source_institution=parent.provenance.source_institution,
        dataset=parent.provenance.dataset,
        locator=parent.provenance.locator,
        retrieved_at=parent.provenance.retrieved_at,
        raw_sha256=parent.provenance.raw_sha256,
        original_frequency=Frequency.MONTHLY,
        model_frequency=Frequency.QUARTERLY,
        transformation=transformation,
        evidence_status=parent.provenance.evidence_status,
        rights=parent.provenance.rights,
        notes=(
            f"quarterly mean derived from admitted monthly artifact "
            f"{parent.artifact_id} (hsm_lab.data.material)"
        ),
        source_id=parent.source_id,
        source_period=f"{periods[0]}..{periods[-1]}",
        raw_path=parent.provenance.raw_path,
        derived_from=[parent.artifact_id],
        artifact_sha256=digest,
    )
    raw12 = (parent.provenance.raw_sha256 or digest)[:12]
    return ForcingArtifact(
        artifact_id=(
            f"{parent.variable_id}__{parent.source_id}__monthly_to_quarterly"
            f"__{raw12}__{transform_hash[:12]}"
        ),
        variable_id=parent.variable_id,
        path=rel_path,
        provenance=provenance,
        source_id=parent.source_id,
        period=PeriodRange(start=periods[0], end=periods[-1], frequency=Frequency.QUARTERLY),
    )


def _cmea_contract_rows(
    oil_monthly: pl.DataFrame, params: dict[str, float]
) -> tuple[pl.DataFrame, dict[str, dict[str, Any]]]:
    """Five-year-rule CMEA contract prices (plan section 6, piecewise constant).

    annual contract price = base * multiplier * mean(annual means of the
    prior 5 complete calendar years of world oil) / reference; every quarter
    of a contract year carries that year's price.  Only past complete years
    are read - no future observations enter the reconstruction.
    """
    quarterly = monthly_to_quarterly(oil_monthly, "mean")
    annual = quarterly_to_annual(quarterly, "mean")
    annual_mean = dict(
        zip(annual["period"].to_list(), annual["value"].to_list(), strict=True)
    )
    base = params["cmea_base_energy_price"]
    multiplier = params["cmea_uncertainty_multiplier"]
    reference = params["world_oil_reference"]
    first_year = int(CMEA_WINDOW[0][:4])
    last_year = int(CMEA_WINDOW[1][:4])
    rows: list[tuple[str, float]] = []
    audit: dict[str, dict[str, Any]] = {}
    for year in range(first_year, last_year + 1):
        input_years = [str(year - k) for k in range(5, 0, -1)]
        missing = [y for y in input_years if y not in annual_mean]
        if missing:
            raise ResearchGateError(
                f"cmea_five_year_contract: contract year {year} lacks complete "
                f"prior world-oil years {missing}; the five-year rule never "
                "reads future or incomplete years"
            )
        mean5 = sum(float(annual_mean[y]) for y in input_years) / 5.0
        price = base * multiplier * mean5 / reference
        audit[str(year)] = {"input_years": input_years, "contract_price": price}
        for quarter in (1, 2, 3, 4):
            rows.append((f"{year}Q{quarter}", price))
    frame = _long_frame(
        "cmea_energy_price",
        [period for period, _ in rows],
        [value for _, value in rows],
        "cmea_settlement_unit_per_p02_energy_unit",
    )
    return frame, audit



def build_external_material_pack(root: Path, source_reports: dict[str, object]) -> dict[str, Any]:
    """Compose the external forcing pack from admitted ingestion artifacts.

    Requires the World Bank oil and Federal Reserve rate ingestions (MNB FX
    optional); refuses with a ``ResearchGateError`` naming the missing
    source.  Derives and registers the quarterly forcing artifacts plus the
    five-year-rule reconstructed CMEA price, then writes
    ``data/observed/p02_material_external_pack.json``.
    """
    root = Path(root)
    registry = DataRegistry.load(root)

    def admitted_source_artifacts(source_id: str) -> list[dict[str, Any]]:
        report = source_reports.get(source_id)
        if report is not None:
            return _report_artifacts(report, source_id)
        artifacts = [
            {
                "artifact_id": artifact.artifact_id,
                "variable_id": artifact.variable_id,
                "role": artifact.role.value,
                "period": {"frequency": cast(ForcingArtifact, artifact).period.frequency.value},
            }
            for artifact in registry.artifacts.values()
            if artifact.source_id == source_id
        ]
        if not artifacts:
            raise ResearchGateError(
                f"external material pack requires admitted {source_id} artifacts; "
                f"run 'hsm data ingest --source {source_id}' first (missing source: "
                f"{source_id})"
            )
        return artifacts

    wb_artifacts = admitted_source_artifacts("worldbank_pink_sheet")
    fed_artifacts = admitted_source_artifacts("federalreserve_h15")
    mnb_artifacts = (
        admitted_source_artifacts("mnb_official_fx")
        if "mnb_official_fx" in source_reports
        or any(a.source_id == "mnb_official_fx" for a in registry.artifacts.values())
        else []
    )

    oil_monthly_id = _admitted_artifact_id(
        wb_artifacts, "world_oil_price", "worldbank_pink_sheet", "monthly"
    )
    rate_monthly_id = _admitted_artifact_id(
        fed_artifacts, "global_usd_rate", "federalreserve_h15", "monthly"
    )

    oil_monthly, oil_frame = _load_admitted_forcing(
        registry, oil_monthly_id, "worldbank_pink_sheet"
    )
    rate_monthly, rate_frame = _load_admitted_forcing(
        registry, rate_monthly_id, "federalreserve_h15"
    )


    oil_quarterly = _derive_quarterly(oil_monthly, oil_frame, registry)
    rate_quarterly = _derive_quarterly(rate_monthly, rate_frame, registry)
    derived: list[ForcingArtifact] = [oil_quarterly, rate_quarterly]

    # --- CMEA five-year contract reconstruction ---------------------------
    params = _external_reconstruction_params(root)
    params_hash = canonical_digest(params)
    cmea_frame, audit = _cmea_contract_rows(oil_frame, params)
    cmea_transformation = Transformation(
        method="cmea_five_year_contract",
        source_frequency=Frequency.MONTHLY,
        result_frequency=Frequency.QUARTERLY,
        aggregation="piecewise_constant",
        description=(
            f"{CMEA_RULE_VERSION}: annual contract price = cmea_base_energy_price "
            f"{params['cmea_base_energy_price']} x cmea_uncertainty_multiplier "
            f"{params['cmea_uncertainty_multiplier']} x mean(prior 5 complete "
            f"calendar years of world-oil annual means) / world_oil_reference "
            f"{params['world_oil_reference']}; input years "
            + "; ".join(
                f"{year}<-{audit[year]['input_years'][0]}..{audit[year]['input_years'][-1]}"
                for year in sorted(audit)
            )
        ),
    )
    cmea_transform_hash = canonical_digest(
        {"rule": CMEA_RULE_VERSION, "reconstruction_params": params}
    )
    raw_sha = cast(str, oil_monthly.provenance.raw_sha256 or oil_monthly.provenance.artifact_sha256)
    cmea_rel_dir = f"data/reconstructed/{oil_monthly.source_id}/{raw_sha}"
    cmea_rel = (
        f"{cmea_rel_dir}/cmea_energy_price_{CMEA_WINDOW[0]}_{CMEA_WINDOW[1]}"
        f"_{cmea_transform_hash}.parquet"
    )
    cmea_digest, _ = _stage_bytes(root / cmea_rel, _parquet_bytes(cmea_frame))
    cmea_provenance = Provenance(
        variable="cmea_energy_price",
        role=DataRole.EXOGENOUS_FORCING,
        source_institution=oil_monthly.provenance.source_institution,
        dataset=oil_monthly.provenance.dataset,
        locator=oil_monthly.provenance.locator,
        retrieved_at=oil_monthly.provenance.retrieved_at,
        raw_sha256=oil_monthly.provenance.raw_sha256,
        original_frequency=Frequency.MONTHLY,
        model_frequency=Frequency.QUARTERLY,
        transformation=cmea_transformation,
        evidence_status=EvidenceStatus.RECONSTRUCTED,
        rights=oil_monthly.provenance.rights,
        notes=(
            "reconstructed_historical_forcing: five-year-rule CMEA contract "
            f"price from admitted WB monthly oil {oil_monthly.artifact_id}; "
            "1957-1974 stays on the separate p02_cmea_contract_prior"
        ),
        source_id=oil_monthly.source_id,
        source_period=f"{CMEA_WINDOW[0]}..{CMEA_WINDOW[1]}",
        raw_path=oil_monthly.provenance.raw_path,
        derived_from=[oil_monthly.artifact_id],
        artifact_sha256=cmea_digest,
    )
    cmea_artifact = ForcingArtifact(
        artifact_id=(
            f"cmea_energy_price__{oil_monthly.source_id}__cmea_five_year_contract"
            f"__{raw_sha[:12]}__{cmea_transform_hash[:12]}"
        ),
        variable_id="cmea_energy_price",
        path=cmea_rel,
        provenance=cmea_provenance,
        source_id=oil_monthly.source_id,
        period=PeriodRange(
            start=CMEA_WINDOW[0], end=CMEA_WINDOW[1], frequency=Frequency.QUARTERLY
        ),
    )
    derived.append(cmea_artifact)

    # --- optional MNB official FX (only when admitted) --------------------
    fx_segment: dict[str, Any] | None = None
    if mnb_artifacts:
        fx_hits = [
            item
            for item in mnb_artifacts
            if item.get("variable_id") == "official_fx"
            and item.get("role") == DataRole.EXOGENOUS_FORCING.value
            and (item.get("period") or {}).get("frequency") == "dated"
        ]
        if len(fx_hits) != 1:
            raise ResearchGateError(
                "expected exactly one admitted MNB official_fx artifact, "
                f"found {len(fx_hits)}"
            )
        fx_id = str(fx_hits[0]["artifact_id"])
        fx_artifact, _ = _load_admitted_forcing(registry, fx_id, "mnb_official_fx")
        fx_segment = {
            "artifact_id": fx_artifact.artifact_id,
            "path": fx_artifact.path,
            "sha256": fx_artifact.provenance.artifact_sha256,
            "period": {
                "start": fx_artifact.period.start,
                "end": fx_artifact.period.end,
                "frequency": fx_artifact.period.frequency.value,
            },
            "evidence": "observed",
            "aggregation": "end_of_period",
            "note": (
                "optional quote reference; quarter-end quotes only, other "
                "quarters stay unavailable (never imputed)"
            ),
        }

    _append_artifact_manifest(root, derived)

    # --- read-back validation through the real registry gates ------------
    reloaded = DataRegistry.load(root)
    for spec in derived:
        admitted = reloaded.artifacts.get(spec.artifact_id)
        if admitted is None:
            raise ResearchGateError(
                f"derived artifact {spec.artifact_id} missing from reloaded registry"
            )
        reloaded.load_forcing(cast(ForcingArtifact, admitted))

    def observed_segment(spec: ForcingArtifact, evidence: str) -> dict[str, Any]:
        return {
            "artifact_id": spec.artifact_id,
            "path": spec.path,
            "sha256": spec.provenance.artifact_sha256,
            "period": {
                "start": spec.period.start,
                "end": spec.period.end,
                "frequency": spec.period.frequency.value,
            },
            "evidence": evidence,
            "derived_from": list(spec.provenance.derived_from),
        }

    segments: dict[str, Any] = {
        "world_oil_price": {
            "warmup": {
                "start": WARMUP_WINDOW[0],
                "end": WARMUP_WINDOW[1],
                "parameter": "oil_warmup_price",
                "evidence": "structural_warmup",
            },
            "observed": observed_segment(oil_quarterly, "observed"),
        },
        "global_usd_rate": observed_segment(rate_quarterly, "observed"),
    }
    cmea_segment = observed_segment(cmea_artifact, "reconstructed_historical_forcing")
    binding_payload = {
        "profile": "external",
        "segments": segments,
        "official_fx": fx_segment,
        "cmea_energy_price": cmea_segment,
    }
    pack: dict[str, Any] = {
        "schema_version": "1",
        "profile": "external",
        "warning": EXTERNAL_WARNING,
        "generated_at": FIXTURE_GENERATED_AT,
        "period": {
            "start": SYNTHETIC_QUARTERLY_WINDOW[0],
            "end": SYNTHETIC_QUARTERLY_WINDOW[1],
            "frequency": "quarterly",
        },
        "segments": segments,
        "official_fx": fx_segment,
        "cmea_energy_price": cmea_segment,
        "reconstruction_params": params,
        "reconstruction_params_hash": params_hash,
        "binding_hash": canonical_digest(binding_payload),
    }
    _stage_bytes(root / MATERIAL_EXTERNAL_PACK_PATH, _json_bytes(pack))
    return pack


# ----------------------------------------------------------------------
# 3. Forcing pack loading
# ----------------------------------------------------------------------


def _read_pack(registry: DataRegistry, rel: str) -> dict[str, Any]:
    path = registry.resolve_path(rel)
    if not path.is_file():
        raise ResearchGateError(
            f"forcing pack {rel} not found at {path}; packs are never built or "
            "downloaded by a run (use 'hsm data build-material-forcing')"
        )
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ResearchGateError(f"forcing pack {rel} is unreadable: {exc}") from exc
    if not isinstance(pack, dict):
        raise ResearchGateError(f"forcing pack {rel} must be a JSON object")
    if pack.get("schema_version") != "1":
        raise ResearchGateError(
            f"forcing pack {rel}: schema_version must be '1', got {pack.get('schema_version')!r}"
        )
    profile = pack.get("profile")
    if profile not in ("synthetic", "external"):
        raise ResearchGateError(
            f"forcing pack {rel}: unknown profile {profile!r} "
            "(expected 'synthetic' or 'external')"
        )
    return pack


def _segment_artifact(
    registry: DataRegistry, variable_id: str, segment: dict[str, Any], pack_rel: str
) -> tuple[ForcingArtifact, pl.DataFrame]:
    artifact_id = segment.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id:
        raise ResearchGateError(
            f"forcing pack {pack_rel}: segment {variable_id} carries no artifact_id"
        )
    artifact = registry.artifacts.get(artifact_id)
    if artifact is None:
        raise ResearchGateError(
            f"forcing pack {pack_rel}: artifact {artifact_id} (variable "
            f"{variable_id}) is not registered in data/manifests/artifacts.yml"
        )
    if not isinstance(artifact, ForcingArtifact):
        raise ResearchGateError(
            f"forcing pack {pack_rel}: artifact {artifact_id} has role "
            f"{artifact.role.value}; only exogenous_forcing artifacts may feed "
            "material forcing (input != target != parameter)"
        )
    if artifact.variable_id != variable_id:
        raise ResearchGateError(
            f"forcing pack {pack_rel}: segment {variable_id} bound artifact "
            f"{artifact_id} carries variable {artifact.variable_id!r}"
        )
    frame = registry.load_forcing(artifact)  # digest re-verified here
    declared = segment.get("sha256")
    if declared != artifact.provenance.artifact_sha256:
        raise ResearchGateError(
            f"forcing pack {pack_rel}: sha256 {declared!r} for artifact "
            f"{artifact_id} does not match the registry declaration "
            f"{artifact.provenance.artifact_sha256}"
        )
    return artifact, frame


def _validate_quarter_label(period: object, artifact_id: str) -> None:
    if not isinstance(period, str) or _QUARTER_LABEL_RE.fullmatch(period) is None:
        raise ResearchGateError(
            f"artifact {artifact_id}: period {period!r} is not a quarterly label"
        )


def _quarterly_values(frame: pl.DataFrame, artifact_id: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for period, value in zip(
        frame["period"].to_list(), frame["value"].to_list(), strict=True
    ):
        _validate_quarter_label(period, artifact_id)
        if period in values:
            raise ResearchGateError(
                f"artifact {artifact_id}: duplicate quarterly period {period}"
            )
        values[period] = float(value)
    return values



def _require_exact_coverage(
    values: dict[str, float],
    quarters: list[str],
    label: str,
    *,
    allowed_quarters: set[str] | None = None,
) -> None:
    """Require requested ticks while allowing pack rows within the frozen core.

    A paused/benchmark run consumes a prefix; the immutable forcing pack may
    cover the full core horizon. Rows outside that declared core (including
    reserved extension) remain a hard error.
    """
    wanted = set(quarters)
    allowed = wanted if allowed_quarters is None else allowed_quarters
    missing = [q for q in quarters if q not in values]
    extra = sorted(p for p in values if p not in allowed)
    if missing or extra:
        raise ResearchGateError(
            f"{label}: pack coverage does not match the declared horizon "
            f"{quarters[0]}..{quarters[-1]} - missing {missing[:4]}"
            f"{'...' if len(missing) > 4 else ''}, outside core {extra[:4]}"
            f"{'...' if len(extra) > 4 else ''} (gaps and reserved spill are refused)"
        )


def load_material_forcing(spec: ScenarioSpec, registry: DataRegistry) -> MaterialForcing:
    """Load the admitted quarterly forcing grid for a material scenario.

    Every bound artifact is re-admitted through ``DataRegistry.load_forcing``
    (role/rights/digest gates), the pack's recorded digests must match the
    registry, and the assembled series must cover the declared horizon
    exactly.  Scenario ``ForcingBinding`` windows are verified as subsets of
    the actually covered quarters.
    """
    if spec.forcing_pack is None:
        raise ResearchGateError(
            f"scenario {spec.scenario_id} declares no forcing_pack; material "
            "runs consume forcing only through an explicit pack"
        )
    if spec.material_parameters is None:  # pragma: no cover - schema enforces
        raise ResearchGateError(
            f"scenario {spec.scenario_id} lacks material_parameters "
            "(warm-up oil price required)"
        )
    pack = _read_pack(registry, spec.forcing_pack)
    profile = pack["profile"]
    contract = load_research_contract(registry.root)
    core_quarters = [
        str(contract.core_start.advance(k)) for k in range(contract.core_ticks)
    ]
    core_set = set(core_quarters)
    quarters = [str(spec.start.advance(k)) for k in range(spec.ticks)]
    if not set(quarters) <= core_set:
        raise ResearchGateError(
            f"scenario {spec.scenario_id}: requested forcing window spills outside "
            "the frozen core"
        )
    index = {quarter: k for k, quarter in enumerate(quarters)}
    ticks = spec.ticks

    oil = np.full(ticks, np.nan, dtype=np.float64)
    rate = np.full(ticks, np.nan, dtype=np.float64)
    fx = np.full(ticks, np.nan, dtype=np.float64)
    cmea = np.full(ticks, np.nan, dtype=np.float64)
    segment_labels: list[str] = [""] * ticks
    hashes: dict[str, str] = {}
    covered: dict[str, set[str]] = {}
    segment_artifacts: dict[str, str] = {}

    segments = pack.get("segments")
    if not isinstance(segments, dict):
        raise ResearchGateError(f"forcing pack {spec.forcing_pack}: missing segments object")
    binding_payload = (
        {"profile": "synthetic", "segments": segments}
        if profile == "synthetic"
        else {
            "profile": "external",
            "segments": segments,
            "official_fx": pack.get("official_fx"),
            "cmea_energy_price": pack.get("cmea_energy_price"),
        }
    )
    if pack.get("binding_hash") != canonical_digest(binding_payload):
        raise ResearchGateError(
            f"forcing pack {spec.forcing_pack}: binding_hash does not match the "
            "recorded bindings (pack integrity gate)"
        )

    def fill_series(array_name: str, values: dict[str, float], label: str | None = None) -> None:
        array = {"oil": oil, "rate": rate, "fx": fx, "cmea": cmea}[array_name]
        for period, value in values.items():
            position = index.get(period)
            if position is None:
                if period in core_set:
                    continue
                raise ResearchGateError(
                    f"forcing pack {spec.forcing_pack}: period {period} lies "
                    "outside the frozen core horizon"
                )
            array[position] = value
            if label is not None:
                segment_labels[position] = label

    if profile == "synthetic":
        for variable_id in ("world_oil_price", "global_usd_rate"):
            seg = segments.get(variable_id)
            if not isinstance(seg, dict):
                raise ResearchGateError(
                    f"synthetic forcing pack {spec.forcing_pack}: segment "
                    f"{variable_id} is missing"
                )
            artifact, frame = _segment_artifact(registry, variable_id, seg, spec.forcing_pack)
            values = _quarterly_values(frame, artifact.artifact_id)
            _require_exact_coverage(
                values, quarters, f"segment {variable_id}", allowed_quarters=core_set
            )
            fill_series("oil" if variable_id == "world_oil_price" else "rate", values)
            hashes[artifact.artifact_id] = artifact.provenance.artifact_sha256 or ""
            covered[variable_id] = set(values)
            segment_artifacts[variable_id] = artifact.artifact_id
        segment_labels = ["synthetic"] * ticks
        # Synthetic profile carries the CMEA price from scenario parameters
        # only; official FX is unavailable by construction.
    else:
        params = spec.material_parameters
        expected_params = {
            "cmea_base_energy_price": float(params.cmea_base_energy_price),
            "cmea_uncertainty_multiplier": float(params.cmea_uncertainty_multiplier),
            "world_oil_reference": float(params.world_oil_reference),
        }
        pack_params = pack.get("reconstruction_params")
        if pack_params != expected_params:
            raise ResearchGateError(
                f"forcing pack {spec.forcing_pack}: reconstruction_params "
                f"{pack_params} do not match the scenario's selected values "
                f"{expected_params}; rebuild the pack after changing parameters"
            )
        if pack.get("reconstruction_params_hash") != canonical_digest(pack_params):
            raise ResearchGateError(
                f"forcing pack {spec.forcing_pack}: reconstruction_params_hash "
                "does not match reconstruction_params"
            )

        oil_seg = segments.get("world_oil_price")
        if not isinstance(oil_seg, dict) or "observed" not in oil_seg or "warmup" not in oil_seg:
            raise ResearchGateError(
                f"external forcing pack {spec.forcing_pack}: world_oil_price "
                "segment needs both 'warmup' and 'observed' parts"
            )
        artifact, frame = _segment_artifact(
            registry, "world_oil_price", oil_seg["observed"], spec.forcing_pack
        )
        observed = _quarterly_values(frame, artifact.artifact_id)
        hashes[artifact.artifact_id] = artifact.provenance.artifact_sha256 or ""
        segment_artifacts["world_oil_price"] = artifact.artifact_id
        warmup = oil_seg["warmup"]
        warmup_quarters = _quarter_range(warmup["start"], warmup["end"])
        stray = [q for q in warmup_quarters if q in observed]
        if stray:
            raise ResearchGateError(
                f"forcing pack {spec.forcing_pack}: warm-up and observed oil "
                f"overlap at {stray[:4]}; segments must partition the horizon"
            )
        outside = [q for q in warmup_quarters if q not in core_set]
        if outside:
            raise ResearchGateError(
                f"forcing pack {spec.forcing_pack}: warm-up window extends "
                f"outside the frozen core ({outside[:4]})"
            )
        _require_exact_coverage(
            {**{q: 0.0 for q in warmup_quarters}, **observed},
            quarters,
            "segment world_oil_price (warmup + observed)",
            allowed_quarters=core_set,
        )
        warmup_price = float(params.oil_warmup_price)
        for q in warmup_quarters:
            position = index.get(q)
            if position is not None:
                oil[position] = warmup_price
                segment_labels[position] = "structural_warmup"
        for period, value in observed.items():
            position = index.get(period)
            if position is not None:
                oil[position] = value
                segment_labels[position] = "observed"
        covered["world_oil_price"] = set(warmup_quarters) | set(observed)

        rate_seg = segments.get("global_usd_rate")
        if not isinstance(rate_seg, dict):
            raise ResearchGateError(
                f"external forcing pack {spec.forcing_pack}: global_usd_rate "
                "segment is missing"
            )
        artifact, frame = _segment_artifact(
            registry, "global_usd_rate", rate_seg, spec.forcing_pack
        )
        rate_values = _quarterly_values(frame, artifact.artifact_id)
        _require_exact_coverage(
            rate_values, quarters, "segment global_usd_rate", allowed_quarters=core_set
        )
        fill_series("rate", rate_values)
        hashes[artifact.artifact_id] = artifact.provenance.artifact_sha256 or ""
        covered["global_usd_rate"] = set(rate_values)
        segment_artifacts["global_usd_rate"] = artifact.artifact_id

        cmea_seg = pack.get("cmea_energy_price")
        if isinstance(cmea_seg, dict):
            artifact, frame = _segment_artifact(
                registry, "cmea_energy_price", cmea_seg, spec.forcing_pack
            )
            cmea_values = _quarterly_values(frame, artifact.artifact_id)
            stray = [p for p in cmea_values if p not in core_set]
            if stray:
                raise ResearchGateError(
                    f"forcing pack {spec.forcing_pack}: cmea_energy_price "
                    f"extends outside the frozen core ({stray[:4]})"
                )
            fill_series("cmea", cmea_values, label="reconstructed")
            hashes[artifact.artifact_id] = artifact.provenance.artifact_sha256 or ""
            covered["cmea_energy_price"] = set(cmea_values)
            segment_artifacts["cmea_energy_price"] = artifact.artifact_id

        fx_seg = pack.get("official_fx")
        if isinstance(fx_seg, dict):
            artifact, frame = _segment_artifact(registry, "official_fx", fx_seg, spec.forcing_pack)
            quarterly_fx = dated_to_quarterly(frame, "end_of_period")
            fx_values = _quarterly_values(quarterly_fx, artifact.artifact_id)
            stray = [p for p in fx_values if p not in core_set]
            if stray:
                raise ResearchGateError(
                    f"forcing pack {spec.forcing_pack}: official_fx quarters "
                    f"outside the frozen core ({stray[:4]})"
                )
            fill_series("fx", fx_values)
            hashes[artifact.artifact_id] = artifact.provenance.artifact_sha256 or ""
            covered["official_fx"] = set(fx_values)
            segment_artifacts["official_fx"] = artifact.artifact_id
        # official_fx stays NaN wherever no quote exists (never imputed).

    # Scenario binding subset checks: each binding's required window must be
    # covered by the actually loaded series.
    for binding in spec.forcing_bindings:
        variable_id = binding.variable_id
        if variable_id not in MATERIAL_FORCING_VARIABLE_IDS:  # pragma: no cover
            raise ResearchGateError(
                f"forcing binding {variable_id} is not a material forcing variable"
            )
        coverage = covered.get(variable_id)
        if not coverage:
            raise ResearchGateError(
                f"forcing binding {variable_id} is not provided by forcing pack "
                f"{spec.forcing_pack}"
            )
        if (
            binding.artifact_id is not None
            and segment_artifacts.get(variable_id) != binding.artifact_id
        ):
            raise ResearchGateError(
                f"forcing binding {variable_id} names artifact "
                f"{binding.artifact_id!r} but the pack supplies "
                f"{segment_artifacts.get(variable_id)!r}"
            )
        required = _quarter_range(binding.required_period_start, binding.required_period_end)
        missing = [q for q in required if q not in coverage]
        if missing:
            raise ResearchGateError(
                f"forcing binding {variable_id} requires "
                f"{binding.required_period_start}..{binding.required_period_end} "
                f"but quarters {missing[:4]} are not covered by the admitted pack"
            )

    return MaterialForcing(
        quarters=quarters,
        oil_price=oil,
        global_usd_rate=rate,
        official_fx=fx,
        cmea_energy_price=cmea,
        segment=segment_labels,
        input_artifact_hashes=hashes,
    )


# ----------------------------------------------------------------------
# 4. Isolated target interface
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class TargetDataset:
    """One admitted TARGET dataset plus the purpose it was loaded for.

    Constructed only by :func:`load_material_targets`; never enters
    ``initialize_material``/``tick_material``/``run_material`` signatures.
    """

    artifact_id: str
    use: TargetUse
    frame: pl.DataFrame


def load_material_targets(
    registry: DataRegistry, artifact_id: str, use: TargetUse
) -> TargetDataset:
    """Load one TARGET artifact for an explicitly declared purpose.

    Fails closed on non-target roles, missing purposes and reserved-window
    attempts before any numeric read.
    """
    artifact = registry.artifacts.get(artifact_id)
    if artifact is None:
        raise ResearchGateError(f"unknown target artifact {artifact_id!r}")
    if not isinstance(artifact, TargetArtifact):
        raise ResearchGateError(
            f"artifact {artifact_id!r} has role {artifact.role.value}; "
            "load_material_targets requires a TARGET artifact "
            "(input != target != parameter)"
        )
    if not isinstance(use, TargetUse):
        raise ResearchGateError(
            f"load_material_targets requires an explicit TargetUse purpose; "
            f"got {use!r}. Numeric target access without a declared purpose "
            "is refused."
        )
    if use is TargetUse.RESERVED:
        raise ResearchGateError(
            f"target {artifact_id}: reserved outcomes are never numerically "
            "loaded (hold-out gate, BASELINE §37)"
        )
    frame = registry.load_targets(artifact, use)
    return TargetDataset(artifact_id=artifact_id, use=use, frame=frame)


def compare_annual(
    simulated: pl.DataFrame,
    targets: TargetDataset,
    aggregation: Literal["sum", "mean", "end_of_period"],
) -> pl.DataFrame:
    """Compare a quarterly simulated series against an annual target dataset.

    ``simulated`` is a long quarterly frame with at least ``period``,
    ``value`` and ``unit`` columns (extra key columns such as
    ``region_id``/``commodity_id`` join through when shared with the target).
    The simulated series is aggregated with ``quarterly_to_annual`` under the
    declared ``aggregation``; metric (join keys), unit and year alignment are
    validated before residuals are computed.
    """
    if aggregation not in ("sum", "mean", "end_of_period"):
        raise ResearchGateError(
            f"compare_annual aggregation must be sum/mean/end_of_period, "
            f"got {aggregation!r}"
        )
    for column in ("period", "value", "unit"):
        if column not in simulated.columns:
            raise ResearchGateError(
                f"simulated frame must carry a {column!r} column; got "
                f"{simulated.columns}"
            )
    keys = [name for name in simulated.columns if name not in ("period", "value")]
    annual = quarterly_to_annual(simulated.select([*keys, "period", "value"]), aggregation)
    annual = annual.rename({"value": "value_simulated", "unit": "unit_simulated"})

    target = targets.frame.select(
        [
            pl.col("variable_id"),
            pl.col("period"),
            pl.col("region_id"),
            pl.col("commodity_id"),
            pl.col("value").alias("value_target"),
            pl.col("unit").alias("unit_target"),
        ]
    )
    target_keys = [name for name in ("variable_id", "region_id", "commodity_id") if name in keys]
    joined = target.join(
        annual,
        on=[*target_keys, "period"],
        how="left",
    )
    missing = joined.filter(pl.col("value_simulated").is_null())
    if missing.height:
        raise ResearchGateError(
            f"target {targets.artifact_id}: year/key alignment failed - no "
            f"simulated annual value for {missing.height} target row(s), e.g. "
            f"{missing.select([*target_keys, 'period']).head(3).to_dicts()}"
        )
    bad_unit = joined.filter(pl.col("unit_simulated") != pl.col("unit_target"))
    if bad_unit.height:
        raise ResearchGateError(
            f"target {targets.artifact_id}: unit mismatch between simulated "
            "and target series, e.g. "
            f"{bad_unit.select(['period', 'unit_simulated', 'unit_target']).head(3).to_dicts()}"
        )
    result = joined.with_columns(
        (pl.col("value_simulated") - pl.col("value_target")).alias("residual")
    ).select(
        [
            pl.col("period"),
            *[pl.col(name) for name in target_keys],
            pl.col("value_simulated"),
            pl.col("value_target"),
            pl.col("unit_target").alias("unit"),
            pl.col("residual"),
        ]
    )
    return result.sort(["period", *target_keys])
