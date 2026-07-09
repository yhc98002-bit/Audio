# Hedge Strategies — M-PRM Risk Mitigation

*写于 2026-05-19；针对 RISK_REGISTER.md 12 类风险的对冲方案。每条按 a/b/c/d 多种 action 给出，标 `Now-actionable` / `Conditional` (达成 trigger 才做) / `Fallback` (Plan B/C)。*

**Status refresh (2026-05-23):** H1 and H2 first-order hedges have fired or been
retired. Phase A passed, the saturation outline is now an inactive fallback, and H2
formula/reliability passed on the canonical 128-prompt analysis. Remaining hedges should
prioritize H3 credit-unit validity, reward hacking, and Phase C training stability.

---

## 1) 致命级对冲

### R1 (H1 fail — no headroom)

- **(a) Tiered exit ramp**: 用 r2_bon (BoN-8 ceiling) 作为 ultimate signal。若 BoN-8 gate_r_lcb 比 r0_base 高 < 0.5 SD，**M1a 直接结束**，不进 Phase B/C。NULL_RESULT_CONTRACT.md §1 已设计，但触发阈值需要在 M1a finals 出齐前 lock-in（避免事后 p-hack）。
  - **Status 2026-05-23**：completed via `orbit-research/HEADROOM_GATE_PREREG.md`; do not edit frozen `configs/eval/gate_v1.yaml` in place.

- **(b) Secondary backbone audit (SAO)**: Phase A.3 head-to-head 加 SAO 1.0 (audit-only)。若 SAO 显示 headroom 而 ACE-Step 没有，paper 重新框架为 *"M-PRM works on SAO; ACE-Step is saturated"*——backbone-specific 结论。
  - **Conditional**（仅 H1 borderline 时触发）。

- **(c) Pre-register saturation paper outline (1 页)**: 若 H1 完全 fail，备选 paper 是 *"Why current music FMs saturate under uniform process reward"*。
  - **Status 2026-05-23**：inactive fallback outline exists at `papers/explainers/SATURATION_PAPER_OUTLINE.md`; H1 did not fail.

- **(d) Bayesian power analysis 防 false-negative**: 当前 n=3 seed × 256 prompt。若效果 +0.05 真实存在，所需 N ≈ 30 seed × 256 prompt 才达 80% power。
  - **Conditional**：若 M1a 末端 r1-r0 effect 在 0-0.5 SD 之间（borderline），花 100 GPU-h 加跑 12 个 extra seeds 而不是直接判 fail。

- **(e) Multi-prompt-set sanity check**: 当前 dev/held-out 同分布。若 H1 borderline，临时 pull 100 个 MusicCaps OOD prompts 跑 r0/r1/r2 → 如果在 OOD 上 r2_bon ≫ r0 但在 dev/held-out 上不显著，说明 dev/held-out 设计需修；不是 H1 本身错。
  - **Conditional**。

### R2 (Tweedie unreliable)

- **(a) 重新推导 flow-matching 版 Tweedie**: 对 rectified-flow ACE-Step，公式应为 `x̂_0 = x_t - t · v_θ(x_t, t)`（velocity field 形式），不是 DDPM 的 `(x_t + (1-α_t) ε_θ) / α_t`。
  - **Status 2026-05-23**：completed. `orbit-research/TWEEDIE_DERIVATION_NOTE.md` is resolved for ACE-Step clean-target formula.

- **(b) D3 reconstruction sanity 升级为 Phase B gate**: 当前 launch_phase_a.sh M0 段把 D3 DEFERRED。在 Phase B kickoff 时把 D3 重新激活，跑 K=4 个 checkpoint × 16 prompt 的 reconstruction Spearman 测试。若 Spearman < 0.7 → Tweedie 不可用，退回 outcome reward。
  - **Status 2026-05-23**：superseded by captured-v parity + Phase B.1 sigma-curve reliability run. H2 verdict is `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES`.

- **(c) Empirical value-head 兜底**: 若 (a)(b) 失败，训一个 small MLP value head 接到 ACE-Step 中间 latents 上，监督拟合 final reward → 用 head 输出当 process signal。绕开理论 Tweedie。
  - **Fallback**——需 Phase B 末预留 200 GPU-h。

