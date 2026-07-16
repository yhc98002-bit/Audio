# Exit-1 Deployable Recipe Curves

The frozen factorial contributes 32 prompt clusters with 16 common-random-number attempts per condition. Selection follows the live worker: promoted-gate satisfaction first, then quality. The CQS-style quality proxy maps factorial CLAP semantic fit and Audiobox PQ onto live-confirmation robust LCB; its floor is the lower quartile of constraint-satisfying `no_probe_reseed` live slots.

| Source | Recipe | N | Violation rate (95% CI) | CQS-style success (95% CI) | Violation delta vs matched baseline | CQS delta vs matched baseline |
|---|---|---:|---:|---:|---:|---:|
| factorial | `plain_baseline+selection` | 1 | 0.719 [0.562, 0.875] | 0.250 [0.094, 0.406] | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] |
| factorial | `positive_text+selection` | 1 | 0.500 [0.312, 0.656] | 0.281 [0.125, 0.438] | -0.219 [-0.375, -0.094] | +0.031 [-0.062, +0.156] |
| factorial | `positive_sampler+selection` | 1 | 0.500 [0.312, 0.688] | 0.312 [0.156, 0.469] | -0.219 [-0.375, -0.094] | +0.062 [-0.094, +0.219] |
| factorial | `plain_baseline+selection` | 2 | 0.375 [0.219, 0.531] | 0.438 [0.281, 0.594] | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] |
| factorial | `positive_text+selection` | 2 | 0.250 [0.124, 0.406] | 0.594 [0.406, 0.750] | -0.125 [-0.250, -0.031] | +0.156 [+0.031, +0.281] |
| factorial | `positive_sampler+selection` | 2 | 0.250 [0.125, 0.406] | 0.688 [0.531, 0.844] | -0.125 [-0.250, -0.031] | +0.250 [+0.125, +0.406] |
| factorial | `plain_baseline+selection` | 4 | 0.250 [0.125, 0.406] | 0.531 [0.344, 0.688] | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] |
| factorial | `positive_text+selection` | 4 | 0.094 [0.000, 0.188] | 0.781 [0.625, 0.906] | -0.156 [-0.281, -0.031] | +0.250 [+0.094, +0.406] |
| factorial | `positive_sampler+selection` | 4 | 0.094 [0.000, 0.188] | 0.781 [0.625, 0.906] | -0.156 [-0.281, -0.031] | +0.250 [+0.094, +0.406] |
| factorial | `plain_baseline+selection` | 8 | 0.188 [0.062, 0.344] | 0.719 [0.562, 0.875] | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] |
| factorial | `positive_text+selection` | 8 | 0.094 [0.000, 0.219] | 0.906 [0.812, 1.000] | -0.094 [-0.219, +0.000] | +0.188 [+0.062, +0.344] |
| factorial | `positive_sampler+selection` | 8 | 0.094 [0.000, 0.219] | 0.906 [0.812, 1.000] | -0.094 [-0.219, +0.000] | +0.188 [+0.062, +0.344] |
| live_confirmation | `plain_baseline+selection` | 2 | 0.354 [0.240, 0.469] | 0.510 [0.385, 0.625] | NA | NA |
| live_confirmation | `positive_sampler+selection` | 2 | 0.219 [0.135, 0.312] | 0.604 [0.490, 0.708] | NA | NA |

## Quality proxy and uncertainty

Proxy formula: robust-LCB = `0.228237 + 0.395439 * CLAP + 0.252999 * Audiobox_PQ`; in-sample live-slot R2 = `0.640905`; frozen quality floor = `2.123218`. This is explicitly CQS-style, not a replacement for the seven-axis robust-LCB evaluator.

Intervals use 10,000 prompt-cluster replicates with seed `2026071603`. Factorial treatment deltas are prompt-paired and compare with `plain_baseline+selection` at the same N and therefore equal generation compute.

Best deployable operating point: `positive_text+selection` at N=8 (0.094 violation; 0.906 CQS-style success).
