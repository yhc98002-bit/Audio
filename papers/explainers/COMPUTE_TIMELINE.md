# 全量实验时间估算

*基于 2026-05-19 Paratera A800 8-卡 3-way oversubscription 的实测吞吐量*

## 当前实测速度

```
M1a dev (18 tasks)：
  - 5.5 h 完成 5/18 (28%)
  - 全部完成预计 ~18-22 h（受 r4_bon_cfg 24× sample 工作量主导）
  - M1a dev + held-out 合计 ~36-45 h ≈ 1.5-2 天
```

GPU-hours 实测：M1a 全部消耗 ~400-450 GPU-h（对照预算 Phase A 总 850 GPU-h，其中 M1a 占主要部分）。

## 按 proposal 预算分阶段（5,400 GPU-h 总）

| 阶段 | 预算 GPU-h | 并行性 | 预计 wallclock |
|------|------------|--------|----------------|
| **Phase A** (M0/M0.5/M1a/M1b/A.3/A.aux) | 850 | 高（batch audit，oversub 1.5-2×） | **3-5 天** |
| **Phase B** (Tweedie reliability + credit-unit pilot) | 650 | 中（部分 batch audit + 小训练） | **3-4 天** |
| **Phase C** (主 RL 训练) | 1800 | **低**（model update 强串行，几乎不能 oversub） | **9-12 天** |
| **Phase D** (ablations × 多 cell) | 1050 | 高（batch） | **3-5 天** |
| **Phase E** (locality probe) + **Phase F** (CVaR aggregator) | ~250 | 中 | **2-3 天** |
| Harness 开发 + 调试 + 数据 pipeline | 350 | 低（互相依赖） | **3-5 天** |
| 反工 / 重跑（pivot / 修 bug） | 450 | — | **3-5 天** |
| 储备 buffer | 250 | — | — |

## 现实时间估算

**纯计算时间**（24/7 不停）：
- 8× A800 持续跑：**25-40 天**（4-6 周）

**加上人工干预 + paper writing**：
- 实验跑完：4-6 周
- Paper writing（含 figure / Codex 审稿 / 重跑响应 reviewer）：4-8 周
- ICLR/NeurIPS 投稿 + rebuttal 周期：1-2 月

**整体到投稿**：**3-5 月**（与 proposal 的 148 天 ≈ 5 月预算吻合）

## 影响速度的关键变量

**变慢**（高概率）：
- Phase C 训练实际比预算慢——RL post-training 收敛慢、需要多 seed
- H2-H6 中 1-2 个失败 → 需要 pivot + 重设计实验
- Reviewer feedback 要求新实验
- Paratera SLURM 排队、维护、节点 drain

**变快**（低概率）：
- 早期 Phase A/B 失败明确 → 转 saturation paper（短得多）
- Codex review 提前发现重大问题 → 减少 rerun
- M1a/M1b 信号清晰 → Phase D 可砍掉部分 ablation

## 风险因素：M1a 已消耗 ~5% 总预算

当前 5.5 h 烧 ~28 GPU-h。Phase A 总 850 GPU-h ÷ 28 = 30 倍当前耗速。M1a 完整大概再要 30-40 h 烧到 200 GPU-h。

**如果 M1a gate 失败**（即 r1/r2/r4 不显著高于 r0+r9）：5400 GPU-h 预算大部分都不会花，研究方向需要重构——但这是 NULL_RESULT_CONTRACT 设计好的兜底，**不算"超时"**，是"提前止损"。

## TL;DR

当前 oversubscription 速度下，**全套实验跑完到投稿大约 3-5 个月**（4-6 周纯实验 + 后续 paper + 投稿），跟 proposal 的 148 天预算一致。最大不确定性是 Phase C 的 RL 主训练（占 33% 预算），M1a gate 决定要不要走到那一步。
