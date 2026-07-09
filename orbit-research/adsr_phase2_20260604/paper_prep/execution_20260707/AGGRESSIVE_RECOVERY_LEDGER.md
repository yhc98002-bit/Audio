
## Aggressive Recovery Run - 2026-07-07T13:46:32-07:00

| timestamp | host/node | command | script path | input artifacts | output artifacts | result | next action |
|---|---|---|---|---|---|---|---|
| 2026-07-07T13:46:32-07:00 | ln207 | initialize aggressive recovery ledger | n/a | user directive 2026-07-07 | paper_prep/execution_20260707/AGGRESSIVE_RECOVERY_LEDGER.md | STARTED | read context and launch judge/SAO tracks |
| 2026-07-07T13:46:50-07:00 | ln207 | context file existence check | find | transcript_clean_with_artifact_markers.md | paper_prep/execution_20260707/AGGRESSIVE_RECOVERY_LEDGER.md | MISSING transcript_clean_with_artifact_markers.md in workspace search | continue with available required context |
| 2026-07-07T13:47:05-07:00 | ln207 | read required context and active blockers | sed/find | ADSR_Publication_ToDo_Guide.md; WHAT_HAVE_I_DONE; FINAL_PREDRAFT_AUDIT; PLAN; paper_prep blocker/readout/audit files | context loaded; transcript file logged missing | PASS | launch judge negative failure diagnosis and SAO execution planning |
| 2026-07-07T13:47:49-07:00 | an12/an29 | node utilization check | ssh nvidia-smi/pgrep | heartbeat logs; nvidia-smi | AGGRESSIVE_RECOVERY_LEDGER.md | both nodes saturated by temporary scripts/torch_gpu_sanity.py filler (600s) | prepare SAO and judge repair while filler exits, then replace with useful jobs |
| 2026-07-07T13:49:14-07:00 | ln207 | add negative smoke failure diagnosis script | paper_prep/scripts/negative_smoke_failure_diagnosis.py | repaired smoke manifest; plus/flash raw logs | NEGATIVE_SMOKE_FAILURE_TABLE.csv; NEGATIVE_SMOKE_FAILURE_ANALYSIS.md | RUNNING | build v2 smoke manifest |
| 2026-07-07T13:49:41-07:00 | ln207 | diagnose failed negative smoke labels | paper_prep/scripts/negative_smoke_failure_diagnosis.py | repaired smoke manifest; Qwen Plus/Flash raw logs | paper_prep/judge_debug/NEGATIVE_SMOKE_FAILURE_TABLE.csv; paper_prep/judge_debug/NEGATIVE_SMOKE_FAILURE_ANALYSIS.md | PASS rows=4 | build v2 smoke manifest from conservative detector-agreed clips |
| 2026-07-07T13:51:14-07:00 | ln207 | build judge smoke v2 manifest and parser tests | build_judge_smoke_v2_manifest.py; judge_client parser import | A_PRIME_500 manifest; held_out prompts | paper_prep/judge_debug/judge_smoke_v2_manifest.csv; PARSER_UNIT_TEST_REPORT.md | RUNNING | run Qwen Plus/Flash smoke v2 |
| 2026-07-07T13:51:28-07:00 | ln207 | run judge smoke v2 Plus/Flash | paper_prep/scripts/judge_client.py smoke | paper_prep/judge_debug/judge_smoke_v2_manifest.csv | judge_smoke_v2_plus_stdout.json; judge_smoke_v2_flash_stdout.json; paper_prep/judge_raw/smoke_10clip_v2_* | RUNNING | inspect smoke verdicts and decide A/B or fallback |
| 2026-07-07T13:52:48-07:00 | ln207 | inspect judge smoke v2 outputs | judge_client.py smoke summaries | judge_smoke_v2 stdout/raw logs | AGGRESSIVE_RECOVERY_LEDGER.md | v2 smoke exited nonzero; inspecting summaries | decide patch/fallback |
| 2026-07-07T13:54:29-07:00 | an29 | launch SAO dedicated env install | paper_prep/sao/run_sao_env_install.sh | SAO_EXECUTION_PLAN_20260707.md; src/mprm/inference/sao.py | paper_prep/sao/logs/sao_env_install_20260707.log; SAO_ENV_STATUS_20260707.json | RUNNING in tmux sao_env_20260707 | monitor install, then run one-sample SAO smoke |
| 2026-07-07T13:54:48-07:00 | ln207 | judge smoke v2 result | judge_client.py smoke | judge_smoke_v2_manifest.csv | judge_smoke_v2_plus_stdout.json; judge_smoke_v2_flash_stdout.json | FAIL Plus=6/10 Flash=6/10, failures all expected-negative clips with voice rationales | start fallback validation plan and package scoring where feasible |
| 2026-07-07T13:55:29-07:00 | ln207/login | pivot SAO env install to login because an29 DNS failed | paper_prep/sao/run_sao_env_install.sh | an29 install log DNS failure; SAO plan | paper_prep/sao/logs/sao_env_install_20260707.log; SAO_ENV_STATUS_20260707.json | RUNNING | after env import passes, run smoke on an29 |
| 2026-07-07T13:55:53-07:00 | ln207/login | rerun SAO env install after syntax fix | paper_prep/sao/run_sao_env_install.sh | previous failed install log | SAO_ENV_STATUS_20260707.json; sao_env_install log | RUNNING | monitor install |
| 2026-07-07T13:58:41-07:00 | ln207 | build A/B validation manifests | paper_prep/scripts/build_validation_manifests.py | A_PRIME sample, rare package, phase0 rater packet, human_ab pair packet | A_PRIME_MANIFEST.csv; B_PRIME_MANIFEST.csv | RUNNING | inspect counts/missing then run fallback model adjudication where valid |
| 2026-07-07T13:58:59-07:00 | ln207 | validation manifest build result | build_validation_manifests.py | existing human/auto packets | A_PRIME_MANIFEST.csv; B_PRIME_MANIFEST.csv | A rows=816 missing_audio=268; B rows=80 missing_pairs=0 | run fallback on existing rows and report missing A-prime blocker |
| 2026-07-07T14:01:08-07:00 | ln207 | recover A-prime tar media and rebuild manifests | tar targeted extract; build_validation_manifests.py | RARE_CLEAN manifest; human eval tarball | validation_A_prime/tar_extracted; A_PRIME_MANIFEST.csv | RUNNING | inspect recovered counts |
| 2026-07-07T14:05:00-07:00 | ln207 | extract phase0 label media from human eval tarball | tar targeted extract | /tmp/adsr_human_eval_pkg_20260620_complete_20260707.tar.gz | validation_A_prime/tar_extracted/adsr_human_eval_pkg/2_label_adjudication; 2c_detector_agreement_spotcheck | RUNNING | patch manifest resolver for extracted case-id media |
| 2026-07-07T14:05:29-07:00 | ln207 | rebuild validation manifests after package extraction | build_validation_manifests.py | extracted label/rare media | A_PRIME_MANIFEST.csv; B_PRIME_MANIFEST.csv | RUNNING | if complete, launch fallback model A/B scoring |
| 2026-07-07T14:06:27-07:00 | ln207 | create fallback validation plan and judgeable A manifest | FALLBACK_VALIDATION_PLAN.md; python csv filter | A_PRIME_MANIFEST.csv | validation_fallback/FALLBACK_VALIDATION_PLAN.md; A_PRIME_JUDGEABLE_MANIFEST.csv | PASS fallback plan written, A full pass blocked by 100 missing phase0 rows | run fallback Qwen A/B scoring |
| 2026-07-07T14:07:08-07:00 | ln207 | launch fallback A/B model scoring | judge_client.py aprime/bprime | A_PRIME_JUDGEABLE_MANIFEST.csv; B_PRIME_MANIFEST.csv | A_PRIME_RAW_RESPONSES.jsonl; B_PRIME_RAW_RESPONSES.jsonl; judge_raw/a_prime_fallback_plus_20260707.jsonl; judge_raw/b_prime_fallback_plus_20260707.jsonl | RUNNING | score gates as fallback when calls complete |
| 2026-07-07T14:08:14-07:00 | an29 | node status during SAO setup | ssh nvidia-smi/pgrep | an29 GPU state | AGGRESSIVE_RECOVERY_LEDGER.md | an29 busy with pre-existing eval_qwen_vl_fliptrack.py shards, not launched by this SAO plan | do not kill unknown jobs; run SAO smoke when free; continue login env install |

