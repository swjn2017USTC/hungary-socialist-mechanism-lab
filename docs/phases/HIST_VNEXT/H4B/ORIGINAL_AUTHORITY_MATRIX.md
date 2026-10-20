# H4B original-authority matrix

Declaration only. No entry in this file is a historical finding, an admitted excerpt, or a model
input. Read level is metadata only: batch manifests, page indexes, QA/exposure records, the H4A-0
source registry, and the H1B synthetic calendar. No original PDF, OCR body, HOLD page, or private
transcript was opened in this step. `approved_excerpt_id = null` everywhere because both source
packages report empty approved-excerpt sets.

Bibliography used below:

- **D01** = Balassa, *The Hungarian Economic Reform, 1968–81*, World Bank Staff Working Paper 506,
  1982; 43 PDF pages; SHA-256 `dd1e8653…d95ad`; `secondary_analysis`.
- **D02-ch02** = Boote/Somogyi, *Economic Reform in Hungary Since 1968*, ch. II, IMF Occasional
  Paper 83, 1991; 2 PDF pages; SHA-256 `0c8e4bf9…2a1bf`; `secondary_analysis`; `work_id =
  boote_somogyi_1991_op83`.
- **D02-ch05** = same work, ch. V; 4 PDF pages; SHA-256 `19e339a0…7009a`; trade background only.
- **Y1956/1957/1960/1968/1973/1975/1978** = Hungarian Statistical Yearbook volumes, user-supplied
  scans; SHA-256 recorded in `SOURCE_MANIFEST.json`.
- **H1B** = `institutions/HIST_VNEXT/h1b_synthetic_calendar.json`; six synthetic fixture events.

Page tags in `page_index.csv` are retrieval hints, not evidence. A page that is tagged
`reform_permissions` has **not** been read here and supplies no proposition.

