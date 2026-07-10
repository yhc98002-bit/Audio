# ADSR Manual Code Review Guide

This is the shortest useful path through the publication-recovery code. Review
the P0 rows first; generated media and large ledgers are evidence, not source.

## Critical Source Files

| Priority | File | Implementation logic to verify |
|---:|---|---|
| P0 | `src/mprm/inference/ace_step.py` | Wraps the **ACE-Step v1** upstream pipeline, validates checkpoint/device behavior, rejects unsupported sampler controls, and captures trajectories through a guarded scheduler hook. The logical model name is historical and must not be read as v1.5 provenance. |
| P0 | `src/mprm/inference/sa3.py` | Implements SA3 Medium loading, generation, and true same-trajectory intermediate capture. Check callback state, latent decoding, seed handling, and separation from legacy `sao.py`. |
| P0 | `scripts/batch3_online_harness.py` | Implements online probe/restart/continue budgets, CRN seeds, arm-2 yoking, intervention escalation, inline gate labels, resume, and append-only ledgers. |
| P0 | `scripts/batch3_analyze_v2.py` | Strictly parses and deduplicates 16 ledgers, reconstructs arm 5, checks every expected cell/selection, computes frozen endpoints and uncertainty, and reports per-arm near silence. |
| P0 | `paper_prep/scripts/stage3_intervention_worker.py` | Generates the six pre-registered decomposition conditions with disjoint seeds and canonical labels. Review condition construction and resume keys. |
| P0 | `paper_prep/scripts/population_retry_worker.py` | Generates the N2 128-prompt retry map. Review seed mapping, deduplication, requested-vocal logic, and FLAC persistence. |
| P0 | `paper_prep/scripts/build_publication_analysis_package_v2.py` | Produces deployment success, expected-draw bounds, prompt-bootstrap CIs, N2 membership uncertainty, and Figure 2 without mutating old figures. |
| P0 | `paper_prep/scripts/validation_gate_v2.py` | Shared fail-closed ID/cardinality/abstention checks used by both human gates. |
| P0 | `paper_prep/validation_A_prime/score_human_A_prime.py` and `validation_B_prime/score_human_B_prime.py` | Enforce exact admin/rating joins and compute the amended A-prime and pair-level B-prime gates. Blank templates must remain `AWAITING_RATINGS`. |
| P0 | `paper_prep/scripts/regeneration_fidelity_20260709.py` | Replays 50 ACE-Step v1 controls, hashes decoded waveforms, pins detector/CLAP randomness, and keeps regenerated media sensitivity-only by default. |
| P1 | `paper_prep/scripts/judge_client.py` | Logs deterministic raw judge requests/responses, audio format, model metadata, and parser output without writing credentials. It is not a validated ground-truth source. |
| P1 | `paper_prep/scripts/run_v15_replication.py` | Uses official ACE-Step 1.5 source/model paths, deterministic manifests, sharded append-only generation, decode/non-silence checks, and exact provenance. |
| P1 | `src/mprm/common/thresholds.py`, `provenance.py`, `run_ledger.py` | Centralize the 0.1791 detector rule and preserve config, Git, and model hashes across start/final/fail ledger events. |

## Markdown Requiring PI Attention

| Priority | File | Decision or risk |
|---:|---|---|
| P0 | `paper_prep/CODE_REVIEW_RECOVERY_REPORT_20260709.md` | Current 16-status recovery contract and evidence links. |
| P0 | `paper_prep/HUMAN_STUDY_CRITERIA_AMENDMENT_20260709.md` | Requires signature before ratings become gate evidence. |
| P0 | `paper_prep/PLAN.md` | Claim-by-claim numbers, paths, audit status, and wording caps. No blocked claim may appear as supported. |
| P0 | `paper_prep/model_identity/MODEL_IDENTITY_AUDIT_20260709.md` | Corrects frozen evidence from presumed v1.5 to verified ACE-Step v1. |
| P1 | `paper_prep/GATE_B_SUPERSESSION_NOTE_20260709.md` | Explains how later audits refine Gate-B without rewriting it. |
| P1 | `paper_prep/v15_replication_20260709/V15_ENV_MODEL_PROVENANCE.md` | Source revision, ModelScope model, environment, and replication status. |

## Review Questions

1. Do all generation and analysis joins fail on duplicate or missing keys?
2. Are seed namespaces deterministic, registered, and disjoint except explicit replay?
3. Does any code turn an unrated package or automatic detector into human truth?
4. Are difficult-set rates and pilot-only SA3 results worded as such?
5. Do failed rows, threshold exceptions, and old-vs-v2 differences remain visible?
