"""Metadata-only registry audit (offline by default, optional online HEAD checks).

The audit separates ``registry_valid`` (structure/references/roles parse) from
``sources_ready`` (verified rights + checked metadata). A registry holding
blocked sources is a *successful audit*, never a Data Freeze and never a PASS
over data availability. Online mode issues one HEAD per metadata locator with
a 10s timeout; it never downloads data files, never retries, and never
upgrades unknown rights.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from hsm_lab.contract.schemas import DataRole
from hsm_lab.data.registry import DataRegistry
from hsm_lab.data.schemas import AuditStatus

_ONLINE_TIMEOUT_S = 10.0
_USER_AGENT = "hsm-lab-p00-metadata-audit/0.1 (research provenance check; no data download)"

GAP_ITEMS: tuple[tuple[str, str, str], ...] = (
    (
        "county_variable_census_coverage",
        "20-node x variable x census-year coverage matrix",
        "§41.1-2",
    ),
    ("io_tables_1972_1976", "1972/1976 Hungary IO tables availability/parsability", "§41.3"),
    ("cmea_energy_quantity", "CMEA / USSR-Hungary energy import quantity series", "§41.4"),
    ("cmea_contract_price_anchors", "CMEA bilateral contract-price anchors", "§41.5"),
    (
        "shortage_proxy_definition",
        "shortage proxy definition (availability/queue/substitution)",
        "§41.6",
    ),
    ("second_economy_years", "second-economy data usable years", "§41.7"),
    ("tarki_rights_weights", "TARKI raw microdata rights and weights", "§41.8"),
    ("osa_machine_readability", "OSA records machine readability", "§41.9"),
    ("enterprise_data", "1970s-80s enterprise-level data", "§41.10"),
    ("coalition_proxies", "political coalition observable indicators", "§41.11"),
    ("information_capacity_proxies", "information/computing proxies", "§41.12"),
    ("g1_g2_mapping", "G1/G2 ontology mapping to historical statistics", "§41.15-16"),
    ("retail_shortage", "commodity-level regional retail / shortage proxies", "§41.18"),
    (
        "elasticity_substitution_durables",
        "demand elasticity/substitution and durable waiting lists",
        "§41.19-20",
    ),
)


def _source_is_ready(source: Any) -> bool:
    return (
        source.rights.license_status == "verified"
        and source.rights.download_allowed is True
        and source.audit_status is AuditStatus.METADATA_CHECKED
    )


def _head_check(locator: str) -> dict[str, Any]:
    record: dict[str, Any] = {"locator": locator}
    try:
        parsed = urlparse(locator)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("not an http(s) metadata locator")
        request = urllib.request.Request(
            locator, method="HEAD", headers={"User-Agent": _USER_AGENT}
        )
        with urllib.request.urlopen(request, timeout=_ONLINE_TIMEOUT_S) as response:
            record.update(
                {
                    "result": "ok",
                    "http_status": response.status,
                    "content_type": response.headers.get("Content-Type"),
                    "final_url": response.url,
                }
            )
    except urllib.error.HTTPError as exc:
        record.update({"result": "http_error", "http_status": exc.code, "error": str(exc)})
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        record.update({"result": "failed", "error": str(exc)})
    record["checked_at"] = datetime.now(UTC).isoformat()
    return record


def audit_registry(registry: DataRegistry, *, online: bool = False) -> dict[str, Any]:
    """Audit manifest metadata. Never mutates the registry or its files."""
    sources = list(registry.sources.values())
    ready = [s.source_id for s in sources if _source_is_ready(s)]
    blocked = [
        {
            "source_id": s.source_id,
            "access_status": s.access_status.value,
            "audit_status": s.audit_status.value,
            "license_status": s.rights.license_status,
            "download_allowed": s.rights.download_allowed,
            "redistribution_allowed": s.rights.redistribution_allowed,
            "reason": s.notes or s.coverage_notes,
        }
        for s in sources
        if not _source_is_ready(s)
    ]
    role_coverage: dict[str, int] = {role.value: 0 for role in DataRole}
    for source in sources:
        for role in source.expected_roles:
            role_coverage[role.value] += 1
    report: dict[str, Any] = {
        "schema_version": "1",
        "audit_kind": "metadata_only",
        "registry_valid": True,
        "artifacts_registered": len(registry.artifacts),
        "sources_total": len(sources),
        "sources_ready": not blocked,
        "ready_source_ids": ready,
        "blocked_or_unverified": blocked,
        "variables_registered": len(registry.variables),
        "role_coverage_in_sources": role_coverage,
        "online": online,
        "gaps": [
            {"gap_id": gap_id, "status": "not_audited", "description": description,
             "reference": f"BASELINE.md {reference}"}
            for gap_id, description, reference in GAP_ITEMS
        ],
        "notes": [
            "Network reachability is not data acquisition; unknown rights stay unknown.",
            "No raw data files were downloaded; no TARKI/OSA microdata was requested.",
            "This report is a registry audit, not a Data Freeze and not a simulation result.",
        ],
    }
    if online:
        report["online_checks"] = [_head_check(source.locator) for source in sources]
    return report


def write_audit_report(report: dict[str, Any], output_dir: Any) -> str:
    """Write the report JSON into a fresh directory; return the file path."""
    import json
    from pathlib import Path

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    path = output_dir / "audit_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)
