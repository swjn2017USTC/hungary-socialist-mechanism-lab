from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypeVar

import polars as pl
import yaml
from pydantic import TypeAdapter, ValidationError

from hsm_lab.contract.guards import load_research_contract, sha256_file
from hsm_lab.contract.schemas import (
    ConfigError,
    EvidenceStatus,
    Frequency,
    ResearchContract,
    ResearchGateError,
    TargetUse,
)
from hsm_lab.data.frequency import validate_period
from hsm_lab.data.schemas import (
    RECONSTRUCTED_ONLY_VARIABLES,
    ROLE_FOR_SEMANTIC_KIND,
    ArtifactSpec,
    ForcingArtifact,
    InitialArtifact,
    ParameterArtifact,
    ParameterPriorFile,
    Provenance,
    SourceSpec,
    TargetArtifact,
    VariableSpec,
)

_ARTIFACT_ADAPTER: TypeAdapter[ArtifactSpec] = TypeAdapter(ArtifactSpec)
DERIVED_METHODS = frozenset(
    {"monthly_to_quarterly", "quarterly_to_annual", "anchor_reconstruction", "literature_prior"}
)
_LONG_COLUMNS: list[tuple[str, Any]] = [
    ("variable_id", pl.String),
    ("period", pl.String),
    ("region_id", pl.String),
    ("commodity_id", pl.String),
    ("value", pl.Float64),
    ("unit", pl.String),
]

A = TypeVar("A", bound=ArtifactSpec)


def _read_yaml_doc(path: Path, key: str) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ResearchGateError(f"data manifest not found: {path}")
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema_version") != "1":
        raise ConfigError(f"{path}: expected top-level schema_version '1'")
    entries = doc.get(key)
    if not isinstance(entries, list):
        raise ConfigError(f"{path}: expected a top-level '{key}' list")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ConfigError(f"{path}: every {key[:-1]} entry must be a mapping")
    return entries


def _index_by_id(items: Sequence[Any], id_attr: str, manifest: str) -> dict[str, Any]:
    index: dict[str, Any] = {}
    for item in items:
        key = getattr(item, id_attr)
        if key in index:
            raise ConfigError(f"{manifest}: duplicate id {key!r}")
        index[key] = item
    return index


def _assert_no_cycles(artifacts: dict[str, ArtifactSpec]) -> None:
    def visit(node: str, stack: list[str]) -> None:
        if node in stack:
            cycle = stack[stack.index(node) :] + [node]
            raise ConfigError(f"derived_from cycle in artifact registry: {' -> '.join(cycle)}")
        deps = artifacts[node].provenance.derived_from
        for dep in deps:
            if dep not in artifacts:
                raise ConfigError(
                    f"artifact {node}: derived_from references unknown artifact {dep!r}"
                )
            visit(dep, stack + [node])

    for artifact_id in artifacts:
        visit(artifact_id, [])