- **(d) Paper 降级路径**: 若 Tweedie 彻底不行 + value head 不收敛，paper claim 从 *"M-PRM"* 降级为 *"M-OR (Musically-structured Outcome Reward)"*——保留 H3/H5/H6 这三大 novelty，丢掉 H2。
  - **Fallback**：plan B 论文骨架。

### R3 (Reward hacking)

- **(a) Probe 全员 lock-in，post-train ≤ 1.5× pre-train**: silence_fraction / autocorr_repetition / hf_artifact_score 已接入。
  - **Now-actionable**：在 `configs/eval/gate_v1.yaml` 加 `probe_post_train_max_ratio: 1.5`，超过即 reject policy。

- **(b) Adversarial robustness eval pre-submission（强制）**: 每个 trained policy 生成 100 audio → 抽 10% 人耳 pair-comparison vs real music。若 reward ranking 与 human ranking Kendall-τ < 0.4 → 判 reward hack，重新 train。
  - **Now-actionable**：Phase A.aux 已设计，预算 ~50 GPU-h + 5 listeners × 5h labour。

- **(c) Off-distribution prompts as canary**: 5 个 canary prompts（"silence"、"chaos"、"copy real song"、"reverse audio"、"single tone"）跑过每个 policy → 期望 reward 输出明确分布。若 canary fail → policy 有 invariance bug。
  - **Now-actionable**：写 `tests/canary_prompts.jsonl` + `tests/test_policy_canaries.py`。

- **(d) Dual reward stack check**: 主训练用 `gate_v1` reward。Phase D ablation 加 `gate_v2`（不同 reward 模型组合，如 MusicCaps-CLAP + AudioLDM-eval）跑 eval。若 gate_v1 ↑ + gate_v2 ↓ → reward hack 特定 v1。
  - **Conditional**（Phase D budget）。

- **(e) Periodic Codex MCP review**: 每周 5 个新 audio sample → Codex review for "this sounds weird"。早期发现 perceptual mismatch。
  - **Now-actionable**：每周 cron via `/loop`。

---

## 2) 严重级对冲

### R4 (Statistical power)

- **(a) Paired analysis (prompt-aware)**: 替代独立 t-test。对每个 prompt p：`Δ(p) = gate(r1, p, seed_avg) - gate(r0, p, seed_avg)`。然后对 256 个 Δ 做 one-sample t-test。Pair structure 去掉 between-prompt variance → power 高 5-10×。
  - **Now-actionable**：改 `scripts/compute_headroom_gate.py` 加 paired test option。

- **(b) Bootstrap CI per metric**: 1000-iter bootstrap (sample 256 prompts × 3 seeds with replacement) → 每 rung × axis 出 95% CI。
  - **Now-actionable**：加到 compute_headroom_gate 或 `/analyze-results` skill。

- **(c) Pre-registered effect size**: M1a finals 出齐前，PI 在 `HEADROOM_GATE_DECISION.json` 写死 "minimum effect of interest = +0.05 absolute gate_r_lcb"。事前固化，避免后期 p-hacking。
  - **Now-actionable**：PI sign-off ASAP（M1a dev 跑完前）。

- **(d) Multiple comparison correction (Bonferroni / BH)**: 5 rungs × 7 axes = 35 tests。报 raw p AND BH-corrected q。
  - **Now-actionable**：加到 paper draft 的 table 模板。

### R5 (λ 权重是配的)

- **(a) Phase D λ-sweep ablation**: λ_wer ∈ {0, 0.1, 0.3, 0.5, 1.0}, λ_probe ∈ {0, 0.2, 0.5} 笛卡尔。预算 ~200 GPU-h。
  - **Conditional**（Phase D 末若 budget 紧，砍最不敏感的）。

- **(b) Sensitivity analysis in paper**: 即使 sweep 没全做，至少 report "claim X holds for λ_wer ∈ [0.2, 0.4]"。承认 sensitivity 比假装没问题好。
  - **Now-actionable**：paper template 加 sensitivity section。

### R6 (A800 数值漂移)

