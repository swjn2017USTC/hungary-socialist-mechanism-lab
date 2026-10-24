"""H5F-F1 / M09 consumer-behaviour tests.

The tests exercise only public boundaries: the forecast adapter, the reviewed
H2B procurement bridge on the tiny material fixture, and the study runner's
read-only package verifier.  No source text or private implementation detail is
pinned.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from hsm_lab.contract.politics import INFORMATION_DIMENSION_IDS
from hsm_lab.engine.material import canonical_material_bytes, tick_material
from hsm_lab.institutions.authority import authority_at
from hsm_lab.institutions.decisions import (
    ActorRole,
    ProcurementChoiceKind,
    ProcurementDecision,
)
from hsm_lab.institutions.execution_adapter import commit_proposal
from hsm_lab.institutions.forecast_error_adapter import (
    ForecastReport,
    RealizedForecast,
    issue_forecast,
    score_forecast,
)
from hsm_lab.institutions.observed import ActorObservation, ObservationBuilder
from hsm_lab.institutions.proposal_validation import ValidationResult
from hsm_lab.institutions.schemas import (
    AuthorityScope,
    DateInterval,
    InstitutionEvent,
    RegimeCalendar,
)
from hsm_lab.provenance.manifest import canonical_digest, canonical_json
from tests.test_hist_tiny_execution import make_two_region

RUN_ID = "run-test"
SUBJECT = "ORG-SRC-0"


# ---------------------------------------------------------------------------
# Adapter helpers
# ---------------------------------------------------------------------------


def _observation(
    *,
    issued_quarter: str,
    issued_at: date,
    published_at: date,
    value: float,
) -> ActorObservation:
    return ObservationBuilder("procurement_organization").build(
        organization_id="ORG-ENT-A",
        sector_id="industry",
        geographic_id="national",
        quarter=issued_quarter,
        decision_at=issued_at,
        available_at=published_at,
        raw_data={"quarter": issued_quarter, "supply_quantity": value},
    )


def make_report(
    measurement_quarter: str,
    value: float,
    *,
    issued_quarter: str = "1957Q3",
    issued_at: date = date(1957, 7, 15),
    published_at: date | None = None,
    subject: str = SUBJECT,
    unit: str = "p02_energy_unit",
    commodity: str = "energy",
) -> ForecastReport:
    published = published_at or date(1957, 6, 10)
    return ForecastReport(
        observation=_observation(
            issued_quarter=issued_quarter,
            issued_at=issued_at,
            published_at=published,
            value=value,
        ),
        measurement_quarter=measurement_quarter,
        subject_organization_id=subject,
        commodity_id=commodity,
        stage="standard",
        unit=unit,
    )


def _forecast_id(run_id: str, issued: str, target: str, subject: str = SUBJECT) -> str:
    return f"{run_id}:{issued}:{target}:energy:standard:{subject}"


def make_issued(
    *,
    method: str,
    run_id: str = RUN_ID,
    arm_id: str | None = None,
    reports: tuple[ForecastReport, ForecastReport] | None = None,
) -> object:
    forecast_reports = reports or (
        make_report("1957Q1", 2.0, published_at=date(1957, 4, 10)),
        make_report("1957Q2", 4.0, published_at=date(1957, 7, 10)),
    )
    return issue_forecast(
        forecast_reports,
        forecast_id=_forecast_id(run_id, "1957Q3", "1957Q4"),
        run_id=run_id,
        seed=1729,
        arm_id=arm_id or f"arm_{method}",
        issued_quarter="1957Q3",
        issued_at=date(1957, 7, 15),
        target_quarter="1957Q4",
        method=method,
    )


def make_realized(
    issued: object,
    value: float,
    *,
    realized_at: date = date(1957, 12, 31),
    seed: int = 1729,
    arm_id: str | None = None,
    witness: str | None = None,
) -> RealizedForecast:
    return RealizedForecast(
        forecast_id=issued.forecast_id,
        run_id=issued.run_id,
        seed=seed,
        arm_id=arm_id or issued.arm_id,
        subject_organization_id=issued.subject_organization_id,
        commodity_id=issued.commodity_id,
        stage=issued.stage,
        unit=issued.unit,
        target_quarter=issued.target_quarter,
        measurement_quarter=issued.target_quarter,
        realized_at=realized_at,
        realized_value=value,
        kernel_tick=4,
        kernel_quarter=issued.target_quarter,
        witness_sha256=witness or "a" * 64,
    )


def test_issued_prediction_and_residual_are_real_values_not_definition_scores() -> None:
    persistence = make_issued(method="persistence")
    linear = make_issued(method="linear")
    assert persistence.prediction == 4.0
    assert linear.prediction == 8.0
    assert linear.raw_prediction == 8.0
    assert linear.clipping_delta == 0.0

    first = score_forecast(persistence, make_realized(persistence, 3.0))
    second = score_forecast(linear, make_realized(linear, 3.0))
    assert first.residual == pytest.approx(-1.0)
    assert first.absolute_error == pytest.approx(1.0)
    assert second.residual == pytest.approx(-5.0)
    assert second.absolute_error == pytest.approx(5.0)

    from hsm_lab.engine.technology import InformationParameters, information_dimensions

    dimensions = information_dimensions(0.25, InformationParameters())
    definition_score = dimensions[INFORMATION_DIMENSION_IDS.index("forecast_accuracy")]
    assert definition_score == pytest.approx(0.25)
    assert first.absolute_error != pytest.approx(1.0 - definition_score)


def test_linear_clips_at_zero_and_records_the_clipping_delta() -> None:
    reports = (
        make_report("1957Q1", 1.0, published_at=date(1957, 4, 10)),
        make_report("1957Q2", 0.5, published_at=date(1957, 7, 10)),
    )
    issued = make_issued(method="linear", reports=reports)
    assert issued.raw_prediction < 0.0
    assert issued.prediction == 0.0
    assert issued.clipping_delta == pytest.approx(-issued.raw_prediction)


def test_adapter_rejects_unpublished_future_and_mixed_inputs() -> None:
    issued_at = date(1957, 7, 15)
    good = make_report("1957Q2", 4.0, published_at=date(1957, 7, 10))
    older = make_report("1957Q1", 2.0, published_at=date(1957, 4, 10))
    with pytest.raises(ValueError):
        make_report("1957Q2", 4.0, published_at=date(1957, 10, 10))
    same_quarter = make_report("1957Q3", 4.0, published_at=date(1957, 7, 10))
    pre_close = make_report("1957Q2", 4.0, published_at=date(1957, 4, 20))
    nonconsecutive = make_report("1956Q4", 4.0, published_at=date(1957, 1, 10))

    def issue(reports: tuple[ForecastReport, ...], target: str = "1957Q4"):
        return issue_forecast(
            reports,
            forecast_id=_forecast_id(RUN_ID, "1957Q3", target),
            run_id=RUN_ID,
            seed=1729,
            arm_id="arm",
            issued_quarter="1957Q3",
            issued_at=issued_at,
            target_quarter=target,
            method="persistence",
        )

    with pytest.raises(ValueError):
        issue((older, pre_close))
    with pytest.raises(ValueError):
        issue((older, same_quarter))
    with pytest.raises(ValueError):
        issue((nonconsecutive, good))
    with pytest.raises(ValueError):
        issue((good, good))
    with pytest.raises(ValueError):
        issue((older, good), target="1958Q1")
    with pytest.raises(ValueError):
        issue((older, make_report("1957Q2", 4.0, subject="OTHER")), target="1957Q4")
    with pytest.raises(ValueError):
        issue((older, make_report("1957Q2", 4.0, unit="p01_unit")), target="1957Q4")
    with pytest.raises(TypeError):
        issue_forecast([older, good], forecast_id="x", run_id=RUN_ID, seed=1729,
                       arm_id="arm", issued_quarter="1957Q3", issued_at=issued_at,
                       target_quarter="1957Q4", method="persistence")


def test_adapter_rejects_forged_observation_and_wrong_forecast_identity() -> None:
    older = make_report("1957Q1", 2.0, published_at=date(1957, 4, 10))
    newer = make_report("1957Q2", 4.0, published_at=date(1957, 7, 10))
    forged = ForecastReport.model_construct(
        observation=older.observation,
        measurement_quarter=older.measurement_quarter,
        subject_organization_id=older.subject_organization_id,
        commodity_id=older.commodity_id,
        stage=older.stage,
    )
    with pytest.raises(ValueError):
        issue_forecast(
            (forged, newer),
            forecast_id=_forecast_id(RUN_ID, "1957Q3", "1957Q4"),
            run_id=RUN_ID,
            seed=1729,
            arm_id="arm",
            issued_quarter="1957Q3",
            issued_at=date(1957, 7, 15),
            target_quarter="1957Q4",
            method="persistence",
        )
    with pytest.raises(ValueError):
        issue_forecast(
            (older, newer),
            forecast_id="not-the-canonical-id",
            run_id=RUN_ID,
            seed=1729,
            arm_id="arm",
            issued_quarter="1957Q3",
            issued_at=date(1957, 7, 15),
            target_quarter="1957Q4",
            method="persistence",
        )
    with pytest.raises(ValueError):
        issue_forecast(
            (older, newer),
            forecast_id=_forecast_id(RUN_ID, "1957Q3", "1957Q4"),
            run_id=RUN_ID,
            seed=1729,
            arm_id="arm",
            issued_quarter="1957Q3",
            issued_at=date(1957, 7, 15),
            target_quarter="1957Q4",
            method="trend",
        )


def test_score_rejects_mismatched_join_early_or_non_finite_realization() -> None:
    issued = make_issued(method="persistence")
    good = make_realized(issued, 3.0)
    assert score_forecast(issued, good).residual == pytest.approx(-1.0)
    for bad in (
        make_realized(issued, 3.0, seed=1730),
        make_realized(issued, 3.0, arm_id="other"),
        make_realized(issued, 3.0, realized_at=date(1957, 9, 30)),
        make_realized(issued, float("nan")),
        make_realized(issued, float("inf")),
        make_realized(issued, 3.0, witness="not-a-hash"),
    ):
        with pytest.raises(ValueError):
            score_forecast(issued, bad)
    pre_close = issued.model_copy(
        update={
            "newer_available_at": date(1957, 4, 20),
            "available_at": date(1957, 4, 20),
        }
    )
    with pytest.raises(ValueError):
        score_forecast(pre_close, make_realized(issued, 3.0))


def test_missing_realization_stays_out_of_the_mae() -> None:
    from studies.HIST_VNEXT.M09 import runner

    rows = []
    for arm in runner.ARMS:
        for _target in ("1957Q4", "1958Q1", "1958Q2"):
            rows.append(
                {
                    "seed": 1729,
                    "arm": arm,
                    "residual": 1.0,
                    "absolute_error": 1.0,
                }
            )
    with pytest.raises(runner.RunnerError):
        runner._matrix_entry(rows, expected_per_arm=4)


# ---------------------------------------------------------------------------
# Real tiny kernel behaviour
# ---------------------------------------------------------------------------


def _tiny_energy_cell(fixture) -> int:
    return fixture.network.cell_index[
        ("organization", 1, 0, "output", "energy", "standard")
    ]


def _tiny_production(fixture) -> float:
    flows = tick_material(
        fixture.state, fixture.forcing(1), fixture.parameters, fixture.network
    )
    produced = np.asarray(flows.activity_realized, dtype=np.float64) @ fixture.network.B
    return float(np.asarray(produced, dtype=np.float64).reshape(-1)[_tiny_energy_cell(fixture)])


def test_same_issued_forecast_scores_two_real_kernel_outcomes_differently() -> None:
    high = make_two_region()
    low = make_two_region()
    low.state.organization_capacity[1] = 40.0
    low.network.activity_capacity[0] = 40.0

    high_value = _tiny_production(high)
    low_value = _tiny_production(low)
    assert high_value == pytest.approx(100.0)
    assert low_value == pytest.approx(40.0)

    issued = make_issued(method="persistence")
    before = issued.model_dump(mode="json")
    high_residual = score_forecast(issued, make_realized(issued, high_value))
    low_residual = score_forecast(issued, make_realized(issued, low_value))
    assert issued.model_dump(mode="json") == before
    assert high_residual.residual != low_residual.residual
    assert high_residual.prediction == low_residual.prediction == 4.0
    assert high_value != 7.0  # not a request echo


def _procurement_decision(
    *,
    quarter: str = "1957Q1",
    quantity: float = 50.0,
    organization_id: str = "3",
) -> ProcurementDecision:
    month = {"1957Q1": 1, "1957Q2": 4}[quarter]
    return ProcurementDecision(
        decision_id=f"proc-{quarter}-{quantity}",
        actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
        organization_id=organization_id,
        sector_id="industry",
        quarter=quarter,
        decision_at=date(1957, month, 15),
        available_at=date(1957, month, 10),
        kind=ProcurementChoiceKind.REQUEST,
        commodity_id="energy",
        requested_quantity=quantity,
    )


def _validation(decision: ProcurementDecision, *, legal: bool = True) -> ValidationResult:
    digest = hashlib.sha256(
        decision.model_dump_json().encode("utf-8")
    ).hexdigest()
    return ValidationResult(
        decision_id=decision.decision_id,
        is_legal=legal,
        authority_status="granted" if legal else "revoked",
        reason="legal" if legal else "revoked",
        mode="admission",
        admission_eligible=legal,
        decision_digest=digest,
    )


def test_procurement_commit_advances_once_and_pays() -> None:
    fixture = make_two_region()
    decision = _procurement_decision()
    result = commit_proposal(
        decision,
        _validation(decision),
        fixture.state,
        fixture.forcing(1),
        fixture.parameters,
        fixture.network,
        organization_index={"3": 3},
    )
    assert result.is_committed
    assert result.flows is not None
    assert int(fixture.state.completed_ticks) == 1
    trace = dict(result.trace)
    assert trace["delivered_quantity"] >= 0.0
    assert trace["buyer_payment"] >= 0.0
    assert trace["completed_ticks_after"] == 1


def test_rejected_validation_does_not_change_state_or_clock() -> None:
    fixture = make_two_region()
    decision = _procurement_decision()
    before = canonical_material_bytes(fixture.state)
    result = commit_proposal(
        decision,
        _validation(decision, legal=False),
        fixture.state,
        fixture.forcing(1),
        fixture.parameters,
        fixture.network,
        organization_index={"3": 3},
    )
    assert not result.is_committed
    assert int(fixture.state.completed_ticks) == 0
    assert canonical_material_bytes(fixture.state) == before


def test_zero_cash_delivery_block_does_not_improve_consumption() -> None:
    fixture = make_two_region()
    fixture.state.organization_capacity[1] = 0.0
    fixture.network.activity_capacity[0] = 0.0
    energy_cells = np.asarray(fixture.network.cell_commodity) == fixture.g("energy")
    fixture.state.stock_value[energy_cells] = 0.0
    baseline_state = copy.deepcopy(fixture.state)
    baseline_flows = tick_material(
        baseline_state,
        fixture.forcing(1),
        fixture.parameters,
        fixture.network,
    )
    decision = _procurement_decision(quantity=50.0)
    result = commit_proposal(
        decision,
        _validation(decision),
        fixture.state,
        fixture.forcing(1),
        fixture.parameters,
        fixture.network,
        organization_index={"3": 3},
    )
    assert result.is_committed
    assert result.flows is not None
    incremental = dict(result.trace)["incremental_delivered_quantity"]
    assert incremental == pytest.approx(0.0)
    trace = dict(result.trace)
    assert trace["binding_status"] == "binding"
    assert trace["plan_actual_gap"] == pytest.approx(50.0)
    controlled = float(np.asarray(result.flows.household_realized).sum())
    baseline = float(np.asarray(baseline_flows.household_realized).sum())
    assert controlled <= baseline + 1e-9


def test_unknown_or_revoked_authority_is_rejected() -> None:
    from studies.HIST_VNEXT.M09 import runner

    decision = _procurement_decision()
    observation = _observation(
        issued_quarter="1957Q1",
        issued_at=decision.decision_at,
        published_at=decision.available_at,
        value=1.0,
    )
    empty = RegimeCalendar(events=())
    validation, error = runner._admit(decision, empty, observation)
    assert validation is None
    assert error is not None

    day = DateInterval(earliest=date(1957, 1, 1), latest=date(1957, 1, 1), precision="day")
    grant = InstitutionEvent(
        event_id="grant",
        permission="procurement",
        scope=AuthorityScope(
            organization_ids=("3",),
            sector_ids=("industry",),
            geographic_ids=("national",),
            excluded_sector_ids=(),
        ),
        action="grant",
        revokes_event_id=None,
        proposal_date=day,
        approval_date=day,
        enactment_date=day,
        effective_from=day,
        effective_to=None,
        observed_implementation_at=None,
        source_available_at=day,
        issuer="test",
        legal_force="enactment",
        source_ids=("synthetic:test",),
        synthetic_flag=True,
        confidence_reason="test",
    )
    revoke = grant.model_copy(
        update={
            "event_id": "revoke",
            "action": "revoke",
            "revokes_event_id": "grant",
        }
    )
    revoke = InstitutionEvent.model_validate(revoke.model_dump())
    revoked = RegimeCalendar(events=(grant, revoke))
    assert authority_at(
        revoked,
        organization_id="3",
        sector_id="industry",
        geographic_id="national",
        permission="procurement",
        decision_at=decision.decision_at,
    ).status in {"revoked", "unknown"}
    validation, error = runner._admit(decision, revoked, observation)
    assert validation is None and error is not None


def test_constant_reports_make_both_methods_the_same_effective_null() -> None:
    reports = (
        make_report("1957Q1", 5.0, published_at=date(1957, 4, 10)),
        make_report("1957Q2", 5.0, published_at=date(1957, 7, 10)),
    )
    persistence = make_issued(method="persistence", reports=reports)
    linear = make_issued(method="linear", reports=reports)
    assert persistence.prediction == linear.prediction == 5.0
    assert persistence.raw_prediction == linear.raw_prediction == 5.0
    first = score_forecast(persistence, make_realized(persistence, 5.0))
    second = score_forecast(linear, make_realized(linear, 5.0))
    assert first.residual == second.residual == 0.0
    assert first.absolute_error == second.absolute_error == 0.0


# ---------------------------------------------------------------------------
# Read-only package verification
# ---------------------------------------------------------------------------


def _update_sidecar(path: Path, mutate) -> None:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        mutate(payload["content"])
        payload["content_sha256"] = canonical_digest(payload["content"])
        rows.append(json.dumps(payload, sort_keys=True))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _refresh_manifest_sidecar(package: Path, name: str) -> None:
    path = package / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["sidecar_sha256"][name] = hashlib.sha256(
        (package / f"{name}.jsonl").read_bytes()
    ).hexdigest()
    path.write_text(canonical_json(manifest).decode("utf-8") + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def smoke_package(tmp_path_factory):
    from studies.HIST_VNEXT.M09 import runner

    root = Path(__file__).resolve().parents[1]
    output = tmp_path_factory.mktemp("m09-smoke") / "smoke"
    runner.run_experiment(
        root,
        spec_path=Path("studies/HIST_VNEXT/M09/spec.json"),
        output_dir=output,
        mode="smoke",
    )
    return output


def test_verify_accepts_the_untampered_small_package(smoke_package) -> None:
    from studies.HIST_VNEXT.M09 import runner

    result = runner._verify_package(smoke_package)
    assert result["status"] == "PASS"
    assert result["records"] == 4


def test_verify_rejects_tampered_date_unit_residual_witness_and_hash(
    smoke_package, tmp_path
) -> None:
    from studies.HIST_VNEXT.M09 import runner

    def fresh(name: str) -> Path:
        target = tmp_path / name
        target.mkdir()
        for source in smoke_package.iterdir():
            if source.is_file():
                (target / source.name).write_bytes(source.read_bytes())
        return target

    # Tampered unit: recompute the sidecar content hash and manifest hash, so
    # only the semantic forecast validation can catch it.
    unit_package = fresh("unit")
    _update_sidecar(
        unit_package / "issued.jsonl",
        lambda content: content.update({"unit": "p01_other_unit"}) or False,
    )
    _refresh_manifest_sidecar(unit_package, "issued")
    with pytest.raises(
        (runner.RunnerError, ValueError), match="invalid issued forecast"
    ):
        runner._verify_package(unit_package)

    # Tampered residual.
    residual_package = fresh("residual")
    def tamper_residual(content: dict) -> bool:
        content["residual"] += 1.0
        content["absolute_error"] = abs(content["residual"])
        return False
    _update_sidecar(residual_package / "residuals.jsonl", tamper_residual)
    _refresh_manifest_sidecar(residual_package, "residuals")
    with pytest.raises(
        (runner.RunnerError, ValueError), match="residual sidecar does not recompute"
    ):
        runner._verify_package(residual_package)

    # Tampered realization date.
    date_package = fresh("date")
    def tamper_date(content: dict) -> bool:
        content["realized_at"] = "1957-09-30"
        return False
    _update_sidecar(date_package / "realized.jsonl", tamper_date)
    _refresh_manifest_sidecar(date_package, "realized")
    with pytest.raises(
        (runner.RunnerError, ValueError), match="realization cannot precede"
    ):
        runner._verify_package(date_package)

    # Tampered witness.
    witness_package = fresh("witness")
    def tamper_witness(content: dict) -> bool:
        content["witness_sha256"] = "f" * 64
        return False
    _update_sidecar(witness_package / "realized.jsonl", tamper_witness)
    _refresh_manifest_sidecar(witness_package, "realized")
    with pytest.raises(
        (runner.RunnerError, ValueError), match="witness does not match"
    ):
        runner._verify_package(witness_package)

    # Tampered science hash.
    hash_package = fresh("hash")
    science_path = hash_package / "science.json"
    science = json.loads(science_path.read_text(encoding="utf-8"))
    science["records"][0]["prediction"] += 1.0
    science_path.write_text(canonical_json(science).decode("utf-8") + "\n", encoding="utf-8")
    with pytest.raises(
        (runner.RunnerError, ValueError), match="science digest does not match"
    ):
        runner._verify_package(hash_package)

    # Tampered publication schedule: recompute the input hash and sidecar hash
    # so only the delay/publication semantic check can catch it.
    schedule_package = fresh("schedule")
    def tamper_schedule(content: dict) -> bool:
        for report in content["reports"]:
            report["published_at"] = "1957-04-20"
        payload = [
            {
                "measurement_quarter": report["measurement_quarter"],
                "observation": {
                    "actor_role": "procurement_organization",
                    "organization_id": "ORG-ENT-A",
                    "sector_id": "industry",
                    "geographic_id": "national",
                    "quarter": content["issued_quarter"],
                    "decision_at": content["issued_at"],
                    "available_at": report["published_at"],
                    "observed_fields": {
                        "quarter": content["issued_quarter"],
                        "supply_quantity": report["value"],
                    },
                },
            }
            for report in content["reports"]
        ]
        content["input_observation_sha256"] = canonical_digest(payload)
        return False
    _update_sidecar(schedule_package / "issued.jsonl", tamper_schedule)
    _refresh_manifest_sidecar(schedule_package, "issued")
    with pytest.raises((runner.RunnerError, ValueError), match="publication date"):
        runner._verify_package(schedule_package)

    # Tampered prediction: a perfect-foresight value must not recompute.
    prediction_package = fresh("prediction")
    def tamper_prediction(content: dict) -> None:
        content["prediction"] = 1234.5
        content["raw_prediction"] = 1234.5
        content["clipping_delta"] = 0.0
    _update_sidecar(prediction_package / "issued.jsonl", tamper_prediction)
    _refresh_manifest_sidecar(prediction_package, "issued")
    with pytest.raises(
        (runner.RunnerError, ValueError), match="raw prediction does not recompute"
    ):
        runner._verify_package(prediction_package)

    # Tampered information timing: a later legal availability must not pass.
    timing_package = fresh("timing")
    def tamper_timing(content: dict) -> None:
        content["older_available_at"] = content["issued_at"]
        content["available_at"] = content["issued_at"]
    _update_sidecar(timing_package / "issued.jsonl", tamper_timing)
    _refresh_manifest_sidecar(timing_package, "issued")
    with pytest.raises(
        (runner.RunnerError, ValueError),
        match="older availability does not match the report",
    ):
        runner._verify_package(timing_package)

    # Deleted grid cell.
    deleted_package = fresh("deleted")
    lines = (deleted_package / "issued.jsonl").read_text(encoding="utf-8").splitlines()
    (deleted_package / "issued.jsonl").write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
    _refresh_manifest_sidecar(deleted_package, "issued")
    with pytest.raises(
        (runner.RunnerError, ValueError), match="realization has no issued forecast"
    ):
        runner._verify_package(deleted_package)
