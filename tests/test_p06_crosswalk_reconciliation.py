"""P07A1 crosswalk identity tests.

Verifies the P06_STATUS_RECONCILIATION.md overlay correctly maps old 1/13
→ new 2/1/11 table identities, and that no frozen report content was modified.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Crosswalk overlay exists and is well-formed
# ---------------------------------------------------------------------------

def test_crosswalk_overlay_exists() -> None:
    """P06_STATUS_RECONCILIATION.md must exist in the evidence directory."""
    overlay = ROOT / "docs" / "upgrade_review" / "evidence" / "P06_STATUS_RECONCILIATION.md"
    assert overlay.exists(), f"Overlay not found at {overlay}"


def test_crosswalk_has_required_sections() -> None:
    """Overlay must contain all required crosswalk sections."""
    overlay = ROOT / "docs" / "upgrade_review" / "evidence" / "P06_STATUS_RECONCILIATION.md"
    text = overlay.read_text(encoding="utf-8")

    required_sections = [
        "Old vs New Table Identity Crosswalk",
        "Run Identity Crosswalk",
        "Card SHA-256 Crosswalk",
        "Protected Identities",
        "11-Card Manifest Status Summary",
        "Version and Digest Audit Trail",
    ]
    for section in required_sections:
        assert section in text, f"Required section '{section}' not found in overlay"


def test_crosswalk_c0_digest_correct() -> None:
    """C0 digest in overlay must match the known audit value."""
    overlay = ROOT / "docs" / "upgrade_review" / "evidence" / "P06_STATUS_RECONCILIATION.md"
    text = overlay.read_text(encoding="utf-8")

    # C0 digest
    assert "92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d" in text
    # C1 digest
    assert "c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5" in text


def test_crosswalk_v1_card_shas_match_supersedes() -> None:
    """v1 SHA-256 values in overlay must match supersedes.json."""
    overlay = ROOT / "docs" / "upgrade_review" / "evidence" / "P06_STATUS_RECONCILIATION.md"
    supersedes_path = ROOT / "config" / "mechanisms" / "v2" / "supersedes.json"

    supersedes = json.loads(supersedes_path.read_text(encoding="utf-8"))
    overlay_text = overlay.read_text(encoding="utf-8")

    for mechanism_id, sha in supersedes.items():
        if mechanism_id in ("schema_version", "description"):
            continue
        assert sha in overlay_text, (
            f"v1 SHA for {mechanism_id} ({sha}) not found in crosswalk overlay"
        )


def test_crosswalk_no_false_research_package_complete() -> None:
    """Overlay must not claim any card has research_package_complete=true."""
    overlay = ROOT / "docs" / "upgrade_review" / "evidence" / "P06_STATUS_RECONCILIATION.md"
    text = overlay.read_text(encoding="utf-8")

    # The phrase "research_package_complete" should only appear in the negative
    matches = re.findall(r"research_package_complete.*?true", text, re.IGNORECASE)
    assert len(matches) == 0, (
        f"Overlay incorrectly claims research_package_complete=true: {matches}"
    )


def test_crosswalk_11_card_summary_present() -> None:
    """11-card manifest status summary must list all M1–M11."""
    overlay = ROOT / "docs" / "upgrade_review" / "evidence" / "P06_STATUS_RECONCILIATION.md"
    text = overlay.read_text(encoding="utf-8")

    for i in range(1, 12):
        card = f"M{i}"
        assert card in text, f"Card {card} not found in 11-card manifest summary"


def test_crosswalk_graded_crosswalk_table() -> None:
    """Overlay must document old 1/13 → new 2/1/11 grade changes."""
    overlay = ROOT / "docs" / "upgrade_review" / "evidence" / "P06_STATUS_RECONCILIATION.md"
    text = overlay.read_text(encoding="utf-8")

    # The specific table showing grade transitions
    assert "normalized_index" in text
    assert "no_counterpart" in text
    assert "blocked" in text
    # Must mention the old-to-new transition
    assert "old" in text.lower() and "new" in text.lower()


def test_frozen_report_not_modified() -> None:
    """docs/phases/P06_FINAL_REPORT.md must not appear in git diff."""
    import subprocess

    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "docs/phases/P06_FINAL_REPORT.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    diff = result.stdout.strip()
    assert diff == "", (
        "docs/phases/P06_FINAL_REPORT.md was modified — "
        f"frozen report must not be changed. Diff: {diff}"
    )


def test_crosswalk_v1_schema_sha_present() -> None:
    """Overlay must contain the v1 schema SHA-256."""
    overlay = ROOT / "docs" / "upgrade_review" / "evidence" / "P06_STATUS_RECONCILIATION.md"
    text = overlay.read_text(encoding="utf-8")

    # v1 schema SHA from audit
    assert "e35d09887cfa853275feaf99fbe1e4f149c38ff5b0699533381390ba5a8d0be9" in text, (
        "v1 schema SHA-256 not found in overlay"
    )


def test_crosswalk_run_identity_table() -> None:
    """Overlay must list C0 and C1 with correct run_id/scenario/digest."""
    overlay = ROOT / "docs" / "upgrade_review" / "evidence" / "P06_STATUS_RECONCILIATION.md"
    text = overlay.read_text(encoding="utf-8")

    assert "historical_f2_replay" in text
    assert "historical_f2_trade_scenario" in text
    assert "codex-audit-vnext-20261011" in text