- **(a) Reproducibility canary**: 同 config 跑两次 → 报 |gate(run1) - gate(run2)|。该数应远小于 |gate(r1) - gate(r0)|。
  - **Now-actionable**：Phase A.aux 末加这个 canary，~10 GPU-h。

- **(b) BoN ranking stability check**: 对 r2_bon，记录每个 prompt 的 8 个候选的 reward ranking。重跑后 Spearman ranking correlation 应 > 0.9。
  - **Now-actionable**：~10 GPU-h，Phase A.aux 加。

### R7 (Phase C training 失败)

- **(a) Checkpoint frequent + KL guard**: 每 100 RL step save，KL(π‖π_ref) > 2.0 abort。
  - **Now-actionable**：在 `src/mprm/baselines/r6/r7/r8` 训练 loop 加。

- **(b) Conservative anneal schedule**: β_KL 从 0.05 退到 0.001，慢慢放开。
  - **Now-actionable**：scheduler 模板。

- **(c) Curriculum (easy prompts first)**: 用 r0_base 的 gate_r_lcb 给 prompts 排序，先 train top-quartile easy → 退到 full distribution。降低早期梯度方差。
  - **Now-actionable**：训练 dataloader 改造。

- **(d) Supervised distillation fallback**: 若 RL training 2× 失败（600 GPU-h 烧掉），生成 BoN-selected pool → SFT on this pool。Paper claim 降级但有结果。
  - **Fallback**。

- **(e) Early stopping on val gate_r_lcb plateau**: 5 epoch 没涨 → stop。避免 over-train degeneration。
  - **Now-actionable**。

---

## 3) 工程级对冲

### R8 (网络回退)

- **(a) 已部署**: `tools/predownload_reward_weights.sh` + launch_phase_a.sh 自动 export LAION_CLAP_* / AUDIOBOX_AES_CKPT / MERT_LOCAL_PATH。
  - **Now-actionable** ✓ done。
- **(b) Periodic file integrity check**: `find ~/HDD_POOL/source -size -1M` 找半下载文件清掉再重 prefetch。
  - **Now-actionable**：bi-weekly cron。

### R9 (_attach silent)

- **(a) Per-perturbation tqdm**: 在 `_attach_r_lcb` / `_attach_gate_r_lcb` 加 tqdm。每 perturbation 一行 log。
  - **Now-actionable**：Phase B 前必修。

- **(b) Watchdog 30-min mtime**: orchestrator 每 5 min 巡逻 per-task log mtime，stale > 30 min + GPU 0% util → 标 deadlock，warning（先不 kill）。
  - **Now-actionable**：加到 `scripts/m1a_run_parallel_rungs.py`。

- **(c) Snapshot intermediate**: `_attach` 每 20 perturbation 做一次中间 results.jsonl 写盘。crash 恢复用。
  - **Conditional**（仅 (a)(b) 不够时）。

### R10 (held-out 同分布)

- **(a) OOD probe set**: Phase A.3 head-to-head 用 50 个 MusicCaps OOD prompts → 报 in-dist gate vs OOD gate。
  - **Now-actionable**：PI approve OOD prompts。

- **(b) Diversity metric on dev/held-out**: 用 CLAP embedding 算 dev vs held-out 的 pairwise distance distribution → 看是否真 disjoint。
  - **Now-actionable**：~1 GPU-h。

### R11 (Novelty overlap with recent work)

- **(a) 早跑 /novelty-check**: Phase A 完工后立刻跑 ORBIT `/novelty-check`，扫近 6 个月 arXiv preprint + ICASSP/NeurIPS/ICML papers，专注 "process reward audio generation"、"section-level reward music"、"CVaR audio RL" 三个关键词组。
  - **Now-actionable**：M1a 完工 → 跑 /novelty-check + /research-lit。

- **(b) Differentiation matrix 写进 paper §2 Related Work**: 对找到的每个前置工作，列 dimension table 比较 (process granularity / section-aware / robust-LCB / CVaR / lyric guard)。证明我们是 first 整合者。
  - **Now-actionable**：写 paper-draft 前 prepare。

- **(c) Defensive citation strategy**: 即使前置工作部分重叠，主动 cite + position as "we build on ... and extend to ..."。Reviewer 不会因此 reject。
  - **Now-actionable**：写作时贯彻。

