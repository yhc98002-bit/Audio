# Decisive Construct Branch Report

`BRANCH_VERDICT = demucs_missing`

This packet selects a diagnostic branch; it is not A-prime validation.

- Contested Label-B decisions: 23/24.
- Qwen matches to Label B: 21.
- Demucs matches to Label B: 2.
- Label-A/Label-B disagreement: 0.0.
- Obvious-control matches: 5/6.
- Real ratings complete: true.

## Per-Bucket Breakdown

| Bucket | N | A yes/no/unsure | B voice/no-voice/unsure | Demucs matches B | Qwen matches B | A/B disagreements |
|---|---:|---:|---:|---:|---:|---:|
| failed_smoke_negative_4 | 4 | 2/1/1 | 2/1/1 | 1 | 2 | 0/3 |
| judge_yes_demucs_no_20 | 20 | 19/0/1 | 19/1/0 | 1 | 19 | 0/19 |
| obvious_agreement_control_6 | 6 | 4/1/1 | 4/2/0 | 5 | 5 | 0/5 |
| rare_basin_6 | 6 | 5/1/0 | 6/0/0 | 1 | 0 | 1/6 |
| threshold_near_6 | 6 | 5/1/0 | 5/1/0 | 0 | 6 | 0/6 |

```json
{
  "branch_verdict": "demucs_missing",
  "bucket_breakdown": {
    "failed_smoke_negative_4": {
      "demucs_matches_label_b": 1,
      "label_a_b_decided": 3,
      "label_a_b_disagreements": 0,
      "label_a_no": 1,
      "label_a_unsure": 1,
      "label_a_yes": 2,
      "label_b_unsure": 1,
      "label_b_voice_absent": 1,
      "label_b_voice_present": 2,
      "qwen_matches_label_b": 2,
      "rows": 4
    },
    "judge_yes_demucs_no_20": {
      "demucs_matches_label_b": 1,
      "label_a_b_decided": 19,
      "label_a_b_disagreements": 0,
      "label_a_no": 0,
      "label_a_unsure": 1,
      "label_a_yes": 19,
      "label_b_unsure": 0,
      "label_b_voice_absent": 1,
      "label_b_voice_present": 19,
      "qwen_matches_label_b": 19,
      "rows": 20
    },
    "obvious_agreement_control_6": {
      "demucs_matches_label_b": 5,
      "label_a_b_decided": 5,
      "label_a_b_disagreements": 0,
      "label_a_no": 1,
      "label_a_unsure": 1,
      "label_a_yes": 4,
      "label_b_unsure": 0,
      "label_b_voice_absent": 2,
      "label_b_voice_present": 4,
      "qwen_matches_label_b": 5,
      "rows": 6
    },
    "rare_basin_6": {
      "demucs_matches_label_b": 1,
      "label_a_b_decided": 6,
      "label_a_b_disagreements": 1,
      "label_a_no": 1,
      "label_a_unsure": 0,
      "label_a_yes": 5,
      "label_b_unsure": 0,
      "label_b_voice_absent": 0,
      "label_b_voice_present": 6,
      "qwen_matches_label_b": 0,
      "rows": 6
    },
    "threshold_near_6": {
      "demucs_matches_label_b": 0,
      "label_a_b_decided": 6,
      "label_a_b_disagreements": 0,
      "label_a_no": 1,
      "label_a_unsure": 0,
      "label_a_yes": 5,
      "label_b_unsure": 0,
      "label_b_voice_absent": 1,
      "label_b_voice_present": 5,
      "qwen_matches_label_b": 6,
      "rows": 6
    }
  },
  "category_counts": {
    "failed_smoke_negative_4": 4,
    "judge_yes_demucs_no_20": 20,
    "obvious_agreement_control_6": 6,
    "rare_basin_6": 6,
    "threshold_near_6": 6
  },
  "contested_label_b_decided": 23,
  "contested_rows": 24,
  "control_decided": 6,
  "control_matches": 5,
  "demucs_matches_label_b": 2,
  "judge_matches_label_b": 21,
  "label_a_b_decided": 22,
  "label_a_b_disagreement_rate": 0.0,
  "provenance_counts": {
    "human": 0,
    "pi": 42
  },
  "real_ratings_complete": true
}
```
