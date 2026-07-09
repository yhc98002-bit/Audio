# ADSR 项目 · 新研究员交接文档

**最后更新:2026-06-20** · 适合刚加入、对项目零了解的研究员
本文目标:看完后你能(a)理解我们在做什么、为什么这么做;(b)找到所有代码/数据/结果;
(c)自己跑起实验;(d)知道哪些坑别踩、哪些活值得做。

> **先读这 3 份(权威来源,本文是它们的导览):**
> 1. `CLAUDE.md` — 项目规则 + 环境 + 硬边界(**必读**)
> 2. `orbit-research/adsr_phase2_20260604/GATE_B_FINAL_REPORT.md` — 权威英文总报告(数字基准)
> 3. `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` — 原始 proposal;`experiment_plan_current.md` — 当前执行计划

---

## 1. 30 秒速览

- **做什么**:研究**推理期算力分配**,让文生音乐模型(ACE-Step v1.5)少犯"类型错误"。
- **方法**:ADSR(Axis-Deferred Speculative Restart,轴延迟·投机重启)——早期探测器发现轨迹要废 → 重启/延后/继续。
- **现状**:**核心实验(Phase 0–3)全部跑完,Gate B 已关闭**,判决 `SUPPORTED_TAIL_RESCUE`。当前无作业在跑。
- **结论一句话**:在"重采样救不回来的确定性尾部",**条件化重启**(改变生成条件,而非只换种子)显著有效。
- **你大概率的第一件事**:读完本文 → 看 ICLR 评估(§7)→ 从"下一步"里挑一个开工(instrumental 实验 / 第二骨干 / 帮 PI 跑人评)。

---

## 2. 研究背景与 proposal

**骨干模型**:ACE-Step v1.5(扩散 / flow-matching 音乐生成,30 步去噪,FlowMatchEulerDiscreteScheduler)。
跨骨干目标是 Stable Audio Open(尚未启动)。

**要解决的痛点 —— 类型错误(type error)**:
- 用户要**带人声** → 模型给了纯伴奏(vocal-miss);
- 用户要**纯伴奏** → 模型漏进人声(instrumental-leak)。
- 普遍率约 **23%** 的候选;而且标准 best-of-N 选择**改不掉**(选出的赢家里仍有 **19.9%** 类型错误)。

**ADSR 方法**:生成途中,在去噪到 **σ=0.8**(约第 12/30 步)时,用轻量探测器 **EVPD**
(Early Vocal-Presence Detector)判断轨迹会不会跑偏,然后三选一:
- **RESTART**:判定要废 → 掐掉,换条件重新生成(把注定失败的算力换成新机会);
- **DEFER**:歌词清晰度这种"晚才看得出"的轴 → 延后判断;
- **CONTINUE**:没问题就跑完。

**ADSR 不是**:回滚、修补、RL 后训练、固定池剪枝挑选。原始 ETP(Early-Tweedie Pruning)是 baseline。

**关键技术点**:
- Tweedie z0 估计:`z0 = x_σ − σ·v`(sample − sigma·model_output),解码成"预览音频",可中途打分;
- 在线重启原语:monkeypatch `scheduler.step`,在 σ≤0.8 的步解码 z0→mel→EVPD,抛异常提前中止(省 ~53% 步);
- 歌词轴是**英文人声专属**(Whisper WER):`vocal_scorable` n=282;**纯伴奏带 1.0 哨兵值,绝不能并入歌词均值**。

---

## 3. 科学叙事的演化(**最重要的 context** — 不懂这段会重走死路)

主张经过了一次**诚实的收窄**,新人必须理解为什么:

| 批次 | 做了什么 | 结论 |
|---|---|---|
| **Batch 1** | 4096 候选重采集 + Demucs 标签 + 早期 mel | 类型错误 23%,早期可分;数据基座 |
| **Batch 2** | EVPD 训练 + 离线 ADSR 模拟 | EVPD 强(AUC 0.94@σ0.7),但"赢"来自 **EVPD 感知的选择**,不是重启 → `ADSR_CONDITIONAL` |
| **Phase 0** | 门控前沿分析 | **一个免费的事后 Demucs 门控就能在简单 prompt 上把类型错误压到很低** → "广义效率"主张被证伪(连完美探针上界 +14.9% 都达不到判据) |
| **Batch 3** | 真实在线重启,8 臂对照 | 主张收窄到**确定性尾部**:对那 32 个"8 选≥5 都犯错"的 prompt,**重采样概率上救不回来,只有改变条件可以** → `SUPPORTED_TAIL_RESCUE` |

