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
| T9 v1.5 prevalence | `2033000000` through `2033001023` | COMPLETE | `base + manifest_index*8 + seed_idx`; seed-disjoint from all completed and registered work. | 128 prompts x 8 seeds. |
| T9 v1.5 focused retry | `2033010000` through `2033010511` | COMPLETE | `base + hard_prompt_rank*32 + seed_idx`; selected only after prevalence scoring. | 16 hard prompts x 32 seeds. |
| T9 v1.5 matched intervention | `2033020000` through `2033020127` | COMPLETE_CRN | Baseline and recondition intentionally share each prompt/seed; range is disjoint across pairs and from all other tasks. | 16 hard prompts x 8 seeds x 2 conditions. |
| T9 v1.5 smoke | `2033090000` through `2033090001` | COMPLETE | Engineering-only smoke; disjoint from all analysis rows. | One instrumental and one vocal request. |

## Collision Guard

Never reuse base `2030000000` with `seed_idx >= 1000`; Stage-3 condition
offsets occupy that range.
