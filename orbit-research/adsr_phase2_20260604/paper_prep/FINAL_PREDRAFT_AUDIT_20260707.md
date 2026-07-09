# Final Pre-Draft Audit

Generated: 2026-07-07

FINAL_STATUS = READY_WITH_REDUCED_CLAIMS

Recommendation: **READY_WITH_REDUCED_CLAIMS**

This is not READY_TO_DRAFT under the full guide checklist because A-prime and
B-prime validation remain blocked by judge-smoke failure. A reduced draft can
proceed only if label/quality validation claims are omitted or explicitly
marked as pending.

## Ready-To-Draft Checklist

| Item | Status | Evidence |
|---|---|---|
| A-prime label validation | BLOCKED | `paper_prep/validation_A_prime/A_PRIME_GATE_REPORT.md`; judge smoke 6/10 FAIL for Plus and Flash |
| B-prime quality validation | BLOCKED | `paper_prep/validation_B_prime/B_PRIME_GATE_REPORT.md`; judge smoke 6/10 FAIL for Plus and Flash |
| Efficiency metrics + Figure 2 | READY | `paper_prep/analysis/efficiency_claims.md`; `paper_prep/figures/fig2_regime_plot.png`; `paper_prep/figures/fig2_regime_plot.pdf` |
| Stage 3 read-out | READY | `paper_prep/stage3_intervention_20260707/STAGE3_PUBLICATION_READOUT.md` |
| N2 population map | READY | `paper_prep/population_retry_20260707/N2_PUBLICATION_READOUT.md` |
| CLAP fidelity | REDUCED | `paper_prep/clap_fidelity/CLAP_FIDELITY_REPORT.md`; mean paired delta +0.005996, CI crosses zero |
| Router replay | REDUCED | `paper_prep/router_replay/ROUTER_REPLAY_REPORT.md`; live router confirmation NO-GO under replay rule |
| `PLAN.md` | READY_WITH_BLOCKERS | `paper_prep/PLAN.md`; 6 READY, 3 REDUCED, 3 BLOCKED rows |
| Wording hygiene | READY_WITH_BLOCKERS | Wording constraints recorded in `paper_prep/PLAN.md` |

## Artifact Table

Full checksum manifest: `paper_prep/PREDRAFT_ARTIFACT_CHECKSUMS_20260707.tsv`

