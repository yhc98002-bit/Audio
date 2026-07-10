#!/usr/bin/env python3
"""Compare the canonical reward wrapper and Batch-3 gate on 200 real clips."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np

from mprm.common.thresholds import is_vocal_present


SELECTION_SEED = 20260709
TARGET_ROWS = 200


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def select_rows(rows: list[dict[str, str]], count: int = TARGET_ROWS) -> list[dict[str, str]]:
    eligible = [row for row in rows if row.get("media_class") == "original"]
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in eligible:
        groups[(row["set_bucket"], row["expected_demucs_label"])].append(row)
    rng = random.Random(SELECTION_SEED)
    for values in groups.values():
        rng.shuffle(values)
    selected = []
    keys = sorted(groups)
    while len(selected) < count and any(groups.values()):
        for key in keys:
            if groups[key] and len(selected) < count:
                selected.append(groups[key].pop())
    if len(selected) != count:
        raise ValueError(f"requested {count} rows but selected {len(selected)}")
    return selected


def scoring_seed(rating_id: str) -> int:
    return int.from_bytes(hashlib.sha256(rating_id.encode()).digest()[:4], "big")


def seed_rng(seed: int) -> None:
    import torch

    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_audio(path: Path):
    import soundfile as sf
    import torch

    data, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    return torch.from_numpy(data.T.copy()), int(sample_rate)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(admin_path: Path, repo_root: Path, out_dir: Path, device: str) -> str:
    import torch
    from mprm.rewards.demucs import DemucsVocalStem
    from scripts.batch3_online_harness import GateLabeler

    selected = select_rows(read_csv(admin_path))
    manifest = []
    for index, row in enumerate(selected, 1):
        path = repo_root / row["package_media_path"]
        if not path.is_file():
            raise FileNotFoundError(path)
        manifest.append(
            {
                "audit_index": index,
                "rating_id": row["rating_id"],
                "set_bucket": row["set_bucket"],
                "expected_demucs_label": row["expected_demucs_label"],
                "audio_path": str(path.relative_to(repo_root)),
                "scoring_seed": scoring_seed(row["rating_id"]),
            }
        )
    write_csv(out_dir / "CANONICAL_LABELER_AGREEMENT_MANIFEST.csv", manifest)

    gate = GateLabeler(device)
    canonical = DemucsVocalStem(device=device)
    results = []
    for row in manifest:
        waveform, sample_rate = load_audio(repo_root / row["audio_path"])
        seed_rng(int(row["scoring_seed"]))
        gate_ratio, gate_silent = gate.ratio(waveform, sample_rate)
        seed_rng(int(row["scoring_seed"]))
        canonical_ratio, canonical_silent = canonical.vocal_energy_ratio(waveform, sample_rate)
        gate_label = int(is_vocal_present(gate_ratio, gate_silent))
        canonical_label = int(is_vocal_present(canonical_ratio, canonical_silent))
        results.append(
            {
                **row,
                "sample_rate": sample_rate,
                "gate_ratio": f"{gate_ratio:.12f}",
                "canonical_ratio": f"{canonical_ratio:.12f}",
                "absolute_ratio_delta": f"{abs(gate_ratio-canonical_ratio):.12f}",
                "gate_near_silent": int(gate_silent),
                "canonical_near_silent": int(canonical_silent),
                "gate_label": gate_label,
                "canonical_label": canonical_label,
                "label_agree": int(gate_label == canonical_label),
            }
        )
        print(json.dumps({"index": row["audit_index"], "label_agree": results[-1]["label_agree"]}), flush=True)
    write_csv(out_dir / "CANONICAL_LABELER_AGREEMENT_RESULTS.csv", results)
    label_matches = sum(int(row["label_agree"]) for row in results)
    near_silent_matches = sum(row["gate_near_silent"] == row["canonical_near_silent"] for row in results)
    max_delta = max(float(row["absolute_ratio_delta"]) for row in results)
    status = "PASS" if label_matches == TARGET_ROWS and near_silent_matches == TARGET_ROWS else "FAIL"
    report = f"""# Canonical Labeler Cross-Implementation Audit

`CANONICAL_LABELER_AGREEMENT_STATUS = {status}`

Two independent project call paths were compared under identical per-clip RNG
seeds: `scripts.batch3_online_harness.GateLabeler` and
`mprm.rewards.demucs.DemucsVocalStem.vocal_energy_ratio`.

| Measure | Result |
|---|---:|
| Original clips | {len(results)} |
| Label agreement | {label_matches}/{len(results)} |
| Near-silent agreement | {near_silent_matches}/{len(results)} |
| Maximum absolute ratio delta | {max_delta:.12f} |
| Device | {device} |
| Torch | {torch.__version__} |

The audit verifies implementation agreement, not human validity of the Demucs
construct. A-prime remains human-gated.
"""
    (out_dir / "CANONICAL_LABELER_AGREEMENT_REPORT.md").write_text(report, encoding="utf-8")
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--admin", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    status = run(args.admin, args.repo_root.resolve(), args.out_dir, args.device)
    print(status)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
