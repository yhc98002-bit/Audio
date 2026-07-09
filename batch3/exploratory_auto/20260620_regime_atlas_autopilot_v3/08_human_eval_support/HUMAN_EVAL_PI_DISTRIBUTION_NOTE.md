# 人评分发说明(PI 专用)

打包产物:`/tmp/adsr_human_eval_pkg_20260620.tar.gz`(3.6 GB),解压见内附 `README.md`(中文)。

三个任务:
1. `1_quality_AB/quality_eval.html` — A/B 盲听质量评测(80 对)→ 发给评分员(建议 2 人 + 分歧加裁)。
2. `2_label_adjudication/label_adjudication.html` — 有无人声判定(112 例)→ 发给评分员(2 人)。
3. `3_PI_sanity_inspect/sanity_inspect.html` — **PI 本人**做的声音体检 → 导出 PASS/FAIL,**这是解锁大规模实验的关口**。

边界:agent 只准备、不分发、不联系评分员、不解盲。`PI_ONLY_KEY_DO_NOT_SHARE/` 切勿外发。
