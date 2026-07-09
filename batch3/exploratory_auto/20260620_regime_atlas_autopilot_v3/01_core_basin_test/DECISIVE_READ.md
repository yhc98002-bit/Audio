# DECISIVE READ — E2 tail large-N BoN (facts-only)

- prompts: 32 | draws: 8192 | N/prompt up to 256
- **fraction 0-clean (p≈0 candidate): vocal 0.0 (0/17) | instrumental 0.0 (0/15)**
- detector (Demucs↔PANNs) agreement overall: 0.515

## 0-clean prompts (candidate basins; Wilson p upper-bound)

| prompt | req | n | clean | p_hat | p_ci | D↔P agree |
|---|---|---|---|---|---|---|

## BoN curve (fixed-N, analytic from p_hat)

| group | S_1 | S_2 | S_4 | S_8 | S_16 | S_32 | S_64 | S_128 | S_256 |
|---|---|---|---|---|---|---|---|---|---|
| vocal | 0.0862 | 0.1611 | 0.2839 | 0.4543 | 0.6389 | 0.7968 | 0.9144 | 0.9779 | 0.9968 |
| instrumental | 0.3583 | 0.5779 | 0.8058 | 0.9509 | 0.9953 | 0.9999 | 1.0 | 1.0 | 1.0 |

_Source: `ledgers/bon256_w*.jsonl`, `decisive_read.py`. Facts only; PI maps to claims._