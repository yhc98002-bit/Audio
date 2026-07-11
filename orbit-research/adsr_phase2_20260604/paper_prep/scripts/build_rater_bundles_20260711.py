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
SHUFFLE_SEED = 20260711

LABEL_A_WORDING = (
    "Do you hear any sound a reasonable listener would perceive as a human voice "
    "or vocalization? Includes singing, rap, speech, chant, humming, wordless "
    "vocals, choir, ooh/ah, vocal chops. Answer Yes / No / Unsure; then select "
    "perceived vocal type and whether it is isolated, intermittent, or sustained."
)
LABEL_B_WORDING = (
    "Vocal request → Satisfied only when clearly audible vocals function as an "
    "intentional musical element; a fleeting isolated chop, ambiguous voice-like "
    "texture, or background artifact is not sufficient. Instrumental request → "
    "Violated when perceived vocal content is salient, recurrent, or functions as "
    "a musical element, or when any phrase is clearly sung, spoken, or rapped; a "
    "single isolated non-linguistic one-shot shorter than ~2 s is normally not a "
    "violation unless unusually prominent."
)
CHOIR_RULE = (
    "Choir-pad rule: perceived as human choir → A=Yes and instrumental request "
    "normally violated; perceived as synth timbre → A=No; ambiguous → Unsure."
)
QUALITY_WORDING = (
    "Judge musical/audio quality while setting aside whether the clip correctly "
    "contains or omits vocals. Consider production quality, artifacts, musical "
    "coherence, naturalness, and listening quality."
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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
.wording{font-size:14px;margin:14px 0}.question{border-top:1px solid var(--line);padding-top:14px;margin-top:14px}.question h2{font-size:15px;margin:0 0 8px}
.choices{display:flex;flex-wrap:wrap;gap:8px}.choices label{display:flex;align-items:center;gap:5px;border:1px solid var(--line);border-radius:4px;padding:7px 10px;background:#fff}
audio{width:100%;margin:8px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}.pair strong{display:block}.field{margin-top:14px}.field label{display:block;font-weight:600;margin-bottom:5px}
select,input,textarea{font:inherit;border:1px solid #9da7b1;border-radius:4px;padding:7px;background:#fff}textarea{width:100%;min-height:74px}.confidence{width:90px}
.nav{display:flex;justify-content:space-between;gap:12px;margin-top:18px}.nav button,.export button{border:0;border-radius:4px;padding:9px 13px;background:#263746;color:#fff;font:inherit;cursor:pointer}.nav button:disabled{opacity:.35}
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
  <div id="prompt" class="prompt hidden"></div>
  <div id="audio"></div><div id="wording" class="wording"></div><div id="questions"></div>
  <div class="field"><label for="confidence">Confidence (1–5)</label><select id="confidence" class="confidence"><option value=""></option><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option></select></div>
  <div class="field"><label for="notes">Comment / notes</label><textarea id="notes"></textarea></div>
  <div class="nav"><button id="previous">← Previous</button><span class="hint">1/2/3: primary answer · Space: play · ←/→: navigate</span><button id="next">Next →</button></div>
</section></main></div>
<script>
"use strict";
const bundle=JSON.parse(document.getElementById("bundle-data").textContent);
const storageKey="adsr-rater-v1:"+bundle.bundle_id;
let state=JSON.parse(localStorage.getItem(storageKey)||'{"rating_source":"","responses":{}}');
let cursor=0;
const $=id=>document.getElementById(id);
function validSource(v){return /^(pi:[A-Za-z][A-Za-z0-9 ._-]{0,63}|human:CXY)$/.test(v)}
function persist(){localStorage.setItem(storageKey,JSON.stringify(state))}
function begin(){if(!validSource(state.rating_source))return;$("sourceGate").classList.add("hidden");$("app").classList.remove("hidden");render()}
$("sourceSave").onclick=()=>{const v=$("sourceInput").value.trim();if(!validSource(v)){ $("sourceError").textContent="Use pi:<name> or human:CXY exactly.";return}state.rating_source=v;persist();begin()};
function values(name){return bundle.mode==="pair"?["A","B","tie"]:["yes","no","unsure"]}
function radio(name,label,choices){return '<div class="question"><h2>'+label+'</h2><div class="choices">'+choices.map((v,i)=>'<label><input type="radio" name="'+name+'" value="'+v+'">'+v+'</label>').join("")+'</div></div>'}
function selectField(name,label,choices){return '<div class="field"><label for="'+name+'">'+label+'</label><select id="'+name+'"><option value=""></option>'+choices.map(v=>'<option>'+v+'</option>').join("")+'</select></div>'}
function questionMarkup(){
 if(bundle.mode==="decisive")return radio("label_a_voice_presence","Label A: voice presence",["yes","no","unsure"])+selectField("perceived_vocal_type","Perceived vocal type",["singing","rap","speech","chant","humming","wordless vocals","choir","ooh/ah","vocal chops","voice-like/ambiguous","none"])+selectField("vocal_extent","Vocal extent",["isolated","intermittent","sustained","none","unsure"])+radio("label_b_constraint","Label B: constraint",["satisfied","violated","unsure"]);
 if(bundle.mode==="pair")return radio("quality_preference","Quality preference (PRIMARY)",["A","B","tie"])+radio("overall_preference","Overall preference",["A","B","tie"])+radio("constraint_preference","Constraint preference",["A","B","tie"]);
 return radio("label_a_voice_presence","Voice presence",["yes","no","unsure"]);
}
function fieldNames(){if(bundle.mode==="decisive")return["label_a_voice_presence","perceived_vocal_type","vocal_extent","label_b_constraint","confidence_1_to_5","notes"];if(bundle.mode==="pair")return["quality_preference","overall_preference","constraint_preference","confidence_1_to_5","notes"];return["label_a_voice_presence","confidence_1_to_5","notes"]}
function saveCurrent(){const row=bundle.rows[cursor],r=state.responses[row.rating_id]||{};for(const f of fieldNames()){if(f==="confidence_1_to_5")r[f]=$("confidence").value;else if(f==="notes")r[f]=$("notes").value;else{const el=document.querySelector('[name="'+f+'"]:checked')||$(f);r[f]=el?el.value:""}}state.responses[row.rating_id]=r;persist();updateProgress()}
function render(){const row=bundle.rows[cursor],r=state.responses[row.rating_id]||{};$("title").textContent=bundle.title;$("position").textContent=(cursor+1)+" / "+bundle.rows.length;$("sourceDisplay").textContent=state.rating_source;$("prompt").classList.toggle("hidden",!row.request_text);$("prompt").textContent=row.request_text||"";
 $("audio").innerHTML=bundle.mode==="pair"?'<div class="pair"><div><strong>A</strong><audio controls preload="metadata" src="'+row.media_a+'"></audio></div><div><strong>B</strong><audio controls preload="metadata" src="'+row.media_b+'"></audio></div></div>':'<audio controls preload="metadata" src="'+row.media+'"></audio>';
 $("wording").innerHTML=bundle.wording_html;$("questions").innerHTML=questionMarkup();for(const f of fieldNames()){if(f==="confidence_1_to_5")$("confidence").value=r[f]||"";else if(f==="notes")$("notes").value=r[f]||"";else{const el=document.querySelector('[name="'+f+'"][value="'+(r[f]||"")+'"]')||$(f);if(el){if(el.type==="radio")el.checked=true;else el.value=r[f]||""}}}
 document.querySelectorAll("input,select,textarea").forEach(el=>el.addEventListener("change",saveCurrent));$("notes").addEventListener("input",saveCurrent);$("previous").disabled=cursor===0;$("next").disabled=cursor===bundle.rows.length-1;updateProgress()}
function updateProgress(){const done=bundle.rows.filter(r=>{const x=state.responses[r.rating_id]||{};return fieldNames().filter(f=>f!=="notes").every(f=>String(x[f]||"").length)}).length;$("progress").textContent=done+" / "+bundle.rows.length+" complete"}
$("previous").onclick=()=>{saveCurrent();if(cursor>0){cursor--;render()}};$("next").onclick=()=>{saveCurrent();if(cursor<bundle.rows.length-1){cursor++;render()}};
function csvCell(v){return '"'+String(v??"").replaceAll('"','""')+'"'}
function exportRows(){saveCurrent();return bundle.rows.map(row=>{const r=state.responses[row.rating_id]||{};const out={rating_id:row.rating_id};for(const f of fieldNames())out[f]=r[f]||"";out.rating_source=state.rating_source;return out})}
function download(name,text,type){const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;document.body.appendChild(a);a.click();URL.revokeObjectURL(a.href);a.remove()}
function initials(){return state.rating_source.split(":",2)[1].replace(/[^A-Za-z0-9]+/g,"_")}
$("csvExport").onclick=()=>{const rows=exportRows(),heads=Object.keys(rows[0]);download("responses_"+initials()+".csv",heads.join(",")+"\n"+rows.map(r=>heads.map(h=>csvCell(r[h])).join(",")).join("\n")+"\n","text/csv")};
$("jsonExport").onclick=()=>download("responses_"+initials()+".json",JSON.stringify({bundle_id:bundle.bundle_id,rating_source:state.rating_source,exported_at:new Date().toISOString(),responses:exportRows()},null,2)+"\n","application/json");
document.addEventListener("keydown",e=>{if(e.target.matches("input,textarea,select"))return;if(e.key==="ArrowLeft")$("previous").click();if(e.key==="ArrowRight")$("next").click();if(e.key===" "){e.preventDefault();const a=document.querySelectorAll("audio")[e.shiftKey?1:0];if(a)a.paused?a.play():a.pause()}if(["1","2","3"].includes(e.key)){const q=bundle.mode==="pair"?"quality_preference":"label_a_voice_presence";const opts=document.querySelectorAll('[name="'+q+'"]');if(opts[Number(e.key)-1]){opts[Number(e.key)-1].checked=true;saveCurrent()}}});
if(state.rating_source){if(validSource(state.rating_source))begin();else{state={rating_source:"",responses:{}};persist()}}
</script>
</body></html>
'''


def render_html(title: str, payload: dict[str, object]) -> str:
    return HTML_TEMPLATE.replace("__TITLE__", html.escape(title)).replace(
        "__DATA_JSON__", safe_json(payload)
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


def build_bundle(spec: dict[str, object], nonce: str, output_root: Path) -> dict[str, object]:
    name = str(spec["name"])
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
        bundle_id = "r_" + opaque_digest(nonce, name, source_id, "id")[:20]
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
        key_rows.append(
            {
                "bundle_rating_id": bundle_id,
                "scorer_rating_id": source_id,
                "bundle_name": name,
                "position": position,
                "shuffle_seed": SHUFFLE_SEED,
                "nonce_sha256": hashlib.sha256(nonce.encode()).hexdigest(),
                "media_sha256": ";".join(media_hashes),
            }
        )

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
    forbidden = {"expected_label", "expected_demucs_label", "bucket", "set_name", "set-name", "arm"}
    for row in payload["rows"]:
        bad = forbidden.intersection(row)
        if bad:
            raise AssertionError(f"leaked fields in {bundle_dir}: {sorted(bad)}")
    lowered = text.lower()
    for token in ["expected_label", "expected_demucs_label", '"bucket"', '"arm"', '"set_name"', '"set-name"']:
        if token in lowered:
            raise AssertionError(f"leaked token {token!r} in {bundle_dir}/index.html")
    return {"rows": expected_rows, "media_files": expected_media, "leak_test": "PASS"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    nonce = os.environ.get("ADSR_BLINDING_NONCE", "")
    if not nonce:
        raise SystemExit("ADSR_BLINDING_NONCE is required; refusing to build unblinded bundles")
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
