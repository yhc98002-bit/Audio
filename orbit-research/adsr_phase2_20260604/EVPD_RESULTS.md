# EVPD Results (Batch 2 Stage 3)

Test = held_out (256 prompts / 2048 cands); presence prevalence(test)=0.5757. Threshold tuned on val only.

## Held-out presence-prediction metrics

| model | AUC | AUPRC | rec@P.8 | prec@R.8 | bal-acc |
|---|---|---|---|---|---|
| scalar_logit_s0.9 | 0.6845 | 0.7186 | 0.1086 | 0.6558 | 0.6565 |
| melsumm_logit_s0.9 | 0.8717 | 0.8955 | 0.8736 | 0.8304 | 0.79 |
| melsumm_gbdt_s0.9 | 0.8438 | 0.8779 | 0.7651 | 0.7928 | 0.7485 |
| cnn_s0.9 | 0.8105 | 0.8404 | 0.7176 | 0.7605 | 0.7279 |
| scalar_logit_s0.8 | 0.6959 | 0.7788 | 0.4394 | 0.6372 | 0.6526 |
| melsumm_logit_s0.8 | 0.9163 | 0.9337 | 0.9432 | 0.8874 | 0.8165 |
| melsumm_gbdt_s0.8 | 0.9046 | 0.9285 | 0.9143 | 0.8737 | 0.8054 |
| cnn_s0.8 | 0.8362 | 0.8736 | 0.7481 | 0.7676 | 0.739 |
| scalar_logit_s0.7 | 0.7403 | 0.785 | 0.5208 | 0.6946 | 0.6746 |
| melsumm_logit_s0.7 | 0.9404 | 0.9551 | 0.9542 | 0.931 | 0.8619 |
| melsumm_gbdt_s0.7 | 0.9379 | 0.9551 | 0.9517 | 0.9264 | 0.8572 |
| cnn_s0.7 | 0.8702 | 0.9015 | 0.8346 | 0.8245 | 0.7915 |
| melsumm_gbdt_fused | 0.938 | 0.955 | 0.9534 | 0.9203 | 0.8463 |
| cnn_fused_s987 | 0.898 | 0.9273 | 0.8838 | 0.8703 | 0.8027 |

## Type-error & survivor-set detection (ADSR-relevant)

```json
{
  "melsumm_gbdt_fused": {
    "type_error_detect_precision": 0.6139,
    "type_error_detect_recall": 0.6417,
    "type_error_true_n": 441,
    "type_error_flagged_n": 461,
    "restart_rate": 0.2251,
    "false_restart_rate": 0.0869,
    "false_restart_frac_of_restarts": 0.3861,
    "survivor_top1_prompts": 256,
    "survivor_top1_true_type_errors": 47,
    "survivor_top1_caught": 22,
    "survivor_top1_catch_rate": 0.4681
  }
}
```