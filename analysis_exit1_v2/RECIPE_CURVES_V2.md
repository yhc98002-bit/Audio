# Exit-1 Recipe Curves v2

## Primary endpoint

The primary endpoint is corrected Label-B violation after gate-first selection. Each condition contains 32 prompt clusters and 16 common-random-number attempts. At each N, selection first prefers a corrected Label-B-satisfied candidate and then uses the available quality score only as a tie-breaker.

| Recipe | N | Violations / 32 | Violation rate (95% prompt-cluster CI) | Paired delta vs equal-compute plain (95% CI) |
|---|---:|---:|---:|---:|
| `plain` | 1 | 23 / 32 | 0.719 [0.562, 0.875] | +0.000 [+0.000, +0.000] |
| `positive_text` | 1 | 16 / 32 | 0.500 [0.312, 0.656] | -0.219 [-0.375, -0.094] |
| `positive_sampler` | 1 | 16 / 32 | 0.500 [0.312, 0.688] | -0.219 [-0.375, -0.094] |
| `plain` | 2 | 12 / 32 | 0.375 [0.219, 0.531] | +0.000 [+0.000, +0.000] |
| `positive_text` | 2 | 8 / 32 | 0.250 [0.124, 0.406] | -0.125 [-0.250, -0.031] |
| `positive_sampler` | 2 | 8 / 32 | 0.250 [0.125, 0.406] | -0.125 [-0.250, -0.031] |
| `plain` | 4 | 8 / 32 | 0.250 [0.125, 0.406] | +0.000 [+0.000, +0.000] |
| `positive_text` | 4 | 3 / 32 | 0.094 [0.000, 0.188] | -0.156 [-0.281, -0.031] |
| `positive_sampler` | 4 | 3 / 32 | 0.094 [0.000, 0.188] | -0.156 [-0.281, -0.031] |
| `plain` | 8 | 6 / 32 | 0.188 [0.062, 0.344] | +0.000 [+0.000, +0.000] |
| `positive_text` | 8 | 3 / 32 | 0.094 [0.000, 0.219] | -0.094 [-0.219, +0.000] |
| `positive_sampler` | 8 | 3 / 32 | 0.094 [0.000, 0.219] | -0.094 [-0.219, +0.000] |

## Quality qualification - non-primary

`QUALITY_STATUS = PROXY_QUALIFIED_SUCCESS`

The 3,072 factorial rows do not contain complete common robust-LCB quality scores. Qualified-success values therefore use the frozen CLAP + Audiobox mapping as `PROXY_QUALIFIED_SUCCESS`. They are excluded from the primary endpoint and must not be presented as genuine qualified success.

| Recipe | N | Qualified successes / 32 | Diagnostic rate (95% CI) | Diagnostic paired delta vs plain (95% CI) |
|---|---:|---:|---:|---:|
| `plain` | 1 | 8 / 32 | 0.250 [0.094, 0.406] | +0.000 [+0.000, +0.000] |
| `positive_text` | 1 | 9 / 32 | 0.281 [0.125, 0.438] | +0.031 [-0.062, +0.156] |
| `positive_sampler` | 1 | 10 / 32 | 0.312 [0.156, 0.469] | +0.062 [-0.094, +0.219] |
| `plain` | 2 | 14 / 32 | 0.438 [0.281, 0.594] | +0.000 [+0.000, +0.000] |
| `positive_text` | 2 | 19 / 32 | 0.594 [0.406, 0.750] | +0.156 [+0.031, +0.281] |
| `positive_sampler` | 2 | 22 / 32 | 0.688 [0.531, 0.844] | +0.250 [+0.125, +0.406] |
| `plain` | 4 | 17 / 32 | 0.531 [0.344, 0.688] | +0.000 [+0.000, +0.000] |
| `positive_text` | 4 | 25 / 32 | 0.781 [0.625, 0.906] | +0.250 [+0.094, +0.406] |
| `positive_sampler` | 4 | 25 / 32 | 0.781 [0.625, 0.906] | +0.250 [+0.094, +0.406] |
| `plain` | 8 | 23 / 32 | 0.719 [0.562, 0.875] | +0.000 [+0.000, +0.000] |
| `positive_text` | 8 | 29 / 32 | 0.906 [0.812, 1.000] | +0.188 [+0.062, +0.344] |
| `positive_sampler` | 8 | 29 / 32 | 0.906 [0.812, 1.000] | +0.188 [+0.062, +0.344] |

## Observed frontier

This is a descriptive compute/violation frontier, not a deployable-point claim.

- `positive_sampler`, N=1: violation 0.500.
- `positive_text`, N=1: violation 0.500.
- `positive_sampler`, N=2: violation 0.250.
- `positive_text`, N=2: violation 0.250.
- `positive_sampler`, N=4: violation 0.094.
- `positive_text`, N=4: violation 0.094.

Best observed (exploratory only): `positive_text` at N=4, `positive_sampler` at N=4, each with violation rate 0.094. No deployment recommendation is made.

Intervals use 10,000 prompt-cluster bootstrap replicates. Treatment deltas are paired by prompt against `plain` at identical N and therefore equal generation compute.

No music was generated for this v2 analysis.