class DataRegistry:
    """Loaded, cross-checked data manifests pinned to one repo root."""

    def __init__(
        self,
        root: Path,
        contract: ResearchContract,
        sources: dict[str, SourceSpec],
        variables: dict[str, VariableSpec],
        artifacts: dict[str, ArtifactSpec],
        extra_roots: tuple[Path, ...] = (),
    ) -> None:
        self.root = root
        self.contract = contract
        self.sources = sources
        self.variables = variables
        self.artifacts = artifacts
        self.extra_roots = extra_roots

    @classmethod
    def load(cls, root: Path, *, extra_roots: Sequence[Path] = ()) -> DataRegistry:
        contract = load_research_contract(root)
        manifests = root / "data" / "manifests"
        try:
            sources_list = [
                SourceSpec.model_validate(entry)
                for entry in _read_yaml_doc(manifests / "sources.yml", "sources")
            ]
            variables_list = [
                VariableSpec.model_validate(entry)
                for entry in _read_yaml_doc(manifests / "variables.yml", "variables")
            ]
            artifacts_list = [
                _ARTIFACT_ADAPTER.validate_python(entry)
                for entry in _read_yaml_doc(manifests / "artifacts.yml", "artifacts")
            ]
        except ValidationError as exc:
            raise ConfigError(f"invalid data manifest under {manifests}:\n{exc}") from exc
        sources = _index_by_id(sources_list, "source_id", "sources.yml")
        variables = _index_by_id(variables_list, "variable_id", "variables.yml")
        artifacts = _index_by_id(artifacts_list, "artifact_id", "artifacts.yml")
        _assert_no_cycles(artifacts)
        for artifact in artifacts.values():
            if artifact.source_id not in sources:
                raise ConfigError(
                    f"artifact {artifact.artifact_id} references unknown source "
                    f"{artifact.source_id!r}"
                )
            if artifact.variable_id not in variables:
                raise ConfigError(
                    f"artifact {artifact.artifact_id} references unknown variable "
                    f"{artifact.variable_id!r}"
                )
            if isinstance(artifact, InitialArtifact):
                for anchor in artifact.anchor_ids:
                    if anchor not in artifacts:
                        raise ConfigError(
                            f"artifact {artifact.artifact_id} references unknown anchor "
                            f"{anchor!r}"
                        )
        return cls(root, contract, sources, variables, artifacts, tuple(extra_roots))

    def resolve_path(self, rel: str) -> Path:
        """Resolve a repo-relative artifact path inside declared roots only."""
        candidate = self.root / rel
        resolved = candidate.resolve()
        for base in (self.root / "data", *self.extra_roots):
            base_resolved = base.resolve()
            if resolved == base_resolved or base_resolved in resolved.parents:
                return resolved
        raise ResearchGateError(
            f"artifact path {rel!r} escapes the declared data/fixture roots"
        )

    # ------------------------------------------------------------------
    # Admission: role/semantic -> rights -> window -> digest, then read.
    # ------------------------------------------------------------------
    def admit_artifact(
        self,
        artifact: A,
        *,
        numeric: bool = True,
        purpose: TargetUse | None = None,
    ) -> Path:
        aid = artifact.artifact_id
        source = self.sources.get(artifact.source_id)
        if source is None:
            raise ResearchGateError(f"artifact {aid}: unknown source {artifact.source_id!r}")
        if artifact.role not in source.expected_roles:
            raise ResearchGateError(
                f"artifact {aid}: source {source.source_id} does not offer role "
                f"{artifact.role.value}"
            )
        variable = self.variables.get(artifact.variable_id)
        if variable is None:
            raise ResearchGateError(
                f"artifact {aid}: unknown variable {artifact.variable_id!r}"
            )
        expected_role = ROLE_FOR_SEMANTIC_KIND[variable.semantic_kind]
        if artifact.role is not expected_role:
            raise ResearchGateError(
                f"artifact {aid}: variable {variable.variable_id} has semantic_kind "
                f"{variable.semantic_kind.value}; it cannot enter the runtime as "
                f"{artifact.role.value} (input != target != parameter)"
            )
        prov = artifact.provenance
        if prov.rights.license_status != source.rights.license_status:
            raise ResearchGateError(
                f"artifact {aid}: provenance rights drift versus source rights "
                f"({prov.rights.license_status} != {source.rights.license_status})"
            )
        if prov.evidence_status is EvidenceStatus.SYNTHETIC_FIXTURE:
            if not prov.locator.startswith("fixture:"):
                raise ResearchGateError(
                    f"artifact {aid}: synthetic_fixture provenance must carry a fixture: URI"
                )
        elif source.rights.download_allowed is not True:
            raise ResearchGateError(
                f"artifact {aid}: real-data admission requires verified download permission; "
                f"source {source.source_id} has download_allowed="
                f"{source.rights.download_allowed!r}"
            )
        if (
            artifact.variable_id in RECONSTRUCTED_ONLY_VARIABLES
            and prov.evidence_status is not EvidenceStatus.RECONSTRUCTED
        ):
            raise ResearchGateError(
                f"artifact {aid}: variable {artifact.variable_id} is reconstruction-only "
                "(CMEA energy price can never be observed)"
            )
        if isinstance(artifact, TargetArtifact):
            self._admit_target(artifact, numeric=numeric, purpose=purpose)

        path = self.resolve_path(artifact.path)
        if not path.is_file():
            raise ResearchGateError(f"artifact {aid}: file not found at {path}")
        digest = sha256_file(path)
        if prov.artifact_sha256 is None or digest != prov.artifact_sha256:
            raise ResearchGateError(
                f"artifact {aid}: content digest mismatch for {path} "
                f"(declared {prov.artifact_sha256}, computed {digest})"
            )
        raw_rel = prov.raw_path if prov.raw_path is not None else artifact.path
        if raw_rel != artifact.path:
            raw_path = self.resolve_path(raw_rel)
            if not raw_path.is_file():
                raise ResearchGateError(f"artifact {aid}: raw file not found at {raw_path}")
            if prov.raw_sha256 is None or sha256_file(raw_path) != prov.raw_sha256:
                raise ResearchGateError(f"artifact {aid}: raw digest mismatch for {raw_path}")
        elif prov.raw_sha256 is not None and prov.raw_sha256 != digest:
            raise ResearchGateError(
                f"artifact {aid}: raw digest differs while raw_path equals artifact path"
            )
        return path

    def _admit_target(
        self, artifact: TargetArtifact, *, numeric: bool, purpose: TargetUse | None
    ) -> None:
        aid = artifact.artifact_id
        if purpose is not None:
            if purpose is TargetUse.RESERVED:
                raise ResearchGateError(
                    f"target {aid}: reserved outcomes are never numerically loaded "
                    "(hold-out gate, BASELINE §37)"
                )
            if artifact.use is not purpose:
                raise ResearchGateError(
                    f"target {aid}: declared use {artifact.use.value} does not match requested "
                    f"purpose {purpose.value}; calibration may not consume "
                    "validation/holdout/reserved targets"
                )
        if not numeric:
            return
        if artifact.use is TargetUse.RESERVED:
            raise ResearchGateError(
                f"target {aid}: reserved outcomes are never numerically loaded (hold-out gate)"
            )
        first, last = artifact.observed_period.year_span()
        reserved_first = self.contract.reserved_start.year
        reserved_last = self.contract.reserved_end.year
        if not (last < reserved_first or first > reserved_last):
            raise ResearchGateError(
                f"target {aid}: observed_period {artifact.observed_period.start}.."
                f"{artifact.observed_period.end} touches the reserved window "
                f"{self.contract.reserved_start}..{self.contract.reserved_end}"
            )
        variable = self.variables[artifact.variable_id]
        if (
            variable.original_frequency is not None
            and artifact.observed_period.frequency is not variable.original_frequency
        ):
            raise ResearchGateError(
                f"target {aid}: variable {variable.variable_id} declares "
                f"{variable.original_frequency.value} observations; artifact claims "
                f"{artifact.observed_period.frequency.value}"
            )

    # ------------------------------------------------------------------
    # Role-specific loaders (the only ways data enters the runtime).
    # ------------------------------------------------------------------
    def _expected_table_frequency(self, prov: Provenance) -> Frequency:
        if prov.transformation.method in DERIVED_METHODS:
            return prov.model_frequency
        return prov.original_frequency

    def _read_long_table(
        self, artifact: ArtifactSpec, path: Path, expected_frequency: Frequency
    ) -> pl.DataFrame:
        frame = pl.read_parquet(path)
        wanted = [name for name, _ in _LONG_COLUMNS]
        if frame.columns != wanted:
            raise ResearchGateError(
                f"artifact {artifact.artifact_id}: long-table columns must be exactly "
                f"{wanted}, got {frame.columns}"
            )
        for name, dtype in _LONG_COLUMNS:
            if frame.schema[name] != dtype:
                raise ResearchGateError(
                    f"artifact {artifact.artifact_id}: column {name} must be {dtype}, "
                    f"got {frame.schema[name]}"
                )
        variables = frame["variable_id"].unique().to_list()
        if variables != [artifact.variable_id]:
            raise ResearchGateError(
                f"artifact {artifact.artifact_id}: file must contain exactly its own "
                f"variable_id, got {variables}"
            )
        units = frame["unit"].unique().to_list()
        if len(units) != 1:
            raise ResearchGateError(
                f"artifact {artifact.artifact_id}: inconsistent units {units}"
            )
        bad_regions = [
            region
            for region in frame["region_id"].drop_nulls().unique().to_list()
            if region not in self.contract.region_ids
        ]
        if bad_regions:
            raise ResearchGateError(
                f"artifact {artifact.artifact_id}: unknown region ids {sorted(bad_regions)}"
            )
        bad_commodities = [
            commodity
            for commodity in frame["commodity_id"].drop_nulls().unique().to_list()
            if not commodity
        ]
        if bad_commodities:
            raise ResearchGateError(
                f"artifact {artifact.artifact_id}: empty commodity ids are not allowed"
            )
        missing = frame["value"].null_count()
        if missing and not artifact.allow_missing:
            raise ResearchGateError(
                f"artifact {artifact.artifact_id}: {missing} missing values but "
                "allow_missing is False (missing values are never filled with zeros)"
            )
        non_null = frame.filter(pl.col("value").is_not_null())
        if non_null.height:
            if not non_null["value"].is_finite().all():
                raise ResearchGateError(
                    f"artifact {artifact.artifact_id}: non-finite values are rejected"
                )
        for period in frame["period"].to_list():
            validate_period(period, expected_frequency)
        duplicated = (
            frame.group_by(["variable_id", "period", "region_id", "commodity_id"])
            .len()
            .filter(pl.col("len") > 1)
        )
        if duplicated.height:
            raise ResearchGateError(
                f"artifact {artifact.artifact_id}: duplicate primary keys "
                f"(variable_id, period, region_id, commodity_id): "
                f"{duplicated.head(3).to_dicts()}"
            )
        return frame

    def load_forcing(self, artifact: ForcingArtifact) -> pl.DataFrame:
        path = self.admit_artifact(artifact, numeric=True)
        return self._read_long_table(
            artifact, path, self._expected_table_frequency(artifact.provenance)
        )

    def load_initial(self, artifact: InitialArtifact) -> pl.DataFrame:
        path = self.admit_artifact(artifact, numeric=True)
        return self._read_long_table(
            artifact, path, self._expected_table_frequency(artifact.provenance)
        )

    def load_targets(self, artifact: TargetArtifact, purpose: TargetUse) -> pl.DataFrame:
        path = self.admit_artifact(artifact, numeric=True, purpose=purpose)
        return self._read_long_table(
            artifact, path, artifact.provenance.original_frequency
        )

    def validate_parameter(self, artifact: ParameterArtifact) -> dict[str, object]:
        """Validate an auditable prior declaration; never a calibrated value."""
        path = self.admit_artifact(artifact, numeric=False)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ResearchGateError(
                f"artifact {artifact.artifact_id}: unreadable prior declaration: {exc}"
            ) from exc
        try:
            prior = ParameterPriorFile.model_validate(payload)
        except ValidationError as exc:
            raise ResearchGateError(
                f"artifact {artifact.artifact_id}: invalid prior declaration:\n{exc}"
            ) from exc
        if prior.schema_version != "1":
            raise ResearchGateError(
                f"artifact {artifact.artifact_id}: prior file schema_version must be '1'"
            )
        if prior.variable_id != artifact.variable_id:
            raise ResearchGateError(
                f"artifact {artifact.artifact_id}: prior file variable_id mismatch"
            )
        if prior.calibration_status != artifact.calibration_status or (
            prior.sensitivity_status != artifact.sensitivity_status
        ):
            raise ResearchGateError(
                f"artifact {artifact.artifact_id}: prior file status fields disagree with "
                "the registry declaration"
            )
        return dict(payload)


