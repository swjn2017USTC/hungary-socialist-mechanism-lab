"""H6B strict research-package audit and safe export.

This module is deliberately separate from the legacy evidence schemas.  It reads
only metadata and already-produced study artifacts, derives the eleven H6B
package checks per mechanism card, and writes a deterministic JSON/Markdown
export.  It never promotes ``research_package_complete`` to
``EvidenceStatus.SUPPORTED`` and it never treats a manifest hash list, a prior
review PASS, or a self-reported boolean as proof that an experiment ran.

Public interface
----------------
``audit_package(root, mode=..., evidence_index=...)``
    Read-only audit of the eleven mechanism cards.
``export_package(package, output_dir)``
    Write ``package.json``, ``README.md``, ``cards/M01.json`` ... ``M11.json``
    and ``MANIFEST.json`` into a new directory.
``verify_export(output_dir)``
    Recompute the export inventory and the eleven-card package contract without
    reading any external original.
``main(argv=None)``
    ``build`` / ``verify`` command line entry point.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from hsm_lab.contract.guards import sha256_file
from hsm_lab.evidence.adapter import register_legacy_cards
from hsm_lab.evidence.loader import load_evidence_manifest
from hsm_lab.evidence.schemas import canonical_mechanism_id
from hsm_lab.provenance.manifest import canonical_digest, canonical_json

PACKAGE_SCHEMA_VERSION = "hist_vnext_h6b_package_v1"
INDEX_SCHEMA_VERSION = "hist_vnext_h6b_evidence_index_v1"
DEFAULT_EVIDENCE_INDEX = Path("studies/HIST_VNEXT/packages/H6B/evidence_index.json")

CHECK_NAMES: tuple[str, ...] = (
    "schema_valid",
    "experiment_declared",
    "paired_control",
    "first_stage_checked",
    "accounting_checked",
    "negative_control",
    "metrics_generated",
    "sensitivity_or_reason_not_run",
    "historical_evidence_grade",
    "counterevidence",
    "reproduction_bundle",
)

_STATUSES = frozenset({"PASS", "BLOCKED", "NOT_RUN"})
_MODES = frozenset({"git-only", "local-data"})
_LEGACY_IDS = tuple(f"M{i}" for i in range(1, 12))
_CANONICAL_IDS = tuple(f"M{i:02d}" for i in range(1, 12))

# Paths whose content is never opened, hashed or copied by this module.
_FORBIDDEN_COMPONENTS = frozenset(
    {
        "private",
        "target",
        "targets",
        "holdout",
        "hold_out",
        "reserved",
        "sealed",
        "originals",
        "raw_sources",
    }
)
_ABSOLUTE_PATH_RE = re.compile(r"(?:^|[\"'\s])/(?:Users|home|tmp|var|private)/")
_FORBIDDEN_TEXT_KEYS = frozenset(
    {
        "original_excerpt",
        "original_text",
        "ocr_text",
        "translation",
        "translated_text",
        "raw_source",
        "local_path",
        "private_path",
        "api_key",
        "secret",
        "password",
    }
)


class PackageExportError(Exception):
    """A deterministic H6B contract failure (CLI exit code 2)."""


@dataclass(frozen=True)
class CardDefinition:
    """Fixed, non-index-provided metadata for one mechanism card."""

    study_id: str
    legacy_card_id: str
    kind: str  # experiment | blocked | not_started | fixture
    phase: str
    card_path: str
    spec_path: str | None = None
    manifest_path: str | None = None
    report_path: str | None = None
    review_path: str | None = None
    runner_path: str | None = None
    declaration_path: str | None = None
    prior_commit: str | None = None
    prior_path: str | None = None
    commands: tuple[str, ...] = ()
    fixture: bool = False


# Prior commits were located with one targeted ``git log`` per evidence file and
# the blob was verified with ``git show <hash>:<path>`` during H6B authoring.
# They are fixed metadata, not derived from a mutable evidence-manifest ``head``.
CARD_DEFINITIONS: dict[str, CardDefinition] = {
    "M01": CardDefinition(
        study_id="M01",
        legacy_card_id="M1",
        kind="experiment",
        phase="H5C",
        card_path="config/p06/cards/M1.json",
        spec_path="studies/HIST_VNEXT/M01/spec.json",
        manifest_path="studies/HIST_VNEXT/M01/EVIDENCE_MANIFEST.json",
        report_path="studies/HIST_VNEXT/M01/REPORT.md",
        review_path="studies/HIST_VNEXT/M01/REVIEW.md",
        runner_path="studies/HIST_VNEXT/M01/runner.py",
        prior_commit="3ec08983f0ca2f77dc1a5e446e4f39e7fab7be98",
        prior_path="studies/HIST_VNEXT/M01/REPORT.md",
        commands=(
            ".venv/bin/python -B -m studies.HIST_VNEXT.M01.runner study --root . "
            "--output-dir <NEW>",
            ".venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir <NEW>",
        ),
    ),
    "M02": CardDefinition(
        study_id="M02",
        legacy_card_id="M2",
        kind="experiment",
        phase="H5A-A1",
        card_path="config/p06/cards/M2.json",
        spec_path="studies/HIST_VNEXT/M02/spec.json",
        manifest_path="studies/HIST_VNEXT/M02/EVIDENCE_MANIFEST.json",
        report_path="studies/HIST_VNEXT/M02/REPORT.md",
        review_path="studies/HIST_VNEXT/M02/REVIEW.md",
        runner_path="experiments/hist_enterprise.py",
        prior_commit="a3ad69cd65f5f4bb02e2b9bf83b2018bad4b260e",
        prior_path="studies/HIST_VNEXT/M02/REPORT.md",
        commands=(
            ".venv/bin/python -B -m experiments.hist_enterprise --root . "
            "--spec studies/HIST_VNEXT/M02/spec.json --output-dir <NEW>",
        ),
    ),
    "M03": CardDefinition(
        study_id="M03",
        legacy_card_id="M3",
        kind="experiment",
        phase="H5D",
        card_path="config/p06/cards/M3.json",
        spec_path="studies/HIST_VNEXT/M03/IMPLEMENTATION_SPEC.json",
        manifest_path="studies/HIST_VNEXT/M03/IMPLEMENTATION_EVIDENCE_MANIFEST.json",
        report_path="studies/HIST_VNEXT/M03/IMPLEMENTATION_REPORT.md",
        review_path="studies/HIST_VNEXT/M03/IMPLEMENTATION_REVIEW.md",
        runner_path="studies/HIST_VNEXT/M03/labor_runner.py",
        prior_commit="b73fb6e0eb34006558e4b1c7aba4df564d927d31",
        prior_path="studies/HIST_VNEXT/M03/IMPLEMENTATION_REPORT.md",
        commands=(
            ".venv/bin/python -B studies/HIST_VNEXT/M03/labor_runner.py "
            "negative-controls --output-dir <NEW>",
            ".venv/bin/python -B studies/HIST_VNEXT/M03/labor_runner.py run "
            "--scenario historical_f2_replay --enable-labor-institution --output-dir <NEW>",
            ".venv/bin/python -B studies/HIST_VNEXT/M03/labor_runner.py verify --run-dir <NEW>",
        ),
    ),
    "M04": CardDefinition(
        study_id="M04",
        legacy_card_id="M4",
        kind="experiment",
        phase="H5B",
        card_path="config/p06/cards/M4.json",
        spec_path="studies/HIST_VNEXT/M04/spec.json",
        manifest_path="studies/HIST_VNEXT/M04/EVIDENCE_MANIFEST.json",
        report_path="studies/HIST_VNEXT/M04/REPORT.md",
        review_path="docs/phases/HIST_VNEXT/H5B/REVIEW.md",
        runner_path="studies/HIST_VNEXT/M04/runner.py",
        prior_commit="8ab4a20ad4920bb631302b0f8ca519a761ee8afa",
        prior_path="studies/HIST_VNEXT/M04/REPORT.md",
        commands=(
            ".venv/bin/python -B studies/HIST_VNEXT/M04/runner.py study "
            "--spec studies/HIST_VNEXT/M04/spec.json --output-dir <NEW>",
        ),
    ),
    "M05": CardDefinition(
        study_id="M05",
        legacy_card_id="M5",
        kind="not_started",
        phase="P07A1",
        card_path="config/p06/cards/M5.json",
        declaration_path="studies/M05/study_decl.json",
        prior_commit="6adb607cd8be4a5255fb7a14792aafd40e26c7d3",
        prior_path="studies/M05/study_decl.json",
    ),
    "M06": CardDefinition(
        study_id="M06",
        legacy_card_id="M6",
        kind="blocked",
        phase="H5G-G1",
        card_path="config/p06/cards/M6.json",
        manifest_path="studies/HIST_VNEXT/M06/EVIDENCE_MANIFEST.json",
        report_path="studies/HIST_VNEXT/M06/REPORT.md",
        review_path="studies/HIST_VNEXT/M06/REVIEW.md",
        declaration_path="studies/M06/study_decl.json",
        prior_commit="c0b19dbd14b79cec79b58c7a1f77d14cc0b6aa5d",
        prior_path="studies/HIST_VNEXT/M06/REPORT.md",
    ),
    "M07": CardDefinition(
        study_id="M07",
        legacy_card_id="M7",
        kind="blocked",
        phase="H5E",
        card_path="config/p06/cards/M7.json",
        manifest_path="studies/HIST_VNEXT/M07/EVIDENCE_MANIFEST.json",
        report_path="studies/HIST_VNEXT/M07/REPORT.md",
        review_path="studies/HIST_VNEXT/M07/REVIEW.md",
        declaration_path="studies/M07/study_decl.json",
        prior_commit="fbfd2216e6a65be3ef9a60e54221c81a000f4766",
        prior_path="studies/HIST_VNEXT/M07/REPORT.md",
    ),
    "M08": CardDefinition(
        study_id="M08",
        legacy_card_id="M8",
        kind="not_started",
        phase="P07A1",
        card_path="config/p06/cards/M8.json",
        declaration_path="studies/M08/study_decl.json",
        prior_commit="6adb607cd8be4a5255fb7a14792aafd40e26c7d3",
        prior_path="studies/M08/study_decl.json",
    ),
    "M09": CardDefinition(
        study_id="M09",
        legacy_card_id="M9",
        kind="experiment",
        phase="H5F-F1",
        card_path="config/p06/cards/M9.json",
        spec_path="studies/HIST_VNEXT/M09/spec.json",
        manifest_path="studies/HIST_VNEXT/M09/EVIDENCE_MANIFEST.json",
        report_path="studies/HIST_VNEXT/M09/REPORT.md",
        review_path="studies/HIST_VNEXT/M09/REVIEW.md",
        runner_path="studies/HIST_VNEXT/M09/runner.py",
        prior_commit="f88eb43a028b4147ca5abe0067c89a99e4ac443a",
        prior_path="studies/HIST_VNEXT/M09/REPORT.md",
        commands=(
            ".venv/bin/python -B -m studies.HIST_VNEXT.M09.runner study --root . "
            "--output-dir <NEW>",
            ".venv/bin/python -B -m studies.HIST_VNEXT.M09.runner verify --root . "
            "--output-dir <NEW>",
        ),
    ),
    "M10": CardDefinition(
        study_id="M10",
        legacy_card_id="M10",
        kind="not_started",
        phase="P07A1",
        card_path="config/p06/cards/M10.json",
        declaration_path="studies/M10/study_decl.json",
        prior_commit="6adb607cd8be4a5255fb7a14792aafd40e26c7d3",
        prior_path="studies/M10/study_decl.json",
    ),
    "M11": CardDefinition(
        study_id="M11",
        legacy_card_id="M11",
        kind="not_started",
        phase="P07A1",
        card_path="config/p06/cards/M11.json",
        declaration_path="studies/M11/study_decl.json",
        prior_commit="6adb607cd8be4a5255fb7a14792aafd40e26c7d3",
        prior_path="studies/M11/study_decl.json",
    ),
}

_SOURCE_METADATA_PATHS = (
    "history/HIST_VNEXT/sources/batch01_candidates.json",
    "history/HIST_VNEXT/h4_sources/sources.json",
)


# ---------------------------------------------------------------------------
# Small deterministic helpers
# ---------------------------------------------------------------------------


def _status(value: str) -> str:
    if value not in _STATUSES:
        raise PackageExportError(f"invalid check status: {value!r}")
    return value


def _check(
    status: str,
    level: str,
    reason: str,
    refs: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "status": _status(status),
        "level": level,
        "reason": reason,
        "evidence_refs": [dict(ref) for ref in refs],
    }


def _ok(
    reason: str, refs: Iterable[dict[str, Any]] = (), *, level: str = "VERIFIED_BY_RUN"
) -> dict[str, Any]:
    return _check("PASS", level, reason, refs)


def _blocked(
    reason: str, refs: Iterable[dict[str, Any]] = (), *, level: str = "VERIFIED_BY_CODE"
) -> dict[str, Any]:
    return _check("BLOCKED", level, reason, refs)


def _not_run(reason: str, refs: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    return _check("NOT_RUN", "NOT_RUN", reason, refs)


def _complete(checks: Mapping[str, dict[str, Any]]) -> bool:
    return all(checks[name]["status"] == "PASS" for name in CHECK_NAMES)


def _finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value == value
        and abs(float(value)) != float("inf")
    )


def _finite_number(value: Any, *, what: str) -> float:
    if not _finite(value):
        raise PackageExportError(f"{what} is not a finite number: {value!r}")
    return float(value)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise PackageExportError(f"duplicate JSON key: {key!r}")
        out[key] = value
    return out


def _reject_constant(value: str) -> None:
    raise PackageExportError(f"non-finite JSON constant rejected: {value}")


def _strict_json(text: str, *, origin: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except PackageExportError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise PackageExportError(f"invalid JSON in {origin}: {exc}") from exc


class AuditContext:
    """Path-guarded, cached read-only access to one repository root."""

    def __init__(self, root: Path, *, mode: str) -> None:
        self.root = root.resolve()
        self.mode = mode
        self._json_cache: dict[str, Any] = {}
        self._hash_cache: dict[str, str] = {}
        self._bytes_cache: dict[str, int] = {}

    def guard(self, relative: str | Path, *, must_exist: bool = False) -> Path:
        if isinstance(relative, Path):
            raw = relative.as_posix()
        else:
            raw = str(relative)
        if not raw or raw.startswith("/") or "\x00" in raw or "\\" in raw:
            raise PackageExportError(f"unsafe path rejected: {raw!r}")
        parts = Path(raw).parts
        if not parts or any(part in ("..", ".") for part in parts):
            raise PackageExportError(f"unsafe path rejected: {raw!r}")
        if any(part in _FORBIDDEN_COMPONENTS for part in parts):
            raise PackageExportError(f"restricted path rejected before open/hash: {raw!r}")
        # Reject symlinks before resolving them: resolving first would hide a
        # symlink that points into a restricted directory.
        current = self.root
        for part in parts:
            current = current / part
            if current.is_symlink():
                raise PackageExportError(f"symlink rejected before open/hash: {raw!r}")
        target = (self.root / raw).resolve()
        if target != self.root and self.root not in target.parents:
            raise PackageExportError(f"path escapes root: {raw!r} -> {target}")
        resolved_relative = target.relative_to(self.root)
        if any(part in _FORBIDDEN_COMPONENTS for part in resolved_relative.parts):
            raise PackageExportError(
                f"restricted resolved path rejected before open/hash: {raw!r} -> {target}"
            )
        for parent in target.parents:
            if parent == self.root:
                break
            if parent.is_symlink():
                raise PackageExportError(f"symlinked ancestor rejected: {raw!r}")
        if must_exist and not target.exists():
            raise FileNotFoundError(raw)
        return target

    def exists(self, relative: str | Path) -> bool:
        try:
            return self.guard(relative).is_file()
        except (PackageExportError, FileNotFoundError):
            return False

    def sha256(self, relative: str | Path) -> str:
        raw = Path(relative).as_posix()
        if raw not in self._hash_cache:
            path = self.guard(raw, must_exist=True)
            self._hash_cache[raw] = sha256_file(path)
            self._bytes_cache[raw] = path.stat().st_size
        return self._hash_cache[raw]

    def size(self, relative: str | Path) -> int:
        raw = Path(relative).as_posix()
        if raw not in self._bytes_cache:
            self.sha256(raw)
        return self._bytes_cache[raw]

    def ref(
        self,
        relative: str | Path,
        *,
        pointer: str | None = None,
        line: int | None = None,
    ) -> dict[str, Any]:
        raw = Path(relative).as_posix()
        path = self.guard(raw, must_exist=True)
        if pointer is None and line is not None:
            if line < 1 or line > len(path.read_text(encoding="utf-8").splitlines()):
                raise PackageExportError(f"line anchor {line} outside {raw}")
        result: dict[str, Any] = {
            "path": raw,
            "sha256": self.sha256(raw),
            "bytes": self.size(raw),
        }
        if pointer is not None:
            result["pointer"] = pointer
        if line is not None:
            result["line"] = line
        return result

    def ref_if_exists(self, relative: str | Path, **kwargs: Any) -> dict[str, Any] | None:
        try:
            return self.ref(relative, **kwargs)
        except FileNotFoundError:
            return None

    def json(self, relative: str | Path) -> Any:
        raw = Path(relative).as_posix()
        if raw not in self._json_cache:
            path = self.guard(raw, must_exist=True)
            self._json_cache[raw] = _strict_json(path.read_text(encoding="utf-8"), origin=raw)
        return self._json_cache[raw]

    def text(self, relative: str | Path) -> str:
        raw = Path(relative).as_posix()
        return self.guard(raw, must_exist=True).read_text(encoding="utf-8")


def _require_dict(value: Any, *, what: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PackageExportError(f"{what} must be a JSON object")
    return value


def _require_list(value: Any, *, what: str) -> list[Any]:
    if not isinstance(value, list):
        raise PackageExportError(f"{what} must be a JSON array")
    return value


def _card_pointer(pointer: str) -> str:
    return pointer


# ---------------------------------------------------------------------------
# Evidence index
# ---------------------------------------------------------------------------


def load_evidence_index(root: Path, path: Path) -> dict[str, Any]:
    """Load and strictly validate the H6B evidence index.

    The index may only locate existing or fresh run directories under the root.
    It cannot carry booleans, expressions, commands, source paths or extra
    fields.
    """

    root = root.resolve()
    ctx = AuditContext(root, mode="local-data")
    raw_path = path if path.is_absolute() else root / path
    try:
        relative = raw_path.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise PackageExportError(f"evidence index outside root: {path}") from exc
    if not ctx.exists(relative):
        raise PackageExportError(f"evidence index missing: {relative}")
    document = _require_dict(ctx.json(relative), what="evidence index")
    if set(document) != {"schema_version", "cards"}:
        raise PackageExportError("evidence index must contain exactly schema_version and cards")
    if document["schema_version"] != INDEX_SCHEMA_VERSION:
        raise PackageExportError(f"evidence index schema_version must be {INDEX_SCHEMA_VERSION!r}")
    cards = _require_dict(document["cards"], what="evidence index cards")
    if set(cards) != set(_CANONICAL_IDS):
        missing = sorted(set(_CANONICAL_IDS) - set(cards))
        extra = sorted(set(cards) - set(_CANONICAL_IDS))
        raise PackageExportError(
            f"evidence index must name exactly M01..M11 (missing={missing}, extra={extra})"
        )
    normalized: dict[str, dict[str, str | None]] = {}
    for card_id in _CANONICAL_IDS:
        entry = _require_dict(cards[card_id], what=f"evidence index {card_id}")
        if set(entry) != {"existing_root", "fresh_root", "repeat_root"}:
            raise PackageExportError(
                f"evidence index {card_id} must contain exactly "
                "existing_root, fresh_root, repeat_root"
            )
        normalized_entry: dict[str, str | None] = {}
        for key in ("existing_root", "fresh_root", "repeat_root"):
            value = entry[key]
            if value is None:
                normalized_entry[key] = None
                continue
            if not isinstance(value, str) or not value.strip():
                raise PackageExportError(
                    f"evidence index {card_id}.{key} must be a non-empty relative path or null"
                )
            # Validate the path shape now, but do not require the directory to
            # exist: fresh/repeat roots may be absent in a git-only checkout.
            ctx.guard(value)
            normalized_entry[key] = Path(value).as_posix()
        normalized[card_id] = normalized_entry
    return {
        "schema_version": document["schema_version"],
        "cards": normalized,
        "digest": ctx.sha256(relative),
        "path": relative,
    }


# ---------------------------------------------------------------------------
# Source-rights metadata (never the originals)
# ---------------------------------------------------------------------------


def _load_source_rights(ctx: AuditContext) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    refs: list[dict[str, Any]] = []
    for relative in _SOURCE_METADATA_PATHS:
        if not ctx.exists(relative):
            continue
        document = ctx.json(relative)
        refs.append(ctx.ref(relative))
        raw_records = document.get("records") if isinstance(document, dict) else None
        if raw_records is None and isinstance(document, dict):
            raw_records = document.get("sources")
        if not isinstance(raw_records, list):
            continue
        for record in raw_records:
            if not isinstance(record, dict):
                continue
            rights = record.get("rights") if isinstance(record.get("rights"), dict) else {}
            records.append(
                {
                    "source_id": record.get("source_id"),
                    "rights_status": (
                        record.get("rights_status") or rights.get("license_status") or "UNKNOWN"
                    ),
                    "redistribution_allowed": bool(rights.get("redistribution_allowed")),
                    "download_allowed": bool(rights.get("download_allowed")),
                    "admission_status": record.get("admission_status")
                    or record.get("data_role")
                    or "UNKNOWN",
                    "source_type": record.get("source_type"),
                    "purpose": record.get("purpose"),
                }
            )
    return {
        "policy": "reference_only; originals are never opened, copied or re-distributed",
        "metadata_refs": refs,
        "sources": sorted(records, key=lambda item: str(item.get("source_id"))),
        "admitted_historical_series": [],
        "redistribution_allowed_any": any(item["redistribution_allowed"] for item in records),
    }


# ---------------------------------------------------------------------------
# Real-card adapters
# ---------------------------------------------------------------------------


def _identity_and_schema(
    ctx: AuditContext,
    definition: CardDefinition,
    registry: Any,
    index_entry: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    """Verify frozen card identity and strict JSON schemas.

    Missing card bytes, a card-SHA mismatch, a missing manifest for an
    experiment/blocked card, or a manifest/spec naming another card is an H6B
    hard failure.  Local missing run outputs are handled by the individual
    checks instead.
    """

    card = next(
        (item for item in registry.cards if item.study_id == definition.study_id),
        None,
    )
    if card is None:
        raise PackageExportError(f"{definition.study_id}: legacy card not registered")
    if canonical_mechanism_id(card.mechanism_id) != canonical_mechanism_id(
        definition.legacy_card_id
    ):
        raise PackageExportError(f"{definition.study_id}: legacy card id mismatch")
    actual_card_sha = ctx.sha256(definition.card_path)
    if actual_card_sha != card.sha256:
        raise PackageExportError(
            f"{definition.study_id}: frozen card SHA mismatch "
            f"(disk={actual_card_sha}, registry={card.sha256})"
        )
    if set(index_entry) != {"existing_root", "fresh_root", "repeat_root"}:
        raise PackageExportError(f"{definition.study_id}: invalid evidence-index entry")

    manifest = None
    spec = None
    if definition.manifest_path:
        if not ctx.exists(definition.manifest_path):
            raise PackageExportError(
                f"{definition.study_id}: required evidence manifest missing: "
                f"{definition.manifest_path}"
            )
        manifest = _require_dict(
            ctx.json(definition.manifest_path), what=f"{definition.study_id} manifest"
        )
        manifest_study = manifest.get("study_id")
        if manifest_study is not None and manifest_study != definition.study_id:
            raise PackageExportError(f"{definition.study_id}: manifest names {manifest_study!r}")
        manifest_mechanism = manifest.get("mechanism_id")
        if manifest_mechanism is not None:
            if canonical_mechanism_id(manifest_mechanism) != canonical_mechanism_id(
                definition.legacy_card_id
            ):
                raise PackageExportError(f"{definition.study_id}: manifest mechanism_id mismatch")
        if not isinstance(manifest.get("schema_version"), str):
            raise PackageExportError(f"{definition.study_id}: manifest has no schema_version")

    if definition.spec_path:
        if not ctx.exists(definition.spec_path):
            if definition.kind == "experiment":
                raise PackageExportError(
                    f"{definition.study_id}: required experiment spec missing: "
                    f"{definition.spec_path}"
                )
        else:
            spec = _require_dict(ctx.json(definition.spec_path), what=f"{definition.study_id} spec")
            if spec.get("study_id") not in (None, definition.study_id):
                raise PackageExportError(f"{definition.study_id}: spec names another study")
            if spec.get("mechanism_id") not in (None, definition.legacy_card_id):
                raise PackageExportError(f"{definition.study_id}: spec names another mechanism")

    if definition.declaration_path and not ctx.exists(definition.declaration_path):
        raise PackageExportError(
            f"{definition.study_id}: required study declaration missing: "
            f"{definition.declaration_path}"
        )

    refs = [ctx.ref(definition.card_path)]
    if definition.spec_path and ctx.exists(definition.spec_path):
        refs.append(ctx.ref(definition.spec_path))
    if definition.manifest_path and ctx.exists(definition.manifest_path):
        refs.append(ctx.ref(definition.manifest_path))
    if definition.declaration_path:
        refs.append(ctx.ref(definition.declaration_path))

    spec_legacy_sha = None
    if isinstance(spec, dict):
        legacy = spec.get("legacy_card")
        if isinstance(legacy, dict):
            spec_legacy_sha = legacy.get("sha256")
    if spec_legacy_sha is not None and spec_legacy_sha != actual_card_sha:
        raise PackageExportError(f"{definition.study_id}: spec binds a different legacy card SHA")

    check = _ok(
        "strict JSON; exact study/mechanism identity; frozen card SHA matches",
        refs,
        level="VERIFIED_BY_CODE",
    )
    return check, spec, manifest


def _experiment_declared(
    definition: CardDefinition,
    spec: dict[str, Any] | None,
    *,
    refs: list[dict[str, Any]],
) -> dict[str, Any]:
    if definition.kind != "experiment":
        return _not_run(
            "no dedicated experiment spec; only a declaration or blocker certificate exists",
            refs,
        )
    if spec is None:
        return _blocked("experiment spec is missing", refs)

    def require(path: tuple[str, ...], what: str) -> Any:
        value: Any = spec
        for key in path:
            if not isinstance(value, dict) or key not in value:
                raise PackageExportError(
                    f"{definition.study_id}: spec lacks {what} ({'.'.join(path)})"
                )
            value = value[key]
        return value

    try:
        if definition.study_id == "M01":
            design = require(("design",), "design")
            for key in (
                "seeds",
                "histories",
                "cuts",
                "budget_only_controls",
                "arms_total",
                "treatment_tick",
            ):
                if key not in design:
                    raise PackageExportError(f"M01: design lacks {key}")
            if require(("legacy_card", "sha256"), "legacy card binding") is None:
                raise PackageExportError("M01: empty legacy card SHA")
        elif definition.study_id == "M02":
            if len(require(("arms",), "arms")) < 2:
                raise PackageExportError("M02: fewer than two declared arms")
            if len(require(("run", "seeds"), "seeds")) < 2:
                raise PackageExportError("M02: fewer than two declared seeds")
            require(("completion_rule",), "completion rule")
            require(("falsification_rule",), "falsification rule")
            require(("legacy_card", "sha256"), "legacy card binding")
        elif definition.study_id == "M03":
            require(("accepted_spec", "sha256"), "accepted spec binding")
            if require(("implementation", "default_off"), "default-off declaration") is not True:
                raise PackageExportError("M03: default_off is not true")
            if len(require(("verification_arms",), "verification arms")) < 3:
                raise PackageExportError("M03: verification arms missing")
        elif definition.study_id == "M04":
            if len(require(("run", "seeds"), "seeds")) < 2:
                raise PackageExportError("M04: fewer than two declared seeds")
            if len(require(("arms",), "arms")) < 2:
                raise PackageExportError("M04: fewer than two declared arms")
            require(("completion_rule",), "completion rule")
            require(("first_stage_adjudication",), "first-stage adjudication")
            require(("legacy_card", "sha256"), "legacy card binding")
        elif definition.study_id == "M09":
            if len(require(("seeds",), "seeds")) < 2:
                raise PackageExportError("M09: fewer than two declared seeds")
            if len(require(("arms",), "arms")) < 2:
                raise PackageExportError("M09: fewer than two declared arms")
            for key in ("issue_ticks", "target_ticks", "historical_status", "structural_status"):
                require((key,), key)
        else:  # pragma: no cover - fixed definitions cover only the five experiments.
            raise PackageExportError(f"no experiment adapter for {definition.study_id}")
    except PackageExportError as exc:
        return _blocked(str(exc), refs)
    return _ok(
        "dedicated preregistration binds the frozen card and declares seeds, arms, "
        "window and adjudication",
        refs,
    )


def _generic_historical_check(
    ctx: AuditContext,
    definition: CardDefinition,
    manifest: dict[str, Any] | None,
    spec: dict[str, Any] | None,
    *,
    status_value: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    refs: list[dict[str, Any]] = []
    declared = status_value
    declared_reason = reason
    if spec:
        declared = declared or spec.get("historical_status")
        if declared_reason is None:
            declared_reason = spec.get("historical_reason")
    if manifest:
        study = manifest.get("study")
        if isinstance(study, dict):
            declared = declared or study.get("historical_status")
        declared = declared or manifest.get("historical_verdict")
        declared = declared or manifest.get("historical_status")
    if definition.report_path and ctx.exists(definition.report_path):
        refs.append(ctx.ref(definition.report_path, line=1))
    if definition.manifest_path:
        refs.append(ctx.ref(definition.manifest_path))
    if definition.spec_path and ctx.exists(definition.spec_path):
        refs.append(ctx.ref(definition.spec_path))
    if declared not in {"UNIDENTIFIED", "NOT_RUN", "BLOCKED", "NOT_ESTABLISHED"}:
        return _blocked(
            f"historical status is not an honest unidentified/not-run grade: {declared!r}",
            refs,
        )
    if not declared_reason and definition.kind == "experiment":
        return _blocked(
            "historical status is declared but no reason/source gap is recorded",
            refs,
        )
    return _ok(
        f"honest historical grade {declared}; source rights are reference-only; no SUPPORTED claim",
        refs,
        level="VERIFIED_BY_CODE",
    )


# --- M01 -------------------------------------------------------------------


def _m01_study_root(ctx: AuditContext, index_entry: Mapping[str, Any]) -> str:
    existing = index_entry.get("existing_root")
    if not existing:
        raise PackageExportError("M01: evidence index has no existing_root")
    return str(existing)


def _m01_arm_files(ctx: AuditContext, study_root: str) -> list[str]:
    arms_root = ctx.guard(f"{study_root}/arms", must_exist=True)
    result: list[str] = []
    for child in sorted(arms_root.iterdir()):
        if child.is_dir() and (child / "result.json").is_file():
            result.append(f"{study_root}/arms/{child.name}/result.json")
    return result


def _m01_validate_run(
    ctx: AuditContext, study_root: str
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    study = _require_dict(ctx.json(f"{study_root}/study.json"), what="M01 study.json")
    _require_dict(ctx.json(f"{study_root}/manifest.json"), what="M01 manifest.json")
    matrix = _require_dict(study.get("matrix"), what="M01 matrix")
    if matrix.get("completed_arms") != 78 or matrix.get("expected_arms") != 78:
        raise PackageExportError("M01: full 78-arm matrix is not complete")
    seeds = [int(seed) for seed in _require_list(study.get("seeds"), what="M01 seeds")]
    if len(seeds) != 3 or len(set(seeds)) != 3:
        raise PackageExportError("M01: expected three distinct paired seeds")
    group = _require_dict(study.get("group_checks"), what="M01 group_checks")
    if set(group) != {str(seed) for seed in seeds}:
        raise PackageExportError("M01: group_checks do not cover every seed")
    for seed in seeds:
        item = _require_dict(group[str(seed)], what=f"M01 group_checks[{seed}]")
        if item.get("arms") != 26:
            raise PackageExportError(f"M01: seed {seed} does not have 26 arms")
        for key in (
            "pre_matching_equal",
            "opening_nonmemory_equal",
            "warmup_interventions_equal",
            "budget_only_opening_memory_equals_transplant_pre",
        ):
            if item.get(key) is not True:
                raise PackageExportError(f"M01: seed {seed} failed {key}")
        if len(item.get("pre_matching_digest_unique", [])) != 1:
            raise PackageExportError(f"M01: seed {seed} has no unique opening digest")
    if study.get("failures"):
        raise PackageExportError("M01: study records failures")

    arm_files = _m01_arm_files(ctx, study_root)
    if len(arm_files) != 78:
        raise PackageExportError(f"M01: expected 78 arm result files, found {len(arm_files)}")
    max_material_ratio = 0.0
    max_finance_ratio = 0.0
    coverage: set[tuple[int, str, float, str]] = set()
    for relative in arm_files:
        result = _require_dict(ctx.json(relative), what=f"M01 arm {relative}")
        if result.get("completed_ticks") != 8:
            raise PackageExportError(f"M01: arm did not complete 8 ticks: {relative}")
        gates = _require_dict(result.get("gates"), what=f"M01 gates {relative}")
        material_ratio = _finite_number(
            gates.get("max_material_tolerance_ratio"), what="M01 material tolerance ratio"
        )
        finance_ratio = _finite_number(
            gates.get("max_finance_tolerance_ratio"), what="M01 finance tolerance ratio"
        )
        if material_ratio > 1.0 or finance_ratio > 1.0:
            raise PackageExportError(f"M01: accounting tolerance exceeded in {relative}")
        max_material_ratio = max(max_material_ratio, material_ratio)
        max_finance_ratio = max(max_finance_ratio, finance_ratio)
        seed = (
            int(result.get("seed"))
            if "seed" in result
            else int(relative.split("/")[-2].split("-")[0])
        )
        opening = _require_dict(result.get("opening"), what=f"M01 opening {relative}")
        if opening.get("matching_digest") != group[str(seed)]["pre_matching_digest_unique"][0]:
            raise PackageExportError(f"M01: opening digest mismatch for {relative}")
        strength = result.get("formation_ratchet_strength")
        coverage.add(
            (
                seed,
                str(result.get("history_id")),
                None if strength is None else float(strength),
                str(result.get("cut_id")),
            )
        )
    expected_coverage: set[tuple[int, str, float | None, str]] = set()
    for seed in seeds:
        for history in matrix["histories"]:
            for strength in matrix["strengths"]:
                for cut in matrix["cuts"]:
                    expected_coverage.add((seed, str(history), float(strength), str(cut)))
        for cut in matrix["native_cuts"]:
            expected_coverage.add((seed, "native", None, str(cut)))
    if coverage != expected_coverage:
        raise PackageExportError("M01: arm coverage is not the full registered matrix")
    # Compare the scientific study payload and the validated gate maxima, not
    # the whole manifest: per-arm result.json records its own output_dir, so a
    # whole-manifest digest would change with the (non-scientific) run path.
    fingerprint_payload = {
        "study": {
            key: study.get(key)
            for key in (
                "schema_version",
                "study_id",
                "matrix",
                "group_checks",
                "reference_first_stage",
                "cut_first_stage",
                "statistics",
                "verdict",
                "failures",
            )
        },
        "gates": {
            "max_material_tolerance_ratio": max_material_ratio,
            "max_finance_tolerance_ratio": max_finance_ratio,
            "arms": 78,
            "ticks": 8,
        },
    }
    refs = [
        ctx.ref(f"{study_root}/study.json"),
        ctx.ref(f"{study_root}/manifest.json"),
        ctx.ref(arm_files[0]),
    ]
    detail = {
        "max_material_tolerance_ratio": max_material_ratio,
        "max_finance_tolerance_ratio": max_finance_ratio,
        "arms": 78,
        "ticks": 8,
    }
    return refs, canonical_digest(fingerprint_payload), detail


def _m01_first_stage_ok(study: dict[str, Any]) -> tuple[bool, str]:
    reference = study.get("reference_first_stage")
    cut = study.get("cut_first_stage")
    if not isinstance(reference, dict) or reference.get("status") != "PASS":
        return False, "reference first stage is not PASS"
    if not isinstance(cut, dict) or cut.get("status") != "PASS":
        return False, "cut first stage is not PASS"
    seeds = [str(seed) for seed in study.get("seeds", [])]
    by_seed = reference.get("by_seed")
    if not isinstance(by_seed, dict) or set(by_seed) != set(seeds):
        return False, "reference first stage does not cover every seed"
    for seed in seeds:
        if not isinstance(by_seed.get(seed), dict) or by_seed[seed].get("status") != "PASS":
            return False, f"reference first stage failed for seed {seed}"
    cut_by_seed = cut.get("by_seed")
    if not isinstance(cut_by_seed, dict) or set(cut_by_seed) != set(seeds):
        return False, "cut first stage does not cover every seed"
    for seed in seeds:
        levers = cut_by_seed.get(seed)
        if not isinstance(levers, dict) or not levers:
            return False, f"cut first stage has no levers for seed {seed}"
        for lever, payload in levers.items():
            if not isinstance(payload, dict):
                return False, f"cut first stage {lever} for seed {seed} is not an object"
            if payload.get("status") != "BINDING":
                return False, f"cut first stage {lever} for seed {seed} is not BINDING"
            for key in ("applied", "effective", "binding"):
                if payload.get(key) is not True:
                    return False, f"cut first stage {lever} for seed {seed} failed {key}"
            flow = payload.get("first_stage")
            if not isinstance(flow, dict) or not flow:
                return False, f"cut first stage {lever} for seed {seed} has no flow"
    return True, "reference and cut first stages PASS for every seed with binding flows"


def _m01_metrics_ok(study: dict[str, Any]) -> tuple[bool, str]:
    levers = study.get("verdict", {}).get("levers")
    if not isinstance(levers, dict) or set(levers) != {"import_cut", "income_cut", "welfare_cut"}:
        return False, "verdict levers are incomplete"
    for lever, payload in levers.items():
        if not isinstance(payload, dict):
            return False, f"lever {lever} is not an object"
        for field in (
            "D_four_minus_one_grievance_by_seed",
            "D_four_minus_one_spending_by_seed",
        ):
            values = payload.get(field)
            if not isinstance(values, dict) or len(values) != 3:
                return False, f"{lever}.{field} is missing or incomplete"
            if not all(_finite(value) for value in values.values()):
                return False, f"{lever}.{field} contains a null/non-finite value"
    ablation = study.get("statistics", {}).get("ablation")
    if not isinstance(ablation, list) or not ablation:
        return False, "formation-ratchet ablation is empty"
    for row in ablation:
        if not isinstance(row, dict) or not isinstance(row.get("N_status"), dict):
            return False, "ablation row has no status map"
        cumulative = row.get("N_cumulative")
        if not isinstance(cumulative, dict):
            return False, "ablation row has no cumulative values"
        for key in (
            "grievance_national_from_table",
            "spending_total",
            "expectation_real_consumption_mean",
        ):
            if not _finite(cumulative.get(key)):
                return False, f"ablation {key} is null/non-finite"
    if study.get("statistics", {}).get("missing"):
        return False, "study records missing metrics"
    return True, "lever effects, ablation statuses and finite values are present"


def _m01_historical_ok(study: dict[str, Any]) -> tuple[bool, str]:
    status = study.get("historical_status")
    verdict = study.get("verdict", {})
    verdict_status = verdict.get("historical_status") if isinstance(verdict, dict) else None
    reason = verdict.get("historical_reason") if isinstance(verdict, dict) else None
    if status != "UNIDENTIFIED" or verdict_status != "UNIDENTIFIED":
        return False, f"historical status contradicted ({status!r}/{verdict_status!r})"
    if not isinstance(reason, str) or not reason.strip():
        return False, "historical UNIDENTIFIED has no reason"
    return True, "historical UNIDENTIFIED is consistent in study and verdict"


def _m01_sensitivity_ok(study: dict[str, Any], spec: dict[str, Any]) -> tuple[bool, str]:
    ablation = study.get("statistics", {}).get("ablation")
    if not isinstance(ablation, list) or not ablation:
        return False, "formation-ratchet ablation is empty"
    strengths = spec.get("design", {}).get("formation_ratchet_strengths")
    if not isinstance(strengths, list) or {float(x) for x in strengths} != {0.0, 0.1}:
        return False, "preregistered formation-ratchet strengths are not 0.0 and 0.1"
    for row in ablation:
        cumulative = row.get("N_cumulative") if isinstance(row, dict) else None
        if not isinstance(cumulative, dict):
            return False, "ablation row has no cumulative values"
        for value in cumulative.values():
            if isinstance(value, dict):
                continue
            if not _finite(value):
                return False, "ablation row contains a null/non-finite scalar"
    return True, "0.1 vs 0.0 formation-ratchet ablation is executed with finite values"


def _m01_counterevidence_ok(study: dict[str, Any]) -> tuple[bool, str]:
    welfare = study.get("verdict", {}).get("levers", {}).get("welfare_cut", {})
    status = welfare.get("status") if isinstance(welfare, dict) else None
    if status in (None, "", "SUPPORTED"):
        return (
            False,
            f"welfare lever status does not record a bounded/unidentified result ({status!r})",
        )
    if study.get("failures"):
        return False, "study records failures"
    if not study.get("false_zero_policy"):
        return False, "study has no false-zero policy"
    if study.get("statistics", {}).get("missing"):
        return False, "study records missing metrics"
    return True, f"welfare lever is {status}; failures and missing metrics are empty"


def _m01_checks(
    ctx: AuditContext, index_entry: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    study_root = _m01_study_root(ctx, index_entry)
    study = ctx.json(f"{study_root}/study.json")
    manifest = ctx.json("studies/HIST_VNEXT/M01/EVIDENCE_MANIFEST.json")
    spec = ctx.json("studies/HIST_VNEXT/M01/spec.json")
    try:
        refs, digest, accounting_detail = _m01_validate_run(ctx, study_root)
        validation_error = None
    except PackageExportError as exc:
        refs = [
            ctx.ref(f"{study_root}/study.json"),
            ctx.ref(f"{study_root}/manifest.json"),
        ]
        digest = None
        accounting_detail = {}
        validation_error = str(exc)

    paired = (
        _ok(
            "78 completed arms; per seed one matched opening digest across 26 arms and "
            "native budget-only controls",
            refs,
        )
        if validation_error is None
        else _blocked(f"paired/accounting validation failed: {validation_error}", refs)
    )
    first_ok, first_reason = _m01_first_stage_ok(study)
    first = (
        _ok(first_reason, [ctx.ref(f"{study_root}/study.json", pointer="/cut_first_stage"), *refs])
        if first_ok
        else _blocked(
            first_reason, [ctx.ref(f"{study_root}/study.json", pointer="/cut_first_stage")]
        )
    )
    accounting = (
        _ok(
            "8 ticks per arm; max material tolerance "
            f"{accounting_detail['max_material_tolerance_ratio']:.3e}, max finance tolerance "
            f"{accounting_detail['max_finance_tolerance_ratio']:.3e}, both <= 1",
            refs,
        )
        if validation_error is None
        else _blocked(f"per-tick accounting validation failed: {validation_error}", refs)
    )
    negative = (
        _ok(
            "native no_cut/income_cut arms share opening memory and differ only through "
            "the wage set; all seeds pass",
            [
                ctx.ref(
                    "studies/HIST_VNEXT/M01/spec.json",
                    pointer="/design/budget_only_controls",
                ),
                *refs,
            ],
        )
        if validation_error is None
        else _blocked(f"negative-control validation failed: {validation_error}", refs)
    )
    metrics_ok, metrics_reason = _m01_metrics_ok(study)
    metrics = (
        _ok(metrics_reason, [ctx.ref(f"{study_root}/study.json", pointer="/verdict"), *refs])
        if metrics_ok
        else _blocked(metrics_reason, [ctx.ref(f"{study_root}/study.json", pointer="/verdict")])
    )
    historical_ok, historical_reason = _m01_historical_ok(study)
    historical = (
        _ok(
            historical_reason,
            [ctx.ref(f"{study_root}/study.json", pointer="/verdict")],
            level="VERIFIED_BY_CODE",
        )
        if historical_ok
        else _blocked(historical_reason, [ctx.ref(f"{study_root}/study.json", pointer="/verdict")])
    )
    sensitivity_ok, sensitivity_reason = _m01_sensitivity_ok(study, spec)
    sensitivity = (
        _ok(
            sensitivity_reason,
            [ctx.ref(f"{study_root}/study.json", pointer="/statistics/ablation"), *refs],
        )
        if sensitivity_ok
        else _blocked(
            sensitivity_reason,
            [ctx.ref(f"{study_root}/study.json", pointer="/statistics/ablation")],
        )
    )
    counter_ok, counter_reason = _m01_counterevidence_ok(study)
    counter = (
        _ok(
            counter_reason,
            [
                ctx.ref(f"{study_root}/study.json", pointer="/verdict/levers/welfare_cut"),
                ctx.ref("studies/HIST_VNEXT/M01/REPORT.md", line=162),
                ctx.ref("studies/HIST_VNEXT/M01/REPORT.md", line=60),
            ],
        )
        if counter_ok
        else _blocked(
            counter_reason,
            [ctx.ref(f"{study_root}/study.json", pointer="/verdict/levers/welfare_cut")],
        )
    )
    study_metrics = []
    for lever, payload in study["verdict"]["levers"].items():
        for field in (
            "D_four_minus_one_grievance_by_seed",
            "D_four_minus_one_spending_by_seed",
        ):
            values = payload.get(field)
            if not isinstance(values, dict):
                continue
            for seed, value in values.items():
                if _finite(value):
                    study_metrics.append(
                        {
                            "metric": f"{lever}.{field}",
                            "value": float(value),
                            "unit": "study-level (declared in M01 verdict)",
                            "selector": {"lever": lever, "field": field, "seed": seed},
                            "status": "observed",
                        }
                    )
    reproduction = (
        _reproduction_from_index(
            ctx,
            index_entry,
            verifier=_m01_validate_run,
            refs=refs,
            existing_digest=digest,
            what="M01",
        )
        if validation_error is None
        else _blocked(f"reproduction validation failed: {validation_error}", refs)
    )
    checks = {
        "paired_control": paired,
        "first_stage_checked": first,
        "accounting_checked": accounting,
        "negative_control": negative,
        "metrics_generated": metrics,
        "sensitivity_or_reason_not_run": sensitivity,
        "historical_evidence_grade": historical,
        "counterevidence": counter,
        "reproduction_bundle": reproduction,
    }
    structural_verdict = "; ".join(
        f"{lever}={payload.get('status')}" for lever, payload in study["verdict"]["levers"].items()
    )
    reproduction_payload = {
        "existing_root": index_entry.get("existing_root"),
        "fresh_root": index_entry.get("fresh_root"),
        "repeat_root": index_entry.get("repeat_root"),
        "commands": list(CARD_DEFINITIONS["M01"].commands),
        "scientific_digest": digest,
        "status": reproduction["status"],
        "reason": reproduction["reason"],
        "accounting": accounting_detail,
    }
    return (
        checks,
        {
            "technical": study["technical_status"],
            "structural": structural_verdict,
            "historical": study["historical_status"],
        },
        {
            "metrics": study_metrics,
            "manifest": manifest,
            "study": study,
            "failed_seeds": list(manifest["study"].get("failed_seeds") or []),
            "reproduction": reproduction_payload,
        },
    )


# --- M02 -------------------------------------------------------------------


def _m02_validate_run(
    ctx: AuditContext, study_root: str
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    results = _require_dict(ctx.json(f"{study_root}/results.json"), what="M02 results.json")
    if results.get("status") != "COMPLETED":
        raise PackageExportError("M02: study status is not COMPLETED")
    if results.get("ticks_executed") != 156:
        raise PackageExportError("M02: expected 156 executed ticks")
    selected = _require_dict(results.get("selected"), what="M02 selected")
    seeds = [int(seed) for seed in _require_list(selected.get("seeds"), what="M02 seeds")]
    arms = [str(arm) for arm in _require_list(selected.get("arms"), what="M02 arms")]
    if len(seeds) != 3 or len(set(seeds)) != 3:
        raise PackageExportError("M02: expected three distinct seeds")
    if len(arms) != 13 or len(set(arms)) != 13:
        raise PackageExportError("M02: expected thirteen distinct arms")
    per_arm = _require_dict(results.get("per_arm"), what="M02 per_arm")
    if len(per_arm) != 39:
        raise PackageExportError(f"M02: expected 39 arm-seeds, found {len(per_arm)}")
    opening_by_seed: dict[int, set[str]] = {seed: set() for seed in seeds}
    for key, payload in per_arm.items():
        item = _require_dict(payload, what=f"M02 per_arm {key}")
        seed = int(item["seed"])
        if seed not in opening_by_seed:
            raise PackageExportError(f"M02: undeclared seed in per_arm: {seed}")
        opening_by_seed[seed].add(str(item["opening_state_digest"]))
    for seed, digests in opening_by_seed.items():
        if len(digests) != 1:
            raise PackageExportError(f"M02: seed {seed} has multiple opening states")
    input_identity = _require_list(results.get("input_identity"), what="M02 input_identity")
    if len(input_identity) != 3:
        raise PackageExportError("M02: input_identity does not cover three seeds")
    if [int(item["seed"]) for item in input_identity] != seeds:
        raise PackageExportError("M02: input_identity seeds do not match the selected seeds")
    placebo = _require_list(results.get("placebo_checks"), what="M02 placebo_checks")
    if len(placebo) != 3 or not all(
        item.get("comparison_digest_equal") is True
        and item.get("scientific_digest_equal") is True
        and item.get("final_state_digest_equal") is True
        and item.get("journal_digest_equal") is True
        for item in placebo
    ):
        raise PackageExportError("M02: placebo equivalence is not complete for all seeds")
    first_stage = _require_dict(results.get("first_stage"), what="M02 first_stage")
    for leg in ("budget", "investment", "demand_regime"):
        if not _require_list(first_stage.get(leg), what=f"M02 first_stage.{leg}"):
            raise PackageExportError(f"M02: empty first_stage.{leg}")
    if results.get("failure") not in (None, {}):
        raise PackageExportError("M02: study records a failure")
    fingerprint_payload = {
        key: results.get(key)
        for key in (
            "schema_version",
            "study_id",
            "status",
            "ticks_executed",
            "selected",
            "input_identity",
            "first_stage",
            "placebo_checks",
            "verdicts",
            "per_arm",
            "contrasts",
            "failure",
        )
    }
    refs = [ctx.ref(f"{study_root}/results.json"), ctx.ref(f"{study_root}/input_identity.json")]
    detail = {
        "ticks": 156,
        "arm_seeds": 39,
        "arms": 13,
        "placebo_seeds": 3,
        "opening_states_per_seed": 1,
    }
    return refs, canonical_digest(fingerprint_payload), detail


def _m02_first_stage_ok(results: dict[str, Any]) -> tuple[bool, str]:
    first_stage = results.get("first_stage")
    if not isinstance(first_stage, dict):
        return False, "first_stage is missing"
    budget = first_stage.get("budget")
    investment = first_stage.get("investment")
    demand = first_stage.get("demand_regime")
    if not isinstance(budget, list) or len(budget) != 12:
        return False, "budget first stage does not have 12 records"
    if not isinstance(investment, list) or len(investment) != 12:
        return False, "investment first stage does not have 12 records"
    if not isinstance(demand, list) or len(demand) != 18:
        return False, "demand-regime first stage does not have 18 records"
    credit_binding_by_seed: dict[int, int] = {}
    for row in budget:
        if row.get("joint_budget_leg", {}).get("status") != "BINDING":
            return False, "joint budget leg is not BINDING in every record"
        seed = int(row["seed"])
        if row.get("credit_leg", {}).get("status") == "BINDING":
            credit_binding_by_seed[seed] = credit_binding_by_seed.get(seed, 0) + 1
    if not credit_binding_by_seed:
        return False, "no credit leg is BINDING in any seed"
    for row in investment:
        if row.get("status") != "BINDING":
            return False, "investment first stage is not BINDING in every record"
        for value in row.get("differences", {}).values():
            if not _finite(value):
                return False, "investment first-stage difference is null/non-finite"
    for row in demand:
        if row.get("status") != "BINDING":
            return False, "demand-regime first stage is not BINDING in every record"
        if not row.get("differing_household_desired_channels"):
            return False, "demand-regime first stage has no differing channels"
    return True, "budget/investment/demand first stages are binding with complete records"


def _m02_metrics_ok(results: dict[str, Any]) -> tuple[bool, str]:
    per_arm = results.get("per_arm")
    if not isinstance(per_arm, dict) or len(per_arm) != 39:
        return False, "per_arm matrix is not 39 arm-seeds"
    required = (
        "shortage_expectation_mean",
        "credit_drawn_total",
        "investment_approved_total",
        "activity_realized_total",
    )
    for key, payload in per_arm.items():
        metrics = payload.get("final_quarter_metrics")
        if not isinstance(metrics, dict):
            return False, f"{key} has no final_quarter_metrics"
        for metric in required:
            if not _finite(metrics.get(metric)):
                return False, f"{key}.{metric} is null/non-finite"
    contrasts = results.get("contrasts", {}).get("by_seed_and_regime")
    if not isinstance(contrasts, list) or not contrasts:
        return False, "axis-scoped contrasts are empty"
    return True, "required shortage/credit/investment metrics and contrasts are finite"


def _m02_historical_ok(results: dict[str, Any]) -> tuple[bool, str]:
    historical = results.get("verdicts", {}).get("historical")
    if not isinstance(historical, dict):
        return False, "historical verdict is missing"
    if historical.get("identification_status") != "UNIDENTIFIED":
        return False, "historical identification is not UNIDENTIFIED"
    if historical.get("historical_support") != "NOT_ESTABLISHED":
        return False, "historical support is not NOT_ESTABLISHED"
    return True, "historical identification stays UNIDENTIFIED / NOT_ESTABLISHED"


def _m02_sensitivity_ok(results: dict[str, Any]) -> tuple[bool, str]:
    contrasts = results.get("contrasts", {}).get("by_seed_and_regime")
    if not isinstance(contrasts, list) or len(contrasts) < 6:
        return False, "less than six regime contrasts are present"
    regimes = {str(row.get("regime")) for row in contrasts if isinstance(row, dict)}
    if regimes != {"base", "reduced"}:
        return False, "both demand regimes are not present in contrasts"
    for row in contrasts:
        for key in ("budget_contrast", "investment_contrast", "difference_in_differences"):
            if key not in row:
                return False, f"contrast row lacks {key}"
    return True, "both regimes, two investment levels and DiD/TriD contrasts are present"


def _m02_counterevidence_ok(results: dict[str, Any]) -> tuple[bool, str]:
    structural = results.get("verdicts", {}).get("structural")
    if not isinstance(structural, dict):
        return False, "structural verdict is missing"
    by_regime = structural.get("by_regime")
    if not isinstance(by_regime, dict) or not by_regime:
        return False, "structural verdict has no by_regime evidence"
    non_falling = []
    for regime, payload in by_regime.items():
        if not isinstance(payload, dict):
            return False, f"structural regime {regime} is not an object"
        reason = payload.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            return False, f"structural regime {regime} has no falsification reason"
        for seed_row in payload.get("seeds_with_non_falling_shortage_axis", []):
            for axis in seed_row.get("axes", []):
                if _finite(axis.get("contrast")) and float(axis["contrast"]) >= 0.0:
                    non_falling.append((regime, axis.get("axis"), axis["contrast"]))
    if not non_falling:
        return False, "no non-falling shortage axis supports the falsification result"
    f2 = results.get("verdicts", {}).get("f2_generalisation", {})
    if f2.get("status") != "NOT_RUN":
        return False, "F2 generalisation is not marked NOT_RUN"
    return True, f"falsification is supported by {len(non_falling)} non-falling axes; F2 NOT_RUN"


def _m02_checks(
    ctx: AuditContext, index_entry: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    existing = index_entry.get("existing_root")
    if not existing:
        raise PackageExportError("M02: evidence index has no existing_root")
    study_root = str(existing)
    manifest = ctx.json("studies/HIST_VNEXT/M02/EVIDENCE_MANIFEST.json")
    summary = _require_dict(manifest.get("statistical_summary"), what="M02 statistical_summary")
    conservation = _require_dict(summary.get("conservation"), what="M02 conservation")
    legality = _require_dict(summary.get("account_legality"), what="M02 account_legality")
    try:
        refs, digest, detail = _m02_validate_run(ctx, study_root)
        results = ctx.json(f"{study_root}/results.json")
        validation_error = None
    except PackageExportError as exc:
        refs = [ctx.ref(f"{study_root}/results.json")]
        results = ctx.json(f"{study_root}/results.json")
        digest = None
        detail = {}
        validation_error = str(exc)
    accounting_problem = None
    if conservation.get("ticks_passed") != 156 or conservation.get("ticks_failed") != 0:
        accounting_problem = "conservation gate is not complete"
    elif legality.get("ticks_checked") != 156 or legality.get("invalid_legs") != 0:
        accounting_problem = "journal legality gate is not complete"
    elif (
        not _finite_number(
            conservation.get("max_material_tolerance_ratio"), what="M02 material ratio"
        )
        <= 1.0
    ):
        accounting_problem = "material tolerance ratio exceeds 1"
    elif (
        not _finite_number(
            conservation.get("max_finance_tolerance_ratio"), what="M02 finance ratio"
        )
        <= 1.0
    ):
        accounting_problem = "finance tolerance ratio exceeds 1"
    first_ok, first_reason = _m02_first_stage_ok(results)
    metrics_ok, metrics_reason = _m02_metrics_ok(results)
    historical_ok, historical_reason = _m02_historical_ok(results)
    sensitivity_ok, sensitivity_reason = _m02_sensitivity_ok(results)
    counter_ok, counter_reason = _m02_counterevidence_ok(results)
    checks = {
        "paired_control": (
            _ok(
                "three seeds x thirteen arms; one shared opening state per seed and a full 39 "
                "arm-seed matrix",
                refs,
            )
            if validation_error is None
            else _blocked(f"paired/accounting validation failed: {validation_error}", refs)
        ),
        "first_stage_checked": (
            _ok(
                first_reason, [ctx.ref(f"{study_root}/results.json", pointer="/first_stage"), *refs]
            )
            if first_ok
            else _blocked(
                first_reason, [ctx.ref(f"{study_root}/results.json", pointer="/first_stage")]
            )
        ),
        "accounting_checked": (
            _ok(
                "156/156 ticks pass conservation; "
                f"{legality['journal_legs_checked']} journal legs checked with "
                f"{legality['invalid_legs']} invalid; material/finance ratios <= 1",
                [
                    ctx.ref(
                        "studies/HIST_VNEXT/M02/EVIDENCE_MANIFEST.json",
                        pointer="/statistical_summary/conservation",
                    ),
                    ctx.ref(
                        "studies/HIST_VNEXT/M02/EVIDENCE_MANIFEST.json",
                        pointer="/statistical_summary/account_legality",
                    ),
                    *refs,
                ],
            )
            if accounting_problem is None and validation_error is None
            else _blocked(
                f"accounting evidence failed: {accounting_problem or validation_error}",
                refs,
            )
        ),
        "negative_control": (
            _ok(
                "placebo_soft_low_base is bit-identical to soft_low_base on comparison, "
                "scientific, final-state and journal digests in all three seeds",
                [ctx.ref(f"{study_root}/results.json", pointer="/placebo_checks"), *refs],
            )
            if validation_error is None
            else _blocked(f"placebo validation failed: {validation_error}", refs)
        ),
        "metrics_generated": (
            _ok(metrics_reason, [ctx.ref(f"{study_root}/results.json", pointer="/per_arm"), *refs])
            if metrics_ok
            else _blocked(
                metrics_reason, [ctx.ref(f"{study_root}/results.json", pointer="/per_arm")]
            )
        ),
        "sensitivity_or_reason_not_run": (
            _ok(
                sensitivity_reason,
                [ctx.ref(f"{study_root}/results.json", pointer="/contrasts"), *refs],
            )
            if sensitivity_ok
            else _blocked(
                sensitivity_reason, [ctx.ref(f"{study_root}/results.json", pointer="/contrasts")]
            )
        ),
        "historical_evidence_grade": (
            _ok(
                historical_reason,
                [ctx.ref(f"{study_root}/results.json", pointer="/verdicts"), *refs],
                level="VERIFIED_BY_CODE",
            )
            if historical_ok
            else _blocked(
                historical_reason,
                [ctx.ref(f"{study_root}/results.json", pointer="/verdicts")],
            )
        ),
        "counterevidence": (
            _ok(
                counter_reason,
                [
                    ctx.ref(
                        f"{study_root}/results.json",
                        pointer="/verdicts/structural/by_regime/base",
                    ),
                    ctx.ref("studies/HIST_VNEXT/M02/spec.json", pointer="/falsification_rule"),
                ],
            )
            if counter_ok
            else _blocked(
                counter_reason,
                [ctx.ref(f"{study_root}/results.json", pointer="/verdicts/structural")],
            )
        ),
    }
    reproduction = (
        _reproduction_from_index(
            ctx,
            index_entry,
            verifier=_m02_validate_run,
            refs=refs,
            existing_digest=digest,
            what="M02",
        )
        if validation_error is None
        else _blocked(f"reproduction validation failed: {validation_error}", refs)
    )
    checks["reproduction_bundle"] = reproduction
    reproduction_payload = {
        "existing_root": index_entry.get("existing_root"),
        "fresh_root": index_entry.get("fresh_root"),
        "repeat_root": index_entry.get("repeat_root"),
        "commands": list(CARD_DEFINITIONS["M02"].commands),
        "scientific_digest": digest,
        "status": reproduction["status"],
        "reason": reproduction["reason"],
        "accounting": detail,
    }
    study_metrics = []
    for arm_seed, payload in ctx.json(f"{study_root}/results.json")["per_arm"].items():
        for metric in (
            "credit_drawn_total",
            "investment_approved_total",
            "shortage_expectation_mean",
        ):
            value = payload["final_quarter_metrics"].get(metric)
            if _finite(value):
                study_metrics.append(
                    {
                        "metric": metric,
                        "value": float(value),
                        "unit": "study-level (M02 final quarter)",
                        "selector": {"arm_seed": arm_seed},
                        "status": "observed",
                    }
                )
    verdicts = ctx.json(f"{study_root}/results.json")["verdicts"]
    return (
        checks,
        {
            "technical": "PASS",
            "structural": "FALSIFICATION_MET_SYNTHETIC_WINDOW",
            "historical": "UNIDENTIFIED",
        },
        {
            "metrics": study_metrics,
            "manifest": manifest,
            "study": ctx.json(f"{study_root}/results.json"),
            "failed_seeds": list(manifest.get("failed_seeds") or []),
            "reproduction": reproduction_payload,
            "verdicts": verdicts,
        },
    )


# --- M03 -------------------------------------------------------------------


def _m03_checks(
    ctx: AuditContext, index_entry: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    acceptance = ctx.json("studies/HIST_VNEXT/M03/IMPLEMENTATION_ACCEPTANCE.json")
    manifest = ctx.json("studies/HIST_VNEXT/M03/IMPLEMENTATION_EVIDENCE_MANIFEST.json")
    matrix = _require_list(manifest.get("acceptance_matrix"), what="M03 acceptance matrix")
    statuses = {str(item.get("id")): item.get("status") for item in matrix}
    for required in ("N1", "N2", "N3"):
        if statuses.get(required) != "PASS":
            raise PackageExportError(f"M03: negative control {required} is not PASS")
    verdicts = _require_dict(acceptance.get("verdicts"), what="M03 verdicts")
    if verdicts.get("technical") != "PASS" or verdicts.get("structural") != "PASS_SYNTHETIC":
        raise PackageExportError(
            "M03: accepted technical/structural verdict is not the recorded PASS_SYNTHETIC"
        )
    if verdicts.get("historical") != "UNIDENTIFIED":
        raise PackageExportError("M03: historical verdict is not UNIDENTIFIED")
    bundle = _require_dict(manifest.get("bundle_resume_check"), what="M03 bundle_resume_check")
    for scenario in ("c0", "c1", "intermediate8"):
        item = _require_dict(bundle.get(scenario), what=f"M03 bundle {scenario}")
        if not all(item.get(key) is True for key in ("core_equal", "labor_equal", "metrics_equal")):
            raise PackageExportError(f"M03: resume equality fails for {scenario}")
    refs = [
        ctx.ref("studies/HIST_VNEXT/M03/IMPLEMENTATION_ACCEPTANCE.json"),
        ctx.ref(
            "studies/HIST_VNEXT/M03/IMPLEMENTATION_EVIDENCE_MANIFEST.json",
            pointer="/acceptance_matrix",
        ),
        ctx.ref("studies/HIST_VNEXT/M03/IMPLEMENTATION_REPORT.md", line=6),
    ]
    checks = {
        "paired_control": _blocked(
            "the accepted implementation spec has no per-seed paired treatment/control "
            "matrix; R/A/N rows are implementation checks, not paired experiments",
            refs,
        ),
        "first_stage_checked": _not_run(
            "no policy first-stage exists in the opt-in labour implementation; N2 "
            "demonstrates rule mechanics, not a treatment first stage",
            refs,
        ),
        "accounting_checked": _blocked(
            "no per-tick ledger/conservation summary is sealed in the implementation "
            "manifest; only resume and legacy digest equality are recorded",
            refs,
        ),
        "negative_control": _ok(
            "preregistered N1 wage processing, N2 employment rule and N3 side-work double "
            "counting all executed and PASS",
            [
                ctx.ref(
                    "studies/HIST_VNEXT/M03/IMPLEMENTATION_EVIDENCE_MANIFEST.json",
                    pointer="/acceptance_matrix",
                )
            ],
        ),
        "metrics_generated": _ok(
            "labour metrics are recorded with finite values, real zero-denominator nulls "
            "and raw counts",
            [
                ctx.ref(
                    "studies/HIST_VNEXT/M03/IMPLEMENTATION_EVIDENCE_MANIFEST.json",
                    pointer="/metrics",
                )
            ],
        ),
        "sensitivity_or_reason_not_run": _not_run(
            "no preregistered sensitivity experiment exists for the labour implementation; "
            "default-off equality is compatibility, not sensitivity",
            refs,
        ),
        "historical_evidence_grade": _ok(
            "historical and institutional-attribution verdicts remain UNIDENTIFIED; no "
            "admitted historical series or calibrated parameter is claimed",
            [ctx.ref("studies/HIST_VNEXT/M03/IMPLEMENTATION_ACCEPTANCE.json", pointer="/verdicts")],
            level="VERIFIED_BY_CODE",
        ),
        "counterevidence": _ok(
            "PASS_SYNTHETIC is separated from institutional attribution UNIDENTIFIED; "
            "N1-N3 are engineering counterexamples, not historical attribution",
            [ctx.ref("studies/HIST_VNEXT/M03/IMPLEMENTATION_REPORT.md", line=6)],
        ),
    }
    reproduction = _reproduction_from_index(
        ctx,
        index_entry,
        verifier=None,
        refs=refs,
        existing_digest=None,
        what="M03",
    )
    checks["reproduction_bundle"] = reproduction
    study_metrics = []
    metrics_doc = _require_dict(manifest.get("metrics"), what="M03 metrics")
    for metric, value in metrics_doc.items():
        if isinstance(value, dict):
            for key, nested in value.items():
                if _finite(nested):
                    study_metrics.append(
                        {
                            "metric": f"{metric}.{key}",
                            "value": float(nested),
                            "unit": "labour study unit (spec-bound)",
                            "selector": {"section": metric, "field": key},
                            "status": "observed",
                        }
                    )
        elif _finite(value):
            study_metrics.append(
                {
                    "metric": metric,
                    "value": float(value),
                    "unit": "labour study unit (spec-bound)",
                    "selector": {"section": metric},
                    "status": "observed",
                }
            )
    return (
        checks,
        {
            "technical": verdicts["technical"],
            "structural": verdicts["structural"],
            "historical": verdicts["historical"],
        },
        {
            "metrics": study_metrics,
            "manifest": manifest,
            "study": acceptance,
            "failed_seeds": list(manifest.get("failed_seeds") or []),
            "reproduction": {
                "existing_root": index_entry.get("existing_root"),
                "fresh_root": index_entry.get("fresh_root"),
                "repeat_root": index_entry.get("repeat_root"),
                "commands": list(CARD_DEFINITIONS["M03"].commands),
                "scientific_digest": None,
                "status": reproduction["status"],
                "reason": reproduction["reason"],
            },
        },
    )


# --- M04 -------------------------------------------------------------------


def _m04_validate_run(
    ctx: AuditContext, study_root: str
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    study = _require_dict(ctx.json(f"{study_root}/study.json"), what="M04 study.json")
    if study.get("status") != "COMPLETED" or study.get("mode") != "study":
        raise PackageExportError("M04: study mode did not complete")
    if study.get("ticks") != 16:
        raise PackageExportError("M04: study is not the 16-tick design")
    seeds = [int(seed) for seed in _require_list(study.get("seeds"), what="M04 seeds")]
    arms = _require_dict(study.get("arms"), what="M04 arms")
    if (
        len(seeds) != 3
        or len(set(seeds)) != 3
        or set(arms) != {"tolerance_0", "tolerance_05", "tolerance_1"}
    ):
        raise PackageExportError("M04: expected 3 seeds x 3 tolerance arms")
    max_pool = 0.0
    max_input = 0.0
    first_stage: dict[int, dict[str, float]] = {seed: {} for seed in seeds}
    opening_by_seed: dict[int, set[tuple[float, float, float]]] = {seed: set() for seed in seeds}
    for arm_name, per_seed in arms.items():
        if not isinstance(per_seed, dict):
            raise PackageExportError(f"M04: arm {arm_name} is not a seed map")
        for seed_text, payload in per_seed.items():
            seed = int(seed_text)
            if seed not in first_stage:
                raise PackageExportError(f"M04: undeclared seed {seed}")
            item = _require_dict(payload, what=f"M04 {arm_name}/{seed}")
            if item.get("completed_ticks") != 16:
                raise PackageExportError(f"M04: {arm_name}/{seed} did not complete 16 ticks")
            ticks = _require_list(item.get("ticks"), what=f"M04 {arm_name}/{seed} ticks")
            if len(ticks) != 16:
                raise PackageExportError(f"M04: {arm_name}/{seed} has {len(ticks)} ticks")
            residuals = _require_list(
                item.get("pool_residuals"), what=f"M04 {arm_name}/{seed} residuals"
            )
            if len(residuals) != 16:
                raise PackageExportError(f"M04: {arm_name}/{seed} has incomplete pool residuals")
            for row in residuals:
                max_pool = max(
                    max_pool,
                    abs(_finite_number(row.get("f2_pool_residual"), what="M04 pool residual")),
                )
                max_input = max(
                    max_input,
                    abs(_finite_number(row.get("f2_input_residual"), what="M04 input residual")),
                )
            opening_by_seed[seed].add(
                (
                    float(item.get("household_cash_open", 0.0)),
                    float(item.get("org_cash_open", 0.0)),
                    float(item.get("bank_balance_open", 0.0)),
                )
            )
            first_stage[seed][arm_name] = sum(
                _finite_number(tick.get("second_hours_total"), what="M04 second_hours_total")
                for tick in ticks
            )
    for seed in seeds:
        if len(opening_by_seed[seed]) != 1:
            raise PackageExportError(
                f"M04: seed {seed} does not share one opening pool across arms"
            )
        values = first_stage[seed]
        if values["tolerance_0"] != 0.0:
            raise PackageExportError(f"M04: negative-control arm is not zero for seed {seed}")
        if not (values["tolerance_05"] > 0.0 and values["tolerance_1"] > values["tolerance_05"]):
            raise PackageExportError(f"M04: tolerance first stage is not monotone for seed {seed}")
    if max_pool > 1e-9 or max_input > 1e-9:
        raise PackageExportError("M04: F2 pool/input residual exceeds the 1e-9 engineering gate")
    refs = [ctx.ref(f"{study_root}/study.json")]
    detail = {
        "ticks": 16,
        "arms": 3,
        "seeds": 3,
        "max_pool_residual": max_pool,
        "max_input_residual": max_input,
    }
    return refs, canonical_digest(study), detail


def _m04_first_stage_ok(study: dict[str, Any]) -> tuple[bool, str]:
    seeds = [int(seed) for seed in study.get("seeds", [])]
    arms = study.get("arms")
    if not isinstance(arms, dict) or set(arms) != {"tolerance_0", "tolerance_05", "tolerance_1"}:
        return False, "tolerance arms are incomplete"
    for seed in seeds:
        values: dict[str, float] = {}
        for arm_name in ("tolerance_0", "tolerance_05", "tolerance_1"):
            payload = arms.get(arm_name, {}).get(str(seed))
            if not isinstance(payload, dict):
                return False, f"{arm_name}/{seed} is missing"
            ticks = payload.get("ticks")
            if not isinstance(ticks, list) or len(ticks) != 16:
                return False, f"{arm_name}/{seed} does not have 16 ticks"
            total = 0.0
            for tick in ticks:
                value = tick.get("second_hours_total")
                if not _finite(value):
                    return False, f"{arm_name}/{seed} second_hours_total is null/non-finite"
                total += float(value)
            values[arm_name] = total
        if values["tolerance_0"] != 0.0:
            return False, f"negative-control arm is not zero for seed {seed}"
        if not (values["tolerance_05"] > 0.0 and values["tolerance_1"] > values["tolerance_05"]):
            return False, f"tolerance first stage is not monotone for seed {seed}"
    return True, "tolerance_0 < tolerance_05 < tolerance_1 in every seed"


def _m04_metrics_ok(study: dict[str, Any]) -> tuple[bool, str]:
    required = (
        "second_hours_total",
        "formal_unmet_total",
        "formal_sales_total",
        "funding_total",
        "plot_self_weighted",
        "plot_market_weighted",
    )
    arms = study.get("arms")
    if not isinstance(arms, dict) or not arms:
        return False, "arms are missing"
    for arm_name, per_seed in arms.items():
        for seed, payload in per_seed.items():
            for tick in payload.get("ticks", []):
                for metric in required:
                    if not _finite(tick.get(metric)):
                        return (
                            False,
                            f"{arm_name}/{seed}/tick {tick.get('tick')} "
                            f"{metric} is null/non-finite",
                        )
    return True, "required formal/plot metrics are finite for every arm-seed-tick"


def _m04_sensitivity_ok(study: dict[str, Any]) -> tuple[bool, str]:
    arms = study.get("arms")
    if not isinstance(arms, dict) or set(arms) != {"tolerance_0", "tolerance_05", "tolerance_1"}:
        return False, "three preregistered tolerance arms are not present"
    seeds = [str(seed) for seed in study.get("seeds", [])]
    for seed in seeds:
        tolerances = set()
        for arm_name, payload in arms.items():
            item = payload.get(seed) if isinstance(payload, dict) else None
            if not isinstance(item, dict) or item.get("completed_ticks") != 16:
                return False, f"{arm_name}/{seed} did not complete 16 ticks"
            tolerances.add(float(item.get("tolerance")))
        if tolerances != {0.0, 0.5, 1.0}:
            return False, f"tolerance levels are incomplete for seed {seed}"
    return True, "all three preregistered tolerance levels executed for every seed"


def _m04_counterevidence_ok(manifest: dict[str, Any], study: dict[str, Any]) -> tuple[bool, str]:
    summary = manifest.get("statistical_summary")
    if not isinstance(summary, dict):
        return False, "statistical_summary is missing"
    first_stage = summary.get("first_stage")
    if not isinstance(first_stage, str) or "saturat" not in first_stage.lower():
        return False, "capacity-ceiling bound is not recorded in the first-stage summary"
    failures = manifest.get("process_failures")
    if not isinstance(failures, list) or not failures:
        return False, "process failures are not preserved separately"
    if study.get("treatment_only") is not True:
        return False, "study does not declare treatment_only"
    return True, "capacity-ceiling bound and preserved process failure are recorded"


def _m04_checks(
    ctx: AuditContext, index_entry: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    existing = index_entry.get("existing_root")
    if not existing:
        raise PackageExportError("M04: evidence index has no existing_root")
    study_root = str(existing)
    study = ctx.json(f"{study_root}/study.json")
    manifest = ctx.json("studies/HIST_VNEXT/M04/EVIDENCE_MANIFEST.json")
    summary = _require_dict(manifest.get("statistical_summary"), what="M04 statistical_summary")
    if summary.get("admitted_ticks") != 144 or summary.get("failed_ticks") != 0:
        raise PackageExportError("M04: admitted tick count/failed ticks contradict the study")
    try:
        refs, digest, detail = _m04_validate_run(ctx, study_root)
        validation_error = None
    except PackageExportError as exc:
        refs = [ctx.ref(f"{study_root}/study.json")]
        digest = None
        detail = {}
        validation_error = str(exc)
    first_ok, first_reason = _m04_first_stage_ok(study)
    metrics_ok, metrics_reason = _m04_metrics_ok(study)
    sensitivity_ok, sensitivity_reason = _m04_sensitivity_ok(study)
    counter_ok, counter_reason = _m04_counterevidence_ok(manifest, study)
    checks = {
        "paired_control": (
            _ok(
                "3 seeds x 3 tolerance arms; one shared opening pool per seed; all 144 "
                "arm-ticks completed",
                refs,
            )
            if validation_error is None
            else _blocked(f"paired/accounting validation failed: {validation_error}", refs)
        ),
        "first_stage_checked": (
            _ok(
                first_reason,
                [ctx.ref("studies/HIST_VNEXT/M04/REPORT.md", line=114), *refs],
            )
            if first_ok
            else _blocked(first_reason, [ctx.ref(f"{study_root}/study.json", pointer="/arms")])
        ),
        "accounting_checked": (
            _ok(
                f"144/144 arm-ticks with per-tick F2 pool and input closure; max residuals "
                f"{detail['max_pool_residual']:.3e}/{detail['max_input_residual']:.3e}",
                refs,
            )
            if validation_error is None
            else _blocked(f"per-tick accounting validation failed: {validation_error}", refs)
        ),
        "negative_control": (
            _ok(
                "tolerance_0 is an executed zero arm: no second hours, input purchase, "
                "production or funding",
                [ctx.ref(f"{study_root}/study.json", pointer="/arms/tolerance_0"), *refs],
            )
            if first_ok
            else _blocked(
                first_reason, [ctx.ref(f"{study_root}/study.json", pointer="/arms/tolerance_0")]
            )
        ),
        "metrics_generated": (
            _ok(metrics_reason, [ctx.ref(f"{study_root}/study.json", pointer="/arms"), *refs])
            if metrics_ok
            else _blocked(metrics_reason, [ctx.ref(f"{study_root}/study.json", pointer="/arms")])
        ),
        "sensitivity_or_reason_not_run": (
            _ok(
                sensitivity_reason,
                [ctx.ref("studies/HIST_VNEXT/M04/spec.json", pointer="/arms"), *refs],
            )
            if sensitivity_ok
            else _blocked(
                sensitivity_reason,
                [ctx.ref(f"{study_root}/study.json", pointer="/arms")],
            )
        ),
        "historical_evidence_grade": (
            _ok(
                "historical identification remains UNIDENTIFIED; the F2 axis is declared, not "
                "identified",
                [ctx.ref(f"{study_root}/study.json", pointer="/treatment_only"), *refs],
                level="VERIFIED_BY_CODE",
            )
            if study.get("treatment_only") is True
            else _blocked(
                "study does not declare treatment_only / UNIDENTIFIED F2",
                [ctx.ref(f"{study_root}/study.json", pointer="/treatment_only")],
            )
        ),
        "counterevidence": (
            _ok(
                counter_reason,
                [
                    ctx.ref(
                        "studies/HIST_VNEXT/M04/EVIDENCE_MANIFEST.json",
                        pointer="/process_failures",
                    ),
                    ctx.ref(
                        "studies/HIST_VNEXT/M04/EVIDENCE_MANIFEST.json",
                        pointer="/statistical_summary/first_stage",
                    ),
                ],
            )
            if counter_ok
            else _blocked(
                counter_reason,
                [
                    ctx.ref(
                        "studies/HIST_VNEXT/M04/EVIDENCE_MANIFEST.json",
                        pointer="/statistical_summary",
                    )
                ],
            )
        ),
    }
    reproduction = (
        _reproduction_from_index(
            ctx,
            index_entry,
            verifier=_m04_validate_run,
            refs=refs,
            existing_digest=digest,
            what="M04",
        )
        if validation_error is None
        else _blocked(f"reproduction validation failed: {validation_error}", refs)
    )
    checks["reproduction_bundle"] = reproduction
    study_metrics = []
    for arm_name, per_seed in study["arms"].items():
        for seed, payload in per_seed.items():
            for tick in payload["ticks"]:
                for metric in (
                    "second_hours_total",
                    "formal_unmet_total",
                    "formal_sales_total",
                    "funding_total",
                ):
                    value = tick.get(metric)
                    if _finite(value):
                        study_metrics.append(
                            {
                                "metric": metric,
                                "value": float(value),
                                "unit": "study-level (M04 tick)",
                                "selector": {"arm": arm_name, "seed": seed, "tick": tick["tick"]},
                                "status": "observed",
                            }
                        )
    failed_seeds = (
        []
        if all(
            payload.get("completed_ticks") == 16
            for per_seed in study["arms"].values()
            for payload in per_seed.values()
        )
        else None
    )
    return (
        checks,
        {
            "technical": "PASS",
            "structural": "FIRST_STAGE_SUPPORTED_WITH_CAPACITY_CEILING",
            "historical": "UNIDENTIFIED",
        },
        {
            "metrics": study_metrics,
            "manifest": manifest,
            "study": study,
            "failed_seeds": failed_seeds,
            "preserved_failures": manifest.get("process_failures") or [],
            "reproduction": {
                "existing_root": index_entry.get("existing_root"),
                "fresh_root": index_entry.get("fresh_root"),
                "repeat_root": index_entry.get("repeat_root"),
                "commands": list(CARD_DEFINITIONS["M04"].commands),
                "scientific_digest": digest,
                "status": reproduction["status"],
                "reason": reproduction["reason"],
                "accounting": detail,
            },
        },
    )


# --- M09 -------------------------------------------------------------------


def _m09_validate_run(
    ctx: AuditContext, study_root: str
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    science = _require_dict(ctx.json(f"{study_root}/science.json"), what="M09 science.json")
    if science.get("mode") != "study":
        raise PackageExportError("M09: science.json is not a study package")
    if science.get("historical_status") != "NOT_RUN":
        raise PackageExportError("M09: historical status must stay NOT_RUN")
    if science.get("registration_status_changed") is not False:
        raise PackageExportError("M09: registration status changed")
    if science.get("structural_status") != "SYNTHETIC_ENGINEERING_PROFILE":
        raise PackageExportError("M09: structural profile was promoted")
    scenario = _require_dict(science.get("scenario"), what="M09 scenario")
    seeds = [int(seed) for seed in _require_list(scenario.get("seeds"), what="M09 seeds")]
    arms = [str(arm) for arm in _require_list(science.get("arms"), what="M09 arms")]
    if len(seeds) != 3 or len(set(seeds)) != 3:
        raise PackageExportError("M09: expected three distinct seeds")
    if len(arms) != 4 or len(set(arms)) != 4:
        raise PackageExportError("M09: expected four arms")
    records = _require_list(science.get("records"), what="M09 records")
    if len(records) != 48:
        raise PackageExportError(f"M09: expected 48 paired records, found {len(records)}")
    cells = set()
    max_material = 0.0
    max_finance = 0.0
    for record in records:
        seed = int(record["seed"])
        arm = str(record["arm"])
        target = str(record["target_quarter"])
        issued = str(record["issued_quarter"])
        cells.add((seed, arm, target))
        for key in ("prediction", "realized_value", "residual", "absolute_error"):
            _finite_number(record.get(key), what=f"M09 record {key}")
        if target <= issued:
            raise PackageExportError("M09: target is not after issuance")
    if len(cells) != 48:
        raise PackageExportError("M09: paired records do not cover 3x4x4 cells")
    first_stage_check = _require_dict(
        science.get("first_stage_check"), what="M09 first_stage_check"
    )
    if (
        first_stage_check.get("status") != "ESTABLISHED"
        or first_stage_check.get("changed_sets") != 24
    ):
        raise PackageExportError("M09: information first stage is not ESTABLISHED for all 24 sets")
    if first_stage_check.get("unchanged_sets") != 0:
        raise PackageExportError("M09: information first stage has unchanged sets")
    first_stage = _require_list(science.get("first_stage"), what="M09 first_stage")
    if len(first_stage) != 48:
        raise PackageExportError("M09: first-stage evidence is incomplete")
    ticks = _require_list(science.get("ticks"), what="M09 ticks")
    if len(ticks) < 48:
        raise PackageExportError("M09: tick evidence is incomplete")
    for tick in ticks:
        accounting = tick.get("accounting")
        if isinstance(accounting, dict):
            if accounting.get("invariant_gate") != "passed":
                raise PackageExportError("M09: invariant gate did not pass")
            if accounting.get("journal_rows_intact") is not True:
                raise PackageExportError("M09: journal rows are not intact")
            material = accounting.get("gate_max_material_abs_residual")
            finance = accounting.get("gate_max_finance_abs_residual")
            material_ratio = accounting.get("gate_max_material_tolerance_ratio")
            finance_ratio = accounting.get("gate_max_finance_tolerance_ratio")
            if _finite(material_ratio) and float(material_ratio) > 1.0:
                raise PackageExportError("M09: material tolerance ratio exceeds 1")
            if _finite(finance_ratio) and float(finance_ratio) > 1.0:
                raise PackageExportError("M09: finance tolerance ratio exceeds 1")
        else:
            material = tick.get("material_max_abs_residual")
            finance = tick.get("finance_max_abs_residual")
        max_material = max(
            max_material,
            abs(_finite_number(material, what="M09 material residual")),
        )
        max_finance = max(
            max_finance,
            abs(_finite_number(finance, what="M09 finance residual")),
        )
    if max_material > 1e-6 or max_finance > 1e-6:
        raise PackageExportError("M09: per-tick gate residual exceeds 1e-6")
    ledger = _require_dict(ctx.json(f"{study_root}/ledger.json"), what="M09 ledger.json")
    if ledger.get("record_count") != 48 or ledger.get("expected_record_count") != 48:
        raise PackageExportError("M09: ledger record count is not 48")
    if ledger.get("failed_seeds"):
        raise PackageExportError("M09: ledger records failed seeds")
    refs = [
        ctx.ref(f"{study_root}/science.json"),
        ctx.ref(f"{study_root}/ledger.json"),
        ctx.ref(f"{study_root}/manifest.json"),
    ]
    detail = {
        "ticks": len(ticks),
        "records": 48,
        "first_stage_sets": 24,
        "max_material_abs_residual": max_material,
        "max_finance_abs_residual": max_finance,
    }
    return refs, canonical_digest(science), detail


def _m09_checks(
    ctx: AuditContext, index_entry: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    existing = index_entry.get("existing_root")
    if not existing:
        raise PackageExportError("M09: evidence index has no existing_root")
    study_root = str(existing)
    refs, digest, detail = _m09_validate_run(ctx, study_root)
    science = ctx.json(f"{study_root}/science.json")
    manifest = ctx.json("studies/HIST_VNEXT/M09/EVIDENCE_MANIFEST.json")
    failed = ctx.json("studies/HIST_VNEXT/M09/FAILED_SEEDS.json")
    if failed.get("checked_pairs") != 48:
        raise PackageExportError("M09: FAILED_SEEDS does not cover 48 checked pairs")
    checks = {
        "paired_control": _ok(
            "48 seed-arm-target records cover the full 3x4x4 matrix; each seed has one "
            "branch state; the report discloses that the 16 cells replicate across seeds",
            [ctx.ref(f"{study_root}/science.json", pointer="/records"), *refs],
        ),
        "first_stage_checked": _ok(
            "all 24 delay x seed x issue-quarter comparisons change the available report "
            "set; no unchanged set",
            [ctx.ref(f"{study_root}/science.json", pointer="/first_stage_check"), *refs],
        ),
        "accounting_checked": _ok(
            f"{detail['ticks']} ticks; max material residual "
            f"{detail['max_material_abs_residual']:.3e}, max finance residual "
            f"{detail['max_finance_abs_residual']:.3e}, both <= 1e-6",
            refs,
        ),
        "negative_control": _blocked(
            "no dedicated preregistered negative-control arm/artifact is sealed; the "
            "saturated-action null is recorded, but it is not a designated control",
            [ctx.ref("studies/HIST_VNEXT/M09/REPORT.md", line=106)],
        ),
        "metrics_generated": _ok(
            "prediction, realized, residual, MAE and per-region energy outcomes are finite "
            "and unit-bearing; no cross-commodity sum",
            [ctx.ref(f"{study_root}/science.json", pointer="/matrix"), *refs],
        ),
        "sensitivity_or_reason_not_run": _ok(
            "2x2 delay x method matrix with per-seed 2x2 effects is executed; no p-value "
            "or power claim",
            [ctx.ref(f"{study_root}/science.json", pointer="/matrix"), *refs],
        ),
        "historical_evidence_grade": _ok(
            "historical validation is NOT_RUN, the registration is unchanged, and the "
            "synthetic profile is not history",
            [ctx.ref("studies/HIST_VNEXT/M09/REPORT.md", line=1), *refs],
            level="VERIFIED_BY_CODE",
        ),
        "counterevidence": _ok(
            "the action channel saturates; identical economic outcomes within seed are a "
            "valid null, not a welfare effect; the pre-fix failure is preserved",
            [
                ctx.ref("studies/HIST_VNEXT/M09/REPORT.md", line=122),
                ctx.ref("studies/HIST_VNEXT/M09/REPORT.md", line=205),
                ctx.ref("studies/HIST_VNEXT/M09/FAILED_SEEDS.json", pointer="/preserved_failures"),
            ],
        ),
    }
    reproduction = _reproduction_from_index(
        ctx,
        index_entry,
        verifier=_m09_validate_run,
        refs=refs,
        existing_digest=digest,
        what="M09",
    )
    checks["reproduction_bundle"] = reproduction
    study_metrics = []
    for record in science["records"]:
        for metric in ("prediction", "realized_value", "residual", "absolute_error"):
            study_metrics.append(
                {
                    "metric": metric,
                    "value": float(record[metric]),
                    "unit": "p02_energy_unit",
                    "selector": {
                        "seed": record["seed"],
                        "arm": record["arm"],
                        "target_quarter": record["target_quarter"],
                    },
                    "status": "observed",
                }
            )
    return (
        checks,
        {
            "technical": "PASS",
            "structural": "SYNTHETIC_ENGINEERING_PROFILE",
            "historical": "NOT_RUN",
        },
        {
            "metrics": study_metrics,
            "manifest": manifest,
            "study": science,
            "failed_seeds": list(science.get("failed_seeds") or []),
            "preserved_failures": failed.get("preserved_failures") or [],
            "reproduction": {
                "existing_root": index_entry.get("existing_root"),
                "fresh_root": index_entry.get("fresh_root"),
                "repeat_root": index_entry.get("repeat_root"),
                "commands": list(CARD_DEFINITIONS["M09"].commands),
                "scientific_digest": digest,
                "status": reproduction["status"],
                "reason": reproduction["reason"],
                "accounting": detail,
            },
        },
    )


# --- blocked / not-started cards -------------------------------------------


def _blocked_card_checks(
    ctx: AuditContext,
    definition: CardDefinition,
    manifest: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    refs = [
        ctx.ref(definition.manifest_path, pointer="/blocking_code"),
        ctx.ref(definition.review_path),
        ctx.ref(definition.report_path),
    ]
    code = str((manifest or {}).get("blocking_code") or "UNSPECIFIED_BLOCKER")
    historical = _generic_historical_check(
        ctx,
        definition,
        manifest,
        None,
        status_value="BLOCKED",
        reason=f"{code} blocks the experiment",
    )
    checks = {
        "experiment_declared": _not_run(f"blocker-only package: {code}", refs),
        "paired_control": _not_run("no paired experiment was run", refs),
        "first_stage_checked": _not_run("no treatment first stage was run", refs),
        "accounting_checked": _not_run("no simulation ledger was produced", refs),
        "negative_control": _not_run("no negative control was run", refs),
        "metrics_generated": _not_run("no study metrics were generated", refs),
        "sensitivity_or_reason_not_run": _not_run(
            f"no sensitivity was run; the blocker reason is {code}", refs
        ),
        "historical_evidence_grade": historical,
        "counterevidence": _ok(
            f"the sealed blocker is {code}; it is counterevidence against treating this "
            f"card as researched",
            refs,
        ),
        "reproduction_bundle": _not_run("no simulation exists to replay", refs),
    }
    verdicts = {
        "technical": "BLOCKED",
        "structural": "NOT_RUN",
        "historical": "UNIDENTIFIED",
    }
    failed_seeds = (
        (manifest or {}).get("seeds", {}).get("failed_seeds")
        if isinstance((manifest or {}).get("seeds"), dict)
        else None
    )
    return (
        checks,
        verdicts,
        {
            "metrics": [],
            "manifest": manifest,
            "failed_seeds": failed_seeds,
            "blockers": [code],
        },
    )


def _not_started_checks(
    ctx: AuditContext,
    definition: CardDefinition,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    declaration = ctx.json(definition.declaration_path)
    refs = [ctx.ref(definition.declaration_path), ctx.ref(definition.card_path)]
    reason = (
        declaration.get("blocked_reason") or declaration.get("declared_reason") or "not executed"
    )
    historical = _generic_historical_check(
        ctx,
        definition,
        None,
        None,
        status_value="UNIDENTIFIED",
        reason=str(reason),
    )
    checks = {
        "experiment_declared": _not_run(
            f"dedicated experiment not created; declaration reason: {reason}", refs
        ),
        "paired_control": _not_run("experiment NOT_STARTED", refs),
        "first_stage_checked": _not_run("experiment NOT_STARTED", refs),
        "accounting_checked": _not_run("experiment NOT_STARTED", refs),
        "negative_control": _not_run("experiment NOT_STARTED", refs),
        "metrics_generated": _not_run("experiment NOT_STARTED", refs),
        "sensitivity_or_reason_not_run": _not_run(
            f"experiment NOT_STARTED; recorded reason: {reason}", refs
        ),
        "historical_evidence_grade": historical,
        "counterevidence": _not_run(
            "no experimental negative result exists; the declaration only records a "
            "prerequisite gap",
            refs,
        ),
        "reproduction_bundle": _not_run("no run exists to replay", refs),
    }
    return (
        checks,
        {
            "technical": "NOT_RUN",
            "structural": "NOT_RUN",
            "historical": "UNIDENTIFIED",
        },
        {
            "metrics": [],
            "declaration": declaration,
            "manifest": None,
            "failed_seeds": None,
            "blockers": [str(reason)],
        },
    )


# ---------------------------------------------------------------------------
# Reproduction bundle
# ---------------------------------------------------------------------------


RunVerifier = Callable[[AuditContext, str], tuple[list[dict[str, Any]], str, dict[str, Any]]]


def _reproduction_from_index(
    ctx: AuditContext,
    index_entry: Mapping[str, Any],
    *,
    verifier: RunVerifier | None,
    refs: list[dict[str, Any]],
    existing_digest: str | None,
    what: str,
) -> dict[str, Any]:
    if ctx.mode == "git-only":
        return _blocked(
            "git-only mode intentionally does not access ignored local run outputs; no "
            "fresh/repeat replay is claimed",
            refs,
        )
    if verifier is None:
        return _blocked(
            "no fresh/repeat full-study replay is recorded for this implementation package",
            refs,
        )
    existing_root = index_entry.get("existing_root")
    fresh_root = index_entry.get("fresh_root")
    repeat_root = index_entry.get("repeat_root")
    if not existing_root:
        return _not_run("no existing evidence root is registered", refs)
    if not fresh_root or not repeat_root:
        return _blocked(
            "fresh_root and repeat_root must both be present for an independent replay",
            refs,
        )
    if existing_root == fresh_root or existing_root == repeat_root or fresh_root == repeat_root:
        return _blocked("existing, fresh and repeat roots must be distinct", refs)
    try:
        fresh_refs, fresh_digest, fresh_detail = verifier(ctx, str(fresh_root))
        repeat_refs, repeat_digest, repeat_detail = verifier(ctx, str(repeat_root))
    except (FileNotFoundError, PackageExportError) as exc:
        return _blocked(f"fresh/repeat replay invalid: {exc}", refs)
    if fresh_digest != repeat_digest:
        return _blocked(
            f"fresh and repeat scientific digests differ ({fresh_digest[:12]} vs "
            f"{repeat_digest[:12]})",
            [*fresh_refs, *repeat_refs],
        )
    if existing_digest is not None and fresh_digest != existing_digest:
        return _blocked(
            "fresh/repeat replay does not reproduce the existing recorded scientific digest",
            [*fresh_refs, *repeat_refs, *refs],
        )
    return _ok(
        "two independent fresh/repeat processes match each other and the "
        "existing scientific digest; commands, run roots and artifact hashes "
        "are recorded",
        [*fresh_refs, *repeat_refs, *refs],
    )


# ---------------------------------------------------------------------------
# Public audit
# ---------------------------------------------------------------------------


def _audit_fixture_card(
    ctx: AuditContext,
    definition: CardDefinition,
    index_entry: Mapping[str, Any],
    registry: Any,
) -> dict[str, Any]:
    """A compact synthetic-experiment adapter used only by contract tests."""

    card = next(item for item in registry.cards if item.study_id == definition.study_id)
    card_sha = ctx.sha256(definition.card_path)
    if card_sha != card.sha256:
        raise PackageExportError(f"{definition.study_id}: fixture card SHA mismatch")
    spec = _require_dict(ctx.json(definition.spec_path), what="fixture spec")
    study_root = index_entry.get("existing_root")
    if not study_root:
        raise PackageExportError("fixture: existing_root required")
    study = _require_dict(ctx.json(f"{study_root}/study.json"), what="fixture study")
    seeds = [int(seed) for seed in _require_list(spec.get("seeds"), what="fixture seeds")]
    arms = [str(arm) for arm in _require_list(spec.get("arms"), what="fixture arms")]
    if len(seeds) < 2 or len(arms) < 2:
        raise PackageExportError("fixture: need at least two seeds and two arms")
    refs = [
        ctx.ref(definition.card_path),
        ctx.ref(definition.spec_path),
        ctx.ref(f"{study_root}/study.json"),
    ]

    def missing(name: str) -> dict[str, Any]:
        return _blocked(f"required fixture evidence missing: {name}", refs)

    checks: dict[str, dict[str, Any]] = {}
    checks["schema_valid"] = _ok(
        "fixture schema and card SHA match", refs, level="VERIFIED_BY_CODE"
    )

    declared = (
        spec.get("window") is not None
        and spec.get("falsification_criterion")
        and spec.get("legacy_card", {}).get("sha256") == card_sha
    )
    checks["experiment_declared"] = (
        _ok("fixture spec binds the card and declares seeds, arms, window and falsification", refs)
        if declared
        else missing("experiment declaration")
    )

    paired = _require_list(study.get("paired"), what="fixture paired")
    expected_pairs = {(seed, arm) for seed in seeds for arm in arms}
    observed_pairs = {
        (int(item["seed"]), str(item["arm"])) for item in paired if isinstance(item, dict)
    }
    opening = {}
    for item in paired:
        opening.setdefault(int(item["seed"]), set()).add(str(item["opening_digest"]))
    checks["paired_control"] = (
        _ok(
            "fixture pairs cover every seed x arm with one opening per seed",
            [ctx.ref(f"{study_root}/study.json", pointer="/paired")],
        )
        if (
            observed_pairs == expected_pairs
            and len(paired) == len(expected_pairs)
            and all(len(value) == 1 for value in opening.values())
        )
        else missing("complete paired matrix")
    )

    first_stage = _require_list(study.get("first_stage"), what="fixture first_stage")
    checks["first_stage_checked"] = (
        _ok(
            "fixture first-stage rows are complete and binding",
            [ctx.ref(f"{study_root}/study.json", pointer="/first_stage")],
        )
        if len(first_stage) >= len(expected_pairs)
        and all(
            item.get("applied") is True
            and item.get("effective") is True
            and item.get("binding") is True
            for item in first_stage
        )
        and all(_finite(item.get("flow")) for item in first_stage)
        else missing("first-stage evidence")
    )

    accounting = _require_dict(study.get("accounting"), what="fixture accounting")
    tick_rows = _require_list(accounting.get("ticks"), what="fixture accounting ticks")
    checks["accounting_checked"] = (
        _ok(
            "fixture per-tick residuals are within the declared gate",
            [ctx.ref(f"{study_root}/study.json", pointer="/accounting")],
        )
        if tick_rows
        and len(tick_rows) >= len(expected_pairs) * int(accounting.get("ticks_per_arm", 1))
        and all(
            abs(float(row["material_residual"])) <= float(accounting["gate"])
            and abs(float(row["finance_residual"])) <= float(accounting["gate"])
            for row in tick_rows
        )
        else missing("per-tick ledger")
    )

    negative = _require_dict(study.get("negative_control"), what="fixture negative_control")
    checks["negative_control"] = (
        _ok(
            "fixture negative control executed and has a finite metric",
            [ctx.ref(f"{study_root}/study.json", pointer="/negative_control")],
        )
        if negative.get("arm") in arms and _finite(negative.get("metric"))
        else missing("negative control")
    )

    required_metrics = _require_list(spec.get("required_metrics"), what="fixture required_metrics")
    metric_doc = _require_dict(study.get("metrics"), what="fixture metrics")
    checks["metrics_generated"] = (
        _ok(
            "fixture required metrics are finite with selector and unit",
            [ctx.ref(f"{study_root}/study.json", pointer="/metrics")],
        )
        if required_metrics
        and all(
            key in metric_doc
            and _finite(metric_doc[key].get("value"))
            and metric_doc[key].get("selector")
            and metric_doc[key].get("unit")
            for key in required_metrics
        )
        else missing("required metrics")
    )

    sensitivity = study.get("sensitivity")
    sensitivity_reason = study.get("sensitivity_not_run_reason")
    checks["sensitivity_or_reason_not_run"] = (
        _ok(
            "fixture sensitivity executed",
            [ctx.ref(f"{study_root}/study.json", pointer="/sensitivity")],
        )
        if isinstance(sensitivity, list) and sensitivity
        else (
            _ok(
                "fixture records a sourced not-run reason",
                [ctx.ref(f"{study_root}/study.json", pointer="/sensitivity_not_run_reason")],
            )
            if isinstance(sensitivity_reason, str) and sensitivity_reason.strip()
            else missing("sensitivity or sourced reason")
        )
    )

    checks["historical_evidence_grade"] = (
        _ok(
            "fixture historical grade is UNIDENTIFIED",
            [ctx.ref(f"{study_root}/study.json", pointer="/historical_status")],
            level="VERIFIED_BY_CODE",
        )
        if study.get("historical_status") == "UNIDENTIFIED"
        else missing("honest UNIDENTIFIED historical grade")
    )

    counter = study.get("counterevidence")
    checks["counterevidence"] = (
        _ok(
            "fixture counterevidence is bound to a result",
            [ctx.ref(f"{study_root}/study.json", pointer="/counterevidence")],
        )
        if isinstance(counter, list)
        and counter
        and all(item.get("result") and item.get("reason") for item in counter)
        else missing("counterevidence")
    )

    def fixture_verifier(
        c: AuditContext, root: str
    ) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
        payload = _require_dict(c.json(f"{root}/study.json"), what="fixture replay study")
        digest = canonical_digest(
            {"study": payload, "study_file_sha256": c.sha256(f"{root}/study.json")}
        )
        return ([c.ref(f"{root}/study.json")], digest, {"ticks": payload.get("ticks")})

    existing_root = index_entry.get("existing_root")
    existing_digest = fixture_verifier(ctx, str(existing_root))[1] if existing_root else None
    checks["reproduction_bundle"] = _reproduction_from_index(
        ctx,
        index_entry,
        verifier=fixture_verifier,
        refs=refs,
        existing_digest=existing_digest,
        what="fixture",
    )

    complete = _complete(checks)
    return {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "study_id": definition.study_id,
        "legacy_card_id": definition.legacy_card_id,
        "card_sha256": card_sha,
        "experiment_status": "COMPLETE" if complete else "BLOCKED",
        "package_status": "complete" if complete else "blocked",
        "research_package_complete": complete,
        "checks": checks,
        "legacy_metrics": [],
        "study_metrics": [],
        "verdicts": {
            "technical": {
                "status": "PASS" if complete else "BLOCKED",
                "level": "VERIFIED_BY_RUN",
                "reason": "fixture",
                "refs": refs,
            },
            "structural": {
                "status": "SYNTHETIC_FIXTURE",
                "level": "VERIFIED_BY_RUN",
                "reason": "fixture",
                "refs": refs,
            },
            "historical": {
                "status": "UNIDENTIFIED",
                "level": "VERIFIED_BY_CODE",
                "reason": "fixture",
                "refs": refs,
            },
        },
        "failed_seeds": study.get("failed_seeds"),
        "preserved_failures": study.get("preserved_failures") or [],
        "historical_counterevidence": counter or [],
        "source_rights": {"policy": "reference_only", "admitted_historical_series": []},
        "reproduction": {
            "existing_root": index_entry.get("existing_root"),
            "fresh_root": index_entry.get("fresh_root"),
            "repeat_root": index_entry.get("repeat_root"),
            "scientific_digest": canonical_digest(study),
            "status": checks["reproduction_bundle"]["status"],
            "reason": checks["reproduction_bundle"]["reason"],
        },
        "prior_review": {},
        "prior_commit": {},
        "blockers": []
        if complete
        else [name for name, check in checks.items() if check["status"] != "PASS"],
    }


def _legacy_metrics_for(registry: Any, definition: CardDefinition) -> list[dict[str, Any]]:
    card = next(item for item in registry.cards if item.study_id == definition.study_id)
    entries: list[dict[str, Any]] = []
    for registration in registry.for_card(card.mechanism_id):
        entries.append(
            {
                "metric_index": registration.metric_index,
                "exact_original_metric": registration.exact_original_metric,
                "status": registration.status,
                "blocked_reason": registration.blocked_reason,
                "spec": registration.spec.model_dump(mode="json"),
                "components": [asdict(component) for component in registration.components],
            }
        )
    return entries


def _prior_review(
    ctx: AuditContext,
    definition: CardDefinition,
    manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "verdict": None,
        "rounds": None,
        "path": definition.review_path,
        "sha256": None,
        "model": None,
        "blob_verified": False,
        "note": "fixed metadata; prior commit/blob was verified during H6B authoring",
    }
    if definition.review_path and ctx.exists(definition.review_path):
        payload["sha256"] = ctx.sha256(definition.review_path)
    if manifest:
        review = manifest.get("review")
        if isinstance(review, dict):
            payload["verdict"] = review.get("final_verdict") or review.get("verdict")
            payload["rounds"] = review.get("rounds")
            payload["model"] = review.get("model")
        if payload["verdict"] is None:
            payload["verdict"] = manifest.get("review_status")
        reviewer = manifest.get("reviewer_field")
        if isinstance(reviewer, dict):
            payload["rounds"] = payload["rounds"] or len(
                [key for key in reviewer if str(key).startswith("round")]
            )
    return payload


def _prior_commit(ctx: AuditContext, definition: CardDefinition) -> dict[str, Any]:
    payload = {
        "hash": definition.prior_commit,
        "path": definition.prior_path,
        "sha256": None,
        "blob_verified": False,
        "reason": None,
    }
    if definition.prior_path and ctx.exists(definition.prior_path):
        payload["sha256"] = ctx.sha256(definition.prior_path)
    if definition.prior_commit is None:
        payload["reason"] = "no prior commit could be proved"
    elif payload["sha256"] is None:
        payload["reason"] = "prior path is missing in this checkout"
    else:
        # The blob was verified during authoring with ``git show``.  A cold
        # ``git archive`` checkout has no .git, so we do not claim a fresh
        # git-object verification there.
        payload["blob_verified"] = False
        payload["reason"] = (
            "fixed prior commit recorded from a targeted git log/git show during "
            "H6B authoring; cold archive checkouts carry no .git metadata"
        )
    return payload


_GIT_ONLY_RUN_CARDS = frozenset({"M01", "M02", "M04", "M09"})


def _git_only_experiment(
    ctx: AuditContext,
    definition: CardDefinition,
    spec: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
    index_entry: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Block run-dependent checks without touching ignored local outputs."""

    refs = []
    if definition.spec_path:
        refs.append(ctx.ref(definition.spec_path))
    if definition.manifest_path:
        refs.append(ctx.ref(definition.manifest_path))
    if definition.report_path:
        refs.append(ctx.ref(definition.report_path))
    reason = (
        "git-only mode does not access ignored local run outputs; the tracked "
        "declaration is preserved but the run evidence is BLOCKED"
    )
    checks = {
        name: _blocked(reason, refs)
        for name in CHECK_NAMES
        if name
        in {
            "paired_control",
            "first_stage_checked",
            "accounting_checked",
            "negative_control",
            "metrics_generated",
            "sensitivity_or_reason_not_run",
            "reproduction_bundle",
        }
    }
    checks["historical_evidence_grade"] = _generic_historical_check(
        ctx,
        definition,
        manifest,
        spec,
        status_value=("UNIDENTIFIED" if definition.study_id != "M09" else "NOT_RUN"),
        reason="no admitted historical series; synthetic engineering evidence only",
    )
    checks["counterevidence"] = _ok(
        "tracked report records the documented negative/bounded result; no local run was read",
        refs,
        level="VERIFIED_BY_CODE",
    )
    failed_seeds = None
    if isinstance(manifest, dict):
        study = manifest.get("study")
        if isinstance(study, dict) and isinstance(study.get("failed_seeds"), list):
            failed_seeds = list(study["failed_seeds"])
    return (
        checks,
        {
            "technical": "BLOCKED",
            "structural": "NOT_RUN_IN_GIT_ONLY",
            "historical": "UNIDENTIFIED" if definition.study_id != "M09" else "NOT_RUN",
        },
        {
            "metrics": [],
            "manifest": manifest,
            "study": {},
            "failed_seeds": failed_seeds,
            "preserved_failures": [],
            "reproduction": {
                "existing_root": index_entry.get("existing_root"),
                "fresh_root": index_entry.get("fresh_root"),
                "repeat_root": index_entry.get("repeat_root"),
                "commands": list(definition.commands),
                "scientific_digest": None,
                "status": "BLOCKED",
                "reason": reason,
            },
        },
    )


