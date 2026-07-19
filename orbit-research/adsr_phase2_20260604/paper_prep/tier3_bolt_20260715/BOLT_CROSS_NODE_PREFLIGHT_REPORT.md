# BOLT Cross-Node Pilot Preflight

PREFLIGHT_STATUS = PASS

Completed at `2026-07-16T03:00:46+08:00` before the multi-worker pilot launch.

## Scope

- `an12`, GPU 4: prompt slot 0, root index 0.
- `an29`, GPU 0: prompt slot 24, root index 0.
- Each worker owned one complete root tree and emitted all three checkpoint states and all five actions at each checkpoint.

## Audit

| Check | Result |
|---|---:|
| Root trajectories | 2/2 |
| Checkpoint states | 6/6 |
| Action outcomes | 30/30 |
| Unique action keys | 30/30 |
| Failed/error rows | 0 |
| Valid, non-silent action outputs | 30/30 |
| Manifest hashes identical | PASS |
| Runtime hashes identical | PASS |
| State/action contracts | PASS |
| Tree-edge NFE accounting | PASS |

The shared manifest hash is `45e469914b50e16da564c2331798d8ed455f35c59b5dacfc721d32d5f530205c`; the shared runtime identity hash is `b7aa5ac2d05c4b81807d08da4e7debd66a89be8c81546c07b83d75e5454a36d2`.

Measured action NFE agrees across nodes: full restarts cost `45` transformer calls, while step-6, step-12, and step-18 continuations cost `39`, `28`, and `16`, respectively. Every action row satisfies `total_tree_edge_nfe = prefix_nfe + action_nfe`.

## Preflight Ledger Checkpoints

- Root ledger SHA256: `73c2de086261b6a576e36c41eef3457ff08b88782512864e7cc989abbe4f41d7`
- Checkpoint ledger SHA256: `0be927df4d9e6614682e612b1c81e14a807b7e2241b17e97639fe13104aeaace`
- Action ledger SHA256: `4873f99c4c4507a85912d7bafab528d98a3c555e79f02b8d780866d18e0ff028`

These are preflight checkpoints only; the append-only ledgers continue during the full pilot.
