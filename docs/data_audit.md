# Data audit (P00)

The data registry (`data/manifests/{sources,variables,artifacts}.yml`) is a
candidate catalogue with rights metadata. **No dataset has been obtained.**
`artifacts: []` until real files exist with verified rights, real SHA-256
digests and full provenance.

## Roles of the audit

`hsm data audit [--online] [--output-dir DIR] --json` reports:

- `registry_valid` — manifests parse, references resolve, roles are consistent;
- `sources_ready` — false while any source lacks verified rights + checked
  metadata. A registry containing blocked sources is a *successful audit*,
  never a Data Freeze and never a claim of data availability.

Offline mode reads only local files. Online mode issues one `HEAD` per
registered metadata locator (10 s timeout, sequential, no retries), records
HTTP status/content-type/final URL, and never follows data download links,
never fetches CSV/XLSX/PDF tables, never calls SOAP. Network reachability is
never promoted into rights evidence.

## Rights policy highlights

- **KSH website tables** — CC BY 4.0 verified (terms page quote + check date);
  specific-request files (CC BY-NC) excluded from the grant.
- **World Bank Pink Sheet** — terms read; whether the dataset is in the CC BY
  scope is unconfirmed, so rights stay `unknown`.
- **FRED FEDFUNDS** — series is "Public Domain: Citation Requested" but the
  FRED legal page restricts ML-related use; registered `restricted`/`blocked`.
  P00 fetches nothing.
- **MNB** — attribution-only distribution grant (`restricted`); download and
  transformed redistribution permissions remain unconfirmed.
- **TÁRKI / OSA / IMF** — `unknown`/`catalogue_only`/`blocked`; no microdata
  was requested or downloaded.
- **CMEA energy reconstruction** — reconstruction requirement only; never
  observed, never fabricated.

## Audit report gaps

The report enumerates the open data gaps from BASELINE §41 (county×census
coverage, IO tables 1972/76, CMEA quantity/price anchors, shortage proxies,
second economy, TÁRKI weights, OSA machine-readability, enterprise data,
coalition proxies, information-capacity proxies, G1/G2 mapping, retail
shortage, elasticity/durables). Every item carries `status: not_audited` plus
its BASELINE reference; nothing is invented to fill the table.
