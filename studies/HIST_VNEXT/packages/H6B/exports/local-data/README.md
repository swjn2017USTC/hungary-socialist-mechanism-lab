# HIST_VNEXT H6B research package

This export is a **package-completeness audit**, not a claim that any
historical hypothesis is SUPPORTED.  Each card separately reports
technical, structural and historical status.  `research_package_complete`
is derived only from the eleven checks; historical `UNIDENTIFIED`/`NOT_RUN`
does not by itself reduce package completeness.

- mode: `local-data`
- cards: 11
- complete: 3 (M01, M02, M04)
- blocked: 8 (M03, M05, M06, M07, M08, M09, M10, M11)
- legacy declared metrics preserved: 41
- package digest: `f4032201ed4f7b79e6f1c8305b1b46f1db6bc6547417fd46652bd4ef1d0b09c4`

## Cards

| card | package | technical | structural | historical | blocking checks |
|---|---|---|---|---|---|
| M01 | complete | PASS | import_cut=CONDITIONAL_CARRIED_REFERENCE_EFFECT; income_cut=CONDITIONAL_CARRIED_REFERENCE_EFFECT; welfare_cut=UNIDENTIFIED | UNIDENTIFIED | none |
| M02 | complete | PASS | FALSIFICATION_MET_SYNTHETIC_WINDOW | UNIDENTIFIED | none |
| M03 | blocked | PASS | PASS_SYNTHETIC | UNIDENTIFIED | paired_control, first_stage_checked, accounting_checked, sensitivity_or_reason_not_run, reproduction_bundle |
| M04 | complete | PASS | FIRST_STAGE_SUPPORTED_WITH_CAPACITY_CEILING | UNIDENTIFIED | none |
| M05 | blocked | NOT_RUN | NOT_RUN | UNIDENTIFIED | experiment_declared, paired_control, first_stage_checked, accounting_checked, negative_control, metrics_generated, sensitivity_or_reason_not_run, counterevidence, reproduction_bundle |
| M06 | blocked | BLOCKED | NOT_RUN | UNIDENTIFIED | experiment_declared, paired_control, first_stage_checked, accounting_checked, negative_control, metrics_generated, sensitivity_or_reason_not_run, reproduction_bundle |
| M07 | blocked | BLOCKED | NOT_RUN | UNIDENTIFIED | experiment_declared, paired_control, first_stage_checked, accounting_checked, negative_control, metrics_generated, sensitivity_or_reason_not_run, reproduction_bundle |
| M08 | blocked | NOT_RUN | NOT_RUN | UNIDENTIFIED | experiment_declared, paired_control, first_stage_checked, accounting_checked, negative_control, metrics_generated, sensitivity_or_reason_not_run, counterevidence, reproduction_bundle |
| M09 | blocked | PASS | SYNTHETIC_ENGINEERING_PROFILE | NOT_RUN | negative_control |
| M10 | blocked | NOT_RUN | NOT_RUN | UNIDENTIFIED | experiment_declared, paired_control, first_stage_checked, accounting_checked, negative_control, metrics_generated, sensitivity_or_reason_not_run, counterevidence, reproduction_bundle |
| M11 | blocked | NOT_RUN | NOT_RUN | UNIDENTIFIED | experiment_declared, paired_control, first_stage_checked, accounting_checked, negative_control, metrics_generated, sensitivity_or_reason_not_run, counterevidence, reproduction_bundle |

## Safety

Only JSON and Markdown are exported.  No original source, OCR, translated text,
raw table, target, HOLD, reserved or private file is opened, copied or
redistributed.  Source rights are reference-only metadata.