| Artifact | Path | SHA256 | Claim supported | Audit status |
|---|---|---|---|---|
| Inventory | `paper_prep/PUBLICATION_ARTIFACT_INVENTORY_20260707.md` | `ea7205977ab8c08695a89101da7d1494a1028c61e34c4d4fb5f27d4098c36f05` | package inventory | PASS |
| Frozen checksums | `paper_prep/FROZEN_ARTIFACT_CHECKSUMS_20260707.tsv` | `bf727e01fd89f9f5e5cc989ab091376c16560282e1ca954a53330b63973f64f3` | Stage 3/N2 frozen evidence | PASS |
| Storage triage | `paper_prep/STORAGE_TRIAGE.md` | `9a2130aa9e72919396239fe79315dd3a32a84da0f75b920460f8f74ac1a554e4` | storage safety | PASS |
| Judge failure analysis | `paper_prep/judge_debug/JUDGE_SMOKE_FAILURE_ANALYSIS_20260707.md` | `ce89792d0afa3dbc1503f9650e243de55719cb64b02a0195241d31faad9ff633` | A/B blocker | BLOCKED |
| A-prime gate | `paper_prep/validation_A_prime/A_PRIME_GATE_REPORT.md` | `a094ce939d9ae5dd06fc52d9e29fdff87f08b121b692570ee7a396263bc86be5` | label validation | BLOCKED |
| B-prime gate | `paper_prep/validation_B_prime/B_PRIME_GATE_REPORT.md` | `22f2b900f3288909084e62ab2da136d25e9b64ed8b9fafc520cbc46d7ac87a29` | quality validation | BLOCKED |
| Figure 2 data | `paper_prep/figures/fig2_regime_data.csv` | `afea9dab46b8721f7e39e1877ff9490ad2f2b07f65318e4a404faffec087c294` | efficiency | PASS |
| Figure 2 PNG | `paper_prep/figures/fig2_regime_plot.png` | `589ac0cab3720eb0e2cf090634ec73b0fb8ad27430f5971c348c9a346d641e57` | efficiency | PASS |
| Figure 2 PDF | `paper_prep/figures/fig2_regime_plot.pdf` | `08ee5c60adf722d7a360a023883f7e0514681bb1be83f9fef49e0d34e5dac202` | efficiency | PASS |
| Efficiency claims | `paper_prep/analysis/efficiency_claims.md` | `5d5531299421acd21265de78e3c1e68c2ef0d0ce1616d21435c14edeba37bf05` | efficiency | PASS |
| Stage 3 read-out | `paper_prep/stage3_intervention_20260707/STAGE3_PUBLICATION_READOUT.md` | `9a7eff3c06a2e137a8d7526660305171ffd14614383ca262b93a5c4dbb5f5960` | intervention decomposition | PASS |
| Stage 3 figure CSV | `paper_prep/stage3_intervention_20260707/stage3_condition_rates_figure_data.csv` | `2e6cb07ffa338c0d181f986e15a480118fd79f5229865d37dd2ba6793c142274` | intervention decomposition | PASS |
| N2 read-out | `paper_prep/population_retry_20260707/N2_PUBLICATION_READOUT.md` | `1a28b99f0666c4ee28b185e7b28d536bb82fedd8346de290a1d8b5abfa46ded2` | regime map | PASS |
| N2 figure CSV | `paper_prep/population_retry_20260707/n2_regime_figure_data.csv` | `3731626addb737aed6abde254f74c2432755cae918a0ec8fdbaf45be11ca2a98` | regime map | PASS |
| CLAP report | `paper_prep/clap_fidelity/CLAP_FIDELITY_REPORT.md` | `dc525436a0e04786f5f5f8b45439a95f098e291476b2373e30fe3a93a497cec8` | prompt fidelity | REDUCED |
| CLAP results | `paper_prep/clap_fidelity/CLAP_FIDELITY_RESULTS.csv` | `fccaded92059d53b4d52bb34fbf8277a7bc2d0cf7a6f4c96482039967d6bcca3` | prompt fidelity | PASS |
| Router replay | `paper_prep/router_replay/ROUTER_REPLAY_REPORT.md` | `e23b2af1179986607a0d84dd85b33ecca22b7e58af79c8736a9e74c59dd0b570` | router policy | REDUCED |
| Claim plan | `paper_prep/PLAN.md` | `0dfffed11d6e4416e52a7aa63fe889c5afd0dd65b35336c2f1fca7d4d8d2bb8f` | all claims | READY_WITH_BLOCKERS |
| Backlog log | `paper_prep/BACKLOG_DISPATCH_LOG.md` | `e2f5b829e8373d80e71e59d7c16cf2837114c08e66fb69159656b4326601b637` | node dispatch | PASS |
| Execution ledger | `paper_prep/execution_20260707/CODEX_RECOVERY_EXECUTION_LEDGER.md` | `a313f005f19b9de09079bb6a3dc3e9f15178751fecd999092804be796ac15b70` | recovery audit trail | PASS |

## Open Blockers

| Blocker | Exact cause | Next action | PI needed |
|---|---|---|---|
| A-prime label validation | Qwen Plus and Flash repaired smokes both failed 6/10; failures are four expected-negative clips with unanimous model `yes` votes. | Build a new smoke with human/PI-adjudicated negatives or approve a fallback validation path. | Yes, if adjudicated labels or fallback choice are required. |
| B-prime quality validation | Same judge smoke failure blocks scale pair judging. | Resolve judge smoke or approve non-Qwen/human fallback before B-prime scale calls. | Yes, if fallback choice affects claims. |
| Stage 4 SAO | `stable_audio_tools` absent; direct install would mutate shared torch/torchaudio/CUDA stack. | Create isolated env/container, run one-sample smoke, then decide whether second-backbone line continues. | No immediate PI decision unless second-backbone result changes paper scope. |
| Router live confirmation | CPU replay says NO-GO for rare-router live confirmation under the simple rule because always-recondition dominates. | Do not launch live router confirmation unless a revised router rule is specified and justified. | Yes only if the paper needs a router claim. |
| Release hygiene | Temporary DashScope credential material exists in non-release-safe locations. | Remove secrets from releaseable files and keep credentials in environment/gitignored secret file. | No. |

## Drafting Recommendation

**READY_WITH_REDUCED_CLAIMS.**

Safe reduced draft scope:

- Efficiency and Figure 2 can be drafted.
- Stage 3 intervention decomposition can be drafted.
- N2 selected held-out regime map can be drafted with the selected/difficult-set caveat.
- CLAP can be described as ambiguous/non-negative on average, with CI crossing zero.
- Router replay can be described as a counterfactual NO-GO for live confirmation under the tested rule.

Unsafe current claims:

- Do not claim A-prime label validation passed.
- Do not claim B-prime quality validation passed.
- Do not claim second-backbone robustness.
- Do not describe selected/difficult-set rates as generic population rates.
