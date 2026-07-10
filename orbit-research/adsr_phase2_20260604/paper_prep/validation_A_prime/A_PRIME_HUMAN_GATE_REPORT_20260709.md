# A-prime Amended Human Gate Report

`A_PRIME_STATUS = AWAITING_RATINGS`

- Abstain policy: `report`.
- Regenerated primary rows excluded: 0.
- Real ratings complete: false.

| Gate set | Label B matches/decided | Label B rate | Label A matches/decided | Label A rate |
|---|---:|---:|---:|---:|
| rare_basin_48 | 0/0 | nan | 0/0 | nan |
| detector_disagreement_112 | 0/0 | nan | 0/0 | nan |
| agreement_spotcheck_30 | 0/0 | nan | 0/0 | nan |
| stratified_random_500 | 0/0 | nan | 0/0 | nan |


The stratified 500 supplies a global Wilson bound and is not part of the pass
shape. Label B is the paper endpoint; Label A is a reported detector construct
sensitivity. A PASS is forbidden until all rows carry non-synthetic human/PI
rating provenance.

```json
{
  "abstain_policy": "report",
  "complete_real_ratings": false,
  "constructs": {
    "label_a": {
      "agreement_spotcheck_30": {
        "abstains": 30,
        "decided": 0,
        "match_rate": NaN,
        "matches": 0,
        "rows": 30,
        "wilson_high": NaN,
        "wilson_low": NaN
      },
      "detector_disagreement_112": {
        "abstains": 112,
        "decided": 0,
        "match_rate": NaN,
        "matches": 0,
        "rows": 112,
        "wilson_high": NaN,
        "wilson_low": NaN
      },
      "rare_basin_48": {
        "abstains": 48,
        "decided": 0,
        "match_rate": NaN,
        "matches": 0,
        "rows": 48,
        "wilson_high": NaN,
        "wilson_low": NaN
      },
      "stratified_random_500": {
        "abstains": 500,
        "decided": 0,
        "match_rate": NaN,
        "matches": 0,
        "rows": 500,
        "wilson_high": NaN,
        "wilson_low": NaN
      }
    },
    "label_b": {
      "agreement_spotcheck_30": {
        "abstains": 30,
        "decided": 0,
        "match_rate": NaN,
        "matches": 0,
        "rows": 30,
        "wilson_high": NaN,
        "wilson_low": NaN
      },
      "detector_disagreement_112": {
        "abstains": 112,
        "decided": 0,
        "match_rate": NaN,
        "matches": 0,
        "rows": 112,
        "wilson_high": NaN,
        "wilson_low": NaN
      },
      "rare_basin_48": {
        "abstains": 48,
        "decided": 0,
        "match_rate": NaN,
        "matches": 0,
        "rows": 48,
        "wilson_high": NaN,
        "wilson_low": NaN
      },
      "stratified_random_500": {
        "abstains": 500,
        "decided": 0,
        "match_rate": NaN,
        "matches": 0,
        "rows": 500,
        "wilson_high": NaN,
        "wilson_low": NaN
      }
    }
  },
  "excluded_regenerated_primary": 0,
  "mechanical_pass": false,
  "status": "AWAITING_RATINGS"
}
```
