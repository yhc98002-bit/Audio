# B-prime Amended Human Gate Report

`B_PRIME_STATUS = AWAITING_RATINGS`

- Primary endpoint: `quality_preference` from the first presentation of each pair.
- Reversed 24-pair presentations: reliability only, never extra votes.
- Primary criterion: one-sided 95% score lower bound > 0.40.
- Abstain policy: `report`.

| Endpoint | Method/decided | Rate | One-sided lower | Primary NI pass | Ties-half | Ties-against |
|---|---:|---:|---:|---:|---:|---:|
| quality_preference | 0/0 | nan | nan | false | nan | nan |
| overall_preference | 0/0 | nan | nan | false | nan | nan |
| constraint_preference | 0/0 | nan | nan | false | nan | nan |


A PASS is forbidden until every row carries non-synthetic human/PI rating
provenance. Quality, overall, and constraint questions are reported separately.

```json
{
  "abstain_policy": "report",
  "complete_real_ratings": false,
  "endpoints": {
    "constraint_preference": {
      "counts": {
        "abstain": 80
      },
      "decided": 0,
      "method_rate": NaN,
      "one_sided_95_lower": NaN,
      "original_rule_p_less_equal_under_0p5": NaN,
      "original_rule_pass": false,
      "primary_noninferiority_pass": false,
      "ties_against_method_rate": NaN,
      "ties_as_half_rate": NaN
    },
    "overall_preference": {
      "counts": {
        "abstain": 80
      },
      "decided": 0,
      "method_rate": NaN,
      "one_sided_95_lower": NaN,
      "original_rule_p_less_equal_under_0p5": NaN,
      "original_rule_pass": false,
      "primary_noninferiority_pass": false,
      "ties_against_method_rate": NaN,
      "ties_as_half_rate": NaN
    },
    "quality_preference": {
      "counts": {
        "abstain": 80
      },
      "decided": 0,
      "method_rate": NaN,
      "one_sided_95_lower": NaN,
      "original_rule_p_less_equal_under_0p5": NaN,
      "original_rule_pass": false,
      "primary_noninferiority_pass": false,
      "ties_against_method_rate": NaN,
      "ties_as_half_rate": NaN
    }
  },
  "reliability": {
    "constraint_preference": {
      "agreed": 0,
      "agreement_rate": NaN,
      "decided": 0
    },
    "overall_preference": {
      "agreed": 0,
      "agreement_rate": NaN,
      "decided": 0
    },
    "quality_preference": {
      "agreed": 0,
      "agreement_rate": NaN,
      "decided": 0
    }
  },
  "status": "AWAITING_RATINGS"
}
```