## 2026-07-07T14:15:16-07:00
- host: ln207
- command: added expanded CLAP/router/scoring/heartbeat scripts
- script path: paper_prep/scripts/clap_fidelity_expanded.py; paper_prep/scripts/router_replay_expanded.py; paper_prep/scripts/score_validation_fallback.py; paper_prep/scripts/heartbeat_full.sh
- input artifacts: CLAP results/manifests; ATLAS ledgers; validation manifests
- output artifacts: scripts staged for execution
- result: PASS
- next action: run scripts and update reports

## 2026-07-07T14:15:49-07:00
- host: ln207
- command: python paper_prep/scripts/clap_fidelity_expanded.py; python paper_prep/scripts/router_replay_expanded.py
- script path: paper_prep/scripts/clap_fidelity_expanded.py; paper_prep/scripts/router_replay_expanded.py
- input artifacts: CLAP scored outputs; ATLAS baseline/intervention ledgers; N2 regime map
- output artifacts: paper_prep/clap_fidelity/CLAP_FIDELITY_EXPANDED_RESULTS.csv; paper_prep/clap_fidelity/CLAP_FIDELITY_EXPANDED_REPORT.md; paper_prep/router_replay/ROUTER_REPLAY_EXPANDED_RESULTS.csv; paper_prep/router_replay/ROUTER_REPLAY_EXPANDED_REPORT.md
- result: PASS after path-anchor repair
- next action: update PLAN.md with expanded CLAP/router status

