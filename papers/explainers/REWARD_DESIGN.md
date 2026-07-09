# M-PRM Process Reward 设计

*写于 2026-05-19；用于解释 paper 的 reward formulation*

## Outcome reward vs Process reward 的根本区别

**Outcome reward**（baseline RL 做法）：
```
audio = generate(prompt)       # 一次性生成完整音频
reward = score(audio)           # 一个分数，覆盖整段
gradient ∝ reward * ∇log p(audio | prompt)
```
反馈太粗——模型不知道改哪一帧 / 哪一段。

**Process reward**（M-PRM）：
```
for t in [10, 20, 30, 40, 50]:                  # 多个中间步
    audio_t_hat = tweedie_decode(x_t)            # 用 Tweedie 公式预测最终音频
    section_rewards_t = score_per_section(audio_t_hat)  # 按段落给分
    advantage_t = section_rewards_t - baseline_t
    gradient_t = advantage_t * ∇log p(x_t)        # 只更新和这个段落、这个时间步相关的参数
```

每个反向传播信号**定位到时间 × 空间**双重细分。

## 五个机制（与 H2-H6 一一对应）

### H2 — Tweedie reliability（中间步可预测最终质量）

Tweedie 公式：给定 diffusion 第 t 步的 noisy latent `x_t`，可以"短路"预测最终的 `x_0`：

```
x̂_0(t) = (x_t + (1 - α_t) · ε_θ(x_t, t)) / α_t      # 经典 DDPM
                                                        # 或 flow-matching 等价形式
```

意义：**不用跑完 50 step 才能打分**——在第 10、20、30 步用 Tweedie 解码出来的近似音频已经能反映"这次生成走得对不对"。

**Reward 设计**：
- 在 K=4 个 checkpoint 时刻（如 t = 10, 25, 40, 50）调用 reward 模型
- 计算 reward(x̂_0(t))
- 这是 process reward 在**时间维度**的颗粒度（4 个 step 一个反馈，而不是只有最终 1 个）

Phase B 要验证：Tweedie 预测 quality 在 t=20 时和 t=50 时的 reward Spearman 相关系数足够高（≥0.7），才能用来做 process reward 信号。

### H3 — Section credit（按段落分配信用，而非全局平均）

用 **MERT embeddings** 计算音频的 self-similarity matrix，自动检测段落边界（前奏 / 主歌 / 副歌 / 桥段 / 尾奏）。

**Reward 设计**：
```python
sections = mert_segment(audio)
# 例: [intro: 0-4s, verse: 4-15s, chorus: 15-25s, outro: 25-30s]
for s in sections:
    section_audio = audio[s.start : s.end]
    section_reward[s] = clap_score(section_audio, prompt)
                      + audiobox_pq(section_audio)
                      + mert_coherence(section_audio)
                      - λ_wer * whisper_wer(section_audio[vocal_track])
```

这是 process reward 在**空间维度**的颗粒度（每段落一个反馈）。

Phase C 要验证：用 section_reward 训练 vs 用 outcome_reward 训练，**section_reward 收敛快 + 最终质量更高**。

### H4 — Locality（局部优势，避免连带破坏）

Naive process reward 有个 bug：奖励"修副歌"的梯度可能也调动了"前奏"的参数（因为 attention 是全局的）→ **修一处坏另一处**。

**Reward 设计** — Locality constraint:
```
advantage[t, s] = section_reward[s] - baseline[s]
# 梯度只回传到 generates section s 的时间步
gradient_per_section[s] = advantage[s] · ∇log p(x_{t in time_range(s)})
```

操作上用 **time-window attention masks**：在更新副歌的 token 时，前奏 token 的梯度被掩盖。

Phase D 要验证：加 locality vs 不加，前奏段落的 quality 是否被保护住（无衰减）。

### H5 — Lyric guard（保护歌词清晰度）

风险：模型为了拉高 aesthetic_pq（音质美感），把人声混音压低、加大 reverb → 歌词糊掉 / Whisper-WER 暴涨。

**Reward 设计** — Lyric guard:
```
r_lcb = main_reward - λ_wer · max(0, wer - wer_baseline)
```
WER 一旦超过 baseline 阈值就开始罚。`λ_wer` 大到能压住 aesthetic_pq 的诱惑。

Phase E 要验证：加 lyric guard，WER 不退化（保持基线 ±5%），同时 aesthetic 涨。

### H6 — CVaR aggregator（关注最差段落，不是平均）

把多段 reward 聚合时，**用均值会被好段落掩盖坏段落**——平均看着 7.5/10，但实际上有一段 3/10（破音）。

**Reward 设计** — CVaR:
```
section_rewards = [r_intro, r_verse, r_chorus, r_outro]
sorted_low_to_high = sorted(section_rewards)
worst_α_fraction = sorted_low_to_high[: int(α * len(sections))]  # 取最差 α=20%
total_reward = mean(worst_α_fraction)                              # CVaR_20%
```

强迫模型修最弱段，而不是只优化平均。

Phase F 要验证：用 CVaR vs 用 mean，**最差段落 quality 是否提升**。

## 完整 reward 公式（合体后的 M-PRM）

```python
# 单步 t、单 prompt 的 process reward 计算：
x_hat_0 = tweedie_decode(x_t, t)                         # H2: Tweedie 中间步预测
sections = mert_segment(x_hat_0)                         # H3: 段落检测
per_section_lcb = {}
for s in sections:
    audio_s = x_hat_0[s.range]
    perturbations = [identity, crop, time_shift]         # 5 种 perturbation
    scores_under_pert = [
        weighted_avg(
            clap=λ_clap * clap_score(p(audio_s), prompt),
            audiobox=λ_aes * audiobox_pq(p(audio_s)),
            mert=λ_coh * mert_coherence(p(audio_s)),
            wer_guard=-λ_wer * max(0, whisper_wer(p(audio_s)) - wer_base)  # H5: lyric guard
        )
        for p in perturbations
    ]
    per_section_lcb[s] = min(scores_under_pert)          # robust lower-confidence bound
    # 减去 anti-hacking probes:
    per_section_lcb[s] -= λ_probe * (silence_frac[s]
                                   + autocorr_repetition[s]
                                   + hf_artifact[s])

# CVaR 聚合 (H6):
sorted_rewards = sorted(per_section_lcb.values())
total_reward = mean(sorted_rewards[: int(0.2 * len(sections))])  # 最差 20%

# Locality (H4): gradient 只回传到生成对应 section 的时间步
for s in sections:
    advantage[s] = per_section_lcb[s] - baseline[s]
    apply_gradient(x_{t in time_range(s)}, advantage[s])  # 仅这些 token
```

## 为什么这个组合是 paper 卖点

业界已有的工作：
- **Outcome RLHF for music**: e.g. MusicRL, MusicGen-RL — 整段打分，效果有限
- **Process reward in LLM** (PRM800K, Math-Shepherd): 按 reasoning step 打分——但**没人在音乐里做过**
- **CVaR / robust RL**: 有零散工作，但**没和音乐 section structure 结合**

**我们的 contribution**：把上面 5 个机制**第一次整合到 flow-matching music RL** 框架里，并通过 H2-H6 五个独立 ablation 证明每个 component 都贡献了。

paper 卖的是 **reward design 配方**，可以直接 copy 到其它 music backbone（SAO、MusicGen-v2 等）。
