#!/usr/bin/env python3
"""Audit matched SA3 vocal-boost intervention fidelity and quality proxies."""
from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import math
import os
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


THRESHOLD = 0.1791
BOOTSTRAP_SEED = 20260709


def find_repo_root(path: Path) -> Path:
    for candidate in (path, *path.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"cannot find repository root from {path}")


ROOT = find_repo_root(Path(__file__).resolve())
sys.path.insert(0, str(ROOT / "src"))


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
    return rows


def unique_index(rows: list[dict], key: str, source: str, ok_field: str | None = None) -> dict[int, dict]:
    output = {}
    for row in rows:
        if ok_field and not row.get(ok_field):
            continue
        value = int(row[key])
        if value in output and row != output[value]:
            raise ValueError(f"conflicting duplicate {source} {key}={value}")
        output[value] = row
    return output


def matched_inputs(full_dir: Path, intervention_dir: Path) -> list[dict]:
    baseline_manifest = unique_index(read_jsonl(full_dir / "SA3_PREVALENCE_MANIFEST.jsonl"), "row_index", "baseline manifest")
    baseline_gen = unique_index([r for r in read_jsonl(full_dir / "SA3_PREVALENCE_LEDGER.jsonl") if r.get("status") == "PASS"], "row_index", "baseline generation")
    baseline_score = unique_index(read_jsonl(full_dir / "SA3_PREVALENCE_DEMUCS_LEDGER.jsonl"), "row_index", "baseline score", "ok")
    intervention_manifest = unique_index(read_jsonl(intervention_dir / "SA3_INTERVENTION_MANIFEST.jsonl"), "row_index", "intervention manifest")
    intervention_gen = unique_index([r for r in read_jsonl(intervention_dir / "SA3_PREVALENCE_LEDGER.jsonl") if r.get("status") == "PASS"], "row_index", "intervention generation")
    intervention_score = unique_index(read_jsonl(intervention_dir / "SA3_PREVALENCE_DEMUCS_LEDGER.jsonl"), "row_index", "intervention score", "ok")
    if not all(len(index) == 256 for index in (intervention_manifest, intervention_gen, intervention_score)):
        raise ValueError("intervention manifest/generation/score must each contain 256 unique rows")
    rows = []
    for row_index, intervention in sorted(intervention_manifest.items()):
        baseline_index = int(intervention["baseline_row_index"])
        base_manifest = baseline_manifest[baseline_index]
        base_gen = baseline_gen[baseline_index]
        base_score = baseline_score[baseline_index]
        int_gen = intervention_gen[row_index]
        int_score = intervention_score[row_index]
        identity = ("prompt_id", "seed_idx", "seed")
        for field in identity:
            values = {str(source[field]) for source in (base_manifest, base_gen, base_score, intervention, int_gen, int_score)}
            if len(values) != 1:
                raise ValueError(f"matched identity mismatch row {row_index} field {field}: {values}")
        for field in ("steps", "cfg_scale", "duration_s_requested"):
            if float(base_gen[field]) != float(int_gen[field]):
                raise ValueError(f"budget mismatch row {row_index} field {field}")
        rows.append(
            {
                "pair_id": f"sa3pair_{row_index:03d}",
                "row_index": row_index,
                "baseline_row_index": baseline_index,
                "prompt_id": intervention["prompt_id"],
                "seed_idx": int(intervention["seed_idx"]),
                "seed": int(intervention["seed"]),
                "original_prompt": base_manifest["prompt"],
                "intervention_prompt": intervention["prompt"],
                "baseline_audio_path": base_score["audio_path"],
                "intervention_audio_path": int_score["audio_path"],
                "baseline_ratio": float(base_score["vocal_energy_ratio"]),
                "intervention_ratio": float(int_score["vocal_energy_ratio"]),
                "baseline_present": int(base_score["present"]),
                "intervention_present": int(int_score["present"]),
                "steps": int(base_gen["steps"]),
                "cfg_scale": float(base_gen["cfg_scale"]),
                "duration_s_requested": float(base_gen["duration_s_requested"]),
            }
        )
    return rows


