# P06 Status Reconciliation — Crosswalk Overlay

**Phase:** P07A1  
**Purpose:** Document the identity mapping between old and new tables in the P06 final report. This file is an **overlay** that annotates the frozen `docs/phases/P06_FINAL_REPORT.md` without modifying it. It does not overwrite any frozen report content.

---

## 1. Old vs New Table Identity Crosswalk

The P06 final report contains both old-style and new-style tables. The identities are:

### 1.1 Consumption / Household Reproduction Table

| Attribute | Old Identity | New Identity |
|---|---|---|
| Location in P06 report | `docs/phases/P06_FINAL_REPORT.md` lines 11–73, "First result: consumption" | `docs/phases/P06_FINAL_REPORT.md` same section |
| Table type | Markdown table, 19 annual rows (1960–1978) | N/A — the report already shows the new style |
| Variable name | `household_consumption` | `annual_household_consumption_index` (from `reproduction_table.py:165–178`) |
| Normalization base | Model's own 1960 = 100 (exact by construction) | Same — index is self-normalized |
| Crosswalk grade | Previously described as `first and only` | Revised to `normalized_index` per v2 crosswalk grade |
| Digest (C0 replay) | `f75ba7767eaf5987eb876413f973e07f13ece4e11906cdd14cbd3b08fbf8ba79` | Same run, different run_id: `outputs/p06-reproduction-table-widened-final2/` |
| Digest (C1 trade) | Same section | Trade scenario digest `6362001deaf055af6c005acc7d6fc6c4bbaf05b7f417b0c3bec5b7c25b8508b0` |

**Note:** The P06 report says "first and only" in lines 11–15. This language predates the v2 crosswalk system. The overlay updates this to the correct `normalized_index` grade. The frozen report language is preserved verbatim; only the crosswalk annotation is updated here.

### 1.2 Graded Crosswalk Table

| Grade | Old Count (P06 report) | New Count (v2 crosswalk) | Notes |
|---|---|---|---|
| `mapped_like_for_like` | 0 | 0 | No like-for-like commodity match |
| `normalized_index` | 1 (consumption) | 1 (consumption) | Same variable, correctly graded |
| `allocation_assumed` | 0 | 0 | No rights-cleared regional allocation series found |
| `no_counterpart` | 13 | 11 | Reduced because two variables now have v2 metric specs with `no_counterpart` grade |
| `blocked` | 0 | 1 | Treasury payable cash rations exports — one new blocked entry |

**Changes from old to new:**
- `trade_export_volume_index`: old `no_counterpart` → new `blocked` (Treasury cash rationing documented)
- `trade_import_volume_index`: retained as `no_counterpart` (imports remain zero throughout)
- `industrial_electricity`, `industrial_crude_steel`, `industrial_fertilizer`, `industrial_cement`, `industrial_television`: old `no_counterpart` → these now have formal v2 metric specs with `no_counterpart` fidelity grade (not silently upgraded)
- `ag_cereals`, `ag_wheat`, `ag_maize`: old `no_counterpart` → retained (F2 single agricultural commodity, no crop split)
- `gdp`: old `no_counterpart` → retained (no GDP aggregate in model)
- `industrial_output`: old `no_counterpart` → retained
- `investment`: old `no_counterpart` → retained

### 1.3 Frozen Gate Table

| Gate/metric | Old value (P06 report) | New value | Notes |
|---|---|---|---|
| Liveness | 0.1116 | 0.1116 | Unchanged |
| Delivered/funded g03 | 0.489 | 0.489 | Unchanged |
| Delivered/funded g15 | 0.120 | 0.120 | Unchanged |
| Delivered/funded g16 | 0.199 | 0.199 | Unchanged |
| Treasury cash zero tick | tick 17–18 | tick 17–18 | Unchanged |
| Tail expired services share | ~0.94 | ~0.94 | Unchanged |
| T1 production last-10 mean | 28,074 | 28,074 | Unchanged |
| T2 household-consumption last-10 mean | 1,668 | 1,668 | Unchanged |
| Accounting invariants | PASS | PASS | Unchanged |

---

## 2. Run Identity Crosswalk