**收窄后的新颖内核(论文要主打这句)**:ADSR 的新意**不是"早重启"**(那是已知的 early-exit/BoN/verifier),
而是 **"诊断出随机性已经耗尽、必须移动生成条件"**。"只换种子 ≈ BoN"的零结果是整篇的支点。

> 新人警告:不要再去追"广义效率/通用加速"的主张——已被 oracle 上界证死,且预注册时已正式退役。

---

## 4. 当前实验状态(Phases 0–3 全部完成)

| 阶段 | 内容 | 关键产出 | 状态 |
|---|---|---|---|
| Phase 0 | 门控前沿/oracle 分解/可观测性曲线/尾部刻画/功效仿真 → 冻结协议 | `phase0/P0_*.{json,md}`,`batch3/{BATCH3_PRELAUNCH_PROTOCOL,ANALYSIS_PLAN}.md` | ✅ |
| Phase 1 | Batch-3 在线:256 held_out × 8 臂 × R2(尾部 R3),3648 units/22825 attempts,**0 ledger 违规** | `batch3/online_run/ledger_w*.jsonl`,`batch3/ADSR_ONLINE_COMPREHENSIVE_RESULTS.{md,json}` | ✅ |
| Phase 2 | ledger 反事实重放 + 48-prompt 在线确认 | `batch3/PHASE2_LEDGER_REPLAYS.{md,json}`,`batch3/CONFIRMATORY_ARM9_RESULTS.json` | ✅(在线未确认,探索性) |
| Phase 3 | T2I/SDXL 三大签名 + 人评包 | `t2i/T2I_SIGNATURES.{md,json}`,`phase3/human_ab/`,`phase0/rater_packet/` | ✅(人评包已备好,未评) |

全程合规:盲态分析 → Codex 审计 → 解盲 → 机械判决;**5 轮 Codex 审计**,所有 blocking 在对应步骤前修复。

---

## 5. 核心结果(数字全部可在 artifact 复核)

**Batch-3 在线主结果(预注册端点全过):**

| 端点 | 结果 | 判据 |
|---|---|---|
| **主:restart2+ 逐次干净率** arm6−arm4,尾部 n=32(30 贡献) | **+0.43 [0.27, 0.58]** | ≥+0.15 ✅(功效 0.87) |
| 次:E2a 全程逐次干净率(Bonferroni) | +0.38 ✅ | — |
| 方向分解(描述性) | vocal **+0.76** / instrumental **≈0** | — |

**各臂选中输出类型错误率**:arm6(我们的方法)**0.98%** vs arm1(同算力基线)**11.5%** vs arm7(BoN-8,1.43×算力)**6.6%**;干净产出 **+30%**(3.71 vs 2.86)。
**质量边际**(arm6 vs arm1,选中输出):Δcommon +0.018 / Δsemantic +0.000 / Δaesthetic +0.10 / **Δ歌词 +0.031** —— 预注册边际下全为正。
**算力对账**:非探针臂偏差 3–8.6%;**EVPD 探针 ≈0.9s vs 分数探针 ≈52s**(arm-3 实际 52h vs 名义 2.7h)→ 只有廉价探针可部署。

**8 个对照臂(harness 定义,记住这个):**
1 BoN-Budget(同算力基线,主比较) · 2 随机重启(abort 数 yoke 到 arm4) · 3 common-score 重启(早期 σ0.8 common < 1.4667=dev-Q40 则 abort) · **4 ADSR+EVPD 只换种子**(冻结 `melsumm_logit_s0.8` thr 0.728,≤6 aborts) · 5 lyric-defer(仅选择,λ=0.25) · **6 ADSR+EVPD+条件化重启=我们的方法**(restart1=换种子,restart2=L1,restart3+=L2,见 `RESPAWN_LADDER.json`) · 7 BoN-8(240 步,1.43×) · 8 BoN-4(120 步) · 9 probe-on-evidence(Phase-2 确认臂,后加)。

