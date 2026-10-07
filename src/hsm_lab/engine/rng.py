"""The single RNG registry (BASELINE §35 replicate gate).

One ``numpy.random.Generator(PCG64)`` per named module, seeded from
``SeedSequence([seed, *sha256_words(module)])`` so streams are independent of
registration order and of Python's hash randomization. The bare generator is
never exposed; every draw is counted, so a "stochastic replicate" claim always
has the draws to back it (and a deterministic run reports zero draws).
"""

from __future__ import annotations

import hashlib

import numpy as np
from numpy.random import PCG64, Generator, SeedSequence

from hsm_lab.contract.schemas import ConfigError

RNG_SCHEME_VERSION = "pcg64-sha256-module-v1"
_KNOWN_SCHEMES = frozenset({RNG_SCHEME_VERSION})


def _module_words(module: str) -> list[int]:
    digest = hashlib.sha256(module.encode("utf-8")).digest()
    return np.frombuffer(digest, dtype="<u4").tolist()


class RngRegistry:
    """Deterministic per-module uniform streams; the only RNG in the project."""

    def __init__(self, seed: int, scheme_version: str = RNG_SCHEME_VERSION) -> None:
        if scheme_version not in _KNOWN_SCHEMES:
            raise ConfigError(f"unknown RNG scheme version {scheme_version!r}")
        if seed < 0:
            raise ConfigError(f"seed must be a non-negative integer, got {seed}")
        self._seed = int(seed)
        self._scheme_version = scheme_version
        self._streams: dict[str, Generator] = {}
        self._counts: dict[str, int] = {}

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def scheme_version(self) -> str:
        return self._scheme_version

    def _stream(self, module: str) -> Generator:
        stream = self._streams.get(module)
        if stream is None:
            sequence = SeedSequence([self._seed, *_module_words(module)])
            stream = Generator(PCG64(sequence))
            self._streams[module] = stream
            self._counts[module] = 0
        return stream

    def uniform(self, module: str, size: int | tuple[int, ...]) -> np.ndarray:
        """Draw ``size`` uniforms in [0, 1) from ``module``'s stream."""
        if not module or not isinstance(module, str):
            raise ConfigError(f"module name must be a non-empty string, got {module!r}")
        if isinstance(size, tuple):
            if not size or any(not isinstance(dim, int) or isinstance(dim, bool) or dim <= 0
                               for dim in size):
                raise ConfigError(f"invalid draw shape {size!r}")
        elif not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ConfigError(f"invalid draw size {size!r}")
        draws = self._stream(module).random(size)
        self._counts[module] = self._counts.get(module, 0) + draws.size
        return draws

    def draws_count(self) -> int:
        return sum(self._counts.values())

    def draws_by_module(self) -> dict[str, int]:
        return dict(self._counts)

    def active_modules(self) -> list[str]:
        return [module for module, count in self._counts.items() if count > 0]

    def snapshot(self) -> dict[str, object]:
        """Full state: seed, scheme and per-module PCG64 state + draw counts."""
        modules: dict[str, object] = {}
        for module in sorted(self._streams):
            generator = self._streams[module]
            modules[module] = {
                "bit_generator": "PCG64",
                "state": dict(generator.bit_generator.state),
                "draw_count": self._counts[module],
            }
        return {
            "seed": self._seed,
            "scheme_version": self._scheme_version,
            "modules": modules,
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, object]) -> RngRegistry:
        """Restore a snapshot without re-drawing history; strict validation."""
        if not isinstance(snapshot, dict):
            raise ConfigError("RNG snapshot must be a dict")
        seed = snapshot.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ConfigError(f"RNG snapshot seed must be a non-negative int, got {seed!r}")
        scheme = snapshot.get("scheme_version")
        if scheme not in _KNOWN_SCHEMES:
            raise ConfigError(f"unknown RNG scheme version {scheme!r}")
        modules = snapshot.get("modules")
        if not isinstance(modules, dict):
            raise ConfigError("RNG snapshot modules must be a dict")
        registry = cls(int(seed), str(scheme))
        for module in sorted(modules):
            if not isinstance(module, str) or not module:
                raise ConfigError(f"invalid module name in RNG snapshot: {module!r}")
            entry = modules[module]
            if not isinstance(entry, dict):
                raise ConfigError(f"RNG snapshot entry for {module!r} must be a dict")
            if entry.get("bit_generator") != "PCG64":
                raise ConfigError(
                    f"RNG snapshot module {module!r} must use the PCG64 bit generator"
                )
            count = entry.get("draw_count")
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ConfigError(
                    f"RNG snapshot draw_count for {module!r} must be a non-negative int"
                )
            state = entry.get("state")
            if not isinstance(state, dict):
                raise ConfigError(f"RNG snapshot state for {module!r} must be a dict")
            generator = Generator(PCG64(seed))
            try:
                generator.bit_generator.state = state
            except (KeyError, TypeError, ValueError) as exc:
                raise ConfigError(
                    f"RNG snapshot state for {module!r} is not a valid PCG64 state: {exc}"
                ) from exc
            registry._streams[module] = generator
            registry._counts[module] = int(count)
        return registry
