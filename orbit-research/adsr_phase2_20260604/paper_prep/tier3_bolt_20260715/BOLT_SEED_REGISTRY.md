# BOLT Seed Registry

Status: `FROZEN_COLLISION_AUDIT_PASS`

Requested candidate namespace base: `2040000000`

Selected namespace base: `2060000000`

The requested 2.04-billion namespace is occupied. The collision scan found
12,857 occurrences in `[2040000000, 2050000000)`, including retained W2 and
v1.5 artifacts. The next aligned namespace, `[2050000000, 2060000000)`, is
also occupied. The scan found zero occurrences in
`[2060000000, 2070000000)`, so `2060000000` is frozen for BOLT.

Frozen derivation, once the base is selected:

- root seed: `base + prompt_slot * 100000 + root_index * 10000`;
- restart seed: `root_seed + checkpoint_step * 100 + action_code`;
- fork seed: `root_seed + checkpoint_step * 100 + 50 + branch_index`;
- worker shard: `prompt_slot mod 16`, independent of action execution order.

Action codes are fixed as base restart `1` and conditioned restart `2`. Fork
branch index is `0` for this pilot. Seed identity depends only on prompt slot,
root index, checkpoint, and action, never dispatch or retry order.

Gate-0 engineering seeds use the reserved upper segment beginning at
`2069000000`; Gate-0 fork calibration uses the segment beginning at
`2069500000`. Pilot root/restart/fork seeds use the derivation above and remain
below `2065000000`. No seed depends on execution order.

Collision evidence: `BOLT_SEED_COLLISION_AUDIT.json`.
