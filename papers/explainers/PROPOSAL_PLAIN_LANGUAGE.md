# 通俗版研究提案（Headroom-Gated M-PRM）

*写于 2026-05-19；用于向非 ML 受众解释项目目标*

## 问题

AI 音乐生成器（比如 ACE-Step）能根据文字描述+歌词生成 20-30 秒的歌。**但它生成的歌不够好**——音质 OK，但缺乏"音乐感"：副歌不够爆、过渡突兀、人声混音不通透。

**问题**：能不能像 ChatGPT 用 RLHF 变聪明、图像模型用 DPO 变好看一样，**用 RL 让音乐模型变好听**？

## 我们的核心赌注

业界用 RL 训音乐模型几乎全是 "**outcome reward**"——给整段音乐打一个分（比如 7/10），告诉模型"你这次生成的整段挺好"。

但音乐天然有结构——前奏 / 主歌 / 副歌 / 间奏。整段打分丢了关键信息："**哪一段**好，**哪一段**差"。模型学不到具体该修哪里。

**我们的方法 M-PRM（Musically Structured Process Reward Modeling）**：奖励信号按音乐段落给——副歌 5/10、主歌 7/10、过渡 3/10。让模型知道**改哪里**，不是只知道**整体烂**。

类比：教学生写作文。
- Outcome reward：老师说"作文 7 分"——学生不知道哪段差
- Process reward：老师标出"开头 9 分、中间论证 5 分、结尾 8 分"——学生知道改中间

## 为什么先做 Headroom Audit（当前 Phase A）

**RL 训练贵**（5400 GPU-h 预算）。如果基础模型已经接近上限（**没 headroom**），上 RL 也涨不动，白烧 GPU。

所以**先用便宜的方法摸底**——这就是 M1a：
- 跑 256 个 prompt × 6 种生成方式
- 每种方式生成 audio 后用 reward 模型评分（CLAP 语义匹配 + Audiobox 美感 + Whisper 歌词清晰度 + MERT 段落连贯度）
- 看哪种方式能把分推高

**6 种方式（rungs）**：

| rung | 干啥 | 角色 |
|------|------|------|
| r0_base | 啥都不动直接生成 | 基线 |
| r1_cfg_sweep | 调 CFG 强度（让模型"更听话"） | **如果显著 > r0** → CFG 是有效杠杆 |
| r2_bon | 生成 8 次挑最好的 | **如果显著 > r0** → 模型有质量上限可以逼近 |
| r9_sampler_control | **负向对照**：换随机种子但不换 CFG | 应该 ≈ r0（否则 r1/r2 的涨是假的） |
| r3_robust_bon | 对小扰动鲁棒的 BoN | 测稳定性 |
| r4_bon_cfg | BoN + CFG 复合 | 上限组合 |

**Headroom Gate 决策**：
- 看 `gate_r_lcb`（lower-confidence bound of reward score）
- 如果 r1/r2/r4 显著高于 r0_base + 控制 r9 ≈ r0 → **有 headroom，进入 Phase B-F 的真正 RL 训练**
- 如果 r1/r2/r4 ≈ r0_base → **没 headroom**，研究方向重组（要么换 backbone，要么承认这个生成器已饱和）

## Phase B-F 在做啥（如果 Phase A 通过）

正式做 M-PRM RL，每个 phase 测一个关键假设：

| Phase | 测什么假设 |
|-------|------------|
| **B** | Tweedie reliability：能不能在 diffusion 中间步骤就预测最终音乐质量？（如果能，就能给中间步给奖励，更高效） |
| **C** | Section credit：把奖励按段落分（副歌 vs 主歌）比按整体分更好吗？ |
| **D** | Locality：改副歌不要把前奏改坏（reward 信号需要"局部生效"） |
| **E** | Lyric guard：提升音质不能牺牲歌词清晰度 |
| **F** | CVaR：最差的 10% 段落更重要——避免"平均听着行但有破音" |

## 最终 paper 卖什么

不是"我们做了 SOTA 音乐生成器"。

**而是："flow-matching music RL 的正确 reward 结构是什么"**——告诉学术界和工业界：当你想用 RL 训音乐模型时，process reward 应该按音乐结构来分、要有局部性、要保护歌词、要看尾部分位数。

**目标 venue**：NeurIPS / ICLR / ICML。

## 当前进度（2026-05-19 晚 9 点）

M1a dev 阶段 5/18 finals 出来；初步结果：
- r0_base mean gate_r_lcb = 2.081
- r1_cfg_sweep seed0 gate_r_lcb = 2.205（+5.9% vs r0，**CFG sweep 有效信号** ✓）
- r9_lite_s7 seed0 gate_r_lcb = 2.119（≈ r0，**负向对照行为正确** ✓）

正在跑：r2_bon / r3_robust_bon / r4_bon_cfg 的 sampling + _attach。预计明日中午全部 M1a finals 出齐。