def _audit_real_card(
    ctx: AuditContext,
    definition: CardDefinition,
    index_entry: Mapping[str, Any],
    registry: Any,
    source_rights: dict[str, Any],
) -> dict[str, Any]:
    schema, spec, manifest = _identity_and_schema(ctx, definition, registry, index_entry)
    checks: dict[str, dict[str, Any]] = {"schema_valid": schema}
    study_metrics: list[dict[str, Any]] = []
    verdicts: dict[str, Any]
    extras: dict[str, Any]

    if definition.kind == "experiment":
        if ctx.mode == "git-only" and definition.study_id in _GIT_ONLY_RUN_CARDS:
            card_checks, verdicts, extras = _git_only_experiment(
                ctx, definition, spec, manifest, index_entry
            )
        elif definition.study_id == "M01":
            card_checks, verdicts, extras = _m01_checks(ctx, index_entry)
        elif definition.study_id == "M02":
            card_checks, verdicts, extras = _m02_checks(ctx, index_entry)
        elif definition.study_id == "M03":
            card_checks, verdicts, extras = _m03_checks(ctx, index_entry)
        elif definition.study_id == "M04":
            card_checks, verdicts, extras = _m04_checks(ctx, index_entry)
        elif definition.study_id == "M09":
            card_checks, verdicts, extras = _m09_checks(ctx, index_entry)
        else:  # pragma: no cover
            raise PackageExportError(f"no audit adapter for {definition.study_id}")
        checks.update(card_checks)
        checks["experiment_declared"] = _experiment_declared(
            definition, spec, refs=[ctx.ref(definition.spec_path)]
        )
        if "historical_evidence_grade" not in checks:
            checks["historical_evidence_grade"] = _generic_historical_check(
                ctx,
                definition,
                manifest,
                spec,
                status_value=verdicts.get("historical"),
                reason="see sealed verdicts",
            )
        study_metrics = extras.pop("metrics", [])
        failed_seeds = extras.pop("failed_seeds", None)
        preserved_failures = extras.pop("preserved_failures", [])
        reproduction = extras.pop("reproduction", {})
        blockers = (
            []
            if _complete(checks)
            else [name for name in CHECK_NAMES if checks[name]["status"] != "PASS"]
        )
        historical_counterevidence = _counterevidence_for(definition, extras)
    elif definition.kind == "blocked":
        card_checks, verdicts, extras = _blocked_card_checks(ctx, definition, manifest)
        checks.update(card_checks)
        failed_seeds = extras.get("failed_seeds")
        preserved_failures = []
        reproduction = {
            "existing_root": index_entry.get("existing_root"),
            "fresh_root": None,
            "repeat_root": None,
            "status": "NOT_RUN",
            "reason": "blocker-only card has no simulation",
        }
        blockers = extras.get("blockers", [])
        historical_counterevidence = [str(item) for item in blockers]
    else:
        card_checks, verdicts, extras = _not_started_checks(ctx, definition)
        checks.update(card_checks)
        failed_seeds = None
        preserved_failures = []
        reproduction = {
            "existing_root": None,
            "fresh_root": None,
            "repeat_root": None,
            "status": "NOT_RUN",
            "reason": "experiment NOT_STARTED",
        }
        blockers = extras.get("blockers", [])
        historical_counterevidence = [str(item) for item in blockers]

    # Preserve exactly the eleven checks in the fixed order.
    ordered_checks = {name: checks[name] for name in CHECK_NAMES}
    complete = _complete(ordered_checks)
    verdict_payload = {}
    for dimension in ("technical", "structural", "historical"):
        value = verdicts.get(dimension)
        if isinstance(value, dict):
            verdict_payload[dimension] = {
                "status": value.get("status") or value.get("level") or "UNKNOWN",
                "level": value.get("level") or "VERIFIED_BY_CODE",
                "reason": value.get("reason") or "",
                "refs": value.get("refs") or [],
            }
        else:
            verdict_payload[dimension] = {
                "status": str(value),
                "level": "VERIFIED_BY_RUN"
                if definition.kind == "experiment"
                else "VERIFIED_BY_CODE",
                "reason": "",
                "refs": [],
            }

    return {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "study_id": definition.study_id,
        "legacy_card_id": definition.legacy_card_id,
        "card_sha256": ctx.sha256(definition.card_path),
        "experiment_status": (
            "COMPLETE"
            if complete
            else ("NOT_STARTED" if definition.kind == "not_started" else "BLOCKED")
        ),
        "package_status": "complete" if complete else "blocked",
        "research_package_complete": complete,
        "checks": ordered_checks,
        "legacy_metrics": _legacy_metrics_for(registry, definition),
        "study_metrics": study_metrics,
        "verdicts": verdict_payload,
        "failed_seeds": failed_seeds,
        "preserved_failures": preserved_failures,
        "historical_counterevidence": historical_counterevidence,
        "source_rights": source_rights,
        "reproduction": reproduction,
        "prior_review": _prior_review(ctx, definition, manifest),
        "prior_commit": _prior_commit(ctx, definition),
        "blockers": blockers if not complete else [],
    }


