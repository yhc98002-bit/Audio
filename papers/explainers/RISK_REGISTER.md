# Risk Register — Headroom-Gated M-PRM

*写于 2026-05-19；Phase A M1a 跑到 8/18 finals 时盘点的项目风险。Hedge 策略见 `HEDGE_STRATEGIES.md`，本文档只列 "What could go wrong"。*

**Status refresh (2026-05-23):** Phase A H1 gate passed after PI spot-check. Phase B.1 H2
returned canonical 128-prompt `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES`. The remaining
paper-critical open risk has shifted toward H3 credit-unit comparison and later Phase C
training, not the initial headroom/Tweedie formula gates.

按"杀伤力 × 概率"分 4 层：致命 / 严重 / 工程 / 外部。

---

## 🔴 致命级（杀掉整个 paper）

### R1. H1 fail — 基线模型没 headroom

- **Mechanism**: 若 M1a 跑完发现 r1/r2/r4 跟 r0_base 没显著差异 + r9 也跟 r0 不分上下 → ACE-Step 在我们的 reward harness 下**已经饱和**，RL 训不动。整个 M-PRM 方法论失去标的。
- **Current evidence (2026-05-23)**: Phase A gate passed after PI audio spot-check.
  `HEADROOM_GATE_DECISION.json` ended `pass_gate=true`; r2_bon and r4_bon_cfg both
  cleared the pre-registered headroom criterion. R1 is no longer an active blocker.
- **Probability**: low for the current project state; keep saturation pivot only as fallback
- **Damage**: 全 paper 重新构思；触发 NULL_RESULT_CONTRACT.md §1 转 saturation paper
- **Detection signal**: M1a held-out gate-critical finals 出齐后，r2_bon - r0_base ≤ 0.5 SD AND r4_bon_cfg - r0_base ≤ 0.5 SD

### R2. H2 Tweedie 不可靠

- **Mechanism**: M-PRM 用 Tweedie/clean-target 公式从 diffusion 中间步预测最终音频质量。如果公式或 sampler branch 错，process-reward signal 会变成伪相关。
- **Current evidence (2026-05-23)**: formula path is resolved in `orbit-research/TWEEDIE_DERIVATION_NOTE.md`; captured-v parity passed under branch-aware effective velocity; Phase B.1 128-prompt H2 verdict is `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES`.
- **Probability**: low for H2 reliability; residual risk is whether this reliable intermediate signal transfers into H3 credit-unit comparison and Phase C training.
- **Damage**: if later H3/Phase C fails, paper narrows to H2 characterization or credit-unit negative study rather than losing the entire Tweedie result.
- **Detection signal**: H3 section credit fails to beat non-section credit units, or Phase C M-PRM cannot convert the H2 signal into trained-policy gains.

### R3. Reward hacking

- **Mechanism**: M-PRM 用多模态聚合 reward（CLAP + Audiobox + WER + MERT + ...）。模型可能学到对抗输出——人耳烂但 reward 高。已知攻击：伪静音（拉 Audiobox PQ）、拷贝重复段落（拉 CLAP）、高频伪影（让 Whisper "听清"）。
- **Current evidence**: anti-hacking probes 已接入；`off_prompt_distance` 已被 PI 砍（STOP-B-7.1 Q1），`broken_section_indicator` deferred 到 Phase A.4——防护面比 proposal 设计的窄
- **Probability**: 60-70% 至少出现 1 种新 hack
- **Damage**: reviewer 重做要求，paper 撤稿风险
- **Detection signal**: Phase A.aux human eval Kendall-τ(reward ranking, human ranking) < 0.4

---

## 🟡 严重级（削弱 paper 但不致命）

### R4. 统计 power 不足 — n=3 seed 太少

- **Mechanism**: r0_base SD=0.141 在 gate ~2.0 量级 → CV ~7%。要检测 +0.05 effect 需要 ~30 seeds 才有 80% power，我们只有 3。
- **Current evidence**: r0_base seed2 / r1_cfg seed2 / r9 seed2 三个 rung 在 seed2 上同步偏低 → 强烈暗示 **seed-specific batch effect** 而非随机噪声。3 seeds 不够分离 batch 效应 vs method 效应。
- **Probability**: 80%（基本必然 reviewer 会问 "why 3 seeds")
- **Damage**: 削弱所有 claim，特别是 H1
- **Detection signal**: 任何 t-test p > 0.10 时 reviewer 会跳出来

