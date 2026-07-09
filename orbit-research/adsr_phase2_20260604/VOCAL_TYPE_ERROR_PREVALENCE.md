# Vocal/Instrumental Type-Error Prevalence (Stage 1)

Label threshold = **0.1791** (strata-median-midpoint; separation 0.3249).

- **Candidate type-error rate: 0.23**
- Prompt-level affected rate: 0.6367
- Vocal prompts: 0.2108 | Instrumental prompts: 0.2608
- vocal-req→no-vocal: 533 | instr-req→has-vocal: 409
- EN-vocal (vocal_scorable) type-error: {'n': 2256, 'type_error_rate': 0.2012}

## Survivor-set type-error (by common score — the decisive number)
- top-1: **0.1992** | top-2: 0.2139 | top-4: 0.2134
- top-1 by stratum: vocal 0.1867 | instrumental 0.2194

- Ambiguous near threshold: 557 (13.6%)

**Read:** if survivor top-1 type-error stays well above 0, simple common-score selection does NOT remove type errors → EVPD has method leverage.