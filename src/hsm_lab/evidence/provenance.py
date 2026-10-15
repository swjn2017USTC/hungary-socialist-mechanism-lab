"""P07A1 §3: provenance DAG for mechanism-card evidence.

The DAG tracks the chain from v1 card SHA-256 anchors through v2 cards,
metric specs, interventions, and run outputs. Each node is immutable and
content-addressed by its digest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from hsm_lab.evidence.schemas import EvidenceStatus  # noqa: F401
from hsm_lab.provenance.manifest import (  # noqa: F401
    MANIFEST_FILENAME,
    RunManifest,
    compute_data_manifest_hash,
    compute_lock_hash,
    compute_parameter_hash,
    hash_output_tree,
)


class DAGNodeType(StrEnum):
    """Taxonomy of nodes in the evidence provenance DAG."""

    V1_CARD = "v1_card"               # config/p06/cards/M*.json
    V2_CARD = "v2_card"               # config/mechanisms/v2/M*.json
    METRIC_SPEC = "metric_spec"       # one MetricSpec within a card
    INTERVENTION_BINDING = "intervention_binding"  # one InterventionBinding
    OBSERVED_STATE = "observed_state"  # captured model output snapshot
    EVIDENCE_RECORD = "evidence_record"  # pre-registered experiment record
    RUN_OUTPUT = "run_output"         # actual run directory output


@dataclass(frozen=True)
class EvidenceDAGNode:
    """One immutable node in the evidence provenance DAG.

    All identity fields are content-addressed: changing any field changes
    the node's digest, which is stored in the DAG edge structure.
    """

    # Required fields first (no defaults)
    node_id: str
    node_type: DAGNodeType
    created_by_phase: str
    digest: str | None = None  # Computed in __post_init__ if None
    # Optional fields (all have defaults)
    description: str | None = None
    card_sha256: str | None = None
    card_mechanism_id: str | None = None
    supersedes_sha256: str | None = None
    parent_record_id: str | None = None
    run_id: str | None = None
    run_scenario: str | None = None
    run_digest: str | None = None
    run_seed: int | None = None
    run_quarter_start: str | None = None
    run_quarter_end: str | None = None
    created_at: str | None = None

    def __post_init__(self) -> None:
        import hashlib
        import json

        # Auto-fill timestamps if not provided
        if self.created_at is None:
            object.__setattr__(
                self,
                "created_at",
                datetime.utcnow().isoformat() + "Z",
            )
        # Compute content-addressed digest if not provided
        if self.digest is None:
            id_fields = [
                self.node_id,
                self.node_type.value if self.node_type else None,
                self.card_sha256,
                self.card_mechanism_id,
                self.supersedes_sha256,
                self.parent_record_id,
                self.run_id,
                self.run_scenario,
                self.run_digest,
                self.run_seed,
                self.run_quarter_start,
                self.run_quarter_end,
                self.created_by_phase,
            ]
            payload = json.dumps(id_fields, sort_keys=True, separators=(",", ":"))
            object.__setattr__(self, "digest", hashlib.sha256(payload.encode()).hexdigest())


@dataclass(frozen=True)
class EvidenceDAGEdge:
    """A directed edge in the evidence provenance DAG."""

    from_node_id: str = Field(min_length=1)
    to_node_id: str = Field(min_length=1)
    edge_label: str = Field(min_length=1)
    edge_type: str = Field(min_length=1)
    # For "supersedes" edges
    superseded_sha256: str | None = Field(default=None)
    created_at: str = field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )


class EvidenceDAG(BaseModel):
    """The full evidence provenance DAG for a phase."""

    model_config = ConfigDict(frozen=True)

    phase: str = Field(min_length=1)
    nodes: Annotated[list[EvidenceDAGNode], Field(min_length=1)]
    edges: list[EvidenceDAGEdge] = Field(default_factory=list)
    manifest_version: str = Field(min_length=1)

    def get_node(self, node_id: str) -> EvidenceDAGNode | None:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def v1_node_for_card(self, mechanism_id: str) -> EvidenceDAGNode | None:
        for node in self.nodes:
            if (
                node.node_type == DAGNodeType.V1_CARD
                and node.card_mechanism_id == mechanism_id
            ):
                return node
        return None

    def v2_node_for_card(self, mechanism_id: str) -> EvidenceDAGNode | None:
        for node in self.nodes:
            if (
                node.node_type == DAGNodeType.V2_CARD
                and node.card_mechanism_id == mechanism_id
            ):
                return node
        return None


def build_card_provenance(
    root_path: str,
    phase: str,
    v1_card_dir: str = "config/p06/cards",
    v2_card_dir: str = "config/mechanisms/v2",
) -> EvidenceDAG:
    """Build the provenance DAG for all M1–M11 cards.

    This function is read-only: it only reads existing card JSON files to
    compute their SHA-256 hashes and creates DAG nodes/edges.

    Parameters
    ----------
    root_path
        Repository root (the directory containing config/, src/, etc.).
    phase
        Current phase label, e.g. "P07A1".
    v1_card_dir
        Relative path from root to v1 card directory.
    v2_card_dir
        Relative path from root to v2 card directory.

    Returns
    -------
    EvidenceDAG
        Complete DAG with v1_card → v2_card supersedes edges, and
        v1_card → evidence_record edges for each mechanism.
    """
    import hashlib
    import json
    from pathlib import Path

    root = Path(root_path)
    v1_dir = root / v1_card_dir
    v2_dir = root / v2_card_dir

    nodes: list[EvidenceDAGNode] = []
    edges: list[EvidenceDAGEdge] = []

    # Load v1 card SHAs and create V1_CARD nodes
    v1_nodes: dict[str, EvidenceDAGNode] = {}
    for card_path in sorted(v1_dir.glob("M*.json")):
        raw = card_path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        mechanism_id = card_path.stem  # "M1", "M2", …
        node_id = f"v1_card:{mechanism_id}"
        node = EvidenceDAGNode(
            node_id=node_id,
            node_type=DAGNodeType.V1_CARD,
            card_sha256=sha,
            card_mechanism_id=mechanism_id,
            description=f"v1 mechanism card for {mechanism_id}",
            created_by_phase=phase,
        )
        nodes.append(node)
        v1_nodes[mechanism_id] = node

    # Load v2 cards if they exist and create V2_CARD nodes + supersedes edges
    if v2_dir.exists():
        for card_path in sorted(v2_dir.glob("M*.json")):
            raw = card_path.read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            mechanism_id = card_path.stem  # "M1", "M2", …
            node_id = f"v2_card:{mechanism_id}"
            supersedes_sha: str | None = None
            supersedes_path = v2_dir.parent / "supersedes.json"
            if supersedes_path.exists():
                sup = json.loads(supersedes_path.read_text(encoding="utf-8"))
                supersedes_sha = sup.get(mechanism_id)

            v2_node = EvidenceDAGNode(
                node_id=node_id,
                node_type=DAGNodeType.V2_CARD,
                card_sha256=sha,
                card_mechanism_id=mechanism_id,
                supersedes_sha256=supersedes_sha,
                description=f"v2 mechanism card for {mechanism_id}",
                created_by_phase=phase,
            )
            nodes.append(v2_node)

            # Edge: v1 → v2 (supersedes)
            v1_node = v1_nodes.get(mechanism_id)
            if v1_node:
                edges.append(
                    EvidenceDAGEdge(
                        from_node_id=v1_node.node_id,
                        to_node_id=v2_node.node_id,
                        edge_label="supersedes",
                        edge_type="supersedes",
                        superseded_sha256=supersedes_sha,
                    )
                )

    # Create one EVIDENCE_RECORD node per mechanism (P07A1 status = DECLARED/BLOCKED)
    for mechanism_id in sorted(v1_nodes.keys()):
        v1_node = v1_nodes[mechanism_id]
        record_node_id = f"evidence_record:{mechanism_id}"
        record_node = EvidenceDAGNode(
            node_id=record_node_id,
            node_type=DAGNodeType.EVIDENCE_RECORD,
            card_mechanism_id=mechanism_id,
            parent_record_id=record_node_id,
            description=f"P07A1 evidence record for {mechanism_id}; status=DECLARED or BLOCKED",
            created_by_phase=phase,
        )
        nodes.append(record_node)
        edges.append(
            EvidenceDAGEdge(
                from_node_id=v1_node.node_id,
                to_node_id=record_node_id,
                edge_label="generates_evidence_record",
                edge_type="generates",
            )
        )

        # If a v2 card exists, also link it to the evidence record
        v2_node_id = f"v2_card:{mechanism_id}"
        if any(n.node_id == v2_node_id for n in nodes):
            edges.append(
                EvidenceDAGEdge(
                    from_node_id=v2_node_id,
                    to_node_id=record_node_id,
                    edge_label="precedes_evidence_record",
                    edge_type="precedes",
                )
            )

    return EvidenceDAG(
        phase=phase,
        nodes=nodes,
        edges=edges,
        manifest_version="1.0.0",
    )


# ---------------------------------------------------------------------------
# verify_run_identity — strict run provenance verification (H0A §4)
# ---------------------------------------------------------------------------

_ALLOWED_RUN_KINDS = frozenset({
    "synthetic_engine_smoke",
    "toy4_f0_simulation",
    "material_household_simulation",
})


def _resolve_output_dir(output_dir: Path, root: Path) -> Path:
    """Resolve output_dir: absolute paths used as-is; relative resolved from root."""
    if output_dir.is_absolute():
        return output_dir
    return (root / output_dir).resolve()


def verify_run_identity(
    *,
    root: Path,
    scenario_id: str,
    seed: int,
    expected_digest: str,
    output_dir: Path,
) -> RunManifest:
    """Verify an actual run's provenance against expected parameters.

    This is a READ-ONLY function: it only reads files already on disk and
    performs no model execution, no writes, and no engine modifications.

    Parameters
    ----------
    root
        Repository root (used to resolve relative output_dir).
    scenario_id
        Scenario identifier, e.g. ``"historical_f2_replay"``.
    seed
        Non-negative integer seed used for the run.
    expected_digest
        The expected SHA-256 digest of the full output tree.
    output_dir
        Path to the run output directory.

    Returns
    -------
    RunManifest
        The parsed and validated run manifest.

    Raises
    ------
    ValueError
        If any provenance check fails (missing file, hash mismatch,
        wrong seed, non-completed run, etc.). The error message contains
        the failing field but does NOT leak sensitive data.
    """
    import json

    from hsm_lab.contract.guards import load_scenario
    from hsm_lab.contract.schemas import ScenarioSpec

    resolved = _resolve_output_dir(output_dir, root)

    # 1. Read and parse manifest
    manifest_path = resolved / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise ValueError(
            "verify_run_identity: manifest.json not found at "
            f"{manifest_path}"
        )
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"verify_run_identity: manifest.json is not valid JSON: {exc}"
        ) from exc

    manifest: RunManifest
    try:
        manifest = RunManifest.model_validate(raw)
    except Exception as exc:
        raise ValueError(
            "verify_run_identity: manifest.json does not conform to "
            f"RunManifest schema: {exc}"
        ) from exc

    # 2. run_kind must be a known non-politics material scenario
    if manifest.run_kind not in _ALLOWED_RUN_KINDS:
        raise ValueError(
            f"verify_run_identity: run_kind={manifest.run_kind!r} is not "
            "in allowed set (non-politics material scenarios only)"
        )

    # 3. Completed / no-failure check
    if manifest.status != "completed":
        raise ValueError(
            f"verify_run_identity: run status is {manifest.status!r}, "
            "expected 'completed'"
        )
    if manifest.failure_message:
        raise ValueError(
            f"verify_run_identity: run has failure_message: "
            f"{manifest.failure_message!r}"
        )

    # 4. completed_ticks must equal ticks (full run completed, not paused)
    if manifest.completed_ticks != manifest.ticks:
        raise ValueError(
            f"verify_run_identity: completed_ticks={manifest.completed_ticks} "
            f"!= ticks={manifest.ticks} (run not fully completed)"
        )

    # 5. Seed check (strict int — no bool coercion)
    if not isinstance(manifest.seed, int) or isinstance(manifest.seed, bool):
        raise ValueError(
            f"verify_run_identity: manifest.seed={manifest.seed!r} is not a "
            "strict integer"
        )
    if manifest.seed != seed:
        raise ValueError(
            f"verify_run_identity: manifest.seed={manifest.seed} does not "
            f"match expected seed={seed}"
        )

    # 6. Digest check (top-level output tree digest)
    if manifest.deterministic_replay_digest != expected_digest:
        raise ValueError(
            "verify_run_identity: manifest.deterministic_replay_digest "
            "does not match expected_digest"
        )

    # 7. scenario_id must be a known scenario; recompute scenario_hash
    try:
        scenario_spec: ScenarioSpec = load_scenario(root, scenario_id)
    except Exception as exc:
        raise ValueError(
            f"verify_run_identity: scenario_id={scenario_id!r} is not "
            f"a known scenario: {exc}"
        ) from exc
    try:
        from hsm_lab.provenance.manifest import compute_scenario_hash

        computed_hash = compute_scenario_hash(scenario_spec)
    except Exception as exc:
        raise ValueError(
            f"verify_run_identity: failed to compute scenario_hash: {exc}"
        ) from exc
    if manifest.scenario_hash != computed_hash:
        raise ValueError(
            "verify_run_identity: manifest.scenario_hash does not match "
            f"computed scenario_hash for scenario_id={scenario_id!r}"
        )

    # 8. All manifest hashes must be non-zero (no stub/zero digests)
    for field_name in (
        "scenario_hash",
        "lock_hash",
        "data_manifest_hash",
        "parameter_hash",
    ):
        h = getattr(manifest, field_name, None)
        if not h or h == "0" * 64:
            raise ValueError(
                f"verify_run_identity: manifest.{field_name} is zero or missing; "
                "run is not a complete formal run"
            )

    # 9. Output tree hash integrity: recompute from disk and compare
    try:
        disk_hashes = hash_output_tree(resolved)
    except Exception as exc:
        raise ValueError(
            f"verify_run_identity: failed to hash output tree: {exc}"
        ) from exc

    manifest_hashes = manifest.output_hashes or {}
    if set(disk_hashes.keys()) != set(manifest_hashes.keys()):
        disk_only = set(disk_hashes.keys()) - set(manifest_hashes.keys())
        manifest_only = set(manifest_hashes.keys()) - set(disk_hashes.keys())
        raise ValueError(
            f"verify_run_identity: output file set mismatch — "
            f"disk-only: {sorted(disk_only)}, manifest-only: {sorted(manifest_only)}"
        )
    for rel_path, disk_hash in disk_hashes.items():
        manifest_hash = manifest_hashes.get(rel_path, "")
        if disk_hash != manifest_hash:
            raise ValueError(
                f"verify_run_identity: hash mismatch for {rel_path}: "
                f"disk={disk_hash[:16]}... manifest={manifest_hash[:16]}..."
            )

    # 10. Required output files must be present
    required_files = ("summary.json", "parameters.json", "initial_recipe.json")
    for fname in required_files:
        fpath = resolved / fname
        if not fpath.exists():
            raise ValueError(
                f"verify_run_identity: required output file {fname} is missing"
            )

    # 11. Verify lock hash against root
    try:
        lock_hash = compute_lock_hash(root)
    except Exception as exc:
        raise ValueError(
            f"verify_run_identity: compute_lock_hash failed: {exc}"
        ) from exc
    if manifest.lock_hash != lock_hash:
        raise ValueError(
            "verify_run_identity: manifest.lock_hash does not match "
            "computed lock_hash"
        )

    # 12. Verify data manifest hash
    try:
        data_hash = compute_data_manifest_hash(root)
    except Exception as exc:
        raise ValueError(
            "verify_run_identity: compute_data_manifest_hash failed: "
            f"{exc}"
        ) from exc
    if manifest.data_manifest_hash != data_hash:
        raise ValueError(
            "verify_run_identity: manifest.data_manifest_hash does not match "
            "computed data_manifest_hash"
        )

    # 13. Verify parameter hash is non-zero
    if not manifest.parameter_hash or manifest.parameter_hash == "0" * 64:
        raise ValueError(
            "verify_run_identity: manifest.parameter_hash is zero "
            "(not a formal run)"
        )

    return manifest