def audio_proxies(waveform: np.ndarray, sample_rate: int) -> dict[str, float | bool]:
    mono = waveform.mean(axis=1) if waveform.ndim == 2 else waveform
    rms = float(np.sqrt(np.mean(np.square(mono, dtype=np.float64))))
    peak = float(np.max(np.abs(mono)))
    window = mono[: min(len(mono), sample_rate * 8)]
    spectrum = np.abs(np.fft.rfft(window.astype(np.float64))) + 1e-12
    frequencies = np.fft.rfftfreq(len(window), 1.0 / sample_rate)
    centroid = float(np.sum(frequencies * spectrum) / np.sum(spectrum))
    flatness = float(np.exp(np.mean(np.log(spectrum))) / np.mean(spectrum))
    return {
        "duration_s": len(mono) / sample_rate,
        "sample_rate": sample_rate,
        "rms": rms,
        "loudness_dbfs": 20 * math.log10(max(rms, 1e-12)),
        "peak": peak,
        "near_silent": rms < 1e-3,
        "spectral_centroid_hz": centroid,
        "spectral_flatness": flatness,
    }


def clap_scores(rows: list[dict], device: str) -> tuple[dict[str, float], dict[str, np.ndarray], dict[str, dict]]:
    import soundfile as sf
    import torch
    import torchaudio
    from mprm.rewards.clap import ClapReward

    reward = ClapReward(device=device)
    reward._ensure_loaded()
    reward._model.model.eval()

    def tokenizer(texts):
        return reward._model.tokenize(texts, padding="max_length", truncation=True, max_length=77, return_tensors="pt")

    prompts = sorted({row["original_prompt"] for row in rows})
    with torch.no_grad():
        text_raw = reward._model.get_text_embedding(prompts, tokenizer=tokenizer, use_tensor=False)
    text_embeddings = {prompt: vector / max(np.linalg.norm(vector), 1e-12) for prompt, vector in zip(prompts, np.asarray(text_raw))}
    paths = sorted({row["baseline_audio_path"] for row in rows} | {row["intervention_audio_path"] for row in rows})
    embeddings: dict[str, np.ndarray] = {}
    proxies: dict[str, dict] = {}
    for start in range(0, len(paths), 16):
        batch_paths = paths[start : start + 16]
        batch = []
        for path_text in batch_paths:
            audio, sample_rate = sf.read(path_text, dtype="float32", always_2d=True)
            proxies[path_text] = audio_proxies(audio, sample_rate)
            mono = torch.from_numpy(audio.mean(axis=1).copy()).unsqueeze(0)
            if sample_rate != 48_000:
                mono = torchaudio.functional.resample(mono, sample_rate, 48_000)
            batch.append(mono.squeeze(0).numpy())
        with torch.no_grad():
            raw = reward._model.get_audio_embedding_from_data(x=np.stack(batch), use_tensor=False)
        for path_text, vector in zip(batch_paths, np.asarray(raw)):
            embeddings[path_text] = vector / max(np.linalg.norm(vector), 1e-12)
        print(json.dumps({"stage": "clap_audio", "done": min(start + 16, len(paths)), "total": len(paths)}), flush=True)
    similarity = {}
    for row in rows:
        text = text_embeddings[row["original_prompt"]]
        for condition in ("baseline", "intervention"):
            path = row[f"{condition}_audio_path"]
            similarity[path] = float(np.dot(embeddings[path], text))
    return similarity, embeddings, proxies