## 2026-07-07T14:17:52-07:00
- host: ln207
- command: redacted CLAUDE.md DashScope literal and added gitignore secret rules
- script path: n/a
- input artifacts: CLAUDE.md; .gitignore; paper_prep/scripts/.dashscope_key
- output artifacts: CLAUDE.md; .gitignore; paper_prep/RELEASE_SECRET_HYGIENE_20260707.md pending
- result: PASS
- next action: scan releaseable files and write hygiene report

## 2026-07-07T14:19:28-07:00
- host: ln207
- command: wrote release-secret hygiene report
- script path: n/a
- input artifacts: CLAUDE.md; .gitignore; paper_prep/scripts/judge_client.py; scoped secret scan outputs
- output artifacts: paper_prep/RELEASE_SECRET_HYGIENE_20260707.md
- result: PASS SECRET_STATUS=CLEAN
- next action: close PLAN.md secret/dataset row

## 2026-07-07T14:20:38-07:00
- host: ln207
- command: killed stalled stable-audio-tools pip resolver in audio-prm-sao
- script path: paper_prep/sao/run_sao_env_install.sh
- input artifacts: /HOME/paratera_xy/pxy1289/.conda/envs/audio-prm-sao
- output artifacts: paper_prep/sao/SAO_ENV_STATUS_20260707.json
- result: FAIL stalled >20 minutes, package not installed
- next action: clone/use existing audio-prm stack and install SAO without dependency resolver churn

## 2026-07-07T14:22:06-07:00
- host: ln207
- command: started persistent heartbeat tmux loops on an12/an29
- script path: paper_prep/scripts/heartbeat_full.sh
- input artifacts: nvidia-smi; tmux; process table; ledger files
- output artifacts: paper_prep/heartbeat_an12.log; paper_prep/heartbeat_an29.log
- result: PASS
- next action: summarize node saturation in audit

## 2026-07-07T14:22:32-07:00
- host: ln207
- command: python paper_prep/scripts/score_validation_fallback.py
- script path: paper_prep/scripts/score_validation_fallback.py
- input artifacts: A/B manifests; A/B raw fallback responses
- output artifacts: paper_prep/validation_A_prime/A_PRIME_AGREEMENT_MATRIX.csv; paper_prep/validation_A_prime/A_PRIME_GATE_REPORT.md; paper_prep/validation_B_prime/B_PRIME_ORDER_BIAS_REPORT.md; paper_prep/validation_B_prime/B_PRIME_GATE_REPORT.md
- result: PARTIAL B_PRIME_STATUS=FALLBACK_READY, A_PRIME still running/incomplete
- next action: rerun scorer after A-prime reaches 716 rows

## 2026-07-07T14:23:53-07:00
- host: ln207
- command: added SAO smoke wrapper
- script path: paper_prep/sao/run_sao_smoke.sh
- input artifacts: scripts/d1_model_load.py; src/mprm/inference/sao.py
- output artifacts: paper_prep/sao/smoke/SAO_SMOKE_LEDGER.jsonl; paper_prep/sao/smoke/SAO_SMOKE_REPORT.md when run
- result: PASS
- next action: launch on an29 after SAO clone import passes

## 2026-07-07T14:27:20-07:00
- host: ln207
- command: direct audio-prm stable-audio-tools --no-deps install authorized due node idle and clone delay
- script path: n/a
- input artifacts: audio-prm environment; package index
- output artifacts: paper_prep/sao/logs/audio_prm_direct_sao_install_20260707.log; before/after pip freeze
- result: RUNNING
- next action: run SAO smoke on an29 if import passes

## 2026-07-07T14:29:34-07:00
- host: ln207
- command: attempted SAO HF prefetch for stabilityai/stable-audio-open-1.0
- script path: n/a
- input artifacts: audio-prm env with stable-audio-tools installed
- output artifacts: paper_prep/sao/logs/sao_hf_prefetch_20260707.log
- result: FAIL gated Hugging Face repo 401, authentication/model access required
- next action: record SAO partial/blocker and do not claim second-backbone robustness

