#!/usr/bin/env python3
"""Build the five self-contained, nonce-blinded 2026-07-11 rater bundles."""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import html
import json
import os
import shutil
import zipfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PAPER_PREP = ROOT / "orbit-research/adsr_phase2_20260604/paper_prep"
KEYS = PAPER_PREP / "rater_admin_keys_20260711"
DEFAULT_OUTPUT = PAPER_PREP / "rater_bundles_20260711"
PROMPT_REGISTRY = ROOT / "configs/prompts/held_out.jsonl"
SHUFFLE_SEED = 20260711

LABEL_A_WORDING = (
    "Do you hear any sound a reasonable listener would perceive as a human voice "
    "or vocalization? Includes singing, rap, speech, chant, humming, wordless "
    "vocals, choir, ooh/ah, vocal chops. Answer Yes / No / Unsure; then select "
    "perceived vocal type and whether it is isolated, intermittent, or sustained."
)
VOCAL_LABEL_B_RULE = (
    "Vocal request → Satisfied only when clearly audible vocals function as an "
    "intentional musical element; a fleeting isolated chop, ambiguous voice-like "
    "texture, or background artifact is not sufficient."
)
INSTRUMENTAL_LABEL_B_RULE = (
    "Instrumental request → Violated when perceived vocal content is salient, recurrent, or functions as "
    "a musical element, or when any phrase is clearly sung, spoken, or rapped; a "
    "single isolated non-linguistic one-shot shorter than ~2 s is normally not a "
    "violation unless unusually prominent."
)
LABEL_B_WORDING = f"{VOCAL_LABEL_B_RULE} {INSTRUMENTAL_LABEL_B_RULE}"
CHOIR_RULE = (
    "Choir-pad rule: perceived as human choir → A=Yes and instrumental request "
    "normally violated; perceived as synth timbre → A=No; ambiguous → Unsure."
)
QUALITY_WORDING = (
    "Judge musical/audio quality while setting aside whether the clip correctly "
    "contains or omits vocals. Consider production quality, artifacts, musical "
    "coherence, naturalness, and listening quality."
)

