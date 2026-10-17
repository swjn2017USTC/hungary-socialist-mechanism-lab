"""H1B §4: read-only authority queries — one entry point authority_at.

Never writes cache, never calls engine, never reads actor/forcing/target.
"""

from __future__ import annotations

from datetime import date

from hsm_lab.institutions.schemas import (
    AuthorityResult,
    DateInterval,
    InstitutionEvent,
    RegimeCalendar,
    _check_revoke_scope,
)

# ---------------------------------------------------------------------------
# Public query entry point
# ---------------------------------------------------------------------------

def authority_at(
    calendar: RegimeCalendar,
    *,
    organization_id: str,
    sector_id: str,
    geographic_id: str,
    permission: str,
    decision_at: date,
) -> AuthorityResult:
    """Read-only authority query for (org, sector, geo, permission) on a given date.

    This is the only public query entry point. All filtering, revocation
    chains, and legal-effectiveness checks are internal.
    """
    # Phase 1 — filter to events whose source was already available
    available = _available_events(calendar, decision_at)

    # Phase 2 — filter to matching permission and scope
    matching = _matching_events(available, organization_id, sector_id, geographic_id, permission)

    # Phase 3 — resolve grants and revokes
    return _resolve_authority(matching, permission, decision_at)


# ---------------------------------------------------------------------------
# Phase 1: source availability
# ---------------------------------------------------------------------------

def _available_events(calendar: RegimeCalendar, decision_at: date) -> list[InstitutionEvent]:
    """Return events whose source was available (latest ≤ decision_at)."""
    result = []
    for ev in calendar.events:
        sav = ev.source_available_at
        if sav.precision == "unknown":
            continue  # unknown availability cannot be used
        if sav.latest is not None and sav.latest <= decision_at:
            result.append(ev)
    return result


# ---------------------------------------------------------------------------
# Phase 2: permission + scope matching
# ---------------------------------------------------------------------------

def _matching_events(
    events: list[InstitutionEvent],
    organization_id: str,
    sector_id: str,
    geographic_id: str,
    permission: str,
) -> list[InstitutionEvent]:
    """Return events that match the given permission and cover the concrete identifiers."""
    return [
        ev for ev in events
        if ev.permission == permission
        and ev.scope.covers(organization_id, sector_id, geographic_id)
    ]


# ---------------------------------------------------------------------------
# Temporal boundary classification
# ---------------------------------------------------------------------------

# Start boundaries (enactment_date, effective_from):
#   "definitely_future"  — the boundary cannot have occurred by decision_at
#   "definitely_elapsed" — the boundary has certainly occurred
#   "uncertain"          — the boundary may or may not have occurred
#
# End boundaries (effective_to, half-open [from, to)):
#   "no_end"             — no declared end
#   "definitely_expired" — decision_at is on/after the last possible end
#   "definitely_active"  — decision_at is before the first possible end
#   "uncertain"          — the end may already have passed

_START_FUTURE = "definitely_future"
_START_ELAPSED = "definitely_elapsed"
_START_UNCERTAIN = "uncertain"

_END_NONE = "no_end"
_END_EXPIRED = "definitely_expired"
_END_ACTIVE = "definitely_active"
_END_UNCERTAIN = "uncertain"


def _start_status(interval: DateInterval, decision_at: date) -> str:
    """Classify whether a start boundary has definitely elapsed by decision_at."""
    if interval.precision == "unknown":
        return _START_UNCERTAIN
    if interval.earliest is not None and decision_at < interval.earliest:
        return _START_FUTURE
    if interval.latest is not None and decision_at >= interval.latest:
        return _START_ELAPSED
    return _START_UNCERTAIN


def _end_status(interval: DateInterval | None, decision_at: date) -> str:
    """Classify whether an exclusive end boundary has definitely expired."""
    if interval is None:
        return _END_NONE
    if interval.precision == "unknown":
        return _END_UNCERTAIN
    if interval.latest is not None and decision_at >= interval.latest:
        return _END_EXPIRED
    if interval.earliest is not None and decision_at < interval.earliest:
        return _END_ACTIVE
    return _END_UNCERTAIN


# ---------------------------------------------------------------------------
# Phase 3: resolve grants / revokes
# ---------------------------------------------------------------------------

