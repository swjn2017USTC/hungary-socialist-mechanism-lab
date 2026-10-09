"""Access policy for calibration, hold-out, and reserved target windows.

This module handles authorization metadata only. In particular, constructing a
hold-out receipt never opens a target artifact or accepts target values.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import TypeVar


class Window(StrEnum):
    TRAINING = "training"
    INTERNAL_VALIDATION = "internal_validation"
    HOLDOUT = "holdout"
    RESERVED = "reserved"


class Phase(StrEnum):
    CALIBRATION = "calibration"
    POST_INFERENCE_HOLDOUT_AUDIT = "post_inference_holdout_audit"
    P06_RESERVED_EVALUATION = "p06_reserved_evaluation"


class WindowAccessRefused(PermissionError):
    """Raised before a target reader is called when a window is not open."""


@dataclass(frozen=True)
class WindowManifestEntry:
    """Explicit phase record required to open a protected window."""

    manifest_id: str
    window: Window
    phase: Phase
    declared_open: bool


@dataclass(frozen=True)
class HashOnlyTarget:
    """Safe hold-out registry projection; contains no location or target value."""

    artifact_id: str
    sha256: str
    window: Window = Window.HOLDOUT
    access: str = "hash_only"

    @classmethod
    def from_registry(cls, *, artifact_id: str, sha256: str) -> HashOnlyTarget:
        if not artifact_id.strip():
            raise ValueError("hold-out artifact_id must be non-empty")
        if re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
            raise ValueError("hold-out sha256 must be a lowercase 64-character digest")
        return cls(artifact_id=artifact_id, sha256=sha256)


def authorize_value_read(
    window: Window,
    phase: Phase,
    *,
    inference_complete: bool = False,
    manifest_entry: WindowManifestEntry | None = None,
) -> None:
    """Check access policy without opening or inspecting any target artifact.

    Training and internal-validation values are available to ordinary
    calibration. Hold-out values require completed inference and a declared
    post-inference audit entry. Reserved values require a separate P06 entry
    explicitly opening the reserved window; the current P05 protocol has no
    such entry, so it remains closed.
    """
    if window in (Window.TRAINING, Window.INTERNAL_VALIDATION):
        if phase is Phase.CALIBRATION:
            return
        raise WindowAccessRefused(f"{window.value} is outside the calibration phase")

    if window is Window.HOLDOUT:
        valid_entry = (
            manifest_entry is not None
            and manifest_entry.manifest_id.strip() != ""
            and manifest_entry.window is Window.HOLDOUT
            and manifest_entry.phase is Phase.POST_INFERENCE_HOLDOUT_AUDIT
            and manifest_entry.declared_open
        )
        if phase is Phase.POST_INFERENCE_HOLDOUT_AUDIT and inference_complete and valid_entry:
            return
        raise WindowAccessRefused(
            "hold-out values are hash-only until inference completes and a post-inference "
            "manifest entry explicitly opens the audit"
        )

    valid_entry = (
        manifest_entry is not None
        and manifest_entry.manifest_id.strip() != ""
        and manifest_entry.window is Window.RESERVED
        and manifest_entry.phase is Phase.P06_RESERVED_EVALUATION
        and manifest_entry.declared_open
    )
    if phase is Phase.P06_RESERVED_EVALUATION and valid_entry:
        return
    raise WindowAccessRefused(
        "reserved 1986Q1-1988Q4 window is closed without an explicit P06 manifest entry"
    )


T = TypeVar("T")


def guarded_value_read(  # noqa: UP047 -- retain compatibility with the project's Python floor
    reader: Callable[[], T],
    window: Window,
    phase: Phase,
    *,
    inference_complete: bool = False,
    manifest_entry: WindowManifestEntry | None = None,
) -> T:
    """Authorize first, then call a supplied reader; refusal has no read side effect."""
    authorize_value_read(
        window,
        phase,
        inference_complete=inference_complete,
        manifest_entry=manifest_entry,
    )
    return reader()


def hash_only_record(target: HashOnlyTarget) -> dict[str, str]:
    """Serialize only hold-out identity and digest, never values or file paths."""
    if target.window is not Window.HOLDOUT or target.access != "hash_only":
        raise ValueError("only hash-only hold-out records may be serialized")
    return {key: str(value) for key, value in asdict(target).items()}
