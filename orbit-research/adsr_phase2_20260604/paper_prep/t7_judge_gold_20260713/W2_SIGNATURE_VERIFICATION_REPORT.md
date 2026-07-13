# W2 Signature Verification

`W2_AMENDMENT_STATUS = PI1_SIGNED_PI2_PENDING`

Verification date: 2026-07-13 Asia/Shanghai.

- PI 1 is signed by Richard Ye (`pi:Richard`) on 2026-07-13.
- PI 1 signature commit: `cf805a3dd88067931c1483d2bbe595d19f839b18`.
- PI 2 provenance, name, date, and commit fields: blank.
- Claude attestation: absent.
- Referenced commit `0df1cbb`: changes only the W2 execution report and recovery ledger; it contains no W2 signature or attestation text.
- Repository/history search for `GPT-5.6-Pro` and the referenced Claude attestation: no recoverable verbatim signature text.

This is not a bookkeeping-only state: the amendment itself says both signatures
are required before ratings and before PLAN/claim changes, while the T6 ratings
already exist. A signature added now must be described as retrospective
ratification/adoption, not as a prospective pre-rating signature.

The Richard signature was explicitly authorized by the user and committed with
Richard Ye authorship. It does not supply or substitute for either missing
independent signature.

Consequences:

- `LIVE_CONFIRM_STATUS = BLOCKED_UNSIGNED_W2_AMENDMENT` because PI 2 remains
  unsigned.
- `W2_ADOPTION = PI1_SIGNED_PI2_PENDING`.
- `PLAN_CLAIMS_SUPERSESSION = NOT_APPLIED`.

Codex did not fabricate or impersonate the missing GPT/Claude signatures.

Evidence:

- `paper_prep/W2_AMENDMENT_20260712.md`
- `paper_prep/t7_judge_gold_20260713/W2_ADOPTION_SIGNATURE_REQUEST.md`
- Git commit `cf805a3dd88067931c1483d2bbe595d19f839b18`
- Git commit `0df1cbb`
- `paper_prep/autochain_20260712/LIVE_CONFIRM_GUARD_TRACEBACK.txt`
- `paper_prep/autochain_20260712/recompute/DUAL_PI_ADOPTION_PACKET.md`
