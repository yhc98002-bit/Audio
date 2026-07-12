# Light-Plan Addendum for the 2026-07-11 Rating Bundles

`LIGHT_PLAN_ADDENDUM_STATUS = SIGNED`

This signed addendum fixes the light-plan rating assignment and provenance. It
does not itself alter a gate or authorize an A-prime or B-prime PASS.

## Rating Assignment

CXY is the independent primary rater, identified by initials only, for the new
2026-07-11 bundles `t2_aprime_core`, `t3_bprime_primary`,
`t4_bprime_reverse`, and `t5_sa3_calibration`. CXY records provenance as
`human:CXY`.

The PI rates `t1_decisive` with provenance `pi:<name>`. The PI also adjudicates
every CXY `unsure` response and every CXY-versus-detector disagreement, and the
PI makes the final A-prime and B-prime gate calls. Mechanical scorers may
compute criteria but never auto-sign or auto-approve either gate.

## Independence Limitation

CXY previously saw older rating packets before these new bundles were built.
That exposure must be disclosed as a limitation. The 2026-07-11 bundles use a
new nonce-derived blinding namespace and contain no expected labels, analysis
buckets, method-arm mappings, or set names, but the earlier exposure cannot be
undone.

## Provenance

Accepted human provenance values are `pi:<name>` and `human:CXY`. A model
rating is ineligible for the 190-row A-prime human core and is eligible for the
separate 500-row judge track only after held-out validation and complete model,
gold-set, calibration, and raw-response provenance are recorded.

## Signature

PI signature: Richard

Date: 2026-07-12

Approval statement: "I have read and approve
LIGHT_PLAN_ADDENDUM_20260711.md as committed at 8e7f412 as the governing
light-plan assignment for the 2026-07-11 rating bundles."