| Run ID | Scenario | Seed | Interval | Ticks | Digest (SHA-256) | C0/C1 label |
|---|---|---|---|---|---|---|
| `codex-audit-vnext-20261011/C0` | `historical_f2_replay` | 1729 | 1957Q1–1985Q4 | 116 | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` | C0 |
| `codex-audit-vnext-20261011/C1` | `historical_f2_trade_scenario` | 1729 | 1957Q1–1985Q4 | 116 | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` | C1 |
| `p06-reproduction-table-widened-final2/` | `historical_f2_replay` | 1729 | 1957Q1–1978Q4 | ~88 | `6362001deaf055af6c005acc7d6fc6c4bbaf05b7f417b0c3bec5b7c25b8508b0` | reproduction only |

**Note:** The reproduction run digest differs from the C0 full run digest because:
1. The reproduction table stops at 1978Q4 (not 1985Q4)
2. It uses a different output directory structure
3. It applies the crosswalk normalization step

The reproduction run is NOT a replacement for C0; it is a diagnostic comparison against admitted targets up to 1978.

---

## 3. Scenario and Scenario Hash Crosswalk

| Scenario ID | Scenario Hash (SHA-256 of spec) | Location | Notes |
|---|---|---|---|
| `historical_f2_replay` | `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445` | C0 run | Matches `calibration/p06_clearance.json:8` |
| `historical_f2_trade_scenario` | `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90` | C1 run | Matches `calibration/p06_clearance.json:8` |
| `intermediate8` | N/A | Synthetic diagnostic runs | 8-good toy layer; NOT F2 |

---

## 4. Card SHA-256 Crosswalk (v1 frozen anchors)

| Card | v1 SHA-256 (frozen) | Stored in | Used in provenance DAG as |
|---|---|---|---|
| M1 | `7a3beaa4be817cfb745a163c579b0ec472fcfb3f55c8caaca7db15854c74352d` | `config/p06/cards/M1.json` | `v1_card:M1` node |
| M2 | `0da621e51ad436103ec3c76d820701cda84e8bb0c9cb79ef0947337856990589` | `config/p06/cards/M2.json` | `v1_card:M2` node |
| M3 | `06adefbd144800d1ff2afd10f5f73765f6e70339d1280ba002b434bb6e32f8ba` | `config/p06/cards/M3.json` | `v1_card:M3` node |
| M4 | `c9e70e5ca07bca8e7865f274dc052cb1ed5aed795787a9a07f16ec37fb5323ac` | `config/p06/cards/M4.json` | `v1_card:M4` node |
| M5 | `cdcbbfbd8d99b8b0d55f1afeaf564d2fac5cef3cd53d7058f75943af611bd879` | `config/p06/cards/M5.json` | `v1_card:M5` node |
| M6 | `047db0a8473f326c8a6a2609bc18ea42c24cb979a96f0a20cf254575dde5e6c6` | `config/p06/cards/M6.json` | `v1_card:M6` node |
| M7 | `f6383c8b16fa5f16e2517ec992da2524a2ba1eb31612ff4c542515f3d3399d90` | `config/p06/cards/M7.json` | `v1_card:M7` node |
| M8 | `f4761f7f7b3865e61d285ccdd058c91ee0cfd463964cb2b7c4b6f03e22dd0bd1` | `config/p06/cards/M8.json` | `v1_card:M8` node |
| M9 | `fa1b30703cda0009471e03cdf6b88b47d20a7ce525385adfdd554f595e55273c` | `config/p06/cards/M9.json` | `v1_card:M9` node |
| M10 | `c23d545b59432e6f9412c512824aba5af40cc242daaa4c65239c6f4ae129b880` | `config/p06/cards/M10.json` | `v1_card:M10` node |
| M11 | `c65318dc1d4c149d7d15b49db229c19768a282f5e6c59307197fe194d1c86887` | `config/p06/cards/M11.json` | `v1_card:M11` node |

**v1 schema SHA-256:** `e35d09887cfa853275feaf99fbe1e4f149c38ff5b0699533381390ba5a8d0be9` (frozen in `config/p06/mechanism_card.schema.json`)

---

## 5. P06 Clearance — Old vs New Structure