**诚实的负结果(不藏)**:
- 广义效率主张:校准死亡,赛前退役为描述性 RMST 曲线。
- Phase-2 离线赢家(probe-on-evidence −7%、portfolio −6%):48-prompt 在线 **未确认**(78.9≈77.8 steps/clean)。
- instrumental 侧干预:dev +0.10,**在线没复现(≈0)**——方法目前**只在 vocal 方向成立**。
- T2I:三大诊断签名复现,但 **probe-restart 没超过 T2I 前沿**(0.096@0.62 vs BoN-4 0.092@0.5)→ 支撑问题框架,非方法迁移。

---

## 6. 怎么读这些数字(防误读)

- **相对比较有效,绝对值别当总体代表**:256 prompt 是"风险富集"挑的(故意多放易错的),"0.98% / 11.5%"不代表全体。
- **质量目前只有代理指标**:人评未做。所以只能说"预注册边际下**未发现**可感质量代价",**不能**说"证明无质量损失"。
- **vocal 强、instrumental ≈0**:主端点效果几乎全来自 vocal 侧。

---

## 7. 诚实的 ICLR 评估 + 下一步(你最该看的)

两份独立评估(我 + Codex)一致:**目前 borderline / 偏拒,分数带 5–6**,不到 7+。
工作严谨(预注册/盲态/0 违规/5 轮审计,强于多数投稿),但**方法被证有效的范围太窄**:单骨干、单约束、**vocal-only**、n=32 尾部、代理质量。新颖性会被对标 early-exit/BoN+verifier(必须主打"随机性耗尽→移动条件"这个内核)。

**通往稳过的最高杠杆(按性价比;前 3 项约一周、不需新骨干):**
1. **跑人评**(包已备好,见 §9)——最便宜,把"代理无代价"升级成"人耳无代价"。**卡在 PI 分发。**
2. **第二骨干 / 第二约束**(首选 Stable Audio Open)——打破"vocal-only 单点",从"窄"到"通用"的唯一硬通货(数天工程)。
3. **攻 instrumental 方向**(见下)——让方法两个方向都成立,消掉"半失败"读感(~1 天)。
4. 扩大/压力测试尾部(更大 held-out 尾部,复现 seed-null/条件化-正 的模式)。
5. 把"尾部不可救"写成小命题(已有 beta-binomial 模型)。

**"instrumental 实验"具体指什么**:vocal-miss 方向我们用"调高 `guidance_scale_lyric` + 注入结构提示"成功了;
instrumental-leak 方向用"文本追加 no-vocals + 提高 cfg"在 dev 有效但在线失败。要找一个**能在线真正压住人声泄漏**的重启干预——候选杠杆:负向提示(ACE-Step 无 negative-prompt 接口,需改 adapter)、更强反人声 tag、不同 `cfg_type`/`omega_scale`、或上游 `retake`/`repaint` 温重启。

---

## 8. 代码地图(`scripts/`)

**流水线顺序**(每个脚本头部都有 docstring):
```
数据基座:   collect_early_tweedie_validation.py  (生成+打分,model.sample/decode)
            adsr_downstream.py  (_label_one = Demucs 人声能量比标签)
Batch 2:    batch2_stage1_typeerror.py / stage3_evpd.py / stage4_adsr_sim.py / stage4b_sigma_frontier.py
            persist_evpd_sigma08.py  (冻结 σ0.8 EVPD → evpd_sigma08_online.joblib)
            online_adsr_smoke.py     (验证在线 hook-abort 原语)
Phase 0:    phase0_gated_replays.py    (P0.1-3 门控前沿/oracle 分解)
            phase0_whisper_pass.py     (P0.4 早期歌词转录,GPU)
            phase0_tail_and_labels.py  (P0.5 尾部+E2 子组冻结; P0.6 阈值扫描+评分包)
            phase0_panns_detector.py   (P0.6 PANNs 替代检测器,GPU)
            phase0_respawn_screen.py + _analyze.py  (P0.8 dev 重启干预筛选→RESPAWN_LADDER)
            phase0_power_sim.py / _v2.py  (P0.7 功效仿真,端点重设计的依据)
            batch3_prompt_strata.py    (256 prompt 分层)
Batch 3:    batch3_online_harness.py   (★ 在线主 harness:8 臂+CRN+预算 ledger+门控+存储策略)
            batch3_node_launcher.sh / batch3_rebalance.sh  (多 GPU 启动/再均衡)
            batch3_validate_ledger.py  (ledger 不变量校验,跑分析前必过)
            batch3_analyze.py          (★ 冻结分析,默认盲态;--unblind 解盲)
Phase 2:    phase2_ledger_replays.py   (反事实重放;arm9 在 harness 里 --only-arm 9)
Phase 3:    t2i_build_prompts.py / t2i_generate.py / t2i_score.py / t2i_signatures.py  (T2I,t2i-adsr env)
            build_human_ui.py          (★ 人评 Web 界面生成器;--reduced 缩减版)
            build_human_ab_packet.py   (人评 A/B 配对生成)
```
`★` = 核心、改动需谨慎(harness/分析/人评 UI)。

