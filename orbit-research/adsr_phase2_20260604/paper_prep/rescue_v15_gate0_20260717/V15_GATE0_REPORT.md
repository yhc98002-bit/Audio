# ACE-Step v1.5 BOLT Gate 0

MODEL_PROVENANCE_STATUS = PASS
ENVIRONMENT_STATUS = PASS
STATE_CONTRACT_STATUS = FAIL
RESUME_EQUIVALENCE_STATUS = FAIL
CONDITION_SWITCH_STATUS = FAIL
FORK_STATUS = FAIL
ACTUAL_NFE_STATUS = PASS
TRUE_ROLLOVER_STATUS = FAIL
COMPLETION_RESERVE_STATUS = FAIL
V15_GATE0_STATUS = FAIL_ESCALATED
TEST_SUITE_STATUS = FAIL

MODEL_IDENTITY = ACE-Step/acestep-v15-xl-sft@d1ca0bc96e29cd46435219ceb4f8e3a13a8eaf50 (config=acestep-v15-xl-sft, is_turbo=false)
MEASURED_FULL_GENERATION_NFE = 50 transformer forward calls; 50 inline Euler updates; 0 scheduler-object calls

## Evidence

evidence: `V15_MODEL_PROVENANCE.md`, `V15_MODEL_CHECKSUMS.tsv`, `V15_PROVENANCE.json`
evidence: `V15_ENVIRONMENT_REPORT.md`, `V15_LOGIN_ENVIRONMENT.json`
evidence: `V15_STATE_CONTRACT.md`, `V15_RESUME_EQUIVALENCE.csv`, `V15_TERMINAL_DIAGNOSIS.json`
evidence: `V15_CONDITION_SWITCH.csv`, `V15_FORK_CALIBRATION.csv`, `V15_FORK_FROZEN.json`
evidence: `V15_NFE_ACCOUNTING.csv`, `V15_TRUE_ROLLOVER_REPORT.md`
evidence: `V15_TEST_RESULTS.json`, `V15_APPEND_ONLY_LEDGER.jsonl`, `V15_CHECKSUMS.tsv`

## Commits and tests

- Seed/preregistration commit: `788e366`.
- Harness commit: `6465750`.
- Provenance commit: `f6883b1`.
- Offline-cache repair commit: `5e0a994`.
- Native-output repair commit: `abe628b`.
- Evidence-base commit at construction: `abe628bec1624df8bf6faf3719215b6c4887a923`.
- Focused tests: `exit=0; ....                                                                     [100%]`.
- Repository suite: `exit=2; !!!!!!!!!!!!!!!!!!! Interrupted: 16 errors during collection !!!!!!!!!!!!!!!!!!!`.

## Bounded terminal diagnosis

The second bounded state-harness attempt failed before the first continuation transformer call because native `generate_audio` requires the timestep suffix as a tensor, while the harness supplied a list. Per B1, no second repair, 64-control run, rollover run, or scientific axis was launched.

## Genuine PI decisions

1. Authorize the targeted tensor-timestep continuation fix and a fresh bounded v1.5 Gate-0 dispatch.
2. Revert the tempo axis to ACE-Step v1 primitives already proven.

No constraint-axis experiment, tempo experiment, policy training, or vocal/instrumental scientific claim was run. Legacy BOLT and W2 evidence were not modified.
