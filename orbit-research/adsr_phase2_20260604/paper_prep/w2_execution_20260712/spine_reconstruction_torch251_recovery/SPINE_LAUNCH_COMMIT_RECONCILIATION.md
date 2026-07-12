# Spine Full-Replay Launch Commit Reconciliation

`SPINE_LAUNCH_COMMIT_RECONCILIATION = PASS_GENERATION_CRITICAL_DIFF_EMPTY`

The frozen protocol recorded repository commit `99c88de3762d05d6c4a1fd8a57254d9c0df38ef9`. Committing the already-generated probe audit, frozen recovery manifest, and protocol advanced HEAD to `7f63ab79948736c5bb6bd0d733c3eb570a1a2ac6` before the full launch. Every full-replay generation ledger records `7f63ab79948736c5bb6bd0d733c3eb570a1a2ac6` as the actual repository commit.

A path-level audit between those commits is empty for every generation-critical input:

- `paper_prep/scripts/w2_spine_reconstruct_20260712.py`;
- `src/mprm/inference/ace_step.py`;
- `scripts/collect_early_tweedie_validation.py`;
- `configs/prompts/dev.jsonl`;
- `configs/prompts/held_out.jsonl`.

The frozen worker SHA256 remains `238179b8d23123253f16eebc8c0ba324d252b5f3b36682e0d7000b5bd9856c51`. The intervening commit contains only the probe audit implementation/results, recovery manifest/snapshot/protocol, tests, logs, and execution-ledger updates.

This is an administrative commit-field correction, not a protocol, seed, model, prompt, scheduler, or runtime change. The final full audit must cite the actual launch commit and this reconciliation instead of silently reporting the stale protocol commit.