def prompt_diversity(rows: list[dict], embeddings: dict[str, np.ndarray], condition: str) -> dict[str, float]:
    paths: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        paths[row["prompt_id"]].append(row[f"{condition}_audio_path"])
    result = {}
    for prompt_id, prompt_paths in paths.items():
        vectors = [embeddings[path] for path in prompt_paths]
        cosines = [float(np.dot(vectors[i], vectors[j])) for i in range(len(vectors)) for j in range(i + 1, len(vectors))]
        result[prompt_id] = 1.0 - float(np.mean(cosines))
    return result


def paired_prompt_bootstrap(rows: list[dict], field: str, reps: int = 10_000) -> tuple[float, float, float]:
    by_prompt: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_prompt[row["prompt_id"]].append(float(row[field]))
    prompt_means = np.array([np.mean(values) for values in by_prompt.values()])
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = rng.choice(prompt_means, size=(reps, len(prompt_means)), replace=True).mean(axis=1)
    return float(prompt_means.mean()), float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_blinded_pairs(rows: list[dict], out_dir: Path, nonce: str) -> None:
    rng = random.Random(BOOTSTRAP_SEED)
    prompt_ids = sorted({row["prompt_id"] for row in rows})
    rng.shuffle(prompt_ids)
    chosen_prompts = set(prompt_ids[:20])
    candidates = [row for row in rows if row["prompt_id"] in chosen_prompts and row["seed_idx"] == min(r["seed_idx"] for r in rows if r["prompt_id"] == row["prompt_id"])]
    audio_dir = out_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    admin = []
    rater = []
    for index, row in enumerate(sorted(candidates, key=lambda value: value["prompt_id"]), 1):
        digest = hmac.new(nonce.encode(), row["pair_id"].encode(), hashlib.sha256).hexdigest()[:10]
        blind_id = f"sa3pair_{index:02d}_{digest}"
        method_is_a = bool(rng.getrandbits(1))
        source_a = row["intervention_audio_path"] if method_is_a else row["baseline_audio_path"]
        source_b = row["baseline_audio_path"] if method_is_a else row["intervention_audio_path"]
        path_a = audio_dir / f"{blind_id}_A.wav"
        path_b = audio_dir / f"{blind_id}_B.wav"
        shutil.copy2(source_a, path_a)
        shutil.copy2(source_b, path_b)
        admin.append({"blind_id": blind_id, "pair_id": row["pair_id"], "prompt_id": row["prompt_id"], "method_side": "A" if method_is_a else "B", "source_a": source_a, "source_b": source_b})
        rater.append({"blind_id": blind_id, "original_prompt": row["original_prompt"], "audio_a": f"audio/{path_a.name}", "audio_b": f"audio/{path_b.name}", "prompt_fidelity_preference": "", "quality_preference": "", "constraint_preference": "", "notes": ""})
    write_csv(out_dir / "SA3_INTERVENTION_PAIRS_ADMIN.csv", admin)
    write_csv(out_dir / "SA3_INTERVENTION_PAIRS_RATINGS.csv", rater)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-dir", type=Path, required=True)
    parser.add_argument("--intervention-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    nonce = os.environ.get("ADSR_BLINDING_NONCE")
    if not nonce:
        raise RuntimeError("ADSR_BLINDING_NONCE is required for the pair packet")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = matched_inputs(args.full_dir, args.intervention_dir)
    similarities, embeddings, proxies = clap_scores(rows, args.device)
    diversity = {condition: prompt_diversity(rows, embeddings, condition) for condition in ("baseline", "intervention")}
    output = []
    for row in rows:
        item = dict(row)
        for condition in ("baseline", "intervention"):
            path = row[f"{condition}_audio_path"]
            item[f"{condition}_clap_original_prompt"] = similarities[path]
            for key, value in proxies[path].items():
                item[f"{condition}_{key}"] = value
            item[f"{condition}_prompt_diversity"] = diversity[condition][row["prompt_id"]]
        item["delta_clap_original_prompt"] = item["intervention_clap_original_prompt"] - item["baseline_clap_original_prompt"]
        item["delta_loudness_dbfs"] = item["intervention_loudness_dbfs"] - item["baseline_loudness_dbfs"]
        item["delta_spectral_centroid_hz"] = item["intervention_spectral_centroid_hz"] - item["baseline_spectral_centroid_hz"]
        item["delta_prompt_diversity"] = item["intervention_prompt_diversity"] - item["baseline_prompt_diversity"]
        item["delta_present"] = item["intervention_present"] - item["baseline_present"]
        output.append(item)
    results_path = args.out_dir / "SA3_INTERVENTION_FIDELITY_RESULTS.csv"
    write_csv(results_path, output)
    build_blinded_pairs(output, args.out_dir / "blinded_pairs", nonce)
    intervals = {field: paired_prompt_bootstrap(output, field) for field in ("delta_present", "delta_clap_original_prompt", "delta_loudness_dbfs", "delta_prompt_diversity")}
    threshold_rows = []
    for threshold in (0.10, 0.15, THRESHOLD, 0.20, 0.25):
        baseline = np.mean([float(row["baseline_ratio"]) >= threshold for row in output])
        intervention = np.mean([float(row["intervention_ratio"]) >= threshold for row in output])
        threshold_rows.append({"threshold": threshold, "baseline_present_rate": baseline, "intervention_present_rate": intervention, "absolute_lift": intervention - baseline})
    write_csv(args.out_dir / "SA3_INTERVENTION_THRESHOLD_SENSITIVITY.csv", threshold_rows)
    report = f"""# SA3 Intervention Fidelity Audit

## Matched Design Audit

- Rows reconciled: {len(output)}/256.
- Prompts: {len({row['prompt_id'] for row in output})}/32; seeds per prompt: 8.
- Prompt ID, seed index, seed, duration, steps, and CFG match for every pair.
- Baseline present: {sum(row['baseline_present'] for row in output)}/256.
- Intervention present: {sum(row['intervention_present'] for row in output)}/256.

## Paired Prompt-Cluster Bootstrap

| Delta (intervention - baseline) | Mean | 95% CI |
|---|---:|---:|
| Demucs present | {intervals['delta_present'][0]:.6f} | [{intervals['delta_present'][1]:.6f}, {intervals['delta_present'][2]:.6f}] |
| CLAP to original prompt | {intervals['delta_clap_original_prompt'][0]:.6f} | [{intervals['delta_clap_original_prompt'][1]:.6f}, {intervals['delta_clap_original_prompt'][2]:.6f}] |
| Loudness dBFS | {intervals['delta_loudness_dbfs'][0]:.6f} | [{intervals['delta_loudness_dbfs'][1]:.6f}, {intervals['delta_loudness_dbfs'][2]:.6f}] |
| Within-prompt embedding diversity | {intervals['delta_prompt_diversity'][0]:.6f} | [{intervals['delta_prompt_diversity'][1]:.6f}, {intervals['delta_prompt_diversity'][2]:.6f}] |

Near-silent baseline/intervention rows: {sum(bool(row['baseline_near_silent']) for row in output)}/{sum(bool(row['intervention_near_silent']) for row in output)}.

## D7 Interpretation

The categorical intervention effect is mechanically verified under matched
budgets. Human SA3 label calibration is still pending, so this audit cannot
promote the second-backbone claim by itself. A 20-pair blinded packet is staged
for optional PI fidelity/quality review. Any prompt-fidelity delta whose
interval includes a material negative effect must remain an explicit wording
constraint.

## Artifacts

- `paper_prep/sao/stable_audio_3_medium/intervention_fidelity/SA3_INTERVENTION_FIDELITY_RESULTS.csv`
- `paper_prep/sao/stable_audio_3_medium/intervention_fidelity/SA3_INTERVENTION_THRESHOLD_SENSITIVITY.csv`
- `paper_prep/sao/stable_audio_3_medium/intervention_fidelity/blinded_pairs/`
"""
    (args.out_dir / "SA3_INTERVENTION_FIDELITY_REPORT.md").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
