# Backlog Dispatch Log

## 2026-07-07T13:00:23-07:00

- Node/host: an29
- Command/script path: `paper_prep/scripts/clap_fidelity_score.py`
- Input artifacts: `paper_prep/storage_triage/CLAP_FIDELITY_INPUT_MANIFEST.csv`, `configs/prompts/held_out.jsonl`, selected online-run FLACs
- Output artifacts: `paper_prep/clap_fidelity/CLAP_FIDELITY_MANIFEST.csv`, `paper_prep/clap_fidelity/CLAP_FIDELITY_RESULTS.csv`, `paper_prep/clap_fidelity/CLAP_FIDELITY_RESULTS.jsonl`, `paper_prep/clap_fidelity/CLAP_FIDELITY_REPORT.md`
- Status: COMPLETE
- Dispatch reason: publication-critical CLAP fidelity validation, GPU smoke passed on an29 GPU 0.
- Seed/disjointness: no generation; scoring-only analysis.
- Result: 1,261/1,261 rows scored, 0 errors. Paired arm6-arm1 mean CLAP delta +0.005996 with CI crossing zero; report verdict AMBIGUOUS.
- Next action: do not overclaim CLAP fidelity; use reduced wording from `paper_prep/clap_fidelity/CLAP_FIDELITY_REPORT.md`.

## 2026-07-07T13:00:23-07:00

- Node/host: an12
- Command/script path: none
- Input artifacts: backlog queue and frozen evidence constraints
- Output artifacts: none
- Status: IDLE_WITH_LOGGED_REASON
- Dispatch reason: no safe fresh generation dispatched during active pre-draft packaging. Tail-deepening has ambiguous existing `ext512*` state in the authoritative retry-study tree and needs a scoped artifact plan before adding new claim-adjacent audio; SAO work is assigned to an29 and remains isolated-env/dependency constrained; router live confirmation is NO-GO from replay; A-prime/B-prime are judge-smoke blocked.
- Seed/disjointness: not applicable.
- Next action: keep heartbeat active; use an12 only after a concrete, non-conflicting artifact plan is materialized.
