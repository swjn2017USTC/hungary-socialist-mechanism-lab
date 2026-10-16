"""H1B §4: read-only authority queries — one entry point authority_at.

Never writes cache, never calls engine, never reads actor/forcing/target.
"""

from __future__ import annotations

from datetime import date

from hsm_lab.institutions.schemas import (
    AuthorityResult,
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
    - A grant is 'uncertain' if its enactment date is unknown (cannot be established).
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
    # Uncertain grants: enactment_date.precision == "unknown" OR
    # effective_from.precision == "unknown" OR decision within effective_from range
    definite_grants, uncertain_grants = _active_grants_at(grants, decision_at)

    all_active = definite_grants + uncertain_grants
    if not all_active:
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

    - definitely_active: grants whose authority is definitively established at decision_at
    - uncertain: grants whose enactment date or effective_from date has unknown precision;
      conservatively treated as uncertain (caller returns 'unknown' if any exist)

    A grant is definitely_active only when all conditions are met:
    - legal_force == 'enactment'
    - enactment_date is known and definitely passed (enactment_date.latest ≤ decision_at)
    - effective_from is known and definitely started (effective_from.latest ≤ decision_at)
    - decision_at is before effective_to (exclusive/inclusive upper bound)
    """
    definite = []
    uncertain = []
    for g in grants:
        if g.legal_force != "enactment":
            continue
        # Track grants with unknown enactment as uncertain — but only if they could
        # possibly be active at decision_at. If effective_from has definitely not
        # started yet (decision_at < effective_from.earliest), the grant cannot affect
        # the outcome at this date and is skipped entirely.
        if g.enactment_date.precision == "unknown":
            if (
                g.effective_from.precision != "unknown"
                and g.effective_from.earliest is not None
                and decision_at < g.effective_from.earliest
            ):
                continue  # definitely not yet active — skip
            uncertain.append(g)
            continue
        if g.enactment_date.latest is None:
            uncertain.append(g)
            continue
        if decision_at < g.enactment_date.latest:
            continue  # enacted after decision date

        # effective_from must be definitely active: effective_from.latest ≤ decision_at
        if g.effective_from.precision == "unknown":
            uncertain.append(g)
            continue
        if g.effective_from.earliest is None:
            uncertain.append(g)
            continue

        # Handle range/month/quarter/year precision: the start is uncertain but before latest.
        # If decision date is within the period → possibly active (not definitely).
        if g.effective_from.precision in ("range", "month", "quarter", "year"):
            if decision_at < g.effective_from.earliest:
                continue  # definitely not yet active
            if decision_at >= g.effective_from.latest:
                pass  # definitely started (end of range has passed)
            else:
                uncertain.append(g)  # within range → possibly active
                continue
        # For day/month/quarter/year precision:
        if g.effective_from.latest is not None and g.effective_from.latest <= decision_at:
            pass  # definitely started so far
        elif decision_at < g.effective_from.earliest:
            continue  # definitely not yet active
        else:
            uncertain.append(g)
            continue  # uncertain — decision within effective_from range

        # effective_to check: half-open [effective_from, effective_to)
        if g.effective_to is not None:
            if g.effective_to.precision == "unknown":
                uncertain.append(g)
                continue
            if g.effective_to.precision == "range":
                d_end_earliest = g.effective_to.earliest
                d_end_latest = g.effective_to.latest
                if d_end_earliest is not None and d_end_latest is not None:
                    if d_end_earliest > d_end_latest:  # inverted range
                        # Exclusive upper bound: active while decision_date < earliest
                        if decision_at < d_end_earliest:
                            pass  # definitely active
                        else:
                            continue  # expired
                    else:  # normal range
                        # Active from effective_from; expires at latest (half-open end)
                        # decision < earliest → definitely active; decision >= latest → expired
                        # decision within [earliest, latest) → possibly expired (uncertain)
                        if decision_at >= d_end_latest:
                            continue  # definitely expired
                        elif decision_at < d_end_earliest:
                            pass  # definitely active
                        else:
                            uncertain.append(g)  # within range — may have expired
                            continue
                elif d_end_latest is not None:
                    if decision_at >= d_end_latest:
                        continue  # definitely expired
                    uncertain.append(g)  # within range — may have expired
                    continue
                elif d_end_earliest is not None:
                    if decision_at >= d_end_earliest:
                        continue  # at or after exclusive end → expired
                    # else: definitely active
                # else: no bounds → always active
            else:
                # Month/quarter/year precision: the end could be anywhere in the period.
                # Within the period → uncertain (may have expired); after period → expired.
                # Decision < earliest → definitely active; earliest ≤ decision < latest → uncertain
                if g.effective_to.earliest is not None and g.effective_to.latest is not None:
                    if decision_at < g.effective_to.earliest:
                        pass  # definitely active
                    elif decision_at >= g.effective_to.latest:
                        continue  # definitely expired
                    else:
                        uncertain.append(g)  # within period → may have expired
                        continue
                elif g.effective_to.earliest is not None:
                    # Only earliest bound known (exclusive): within range → uncertain
                    if decision_at >= g.effective_to.earliest:
                        uncertain.append(g)  # within period → may have expired
                        continue
                    # else: definitely active
                elif g.effective_to.latest is not None:
                    # Only latest bound known (inclusive): within range → uncertain
                    if decision_at >= g.effective_to.latest:
                        continue  # definitely expired
                    uncertain.append(g)  # within range → may have expired
                    continue
                # else: no bounds → always active

        definite.append(g)
    return definite, uncertain


def _effective_revokes(
    revokes: list[InstitutionEvent],
    active_grants: list[InstitutionEvent],
    decision_at: date,
) -> tuple[list[InstitutionEvent], list[InstitutionEvent]]:
    """Return (definitely_effective, possibly_effective) revokes at decision_at.

    A revoke is definitely effective only when:
    1. legal_force is 'enactment'
    2. Its enactment date is known and definitely passed
    3. Its start period has definitely begun (effective_from known and passed)
    4. The decision date is before the end period

    A revoke is possibly effective when:
    - Enactment date is unknown (may never have been enacted)
    - OR effective_from is uncertain (unknown precision, or decision within range)
    - OR effective_to is uncertain (unknown precision, or decision within range)
    - OR effective_to is definite but before decision date (expired)

    Unknown enactment = possibly effective (not skipped), because we cannot confirm
    the revoke was ever legally established.
    """
    definite = []
    possible = []
    active_ids = {g.event_id for g in active_grants}
    for rev in revokes:
        if rev.revokes_event_id not in active_ids:
            continue
        if rev.legal_force != "enactment":
            continue  # proposal/approval revoke has no established legal force

        # Enactment date: check first — unknown enactment means possibly not enacted
        # (possibly effective, not definitely). Known enactment: check if passed.
        if rev.enactment_date.precision == "unknown":
            # Uncertain enactment — might never have been established.
            # BUT: check effective_to first. If definitely expired before decision date,
            # skip (expired revoke cannot be possibly effective even if enacted).
            if (
                rev.effective_to is not None
                and rev.effective_to.latest is not None
                and decision_at >= rev.effective_to.latest
            ):
                continue  # definitely expired before decision date — skip
            # Also check effective_from: if definitely in future, definitely not effective
            ef = rev.effective_from
            ef_definitely_future = (
                ef.precision != "unknown"
                and ef.earliest is not None
                and decision_at < ef.earliest
            )
            if ef_definitely_future:
                continue  # definitely not effective yet
            # Otherwise: possibly effective (enactment unknown but revoke may have started)
            possible.append(rev)
            continue
        if rev.enactment_date.latest is not None and decision_at < rev.enactment_date.latest:
            continue  # not enacted yet at decision date

        # effective_from must be checked for start of effectiveness
        if rev.effective_from.precision == "unknown":
            # Unknown start: possibly effective if enacted (and possibly expired)
            # Check effective_to: if definitely expired, not even possibly effective
            if (
                rev.effective_to is not None
                and rev.effective_to.latest is not None
                and decision_at >= rev.effective_to.latest
            ):
                continue  # definitely expired before decision date
            possible.append(rev)
            continue
        if rev.effective_from.earliest is None:
            possible.append(rev)
            continue

        # Handle range precision: the range means start is uncertain but before latest.
        # Decision within range → possibly effective (not definitely).
        # Same for month/quarter/year precision where the date could be anywhere in the period.
        if rev.effective_from.precision in ("range", "month", "quarter", "year"):
            if decision_at < rev.effective_from.earliest:
                continue  # not yet started
            if decision_at >= rev.effective_from.latest:
                pass  # definitely started (end of range has passed)
            else:
                possible.append(rev)  # within range → possibly effective
                continue

        # effective_from must be definitely active: effective_from.latest ≤ decision_at
        if rev.effective_from.latest is not None and decision_at >= rev.effective_from.latest:
            pass  # definitely started
        else:
            continue  # not yet started at decision date

        # effective_to: check if revoke has ended before decision date
        if rev.effective_to is not None:
            if rev.effective_to.precision == "unknown":
                possible.append(rev)
                continue
            if rev.effective_to.precision == "range":
                d_end_earliest = rev.effective_to.earliest
                d_end_latest = rev.effective_to.latest
                if d_end_earliest is not None and d_end_latest is not None:
                    if d_end_earliest > d_end_latest:  # inverted range
                        # Exclusive upper bound: active only while decision_date < earliest
                        if decision_at < d_end_earliest:
                            definite.append(rev)  # definitely not expired
                        continue  # at or after exclusive end → expired
                    else:  # normal range
                        # Active from earliest; expires at latest (half-open end)
                        if decision_at < d_end_earliest:
                            definite.append(rev)  # definitely not expired
                            continue
                        if decision_at >= d_end_latest:
                            continue  # definitely expired
                        possible.append(rev)  # within range → possibly expired
                        continue
                elif d_end_latest is not None:
                    if decision_at < d_end_latest:
                        definite.append(rev)  # definitely not expired
                    continue
                # else: no end bound → always active
            else:
                # Month/quarter/year precision: within period → possibly expired (uncertain)
                # Decision < earliest → definitely not expired;
                # earliest ≤ decision < latest → uncertain
                if rev.effective_to.earliest is not None and rev.effective_to.latest is not None:
                    if decision_at < rev.effective_to.earliest:
                        definite.append(rev)  # definitely not expired
                        continue
                    elif decision_at >= rev.effective_to.latest:
                        continue  # definitely expired
                    else:
                        possible.append(rev)  # within period → possibly expired
                        continue
                elif rev.effective_to.earliest is not None:
                    # Only earliest known (exclusive): within range → uncertain
                    if decision_at >= rev.effective_to.earliest:
                        possible.append(rev)  # within period → possibly expired
                        continue
                    else:
                        definite.append(rev)  # before period → definitely not expired
                        continue
                elif rev.effective_to.latest is not None:
                    # Only latest known (inclusive): within range → uncertain
                    if decision_at >= rev.effective_to.latest:
                        continue  # definitely expired
                    possible.append(rev)  # within range → possibly expired
                    continue
                # else: no end bound → always active

        definite.append(rev)
    return definite, possible





def _validate_revoke_scope(revoke: InstitutionEvent, target: InstitutionEvent) -> None:
    """Raise ConfigError if revoke scope exceeds target grant scope."""
    # Delegate to comprehensive _check_revoke_scope
    _check_revoke_scope(revoke, target)