## 2026-07-07T14:29:59-07:00
- host: ln207
- command: SAO smoke on an29 via audio-prm after direct stable-audio-tools install
- script path: paper_prep/sao/run_sao_smoke.sh; scripts/d1_model_load.py; src/mprm/inference/sao.py
- input artifacts: audio-prm env; stabilityai/stable-audio-open-1.0 model reference
- output artifacts: paper_prep/sao/smoke/SAO_SMOKE_LEDGER.jsonl; paper_prep/sao/smoke/SAO_SMOKE_REPORT.md; paper_prep/sao/smoke/sao_smoke_an29_20260708T052823.log
- result: FAIL model files unavailable on an29 and HF repo gated on login prefetch
- next action: SAO remains PARTIAL/blocked by HF authentication/model access, not package environment

## 2026-07-07T14:29:59-07:00
- host: ln207
- command: stopped redundant audio-prm-sao-clone process after direct audio-prm install/smoke path executed
- script path: n/a
- input artifacts: partial conda clone /HOME/paratera_xy/pxy1289/.conda/envs/audio-prm-sao-clone
- output artifacts: paper_prep/sao/logs/sao_clone_install_20260707.log
- result: STOPPED partial clone, no evidence deleted
- next action: document dependency/package diff and model-access blocker in SAO report

## 2026-07-07T14:30:47-07:00
- host: ln207
- command: wrote SAO prevalence/observability/intervention blocker reports after smoke failure
- script path: paper_prep/sao/run_sao_smoke.sh
- input artifacts: SAO smoke ledger/report; HF prefetch log; audio-prm pip freeze diff
- output artifacts: paper_prep/sao/prevalence/SAO_PREVALENCE_REPORT.md; paper_prep/sao/observability/SAO_OBSERVABILITY_REPORT.md; paper_prep/sao/intervention/SAO_INTERVENTION_REPORT.md; corresponding JSONL ledgers
- result: PARTIAL SAO package fixed, generation blocked by gated model access
- next action: update PLAN.md limitation/follow-up

## 2026-07-07T14:31:44-07:00
- host: ln207
- command: inspected atlas backlog for idle GPU dispatch
- script path: batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/core_largeN_worker.py
- input artifacts: queue/done env files; ext512 logs; bon256 ledgers; STATUS_DAILY duplicate-bug notes
- output artifacts: AGGRESSIVE_RECOVERY_LEDGER.md
- result: NO_DISPATCH because ext512/bon256 tag reuse and prior duplicate-ledger bug make immediate launch unsafe without a new seed/tag plan
- next action: keep nodes heartbeated; do not corrupt frozen atlas evidence

## 2026-07-07T14:33:05-07:00
- host: ln207
- command: patched A-prime scorer for actual manifest set names
- script path: paper_prep/scripts/score_validation_fallback.py
- input artifacts: A_PRIME_MANIFEST.csv set_name values
- output artifacts: scorer update only; reports will be regenerated after A-prime completes
- result: PASS
- next action: wait for A_PRIME_RAW_RESPONSES.jsonl to reach 716 rows and rescore

## 2026-07-07T14:46:36-07:00
- host: ln207
- command: completed A-prime fallback API scoring and regenerated A/B gate reports
- script path: paper_prep/scripts/judge_client.py; paper_prep/scripts/score_validation_fallback.py
- input artifacts: A_PRIME_JUDGEABLE_MANIFEST.csv; B_PRIME_MANIFEST.csv; raw judge responses
- output artifacts: A_PRIME_RAW_RESPONSES.jsonl; A_PRIME_AGREEMENT_MATRIX.csv; A_PRIME_GATE_REPORT.md; B_PRIME_GATE_REPORT.md; B_PRIME_ORDER_BIAS_REPORT.md
- result: COMPLETED raw scoring; gate statuses in reports
- next action: update PLAN.md and final audit addendum

## 2026-07-07T14:48:26-07:00
- host: ln207
- command: rewrote PLAN.md with 15 mandatory claim rows
- script path: n/a
- input artifacts: final gate reports; CLAP/router expanded reports; SAO smoke reports; frozen claim artifacts
- output artifacts: paper_prep/PLAN.md
- result: PASS READY=8 REDUCED=6 BLOCKED=0 REMOVED=1
- next action: write final aggressive addendum

## 2026-07-07T14:50:38-07:00
- host: ln207
- command: wrote final aggressive addendum and completed artifact sanity checks
- script path: n/a
- input artifacts: PLAN.md; validation reports; SAO reports; CLAP/router reports; node audit
- output artifacts: paper_prep/FINAL_PREDRAFT_AUDIT_AGGRESSIVE_ADDENDUM_20260707.md
- result: READY_WITH_REDUCED_CLAIMS
- next action: report final status to PI
