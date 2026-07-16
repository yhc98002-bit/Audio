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
| W2 spine reconstruction | source-seed replay: `2026052700` through `2026563707` | ACTIVE_REPLAY | Intentional replay of each exact frozen candidate seed in a new output root; replay rows are linked to their historical identity and never treated as independent samples. | 4,095 missing candidates plus one surviving-original audit replay; exact ACE-Step v1 configuration. |
| W2 instrumental factorial | `2034000000` through `2034031015` | RESERVED_CRN | `base + prompt_rank*1000 + seed_idx`; all six conditions intentionally share the same prompt/seed and the range is disjoint from all completed and registered work. | 32 prompts x 6 conditions x 16 seeds; 3,072 clips. |
| W2 bounded live confirm | `2035000000` through `2035006301` | RESERVED_CRN_BLOCKED | `base + prompt_rank*100 + rep`; all four policies intentionally share each prompt/repetition seed. No launch until dual signatures, promoted-instrument PASS, and frozen policies are machine-verified. | 64 prompts x 4 policies x 2 repetitions; preparation only. |
| Exit-1 unconditional base rate | `2036000000` through `2036000255` | RESERVED | `base + manifest_index`; seed-disjoint from completed and registered work. | 16 frozen empty/neutral prompt rows x 16 seeds; 256 retained clips; PRIOR EVIDENCE only. |

## Collision Guard

Never reuse base `2030000000` with `seed_idx >= 1000`; Stage-3 condition
offsets occupy that range.
