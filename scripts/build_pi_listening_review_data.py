"""Build static data for the PI listening-review web UI.

The generated file is a browser-loadable JavaScript assignment. It is derived
from the already prepared human spot-check packet and prompt manifests; it does
not modify audio, scoring outputs, reward definitions, or run artifacts.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _audio_path_for_packet(packet_dir: Path, path_value: str) -> str:
    path = Path(path_value)
    try:
        return path.relative_to(packet_dir).as_posix()
    except ValueError:
        parts = path.parts
        if "audio" in parts:
            return Path(*parts[parts.index("audio") :]).as_posix()
        return path.as_posix()


def _load_candidate_rows(dataset_path: Path, candidate_uids: set[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with dataset_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            uid = str(row.get("candidate_uid"))
            if uid in candidate_uids:
                out[uid] = row
                if len(out) == len(candidate_uids):
                    break
    missing = sorted(candidate_uids - set(out))
    if missing:
        raise RuntimeError(f"missing candidate rows: {missing[:5]}")
    return out


def _load_prompt_rows(candidate_rows: dict[str, dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    sources = sorted({str(row["prompt_source"]) for row in candidate_rows.values()})
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for source in sources:
        source_path = REPO_ROOT / source
        for row in _read_jsonl(source_path):
            out[(source, str(row["prompt_id"]))] = row
    return out


def _candidate_summary(row: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "candidate_uid",
        "candidate_index",
        "candidate_seed",
        "duration_actual_s",
        "final_rank_common_robust_lcb",
        "label_final_winner",
        "label_final_top2",
        "label_final_top4",
    ]
    return {key: row.get(key) for key in keys}


def build_payload(packet_dir: Path, dataset_path: Path) -> dict[str, Any]:
    pairs_path = packet_dir / "human_spotcheck_pairs.with_audio.jsonl"
    pairs = _read_jsonl(pairs_path)
    candidate_uids = {
        str(pair[f"{side}_candidate_uid"])
        for pair in pairs
        for side in ("left", "right")
    }
    candidate_rows = _load_candidate_rows(dataset_path, candidate_uids)
    prompt_rows = _load_prompt_rows(candidate_rows)

    review_pairs: list[dict[str, Any]] = []
    for index, pair in enumerate(pairs):
        left_uid = str(pair["left_candidate_uid"])
        right_uid = str(pair["right_candidate_uid"])
        left_row = candidate_rows[left_uid]
        prompt_key = (str(left_row["prompt_source"]), str(left_row["prompt_id"]))
        prompt = prompt_rows.get(prompt_key)
        if prompt is None:
            raise RuntimeError(f"missing prompt row for {prompt_key}")
        if str(prompt["prompt_id"]) != str(pair["prompt_id"]):
            raise RuntimeError(f"prompt mismatch for pair {pair['pair_id']}")

        review_pairs.append(
            {
                "index": index,
                "pair_id": pair["pair_id"],
                "prompt_id": pair["prompt_id"],
                "split": pair.get("split"),
                "genre": pair.get("genre"),
                "vocal_stratum": pair.get("vocal_stratum"),
                "rater_blinding": pair.get("rater_blinding"),
                "comparison_type": pair.get("comparison_type"),
                "prompt": {
                    "text": prompt.get("text") or "",
                    "lyrics": prompt.get("lyrics") or "",
                    "structure_hint": prompt.get("structure_hint") or "",
                    "duration_target": prompt.get("duration_target"),
                    "strata": prompt.get("strata") or {},
                },
                "left": {
                    "display_label": "A",
                    "audio_path": _audio_path_for_packet(packet_dir, str(pair["left_audio_path"])),
                    **_candidate_summary(left_row),
                },
                "right": {
                    "display_label": "B",
                    "audio_path": _audio_path_for_packet(packet_dir, str(pair["right_audio_path"])),
                    **_candidate_summary(candidate_rows[right_uid]),
                },
            }
        )

    return {
        "generated_utc": _now_utc(),
        "packet_dir": packet_dir.as_posix(),
        "source_pairs": pairs_path.as_posix(),
        "source_dataset": dataset_path.as_posix(),
        "blinding": "A/B order is randomized; method labels are hidden in the UI.",
        "pairs": review_pairs,
        "safety": {
            "training_launched": False,
            "human_crowdsourcing_launched": False,
            "phase_d_launched": False,
            "reward_definitions_changed": False,
            "raw_audio_modified": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packet-dir",
        type=Path,
        default=Path("orbit-research/human_spotcheck_packet_20260528"),
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("orbit-research/trajectory_candidate_dataset.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("orbit-research/human_spotcheck_packet_20260528/pi_listening_review_data.js"),
    )
    args = parser.parse_args()

    packet_dir = args.packet_dir
    dataset_path = args.dataset
    output = args.output
    payload = build_payload(packet_dir, dataset_path)
    output.write_text(
        "window.PI_LISTENING_REVIEW_DATA = "
        + json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
        + ";\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "pairs": len(payload["pairs"]), "output": output.as_posix()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
