"""
H1A — source admission, shared-observation detection, and 1957 anchor crosswalk validation.

Offline evaluation only: no PDF reading, no OCR traversal, no remote uploads.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def evaluate_source(record: dict, *, approved_excerpts: list[dict]) -> dict:
    """
    Evaluate a single source record for admission status.

    Returns
    -------
    dict with keys:
        status : "candidate" | "admitted" | "blocked"
        reasons : list[str]   # field-level evidence gaps
    """
    reasons: list[str] = []
    source_type = record.get("source_type", "")

    # ── forcing/actor purpose always blocked (H1A §4) ──
    purpose = record.get("purpose", "")
    if purpose in ("forcing", "actor"):
        reasons.append(f"purpose={purpose!r}: historical target as forcing/actor not admitted")
        return {"status": "blocked", "reasons": reasons}

    # ── secondary_analysis: always candidate (contextual, not primary evidence) ──
    if source_type == "secondary_analysis":
        reasons.append("secondary_analysis: contextual only, not a primary institutional source")
        return {"status": "candidate", "reasons": reasons}

    # ── primary_institutional / primary_observation: check all required fields ──
    if source_type in ("primary_institutional", "primary_observation"):
        # Required for institutional documents (plan §3)
        required_fields = {
            "document_number": record.get("document_number"),
            "archival_reference": record.get("archival_reference"),
            "rights": _evaluate_rights(record.get("rights")),
        }
        # Additional required (plan §3): hash, page range, period/availability
        required_additional = {
            "source_sha256": record.get("source_sha256"),
            "pdf_page_range": record.get("pdf_page_range"),
        }
        period_or_avail = (
            record.get("statistical_period") or record.get("source_available_at")
        )

        for field, value in required_fields.items():
            if value is None:
                reasons.append(f"missing: {field}")
            elif value == {}:
                # Unknown rights → candidate (insufficient evidence to admit,
                # but not confirmed absent)
                reasons.append(f"unknown rights: {field}")
                return {"status": "candidate", "reasons": reasons}

        for field, value in required_additional.items():
            if not value:
                reasons.append(f"missing: {field}")

        if not period_or_avail:
            reasons.append("missing: statistical_period or source_available_at")

        # Must have at least one approved excerpt with valid hash + approval metadata
        if not approved_excerpts:
            reasons.append("no approved excerpts")
        else:
            for ex in approved_excerpts:
                if not _validate_excerpt(ex):
                    reasons.append(f"invalid excerpt: {ex.get('excerpt_id', 'unknown')}")
                # Excerpt source_id must match the parent record
                if ex.get("source_id") != record.get("source_id"):
                    reasons.append(
                        f"excerpt source_id mismatch: expected {record.get('source_id')!r}, "
                        f"got {ex.get('source_id')!r}"
                    )

        if reasons:
            return {"status": "blocked", "reasons": reasons}

        # All gates passed
        return {"status": "admitted", "reasons": []}

    # ── catalogue: treated as candidate only ──
    if source_type == "catalogue":
        reasons.append("catalogue: metadata reference only")
        return {"status": "candidate", "reasons": reasons}

    # ── unknown type: blocked ──
    reasons.append(f"unknown source_type: {source_type!r}")
    return {"status": "blocked", "reasons": reasons}


def find_shared_observations(records: list[dict]) -> list[dict]:
    """
    Detect shared/cited observations across records.

    Two records under the same work_id sharing a root observation are NOT independent.
    A cited observation ID that does not appear in any record's observation_ids is
    treated as an unknown root → independent = None.

    Returns one result dict per record pair evaluated.
    """
    if len(records) < 2:
        return []

    # Build global index: known root observation IDs
    known_root_ids: set[str] = set()
    for rec in records:
        known_root_ids.update(rec.get("observation_ids", []))

    results: list[dict] = []

    for i, rec in enumerate(records):
        other_recs = records[i + 1 :]
        cited_ids = set(rec.get("cited_observation_ids", []))
        obs_ids = set(rec.get("observation_ids", []))
        work_id = rec.get("work_id")

        for other in other_recs:
            other_work = other.get("work_id")
            other_cited = set(other.get("cited_observation_ids", []))
            other_obs = set(other.get("observation_ids", []))

            # Find shared observations (root observations cited by both)
            shared = cited_ids & other_obs
            shared |= other_cited & obs_ids
            shared |= cited_ids & other_cited

            # Compute unknown cited IDs once, before branching
            all_cited = cited_ids | other_cited
            unknown_cited = all_cited - known_root_ids

            if not shared:
                # No shared observations: check if any cited ID is an unknown root
                if unknown_cited or not known_root_ids:
                    # Plan §3: cited root unknown → independent = None
                    independent = None
                else:
                    independent = True
            else:
                # Shared observations detected
                # Plan §3: different works sharing a root → independent = false
                # Plan §5: 两篇论文共引同一原始观测而伪算独立 → false
                # But if the shared observation is unknown, don't assert false
                if shared & unknown_cited:
                    independent = None
                else:
                    independent = False

            results.append(
                {
                    "record_ids": [rec.get("source_id"), other.get("source_id")],
                    "work_ids": [work_id, other_work],
                    "shared_work_ids": [work_id, other_work] if work_id == other_work else [],
                    "shared_observation_ids": sorted(shared),
                    "independent": independent,
                }
            )

    return results


def validate_anchor_crosswalk(
    records: list[dict], *, legacy_artifact_ids: set[str] | None = None
) -> None:
    """
    Validate a 1957 anchor crosswalk.

    Raises ValueError on:
    - duplicate anchor_id
    - missing anchor_id
    - national anchor marked as a regional scope
    - missing classification
    - 1960 proxy classified as 1957 direct
    - missing per-row runtime_connected field (R2 fix)
    - missing per-row path field (R2 fix)
    """
    seen_ids: dict[str, int] = {}
    for idx, rec in enumerate(records):
        anchor_id = rec.get("anchor_id")
        if anchor_id is None:
            raise ValueError(
                f"Record at index {idx} is missing anchor_id; "
                "every anchor must have a unique anchor_id"
            )
        if anchor_id in seen_ids:
            raise ValueError(
                f"Duplicate anchor_id: {anchor_id!r} (first seen at index {seen_ids[anchor_id]}, "
                f"again at index {idx})"
            )
        seen_ids[anchor_id] = idx

    # Check classification requirements and per-row fields
    for idx, rec in enumerate(records):
        classification = rec.get("classification")
        if classification is None:
            raise ValueError(
                f"anchor_id {rec.get('anchor_id')!r} at index {idx} has no classification; "
                "every anchor must have one of: direct, reconstructed, proxy, synthetic, blocked"
            )

        # R2: per-row path must be present
        if not rec.get("path"):
            raise ValueError(
                f"anchor_id {rec.get('anchor_id')!r} at index {idx} is missing path; "
                "per-row path must be preserved per plan §5"
            )

        # R2: per-row runtime_connected must be present
        if "runtime_connected" not in rec:
            raise ValueError(
                f"anchor_id {rec.get('anchor_id')!r} at index {idx} is missing "
                "runtime_connected field; per-row field must be present per plan §5"
            )

        # 1960 proxy cannot be declared as 1957 direct
        legacy_initial = rec.get("legacy_initial_at", "")
        source_kind = rec.get("source_evidence_kind", "")
        if (
            legacy_initial == "1960-01-01"
            and source_kind == "proxy"
            and classification == "direct"
        ):
            raise ValueError(
                f"anchor_id {rec.get('anchor_id')!r}: legacy_initial_at=1960-01-01 "
                f"with source_evidence_kind=proxy cannot be classified as direct for 1957 target"
            )

        # National scope must be the 00 entry (orszagos)
        anchor_id = rec.get("anchor_id", "")
        geographic = rec.get("geographic_scope", "")
        # Parse anchor_id pattern: <type>_<year>_orszagos_<NN>
        parts = anchor_id.split("_")
        if len(parts) >= 4:
            suffix = parts[-1]  # "00" or "01".."20"
            is_national = suffix == "00"
            if is_national and geographic != "national":
                raise ValueError(
                    f"anchor_id {anchor_id!r} is the national (00) entry but "
                    f"geographic_scope={geographic!r}; must be 'national'"
                )
            if not is_national and geographic == "national":
                raise ValueError(
                    f"anchor_id {anchor_id!r} is a regional entry (suffix {suffix!r}) "
                    "but geographic_scope='national'; regional entries must not be national"
                )


def audit_h1a(root: Path) -> dict:
    """
    Run the full H1A audit on the repository at *root*.

    Reads only the whitelisted JSON manifests (batch01_candidates.json,
    authority_coverage.json, events.json, access_register.json,
    review_requests.json, anchor_crosswalk.json) plus DATA_MANIFEST_v1.json.

    Returns a dict with:
        exit_code : int   # 0 = all gates pass, 1 = blocked, 2 = structural error
        structural : "PASS" | "BLOCKED"
        historical : "BLOCKED" | "PASS" | "UNIDENTIFIED"
        summary : dict with counts
        details : list[str]
    """


    details: list[str] = []
    root = Path(root)

    # ── Locate artifacts ──
    candidates_path = root / "history/HIST_VNEXT/sources/batch01_candidates.json"
    authority_path = root / "history/HIST_VNEXT/sources/authority_coverage.json"
    events_path = root / "history/HIST_VNEXT/event_candidates/events.json"
    access_path = root / "history/HIST_VNEXT/exposure/access_register.json"
    review_req_path = root / "history/HIST_VNEXT/exposure/review_requests.json"
    crosswalk_path = root / "config/initial_state/hist_vnext_v1/anchor_crosswalk.json"
    manifest_path = root / "data/manifests/DATA_MANIFEST_v1.json"

    # ── Structural validation: all required files must exist ──
    missing_files: list[str] = []
    for path, label in [
        (candidates_path, "batch01_candidates.json"),
        (authority_path, "authority_coverage.json"),
        (events_path, "events.json"),
        (access_path, "access_register.json"),
        (review_req_path, "review_requests.json"),
        (crosswalk_path, "anchor_crosswalk.json"),
        (manifest_path, "DATA_MANIFEST_v1.json"),
    ]:
        if not path.exists():
            missing_files.append(label)

    if missing_files:
        details.append(f"Missing required files: {', '.join(missing_files)}")
        return {
            "exit_code": 2,
            "structural": "BLOCKED",
            "historical": "UNIDENTIFIED",
            "summary": {},
            "details": details,
        }

    # ── Helper: load JSON with structured error handling ──
    def _load_json(path: Path, label: str) -> dict | None:
        """Load a JSON file; on decode error or OS error return None and log the failure."""
        try:
            with open(path) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            details.append(f"  JSON parse error in {label}: {e}")
            return None
        except OSError as e:
            details.append(f"  OS error loading {label}: {e}")
            return None

    # ── Load batch01 candidates ──
    candidates_data = _load_json(candidates_path, "batch01_candidates.json")
    if candidates_data is None:
        return {
            "exit_code": 2,
            "structural": "BLOCKED",
            "historical": "UNIDENTIFIED",
            "summary": {},
            "details": details,
        }

    records = candidates_data.get("records", [])
    if not isinstance(records, list):
        details.append("batch01_candidates.json: 'records' must be a list")
        return {
            "exit_code": 2,
            "structural": "BLOCKED",
            "historical": "UNIDENTIFIED",
            "summary": {},
            "details": details,
        }

    # ── Load access register (approved_excerpts) ──
    access_data = _load_json(access_path, "access_register.json")
    if access_data is None:
        return {
            "exit_code": 2,
            "structural": "BLOCKED",
            "historical": "UNIDENTIFIED",
            "summary": {},
            "details": details,
        }
    approved_excerpts = access_data.get("approved_excerpts", [])

    # ── Evaluate each source ──
    admitted_count = 0
    candidate_count = 0
    blocked_count = 0
    work_ids: set[str] = set()

    for rec in records:
        result = evaluate_source(rec, approved_excerpts=approved_excerpts)
        if result["status"] == "admitted":
            admitted_count += 1
        elif result["status"] == "candidate":
            candidate_count += 1
        else:
            blocked_count += 1

        wid = rec.get("work_id")
        if wid:
            work_ids.add(wid)

        for reason in result["reasons"]:
            details.append(f"  [{rec.get('source_id')}] {reason}")

    # ── Shared observations ──
    shared = find_shared_observations(records)
    non_independent = sum(1 for r in shared if r["independent"] is False)
    details.append(f"  Shared-observation pairs: {len(shared)}, non-independent: {non_independent}")

    # ── Authority coverage ──
    authority_data = _load_json(authority_path, "authority_coverage.json")
    if authority_data is None:
        return {
            "exit_code": 2,
            "structural": "BLOCKED",
            "historical": "UNIDENTIFIED",
            "summary": {},
            "details": details,
        }
    auth_list = (
        authority_data
        if isinstance(authority_data, list)
        else authority_data.get("authorities", [])
    )
    auth_blocked = sum(1 for a in auth_list if a.get("status") == "blocked")
    details.append(f"  Authority entries: {len(auth_list)}, blocked: {auth_blocked}")

    # ── Event candidates ──
    events_data = _load_json(events_path, "events.json")
    if events_data is None:
        return {
            "exit_code": 2,
            "structural": "BLOCKED",
            "historical": "UNIDENTIFIED",
            "summary": {},
            "details": details,
        }
    ev_list = events_data.get("events", [])
    ev_candidates = sum(1 for e in ev_list if e.get("status") == "candidate")
    details.append(f"  Event candidates: {len(ev_list)}, candidate: {ev_candidates}")

    # ── Review requests ──
    rr_data = _load_json(review_req_path, "review_requests.json")
    if rr_data is None:
        return {
            "exit_code": 2,
            "structural": "BLOCKED",
            "historical": "UNIDENTIFIED",
            "summary": {},
            "details": details,
        }
    rr_list = rr_data.get("requests", [])
    rr_required = sum(1 for r in rr_list if r.get("status") == "REVIEW_REQUIRED")
    details.append(f"  Review requests: {len(rr_list)}, REVIEW_REQUIRED: {rr_required}")

    # ── Anchor crosswalk ──
    crosswalk_data = _load_json(crosswalk_path, "anchor_crosswalk.json")
    if crosswalk_data is None:
        return {
            "exit_code": 2,
            "structural": "BLOCKED",
            "historical": "UNIDENTIFIED",
            "summary": {},
            "details": details,
        }
    anchor_records = crosswalk_data.get("records", [])

    # ── Load manifest for crosswalk validation (R1: legacy_artifact_ids) ──
    # legacy_anchors = manifest initial_state artifacts (NOT the crosswalk records themselves)
    manifest_data = _load_json(manifest_path, "DATA_MANIFEST_v1.json")
    legacy_artifact_ids: set[str] = set()
    if manifest_data is not None:
        legacy_artifact_ids = {
            a.get("artifact_id", "")
            for a in manifest_data.get("artifacts", [])
            if a.get("role") == "initial_state" and a.get("artifact_id")
        }
    if len(anchor_records) != 63:
        details.append(
            f"  anchor_crosswalk.json: expected 63 records, got {len(anchor_records)}"
        )
        return {
            "exit_code": 2,
            "structural": "BLOCKED",
            "historical": "BLOCKED",
            "summary": {},
            "details": details,
        }

    # Validate crosswalk (raises ValueError on structural error)
    try:
        validate_anchor_crosswalk(anchor_records, legacy_artifact_ids=legacy_artifact_ids)
    except ValueError as e:
        details.append(f"  anchor_crosswalk validation error: {e}")
        return {
            "exit_code": 2,
            "structural": "BLOCKED",
            "historical": "BLOCKED",
            "summary": {},
            "details": details,
        }

    # Count classifications
    classifications: dict[str, int] = {}
    for a in anchor_records:
        cl = a.get("classification", "unknown")
        classifications[cl] = classifications.get(cl, 0) + 1

    for cl, cnt in sorted(classifications.items()):
        details.append(f"  Anchor classification {cl}: {cnt}")

    # ── Determine exit code ──
    # H1A passes structurally when:
    #   - all required files exist and parseable
    #   - anchor crosswalk validates (no ValueError)
    #   - 63 anchors all classified
    structural_pass = True

    # H1A historical gate: requires admitted primary documents + authority coverage + events
    historical_pass = (
        admitted_count >= 1
        and auth_blocked == 0
        and all(e.get("status") != "candidate" for e in ev_list)
    )

    if not structural_pass:
        exit_code = 2
    elif not historical_pass:
        exit_code = 1
    else:
        exit_code = 0

    return {
        "exit_code": exit_code,
        "structural": "PASS" if structural_pass else "BLOCKED",
        "historical": "BLOCKED" if not historical_pass else "PASS",
        "summary": {
            "total_candidates": candidate_count,
            "total_admitted": admitted_count,
            "total_blocked_anchors": sum(v for k, v in classifications.items() if k == "blocked"),
            "total_sources": len(records),
            "total_works": len(work_ids),
            "anchor_classifications": classifications,
            "authority_blocked": auth_blocked,
            "event_candidates": ev_candidates,
            "review_requests_required": rr_required,
        },
        "details": details,
    }


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _evaluate_rights(rights: dict | None) -> dict | None:
    """
    Evaluate rights dict per RightsSpec.

    Supports both the RightsSpec field name (license_status) and the
    legacy artifact field name (license).  Returns None if no rights dict;
    returns {} if license_status/license is 'unknown'; returns the dict otherwise.
    """
    if not rights:
        return None
    # RightsSpec uses license_status; artifact JSON may use 'license'
    status = rights.get("license_status") or rights.get("license", "unknown")
    if status == "unknown":
        return {}
    return rights


def _validate_excerpt(excerpt: dict) -> bool:
    """Validate an approved excerpt has all required fields."""
    required = {
        "excerpt_id", "source_id", "content_hash",
        "approved_by", "approved_at", "allowed_window",
    }
    return all(k in excerpt and excerpt[k] for k in required)


# --------------------------------------------------------------------------- #
# CLI entry point
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import json as _json

    repo_root = Path(".")
    if "--root" in sys.argv:
        idx = sys.argv.index("--root")
        if idx + 1 < len(sys.argv):
            repo_root = Path(sys.argv[idx + 1])

    result = audit_h1a(repo_root)
    _json.dump(result, sys.stdout, indent=2)
    sys.exit(result["exit_code"])
