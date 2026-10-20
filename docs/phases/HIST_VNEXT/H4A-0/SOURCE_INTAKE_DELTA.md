# H4A-0 source intake delta

Run: 2026-10-20. This is a declaration and gap record, not a historical PASS.

## Inputs actually read

| Input | Read level | Result |
|---|---|---|
| `batch01_20261016/{README,manifest,page_index,QA_REPORT,DEFERRED_ARCHIVES}` and batch01 candidates/exposure metadata | metadata | 4 PDFs, 3 works; all secondary analysis; no numerical value use |
| `batch02_20261020/{README,TABLE_LOCATOR,D08_NOTES,manifest,page_index,QA_REPORT,EXPOSURE_AND_ACCESS,existing_anchor_metadata}` | metadata | 7 yearbooks, 3,553 PDF pages, 368 selected pages, 70 groups |
| 1956 PDF 14–21, 279–281 | native text; image check for 20 and 279 | population 1957-01-01 and 1956 year-end housing candidates |
| 1957 PDF 18–23, 349–351, 379–388 | native text; image check for 21 and 349 | population/housing reprints and D08 definitions |
| 1960 PDF 19–30 (excluding HOLD 23, 27), 370–374 (HOLD 371, 372 text was inadvertently opened; no image/value use), 469–475 | native text; no image check | 1960 census/household definitions only; no 1957 backfill |
| 1960 PDF 401–402 | native text | 1959 IO method: 96→26 branches, A/B import treatment, direct coefficients vs inverse matrix |
| 1973 PDF 94–97 | native text | one 1972 consolidated IO matrix across four continuation pages |
| 1957 PDF 418–423 | native text | devizaforint, border parity, CPI 1956→1957 method break, consumption coverage |
| 1960 PDF 539–546 | native text | trade border parity and household-survey sample definition |
| 1968 PDF 272, 350–352, 366–377 (HOLD 367 text was inadvertently opened; no image/value use) | native text | trade, per-capita consumption, CPI and price tables |
| 1978 PDF 370 | native text | comparison-price basis change 1968 → 1976 |

Not opened as images or used for values: batch02 HOLD pages 1956/92,163,166,195,223;
1957/17,72,153,206,243; 1960/23,27,371,372,405,409,413; 1968/191,193,229,367;
1973/18,92,249,251,253,305,306,400,408; 1975/255,256,258,345; 1978/207,253,300,372,379.
**Exception:** native text of 1960/371, 1960/372 and 1968/367 was inadvertently opened during
metadata exploration before the routing check. No image, value, candidate, or admission used
them. See the HOLD disclosure below.

## Integrity evidence

```
python3 -B data/private/hist_vnext_sources/batch01_20261016/tools/verify_intake.py data/private/hist_vnext_sources/batch01_20261016
PASS: 112 hashed files; 4 original PDFs; 89 native pages; 83 OCR pages; 0 admitted excerpts.

python3 -B data/private/hist_vnext_sources/batch02_20261020/tools/verify_intake.py data/private/hist_vnext_sources/batch02_20261020
PASS: 1943 hashed files; 7 originals; 3553 page metadata rows; 368 selected/OCR pages; 70 groups; 0 admitted value records.
```

These are package-integrity results. They are not statistical or historical admission.

## Rights split

`access_register.json` records four separate questions per source:

1. local review of metadata/targeted non-HOLD pages: allowed by the 2026-10-20 workflow instruction;
2. numerical value reuse: **not** allowed; file-specific rights were not re-checked;
3. external model upload: not allowed;
4. redistribution: not allowed.

`RightsSpec.license_status` remains `unknown` for all 11 sources. Workflow authorization is not
a copyright licence. No EPA/KSH site licence is transferred to the user-supplied scans.

## HOLD disclosure

During exploratory metadata work the implementation role opened the **native text** of three
pages that the page index marks `YEAR_HINT_HOLD_NO_DEFAULT_READ`: 1960/371, 1960/372, 1968/367.
The routing check happened after that dump. No page image was opened, no value was transcribed,
and no candidate or admission uses those pages. The event is logged as H4A0-LOG-002/003 in
`access_register.json` and in `REPORT.md#hold-disclosure`. This is a procedural deviation, not a
data use. It does not create a HOLD approval. Consequence: those pages cannot be treated as
unseen, and no blind-holdout or retrospective approval may be inferred. They are excluded from
every candidate and from `APPROVED_INPUT_SET`.

## Candidate result

- 14 candidate declarations.
- 0 admitted values.
- 11 candidate-only items (rights/value-use gate not passed).
- 3 blocked items: no 1957 household table, no regional boundary crosswalk, sample households
  cannot stand in for national households.
- `APPROVED_INPUT_SET.json` contains empty `initial_state_inputs`, `measurement_inputs`, and
  `assumption_inputs`.

Canonical JSON:

- `history/HIST_VNEXT/h4_sources/sources.json`
- `history/HIST_VNEXT/h4_sources/access_register.json`
- `config/initial_state/hist_vnext_h4_v1/candidate_overlay.json`
- `history/HIST_VNEXT/h4_sources/shared_observations.json`
