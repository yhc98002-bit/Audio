# BOLT Oracle Structural Headroom

Best globally fixed feasible program: `frozen_w2_two_slot`. Raw-NFE budget: `90` (`2 x 45` measured forward calls).

BEST_STATIC_CQS60 = 0.745199693
ORACLE_CQS60 = 0.931451613
ORACLE_HEADROOM_CQS60 = 0.186251920
ORACLE_HEADROOM_LCB95 = 0.096069007
ORACLE_COMPUTE_SAVING = 0.342115277
ORACLE_COMPUTE_SAVING_LCB95 = 0.275409155
ORACLE_NONSTATIC_PROMPT_SHARE = 1.000000000

Best-static prompt-bootstrap 95% interval: `[0.578804057, 0.885492285]`; oracle interval: `[0.804382896, 1.000000000]`. Equal-stratum diagnostic CQS@60 is `0.679135818` static and `0.959865196` oracle. Oracle completion probability is `1.000000000`, mean selected-program NFE is `80.877803`, and selected oracle leaves contain `2` quality-floor failures.

The empirical tree oracle is outcome-aware and is only an upper bound. Terminal CONTINUE leaves are deduplicated by physical root output. Tree costs share each root prefix once; switch/fork continuations pay their remaining measured NFE and restarts pay their complete measured generation NFE. The option-value approximation uses `sum[-log(1-p_i)]` and is reported separately from empirical any-success.

`ORACLE_NONSTATIC_PROMPT_SHARE` is the frozen weighted share of prompts where the oracle-optimal feasible leaf program differs from the globally best static program. Comparison uses canonical physical leaf IDs after CONTINUE deduplication.

## Static programs

| program | weighted CQS@60 | completion | mean NFE | infeasible prompts |
| --- | ---: | ---: | ---: | ---: |
| frozen_w2_two_slot | 0.745200 | 1.000000 | 83.377 | 0 |
| fixed_step12_continue_switch_root0 | 0.736290 | 1.000000 | 79.169 | 0 |
| fixed_step18_continue_switch_root0 | 0.676114 | 1.000000 | 63.468 | 0 |
| two_base | 0.664190 | 1.000000 | 90.000 | 0 |
| fixed_step18_deterministic_fork_root0 | 0.654512 | 1.000000 | 61.000 | 0 |
| fixed_step12_deterministic_fork_root0 | 0.642416 | 1.000000 | 73.000 | 0 |
| fixed_step6_deterministic_fork_root0 | 0.642416 | 1.000000 | 84.000 | 0 |
| true_rollover_corrected_evpd | 0.628975 | 1.000000 | 87.792 | 0 |
| fixed_step12_continue_switch_root1 | 0.547561 | 1.000000 | 79.169 | 0 |
| fixed_step18_continue_switch_root1 | 0.505127 | 1.000000 | 63.468 | 0 |
| fixed_step18_deterministic_fork_root1 | 0.488998 | 1.000000 | 61.000 | 0 |
| fixed_step12_deterministic_fork_root1 | 0.488998 | 1.000000 | 73.000 | 0 |
| fixed_step6_deterministic_fork_root1 | 0.488998 | 1.000000 | 84.000 | 0 |
| one_base_plus_one_conditioned | 0.299059 | 0.383065 | 99.254 | 12 |
| two_direction_conditioned | 0.294163 | 0.383065 | 108.508 | 12 |
| fixed_step6_continue_switch_root0 | 0.264113 | 0.383065 | 93.254 | 12 |
| fixed_step6_continue_switch_root1 | 0.246448 | 0.383065 | 93.254 | 12 |

## Frozen strata

| stratum | static | oracle | headroom | nonstatic share |
| --- | ---: | ---: | ---: | ---: |
| high_risk_instrumental | 0.557292 | 0.937500 | 0.380208 | 1.000000 |
| low_risk_instrumental | 0.764881 | 1.000000 | 0.235119 | 1.000000 |
| medium_risk_instrumental | 0.580645 | 1.000000 | 0.419355 | 1.000000 |
| vocal_request | 0.813725 | 0.901961 | 0.088235 | 1.000000 |

## Structural choices

Action frequency: `{'SWITCH_CONDITION': 29, 'CONTINUE': 3, 'RESTART_CONDITIONED': 4, 'RESTART_BASE': 2, 'FORK_LATENT': 10}`. Checkpoint frequency: `{6: 29, 30: 3, 18: 7, 12: 9}`. Action entropy (natural log): `1.144019`.

Fixed conditioning is unnecessary on `25` sampled prompts (base already attains CQS) and harmful on `13` of them: `dev_0033, dev_0142, dev_0194, dev_0017, dev_0023, dev_0031, dev_0050, dev_0075, dev_0097, dev_0152, dev_0181, dev_0217, dev_0239`. Same-latent switching beats both matched restart actions at `19` states: `dev_0073:root1:step6, dev_0074:root1:step18, dev_0150:root0:step12, dev_0187:root0:step12, dev_0187:root1:step12, dev_0254:root0:step6, dev_0254:root1:step12, dev_0133:root0:step18, dev_0133:root1:step12, dev_0144:root1:step12, dev_0160:root0:step12, dev_0160:root1:step6, dev_0174:root1:step18, dev_0033:root0:step6, dev_0033:root0:step18, dev_0070:root0:step6, dev_0162:root1:step6, dev_0243:root0:step6, dev_0181:root0:step18`. A fixed deterministic-plus-fork program rescues `0` prompts missed by two base generations: `none`.

The corrected-EVPD baselines use the frozen sigma-0.8 W2 probe without retuning. The W2 two-slot baseline leaves abort savings unused; the true-rollover baseline returns measured NFE and uses only an additional branch that fits the global budget.
