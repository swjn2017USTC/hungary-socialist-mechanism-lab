"""Research gates: baseline byte-hash verification and config loading.

``verify_baseline`` hashes the *original bytes* of BASELINE.md and compares
against the pinned contract hash. A missing or drifted baseline stops every
contract-bound run; the expected hash is never rewritten and the user's file is
never modified.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from hsm_lab.contract.schemas import (
    ConfigError,
    Quarter,
    ResearchContract,
    ResearchGateError,
    ScenarioSpec,
)

BASELINE_FILENAME = "BASELINE.md"
AVAILABLE_SCENARIOS = ("smoke",)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ResearchGateError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {path}: {exc}") from exc


def load_research_contract(root: Path) -> ResearchContract:
    """Load and validate ``config/research_contract.json`` under ``root``."""
    path = root / "config" / "research_contract.json"
    if not path.is_file():
        raise ResearchGateError(
            f"research contract config not found at {path}; run from the repository root"
        )
    try:
        return ResearchContract.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigError(f"invalid research contract config {path}:\n{exc}") from exc


def load_scenario(root: Path, scenario_id: str) -> ScenarioSpec:
    """Load ``config/scenarios/<scenario_id>.json`` under ``root``."""
    if scenario_id not in AVAILABLE_SCENARIOS:
        raise ConfigError(
            f"unsupported scenario {scenario_id!r}; available: {', '.join(AVAILABLE_SCENARIOS)}. "
            "P00 implements no historical simulator."
        )
    path = root / "config" / "scenarios" / f"{scenario_id}.json"
    if not path.is_file():
        raise ResearchGateError(f"scenario config not found at {path}")
    try:
        return ScenarioSpec.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigError(f"invalid scenario config {path}:\n{exc}") from exc


def verify_baseline(path: Path, contract: ResearchContract) -> str:
    """Return the SHA-256 of BASELINE.md bytes, or refuse the run.

    Refusal cases: file missing (ResearchGateError) or hash drift versus the
    pinned expected hash (ResearchGateError). Never rewrites either side.
    """
    if not path.is_file():
        raise ResearchGateError(f"baseline file not found: {path}")
    digest = sha256_file(path)
    if digest != contract.expected_baseline_sha256:
        raise ResearchGateError(
            "BASELINE.md hash drift detected: refusing to run.\n"
            f"  expected (pinned): {contract.expected_baseline_sha256}\n"
            f"  actual (bytes)   : {digest}\n"
            "The pinned hash is never updated automatically; a baseline version "
            "decision belongs to the user."
        )
    return digest


def check_core_window(start: Quarter, ticks: int, contract: ResearchContract) -> Quarter:
    """Return the end quarter after asserting the whole window is inside core."""
    if ticks < 1:
        raise ConfigError(f"ticks must be >= 1, got {ticks}")
    end = start.advance(ticks - 1)
    if not contract.in_core(start) or not contract.in_core(end):
        raise ResearchGateError(
            f"window {start}..{end} outside core {contract.core_start}..{contract.core_end}"
        )
    return end
