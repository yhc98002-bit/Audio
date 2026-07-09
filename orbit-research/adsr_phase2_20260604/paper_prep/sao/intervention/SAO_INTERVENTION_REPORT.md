# SAO Intervention Report

Generated: 2026-07-07

SAO_INTERVENTION_STATUS = NOT_RUN_SMOKE_FAILED

No paired SAO intervention was run because Stable Audio Open did not pass the
one-sample generation smoke:

- Smoke report: `paper_prep/sao/smoke/SAO_SMOKE_REPORT.md`
- Smoke ledger: `paper_prep/sao/smoke/SAO_SMOKE_LEDGER.jsonl`
- Model-access/prefetch log: `paper_prep/sao/logs/sao_hf_prefetch_20260707.log`

Conclusion: second-model robustness is not supported by generated SAO evidence
in this recovery pass. The paper must keep the single-backbone limitation unless
authenticated SAO model access is provided and the smoke/prevalence/intervention
sequence is rerun.
