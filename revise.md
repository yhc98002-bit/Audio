Final Plan: Early Trajectory Verifiers for Flow-Matching Music Generation
4.1 论文主线

论文不是 “剪枝技巧”，而是：

Flow-matching 音乐生成中的早期轨迹状态已经携带最终质量信号；我们将其形式化为 early trajectory verification 问题，并提出 risk-aware pruning / compute allocation 方法。

最终主张：

1. 早期轨迹可预测最终质量；
2. 原始 Early-Tweedie reward 已经能做强剪枝；
3. Learned early trajectory verifier 能进一步提升 same-compute selection；
4. 这种方法在显著减少计算的情况下接近 full BoN；
5. 音乐短片段质量差异呈全局持续性，这解释了为什么 early pruning 有效。
5. 核心方法设计
Method 1：Raw Early-Tweedie Pruning

作为强 baseline。

输入：

x_σ, v_θ, prompt

计算：

x̂₀ = x_σ − σv_θ

解码 early audio，打分，按 score 剪枝。

固定 schedules：

Schedule A:
σ=0.9 keep top4
σ=0.7 keep top2
final select top1

Schedule B:
σ=0.8 keep top4
σ=0.7 keep top2
final select top1

Schedule C:
σ=0.8 keep top6
final select top1

Bottom-prune:
σ=0.7 remove bottom25%
continue rest
Method 2：Early Trajectory Verifier, ETV

这是主方法。

学习一个 value / verifier：

V_σ(candidate, prompt) → final quality / final rank / top-k survival probability
输入特征

不直接训练大音频模型，先用稳健特征：

early reward vector at σ=0.9/0.8/0.7
reward slope: r_0.7 - r_0.9
early rank within prompt
prompt type: vocal / instrumental
CLAP / Audiobox / MERT scores if available
uncertainty features

可选加入 frozen embeddings，但不做大模型训练。

目标

三个目标都做：

1. final robust-LCB regression
2. final rank within BoN group
3. final top-k / winner survival classification
模型

按层级：

Linear / logistic baseline
GBDT / LambdaMART / pairwise ranker as primary
Small MLP optional appendix

不要为了 fancy 上大模型。
真正高级的是：

within-prompt ranking + risk-controlled pruning
Method 3：Risk-controlled adaptive pruning

把 ETV 输出转成剪枝策略。

核心不是固定 keep top4，而是控制误杀风险：

P(prune final top-1 candidate) ≤ ε

报告不同 ε：

ε = 1%, 3%, 5%

对应：

compute saved
reward retained
winner retention
false-negative

这会让方法从 heuristic 变成：

risk-aware trajectory pruning。

Method 4：Optional adaptive compute allocation

如果 ETV 足够好，做离线模拟：

confident bad → prune
uncertain → continue one more σ
confident good → retain

不一定作为主方法，可以作为 extension。

6. 实验计划
Experiment 1：Trajectory quality emergence

目的：

证明早期 σ 已经携带最终质量信号。

数据：

BoN-8 candidates
σ={0.9,0.8,0.7}
final reward

指标：

Spearman early vs final
winner retention
bottom false-negative
vocal/instrumental stratification

输出：

early quality emergence curve

这部分我们已有强结果，但要整理成 paper-grade。

Experiment 2：Same-compute pruning comparison

这是主实验。

比较：

Full BoN-8
BoN-4
Random prune
Raw ETP schedule A/B/C
ETV learned verifier
Risk-controlled ETV

指标：

reward fraction
compute fraction
exact winner match
top-2 retention
false-negative
regret

必须回答：

ETV/ETP 是否比同等 compute 的 BoN-4 更好？

如果不能赢 BoN-4，论文会弱。
如果能赢，这是核心结果。

Experiment 3：Cross-metric validation

避免 reward circularity。

选择用：

selection:
early verifier score

evaluation:
robust-LCB
aesthetic_pq
CLAP semantic
lyric/vocal constraints
MERT/coherence

至少要证明：

不是只在 aesthetic_pq 上好看
Experiment 4：Human spot-check

规模不需要大，但必须有。

设计：

32–64 pairs

比较：

Full BoN-8 vs ETP@50%
BoN-4 vs ETP@50%
Random prune vs ETP
ETP vs ETV if needed

指标：

overall preference
musicality
prompt fit
vocal/lyric issue

这是 ICLR 必需防线。

Experiment 5：Global quality mechanism

利用 time-uniform diagnostic。

核心图：

x: time window
y: reward
top-quality vs bottom-quality curves

指标：

between-song variance / within-song variance
globalness index
crossing frequency

目的：

解释为什么早期轨迹剪枝有效：质量差异是全局持续的，而不是孤立时间窗噪声。

Experiment 6：Failure analysis

必须做，增加可信度。

分析：

被 early prune 误杀的 final winners
late bloomers
ETV 失败案例
不同 genre / vocal / instrumental 的失败

如果 late bloomer 很少，这正好支持你的人工观察。

7. RL 结果怎么放？

不要隐藏，但降级。

写法：

We also evaluated whether the same process signals transfer to LoRA/GRPO post-training. The backend trains stably, but a first-wave comparison did not produce clear common-metric gains. This suggests that inference-time trajectory selection is currently a more robust use of early trajectory signals than direct RL post-training.

也就是说：

RL 是 boundary result，不是主贡献。

这比硬说 M-FixedWin 有效更好。

8. 论文结构
Title

推荐：

Early Trajectory Verifiers for Flow-Matching Music Generation

副标题可以是：

Trajectory-Aware Pruning for Efficient Music Generation
Abstract 核心句
We show that final music quality in flow-matching generation is often predictable from early Tweedie-clean estimates. We formalize this as early trajectory verification and use it for risk-aware candidate pruning, achieving near-full BoN quality at substantially lower compute.
Sections
1. Introduction
2. Background: flow matching, Tweedie clean estimates, BoN
3. Trajectory quality emergence
4. Early-Tweedie pruning
5. Early trajectory verifier and risk-controlled pruning
6. Experiments: same-compute quality Pareto
7. Human evaluation
8. Mechanism: global/persistent quality
9. Boundary: RL post-training first-wave
10. Discussion
9. 需要坚决避免的事情

不要再让论文变成：

H1/H2/H3/RL/FixedWin/Section/Pruning 全都讲一遍

这会很散。

最终论文里：

H1/H2 是铺垫；
H3 是动机/边界；
C1 RL 是 boundary；
Pruning + ETV 是主方法；
globalness 是机制解释。