V2_IDENTITY_NAMES = {
    "t1_decisive_v2": "t1_decisive",
    "t3_bprime_primary_v2": "t3_bprime_primary",
    "t4_bprime_reverse_v2": "t4_bprime_reverse",
}
ACTIVE_BUNDLES = {
    "t1_decisive_v2": (42, 42),
    "t2_aprime_core": (190, 190),
    "t3_bprime_primary_v2": (80, 160),
    "t4_bprime_reverse_v2": (24, 48),
    "t5_sa3_calibration": (60, 60),
}
FORBIDDEN_PUBLIC_FIELDS = {
    "expected_label",
    "expected_demucs_label",
    "bucket",
    "set_name",
    "set-name",
    "arm",
}
ALLOWED_ROW_FIELDS = {
    "decisive": {"rating_id", "media", "request_type"},
    "decisive_staged": {"rating_id", "media", "request_mode"},
    "label": {"rating_id", "media"},
    "pair": {"rating_id", "media_a", "media_b", "request_text"},
    "pair_staged": {
        "rating_id",
        "media_a",
        "media_b",
        "prompt_text",
        "request_mode",
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
    return rows


def request_mode(requested_vocal: str) -> str:
    if requested_vocal == "1":
        return "vocal"
    if requested_vocal == "0":
        return "instrumental"
    raise ValueError(f"requested_vocal must be 0 or 1, got {requested_vocal!r}")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def opaque_digest(nonce: str, bundle: str, source_id: str, purpose: str) -> str:
    payload = f"{SHUFFLE_SEED}|{bundle}|{source_id}|{purpose}".encode()
    return hmac.new(nonce.encode(), payload, hashlib.sha256).hexdigest()


def resolve_repo_path(value: str, package_dir: Path) -> Path:
    path = Path(value)
    candidates = [path] if path.is_absolute() else [package_dir / path, ROOT / path]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"bundle source media is missing: {value}")


def link_media(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite bundle media: {destination}")
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def safe_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


STAGE_POLICY_JS = r'''
function hasValue(value){return String(value??"").length>0}
function labelAComplete(response){return ["label_a_voice_presence","perceived_vocal_type","vocal_extent"].every(field=>hasValue(response[field]))}
function stagePolicy(mode,response){
 const revealed=Boolean(response.request_revealed);
 if(mode==="decisive_staged")return {
  reveal_enabled:labelAComplete(response)&&!revealed,
  context_visible:revealed,
  label_a_enabled:!revealed||Boolean(response.label_a_editing),
  label_b_enabled:revealed,
  secondary_enabled:revealed
 };
 if(mode==="pair_staged")return {
  reveal_enabled:hasValue(response.quality_preference)&&!revealed,
  context_visible:revealed,
  quality_enabled:!revealed,
  secondary_enabled:revealed
 };
 return {reveal_enabled:false,context_visible:mode==="pair",label_a_enabled:true,label_b_enabled:true,quality_enabled:true,secondary_enabled:true};
}
function setLabelAEditing(response,enabled){response.label_a_editing=Boolean(enabled);if(enabled)response.label_a_amended=true;return response}
function matchingLabelBRule(mode){if(mode==="vocal")return __VOCAL_RULE_JSON__;if(mode==="instrumental")return __INSTRUMENTAL_RULE_JSON__;throw new Error("invalid request mode")}
function exportFieldNames(mode){
 if(mode==="decisive_staged")return ["label_a_voice_presence","perceived_vocal_type","vocal_extent","label_b_constraint","confidence_1_to_5","notes","request_mode","label_a_amended","reveal_sequence"];
 if(mode==="decisive")return ["label_a_voice_presence","perceived_vocal_type","vocal_extent","label_b_constraint","confidence_1_to_5","notes"];
 if(mode==="pair_staged")return ["quality_preference","constraint_preference","overall_preference","confidence_1_to_5","notes","prompt_text","request_mode","request_revealed","quality_answer_sequence","reveal_sequence","constraint_answer_sequence","overall_answer_sequence"];
 if(mode==="pair")return ["quality_preference","overall_preference","constraint_preference","confidence_1_to_5","notes"];
 return ["label_a_voice_presence","confidence_1_to_5","notes"];
}
'''


HTML_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{color-scheme:light;--ink:#17202a;--muted:#5b6672;--line:#d5dbe1;--accent:#176b5b;--paper:#fff;--wash:#f3f5f6}
*{box-sizing:border-box}body{margin:0;background:var(--wash);color:var(--ink);font:15px/1.45 system-ui,sans-serif;letter-spacing:0}
header{position:sticky;top:0;z-index:2;background:#fff;border-bottom:1px solid var(--line);padding:12px 20px;display:flex;gap:16px;align-items:center}
h1{font-size:18px;margin:0;flex:1}main{max-width:920px;margin:0 auto;padding:20px}.panel{background:var(--paper);border:1px solid var(--line);border-radius:6px;padding:18px}
.meta{display:flex;gap:16px;color:var(--muted);margin-bottom:12px}.prompt{white-space:pre-wrap;padding:10px 12px;background:var(--wash);border-left:3px solid var(--accent);margin:12px 0}
.request-context{border:2px solid var(--ink);padding:14px;margin:16px 0}.request-mode{font-size:24px;font-weight:800;text-align:center}.rule{margin-top:12px;font-weight:600}
.wording{font-size:14px;margin:14px 0}.question{border-top:1px solid var(--line);padding-top:14px;margin-top:14px}.question h2{font-size:15px;margin:0 0 8px}
.choices{display:flex;flex-wrap:wrap;gap:8px}.choices label{display:flex;align-items:center;gap:5px;border:1px solid var(--line);border-radius:4px;padding:7px 10px;background:#fff}
audio{width:100%;margin:8px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}.pair strong{display:block}.field{margin-top:14px}.field label{display:block;font-weight:600;margin-bottom:5px}
select,input,textarea{font:inherit;border:1px solid #9da7b1;border-radius:4px;padding:7px;background:#fff}textarea{width:100%;min-height:74px}.confidence{width:90px}
.stage-controls{display:flex;align-items:center;gap:16px;margin:16px 0}.stage-controls button,.nav button,.export button{border:0;border-radius:4px;padding:9px 13px;background:#263746;color:#fff;font:inherit;cursor:pointer}.stage-controls button:disabled,.nav button:disabled{opacity:.35;cursor:not-allowed}.amend{font-weight:600}
.nav{display:flex;justify-content:space-between;gap:12px;margin-top:18px}
.export{display:flex;gap:8px}.export button{background:var(--accent)}#sourceGate{max-width:520px;margin:80px auto}.error{color:#9d1c24;font-weight:600}.hint{color:var(--muted);font-size:13px}.hidden{display:none!important}
@media(max-width:680px){header{align-items:flex-start;flex-wrap:wrap}.pair{grid-template-columns:1fr}main{padding:10px}.panel{padding:13px}}
</style>
</head>
<body>
<script id="bundle-data" type="application/json">__DATA_JSON__</script>
<section id="sourceGate" class="panel">
  <h1>Rater identity</h1>
  <p>Enter one approved source once: <code>pi:&lt;name&gt;</code> or <code>human:CXY</code>.</p>
  <input id="sourceInput" autocomplete="off" placeholder="pi:Richard Ye">
  <button id="sourceSave">Begin</button>
  <p id="sourceError" class="error"></p>
</section>
<div id="app" class="hidden">
<header><h1 id="title"></h1><span id="progress"></span><div class="export"><button id="csvExport">CSV</button><button id="jsonExport">JSON</button></div></header>
<main><section class="panel">
  <div class="meta"><span id="position"></span><span id="sourceDisplay"></span></div>
  <div id="audio"></div><div id="wording" class="wording"></div><div id="questions"></div>
  <div id="stageControls" class="stage-controls hidden"><button id="revealRequest" disabled>Reveal request</button><label id="amendControl" class="amend hidden"><input id="amendLabelA" type="checkbox"> amend Label A</label></div>
  <div id="requestContext" class="request-context hidden"><div id="requestMode" class="request-mode"></div><div id="prompt" class="prompt hidden"></div><div id="labelBRule" class="rule hidden"></div></div>
  <div class="field"><label for="confidence">Confidence (1–5)</label><select id="confidence" class="confidence"><option value=""></option><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option></select></div>
  <div class="field"><label for="notes">Comment / notes</label><textarea id="notes"></textarea></div>
  <div class="nav"><button id="previous">← Previous</button><span class="hint">1/2/3: primary answer · Space: play · ←/→: navigate</span><button id="next">Next →</button></div>
</section></main></div>
<script>
"use strict";
__STAGE_POLICY_JS__
const bundle=JSON.parse(document.getElementById("bundle-data").textContent);
const storageKey="adsr-rater-v2:"+bundle.bundle_id;
let state=JSON.parse(localStorage.getItem(storageKey)||'{"rating_source":"","responses":{},"event_counter":0}');
state.responses=state.responses||{};state.event_counter=Number(state.event_counter||0);
let cursor=0;
const $=id=>document.getElementById(id);
function validSource(v){return /^(pi:[A-Za-z][A-Za-z0-9 ._-]{0,63}|human:CXY)$/.test(v)}
function persist(){localStorage.setItem(storageKey,JSON.stringify(state))}
function begin(){if(!validSource(state.rating_source))return;$("sourceGate").classList.add("hidden");$("app").classList.remove("hidden");render()}
$("sourceSave").onclick=()=>{const v=$("sourceInput").value.trim();if(!validSource(v)){ $("sourceError").textContent="Use pi:<name> or human:CXY exactly.";return}state.rating_source=v;persist();begin()};
function radio(name,label,choices){return '<div class="question" data-question="'+name+'"><h2>'+label+'</h2><div class="choices">'+choices.map(v=>'<label><input type="radio" name="'+name+'" value="'+v+'">'+v+'</label>').join("")+'</div></div>'}
function selectField(name,label,choices){return '<div class="field"><label for="'+name+'">'+label+'</label><select id="'+name+'"><option value=""></option>'+choices.map(v=>'<option>'+v+'</option>').join("")+'</select></div>'}
function questionMarkup(){
 if(bundle.mode==="decisive"||bundle.mode==="decisive_staged")return radio("label_a_voice_presence","Label A: voice presence",["yes","no","unsure"])+selectField("perceived_vocal_type","Perceived vocal type",["singing","rap","speech","chant","humming","wordless vocals","choir","ooh/ah","vocal chops","voice-like/ambiguous","none"])+selectField("vocal_extent","Vocal extent",["isolated","intermittent","sustained","none","unsure"])+radio("label_b_constraint","Label B: constraint",["satisfied","violated","unsure"]);
 if(bundle.mode==="pair"||bundle.mode==="pair_staged")return radio("quality_preference","Quality preference (PRIMARY)",["A","B","tie"])+radio("constraint_preference","Constraint preference",["A","B","tie"])+radio("overall_preference","Overall preference",["A","B","tie"]);
 return radio("label_a_voice_presence","Voice presence",["yes","no","unsure"]);
}
function responseFields(){return exportFieldNames(bundle.mode).filter(field=>!["request_mode","prompt_text","request_revealed","label_a_amended","reveal_sequence","quality_answer_sequence","constraint_answer_sequence","overall_answer_sequence"].includes(field))}
function fieldElement(field){if(field==="confidence_1_to_5")return $("confidence");if(field==="notes")return $("notes");return document.querySelector('[name="'+field+'"]:checked')||$(field)}
function setFieldDisabled(field,disabled){document.querySelectorAll('[name="'+field+'"]' ).forEach(el=>el.disabled=disabled);const byId=$(field);if(byId)byId.disabled=disabled}
function showQuestion(field,show){const el=document.querySelector('[data-question="'+field+'"]');if(el)el.classList.toggle("hidden",!show)}
function markSequence(response,field){const key={quality_preference:"quality_answer_sequence",constraint_preference:"constraint_answer_sequence",overall_preference:"overall_answer_sequence"}[field];if(key&&!response[key]){state.event_counter+=1;response[key]=state.event_counter}}
function refreshStageAvailability(){const row=bundle.rows[cursor],r=state.responses[row.rating_id]||{},policy=stagePolicy(bundle.mode,r);if(bundle.mode==="decisive_staged"||bundle.mode==="pair_staged")$("revealRequest").disabled=!policy.reveal_enabled}
function saveCurrent(changedField=""){const row=bundle.rows[cursor],r=state.responses[row.rating_id]||{};for(const field of responseFields()){const el=fieldElement(field);r[field]=el?el.value:""}if(changedField)markSequence(r,changedField);state.responses[row.rating_id]=r;persist();refreshStageAvailability();updateProgress()}
function render(){const row=bundle.rows[cursor],r=state.responses[row.rating_id]||{},policy=stagePolicy(bundle.mode,r);$("title").textContent=bundle.title;$("position").textContent=(cursor+1)+" / "+bundle.rows.length;$("sourceDisplay").textContent=state.rating_source;
 $("audio").innerHTML=(bundle.mode==="pair"||bundle.mode==="pair_staged")?'<div class="pair"><div><strong>A</strong><audio controls preload="metadata" src="'+row.media_a+'"></audio></div><div><strong>B</strong><audio controls preload="metadata" src="'+row.media_b+'"></audio></div></div>':'<audio controls preload="metadata" src="'+row.media+'"></audio>';
 $("wording").innerHTML=bundle.wording_html;$("questions").innerHTML=questionMarkup();for(const field of responseFields()){const value=r[field]||"";if(field==="confidence_1_to_5")$("confidence").value=value;else if(field==="notes")$("notes").value=value;else{const el=document.querySelector('[name="'+field+'"][value="'+value+'"]')||$(field);if(el){if(el.type==="radio")el.checked=true;else el.value=value}}}
 const staged=bundle.mode==="decisive_staged"||bundle.mode==="pair_staged";$("stageControls").classList.toggle("hidden",!staged);$("revealRequest").classList.toggle("hidden",!staged||policy.context_visible);$("revealRequest").disabled=!policy.reveal_enabled;$("requestContext").classList.toggle("hidden",!policy.context_visible);
 $("requestMode").textContent=policy.context_visible?"REQUEST: "+String(row.request_mode||"").toUpperCase():"";const promptText=row.prompt_text||row.request_text||"";$("prompt").textContent=promptText;$("prompt").classList.toggle("hidden",!policy.context_visible||!promptText);$("labelBRule").textContent=bundle.mode==="decisive_staged"&&policy.context_visible?matchingLabelBRule(row.request_mode):"";$("labelBRule").classList.toggle("hidden",bundle.mode!=="decisive_staged"||!policy.context_visible);
 if(bundle.mode==="decisive_staged"){["label_a_voice_presence","perceived_vocal_type","vocal_extent"].forEach(field=>setFieldDisabled(field,!policy.label_a_enabled));showQuestion("label_b_constraint",policy.label_b_enabled);setFieldDisabled("label_b_constraint",!policy.label_b_enabled);$("amendControl").classList.toggle("hidden",!policy.context_visible);$("amendLabelA").checked=Boolean(r.label_a_editing)}else{$("amendControl").classList.add("hidden")}
 if(bundle.mode==="pair_staged"){setFieldDisabled("quality_preference",!policy.quality_enabled);for(const field of ["constraint_preference","overall_preference"]){showQuestion(field,policy.secondary_enabled);setFieldDisabled(field,!policy.secondary_enabled)}}
 const secondaryLocked=(bundle.mode==="decisive_staged"||bundle.mode==="pair_staged")&&!policy.secondary_enabled;$("confidence").disabled=secondaryLocked;$("notes").disabled=secondaryLocked;
 document.querySelectorAll("#app input[type=radio],#app select").forEach(el=>el.addEventListener("change",()=>saveCurrent(el.name||el.id)));$("notes").addEventListener("input",()=>saveCurrent("notes"));$("amendLabelA").onchange=()=>{setLabelAEditing(r,$("amendLabelA").checked);state.responses[row.rating_id]=r;persist();render()};$("previous").disabled=cursor===0;$("next").disabled=cursor===bundle.rows.length-1;updateProgress()}
function rowComplete(row){const response=state.responses[row.rating_id]||{};if((bundle.mode==="decisive_staged"||bundle.mode==="pair_staged")&&!response.request_revealed)return false;return responseFields().filter(field=>field!=="notes").every(field=>hasValue(response[field]))}
function updateProgress(){const done=bundle.rows.filter(rowComplete).length;$("progress").textContent=done+" / "+bundle.rows.length+" complete"}
$("revealRequest").onclick=()=>{saveCurrent();const row=bundle.rows[cursor],r=state.responses[row.rating_id]||{},policy=stagePolicy(bundle.mode,r);if(!policy.reveal_enabled)return;r.request_revealed=true;state.event_counter+=1;r.reveal_sequence=state.event_counter;state.responses[row.rating_id]=r;persist();render()};
$("previous").onclick=()=>{saveCurrent();if(cursor>0){cursor--;render()}};$("next").onclick=()=>{saveCurrent();if(cursor<bundle.rows.length-1){cursor++;render()}};
function csvCell(v){return '"'+String(v??"").replaceAll('"','""')+'"'}
function exportRows(){saveCurrent();return bundle.rows.map(row=>{const r=state.responses[row.rating_id]||{},out={rating_id:row.rating_id};for(const field of exportFieldNames(bundle.mode)){if(field==="request_mode"||field==="prompt_text")out[field]=row[field]||"";else if(field==="request_revealed"||field==="label_a_amended")out[field]=Boolean(r[field]);else out[field]=r[field]??""}out.rating_source=state.rating_source;return out})}
function download(name,text,type){const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;document.body.appendChild(a);a.click();URL.revokeObjectURL(a.href);a.remove()}
function initials(){return state.rating_source.split(":",2)[1].replace(/[^A-Za-z0-9]+/g,"_")}
$("csvExport").onclick=()=>{const rows=exportRows(),heads=Object.keys(rows[0]);download("responses_"+initials()+".csv",heads.join(",")+"\n"+rows.map(r=>heads.map(h=>csvCell(r[h])).join(",")).join("\n")+"\n","text/csv")};
$("jsonExport").onclick=()=>download("responses_"+initials()+".json",JSON.stringify({bundle_id:bundle.bundle_id,rating_source:state.rating_source,exported_at:new Date().toISOString(),responses:exportRows()},null,2)+"\n","application/json");
document.addEventListener("keydown",e=>{if(e.target.matches("input,textarea,select"))return;if(e.key==="ArrowLeft")$("previous").click();if(e.key==="ArrowRight")$("next").click();if(e.key===" "){e.preventDefault();const a=document.querySelectorAll("audio")[e.shiftKey?1:0];if(a)a.paused?a.play():a.pause()}if(["1","2","3"].includes(e.key)){const q=(bundle.mode==="pair"||bundle.mode==="pair_staged")?"quality_preference":"label_a_voice_presence",opts=[...document.querySelectorAll('[name="'+q+'"]')].filter(el=>!el.disabled);if(opts[Number(e.key)-1]){opts[Number(e.key)-1].checked=true;saveCurrent(q)}}});
if(state.rating_source){if(validSource(state.rating_source))begin();else{state={rating_source:"",responses:{}};persist()}}
</script>
</body></html>
'''


def render_html(title: str, payload: dict[str, object]) -> str:
    return (
        HTML_TEMPLATE.replace("__TITLE__", html.escape(title))
        .replace("__DATA_JSON__", safe_json(payload))
        .replace("__STAGE_POLICY_JS__", STAGE_POLICY_JS)
        .replace("__VOCAL_RULE_JSON__", safe_json(VOCAL_LABEL_B_RULE))
        .replace("__INSTRUMENTAL_RULE_JSON__", safe_json(INSTRUMENTAL_LABEL_B_RULE))
    )


def build_rows(nonce: str) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []

    decisive_dir = PAPER_PREP / "pi_decisive_packet_20260709"
    decisive = read_csv(decisive_dir / "DECISIVE_PACKET_RATINGS.csv")
    if len(decisive) != 42:
        raise ValueError(f"t1 source must contain 42 rows, found {len(decisive)}")
    specs.append(
        {
            "name": "t1_decisive",
            "title": "Decisive construct rating",
            "mode": "decisive",
            "readme": [
                "t1_decisive blinded rating bundle (42 clips).",
                "Open index.html in a modern browser; keep this directory beside media/.",
                "Export both responses_<initials>.csv and the JSON backup when complete.",
            ],
            "wording": (
                f"<p><strong>Label A:</strong> {html.escape(LABEL_A_WORDING)}</p>"
                f"<p><strong>Label B:</strong> {html.escape(LABEL_B_WORDING)}</p>"
                f"<p>{html.escape(CHOIR_RULE)}</p>"
            ),
            "source_dir": decisive_dir,
            "rows": decisive,
            "id_field": "rating_id",
            "media_fields": ["media_path"],
            "public_fields": ["request_type"],
            "key_path": KEYS / "t1_decisive/T1_BUNDLE_KEY.csv",
        }
    )

    aprime_dir = PAPER_PREP / "validation_A_prime/primary_package_20260709"
    aprime_ratings = read_csv(aprime_dir / "A_PRIME_PRIMARY_RATINGS.csv")
    aprime_admin = read_csv(KEYS / "t2_aprime/A_PRIME_PRIMARY_ADMIN.csv")
    selected_ids = {
        row["rating_id"] for row in aprime_admin if row["analysis_role"] == "primary"
    }
    selected = [row for row in aprime_ratings if row["rating_id"] in selected_ids]
    bucket_counts = Counter(
        row["set_bucket"] for row in aprime_admin if row["rating_id"] in selected_ids
    )
    expected_buckets = {
        "detector_disagreement_112": 112,
        "rare_basin_48": 48,
        "agreement_spotcheck_30": 30,
    }
    if len(selected) != 190 or bucket_counts != expected_buckets:
        raise ValueError(
            f"t2 must be the exact 190-row human core; found {len(selected)}, "
            f"{dict(bucket_counts)}"
        )
    specs.append(
        {
            "name": "t2_aprime_core",
            "title": "A-prime human-core rating",
            "mode": "label",
            "readme": [
                "t2_aprime_core blinded rating bundle (190 clips).",
                "Open index.html in a modern browser; keep this directory beside media/.",
                "Export both responses_<initials>.csv and the JSON backup when complete.",
            ],
            "wording": f"<p>{html.escape(LABEL_A_WORDING)}</p>",
            "source_dir": aprime_dir,
            "rows": selected,
            "id_field": "rating_id",
            "media_fields": ["media_path"],
            "public_fields": [],
            "key_path": KEYS / "t2_aprime/T2_BUNDLE_KEY.csv",
        }
    )

    bprime_dir = PAPER_PREP / "validation_B_prime/pi_package_20260709"
    bprime_ratings = read_csv(bprime_dir / "B_PRIME_PI_RATINGS.csv")
    bprime_admin = read_csv(KEYS / "t3_t4_bprime/B_PRIME_ORDERED_ADMIN.csv")
    ratings_by_id = {row["rating_id"]: row for row in bprime_ratings}
    for name, role, count, key_name in [
        ("t3_bprime_primary", "primary", 80, "T3_BUNDLE_KEY.csv"),
        ("t4_bprime_reverse", "reliability_reverse", 24, "T4_BUNDLE_KEY.csv"),
    ]:
        role_ids = [row["rating_id"] for row in bprime_admin if row["presentation_role"] == role]
        rows = [ratings_by_id[rating_id] for rating_id in role_ids]
        if len(rows) != count or len(set(role_ids)) != count:
            raise ValueError(f"{name} must contain exactly {count} unique rows")
        readme_last = (
            "Important: open on a later day than t3; then export CSV and JSON."
            if role == "reliability_reverse"
            else "Export both responses_<initials>.csv and the JSON backup when complete."
        )
        specs.append(
            {
                "name": name,
                "title": "B-prime primary rating" if role == "primary" else "B-prime delayed reverse rating",
                "mode": "pair",
                "readme": [
                    f"{name} blinded rating bundle ({count} pairs).",
                    "Open index.html in a modern browser; keep this directory beside media/.",
                    readme_last,
                ],
                "wording": f"<p><strong>Quality preference:</strong> {html.escape(QUALITY_WORDING)}</p>",
                "source_dir": bprime_dir,
                "rows": rows,
                "id_field": "rating_id",
                "media_fields": ["media_a_path", "media_b_path"],
                "public_fields": ["request_text"],
                "key_path": KEYS / f"t3_t4_bprime/{key_name}",
            }
        )

    sa3_dir = PAPER_PREP / "sao/stable_audio_3_medium/label_calibration"
    sa3 = read_csv(sa3_dir / "SA3_LABEL_CALIBRATION_RATINGS.csv")
    if len(sa3) != 60:
        raise ValueError(f"t5 source must contain 60 rows, found {len(sa3)}")
    specs.append(
        {
            "name": "t5_sa3_calibration",
            "title": "SA3 detector calibration rating",
            "mode": "label",
            "readme": [
                "t5_sa3_calibration blinded rating bundle (60 clips).",
                "Open index.html in a modern browser; keep this directory beside media/.",
                "Export both responses_<initials>.csv and the JSON backup when complete.",
            ],
            "wording": f"<p>{html.escape(LABEL_A_WORDING)}</p>",
            "source_dir": sa3_dir,
            "rows": sa3,
            "id_field": "blind_id",
            "media_fields": ["audio_path"],
            "public_fields": [],
            "key_path": KEYS / "t5_sa3_calibration/T5_BUNDLE_KEY.csv",
        }
    )

    for spec in specs:
        name = str(spec["name"])
        rows = list(spec["rows"])
        id_field = str(spec["id_field"])
        rows.sort(
            key=lambda row: opaque_digest(
                nonce, name, row[id_field], "order"
            )
        )
        spec["rows"] = rows
    return specs


def build_v2_rows(nonce: str) -> list[dict[str, object]]:
    """Build only the request-reveal fixes while retaining v1 IDs and order."""
    v1_specs = {str(spec["name"]): spec for spec in build_rows(nonce)}

    t1_admin_rows = read_csv(KEYS / "t1_decisive/DECISIVE_PACKET_ADMIN.csv")
    t1_admin = {row["rating_id"]: row for row in t1_admin_rows}
    t1_source = v1_specs["t1_decisive"]
    t1_source_rows = list(t1_source["rows"])
    if set(t1_admin) != {row["rating_id"] for row in t1_source_rows}:
        raise ValueError("t1 admin/rating ID sets differ; refusing request-mode join")
    t1_rows: list[dict[str, str]] = []
    for row in t1_source_rows:
        mode = request_mode(t1_admin[row["rating_id"]]["requested_vocal"])
        if row["request_type"].strip().lower() != mode:
            raise ValueError(f"t1 request metadata conflict for {row['rating_id']}")
        t1_rows.append({**row, "request_mode": mode})
    t1 = {
        **t1_source,
        "name": "t1_decisive_v2",
        "identity_name": "t1_decisive",
        "title": "Decisive construct rating v2",
        "mode": "decisive_staged",
        "readme": [
            "t1_decisive_v2 staged, blinded rating bundle (42 clips).",
            "Complete Label A, reveal the request, then complete Label B and export.",
            "Export both responses_<initials>.csv and the JSON backup when complete.",
        ],
        "wording": (
            f"<p><strong>Label A:</strong> {html.escape(LABEL_A_WORDING)}</p>"
            f"<p>{html.escape(CHOIR_RULE)}</p>"
        ),
        "rows": t1_rows,
        "public_fields": ["request_mode"],
        "key_metadata_fields": ["request_mode"],
        "key_path": KEYS / "t1_decisive/T1_BUNDLE_KEY_V2.csv",
    }

    pair_manifest_rows = read_csv(PAPER_PREP / "validation_B_prime/B_PRIME_MANIFEST.csv")
    pair_manifest = {row["pair_id"]: row for row in pair_manifest_rows}
    ordered_rows = read_csv(KEYS / "t3_t4_bprime/B_PRIME_ORDERED_ADMIN.csv")
    ordered_admin = {row["rating_id"]: row for row in ordered_rows}
    prompt_rows = read_jsonl(PROMPT_REGISTRY)
    prompt_registry = {str(row["prompt_id"]): row for row in prompt_rows}

    v2_specs: list[dict[str, object]] = [t1]
    for old_name, new_name, key_name in [
        ("t3_bprime_primary", "t3_bprime_primary_v2", "T3_BUNDLE_KEY_V2.csv"),
        ("t4_bprime_reverse", "t4_bprime_reverse_v2", "T4_BUNDLE_KEY_V2.csv"),
    ]:
        source = v1_specs[old_name]
        enriched: list[dict[str, str]] = []
        for row in source["rows"]:
            admin = ordered_admin.get(row["rating_id"])
            if admin is None:
                raise ValueError(f"missing ordered admin row for {row['rating_id']}")
            pair = pair_manifest.get(admin["pair_id"])
            if pair is None:
                raise ValueError(f"missing B-prime pair manifest row for {admin['pair_id']}")
            prompt = prompt_registry.get(pair["prompt_id"])
            if prompt is None:
                raise ValueError(f"missing prompt-registry row for {pair['prompt_id']}")
            prompt_text = str(prompt["text"])
            if row["request_text"] != pair["request_text"] or prompt_text != pair["request_text"]:
                raise ValueError(f"B-prime prompt-text conflict for {row['rating_id']}")
            strata = dict(prompt["strata"])
            metadata = dict(prompt["metadata"])
            mode = str(strata["vocal_vs_instrumental"])
            if mode not in {"vocal", "instrumental"}:
                raise ValueError(f"invalid prompt request mode for {pair['prompt_id']}: {mode}")
            if "instrumental" in metadata and bool(metadata["instrumental"]) != (
                mode == "instrumental"
            ):
                raise ValueError(f"prompt request metadata conflict for {pair['prompt_id']}")
            enriched.append(
                {
                    **row,
                    "prompt_text": prompt_text,
                    "request_mode": mode,
                }
            )
        readme = list(source["readme"])
        readme[0] = readme[0].replace(old_name, new_name)
        readme[1] = "Rate quality blind, reveal request context, then rate constraint and overall preference."
        v2_specs.append(
            {
                **source,
                "name": new_name,
                "identity_name": old_name,
                "title": str(source["title"]) + " v2",
                "mode": "pair_staged",
                "readme": readme,
                "rows": enriched,
                "public_fields": ["prompt_text", "request_mode"],
                "key_metadata_fields": ["request_mode"],
                "key_path": KEYS / f"t3_t4_bprime/{key_name}",
            }
        )
    return v2_specs


def build_bundle(spec: dict[str, object], nonce: str, output_root: Path) -> dict[str, object]:
    name = str(spec["name"])
    identity_name = str(spec.get("identity_name", name))
    bundle_dir = output_root / name
    if bundle_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing bundle: {bundle_dir}")
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "media").mkdir()

    public_rows: list[dict[str, str]] = []
    key_rows: list[dict[str, object]] = []
    source_dir = Path(spec["source_dir"])
    id_field = str(spec["id_field"])
    media_fields = list(spec["media_fields"])
    for position, row in enumerate(spec["rows"], start=1):
        source_id = row[id_field]
        bundle_id = "r_" + opaque_digest(nonce, identity_name, source_id, "id")[:20]
        public: dict[str, str] = {"rating_id": bundle_id}
        media_hashes: list[str] = []
        for media_index, media_field in enumerate(media_fields):
            source = resolve_repo_path(row[media_field], source_dir)
            suffix = source.suffix.lower()
            side = "" if len(media_fields) == 1 else "_" + chr(ord("A") + media_index)
            filename = f"audio_{bundle_id}{side}{suffix}"
            destination = bundle_dir / "media" / filename
            link_media(source, destination)
            public_key = "media" if len(media_fields) == 1 else f"media_{chr(ord('a') + media_index)}"
            public[public_key] = f"media/{filename}"
            media_hashes.append(sha256(destination))
        for field in spec["public_fields"]:
            public[str(field)] = row[str(field)]
        public_rows.append(public)
        key_row: dict[str, object] = {
            "bundle_rating_id": bundle_id,
            "scorer_rating_id": source_id,
            "bundle_name": name,
            "identity_bundle_name": identity_name,
            "position": position,
            "shuffle_seed": SHUFFLE_SEED,
            "nonce_sha256": hashlib.sha256(nonce.encode()).hexdigest(),
            "media_sha256": ";".join(media_hashes),
        }
        for field in spec.get("key_metadata_fields", []):
            key_row[str(field)] = row[str(field)]
        key_rows.append(key_row)

    payload = {
        "bundle_id": name,
        "title": spec["title"],
        "mode": spec["mode"],
        "wording_html": spec["wording"],
        "rows": public_rows,
    }
    (bundle_dir / "index.html").write_text(
        render_html(str(spec["title"]), payload), encoding="utf-8"
    )
    readme = "\n".join(str(line) for line in spec["readme"]) + "\n"
    if len(readme.splitlines()) != 3:
        raise AssertionError(f"{name} README must contain exactly three lines")
    (bundle_dir / "README").write_text(readme, encoding="utf-8")
    write_csv(Path(spec["key_path"]), key_rows)
    return {
        "bundle": name,
        "rows": len(public_rows),
        "media_files": len(list((bundle_dir / "media").iterdir())),
        "bundle_dir": str(bundle_dir),
        "key_path": str(spec["key_path"]),
    }


def make_zip(bundle_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        raise FileExistsError(f"refusing to overwrite bundle archive: {zip_path}")
    with zipfile.ZipFile(zip_path, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for path in sorted(bundle_dir.rglob("*")):
            if path.is_file():
                archive.write(path, Path(bundle_dir.name) / path.relative_to(bundle_dir))


def audit_bundle(bundle_dir: Path, expected_rows: int, expected_media: int) -> dict[str, object]:
    visible = sorted(path.name for path in bundle_dir.iterdir())
    if visible != ["README", "index.html", "media"]:
        raise AssertionError(f"unexpected files in {bundle_dir}: {visible}")
    if len((bundle_dir / "README").read_text(encoding="utf-8").splitlines()) != 3:
        raise AssertionError(f"README is not exactly three lines: {bundle_dir}")
    text = (bundle_dir / "index.html").read_text(encoding="utf-8")
    start = text.index('<script id="bundle-data" type="application/json">')
    start = text.index(">", start) + 1
    end = text.index("</script>", start)
    payload = json.loads(text[start:end])
    if len(payload["rows"]) != expected_rows:
        raise AssertionError(f"row-count mismatch in {bundle_dir}")
    if len(list((bundle_dir / "media").iterdir())) != expected_media:
        raise AssertionError(f"media-count mismatch in {bundle_dir}")
    mode = str(payload["mode"])
    if mode not in ALLOWED_ROW_FIELDS:
        raise AssertionError(f"unknown public bundle mode in {bundle_dir}: {mode}")
    allowed = ALLOWED_ROW_FIELDS[mode]
    for row in payload["rows"]:
        bad = FORBIDDEN_PUBLIC_FIELDS.intersection(row)
        if bad:
            raise AssertionError(f"leaked fields in {bundle_dir}: {sorted(bad)}")
        unexpected = set(row).difference(allowed)
        if unexpected:
            raise AssertionError(
                f"non-whitelisted public fields in {bundle_dir}: {sorted(unexpected)}"
            )
        if mode in {"decisive_staged", "pair_staged"} and row["request_mode"] not in {
            "vocal",
            "instrumental",
        }:
            raise AssertionError(f"invalid request_mode in {bundle_dir}")
        if mode == "pair_staged" and not row["prompt_text"].strip():
            raise AssertionError(f"blank prompt_text in {bundle_dir}")
        if mode == "label" and {"request_mode", "prompt_text"}.intersection(row):
            raise AssertionError(f"request context leaked into Label-A-only bundle: {bundle_dir}")
    if mode == "label" and "Label B" in str(payload["wording_html"]):
        raise AssertionError(f"Label B wording leaked into Label-A-only bundle: {bundle_dir}")
    lowered = text.lower()
    for token in ["expected_label", "expected_demucs_label", '"bucket"', '"arm"', '"set_name"', '"set-name"']:
        if token in lowered:
            raise AssertionError(f"leaked token {token!r} in {bundle_dir}/index.html")
    return {
        "rows": expected_rows,
        "media_files": expected_media,
        "leak_test": "PASS",
        "public_mode": mode,
        "allowed_task_fields": sorted(
            {"request_mode", "prompt_text"}.intersection(allowed)
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--request-reveal-v2",
        action="store_true",
        help="build only t1/t3/t4 request-reveal replacements in an existing root",
    )
    return parser.parse_args()


def archive_v1_zips(output_root: Path) -> list[Path]:
    archive_dir = output_root / "legacy_v1_archives"
    archive_dir.mkdir(exist_ok=True)
    readme = archive_dir / "README"
    if not readme.exists():
        readme.write_text(
            "Superseded v1 archives preserved after the request-reveal fix.\n"
            "Do not distribute these bundles for new ratings.\n"
            "Use t1_decisive_v2, t3_bprime_primary_v2, and t4_bprime_reverse_v2.\n",
            encoding="utf-8",
        )
    moved: list[Path] = []
    for name in ("t1_decisive", "t3_bprime_primary", "t4_bprime_reverse"):
        source = output_root / f"{name}.zip"
        destination = archive_dir / f"{name}.zip"
        if destination.exists():
            if source.exists():
                raise FileExistsError(
                    f"both active and archived v1 bundles exist: {source}, {destination}"
                )
            moved.append(destination)
            continue
        if not source.is_file():
            raise FileNotFoundError(f"v1 archive missing before preservation move: {source}")
        source.rename(destination)
        moved.append(destination)
    return moved


def write_active_audit(output_root: Path, nonce: str) -> dict[str, object]:
    audit = {
        name: audit_bundle(output_root / name, *counts)
        for name, counts in ACTIVE_BUNDLES.items()
    }
    zip_rows: list[dict[str, str]] = []
    for name in ACTIVE_BUNDLES:
        zip_path = output_root / f"{name}.zip"
        if not zip_path.is_file():
            raise FileNotFoundError(f"active bundle archive is missing: {zip_path}")
        zip_rows.append({"sha256": sha256(zip_path), "path": str(zip_path.resolve())})
    sums = "".join(f"{row['sha256']}  {row['path']}\n" for row in zip_rows)
    (output_root / "SHA256SUMS").write_text(sums, encoding="utf-8")
    audit_payload = {
        "shuffle_seed": SHUFFLE_SEED,
        "nonce_present": True,
        "nonce_sha256": hashlib.sha256(nonce.encode()).hexdigest(),
        "request_reveal_fix": "v2",
        "bundles": audit,
        "archives": zip_rows,
    }
    (output_root / "BUNDLE_AUDIT.json").write_text(
        json.dumps(audit_payload, indent=2) + "\n", encoding="utf-8"
    )
    return audit_payload


def main() -> None:
    args = parse_args()
    nonce = os.environ.get("ADSR_BLINDING_NONCE", "")
    if not nonce:
        raise SystemExit("ADSR_BLINDING_NONCE is required; refusing to build unblinded bundles")
    if args.request_reveal_v2:
        if not args.output.is_dir():
            raise SystemExit(f"existing v1 output root is required: {args.output}")
        specs = build_v2_rows(nonce)
        expected_names = set(V2_IDENTITY_NAMES)
        if {str(spec["name"]) for spec in specs} != expected_names:
            raise AssertionError("v2 builder selected an unexpected bundle set")
        built = [build_bundle(spec, nonce, args.output) for spec in specs]
        for row in built:
            make_zip(
                args.output / str(row["bundle"]),
                args.output / f"{row['bundle']}.zip",
            )
        moved = archive_v1_zips(args.output)
        audit_payload = write_active_audit(args.output, nonce)
        audit_payload["preserved_v1_archives"] = [str(path.resolve()) for path in moved]
        (args.output / "BUNDLE_AUDIT.json").write_text(
            json.dumps(audit_payload, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(audit_payload, indent=2))
        return
    if args.output.exists():
        raise SystemExit(f"output already exists; archive it instead of deleting: {args.output}")
    args.output.mkdir(parents=True)
    specs = build_rows(nonce)
    built = [build_bundle(spec, nonce, args.output) for spec in specs]
    expected = {
        "t1_decisive": (42, 42),
        "t2_aprime_core": (190, 190),
        "t3_bprime_primary": (80, 160),
        "t4_bprime_reverse": (24, 48),
        "t5_sa3_calibration": (60, 60),
    }
    audit = {
        row["bundle"]: audit_bundle(
            args.output / row["bundle"], *expected[row["bundle"]]
        )
        for row in built
    }
    zip_rows: list[dict[str, str]] = []
    for row in built:
        bundle_dir = args.output / row["bundle"]
        zip_path = args.output / f"{row['bundle']}.zip"
        make_zip(bundle_dir, zip_path)
        zip_rows.append(
            {
                "sha256": sha256(zip_path),
                "path": str(zip_path.resolve()),
            }
        )
    sums = "".join(f"{row['sha256']}  {row['path']}\n" for row in zip_rows)
    (args.output / "SHA256SUMS").write_text(sums, encoding="utf-8")
    audit_payload = {
        "shuffle_seed": SHUFFLE_SEED,
        "nonce_present": True,
        "nonce_sha256": hashlib.sha256(nonce.encode()).hexdigest(),
        "bundles": audit,
        "archives": zip_rows,
    }
    (args.output / "BUNDLE_AUDIT.json").write_text(
        json.dumps(audit_payload, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit_payload, indent=2))


if __name__ == "__main__":
    main()
