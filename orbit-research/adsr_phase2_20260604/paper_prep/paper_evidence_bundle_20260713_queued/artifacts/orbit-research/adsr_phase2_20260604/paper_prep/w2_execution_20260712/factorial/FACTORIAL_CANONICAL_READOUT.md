# W2 Instrumental Factorial Canonical Readout

`FACTORIAL_STATUS = PREREGISTERED_GENERATED`

Primary positive-condition rows use the committed full-prompt lexical correction. The first 1,024 positive rows remain an invalid implementation-sensitivity cohort.

| condition | rows | current apparent violation | candidate sensitivity violation | candidate 95% prompt-bootstrap CI |
|---|---:|---:|---:|---|
| `plain_baseline` | 512 | 0.396484 | 0.568359 | [0.472656, 0.662109] |
| `negative_text` | 512 | 0.429688 | 0.619141 | [0.539062, 0.699219] |
| `positive_text` | 512 | 0.207031 | 0.353516 | [0.263672, 0.443359] |
| `sampler_only` | 512 | 0.390625 | 0.552734 | [0.445312, 0.658203] |
| `negative_sampler` | 512 | 0.417969 | 0.591797 | [0.494141, 0.687500] |
| `positive_sampler` | 512 | 0.195312 | 0.332031 | [0.230469, 0.435547] |

All rates are apparent or candidate-instrument sensitivity results. Promoted-instrument scoring remains blocked on W2 ratings and signatures.
The 20-pair blinded PI spot check uses `positive_sampler` selected by `candidate_violation`.

## Invalid First Positive Cohort

- `positive_text`: n=512, candidate rate=0.435547.
- `positive_sampler`: n=512, candidate rate=0.406250.
