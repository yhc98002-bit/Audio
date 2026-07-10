#!/usr/bin/env python
"""Bundle ALL human-in-the-loop work into one portable archive with GUIs + a Chinese README.

Three human-blocked tasks:
  1. A/B quality eval (80 pairs)      — GUI exists (phase3/human_ab/index.html)
  2. label adjudication (112 cases)   — GUI exists (phase0/rater_packet/adjudication.html)
  3. PI sanity inspection (160 clips) — GUI BUILT HERE (currently blocks large-N)

Stages everything (with REAL audio, symlinks dereferenced) into /tmp, writes a Chinese README,
isolates the PI-only unblinding key, and tars it. Nothing is distributed — the PI hands it out.
"""
from __future__ import annotations
import csv, json, os, shutil, subprocess
from pathlib import Path

REPO = Path(os.environ.get("MPRM_REPO_ROOT", Path(__file__).resolve().parents[1])).resolve()
B3 = REPO / "orbit-research/adsr_phase2_20260604"
SAN = REPO / "batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/00_controls_and_sanity_gate"
STAGE = Path("/tmp/adsr_human_eval_pkg")
TAR = Path("/tmp/adsr_human_eval_pkg_20260620.tar.gz")

# ---------------------------------------------------------------- sanity inspection GUI (new)
SANITY_HTML = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>声音正确性体检 · PI 专用</title>
<style>
:root{--bg:#0f1115;--card:#1a1d24;--fg:#e8eaed;--mut:#9aa0a6;--ac:#4f8cff;--ok:#34c759;--bad:#ff453a;--line:#2a2e37}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,"PingFang SC","Microsoft YaHei",sans-serif}
header{position:sticky;top:0;z-index:5;background:#13161c;border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.t{font-weight:700}.pill{font-size:12px;color:var(--mut);background:#0c0e12;border:1px solid var(--line);border-radius:99px;padding:3px 10px;cursor:pointer}
.pill.on{color:#fff;border-color:var(--ac);background:#1b2330}
main{max-width:980px;margin:16px auto;padding:0 16px}
.cat{font-weight:700;margin:18px 0 8px;font-size:15px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:10px}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.badge{font-size:12px;border-radius:7px;padding:3px 8px;font-weight:700}
.voc{background:#1d2b1f;color:#7ee08a}.ins{background:#26211d;color:#ffce85}
.tc1{color:var(--ok);font-weight:700}.tc0{color:var(--bad);font-weight:700}
.ptext{color:#cfd3d8;background:#0c0e12;border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin:8px 0;font-size:13.5px;white-space:pre-wrap}
audio{width:100%;margin-top:6px}
.sc{font-size:12px;color:var(--mut);margin-top:6px}
.decision{position:sticky;bottom:0;background:#13161c;border-top:1px solid var(--line);padding:12px 16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.decision button{border:0;border-radius:9px;padding:10px 16px;cursor:pointer;font-weight:700}
.pass{background:var(--ok);color:#03210c}.fail{background:var(--bad);color:#2a0000}.exp{background:#222632;color:var(--fg);border:1px solid var(--line)!important}
input,textarea{background:#0c0e12;border:1px solid var(--line);color:var(--fg);border-radius:8px;padding:7px 9px;font:inherit}
.flagbtn{font-size:12px;background:#0c0e12;border:1px solid var(--line);color:var(--mut);border-radius:7px;padding:4px 8px;cursor:pointer}
.flagbtn.on{border-color:var(--bad);color:var(--bad)}
</style></head><body>
<header><span class="t">声音正确性体检 · PI 专用(过这一关才解锁大规模实验)</span>
<label class="pill">PI 缩写 <input id="who" style="width:70px" maxlength="12"></label>
<span id="filters"></span><span class="pill" id="cnt"></span></header>
<main id="app"></main>
<div class="decision">
  <span style="color:var(--mut)">整体判定:</span>
  <button class="pass" id="bp">PASS(标签与听感一致 → 开始大规模实验)</button>
  <button class="fail" id="bf">FAIL(有问题,先修)</button>
  <input id="note" placeholder="备注(可选,例如哪条标签与听感不符)" style="flex:1;min-width:180px">
  <button class="exp" id="exp">导出判定 JSON</button>
  <span id="st" style="color:var(--mut);font-size:13px"></span>
</div>
<script>
const DATA=__DATA__, CATS=__CATS__;
let cat="ALL"; const $=s=>document.querySelector(s);
function flags(){try{return JSON.parse(localStorage.getItem("sanity_flags"))||{}}catch(e){return {}}}
function esc(s){return (s||"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}
function render(){
  $("#filters").innerHTML=["ALL",...CATS].map(c=>'<span class="pill '+(cat===c?"on":"")+'" data-c="'+c+'">'+c+'</span>').join("");
  document.querySelectorAll('#filters .pill').forEach(p=>p.onclick=()=>{cat=p.dataset.c;render()});
  const fl=flags(); const rows=DATA.filter(d=>cat==="ALL"||d.control_category===cat);
  let html=""; let last="";
  rows.forEach(d=>{
    if(d.control_category!==last){html+='<div class="cat">'+d.control_category+'</div>';last=d.control_category}
    const tb=d.requested_vocal? '<span class="badge voc">要求:有人声</span>':'<span class="badge ins">要求:纯伴奏</span>';
    const tc=d.type_correct? '<span class="tc1">类型✓</span>':'<span class="tc0">类型✗</span>';
    html+='<div class="card"><div class="row">'+tb+tc+'<span style="color:var(--mut);font-size:12px">'+d.prompt_id+' · seed'+d.seed+'</span>'+
      '<span class="flagbtn '+(fl[d.flac]?"on":"")+'" data-f="'+d.flac+'">'+(fl[d.flac]?"已标:标签可疑":"标记此条标签可疑")+'</span></div>'+
      (d.prompt_text?'<div class="ptext">'+esc(d.prompt_text)+'</div>':'')+
      '<audio controls preload="none" src="'+d.flac+'"></audio>'+
      '<div class="sc">Demucs人声比 '+d.vocal_energy_ratio+' · PANNs '+(d.panns_vocal??"—")+' · common '+(d.common??"—")+' · semantic '+(d.semantic??"—")+' · aesthetic '+(d.aesthetic??"—")+' · lyric '+(d.lyric??"—")+'</div></div>';
  });
  $("#app").innerHTML=html;
  document.querySelectorAll('.flagbtn').forEach(b=>b.onclick=()=>{const f=flags();if(f[b.dataset.f])delete f[b.dataset.f];else f[b.dataset.f]=1;localStorage.setItem("sanity_flags",JSON.stringify(f));render()});
  $("#cnt").textContent=rows.length+" 条 · 已标可疑 "+Object.keys(fl).length;
}
$("#who").value=localStorage.getItem("sanity_who")||"";$("#who").oninput=()=>localStorage.setItem("sanity_who",$("#who").value);
function exportDecision(verdict){
  const o={verdict:verdict,pi:$("#who").value.trim(),note:$("#note").value,suspect_clips:Object.keys(flags()),
           total:DATA.length,ts:new Date().toString()};
  const b=new Blob([JSON.stringify(o,null,2)],{type:"application/json"});
  const u=URL.createObjectURL(b);const a=document.createElement("a");a.href=u;a.download="SANITY_DECISION_"+verdict+".json";a.click();
  $("#st").textContent="已导出判定: "+verdict+"(把这个 json 发回给我)";
}
$("#bp").onclick=()=>exportDecision("PASS");$("#bf").onclick=()=>exportDecision("FAIL");
$("#exp").onclick=()=>exportDecision($("#note").value?"NOTED":"REVIEW");
render();
</script></body></html>"""


def build_sanity_html(dst: Path):
    prompts = {json.loads(l)["prompt_id"]: json.loads(l)
               for l in open(SAN / "CONTROL_PROMPTS.jsonl")}
    data = []
    for r in csv.DictReader(open(SAN / "SANITY_GATE_AUDIO_MANIFEST.csv")):
        pm = prompts.get(r["prompt_id"], {})
        data.append({"flac": r["flac"], "control_category": r["control_category"],
                     "prompt_id": r["prompt_id"], "requested_vocal": int(r["requested_vocal"]),
                     "seed": r["seed"], "vocal_energy_ratio": r["vocal_energy_ratio"],
                     "panns_vocal": r["panns_vocal"] or None, "type_correct": int(r["type_correct"]),
                     "prompt_text": pm.get("text", ""), "common": r["common"] or None,
                     "semantic": r["semantic"] or None, "aesthetic": r["aesthetic_pq"] or None,
                     "lyric": r["lyric"] or None})
    cats = sorted({d["control_category"] for d in data})
    html = (SANITY_HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__CATS__", json.dumps(cats, ensure_ascii=False)))
    dst.write_text(html, encoding="utf-8")


def derefcopy(src_dir: Path, dst_dir: Path):
    """copy a media symlink-farm into real files."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    for f in src_dir.iterdir():
        shutil.copy2(f.resolve(), dst_dir / f.name)   # resolve() follows the symlink


README = """# ADSR 人评包 · 使用说明

本压缩包含 **3 个需要人参与的任务**,每个都带**图形界面(网页),无需安装**。
浏览器请用 **Chrome 或 Firefox**(它们能播放 FLAC 音频)。

---

## 三个任务总览

| 文件夹 | 任务 | 谁来做 | 作用 |
|---|---|---|---|
| `1_quality_AB/` | **A/B 盲听质量评测**(80 对) | 评分员(2 人 + 分歧加裁) | 证明我们的方法**无可感质量代价**(论文软肋) |
| `2_label_adjudication/` | **有无人声判定**(112 例) | 评分员(2 人 + 加裁) | 验证自动标签(Demucs)是否可靠 |
| `3_PI_sanity_inspect/` | **声音正确性体检**(160 段) | **PI 本人** | **当前关口:过了才解锁大规模实验** |
| `PI_ONLY_KEY_DO_NOT_SHARE/` | 解盲钥匙 | **仅 PI** | A/B 的答案对照,**切勿发给评分员** |

---

## 怎么打开界面(两种方式,任选其一)

**方式 A:直接双击网页**(最简单)
- 进入对应文件夹,双击里面的 `.html` 文件,用 Chrome/Firefox 打开即可。

**方式 B:起一个本地小服务**(如果双击后音频不播放,用这个)
```
cd 进入对应文件夹
python3 -m http.server 8800
# 浏览器打开 http://localhost:8800/ ,点对应的 html
```

---

## 任务 1:A/B 盲听质量评测(发给评分员)

- 打开 `1_quality_AB/quality_eval.html`。
- 右上角填**评分员缩写**(区分不同人)。
- 每屏:看 prompt(要求有/无人声)→ 听**片段 A**和**片段 B**(快捷键 1 / 2)→ 答 3 个问题
  (总体更喜欢 / 更贴合 prompt / 瑕疵更少)+ 把握程度 + 备注。
- 答题**自动保存**(刷新不丢)。全部做完点底部「导出 CSV」,把 CSV 发回。
- **建议 2 人各自做一遍**;遇到两人主端点分歧、或有人标「拿不准」,再上第三人加裁。

## 任务 2:有无人声判定(发给评分员)

- 打开 `2_label_adjudication/label_adjudication.html`。
- 每段只判一个问题:**这段里有没有人声**(有 / 无 / 不确定,快捷键 1 / 0 / u)。
- 做完导出 CSV 发回。**建议 2 人**。

## 任务 3:声音正确性体检(PI 本人做,当前最关键)

- 打开 `3_PI_sanity_inspect/sanity_inspect.html`。
- 这是给 **PI** 核验自动流水线是否正常的:按 A–E 分组,每段能看到 prompt、要求类型、
  Demucs/PANNs 标签、各项分数,并能播放。
- 抽听几段,确认**标签与你的听感一致**(尤其:A 类该多为「有人声」、B 类该多为「纯伴奏」)。
- 听完在底部选 **PASS** 或 **FAIL**,导出 `SANITY_DECISION_*.json` 发回给我。
- **PASS = 解锁大规模实验**(我会立刻开始跑);**FAIL = 我先修流水线**。
- 如某条标签和你听到的不符,点该条「标记此条标签可疑」,会一起记进导出文件。

---

## 回收 / 注意事项

- 每位评分员把导出的 **CSV / JSON** 发回即可,我会汇总。
- `PI_ONLY_KEY_DO_NOT_SHARE/` 里的解盲钥匙是 A/B 的答案对照,**只有 PI 留存,绝不能给评分员**(否则评测失去盲态)。
- 全部为**内部评测**,非众包;由 PI 分发。
- 音频较多,整包约 3 GB。
"""


def main():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    # 1. A/B quality
    d1 = STAGE / "1_quality_AB"; d1.mkdir()
    shutil.copy2(B3 / "phase3/human_ab/index.html", d1 / "quality_eval.html")
    shutil.copy2(B3 / "phase3/human_ab/response_sheet.csv", d1 / "response_sheet.csv")
    shutil.copy2(B3 / "phase3/HUMAN_EVAL_DESIGN.md", d1 / "DESIGN.md")
    derefcopy(B3 / "phase3/human_ab/media", d1 / "media")
    # 2. adjudication
    d2 = STAGE / "2_label_adjudication"; d2.mkdir()
    shutil.copy2(B3 / "phase0/rater_packet/adjudication.html", d2 / "label_adjudication.html")
    shutil.copy2(B3 / "phase0/rater_packet/response_sheet.csv", d2 / "response_sheet.csv")
    derefcopy(B3 / "phase0/rater_packet/media", d2 / "media")
    # 3. sanity inspect (PI)
    d3 = STAGE / "3_PI_sanity_inspect"; d3.mkdir()
    build_sanity_html(d3 / "sanity_inspect.html")
    shutil.copy2(SAN / "SANITY_GATE_AUDIO_MANIFEST.csv", d3 / "manifest.csv")
    shutil.copy2(SAN / "SANITY_GATE_RESULTS.md", d3 / "RESULTS.md")
    shutil.copytree(SAN / "keep", d3 / "keep")
    # PI-only key
    dk = STAGE / "PI_ONLY_KEY_DO_NOT_SHARE"; dk.mkdir()
    shutil.copy2(B3 / "phase3/human_ab/UNBLINDING_KEY.jsonl", dk / "UNBLINDING_KEY.jsonl")
    (dk / "README_PI.txt").write_text(
        "这是 A/B 评测的解盲钥匙(pair_id → 哪个臂)。只有 PI 留存。\n"
        "绝对不要放进发给评分员的包里,否则评测失去盲态。\n", encoding="utf-8")
    (STAGE / "README.md").write_text(README, encoding="utf-8")
    # tar
    if TAR.exists():
        TAR.unlink()
    subprocess.run(["tar", "czf", str(TAR), "-C", str(STAGE.parent), STAGE.name], check=True)
    sz = TAR.stat().st_size / 1e9
    counts = {"AB_pairs_media": len(list((d1 / "media").iterdir())),
              "adj_media": len(list((d2 / "media").iterdir())),
              "sanity_flac": len(list((d3 / "keep").rglob("*.flac")))}
    print(json.dumps({"tar": str(TAR), "size_GB": round(sz, 2), "staging": str(STAGE),
                      "counts": counts}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
