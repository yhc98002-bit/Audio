# HUMAN-STUDY SUCCESS CRITERIA — FROZEN (T0.5, GATE-CRITICAL)

**Status: FROZEN as of 2026-07-06.**
From this date the criteria below may not change, and nobody views study results before
this file exists (guide §4 T0.5; §10 rule 1 "criteria before results").

**Source:** `ADSR_Publication_ToDo_Guide.md` v1.0 (2026-07-06), tasks T1.2 and T1.3.
The PI made **no amendments**; the criteria are adopted verbatim as written below.

---

## Study A — are the automatic vocal labels correct? (T1.2, GATE)

**Materials (three clip sets), verbatim from the guide:**

1. **Disagreement set — 112 clips** where our two automatic detectors disagreed. Already
   packaged: `orbit-research/adsr_phase2_20260604/phase0/rater_packet/` (interface
   `adjudication.html`).
2. **Hard-prompt audit — about 50 clips.** Build a blinded packet from the five
   vocal-request prompts with the rarest successes: `held_out_0199` (3 clean of 256),
   `held_out_0254` (6/256), `held_out_0024`, `held_out_0045`, `held_out_0240` (7/256 each).
   For each prompt take 6 randomly chosen clips the detector called "no vocals" plus ALL
   clips it called "has vocals". Audio is under
   `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/keep/`.
   The task spec already exists:
   `.../00_controller/HUMAN_BATCH_QUEUE/pending/AUDIT_rare_vocal_basins_20260621.md`.
3. **Agreement spot-check — 30 clips** randomly sampled from cases where both detectors
   agreed (this bounds the "both detectors wrong together" risk). Sample with a fixed
   random seed and record it.

**Rater question per clip (blinded, shuffled):** "Does this clip contain human singing or
voice? Yes / No / Unsure." Two raters per clip; the third rater judges only clips where the
two disagree or either marked Unsure. Human majority = ground truth.

**PASS CRITERIA (frozen):**

- Hard-prompt audit: at least **90%** of detector-labeled clips match human majority.
- Disagreement set: Demucs matches human majority in at least **70%** of the 112 cases
  (this also tells us which detector to trust and lets us state a bound on the global
  label error rate).
- Agreement spot-check: at most **2 of 30** clips contradict the human majority.

**Analysis is scripted, not eyeballed**; results go to
`paper_prep/HUMAN_STUDY_A_RESULTS.md` with counts, agreement rates, kappa, per-direction
breakdown, and a PASS/FAIL line, countersigned by the PI.
**If it fails:** stop Stages 3–5 → guide §11-A.

---

## Study B — do humans hear a quality cost? (T1.3, GATE)

**Materials, verbatim from the guide:** the pre-built blinded comparison set of **80
pairs** — 40 pairs of (our method Group 6) vs (equal-compute baseline Group 1), and 40
pairs of (Group 6) vs (new-seed-restart Group 4). Interface:
`orbit-research/adsr_phase2_20260604/phase3/human_ab/index.html`. Design doc:
`phase3/HUMAN_EVAL_DESIGN.md`.

**Rater questions per pair (already in the interface):** (1) Which clip do you prefer
overall? A / B / no preference. (2) Which matches the request better? (3) Which has fewer
audio flaws? Two raters per pair; third rater only on primary-question disagreement or
"unsure".

**PASS CRITERION (frozen), primary comparison = Group 6 vs Group 1:** among pairs where
raters expressed a preference, our method is preferred in at least **40%**, AND a standard
binomial test does not show it significantly below 50% (**5% level**). The Group 6 vs
Group 4 comparison is reported but is not a gate.

**Analysis:** per pair, take the majority answer on question 1; count wins among pairs
with a preference; results go to `paper_prep/HUMAN_STUDY_B_RESULTS.md` with win counts,
percentages, confidence intervals (separately for the two comparisons), and a PASS/FAIL
line, countersigned by the PI.
**If it fails:** stop Stages 3–4 method work → guide §11-B.

**Paper wording rule regardless of outcome:** we may write "no quality difference was
detected within the pre-set margin"; we may NEVER write "we proved there is no quality
loss".

---

## Clarifying note (recorded at freeze time; NOT an amendment)

The prepared A/B packet ships **240** blinded pairs
(`phase3/human_ab/response_sheet.csv`), a superset of the 80 gate-relevant pairs defined
above. The Study-B gate is evaluated exactly as written: on the pre-registered primary
comparison (Group 6 vs Group 1 pairs), with Group 6 vs Group 4 reported non-gating.
Ratings collected on any additional pairs are reported descriptively and gate nothing.

## Freeze provisions

1. These criteria may not be edited after 2026-07-06. Any change would require a new
   PI-signed file superseding this one BEFORE any rating CSV is opened — and none is
   anticipated.
2. Raters remain blinded (guide glossary); the unblinding key stays in the PI-only folder
   (`UNBLINDING_KEY.jsonl`, verified separated in T0.2).
3. `HUMAN_STUDY_A_RESULTS.md` / `HUMAN_STUDY_B_RESULTS.md` are invalid unless
   countersigned by the PI against this file.

## Attestation — no results viewed before freeze

Verified 2026-07-06, before signature:

- No rater CSV has been returned or opened. Both packet response sheets are blank
  templates: `phase3/human_ab/response_sheet.csv` (240 pair rows, all answer fields
  empty) and `phase0/rater_packet/response_sheet.csv` (250 rows, all answer fields
  empty).
- Per `GATE_B_FINAL_REPORT.md` §3/§5: rater packets prepared but not distributed;
  students not contacted; analysis of the online experiment was blinded until its Codex
  audit passed.

## PI sign-off

**Signed: yhc (Principal Investigator) — 2026-07-06.**

Authorization recorded verbatim from the PI's written instruction of 2026-07-06 in the
project session:

> "I am granting you authorization as Principal Investigator; all experiments conducted
> to date are fully compliant with regulations, so you may sign off on them."

This signature freezes the Study A and Study B criteria above and includes the PI's
compliance attestation for all experiments conducted to date. Filed on the PI's behalf,
as directed, by the project assistant (Claude), 2026-07-06. Consistent with the PI
authorization note added to `CLAUDE.md` on the same date.
