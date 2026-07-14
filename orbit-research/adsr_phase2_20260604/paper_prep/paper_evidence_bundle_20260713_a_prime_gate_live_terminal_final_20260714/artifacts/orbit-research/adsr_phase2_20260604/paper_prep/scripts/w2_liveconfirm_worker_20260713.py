#!/usr/bin/env python3
"""Sharded, resumable worker for the frozen W2 four-policy live confirmation."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import glob
import hashlib
import json
import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
PAPER = ROOT / "paper_prep"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(PAPER / "w2_contingency_20260711"))
PREP = PAPER / "w2_execution_20260712/evpd_liveconfirm_torch251_recovery"
MANIFEST = PREP / "LIVE_CONFIRM_MANIFEST.csv"
PROMPTS = PREP / "LIVE_CONFIRM_PROMPTS.jsonl"
EVPD_MODEL = PREP / "corrected_evpd_sigma08.joblib"
PROMOTION = PAPER / "autochain_20260712/T6_PROMOTION_RESULT.json"
AMENDMENT = PAPER / "W2_AMENDMENT_20260712.md"
OUT = PAPER / "w2_execution_20260712/live_confirmation_20260713"
BASE_EXTRAS = {
    "cfg_type": "apg",
    "guidance_interval": 0.5,
    "use_erg_tag": False,
    "use_erg_lyric": False,
    "use_erg_diffusion": False,
}
POSITIVE_INSTRUMENTAL_TEXT = (
    "instrumental arrangement led by synthesizer, drums, bass, and melodic instruments"
)
SIGMA_DECIDE = 0.8


class EarlyAbort(Exception):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_runtime_authorization(amendment_text: str, promotion: dict, evpd: dict) -> None:
    if "W2_AMENDMENT_STATUS = SIGNED_BY_BOTH_PIS" not in amendment_text:
        raise ValueError("live worker requires the signed W2 amendment")
    promotion_status = promotion.get("CORRECTED_INSTRUMENT_STATUS")
    if promotion_status not in {"PROMOTED", "PASS_DUAL_PI_ADOPTED"}:
        raise ValueError("live worker requires mechanically promoted corrected instrument")
    allowed_evpd = {
        "DRAFT_MECHANICAL_PROMOTION_AWAITING_DUAL_PI_ADOPTION",
        "DUAL_PI_ADOPTED",
    }
    if evpd.get("training_status") not in allowed_evpd:
        raise ValueError("corrected EVPD model has an unsupported training status")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def output_audio_path(unit_id: str, slot: int, seed: int) -> Path:
    return OUT / "audio" / unit_id / f"slot{slot}_seed{seed}.flac"


def mel_summary(audio: np.ndarray, sample_rate: int = 48000) -> np.ndarray:
    import librosa

    mono = audio.mean(0) if audio.ndim == 2 else audio
    mel = librosa.feature.melspectrogram(
        y=mono.astype("float32"), sr=sample_rate, n_mels=64, hop_length=512
    )
    log_mel = librosa.power_to_db(mel + 1e-9)
    return np.concatenate(
        [
            log_mel.mean(1),
            log_mel.std(1),
            log_mel.max(1),
            np.percentile(log_mel, 25, 1),
            np.percentile(log_mel, 75, 1),
        ]
    )


def apply_direction(prompt, requested_vocal: int):
    if requested_vocal:
        if not (prompt.structure_hint or "").strip():
            prompt = dataclasses.replace(
                prompt, structure_hint="[verse]\n[chorus]\n[verse]\n[chorus]"
            )
        return prompt, {"guidance_scale_text": 5.0, "guidance_scale_lyric": 7.5}, 5.0
    prompt = dataclasses.replace(
        prompt,
        text=prompt.text.rstrip(". ") + ", " + POSITIVE_INSTRUMENTAL_TEXT,
        lyrics=None,
    )
    return prompt, {}, 7.5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-index", type=int, required=True)
    parser.add_argument("--num-workers", type=int, required=True)
    args = parser.parse_args()
    if not 0 <= args.worker_index < args.num_workers:
        raise ValueError("worker index outside shard range")
    visible = [value for value in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if value]
    if len(visible) != 1:
        raise RuntimeError("each live-confirm worker requires exactly one visible GPU")

    import joblib
    import soundfile as sf
    import torch
    from acestep.schedulers.scheduling_flow_match_euler_discrete import FlowMatchEulerDiscreteScheduler
    from mprm.common.config import load_config
    from mprm.common.seeding import seed_everything
    from mprm.inference.ace_step import AceStepModel
    from scripts.collect_early_tweedie_validation import _prompt_from_row, _score_common_metrics
    from scripts.launch_baseline import _assert_reward_axes_match_policy, _build_reward_models, load_gate_eval_policy
    from w2_instruments import LiveDemucsPannsEnsembleInstrument

    promotion = json.loads(PROMOTION.read_text(encoding="utf-8"))
    candidate = promotion.get("selected_candidate") or promotion["heldout"]["selected_candidate"]
    if candidate["family"] != "or":
        raise ValueError("live worker is frozen for the promoted OR instrument")
    evpd = joblib.load(EVPD_MODEL)
    validate_runtime_authorization(AMENDMENT.read_text(encoding="utf-8"), promotion, evpd)
    if evpd.get("promotion_sha256") != sha256_file(PROMOTION):
        raise ValueError("corrected EVPD promotion hash does not match the launch record")

    prompts = {row["prompt_id"]: row for row in read_jsonl(PROMPTS)}
    tasks = read_csv(MANIFEST)
    if len(tasks) != 512:
        raise ValueError("live manifest must contain 512 units")
    mine = tasks[args.worker_index :: args.num_workers]
    ledger = OUT / "live_ledgers" / f"live_w{args.worker_index}.jsonl"
    prior: dict[str, list[dict]] = defaultdict(list)
    for path in glob.glob(str(OUT / "live_ledgers/live_w*.jsonl")):
        for row in read_jsonl(Path(path)):
            prior[row["unit_id"]].append(row)

    gate_policy, _ = load_gate_eval_policy(ROOT / "configs/eval/gate_v2.yaml.draft")
    config = load_config(ROOT / "configs/baselines/r2_bon.yaml")
    reward_models = _build_reward_models(config.reward)
    _assert_reward_axes_match_policy(reward_models, gate_policy)
    model = AceStepModel()
    instrument = LiveDemucsPannsEnsembleInstrument(
        "cuda", float(candidate["demucs_threshold"]), float(candidate["panns_threshold"]), "or"
    )
    original_step = FlowMatchEulerDiscreteScheduler.step

    def generate(prompt, seed: int, probe: bool, extras: dict, cfg_scale: float):
        state = {"probed": False, "aborted": False, "evpd_probability": None, "probe_s": 0.0}

        def step(scheduler, model_output, timestep, sample, **kwargs):
            if scheduler.step_index is None:
                scheduler._init_step_index(timestep)
            sigma = float(scheduler.sigmas[scheduler.step_index])
            if probe and not state["probed"] and sigma <= SIGMA_DECIDE:
                state["probed"] = True
                started = time.time()
                z0 = sample.to(torch.float32) - sigma * model_output.to(torch.float32)
                early = model.decode(z0).detach().cpu().numpy()
                feature = mel_summary(early)
                probability = float(
                    evpd["model"].predict_proba(evpd["scaler"].transform(feature.reshape(1, -1)))[0, 1]
                )
                state["evpd_probability"] = probability
                state["probe_s"] = time.time() - started
                if probability >= float(evpd["threshold"]):
                    state["aborted"] = True
                    raise EarlyAbort()
            return original_step(scheduler, model_output, timestep, sample, **kwargs)

        FlowMatchEulerDiscreteScheduler.step = step
        seed_everything(seed)
        started = time.time()
        try:
            result = model.sample(
                prompt,
                seed=seed,
                cfg_scale=cfg_scale,
                steps=30,
                return_trajectory=False,
                extras={**BASE_EXTRAS, **extras},
            )
        except EarlyAbort:
            result = None
        finally:
            FlowMatchEulerDiscreteScheduler.step = original_step
        state["wall_s"] = time.time() - started
        state["result"] = result
        return state

    def score_audio(audio_path: Path, waveform: torch.Tensor, sample_rate: int, prompt):
        instrument_result = instrument.score(audio_path)
        common = _score_common_metrics(
            reward_models=reward_models,
            waveform=waveform,
            sample_rate=sample_rate,
            prompt=prompt,
            gate_policy=gate_policy,
        )
        present = int(instrument_result["present"])
        return {
            "audio_path": str(audio_path),
            "audio_sha256": sha256_file(audio_path),
            "sample_rate": sample_rate,
            "duration_seconds": round(waveform.shape[-1] / sample_rate, 6),
            "near_silent": bool(float(waveform.square().mean().sqrt()) < 1e-4),
            "present": present,
            "demucs_score": instrument_result["vocal_energy_ratio"],
            "panns_score": instrument_result["panns_score"],
            "final_common_robust_lcb": common.get("common_robust_lcb"),
            "final_scores": common,
        }

    OUT.mkdir(parents=True, exist_ok=True)
    for unit in mine:
        unit_id = unit["unit_id"]
        old = prior.get(unit_id, [])
        if any(row.get("record_type") == "unit_selection" for row in old):
            continue
        prompt = _prompt_from_row(prompts[unit["prompt_id"]])
        requested = int(unit["requested_vocal"])
        policy = unit["policy"]
        slot_records = {
            int(row["slot"]): row
            for row in old
            if row.get("record_type") == "slot" and row.get("status") in {"ABORTED", "COMPLETE"}
        }
        for slot in range(2):
            if slot in slot_records:
                continue
            use_direction = policy == "always_direction_condition" or (
                policy == "corrected_probe_direction_action"
                and slot == 1
                and slot_records.get(0, {}).get("status") == "ABORTED"
            )
            probe = policy == "corrected_probe_abort_reseed" or (
                policy == "corrected_probe_direction_action" and not use_direction
            )
            active_prompt, extras, cfg = (
                apply_direction(prompt, requested) if use_direction else (prompt, {}, 5.0)
            )
            seed = int(unit["seed"]) + slot * 10
            audio_path = output_audio_path(unit_id, slot, seed)
            if audio_path.exists():
                samples, sample_rate = sf.read(
                    str(audio_path), always_2d=True, dtype="float32"
                )
                if len(samples) / sample_rate <= 1.0:
                    raise RuntimeError(f"refusing invalid orphan audio: {audio_path}")
                waveform = torch.from_numpy(samples.T.copy())
                if float(waveform.square().mean().sqrt()) < 1e-4:
                    raise RuntimeError(f"refusing near-silent orphan audio: {audio_path}")
                scored = score_audio(audio_path, waveform, sample_rate, prompt)
                record = {
                    **unit,
                    "record_type": "slot",
                    "slot": slot,
                    "slot_seed": seed,
                    "slot_seed_rule": "unit_seed_plus_10_times_slot",
                    "worker_index": args.worker_index,
                    "host": os.uname().nodename,
                    "probe": probe,
                    "direction_conditioned": use_direction,
                    "evpd_probability": None,
                    "probe_s": None,
                    "wall_s": None,
                    "nominal_steps": 30,
                    "actual_steps": 30,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "status": "COMPLETE",
                    "recovered_orphan": True,
                    "recovery_reason": "audio_written_before_reward_scoring_failure",
                    "probe_outcome": (
                        "non_abort_inferred_from_completed_audio" if probe else "not_applicable"
                    ),
                    **scored,
                    "label_b_satisfied": int(scored["present"] == requested),
                }
                append_jsonl(ledger, record)
                slot_records[slot] = record
                continue
            state = generate(active_prompt, seed, probe, extras, cfg)
            record = {
                **unit,
                "record_type": "slot",
                "slot": slot,
                "slot_seed": seed,
                "slot_seed_rule": "unit_seed_plus_10_times_slot",
                "worker_index": args.worker_index,
                "host": os.uname().nodename,
                "probe": probe,
                "direction_conditioned": use_direction,
                "evpd_probability": state["evpd_probability"],
                "probe_s": round(state["probe_s"], 6),
                "wall_s": round(state["wall_s"], 6),
                "nominal_steps": 30,
                "actual_steps": 12 if state["aborted"] else 30,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            if state["aborted"]:
                record["status"] = "ABORTED"
            else:
                result = state["result"]
                audio_path.parent.mkdir(parents=True, exist_ok=True)
                samples = result.waveform.detach().cpu().numpy().T
                sf.write(str(audio_path), samples, result.sample_rate, format="FLAC")
                record.update(
                    {
                        "status": "COMPLETE",
                        **score_audio(audio_path, result.waveform, result.sample_rate, prompt),
                    }
                )
                record["label_b_satisfied"] = int(record["present"] == requested)
            append_jsonl(ledger, record)
            slot_records[slot] = record
        completed = [row for row in slot_records.values() if row["status"] == "COMPLETE"]
        selected = max(
            completed,
            key=lambda row: (
                int(row["label_b_satisfied"]),
                float(row.get("final_common_robust_lcb") or -math.inf),
                -int(row["slot"]),
            ),
        ) if completed else None
        append_jsonl(
            ledger,
            {
                **unit,
                "record_type": "unit_selection",
                "worker_index": args.worker_index,
                "status": "COMPLETE" if selected else "NO_COMPLETED_SLOT",
                "selected_slot": selected["slot"] if selected else "",
                "selected_audio_path": selected["audio_path"] if selected else "",
                "selected_label_b_satisfied": selected["label_b_satisfied"] if selected else "",
                "selected_present": selected["present"] if selected else "",
                "nominal_steps": 60,
                "actual_steps": sum(int(row["actual_steps"]) for row in slot_records.values()),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
