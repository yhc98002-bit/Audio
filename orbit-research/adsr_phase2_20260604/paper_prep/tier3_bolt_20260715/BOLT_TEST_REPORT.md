# BOLT Test Report

TEST_SUITE_STATUS = PASS

## Final commands

Environment: Python `3.10.20`, torch `2.5.1+cu121`, CUDA build `12.1`, `w2-torch251` environment.

| Scope | Command | Passed | Failed | Skipped | Runtime |
|---|---|---:|---:|---:|---:|
| Focused BOLT, final | `python -m pytest -q paper_prep/tier3_bolt_20260715/tests` | 27 | 0 | 0 | 80.81 s |
| Canonical repository, final | `python -m pytest -q` | 355 | 0 | 0 | 331.24 s |

The canonical invocation uses `pyproject.toml` test paths (`tests/`). The focused invocation separately covers the BOLT-local tests because those tests intentionally live with the bounded Gate 0/1 artifact package.

## Recovered test failure

The first post-audit focused run reported 26 passed and one failed test in 85.80 seconds. The failed test incorrectly required a zero-CQS, nonzero-option oracle to stop at 45 NFE. The implementation correctly selected two estimated-positive leaves under the 90-NFE budget. The test was corrected to assert the scientific invariant: at least one completed leaf and total cost within `[45, 90]`. No experiment output, threshold, or result changed.

Final logs:

- `paper_prep/tier3_bolt_20260715/BOLT_FOCUSED_TESTS_POST_AUDIT_V2.log`
- `paper_prep/tier3_bolt_20260715/BOLT_FULL_REPOSITORY_TESTS_FINAL.log`

Covered regressions include state serialization, separate-process resume, exact resume equivalence, conditioning-hash change and fallback rejection, fixed-seed fork determinism and cross-seed diversity, transformer-call and shared-prefix accounting, two-abort rollover, completion reserve, zero-score selection, duplicate/missing keys, prompt leakage, seed collision, crash/resume idempotence, terminal-leaf deduplication, tree-knapsack accounting, and static/oracle separation.
