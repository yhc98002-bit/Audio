#!/usr/bin/env python
"""Generate self-contained web UIs for the two human-eval packets (no install, offline-ok).

A/B packet  (phase3/human_ab/)     -> index.html        : blinded A/B preference, 6-dim rubric
Adjudication (phase0/rater_packet/) -> adjudication.html : vocal-presence yes/no/unsure

Design:
- Data is EMBEDDED in the HTML (works under file:// too; no fetch/CORS issues).
- Audio referenced via a sibling `media/` symlink farm (zero bytes, no quota) so the packet can
  be served in place with `python -m http.server` from the packet dir.
- Blinding preserved: arm identities live ONLY in UNBLINDING_KEY.jsonl (read here only to join
  prompt TEXT, never arm labels into the HTML).
- Responses autosave to the browser's localStorage (resume on reload); rater exports the exact
  response_sheet.csv schema at the end.
- `--package` dereferences the symlink farm into real audio copies for a portable tar (remote raters).

Usage:
  python scripts/build_human_ui.py            # build both UIs in place (symlink media)
  python scripts/build_human_ui.py --package  # also copy real audio into media/ (portable)
"""
from __future__ import annotations
import argparse, csv, json, os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
B3 = REPO / "orbit-research/adsr_phase2_20260604"
AB = B3 / "phase3/human_ab"
ADJ = B3 / "phase0/rater_packet"

