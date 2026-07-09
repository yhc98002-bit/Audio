# P0.1–P0.3 Gated replays (held_out, n=256)

**Held_out all-8-fail floor: 0.0117**

## P0.1 Gated BoN-k frontier (real seed order)

| policy | compute | gated type-error [CI95] | reward_frac |
|---|---|---|---|
| bon4_gated | 0.5 | 0.0391 [0.0195, 0.0625] | 0.972 |
| bon5_gated | 0.625 | 0.0234 [0.0078, 0.043] | 0.9789 |
| bon6_gated | 0.75 | 0.0117 [0.0, 0.0273] | 0.9852 |
| bon8_gated | 1.0 | 0.0117 [0.0, 0.0273] | 0.9931 |

## P0.2 Oracle decomposition (σ0.8, ungated selected type-error)

```json
{
  "evpd_k4_select (Batch-2 \u03c30.8 repro)": 0.1328,
  "oracle_k4_select": 0.0117,
  "oracle_unconstrained": 0.0117
}
```

## P0.3 Gated re-sim of Batch-2 policies

| policy | gated type-error [CI95] | reward_frac |
|---|---|---|
| full_bon8 | 0.0117 [0.0, 0.0273] | 0.9931 |
| bon4_first4 | 0.0391 [0.0156, 0.0664] | 0.972 |
| random_keep4 | 0.0195 [0.0039, 0.0391] | 0.9703 |
| common_restart | 0.0234 [0.0078, 0.043] | 0.9888 |
| adsr_evpd | 0.0195 [0.0039, 0.0391] | 0.9874 |