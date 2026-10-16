"""H1B §2: institutional event schemas — calendar, authority scope, regime calendar.

StrictModel (extra forbid, frozen) from hsm_lab.contract.base.
Uses tuple for immutable collections; None for unknown endpoints.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from hsm_lab.contract.base import ConfigError, StrictModel

# ---------------------------------------------------------------------------
# Precision ladder for DateInterval
# ---------------------------------------------------------------------------

DatePrecision = Literal["day", "month", "quarter", "year", "range", "unknown"]


class DateInterval(StrictModel):
    """A possibly-bounded temporal interval with explicit precision.

    - ``unknown``: both earliest and latest are None.
    - ``day``: earliest == latest (a single calendar day).
    - ``month``: bounds are first/last day of the same calendar month.
    - ``quarter``: bounds are first/last day of the same calendar quarter.
    - ``year``: bounds are first/last day of the same calendar year.
    - ``range``: preserves the original inclusive interval.
    """

    earliest: date | None = Field(default=None)
    latest: date | None = Field(default=None)
    precision: DatePrecision = Field(default="unknown")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _check_invariants(self) -> DateInterval:
        p = self.precision
        if p == "unknown":
            # Unknown precision means neither bound is meaningful; reject if bounds are set
            if self.earliest is not None or self.latest is not None:
                raise ValueError(
                    "DateInterval precision='unknown' requires both earliest and latest "
                    f"to be None, got earliest={self.earliest}, latest={self.latest}",
                )
            return self
        # All non-unknown precisions require both bounds
        if self.earliest is None or self.latest is None:
            raise ValueError(
                f"DateInterval precision '{p}' requires both earliest and latest, got None"
            )
        if p == "day":
            if self.earliest != self.latest:
                raise ValueError(
                    f"DateInterval precision='day' requires earliest == latest, "
                    f"got {self.earliest} != {self.latest}"
                )
            return self
        # All precisions except "unknown" require earliest <= latest
        if p != "unknown" and self.earliest is not None and self.latest is not None:
            if self.earliest > self.latest:
                raise ValueError(
                    f"DateInterval precision='{p}' requires earliest <= latest, "
                    f"got earliest={self.earliest}, latest={self.latest}"
                )
        return self

    # ---------------------------------------------------------------------------
    # Query helpers
    # ---------------------------------------------------------------------------

    def is_active_on(self, d: date) -> bool | None:
        """Return True/False/None (unknown) for whether d falls within [earliest, latest].

        Uses conservative interval logic:
        - earliest is the first possible day (inclusive)
        - latest is the last possible day (inclusive)
        - For 'day' precision, earliest == latest is required; dates not equal return None
        - For broader precision (quarter, month, etc.), a date strictly between
          earliest and latest returns None (uncertain) to avoid false certainty
          about when within the interval the event actually became effective.
        - For range precision with inverted bounds (earliest > latest), the
          effective_to is an exclusive upper bound; d < earliest means active.
        """
        if self.precision == "unknown":
            return None
        if self.earliest is not None and d < self.earliest:
            return False
        if self.latest is not None and d > self.latest:
            return False
        # Day precision requires earliest == latest; mismatched bounds mean uncertain
        if self.precision == "day":
            if (
                self.earliest is not None
                and self.latest is not None
                and self.earliest != self.latest
            ):
                return None
            return True
        # For non-day precision, dates between earliest and latest are uncertain
        if (
            self.earliest is not None
            and self.latest is not None
            and self.earliest < d < self.latest
        ):
            return None
        return True


# ---------------------------------------------------------------------------
# Authority scope — who/what is covered by one permission event
# ---------------------------------------------------------------------------

class AuthorityScope(StrictModel):
    """Scope of one InstitutionEvent: which organisations, sectors, and geographies.

    Empty tuple means wildcard (all values in that dimension).
    excluded_sector_ids are subtracted from sector_ids.
    """

    organization_ids: tuple[str, ...] = Field(default_factory=tuple)
    sector_ids: tuple[str, ...] = Field(default_factory=tuple)
    excluded_sector_ids: tuple[str, ...] = Field(default_factory=tuple)
    geographic_ids: tuple[str, ...] = Field(default_factory=tuple)

    def __init__(self, **data):
        super().__init__(**data)
        # Non-empty entries must be non-empty strings with no duplicates
        for field in ("organization_ids", "sector_ids", "excluded_sector_ids", "geographic_ids"):
            vals = getattr(self, field)
            if vals:
                if not all(isinstance(v, str) and v.strip() for v in vals):
                    raise ConfigError(f"{field} must contain non-empty strings")
                if len(set(vals)) != len(vals):
                    raise ConfigError(f"{field} contains duplicates: {vals}")

    def covers(
        self,
        organization_id: str,
        sector_id: str,
        geographic_id: str,
    ) -> bool:
        """Return True if the given concrete identifiers fall within this scope."""
        # Organization check
        if self.organization_ids and organization_id not in self.organization_ids:
            return False
        # Sector check: if sector_ids is non-empty, sector must be in it.
        # Regardless of wildcard, sector must not be in excluded_sector_ids.
        if self.sector_ids:
            if sector_id not in self.sector_ids:
                return False  # sector not in the inclusion set
        if sector_id in self.excluded_sector_ids:
            return False  # sector explicitly excluded, even for wildcard
        if self.geographic_ids and geographic_id not in self.geographic_ids:
            return False
        return True


# ---------------------------------------------------------------------------
# InstitutionEvent — one permission change record
# ---------------------------------------------------------------------------

LegalForce = Literal["proposal", "approval", "enactment", "unknown"]
EventAction = Literal["grant", "revoke"]


class InstitutionEvent(StrictModel):
    """One atomic permission event in the institutional calendar."""

    event_id: str = Field(min_length=1)
    permission: str = Field(min_length=1)
    scope: AuthorityScope
    action: EventAction
    revokes_event_id: str | None = None

    proposal_date: DateInterval
    approval_date: DateInterval
    enactment_date: DateInterval
    effective_from: DateInterval
    effective_to: DateInterval | None = None
    observed_implementation_at: DateInterval | None = None
    source_available_at: DateInterval

    issuer: str = Field(min_length=1)
    legal_force: LegalForce = "unknown"
    source_ids: tuple[str, ...] = Field(default_factory=tuple)
    implementation_evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    synthetic_flag: bool = True
    confidence_reason: str = ""
    search_tags: tuple[str, ...] = Field(default_factory=tuple)

    # ---------------------------------------------------------------------------
    # Invariants
    # ---------------------------------------------------------------------------
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _check_invariants(self) -> InstitutionEvent:
        # Action-specific invariants
        if self.action == "grant" and self.revokes_event_id is not None:
            raise ValueError(
                f"grant event {self.event_id} must not have revokes_event_id"
            )
        if self.action == "revoke":
            if not self.revokes_event_id:
                raise ValueError(f"revoke event {self.event_id} requires revokes_event_id")
            if self.revokes_event_id == self.event_id:
                raise ValueError(f"revoke event {self.event_id} cannot revoke itself")

        # Date ordering: proposal ≤ approval ≤ enactment ≤ effective_from
        # Use latest bounds when available; skip check if precision is unknown
        def _earliest(di: DateInterval) -> date | None:
            if di.precision == "unknown":
                return None
            return di.earliest

        def _latest(di: DateInterval) -> date | None:
            if di.precision == "unknown":
                return None
            return di.latest

        prop_e = _earliest(self.proposal_date)
        appr_e = _earliest(self.approval_date)
        appr_l = _latest(self.approval_date)
        enact_e = _earliest(self.enactment_date)
        enact_l = _latest(self.enactment_date)
        eff_from_l = _latest(self.effective_from)

        # Lifecycle feasibility: each adjacent pair checked independently:
        # some value in earlier_range must be ≤ some value in later_range.
        # Possible iff: earlier.earliest ≤ later.latest
        # Constraint chain: proposal ≤ approval ≤ enactment ≤ effective_from

        # proposal → approval
        if prop_e is not None and appr_l is not None and prop_e > appr_l:
            raise ValueError(
                f"event {self.event_id}: proposal_date.earliest {prop_e} > "
                f"approval_date.latest {appr_l} — impossible chronology"
            )
        # proposal → effective_from
        if prop_e is not None and eff_from_l is not None and prop_e > eff_from_l:
            raise ValueError(
                f"event {self.event_id}: proposal_date.earliest {prop_e} > "
                f"effective_from.latest {eff_from_l} — impossible chronology"
            )
        # approval → enactment (only if enacted)
        if appr_e is not None and enact_l is not None and appr_e > enact_l:
            raise ValueError(
                f"event {self.event_id}: approval_date.earliest {appr_e} > "
                f"enactment_date.latest {enact_l} — impossible chronology"
            )
        # approval → effective_from (always)
        if appr_e is not None and eff_from_l is not None and appr_e > eff_from_l:
            raise ValueError(
                f"event {self.event_id}: approval_date.earliest {appr_e} > "
                f"effective_from.latest {eff_from_l} — impossible chronology"
            )
        # enactment → effective_from (always)
        if enact_e is not None and eff_from_l is not None and enact_e > eff_from_l:
            raise ValueError(
                f"event {self.event_id}: enactment_date.earliest {enact_e} > "
                f"effective_from.latest {eff_from_l} — impossible chronology"
            )

        # effective_to must be strictly after effective_from's range begins.
        # For exclusive bounds: effective_from.latest < effective_to.earliest
        # For inclusive bounds: effective_from.latest <= effective_to.latest
        # A valid window requires at least one feasible (start, end) pair.
        if self.effective_to is not None and self.effective_to.precision != "unknown":
            from_latest = _latest(self.effective_from)
            if self.effective_to.precision == "day":
                # Inclusive upper bound: window valid if effective_from.latest <= effective_to
                to_eff = _latest(self.effective_to)
                if (
                    to_eff is not None
                    and from_latest is not None
                    and to_eff < from_latest
                ):
                    raise ValueError(
                        f"event {self.event_id}: effective_to {to_eff} (inclusive) must be "
                        f">= effective_from latest {from_latest}"
                    )
            else:
                # Exclusive upper bound: window valid if effective_from.latest < to.earliest
                to_eff_e = _earliest(self.effective_to)
                if (
                    to_eff_e is not None
                    and from_latest is not None
                    and to_eff_e <= from_latest
                ):
                    raise ValueError(
                        f"event {self.event_id}: effective_to {to_eff_e} (exclusive) must be "
                        f"after effective_from latest {from_latest}"
                    )

        return self

    # ---------------------------------------------------------------------------
    # Legal-effectiveness query
    # ---------------------------------------------------------------------------

    def is_granted_at(self, d: date) -> bool | None:
        """Return True only when legal_force == 'enactment' and effective window is active."""
        if self.legal_force != "enactment":
            return None
        if self.effective_from.is_active_on(d) is False:
            return False
        active_from = self.effective_from.is_active_on(d)
        if active_from is None:
            return None
        if self.effective_to is not None:
            to_active = self.effective_to.is_active_on(d)
            if to_active is False:
                return False
            if to_active is None:
                return None
        return True


def _check_revoke_scope(revoke: InstitutionEvent, target: InstitutionEvent) -> None:
    """Raise ConfigError if revoke scope exceeds target grant scope.

    Checks all three scope dimensions: organization, sector (including exclusions),
    and geography. Wildcard in grant means no restriction; revoke cannot expand
    the grant's effective coverage.
    """
    gs = target.scope  # grant scope
    rs = revoke.scope  # revoke scope

    # Organization containment:
    # - Grant with specific orgs: revoke's orgs must be subset of grant's
    # - Grant is wildcard: revoke must also have specific orgs (can't expand to all)
    if gs.organization_ids:
        if not rs.organization_ids:
            raise ConfigError(
                f"revoke {revoke.event_id} has no organization restriction (wildcard) "
                f"but grant {target.event_id} is restricted to {gs.organization_ids}"
            )
        if not set(rs.organization_ids).issubset(set(gs.organization_ids)):
            raise ConfigError(
                f"revoke {revoke.event_id} organization scope {rs.organization_ids} "
                f"exceeds grant {target.event_id} scope {gs.organization_ids}"
            )

    # Sector containment: revoke effective sectors must be within grant effective sectors.
    # Effective set = sector_ids minus excluded_sector_ids.
    # Empty sector_ids = universal set (wildcard), NOT empty set.
    # Containment: revoke_effective ⊆ grant_effective.

    # Compute effective sets
    # grant_eff=None means unrestricted wildcard (universal set)
    # grant_eff=set(...) means specific sectors
    # grant_eff="wildcard_minus_exclusions" means universal minus exclusions
    grant_eff: str | set | None
    if gs.sector_ids:
        grant_eff = set(gs.sector_ids) - set(gs.excluded_sector_ids)
    elif gs.excluded_sector_ids:
        grant_eff = "wildcard_minus_exclusions"  # universal minus exclusions
    else:
        grant_eff = None  # unrestricted wildcard

    revoke_eff: str | set | None
    if rs.sector_ids:
        revoke_eff = set(rs.sector_ids) - set(rs.excluded_sector_ids)
    elif rs.excluded_sector_ids:
        revoke_eff = "wildcard_minus_exclusions"
    else:
        revoke_eff = None  # unrestricted wildcard

    if grant_eff is None:
        # Grant: unrestricted wildcard (all sectors)
        if revoke_eff is None:
            pass  # both unrestricted → OK
        elif revoke_eff == "wildcard_minus_exclusions":
            # Revoke has exclusions: scope is narrowed (all minus some)
            # This is narrowing from unrestricted → OK
            pass
        elif rs.sector_ids:
            # Revoke: specific sectors → narrowing → OK
            # But reject if grant has exclusions AND revoke targets only excluded sectors
            if gs.excluded_sector_ids and set(rs.sector_ids).issubset(set(gs.excluded_sector_ids)):
                raise ConfigError(
                    f"revoke {revoke.event_id} targets only excluded sectors "
                    f"{rs.sector_ids} of wildcard grant {target.event_id} "
                    f"(excluded: {gs.excluded_sector_ids})"
                )
    elif grant_eff == "wildcard_minus_exclusions":
        # Grant: wildcard minus exclusions = all sectors except some
        if revoke_eff is None:
            # Revoke: unrestricted wildcard → expands scope (covers excluded sectors) → REJECT
            raise ConfigError(
                f"revoke {revoke.event_id} has no sector restriction (wildcard) "
                f"but grant {target.event_id} excludes {gs.excluded_sector_ids}"
            )
        elif revoke_eff == "wildcard_minus_exclusions":
            # Both have exclusions: revoke exclusions must be superset of grant exclusions
            if not set(rs.excluded_sector_ids).issuperset(set(gs.excluded_sector_ids)):
                raise ConfigError(
                    f"revoke {revoke.event_id} sector exclusions {rs.excluded_sector_ids} "
                    f"are narrower than grant exclusions {gs.excluded_sector_ids}"
                )
        else:
            # Revoke: specific sectors → must be ⊆ grant effective
            if not revoke_eff.issubset(
                set(gs.sector_ids) - set(gs.excluded_sector_ids)
            ):
                raise ConfigError(
                    f"revoke {revoke.event_id} effective sector scope {revoke_eff} "
                    f"exceeds grant {target.event_id} effective scope "
                    f"{set(gs.sector_ids) - set(gs.excluded_sector_ids)}"
                )
    else:
        # Grant: specific sectors
        if revoke_eff is None:
            # Revoke: unrestricted wildcard → expands scope → REJECT
            raise ConfigError(
                f"revoke {revoke.event_id} has no sector restriction (wildcard) "
                f"but grant {target.event_id} is restricted to {gs.sector_ids}"
            )
        elif revoke_eff == "wildcard_minus_exclusions":
            # Revoke: wildcard-with-exclusions → expands scope → REJECT
            raise ConfigError(
                f"revoke {revoke.event_id} has sector exclusions {rs.excluded_sector_ids} "
                f"but grant {target.event_id} is restricted to {gs.sector_ids}"
            )
        else:
            # Both specific: revoke effective ⊆ grant effective
            if not revoke_eff.issubset(grant_eff):
                raise ConfigError(
                    f"revoke {revoke.event_id} effective sector scope {revoke_eff} "
                    f"exceeds grant {target.event_id} effective scope {grant_eff}"
                )

    # Geography containment: same pattern as organization
    if gs.geographic_ids:
        if not rs.geographic_ids:
            raise ConfigError(
                f"revoke {revoke.event_id} has no geographic restriction (wildcard) "
                f"but grant {target.event_id} is restricted to {gs.geographic_ids}"
            )
        if not set(rs.geographic_ids).issubset(set(gs.geographic_ids)):
            raise ConfigError(
                f"revoke {revoke.event_id} geographic scope {rs.geographic_ids} "
                f"exceeds grant {target.event_id} scope {gs.geographic_ids}"
            )


# ---------------------------------------------------------------------------
# RegimeCalendar — top-level container
# ---------------------------------------------------------------------------

class RegimeCalendar(StrictModel):
    """Read-only institutional calendar containing all institution events."""

    events: tuple[InstitutionEvent, ...] = Field(default_factory=tuple)

    model_config = ConfigDict(extra="forbid")

    def __init__(self, **data):
        super().__init__(**data)
        # Reject empty calendar
        if not self.events:
            raise ConfigError("RegimeCalendar must have at least one event")
        # Reject non-synthetic events if no historical source is present
        for ev in self.events:
            if not ev.synthetic_flag:
                raise ConfigError(
                    f"Event {ev.event_id} has synthetic_flag=False — "
                    "historical sources not admitted for this phase"
                )
            # Check implementation_evidence_ids for synthetic known-true events
            # A known-true synthetic event must have evidence backing it up
            if ev.synthetic_flag and ev.implementation_evidence_ids is not None:
                # If known_true_for is set, the event is "known true" and needs evidence
                if getattr(ev, 'known_true_for', None) and not ev.implementation_evidence_ids:
                    raise ConfigError(
                        f"Event {ev.event_id} is known-true but has no implementation_evidence_ids"
                    )
            # Check precision alignment: natural periods must align with period boundaries
            for field_name in ("effective_from", "effective_to"):
                di = getattr(ev, field_name, None)
                if di is None:
                    continue
                if di.precision in ("month", "quarter", "year"):
                    # Must align to first day of period (month=01, quarter=Q1=01, year=01)
                    if di.earliest is not None:
                        if di.precision == "month" and di.earliest.day != 1:
                            raise ConfigError(
                                f"Event {ev.event_id} {field_name} precision={di.precision} "
                                f"but earliest={di.earliest} is not on month boundary"
                            )
                        if di.precision == "quarter":
                            m = di.earliest.month
                            if m not in (1, 4, 7, 10) or di.earliest.day != 1:
                                raise ConfigError(
                                    f"Event {ev.event_id} {field_name} precision=quarter "
                                    f"but earliest={di.earliest} is not on quarter boundary"
                                )
                        if di.precision == "year" and di.earliest.day != 1:
                            raise ConfigError(
                                f"Event {ev.event_id} {field_name} precision=year "
                                f"but earliest={di.earliest} is not on year boundary"
                            )
        # No duplicate eventids
        ids = [ev.event_id for ev in self.events]
        if len(set(ids)) != len(ids):
            raise ConfigError(f"Duplicate event_id in calendar: {ids}")

        # Calendar-level revocation integrity: validate well-formed revoke targets
        # Plan §4: nonexistent targets → silently ignored at query time (unknown result)
        # Here we validate that IF the target exists, it is a grant with matching permission
        # and proper scope containment
        all_events = {ev.event_id: ev for ev in self.events}
        for ev in self.events:
            if ev.action == "revoke":
                target_id = ev.revokes_event_id
                if target_id is None:
                    raise ConfigError(
                        f"revoke event {ev.event_id} has no revokes_event_id"
                    )
                if target_id not in all_events:
                    continue  # plan §4: nonexistent targets → unknown at query time
                target = all_events[target_id]
                if target.action != "grant":
                    raise ConfigError(
                        f"revoke event {ev.event_id} targets non-grant event '{target_id}' "
                        f"(action='{target.action}')"
                    )
                # Permission must match
                if target.permission != ev.permission:
                    raise ConfigError(
                        f"revoke {ev.event_id} permission '{ev.permission}' != "
                        f"target grant {target_id} permission '{target.permission}'"
                    )
                # Revoke scope must be contained within grant scope
                _check_revoke_scope(ev, target)

    def event_by_id(self, event_id: str) -> InstitutionEvent | None:
        return next((e for e in self.events if e.event_id == event_id), None)


# ---------------------------------------------------------------------------
# AuthorityResult — read-only permission裁决
# ---------------------------------------------------------------------------

class AuthorityResult(StrictModel):
    """Result of a read-only authority query."""

    status: Literal["granted", "revoked", "unknown"]
    permission: str
    active_event_ids: tuple[str, ...] = Field(default_factory=tuple)
    reason: str = ""

    model_config = ConfigDict(extra="forbid")