# ----------------------------------------------------------------------------- shared HTML shell
SHELL = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root{--bg:#0f1115;--card:#1a1d24;--fg:#e8eaed;--mut:#9aa0a6;--ac:#4f8cff;--ok:#34c759;--warn:#ff9f0a;--line:#2a2e37}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,system-ui,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif}
  header{position:sticky;top:0;z-index:5;background:#13161c;border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
  header .t{font-weight:700;font-size:16px}
  header input{background:#0c0e12;border:1px solid var(--line);color:var(--fg);border-radius:8px;padding:6px 9px;font-size:14px}
  .prog{flex:1;min-width:160px}
  .bar{height:8px;background:#0c0e12;border-radius:99px;overflow:hidden;border:1px solid var(--line)}
  .bar>i{display:block;height:100%;background:var(--ac);width:0%}
  .pill{font-size:12px;color:var(--mut);background:#0c0e12;border:1px solid var(--line);border-radius:99px;padding:3px 10px}
  .save{font-size:12px;color:var(--ok)}
  main{max-width:880px;margin:18px auto;padding:0 16px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:16px}
  .meta{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
  .badge{font-weight:700;border-radius:8px;padding:4px 10px;font-size:13px}
  .voc{background:#1d2b1f;color:#7ee08a;border:1px solid #2f5135}
  .ins{background:#26211d;color:#ffce85;border:1px solid #5a4527}
  .grp{background:#1b2330;color:#8db4ff;border:1px solid #2b3a52}
  .ptext{color:var(--fg);background:#0c0e12;border:1px solid var(--line);border-radius:10px;padding:12px 14px;white-space:pre-wrap}
  .lyr{margin-top:8px}
  .lyr summary{cursor:pointer;color:var(--mut)}
  .lyr pre{white-space:pre-wrap;color:#cfd3d8;background:#0c0e12;border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:8px 0 0}
  .players{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:16px 0}
  .pl{background:#0c0e12;border:1px solid var(--line);border-radius:12px;padding:14px;text-align:center}
  .pl h3{margin:0 0 8px;font-size:15px;letter-spacing:.5px}
  .pl audio{width:100%}
  .pl .key{font-size:12px;color:var(--mut);margin-top:6px}
  .single audio{width:100%}
  .q{margin:14px 0;padding-top:12px;border-top:1px dashed var(--line)}
  .q .ql{font-size:14px;margin-bottom:8px;color:#dfe3e8}
  .opts{display:flex;gap:8px;flex-wrap:wrap}
  .opts button{flex:1;min-width:64px;background:#0c0e12;border:1px solid var(--line);color:var(--fg);border-radius:9px;padding:10px;cursor:pointer;font-size:14px;transition:.1s}
  .opts button:hover{border-color:var(--ac)}
  .opts button.sel{background:var(--ac);border-color:var(--ac);color:#fff;font-weight:700}
  .opts button.selna{background:#5a4527;border-color:var(--warn);color:#fff}
  textarea{width:100%;background:#0c0e12;border:1px solid var(--line);color:var(--fg);border-radius:10px;padding:10px;margin-top:6px;font:inherit;resize:vertical}
  .nav{display:flex;gap:10px;justify-content:space-between;margin-top:10px}
  .nav button{background:#222632;border:1px solid var(--line);color:var(--fg);border-radius:10px;padding:10px 18px;cursor:pointer;font-size:14px}
  .nav button:hover{border-color:var(--ac)}
  .nav .next{background:var(--ac);color:#fff;font-weight:700;border-color:var(--ac)}
  footer{max-width:880px;margin:0 auto 40px;padding:0 16px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
  footer button{background:var(--ok);border:0;color:#03210c;border-radius:10px;padding:11px 18px;cursor:pointer;font-weight:700}
  footer .j{background:#222632;color:var(--fg);border:1px solid var(--line)}
  footer .status{color:var(--mut);font-size:13px}
  .req{color:var(--warn)}
  .done{color:var(--ok)}
  .hint{color:var(--mut);font-size:12.5px;margin-top:4px}
  @media(max-width:640px){.players{grid-template-columns:1fr}}
</style></head>
<body>
<header>
  <span class="t">__TITLE__</span>
  <label class="pill">评分员缩写 <input id="who" placeholder="如 ZS" maxlength="12" style="width:84px"></label>
  <span class="pill" id="grp"></span>
  <div class="prog"><div class="bar"><i id="pfill"></i></div></div>
  <span class="pill" id="pcount">0 / 0</span>
  <span class="save" id="save"></span>
</header>
<main id="app"></main>
<footer>
  <button id="exp">⬇ 导出我的评分 CSV</button>
  <button id="expj" class="j">导出 JSON(备份)</button>
  <span class="status" id="fstat"></span>
</footer>
<script>
const MODE="__MODE__";
const DATA=__DATA__;
const COLS=__COLS__;
const QS=__QS__;
__APPJS__
</script>
</body></html>
"""

# ----------------------------------------------------------------------------- A/B app JS
AB_JS = r"""
let i=0;
const $=s=>document.querySelector(s);
const store=()=>"adsr_"+MODE+"_"+($("#who").value.trim()||"anon");
function load(){try{return JSON.parse(localStorage.getItem(store()))||{}}catch(e){return {}}}
function save(o){localStorage.setItem(store(),JSON.stringify(o));flash()}
let _t;function flash(){$("#save").textContent="已自动保存";clearTimeout(_t);_t=setTimeout(()=>$("#save").textContent="",1200)}
function render(){
  const d=DATA[i], ans=load(), a=ans[d.pair_id]||{};
  $("#grp").textContent="分组 "+d.group+"  ·  对 "+(i+1);
  const typeBadge = d.requested_type==="vocal"
    ? '<span class="badge voc">🎤 要求:有人声</span>'
    : '<span class="badge ins">🎹 要求:纯伴奏</span>';
  const lyr = (d.lyrics && d.requested_type==="vocal")
    ? '<details class="lyr"><summary>展开歌词(参考)</summary><pre>'+esc(d.lyrics)+'</pre></details>' : '';
  let qhtml="";
  QS.forEach(q=>{
    const opts=[["A","片段 A"],["tie","平局"],["B","片段 B"]]; if(q.na)opts.push(["NA","不适用"]);
    qhtml+='<div class="q"><div class="ql">'+q.t+(a[q.k]?' <span class="done">✓</span>':' <span class="req">*</span>')+'</div><div class="opts">'+
      opts.map(([v,lab])=>'<button data-q="'+q.k+'" data-v="'+v+'" class="'+(a[q.k]===v?(v==="NA"?"selna":"sel"):"")+'">'+lab+'</button>').join('')+'</div></div>';
  });
  $("#app").innerHTML=
   '<div class="card"><div class="meta">'+typeBadge+'<span class="badge grp">'+d.group+'</span></div>'+
   '<div class="ptext">'+esc(d.prompt_text||"(无 prompt 文本)")+'</div>'+lyr+
   '<div class="players">'+
     '<div class="pl"><h3>片段 A</h3><audio id="aA" controls preload="none" src="media/'+d.pair_id+'_A.'+d.ext+'"></audio><div class="key">播放快捷键: 1</div></div>'+
     '<div class="pl"><h3>片段 B</h3><audio id="aB" controls preload="none" src="media/'+d.pair_id+'_B.'+d.ext+'"></audio><div class="key">播放快捷键: 2</div></div>'+
   '</div>'+qhtml+
   '<div class="q"><div class="ql">把握程度(用于决定是否需要第三人加裁)</div><div class="opts">'+
     [["high","有把握"],["low","拿不准"]].map(([v,lab])=>'<button data-q="confidence" data-v="'+v+'" class="'+((a.confidence||"high")===v?"sel":"")+'">'+lab+'</button>').join('')+'</div></div>'+
   '<div class="q"><div class="ql">备注(可选)</div><textarea id="cm" rows="2" placeholder="任何说明...">'+esc(a.comment||"")+'</textarea></div>'+
   '<div class="hint">快捷键: 1/2 播放 A/B · ← → 上一条/下一条 · 数字键由你点选</div>'+
   '<div class="nav"><button id="prev">← 上一条</button><button id="next" class="next">下一条 →</button></div></div>';
  document.querySelectorAll('.opts button').forEach(b=>b.onclick=()=>{
    const o=load(); o[d.pair_id]=o[d.pair_id]||{}; o[d.pair_id][b.dataset.q]=b.dataset.v; save(o); render();
  });
  $("#cm").oninput=e=>{const o=load();o[d.pair_id]=o[d.pair_id]||{};o[d.pair_id].comment=e.target.value;save(o)};
  $("#prev").onclick=()=>{if(i>0){i--;render()}};
  $("#next").onclick=()=>{if(i<DATA.length-1){i++;render()}else alert("已是最后一条。请点底部「导出 CSV」。")};
  const done=DATA.filter(x=>complete((load()[x.pair_id])||{})).length;
  $("#pcount").textContent=done+" / "+DATA.length+" 完成";
  $("#pfill").style.width=(100*done/DATA.length)+"%";
}
function complete(a){return QS.every(q=>a[q.k])}
function esc(s){return (s||"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}
document.onkeydown=e=>{
  if(e.target.tagName==="TEXTAREA"||e.target.tagName==="INPUT")return;
  if(e.key==="1"){const a=document.getElementById("aA");if(a){a.paused?a.play():a.pause()}}
  if(e.key==="2"){const b=document.getElementById("aB");if(b){b.paused?b.play():b.pause()}}
  if(e.key==="ArrowLeft"&&i>0){i--;render()}
  if(e.key==="ArrowRight"&&i<DATA.length-1){i++;render()}
};
$("#who").value=localStorage.getItem("adsr_who")||"";
$("#who").oninput=()=>{localStorage.setItem("adsr_who",$("#who").value);render()};
function csv(){
  const o=load(), who=$("#who").value.trim(); const lines=[COLS.join(",")];
  DATA.forEach(d=>{const a=o[d.pair_id]||{};
    const row=[d.pair_id,who].concat(QS.map(q=>a[q.k]||"")).concat([a.confidence||"high",(a.comment||"").replace(/[\r\n,]/g," ")]);
    lines.push(row.join(","));});
  return lines.join("\n");
}
$("#exp").onclick=()=>{const who=$("#who").value.trim();if(!who){alert("请先在右上角填写评分员缩写");return}
  const done=DATA.filter(x=>complete((load()[x.pair_id])||{})).length;
  if(done<DATA.length && !confirm("还有 "+(DATA.length-done)+" 条未完成,仍要导出?"))return;
  dl(csv(),"ab_responses_"+who+".csv","text/csv");};
$("#expj").onclick=()=>{const who=$("#who").value.trim()||"anon";dl(JSON.stringify(load(),null,1),"ab_backup_"+who+".json","application/json")};
function dl(txt,name,mime){const b=new Blob([txt],{type:mime});const u=URL.createObjectURL(b);const a=document.createElement("a");a.href=u;a.download=name;a.click();URL.revokeObjectURL(u);$("#fstat").textContent="已下载 "+name}
render();
"""

# ----------------------------------------------------------------------------- Adjudication app JS
ADJ_JS = r"""
let i=0;
const $=s=>document.querySelector(s);
const store=()=>"adsr_"+MODE+"_"+($("#who").value.trim()||"anon");
function load(){try{return JSON.parse(localStorage.getItem(store()))||{}}catch(e){return {}}}
function save(o){localStorage.setItem(store(),JSON.stringify(o));flash()}
let _t;function flash(){$("#save").textContent="已自动保存";clearTimeout(_t);_t=setTimeout(()=>$("#save").textContent="",1200)}
function render(){
  const d=DATA[i], ans=load(), a=ans[d.case_id]||{};
  $("#grp").textContent="样本 "+(i+1);
  const opts=[["1","有人声"],["0","纯伴奏(无人声)"],["unsure","不确定"]];
  $("#app").innerHTML=
   '<div class="card"><div class="meta"><span class="badge grp">仅判断「有没有人声」,不看歌词清晰度</span></div>'+
   '<div class="pl single"><audio id="a0" controls preload="none" src="media/'+d.case_id+'.wav"></audio><div class="key">播放/暂停快捷键: 空格</div></div>'+
   '<div class="q"><div class="ql">这段里有人声吗?(任何人声/吟唱/说话都算「有」)'+(a.v?' <span class="done">✓</span>':' <span class="req">*</span>')+'</div><div class="opts">'+
     opts.map(([v,lab])=>'<button data-v="'+v+'" class="'+(a.v===v?"sel":"")+'">'+lab+'</button>').join('')+'</div></div>'+
   '<div class="q"><div class="ql">备注(可选)</div><textarea id="cm" rows="2">'+esc(a.comment||"")+'</textarea></div>'+
   '<div class="hint">快捷键: 空格 播放 · ← → 切换样本 · 1=有 / 0=无 / u=不确定</div>'+
   '<div class="nav"><button id="prev">← 上一条</button><button id="next" class="next">下一条 →</button></div></div>';
  document.querySelectorAll('.opts button').forEach(b=>b.onclick=()=>{const o=load();o[d.case_id]=o[d.case_id]||{};o[d.case_id].v=b.dataset.v;save(o);render()});
  $("#cm").oninput=e=>{const o=load();o[d.case_id]=o[d.case_id]||{};o[d.case_id].comment=e.target.value;save(o)};
  $("#prev").onclick=()=>{if(i>0){i--;render()}};
  $("#next").onclick=()=>{if(i<DATA.length-1){i++;render()}else alert("已是最后一条。请点底部「导出 CSV」。")};
  const done=DATA.filter(x=>((load()[x.case_id])||{}).v).length;
  $("#pcount").textContent=done+" / "+DATA.length+" 完成";
  $("#pfill").style.width=(100*done/DATA.length)+"%";
}
function esc(s){return (s||"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}
function set(v){const d=DATA[i],o=load();o[d.case_id]=o[d.case_id]||{};o[d.case_id].v=v;save(o);render()}
document.onkeydown=e=>{
  if(e.target.tagName==="TEXTAREA"||e.target.tagName==="INPUT")return;
  if(e.key===" "){e.preventDefault();const a=document.getElementById("a0");if(a){a.paused?a.play():a.pause()}}
  if(e.key==="1")set("1"); if(e.key==="0")set("0"); if(e.key.toLowerCase()==="u")set("unsure");
  if(e.key==="ArrowLeft"&&i>0){i--;render()} if(e.key==="ArrowRight"&&i<DATA.length-1){i++;render()}
};
$("#who").value=localStorage.getItem("adsr_who")||"";
$("#who").oninput=()=>{localStorage.setItem("adsr_who",$("#who").value);render()};
function csv(){const o=load(),who=$("#who").value.trim();const lines=[COLS.join(",")];
  DATA.forEach(d=>{const a=o[d.case_id]||{};lines.push([d.case_id,who,a.v||"",(a.comment||"").replace(/[\r\n,]/g," ")].join(","))});return lines.join("\n")}
$("#exp").onclick=()=>{const who=$("#who").value.trim();if(!who){alert("请先填写评分员缩写");return}
  const done=DATA.filter(x=>((load()[x.case_id])||{}).v).length;
  if(done<DATA.length && !confirm("还有 "+(DATA.length-done)+" 条未完成,仍导出?"))return;
  dl(csv(),"adjudication_responses_"+who+".csv","text/csv")};
$("#expj").onclick=()=>{const who=$("#who").value.trim()||"anon";dl(JSON.stringify(load(),null,1),"adj_backup_"+who+".json","application/json")};
function dl(txt,name,mime){const b=new Blob([txt],{type:mime});const u=URL.createObjectURL(b);const a=document.createElement("a");a.href=u;a.download=name;a.click();URL.revokeObjectURL(u);$("#fstat").textContent="已下载 "+name}
render();
"""


MERGELOSER_MIRROR = Path("/tmp/adsr_mergeloser_audio")


def _resolve(src: str) -> Path | None:
    """Resolve a packet audio path; fall back to the /tmp mirror for files relocated off Lustre."""
    real = Path(src) if os.path.isabs(src) else (REPO / src)
    if real.exists():
        return real
    # files under runs/adsr_recollect_resume/ may have been moved to the /tmp mirror
    prefix = "runs/adsr_recollect_resume/"
    if src.startswith(prefix):
        cand = MERGELOSER_MIRROR / src[len(prefix):]
        if cand.exists():
            return cand
    return None


def symfarm(media: Path, items, package: bool):
    import shutil
    if media.exists():
        shutil.rmtree(media)
    media.mkdir(parents=True)
    n = 0; missing = 0
    for name, src in items:
        dst = media / name
        real = _resolve(src)
        if real is None:
            missing += 1
            continue
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        if package:
            shutil.copy2(real, dst)
        else:
            dst.symlink_to(real.resolve())
        n += 1
    if missing:
        print(f"  WARNING: {missing} audio files unresolved under {media}", flush=True)
    return n


DIMS_FULL = [("overall_preference", "1. 总体更喜欢哪个?", False),
             ("musicality", "2. 音乐性更好?", False),
             ("prompt_fit", "3. 更贴合 prompt 描述?", False),
             ("vocal_type_correct", "4. 人声类型更正确?", False),
             ("lyric_intelligibility", "5. 歌词更清晰?(纯伴奏选 NA)", True),
             ("vocal_artifacts", "6. 瑕疵更少 / 更干净?", False)]
DIMS_REDUCED = [("overall_preference", "1. 总体更喜欢哪个?(主端点)", False),
                ("prompt_fit", "2. 更贴合 prompt 描述?", False),
                ("vocal_artifacts", "3. 瑕疵更少 / 更干净?", False)]
REDUCED_CONTRASTS = {"arm6_vs_arm1", "arm6_vs_arm4"}
REDUCED_PER_CONTRAST = 40


def _select_reduced_pairs(pairs, key):
    """2 contrasts × 40 pairs, stratified to preserve tail/lyric/general proportions (deterministic)."""
    from collections import defaultdict
    buckets = defaultdict(list)
    for pr in pairs:
        con = key[pr["pair_id"]]["contrast"]
        if con in REDUCED_CONTRASTS:
            buckets[(con, pr["group"])].append(pr)
    # original group split per contrast is 24 tail / 20 lyric / 16 general -> scale to 40
    cap = {"tail": 16, "lyric": 13, "general": 11}
    out = []
    for con in sorted(REDUCED_CONTRASTS):
        for g in ("tail", "lyric", "general"):
            ps = sorted(buckets.get((con, g), []), key=lambda p: p["pair_id"])
            out.extend(ps[:cap[g]])
    return out


def build_ab(package: bool, reduced: bool = False):
    pairs = [json.loads(l) for l in open(AB / "human_adsr_pairs.jsonl")]
    key = {k["pair_id"]: k for k in (json.loads(l) for l in open(AB / "UNBLINDING_KEY.jsonl"))}
    dims = DIMS_REDUCED if reduced else DIMS_FULL
    if reduced:
        pairs = _select_reduced_pairs(pairs, key)
    # prompt metadata from the canonical prompt sources (text/lyrics/requested type) — NOT arm
    sel = {json.loads(l)["prompt_id"]: json.loads(l)
           for l in open(B3 / "batch3/batch3_selected_prompts_256.jsonl")}
    psrc = {}
    for src in {r["prompt_source"] for r in sel.values()}:
        p = REPO / src
        if p.exists():
            for l in open(p):
                r = json.loads(l); psrc[r["prompt_id"]] = r
    data, media = [], []
    for pr in pairs:
        pid = key[pr["pair_id"]]["prompt_id"]
        pm = psrc.get(pid, {})
        rt = sel.get(pid, {}).get("vocal_stratum") or ("instrumental" if pm.get("metadata", {}).get("instrumental") else "vocal")
        ext = Path(pr["A"]).suffix.lstrip(".")
        data.append({"pair_id": pr["pair_id"], "group": pr["group"], "requested_type": rt,
                     "prompt_text": pm.get("text", ""), "lyrics": pm.get("lyrics"), "ext": ext})
        media.append((f'{pr["pair_id"]}_A.{ext}', pr["A"]))
        media.append((f'{pr["pair_id"]}_B.{ext}', pr["B"]))
    qs = [{"k": k, "t": t, "na": na} for (k, t, na) in dims]
    cols = (["pair_id", "rater_initials"]
            + [f"{k}(A/B/tie/NA)" if na else f"{k}(A/B/tie)" for (k, t, na) in dims]
            + ["confidence(high/low)", "comment"])
    html = (SHELL.replace("__TITLE__", "ADSR 盲听评测 · A/B 偏好")
            .replace("__MODE__", "ab").replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__COLS__", json.dumps(cols, ensure_ascii=False))
            .replace("__QS__", json.dumps(qs, ensure_ascii=False)).replace("__APPJS__", AB_JS))
    (AB / "index.html").write_text(html, encoding="utf-8")
    n = symfarm(AB / "media", media, package)
    return len(data), n


def _detector_disagreements():
    """case_ids where Demucs and PANNs disagree on vocal presence (highest human value)."""
    THR, PT = 0.1791, 0.0654
    lab = {}
    for l in open(B3 / "vocal_presence_raw.jsonl"):
        d = json.loads(l)
        if d.get("ok"):
            lab[(d["prompt_id"], d["candidate_index"])] = d
    pan = {}
    for l in open(B3 / "phase0/panns_labels.jsonl"):
        d = json.loads(l)
        if "panns_vocal_score" in d:
            pan[(d["prompt_id"], d["candidate_index"])] = d["panns_vocal_score"]
    dis = set()
    for c in (json.loads(l) for l in open(ADJ / "cases_blinded.jsonl")):
        k = (c["_internal"]["prompt_id"], c["_internal"]["candidate_index"])
        if k in lab and k in pan:
            if int(lab[k]["vocal_energy_ratio"] >= THR) != int(pan[k] >= PT):
                dis.add(c["case_id"])
    return dis


def build_adj(package: bool, reduced: bool = False):
    cases = [json.loads(l) for l in open(ADJ / "cases_blinded.jsonl")]
    seen = set(); uniq = []          # original packet has 8 exact-duplicate rows; show each once
    for c in cases:
        if c["case_id"] not in seen:
            seen.add(c["case_id"]); uniq.append(c)
    cases = uniq
    if reduced:
        keep = _detector_disagreements()
        cases = [c for c in cases if c["case_id"] in keep]
    data = [{"case_id": c["case_id"]} for c in cases]
    media = [(f'{c["case_id"]}.wav', c["audio_path"]) for c in cases]
    cols = ["case_id", "rater_initials", "vocals_present(0/1/unsure)", "comment"]
    html = (SHELL.replace("__TITLE__", "ADSR 人声有无判定")
            .replace("__MODE__", "adj").replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__COLS__", json.dumps(cols, ensure_ascii=False))
            .replace("__QS__", "[]").replace("__APPJS__", ADJ_JS))
    (ADJ / "adjudication.html").write_text(html, encoding="utf-8")
    n = symfarm(ADJ / "media", media, package)
    return len(data), n


DESIGN_DOC = """# 人评设计(预注册,缩减版 2026-06-20)

工作量从全量约 4925 个评分单位 → 约 810(**减少 ~84%**),经 Codex 方法学复核。
缩减只去掉冗余,不动两个承重主张:**(1) arm6 无可感质量代价;(2) Demucs 标签有效**。

## A/B 盲听偏好(80 对)
- **对比(2 个,承重)**: arm6 vs arm1(同算力部署基线)· arm6 vs arm4(同算力、只换种子的机制对照)。
  - 已去掉: arm6 vs arm7(算力预算不同,"胜过更高算力"由客观 ledger 证明,移附录)、arm6 vs arm2(随机对照,客观已覆盖)。
- **每对比 40 对**,分层保留 tail/lyric/general 比例(16/13/11)。非劣性(near-tie)按 1/√n 收窄,40/对比是可辩护下限。
- **评分维度(3,从 6 删)**: 总体偏好(主端点)· 贴合 prompt · 瑕疵更少。删去 vocal-type-correct(检测器已覆盖)、lyric(子集小且噪)、musicality(与总体偏好重叠)。
- **评分员**: 2 人全评 + **自适应加裁**(仅当两人主端点分歧、或任一人标"拿不准"时上第三人)。
- **措辞红线**: 只能说"在所测对比与预设边际内**未发现**可感质量代价",不能说"证明无质量损失"。

## 标签判定(112 例)
- 仅保留 **Demucs↔PANNs 不一致**的 112 例(人评最增信);两检测器已一致的 130 例报为低风险、可抽样抽查。
- 2 人 + 自适应加裁。不整包暂缓(标签有效性是人评两大任务之一,PANNs 78%/κ0.52 是验证非金标)。

## 回收
每人导出一份 CSV(列与 response_sheet 对齐,含 confidence 列驱动加裁);UNBLINDING_KEY 仅 PI 持有。
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", action="store_true", help="copy real audio (portable) instead of symlinks")
    ap.add_argument("--reduced", action="store_true", help="reduced design: 2 contrasts×40, 3 dims, 112 adj cases")
    args = ap.parse_args()
    nab, mab = build_ab(args.package, args.reduced)
    nadj, madj = build_adj(args.package, args.reduced)
    if args.reduced:
        (B3 / "phase3/HUMAN_EVAL_DESIGN.md").write_text(DESIGN_DOC, encoding="utf-8")
    serve = (
        "# 人评界面 — 启动说明\n\n"
        "两个自带界面已生成(无需安装,离线可用):\n\n"
        "- A/B 偏好: `phase3/human_ab/index.html`(%d 对,%d 个音频)\n"
        "- 人声判定: `phase0/rater_packet/adjudication.html`(%d 例,%d 个音频)\n\n"
        "## 方式一(推荐,在集群上起本地服务)\n"
        "```bash\n"
        "cd orbit-research/adsr_phase2_20260604/phase3/human_ab   # 或 phase0/rater_packet\n"
        "python -m http.server 8731\n"
        "```\n"
        "评分员浏览器打开 `http://<本机或隧道>:8731/index.html`(判定包用 `adjudication.html`)。\n"
        "用 Chrome / Firefox(支持 FLAC 播放)。\n\n"
        "## 方式二(发给远端评分员)\n"
        "`python scripts/build_human_ui.py --package` 会把真实音频拷进 `media/`,然后把整个\n"
        "`phase3/human_ab/`(或 `phase0/rater_packet/`)目录打包发给评分员,本地双击 html 即可\n"
        "(file:// 下用 Chrome/Firefox)。\n\n"
        "## 使用与回收\n"
        "- 右上角填**评分员缩写**;答题自动存浏览器(刷新不丢);完成后点底部「导出 CSV」。\n"
        "- **2 位评分员**全评 + 自适应加裁(仅当主端点分歧、或有人标「拿不准」才上第三人);各自导出 CSV。\n"
        "- A/B 的 `UNBLINDING_KEY.jsonl` 是 **PI 专属解盲钥匙,切勿给评分员**。\n"
    ) % (nab, mab, nadj, madj)
    (B3 / "phase3/HUMAN_UI_README.md").write_text(serve, encoding="utf-8")
    print(json.dumps({"ab_pairs": nab, "ab_media": mab, "adj_cases": nadj, "adj_media": madj,
                      "package_mode": args.package,
                      "ab_html": str((AB / "index.html")),
                      "adj_html": str((ADJ / "adjudication.html"))}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
