#!/usr/bin/env python3
"""Frozen promoted-instrument and common-quality scoring for BOLT outputs."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
HERE = Path(__file__).resolve().parent
for path in (ROOT, ROOT / "src", ROOT / "scripts", ROOT / "paper_prep/w2_contingency_20260711", HERE):
    sys.path.insert(0, str(path))

from bolt_ace_step import waveform_nrmse, waveform_validity  # noqa: E402
from bolt_core import canonical_json_hash, sha256_file  # noqa: E402


PROMOTION = ROOT / "paper_prep/autochain_20260712/T6_PROMOTION_RESULT.json"
FLOORS = HERE / "BOLT_QUALITY_FLOORS.json"
CALIBRATION_SCRIPT = ROOT / "paper_prep/scripts/autochain_corrected_recompute_20260712.py"
EVPD_MODEL = ROOT / (
    "paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/"
    "corrected_evpd_sigma08.joblib"
)
RUNTIME = HERE / "BOLT_RUNTIME_FREEZE.json"
SCORING_PROTOCOL_VERSION = "bolt_scoring_v2_hash_scoped_deterministic_clap"
CLAP_AUDIO_AUDIO_RNG_SEED = 2_060_000_000


def enable_hash_frozen_local_transformers_load() -> str:
    """Bypass torch<2.6 rejection only for parity-hashed local quality files."""
    runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
    if runtime.get("status") != "FROZEN_PARITY_PASS":
        raise RuntimeError("trusted local load requires a passed runtime freeze")
    allowed = {
        str(Path(row["path"]).resolve()): row["sha256"]
        for row in runtime.get("quality_artifact_files", [])
    }
    if not allowed:
        raise RuntimeError("runtime freeze lacks per-file quality hashes")
    import transformers.modeling_utils as modeling_utils

    original = modeling_utils.load_state_dict
    if getattr(original, "_bolt_hash_scoped", False):
        return canonical_json_hash(allowed)

    def hash_scoped_load(checkpoint_file, *args, **kwargs):
        path = Path(checkpoint_file).resolve()
        expected = allowed.get(str(path))
        if expected is not None:
            if sha256_file(path) != expected:
                raise RuntimeError(f"hash-frozen quality artifact changed: {path}")
            kwargs["weights_only"] = False
        return original(checkpoint_file, *args, **kwargs)

    hash_scoped_load._bolt_hash_scoped = True  # type: ignore[attr-defined]
    modeling_utils.load_state_dict = hash_scoped_load
    return canonical_json_hash(allowed)


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def save_audio_once(path: Path, waveform: torch.Tensor, sample_rate: int) -> dict[str, Any]:
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    value = waveform.detach().cpu().to(torch.float32)
    if path.exists():
        samples, existing_sr = sf.read(str(path), always_2d=True, dtype="float32")
        existing = torch.from_numpy(samples.T.copy())
        validity = waveform_validity(existing, int(existing_sr))
        if not validity["valid"]:
            raise RuntimeError(f"existing output is invalid: {path}: {validity}")
        if int(existing_sr) != int(sample_rate) or waveform_nrmse(value, existing) > 1e-6:
            raise RuntimeError(f"existing output conflicts with deterministic recovery: {path}")
        return {
            **validity,
            "output_path": str(path),
            "output_sha256": sha256_file(path),
            "recovered_existing": True,
        }
    temporary = path.with_suffix(path.suffix + f".partial.{os.getpid()}")
    try:
        sf.write(str(temporary), value.T.numpy(), int(sample_rate), format="FLAC", subtype="PCM_24")
        samples, decoded_sr = sf.read(str(temporary), always_2d=True, dtype="float32")
        decoded = torch.from_numpy(samples.T.copy())
        validity = waveform_validity(decoded, int(decoded_sr))
        if not validity["valid"]:
            raise RuntimeError(f"generated output is invalid: {path}: {validity}")
        os.rename(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {
        **validity,
        "output_path": str(path),
        "output_sha256": sha256_file(path),
        "recovered_existing": False,
    }


class BoltScorer:
    def __init__(self, *, device: str = "cuda"):
        self.trusted_load_policy_hash = enable_hash_frozen_local_transformers_load()
        from mprm.common.config import load_config
        from scripts.collect_early_tweedie_validation import _score_common_metrics
        from scripts.launch_baseline import (
            _assert_reward_axes_match_policy,
            _build_reward_models,
            load_gate_eval_policy,
        )
        from w2_instruments import LiveDemucsPannsEnsembleInstrument

        promotion = json.loads(PROMOTION.read_text(encoding="utf-8"))
        if promotion.get("CORRECTED_INSTRUMENT_STATUS") != "PROMOTED":
            raise RuntimeError("BOLT scoring requires the promoted W2 instrument")
        candidate = promotion.get("selected_candidate") or promotion["heldout"]["selected_candidate"]
        if candidate.get("family") != "or":
            raise RuntimeError("BOLT scoring is frozen to the promoted OR candidate")
        self.candidate = candidate
        self.promotion_sha256 = sha256_file(PROMOTION)
        self.floors_record = json.loads(FLOORS.read_text(encoding="utf-8"))
        if self.floors_record.get("status") != "FROZEN_BEFORE_BOLT_OUTPUT":
            raise RuntimeError("quality floors are not frozen")
        self.gate_policy, self.gate_policy_hash = load_gate_eval_policy(
            ROOT / "configs/eval/gate_v2.yaml.draft"
        )
        config = load_config(ROOT / "configs/baselines/r2_bon.yaml")
        self.reward_models = _build_reward_models(config.reward)
        _assert_reward_axes_match_policy(self.reward_models, self.gate_policy)
        self.instrument = LiveDemucsPannsEnsembleInstrument(
            device,
            float(candidate["demucs_threshold"]),
            float(candidate["panns_threshold"]),
            "or",
        )
        self._score_common_metrics = _score_common_metrics
        calibration = _load_module(CALIBRATION_SCRIPT, "bolt_w2_calibration")
        rows = calibration.prepare_calibration()
        self.calibration_module = calibration.CAL
        self.calibration_fit = self.calibration_module.select_model(rows)
        self.calibration_audit = {
            key: value for key, value in self.calibration_fit.items() if key != "model"
        }
        self.calibration_hash = canonical_json_hash(self.calibration_audit)
        import joblib

        self.evpd = joblib.load(EVPD_MODEL)
        if self.evpd.get("promotion_sha256") != self.promotion_sha256:
            raise RuntimeError("corrected EVPD promotion hash does not match the promoted instrument")
        self.evpd_hash = sha256_file(EVPD_MODEL)

    def _calibrated_violation_probability(self, demucs: float, panns: float, requested_vocal: int) -> float:
        row = {
            "demucs_score": float(demucs),
            "panns_score": float(panns),
            "requested_vocal": int(requested_vocal),
        }
        return float(self.calibration_module.predict_probability([row], self.calibration_fit)[0])

    def score(
        self,
        *,
        audio_path: Path,
        waveform: torch.Tensor,
        sample_rate: int,
        prompt: Any,
        requested_vocal: int,
    ) -> dict[str, Any]:
        saved = save_audio_once(audio_path, waveform, sample_rate)
        instrument = self.instrument.score(audio_path)
        common = self._score_common_metrics(
            reward_models=self.reward_models,
            waveform=waveform.detach().cpu().to(torch.float32),
            sample_rate=int(sample_rate),
            prompt=prompt,
            gate_policy=self.gate_policy,
        )
        demucs = float(instrument["vocal_energy_ratio"])
        panns = float(instrument["panns_score"])
        present = int(instrument["present"])
        label_b_satisfied = int(present == int(requested_vocal))
        direction = "vocal_request" if int(requested_vocal) else "instrumental_request"
        floor = self.floors_record["directions"][direction]
        common_lcb = common.get("common_robust_lcb")
        semantic_fit = common.get("semantic_fit")
        common_ok = common_lcb is not None and math.isfinite(float(common_lcb)) and float(common_lcb) >= float(
            floor["common_robust_lcb_floor"]
        )
        clap_ok = semantic_fit is not None and math.isfinite(float(semantic_fit)) and float(semantic_fit) >= float(
            floor["clap_to_original_prompt_floor"]
        )
        quality_ok = bool(common_ok and clap_ok)
        audio_ok = bool(saved["valid"])
        cqs = int(label_b_satisfied and quality_ok and audio_ok)
        return {
            **saved,
            "promoted_instrument_sha256": self.promotion_sha256,
            "promoted_instrument_family": "or",
            "demucs_score": demucs,
            "panns_score": panns,
            "promoted_present": present,
            "label_b_satisfied": label_b_satisfied,
            "calibrated_label_b_violation_probability": self._calibrated_violation_probability(
                demucs, panns, requested_vocal
            ),
            "calibration_model_hash": self.calibration_hash,
            "common_robust_lcb": common_lcb,
            "clap_to_original_prompt": semantic_fit,
            "common_quality_floor": float(floor["common_robust_lcb_floor"]),
            "clap_prompt_floor": float(floor["clap_to_original_prompt_floor"]),
            "common_quality_floor_pass": bool(common_ok),
            "clap_prompt_floor_pass": bool(clap_ok),
            "quality_floor_status": "PASS" if quality_ok else "FAIL",
            "cqs": cqs,
            "gate_policy_hash": self.gate_policy_hash,
            "common_scores": common,
            "trusted_local_load_policy_hash": self.trusted_load_policy_hash,
            "scoring_protocol_version": SCORING_PROTOCOL_VERSION,
        }

    def audio_embedding(self, waveform: torch.Tensor, sample_rate: int) -> np.ndarray:
        import torchaudio
        from mprm.rewards.clap import ClapReward

        clap = next((model for model in self.reward_models if isinstance(model, ClapReward)), None)
        if clap is None:
            raise RuntimeError("CLAP reward model is absent")
        clap._ensure_loaded()
        value = waveform.detach().cpu().to(torch.float32)
        if sample_rate != 48_000:
            value = torchaudio.functional.resample(value, sample_rate, 48_000)
        if value.dim() == 2:
            value = value.mean(dim=0, keepdim=True)
        python_state = random.getstate()
        numpy_state = np.random.get_state()
        torch_state = torch.get_rng_state()
        cuda_states = torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None
        try:
            random.seed(CLAP_AUDIO_AUDIO_RNG_SEED)
            np.random.seed(CLAP_AUDIO_AUDIO_RNG_SEED % (2**32))
            torch.manual_seed(CLAP_AUDIO_AUDIO_RNG_SEED)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(CLAP_AUDIO_AUDIO_RNG_SEED)
            embedding = clap._model.get_audio_embedding_from_data(x=value.numpy(), use_tensor=False)
        finally:
            random.setstate(python_state)
            np.random.set_state(numpy_state)
            torch.set_rng_state(torch_state)
            if cuda_states is not None:
                torch.cuda.set_rng_state_all(cuda_states)
        vector = np.asarray(embedding, dtype=np.float64).reshape(-1)
        norm = np.linalg.norm(vector)
        if not math.isfinite(float(norm)) or norm <= 0:
            raise RuntimeError("invalid CLAP audio embedding")
        return vector / norm

    def early_evpd_probability(self, waveform: torch.Tensor, sample_rate: int) -> float:
        """Apply the frozen sigma-0.8 corrected EVPD feature and threshold model."""
        import librosa
        import torchaudio

        value = waveform.detach().cpu().to(torch.float32)
        if sample_rate != 48_000:
            value = torchaudio.functional.resample(value, sample_rate, 48_000)
        mono = value.mean(dim=0).numpy() if value.ndim == 2 else value.numpy()
        mel = librosa.feature.melspectrogram(
            y=mono.astype("float32"), sr=48_000, n_mels=64, hop_length=512
        )
        log_mel = librosa.power_to_db(mel + 1e-9)
        feature = np.concatenate(
            [
                log_mel.mean(1),
                log_mel.std(1),
                log_mel.max(1),
                np.percentile(log_mel, 25, 1),
                np.percentile(log_mel, 75, 1),
            ]
        )
        scaled = self.evpd["scaler"].transform(feature.reshape(1, -1))
        return float(self.evpd["model"].predict_proba(scaled)[0, 1])

    def audio_audio_cosine(
        self,
        left: torch.Tensor,
        right: torch.Tensor,
        sample_rate: int,
    ) -> float:
        a = self.audio_embedding(left, sample_rate)
        b = self.audio_embedding(right, sample_rate)
        return float(np.dot(a, b))
