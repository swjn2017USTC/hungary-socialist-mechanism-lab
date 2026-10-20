# H4A-0 anchor crosswalk

Canonical JSON: `config/initial_state/hist_vnext_h4_v1/anchor_crosswalk.json`.

## Coverage

| Check | Result |
|---|---|
| Legacy anchor count | 63 |
| Population / household / dwelling | 21 / 21 / 21 |
| Exact one-to-one anchor IDs | 63 / 63 |
| Legacy snapshot preserved | 63 / 63 |
| Original xls path exists | 63 / 63 |
| Recomputed SHA equals legacy SHA | 63 / 63 |
| `DATA_MANIFEST_v1` initial-state artifact SHA matches | 63 / 63 |
| New 1957 candidate linked | 43 anchors (21 population + 21 household-definition witness + 1 national dwelling) |
| `runtime_connected=true` | 0 |

The xls files were hashed, **not opened for values**. No legacy registration was rewritten.

## Verdict by family

| Family | H4A-0 result | Why |
|---|---|---|
| Population, national (`*_00`) | blocked | 1957-01-01 national candidate exists (1956 p20 + 1957 p21 reprint), but value-use rights and a second independent transcription are missing |
| Population, regional (01–20) | blocked | printed counties and county-status cities have no dated mapping to the 20 model regions; summing or proportional splitting would invent a distribution |
| Household, all 21 | blocked | no 1957 national/regional household table located in the selected pages; 1960 census/survey definitions are later-period witnesses only |
| Dwelling, national (`*_00`) | blocked | 1956-12-31 stock candidate exists (1956 p279 + 1957 p349 reprint), but it is partly estimated, rounded to 1000, and lacks value-use rights |
| Dwelling, regional (01–20) | blocked | no 1957 regional housing-stock observation; regional construction flows are not stocks |

## Legacy semantics preserved

Every record keeps:

- `legacy_record` verbatim (including `observation_at=1960-01-01`,
  `legacy_initial_at=1960-01-01`, `legacy_evidence_status=literature_proxy`,
  `source_evidence_kind=proxy`, `classification=blocked`);
- the original `artifact_id` and `DATA_MANIFEST_v1` path/SHA/grade/evidence status;
- `h4_classification=blocked` and `admission_status=blocked`;
- `runtime_connected=false` and the actual consumer evidence.

`grep` on 2026-10-20 found no `src/` consumer of `anchor_crosswalk.json` or of
`population_anchor` / `household_anchor` / `dwelling_anchor`. The observed consumers are the H1A
audit (`history/HIST_VNEXT/sources/admission.py:audit_h1a`) and
`tests/test_hist_source_admission.py`. The new crosswalk is therefore a declaration, not a
runtime state source.

## Numeric candidate boundary

- National population: rounded thousand value with an exact footnote; the value is held only in
  the private transcript. It is one observation with two print witnesses, not two independent
  observations.
- National housing stock: 1956-12-31 stock is partly estimated and rounded to 1000; the value is
  held only in the private transcript. The later 1957 stock row is a flow result and MUST NOT be
  moved into the 1957-01-01 initial state.
- Regional population and housing remain blocked. No 0.5 rounding tolerance, interpolation, or
  proportional split was introduced.

## H4A-1 availability

Available after this step: a reviewed candidate path for national population and national
housing, plus explicit regional/household gaps. **Not available:** any admitted initial-state
value. H4A-1 cannot consume these candidates without a later rights/value-use decision and a
second independent transcription.
