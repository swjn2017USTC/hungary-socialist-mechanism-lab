"""P07B2 regression tests: manifest verification.

Verifies that studies/manifest.json and all M*/study_decl.json files
are machine-readable and satisfy the declared/blocked manifest contract.
No production engine is modified.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# studies/manifest.json
# ---------------------------------------------------------------------------

def test_manifest_exists_and_valid_json() -> None:
    """studies/manifest.json must exist and be valid JSON."""
    manifest_path = ROOT / "studies" / "manifest.json"
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)


def test_manifest_has_required_top_level_fields() -> None:
    """manifest.json must have manifest_version, phase, and records."""
    manifest_path = ROOT / "studies" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "manifest_version" in payload
    assert "phase" in payload
    assert "records" in payload
    assert isinstance(payload["records"], list)


def test_manifest_phase_is_p07a1() -> None:
    """Phase must be P07A1 (the phase that created the manifest)."""
    manifest_path = ROOT / "studies" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["phase"] == "P07A1"


def test_manifest_has_exactly_11_records() -> None:
    """manifest.json must contain exactly 11 records (M01–M11)."""
    manifest_path = ROOT / "studies" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(payload["records"]) == 11


def test_manifest_records_have_required_fields() -> None:
    """Each record must have record_id, mechanism_id, status, and reason fields."""
    manifest_path = ROOT / "studies" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    required_fields = {
        "record_id", "mechanism_id", "status",
        "intent", "linked_cards",
    }
    for record in payload["records"]:
        missing = required_fields - set(record.keys())
        assert not missing, f"Record {record.get('record_id')} missing fields: {missing}"


def test_manifest_mechanism_ids_m01_to_m11() -> None:
    """Each record must have a unique mechanism_id from M01 to M11."""
    manifest_path = ROOT / "studies" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids = sorted(r["mechanism_id"] for r in payload["records"])
    assert ids == [f"M{i:02d}" for i in range(1, 12)]


def test_manifest_all_statuses_are_declared_or_blocked() -> None:
    """All record statuses must be either 'declared' or 'blocked'."""
    manifest_path = ROOT / "studies" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    for record in payload["records"]:
        assert record["status"] in ("declared", "blocked"), (
            f"Record {record['record_id']} has unexpected status: {record['status']}"
        )


def test_manifest_declared_records_have_nonempty_declared_reason() -> None:
    """Every record with status=declared must have a non-empty declared_reason."""
    manifest_path = ROOT / "studies" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    for record in payload["records"]:
        if record["status"] == "declared":
            assert record.get("declared_reason"), (
                f"Record {record['record_id']} is DECLARED but has no declared_reason"
            )


def test_manifest_blocked_records_have_nonempty_blocked_reason() -> None:
    """Every record with status=blocked must have a non-empty blocked_reason."""
    manifest_path = ROOT / "studies" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    for record in payload["records"]:
        if record["status"] == "blocked":
            assert record.get("blocked_reason"), (
                f"Record {record['record_id']} is BLOCKED but has no blocked_reason"
            )


def test_manifest_no_research_package_complete_true() -> None:
    """No record may claim research_package_complete=true."""
    manifest_path = ROOT / "studies" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    for record in payload["records"]:
        rpc = record.get("research_package_complete")
        assert rpc is not True, (
            f"Record {record['record_id']} incorrectly claims research_package_complete=true"
        )


def test_manifest_declared_card_count() -> None:
    """Exactly 3 cards must be declared (M01, M05, M08 per the plan)."""
    manifest_path = ROOT / "studies" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared = [r for r in payload["records"] if r["status"] == "declared"]
    blocked = [r for r in payload["records"] if r["status"] == "blocked"]
    assert len(declared) == 3, (
        f"Expected 3 declared, got {len(declared)}: "
        f"{[r['mechanism_id'] for r in declared]}"
    )
    assert len(blocked) == 8, f"Expected 8 blocked, got {len(blocked)}"


# ---------------------------------------------------------------------------
# Per-card study_decl.json files
# ---------------------------------------------------------------------------

def test_each_mechanism_has_study_decl_json() -> None:
    """studies/M01/ through studies/M11/ must each contain study_decl.json."""
    for i in range(1, 12):
        mid = f"M{i:02d}"
        decl_path = ROOT / "studies" / mid / "study_decl.json"
        assert decl_path.exists(), f"{mid}/study_decl.json does not exist"


def test_each_study_decl_is_valid_json() -> None:
    """Each study_decl.json must be valid JSON."""
    for i in range(1, 12):
        mid = f"M{i:02d}"
        decl_path = ROOT / "studies" / mid / "study_decl.json"
        payload = json.loads(decl_path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)


def test_each_study_decl_has_required_fields() -> None:
    """Each study_decl.json must have mechanism_id, intent, status, phase."""
    for i in range(1, 12):
        mid = f"M{i:02d}"
        decl_path = ROOT / "studies" / mid / "study_decl.json"
        payload = json.loads(decl_path.read_text(encoding="utf-8"))
        required = {"mechanism_id", "intent", "status", "phase", "v1_card_sha256"}
        missing = required - set(payload.keys())
        assert not missing, f"{mid}/study_decl.json missing fields: {missing}"


def test_each_study_decl_mechanism_id_matches_directory() -> None:
    """Each study_decl.json mechanism_id must match its parent directory."""
    for i in range(1, 12):
        mid = f"M{i:02d}"
        decl_path = ROOT / "studies" / mid / "study_decl.json"
        payload = json.loads(decl_path.read_text(encoding="utf-8"))
        assert payload["mechanism_id"] == mid, (
            f"{mid}/study_decl.json has mechanism_id={payload['mechanism_id']}"
        )


def test_each_study_decl_sha256_is_64_hex_chars() -> None:
    """Each study_decl.json v1_card_sha256 must be a 64-char hex string."""
    for i in range(1, 12):
        mid = f"M{i:02d}"
        decl_path = ROOT / "studies" / mid / "study_decl.json"
        payload = json.loads(decl_path.read_text(encoding="utf-8"))
        sha = payload["v1_card_sha256"]
        assert len(sha) == 64, (
            f"{mid}/study_decl.json v1_card_sha256 is {len(sha)} chars, expected 64"
        )
        assert all(c in "0123456789abcdef" for c in sha), (
            f"{mid}/study_decl.json v1_card_sha256 contains non-hex chars"
        )


def test_each_study_decl_no_research_package_complete_true() -> None:
    """No study_decl.json may claim research_package_complete=true."""
    for i in range(1, 12):
        mid = f"M{i:02d}"
        decl_path = ROOT / "studies" / mid / "study_decl.json"
        payload = json.loads(decl_path.read_text(encoding="utf-8"))
        rpc = payload.get("research_package_complete", False)
        assert rpc is not True, (
            f"{mid}/study_decl.json incorrectly claims research_package_complete=true"
        )


def test_study_decl_status_matches_manifest() -> None:
    """Each study_decl.json status must match the corresponding manifest record."""
    manifest_path = ROOT / "studies" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_by_id = {r["mechanism_id"]: r for r in manifest["records"]}

    for i in range(1, 12):
        mid = f"M{i:02d}"
        decl_path = ROOT / "studies" / mid / "study_decl.json"
        payload = json.loads(decl_path.read_text(encoding="utf-8"))
        m_record = manifest_by_id[mid]
        assert payload["status"] == m_record["status"], (
            f"{mid} status mismatch: manifest={m_record['status']}, "
            f"study_decl.json={payload['status']}"
        )


def test_study_decl_phase_is_p07a1() -> None:
    """Each study_decl.json phase must be P07A1."""
    for i in range(1, 12):
        mid = f"M{i:02d}"
        decl_path = ROOT / "studies" / mid / "study_decl.json"
        payload = json.loads(decl_path.read_text(encoding="utf-8"))
        assert payload["phase"] == "P07A1"


def test_v1_card_sha256_matches_supersedes_json() -> None:
    """Each study_decl.json v1_card_sha256 must match supersedes.json."""
    supersedes_path = ROOT / "config" / "mechanisms" / "v2" / "supersedes.json"
    supersedes = json.loads(supersedes_path.read_text(encoding="utf-8"))

    for i in range(1, 12):
        mid = f"M{i:02d}"
        decl_path = ROOT / "studies" / mid / "study_decl.json"
        payload = json.loads(decl_path.read_text(encoding="utf-8"))
        expected_sha = supersedes.get(mid)
        if expected_sha is not None:
            assert payload["v1_card_sha256"] == expected_sha, (
                f"{mid} v1_card_sha256 mismatch: "
                f"study_decl={payload['v1_card_sha256']}, "
                f"supersedes={expected_sha}"
            )
