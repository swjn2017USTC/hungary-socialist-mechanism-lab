# P06 run report

P06 W1–W4 and W8 infrastructure/reporting are complete within the reproduction-scope boundary. W5–W7 remain OPEN: every available 1968Q1 checkpoint is `material-checkpoint-v3`, while the current fork loader requires v4. The measured 0.633-second refusal is not a political runtime measurement, so the plan’s runtime prerequisite and degradation ladder were not triggered. No arms were fabricated or simulated past 1985Q4.

The final report is [P06_FINAL_REPORT.md](P06_FINAL_REPORT.md). Three clearance items remain OPEN (`p06_1968_runs`, `p06_1973_runs`, `p06_political_runs`); the clearance command is expected to exit nonzero until compatible checkpoint evidence exists. The frozen reproduction gates remain failed except accounting and diagnostic T3. No parameter block is identified; calibrated remains zero.

Validation: `.venv/bin/ruff check src tests` clean; `.venv/bin/python -m pytest -q -p no:cacheprovider` → 404 passed. Exact evidence is recorded in `outputs/p06-clearance/pytest.json`. Reproducibility bundle CLI assembly/verification and target-loading window refusals have tests.

W5–W7 intervention definitions are registered but their metrics, hashes, and run dispositions remain unmeasured. W2 has 24 original OAT arms plus 48 replicate arms; W3 has 18 original Morris arms plus 36 replicate arms over three seeds. Morris is exploratory only. H4 remains conditional at residual `1.3666269856210904e-6` against the unchanged `1e-6` cutoff.
