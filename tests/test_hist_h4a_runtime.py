"""H4A runtime connection: approved experiment inputs consumed by a real run."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from uuid import uuid4

from history.HIST_VNEXT.h4_sources.runtime_adapter import run_h4a_experiment

REPO_ROOT = Path(__file__).resolve().parents[1]


def _approval_case(*, expires_at: str | None, malformed: bool = False):
    """Create a repo-local approval (+ matching review) for admission tests."""
    base = REPO_ROOT / "outputs" / f"h4a-approval-test-{uuid4().hex}"
    base.mkdir(parents=True)
    review = json.loads(
        (REPO_ROOT / "docs/phases/HIST_VNEXT/H4A-1/EXPERIMENT_INPUT_REVIEW.json").read_text()
    )
    approval = json.loads(
        (REPO_ROOT / "docs/phases/HIST_VNEXT/H4A-1/EXPERIMENT_INPUT_APPROVAL.json").read_text()
    )
    review["expires_at"] = expires_at
    review_path = base / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    approval["expires_at"] = expires_at
    approval["review"] = {
        "path": review_path.relative_to(REPO_ROOT).as_posix(),
        "sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
    }
    if malformed:
        approval["approved_assumption_ids"] = []
    approval_path = base / "approval.json"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    return approval_path, base


def test_approved_experiment_is_consumed_and_measured(tmp_path: Path) -> None:
    result = run_h4a_experiment(
        REPO_ROOT,
        config_path=Path("config/initial_state/hist_vnext_h4_v1/experiment_inputs.json"),
        approval_path=Path("docs/phases/HIST_VNEXT/H4A-1/EXPERIMENT_INPUT_APPROVAL.json"),
        output_dir=tmp_path / "run",
        setting_ids=["baseline"],
    )

    assert result["runtime_connected"] is True
    assert result["historical_inputs_admitted"] == 0
    assert result["historical_status"] == "NOT_ESTABLISHED"
    assert len(result["consumed_by_model"]) == 3
    assert {row["assumption_id"] for row in result["consumed_by_model"]} == {
        "h4exp_inherited_persons",
        "h4exp_inherited_households",
        "h4exp_dwelling_ratio",
    }
    run = result["runs"]["baseline"]
    assert run["status"] == "completed"
    assert run["completed_ticks"] == 4

    measurement = json.loads(
        (tmp_path / "run" / "baseline" / "measurement.json").read_text(encoding="utf-8")
    )
    assert measurement["historical_comparison"] == "NOT_RUN"
    assert measurement["role"] == "model_measurement"
    assert measurement["run_id"] == run["run_id"]
    assert measurement["metrics"]["production_total"] > 0.0
    assert measurement["metrics"]["max_material_abs_residual"] < 1e-6
    assert measurement["metrics"]["max_finance_abs_residual"] < 1e-6

    runtime = json.loads((tmp_path / "run" / "runtime_manifest.json").read_text())
    assert runtime["consumed_by_model"] == result["consumed_by_model"]


def test_expired_approval_fails_closed(tmp_path: Path) -> None:
    approval_path, base = _approval_case(expires_at="2000-01-01T00:00:00+00:00")
    target = tmp_path / "expired-run"
    try:
        run_h4a_experiment(
            REPO_ROOT,
            config_path=Path(
                "config/initial_state/hist_vnext_h4_v1/experiment_inputs.json"
            ),
            approval_path=approval_path,
            output_dir=target,
            setting_ids=["baseline"],
        )
    except Exception as exc:  # noqa: BLE001 - ConfigError is the expected type
        assert "expired" in str(exc).lower(), str(exc)
    else:
        raise AssertionError("expired approval must fail closed")
    finally:
        shutil.rmtree(base)
    assert not target.exists()


def test_malformed_approval_fails_closed(tmp_path: Path) -> None:
    approval_path, base = _approval_case(expires_at=None, malformed=True)
    target = tmp_path / "bad-run"
    try:
        run_h4a_experiment(
            REPO_ROOT,
            config_path=Path(
                "config/initial_state/hist_vnext_h4_v1/experiment_inputs.json"
            ),
            approval_path=approval_path,
            output_dir=target,
            setting_ids=["baseline"],
        )
    except Exception as exc:  # noqa: BLE001 - ConfigError is the expected type
        assert "approval" in str(exc).lower(), str(exc)
    else:
        raise AssertionError("malformed approval must fail closed")
    finally:
        shutil.rmtree(base)
    assert not target.exists()
