# A-Prime Stratified-500 Judge Result

`JUDGE_500_STATUS = COMPLETE`

Apparent and judge-calibrated Label-A estimates are reported separately from detector estimates. The nominal 500 rows deduplicate to 493 unique audio hashes before inference and estimation. Equal manifest weights are used because the frozen manifest does not record unequal inclusion probabilities; bootstrap strata preserve corpus, source family, and request direction.

| Group | Rows | Apparent voice | Calibrated voice | Apparent Label-A violation | Calibrated Label-A violation |
|---|---:|---:|---:|---:|---:|
| all=all | 493 | 0.916836 | 0.917257 | NA | NA |
| requested_vocal=0 | 146 | 0.719178 | 0.697981 | 0.7191780821917808 | 0.6979809869846652 |
| requested_vocal=1 | 347 | 1.000000 | 1.000000 | 0.0 | 0.0 |
