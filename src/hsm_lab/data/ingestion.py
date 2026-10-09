"""Download/cache orchestration for the first batch of audited sources.

Pipeline (MATERIAL_ECONOMY_EXPANSION_PLAN.md section 6):

1. rights gate - ``source.rights.download_allowed is True`` before any
   network call *and* before any cache read (a blocked FRED cannot be
   laundered through an old cache);
2. content-addressed cache - ``data/raw/<provider>/<full-sha256>/payload.<ext>``
   plus ``retrieval.json``; the index ``data/raw/cache-index.json`` maps the
   canonical request hash to the immutable content hash and is never an
   admission authority (the payload digest is recomputed on every read);
3. one standard-library GET per source (no retry, workers=1, 30s timeout,
   fixed UA), streamed under a hard payload cap;
4. fail-closed adapter parsing (see adapters.py);
5. normalized long-table parquet under ``data/observed/`` and artifact
   registration in ``data/manifests/artifacts.yml`` followed by a full
   ``DataRegistry.admit_artifact`` / role-loader read-back.

``--offline`` reads only hash-verified cache (a miss raises); ``--refresh``
downloads a new vintage (a changed hash creates a new content directory and
hash-suffixed artifacts; nothing is ever overwritten); the two flags
combined are a configuration error.
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import polars as pl
import yaml

from hsm_lab.contract.guards import sha256_file
from hsm_lab.contract.schemas import (
    ConfigError,
    DataRole,
    EvidenceStatus,
    Frequency,
    ResearchGateError,
    TargetUse,
)
from hsm_lab.data import adapters
from hsm_lab.data.adapters import ParsedSeries, SourceContentIncomplete
from hsm_lab.data.frequency import Aggregation, validate_period
from hsm_lab.data.registry import DataRegistry
from hsm_lab.data.schemas import (
    ROLE_FOR_SEMANTIC_KIND,
    ForcingArtifact,
    PeriodRange,
    Provenance,
    RightsSpec,
    TargetArtifact,
    Transformation,
)
from hsm_lab.provenance.manifest import canonical_digest

__all__ = [
    "ALLOWED_SOURCES",
    "CachedDownload",
    "IngestionReport",
    "IngestionRequest",
    "ingest_source",
]

USER_AGENT = "Mozilla/5.0 (compatible; hsm-lab-data-ingestion/0.1)"
_TIMEOUT_S = 30.0
_MAX_PAYLOAD_BYTES = 64 * 1024 * 1024  # streamed response cap (Fed archive ~4.1 MB)

# BASELINE §30.3: calibration ~1960-1969, internal validation ~1970-1978,
# hard hold-out 1979-1985; the reserved window 1986-1988 stays unleachable.
TARGET_USE_SPLITS: tuple[tuple[TargetUse, int, int], ...] = (
    (TargetUse.CALIBRATION, 1960, 1969),
    (TargetUse.VALIDATION, 1970, 1978),
    (TargetUse.HOLDOUT, 1979, 1985),
)

# Physical outcome series map onto the Intermediate-8 commodity ontology;
# indices, rates, FX and macro aggregates stay commodity-neutral (null).
COMMODITY_FOR_VARIABLE: dict[str, str] = {
    "industrial_electricity": "energy",
    "industrial_crude_steel": "raw_materials",
    "industrial_fertilizer": "raw_materials",
    "industrial_cement": "raw_materials",
    "industrial_television": "durable_goods",
    "ag_cereals": "food",
    "ag_wheat": "food",
    "ag_maize": "food",
}


@dataclass(frozen=True)
class IngestionRequest:
    """One ingestion job: a whitelisted source plus its requested window."""

    source_id: str
    start: str
    end: str
    offline: bool = False
    refresh: bool = False


@dataclass(frozen=True)
class CachedDownload:
    """A hash-verified raw payload plus its retrieval evidence."""

    raw_path: Path
    raw_sha256: str
    retrieved_at: datetime
    request_hash: str
    response_metadata: dict[str, Any]


@dataclass(frozen=True)
class IngestionReport:
    """Everything a caller needs to audit one completed ingestion."""

    source_id: str
    request: IngestionRequest
    request_hash: str
    cache_hit: bool
    downloaded: bool
    raw_sha256: str
    raw_path: Path
    retrieval_url: str
    retrieved_at: datetime
    response_metadata: dict[str, Any]
    variable_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    artifact_paths: tuple[str, ...]
    artifacts: tuple[dict[str, Any], ...] = field(default=())


@dataclass(frozen=True)
class _Provider:
    source_id: str
    payload_ext: str
    window: Frequency
    parser_version: str
    build_url: Callable[[IngestionRequest], str]
    parse: Callable[..., list[ParsedSeries]]


def _fixed_url(url: str) -> Callable[[IngestionRequest], str]:
    def build(_request: IngestionRequest) -> str:
        return url

    return build


def _fred_url(request: IngestionRequest) -> str:
    return (
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS"
        f"&cosd={request.start}-01&coed={request.end}-12"
    )


def _mnb_url(request: IngestionRequest) -> str:
    start = date.fromisoformat(request.start)
    end = date.fromisoformat(request.end)
    datefrom = f"{start.day:02d}%2F{start.month:02d}%2F{start.year}"
    datetill = f"{end.day:02d}%2F{end.month:02d}%2F{end.year}"
    return (
        "https://www.mnb.hu/en/arfolyam-tablazat?query&deviza=rbCurrencySelect"
        f"&devizaSelected=USD&datefrom={datefrom}&datetill={datetill}"
    )


_PROVIDERS: dict[str, _Provider] = {
    spec.source_id: spec
    for spec in (
        _Provider(
            "ksh_gdp",
            "csv",
            Frequency.ANNUAL,
            "ksh-gdp0002-csv-v1",
            _fixed_url("https://www.ksh.hu/stadat_files/gdp/en/gdp0002.csv"),
            adapters.parse_ksh_gdp_csv,
        ),
        _Provider(
            "ksh_industry",
            "csv",
            Frequency.ANNUAL,
            "ksh-ipa0002-csv-v1",
            _fixed_url("https://www.ksh.hu/stadat_files/ipa/en/ipa0002.csv"),
            adapters.parse_ksh_industry_csv,
        ),
        _Provider(
            "ksh_agriculture_b",
            "html",
            Frequency.ANNUAL,
            "ksh-homf001b-html-v1",
            _fixed_url(
                "https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001b.html"
            ),
            adapters.parse_ksh_agriculture_html,
        ),
        _Provider(
            "ksh_trade",
            "html",
            Frequency.ANNUAL,
            "ksh-hqkt001-html-v1",
            _fixed_url("https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_qkt001.html"),
            adapters.parse_ksh_trade_html,
        ),
        _Provider(
            "worldbank_pink_sheet",
            "xlsx",
            Frequency.MONTHLY,
            "wb-cmo-monthly-xlsx-v1",
            _fixed_url(
                "https://thedocs.worldbank.org/en/doc/"
                "5d903e848db1d1b83e0ec8f744e55570-0350012021/related/"
                "CMO-Historical-Data-Monthly.xlsx"
            ),
            adapters.parse_worldbank_pink_sheet_xlsx,
        ),
        _Provider(
            "federalreserve_h15",
            "zip",
            Frequency.MONTHLY,
            "frb-h15-xml-zip-v1",
            _fixed_url("https://www.federalreserve.gov/releases/h15/data/FRB_h15_xml.zip"),
            adapters.parse_fed_h15_zip,
        ),
        _Provider(
            "fred_fedfunds",
            "csv",
            Frequency.MONTHLY,
            "fred-fedfunds-csv-v1",
            _fred_url,
            adapters.parse_fred_fedfunds_csv,
        ),
        _Provider(
            "mnb_official_fx",
            "html",
            Frequency.DATED,
            "mnb-arfolyam-html-v1",
            _mnb_url,
            adapters.parse_mnb_fx_html,
        ),
    )
}

ALLOWED_SOURCES = frozenset(_PROVIDERS)


# ----------------------------------------------------------------------
# Request window handling
# ----------------------------------------------------------------------


def _window_kwargs(provider: _Provider, request: IngestionRequest) -> dict[str, Any]:
    validate_period(request.start, provider.window)
    validate_period(request.end, provider.window)
    if provider.window is Frequency.ANNUAL:
        if int(request.start) > int(request.end):
            raise ConfigError(
                f"source {provider.source_id}: inverted year window "
                f"{request.start}-{request.end}"
            )
        return {"start_year": int(request.start), "end_year": int(request.end)}
    if provider.window is Frequency.MONTHLY:
        if request.start > request.end:
            raise ConfigError(
                f"source {provider.source_id}: inverted month window "
                f"{request.start}..{request.end}"
            )
        return {"start_month": request.start, "end_month": request.end}
    if request.start > request.end:
        raise ConfigError(
            f"source {provider.source_id}: inverted date window "
            f"{request.start}..{request.end}"
        )
    return {"start_date": request.start, "end_date": request.end}


def _request_hash(url: str) -> str:
    return canonical_digest({"method": "GET", "url": url, "body_sha256": None})


# ----------------------------------------------------------------------
# Cache index and immutable content directories
# ----------------------------------------------------------------------


def _cache_index_path(root: Path) -> Path:
    return root / "data" / "raw" / "cache-index.json"


def _load_cache_index(root: Path) -> dict[str, str]:
    path = _cache_index_path(root)
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ResearchGateError(f"unreadable cache index {path}: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema_version") != "1":
        raise ResearchGateError(f"cache index {path}: expected schema_version '1'")
    entries = doc.get("entries", {})
    if not isinstance(entries, dict):
        raise ResearchGateError(f"cache index {path}: 'entries' must be a mapping")
    return dict(entries)


def _write_cache_index(root: Path, entries: dict[str, str]) -> None:
    path = _cache_index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"schema_version": "1", "entries": entries}, indent=1, sort_keys=True
    )
    _atomic_write(path, (payload + "\n").encode("utf-8"))


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _content_dir(root: Path, provider: _Provider, content_sha256: str) -> Path:
    return root / "data" / "raw" / provider.source_id / content_sha256


def _read_retrieval(root: Path, provider: _Provider, content_sha256: str) -> dict[str, Any]:
    path = _content_dir(root, provider, content_sha256) / "retrieval.json"
    try:
        doc: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ResearchGateError(f"unreadable retrieval metadata {path}: {exc}") from exc
    if doc.get("raw_sha256") != content_sha256:
        raise ResearchGateError(
            f"retrieval metadata {path} disagrees with its own content hash"
        )
    return doc


def _lookup_cache(
    root: Path, provider: _Provider, request_hash: str
) -> CachedDownload | None:
    """Return the hash-verified cached payload, or None on any miss.

    The index is only a hint: the raw payload digest is always recomputed,
    and a mismatching or unreadable entry is a miss, never an authority.
    """
    entries = _load_cache_index(root)
    content_sha = entries.get(request_hash)
    if content_sha is None:
        return None
    payload = _content_dir(root, provider, content_sha) / f"payload.{provider.payload_ext}"
    if not payload.is_file():
        return None
    try:
        digest = sha256_file(payload)
    except OSError:
        return None
    if digest != content_sha:
        return None
    try:
        retrieval = _read_retrieval(root, provider, content_sha)
    except ResearchGateError:
        return None
    response = retrieval.get("response", {})
    return CachedDownload(
        raw_path=payload,
        raw_sha256=digest,
        retrieved_at=_parse_utc(retrieval["retrieved_at_utc"]),
        request_hash=request_hash,
        response_metadata=dict(response),
    )


def _parse_utc(text: str) -> datetime:
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ResearchGateError(f"retrieval timestamp {text!r} is not UTC-qualified")
    return parsed


# ----------------------------------------------------------------------
# Download (single attempt, streamed, capped)
# ----------------------------------------------------------------------


def _download(
    root: Path, provider: _Provider, url: str, request_hash: str
) -> CachedDownload:
    raw_dir = root / "data" / "raw" / provider.source_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
            status = getattr(response, "status", 200)
            final_url = response.geturl()
            headers = {key.lower(): value for key, value in response.headers.items()}
            fd, tmp_name = tempfile.mkstemp(dir=raw_dir, prefix=".download-", suffix=".tmp")
            tmp = Path(tmp_name)
            size = 0
            with os.fdopen(fd, "wb") as handle:
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > _MAX_PAYLOAD_BYTES:
                        handle.close()
                        tmp.unlink(missing_ok=True)
                        raise ResearchGateError(
                            f"source {provider.source_id}: payload exceeded the "
                            f"{_MAX_PAYLOAD_BYTES} byte streaming cap after {size} "
                            "bytes; refusing to store it"
                        )
                    handle.write(chunk)
    except urllib.error.HTTPError as exc:
        raise ResearchGateError(
            f"source {provider.source_id}: HTTP {exc.code} for {url}; "
            "no retry, no mirror fallback"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ResearchGateError(
            f"source {provider.source_id}: request failed for {url}: {exc}; "
            "no retry, no mirror fallback"
        ) from exc

    digest = sha256_file(tmp)
    content_dir = _content_dir(root, provider, digest)
    payload_path = content_dir / f"payload.{provider.payload_ext}"
    if payload_path.is_file():
        # Immutable path already holds these exact bytes; never overwrite.
        existing = sha256_file(payload_path)
        if existing != digest:
            raise ResearchGateError(
                f"source {provider.source_id}: content collision at {payload_path} "
                f"(existing {existing}, downloaded {digest})"
            )
        tmp.unlink(missing_ok=True)
        try:
            prior = _read_retrieval(root, provider, digest)
        except ResearchGateError:
            prior = None
        if prior is not None:
            # Refresh with an unchanged hash reuses the original artifact:
            # retrieved_at is never rewritten by access time.
            entries = _load_cache_index(root)
            entries[request_hash] = digest
            _write_cache_index(root, entries)
            return CachedDownload(
                raw_path=payload_path,
                raw_sha256=digest,
                retrieved_at=_parse_utc(prior["retrieved_at_utc"]),
                request_hash=request_hash,
                response_metadata=dict(prior.get("response", {})),
            )
    else:
        content_dir.mkdir(parents=True, exist_ok=True)
        os.replace(tmp, payload_path)

    retrieved_at = datetime.now(UTC)
    retrieval: dict[str, Any] = {
        "schema_version": "1",
        "source_id": provider.source_id,
        "request": {
            "method": "GET",
            "url": url,
            "body_sha256": None,
            "request_hash": request_hash,
        },
        "retrieved_at_utc": retrieved_at.isoformat(),
        "response": {
            "status": status,
            "final_url": final_url,
            "content_type": headers.get("content-type"),
            "content_length": headers.get("content-length"),
            "etag": headers.get("etag"),
            "last_modified": headers.get("last-modified"),
            "payload_bytes": size,
        },
        "raw_sha256": digest,
        "payload_file": payload_path.name,
        "dataset": _source_dataset(root, provider.source_id),
        "rights_evidence": _rights_evidence(root, provider.source_id),
    }
    _atomic_write(
        content_dir / "retrieval.json",
        (json.dumps(retrieval, indent=1, sort_keys=True) + "\n").encode("utf-8"),
    )
    entries = _load_cache_index(root)
    entries[request_hash] = digest
    _write_cache_index(root, entries)
    return CachedDownload(
        raw_path=payload_path,
        raw_sha256=digest,
        retrieved_at=retrieved_at,
        request_hash=request_hash,
        response_metadata=dict(retrieval["response"]),
    )


def _source_dataset(root: Path, source_id: str) -> str | None:
    registry = DataRegistry.load(root)
    source = registry.sources.get(source_id)
    return source.dataset if source else None


def _rights_evidence(root: Path, source_id: str) -> dict[str, Any]:
    registry = DataRegistry.load(root)
    source = registry.sources.get(source_id)
    if source is None:
        return {}
    rights: RightsSpec = source.rights
    return rights.model_dump(mode="json")


# ----------------------------------------------------------------------
# Normalization and artifact registration
# ----------------------------------------------------------------------


def _long_frame(series: ParsedSeries, commodity_id: str | None) -> pl.DataFrame:
    periods = [period for period, _ in series.rows]
    values = [value for _, value in series.rows]
    frame = pl.DataFrame(
        {
            "variable_id": pl.Series([series.variable_id] * len(periods), dtype=pl.String),
            "period": pl.Series(periods, dtype=pl.String),
            "region_id": pl.Series([None] * len(periods), dtype=pl.String),
            "commodity_id": pl.Series([commodity_id] * len(periods), dtype=pl.String),
            "value": pl.Series(values, dtype=pl.Float64),
            "unit": pl.Series([series.unit] * len(periods), dtype=pl.String),
        }
    )
    return frame.sort("period")


def _role_dir(role: DataRole) -> str:
    return "external_forcing" if role is DataRole.EXOGENOUS_FORCING else "targets"


def _split_windows(
    role: DataRole, request: IngestionRequest
) -> list[tuple[str, str, TargetUse | None]]:
    if role is not DataRole.TARGET:
        return [(request.start, request.end, None)]
    start_year, end_year = int(request.start), int(request.end)
    windows: list[tuple[str, str, TargetUse | None]] = []
    for use, split_start, split_end in TARGET_USE_SPLITS:
        lo, hi = max(start_year, split_start), min(end_year, split_end)
        if lo <= hi:
            windows.append((str(lo), str(hi), use))
    return windows


def _transformation(series: ParsedSeries, parser_version: str) -> Transformation:
    return Transformation(
        method="identity",
        source_frequency=series.frequency,
        result_frequency=series.frequency,
        aggregation=None,
        description=(
            f"identity normalization of the audited source table by parser "
            f"{parser_version}; no frequency change, no imputation"
        ),
    )


def _transform_hash(transformation: Transformation, parser_version: str) -> str:
    return canonical_digest(
        {"parser_version": parser_version, "transformation": transformation.model_dump(mode="json")}
    )


def _build_artifacts(
    root: Path,
    registry: DataRegistry,
    provider: _Provider,
    request: IngestionRequest,
    series_list: list[ParsedSeries],
    raw_sha256: str,
    raw_rel_path: str,
    retrieved_at: datetime,
) -> list[ForcingArtifact | TargetArtifact]:
    source = registry.sources[provider.source_id]
    specs: list[ForcingArtifact | TargetArtifact] = []
    for series in series_list:
        variable = registry.variables.get(series.variable_id)
        if variable is None:
            raise ConfigError(
                f"source {provider.source_id}: parser emitted unknown variable "
                f"{series.variable_id!r}; declare it in variables.yml first"
            )
        if variable.unit != series.unit:
            raise ConfigError(
                f"source {provider.source_id}: variable {series.variable_id} declares "
                f"unit {variable.unit!r} but the audited parser emits {series.unit!r}"
            )
        declared_frequency = variable.original_frequency
        if declared_frequency != series.frequency:
            declared_label = declared_frequency.value if declared_frequency is not None else None
            raise ConfigError(
                f"source {provider.source_id}: variable {series.variable_id} declares "
                f"{declared_label} but the parser emits "
                f"{series.frequency.value}"
            )
        role = ROLE_FOR_SEMANTIC_KIND[variable.semantic_kind]
        transformation = _transformation(series, provider.parser_version)
        transform_hash = _transform_hash(transformation, provider.parser_version)
        commodity = COMMODITY_FOR_VARIABLE.get(series.variable_id)
        for win_start, win_end, use in _split_windows(role, request):
            rows = [r for r in series.rows if win_start <= r[0] <= win_end]
            if not rows:
                continue
            artifact_id = (
                f"{series.variable_id}__{provider.source_id}__{win_start}__{win_end}"
                f"__{raw_sha256[:12]}__{transform_hash[:12]}"
            )
            rel_dir = (
                f"data/observed/{_role_dir(role)}/{provider.source_id}/{raw_sha256}"
            )
            rel_path = (
                f"{rel_dir}/{series.variable_id}_{win_start}_{win_end}_"
                f"{transform_hash}.parquet"
            )
            frame = _long_frame(
                ParsedSeries(
                    variable_id=series.variable_id,
                    unit=series.unit,
                    frequency=series.frequency,
                    rows=tuple(rows),
                ),
                commodity,
            )
            path = root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.write_parquet(path)
            artifact_sha256 = sha256_file(path)
            provenance = Provenance(
                variable=series.variable_id,
                role=role,
                source_institution=source.institution,
                dataset=source.dataset,
                locator=source.locator,
                retrieved_at=retrieved_at,
                raw_sha256=raw_sha256,
                original_frequency=series.frequency,
                model_frequency=series.frequency,
                transformation=transformation,
                evidence_status=EvidenceStatus.OBSERVED,
                rights=source.rights.model_copy(deep=True),
                notes=(
                    f"first-batch observed ingestion; normalized from "
                    f"{raw_rel_path} by parser {provider.parser_version}; "
                    "national series (region_id null)"
                ),
                source_id=provider.source_id,
                source_period=f"{win_start}..{win_end}",
                raw_path=raw_rel_path,
                derived_from=[],
                artifact_sha256=artifact_sha256,
            )
            if role is DataRole.TARGET:
                assert use is not None
                specs.append(
                    TargetArtifact(
                        artifact_id=artifact_id,
                        variable_id=series.variable_id,
                        path=rel_path,
                        provenance=provenance,
                        source_id=provider.source_id,
                        observed_period=PeriodRange(
                            start=win_start, end=win_end, frequency=series.frequency
                        ),
                        use=use,
                        comparison_aggregation=cast(Aggregation, variable.aggregation),
                    )
                )
            else:
                specs.append(
                    ForcingArtifact(
                        artifact_id=artifact_id,
                        variable_id=series.variable_id,
                        path=rel_path,
                        provenance=provenance,
                        source_id=provider.source_id,
                        period=PeriodRange(
                            start=win_start, end=win_end, frequency=series.frequency
                        ),
                    )
                )
    return specs


def _append_artifact_manifest(root: Path, specs: list[Any]) -> None:
    path = root / "data" / "manifests" / "artifacts.yml"
    if not path.is_file():
        raise ResearchGateError(f"artifact manifest not found: {path}")
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema_version") != "1":
        raise ConfigError(f"{path}: expected top-level schema_version '1'")
    entries = doc.get("artifacts")
    if not isinstance(entries, list):
        raise ConfigError(f"{path}: expected a top-level 'artifacts' list")
    existing = {entry.get("artifact_id"): entry for entry in entries if isinstance(entry, dict)}
    changed = False
    for spec in specs:
        dump = spec.model_dump(mode="json")
        if spec.artifact_id in existing:
            if existing[spec.artifact_id] != dump:
                raise ResearchGateError(
                    f"artifact {spec.artifact_id}: registry entry exists with different "
                    "content; artifact ids are immutable - a changed transformation or "
                    "raw source must produce a new hash-suffixed id (exit 1)"
                )
            continue
        entries.append(dump)
        existing[spec.artifact_id] = dump
        changed = True
    if changed:
        _atomic_write(
            path,
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100).encode("utf-8"),
        )


# ----------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------


def ingest_source(root: Path, request: IngestionRequest) -> IngestionReport:
    """Ingest one whitelisted source end-to-end and register its artifacts."""
    if request.offline and request.refresh:
        raise ConfigError("--offline and --refresh are mutually exclusive")
    provider = _PROVIDERS.get(request.source_id)
    if provider is None:
        raise ConfigError(
            f"unknown ingestion source {request.source_id!r}; allowlist: "
            f"{sorted(_PROVIDERS)}"
        )
    window = _window_kwargs(provider, request)

    # Rights gate: before any network call AND before any cache read. A
    # blocked source (FRED) cannot be laundered through a stale cache.
    registry = DataRegistry.load(root)
    source = registry.sources.get(request.source_id)
    if source is None:
        raise ConfigError(
            f"source {request.source_id} is ingestable but missing from "
            "data/manifests/sources.yml"
        )
    if source.rights.download_allowed is not True:
        raise ResearchGateError(
            f"rights-blocked: source {request.source_id} has download_allowed="
            f"{source.rights.download_allowed!r} (license_status="
            f"{source.rights.license_status}); no network call and no cache read "
            "was performed - a public-domain tag or user flag cannot override "
            "the gate"
        )

    url = provider.build_url(request)
    request_hash = _request_hash(url)

    cached = _lookup_cache(root, provider, request_hash)
    downloaded = False
    if cached is not None and not request.refresh:
        payload = cached
    else:
        if request.offline:
            raise ResearchGateError(
                f"offline cache miss for source {request.source_id} "
                f"(request_hash {request_hash}); no network access is attempted "
                "in offline mode (exit 1)"
            )
        payload = _download(root, provider, url, request_hash)
        downloaded = True

    series_list = provider.parse(payload.raw_path, **window)
    if not series_list:
        raise SourceContentIncomplete(
            request.source_id, "parser produced no series; nothing to register"
        )

    raw_rel = str(payload.raw_path.relative_to(root))
    specs = _build_artifacts(
        root,
        registry,
        provider,
        request,
        series_list,
        payload.raw_sha256,
        raw_rel,
        payload.retrieved_at,
    )
    _append_artifact_manifest(root, specs)

    # Read-back validation through the real registry gates (role, rights,
    # window, digests, long-table structure and payload metadata).
    reloaded = DataRegistry.load(root)
    for spec in specs:
        admitted = reloaded.artifacts.get(spec.artifact_id)
        if admitted is None:
            raise ResearchGateError(
                f"artifact {spec.artifact_id} missing from reloaded registry"
        )
        if isinstance(spec, TargetArtifact):
            if spec.use is TargetUse.HOLDOUT:
                # Ingestion may verify the admitted bytes and metadata, but
                # read-back validation must not materialize protected values.
                reloaded.admit_artifact(cast(TargetArtifact, admitted), numeric=False)
            else:
                reloaded.load_targets(cast(TargetArtifact, admitted), spec.use)
        else:
            reloaded.load_forcing(cast(ForcingArtifact, admitted))

    return IngestionReport(
        source_id=request.source_id,
        request=request,
        request_hash=request_hash,
        cache_hit=cached is not None and not request.refresh,
        downloaded=downloaded,
        raw_sha256=payload.raw_sha256,
        raw_path=payload.raw_path,
        retrieval_url=url,
        retrieved_at=payload.retrieved_at,
        response_metadata=payload.response_metadata,
        variable_ids=tuple(s.variable_id for s in series_list),
        artifact_ids=tuple(spec.artifact_id for spec in specs),
        artifact_paths=tuple(spec.path for spec in specs),
        artifacts=tuple(spec.model_dump(mode="json") for spec in specs),
    )