---

## 9. 数据与产物地图

| 内容 | 路径 |
|---|---|
| **4096 候选数据集**(spine,jsonl+符号链) | `runs/adsr_recollect_20260604_full01_merged/shard0*/candidate_records.jsonl`(8 shard) |
| 原始音频(被 spine 引用) | `runs/adsr_recollect_20260604_full01/`、`runs/adsr_recollect_resume/` |
| 连续 Demucs 比值 + PANNs | `…/vocal_presence_raw.jsonl`、`…/phase0/panns_labels.jsonl` |
| **冻结 σ0.8 EVPD 模型** | `…/batch2/evpd_sigma08_online.joblib`(thr 0.728,**别重训**) |
| Batch-3 ledger(单一真相源) | `…/batch3/online_run/ledger_w*.jsonl`(attempt 行 + unit_selection 行) |
| Batch-3 保留音频(FLAC) | `…/batch3/online_run/keep/`(~35GB,选中输出+E2+人评对) |
| 主结果 + 判决 | `…/batch3/ADSR_ONLINE_COMPREHENSIVE_RESULTS.{md,json}` |
| 冻结协议/分析计划 | `…/batch3/{BATCH3_PRELAUNCH_PROTOCOL,ANALYSIS_PLAN}.md` |
| 尾部子组 / 重启梯 / dev 校准 | `…/batch3/{E2_TAIL_SUBGROUP.jsonl,RESPAWN_LADDER.json,DEV_CALIBRATIONS.json}` |
| T2I(4000 图 + 24k 预览) | `…/t2i/`(images/、records_w*、T2I_SIGNATURES.*) |
| **人评界面(缩减版,可直接发)** | A/B:`…/phase3/human_ab/index.html`(80 对) · 判定:`…/phase0/rater_packet/adjudication.html`(112 例) · 设计:`…/phase3/HUMAN_EVAL_DESIGN.md` · 启动:`…/phase3/HUMAN_UI_README.md` |
| 人评解盲钥匙(**PI 专属**) | `…/phase3/human_ab/UNBLINDING_KEY.jsonl` |

人评界面用法:`cd` 到包目录 → `python -m http.server 8731` → 浏览器开 `index.html`(Chrome/Firefox,支持 FLAC)。或 `python scripts/build_human_ui.py --reduced --package` 打便携版。

---

## 10. 环境与运行

```bash
module load anaconda3/2023.09
source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh
conda activate audio-prm                      # 主环境(torch 2.5.1+cu121)
# T2I 用独立环境保护主环境:conda activate t2i-adsr(diffusers 0.31 + owlv2 + pickscore)
```
- **计算节点**:`an17`(job 93398)、`an29`(job 93896),均 `ai` 分区、不限时、8×A800 80GB。**temp 分区(an22)已退役,别用。** 更多节点:`salloc -p ai -N1 --exclusive`。
- 节点**无外网** → 跑生成加 `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`;模型权重本地已缓存。
- **多 GPU 跑 harness**(每节点 8 worker → 实测过线程超订;**OMP_NUM_THREADS=6、每节点 4 worker** 更稳):
  ```bash
  ssh an17 "bash $REPO/scripts/batch3_node_launcher.sh 0"   # worker 0-7
  ssh an29 "bash $REPO/scripts/batch3_node_launcher.sh 8"   # worker 8-15
  ```