def _resolve_authority(
    events: list[InstitutionEvent],
    permission: str,
    decision_at: date,
) -> AuthorityResult:
    """Compute granted / revoked / unknown for a set of permission-matching events.

    Per-grant revocation tracking with full uncertainty propagation:
    - A grant is 'definitely_active' if all its temporal conditions are definitely met.
    - A grant is 'uncertain' if its enactment date or effective dates leave open
      whether it is active (but it is not definitely inactive).
    - A grant is 'definitely_revoked' if targeted by a definitely-effective revoke.
    - A grant is 'possibly_revoked' if targeted by a possibly-effective revoke.

    Overall status:
    - granted: at least one grant is definitely_active, no grant is definitely revoked,
      AND no grant is possibly revoked
    - revoked: all definitely-active grants are definitely revoked, no uncertain grants
    - unknown: any grant is uncertain, OR no grant is definitely revoked but some
      are possibly revoked, OR some grants are uncertain and others definitely revoked
    """
    # Separate grants and revokes
    grants = [ev for ev in events if ev.action == "grant"]
    revokes = [ev for ev in events if ev.action == "revoke"]

    # Validate revocation targets and scope constraints
    for rev in revokes:
        target_ev = next((e for e in grants if e.event_id == rev.revokes_event_id), None)
        if target_ev is not None:
            _validate_revoke_scope(rev, target_ev)

    # Separate definitely-active and uncertain grants
    definite_grants, uncertain_grants = _active_grants_at(grants, decision_at)

    all_active = definite_grants + uncertain_grants
    if not all_active:
        # No grant is temporally active, but a definitely applicable revoke
        # of an expired grant still establishes revocation.  Evaluate revoke
        # evidence against every declared grant before falling back to
        # "unknown".
        definite_revokes_all, possible_revokes_all = _effective_revokes(
            revokes, grants, decision_at
        )
        if definite_revokes_all:
            return AuthorityResult(
                status="revoked",
                permission=permission,
                active_event_ids=tuple(
                    sorted(rev.event_id for rev in definite_revokes_all)
                ),
                reason=(
                    f"no active grant at {decision_at}, but a definitely "
                    "applicable revocation targets a declared grant"
                ),
            )
        if possible_revokes_all:
            return AuthorityResult(
                status="unknown",
                permission=permission,
                active_event_ids=tuple(
                    sorted(rev.event_id for rev in possible_revokes_all)
                ),
                reason=(
                    f"no active grant at {decision_at}, but a possibly "
                    "applicable revocation targets a declared grant"
                ),
            )
        return AuthorityResult(
            status="unknown",
            permission=permission,
            active_event_ids=(),
            reason=f"no active grant at {decision_at}",
        )

    # Find definitely-effective and possibly-effective revokes
    definite_revokes, possible_revokes = _effective_revokes(
        revokes, all_active, decision_at
    )

    # Per-grant revocation tracking
    definitely_revoked_ids: set[str] = set()
    possibly_revoked_ids: set[str] = set()

    for g in definite_grants:
        if any(r.revokes_event_id == g.event_id for r in definite_revokes):
            definitely_revoked_ids.add(g.event_id)
        elif any(r.revokes_event_id == g.event_id for r in possible_revokes):
            possibly_revoked_ids.add(g.event_id)

    # Uncertain grants with definite revokes are reclassified as definitely revoked.
    # The definite revoke eliminates the uncertainty about the grant's authorization.
    # Uncertain grants with only possible/uncertain revokes remain uncertain.
    # Uncertain grants with no targeting revokes remain uncertain.
    reclassified_as_revoked = set()
    remaining_uncertain = []
    for g in uncertain_grants:
        if any(r.revokes_event_id == g.event_id for r in definite_revokes):
            reclassified_as_revoked.add(g.event_id)
        else:
            remaining_uncertain.append(g)
    uncertain_grants = remaining_uncertain

    # Surviving grants: definitely-active and not targeted by any revoke
    surviving = [
        g for g in definite_grants
        if g.event_id not in definitely_revoked_ids and g.event_id not in possibly_revoked_ids
    ]

    # A definitely surviving independent grant establishes permission regardless
    # of uncertainty affecting other grants (per plan §4: per-target contract).
    if surviving:
        active_ids = tuple(sorted(g.event_id for g in surviving))
        return AuthorityResult(
            status="granted",
            permission=permission,
            active_event_ids=active_ids,
            reason=f"{len(active_ids)} surviving grant(s) at {decision_at}",
        )
    # No definitely surviving grants — check for uncertainty or definite revocation
    total_revoked = len(definitely_revoked_ids) + len(reclassified_as_revoked)
    if uncertain_grants or possibly_revoked_ids:
        # Uncertainty (uncertain grants or possibly-revoked definite grants) → unknown
        return AuthorityResult(
            status="unknown",
            permission=permission,
            active_event_ids=(),
            reason=(
                f"{len(uncertain_grants)} uncertain, "
                f"{len(possibly_revoked_ids)} possibly revoked, "
                f"{total_revoked} definitely revoked at {decision_at}"
            ),
        )
    # All grants definitely revoked with no uncertainty
    return AuthorityResult(
        status="revoked",
        permission=permission,
        active_event_ids=(),
        reason=(
            f"{total_revoked} grant(s) definitely revoked at {decision_at}"
        ),
    )


