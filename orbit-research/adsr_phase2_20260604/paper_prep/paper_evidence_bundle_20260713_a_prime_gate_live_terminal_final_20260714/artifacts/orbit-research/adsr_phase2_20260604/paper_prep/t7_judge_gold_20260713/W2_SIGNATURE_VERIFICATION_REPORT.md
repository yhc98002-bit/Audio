# W2 Signature Verification

`W2_AMENDMENT_STATUS = SIGNED_BY_BOTH_PIS`

`W2_ADOPTION = PI1_SIGNED_PI2_INCOMPLETE`

Verification date: 2026-07-14 Asia/Shanghai.

## Amendment

- PI 1 provenance/name/date/commit/decision are complete for `pi:Richard`.
- PI 2 provenance/name/date/commit/decision are complete for
  `pi:GPT-5.6-Pro` as recorded verbatim by `pi:Richard`.
- The independent Claude auditing attestation is present.
- Remote signature commits `93d334c` and `95578a6` were merged into local
  `main`; the amendment status was mechanically updated after field checks.
- The pre-signature header prose still says `PI 2 pending`, contrary to the
  complete signature blocks and signed status marker. It is retained because
  the live launch froze amendment SHA-256
  `37dfec4cedbd6cb74a3f8cf78211c61631dd3a07618e88a9e3840542a3895439`;
  the external verification report records the clerical contradiction instead
  of mutating the hashed launch input.
- The signature timing remains retrospective relative to T6 ratings; signing
  does not convert A-prime or B-prime into a PASS.

Consequence: the frozen W2 amendment plus mechanical corrected-instrument
promotion satisfied the live-confirm launch authorization. The live run is
now active on `an12` GPUs 4-7; its first reward-scoring attempt failed, was
repaired using verified local offline models, and resumed without resetting
the original hard-stop clock or regenerating the four completed orphan FLACs.

## Adoption

The publication-adoption branch remains fail-closed:

- `W2_ADOPTION_SIGNATURE_REQUEST.md` still has a blank PI 2 name, date,
  signing commit, and authentic decision block.
- `T6_PROMOTION_ESCALATION.md` now contains PI 1 and PI 2 adoption headings,
  but the PI 2 decision ends mid-sentence after `the promoted corrected`.
- Claude's adoption attestation is complete, but it cannot substitute for the
  incomplete PI 2 adoption text.

These artifacts conflict on adoption completeness. Codex did not repair or
invent the missing PI 2 text. Therefore broad corrected-number PLAN/CLAIMS
supersession and the post-adoption evidence-bundle refresh remain blocked.

Current consequences:

- `LIVE_CONFIRM_STATUS = COMPLETE_CRITERIA_NOT_ALL_MET`.
- `PLAN_CLAIMS_SUPERSESSION = NOT_APPLIED`.
- `EVIDENCE_BUNDLE_REFRESH = BLOCKED_W2_ADOPTION`.

Evidence:

- `paper_prep/W2_AMENDMENT_20260712.md`
- `paper_prep/autochain_20260712/T6_PROMOTION_ESCALATION.md`
- `paper_prep/t7_judge_gold_20260713/W2_ADOPTION_SIGNATURE_REQUEST.md`
- `paper_prep/autochain_20260712/T6_PROMOTION_RESULT.json`
- Git commits `93d334c`, `95578a6`, and the local merge commit
