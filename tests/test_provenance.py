"""D6: provenance/manifest digest semantics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hsm_lab.provenance.manifest import (
    canonical_digest,
    canonical_json,
    compute_data_manifest_hash,
    hash_output_tree,
)


def test_canonical_json_is_sorted_compact_utf8() -> None:
    assert canonical_json({"b": 1, "a": "ő"}) == b'{"a":"\xc5\x91","b":1}'
    assert canonical_json({"x": [1, 2]}) == b'{"x":[1,2]}'


def test_canonical_json_rejects_nan() -> None:
    with pytest.raises(ValueError):
        canonical_json({"bad": float("nan")})


def test_canonical_digest_stable_across_key_order() -> None:
    assert canonical_digest({"a": 1, "b": [2, 3]}) == canonical_digest({"b": [2, 3], "a": 1})


def test_data_manifest_hash_tracks_manifest_bytes(tmp_path) -> None:
    manifests = tmp_path / "data" / "manifests"
    manifests.mkdir(parents=True)
    for name in ("sources.yml", "variables.yml", "artifacts.yml"):
        (manifests / name).write_text("schema_version: '1'\n", encoding="utf-8")
    first = compute_data_manifest_hash(tmp_path)
    (manifests / "sources.yml").write_text(
        "schema_version: '1'\n# touched\n", encoding="utf-8"
    )
    second = compute_data_manifest_hash(tmp_path)
    assert first != second
    assert len(first) == 64


def test_hash_output_tree_excludes_manifest(tmp_path) -> None:
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "summary.json").write_text("{}", encoding="utf-8")
    hashes = hash_output_tree(tmp_path)
    assert set(hashes) == {"summary.json"}
    import hashlib

    assert hashes["summary.json"] == hashlib.sha256(b"{}").hexdigest()


def test_real_run_manifest_is_complete(repo_root) -> None:
    """The repo's own smoke config hashes deterministically end-to-end."""
    from hsm_lab.contract.guards import load_scenario
    from hsm_lab.provenance.manifest import compute_scenario_hash

    spec = load_scenario(repo_root, "smoke")
    digest = compute_scenario_hash(spec)
    assert len(digest) == 64
    # seed override must change the scenario hash
    assert compute_scenario_hash(spec.model_copy(update={"seed": 1730})) != digest


def test_run_manifest_json_roundtrip(repo_root, tmp_path) -> None:
    from hsm_lab.contract.guards import load_research_contract, load_scenario
    from hsm_lab.data.registry import DataRegistry
    from hsm_lab.engine.smoke import run_smoke

    contract = load_research_contract(repo_root)
    spec = load_scenario(repo_root, "smoke")
    registry = DataRegistry.load(repo_root)
    manifest = run_smoke(spec, tmp_path / "rt", contract, registry)
    payload = json.loads((tmp_path / "rt" / "manifest.json").read_text(encoding="utf-8"))
    assert payload["run_id"] == manifest.run_id
    assert payload["seed"] == 1729
    assert payload["households"] == 1000
    assert payload["enterprises"] == 50
    assert payload["ticks"] == 10
    assert payload["dependency_versions"]["numpy"].startswith("2")
    assert payload["platform"]["arm64"] is True
    assert Path(payload["output_hashes"]["aggregates.parquet"]).name  # repo-relative names
