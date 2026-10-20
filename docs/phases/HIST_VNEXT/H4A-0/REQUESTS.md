# H4A-0 requests

No request below is approved. They are narrow requests for an isolated reviewer; they do not
authorize a whole-volume read, OCR, translation, embedding, or model upload.

## Existing batch01 requests (unchanged)

| ID | Source | Pages | Purpose | Status |
|---|---|---|---|---|
| RR-001 | `balassa_1982_swp506` | 10–18 | price/investment/1972 adjustment clues | REVIEW_REQUIRED |
| RR-002 | `boote_somogyi_1991_ch02` | 1–2 | reform approval vs implementation | REVIEW_REQUIRED |
| RR-003 | `kenen_1990_wp9079` | 7 | CMEA rules and authority clues | REVIEW_REQUIRED |
| RR-004 | `boote_somogyi_1991_ch05` | 1–4 | foreign trade/exchange-rate reform | REVIEW_REQUIRED |

## New narrow requests

| ID | Source + SHA | Physical page | Need | Allowed use requested | Isolated-review requirement | Current result |
|---|---|---|---|---|---|---|
| RR-H4A0-001 | `EPA_YEARBOOK_1956`, `b443db48…f2f` | 92 | fuel/energy table needed for D09 material context | definition/background | SHA + page + table/columns + purpose + approver | HOLD; skipped |
| RR-H4A0-002 | `EPA_YEARBOOK_1957`, `abc69099…9a63` | 17 | population page adjacent to the 1957-01-01 table | initial-state context | same | HOLD; skipped; no candidate |
| RR-H4A0-003 | `EPA_YEARBOOK_1960`, `12064a83…f291` | 405, 409, 413 | IO A/B direct-coefficient, import and inverse-matrix pages | definition/method | same; page-specific column window | HOLD; skipped; no matrix cells read |
| RR-H4A0-004 | `EPA_YEARBOOK_1968`, `a8d3fa70…5716` | 367 | consumption table continuation | measurement definition | same | HOLD; native text inadvertently opened before routing check; no image/value/candidate use; request remains unapproved |
| RR-H4A0-005 | `EPA_YEARBOOK_1973`, `729a2d5f…6a71` | 18, 92, 249, 251, 253, 305, 306, 400, 408 | late-year hints in otherwise relevant sections | none until reviewed | same | HOLD; skipped |
| RR-H4A0-006 | `EPA_YEARBOOK_1975`, `71abf03d…d202` | 255, 256, 258, 345 | late-year hints | none until reviewed | same | HOLD; skipped |
| RR-H4A0-007 | `EPA_YEARBOOK_1978`, `12bfc2b5…47bc` | 207, 253, 300, 372, 379 | late-year hints near D09/D10 sections | none until reviewed | same | HOLD; skipped |
| RR-H4A0-008 | 1956/1957/1960/1968 yearbooks | selected non-HOLD pages | second independent transcription of the four D08 numeric candidates | value admission | a reviewer independent of the implementation role, with page image + row/column + hash | NOT_RUN |
| RR-H4A0-009 | 1957/1960/1968 yearbooks | not located in selected pages | 1957 national and regional household counts; dated county/city → 20-region boundary crosswalk; 1957 regional housing stock | initial state | source + page + table + boundary basis + approver | NOT_FOUND in selected pages; broader search not requested |

## Not requested

- No whole-volume OCR, translation, embedding, or external upload.
- No re-download claimed as byte-identical to an official archive.
- No access to 1979–88 targets or sealed payloads.
- No HOLD page value extraction before a matching SHA + page + column + year + purpose + approver
  record exists.