- **(d) Pre-print 抢时间**: Phase A 末出 preliminary results 就发 arXiv，建立 priority date。即使别人后来发了类似的，我们有 priority。
  - **Conditional**（仅 H1 PASS + Phase A.aux 数据 positive 时触发）。

### R12 (SLURM 不稳)

- **(a) Frequent state save**: per-seed dir + RUN_LEDGER 高频 append。已设计，trap 已加。
  - **Now-actionable** ✓ done。

- **(b) Vast.ai mirror as DR**: 若 Paratera maintenance > 24h，把 conda env tarball + ckpts rsync 到 vast.ai。$3-5/hr cost。
  - **Fallback**。

---

## 4) 跨切对冲（cross-cutting）

- **(a) Bi-weekly Codex MCP review**: 用 `mcp__codex__codex` 跑：ledger + interpretation + claims review。catches: H1 false-positive, reward hack 迹象, statistical mis-interpretation。
  - **Now-actionable**：周三 cron via `/schedule`。

- **(b) Phase A.aux human eval scaling up**: 当前 proposal 是 5 listeners × N pairs。若 budget 允许扩到 10 listeners + paired comparison + ICC（inter-rater）报告。Reviewer 必问。
  - **Conditional**（取决于 human-eval budget）。

- **(c) Pre-registration on OpenReview**: Phase A 全 done 后，把 H1-H6 锁死的 hypothesis + metric + threshold post 到 OpenReview 公开 pre-reg。投稿时引用。
  - **Now-actionable**：Phase A 完工后。

- **(d) Negative outcome paper draft**: 见 R1(c)，`SATURATION_PAPER_OUTLINE.md`。
  - **Status 2026-05-23**：inactive fallback only; H1 passed.

- **(e) Public artifact release plan**: code + ckpts + reward harness 全 open。Reviewer 友好。
  - **Now-actionable**：Phase A 末做 release checklist。

---

## 优先级排序（按时间 / 杀伤力 / 实施难度）

| # | 对冲 | 风险 | 实施时机 | 难度 |
|---|------|------|---------|------|
| 1 | **per-perturbation tqdm + watchdog** | R9 | Phase B 前 | 低 (1 天) |
| 2 | **paired analysis + bootstrap CI in headroom_gate** | R4 | M1a 完工前 | 低 (2 天) |
| 3 | **Pre-reg effect size in HEADROOM_GATE_PREREG** | R4, R1 | DONE 2026-05-21 | 完成 |
| 4 | **Tweedie 重推导 + H2 reliability** | R2 | DONE 2026-05-23 | 完成 |
| 5 | **Saturation paper outline (1 页)** | R1 | inactive fallback | 完成 |
| 6 | **Probe lock-in + adversarial eval** | R3 | Phase A.aux | 中 (3 天) |
| 7 | **Bi-weekly Codex review cron** | 跨切 | now | 低 |
| 8 | **OOD canary prompts** | R10 | Phase A.3 | 中 |
| 9 | **Phase C training guards (KL/checkpoint/curriculum)** | R7 | Phase C kickoff | 中 |
| 10 | **Sensitivity sweep** | R5 | Phase D | 中 |

---

## 时间窗与触发条件总表

| 触发条件 | 立刻执行 |
|---------|----------|
| M1a finals 出齐前 24h | hedge #3 (pre-reg effect size) |
| M1a finals 出齐后 24h | hedge #2 (paired test + bootstrap) + hedge #5 (saturation outline) |
| H1 borderline (r1-r0 ∈ [0, 0.5 SD]) | R1 hedge (d), (e) |
| Phase B kickoff 前 | hedge #4 (Tweedie 重推导) + hedge #1 (watchdog/tqdm) |
| Phase A.aux 启动 | hedge #6 (adversarial eval + canary) |
| Phase C kickoff 前 | hedge #9 (KL guard + curriculum + early stop) |
| Phase D 末 | hedge #10 (λ sweep) |
| Paper draft 阶段 | R5(b) sensitivity section, R4(d) BH-correction tables |
| 投稿前 | hedge (c) OpenReview pre-reg |
