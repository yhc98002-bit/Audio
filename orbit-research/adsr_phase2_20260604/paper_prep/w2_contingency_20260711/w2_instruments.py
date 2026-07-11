#!/usr/bin/env python3
"""Pluggable instruments for the W2 relabel contingency."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "paper_prep/scripts"))
from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD  # noqa: E402
from rating_provenance import (  # noqa: E402
    parse_rating_source,
    require_validated_judge_metadata,
)


THRESHOLD = VOCAL_PRESENCE_THRESHOLD


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class CurrentDemucsInstrument:
    instrument_id = "current_demucs_htdemucs_threshold_0p1791"

    def __init__(self, device: str = "cuda", threshold: float = THRESHOLD):
        self.device = device
        self.threshold = threshold
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from mprm.rewards.demucs import DemucsVocalStem

            self._model = DemucsVocalStem(device=self.device)
        return self._model

    def score(self, path: Path) -> dict:
        import numpy as np
        import soundfile as sf
        import torch

        random.seed(20260711)
        np.random.seed(20260711)
        torch.manual_seed(20260711)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(20260711)
        audio, sample_rate = sf.read(str(path), always_2d=True, dtype="float32")
        waveform = torch.from_numpy(audio.T.copy())
        ratio, near_silent = self._ensure_model().vocal_energy_ratio(
            waveform, int(sample_rate)
        )
        return {
            "instrument_id": self.instrument_id,
            "vocal_energy_ratio": ratio,
            "near_silent": bool(near_silent),
            "present": int(ratio >= self.threshold and not near_silent),
            "threshold": self.threshold,
        }


class HumanCalibratedThresholdInstrument(CurrentDemucsInstrument):
    def __init__(self, device: str, threshold: float, calibration_artifact: Path):
        if not 0 < threshold < 1:
            raise ValueError("human-calibrated threshold must be in (0, 1)")
        if not calibration_artifact.is_file():
            raise FileNotFoundError(calibration_artifact)
        super().__init__(device=device, threshold=threshold)
        self.instrument_id = f"human_calibrated_demucs_threshold_{threshold:.8f}"
        self.calibration_artifact = str(calibration_artifact.resolve())

    def score(self, path: Path) -> dict:
        result = super().score(path)
        result["instrument_id"] = self.instrument_id
        result["calibration_artifact"] = self.calibration_artifact
        return result


class DemucsPannsEnsembleInstrument(CurrentDemucsInstrument):
    def __init__(
        self,
        device: str,
        panns_scores: Path,
        panns_threshold: float,
        decision_rule: str,
    ):
        if decision_rule not in {"or", "and"}:
            raise ValueError("two-instrument decision_rule must be 'or' or 'and'")
        super().__init__(device=device)
        self.instrument_id = f"demucs_panns_{decision_rule}"
        self.panns_threshold = panns_threshold
        self.decision_rule = decision_rule
        with panns_scores.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.panns = {row["audio_sha256"]: float(row["panns_score"]) for row in rows}
        if len(self.panns) != len(rows):
            raise ValueError("PANNs score table contains duplicate audio hashes")

    def score(self, path: Path) -> dict:
        result = super().score(path)
        audio_hash = sha256_file(path)
        if audio_hash not in self.panns:
            raise ValueError(f"missing PANNs score for {path}")
        panns_present = self.panns[audio_hash] >= self.panns_threshold
        demucs_present = bool(result["present"])
        result.update(
            {
                "instrument_id": self.instrument_id,
                "panns_score": self.panns[audio_hash],
                "panns_threshold": self.panns_threshold,
                "demucs_present": int(demucs_present),
                "present": int(
                    demucs_present or panns_present
                    if self.decision_rule == "or"
                    else demucs_present and panns_present
                ),
            }
        )
        return result


class ValidatedJudgeInstrument:
    def __init__(self, labels: Path, metadata: Path):
        record = json.loads(metadata.read_text(encoding="utf-8"))
        source = parse_rating_source(record.get("rating_source", ""))
        prepared = {
            "judge_validation_status": record.get("validation_status", ""),
            "judge_model_id": record.get("model_id", ""),
            "judge_gold_set_hash": record.get("gold_set_hash", ""),
            "judge_calibration_metrics": json.dumps(record.get("calibration_metrics", {})),
            "judge_raw_response_ledger": record.get("raw_response_ledger", ""),
            "judge_raw_response_ledger_sha256": record.get("raw_response_ledger_sha256", ""),
        }
        require_validated_judge_metadata(prepared, source)
        with labels.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.labels = {row["audio_sha256"]: row["label"].strip().lower() for row in rows}
        if len(self.labels) != len(rows) or not set(self.labels.values()) <= {"yes", "no"}:
            raise ValueError("validated-judge labels are duplicate or invalid")
        self.instrument_id = source.raw
        self.metadata = prepared

    def score(self, path: Path) -> dict:
        audio_hash = sha256_file(path)
        if audio_hash not in self.labels:
            raise ValueError(f"missing validated-judge label for {path}")
        return {
            "instrument_id": self.instrument_id,
            "present": int(self.labels[audio_hash] == "yes"),
            **self.metadata,
        }
