"""P07A1 §3: provenance DAG for mechanism-card evidence.

The DAG tracks the chain from v1 card SHA-256 anchors through v2 cards,
metric specs, interventions, and run outputs. Each node is immutable and
content-addressed by its digest.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from hsm_lab.evidence.schemas import EvidenceStatus  # noqa: F401
from hsm_lab.evidence.table_registry import F2_TABLES
from hsm_lab.provenance.manifest import (  # noqa: F401
    MANIFEST_FILENAME,
    RunManifest,
    compute_data_manifest_hash,
    compute_lock_hash,
    compute_parameter_hash,
    hash_output_tree,
)

if TYPE_CHECKING:
    from hsm_lab.contract.schemas import ScenarioSpec


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


# Material runs are produced by ``hsm_lab.engine.material.run_material``, which
# always writes the compact per-tick trajectory tables plus the DuckDB
# trajectory store (``hsm_lab.storage.material_output.write_material_tables``).
_MATERIAL_RUN_KIND = "material_household_simulation"
_TRAJECTORY_STORE_FILENAME = "trajectory.duckdb"
_TRAJECTORY_TABLES_DIRNAME = "trajectory_tables"

# summary.json fields that must agree with the run manifest naming them. The
# summary is the run's own account of what completed, so a manifest/summary
# contradiction is a fabricated or mismatched pairing.
_SUMMARY_MIRRORED_MANIFEST_FIELDS = (
    "run_kind",
    "seed",
    "completed_ticks",
    "parameter_hash",
    "initial_recipe_hash",
    "deterministic_replay_digest",
    "input_artifact_hashes",
)

# Identity fields a completed material run's summary.json always records
# (``hsm_lab.engine.material._build_summary``). A summary that omits them is a
# placeholder — e.g. ``{"run_id": "test", "row_counts": {...}}`` — rather than
# the run's own account of what completed.
_MATERIAL_SUMMARY_REQUIRED_FIELDS = (
    "run_kind",
    "scenario_id",
    "seed",
    "planned_ticks",
    "completed_ticks",
    "households",
    "commodity_ids",
    "region_ids",
    "parameter_hash",
    "initial_recipe_hash",
    "deterministic_replay_digest",
    "input_artifact_hashes",
    "row_counts",
)

# The accounting certification a material run records in ``summary.json``.
# ``hsm_lab.engine.material`` advances ``completed_ticks`` only after
# ``check_material_invariants`` passed for the tick, so these fields are the
# run's own account of that certification: the worst per-cell residual of the
# material and finance accounting identities, the same residuals as a share of
# the tick's tolerance band, and the number of ticks the check covered.
_MATERIAL_SUMMARY_RESIDUAL_FIELDS = (
    "max_material_abs_residual",
    "max_finance_abs_residual",
)

# A tolerance ratio above 1.0 is a residual outside the tick's tolerance band:
# the tick recording it would not have been certified, so a summary that
# certifies it contradicts the gate that let the run finish.
_MATERIAL_SUMMARY_TOLERANCE_FIELDS = (
    "max_material_tolerance_ratio",
    "max_finance_tolerance_ratio",
)
_MATERIAL_TOLERANCE_CEILING = 1.0

_MATERIAL_SUMMARY_NUMERIC_INVARIANT_FIELDS = (
    *_MATERIAL_SUMMARY_RESIDUAL_FIELDS,
    *_MATERIAL_SUMMARY_TOLERANCE_FIELDS,
)
_MATERIAL_SUMMARY_INVARIANT_FIELDS = (
    *_MATERIAL_SUMMARY_NUMERIC_INVARIANT_FIELDS,
    "checked_ticks",
)

# The recipe declaration a material run writes beside its tables: the
# scenario's declared initial state (``declaration``), the hash of that recipe,
# and the scenario it belongs to. An empty ``{}`` is a stub, not a recipe.
_MATERIAL_RECIPE_FILENAME = "initial_recipe.json"

# Every compact material table carries these key columns, plus the axis key
# columns of the dimensions the table models (per the F2 table registry). A
# Parquet file holding only ``tick``/``value`` is not a table the material
# runner wrote.
_MATERIAL_TABLE_KEY_COLUMNS = ("tick", "quarter")
_MATERIAL_TABLE_AXIS_COLUMNS = (
    ("region_id", "has_region_axis"),
    ("commodity_id", "has_commodity_axis"),
    ("stage", "has_stage_axis"),
)
_MATERIAL_TABLE_MIN_COLUMNS = 3


def _trajectory_table_path(resolved: Path, table_name: str) -> Path | None:
    """Locate one compact trajectory table inside a run directory.

    Tables live either at the run root (``aggregates.parquet``) or in the
    equivalent ``trajectory_tables/`` directory.
    """
    for candidate in (
        resolved / f"{table_name}.parquet",
        resolved / _TRAJECTORY_TABLES_DIRNAME / f"{table_name}.parquet",
    ):
        if candidate.is_file():
            return candidate
    return None


def _verify_material_tick_data(
    resolved: Path,
    manifest: RunManifest,
    summary: dict[str, Any],
    scenario_spec: ScenarioSpec,
) -> None:
    """Require real tick-level trajectory data for a material run.

    ``summary.json``, ``parameters.json`` and ``initial_recipe.json`` can be
    written by hand — and can be made hash-consistent with each other — so
    their presence alone does not make a directory a run. A material run is
    only a run if the artefacts the material runner writes are present and
    actually carry what the run claims:

    * ``summary.json`` must be the run's own account, not a placeholder: it
      must carry the identity fields a completed material run records
      (``run_kind``, ``scenario_id``, ``seed``, ``planned_ticks``,
      ``completed_ticks``, ``households``, ``commodity_ids``, ``region_ids``,
      ``parameter_hash``, ``initial_recipe_hash``,
      ``deterministic_replay_digest``, ``input_artifact_hashes``,
      ``row_counts``), each agreeing with the manifest (see
      ``verify_run_identity`` step 10a for the mirrored fields);
    * ``summary.json``'s ``invariants`` block must be present and
      self-consistent: the material and finance residual/tolerance fields the
      runner's certification records, tolerance ratios at or below the 1.0
      ceiling, and ``checked_ticks`` equal to the ``completed_ticks`` the run
      reports — the certification is checked as the run's own account, not
      recomputed from the tables;
    * ``initial_recipe.json`` must declare the scenario's recipe: a non-empty
      ``declaration`` object, the recipe's ``initial_recipe_hash`` (matching
      the manifest), and the scenario id it belongs to. An empty ``{}`` — or a
      declaration without recipe content — is a stub. The declaration itself
      must be a valid material initial-state recipe *and* the concrete recipe
      the scenario declares: the recipe hash binds the scenario's
      organization/technology/route recipe rather than the initial-state
      declaration, so a hand-written declaration that only agrees on the hash
      is rejected;
    * the DuckDB trajectory store (``trajectory.duckdb``) or the equivalent
      ``trajectory_tables/`` directory must exist and be non-empty;
    * every table named by ``summary.json``'s ``row_counts`` must exist as a
      readable Parquet trajectory table with exactly the declared row count and
      the schema the material runner writes for that table — the ``tick`` and
      ``quarter`` keys plus the axis key columns of the dimensions the table
      models (``region_id``, ``commodity_id``, ``stage``) — so a hand-written
      ``tick,value`` file cannot stand in for a trajectory table;
    * every non-empty axis table must cover the run's declared commodity and
      region universe (``manifest.commodity_ids`` / ``manifest.region_ids``);
      and
    * the union of tick values across those tables must cover every completed
      tick (``0 … completed_ticks - 1``), so a truncated or stubbed trajectory
      cannot stand in for a full run.

    Raises
    ------
    ValueError
        If the summary is a placeholder or contradicts the manifest, the recipe
        is an empty stub or its hash/scenario disagrees, or its
        declaration is not the scenario's declared initial-state recipe, the
        trajectory store/tables are absent or empty, a declared table is
        missing/unreadable/empty or has the wrong row count or schema, an axis
        table omits part of the run's declared commodity/region universe, or
        the tick coverage does not match the manifest.
    """
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    # 1. summary.json must be the run's own account of what completed: a
    # placeholder such as ``{"run_id": "test"}`` cannot stand in for one, so
    # the identity fields a completed material run records must be present.
    # Step 10a then binds each mirrored field to the matching manifest value.
    missing_summary_fields = [
        name for name in _MATERIAL_SUMMARY_REQUIRED_FIELDS if name not in summary
    ]
    if missing_summary_fields:
        raise ValueError(
            "verify_run_identity: material run summary.json is missing the "
            "fields a completed run records: "
            f"{missing_summary_fields}; a placeholder summary is not a run"
        )
    for field_name in ("run_kind", "scenario_id"):
        field_value = summary[field_name]
        if not isinstance(field_value, str) or not field_value:
            raise ValueError(
                "verify_run_identity: material run summary.json "
                f"{field_name!r} must be a non-empty string, got {field_value!r}"
            )
    for field_name in ("commodity_ids", "region_ids"):
        field_value = summary[field_name]
        if (
            not isinstance(field_value, list)
            or not field_value
            or not all(isinstance(item, str) and item for item in field_value)
        ):
            raise ValueError(
                "verify_run_identity: material run summary.json "
                f"{field_name!r} must be a non-empty list of ids, got "
                f"{field_value!r}"
            )
    households = summary["households"]
    if not isinstance(households, int) or isinstance(households, bool) or households <= 0:
        raise ValueError(
            "verify_run_identity: material run summary.json 'households' must "
            f"be a positive integer, got {households!r}"
        )

    # 1b. The run's accounting certification must be present and internally
    # consistent. ``completed_ticks`` advances only after
    # ``check_material_invariants`` passed the tick, so a summary without the
    # block that records the check is not the account of a certified run — and
    # a block whose residual exceeds its tolerance band, or whose
    # ``checked_ticks`` disagrees with the run's own ``completed_ticks``,
    # contradicts the gate that let the run finish. This verifies the
    # certification the run reports; it does not recompute the accounting
    # (verify_run_identity is read-only and the residuals are the engine's).
    invariants = summary.get("invariants")
    if not isinstance(invariants, dict) or not invariants:
        raise ValueError(
            "verify_run_identity: material run summary.json has no non-empty "
            "'invariants' block; the accounting certification a completed tick "
            "requires is missing"
        )
    missing_invariants = [
        name for name in _MATERIAL_SUMMARY_INVARIANT_FIELDS if name not in invariants
    ]
    if missing_invariants:
        raise ValueError(
            "verify_run_identity: material run summary.json 'invariants' is "
            f"missing the fields the accounting certification records: "
            f"{missing_invariants}"
        )
    for field_name in _MATERIAL_SUMMARY_NUMERIC_INVARIANT_FIELDS:
        value = invariants[field_name]
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            raise ValueError(
                "verify_run_identity: material run summary.json "
                f"'invariants[{field_name}]' must be a finite number, got "
                f"{value!r}"
            )
        if value < 0.0:
            raise ValueError(
                "verify_run_identity: material run summary.json "
                f"'invariants[{field_name}]' is negative ({value!r}); a "
                "residual and its tolerance ratio cannot be negative"
            )
        if (
            field_name in _MATERIAL_SUMMARY_TOLERANCE_FIELDS
            and value > _MATERIAL_TOLERANCE_CEILING
        ):
            raise ValueError(
                "verify_run_identity: material run summary.json "
                f"'invariants[{field_name}]' is {value!r}, above the "
                f"{_MATERIAL_TOLERANCE_CEILING} tolerance ceiling; the run's "
                "own accounting certification is not satisfied"
            )
    checked_ticks = invariants["checked_ticks"]
    if not isinstance(checked_ticks, int) or isinstance(checked_ticks, bool):
        raise ValueError(
            "verify_run_identity: material run summary.json "
            f"'invariants[checked_ticks]' must be an integer, got "
            f"{checked_ticks!r}"
        )
    if checked_ticks != summary["completed_ticks"]:
        raise ValueError(
            "verify_run_identity: material run summary.json "
            f"'invariants.checked_ticks'={checked_ticks} does not match "
            f"completed_ticks={summary['completed_ticks']!r}; the accounting "
            "certification does not cover the ticks the run reports as "
            "completed"
        )

    # 2. initial_recipe.json must carry the scenario's recipe, not an empty
    # stub: the material runner writes the declared initial state under
    # ``declaration``, the hash of that recipe, and the scenario it belongs to.
    recipe_path = resolved / _MATERIAL_RECIPE_FILENAME
    try:
        recipe_raw = json.loads(recipe_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(
            f"verify_run_identity: material run {_MATERIAL_RECIPE_FILENAME} "
            f"cannot be read: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"verify_run_identity: {_MATERIAL_RECIPE_FILENAME} is not valid "
            f"JSON: {exc}"
        ) from exc
    if not isinstance(recipe_raw, dict) or not recipe_raw:
        raise ValueError(
            "verify_run_identity: material run "
            f"{_MATERIAL_RECIPE_FILENAME} must be a non-empty JSON object "
            "declaring the scenario's recipe"
        )
    declaration = recipe_raw.get("declaration")
    if not isinstance(declaration, dict) or not declaration:
        raise ValueError(
            "verify_run_identity: material run "
            f"{_MATERIAL_RECIPE_FILENAME} has no non-empty 'declaration' "
            "object; an empty recipe stub is not a run's initial recipe"
        )
    recorded_recipe_hash = recipe_raw.get("initial_recipe_hash")
    if not isinstance(recorded_recipe_hash, str) or not recorded_recipe_hash:
        raise ValueError(
            "verify_run_identity: material run "
            f"{_MATERIAL_RECIPE_FILENAME} has no 'initial_recipe_hash'"
        )
    if recorded_recipe_hash != manifest.initial_recipe_hash:
        raise ValueError(
            "verify_run_identity: "
            f"{_MATERIAL_RECIPE_FILENAME} initial_recipe_hash "
            f"{recorded_recipe_hash[:16]}... does not match "
            "manifest.initial_recipe_hash"
        )
    recorded_recipe_scenario = recipe_raw.get("scenario_id")
    if recorded_recipe_scenario != summary["scenario_id"]:
        raise ValueError(
            "verify_run_identity: "
            f"{_MATERIAL_RECIPE_FILENAME} scenario_id "
            f"{recorded_recipe_scenario!r} does not match summary.json "
            f"scenario_id {summary['scenario_id']!r}; the recipe belongs to "
            "another scenario"
        )

    # 2b. The declaration must be a real recipe of the declared schema, and it
    # must be the one the scenario declares. The recipe hash binds the
    # scenario's organization/technology/route recipe, not the initial-state
    # declaration, so a fabricated declaration would otherwise ride along on a
    # correct hash: hand-written JSON could claim an initial state the scenario
    # never declared while every hash in the directory still agrees.
    from hsm_lab.contract.material import MaterialInitialRecipe

    try:
        declared_recipe = MaterialInitialRecipe.model_validate(declaration)
    except Exception as exc:
        raise ValueError(
            "verify_run_identity: material run "
            f"{_MATERIAL_RECIPE_FILENAME} 'declaration' is not a valid "
            f"material initial-state recipe: {exc}"
        ) from exc
    expected_recipe = scenario_spec.material_initial
    if expected_recipe is not None:
        declared_payload = declared_recipe.model_dump(mode="json")
        expected_payload = expected_recipe.model_dump(mode="json")
        if declared_payload != expected_payload:
            differing = sorted(
                key
                for key in set(declared_payload) | set(expected_payload)
                if declared_payload.get(key) != expected_payload.get(key)
            )
            raise ValueError(
                "verify_run_identity: "
                f"{_MATERIAL_RECIPE_FILENAME} declaration does not match the "
                f"recipe scenario {summary['scenario_id']!r} declares "
                f"(differing fields: {differing}); a declaration the scenario "
                "never declared is not this run's initial recipe"
            )

    store = resolved / _TRAJECTORY_STORE_FILENAME
    tables_dir = resolved / _TRAJECTORY_TABLES_DIRNAME
    has_store = store.is_file() and store.stat().st_size > 0
    has_tables_dir = tables_dir.is_dir() and any(
        path.is_file() and path.stat().st_size > 0
        for path in tables_dir.rglob("*")
    )
    if not (has_store or has_tables_dir):
        raise ValueError(
            "verify_run_identity: material run has neither a "
            f"{_TRAJECTORY_STORE_FILENAME} trajectory store nor a non-empty "
            f"{_TRAJECTORY_TABLES_DIRNAME}/ directory; a JSON-only output "
            "directory is not a run"
        )

    row_counts = summary.get("row_counts")
    if not isinstance(row_counts, dict) or not row_counts:
        raise ValueError(
            "verify_run_identity: summary.json 'row_counts' must be a non-empty "
            "object for a material run"
        )

    covered_ticks: set[int] = set()
    for table_name, declared_rows in row_counts.items():
        if not isinstance(table_name, str) or not table_name:
            raise ValueError(
                "verify_run_identity: summary.json 'row_counts' has a non-string "
                f"table name: {table_name!r}"
            )
        if not isinstance(declared_rows, int) or isinstance(declared_rows, bool):
            raise ValueError(
                f"verify_run_identity: summary.json 'row_counts[{table_name}]' "
                f"must be an integer, got {declared_rows!r}"
            )
        table_path = _trajectory_table_path(resolved, table_name)
        if table_path is None:
            raise ValueError(
                f"verify_run_identity: summary.json declares trajectory table "
                f"{table_name!r} but no such Parquet file exists for this run"
            )
        if table_path.stat().st_size == 0:
            raise ValueError(
                f"verify_run_identity: trajectory table {table_path.name} is empty"
            )
        try:
            parquet_file = pq.ParquetFile(table_path)
        except Exception as exc:
            raise ValueError(
                "verify_run_identity: trajectory table "
                f"{table_path.name} is not a readable Parquet table: {exc}"
            ) from exc
        if "tick" not in set(parquet_file.schema_arrow.names):
            raise ValueError(
                "verify_run_identity: trajectory table "
                f"{table_path.name} has no 'tick' column; it is not a "
                "tick-grain trajectory table"
            )
        schema_names = set(parquet_file.schema_arrow.names)
        axis = F2_TABLES.get(table_name)
        expected_columns = list(_MATERIAL_TABLE_KEY_COLUMNS)
        if axis is not None:
            expected_columns.extend(
                column
                for column, axis_flag in _MATERIAL_TABLE_AXIS_COLUMNS
                if getattr(axis, axis_flag)
            )
        missing_columns = [
            column for column in expected_columns if column not in schema_names
        ]
        if missing_columns:
            raise ValueError(
                "verify_run_identity: trajectory table "
                f"{table_path.name} is missing the columns the material runner "
                f"writes for table {table_name!r}: {missing_columns}; a "
                "tick,value stub is not a trajectory table"
            )
        if len(schema_names) < _MATERIAL_TABLE_MIN_COLUMNS:
            raise ValueError(
                "verify_run_identity: trajectory table "
                f"{table_path.name} has only the columns {sorted(schema_names)}; "
                "a material table carries its own data columns, not a "
                "tick/value stub"
            )
        actual_rows = parquet_file.metadata.num_rows
        if actual_rows != declared_rows:
            raise ValueError(
                f"verify_run_identity: trajectory table {table_path.name} has "
                f"{actual_rows} rows but summary.json declares {declared_rows}"
            )
        if actual_rows > 0 and axis is not None:
            # A non-empty axis table must actually carry the run's declared
            # commodity/region universe: a table covering a handful of ids
            # while the manifest declares many is not the run's own output.
            for axis_column, axis_flag, declared_ids in (
                ("commodity_id", "has_commodity_axis", manifest.commodity_ids),
                ("region_id", "has_region_axis", manifest.region_ids),
            ):
                if not getattr(axis, axis_flag) or not declared_ids:
                    continue
                present_ids = {
                    value
                    for value in pq.read_table(
                        table_path, columns=[axis_column]
                    ).column(axis_column).to_pylist()
                    if value is not None
                }
                missing_ids = [
                    value for value in declared_ids if value not in present_ids
                ]
                if missing_ids:
                    raise ValueError(
                        "verify_run_identity: trajectory table "
                        f"{table_path.name} has no rows for declared "
                        f"{axis_column} value(s) {missing_ids[:5]}; the table "
                        "does not cover the run's declared universe"
                    )
        tick_column = pq.read_table(table_path, columns=["tick"]).column("tick")
        covered_ticks.update(int(tick) for tick in tick_column.to_pylist())

    expected_ticks = set(range(manifest.completed_ticks))
    if covered_ticks != expected_ticks:
        missing = sorted(expected_ticks - covered_ticks)[:5]
        raise ValueError(
            "verify_run_identity: trajectory tick coverage mismatch — "
            f"{len(covered_ticks)} distinct ticks on disk vs "
            f"completed_ticks={manifest.completed_ticks} "
            f"(missing e.g. {missing})"
        )


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

    Beyond the standard run-provenance checks, the recorded
    ``parameters.json`` must declare the same ``parameter_hash`` as the run
    manifest, and that hash must equal the hash recomputed from the scenario
    spec's material parameter vector (``material_parameter_vector`` →
    ``compute_parameter_hash``). A manifest therefore cannot claim a parameter
    identity that its own output directory — or the scenario it names —
    contradicts.

    Three further identities are recomputed from the repository and the
    scenario spec rather than trusted from the manifest:

    * ``scenario_hash`` — from the scenario spec with the requested ``seed``
      override applied (the same override the CLI applies before running), so
      seed-overridden runs are still identified by content.
    * ``baseline_hash`` — from the live ``BASELINE.md`` bytes (via
      ``verify_baseline``, which also refuses on contract drift).
    * ``initial_recipe_hash`` and ``input_artifact_hashes`` — from
      ``material_recipe_hash`` and from re-admitting the scenario's forcing
      pack through ``DataRegistry`` + ``load_material_forcing``, i.e. the same
      gates the engine uses. These two bindings apply where the scenario spec
      declares the corresponding material components; non-material scenarios
      (e.g. ``smoke``) declare none and are skipped.

    The output directory itself must agree with the manifest, not merely exist:
    ``summary.json`` must be a non-empty object declaring this ``run_id`` whose
    identity fields (``run_kind``, ``seed``, ``completed_ticks``,
    ``parameter_hash``, ``initial_recipe_hash``,
    ``deterministic_replay_digest``, ``input_artifact_hashes``,
    ``planned_ticks``) do not contradict the manifest. Material runs must
    additionally ship the material runner's tick-level trajectory data: a
    DuckDB trajectory store or ``trajectory_tables/`` directory, plus every
    table ``summary.json`` declares in ``row_counts`` as a Parquet table with
    the material runner's schema for that table (``tick``/``quarter`` keys,
    the table's axis key columns, real columns), the declared row count, the
    run's declared commodity/region universe, and tick coverage of every
    completed tick. The summary must carry the identity fields a completed
    material run records, and ``initial_recipe.json`` must declare the
    scenario's actual recipe (non-empty declaration matching the scenario's
    declared initial-state recipe, matching recipe hash and scenario id) rather
    than an empty stub. A hand-written directory of
    summary/parameters/recipe JSON — or one whose tables are ``tick,value``
    stubs — is rejected.

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

    # 7. scenario_id must be a known scenario; recompute scenario_hash.
    # The run itself is started from the spec *after* the CLI's ``--seed``
    # override has been applied, so the manifest's scenario_hash describes the
    # overridden spec rather than the file on disk. Applying the same override
    # here keeps the recomputation faithful to what the engine actually hashed.
    try:
        scenario_spec: ScenarioSpec = load_scenario(root, scenario_id)
    except Exception as exc:
        raise ValueError(
            f"verify_run_identity: scenario_id={scenario_id!r} is not "
            f"a known scenario: {exc}"
        ) from exc
    scenario_with_seed = scenario_spec.model_copy(update={"seed": seed})
    try:
        from hsm_lab.provenance.manifest import compute_scenario_hash

        computed_hash = compute_scenario_hash(scenario_with_seed)
    except Exception as exc:
        raise ValueError(
            f"verify_run_identity: failed to compute scenario_hash: {exc}"
        ) from exc
    if manifest.scenario_hash != computed_hash:
        raise ValueError(
            "verify_run_identity: manifest.scenario_hash does not match "
            f"computed scenario_hash for scenario_id={scenario_id!r}"
        )

    # 7a. manifest.ticks must match scenario_spec.ticks
    if manifest.ticks != scenario_spec.ticks:
        raise ValueError(
            f"verify_run_identity: manifest.ticks={manifest.ticks} does not match "
            f"scenario_spec.ticks={scenario_spec.ticks} for scenario_id={scenario_id!r}"
        )

    # 8. All manifest hashes must be non-zero (no stub/zero digests)
    for field_name in (
        "scenario_hash",
        "lock_hash",
        "data_manifest_hash",
        "parameter_hash",
        "deterministic_replay_digest",
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

    # 10a. summary.json must be the run's own record, not a placeholder: it must
    # be a non-empty object that declares this run's id and whose identity fields
    # agree with the manifest the directory is filed under.
    summary_path = resolved / "summary.json"
    try:
        summary_raw = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"verify_run_identity: summary.json is not valid JSON: {exc}"
        ) from exc
    if not isinstance(summary_raw, dict) or not summary_raw:
        raise ValueError(
            "verify_run_identity: summary.json must be a non-empty JSON object "
            "describing the run"
        )
    recorded_run_id = summary_raw.get("run_id")
    if not isinstance(recorded_run_id, str) or not recorded_run_id:
        raise ValueError(
            "verify_run_identity: summary.json has no 'run_id' field"
        )
    if recorded_run_id != manifest.run_id:
        raise ValueError(
            f"verify_run_identity: summary.json run_id {recorded_run_id!r} does "
            f"not match manifest.run_id {manifest.run_id!r}"
        )
    for field_name in _SUMMARY_MIRRORED_MANIFEST_FIELDS:
        if field_name not in summary_raw:
            continue
        recorded_value = summary_raw[field_name]
        manifest_value = getattr(manifest, field_name)
        if recorded_value != manifest_value:
            raise ValueError(
                f"verify_run_identity: summary.json {field_name} "
                f"{recorded_value!r} contradicts manifest.{field_name} "
                f"{manifest_value!r}"
            )
    if "planned_ticks" in summary_raw and summary_raw["planned_ticks"] != manifest.ticks:
        raise ValueError(
            "verify_run_identity: summary.json planned_ticks "
            f"{summary_raw['planned_ticks']!r} contradicts manifest.ticks "
            f"{manifest.ticks!r}"
        )

    # 10b. A material run must ship the tick-level trajectory data the material
    # runner writes. Steps 9–10 only prove that the JSON artefacts agree with
    # each other, which a hand-written directory can satisfy; the trajectory
    # tables are what make it an actual run.
    if manifest.run_kind == _MATERIAL_RUN_KIND:
        _verify_material_tick_data(resolved, manifest, summary_raw, scenario_spec)

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

    # 14. parameters.json must record the same parameter hash as the manifest.
    # The byte-level integrity of parameters.json is already covered by the
    # output-tree digest check (step 9); this check binds the parameter identity
    # declared inside the run output to the value the manifest claims.
    parameters_path = resolved / "parameters.json"
    try:
        parameters_raw = json.loads(parameters_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"verify_run_identity: parameters.json is not valid JSON: {exc}"
        ) from exc
    if not isinstance(parameters_raw, dict):
        raise ValueError(
            "verify_run_identity: parameters.json must be a JSON object"
        )
    recorded_parameter_hash = parameters_raw.get("parameter_hash")
    if not isinstance(recorded_parameter_hash, str) or not recorded_parameter_hash:
        raise ValueError(
            "verify_run_identity: parameters.json has no 'parameter_hash' field"
        )
    if recorded_parameter_hash != manifest.parameter_hash:
        raise ValueError(
            "verify_run_identity: parameters.json parameter_hash "
            f"{recorded_parameter_hash[:16]}... does not match "
            f"manifest.parameter_hash {manifest.parameter_hash[:16]}..."
        )

    # 15. Parameter identity must match the scenario specification. Steps 13–14
    # only bind parameters.json to the run manifest, so a fabricated run could
    # satisfy both while claiming parameters the scenario never declared.
    # Recomputing the hash from the canonical spec's material parameter vector
    # (exactly as the run itself derives it) ties ``parameter_hash`` to
    # ``scenario_id``. Non-material scenarios (e.g. ``smoke``, used by
    # ``synthetic_engine_smoke``) declare no parameter vector to recompute from,
    # so this binding only applies where the spec actually carries one.
    if (
        scenario_spec.material_parameters is not None
        and scenario_spec.material_initial is not None
    ):
        try:
            from hsm_lab.engine.material import material_parameter_vector

            recomputed_parameter_hash = compute_parameter_hash(
                material_parameter_vector(scenario_spec)
            )
        except Exception as exc:
            raise ValueError(
                "verify_run_identity: failed to recompute parameter_hash from "
                f"scenario spec {scenario_id!r}: {exc}"
            ) from exc
        if manifest.parameter_hash != recomputed_parameter_hash:
            raise ValueError(
                "verify_run_identity: manifest.parameter_hash "
                f"{manifest.parameter_hash[:16]}... does not match the hash "
                f"recomputed from scenario {scenario_id!r} "
                f"({recomputed_parameter_hash[:16]}...)"
            )

    # 16. baseline_hash must be the digest of the live BASELINE.md. Steps 11–12
    # pin the lockfile and the data manifests, but nothing else binds the
    # research baseline the run claims to honour to the bytes in the repository.
    # ``verify_baseline`` re-checks the file against the pinned contract hash
    # (refusing on drift) and returns the actual digest.
    try:
        from hsm_lab.contract.guards import (
            BASELINE_FILENAME,
            load_research_contract,
            verify_baseline,
        )

        contract = load_research_contract(root)
        live_baseline_hash = verify_baseline(root / BASELINE_FILENAME, contract)
    except Exception as exc:
        raise ValueError(
            f"verify_run_identity: baseline verification failed: {exc}"
        ) from exc
    if manifest.baseline_hash != live_baseline_hash:
        raise ValueError(
            "verify_run_identity: manifest.baseline_hash "
            f"{manifest.baseline_hash[:16]}... does not match the live "
            f"BASELINE.md hash ({live_baseline_hash[:16]}...)"
        )

    # 17. initial_recipe_hash must be the digest of the scenario's declared
    # recipe. Material scenarios declare organization_recipe/technologies, so a
    # run that names one may not present a recipe identity the spec contradicts.
    # Neither the recipe nor its hash depends on the run seed.
    if (
        scenario_spec.organization_recipe is not None
        and scenario_spec.technologies is not None
    ):
        try:
            from hsm_lab.engine.material import material_recipe_hash

            recomputed_recipe_hash = material_recipe_hash(scenario_spec)
        except Exception as exc:
            raise ValueError(
                "verify_run_identity: failed to recompute initial_recipe_hash "
                f"from scenario spec {scenario_id!r}: {exc}"
            ) from exc
        if manifest.initial_recipe_hash != recomputed_recipe_hash:
            recorded_recipe = manifest.initial_recipe_hash or "<missing>"
            raise ValueError(
                "verify_run_identity: manifest.initial_recipe_hash "
                f"{recorded_recipe[:16]} does not match the hash recomputed "
                f"from scenario {scenario_id!r} "
                f"({recomputed_recipe_hash[:16]}...)"
            )

    # 18. input_artifact_hashes must match the forcing inputs actually admitted
    # for the scenario. Re-admitting them through the same registry and loader
    # the engine uses (role/rights/digest gates, pack integrity, coverage) binds
    # the declared inputs to the repository data; a fabricated run cannot claim
    # input digests its own forcing pack contradicts.
    if (
        scenario_spec.forcing_pack is not None
        and scenario_spec.material_parameters is not None
    ):
        try:
            from hsm_lab.data.registry import DataRegistry
            from hsm_lab.engine.material import load_material_forcing

            registry = DataRegistry.load(
                root, allowed_commodities=scenario_spec.commodities
            )
            forcing = load_material_forcing(scenario_spec, registry)
            recomputed_input_hashes = dict(forcing.input_artifact_hashes)
        except Exception as exc:
            raise ValueError(
                "verify_run_identity: failed to reload forcing inputs for "
                f"scenario {scenario_id!r}: {exc}"
            ) from exc
        if dict(manifest.input_artifact_hashes) != recomputed_input_hashes:
            raise ValueError(
                "verify_run_identity: manifest.input_artifact_hashes "
                f"{sorted(manifest.input_artifact_hashes)} do not match the "
                "forcing inputs admitted for scenario "
                f"{scenario_id!r} ({sorted(recomputed_input_hashes)})"
            )

    return manifest