| Clearance Item | Old Result | New Status | Notes |
|---|---|---|---|
| 25 PASS / 4 WAIVED / 1 OPEN | Initial run exit=1 | 26 PASS / 4 WAIVED / 0 OPEN with `--with-runs` | Same 26 technical items |
| Digest check | Not executed initially | Verified: C0 `92f9ea0a…`, C1 `c4810481…` | Exact digests match |
| Bundle verify | N/A | C0 and C1 both `digest_matches=true`, `parameter_hash_matches=true` | |
| F2 H0 closure | exit=1, collapsed, liveness=0 | Unchanged — this is a real economic failure, not a test artifact | |
| Reproduction table | 38 annual rows, 18/18 informative years outside tolerance | Unchanged | |

---

## 6. Protected Identities (DO NOT MODIFY)

The following are preserved verbatim and must not be changed by any subsequent phase:

| Object | SHA-256 / Identity | Location |
|---|---|---|
| BASELINE.md | `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` | Root |
| config/research_contract.json | `6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82` | Root |
| .omp/config.yml (user dirty) | `e16efec36889a8f453779e1be1fa3e92988a1b49961e0db66e334962b9de5339` | .omp/ |
| uv.lock | `9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9` | Root |
| docs/phases/P06_FINAL_REPORT.md | git-tracked, not modified by this overlay | docs/phases/ |
| config/p06/cards/M*.json (v1) | SHA-256 per §4 above | config/p06/cards/ |
| C0 digest | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` | outputs/codex-audit-vnext-20261011/C0 |
| C1 digest | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` | outputs/codex-audit-vnext-20261011/C1 |

---

## 7. 11-Card Manifest Status Summary

| Card | v1 Status (P06) | P07A1 Status | Declared / Blocked Reason |
|---|---|---|---|
| M1 | UNIDENTIFIED (no verdict) | DECLARED | p04_coalition_prior and p04_observation_prior identified; ratchet design ready |
| M2 | UNIDENTIFIED | BLOCKED | F2 second economy empty; pending wiring |
| M3 | UNIDENTIFIED | BLOCKED | No labor hoarding state; pending labor identity |
| M4 | UNIDENTIFIED | BLOCKED | F2 second economy empty; pending wiring |
| M5 | UNIDENTIFIED | DECLARED | p04_coalition_prior and p04_information_prior identified; autonomy×hardness design ready |
| M6 | UNIDENTIFIED | BLOCKED | convertible_credit_envelope not in engine; pending P08D |
| M7 | UNIDENTIFIED | BLOCKED | National scalars not regional vectors; pending regional adapter |
| M8 | UNIDENTIFIED | DECLARED | Political probe feasible; negative control available |
| M9 | UNIDENTIFIED | BLOCKED | forecast_accuracy = capability (definition not error); pending pre-prediction tracking |
| M10 | UNIDENTIFIED | BLOCKED | P06 old arms REPORTED_ONLY; pending P08D factor decomposition |
| M11 | CONDITIONAL (structural) | BLOCKED | F1 g13 invalid for F2; pending M2/M5 prerequisite |

**No `research_package_complete` claimed for any card.**

---

## 8. Version and Digest Audit Trail

| Version Layer | Identity | Digest / Hash | Notes |
|---|---|---|---|
| P06 v1 card schema | `config/p06/mechanism_card.schema.json` | `e35d09887cfa…` | Superseded by v2 schema |
| P07A1 v2 card schema | `config/mechanisms/v2/mechanism_card.schema.json` | New file | Adds typed MetricSpec, supersedes pointer |
| supersedes index | `config/mechanisms/v2/supersedes.json` | New file | Maps M1–M11 to v1 SHA-256 |
| Evidence manifest | `studies/manifest.json` | New file | 11 records, DECLARED or BLOCKED |
| Study declarations | `studies/M01–M11/study_decl.json` | New files | Per-card stubs, no results |
| Provenance DAG | Built by `build_card_provenance()` | Computed at runtime | v1 SHA anchors + DAG edges |
| Crosswalk overlay | `docs/upgrade_review/evidence/P06_STATUS_RECONCILIATION.md` | New file | Does not overwrite frozen P06 report |
