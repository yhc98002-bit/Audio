# Publication Recovery Seed Registry

All entries are reservations. A reservation does not authorize generation by
itself; it prevents accidental overlap once the corresponding task is
authorized by the governing recovery brief.

| Task | Seed base or range | Status | Collision policy | Notes |
|---|---|---|---|---|
| T2 regeneration-fidelity controls | source-seed replay: `2026052700` through `2026563707` | ACTIVE_REPLAY | Intentional replay of the exact historical candidate seed in an isolated output directory; never count replay rows as independent samples. | Registered before T2 launch. No new estimand or seed-disjoint claim. |
| T8 SA3 same-trajectory pilot | source-seed replay from existing SA3 range `2026070800` through `2026120707` | ACTIVE_REPLAY | Intentional replay of one existing seed per selected prompt; the replay is paired instrumentation and never counted as an independent prevalence sample. | Registered before true-intermediate launch. Selection seed `20260709`; 96 prompts maximum. |
| T10 tail deepening | `2031000000` | RESERVED | Seed-disjoint from completed generation and all other rows in this registry. | 32 prompts x N=1024; smoke first. |
| T10 warm restart | `2032000000` | RESERVED | Seed-disjoint from completed generation and all other rows in this registry. | One-day cap. |
| T9 ACE-Step v1.5 replication | `2033000000` | RESERVED | Seed-disjoint from completed generation and all other rows in this registry. | Mandatory because T0 resolved the frozen evidence as v1. |

## Collision Guard

Never reuse base `2030000000` with `seed_idx >= 1000`; Stage-3 condition
offsets occupy that range.