### R5. 多 reward axis 权重 (λ) 是配的

- **Mechanism**: `gate_v1.yaml` 里的 `lambda_probe`、`reward_axes` 权重是 PI 拍脑袋选的（CODEX_PHASE_4_CALIBRATION 期间）。Reviewer 会问"为什么 λ_wer=0.3 而不是 0.5？sweep 了吗？"
- **Current evidence**: 没扫
- **Probability**: 80%（标准 reviewer ask）
- **Damage**: 削弱 robustness claim
- **Detection signal**: Phase D ablation 缺 λ-sweep

### R6. A800 vs sichuan/pro6000 数值差异在 BoN/CFG 上可能放大

- **Mechanism**: r0_base 数值跟 sichuan 差异 <0.5%（fp 噪声级）。但 BoN/CFG sweep 涉及 best-of-N selection——noisy ranking 容易翻牌。
- **Current evidence**: r1_cfg_sweep seed0/seed1 A800 vs sichuan 差异 <0.2%（看起来稳）；r4_bon_cfg 无 sichuan 对照
- **Probability**: 30%（轻度）
- **Damage**: 跨 cluster reproducibility claim 弱
- **Detection signal**: 同 config 重跑两次的 gate_r_lcb 差异 > 0.05

### R7. Phase C 训练 1800 GPU-h 单点失败

- **Mechanism**: 33% 预算压在 Phase C 一个块。RL post-training 公认不稳——KL 飞掉、灾难性遗忘、奖励崩溃。若训练发散需要重训。
- **Current evidence**: 还没到 Phase C
- **Probability**: 60-70%（至少 1 次需要 restart）
- **Damage**: 期望浪费 17% 总预算
- **Detection signal**: Phase C 训练曲线 KL(π‖π_ref) > 2.0 OR val gate_r_lcb 持续下降 > 5 epoch

---

## 🟢 工程级（可挽救但烦人）

### R8. Reward 模型 load 时网络回退

- **Mechanism**: laion_clap module-level loads bert/roberta/bart 时，shim 路径不命中 → 回退网络下载 → 在 compute 节点超时。
- **Current evidence**: 已规避——预下载到 `~/HDD_POOL/source/`，shim 走本地
- **Probability**: 10%（残留风险：权限 / 文件损坏 / 部分下载）
- **Damage**: 卡住整个 _attach phase
- **Detection signal**: 某次 import laion_clap 报 connection timeout

### R9. `_attach` perturbation 重打分 silent 阶段没监控

- **Mechanism**: launch_baseline.py `_attach_r_lcb` / `_attach_gate_r_lcb` 阶段 silent，stdout 不更新可能 100+ min。如果数值不稳出 NaN→inf loop 我们看不见。
- **Current evidence**: r0_base seed2 silent 113 min 期间无法判断进度；seed1 silent 130+ min
- **Probability**: 30%
- **Damage**: 局部重跑（per-task），但每个 task ~3-5h GPU-h
- **Detection signal**: 任务 mtime stale > 60 min + GPU 0% util + process 仍存活

### R10. Held-out 跟 dev 同分布

- **Mechanism**: 256 dev + 256 held-out 是 PI 在 STOP-B-8 Phase-1 同批 generate 的，prompt-generation 流程同一个，可能分布太接近——"held-out" 实际不是真正的 OOD。
- **Current evidence**: 未做 distribution distance check
- **Probability**: 50%（design 看，可能严重）
- **Damage**: generalization claim 站不住
- **Detection signal**: CLAP-embedding 算 dev vs held-out pairwise distance < intra-set distance

---

## ⚪ 学术 / venue 风险

### R11. Process reward in music 不算 novel

- **Mechanism**: reviewer 可能拉出 MusicLM/MusicGen 的某 followup 或 ICASSP 最近 preprint 做了类似 section reward，或 Anthropic CAI 思路也算 process reward。
- **Current evidence**: novelty-check 还没跑（Phase A 末才做）
- **Probability**: 40%（取决于近 3 个月 preprint）
- **Damage**: 强 reject (novelty insufficient)
- **Detection signal**: ORBIT `/novelty-check` 跑出 ≥ 3 个直接前置工作

### R12. 148 天预算被 Paratera 维护吃掉