def _active_grants_at(
    grants: list[InstitutionEvent],
    decision_at: date,
) -> tuple[list[InstitutionEvent], list[InstitutionEvent]]:
    """Return (definitely_active, uncertain) grants at decision_at.

    Definite nonactivity is applied before residual uncertainty:
    - effective_to definitely expired → inactive (even if enactment/start unknown)
    - effective_from definitely in the future → inactive
    - enactment definitely in the future → inactive

    A grant is definitely_active only when its enactment and effective_from
    boundaries have definitely elapsed and its half-open effective_to has not
    expired. Any residual uncertainty makes it uncertain; it is never treated
    as definitely active by default.
    """
    definite = []
    uncertain = []
    for g in grants:
        if g.legal_force != "enactment":
            continue

        enactment = _start_status(g.enactment_date, decision_at)
        effective_from = _start_status(g.effective_from, decision_at)
        effective_to = _end_status(g.effective_to, decision_at)

        # Definite nonactivity constraints hold regardless of any other
        # uncertainty, so they take precedence over uncertainty classification.
        if effective_to == _END_EXPIRED:
            continue
        if effective_from == _START_FUTURE:
            continue
        if enactment == _START_FUTURE:
            continue

        if (
            enactment == _START_ELAPSED
            and effective_from == _START_ELAPSED
            and effective_to in (_END_NONE, _END_ACTIVE)
        ):
            definite.append(g)
        else:
            uncertain.append(g)
    return definite, uncertain


def _effective_revokes(
    revokes: list[InstitutionEvent],
    active_grants: list[InstitutionEvent],
    decision_at: date,
) -> tuple[list[InstitutionEvent], list[InstitutionEvent]]:
    """Return (definitely_effective, possibly_effective) revokes at decision_at.

    A revoke is definitely effective only when:
    1. legal_force is 'enactment'
    2. Its enactment and effective_from boundaries have definitely elapsed
    3. Its effective_to has definitely not expired (or is absent)

    A revoke is possibly effective when it is not definitely inactive but one
    of those conditions remains uncertain (unknown/overlapping enactment,
    unknown/overlapping start, unknown/overlapping end). Definite nonactivity —
    enactment or start definitely in the future, or end definitely expired —
    removes the revoke entirely.
    """
    definite = []
    possible = []
    active_ids = {g.event_id for g in active_grants}
    for rev in revokes:
        if rev.revokes_event_id not in active_ids:
            continue
        if rev.legal_force != "enactment":
            continue  # proposal/approval revoke has no established legal force

        enactment = _start_status(rev.enactment_date, decision_at)
        effective_from = _start_status(rev.effective_from, decision_at)
        effective_to = _end_status(rev.effective_to, decision_at)

        # Definite nonactivity constraints take precedence over uncertainty.
        if effective_to == _END_EXPIRED:
            continue
        if effective_from == _START_FUTURE:
            continue
        if enactment == _START_FUTURE:
            continue

        if (
            enactment == _START_ELAPSED
            and effective_from == _START_ELAPSED
            and effective_to in (_END_NONE, _END_ACTIVE)
        ):
            definite.append(rev)
        else:
            possible.append(rev)
    return definite, possible


def _validate_revoke_scope(revoke: InstitutionEvent, target: InstitutionEvent) -> None:
    """Raise ConfigError if revoke scope exceeds target grant scope."""
    # Delegate to comprehensive _check_revoke_scope
    _check_revoke_scope(revoke, target)
