# BOLT Node Utilization

NODE_UTILIZATION_STATUS = COMPLETE_WITH_RECORDED_AN12_CAPACITY_DEVIATION

## Atlas execution

| Node | Prompt slots | Canonical roots | Canonical action rows | BOLT workers | GPUs | First record | Last record |
|---|---:|---:|---:|---:|---|---|---|
| `an12` | 0–23 | 48 | 720 | 4 | 4–7 | 2026-07-16T02:58:35+08:00 | 2026-07-16T03:30:01+08:00 |
| `an29` | 24–47 | 48 | 720 | 8 | 0–7 | 2026-07-16T02:58:36+08:00 | 2026-07-16T04:14:11+08:00 |

The summed per-output generation GPU wall time was `1427.503383` seconds on `an12` and `1941.117290` seconds on `an29`. Integrated scorer time summed over outputs was `4372.587437` and `27514.705962` seconds, respectively. `an29` became CPU-bound under eight concurrent integrated-scoring workers; no worker parameters were changed after launch.

## Preflight and recovery

The cross-node preflight produced two canonical roots, six checkpoint states, and 30 action rows before the full launch. Full workers verified and reused those files by key and hash. The attempt ledgers contain 98 `root_tree_complete:PASS` records: 96 unique root trees plus two idempotent preflight redispatch confirmations. Canonical ledgers contain exactly 96 root keys and no duplicates.

- Failed workers: `0`.
- Recovered workers: `0`.
- Missing action rows: `0`.
- Duplicate or conflicting canonical action rows: `0`.

## Capacity deviation

`an12` GPUs 0–3 were occupied by pre-existing non-BOLT processes throughout launch. They were not killed, suspended, or preempted. BOLT therefore used the four free GPUs 4–7 on `an12`, while `an29` ran the requested eight one-GPU workers. Each worker still owned complete root trees for its fixed prompt/root shard; no tree crossed nodes, and no live shard was reassigned when `an12` finished first.

This deviation affects wall-clock throughput only. The frozen prompt manifest, seed namespace, root ownership, shared-prefix accounting, model/checkpoint hashes, and expected action-key set were unchanged.

## Heartbeats

- `paper_prep/tier3_bolt_20260715/BOLT_HEARTBEAT_an12.log`
- `paper_prep/tier3_bolt_20260715/BOLT_HEARTBEAT_an29.log`

Both append-only logs span Gate 0, the cross-node preflight, full pilot generation, and the final `96 / 288 / 1440` ledger state. `BOLT_HEARTBEAT_STOP` was written only after generation, strict media audit, and oracle analysis completed.
