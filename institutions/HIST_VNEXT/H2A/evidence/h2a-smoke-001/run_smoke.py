#!/usr/bin/env python3
"""H2A smoke script — exercises observation, decision, and validation modules.

Run from repo root:
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
    institutions/HIST_VNEXT/H2A/evidence/h2a-smoke-001/run_smoke.py
"""

from datetime import date
from pathlib import Path

from hsm_lab.institutions.decisions import (
    ActorRole,
    ProcurementChoiceKind,
    ProcurementDecision,
)
from hsm_lab.institutions.observed import (
    ObservationBuilder,
    verify_observation_invariants,
)
from hsm_lab.institutions.proposal_validation import (
    BoundedPlanning,
    evaluate_all_rules,
    validate_proposal,
)

# ---------------------------------------------------------------------------
# Load H1B calendar for authority checks
# ---------------------------------------------------------------------------

_H1B_PATH = (
    Path(__file__).parents[5]
    / "institutions"
    / "HIST_VNEXT"
    / "h1b_synthetic_calendar.json"
)


def load_h1b_calendar():
    from hsm_lab.institutions.calendar import load_calendar
    if _H1B_PATH.exists():
        return load_calendar(_H1B_PATH)
    # Minimal fallback for isolated smoke
    from hsm_lab.institutions.schemas import AuthorityScope, DateInterval, RegimeCalendar

    def di(earliest, latest, precision):
        return DateInterval(earliest=earliest, latest=latest, precision=precision)

    grant_scope = AuthorityScope(
        organization_ids=("ORG-ENT-A",),
        sector_ids=("industry",),
        excluded_sector_ids=(),
        geographic_ids=(),
    )
    grant = {
        "event_id": "smoke-grant",
        "permission": "procurement",
        "scope": grant_scope,
        "action": "grant",
        "proposal_date": di(date(1966, 5, 1), date(1966, 5, 1), "day"),
        "approval_date": di(date(1966, 6, 1), date(1966, 6, 1), "day"),
        "enactment_date": di(date(1967, 12, 1), date(1967, 12, 1), "day"),
        "effective_from": di(date(1968, 1, 1), date(1968, 1, 1), "day"),
        "effective_to": None,
        "source_available_at": di(date(1957, 1, 1), date(1957, 1, 1), "day"),
        "issuer": "smoke",
        "legal_force": "enactment",
        "source_ids": (),
        "implementation_evidence_ids": (),
        "synthetic_flag": True,
        "confidence_reason": "smoke fixture",
        "search_tags": (),
    }
    return RegimeCalendar(events=(grant,))


calendar = load_h1b_calendar()

# ---------------------------------------------------------------------------
# Smoke checks
# ---------------------------------------------------------------------------

passed: list[str] = []
failed: list[str] = []


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        passed.append(name)
        print(f"  PASS  {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL  {name}: {detail}")


# S1: Observation — prohibited key rejection + whitelist filtering
builder = ObservationBuilder("procurement_organization")
# S1a: raw_truth must raise
try:
    builder.build(
        organization_id="ORG-ENT-A",
        sector_id="industry",
        geographic_id="national",
        quarter="1968Q1",
        decision_at=date(1968, 1, 15),
        available_at=date(1968, 1, 10),
        raw_data={
            "raw_truth": 999.0,  # prohibited — must raise
        },
    )
    check("S1: raw_truth raises TypeError", False, "no exception raised")
except TypeError as exc:
    check("S1: raw_truth raises TypeError", "Prohibited key" in str(exc))

# S1b: whitelist filtering — supply_quantity retained, others dropped
obs = builder.build(
    organization_id="ORG-ENT-A",
    sector_id="industry",
    geographic_id="national",
    quarter="1968Q1",
    decision_at=date(1968, 1, 15),
    available_at=date(1968, 1, 10),
    raw_data={
        "supply_quantity": 100.0,
        "demand_quantity": 90.0,
        "administered_price": 50.0,
        "inventory_level": 30.0,
        "capacity_utilization": 0.85,
        "shortage_indicator": 0.1,
        "unrelated_field": 999.0,  # not whitelisted — silently dropped
    },
)
check("S1: whitelist includes supply_quantity",
      "supply_quantity" in {n for n, _ in obs.observed_fields})

# S2: available_at constraint
try:
    builder.build(
        organization_id="ORG-ENT-A", sector_id="industry",
        geographic_id="national", quarter="1968Q1",
        decision_at=date(1968, 1, 15),
        available_at=date(1968, 1, 20),  # future — must reject
        raw_data={"supply_quantity": 100.0},
    )
    check("S2: future available_at rejected", False, "no exception raised")
except ValueError:
    check("S2: future available_at rejected", True)

# S3: Observation is frozen
try:
    obs.observed_fields = (("supply_quantity", 200.0),)
    check("S3: observation is frozen", False, "no exception raised")
except Exception:
    check("S3: observation is frozen", True)

# S4: Observation invariants
violations = verify_observation_invariants(obs)
check("S4: clean observation passes invariants", len(violations) == 0, f"violations: {violations}")

# S5: Legal proposal
decision = ProcurementDecision(
    decision_id="smoke-d1",
    actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
    organization_id="ORG-ENT-A",
    sector_id="industry",
    quarter="1968Q2",
    decision_at=date(1968, 6, 1),
    available_at=date(1968, 5, 25),
    kind=ProcurementChoiceKind.REQUEST,
    commodity_id="coal",
    requested_quantity=50.0,
)
result = validate_proposal(decision, calendar)
check("S5: legal proposal validated", result.is_legal, result.reason)

# S6: Negative quantity rejected
bad = ProcurementDecision(
    decision_id="smoke-d2",
    actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
    organization_id="ORG-ENT-A",
    sector_id="industry",
    quarter="1968Q1",
    decision_at=date(1968, 6, 1),
    available_at=date(1968, 5, 25),
    kind=ProcurementChoiceKind.REQUEST,
    commodity_id="coal",
    requested_quantity=-10.0,  # illegal
)
is_legal, reason = bad.validate_legality()
check("S6: negative quantity rejected", not is_legal, reason)

# S7: Three rules
rule = BoundedPlanning()
passed_bp, reason_bp = rule.evaluate(decision, None)
check("S7: bounded_planning passes for legal decision", passed_bp, reason_bp)

# S8: Bounded planning rejects future info
bad2 = ProcurementDecision(
    decision_id="smoke-d3",
    actor_role=ActorRole.PROCUREMENT_ORGANIZATION,
    organization_id="ORG-ENT-A",
    sector_id="industry",
    quarter="1968Q1",
    decision_at=date(1968, 6, 1),
    available_at=date(1968, 6, 10),  # future
    kind=ProcurementChoiceKind.REQUEST,
    commodity_id="coal",
    requested_quantity=50.0,
)
passed_bp2, reason_bp2 = BoundedPlanning().evaluate(bad2, None)
check("S8: bounded_planning rejects future info", not passed_bp2, reason_bp2)

# S9: evaluate_all_rules returns three results
results = evaluate_all_rules(decision, None)
check("S9: evaluate_all_rules returns 3 results", len(results) == 3, f"got {len(results)}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print()
print(f"Results: {len(passed)} passed, {len(failed)} failed")
if failed:
    print("FAILURES:")
    for name, detail in failed:
        print(f"  {name}: {detail}")
    exit(1)
else:
    print("ALL SMOKE CHECKS PASSED")
    exit(0)
