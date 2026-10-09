# P06 mechanism-card preregistrations

These cards are pre-registrations from Annex A of `P06_EXECUTION_PLAN.md`; they contain no
results or verdicts. Each allows all five result categories and requires three deterministic
seed-bank replicates. Dependencies resolve through the frozen parameter registry's canonical
`artifact_id`; the six behavioural blocks remain UNIDENTIFIED.

| ID | Hypothesis | Calibrated-parameter dependencies |
|---|---|---|
| M1 | Social-contract ratchet: equal cuts provoke a larger response after a long improvement run. | `p04_coalition_prior`, `p04_observation_prior` |
| M2 | Soft budget plus investment hunger sustains systemic shortage independently of demand regime. | none |
| M3 | Full employment weakens enterprise discipline and feeds wage/hoarding feedback. | none |
| M4 | The second economy is net stabilising or net eroding for the formal system. | `p04_culture_prior` |
| M5 | Rising enterprise autonomy with persistent soft budgets yields efficiency gains and macro imbalance. | `p04_coalition_prior`, `p04_information_prior` |
| M6 | External debt lengthens the social contract and shifts its cost forward. | `p04_external_recipe_prior` |
| M7 | Uneven regional distribution of social-contract gains creates different stability paths. | `p04_opposition_prior`, `p04_coalition_prior` |
| M8 | Economic deterioration can strengthen administrative conservatism or the reform coalition. | `p04_coalition_prior`, `p04_observation_prior`, `p04_information_prior` |
| M9 | Stronger information capacity removes some shortage and planning error. | `p04_information_prior` |
| M10 | Subsidies, borrowing and CMEA terms postpone an external shock, potentially raising later fragility. | `p04_external_recipe_prior` |
| M11 | Department I investment and input priority crowd out Department II consumer availability. | none |

Load and validate the registered cards with `load_mechanism_cards(repository_root)`. That loader
rejects missing/duplicate card IDs, unknown dependency IDs and a SUPPORTED-only category list
for a card depending on an unidentified block.