def _counterevidence_for(definition: CardDefinition, extras: Mapping[str, Any]) -> list[Any]:
    study = extras.get("study") if isinstance(extras.get("study"), dict) else {}
    if definition.study_id == "M01":
        return [
            {
                "kind": "structural_non_result",
                "statement": "welfare_cut history contrast is UNIDENTIFIED (mixed signs and a "
                "numerically zero ablation)",
                "refs": study.get("verdict", {}).get("levers", {}).get("welfare_cut", {}),
            },
            {
                "kind": "measurement_boundary",
                "statement": "empty C0 political tables are missing measurements, not measured "
                "zeros",
            },
        ]
    if definition.study_id == "M02":
        return [
            {
                "kind": "falsification_met",
                "statement": "non-falling shortage axes meet the card's falsification "
                "criterion in this synthetic window",
            },
            {
                "kind": "scope_limit",
                "statement": "F2 generalisation is NOT_RUN; SUPPORTED is unreachable from a "
                "four-quarter synthetic window",
            },
        ]
    if definition.study_id == "M03":
        return [
            {
                "kind": "unidentified",
                "statement": "institutional attribution remains UNIDENTIFIED; PASS_SYNTHETIC "
                "is not historical attribution",
            }
        ]
    if definition.study_id == "M04":
        return [
            {
                "kind": "bounded_first_stage",
                "statement": "the full tolerance arm saturates the capacity ceiling; the "
                "effect is conditional on that bound",
            },
            {
                "kind": "process_failure",
                "statement": "the implementation session timeout is preserved separately from "
                "seed failures",
            },
        ]
    if definition.study_id == "M09":
        return [
            {
                "kind": "valid_null",
                "statement": "all arms request 100 units because the cap binds; identical "
                "economic outcomes are a valid null, not a welfare effect",
            },
            {
                "kind": "preserved_failure",
                "statement": "the pre-fix matrix-count failure is retained in the "
                "study-failed-1 artifact",
            },
        ]
    return []