- **CRN 种子公式**:`seed = 2026062000 + manifest_index*1000 + rep*100 + attempt`(与 arm 无关 → 各臂同噪声配对)。
- 配额:`lfs quota -u pxy1289 .`(只能在树内路径跑)。当前 **393/510GB**。

---

## 11. 硬边界(**别碰** —— 详见 CLAUDE.md)

不经 PI 明确批准:RL 训练、pruning+RL、Phase D、众包人评、canonical proposal 重写。
不改:`configs/eval/gate_v1.yaml`、reward 定义、prompt split(dev/held_out)、已有 `runs/**` 证据、
`orbit-research/trajectory_candidate_dataset.jsonl`。`gate_v2.yaml.draft` 是草稿、**只读、绝不重命名激活**。
EVPD 阈值冻结 0.728(别重训);歌词哨兵恒掩码(只算 EN-vocal);人评由 **PI 分发**(内部学生,非众包)。

---

## 12. 运维教训(踩过的坑 —— 能省你几天)

- **/XYFS02 配额 500/510GB 是瓶颈**;EDQUOT(os error 122)在 libsndfile 里伪装成 "System error"。
  122GB 冗余 merge 落选音频已搬到 `/tmp/adsr_mergeloser_audio/`(可恢复)。大批生成把瞬态 wav 写 `/dev/shm`(504G tmpfs,零配额),keep 转 FLAC 落盘。
- **huggingface-hub 必须 <1.0(钉死 0.36.2)**,否则 transformers/ACE-Step import 崩。修:`pip install --force-reinstall --no-deps "huggingface-hub==0.36.2"`(登录节点,代理 127.0.0.1:7890)。
- **torch 线程超订**:8 worker × 56 线程 → load 161、6× 变慢。设 `OMP_NUM_THREADS=6`、每节点 4 worker。
- **T2I 坑**:SDXL `scheduler.step(return_dict=False)` 拿不到 `pred_original_sample`→ 在 hook 里自己算 x0;fp16 VAE 解码预览全黑 → 用独立 fp32 VAE 副本;prompt builder 的 kind⊗split 不要相关;NFS 元数据延迟会让计算节点上刚 pip 装的包"看不见"→ 等 `is_*_available()` 为真再起。
- **Codex CLI**:必须 `</dev/null` + `timeout` 防 stdin 卡死;参数 `sandbox_mode/approval_policy="never"/model_reasoning_effort/service_tier="fast"/--skip-git-repo-check -C <repo>`。
- **别误释放 GPU 节点**:释放前问 PI;an17/an29 是手持的命根子。
- 复合 Bash 命令里的 pkill/scancel 会触发 exit 143/144 信号假象 → 拆成单条跑、单独验证状态。

---

## 13. 术语表

- **EVPD**:Early Vocal-Presence Detector,早期 mel→最终人声有无的检测器(逻辑回归/GBDT)。
- **ETP**:Early-Tweedie Pruning,基于早期分数的剪枝,现为 baseline。
- **Tweedie / z0**:`z0 = x_σ − σ·v`,中途的"干净估计",可解码打分。
- **σ(sigma)**:噪声水平;决策点 σ0.8(第 12/30 步)。SIGMA_STEPS {0.9:7, 0.8:12, 0.7:16}, FULL=30。
- **gate(门控)**:最终 Demucs 类型检查(免费、可部署),选择时只在过门候选里挑。
- **type-error**:最终人声有无 XOR 请求类型。Demucs 人声能量比阈值 **0.1791**。
- **vocal_scorable / 哨兵**:EN-vocal n=282 才算歌词;纯伴奏 lyric=1.0 哨兵,**绝不并入均值**。
- **CRN**:Common Random Numbers,各臂共享同种子初始噪声,降方差。
- **restart2+**:第 2 次及以后的重启(即条件干预生效后)生成的候选——主端点就建在这上面。
- **E2 尾部子组**:held_out 中 Batch-1 ≥5/8 违规的 32 个 prompt,冻结。

---

*本文每个数字/路径都在 2026-06-20 核对过。权威来源见 §0 顶部 3 份文件。有疑问先查 artifact,再问 PI;
不确定就停下来问(项目铁律:别猜)。*