- **Mechanism**: `sinfo` 显示 8 个 ai partition 节点 drain*（已 drain），18 个 drng（drain pending）。实际可用节点也许 < 30%，且经常调整。若实验中断，SLURM 排队几小时。
- **Current evidence**: 当前 job 90074 连跑 ~6h 未中断，但 long-run 风险存在
- **Probability**: 70%（至少出现 1-2 周时间稀释）
- **Damage**: paper timeline 推迟 1-2 月
- **Detection signal**: job 90074 被强制 cancel 或所有 ai partition 节点同时 drain

---

## 风险 × 当前数据 sanity 表

| 风险 | 概率 | 杀伤力 | 当前是否触发？ |
|------|------|--------|---------------|
| R1 H1 fail | Low post-Phase-A | 全 paper | CLEARED: Phase A gate passed |
| R2 Tweedie | Low for H2; residual for H3/Phase C | 失去/缩窄 process-reward claim | CLEARED for formula + H2 reliability; watch H3/Phase C |
| R3 Reward hacking | 60-70% | reviewer 重做 | Phase A 还未训 policy，未触发 |
| R4 Power 不足 | 80% | 削弱 claim | seed2 异常已是预警 |
| R5 λ 拍脑袋 | 80% | 削弱 robustness | 未触发但确定要 hedge |
| R6 数值漂移 | 30% | reproducibility | r0/r1 数值匹配 sichuan，OK |
| R7 Phase C 训练事故 | 60-70% | 重烧 17% 预算 | 未到 |
| R8 网络回退 | 10% | 局部卡死 | 已 hedge |
| R9 _attach silent | 30% | 局部重跑 | r0_base 113 min silent 已现象 |
| R10 held-out 同分布 | 50% | generalization 弱 | 未触发 |
| R11 novelty 重叠 | 40% | reject | novelty-check 未跑 |
| R12 SLURM 不稳 | 70% | 时间稀释 | 当前稳，但 drain 节点多 |

---

## Known Issues — discovered post-M1a (2026-05-21)

### K1. Base ACE-Step seed-2 silence bug

- **Mechanism**: Base ACE-Step (R0) sampling occasionally produces audio with long silence segments, concentrated on seed 2 across multiple prompts.
- **Evidence**: PI Phase A.4 spot-check 2026-05-21 (`runs/m1a_spot_check_verdicts_2026-05-21.json`) flagged held-out prompts with seed-2 silence:
  - `held_out_0101` seed 2 base: first 30 seconds completely silent
  - `held_out_0092` seed 2 base: mostly silent
  - `held_out_0054` seed 2 base: silent section in audio
  - `held_out_0163` both seeds: silence-related quality issue
- **PI recommendation (verbatim)**: "run a pipeline to check if similar silence issues are widespread".
- **Disposition (PI decision 2026-05-21)**: record as Known Issue; **defer the systematic silence-sweep to Phase B kickoff**. M1a gate not blocked (PI confirmed audible improvement majority — 27/32 bon_better despite silence outliers).
- **Action when handled (Phase B kickoff)**: scan all 256 held-out × 3 seeds r0_base audio for `silence_fraction > 0.3` (per `gate_v1.yaml` probe threshold). Cross-reference seed distribution. If seed 2 systematic, that's an ACE-Step inference-seed bug worth upstream filing.
- **Damage**: low — base policy is the control, not the proposed method. Could be cited in paper as motivation for M-PRM's `silence_fraction` anti-hacking probe being load-bearing.

### K2. Base ACE-Step prompt-adherence weakness

- **Mechanism**: Base ACE-Step occasionally fails prompt-adherence on lyric-bearing prompts (generates instrumental-only despite prompt asking for vocals).
- **Evidence**: PI Phase A.4 spot-check flagged `held_out_{0105, 0161, 0202, 0108, 0124, 0032, 0043}` with notes including "both hard to follow the prompt: no lyrics, why it happen?" and "is it a worthy scientific question?"
- **PI observation**: even when both base and BoN fail prompt adherence, BoN is consistently preferred for musical quality.
- **Disposition (PI decision 2026-05-21)**: Known Issue; deferred to Phase B kickoff. **Material for paper limitations section** — "base ACE-Step prompt-adherence is imperfect on a subset of held-out prompts; BoN selection compensates partially; M-PRM may not fully recover prompt-adherence if reward stack does not score adherence highly".
- **Action when handled**: at Phase A.aux 升级 OR Block A.aux pilot expansion, label per-prompt "prompt-adherence" axis from human eval; track which prompts both base AND BoN fail; consider as a credit-unit confound.