def audit_package(
    root: Path,
    *,
    mode: str = "git-only",
    evidence_index: Path | None = None,
) -> dict[str, Any]:
    """Audit the eleven H6B cards without modifying any file."""

    if mode not in _MODES:
        raise PackageExportError(f"mode must be one of {sorted(_MODES)}")
    root = Path(root).resolve()
    if not root.is_dir():
        raise PackageExportError(f"root is not a directory: {root}")
    ctx = AuditContext(root, mode=mode)

    try:
        registry = register_legacy_cards(root)
    except Exception as exc:  # noqa: BLE001 - contract hard failure
        raise PackageExportError(f"legacy card registry failed: {exc}") from exc
    try:
        load_evidence_manifest(root, root / "studies" / "manifest.json")
    except Exception as exc:  # noqa: BLE001 - contract hard failure
        raise PackageExportError(f"study manifest/cards failed verification: {exc}") from exc

    index_path = evidence_index or DEFAULT_EVIDENCE_INDEX
    index = load_evidence_index(root, index_path)
    source_rights = _load_source_rights(ctx)

    cards: dict[str, Any] = {}
    for card_id in _CANONICAL_IDS:
        definition = CARD_DEFINITIONS[card_id]
        entry = index["cards"][card_id]
        if getattr(definition, "fixture", False):
            cards[card_id] = _audit_fixture_card(ctx, definition, entry, registry)
        else:
            cards[card_id] = _audit_real_card(ctx, definition, entry, registry, source_rights)

    complete = [card_id for card_id, card in cards.items() if card["research_package_complete"]]
    blocked = [card_id for card_id in cards if card_id not in complete]
    payload = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "mode": mode,
        "evidence_index": {
            "path": index["path"],
            "sha256": index["digest"],
            "schema_version": index["schema_version"],
        },
        "card_registry": {
            "counts": registry.counts(),
            "identity_map": registry.identity_map(),
            "identity_map_sha256": registry.identity_map_sha256(),
        },
        "summary": {
            "cards": 11,
            "complete": len(complete),
            "blocked": len(blocked),
            "complete_cards": complete,
            "blocked_cards": blocked,
            "legacy_metrics": sum(len(card["legacy_metrics"]) for card in cards.values()),
        },
        "source_rights": source_rights,
        "cards": cards,
    }
    package_digest = canonical_digest(payload)
    payload["package_digest"] = package_digest
    return payload


