"""H4A-1 experiment initial-state admission — behavioral contracts.

The fixtures are software contracts.  They do not assert a historical observation,
a real approval, or a runtime-wired initial state.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from history.HIST_VNEXT.h4_sources.experiment_admission import (
    REQUIRED_REVIEW_FILES,
    SCHEMA_VERSION,
    audit_experiment_admission,
    load_experiment_declaration,
)
from hsm_lab.contract.schemas import ScenarioSpec
from hsm_lab.provenance.manifest import canonical_json

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path("config/initial_state/hist_vnext_h4_v1/experiment_inputs.json")
BASE = Path("config/scenarios/historical_f2_replay.json")
UPSTREAM = Path("docs/phases/HIST_VNEXT/H4A-0/APPROVED_INPUT_SET.json")
LEDGER = Path("docs/phases/HIST_VNEXT/H4A-1/ASSUMPTION_LEDGER.md")
MODULE = Path("history/HIST_VNEXT/h4_sources/experiment_admission.py")
TEST_FILE = Path("tests/test_hist_experiment_initial_admission.py")
H1A_REVIEW = Path("docs/phases/HIST_VNEXT/H4A-1/H1A_REREVIEW_ROUND14.md")
REVIEW_FILE = Path("docs/phases/HIST_VNEXT/H4A-1/EXPERIMENT_INPUT_REVIEW.json")
APPROVAL_FILE = Path("docs/phases/HIST_VNEXT/H4A-1/EXPERIMENT_INPUT_APPROVAL.json")
CHECKED_AT = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
REVIEWED_AT = CHECKED_AT - timedelta(hours=1)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_workspace(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for relative in REQUIRED_REVIEW_FILES:
        source = REPO_ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return root


def _read(root: Path, relative: Path) -> dict:
    return json.loads((root / relative).read_text())


def _write(root: Path, relative: Path, value: object) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _refresh_config_hashes(root: Path) -> None:
    config = _read(root, CONFIG)
    base_bytes = (root / BASE).read_bytes()
    config["base_scenario"]["sha256"] = hashlib.sha256(base_bytes).hexdigest()
    try:
        spec = ScenarioSpec.model_validate(json.loads(base_bytes))
    except Exception:
        # The malformed recipe is supposed to fail in the audit, not the fixture.
        _write(root, CONFIG, config)
        return
    assert spec.household_initial is not None
    assert spec.material_initial is not None
    config["base_scenario"]["household_recipe_sha256"] = hashlib.sha256(
        canonical_json(spec.household_initial.model_dump(mode="json"))
    ).hexdigest()
    config["base_scenario"]["material_recipe_sha256"] = hashlib.sha256(
        canonical_json(spec.material_initial.model_dump(mode="json"))
    ).hexdigest()
    config["upstream_approved_input_set"]["sha256"] = _sha(root / UPSTREAM)
    config["ledger_sha256"] = _sha(root / LEDGER)
    _write(root, CONFIG, config)


def _approve(
    root: Path,
    *,
    verdict: str = "PASS",
    reviewer_identity: str = "phase-reviewer:test",
    reviewed_at: datetime = REVIEWED_AT,
    issued_at: datetime = REVIEWED_AT,
    expires_at: datetime | None = None,
    approved_ids: list[str] | None = None,
    purpose: str = "initial_state",
    target_initial_at: str = "1957-01-01",
) -> tuple[Path, Path]:
    hashes = {relative: _sha(root / relative) for relative in REQUIRED_REVIEW_FILES}
    ids = approved_ids or [
        "h4exp_inherited_persons",
        "h4exp_inherited_households",
        "h4exp_dwelling_ratio",
    ]
    review = {
        "schema_version": SCHEMA_VERSION,
        "verdict": verdict,
        "reviewer_identity": reviewer_identity,
        "reviewer_role": "@review",
        "reviewed_at": reviewed_at.isoformat(),
        "reviewed_sha256": hashes,
        "approved_assumption_ids": ids,
        "purpose": purpose,
        "target_initial_at": target_initial_at,
        "expires_at": expires_at.isoformat() if expires_at is not None else None,
    }
    review_path = root / REVIEW_FILE
    _write(root, REVIEW_FILE, review)
    approval = {
        "schema_version": SCHEMA_VERSION,
        "review": {"path": str(REVIEW_FILE), "sha256": _sha(review_path)},
        "reviewed_sha256": hashes,
        "approved_assumption_ids": ids,
        "purpose": purpose,
        "target_initial_at": target_initial_at,
        "expires_at": expires_at.isoformat() if expires_at is not None else None,
        "issued_by": reviewer_identity,
        "issued_at": issued_at.isoformat(),
        "runtime_connected": False,
    }
    _write(root, APPROVAL_FILE, approval)
    return review_path, root / APPROVAL_FILE


def _audit(root: Path, approval: Path | None = None, checked_at: datetime = CHECKED_AT):
    return audit_experiment_admission(
        root,
        config_path=CONFIG,
        approval_path=approval,
        checked_at=checked_at,
    )


def _run_cli(root: Path, approval: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "history.HIST_VNEXT.h4_sources.experiment_admission",
        "--root",
        str(root),
        "--config",
        str(CONFIG),
    ]
    if approval is not None:
        command.extend(["--approval", str(approval)])
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return _copy_workspace(tmp_path)


# ---------------------------------------------------------------------------
# Declaration
# ---------------------------------------------------------------------------


class TestDeclaration:
    def test_declaration_loads_and_binds_hashes(self, workspace: Path):
        declaration = load_experiment_declaration(workspace, CONFIG)
        assert declaration.experiment_id == "h4exp_synthetic_dwelling_sensitivity_v1"
        assert declaration.classification == "synthetic"
        assert declaration.data_role == "initial_state"
        assert declaration.runtime_connected is False
        assert [record.assumption_id for record in declaration.records] == [
            "h4exp_inherited_persons",
            "h4exp_inherited_households",
            "h4exp_dwelling_ratio",
        ]

    def test_source_like_record_field_is_rejected(self, workspace: Path):
        config = _read(workspace, CONFIG)
        config["records"][0]["source_id"] = "pretend_source"
        _write(workspace, CONFIG, config)
        result = _audit(workspace)
        assert result["exit_code"] == 2
        assert result["structural"] == "BLOCKED"

    def test_direct_classification_is_rejected(self, workspace: Path):
        config = _read(workspace, CONFIG)
        config["classification"] = "direct"
        _write(workspace, CONFIG, config)
        result = _audit(workspace)
        assert result["exit_code"] == 2

    def test_unknown_target_is_rejected(self, workspace: Path):
        config = _read(workspace, CONFIG)
        config["records"][0]["target_field"] = "household_initial.counties[].invented"
        _write(workspace, CONFIG, config)
        result = _audit(workspace)
        assert result["exit_code"] == 2

    def test_duplicate_setting_is_rejected(self, workspace: Path):
        config = _read(workspace, CONFIG)
        config["settings"][1]["setting_id"] = "low"
        _write(workspace, CONFIG, config)
        result = _audit(workspace)
        assert result["exit_code"] == 2

    def test_baseline_must_equal_recipe(self, workspace: Path):
        config = _read(workspace, CONFIG)
        config["settings"][1]["value"] = 0.41
        _write(workspace, CONFIG, config)
        result = _audit(workspace)
        assert result["exit_code"] == 2

    def test_path_escape_is_rejected(self, workspace: Path):
        config = _read(workspace, CONFIG)
        config["base_scenario"]["path"] = "../outside.json"
        _write(workspace, CONFIG, config)
        result = _audit(workspace)
        assert result["exit_code"] == 2

    def test_sha_mismatch_is_rejected(self, workspace: Path):
        config = _read(workspace, CONFIG)
        config["base_scenario"]["sha256"] = "0" * 64
        _write(workspace, CONFIG, config)
        result = _audit(workspace)
        assert result["exit_code"] == 2


# ---------------------------------------------------------------------------
# Base recipe guards
# ---------------------------------------------------------------------------


class TestBaseRecipe:
    def _mutate_base(self, workspace: Path, mutation) -> dict:
        base = _read(workspace, BASE)
        mutation(base)
        _write(workspace, BASE, base)
        _refresh_config_hashes(workspace)
        return _audit(workspace)

    def test_missing_region_is_rejected(self, workspace: Path):
        def mutate(base: dict) -> None:
            base["region_ids"] = base["region_ids"][:-1]
        result = self._mutate_base(workspace, mutate)
        assert result["exit_code"] == 2

    def test_duplicate_region_is_rejected(self, workspace: Path):
        def mutate(base: dict) -> None:
            base["region_ids"][1] = base["region_ids"][0]
        result = self._mutate_base(workspace, mutate)
        assert result["exit_code"] == 2

    def test_bool_persons_is_rejected(self, workspace: Path):
        def mutate(base: dict) -> None:
            base["household_initial"]["counties"][0]["persons_total"] = True
        result = self._mutate_base(workspace, mutate)
        assert result["exit_code"] == 2

    def test_persons_below_households_is_rejected(self, workspace: Path):
        def mutate(base: dict) -> None:
            county = base["household_initial"]["counties"][0]
            county["persons_total"] = county["household_total"] - 1.0
        result = self._mutate_base(workspace, mutate)
        assert result["exit_code"] == 2

    def test_missing_material_recipe_is_rejected(self, workspace: Path):
        def mutate(base: dict) -> None:
            del base["material_initial"]
        result = self._mutate_base(workspace, mutate)
        assert result["exit_code"] == 2

    def test_non_finite_persons_is_rejected(self, workspace: Path):
        def mutate(base: dict) -> None:
            base["household_initial"]["counties"][0]["persons_total"] = "NaN"
        result = self._mutate_base(workspace, mutate)
        assert result["exit_code"] == 2


# ---------------------------------------------------------------------------
# Approval and audit
# ---------------------------------------------------------------------------


class TestApproval:
    def test_no_approval_is_pending(self, workspace: Path):
        result = _audit(workspace)
        assert result["exit_code"] == 1
        assert result["structural"] == "PASS"
        assert result["admission"] == "PENDING"
        assert result["historical"] == "NOT_ESTABLISHED"
        assert result["approved_inputs"] == []
        assert result["historical_inputs_admitted"] == 0
        assert result["runtime_connected"] is False

    def test_missing_approval_is_structural_block(self, workspace: Path):
        result = _audit(workspace, workspace / "missing.json")
        assert result["exit_code"] == 2
        assert result["structural"] == "BLOCKED"

    def test_valid_approval_is_experiment_only(self, workspace: Path):
        _, approval = _approve(workspace)
        result = _audit(workspace, approval)
        assert result["exit_code"] == 0
        assert result["structural"] == "PASS"
        assert result["admission"] == "EXPERIMENT_ONLY"
        assert result["historical"] == "NOT_ESTABLISHED"
        assert result["runtime_connected"] is False
        assert result["historical_inputs_admitted"] == 0
        assert len(result["approved_inputs"]) == 3

    def test_derived_quantities_are_complete(self, workspace: Path):
        _, approval = _approve(workspace)
        result = _audit(workspace, approval)
        derived = result["derived_quantities"]
        assert derived["units"] == {
            "persons": "persons",
            "households": "households",
            "dwellings": "dwellings",
        }
        assert len(derived["by_region"]) == 20
        for region in derived["by_region"].values():
            assert region["dwellings"]["low"] == pytest.approx(0.3 * region["persons"])
            assert region["dwellings"]["baseline"] == pytest.approx(0.4 * region["persons"])
            assert region["dwellings"]["high"] == pytest.approx(0.5 * region["persons"])
        for key in ("persons", "households"):
            assert derived["national"][key] == pytest.approx(
                math.fsum(region[key] for region in derived["by_region"].values())
            )
        for setting in ("low", "baseline", "high"):
            assert derived["national"]["dwellings"][setting] == pytest.approx(
                math.fsum(
                    region["dwellings"][setting]
                    for region in derived["by_region"].values()
                )
            )

    def test_non_pass_review_is_blocked(self, workspace: Path):
        _, approval = _approve(workspace, verdict="PATCH")
        result = _audit(workspace, approval)
        assert result["exit_code"] == 1
        assert result["admission"] == "BLOCKED"

    def test_same_declarer_and_reviewer_is_rejected(self, workspace: Path):
        _, approval = _approve(workspace, reviewer_identity="deepseek/deepseek-flash")
        result = _audit(workspace, approval)
        assert result["exit_code"] == 2

    def test_wrong_scope_is_rejected(self, workspace: Path):
        _, approval = _approve(
            workspace,
            approved_ids=["h4exp_inherited_persons"],
        )
        result = _audit(workspace, approval)
        assert result["exit_code"] == 2

    def test_wrong_purpose_is_rejected(self, workspace: Path):
        _, approval = _approve(workspace, purpose="measurement")
        result = _audit(workspace, approval)
        assert result["exit_code"] == 2

    def test_wrong_target_date_is_rejected(self, workspace: Path):
        _, approval = _approve(workspace, target_initial_at="1958-01-01")
        result = _audit(workspace, approval)
        assert result["exit_code"] == 2

    def test_stale_review_hash_is_rejected(self, workspace: Path):
        _, approval = _approve(workspace)
        (workspace / MODULE).write_text((workspace / MODULE).read_text() + "\n")
        result = _audit(workspace, approval)
        assert result["exit_code"] == 2
        assert any("stale" in error for error in result["errors"])

    def test_approval_without_review_file_is_rejected(self, workspace: Path):
        _, approval = _approve(workspace)
        (workspace / REVIEW_FILE).unlink()
        result = _audit(workspace, approval)
        assert result["exit_code"] == 2

    def test_expired_approval_is_blocked(self, workspace: Path):
        expires = CHECKED_AT - timedelta(seconds=1)
        _, approval = _approve(workspace, expires_at=expires)
        result = _audit(workspace, approval)
        assert result["exit_code"] == 1
        assert result["admission"] == "BLOCKED"

    def test_expiry_boundary_is_blocked(self, workspace: Path):
        expires = CHECKED_AT
        _, approval = _approve(workspace, expires_at=expires)
        result = _audit(workspace, approval)
        assert result["exit_code"] == 1

    def test_just_before_expiry_is_accepted(self, workspace: Path):
        expires = CHECKED_AT + timedelta(seconds=1)
        _, approval = _approve(workspace, expires_at=expires)
        result = _audit(workspace, approval)
        assert result["exit_code"] == 0

    def test_future_issued_approval_is_rejected(self, workspace: Path):
        future = CHECKED_AT + timedelta(seconds=1)
        _, approval = _approve(workspace, issued_at=future)
        result = _audit(workspace, approval)
        assert result["exit_code"] == 2

    def test_naive_datetime_is_rejected(self, workspace: Path):
        naive = datetime(2026, 10, 20, 11, 0)
        _, approval = _approve(workspace, reviewed_at=naive)
        result = _audit(workspace, approval)
        assert result["exit_code"] == 2

    def test_tampered_approval_scope_is_rejected(self, workspace: Path):
        _, approval = _approve(workspace)
        data = json.loads(approval.read_text())
        data["approved_assumption_ids"] = ["h4exp_inherited_persons"]
        _write(workspace, APPROVAL_FILE, data)
        result = _audit(workspace, approval)
        assert result["exit_code"] == 2

    def test_cli_pending_then_experiment_only(self, workspace: Path):
        pending = _run_cli(workspace)
        assert pending.returncode == 1
        assert json.loads(pending.stdout)["admission"] == "PENDING"
        _, approval = _approve(workspace)
        approved = _run_cli(workspace, approval)
        assert approved.returncode == 0
        body = json.loads(approved.stdout)
        assert body["admission"] == "EXPERIMENT_ONLY"
        assert body["historical_inputs_admitted"] == 0

    def test_cli_wrong_unit_is_structural_block(self, workspace: Path):
        config = _read(workspace, CONFIG)
        config["records"][2]["unit"] = "M_forint"
        _write(workspace, CONFIG, config)
        completed = _run_cli(workspace)
        assert completed.returncode == 2
        body = json.loads(completed.stdout)
        assert body["structural"] == "BLOCKED"
        assert body["approved_inputs"] == []

    def test_changed_recipe_byte_invalidates_approval(self, workspace: Path):
        _, approval = _approve(workspace)
        base = _read(workspace, BASE)
        base["household_initial"]["counties"][0]["persons_total"] += 0.01
        _write(workspace, BASE, base)
        result = _audit(workspace, approval)
        assert result["exit_code"] == 2

    def test_changed_test_byte_invalidates_approval(self, workspace: Path):
        _, approval = _approve(workspace)
        (workspace / TEST_FILE).write_text((workspace / TEST_FILE).read_text() + "\n")
        result = _audit(workspace, approval)
        assert result["exit_code"] == 2


# ---------------------------------------------------------------------------
# No historical forwarding
# ---------------------------------------------------------------------------


def test_audit_never_admits_historical_inputs(workspace: Path):
    _, approval = _approve(workspace)
    result = _audit(workspace, approval)
    assert result["historical_inputs_admitted"] == 0
    assert result["historical"] == "NOT_ESTABLISHED"
    assert result["runtime_connected"] is False
    for record in result["approved_inputs"]:
        assert record["historical_support"] == "none"
        assert "source_id" not in record
        assert "value_ref" not in record
