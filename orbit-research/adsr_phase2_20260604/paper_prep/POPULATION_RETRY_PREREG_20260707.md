# Population Retry Map Pre-Registration

Status: frozen before the 2026-07-07 population retry smoke/full launch.

## Purpose

Estimate regime proportions over a broader held-out population by rerunning
128 held-out prompts for 128 independent seeds each, using no intervention.
The primary read-out is the per-prompt clean-rate distribution and the fraction
of prompts in easy, intermediate, and rare regimes.

## Manifest

- Source prompts: `configs/prompts/held_out.jsonl`.
- Stratification source: `orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl`.
- Label threshold: vocal present iff Demucs vocal ratio is at least `0.1791`
  and the clip is not near-silent.
- Selection: 128 of 256 held-out prompts, deterministic and stratified over
  the 8-candidate baseline violation-count histogram.
- Frozen manifest:
  `orbit-research/adsr_phase2_20260604/paper_prep/population_retry_20260707/population_retry_manifest_128.jsonl`.

## Generation

- Model: ACE-Step v1.5 via the existing `audio-prm` environment.
- Node: an12 only unless PI reallocates nodes.
- Seeds: `2030000000 + original_heldout_prompt_index * 100000 + seed_idx`,
  with `seed_idx` in `[0, 127]`.
- Condition: `none`; no prompt edits, no guidance/hint intervention.
- Expected full rows: `128 * 128 = 16384`.
- Temporary WAVs: `/dev/shm`; kept outputs: FLAC under `paper_prep`.

## Gates

- Smoke: 50 clips, stratified over baseline violation-count bins.
- Full launch requires smoke duplicate/schema PASS, 0 generation errors,
  0 missing FLACs, and no near-silent rate above 2%.
- First-500 audit repeats duplicate/schema, error, near-silent, and FLAC checks.
- Final audit requires exactly 16,384 rows, no duplicate
  `(prompt_id, seed_idx)` keys, 0 generation errors, and 0 missing FLACs.

## Escalation

Stop and escalate on node loss, quota above 480 GB, duplicate-key failure,
near-silent rate above 2%, unrecoverable worker failure, or any result that
would reverse the direction of a paper claim without a clean audit trail.
