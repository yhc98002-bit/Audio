"""Regenerate audio files for the human spot-check packet.

This is inference-only audio reproduction from stored prompt IDs and candidate
seeds. It does not score, train, launch crowdsourcing, or alter research
definitions.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _load_prompt_rows(sources: set[str]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for source in sorted(sources):
        with (REPO_ROOT / source).open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                out[(source, row["prompt_id"])] = row
    return out


def _prompt_from_row(row: dict[str, Any]):
    from mprm.data.prompts import Prompt

    return Prompt(
        prompt_id=row["prompt_id"],
        text=row.get("text", ""),
        lyrics=row.get("lyrics"),
        structure_hint=row.get("structure_hint"),
        duration_target=float(row.get("duration_target", 30.0)),
        metadata=row.get("metadata", {}),
        strata=row.get("strata", {}),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, default=Path("orbit-research/human_spotcheck_packet_20260528/human_spotcheck_pairs.jsonl"))
    parser.add_argument("--dataset", type=Path, default=Path("orbit-research/trajectory_candidate_dataset.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("orbit-research/human_spotcheck_packet_20260528/audio"))
    parser.add_argument("--updated-pairs", type=Path, default=Path("orbit-research/human_spotcheck_packet_20260528/human_spotcheck_pairs.with_audio.jsonl"))
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--cfg-scale", type=float, default=5.0)
    parser.add_argument("--infer-steps", type=int, default=30)
    parser.add_argument("--cfg-type", default="cfg")
    parser.add_argument("--guidance-interval", type=float, default=0.5)
    parser.add_argument("--merge-only", action="store_true", help="Only merge existing shard audio maps into the updated pair file.")
    args = parser.parse_args()

    if args.num_shards < 1 or not (0 <= args.shard_index < args.num_shards):
        raise SystemExit("invalid shard index/count")
    pairs = _read_jsonl(args.pairs)
    dataset = {row["candidate_uid"]: row for row in _read_jsonl(args.dataset)}
    needed = {}
    for pair in pairs:
        for side in ("left", "right"):
            uid = pair[f"{side}_candidate_uid"]
            if uid not in dataset:
                raise RuntimeError(f"candidate uid missing from dataset: {uid}")
            needed[uid] = dataset[uid]
    all_items = sorted(needed.items())
    shard_items = [(uid, row) for i, (uid, row) in enumerate(all_items) if i % args.num_shards == args.shard_index]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    generated = {}
    if not args.merge_only:
        prompt_rows = _load_prompt_rows({str(row["prompt_source"]) for _, row in all_items})

        from mprm.common.seeding import seed_everything
        from mprm.data.audio_io import save_audio
        from mprm.inference.ace_step import AceStepModel

        model = AceStepModel()
        for uid, row in shard_items:
            prompt_key = (str(row["prompt_source"]), str(row["prompt_id"]))
            prompt = _prompt_from_row(prompt_rows[prompt_key])
            seed = int(row["candidate_seed"])
            seed_everything(seed)
            res = model.sample(
                prompt,
                seed=seed,
                cfg_scale=float(args.cfg_scale),
                steps=int(args.infer_steps),
                return_trajectory=False,
                extras={
                    "cfg_type": args.cfg_type,
                    "guidance_interval": float(args.guidance_interval),
                    "use_erg_tag": False,
                    "use_erg_lyric": False,
                    "use_erg_diffusion": False,
                },
            )
            prompt_dir = args.output_dir / str(row["prompt_id"])
            prompt_dir.mkdir(parents=True, exist_ok=True)
            out_path = prompt_dir / f"{uid}_seed{seed}.wav"
            if not out_path.exists():
                save_audio(out_path, res.waveform, res.sample_rate)
            generated[uid] = str(out_path)
            print(json.dumps({"event": "audio_generated", "uid": uid, "path": str(out_path)}), flush=True)

        shard_map = args.output_dir.parent / f"audio_paths_shard{args.shard_index:02d}.json"
        shard_map.write_text(
            json.dumps(
                {
                    "generated_at_utc": _now_utc(),
                    "shard_index": args.shard_index,
                    "num_shards": args.num_shards,
                    "generated": generated,
                    "safety": {
                        "training_launched": False,
                        "human_crowdsourcing_launched": False,
                        "phase_d_launched": False,
                        "pruning_rl_launched": False,
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    maps = sorted(args.output_dir.parent.glob("audio_paths_shard*.json"))
    merged = {}
    for path in maps:
        payload = json.loads(path.read_text(encoding="utf-8"))
        merged.update(payload.get("generated") or {})
    updated_pairs = []
    for pair in pairs:
        row = dict(pair)
        for side in ("left", "right"):
            uid = row[f"{side}_candidate_uid"]
            if uid in merged:
                row[f"{side}_audio_path"] = merged[uid]
        row["audio_status"] = "present" if row.get("left_audio_path") and row.get("right_audio_path") else "partial"
        updated_pairs.append(row)
    with args.updated_pairs.open("w", encoding="utf-8") as f:
        for row in updated_pairs:
            f.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
    present = sum(1 for row in updated_pairs if row["audio_status"] == "present")
    manifest = args.output_dir.parent / "HUMAN_SPOTCHECK_PACKET_MANIFEST.md"
    manifest.write_text(
        "\n".join(
            [
                "# Human Spot-Check Packet Manifest",
                "",
                f"Generated UTC: `{_now_utc()}`",
                "",
                "This packet is prepared for PI/manual listening only. No crowdsourcing or human eval was launched.",
                "",
                f"- Pair manifest without audio paths: `{args.pairs}`",
                f"- Pair manifest with audio paths: `{args.updated_pairs}`",
                f"- Scoring template: `{args.output_dir.parent / 'scoring_sheet_template.csv'}`",
                f"- Audio directory: `{args.output_dir}`",
                f"- Pairs: `{len(updated_pairs)}`",
                f"- Pairs with both audio files present: `{present}`",
                f"- Unique candidate audio files mapped: `{len(merged)}`",
                f"- Audio status: `{'present' if present == len(updated_pairs) else 'partial'}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "generated": len(generated), "updated_pairs": str(args.updated_pairs)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
