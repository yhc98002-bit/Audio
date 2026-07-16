# BOLT Gate 1.5A Test Report

TEST_SUITE_STATUS = PASS

evidence: `tests/test_bolt_gate15a.py`, `gate15a_logs/test_focused_final.log`, `gate15a_logs/test_full_final.log`

## Final focused suite

Command:

```bash
module load anaconda3/2023.09
conda run -n audio-prm python -m pytest -q \
  orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/tests/test_bolt_gate15a.py
```

Result: **12 passed, 0 failed, 0 skipped** in `46.42 s` wall time.

The focused suite covers prompt-grouped balanced folds, shared-prefix and
completion-reserve accounting, all frozen continuation boundaries, MAP
optimizer stationarity at `1e-9`, outcome-free action selection, frozen
categorical encoding, encoded-audio recovery, terminal-report consistency,
held-out prompt exclusion in every model audit, and the exact 288-row
persisted-latent feature ledger.

## Final repository suite

Command:

```bash
module load anaconda3/2023.09
conda run -n audio-prm python -m pytest -q
```

Result: **355 passed, 0 failed, 0 skipped** in `206.81 s` wall time.

## Test sequence and correction

The pre-extraction focused suite passed 9 tests. After the first canonical
worker exposed the encoded-audio recovery defect, a new regression test was
added. Its first fixture was correctly rejected as near-silent; the fixture
was changed to valid two-second audio without weakening production validity
checks. The corrected 10-test suite passed before cross-fitting. Two terminal
output audits were then added, yielding the final 12-test focused result above.

Environment: `audio-prm`, Python `3.10.20`, torch `2.5.1+cu121`; frozen
environment hash
`d1c44cb0fec1fa4347ba3b0908cab561ebbbbba648026c57c0b79aeffb0df542`.
