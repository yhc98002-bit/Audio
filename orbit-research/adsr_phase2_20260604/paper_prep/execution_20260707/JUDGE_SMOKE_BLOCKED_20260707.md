# Judge Smoke Blocked

Status: **BLOCKED**

## What Happened

- Original smoke: `paper_prep/judge_raw/smoke_10clip_20260706.jsonl`
  - Model: `qwen3.5-omni-plus`
  - Result: `FAIL`, 8/10.
  - The two misses were expected-negative clips with non-trivial detector values
    (`vocal_energy_ratio` 0.14929 / 0.11083; PANNs 0.18032 / 0.08641).
- Repaired smoke manifest:
  `paper_prep/execution_20260707/judge_smoke_manifest_repaired.csv`
  - Built from extreme positive and low-Demucs negative examples.
- Repaired Plus smoke:
  `paper_prep/execution_20260707/judge_smoke_repaired_stdout.json`
  - Result: `FAIL`, 6/10.
- Repaired Flash fallback smoke:
  `paper_prep/execution_20260707/judge_smoke_repaired_flash_stdout.json`
  - Model selected by `DASHSCOPE_MODEL=qwen3.5-omni-flash`.
  - Result: `FAIL`, 6/10.

## Decision

Do not run scale A′/B′ judge calls. This follows the guide's smoke rule:
the judge must pass 10/10 before real judging, and the specified fallback also
failed.

## Needed Human Decision

PI/manual review must decide whether the repeated expected-negative misses are:

- true vocal content missed by Demucs,
- judge over-calling instrumental audio as vocal,
- or an unsuitable smoke-set construction problem.

Until then, judge outputs are not used as gate evidence.
