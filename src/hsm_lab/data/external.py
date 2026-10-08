"""P04 input boundary: external pack, event registry, policy replay, broadcasts.

This module is the *only* way P04 political inputs enter a run.  It mirrors the
P02 material data layer: deterministic local fixtures, immutable/idempotent
registry builds, role/rights/digest gates, and a fail-closed external profile
that never downloads and never silently degrades to synthetic.

Nothing here is a historical Hungarian estimate.  Structural external proxies
(subjective indices, base multipliers, signal loadings) are registered as
``latent_parameter`` artifacts with ``structural_assumption / not_calibrated /
not_assessed`` status; only variables with declared historical anchors may bind
a reconstructed/observed forcing series.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
import polars as pl
import yaml

from hsm_lab.contract.base import ConfigError, ResearchGateError
from hsm_lab.contract.guards import load_research_contract, sha256_file
from hsm_lab.contract.material import MaterialParameters
from hsm_lab.contract.politics import (
    EXTERNAL_OPTIONAL_VARIABLES,
    EXTERNAL_VARIABLE_IDS,
    POLICY_COORDINATES,
    SIGNAL_CHANNELS,
    EventRegistry,
    ExternalWorldPack,
    InformationMessage,
    InformationProgram,
    PolicyReplayRegistry,
    PoliticalParameters,
    PoliticalRunSpec,
)
from hsm_lab.contract.schemas import (
    DataRole,
    EvidenceStatus,
    Frequency,
    Quarter,
)
from hsm_lab.data.material import _ensure_manifest_entries, _fixture_rights
from hsm_lab.data.registry import DataRegistry
from hsm_lab.data.schemas import (
    Bounds,
    ForcingArtifact,
    ParameterArtifact,
    ParameterPriorFile,
    PeriodRange,
    Provenance,
    Transformation,
)
from hsm_lab.provenance.manifest import canonical_digest

P04_SYNTHETIC_PACK_PATH = "data/fixtures/p04_external_synthetic_pack.json"
P04_HYBRID_PACK_PATH = "data/reconstructed/p04_external_hybrid_pack.json"
P04_EVENT_REGISTRY_PATH = "data/manifests/external_events.yml"
P04_REPLAY_REGISTRY_PATH = "data/manifests/policy_replay.yml"
P04_INFORMATION_PROGRAM_PATH = "data/fixtures/p04_information_program.json"
P04_POLICY_FIXTURE_DIR = "data/fixtures/p04_policy"

P04_FIXTURE_SOURCE_ID = "p04_fixture"
P04_FIXTURE_LOCATOR = "fixture:p04-politics"
P04_FIXTURE_DATASET = "P04 political/external/information structural fixtures"
P04_FIXTURE_GENERATED_AT = "2026-10-08T00:00:00Z"
_FIXTURE_GENERATED_AT_DT = datetime.fromisoformat("2026-10-08T00:00:00+00:00")
P04_WARNING = "p04_structural_fixture_not_historical_fit"

#: Sensible default content-sensitivity by channel (fixture engineering values).
CHANNEL_CONTENT_SENSITIVITY: dict[str, float] = {
    "western_comparison": 0.5,
    "official_policy": 0.1,
    "opposition_success": 0.8,
    "public_action_risk": 0.1,
    "foreign_linkage": 0.5,
    "intellectual_linkage": 0.8,
    "worker_linkage": 0.8,
    "regime_threat": 0.1,
    "repression_cost": 0.1,
}

#: Intensities overridden for the solidarity fixture (tolerated-propagation test).
SOLIDARITY_TOLERATED_CHANNELS = frozenset({"opposition_success", "worker_linkage"})
SOLIDARITY_TOLERATED_SENSITIVITY = 0.6

_P04_PARAMETER_MODULES = (
    "coalition",
    "broker",
    "information",
    "observation",
    "culture",
    "opposition",
    "external_recipe",
)


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _parquet_bytes(frame: pl.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.write_parquet(buffer)
    return buffer.getvalue()


def _stage_bytes(path: Path, data: bytes) -> tuple[str, bool]:
    """Immutable-content write; identical reuse, conflicting drift fails closed."""
    digest = hashlib.sha256(data).hexdigest()
    if path.is_file():
        existing = sha256_file(path)
        if existing == digest:
            return digest, True
        raise ResearchGateError(
            f"{path}: existing content (sha256 {existing}) differs from the "
            f"deterministic generated content (sha256 {digest}); P04 input files are "
            "immutable - investigate the drift instead of overwriting"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return digest, False


def _quarter_range(start: str, end: str) -> list[str]:
    first = Quarter.parse(start)
    last = Quarter.parse(end)
    return [str(first.advance(k)) for k in range(last.to_ordinal() - first.to_ordinal() + 1)]


# ---------------------------------------------------------------------------
# Manifests: fixture source, latent political parameter priors
# ---------------------------------------------------------------------------

_P04_SOURCE_ENTRY: dict[str, Any] = {
    "source_id": P04_FIXTURE_SOURCE_ID,
    "institution": "HSM Lab local fixture",
    "dataset": P04_FIXTURE_DATASET,
    "locator": P04_FIXTURE_LOCATOR,
    "expected_format": ["JSON", "PARQUET"],
    "expected_roles": ["exogenous_forcing", "latent_parameter", "initial_state"],
    "retrieval_method": "local deterministic generation inside this repository",
    "access_status": "public_metadata",
    "audit_status": "metadata_checked",
    "rights": _fixture_rights().model_dump(mode="json"),
    "coverage_notes": (
        "Deterministic synthetic/structural P04 inputs 1957Q1..1985Q4: external "
        "recipe, 16-event chronology, policy replay schedule and broadcast program."
    ),
    "notes": (
        "Local structural fixture source; real historical anchors, if any, must be "
        "registered through their own audited source, never here."
    ),
}


def _p04_variable_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for module in _P04_PARAMETER_MODULES:
        entries.append(
            {
                "variable_id": f"p04_{module}_parameters",
                "semantic_kind": "latent",
                "allowed_roles": ["latent_parameter"],
                "unit": "dimensionless",
                "original_frequency": "static",
                "aggregation": None,
                "notes": (
                    f"P04 {module} latent parameter block; selected values and per-scalar "
                    "engineering bounds recorded in the prior file. Structural assumption, "
                    "not calibrated, not assessed."
                ),
            }
        )
    for coordinate in POLICY_COORDINATES:
        entries.append(
            {
                "variable_id": f"policy_{coordinate}",
                "semantic_kind": "policy_input",
                "allowed_roles": ["exogenous_forcing"],
                "unit": "dimensionless",
                "original_frequency": "quarterly",
                "aggregation": None,
                "notes": (
                    f"Domestic policy tool {coordinate} (Mode A replay input); a declared "
                    "policy instrument, never a realized outcome and never observed."
                ),
            }
        )
    return entries


def register_p04_manifests(root: Path) -> None:
    """Idempotently register the P04 fixture source and latent/policy variables."""
    _ensure_manifest_entries(root, "sources.yml", "sources", "source_id", [_P04_SOURCE_ENTRY])
    _ensure_manifest_entries(
        root, "variables.yml", "variables", "variable_id", _p04_variable_entries()
    )


def _scalar_bounds(key: str) -> tuple[float, float]:
    """Declared engineering envelope for one flattened scalar (documented rule)."""
    signed = (
        key.startswith("coalition.intercept")
        or key.startswith("coalition.beta")
        or key.startswith("coalition.interaction")
        or key.startswith("broker.A")
        or key.startswith("broker.q")
        or key.startswith("broker.target_base")
        or key.startswith("broker.target_response")
        or key.startswith("broker.ideal")
        or key.endswith("official_loading")
        or key.endswith("western_loading")
        or key.endswith("signal_lower")
        or key.endswith("base_western_inflation")
    )
    if signed:
        low = -100.0 if key.endswith("base_western_inflation") else -2.0
        return low, 2.0
    if key.endswith("lag_cap"):
        return 0.0, 8.0
    return 0.0, 2.0


def _political_prior_payloads(parameters: PoliticalParameters) -> dict[str, dict[str, Any]]:
    """Per-module prior payload + artifact declaration for the P04 parameters."""
    payloads: dict[str, dict[str, Any]] = {}
    for module in _P04_PARAMETER_MODULES:
        group = getattr(parameters, module)
        flat = {f"p04.{module}.{k}": float(v) for k, v in group.flatten().items()}
        scalar_bounds = {key: _scalar_bounds(key[len(f"p04.{module}.") :]) for key in flat}
        envelope = (
            min(b[0] for b in scalar_bounds.values()),
            max(b[1] for b in scalar_bounds.values()),
        )
        payloads[module] = {
            "schema_version": "1",
            "variable_id": f"p04_{module}_parameters",
            "literature_refs": [f"structural engineering fixture: P04 {module} parameters"],
            "prior_description": (
                f"Selected engineering values and per-scalar bounds for the P04 {module} "
                "parameter block; every value is a declared structural assumption with no "
                "calibration against observed Hungarian series."
            ),
            "bounds": {"lower": envelope[0], "upper": envelope[1]},
            "calibration_status": "not_calibrated",
            "sensitivity_status": "not_assessed",
            "uncertainty_notes": (
                "not_calibrated / not_assessed. Declared envelope ["
                f"{envelope[0]}, {envelope[1]}]; selected_value_flat="
                + json.dumps(flat, sort_keys=True)
                + "; scalar_bounds="
                + json.dumps({k: list(v) for k, v in sorted(scalar_bounds.items())}, sort_keys=True)
            ),
        }
    return payloads


# ---------------------------------------------------------------------------
# External world pack
# ---------------------------------------------------------------------------


def _external_values(
    root: Path, profile: str, parameters: PoliticalParameters, quarters: list[str]
) -> tuple[dict[str, list[float | None]], dict[str, dict[str, str]]]:
    """Assemble the 12-variable external grid for the requested profile."""
    ticks = len(quarters)
    recipe = parameters.external_recipe
    values: dict[str, list[float | None]] = {}
    meta: dict[str, dict[str, str]] = {}

    def constant(variable: str, value: float, origin: str, evidence: str) -> None:
        values[variable] = [float(value)] * ticks
        meta[variable] = {
            "unit": "index",
            "origin": origin,
            "evidence_status": evidence,
        }

    # Series-bound variables: synthetic profile uses the p02 synthetic fixture
    # series; external profile binds the admitted material external series.
    if profile == "synthetic":
        from hsm_lab.data.material import (
            MATERIAL_SYNTHETIC_PACK_PATH,
            build_synthetic_material_fixtures,
        )

        pack_path = root / MATERIAL_SYNTHETIC_PACK_PATH
        if not pack_path.is_file():
            build_synthetic_material_fixtures(root)
        registry = DataRegistry.load(root)
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        for variable, field in (("world_oil_price", "oil"), ("global_usd_rate", "rate")):
            segment = pack["segments"][variable]
            artifact = registry.artifacts[segment["artifact_id"]]
            frame = registry.load_forcing(cast("ForcingArtifact", artifact))
            by_quarter = dict(zip(frame["period"].to_list(), frame["value"].to_list(), strict=True))
            values[variable] = [float(by_quarter[q]) if q in by_quarter else None for q in quarters]
            meta[variable] = {
                "unit": "USD_per_barrel" if field == "oil" else "percent_per_year",
                "origin": segment["artifact_id"],
                "evidence_status": segment["evidence"],
            }
    else:
        from hsm_lab.data.material import MATERIAL_EXTERNAL_PACK_PATH

        pack_path = root / MATERIAL_EXTERNAL_PACK_PATH
        if not pack_path.is_file():
            raise ResearchGateError(
                f"external P04 profile requires the admitted material external pack at "
                f"{pack_path}; run 'hsm data build-material-forcing --profile external' "
                "first (no synthetic fallback)"
            )
        registry = DataRegistry.load(root)
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        oil_seg = pack["segments"]["world_oil_price"]
        oil_values: dict[str, float] = {}
        for part in (oil_seg.get("warmup"), oil_seg.get("observed")):
            if not isinstance(part, dict):
                continue
            if "artifact_id" in part:
                artifact = registry.artifacts[part["artifact_id"]]
                frame = registry.load_forcing(cast("ForcingArtifact", artifact))
                oil_values.update(
                    dict(zip(frame["period"].to_list(), frame["value"].to_list(), strict=True))
                )
            else:
                start, end = part["start"], part["end"]
                warmup_value = float(MaterialParameters().oil_warmup_price)
                for quarter in _quarter_range(start, end):
                    oil_values[quarter] = warmup_value
        values["world_oil_price"] = [oil_values.get(q) for q in quarters]
        meta["world_oil_price"] = {
            "unit": "USD_per_barrel",
            "origin": str(oil_seg.get("observed", {}).get("artifact_id", "material_external_pack")),
            "evidence_status": "reconstructed",
        }
        rate_seg = pack["segments"]["global_usd_rate"]
        artifact = registry.artifacts[rate_seg["artifact_id"]]
        frame = registry.load_forcing(cast("ForcingArtifact", artifact))
        rate_by_quarter = dict(
            zip(frame["period"].to_list(), frame["value"].to_list(), strict=True)
        )
        values["global_usd_rate"] = [float(rate_by_quarter[q]) for q in quarters]
        meta["global_usd_rate"] = {
            "unit": "percent_per_year",
            "origin": rate_seg["artifact_id"],
            "evidence_status": "observed",
        }

    # Declared-missing diagnostics (never fabricated).
    values["official_fx"] = [None] * ticks
    meta["official_fx"] = {
        "unit": "HUF_per_USD",
        "origin": "missing",
        "evidence_status": "observed",
    }
    values["cmea_energy_price"] = [None] * ticks
    meta["cmea_energy_price"] = {
        "unit": "cmea_settlement_unit_per_p02_energy_unit",
        "origin": "missing",
        "evidence_status": "reconstructed",
    }

    # Structural external proxies.
    constant(
        "soviet_energy_availability",
        recipe.base_energy_quota,
        "p04.external_recipe.base_energy_quota",
        "structural_assumption",
    )
    constant(
        "western_demand",
        recipe.base_western_demand,
        "p04.external_recipe.base_western_demand",
        "structural_assumption",
    )
    constant(
        "cmea_demand",
        recipe.base_cmea_demand,
        "p04.external_recipe.base_cmea_demand",
        "structural_assumption",
    )
    constant(
        "western_inflation",
        recipe.base_western_inflation,
        "p04.external_recipe.base_western_inflation",
        "structural_assumption",
    )
    constant(
        "international_credit_availability",
        recipe.base_credit_availability,
        "p04.external_recipe.base_credit_availability",
        "structural_assumption",
    )
    constant(
        "technology_access",
        recipe.base_technology_access,
        "p04.external_recipe.base_technology_access",
        "structural_assumption",
    )

    # Political indices precompiled from the event registry (recipe + loadings).
    events = load_event_registry(root)
    tension: list[float] = []
    constraint: list[float] = []
    for quarter in quarters:
        parsed = Quarter.parse(quarter)
        active = [event for event in events.events if event.active(parsed)]
        threat_events = [e for e in active if "regime_threat" in e.signal_channels]
        tolerance_events = [e for e in active if "opposition_success" in e.signal_channels]
        tension.append(
            float(
                np.clip(
                    recipe.base_geopolitical_tension + recipe.default_loading * len(threat_events),
                    0.0,
                    1.0,
                )
            )
        )
        constraint.append(
            float(
                np.clip(
                    recipe.base_soviet_constraint
                    + recipe.default_loading * (len(threat_events) - len(tolerance_events)),
                    0.0,
                    1.0,
                )
            )
        )
    values["geopolitical_tension"] = tension
    meta["geopolitical_tension"] = {
        "unit": "index",
        "origin": "p04.external_recipe.base_geopolitical_tension",
        "evidence_status": "structural_assumption",
    }
    values["soviet_constraint"] = constraint
    meta["soviet_constraint"] = {
        "unit": "index",
        "origin": "p04.external_recipe.base_soviet_constraint",
        "evidence_status": "structural_assumption",
    }
    return values, meta


def build_p04_inputs(root: Path, profile: str) -> dict[str, Any]:
    """Generate/register the P04 external pack, event registry, replay and program."""
    if profile not in ("synthetic", "external"):
        raise ConfigError(f"unknown P04 profile {profile!r}: use synthetic or external")
    root = Path(root)
    register_p04_manifests(root)
    parameters = PoliticalParameters()
    contract = load_research_contract(root)
    quarters = [str(contract.core_start.advance(k)) for k in range(contract.core_ticks)]

    files: list[tuple[str, str]] = []
    reused: list[bool] = []

    def stage(rel: str, data: bytes) -> str:
        digest, was_reused = _stage_bytes(root / rel, data)
        files.append((rel, digest))
        reused.append(was_reused)
        return digest

    # --- latent parameter priors -----------------------------------------
    prior_payloads = _political_prior_payloads(parameters)
    parameter_specs: list[ParameterArtifact] = []
    for module, payload in prior_payloads.items():
        rel = f"data/fixtures/p04_priors/p04_{module}_parameters.json"
        ParameterPriorFile.model_validate(payload)
        digest = stage(rel, _json_bytes(payload))
        bounds = Bounds(**payload["bounds"])
        parameter_specs.append(
            ParameterArtifact(
                artifact_id=f"p04_{module}_prior",
                variable_id=f"p04_{module}_parameters",
                path=rel,
                provenance=Provenance(
                    variable=f"p04_{module}_parameters",
                    role=DataRole.LATENT_PARAMETER,
                    source_institution="HSM Lab local fixture",
                    dataset=P04_FIXTURE_DATASET,
                    locator=P04_FIXTURE_LOCATOR,
                    retrieved_at=_FIXTURE_GENERATED_AT_DT,
                    raw_sha256=digest,
                    original_frequency=Frequency.STATIC,
                    model_frequency=Frequency.STATIC,
                    transformation=Transformation(
                        method="literature_prior",
                        source_frequency=Frequency.STATIC,
                        result_frequency=Frequency.STATIC,
                        aggregation=None,
                        description="Structural political parameter prior declared locally",
                    ),
                    evidence_status=EvidenceStatus.STRUCTURAL_ASSUMPTION,
                    rights=_fixture_rights(),
                    notes="P04 latent political parameter prior; not calibrated.",
                    source_id=P04_FIXTURE_SOURCE_ID,
                    artifact_sha256=digest,
                ),
                source_id=P04_FIXTURE_SOURCE_ID,
                literature_refs=list(payload["literature_refs"]),
                prior_description=str(payload["prior_description"]),
                bounds=bounds,
                uncertainty_notes=str(payload["uncertainty_notes"]),
            )
        )

    # --- policy replay schedule ------------------------------------------
    replay, policy_specs = _build_policy_replay(root, quarters, stage)

    # --- broadcast program -----------------------------------------------
    events = load_event_registry(root)
    program = _build_information_program(quarters, events, parameters)
    program_path = P04_INFORMATION_PROGRAM_PATH
    program_payload = _program_payload(program)
    program_digest = stage(program_path, _json_bytes(program_payload))
    rel_program = program_path

    # --- external pack ----------------------------------------------------
    values, meta = _external_values(root, profile, parameters, quarters)
    pack = {
        "schema_version": "1",
        "profile": profile,
        "source_id": P04_FIXTURE_SOURCE_ID,
        "locator": P04_FIXTURE_LOCATOR,
        "generated_at": P04_FIXTURE_GENERATED_AT,
        "warning": P04_WARNING,
        "quarters": quarters,
        "variables": {
            variable: {
                "unit": meta[variable]["unit"],
                "origin": meta[variable]["origin"],
                "evidence_status": meta[variable]["evidence_status"],
                "values": values[variable],
            }
            for variable in EXTERNAL_VARIABLE_IDS
        },
        "information_program": {"path": rel_program, "sha256": program_digest},
    }
    pack["pack_sha256"] = canonical_digest(pack)
    pack_rel = P04_SYNTHETIC_PACK_PATH if profile == "synthetic" else P04_HYBRID_PACK_PATH
    pack_digest = stage(pack_rel, _json_bytes(pack))

    # --- register artifacts and read back through the real gates ----------
    from hsm_lab.data.material import _append_artifact_manifest

    _append_artifact_manifest(root, [*parameter_specs, *policy_specs])
    reloaded = DataRegistry.load(root)
    for spec in parameter_specs:
        reloaded.validate_parameter(cast("ParameterArtifact", reloaded.artifacts[spec.artifact_id]))
    for spec in policy_specs:
        admitted = reloaded.artifacts[spec.artifact_id]
        if not isinstance(admitted, ForcingArtifact):  # pragma: no cover - declared policy_input
            raise ResearchGateError(f"policy artifact {spec.artifact_id} reloaded with wrong role")
        reloaded.load_policy_input(cast("ForcingArtifact", admitted))
    load_event_registry(root)

    return {
        "schema_version": "1",
        "profile": profile,
        "pack_path": pack_rel,
        "pack_sha256": pack_digest,
        "event_registry": P04_EVENT_REGISTRY_PATH,
        "replay_registry": P04_REPLAY_REGISTRY_PATH,
        "replay_schedule_sha256": replay["schedule_sha256"],
        "information_program": rel_program,
        "information_program_sha256": program_digest,
        "files": [{"path": rel, "sha256": digest} for rel, digest in files],
        "cache_hit": all(reused),
        "artifact_ids": [spec.artifact_id for spec in [*parameter_specs, *policy_specs]],
        "quarters": len(quarters),
    }


# ---------------------------------------------------------------------------
# Event registry
# ---------------------------------------------------------------------------


def load_event_registry(root: Path) -> EventRegistry:
    path = Path(root) / P04_EVENT_REGISTRY_PATH
    if not path.is_file():
        raise ResearchGateError(f"external event registry not found at {path}")
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema_version") != "1":
        raise ConfigError(f"{path}: expected top-level schema_version '1'")
    return EventRegistry.model_validate(doc)


# ---------------------------------------------------------------------------
# Policy replay (Mode A)
# ---------------------------------------------------------------------------


def _build_policy_replay(
    root: Path, quarters: list[str], stage: Any
) -> tuple[dict[str, Any], list[ForcingArtifact]]:
    path = root / P04_REPLAY_REGISTRY_PATH
    if not path.is_file():
        raise ResearchGateError(f"policy replay registry not found at {path}")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ConfigError(f"{path}: must be a mapping")
    registry = PolicyReplayRegistry.model_validate(doc.get("replay", doc))
    schedule = registry.compiled_schedule(tuple(quarters))
    schedule_sha = canonical_digest(schedule)

    specs: list[ForcingArtifact] = []
    for coordinate in POLICY_COORDINATES:
        variable_id = f"policy_{coordinate}"
        rel = f"{P04_POLICY_FIXTURE_DIR}/{variable_id}.parquet"
        frame = pl.DataFrame(
            {
                "variable_id": pl.Series([variable_id] * len(quarters), dtype=pl.String),
                "period": pl.Series(quarters, dtype=pl.String),
                "region_id": pl.Series([None] * len(quarters), dtype=pl.String),
                "commodity_id": pl.Series([None] * len(quarters), dtype=pl.String),
                "value": pl.Series(schedule[coordinate], dtype=pl.Float64),
                "unit": pl.Series(["dimensionless"] * len(quarters), dtype=pl.String),
            }
        ).sort("period")
        digest = stage(rel, _parquet_bytes(frame))
        specs.append(
            ForcingArtifact(
                artifact_id=f"p04_policy_{coordinate}",
                variable_id=variable_id,
                path=rel,
                provenance=Provenance(
                    variable=variable_id,
                    role=DataRole.EXOGENOUS_FORCING,
                    source_institution="HSM Lab local fixture",
                    dataset=P04_FIXTURE_DATASET,
                    locator=P04_FIXTURE_LOCATOR,
                    retrieved_at=_FIXTURE_GENERATED_AT_DT,
                    raw_sha256=digest,
                    original_frequency=Frequency.QUARTERLY,
                    model_frequency=Frequency.QUARTERLY,
                    transformation=Transformation(
                        method="synthetic_generation",
                        source_frequency=Frequency.QUARTERLY,
                        result_frequency=Frequency.QUARTERLY,
                        aggregation=None,
                        description=(
                            "Compiled Mode A domestic policy replay schedule; a declared "
                            "instrument path, never an observed outcome."
                        ),
                    ),
                    evidence_status=EvidenceStatus.STRUCTURAL_ASSUMPTION,
                    rights=_fixture_rights(),
                    notes=(
                        "Domestic policy replay schedule (fixture). 1968Q1 enterprise_autonomy="
                        "0.7 is an engineering structural assumption; only the 1968Q1 date "
                        "is source-confirmed."
                    ),
                    source_id=P04_FIXTURE_SOURCE_ID,
                    artifact_sha256=digest,
                ),
                source_id=P04_FIXTURE_SOURCE_ID,
                period=PeriodRange(
                    start=quarters[0], end=quarters[-1], frequency=Frequency.QUARTERLY
                ),
            )
        )
    return {"schedule_sha256": schedule_sha}, specs


def load_policy_replay(root: Path, rel: str) -> PolicyReplayRegistry:
    path = Path(root) / rel
    if not path.is_file():
        raise ResearchGateError(f"policy replay registry not found at {path}")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ConfigError(f"{path}: must be a mapping")
    return PolicyReplayRegistry.model_validate(doc.get("replay", doc))


def compile_policy_schedule(
    politics: PoliticalRunSpec, registry: DataRegistry, quarters: list[str]
) -> dict[str, list[float]]:
    """Recompile the Mode A schedule and cross-check the admitted parquet tables."""
    if not politics.replay_registry:
        raise ConfigError("Mode A requires a replay registry")
    replay = load_policy_replay(registry.root, politics.replay_registry)
    schedule = replay.compiled_schedule(tuple(quarters))
    for coordinate in POLICY_COORDINATES:
        artifact = registry.artifacts.get(f"p04_policy_{coordinate}")
        if not isinstance(artifact, ForcingArtifact):
            raise ResearchGateError(
                f"policy replay artifact p04_policy_{coordinate} is not registered; "
                "run 'hsm data build-p04-inputs'"
            )
        frame = registry.load_policy_input(artifact)
        by_quarter = dict(zip(frame["period"].to_list(), frame["value"].to_list(), strict=True))
        for index, quarter in enumerate(quarters):
            if (
                quarter not in by_quarter
                or abs(float(by_quarter[quarter]) - schedule[coordinate][index]) > 1e-9
            ):
                raise ResearchGateError(
                    f"policy replay mismatch for {coordinate} at {quarter}: admitted "
                    "parquet disagrees with the recompiled schedule"
                )
    return schedule


# ---------------------------------------------------------------------------
# Information program
# ---------------------------------------------------------------------------


def _program_payload(program: InformationProgram) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "messages": [
            {
                "message_id": message.message_id,
                "at_step": message.at_step,
                "ttl": message.ttl,
                "audience_all": message.audience_all,
                "region_ids": list(message.region_ids),
                "channel": message.channel,
                "intensity": message.intensity,
                "content_sensitivity": message.content_sensitivity,
                "content": message.content,
                "display_only": message.display_only,
            }
            for message in program.messages
        ],
    }


def _build_information_program(
    quarters: list[str], events: EventRegistry, parameters: PoliticalParameters
) -> InformationProgram:
    loading = parameters.external_recipe.default_loading
    messages: list[InformationMessage] = []
    for event in events.events:
        start_index = quarters.index(str(event.start))
        for channel in event.signal_channels:
            sensitivity = CHANNEL_CONTENT_SENSITIVITY.get(channel, 0.5)
            intensity = loading
            if event.event_id == "solidarity" and channel in SOLIDARITY_TOLERATED_CHANNELS:
                sensitivity = SOLIDARITY_TOLERATED_SENSITIVITY
            messages.append(
                InformationMessage(
                    message_id=f"{event.event_id}:{channel}",
                    at_step=start_index + 1,  # closing step of the event-start quarter
                    ttl=event.quarters(),
                    audience_all=True,
                    region_ids=(),
                    channel=channel,
                    intensity=float(intensity),
                    content_sensitivity=float(sensitivity),
                    content=event.event_id,
                    display_only=False,
                )
            )
    messages.sort(key=lambda message: (message.at_step, message.message_id))
    program_hash = canonical_digest(_program_payload(InformationProgram(tuple(messages), "")))
    return InformationProgram(tuple(messages), program_hash)


def load_information_program(root: Path, rel: str) -> InformationProgram:
    path = Path(root) / rel
    if not path.is_file():
        raise ResearchGateError(f"information program not found at {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != "1":
        raise ConfigError(f"{path}: expected schema_version '1'")
    messages: list[InformationMessage] = []
    for entry in payload.get("messages", []):
        channel = entry["channel"]
        if channel not in SIGNAL_CHANNELS:
            raise ConfigError(f"{path}: unknown broadcast channel {channel!r}")
        audience_all = bool(entry.get("audience_all"))
        region_ids = tuple(entry.get("region_ids", []))
        if audience_all and region_ids:
            raise ConfigError(f"{path}: message {entry['message_id']} selects all and regions")
        if not audience_all and not region_ids:
            raise ConfigError(f"{path}: message {entry['message_id']} selects no audience")
        messages.append(
            InformationMessage(
                message_id=entry["message_id"],
                at_step=int(entry["at_step"]),
                ttl=int(entry["ttl"]),
                audience_all=audience_all,
                region_ids=region_ids,
                channel=channel,
                intensity=float(entry["intensity"]),
                content_sensitivity=float(entry["content_sensitivity"]),
                content=str(entry.get("content", entry["message_id"])),
                display_only=bool(entry.get("display_only", False)),
            )
        )
    program_hash = canonical_digest(_program_payload(InformationProgram(tuple(messages), "")))
    return InformationProgram(tuple(messages), program_hash)


# ---------------------------------------------------------------------------
# Loaders used by the run
# ---------------------------------------------------------------------------


def load_external_pack(politics: PoliticalRunSpec, registry: DataRegistry) -> ExternalWorldPack:
    rel = politics.external_pack
    path = registry.resolve_path(rel)
    if not path.is_file():
        raise ResearchGateError(
            f"external pack {rel} not found at {path}; packs are never built or downloaded "
            "by a run (use 'hsm data build-p04-inputs')"
        )
    pack = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(pack, dict) or pack.get("schema_version") != "1":
        raise ResearchGateError(f"external pack {rel}: schema_version must be '1'")
    if pack.get("pack_sha256") != canonical_digest(
        {k: v for k, v in pack.items() if k != "pack_sha256"}
    ):
        raise ResearchGateError(f"external pack {rel}: pack_sha256 integrity gate failed")
    quarters = tuple(pack.get("quarters", ()))
    if not quarters:
        raise ResearchGateError(f"external pack {rel}: no quarters")
    variables = pack.get("variables")
    if not isinstance(variables, dict) or set(variables) != set(EXTERNAL_VARIABLE_IDS):
        raise ResearchGateError(
            f"external pack {rel}: variables must be exactly the 12 declared external ids"
        )
    ticks = len(quarters)
    values = np.full((ticks, len(EXTERNAL_VARIABLE_IDS)), np.nan, dtype=np.float64)
    origins: list[dict[str, str]] = []
    status: list[dict[str, str]] = []
    units: list[str] = []
    for index, variable in enumerate(EXTERNAL_VARIABLE_IDS):
        entry = variables[variable]
        series = entry.get("values")
        if not isinstance(series, list) or len(series) != ticks:
            raise ResearchGateError(
                f"external pack {rel}: variable {variable} must have one value per quarter"
            )
        for tick, value in enumerate(series):
            if value is None:
                if variable not in EXTERNAL_OPTIONAL_VARIABLES:
                    raise ResearchGateError(
                        f"external pack {rel}: variable {variable} has a missing value at "
                        f"{quarters[tick]} but is not declared optional"
                    )
                continue
            numeric = float(value)
            if not np.isfinite(numeric):
                raise ResearchGateError(
                    f"external pack {rel}: variable {variable} carries a non-finite value"
                )
            values[tick, index] = numeric
        units.append(str(entry["unit"]))
    for _tick in range(ticks):
        origins.append(
            {variable: str(variables[variable]["origin"]) for variable in EXTERNAL_VARIABLE_IDS}
        )
        status.append(
            {
                variable: str(variables[variable]["evidence_status"])
                for variable in EXTERNAL_VARIABLE_IDS
            }
        )
    program_info = pack.get("information_program")
    if not isinstance(program_info, dict) or not program_info.get("sha256"):
        raise ResearchGateError(f"external pack {rel}: information_program block is required")
    program_path = registry.resolve_path(str(program_info["path"]))
    if not program_path.is_file() or sha256_file(program_path) != program_info["sha256"]:
        raise ResearchGateError(
            f"external pack {rel}: information program digest mismatch for {program_info['path']}"
        )
    input_hashes = {
        f"{rel}": sha256_file(path),
        str(program_info["path"]): program_info["sha256"],
    }
    return ExternalWorldPack(
        quarters=quarters,
        variable_ids=EXTERNAL_VARIABLE_IDS,
        values=values,
        origins=origins,
        evidence_status=status,
        units=tuple(units),
        information_program_path=str(program_info["path"]),
        information_program_sha256=str(program_info["sha256"]),
        input_artifact_hashes=input_hashes,
        pack_hash=str(pack["pack_sha256"]),
    )


__all__ = [
    "CHANNEL_CONTENT_SENSITIVITY",
    "P04_EVENT_REGISTRY_PATH",
    "P04_FIXTURE_GENERATED_AT",
    "P04_FIXTURE_LOCATOR",
    "P04_FIXTURE_SOURCE_ID",
    "P04_HYBRID_PACK_PATH",
    "P04_INFORMATION_PROGRAM_PATH",
    "P04_POLICY_FIXTURE_DIR",
    "P04_REPLAY_REGISTRY_PATH",
    "P04_SYNTHETIC_PACK_PATH",
    "build_p04_inputs",
    "compile_policy_schedule",
    "load_event_registry",
    "load_external_pack",
    "load_information_program",
    "load_policy_replay",
    "register_p04_manifests",
]
