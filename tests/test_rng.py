"""D4: RNG registry determinism, stream independence, and draw accounting."""

from __future__ import annotations

import numpy as np
import pytest

from hsm_lab.contract.schemas import ConfigError
from hsm_lab.engine.rng import RNG_SCHEME_VERSION, RngRegistry


def test_same_seed_same_module_equal_arrays() -> None:
    a = RngRegistry(1729).uniform("smoke.households", (25, 4))
    b = RngRegistry(1729).uniform("smoke.households", (25, 4))
    np.testing.assert_array_equal(a, b)
    assert a.shape == (25, 4)
    assert a.dtype == np.float64
    assert ((a >= 0.0) & (a < 1.0)).all()


def test_different_seed_diverges() -> None:
    a = RngRegistry(1729).uniform("smoke.households", 1000)
    b = RngRegistry(1730).uniform("smoke.households", 1000)
    assert not np.array_equal(a, b)


def test_module_registration_order_irrelevant() -> None:
    first = RngRegistry(7)
    left = first.uniform("module.a", 64)
    first.uniform("module.b", 64)  # adding another module later...
    second = RngRegistry(7)
    second.uniform("module.c", 64)  # ...or before/around must not matter
    again = second.uniform("module.a", 64)
    np.testing.assert_array_equal(left, again)


def test_successive_draws_advance_stream() -> None:
    whole = RngRegistry(21).uniform("m", 4)
    split = RngRegistry(21)
    first = split.uniform("m", 1)
    second = split.uniform("m", 1)
    tail = split.uniform("m", 2)
    np.testing.assert_array_equal(whole, np.concatenate([first, second, tail]))


def test_draw_counts_match_returned_sizes() -> None:
    registry = RngRegistry(5)
    registry.uniform("x", (10, 10))
    registry.uniform("y", 7)
    assert registry.draws_count() == 107
    assert registry.draws_by_module() == {"x": 100, "y": 7}
    assert registry.active_modules() == ["x", "y"]


def test_validation_failures() -> None:
    with pytest.raises(ConfigError):
        RngRegistry(-1)
    with pytest.raises(ConfigError):
        RngRegistry(1, scheme_version="xorshift-v0")
    registry = RngRegistry(1)
    with pytest.raises(ConfigError):
        registry.uniform("", 4)
    with pytest.raises(ConfigError):
        registry.uniform("m", 0)
    with pytest.raises(ConfigError):
        registry.uniform("m", (3, -1))


def test_scheme_version_exposed() -> None:
    assert RngRegistry(0).scheme_version == RNG_SCHEME_VERSION


def test_snapshot_restores_exact_continuation() -> None:
    """7 draws -> snapshot -> 5 more == restore -> 5 more; counts reach 12."""
    rng = RngRegistry(1729)
    rng.uniform("material.initial_households", 7)
    snapshot = rng.snapshot()
    live_tail = rng.uniform("material.initial_households", 5)
    restored = RngRegistry.from_snapshot(snapshot)
    restored_tail = restored.uniform("material.initial_households", 5)
    np.testing.assert_array_equal(live_tail, restored_tail)
    assert restored.draws_by_module() == {"material.initial_households": 12}
    assert restored.draws_count() == rng.draws_count() == 12
    assert restored.seed == 1729
    assert restored.scheme_version == RNG_SCHEME_VERSION
    # A second snapshot of the restored registry equals the live one.
    assert restored.snapshot() == rng.snapshot()


def test_snapshot_survives_json_roundtrip() -> None:
    import json

    rng = RngRegistry(3)
    rng.uniform("a", 5)
    rng.uniform("b", 3)
    through_json = json.loads(json.dumps(rng.snapshot()))
    restored = RngRegistry.from_snapshot(through_json)
    np.testing.assert_array_equal(
        restored.uniform("a", 4), rng.uniform("a", 4)
    )


def test_from_snapshot_rejects_bad_payloads() -> None:
    rng = RngRegistry(11)
    rng.uniform("m", 2)
    snapshot = rng.snapshot()
    with pytest.raises(ConfigError, match="dict"):
        RngRegistry.from_snapshot(None)  # type: ignore[arg-type]
    with pytest.raises(ConfigError, match="seed"):
        RngRegistry.from_snapshot({**snapshot, "seed": -1})
    with pytest.raises(ConfigError, match="scheme"):
        RngRegistry.from_snapshot({**snapshot, "scheme_version": "xorshift-v0"})
    with pytest.raises(ConfigError, match="modules"):
        RngRegistry.from_snapshot({**snapshot, "modules": []})
    module = snapshot["modules"]["m"]
    assert isinstance(module, dict)
    with pytest.raises(ConfigError, match="PCG64"):
        RngRegistry.from_snapshot(
            {**snapshot, "modules": {"m": {**module, "bit_generator": "MT19937"}}}
        )
    with pytest.raises(ConfigError, match="draw_count"):
        RngRegistry.from_snapshot(
            {**snapshot, "modules": {"m": {**module, "draw_count": -1}}}
        )
    with pytest.raises(ConfigError, match="draw_count"):
        RngRegistry.from_snapshot(
            {**snapshot, "modules": {"m": {**module, "draw_count": True}}}
        )
    with pytest.raises(ConfigError, match="state"):
        RngRegistry.from_snapshot(
            {**snapshot, "modules": {"m": {**module, "state": {"junk": 1}}}}
        )


def test_empty_snapshot_restores_empty_registry() -> None:
    restored = RngRegistry.from_snapshot(RngRegistry(42).snapshot())
    assert restored.draws_count() == 0
    assert restored.draws_by_module() == {}