| # | Period / sector / actor | Candidate bibliography and physical PDF page pointer | Read level | Admitted excerpt ID | Narrowest proposition actually supported | Unproven institutional detail | D03/D04/D05/D16 gaps | Model authority vs historical authority |
|---|---|---|---|---|---|---|---|---|
| 1 | 1968 procurement; industrial enterprises; enterprise purchase decisions | D01 pp. 1, 3, 5, 9–11, 14–17, 26–27, 32, 36–37, 43 carry `reform_permissions` tags; D02-ch02 pp. 1–2 carry `reform_permissions` + `prices` tags. Both are post-hoc secondary analyses. | metadata only; no page body read | null | None stated. The metadata only locates candidate discussions of 1968 reform permissions; it does not establish which organizations could purchase which commodities, under what central or sectoral approval, from when. | Scope of the grant (all industry? which organizations?), commodity coverage, whether central/sectoral permission persisted, effective date within 1968, and revocation rules. | D03 reform resolution and D04 implementing regulations absent; D05 enterprise sample absent; D16 CMEA/party records absent. | **Model:** H1B synthetic `EVT-1966-NEM-GRANT-PROCUREMENT` (`procurement`, quarter `1968-01-01..1968-03-31`, synthetic flag, source `synthetic_h1b_design_note`) can be queried. **Historical:** `UNIDENTIFIED`; no historical grant is admitted. |
| 2 | 1968 price categories; price-proposal subjects; producer/consumer price administration | D01 pp. 3, 7–9, 11–14, 18, 21–23, 25–30, 34, 36 carry `prices` tags; D02-ch02 pp. 1–2 carry `prices`. | metadata only | null | None stated. No category list, no fixed/free/authorized-adjustment share, no proposing authority, and no approval criterion is established by the metadata. | Which product categories were fixed, which were subject to authorized adjustment, who proposed, who approved, and the effective dates. | D03/D04 absent; D05 absent; D16 absent. | **Model:** H1B synthetic `EVT-1968-NEM-GRANT-PRICE-SETTING` (`price_setting`, industry with agriculture excluded, synthetic). The engine's `PolicyVector.admin_price_factor` is a **global scalar multiplier** (`engine/policy.py:89–94`), not a per-category authority. **Historical:** `UNIDENTIFIED`. |
| 3 | 1968 investment approval; investment proposers and approvers | D01 pp. 1, 3, 5, 7, 9–11, 15, 17, 19–20, 23–26, 29, 31, 34 carry `investment_credit` tags; D02-ch02 p. 2 carries `investment_credit`. | metadata only | null | None stated. The metadata locates candidate discussion of investment/credit, not an approval rule, threshold, or delegation. | Project-level approval authority, thresholds, waiting time, financing source, and whether enterprise proposals were binding. | D03/D04 absent; D05 enterprise records absent; D16 absent. | **Model:** H1B synthetic `EVT-1968-NEM-GRANT-INVESTMENT` (`investment_approval`, organization `ORG-ENT-A`, sector `industry`, synthetic). There is **no** per-project approval input in `TickControls`; `engine/finance.py:1611–1615` approves `requested` up to remaining cash, and `engine/material.py:1594–1605` forms `new_request` from endogenous capacity × hunger. **Historical:** `UNIDENTIFIED`. |
| 4 | 1972 adjustment; industry/organization scope | Y1973 pp. 94–97: one 1972 consolidated IO matrix in organizational delimitation, four continuation pages. H1B synthetic revoke `EVT-1968-NEM-REVOKE-PROCUREMENT-ENT-B` uses 1972-11-15. | metadata only (locator/exposure records); the matrix was not read | null | None. The locator states only that pp. 94–97 are one 1972 matrix, not a reform act and not a 1973 observation. | Date, legal form, sector and enterprise scope, and whether any procurement/investment/price authority actually changed in 1972. | D03/D04 absent; D05 absent; D16 absent. The synthetic revoke is a fixture, not evidence. | **Model:** synthetic revoke exists for one organization only. **Historical:** no 1972 adjustment is established; do not generalize the fixture into a "recentralization". |
| 5 | 1973 adjustment; industry/organization scope | No candidate page was located in the read metadata for a 1973 institutional act. Y1973 pp. 94–97 are **1972** data. | metadata only | null | None. | Existence, date, scope, and content of any 1973 adjustment. | D03/D04/D05/D16 absent. | **Model:** none. **Historical:** `UNIDENTIFIED`. |
| 6 | 1974 adjustment; industry/organization scope | No candidate page located in the read metadata. | metadata only | null | None. | Existence, date, scope, content. | D03/D04/D05/D16 absent. | **Model:** none. **Historical:** `UNIDENTIFIED`. |
| 7 | 1975 adjustment; industry/organization scope | Y1975 p. 120 is a candidate **organizational/wage statistical-definition** page (locator: `D09_1975_0120_0120`). Y1975 pp. 272–275 are trade method/total pages. | metadata only | null | None about an institutional act. The locator explicitly says the p. 120 definition change is not behavioural-mechanism evidence. | Whether p. 120 reflects a real organizational change, its date/scope, and whether it coincides with any authority change. | D03/D04/D05/D16 absent. | **Model:** CMEA pre/post-1975 synthetic events exist, unrelated to domestic investment/price authority. **Historical:** `UNIDENTIFIED`. |
| 8 | 1976 adjustment; industry/organization scope | No candidate page located. Y1978 p. 370 documents only the 1968→1976 **comparison-price basis** change. | metadata only | null | `Y1978 p. 370` supports, at the locator level, that the comparison-price basis changed to 1976 prices. It does **not** establish any 1976 institutional adjustment. This is a measurement/definition statement, not behavior. | Any 1976 authority/approval change; date, scope, legal form. | D03/D04/D05/D16 absent. | **Model:** none. **Historical:** `UNIDENTIFIED`; comparison-price basis is a measurement issue. |
| 9 | Enterprise implementation chain (application → approval → procurement/finance → delivery → input/output → consumption) | D05 enterprise sample absent; D03/D04 legal acts absent; D16 absent. H1B synthetic procurement fixture has a synthetic `observed_implementation_at = 1968-03-15`. H2B tiny tests exercise the procurement bridge on synthetic state, not on historical firms. | metadata only; H2B code read | null | None historically. The only executable chain is the synthetic H2B procurement bridge, which commits a `ProcurementDecision` into `TickControls` and settles against kernel prices; it is not a historical firm. | Who applied, who approved, what was financed, what was delivered, and what was produced in any historical enterprise. | D05 absent; D03/D04 absent; D16 absent. | **Model:** procurement only (`execution_adapter.py:363–371`). Price and investment decisions return `is_committed=false` with the documented "no existing TickControls mapping" reason. **Historical:** `NOT_ESTABLISHED`. |

## Shared-source and independence constraints

- D02-ch02 and D02-ch05 are chapters of one work (`work_id = boote_somogyi_1991_op83`). They are
  not two independent sources, and ch05 is background for trade only.
- Y1956 p. 20 and Y1957 p. 21 are two print witnesses of one 1957-01-01 population observation.
- Y1956 p. 279 and Y1957 p. 349 are two print witnesses of one 1956-12-31 dwelling-stock
  observation.
- Y1973 pp. 94–97 are four continuation pages of one 1972 matrix; they are not four observations.
- Native text and OCR of the same page are two machine readings, not two historical sources.

## Read-level legend

- `metadata only` — only manifest/page-index/QA/exposure/locator fields were consulted; no body
  text, image, or number.
- `code read` — repository source was read, not a historical document.
- No entry in this matrix reaches `approved excerpt` or `admitted value`.