# ---------------------------------------------------------------------------
# Export and verification
# ---------------------------------------------------------------------------


def _assert_public_payload(value: Any, *, where: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key) in _FORBIDDEN_TEXT_KEYS:
                raise PackageExportError(f"restricted key {key!r} at {where}")
            _assert_public_payload(nested, where=f"{where}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _assert_public_payload(nested, where=f"{where}[{index}]")
    elif isinstance(value, str):
        if _ABSOLUTE_PATH_RE.search(value) or "data/private" in value:
            raise PackageExportError(f"absolute/private path leaked at {where}: {value!r}")
        if "\x00" in value:
            raise PackageExportError(f"NUL byte at {where}")


def _readme(package: dict[str, Any]) -> str:
    summary = package["summary"]
    lines = [
        "# HIST_VNEXT H6B research package",
        "",
        "This export is a **package-completeness audit**, not a claim that any",
        "historical hypothesis is SUPPORTED.  Each card separately reports",
        "technical, structural and historical status.  `research_package_complete`",
        "is derived only from the eleven checks; historical `UNIDENTIFIED`/`NOT_RUN`",
        "does not by itself reduce package completeness.",
        "",
        f"- mode: `{package['mode']}`",
        f"- cards: {summary['cards']}",
        f"- complete: {summary['complete']} ({', '.join(summary['complete_cards']) or 'none'})",
        f"- blocked: {summary['blocked']} ({', '.join(summary['blocked_cards']) or 'none'})",
        f"- legacy declared metrics preserved: {summary['legacy_metrics']}",
        f"- package digest: `{package['package_digest']}`",
        "",
        "## Cards",
        "",
        "| card | package | technical | structural | historical | blocking checks |",
        "|---|---|---|---|---|---|",
    ]
    for card_id in _CANONICAL_IDS:
        card = package["cards"][card_id]
        verdicts = card["verdicts"]
        blocking = [name for name in CHECK_NAMES if card["checks"][name]["status"] != "PASS"]
        lines.append(
            "| {card} | {package_status} | {technical} | "
            "{structural} | {historical} | {blocking} |".format(
                card=card_id,
                package_status=card["package_status"],
                technical=verdicts["technical"]["status"],
                structural=verdicts["structural"]["status"],
                historical=verdicts["historical"]["status"],
                blocking=", ".join(blocking) or "none",
            )
        )
    lines += [
        "",
        "## Safety",
        "",
        "Only JSON and Markdown are exported.  No original source, OCR, translated text,",
        "raw table, target, HOLD, reserved or private file is opened, copied or",
        "redistributed.  Source rights are reference-only metadata.",
        "",
    ]
    return "\n".join(lines)


def export_package(package: dict[str, Any], output_dir: Path) -> Path:
    """Write a deterministic public export into a new directory."""

    _validate_package_shape(package)
    _assert_public_payload(package)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise PackageExportError(f"export destination already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)
    cards_dir = output_dir / "cards"
    cards_dir.mkdir()
    package_payload = {key: value for key, value in package.items() if key != "package_digest"}
    package_bytes = canonical_json(package_payload) + b"\n"
    package_digest = canonical_digest(package_payload)
    (output_dir / "package.json").write_bytes(package_bytes)
    (output_dir / "README.md").write_text(_readme(package), encoding="utf-8")
    files: list[dict[str, Any]] = []
    for card_id in _CANONICAL_IDS:
        card_bytes = canonical_json(package["cards"][card_id]) + b"\n"
        relative = f"cards/{card_id}.json"
        path = cards_dir / f"{card_id}.json"
        path.write_bytes(card_bytes)
        files.append({"path": relative, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    files.append(
        {
            "path": "package.json",
            "sha256": hashlib.sha256(package_bytes).hexdigest(),
            "bytes": len(package_bytes),
        }
    )
    files.append(
        {
            "path": "README.md",
            "sha256": sha256_file(output_dir / "README.md"),
            "bytes": (output_dir / "README.md").stat().st_size,
        }
    )
    manifest = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package_digest": package_digest,
        "files": sorted(files, key=lambda item: item["path"]),
        "excludes_self": "MANIFEST.json",
    }
    (output_dir / "MANIFEST.json").write_bytes(canonical_json(manifest) + b"\n")
    return output_dir


def _validate_package_shape(package: Mapping[str, Any]) -> None:
    if not isinstance(package, Mapping):
        raise PackageExportError("package must be an object")
    if package.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        raise PackageExportError("wrong package schema_version")
    cards = package.get("cards")
    if not isinstance(cards, Mapping) or set(cards) != set(_CANONICAL_IDS):
        raise PackageExportError("package must contain exactly M01..M11")
    for card_id in _CANONICAL_IDS:
        card = _require_dict(cards[card_id], what=f"card {card_id}")
        if card.get("study_id") != card_id:
            raise PackageExportError(f"{card_id}: card study_id mismatch")
        checks = _require_dict(card.get("checks"), what=f"{card_id} checks")
        if set(checks) != set(CHECK_NAMES):
            raise PackageExportError(f"{card_id}: checks are not exactly the eleven H6B checks")
        for name in CHECK_NAMES:
            item = _require_dict(checks[name], what=f"{card_id}.{name}")
            if item.get("status") not in _STATUSES:
                raise PackageExportError(f"{card_id}.{name}: invalid status")
        derived = _complete(checks)
        if card.get("research_package_complete") is not derived:
            raise PackageExportError(f"{card_id}: self-reported completeness contradicts checks")
        expected_status = "complete" if derived else "blocked"
        if card.get("package_status") != expected_status:
            raise PackageExportError(f"{card_id}: package_status contradicts checks")


def verify_export(output_dir: Path) -> dict[str, Any]:
    """Recompute the export manifest and card contract without external originals."""

    output_dir = Path(output_dir)
    manifest_path = output_dir / "MANIFEST.json"
    if not manifest_path.is_file():
        raise PackageExportError("MANIFEST.json missing")
    manifest = _strict_json(manifest_path.read_text(encoding="utf-8"), origin="MANIFEST.json")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        raise PackageExportError("invalid export manifest schema")
    files = _require_list(manifest.get("files"), what="MANIFEST files")
    listed = {str(item["path"]): item for item in files}
    actual = set()
    for path in output_dir.rglob("*"):
        if path.is_file():
            relative = path.relative_to(output_dir).as_posix()
            if relative == "MANIFEST.json":
                continue
            actual.add(relative)
    if actual != set(listed):
        raise PackageExportError(
            f"export file set mismatch: missing={sorted(set(listed) - actual)}, "
            f"extra={sorted(actual - set(listed))}"
        )
    for relative, expected in listed.items():
        path = output_dir / relative
        if path.is_symlink():
            raise PackageExportError(f"symlink in export: {relative}")
        if sha256_file(path) != expected["sha256"] or path.stat().st_size != int(expected["bytes"]):
            raise PackageExportError(f"export file changed: {relative}")
    package_bytes = (output_dir / "package.json").read_bytes()
    package = _strict_json(package_bytes.decode("utf-8"), origin="package.json")
    if canonical_digest(package) != manifest.get("package_digest"):
        raise PackageExportError("package_digest mismatch")
    _validate_package_shape(package)
    _assert_public_payload(package)
    for card_id in _CANONICAL_IDS:
        card_bytes = (output_dir / "cards" / f"{card_id}.json").read_bytes()
        card = _strict_json(card_bytes.decode("utf-8"), origin=f"cards/{card_id}.json")
        if canonical_json(card) + b"\n" != card_bytes:
            raise PackageExportError(f"cards/{card_id}.json is not canonical")
        if card != package["cards"][card_id]:
            raise PackageExportError(f"cards/{card_id}.json disagrees with package.json")
    return {
        "status": "verified",
        "package_digest": manifest["package_digest"],
        "files": len(listed),
        "cards": len(package["cards"]),
        "complete": package["summary"]["complete"],
        "blocked": package["summary"]["blocked"],
        "note": "export sealing only; not an independent scientific reproduction",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m hsm_lab.evidence.package_export")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="audit the eleven cards and write a new export")
    build.add_argument("--root", type=Path, default=Path("."))
    build.add_argument("--mode", choices=sorted(_MODES), default="git-only")
    build.add_argument("--evidence-index", type=Path, default=DEFAULT_EVIDENCE_INDEX)
    build.add_argument("--output-dir", type=Path, required=True)
    verify = sub.add_parser("verify", help="verify an exported package directory")
    verify.add_argument("--package-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            package = audit_package(
                args.root,
                mode=args.mode,
                evidence_index=args.evidence_index,
            )
            export_package(package, args.output_dir)
            summary = {
                "status": "built",
                "output_dir": str(args.output_dir),
                "mode": package["mode"],
                "cards": package["summary"]["cards"],
                "complete": package["summary"]["complete"],
                "blocked": package["summary"]["blocked"],
                "package_digest": package["package_digest"],
            }
        else:
            summary = verify_export(args.package_dir)
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (PackageExportError, FileNotFoundError, OSError) as exc:
        print(
            json.dumps(
                {"status": "error", "error": str(exc), "exit_code": 2},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
