"""Shared contract primitives (exceptions, strict base, annotated types).

Imported by both ``contract.schemas`` and ``contract.material``; importing
from ``contract.schemas`` still works (it re-exports everything below).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ConfigError(ValueError):
    """Input/configuration validation failure (CLI exit code 2)."""


class ResearchGateError(RuntimeError):
    """Environment / I/O / research-gate failure (CLI exit code 1)."""


class StrictModel(BaseModel):
    """Shared strict base: unknown fields are errors, instances are frozen."""

    model_config = ConfigDict(extra="forbid", frozen=True)


StrictInt = Annotated[int, Field(strict=True)]
FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
